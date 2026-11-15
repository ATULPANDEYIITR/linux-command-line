"use strict";

/*
 * Introduction to Containers
 *
 * Event-driven container platform simulator.
 *
 * Features:
 * - Application image packaging
 * - Image layers and SHA-256 digests
 * - Image registry
 * - Container lifecycle
 * - Resource scheduling
 * - Port allocation
 * - Environment configuration
 * - Isolation policies
 * - Health monitoring
 * - Asynchronous deployment
 * - Restart handling
 * - Operational event history
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const EventEmitter = require("node:events");

class ContainerError extends Error {}
class ValidationError extends ContainerError {}
class SecurityError extends ContainerError {}
class ResourceError extends ContainerError {}
class StateError extends ContainerError {}

const State = Object.freeze({
    CREATED: "created",
    RUNNING: "running",
    STOPPED: "stopped",
    FAILED: "failed",
    REMOVED: "removed"
});

const Health = Object.freeze({
    STARTING: "starting",
    HEALTHY: "healthy",
    UNHEALTHY: "unhealthy"
});

const RestartPolicy = Object.freeze({
    NO: "no",
    ALWAYS: "always",
    ON_FAILURE: "on-failure"
});

function sha256(value) {
    return crypto
        .createHash("sha256")
        .update(value)
        .digest("hex");
}

function validatePort(port) {
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new ValidationError(`Invalid port: ${port}`);
    }
}

function validateIdentifier(value) {
    if (
        typeof value !== "string" ||
        !/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$/.test(value)
    ) {
        throw new ValidationError("Invalid resource identifier.");
    }
}

class ImageLayer {
    constructor(instruction, content) {
        if (!instruction || !content) {
            throw new ValidationError("Layer instruction and content required.");
        }

        this.instruction = instruction;
        this.content = content;
        this.digest = sha256(`${instruction}:${content}`);

        Object.freeze(this);
    }
}

class ContainerImage {
    constructor({
        name,
        tag,
        layers,
        entrypoint,
        exposedPorts = [],
        user = "app",
        vulnerabilities = 0
    }) {
        validateIdentifier(name);
        validateIdentifier(tag);

        if (!Array.isArray(layers) || layers.length === 0) {
            throw new ValidationError("Image requires at least one layer.");
        }

        if (!Array.isArray(entrypoint) || entrypoint.length === 0) {
            throw new ValidationError("Entrypoint is required.");
        }

        if (!Array.isArray(exposedPorts)) {
            throw new ValidationError("Exposed ports must be an array.");
        }

        exposedPorts.forEach(validatePort);

        if (!Number.isInteger(vulnerabilities) || vulnerabilities < 0) {
            throw new ValidationError("Invalid vulnerability count.");
        }

        this.name = name;
        this.tag = tag;
        this.layers = Object.freeze([...layers]);
        this.entrypoint = Object.freeze([...entrypoint]);
        this.exposedPorts = Object.freeze([...new Set(exposedPorts)]);
        this.user = user;
        this.vulnerabilities = vulnerabilities;

        Object.freeze(this);
    }

    get reference() {
        return `${this.name}:${this.tag}`;
    }

    get digest() {
        return sha256(this.layers.map(layer => layer.digest).join("|"));
    }

    get sizeBytes() {
        return this.layers.reduce(
            (total, layer) =>
                total + Buffer.byteLength(layer.content),
            0
        );
    }
}

class ImageRegistry {
    #images = new Map();

    push(image) {
        if (!(image instanceof ContainerImage)) {
            throw new ValidationError("Expected ContainerImage.");
        }

        this.#images.set(image.reference, {
            image,
            digest: image.digest
        });

        return image.digest;
    }

    async pull(reference) {
        const record = this.#images.get(reference);

        if (!record) {
            throw new ContainerError(`Image not found: ${reference}`);
        }

        // Simulate asynchronous registry access.
        await new Promise(resolve => setImmediate(resolve));

        if (record.digest !== record.image.digest) {
            throw new SecurityError("Image digest mismatch.");
        }

        return record.image;
    }

    list() {
        return [...this.#images.values()].map(record => ({
            reference: record.image.reference,
            digest: record.digest
        }));
    }
}

class ResourceScheduler {
    constructor({ cpu = 8, memoryMB = 4096 } = {}) {
        if (cpu <= 0 || memoryMB <= 0) {
            throw new ValidationError("Host resources must be positive.");
        }

        this.capacity = { cpu, memoryMB };
        this.allocations = new Map();
    }

    allocate(id, resources) {
        const { cpu, memoryMB } = resources;

        if (
            !Number.isFinite(cpu) ||
            cpu <= 0 ||
            !Number.isInteger(memoryMB) ||
            memoryMB < 16
        ) {
            throw new ValidationError("Invalid resource request.");
        }

        const allocated = [...this.allocations.values()];

        const usedCPU = allocated.reduce((s, r) => s + r.cpu, 0);
        const usedMemory = allocated.reduce((s, r) => s + r.memoryMB, 0);

        if (usedCPU + cpu > this.capacity.cpu) {
            throw new ResourceError("Insufficient CPU capacity.");
        }

        if (usedMemory + memoryMB > this.capacity.memoryMB) {
            throw new ResourceError("Insufficient memory capacity.");
        }

        this.allocations.set(id, { cpu, memoryMB });
    }

    release(id) {
        this.allocations.delete(id);
    }

    usage() {
        return [...this.allocations.values()].reduce(
            (result, resource) => ({
                cpu: result.cpu + resource.cpu,
                memoryMB: result.memoryMB + resource.memoryMB
            }),
            { cpu: 0, memoryMB: 0 }
        );
    }
}

class PortAllocator {
    constructor() {
        this.owners = new Map();
    }

    reserve(containerId, mappings) {
        const requested = Object.values(mappings);

        requested.forEach(validatePort);

        if (new Set(requested).size !== requested.length) {
            throw new ValidationError("Duplicate host port in mappings.");
        }

        for (const port of requested) {
            const owner = this.owners.get(port);

            if (owner && owner !== containerId) {
                throw new ResourceError(`Host port ${port} is occupied.`);
            }
        }

        for (const port of requested) {
            this.owners.set(port, containerId);
        }
    }

    release(containerId) {
        for (const [port, owner] of this.owners) {
            if (owner === containerId) {
                this.owners.delete(port);
            }
        }
    }
}

class Container extends EventEmitter {
    constructor(image, configuration, scheduler, ports) {
        super();

        this.id = crypto.randomUUID().slice(0, 12);
        this.image = image;
        this.configuration = configuration;
        this.scheduler = scheduler;
        this.ports = ports;

        this.state = State.CREATED;
        this.health = Health.STARTING;
        this.restartCount = 0;
        this.createdAt = new Date().toISOString();
        this.startedAt = null;
        this.history = [];
    }

    record(event, details = {}) {
        const entry = {
            timestamp: new Date().toISOString(),
            containerId: this.id,
            event,
            state: this.state,
            details
        };

        this.history.push(entry);
        this.emit("lifecycle", entry);
    }

    start() {
        if (![State.CREATED, State.STOPPED].includes(this.state)) {
            throw new StateError(`Cannot start from ${this.state}.`);
        }

        this.scheduler.allocate(this.id, this.configuration.resources);

        try {
            this.ports.reserve(
                this.id,
                this.configuration.portMappings
            );
        } catch (error) {
            this.scheduler.release(this.id);
            throw error;
        }

        this.state = State.RUNNING;
        this.health = Health.STARTING;
        this.startedAt = new Date().toISOString();

        this.record("container.started", {
            image: this.image.reference
        });
    }

    markHealthy() {
        if (this.state !== State.RUNNING) {
            throw new StateError("Container is not running.");
        }

        this.health = Health.HEALTHY;
        this.record("health.healthy");
    }

    markUnhealthy() {
        if (this.state !== State.RUNNING) {
            throw new StateError("Container is not running.");
        }

        this.health = Health.UNHEALTHY;
        this.record("health.unhealthy");
    }

    stop() {
        if (this.state !== State.RUNNING) {
            throw new StateError("Only running containers can stop.");
        }

        this.state = State.STOPPED;
        this.health = Health.UNHEALTHY;

        this.scheduler.release(this.id);
        this.ports.release(this.id);

        this.record("container.stopped");
    }

    fail(reason) {
        if (this.state !== State.RUNNING) {
            throw new StateError("Only running containers can fail.");
        }

        this.state = State.FAILED;
        this.health = Health.UNHEALTHY;

        this.scheduler.release(this.id);
        this.ports.release(this.id);

        this.record("container.failed", { reason });
    }

    remove() {
        if (this.state === State.RUNNING) {
            throw new StateError("Stop container before removal.");
        }

        if (this.state === State.REMOVED) {
            throw new StateError("Container already removed.");
        }

        this.state = State.REMOVED;
        this.record("container.removed");
    }

    snapshot() {
        return {
            id: this.id,
            image: this.image.reference,
            digest: this.image.digest,
            state: this.state,
            health: this.health,
            restartCount: this.restartCount,
            createdAt: this.createdAt
        };
    }
}

class ContainerPlatform extends EventEmitter {
    constructor() {
        super();

        this.registry = new ImageRegistry();
        this.scheduler = new ResourceScheduler();
        this.ports = new PortAllocator();
        this.containers = new Map();
    }

    create(image, configuration) {
        if (image.vulnerabilities > 0) {
            throw new SecurityError(
                "Image rejected by vulnerability policy."
            );
        }

        if (image.user === "root") {
            throw new SecurityError("Root-based images are prohibited.");
        }

        const {
            environment = {},
            portMappings = {},
            resources = { cpu: 1, memoryMB: 256 },
            privileged = false,
            readOnlyRootfs = true,
            restartPolicy = RestartPolicy.NO
        } = configuration;

        if (privileged) {
            throw new SecurityError("Privileged mode is prohibited.");
        }

        if (!readOnlyRootfs) {
            throw new SecurityError("Read-only root filesystem is required.");
        }

        if (!Object.values(RestartPolicy).includes(restartPolicy)) {
            throw new ValidationError("Invalid restart policy.");
        }

        for (const [key, value] of Object.entries(environment)) {
            if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
                throw new ValidationError(`Invalid environment key: ${key}`);
            }

            if (typeof value !== "string" || value.length > 4096) {
                throw new ValidationError("Invalid environment value.");
            }
        }

        for (const containerPort of Object.keys(portMappings)) {
            const port = Number(containerPort);

            validatePort(port);

            if (!image.exposedPorts.includes(port)) {
                throw new ValidationError(
                    `Image does not expose port ${port}.`
                );
            }
        }

        const container = new Container(
            image,
            {
                environment: Object.freeze({ ...environment }),
                portMappings: Object.freeze({ ...portMappings }),
                resources: Object.freeze({ ...resources }),
                restartPolicy,
                readOnlyRootfs
            },
            this.scheduler,
            this.ports
        );

        container.on("lifecycle", event => {
            this.emit("container.event", event);
        });

        this.containers.set(container.id, container);

        return container;
    }

    async deploy(reference, configuration) {
        const image = await this.registry.pull(reference);
        const container = this.create(image, configuration);

        container.start();

        return container;
    }

    restart(container) {
        if (container.state !== State.FAILED) {
            throw new StateError("Container has not failed.");
        }

        const policy = container.configuration.restartPolicy;

        if (policy === RestartPolicy.NO) {
            return false;
        }

        if (
            policy === RestartPolicy.ON_FAILURE &&
            container.restartCount >= 3
        ) {
            return false;
        }

        container.restartCount++;
        container.state = State.STOPPED;
        container.start();

        return true;
    }

    list() {
        return [...this.containers.values()]
            .filter(c => c.state !== State.REMOVED)
            .map(c => c.snapshot());
    }

    async exportAudit(filename) {
        const report = {
            generatedAt: new Date().toISOString(),
            containers: this.list(),
            resourceUsage: this.scheduler.usage()
        };

        await fs.writeFile(
            filename,
            JSON.stringify(report, null, 2),
            { mode: 0o600 }
        );
    }
}

function createApplicationImage() {
    return new ContainerImage({
        name: "inventory-api",
        tag: "1.0.0",
        layers: [
            new ImageLayer("FROM", "node:22-slim"),
            new ImageLayer("WORKDIR", "/app"),
            new ImageLayer("COPY", "package.json"),
            new ImageLayer("RUN", "npm install --omit=dev"),
            new ImageLayer("COPY", "server.js")
        ],
        entrypoint: ["node", "server.js"],
        exposedPorts: [3000],
        user: "app"
    });
}

async function main() {
    console.log("=== CONTAINER PLATFORM ===");

    const platform = new ContainerPlatform();

    platform.on("container.event", event => {
        console.log(
            `[EVENT] ${event.event}: ${event.containerId}`
        );
    });

    const image = createApplicationImage();

    const digest = platform.registry.push(image);

    console.log("\nImage reference:", image.reference);
    console.log("Image digest:", digest);
    console.log("Image layers:", image.layers.length);

    const container = await platform.deploy(
        "inventory-api:1.0.0",
        {
            environment: {
                NODE_ENV: "production",
                LOG_LEVEL: "info"
            },
            portMappings: {
                3000: 8080
            },
            resources: {
                cpu: 1,
                memoryMB: 512
            },
            restartPolicy: RestartPolicy.ON_FAILURE,
            readOnlyRootfs: true
        }
    );

    container.markHealthy();

    console.log("\nContainer:", container.snapshot());

    console.log("\nResource usage:", platform.scheduler.usage());

    container.fail("Application process exited unexpectedly");

    console.log(
        "\nRestart attempted:",
        platform.restart(container)
    );

    container.markHealthy();

    await platform.exportAudit("container-audit.json");

    console.log("\nAudit report written.");

    container.stop();
    container.remove();

    console.log("\nFinal state:", container.state);

    // Verify security policy.
    try {
        platform.create(image, {
            privileged: true
        });
    } catch (error) {
        console.log("\nExpected security rejection:", error.message);
    }

    // Verify invalid port handling.
    try {
        platform.create(image, {
            portMappings: { 9999: 8081 }
        });
    } catch (error) {
        console.log("Expected port rejection:", error.message);
    }

    console.log("\nRemaining containers:", platform.list().length);
}

main().catch(error => {
    console.error("Platform failure:", error.message);
    process.exitCode = 1;
});
