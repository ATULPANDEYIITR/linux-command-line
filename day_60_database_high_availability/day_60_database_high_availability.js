"use strict";

/*
 * Event-driven database high-availability control-plane model.
 *
 * Features:
 * - Three-voter, multi-zone topology
 * - Majority write acknowledgements
 * - Synchronous and asynchronous replication behavior
 * - Concurrent operation serialization
 * - Asynchronous health probing
 * - Failover eligibility and safe promotion
 * - Primary fencing and replica rejoining
 * - Structured event reporting
 *
 * Run with Node.js 18 or later. No third-party packages are required.
 */

const { EventEmitter } = require("node:events");

class HAError extends Error {
    constructor(message) {
        super(message);
        this.name = "HAError";
    }
}

class QuorumError extends HAError {
    constructor(message) {
        super(message);
        this.name = "QuorumError";
    }
}

class UnsafePromotionError extends HAError {
    constructor(message) {
        super(message);
        this.name = "UnsafePromotionError";
    }
}

const Role = Object.freeze({
    PRIMARY: "primary",
    REPLICA: "replica"
});

const State = Object.freeze({
    HEALTHY: "healthy",
    SUSPECT: "suspect",
    DOWN: "down",
    FENCED: "fenced"
});

class Node {
    constructor({
        id,
        zone,
        role,
        priority,
        voter = true,
        reachable = true,
        state = State.HEALTHY,
        appliedIndex = 0,
        lagMs = 0
    }) {
        if (typeof id !== "string" || !id.trim()) {
            throw new TypeError("Node identifier is required.");
        }
        if (typeof zone !== "string" || !zone.trim()) {
            throw new TypeError("Availability zone is required.");
        }
        if (!Object.values(Role).includes(role)) {
            throw new TypeError("Invalid node role.");
        }
        if (!Number.isInteger(priority) || priority < 0) {
            throw new RangeError("Priority must be a non-negative integer.");
        }
        if (!Number.isSafeInteger(appliedIndex) || appliedIndex < 0) {
            throw new RangeError("Applied index must be a non-negative safe integer.");
        }
        if (!Number.isFinite(lagMs) || lagMs < 0) {
            throw new RangeError("Replication lag must be non-negative.");
        }
        if (state === State.DOWN && reachable) {
            throw new TypeError("A down node cannot be reachable.");
        }

        this.id = id;
        this.zone = zone;
        this.role = role;
        this.priority = priority;
        this.voter = Boolean(voter);
        this.reachable = Boolean(reachable);
        this.state = state;
        this.fenced = state === State.FENCED;
        this.appliedIndex = appliedIndex;
        this.lagMs = lagMs;
    }

    get isLiveVoter() {
        return (
            this.voter &&
            this.reachable &&
            this.state === State.HEALTHY &&
            !this.fenced
        );
    }
}

class AsyncLock {
    constructor() {
        this.tail = Promise.resolve();
    }

    async run(operation) {
        let release;
        const previous = this.tail;

        this.tail = new Promise((resolve) => {
            release = resolve;
        });

        await previous;
        try {
            return await operation();
        } finally {
            release();
        }
    }
}

class HACluster extends EventEmitter {
    constructor(clusterId, nodes, policy = {}) {
        super();

        const options = {
            expectedVoters: 3,
            synchronousReplicaAcks: 1,
            maximumLagMs: 500,
            minimumLiveZones: 2,
            ...policy
        };

        if (!clusterId || typeof clusterId !== "string") {
            throw new TypeError("Cluster identifier is required.");
        }
        if (!Number.isInteger(options.expectedVoters) ||
            options.expectedVoters < 3 ||
            options.expectedVoters % 2 === 0) {
            throw new RangeError("Expected voters must be an odd number of at least three.");
        }
        if (!Number.isInteger(options.synchronousReplicaAcks) ||
            options.synchronousReplicaAcks < 1 ||
            options.synchronousReplicaAcks >= options.expectedVoters) {
            throw new RangeError("Invalid synchronous acknowledgement count.");
        }
        if (!Number.isFinite(options.maximumLagMs) || options.maximumLagMs < 0) {
            throw new RangeError("Maximum lag must be non-negative.");
        }
        if (!Number.isInteger(options.minimumLiveZones) ||
            options.minimumLiveZones < 1 ||
            options.minimumLiveZones > options.expectedVoters) {
            throw new RangeError("Invalid minimum live-zone requirement.");
        }

        if (!Array.isArray(nodes) || nodes.length !== options.expectedVoters) {
            throw new TypeError("Node count must match the configured voter count.");
        }

        this.nodes = new Map();
        for (const node of nodes) {
            if (!(node instanceof Node) || this.nodes.has(node.id)) {
                throw new TypeError("Nodes must be unique Node instances.");
            }
            this.nodes.set(node.id, node);
        }

        const primaries = nodes.filter((node) => node.role === Role.PRIMARY);
        if (primaries.length !== 1 || nodes.some((node) => !node.voter)) {
            throw new HAError("Cluster requires exactly one primary and all configured voters.");
        }

        this.clusterId = clusterId;
        this.policy = Object.freeze(options);
        this.primaryId = primaries[0].id;
        this.commitIndex = 0;
        this.term = 1;
        this.lock = new AsyncLock();
        this.audit = [];

        this.record("cluster_initialized", { primary: this.primaryId });
    }

    get quorum() {
        return Math.floor(this.policy.expectedVoters / 2) + 1;
    }

    record(event, details = {}) {
        const entry = Object.freeze({
            event,
            clusterId: this.clusterId,
            term: this.term,
            commitIndex: this.commitIndex,
            timestamp: new Date().toISOString(),
            ...details
        });

        this.audit.push(entry);
        this.emit("clusterEvent", entry);
    }

    getPrimary() {
        const primary = this.nodes.get(this.primaryId);
        if (!primary) {
            throw new HAError("Configured primary does not exist.");
        }
        return primary;
    }

    liveVoters() {
        return [...this.nodes.values()].filter((node) => node.isLiveVoter);
    }

    async commitWrite(payload) {
        if (typeof payload !== "string" || !payload.trim()) {
            throw new TypeError("Write payload must be a non-empty string.");
        }
        if (Buffer.byteLength(payload, "utf8") > 4096) {
            throw new RangeError("Write payload exceeds 4096 bytes.");
        }

        return this.lock.run(async () => {
            const primary = this.getPrimary();
            if (primary.role !== Role.PRIMARY || !primary.isLiveVoter) {
                throw new HAError("Current primary is not operational.");
            }

            const live = this.liveVoters();
            if (live.length < this.quorum) {
                throw new QuorumError("Write rejected because majority quorum is unavailable.");
            }

            const requiredAcks = Math.max(
                this.policy.synchronousReplicaAcks,
                this.quorum - 1
            );

            const replicas = live
                .filter((node) => node.id !== this.primaryId && node.role === Role.REPLICA)
                .sort((a, b) => a.priority - b.priority || a.id.localeCompare(b.id));

            if (replicas.length < requiredAcks) {
                throw new QuorumError("Insufficient healthy replicas for synchronous acknowledgements.");
            }

            this.commitIndex += 1;
            primary.appliedIndex = this.commitIndex;
            primary.lagMs = 0;

            const acknowledged = replicas.slice(0, requiredAcks);
            for (const replica of acknowledged) {
                replica.appliedIndex = this.commitIndex;
                replica.lagMs = 0;
            }

            for (const replica of replicas.slice(requiredAcks)) {
                replica.lagMs += 100;
            }

            this.record("write_committed", {
                acknowledgedNodes: acknowledged.map((node) => node.id)
            });

            return this.commitIndex;
        });
    }

    async replicate(replicaId) {
        return this.lock.run(async () => {
            const replica = this.nodes.get(replicaId);
            if (!replica || replica.role !== Role.REPLICA || !replica.isLiveVoter) {
                throw new HAError("Replication target must be a healthy replica.");
            }

            replica.appliedIndex = this.commitIndex;
            replica.lagMs = 0;
            this.record("replica_caught_up", { nodeId: replicaId });
        });
    }

    async refreshHealth(probe) {
        if (typeof probe !== "function") {
            throw new TypeError("Health probe must be a function.");
        }

        // Probes run concurrently; state changes are applied under the cluster lock.
        const results = await Promise.allSettled(
            [...this.nodes.values()].map(async (node) => ({
                nodeId: node.id,
                healthy: Boolean(await probe(node))
            }))
        );

        return this.lock.run(async () => {
            const outcomes = [];

            for (let index = 0; index < results.length; index += 1) {
                const result = results[index];
                const nodeId = [...this.nodes.keys()][index];
                const node = this.nodes.get(nodeId);

                if (result.status === "rejected" || !result.value.healthy) {
                    if (!node.fenced) {
                        node.state = State.DOWN;
                        node.reachable = false;
                    }
                    outcomes.push({ nodeId, healthy: false });
                } else {
                    if (!node.fenced && node.state !== State.FENCED) {
                        node.state = State.HEALTHY;
                        node.reachable = true;
                    }
                    outcomes.push({ nodeId, healthy: true });
                }
            }

            this.record("health_check_completed", { outcomes });
            return outcomes;
        });
    }

    evaluateFailover() {
        const live = this.liveVoters();
        const zones = new Set(live.map((node) => node.zone));
        const primary = this.getPrimary();

        const result = {
            eligible: false,
            candidateId: null,
            liveVoters: live.length,
            liveZones: zones.size,
            reason: ""
        };

        if (primary.isLiveVoter) {
            result.reason = "Current primary is healthy.";
            return result;
        }

        if (live.length < this.quorum) {
            result.reason = "Majority quorum is unavailable.";
            return result;
        }

        if (zones.size < this.policy.minimumLiveZones) {
            result.reason = "Insufficient live availability zones.";
            return result;
        }

        const candidates = live
            .filter((node) =>
                node.role === Role.REPLICA &&
                node.appliedIndex >= this.commitIndex &&
                node.lagMs <= this.policy.maximumLagMs
            )
            .sort((a, b) =>
                b.appliedIndex - a.appliedIndex ||
                a.priority - b.priority ||
                a.id.localeCompare(b.id)
            );

        if (candidates.length === 0) {
            result.reason = "No replica contains all committed writes within the lag policy.";
            return result;
        }

        result.eligible = true;
        result.candidateId = candidates[0].id;
        result.reason = "Quorum and replication safety conditions are satisfied.";
        return result;
    }

    async failover() {
        return this.lock.run(async () => {
            const decision = this.evaluateFailover();
            if (!decision.eligible || !decision.candidateId) {
                throw new UnsafePromotionError(decision.reason);
            }

            const oldPrimary = this.getPrimary();
            const candidate = this.nodes.get(decision.candidateId);

            // Fence first so a recovering former primary cannot accept writes.
            oldPrimary.role = Role.REPLICA;
            oldPrimary.state = State.FENCED;
            oldPrimary.fenced = true;
            oldPrimary.reachable = false;

            candidate.role = Role.PRIMARY;
            candidate.state = State.HEALTHY;
            candidate.fenced = false;
            candidate.reachable = true;

            this.primaryId = candidate.id;
            this.term += 1;

            this.record("automatic_failover", {
                oldPrimary: oldPrimary.id,
                newPrimary: candidate.id
            });

            this.emit("primaryChanged", {
                oldPrimary: oldPrimary.id,
                newPrimary: candidate.id,
                term: this.term
            });

            return candidate.id;
        });
    }

    async rejoinAsReplica(nodeId) {
        return this.lock.run(async () => {
            const node = this.nodes.get(nodeId);
            if (!node || nodeId === this.primaryId) {
                throw new HAError("Recovery target must be a non-primary cluster node.");
            }

            node.role = Role.REPLICA;
            node.state = State.HEALTHY;
            node.fenced = false;
            node.reachable = true;
            node.appliedIndex = this.commitIndex;
            node.lagMs = 0;

            this.record("node_rejoined_as_replica", { nodeId });
        });
    }

    status() {
        return {
            clusterId: this.clusterId,
            primary: this.primaryId,
            term: this.term,
            commitIndex: this.commitIndex,
            quorumRequired: this.quorum,
            liveVoters: this.liveVoters().length,
            nodes: [...this.nodes.values()].map((node) => ({
                id: node.id,
                zone: node.zone,
                role: node.role,
                state: node.state,
                reachable: node.reachable,
                fenced: node.fenced,
                appliedIndex: node.appliedIndex,
                lagMs: node.lagMs
            }))
        };
    }
}

function createCluster(clusterId = "orders-production") {
    return new HACluster(
        clusterId,
        [
            new Node({ id: "db-a", zone: "zone-a", role: Role.PRIMARY, priority: 0 }),
            new Node({ id: "db-b", zone: "zone-b", role: Role.REPLICA, priority: 1 }),
            new Node({ id: "db-c", zone: "zone-c", role: Role.REPLICA, priority: 2 })
        ]
    );
}

async function main() {
    const cluster = createCluster();

    cluster.on("clusterEvent", (event) => {
        console.log("EVENT", event.event, event);
    });

    cluster.on("primaryChanged", (change) => {
        console.log("PRIMARY_CHANGED", change);
    });

    await cluster.commitWrite("order-2001");
    await cluster.commitWrite("order-2002");

    console.log("\nInitial cluster state:");
    console.dir(cluster.status(), { depth: null });

    await cluster.refreshHealth(async (node) => {
        // Simulate loss of the primary while both replicas remain reachable.
        await new Promise((resolve) => setTimeout(resolve, 5));
        return node.id !== "db-a";
    });

    const decision = cluster.evaluateFailover();
    console.log("\nFailover decision:", decision);

    const newPrimary = await cluster.failover();
    if (newPrimary !== "db-b") {
        throw new Error("Unexpected failover candidate.");
    }

    await cluster.rejoinAsReplica("db-a");

    console.log("\nRecovered cluster state:");
    console.dir(cluster.status(), { depth: null });

    // A separate cluster demonstrates safe rejection without quorum.
    const isolated = createCluster("isolated-cluster");
    await isolated.refreshHealth(async (node) => node.id === "db-b");

    try {
        await isolated.failover();
        throw new Error("Failover should have been rejected.");
    } catch (error) {
        if (!(error instanceof UnsafePromotionError)) {
            throw error;
        }
        console.log("\nExpected failover rejection:", error.message);
    }
}

main().catch((error) => {
    console.error("Cluster execution failed:", error.name, error.message);
    process.exitCode = 1;
});
