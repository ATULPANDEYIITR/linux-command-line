#!/usr/bin/env node
"use strict";

/*
 * Database replication policy and event model.
 *
 * This implementation emphasizes JavaScript-specific behavior:
 * asynchronous replication workers, events, Maps, Sets, immutable
 * transaction records, and policy evaluation.
 */

const { EventEmitter } = require("node:events");

const ReplicationMode = Object.freeze({
  SYNC: "synchronous",
  ASYNC: "asynchronous",
});

const NodeRole = Object.freeze({
  PRIMARY: "primary",
  REPLICA: "replica",
  OFFLINE: "offline",
});

class ReplicationError extends Error {}

class ReplicationNode {
  constructor(name, mode, role = NodeRole.REPLICA) {
    this.name = name;
    this.mode = mode;
    this.role = role;
    this.online = true;
    this.appliedPosition = 0;
    this.data = new Map();
    this.queue = [];
  }

  enqueue(transaction) {
    if (this.online) {
      this.queue.push(transaction);
    }
  }

  apply(limit = Infinity) {
    if (!this.online) return 0;

    let count = 0;
    while (this.queue.length && count < limit) {
      const tx = this.queue[0];

      if (tx.position <= this.appliedPosition) {
        this.queue.shift();
        continue;
      }

      if (tx.position !== this.appliedPosition + 1) {
        break;
      }

      this.data.set(tx.key, tx.value);
      this.appliedPosition = tx.position;
      this.queue.shift();
      count += 1;
    }
    return count;
  }
}

class ReplicationCluster extends EventEmitter {
  constructor() {
    super();
    this.primaryName = "primary-01";
    this.primaryOnline = true;
    this.position = 0;
    this.data = new Map();
    this.wal = [];

    this.nodes = new Map([
      [
        "replica-sync",
        new ReplicationNode("replica-sync", ReplicationMode.SYNC),
      ],
      [
        "replica-async",
        new ReplicationNode("replica-async", ReplicationMode.ASYNC),
      ],
    ]);
  }

  validateWrite(key, value) {
    if (typeof key !== "string" || key.trim() === "") {
      throw new TypeError("Write key must be a non-empty string.");
    }
    if (typeof value !== "string") {
      throw new TypeError("Write value must be a string.");
    }
    if (key.length > 256 || value.length > 4096) {
      throw new RangeError("Write exceeds configured size limits.");
    }
  }

  write(key, value) {
    if (!this.primaryOnline) {
      throw new ReplicationError("Primary is unavailable.");
    }

    this.validateWrite(key, value);

    const transaction = Object.freeze({
      position: ++this.position,
      key,
      value,
      timestamp: new Date().toISOString(),
    });

    this.wal.push(transaction);
    this.data.set(key, value);

    for (const node of this.nodes.values()) {
      node.enqueue(transaction);
    }

    const syncNodes = [...this.nodes.values()].filter(
      (node) => node.mode === ReplicationMode.SYNC
    );

    for (const node of syncNodes) {
      node.apply();
    }

    const acknowledged = syncNodes.every(
      (node) => node.online && node.appliedPosition >= transaction.position
    );

    this.emit("write", {
      transaction,
      acknowledged,
    });

    return transaction;
  }

  async processAsyncReplication(batchSize = 1, delayMs = 10) {
    if (!Number.isInteger(batchSize) || batchSize < 1) {
      throw new RangeError("Batch size must be positive.");
    }

    await new Promise((resolve) => setTimeout(resolve, delayMs));

    let applied = 0;
    for (const node of this.nodes.values()) {
      if (node.mode === ReplicationMode.ASYNC) {
        applied += node.apply(batchSize);
      }
    }

    this.emit("replication", { applied });
    return applied;
  }

  read(key, nodeName = null, requiredPosition = null) {
    if (!nodeName) return this.data.get(key);

    const node = this.nodes.get(nodeName);
    if (!node || !node.online) {
      throw new ReplicationError("Requested node is unavailable.");
    }

    if (
      requiredPosition !== null &&
      node.appliedPosition < requiredPosition
    ) {
      throw new ReplicationError(
        `Replica lag: ${node.appliedPosition}; ` +
          `required ${requiredPosition}.`
      );
    }

    return node.data.get(key);
  }

  failPrimary() {
    this.primaryOnline = false;
    this.emit("failure", { node: this.primaryName });
  }

  promote(nodeName) {
    const node = this.nodes.get(nodeName);

    if (!node || !node.online) {
      throw new ReplicationError("Only an online replica can be promoted.");
    }

    for (const candidate of this.nodes.values()) {
      candidate.role = NodeRole.REPLICA;
    }

    node.role = NodeRole.PRIMARY;
    this.primaryName = nodeName;
    this.data = new Map(node.data);
    this.primaryOnline = true;

    this.emit("promotion", {
      node: nodeName,
      position: node.appliedPosition,
    });
  }

  status() {
    return [...this.nodes.values()].map((node) => ({
      node: node.name,
      role: node.role,
      mode: node.mode,
      online: node.online,
      appliedPosition: node.appliedPosition,
      lag: this.position - node.appliedPosition,
    }));
  }
}

async function main() {
  const cluster = new ReplicationCluster();

  cluster.on("write", ({ transaction, acknowledged }) => {
    console.log(
      `write position=${transaction.position} acknowledged=${acknowledged}`
    );
  });

  cluster.on("failure", ({ node }) => {
    console.log(`failure detected on ${node}`);
  });

  cluster.on("promotion", ({ node, position }) => {
    console.log(`promoted ${node} at position ${position}`);
  });

  cluster.on("replication", ({ applied }) => {
    console.log(`async replication applied=${applied}`);
  });

  const first = cluster.write("account:10", "enabled");
  cluster.write("payment:90", "settled");

  console.log("Status before async catch-up:", cluster.status());

  try {
    cluster.read(
      "payment:90",
      "replica-async",
      first.position + 1
    );
  } catch (error) {
    console.log("Expected consistency failure:", error.message);
  }

  await cluster.processAsyncReplication(10);

  console.log(
    "Async read after catch-up:",
    cluster.read(
      "payment:90",
      "replica-async",
      cluster.position
    )
  );

  cluster.failPrimary();
  cluster.promote("replica-sync");

  cluster.write("account:10", "verified");

  console.log("Post-failover status:", cluster.status());

  // A bounded input prevents untrusted clients from creating
  // arbitrarily large transactions.
  try {
    cluster.write("", "invalid");
  } catch (error) {
    console.log("Expected validation failure:", error.message);
  }
}

main().catch((error) => {
  console.error("Fatal error:", error.message);
  process.exitCode = 1;
});
