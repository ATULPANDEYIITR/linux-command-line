#!/usr/bin/env node
'use strict';

/*
 * Database Infrastructure Fundamentals
 *
 * Event-driven simulation covering:
 * - server roles
 * - storage pages
 * - transactions
 * - write-ahead logging
 * - asynchronous and synchronous replication
 * - status monitoring
 * - failover
 * - availability
 *
 * Node.js standard-library APIs are sufficient for this implementation.
 */

const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

const ServerRole = Object.freeze({
  PRIMARY: 'PRIMARY',
  REPLICA: 'REPLICA',
});

const ReplicationMode = Object.freeze({
  ASYNC: 'ASYNC',
  SYNC: 'SYNC',
});

const TransactionState = Object.freeze({
  ACTIVE: 'ACTIVE',
  COMMITTED: 'COMMITTED',
  ABORTED: 'ABORTED',
});

class DatabaseError extends Error {}
class TransactionError extends DatabaseError {}
class ReplicationError extends DatabaseError {}
class ValidationError extends DatabaseError {}

function deepClone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function stableHash(value) {
  return crypto
    .createHash('sha256')
    .update(JSON.stringify(value))
    .digest('hex');
}

class Page {
  constructor(id, capacity) {
    this.id = id;
    this.capacity = capacity;
    this.records = new Map();
  }

  hasSpace(key) {
    return this.records.has(key) || this.records.size < this.capacity;
  }

  put(key, value) {
    if (!this.hasSpace(key)) {
      throw new DatabaseError(`Page ${this.id} is full`);
    }
    this.records.set(key, deepClone(value));
  }

  delete(key) {
    this.records.delete(key);
  }
}

class StorageEngine {
  constructor(pageCapacity = 4) {
    if (!Number.isInteger(pageCapacity) || pageCapacity < 1) {
      throw new ValidationError('Page capacity must be a positive integer');
    }

    this.pageCapacity = pageCapacity;
    this.pages = [];
  }

  locatePage(key) {
    const existing = this.pages.find(page => page.records.has(key));
    if (existing) return existing;

    const available = this.pages.find(page => page.hasSpace(key));
    if (available) return available;

    const page = new Page(this.pages.length, this.pageCapacity);
    this.pages.push(page);
    return page;
  }

  write(key, value) {
    if (typeof key !== 'string' || key.length === 0) {
      throw new ValidationError('Storage key is required');
    }
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      throw new ValidationError('Storage value must be an object');
    }

    this.locatePage(key).put(key, value);
  }

  delete(key) {
    for (const page of this.pages) {
      if (page.records.has(key)) {
        page.delete(key);
        return;
      }
    }
  }

  read(key) {
    for (const page of this.pages) {
      if (page.records.has(key)) {
        return deepClone(page.records.get(key));
      }
    }
    return null;
  }

  snapshot() {
    const snapshot = {};
    for (const page of this.pages) {
      for (const [key, value] of page.records) {
        snapshot[key] = deepClone(value);
      }
    }
    return snapshot;
  }

  restore(snapshot) {
    this.pages = [];
    for (const [key, value] of Object.entries(snapshot)) {
      this.write(key, value);
    }
  }
}

class Transaction {
  constructor(id) {
    this.id = id;
    this.state = TransactionState.ACTIVE;
    this.writes = new Map();
  }

  stage(key, value) {
    if (this.state !== TransactionState.ACTIVE) {
      throw new TransactionError('Transaction is not active');
    }
    this.writes.set(key, deepClone(value));
  }
}

class DatabaseServer extends EventEmitter {
  constructor(name, role, pageCapacity = 4) {
    super();

    if (!name || !Object.values(ServerRole).includes(role)) {
      throw new ValidationError('Invalid server definition');
    }

    this.name = name;
    this.role = role;
    this.storage = new StorageEngine(pageCapacity);
    this.wal = [];
    this.nextLsn = 1;
    this.nextTransactionId = 1;
    this.committedTransactions = new Set();
    this.replayLsn = 0;
    this.available = true;
    this.checkpointLsn = 0;
  }

  ensureAvailable() {
    if (!this.available) {
      throw new DatabaseError(`${this.name} is unavailable`);
    }
  }

  begin() {
    this.ensureAvailable();
    return new Transaction(this.nextTransactionId++);
  }

  read(key, transaction = null) {
    this.ensureAvailable();

    if (transaction?.writes.has(key)) {
      return deepClone(transaction.writes.get(key));
    }

    return this.storage.read(key);
  }

  createWalRecord(transactionId, operation, key, value) {
    const record = {
      lsn: this.nextLsn++,
      transactionId,
      operation,
      key,
      value: deepClone(value),
    };

    record.checksum = stableHash(record);
    return record;
  }

  commit(transaction) {
    this.ensureAvailable();

    if (this.role !== ServerRole.PRIMARY) {
      throw new TransactionError('Only the primary accepts writes');
    }

    if (transaction.state !== TransactionState.ACTIVE) {
      throw new TransactionError('Transaction is not active');
    }

    const records = [];

    for (const [key, value] of transaction.writes) {
      records.push(
        this.createWalRecord(
          transaction.id,
          value === null ? 'DELETE' : 'UPSERT',
          key,
          value
        )
      );
    }

    // WAL is appended before the data pages are changed.
    this.wal.push(...records);

    const backup = this.storage.snapshot();

    try {
      for (const record of records) {
        if (record.operation === 'DELETE') {
          this.storage.delete(record.key);
        } else {
          this.storage.write(record.key, record.value);
        }
      }
    } catch (error) {
      this.storage.restore(backup);
      transaction.state = TransactionState.ABORTED;
      throw error;
    }

    transaction.state = TransactionState.COMMITTED;
    this.committedTransactions.add(transaction.id);

    this.emit('commit', {
      server: this.name,
      transactionId: transaction.id,
      records,
    });

    return records;
  }

  rollback(transaction) {
    if (transaction.state !== TransactionState.ACTIVE) {
      throw new TransactionError('Transaction is not active');
    }

    transaction.writes.clear();
    transaction.state = TransactionState.ABORTED;
    this.emit('rollback', { transactionId: transaction.id });
  }

  checkpoint() {
    this.ensureAvailable();
    this.checkpointLsn = this.wal.at(-1)?.lsn ?? 0;
    this.emit('checkpoint', {
      server: this.name,
      lsn: this.checkpointLsn,
    });
  }

  crash() {
    this.available = false;
    this.emit('unavailable', { server: this.name });
  }

  recover() {
    this.storage = new StorageEngine(this.storage.pageCapacity);

    for (const record of this.wal) {
      if (!this.committedTransactions.has(record.transactionId)) continue;

      const copy = { ...record };
      const checksum = copy.checksum;
      delete copy.checksum;

      if (stableHash(copy) !== checksum) {
        throw new DatabaseError(`Corrupt WAL at LSN ${record.lsn}`);
      }

      if (record.operation === 'DELETE') {
        this.storage.delete(record.key);
      } else {
        this.storage.write(record.key, record.value);
      }
    }

    this.available = true;
    this.emit('recovered', { server: this.name });
  }
}

class ReplicationCluster extends EventEmitter {
  constructor(primary) {
    super();

    if (primary.role !== ServerRole.PRIMARY) {
      throw new ValidationError('Cluster requires a primary');
    }

    this.primary = primary;
    this.replicas = new Map();
    this.queues = new Map();
    this.mode = ReplicationMode.ASYNC;
  }

  addReplica(replica) {
    if (replica.role !== ServerRole.REPLICA) {
      throw new ValidationError('Server must have REPLICA role');
    }

    this.replicas.set(replica.name, replica);
    this.queues.set(replica.name, []);
  }

  commit(transaction, requiredSynchronousAcks = 0) {
    const records = this.primary.commit(transaction);

    for (const replica of this.replicas.values()) {
      this.queues.get(replica.name).push(...records);
    }

    if (this.mode === ReplicationMode.SYNC) {
      this.replicateAll();

      const targetLsn = records.at(-1)?.lsn ?? 0;
      const acknowledgements = [...this.replicas.values()]
        .filter(replica => replica.replayLsn >= targetLsn)
        .length;

      if (acknowledgements < requiredSynchronousAcks) {
        throw new ReplicationError(
          'Required synchronous acknowledgements were not received'
        );
      }
    }

    this.emit('replicationQueued', {
      transactionId: transaction.id,
      records: records.length,
    });
  }

  replicateAll() {
    for (const replica of this.replicas.values()) {
      if (!replica.available) continue;

      const queue = this.queues.get(replica.name);

      for (const record of queue) {
        if (record.lsn <= replica.replayLsn) continue;

        if (record.operation === 'DELETE') {
          replica.storage.delete(record.key);
        } else {
          replica.storage.write(record.key, record.value);
        }

        replica.replayLsn = record.lsn;
      }

      queue.length = 0;
    }
  }

  lag(replica) {
    return Math.max(
      0,
      (this.primary.nextLsn - 1) - replica.replayLsn
    );
  }

  failover(replicaName) {
    const replica = this.replicas.get(replicaName);

    if (!replica) {
      throw new ReplicationError('Unknown replica');
    }

    if (!replica.available) {
      throw new ReplicationError('Unavailable replica cannot be promoted');
    }

    this.primary.role = ServerRole.REPLICA;
    replica.role = ServerRole.PRIMARY;
    this.primary = replica;

    this.emit('failover', { newPrimary: replica.name });
    return replica;
  }
}

async function runHealthCheck(cluster) {
  await new Promise(resolve => setTimeout(resolve, 5));

  return {
    primary: {
      name: cluster.primary.name,
      available: cluster.primary.available,
      replayLsn: cluster.primary.replayLsn,
    },
    replicas: [...cluster.replicas.values()].map(replica => ({
      name: replica.name,
      available: replica.available,
      replayLsn: replica.replayLsn,
      lag: cluster.lag(replica),
    })),
  };
}

function assertEmployee(employee) {
  if (
    !employee ||
    typeof employee.name !== 'string' ||
    employee.name.trim().length === 0 ||
    !Number.isFinite(employee.salary) ||
    employee.salary < 0
  ) {
    throw new ValidationError('Invalid employee record');
  }
}

async function main() {
  console.log('DATABASE INFRASTRUCTURE FUNDAMENTALS');
  console.log('====================================');

  const primary = new DatabaseServer(
    'orders-primary',
    ServerRole.PRIMARY,
    2
  );

  const replicaA = new DatabaseServer(
    'orders-replica-a',
    ServerRole.REPLICA,
    2
  );

  const replicaB = new DatabaseServer(
    'orders-replica-b',
    ServerRole.REPLICA,
    2
  );

  primary.on('commit', event => {
    console.log(`Committed transaction ${event.transactionId} on ${event.server}`);
  });

  const cluster = new ReplicationCluster(primary);
  cluster.addReplica(replicaA);
  cluster.addReplica(replicaB);

  console.log('\nTRANSACTION');

  const transaction = primary.begin();
  transaction.stage('customer:C100', {
    name: 'Riya',
    creditLimit: 100000,
  });
  transaction.stage('order:O900', {
    customer: 'C100',
    amount: 2499,
    status: 'PAID',
  });

  cluster.commit(transaction);

  console.log('Primary order:', primary.read('order:O900'));
  console.log('Replica lag before replay:', cluster.lag(replicaA));

  cluster.replicateAll();

  console.log('Replica order:', replicaA.read('order:O900'));
  console.log('Replica lag after replay:', cluster.lag(replicaA));

  console.log('\nSYNCHRONOUS REPLICATION');

  cluster.mode = ReplicationMode.SYNC;

  const synchronousTransaction = primary.begin();
  synchronousTransaction.stage('inventory:SKU-10', {
    quantity: 75,
    warehouse: 'LKO',
  });

  cluster.commit(synchronousTransaction, 2);
  console.log('Synchronous replication requirement satisfied.');

  console.log('\nCHECKPOINT AND RECOVERY');

  primary.checkpoint();
  console.log('Checkpoint LSN:', primary.checkpointLsn);

  primary.crash();

  try {
    primary.read('order:O900');
  } catch (error) {
    console.log('Expected availability error:', error.message);
  }

  primary.recover();
  console.log('Recovered order:', primary.read('order:O900'));

  console.log('\nVALIDATION');

  try {
    const invalidEmployee = {
      name: '',
      salary: -10,
    };
    assertEmployee(invalidEmployee);
  } catch (error) {
    console.log('Rejected invalid employee:', error.message);
  }

  console.log('\nFAILOVER');

  cluster.replicateAll();
  replicaA.crash();

  const promoted = cluster.failover('orders-replica-b');
  console.log('New primary:', promoted.name);
  console.log('New primary role:', promoted.role);

  console.log('\nHEALTH');

  const health = await runHealthCheck(cluster);
  console.log(JSON.stringify(health, null, 2));

  if (replicaB.read('order:O900') === null) {
    throw new Error('Replica B should contain replicated order data');
  }

  console.log('\nPerformance considerations:');
  console.log('- Page scans are linear in page count in this simulation.');
  console.log('- Production engines use indexes and buffer pools.');
  console.log('- Synchronous replication adds commit latency.');
  console.log('- Asynchronous replication permits lag during network or I/O pressure.');

  console.log('\nSecurity considerations:');
  console.log('- Restrict failover and administrative operations.');
  console.log('- Authenticate replication peers.');
  console.log('- Encrypt database traffic.');
  console.log('- Protect WAL and storage files from unauthorized access.');
}

main().catch(error => {
  console.error(`Fatal error: ${error.message}`);
  process.exitCode = 1;
});
