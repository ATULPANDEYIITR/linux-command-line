#!/usr/bin/env python3
"""
Containers vs Virtual Machines

A self-contained technical demonstration comparing containers and virtual
machines in terms of isolation, performance, portability, and resource usage.

The program uses a measurement model rather than pretending that a Python
process can create real containers or virtual machines without platform tools.
It combines:
- conceptual system models,
- resource accounting,
- startup simulations,
- workload isolation models,
- portability scoring,
- scenario analysis,
- sensitivity analysis,
- and an executable comparison report.

The numerical values are deliberately configurable assumptions. Real-world
measurements depend on the hypervisor, container runtime, operating system,
kernel, CPU, storage, networking, workload, and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import statistics
import time
from typing import Dict, Iterable, List, Tuple


class WorkloadType(Enum):
    WEB_SERVICE = "web service"
    BATCH_PROCESSING = "batch processing"
    DATABASE = "database"
    LEGACY_APPLICATION = "legacy application"
    MICROSERVICE = "microservice"


@dataclass(frozen=True)
class Host:
    name: str
    total_cpu_cores: float
    total_memory_gib: float
    total_storage_gib: float
    host_kernel: str


@dataclass
class IsolationProfile:
    kernel_sharing: bool
    process_namespace: bool
    filesystem_boundary: bool
    virtual_hardware_boundary: bool
    privilege_boundary: str
    isolation_strength: float

    def description(self) -> str:
        shared = "shared host kernel" if self.kernel_sharing else "independent guest kernel"
        hardware = (
            "virtual hardware boundary"
            if self.virtual_hardware_boundary
            else "OS-level process boundary"
        )
        return f"{shared}; {hardware}; {self.privilege_boundary} boundary"


@dataclass
class DeploymentProfile:
    name: str
    isolation: IsolationProfile
    memory_overhead_mib: float
    cpu_overhead_percent: float
    startup_seconds: float
    storage_overhead_gib: float
    portable_across_host_os: bool
    requires_guest_kernel: bool
    density_factor: float
    strengths: Tuple[str, ...]
    limitations: Tuple[str, ...]


@dataclass
class Instance:
    identifier: str
    workload: WorkloadType
    requested_memory_gib: float
    requested_cpu_cores: float
    profile: DeploymentProfile
    running: bool = False
    start_time: float | None = None

    def estimated_memory_gib(self) -> float:
        return self.requested_memory_gib + self.profile.memory_overhead_mib / 1024

    def estimated_cpu_cores(self) -> float:
        return self.requested_cpu_cores * (
            1.0 + self.profile.cpu_overhead_percent / 100.0
        )

    def estimated_storage_gib(self) -> float:
        return self.profile.storage_overhead_gib


@dataclass
class ResourceReport:
    instance_count: int
    requested_memory_gib: float
    estimated_memory_gib: float
    estimated_cpu_cores: float
    estimated_storage_gib: float
    memory_utilization_percent: float
    cpu_utilization_percent: float
    storage_utilization_percent: float


@dataclass
class Scenario:
    name: str
    workload: WorkloadType
    instances: int
    memory_per_instance_gib: float
    cpu_per_instance: float
    host: Host


CONTAINER = DeploymentProfile(
    name="Container",
    isolation=IsolationProfile(
        kernel_sharing=True,
        process_namespace=True,
        filesystem_boundary=True,
        virtual_hardware_boundary=False,
        privilege_boundary="OS-level",
        isolation_strength=0.72,
    ),
    memory_overhead_mib=80,
    cpu_overhead_percent=2.0,
    startup_seconds=0.8,
    storage_overhead_gib=0.15,
    portable_across_host_os=False,
    requires_guest_kernel=False,
    density_factor=0.92,
    strengths=(
        "high workload density",
        "fast startup",
        "small image footprint",
        "efficient microservice deployment",
        "repeatable application packaging",
    ),
    limitations=(
        "shares the host kernel",
        "Linux containers require compatible kernel facilities",
        "kernel-level isolation is not equivalent to a VM boundary",
    ),
)

VIRTUAL_MACHINE = DeploymentProfile(
    name="Virtual Machine",
    isolation=IsolationProfile(
        kernel_sharing=False,
        process_namespace=False,
        filesystem_boundary=True,
        virtual_hardware_boundary=True,
        privilege_boundary="hardware-assisted virtualization",
        isolation_strength=0.96,
    ),
    memory_overhead_mib=900,
    cpu_overhead_percent=7.0,
    startup_seconds=25.0,
    storage_overhead_gib=8.0,
    portable_across_host_os=True,
    requires_guest_kernel=True,
    density_factor=0.45,
    strengths=(
        "strong guest OS isolation",
        "independent guest kernel",
        "heterogeneous guest operating systems",
        "useful legacy OS support",
        "stronger tenant boundary",
    ),
    limitations=(
        "larger memory footprint",
        "slower startup",
        "larger disk footprint",
        "lower workload density",
    ),
)


def heading(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def format_gib(value: float) -> str:
    return f"{value:.2f} GiB"


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def compare_architecture() -> None:
    heading("Architecture and Isolation")

    print("Container:")
    print("  - The application runs in an isolated user-space environment.")
    print("  - Processes use namespaces, cgroups, filesystem isolation, and")
    print("    other operating-system primitives.")
    print("  - The container normally shares the host kernel.")
    print(f"  - {CONTAINER.isolation.description()}")

    print()
    print("Virtual machine:")
    print("  - The application runs inside a complete guest operating system.")
    print("  - A hypervisor provides virtual CPU, memory, storage, and devices.")
    print("  - The guest owns its own kernel.")
    print(f"  - {VIRTUAL_MACHINE.isolation.description()}")

    print()
    print(
        "Isolation interpretation: the VM model creates a stronger boundary "
        "when the security requirement is separation at the guest-OS level."
    )
    print(
        "Container isolation is still substantial, but the shared kernel is "
        "an architectural dependency and therefore part of the threat model."
    )


def calculate_resource_report(
    host: Host,
    instances: Iterable[Instance],
) -> ResourceReport:
    instances = list(instances)

    requested_memory = sum(i.requested_memory_gib for i in instances)
    estimated_memory = sum(i.estimated_memory_gib() for i in instances)
    estimated_cpu = sum(i.estimated_cpu_cores() for i in instances)
    estimated_storage = sum(i.estimated_storage_gib() for i in instances)

    return ResourceReport(
        instance_count=len(instances),
        requested_memory_gib=requested_memory,
        estimated_memory_gib=estimated_memory,
        estimated_cpu_cores=estimated_cpu,
        estimated_storage_gib=estimated_storage,
        memory_utilization_percent=(
            estimated_memory / host.total_memory_gib * 100
        ),
        cpu_utilization_percent=(
            estimated_cpu / host.total_cpu_cores * 100
        ),
        storage_utilization_percent=(
            estimated_storage / host.total_storage_gib * 100
        ),
    )


def print_resource_report(label: str, report: ResourceReport) -> None:
    print(f"\n{label}")
    print(f"  Instances:              {report.instance_count}")
    print(f"  Requested memory:       {format_gib(report.requested_memory_gib)}")
    print(f"  Estimated memory:       {format_gib(report.estimated_memory_gib)}")
    print(f"  Estimated CPU:          {report.estimated_cpu_cores:.2f} cores")
    print(f"  Estimated storage:      {format_gib(report.estimated_storage_gib)}")
    print(
        f"  Memory utilization:     "
        f"{format_percent(report.memory_utilization_percent)}"
    )
    print(
        f"  CPU utilization:        "
        f"{format_percent(report.cpu_utilization_percent)}"
    )
    print(
        f"  Storage utilization:    "
        f"{format_percent(report.storage_utilization_percent)}"
    )


def build_instances(
    profile: DeploymentProfile,
    count: int,
    workload: WorkloadType,
    memory_gib: float,
    cpu_cores: float,
) -> List[Instance]:
    if count <= 0:
        raise ValueError("Instance count must be greater than zero.")
    if memory_gib <= 0:
        raise ValueError("Memory allocation must be positive.")
    if cpu_cores <= 0:
        raise ValueError("CPU allocation must be positive.")

    return [
        Instance(
            identifier=f"{profile.name.lower().replace(' ', '-')}-{index}",
            workload=workload,
            requested_memory_gib=memory_gib,
            requested_cpu_cores=cpu_cores,
            profile=profile,
        )
        for index in range(1, count + 1)
    ]


def simulate_startup(profile: DeploymentProfile, count: int) -> List[float]:
    if count <= 0:
        raise ValueError("Count must be positive.")

    # Startup times are modeled rather than waiting for real infrastructure.
    # A small deterministic variance represents image/boot initialization.
    samples = []
    for index in range(count):
        variance = 1.0 + ((index % 5) - 2) * 0.035
        samples.append(max(0.01, profile.startup_seconds * variance))
    return samples


def benchmark_startup() -> None:
    heading("Startup Behavior")

    container_samples = simulate_startup(CONTAINER, 20)
    vm_samples = simulate_startup(VIRTUAL_MACHINE, 20)

    print(
        f"Container median startup: "
        f"{statistics.median(container_samples):.2f} seconds"
    )
    print(
        f"VM median startup: "
        f"{statistics.median(vm_samples):.2f} seconds"
    )
    print(
        f"Modeled VM/container startup ratio: "
        f"{statistics.median(vm_samples) / statistics.median(container_samples):.1f}x"
    )

    print(
        "\nThe model represents a structural difference: a container generally "
        "starts an application process, while a VM must initialize a guest OS."
    )


def density_analysis(host: Host, workload: WorkloadType) -> None:
    heading(f"Density Analysis: {workload.value}")

    print(
        f"Host capacity: {host.total_cpu_cores:.1f} CPU cores, "
        f"{host.total_memory_gib:.1f} GiB RAM, "
        f"{host.total_storage_gib:.1f} GiB storage"
    )

    for profile in (CONTAINER, VIRTUAL_MACHINE):
        count = 1
        while True:
            instances = build_instances(
                profile=profile,
                count=count,
                workload=workload,
                memory_gib=1.0,
                cpu_cores=0.25,
            )
            report = calculate_resource_report(host, instances)

            if (
                report.memory_utilization_percent > 90
                or report.cpu_utilization_percent > 90
                or report.storage_utilization_percent > 90
            ):
                break

            count += 1

        print(
            f"{profile.name:18} estimated maximum before 90% resource "
            f"threshold: {count - 1} instances"
        )


def portability_score(profile: DeploymentProfile, target_host_kernels: List[str]) -> float:
    """
    A simplified portability model.

    Containers are highly portable when the target provides a compatible
    kernel/runtime. VMs can carry their guest kernel and therefore tolerate
    greater host-OS variation.
    """
    if not target_host_kernels:
        raise ValueError("At least one target host is required.")

    compatible = 0
    for kernel in target_host_kernels:
        if profile == VIRTUAL_MACHINE:
            compatible += 1
        elif kernel.startswith("Linux"):
            compatible += 1

    return compatible / len(target_host_kernels) * 100


def portability_analysis() -> None:
    heading("Portability")

    hosts = [
        "Linux 6.8",
        "Linux 6.12",
        "Windows Server 2025",
        "FreeBSD 14",
    ]

    container_score = portability_score(CONTAINER, hosts)
    vm_score = portability_score(VIRTUAL_MACHINE, hosts)

    print(f"Container compatibility model: {container_score:.1f}%")
    print(f"VM compatibility model:        {vm_score:.1f}%")

    print()
    print(
        "Container portability is application-plus-runtime portability. "
        "The target must provide compatible kernel semantics and runtime "
        "support. A VM image carries a guest operating system, which makes "
        "the guest environment more independent of the host OS."
    )


def isolation_test_simulation() -> None:
    heading("Isolation Model")

    resources = {
        "process IDs": {
            "container": "isolated namespace",
            "vm": "isolated guest kernel",
        },
        "filesystem": {
            "container": "isolated root filesystem",
            "vm": "virtual disk and guest filesystem",
        },
        "kernel": {
            "container": "shared host kernel",
            "vm": "independent guest kernel",
        },
        "hardware": {
            "container": "host hardware exposed through OS",
            "vm": "virtual hardware presented by hypervisor",
        },
    }

    for resource, implementations in resources.items():
        print(f"\n{resource.title()}")
        for technology, behavior in implementations.items():
            print(f"  {technology.title():10}: {behavior}")

    print(
        "\nImportant security distinction: a container that escapes its "
        "intended isolation can potentially interact with the host kernel, "
        "whereas a VM escape targets a hypervisor boundary. Neither boundary "
        "should be treated as automatically secure."
    )


def performance_model(
    profile: DeploymentProfile,
    cpu_work_units: float,
    memory_work_units: float,
    io_work_units: float,
) -> Dict[str, float]:
    if min(cpu_work_units, memory_work_units, io_work_units) < 0:
        raise ValueError("Work units cannot be negative.")

    cpu_effective = cpu_work_units / (1 + profile.cpu_overhead_percent / 100)
    memory_effective = memory_work_units - profile.memory_overhead_mib / 1024
    io_effective = io_work_units * (
        1 - min(profile.cpu_overhead_percent / 100, 0.25)
    )

    return {
        "cpu": max(cpu_effective, 0),
        "memory": max(memory_effective, 0),
        "io": max(io_effective, 0),
    }


def performance_analysis() -> None:
    heading("Performance Model")

    workload = {
        "cpu_work": 100.0,
        "memory_work": 64.0,
        "io_work": 100.0,
    }

    for profile in (CONTAINER, VIRTUAL_MACHINE):
        result = performance_model(profile, **workload)
        print(
            f"{profile.name:18} "
            f"CPU={result['cpu']:.2f}, "
            f"Memory={result['memory']:.2f}, "
            f"I/O={result['io']:.2f}"
        )

    print(
        "\nContainers often have lower virtualization overhead because "
        "application processes execute directly on the host kernel. Modern "
        "hardware virtualization can make VM CPU and I/O overhead quite "
        "small, so the actual gap must be measured for the target workload."
    )


def scenario_analysis(scenario: Scenario) -> None:
    heading(f"Scenario: {scenario.name}")

    for profile in (CONTAINER, VIRTUAL_MACHINE):
        instances = build_instances(
            profile,
            scenario.instances,
            scenario.workload,
            scenario.memory_per_instance_gib,
            scenario.cpu_per_instance,
        )
        report = calculate_resource_report(scenario.host, instances)

        print_resource_report(profile.name, report)

        if report.memory_utilization_percent > 100:
            print("  Status: memory capacity exceeded")
        elif report.cpu_utilization_percent > 100:
            print("  Status: CPU capacity exceeded")
        elif report.storage_utilization_percent > 100:
            print("  Status: storage capacity exceeded")
        else:
            print("  Status: fits modeled host capacity")


def edge_case_validation() -> None:
    heading("Validation and Failure Conditions")

    tests = [
        ("zero instances", lambda: build_instances(
            CONTAINER, 0, WorkloadType.WEB_SERVICE, 1, 0.5
        )),
        ("negative memory", lambda: build_instances(
            CONTAINER, 1, WorkloadType.WEB_SERVICE, -1, 0.5
        )),
        ("negative CPU", lambda: build_instances(
            VIRTUAL_MACHINE, 1, WorkloadType.DATABASE, 4, -0.5
        )),
        ("empty portability targets", lambda: portability_score(CONTAINER, [])),
    ]

    for name, operation in tests:
        try:
            operation()
        except ValueError as error:
            print(f"{name}: correctly rejected -> {error}")
        else:
            print(f"{name}: ERROR, invalid input was accepted")


def decision_matrix() -> None:
    heading("Decision Matrix")

    criteria = [
        ("Isolation", CONTAINER.isolation.isolation_strength, VIRTUAL_MACHINE.isolation.isolation_strength),
        ("Startup speed", 0.95, 0.30),
        ("Resource efficiency", 0.95, 0.55),
        ("Guest OS independence", 0.25, 0.98),
        ("Workload density", CONTAINER.density_factor, VIRTUAL_MACHINE.density_factor),
    ]

    print(f"{'Criterion':28} {'Container':>12} {'VM':>12}")
    print("-" * 56)

    for criterion, container_score, vm_score in criteria:
        print(
            f"{criterion:28} "
            f"{container_score:>12.2f} "
            f"{vm_score:>12.2f}"
        )

    print()
    print(
        "These scores are comparative teaching values, not universal "
        "benchmarks. A production architecture should use measurements "
        "from the actual workload and infrastructure."
    )


def production_considerations() -> None:
    heading("Production Considerations")

    considerations = {
        "Security": (
            "Use least privilege, drop unnecessary Linux capabilities, "
            "apply seccomp/AppArmor/SELinux where appropriate, patch the "
            "kernel and runtime, and treat container isolation as a security boundary."
        ),
        "Resource control": (
            "Containers benefit from CPU and memory quotas, cgroups, requests, "
            "limits, and workload-level scheduling. VMs can use hypervisor "
            "resource allocation and guest-level limits."
        ),
        "Portability": (
            "Container images package application dependencies but do not "
            "normally package the host kernel. VM images package the guest OS "
            "and therefore provide stronger environment independence."
        ),
        "Operations": (
            "Containers commonly support rapid replacement and immutable "
            "deployment patterns. VMs remain valuable for legacy systems, "
            "heterogeneous operating systems, and stronger tenant boundaries."
        ),
        "Observability": (
            "Container monitoring must distinguish application, container, "
            "node, and orchestration metrics. VM monitoring adds guest OS "
            "metrics and hypervisor-level telemetry."
        ),
    }

    for area, explanation in considerations.items():
        print(f"\n{area}: {explanation}")


def run_all() -> None:
    host = Host(
        name="Example application host",
        total_cpu_cores=16,
        total_memory_gib=64,
        total_storage_gib=500,
        host_kernel="Linux 6.12",
    )

    compare_architecture()
    isolation_test_simulation()
    benchmark_startup()
    performance_analysis()
    portability_analysis()
    density_analysis(host, WorkloadType.MICROSERVICE)

    scenario_analysis(
        Scenario(
            name="High-density API services",
            workload=WorkloadType.MICROSERVICE,
            instances=30,
            memory_per_instance_gib=1.0,
            cpu_per_instance=0.25,
            host=host,
        )
    )

    scenario_analysis(
        Scenario(
            name="Legacy application estate",
            workload=WorkloadType.LEGACY_APPLICATION,
            instances=5,
            memory_per_instance_gib=4.0,
            cpu_per_instance=1.5,
            host=host,
        )
    )

    edge_case_validation()
    decision_matrix()
    production_considerations()


if __name__ == "__main__":
    started = time.perf_counter()
    run_all()
    elapsed = time.perf_counter() - started

    heading("Execution")
    print(f"Completed in {elapsed:.4f} seconds.")
    print(
        "The program models architectural differences without requiring a "
        "container runtime, hypervisor, root privileges, or third-party packages."
    )
