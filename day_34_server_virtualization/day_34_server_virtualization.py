#!/usr/bin/env python3
"""
Server Virtualization: Physical Resource Allocation and Virtual Machine Simulation

This self-contained program models the core mechanics of server virtualization:
physical CPU, memory, storage, and network resources are represented by a host,
then divided among multiple virtual machines (VMs).

The implementation progresses from resource accounting to VM lifecycle management,
resource overcommitment, allocation policies, contention, snapshots, migration,
and capacity analysis.

It is a simulation and does not create real virtual machines or interact with a
hypervisor such as KVM, Hyper-V, VMware ESXi, or Xen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from random import Random
from typing import Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Basic resource model
# ---------------------------------------------------------------------------

class VMState(Enum):
    """Lifecycle states used by the virtualization simulator."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class ResourceVector:
    """
    Represents a quantity of physical resources.

    CPU is expressed as logical vCPUs.
    Memory and storage are expressed in GiB.
    Network is expressed in Mbps.
    """
    cpu: int
    memory_gib: float
    storage_gib: float
    network_mbps: float

    def validate_non_negative(self) -> None:
        """Reject physically impossible negative resource quantities."""
        if self.cpu < 0:
            raise ValueError("CPU capacity cannot be negative.")
        if self.memory_gib < 0:
            raise ValueError("Memory capacity cannot be negative.")
        if self.storage_gib < 0:
            raise ValueError("Storage capacity cannot be negative.")
        if self.network_mbps < 0:
            raise ValueError("Network capacity cannot be negative.")

    def add(self, other: ResourceVector) -> ResourceVector:
        """Return the resource-wise sum of two vectors."""
        return ResourceVector(
            self.cpu + other.cpu,
            self.memory_gib + other.memory_gib,
            self.storage_gib + other.storage_gib,
            self.network_mbps + other.network_mbps,
        )

    def subtract(self, other: ResourceVector) -> ResourceVector:
        """Return the resource-wise difference between two vectors."""
        return ResourceVector(
            self.cpu - other.cpu,
            self.memory_gib - other.memory_gib,
            self.storage_gib - other.storage_gib,
            self.network_mbps - other.network_mbps,
        )

    def fits_within(self, capacity: ResourceVector) -> bool:
        """Check whether this allocation fits inside another resource vector."""
        return (
            self.cpu <= capacity.cpu
            and self.memory_gib <= capacity.memory_gib
            and self.storage_gib <= capacity.storage_gib
            and self.network_mbps <= capacity.network_mbps
        )

    def utilization_against(self, capacity: ResourceVector) -> Dict[str, float]:
        """
        Calculate utilization ratios.

        A ratio of 1.0 means the physical resource is fully allocated.
        """
        return {
            "cpu": self.cpu / capacity.cpu if capacity.cpu else 0.0,
            "memory": (
                self.memory_gib / capacity.memory_gib
                if capacity.memory_gib
                else 0.0
            ),
            "storage": (
                self.storage_gib / capacity.storage_gib
                if capacity.storage_gib
                else 0.0
            ),
            "network": (
                self.network_mbps / capacity.network_mbps
                if capacity.network_mbps
                else 0.0
            ),
        }


# ---------------------------------------------------------------------------
# Virtual machine representation
# ---------------------------------------------------------------------------

@dataclass
class VirtualMachine:
    """
    Represents a VM from the hypervisor's resource-accounting perspective.

    A VM has configured resources and can also have a runtime demand that differs
    from its configured allocation. This distinction is important for
    virtualization because allocated capacity and instantaneous workload demand
    are not necessarily identical.
    """
    name: str
    resources: ResourceVector
    state: VMState = VMState.STOPPED
    cpu_demand: float = 0.0
    memory_demand_gib: float = 0.0
    network_demand_mbps: float = 0.0
    storage_used_gib: float = 0.0
    priority: int = 1
    snapshots: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.resources.validate_non_negative()

        if not self.name.strip():
            raise ValueError("VM name cannot be empty.")

        if not 1 <= self.priority <= 10:
            raise ValueError("VM priority must be between 1 and 10.")

        self.cpu_demand = max(0.0, min(self.cpu_demand, float(self.resources.cpu)))
        self.memory_demand_gib = max(
            0.0, min(self.memory_demand_gib, self.resources.memory_gib)
        )
        self.network_demand_mbps = max(
            0.0, min(self.network_demand_mbps, self.resources.network_mbps)
        )
        self.storage_used_gib = max(
            0.0, min(self.storage_used_gib, self.resources.storage_gib)
        )

    def start(self) -> None:
        """Start a stopped VM."""
        if self.state == VMState.RUNNING:
            raise RuntimeError(f"{self.name} is already running.")
        self.state = VMState.RUNNING

    def stop(self) -> None:
        """Stop a running or paused VM."""
        self.state = VMState.STOPPED

    def pause(self) -> None:
        """Pause an active VM without releasing its configured resources."""
        if self.state != VMState.RUNNING:
            raise RuntimeError(f"{self.name} must be running before it can be paused.")
        self.state = VMState.PAUSED

    def resume(self) -> None:
        """Resume a paused VM."""
        if self.state != VMState.PAUSED:
            raise RuntimeError(f"{self.name} is not paused.")
        self.state = VMState.RUNNING

    def effective_cpu_demand(self) -> float:
        """Return current CPU demand in vCPU units."""
        return self.cpu_demand if self.state == VMState.RUNNING else 0.0

    def effective_memory_demand(self) -> float:
        """Return current memory demand in GiB."""
        return self.memory_demand_gib if self.state == VMState.RUNNING else 0.0

    def effective_network_demand(self) -> float:
        """Return current network demand in Mbps."""
        return self.network_demand_mbps if self.state == VMState.RUNNING else 0.0

    def create_snapshot(self, snapshot_name: str) -> None:
        """
        Record a snapshot.

        A real hypervisor snapshot would preserve VM disk state and metadata.
        This simulator records snapshot names to keep the model self-contained.
        """
        if not snapshot_name.strip():
            raise ValueError("Snapshot name cannot be empty.")
        if snapshot_name in self.snapshots:
            raise ValueError("Snapshot already exists.")
        self.snapshots.append(snapshot_name)


# ---------------------------------------------------------------------------
# Physical host and hypervisor-like resource manager
# ---------------------------------------------------------------------------

class PhysicalHost:
    """
    Models a physical server containing resources shared by VMs.

    The host maintains separate concepts for:
    - physical capacity
    - configured VM allocation
    - actual workload demand

    The configured allocation can exceed physical capacity in an overcommit
    scenario, while actual demand may still remain below physical capacity.
    """

    def __init__(self, name: str, capacity: ResourceVector):
        capacity.validate_non_negative()

        if capacity.cpu == 0:
            raise ValueError("A virtualization host needs at least one CPU.")

        if capacity.memory_gib == 0:
            raise ValueError("A virtualization host needs memory.")

        self.name = name
        self.capacity = capacity
        self.vms: Dict[str, VirtualMachine] = {}

    def add_vm(self, vm: VirtualMachine, allow_overcommit: bool = False) -> None:
        """Register a VM if its configured allocation is permitted."""
        if vm.name in self.vms:
            raise ValueError(f"VM '{vm.name}' already exists.")

        allocated = self.configured_allocation().add(vm.resources)

        if not allow_overcommit and not allocated.fits_within(self.capacity):
            raise RuntimeError(
                f"Adding {vm.name} would exceed physical capacity."
            )

        self.vms[vm.name] = vm

    def remove_vm(self, vm_name: str) -> VirtualMachine:
        """Remove a VM only after it has been stopped."""
        vm = self.get_vm(vm_name)

        if vm.state != VMState.STOPPED:
            raise RuntimeError("A VM must be stopped before removal.")

        return self.vms.pop(vm_name)

    def get_vm(self, vm_name: str) -> VirtualMachine:
        """Retrieve a VM by name."""
        try:
            return self.vms[vm_name]
        except KeyError as exc:
            raise KeyError(f"VM '{vm_name}' does not exist.") from exc

    def configured_allocation(self) -> ResourceVector:
        """
        Sum configured VM resources.

        This is equivalent to the capacity promised or reserved by the VM
        definitions, not necessarily the current physical workload.
        """
        total = ResourceVector(0, 0.0, 0.0, 0.0)

        for vm in self.vms.values():
            total = total.add(vm.resources)

        return total

    def running_demand(self) -> ResourceVector:
        """Sum actual current demand of running VMs."""
        return ResourceVector(
            cpu=ceil(
                sum(vm.effective_cpu_demand() for vm in self.vms.values())
            ),
            memory_gib=sum(
                vm.effective_memory_demand() for vm in self.vms.values()
            ),
            storage_gib=sum(
                vm.storage_used_gib
                for vm in self.vms.values()
                if vm.state == VMState.RUNNING
            ),
            network_mbps=sum(
                vm.effective_network_demand() for vm in self.vms.values()
            ),
        )

    def allocation_utilization(self) -> Dict[str, float]:
        """Return physical-resource utilization based on configured allocations."""
        return self.configured_allocation().utilization_against(self.capacity)

    def demand_utilization(self) -> Dict[str, float]:
        """Return physical-resource utilization based on current workload demand."""
        return self.running_demand().utilization_against(self.capacity)

    def is_overcommitted(self) -> bool:
        """Detect whether configured allocations exceed physical capacity."""
        return not self.configured_allocation().fits_within(self.capacity)

    def is_currently_overloaded(self) -> bool:
        """
        Detect actual workload pressure.

        Storage is excluded because disk capacity is persistent allocation rather
        than an instantaneous compute bottleneck in this simplified model.
        """
        demand = self.running_demand()
        return (
            demand.cpu > self.capacity.cpu
            or demand.memory_gib > self.capacity.memory_gib
            or demand.network_mbps > self.capacity.network_mbps
        )

    def report(self) -> str:
        """Produce a human-readable resource report."""
        allocation = self.configured_allocation()
        demand = self.running_demand()
        allocation_util = self.allocation_utilization()
        demand_util = self.demand_utilization()

        lines = [
            f"Host: {self.name}",
            (
                f"Physical capacity: "
                f"{self.capacity.cpu} vCPU, "
                f"{self.capacity.memory_gib:.1f} GiB RAM, "
                f"{self.capacity.storage_gib:.1f} GiB storage, "
                f"{self.capacity.network_mbps:.1f} Mbps network"
            ),
            (
                f"Configured VM allocation: "
                f"{allocation.cpu} vCPU, "
                f"{allocation.memory_gib:.1f} GiB RAM, "
                f"{allocation.storage_gib:.1f} GiB storage, "
                f"{allocation.network_mbps:.1f} Mbps network"
            ),
            (
                f"Current running demand: "
                f"{demand.cpu} vCPU, "
                f"{demand.memory_gib:.1f} GiB RAM, "
                f"{demand.network_mbps:.1f} Mbps network"
            ),
            (
                "Allocation utilization: "
                f"CPU {allocation_util['cpu']:.0%}, "
                f"RAM {allocation_util['memory']:.0%}, "
                f"storage {allocation_util['storage']:.0%}, "
                f"network {allocation_util['network']:.0%}"
            ),
            (
                "Demand utilization: "
                f"CPU {demand_util['cpu']:.0%}, "
                f"RAM {demand_util['memory']:.0%}, "
                f"network {demand_util['network']:.0%}"
            ),
            f"Configured overcommit: {'yes' if self.is_overcommitted() else 'no'}",
            f"Current workload overload: {'yes' if self.is_currently_overloaded() else 'no'}",
        ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Allocation policies
# ---------------------------------------------------------------------------

class AllocationPolicy:
    """
    A policy determines whether a new VM can be placed on a host.

    Different policies matter because virtualization is not only about dividing
    resources; it is also about deciding how aggressively those resources can be
    promised.
    """

    def can_place(
        self,
        host: PhysicalHost,
        vm: VirtualMachine,
    ) -> Tuple[bool, str]:
        raise NotImplementedError


class ConservativePolicy(AllocationPolicy):
    """
    Reject an allocation if configured resources exceed physical capacity.

    This resembles a capacity-reservation approach where the administrator
    prioritizes predictable resource guarantees over density.
    """

    def can_place(
        self,
        host: PhysicalHost,
        vm: VirtualMachine,
    ) -> Tuple[bool, str]:
        projected = host.configured_allocation().add(vm.resources)

        if projected.fits_within(host.capacity):
            return True, "VM fits within physical capacity."

        return False, "VM would exceed physical host capacity."


class ControlledOvercommitPolicy(AllocationPolicy):
    """
    Allow moderate CPU and memory overcommit while preventing unsafe storage
    and network allocation.

    CPU and memory overcommit can be useful because not every VM reaches its
    configured maximum simultaneously. Storage and network can be governed more
    conservatively because their capacity constraints differ operationally.
    """

    def __init__(
        self,
        max_cpu_ratio: float = 2.0,
        max_memory_ratio: float = 1.5,
    ):
        if max_cpu_ratio < 1.0 or max_memory_ratio < 1.0:
            raise ValueError("Overcommit ratios must be at least 1.0.")

        self.max_cpu_ratio = max_cpu_ratio
        self.max_memory_ratio = max_memory_ratio

    def can_place(
        self,
        host: PhysicalHost,
        vm: VirtualMachine,
    ) -> Tuple[bool, str]:
        projected = host.configured_allocation().add(vm.resources)

        if projected.storage_gib > host.capacity.storage_gib:
            return False, "Storage allocation would exceed physical capacity."

        if projected.network_mbps > host.capacity.network_mbps:
            return False, "Network allocation would exceed physical capacity."

        cpu_ratio = projected.cpu / host.capacity.cpu
        memory_ratio = projected.memory_gib / host.capacity.memory_gib

        if cpu_ratio > self.max_cpu_ratio:
            return False, "CPU overcommit ratio would exceed policy."

        if memory_ratio > self.max_memory_ratio:
            return False, "Memory overcommit ratio would exceed policy."

        return True, "VM satisfies controlled-overcommit policy."


class ClusterScheduler:
    """
    Places VMs on one of several physical hosts.

    A simple best-fit strategy is used: choose the host with the smallest
    remaining normalized capacity after placement. This reduces fragmentation
    when multiple resources must be considered together.
    """

    def __init__(self, hosts: Iterable[PhysicalHost], policy: AllocationPolicy):
        self.hosts = list(hosts)
        self.policy = policy

    @staticmethod
    def _score_after_placement(
        host: PhysicalHost,
        vm: VirtualMachine,
    ) -> float:
        """
        Calculate remaining normalized capacity.

        The score is the average remaining capacity across CPU, memory, storage,
        and network. A lower score indicates a tighter fit.
        """
        projected = host.configured_allocation().add(vm.resources)
        remaining = host.capacity.subtract(projected)

        ratios = [
            remaining.cpu / host.capacity.cpu,
            remaining.memory_gib / host.capacity.memory_gib,
            remaining.storage_gib / host.capacity.storage_gib,
            remaining.network_mbps / host.capacity.network_mbps,
        ]

        return sum(ratios) / len(ratios)

    def place(self, vm: VirtualMachine) -> PhysicalHost:
        """Select the best eligible host and register the VM there."""
        candidates: List[Tuple[float, PhysicalHost]] = []

        for host in self.hosts:
            allowed, _ = self.policy.can_place(host, vm)

            if allowed:
                score = self._score_after_placement(host, vm)
                candidates.append((score, host))

        if not candidates:
            raise RuntimeError(f"No host can place VM '{vm.name}'.")

        _, selected = min(candidates, key=lambda item: item[0])
        selected.add_vm(
            vm,
            allow_overcommit=isinstance(
                self.policy,
                ControlledOvercommitPolicy,
            ),
        )
        return selected


# ---------------------------------------------------------------------------
# Resource contention and fair-share simulation
# ---------------------------------------------------------------------------

def distribute_cpu_fair_share(
    host: PhysicalHost,
) -> Dict[str, float]:
    """
    Allocate CPU proportionally when active VM demand exceeds physical CPU.

    Priority acts as a weight. This demonstrates a simplified scheduler model.
    Real hypervisors use substantially more sophisticated CPU scheduling,
    virtualization extensions, run queues, vCPU topology, NUMA awareness,
    reservations, shares, limits, and workload-specific policies.
    """
    running = [
        vm for vm in host.vms.values()
        if vm.state == VMState.RUNNING and vm.effective_cpu_demand() > 0
    ]

    total_weighted_demand = sum(
        vm.effective_cpu_demand() * vm.priority
        for vm in running
    )

    if total_weighted_demand <= host.capacity.cpu:
        return {
            vm.name: vm.effective_cpu_demand()
            for vm in running
        }

    allocations: Dict[str, float] = {}

    for vm in running:
        weighted = vm.effective_cpu_demand() * vm.priority
        allocations[vm.name] = (
            host.capacity.cpu * weighted / total_weighted_demand
        )

    return allocations


# ---------------------------------------------------------------------------
# Migration feasibility
# ---------------------------------------------------------------------------

def can_live_migrate(
    source: PhysicalHost,
    destination: PhysicalHost,
    vm_name: str,
) -> Tuple[bool, str]:
    """
    Determine whether a simplified live migration is possible.

    The destination must have enough configured capacity for the VM.
    The VM remains running in this simulation because live migration is modeled
    as a capacity decision rather than a real memory-copy operation.
    """
    vm = source.get_vm(vm_name)

    if vm.state != VMState.RUNNING:
        return False, "Only a running VM is considered for live migration."

    if vm.resources.storage_gib > destination.capacity.storage_gib:
        return False, "Destination lacks sufficient storage capacity."

    projected = destination.configured_allocation().add(vm.resources)

    if not projected.fits_within(destination.capacity):
        return False, "Destination lacks sufficient configured capacity."

    return True, "Destination can accommodate the VM."


def migrate_vm(
    source: PhysicalHost,
    destination: PhysicalHost,
    vm_name: str,
) -> None:
    """
    Move a VM between hosts after checking destination capacity.

    This is an accounting simulation, not a real live migration protocol.
    """
    allowed, reason = can_live_migrate(source, destination, vm_name)

    if not allowed:
        raise RuntimeError(reason)

    vm = source.get_vm(vm_name)
    source.vms.pop(vm_name)
    destination.add_vm(vm)


# ---------------------------------------------------------------------------
# Workload simulation
# ---------------------------------------------------------------------------

def simulate_workload(
    host: PhysicalHost,
    cycles: int = 8,
    seed: int = 42,
) -> List[Dict[str, float]]:
    """
    Generate deterministic workload demand and record resource pressure.

    A fixed seed makes the example reproducible while still demonstrating that
    VM demand changes over time rather than remaining at configured maximums.
    """
    rng = Random(seed)
    history: List[Dict[str, float]] = []

    running = [
        vm for vm in host.vms.values()
        if vm.state == VMState.RUNNING
    ]

    for cycle in range(1, cycles + 1):
        for vm in running:
            cpu_fraction = rng.uniform(0.25, 1.0)
            memory_fraction = rng.uniform(0.45, 1.0)
            network_fraction = rng.uniform(0.10, 1.0)

            vm.cpu_demand = vm.resources.cpu * cpu_fraction
            vm.memory_demand_gib = vm.resources.memory_gib * memory_fraction
            vm.network_demand_mbps = (
                vm.resources.network_mbps * network_fraction
            )

        demand = host.running_demand()
        history.append(
            {
                "cycle": float(cycle),
                "cpu": float(demand.cpu),
                "memory_gib": demand.memory_gib,
                "network_mbps": demand.network_mbps,
                "cpu_utilization": demand.cpu / host.capacity.cpu,
                "memory_utilization": (
                    demand.memory_gib / host.capacity.memory_gib
                ),
                "network_utilization": (
                    demand.network_mbps / host.capacity.network_mbps
                ),
            }
        )

    return history


# ---------------------------------------------------------------------------
# Demonstrations
# ---------------------------------------------------------------------------

def demonstrate_basic_virtualization() -> None:
    print("\n=== Basic Physical Resource Division ===")

    host = PhysicalHost(
        "compute-01",
        ResourceVector(
            cpu=16,
            memory_gib=64,
            storage_gib=1000,
            network_mbps=10000,
        ),
    )

    web_vm = VirtualMachine(
        "web-01",
        ResourceVector(4, 8, 100, 1000),
        cpu_demand=1.5,
        memory_demand_gib=5,
        network_demand_mbps=250,
    )

    database_vm = VirtualMachine(
        "database-01",
        ResourceVector(6, 24, 300, 2500),
        cpu_demand=4,
        memory_demand_gib=18,
        network_demand_mbps=1200,
    )

    host.add_vm(web_vm)
    host.add_vm(database_vm)

    web_vm.start()
    database_vm.start()

    print(host.report())


def demonstrate_overcommitment() -> PhysicalHost:
    print("\n=== Controlled Overcommitment ===")

    host = PhysicalHost(
        "dense-compute-01",
        ResourceVector(
            cpu=8,
            memory_gib=32,
            storage_gib=500,
            network_mbps=5000,
        ),
    )

    policy = ControlledOvercommitPolicy(
        max_cpu_ratio=2.0,
        max_memory_ratio=1.5,
    )

    scheduler = ClusterScheduler([host], policy)

    for vm in [
        VirtualMachine(
            "api-01",
            ResourceVector(4, 8, 50, 500),
            cpu_demand=1.0,
            memory_demand_gib=4,
            network_demand_mbps=100,
            priority=5,
        ),
        VirtualMachine(
            "api-02",
            ResourceVector(4, 8, 50, 500),
            cpu_demand=1.0,
            memory_demand_gib=4,
            network_demand_mbps=100,
            priority=3,
        ),
        VirtualMachine(
            "batch-01",
            ResourceVector(4, 8, 50, 500),
            cpu_demand=1.0,
            memory_demand_gib=4,
            network_demand_mbps=100,
            priority=1,
        ),
        VirtualMachine(
            "worker-01",
            ResourceVector(2, 8, 50, 500),
            cpu_demand=0.5,
            memory_demand_gib=3,
            network_demand_mbps=100,
            priority=2,
        ),
    ]:
        scheduler.place(vm)
        vm.start()

    print(host.report())

    allocations = distribute_cpu_fair_share(host)

    print("\nCPU scheduler allocation under current demand:")
    for name, cpu in allocations.items():
        print(f"  {name}: {cpu:.2f} vCPU")

    return host


def demonstrate_contention(host: PhysicalHost) -> None:
    print("\n=== Workload Contention Simulation ===")

    history = simulate_workload(host, cycles=6)

    for sample in history:
        print(
            f"cycle={int(sample['cycle'])} "
            f"cpu={sample['cpu']:.0f}/{host.capacity.cpu} "
            f"({sample['cpu_utilization']:.0%}) "
            f"memory={sample['memory_gib']:.1f}/"
            f"{host.capacity.memory_gib:.1f} GiB "
            f"({sample['memory_utilization']:.0%}) "
            f"network={sample['network_mbps']:.0f}/"
            f"{host.capacity.network_mbps:.0f} Mbps "
            f"({sample['network_utilization']:.0%})"
        )


def demonstrate_snapshots(host: PhysicalHost) -> None:
    print("\n=== VM Snapshot Metadata ===")

    vm = host.get_vm("api-01")
    vm.create_snapshot("before-configuration-change")
    vm.create_snapshot("after-configuration-change")

    print(f"{vm.name} snapshots: {', '.join(vm.snapshots)}")


def demonstrate_migration() -> None:
    print("\n=== VM Placement and Migration ===")

    source = PhysicalHost(
        "source-01",
        ResourceVector(16, 64, 1000, 10000),
    )
    destination = PhysicalHost(
        "destination-01",
        ResourceVector(24, 96, 1500, 10000),
    )

    vm = VirtualMachine(
        "analytics-01",
        ResourceVector(6, 20, 250, 1500),
        cpu_demand=4,
        memory_demand_gib=14,
        network_demand_mbps=700,
    )

    source.add_vm(vm)
    vm.start()

    allowed, reason = can_live_migrate(source, destination, vm.name)
    print(f"Migration check: {'allowed' if allowed else 'blocked'}")
    print(f"Reason: {reason}")

    if allowed:
        migrate_vm(source, destination, vm.name)
        print(f"VM is now hosted by {destination.name}.")
        print(destination.report())


def demonstrate_edge_cases() -> None:
    print("\n=== Validation and Failure Conditions ===")

    host = PhysicalHost(
        "validation-host",
        ResourceVector(8, 32, 500, 1000),
    )

    try:
        host.add_vm(
            VirtualMachine(
                "too-large",
                ResourceVector(16, 64, 100, 100),
            )
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Expected allocation failure: {exc}")

    try:
        VirtualMachine(
            "invalid",
            ResourceVector(-1, 4, 20, 100),
        )
    except ValueError as exc:
        print(f"Expected validation failure: {exc}")

    vm = VirtualMachine(
        "lifecycle-test",
        ResourceVector(2, 4, 20, 100),
    )
    host.add_vm(vm)

    try:
        vm.pause()
    except RuntimeError as exc:
        print(f"Expected lifecycle failure: {exc}")

    vm.start()
    vm.pause()
    vm.resume()
    vm.stop()

    print(f"{vm.name} lifecycle completed successfully.")


def compare_allocation_models() -> None:
    print("\n=== Conservative vs Overcommit Allocation ===")

    capacity = ResourceVector(8, 32, 500, 5000)

    conservative_host = PhysicalHost("conservative", capacity)
    conservative = ConservativePolicy()

    candidate = VirtualMachine(
        "candidate",
        ResourceVector(8, 16, 100, 1000),
    )

    allowed, reason = conservative.can_place(conservative_host, candidate)
    print(f"Conservative policy: {allowed} - {reason}")

    first = VirtualMachine(
        "existing",
        ResourceVector(6, 20, 100, 1000),
    )
    conservative_host.add_vm(first)

    allowed, reason = conservative.can_place(conservative_host, candidate)
    print(f"After existing VM: {allowed} - {reason}")

    overcommit_host = PhysicalHost("overcommit", capacity)
    overcommit = ControlledOvercommitPolicy(
        max_cpu_ratio=2.0,
        max_memory_ratio=1.5,
    )

    overcommit_host.add_vm(first)
    allowed, reason = overcommit.can_place(overcommit_host, candidate)

    print(f"Controlled overcommit: {allowed} - {reason}")


def main() -> None:
    print("SERVER VIRTUALIZATION RESOURCE SIMULATOR")
    print("----------------------------------------")
    print(
        "The program models how one physical server can provide isolated "
        "resource allocations to multiple virtual machines."
    )

    demonstrate_basic_virtualization()

    dense_host = demonstrate_overcommitment()
    demonstrate_contention(dense_host)
    demonstrate_snapshots(dense_host)
    demonstrate_migration()
    demonstrate_edge_cases()
    compare_allocation_models()

    print("\n=== Practical Interpretation ===")
    print(
        "A hypervisor does not simply divide a server into fixed pieces. "
        "It manages CPU scheduling, memory allocation, storage access, "
        "network bandwidth, isolation, and VM lifecycle operations."
    )
    print(
        "Configured capacity describes what VMs are provisioned to use, "
        "while runtime demand describes what workloads actually consume."
    )
    print(
        "Overcommitment can increase server density, but it creates a risk "
        "that simultaneous workload demand will exceed physical capacity."
    )


if __name__ == "__main__":
    main()
