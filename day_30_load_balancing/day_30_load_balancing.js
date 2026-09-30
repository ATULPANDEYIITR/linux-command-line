'use strict';

/*
 * Load Balancing in JavaScript
 *
 * This file models an event-driven load-balancing controller. The design
 * intentionally differs from the Python simulation by emphasizing:
 *
 * - JavaScript classes and Maps.
 * - EventEmitter-style lifecycle events.
 * - asynchronous health checks.
 * - HTTP-aware routing rules.
 * - policy evaluation before accepting traffic.
 * - request retries with idempotency awareness.
 * - graceful backend draining.
 * - operational metrics.
 *
 * It runs with Node.js and uses only built-in functionality.
 */

const { EventEmitter } = require('node:events');
const crypto = require('node:crypto');

const BackendState = Object.freeze({
  HEALTHY: 'healthy',
  UNHEALTHY: 'unhealthy',
  DRAINING: 'draining'
});

const Method = Object.freeze({
  GET: 'GET',
  HEAD: 'HEAD',
  POST: 'POST',
  PUT: 'PUT',
  DELETE: 'DELETE'
});

const IDEMPOTENT_METHODS = new Set([
  Method.GET,
  Method.HEAD,
  Method.PUT,
  Method.DELETE
]);

function stableHash(value) {
  const digest = crypto
    .createHash('sha256')
    .update(value)
    .digest('hex');

  return Number.parseInt(digest.slice(0, 12), 16);
}

class Backend {
  constructor({
    name,
    address,
    port = 8080,
    weight = 1,
    zone = 'zone-a',
    version = 'v1',
    role = 'application',
    failureRate = 0
  }) {
    if (!name || !address) {
      throw new TypeError('Backend requires a name and address.');
    }

    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new RangeError(`Invalid backend port: ${port}`);
    }

    if (!Number.isInteger(weight) || weight <= 0) {
      throw new RangeError(`Invalid backend weight: ${weight}`);
    }

    if (failureRate < 0 || failureRate > 1) {
      throw new RangeError('failureRate must be between 0 and 1.');
    }

    this.name = name;
    this.address = address;
    this.port = port;
    this.weight = weight;
    this.zone = zone;
    this.version = version;
    this.role = role;
    this.failureRate = failureRate;

    this.state = BackendState.HEALTHY;
    this.activeConnections = 0;
    this.requestCount = 0;
    this.failedRequests = 0;
    this.totalLatencyMs = 0;
  }

  get acceptingTraffic() {
    return this.state === BackendState.HEALTHY;
  }

  get averageLatencyMs() {
    return this.requestCount === 0
      ? 0
      : this.totalLatencyMs / this.requestCount;
  }

  beginDrain() {
    if (this.state === BackendState.HEALTHY) {
      this.state = BackendState.DRAINING;
    }
  }

  recover() {
    this.state = BackendState.HEALTHY;
  }

  recordRequest(latencyMs) {
    this.requestCount += 1;
    this.totalLatencyMs += latencyMs;
  }

  recordFailure() {
    this.failedRequests += 1;
  }
}

class BackendPool {
  constructor(backends) {
    if (!Array.isArray(backends) || backends.length === 0) {
      throw new Error('BackendPool cannot be empty.');
    }

    this.backends = new Map();

    for (const backend of backends) {
      if (this.backends.has(backend.name)) {
        throw new Error(`Duplicate backend: ${backend.name}`);
      }
      this.backends.set(backend.name, backend);
    }
  }

  get healthy() {
    return [...this.backends.values()].filter(
      backend => backend.acceptingTraffic
    );
  }

  get(name) {
    const backend = this.backends.get(name);

    if (!backend) {
      throw new Error(`Unknown backend: ${name}`);
    }

    return backend;
  }

  startDrain(name) {
    this.get(name).beginDrain();
  }
}

class AsyncHealthChecker extends EventEmitter {
  constructor({
    intervalMs = 1000,
    timeoutMs = 150,
    failureThreshold = 2,
    recoveryThreshold = 2
  } = {}) {
    super();

    this.intervalMs = intervalMs;
    this.timeoutMs = timeoutMs;
    this.failureThreshold = failureThreshold;
    this.recoveryThreshold = recoveryThreshold;

    this.failures = new Map();
    this.successes = new Map();
  }

  async probe(backend) {
    /*
     * A real checker would open a connection or send an HTTP request.
     * The timeout is represented with Promise.race so the model preserves
     * the asynchronous failure mode of a real health-check subsystem.
     */
    const probe = new Promise(resolve => {
      setTimeout(() => {
        if (backend.failureRate > 0.5) {
          resolve({
            healthy: false,
            reason: 'simulated upstream failure'
          });
        } else {
          resolve({
            healthy: true,
            reason: 'health endpoint responded'
          });
        }
      }, 5);
    });

    const timeout = new Promise(resolve => {
      setTimeout(() => {
        resolve({
          healthy: false,
          reason: 'health check timeout'
        });
      }, this.timeoutMs);
    });

    return Promise.race([probe, timeout]);
  }

  async check(backend) {
    const result = await this.probe(backend);

    const failures = this.failures.get(backend.name) || 0;
    const successes = this.successes.get(backend.name) || 0;

    if (result.healthy) {
      this.failures.set(backend.name, 0);
      this.successes.set(backend.name, successes + 1);

      if (
        backend.state === BackendState.UNHEALTHY &&
        successes + 1 >= this.recoveryThreshold
      ) {
        backend.recover();
        this.emit('backendRecovered', backend);
      }
    } else {
      this.successes.set(backend.name, 0);
      this.failures.set(backend.name, failures + 1);

      if (
        backend.state === BackendState.HEALTHY &&
        failures + 1 >= this.failureThreshold
      ) {
        backend.state = BackendState.UNHEALTHY;
        this.emit('backendFailed', backend);
      }
    }

    return {
      backend: backend.name,
      ...result,
      state: backend.state
    };
  }
}

class Layer4Router {
  constructor(pool, algorithm = 'least-connections') {
    this.pool = pool;
    this.algorithm = algorithm;
    this.index = 0;
    this.connectionMap = new Map();
  }

  chooseRoundRobin(backends) {
    const backend = backends[this.index % backends.length];
    this.index += 1;
    return backend;
  }

  chooseWeighted(backends) {
    const expanded = [];

    for (const backend of backends) {
      for (let i = 0; i < backend.weight; i += 1) {
        expanded.push(backend);
      }
    }

    const backend = expanded[this.index % expanded.length];
    this.index += 1;
    return backend;
  }

  chooseLeastConnections(backends) {
    /*
     * The secondary key prevents arbitrary instability when two nodes have
     * identical connection counts.
     */
    return [...backends].sort(
      (a, b) =>
        a.activeConnections - b.activeConnections ||
        a.name.localeCompare(b.name)
    )[0];
  }

  chooseConsistentHash(backends, clientIp) {
    return backends[stableHash(clientIp) % backends.length];
  }

  openConnection(connection) {
    const existing = this.connectionMap.get(connection.id);

    if (existing) {
      return this.pool.get(existing);
    }

    const candidates = this.pool.healthy;

    if (candidates.length === 0) {
      throw new Error('L4 routing failed: no healthy backend.');
    }

    let backend;

    switch (this.algorithm) {
      case 'round-robin':
        backend = this.chooseRoundRobin(candidates);
        break;
      case 'weighted':
        backend = this.chooseWeighted(candidates);
        break;
      case 'consistent-hash':
        backend = this.chooseConsistentHash(
          candidates,
          connection.clientIp
        );
        break;
      case 'least-connections':
        backend = this.chooseLeastConnections(candidates);
        break;
      default:
        throw new Error(`Unsupported L4 algorithm: ${this.algorithm}`);
    }

    backend.activeConnections += 1;
    this.connectionMap.set(connection.id, backend.name);

    return backend;
  }

  closeConnection(connectionId) {
    const backendName = this.connectionMap.get(connectionId);

    if (!backendName) {
      return;
    }

    const backend = this.pool.get(backendName);
    backend.activeConnections = Math.max(
      0,
      backend.activeConnections - 1
    );

    this.connectionMap.delete(connectionId);
  }
}

class Layer7Router extends EventEmitter {
  constructor(pool) {
    super();

    this.pool = pool;
    this.index = 0;
    this.sessions = new Map();
    this.metrics = new Map();
  }

  incrementMetric(name) {
    this.metrics.set(name, (this.metrics.get(name) || 0) + 1);
  }

  roundRobin(backends) {
    const backend = backends[this.index % backends.length];
    this.index += 1;
    return backend;
  }

  route(request) {
    const candidates = this.pool.healthy;

    if (candidates.length === 0) {
      this.incrementMetric('no_healthy_backend');
      throw new Error('L7 routing failed: no healthy backend.');
    }

    /*
     * L7 routing can inspect HTTP semantics. This rule sends API traffic to
     * API nodes and separates static assets to edge nodes.
     */
    if (request.path.startsWith('/static/')) {
      const edgeNodes = candidates.filter(
        backend => backend.role === 'edge'
      );

      if (edgeNodes.length > 0) {
        this.incrementMetric('static_route');
        return this.roundRobin(edgeNodes);
      }
    }

    if (request.path.startsWith('/admin')) {
      const adminNodes = candidates.filter(
        backend => backend.role === 'admin'
      );

      if (adminNodes.length > 0) {
        this.incrementMetric('admin_route');
        return this.roundRobin(adminNodes);
      }
    }

    /*
     * Cookie-based affinity is an application-layer feature. It is different
     * from TCP connection affinity because multiple HTTP requests can arrive
     * on different transport connections.
     */
    const sessionId = request.cookies?.session_id;

    if (sessionId && this.sessions.has(sessionId)) {
      const backend = this.pool.get(this.sessions.get(sessionId));

      if (backend.acceptingTraffic) {
        this.incrementMetric('sticky_session_hit');
        return backend;
      }

      /*
       * If a sticky backend has failed, the affinity entry must not prevent
       * recovery of the user's request.
       */
      this.sessions.delete(sessionId);
    }

    const backend = this.roundRobin(candidates);

    if (sessionId) {
      this.sessions.set(sessionId, backend.name);
      this.incrementMetric('sticky_session_assignment');
    }

    return backend;
  }

  async handle(request) {
    const backend = this.route(request);

    if (!backend.acceptingTraffic) {
      throw new Error(
        `Backend ${backend.name} stopped accepting traffic.`
      );
    }

    await new Promise(resolve => setTimeout(resolve, 2));

    const failed = Math.random() < backend.failureRate;

    if (failed) {
      backend.recordFailure();
      this.incrementMetric('upstream_failure');

      throw new Error(`Upstream request failed at ${backend.name}`);
    }

    const latencyMs = 8 + Math.random() * 12;
    backend.recordRequest(latencyMs);
    this.incrementMetric('request');

    this.emit('requestRouted', {
      requestId: request.id,
      backend: backend.name,
      latencyMs
    });

    return backend;
  }
}

class RetryController {
  constructor(router, { maxAttempts = 2 } = {}) {
    this.router = router;
    this.maxAttempts = maxAttempts;
  }

  async execute(request) {
    /*
     * Retrying only safe/idempotent operations avoids blindly repeating
     * mutations. A failed POST can have reached the application before the
     * connection broke, so automatically replaying it may create duplicates.
     */
    const canRetry = IDEMPOTENT_METHODS.has(request.method);
    const attemptsAllowed = canRetry ? this.maxAttempts : 1;

    let lastError;

    for (let attempt = 1; attempt <= attemptsAllowed; attempt += 1) {
      try {
        return await this.router.handle(request);
      } catch (error) {
        lastError = error;

        if (attempt < attemptsAllowed) {
          console.log(
            `Retrying ${request.id}: attempt ${attempt + 1}`
          );
        }
      }
    }

    throw lastError;
  }
}

class TrafficPolicy {
  constructor({
    requiredHealthyBackends = 2,
    minimumHealthyZones = 2
  } = {}) {
    this.requiredHealthyBackends = requiredHealthyBackends;
    this.minimumHealthyZones = minimumHealthyZones;
  }

  evaluate(pool) {
    const healthy = pool.healthy;
    const zones = new Set(healthy.map(backend => backend.zone));

    return {
      allowed: (
        healthy.length >= this.requiredHealthyBackends &&
        zones.size >= this.minimumHealthyZones
      ),
      healthyBackends: healthy.length,
      healthyZones: zones.size,
      reason:
        healthy.length < this.requiredHealthyBackends
          ? 'insufficient healthy capacity'
          : zones.size < this.minimumHealthyZones
            ? 'insufficient zone diversity'
            : 'capacity and zone requirements satisfied'
    };
  }
}

class HighAvailabilityPair extends EventEmitter {
  constructor(primary, standby) {
    super();
    this.primary = primary;
    this.standby = standby;
    this.active = primary;
    this.epoch = 1;
  }

  failover() {
    const previous = this.active;
    this.active =
      this.active === this.primary ? this.standby : this.primary;
    this.epoch += 1;

    this.emit('failover', {
      previous: previous.name,
      active: this.active.name,
      epoch: this.epoch
    });
  }
}

async function demonstrateHealthChecks(pool) {
  console.log('\n=== ASYNCHRONOUS HEALTH CHECKS ===');

  const checker = new AsyncHealthChecker({
    failureThreshold: 2,
    recoveryThreshold: 2,
    timeoutMs: 50
  });

  checker.on('backendFailed', backend => {
    console.log(`Backend removed from rotation: ${backend.name}`);
  });

  checker.on('backendRecovered', backend => {
    console.log(`Backend returned to rotation: ${backend.name}`);
  });

  const target = pool.get('api-b');

  target.failureRate = 1;

  for (let i = 0; i < 2; i += 1) {
    const result = await checker.check(target);
    console.log(result);
  }

  target.failureRate = 0;

  for (let i = 0; i < 2; i += 1) {
    const result = await checker.check(target);
    console.log(result);
  }
}

function demonstrateLayer4(pool) {
  console.log('\n=== LAYER 4 CONNECTION ROUTING ===');

  const router = new Layer4Router(pool, 'least-connections');

  const connections = [
    {
      id: 'tcp-001',
      clientIp: '192.0.2.10',
      sourcePort: 41001
    },
    {
      id: 'tcp-002',
      clientIp: '192.0.2.11',
      sourcePort: 41002
    },
    {
      id: 'tcp-003',
      clientIp: '192.0.2.12',
      sourcePort: 41003
    },
    {
      id: 'tcp-004',
      clientIp: '192.0.2.13',
      sourcePort: 41004
    }
  ];

  for (const connection of connections) {
    const backend = router.openConnection(connection);

    console.log(
      `${connection.id} ${connection.clientIp}:${connection.sourcePort}` +
      ` -> ${backend.name}`
    );
  }

  router.closeConnection('tcp-002');
  router.closeConnection('tcp-004');

  console.log('\nConnection counts after close:');

  for (const backend of pool.backends.values()) {
    console.log(
      `${backend.name}: ${backend.activeConnections}`
    );
  }
}

async function demonstrateLayer7(pool) {
  console.log('\n=== LAYER 7 HTTP ROUTING ===');

  const router = new Layer7Router(pool);

  router.on('requestRouted', event => {
    console.log(
      `${event.requestId} -> ${event.backend} ` +
      `(${event.latencyMs.toFixed(1)} ms)`
    );
  });

  const retryController = new RetryController(router);

  const requests = [
    {
      id: 'http-001',
      method: Method.GET,
      host: 'api.example.test',
      path: '/orders',
      cookies: {}
    },
    {
      id: 'http-002',
      method: Method.GET,
      host: 'www.example.test',
      path: '/static/app.js',
      cookies: {}
    },
    {
      id: 'http-003',
      method: Method.GET,
      host: 'admin.example.test',
      path: '/admin/users',
      cookies: {}
    },
    {
      id: 'http-004',
      method: Method.GET,
      host: 'api.example.test',
      path: '/profile',
      cookies: { session_id: 'customer-17' }
    },
    {
      id: 'http-005',
      method: Method.GET,
      host: 'api.example.test',
      path: '/orders/991',
      cookies: { session_id: 'customer-17' }
    },
    {
      id: 'http-006',
      method: Method.POST,
      host: 'api.example.test',
      path: '/orders',
      cookies: {}
    }
  ];

  for (const request of requests) {
    try {
      await retryController.execute(request);
    } catch (error) {
      console.log(`${request.id} failed: ${error.message}`);
    }
  }

  console.log('\nL7 metrics:');

  for (const [metric, count] of router.metrics.entries()) {
    console.log(`${metric}: ${count}`);
  }
}

function demonstrateDraining(pool) {
  console.log('\n=== GRACEFUL BACKEND DRAINING ===');

  const backend = pool.get('api-c');

  backend.activeConnections = 3;
  pool.startDrain(backend.name);

  console.log(
    `${backend.name}: state=${backend.state}, ` +
    `connections=${backend.activeConnections}`
  );

  /*
   * Existing connections are allowed to finish. New routing excludes the
   * draining backend because acceptingTraffic checks for HEALTHY state.
   */
  while (backend.activeConnections > 0) {
    backend.activeConnections -= 1;
  }

  console.log(
    `${backend.name}: active connections drained=${backend.activeConnections}`
  );

  backend.recover();

  console.log(
    `${backend.name}: state=${backend.state}`
  );
}

function demonstratePolicy(pool) {
  console.log('\n=== CAPACITY AND AVAILABILITY POLICY ===');

  const policy = new TrafficPolicy({
    requiredHealthyBackends: 3,
    minimumHealthyZones: 2
  });

  const result = policy.evaluate(pool);

  console.log(result);
}

function demonstrateHighAvailability() {
  console.log('\n=== LOAD-BALANCER HIGH AVAILABILITY ===');

  const primary = { name: 'lb-primary' };
  const standby = { name: 'lb-standby' };

  const pair = new HighAvailabilityPair(primary, standby);

  pair.on('failover', event => {
    console.log(
      `Failover epoch ${event.epoch}: ` +
      `${event.previous} -> ${event.active}`
    );
  });

  console.log(`Active node: ${pair.active.name}`);
  pair.failover();
  console.log(`Active node: ${pair.active.name}`);
  pair.failover();
  console.log(`Active node: ${pair.active.name}`);
}

function printOperationsReport(pool) {
  console.log('\n=== OPERATIONS REPORT ===');

  for (const backend of pool.backends.values()) {
    console.log(
      `${backend.name.padEnd(14)} ` +
      `state=${backend.state.padEnd(10)} ` +
      `requests=${String(backend.requestCount).padStart(3)} ` +
      `failures=${String(backend.failedRequests).padStart(3)} ` +
      `connections=${String(backend.activeConnections).padStart(2)} ` +
      `avgLatency=${backend.averageLatencyMs.toFixed(2)}ms`
    );
  }
}

async function main() {
  const pool = new BackendPool([
    new Backend({
      name: 'api-a',
      address: '10.0.1.10',
      weight: 3,
      zone: 'zone-a',
      role: 'application'
    }),
    new Backend({
      name: 'api-b',
      address: '10.0.1.11',
      weight: 2,
      zone: 'zone-b',
      role: 'application'
    }),
    new Backend({
      name: 'api-c',
      address: '10.0.2.10',
      weight: 1,
      zone: 'zone-b',
      role: 'application'
    }),
    new Backend({
      name: 'edge-a',
      address: '10.0.9.10',
      zone: 'zone-a',
      role: 'edge'
    }),
    new Backend({
      name: 'admin-a',
      address: '10.0.8.10',
      zone: 'zone-a',
      role: 'admin'
    })
  ]);

  console.log('LOAD BALANCING EVENT-DRIVEN LAB');

  await demonstrateHealthChecks(pool);
  demonstrateLayer4(pool);
  await demonstrateLayer7(pool);
  demonstrateDraining(pool);
  demonstratePolicy(pool);
  demonstrateHighAvailability();
  printOperationsReport(pool);
}

main().catch(error => {
  console.error(`Fatal error: ${error.message}`);
  process.exitCode = 1;
});
