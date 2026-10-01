/**
 * Introduction to Virtualization
 *
 * A self-contained Node.js demonstration of:
 * - Physical server resource abstraction
 * - Virtual machines and lifecycle events
 * - Hypervisor resource allocation
 * - Event-driven VM operations
 * - Resource utilization
 * - CPU scheduling and contention
 * - Capacity policies
 * - Protected resource boundaries
 *
 * Run with:
 *   node virtualization.js
 */

"use strict";

const { EventEmitter } = require("node:events");

function heading(title) {
    console.log(`\n${"=".repeat(78)}\n${title}\n${"=".repeat(78)}`);
}

function subheading(title) {
    console.log(`\n--- ${title} ---`);
}

// ---------------------------------------------------------------------------
// Physical infrastructure
// ---------------------------------------------------------------------------

class PhysicalServer {
    constructor({ name, cpuCores, memoryGiB, storageGiB, networkGbps }) {
        if (cpuCores <= 0 || memoryGiB <= 0 || storageGiB <= 0 || networkGbps <= 0) {
            throw new Error("Physical server resources must be positive.");
        }

        this.name = name;
        this.cpuCores = cpuCores;
        this.memoryGiB = memoryGiB;
        this.storageGiB = storageGiB;
        this.networkGbps = networkGbps;
    }

    describe() {
        console.log(`Physical server: ${this.name}`);
        console.log(`  CPU: ${this.cpuCores} cores`);
        console.log(`  Memory: ${this.memoryGiB} GiB`);
        console.log(`  Storage: ${this.storageGiB} GiB`);
        console.log(`  Network: ${this.networkGbps} Gbps`);
    }
}

// ---------------------------------------------------------------------------
// Virtual machine model
// ---------------------------------------------------------------------------

class VirtualMachine extends EventEmitter {
    constructor({ name, operatingSystem, cpuCores, memoryGiB, storageGiB, networkGbps }) {
        super();

        if (!name || !operatingSystem) {
            throw new Error("VM name and operating system are required.");
        }

        if (cpuCores <= 0 || memoryGiB <= 0 || storageGiB <= 0 || networkGbps <= 0) {
            throw new Error("Virtual resource allocations must be positive.");
        }

        this.name = name;
        this.operatingSystem = operatingSystem;
        this.resources = {
            cpuCores,
            memoryGiB,
            storageGiB,
            networkGbps
        };

        this.state = "stopped";
        this.utilization = {
            cpu: 0,
            memory: 0,
            storage: 0,
            network: 0
        };
    }

    start() {
        if (this.state === "running") {
            throw new Error(`${this.name} is already running.`);
        }

        this.state = "running";
        this.emit("started", { vm: this.name });
    }

    stop() {
        if (this.state === "stopped") {
            throw new Error(`${this.name} is already stopped.`);
        }

        this.state = "stopped";
        this.emit("stopped", { vm: this.name });
    }

    pause() {
        if (this.state !== "running") {
            throw new Error(`${this.name} can only be paused while running.`);
        }

        this.state = "paused";
        this.emit("paused", { vm: this.name });
    }

    resume() {
        if (this.state !== "paused") {
            throw new Error(`${this.name} can only be resumed from paused state.`);
        }

        this.state = "running";
        this.emit("resumed", { vm: this.name });
    }

    setUtilization({ cpu, memory, storage, network }) {
        const values = { cpu, memory, storage, network };

        for (const [resource, value] of Object.entries(values)) {
            if (!Number.isFinite(value) || value < 0 || value > 100) {
                throw new Error(`${resource} utilization must be between 0 and 100.`);
            }
        }

        this.utilization = values;
    }

    currentUsage() {
        if (this.state !== "running") {
            return {
                cpuCores: 0,
                memoryGiB: 0,
                storageGiB: 0,
                networkGbps: 0
            };
        }

        return {
            cpuCores: Math.ceil(this.resources.cpuCores * this.utilization.cpu / 100),
            memoryGiB: Math.ceil(this.resources.memoryGiB * this.utilization.memory / 100),
            storageGiB: Math.ceil(this.resources.storageGiB * this.utilization.storage / 100),
            networkGbps: this.resources.networkGbps * this.utilization.network / 100
        };
    }
}

// ---------------------------------------------------------------------------
// Hypervisor
// ---------------------------------------------------------------------------

class Hypervisor extends EventEmitter {
    constructor(host, { allowCpuOvercommit = true } = {}) {
        super();

        this.host = host;
        this.allowCpuOvercommit = allowCpuOvercommit;
        this.vms = new Map();
    }

    createVM(config) {
        if (this.vms.has(config.name)) {
            throw new Error(`VM ${config.name} already exists.`);
        }

        const vm = new VirtualMachine(config);
        this.validateResourceRequest(vm.resources);

        // Events make VM lifecycle changes observable to management software.
        vm.on("started", event => this.emit("vmStarted", event));
        vm.on("stopped", event => this.emit("vmStopped", event));
        vm.on("paused", event => this.emit("vmPaused", event));
        vm.on("resumed", event => this.emit("vmResumed", event));

        this.vms.set(vm.name, vm);
        this.emit("vmCreated", { vm: vm.name });

        return vm;
    }

    validateResourceRequest(resources) {
        if (resources.memoryGiB > this.host.memoryGiB) {
            throw new Error("Requested VM memory exceeds physical host memory.");
        }

        if (resources.storageGiB > this.host.storageGiB) {
            throw new Error("Requested VM storage exceeds physical storage.");
        }

        if (resources.networkGbps > this.host.networkGbps) {
            throw new Error("Requested VM network capacity exceeds host capacity.");
        }

        const allocatedCpu = this.totalAllocated().cpuCores + resources.cpuCores;

        if (!this.allowCpuOvercommit && allocatedCpu > this.host.cpuCores) {
            throw new Error("CPU allocation exceeds host capacity.");
        }

        const allocatedMemory = this.totalAllocated().memoryGiB + resources.memoryGiB;

        if (allocatedMemory > this.host.memoryGiB) {
            throw new Error("Memory allocation exceeds host capacity.");
        }

        const allocatedStorage = this.totalAllocated().storageGiB + resources.storageGiB;

        if (allocatedStorage > this.host.storageGiB) {
            throw new Error("Storage allocation exceeds host capacity.");
        }

        const allocatedNetwork =
            this.totalAllocated().networkGbps + resources.networkGbps;

        if (allocatedNetwork > this.host.networkGbps) {
            throw new Error("Network allocation exceeds host capacity.");
        }
    }

    totalAllocated() {
        const total = {
            cpuCores: 0,
            memoryGiB: 0,
            storageGiB: 0,
            networkGbps: 0
        };

        for (const vm of this.vms.values()) {
            total.cpuCores += vm.resources.cpuCores;
            total.memoryGiB += vm.resources.memoryGiB;
            total.storageGiB += vm.resources.storageGiB;
            total.networkGbps += vm.resources.networkGbps;
        }

        return total;
    }

    totalCurrentUsage() {
        const total = {
            cpuCores: 0,
            memoryGiB: 0,
            storageGiB: 0,
            networkGbps: 0
        };

        for (const vm of this.vms.values()) {
            const usage = vm.currentUsage();
            total.cpuCores += usage.cpuCores;
            total.memoryGiB += usage.memoryGiB;
            total.storageGiB += usage.storageGiB;
            total.networkGbps += usage.networkGbps;
        }

        return total;
    }

    capacityStatus() {
        const allocated = this.totalAllocated();

        return {
            cpu: this.allowCpuOvercommit || allocated.cpuCores <= this.host.cpuCores,
            memory: allocated.memoryGiB <= this.host.memoryGiB,
            storage: allocated.storageGiB <= this.host.storageGiB,
            network: allocated.networkGbps <= this.host.networkGbps
        };
    }

    printReport() {
        const allocated = this.totalAllocated();
        const current = this.totalCurrentUsage();
        const status = this.capacityStatus();

        console.log(`Host: ${this.host.name}`);
        console.log(
            `  CPU: ${allocated.cpuCores} virtual / ` +
            `${this.host.cpuCores} physical / ` +
            `${current.cpuCores} active`
        );
        console.log(
            `  Memory: ${allocated.memoryGiB} GiB allocated / ` +
            `${this.host.memoryGiB} GiB physical / ` +
            `${current.memoryGiB} GiB active`
        );
        console.log(
            `  Storage: ${allocated.storageGiB} GiB allocated / ` +
            `${this.host.storageGiB} GiB physical`
        );
        console.log(
            `  Network: ${allocated.networkGbps.toFixed(1)} Gbps allocated / ` +
            `${this.host.networkGbps.toFixed(1)} Gbps physical`
        );

        console.log("  Capacity policy:");
        for (const [resource, passed] of Object.entries(status)) {
            console.log(`    ${resource.padEnd(8)} ${passed ? "PASS" : "FAIL"}`);
        }
    }
}

// ---------------------------------------------------------------------------
// CPU scheduling
// ---------------------------------------------------------------------------

function proportionalCpuSchedule(physicalCores, demandByVm) {
    if (physicalCores <= 0) {
        throw new Error("Physical CPU capacity must be positive.");
    }

    const cleanDemand = Object.fromEntries(
        Object.entries(demandByVm).map(([name, demand]) => [
            name,
            Math.max(0, Number(demand))
        ])
    );

    const totalDemand = Object.values(cleanDemand)
        .reduce((sum, demand) => sum + demand, 0);

    if (totalDemand === 0) {
        return Object.fromEntries(
            Object.keys(cleanDemand).map(name => [name, 0])
        );
    }

    if (totalDemand <= physicalCores) {
        return cleanDemand;
    }

    const factor = physicalCores / totalDemand;

    return Object.fromEntries(
        Object.entries(cleanDemand).map(([name, demand]) => [
            name,
            demand * factor
        ])
    );
}

// ---------------------------------------------------------------------------
// Event-driven management demonstration
// ---------------------------------------------------------------------------

function demonstrateEventDrivenLifecycle() {
    heading("Event-Driven Virtual Machine Lifecycle");

    const host = new PhysicalServer({
        name: "node-01",
        cpuCores: 12,
        memoryGiB: 48,
        storageGiB: 800,
        networkGbps: 10
    });

    const hypervisor = new Hypervisor(host);

    // Node.js EventEmitter models how management software can react to
    // asynchronous lifecycle events instead of repeatedly polling state.
    hypervisor.on("vmCreated", event => {
        console.log(`[event] VM created: ${event.vm}`);
    });

    hypervisor.on("vmStarted", event => {
        console.log(`[event] VM started: ${event.vm}`);
    });

    hypervisor.on("vmPaused", event => {
        console.log(`[event] VM paused: ${event.vm}`);
    });

    hypervisor.on("vmStopped", event => {
        console.log(`[event] VM stopped: ${event.vm}`);
    });

    const vm = hypervisor.createVM({
        name: "api-server",
        operatingSystem: "Linux",
        cpuCores: 4,
        memoryGiB: 12,
        storageGiB: 100,
        networkGbps: 2
    });

    vm.start();
    vm.pause();
    vm.resume();
    vm.stop();
}

// ---------------------------------------------------------------------------
// Resource abstraction demonstration
// ---------------------------------------------------------------------------

function demonstrateAbstraction() {
    heading("Physical Hardware and Virtual Resource Abstraction");

    const host = new PhysicalServer({
        name: "production-host",
        cpuCores: 16,
        memoryGiB: 64,
        storageGiB: 1200,
        networkGbps: 10
    });

    host.describe();

    const hypervisor = new Hypervisor(host);

    const web = hypervisor.createVM({
        name: "web",
        operatingSystem: "Linux",
        cpuCores: 4,
        memoryGiB: 16,
        storageGiB: 120,
        networkGbps: 2
    });

    const database = hypervisor.createVM({
        name: "database",
        operatingSystem: "Linux",
        cpuCores: 6,
        memoryGiB: 24,
        storageGiB: 300,
        networkGbps: 4
    });

    const monitoring = hypervisor.createVM({
        name: "monitoring",
        operatingSystem: "Linux",
        cpuCores: 4,
        memoryGiB: 8,
        storageGiB: 100,
        networkGbps: 1
    });

    web.start();
    database.start();
    monitoring.start();

    web.setUtilization({
        cpu: 30,
        memory: 45,
        storage: 20,
        network: 10
    });

    database.setUtilization({
        cpu: 75,
        memory: 80,
        storage: 65,
        network: 50
    });

    monitoring.setUtilization({
        cpu: 15,
        memory: 40,
        storage: 25,
        network: 15
    });

    subheading("Virtual resource allocation");

    for (const vm of hypervisor.vms.values()) {
        console.log(
            `${vm.name.padEnd(12)} ` +
            `vCPU=${vm.resources.cpuCores} ` +
            `RAM=${vm.resources.memoryGiB} GiB ` +
            `disk=${vm.resources.storageGiB} GiB ` +
            `state=${vm.state}`
        );
    }

    subheading("Host resource report");
    hypervisor.printReport();

    console.log(
        "\nThe virtual machines are separate resource consumers, but the "
        + "hypervisor maps those virtual resources onto the same physical host."
    );
}

// ---------------------------------------------------------------------------
// Scheduling demonstration
// ---------------------------------------------------------------------------

function demonstrateScheduling() {
    heading("CPU Scheduling Under Contention");

    const demands = {
        web: 2,
        database: 5,
        analytics: 4
    };

    const allocation = proportionalCpuSchedule(8, demands);

    console.log("CPU demand:");
    for (const [name, demand] of Object.entries(demands)) {
        console.log(`  ${name.padEnd(10)} ${demand.toFixed(2)} cores`);
    }

    console.log("\nIllustrative scheduled CPU capacity:");

    for (const [name, value] of Object.entries(allocation)) {
        console.log(`  ${name.padEnd(10)} ${value.toFixed(2)} cores`);
    }

    console.log(
        "\nThe requested workload needs more CPU than the host can execute "
        + "simultaneously, so a simplified proportional scheduler shares "
        + "the finite physical CPU capacity."
    );
}

// ---------------------------------------------------------------------------
// Validation and failure behavior
// ---------------------------------------------------------------------------

function demonstrateFailures() {
    heading("Validation and Failure Conditions");

    const host = new PhysicalServer({
        name: "small-host",
        cpuCores: 8,
        memoryGiB: 16,
        storageGiB: 500,
        networkGbps: 2
    });

    const hypervisor = new Hypervisor(host);

    const invalidRequests = [
        {
            label: "memory exceeds host",
            name: "memory-heavy",
            cpuCores: 2,
            memoryGiB: 32,
            storageGiB: 50,
            networkGbps: 0.5
        },
        {
            label: "storage exceeds host",
            name: "storage-heavy",
            cpuCores: 2,
            memoryGiB: 4,
            storageGiB: 700,
            networkGbps: 0.5
        },
        {
            label: "network exceeds host",
            name: "network-heavy",
            cpuCores: 2,
            memoryGiB: 4,
            storageGiB: 50,
            networkGbps: 5
        }
    ];

    for (const request of invalidRequests) {
        try {
            hypervisor.createVM({
                name: request.name,
                operatingSystem: "Linux",
                cpuCores: request.cpuCores,
                memoryGiB: request.memoryGiB,
                storageGiB: request.storageGiB,
                networkGbps: request.networkGbps
            });
        } catch (error) {
            console.log(`${request.label}: rejected`);
            console.log(`  ${error.message}`);
        }
    }
}

// ---------------------------------------------------------------------------
// Virtualization benefits
// ---------------------------------------------------------------------------

function demonstrateBenefits() {
    heading("Virtualization Benefits and Trade-offs");

    const workloadProfiles = [
        { name: "web", cpu: 2, memory: 8 },
        { name: "database", cpu: 6, memory: 20 },
        { name: "analytics", cpu: 4, memory: 12 }
    ];

    const dedicatedCpu = workloadProfiles
        .reduce((sum, workload) => sum + workload.cpu, 0);

    const dedicatedMemory = workloadProfiles
        .reduce((sum, workload) => sum + workload.memory, 0);

    console.log(
        `Dedicated workload capacity: ${dedicatedCpu} CPU cores, ` +
        `${dedicatedMemory} GiB memory`
    );

    console.log(
        "\nConsolidation can place these workloads into a shared resource pool. "
        + "The operational advantage comes from pooling capacity rather than "
        + "from creating additional physical resources."
    );

    console.log("\nImportant production considerations:");

    console.log(
        "Resource efficiency: shared hosts can raise utilization when workloads "
        + "have different demand patterns."
    );

    console.log(
        "Isolation: VMs separate guest operating-system environments, but the "
        + "hypervisor and physical host remain shared infrastructure."
    );

    console.log(
        "Availability: consolidation reduces hardware sprawl but can enlarge "
        + "the failure domain if several critical VMs depend on one host."
    );

    console.log(
        "Performance: CPU, memory bandwidth, storage I/O, and network capacity "
        + "can become contention points under simultaneous peak demand."
    );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
    console.log("INTRODUCTION TO VIRTUALIZATION");
    console.log(
        "A practical Node.js model of physical servers, virtual machines, "
        + "resource abstraction, scheduling, and virtualization trade-offs."
    );

    demonstrateAbstraction();
    demonstrateEventDrivenLifecycle();
    demonstrateScheduling();
    demonstrateFailures();
    demonstrateBenefits();
}

main();
