"use strict";

/*
 * Docker Compose: Event-driven service orchestration model.
 *
 * Features:
 * - Declarative service definitions
 * - Environment interpolation
 * - Dependency graph validation
 * - Concurrent startup of independent services
 * - Health conditions
 * - Networks, ports, volumes
 * - Restart policies
 * - Event-driven lifecycle
 * - Deployment failure propagation
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const EventEmitter = require("node:events");
const assert = require("node:assert/strict");

class ComposeError extends Error {}
class ConfigurationError extends ComposeError {}
class DependencyError extends ComposeError {}
class DeploymentError extends ComposeError {}

const State = Object.freeze({
    CREATED: "created",
    STARTING: "starting",
    RUNNING: "running",
    HEALTHY: "healthy",
    UNHEALTHY: "unhealthy",
    FAILED: "failed",
    STOPPED: "stopped"
});

const Condition = Object.freeze({
    STARTED: "service_started",
    HEALTHY: "service_healthy",
    COMPLETED: "service_completed_successfully"
});

const Restart = Object.freeze({
    NO: "no",
    ALWAYS: "always",
    ON_FAILURE: "on-failure",
    UNLESS_STOPPED: "unless-stopped"
});

function interpolate(value, environment) {
    return value.replace(
        /\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}/g,
        (_, key, fallback) => {
            if (Object.hasOwn(environment, key)) {
                return String(environment[key]);
            }

            if (fallback !== undefined) {
                return fallback;
            }

            throw new ConfigurationError(
                `Missing environment variable: ${key}`
            );
        }
    );
}

function normalizeService(name, config, environment) {
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/.test(name)) {
        throw new ConfigurationError(`Invalid service name: ${name}`);
    }

    if (!config.image || typeof config.image !== "string") {
        throw new ConfigurationError(`${name}: image is required`);
    }

    const ports = config.ports || [];
    const volumes = config.volumes || [];
    const dependencies = config.dependsOn || [];
    const networks = new Set(config.networks || []);

    for (const port of ports) {
        if (
            !Number.isInteger(port.host) ||
            !Number.isInteger(port.container) ||
            port.host < 1 ||
            port.host > 65535 ||
            port.container < 1 ||
            port.container > 65535
        ) {
            throw new ConfigurationError(
                `${name}: invalid port mapping`
            );
        }

        if (!["tcp", "udp"].includes(port.protocol || "tcp")) {
            throw new ConfigurationError(
                `${name}: unsupported port protocol`
            );
        }
    }

    for (const volume of volumes) {
        if (
            !volume.source ||
            !volume.target ||
            !volume.target.startsWith("/") ||
            volume.target.split("/").includes("..")
        ) {
            throw new ConfigurationError(
                `${name}: invalid volume mount`
            );
        }
    }

    const resolvedEnvironment = {};

    for (const [key, value] of Object.entries(config.environment || {})) {
        resolvedEnvironment[key] = interpolate(
            String(value),
            environment
        );
    }

    if (config.healthcheck) {
        const health = config.healthcheck;

        if (
            !health.command ||
            (health.intervalSeconds ?? 10) < 1 ||
            (health.retries ?? 3) < 1
        ) {
            throw new ConfigurationError(
                `${name}: invalid health check`
            );
        }
    }

    return {
        name,
        image: config.image,
        command: config.command || "",
        environment: Object.freeze(resolvedEnvironment),
        ports,
        volumes,
        networks,
        dependencies,
        healthcheck: config.healthcheck || null,
        restart: config.restart || Restart.NO,
        state: State.CREATED,
        attempts: 0,
        error: null
    };
}

class ComposeEngine extends EventEmitter {
    constructor(projectName, configuration, environment = process.env) {
        super();

        if (!projectName || !configuration.services) {
            throw new ConfigurationError(
                "Project name and services are required"
            );
        }

        this.projectName = projectName;
        this.networks = new Set(configuration.networks || []);
        this.volumes = new Set(configuration.volumes || []);
        this.services = new Map();

        this.environment = { ...environment };
        this.eventHistory = [];
        this.stoppedManually = false;

        for (const [name, config] of Object.entries(
            configuration.services
        )) {
            this.services.set(
                name,
                normalizeService(name, config, this.environment)
            );
        }

        this.validate();
    }

    record(type, service, details = {}) {
        const event = Object.freeze({
            timestamp: new Date().toISOString(),
            type,
            service,
            details
        });

        this.eventHistory.push(event);
        this.emit(type, event);
    }

    validate() {
        if (this.services.size === 0) {
            throw new ConfigurationError("No services defined");
        }

        const hostPorts = new Set();

        for (const service of this.services.values()) {
            for (const dependency of service.dependencies) {
                if (!this.services.has(dependency.service)) {
                    throw new DependencyError(
                        `${service.name} depends on missing service ` +
                        dependency.service
                    );
                }

                if (dependency.service === service.name) {
                    throw new DependencyError(
                        `${service.name} cannot depend on itself`
                    );
                }

                if (!Object.values(Condition).includes(
                    dependency.condition || Condition.STARTED
                )) {
                    throw new ConfigurationError(
                        "Unknown dependency condition"
                    );
                }
            }

            for (const network of service.networks) {
                if (!this.networks.has(network)) {
                    throw new ConfigurationError(
                        `Undefined network: ${network}`
                    );
                }
            }

            for (const port of service.ports) {
                const key = `${port.host}/${port.protocol || "tcp"}`;

                if (hostPorts.has(key)) {
                    throw new ConfigurationError(
                        `Host port conflict: ${key}`
                    );
                }

                hostPorts.add(key);
            }
        }

        this.topologicalOrder();
    }

    topologicalOrder() {
        const indegree = new Map();
        const children = new Map();

        for (const name of this.services.keys()) {
            indegree.set(name, 0);
            children.set(name, []);
        }

        for (const service of this.services.values()) {
            for (const dependency of service.dependencies) {
                indegree.set(
                    service.name,
                    indegree.get(service.name) + 1
                );

                children.get(dependency.service).push(service.name);
            }
        }

        const queue = [...indegree]
            .filter(([, degree]) => degree === 0)
            .map(([name]) => name);

        const result = [];

        while (queue.length) {
            const name = queue.shift();
            result.push(name);

            for (const child of children.get(name)) {
                indegree.set(child, indegree.get(child) - 1);

                if (indegree.get(child) === 0) {
                    queue.push(child);
                }
            }
        }

        if (result.length !== this.services.size) {
            throw new DependencyError(
                "Circular service dependency detected"
            );
        }

        return result;
    }

    isDependencySatisfied(dependency) {
        const service = this.services.get(dependency.service);
        const condition = dependency.condition || Condition.STARTED;

        switch (condition) {
            case Condition.STARTED:
                return [
                    State.RUNNING,
                    State.HEALTHY
                ].includes(service.state);

            case Condition.HEALTHY:
                return service.state === State.HEALTHY;

            case Condition.COMPLETED:
                return service.state === State.STOPPED;

            default:
                return false;
        }
    }

    async startService(name) {
        const service = this.services.get(name);

        if (!service) {
            throw new DeploymentError(`Unknown service: ${name}`);
        }

        if ([State.RUNNING, State.HEALTHY].includes(service.state)) {
            return;
        }

        for (const dependency of service.dependencies) {
            if (!this.isDependencySatisfied(dependency)) {
                throw new DeploymentError(
                    `${name}: dependency ${dependency.service} ` +
                    `has not satisfied ${dependency.condition}`
                );
            }
        }

        service.state = State.STARTING;
        service.attempts++;

        this.record("service-starting", name, {
            image: service.image
        });

        // Represents asynchronous container creation.
        await Promise.resolve();

        service.state = service.healthcheck
            ? State.HEALTHY
            : State.RUNNING;

        this.record("service-started", name, {
            state: service.state
        });
    }

    async up() {
        this.stoppedManually = false;
        this.record("deployment-starting", this.projectName);

        const pending = new Set(this.services.keys());

        while (pending.size) {
            const ready = [...pending].filter(name => {
                const service = this.services.get(name);

                return service.dependencies.every(dependency =>
                    this.isDependencySatisfied(dependency)
                );
            });

            if (ready.length === 0) {
                throw new DeploymentError(
                    "No service can start; dependency state is invalid"
                );
            }

            try {
                await Promise.all(
                    ready.map(name => this.startService(name))
                );
            } catch (error) {
                this.record("deployment-failed", this.projectName, {
                    error: error.message
                });

                for (const name of ready) {
                    const service = this.services.get(name);

                    if (service.state === State.STARTING) {
                        service.state = State.FAILED;
                        service.error = error.message;
                    }
                }

                throw error;
            }

            ready.forEach(name => pending.delete(name));
        }

        this.record("deployment-completed", this.projectName);
    }

    async simulateFailure(name, reason) {
        const service = this.services.get(name);

        if (!service) {
            throw new DeploymentError(`Unknown service: ${name}`);
        }

        service.state = State.FAILED;
        service.error = reason;

        this.record("service-failed", name, { reason });

        const policy = service.restart;

        if (
            policy === Restart.NO ||
            (policy === Restart.UNLESS_STOPPED && this.stoppedManually)
        ) {
            return false;
        }

        service.state = State.STARTING;
        service.attempts++;

        // A production engine must apply restart limits and backoff.
        await new Promise(resolve => setImmediate(resolve));

        service.state = service.healthcheck
            ? State.HEALTHY
            : State.RUNNING;

        service.error = null;

        this.record("service-restarted", name, {
            attempts: service.attempts,
            policy
        });

        return true;
    }

    async down() {
        this.stoppedManually = true;

        const order = this.topologicalOrder().reverse();

        for (const name of order) {
            const service = this.services.get(name);

            if (service.state !== State.STOPPED) {
                service.state = State.STOPPED;
                this.record("service-stopped", name);
            }
        }

        this.record("deployment-stopped", this.projectName);
    }

    status() {
        return Object.fromEntries(
            [...this.services].map(([name, service]) => [
                name,
                {
                    state: service.state,
                    attempts: service.attempts,
                    error: service.error
                }
            ])
        );
    }

    report() {
        return {
            project: this.projectName,
            startupOrder: this.topologicalOrder(),
            status: this.status(),
            events: this.eventHistory
        };
    }
}

async function main() {
    const configuration = {
        networks: ["frontend", "backend"],
        volumes: ["database-data"],
        services: {
            database: {
                image: "postgres:18",
                environment: {
                    POSTGRES_DB: "${DB_NAME:-inventory}",
                    POSTGRES_PASSWORD: "${DB_PASSWORD}"
                },
                networks: ["backend"],
                volumes: [
                    {
                        source: "database-data",
                        target: "/var/lib/postgresql/data"
                    }
                ],
                healthcheck: {
                    command: "pg_isready",
                    intervalSeconds: 10,
                    retries: 3
                },
                restart: Restart.UNLESS_STOPPED
            },

            cache: {
                image: "redis:8",
                networks: ["backend"],
                healthcheck: {
                    command: "redis-cli ping"
                },
                restart: Restart.ALWAYS
            },

            api: {
                image: "inventory-api:1.0",
                environment: {
                    DATABASE_HOST: "database",
                    CACHE_HOST: "cache"
                },
                ports: [
                    { host: 8000, container: 8000 }
                ],
                networks: ["frontend", "backend"],
                dependsOn: [
                    {
                        service: "database",
                        condition: Condition.HEALTHY
                    },
                    {
                        service: "cache",
                        condition: Condition.HEALTHY
                    }
                ],
                healthcheck: {
                    command: "curl -f localhost:8000/health"
                },
                restart: Restart.ON_FAILURE
            },

            web: {
                image: "inventory-web:1.0",
                ports: [
                    { host: 8080, container: 80 }
                ],
                networks: ["frontend"],
                dependsOn: [
                    {
                        service: "api",
                        condition: Condition.HEALTHY
                    }
                ],
                restart: Restart.UNLESS_STOPPED
            }
        }
    };

    const engine = new ComposeEngine(
        "inventory-platform",
        configuration,
        {
            DB_NAME: "inventory",
            DB_PASSWORD: "local-development-secret"
        }
    );

    engine.on("service-failed", event => {
        process.stderr.write(
            `Service failure: ${event.service}\n`
        );
    });

    engine.on("service-restarted", event => {
        process.stdout.write(
            `Service recovered: ${event.service}\n`
        );
    });

    await engine.up();

    assert.equal(engine.status().database.state, State.HEALTHY);
    assert.equal(engine.status().api.state, State.HEALTHY);
    assert.equal(engine.status().web.state, State.RUNNING);

    const recovered = await engine.simulateFailure(
        "api",
        "Temporary database connection failure"
    );

    assert.equal(recovered, true);
    assert.equal(engine.status().api.state, State.HEALTHY);

    console.log(JSON.stringify(engine.report(), null, 2));

    await engine.down();

    assert.ok(
        Object.values(engine.status()).every(
            service => service.state === State.STOPPED
        )
    );

    assert.throws(
        () => new ComposeEngine(
            "invalid",
            {
                networks: [],
                services: {
                    alpha: {
                        image: "alpha:1",
                        dependsOn: [
                            { service: "beta" }
                        ]
                    },
                    beta: {
                        image: "beta:1",
                        dependsOn: [
                            { service: "alpha" }
                        ]
                    }
                }
            },
            {}
        ),
        DependencyError
    );

    console.log("All Docker Compose model tests passed.");
}

main().catch(error => {
    console.error("Deployment error:", error.message);
    process.exitCode = 1;
});
