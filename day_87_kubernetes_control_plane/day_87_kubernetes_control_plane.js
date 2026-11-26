"use strict";

/**
 * Kubernetes Control Plane
 *
 * Event-driven control plane simulator.
 *
 * Components:
 * - API server request processing
 * - Resource validation
 * - Versioned etcd-style storage
 * - Scheduler filtering and scoring
 * - Controller reconciliation
 * - Component health monitoring
 * - Lease-based leader election
 * - Event-driven operational reporting
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");

// ============================================================
// 1. ENUMERATIONS AND ERRORS
// ============================================================

const PodPhase = Object.freeze({
    PENDING: "Pending",
    RUNNING: "Running",
    FAILED: "Failed",
    SUCCEEDED: "Succeeded"
});

const NodeCondition = Object.freeze({
    READY: "Ready",
    NOT_READY: "NotReady",
    UNKNOWN: "Unknown"
});

const ComponentStatus = Object.freeze({
    HEALTHY: "Healthy",
    DEGRADED: "Degraded",
    UNAVAILABLE: "Unavailable"
});

class ControlPlaneError extends Error {}
class ValidationError extends ControlPlaneError {}
class NotFoundError extends ControlPlaneError {}
class ConflictError extends ControlPlaneError {}
class SchedulingError extends ControlPlaneError {}

// ============================================================
// 2. DOMAIN OBJECTS
// ============================================================

class ResourceMetadata {
    constructor(name, namespace = "default", labels = {}) {
        if (typeof name !== "string" || !name.trim()) {
            throw new ValidationError("Resource name is required");
        }

        if (typeof namespace !== "string" || !namespace.trim()) {
            throw new ValidationError("Namespace is required");
        }

        this.name = name;
        this.namespace = namespace;
        this.uid = crypto.randomUUID();
        this.resourceVersion = 0;
        this.labels = new Map(Object.entries(labels));
        this.annotations = new Map();
    }

    validate() {
        if (this.name.length > 253 || this.namespace.length > 63) {
            throw new ValidationError("Metadata exceeds allowed length");
        }

        for (const [key, value] of this.labels) {
            if (!key || typeof value !== "string") {
                throw new ValidationError("Invalid label");
            }
        }
    }

    toJSON() {
        return {
            name: this.name,
            namespace: this.namespace,
            uid: this.uid,
            resourceVersion: this.resourceVersion,
            labels: Object.fromEntries(this.labels),
            annotations: Object.fromEntries(this.annotations)
        };
    }
}

class ContainerSpec {
    constructor(name, image, cpu = 1, memory = 128) {
        this.name = name;
        this.image = image;
        this.cpu = cpu;
        this.memory = memory;
        this.validate();
    }

    validate() {
        if (!this.name || !this.image) {
            throw new ValidationError("Container name and image required");
        }

        if (!Number.isSafeInteger(this.cpu) || this.cpu <= 0) {
            throw new ValidationError("CPU request must be positive");
        }

        if (!Number.isSafeInteger(this.memory) || this.memory <= 0) {
            throw new ValidationError("Memory request must be positive");
        }
    }
}

class Pod {
    constructor(metadata, containers) {
        this.metadata = metadata;
        this.containers = containers;
        this.phase = PodPhase.PENDING;
        this.nodeName = null;
        this.restartCount = 0;
        this.validate();
    }

    validate() {
        this.metadata.validate();

        if (!Array.isArray(this.containers) || this.containers.length === 0) {
            throw new ValidationError("Pod requires containers");
        }

        const names = new Set();

        for (const container of this.containers) {
            container.validate();

            if (names.has(container.name)) {
                throw new ValidationError("Duplicate container name");
            }

            names.add(container.name);
        }
    }

    get cpuRequest() {
        return this.containers.reduce((sum, c) => sum + c.cpu, 0);
    }

    get memoryRequest() {
        return this.containers.reduce((sum, c) => sum + c.memory, 0);
    }

    toJSON() {
        return {
            metadata: this.metadata.toJSON(),
            containers: this.containers.map(c => ({
                name: c.name,
                image: c.image,
                cpu: c.cpu,
                memory: c.memory
            })),
            phase: this.phase,
            nodeName: this.nodeName,
            restartCount: this.restartCount
        };
    }

    static fromJSON(data) {
        const metadata = new ResourceMetadata(
            data.metadata.name,
            data.metadata.namespace,
            data.metadata.labels
        );

        metadata.uid = data.metadata.uid;
        metadata.resourceVersion = data.metadata.resourceVersion;
        metadata.annotations = new Map(
            Object.entries(data.metadata.annotations || {})
        );

        const pod = new Pod(
            metadata,
            data.containers.map(c =>
                new ContainerSpec(c.name, c.image, c.cpu, c.memory)
            )
        );

        pod.phase = data.phase;
        pod.nodeName = data.nodeName;
        pod.restartCount = data.restartCount;

        return pod;
    }
}

class Node {
    constructor(name, cpuCapacity, memoryCapacity) {
        if (!name || !Number.isSafeInteger(cpuCapacity) ||
            !Number.isSafeInteger(memoryCapacity) ||
            cpuCapacity <= 0 || memoryCapacity <= 0) {
            throw new ValidationError("Invalid node configuration");
        }

        this.name = name;
        this.cpuCapacity = cpuCapacity;
        this.memoryCapacity = memoryCapacity;
        this.cpuAllocated = 0;
        this.memoryAllocated = 0;
        this.condition = NodeCondition.READY;
        this.labels = new Map();
    }

    get availableCPU() {
        return this.cpuCapacity - this.cpuAllocated;
    }

    get availableMemory() {
        return this.memoryCapacity - this.memoryAllocated;
    }

    canHost(pod) {
        return this.condition === NodeCondition.READY &&
            this.availableCPU >= pod.cpuRequest &&
            this.availableMemory >= pod.memoryRequest;
    }

    allocate(pod) {
        if (!this.canHost(pod)) {
            throw new SchedulingError(`Node ${this.name} is infeasible`);
        }

        this.cpuAllocated += pod.cpuRequest;
        this.memoryAllocated += pod.memoryRequest;
    }

    release(pod) {
        this.cpuAllocated -= pod.cpuRequest;
        this.memoryAllocated -= pod.memoryRequest;

        if (this.cpuAllocated < 0 || this.memoryAllocated < 0) {
            throw new ConflictError("Resource accounting underflow");
        }
    }
}

// ============================================================
// 3. VERSIONED ETCD-STYLE STORAGE
// ============================================================

class EtcdStore {
    #records = new Map();
    #revision = 0;

    constructor(events) {
        this.events = events;
    }

    get revision() {
        return this.#revision;
    }

    put(key, value, expectedRevision = null) {
        if (typeof key !== "string" || !key.startsWith("/")) {
            throw new ValidationError("Invalid storage key");
        }

        const existing = this.#records.get(key);
        const actualRevision = existing?.revision ?? 0;

        if (expectedRevision !== null &&
            expectedRevision !== actualRevision) {
            throw new ConflictError(
                `Revision conflict for ${key}: expected ` +
                `${expectedRevision}, received ${actualRevision}`
            );
        }

        const revision = ++this.#revision;

        this.#records.set(key, {
            value: structuredClone(value),
            revision
        });

        this.events.emit("storage:changed", {
            key,
            revision
        });

        return revision;
    }

    get(key) {
        const record = this.#records.get(key);

        if (!record) {
            throw new NotFoundError(`Resource not found: ${key}`);
        }

        return structuredClone(record.value);
    }

    getWithRevision(key) {
        const record = this.#records.get(key);

        if (!record) {
            throw new NotFoundError(`Resource not found: ${key}`);
        }

        return {
            value: structuredClone(record.value),
            revision: record.revision
        };
    }

    delete(key) {
        if (!this.#records.has(key)) {
            throw new NotFoundError(`Resource not found: ${key}`);
        }

        this.#records.delete(key);
        this.#revision++;

        this.events.emit("storage:deleted", {
            key,
            revision: this.#revision
        });
    }

    list(prefix) {
        return Array.from(this.#records.entries())
            .filter(([key]) => key.startsWith(prefix))
            .map(([, record]) => structuredClone(record.value));
    }
}

// ============================================================
// 4. API SERVER AND AUDIT EVENTS
// ============================================================

class APIServer {
    constructor(store, events) {
        this.store = store;
        this.events = events;
        this.auditLog = [];
    }

    podKey(namespace, name) {
        return `/registry/pods/${namespace}/${name}`;
    }

    async createPod(pod, actor = "system") {
        return this.execute("CREATE", pod.metadata.name, actor, async () => {
            pod.validate();

            const key = this.podKey(
                pod.metadata.namespace,
                pod.metadata.name
            );

            const existing = this.store.list(key);

            if (existing.length > 0) {
                throw new ConflictError("Pod already exists");
            }

            pod.metadata.resourceVersion = this.store.put(
                key,
                pod.toJSON()
            );

            this.events.emit("pod:created", {
                name: pod.metadata.name,
                namespace: pod.metadata.namespace
            });

            return pod;
        });
    }

    async updatePod(pod, actor = "system") {
        return this.execute("UPDATE", pod.metadata.name, actor, async () => {
            pod.validate();

            const key = this.podKey(
                pod.metadata.namespace,
                pod.metadata.name
            );

            const current = this.store.getWithRevision(key);

            pod.metadata.resourceVersion = this.store.put(
                key,
                pod.toJSON(),
                current.revision
            );

            this.events.emit("pod:updated", {
                name: pod.metadata.name,
                phase: pod.phase
            });

            return pod;
        });
    }

    getPod(namespace, name) {
        return Pod.fromJSON(
            this.store.get(this.podKey(namespace, name))
        );
    }

    async execute(operation, resource, actor, callback) {
        try {
            const result = await callback();

            this.auditLog.push({
                timestamp: new Date().toISOString(),
                operation,
                resource,
                actor,
                result: "SUCCESS"
            });

            return result;
        } catch (error) {
            this.auditLog.push({
                timestamp: new Date().toISOString(),
                operation,
                resource,
                actor,
                result: "FAILED",
                error: error.message
            });

            throw error;
        }
    }
}

// ============================================================
// 5. SCHEDULER
// ============================================================

class Scheduler {
    constructor(apiServer, nodes, events) {
        this.apiServer = apiServer;
        this.nodes = nodes;
        this.events = events;
    }

    async schedule(pod) {
        if (pod.phase !== PodPhase.PENDING) {
            throw new SchedulingError("Pod is not pending");
        }

        // Filtering identifies feasible nodes.
        const feasible = this.nodes.filter(node => node.canHost(pod));

        if (feasible.length === 0) {
            throw new SchedulingError(
                `No feasible node for ${pod.metadata.name}`
            );
        }

        // Scoring favors the smallest remaining CPU capacity.
        feasible.sort((a, b) => {
            const scoreA = a.availableCPU - pod.cpuRequest;
            const scoreB = b.availableCPU - pod.cpuRequest;

            return scoreA - scoreB ||
                a.availableMemory - b.availableMemory ||
                a.name.localeCompare(b.name);
        });

        const selected = feasible[0];

        selected.allocate(pod);
        pod.nodeName = selected.name;
        pod.phase = PodPhase.RUNNING;

        try {
            await this.apiServer.updatePod(pod, "scheduler");

            this.events.emit("pod:scheduled", {
                pod: pod.metadata.name,
                node: selected.name
            });

            return selected.name;
        } catch (error) {
            selected.release(pod);
            pod.phase = PodPhase.PENDING;
            pod.nodeName = null;
            throw error;
        }
    }
}

// ============================================================
// 6. CONTROLLER RECONCILIATION
// ============================================================

class Deployment {
    constructor(name, namespace, replicas, image, cpu = 1, memory = 128) {
        this.name = name;
        this.namespace = namespace;
        this.replicas = replicas;
        this.image = image;
        this.cpu = cpu;
        this.memory = memory;

        if (!name || !namespace || !image ||
            !Number.isSafeInteger(replicas) || replicas < 0) {
            throw new ValidationError("Invalid deployment specification");
        }
    }
}

class DeploymentController {
    constructor(apiServer, events) {
        this.apiServer = apiServer;
        this.events = events;
    }

    async reconcile(deployment) {
        const prefix =
            `/registry/pods/${deployment.namespace}/${deployment.name}-`;

        const existing = this.apiServer.store.list(prefix);

        const current = existing.length;
        let created = 0;

        for (let i = current; i < deployment.replicas; i++) {
            const pod = new Pod(
                new ResourceMetadata(
                    `${deployment.name}-${i}`,
                    deployment.namespace,
                    { app: deployment.name }
                ),
                [
                    new ContainerSpec(
                        "application",
                        deployment.image,
                        deployment.cpu,
                        deployment.memory
                    )
                ]
            );

            await this.apiServer.createPod(
                pod,
                "deployment-controller"
            );

            created++;
        }

        this.events.emit("deployment:reconciled", {
            deployment: deployment.name,
            desired: deployment.replicas,
            observedBefore: current,
            created
        });

        return {
            desired: deployment.replicas,
            observedBefore: current,
            created
        };
    }
}

// ============================================================
// 7. HEALTH MONITORING
// ============================================================

class ComponentMonitor {
    constructor(events) {
        this.components = new Map();
        this.events = events;
    }

    register(name, version) {
        if (this.components.has(name)) {
            throw new ConflictError("Component already registered");
        }

        this.components.set(name, {
            name,
            version,
            status: ComponentStatus.HEALTHY,
            heartbeat: Date.now()
        });
    }

    heartbeat(name) {
        const component = this.components.get(name);

        if (!component) {
            throw new NotFoundError("Component not found");
        }

        component.heartbeat = Date.now();
        component.status = ComponentStatus.HEALTHY;
    }

    evaluate(timeoutMilliseconds = 30000) {
        if (!Number.isFinite(timeoutMilliseconds) ||
            timeoutMilliseconds <= 0) {
            throw new ValidationError("Invalid timeout");
        }

        const now = Date.now();
        const result = {};

        for (const [name, component] of this.components) {
            if (now - component.heartbeat > timeoutMilliseconds) {
                component.status = ComponentStatus.UNAVAILABLE;

                this.events.emit("component:unavailable", {
                    component: name
                });
            }

            result[name] = component.status;
        }

        return result;
    }
}

// ============================================================
// 8. LEASE-BASED LEADER ELECTION
// ============================================================

class LeaderElection {
    constructor(leaseMilliseconds = 15000) {
        if (!Number.isFinite(leaseMilliseconds) ||
            leaseMilliseconds <= 0) {
            throw new ValidationError("Invalid lease duration");
        }

        this.leaseMilliseconds = leaseMilliseconds;
        this.holder = null;
        this.renewedAt = 0;
    }

    acquire(candidate) {
        if (!candidate) {
            throw new ValidationError("Candidate identity required");
        }

        const now = Date.now();

        const expired = this.holder === null ||
            now - this.renewedAt >= this.leaseMilliseconds;

        if (expired || this.holder === candidate) {
            this.holder = candidate;
            this.renewedAt = now;
            return true;
        }

        return false;
    }

    isLeader(candidate) {
        return this.holder === candidate &&
            Date.now() - this.renewedAt < this.leaseMilliseconds;
    }
}

// ============================================================
// 9. CLUSTER ORCHESTRATION
// ============================================================

class KubernetesControlPlane extends EventEmitter {
    constructor() {
        super();

        this.store = new EtcdStore(this);
        this.apiServer = new APIServer(this.store, this);

        this.nodes = [
            new Node("worker-01", 8, 2048),
            new Node("worker-02", 4, 1024)
        ];

        this.scheduler = new Scheduler(
            this.apiServer,
            this.nodes,
            this
        );

        this.controller = new DeploymentController(
            this.apiServer,
            this
        );

        this.monitor = new ComponentMonitor(this);
        this.leaderElection = new LeaderElection();

        this.registerComponents();
    }

    registerComponents() {
        for (const name of [
            "kube-apiserver",
            "kube-scheduler",
            "kube-controller-manager",
            "etcd"
        ]) {
            this.monitor.register(name, "v1.32.0");
        }
    }

    async deploy(deployment) {
        return this.controller.reconcile(deployment);
    }

    async schedulePending() {
        const pending = this.store.list("/registry/pods/")
            .map(Pod.fromJSON)
            .filter(pod => pod.phase === PodPhase.PENDING);

        const results = [];

        for (const pod of pending) {
            try {
                const node = await this.scheduler.schedule(pod);

                results.push({
                    pod: pod.metadata.name,
                    result: "Scheduled",
                    node
                });
            } catch (error) {
                if (!(error instanceof SchedulingError)) {
                    throw error;
                }

                results.push({
                    pod: pod.metadata.name,
                    result: "Unschedulable",
                    reason: error.message
                });
            }
        }

        return results;
    }

    report() {
        const pods = this.store.list("/registry/pods/")
            .map(Pod.fromJSON);

        const phases = Object.fromEntries(
            Object.values(PodPhase).map(phase => [
                phase,
                pods.filter(pod => pod.phase === phase).length
            ])
        );

        return {
            revision: this.store.revision,
            podCount: pods.length,
            phases,
            nodes: this.nodes.map(node => ({
                name: node.name,
                condition: node.condition,
                cpuAvailable: node.availableCPU,
                memoryAvailable: node.availableMemory
            })),
            components: this.monitor.evaluate(),
            auditRecords: this.apiServer.auditLog.length
        };
    }
}

// ============================================================
// 10. EXECUTABLE TESTS
// ============================================================

async function main() {
    const cluster = new KubernetesControlPlane();

    cluster.on("pod:created", event => {
        console.log("POD CREATED:", event.name);
    });

    cluster.on("pod:scheduled", event => {
        console.log(
            `POD SCHEDULED: ${event.pod} -> ${event.node}`
        );
    });

    cluster.on("component:unavailable", event => {
        console.log("COMPONENT FAILURE:", event.component);
    });

    assert.equal(
        cluster.leaderElection.acquire("controller-01"),
        true
    );

    assert.equal(
        cluster.leaderElection.isLeader("controller-01"),
        true
    );

    const deployment = new Deployment(
        "web",
        "production",
        3,
        "nginx:1.27",
        1,
        256
    );

    const reconciliation = await cluster.deploy(deployment);

    assert.equal(reconciliation.created, 3);

    const scheduling = await cluster.schedulePending();

    assert.equal(scheduling.length, 3);
    assert.ok(
        scheduling.every(item => item.result === "Scheduled")
    );

    const pods = cluster.store.list(
        "/registry/pods/production/web-"
    ).map(Pod.fromJSON);

    assert.equal(pods.length, 3);

    assert.ok(
        pods.every(pod => pod.phase === PodPhase.RUNNING)
    );

    // Duplicate resource rejection.
    await assert.rejects(
        () => cluster.apiServer.createPod(pods[0]),
        ConflictError
    );

    // Invalid resource rejection.
    assert.throws(
        () => new ContainerSpec("bad", "nginx", 0, 128),
        ValidationError
    );

    // Unschedulable resource.
    const oversized = new Pod(
        new ResourceMetadata("oversized"),
        [
            new ContainerSpec("app", "large-image", 100, 100000)
        ]
    );

    await assert.rejects(
        () => cluster.scheduler.schedule(oversized),
        SchedulingError
    );

    // Optimistic concurrency conflict.
    const key = "/registry/pods/production/web-0";
    const snapshot = cluster.store.getWithRevision(key);

    cluster.store.put(key, snapshot.value);

    assert.throws(
        () => cluster.store.put(
            key,
            snapshot.value,
            snapshot.revision
        ),
        ConflictError
    );

    console.log("\nCLUSTER REPORT");

    console.log(
        JSON.stringify(cluster.report(), null, 2)
    );

    console.log("\nSCHEDULING RESULTS");

    console.log(
        JSON.stringify(scheduling, null, 2)
    );

    console.log("\nALL TESTS PASSED");
}

main().catch(error => {
    console.error("CONTROL PLANE FAILURE:", error.message);
    process.exitCode = 1;
});
