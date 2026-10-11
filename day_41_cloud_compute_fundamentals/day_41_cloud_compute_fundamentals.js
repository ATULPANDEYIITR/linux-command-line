"use strict";

/*
 * Cloud compute provisioning and capacity planning.
 * Run with Node.js 18 or later: node cloud_compute.js
 */

const { EventEmitter } = require("node:events");

const Family = Object.freeze({
  GENERAL: "general-purpose",
  COMPUTE: "compute-optimized",
  MEMORY: "memory-optimized",
  BURSTABLE: "burstable",
  ACCELERATED: "accelerated",
});

const State = Object.freeze({
  REQUESTED: "requested",
  PROVISIONING: "provisioning",
  RUNNING: "running",
  STOPPED: "stopped",
  TERMINATED: "terminated",
  FAILED: "failed",
});

class ComputeError extends Error {}

class InstanceCatalog {
  #types = new Map();

  add(type) {
    if (!type.name || this.#types.has(type.name)) {
      throw new ComputeError(`Missing or duplicate instance type: ${type.name}`);
    }
    if (
      !Number.isInteger(type.vcpus) ||
      type.vcpus <= 0 ||
      !Number.isFinite(type.memoryGiB) ||
      type.memoryGiB <= 0 ||
      !Number.isFinite(type.hourlyRate) ||
      type.hourlyRate < 0
    ) {
      throw new ComputeError(`Invalid resource specification: ${type.name}`);
    }
    this.#types.set(type.name, Object.freeze({ ...type }));
  }

  get(name) {
    const type = this.#types.get(name);
    if (!type) throw new ComputeError(`Unknown instance type: ${name}`);
    return type;
  }

  values() {
    return [...this.#types.values()];
  }

  select({ vcpus, memoryGiB, family, maxHourlyRate = Infinity }) {
    if (vcpus <= 0 || memoryGiB <= 0 || maxHourlyRate < 0) {
      throw new ComputeError("Invalid selection requirements.");
    }

    const candidates = this.values().filter(
      (type) =>
        type.vcpus >= vcpus &&
        type.memoryGiB >= memoryGiB &&
        (!family || type.family === family) &&
        type.hourlyRate <= maxHourlyRate
    );

    candidates.sort(
      (a, b) =>
        a.hourlyRate - b.hourlyRate ||
        a.vcpus - b.vcpus ||
        a.memoryGiB - b.memoryGiB
    );

    if (candidates.length === 0) {
      throw new ComputeError("No catalog entry satisfies the request.");
    }
    return candidates[0];
  }
}

class Host {
  constructor(id, vcpus, memoryGiB, architectures = ["x86_64"]) {
    if (!id || !Number.isInteger(vcpus) || vcpus <= 0 || memoryGiB <= 0) {
      throw new ComputeError("Invalid physical host configuration.");
    }
    this.id = id;
    this.totalVcpus = vcpus;
    this.totalMemoryGiB = memoryGiB;
    this.architectures = new Set(architectures);
    this.reservations = new Map();
  }

  get usedVcpus() {
    return [...this.reservations.values()].reduce(
      (sum, reservation) => sum + reservation.vcpus,
      0
    );
  }

  get usedMemoryGiB() {
    return [...this.reservations.values()].reduce(
      (sum, reservation) => sum + reservation.memoryGiB,
      0
    );
  }

  canFit(type) {
    return (
      this.architectures.has(type.architecture || "x86_64") &&
      this.totalVcpus - this.usedVcpus >= type.vcpus &&
      this.totalMemoryGiB - this.usedMemoryGiB >= type.memoryGiB
    );
  }

  reserve(id, type) {
    if (this.reservations.has(id)) {
      throw new ComputeError(`Duplicate reservation: ${id}`);
    }
    if (!this.canFit(type)) {
      throw new ComputeError(`Insufficient host capacity: ${this.id}`);
    }
    this.reservations.set(id, {
      vcpus: type.vcpus,
      memoryGiB: type.memoryGiB,
    });
  }

  release(id) {
    return this.reservations.delete(id);
  }
}

class ComputeControlPlane extends EventEmitter {
  constructor(catalog, hosts) {
    super();
    this.catalog = catalog;
    this.hosts = hosts;
    this.instances = new Map();
    this.nextId = 1;
  }

  async provision(typeName, workload, { signal, tags = {} } = {}) {
    if (!workload || !workload.trim()) {
      throw new ComputeError("Workload name is required.");
    }
    if (signal?.aborted) {
      throw new ComputeError("Provisioning was cancelled before allocation.");
    }

    const type = this.catalog.get(typeName);
    const id = `vm-${String(this.nextId++).padStart(4, "0")}`;
    const instance = {
      id,
      workload,
      type,
      state: State.REQUESTED,
      hostId: null,
      tags: Object.freeze({ ...tags }),
    };
    this.instances.set(id, instance);
    this.#transition(instance, State.PROVISIONING);

    try {
      // An asynchronous boundary models an external control-plane operation.
      // Cancellation is checked again before resources are reserved.
      await Promise.resolve();
      if (signal?.aborted) throw new ComputeError("Provisioning cancelled.");

      const candidates = [...this.hosts].sort(
        (a, b) =>
          b.totalMemoryGiB -
            b.usedMemoryGiB -
            (a.totalMemoryGiB - a.usedMemoryGiB) ||
          a.id.localeCompare(b.id)
      );
      const host = candidates.find((candidate) => candidate.canFit(type));

      if (!host) {
        throw new ComputeError(`No compatible host for ${typeName}.`);
      }

      host.reserve(id, type);
      instance.hostId = host.id;
      this.#transition(instance, State.RUNNING);
      return this.#snapshot(instance);
    } catch (error) {
      this.#transition(instance, State.FAILED);
      throw error;
    }
  }

  stop(id) {
    const instance = this.#get(id);
    this.#requireState(instance, State.RUNNING);
    this.#transition(instance, State.STOPPED);
    if (instance.hostId) this.#release(instance);
    return this.#snapshot(instance);
  }

  async start(id) {
    const instance = this.#get(id);
    this.#requireState(instance, State.STOPPED);
    this.#transition(instance, State.PROVISIONING);

    try {
      await Promise.resolve();
      const host = this.hosts.find((candidate) =>
        candidate.canFit(instance.type)
      );
      if (!host) throw new ComputeError("No capacity available for restart.");

      host.reserve(id, instance.type);
      instance.hostId = host.id;
      this.#transition(instance, State.RUNNING);
      return this.#snapshot(instance);
    } catch (error) {
      // A failed restart leaves the existing instance stopped, not running
      // without resources and not permanently failed.
      this.#transition(instance, State.STOPPED);
      throw error;
    }
  }

  terminate(id) {
    const instance = this.#get(id);
    if (![State.RUNNING, State.STOPPED, State.FAILED].includes(instance.state)) {
      throw new ComputeError(`Cannot terminate from ${instance.state}.`);
    }
    if (instance.hostId) this.#release(instance);
    this.#transition(instance, State.TERMINATED);
  }

  #release(instance) {
    const host = this.hosts.find((candidate) => candidate.id === instance.hostId);
    if (!host || !host.release(instance.id)) {
      throw new ComputeError(`Resource accounting inconsistency for ${instance.id}`);
    }
    instance.hostId = null;
  }

  #get(id) {
    const instance = this.instances.get(id);
    if (!instance) throw new ComputeError(`Unknown instance: ${id}`);
    return instance;
  }

  #requireState(instance, expected) {
    if (instance.state !== expected) {
      throw new ComputeError(
        `${instance.id} is ${instance.state}; expected ${expected}.`
      );
    }
  }

  #transition(instance, target) {
    const transitions = {
      [State.REQUESTED]: [State.PROVISIONING, State.FAILED],
      [State.PROVISIONING]: [State.RUNNING, State.FAILED, State.STOPPED],
      [State.RUNNING]: [State.STOPPED, State.TERMINATED],
      [State.STOPPED]: [State.PROVISIONING, State.TERMINATED],
      [State.FAILED]: [State.TERMINATED],
      [State.TERMINATED]: [],
    };

    if (!transitions[instance.state].includes(target)) {
      throw new ComputeError(
        `Illegal state transition: ${instance.state} -> ${target}`
      );
    }
    const previous = instance.state;
    instance.state = target;
    this.emit("stateChanged", {
      id: instance.id,
      previous,
      current: target,
    });
  }

  #snapshot(instance) {
    return Object.freeze({
      id: instance.id,
      workload: instance.workload,
      type: instance.type.name,
      vcpus: instance.type.vcpus,
      memoryGiB: instance.type.memoryGiB,
      state: instance.state,
      hostId: instance.hostId,
      tags: instance.tags,
    });
  }
}

function estimateComputeCost(hourlyRate, hours, count = 1) {
  if (
    !Number.isFinite(hourlyRate) ||
    !Number.isFinite(hours) ||
    hourlyRate < 0 ||
    hours < 0 ||
    !Number.isInteger(count) ||
    count < 1
  ) {
    throw new ComputeError("Invalid compute-cost inputs.");
  }
  return Number((hourlyRate * hours * count).toFixed(4));
}

async function main() {
  const catalog = new InstanceCatalog();
  [
    {
      name: "general-medium",
      family: Family.GENERAL,
      vcpus: 4,
      memoryGiB: 16,
      hourlyRate: 0.16,
      architecture: "x86_64",
    },
    {
      name: "compute-large",
      family: Family.COMPUTE,
      vcpus: 8,
      memoryGiB: 16,
      hourlyRate: 0.24,
      architecture: "x86_64",
    },
    {
      name: "memory-large",
      family: Family.MEMORY,
      vcpus: 4,
      memoryGiB: 32,
      hourlyRate: 0.22,
      architecture: "x86_64",
    },
    {
      name: "arm-burst",
      family: Family.BURSTABLE,
      vcpus: 2,
      memoryGiB: 4,
      hourlyRate: 0.035,
      architecture: "arm64",
    },
  ].forEach((type) => catalog.add(type));

  const hosts = [
    new Host("rack-a-node-1", 16, 64, ["x86_64", "arm64"]),
    new Host("rack-b-node-1", 8, 32, ["x86_64"]),
  ];
  const cloud = new ComputeControlPlane(catalog, hosts);

  // Event listeners make lifecycle transitions observable by audit systems.
  cloud.on("stateChanged", (event) => {
    console.log(
      `[event] ${event.id}: ${event.previous} -> ${event.current}`
    );
  });

  const selection = catalog.select({
    vcpus: 4,
    memoryGiB: 24,
    family: Family.MEMORY,
    maxHourlyRate: 0.3,
  });
  console.log("Selected database size:", selection.name);

  const database = await cloud.provision("memory-large", "orders-database", {
    tags: { environment: "production", owner: "data-platform" },
  });
  console.log("Database allocation:", database);

  const api = await cloud.provision("general-medium", "orders-api");
  console.log("API allocation:", api);

  console.log(
    "Three general-medium instances for 8 hours:",
    `$${estimateComputeCost(0.16, 8, 3).toFixed(2)}`
  );

  cloud.stop(api.id);
  await cloud.start(api.id);
  cloud.terminate(api.id);
  cloud.terminate(database.id);

  try {
    await cloud.provision("missing-size", "invalid-request");
  } catch (error) {
    console.log("Expected failure:", error.message);
  }

  console.log("\nHost utilization");
  for (const host of hosts) {
    console.log({
      host: host.id,
      usedVcpus: host.usedVcpus,
      freeVcpus: host.totalVcpus - host.usedVcpus,
      usedMemoryGiB: host.usedMemoryGiB,
      freeMemoryGiB: host.totalMemoryGiB - host.usedMemoryGiB,
    });
  }
}

main().catch((error) => {
  console.error("Compute control plane failed:", error);
  process.exitCode = 1;
});
