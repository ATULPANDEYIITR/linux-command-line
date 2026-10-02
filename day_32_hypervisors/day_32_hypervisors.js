'use strict';

/*
 * Hypervisors: Type 1, Type 2, and Virtual Machine Management
 *
 * This Node.js program models virtualization management rather than creating
 * real virtual machines. It focuses on JavaScript-specific event-driven
 * lifecycle management, policy validation, resource accounting, snapshots,
 * and asynchronous management operations.
 *
 * Real hypervisors additionally interact with CPU virtualization extensions,
 * memory translation hardware, device emulation, storage systems, and
 * virtual network devices.
 */

const crypto = require('crypto');
const { EventEmitter } = require('events');


/* -------------------------------------------------------------------------
 * Enumerations and resource models
 * ---------------------------------------------------------------------- */

const HypervisorType = Object.freeze({
    TYPE_1: 'Type 1 / bare-metal',
    TYPE_2: 'Type 2 / hosted'
});

const VMState = Object.freeze({
    CREATED: 'created',
    RUNNING: 'running',
    PAUSED: 'paused',
    STOPPED: 'stopped',
    DESTROYED: 'destroyed'
});

const NetworkMode = Object.freeze({
    NAT: 'nat',
    BRIDGED: 'bridged',
    HOST_ONLY: 'host-only'
});


class HostResources {
    constructor(cpuCores, memoryMB, storageGB) {
        if (!Number.isInteger(cpuCores) || cpuCores <= 0) {
            throw new Error('CPU core count must be a positive integer.');
        }

        if (!Number.isInteger(memoryMB) || memoryMB <= 0) {
            throw new Error('Host memory must be positive.');
        }

        if (!Number.isInteger(storageGB) || storageGB <= 0) {
            throw new Error('Host storage must be positive.');
        }

        this.cpuCores = cpuCores;
        this.memoryMB = memoryMB;
        this.storageGB = storageGB;
    }
}


class VirtualDisk {
    constructor(path, capacityGB, options = {}) {
        if (!Number.isInteger(capacityGB) || capacityGB <= 0) {
            throw new Error('Virtual disk capacity must be positive.');
        }

        this.path = path;
        this.capacityGB = capacityGB;
        this.usedGB = 0;
        this.bus = options.bus ?? 'virtio';
        this.thinProvisioned = options.thinProvisioned ?? true;
    }

    write(amountGB) {
        if (!Number.isInteger(amountGB) || amountGB < 0) {
            throw new Error('Disk write amount must be a non-negative integer.');
        }

        if (this.usedGB + amountGB > this.capacityGB) {
            throw new Error(`Insufficient capacity on ${this.path}.`);
        }

        this.usedGB += amountGB;
    }
}


class VirtualNIC {
    constructor(name, macAddress, networkMode = NetworkMode.NAT) {
        this.name = name;
        this.macAddress = macAddress;
        this.networkMode = networkMode;
        this.connected = true;
    }

    disconnect() {
        this.connected = false;
    }

    connect() {
        this.connected = true;
    }
}


class VirtualMachine {
    constructor({ name, vcpus, memoryMB, storageGB, guestOS }) {
        if (!name || typeof name !== 'string') {
            throw new Error('VM name is required.');
        }

        if (!Number.isInteger(vcpus) || vcpus <= 0) {
            throw new Error('vCPU count must be positive.');
        }

        if (!Number.isInteger(memoryMB) || memoryMB < 128) {
            throw new Error('VM memory must be at least 128 MB.');
        }

        if (!Number.isInteger(storageGB) || storageGB <= 0) {
            throw new Error('VM storage must be positive.');
        }

        this.id = crypto.randomUUID();
        this.name = name;
        this.vcpus = vcpus;
        this.memoryMB = memoryMB;
        this.storageGB = storageGB;
        this.guestOS = guestOS;
        this.state = VMState.CREATED;
        this.disks = [];
        this.nics = [];
        this.snapshots = new Map();
        this.cpuTimeMS = 0;
    }

    attachDisk(disk) {
        this.ensureMutable();
        this.disks.push(disk);
    }

    attachNIC(nic) {
        this.ensureMutable();
        this.nics.push(nic);
    }

    start() {
        if (
            this.state === VMState.CREATED ||
            this.state === VMState.STOPPED ||
            this.state === VMState.PAUSED
        ) {
            this.state = VMState.RUNNING;
            return;
        }

        if (this.state === VMState.RUNNING) {
            return;
        }

        throw new Error('Destroyed VM cannot be started.');
    }

    pause() {
        if (this.state !== VMState.RUNNING) {
            throw new Error('Only a running VM can be paused.');
        }

        this.state = VMState.PAUSED;
    }

    resume() {
        if (this.state !== VMState.PAUSED) {
            throw new Error('Only a paused VM can be resumed.');
        }

        this.state = VMState.RUNNING;
    }

    shutdown() {
        if (
            this.state === VMState.RUNNING ||
            this.state === VMState.PAUSED
        ) {
            this.state = VMState.STOPPED;
        }
    }

    destroy() {
        this.state = VMState.DESTROYED;
    }

    createSnapshot(name) {
        this.ensureMutable();

        const snapshot = {
            id: crypto.randomUUID(),
            name,
            state: this.state,
            vcpus: this.vcpus,
            memoryMB: this.memoryMB,
            diskUsage: new Map(
                this.disks.map(disk => [disk.path, disk.usedGB])
            ),
            createdAt: new Date().toISOString()
        };

        this.snapshots.set(snapshot.id, snapshot);
        return snapshot;
    }

    restoreSnapshot(snapshotID) {
        const snapshot = this.snapshots.get(snapshotID);

        if (!snapshot) {
            throw new Error('Snapshot does not exist.');
        }

        this.vcpus = snapshot.vcpus;
        this.memoryMB = snapshot.memoryMB;

        for (const disk of this.disks) {
            if (snapshot.diskUsage.has(disk.path)) {
                disk.usedGB = snapshot.diskUsage.get(disk.path);
            }
        }

        this.state = snapshot.state;
    }

    ensureMutable() {
        if (this.state === VMState.DESTROYED) {
            throw new Error('Destroyed VM cannot be modified.');
        }
    }

    status() {
        return {
            id: this.id,
            name: this.name,
            state: this.state,
            guestOS: this.guestOS,
            vcpus: this.vcpus,
            memoryMB: this.memoryMB,
            storageGB: this.disks.reduce(
                (total, disk) => total + disk.capacityGB,
                0
            ),
            networkInterfaces: this.nics.length,
            snapshots: this.snapshots.size
        };
    }
}


/* -------------------------------------------------------------------------
 * Event-driven hypervisor management
 * ---------------------------------------------------------------------- */

class Hypervisor extends EventEmitter {
    constructor({
        name,
        type,
        resources,
        allowMemoryOvercommit = false
    }) {
        super();

        this.name = name;
        this.type = type;
        this.resources = resources;
        this.allowMemoryOvercommit = allowMemoryOvercommit;
        this.vms = new Map();

        /*
         * EventEmitter is useful here because real management platforms are
         * event-driven: VM creation, state transitions, network changes,
         * storage operations, and failures can trigger audit or automation
         * handlers without coupling those handlers to VM logic.
         */
    }

    get allocatedCPU() {
        return [...this.vms.values()]
            .filter(vm => vm.state !== VMState.DESTROYED)
            .reduce((sum, vm) => sum + vm.vcpus, 0);
    }

    get allocatedMemoryMB() {
        return [...this.vms.values()]
            .filter(vm => vm.state !== VMState.DESTROYED)
            .reduce((sum, vm) => sum + vm.memoryMB, 0);
    }

    get allocatedStorageGB() {
        return [...this.vms.values()]
            .filter(vm => vm.state !== VMState.DESTROYED)
            .reduce(
                (sum, vm) => sum + vm.storageGB,
                0
            );
    }

    validateResources(vcpus, memoryMB, storageGB) {
        if (this.allocatedCPU + vcpus > this.resources.cpuCores) {
            return {
                allowed: false,
                reason: 'CPU capacity exceeded.'
            };
        }

        if (
            !this.allowMemoryOvercommit &&
            this.allocatedMemoryMB + memoryMB > this.resources.memoryMB
        ) {
            return {
                allowed: false,
                reason: 'Memory capacity exceeded.'
            };
        }

        if (
            this.allocatedStorageGB + storageGB >
            this.resources.storageGB
        ) {
            return {
                allowed: false,
                reason: 'Storage capacity exceeded.'
            };
        }

        return {
            allowed: true,
            reason: 'Resources available.'
        };
    }

    createVM(config) {
        if ([...this.vms.values()].some(vm => vm.name === config.name)) {
            throw new Error(`VM name already exists: ${config.name}`);
        }

        const validation = this.validateResources(
            config.vcpus,
            config.memoryMB,
            config.storageGB
        );

        if (!validation.allowed) {
            throw new Error(validation.reason);
        }

        const vm = new VirtualMachine(config);

        vm.attachDisk(
            new VirtualDisk(
                `/virtual-disks/${config.name}.qcow2`,
                config.storageGB
            )
        );

        vm.attachNIC(
            new VirtualNIC(
                `${config.name}-nic0`,
                this.generateMAC(vm.id),
                NetworkMode.NAT
            )
        );

        this.vms.set(vm.id, vm);

        this.emit('vmCreated', vm.status());

        return vm;
    }

    generateMAC(seed) {
        const digest = crypto
            .createHash('sha256')
            .update(seed)
            .digest();

        const bytes = [
            0x52,
            0x54,
            0x00,
            digest[0],
            digest[1],
            digest[2]
        ];

        return bytes
            .map(byte => byte.toString(16).padStart(2, '0'))
            .join(':');
    }

    changeState(vm, operation) {
        const previous = vm.state;
        operation();
        const current = vm.state;

        if (previous !== current) {
            this.emit('stateChanged', {
                vmID: vm.id,
                vmName: vm.name,
                previous,
                current
            });
        }
    }

    startVM(vmID) {
        const vm = this.getVM(vmID);
        this.changeState(vm, () => vm.start());
    }

    pauseVM(vmID) {
        const vm = this.getVM(vmID);
        this.changeState(vm, () => vm.pause());
    }

    resumeVM(vmID) {
        const vm = this.getVM(vmID);
        this.changeState(vm, () => vm.resume());
    }

    shutdownVM(vmID) {
        const vm = this.getVM(vmID);
        this.changeState(vm, () => vm.shutdown());
    }

    destroyVM(vmID) {
        const vm = this.getVM(vmID);
        this.changeState(vm, () => vm.destroy());
        this.emit('vmDestroyed', vm.status());
    }

    getVM(vmID) {
        const vm = this.vms.get(vmID);

        if (!vm) {
            throw new Error(`Unknown VM: ${vmID}`);
        }

        return vm;
    }

    listVMs() {
        return [...this.vms.values()]
            .filter(vm => vm.state !== VMState.DESTROYED)
            .map(vm => vm.status());
    }

    scheduleCPU(quantumMS = 10) {
        const running = [...this.vms.values()]
            .filter(vm => vm.state === VMState.RUNNING);

        for (const vm of running) {
            const usableVCPUs = Math.min(
                vm.vcpus,
                this.resources.cpuCores
            );

            vm.cpuTimeMS += quantumMS * usableVCPUs;
        }

        this.emit('cpuScheduled', {
            quantumMS,
            runningVMs: running.length
        });
    }

    memoryPressure() {
        return this.allocatedMemoryMB / this.resources.memoryMB;
    }

    summary() {
        return {
            name: this.name,
            type: this.type,
            resources: this.resources,
            allocatedCPU: this.allocatedCPU,
            allocatedMemoryMB: this.allocatedMemoryMB,
            allocatedStorageGB: this.allocatedStorageGB,
            memoryPressure: Number(this.memoryPressure().toFixed(3)),
            vmCount: this.listVMs().length
        };
    }
}


/* -------------------------------------------------------------------------
 * Asynchronous management API
 * ---------------------------------------------------------------------- */

class ManagementController {
    constructor(hypervisor) {
        this.hypervisor = hypervisor;
        this.auditLog = [];

        this.hypervisor.on('vmCreated', event => {
            this.record('VM_CREATED', event);
        });

        this.hypervisor.on('stateChanged', event => {
            this.record('STATE_CHANGED', event);
        });

        this.hypervisor.on('vmDestroyed', event => {
            this.record('VM_DESTROYED', event);
        });
    }

    record(action, details) {
        this.auditLog.push({
            timestamp: new Date().toISOString(),
            action,
            details
        });
    }

    async provisionVM(config) {
        /*
         * The Promise models a management-plane API call. A real system could
         * perform authentication, authorization, inventory lookup, storage
         * provisioning, and asynchronous backend operations here.
         */
        await new Promise(resolve => setTimeout(resolve, 10));
        return this.hypervisor.createVM(config);
    }

    async startVM(vmID) {
        await new Promise(resolve => setTimeout(resolve, 10));
        this.hypervisor.startVM(vmID);
    }

    async shutdownVM(vmID) {
        await new Promise(resolve => setTimeout(resolve, 10));
        this.hypervisor.shutdownVM(vmID);
    }
}


/* -------------------------------------------------------------------------
 * Demonstrations
 * ---------------------------------------------------------------------- */

async function demonstrateTypeComparison() {
    console.log('\n=== Type 1 and Type 2 Architecture ===');

    const type1 = new Hypervisor({
        name: 'Production-HV',
        type: HypervisorType.TYPE_1,
        resources: new HostResources(16, 32768, 2000)
    });

    const type2 = new Hypervisor({
        name: 'Developer-HV',
        type: HypervisorType.TYPE_2,
        resources: new HostResources(8, 16384, 1000)
    });

    console.log(type1.summary());
    console.log(type2.summary());

    console.log('\nType 1 path: hardware -> hypervisor -> guest VMs');
    console.log(
        'Type 2 path: hardware -> host OS -> hypervisor -> guest VMs'
    );
}


async function demonstrateLifecycle() {
    console.log('\n=== Event-Driven VM Lifecycle ===');

    const hypervisor = new Hypervisor({
        name: 'Lab-HV',
        type: HypervisorType.TYPE_1,
        resources: new HostResources(8, 16384, 500)
    });

    const controller = new ManagementController(hypervisor);

    const vm = await controller.provisionVM({
        name: 'api-server',
        vcpus: 2,
        memoryMB: 4096,
        storageGB: 40,
        guestOS: 'Linux'
    });

    await controller.startVM(vm.id);

    vm.disks[0].write(7);

    hypervisor.scheduleCPU(25);
    hypervisor.scheduleCPU(25);

    const snapshot = vm.createSnapshot('stable-api');

    hypervisor.pauseVM(vm.id);
    hypervisor.resumeVM(vm.id);

    await controller.shutdownVM(vm.id);

    vm.restoreSnapshot(snapshot.id);

    console.log('VM status:', vm.status());
    console.log('Audit events:', controller.auditLog);
}


async function demonstratePolicyFailures() {
    console.log('\n=== Resource Policy and Failure Handling ===');

    const hypervisor = new Hypervisor({
        name: 'Capacity-HV',
        type: HypervisorType.TYPE_1,
        resources: new HostResources(4, 8192, 200)
    });

    try {
        hypervisor.createVM({
            name: 'oversized',
            vcpus: 8,
            memoryMB: 16384,
            storageGB: 20,
            guestOS: 'Linux'
        });
    } catch (error) {
        console.log('Rejected VM:', error.message);
    }

    const vm = hypervisor.createVM({
        name: 'small-vm',
        vcpus: 1,
        memoryMB: 1024,
        storageGB: 10,
        guestOS: 'Linux'
    });

    try {
        vm.disks[0].write(20);
    } catch (error) {
        console.log('Rejected disk operation:', error.message);
    }

    hypervisor.destroyVM(vm.id);

    try {
        hypervisor.startVM(vm.id);
    } catch (error) {
        console.log('Rejected lifecycle operation:', error.message);
    }
}


async function demonstrateOvercommitment() {
    console.log('\n=== Memory Overcommitment ===');

    const hypervisor = new Hypervisor({
        name: 'Overcommit-HV',
        type: HypervisorType.TYPE_1,
        resources: new HostResources(8, 8192, 500),
        allowMemoryOvercommit: true
    });

    hypervisor.createVM({
        name: 'memory-a',
        vcpus: 1,
        memoryMB: 6144,
        storageGB: 20,
        guestOS: 'Linux'
    });

    hypervisor.createVM({
        name: 'memory-b',
        vcpus: 1,
        memoryMB: 4096,
        storageGB: 20,
        guestOS: 'Linux'
    });

    console.log(hypervisor.summary());
    console.log(
        'A production hypervisor needs memory reclamation mechanisms when '
        + 'committed virtual memory exceeds physical memory.'
    );
}


async function main() {
    console.log('=== Hypervisor Management Simulator ===');

    await demonstrateTypeComparison();
    await demonstrateLifecycle();
    await demonstratePolicyFailures();
    await demonstrateOvercommitment();

    console.log('\n=== Simulation Complete ===');
}


main().catch(error => {
    console.error('Management operation failed:', error.message);
    process.exitCode = 1;
});
