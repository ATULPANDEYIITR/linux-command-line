'use strict';

/*
 * Managed Database Services
 *
 * Event-driven operational model covering:
 * - automated patching
 * - backups and retention
 * - replicas and replication lag
 * - horizontal read scaling
 * - storage/compute scaling
 * - health checks
 * - failover
 * - policy evaluation
 *
 * Node.js standard library only.
 */

const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

const DatabaseState = Object.freeze({
  AVAILABLE: 'available',
  MAINTENANCE: 'maintenance',
  FAILING_OVER: 'failing_over',
  DEGRADED: 'degraded',
  FAILED: 'failed'
});

const ReplicaState = Object.freeze({
  STREAMING: 'streaming',
  LAGGING: 'lagging',
  FAILED: 'failed'
});

class ManagedDatabaseError extends Error {}
class ValidationError extends ManagedDatabaseError {}
class AvailabilityError extends ManagedDatabaseError {}

function requirePositiveInteger(value, field) {
  if (!Number.isInteger(value) || value <= 0) {
    throw new ValidationError(`${field} must be a positive integer`);
  }
}

function nowIso() {
  return new Date().toISOString();
}

class BackupManager {
  constructor(retentionDays) {
    if (!Number.isInteger(retentionDays) || retentionDays < 0 || retentionDays > 35) {
      throw new ValidationError('Retention must be between 0 and 35 days');
    }
    this.retentionDays = retentionDays;
    this.backups = new Map();
  }

  create(databaseName, lsn, sizeGb) {
    const id = crypto.randomUUID();
    const checksum = crypto
      .createHash('sha256')
      .update(`${databaseName}:${lsn}:${nowIso()}`)
      .digest('hex');

    const backup = Object.freeze({
      id,
      databaseName,
      lsn,
      sizeGb,
      checksum,
      createdAt: nowIso()
    });

    this.backups.set(id, backup);
    return backup;
  }

  purge() {
    if (this.retentionDays === 0) {
      const count = this.backups.size;
      this.backups.clear();
      return count;
    }

    const cutoff = Date.now() - this.retentionDays * 24 * 60 * 60 * 1000;
    let removed = 0;

    for (const [id, backup] of this.backups) {
      if (new Date(backup.createdAt).getTime() < cutoff) {
        this.backups.delete(id);
        removed += 1;
      }
    }

    return removed;
  }

  get(id) {
    const backup = this.backups.get(id);
    if (!backup) {
      throw new ValidationError(`Backup ${id} does not exist`);
    }
    return backup;
  }
}

class ReplicationManager {
  constructor(primaryRegion) {
    this.primaryRegion = primaryRegion;
    this.replicas = new Map();
  }

  addReplica(region, lsn) {
    if (!region || region === this.primaryRegion) {
      throw new ValidationError('Replica region must differ from primary region');
    }

    if ([...this.replicas.values()].some(replica => replica.region === region)) {
      throw new ValidationError(`Replica already exists in ${region}`);
    }

    const replica = {
      id: crypto.randomUUID(),
      region,
      state: ReplicaState.STREAMING,
      lagSeconds: 1,
      replayedLsn: lsn
    };

    this.replicas.set(replica.id, replica);
    return replica;
  }

  applyLag(id, seconds, primaryLsn) {
    const replica = this.replicas.get(id);

    if (!replica) {
      throw new ValidationError('Replica does not exist');
    }

    if (replica.state === ReplicaState.FAILED) {
      throw new AvailabilityError('Failed replica cannot replay changes');
    }

    replica.lagSeconds = Math.max(0, replica.lagSeconds + seconds);

    if (replica.lagSeconds > 60) {
      replica.state = ReplicaState.LAGGING;
    } else {
      replica.state = ReplicaState.STREAMING;
      replica.replayedLsn = primaryLsn;
    }
  }

  healthyReplica() {
    return [...this.replicas.values()].find(
      replica => replica.state === ReplicaState.STREAMING
    );
  }

  allHealthy() {
    return [...this.replicas.values()].every(
      replica => replica.state === ReplicaState.STREAMING
    );
  }
}

class ManagedDatabase extends EventEmitter {
  constructor(config) {
    super();

    const {
      name,
      engine,
      version,
      region,
      storageGb,
      computeUnits,
      multiAz,
      backupRetentionDays,
      maintenanceHour = 2
    } = config;

    if (!name || !engine || !version || !region) {
      throw new ValidationError('Database identity fields are required');
    }

    requirePositiveInteger(storageGb, 'storageGb');
    requirePositiveInteger(computeUnits, 'computeUnits');

    if (storageGb < 20) {
      throw new ValidationError('Storage must be at least 20 GB');
    }

    this.name = name;
    this.engine = engine;
    this.version = version;
    this.region = region;
    this.storageGb = storageGb;
    this.computeUnits = computeUnits;
    this.multiAz = Boolean(multiAz);
    this.maintenanceHour = maintenanceHour;

    this.state = DatabaseState.AVAILABLE;
    this.lsn = 0;
    this.audit = [];

    this.backups = new BackupManager(backupRetentionDays);
    this.replication = new ReplicationManager(region);

    this.on('operation', event => {
      this.audit.push({
        id: crypto.randomUUID(),
        timestamp: nowIso(),
        ...event
      });
    });
  }

  emitOperation(action, result, details = {}) {
    this.emit('operation', {
      action,
      result,
      details
    });
  }

  assertAvailable() {
    if (![DatabaseState.AVAILABLE, DatabaseState.DEGRADED].includes(this.state)) {
      throw new AvailabilityError(`Database is ${this.state}`);
    }
  }

  async write(records) {
    requirePositiveInteger(records, 'records');
    this.assertAvailable();

    this.lsn += records;

    this.emitOperation('write', 'success', {
      records,
      lsn: this.lsn
    });

    return this.lsn;
  }

  async createBackup() {
    this.assertAvailable();

    const backup = this.backups.create(
      this.name,
      this.lsn,
      Math.max(1, Math.round(this.storageGb * 0.65))
    );

    this.emitOperation('backup', 'success', {
      backupId: backup.id
    });

    return backup;
  }

  async patch(targetVersion, requestedHour) {
    if (!targetVersion) {
      throw new ValidationError('Target version is required');
    }

    if (requestedHour !== this.maintenanceHour) {
      throw new ValidationError('Patch is outside the maintenance window');
    }

    this.assertAvailable();
    this.state = DatabaseState.MAINTENANCE;

    try {
      this.version = targetVersion;

      this.emitOperation('patch', 'success', {
        targetVersion
      });
    } finally {
      this.state = DatabaseState.AVAILABLE;
    }
  }

  scaleStorage(newSize) {
    requirePositiveInteger(newSize, 'newSize');

    if (newSize < this.storageGb) {
      throw new ValidationError('Storage reduction is not supported');
    }

    const previous = this.storageGb;
    this.storageGb = newSize;

    this.emitOperation('storage_scale', 'success', {
      previous,
      current: newSize
    });
  }

  scaleCompute(newUnits) {
    requirePositiveInteger(newUnits, 'newUnits');

    const previous = this.computeUnits;
    this.computeUnits = newUnits;

    this.emitOperation('compute_scale', 'success', {
      previous,
      current: newUnits
    });
  }

  async failover() {
    if (!this.multiAz) {
      throw new AvailabilityError('Multi-AZ is required for failover');
    }

    const replica = this.replication.healthyReplica();

    if (!replica) {
      this.state = DatabaseState.FAILED;
      this.emitOperation('failover', 'failed', {
        reason: 'No healthy replica'
      });
      throw new AvailabilityError('No healthy replica is available');
    }

    this.state = DatabaseState.FAILING_OVER;

    await new Promise(resolve => setTimeout(resolve, 20));

    this.region = replica.region;
    this.replication.primaryRegion = replica.region;
    this.state = DatabaseState.AVAILABLE;

    this.emitOperation('failover', 'success', {
      newPrimaryRegion: this.region
    });
  }

  healthCheck() {
    const checks = [
      {
        name: 'storage',
        passed: this.storageGb >= 20
      },
      {
        name: 'compute',
        passed: this.computeUnits >= 1
      },
      {
        name: 'replication',
        passed: this.replication.allHealthy()
      },
      {
        name: 'state',
        passed: [DatabaseState.AVAILABLE, DatabaseState.DEGRADED].includes(this.state)
      }
    ];

    const healthy = checks.every(check => check.passed);

    if (!healthy) {
      this.state = DatabaseState.DEGRADED;
    }

    this.emitOperation('health_check', healthy ? 'success' : 'warning', {
      checks
    });

    return checks;
  }

  report() {
    return {
      name: this.name,
      engine: this.engine,
      version: this.version,
      region: this.region,
      state: this.state,
      storageGb: this.storageGb,
      computeUnits: this.computeUnits,
      multiAz: this.multiAz,
      lsn: this.lsn,
      backupCount: this.backups.backups.size,
      replicas: [...this.replication.replicas.values()],
      auditEvents: this.audit.length
    };
  }
}

async function main() {
  const database = new ManagedDatabase({
    name: 'orders-prod',
    engine: 'PostgreSQL',
    version: '18.0',
    region: 'ap-south-1',
    storageGb: 250,
    computeUnits: 8,
    multiAz: true,
    backupRetentionDays: 7,
    maintenanceHour: 2
  });

  await database.write(500);

  const backup = await database.createBackup();

  const replica = database.replication.addReplica(
    'ap-southeast-1',
    database.lsn
  );

  await database.write(200);
  database.replication.applyLag(replica.id, 2, database.lsn);

  database.scaleStorage(400);
  database.scaleCompute(12);

  await database.patch('18.1', 2);

  console.log('\n=== Health Checks ===');
  console.table(database.healthCheck());

  await database.failover();

  console.log('\n=== Backup ===');
  console.log(database.backups.get(backup.id));

  console.log('\n=== Database Report ===');
  console.log(JSON.stringify(database.report(), null, 2));

  try {
    database.scaleStorage(100);
  } catch (error) {
    console.log(`Expected failure: ${error.message}`);
  }

  try {
    await database.patch('18.2', 15);
  } catch (error) {
    console.log(`Expected maintenance failure: ${error.message}`);
  }

  if (database.state !== DatabaseState.AVAILABLE) {
    throw new Error('Database should be available after successful failover');
  }
}

main().catch(error => {
  console.error(`Fatal operational error: ${error.message}`);
  process.exitCode = 1;
});
