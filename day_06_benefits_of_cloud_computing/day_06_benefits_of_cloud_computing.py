"""
Benefits of Cloud Computing
============================

A self-contained study script covering cloud-computing benefits from beginner
through advanced level.

Topics demonstrated:
- Scalability
- Elasticity
- Availability
- Fault tolerance
- Global infrastructure
- Cost optimization
- Automation
- Disaster recovery
- Backup and recovery
- Capacity planning
- Load balancing
- Horizontal and vertical scaling
- Multi-zone and multi-region architecture
- Reliability metrics
- RTO and RPO
- Infrastructure automation
- Autoscaling
- Queue-based workload smoothing
- Serverless-style cost modeling
- Cloud cost estimation and optimization
- Failure simulation
- Disaster-recovery simulation
- Observability and operational considerations
- Security implications
- Trade-offs and architectural decision-making

The examples use only Python's standard library so that the script can run
without external dependencies.

Run:
    python cloud_computing_benefits.py

The script is intentionally executable. Each demonstration prints its
results so that concepts can be studied by reading the code and observing
the simulations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from random import Random
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================================
# SECTION 1: FUNDAMENTAL TERMINOLOGY
# ============================================================================

def print_section(title: str) -> None:
    """Print a consistent section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_subsection(title: str) -> None:
    """Print a subsection heading."""
    print(f"\n--- {title} ---")


def explain_basic_terms() -> None:
    """Introduce core cloud-computing concepts using executable examples."""

    print_section("1. CLOUD COMPUTING FUNDAMENTALS")

    concepts = {
        "Cloud computing": (
            "Delivery of computing resources such as compute, storage, "
            "networking, databases, and software through a provider-managed "
            "infrastructure."
        ),
        "Scalability": (
            "The ability of a system to handle increased workload by "
            "increasing available resources."
        ),
        "Elasticity": (
            "The ability to automatically add or remove resources as demand "
            "changes."
        ),
        "Availability": (
            "The proportion of time a service remains operational and "
            "accessible."
        ),
        "Reliability": (
            "The probability that a system performs correctly for a required "
            "period."
        ),
        "Fault tolerance": (
            "The ability to continue operating despite failures in individual "
            "components."
        ),
        "Region": (
            "A geographic cloud-provider area containing infrastructure "
            "deployed in a particular geographic location."
        ),
        "Availability Zone": (
            "An isolated infrastructure location within a cloud region, "
            "designed to reduce correlated failures."
        ),
        "RTO": (
            "Recovery Time Objective: the maximum acceptable time required "
            "to restore a service after a disruptive event."
        ),
        "RPO": (
            "Recovery Point Objective: the maximum acceptable amount of data "
            "loss measured in time."
        ),
    }

    for name, definition in concepts.items():
        print(f"{name}: {definition}")


# ============================================================================
# SECTION 2: SCALABILITY
# ============================================================================

@dataclass
class Server:
    """Simple representation of a compute instance."""

    name: str
    capacity_per_second: int
    active: bool = True

    def process_capacity(self) -> int:
        """Return zero capacity when the server is unavailable."""
        return self.capacity_per_second if self.active else 0


def horizontal_scaling(
    request_rate: int,
    server_capacity: int,
    minimum_servers: int = 1,
) -> int:
    """
    Calculate the number of servers needed for a workload.

    Horizontal scaling means adding or removing instances rather than
    increasing the resources of an existing instance.
    """
    if request_rate < 0:
        raise ValueError("Request rate cannot be negative.")
    if server_capacity <= 0:
        raise ValueError("Server capacity must be positive.")
    if minimum_servers < 1:
        raise ValueError("Minimum servers must be at least one.")

    required = ceil(request_rate / server_capacity) if request_rate else 1
    return max(minimum_servers, required)


def vertical_scaling(
    current_capacity: int,
    requested_capacity: int,
) -> Tuple[int, int]:
    """
    Demonstrate vertical scaling.

    Returns:
        old capacity, new capacity
    """
    if current_capacity <= 0 or requested_capacity <= 0:
        raise ValueError("Capacities must be positive.")
    if requested_capacity < current_capacity:
        raise ValueError(
            "This demonstration only models vertical scale-up, not scale-down."
        )

    return current_capacity, requested_capacity


def demonstrate_scalability() -> None:
    print_section("2. SCALABILITY")

    print_subsection("Horizontal scaling")

    workloads = [100, 500, 1_000, 2_500, 5_000, 12_000]

    for workload in workloads:
        servers = horizontal_scaling(
            request_rate=workload,
            server_capacity=1_000,
            minimum_servers=2,
        )
        print(
            f"Workload={workload:>5} requests/s -> "
            f"servers required={servers}"
        )

    print_subsection("Vertical scaling")

    old_capacity, new_capacity = vertical_scaling(
        current_capacity=1_000,
        requested_capacity=4_000,
    )

    print(
        f"One server changed from {old_capacity} to "
        f"{new_capacity} requests/s capacity."
    )

    print_subsection("Scalability trade-offs")

    comparisons = [
        (
            "Horizontal scaling",
            "Add instances",
            "Good for distributed workloads and fault isolation",
            "Requires coordination, networking, and distributed-system design",
        ),
        (
            "Vertical scaling",
            "Increase instance size",
            "Simple for some applications",
            "Has hardware limits and can create a larger failure domain",
        ),
    ]

    for approach, mechanism, advantage, limitation in comparisons:
        print(f"\n{approach}")
        print(f"  Mechanism:   {mechanism}")
        print(f"  Advantage:   {advantage}")
        print(f"  Limitation:  {limitation}")


# ============================================================================
# SECTION 3: ELASTICITY
# ============================================================================

@dataclass
class ElasticCluster:
    """A simple cluster that grows and shrinks based on demand."""

    server_capacity: int
    minimum_servers: int
    maximum_servers: int
    servers: int = field(init=False)

    def __post_init__(self) -> None:
        if self.server_capacity <= 0:
            raise ValueError("Server capacity must be positive.")
        if self.minimum_servers < 1:
            raise ValueError("Minimum servers must be at least one.")
        if self.maximum_servers < self.minimum_servers:
            raise ValueError("Maximum servers must not be below minimum.")
        self.servers = self.minimum_servers

    def autoscale(self, request_rate: int) -> None:
        """Resize the cluster to match current demand."""
        required = horizontal_scaling(
            request_rate,
            self.server_capacity,
            self.minimum_servers,
        )
        self.servers = min(required, self.maximum_servers)

    @property
    def capacity(self) -> int:
        return self.servers * self.server_capacity

    def utilization(self, request_rate: int) -> float:
        """Return cluster utilization as a fraction."""
        if self.capacity <= 0:
            return 0.0
        return min(request_rate / self.capacity, 1.0)


def demonstrate_elasticity() -> None:
    print_section("3. ELASTICITY AND AUTOSCALING")

    cluster = ElasticCluster(
        server_capacity=1_000,
        minimum_servers=2,
        maximum_servers=10,
    )

    traffic_pattern = [
        500,
        1_000,
        1_800,
        4_000,
        7_500,
        10_000,
        6_000,
        3_000,
        1_000,
        300,
    ]

    print(
        f"{'Demand':>10} {'Servers':>10} "
        f"{'Capacity':>10} {'Utilization':>14}"
    )

    for request_rate in traffic_pattern:
        cluster.autoscale(request_rate)
        utilization = cluster.utilization(request_rate)
        print(
            f"{request_rate:>10} "
            f"{cluster.servers:>10} "
            f"{cluster.capacity:>10} "
            f"{utilization:>13.1%}"
        )

    print("\nElasticity differs from scalability:")
    print("  Scalability asks whether capacity can be increased.")
    print("  Elasticity asks whether capacity can dynamically follow demand.")


# ============================================================================
# SECTION 4: AUTOSCALING POLICIES
# ============================================================================

@dataclass
class AutoscalingPolicy:
    """A threshold-based autoscaling policy."""

    minimum_servers: int
    maximum_servers: int
    scale_up_threshold: float
    scale_down_threshold: float
    scale_up_step: int = 1
    scale_down_step: int = 1

    def decide(self, server_count: int, utilization: float) -> int:
        """Return the desired number of servers."""
        if server_count < self.minimum_servers:
            return self.minimum_servers

        if utilization > self.scale_up_threshold:
            return min(
                self.maximum_servers,
                server_count + self.scale_up_step,
            )

        if utilization < self.scale_down_threshold:
            return max(
                self.minimum_servers,
                server_count - self.scale_down_step,
            )

        return server_count


def demonstrate_autoscaling_policy() -> None:
    print_section("4. AUTOSCALING POLICY DESIGN")

    policy = AutoscalingPolicy(
        minimum_servers=2,
        maximum_servers=8,
        scale_up_threshold=0.75,
        scale_down_threshold=0.30,
        scale_up_step=2,
        scale_down_step=1,
    )

    server_count = 2
    utilization_sequence = [
        0.20,
        0.25,
        0.50,
        0.80,
        0.90,
        0.95,
        0.65,
        0.20,
        0.10,
    ]

    print(f"{'Utilization':>14} {'Old':>8} {'New':>8}")

    for utilization in utilization_sequence:
        old_count = server_count
        server_count = policy.decide(server_count, utilization)
        print(
            f"{utilization:>13.0%} "
            f"{old_count:>8} "
            f"{server_count:>8}"
        )

    print("\nImportant autoscaling considerations:")
    print("  - Scale-up delay can cause temporary overload.")
    print("  - Aggressive scale-down can cause capacity oscillation.")
    print("  - Cooldown periods reduce scaling thrashing.")
    print("  - Minimum capacity protects baseline availability.")
    print("  - Maximum capacity controls runaway costs.")


# ============================================================================
# SECTION 5: LOAD BALANCING
# ============================================================================

def round_robin_distribution(
    requests: int,
    server_count: int,
) -> List[int]:
    """Distribute requests approximately evenly across servers."""
    if requests < 0:
        raise ValueError("Requests cannot be negative.")
    if server_count <= 0:
        raise ValueError("Server count must be positive.")

    distribution = [0] * server_count

    for request_id in range(requests):
        distribution[request_id % server_count] += 1

    return distribution


def demonstrate_load_balancing() -> None:
    print_section("5. LOAD BALANCING")

    requests = 17
    servers = 4

    distribution = round_robin_distribution(requests, servers)

    for index, assigned_requests in enumerate(distribution, start=1):
        print(
            f"Server {index}: {assigned_requests} requests"
        )

    print(
        "\nA load balancer helps make horizontal scaling useful by "
        "distributing traffic across available instances."
    )


# ============================================================================
# SECTION 6: AVAILABILITY
# ============================================================================

def availability_percentage(
    total_minutes: float,
    downtime_minutes: float,
) -> float:
    """Calculate availability percentage."""
    if total_minutes <= 0:
        raise ValueError("Total time must be positive.")
    if downtime_minutes < 0:
        raise ValueError("Downtime cannot be negative.")
    if downtime_minutes > total_minutes:
        raise ValueError("Downtime cannot exceed total time.")

    return (total_minutes - downtime_minutes) / total_minutes * 100


def downtime_from_availability(
    total_minutes: float,
    target_availability: float,
) -> float:
    """Calculate permitted downtime for a target availability percentage."""
    if total_minutes <= 0:
        raise ValueError("Total time must be positive.")
    if not 0 <= target_availability <= 100:
        raise ValueError("Availability must be between 0 and 100.")

    return total_minutes * (1 - target_availability / 100)


def demonstrate_availability() -> None:
    print_section("6. AVAILABILITY")

    periods = {
        "99.0%": 99.0,
        "99.9%": 99.9,
        "99.99%": 99.99,
        "99.999%": 99.999,
    }

    minutes_per_year = 365 * 24 * 60

    print("Approximate maximum downtime in a 365-day year:")

    for label, target in periods.items():
        downtime = downtime_from_availability(
            minutes_per_year,
            target,
        )
        print(f"  {label:>7}: {downtime:.2f} minutes")

    observed = availability_percentage(
        total_minutes=43_200,
        downtime_minutes=20,
    )

    print(
        f"\nObserved availability over 30 days with 20 minutes "
        f"downtime: {observed:.4f}%"
    )


# ============================================================================
# SECTION 7: REDUNDANCY AND FAULT TOLERANCE
# ============================================================================

@dataclass
class ServiceCluster:
    """Represents service instances distributed across failure domains."""

    instances: Dict[str, int]

    def total_instances(self) -> int:
        return sum(self.instances.values())

    def lose_zone(self, zone: str) -> int:
        """Remove all instances in one zone and return remaining capacity."""
        if zone not in self.instances:
            raise KeyError(f"Unknown zone: {zone}")

        remaining = self.total_instances() - self.instances[zone]
        return remaining

    def can_survive_zone_failure(self, required_instances: int) -> bool:
        """Determine whether the cluster can satisfy demand after one zone fails."""
        for zone in self.instances:
            if self.lose_zone(zone) < required_instances:
                return False
        return True


def demonstrate_fault_tolerance() -> None:
    print_section("7. REDUNDANCY AND FAULT TOLERANCE")

    cluster = ServiceCluster(
        instances={
            "zone-a": 3,
            "zone-b": 3,
            "zone-c": 3,
        }
    )

    print(f"Total instances: {cluster.total_instances()}")

    for zone in cluster.instances:
        print(
            f"If {zone} fails, remaining instances: "
            f"{cluster.lose_zone(zone)}"
        )

    required = 6

    print(
        f"\nCan the cluster maintain at least {required} instances "
        f"after any one zone failure? "
        f"{cluster.can_survive_zone_failure(required)}"
    )

    print(
        "\nRedundancy increases resilience, but duplicated resources "
        "also increase cost and operational complexity."
    )


# ============================================================================
# SECTION 8: GLOBAL INFRASTRUCTURE
# ============================================================================

@dataclass(frozen=True)
class Region:
    """Simplified representation of a geographic cloud region."""

    name: str
    latency_ms: Dict[str, float]


def choose_lowest_latency_region(
    client_location: str,
    regions: Sequence[Region],
) -> Region:
    """Select the region with the lowest modeled network latency."""
    if not regions:
        raise ValueError("At least one region is required.")

    for region in regions:
        if client_location not in region.latency_ms:
            raise KeyError(
                f"{client_location} missing from region {region.name}"
            )

    return min(
        regions,
        key=lambda region: region.latency_ms[client_location],
    )


def demonstrate_global_infrastructure() -> None:
    print_section("8. GLOBAL INFRASTRUCTURE")

    regions = [
        Region(
            "Asia-Pacific",
            {
                "India": 35,
                "Europe": 110,
                "North America": 180,
            },
        ),
        Region(
            "Europe",
            {
                "India": 120,
                "Europe": 25,
                "North America": 100,
            },
        ),
        Region(
            "North America",
            {
                "India": 190,
                "Europe": 105,
                "North America": 20,
            },
        ),
    ]

    for client in ["India", "Europe", "North America"]:
        selected = choose_lowest_latency_region(client, regions)
        latency = selected.latency_ms[client]
        print(
            f"{client:>15} -> {selected.name:<16} "
            f"({latency:.0f} ms modeled latency)"
        )

    print(
        "\nGlobal infrastructure can reduce latency, support geographic "
        "resilience, satisfy data-location requirements, and improve "
        "user experience."
    )


# ============================================================================
# SECTION 9: COST MODELING
# ============================================================================

@dataclass
class ComputePricing:
    """Simplified hourly compute pricing model."""

    price_per_instance_hour: float

    def monthly_cost(
        self,
        instances: int,
        hours_per_month: float = 730,
    ) -> float:
        if instances < 0:
            raise ValueError("Instances cannot be negative.")
        if hours_per_month <= 0:
            raise ValueError("Hours per month must be positive.")

        return instances * self.price_per_instance_hour * hours_per_month


def cost_per_request(
    monthly_cost: float,
    monthly_requests: int,
) -> float:
    """Calculate infrastructure cost per request."""
    if monthly_cost < 0:
        raise ValueError("Cost cannot be negative.")
    if monthly_requests <= 0:
        raise ValueError("Requests must be positive.")

    return monthly_cost / monthly_requests


def demonstrate_cost_optimization() -> None:
    print_section("9. COST OPTIMIZATION")

    pricing = ComputePricing(price_per_instance_hour=0.08)

    fixed_instances = 10
    fixed_cost = pricing.monthly_cost(fixed_instances)

    print(f"Fixed 10-instance monthly cost: ${fixed_cost:,.2f}")

    demand_hours = {
        2: 300,
        4: 200,
        8: 150,
        10: 80,
    }

    elastic_cost = sum(
        pricing.monthly_cost(instances, hours)
        for instances, hours in demand_hours.items()
    )

    print(f"Modeled elastic monthly cost:     ${elastic_cost:,.2f}")

    monthly_requests = 50_000_000

    print(
        f"Fixed cost per request: "
        f"${cost_per_request(fixed_cost, monthly_requests):.8f}"
    )
    print(
        f"Elastic cost per request: "
        f"${cost_per_request(elastic_cost, monthly_requests):.8f}"
    )

    print("\nCloud cost optimization mechanisms include:")
    print("  - Rightsizing")
    print("  - Autoscaling")
    print("  - Removing idle resources")
    print("  - Choosing suitable pricing models")
    print("  - Scheduling non-production environments")
    print("  - Storage lifecycle management")
    print("  - Monitoring and budgets")
    print("  - Architecture-level efficiency")


# ============================================================================
# SECTION 10: CAPEX VS OPEX
# ============================================================================

def compare_capex_opex() -> None:
    print_section("10. CAPEX AND OPEX")

    capex = {
        "servers": 100_000,
        "networking": 30_000,
        "storage": 20_000,
    }

    opex = {
        "compute": 8_000,
        "storage": 1_500,
        "networking": 1_000,
        "operations": 3_000,
    }

    initial_capex = sum(capex.values())
    monthly_opex = sum(opex.values())

    print(f"Example initial capital expenditure: ${initial_capex:,.2f}")
    print(f"Example monthly operating expenditure: ${monthly_opex:,.2f}")

    print(
        "\nTraditional infrastructure commonly requires substantial "
        "up-front capital investment."
    )
    print(
        "Cloud services commonly convert infrastructure expenditure into "
        "usage-oriented operating expenditure."
    )
    print(
        "This does not mean cloud computing is automatically cheaper. "
        "Poorly governed cloud usage can become expensive."
    )


# ============================================================================
# SECTION 11: QUEUES AND BURST HANDLING
# ============================================================================

@dataclass
class QueueSystem:
    """
    Simplified queue model.

    Queues decouple producers from consumers and can absorb temporary
    workload bursts without requiring consumer capacity to equal the
    instantaneous peak.
    """

    queue_depth: int = 0

    def enqueue(self, messages: int) -> None:
        if messages < 0:
            raise ValueError("Messages cannot be negative.")
        self.queue_depth += messages

    def process(self, messages: int) -> int:
        if messages < 0:
            raise ValueError("Messages cannot be negative.")

        processed = min(messages, self.queue_depth)
        self.queue_depth -= processed
        return processed


def demonstrate_queue_based_scaling() -> None:
    print_section("11. QUEUE-BASED BURST HANDLING")

    queue = QueueSystem()

    arrivals = [100, 500, 2_000, 5_000, 1_000, 300]
    processing_capacity = 1_500

    print(f"{'Arrivals':>10} {'Processed':>12} {'Queue':>10}")

    for incoming in arrivals:
        queue.enqueue(incoming)
        processed = queue.process(processing_capacity)
        print(
            f"{incoming:>10} "
            f"{processed:>12} "
            f"{queue.queue_depth:>10}"
        )

    print(
        "\nQueues can smooth bursts, but they introduce latency and require "
        "monitoring of queue depth, age, retry behavior, and dead-letter "
        "handling."
    )


# ============================================================================
# SECTION 12: AUTOMATION
# ============================================================================

@dataclass
class Resource:
    """Resource used to demonstrate automated lifecycle management."""

    name: str
    environment: str
    active: bool = True


def stop_nonproduction_resources(
    resources: Iterable[Resource],
) -> List[str]:
    """
    Automate a simple governance policy.

    Production resources remain active. Non-production resources are stopped.
    """
    stopped = []

    for resource in resources:
        if resource.environment.lower() != "production":
            resource.active = False
            stopped.append(resource.name)

    return stopped


def demonstrate_automation() -> None:
    print_section("12. AUTOMATION")

    resources = [
        Resource("production-api", "production"),
        Resource("development-api", "development"),
        Resource("testing-db", "testing"),
        Resource("staging-web", "staging"),
    ]

    stopped = stop_nonproduction_resources(resources)

    for resource in resources:
        state = "running" if resource.active else "stopped"
        print(f"{resource.name:<20} {resource.environment:<15} {state}")

    print(f"\nAutomated policy stopped: {', '.join(stopped)}")

    print(
        "\nAutomation can reduce manual operations, improve consistency, "
        "enforce policies, accelerate deployment, and reduce waste."
    )


# ============================================================================
# SECTION 13: INFRASTRUCTURE AS CODE CONCEPT
# ============================================================================

@dataclass
class ComputeConfiguration:
    """Declarative representation of desired infrastructure."""

    application: str
    instances: int
    cpu_units: int
    memory_gb: int
    region: str


def reconcile_infrastructure(
    desired: ComputeConfiguration,
    actual: ComputeConfiguration,
) -> List[str]:
    """
    Identify differences between desired and actual state.

    This models the core idea behind declarative infrastructure management:
    define desired state and automatically reconcile actual infrastructure.
    """
    changes = []

    if desired.instances != actual.instances:
        changes.append(
            f"instances: {actual.instances} -> {desired.instances}"
        )

    if desired.cpu_units != actual.cpu_units:
        changes.append(
            f"cpu_units: {actual.cpu_units} -> {desired.cpu_units}"
        )

    if desired.memory_gb != actual.memory_gb:
        changes.append(
            f"memory_gb: {actual.memory_gb} -> {desired.memory_gb}"
        )

    if desired.region != actual.region:
        changes.append(
            f"region: {actual.region} -> {desired.region}"
        )

    return changes


def demonstrate_infrastructure_as_code() -> None:
    print_section("13. INFRASTRUCTURE AS CODE")

    desired = ComputeConfiguration(
        application="payments-api",
        instances=6,
        cpu_units=4,
        memory_gb=16,
        region="region-a",
    )

    actual = ComputeConfiguration(
        application="payments-api",
        instances=3,
        cpu_units=2,
        memory_gb=8,
        region="region-a",
    )

    changes = reconcile_infrastructure(desired, actual)

    print("Desired infrastructure differs from actual infrastructure:")

    for change in changes:
        print(f"  - {change}")

    print(
        "\nDeclarative infrastructure allows infrastructure definitions "
        "to be reviewed, versioned, tested, and repeatedly applied."
    )


# ============================================================================
# SECTION 14: DISASTER RECOVERY
# ============================================================================

class RecoveryStrategy(Enum):
    BACKUP_RESTORE = "Backup and Restore"
    PILOT_LIGHT = "Pilot Light"
    WARM_STANDBY = "Warm Standby"
    ACTIVE_ACTIVE = "Active-Active"


@dataclass
class RecoveryPlan:
    """Simplified disaster-recovery plan."""

    strategy: RecoveryStrategy
    rto_minutes: int
    rpo_minutes: int
    recovery_cost_per_month: float

    def validate(self) -> None:
        if self.rto_minutes < 0:
            raise ValueError("RTO cannot be negative.")
        if self.rpo_minutes < 0:
            raise ValueError("RPO cannot be negative.")
        if self.recovery_cost_per_month < 0:
            raise ValueError("Recovery cost cannot be negative.")


def demonstrate_disaster_recovery() -> None:
    print_section("14. DISASTER RECOVERY")

    plans = [
        RecoveryPlan(
            RecoveryStrategy.BACKUP_RESTORE,
            rto_minutes=240,
            rpo_minutes=60,
            recovery_cost_per_month=500,
        ),
        RecoveryPlan(
            RecoveryStrategy.PILOT_LIGHT,
            rto_minutes=90,
            rpo_minutes=15,
            recovery_cost_per_month=1_500,
        ),
        RecoveryPlan(
            RecoveryStrategy.WARM_STANDBY,
            rto_minutes=30,
            rpo_minutes=5,
            recovery_cost_per_month=4_000,
        ),
        RecoveryPlan(
            RecoveryStrategy.ACTIVE_ACTIVE,
            rto_minutes=5,
            rpo_minutes=0,
            recovery_cost_per_month=12_000,
        ),
    ]

    print(
        f"{'Strategy':<20} "
        f"{'RTO':>10} "
        f"{'RPO':>10} "
        f"{'Monthly Cost':>16}"
    )

    for plan in plans:
        plan.validate()
        print(
            f"{plan.strategy.value:<20} "
            f"{plan.rto_minutes:>7} min "
            f"{plan.rpo_minutes:>7} min "
            f"${plan.recovery_cost_per_month:>14,.2f}"
        )

    print(
        "\nThere is a fundamental trade-off between recovery speed, "
        "recovery-point objectives, operational complexity, and cost."
    )


# ============================================================================
# SECTION 15: BACKUP SIMULATION
# ============================================================================

@dataclass
class DatabaseState:
    """Tiny database model used to demonstrate backup and recovery."""

    records: Dict[int, str] = field(default_factory=dict)

    def write(self, record_id: int, value: str) -> None:
        self.records[record_id] = value

    def snapshot(self) -> Dict[int, str]:
        """Return an independent backup copy."""
        return dict(self.records)

    def restore(self, backup: Dict[int, str]) -> None:
        self.records = dict(backup)


def demonstrate_backup_restore() -> None:
    print_section("15. BACKUP AND RESTORE")

    database = DatabaseState()

    database.write(1, "Alice")
    database.write(2, "Bob")
    database.write(3, "Charlie")

    backup = database.snapshot()

    print(f"Records before incident: {database.records}")

    database.write(4, "Unintended record")
    database.write(5, "Corrupted record")

    print(f"Records after incident:  {database.records}")

    database.restore(backup)

    print(f"Records after restore:    {database.records}")

    print(
        "\nA backup is useful only when it is recoverable. Production "
        "backup programs therefore need restoration tests, retention "
        "policies, integrity checks, access controls, and monitoring."
    )


# ============================================================================
# SECTION 16: RPO SIMULATION
# ============================================================================

def simulate_data_loss(
    writes_per_minute: int,
    rpo_minutes: int,
) -> int:
    """
    Estimate maximum writes potentially lost under the modeled RPO.

    This is intentionally simplified: actual data loss depends on the
    application's replication and backup architecture.
    """
    if writes_per_minute < 0:
        raise ValueError("Write rate cannot be negative.")
    if rpo_minutes < 0:
        raise ValueError("RPO cannot be negative.")

    return writes_per_minute * rpo_minutes


def demonstrate_rpo() -> None:
    print_section("16. RPO AND DATA LOSS")

    write_rate = 120

    for rpo in [60, 15, 5, 1, 0]:
        potential_loss = simulate_data_loss(write_rate, rpo)
        print(
            f"RPO={rpo:>2} minutes -> "
            f"modeled maximum unreplicated writes={potential_loss}"
        )

    print(
        "\nRPO does not directly mean that exactly that many records will "
        "be lost. It specifies an acceptable recovery-point window."
    )


# ============================================================================
# SECTION 17: RTO SIMULATION
# ============================================================================

@dataclass
class RecoveryPhase:
    """One phase of a recovery procedure."""

    name: str
    duration_minutes: int


def calculate_rto(phases: Sequence[RecoveryPhase]) -> int:
    """Calculate total modeled recovery duration."""
    if any(phase.duration_minutes < 0 for phase in phases):
        raise ValueError("Recovery durations cannot be negative.")

    return sum(phase.duration_minutes for phase in phases)


def demonstrate_rto() -> None:
    print_section("17. RTO AND RECOVERY TIME")

    phases = [
        RecoveryPhase("Detect incident", 5),
        RecoveryPhase("Declare disaster", 5),
        RecoveryPhase("Provision infrastructure", 15),
        RecoveryPhase("Restore database", 20),
        RecoveryPhase("Validate application", 10),
        RecoveryPhase("Redirect traffic", 5),
    ]

    total = calculate_rto(phases)

    for phase in phases:
        print(f"{phase.name:<30} {phase.duration_minutes:>4} minutes")

    print(f"\nModeled RTO: {total} minutes")


# ============================================================================
# SECTION 18: MULTI-REGION FAILURE SIMULATION
# ============================================================================

@dataclass
class RegionCapacity:
    """Compute capacity and operational status for one region."""

    name: str
    capacity: int
    healthy: bool = True


def total_healthy_capacity(
    regions: Sequence[RegionCapacity],
) -> int:
    """Return capacity contributed by healthy regions."""
    return sum(
        region.capacity
        for region in regions
        if region.healthy
    )


def demonstrate_multi_region_resilience() -> None:
    print_section("18. MULTI-REGION RESILIENCE")

    regions = [
        RegionCapacity("Region-A", 5_000),
        RegionCapacity("Region-B", 5_000),
        RegionCapacity("Region-C", 5_000),
    ]

    demand = 7_000

    print(f"Normal healthy capacity: {total_healthy_capacity(regions)}")
    print(f"Required capacity:       {demand}")

    regions[0].healthy = False

    remaining_capacity = total_healthy_capacity(regions)

    print(
        f"After Region-A failure:  {remaining_capacity}"
    )
    print(
        f"Demand still satisfied:  {remaining_capacity >= demand}"
    )

    regions[1].healthy = False

    remaining_capacity = total_healthy_capacity(regions)

    print(
        f"After second region failure: {remaining_capacity}"
    )
    print(
        f"Demand still satisfied:       {remaining_capacity >= demand}"
    )

    print(
        "\nMulti-region architectures improve geographic resilience but "
        "can increase data-replication complexity, network costs, latency, "
        "consistency challenges, and operational complexity."
    )


# ============================================================================
# SECTION 19: COST OF OVERPROVISIONING
# ============================================================================

def utilization_cost_analysis(
    server_count: int,
    server_capacity: int,
    average_demand: int,
    hourly_price: float,
) -> Dict[str, float]:
    """Analyze waste caused by provisioning substantially more capacity than needed."""

    if server_count <= 0:
        raise ValueError("Server count must be positive.")
    if server_capacity <= 0:
        raise ValueError("Server capacity must be positive.")
    if average_demand < 0:
        raise ValueError("Demand cannot be negative.")
    if hourly_price < 0:
        raise ValueError("Price cannot be negative.")

    capacity = server_count * server_capacity
    utilization = min(average_demand / capacity, 1.0)
    hourly_cost = server_count * hourly_price
    monthly_cost = hourly_cost * 730

    return {
        "capacity": capacity,
        "utilization": utilization,
        "hourly_cost": hourly_cost,
        "monthly_cost": monthly_cost,
    }


def demonstrate_overprovisioning() -> None:
    print_section("19. OVERPROVISIONING AND WASTE")

    analysis = utilization_cost_analysis(
        server_count=20,
        server_capacity=1_000,
        average_demand=5_000,
        hourly_price=0.08,
    )

    print(f"Provisioned capacity: {analysis['capacity']}")
    print(f"Average utilization:  {analysis['utilization']:.1%}")
    print(f"Hourly cost:          ${analysis['hourly_cost']:.2f}")
    print(f"Monthly cost:         ${analysis['monthly_cost']:.2f}")

    print(
        "\nCloud elasticity can reduce this type of waste when workload "
        "patterns are predictable enough for autoscaling to respond safely."
    )


# ============================================================================
# SECTION 20: SERVERLESS-STYLE COST MODEL
# ============================================================================

@dataclass
class FunctionPricing:
    """Simplified serverless-style execution pricing."""

    request_price_per_million: float
    gb_second_price: float

    def monthly_cost(
        self,
        requests: int,
        gb_seconds: float,
    ) -> float:
        if requests < 0 or gb_seconds < 0:
            raise ValueError("Usage cannot be negative.")

        request_cost = (
            requests / 1_000_000
        ) * self.request_price_per_million

        execution_cost = gb_seconds * self.gb_second_price

        return request_cost + execution_cost


def demonstrate_usage_based_computing() -> None:
    print_section("20. USAGE-BASED COMPUTING")

    pricing = FunctionPricing(
        request_price_per_million=0.20,
        gb_second_price=0.000016,
    )

    cost = pricing.monthly_cost(
        requests=25_000_000,
        gb_seconds=500_000,
    )

    print(f"Modeled monthly serverless-style cost: ${cost:,.2f}")

    print(
        "\nUsage-based services can be attractive for intermittent workloads "
        "because capacity does not need to remain permanently provisioned."
    )

    print(
        "They may be less attractive for sustained workloads depending on "
        "pricing, execution duration, architecture, networking, and "
        "operational requirements."
    )


# ============================================================================
# SECTION 21: CLOUD BENEFIT SCORECARD
# ============================================================================

@dataclass
class BenefitScore:
    """Score a cloud benefit from 1 to 5."""

    name: str
    score: int
    justification: str

    def validate(self) -> None:
        if not 1 <= self.score <= 5:
            raise ValueError("Score must be between 1 and 5.")


def demonstrate_benefit_scorecard() -> None:
    print_section("21. CLOUD BENEFIT SCORECARD")

    scores = [
        BenefitScore(
            "Scalability",
            5,
            "Resources can be expanded as workloads grow.",
        ),
        BenefitScore(
            "Elasticity",
            5,
            "Resources can respond dynamically to changing demand.",
        ),
        BenefitScore(
            "Global reach",
            5,
            "Infrastructure can be deployed closer to users.",
        ),
        BenefitScore(
            "Automation",
            5,
            "Infrastructure and operations can be programmatically managed.",
        ),
        BenefitScore(
            "Cost optimization",
            4,
            "Consumption models enable optimization, but poor governance "
            "can produce substantial waste.",
        ),
        BenefitScore(
            "Disaster recovery",
            5,
            "Geographically distributed infrastructure can support recovery.",
        ),
    ]

    for score in scores:
        score.validate()
        print(
            f"{score.name:<22} "
            f"{score.score}/5 "
            f"- {score.justification}"
        )


# ============================================================================
# SECTION 22: CLOUD SERVICE MODELS
# ============================================================================

def explain_service_models() -> None:
    print_section("22. SERVICE MODELS AND THEIR BENEFITS")

    models = [
        (
            "IaaS",
            "Infrastructure as a Service",
            "Virtual machines, networks, disks",
            "High control and flexibility",
            "More infrastructure management",
        ),
        (
            "PaaS",
            "Platform as a Service",
            "Application runtime and managed platform",
            "Less operational infrastructure work",
            "Less low-level control",
        ),
        (
            "SaaS",
            "Software as a Service",
            "Complete software application",
            "Minimal infrastructure management",
            "Limited control over implementation",
        ),
        (
            "Serverless",
            "Event-driven managed execution",
            "Functions or managed execution units",
            "Fine-grained operational abstraction",
            "Execution, runtime, networking, and pricing constraints",
        ),
    ]

    for (
        abbreviation,
        full_name,
        examples,
        benefit,
        tradeoff,
    ) in models:
        print(f"\n{abbreviation}: {full_name}")
        print(f"  Typical resource: {examples}")
        print(f"  Benefit:          {benefit}")
        print(f"  Trade-off:        {tradeoff}")


# ============================================================================
# SECTION 23: MANAGED SERVICES
# ============================================================================

@dataclass
class ManagedService:
    """Represent a service-management responsibility split."""

    service_name: str
    provider_managed: List[str]
    customer_managed: List[str]


def demonstrate_managed_services() -> None:
    print_section("23. MANAGED SERVICES")

    database = ManagedService(
        service_name="Managed database",
        provider_managed=[
            "Underlying hardware",
            "Host operating environment",
            "Selected database maintenance",
            "Infrastructure availability mechanisms",
        ],
        customer_managed=[
            "Schema",
            "Queries",
            "Indexes",
            "Data access policies",
            "Application behavior",
        ],
    )

    print(database.service_name)

    print("Provider-managed responsibilities:")
    for item in database.provider_managed:
        print(f"  - {item}")

    print("Customer-managed responsibilities:")
    for item in database.customer_managed:
        print(f"  - {item}")

    print(
        "\nManaged services shift operational responsibility to the provider "
        "but do not eliminate the customer's responsibility for architecture, "
        "configuration, data, security, and application behavior."
    )


# ============================================================================
# SECTION 24: SECURITY CONSIDERATIONS
# ============================================================================

@dataclass
class SecurityControl:
    """Simple representation of a security control."""

    control: str
    purpose: str


def demonstrate_security() -> None:
    print_section("24. SECURITY CONSIDERATIONS")

    controls = [
        SecurityControl(
            "Identity and access management",
            "Restrict access to authorized identities and actions.",
        ),
        SecurityControl(
            "Encryption at rest",
            "Protect stored data if storage media or snapshots are exposed.",
        ),
        SecurityControl(
            "Encryption in transit",
            "Protect data moving across networks.",
        ),
        SecurityControl(
            "Least privilege",
            "Give identities only the permissions required for their tasks.",
        ),
        SecurityControl(
            "Network segmentation",
            "Reduce unnecessary communication paths between workloads.",
        ),
        SecurityControl(
            "Audit logging",
            "Record security-relevant activity for detection and investigation.",
        ),
        SecurityControl(
            "Backup protection",
            "Protect backups from unauthorized deletion or modification.",
        ),
        SecurityControl(
            "Secrets management",
            "Avoid embedding credentials directly into source code.",
        ),
    ]

    for control in controls:
        print(f"{control.control:<28} -> {control.purpose}")

    print(
        "\nCloud elasticity does not automatically provide security. "
        "Automation must be designed so that scaling, deployment, backup, "
        "and recovery operations preserve security controls."
    )


# ============================================================================
# SECTION 25: OBSERVABILITY
# ============================================================================

@dataclass
class MetricSample:
    """Basic observability metric."""

    timestamp: int
    request_rate: int
    utilization: float
    error_rate: float
    latency_ms: float


def calculate_average_latency(
    samples: Sequence[MetricSample],
) -> float:
    """Calculate mean latency."""
    if not samples:
        return 0.0
    return mean(sample.latency_ms for sample in samples)


def calculate_average_error_rate(
    samples: Sequence[MetricSample],
) -> float:
    """Calculate mean error rate."""
    if not samples:
        return 0.0
    return mean(sample.error_rate for sample in samples)


def demonstrate_observability() -> None:
    print_section("25. OBSERVABILITY")

    samples = [
        MetricSample(1, 800, 0.40, 0.010, 100),
        MetricSample(2, 1_200, 0.60, 0.012, 110),
        MetricSample(3, 1_800, 0.78, 0.015, 125),
        MetricSample(4, 2_500, 0.90, 0.030, 180),
        MetricSample(5, 900, 0.45, 0.011, 105),
    ]

    for sample in samples:
        print(
            f"t={sample.timestamp} "
            f"requests/s={sample.request_rate:>5} "
            f"utilization={sample.utilization:>5.0%} "
            f"errors={sample.error_rate:>5.1%} "
            f"latency={sample.latency_ms:>4.0f} ms"
        )

    print(
        f"\nAverage latency: "
        f"{calculate_average_latency(samples):.1f} ms"
    )

    print(
        f"Average error rate: "
        f"{calculate_average_error_rate(samples):.2%}"
    )

    print(
        "\nScaling decisions based on a single metric can be misleading. "
        "Production systems commonly combine utilization, request rate, "
        "latency, queue depth, error rate, and business metrics."
    )


# ============================================================================
# SECTION 26: AUTOSCALING EDGE CASES
# ============================================================================

def safe_scale_decision(
    current_servers: int,
    requested_servers: int,
    minimum_servers: int,
    maximum_servers: int,
) -> int:
    """
    Clamp scaling decisions to operational boundaries.

    This protects against accidental requests that violate capacity policy.
    """
    if minimum_servers < 1:
        raise ValueError("Minimum servers must be at least one.")
    if maximum_servers < minimum_servers:
        raise ValueError("Maximum cannot be below minimum.")
    if current_servers < 0:
        raise ValueError("Current server count cannot be negative.")

    bounded = max(minimum_servers, requested_servers)
    return min(maximum_servers, bounded)


def demonstrate_edge_cases() -> None:
    print_section("26. EDGE CASES AND EXCEPTIONS")

    test_cases = [
        (2, 0, 2, 10),
        (2, 100, 2, 10),
        (2, 1, 2, 10),
        (5, 6, 2, 10),
    ]

    for current, requested, minimum, maximum in test_cases:
        result = safe_scale_decision(
            current,
            requested,
            minimum,
            maximum,
        )

        print(
            f"Current={current}, requested={requested} -> "
            f"bounded decision={result}"
        )

    print("\nExamples of production edge cases:")
    print("  - Traffic spikes faster than autoscaling can react.")
    print("  - Maximum capacity is reached.")
    print("  - A dependency becomes unavailable.")
    print("  - A scaling event increases downstream database load.")
    print("  - Multiple autoscaling policies conflict.")
    print("  - A failed deployment scales unhealthy instances.")
    print("  - A cloud quota prevents additional resources.")
    print("  - A runaway workload causes unexpected spending.")
    print("  - Cross-region replication falls behind.")


# ============================================================================
# SECTION 27: DATABASE SCALING TRADE-OFF
# ============================================================================

@dataclass
class DatabaseCapacity:
    """Simple model showing why application scaling can hit database limits."""

    max_connections: int
    current_connections: int = 0

    def connect(self, connections: int) -> bool:
        if connections < 0:
            raise ValueError("Connections cannot be negative.")

        if self.current_connections + connections > self.max_connections:
            return False

        self.current_connections += connections
        return True


def demonstrate_database_bottleneck() -> None:
    print_section("27. SCALING BOTTLENECKS")

    database = DatabaseCapacity(max_connections=100)

    application_instances = 5
    connections_per_instance = 15

    successful = database.connect(
        application_instances * connections_per_instance
    )

    print(
        f"Initial application instances: {application_instances}"
    )
    print(
        f"Database connection allocation successful: {successful}"
    )
    print(
        f"Database connections in use: "
        f"{database.current_connections}"
    )

    more_instances = 4
    successful = database.connect(
        more_instances * connections_per_instance
    )

    print(
        f"Additional instances: {more_instances}"
    )
    print(
        f"Additional connections accepted: {successful}"
    )
    print(
        f"Database connections in use: "
        f"{database.current_connections}"
    )

    print(
        "\nApplication autoscaling does not guarantee system scalability. "
        "Databases, APIs, queues, network limits, quotas, and third-party "
        "dependencies can become bottlenecks."
    )


# ============================================================================
# SECTION 28: DISTRIBUTED SYSTEM CONSISTENCY
# ============================================================================

@dataclass
class Replica:
    """Simple replicated value."""

    name: str
    value: int = 0


def demonstrate_replication_tradeoff() -> None:
    print_section("28. REPLICATION AND CONSISTENCY TRADE-OFFS")

    replicas = [
        Replica("Region-A"),
        Replica("Region-B"),
        Replica("Region-C"),
    ]

    primary = replicas[0]
    primary.value = 100

    print("Immediately after primary update:")

    for replica in replicas:
        print(f"  {replica.name}: {replica.value}")

    # Simulate asynchronous replication.
    replicas[1].value = primary.value
    replicas[2].value = primary.value

    print("\nAfter asynchronous replication catches up:")

    for replica in replicas:
        print(f"  {replica.name}: {replica.value}")

    print(
        "\nDistributed replication introduces questions about consistency, "
        "replication lag, conflict resolution, ordering, availability, "
        "and network partitions."
    )


# ============================================================================
# SECTION 29: CLOUD MIGRATION BENEFITS
# ============================================================================

def demonstrate_migration_benefits() -> None:
    print_section("29. CLOUD MIGRATION BENEFITS")

    migration_dimensions = [
        (
            "Capacity",
            "Move from fixed hardware capacity toward configurable resources."
        ),
        (
            "Deployment",
            "Automate repeatable infrastructure and application deployment."
        ),
        (
            "Global access",
            "Place services in multiple geographic locations."
        ),
        (
            "Recovery",
            "Use geographically separated backups and recovery environments."
        ),
        (
            "Operations",
            "Use managed services and automation to reduce infrastructure work."
        ),
        (
            "Financial model",
            "Align infrastructure expenditure more closely with consumption."
        ),
    ]

    for dimension, benefit in migration_dimensions:
        print(f"{dimension:<18}: {benefit}")


# ============================================================================
# SECTION 30: ARCHITECTURE DECISION EXAMPLE
# ============================================================================

@dataclass
class ArchitectureDecision:
    """Evaluate a simplified architecture against requirements."""

    name: str
    monthly_cost: float
    rto_minutes: int
    rpo_minutes: int
    regions: int
    operational_complexity: int

    def score(self) -> float:
        """
        Compute a simple educational score.

        Lower cost, lower RTO/RPO, more regions, and lower complexity are
        desirable. This is not a production decision formula.
        """
        cost_component = max(0.0, 100 - self.monthly_cost / 100)
        recovery_component = max(
            0.0,
            100 - self.rto_minutes / 10 - self.rpo_minutes / 2,
        )
        geographic_component = min(100.0, self.regions * 30)
        complexity_component = max(
            0.0,
            100 - self.operational_complexity * 10,
        )

        return mean(
            [
                cost_component,
                recovery_component,
                geographic_component,
                complexity_component,
            ]
        )


def demonstrate_architecture_decision() -> None:
    print_section("30. ARCHITECTURE TRADE-OFF ANALYSIS")

    architectures = [
        ArchitectureDecision(
            "Single region",
            monthly_cost=2_000,
            rto_minutes=240,
            rpo_minutes=60,
            regions=1,
            operational_complexity=1,
        ),
        ArchitectureDecision(
            "Multi-zone",
            monthly_cost=4_000,
            rto_minutes=60,
            rpo_minutes=15,
            regions=1,
            operational_complexity=2,
        ),
        ArchitectureDecision(
            "Multi-region",
            monthly_cost=10_000,
            rto_minutes=15,
            rpo_minutes=5,
            regions=2,
            operational_complexity=4,
        ),
        ArchitectureDecision(
            "Active-active",
            monthly_cost=20_000,
            rto_minutes=5,
            rpo_minutes=0,
            regions=3,
            operational_complexity=5,
        ),
    ]

    for architecture in architectures:
        print(
            f"{architecture.name:<18} "
            f"cost=${architecture.monthly_cost:>8,.0f} "
            f"RTO={architecture.rto_minutes:>3}m "
            f"RPO={architecture.rpo_minutes:>3}m "
            f"regions={architecture.regions} "
            f"complexity={architecture.operational_complexity} "
            f"score={architecture.score():>6.2f}"
        )

    print(
        "\nA numerical architecture score is only an educational model. "
        "Production decisions must be driven by actual business requirements, "
        "risk tolerance, regulatory obligations, workload characteristics, "
        "and measured operational constraints."
    )


# ============================================================================
# SECTION 31: SLO-STYLE CHECK
# ============================================================================

@dataclass
class ServiceLevelObjective:
    """Simple SLO model."""

    target_availability: float
    observed_availability: float

    def meets_target(self) -> bool:
        return self.observed_availability >= self.target_availability


def demonstrate_slo() -> None:
    print_section("31. SERVICE LEVEL OBJECTIVES")

    objectives = [
        ServiceLevelObjective(99.9, 99.95),
        ServiceLevelObjective(99.99, 99.97),
        ServiceLevelObjective(99.5, 99.7),
    ]

    for objective in objectives:
        status = "PASS" if objective.meets_target() else "FAIL"
        print(
            f"Target={objective.target_availability:.2f}% "
            f"Observed={objective.observed_availability:.2f}% "
            f"{status}"
        )

    print(
        "\nAvailability targets should be connected to measurable service "
        "objectives and business impact rather than treated as isolated "
        "technical numbers."
    )


# ============================================================================
# SECTION 32: TESTING CLOUD RESILIENCE
# ============================================================================

class TestResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"


def run_resilience_test(
    healthy_capacity: int,
    demand: int,
    failed_capacity: int,
) -> TestResult:
    """Test whether remaining capacity can satisfy demand."""
    if min(healthy_capacity, demand, failed_capacity) < 0:
        raise ValueError("Capacity and demand cannot be negative.")

    remaining_capacity = healthy_capacity - failed_capacity

    return (
        TestResult.PASS
        if remaining_capacity >= demand
        else TestResult.FAIL
    )


def demonstrate_resilience_testing() -> None:
    print_section("32. RESILIENCE TESTING")

    tests = [
        ("One instance failure", 10_000, 7_000, 1_000),
        ("Two instance failure", 10_000, 7_000, 2_000),
        ("Major capacity failure", 10_000, 7_000, 5_000),
        ("Regional failure", 15_000, 7_000, 8_000),
    ]

    for name, capacity, demand, failed_capacity in tests:
        result = run_resilience_test(
            capacity,
            demand,
            failed_capacity,
        )

        print(f"{name:<25} {result.value}")

    print(
        "\nResilience must be tested. An architecture that looks redundant "
        "on a diagram may fail in practice because of configuration errors, "
        "dependency failures, quotas, data inconsistency, or untested "
        "recovery procedures."
    )


# ============================================================================
# SECTION 33: CHAOS-STYLE FAILURE SIMULATION
# ============================================================================

def random_failure_simulation(
    instances: int,
    failure_probability: float,
    required_instances: int,
    trials: int = 10_000,
    seed: int = 42,
) -> float:
    """
    Estimate probability of maintaining required capacity.

    Each instance independently fails with the given probability.
    """
    if instances <= 0:
        raise ValueError("Instances must be positive.")
    if not 0 <= failure_probability <= 1:
        raise ValueError("Failure probability must be between 0 and 1.")
    if not 0 <= required_instances <= instances:
        raise ValueError(
            "Required instances must be between zero and total instances."
        )
    if trials <= 0:
        raise ValueError("Trials must be positive.")

    random = Random(seed)
    successes = 0

    for _ in range(trials):
        healthy = sum(
            random.random() >= failure_probability
            for _ in range(instances)
        )

        if healthy >= required_instances:
            successes += 1

    return successes / trials


def demonstrate_failure_probability() -> None:
    print_section("33. FAILURE PROBABILITY SIMULATION")

    scenarios = [
        (5, 0.05, 3),
        (10, 0.05, 7),
        (10, 0.10, 7),
        (20, 0.10, 15),
    ]

    for instances, probability, required in scenarios:
        success_rate = random_failure_simulation(
            instances,
            probability,
            required,
        )

        print(
            f"Instances={instances:>2}, "
            f"failure probability={probability:>4.0%}, "
            f"required={required:>2} -> "
            f"capacity survival probability≈{success_rate:.2%}"
        )

    print(
        "\nRedundancy changes the probability that independent component "
        "failures cause service-level failure. Real cloud failure domains "
        "are not always independent, so correlated failures matter."
    )


# ============================================================================
# SECTION 34: CLOUD QUOTAS AND LIMITS
# ============================================================================

@dataclass
class CloudQuota:
    """Model a service quota."""

    resource: str
    limit: int
    used: int = 0

    def request(self, amount: int) -> bool:
        if amount < 0:
            raise ValueError("Requested amount cannot be negative.")

        if self.used + amount > self.limit:
            return False

        self.used += amount
        return True


def demonstrate_quotas() -> None:
    print_section("34. CLOUD QUOTAS AND RESOURCE LIMITS")

    quota = CloudQuota(
        resource="compute instances",
        limit=10,
    )

    for request in [4, 3, 2, 2]:
        accepted = quota.request(request)

        print(
            f"Request={request:>2}, "
            f"accepted={accepted}, "
            f"used={quota.used}/{quota.limit}"
        )

    print(
        "\nElasticity is constrained by quotas, regional capacity, service "
        "limits, account limits, network limits, and application dependencies."
    )


# ============================================================================
# SECTION 35: DATA TRANSFER COSTS
# ============================================================================

def data_transfer_cost(
    gigabytes: float,
    price_per_gb: float,
) -> float:
    """Calculate simplified data-transfer cost."""
    if gigabytes < 0 or price_per_gb < 0:
        raise ValueError("Values cannot be negative.")

    return gigabytes * price_per_gb


def demonstrate_network_cost() -> None:
    print_section("35. NETWORK AND DATA TRANSFER COSTS")

    traffic = [
        ("Low traffic", 100),
        ("Medium traffic", 10_000),
        ("High traffic", 500_000),
    ]

    price = 0.02

    for description, gigabytes in traffic:
        cost = data_transfer_cost(gigabytes, price)
        print(
            f"{description:<15} "
            f"{gigabytes:>10,.0f} GB -> "
            f"${cost:>10,.2f}"
        )

    print(
        "\nGlobal architectures can improve latency and resilience but may "
        "increase cross-region and cross-service network transfer costs."
    )


# ============================================================================
# SECTION 36: STORAGE LIFECYCLE
# ============================================================================

@dataclass
class StoredObject:
    """Storage object with age and size."""

    name: str
    age_days: int
    size_gb: float


def storage_lifecycle_cost(
    objects: Sequence[StoredObject],
    standard_price: float,
    archive_price: float,
    archive_after_days: int,
) -> float:
    """Estimate monthly storage cost using a simple lifecycle policy."""
    if standard_price < 0 or archive_price < 0:
        raise ValueError("Prices cannot be negative.")
    if archive_after_days < 0:
        raise ValueError("Archive threshold cannot be negative.")

    total = 0.0

    for obj in objects:
        price = (
            archive_price
            if obj.age_days >= archive_after_days
            else standard_price
        )

        total += obj.size_gb * price

    return total


def demonstrate_storage_optimization() -> None:
    print_section("36. STORAGE LIFECYCLE OPTIMIZATION")

    objects = [
        StoredObject("recent-report", 10, 100),
        StoredObject("old-report", 180, 300),
        StoredObject("archive-data", 800, 1_000),
    ]

    standard_price = 0.023
    archive_price = 0.004

    monthly_cost = storage_lifecycle_cost(
        objects,
        standard_price,
        archive_price,
        archive_after_days=90,
    )

    print(
        f"Modeled monthly storage cost with lifecycle policy: "
        f"${monthly_cost:.2f}"
    )

    print(
        "\nStorage lifecycle policies can reduce costs by moving infrequently "
        "accessed data to cheaper storage tiers, subject to access latency, "
        "retrieval costs, retention requirements, and durability needs."
    )


# ============================================================================
# SECTION 37: PERFORMANCE CONSIDERATIONS
# ============================================================================

def throughput_capacity(
    workers: int,
    throughput_per_worker: float,
) -> float:
    """Calculate theoretical aggregate throughput."""
    if workers < 0:
        raise ValueError("Workers cannot be negative.")
    if throughput_per_worker < 0:
        raise ValueError("Throughput cannot be negative.")

    return workers * throughput_per_worker


def demonstrate_performance() -> None:
    print_section("37. PERFORMANCE CONSIDERATIONS")

    workers = [1, 2, 4, 8, 16]

    for count in workers:
        capacity = throughput_capacity(
            workers=count,
            throughput_per_worker=125,
        )

        print(
            f"Workers={count:>2} -> "
            f"theoretical throughput={capacity:>6.0f} operations/s"
        )

    print(
        "\nReal systems rarely scale perfectly linearly. Coordination, "
        "network latency, locking, database contention, serialization, "
        "cache behavior, and downstream bottlenecks can reduce scaling efficiency."
    )


# ============================================================================
# SECTION 38: SCALING EFFICIENCY
# ============================================================================

def scaling_efficiency(
    baseline_workers: int,
    baseline_throughput: float,
    scaled_workers: int,
    scaled_throughput: float,
) -> float:
    """
    Calculate scaling efficiency.

    Perfect linear scaling would produce 100%.
    """
    if baseline_workers <= 0 or scaled_workers <= 0:
        raise ValueError("Worker counts must be positive.")
    if baseline_throughput <= 0 or scaled_throughput < 0:
        raise ValueError("Throughput values are invalid.")

    ideal_throughput = (
        baseline_throughput
        * scaled_workers
        / baseline_workers
    )

    return scaled_throughput / ideal_throughput


def demonstrate_scaling_efficiency() -> None:
    print_section("38. SCALING EFFICIENCY")

    efficiency = scaling_efficiency(
        baseline_workers=2,
        baseline_throughput=1_000,
        scaled_workers=8,
        scaled_throughput=3_000,
    )

    print(f"Scaling efficiency: {efficiency:.1%}")

    print(
        "The modeled system achieves only 75% of ideal linear scaling "
        "because the 8-worker system would ideally produce 4,000 operations/s."
    )


# ============================================================================
# SECTION 39: CLOUD-NATIVE ARCHITECTURAL CHARACTERISTICS
# ============================================================================

def explain_cloud_native_characteristics() -> None:
    print_section("39. CLOUD-NATIVE DESIGN CHARACTERISTICS")

    characteristics = {
        "Stateless application instances": (
            "Make horizontal scaling and replacement easier."
        ),
        "Externalized state": (
            "Store persistent state in appropriate databases or storage systems."
        ),
        "Automated deployment": (
            "Reduce manual deployment inconsistency."
        ),
        "Health checks": (
            "Allow unhealthy instances to be detected and replaced."
        ),
        "Observability": (
            "Expose metrics, logs, traces, and meaningful service indicators."
        ),
        "Failure isolation": (
            "Limit the blast radius of component failures."
        ),
        "Immutable deployment patterns": (
            "Prefer replacing known infrastructure versions over uncontrolled "
            "in-place modification."
        ),
        "Horizontal scaling": (
            "Increase capacity by adding instances or workers."
        ),
    }

    for characteristic, explanation in characteristics.items():
        print(f"{characteristic:<30}: {explanation}")


# ============================================================================
# SECTION 40: HEALTH CHECKS
# ============================================================================

@dataclass
class ApplicationInstance:
    """Instance used to demonstrate health-based traffic routing."""

    name: str
    healthy: bool
    capacity: int


def select_healthy_instances(
    instances: Sequence[ApplicationInstance],
) -> List[ApplicationInstance]:
    """Return only healthy instances."""
    return [
        instance
        for instance in instances
        if instance.healthy
    ]


def demonstrate_health_checks() -> None:
    print_section("40. HEALTH CHECKS")

    instances = [
        ApplicationInstance("api-1", True, 1_000),
        ApplicationInstance("api-2", True, 1_000),
        ApplicationInstance("api-3", False, 1_000),
        ApplicationInstance("api-4", True, 1_000),
    ]

    healthy = select_healthy_instances(instances)

    print("Instances receiving traffic:")

    for instance in healthy:
        print(f"  {instance.name}")

    print(
        "\nHealth checks help prevent known-unhealthy instances from "
        "receiving traffic, but poorly designed health checks can also "
        "remove healthy capacity or fail to detect dependency failures."
    )


# ============================================================================
# SECTION 41: GRACEFUL DEGRADATION
# ============================================================================

def serve_request(
    primary_available: bool,
    cache_available: bool,
) -> str:
    """
    Demonstrate graceful degradation.

    The service provides a fallback response when the primary dependency
    is unavailable.
    """
    if primary_available:
        return "Fresh response from primary service."

    if cache_available:
        return "Stale-but-usable response from cache."

    return "Minimal fallback response."


def demonstrate_graceful_degradation() -> None:
    print_section("41. GRACEFUL DEGRADATION")

    scenarios = [
        (True, True),
        (False, True),
        (False, False),
    ]

    for primary, cache in scenarios:
        print(
            f"Primary={primary}, Cache={cache} -> "
            f"{serve_request(primary, cache)}"
        )

    print(
        "\nAvailability can sometimes be improved by deliberately reducing "
        "functionality instead of allowing the entire service to fail."
    )


# ============================================================================
# SECTION 42: CLOUD BENEFITS VS TRADE-OFFS
# ============================================================================

def demonstrate_benefits_and_tradeoffs() -> None:
    print_section("42. BENEFITS AND TRADE-OFFS")

    table = [
        (
            "Scalability",
            "Handle larger workloads",
            "Architecture may become distributed and complex",
        ),
        (
            "Elasticity",
            "Match capacity to changing demand",
            "Autoscaling can react too slowly or increase costs",
        ),
        (
            "Availability",
            "Reduce downtime with redundancy",
            "Redundancy costs money and adds complexity",
        ),
        (
            "Global infrastructure",
            "Reduce latency and geographic risk",
            "Cross-region operations and data consistency are difficult",
        ),
        (
            "Cost optimization",
            "Pay closer to actual usage",
            "Poor governance can cause cloud waste",
        ),
        (
            "Automation",
            "Reduce manual operational effort",
            "Automation errors can operate at large scale",
        ),
        (
            "Disaster recovery",
            "Recover from major failures",
            "Recovery infrastructure and testing have ongoing costs",
        ),
    ]

    for benefit, advantage, tradeoff in table:
        print(f"\n{benefit}")
        print(f"  Advantage:  {advantage}")
        print(f"  Trade-off:  {tradeoff}")


# ============================================================================
# SECTION 43: COMMON MISTAKES
# ============================================================================

def demonstrate_common_mistakes() -> None:
    print_section("43. COMMON CLOUD COMPUTING MISTAKES")

    mistakes = [
        (
            "Assuming cloud automatically means cheaper",
            "Measure actual utilization, architecture cost, and operational cost.",
        ),
        (
            "Scaling only the application tier",
            "Identify database, network, queue, and dependency bottlenecks.",
        ),
        (
            "Treating multi-region as automatically resilient",
            "Test actual failover and verify data and dependency behavior.",
        ),
        (
            "Ignoring quotas",
            "Understand service limits before designing autoscaling.",
        ),
        (
            "Ignoring data-transfer charges",
            "Model network flows and cross-region traffic.",
        ),
        (
            "Creating backups without restore testing",
            "Regularly perform controlled restoration tests.",
        ),
        (
            "Using one autoscaling metric",
            "Combine infrastructure, application, and business signals.",
        ),
        (
            "Automating without guardrails",
            "Use limits, approvals where appropriate, policies, and monitoring.",
        ),
        (
            "Assuming managed services remove all responsibility",
            "Retain ownership of data, access control, configuration, and usage.",
        ),
        (
            "Failing to test failure scenarios",
            "Exercise instance, zone, region, dependency, and recovery failures.",
        ),
    ]

    for mistake, correction in mistakes:
        print(f"\nMistake:    {mistake}")
        print(f"Better:     {correction}")


# ============================================================================
# SECTION 44: PRODUCTION CHECKLIST
# ============================================================================

def print_production_checklist() -> None:
    print_section("44. PRODUCTION DESIGN CHECKLIST")

    checklist = [
        "Define availability objectives.",
        "Define RTO and RPO.",
        "Identify workload traffic patterns.",
        "Determine scaling dimensions and bottlenecks.",
        "Set minimum and maximum autoscaling boundaries.",
        "Implement meaningful health checks.",
        "Use redundancy across appropriate failure domains.",
        "Protect persistent data with tested backups.",
        "Design and test disaster recovery.",
        "Monitor cost and resource utilization.",
        "Apply least-privilege access control.",
        "Encrypt sensitive data appropriately.",
        "Protect secrets.",
        "Monitor logs, metrics, traces, latency, and errors.",
        "Understand cloud quotas and service limits.",
        "Model network and data-transfer costs.",
        "Automate repeatable infrastructure operations.",
        "Test recovery procedures regularly.",
        "Document dependencies and failure modes.",
        "Use controlled deployment and rollback procedures.",
    ]

    for number, item in enumerate(checklist, start=1):
        print(f"{number:>2}. {item}")


# ============================================================================
# SECTION 45: INTEGRATED CLOUD ARCHITECTURE SIMULATION
# ============================================================================

@dataclass
class CloudApplication:
    """
    Integrated model combining multiple cloud concepts.

    This is an educational simulation rather than a cloud-provider SDK.
    """

    name: str
    cluster: ElasticCluster
    database: DatabaseCapacity
    regions: List[RegionCapacity]
    queue: QueueSystem

    def handle_traffic(self, request_rate: int) -> Dict[str, float]:
        """Scale application capacity and report resulting metrics."""
        self.cluster.autoscale(request_rate)

        capacity = self.cluster.capacity

        return {
            "request_rate": request_rate,
            "capacity": capacity,
            "utilization": self.cluster.utilization(request_rate),
            "healthy_regions": sum(
                region.healthy
                for region in self.regions
            ),
        }

    def fail_region(self, region_name: str) -> None:
        """Simulate a regional failure."""
        for region in self.regions:
            if region.name == region_name:
                region.healthy = False
                return

        raise KeyError(f"Region not found: {region_name}")


def demonstrate_integrated_architecture() -> None:
    print_section("45. INTEGRATED CLOUD ARCHITECTURE SIMULATION")

    application = CloudApplication(
        name="order-service",
        cluster=ElasticCluster(
            server_capacity=1_000,
            minimum_servers=2,
            maximum_servers=12,
        ),
        database=DatabaseCapacity(
            max_connections=200,
        ),
        regions=[
            RegionCapacity("Region-A", 5_000),
            RegionCapacity("Region-B", 5_000),
            RegionCapacity("Region-C", 5_000),
        ],
        queue=QueueSystem(),
    )

    traffic = [1_000, 2_000, 4_000, 8_000, 3_000]

    for request_rate in traffic:
        result = application.handle_traffic(request_rate)

        print(
            f"Traffic={result['request_rate']:>5} "
            f"capacity={result['capacity']:>5} "
            f"utilization={result['utilization']:.1%} "
            f"healthy_regions={result['healthy_regions']}"
        )

    application.fail_region("Region-A")

    print(
        "\nAfter simulated Region-A failure:"
    )

    healthy_capacity = total_healthy_capacity(application.regions)

    print(f"Remaining regional capacity: {healthy_capacity}")

    print(
        "\nThis integrated model demonstrates the relationship between "
        "elasticity, redundancy, global infrastructure, and capacity. "
        "Cloud benefits are strongest when the application architecture "
        "is designed to use them correctly."
    )


# ============================================================================
# SECTION 46: CONCEPTUAL RELATIONSHIPS
# ============================================================================

def explain_concept_relationships() -> None:
    print_section("46. RELATIONSHIPS BETWEEN CLOUD BENEFITS")

    relationships = [
        (
            "Scalability + Load balancing",
            "Makes additional compute instances usable under increased demand.",
        ),
        (
            "Elasticity + Autoscaling",
            "Allows resource count to change automatically as workload changes.",
        ),
        (
            "Availability + Redundancy",
            "Reduces the probability that one component failure causes service outage.",
        ),
        (
            "Global infrastructure + Multi-region",
            "Supports geographic distribution and regional failure resilience.",
        ),
        (
            "Cost optimization + Elasticity",
            "Allows unused capacity to be reduced when demand falls.",
        ),
        (
            "Automation + Infrastructure as Code",
            "Makes infrastructure provisioning repeatable and consistent.",
        ),
        (
            "Disaster recovery + Backups",
            "Provides a mechanism for restoring data after disruptive events.",
        ),
        (
            "Observability + Autoscaling",
            "Provides signals that can drive scaling decisions.",
        ),
        (
            "Security + Automation",
            "Allows security controls to be applied consistently at scale.",
        ),
    ]

    for relationship, explanation in relationships:
        print(f"\n{relationship}")
        print(f"  {explanation}")


# ============================================================================
# SECTION 47: ADVANCED DESIGN PRINCIPLES
# ============================================================================

def explain_advanced_design_principles() -> None:
    print_section("47. ADVANCED DESIGN PRINCIPLES")

    principles = [
        (
            "Design for failure",
            "Assume components can fail and create controlled recovery paths."
        ),
        (
            "Avoid single points of failure",
            "Identify components whose failure can stop the service."
        ),
        (
            "Separate failure domains",
            "Distribute replicas so one infrastructure failure does not remove all capacity."
        ),
        (
            "Use bounded elasticity",
            "Define minimum and maximum resource limits."
        ),
        (
            "Scale the bottleneck",
            "Find the constrained resource rather than scaling unrelated components."
        ),
        (
            "Make recovery measurable",
            "Measure actual recovery time and data restoration capability."
        ),
        (
            "Automate with guardrails",
            "Prevent automation from producing uncontrolled capacity or cost."
        ),
        (
            "Treat cost as an architectural property",
            "Network, storage, compute, replication, and managed-service choices all affect cost."
        ),
        (
            "Test assumptions",
            "Use load tests, recovery tests, and failure simulations to validate architecture."
        ),
    ]

    for principle, explanation in principles:
        print(f"\n{principle}")
        print(f"  {explanation}")


# ============================================================================
# SECTION 48: KNOWLEDGE CHECKS
# ============================================================================

def run_knowledge_checks() -> None:
    print_section("48. KNOWLEDGE CHECKS")

    questions = [
        (
            "Which concept describes adding more application instances?",
            "Horizontal scaling",
        ),
        (
            "Which concept describes automatically adding and removing capacity?",
            "Elasticity",
        ),
        (
            "What does RTO measure?",
            "Maximum acceptable recovery time",
        ),
        (
            "What does RPO measure?",
            "Maximum acceptable recovery-point/data-loss window",
        ),
        (
            "Why use multiple availability zones?",
            "To reduce the impact of localized infrastructure failures",
        ),
        (
            "Can cloud computing automatically guarantee lower cost?",
            "No",
        ),
        (
            "Why are backups insufficient without restore tests?",
            "A backup may exist but still be unusable or incomplete",
        ),
        (
            "What can constrain application autoscaling?",
            "Databases, quotas, networks, dependencies, and other bottlenecks",
        ),
    ]

    for number, (question, answer) in enumerate(questions, start=1):
        print(f"{number}. {question}")
        print(f"   Answer: {answer}")


# ============================================================================
# SECTION 49: MAIN PROGRAM
# ============================================================================

def main() -> None:
    """
    Run all demonstrations in logical learning order.

    The sequence progresses from definitions to scaling, elasticity,
    availability, global infrastructure, cost, automation, disaster
    recovery, security, observability, resilience, and integrated design.
    """

    explain_basic_terms()
    demonstrate_scalability()
    demonstrate_elasticity()
    demonstrate_autoscaling_policy()
    demonstrate_load_balancing()
    demonstrate_availability()
    demonstrate_fault_tolerance()
    demonstrate_global_infrastructure()
    demonstrate_cost_optimization()
    compare_capex_opex()
    demonstrate_queue_based_scaling()
    demonstrate_automation()
    demonstrate_infrastructure_as_code()
    demonstrate_disaster_recovery()
    demonstrate_backup_restore()
    demonstrate_rpo()
    demonstrate_rto()
    demonstrate_multi_region_resilience()
    demonstrate_overprovisioning()
    demonstrate_usage_based_computing()
    demonstrate_benefit_scorecard()
    explain_service_models()
    demonstrate_managed_services()
    demonstrate_security()
    demonstrate_observability()
    demonstrate_edge_cases()
    demonstrate_database_bottleneck()
    demonstrate_replication_tradeoff()
    demonstrate_migration_benefits()
    demonstrate_architecture_decision()
    demonstrate_slo()
    demonstrate_resilience_testing()
    demonstrate_failure_probability()
    demonstrate_quotas()
    demonstrate_network_cost()
    demonstrate_storage_optimization()
    demonstrate_performance()
    demonstrate_scaling_efficiency()
    explain_cloud_native_characteristics()
    demonstrate_health_checks()
    demonstrate_graceful_degradation()
    demonstrate_benefits_and_tradeoffs()
    demonstrate_common_mistakes()
    print_production_checklist()
    demonstrate_integrated_architecture()
    explain_concept_relationships()
    explain_advanced_design_principles()
    run_knowledge_checks()

    print_section("END OF CLOUD COMPUTING BENEFITS STUDY SCRIPT")
    print(
        "The script has demonstrated cloud scalability, elasticity, "
        "availability, global infrastructure, cost optimization, "
        "automation, resilience, and disaster recovery through executable "
        "Python models."
    )


if __name__ == "__main__":
    main()
