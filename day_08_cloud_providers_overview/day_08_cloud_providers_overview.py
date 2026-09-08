"""
Cloud Providers Overview
========================

A self-contained study script covering major cloud providers, core infrastructure
services, global architecture, service models, deployment patterns, networking,
storage, compute, security, resilience, cost management, portability, and
production design.

The script uses only the Python standard library and simulates common cloud
concepts. It is designed to be read, modified, and executed.

Major providers discussed:
- Amazon Web Services (AWS)
- Microsoft Azure
- Google Cloud Platform (GCP)

Other providers included for architectural comparison:
- Oracle Cloud Infrastructure (OCI)
- IBM Cloud
- DigitalOcean

Run:
    python cloud_providers_overview.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import hashlib
import itertools
import json
import random
import time


# =============================================================================
# 1. FUNDAMENTAL CLOUD COMPUTING CONCEPTS
# =============================================================================


class ServiceModel(str, Enum):
    """
    Cloud service responsibility models.

    IaaS:
        Infrastructure as a Service. The provider manages physical infrastructure,
        while the customer manages operating systems and applications.

    PaaS:
        Platform as a Service. The provider manages more of the platform,
        reducing operational responsibility.

    SaaS:
        Software as a Service. The provider operates the complete application.

    SERVERLESS:
        The customer focuses primarily on application code and configuration.
        Infrastructure capacity is allocated and managed by the provider.
    """

    IAAS = "IaaS"
    PAAS = "PaaS"
    SAAS = "SaaS"
    SERVERLESS = "Serverless"


class DeploymentModel(str, Enum):
    """Common cloud deployment approaches."""

    PUBLIC_CLOUD = "Public Cloud"
    PRIVATE_CLOUD = "Private Cloud"
    HYBRID_CLOUD = "Hybrid Cloud"
    MULTI_CLOUD = "Multi-Cloud"


class ResourceState(str, Enum):
    """Simplified lifecycle states for infrastructure resources."""

    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


class AvailabilityTier(str, Enum):
    """
    Simplified availability classifications.

    These are conceptual labels rather than official provider SLAs.
    """

    SINGLE_ZONE = "single-zone"
    MULTI_ZONE = "multi-zone"
    MULTI_REGION = "multi-region"


# =============================================================================
# 2. GLOBAL CLOUD ARCHITECTURE
# =============================================================================


@dataclass(frozen=True)
class Region:
    """
    A geographical cloud area containing one or more isolated availability zones.

    Regions help organizations place workloads closer to users, satisfy data
    residency requirements, and implement geographic disaster recovery.
    """

    provider: str
    code: str
    location: str
    zones: Tuple[str, ...]

    def describe(self) -> str:
        return (
            f"{self.provider} region {self.code} ({self.location}) "
            f"with {len(self.zones)} availability zones"
        )


@dataclass(frozen=True)
class EdgeLocation:
    """
    A point-of-presence used for edge delivery.

    Edge infrastructure is commonly used by:
    - Content delivery networks
    - DNS services
    - DDoS mitigation
    - Edge computing
    - Application acceleration
    """

    provider: str
    city: str
    code: str


@dataclass
class GlobalArchitecture:
    """
    Represents a provider's broad global infrastructure model.

    Most large cloud providers use several infrastructure layers:

    1. Global backbone:
       Private high-capacity networking between provider facilities.

    2. Regions:
       Independent geographical areas.

    3. Availability zones or equivalent failure domains:
       Isolated facilities within or associated with a region.

    4. Edge locations:
       Infrastructure positioned close to users.

    Isolation matters because an outage affecting one zone should not necessarily
    affect another zone. A multi-zone application can therefore tolerate certain
    localized infrastructure failures.
    """

    provider: str
    regions: List[Region]
    edge_locations: List[EdgeLocation]

    def find_region(self, region_code: str) -> Optional[Region]:
        for region in self.regions:
            if region.code == region_code:
                return region
        return None

    def zones_in_region(self, region_code: str) -> Tuple[str, ...]:
        region = self.find_region(region_code)
        return region.zones if region else ()

    def nearest_edge(self, city: str) -> Optional[EdgeLocation]:
        """
        This is a conceptual exact-city lookup.

        Real CDNs select edge locations using network routing, latency, health,
        capacity, geography, and traffic engineering rather than exact string
        comparison.
        """
        normalized_city = city.strip().lower()

        for edge in self.edge_locations:
            if edge.city.lower() == normalized_city:
                return edge

        return None


# =============================================================================
# 3. PROVIDER SERVICE CATALOGS
# =============================================================================


@dataclass(frozen=True)
class Service:
    """A cloud service and its broad architectural category."""

    name: str
    category: str
    service_model: ServiceModel
    description: str


@dataclass
class CloudProvider:
    """
    Represents a cloud provider.

    Service names differ between providers, but many infrastructure concepts are
    comparable:

    Compute:
        Virtual machines, containers, functions.

    Storage:
        Object, block, and file storage.

    Networking:
        Virtual networks, subnets, routing, load balancing, DNS.

    Databases:
        Relational, NoSQL, analytics, caching.

    Identity and security:
        Identity management, access policies, encryption, secrets.

    Management:
        Monitoring, logging, infrastructure automation, cost governance.
    """

    name: str
    abbreviation: str
    architecture: GlobalArchitecture
    services: List[Service]

    def services_by_category(self, category: str) -> List[Service]:
        category = category.lower()
        return [
            service
            for service in self.services
            if service.category.lower() == category
        ]

    def find_service(self, name: str) -> Optional[Service]:
        normalized = name.strip().lower()

        for service in self.services:
            if service.name.lower() == normalized:
                return service

        return None

    def categories(self) -> List[str]:
        return sorted({service.category for service in self.services})


# =============================================================================
# 4. CLOUD PROVIDER DATA
# =============================================================================


def build_providers() -> Dict[str, CloudProvider]:
    """Build representative provider catalogs."""

    aws = CloudProvider(
        name="Amazon Web Services",
        abbreviation="AWS",
        architecture=GlobalArchitecture(
            provider="AWS",
            regions=[
                Region(
                    "AWS",
                    "us-east-1",
                    "Northern Virginia",
                    ("us-east-1a", "us-east-1b", "us-east-1c"),
                ),
                Region(
                    "AWS",
                    "eu-west-1",
                    "Ireland",
                    ("eu-west-1a", "eu-west-1b", "eu-west-1c"),
                ),
                Region(
                    "AWS",
                    "ap-south-1",
                    "Mumbai",
                    ("ap-south-1a", "ap-south-1b", "ap-south-1c"),
                ),
            ],
            edge_locations=[
                EdgeLocation("AWS", "Mumbai", "edge-mum"),
                EdgeLocation("AWS", "Singapore", "edge-sin"),
                EdgeLocation("AWS", "London", "edge-lon"),
            ],
        ),
        services=[
            Service(
                "EC2",
                "Compute",
                ServiceModel.IAAS,
                "Virtual machine compute instances.",
            ),
            Service(
                "Lambda",
                "Compute",
                ServiceModel.SERVERLESS,
                "Event-driven serverless function execution.",
            ),
            Service(
                "ECS",
                "Containers",
                ServiceModel.PAAS,
                "Container orchestration service.",
            ),
            Service(
                "EKS",
                "Containers",
                ServiceModel.PAAS,
                "Managed Kubernetes service.",
            ),
            Service(
                "S3",
                "Storage",
                ServiceModel.PAAS,
                "Highly scalable object storage.",
            ),
            Service(
                "EBS",
                "Storage",
                ServiceModel.IAAS,
                "Persistent block storage for compute instances.",
            ),
            Service(
                "EFS",
                "Storage",
                ServiceModel.PAAS,
                "Managed shared file storage.",
            ),
            Service(
                "VPC",
                "Networking",
                ServiceModel.IAAS,
                "Logically isolated virtual network.",
            ),
            Service(
                "RDS",
                "Databases",
                ServiceModel.PAAS,
                "Managed relational database service.",
            ),
            Service(
                "DynamoDB",
                "Databases",
                ServiceModel.PAAS,
                "Managed NoSQL database.",
            ),
            Service(
                "IAM",
                "Identity",
                ServiceModel.PAAS,
                "Identity and access management.",
            ),
            Service(
                "CloudWatch",
                "Observability",
                ServiceModel.PAAS,
                "Metrics, logs, alarms, and monitoring.",
            ),
            Service(
                "CloudFront",
                "Edge",
                ServiceModel.PAAS,
                "Content delivery network.",
            ),
        ],
    )

    azure = CloudProvider(
        name="Microsoft Azure",
        abbreviation="Azure",
        architecture=GlobalArchitecture(
            provider="Azure",
            regions=[
                Region(
                    "Azure",
                    "eastus",
                    "East US",
                    ("eastus-1", "eastus-2", "eastus-3"),
                ),
                Region(
                    "Azure",
                    "westeurope",
                    "West Europe",
                    ("westeurope-1", "westeurope-2", "westeurope-3"),
                ),
                Region(
                    "Azure",
                    "centralindia",
                    "Central India",
                    (
                        "centralindia-1",
                        "centralindia-2",
                        "centralindia-3",
                    ),
                ),
            ],
            edge_locations=[
                EdgeLocation("Azure", "Mumbai", "azure-edge-mum"),
                EdgeLocation("Azure", "Singapore", "azure-edge-sin"),
                EdgeLocation("Azure", "Amsterdam", "azure-edge-ams"),
            ],
        ),
        services=[
            Service(
                "Azure Virtual Machines",
                "Compute",
                ServiceModel.IAAS,
                "On-demand virtual machines.",
            ),
            Service(
                "Azure Functions",
                "Compute",
                ServiceModel.SERVERLESS,
                "Event-driven serverless functions.",
            ),
            Service(
                "Azure Kubernetes Service",
                "Containers",
                ServiceModel.PAAS,
                "Managed Kubernetes platform.",
            ),
            Service(
                "Azure Blob Storage",
                "Storage",
                ServiceModel.PAAS,
                "Object storage for unstructured data.",
            ),
            Service(
                "Azure Managed Disks",
                "Storage",
                ServiceModel.IAAS,
                "Managed persistent block storage.",
            ),
            Service(
                "Azure Files",
                "Storage",
                ServiceModel.PAAS,
                "Managed cloud file shares.",
            ),
            Service(
                "Azure Virtual Network",
                "Networking",
                ServiceModel.IAAS,
                "Private virtual networking environment.",
            ),
            Service(
                "Azure SQL Database",
                "Databases",
                ServiceModel.PAAS,
                "Managed relational database.",
            ),
            Service(
                "Cosmos DB",
                "Databases",
                ServiceModel.PAAS,
                "Distributed multi-model database.",
            ),
            Service(
                "Microsoft Entra ID",
                "Identity",
                ServiceModel.PAAS,
                "Cloud identity and access management.",
            ),
            Service(
                "Azure Monitor",
                "Observability",
                ServiceModel.PAAS,
                "Metrics, logs, traces, and monitoring.",
            ),
            Service(
                "Azure Front Door",
                "Edge",
                ServiceModel.PAAS,
                "Global application delivery and acceleration.",
            ),
        ],
    )

    gcp = CloudProvider(
        name="Google Cloud",
        abbreviation="GCP",
        architecture=GlobalArchitecture(
            provider="GCP",
            regions=[
                Region(
                    "GCP",
                    "us-central1",
                    "Iowa",
                    ("us-central1-a", "us-central1-b", "us-central1-c"),
                ),
                Region(
                    "GCP",
                    "europe-west1",
                    "Belgium",
                    (
                        "europe-west1-b",
                        "europe-west1-c",
                        "europe-west1-d",
                    ),
                ),
                Region(
                    "GCP",
                    "asia-south1",
                    "Mumbai",
                    (
                        "asia-south1-a",
                        "asia-south1-b",
                        "asia-south1-c",
                    ),
                ),
            ],
            edge_locations=[
                EdgeLocation("GCP", "Mumbai", "gcp-edge-mum"),
                EdgeLocation("GCP", "Singapore", "gcp-edge-sin"),
                EdgeLocation("GCP", "Frankfurt", "gcp-edge-fra"),
            ],
        ),
        services=[
            Service(
                "Compute Engine",
                "Compute",
                ServiceModel.IAAS,
                "Virtual machine infrastructure.",
            ),
            Service(
                "Cloud Run",
                "Compute",
                ServiceModel.SERVERLESS,
                "Managed container execution.",
            ),
            Service(
                "Cloud Functions",
                "Compute",
                ServiceModel.SERVERLESS,
                "Event-driven function execution.",
            ),
            Service(
                "Google Kubernetes Engine",
                "Containers",
                ServiceModel.PAAS,
                "Managed Kubernetes platform.",
            ),
            Service(
                "Cloud Storage",
                "Storage",
                ServiceModel.PAAS,
                "Object storage service.",
            ),
            Service(
                "Persistent Disk",
                "Storage",
                ServiceModel.IAAS,
                "Persistent block storage.",
            ),
            Service(
                "Filestore",
                "Storage",
                ServiceModel.PAAS,
                "Managed file storage.",
            ),
            Service(
                "Virtual Private Cloud",
                "Networking",
                ServiceModel.IAAS,
                "Virtual private networking.",
            ),
            Service(
                "Cloud SQL",
                "Databases",
                ServiceModel.PAAS,
                "Managed relational databases.",
            ),
            Service(
                "Firestore",
                "Databases",
                ServiceModel.PAAS,
                "Document-oriented NoSQL database.",
            ),
            Service(
                "Cloud IAM",
                "Identity",
                ServiceModel.PAAS,
                "Identity and access management.",
            ),
            Service(
                "Cloud Monitoring",
                "Observability",
                ServiceModel.PAAS,
                "Infrastructure and application monitoring.",
            ),
            Service(
                "Cloud CDN",
                "Edge",
                ServiceModel.PAAS,
                "Content delivery network.",
            ),
        ],
    )

    oci = CloudProvider(
        name="Oracle Cloud Infrastructure",
        abbreviation="OCI",
        architecture=GlobalArchitecture(
            provider="OCI",
            regions=[
                Region(
                    "OCI",
                    "us-ashburn-1",
                    "Ashburn",
                    ("ad-1", "ad-2", "ad-3"),
                ),
                Region(
                    "OCI",
                    "uk-london-1",
                    "London",
                    ("ad-1", "ad-2", "ad-3"),
                ),
                Region(
                    "OCI",
                    "ap-mumbai-1",
                    "Mumbai",
                    ("ad-1", "ad-2", "ad-3"),
                ),
            ],
            edge_locations=[
                EdgeLocation("OCI", "Mumbai", "oci-edge-mum"),
                EdgeLocation("OCI", "London", "oci-edge-lon"),
            ],
        ),
        services=[
            Service(
                "Compute",
                "Compute",
                ServiceModel.IAAS,
                "Virtual machines and bare metal compute.",
            ),
            Service(
                "Functions",
                "Compute",
                ServiceModel.SERVERLESS,
                "Serverless function execution.",
            ),
            Service(
                "Container Engine for Kubernetes",
                "Containers",
                ServiceModel.PAAS,
                "Managed Kubernetes.",
            ),
            Service(
                "Object Storage",
                "Storage",
                ServiceModel.PAAS,
                "Object storage service.",
            ),
            Service(
                "Block Volume",
                "Storage",
                ServiceModel.IAAS,
                "Persistent block storage.",
            ),
            Service(
                "Virtual Cloud Network",
                "Networking",
                ServiceModel.IAAS,
                "Virtual networking service.",
            ),
            Service(
                "Autonomous Database",
                "Databases",
                ServiceModel.PAAS,
                "Managed automated database platform.",
            ),
            Service(
                "Identity and Access Management",
                "Identity",
                ServiceModel.PAAS,
                "Authentication and authorization services.",
            ),
        ],
    )

    ibm = CloudProvider(
        name="IBM Cloud",
        abbreviation="IBM",
        architecture=GlobalArchitecture(
            provider="IBM",
            regions=[
                Region(
                    "IBM",
                    "us-south",
                    "Dallas",
                    ("zone-1", "zone-2", "zone-3"),
                ),
                Region(
                    "IBM",
                    "eu-de",
                    "Frankfurt",
                    ("zone-1", "zone-2", "zone-3"),
                ),
            ],
            edge_locations=[
                EdgeLocation("IBM", "Frankfurt", "ibm-edge-fra"),
                EdgeLocation("IBM", "Dallas", "ibm-edge-dal"),
            ],
        ),
        services=[
            Service(
                "Virtual Servers",
                "Compute",
                ServiceModel.IAAS,
                "Virtual server infrastructure.",
            ),
            Service(
                "Code Engine",
                "Compute",
                ServiceModel.SERVERLESS,
                "Managed application and job execution.",
            ),
            Service(
                "Kubernetes Service",
                "Containers",
                ServiceModel.PAAS,
                "Managed Kubernetes.",
            ),
            Service(
                "Cloud Object Storage",
                "Storage",
                ServiceModel.PAAS,
                "Distributed object storage.",
            ),
            Service(
                "Virtual Private Cloud",
                "Networking",
                ServiceModel.IAAS,
                "Isolated virtual networking.",
            ),
        ],
    )

    digitalocean = CloudProvider(
        name="DigitalOcean",
        abbreviation="DO",
        architecture=GlobalArchitecture(
            provider="DigitalOcean",
            regions=[
                Region(
                    "DigitalOcean",
                    "nyc3",
                    "New York",
                    ("nyc3-1", "nyc3-2", "nyc3-3"),
                ),
                Region(
                    "DigitalOcean",
                    "blr1",
                    "Bengaluru",
                    ("blr1-1", "blr1-2", "blr1-3"),
                ),
            ],
            edge_locations=[],
        ),
        services=[
            Service(
                "Droplets",
                "Compute",
                ServiceModel.IAAS,
                "Virtual machines.",
            ),
            Service(
                "App Platform",
                "Compute",
                ServiceModel.PAAS,
                "Managed application platform.",
            ),
            Service(
                "Kubernetes",
                "Containers",
                ServiceModel.PAAS,
                "Managed Kubernetes.",
            ),
            Service(
                "Spaces",
                "Storage",
                ServiceModel.PAAS,
                "S3-compatible object storage.",
            ),
            Service(
                "Volumes",
                "Storage",
                ServiceModel.IAAS,
                "Block storage.",
            ),
            Service(
                "VPC",
                "Networking",
                ServiceModel.IAAS,
                "Private virtual networking.",
            ),
            Service(
                "Managed Databases",
                "Databases",
                ServiceModel.PAAS,
                "Managed database services.",
            ),
        ],
    )

    return {
        provider.abbreviation: provider
        for provider in (
            aws,
            azure,
            gcp,
            oci,
            ibm,
            digitalocean,
        )
    }


# =============================================================================
# 5. CROSS-PROVIDER SERVICE COMPARISON
# =============================================================================


@dataclass(frozen=True)
class ServiceMapping:
    """Represents conceptually comparable services across providers."""

    concept: str
    aws: str
    azure: str
    gcp: str
    oci: str


SERVICE_MAPPINGS = [
    ServiceMapping(
        "Virtual Machines",
        "EC2",
        "Azure Virtual Machines",
        "Compute Engine",
        "Compute",
    ),
    ServiceMapping(
        "Object Storage",
        "S3",
        "Azure Blob Storage",
        "Cloud Storage",
        "Object Storage",
    ),
    ServiceMapping(
        "Managed Kubernetes",
        "EKS",
        "Azure Kubernetes Service",
        "Google Kubernetes Engine",
        "Container Engine for Kubernetes",
    ),
    ServiceMapping(
        "Serverless Functions",
        "Lambda",
        "Azure Functions",
        "Cloud Functions",
        "Functions",
    ),
    ServiceMapping(
        "Virtual Network",
        "VPC",
        "Azure Virtual Network",
        "Virtual Private Cloud",
        "Virtual Cloud Network",
    ),
    ServiceMapping(
        "Managed Relational Database",
        "RDS",
        "Azure SQL Database",
        "Cloud SQL",
        "Autonomous Database",
    ),
]


def print_service_comparison() -> None:
    """Print a simplified conceptual service comparison."""

    print("\nCROSS-PROVIDER SERVICE COMPARISON")
    print("-" * 100)

    for mapping in SERVICE_MAPPINGS:
        print(f"\nConcept: {mapping.concept}")
        print(f"  AWS:   {mapping.aws}")
        print(f"  Azure: {mapping.azure}")
        print(f"  GCP:   {mapping.gcp}")
        print(f"  OCI:   {mapping.oci}")


# =============================================================================
# 6. COMPUTE FUNDAMENTALS
# =============================================================================


@dataclass
class VirtualMachine:
    """
    Simplified virtual machine.

    A VM abstracts physical server hardware into a configurable software-defined
    compute environment.

    Common characteristics:
    - CPU capacity
    - Memory capacity
    - Operating system
    - Attached storage
    - Network interfaces
    - Lifecycle state
    """

    instance_id: str
    region: str
    zone: str
    vcpus: int
    memory_gb: int
    operating_system: str
    state: ResourceState = ResourceState.PROVISIONING
    cpu_utilization: float = 0.0

    def start(self) -> None:
        if self.state == ResourceState.DELETED:
            raise RuntimeError("A deleted VM cannot be restarted.")

        self.state = ResourceState.RUNNING

    def stop(self) -> None:
        if self.state != ResourceState.RUNNING:
            raise RuntimeError("Only a running VM can be stopped.")

        self.state = ResourceState.STOPPED
        self.cpu_utilization = 0.0

    def simulate_workload(self, cpu_percent: float) -> None:
        if self.state != ResourceState.RUNNING:
            raise RuntimeError("Workload cannot run on a non-running VM.")

        if not 0 <= cpu_percent <= 100:
            raise ValueError("CPU utilization must be between 0 and 100.")

        self.cpu_utilization = cpu_percent


def demonstrate_virtual_machine() -> None:
    print("\nVIRTUAL MACHINE EXAMPLE")
    print("-" * 100)

    vm = VirtualMachine(
        instance_id="vm-001",
        region="ap-south-1",
        zone="ap-south-1a",
        vcpus=4,
        memory_gb=16,
        operating_system="Linux",
    )

    print("Initial state:", vm.state.value)

    vm.start()
    vm.simulate_workload(67.5)

    print("Running state:", vm.state.value)
    print("CPU utilization:", vm.cpu_utilization)


# =============================================================================
# 7. AUTOSCALING
# =============================================================================


@dataclass
class AutoScalingGroup:
    """
    A simplified autoscaling model.

    Real autoscaling systems can use:
    - CPU utilization
    - Memory utilization
    - Request counts
    - Queue length
    - Custom application metrics
    - Scheduled rules
    - Predictive models

    Scaling introduces trade-offs. More instances improve capacity and resilience,
    but increase cost. Aggressive scaling can also cause oscillation.
    """

    min_instances: int
    max_instances: int
    target_cpu: float
    current_instances: int

    def validate(self) -> None:
        if self.min_instances < 1:
            raise ValueError("Minimum instances must be at least 1.")

        if self.max_instances < self.min_instances:
            raise ValueError(
                "Maximum instances cannot be smaller than minimum instances."
            )

        if not self.min_instances <= self.current_instances <= self.max_instances:
            raise ValueError(
                "Current instance count must remain within scaling bounds."
            )

        if not 0 < self.target_cpu < 100:
            raise ValueError("Target CPU should be between 0 and 100.")

    def evaluate(self, average_cpu: float) -> str:
        self.validate()

        if average_cpu > self.target_cpu + 10:
            if self.current_instances < self.max_instances:
                self.current_instances += 1
                return "Scaled out by one instance."
            return "At maximum capacity."

        if average_cpu < self.target_cpu - 20:
            if self.current_instances > self.min_instances:
                self.current_instances -= 1
                return "Scaled in by one instance."
            return "At minimum capacity."

        return "No scaling action."


def demonstrate_autoscaling() -> None:
    print("\nAUTOSCALING EXAMPLE")
    print("-" * 100)

    group = AutoScalingGroup(
        min_instances=2,
        max_instances=10,
        target_cpu=60,
        current_instances=3,
    )

    workloads = [30, 55, 76, 90, 50, 20]

    for cpu in workloads:
        result = group.evaluate(cpu)
        print(
            f"Average CPU: {cpu:>5}% | "
            f"Instances: {group.current_instances} | {result}"
        )


# =============================================================================
# 8. STORAGE FUNDAMENTALS
# =============================================================================


class StorageType(str, Enum):
    """Major infrastructure storage categories."""

    OBJECT = "object"
    BLOCK = "block"
    FILE = "file"


@dataclass
class StorageObject:
    """An object stored in an object storage system."""

    key: str
    content: bytes
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


class ObjectStorageBucket:
    """
    Simplified object storage.

    Object storage usually organizes data as:
        bucket/container -> object key -> object data + metadata

    Object storage is different from a traditional mounted file system:
    - Data is accessed through APIs.
    - Objects commonly have key-based identifiers.
    - Prefixes may resemble directories but are not always physical directories.
    """

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("Bucket name cannot be empty.")

        self.name = name
        self._objects: Dict[str, StorageObject] = {}

    def put_object(
        self,
        key: str,
        content: bytes,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StorageObject:
        if not key:
            raise ValueError("Object key cannot be empty.")

        if not isinstance(content, bytes):
            raise TypeError("Object content must be bytes.")

        obj = StorageObject(
            key=key,
            content=content,
            metadata=metadata or {},
        )

        self._objects[key] = obj
        return obj

    def get_object(self, key: str) -> StorageObject:
        if key not in self._objects:
            raise KeyError(f"Object not found: {key}")

        return self._objects[key]

    def delete_object(self, key: str) -> None:
        if key not in self._objects:
            raise KeyError(f"Object not found: {key}")

        del self._objects[key]

    def list_objects(self, prefix: str = "") -> List[str]:
        return sorted(
            key
            for key in self._objects
            if key.startswith(prefix)
        )


def demonstrate_storage() -> None:
    print("\nOBJECT STORAGE EXAMPLE")
    print("-" * 100)

    bucket = ObjectStorageBucket("application-data")

    uploaded = bucket.put_object(
        key="reports/2026/report.txt",
        content=b"Cloud infrastructure report",
        metadata={
            "department": "engineering",
            "classification": "internal",
        },
    )

    print("Object key:", uploaded.key)
    print("Object size:", uploaded.size_bytes)
    print("SHA-256 checksum:", uploaded.checksum[:16] + "...")

    print("Objects under reports/:", bucket.list_objects("reports/"))

    retrieved = bucket.get_object("reports/2026/report.txt")
    print("Retrieved content:", retrieved.content.decode())


# =============================================================================
# 9. NETWORKING FUNDAMENTALS
# =============================================================================


@dataclass(frozen=True)
class CIDRBlock:
    """
    A simplified IPv4 CIDR representation.

    CIDR notation such as 10.0.0.0/16 identifies a network prefix.

    This class does not implement every networking operation. It focuses on
    validation and capacity calculation.
    """

    network: str
    prefix_length: int

    def __post_init__(self) -> None:
        octets = self.network.split(".")

        if len(octets) != 4:
            raise ValueError("IPv4 network must contain four octets.")

        for octet in octets:
            if not octet.isdigit() or not 0 <= int(octet) <= 255:
                raise ValueError("Invalid IPv4 address.")

        if not 0 <= self.prefix_length <= 32:
            raise ValueError("Prefix length must be between 0 and 32.")

    @property
    def address_count(self) -> int:
        return 2 ** (32 - self.prefix_length)

    def __str__(self) -> str:
        return f"{self.network}/{self.prefix_length}"


@dataclass
class Subnet:
    """
    A subnet is a smaller network inside a larger virtual network.

    Public versus private subnet is a routing property rather than simply a
    property of the IP address. A subnet is generally considered public when
    routing permits direct internet access through an internet gateway.
    """

    name: str
    cidr: CIDRBlock
    zone: str
    public: bool


@dataclass
class VirtualNetwork:
    """
    Simplified virtual network.

    Cloud networking commonly includes:
    - Virtual network address range
    - Subnets
    - Route tables
    - Internet connectivity
    - NAT
    - Security groups or firewall rules
    - Network ACLs
    - Private connectivity
    """

    name: str
    cidr: CIDRBlock
    subnets: List[Subnet] = field(default_factory=list)

    def add_subnet(self, subnet: Subnet) -> None:
        if any(existing.name == subnet.name for existing in self.subnets):
            raise ValueError("Subnet names must be unique.")

        self.subnets.append(subnet)

    def public_subnets(self) -> List[Subnet]:
        return [subnet for subnet in self.subnets if subnet.public]

    def private_subnets(self) -> List[Subnet]:
        return [subnet for subnet in self.subnets if not subnet.public]


def demonstrate_networking() -> VirtualNetwork:
    print("\nVIRTUAL NETWORK EXAMPLE")
    print("-" * 100)

    network = VirtualNetwork(
        name="production-vpc",
        cidr=CIDRBlock("10.0.0.0", 16),
    )

    network.add_subnet(
        Subnet(
            name="public-zone-a",
            cidr=CIDRBlock("10.0.1.0", 24),
            zone="zone-a",
            public=True,
        )
    )

    network.add_subnet(
        Subnet(
            name="private-zone-a",
            cidr=CIDRBlock("10.0.10.0", 24),
            zone="zone-a",
            public=False,
        )
    )

    network.add_subnet(
        Subnet(
            name="private-zone-b",
            cidr=CIDRBlock("10.0.20.0", 24),
            zone="zone-b",
            public=False,
        )
    )

    print("VPC:", network.name)
    print("Network CIDR:", network.cidr)
    print("Total theoretical addresses:", network.cidr.address_count)

    print("Public subnets:")
    for subnet in network.public_subnets():
        print(f"  {subnet.name}: {subnet.cidr}")

    print("Private subnets:")
    for subnet in network.private_subnets():
        print(f"  {subnet.name}: {subnet.cidr}")

    return network


# =============================================================================
# 10. LOAD BALANCING AND HEALTH CHECKS
# =============================================================================


@dataclass
class Backend:
    """A backend service target."""

    backend_id: str
    zone: str
    healthy: bool = True
    active_requests: int = 0


class LoadBalancer:
    """
    Round-robin load balancer with health-aware routing.

    Real load balancers may support:
    - Layer 4 routing
    - Layer 7 routing
    - Path-based routing
    - Host-based routing
    - Weighted routing
    - Sticky sessions
    - TLS termination
    - Web application firewall integration
    """

    def __init__(self, backends: List[Backend]) -> None:
        if not backends:
            raise ValueError("At least one backend is required.")

        self.backends = backends
        self._counter = itertools.count()

    def healthy_backends(self) -> List[Backend]:
        return [backend for backend in self.backends if backend.healthy]

    def route_request(self) -> Backend:
        healthy = self.healthy_backends()

        if not healthy:
            raise RuntimeError("No healthy backend is available.")

        index = next(self._counter) % len(healthy)
        backend = healthy[index]
        backend.active_requests += 1
        return backend


def demonstrate_load_balancing() -> None:
    print("\nLOAD BALANCING EXAMPLE")
    print("-" * 100)

    load_balancer = LoadBalancer(
        [
            Backend("api-a", "zone-a"),
            Backend("api-b", "zone-b"),
            Backend("api-c", "zone-c"),
        ]
    )

    for request_number in range(1, 7):
        backend = load_balancer.route_request()
        print(
            f"Request {request_number} routed to "
            f"{backend.backend_id} in {backend.zone}"
        )

    load_balancer.backends[1].healthy = False

    print("\nAfter api-b health check failure:")

    for request_number in range(7, 11):
        backend = load_balancer.route_request()
        print(
            f"Request {request_number} routed to "
            f"{backend.backend_id}"
        )


# =============================================================================
# 11. IDENTITY AND ACCESS MANAGEMENT
# =============================================================================


class PermissionDenied(Exception):
    """Raised when a principal lacks authorization."""


@dataclass
class Role:
    """
    A role groups permissions.

    Permissions should follow least privilege:
    grant only the minimum actions required for the workload.
    """

    name: str
    permissions: Set[str]


@dataclass
class Principal:
    """
    A principal is an identity that can perform actions.

    Examples:
    - Human user
    - Service account
    - Application workload identity
    - Federated external identity
    """

    name: str
    roles: List[Role] = field(default_factory=list)

    def permissions(self) -> Set[str]:
        combined: Set[str] = set()

        for role in self.roles:
            combined.update(role.permissions)

        return combined

    def authorize(self, action: str) -> None:
        if action not in self.permissions():
            raise PermissionDenied(
                f"{self.name} is not authorized for {action}"
            )


def demonstrate_identity_and_access() -> None:
    print("\nIDENTITY AND ACCESS MANAGEMENT EXAMPLE")
    print("-" * 100)

    reader_role = Role(
        name="storage-reader",
        permissions={"storage.read"},
    )

    writer_role = Role(
        name="storage-writer",
        permissions={"storage.write"},
    )

    analyst = Principal(
        name="analytics-service",
        roles=[reader_role],
    )

    deployment_service = Principal(
        name="deployment-service",
        roles=[reader_role, writer_role],
    )

    for principal, action in [
        (analyst, "storage.read"),
        (analyst, "storage.write"),
        (deployment_service, "storage.write"),
    ]:
        try:
            principal.authorize(action)
            print(f"{principal.name}: ALLOWED -> {action}")
        except PermissionDenied as error:
            print(f"{principal.name}: DENIED -> {error}")


# =============================================================================
# 12. SHARED RESPONSIBILITY MODEL
# =============================================================================


@dataclass(frozen=True)
class Responsibility:
    """Describes who primarily manages an infrastructure layer."""

    layer: str
    provider_responsible: bool
    customer_responsible: bool


def shared_responsibility(service_model: ServiceModel) -> List[Responsibility]:
    """
    Return a conceptual responsibility matrix.

    Exact responsibility boundaries vary by provider and service. The central
    principle is that cloud services transfer some operational responsibility
    to the provider but do not automatically remove customer responsibility for
    configuration, data governance, identity, and application security.
    """

    physical = Responsibility(
        "Physical data centers",
        True,
        False,
    )

    hardware = Responsibility(
        "Physical hardware",
        True,
        False,
    )

    networking = Responsibility(
        "Core infrastructure networking",
        True,
        service_model == ServiceModel.IAAS,
    )

    operating_system = Responsibility(
        "Operating system management",
        service_model != ServiceModel.IAAS,
        service_model == ServiceModel.IAAS,
    )

    application = Responsibility(
        "Application code",
        False,
        service_model != ServiceModel.SAAS,
    )

    data = Responsibility(
        "Data governance and access",
        False,
        service_model != ServiceModel.SAAS,
    )

    return [
        physical,
        hardware,
        networking,
        operating_system,
        application,
        data,
    ]


def demonstrate_shared_responsibility() -> None:
    print("\nSHARED RESPONSIBILITY EXAMPLE")
    print("-" * 100)

    for model in (
        ServiceModel.IAAS,
        ServiceModel.PAAS,
        ServiceModel.SERVERLESS,
        ServiceModel.SAAS,
    ):
        print(f"\n{model.value}")

        for responsibility in shared_responsibility(model):
            parties = []

            if responsibility.provider_responsible:
                parties.append("Provider")

            if responsibility.customer_responsible:
                parties.append("Customer")

            print(
                f"  {responsibility.layer}: "
                f"{' + '.join(parties) if parties else 'Service dependent'}"
            )


# =============================================================================
# 13. RELIABILITY AND MULTI-ZONE ARCHITECTURE
# =============================================================================


@dataclass
class ApplicationReplica:
    """A replica of an application deployed in a failure domain."""

    replica_id: str
    zone: str
    healthy: bool = True


class HighlyAvailableApplication:
    """
    A simple application replicated across availability zones.

    High availability is not the same as disaster recovery.

    High availability:
        Focuses on continuing operation during component failures.

    Disaster recovery:
        Focuses on recovering from larger events, including regional failures,
        corruption, or major operational incidents.
    """

    def __init__(self, replicas: List[ApplicationReplica]) -> None:
        if not replicas:
            raise ValueError("At least one replica is required.")

        self.replicas = replicas

    def available(self) -> bool:
        return any(replica.healthy for replica in self.replicas)

    def available_zones(self) -> Set[str]:
        return {
            replica.zone
            for replica in self.replicas
            if replica.healthy
        }

    def simulate_zone_failure(self, zone: str) -> None:
        for replica in self.replicas:
            if replica.zone == zone:
                replica.healthy = False


def demonstrate_high_availability() -> None:
    print("\nMULTI-ZONE AVAILABILITY EXAMPLE")
    print("-" * 100)

    application = HighlyAvailableApplication(
        [
            ApplicationReplica("app-1", "zone-a"),
            ApplicationReplica("app-2", "zone-b"),
            ApplicationReplica("app-3", "zone-c"),
        ]
    )

    print("Initially available:", application.available())
    print("Healthy zones:", sorted(application.available_zones()))

    application.simulate_zone_failure("zone-b")

    print("After zone-b failure:", application.available())
    print("Remaining healthy zones:", sorted(application.available_zones()))


# =============================================================================
# 14. DISASTER RECOVERY METRICS
# =============================================================================


@dataclass(frozen=True)
class DisasterRecoveryTarget:
    """
    Recovery objectives.

    RPO: Recovery Point Objective
        Maximum acceptable amount of data loss measured in time.

    RTO: Recovery Time Objective
        Maximum acceptable time required to restore service.

    Lower values usually require more redundancy, automation, and cost.
    """

    rpo_minutes: int
    rto_minutes: int

    def validate(self) -> None:
        if self.rpo_minutes < 0:
            raise ValueError("RPO cannot be negative.")

        if self.rto_minutes <= 0:
            raise ValueError("RTO must be greater than zero.")


def classify_dr_strategy(
    target: DisasterRecoveryTarget,
) -> str:
    """
    A conceptual classification.

    Real architectures require detailed workload analysis. This simplified
    function demonstrates the relationship between strict recovery targets and
    architectural complexity.
    """

    target.validate()

    if target.rpo_minutes <= 5 and target.rto_minutes <= 15:
        return "Active-active or highly automated warm standby"

    if target.rpo_minutes <= 60 and target.rto_minutes <= 120:
        return "Warm standby"

    if target.rpo_minutes <= 24 * 60 and target.rto_minutes <= 24 * 60:
        return "Pilot light or backup and restore"

    return "Long-term backup and manual recovery"


def demonstrate_disaster_recovery() -> None:
    print("\nDISASTER RECOVERY EXAMPLE")
    print("-" * 100)

    targets = [
        DisasterRecoveryTarget(5, 15),
        DisasterRecoveryTarget(30, 90),
        DisasterRecoveryTarget(720, 480),
        DisasterRecoveryTarget(2880, 4320),
    ]

    for target in targets:
        print(
            f"RPO={target.rpo_minutes} minutes, "
            f"RTO={target.rto_minutes} minutes -> "
            f"{classify_dr_strategy(target)}"
        )


# =============================================================================
# 15. DATABASE CONCEPTS
# =============================================================================


class DatabaseType(str, Enum):
    RELATIONAL = "Relational"
    DOCUMENT = "Document"
    KEY_VALUE = "Key-Value"
    WIDE_COLUMN = "Wide-Column"
    GRAPH = "Graph"
    TIME_SERIES = "Time-Series"


@dataclass
class DatabaseRequirement:
    """Requirements used for a simplified database selection exercise."""

    strong_relational_queries: bool
    flexible_schema: bool
    extremely_high_key_value_scale: bool
    relationship_traversal: bool
    time_series_workload: bool


def recommend_database_type(
    requirement: DatabaseRequirement,
) -> DatabaseType:
    """
    Demonstrates trade-offs rather than providing a universal database decision.

    Real selection must also consider:
    - Consistency requirements
    - Query patterns
    - Data size
    - Latency
    - Operational expertise
    - Cost
    - Backup and recovery
    """

    if requirement.relationship_traversal:
        return DatabaseType.GRAPH

    if requirement.time_series_workload:
        return DatabaseType.TIME_SERIES

    if requirement.strong_relational_queries:
        return DatabaseType.RELATIONAL

    if requirement.extremely_high_key_value_scale:
        return DatabaseType.KEY_VALUE

    if requirement.flexible_schema:
        return DatabaseType.DOCUMENT

    return DatabaseType.RELATIONAL


def demonstrate_database_selection() -> None:
    print("\nDATABASE SELECTION EXAMPLE")
    print("-" * 100)

    requirements = [
        DatabaseRequirement(
            strong_relational_queries=True,
            flexible_schema=False,
            extremely_high_key_value_scale=False,
            relationship_traversal=False,
            time_series_workload=False,
        ),
        DatabaseRequirement(
            strong_relational_queries=False,
            flexible_schema=True,
            extremely_high_key_value_scale=False,
            relationship_traversal=False,
            time_series_workload=False,
        ),
        DatabaseRequirement(
            strong_relational_queries=False,
            flexible_schema=False,
            extremely_high_key_value_scale=True,
            relationship_traversal=False,
            time_series_workload=False,
        ),
    ]

    for requirement in requirements:
        recommendation = recommend_database_type(requirement)
        print(
            f"Requirements={requirement} -> "
            f"{recommendation.value}"
        )


# =============================================================================
# 16. SERVERLESS COMPUTING
# =============================================================================


@dataclass
class FunctionInvocation:
    """
    Represents one serverless function invocation.

    Billing and execution details differ by provider. Important characteristics
    often include:
    - Invocation count
    - Execution duration
    - Allocated memory
    - Concurrency
    - Cold start behavior
    - Event source
    """

    function_name: str
    event: Dict[str, str]
    duration_ms: int


class ServerlessFunction:
    """Simplified event-driven serverless function."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.invocations: List[FunctionInvocation] = []

    def invoke(self, event: Dict[str, str]) -> Dict[str, str]:
        started = time.perf_counter()

        if "action" not in event:
            raise ValueError("Event must contain an 'action' field.")

        result = {
            "function": self.name,
            "status": "processed",
            "action": event["action"],
        }

        duration_ms = int(
            (time.perf_counter() - started) * 1000
        )

        self.invocations.append(
            FunctionInvocation(
                function_name=self.name,
                event=event,
                duration_ms=max(duration_ms, 1),
            )
        )

        return result


def demonstrate_serverless() -> None:
    print("\nSERVERLESS FUNCTION EXAMPLE")
    print("-" * 100)

    function = ServerlessFunction("image-processing-handler")

    result = function.invoke(
        {
            "action": "resize",
            "object_key": "uploads/photo.jpg",
        }
    )

    print(json.dumps(result, indent=2))
    print("Invocation count:", len(function.invocations))


# =============================================================================
# 17. CONTAINERS AND KUBERNETES CONCEPTS
# =============================================================================


@dataclass
class Container:
    """
    A container packages an application and dependencies.

    Containers differ from virtual machines because multiple containers can share
    the same host operating system kernel while remaining logically isolated.
    """

    name: str
    image: str
    port: int


@dataclass
class Pod:
    """
    Simplified Kubernetes pod.

    A pod is a scheduling unit that can contain one or more containers.
    """

    name: str
    containers: List[Container]
    healthy: bool = True


@dataclass
class KubernetesDeployment:
    """
    Simplified deployment controller.

    Desired state is central to declarative orchestration. A controller attempts
    to reconcile actual state with desired state.
    """

    name: str
    desired_replicas: int
    pods: List[Pod] = field(default_factory=list)

    def reconcile(self) -> None:
        """
        Restore the desired number of healthy pods.

        This is a simplified model. Production orchestration includes scheduling,
        node capacity, image pulls, readiness probes, rolling updates, and more.
        """

        self.pods = [pod for pod in self.pods if pod.healthy]

        while len(self.pods) < self.desired_replicas:
            number = len(self.pods) + 1

            self.pods.append(
                Pod(
                    name=f"{self.name}-{number}",
                    containers=[
                        Container(
                            name="application",
                            image="example/application:1.0",
                            port=8080,
                        )
                    ],
                )
            )

        while len(self.pods) > self.desired_replicas:
            self.pods.pop()


def demonstrate_kubernetes() -> None:
    print("\nKUBERNETES DESIRED STATE EXAMPLE")
    print("-" * 100)

    deployment = KubernetesDeployment(
        name="web-api",
        desired_replicas=3,
    )

    deployment.reconcile()

    print(
        "Initial pods:",
        [pod.name for pod in deployment.pods],
    )

    deployment.pods[1].healthy = False
    deployment.reconcile()

    print(
        "After unhealthy pod reconciliation:",
        [pod.name for pod in deployment.pods],
    )


# =============================================================================
# 18. INFRASTRUCTURE AS CODE CONCEPTS
# =============================================================================


@dataclass
class InfrastructureResource:
    """Declarative representation of infrastructure."""

    resource_type: str
    name: str
    configuration: Dict[str, object]


class InfrastructureState:
    """
    Tracks desired and actual infrastructure.

    Infrastructure as Code benefits include:
    - Repeatability
    - Version control
    - Peer review
    - Automation
    - Reduced configuration drift

    A production IaC system must carefully manage state, credentials, locking,
    secrets, dependencies, and destructive operations.
    """

    def __init__(self) -> None:
        self.resources: Dict[str, InfrastructureResource] = {}

    @staticmethod
    def _resource_id(resource: InfrastructureResource) -> str:
        return f"{resource.resource_type}:{resource.name}"

    def apply(
        self,
        desired_resources: List[InfrastructureResource],
    ) -> List[str]:
        actions: List[str] = []
        desired_ids = {
            self._resource_id(resource)
            for resource in desired_resources
        }

        for resource in desired_resources:
            resource_id = self._resource_id(resource)

            if resource_id not in self.resources:
                actions.append(f"CREATE {resource_id}")
            elif self.resources[resource_id] != resource:
                actions.append(f"UPDATE {resource_id}")
            else:
                actions.append(f"NO CHANGE {resource_id}")

            self.resources[resource_id] = resource

        for resource_id in list(self.resources):
            if resource_id not in desired_ids:
                actions.append(f"DELETE {resource_id}")
                del self.resources[resource_id]

        return actions


def demonstrate_infrastructure_as_code() -> None:
    print("\nINFRASTRUCTURE AS CODE EXAMPLE")
    print("-" * 100)

    state = InfrastructureState()

    desired = [
        InfrastructureResource(
            resource_type="network",
            name="production-vpc",
            configuration={"cidr": "10.0.0.0/16"},
        ),
        InfrastructureResource(
            resource_type="compute",
            name="web-server",
            configuration={"vcpus": 2, "memory_gb": 8},
        ),
    ]

    for action in state.apply(desired):
        print(action)

    print("\nApplying the same desired state again:")

    for action in state.apply(desired):
        print(action)


# =============================================================================
# 19. OBSERVABILITY
# =============================================================================


@dataclass
class Metric:
    """A numerical observation associated with a resource."""

    name: str
    value: float
    unit: str
    timestamp: float


class MetricsStore:
    """
    Stores metrics and calculates simple aggregates.

    Observability usually combines:
    - Metrics: numerical measurements
    - Logs: detailed event records
    - Traces: request paths across distributed services
    """

    def __init__(self) -> None:
        self.metrics: List[Metric] = []

    def record(self, name: str, value: float, unit: str) -> None:
        self.metrics.append(
            Metric(
                name=name,
                value=value,
                unit=unit,
                timestamp=time.time(),
            )
        )

    def average(self, name: str) -> Optional[float]:
        values = [
            metric.value
            for metric in self.metrics
            if metric.name == name
        ]

        if not values:
            return None

        return sum(values) / len(values)


@dataclass
class Alarm:
    """Threshold-based alert rule."""

    metric_name: str
    threshold: float

    def evaluate(
        self,
        metrics_store: MetricsStore,
    ) -> bool:
        value = metrics_store.average(self.metric_name)

        return value is not None and value > self.threshold


def demonstrate_observability() -> None:
    print("\nOBSERVABILITY EXAMPLE")
    print("-" * 100)

    metrics = MetricsStore()

    for value in [45, 62, 78, 91]:
        metrics.record("cpu_utilization", value, "percent")

    average_cpu = metrics.average("cpu_utilization")

    alarm = Alarm(
        metric_name="cpu_utilization",
        threshold=70,
    )

    print("Average CPU:", average_cpu)
    print("Alarm triggered:", alarm.evaluate(metrics))


# =============================================================================
# 20. CLOUD COST MODELING
# =============================================================================


@dataclass
class UsageItem:
    """
    Represents measured usage.

    Cloud billing often includes:
    - Compute time
    - Storage capacity
    - Requests
    - Data transfer
    - Database capacity
    - Managed service consumption
    """

    resource_type: str
    quantity: float
    unit_price: float

    @property
    def cost(self) -> float:
        return self.quantity * self.unit_price


class CloudBill:
    """A simplified monthly cloud bill."""

    def __init__(self) -> None:
        self.items: List[UsageItem] = []

    def add_usage(
        self,
        resource_type: str,
        quantity: float,
        unit_price: float,
    ) -> None:
        if quantity < 0:
            raise ValueError("Usage quantity cannot be negative.")

        if unit_price < 0:
            raise ValueError("Unit price cannot be negative.")

        self.items.append(
            UsageItem(
                resource_type,
                quantity,
                unit_price,
            )
        )

    def total_cost(self) -> float:
        return sum(item.cost for item in self.items)

    def cost_by_resource_type(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}

        for item in self.items:
            totals[item.resource_type] = (
                totals.get(item.resource_type, 0.0)
                + item.cost
            )

        return totals


def demonstrate_cost_management() -> None:
    print("\nCLOUD COST MODEL EXAMPLE")
    print("-" * 100)

    bill = CloudBill()

    bill.add_usage("Virtual Machines", 720, 0.08)
    bill.add_usage("Object Storage GB-month", 500, 0.02)
    bill.add_usage("Load Balancer Hours", 720, 0.025)
    bill.add_usage("Data Transfer GB", 250, 0.09)

    for resource_type, cost in bill.cost_by_resource_type().items():
        print(f"{resource_type}: ${cost:.2f}")

    print(f"Total: ${bill.total_cost():.2f}")


# =============================================================================
# 21. CLOUD SECURITY PRINCIPLES
# =============================================================================


@dataclass
class SecurityControl:
    """Represents a security control category."""

    name: str
    purpose: str
    example: str


SECURITY_CONTROLS = [
    SecurityControl(
        "Identity",
        "Authenticate users and workloads.",
        "Multi-factor authentication and workload identities.",
    ),
    SecurityControl(
        "Least Privilege",
        "Limit permissions to required actions.",
        "Role grants only required storage read access.",
    ),
    SecurityControl(
        "Encryption",
        "Protect data confidentiality.",
        "TLS in transit and encryption at rest.",
    ),
    SecurityControl(
        "Network Segmentation",
        "Reduce unnecessary network exposure.",
        "Private database subnets without direct internet access.",
    ),
    SecurityControl(
        "Secrets Management",
        "Avoid exposing credentials in source code.",
        "Store database credentials in a managed secret system.",
    ),
    SecurityControl(
        "Logging",
        "Support auditing and incident investigation.",
        "Record identity and infrastructure changes.",
    ),
]


def demonstrate_security_controls() -> None:
    print("\nCLOUD SECURITY CONTROLS")
    print("-" * 100)

    for control in SECURITY_CONTROLS:
        print(f"\n{control.name}")
        print("  Purpose:", control.purpose)
        print("  Example:", control.example)


# =============================================================================
# 22. MULTI-CLOUD PORTABILITY AND LOCK-IN
# =============================================================================


@dataclass
class ApplicationArchitecture:
    """
    Describes dependencies affecting portability.

    Cloud portability is not binary.

    Virtual machines may be relatively portable conceptually, but image formats,
    networking, IAM, automation, monitoring, and storage semantics still differ.

    Managed proprietary services can reduce operational effort but may increase
    migration complexity.
    """

    uses_standard_containers: bool
    uses_managed_kubernetes: bool
    uses_provider_specific_serverless: bool
    uses_provider_specific_database: bool
    uses_infrastructure_as_code: bool


def estimate_portability_score(
    architecture: ApplicationArchitecture,
) -> int:
    """
    Produce a conceptual portability score from 0 to 100.

    This is not a real cloud migration formula.
    It demonstrates how architectural choices influence portability.
    """

    score = 50

    if architecture.uses_standard_containers:
        score += 20

    if architecture.uses_managed_kubernetes:
        score += 10

    if architecture.uses_infrastructure_as_code:
        score += 10

    if architecture.uses_provider_specific_serverless:
        score -= 15

    if architecture.uses_provider_specific_database:
        score -= 20

    return max(0, min(100, score))


def demonstrate_portability() -> None:
    print("\nMULTI-CLOUD PORTABILITY EXAMPLE")
    print("-" * 100)

    architecture = ApplicationArchitecture(
        uses_standard_containers=True,
        uses_managed_kubernetes=True,
        uses_provider_specific_serverless=False,
        uses_provider_specific_database=True,
        uses_infrastructure_as_code=True,
    )

    score = estimate_portability_score(architecture)

    print("Architecture:", architecture)
    print("Conceptual portability score:", score, "/ 100")


# =============================================================================
# 23. REGION SELECTION
# =============================================================================


@dataclass(frozen=True)
class RegionRequirement:
    """
    Requirements affecting region selection.

    Region selection may depend on:
    - User latency
    - Data residency
    - Service availability
    - Disaster recovery
    - Cost
    - Existing enterprise connectivity
    """

    preferred_location: str
    required_zone_count: int
    requires_edge_presence: bool


def select_region(
    provider: CloudProvider,
    requirement: RegionRequirement,
) -> Optional[Region]:
    """
    Select a region using a simplified score.

    Real region selection should use measured latency and verified service
    availability rather than relying only on geographic labels.
    """

    candidates = []

    for region in provider.architecture.regions:
        if len(region.zones) < requirement.required_zone_count:
            continue

        score = 0

        if requirement.preferred_location.lower() in region.location.lower():
            score += 100

        if requirement.requires_edge_presence:
            matching_edges = [
                edge
                for edge in provider.architecture.edge_locations
                if requirement.preferred_location.lower()
                in edge.city.lower()
            ]

            score += 25 if matching_edges else 0

        candidates.append((score, region))

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            len(item[1].zones),
        ),
        reverse=True,
    )

    return candidates[0][1]


def demonstrate_region_selection(
    providers: Dict[str, CloudProvider],
) -> None:
    print("\nREGION SELECTION EXAMPLE")
    print("-" * 100)

    requirement = RegionRequirement(
        preferred_location="Mumbai",
        required_zone_count=3,
        requires_edge_presence=True,
    )

    for abbreviation in ("AWS", "Azure", "GCP", "OCI"):
        provider = providers[abbreviation]
        region = select_region(provider, requirement)

        if region:
            print(
                f"{provider.name}: selected {region.code} "
                f"({region.location})"
            )
        else:
            print(f"{provider.name}: no matching region")


# =============================================================================
# 24. PRODUCTION WEB APPLICATION ARCHITECTURE
# =============================================================================


@dataclass
class ProductionArchitecture:
    """
    A simplified production architecture.

    Typical request path:

        User
          |
          v
        DNS / Edge
          |
          v
        Web Application Firewall
          |
          v
        Load Balancer
          |
          +------ Application Replica Zone A
          |
          +------ Application Replica Zone B
          |
          +------ Application Replica Zone C
                          |
                          v
                   Managed Database
                          |
                          v
                    Backup / Recovery

    The actual implementation varies across providers.
    """

    provider: str
    region: str
    availability_tier: AvailabilityTier
    application_replicas: int
    database_multi_zone: bool
    backups_enabled: bool
    monitoring_enabled: bool
    encryption_enabled: bool

    def validate(self) -> List[str]:
        findings: List[str] = []

        if self.application_replicas < 2:
            findings.append(
                "Single application replica creates a major availability risk."
            )

        if (
            self.availability_tier == AvailabilityTier.MULTI_ZONE
            and not self.database_multi_zone
        ):
            findings.append(
                "Application is multi-zone but database is not configured "
                "for equivalent redundancy."
            )

        if not self.backups_enabled:
            findings.append(
                "Backups are disabled, increasing recovery risk."
            )

        if not self.monitoring_enabled:
            findings.append(
                "Monitoring is disabled, reducing failure detection capability."
            )

        if not self.encryption_enabled:
            findings.append(
                "Encryption is disabled, creating a confidentiality risk."
            )

        return findings


def demonstrate_production_architecture() -> None:
    print("\nPRODUCTION ARCHITECTURE VALIDATION")
    print("-" * 100)

    architecture = ProductionArchitecture(
        provider="AWS",
        region="ap-south-1",
        availability_tier=AvailabilityTier.MULTI_ZONE,
        application_replicas=3,
        database_multi_zone=True,
        backups_enabled=True,
        monitoring_enabled=True,
        encryption_enabled=True,
    )

    findings = architecture.validate()

    if findings:
        for finding in findings:
            print("WARNING:", finding)
    else:
        print("No simplified architectural issues detected.")


# =============================================================================
# 25. FAILURE SIMULATION
# =============================================================================


class CloudFailureSimulator:
    """
    Simulates failures across zones.

    Important reliability principle:
    redundancy must exist across meaningful failure boundaries.

    Three replicas inside one availability zone may protect against individual
    process failures but may not protect against a zone-wide outage.
    """

    def __init__(
        self,
        replicas: List[ApplicationReplica],
    ) -> None:
        self.replicas = replicas

    def fail_random_replica(self) -> ApplicationReplica:
        replica = random.choice(self.replicas)
        replica.healthy = False
        return replica

    def fail_zone(self, zone: str) -> List[ApplicationReplica]:
        affected = []

        for replica in self.replicas:
            if replica.zone == zone:
                replica.healthy = False
                affected.append(replica)

        return affected

    def service_available(self) -> bool:
        return any(replica.healthy for replica in self.replicas)

    def healthy_replica_count(self) -> int:
        return sum(
            1
            for replica in self.replicas
            if replica.healthy
        )


def demonstrate_failure_simulation() -> None:
    print("\nFAILURE DOMAIN SIMULATION")
    print("-" * 100)

    replicas = [
        ApplicationReplica("replica-1", "zone-a"),
        ApplicationReplica("replica-2", "zone-b"),
        ApplicationReplica("replica-3", "zone-c"),
    ]

    simulator = CloudFailureSimulator(replicas)

    failed = simulator.fail_random_replica()

    print("Random replica failure:", failed.replica_id)
    print(
        "Healthy replicas:",
        simulator.healthy_replica_count(),
    )
    print(
        "Service available:",
        simulator.service_available(),
    )

    affected = simulator.fail_zone("zone-b")

    print(
        "Zone-b failure affected:",
        [replica.replica_id for replica in affected],
    )
    print(
        "Healthy replicas:",
        simulator.healthy_replica_count(),
    )


# =============================================================================
# 26. COMMON CLOUD ARCHITECTURE MISTAKES
# =============================================================================


COMMON_MISTAKES = {
    "Single availability zone": (
        "A localized zone failure can interrupt the entire application."
    ),
    "Public database exposure": (
        "Databases exposed directly to the internet increase attack surface."
    ),
    "Overly broad IAM permissions": (
        "Compromised identities can cause greater damage."
    ),
    "Secrets in source code": (
        "Credentials may leak through repositories, logs, or build systems."
    ),
    "No backup testing": (
        "A backup is useful only when restoration procedures actually work."
    ),
    "Ignoring cost governance": (
        "Elastic resources can create unexpected cost when left uncontrolled."
    ),
    "No observability": (
        "Failures may be detected late and become difficult to diagnose."
    ),
    "Assuming cloud automatically secures everything": (
        "Customer configuration remains part of the shared responsibility model."
    ),
}


def print_common_mistakes() -> None:
    print("\nCOMMON CLOUD ARCHITECTURE MISTAKES")
    print("-" * 100)

    for mistake, consequence in COMMON_MISTAKES.items():
        print(f"\n{mistake}")
        print("  Risk:", consequence)


# =============================================================================
# 27. PROVIDER OVERVIEW REPORT
# =============================================================================


def print_provider_overview(
    providers: Dict[str, CloudProvider],
) -> None:
    print("\nMAJOR CLOUD PROVIDER OVERVIEW")
    print("=" * 100)

    for provider in providers.values():
        print(f"\n{provider.name} ({provider.abbreviation})")
        print("-" * 80)

        print("Representative regions:")

        for region in provider.architecture.regions:
            print(
                f"  {region.code}: {region.location} "
                f"({len(region.zones)} zones)"
            )

        print("Service categories:")

        for category in provider.categories():
            services = provider.services_by_category(category)

            names = ", ".join(
                service.name
                for service in services
            )

            print(f"  {category}: {names}")


# =============================================================================
# 28. ARCHITECTURAL DECISION EXAMPLE
# =============================================================================


@dataclass
class WorkloadRequirements:
    """Requirements for selecting a conceptual cloud architecture."""

    traffic_is_variable: bool
    requires_container_portability: bool
    requires_managed_database: bool
    global_users: bool
    strict_high_availability: bool


def design_architecture(
    requirements: WorkloadRequirements,
) -> List[str]:
    """
    Select conceptual building blocks.

    This function intentionally selects architectural concepts rather than
    provider-specific services.
    """

    components = []

    if requirements.global_users:
        components.extend(
            [
                "Global DNS",
                "Content Delivery Network",
                "Regional application entry points",
            ]
        )

    components.append("Virtual network with public and private subnets")
    components.append("Identity and access management")

    if requirements.traffic_is_variable:
        components.append("Autoscaling compute platform")

    else:
        components.append("Predictable-capacity compute platform")

    if requirements.requires_container_portability:
        components.append("Container orchestration platform")

    else:
        components.append("Managed application platform")

    if requirements.requires_managed_database:
        components.append("Managed database with backups")

    if requirements.strict_high_availability:
        components.extend(
            [
                "Multi-zone application replicas",
                "Health-aware load balancing",
                "Multi-zone database architecture",
                "Monitoring and automated alerting",
            ]
        )

    components.extend(
        [
            "Centralized logging",
            "Encryption at rest and in transit",
            "Backup and disaster recovery process",
        ]
    )

    return components


def demonstrate_architectural_decision() -> None:
    print("\nARCHITECTURAL DESIGN EXAMPLE")
    print("-" * 100)

    requirements = WorkloadRequirements(
        traffic_is_variable=True,
        requires_container_portability=True,
        requires_managed_database=True,
        global_users=True,
        strict_high_availability=True,
    )

    components = design_architecture(requirements)

    print("Selected conceptual architecture:")

    for number, component in enumerate(
        components,
        start=1,
    ):
        print(f"{number}. {component}")


# =============================================================================
# 29. MAIN PROGRAM
# =============================================================================


def main() -> None:
    """
    Execute all demonstrations.

    Each section is independent enough to be studied separately.
    """

    random.seed(42)

    providers = build_providers()

    print_provider_overview(providers)
    print_service_comparison()

    demonstrate_virtual_machine()
    demonstrate_autoscaling()
    demonstrate_storage()
    demonstrate_networking()
    demonstrate_load_balancing()
    demonstrate_identity_and_access()
    demonstrate_shared_responsibility()
    demonstrate_high_availability()
    demonstrate_disaster_recovery()
    demonstrate_database_selection()
    demonstrate_serverless()
    demonstrate_kubernetes()
    demonstrate_infrastructure_as_code()
    demonstrate_observability()
    demonstrate_cost_management()
    demonstrate_security_controls()
    demonstrate_portability()
    demonstrate_region_selection(providers)
    demonstrate_production_architecture()
    demonstrate_failure_simulation()
    print_common_mistakes()
    demonstrate_architectural_decision()

    print("\n" + "=" * 100)
    print("Cloud Providers Overview demonstration completed.")
    print("=" * 100)


if __name__ == "__main__":
    main()
