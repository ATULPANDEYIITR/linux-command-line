"use strict";

/*
 * Highly Available Database Infrastructure
 *
 * Demonstrates:
 * - Primary/replica topology
 * - Event-driven health monitoring
 * - Replica routing
 * - Circuit breakers
 * - Cache invalidation
 * - Backup retention and verification
 * - Failover coordination
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const EventEmitter = require("node:events");

class InfrastructureError extends Error {
    constructor(message, code = "INFRASTRUCTURE_ERROR") {
        super(message);
        this.name = "InfrastructureError";
        this.code = code;
    }
}

const Role = Object.freeze({
    PRIMARY: "PRIMARY",
    REPLICA: "REPLICA"
});

const State = Object.freeze({
    HEALTHY: "HEALTHY",
    DEGRADED: "DEGRADED",
    FAILED: "FAILED",
    RECOVERING: "RECOVERING"
});

const BackupType = Object.freeze({
    FULL: "FULL",
    INCREMENTAL: "INCREMENTAL"
});

class Configuration {
    constructor(options = {}) {
        this.maxReplicationLag = options.maxReplicationLag ?? 5;
        this.maxConnections = options.maxConnections ?? 100;
        this.cacheTTL = options.cacheTTL ?? 30000;
        this.maxCPU = options.maxCPU ?? 85;
        this.maxMemory = options.maxMemory ?? 90;
        this.requiredReplicas = options.requiredReplicas ?? 1;
        this.backupRetentionDays = options.backupRetentionDays ?? 30;

        this.validate();
    }

    validate() {
        for (const [key, value] of Object.entries({
            maxReplicationLag: this.maxReplicationLag,
            maxConnections: this.maxConnections,
            cacheTTL: this.cacheTTL,
            maxCPU: this.maxCPU,
            maxMemory: this.maxMemory,
            backupRetentionDays: this.backupRetentionDays
        })) {
            if (!Number.isFinite(value) || value < 0) {
                throw new TypeError(`Invalid configuration: ${key}`);
            }
        }

        if (!Number.isInteger(this.requiredReplicas) ||
            this.requiredReplicas < 0) {
            throw new TypeError("Invalid requiredReplicas");
        }

        if (this.maxConnections === 0 || this.cacheTTL === 0) {
            throw new TypeError("Connection limit and cache TTL must be positive");
        }
    }
}

class DatabaseNode {
    constructor({
        id,
        region,
        zone,
        role,
        transactionPosition = 0,
        connectionLimit = 100
    }) {
        if (!id || !region || !zone) {
            throw new TypeError("Node identity, region and zone are required");
        }

        if (!Object.values(Role).includes(role)) {
            throw new TypeError("Invalid database role");
        }

        this.id = id;
        this.region = region;
        this.zone = zone;
        this.role = role;
        this.state = State.HEALTHY;
        this.transactionPosition = transactionPosition;
        this.replicationLag = 0;
        this.connectionLimit = connectionLimit;
        this.connections = 0;
        this.cpu = 20;
        this.memory = 40;
        this.lastHeartbeat = Date.now();
        this.errorCount = 0;
    }

    get available() {
        return this.state === State.HEALTHY &&
            this.connections < this.connectionLimit;
    }

    acquire() {
        if (!this.available) {
            throw new InfrastructureError(
                `Node ${this.id} cannot accept connections`,
                "NODE_UNAVAILABLE"
            );
        }
        this.connections++;
    }

    release() {
        this.connections = Math.max(0, this.connections - 1);
    }

    heartbeat() {
        if (this.state !== State.FAILED) {
            this.lastHeartbeat = Date.now();
        }
    }

    snapshot() {
        return Object.freeze({
            id: this.id,
            region: this.region,
            zone: this.zone,
            role: this.role,
            state: this.state,
            position: this.transactionPosition,
            lag: this.replicationLag,
            connections: this.connections,
            cpu: this.cpu,
            memory: this.memory
        });
    }
}

class CircuitBreaker {
    constructor(threshold = 3, resetTimeout = 10000) {
        this.threshold = threshold;
        this.resetTimeout = resetTimeout;
        this.failures = 0;
        this.openedAt = null;
    }

    get state() {
        if (this.openedAt === null) return "CLOSED";

        if (Date.now() - this.openedAt >= this.resetTimeout) {
            return "HALF_OPEN";
        }

        return "OPEN";
    }

    allowRequest() {
        if (this.state === "OPEN") {
            return false;
        }
        return true;
    }

    success() {
        this.failures = 0;
        this.openedAt = null;
    }

    failure() {
        this.failures++;

        if (this.failures >= this.threshold) {
            this.openedAt = Date.now();
        }
    }
}

class TTLCache {
    constructor(ttlMilliseconds) {
        this.ttl = ttlMilliseconds;
        this.entries = new Map();
        this.hits = 0;
        this.misses = 0;
    }

    get(key) {
        const entry = this.entries.get(key);

        if (!entry || entry.expiresAt <= Date.now()) {
            this.entries.delete(key);
            this.misses++;
            return undefined;
        }

        this.hits++;
        return entry.value;
    }

    set(key, value) {
        this.entries.set(key, {
            value: structuredClone(value),
            expiresAt: Date.now() + this.ttl
        });
    }

    invalidate(key) {
        this.entries.delete(key);
    }

    invalidatePrefix(prefix) {
        for (const key of this.entries.keys()) {
            if (key.startsWith(prefix)) {
                this.entries.delete(key);
            }
        }
    }

    clear() {
        this.entries.clear();
    }

    getStatistics() {
        const total = this.hits + this.misses;

        return {
            entries: this.entries.size,
            hits: this.hits,
            misses: this.misses,
            hitRatio: total ? this.hits / total : 0
        };
    }
}

class BackupService {
    constructor() {
        this.backups = new Map();
        this.sequence = 0;
    }

    async create(node, type = BackupType.FULL) {
        if (node.role !== Role.PRIMARY || !node.available) {
            throw new InfrastructureError(
                "A healthy primary is required for backup"
            );
        }

        if (!Object.values(BackupType).includes(type)) {
            throw new TypeError("Invalid backup type");
        }

        let parentId = null;

        if (type === BackupType.INCREMENTAL) {
            const full = [...this.backups.values()]
                .filter(b => b.type === BackupType.FULL && b.verified)
                .sort((a, b) => b.createdAt - a.createdAt)[0];

            if (!full) {
                throw new InfrastructureError(
                    "Incremental backup requires a verified full backup"
                );
            }

            parentId = full.id;
        }

        const createdAt = Date.now();
        const payload = [
            node.id,
            node.transactionPosition,
            createdAt,
            type
        ].join(":");

        const checksum = crypto
            .createHash("sha256")
            .update(payload)
            .digest("hex");

        const backup = Object.freeze({
            id: `backup-${++this.sequence}`,
            type,
            parentId,
            createdAt,
            transactionPosition: node.transactionPosition,
            checksum,
            verified: true,
            bytes: type === BackupType.FULL
                ? 100 * 1024 * 1024
                : 5 * 1024 * 1024
        });

        this.backups.set(backup.id, backup);
        return backup;
    }

    verify(backupId) {
        const backup = this.backups.get(backupId);

        if (!backup || !backup.verified) {
            return false;
        }

        if (backup.type === BackupType.INCREMENTAL) {
            const parent = this.backups.get(backup.parentId);
            return Boolean(parent && parent.verified);
        }

        return true;
    }

    async restore(backupId, node) {
        if (!this.verify(backupId)) {
            throw new InfrastructureError(
                "Backup or dependency chain failed verification"
            );
        }

        const backup = this.backups.get(backupId);

        node.state = State.RECOVERING;
        node.transactionPosition = backup.transactionPosition;
        node.replicationLag = 0;
        node.state = State.HEALTHY;

        return node.snapshot();
    }

    prune(retentionDays) {
        const cutoff = Date.now() -
            retentionDays * 24 * 60 * 60 * 1000;

        const protectedIds = new Set();

        // Preserve full backups referenced by retained incremental backups.
        for (const backup of this.backups.values()) {
            if (backup.createdAt >= cutoff && backup.parentId) {
                protectedIds.add(backup.parentId);
            }
        }

        let deleted = 0;

        for (const [id, backup] of this.backups) {
            if (backup.createdAt < cutoff && !protectedIds.has(id)) {
                this.backups.delete(id);
                deleted++;
            }
        }

        return deleted;
    }
}

class DatabaseCluster extends EventEmitter {
    constructor(nodes, config) {
        super();

        if (!Array.isArray(nodes) || nodes.length === 0) {
            throw new TypeError("At least one node is required");
        }

        if (nodes.filter(n => n.role === Role.PRIMARY).length !== 1) {
            throw new TypeError("Exactly one primary is required");
        }

        this.nodes = new Map(nodes.map(node => [node.id, node]));
        this.config = config;
        this.failoverInProgress = false;
        this.failoverHistory = [];
        this.breakers = new Map(
            nodes.map(node => [node.id, new CircuitBreaker()])
        );
    }

    get primary() {
        return [...this.nodes.values()]
            .find(node => node.role === Role.PRIMARY);
    }

    get replicas() {
        return [...this.nodes.values()]
            .filter(node => node.role === Role.REPLICA);
    }

    healthyReplicas() {
        return this.replicas.filter(node =>
            node.available &&
            node.replicationLag <= this.config.maxReplicationLag
        );
    }

    getNode(id) {
        const node = this.nodes.get(id);

        if (!node) {
            throw new InfrastructureError(`Unknown node: ${id}`);
        }

        return node;
    }

    async write(transactionCount = 1) {
        if (!Number.isInteger(transactionCount) ||
            transactionCount <= 0) {
            throw new RangeError("Transaction count must be positive");
        }

        const primary = this.primary;
        const breaker = this.breakers.get(primary.id);

        if (!primary.available || !breaker.allowRequest()) {
            throw new InfrastructureError(
                "Primary is unavailable or circuit is open"
            );
        }

        primary.acquire();

        try {
            primary.transactionPosition += transactionCount;

            for (const replica of this.replicas) {
                if (replica.state === State.HEALTHY) {
                    replica.replicationLag += transactionCount;
                }
            }

            breaker.success();

            this.emit("transaction:committed", {
                node: primary.id,
                position: primary.transactionPosition
            });

            return primary.transactionPosition;
        } catch (error) {
            breaker.failure();
            throw error;
        } finally {
            primary.release();
        }
    }

    async replicate(replicaId, transactionCount) {
        if (!Number.isInteger(transactionCount) ||
            transactionCount < 0) {
            throw new RangeError("Invalid replication amount");
        }

        const replica = this.getNode(replicaId);

        if (replica.role !== Role.REPLICA ||
            replica.state !== State.HEALTHY) {
            throw new InfrastructureError("Replica cannot replicate");
        }

        replica.replicationLag = Math.max(
            0,
            replica.replicationLag - transactionCount
        );

        replica.transactionPosition = Math.max(
            0,
            this.primary.transactionPosition - replica.replicationLag
        );

        this.emit("replication:updated", replica.snapshot());
    }

    selectReadNode() {
        const candidates = this.healthyReplicas();

        if (candidates.length > 0) {
            // Prefer low lag, then low load, then local-region preference.
            return candidates.sort((a, b) =>
                a.replicationLag - b.replicationLag ||
                a.connections - b.connections ||
                a.cpu - b.cpu
            )[0];
        }

        if (this.primary.available) {
            return this.primary;
        }

        throw new InfrastructureError("No readable database node");
    }

    async read(key, cache) {
        if (typeof key !== "string" || key.trim().length === 0) {
            throw new TypeError("Read key cannot be empty");
        }

        const cached = cache.get(key);

        if (cached !== undefined) {
            return cached;
        }

        const node = this.selectReadNode();
        const breaker = this.breakers.get(node.id);

        if (!breaker.allowRequest()) {
            throw new InfrastructureError("Read circuit is open");
        }

        node.acquire();

        try {
            const result = {
                key,
                servedBy: node.id,
                position: node.transactionPosition,
                lag: node.replicationLag
            };

            cache.set(key, result);
            breaker.success();

            this.emit("read:completed", result);
            return result;
        } catch (error) {
            breaker.failure();
            throw error;
        } finally {
            node.release();
        }
    }

    async failover() {
        if (this.failoverInProgress) {
            throw new InfrastructureError("Failover already in progress");
        }

        this.failoverInProgress = true;

        try {
            const oldPrimary = this.primary;
            oldPrimary.state = State.FAILED;

            const candidates = this.healthyReplicas();

            if (candidates.length === 0) {
                throw new InfrastructureError(
                    "No healthy replica available for promotion"
                );
            }

            const promoted = candidates.sort((a, b) =>
                b.transactionPosition - a.transactionPosition
            )[0];

            promoted.role = Role.PRIMARY;
            promoted.replicationLag = 0;

            const event = Object.freeze({
                oldPrimary: oldPrimary.id,
                newPrimary: promoted.id,
                promotedPosition: promoted.transactionPosition,
                timestamp: new Date().toISOString()
            });

            this.failoverHistory.push(event);
            this.emit("failover:completed", event);

            return event;
        } finally {
            this.failoverInProgress = false;
        }
    }

    rejoin(nodeId) {
        const node = this.getNode(nodeId);

        if (node.role === Role.PRIMARY && node.available) {
            throw new InfrastructureError(
                "Cannot rejoin an active primary"
            );
        }

        node.role = Role.REPLICA;
        node.state = State.RECOVERING;
        node.transactionPosition = this.primary.transactionPosition;
        node.replicationLag = 0;
        node.state = State.HEALTHY;
        node.heartbeat();

        this.emit("node:rejoined", node.snapshot());
    }

    availability() {
        const replicas = this.healthyReplicas();

        return {
            writeAvailable: this.primary.available,
            readAvailable: this.primary.available || replicas.length > 0,
            healthyReplicas: replicas.length,
            replicaRequirementSatisfied:
                replicas.length >= this.config.requiredReplicas
        };
    }
}

class MonitoringService extends EventEmitter {
    constructor(cluster, config) {
        super();

        this.cluster = cluster;
        this.config = config;
        this.history = [];
        this.alerts = [];
    }

    collect() {
        const timestamp = new Date().toISOString();

        for (const node of this.cluster.nodes.values()) {
            const metrics = {
                cpu: node.cpu,
                memory: node.memory,
                replicationLag: node.replicationLag,
                connections: node.connections
            };

            const record = {
                timestamp,
                nodeId: node.id,
                state: node.state,
                metrics
            };

            this.history.push(record);

            if (node.state === State.FAILED) {
                this.alert("NODE_FAILURE", node.id, timestamp);
            }

            if (node.cpu >= this.config.maxCPU) {
                this.alert("HIGH_CPU", node.id, timestamp);
            }

            if (node.memory >= this.config.maxMemory) {
                this.alert("HIGH_MEMORY", node.id, timestamp);
            }

            if (node.replicationLag >
                this.config.maxReplicationLag) {
                this.alert("REPLICATION_LAG", node.id, timestamp);
            }
        }
    }

    alert(type, nodeId, timestamp) {
        const alert = { type, nodeId, timestamp };

        this.alerts.push(alert);
        this.emit("alert", alert);
    }

    report() {
        return {
            availability: this.cluster.availability(),
            nodes: [...this.cluster.nodes.values()]
                .map(node => node.snapshot()),
            metricsCollected: this.history.length,
            alerts: this.alerts,
            failovers: this.cluster.failoverHistory
        };
    }
}

class InfrastructureApplication {
    constructor() {
        this.config = new Configuration({
            maxReplicationLag: 5,
            requiredReplicas: 1,
            cacheTTL: 30000
        });

        const nodes = [
            new DatabaseNode({
                id: "primary-east",
                region: "ap-south-1",
                zone: "zone-a",
                role: Role.PRIMARY
            }),
            new DatabaseNode({
                id: "replica-east",
                region: "ap-south-1",
                zone: "zone-b",
                role: Role.REPLICA
            }),
            new DatabaseNode({
                id: "replica-west",
                region: "ap-south-2",
                zone: "zone-c",
                role: Role.REPLICA
            })
        ];

        this.cluster = new DatabaseCluster(nodes, this.config);
        this.cache = new TTLCache(this.config.cacheTTL);
        this.backups = new BackupService();
        this.monitor = new MonitoringService(
            this.cluster,
            this.config
        );

        this.cluster.on("failover:completed", event => {
            this.cache.clear();
            console.log("Failover completed:", event);
        });

        this.cluster.on("transaction:committed", event => {
            console.log("Transaction committed:", event);
        });

        this.monitor.on("alert", alert => {
            console.error("MONITORING ALERT:", alert);
        });
    }

    async run() {
        console.log("\n1. Initial availability");
        console.log(this.cluster.availability());

        console.log("\n2. Database writes");
        await this.cluster.write(20);
        await this.cluster.write(10);

        console.log("\n3. Replica synchronization");
        await this.cluster.replicate("replica-east", 25);
        await this.cluster.replicate("replica-west", 20);

        console.log("\n4. Read routing and cache");
        console.log(await this.cluster.read("account:1001", this.cache));
        console.log(await this.cluster.read("account:1001", this.cache));
        console.log(this.cache.getStatistics());

        console.log("\n5. Backup creation");
        const full = await this.backups.create(
            this.cluster.primary,
            BackupType.FULL
        );

        const incremental = await this.backups.create(
            this.cluster.primary,
            BackupType.INCREMENTAL
        );

        console.log({ full, incremental });

        console.log("\n6. Monitoring");
        this.cluster.primary.cpu = 91;
        this.monitor.collect();

        console.log("\n7. Primary failure and promotion");
        this.cluster.primary.state = State.FAILED;
        const failover = await this.cluster.failover();
        console.log(failover);

        console.log("\n8. Rejoin old primary");
        this.cluster.rejoin("primary-east");

        console.log("\n9. Backup restoration test");
        const restoreNode = new DatabaseNode({
            id: "restore-node",
            region: "ap-south-1",
            zone: "zone-d",
            role: Role.REPLICA
        });

        console.log(
            await this.backups.restore(full.id, restoreNode)
        );

        console.log("\n10. Final infrastructure report");
        this.monitor.collect();

        const report = {
            generatedAt: new Date().toISOString(),
            monitoring: this.monitor.report(),
            cache: this.cache.getStatistics(),
            backupCount: this.backups.backups.size
        };

        console.log(JSON.stringify(report, null, 2));

        await fs.writeFile(
            "database-infrastructure-report.json",
            JSON.stringify(report, null, 2),
            { encoding: "utf8", mode: 0o600 }
        );
    }
}

async function runTests() {
    const app = new InfrastructureApplication();
    const cluster = app.cluster;

    const initialPosition = await cluster.write(10);
    console.assert(initialPosition === 10);

    await cluster.replicate("replica-east", 10);

    const first = await cluster.read("test-key", app.cache);
    const second = await cluster.read("test-key", app.cache);

    console.assert(first.key === second.key);
    console.assert(app.cache.getStatistics().hits === 1);

    const full = await app.backups.create(cluster.primary);
    console.assert(app.backups.verify(full.id));

    cluster.primary.state = State.FAILED;
    const event = await cluster.failover();

    console.assert(event.newPrimary === "replica-east");

    cluster.rejoin("primary-east");
    console.assert(cluster.getNode("primary-east").role === Role.REPLICA);

    console.log("All JavaScript infrastructure tests passed.");
}

async function main() {
    try {
        if (process.argv.includes("--test")) {
            await runTests();
        } else {
            await new InfrastructureApplication().run();
        }
    } catch (error) {
        console.error("Infrastructure execution failed:", error.message);
        process.exitCode = 1;
    }
}

if (require.main === module) {
    main();
}

module.exports = {
    Configuration,
    DatabaseNode,
    DatabaseCluster,
    TTLCache,
    BackupService,
    MonitoringService,
    InfrastructureApplication,
    Role,
    State,
    BackupType
};
