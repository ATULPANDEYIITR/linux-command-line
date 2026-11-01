'use strict';

/*
 * Database scaling case study.
 *
 * The implementation focuses on policy evaluation and event-driven workload
 * routing rather than reproducing the Python object model.
 */

const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

const ScalingMode = Object.freeze({
  VERTICAL: 'vertical',
  HORIZONTAL: 'horizontal'
});

const PartitionStrategy = Object.freeze({
  RANGE: 'range',
  HASH: 'hash'
});

const ShardStrategy = Object.freeze({
  HASH: 'hash',
  RANGE: 'range'
});

function assertPositiveInteger(value, name) {
  if (!Number.isInteger(value) || value <= 0) {
    throw new RangeError(`${name} must be a positive integer`);
  }
}

function stableHash(value) {
  const digest = crypto
    .createHash('sha256')
    .update(String(value))
    .digest();
  return digest.readUInt32BE(0);
}

class DatabaseNode {
  constructor(id, capacity) {
    if (!id || typeof id !== 'string') {
      throw new TypeError('Node ID must be a non-empty string');
    }
    assertPositiveInteger(capacity, 'Node capacity');

    this.id = id;
    this.capacity = capacity;
    this.active = 0;
    this.healthy = true;
  }

  get utilization() {
    return this.active / this.capacity;
  }

  acquire() {
    if (!this.healthy) {
      throw new Error(`Node ${this.id} is unhealthy`);
    }
    if (this.active >= this.capacity) {
      throw new Error(`Node ${this.id} has reached capacity`);
    }
    this.active += 1;
  }

  release() {
    if (this.active <= 0) {
      throw new Error(`Node ${this.id} has no active workload`);
    }
    this.active -= 1;
  }
}

class ScalingController {
  constructor(nodes = []) {
    this.nodes = new Map();
    this.events = new EventEmitter();

    for (const node of nodes) {
      this.addNode(node);
    }
  }

  addNode(node) {
    if (this.nodes.has(node.id)) {
      throw new Error(`Duplicate node: ${node.id}`);
    }
    this.nodes.set(node.id, node);
    this.events.emit('nodeAdded', { nodeId: node.id });
  }

  resizeNode(nodeId, newCapacity) {
    assertPositiveInteger(newCapacity, 'New capacity');

    const node = this.getNode(nodeId);
    if (newCapacity < node.active) {
      throw new Error('New capacity cannot be below active workload');
    }

    node.capacity = newCapacity;
    this.events.emit('nodeResized', {
      nodeId,
      capacity: newCapacity
    });
  }

  getNode(nodeId) {
    const node = this.nodes.get(nodeId);
    if (!node) {
      throw new Error(`Unknown node: ${nodeId}`);
    }
    return node;
  }

  chooseNode() {
    const candidates = [...this.nodes.values()]
      .filter(node => node.healthy && node.active < node.capacity)
      .sort((a, b) => a.utilization - b.utilization);

    if (candidates.length === 0) {
      throw new Error('No healthy node has available capacity');
    }

    return candidates[0];
  }

  route(requestId) {
    const node = this.chooseNode();
    node.acquire();

    this.events.emit('requestRouted', {
      requestId,
      nodeId: node.id
    });

    return node.id;
  }
}

class Partitioner {
  constructor(strategy, partitionCount) {
    if (!Object.values(PartitionStrategy).includes(strategy)) {
      throw new Error('Unsupported partition strategy');
    }
    assertPositiveInteger(partitionCount, 'Partition count');

    this.strategy = strategy;
    this.partitionCount = partitionCount;
  }

  locate(customerId) {
    assertPositiveInteger(customerId, 'Customer ID');

    if (this.strategy === PartitionStrategy.HASH) {
      return stableHash(customerId) % this.partitionCount;
    }

    return Math.min(
      Math.floor(customerId / 1000),
      this.partitionCount - 1
    );
  }
}

class ShardRouter {
  constructor(shardCount, strategy = ShardStrategy.HASH) {
    assertPositiveInteger(shardCount, 'Shard count');

    if (!Object.values(ShardStrategy).includes(strategy)) {
      throw new Error('Unsupported shard strategy');
    }

    this.shardCount = shardCount;
    this.strategy = strategy;
  }

  route(customerId) {
    assertPositiveInteger(customerId, 'Customer ID');

    if (this.strategy === ShardStrategy.HASH) {
      return stableHash(customerId) % this.shardCount;
    }

    return Math.min(
      Math.floor(customerId / 1000),
      this.shardCount - 1
    );
  }
}

class ShardedRepository {
  constructor(router) {
    this.router = router;
    this.data = Array.from(
      { length: router.shardCount },
      () => new Map()
    );
  }

  insert(record) {
    if (!record || !Number.isInteger(record.id)) {
      throw new TypeError('Record must contain an integer id');
    }

    const shard = this.router.route(record.customerId);

    if (this.data[shard].has(record.id)) {
      throw new Error(`Duplicate record: ${record.id}`);
    }

    this.data[shard].set(record.id, Object.freeze({ ...record }));
    return shard;
  }

  find(id, customerId) {
    const shard = this.router.route(customerId);
    return this.data[shard].get(id) ?? null;
  }

  distribution() {
    return this.data.map(bucket => bucket.size);
  }
}

function createOrders(count) {
  assertPositiveInteger(count, 'Order count');

  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    customerId: 100 + ((index * 7919) % 9000),
    amount: Number((25 + (index * 17.37) % 2500).toFixed(2))
  }));
}

function printNodes(controller) {
  for (const node of controller.nodes.values()) {
    console.log(
      `${node.id}: active=${node.active}, capacity=${node.capacity}, ` +
      `utilization=${(node.utilization * 100).toFixed(1)}%, healthy=${node.healthy}`
    );
  }
}

async function processBatch(controller, requestIds) {
  /*
   * Promise.all models concurrent request submission. Routing itself remains
   * synchronous so capacity checks happen before each request is accepted.
   */
  return Promise.all(
    requestIds.map(async requestId => ({
      requestId,
      nodeId: controller.route(requestId)
    }))
  );
}

async function main() {
  console.log('DATABASE SCALING CASE STUDY');

  const controller = new ScalingController();

  controller.events.on('nodeAdded', event => {
    console.log(`Node added: ${event.nodeId}`);
  });

  controller.events.on('nodeResized', event => {
    console.log(`Node resized: ${event.nodeId} -> ${event.capacity}`);
  });

  controller.events.on('requestRouted', event => {
    console.log(`Request ${event.requestId} routed to ${event.nodeId}`);
  });

  // Vertical scaling changes the resource ceiling of an existing node.
  const primary = new DatabaseNode('primary', 100);
  controller.addNode(primary);
  controller.resizeNode('primary', 150);

  // Horizontal scaling adds independent capacity.
  controller.addNode(new DatabaseNode('replica-1', 80));
  controller.addNode(new DatabaseNode('replica-2', 80));

  console.log('\nNode state');
  printNodes(controller);

  console.log('\nConcurrent workload');
  const results = await processBatch(
    controller,
    ['req-1', 'req-2', 'req-3', 'req-4', 'req-5']
  );
  console.log(results);

  // Partitioning decides logical data placement.
  const partitioner = new Partitioner(PartitionStrategy.HASH, 8);
  const orders = createOrders(100);
  const partitionCounts = Array(8).fill(0);

  for (const order of orders) {
    partitionCounts[partitioner.locate(order.customerId)] += 1;
  }

  console.log('\nPartition distribution');
  console.log(partitionCounts);

  // Sharding maps a logical partition to an independent database shard.
  const router = new ShardRouter(4, ShardStrategy.HASH);
  const repository = new ShardedRepository(router);

  for (const order of orders) {
    repository.insert(order);
  }

  console.log('\nShard distribution');
  console.log(repository.distribution());

  const selected = orders[20];
  const found = repository.find(selected.id, selected.customerId);

  if (!found || found.id !== selected.id) {
    throw new Error('Point lookup invariant failed');
  }

  console.log(`Point lookup succeeded for order ${selected.id}`);

  // Failure handling prevents new work from entering an unhealthy node.
  controller.getNode('replica-1').healthy = false;

  console.log('\nFailure simulation');
  printNodes(controller);

  for (let i = 0; i < 5; i += 1) {
    try {
      controller.route(`failure-test-${i}`);
    } catch (error) {
      console.error(`Routing failure: ${error.message}`);
    }
  }

  // Security: diagnostic output uses IDs only and does not expose credentials.
  console.log('\nScaling model completed successfully.');
}

main().catch(error => {
  console.error(`Fatal error: ${error.message}`);
  process.exitCode = 1;
});
