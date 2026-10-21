'use strict';

const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

const RecoveryTier = Object.freeze({
  BACKUP_RESTORE: 'backup_restore',
  PILOT_LIGHT: 'pilot_light',
  WARM_STANDBY: 'warm_standby',
  MULTI_REGION: 'multi_region'
});

const RegionState = Object.freeze({
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  FAILED: 'failed'
});

class RecoveryError extends Error {}

class RecoveryPolicy {
  constructor({ rpoMinutes, rtoMinutes, requiredApprovals = 1 }) {
    if (!Number.isInteger(rpoMinutes) || rpoMinutes < 0) {
      throw new TypeError('RPO must be a non-negative integer');
    }

    if (!Number.isInteger(rtoMinutes) || rtoMinutes <= 0) {
      throw new TypeError('RTO must be a positive integer');
    }

    if (!Number.isInteger(requiredApprovals) || requiredApprovals < 1) {
      throw new TypeError('requiredApprovals must be positive');
    }

    this.rpoMinutes = rpoMinutes;
    this.rtoMinutes = rtoMinutes;
    this.requiredApprovals = requiredApprovals;
  }
}

class Backup {
  constructor({ id, service, createdAt, payload, location }) {
    this.id = id;
    this.service = service;
    this.createdAt = createdAt;
    this.location = location;
    this.payloadHash = crypto
      .createHash('sha256')
      .update(JSON.stringify(payload))
      .digest('hex');
  }

  ageMinutes(now = Date.now()) {
    return Math.max(0, (now - this.createdAt) / 60000);
  }
}

class Region {
  constructor(name, state = RegionState.SECONDARY, capacity = 100) {
    if (!name || capacity < 0 || capacity > 100) {
      throw new TypeError('Invalid region configuration');
    }

    this.name = name;
    this.state = state;
    this.capacity = capacity;
  }

  isAvailable() {
    return this.state !== RegionState.FAILED && this.capacity > 0;
  }
}

class Service {
  constructor({ name, policy, tier, regions }) {
    if (!name || !Object.values(RecoveryTier).includes(tier)) {
      throw new TypeError('Invalid service definition');
    }

    if (!Array.isArray(regions) || regions.length === 0) {
      throw new TypeError('A service requires at least one recovery region');
    }

    this.name = name;
    this.policy = policy;
    this.tier = tier;
    this.regions = new Set(regions);
    this.data = new Map();
    this.backups = [];
  }

  write(key, value) {
    if (!key || typeof value !== 'string') {
      throw new TypeError('Invalid service data');
    }

    this.data.set(key, value);
  }

  createBackup(location = 'secondary-object-storage') {
    const payload = Object.fromEntries(this.data.entries());

    const backup = new Backup({
      id: `${this.name}-backup-${this.backups.length + 1}`,
      service: this.name,
      createdAt: Date.now(),
      payload,
      location
    });

    this.backups.push(backup);
    return backup;
  }

  latestBackup() {
    return this.backups.at(-1) ?? null;
  }
}

class RecoveryController extends EventEmitter {
  constructor() {
    super();
    this.regions = new Map();
    this.services = new Map();
  }

  addRegion(region) {
    if (this.regions.has(region.name)) {
      throw new RecoveryError(`Region already exists: ${region.name}`);
    }

    this.regions.set(region.name, region);
  }

  addService(service) {
    for (const region of service.regions) {
      if (!this.regions.has(region)) {
        throw new RecoveryError(
          `Service ${service.name} references unknown region ${region}`
        );
      }
    }

    this.services.set(service.name, service);
  }

  failRegion(regionName) {
    const region = this.getRegion(regionName);
    region.state = RegionState.FAILED;

    this.emit('regionFailed', {
      region: regionName,
      timestamp: new Date().toISOString()
    });
  }

  evaluate(serviceName, failedRegion, targetRegion) {
    const service = this.getService(serviceName);
    const failed = this.getRegion(failedRegion);
    const target = this.getRegion(targetRegion);

    const backup = service.latestBackup();

    const checks = {
      targetConfigured: service.regions.has(targetRegion),
      targetAvailable: target.isAvailable(),
      failed: failed.state === RegionState.FAILED,
      backupAvailable: backup !== null,
      rpoMet: false,
      rtoMet: false,
      tierSupported: false
    };

    const recoveryMinutes = {
      [RecoveryTier.BACKUP_RESTORE]: 90,
      [RecoveryTier.PILOT_LIGHT]: 30,
      [RecoveryTier.WARM_STANDBY]: 10,
      [RecoveryTier.MULTI_REGION]: 2
    }[service.tier];

    checks.rtoMet = recoveryMinutes <= service.policy.rtoMinutes;

    if (backup) {
      checks.rpoMet =
        backup.ageMinutes() <= service.policy.rpoMinutes;
    }

    checks.tierSupported =
      service.tier === RecoveryTier.BACKUP_RESTORE
        ? checks.backupAvailable
        : checks.targetConfigured;

    const eligible = Object.values(checks).every(Boolean);

    return {
      service: service.name,
      failedRegion,
      targetRegion,
      tier: service.tier,
      checks,
      recoveryMinutes,
      backupAgeMinutes: backup
        ? Number(backup.ageMinutes().toFixed(2))
        : null,
      eligible
    };
  }

  recover(serviceName, failedRegion, targetRegion) {
    const evaluation = this.evaluate(
      serviceName,
      failedRegion,
      targetRegion
    );

    if (!evaluation.eligible) {
      throw new RecoveryError(
        `Recovery rejected: ${JSON.stringify(evaluation.checks)}`
      );
    }

    this.getRegion(targetRegion).state = RegionState.PRIMARY;

    this.emit('failoverCompleted', {
      service: serviceName,
      from: failedRegion,
      to: targetRegion,
      at: new Date().toISOString()
    });

    return evaluation;
  }

  audit() {
    const findings = [];

    for (const service of this.services.values()) {
      const backup = service.latestBackup();

      if (!backup) {
        findings.push(`${service.name}: no backup`);
        continue;
      }

      if (backup.ageMinutes() > service.policy.rpoMinutes) {
        findings.push(
          `${service.name}: backup age exceeds RPO`
        );
      }

      if (service.tier === RecoveryTier.MULTI_REGION) {
        const available = [...service.regions]
          .map(name => this.getRegion(name))
          .filter(region => region.isAvailable());

        if (available.length < 2) {
          findings.push(
            `${service.name}: insufficient available regions`
          );
        }
      }
    }

    return findings;
  }

  getService(name) {
    const service = this.services.get(name);
    if (!service) {
      throw new RecoveryError(`Unknown service: ${name}`);
    }
    return service;
  }

  getRegion(name) {
    const region = this.regions.get(name);
    if (!region) {
      throw new RecoveryError(`Unknown region: ${name}`);
    }
    return region;
  }
}

async function waitForHealthCheck(region) {
  // Event-driven recovery systems normally wait for an external health signal.
  // This deterministic simulation uses a short asynchronous delay.
  await new Promise(resolve => setTimeout(resolve, 25));
  return region.isAvailable();
}

async function main() {
  const controller = new RecoveryController();

  controller.on('regionFailed', event => {
    console.log(`EVENT regionFailed: ${event.region}`);
  });

  controller.on('failoverCompleted', event => {
    console.log(
      `EVENT failoverCompleted: ${event.service} ${event.from} -> ${event.to}`
    );
  });

  controller.addRegion(
    new Region('ap-south-1', RegionState.PRIMARY)
  );
  controller.addRegion(
    new Region('ap-southeast-1', RegionState.SECONDARY)
  );
  controller.addRegion(
    new Region('eu-west-1', RegionState.PRIMARY)
  );
  controller.addRegion(
    new Region('eu-central-1', RegionState.SECONDARY)
  );

  const payments = new Service({
    name: 'payments',
    policy: new RecoveryPolicy({
      rpoMinutes: 5,
      rtoMinutes: 15
    }),
    tier: RecoveryTier.WARM_STANDBY,
    regions: ['ap-south-1', 'ap-southeast-1']
  });

  payments.write('transaction-1001', 'approved');
  payments.createBackup();

  const analytics = new Service({
    name: 'analytics',
    policy: new RecoveryPolicy({
      rpoMinutes: 30,
      rtoMinutes: 60
    }),
    tier: RecoveryTier.BACKUP_RESTORE,
    regions: ['eu-west-1', 'eu-central-1']
  });

  analytics.write('report-2026-10-21', 'complete');
  const analyticsBackup = analytics.createBackup();

  // Simulate an old backup so the RPO rule fails.
  analyticsBackup.createdAt = Date.now() - 45 * 60000;

  controller.addService(payments);
  controller.addService(analytics);

  const target = controller.getRegion('ap-southeast-1');
  console.log(
    `Target health: ${await waitForHealthCheck(target)}`
  );

  controller.failRegion('ap-south-1');

  try {
    const result = controller.recover(
      'payments',
      'ap-south-1',
      'ap-southeast-1'
    );

    console.log(
      JSON.stringify(result, null, 2)
    );
  } catch (error) {
    console.error(`Unexpected recovery failure: ${error.message}`);
  }

  controller.failRegion('eu-west-1');

  try {
    controller.recover(
      'analytics',
      'eu-west-1',
      'eu-central-1'
    );
  } catch (error) {
    console.log(`Expected rejection: ${error.message}`);
  }

  console.log('\nRecovery audit:');
  console.log(controller.audit());

  // A target with zero capacity must never be selected for failover.
  controller.getRegion('ap-southeast-1').capacity = 0;

  try {
    controller.recover(
      'payments',
      'ap-south-1',
      'ap-southeast-1'
    );
  } catch (error) {
    console.log(
      `Expected capacity rejection: ${error.message}`
    );
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
