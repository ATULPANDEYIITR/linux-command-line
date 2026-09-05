"""
CLOUD DEPLOYMENT MODELS
=======================

A self-contained study and demonstration script covering:

1. Cloud computing fundamentals
2. Public cloud
3. Private cloud
4. Hybrid cloud
5. Multi-cloud
6. Community cloud
7. Deployment-model comparison
8. Service models: IaaS, PaaS, SaaS
9. Virtualization, containers, orchestration, and networking
10. Identity, security, compliance, and governance
11. Availability, resilience, scalability, and disaster recovery
12. Cost and operational considerations
13. Workload-placement decisions
14. Architecture simulations
15. Migration scenarios
16. Advanced design considerations
17. Validation and testing

The examples use only Python's standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import math
import random
import statistics
import unittest


# ============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# ============================================================================

class DeploymentModel(Enum):
    """Major cloud deployment models."""

    PUBLIC = "Public Cloud"
    PRIVATE = "Private Cloud"
    HYBRID = "Hybrid Cloud"
    MULTI_CLOUD = "Multi-Cloud"
    COMMUNITY = "Community Cloud"


class ServiceModel(Enum):
    """Common cloud service-delivery models."""

    IAAS = "Infrastructure as a Service"
    PAAS = "Platform as a Service"
    SAAS = "Software as a Service"


class WorkloadType(Enum):
    """Representative workload categories."""

    WEB_APPLICATION = "Web Application"
    DATABASE = "Database"
    AI_TRAINING = "AI/ML Training"
    REGULATED_DATA = "Regulated Data"
    BATCH_PROCESSING = "Batch Processing"
    DISASTER_RECOVERY = "Disaster Recovery"
    INTERNAL_APPLICATION = "Internal Application"


class RiskLevel(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class CloudProvider:
    """
    Represents a generic cloud provider.

    The model deliberately avoids provider-specific implementation details so
    that the architectural concepts remain applicable across providers.
    """

    name: str
    regions: int
    availability_zones_per_region: int
    compute_unit_cost: float
    storage_unit_cost: float
    network_unit_cost: float
    managed_services: Set[str] = field(default_factory=set)

    def estimated_monthly_cost(
        self,
        compute_units: float,
        storage_units: float,
        network_units: float,
    ) -> float:
        """Estimate cost using simplified unit prices."""
        return (
            compute_units * self.compute_unit_cost
            + storage_units * self.storage_unit_cost
            + network_units * self.network_unit_cost
        )


@dataclass
class Workload:
    """Describes a workload that must be placed on one or more environments."""

    name: str
    workload_type: WorkloadType
    monthly_compute_units: float
    monthly_storage_units: float
    monthly_network_units: float
    data_sensitivity: RiskLevel
    availability_target: float
    portability_requirement: float
    latency_sensitive: bool = False
    regulatory_requirements: Set[str] = field(default_factory=set)
    preferred_providers: Set[str] = field(default_factory=set)

    def validate(self) -> None:
        """Validate workload assumptions before architectural decisions."""
        if self.monthly_compute_units < 0:
            raise ValueError("Compute requirements cannot be negative.")
        if self.monthly_storage_units < 0:
            raise ValueError("Storage requirements cannot be negative.")
        if self.monthly_network_units < 0:
            raise ValueError("Network requirements cannot be negative.")
        if not 0 <= self.availability_target <= 100:
            raise ValueError("Availability target must be between 0 and 100.")
        if not 0 <= self.portability_requirement <= 100:
            raise ValueError("Portability requirement must be between 0 and 100.")


# ============================================================================
# 2. CORE CLOUD CONCEPTS
# ============================================================================

def explain_cloud_computing() -> None:
    """
    Demonstrate the basic meaning of cloud computing.

    Cloud computing is a model for obtaining computing resources over a
    network with characteristics such as on-demand provisioning, elasticity,
    measured usage, and shared infrastructure.
    """

    characteristics = {
        "On-demand self-service": "Resources can be provisioned without manual infrastructure procurement.",
        "Broad network access": "Services are reachable through standard network mechanisms.",
        "Resource pooling": "Provider infrastructure is shared among multiple consumers.",
        "Rapid elasticity": "Capacity can expand or contract as demand changes.",
        "Measured service": "Usage can be monitored and charged according to consumption.",
    }

    print("\n=== Cloud Computing Fundamentals ===")
    for name, description in characteristics.items():
        print(f"{name}: {description}")


def explain_shared_responsibility() -> None:
    """
    Illustrate the shared-responsibility principle.

    Responsibility changes depending on the service model. A customer normally
    controls more of the stack in IaaS than in SaaS.
    """

    responsibility = {
        "IaaS": [
            "Customer applications",
            "Customer data",
            "Guest operating system",
            "Network configuration",
            "Identity and access configuration",
        ],
        "PaaS": [
            "Customer applications",
            "Customer data",
            "Application configuration",
            "Identity and access configuration",
        ],
        "SaaS": [
            "Customer data",
            "Users and identities",
            "Application-level configuration",
            "Access policies",
        ],
    }

    print("\n=== Shared Responsibility ===")
    for model, responsibilities in responsibility.items():
        print(f"\n{model} customer responsibilities:")
        for item in responsibilities:
            print(f"  - {item}")


# ============================================================================
# 3. SERVICE MODELS
# ============================================================================

def compare_service_models() -> None:
    """
    Compare IaaS, PaaS, and SaaS.

    IaaS exposes relatively low-level infrastructure.
    PaaS abstracts much of the infrastructure and runtime.
    SaaS delivers a complete application to end users.
    """

    models = {
        ServiceModel.IAAS: {
            "customer_control": "High",
            "provider_manages": "Physical infrastructure and virtualization layer",
            "customer_typically_manages": "Operating system, applications, data, configurations",
            "example_use": "Custom application on virtual machines",
        },
        ServiceModel.PAAS: {
            "customer_control": "Medium",
            "provider_manages": "Infrastructure, operating system, runtime platform",
            "customer_typically_manages": "Application code and data",
            "example_use": "Deploying an application without managing servers",
        },
        ServiceModel.SAAS: {
            "customer_control": "Low",
            "provider_manages": "Application and underlying platform",
            "customer_typically_manages": "Users, data, configuration, access",
            "example_use": "Using a hosted business application",
        },
    }

    print("\n=== Service Model Comparison ===")
    for model, details in models.items():
        print(f"\n{model.value}")
        for key, value in details.items():
            print(f"  {key}: {value}")


# ============================================================================
# 4. PUBLIC CLOUD
# ============================================================================

def public_cloud_example() -> Dict[str, object]:
    """
    Model a public-cloud architecture.

    Public cloud infrastructure is owned and operated by a cloud provider and
    shared by multiple customers using logical isolation.
    """

    architecture = {
        "ownership": "Third-party cloud provider",
        "infrastructure": "Provider-owned shared infrastructure",
        "access": "Internet/private network connectivity",
        "scaling": "Highly elastic",
        "capital_expense": "Usually lower",
        "operational_model": "Provider-managed physical infrastructure",
        "strengths": [
            "Rapid provisioning",
            "Large resource pool",
            "Global reach",
            "Managed services",
            "Elastic capacity",
        ],
        "limitations": [
            "Ongoing operational expense",
            "Provider dependency",
            "Potential data-residency constraints",
            "Shared infrastructure concerns",
        ],
    }

    print("\n=== Public Cloud ===")
    for key, value in architecture.items():
        print(f"{key}: {value}")

    return architecture


# ============================================================================
# 5. PRIVATE CLOUD
# ============================================================================

def private_cloud_example() -> Dict[str, object]:
    """
    Model a private-cloud environment.

    A private cloud is dedicated to one organization. It may be operated by
    the organization itself or by a third party.
    """

    architecture = {
        "ownership": "Single organization or dedicated operator",
        "infrastructure": "Dedicated environment",
        "access": "Restricted organizational access",
        "scaling": "Constrained by dedicated capacity unless expanded",
        "capital_expense": "Potentially high",
        "control": "High",
        "typical_drivers": [
            "Strict regulatory requirements",
            "Legacy integration",
            "Special hardware requirements",
            "Data sovereignty",
            "Highly customized infrastructure",
        ],
    }

    print("\n=== Private Cloud ===")
    for key, value in architecture.items():
        print(f"{key}: {value}")

    return architecture


# ============================================================================
# 6. HYBRID CLOUD
# ============================================================================

@dataclass
class HybridArchitecture:
    """
    Represents an architecture combining private and public environments.

    Hybrid architecture becomes useful when workloads or data need to remain
    in a private environment while other workloads benefit from public-cloud
    elasticity.
    """

    private_workloads: List[str]
    public_workloads: List[str]
    connectivity: str
    identity_integration: bool
    centralized_monitoring: bool

    def validate(self) -> None:
        if not self.connectivity:
            raise ValueError("Hybrid architecture requires a connectivity mechanism.")

        if not self.identity_integration:
            raise ValueError(
                "Production hybrid environments should integrate identity "
                "and access controls."
            )


def hybrid_cloud_example() -> HybridArchitecture:
    architecture = HybridArchitecture(
        private_workloads=[
            "Highly sensitive customer records",
            "Legacy database requiring specialized connectivity",
        ],
        public_workloads=[
            "Web frontend",
            "Elastic analytics",
            "Public API",
        ],
        connectivity="Encrypted private connectivity",
        identity_integration=True,
        centralized_monitoring=True,
    )

    architecture.validate()

    print("\n=== Hybrid Cloud ===")
    print(f"Private workloads: {architecture.private_workloads}")
    print(f"Public workloads: {architecture.public_workloads}")
    print(f"Connectivity: {architecture.connectivity}")
    print(f"Identity integration: {architecture.identity_integration}")
    print(f"Centralized monitoring: {architecture.centralized_monitoring}")

    return architecture


# ============================================================================
# 7. MULTI-CLOUD
# ============================================================================

@dataclass
class MultiCloudArchitecture:
    """
    Represents deliberate use of multiple public-cloud providers.

    Multi-cloud is not automatically the same as hybrid cloud. Hybrid cloud
    combines distinct environments such as private and public infrastructure.
    Multi-cloud primarily refers to using multiple cloud providers.
    """

    providers: List[CloudProvider]
    workload_distribution: Dict[str, List[str]]

    def provider_count(self) -> int:
        return len(self.providers)

    def is_multi_cloud(self) -> bool:
        return self.provider_count() >= 2

    def validate(self) -> None:
        if not self.is_multi_cloud():
            raise ValueError("At least two providers are required for multi-cloud.")


def multi_cloud_example() -> MultiCloudArchitecture:
    provider_a = CloudProvider(
        name="Provider-A",
        regions=30,
        availability_zones_per_region=3,
        compute_unit_cost=0.10,
        storage_unit_cost=0.02,
        network_unit_cost=0.01,
        managed_services={"database", "queue", "object-storage"},
    )

    provider_b = CloudProvider(
        name="Provider-B",
        regions=25,
        availability_zones_per_region=3,
        compute_unit_cost=0.11,
        storage_unit_cost=0.018,
        network_unit_cost=0.012,
        managed_services={"database", "container-platform", "object-storage"},
    )

    architecture = MultiCloudArchitecture(
        providers=[provider_a, provider_b],
        workload_distribution={
            "Provider-A": ["Customer API", "Analytics"],
            "Provider-B": ["Backup", "Secondary API"],
        },
    )

    architecture.validate()

    print("\n=== Multi-Cloud ===")
    print(f"Providers: {[provider.name for provider in architecture.providers]}")
    print(f"Distribution: {architecture.workload_distribution}")

    return architecture


# ============================================================================
# 8. COMMUNITY CLOUD
# ============================================================================

def community_cloud_example() -> Dict[str, object]:
    """
    Model a community cloud.

    A community cloud serves organizations sharing common requirements such as
    regulatory, security, mission, or policy requirements.
    """

    architecture = {
        "participants": [
            "Government agencies",
            "Healthcare organizations",
            "Research institutions",
        ],
        "shared_requirements": [
            "Common compliance controls",
            "Controlled data access",
            "Common security policies",
            "Shared governance requirements",
        ],
        "key_advantage": "Shared infrastructure aligned to common requirements",
        "key_challenge": "Governance among multiple participating organizations",
    }

    print("\n=== Community Cloud ===")
    for key, value in architecture.items():
        print(f"{key}: {value}")

    return architecture


# ============================================================================
# 9. DEPLOYMENT MODEL COMPARISON
# ============================================================================

def deployment_model_matrix() -> List[Dict[str, str]]:
    """
    Create a conceptual comparison of the five deployment models.

    The ratings are educational abstractions rather than universal guarantees.
    """

    matrix = [
        {
            "model": "Public",
            "ownership": "Provider",
            "resource_sharing": "Multi-tenant",
            "control": "Medium",
            "elasticity": "High",
            "typical_cost_profile": "Usage-based",
            "common_use": "General scalable workloads",
        },
        {
            "model": "Private",
            "ownership": "Single organization",
            "resource_sharing": "Dedicated",
            "control": "High",
            "elasticity": "Medium",
            "typical_cost_profile": "Infrastructure-heavy",
            "common_use": "Sensitive or customized workloads",
        },
        {
            "model": "Hybrid",
            "ownership": "Mixed",
            "resource_sharing": "Mixed",
            "control": "High to medium",
            "elasticity": "High",
            "typical_cost_profile": "Mixed",
            "common_use": "Workload/data placement across environments",
        },
        {
            "model": "Multi-cloud",
            "ownership": "Multiple providers",
            "resource_sharing": "Provider-dependent",
            "control": "Medium",
            "elasticity": "High",
            "typical_cost_profile": "Multiple usage models",
            "common_use": "Provider diversification or capability selection",
        },
        {
            "model": "Community",
            "ownership": "Shared community",
            "resource_sharing": "Community-specific",
            "control": "Shared governance",
            "elasticity": "Variable",
            "typical_cost_profile": "Shared",
            "common_use": "Organizations with common requirements",
        },
    ]

    print("\n=== Deployment Model Matrix ===")
    for row in matrix:
        print("\n" + row["model"])
        for key, value in row.items():
            if key != "model":
                print(f"  {key}: {value}")

    return matrix


# ============================================================================
# 10. VIRTUALIZATION
# ============================================================================

@dataclass
class VirtualMachine:
    """A simplified virtual machine representation."""

    name: str
    vcpus: int
    memory_gb: int
    storage_gb: int

    def validate(self) -> None:
        if self.vcpus <= 0:
            raise ValueError("A VM must have at least one vCPU.")
        if self.memory_gb <= 0:
            raise ValueError("VM memory must be positive.")
        if self.storage_gb < 0:
            raise ValueError("VM storage cannot be negative.")


def demonstrate_virtualization() -> None:
    """
    Demonstrate the abstraction provided by virtualization.

    A hypervisor allows multiple virtual machines to share physical resources
    while maintaining logical isolation between guests.
    """

    machines = [
        VirtualMachine("web-01", 2, 4, 50),
        VirtualMachine("api-01", 4, 8, 80),
        VirtualMachine("database-01", 8, 32, 500),
    ]

    print("\n=== Virtualization ===")
    for machine in machines:
        machine.validate()
        print(
            f"{machine.name}: "
            f"{machine.vcpus} vCPU, "
            f"{machine.memory_gb} GB RAM, "
            f"{machine.storage_gb} GB storage"
        )


# ============================================================================
# 11. CONTAINERS AND ORCHESTRATION
# ============================================================================

@dataclass
class Container:
    """A simplified container model."""

    name: str
    image: str
    cpu_limit: float
    memory_limit_mb: int

    def validate(self) -> None:
        if not self.image:
            raise ValueError("Container image cannot be empty.")
        if self.cpu_limit <= 0:
            raise ValueError("CPU limit must be positive.")
        if self.memory_limit_mb <= 0:
            raise ValueError("Memory limit must be positive.")


@dataclass
class ContainerCluster:
    """Simplified orchestration cluster."""

    name: str
    nodes: int
    containers: List[Container]

    def total_cpu_limit(self) -> float:
        return sum(container.cpu_limit for container in self.containers)

    def total_memory_limit(self) -> int:
        return sum(container.memory_limit_mb for container in self.containers)

    def validate(self) -> None:
        if self.nodes <= 0:
            raise ValueError("Cluster must contain at least one node.")
        for container in self.containers:
            container.validate()


def demonstrate_containers() -> None:
    cluster = ContainerCluster(
        name="application-cluster",
        nodes=3,
        containers=[
            Container("frontend", "frontend:v1", 0.5, 512),
            Container("api", "api:v3", 1.0, 1024),
            Container("worker", "worker:v2", 1.5, 2048),
        ],
    )

    cluster.validate()

    print("\n=== Containers and Orchestration ===")
    print(f"Cluster: {cluster.name}")
    print(f"Nodes: {cluster.nodes}")
    print(f"CPU limits: {cluster.total_cpu_limit()}")
    print(f"Memory limits: {cluster.total_memory_limit()} MB")


# ============================================================================
# 12. NETWORKING
# ============================================================================

@dataclass
class NetworkSegment:
    """Represents a logically isolated network segment."""

    name: str
    cidr: str
    private: bool
    internet_access: bool

    def describe(self) -> str:
        exposure = "private" if self.private else "public"
        internet = "internet-enabled" if self.internet_access else "no direct internet"
        return f"{self.name} ({self.cidr}, {exposure}, {internet})"


def demonstrate_network_segmentation() -> None:
    """
    Demonstrate a basic cloud network design.

    Public-facing components should not automatically share the same network
    segment as databases and other sensitive components.
    """

    segments = [
        NetworkSegment("public-subnet", "10.0.1.0/24", False, True),
        NetworkSegment("application-subnet", "10.0.2.0/24", True, False),
        NetworkSegment("database-subnet", "10.0.3.0/24", True, False),
    ]

    print("\n=== Network Segmentation ===")
    for segment in segments:
        print(segment.describe())


# ============================================================================
# 13. IDENTITY AND ACCESS MANAGEMENT
# ============================================================================

@dataclass
class Identity:
    name: str
    roles: Set[str]
    multifactor_enabled: bool


def authorize(identity: Identity, required_role: str) -> bool:
    """
    Simple role-based authorization.

    Authentication answers "Who are you?"
    Authorization answers "What are you allowed to do?"
    """

    return required_role in identity.roles


def demonstrate_iam() -> None:
    users = [
        Identity("developer", {"read-application", "deploy-application"}, True),
        Identity("auditor", {"read-audit-logs"}, True),
        Identity("operator", {"read-application", "restart-service"}, True),
    ]

    print("\n=== Identity and Access Management ===")

    for user in users:
        deployment_allowed = authorize(user, "deploy-application")
        print(
            f"{user.name}: MFA={user.multifactor_enabled}, "
            f"deploy_allowed={deployment_allowed}"
        )


# ============================================================================
# 14. SECURITY CONTROLS
# ============================================================================

@dataclass
class SecurityControl:
    name: str
    purpose: str
    layer: str


def security_control_catalog() -> List[SecurityControl]:
    controls = [
        SecurityControl(
            "Encryption at rest",
            "Protect stored data from unauthorized disclosure.",
            "Data",
        ),
        SecurityControl(
            "Encryption in transit",
            "Protect network traffic against interception.",
            "Network",
        ),
        SecurityControl(
            "Least privilege",
            "Grant only permissions required for a task.",
            "Identity",
        ),
        SecurityControl(
            "Network segmentation",
            "Limit lateral movement and isolate trust zones.",
            "Network",
        ),
        SecurityControl(
            "Centralized logging",
            "Provide evidence for monitoring and investigations.",
            "Operations",
        ),
        SecurityControl(
            "Secrets management",
            "Avoid embedding credentials directly in application code.",
            "Application",
        ),
        SecurityControl(
            "Backup and recovery",
            "Recover data after deletion, corruption, or disaster.",
            "Resilience",
        ),
    ]

    print("\n=== Security Control Catalog ===")
    for control in controls:
        print(f"{control.name}: {control.purpose} [{control.layer}]")

    return controls


# ============================================================================
# 15. AVAILABILITY AND FAILURE DOMAINS
# ============================================================================

def series_availability(component_availability: List[float]) -> float:
    """
    Calculate availability for components arranged in series.

    If every component must work for the service to work:

        A_total = A1 * A2 * ... * An

    Availability values are supplied as percentages.
    """

    if not component_availability:
        raise ValueError("At least one component is required.")

    result = 1.0

    for availability in component_availability:
        if not 0 <= availability <= 100:
            raise ValueError("Availability must be between 0 and 100.")
        result *= availability / 100.0

    return result * 100.0


def parallel_availability(component_availability: List[float]) -> float:
    """
    Calculate availability when service continues if at least one independent
    component remains operational.

        A_parallel = 1 - product(1 - Ai)
    """

    if not component_availability:
        raise ValueError("At least one component is required.")

    probability_of_all_failure = 1.0

    for availability in component_availability:
        if not 0 <= availability <= 100:
            raise ValueError("Availability must be between 0 and 100.")
        probability_of_all_failure *= 1 - availability / 100.0

    return (1 - probability_of_all_failure) * 100.0


def demonstrate_availability() -> None:
    print("\n=== Availability ===")

    single_service = series_availability([99.9])
    dependent_architecture = series_availability([99.9, 99.9, 99.9])
    redundant_architecture = parallel_availability([99.9, 99.9])

    print(f"Single 99.9% component: {single_service:.5f}%")
    print(f"Three serial 99.9% components: {dependent_architecture:.5f}%")
    print(f"Two independent 99.9% components in parallel: {redundant_architecture:.5f}%")


# ============================================================================
# 16. DOWNTIME CALCULATION
# ============================================================================

def annual_downtime_minutes(availability_percent: float) -> float:
    """Convert an availability percentage into expected annual downtime."""

    if not 0 <= availability_percent <= 100:
        raise ValueError("Availability must be between 0 and 100.")

    minutes_per_year = 365 * 24 * 60
    return minutes_per_year * (1 - availability_percent / 100.0)


def demonstrate_slas() -> None:
    print("\n=== Availability and Downtime ===")

    for target in [99.0, 99.9, 99.95, 99.99, 99.999]:
        downtime = annual_downtime_minutes(target)
        print(f"{target:.3f}% availability -> {downtime:.2f} minutes/year")


# ============================================================================
# 17. SCALABILITY
# ============================================================================

def required_instances(
    current_load: float,
    capacity_per_instance: float,
    target_utilization: float = 0.70,
) -> int:
    """
    Estimate instance count.

    Keeping planned utilization below 100% provides headroom for spikes.
    """

    if current_load < 0:
        raise ValueError("Current load cannot be negative.")
    if capacity_per_instance <= 0:
        raise ValueError("Instance capacity must be positive.")
    if not 0 < target_utilization <= 1:
        raise ValueError("Target utilization must be between 0 and 1.")

    effective_capacity = capacity_per_instance * target_utilization

    if current_load == 0:
        return 0

    return math.ceil(current_load / effective_capacity)


def demonstrate_scalability() -> None:
    print("\n=== Scalability ===")

    load = 1_000
    capacity = 250

    for utilization in [0.50, 0.70, 0.80, 0.90]:
        count = required_instances(load, capacity, utilization)
        print(
            f"Target utilization={utilization:.0%}: "
            f"{count} instances"
        )


# ============================================================================
# 18. DISASTER RECOVERY
# ============================================================================

@dataclass
class DisasterRecoveryPlan:
    """
    Represents basic RPO and RTO requirements.

    RPO = Recovery Point Objective:
        Maximum acceptable amount of data loss measured in time.

    RTO = Recovery Time Objective:
        Maximum acceptable time to restore service.
    """

    system_name: str
    rpo_minutes: int
    rto_minutes: int
    backup_frequency_minutes: int
    secondary_environment: str

    def validate(self) -> None:
        if self.rpo_minutes < 0:
            raise ValueError("RPO cannot be negative.")
        if self.rto_minutes < 0:
            raise ValueError("RTO cannot be negative.")
        if self.backup_frequency_minutes <= 0:
            raise ValueError("Backup frequency must be positive.")
        if self.backup_frequency_minutes > self.rpo_minutes and self.rpo_minutes != 0:
            raise ValueError(
                "Backup frequency is too slow to satisfy the stated RPO."
            )


def demonstrate_disaster_recovery() -> None:
    plan = DisasterRecoveryPlan(
        system_name="payment-service",
        rpo_minutes=15,
        rto_minutes=30,
        backup_frequency_minutes=10,
        secondary_environment="Separate failure domain",
    )

    plan.validate()

    print("\n=== Disaster Recovery ===")
    print(f"System: {plan.system_name}")
    print(f"RPO: {plan.rpo_minutes} minutes")
    print(f"RTO: {plan.rto_minutes} minutes")
    print(f"Backup frequency: {plan.backup_frequency_minutes} minutes")
    print(f"Secondary environment: {plan.secondary_environment}")


# ============================================================================
# 19. COST MODELING
# ============================================================================

@dataclass
class CostModel:
    """
    Simplified total-cost model.

    Real cloud cost models can include compute, storage, network transfer,
    managed services, support, licensing, labor, reservations, discounts,
    taxes, and data-transfer-related costs.
    """

    compute: float
    storage: float
    network: float
    managed_services: float
    operations: float

    def total(self) -> float:
        values = [
            self.compute,
            self.storage,
            self.network,
            self.managed_services,
            self.operations,
        ]

        if any(value < 0 for value in values):
            raise ValueError("Costs cannot be negative.")

        return sum(values)


def compare_cost_models() -> None:
    public = CostModel(
        compute=10_000,
        storage=2_000,
        network=1_500,
        managed_services=3_000,
        operations=2_500,
    )

    private = CostModel(
        compute=7_000,
        storage=1_500,
        network=700,
        managed_services=800,
        operations=8_000,
    )

    print("\n=== Simplified Cost Comparison ===")
    print(f"Public-cloud monthly estimate: ${public.total():,.2f}")
    print(f"Private-cloud monthly estimate: ${private.total():,.2f}")


# ============================================================================
# 20. CLOUD ECONOMICS
# ============================================================================

def calculate_break_even(
    private_monthly_cost: float,
    public_fixed_monthly_cost: float,
    public_variable_cost_per_unit: float,
) -> Optional[float]:
    """
    Find the usage level where public and private costs are equal.

    private_cost = public_fixed_cost + variable_cost * usage

    usage = (private_cost - public_fixed_cost) / variable_cost
    """

    if private_monthly_cost < 0:
        raise ValueError("Private cost cannot be negative.")
    if public_fixed_monthly_cost < 0:
        raise ValueError("Public fixed cost cannot be negative.")
    if public_variable_cost_per_unit < 0:
        raise ValueError("Variable cost cannot be negative.")

    if public_variable_cost_per_unit == 0:
        return None

    return (
        private_monthly_cost - public_fixed_monthly_cost
    ) / public_variable_cost_per_unit


def demonstrate_break_even() -> None:
    print("\n=== Break-Even Analysis ===")

    usage = calculate_break_even(
        private_monthly_cost=20_000,
        public_fixed_monthly_cost=5_000,
        public_variable_cost_per_unit=0.10,
    )

    print(f"Approximate break-even usage: {usage:,.0f} units")


# ============================================================================
# 21. WORKLOAD PLACEMENT
# ============================================================================

@dataclass
class PlacementScore:
    model: DeploymentModel
    score: float
    reasons: List[str]


def score_workload_for_model(
    workload: Workload,
    model: DeploymentModel,
) -> PlacementScore:
    """
    Apply a simplified rule-based placement framework.

    This is not a universal decision engine. Actual placement requires
    workload-specific requirements, regulations, contracts, architecture,
    operational capabilities, and measured economics.
    """

    workload.validate()

    score = 50.0
    reasons: List[str] = []

    if model == DeploymentModel.PUBLIC:
        if workload.portability_requirement >= 70:
            score += 10
            reasons.append("Public cloud can provide elastic standardized infrastructure.")
        if workload.data_sensitivity in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            score -= 10
            reasons.append("Sensitive data may require stronger governance controls.")
        if workload.latency_sensitive:
            score -= 5
            reasons.append("Network distance and connectivity must be evaluated.")

    elif model == DeploymentModel.PRIVATE:
        if workload.data_sensitivity in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            score += 20
            reasons.append("Dedicated infrastructure can simplify control requirements.")
        if workload.portability_requirement >= 70:
            score -= 10
            reasons.append("Private infrastructure can increase infrastructure coupling.")
        if workload.monthly_compute_units > 10_000:
            score -= 5
            reasons.append("Large dedicated capacity may require significant investment.")

    elif model == DeploymentModel.HYBRID:
        if workload.data_sensitivity in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            score += 15
            reasons.append("Hybrid placement can isolate sensitive components.")
        if workload.portability_requirement >= 60:
            score += 10
            reasons.append("Workloads can be distributed according to requirements.")
        if workload.latency_sensitive:
            score += 5
            reasons.append("Placement can keep latency-sensitive components close to users.")

    elif model == DeploymentModel.MULTI_CLOUD:
        if workload.portability_requirement >= 70:
            score += 20
            reasons.append("Multiple providers can support provider diversification.")
        else:
            score -= 5
            reasons.append("Multi-cloud may add unnecessary operational complexity.")

        if workload.monthly_network_units > 10_000:
            score -= 10
            reasons.append("Cross-provider traffic can create cost and latency concerns.")

    elif model == DeploymentModel.COMMUNITY:
        if workload.regulatory_requirements:
            score += 10
            reasons.append("Common governance can be useful for regulated communities.")
        else:
            score -= 10
            reasons.append("Community-specific governance may not justify its complexity.")

    return PlacementScore(
        model=model,
        score=max(0.0, min(100.0, score)),
        reasons=reasons,
    )


def recommend_deployment_models(workload: Workload) -> List[PlacementScore]:
    models = list(DeploymentModel)

    scores = [
        score_workload_for_model(workload, model)
        for model in models
    ]

    return sorted(scores, key=lambda result: result.score, reverse=True)


def demonstrate_workload_placement() -> None:
    workload = Workload(
        name="Healthcare Analytics",
        workload_type=WorkloadType.REGULATED_DATA,
        monthly_compute_units=8_000,
        monthly_storage_units=10_000,
        monthly_network_units=2_000,
        data_sensitivity=RiskLevel.CRITICAL,
        availability_target=99.99,
        portability_requirement=75,
        latency_sensitive=False,
        regulatory_requirements={"data-residency", "auditability"},
    )

    print("\n=== Workload Placement ===")
    print(f"Workload: {workload.name}")

    for result in recommend_deployment_models(workload):
        print(f"\n{result.model.value}: {result.score:.1f}/100")
        for reason in result.reasons:
            print(f"  - {reason}")


# ============================================================================
# 22. HYBRID ARCHITECTURE DATA FLOW
# ============================================================================

def simulate_hybrid_request(
    request_type: str,
    contains_sensitive_data: bool,
) -> str:
    """
    Route a request according to data sensitivity.

    This illustrates policy-based workload placement rather than a provider-
    specific networking implementation.
    """

    normalized_type = request_type.strip().lower()

    if not normalized_type:
        raise ValueError("Request type cannot be empty.")

    if contains_sensitive_data:
        return "Private environment"

    if normalized_type in {"web", "api", "analytics"}:
        return "Public cloud"

    return "Policy review required"


def demonstrate_hybrid_routing() -> None:
    print("\n=== Hybrid Request Routing ===")

    requests = [
        ("web", False),
        ("database", True),
        ("analytics", False),
        ("unknown", True),
    ]

    for request_type, sensitive in requests:
        destination = simulate_hybrid_request(request_type, sensitive)
        print(
            f"request={request_type!r}, "
            f"sensitive={sensitive} -> {destination}"
        )


# ============================================================================
# 23. MULTI-CLOUD PORTABILITY
# ============================================================================

@dataclass
class ApplicationComponent:
    name: str
    portable: bool
    provider_specific_dependencies: Set[str] = field(default_factory=set)

    def portability_score(self) -> float:
        """
        Approximate portability.

        Provider-specific dependencies reduce portability.
        """

        base = 100.0 if self.portable else 40.0
        penalty = min(60.0, len(self.provider_specific_dependencies) * 10.0)
        return max(0.0, base - penalty)


def demonstrate_portability() -> None:
    components = [
        ApplicationComponent(
            "Containerized API",
            portable=True,
        ),
        ApplicationComponent(
            "Managed Database Integration",
            portable=True,
            provider_specific_dependencies={"provider-managed-feature"},
        ),
        ApplicationComponent(
            "Proprietary Event System",
            portable=False,
            provider_specific_dependencies={
                "special-api",
                "special-sdk",
                "special-identity",
            },
        ),
    ]

    print("\n=== Application Portability ===")

    for component in components:
        print(
            f"{component.name}: "
            f"portability={component.portability_score():.1f}/100"
        )


# ============================================================================
# 24. VENDOR LOCK-IN
# ============================================================================

def vendor_lock_in_risk(
    provider_specific_services: int,
    proprietary_apis: int,
    migration_complexity: int,
) -> float:
    """
    Calculate a simple normalized lock-in indicator.

    Higher values indicate stronger dependence on provider-specific
    technologies. This is an analytical aid, not a standardized metric.
    """

    values = [
        provider_specific_services,
        proprietary_apis,
        migration_complexity,
    ]

    if any(value < 0 for value in values):
        raise ValueError("Risk inputs cannot be negative.")

    raw_score = (
        provider_specific_services * 10
        + proprietary_apis * 8
        + migration_complexity * 12
    )

    return min(100.0, raw_score)


def demonstrate_vendor_lock_in() -> None:
    print("\n=== Vendor Lock-In ===")

    scenarios = [
        ("Portable containers", 1, 1, 2),
        ("Moderately provider-specific", 4, 3, 5),
        ("Highly provider-specific", 8, 7, 8),
    ]

    for name, services, apis, complexity in scenarios:
        risk = vendor_lock_in_risk(services, apis, complexity)
        print(f"{name}: lock-in indicator={risk:.1f}/100")


# ============================================================================
# 25. DATA RESIDENCY AND COMPLIANCE
# ============================================================================

@dataclass
class DataPolicy:
    classification: RiskLevel
    allowed_regions: Set[str]
    encryption_required: bool
    audit_logging_required: bool
    retention_days: int

    def validate(self) -> None:
        if self.retention_days < 0:
            raise ValueError("Retention cannot be negative.")

        if self.classification in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            if not self.encryption_required:
                raise ValueError(
                    "High-risk data should have encryption enabled."
                )

        if self.classification == RiskLevel.CRITICAL:
            if not self.audit_logging_required:
                raise ValueError(
                    "Critical data should have audit logging enabled."
                )


def can_deploy_data(
    policy: DataPolicy,
    region: str,
) -> bool:
    """Determine whether a region satisfies a simplified data policy."""

    policy.validate()

    return region in policy.allowed_regions


def demonstrate_data_governance() -> None:
    policy = DataPolicy(
        classification=RiskLevel.CRITICAL,
        allowed_regions={"Region-A", "Region-B"},
        encryption_required=True,
        audit_logging_required=True,
        retention_days=365,
    )

    print("\n=== Data Governance ===")

    for region in ["Region-A", "Region-C"]:
        print(
            f"{region}: "
            f"deployment_allowed={can_deploy_data(policy, region)}"
        )


# ============================================================================
# 26. OBSERVABILITY
# ============================================================================

@dataclass
class ServiceTelemetry:
    requests: int
    errors: int
    total_latency_ms: float

    def error_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.errors / self.requests * 100

    def average_latency_ms(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.total_latency_ms / self.requests


def demonstrate_observability() -> None:
    telemetry = ServiceTelemetry(
        requests=100_000,
        errors=120,
        total_latency_ms=8_000_000,
    )

    print("\n=== Observability ===")
    print(f"Requests: {telemetry.requests:,}")
    print(f"Error rate: {telemetry.error_rate():.3f}%")
    print(f"Average latency: {telemetry.average_latency_ms():.2f} ms")


# ============================================================================
# 27. LOAD SIMULATION
# ============================================================================

def simulate_load(
    minutes: int,
    baseline_requests_per_minute: int,
    spike_probability: float,
    spike_multiplier: float,
    seed: int = 42,
) -> List[int]:
    """
    Generate deterministic synthetic traffic.

    A fixed seed makes the educational simulation reproducible.
    """

    if minutes <= 0:
        raise ValueError("Simulation duration must be positive.")
    if baseline_requests_per_minute < 0:
        raise ValueError("Baseline traffic cannot be negative.")
    if not 0 <= spike_probability <= 1:
        raise ValueError("Spike probability must be between 0 and 1.")
    if spike_multiplier < 1:
        raise ValueError("Spike multiplier must be at least 1.")

    random_generator = random.Random(seed)
    traffic = []

    for _ in range(minutes):
        if random_generator.random() < spike_probability:
            traffic.append(
                int(baseline_requests_per_minute * spike_multiplier)
            )
        else:
            variation = random_generator.uniform(0.8, 1.2)
            traffic.append(int(baseline_requests_per_minute * variation))

    return traffic


def demonstrate_load_simulation() -> None:
    traffic = simulate_load(
        minutes=30,
        baseline_requests_per_minute=10_000,
        spike_probability=0.10,
        spike_multiplier=3,
    )

    print("\n=== Load Simulation ===")
    print(f"Average requests/minute: {statistics.mean(traffic):,.0f}")
    print(f"Peak requests/minute: {max(traffic):,.0f}")
    print(f"Minimum requests/minute: {min(traffic):,.0f}")


# ============================================================================
# 28. ELASTICITY
# ============================================================================

def autoscale_decision(
    requests_per_minute: float,
    capacity_per_instance: float,
    current_instances: int,
    scale_up_threshold: float = 0.70,
    scale_down_threshold: float = 0.30,
) -> Tuple[str, int]:
    """
    Produce a simple autoscaling decision.

    Real autoscaling systems use metrics, cooldown periods, health checks,
    predictive policies, workload characteristics, and minimum/maximum
    capacity constraints.
    """

    if requests_per_minute < 0:
        raise ValueError("Traffic cannot be negative.")
    if capacity_per_instance <= 0:
        raise ValueError("Capacity must be positive.")
    if current_instances <= 0:
        raise ValueError("Current instance count must be positive.")

    utilization = requests_per_minute / (
        capacity_per_instance * current_instances
    )

    if utilization > scale_up_threshold:
        desired = math.ceil(
            requests_per_minute
            / (capacity_per_instance * scale_up_threshold)
        )
        return "scale_up", max(current_instances + 1, desired)

    if utilization < scale_down_threshold and current_instances > 1:
        desired = math.ceil(
            requests_per_minute
            / (capacity_per_instance * max(scale_down_threshold, 0.01))
        )
        return "scale_down", max(1, min(current_instances - 1, desired))

    return "hold", current_instances


def demonstrate_autoscaling() -> None:
    print("\n=== Autoscaling ===")

    for traffic in [1_000, 5_000, 12_000, 20_000]:
        action, instances = autoscale_decision(
            requests_per_minute=traffic,
            capacity_per_instance=5_000,
            current_instances=3,
        )

        print(
            f"Traffic={traffic:,}: "
            f"action={action}, instances={instances}"
        )


# ============================================================================
# 29. MIGRATION STRATEGIES
# ============================================================================

class MigrationStrategy(Enum):
    REHOST = "Rehost"
    REPLATFORM = "Replatform"
    REFACTOR = "Refactor"
    REPURCHASE = "Repurchase"
    RETAIN = "Retain"
    RETIRE = "Retire"


def explain_migration_strategies() -> None:
    """
    Explain common migration approaches.

    Rehost:
        Move the workload with minimal changes.

    Replatform:
        Make limited modifications to use cloud capabilities.

    Refactor:
        Redesign the application substantially for cloud-native operation.

    Repurchase:
        Replace an existing system with a different product/service.

    Retain:
        Keep the workload where it is.

    Retire:
        Remove a workload that is no longer required.
    """

    print("\n=== Migration Strategies ===")

    descriptions = {
        MigrationStrategy.REHOST: "Move with minimal architectural change.",
        MigrationStrategy.REPLATFORM: "Move with moderate optimization.",
        MigrationStrategy.REFACTOR: "Redesign substantially for cloud capabilities.",
        MigrationStrategy.REPURCHASE: "Replace the existing system with another service.",
        MigrationStrategy.RETAIN: "Keep the workload in its current environment.",
        MigrationStrategy.RETIRE: "Remove the workload because it is no longer needed.",
    }

    for strategy, description in descriptions.items():
        print(f"{strategy.value}: {description}")


# ============================================================================
# 30. DECISION FRAMEWORK
# ============================================================================

@dataclass
class ArchitectureRequirements:
    security: int
    compliance: int
    scalability: int
    portability: int
    cost_sensitivity: int
    operational_maturity: int

    def validate(self) -> None:
        values = [
            self.security,
            self.compliance,
            self.scalability,
            self.portability,
            self.cost_sensitivity,
            self.operational_maturity,
        ]

        if any(value < 1 or value > 5 for value in values):
            raise ValueError("Requirement weights must be between 1 and 5.")


def architecture_decision(
    requirements: ArchitectureRequirements,
) -> List[Tuple[str, float]]:
    """
    Produce a conceptual decision score.

    Scores are deliberately transparent so that assumptions can be inspected.
    Real architecture decisions should be supported by detailed requirements,
    proofs of concept, risk analysis, contracts, and financial modeling.
    """

    requirements.validate()

    public = (
        requirements.scalability * 1.5
        + requirements.cost_sensitivity * 1.0
        + requirements.operational_maturity * 1.2
        + requirements.portability * 0.8
        - requirements.compliance * 0.5
    )

    private = (
        requirements.security * 1.5
        + requirements.compliance * 1.5
        + requirements.operational_maturity * 0.8
        - requirements.scalability * 0.4
    )

    hybrid = (
        requirements.security * 1.2
        + requirements.compliance * 1.2
        + requirements.scalability * 1.2
        + requirements.portability * 1.0
        - requirements.operational_maturity * 0.2
    )

    multi_cloud = (
        requirements.portability * 1.6
        + requirements.scalability * 1.2
        + requirements.security * 0.8
        - requirements.operational_maturity * 0.8
        - requirements.cost_sensitivity * 0.3
    )

    community = (
        requirements.compliance * 1.6
        + requirements.security * 1.2
        - requirements.scalability * 0.2
    )

    scores = {
        "Public Cloud": public,
        "Private Cloud": private,
        "Hybrid Cloud": hybrid,
        "Multi-Cloud": multi_cloud,
        "Community Cloud": community,
    }

    return sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )


def demonstrate_architecture_decision() -> None:
    requirements = ArchitectureRequirements(
        security=5,
        compliance=5,
        scalability=4,
        portability=4,
        cost_sensitivity=3,
        operational_maturity=4,
    )

    print("\n=== Architecture Decision Framework ===")

    for model, score in architecture_decision(requirements):
        print(f"{model}: {score:.2f}")


# ============================================================================
# 31. EDGE CASES AND VALIDATION
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\n=== Edge Cases and Validation ===")

    cases = [
        ("Negative compute", lambda: required_instances(-1, 100)),
        ("Zero instance capacity", lambda: required_instances(100, 0)),
        ("Invalid availability", lambda: annual_downtime_minutes(101)),
        ("Empty series", lambda: series_availability([])),
        ("Invalid RTO/RPO backup", lambda: DisasterRecoveryPlan(
            system_name="test",
            rpo_minutes=10,
            rto_minutes=20,
            backup_frequency_minutes=30,
            secondary_environment="secondary",
        ).validate()),
    ]

    for name, operation in cases:
        try:
            operation()
        except (ValueError, TypeError) as error:
            print(f"{name}: correctly rejected -> {error}")
        else:
            print(f"{name}: ERROR, invalid input was accepted")


# ============================================================================
# 32. COMMON ARCHITECTURAL MISTAKES
# ============================================================================

def demonstrate_common_mistakes() -> None:
    """
    Print common mistakes and the underlying architectural principle.
    """

    mistakes = {
        "Treating cloud as simply someone else's data center":
            "Cloud introduces elasticity, automation, managed services, and consumption-based economics.",
        "Choosing multi-cloud only to avoid lock-in":
            "Multi-cloud introduces networking, identity, observability, skills, and operational complexity.",
        "Assuming public cloud is always cheaper":
            "Cost depends on utilization, architecture, licensing, traffic, operations, and workload shape.",
        "Putting every workload in private infrastructure":
            "Dedicated capacity may be unnecessary for elastic or commodity workloads.",
        "Putting every workload in public cloud":
            "Data residency, latency, hardware, regulatory, or legacy requirements may justify other environments.",
        "Ignoring data transfer":
            "Cross-region and cross-provider traffic can affect both cost and latency.",
        "Using excessive provider-specific services":
            "Managed services can improve productivity but may reduce portability.",
        "Treating availability as the same as resilience":
            "Availability addresses service uptime; resilience also considers recovery from failures and disasters.",
        "Skipping identity design":
            "Compromised credentials can undermine otherwise strong network and infrastructure controls.",
        "No observability":
            "A system cannot be operated reliably if failures and performance degradation cannot be detected.",
    }

    print("\n=== Common Architectural Mistakes ===")

    for mistake, principle in mistakes.items():
        print(f"\nMistake: {mistake}")
        print(f"Principle: {principle}")


# ============================================================================
# 33. PRODUCTION DESIGN CHECKLIST
# ============================================================================

def production_checklist() -> List[str]:
    """
    Return a practical production architecture checklist.
    """

    checklist = [
        "Define business and technical requirements.",
        "Classify data and identify regulatory requirements.",
        "Define identity, authentication, authorization, and privileged access.",
        "Separate public-facing and sensitive network components.",
        "Define encryption requirements for data at rest and in transit.",
        "Define backup, RPO, and RTO requirements.",
        "Design for appropriate failure domains.",
        "Define monitoring, logging, tracing, and alerting.",
        "Establish infrastructure-as-code and configuration management.",
        "Define deployment and rollback mechanisms.",
        "Control secrets and credentials.",
        "Model expected and peak workloads.",
        "Estimate total cost, including network and operational costs.",
        "Evaluate provider-specific dependencies.",
        "Document data residency and retention requirements.",
        "Test disaster recovery instead of assuming backups work.",
        "Define incident response procedures.",
        "Review access privileges periodically.",
        "Measure service-level objectives using real telemetry.",
        "Document ownership and operational responsibilities.",
    ]

    print("\n=== Production Checklist ===")
    for number, item in enumerate(checklist, start=1):
        print(f"{number:02d}. {item}")

    return checklist


# ============================================================================
# 34. REAL-WORLD ARCHITECTURE SCENARIOS
# ============================================================================

def scenario_ecommerce() -> Dict[str, str]:
    """
    E-commerce example.

    Public cloud is often attractive for highly variable web traffic.
    """

    architecture = {
        "frontend": "Public cloud",
        "application": "Public cloud",
        "database": "Public managed service or private environment based on requirements",
        "backup": "Independent recovery environment",
        "security": "WAF, IAM, encryption, segmentation, monitoring",
        "scaling": "Horizontal autoscaling",
    }

    return architecture


def scenario_bank() -> Dict[str, str]:
    """
    Banking-style example.

    A real financial institution's architecture depends on jurisdiction,
    regulation, risk appetite, existing infrastructure, and contracts.
    """

    return {
        "customer-facing services": "Public cloud or hybrid",
        "legacy_core": "Private environment or controlled hosted environment",
        "analytics": "Public cloud where permitted",
        "sensitive_records": "Environment selected according to regulatory requirements",
        "identity": "Centralized enterprise identity",
        "audit": "Centralized tamper-resistant logging",
    }


def scenario_research() -> Dict[str, str]:
    """Research institution example."""

    return {
        "large-scale compute": "Public or community cloud",
        "specialized hardware": "Private or dedicated infrastructure",
        "shared datasets": "Community environment",
        "collaboration": "Controlled public services",
        "governance": "Research-specific access policies",
    }


def demonstrate_real_world_scenarios() -> None:
    print("\n=== Real-World Scenarios ===")

    scenarios = {
        "E-commerce": scenario_ecommerce(),
        "Financial services": scenario_bank(),
        "Research institution": scenario_research(),
    }

    for name, architecture in scenarios.items():
        print(f"\n{name}")
        for component, environment in architecture.items():
            print(f"  {component}: {environment}")


# ============================================================================
# 35. ADVANCED COMPARISON: HYBRID VS MULTI-CLOUD
# ============================================================================

def compare_hybrid_and_multi_cloud() -> None:
    """
    Explain a frequent conceptual distinction.

    Hybrid:
        Combines different infrastructure/environment types, commonly private
        and public cloud.

    Multi-cloud:
        Uses multiple cloud providers.

    The two can coexist. An organization may have private infrastructure plus
    two public cloud providers, making its architecture both hybrid and
    multi-cloud.
    """

    examples = [
        (
            "Hybrid only",
            "Private cloud + one public cloud provider",
        ),
        (
            "Multi-cloud only",
            "Two public cloud providers without private infrastructure",
        ),
        (
            "Hybrid + multi-cloud",
            "Private cloud + two public cloud providers",
        ),
    ]

    print("\n=== Hybrid vs Multi-Cloud ===")

    for label, architecture in examples:
        print(f"{label}: {architecture}")


# ============================================================================
# 36. CLOUD-NATIVE DESIGN
# ============================================================================

@dataclass
class CloudNativePrinciples:
    principles: List[str]

    def validate(self) -> None:
        required = {
            "automation",
            "observability",
            "elasticity",
            "resilience",
            "declarative infrastructure",
        }

        normalized = {item.lower() for item in self.principles}

        missing = required - normalized

        if missing:
            raise ValueError(
                f"Missing cloud-native principles: {sorted(missing)}"
            )


def demonstrate_cloud_native_design() -> None:
    design = CloudNativePrinciples(
        principles=[
            "automation",
            "observability",
            "elasticity",
            "resilience",
            "declarative infrastructure",
        ]
    )

    design.validate()

    print("\n=== Cloud-Native Design Principles ===")
    for principle in design.principles:
        print(f"- {principle}")


# ============================================================================
# 37. PERFORMANCE CONSIDERATIONS
# ============================================================================

def estimate_response_time(
    application_ms: float,
    database_ms: float,
    network_ms: float,
    external_service_ms: float,
) -> float:
    """
    Approximate sequential latency.

    Real distributed systems can have parallel operations, queues, retries,
    serialization, caching, contention, and tail latency effects.
    """

    components = [
        application_ms,
        database_ms,
        network_ms,
        external_service_ms,
    ]

    if any(value < 0 for value in components):
        raise ValueError("Latency components cannot be negative.")

    return sum(components)


def demonstrate_performance() -> None:
    print("\n=== Performance ===")

    latency = estimate_response_time(
        application_ms=30,
        database_ms=20,
        network_ms=15,
        external_service_ms=40,
    )

    print(f"Estimated sequential response time: {latency} ms")


# ============================================================================
# 38. TAIL LATENCY
# ============================================================================

def percentile(values: List[float], p: float) -> float:
    """
    Compute a simple linear-interpolation percentile.

    Percentiles such as p95 and p99 are often more useful than averages for
    understanding user-facing distributed-system latency.
    """

    if not values:
        raise ValueError("At least one value is required.")
    if not 0 <= p <= 100:
        raise ValueError("Percentile must be between 0 and 100.")

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * p / 100
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    weight = position - lower

    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def demonstrate_tail_latency() -> None:
    samples = [
        20, 22, 23, 24, 25,
        26, 27, 28, 30, 32,
        35, 38, 42, 50, 120,
    ]

    print("\n=== Tail Latency ===")
    print(f"Average: {statistics.mean(samples):.2f} ms")
    print(f"p95: {percentile(samples, 95):.2f} ms")
    print(f"p99: {percentile(samples, 99):.2f} ms")


# ============================================================================
# 39. RESILIENCE TESTING
# ============================================================================

@dataclass
class FailureScenario:
    name: str
    affected_components: Set[str]
    expected_behavior: str


def evaluate_failure(
    scenario: FailureScenario,
    redundancy: Dict[str, int],
) -> bool:
    """
    Evaluate whether enough redundant capacity remains after a failure.

    A component with one redundant copy has a simplified redundancy value of 2,
    meaning two instances exist before the failure.
    """

    for component in scenario.affected_components:
        if redundancy.get(component, 0) <= 1:
            return False

    return True


def demonstrate_resilience_testing() -> None:
    scenarios = [
        FailureScenario(
            "Web instance failure",
            {"web"},
            "Traffic is routed to remaining instances.",
        ),
        FailureScenario(
            "Database primary failure",
            {"database"},
            "A healthy replica becomes primary.",
        ),
        FailureScenario(
            "Entire region failure",
            {"region"},
            "Traffic moves to another region.",
        ),
    ]

    redundancy = {
        "web": 3,
        "database": 2,
        "region": 2,
    }

    print("\n=== Resilience Testing ===")

    for scenario in scenarios:
        survives = evaluate_failure(scenario, redundancy)
        print(
            f"{scenario.name}: "
            f"resilience_test={'PASS' if survives else 'FAIL'}"
        )


# ============================================================================
# 40. SECURITY THREAT MODEL
# ============================================================================

@dataclass
class Threat:
    name: str
    probability: float
    impact: float

    def risk_score(self) -> float:
        """
        Simplified risk calculation.

        risk = probability × impact

        Values are normalized to 0-100 for educational purposes.
        """

        if not 0 <= self.probability <= 1:
            raise ValueError("Probability must be between 0 and 1.")
        if not 0 <= self.impact <= 100:
            raise ValueError("Impact must be between 0 and 100.")

        return self.probability * self.impact


def demonstrate_threat_model() -> None:
    threats = [
        Threat("Credential compromise", 0.20, 90),
        Threat("Misconfigured storage", 0.15, 85),
        Threat("Provider outage", 0.05, 80),
        Threat("Insufficient logging", 0.30, 50),
    ]

    print("\n=== Simplified Cloud Threat Model ===")

    for threat in threats:
        print(
            f"{threat.name}: risk={threat.risk_score():.2f}"
        )


# ============================================================================
# 41. GOVERNANCE
# ============================================================================

@dataclass
class GovernancePolicy:
    mandatory_tags: Set[str]
    allowed_regions: Set[str]
    encryption_required: bool
    public_storage_allowed: bool

    def validate_resource(
        self,
        tags: Set[str],
        region: str,
        encrypted: bool,
        is_public_storage: bool,
    ) -> Tuple[bool, List[str]]:
        violations = []

        missing_tags = self.mandatory_tags - tags

        if missing_tags:
            violations.append(
                f"Missing tags: {sorted(missing_tags)}"
            )

        if region not in self.allowed_regions:
            violations.append(
                f"Region {region!r} is not allowed."
            )

        if self.encryption_required and not encrypted:
            violations.append("Encryption is required.")

        if not self.public_storage_allowed and is_public_storage:
            violations.append("Public storage is prohibited.")

        return len(violations) == 0, violations


def demonstrate_governance() -> None:
    policy = GovernancePolicy(
        mandatory_tags={"owner", "environment", "cost-center"},
        allowed_regions={"Region-A", "Region-B"},
        encryption_required=True,
        public_storage_allowed=False,
    )

    resources = [
        (
            {"owner", "environment", "cost-center"},
            "Region-A",
            True,
            False,
        ),
        (
            {"owner"},
            "Region-C",
            False,
            True,
        ),
    ]

    print("\n=== Governance ===")

    for resource in resources:
        valid, violations = policy.validate_resource(*resource)

        print(f"Compliant: {valid}")

        for violation in violations:
            print(f"  - {violation}")


# ============================================================================
# 42. TESTS
# ============================================================================

class CloudDeploymentTests(unittest.TestCase):
    """Unit tests for core educational functions."""

    def test_series_availability(self) -> None:
        self.assertAlmostEqual(
            series_availability([99.9, 99.9]),
            99.8001,
            places=4,
        )

    def test_parallel_availability(self) -> None:
        result = parallel_availability([99.9, 99.9])
        self.assertGreater(result, 99.9)

    def test_required_instances(self) -> None:
        self.assertEqual(required_instances(1_000, 250, 0.5), 8)

    def test_percentile(self) -> None:
        self.assertAlmostEqual(
            percentile([1, 2, 3, 4, 5], 50),
            3,
        )

    def test_public_workload(self) -> None:
        workload = Workload(
            name="Test",
            workload_type=WorkloadType.WEB_APPLICATION,
            monthly_compute_units=100,
            monthly_storage_units=100,
            monthly_network_units=100,
            data_sensitivity=RiskLevel.LOW,
            availability_target=99.9,
            portability_requirement=50,
        )

        result = score_workload_for_model(
            workload,
            DeploymentModel.PUBLIC,
        )

        self.assertEqual(result.model, DeploymentModel.PUBLIC)

    def test_invalid_availability(self) -> None:
        with self.assertRaises(ValueError):
            annual_downtime_minutes(101)

    def test_invalid_scaling(self) -> None:
        with self.assertRaises(ValueError):
            required_instances(100, 0)


def run_tests() -> None:
    """
    Run tests without relying on the command-line unittest runner.

    exit=False allows the educational script to continue after test execution.
    """

    print("\n=== Automated Tests ===")

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        CloudDeploymentTests
    )

    runner = unittest.TextTestRunner(verbosity=1)
    runner.run(suite)


# ============================================================================
# 43. INTEGRATED CASE STUDY
# ============================================================================

def integrated_case_study() -> None:
    """
    Combine multiple concepts into one architecture exercise.

    Scenario:
        A growing organization operates a customer-facing application,
        sensitive records, analytics workloads, and disaster recovery.

    A plausible design may be hybrid or multi-cloud depending on the actual
    requirements. The purpose is to demonstrate the reasoning process.
    """

    print("\n=== Integrated Case Study ===")

    workload = Workload(
        name="Customer Platform",
        workload_type=WorkloadType.WEB_APPLICATION,
        monthly_compute_units=20_000,
        monthly_storage_units=15_000,
        monthly_network_units=8_000,
        data_sensitivity=RiskLevel.HIGH,
        availability_target=99.99,
        portability_requirement=80,
        latency_sensitive=True,
        regulatory_requirements={"auditability"},
    )

    workload.validate()

    print(f"Workload: {workload.name}")

    print("\nPlacement candidates:")

    for result in recommend_deployment_models(workload):
        print(f"- {result.model.value}: {result.score:.1f}/100")

    print("\nCapacity estimate:")

    instances = required_instances(
        current_load=20_000,
        capacity_per_instance=5_000,
        target_utilization=0.70,
    )

    print(f"Required application instances: {instances}")

    print("\nAvailability design:")

    availability = parallel_availability([99.95, 99.95])
    print(f"Two independent service paths: {availability:.5f}%")

    print("\nGovernance requirements:")

    governance = GovernancePolicy(
        mandatory_tags={"owner", "environment", "cost-center"},
        allowed_regions={"Region-A", "Region-B"},
        encryption_required=True,
        public_storage_allowed=False,
    )

    valid, violations = governance.validate_resource(
        tags={"owner", "environment", "cost-center"},
        region="Region-A",
        encrypted=True,
        is_public_storage=False,
    )

    print(f"Resource compliant: {valid}")

    if violations:
        for violation in violations:
            print(f"  - {violation}")


# ============================================================================
# 44. COMPLETE COURSE RUNNER
# ============================================================================

def run_course() -> None:
    """
    Execute the educational material in a logical progression.
    """

    print("=" * 80)
    print("CLOUD DEPLOYMENT MODELS")
    print("Public | Private | Hybrid | Multi-Cloud | Community")
    print("=" * 80)

    explain_cloud_computing()
    explain_shared_responsibility()

    compare_service_models()

    public_cloud_example()
    private_cloud_example()
    hybrid_cloud_example()
    multi_cloud_example()
    community_cloud_example()

    deployment_model_matrix()

    demonstrate_virtualization()
    demonstrate_containers()
    demonstrate_network_segmentation()

    demonstrate_iam()
    security_control_catalog()

    demonstrate_availability()
    demonstrate_slas()
    demonstrate_scalability()
    demonstrate_disaster_recovery()

    compare_cost_models()
    demonstrate_break_even()

    demonstrate_workload_placement()
    demonstrate_hybrid_routing()
    demonstrate_portability()
    demonstrate_vendor_lock_in()

    demonstrate_data_governance()
    demonstrate_observability()
    demonstrate_load_simulation()
    demonstrate_autoscaling()

    explain_migration_strategies()
    demonstrate_architecture_decision()

    demonstrate_edge_cases()
    demonstrate_common_mistakes()
    production_checklist()

    demonstrate_real_world_scenarios()
    compare_hybrid_and_multi_cloud()
    demonstrate_cloud_native_design()

    demonstrate_performance()
    demonstrate_tail_latency()
    demonstrate_resilience_testing()
    demonstrate_threat_model()
    demonstrate_governance()

    integrated_case_study()

    run_tests()

    print("\n" + "=" * 80)
    print("END OF CLOUD DEPLOYMENT MODELS STUDY SCRIPT")
    print("=" * 80)


if __name__ == "__main__":
    run_course()
