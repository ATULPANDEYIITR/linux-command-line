"use strict";

/**
 * Docker Container Operations and Policy Engine
 *
 * Runtime: Node.js 18+
 *
 * Demonstrates:
 * - Event-driven container lifecycle
 * - Asynchronous Docker CLI operations
 * - Container state transitions
 * - Environment configuration
 * - Port and volume validation
 * - Network management
 * - Health checks
 * - Resource policies
 * - Failure recovery
 *
 * Usage:
 *   node docker_manager.js test
 *   node docker_manager.js inventory
 *   node docker_manager.js demo
 *   node docker_manager.js cleanup
 */

const { spawn } = require("node:child_process");
const { EventEmitter } = require("node:events");
const os = require("node:os");

const STATES = Object.freeze({
    CREATED: "created",
    RUNNING: "running",
    PAUSED: "paused",
    RESTARTING: "restarting",
    EXITED: "exited",
    DEAD: "dead"
});

const ALLOWED_TRANSITIONS = Object.freeze({
    created: ["running", "exited", "dead"],
    running: ["paused", "restarting", "exited", "dead"],
    paused: ["running", "exited", "dead"],
    restarting: ["running", "exited", "dead"],
    exited: ["running", "dead"],
    dead: []
});

class DockerError extends Error {
    constructor(message, code = "DOCKER_ERROR") {
        super(message);
        this.name = "DockerError";
        this.code = code;
    }
}

class ValidationError extends DockerError {
    constructor(message) {
        super(message, "VALIDATION_ERROR");
        this.name = "ValidationError";
    }
}

class ContainerStateMachine extends EventEmitter {
    constructor(containerId, initialState = STATES.CREATED) {
        super();

        this.containerId = containerId;
        this.state = initialState;
        this.history = [{
            state: initialState,
            timestamp: new Date().toISOString()
        }];
    }

    transition(nextState, metadata = {}) {
        const allowed = ALLOWED_TRANSITIONS[this.state];

        if (!allowed || !allowed.includes(nextState)) {
            throw new DockerError(
                `Invalid transition: ${this.state} -> ${nextState}`,
                "INVALID_TRANSITION"
            );
        }

        const previousState = this.state;
        this.state = nextState;

        const event = Object.freeze({
            containerId: this.containerId,
            previousState,
            currentState: nextState,
            timestamp: new Date().toISOString(),
            metadata
        });

        this.history.push(event);
        this.emit("stateChanged", event);

        return event;
    }
}

class ContainerConfig {
    constructor(options) {
        this.name = options.name;
        this.image = options.image;
        this.command = options.command || [];
        this.environment = options.environment || {};
        this.ports = options.ports || [];
        this.volumes = options.volumes || [];
        this.network = options.network || null;
        this.memory = options.memory || "128m";
        this.cpus = options.cpus ?? 0.5;
        this.restartPolicy = options.restartPolicy || "unless-stopped";

        this.validate();
    }

    validate() {
        if (
            typeof this.name !== "string" ||
            !/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$/.test(this.name)
        ) {
            throw new ValidationError("Invalid container name.");
        }

        if (
            typeof this.image !== "string" ||
            !this.image.trim() ||
            this.image.startsWith("-")
        ) {
            throw new ValidationError("Invalid Docker image.");
        }

        if (!Array.isArray(this.command)) {
            throw new ValidationError("Command must be an array.");
        }

        if (
            !Number.isFinite(this.cpus) ||
            this.cpus <= 0
        ) {
            throw new ValidationError("CPU limit must be positive.");
        }

        if (!/^\d+(?:[kKmMgG])?$/.test(this.memory)) {
            throw new ValidationError("Invalid memory limit.");
        }

        if (
            !["no", "always", "unless-stopped", "on-failure"]
                .includes(this.restartPolicy)
        ) {
            throw new ValidationError("Invalid restart policy.");
        }

        for (const [key, value] of Object.entries(this.environment)) {
            if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
                throw new ValidationError(
                    `Invalid environment variable: ${key}`
                );
            }

            if (
                typeof value !== "string" &&
                typeof value !== "number" &&
                typeof value !== "boolean"
            ) {
                throw new ValidationError(
                    `Invalid environment value for ${key}`
                );
            }

            if (String(value).includes("\0")) {
                throw new ValidationError("NUL characters are forbidden.");
            }
        }

        const hostPorts = new Set();

        for (const mapping of this.ports) {
            if (
                !Number.isInteger(mapping.host) ||
                !Number.isInteger(mapping.container) ||
                mapping.host < 1 ||
                mapping.host > 65535 ||
                mapping.container < 1 ||
                mapping.container > 65535
            ) {
                throw new ValidationError("Invalid port mapping.");
            }

            if (!["tcp", "udp"].includes(mapping.protocol || "tcp")) {
                throw new ValidationError("Invalid port protocol.");
            }

            if (hostPorts.has(mapping.host)) {
                throw new ValidationError("Duplicate host port.");
            }

            hostPorts.add(mapping.host);
        }

        for (const volume of this.volumes) {
            if (
                typeof volume !== "string" ||
                !volume.includes(":") ||
                volume.includes("\0")
            ) {
                throw new ValidationError("Invalid volume mapping.");
            }
        }
    }

    toDockerArguments() {
        const args = [
            "run",
            "-d",
            "--name", this.name,
            "--restart", this.restartPolicy,
            "--memory", this.memory,
            "--cpus", String(this.cpus)
        ];

        for (const [key, value] of Object.entries(this.environment)) {
            args.push("-e", `${key}=${value}`);
        }

        for (const port of this.ports) {
            args.push(
                "-p",
                `${port.host}:${port.container}/${port.protocol || "tcp"}`
            );
        }

        for (const volume of this.volumes) {
            args.push("-v", volume);
        }

        if (this.network) {
            args.push("--network", this.network);
        }

        args.push(this.image, ...this.command);

        return args;
    }
}

class DockerClient {
    constructor(options = {}) {
        this.binary = options.binary || "docker";
        this.timeout = options.timeout || 30000;
    }

    execute(args, options = {}) {
        if (
            !Array.isArray(args) ||
            args.some(arg => typeof arg !== "string" || arg.includes("\0"))
        ) {
            return Promise.reject(
                new ValidationError("Invalid Docker command arguments.")
            );
        }

        return new Promise((resolve, reject) => {
            const child = spawn(this.binary, args, {
                shell: false,
                windowsHide: true,
                stdio: ["ignore", "pipe", "pipe"]
            });

            let stdout = "";
            let stderr = "";
            let settled = false;

            const finish = (error, result) => {
                if (settled) return;
                settled = true;
                clearTimeout(timer);

                if (error) reject(error);
                else resolve(result);
            };

            const timer = setTimeout(() => {
                child.kill("SIGTERM");

                finish(
                    new DockerError("Docker command timed out.", "TIMEOUT")
                );
            }, options.timeout || this.timeout);

            child.stdout.setEncoding("utf8");
            child.stderr.setEncoding("utf8");

            child.stdout.on("data", chunk => {
                stdout += chunk;

                if (stdout.length > 5_000_000) {
                    child.kill("SIGTERM");
                    finish(new DockerError("Output limit exceeded."));
                }
            });

            child.stderr.on("data", chunk => {
                stderr += chunk;

                if (stderr.length > 1_000_000) {
                    child.kill("SIGTERM");
                    finish(new DockerError("Error output limit exceeded."));
                }
            });

            child.on("error", error => {
                finish(
                    new DockerError(`Unable to execute Docker: ${error.message}`)
                );
            });

            child.on("close", code => {
                if (settled) return;

                if (code !== 0) {
                    finish(
                        new DockerError(
                            stderr.trim() || `Docker exited with ${code}`,
                            "COMMAND_FAILED"
                        )
                    );
                    return;
                }

                finish(null, {
                    code,
                    stdout: stdout.trim(),
                    stderr: stderr.trim()
                });
            });
        });
    }

    async checkDaemon() {
        const result = await this.execute([
            "info",
            "--format",
            "{{.ServerVersion}}"
        ]);

        return result.stdout;
    }

    async pullImage(image) {
        return this.execute(["pull", image], {
            timeout: 300000
        });
    }

    async imageExists(image) {
        try {
            await this.execute(["image", "inspect", image]);
            return true;
        } catch {
            return false;
        }
    }

    async run(config) {
        if (!(config instanceof ContainerConfig)) {
            throw new ValidationError("ContainerConfig required.");
        }

        const result = await this.execute(
            config.toDockerArguments(),
            { timeout: 120000 }
        );

        return result.stdout;
    }

    async listContainers(all = true) {
        const args = ["ps", "--format", "{{json .}}"];

        if (all) args.push("-a");

        const result = await this.execute(args);

        if (!result.stdout) return [];

        return result.stdout
            .split("\n")
            .filter(Boolean)
            .map(line => JSON.parse(line));
    }

    async inspect(name) {
        const result = await this.execute(["inspect", name]);
        return JSON.parse(result.stdout)[0];
    }

    async stop(name, timeout = 10) {
        return this.execute([
            "stop",
            "--time",
            String(timeout),
            name
        ]);
    }

    async start(name) {
        return this.execute(["start", name]);
    }

    async restart(name) {
        return this.execute(["restart", name]);
    }

    async pause(name) {
        return this.execute(["pause", name]);
    }

    async unpause(name) {
        return this.execute(["unpause", name]);
    }

    async remove(name, force = false) {
        const args = ["rm"];

        if (force) args.push("-f");

        args.push(name);

        return this.execute(args);
    }

    async logs(name, tail = 100) {
        if (!Number.isInteger(tail) || tail < 1 || tail > 10000) {
            throw new ValidationError("Invalid log limit.");
        }

        const result = await this.execute([
            "logs",
            "--tail",
            String(tail),
            name
        ]);

        return result.stdout + "\n" + result.stderr;
    }

    async createNetwork(name) {
        return this.execute([
            "network",
            "create",
            "--driver",
            "bridge",
            name
        ]);
    }

    async createVolume(name) {
        return this.execute(["volume", "create", name]);
    }

    async stats(name) {
        const result = await this.execute([
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            name
        ]);

        return JSON.parse(result.stdout);
    }
}

class ContainerService extends EventEmitter {
    constructor(client) {
        super();
        this.client = client;
        this.registry = new Map();
    }

    async deploy(config) {
        if (this.registry.has(config.name)) {
            throw new DockerError("Container already registered.");
        }

        const stateMachine = new ContainerStateMachine(config.name);

        stateMachine.on("stateChanged", event => {
            this.emit("containerStateChanged", event);
        });

        this.registry.set(config.name, stateMachine);

        try {
            if (!(await this.client.imageExists(config.image))) {
                this.emit("imagePullStarted", config.image);
                await this.client.pullImage(config.image);
                this.emit("imagePullCompleted", config.image);
            }

            const containerId = await this.client.run(config);

            stateMachine.transition(STATES.RUNNING, {
                containerId
            });

            this.emit("containerStarted", {
                name: config.name,
                containerId
            });

            return containerId;
        } catch (error) {
            stateMachine.transition(STATES.DEAD, {
                reason: error.message
            });

            this.registry.delete(config.name);

            this.emit("deploymentFailed", {
                name: config.name,
                error: error.message
            });

            throw error;
        }
    }

    async stop(name) {
        const state = this.registry.get(name);

        if (!state) {
            throw new DockerError("Container is not registered.");
        }

        await this.client.stop(name);

        state.transition(STATES.EXITED);
        this.emit("containerStopped", name);
    }

    async restart(name) {
        const state = this.registry.get(name);

        if (!state) {
            throw new DockerError("Container is not registered.");
        }

        if (state.state === STATES.RUNNING) {
            state.transition(STATES.RESTARTING);
        } else if (state.state === STATES.EXITED) {
            state.transition(STATES.RUNNING);
        } else {
            throw new DockerError(
                `Cannot restart from state ${state.state}.`
            );
        }

        await this.client.restart(name);

        if (state.state === STATES.RESTARTING) {
            state.transition(STATES.RUNNING);
        }
    }

    getState(name) {
        return this.registry.get(name)?.state ?? null;
    }
}

async function runTests() {
    const config = new ContainerConfig({
        name: "test-nginx",
        image: "nginx:alpine",
        environment: {
            APP_ENV: "test"
        },
        ports: [{
            host: 8088,
            container: 80
        }]
    });

    const state = new ContainerStateMachine("test-nginx");

    state.transition(STATES.RUNNING);
    state.transition(STATES.PAUSED);
    state.transition(STATES.RUNNING);
    state.transition(STATES.EXITED);

    if (state.history.length !== 5) {
        throw new Error("State history test failed.");
    }

    let invalidTransitionRejected = false;

    try {
        state.transition(STATES.PAUSED);
    } catch {
        invalidTransitionRejected = true;
    }

    if (!invalidTransitionRejected) {
        throw new Error("Invalid transition was accepted.");
    }

    let invalidConfigRejected = false;

    try {
        new ContainerConfig({
            name: "invalid name",
            image: "nginx:alpine"
        });
    } catch {
        invalidConfigRejected = true;
    }

    if (!invalidConfigRejected) {
        throw new Error("Invalid configuration was accepted.");
    }

    console.log("All local tests passed.");
}

async function inventory(client) {
    const containers = await client.listContainers(true);

    console.log("\nDOCKER CONTAINERS");
    console.table(containers.map(container => ({
        name: container.Names,
        image: container.Image,
        status: container.Status,
        ports: container.Ports
    })));
}

async function demonstration(client) {
    const service = new ContainerService(client);

    service.on("containerStarted", event => {
        console.log("Container started:", event.name);
    });

    service.on("containerStateChanged", event => {
        console.log(
            `${event.containerId}: ${event.previousState} -> ${event.currentState}`
        );
    });

    service.on("deploymentFailed", event => {
        console.error("Deployment failed:", event.error);
    });

    const config = new ContainerConfig({
        name: "node-docker-learning",
        image: "nginx:alpine",
        environment: {
            APP_ENV: "development",
            APP_PORT: "80"
        },
        ports: [{
            host: 8089,
            container: 80,
            protocol: "tcp"
        }],
        memory: "128m",
        cpus: 0.5,
        restartPolicy: "unless-stopped"
    });

    await service.deploy(config);

    console.log("\nContainer information:");

    const details = await client.inspect(config.name);

    console.log({
        id: details.Id.substring(0, 12),
        image: details.Config.Image,
        state: details.State.Status,
        network: details.NetworkSettings.Networks
    });

    console.log("\nContainer logs:");
    console.log(await client.logs(config.name, 10));

    console.log("\nContainer statistics:");
    console.log(await client.stats(config.name));

    console.log("\nPausing container...");
    await client.pause(config.name);

    console.log("Resuming container...");
    await client.unpause(config.name);

    console.log("Stopping container...");
    await service.stop(config.name);
}

async function cleanup(client) {
    try {
        await client.remove("node-docker-learning", true);
        console.log("Demo container removed.");
    } catch (error) {
        if (error.code === "COMMAND_FAILED") {
            console.log("Demo container is not available for removal.");
            return;
        }

        throw error;
    }
}

async function main() {
    const command = process.argv[2] || "inventory";

    if (command === "test") {
        await runTests();
        return;
    }

    const client = new DockerClient();

    const version = await client.checkDaemon();
    console.log("Docker Engine:", version);

    switch (command) {
        case "inventory":
            await inventory(client);
            break;

        case "demo":
            await demonstration(client);
            break;

        case "cleanup":
            await cleanup(client);
            break;

        default:
            throw new ValidationError(
                "Use inventory, demo, cleanup or test."
            );
    }
}

main().catch(error => {
    console.error(`[${error.code || "ERROR"}] ${error.message}`);
    process.exitCode = 1;
});
