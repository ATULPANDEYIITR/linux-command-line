"use strict";

/*
 * Kubernetes Deployment and ReplicaSet controller simulation.
 *
 * Demonstrates:
 * - Declarative desired state
 * - Event-driven reconciliation
 * - ReplicaSet lifecycle
 * - Rolling updates
 * - Readiness management
 * - Rollback
 * - Deployment scaling
 * - Revision history
 * - Asynchronous controller operations
 *
 * Runtime: Node.js 18+
 */

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");

class DeploymentError extends Error {}
class ValidationError extends DeploymentError {}
class RevisionError extends DeploymentError {}

const PodPhase = Object.freeze({
    PENDING: "Pending",
    RUNNING: "Running",
    TERMINATING: "Terminating",
    TERMINATED: "Terminated",
    FAILED: "Failed"
});

const DeploymentPhase = Object.freeze({
    PROGRESSING: "Progressing",
    AVAILABLE: "Available",
    DEGRADED: "Degraded"
});

function validateImage(image) {
    if (
        typeof image !== "string" ||
        image.trim().length === 0 ||
        image.length > 255
    ) {
        throw new ValidationError("Invalid container image");
    }
}

function validateInteger(value, name, minimum = 0) {
    if (!Number.isSafeInteger(value) || value < minimum) {
        throw new ValidationError(
            `${name} must be an integer >= ${minimum}`
        );
    }
}

class Pod {
    constructor(image, replicaSetId) {
        this.id = crypto.randomUUID();
        this.image = image;
        this.replicaSetId = replicaSetId;
        this.phase = PodPhase.PENDING;
        this.ready = false;
        this.createdAt = Date.now();
        this.readySince = null;
    }

    start() {
        if (this.phase !== PodPhase.PENDING) {
            throw new DeploymentError("Pod cannot start from current state");
        }

        this.phase = PodPhase.RUNNING;
    }

    markReady() {
        if (this.phase !== PodPhase.RUNNING) {
            throw new DeploymentError("Pod must be running before readiness");
        }

        this.ready = true;
        this.readySince = Date.now();
    }

    markUnready() {
        this.ready = false;
        this.readySince = null;
    }

    terminate() {
        if (
            this.phase === PodPhase.TERMINATED ||
            this.phase === PodPhase.FAILED
        ) {
            return;
        }

        this.ready = false;
        this.phase = PodPhase.TERMINATING;
        this.phase = PodPhase.TERMINATED;
    }

    get active() {
        return ![
            PodPhase.TERMINATED,
            PodPhase.FAILED
        ].includes(this.phase);
    }
}

class ReplicaSet {
    constructor(deploymentName, image, revision) {
        this.id = crypto.randomUUID();
        this.name = `${deploymentName}-${this.id.slice(0, 8)}`;
        this.image = image;
        this.revision = revision;
        this.deploymentName = deploymentName;
        this.desiredReplicas = 0;
        this.pods = new Map();
        this.active = true;
    }

    get activePods() {
        return [...this.pods.values()].filter(pod => pod.active);
    }

    get readyReplicas() {
        return this.activePods.filter(
            pod => pod.phase === PodPhase.RUNNING && pod.ready
        ).length;
    }
}

class Deployment extends EventEmitter {
    constructor(config) {
        super();

        this.config = this.validateConfig(config);
        this.generation = 1;
        this.revision = 1;

        this.replicaSets = new Map();
        this.history = new Map();

        this.status = {
            desired: this.config.replicas,
            updated: 0,
            ready: 0,
            available: 0,
            unavailable: this.config.replicas,
            phase: DeploymentPhase.PROGRESSING
        };

        this.createReplicaSet(this.config.image);
        this.reconcile();
    }

    validateConfig(config) {
        if (!config || typeof config !== "object") {
            throw new ValidationError("Configuration is required");
        }

        if (!/^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/.test(config.name)) {
            throw new ValidationError("Invalid deployment name");
        }

        validateImage(config.image);
        validateInteger(config.replicas, "replicas");
        validateInteger(config.maxSurge, "maxSurge");
        validateInteger(config.maxUnavailable, "maxUnavailable");
        validateInteger(config.minReadySeconds ?? 0, "minReadySeconds");
        validateInteger(config.revisionHistoryLimit ?? 5, "revisionHistoryLimit");

        if (config.maxSurge === 0 && config.maxUnavailable === 0) {
            throw new ValidationError(
                "maxSurge and maxUnavailable cannot both be zero"
            );
        }

        return {
            namespace: "default",
            minReadySeconds: 0,
            revisionHistoryLimit: 5,
            ...config
        };
    }

    createReplicaSet(image) {
        const rs = new ReplicaSet(
            this.config.name,
            image,
            this.revision
        );

        this.replicaSets.set(rs.id, rs);

        this.history.set(this.revision, {
            revision: this.revision,
            image,
            replicaSetId: rs.id
        });

        this.emit("replicaset:created", rs);

        return rs;
    }

    get activeReplicaSets() {
        return [...this.replicaSets.values()].filter(rs => rs.active);
    }

    get currentReplicaSet() {
        const candidates = this.activeReplicaSets.filter(
            rs => rs.image === this.config.image
        );

        return candidates.sort(
            (a, b) => b.revision - a.revision
        )[0];
    }

    createPod(rs) {
        const pod = new Pod(rs.image, rs.id);

        rs.pods.set(pod.id, pod);
        pod.start();

        this.emit("pod:created", pod);

        return pod;
    }

    removePod(pod) {
        pod.terminate();
        this.emit("pod:terminated", pod);
    }

    syncReplicaSet(rs, desired) {
        rs.desiredReplicas = desired;

        const active = rs.activePods;

        while (active.length < desired) {
            active.push(this.createPod(rs));
        }

        while (active.length > desired) {
            const pod = active.pop();
            this.removePod(pod);
        }
    }

    reconcile() {
        /*
         * Reconciliation is idempotent: repeated execution converges
         * the actual state toward the declared desired state.
         */

        const sets = this.activeReplicaSets;

        if (sets.length === 0) {
            this.createReplicaSet(this.config.image);
        }

        for (const rs of this.activeReplicaSets) {
            const desired = rs.image === this.config.image
                ? this.config.replicas
                : 0;

            this.syncReplicaSet(rs, desired);
        }

        this.refreshStatus();
        this.emit("deployment:reconciled", this.snapshot());

        return this.status;
    }

    refreshStatus() {
        const pods = this.activeReplicaSets.flatMap(
            rs => rs.activePods
        );

        const readyPods = pods.filter(
            pod => pod.ready && pod.phase === PodPhase.RUNNING
        );

        const availablePods = readyPods.filter(pod => {
            return (
                this.config.minReadySeconds === 0 ||
                Date.now() - pod.readySince >=
                    this.config.minReadySeconds * 1000
            );
        });

        const updated = pods.filter(
            pod => pod.image === this.config.image
        ).length;

        this.status = {
            desired: this.config.replicas,
            updated,
            ready: readyPods.length,
            available: availablePods.length,
            unavailable: Math.max(
                0,
                this.config.replicas - availablePods.length
            ),
            phase: availablePods.length >= this.config.replicas
                ? DeploymentPhase.AVAILABLE
                : DeploymentPhase.PROGRESSING
        };
    }

    markReady(podId) {
        for (const rs of this.replicaSets.values()) {
            const pod = rs.pods.get(podId);

            if (pod) {
                pod.markReady();
                this.refreshStatus();
                this.emit("pod:ready", pod);
                return;
            }
        }

        throw new DeploymentError(`Pod ${podId} not found`);
    }

    markUnready(podId) {
        for (const rs of this.replicaSets.values()) {
            const pod = rs.pods.get(podId);

            if (pod) {
                pod.markUnready();
                this.refreshStatus();
                this.emit("pod:unready", pod);
                return;
            }
        }

        throw new DeploymentError(`Pod ${podId} not found`);
    }

    scale(replicas) {
        validateInteger(replicas, "replicas");

        this.config.replicas = replicas;
        this.generation++;

        this.reconcile();

        this.emit("deployment:scaled", {
            generation: this.generation,
            replicas
        });
    }

    updateImage(image) {
        validateImage(image);

        if (image === this.config.image) {
            return false;
        }

        this.config.image = image;
        this.generation++;
        this.revision++;

        for (const rs of this.activeReplicaSets) {
            rs.active = false;
        }

        this.createReplicaSet(image);
        this.reconcile();

        this.emit("deployment:updated", {
            image,
            revision: this.revision
        });

        return true;
    }

    async rollingUpdateStep() {
        const desired = this.config.replicas;

        const oldSets = this.activeReplicaSets.filter(
            rs => rs.image !== this.config.image
        );

        const newSets = this.activeReplicaSets.filter(
            rs => rs.image === this.config.image
        );

        if (newSets.length === 0) {
            throw new DeploymentError("Target ReplicaSet not found");
        }

        const target = newSets[0];

        const allPods = this.activeReplicaSets.flatMap(
            rs => rs.activePods
        );

        const total = allPods.length;

        const ready = allPods.filter(
            pod => pod.ready && pod.phase === PodPhase.RUNNING
        ).length;

        const maxTotal = desired + this.config.maxSurge;

        const minimumAvailable = Math.max(
            0,
            desired - this.config.maxUnavailable
        );

        const oldPods = oldSets.flatMap(rs => rs.activePods);
        const newPods = target.activePods;

        if (
            newPods.length < desired &&
            total < maxTotal
        ) {
            const pod = this.createPod(target);
            this.refreshStatus();

            return {
                action: "CREATE",
                podId: pod.id
            };
        }

        if (oldPods.length > 0 && ready > minimumAvailable) {
            const pod = oldPods[0];

            this.removePod(pod);
            this.refreshStatus();

            return {
                action: "TERMINATE",
                podId: pod.id
            };
        }

        if (
            oldPods.length === 0 &&
            newPods.length >= desired
        ) {
            oldSets.forEach(rs => {
                rs.active = false;
            });

            this.refreshStatus();

            return {
                action: "COMPLETED"
            };
        }

        return {
            action: "WAIT",
            reason: "Waiting for readiness or available capacity"
        };
    }

    async rollingUpdate(maxSteps = 100) {
        validateInteger(maxSteps, "maxSteps", 1);

        const operations = [];

        for (let i = 0; i < maxSteps; i++) {
            const operation = await this.rollingUpdateStep();

            operations.push(operation);
            this.emit("rollout:operation", operation);

            if (operation.action === "COMPLETED") {
                return operations;
            }

            if (operation.action === "WAIT") {
                return operations;
            }

            // The simulator models asynchronous controller scheduling.
            await new Promise(resolve => setImmediate(resolve));
        }

        throw new DeploymentError("Rollout exceeded maximum steps");
    }

    rollback(targetRevision) {
        validateInteger(targetRevision, "targetRevision", 1);

        const previous = this.history.get(targetRevision);

        if (!previous) {
            throw new RevisionError(
                `Revision ${targetRevision} does not exist`
            );
        }

        if (previous.image === this.config.image) {
            return false;
        }

        // Rollback creates a new revision; history remains chronological.
        this.updateImage(previous.image);

        this.emit("deployment:rollback", {
            targetRevision,
            newRevision: this.revision,
            image: previous.image
        });

        return true;
    }

    pruneHistory() {
        const limit = this.config.revisionHistoryLimit;

        if (limit === 0) {
            const current = this.history.get(this.revision);

            this.history.clear();
            this.history.set(this.revision, current);
        } else {
            const revisions = [...this.history.keys()].sort(
                (a, b) => a - b
            );

            while (revisions.length > limit) {
                const oldRevision = revisions.shift();
                this.history.delete(oldRevision);
            }
        }

        for (const [id, rs] of this.replicaSets) {
            if (!rs.active && !this.history.has(rs.revision)) {
                this.replicaSets.delete(id);
            }
        }
    }

    snapshot() {
        this.refreshStatus();

        return {
            name: this.config.name,
            namespace: this.config.namespace,
            generation: this.generation,
            revision: this.revision,
            image: this.config.image,
            status: { ...this.status },
            replicaSets: this.activeReplicaSets.map(rs => ({
                name: rs.name,
                revision: rs.revision,
                image: rs.image,
                desired: rs.desiredReplicas,
                active: rs.activePods.length,
                ready: rs.readyReplicas
            })),
            history: [...this.history.values()]
        };
    }

    async saveReport(filePath) {
        const report = JSON.stringify(this.snapshot(), null, 2);

        // Restrictive permissions protect the generated report.
        await fs.writeFile(filePath, report, {
            encoding: "utf8",
            mode: 0o600
        });
    }
}

async function main() {
    const deployment = new Deployment({
        name: "payment-api",
        namespace: "production",
        image: "payment-api:1.0.0",
        replicas: 3,
        maxSurge: 1,
        maxUnavailable: 0,
        minReadySeconds: 0,
        revisionHistoryLimit: 5
    });

    deployment.on("pod:created", pod => {
        console.log("POD CREATED:", pod.id, pod.image);
    });

    deployment.on("pod:ready", pod => {
        console.log("POD READY:", pod.id);
    });

    deployment.on("deployment:updated", event => {
        console.log("DEPLOYMENT UPDATED:", event);
    });

    // Mark initial application instances ready.
    for (const rs of deployment.activeReplicaSets) {
        for (const pod of rs.activePods) {
            deployment.markReady(pod.id);
        }
    }

    console.log("\nINITIAL STATE");
    console.log(JSON.stringify(deployment.snapshot(), null, 2));

    deployment.updateImage("payment-api:2.0.0");

    console.log("\nROLLING UPDATE");

    for (let i = 0; i < 30; i++) {
        const result = await deployment.rollingUpdateStep();

        console.log(result);

        // Simulate successful readiness probes.
        for (const rs of deployment.activeReplicaSets) {
            for (const pod of rs.activePods) {
                if (
                    pod.image === deployment.config.image &&
                    !pod.ready
                ) {
                    deployment.markReady(pod.id);
                }
            }
        }

        if (result.action === "COMPLETED") {
            break;
        }
    }

    console.log("\nUPDATED STATE");
    console.log(JSON.stringify(deployment.snapshot(), null, 2));

    deployment.rollback(1);

    for (const rs of deployment.activeReplicaSets) {
        for (const pod of rs.activePods) {
            if (
                pod.image === deployment.config.image &&
                !pod.ready
            ) {
                deployment.markReady(pod.id);
            }
        }
    }

    console.log("\nROLLBACK STATE");
    console.log(JSON.stringify(deployment.snapshot(), null, 2));

    deployment.scale(5);

    console.log("\nSCALED STATE");
    console.log(JSON.stringify(deployment.snapshot(), null, 2));

    deployment.pruneHistory();

    // Uncomment to persist a local report.
    // await deployment.saveReport("./deployment-report.json");
}

main().catch(error => {
    console.error("CONTROLLER FAILURE:", error.message);
    process.exitCode = 1;
});
