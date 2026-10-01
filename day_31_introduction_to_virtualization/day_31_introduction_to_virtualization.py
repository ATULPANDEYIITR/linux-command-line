"""
Introduction to Virtualization

A self-contained executable learning program that models:
- Physical server resources
- Hypervisor-based resource abstraction
- Virtual machines
- CPU, memory, storage, and network allocation
- Resource overcommitment and capacity validation
- VM lifecycle operations
- Isolation boundaries
- Resource utilization and virtualization benefits
- Basic consolidation analysis

The simulation intentionally uses standard Python only so it can run without
external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import math


def heading(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subheading(title: str) -> None:
    print(f"\n--- {title} ---")


# ---------------------------------------------------------------------------
# Physical infrastructure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhysicalServer:
    """
    Represents a physical machine before virtualization abstracts its hardware.

    CPU capacity is expressed as logical CPU units, memory in GiB, storage in
    GiB, and network capacity in Gbps.
    """

    name: str
    cpu_cores: int
    memory_gib: int
    storage_gib: int
    network_gbps: float

    def __post_init__(self) -> None:
        if self.cpu_cores <= 0:
            raise ValueError("CPU cores must be positive.")
        if self.memory_gib <= 0:
            raise ValueError("Memory must be positive.")
        if self.storage_gib <= 0:
            raise ValueError("Storage must be positive.")
        if self.network_gbps <= 0:
            raise ValueError("Network capacity must be positive.")

    def describe(self) -> None:
        print(f"Physical server: {self.name}")
        print(f"  CPU cores:       {self.cpu_cores}")
        print(f"  Memory:          {self.memory_gib} GiB")
        print(f"  Storage:         {self.storage_gib} GiB")
        print(f"  Network:         {self.network_gbps:.1f} Gbps")


@dataclass
class ResourceRequest:
    """Requested virtual resources for a VM."""

    cpu_cores: int
    memory_gib: int
    storage_gib: int
    network_gbps: float

    def validate(self) -> None:
        if self.cpu_cores <= 0:
            raise ValueError("VM CPU allocation must be positive.")
        if self.memory_gib <= 0:
            raise ValueError("VM memory allocation must be positive.")
        if self.storage_gib <= 0:
            raise ValueError("VM storage allocation must be positive.")
        if self.network_gbps <= 0:
            raise ValueError("VM network allocation must be positive.")


# ---------------------------------------------------------------------------
# Virtual machine lifecycle
# ---------------------------------------------------------------------------

class VMState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class VirtualMachine:
    """
    A VM receives virtual hardware rather than directly owning physical
    hardware. The hypervisor maps these virtual resources onto host resources.
    """

    name: str
    operating_system: str
    request: ResourceRequest
    state: VMState = VMState.STOPPED
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    disk_usage_percent: float = 0.0
    network_usage_percent: float = 0.0

    def __post_init__(self) -> None:
        self.request.validate()

    def start(self) -> None:
        if self.state == VMState.RUNNING:
            raise RuntimeError(f"{self.name} is already running.")
        self.state = VMState.RUNNING

    def stop(self) -> None:
        if self.state == VMState.STOPPED:
            raise RuntimeError(f"{self.name} is already stopped.")
        self.state = VMState.STOPPED

    def pause(self) -> None:
        if self.state != VMState.RUNNING:
            raise RuntimeError(f"{self.name} can only be paused while running.")
        self.state = VMState.PAUSED

    def resume(self) -> None:
        if self.state != VMState.PAUSED:
            raise RuntimeError(f"{self.name} can only be resumed from paused state.")
        self.state = VMState.RUNNING

    def set_utilization(
        self,
        cpu: float,
        memory: float,
        disk: float,
        network: float,
    ) -> None:
        values = {
            "CPU": cpu,
            "memory": memory,
            "disk": disk,
            "network": network,
        }
        for resource, value in values.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{resource} utilization must be between 0 and 100.")

        self.cpu_usage_percent = cpu
        self.memory_usage_percent = memory
        self.disk_usage_percent = disk
        self.network_usage_percent = network

    def actual_usage(self) -> ResourceRequest:
        """
        Converts utilization percentages into approximate current resource
        consumption. This demonstrates the distinction between allocated
        virtual capacity and actual workload consumption.
        """
        if self.state != VMState.RUNNING:
            return ResourceRequest(0, 0, 0, 0.0)

        return ResourceRequest(
            cpu_cores=max(0, math.ceil(
                self.request.cpu_cores * self.cpu_usage_percent / 100
            )),
            memory_gib=max(0, math.ceil(
                self.request.memory_gib * self.memory_usage_percent / 100
            )),
            storage_gib=max(0, math.ceil(
                self.request.storage_gib * self.disk_usage_percent / 100
            )),
            network_gbps=(
                self.request.network_gbps
                * self.network_usage_percent
                / 100
            ),
        )


# ---------------------------------------------------------------------------
# Hypervisor and resource abstraction
# ---------------------------------------------------------------------------

@dataclass
class Hypervisor:
    """
    Models the software layer between physical hardware and VMs.

    The hypervisor maintains VM definitions and enforces resource allocation
    policy. It does not make physical resources disappear; it multiplexes them
    among virtual machines.
    """

    host: PhysicalServer
    allow_cpu_overcommit: bool = True
    vms: Dict[str, VirtualMachine] = field(default_factory=dict)

    def create_vm(
        self,
        name: str,
        operating_system: str,
        request: ResourceRequest,
    ) -> VirtualMachine:
        if name in self.vms:
            raise ValueError(f"A VM named {name!r} already exists.")

        request.validate()

        if request.memory_gib > self.host.memory_gib:
            raise ValueError(
                f"{name}: requested memory exceeds physical host memory."
            )

        if request.storage_gib > self.host.storage_gib:
            raise ValueError(
                f"{name}: requested storage exceeds physical host storage."
            )

        if request.network_gbps > self.host.network_gbps:
            raise ValueError(
                f"{name}: requested network exceeds host network capacity."
            )

        vm = VirtualMachine(name, operating_system, request)
        self.vms[name] = vm
        return vm

    def delete_vm(self, name: str) -> None:
        vm = self.vms.get(name)
        if vm is None:
            raise KeyError(f"Unknown VM: {name}")
        if vm.state == VMState.RUNNING:
            raise RuntimeError("A running VM must be stopped before deletion.")
        del self.vms[name]

    def allocated_resources(self) -> ResourceRequest:
        """Sum configured virtual resources across all VMs."""
        return ResourceRequest(
            cpu_cores=sum(vm.request.cpu_cores for vm in self.vms.values()),
            memory_gib=sum(vm.request.memory_gib for vm in self.vms.values()),
            storage_gib=sum(vm.request.storage_gib for vm in self.vms.values()),
            network_gbps=sum(
                vm.request.network_gbps for vm in self.vms.values()
            ),
        )

    def actual_host_usage(self) -> ResourceRequest:
        """Sum current workload consumption across running VMs."""
        usages = [vm.actual_usage() for vm in self.vms.values()]
        return ResourceRequest(
            cpu_cores=sum(item.cpu_cores for item in usages),
            memory_gib=sum(item.memory_gib for item in usages),
            storage_gib=sum(item.storage_gib for item in usages),
            network_gbps=sum(item.network_gbps for item in usages),
        )

    def check_capacity(self) -> Dict[str, bool]:
        allocated = self.allocated_resources()

        return {
            "cpu": (
                self.allow_cpu_overcommit
                or allocated.cpu_cores <= self.host.cpu_cores
            ),
            "memory": allocated.memory_gib <= self.host.memory_gib,
            "storage": allocated.storage_gib <= self.host.storage_gib,
            "network": allocated.network_gbps <= self.host.network_gbps,
        }

    def utilization_report(self) -> None:
        allocated = self.allocated_resources()
        actual = self.actual_host_usage()

        print(f"Host: {self.host.name}")
        print(
            f"  CPU:     allocated={allocated.cpu_cores} cores, "
            f"active={actual.cpu_cores} cores, "
            f"physical={self.host.cpu_cores} cores"
        )
        print(
            f"  Memory:  allocated={allocated.memory_gib} GiB, "
            f"active={actual.memory_gib} GiB, "
            f"physical={self.host.memory_gib} GiB"
        )
        print(
            f"  Storage: allocated={allocated.storage_gib} GiB, "
            f"physical={self.host.storage_gib} GiB"
        )
        print(
            f"  Network: allocated={allocated.network_gbps:.1f} Gbps, "
            f"physical={self.host.network_gbps:.1f} Gbps"
        )

        checks = self.check_capacity()
        print("  Capacity checks:")
        for resource, passed in checks.items():
            print(f"    {resource:<8}: {'PASS' if passed else 'FAIL'}")

    def list_vms(self) -> None:
        if not self.vms:
            print("No virtual machines configured.")
            return

        for vm in self.vms.values():
            print(
                f"{vm.name:<16} "
                f"OS={vm.operating_system:<12} "
                f"CPU={vm.request.cpu_cores:<2} "
                f"RAM={vm.request.memory_gib:<3} GiB "
                f"State={vm.state.value}"
            )


# ---------------------------------------------------------------------------
# Resource abstraction demonstration
# ---------------------------------------------------------------------------

def demonstrate_resource_abstraction() -> None:
    heading("Physical Server and Virtual Resource Abstraction")

    host = PhysicalServer(
        name="compute-host-01",
        cpu_cores=16,
        memory_gib=64,
        storage_gib=1000,
        network_gbps=10.0,
    )
    host.describe()

    print(
        "\nThe physical server exposes hardware capacity directly to the "
        "hypervisor. VMs see virtual CPUs, virtual memory, virtual disks, and "
        "virtual network interfaces instead of owning the host hardware."
    )

    hypervisor = Hypervisor(host=host)

    web_vm = hypervisor.create_vm(
        "web-server",
        "Linux",
        ResourceRequest(4, 16, 120, 2.0),
    )

    database_vm = hypervisor.create_vm(
        "database",
        "Linux",
        ResourceRequest(6, 24, 300, 4.0),
    )

    analytics_vm = hypervisor.create_vm(
        "analytics",
        "Linux",
        ResourceRequest(8, 16, 200, 3.0),
    )

    web_vm.start()
    database_vm.start()
    analytics_vm.start()

    web_vm.set_utilization(35, 50, 20, 15)
    database_vm.set_utilization(70, 75, 60, 40)
    analytics_vm.set_utilization(20, 40, 30, 10)

    subheading("Configured virtual machines")
    hypervisor.list_vms()

    subheading("Host capacity versus virtual allocation")
    hypervisor.utilization_report()

    print(
        "\nCPU overcommit is enabled in this simulation: 18 virtual CPU cores "
        "can be assigned to a 16-core host because the hypervisor schedules "
        "CPU execution over time. Memory is not overcommitted here, so the "
        "allocated 56 GiB remains below the host's 64 GiB."
    )


# ---------------------------------------------------------------------------
# VM lifecycle demonstration
# ---------------------------------------------------------------------------

def demonstrate_vm_lifecycle() -> None:
    heading("Virtual Machine Lifecycle")

    host = PhysicalServer("lifecycle-host", 8, 32, 500, 5.0)
    hypervisor = Hypervisor(host)

    vm = hypervisor.create_vm(
        "application-server",
        "Linux",
        ResourceRequest(2, 8, 80, 1.0),
    )

    print(f"Initial state: {vm.state.value}")

    vm.start()
    print(f"After start:   {vm.state.value}")

    vm.pause()
    print(f"After pause:   {vm.state.value}")

    vm.resume()
    print(f"After resume:  {vm.state.value}")

    vm.stop()
    print(f"After stop:    {vm.state.value}")

    try:
        vm.resume()
    except RuntimeError as error:
        print(f"Expected lifecycle error: {error}")


# ---------------------------------------------------------------------------
# Consolidation and utilization
# ---------------------------------------------------------------------------

@dataclass
class PhysicalWorkload:
    name: str
    cpu_cores: int
    memory_gib: int

    def __post_init__(self) -> None:
        if self.cpu_cores <= 0 or self.memory_gib <= 0:
            raise ValueError("Workload resources must be positive.")


def compare_non_virtualized_and_virtualized() -> None:
    heading("Server Consolidation and Utilization")

    workloads = [
        PhysicalWorkload("web", 4, 8),
        PhysicalWorkload("database", 8, 24),
        PhysicalWorkload("analytics", 4, 12),
    ]

    dedicated_cpu = sum(w.cpu_cores for w in workloads)
    dedicated_memory = sum(w.memory_gib for w in workloads)

    print("Traditional dedicated-server model:")
    print(f"  Total required CPU:    {dedicated_cpu} cores")
    print(f"  Total required memory: {dedicated_memory} GiB")
    print("  Each workload would typically require its own physical server.")

    host = PhysicalServer("consolidated-host", 16, 64, 1500, 10)
    hypervisor = Hypervisor(host)

    for workload in workloads:
        vm = hypervisor.create_vm(
            workload.name,
            "Linux",
            ResourceRequest(
                workload.cpu_cores,
                workload.memory_gib,
                200,
                1.0,
            ),
        )
        vm.start()

    print("\nVirtualized model:")
    hypervisor.utilization_report()

    print(
        "\nConsolidation works because multiple isolated workloads share one "
        "physical platform while retaining separate virtual machine boundaries. "
        "The benefit is not unlimited capacity: the host remains a finite "
        "resource pool and must be sized for peak demand and failure scenarios."
    )


# ---------------------------------------------------------------------------
# Failure and validation scenarios
# ---------------------------------------------------------------------------

def demonstrate_validation_and_failures() -> None:
    heading("Capacity Validation and Failure Conditions")

    host = PhysicalServer("small-host", 8, 16, 500, 2.0)
    hypervisor = Hypervisor(host)

    cases = [
        (
            "Excessive memory",
            ResourceRequest(2, 32, 50, 0.5),
        ),
        (
            "Excessive storage",
            ResourceRequest(2, 4, 700, 0.5),
        ),
        (
            "Excessive network",
            ResourceRequest(2, 4, 50, 5.0),
        ),
    ]

    for description, request in cases:
        try:
            hypervisor.create_vm(
                description.lower().replace(" ", "-"),
                "Linux",
                request,
            )
        except ValueError as error:
            print(f"{description}: rejected")
            print(f"  Reason: {error}")

    try:
        hypervisor.create_vm(
            "invalid-vm",
            "Linux",
            ResourceRequest(0, 4, 20, 0.5),
        )
    except ValueError as error:
        print(f"Invalid CPU allocation: rejected")
        print(f"  Reason: {error}")


# ---------------------------------------------------------------------------
# Isolation model
# ---------------------------------------------------------------------------

def demonstrate_isolation() -> None:
    heading("Virtual Machine Isolation")

    host = PhysicalServer("isolated-host", 12, 48, 800, 10)
    hypervisor = Hypervisor(host)

    vm_a = hypervisor.create_vm(
        "tenant-a",
        "Linux",
        ResourceRequest(4, 12, 150, 2),
    )
    vm_b = hypervisor.create_vm(
        "tenant-b",
        "Linux",
        ResourceRequest(4, 12, 150, 2),
    )

    vm_a.start()
    vm_b.start()

    print("Each VM has its own virtual machine identity and allocated resources.")
    print(f"{vm_a.name}: {vm_a.request}")
    print(f"{vm_b.name}: {vm_b.request}")

    print(
        "\nA workload inside tenant-a does not directly address tenant-b's "
        "virtual memory or virtual disk. The hypervisor controls mappings "
        "between guest-visible resources and physical resources."
    )

    print(
        "\nIsolation is a boundary, not an absolute guarantee against every "
        "failure. Hypervisor vulnerabilities, incorrect device configuration, "
        "shared-resource side channels, and host compromise can weaken the "
        "security model."
    )


# ---------------------------------------------------------------------------
# Advanced scheduling demonstration
# ---------------------------------------------------------------------------

@dataclass
class CpuScheduler:
    """
    Simplified proportional scheduler.

    Real hypervisors use significantly more sophisticated scheduling,
    virtualization extensions, interrupt handling, NUMA awareness, CPU
    affinity, and fairness mechanisms. This model illustrates the basic idea:
    virtual CPU demand competes for finite physical execution capacity.
    """

    physical_cores: int

    def allocate(self, demands: Dict[str, float]) -> Dict[str, float]:
        if self.physical_cores <= 0:
            raise ValueError("Physical core count must be positive.")

        total_demand = sum(max(0.0, demand) for demand in demands.values())

        if total_demand == 0:
            return {name: 0.0 for name in demands}

        if total_demand <= self.physical_cores:
            return {
                name: max(0.0, demand)
                for name, demand in demands.items()
            }

        scale = self.physical_cores / total_demand

        return {
            name: max(0.0, demand) * scale
            for name, demand in demands.items()
        }


def demonstrate_cpu_scheduling() -> None:
    heading("Advanced Topic: CPU Scheduling Under Contention")

    scheduler = CpuScheduler(physical_cores=8)

    demands = {
        "web-server": 2.0,
        "database": 5.0,
        "analytics": 4.0,
    }

    allocation = scheduler.allocate(demands)

    print("Requested CPU execution:")
    for vm_name, demand in demands.items():
        print(f"  {vm_name:<14}: {demand:.2f} cores")

    print("\nScheduled CPU execution:")
    for vm_name, cores in allocation.items():
        print(f"  {vm_name:<14}: {cores:.2f} cores")

    print(
        "\nThe scheduler shares finite physical execution capacity. This "
        "illustrates why CPU overcommit can be useful when workloads peak at "
        "different times, but excessive contention can increase latency."
    )


# ---------------------------------------------------------------------------
# Benefits analysis
# ---------------------------------------------------------------------------

def calculate_consolidation_ratio(
    physical_servers: int,
    virtual_machines: int,
) -> float:
    if physical_servers <= 0:
        raise ValueError("Physical server count must be positive.")
    if virtual_machines < 0:
        raise ValueError("Virtual machine count cannot be negative.")

    return virtual_machines / physical_servers


def demonstrate_benefits() -> None:
    heading("Benefits of Virtualization")

    benefits = {
        "Consolidation": (
            "Multiple workloads can share one physical host instead of "
            "requiring separate physical machines."
        ),
        "Resource utilization": (
            "CPU and memory can be assigned according to workload requirements "
            "rather than reserving an entire physical server for one application."
        ),
        "Isolation": (
            "Separate VMs provide independent guest operating-system "
            "environments and virtual resource boundaries."
        ),
        "Operational flexibility": (
            "VMs can be created, stopped, paused, resized, migrated, backed up, "
            "and restored through virtualization management systems."
        ),
        "Hardware abstraction": (
            "Guest software can use standardized virtual hardware interfaces "
            "without directly depending on every physical device."
        ),
    }

    for name, explanation in benefits.items():
        print(f"{name}: {explanation}")

    ratio = calculate_consolidation_ratio(
        physical_servers=3,
        virtual_machines=12,
    )

    print(f"\nIllustrative VM-to-host ratio: {ratio:.1f}:1")
    print(
        "The ratio is a planning metric rather than a universal target. "
        "Workload CPU, memory, storage I/O, network traffic, licensing, "
        "availability requirements, and failure-domain design determine "
        "appropriate consolidation."
    )


# ---------------------------------------------------------------------------
# Main executable demonstration
# ---------------------------------------------------------------------------

def main() -> None:
    print("INTRODUCTION TO VIRTUALIZATION")
    print(
        "A practical simulation of physical resources, virtual machines, "
        "resource abstraction, and virtualization benefits."
    )

    demonstrate_resource_abstraction()
    demonstrate_vm_lifecycle()
    compare_non_virtualized_and_virtualized()
    demonstrate_validation_and_failures()
    demonstrate_isolation()
    demonstrate_cpu_scheduling()
    demonstrate_benefits()

    heading("Operational Takeaways")
    print(
        "Virtualization introduces an abstraction layer between workloads and "
        "physical hardware. The hypervisor manages this shared resource pool, "
        "while each VM receives a controlled virtual hardware environment."
    )
    print(
        "The central engineering trade-off is utilization versus contention: "
        "consolidation can improve hardware efficiency, but resource guarantees "
        "must be respected and peak demand must be planned."
    )
    print(
        "Production virtualization also requires monitoring, backups, capacity "
        "planning, patch management, access control, network segmentation, "
        "hardware redundancy, and tested recovery procedures."
    )


if __name__ == "__main__":
    main()
