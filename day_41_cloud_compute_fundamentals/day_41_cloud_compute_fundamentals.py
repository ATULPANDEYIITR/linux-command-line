#!/usr/bin/env python3
"""Cloud compute fundamentals: instance sizing, resource allocation, and provisioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Iterable


class InstanceFamily(str, Enum):
    GENERAL_PURPOSE = "general-purpose"
    COMPUTE_OPTIMIZED = "compute-optimized"
    MEMORY_OPTIMIZED = "memory-optimized"
    BURSTABLE = "burstable"
    ACCELERATED = "accelerated"


class InstanceState(str, Enum):
    REQUESTED = "requested"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"
    FAILED = "failed"


class ProvisioningError(Exception):
    """Raised when a compute request cannot be fulfilled."""


@dataclass(frozen=True)
class InstanceType:
    name: str
    family: InstanceFamily
    vcpus: int
    memory_gib: float
    hourly_rate: float
    max_network_gbps: float
    architecture: str = "x86_64"
    local_storage_gib: int = 0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Instance type name cannot be empty.")
        if self.vcpus <= 0:
            raise ValueError("An instance must have at least one vCPU.")
        if self.memory_gib <= 0 or self.hourly_rate < 0:
            raise ValueError("Memory must be positive and rate non-negative.")
        if self.max_network_gbps <= 0:
            raise ValueError("Network capacity must be positive.")

    @property
    def memory_per_vcpu(self) -> float:
        return self.memory_gib / self.vcpus


@dataclass
class ComputeInstance:
    instance_id: str
    instance_type: InstanceType
    workload: str
    state: InstanceState = InstanceState.REQUESTED
    assigned_host: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    def transition(self, target: InstanceState) -> None:
        allowed = {
            InstanceState.REQUESTED: {
                InstanceState.PROVISIONING,
                InstanceState.FAILED,
            },
            InstanceState.PROVISIONING: {
                InstanceState.RUNNING,
                InstanceState.FAILED,
            },
            InstanceState.RUNNING: {
                InstanceState.STOPPED,
                InstanceState.TERMINATED,
            },
            InstanceState.STOPPED: {
                InstanceState.PROVISIONING,
                InstanceState.TERMINATED,
            },
            InstanceState.FAILED: {InstanceState.TERMINATED},
            InstanceState.TERMINATED: set(),
        }
        if target not in allowed[self.state]:
            raise ProvisioningError(
                f"Invalid transition: {self.state.value} -> {target.value}"
            )
        self.state = target


@dataclass
class PhysicalHost:
    host_id: str
    total_vcpus: int
    total_memory_gib: float
    available_architectures: set[str] = field(
        default_factory=lambda: {"x86_64"}
    )
    reserved_vcpus: int = 0
    reserved_memory_gib: float = 0.0
    instance_ids: set[str] = field(default_factory=set)

    @property
    def free_vcpus(self) -> int:
        return self.total_vcpus - self.reserved_vcpus

    @property
    def free_memory_gib(self) -> float:
        return self.total_memory_gib - self.reserved_memory_gib

    def can_fit(self, instance_type: InstanceType) -> bool:
        return (
            instance_type.architecture in self.available_architectures
            and self.free_vcpus >= instance_type.vcpus
            and self.free_memory_gib >= instance_type.memory_gib
        )

    def reserve(self, instance: ComputeInstance) -> None:
        spec = instance.instance_type
        if not self.can_fit(spec):
            raise ProvisioningError(
                f"Host {self.host_id} lacks compatible free capacity."
            )
        self.reserved_vcpus += spec.vcpus
        self.reserved_memory_gib += spec.memory_gib
        self.instance_ids.add(instance.instance_id)

    def release(self, instance: ComputeInstance) -> None:
        if instance.instance_id not in self.instance_ids:
            return
        spec = instance.instance_type
        self.reserved_vcpus -= spec.vcpus
        self.reserved_memory_gib -= spec.memory_gib
        self.instance_ids.remove(instance.instance_id)


class ComputeCloud:
    def __init__(
        self,
        catalog: Iterable[InstanceType],
        hosts: Iterable[PhysicalHost],
    ) -> None:
        self.catalog = {spec.name: spec for spec in catalog}
        self.hosts = {host.host_id: host for host in hosts}
        self.instances: dict[str, ComputeInstance] = {}
        if not self.catalog:
            raise ValueError("The instance catalog cannot be empty.")
        if not self.hosts:
            raise ValueError("At least one physical host is required.")

    def provision(
        self,
        instance_type_name: str,
        workload: str,
        tags: dict[str, str] | None = None,
    ) -> ComputeInstance:
        if not workload.strip():
            raise ValueError("Workload name cannot be empty.")
        if instance_type_name not in self.catalog:
            raise ProvisioningError(
                f"Unknown instance type: {instance_type_name}"
            )

        instance_id = f"vm-{len(self.instances) + 1:04d}"
        instance = ComputeInstance(
            instance_id=instance_id,
            instance_type=self.catalog[instance_type_name],
            workload=workload,
            tags=dict(tags or {}),
        )
        self.instances[instance_id] = instance
        instance.transition(InstanceState.PROVISIONING)

        # First-fit placement is simple and deterministic. Real schedulers
        # may consider NUMA topology, affinity, reservations, and fragmentation.
        candidates = sorted(
            self.hosts.values(),
            key=lambda host: (
                host.free_memory_gib,
                host.free_vcpus,
                host.host_id,
            ),
            reverse=True,
        )

        for host in candidates:
            if host.can_fit(instance.instance_type):
                try:
                    host.reserve(instance)
                    instance.assigned_host = host.host_id
                    instance.transition(InstanceState.RUNNING)
                    return instance
                except ProvisioningError:
                    continue

        instance.transition(InstanceState.FAILED)
        raise ProvisioningError(
            f"No compatible host can fit {instance_type_name}; "
            "the instance is recorded as failed."
        )

    def stop(self, instance_id: str) -> None:
        instance = self._get_instance(instance_id)
        instance.transition(InstanceState.STOPPED)
        if instance.assigned_host is not None:
            self.hosts[instance.assigned_host].release(instance)
            instance.assigned_host = None

    def start(self, instance_id: str) -> None:
        instance = self._get_instance(instance_id)
        instance.transition(InstanceState.PROVISIONING)
        for host in sorted(self.hosts.values(), key=lambda h: h.host_id):
            if host.can_fit(instance.instance_type):
                host.reserve(instance)
                instance.assigned_host = host.host_id
                instance.transition(InstanceState.RUNNING)
                return
        instance.transition(InstanceState.STOPPED)
        raise ProvisioningError("Restart failed: insufficient free capacity.")

    def terminate(self, instance_id: str) -> None:
        instance = self._get_instance(instance_id)
        if instance.assigned_host is not None:
            self.hosts[instance.assigned_host].release(instance)
            instance.assigned_host = None
        instance.transition(InstanceState.TERMINATED)

    def _get_instance(self, instance_id: str) -> ComputeInstance:
        try:
            return self.instances[instance_id]
        except KeyError as exc:
            raise ProvisioningError(
                f"Unknown instance: {instance_id}"
            ) from exc

    def inventory(self) -> None:
        print("\nCloud instance inventory")
        print("-" * 105)
        print(
            f"{'ID':<10} {'TYPE':<17} {'FAMILY':<19} "
            f"{'VCPU':>5} {'RAM GiB':>9} {'STATE':<13} {'HOST':<12}"
        )
        for instance in self.instances.values():
            spec = instance.instance_type
            print(
                f"{instance.instance_id:<10} {spec.name:<17} "
                f"{spec.family.value:<19} {spec.vcpus:>5} "
                f"{spec.memory_gib:>9.1f} {instance.state.value:<13} "
                f"{(instance.assigned_host or '-'): <12}"
            )

    def host_capacity(self) -> None:
        print("\nPhysical host capacity")
        for host in self.hosts.values():
            print(
                f"{host.host_id}: "
                f"{host.free_vcpus}/{host.total_vcpus} vCPUs free, "
                f"{host.free_memory_gib:.1f}/"
                f"{host.total_memory_gib:.1f} GiB RAM free"
            )


def choose_instance_type(
    catalog: Iterable[InstanceType],
    required_vcpus: int,
    required_memory_gib: float,
    preferred_family: InstanceFamily | None = None,
    max_hourly_cost: float | None = None,
) -> InstanceType:
    """Choose the cheapest compatible catalog entry."""
    if required_vcpus <= 0 or required_memory_gib <= 0:
        raise ValueError("Resource requirements must be positive.")

    candidates = [
        spec
        for spec in catalog
        if spec.vcpus >= required_vcpus
        and spec.memory_gib >= required_memory_gib
        and (
            preferred_family is None or spec.family == preferred_family
        )
        and (
            max_hourly_cost is None or spec.hourly_rate <= max_hourly_cost
        )
    ]
    if not candidates:
        raise ProvisioningError("No instance type satisfies the requirements.")
    return min(candidates, key=lambda spec: (spec.hourly_rate, spec.vcpus))


def estimate_cost(
    hourly_rate: float,
    running_hours: float,
    instance_count: int = 1,
    monthly_hours: float = 730.0,
) -> dict[str, float]:
    """Estimate compute-only cost, excluding storage, network, and taxes."""
    if hourly_rate < 0 or running_hours < 0 or instance_count <= 0:
        raise ValueError("Invalid pricing inputs.")
    return {
        "period_cost": hourly_rate * running_hours * instance_count,
        "monthly_cost": hourly_rate * monthly_hours * instance_count,
        "annual_cost": hourly_rate * monthly_hours * 12 * instance_count,
    }


def calculate_capacity(
    total_vcpus: int,
    target_utilization: float,
    average_workload_vcpus: float,
) -> int:
    """Estimate concurrent workload capacity at a utilization target."""
    if total_vcpus <= 0 or average_workload_vcpus <= 0:
        raise ValueError("CPU capacity and workload size must be positive.")
    if not 0 < target_utilization <= 1:
        raise ValueError("Utilization must be greater than zero and at most one.")
    usable_vcpus = total_vcpus * target_utilization
    return int(usable_vcpus // average_workload_vcpus)


def print_catalog(catalog: Iterable[InstanceType]) -> None:
    print("Instance type catalog")
    print("-" * 86)
    for spec in catalog:
        print(
            f"{spec.name:<16} {spec.family.value:<20} "
            f"{spec.vcpus:>3} vCPU  {spec.memory_gib:>5.1f} GiB  "
            f"${spec.hourly_rate:.3f}/hour  "
            f"{spec.max_network_gbps:.1f} Gbps network"
        )


def main() -> None:
    catalog = [
        InstanceType("gp-small", InstanceFamily.GENERAL_PURPOSE, 2, 8, 0.08, 5),
        InstanceType("gp-medium", InstanceFamily.GENERAL_PURPOSE, 4, 16, 0.16, 10),
        InstanceType("cpu-large", InstanceFamily.COMPUTE_OPTIMIZED, 8, 16, 0.24, 15),
        InstanceType("mem-large", InstanceFamily.MEMORY_OPTIMIZED, 4, 32, 0.22, 10),
        InstanceType("burst-small", InstanceFamily.BURSTABLE, 2, 4, 0.035, 2),
        InstanceType("gpu-large", InstanceFamily.ACCELERATED, 8, 32, 1.20, 25),
    ]

    hosts = [
        PhysicalHost("host-a", 16, 64, {"x86_64", "arm64"}),
        PhysicalHost("host-b", 8, 32, {"x86_64"}),
    ]

    print_catalog(catalog)

    print("\nInstance selection for a database workload")
    selected = choose_instance_type(
        catalog,
        required_vcpus=4,
        required_memory_gib=24,
        preferred_family=InstanceFamily.MEMORY_OPTIMIZED,
        max_hourly_cost=0.30,
    )
    print(f"Selected: {selected.name}, ${selected.hourly_rate:.2f}/hour")

    cloud = ComputeCloud(catalog, hosts)
    database = cloud.provision(
        "mem-large", "orders-database", {"environment": "production"}
    )
    api = cloud.provision(
        "gp-medium", "orders-api", {"environment": "production"}
    )
    analytics = cloud.provision(
        "cpu-large", "batch-analytics", {"environment": "staging"}
    )

    cloud.inventory()
    cloud.host_capacity()

    print("\nCost estimates for three gp-medium instances")
    costs = estimate_cost(0.16, running_hours=8, instance_count=3)
    for period, amount in costs.items():
        print(f"{period}: ${amount:.2f}")

    print("\nCPU capacity estimate")
    print(
        "Concurrent 1.5-vCPU workloads on 16 vCPUs at 70% utilization:",
        calculate_capacity(16, 0.70, 1.5),
    )

    print("\nLifecycle and recovery")
    cloud.stop(api.instance_id)
    print(f"{api.instance_id} stopped and host capacity released.")
    cloud.start(api.instance_id)
    print(f"{api.instance_id} restarted on {api.assigned_host}.")
    cloud.terminate(analytics.instance_id)
    print(f"{analytics.instance_id} terminated.")

    # A running VM does not imply that its application is healthy. Production
    # provisioning must separately check boot, networking, and service health.
    assert database.state == InstanceState.RUNNING
    assert api.state == InstanceState.RUNNING
    assert analytics.state == InstanceState.TERMINATED

    print("\nValidation and failure handling")
    try:
        cloud.provision("nonexistent-size", "invalid-workload")
    except ProvisioningError as exc:
        print(f"Expected provisioning failure: {exc}")

    try:
        database.transition(InstanceState.REQUESTED)
    except ProvisioningError as exc:
        print(f"Expected lifecycle rejection: {exc}")

    print("\nAll cloud compute demonstrations completed successfully.")


if __name__ == "__main__":
    main()
