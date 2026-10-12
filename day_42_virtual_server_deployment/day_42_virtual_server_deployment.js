"use strict";

/*
 * Virtual server deployment control plane.
 * Runtime: Node.js 18 or later.
 *
 * This executable simulation demonstrates asynchronous provisioning,
 * idempotency keys, lifecycle events, health checks, retryable failures,
 * deployment policy, stale operation protection, and cost estimation.
 * It does not call a real cloud API.
 */

const { randomUUID } = require("node:crypto");
const { setTimeout: delay } = require("node:timers/promises");

const STATES = Object.freeze({
  REQUESTED: "requested",
  PROVISIONING: "provisioning",
  RUNNING: "running",
  STOPPING: "stopping",
  STOPPED: "stopped",
  RESTARTING: "restarting",
  TERMINATED: "terminated",
  FAILED: "failed",
});

const TRANSITIONS = Object.freeze({
  requested: ["provisioning", "failed"],
  provisioning: ["running", "failed"],
  running: ["stopping", "restarting", "terminated", "failed"],
  stopping: ["stopped", "failed"],
  stopped: ["provisioning", "terminated", "failed"],
  restarting: ["running", "failed"],
  failed: ["provisioning", "terminated"],
  terminated: [],
});

const INSTANCE_TYPES = Object.freeze({
  small: { vcpus: 2, memoryGiB: 4, hourlyRate: 0.05 },
  medium: { vcpus: 4, memoryGiB: 16, hourlyRate: 0.12 },
  large: { vcpus: 8, memoryGiB: 32, hourlyRate: 0.24 },
});

class DeploymentError extends Error {}
class PolicyError extends DeploymentError {}
class LifecycleError extends DeploymentError {}
class ProviderError extends DeploymentError {}

function assertIdentifier(value, pattern, description) {
  if (typeof value !== "string" || !pattern.test(value)) {
    throw new PolicyError(`Invalid ${description}.`);
  }
}

function validateSpecification(spec) {
  if (!spec || typeof spec !== "object") {
    throw new PolicyError("A server specification is required.");
  }

  assertIdentifier(spec.name, /^[a-z][a-z0-9-]{1,39}$/, "server name");
  assertIdentifier(spec.region, /^[a-z]{2}(?:-[a-z0-9]+)+-\d+$/, "region");
  assertIdentifier(spec.imageId, /^(?:img|ami)-[a-zA-Z0-9-]{3,40}$/, "image ID");

  if (!Object.hasOwn(INSTANCE_TYPES, spec.instanceType)) {
    throw new PolicyError("Unknown instance type.");
  }

  if (!["development", "staging", "production"].includes(spec.environment)) {
    throw new PolicyError("Unsupported environment.");
  }

  if (!Number.isInteger(spec.rootDiskGiB) ||
      spec.rootDiskGiB < 8 || spec.rootDiskGiB > 16384) {
    throw new PolicyError("Root disk must be between 8 and 16384 GiB.");
  }

  if (!spec.network || !Array.isArray(spec.network.securityGroupIds) ||
      spec.network.securityGroupIds.length === 0) {
    throw new PolicyError("At least one security group is required.");
  }

  assertIdentifier(spec.network.subnetId, /^subnet-[a-zA-Z0-9-]{3,40}$/,
    "subnet ID");

  for (const groupId of spec.network.securityGroupIds) {
    assertIdentifier(groupId, /^sg-[a-zA-Z0-9-]{3,40}$/, "security group ID");
  }

  if (!Array.isArray(spec.network.ingressPorts)) {
    throw new PolicyError("Ingress ports must be an array.");
  }

  if (new Set(spec.network.ingressPorts).size !== spec.network.ingressPorts.length) {
    throw new PolicyError("Duplicate ingress ports are not allowed.");
  }

  for (const port of spec.network.ingressPorts) {
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new PolicyError(`Invalid ingress port: ${port}`);
    }
  }

  if (spec.environment === "production") {
    if (spec.encryptedDisk !== true || spec.monitoringEnabled !== true) {
      throw new PolicyError(
        "Production requires encrypted storage and monitoring."
      );
    }
  }

  if (typeof spec.startupScript !== "string" ||
      Buffer.byteLength(spec.startupScript, "utf8") > 16384) {
    throw new PolicyError("Startup script must be a string under 16 KiB.");
  }

  return structuredClone(spec);
}

class EventBus {
  #listeners = new Map();

  on(eventName, listener) {
    if (typeof listener !== "function") {
      throw new TypeError("Event listener must be a function.");
    }
    const listeners = this.#listeners.get(eventName) ?? new Set();
    listeners.add(listener);
    this.#listeners.set(eventName, listeners);
    return () => listeners.delete(listener);
  }

  emit(eventName, event) {
    // Each listener receives an immutable event snapshot. Listener failures
    // are isolated so that logging or notification cannot undo a state change.
    const snapshot = Object.freeze(structuredClone(event));
    for (const listener of this.#listeners.get(eventName) ?? []) {
      try {
        listener(snapshot);
      } catch (error) {
        console.error(`Listener failed for ${eventName}: ${error.message}`);
      }
    }
  }
}

class MockCloudAdapter {
  #nextPrivateAddress = 10;
  failNext = null;

  async #maybeFail(operation) {
    await delay(5);
    if (this.failNext === operation) {
      this.failNext = null;
      throw new ProviderError(`Provider failed during ${operation}.`);
    }
  }

  async create(spec) {
    await this.#maybeFail("create");
    const host = this.#nextPrivateAddress++;
    return {
      providerId: `cloud-${randomUUID().slice(0, 8)}`,
      privateIp: `10.30.0.${host}`,
      publicIp: spec.network.publicIp ? `198.51.100.${host}` : null,
    };
  }

  async stop() {
    await this.#maybeFail("stop");
  }

  async start(vm) {
    await this.#maybeFail("start");
    return { privateIp: vm.privateIp };
  }

  async restart() {
    await this.#maybeFail("restart");
  }

  async terminate() {
    await this.#maybeFail("terminate");
  }

  async healthCheck(vm) {
    await this.#maybeFail("health");
    return {
      healthy: vm.state === STATES.RUNNING,
      checkedAt: new Date().toISOString(),
    };
  }
}

class DeploymentController {
  #instances = new Map();
  #names = new Map();
  #idempotency = new Map();
  #operations = new Map();

  constructor(adapter = new MockCloudAdapter(), events = new EventBus()) {
    this.adapter = adapter;
    this.events = events;
  }

  #transition(vm, target, action, details = "") {
    if (!TRANSITIONS[vm.state]?.includes(target)) {
      throw new LifecycleError(
        `Invalid transition ${vm.state} -> ${target} for ${vm.id}.`
      );
    }

    const previousState = vm.state;
    vm.state = target;
    vm.updatedAt = new Date().toISOString();

    const event = {
      instanceId: vm.id,
      name: vm.spec.name,
      action,
      previousState,
      newState: target,
      timestamp: vm.updatedAt,
      details,
    };

    vm.audit.push(event);
    this.events.emit("lifecycle", event);
  }

  #beginOperation(vm, operation) {
    // Operation generations stop an old asynchronous response from being
    // applied after a newer lifecycle operation has superseded it.
    const generation = (this.#operations.get(vm.id) ?? 0) + 1;
    this.#operations.set(vm.id, generation);
    return {
      generation,
      assertCurrent: () => {
        if (this.#operations.get(vm.id) !== generation) {
          throw new LifecycleError("Operation was superseded.");
        }
      },
    };
  }

  async deploy(rawSpec, idempotencyKey) {
    const spec = validateSpecification(rawSpec);

    if (typeof idempotencyKey !== "string" ||
        idempotencyKey.length < 8 || idempotencyKey.length > 128) {
      throw new PolicyError("A valid idempotency key is required.");
    }

    const previous = this.#idempotency.get(idempotencyKey);
    if (previous) {
      if (previous.name !== spec.name ||
          previous.specification !== JSON.stringify(spec)) {
        throw new PolicyError(
          "An idempotency key cannot be reused for a different request."
        );
      }
      return this.#instances.get(previous.instanceId);
    }

    if (this.#names.has(spec.name)) {
      throw new PolicyError(`Instance name ${spec.name} already exists.`);
    }

    const vm = {
      id: `vm-${randomUUID().slice(0, 12)}`,
      spec,
      state: STATES.REQUESTED,
      providerId: null,
      privateIp: null,
      publicIp: null,
      health: "unknown",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      bootCount: 0,
      audit: [],
    };

    this.#instances.set(vm.id, vm);
    this.#names.set(spec.name, vm.id);
    this.#idempotency.set(idempotencyKey, {
      instanceId: vm.id,
      name: spec.name,
      specification: JSON.stringify(spec),
    });

    const operation = this.#beginOperation(vm, "create");
    this.#transition(vm, STATES.PROVISIONING, "create");

    try {
      const allocation = await this.adapter.create(spec);
      operation.assertCurrent();

      Object.assign(vm, allocation);
      vm.bootCount = 1;
      this.#transition(vm, STATES.RUNNING, "create", "Resources allocated.");
      vm.health = "healthy";
      this.events.emit("deployment-ready", {
        instanceId: vm.id,
        privateIp: vm.privateIp,
      });
      return vm;
    } catch (error) {
      if (vm.state === STATES.PROVISIONING) {
        this.#transition(vm, STATES.FAILED, "create", error.message);
      }
      vm.health = "unhealthy";
      throw error;
    }
  }

  async stop(instanceId) {
    const vm = this.get(instanceId);
    if (vm.state !== STATES.RUNNING) {
      throw new LifecycleError("Only running instances can be stopped.");
    }

    const operation = this.#beginOperation(vm, "stop");
    this.#transition(vm, STATES.STOPPING, "stop");

    try {
      await this.adapter.stop(vm);
      operation.assertCurrent();
      this.#transition(vm, STATES.STOPPED, "stop");
      vm.health = "not-running";
      return vm;
    } catch (error) {
      if (vm.state === STATES.STOPPING) {
        this.#transition(vm, STATES.FAILED, "stop", error.message);
      }
      vm.health = "unhealthy";
      throw error;
    }
  }

  async start(instanceId) {
    const vm = this.get(instanceId);
    if (![STATES.STOPPED, STATES.FAILED].includes(vm.state)) {
      throw new LifecycleError("Only stopped or failed instances can start.");
    }

    const operation = this.#beginOperation(vm, "start");
    this.#transition(vm, STATES.PROVISIONING, "start");

    try {
      const allocation = await this.adapter.start(vm);
      operation.assertCurrent();
      if (allocation.privateIp) vm.privateIp = allocation.privateIp;
      vm.bootCount++;
      this.#transition(vm, STATES.RUNNING, "start");
      vm.health = "healthy";
      return vm;
    } catch (error) {
      if (vm.state === STATES.PROVISIONING) {
        this.#transition(vm, STATES.FAILED, "start", error.message);
      }
      vm.health = "unhealthy";
      throw error;
    }
  }

  async restart(instanceId) {
    const vm = this.get(instanceId);
    if (vm.state !== STATES.RUNNING) {
      throw new LifecycleError("Only running instances can restart.");
    }

    const operation = this.#beginOperation(vm, "restart");
    this.#transition(vm, STATES.RESTARTING, "restart");

    try {
      await this.adapter.restart(vm);
      operation.assertCurrent();
      vm.bootCount++;
      this.#transition(vm, STATES.RUNNING, "restart");
      vm.health = "healthy";
      return vm;
    } catch (error) {
      if (vm.state === STATES.RESTARTING) {
        this.#transition(vm, STATES.FAILED, "restart", error.message);
      }
      vm.health = "unhealthy";
      throw error;
    }
  }

  async terminate(instanceId) {
    const vm = this.get(instanceId);
    if (vm.state === STATES.TERMINATED) {
      throw new LifecycleError("Instance is already terminated.");
    }

    this.#beginOperation(vm, "terminate");
    try {
      await this.adapter.terminate(vm);
    } catch (error) {
      if (vm.state !== STATES.FAILED) {
        this.#transition(vm, STATES.FAILED, "terminate", error.message);
      }
      throw error;
    }

    this.#transition(vm, STATES.TERMINATED, "terminate");
    vm.publicIp = null;
    vm.privateIp = null;
    vm.health = "terminated";
    return vm;
  }

  async checkHealth(instanceId) {
    const vm = this.get(instanceId);
    try {
      const result = await this.adapter.healthCheck(vm);
      vm.health = result.healthy ? "healthy" : "unhealthy";
      return result;
    } catch (error) {
      vm.health = "unknown";
      throw error;
    }
  }

  get(instanceId) {
    const vm = this.#instances.get(instanceId);
    if (!vm) throw new DeploymentError(`Unknown instance: ${instanceId}`);
    return vm;
  }

  list(state = null) {
    return [...this.#instances.values()]
      .filter(vm => state === null || vm.state === state)
      .map(vm => ({
        id: vm.id,
        name: vm.spec.name,
        state: vm.state,
        region: vm.spec.region,
        instanceType: vm.spec.instanceType,
        privateIp: vm.privateIp,
        publicIp: vm.publicIp,
        health: vm.health,
      }));
  }

  estimateComputeCost(instanceId, hours = 730) {
    if (!Number.isFinite(hours) || hours < 0 || hours > 744) {
      throw new PolicyError("Hours must be between 0 and 744.");
    }
    const vm = this.get(instanceId);
    if (vm.state === STATES.TERMINATED) return 0;
    return Number(
      (INSTANCE_TYPES[vm.spec.instanceType].hourlyRate * hours).toFixed(2)
    );
  }
}

function makeSpecification(name, options = {}) {
  return {
    name,
    instanceType: options.instanceType ?? "medium",
    imageId: "img-linux2026",
    region: "ap-south-1",
    environment: options.environment ?? "development",
    rootDiskGiB: 40,
    encryptedDisk: true,
    monitoringEnabled: true,
    startupScript: "#!/bin/sh\nset -eu\necho service-ready\n",
    network: {
      subnetId: "subnet-prod001",
      securityGroupIds: ["sg-app001"],
      publicIp: options.publicIp ?? false,
      ingressPorts: [443],
    },
  };
}

async function main() {
  const events = new EventBus();
  const adapter = new MockCloudAdapter();
  const controller = new DeploymentController(adapter, events);

  events.on("lifecycle", event => {
    console.log(
      `[${event.action}] ${event.name}: ` +
      `${event.previousState} -> ${event.newState}`
    );
  });

  const api = await controller.deploy(
    makeSpecification("catalog-api"),
    "catalog-deploy-2026"
  );

  // Retrying the same request returns the same instance instead of allocating
  // duplicate compute resources.
  const retried = await controller.deploy(
    makeSpecification("catalog-api"),
    "catalog-deploy-2026"
  );
  console.log("Idempotent retry:", retried.id === api.id);

  console.log("Health check:", await controller.checkHealth(api.id));
  console.log("Estimated monthly compute:", controller.estimateComputeCost(api.id));

  await controller.stop(api.id);
  await controller.start(api.id);
  await controller.restart(api.id);

  // A failed provider call is recorded as a failed instance state, which can
  // be inspected and retried through an explicit start operation.
  adapter.failNext = "stop";
  try {
    await controller.stop(api.id);
  } catch (error) {
    console.log("Expected operational failure:", error.message);
  }

  console.log("Inventory:", JSON.stringify(controller.list(), null, 2));
  console.log("Audit events:", api.audit.length);
}

main().catch(error => {
  console.error("Deployment demonstration failed:", error.message);
  process.exitCode = 1;
});
