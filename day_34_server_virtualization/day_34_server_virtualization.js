'use strict';

/*
 * Server Virtualization: Event-Driven Resource Allocation Model
 *
 * This Node.js-compatible program models virtualization from a JavaScript
 * perspective. It focuses on event-driven VM lifecycle changes, resource
 * reservations, workload demand, policy evaluation, and asynchronous
 * monitoring.
 *
 * It is intentionally not a translation of the Python simulator. JavaScript's
 * event-driven model is used to show how a virtualization management service
 * could react to VM state changes and periodically evaluate host pressure.
 */

const { EventEmitter } = require('node:events');


/* -------------------------------------------------------------------------- */
/* Resource and validation utilities                                           */
/* -------------------------------------------------------------------------- */

class ResourceVector {
    constructor(cpu, memoryGiB, storageGiB, networkMbps) {
        this.cpu = cpu;
        this.memoryGiB = memoryGiB;
        this.storageGiB = storageGiB;
        this.networkMbps = networkMbps;
        this.validate();
    }

    validate() {
        const values = [
            ['cpu', this.cpu],
            ['memoryGiB', this.memoryGiB],
            ['storageGiB', this.storageGiB],
            ['networkMbps', this.networkMbps]
        ];

        for (const [name, value] of values) {
            if (!Number.isFinite(value) || value < 0) {
                throw new RangeError(`${name} must be a finite non-negative number`);
            }
        }

        if (!Number.isInteger(this.cpu)) {
            throw new TypeError('CPU capacity must be an integer');
        }
    }

    add(other) {
        return new ResourceVector(
            this.cpu + other.cpu,
            this.memoryGiB + other.memoryGiB,
            this.storageGiB + other.storageGiB,
            this.networkMbps + other.networkMbps
        );
    }

    exceeds(capacity) {
        return (
            this.cpu > capacity.cpu ||
            this.memoryGiB > capacity.memoryGiB ||
            this.storageGiB > capacity.storageGiB ||
            this.networkMbps > capacity.networkMbps
        );
    }

    utilization(capacity) {
        return {
            cpu: this.cpu / capacity.cpu,
            memory: this.memoryGiB / capacity.memoryGiB,
            storage: this.storageGiB / capacity.storageGiB,
            network: this.networkMbps / capacity.networkMbps
        };
    }
}


/* -------------------------------------------------------------------------- */
/* Virtual machine model                                                       */
/* -------------------------------------------------------------------------- */

class VirtualMachine extends EventEmitter {
    constructor(name, resources, options = {}) {
        super();

        if (!name || !name.trim()) {
            throw new Error('VM name is required');
        }

        this.name = name;
        this.resources = resources;
        this.state = 'stopped';
        this.priority = options.priority ?? 1;
        this.cpuDemand = 0;
        this.memoryDemandGiB = 0;
        this.networkDemandMbps = 0;
        this.snapshots = [];

        if (!Number.isInteger(this.priority) || this.priority < 1 || this.priority > 10) {
            throw new RangeError('VM priority must be an integer from 1 through 10');
        }

        this.setDemand(
            options.cpuDemand ?? 0,
            options.memoryDemandGiB ?? 0,
            options.networkDemandMbps ?? 0
        );
    }

    setDemand(cpu, memoryGiB, networkMbps) {
        if (![cpu, memoryGiB, networkMbps].every(Number.isFinite)) {
            throw new TypeError('Workload demand values must be finite');
        }

        /*
         * A guest cannot request more than its configured virtual resources
         * in this simplified model. Real systems can expose additional
         * mechanisms such as ballooning, hot-add, CPU limits, or memory
         * reclamation.
         */
        this.cpuDemand = Math.max(0, Math.min(cpu, this.resources.cpu));
        this.memoryDemandGiB = Math.max(
            0,
            Math.min(memoryGiB, this.resources.memoryGiB)
        );
        this.networkDemandMbps = Math.max(
            0,
            Math.min(networkMbps, this.resources.networkMbps)
        );
    }

    start() {
        if (this.state === 'running') {
            throw new Error(`${this.name} is already running`);
        }

        this.state = 'running';
        this.emit('stateChanged', {
            vm: this.name,
            state: this.state
        });
    }

    pause() {
        if (this.state !== 'running') {
            throw new Error(`${this.name} must be running before pause`);
        }

        this.state = 'paused';
        this.emit('stateChanged', {
            vm: this.name,
            state: this.state
        });
    }

    resume() {
        if (this.state !== 'paused') {
            throw new Error(`${this.name} is not paused`);
        }

        this.state = 'running';
        this.emit('stateChanged', {
            vm: this.name,
            state: this.state
        });
    }

    stop() {
        this.state = 'stopped';
        this.emit('stateChanged', {
            vm: this.name,
            state: this.state
        });
    }

    createSnapshot(name) {
        if (!name || !name.trim()) {
            throw new Error('Snapshot name is required');
        }

        if (this.snapshots.includes(name)) {
            throw new Error(`Snapshot '${name}' already exists`);
        }

        this.snapshots.push(name);
        this.emit('snapshotCreated', {
            vm: this.name,
            snapshot: name
        });
    }

    currentDemand() {
        if (this.state !== 'running') {
            return new ResourceVector(0, 0, 0, 0);
        }

        return new ResourceVector(
            Math.ceil(this.cpuDemand),
            this.memoryDemandGiB,
            0,
            this.networkDemandMbps
        );
    }
}


/* -------------------------------------------------------------------------- */
/* Physical host                                                               */
/* -------------------------------------------------------------------------- */

class PhysicalHost extends EventEmitter {
    constructor(name, capacity) {
        super();

        if (capacity.cpu <= 0 || capacity.memoryGiB <= 0) {
            throw new Error('A host requires positive CPU and memory capacity');
        }

        this.name = name;
        this.capacity = capacity;
        this.vms = new Map();
    }

    configuredAllocation() {
        let total = new ResourceVector(0, 0, 0, 0);

        for (const vm of this.vms.values()) {
            total = total.add(vm.resources);
        }

        return total;
    }

    runningDemand() {
        let total = new ResourceVector(0, 0, 0, 0);

        for (const vm of this.vms.values()) {
            total = total.add(vm.currentDemand());
        }

        return total;
    }

    addVM(vm, allowOvercommit = false) {
        if (this.vms.has(vm.name)) {
            throw new Error(`VM '${vm.name}' already exists on ${this.name}`);
        }

        const projected = this.configuredAllocation().add(vm.resources);

        if (!allowOvercommit && projected.exceeds(this.capacity)) {
            throw new Error(
                `Adding '${vm.name}' would exceed physical capacity of ${this.name}`
            );
        }

        this.vms.set(vm.name, vm);

        /*
         * EventEmitter is useful here because an orchestration service can
         * react to resource changes without tightly coupling the VM object to
         * every consumer of the event.
         */
        vm.on('stateChanged', event => {
            this.emit('vmStateChanged', {
                host: this.name,
                ...event
            });
        });

        vm.on('snapshotCreated', event => {
            this.emit('snapshotCreated', {
                host: this.name,
                ...event
            });
        });

        this.emit('vmAdded', {
            host: this.name,
            vm: vm.name
        });
    }

    removeVM(vmName) {
        const vm = this.vms.get(vmName);

        if (!vm) {
            throw new Error(`VM '${vmName}' does not exist`);
        }

        if (vm.state !== 'stopped') {
            throw new Error('VM must be stopped before removal');
        }

        this.vms.delete(vmName);

        this.emit('vmRemoved', {
            host: this.name,
            vm: vmName
        });
    }

    report() {
        const allocation = this.configuredAllocation();
        const demand = this.runningDemand();

        return {
            host: this.name,
            capacity: this.capacity,
            allocation,
            demand,
            allocationUtilization: allocation.utilization(this.capacity),
            demandUtilization: demand.utilization(this.capacity),
            allocationOvercommitted: allocation.exceeds(this.capacity),
            demandOverloaded: demand.exceeds(
                new ResourceVector(
                    this.capacity.cpu,
                    this.capacity.memoryGiB,
                    Infinity,
                    this.capacity.networkMbps
                )
            )
        };
    }
}


/* -------------------------------------------------------------------------- */
/* Virtualization policy                                                       */
/* -------------------------------------------------------------------------- */

class PlacementPolicy {
    canPlace(host, vm) {
        throw new Error('PlacementPolicy.canPlace must be implemented');
    }
}


class ReservedCapacityPolicy extends PlacementPolicy {
    canPlace(host, vm) {
        const projected = host.configuredAllocation().add(vm.resources);

        if (projected.exceeds(host.capacity)) {
            return {
                allowed: false,
                reason: 'Configured allocation exceeds physical capacity'
            };
        }

        return {
            allowed: true,
            reason: 'Full configured allocation fits'
        };
    }
}


class BurstablePolicy extends PlacementPolicy {
    constructor(cpuRatio = 2, memoryRatio = 1.5) {
        super();

        if (cpuRatio < 1 || memoryRatio < 1) {
            throw new RangeError('Overcommit ratios cannot be below 1');
        }

        this.cpuRatio = cpuRatio;
        this.memoryRatio = memoryRatio;
    }

    canPlace(host, vm) {
        const projected = host.configuredAllocation().add(vm.resources);

        if (projected.storageGiB > host.capacity.storageGiB) {
            return {
                allowed: false,
                reason: 'Storage cannot be overcommitted by this policy'
            };
        }

        if (projected.networkMbps > host.capacity.networkMbps) {
            return {
                allowed: false,
                reason: 'Network capacity cannot be overcommitted'
            };
        }

        const cpuRatio = projected.cpu / host.capacity.cpu;
        const memoryRatio = projected.memoryGiB / host.capacity.memoryGiB;

        if (cpuRatio > this.cpuRatio) {
            return {
                allowed: false,
                reason: `CPU ratio ${cpuRatio.toFixed(2)} exceeds policy`
            };
        }

        if (memoryRatio > this.memoryRatio) {
            return {
                allowed: false,
                reason: `Memory ratio ${memoryRatio.toFixed(2)} exceeds policy`
            };
        }

        return {
            allowed: true,
            reason: 'Placement satisfies burstable overcommit limits'
        };
    }
}


/* -------------------------------------------------------------------------- */
/* Event-driven management service                                             */
/* -------------------------------------------------------------------------- */

class VirtualizationManager extends EventEmitter {
    constructor(policy) {
        super();
        this.policy = policy;
        this.hosts = new Map();
    }

    registerHost(host) {
        if (this.hosts.has(host.name)) {
            throw new Error(`Host '${host.name}' is already registered`);
        }

        this.hosts.set(host.name, host);

        host.on('vmAdded', event => this.emit('resourceChange', event));
        host.on('vmRemoved', event => this.emit('resourceChange', event));
        host.on('vmStateChanged', event => this.emit('resourceChange', event));
        host.on('snapshotCreated', event => this.emit('auditEvent', event));
    }

    placeVM(vm) {
        const candidates = [];

        for (const host of this.hosts.values()) {
            const decision = this.policy.canPlace(host, vm);

            if (decision.allowed) {
                const projected = host.configuredAllocation().add(vm.resources);
                const utilization = projected.utilization(host.capacity);

                /*
                 * Best-fit scoring favors a host that becomes efficiently
                 * utilized without violating the policy.
                 */
                const score =
                    utilization.cpu +
                    utilization.memory +
                    utilization.storage +
                    utilization.network;

                candidates.push({ host, score });
            }
        }

        if (candidates.length === 0) {
            throw new Error(`No host can place VM '${vm.name}'`);
        }

        candidates.sort((a, b) => a.score - b.score);
        const selected = candidates[0].host;

        const allowOvercommit =
            this.policy instanceof BurstablePolicy;

        selected.addVM(vm, allowOvercommit);

        this.emit('placement', {
            vm: vm.name,
            host: selected.name
        });

        return selected;
    }

    getHost(name) {
        const host = this.hosts.get(name);

        if (!host) {
            throw new Error(`Host '${name}' does not exist`);
        }

        return host;
    }

    async monitorOnce() {
        /*
         * Promise.resolve() makes this method asynchronous without pretending
         * that the simulator is performing real hardware I/O.
         *
         * In a production management plane, this layer could await telemetry
         * from an agent, hypervisor API, or metrics service.
         */
        await Promise.resolve();

        const results = [];

        for (const host of this.hosts.values()) {
            const report = host.report();
            results.push(report);

            if (report.demandOverloaded) {
                this.emit('alert', {
                    type: 'resource-contention',
                    host: host.name,
                    demand: report.demand
                });
            }
        }

        return results;
    }
}


/* -------------------------------------------------------------------------- */
/* CPU contention model                                                        */
/* -------------------------------------------------------------------------- */

function weightedCPUAllocation(host) {
    const activeVMs = [...host.vms.values()].filter(
        vm => vm.state === 'running' && vm.cpuDemand > 0
    );

    const weightedDemand = activeVMs.reduce(
        (sum, vm) => sum + vm.cpuDemand * vm.priority,
        0
    );

    const physicalCPU = host.capacity.cpu;

    if (weightedDemand <= physicalCPU) {
        return Object.fromEntries(
            activeVMs.map(vm => [vm.name, vm.cpuDemand])
        );
    }

    /*
     * When aggregate demand is larger than physical CPU, this simplified
     * scheduler distributes available CPU according to priority-weighted
     * demand. Real schedulers also account for CPU affinity, topology,
     * reservations, limits, time slices, and hypervisor overhead.
     */
    return Object.fromEntries(
        activeVMs.map(vm => [
            vm.name,
            physicalCPU *
            (vm.cpuDemand * vm.priority) /
            weightedDemand
        ])
    );
}


/* -------------------------------------------------------------------------- */
/* Asynchronous workload simulation                                            */
/* -------------------------------------------------------------------------- */

function sleep(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}


async function simulateChangingWorkload(host, cycles = 5) {
    for (let cycle = 1; cycle <= cycles; cycle++) {
        const runningVMs = [...host.vms.values()].filter(
            vm => vm.state === 'running'
        );

        /*
         * Deterministic workload changes make the demonstration reproducible.
         * Demand changes are independent of configured allocation.
         */
        for (const vm of runningVMs) {
            const intensity = 0.35 + ((cycle * 0.13) % 0.60);

            vm.setDemand(
                vm.resources.cpu * intensity,
                vm.resources.memoryGiB * Math.min(1, intensity + 0.20),
                vm.resources.networkMbps * Math.min(1, intensity + 0.10)
            );
        }

        const demand = host.runningDemand();

        console.log(
            `cycle=${cycle} ` +
            `cpu=${demand.cpu}/${host.capacity.cpu} ` +
            `memory=${demand.memoryGiB.toFixed(1)}/${host.capacity.memoryGiB}GiB ` +
            `network=${demand.networkMbps.toFixed(0)}/${host.capacity.networkMbps}Mbps`
        );

        await sleep(25);
    }
}


/* -------------------------------------------------------------------------- */
/* Demonstration                                                               */
/* -------------------------------------------------------------------------- */

async function main() {
    console.log('SERVER VIRTUALIZATION MANAGEMENT MODEL');
    console.log('--------------------------------------');

    const manager = new VirtualizationManager(
        new BurstablePolicy(2.0, 1.5)
    );

    manager.on('placement', event => {
        console.log(
            `[placement] ${event.vm} -> ${event.host}`
        );
    });

    manager.on('resourceChange', event => {
        console.log(
            `[resource-change] ${event.vm ?? 'host event'} on ${event.host}`
        );
    });

    manager.on('auditEvent', event => {
        console.log(
            `[audit] snapshot '${event.snapshot}' created for ${event.vm}`
        );
    });

    manager.on('alert', event => {
        console.log(
            `[ALERT] ${event.type} detected on ${event.host}`
        );
    });

    const hostA = new PhysicalHost(
        'compute-a',
        new ResourceVector(12, 48, 1000, 10000)
    );

    const hostB = new PhysicalHost(
        'compute-b',
        new ResourceVector(16, 64, 1500, 10000)
    );

    manager.registerHost(hostA);
    manager.registerHost(hostB);

    const workloads = [
        new VirtualMachine(
            'frontend',
            new ResourceVector(4, 8, 100, 1000),
            {
                priority: 8,
                cpuDemand: 1.5,
                memoryDemandGiB: 5,
                networkDemandMbps: 400
            }
        ),
        new VirtualMachine(
            'orders-db',
            new ResourceVector(6, 20, 300, 2500),
            {
                priority: 10,
                cpuDemand: 4,
                memoryDemandGiB: 16,
                networkDemandMbps: 800
            }
        ),
        new VirtualMachine(
            'analytics',
            new ResourceVector(8, 16, 250, 1800),
            {
                priority: 3,
                cpuDemand: 2,
                memoryDemandGiB: 8,
                networkDemandMbps: 600
            }
        ),
        new VirtualMachine(
            'development',
            new ResourceVector(4, 8, 100, 800),
            {
                priority: 1,
                cpuDemand: 0.5,
                memoryDemandGiB: 4,
                networkDemandMbps: 100
            }
        )
    ];

    for (const vm of workloads) {
        manager.placeVM(vm);
        vm.start();
    }

    console.log('\nHost resource reports:');

    for (const host of manager.hosts.values()) {
        const report = host.report();

        console.log(
            `${host.name}: ` +
            `configured CPU ${report.allocation.cpu}/${host.capacity.cpu}, ` +
            `RAM ${report.allocation.memoryGiB}/${host.capacity.memoryGiB}GiB, ` +
            `overcommitted=${report.allocationOvercommitted}`
        );
    }

    console.log('\nPriority-weighted CPU scheduling:');

    for (const host of manager.hosts.values()) {
        const allocation = weightedCPUAllocation(host);

        console.log(host.name);

        for (const [vmName, cpu] of Object.entries(allocation)) {
            console.log(`  ${vmName}: ${cpu.toFixed(2)} vCPU`);
        }
    }

    const databaseVM = hostA.vms.get('orders-db') ??
        hostB.vms.get('orders-db');

    if (databaseVM) {
        databaseVM.createSnapshot('pre-maintenance');
        databaseVM.pause();
        databaseVM.resume();
    }

    console.log('\nAsynchronous workload monitoring:');

    for (const host of manager.hosts.values()) {
        await simulateChangingWorkload(host, 3);
    }

    console.log('\nMonitoring service result:');

    const reports = await manager.monitorOnce();

    for (const report of reports) {
        console.log(
            `${report.host}: ` +
            `demand CPU ${report.demand.cpu}, ` +
            `RAM ${report.demand.memoryGiB.toFixed(1)} GiB, ` +
            `network ${report.demand.networkMbps.toFixed(0)} Mbps`
        );
    }

    console.log('\nFailure handling example:');

    try {
        const oversized = new VirtualMachine(
            'oversized',
            new ResourceVector(64, 256, 100, 1000)
        );

        manager.placeVM(oversized);
    } catch (error) {
        /*
         * Management software should treat placement failure as a normal
         * operational condition rather than silently creating an invalid
         * allocation.
         */
        console.log(`Placement rejected: ${error.message}`);
    }

    console.log('\nVirtualization-specific design observations:');
    console.log(
        '- Configured VM resources represent provisioned virtual capacity.'
    );
    console.log(
        '- Runtime demand represents what guests currently consume.'
    );
    console.log(
        '- CPU and memory overcommit can improve density but increases contention risk.'
    );
    console.log(
        '- Event-driven state changes let management software react to VM lifecycle events.'
    );
    console.log(
        '- Resource policies determine whether a host may accept another VM.'
    );
}

main().catch(error => {
    console.error(`Fatal management-plane error: ${error.message}`);
    process.exitCode = 1;
});
