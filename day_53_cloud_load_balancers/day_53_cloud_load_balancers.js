"use strict";

/*
 * Cloud Load Balancer Policy and Routing Simulator
 *
 * Node.js 18+.
 *
 * Models:
 * - Target groups
 * - Health checks
 * - Weighted routing
 * - Least-connections routing
 * - TLS termination policy
 * - Sticky sessions
 * - Backend failure and recovery
 * - Required status conditions
 * - Event-driven request processing
 * - Operational metrics
 *
 * No external npm dependencies are required.
 */

const crypto = require("crypto");
const { EventEmitter } = require("events");

const TargetState = Object.freeze({
  HEALTHY: "healthy",
  UNHEALTHY: "unhealthy",
  DRAINING: "draining",
});

const Algorithm = Object.freeze({
  WEIGHTED: "weighted",
  LEAST_CONNECTIONS: "least_connections",
});

const Protocol = Object.freeze({
  HTTP: "HTTP",
  HTTPS: "HTTPS",
});

class HealthCheckConfig {
  constructor({
    path = "/health",
    intervalMs = 5000,
    timeoutMs = 2000,
    healthyThreshold = 2,
    unhealthyThreshold = 2,
  } = {}) {
    if (!path.startsWith("/")) {
      throw new Error("Health-check path must start with '/'");
    }

    if (intervalMs <= 0 || timeoutMs <= 0) {
      throw new Error("Health-check timing must be positive");
    }

    if (healthyThreshold < 1 || unhealthyThreshold < 1) {
      throw new Error("Health-check thresholds must be positive");
    }

    this.path = path;
    this.intervalMs = intervalMs;
    this.timeoutMs = timeoutMs;
    this.healthyThreshold = healthyThreshold;
    this.unhealthyThreshold = unhealthyThreshold;
  }
}

class BackendTarget {
  constructor({
    id,
    host,
    port,
    weight = 1,
    latencyMs = 20,
    healthy = true,
  }) {
    if (!id || !host) {
      throw new Error("Target id and host are required");
    }

    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new Error(`Invalid target port: ${port}`);
    }

    if (!Number.isInteger(weight) || weight < 1) {
      throw new Error("Target weight must be a positive integer");
    }

    this.id = id;
    this.host = host;
    this.port = port;
    this.weight = weight;
    this.latencyMs = latencyMs;
    this.state = TargetState.HEALTHY;
    this.simulatedHealth = healthy;
    this.activeConnections = 0;
    this.consecutiveSuccesses = 0;
    this.consecutiveFailures = 0;
    this.totalRequests = 0;
    this.failedRequests = 0;
  }

  runHealthCheck(config) {
    if (this.state === TargetState.DRAINING) {
      return false;
    }

    if (this.simulatedHealth) {
      this.consecutiveSuccesses++;
      this.consecutiveFailures = 0;

      if (this.consecutiveSuccesses >= config.healthyThreshold) {
        this.state = TargetState.HEALTHY;
      }

      return true;
    }

    this.consecutiveFailures++;
    this.consecutiveSuccesses = 0;

    if (this.consecutiveFailures >= config.unhealthyThreshold) {
      this.state = TargetState.UNHEALTHY;
    }

    return false;
  }

  get available() {
    return this.state === TargetState.HEALTHY;
  }
}

class TargetGroup {
  constructor(name, config = new HealthCheckConfig(), algorithm = Algorithm.WEIGHTED) {
    if (!name) {
      throw new Error("Target-group name is required");
    }

    this.name = name;
    this.healthCheck = config;
    this.algorithm = algorithm;
    this.targets = new Map();
  }

  register(target) {
    if (this.targets.has(target.id)) {
      throw new Error(`Duplicate target: ${target.id}`);
    }

    this.targets.set(target.id, target);
  }

  healthyTargets() {
    return [...this.targets.values()].filter((target) => target.available);
  }

  runHealthChecks() {
    for (const target of this.targets.values()) {
      target.runHealthCheck(this.healthCheck);
    }
  }

  selectTarget(requestId, sessionId) {
    const candidates = this.healthyTargets();

    if (candidates.length === 0) {
      throw new Error(`Target group ${this.name} has no healthy targets`);
    }

    if (this.algorithm === Algorithm.LEAST_CONNECTIONS) {
      return candidates.reduce((best, candidate) => {
        if (!best) return candidate;

        if (candidate.activeConnections < best.activeConnections) {
          return candidate;
        }

        if (
          candidate.activeConnections === best.activeConnections &&
          candidate.latencyMs < best.latencyMs
        ) {
          return candidate;
        }

        return best;
      }, null);
    }

    const key = sessionId || requestId;
    const digest = crypto.createHash("sha256").update(key).digest();
    const number = digest.readUInt32BE(0);

    const totalWeight = candidates.reduce(
      (total, target) => total + target.weight,
      0
    );

    let position = number % totalWeight;

    for (const target of candidates) {
      if (position < target.weight) {
        return target;
      }
      position -= target.weight;
    }

    return candidates[candidates.length - 1];
  }
}

class CloudLoadBalancer extends EventEmitter {
  constructor({
    name,
    certificateHost,
    minimumTlsVersion = "TLSv1.2",
    stickySessions = true,
  }) {
    super();

    if (!name || !certificateHost) {
      throw new Error("Load-balancer name and certificate host are required");
    }

    if (!["TLSv1.2", "TLSv1.3"].includes(minimumTlsVersion)) {
      throw new Error("Unsupported TLS policy");
    }

    this.name = name;
    this.certificateHost = certificateHost;
    this.minimumTlsVersion = minimumTlsVersion;
    this.stickySessions = stickySessions;
    this.targetGroups = new Map();
    this.sessions = new Map();
    this.logs = [];
  }

  addTargetGroup(group) {
    if (this.targetGroups.has(group.name)) {
      throw new Error(`Duplicate target group: ${group.name}`);
    }

    this.targetGroups.set(group.name, group);
  }

  synchronizeHealth() {
    for (const group of this.targetGroups.values()) {
      group.runHealthChecks();
    }

    this.emit("health-cycle-complete");
  }

  validateTls(request) {
    if (request.protocol !== Protocol.HTTPS) {
      return;
    }

    if (request.host !== this.certificateHost) {
      const error = new Error(
        `Certificate hostname mismatch for ${request.host}`
      );
      error.code = "TLS_HOST_MISMATCH";
      throw error;
    }
  }

  validateRequest(request) {
    if (!request.id || !request.clientIp || !request.host) {
      throw new Error("Request id, client IP, and host are required");
    }

    if (!request.path.startsWith("/")) {
      throw new Error("Request path must start with '/'");
    }

    if (!Object.values(Protocol).includes(request.protocol)) {
      throw new Error(`Unsupported protocol: ${request.protocol}`);
    }
  }

  async route(request, targetGroupName) {
    try {
      this.validateRequest(request);
      this.validateTls(request);
    } catch (error) {
      return {
        id: request.id,
        status: 400,
        target: null,
        message: error.message,
      };
    }

    const group = this.targetGroups.get(targetGroupName);

    if (!group) {
      return {
        id: request.id,
        status: 503,
        target: null,
        message: "Target group not found",
      };
    }

    let target = null;

    if (this.stickySessions && request.sessionId) {
      const targetId = this.sessions.get(request.sessionId);
      const mappedTarget = group.targets.get(targetId);

      if (mappedTarget?.available) {
        target = mappedTarget;
      }
    }

    try {
      if (!target) {
        target = group.selectTarget(request.id, request.sessionId);

        if (this.stickySessions && request.sessionId) {
          this.sessions.set(request.sessionId, target.id);
        }
      }
    } catch (error) {
      return {
        id: request.id,
        status: 503,
        target: null,
        message: error.message,
      };
    }

    target.activeConnections++;
    target.totalRequests++;

    this.emit("request-routed", {
      requestId: request.id,
      targetId: target.id,
    });

    /*
     * Promise-based processing reflects event-driven request handling.
     * The timeout represents backend service time rather than real network I/O.
     */
    const result = await new Promise((resolve) => {
      setTimeout(() => {
        const healthy = target.state === TargetState.HEALTHY;

        target.activeConnections--;

        if (!healthy) {
          target.failedRequests++;
        }

        const response = {
          id: request.id,
          status: healthy ? 200 : 502,
          target: target.id,
          tlsTerminated: request.protocol === Protocol.HTTPS,
          latencyMs: target.latencyMs,
          message: healthy
            ? `Served by ${target.id}`
            : "Backend target unavailable",
        };

        this.logs.push({
          requestId: request.id,
          clientIp: request.clientIp,
          path: request.path,
          targetId: target.id,
          status: response.status,
          latencyMs: response.latencyMs,
          tlsTerminated: response.tlsTerminated,
        });

        resolve(response);
      }, Math.min(target.latencyMs, 50));
    });

    return result;
  }

  metrics() {
    const requests = this.logs.length;
    const successful = this.logs.filter((entry) => entry.status < 400).length;

    return {
      requests,
      successful,
      failed: requests - successful,
      successRate: requests ? (successful / requests) * 100 : 0,
      averageLatencyMs: requests
        ? this.logs.reduce((sum, entry) => sum + entry.latencyMs, 0) / requests
        : 0,
    };
  }
}

async function main() {
  const loadBalancer = new CloudLoadBalancer({
    name: "production-api-lb",
    certificateHost: "api.example.com",
    minimumTlsVersion: "TLSv1.2",
    stickySessions: true,
  });

  const apiTargets = new TargetGroup(
    "api-production",
    new HealthCheckConfig({
      path: "/health",
      intervalMs: 5000,
      timeoutMs: 2000,
      healthyThreshold: 2,
      unhealthyThreshold: 2,
    }),
    Algorithm.WEIGHTED
  );

  apiTargets.register(
    new BackendTarget({
      id: "api-a",
      host: "10.0.10.10",
      port: 8080,
      weight: 5,
      latencyMs: 12,
    })
  );

  apiTargets.register(
    new BackendTarget({
      id: "api-b",
      host: "10.0.10.11",
      port: 8080,
      weight: 3,
      latencyMs: 20,
    })
  );

  apiTargets.register(
    new BackendTarget({
      id: "api-c",
      host: "10.0.10.12",
      port: 8080,
      weight: 2,
      latencyMs: 28,
    })
  );

  loadBalancer.addTargetGroup(apiTargets);

  loadBalancer.on("request-routed", (event) => {
    console.log(
      `[routing] ${event.requestId} -> ${event.targetId}`
    );
  });

  loadBalancer.on("health-cycle-complete", () => {
    console.log("[health] health-check cycle completed");
  });

  /*
   * Two successful checks satisfy the configured healthy threshold.
   */
  loadBalancer.synchronizeHealth();
  loadBalancer.synchronizeHealth();

  console.log("\nHealthy targets:");
  console.log(
    apiTargets.healthyTargets().map((target) => target.id)
  );

  const requests = Array.from({ length: 8 }, (_, index) => ({
    id: `request-${index + 1}`,
    clientIp: `192.0.2.${index + 10}`,
    protocol: Protocol.HTTPS,
    host: "api.example.com",
    path: "/orders",
    sessionId: `session-${index % 2}`,
  }));

  console.log("\nConcurrent request processing:");

  const responses = await Promise.all(
    requests.map((request) =>
      loadBalancer.route(request, "api-production")
    )
  );

  for (const response of responses) {
    console.log(
      `${response.id}: status=${response.status}, target=${response.target}`
    );
  }

  /*
   * Backend b fails two consecutive health checks. It then becomes
   * ineligible for new traffic without removing the target definition.
   */
  const failedTarget = apiTargets.targets.get("api-b");
  failedTarget.simulatedHealth = false;

  loadBalancer.synchronizeHealth();
  loadBalancer.synchronizeHealth();

  console.log("\nAfter api-b failure:");
  for (const target of apiTargets.targets.values()) {
    console.log(`${target.id}: ${target.state}`);
  }

  const failoverResponse = await loadBalancer.route(
    {
      id: "failover-request",
      clientIp: "198.51.100.10",
      protocol: Protocol.HTTPS,
      host: "api.example.com",
      path: "/orders",
      sessionId: "new-session",
    },
    "api-production"
  );

  console.log(
    `Failover request: ${failoverResponse.status} -> ${failoverResponse.target}`
  );

  /*
   * Recovery requires the configured healthy threshold to be met again.
   */
  failedTarget.simulatedHealth = true;
  loadBalancer.synchronizeHealth();
  loadBalancer.synchronizeHealth();

  console.log("\nAfter api-b recovery:");
  for (const target of apiTargets.targets.values()) {
    console.log(`${target.id}: ${target.state}`);
  }

  const invalidTls = await loadBalancer.route(
    {
      id: "invalid-tls",
      clientIp: "203.0.113.10",
      protocol: Protocol.HTTPS,
      host: "attacker.example.net",
      path: "/orders",
    },
    "api-production"
  );

  console.log("\nTLS validation failure:");
  console.log(invalidTls);

  console.log("\nMetrics:");
  console.table(loadBalancer.metrics());
}

main().catch((error) => {
  console.error("Fatal load-balancer simulation error:", error.message);
  process.exitCode = 1;
});
