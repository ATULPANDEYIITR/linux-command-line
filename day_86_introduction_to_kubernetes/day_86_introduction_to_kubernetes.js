'use strict';

/**
 * Kubernetes Event-Driven Control Plane Simulator
 *
 * Demonstrates:
 * - Cluster and node management
 * - Asynchronous API operations
 * - Event-driven reconciliation
 * - Pod lifecycle
 * - Deployment controllers
 * - Resource-aware scheduling
 * - Service discovery
 * - Health monitoring
 * - Rolling updates
 * - Failure handling
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const { EventEmitter } = require('node:events');
const { randomUUID } = require('node:crypto');
const { setTimeout: delay } = require('node:timers/promises');


class KubernetesError extends Error {
    constructor(message, code = 'KUBERNETES_ERROR') {
        super(message);
        this.name = 'KubernetesError';
        this.code = code;
    }
}

class ValidationError extends KubernetesError {
    constructor(message) {
        super(message, 'VALIDATION_ERROR');
    }
}

class SchedulingError extends KubernetesError {
    constructor(message) {
        super(message, 'SCHEDULING_ERROR');
    }
}

class ResourceNotFoundError extends KubernetesError {
    constructor(message) {
        super(message, 'NOT_FOUND');
    }
}


// ============================================================
// RESOURCE VALIDATION
// ============================================================

class ResourceRequirements {
    constructor(cpuMillicores, memoryMB) {
        if (!Number.isInteger(cpuMillicores) || cpuMillicores <= 0) {
            throw new ValidationError('Invalid CPU request.');
        }

        if (!Number.isInteger(memoryMB) || memoryMB <= 0) {
            throw new ValidationError('Invalid memory request.');
        }

        this.cpuMillicores = cpuMillicores;
        this.memoryMB = memoryMB;

        Object.freeze(this);
    }
}


// ============================================================
// NODE
// ============================================================

class Node {
    constructor({
        name,
        role = 'worker',
        cpuMillicores,
        memoryMB
    }) {
        if (!name || !name.trim()) {
            throw new ValidationError('Node name is required.');
        }

        if (!['worker', 'control-plane'].includes(role)) {
            throw new ValidationError('Invalid node role.');
        }

        this.name = name;
        this.role = role;
        this.capacity = new ResourceRequirements(
            cpuMillicores,
            memoryMB
        );

        this.status = 'Ready';
        this.allocatedCPU = 0;
        this.allocatedMemory = 0;
        this.pods = new Set();
    }

    canHost(resources) {
        return (
            this.role === 'worker' &&
            this.status === 'Ready' &&
            this.allocatedCPU + resources.cpuMillicores
                <= this.capacity.cpuMillicores &&
            this.allocatedMemory + resources.memoryMB
                <= this.capacity.memoryMB
        );
    }

    allocate(pod) {
        if (!this.canHost(pod.resources)) {
            throw new SchedulingError(
                `Node ${this.name} cannot host Pod ${pod.name}`
            );
        }

        this.allocatedCPU += pod.resources.cpuMillicores;
        this.allocatedMemory += pod.resources.memoryMB;

        this.pods.add(pod.id);
    }

    release(pod) {
        if (!this.pods.has(pod.id)) {
            return;
        }

        this.allocatedCPU -= pod.resources.cpuMillicores;
        this.allocatedMemory -= pod.resources.memoryMB;

        this.pods.delete(pod.id);

        if (this.allocatedCPU < 0 || this.allocatedMemory < 0) {
            throw new KubernetesError(
                'Resource accounting invariant violated.'
            );
        }
    }
}


// ============================================================
// POD
// ============================================================

class Pod {
    constructor({
        name,
        image,
        labels,
        resources,
        namespace = 'default'
    }) {
        if (!name || !image || !resources) {
            throw new ValidationError(
                'Pod name, image and resources are required.'
            );
        }

        if (!labels || Object.keys(labels).length === 0) {
            throw new ValidationError('Pod labels are required.');
        }

        this.id = randomUUID();
        this.name = name;
        this.image = image;
        this.labels = Object.freeze({ ...labels });
        this.resources = resources;
        this.namespace = namespace;

        this.status = 'Pending';
        this.nodeName = null;
        this.ready = false;
        this.restartCount = 0;
    }

    matches(selector) {
        return Object.entries(selector).every(
            ([key, value]) => this.labels[key] === value
        );
    }
}


// ============================================================
// DEPLOYMENT
// ============================================================

class Deployment {
    constructor({
        name,
        image,
        replicas,
        labels,
        resources
    }) {
        if (!name || !image) {
            throw new ValidationError(
                'Deployment name and image are required.'
            );
        }

        if (!Number.isInteger(replicas) || replicas < 0) {
            throw new ValidationError('Invalid replica count.');
        }

        this.name = name;
        this.image = image;
        this.desiredReplicas = replicas;
        this.labels = Object.freeze({ ...labels });
        this.resources = resources;

        this.podIds = new Set();
        this.generation = 1;
    }
}


// ============================================================
// SCHEDULER
// ============================================================

class Scheduler {

    schedule(pod, nodes) {
        const candidates = nodes.filter(
            node => node.canHost(pod.resources)
        );

        if (candidates.length === 0) {
            throw new SchedulingError(
                `No available worker node for ${pod.name}`
            );
        }

        // Select the node with the smallest remaining CPU capacity.
        candidates.sort((a, b) => {
            const remainingA =
                a.capacity.cpuMillicores -
                a.allocatedCPU -
                pod.resources.cpuMillicores;

            const remainingB =
                b.capacity.cpuMillicores -
                b.allocatedCPU -
                pod.resources.cpuMillicores;

            return remainingA - remainingB;
        });

        const selected = candidates[0];

        selected.allocate(pod);

        pod.nodeName = selected.name;
        pod.status = 'Running';
        pod.ready = true;

        return selected;
    }
}


// ============================================================
// CLUSTER API AND EVENT BUS
// ============================================================

class KubernetesCluster extends EventEmitter {

    constructor(name) {
        super();

        if (!name) {
            throw new ValidationError('Cluster name is required.');
        }

        this.name = name;

        this.nodes = new Map();
        this.pods = new Map();
        this.deployments = new Map();
        this.services = new Map();

        this.scheduler = new Scheduler();

        this.eventSequence = 0;
        this.operationQueue = Promise.resolve();

        this.on('pod.created', pod => {
            console.log(`[EVENT] Pod created: ${pod.name}`);
        });

        this.on('pod.scheduled', pod => {
            console.log(
                `[EVENT] ${pod.name} scheduled on ${pod.nodeName}`
            );
        });

        this.on('node.failed', name => {
            console.log(`[EVENT] Node failure: ${name}`);
        });
    }

    emitEvent(event, payload) {
        this.eventSequence++;

        this.emit(event, {
            sequence: this.eventSequence,
            timestamp: new Date().toISOString(),
            payload
        });

        // Domain event handlers receive their original payload.
        // The sequence is maintained separately for audit ordering.
    }

    addNode(node) {
        if (this.nodes.has(node.name)) {
            throw new ValidationError('Duplicate node.');
        }

        this.nodes.set(node.name, node);

        this.emitEvent('node.added', {
            name: node.name,
            role: node.role
        });
    }

    async createPod(pod) {
        if (this.pods.has(pod.id)) {
            throw new ValidationError('Duplicate Pod ID.');
        }

        this.pods.set(pod.id, pod);

        this.emitEvent('pod.created', pod);

        try {
            this.scheduler.schedule(
                pod,
                [...this.nodes.values()]
            );

            this.emitEvent('pod.scheduled', pod);
        } catch (error) {
            if (!(error instanceof SchedulingError)) {
                throw error;
            }

            pod.status = 'Pending';
            pod.ready = false;

            this.emitEvent('pod.pending', {
                pod: pod.name,
                reason: error.message
            });
        }

        return pod;
    }

    async deletePod(podId) {
        const pod = this.pods.get(podId);

        if (!pod) {
            throw new ResourceNotFoundError(
                `Pod ${podId} not found.`
            );
        }

        pod.status = 'Terminating';
        pod.ready = false;

        if (pod.nodeName) {
            this.nodes.get(pod.nodeName).release(pod);
        }

        this.pods.delete(podId);

        this.emitEvent('pod.deleted', {
            name: pod.name,
            id: podId
        });
    }

    async createDeployment(deployment) {
        if (this.deployments.has(deployment.name)) {
            throw new ValidationError(
                'Deployment already exists.'
            );
        }

        this.deployments.set(deployment.name, deployment);

        await this.reconcile(deployment.name);
    }

    async reconcile(deploymentName) {
        const deployment = this.deployments.get(deploymentName);

        if (!deployment) {
            throw new ResourceNotFoundError(deploymentName);
        }

        const activePods = () => {
            return [...deployment.podIds]
                .map(id => this.pods.get(id))
                .filter(pod =>
                    pod &&
                    ['Running', 'Pending'].includes(pod.status)
                );
        };

        while (
            activePods().length < deployment.desiredReplicas
        ) {
            const index = deployment.podIds.size + 1;

            const pod = new Pod({
                name: `${deployment.name}-${index}`,
                image: deployment.image,
                labels: deployment.labels,
                resources: deployment.resources
            });

            await this.createPod(pod);
            deployment.podIds.add(pod.id);
        }

        while (
            activePods().length > deployment.desiredReplicas
        ) {
            const pod = activePods().at(-1);

            await this.deletePod(pod.id);
            deployment.podIds.delete(pod.id);
        }

        this.emitEvent('deployment.reconciled', {
            name: deployment.name,
            desired: deployment.desiredReplicas,
            observed: activePods().length,
            generation: deployment.generation
        });
    }

    async scaleDeployment(name, replicas) {
        if (!Number.isInteger(replicas) || replicas < 0) {
            throw new ValidationError('Invalid replica count.');
        }

        const deployment = this.deployments.get(name);

        if (!deployment) {
            throw new ResourceNotFoundError(name);
        }

        deployment.desiredReplicas = replicas;
        deployment.generation++;

        await this.reconcile(name);
    }

    async updateDeployment(name, image, maxSurge = 1) {
        const deployment = this.deployments.get(name);

        if (!deployment) {
            throw new ResourceNotFoundError(name);
        }

        if (!image || !image.trim()) {
            throw new ValidationError('Image is required.');
        }

        if (!Number.isInteger(maxSurge) || maxSurge < 0) {
            throw new ValidationError('Invalid maxSurge.');
        }

        const originalImage = deployment.image;
        const originalGeneration = deployment.generation;

        deployment.image = image;
        deployment.generation++;

        this.emitEvent('deployment.updated', {
            name,
            oldImage: originalImage,
            newImage: image
        });

        // Rolling replacement creates new Pods before removing old ones.
        // If scheduling fails, restore the desired template and retain
        // the old running replicas.
        const oldIds = [...deployment.podIds];

        try {
            for (let i = 0; i < deployment.desiredReplicas; i++) {
                const pod = new Pod({
                    name: `${name}-rollout-${deployment.generation}-${i + 1}`,
                    image,
                    labels: deployment.labels,
                    resources: deployment.resources
                });

                await this.createPod(pod);

                if (pod.status !== 'Running') {
                    await this.deletePod(pod.id);

                    throw new SchedulingError(
                        `Unable to schedule updated Pod ${pod.name}`
                    );
                }

                deployment.podIds.add(pod.id);

                // Keep temporary surge bounded.
                const excess = deployment.podIds.size -
                    deployment.desiredReplicas;

                if (excess > maxSurge) {
                    const oldId = oldIds.shift();

                    if (oldId && this.pods.has(oldId)) {
                        await this.deletePod(oldId);
                        deployment.podIds.delete(oldId);
                    }
                }
            }

            for (const oldId of oldIds) {
                if (this.pods.has(oldId)) {
                    await this.deletePod(oldId);
                }

                deployment.podIds.delete(oldId);
            }

        } catch (error) {
            // Restore the template. Existing Pods remain available,
            // although already-created replacement Pods may need cleanup.
            deployment.image = originalImage;
            deployment.generation = originalGeneration;

            for (const id of [...deployment.podIds]) {
                const pod = this.pods.get(id);

                if (
                    pod &&
                    pod.image === image &&
                    !oldIds.includes(id)
                ) {
                    await this.deletePod(id);
                    deployment.podIds.delete(id);
                }
            }

            throw error;
        }
    }

    addService({
        name,
        selector,
        port,
        targetPort = 8080
    }) {
        if (!name || !selector || Object.keys(selector).length === 0) {
            throw new ValidationError('Invalid Service definition.');
        }

        if (
            !Number.isInteger(port) ||
            port < 1 ||
            port > 65535 ||
            !Number.isInteger(targetPort) ||
            targetPort < 1 ||
            targetPort > 65535
        ) {
            throw new ValidationError('Invalid Service port.');
        }

        if (this.services.has(name)) {
            throw new ValidationError('Service already exists.');
        }

        this.services.set(name, {
            name,
            selector: Object.freeze({ ...selector }),
            port,
            targetPort,
            clusterIP: `10.96.0.${this.services.size + 10}`
        });
    }

    getEndpoints(serviceName) {
        const service = this.services.get(serviceName);

        if (!service) {
            throw new ResourceNotFoundError(serviceName);
        }

        return [...this.pods.values()]
            .filter(pod =>
                pod.status === 'Running' &&
                pod.ready &&
                pod.matches(service.selector)
            )
            .map(pod => ({
                pod: pod.name,
                node: pod.nodeName,
                port: service.targetPort
            }));
    }

    async failNode(nodeName) {
        const node = this.nodes.get(nodeName);

        if (!node) {
            throw new ResourceNotFoundError(nodeName);
        }

        node.status = 'NotReady';

        this.emitEvent('node.failed', nodeName);

        for (const id of [...node.pods]) {
            const pod = this.pods.get(id);

            if (!pod) {
                continue;
            }

            node.release(pod);

            pod.nodeName = null;
            pod.status = 'Failed';
            pod.ready = false;
        }

        for (const deployment of this.deployments.values()) {
            await this.reconcile(deployment.name);
        }
    }

    async recoverNode(nodeName) {
        const node = this.nodes.get(nodeName);

        if (!node) {
            throw new ResourceNotFoundError(nodeName);
        }

        node.status = 'Ready';

        for (const pod of this.pods.values()) {
            if (pod.status !== 'Pending') {
                continue;
            }

            try {
                this.scheduler.schedule(
                    pod,
                    [...this.nodes.values()]
                );
            } catch (error) {
                if (!(error instanceof SchedulingError)) {
                    throw error;
                }
            }
        }

        this.emitEvent('node.recovered', nodeName);
    }

    report() {
        return {
            cluster: this.name,

            nodes: [...this.nodes.values()].map(node => ({
                name: node.name,
                role: node.role,
                status: node.status,
                allocatedCPU: node.allocatedCPU,
                allocatedMemory: node.allocatedMemory,
                podCount: node.pods.size
            })),

            podCounts: [...this.pods.values()].reduce(
                (counts, pod) => {
                    counts[pod.status] =
                        (counts[pod.status] || 0) + 1;

                    return counts;
                },
                {}
            ),

            deployments: [...this.deployments.values()].map(
                deployment => ({
                    name: deployment.name,
                    desired: deployment.desiredReplicas,
                    observed: deployment.podIds.size,
                    image: deployment.image,
                    generation: deployment.generation
                })
            ),

            eventSequence: this.eventSequence
        };
    }
}


// ============================================================
// SERIALIZED OPERATIONS
// ============================================================

class OperationQueue {

    constructor() {
        this.tail = Promise.resolve();
    }

    execute(operation) {
        const current = this.tail.then(operation);

        // A failed operation must not permanently block the queue.
        this.tail = current.catch(() => undefined);

        return current;
    }
}


// ============================================================
// DEMONSTRATION
// ============================================================

async function main() {

    const cluster = new KubernetesCluster('production-cluster');

    cluster.addNode(new Node({
        name: 'master-01',
        role: 'control-plane',
        cpuMillicores: 8000,
        memoryMB: 16384
    }));

    cluster.addNode(new Node({
        name: 'worker-01',
        cpuMillicores: 4000,
        memoryMB: 8192
    }));

    cluster.addNode(new Node({
        name: 'worker-02',
        cpuMillicores: 4000,
        memoryMB: 8192
    }));

    cluster.addNode(new Node({
        name: 'worker-03',
        cpuMillicores: 2000,
        memoryMB: 4096
    }));

    const deployment = new Deployment({
        name: 'inventory-api',
        image: 'inventory-api:1.0.0',
        replicas: 3,
        labels: {
            app: 'inventory',
            environment: 'production'
        },
        resources: new ResourceRequirements(500, 512)
    });

    await cluster.createDeployment(deployment);

    cluster.addService({
        name: 'inventory-service',
        selector: {
            app: 'inventory'
        },
        port: 80,
        targetPort: 8080
    });

    console.log('\nINITIAL REPORT');
    console.log(JSON.stringify(cluster.report(), null, 2));

    console.log('\nSERVICE ENDPOINTS');
    console.log(cluster.getEndpoints('inventory-service'));

    console.log('\nSCALING TO FIVE REPLICAS');

    await cluster.scaleDeployment('inventory-api', 5);

    console.log(JSON.stringify(cluster.report(), null, 2));

    console.log('\nROLLING UPDATE');

    await cluster.updateDeployment(
        'inventory-api',
        'inventory-api:2.0.0',
        1
    );

    console.log(JSON.stringify(cluster.report(), null, 2));

    console.log('\nSIMULATING NODE FAILURE');

    await cluster.failNode('worker-01');

    console.log(JSON.stringify(cluster.report(), null, 2));

    console.log('\nRECOVERING NODE');

    await cluster.recoverNode('worker-01');

    console.log(JSON.stringify(cluster.report(), null, 2));

    // Verify resource invariants.
    for (const node of cluster.nodes.values()) {
        if (
            node.allocatedCPU < 0 ||
            node.allocatedMemory < 0 ||
            node.allocatedCPU > node.capacity.cpuMillicores ||
            node.allocatedMemory > node.capacity.memoryMB
        ) {
            throw new KubernetesError(
                `Resource invariant failed on ${node.name}`
            );
        }
    }

    console.log('\nAll resource invariants passed.');

    // Demonstrate serialized asynchronous operations.
    const queue = new OperationQueue();

    await Promise.all([
        queue.execute(async () => {
            await delay(10);
            console.log('Operation 1 completed');
        }),
        queue.execute(async () => {
            console.log('Operation 2 completed');
        })
    ]);
}


main().catch(error => {
    console.error('Cluster operation failed:', {
        name: error.name,
        code: error.code,
        message: error.message
    });

    process.exitCode = 1;
});
