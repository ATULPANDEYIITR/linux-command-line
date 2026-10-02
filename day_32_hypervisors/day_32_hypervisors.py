#!/usr/bin/env python3
"""
Hypervisors: Type 1, Type 2, and Virtual Machine Management

A self-contained educational simulation of hypervisor behavior.

The program models:
- Type 1 (bare-metal) hypervisors
- Type 2 (hosted) hypervisors
- Virtual CPU, memory, storage, and network allocation
- VM creation and lifecycle management
- Resource validation and overcommitment
- CPU scheduling
- Memory allocation
- Virtual disk attachment
- Virtual networking
- Snapshots
- Pause, resume, shutdown, and destruction
- Resource accounting
- Isolation boundaries
- Basic hypervisor management concepts

This is a simulator, not a real hardware virtualization layer. It does not
create real VMs or execute guest operating systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import hashlib
import math
import time
import uuid


# ---------------------------------------------------------------------------
# Fundamental VM state
# ---------------------------------------------------------------------------

class VMState(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    DESTROYED = "destroyed"


class HypervisorType(Enum):
    TYPE_1 = "Type 1 / bare-metal"
    TYPE_2 = "Type 2 / hosted"


class DiskBus(Enum):
    VIRTIO = "virtio"
    SATA = "sata"
    SCSI = "scsi"


class NetworkMode(Enum):
    NAT = "nat"
    BRIDGED = "bridged"
    HOST_ONLY = "host-only"


# ---------------------------------------------------------------------------
# Resource models
# ---------------------------------------------------------------------------

@dataclass
class HostResources:
    cpu_cores: int
    memory_mb: int
    storage_gb: int

    def validate(self) -> None:
        if self.cpu_cores <= 0:
            raise ValueError("Host must provide at least one CPU core.")
        if self.memory_mb <= 0:
            raise ValueError("Host must provide positive memory.")
        if self.storage_gb <= 0:
            raise ValueError("Host must provide positive storage.")


@dataclass
class VirtualDisk:
    path: str
    capacity_gb: int
    bus: DiskBus = DiskBus.VIRTIO
    thin_provisioned: bool = True
    used_gb: int = 0

    def __post_init__(self) -> None:
        if self.capacity_gb <= 0:
            raise ValueError("Virtual disk capacity must be positive.")
        if self.used_gb < 0 or self.used_gb > self.capacity_gb:
            raise ValueError("Disk usage must remain inside disk capacity.")

    def write(self, amount_gb: int) -> None:
        if amount_gb < 0:
            raise ValueError("Write size cannot be negative.")
        if self.used_gb + amount_gb > self.capacity_gb:
            raise RuntimeError(
                f"Disk {self.path} has insufficient virtual capacity."
            )
        self.used_gb += amount_gb

    def snapshot_metadata(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "capacity_gb": self.capacity_gb,
            "used_gb": self.used_gb,
            "bus": self.bus.value,
            "thin_provisioned": self.thin_provisioned,
        }


@dataclass
class VirtualNIC:
    name: str
    mac_address: str
    network_mode: NetworkMode
    connected: bool = True

    def disconnect(self) -> None:
        self.connected = False

    def connect(self) -> None:
        self.connected = True


@dataclass
class Snapshot:
    snapshot_id: str
    name: str
    vm_state: VMState
    cpu_count: int
    memory_mb: int
    disk_usage: Dict[str, int]
    created_at: float = field(default_factory=time.time)


@dataclass
class VirtualMachine:
    name: str
    cpu_count: int
    memory_mb: int
    storage_gb: int
    guest_os: str
    vm_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: VMState = VMState.CREATED
    disks: List[VirtualDisk] = field(default_factory=list)
    nics: List[VirtualNIC] = field(default_factory=list)
    snapshots: Dict[str, Snapshot] = field(default_factory=dict)
    cpu_time_ms: int = 0

    def __post_init__(self) -> None:
        if self.cpu_count <= 0:
            raise ValueError("A VM must have at least one virtual CPU.")
        if self.memory_mb < 128:
            raise ValueError("A VM requires at least 128 MB in this simulator.")
        if self.storage_gb <= 0:
            raise ValueError("A VM must have positive storage.")

    def attach_disk(self, disk: VirtualDisk) -> None:
        if self.state == VMState.DESTROYED:
            raise RuntimeError("Cannot modify a destroyed VM.")
        self.disks.append(disk)

    def attach_network(self, nic: VirtualNIC) -> None:
        if self.state == VMState.DESTROYED:
            raise RuntimeError("Cannot modify a destroyed VM.")
        self.nics.append(nic)

    def total_disk_capacity(self) -> int:
        return sum(disk.capacity_gb for disk in self.disks)

    def start(self) -> None:
        if self.state in {VMState.CREATED, VMState.STOPPED}:
            self.state = VMState.RUNNING
        elif self.state == VMState.PAUSED:
            self.state = VMState.RUNNING
        elif self.state == VMState.RUNNING:
            return
        else:
            raise RuntimeError("Destroyed VMs cannot be started.")

    def pause(self) -> None:
        if self.state != VMState.RUNNING:
            raise RuntimeError("Only a running VM can be paused.")
        self.state = VMState.PAUSED

    def resume(self) -> None:
        if self.state != VMState.PAUSED:
            raise RuntimeError("Only a paused VM can be resumed.")
        self.state = VMState.RUNNING

    def shutdown(self) -> None:
        if self.state in {VMState.RUNNING, VMState.PAUSED}:
            self.state = VMState.STOPPED

    def destroy(self) -> None:
        if self.state == VMState.DESTROYED:
            return
        self.state = VMState.DESTROYED

    def create_snapshot(self, name: str) -> Snapshot:
        if self.state == VMState.DESTROYED:
            raise RuntimeError("Destroyed VMs cannot be snapshotted.")

        snapshot = Snapshot(
            snapshot_id=str(uuid.uuid4()),
            name=name,
            vm_state=self.state,
            cpu_count=self.cpu_count,
            memory_mb=self.memory_mb,
            disk_usage={
                disk.path: disk.used_gb
                for disk in self.disks
            },
        )
        self.snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> None:
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            raise KeyError("Snapshot does not exist.")

        self.cpu_count = snapshot.cpu_count
        self.memory_mb = snapshot.memory_mb

        for disk in self.disks:
            if disk.path in snapshot.disk_usage:
                disk.used_gb = snapshot.disk_usage[disk.path]

        self.state = snapshot.vm_state

    def status(self) -> Dict[str, object]:
        return {
            "id": self.vm_id,
            "name": self.name,
            "state": self.state.value,
            "guest_os": self.guest_os,
            "vcpus": self.cpu_count,
            "memory_mb": self.memory_mb,
            "storage_gb": self.total_disk_capacity(),
            "nics": len(self.nics),
            "snapshots": len(self.snapshots),
        }


# ---------------------------------------------------------------------------
# Hypervisor abstraction
# ---------------------------------------------------------------------------

class Hypervisor:
    """
    Common resource-management layer.

    A real hypervisor performs operations below using CPU virtualization
    extensions, page tables, device virtualization, interrupt handling,
    schedulers, storage backends, and hardware isolation mechanisms.

    This class models the management semantics without touching real hardware.
    """

    def __init__(
        self,
        name: str,
        hypervisor_type: HypervisorType,
        resources: HostResources,
        allow_memory_overcommit: bool = False,
    ) -> None:
        self.name = name
        self.hypervisor_type = hypervisor_type
        self.resources = resources
        self.resources.validate()
        self.allow_memory_overcommit = allow_memory_overcommit
        self.vms: Dict[str, VirtualMachine] = {}

    @property
    def allocated_cpu(self) -> int:
        return sum(
            vm.cpu_count
            for vm in self.vms.values()
            if vm.state != VMState.DESTROYED
        )

    @property
    def allocated_memory(self) -> int:
        return sum(
            vm.memory_mb
            for vm in self.vms.values()
            if vm.state != VMState.DESTROYED
        )

    @property
    def allocated_storage(self) -> int:
        return sum(
            vm.total_disk_capacity()
            for vm in self.vms.values()
            if vm.state != VMState.DESTROYED
        )

    def available_cpu(self) -> int:
        return self.resources.cpu_cores - self.allocated_cpu

    def available_memory(self) -> int:
        return self.resources.memory_mb - self.allocated_memory

    def available_storage(self) -> int:
        return self.resources.storage_gb - self.allocated_storage

    def can_create_vm(
        self,
        cpu_count: int,
        memory_mb: int,
        storage_gb: int,
    ) -> Tuple[bool, str]:
        if cpu_count <= 0:
            return False, "CPU allocation must be positive."

        if memory_mb < 128:
            return False, "Memory allocation is below the simulator minimum."

        if storage_gb <= 0:
            return False, "Storage allocation must be positive."

        if self.allocated_cpu + cpu_count > self.resources.cpu_cores:
            return False, "CPU capacity exceeded."

        if (
            not self.allow_memory_overcommit
            and self.allocated_memory + memory_mb > self.resources.memory_mb
        ):
            return False, "Memory capacity exceeded."

        if self.allocated_storage + storage_gb > self.resources.storage_gb:
            return False, "Storage capacity exceeded."

        return True, "Resources available."

    def create_vm(
        self,
        name: str,
        cpu_count: int,
        memory_mb: int,
        storage_gb: int,
        guest_os: str,
    ) -> VirtualMachine:
        if any(vm.name == name for vm in self.vms.values()):
            raise ValueError(f"VM name already exists: {name}")

        allowed, reason = self.can_create_vm(
            cpu_count,
            memory_mb,
            storage_gb,
        )

        if not allowed:
            raise RuntimeError(f"Cannot create VM '{name}': {reason}")

        vm = VirtualMachine(
            name=name,
            cpu_count=cpu_count,
            memory_mb=memory_mb,
            storage_gb=storage_gb,
            guest_os=guest_os,
        )

        disk = VirtualDisk(
            path=f"/virtual-disks/{name}.qcow2",
            capacity_gb=storage_gb,
            bus=DiskBus.VIRTIO,
            thin_provisioned=True,
        )

        nic = VirtualNIC(
            name=f"{name}-nic0",
            mac_address=self._generate_mac(vm.vm_id),
            network_mode=NetworkMode.NAT,
        )

        vm.attach_disk(disk)
        vm.attach_network(nic)
        self.vms[vm.vm_id] = vm

        return vm

    @staticmethod
    def _generate_mac(seed: str) -> str:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        octets = [0x52, 0x54, 0x00, digest[0], digest[1], digest[2]]
        return ":".join(f"{octet:02x}" for octet in octets)

    def delete_vm(self, vm_id: str) -> None:
        vm = self.get_vm(vm_id)
        vm.destroy()

    def get_vm(self, vm_id: str) -> VirtualMachine:
        if vm_id not in self.vms:
            raise KeyError(f"Unknown VM ID: {vm_id}")
        return self.vms[vm_id]

    def list_vms(self) -> List[Dict[str, object]]:
        return [
            vm.status()
            for vm in self.vms.values()
            if vm.state != VMState.DESTROYED
        ]

    def schedule_cpu(self, quantum_ms: int = 10) -> None:
        """
        Simplified round-robin scheduling.

        A real hypervisor maps virtual CPUs to physical execution resources,
        accounts for time, handles interrupts, and may use sophisticated
        fairness or priority algorithms.
        """
        if quantum_ms <= 0:
            raise ValueError("CPU quantum must be positive.")

        running_vms = [
            vm
            for vm in self.vms.values()
            if vm.state == VMState.RUNNING
        ]

        if not running_vms:
            return

        physical_slots = self.resources.cpu_cores

        for index, vm in enumerate(running_vms):
            assigned_slots = min(vm.cpu_count, physical_slots)
            vm.cpu_time_ms += quantum_ms * assigned_slots

            if index >= physical_slots:
                # The simulator records execution but indicates that the VM
                # would need scheduling time on an oversubscribed host.
                vm.cpu_time_ms -= quantum_ms // 2

    def memory_pressure(self) -> float:
        if self.resources.memory_mb == 0:
            return 0.0
        return self.allocated_memory / self.resources.memory_mb

    def summary(self) -> Dict[str, object]:
        return {
            "hypervisor": self.name,
            "type": self.hypervisor_type.value,
            "host_cpu_cores": self.resources.cpu_cores,
            "allocated_vcpus": self.allocated_cpu,
            "host_memory_mb": self.resources.memory_mb,
            "allocated_memory_mb": self.allocated_memory,
            "memory_pressure": round(self.memory_pressure(), 3),
            "host_storage_gb": self.resources.storage_gb,
            "allocated_storage_gb": self.allocated_storage,
            "vm_count": len(self.list_vms()),
        }


class Type1Hypervisor(Hypervisor):
    """
    Type 1 hypervisor runs directly on physical hardware.

    Examples in real environments include VMware ESXi, Microsoft Hyper-V
    in its hypervisor architecture, and Xen. Exact architecture differs
    between products.
    """

    def __init__(self, name: str, resources: HostResources) -> None:
        super().__init__(
            name=name,
            hypervisor_type=HypervisorType.TYPE_1,
            resources=resources,
        )
        self.hardware_devices = {
            "cpu": True,
            "memory": True,
            "storage_controller": True,
            "network_controller": True,
        }


class Type2Hypervisor(Hypervisor):
    """
    Type 2 hypervisor runs as an application or service on a host OS.

    Examples include desktop virtualization products such as VirtualBox
    and VMware Workstation. The host operating system remains between
    the virtualization software and physical hardware.
    """

    def __init__(
        self,
        name: str,
        resources: HostResources,
        host_os: str,
    ) -> None:
        super().__init__(
            name=name,
            hypervisor_type=HypervisorType.TYPE_2,
            resources=resources,
        )
        self.host_os = host_os

    def summary(self) -> Dict[str, object]:
        result = super().summary()
        result["host_os"] = self.host_os
        return result


# ---------------------------------------------------------------------------
# Demonstrations
# ---------------------------------------------------------------------------

def print_title(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def demonstrate_type_comparison() -> None:
    print_title("Type 1 versus Type 2")

    type1 = Type1Hypervisor(
        "BareMetal-HV",
        HostResources(cpu_cores=16, memory_mb=32768, storage_gb=1000),
    )

    type2 = Type2Hypervisor(
        "Desktop-HV",
        HostResources(cpu_cores=8, memory_mb=16384, storage_gb=500),
        host_os="Windows 11",
    )

    print(type1.summary())
    print(type2.summary())

    print("\nArchitecture:")
    print("Type 1: hardware -> hypervisor -> virtual machines")
    print("Type 2: hardware -> host OS -> hypervisor -> virtual machines")


def demonstrate_vm_lifecycle(hypervisor: Hypervisor) -> VirtualMachine:
    print_title("Virtual Machine Lifecycle")

    vm = hypervisor.create_vm(
        name="web-server",
        cpu_count=2,
        memory_mb=4096,
        storage_gb=40,
        guest_os="Ubuntu Server",
    )

    print("Created:", vm.status())

    vm.start()
    print("Started:", vm.status())

    vm.disks[0].write(8)
    print("Disk usage after guest workload:", vm.disks[0].used_gb, "GB")

    vm.pause()
    print("Paused:", vm.state.value)

    vm.resume()
    print("Resumed:", vm.state.value)

    snapshot = vm.create_snapshot("before-maintenance")
    print("Snapshot:", snapshot.snapshot_id)

    vm.shutdown()
    print("Stopped:", vm.state.value)

    vm.restore_snapshot(snapshot.snapshot_id)
    print("Restored:", vm.status())

    return vm


def demonstrate_validation(hypervisor: Hypervisor) -> None:
    print_title("Resource Validation and Failure Conditions")

    try:
        hypervisor.create_vm(
            name="invalid-memory",
            cpu_count=1,
            memory_mb=64,
            storage_gb=10,
            guest_os="Test OS",
        )
    except (ValueError, RuntimeError) as exc:
        print("Rejected low-memory VM:", exc)

    try:
        hypervisor.create_vm(
            name="too-large",
            cpu_count=100,
            memory_mb=100000,
            storage_gb=10,
            guest_os="Test OS",
        )
    except (ValueError, RuntimeError) as exc:
        print("Rejected oversized VM:", exc)


def demonstrate_cpu_scheduling(hypervisor: Hypervisor) -> None:
    print_title("Virtual CPU Scheduling")

    vm_a = hypervisor.create_vm(
        name="application-server",
        cpu_count=2,
        memory_mb=2048,
        storage_gb=30,
        guest_os="Linux",
    )

    vm_b = hypervisor.create_vm(
        name="database-server",
        cpu_count=4,
        memory_mb=4096,
        storage_gb=80,
        guest_os="Linux",
    )

    vm_a.start()
    vm_b.start()

    for _ in range(5):
        hypervisor.schedule_cpu(quantum_ms=20)

    print(
        f"{vm_a.name}: simulated CPU time = "
        f"{vm_a.cpu_time_ms} ms"
    )
    print(
        f"{vm_b.name}: simulated CPU time = "
        f"{vm_b.cpu_time_ms} ms"
    )


def demonstrate_networking(hypervisor: Hypervisor) -> None:
    print_title("Virtual Networking")

    vm = hypervisor.create_vm(
        name="network-node",
        cpu_count=1,
        memory_mb=1024,
        storage_gb=20,
        guest_os="Linux",
    )

    nic = vm.nics[0]

    print("NIC:", nic.name)
    print("MAC:", nic.mac_address)
    print("Mode:", nic.network_mode.value)
    print("Connected:", nic.connected)

    nic.disconnect()
    print("After disconnect:", nic.connected)

    nic.connect()
    print("After reconnect:", nic.connected)


def demonstrate_memory_overcommitment() -> None:
    print_title("Memory Overcommitment")

    hypervisor = Hypervisor(
        name="MemoryLab",
        hypervisor_type=HypervisorType.TYPE_1,
        resources=HostResources(
            cpu_cores=8,
            memory_mb=8192,
            storage_gb=500,
        ),
        allow_memory_overcommit=True,
    )

    first = hypervisor.create_vm(
        name="vm-a",
        cpu_count=1,
        memory_mb=6144,
        storage_gb=20,
        guest_os="Linux",
    )

    second = hypervisor.create_vm(
        name="vm-b",
        cpu_count=1,
        memory_mb=4096,
        storage_gb=20,
        guest_os="Linux",
    )

    print("VM A memory:", first.memory_mb, "MB")
    print("VM B memory:", second.memory_mb, "MB")
    print("Host memory:", hypervisor.resources.memory_mb, "MB")
    print("Allocated memory:", hypervisor.allocated_memory, "MB")
    print("Pressure:", round(hypervisor.memory_pressure(), 2))

    print(
        "\nThe simulator permits committed virtual memory to exceed physical "
        "memory because overcommitment was explicitly enabled. A production "
        "hypervisor needs a reclamation mechanism such as ballooning, "
        "page sharing, compression, or host swapping, with significant "
        "performance implications."
    )


def demonstrate_security_boundary() -> None:
    print_title("Isolation and Security Boundary")

    hypervisor = Type1Hypervisor(
        "Secure-HV",
        HostResources(cpu_cores=4, memory_mb=8192, storage_gb=200),
    )

    trusted = hypervisor.create_vm(
        name="trusted-workload",
        cpu_count=1,
        memory_mb=1024,
        storage_gb=10,
        guest_os="Linux",
    )

    untrusted = hypervisor.create_vm(
        name="untrusted-workload",
        cpu_count=1,
        memory_mb=1024,
        storage_gb=10,
        guest_os="Linux",
    )

    print("VM A:", trusted.vm_id)
    print("VM B:", untrusted.vm_id)
    print(
        "Separate VM identifiers represent separate virtual machines. "
        "A real hypervisor must enforce isolation using hardware-supported "
        "memory translation, privilege boundaries, device isolation, and "
        "carefully validated virtual-device implementations."
    )


def demonstrate_production_considerations() -> None:
    print_title("Production-Oriented Considerations")

    considerations = {
        "CPU": [
            "vCPU scheduling",
            "CPU affinity",
            "hardware virtualization extensions",
            "NUMA locality",
        ],
        "Memory": [
            "second-level address translation",
            "memory reservation",
            "ballooning",
            "huge pages",
        ],
        "Storage": [
            "thin versus thick provisioning",
            "copy-on-write snapshots",
            "I/O queues",
            "persistent storage durability",
        ],
        "Networking": [
            "virtual switches",
            "bridged networking",
            "NAT",
            "virtual network isolation",
        ],
        "Security": [
            "VM isolation",
            "device emulation attack surface",
            "management-plane authentication",
            "patching the hypervisor",
        ],
    }

    for category, items in considerations.items():
        print(f"\n{category}")
        for item in items:
            print(f"  - {item}")


def main() -> None:
    print_title("Hypervisor and Virtual Machine Simulator")

    demonstrate_type_comparison()

    host = Type1Hypervisor(
        "Training-HV",
        HostResources(
            cpu_cores=16,
            memory_mb=32768,
            storage_gb=1000,
        ),
    )

    vm = demonstrate_vm_lifecycle(host)
    demonstrate_validation(host)
    demonstrate_cpu_scheduling(host)
    demonstrate_networking(host)
    demonstrate_memory_overcommitment()
    demonstrate_security_boundary()
    demonstrate_production_considerations()

    print_title("Final Hypervisor State")
    print(host.summary())

    print("\nManaged VMs:")
    for status in host.list_vms():
        print(status)

    vm.destroy()
    print("\nExample VM destroyed:", vm.name, vm.state.value)


if __name__ == "__main__":
    main()
