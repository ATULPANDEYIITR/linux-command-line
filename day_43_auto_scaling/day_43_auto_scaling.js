"use strict";

/*
 * Event-driven auto-scaling controller.
 *
 * Run with Node.js 18 or later:
 *     node autoscaling.js
 *
 * This implementation emphasizes event processing, asynchronous monitoring,
 * policy evaluation, and idempotent reconciliation of desired capacity.
 * It simulates infrastructure and does not call a cloud provider.
 */

const { EventEmitter } = require("node:events");
const fs = require("node:fs/promises");

class ValidationError extends Error {}
class PolicyError extends Error {}

function requireFiniteNumber(name, value, minimum = 0) {
  if (!Number.isFinite(value) || value < minimum) {
    throw new ValidationError(
      `${name} must be a finite number greater than or equal to ${minimum}.`
    );
  }
}

class ScalingPolicy {
  constructor({
    minInstances = 2,
    maxInstances = 12,
    targetCpu = 60,
    scaleOutCpu = 75,
    scaleInCpu = 30,
    scaleOutStep = 2,
    scaleInStep = 1,
    cooldownSeconds = 90,
    warmupSeconds = 45,
    evaluationSamples = 3,
    maxChangePerEvaluation = 3,
  } = {}) {
    if (!Number.isInteger(minInstances) || minInstances < 1) {
      throw new PolicyError("Minimum instances must be a positive integer.");
    }
    if (!Number.isInteger(maxInstances) || maxInstances < minInstances) {
      throw new PolicyError("Maximum instances must be at least the minimum.");
    }
    if (!(scaleInCpu >= 0 && scaleInCpu < scaleOutCpu && scaleOutCpu <= 100)) {
      throw new PolicyError("Scaling thresholds must be ordered within 0-100.");
    }
    if (!(targetCpu > 0 && targetCpu < 100)) {
      throw new PolicyError("Target CPU must be between 0 and 100.");
    }

    for (const [name, value] of Object.entries({
      scaleOutStep,
      scaleInStep,
      evaluationSamples,
      maxChangePerEvaluation,
    })) {
      if (!Number.isInteger(value) || value < 1) {
        throw new PolicyError(`${name} must be a positive integer.`);
      }
    }

    requireFiniteNumber("cooldownSeconds", cooldownSeconds);
    requireFiniteNumber("warmupSeconds", warmupSeconds);

    Object.assign(this, {
      minInstances,
      maxInstances,
      targetCpu,
      scaleOutCpu,
      scaleInCpu,
      scaleOutStep,
      scaleInStep,
      cooldownSeconds,
      warmupSeconds,
      evaluationSamples,
      maxChangePerEvaluation,
    });
    Object.freeze(this);
  }
}

class CapacityPool extends EventEmitter {
  constructor({ instanceCapacityRps, instanceHourlyCost, initialCount, policy }) {
    super();
    requireFiniteNumber("instanceCapacityRps", instanceCapacityRps, 0.001);
    requireFiniteNumber("instanceHourlyCost", instanceHourlyCost);

    if (!Number.isInteger(initialCount)) {
      throw new ValidationError("Initial count must be an integer.");
    }

    this.instanceCapacityRps = instanceCapacityRps;
    this.instanceHourlyCost = instanceHourlyCost;
    this.policy = policy;
    this.instances = new Map();
    this.sequence = 1;
    this.now = 0;
    this.lastActionAt = -Infinity;
    this.cpuSamples = [];
    this.metrics = [];
    this.events = [];
    this.revision = 0;

    const initial = Math.max(
      policy.minInstances,
      Math.min(policy.maxInstances, initialCount)
    );

    for (let index = 0; index < initial; index += 1) {
      this.createInstance(this.now, true);
    }
  }

  createInstance(readyAt, immediatelyReady = false) {
    const id = `api-${String(this.sequence++).padStart(3, "0")}`;
    const instance = {
      id,
      state: immediatelyReady ? "ready" : "pending",
      readyAt,
      healthy: true,
      generation: this.revision,
    };

    this.instances.set(id, instance);
    this.emit("instance-created", { ...instance });
    return instance;
  }

  get readyInstances() {
    return [...this.instances.values()].filter(
      (instance) => instance.healthy && instance.state === "ready"
    );
  }

  get desiredCount() {
    return this.instances.size;
  }

  get readyCapacityRps() {
    return this.readyInstances.length * this.instanceCapacityRps;
  }

  get hourlyCost() {
    return [...this.instances.values()].filter(
      (instance) => instance.healthy
    ).length * this.instanceHourlyCost;
  }

  advance(seconds) {
    requireFiniteNumber("seconds", seconds);
    this.now += seconds;

    for (const instance of this.instances.values()) {
      if (
        instance.healthy &&
        instance.state === "pending" &&
        instance.readyAt <= this.now
      ) {
        instance.state = "ready";
        this.emit("instance-ready", { ...instance, time: this.now });
      }
    }
  }

  async collectMetrics(incomingRps, memoryUtilization = 45) {
    requireFiniteNumber("incomingRps", incomingRps);
    requireFiniteNumber("memoryUtilization", memoryUtilization);
    if (memoryUtilization > 100) {
      throw new ValidationError("Memory utilization cannot exceed 100%.");
    }

    // Yielding permits a monitoring caller to interleave asynchronous work.
    await Promise.resolve();

    const capacity = this.readyCapacityRps;
    const servedRps = Math.min(incomingRps, capacity);
    const rejectedRps = Math.max(0, incomingRps - capacity);
    const cpu = capacity === 0
      ? 100
      : Math.min(100, (incomingRps / capacity) * 100);

    const metric = Object.freeze({
      time: this.now,
      incomingRps,
      capacity,
      servedRps,
      rejectedRps,
      cpu: Number(cpu.toFixed(2)),
      memory: memoryUtilization,
      desired: this.desiredCount,
      ready: this.readyInstances.length,
      pending: [...this.instances.values()].filter(
        (instance) => instance.state === "pending"
      ).length,
      hourlyCost: Number(this.hourlyCost.toFixed(4)),
    });

    this.metrics.push(metric);
    this.cpuSamples.push(metric.cpu);
    if (this.cpuSamples.length > this.policy.evaluationSamples) {
      this.cpuSamples.shift();
    }

    this.emit("metrics", metric);
    return metric;
  }

  async scaleOut(count, reason) {
    if (!Number.isInteger(count) || count < 1) {
      throw new ValidationError("Scale-out count must be a positive integer.");
    }

    const allowed = Math.min(
      count,
      this.policy.maxInstances - this.desiredCount,
      this.policy.maxChangePerEvaluation
    );
    if (allowed <= 0) return 0;

    const previous = this.desiredCount;
    const nextRevision = this.revision + 1;

    // Capacity is reconciled from the desired difference, making repeated
    // evaluations harmless once the requested capacity has been reached.
    for (let index = 0; index < allowed; index += 1) {
      this.createInstance(this.now + this.policy.warmupSeconds);
    }

    this.revision = nextRevision;
    this.lastActionAt = this.now;
    this.recordAction("scale_out", previous, this.desiredCount, reason);
    return allowed;
  }

  async scaleIn(count, reason) {
    if (!Number.isInteger(count) || count < 1) {
      throw new ValidationError("Scale-in count must be a positive integer.");
    }

    const allowed = Math.min(
      count,
      this.desiredCount - this.policy.minInstances,
      this.policy.maxChangePerEvaluation
    );
    if (allowed <= 0) return 0;

    const candidates = [...this.instances.values()]
      .filter((instance) => instance.healthy)
      .sort((a, b) => {
        // Remove not-yet-ready instances first to avoid dropping serving capacity.
        if (a.state !== b.state) return a.state === "pending" ? -1 : 1;
        return b.id.localeCompare(a.id);
      })
      .slice(0, allowed);

    const previous = this.desiredCount;
    for (const instance of candidates) {
      this.instances.delete(instance.id);
      this.emit("instance-removed", { id: instance.id, time: this.now });
    }

    this.revision += 1;
    this.lastActionAt = this.now;
    this.recordAction("scale_in", previous, this.desiredCount, reason);
    return candidates.length;
  }

  recordAction(direction, previous, current, reason) {
    const event = Object.freeze({
      time: this.now,
      direction,
      previous,
      current,
      reason,
      revision: this.revision,
    });
    this.events.push(event);
    this.emit("scaling-action", event);
  }

  async evaluatePolicy() {
    if (this.cpuSamples.length < this.policy.evaluationSamples) {
      return "insufficient-data";
    }

    if (this.now - this.lastActionAt < this.policy.cooldownSeconds) {
      return "cooldown";
    }

    const averageCpu = this.cpuSamples.reduce((sum, value) => sum + value, 0)
      / this.cpuSamples.length;

    if (averageCpu > this.policy.scaleOutCpu) {
      await this.scaleOut(
        this.policy.scaleOutStep,
        `Average CPU ${averageCpu.toFixed(1)}% exceeds threshold`
      );
      return "scale_out";
    }

    if (averageCpu < this.policy.scaleInCpu) {
      await this.scaleIn(
        this.policy.scaleInStep,
        `Average CPU ${averageCpu.toFixed(1)}% is below threshold`
      );
      return "scale_in";
    }

    return "stable";
  }

  failInstance(id) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new ValidationError(`Instance ${id} does not exist.`);
    }

    instance.healthy = false;
    instance.state = "unhealthy";
    this.emit("instance-unhealthy", { id, time: this.now });
  }

  recoverInstance(id) {
    const instance = this.instances.get(id);
    if (!instance || instance.healthy) {
      throw new ValidationError("Instance must exist and be unhealthy.");
    }

    instance.healthy = true;
    instance.state = "pending";
    instance.readyAt = this.now + this.policy.warmupSeconds;
    this.emit("instance-recovering", { id, readyAt: instance.readyAt });
  }

  snapshot() {
    return {
      time: this.now,
      desired: this.desiredCount,
      ready: this.readyInstances.length,
      capacityRps: this.readyCapacityRps,
      hourlyCost: this.hourlyCost,
      events: [...this.events],
    };
  }
}

async function runLoadTest(pool, trafficProfile, intervalSeconds = 30) {
  const results = [];

  for (const incomingRps of trafficProfile) {
    pool.advance(intervalSeconds);
    const metric = await pool.collectMetrics(incomingRps);
    const action = await pool.evaluatePolicy();
    results.push({ ...metric, action });
  }

  return results;
}

async function main() {
  const policy = new ScalingPolicy({
    minInstances: 2,
    maxInstances: 10,
    targetCpu: 60,
    scaleOutCpu: 75,
    scaleInCpu: 25,
    scaleOutStep: 2,
    scaleInStep: 1,
    cooldownSeconds: 60,
    warmupSeconds: 60,
    evaluationSamples: 2,
    maxChangePerEvaluation: 3,
  });

  const pool = new CapacityPool({
    instanceCapacityRps: 240,
    instanceHourlyCost: 0.08,
    initialCount: 2,
    policy,
  });

  pool.on("scaling-action", (event) => {
    console.log(
      `[t=${event.time}s] ${event.direction}: ` +
      `${event.previous} -> ${event.current}; ${event.reason}`
    );
  });

  pool.on("instance-ready", (event) => {
    console.log(`[t=${event.time}s] ${event.id} is ready`);
  });

  const traffic = [
    ...Array(4).fill(80),
    ...Array(4).fill(350),
    ...Array(6).fill(850),
    ...Array(4).fill(1400),
    ...Array(8).fill(90),
  ];

  const results = await runLoadTest(pool, traffic);
  console.log("\nSample metrics:");
  console.table(results.filter((_, index) => index % 3 === 0));

  if (pool.readyInstances.length > 0) {
    const instanceId = pool.readyInstances[0].id;
    pool.failInstance(instanceId);
    console.log("\nFailure snapshot:", pool.snapshot());

    // A real controller would consult an orchestrator or provider API to
    // replace failed instances and would apply a bounded retry policy.
    await pool.scaleOut(1, `Replace failed capacity from ${instanceId}`);
    pool.advance(policy.warmupSeconds);
  }

  await fs.writeFile(
    "autoscaling-js-report.json",
    JSON.stringify(
      {
        policy,
        snapshot: pool.snapshot(),
        metrics: results,
      },
      null,
      2
    ),
    "utf8"
  );

  console.log("\nReport written to autoscaling-js-report.json.");
}

async function testInvalidTraffic() {
  const policy = new ScalingPolicy();
  const pool = new CapacityPool({
    instanceCapacityRps: 100,
    instanceHourlyCost: 0.05,
    initialCount: 2,
    policy,
  });

  try {
    await pool.collectMetrics(-5);
  } catch (error) {
    if (!(error instanceof ValidationError)) throw error;
    console.log("Invalid traffic correctly rejected:", error.message);
  }

  const originalCount = pool.desiredCount;
  await pool.scaleOut(100, "maximum-capacity boundary test");
  if (pool.desiredCount > policy.maxInstances) {
    throw new Error("Maximum instance limit violated.");
  }

  await pool.scaleIn(100, "minimum-capacity boundary test");
  if (pool.desiredCount < policy.minInstances) {
    throw new Error("Minimum instance limit violated.");
  }

  console.log(`Capacity bounds tested; initial count was ${originalCount}.`);
}

main()
  .then(testInvalidTraffic)
  .catch((error) => {
    console.error("Auto-scaling simulation failed:", error.message);
    process.exitCode = 1;
  });
