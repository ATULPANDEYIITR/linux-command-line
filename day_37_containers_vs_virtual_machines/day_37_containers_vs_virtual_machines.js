"use strict";

/*
 * Containers vs Virtual Machines
 *
 * This Node.js program models the architectural differences between
 * containers and virtual machines and demonstrates:
 * - event-driven deployment lifecycle
 * - resource accounting
 * - isolation modeling
 * - startup behavior
 * - portability rules
 * - policy evaluation
 * - asynchronous deployment simulation
 * - workload-density analysis
 *
 * The values are educational modeling assumptions. They are not universal
 * benchmarks. Real performance depends on the runtime, hypervisor, kernel,
 * hardware, storage, networking, workload, and configuration.
 */

const { performance } = require("node:perf_hooks");
const { EventEmitter } = require("node:events");

const Workload = Object.freeze({
  WEB_SERVICE: "web-service",
  DATABASE: "database",
  MICROSERVICE: "microservice",
  LEGACY: "legacy-application",
});

class DeploymentError extends Error {
  constructor(message) {
    super(message);
    this.name = "DeploymentError";
  }
}

class RuntimeProfile {
  constructor({
    name,
    kernelModel,
    isolationLevel,
    memoryOverheadMiB,
    cpuOverheadPercent,
    startupSeconds,
    storageOverheadGiB,
    guestKernel,
    hostOsDependency,
  }) {
    this.name = name;
    this.kernelModel = kernelModel;
    this.isolationLevel = isolationLevel;
    this.memoryOverheadMiB = memoryOverheadMiB;
    this.cpuOverheadPercent = cpuOverheadPercent;
    this.startupSeconds = startupSeconds;
    this.storageOverheadGiB = storageOverheadGiB;
    this.guestKernel = guestKernel;
    this.hostOsDependency = hostOsDependency;
  }

  estimateMemoryGiB(applicationMemoryGiB) {
    return applicationMemoryGiB + this.memoryOverheadMiB / 1024;
  }

  estimateCpu(applicationCpu) {
    return applicationCpu * (1 + this.cpuOverheadPercent / 100);
  }
}

const CONTAINER = new RuntimeProfile({
  name: "Container",
  kernelModel: "shared host kernel",
  isolationLevel: 0.72,
  memoryOverheadMiB: 80,
  cpuOverheadPercent: 2,
  startupSeconds: 0.8,
  storageOverheadGiB: 0.15,
  guestKernel: false,
  hostOsDependency: true,
});

const VM = new RuntimeProfile({
  name: "Virtual Machine",
  kernelModel: "independent guest kernel",
  isolationLevel: 0.96,
  memoryOverheadMiB: 900,
  cpuOverheadPercent: 7,
  startupSeconds: 25,
  storageOverheadGiB: 8,
  guestKernel: true,
  hostOsDependency: false,
});

class WorkloadInstance {
  constructor(id, workload, profile, memoryGiB, cpuCores) {
    if (!id || !workload) {
      throw new DeploymentError("Instance ID and workload are required.");
    }
    if (memoryGiB <= 0 || cpuCores <= 0) {
      throw new DeploymentError(
        "Memory and CPU requirements must be positive."
      );
    }

    this.id = id;
    this.workload = workload;
    this.profile = profile;
    this.memoryGiB = memoryGiB;
    this.cpuCores = cpuCores;
    this.state = "created";
    this.startedAt = null;
  }

  estimatedResources() {
    return {
      memoryGiB: this.profile.estimateMemoryGiB(this.memoryGiB),
      cpuCores: this.profile.estimateCpu(this.cpuCores),
      storageGiB: this.profile.storageOverheadGiB,
    };
  }
}

class DeploymentController extends EventEmitter {
  constructor(host) {
    super();
    this.host = host;
    this.instances = new Map();

    this.on("stateChanged", ({ instance, oldState, newState }) => {
      console.log(
        `[event] ${instance.id}: ${oldState} -> ${newState}`
      );
    });
  }

  register(instance) {
    if (this.instances.has(instance.id)) {
      throw new DeploymentError(`Duplicate instance: ${instance.id}`);
    }

    this.instances.set(instance.id, instance);
    this.emit("stateChanged", {
      instance,
      oldState: "unregistered",
      newState: "created",
    });
  }

  async start(instanceId) {
    const instance = this.instances.get(instanceId);

    if (!instance) {
      throw new DeploymentError(`Unknown instance: ${instanceId}`);
    }

    if (instance.state !== "created" && instance.state !== "stopped") {
      throw new DeploymentError(
        `Cannot start ${instance.id} from state ${instance.state}.`
      );
    }

    const oldState = instance.state;
    instance.state = "starting";
    this.emit("stateChanged", {
      instance,
      oldState,
      newState: "starting",
    });

    // setTimeout demonstrates the asynchronous startup nature of deployment.
    // The delay is capped so that the example remains fast to execute.
    const delay = Math.min(instance.profile.startupSeconds * 20, 1000);

    await new Promise((resolve) => setTimeout(resolve, delay));

    const previousState = instance.state;
    instance.state = "running";
    instance.startedAt = new Date();

    this.emit("stateChanged", {
      instance,
      oldState: previousState,
      newState: "running",
    });
  }

  stop(instanceId) {
    const instance = this.instances.get(instanceId);

    if (!instance) {
      throw new DeploymentError(`Unknown instance: ${instanceId}`);
    }

    if (instance.state !== "running") {
      throw new DeploymentError(
        `Cannot stop ${instance.id} from state ${instance.state}.`
      );
    }

    const oldState = instance.state;
    instance.state = "stopped";

    this.emit("stateChanged", {
      instance,
      oldState,
      newState: "stopped",
    });
  }

  resourceReport() {
    const totals = {
      memoryGiB: 0,
      cpuCores: 0,
      storageGiB: 0,
      running: 0,
    };

    for (const instance of this.instances.values()) {
      const resources = instance.estimatedResources();

      totals.memoryGiB += resources.memoryGiB;
      totals.cpuCores += resources.cpuCores;
      totals.storageGiB += resources.storageGiB;

      if (instance.state === "running") {
        totals.running += 1;
      }
    }

    return {
      ...totals,
      memoryUtilization:
        (totals.memoryGiB / this.host.memoryGiB) * 100,
      cpuUtilization:
        (totals.cpuCores / this.host.cpuCores) * 100,
      storageUtilization:
        (totals.storageGiB / this.host.storageGiB) * 100,
    };
  }
}

class Host {
  constructor(name, cpuCores, memoryGiB, storageGiB, kernel) {
    if (cpuCores <= 0 || memoryGiB <= 0 || storageGiB <= 0) {
      throw new Error("Host resources must be positive.");
    }

    this.name = name;
    this.cpuCores = cpuCores;
    this.memoryGiB = memoryGiB;
    this.storageGiB = storageGiB;
    this.kernel = kernel;
  }
}

function printArchitectureComparison() {
  console.log("\n=== Architecture ===");

  console.log("\nContainer");
  console.log("Kernel:", CONTAINER.kernelModel);
  console.log("Isolation score:", CONTAINER.isolationLevel);
  console.log("Guest kernel:", CONTAINER.guestKernel);
  console.log("Host OS dependency:", CONTAINER.hostOsDependency);

  console.log("\nVirtual Machine");
  console.log("Kernel:", VM.kernelModel);
  console.log("Isolation score:", VM.isolationLevel);
  console.log("Guest kernel:", VM.guestKernel);
  console.log("Host OS dependency:", VM.hostOsDependency);

  console.log(
    "\nThe defining distinction is the kernel boundary: containers normally " +
      "share the host kernel, while VMs provide a separate guest kernel."
  );
}

function portabilityAssessment(profile, targetHosts) {
  if (!Array.isArray(targetHosts) || targetHosts.length === 0) {
    throw new DeploymentError("At least one target host is required.");
  }

  let compatible = 0;

  for (const host of targetHosts) {
    if (profile === VM) {
      compatible += 1;
    } else if (host.kernel.startsWith("Linux")) {
      compatible += 1;
    }
  }

  return (compatible / targetHosts.length) * 100;
}

function comparePortability() {
  console.log("\n=== Portability ===");

  const hosts = [
    new Host("Linux node", 16, 64, 500, "Linux 6.12"),
    new Host("Linux cloud node", 32, 128, 1000, "Linux 6.8"),
    new Host("Windows server", 32, 128, 1000, "Windows Server 2025"),
    new Host("BSD host", 16, 64, 500, "FreeBSD 14"),
  ];

  console.log(
    "Container compatibility:",
    portabilityAssessment(CONTAINER, hosts).toFixed(1) + "%"
  );
  console.log(
    "VM compatibility:",
    portabilityAssessment(VM, hosts).toFixed(1) + "%"
  );

  console.log(
    "A VM packages the guest kernel and OS. A container packages the " +
      "application environment but remains dependent on compatible host " +
      "kernel facilities."
  );
}

function resourceDensity(profile, host, count, workload) {
  const controller = new DeploymentController(host);

  for (let i = 1; i <= count; i += 1) {
    controller.register(
      new WorkloadInstance(
        `${profile.name}-${i}`,
        workload,
        profile,
        1,
        0.25
      )
    );
  }

  return controller.resourceReport();
}

function densityExperiment() {
  console.log("\n=== Resource Density ===");

  const host = new Host(
    "Application host",
    16,
    64,
    500,
    "Linux 6.12"
  );

  for (const profile of [CONTAINER, VM]) {
    let maximum = 0;

    for (let count = 1; count <= 200; count += 1) {
      const report = resourceDensity(
        profile,
        host,
        count,
        Workload.MICROSERVICE
      );

      if (
        report.memoryUtilization > 90 ||
        report.cpuUtilization > 90 ||
        report.storageUtilization > 90
      ) {
        break;
      }

      maximum = count;
    }

    console.log(
      `${profile.name}: approximately ${maximum} microservice instances ` +
        "before the modeled 90% resource threshold"
    );
  }
}

async function startupExperiment() {
  console.log("\n=== Asynchronous Startup ===");

  const host = new Host(
    "Startup experiment host",
    8,
    32,
    250,
    "Linux 6.12"
  );

  const controller = new DeploymentController(host);

  for (const [profile, id] of [
    [CONTAINER, "api-container"],
    [VM, "api-vm"],
  ]) {
    controller.register(
      new WorkloadInstance(
        id,
        Workload.WEB_SERVICE,
        profile,
        1,
        0.5
      )
    );
  }

  const started = performance.now();

  await Promise.all([
    controller.start("api-container"),
    controller.start("api-vm"),
  ]);

  const elapsed = performance.now() - started;

  console.log(`Wall-clock simulation time: ${elapsed.toFixed(1)} ms`);
  console.log(
    "The example uses asynchronous JavaScript events to model deployment " +
      "operations without blocking the Node.js event loop."
  );
}

function securityModel() {
  console.log("\n=== Security Boundary ===");

  const controls = [
    {
      control: "Kernel boundary",
      container: "shared host kernel",
      vm: "independent guest kernel",
    },
    {
      control: "Process visibility",
      container: "namespace isolation",
      vm: "guest OS isolation",
    },
    {
      control: "Resource limits",
      container: "cgroups / runtime limits",
      vm: "hypervisor allocation / guest limits",
    },
    {
      control: "Privilege reduction",
      container: "capabilities, seccomp, MAC policies",
      vm: "guest privileges plus hypervisor boundary",
    },
  ];

  for (const item of controls) {
    console.log(`\n${item.control}`);
    console.log(`  Container: ${item.container}`);
    console.log(`  VM:        ${item.vm}`);
  }

  console.log(
    "\nNeither technology should be treated as automatically secure. " +
      "Patch management, least privilege, isolation configuration, image " +
      "integrity, and monitoring remain necessary."
  );
}

function performanceModel(profile) {
  const workload = {
    cpuUnits: 100,
    memoryUnits: 100,
    ioUnits: 100,
  };

  return {
    cpu:
      workload.cpuUnits /
      (1 + profile.cpuOverheadPercent / 100),
    memory:
      workload.memoryUnits -
      profile.memoryOverheadMiB / 1024,
    io:
      workload.ioUnits *
      (1 - Math.min(profile.cpuOverheadPercent / 100, 0.25)),
  };
}

function performanceComparison() {
  console.log("\n=== Performance Model ===");

  for (const profile of [CONTAINER, VM]) {
    const result = performanceModel(profile);

    console.log(
      `${profile.name}: CPU=${result.cpu.toFixed(2)}, ` +
        `memory=${result.memory.toFixed(2)}, ` +
        `I/O=${result.io.toFixed(2)}`
    );
  }

  console.log(
    "\nThe model emphasizes that containers often have lower overhead, " +
      "but modern VMs can achieve near-native performance for many workloads."
  );
}

async function main() {
  printArchitectureComparison();
  comparePortability();
  performanceComparison();
  securityModel();
  densityExperiment();
  await startupExperiment();

  console.log("\n=== Completed ===");
  console.log(
    "Container selection is favored by fast startup, high density, and " +
      "application-centric deployment. VM selection is favored by guest " +
      "kernel independence, stronger isolation boundaries, and heterogeneous OS requirements."
  );
}

main().catch((error) => {
  console.error(`Execution failed: ${error.message}`);
  process.exitCode = 1;
});
