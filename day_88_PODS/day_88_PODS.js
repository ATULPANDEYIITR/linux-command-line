"use strict";

/*
 * KUBERNETES POD LIFECYCLE AND WORKLOAD CONTROLLER
 *
 * Node.js 18+
 *
 * Engineering focus:
 * - Event-driven Pod lifecycle
 * - Container state management
 * - Asynchronous initialization
 * - Resource-aware scheduling
 * - Readiness and liveness policies
 * - Deployment reconciliation
 * - Rolling updates
 * - Retry handling
 * - Manifest validation
 * - Operational event monitoring
 */

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");

// ============================================================
// 1. CONSTANTS
// ============================================================

const PodPhase = Object.freeze({
    PENDING: "Pending",
    RUNNING: "Running",
    SUCCEEDED: "Succeeded",
    FAILED: "Failed",
    UNKNOWN: "Unknown"
});

const ContainerState = Object.freeze({
    WAITING: "Waiting",
    RUNNING: "Running",
    TERMINATED: "Terminated"
});

const RestartPolicy = Object.freeze({
    ALWAYS: "Always",
    ON_FAILURE: "OnFailure",
    NEVER: "Never"
});

const sleep = (milliseconds) =>
    new Promise(resolve => setTimeout(resolve, milliseconds));

function validateName(value, field) {
    if (
        typeof value !== "string" ||
        !/^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/.test(value)
    ) {
        throw new Error(`Invalid ${field}: ${value}`);
    }
}

function validateResources(resources) {
    const {
        cpuRequest,
        memoryRequest,
        cpuLimit,
        memoryLimit
    } = resources;

    for (const [name, value] of Object.entries(resources)) {
        if (!Number.isFinite(value) || value < 0) {
            throw new Error(`Invalid resource value: ${name}`);
        }
    }

    if (
        cpuLimit <= 0 ||
        memoryLimit <= 0 ||
        cpuRequest > cpuLimit ||
        memoryRequest > memoryLimit
    ) {
        throw new Error("Resource requests and limits are inconsistent.");
    }
}

// ============================================================
// 2. CONTAINER
// ============================================================

class Container {
    constructor({
        name,
        image,
        cpuRequest = 0.1,
        memoryRequest = 128,
        cpuLimit = 0.5,
        memoryLimit = 512,
        environment = {}
    }) {
        validateName(name, "container name");

        if (
            typeof image !== "string" ||
            !image.trim() ||
            /\s/.test(image)
        ) {
            throw new Error("A valid container image is required.");
        }

        validateResources({
            cpuRequest,
            memoryRequest,
            cpuLimit,
            memoryLimit
        });

        this.name = name;
        this.image = image;
        this.resources = Object.freeze({
            cpuRequest,
            memoryRequest,
            cpuLimit,
            memoryLimit
        });

        this.environment = Object.freeze({ ...environment });
        this.state = ContainerState.WAITING;
        this.ready = false;
        this.restartCount = 0;
        this.exitCode = null;
        this.logs = [];
    }

    start() {
        if (this.state === ContainerState.RUNNING) {
            throw new Error(`${this.name} is already running.`);
        }

        this.state = ContainerState.RUNNING;
        this.ready = false;
        this.exitCode = null;
        this.logs.push("Container started.");
    }

    markReady() {
        if (this.state !== ContainerState.RUNNING) {
            throw new Error("Container must be running.");
        }

        this.ready = true;
        this.logs.push("Readiness check succeeded.");
    }

    terminate(exitCode) {
        if (this.state !== ContainerState.RUNNING) {
            throw new Error("Container is not running.");
        }

        if (!Number.isInteger(exitCode)) {
            throw new Error("Exit code must be an integer.");
        }

        this.state = ContainerState.TERMINATED;
        this.ready = false;
        this.exitCode = exitCode;
        this.logs.push(`Container exited: ${exitCode}.`);
    }

    restart() {
        this.restartCount++;
        this.state = ContainerState.WAITING;
        this.ready = false;
        this.exitCode = null;
        this.logs.push("Container restart initiated.");
    }

    snapshot() {
        return {
            name: this.name,
            image: this.image,
            state: this.state,
            ready: this.ready,
            restartCount: this.restartCount,
            exitCode: this.exitCode
        };
    }
}

// ============================================================
// 3. NODE RESOURCE MANAGEMENT
// ============================================================

class Node {
    constructor(name, cpuCapacity, memoryCapacity) {
        validateName(name, "node name");

        if (
            !Number.isFinite(cpuCapacity) ||
            !Number.isFinite(memoryCapacity) ||
            cpuCapacity <= 0 ||
            memoryCapacity <= 0
        ) {
            throw new Error("Invalid node capacity.");
        }

        this.name = name;
        this.cpuCapacity = cpuCapacity;
        this.memoryCapacity = memoryCapacity;
        this.allocations = new Map();
    }

    get allocated() {
        let cpu = 0;
        let memory = 0;

        for (const allocation of this.allocations.values()) {
            cpu += allocation.cpu;
            memory += allocation.memory;
        }

        return { cpu, memory };
    }

    canFit(request) {
        const current = this.allocated;

        return (
            current.cpu + request.cpu <= this.cpuCapacity &&
            current.memory + request.memory <= this.memoryCapacity
        );
    }

    reserve(podId, request) {
        if (this.allocations.has(podId)) {
            throw new Error("Pod already has a node reservation.");
        }

        if (!this.canFit(request)) {
            return false;
        }

        this.allocations.set(podId, { ...request });
        return true;
    }

    release(podId) {
        return this.allocations.delete(podId);
    }
}

// ============================================================
// 4. RESOURCE-AWARE SCHEDULER
// ============================================================

class Scheduler {
    constructor(nodes) {
        if (!Array.isArray(nodes) || nodes.length === 0) {
            throw new Error("Scheduler requires at least one node.");
        }

        this.nodes = nodes;
    }

    calculateRequest(pod) {
        const application = pod.containers.reduce(
            (total, container) => ({
                cpu: total.cpu + container.resources.cpuRequest,
                memory: total.memory + container.resources.memoryRequest
            }),
            { cpu: 0, memory: 0 }
        );

        const init = pod.initContainers.reduce(
            (maximum, container) => ({
                cpu: Math.max(
                    maximum.cpu,
                    container.resources.cpuRequest
                ),
                memory: Math.max(
                    maximum.memory,
                    container.resources.memoryRequest
                )
            }),
            { cpu: 0, memory: 0 }
        );

        return {
            cpu: Math.max(application.cpu, init.cpu),
            memory: Math.max(application.memory, init.memory)
        };
    }

    schedule(pod) {
        if (pod.node) {
            throw new Error("Pod is already scheduled.");
        }

        const request = this.calculateRequest(pod);

        const candidates = this.nodes
            .filter(node => node.canFit(request))
            .sort((a, b) => {
                const scoreA =
                    a.cpuCapacity - a.allocated.cpu - request.cpu;
                const scoreB =
                    b.cpuCapacity - b.allocated.cpu - request.cpu;

                return scoreA - scoreB;
            });

        for (const node of candidates) {
            if (node.reserve(pod.id, request)) {
                pod.node = node;
                pod.emit("scheduled", {
                    node: node.name,
                    request
                });
                return node.name;
            }
        }

        throw new Error(
            `Insufficient resources for Pod ${pod.name}.`
        );
    }
}

// ============================================================
// 5. POD CONTROLLER
// ============================================================

class Pod extends EventEmitter {
    constructor({
        name,
        namespace = "default",
        containers,
        initContainers = [],
        restartPolicy = RestartPolicy.ALWAYS,
        labels = {},
        readinessProbe = null,
        livenessProbe = null
    }) {
        super();

        validateName(name, "Pod name");
        validateName(namespace, "namespace");

        if (!Array.isArray(containers) || containers.length === 0) {
            throw new Error("At least one application container is required.");
        }

        if (!Object.values(RestartPolicy).includes(restartPolicy)) {
            throw new Error("Unsupported restart policy.");
        }

        const allNames = [
            ...containers,
            ...initContainers
        ].map(container => container.name);

        if (new Set(allNames).size !== allNames.length) {
            throw new Error("Container names must be unique.");
        }

        this.id = crypto.randomUUID();
        this.name = name;
        this.namespace = namespace;
        this.containers = containers;
        this.initContainers = initContainers;
        this.restartPolicy = restartPolicy;
        this.labels = Object.freeze({ ...labels });
        this.readinessProbe = readinessProbe;
        this.livenessProbe = livenessProbe;

        this.node = null;
        this.phase = PodPhase.PENDING;

        this.conditions = {
            PodScheduled: false,
            Initialized: initContainers.length === 0,
            ContainersReady: false,
            Ready: false
        };

        this.events = [];
    }

    emit(event, data = {}) {
        const record = {
            event,
            data,
            timestamp: new Date().toISOString()
        };

        this.events.push(record);
        super.emit("podEvent", record);
    }

    async initialize() {
        if (!this.node) {
            throw new Error("Pod must be scheduled first.");
        }

        if (this.phase !== PodPhase.PENDING) {
            throw new Error("Pod is not pending.");
        }

        this.conditions.PodScheduled = true;

        for (const container of this.initContainers) {
            container.start();
            await sleep(5);
            container.markReady();
            container.terminate(0);

            this.emit("initContainerCompleted", {
                container: container.name
            });
        }

        this.conditions.Initialized = true;
    }

    async start() {
        if (!this.conditions.Initialized) {
            throw new Error("Initialization is incomplete.");
        }

        if (!this.node) {
            throw new Error("Pod is not scheduled.");
        }

        if (this.phase !== PodPhase.PENDING) {
            throw new Error("Pod cannot start in its current phase.");
        }

        for (const container of this.containers) {
            container.start();
        }

        this.phase = PodPhase.RUNNING;
        this.emit("started");
    }

    evaluateReadiness() {
        const ready =
            this.phase === PodPhase.RUNNING &&
            this.containers.every(
                container =>
                    container.state === ContainerState.RUNNING &&
                    container.ready
            );

        this.conditions.ContainersReady = ready;
        this.conditions.Ready = ready;

        return ready;
    }

    async runReadinessCheck(checkFunction) {
        if (!this.readinessProbe) {
            throw new Error("Readiness probe is not configured.");
        }

        if (this.phase !== PodPhase.RUNNING) {
            throw new Error("Pod is not running.");
        }

        const successful = await checkFunction();

        for (const container of this.containers) {
            if (container.state === ContainerState.RUNNING) {
                container.ready = Boolean(successful);
            }
        }

        this.evaluateReadiness();

        this.emit("readinessEvaluated", {
            successful: Boolean(successful),
            ready: this.conditions.Ready
        });

        return this.conditions.Ready;
    }

    async runLivenessCheck(checkFunction) {
        if (!this.livenessProbe) {
            throw new Error("Liveness probe is not configured.");
        }

        if (this.phase !== PodPhase.RUNNING) {
            throw new Error("Pod is not running.");
        }

        const alive = await checkFunction();

        if (!alive) {
            this.emit("livenessFailure");
            await this.handleFailure(
                this.containers[0].name,
                137
            );
        }

        return Boolean(alive);
    }

    async handleFailure(containerName, exitCode) {
        const container = this.containers.find(
            item => item.name === containerName
        );

        if (!container) {
            throw new Error("Unknown container.");
        }

        container.terminate(exitCode);

        this.emit("containerTerminated", {
            container: containerName,
            exitCode
        });

        const restart =
            this.restartPolicy === RestartPolicy.ALWAYS ||
            (
                this.restartPolicy === RestartPolicy.ON_FAILURE &&
                exitCode !== 0
            );

        if (restart) {
            container.restart();
            container.start();

            this.emit("containerRestarted", {
                container: containerName,
                restartCount: container.restartCount
            });
        } else if (
            this.containers.every(
                item => item.state === ContainerState.TERMINATED
            )
        ) {
            this.phase = this.containers.every(
                item => item.exitCode === 0
            )
                ? PodPhase.SUCCEEDED
                : PodPhase.FAILED;
        }

        this.evaluateReadiness();
    }

    snapshot() {
        return {
            id: this.id,
            name: this.name,
            namespace: this.namespace,
            phase: this.phase,
            node: this.node?.name ?? null,
            conditions: { ...this.conditions },
            containers: this.containers.map(
                container => container.snapshot()
            ),
            events: this.events.length
        };
    }
}

// ============================================================
// 6. DEPLOYMENT CONTROLLER
// ============================================================

class Deployment {
    constructor({
        name,
        namespace,
        image,
        replicas,
        labels = {},
        maxSurge = 1
    }) {
        validateName(name, "deployment name");

        if (!Number.isInteger(replicas) || replicas < 0) {
            throw new Error("Replica count must be a non-negative integer.");
        }

        if (!Number.isInteger(maxSurge) || maxSurge < 0) {
            throw new Error("maxSurge must be non-negative.");
        }

        this.name = name;
        this.namespace = namespace;
        this.image = image;
        this.desiredReplicas = replicas;
        this.labels = Object.freeze({ ...labels });
        this.maxSurge = maxSurge;
        this.generation = 1;
        this.pods = new Map();
    }

    createPod(index, image = this.image) {
        const pod = new Pod({
            name: `${this.name}-${index}-${crypto.randomUUID().slice(0, 6)}`,
            namespace: this.namespace,
            containers: [
                new Container({
                    name: "application",
                    image
                })
            ],
            labels: {
                ...this.labels,
                deployment: this.name
            }
        });

        this.pods.set(pod.id, pod);
        return pod;
    }

    reconcile() {
        const active = [...this.pods.values()].filter(
            pod =>
                pod.phase !== PodPhase.FAILED &&
                pod.phase !== PodPhase.SUCCEEDED
        );

        const difference = this.desiredReplicas - active.length;

        if (difference > 0) {
            for (let i = 0; i < difference; i++) {
                this.createPod(active.length + i + 1);
            }
        } else if (difference < 0) {
            const excess = active.slice(difference);

            for (const pod of excess) {
                this.pods.delete(pod.id);
            }
        }

        return this.status();
    }

    async rollingUpdate(newImage, scheduler) {
        if (!newImage || /\s/.test(newImage)) {
            throw new Error("A valid image reference is required.");
        }

        this.generation++;

        const oldPods = [...this.pods.values()];
        const replacementPods = [];

        // Create replacements within the configured surge allowance.
        for (
            let i = 0;
            i < oldPods.length;
            i += this.maxSurge + 1
        ) {
            const batch = oldPods.slice(
                i,
                i + this.maxSurge + 1
            );

            for (const oldPod of batch) {
                const replacement = this.createPod(
                    i + replacementPods.length + 1,
                    newImage
                );

                scheduler.schedule(replacement);
                await replacement.initialize();
                await replacement.start();

                replacement.containers[0].markReady();
                replacement.evaluateReadiness();

                if (!replacement.conditions.Ready) {
                    throw new Error(
                        "Replacement Pod failed readiness validation."
                    );
                }

                replacementPods.push(replacement);
                this.pods.delete(oldPod.id);

                if (oldPod.node) {
                    oldPod.node.release(oldPod.id);
                }
            }
        }

        this.image = newImage;
        return this.status();
    }

    status() {
        const pods = [...this.pods.values()];

        return {
            name: this.name,
            desired: this.desiredReplicas,
            actual: pods.length,
            ready: pods.filter(
                pod => pod.conditions.Ready
            ).length,
            generation: this.generation,
            image: this.image
        };
    }
}

// ============================================================
// 7. MANIFEST VALIDATION
// ============================================================

function validateManifest(manifest) {
    const errors = [];

    if (manifest.apiVersion !== "v1") {
        errors.push("apiVersion must be v1.");
    }

    if (manifest.kind !== "Pod") {
        errors.push("kind must be Pod.");
    }

    if (!manifest.metadata?.name) {
        errors.push("metadata.name is required.");
    }

    const containers = manifest.spec?.containers;

    if (!Array.isArray(containers) || containers.length === 0) {
        errors.push("At least one container is required.");
    } else {
        const names = new Set();

        for (const container of containers) {
            if (!container.name || names.has(container.name)) {
                errors.push("Container names must be unique.");
            }

            names.add(container.name);

            if (!container.image) {
                errors.push(
                    `Container ${container.name} requires an image.`
                );
            }
        }
    }

    return {
        valid: errors.length === 0,
        errors
    };
}

// ============================================================
// 8. CLUSTER OBSERVABILITY
// ============================================================

function clusterMetrics(pods) {
    const metrics = {
        total: pods.length,
        pending: 0,
        running: 0,
        succeeded: 0,
        failed: 0,
        ready: 0,
        restarts: 0
    };

    for (const pod of pods) {
        switch (pod.phase) {
            case PodPhase.PENDING:
                metrics.pending++;
                break;
            case PodPhase.RUNNING:
                metrics.running++;
                break;
            case PodPhase.SUCCEEDED:
                metrics.succeeded++;
                break;
            case PodPhase.FAILED:
                metrics.failed++;
                break;
        }

        if (pod.evaluateReadiness()) {
            metrics.ready++;
        }

        metrics.restarts += pod.containers.reduce(
            (sum, container) => sum + container.restartCount,
            0
        );
    }

    return metrics;
}

// ============================================================
// 9. EXECUTION AND TESTING
// ============================================================

async function main() {
    console.log("\nKUBERNETES EVENT-DRIVEN POD CONTROLLER");
    console.log("======================================");

    const nodes = [
        new Node("worker-01", 8, 16384),
        new Node("worker-02", 4, 8192)
    ];

    const scheduler = new Scheduler(nodes);

    const pod = new Pod({
        name: "api-pod",
        namespace: "production",
        containers: [
            new Container({
                name: "api",
                image: "node:22-alpine",
                cpuRequest: 0.5,
                memoryRequest: 256,
                cpuLimit: 1,
                memoryLimit: 512
            }),
            new Container({
                name: "logging",
                image: "busybox:1.36"
            })
        ],
        initContainers: [
            new Container({
                name: "database-check",
                image: "busybox:1.36"
            })
        ],
        restartPolicy: RestartPolicy.ALWAYS,
        readinessProbe: {
            path: "/health",
            periodSeconds: 10
        },
        livenessProbe: {
            path: "/live",
            periodSeconds: 15
        }
    });

    pod.on("podEvent", event => {
        console.log("EVENT:", event.event);
    });

    console.log("\n1. Scheduling");
    console.log("Node:", scheduler.schedule(pod));

    console.log("\n2. Initialization");
    await pod.initialize();

    console.log("\n3. Container startup");
    await pod.start();

    console.log("\n4. Readiness");
    await pod.runReadinessCheck(async () => true);

    assert.equal(pod.conditions.Ready, true);

    console.log("Pod ready:", pod.conditions.Ready);

    console.log("\n5. Liveness");
    await pod.runLivenessCheck(async () => true);

    console.log("\n6. Failure and restart");
    await pod.handleFailure("api", 1);

    assert.equal(pod.containers[0].restartCount, 1);

    console.log(
        "Restart count:",
        pod.containers[0].restartCount
    );

    console.log("\n7. Manifest validation");

    const manifest = {
        apiVersion: "v1",
        kind: "Pod",
        metadata: {
            name: "sample-api"
        },
        spec: {
            containers: [
                {
                    name: "api",
                    image: "node:22-alpine"
                }
            ]
        }
    };

    const validation = validateManifest(manifest);

    assert.equal(validation.valid, true);

    console.log(validation);

    console.log("\n8. Deployment reconciliation");

    const deployment = new Deployment({
        name: "frontend",
        namespace: "production",
        image: "nginx:1.27",
        replicas: 3,
        labels: {
            app: "frontend"
        },
        maxSurge: 1
    });

    console.log("Initial state:", deployment.reconcile());

    console.log("\n9. Rolling update");

    const updated = await deployment.rollingUpdate(
        "nginx:1.28",
        scheduler
    );

    console.log("Updated deployment:", updated);

    console.log("\n10. Resource usage");

    for (const node of nodes) {
        console.log(node.name, {
            allocated: node.allocated,
            capacity: {
                cpu: node.cpuCapacity,
                memory: node.memoryCapacity
            }
        });
    }

    console.log("\n11. Cluster metrics");

    console.log(
        clusterMetrics([
            pod,
            ...deployment.pods.values()
        ])
    );

    console.log("\n12. Edge-case testing");

    assert.throws(
        () => new Node("invalid", -1, 1024),
        /Invalid node capacity/
    );

    assert.throws(
        () => new Container({
            name: "invalid",
            image: "nginx",
            cpuRequest: 2,
            cpuLimit: 1
        }),
        /inconsistent/
    );

    assert.throws(
        () => validateManifest({
            apiVersion: "v1",
            kind: "Pod",
            metadata: { name: "broken" },
            spec: { containers: [] }
        }).valid === false
            ? (() => { throw new Error("Invalid manifest"); })()
            : null,
        /Invalid manifest/
    );

    console.log("All assertions passed.");
}

main().catch(error => {
    console.error("Controller failure:", error.message);
    process.exitCode = 1;
});
