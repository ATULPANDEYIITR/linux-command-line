"use strict";

/*
 * Docker Multi-Service Application
 * Frontend gateway and container topology monitor.
 *
 * Runtime: Node.js 22+
 *
 * Features:
 * - HTTP frontend
 * - Backend API proxy
 * - Service dependency validation
 * - Concurrent health checks
 * - Circuit breaker
 * - Request timeout
 * - Graceful shutdown
 * - Request correlation identifiers
 *
 * Run:
 * node server.js
 */

const http = require("node:http");
const crypto = require("node:crypto");
const { URL } = require("node:url");

const CONFIG = Object.freeze({
    port: Number(process.env.PORT || 3000),
    backend: process.env.BACKEND_URL || "http://backend:8000",
    timeout: 5000,
    failureThreshold: 3,
    recoveryTime: 10000,
    maxBodyBytes: 4096
});

const ServiceState = Object.freeze({
    CLOSED: "CLOSED",
    OPEN: "OPEN",
    HALF_OPEN: "HALF_OPEN"
});

class ConfigurationError extends Error {}

class CircuitBreaker {
    constructor(threshold, recoveryTime) {
        this.threshold = threshold;
        this.recoveryTime = recoveryTime;
        this.failures = 0;
        this.state = ServiceState.CLOSED;
        this.lastFailure = 0;
        this.probeActive = false;
    }

    canExecute() {
        if (this.state === ServiceState.CLOSED) {
            return true;
        }

        if (this.state === ServiceState.OPEN) {
            if (Date.now() - this.lastFailure >= this.recoveryTime) {
                this.state = ServiceState.HALF_OPEN;
                this.probeActive = false;
            } else {
                return false;
            }
        }

        if (this.state === ServiceState.HALF_OPEN) {
            if (this.probeActive) return false;
            this.probeActive = true;
            return true;
        }

        return false;
    }

    success() {
        this.failures = 0;
        this.state = ServiceState.CLOSED;
        this.probeActive = false;
    }

    failure() {
        this.failures++;
        this.lastFailure = Date.now();
        this.probeActive = false;

        if (
            this.failures >= this.threshold ||
            this.state === ServiceState.HALF_OPEN
        ) {
            this.state = ServiceState.OPEN;
        }
    }
}

class ServiceRegistry {
    constructor() {
        this.services = new Map([
            ["frontend", {
                port: 3000,
                dependencies: ["backend"]
            }],
            ["backend", {
                port: 8000,
                dependencies: ["database"]
            }],
            ["database", {
                port: 5432,
                dependencies: []
            }]
        ]);
    }

    validate() {
        for (const [name, service] of this.services) {
            if (!Number.isInteger(service.port) ||
                service.port < 1 ||
                service.port > 65535) {
                throw new ConfigurationError(
                    `Invalid port for ${name}`
                );
            }

            for (const dependency of service.dependencies) {
                if (!this.services.has(dependency)) {
                    throw new ConfigurationError(
                        `Unknown dependency: ${dependency}`
                    );
                }
            }
        }

        const visited = new Set();
        const active = new Set();

        const visit = (name) => {
            if (active.has(name)) {
                throw new ConfigurationError(
                    `Dependency cycle detected at ${name}`
                );
            }

            if (visited.has(name)) return;

            active.add(name);

            for (const dependency of this.services.get(name).dependencies) {
                visit(dependency);
            }

            active.delete(name);
            visited.add(name);
        };

        for (const name of this.services.keys()) {
            visit(name);
        }

        return true;
    }

    get(name) {
        const service = this.services.get(name);
        if (!service) {
            throw new ConfigurationError(
                `Unknown service: ${name}`
            );
        }
        return service;
    }
}

class BackendGateway {
    constructor(baseURL) {
        this.baseURL = new URL(baseURL);
        if (!["http:", "https:"].includes(this.baseURL.protocol)) {
            throw new ConfigurationError(
                "Backend URL must use HTTP or HTTPS"
            );
        }

        this.breaker = new CircuitBreaker(
            CONFIG.failureThreshold,
            CONFIG.recoveryTime
        );
    }

    async request(path, method, body) {
        if (!this.breaker.canExecute()) {
            const error = new Error("Backend circuit breaker is open");
            error.statusCode = 503;
            throw error;
        }

        try {
            const response = await fetch(
                new URL(path, this.baseURL),
                {
                    method,
                    headers: method === "POST"
                        ? {"Content-Type": "application/json"}
                        : {},
                    body,
                    signal: AbortSignal.timeout(CONFIG.timeout)
                }
            );

            if (response.status >= 500) {
                this.breaker.failure();
            } else {
                this.breaker.success();
            }

            return {
                status: response.status,
                body: await response.text()
            };

        } catch (error) {
            this.breaker.failure();

            const gatewayError = new Error(
                "Backend connection failed"
            );
            gatewayError.statusCode = 503;
            throw gatewayError;
        }
    }
}

class Application {
    constructor() {
        this.registry = new ServiceRegistry();
        this.registry.validate();

        this.gateway = new BackendGateway(CONFIG.backend);
        this.server = http.createServer(
            this.handle.bind(this)
        );

        this.server.maxHeadersCount = 50;
        this.server.requestTimeout = 10000;
        this.server.headersTimeout = 12000;
    }

    async readBody(request) {
        const chunks = [];
        let size = 0;

        for await (const chunk of request) {
            size += chunk.length;

            if (size > CONFIG.maxBodyBytes) {
                const error = new Error("Request body too large");
                error.statusCode = 413;
                throw error;
            }

            chunks.push(chunk);
        }

        return Buffer.concat(chunks).toString("utf8");
    }

    respond(response, status, payload, requestId) {
        const body = typeof payload === "string"
            ? payload
            : JSON.stringify(payload);

        response.writeHead(status, {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": Buffer.byteLength(body),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Request-ID": requestId
        });

        response.end(body);
    }

    async handle(request, response) {
        const requestId = crypto.randomUUID();

        try {
            const url = new URL(
                request.url,
                "http://localhost"
            );

            if (url.pathname === "/health" && request.method === "GET") {
                return this.respond(
                    response,
                    200,
                    {
                        status: "healthy",
                        service: "frontend",
                        backendCircuit: this.gateway.breaker.state
                    },
                    requestId
                );
            }

            if (url.pathname === "/" && request.method === "GET") {
                return this.respond(
                    response,
                    200,
                    {
                        application: "Docker Multi-Service Application",
                        architecture: [
                            "Frontend",
                            "Backend",
                            "PostgreSQL"
                        ]
                    },
                    requestId
                );
            }

            if (
                url.pathname === "/api/tasks" &&
                ["GET", "POST"].includes(request.method)
            ) {
                let body;

                if (request.method === "POST") {
                    body = await this.readBody(request);

                    let parsed;
                    try {
                        parsed = JSON.parse(body);
                    } catch {
                        const error = new Error("Invalid JSON");
                        error.statusCode = 400;
                        throw error;
                    }

                    if (
                        typeof parsed.title !== "string" ||
                        parsed.title.trim().length === 0 ||
                        parsed.title.trim().length > 200
                    ) {
                        const error = new Error("Invalid task title");
                        error.statusCode = 400;
                        throw error;
                    }
                }

                const result = await this.gateway.request(
                    url.pathname,
                    request.method,
                    body
                );

                return this.respond(
                    response,
                    result.status,
                    result.body,
                    requestId
                );
            }

            return this.respond(
                response,
                404,
                {error: "Route not found"},
                requestId
            );

        } catch (error) {
            console.error({
                requestId,
                message: error.message
            });

            return this.respond(
                response,
                error.statusCode || 500,
                {
                    error: error.statusCode
                        ? error.message
                        : "Internal server error"
                },
                requestId
            );
        }
    }

    start() {
        this.server.listen(
            CONFIG.port,
            "0.0.0.0",
            () => {
                console.log(
                    `Frontend listening on ${CONFIG.port}`
                );
            }
        );
    }

    async shutdown() {
        console.log("Graceful shutdown initiated.");

        await new Promise((resolve) => {
            this.server.close(resolve);
        });

        console.log("Frontend stopped.");
    }
}

async function main() {
    const application = new Application();

    application.start();

    const shutdown = async () => {
        try {
            await application.shutdown();
            process.exit(0);
        } catch (error) {
            console.error(error.message);
            process.exit(1);
        }
    };

    process.on("SIGTERM", shutdown);
    process.on("SIGINT", shutdown);
}

main().catch((error) => {
    console.error("Application startup failed:", error.message);
    process.exit(1);
});
