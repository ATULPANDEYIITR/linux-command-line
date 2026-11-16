"use strict";

/*
 * Docker Fundamentals: Event-Driven Container and Image Manager.
 *
 * Node.js 18+
 *
 * Features:
 * - Docker architecture modeling
 * - Image manifests and content layers
 * - Container lifecycle events
 * - Registry operations
 * - Image tagging and distribution
 * - Port and volume configuration
 * - Resource policy evaluation
 * - Asynchronous operations
 * - EventEmitter-based lifecycle notifications
 * - JSON persistence
 * - Docker CLI integration
 *
 * No third-party dependencies.
 */

const fs = require("node:fs/promises");
const { spawn } = require("node:child_process");
const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");
const path = require("node:path");

// ============================================================
// 1. CONSTANTS AND ENUMERATIONS
// ============================================================

const ContainerState = Object.freeze({
    CREATED: "created",
    RUNNING: "running",
    PAUSED: "paused",
    RESTARTING: "restarting",
    EXITED: "exited",
    DEAD: "dead"
});

const ReviewableStates = new Set([
    ContainerState.CREATED,
    ContainerState.RUNNING,
    ContainerState.PAUSED,
    ContainerState.EXITED
]);

const DockerArchitecture = Object.freeze({
    client: "Docker CLI and API client",
    daemon: "dockerd manages Docker resources",
    containerd: "Container lifecycle management",
    runtime: "runc creates isolated processes",
    buildkit: "Image build engine",
    registry: "Image storage and distribution"
});

// ============================================================
// 2. VALIDATION
// ============================================================

function validateString(value, field) {
    if (typeof value !== "string" || !value.trim()) {
        throw new TypeError(`${field} must be a non-empty string`);
    }

    if (value.length > 255 || value.includes("\0")) {
        throw new RangeError(`${field} has an invalid length or character`);
    }

    return value.trim();
}

function validateImageReference(reference) {
    reference = validateString(reference, "Image reference");

    const pattern =
        /^(?:[a-zA-Z0-9.-]+(?::\d+)?\/)?[a-z0-9]+(?:[._-][a-z0-9]+)*(?:\/[a-z0-9]+(?:[._-][a-z0-9]+)*)*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?(?:@sha256:[a-fA-F0-9]{64})?$/;

    if (!pattern.test(reference)) {
        throw new TypeError(`Invalid image reference: ${reference}`);
    }

    return reference;
}

function validatePort(port) {
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new RangeError("Port must be an integer from 1 to 65535");
    }
}

function validateResourceLimits({ cpu, memoryMB }) {
    if (!Number.isFinite(cpu) || cpu <= 0) {
        throw new RangeError("CPU limit must be positive");
    }

    if (!Number.isInteger(memoryMB) || memoryMB < 6) {
        throw new RangeError("Memory must be at least 6 MB");
    }
}

// ============================================================
// 3. IMAGE AND LAYER MODEL
// ============================================================

class ImageLayer {
    constructor(instruction, sizeMB, parentDigest = null) {
        this.instruction = validateString(
            instruction,
            "Layer instruction"
        );

        if (!Number.isFinite(sizeMB) || sizeMB < 0) {
            throw new RangeError("Layer size cannot be negative");
        }

        this.sizeMB = sizeMB;
        this.parentDigest = parentDigest;

        this.digest = crypto
            .createHash("sha256")
            .update(
                JSON.stringify({
                    instruction: this.instruction,
                    sizeMB: this.sizeMB,
                    parentDigest
                })
            )
            .digest("hex");
    }
}

class DockerImage {
    constructor(repository, tag, layers, options = {}) {
        this.repository = validateString(repository, "Repository");
        this.tag = validateString(tag, "Tag");

        validateImageReference(`${this.repository}:${this.tag}`);

        if (!Array.isArray(layers) || layers.length === 0) {
            throw new TypeError("An image requires at least one layer");
        }

        if (!layers.every(layer => layer instanceof ImageLayer)) {
            throw new TypeError("Invalid image layer collection");
        }

        const digests = layers.map(layer => layer.digest);

        if (new Set(digests).size !== digests.length) {
            throw new Error("Duplicate image layers are not allowed");
        }

        this.layers = Object.freeze([...layers]);
        this.createdAt = new Date().toISOString();
        this.source = options.source ?? "local";

        this.digest = crypto
            .createHash("sha256")
            .update(digests.join(":"))
            .digest("hex");
    }

    get reference() {
        return `${this.repository}:${this.tag}`;
    }

    get sizeMB() {
        return this.layers.reduce(
            (total, layer) => total + layer.sizeMB,
            0
        );
    }

    manifest() {
        return {
            reference: this.reference,
            digest: this.digest,
            layers: this.layers.map(layer => ({
                digest: layer.digest,
                instruction: layer.instruction,
                sizeMB: layer.sizeMB
            })),
            totalSizeMB: this.sizeMB,
            createdAt: this.createdAt
        };
    }
}

// ============================================================
// 4. IMAGE STORE
// ============================================================

class ImageStore {
    #images = new Map();

    add(image) {
        if (!(image instanceof DockerImage)) {
            throw new TypeError("Expected a DockerImage");
        }

        this.#images.set(image.reference, image);
    }

    get(reference) {
        const image = this.#images.get(reference);

        if (!image) {
            throw new Error(`Local image not found: ${reference}`);
        }

        return image;
    }

    has(reference) {
        return this.#images.has(reference);
    }

    remove(reference) {
        if (!this.#images.delete(reference)) {
            throw new Error(`Image does not exist: ${reference}`);
        }
    }

    list() {
        return Array.from(this.#images.values());
    }

    get size() {
        return this.#images.size;
    }
}

// ============================================================
// 5. REGISTRY
// ============================================================

class ImageRegistry {
    #images = new Map();
    #sessions = new Set();

    constructor(hostname) {
        this.hostname = validateString(hostname, "Registry hostname");
    }

    login(username, token) {
        validateString(username, "Username");
        validateString(token, "Authentication token");

        // The example records a session identity, not the token.
        this.#sessions.add(username);
    }

    logout(username) {
        this.#sessions.delete(username);
    }

    push(image, username) {
        if (!this.#sessions.has(username)) {
            throw new Error("Registry authentication required");
        }

        const remoteReference =
            `${this.hostname}/${image.reference}`;

        this.#images.set(remoteReference, image);

        return remoteReference;
    }

    async pull(reference) {
        await Promise.resolve();

        const image = this.#images.get(reference);

        if (!image) {
            throw new Error(`Registry image not found: ${reference}`);
        }

        return image;
    }

    list() {
        return Array.from(this.#images.keys());
    }
}

// ============================================================
// 6. CONTAINER RESOURCE POLICY
// ============================================================

class ResourcePolicy {
    constructor({ cpu = 1, memoryMB = 512, maxPorts = 20 } = {}) {
        validateResourceLimits({ cpu, memoryMB });

        if (!Number.isInteger(maxPorts) || maxPorts < 1) {
            throw new RangeError("Invalid maximum port count");
        }

        this.cpu = cpu;
        this.memoryMB = memoryMB;
        this.maxPorts = maxPorts;
    }

    evaluate(configuration) {
        const errors = [];

        try {
            validateResourceLimits({
                cpu: configuration.cpu,
                memoryMB: configuration.memoryMB
            });
        } catch (error) {
            errors.push(error.message);
        }

        const ports = configuration.ports ?? {};

        if (Object.keys(ports).length > this.maxPorts) {
            errors.push("Maximum port mapping count exceeded");
        }

        for (const [host, container] of Object.entries(ports)) {
            try {
                validatePort(Number(host));
                validatePort(container);
            } catch (error) {
                errors.push(error.message);
            }
        }

        if (configuration.memoryMB > this.memoryMB) {
            errors.push("Memory allocation exceeds policy");
        }

        if (configuration.cpu > this.cpu) {
            errors.push("CPU allocation exceeds policy");
        }

        return {
            allowed: errors.length === 0,
            errors
        };
    }
}

// ============================================================
// 7. CONTAINER
// ============================================================

class DockerContainer extends EventEmitter {
    constructor({
        name,
        image,
        environment = {},
        ports = {},
        volumes = {},
        cpu = 1,
        memoryMB = 512
    }) {
        super();

        this.name = validateString(name, "Container name");

        if (!(image instanceof DockerImage)) {
            throw new TypeError("A valid image is required");
        }

        this.id = crypto.randomUUID();
        this.image = image;
        this.environment = Object.freeze({ ...environment });
        this.ports = Object.freeze({ ...ports });
        this.volumes = Object.freeze({ ...volumes });

        this.cpu = cpu;
        this.memoryMB = memoryMB;

        this.state = ContainerState.CREATED;
        this.restartCount = 0;
        this.createdAt = new Date().toISOString();

        this.#validateConfiguration();
    }

    #validateConfiguration() {
        validateResourceLimits({
            cpu: this.cpu,
            memoryMB: this.memoryMB
        });

        for (const [host, container] of Object.entries(this.ports)) {
            validatePort(Number(host));
            validatePort(container);
        }

        for (const [key, value] of Object.entries(this.environment)) {
            if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
                throw new TypeError(`Invalid environment key: ${key}`);
            }

            if (typeof value !== "string" || value.includes("\0")) {
                throw new TypeError(`Invalid environment value: ${key}`);
            }
        }
    }

    #transition(expected, next) {
        if (this.state !== expected) {
            throw new Error(
                `Invalid transition: ${this.state} -> ${next}`
            );
        }

        const previous = this.state;
        this.state = next;

        this.emit("stateChanged", {
            containerId: this.id,
            name: this.name,
            previous,
            current: next,
            timestamp: new Date().toISOString()
        });
    }

    start() {
        if (
            this.state !== ContainerState.CREATED &&
            this.state !== ContainerState.EXITED
        ) {
            throw new Error("Container cannot be started");
        }

        this.#transition(this.state, ContainerState.RUNNING);
    }

    pause() {
        this.#transition(
            ContainerState.RUNNING,
            ContainerState.PAUSED
        );
    }

    unpause() {
        this.#transition(
            ContainerState.PAUSED,
            ContainerState.RUNNING
        );
    }

    stop() {
        if (
            this.state !== ContainerState.RUNNING &&
            this.state !== ContainerState.PAUSED
        ) {
            throw new Error("Container cannot be stopped");
        }

        this.#transition(this.state, ContainerState.EXITED);
    }

    async restart() {
        if (this.state === ContainerState.DEAD) {
            throw new Error("Dead containers cannot restart");
        }

        if (this.state === ContainerState.RUNNING) {
            this.stop();
        }

        if (this.state === ContainerState.PAUSED) {
            this.stop();
        }

        this.#transition(
            ContainerState.EXITED,
            ContainerState.RESTARTING
        );

        await Promise.resolve();

        this.restartCount++;

        this.#transition(
            ContainerState.RESTARTING,
            ContainerState.RUNNING
        );
    }

    remove(force = false) {
        if (
            this.state === ContainerState.RUNNING ||
            this.state === ContainerState.PAUSED
        ) {
            if (!force) {
                throw new Error("Stop container before removal");
            }
        }

        const previous = this.state;
        this.state = ContainerState.DEAD;

        this.emit("stateChanged", {
            containerId: this.id,
            name: this.name,
            previous,
            current: this.state
        });
    }

    inspect() {
        return {
            id: this.id,
            name: this.name,
            image: this.image.reference,
            state: this.state,
            ports: this.ports,
            volumes: this.volumes,
            cpu: this.cpu,
            memoryMB: this.memoryMB,
            restartCount: this.restartCount
        };
    }
}

// ============================================================
// 8. DOCKER ENGINE
// ============================================================

class DockerEngine extends EventEmitter {
    #containers = new Map();
    #names = new Map();

    constructor(resourcePolicy = new ResourcePolicy()) {
        super();

        this.images = new ImageStore();
        this.policy = resourcePolicy;
    }

    addImage(image) {
        this.images.add(image);
        this.emit("imageAdded", image.manifest());
    }

    async pullImage(registry, reference) {
        const image = await registry.pull(reference);

        this.images.add(image);

        this.emit("imagePulled", {
            reference: image.reference,
            digest: image.digest
        });

        return image;
    }

    createContainer(configuration) {
        if (this.#names.has(configuration.name)) {
            throw new Error("Container name already exists");
        }

        const image = this.images.get(configuration.image);

        const evaluation = this.policy.evaluate({
            cpu: configuration.cpu ?? 1,
            memoryMB: configuration.memoryMB ?? 512,
            ports: configuration.ports ?? {}
        });

        if (!evaluation.allowed) {
            throw new Error(evaluation.errors.join("; "));
        }

        const container = new DockerContainer({
            ...configuration,
            image
        });

        container.on("stateChanged", event => {
            this.emit("containerStateChanged", event);
        });

        this.#containers.set(container.id, container);
        this.#names.set(container.name, container.id);

        this.emit("containerCreated", container.inspect());

        return container;
    }

    getContainer(name) {
        const id = this.#names.get(name);

        if (!id) {
            throw new Error(`Container not found: ${name}`);
        }

        return this.#containers.get(id);
    }

    removeContainer(name, force = false) {
        const container = this.getContainer(name);

        container.remove(force);

        this.#containers.delete(container.id);
        this.#names.delete(name);

        this.emit("containerRemoved", {
            id: container.id,
            name
        });
    }

    listContainers({ all = true } = {}) {
        return Array.from(this.#containers.values())
            .filter(container =>
                all || container.state === ContainerState.RUNNING
            )
            .map(container => container.inspect());
    }

    get inventory() {
        return {
            images: this.images.list().map(image => image.manifest()),
            containers: this.listContainers()
        };
    }
}

// ============================================================
// 9. PERSISTENCE
// ============================================================

class InventoryRepository {
    static async save(engine, filename) {
        const destination = path.resolve(filename);
        const temporary = `${destination}.tmp`;

        await fs.writeFile(
            temporary,
            JSON.stringify(engine.inventory, null, 2),
            { encoding: "utf8", mode: 0o600 }
        );

        // Rename provides an atomic replacement on the same filesystem.
        await fs.rename(temporary, destination);
    }

    static async read(filename) {
        const raw = await fs.readFile(filename, "utf8");
        const inventory = JSON.parse(raw);

        if (
            !inventory ||
            !Array.isArray(inventory.images) ||
            !Array.isArray(inventory.containers)
        ) {
            throw new Error("Invalid inventory document");
        }

        return inventory;
    }
}

// ============================================================
// 10. DOCKER CLI WRAPPER
// ============================================================

function executeDocker(args, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
        if (!Array.isArray(args) || args.length === 0) {
            reject(new TypeError("Docker arguments are required"));
            return;
        }

        if (!args.every(arg => typeof arg === "string")) {
            reject(new TypeError("Arguments must be strings"));
            return;
        }

        const child = spawn("docker", args, {
            shell: false,
            stdio: ["ignore", "pipe", "pipe"],
            windowsHide: true
        });

        let stdout = "";
        let stderr = "";
        let settled = false;

        const timeout = setTimeout(() => {
            child.kill();
            settled = true;
            reject(new Error("Docker command timed out"));
        }, timeoutMs);

        child.stdout.setEncoding("utf8");
        child.stderr.setEncoding("utf8");

        child.stdout.on("data", chunk => {
            stdout += chunk;
        });

        child.stderr.on("data", chunk => {
            stderr += chunk;
        });

        child.on("error", error => {
            if (!settled) {
                settled = true;
                clearTimeout(timeout);
                reject(error);
            }
        });

        child.on("close", code => {
            if (settled) return;

            settled = true;
            clearTimeout(timeout);

            if (code !== 0) {
                reject(new Error(stderr || `Docker exit code ${code}`));
                return;
            }

            resolve(stdout.trim());
        });
    });
}

// ============================================================
// 11. PRACTICAL DEMONSTRATION
// ============================================================

async function demonstrate() {
    console.log("DOCKER ARCHITECTURE");

    for (const [component, responsibility] of Object.entries(
        DockerArchitecture
    )) {
        console.log(`${component}: ${responsibility}`);
    }

    const base = new ImageLayer(
        "FROM python:3.13-slim",
        45
    );

    const dependencies = new ImageLayer(
        "RUN install application dependencies",
        18,
        base.digest
    );

    const application = new ImageLayer(
        "COPY application files",
        4,
        dependencies.digest
    );

    const image = new DockerImage(
        "training/web-api",
        "1.0.0",
        [base, dependencies, application],
        { source: "built" }
    );

    const registry = new ImageRegistry("registry.example.com");

    registry.login("developer", "demo-token");

    const remote = registry.push(image, "developer");

    console.log("\nREGISTRY PUSH:", remote);

    const engine = new DockerEngine(
        new ResourcePolicy({
            cpu: 2,
            memoryMB: 1024,
            maxPorts: 10
        })
    );

    engine.on("containerStateChanged", event => {
        console.log(
            `EVENT: ${event.name}: ${event.previous} -> ${event.current}`
        );
    });

    engine.addImage(await registry.pull(remote));

    const container = engine.createContainer({
        name: "training-api",
        image: image.reference,
        environment: {
            APP_ENV: "development",
            PORT: "8000"
        },
        ports: {
            8080: 8000
        },
        volumes: {
            "/host/data": "/app/data"
        },
        cpu: 1.5,
        memoryMB: 768
    });

    container.start();
    container.pause();
    container.unpause();

    await container.restart();

    console.log("\nCONTAINER INSPECTION");
    console.log(JSON.stringify(container.inspect(), null, 2));

    container.stop();

    console.log("\nIMAGE INVENTORY");
    console.log(JSON.stringify(engine.images.list().map(
        item => item.manifest()
    ), null, 2));

    console.log("\nRUNNING CONTAINERS");
    console.log(engine.listContainers({ all: false }));

    console.log("\nFULL INVENTORY");
    console.log(JSON.stringify(engine.inventory, null, 2));

    try {
        engine.createContainer({
            name: "invalid-api",
            image: image.reference,
            cpu: 5,
            memoryMB: 4096
        });
    } catch (error) {
        console.log("\nEXPECTED POLICY FAILURE:", error.message);
    }
}

// ============================================================
// 12. TESTS
// ============================================================

async function runTests() {
    const image = new DockerImage(
        "test/application",
        "1.0",
        [new ImageLayer("Base image", 20)]
    );

    const engine = new DockerEngine();
    engine.addImage(image);

    const container = engine.createContainer({
        name: "test-container",
        image: image.reference,
        cpu: 1,
        memoryMB: 256,
        ports: { 8080: 80 }
    });

    container.start();
    console.assert(
        container.state === ContainerState.RUNNING,
        "Start transition failed"
    );

    container.pause();
    console.assert(
        container.state === ContainerState.PAUSED,
        "Pause transition failed"
    );

    container.unpause();
    await container.restart();

    console.assert(
        container.restartCount === 1,
        "Restart count is incorrect"
    );

    container.stop();

    let rejected = false;

    try {
        container.pause();
    } catch {
        rejected = true;
    }

    console.assert(rejected, "Invalid transition was accepted");

    rejected = false;

    try {
        validatePort(90000);
    } catch {
        rejected = true;
    }

    console.assert(rejected, "Invalid port was accepted");

    rejected = false;

    try {
        engine.createContainer({
            name: "invalid",
            image: image.reference,
            cpu: 4,
            memoryMB: 2048
        });
    } catch {
        rejected = true;
    }

    console.assert(rejected, "Resource policy was bypassed");

    console.log("\nAll JavaScript tests completed.");
}

// ============================================================
// 13. MAIN
// ============================================================

async function main() {
    const command = process.argv[2] ?? "demo";

    if (command === "demo") {
        await demonstrate();
    } else if (command === "test") {
        await runTests();
    } else if (command === "real") {
        console.log("DOCKER CLIENT VERSION");
        console.log(await executeDocker(["version", "--format", "{{.Client.Version}}"]));

        console.log("\nDOCKER IMAGES");
        console.log(await executeDocker(["images"]));

        console.log("\nDOCKER CONTAINERS");
        console.log(await executeDocker(["ps", "-a"]));

        console.log("\nDOCKER SERVER VERSION");
        console.log(await executeDocker(["info", "--format", "{{.ServerVersion}}"]));
    } else {
        throw new Error("Usage: node docker_fundamentals.js [demo|test|real]");
    }
}

if (require.main === module) {
    main().catch(error => {
        console.error("Execution failed:", error.message);
        process.exitCode = 1;
    });
}

module.exports = {
    ImageLayer,
    DockerImage,
    ImageStore,
    ImageRegistry,
    DockerContainer,
    ResourcePolicy,
    DockerEngine,
    InventoryRepository,
    ContainerState,
    validateImageReference,
    executeDocker
};
