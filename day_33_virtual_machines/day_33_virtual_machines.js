'use strict';

/*
 * Virtual Machine Control Plane Simulator
 *
 * This Node.js-compatible program focuses on event-driven VM lifecycle
 * management. It complements the Python model by emphasizing JavaScript
 * objects, EventEmitter-based events, asynchronous operations, policy
 * evaluation, immutable-style state transitions, and operational telemetry.
 *
 * It models:
 * - CPU and memory reservations
 * - Virtual disks and I/O
 * - Virtual network interfaces
 * - VM images
 * - Snapshots
 * - Lifecycle events
 * - Asynchronous boot and shutdown
 * - Capacity checks
 * - Merge-like policy evaluation for operational changes
 * - Audit logging
 */

const { EventEmitter } = require('node:events');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');


const VM_STATES = Object.freeze({
  DEFINED: 'defined',
  STARTING: 'starting',
  RUNNING: 'running',
  PAUSED: 'paused',
  STOPPING: 'stopping',
  STOPPED: 'stopped',
  FAILED: 'failed'
});

const VALID_TRANSITIONS = Object.freeze({
  defined: new Set(['starting']),
  stopped: new Set(['starting']),
  starting: new Set(['running', 'failed']),
  running: new Set(['paused', 'stopping', 'failed']),
  paused: new Set(['running', 'stopping', 'failed']),
  stopping: new Set(['stopped', 'failed']),
  failed: new Set(['starting', 'stopped'])
});


function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}


function deepClone(value) {
  return structuredClone(value);
}


function nowIso() {
  return new Date().toISOString();
}


class ImageCatalog {
  constructor() {
    this.images = new Map();
  }

  add(image) {
    assert(image.id && image.name, 'Image ID and name are required.');
    assert(Number.isInteger(image.sizeGb) && image.sizeGb > 0,
      'Image size must be a positive integer.');
    assert(image.sha256, 'A trusted image checksum is required.');

    if (this.images.has(image.id)) {
      throw new Error(`Image ${image.id} already exists.`);
    }

    this.images.set(image.id, Object.freeze({ ...image }));
  }

  get(id) {
    const image = this.images.get(id);
    if (!image) {
      throw new Error(`Unknown image: ${id}`);
    }
    return image;
  }

  verify(id, checksum) {
    return this.get(id).sha256.toLowerCase() === checksum.toLowerCase();
  }
}


class IPAllocator {
  constructor(prefix = '10.30.0.') {
    this.prefix = prefix;
    this.allocated = new Map();
  }

  allocate(vmId) {
    if (this.allocated.has(vmId)) {
      return this.allocated.get(vmId);
    }

    for (let host = 10; host <= 254; host += 1) {
      const address = `${this.prefix}${host}`;
      if (![...this.allocated.values()].includes(address)) {
        this.allocated.set(vmId, address);
        return address;
      }
    }

    throw new Error('Virtual network address pool exhausted.');
  }

  release(vmId) {
    this.allocated.delete(vmId);
  }
}


class VirtualDisk {
  constructor({ name, sizeGb, bus = 'virtio', imageId = null }) {
    assert(name, 'Disk name is required.');
    assert(Number.isFinite(sizeGb) && sizeGb > 0,
      'Disk size must be positive.');

    this.name = name;
    this.sizeGb = sizeGb;
    this.bus = bus;
    this.imageId = imageId;
    this.usedGb = imageId ? 0 : 0;
    this.readonly = false;
    this.readIops = 0;
    this.writeIops = 0;
  }

  get freeGb() {
    return Math.max(0, this.sizeGb - this.usedGb);
  }

  write(gb) {
    assert(gb >= 0, 'Disk write size cannot be negative.');
    if (this.readonly) {
      throw new Error(`Disk ${this.name} is read-only.`);
    }
    if (gb > this.freeGb) {
      throw new Error(
        `Disk ${this.name} has only ${this.freeGb.toFixed(2)} GB free.`
      );
    }

    this.usedGb += gb;
    this.writeIops += 1;
  }

  read(gb) {
    assert(gb >= 0, 'Disk read size cannot be negative.');
    this.readIops += 1;
    return Math.min(gb, this.usedGb);
  }
}


class VirtualNetworkInterface {
  constructor({ name, mac, mode = 'nat' }) {
    this.name = name;
    this.mac = mac;
    this.mode = mode;
    this.ip = null;
    this.connected = true;
    this.rxMb = 0;
    this.txMb = 0;
  }

  receive(mb) {
    if (!this.connected) {
      throw new Error(`Interface ${this.name} is disconnected.`);
    }
    assert(mb >= 0, 'Received traffic cannot be negative.');
    this.rxMb += mb;
  }

  transmit(mb) {
    if (!this.connected) {
      throw new Error(`Interface ${this.name} is disconnected.`);
    }
    assert(mb >= 0, 'Transmitted traffic cannot be negative.');
    this.txMb += mb;
  }
}


class Snapshot {
  constructor(vm, id, name, includeMemory) {
    this.id = id;
    this.name = name;
    this.vmId = vm.id;
    this.createdAt = nowIso();
    this.includeMemory = includeMemory;
    this.diskState = new Map(
      [...vm.disks.entries()].map(([diskName, disk]) => [
        diskName,
        disk.usedGb
      ])
    );
    this.changedGb = 0;
  }
}


class VirtualMachine {
  constructor({
    id,
    name,
    imageId,
    vcpus,
    memoryMb,
    diskGb,
    cpuLimit = 100
  }) {
    assert(id && name, 'VM ID and name are required.');
    assert(Number.isInteger(vcpus) && vcpus > 0,
      'vCPUs must be a positive integer.');
    assert(Number.isInteger(memoryMb) && memoryMb >= 128,
      'VM memory must be at least 128 MB.');
    assert(Number.isInteger(diskGb) && diskGb > 0,
      'Disk capacity must be positive.');
    assert(cpuLimit >= 1 && cpuLimit <= 100,
      'CPU limit must be between 1 and 100 percent.');

    this.id = id;
    this.name = name;
    this.imageId = imageId;

    this.cpu = {
      vcpus,
      maxVcpus: vcpus * 2,
      shares: 1024,
      limit: cpuLimit,
      cpuSeconds: 0
    };

    this.memory = {
      allocatedMb: memoryMb,
      maxMb: memoryMb * 2,
      balloonEnabled: true,
      pressurePercent: 0
    };

    this.disks = new Map([
      ['boot', new VirtualDisk({
        name: 'boot',
        sizeGb: diskGb,
        bus: 'virtio',
        imageId
      })]
    ]);

    this.interfaces = new Map([
      ['eth0', new VirtualNetworkInterface({
        name: 'eth0',
        mac: VirtualMachine.makeMac(id)
      })]
    ]);

    this.snapshots = new Map();
    this.state = VM_STATES.DEFINED;
    this.bootCount = 0;
    this.uptimeSeconds = 0;
    this.lastError = null;
  }

  static makeMac(seed) {
    const digest = crypto.createHash('sha256')
      .update(seed)
      .digest();

    // 02 sets the locally administered/unicast MAC bits appropriate for
    // an internally generated address rather than copying a physical NIC.
    return [
      '02',
      digest[0].toString(16).padStart(2, '0'),
      digest[1].toString(16).padStart(2, '0'),
      digest[2].toString(16).padStart(2, '0'),
      digest[3].toString(16).padStart(2, '0'),
      digest[4].toString(16).padStart(2, '0')
    ].join(':');
  }

  get diskCapacityGb() {
    return [...this.disks.values()]
      .reduce((total, disk) => total + disk.sizeGb, 0);
  }

  get diskUsedGb() {
    return [...this.disks.values()]
      .reduce((total, disk) => total + disk.usedGb, 0);
  }

  transition(nextState) {
    const allowed = VALID_TRANSITIONS[this.state];

    if (!allowed || !allowed.has(nextState)) {
      throw new Error(
        `Invalid transition: ${this.state} -> ${nextState}`
      );
    }

    this.state = nextState;
  }
}


class PolicyEngine {
  /*
   * Operational policy is kept separate from the VM object. This avoids
   * mixing resource state with governance decisions such as "a production VM
   * cannot be started without a verified image".
   */
  constructor({ requireVerifiedImages = true, maxProductionVcpus = 16 }) {
    this.requireVerifiedImages = requireVerifiedImages;
    this.maxProductionVcpus = maxProductionVcpus;
  }

  evaluateStart(vm, image) {
    const failures = [];

    if (this.requireVerifiedImages && !image.sha256) {
      failures.push('Image does not contain a verification checksum.');
    }

    if (vm.cpu.vcpus > this.maxProductionVcpus) {
      failures.push('VM exceeds the permitted production vCPU limit.');
    }

    if (vm.disks.size === 0) {
      failures.push('VM has no virtual disks.');
    }

    if (vm.interfaces.size === 0) {
      failures.push('VM has no network interfaces.');
    }

    return {
      allowed: failures.length === 0,
      failures
    };
  }
}


class VirtualizationManager extends EventEmitter {
  constructor({
    hostName,
    cpuCores,
    memoryMb,
    storageGb,
    imageCatalog,
    policyEngine
  }) {
    super();

    assert(cpuCores > 0, 'Host CPU capacity must be positive.');
    assert(memoryMb >= 128, 'Host memory capacity is too small.');
    assert(storageGb > 0, 'Host storage capacity must be positive.');

    this.host = {
      name: hostName,
      cpuCores,
      memoryMb,
      storageGb,
      allocatedCpu: 0,
      allocatedMemoryMb: 0,
      allocatedStorageGb: 0
    };

    this.images = imageCatalog;
    this.policy = policyEngine;
    this.vms = new Map();
    this.ipAllocator = new IPAllocator();
    this.audit = [];
  }

  log(event, vmId, details = {}) {
    const record = {
      timestamp: nowIso(),
      event,
      vmId,
      details: deepClone(details)
    };

    this.audit.push(record);
    this.emit(event, record);
  }

  ensureCapacity({ cpu, memoryMb, storageGb }) {
    assert(
      this.host.allocatedCpu + cpu <= this.host.cpuCores,
      `Host CPU capacity exceeded: need ${cpu} cores.`
    );

    assert(
      this.host.allocatedMemoryMb + memoryMb <= this.host.memoryMb,
      `Host memory capacity exceeded: need ${memoryMb} MB.`
    );

    assert(
      this.host.allocatedStorageGb + storageGb <= this.host.storageGb,
      `Host storage capacity exceeded: need ${storageGb} GB.`
    );
  }

  createVm(options) {
    if (this.vms.has(options.id)) {
      throw new Error(`VM ${options.id} already exists.`);
    }

    const image = this.images.get(options.imageId);

    assert(
      options.diskGb >= image.sizeGb,
      `Boot disk must be at least ${image.sizeGb} GB.`
    );

    this.ensureCapacity({
      cpu: options.vcpus,
      memoryMb: options.memoryMb,
      storageGb: options.diskGb
    });

    const vm = new VirtualMachine(options);

    // The image already occupies logical filesystem content inside the boot
    // disk. The physical backing-store accounting remains separate.
    vm.disks.get('boot').usedGb = image.sizeGb;

    this.vms.set(vm.id, vm);
    this.host.allocatedCpu += vm.cpu.vcpus;
    this.host.allocatedMemoryMb += vm.memory.allocatedMb;
    this.host.allocatedStorageGb += vm.diskCapacityGb;

    this.log('vm-created', vm.id, {
      imageId: vm.imageId,
      vcpus: vm.cpu.vcpus,
      memoryMb: vm.memory.allocatedMb
    });

    return vm;
  }

  getVm(vmId) {
    const vm = this.vms.get(vmId);
    if (!vm) {
      throw new Error(`Unknown VM: ${vmId}`);
    }
    return vm;
  }

  async start(vmId) {
    const vm = this.getVm(vmId);
    const image = this.images.get(vm.imageId);

    if (![VM_STATES.DEFINED, VM_STATES.STOPPED, VM_STATES.FAILED]
      .includes(vm.state)) {
      throw new Error(
        `Cannot start ${vm.name} from ${vm.state}.`
      );
    }

    const decision = this.policy.evaluateStart(vm, image);

    if (!decision.allowed) {
      throw new Error(
        `Start policy rejected VM: ${decision.failures.join('; ')}`
      );
    }

    vm.transition(VM_STATES.STARTING);
    this.log('vm-starting', vm.id);

    try {
      // A real control plane would wait for the hypervisor to create virtual
      // CPUs, restore device state, map memory, and launch guest firmware.
      await new Promise(resolve => setTimeout(resolve, 20));

      vm.interfaces.get('eth0').ip = this.ipAllocator.allocate(vm.id);
      vm.bootCount += 1;
      vm.lastError = null;
      vm.transition(VM_STATES.RUNNING);

      this.log('vm-started', vm.id, {
        ip: vm.interfaces.get('eth0').ip,
        bootCount: vm.bootCount
      });

      return vm;
    } catch (error) {
      vm.lastError = error.message;
      vm.state = VM_STATES.FAILED;
      this.log('vm-start-failed', vm.id, {
        message: error.message
      });
      throw error;
    }
  }

  async stop(vmId) {
    const vm = this.getVm(vmId);

    if (![VM_STATES.RUNNING, VM_STATES.PAUSED].includes(vm.state)) {
      throw new Error(`Cannot stop VM from ${vm.state}.`);
    }

    vm.transition(VM_STATES.STOPPING);
    this.log('vm-stopping', vm.id);

    await new Promise(resolve => setTimeout(resolve, 15));

    this.ipAllocator.release(vm.id);
    vm.interfaces.get('eth0').ip = null;
    vm.transition(VM_STATES.STOPPED);

    this.log('vm-stopped', vm.id);
  }

  async restart(vmId) {
    const vm = this.getVm(vmId);

    if (![VM_STATES.RUNNING, VM_STATES.PAUSED].includes(vm.state)) {
      throw new Error('Restart requires a running or paused VM.');
    }

    await this.stop(vmId);
    await this.start(vmId);

    this.log('vm-restarted', vm.id);
  }

  pause(vmId) {
    const vm = this.getVm(vmId);
    vm.transition(VM_STATES.PAUSED);
    this.log('vm-paused', vm.id);
  }

  resume(vmId) {
    const vm = this.getVm(vmId);
    vm.transition(VM_STATES.RUNNING);
    this.log('vm-resumed', vm.id);
  }

  resizeMemory(vmId, newMemoryMb) {
    const vm = this.getVm(vmId);

    assert(
      newMemoryMb >= 128 && newMemoryMb <= vm.memory.maxMb,
      `Memory must be between 128 MB and ${vm.memory.maxMb} MB.`
    );

    const delta = newMemoryMb - vm.memory.allocatedMb;

    assert(
      this.host.allocatedMemoryMb + delta <= this.host.memoryMb,
      'Host does not have enough memory for this resize.'
    );

    vm.memory.allocatedMb = newMemoryMb;
    this.host.allocatedMemoryMb += delta;

    this.log('memory-resized', vm.id, {
      newMemoryMb
    });
  }

  addDisk(vmId, { name, sizeGb, bus = 'virtio' }) {
    const vm = this.getVm(vmId);

    if (vm.disks.has(name)) {
      throw new Error(`Disk ${name} already exists.`);
    }

    this.ensureCapacity({
      cpu: 0,
      memoryMb: 0,
      storageGb: sizeGb
    });

    vm.disks.set(name, new VirtualDisk({
      name,
      sizeGb,
      bus
    }));

    this.host.allocatedStorageGb += sizeGb;

    this.log('disk-added', vm.id, {
      name,
      sizeGb,
      bus
    });
  }

  writeDisk(vmId, diskName, gb) {
    const vm = this.getVm(vmId);
    const disk = vm.disks.get(diskName);

    if (!disk) {
      throw new Error(`Unknown disk ${diskName}.`);
    }

    disk.write(gb);

    for (const snapshot of vm.snapshots.values()) {
      snapshot.changedGb += gb;
    }

    this.log('disk-write', vm.id, {
      diskName,
      gb
    });
  }

  networkTransmit(vmId, interfaceName, mb) {
    const vm = this.getVm(vmId);
    const nic = vm.interfaces.get(interfaceName);

    if (!nic) {
      throw new Error(`Unknown interface ${interfaceName}.`);
    }

    nic.transmit(mb);

    this.log('network-transmit', vm.id, {
      interfaceName,
      mb
    });
  }

  networkReceive(vmId, interfaceName, mb) {
    const vm = this.getVm(vmId);
    const nic = vm.interfaces.get(interfaceName);

    if (!nic) {
      throw new Error(`Unknown interface ${interfaceName}.`);
    }

    nic.receive(mb);

    this.log('network-receive', vm.id, {
      interfaceName,
      mb
    });
  }

  createSnapshot(vmId, snapshotId, name, includeMemory = false) {
    const vm = this.getVm(vmId);

    if (vm.snapshots.has(snapshotId)) {
      throw new Error(`Snapshot ${snapshotId} already exists.`);
    }

    if (![VM_STATES.RUNNING, VM_STATES.PAUSED, VM_STATES.STOPPED]
      .includes(vm.state)) {
      throw new Error('VM is not in a snapshot-capable state.');
    }

    const snapshot = new Snapshot(
      vm,
      snapshotId,
      name,
      includeMemory
    );

    vm.snapshots.set(snapshotId, snapshot);

    this.log('snapshot-created', vm.id, {
      snapshotId,
      includeMemory
    });

    return snapshot;
  }

  restoreSnapshot(vmId, snapshotId) {
    const vm = this.getVm(vmId);
    const snapshot = vm.snapshots.get(snapshotId);

    if (!snapshot) {
      throw new Error(`Unknown snapshot ${snapshotId}.`);
    }

    if ([VM_STATES.RUNNING, VM_STATES.PAUSED].includes(vm.state)) {
      throw new Error(
        'Stop the VM before restoring a disk snapshot in this simulator.'
      );
    }

    for (const [diskName, usedGb] of snapshot.diskState.entries()) {
      const disk = vm.disks.get(diskName);
      if (disk) {
        disk.usedGb = usedGb;
      }
    }

    this.log('snapshot-restored', vm.id, {
      snapshotId
    });
  }

  destroy(vmId) {
    const vm = this.getVm(vmId);

    if ([VM_STATES.RUNNING, VM_STATES.PAUSED, VM_STATES.STARTING]
      .includes(vm.state)) {
      throw new Error('VM must be stopped before destruction.');
    }

    this.ipAllocator.release(vm.id);
    this.host.allocatedCpu -= vm.cpu.vcpus;
    this.host.allocatedMemoryMb -= vm.memory.allocatedMb;
    this.host.allocatedStorageGb -= vm.diskCapacityGb;

    this.vms.delete(vm.id);

    this.log('vm-destroyed', vm.id);
  }

  simulateWorkload(vmId, {
    seconds,
    cpuPercent,
    memoryPressurePercent,
    diskWriteGb = 0,
    txMb = 0,
    rxMb = 0
  }) {
    const vm = this.getVm(vmId);

    assert(vm.state === VM_STATES.RUNNING,
      'Workload requires a running VM.');
    assert(seconds > 0, 'Workload duration must be positive.');
    assert(cpuPercent >= 0 && cpuPercent <= 100,
      'CPU percentage must be between 0 and 100.');
    assert(memoryPressurePercent >= 0 && memoryPressurePercent <= 100,
      'Memory pressure must be between 0 and 100.');

    const effectiveCpu = Math.min(cpuPercent, vm.cpu.limit);

    vm.uptimeSeconds += seconds;
    vm.cpu.cpuSeconds += seconds * effectiveCpu / 100;
    vm.memory.pressurePercent = memoryPressurePercent;

    if (diskWriteGb > 0) {
      this.writeDisk(vmId, 'boot', diskWriteGb);
    }

    if (txMb > 0) {
      this.networkTransmit(vmId, 'eth0', txMb);
    }

    if (rxMb > 0) {
      this.networkReceive(vmId, 'eth0', rxMb);
    }

    this.log('workload-simulated', vm.id, {
      seconds,
      cpuPercent,
      effectiveCpu,
      memoryPressurePercent
    });
  }

  report(vmId) {
    const vm = this.getVm(vmId);

    return {
      id: vm.id,
      name: vm.name,
      state: vm.state,
      imageId: vm.imageId,
      cpu: deepClone(vm.cpu),
      memory: deepClone(vm.memory),
      disks: Object.fromEntries(
        [...vm.disks.entries()].map(([name, disk]) => [
          name,
          {
            sizeGb: disk.sizeGb,
            usedGb: Number(disk.usedGb.toFixed(2)),
            freeGb: Number(disk.freeGb.toFixed(2)),
            bus: disk.bus,
            readIops: disk.readIops,
            writeIops: disk.writeIops
          }
        ])
      ),
      interfaces: Object.fromEntries(
        [...vm.interfaces.entries()].map(([name, nic]) => [
          name,
          deepClone(nic)
        ])
      ),
      snapshots: Object.fromEntries(
        [...vm.snapshots.entries()].map(([id, snapshot]) => [
          id,
          {
            name: snapshot.name,
            createdAt: snapshot.createdAt,
            changedGb: snapshot.changedGb,
            includeMemory: snapshot.includeMemory
          }
        ])
      ),
      uptimeSeconds: vm.uptimeSeconds,
      lastError: vm.lastError
    };
  }

  hostReport() {
    return {
      host: this.host.name,
      cpu: {
        total: this.host.cpuCores,
        allocated: this.host.allocatedCpu,
        free: this.host.cpuCores - this.host.allocatedCpu
      },
      memoryMb: {
        total: this.host.memoryMb,
        allocated: this.host.allocatedMemoryMb,
        free: this.host.memoryMb - this.host.allocatedMemoryMb
      },
      storageGb: {
        total: this.host.storageGb,
        allocated: this.host.allocatedStorageGb,
        free: this.host.storageGb - this.host.allocatedStorageGb
      },
      vmCount: this.vms.size
    };
  }

  async saveAuditLog(path) {
    await fs.writeFile(
      path,
      JSON.stringify(this.audit, null, 2),
      'utf8'
    );
  }
}


function createDemoManager() {
  const images = new ImageCatalog();

  images.add({
    id: 'debian-13',
    name: 'Debian 13 Server',
    os: 'Linux',
    version: '13',
    architecture: 'x86_64',
    sizeGb: 7,
    sha256: 'sha256:verified-debian-demo'
  });

  images.add({
    id: 'ubuntu-24',
    name: 'Ubuntu Server 24.04',
    os: 'Linux',
    version: '24.04',
    architecture: 'x86_64',
    sizeGb: 8,
    sha256: 'sha256:verified-ubuntu-demo'
  });

  const policy = new PolicyEngine({
    requireVerifiedImages: true,
    maxProductionVcpus: 16
  });

  const manager = new VirtualizationManager({
    hostName: 'edge-compute-01',
    cpuCores: 12,
    memoryMb: 24576,
    storageGb: 500,
    imageCatalog: images,
    policyEngine: policy
  });

  manager.on('vm-started', event => {
    console.log(
      `[EVENT] ${event.event}: ${event.vmId} -> ${event.details.ip}`
    );
  });

  manager.on('snapshot-created', event => {
    console.log(
      `[EVENT] snapshot ${event.details.snapshotId} created for ${event.vmId}`
    );
  });

  return manager;
}


async function run() {
  console.log('Virtual Machine Event-Driven Management Simulator');

  const manager = createDemoManager();

  manager.createVm({
    id: 'web-01',
    name: 'Web Frontend',
    imageId: 'ubuntu-24',
    vcpus: 2,
    memoryMb: 2048,
    diskGb: 30,
    cpuLimit: 90
  });

  manager.createVm({
    id: 'db-01',
    name: 'Database',
    imageId: 'debian-13',
    vcpus: 4,
    memoryMb: 8192,
    diskGb: 80,
    cpuLimit: 100
  });

  console.log('\nHost allocation before boot:');
  console.log(JSON.stringify(manager.hostReport(), null, 2));

  console.log('\nImage verification:');
  console.log(
    'Ubuntu trusted checksum:',
    manager.images.verify(
      'ubuntu-24',
      'sha256:verified-ubuntu-demo'
    )
  );
  console.log(
    'Ubuntu forged checksum:',
    manager.images.verify(
      'ubuntu-24',
      'sha256:wrong-value'
    )
  );

  await manager.start('web-01');
  await manager.start('db-01');

  manager.addDisk('db-01', {
    name: 'database-data',
    sizeGb: 120,
    bus: 'scsi'
  });

  manager.simulateWorkload('web-01', {
    seconds: 60,
    cpuPercent: 75,
    memoryPressurePercent: 48,
    diskWriteGb: 2,
    txMb: 320,
    rxMb: 980
  });

  manager.simulateWorkload('db-01', {
    seconds: 60,
    cpuPercent: 91,
    memoryPressurePercent: 78,
    diskWriteGb: 5,
    txMb: 210,
    rxMb: 180
  });

  const snapshot = manager.createSnapshot(
    'db-01',
    'db-before-index-change',
    'Before database index change',
    false
  );

  manager.writeDisk('db-01', 'database-data', 12);

  console.log('\nDatabase report after snapshot and write:');
  console.log(JSON.stringify(manager.report('db-01'), null, 2));

  await manager.stop('db-01');
  manager.restoreSnapshot('db-01', snapshot.id);
  await manager.start('db-01');

  manager.pause('web-01');
  manager.resume('web-01');

  manager.resizeMemory('web-01', 3072);

  console.log('\nFinal host allocation:');
  console.log(JSON.stringify(manager.hostReport(), null, 2));

  console.log('\nFinal web VM report:');
  console.log(JSON.stringify(manager.report('web-01'), null, 2));

  console.log('\nRecent audit records:');
  console.log(
    JSON.stringify(manager.audit.slice(-8), null, 2)
  );

  const auditPath = './vm-audit-demo.json';
  await manager.saveAuditLog(auditPath);
  console.log(`\nAudit log written to ${auditPath}`);

  // Remove the demonstration artifact so execution does not permanently
  // modify the working directory.
  await fs.unlink(auditPath).catch(() => {});

  try {
    manager.destroy('web-01');
  } catch (error) {
    console.log(`\nExpected destruction failure: ${error.message}`);
  }

  await manager.stop('web-01');
  manager.destroy('web-01');

  console.log(
    '\nVM lifecycle completed: running -> stopped -> destroyed.'
  );
}


run().catch(error => {
  console.error(`Fatal simulation error: ${error.message}`);
  process.exitCode = 1;
});
