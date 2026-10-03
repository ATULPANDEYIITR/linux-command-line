#!/usr/bin/env python3
"""
Virtual Machines: CPU, memory, disk, networking, images, snapshots,
and VM lifecycle management.

This self-contained program models a small virtual-machine platform. It is
intentionally a simulation rather than a hypervisor: it demonstrates the
resource and lifecycle decisions made by a VM management layer without
requiring privileged operating-system or virtualization APIs.

The model covers:
- CPU allocation and scheduling
- Memory allocation and reclamation
- Virtual disks, capacity, read/write operations, and I/O pressure
- Virtual network interfaces, IP allocation, traffic accounting, and rules
- VM images and image cloning
- Snapshots with copy-on-write-style disk accounting
- VM lifecycle transitions
- Resource validation and overcommit prevention
- Host capacity reporting
- Operational failures and recovery
- Persistence to JSON
- A small command-line demonstration
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import copy
import json
import math
import random
import time


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class VMState(str, Enum):
    """Lifecycle states supported by the simulated VM manager."""

    DEFINED = "defined"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class DiskBus(str, Enum):
    """Virtual disk attachment types represented by the simulator."""

    VIRTIO = "virtio"
    SATA = "sata"
    SCSI = "scsi"


class NetworkMode(str, Enum):
    """Simplified networking modes."""

    NAT = "nat"
    BRIDGED = "bridged"
    ISOLATED = "isolated"


class PowerAction(str, Enum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    PAUSE = "pause"
    RESUME = "resume"
    DESTROY = "destroy"


@dataclass
class CPUConfig:
    vcpus: int
    max_vcpus: int
    shares: int = 1024
    cpu_limit_percent: int = 100

    def validate(self) -> None:
        if self.vcpus < 1:
            raise ValueError("A VM must have at least one vCPU.")
        if self.max_vcpus < self.vcpus:
            raise ValueError("max_vcpus cannot be below the current vCPU count.")
        if self.shares <= 0:
            raise ValueError("CPU shares must be positive.")
        if not 1 <= self.cpu_limit_percent <= 100:
            raise ValueError("CPU limit must be between 1 and 100 percent.")


@dataclass
class MemoryConfig:
    allocated_mb: int
    max_mb: int
    balloon_enabled: bool = True

    def validate(self) -> None:
        if self.allocated_mb < 128:
            raise ValueError("The simulator requires at least 128 MB of VM memory.")
        if self.max_mb < self.allocated_mb:
            raise ValueError("max_mb cannot be below allocated_mb.")


@dataclass
class VirtualDisk:
    name: str
    size_gb: int
    bus: DiskBus = DiskBus.VIRTIO
    readonly: bool = False
    used_gb: float = 0.0
    iops_limit: Optional[int] = None
    image_id: Optional[str] = None

    def validate(self) -> None:
        if self.size_gb <= 0:
            raise ValueError("Disk size must be positive.")
        if not 0 <= self.used_gb <= self.size_gb:
            raise ValueError(f"Disk {self.name} has invalid used capacity.")

    @property
    def free_gb(self) -> float:
        return max(0.0, self.size_gb - self.used_gb)

    def write(self, gb: float) -> None:
        if self.readonly:
            raise PermissionError(f"Disk {self.name} is read-only.")
        if gb < 0:
            raise ValueError("Write amount cannot be negative.")
        if self.used_gb + gb > self.size_gb:
            raise OSError(
                f"Disk {self.name} is full: requested {gb:.2f} GB, "
                f"only {self.free_gb:.2f} GB remains."
            )
        self.used_gb += gb

    def read(self, gb: float) -> None:
        if gb < 0:
            raise ValueError("Read amount cannot be negative.")
        if gb > self.used_gb:
            raise ValueError(
                f"Cannot read {gb:.2f} GB of logical data from {self.name}; "
                f"only {self.used_gb:.2f} GB is currently used."
            )


@dataclass
class NetworkInterface:
    name: str
    mac: str
    ip: Optional[str] = None
    network: str = "default"
    mode: NetworkMode = NetworkMode.NAT
    rx_mb: float = 0.0
    tx_mb: float = 0.0
    connected: bool = True

    def transmit(self, mb: float) -> None:
        if not self.connected:
            raise ConnectionError(f"Interface {self.name} is disconnected.")
        if mb < 0:
            raise ValueError("Transmitted traffic cannot be negative.")
        self.tx_mb += mb

    def receive(self, mb: float) -> None:
        if not self.connected:
            raise ConnectionError(f"Interface {self.name} is disconnected.")
        if mb < 0:
            raise ValueError("Received traffic cannot be negative.")
        self.rx_mb += mb


@dataclass
class VMImage:
    image_id: str
    name: str
    os_family: str
    version: str
    size_gb: int
    checksum: str
    architecture: str = "x86_64"
    description: str = ""

    def validate(self) -> None:
        if not self.image_id or not self.name:
            raise ValueError("An image requires an ID and name.")
        if self.size_gb <= 0:
            raise ValueError("Image size must be positive.")
        if not self.checksum:
            raise ValueError("An image checksum is required.")


@dataclass
class Snapshot:
    snapshot_id: str
    vm_id: str
    name: str
    created_at: float
    disk_used_at_creation: Dict[str, float]
    changed_gb_since_snapshot: float = 0.0
    memory_state_captured: bool = False
    parent_snapshot_id: Optional[str] = None

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.created_at)


@dataclass
class VM:
    vm_id: str
    name: str
    cpu: CPUConfig
    memory: MemoryConfig
    disks: Dict[str, VirtualDisk]
    interfaces: Dict[str, NetworkInterface]
    image_id: Optional[str]
    state: VMState = VMState.DEFINED
    snapshots: Dict[str, Snapshot] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    cpu_time_seconds: float = 0.0
    memory_pressure_percent: float = 0.0
    boot_count: int = 0
    last_error: Optional[str] = None

    def validate(self) -> None:
        self.cpu.validate()
        self.memory.validate()

        if not self.disks:
            raise ValueError("A VM must have at least one virtual disk.")
        if not self.interfaces:
            raise ValueError("A VM must have at least one network interface.")

        for disk in self.disks.values():
            disk.validate()

        for interface in self.interfaces.values():
            if not interface.mac:
                raise ValueError(f"Interface {interface.name} requires a MAC address.")

    @property
    def disk_capacity_gb(self) -> int:
        return sum(disk.size_gb for disk in self.disks.values())

    @property
    def disk_used_gb(self) -> float:
        return sum(disk.used_gb for disk in self.disks.values())

    @property
    def network_rx_mb(self) -> float:
        return sum(interface.rx_mb for interface in self.interfaces.values())

    @property
    def network_tx_mb(self) -> float:
        return sum(interface.tx_mb for interface in self.interfaces.values())


@dataclass
class Host:
    name: str
    physical_cpu_cores: int
    memory_mb: int
    storage_gb: int
    allocated_cpu: int = 0
    allocated_memory_mb: int = 0
    allocated_storage_gb: int = 0
    running_vms: Set[str] = field(default_factory=set)

    @property
    def free_cpu(self) -> int:
        return self.physical_cpu_cores - self.allocated_cpu

    @property
    def free_memory_mb(self) -> int:
        return self.memory_mb - self.allocated_memory_mb

    @property
    def free_storage_gb(self) -> int:
        return self.storage_gb - self.allocated_storage_gb


# ---------------------------------------------------------------------------
# Image catalog
# ---------------------------------------------------------------------------

class ImageCatalog:
    """Stores trusted VM images and validates their basic metadata."""

    def __init__(self) -> None:
        self.images: Dict[str, VMImage] = {}

    def add(self, image: VMImage) -> None:
        image.validate()
        if image.image_id in self.images:
            raise KeyError(f"Image {image.image_id} already exists.")
        self.images[image.image_id] = image

    def get(self, image_id: str) -> VMImage:
        try:
            return self.images[image_id]
        except KeyError as exc:
            raise KeyError(f"Unknown VM image: {image_id}") from exc

    def verify(self, image_id: str, checksum: str) -> bool:
        image = self.get(image_id)
        return image.checksum.lower() == checksum.lower()


# ---------------------------------------------------------------------------
# IP address allocation
# ---------------------------------------------------------------------------

class IPPool:
    """
    Small IPv4 allocator.

    Addresses are allocated from a private network while network and broadcast
    addresses remain unavailable. Released addresses can be reused.
    """

    def __init__(self, network: str = "10.20.0.0/24") -> None:
        self.network = IPv4Network(network)
        self.allocated: Dict[str, str] = {}

    def allocate(self, vm_id: str) -> str:
        if vm_id in self.allocated:
            return self.allocated[vm_id]

        used = {IPv4Address(value) for value in self.allocated.values()}
        for address in self.network.hosts():
            if address not in used:
                value = str(address)
                self.allocated[vm_id] = value
                return value

        raise RuntimeError("The VM network address pool is exhausted.")

    def release(self, vm_id: str) -> None:
        self.allocated.pop(vm_id, None)


# ---------------------------------------------------------------------------
# VM manager
# ---------------------------------------------------------------------------

class VMManager:
    """
    Coordinates VM resources and lifecycle operations.

    This is deliberately modeled as a control-plane component. A real
    hypervisor would perform privileged operations such as creating page
    tables, configuring virtual CPU execution, attaching block devices, and
    connecting virtual NICs to a virtual switch.
    """

    VALID_TRANSITIONS = {
        VMState.DEFINED: {VMState.STARTING},
        VMState.STOPPED: {VMState.STARTING},
        VMState.STARTING: {VMState.RUNNING, VMState.FAILED},
        VMState.RUNNING: {VMState.PAUSED, VMState.STOPPING, VMState.FAILED},
        VMState.PAUSED: {VMState.RUNNING, VMState.STOPPING, VMState.FAILED},
        VMState.STOPPING: {VMState.STOPPED, VMState.FAILED},
        VMState.FAILED: {VMState.STARTING, VMState.STOPPED},
    }

    def __init__(self, host: Host, image_catalog: ImageCatalog) -> None:
        self.host = host
        self.image_catalog = image_catalog
        self.vms: Dict[str, VM] = {}
        self.ip_pool = IPPool()
        self.event_log: List[Dict[str, object]] = []

    def _log(self, event: str, vm_id: str, details: str = "") -> None:
        self.event_log.append(
            {
                "timestamp": time.time(),
                "event": event,
                "vm_id": vm_id,
                "details": details,
            }
        )

    def _transition(self, vm: VM, new_state: VMState) -> None:
        allowed = self.VALID_TRANSITIONS.get(vm.state, set())
        if new_state not in allowed:
            raise RuntimeError(
                f"Invalid lifecycle transition for {vm.name}: "
                f"{vm.state.value} -> {new_state.value}"
            )
        vm.state = new_state

    def _check_host_resources(
        self,
        cpu: CPUConfig,
        memory: MemoryConfig,
        disks: Dict[str, VirtualDisk],
    ) -> None:
        storage_required = sum(disk.size_gb for disk in disks.values())

        if cpu.vcpus > self.host.free_cpu:
            raise RuntimeError(
                f"Insufficient host CPU: requested {cpu.vcpus}, "
                f"available {self.host.free_cpu}."
            )

        if memory.allocated_mb > self.host.free_memory_mb:
            raise RuntimeError(
                f"Insufficient host memory: requested {memory.allocated_mb} MB, "
                f"available {self.host.free_memory_mb} MB."
            )

        if storage_required > self.host.free_storage_gb:
            raise RuntimeError(
                f"Insufficient host storage: requested {storage_required} GB, "
                f"available {self.host.free_storage_gb} GB."
            )

    def create_vm(
        self,
        vm_id: str,
        name: str,
        image_id: str,
        vcpus: int,
        memory_mb: int,
        disk_size_gb: int,
        network_mode: NetworkMode = NetworkMode.NAT,
    ) -> VM:
        if vm_id in self.vms:
            raise KeyError(f"VM {vm_id} already exists.")

        image = self.image_catalog.get(image_id)

        if disk_size_gb < image.size_gb:
            raise ValueError(
                f"Boot disk must be at least the image size of {image.size_gb} GB."
            )

        cpu = CPUConfig(vcpus=vcpus, max_vcpus=max(vcpus, vcpus * 2))
        memory = MemoryConfig(allocated_mb=memory_mb, max_mb=memory_mb * 2)
        disk = VirtualDisk(
            name="boot",
            size_gb=disk_size_gb,
            bus=DiskBus.VIRTIO,
            used_gb=float(image.size_gb),
            image_id=image_id,
        )

        mac = self._generate_mac(vm_id)
        interface = NetworkInterface(
            name="eth0",
            mac=mac,
            network="default",
            mode=network_mode,
        )

        self._check_host_resources(cpu, memory, {"boot": disk})

        vm = VM(
            vm_id=vm_id,
            name=name,
            cpu=cpu,
            memory=memory,
            disks={"boot": disk},
            interfaces={"eth0": interface},
            image_id=image_id,
        )
        vm.validate()

        self.vms[vm_id] = vm
        self.host.allocated_cpu += cpu.vcpus
        self.host.allocated_memory_mb += memory.allocated_mb
        self.host.allocated_storage_gb += disk.size_gb

        self._log("vm_created", vm_id, f"image={image_id}")
        return vm

    @staticmethod
    def _generate_mac(vm_id: str) -> str:
        """
        Generates a deterministic locally administered MAC.

        The first octet has the local-administration bit set. This simulator
        does not connect the address to a physical Ethernet segment.
        """
        digest = sum(ord(char) for char in vm_id)
        values = [
            0x02,
            (digest >> 8) & 0xFF,
            digest & 0xFF,
            (digest * 3) & 0xFF,
            (digest * 5) & 0xFF,
            (digest * 7) & 0xFF,
        ]
        return ":".join(f"{value:02x}" for value in values)

    def get_vm(self, vm_id: str) -> VM:
        try:
            return self.vms[vm_id]
        except KeyError as exc:
            raise KeyError(f"Unknown VM: {vm_id}") from exc

    def start(self, vm_id: str) -> None:
        vm = self.get_vm(vm_id)

        if vm.state not in {VMState.DEFINED, VMState.STOPPED, VMState.FAILED}:
            raise RuntimeError(f"VM {vm.name} cannot be started from {vm.state.value}.")

        self._transition(vm, VMState.STARTING)

        try:
            # Assigning an address is modeled as part of virtual NIC activation.
            vm.interfaces["eth0"].ip = self.ip_pool.allocate(vm_id)

            # A real hypervisor would load the VM image, construct guest page
            # tables, initialize virtual devices, and transfer control to the
            # guest boot firmware here.
            if vm.image_id is None:
                raise RuntimeError("VM has no boot image.")

            vm.boot_count += 1
            vm.last_error = None
            self._transition(vm, VMState.RUNNING)
            self._log("vm_started", vm_id, f"ip={vm.interfaces['eth0'].ip}")
        except Exception as exc:
            vm.last_error = str(exc)
            vm.state = VMState.FAILED
            self._log("vm_start_failed", vm_id, str(exc))
            raise

    def stop(self, vm_id: str) -> None:
        vm = self.get_vm(vm_id)

        if vm.state not in {VMState.RUNNING, VMState.PAUSED}:
            raise RuntimeError(f"VM {vm.name} cannot be stopped from {vm.state.value}.")

        self._transition(vm, VMState.STOPPING)

        # The simulator performs a graceful stop immediately. A real system
        # would wait for the guest OS and could eventually issue a hard poweroff.
        self.ip_pool.release(vm_id)
        for interface in vm.interfaces.values():
            interface.ip = None

        self._transition(vm, VMState.STOPPED)
        self._log("vm_stopped", vm_id)

    def pause(self, vm_id: str) -> None:
        vm = self.get_vm(vm_id)
        if vm.state != VMState.RUNNING:
            raise RuntimeError("Only a running VM can be paused.")
        self._transition(vm, VMState.PAUSED)
        self._log("vm_paused", vm_id)

    def resume(self, vm_id: str) -> None:
        vm = self.get_vm(vm_id)
        if vm.state != VMState.PAUSED:
            raise RuntimeError("Only a paused VM can be resumed.")
        self._transition(vm, VMState.RUNNING)
        self._log("vm_resumed", vm_id)

    def restart(self, vm_id: str) -> None:
        vm = self.get_vm(vm_id)
        if vm.state not in {VMState.RUNNING, VMState.PAUSED}:
            raise RuntimeError("Only a running or paused VM can be restarted.")
        self.stop(vm_id)
        self.start(vm_id)
        self._log("vm_restarted", vm_id)

    def destroy(self, vm_id: str) -> None:
        vm = self.get_vm(vm_id)

        if vm.state in {VMState.RUNNING, VMState.PAUSED, VMState.STARTING}:
            raise RuntimeError("Stop the VM before destroying it.")

        self.ip_pool.release(vm_id)
        self.host.allocated_cpu -= vm.cpu.vcpus
        self.host.allocated_memory_mb -= vm.memory.allocated_mb
        self.host.allocated_storage_gb -= vm.disk_capacity_gb
        del self.vms[vm_id]
        self._log("vm_destroyed", vm_id)

    def resize_memory(self, vm_id: str, new_memory_mb: int) -> None:
        vm = self.get_vm(vm_id)
        if new_memory_mb < 128:
            raise ValueError("VM memory cannot be below 128 MB.")
        if new_memory_mb > vm.memory.max_mb:
            raise ValueError(
                f"Requested memory exceeds configured maximum of "
                f"{vm.memory.max_mb} MB."
            )

        delta = new_memory_mb - vm.memory.allocated_mb
        if delta > self.host.free_memory_mb:
            raise RuntimeError("Host lacks enough free memory for the resize.")

        vm.memory.allocated_mb = new_memory_mb
        self.host.allocated_memory_mb += delta
        self._log("memory_resized", vm_id, f"new_memory_mb={new_memory_mb}")

    def resize_vcpus(self, vm_id: str, new_vcpus: int) -> None:
        vm = self.get_vm(vm_id)
        if new_vcpus < 1 or new_vcpus > vm.cpu.max_vcpus:
            raise ValueError("Requested vCPU count is outside the configured range.")

        delta = new_vcpus - vm.cpu.vcpus
        if delta > self.host.free_cpu:
            raise RuntimeError("Host lacks enough free CPU cores.")

        vm.cpu.vcpus = new_vcpus
        self.host.allocated_cpu += delta
        self._log("cpu_resized", vm_id, f"new_vcpus={new_vcpus}")

    def add_disk(
        self,
        vm_id: str,
        disk_name: str,
        size_gb: int,
        bus: DiskBus = DiskBus.VIRTIO,
    ) -> None:
        vm = self.get_vm(vm_id)
        if disk_name in vm.disks:
            raise KeyError(f"Disk {disk_name} already exists.")
        if size_gb <= 0:
            raise ValueError("Disk size must be positive.")
        if size_gb > self.host.free_storage_gb:
            raise RuntimeError("Host lacks enough free storage.")

        disk = VirtualDisk(name=disk_name, size_gb=size_gb, bus=bus)
        vm.disks[disk_name] = disk
        self.host.allocated_storage_gb += size_gb
        self._log("disk_added", vm_id, f"disk={disk_name},size_gb={size_gb}")

    def write_disk(self, vm_id: str, disk_name: str, gb: float) -> None:
        vm = self.get_vm(vm_id)
        disk = self._get_disk(vm, disk_name)
        disk.write(gb)

        # A snapshot causes changed blocks to consume additional storage in a
        # copy-on-write design. This is represented as logical changed capacity.
        for snapshot in vm.snapshots.values():
            snapshot.changed_gb_since_snapshot += gb

        self._log("disk_write", vm_id, f"disk={disk_name},gb={gb:.2f}")

    def read_disk(self, vm_id: str, disk_name: str, gb: float) -> None:
        vm = self.get_vm(vm_id)
        disk = self._get_disk(vm, disk_name)
        disk.read(gb)
        self._log("disk_read", vm_id, f"disk={disk_name},gb={gb:.2f}")

    @staticmethod
    def _get_disk(vm: VM, disk_name: str) -> VirtualDisk:
        try:
            return vm.disks[disk_name]
        except KeyError as exc:
            raise KeyError(f"Unknown disk {disk_name} on VM {vm.name}.") from exc

    def send_network(self, vm_id: str, interface_name: str, mb: float) -> None:
        vm = self.get_vm(vm_id)
        interface = self._get_interface(vm, interface_name)
        interface.transmit(mb)
        self._log("network_tx", vm_id, f"interface={interface_name},mb={mb:.2f}")

    def receive_network(self, vm_id: str, interface_name: str, mb: float) -> None:
        vm = self.get_vm(vm_id)
        interface = self._get_interface(vm, interface_name)
        interface.receive(mb)
        self._log("network_rx", vm_id, f"interface={interface_name},mb={mb:.2f}")

    @staticmethod
    def _get_interface(vm: VM, interface_name: str) -> NetworkInterface:
        try:
            return vm.interfaces[interface_name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown network interface {interface_name} on VM {vm.name}."
            ) from exc

    def create_snapshot(
        self,
        vm_id: str,
        snapshot_id: str,
        name: str,
        include_memory: bool = False,
    ) -> Snapshot:
        vm = self.get_vm(vm_id)
        if snapshot_id in vm.snapshots:
            raise KeyError(f"Snapshot {snapshot_id} already exists.")

        if vm.state not in {VMState.RUNNING, VMState.PAUSED, VMState.STOPPED}:
            raise RuntimeError("VM must be operational before taking a snapshot.")

        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            vm_id=vm_id,
            name=name,
            created_at=time.time(),
            disk_used_at_creation={
                name: disk.used_gb for name, disk in vm.disks.items()
            },
            memory_state_captured=include_memory,
        )
        vm.snapshots[snapshot_id] = snapshot
        self._log(
            "snapshot_created",
            vm_id,
            f"snapshot={snapshot_id},memory={include_memory}",
        )
        return snapshot

    def restore_snapshot(self, vm_id: str, snapshot_id: str) -> None:
        vm = self.get_vm(vm_id)
        if snapshot_id not in vm.snapshots:
            raise KeyError(f"Unknown snapshot {snapshot_id}.")

        snapshot = vm.snapshots[snapshot_id]

        if vm.state in {VMState.RUNNING, VMState.PAUSED}:
            self.stop(vm_id)

        for disk_name, original_used in snapshot.disk_used_at_creation.items():
            if disk_name in vm.disks:
                vm.disks[disk_name].used_gb = original_used

        for snapshot_record in vm.snapshots.values():
            if snapshot_record.created_at >= snapshot.created_at:
                snapshot_record.changed_gb_since_snapshot = 0.0

        self._log("snapshot_restored", vm_id, f"snapshot={snapshot_id}")

    def delete_snapshot(self, vm_id: str, snapshot_id: str) -> None:
        vm = self.get_vm(vm_id)
        if snapshot_id not in vm.snapshots:
            raise KeyError(f"Unknown snapshot {snapshot_id}.")
        del vm.snapshots[snapshot_id]
        self._log("snapshot_deleted", vm_id, f"snapshot={snapshot_id}")

    def simulate_workload(
        self,
        vm_id: str,
        seconds: float,
        cpu_utilization: float,
        memory_pressure: float,
        disk_write_gb: float = 0.0,
        network_tx_mb: float = 0.0,
        network_rx_mb: float = 0.0,
    ) -> None:
        vm = self.get_vm(vm_id)

        if vm.state != VMState.RUNNING:
            raise RuntimeError("Workload simulation requires a running VM.")
        if seconds <= 0:
            raise ValueError("Workload duration must be positive.")
        if not 0 <= cpu_utilization <= 100:
            raise ValueError("CPU utilization must be between 0 and 100.")
        if not 0 <= memory_pressure <= 100:
            raise ValueError("Memory pressure must be between 0 and 100.")

        effective_cpu = min(cpu_utilization, vm.cpu.cpu_limit_percent)
        vm.uptime_seconds += seconds
        vm.cpu_time_seconds += seconds * effective_cpu / 100.0
        vm.memory_pressure_percent = memory_pressure

        if disk_write_gb:
            self.write_disk(vm_id, "boot", disk_write_gb)
        if network_tx_mb:
            self.send_network(vm_id, "eth0", network_tx_mb)
        if network_rx_mb:
            self.receive_network(vm_id, "eth0", network_rx_mb)

        self._log(
            "workload_simulated",
            vm_id,
            (
                f"seconds={seconds},cpu={cpu_utilization},"
                f"memory_pressure={memory_pressure}"
            ),
        )

    def resource_report(self) -> Dict[str, object]:
        return {
            "host": self.host.name,
            "cpu": {
                "total": self.host.physical_cpu_cores,
                "allocated": self.host.allocated_cpu,
                "free": self.host.free_cpu,
            },
            "memory_mb": {
                "total": self.host.memory_mb,
                "allocated": self.host.allocated_memory_mb,
                "free": self.host.free_memory_mb,
            },
            "storage_gb": {
                "total": self.host.storage_gb,
                "allocated": self.host.allocated_storage_gb,
                "free": self.host.free_storage_gb,
            },
            "vm_count": len(self.vms),
            "running_vms": sum(
                vm.state == VMState.RUNNING for vm in self.vms.values()
            ),
        }

    def vm_report(self, vm_id: str) -> Dict[str, object]:
        vm = self.get_vm(vm_id)
        return {
            "vm_id": vm.vm_id,
            "name": vm.name,
            "state": vm.state.value,
            "boot_count": vm.boot_count,
            "vcpus": vm.cpu.vcpus,
            "cpu_limit_percent": vm.cpu.cpu_limit_percent,
            "memory_mb": vm.memory.allocated_mb,
            "memory_max_mb": vm.memory.max_mb,
            "disk_capacity_gb": vm.disk_capacity_gb,
            "disk_used_gb": round(vm.disk_used_gb, 2),
            "network": {
                name: {
                    "mac": interface.mac,
                    "ip": interface.ip,
                    "mode": interface.mode.value,
                    "rx_mb": round(interface.rx_mb, 2),
                    "tx_mb": round(interface.tx_mb, 2),
                }
                for name, interface in vm.interfaces.items()
            },
            "snapshots": {
                snapshot_id: {
                    "name": snapshot.name,
                    "age_seconds": round(snapshot.age_seconds, 2),
                    "changed_gb": round(snapshot.changed_gb_since_snapshot, 2),
                    "memory_state": snapshot.memory_state_captured,
                }
                for snapshot_id, snapshot in vm.snapshots.items()
            },
            "uptime_seconds": round(vm.uptime_seconds, 2),
            "cpu_time_seconds": round(vm.cpu_time_seconds, 2),
            "memory_pressure_percent": round(vm.memory_pressure_percent, 2),
            "last_error": vm.last_error,
        }

    def export_state(self, path: str) -> None:
        """
        Serialize control-plane state.

        Enum values are converted explicitly because JSON does not understand
        Python Enum objects. Runtime-only structures such as the IP network
        object are reconstructed during import.
        """
        payload = {
            "host": {
                "name": self.host.name,
                "physical_cpu_cores": self.host.physical_cpu_cores,
                "memory_mb": self.host.memory_mb,
                "storage_gb": self.host.storage_gb,
                "allocated_cpu": self.host.allocated_cpu,
                "allocated_memory_mb": self.host.allocated_memory_mb,
                "allocated_storage_gb": self.host.allocated_storage_gb,
                "running_vms": sorted(self.host.running_vms),
            },
            "images": {
                image_id: asdict(image)
                for image_id, image in self.image_catalog.images.items()
            },
            "vms": self._serialize_vms(),
            "ip_allocations": self.ip_pool.allocated,
            "events": self.event_log,
        }

        Path(path).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _serialize_vms(self) -> Dict[str, object]:
        output: Dict[str, object] = {}

        for vm_id, vm in self.vms.items():
            vm_data = {
                "vm_id": vm.vm_id,
                "name": vm.name,
                "cpu": asdict(vm.cpu),
                "memory": asdict(vm.memory),
                "disks": {
                    name: {
                        **asdict(disk),
                        "bus": disk.bus.value,
                    }
                    for name, disk in vm.disks.items()
                },
                "interfaces": {
                    name: {
                        **asdict(interface),
                        "mode": interface.mode.value,
                    }
                    for name, interface in vm.interfaces.items()
                },
                "image_id": vm.image_id,
                "state": vm.state.value,
                "snapshots": {
                    snapshot_id: asdict(snapshot)
                    for snapshot_id, snapshot in vm.snapshots.items()
                },
                "uptime_seconds": vm.uptime_seconds,
                "cpu_time_seconds": vm.cpu_time_seconds,
                "memory_pressure_percent": vm.memory_pressure_percent,
                "boot_count": vm.boot_count,
                "last_error": vm.last_error,
            }
            output[vm_id] = vm_data

        return output

    @classmethod
    def import_state(cls, path: str) -> "VMManager":
        """
        Reconstruct a VM manager from JSON exported by export_state().

        This demonstrates the difference between persistent control-plane
        metadata and ephemeral hypervisor state. The imported model represents
        configuration; it does not attempt to resume a real guest CPU.
        """
        payload = json.loads(Path(path).read_text(encoding="utf-8"))

        host_data = payload["host"]
        host = Host(
            name=host_data["name"],
            physical_cpu_cores=host_data["physical_cpu_cores"],
            memory_mb=host_data["memory_mb"],
            storage_gb=host_data["storage_gb"],
            allocated_cpu=host_data["allocated_cpu"],
            allocated_memory_mb=host_data["allocated_memory_mb"],
            allocated_storage_gb=host_data["allocated_storage_gb"],
            running_vms=set(host_data.get("running_vms", [])),
        )

        catalog = ImageCatalog()
        for image_data in payload["images"].values():
            catalog.add(VMImage(**image_data))

        manager = cls(host, catalog)

        for vm_data in payload["vms"].values():
            cpu = CPUConfig(**vm_data["cpu"])
            memory = MemoryConfig(**vm_data["memory"])

            disks = {}
            for name, disk_data in vm_data["disks"].items():
                disk_data = dict(disk_data)
                disk_data["bus"] = DiskBus(disk_data["bus"])
                disks[name] = VirtualDisk(**disk_data)

            interfaces = {}
            for name, interface_data in vm_data["interfaces"].items():
                interface_data = dict(interface_data)
                interface_data["mode"] = NetworkMode(interface_data["mode"])
                interfaces[name] = NetworkInterface(**interface_data)

            snapshots = {
                snapshot_id: Snapshot(**snapshot_data)
                for snapshot_id, snapshot_data in vm_data["snapshots"].items()
            }

            vm = VM(
                vm_id=vm_data["vm_id"],
                name=vm_data["name"],
                cpu=cpu,
                memory=memory,
                disks=disks,
                interfaces=interfaces,
                image_id=vm_data["image_id"],
                state=VMState(vm_data["state"]),
                snapshots=snapshots,
                uptime_seconds=vm_data["uptime_seconds"],
                cpu_time_seconds=vm_data["cpu_time_seconds"],
                memory_pressure_percent=vm_data["memory_pressure_percent"],
                boot_count=vm_data["boot_count"],
                last_error=vm_data["last_error"],
            )
            manager.vms[vm.vm_id] = vm

        manager.ip_pool.allocated = dict(payload["ip_allocations"])
        manager.event_log = list(payload["events"])
        return manager


# ---------------------------------------------------------------------------
# Demonstration helpers
# ---------------------------------------------------------------------------

def print_json(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(value, indent=2, sort_keys=True))


def demonstrate_validation(manager: VMManager) -> None:
    print("\n=== Validation and failure handling ===")

    try:
        manager.create_vm(
            vm_id="too-small",
            name="Invalid Disk VM",
            image_id="ubuntu-24",
            vcpus=1,
            memory_mb=512,
            disk_size_gb=4,
        )
    except ValueError as exc:
        print(f"Expected validation failure: {exc}")

    vm = manager.get_vm("analytics")
    try:
        manager.resize_memory(vm.vm_id, vm.memory.max_mb + 1)
    except ValueError as exc:
        print(f"Expected resize failure: {exc}")

    try:
        manager.write_disk(vm.vm_id, "boot", 1000)
    except OSError as exc:
        print(f"Expected disk failure: {exc}")

    try:
        manager.pause(vm.vm_id)
        manager.pause(vm.vm_id)
    except RuntimeError as exc:
        print(f"Expected lifecycle failure: {exc}")

    manager.resume(vm.vm_id)


def demonstrate_cpu_scheduling() -> None:
    """
    Demonstrate proportional CPU scheduling.

    CPU shares do not create physical CPU cores. They are a weighting mechanism
    used here to distribute a fixed amount of host CPU time among runnable VMs.
    """
    print("\n=== CPU share scheduling ===")

    runnable = [
        ("database", 2048, 4),
        ("api", 1024, 2),
        ("worker", 512, 1),
    ]
    total_shares = sum(shares for _, shares, _ in runnable)
    available_core_seconds = 4.0

    for name, shares, vcpus in runnable:
        allocation = available_core_seconds * shares / total_shares
        print(
            f"{name:10} vCPUs={vcpus} shares={shares:4} "
            f"scheduled_core_seconds={allocation:.3f}"
        )


def demonstrate_memory_ballooning(vm: VM) -> None:
    """
    Model guest memory reclamation.

    Ballooning is cooperative: the hypervisor asks a guest balloon driver to
    allocate pages, causing the guest to release those physical pages back to
    the host. It is not equivalent to silently deleting arbitrary guest data.
    """
    print("\n=== Memory ballooning ===")

    if not vm.memory.balloon_enabled:
        print("Ballooning is disabled.")
        return

    original = vm.memory.allocated_mb
    reclaim_target = max(128, int(original * 0.75))
    reclaimed = original - reclaim_target
    vm.memory.allocated_mb = reclaim_target

    print(f"Allocated before ballooning: {original} MB")
    print(f"Allocated after ballooning:  {reclaim_target} MB")
    print(f"Reclaimed from guest:        {reclaimed} MB")


def demonstrate_network_policy() -> None:
    """
    A minimal network-policy example.

    The rule model illustrates that a virtual NIC can be attached to a logical
    network while traffic policy determines which flows are permitted.
    """
    print("\n=== Virtual network policy ===")

    rules = [
        {"source": "10.20.0.0/24", "destination_port": 443, "action": "allow"},
        {"source": "10.20.0.0/24", "destination_port": 22, "action": "deny"},
        {"source": "10.20.0.0/24", "destination_port": 53, "action": "allow"},
    ]

    for rule in rules:
        print(
            f"{rule['source']} -> port {rule['destination_port']:>3}: "
            f"{rule['action']}"
        )


def demonstrate_image_integrity(catalog: ImageCatalog) -> None:
    print("\n=== Image integrity ===")

    image = catalog.get("ubuntu-24")
    print(f"Image: {image.name}")
    print(f"Checksum: {image.checksum}")
    print(
        "Checksum verification:",
        catalog.verify(image.image_id, image.checksum),
    )
    print(
        "Wrong checksum verification:",
        catalog.verify(image.image_id, "not-the-real-checksum"),
    )


def demonstrate_snapshot_behavior(manager: VMManager) -> None:
    print("\n=== Snapshot and copy-on-write behavior ===")

    vm = manager.get_vm("analytics")

    snapshot = manager.create_snapshot(
        vm_id=vm.vm_id,
        snapshot_id="analytics-before-upgrade",
        name="Before analytics upgrade",
        include_memory=False,
    )

    before = vm.disks["boot"].used_gb
    manager.write_disk(vm.vm_id, "boot", 3.5)
    after = vm.disks["boot"].used_gb

    print(f"Disk usage at snapshot: {before:.2f} GB")
    print(f"Disk usage after change: {after:.2f} GB")
    print(
        f"Changed capacity tracked by snapshot: "
        f"{snapshot.changed_gb_since_snapshot:.2f} GB"
    )

    manager.restore_snapshot(vm.vm_id, snapshot.snapshot_id)
    print(
        f"Disk usage after restore: "
        f"{vm.disks['boot'].used_gb:.2f} GB"
    )


def build_demo_manager() -> VMManager:
    catalog = ImageCatalog()

    catalog.add(
        VMImage(
            image_id="ubuntu-24",
            name="Ubuntu Server 24.04",
            os_family="Linux",
            version="24.04",
            size_gb=8,
            checksum="sha256:ubuntu-demo-verified",
            architecture="x86_64",
            description="Minimal Linux server image for application workloads.",
        )
    )

    catalog.add(
        VMImage(
            image_id="debian-13",
            name="Debian 13",
            os_family="Linux",
            version="13",
            size_gb=6,
            checksum="sha256:debian-demo-verified",
            architecture="x86_64",
            description="General-purpose Debian server image.",
        )
    )

    host = Host(
        name="compute-01",
        physical_cpu_cores=16,
        memory_mb=32768,
        storage_gb=1000,
    )

    manager = VMManager(host, catalog)

    manager.create_vm(
        vm_id="analytics",
        name="Analytics Server",
        image_id="ubuntu-24",
        vcpus=4,
        memory_mb=4096,
        disk_size_gb=40,
    )

    manager.create_vm(
        vm_id="api",
        name="API Server",
        image_id="debian-13",
        vcpus=2,
        memory_mb=2048,
        disk_size_gb=25,
        network_mode=NetworkMode.BRIDGED,
    )

    return manager


def run_demo() -> None:
    print("Virtual Machine Management Simulator")

    manager = build_demo_manager()

    print_json("Initial host resources", manager.resource_report())

    demonstrate_image_integrity(manager.image_catalog)

    manager.start("analytics")
    manager.start("api")

    analytics = manager.get_vm("analytics")
    manager.add_disk("analytics", "data", 100, DiskBus.SCSI)

    manager.simulate_workload(
        vm_id="analytics",
        seconds=30,
        cpu_utilization=82,
        memory_pressure=68,
        disk_write_gb=4,
        network_tx_mb=250,
        network_rx_mb=180,
    )

    manager.simulate_workload(
        vm_id="api",
        seconds=30,
        cpu_utilization=45,
        memory_pressure=42,
        disk_write_gb=1.5,
        network_tx_mb=95,
        network_rx_mb=420,
    )

    print_json("Analytics VM after workload", manager.vm_report("analytics"))

    demonstrate_cpu_scheduling()
    demonstrate_memory_ballooning(analytics)
    demonstrate_network_policy()

    demonstrate_snapshot_behavior(manager)

    manager.pause("analytics")
    print(f"\nAnalytics state after pause: {analytics.state.value}")
    manager.resume("analytics")
    print(f"Analytics state after resume: {analytics.state.value}")

    manager.stop("api")
    print(f"API state after graceful stop: {manager.get_vm('api').state.value}")

    manager.restart("analytics")
    print(f"Analytics state after restart: {manager.get_vm('analytics').state.value}")

    demonstrate_validation(manager)

    state_file = "vm_manager_state.json"
    manager.export_state(state_file)
    print(f"\nPersistent control-plane state exported to {state_file}")

    restored = VMManager.import_state(state_file)
    print_json("Restored manager state", restored.resource_report())

    # The temporary file is intentionally removed after demonstrating
    # serialization so that the script does not leave operational state behind.
    Path(state_file).unlink(missing_ok=True)

    print_json("Event log", manager.event_log)


if __name__ == "__main__":
    run_demo()
