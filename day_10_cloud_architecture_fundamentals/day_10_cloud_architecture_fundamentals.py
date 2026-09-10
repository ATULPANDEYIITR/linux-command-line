"""
Cloud Architecture Fundamentals
===============================

A self-contained study and demonstration program covering cloud architecture
from absolute beginner concepts through advanced architectural considerations.

The script uses only the Python standard library.

Topics covered:
    1. Cloud computing foundations
    2. Cloud service models
    3. Cloud deployment models
    4. Regions, availability zones, and points of presence
    5. Compute architecture
    6. Networking architecture
    7. Storage architecture
    8. Databases and data architecture
    9. Application architecture
    10. Load balancing
    11. DNS
    12. Caching and CDNs
    13. Identity and access management
    14. Encryption and secrets
    15. High availability
    16. Scalability and elasticity
    17. Reliability and disaster recovery
    18. Backup strategies
    19. Observability and monitoring
    20. Infrastructure as Code concepts
    21. Containers and orchestration concepts
    22. Serverless architecture
    23. Event-driven architecture
    24. Microservices and distributed systems
    25. API gateways
    26. Queues and asynchronous processing
    27. CAP theorem and consistency
    28. Distributed-system failure modes
    29. Security architecture
    30. Network segmentation
    31. Zero-trust concepts
    32. Cost architecture
    33. Performance architecture
    34. Twelve-factor application concepts
    35. Architectural patterns
    36. Architecture trade-offs
    37. Reference architectures
    38. Architecture decision records
    39. Testing and validation
    40. Production-readiness assessment

The examples intentionally model cloud concepts with Python objects and
simulations rather than connecting to a real cloud provider.
"""

from __future__ import annotations

import base64
import hashlib
import heapq
import json
import math
import random
import secrets
import statistics
import time
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Optional


# =============================================================================
# 1. FOUNDATIONAL TERMINOLOGY
# =============================================================================

print("=" * 80)
print("CLOUD ARCHITECTURE FUNDAMENTALS")
print("=" * 80)


def section(title: str) -> None:
    """Print a consistent heading for each educational section."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


section("1. What Is Cloud Computing?")

print(
    """
Cloud computing is the delivery of computing resources over a network.

Typical cloud resources include:
    - Compute
    - Networking
    - Storage
    - Databases
    - Identity
    - Security services
    - Monitoring
    - Messaging
    - Application platforms

A cloud architecture describes how these resources are organized and how
they communicate to provide an application or business capability.

A simple architecture can be represented as:

    User
      |
      v
    DNS
      |
      v
    Load Balancer
      |
      v
    Application
      |
      +-------------> Cache
      |
      +-------------> Database
      |
      +-------------> Object Storage
      |
      +-------------> Message Queue

The important architectural idea is that these components have different
responsibilities and failure characteristics.
"""
)


class CloudServiceModel(Enum):
    """Common cloud service models."""

    IAAS = "Infrastructure as a Service"
    PAAS = "Platform as a Service"
    SAAS = "Software as a Service"
    FAAS = "Function as a Service"


class DeploymentModel(Enum):
    """Common cloud deployment models."""

    PUBLIC = "Public Cloud"
    PRIVATE = "Private Cloud"
    HYBRID = "Hybrid Cloud"
    MULTI_CLOUD = "Multi-Cloud"


print("Service models:")
for model in CloudServiceModel:
    print(f"  {model.name}: {model.value}")

print("\nDeployment models:")
for model in DeploymentModel:
    print(f"  {model.name}: {model.value}")


# =============================================================================
# 2. SHARED RESPONSIBILITY MODEL
# =============================================================================

section("2. Shared Responsibility Model")

print(
    """
Cloud security is normally divided between the cloud provider and the
customer.

The provider commonly manages physical infrastructure, while the customer
is responsible for configuring the resources and protecting its workloads.

The exact boundary depends on the service model.

For example:

    IaaS:
        Provider -> physical infrastructure
        Customer -> operating system, application, data, configuration

    PaaS:
        Provider -> infrastructure and platform
        Customer -> application, data, configuration

    SaaS:
        Provider -> most technical layers
        Customer -> identities, data usage, access configuration
"""
)


@dataclass
class Responsibility:
    layer: str
    provider: str
    customer: str


responsibilities = [
    Responsibility("Physical facilities", "Provider", "Customer consumes service"),
    Responsibility("Networking hardware", "Provider", "Configuration depends on service"),
    Responsibility("Virtual machines", "Shared depending on service", "Shared depending on service"),
    Responsibility("Operating system", "Usually customer in IaaS", "Customer in IaaS"),
    Responsibility("Application", "Provider in SaaS", "Customer in most custom workloads"),
    Responsibility("Data", "Provider protects platform", "Customer owns data governance and access"),
    Responsibility("Identity", "Platform support", "Customer configures identities and permissions"),
]

for item in responsibilities:
    print(f"{item.layer}: provider={item.provider}; customer={item.customer}")


# =============================================================================
# 3. CLOUD GEOGRAPHY
# =============================================================================

section("3. Regions, Availability Zones, and Points of Presence")

print(
    """
A region is a geographic cloud location.

An availability zone is an isolated infrastructure location inside a region.

A point of presence is a network edge location used to bring content or
network services closer to users.

A simplified hierarchy is:

    Cloud Provider
        |
        +-- Region A
        |     +-- Availability Zone A
        |     +-- Availability Zone B
        |     +-- Availability Zone C
        |
        +-- Region B
              +-- Availability Zone A
              +-- Availability Zone B

Architectural consequences:

    One instance in one zone
        -> vulnerable to instance and zone failure

    Multiple instances across zones
        -> higher availability

    Multiple regions
        -> stronger geographic resilience but higher complexity and cost
"""
)


@dataclass
class AvailabilityZone:
    name: str
    healthy: bool = True


@dataclass
class CloudRegion:
    name: str
    zones: list[AvailabilityZone]

    def healthy_zones(self) -> list[AvailabilityZone]:
        return [zone for zone in self.zones if zone.healthy]

    def is_available(self) -> bool:
        return bool(self.healthy_zones())


region = CloudRegion(
    "example-region",
    [
        AvailabilityZone("zone-a"),
        AvailabilityZone("zone-b"),
        AvailabilityZone("zone-c"),
    ],
)

print("Healthy zones:", [zone.name for zone in region.healthy_zones()])

region.zones[0].healthy = False
print("After zone-a failure:", [zone.name for zone in region.healthy_zones()])
print("Region still available:", region.is_available())


# =============================================================================
# 4. COMPUTE
# =============================================================================

section("4. Compute Architecture")

print(
    """
Compute executes application logic.

Common compute approaches include:

    Virtual machines
        Full operating-system environments.

    Containers
        Application processes packaged with their dependencies.

    Serverless functions
        Short-lived event-driven execution units.

    Managed application platforms
        Platforms where infrastructure management is abstracted.

Important compute dimensions include:

    CPU
    Memory
    Disk
    Network throughput
    Startup time
    Maximum execution time
    Scaling behavior
    Isolation
    Cost model
"""
)


@dataclass
class VirtualMachine:
    name: str
    cpu: int
    memory_gb: float
    running: bool = True
    utilization: float = 0.0

    def capacity(self) -> float:
        """A simple educational capacity score."""
        return self.cpu * 100 + self.memory_gb * 20

    def handle_request(self, load: float) -> bool:
        """Return False if the VM cannot safely absorb the load."""
        if not self.running:
            return False

        self.utilization = min(100.0, load)
        return self.utilization < 90.0


vm = VirtualMachine("app-server-1", cpu=4, memory_gb=16)

print("VM capacity:", vm.capacity())
print("Handles 60% load:", vm.handle_request(60))
print("Handles 95% load safely:", vm.handle_request(95))


@dataclass
class Container:
    image: str
    cpu_limit: float
    memory_limit_mb: int

    def describe(self) -> str:
        return (
            f"Container(image={self.image}, "
            f"cpu_limit={self.cpu_limit}, "
            f"memory_limit={self.memory_limit_mb}MB)"
        )


container = Container("web-app:1.0", 1.0, 512)
print(container.describe())


@dataclass
class ServerlessFunction:
    name: str
    memory_mb: int
    timeout_seconds: int

    def invoke(self, event: dict[str, Any]) -> dict[str, Any]:
        return {
            "function": self.name,
            "status": "success",
            "event": event,
        }


function = ServerlessFunction("process-order", 512, 30)
print(function.invoke({"order_id": 1001}))


# =============================================================================
# 5. SCALABILITY AND ELASTICITY
# =============================================================================

section("5. Scalability and Elasticity")

print(
    """
Scalability means a system can handle increasing demand by adding resources
or improving capacity.

Vertical scaling:
    Increase resources of an existing machine.

Horizontal scaling:
    Add more machines or instances.

Elasticity:
    Automatically adjust capacity as demand changes.

Example:

    1 server
        |
        | traffic increases
        v
    3 servers
        |
        | traffic decreases
        v
    1 server

Horizontal scaling is especially important for stateless web applications.
"""
)


@dataclass
class AutoScaler:
    minimum_instances: int
    maximum_instances: int
    target_utilization: float
    instances: int = 1

    def scale(self, utilization: float) -> int:
        if utilization > self.target_utilization + 10:
            self.instances = min(self.maximum_instances, self.instances + 1)
        elif utilization < self.target_utilization - 20:
            self.instances = max(self.minimum_instances, self.instances - 1)

        return self.instances


autoscaler = AutoScaler(
    minimum_instances=1,
    maximum_instances=5,
    target_utilization=60,
)

for utilization in [30, 50, 75, 85, 95, 40, 25]:
    print(
        f"Utilization={utilization}% -> "
        f"instances={autoscaler.scale(utilization)}"
    )


# =============================================================================
# 6. STATELESS VS STATEFUL APPLICATIONS
# =============================================================================

section("6. Stateless and Stateful Architecture")

print(
    """
A stateless application does not depend on local memory or local disk to
preserve user state between requests.

This makes horizontal scaling easier.

A stateful application maintains important state inside a particular process,
machine, or session.

A common cloud pattern is:

    Client
       |
       v
    Load Balancer
       |
       +----> App 1
       +----> App 2
       +----> App 3
                |
                +----> Shared Database
                +----> Shared Cache
                +----> Object Storage

Instead of storing session data only on App 1, shared state can be placed in
a centralized service.
"""
)


class StatelessApplication:
    """The application derives results from the request and shared state."""

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "request_id": request["request_id"],
            "message": f"Processed {request['operation']}",
        }


class StatefulApplication:
    """This process keeps state locally, making scaling more complicated."""

    def __init__(self) -> None:
        self.counter = 0

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        self.counter += 1
        return {"local_counter": self.counter}


stateless = StatelessApplication()
stateful = StatefulApplication()

print(stateless.handle({"request_id": "abc", "operation": "read"}))
print(stateful.handle({"operation": "read"}))
print(stateful.handle({"operation": "read"}))


# =============================================================================
# 7. NETWORKING
# =============================================================================

section("7. Cloud Networking Fundamentals")

print(
    """
Cloud networking provides communication between users, applications,
services, databases, and external systems.

Important concepts:

    IP address
        Identifies a network interface.

    Subnet
        A logical subdivision of an IP network.

    Route
        Determines where packets should be sent.

    Router
        Connects networks.

    Firewall
        Controls traffic according to security rules.

    NAT
        Allows private resources to communicate with external networks
        without directly exposing their private addresses.

    Load balancer
        Distributes traffic across healthy application targets.

    DNS
        Maps human-readable names to network destinations.

A common architecture separates public-facing and private resources.
"""
)


def ip_to_int(ip: str) -> int:
    parts = [int(part) for part in ip.split(".")]
    if len(parts) != 4 or any(not 0 <= part <= 255 for part in parts):
        raise ValueError(f"Invalid IPv4 address: {ip}")

    value = 0
    for part in parts:
        value = (value << 8) | part

    return value


def int_to_ip(value: int) -> str:
    if not 0 <= value <= 2**32 - 1:
        raise ValueError("IPv4 integer is outside valid range")

    return ".".join(
        str((value >> shift) & 255)
        for shift in (24, 16, 8, 0)
    )


def same_subnet(ip1: str, ip2: str, mask: str) -> bool:
    network_mask = ip_to_int(mask)
    return (ip_to_int(ip1) & network_mask) == (
        ip_to_int(ip2) & network_mask
    )


print("10.0.1.10 and 10.0.1.20 same /24:",
      same_subnet("10.0.1.10", "10.0.1.20", "255.255.255.0"))

print("10.0.1.10 and 10.0.2.20 same /24:",
      same_subnet("10.0.1.10", "10.0.2.20", "255.255.255.0"))


@dataclass
class NetworkRule:
    source: str
    destination_port: int
    protocol: str
    action: str

    def allows(self, source_ip: str, port: int, protocol: str) -> bool:
        source_matches = self.source == "0.0.0.0/0" or self.source == source_ip
        return (
            source_matches
            and self.destination_port == port
            and self.protocol.lower() == protocol.lower()
            and self.action.lower() == "allow"
        )


firewall_rule = NetworkRule(
    source="10.0.1.10",
    destination_port=443,
    protocol="TCP",
    action="ALLOW",
)

print(
    "HTTPS request allowed:",
    firewall_rule.allows("10.0.1.10", 443, "tcp"),
)

print(
    "HTTP request allowed:",
    firewall_rule.allows("10.0.1.10", 80, "tcp"),
)


# =============================================================================
# 8. PUBLIC AND PRIVATE SUBNETS
# =============================================================================

section("8. Public and Private Network Segmentation")

print(
    """
A public subnet is normally associated with resources that can receive
traffic through an internet-facing path.

A private subnet is used for resources that should not be directly reachable
from the public internet.

A common three-tier design is:

    Internet
       |
       v
    Public Load Balancer
       |
       v
    Private Application Subnets
       |
       +------> Private Database
       |
       +------> Private Cache

Public access should be minimized.

A database generally should not need a public IP address merely because an
application needs database connectivity.
"""
)


@dataclass
class Subnet:
    name: str
    cidr: str
    public: bool
    availability_zone: str


subnets = [
    Subnet("public-a", "10.0.1.0/24", True, "zone-a"),
    Subnet("public-b", "10.0.2.0/24", True, "zone-b"),
    Subnet("private-app-a", "10.0.11.0/24", False, "zone-a"),
    Subnet("private-app-b", "10.0.12.0/24", False, "zone-b"),
    Subnet("private-db-a", "10.0.21.0/24", False, "zone-a"),
    Subnet("private-db-b", "10.0.22.0/24", False, "zone-b"),
]

for subnet in subnets:
    exposure = "public" if subnet.public else "private"
    print(f"{subnet.name}: {subnet.cidr}, {exposure}, {subnet.availability_zone}")


# =============================================================================
# 9. LOAD BALANCING
# =============================================================================

section("9. Load Balancing")

print(
    """
A load balancer distributes requests among multiple targets.

Common algorithms include:

    Round robin
        Targets are selected sequentially.

    Weighted routing
        Targets receive traffic according to assigned weights.

    Least connections
        The target with fewer active connections is preferred.

    IP hashing
        A client identifier determines the target.

Health checks prevent traffic from being sent to unhealthy targets.
"""
)


@dataclass
class Backend:
    name: str
    healthy: bool = True
    active_connections: int = 0


class RoundRobinLoadBalancer:
    def __init__(self, backends: list[Backend]) -> None:
        self.backends = backends
        self.index = 0

    def choose_backend(self) -> Backend:
        healthy = [backend for backend in self.backends if backend.healthy]

        if not healthy:
            raise RuntimeError("No healthy backends available")

        backend = healthy[self.index % len(healthy)]
        self.index += 1
        backend.active_connections += 1
        return backend


backends = [
    Backend("app-a"),
    Backend("app-b"),
    Backend("app-c"),
]

load_balancer = RoundRobinLoadBalancer(backends)

for request_number in range(7):
    backend = load_balancer.choose_backend()
    print(f"Request {request_number + 1} -> {backend.name}")

backends[1].healthy = False
print("app-b failed health check")

for request_number in range(4):
    backend = load_balancer.choose_backend()
    print(f"Request after failure -> {backend.name}")


# =============================================================================
# 10. DNS
# =============================================================================

section("10. DNS Architecture")

print(
    """
DNS translates names into destinations.

Example:

    www.example.com
          |
          v
       DNS
          |
          v
    Load Balancer IP

Important DNS concepts include:

    A record
        Name -> IPv4 address

    AAAA record
        Name -> IPv6 address

    CNAME
        Name -> another DNS name

    MX
        Mail routing

    TXT
        Arbitrary text used for verification and policy mechanisms

TTL controls how long a DNS response may be cached.
"""
)


@dataclass
class DNSRecord:
    name: str
    record_type: str
    value: str
    ttl_seconds: int


dns_records = [
    DNSRecord("example.com", "A", "203.0.113.10", 300),
    DNSRecord("www.example.com", "CNAME", "example.com", 300),
]

for record in dns_records:
    print(
        f"{record.record_type} {record.name} -> "
        f"{record.value} TTL={record.ttl_seconds}s"
    )


# =============================================================================
# 11. STORAGE
# =============================================================================

section("11. Cloud Storage Architecture")

print(
    """
Three major storage categories are:

    Block storage
        Virtual disk blocks. Commonly attached to compute instances.

    File storage
        Shared filesystem semantics.

    Object storage
        Objects identified by keys inside buckets or containers.

Object storage is useful for:

    Images
    Videos
    Documents
    Backups
    Logs
    Data lake files
    Static website assets

Object storage is generally not equivalent to a POSIX filesystem.
"""
)


@dataclass
class Object:
    key: str
    data: bytes
    metadata: dict[str, str] = field(default_factory=dict)


class ObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, Object] = {}

    def put(
        self,
        key: str,
        data: bytes,
        metadata: Optional[dict[str, str]] = None,
    ) -> None:
        self.objects[key] = Object(
            key,
            data,
            metadata or {},
        )

    def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise KeyError(f"Object does not exist: {key}")
        return self.objects[key].data

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def list_keys(self, prefix: str = "") -> list[str]:
        return sorted(
            key for key in self.objects
            if key.startswith(prefix)
        )


storage = ObjectStorage()

storage.put(
    "images/profile/avatar.txt",
    b"example-image-content",
    {"content-type": "text/plain"},
)

storage.put(
    "documents/report.txt",
    b"cloud architecture report",
)

print("Objects:", storage.list_keys())
print("Retrieved:", storage.get("documents/report.txt").decode())


# =============================================================================
# 12. STORAGE DURABILITY AND AVAILABILITY
# =============================================================================

section("12. Durability Versus Availability")

print(
    """
Durability answers:

    "Will stored data survive?"

Availability answers:

    "Can I access the service when I need it?"

They are related but different.

For example:

    High durability + temporary service outage
        -> data may remain safe but unavailable

    High availability + inadequate durability
        -> service is reachable but data could still be lost

Architectural decisions should explicitly consider both.
"""
)


@dataclass
class StoragePolicy:
    replication_factor: int
    backup_enabled: bool
    cross_region_replication: bool

    def durability_score(self) -> float:
        score = min(99.0, 80 + self.replication_factor * 5)

        if self.backup_enabled:
            score += 2

        if self.cross_region_replication:
            score += 2

        return min(score, 99.999)


policy = StoragePolicy(
    replication_factor=3,
    backup_enabled=True,
    cross_region_replication=True,
)

print("Illustrative durability score:", policy.durability_score())


# =============================================================================
# 13. DATABASE ARCHITECTURE
# =============================================================================

section("13. Databases")

print(
    """
Relational databases organize structured data around tables, relationships,
constraints, and transactions.

Examples of relational workloads:

    Orders
    Payments
    Banking records
    Customer accounts
    Inventory

NoSQL databases include several models:

    Key-value
    Document
    Wide-column
    Graph

The database choice should follow workload requirements rather than fashion.

Important database concerns include:

    Consistency
    Transactions
    Query patterns
    Indexing
    Replication
    Partitioning
    Backup
    Recovery
    Connection management
"""
)


@dataclass
class User:
    user_id: int
    name: str
    email: str


class InMemoryRelationalLikeDatabase:
    """A small educational representation of table-like data."""

    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self.email_index: dict[str, int] = {}

    def insert_user(self, user: User) -> None:
        if user.user_id in self.users:
            raise ValueError("Duplicate user ID")

        if user.email in self.email_index:
            raise ValueError("Duplicate email")

        self.users[user.user_id] = user
        self.email_index[user.email] = user.user_id

    def find_by_email(self, email: str) -> Optional[User]:
        user_id = self.email_index.get(email)

        if user_id is None:
            return None

        return self.users[user_id]


database = InMemoryRelationalLikeDatabase()

database.insert_user(User(1, "Asha", "asha@example.com"))
database.insert_user(User(2, "Ravi", "ravi@example.com"))

print(database.find_by_email("ravi@example.com"))


# =============================================================================
# 14. DATABASE INDEXING
# =============================================================================

section("14. Database Indexing")

print(
    """
An index provides an alternative access path to data.

Without an index, a database may need to inspect many rows.

With an appropriate index, a query can often locate matching records much
faster.

Indexes have costs:

    - Additional storage
    - Additional write work
    - Maintenance overhead
    - Possible poor performance if the index is not selective

Index design should follow actual query patterns.
"""
)


class IndexedCollection:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.index: dict[Any, list[int]] = defaultdict(list)

    def add(self, row: dict[str, Any], indexed_field: str) -> None:
        position = len(self.rows)
        self.rows.append(row)
        self.index[row[indexed_field]].append(position)

    def lookup(self, value: Any) -> list[dict[str, Any]]:
        return [self.rows[position] for position in self.index.get(value, [])]


orders = IndexedCollection()

orders.add({"id": 1, "customer": "Asha", "amount": 500}, "customer")
orders.add({"id": 2, "customer": "Ravi", "amount": 700}, "customer")
orders.add({"id": 3, "customer": "Asha", "amount": 250}, "customer")

print("Indexed lookup:", orders.lookup("Asha"))


# =============================================================================
# 15. REPLICATION
# =============================================================================

section("15. Database Replication")

print(
    """
Replication creates multiple copies of data.

Common patterns:

    Primary-replica
        Writes go to a primary; replicas serve reads.

    Multi-primary
        Multiple nodes can accept writes.

    Synchronous replication
        The system waits for required replicas to acknowledge data.

    Asynchronous replication
        Replicas may lag behind the primary.

Trade-offs involve:

    Latency
    Consistency
    Availability
    Operational complexity
"""
)


@dataclass
class Replica:
    name: str
    data_version: int = 0
    healthy: bool = True


class PrimaryReplicaDatabase:
    def __init__(self, replica_names: list[str]) -> None:
        self.version = 0
        self.replicas = [Replica(name) for name in replica_names]

    def write(self, synchronous: bool = True) -> int:
        self.version += 1

        if synchronous:
            for replica in self.replicas:
                if replica.healthy:
                    replica.data_version = self.version
        else:
            healthy = [r for r in self.replicas if r.healthy]
            if healthy:
                healthy[0].data_version = self.version

        return self.version


replicated_db = PrimaryReplicaDatabase(["replica-a", "replica-b"])

replicated_db.write(synchronous=True)

print(
    "Replica versions:",
    [replica.data_version for replica in replicated_db.replicas],
)

replicated_db.replicas[1].healthy = False
replicated_db.write(synchronous=False)

print(
    "After replica failure:",
    [
        (replica.name, replica.data_version, replica.healthy)
        for replica in replicated_db.replicas
    ],
)


# =============================================================================
# 16. CACHING
# =============================================================================

section("16. Caching")

print(
    """
A cache stores frequently accessed data closer to the consumer.

Typical locations:

    Browser cache
    CDN cache
    Application cache
    Distributed cache
    Database buffer/cache

A cache hit avoids an expensive backend operation.

Important concepts:

    TTL
    Eviction
    Cache invalidation
    Cache-aside
    Write-through
    Write-back
    Stale data
"""
)


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.entries: dict[str, CacheEntry] = {}

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        self.entries[key] = CacheEntry(
            value,
            self.clock() + ttl_seconds,
        )

    def get(self, key: str) -> Optional[Any]:
        entry = self.entries.get(key)

        if entry is None:
            return None

        if self.clock() >= entry.expires_at:
            del self.entries[key]
            return None

        return entry.value


cache = TTLCache()

cache.set("product:100", {"name": "Keyboard", "price": 1500}, ttl_seconds=60)

print("Cache hit:", cache.get("product:100"))
print("Cache miss:", cache.get("product:999"))


# =============================================================================
# 17. CACHE-ASIDE PATTERN
# =============================================================================

section("17. Cache-Aside Pattern")

print(
    """
The cache-aside pattern usually follows:

    1. Application checks cache.
    2. If present, return cached data.
    3. If absent, query the database.
    4. Put the result into the cache.
    5. Return the result.

The pattern is simple but creates invalidation challenges.

Example:
"""
)


class ProductService:
    def __init__(
        self,
        cache: TTLCache,
        database: dict[int, dict[str, Any]],
    ) -> None:
        self.cache = cache
        self.database = database

    def get_product(self, product_id: int) -> Optional[dict[str, Any]]:
        key = f"product:{product_id}"

        cached = self.cache.get(key)
        if cached is not None:
            return cached

        product = self.database.get(product_id)

        if product is not None:
            self.cache.set(key, product, 300)

        return product


product_service = ProductService(
    TTLCache(),
    {
        1: {"id": 1, "name": "Laptop", "price": 75000},
        2: {"id": 2, "name": "Mouse", "price": 1200},
    },
)

print(product_service.get_product(1))
print(product_service.get_product(1))


# =============================================================================
# 18. CDN
# =============================================================================

section("18. Content Delivery Networks")

print(
    """
A CDN places content at edge locations closer to users.

Typical CDN content:

    Images
    JavaScript
    CSS
    Videos
    Static HTML
    Downloadable files

A simplified path is:

    User
      |
      v
    Nearest Edge
      |
      | cache hit
      v
    Content

If the content is not cached:

    User -> Edge -> Origin -> Edge -> User

CDNs can improve latency and reduce origin traffic.
"""
)


@dataclass
class EdgeCache:
    region: str
    objects: dict[str, str] = field(default_factory=dict)

    def fetch(self, key: str) -> tuple[str, bool]:
        if key in self.objects:
            return self.objects[key], True

        value = f"origin-content-for-{key}"
        self.objects[key] = value
        return value, False


edge = EdgeCache("asia-south")
print(edge.fetch("/static/app.js"))
print(edge.fetch("/static/app.js"))


# =============================================================================
# 19. API GATEWAY
# =============================================================================

section("19. API Gateway")

print(
    """
An API gateway can provide a single controlled entry point for APIs.

Typical responsibilities:

    Authentication
    Authorization
    Rate limiting
    Request routing
    TLS termination
    Request transformation
    Logging
    Metrics
    API versioning

It should not automatically become a place where all business logic is
implemented.
"""
)


@dataclass
class APIRequest:
    path: str
    method: str
    headers: dict[str, str]
    body: dict[str, Any]


class APIGateway:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Callable[[APIRequest], dict[str, Any]]] = {}
        self.rate_counts: Counter[str] = Counter()

    def add_route(
        self,
        method: str,
        path: str,
        handler: Callable[[APIRequest], dict[str, Any]],
    ) -> None:
        self.routes[(method.upper(), path)] = handler

    def handle(self, request: APIRequest) -> dict[str, Any]:
        client = request.headers.get("client-id", "anonymous")
        self.rate_counts[client] += 1

        if self.rate_counts[client] > 5:
            return {"status": 429, "error": "rate limit exceeded"}

        route = self.routes.get((request.method.upper(), request.path))

        if route is None:
            return {"status": 404, "error": "route not found"}

        return route(request)


gateway = APIGateway()


def health_handler(request: APIRequest) -> dict[str, Any]:
    return {"status": 200, "service": "healthy"}


gateway.add_route("GET", "/health", health_handler)

print(
    gateway.handle(
        APIRequest(
            "/health",
            "GET",
            {"client-id": "client-1"},
            {},
        )
    )
)


# =============================================================================
# 20. ASYNCHRONOUS PROCESSING
# =============================================================================

section("20. Queues and Asynchronous Architecture")

print(
    """
A message queue decouples producers from consumers.

Synchronous:

    User -> API -> Worker -> Database -> Response

Asynchronous:

    User -> API -> Queue -> Response
                       |
                       v
                     Worker
                       |
                       v
                    Database

Benefits:

    Decoupling
    Traffic smoothing
    Retry capability
    Independent scaling
    Better handling of long-running work

Costs:

    Eventual consistency
    Duplicate messages
    Ordering complexity
    Retry and dead-letter handling
"""
)


@dataclass
class Message:
    message_id: str
    payload: dict[str, Any]
    attempts: int = 0


class MessageQueue:
    def __init__(self) -> None:
        self.messages: deque[Message] = deque()

    def publish(self, payload: dict[str, Any]) -> str:
        message_id = str(uuid.uuid4())

        self.messages.append(
            Message(message_id, payload)
        )

        return message_id

    def consume(self) -> Optional[Message]:
        if not self.messages:
            return None

        return self.messages.popleft()

    def size(self) -> int:
        return len(self.messages)


queue = MessageQueue()

queue.publish({"order_id": 101, "action": "charge"})
queue.publish({"order_id": 102, "action": "ship"})

print("Queue size:", queue.size())

message = queue.consume()
print("Consumed:", message)


# =============================================================================
# 21. RETRIES AND DEAD-LETTER QUEUES
# =============================================================================

section("21. Retries and Dead-Letter Queues")

print(
    """
Retries are useful for transient failures.

Examples of transient failures:

    Network timeout
    Temporary dependency outage
    Rate limit
    Short-lived service overload

Retries are dangerous when used blindly.

Problems include:

    Retry storms
    Duplicate side effects
    Longer latency
    Amplified downstream load

Exponential backoff increases the delay between attempts.

A dead-letter queue stores messages that repeatedly fail processing.
"""
)


def exponential_backoff(
    attempt: int,
    base_seconds: float = 1.0,
    maximum_seconds: float = 60.0,
) -> float:
    delay = base_seconds * (2 ** attempt)
    jitter = random.uniform(0, 0.25 * delay)
    return min(maximum_seconds, delay + jitter)


for attempt in range(5):
    print(
        f"attempt={attempt}, "
        f"backoff≈{exponential_backoff(attempt):.2f}s"
    )


# =============================================================================
# 22. IDEMPOTENCY
# =============================================================================

section("22. Idempotency")

print(
    """
An operation is idempotent when repeating it produces the same intended
final state.

For example:

    Set account status to ACTIVE
        repeated execution -> ACTIVE

is naturally idempotent.

Whereas:

    Add ₹100 to account
        repeated execution -> multiple credits

is not naturally idempotent.

Distributed systems often use idempotency keys for operations such as
payments and order creation.
"""
)


class IdempotentOrderService:
    def __init__(self) -> None:
        self.completed_requests: dict[str, dict[str, Any]] = {}

    def create_order(
        self,
        idempotency_key: str,
        order_data: dict[str, Any],
    ) -> dict[str, Any]:
        if idempotency_key in self.completed_requests:
            return self.completed_requests[idempotency_key]

        result = {
            "order_id": str(uuid.uuid4()),
            "status": "created",
            "data": order_data,
        }

        self.completed_requests[idempotency_key] = result
        return result


order_service = IdempotentOrderService()

first_result = order_service.create_order(
    "payment-request-123",
    {"amount": 500},
)

second_result = order_service.create_order(
    "payment-request-123",
    {"amount": 500},
)

print("Same result returned:", first_result == second_result)


# =============================================================================
# 23. EVENT-DRIVEN ARCHITECTURE
# =============================================================================

section("23. Event-Driven Architecture")

print(
    """
An event describes something that happened.

Examples:

    OrderCreated
    PaymentCompleted
    UserRegistered
    FileUploaded

A producer emits an event.

Consumers subscribe to events.

Example:

    Order Service
          |
          v
    OrderCreated Event
       /       |       \
      v        v        v
   Billing  Shipping  Analytics

This architecture reduces direct coupling but introduces asynchronous
coordination and eventual consistency.
"""
)


@dataclass
class Event:
    event_type: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class EventBus:
    def __init__(self) -> None:
        self.subscribers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], None],
    ) -> None:
        self.subscribers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        for handler in self.subscribers[event.event_type]:
            handler(event)


event_bus = EventBus()


def billing_consumer(event: Event) -> None:
    print("Billing received:", event.payload)


def analytics_consumer(event: Event) -> None:
    print("Analytics recorded:", event.event_type)


event_bus.subscribe("OrderCreated", billing_consumer)
event_bus.subscribe("OrderCreated", analytics_consumer)

event_bus.publish(
    Event(
        "OrderCreated",
        {"order_id": 5001, "amount": 1200},
    )
)


# =============================================================================
# 24. MICROSERVICES
# =============================================================================

section("24. Monolith Versus Microservices")

print(
    """
Monolith:
    One deployable application containing multiple capabilities.

Advantages:
    - Simple deployment
    - Easy local development
    - Simple transactions
    - Fewer distributed-system problems

Disadvantages:
    - Large deployment unit
    - Scaling may be less granular
    - Stronger internal coupling may develop

Microservices:
    Multiple independently deployable services.

Advantages:
    - Independent deployment
    - Independent scaling
    - Team ownership boundaries
    - Technology flexibility

Disadvantages:
    - Network failures
    - Distributed tracing
    - Data consistency challenges
    - More deployments
    - More operational complexity

Microservices are an architectural trade-off, not an automatic improvement.
"""
)


@dataclass
class Service:
    name: str
    responsibility: str
    endpoint: str


services = [
    Service("user-service", "Identity and profile", "/users"),
    Service("order-service", "Order lifecycle", "/orders"),
    Service("payment-service", "Payment processing", "/payments"),
    Service("inventory-service", "Stock management", "/inventory"),
]

for service in services:
    print(f"{service.name}: {service.responsibility} -> {service.endpoint}")


# =============================================================================
# 25. SERVICE DISCOVERY
# =============================================================================

section("25. Service Discovery")

print(
    """
In dynamic cloud environments, application instances may change frequently.

Service discovery maps logical service names to currently available
instances.

For example:

    payment-service
          |
          v
    instance-a
    instance-b
    instance-c

Consumers use the logical service name instead of hard-coding a machine IP.
"""
)


class ServiceRegistry:
    def __init__(self) -> None:
        self.instances: dict[str, set[str]] = defaultdict(set)

    def register(self, service: str, endpoint: str) -> None:
        self.instances[service].add(endpoint)

    def deregister(self, service: str, endpoint: str) -> None:
        self.instances[service].discard(endpoint)

    def discover(self, service: str) -> list[str]:
        return sorted(self.instances.get(service, set()))


registry = ServiceRegistry()

registry.register("payment-service", "10.0.11.10:8080")
registry.register("payment-service", "10.0.12.10:8080")
registry.register("payment-service", "10.0.13.10:8080")

print("Discovered payment instances:", registry.discover("payment-service"))


# =============================================================================
# 26. CONTAINERS AND ORCHESTRATION
# =============================================================================

section("26. Containers and Orchestration")

print(
    """
Containers package an application and its runtime dependencies.

An orchestrator can manage:

    Scheduling
    Restarting failed workloads
    Service discovery
    Scaling
    Rolling deployments
    Health checks
    Resource limits

A simplified orchestration hierarchy is:

    Cluster
       |
       +-- Node
       |    +-- Container
       |    +-- Container
       |
       +-- Node
            +-- Container
            +-- Container

Kubernetes is a common example of a container orchestration platform.
"""
)


@dataclass
class Pod:
    name: str
    cpu_request: float
    memory_request_mb: int
    healthy: bool = True


@dataclass
class Node:
    name: str
    cpu_capacity: float
    memory_capacity_mb: int
    pods: list[Pod] = field(default_factory=list)

    def can_schedule(self, pod: Pod) -> bool:
        used_cpu = sum(p.cpu_request for p in self.pods)
        used_memory = sum(p.memory_request_mb for p in self.pods)

        return (
            used_cpu + pod.cpu_request <= self.cpu_capacity
            and used_memory + pod.memory_request_mb <= self.memory_capacity_mb
        )

    def schedule(self, pod: Pod) -> bool:
        if not self.can_schedule(pod):
            return False

        self.pods.append(pod)
        return True


nodes = [
    Node("node-a", 4, 8192),
    Node("node-b", 4, 8192),
]

pods = [
    Pod("web-1", 1, 512),
    Pod("web-2", 1, 512),
    Pod("api-1", 2, 1024),
    Pod("worker-1", 1, 1024),
]

for pod in pods:
    scheduled = False

    for node in nodes:
        if node.schedule(pod):
            print(f"{pod.name} scheduled on {node.name}")
            scheduled = True
            break

    if not scheduled:
        print(f"{pod.name} could not be scheduled")


# =============================================================================
# 27. SERVERLESS
# =============================================================================

section("27. Serverless Architecture")

print(
    """
Serverless does not mean that servers do not exist.

It means the infrastructure management responsibility is abstracted from the
application developer.

Typical characteristics:

    Event-driven execution
    Automatic scaling
    Pay-per-use pricing
    Short-lived execution
    Managed runtime

Potential limitations:

    Cold starts
    Execution duration limits
    Stateless execution model
    Platform-specific behavior
    Debugging complexity
"""
)


class ServerlessRuntime:
    def __init__(self) -> None:
        self.invocation_count = 0

    def execute(
        self,
        function: Callable[[dict[str, Any]], Any],
        event: dict[str, Any],
    ) -> Any:
        self.invocation_count += 1
        return function(event)


runtime = ServerlessRuntime()


def resize_image(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "input": event["object_key"],
        "output": event["object_key"].replace(
            "/original/",
            "/thumbnail/",
        ),
    }


print(
    runtime.execute(
        resize_image,
        {"object_key": "/original/photo.jpg"},
    )
)


# =============================================================================
# 28. SECURITY FUNDAMENTALS
# =============================================================================

section("28. Cloud Security Fundamentals")

print(
    """
Core security objectives are commonly described as the CIA triad:

    Confidentiality
        Prevent unauthorized disclosure.

    Integrity
        Prevent unauthorized or unnoticed modification.

    Availability
        Keep systems accessible when required.

Cloud security layers include:

    Identity
    Network controls
    Encryption
    Application security
    Data protection
    Logging
    Monitoring
    Vulnerability management
    Backup and recovery
"""
)


@dataclass
class SecurityPolicy:
    confidentiality: bool
    integrity: bool
    availability: bool

    def score(self) -> int:
        return sum(
            [
                self.confidentiality,
                self.integrity,
                self.availability,
            ]
        )


security_policy = SecurityPolicy(
    confidentiality=True,
    integrity=True,
    availability=True,
)

print("CIA controls enabled:", security_policy.score(), "/ 3")


# =============================================================================
# 29. IDENTITY AND ACCESS MANAGEMENT
# =============================================================================

section("29. Identity and Access Management")

print(
    """
Authentication asks:

    "Who are you?"

Authorization asks:

    "What are you allowed to do?"

A permission model commonly consists of:

    Principal
        User, service, or workload.

    Resource
        Object being accessed.

    Action
        Operation such as read or write.

    Policy
        Rules determining whether the action is permitted.

Least privilege means granting only the permissions necessary for a task.
"""
)


@dataclass(frozen=True)
class Permission:
    resource: str
    action: str


@dataclass
class Principal:
    name: str
    permissions: set[Permission] = field(default_factory=set)

    def can(self, resource: str, action: str) -> bool:
        return Permission(resource, action) in self.permissions


application_role = Principal(
    name="order-service-role",
    permissions={
        Permission("orders", "read"),
        Permission("orders", "write"),
    },
)

print("Can read orders:", application_role.can("orders", "read"))
print("Can delete orders:", application_role.can("orders", "delete"))


# =============================================================================
# 30. ROLE-BASED ACCESS CONTROL
# =============================================================================

section("30. Role-Based Access Control")

print(
    """
RBAC assigns permissions to roles rather than individually configuring every
user.

Example:

    Analyst
        -> read analytics

    Developer
        -> deploy development applications

    Administrator
        -> infrastructure administration

RBAC simplifies permission management but requires careful role design.
"""
)


class RBAC:
    def __init__(self) -> None:
        self.roles: dict[str, set[Permission]] = defaultdict(set)
        self.user_roles: dict[str, set[str]] = defaultdict(set)

    def add_permission(self, role: str, permission: Permission) -> None:
        self.roles[role].add(permission)

    def assign_role(self, user: str, role: str) -> None:
        self.user_roles[user].add(role)

    def allowed(self, user: str, permission: Permission) -> bool:
        return any(
            permission in self.roles[role]
            for role in self.user_roles[user]
        )


rbac = RBAC()

rbac.add_permission("analyst", Permission("reports", "read"))
rbac.add_permission("analyst", Permission("dashboards", "read"))
rbac.assign_role("user-1", "analyst")

print(
    "user-1 can read reports:",
    rbac.allowed("user-1", Permission("reports", "read")),
)

print(
    "user-1 can delete reports:",
    rbac.allowed("user-1", Permission("reports", "delete")),
)


# =============================================================================
# 31. ENCRYPTION
# =============================================================================

section("31. Encryption")

print(
    """
Encryption protects information by transforming readable data into data that
requires a key to recover.

Two important states are:

    Encryption at rest
        Data stored on disks, databases, object storage, and backups.

    Encryption in transit
        Data moving between systems, commonly protected with TLS.

Symmetric encryption uses the same secret key for encryption and decryption.

Asymmetric cryptography uses a public/private key pair.

Hashing is different from encryption:
    - Hashes are designed as one-way transformations.
    - Encryption is designed to be reversible with the correct key.

This example demonstrates hashing, not secure encryption.
"""
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


password_hash = sha256_text("example-password")
print("SHA-256 digest:", password_hash)


def demonstrate_base64(value: str) -> str:
    """
    Base64 is encoding, not encryption.

    Anyone can decode it without a secret key.
    """
    return base64.b64encode(value.encode()).decode()


encoded = demonstrate_base64("sensitive-looking-text")
print("Base64:", encoded)
print("Base64 decoded:", base64.b64decode(encoded).decode())


# =============================================================================
# 32. SECRETS MANAGEMENT
# =============================================================================

section("32. Secrets Management")

print(
    """
Secrets include:

    Passwords
    API keys
    Database credentials
    Private keys
    Tokens

Secrets should not normally be hard-coded into source code.

A production architecture commonly uses a dedicated secret-management
mechanism with controlled access, auditing, and rotation.
"""
)


class SecretStore:
    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def put(self, name: str, value: str) -> None:
        self._secrets[name] = value

    def get(self, name: str) -> str:
        if name not in self._secrets:
            raise KeyError("Secret not found")
        return self._secrets[name]


secret_store = SecretStore()
secret_store.put("database-password", "example-only")

print("Secret exists:", bool(secret_store.get("database-password")))


# =============================================================================
# 33. ZERO TRUST
# =============================================================================

section("33. Zero-Trust Architecture")

print(
    """
Zero trust is based on the idea that network location alone should not imply
trust.

Important principles include:

    Verify identity
    Apply least privilege
    Authenticate continuously where appropriate
    Segment resources
    Monitor activity
    Assume compromise is possible

Traditional perimeter thinking:

    Inside network = trusted
    Outside network = untrusted

Zero-trust thinking:

    Every access request requires appropriate verification.
"""
)


@dataclass
class AccessRequest:
    principal: str
    resource: str
    authenticated: bool
    authorized: bool
    device_compliant: bool


def zero_trust_decision(request: AccessRequest) -> bool:
    return (
        request.authenticated
        and request.authorized
        and request.device_compliant
    )


request = AccessRequest(
    principal="service-a",
    resource="database",
    authenticated=True,
    authorized=True,
    device_compliant=True,
)

print("Access granted:", zero_trust_decision(request))


# =============================================================================
# 34. NETWORK SECURITY GROUPS AND SEGMENTATION
# =============================================================================

section("34. Network Segmentation")

print(
    """
Network segmentation reduces unnecessary communication paths.

For example:

    Internet
       |
       v
    Web Tier
       |
       v
    Application Tier
       |
       v
    Database Tier

A database firewall rule might allow:

    App subnet -> database port

but deny:

    Internet -> database port

Segmentation limits blast radius when a component is compromised.
"""
)


@dataclass
class SecurityGroup:
    name: str
    allowed_sources: set[str]
    allowed_ports: set[int]

    def allows(self, source: str, port: int) -> bool:
        return (
            source in self.allowed_sources
            and port in self.allowed_ports
        )


database_security_group = SecurityGroup(
    name="database-sg",
    allowed_sources={"application-subnet"},
    allowed_ports={5432},
)

print(
    "Application can reach PostgreSQL:",
    database_security_group.allows("application-subnet", 5432),
)

print(
    "Internet can reach PostgreSQL:",
    database_security_group.allows("internet", 5432),
)


# =============================================================================
# 35. HIGH AVAILABILITY
# =============================================================================

section("35. High Availability")

print(
    """
High availability aims to reduce service interruption.

Common techniques:

    Multiple instances
    Multiple availability zones
    Health checks
    Automatic failover
    Redundant networking
    Replicated data
    Load balancing

A single component can become a single point of failure.

The architectural goal is not simply "add more servers". Dependencies must
also be considered.

For example:

    3 application servers
        +
    1 database server

still contains a database single point of failure.
"""
)


@dataclass
class HAService:
    instances: int
    healthy_instances: int

    def available(self) -> bool:
        return self.healthy_instances > 0

    def availability_ratio(self) -> float:
        if self.instances <= 0:
            return 0.0

        return self.healthy_instances / self.instances


ha_service = HAService(3, 3)

print("Availability ratio:", ha_service.availability_ratio())

ha_service.healthy_instances = 1

print("After two failures:", ha_service.availability_ratio())
print("Service still available:", ha_service.available())


# =============================================================================
# 36. AVAILABILITY ZONE FAILURE SIMULATION
# =============================================================================

section("36. Failure Simulation")

print(
    """
A useful architectural exercise is to ask:

    "What happens if this component disappears?"

Failure scenarios can include:

    Instance failure
    Zone failure
    Region failure
    Database failure
    Network partition
    Dependency outage
    Credential expiration
    Configuration error
"""
)


@dataclass
class ApplicationInstance:
    name: str
    zone: str
    healthy: bool = True


instances = [
    ApplicationInstance("app-a1", "zone-a"),
    ApplicationInstance("app-a2", "zone-a"),
    ApplicationInstance("app-b1", "zone-b"),
    ApplicationInstance("app-b2", "zone-b"),
]

for instance in instances:
    print(instance)

for instance in instances:
    if instance.zone == "zone-a":
        instance.healthy = False

healthy_instances = [
    instance.name
    for instance in instances
    if instance.healthy
]

print("Healthy after zone-a failure:", healthy_instances)


# =============================================================================
# 37. RELIABILITY AND ERROR BUDGETS
# =============================================================================

section("37. Reliability Metrics")

print(
    """
Common reliability concepts:

    SLA
        A formal service commitment.

    SLO
        A target for a service metric.

    SLI
        The measured indicator used to evaluate the target.

For example:

    SLI = successful requests / total requests

    SLO = 99.9% successful requests

An error budget represents the amount of unreliability permitted by the SLO.
"""
)


def success_rate(successes: int, total: int) -> float:
    if total <= 0:
        raise ValueError("Total requests must be positive")

    if successes < 0 or successes > total:
        raise ValueError("Success count must be between 0 and total")

    return successes / total


rate = success_rate(9990, 10000)

print(f"Success rate: {rate:.4%}")

slo = 0.999
error_budget = 1 - slo

print(f"SLO: {slo:.3%}")
print(f"Allowed error budget: {error_budget:.3%}")


# =============================================================================
# 38. SLA AVAILABILITY AND DOWNTIME
# =============================================================================

section("38. Availability Mathematics")

print(
    """
Availability is commonly expressed as:

    Availability = uptime / total time

The complement is downtime:

    Downtime = 1 - availability

For a simple 30-day period:

    99.0%  -> approximately 7.2 hours
    99.9%  -> approximately 43.2 minutes
    99.99% -> approximately 4.32 minutes

These are mathematical illustrations. Real contractual SLAs have their own
definitions and exclusions.
"""
)


def monthly_downtime_minutes(
    availability_percentage: float,
    days: int = 30,
) -> float:
    if not 0 < availability_percentage <= 100:
        raise ValueError("Availability must be between 0 and 100")

    total_minutes = days * 24 * 60
    return total_minutes * (1 - availability_percentage / 100)


for availability_percentage in [99.0, 99.9, 99.99, 99.999]:
    print(
        f"{availability_percentage}% -> "
        f"{monthly_downtime_minutes(availability_percentage):.2f} minutes"
    )


# =============================================================================
# 39. DISASTER RECOVERY
# =============================================================================

section("39. Disaster Recovery")

print(
    """
Disaster recovery prepares for major service disruption.

Two important metrics are:

    RTO - Recovery Time Objective
        Maximum acceptable recovery time.

    RPO - Recovery Point Objective
        Maximum acceptable data loss measured in time.

Example:

    RTO = 60 minutes
    RPO = 15 minutes

This implies the organization aims to restore service within 60 minutes and
accepts at most approximately 15 minutes of data loss under the defined
scenario.

Recovery strategies can range from:

    Backup and restore
    Pilot light
    Warm standby
    Hot standby
    Active-active
"""
)


@dataclass
class RecoveryPlan:
    name: str
    rto_minutes: int
    rpo_minutes: int
    estimated_cost: float

    def meets_requirements(
        self,
        required_rto: int,
        required_rpo: int,
    ) -> bool:
        return (
            self.rto_minutes <= required_rto
            and self.rpo_minutes <= required_rpo
        )


recovery_plans = [
    RecoveryPlan("Backup Restore", 240, 60, 100),
    RecoveryPlan("Warm Standby", 60, 15, 500),
    RecoveryPlan("Hot Standby", 15, 5, 1200),
]

for plan in recovery_plans:
    print(
        plan.name,
        "meets RTO=60/RPO=15:",
        plan.meets_requirements(60, 15),
    )


# =============================================================================
# 40. BACKUP STRATEGIES
# =============================================================================

section("40. Backup Architecture")

print(
    """
A robust backup strategy considers:

    Frequency
    Retention
    Encryption
    Geographic separation
    Immutability
    Access controls
    Restore testing

A backup that has never been restored is an assumption, not demonstrated
recoverability.

The 3-2-1 concept is a common backup principle:

    3 copies of data
    2 different media or storage types
    1 copy stored off-site

Modern environments may extend this with immutable and logically isolated
copies.
"""
)


@dataclass
class Backup:
    backup_id: str
    created_at: float
    location: str
    immutable: bool


backups = [
    Backup("backup-001", time.time(), "primary-region", True),
    Backup("backup-002", time.time(), "secondary-region", True),
    Backup("backup-003", time.time(), "offline-archive", True),
]

print("Number of backup copies:", len(backups))
print("Immutable copies:", sum(backup.immutable for backup in backups))


# =============================================================================
# 41. OBSERVABILITY
# =============================================================================

section("41. Observability")

print(
    """
Observability is the ability to understand system behavior from its outputs.

Three common pillars are:

    Logs
        Detailed event records.

    Metrics
        Numeric measurements over time.

    Traces
        End-to-end request paths across distributed services.

Useful application metrics include:

    Request rate
    Error rate
    Latency
    Saturation
    CPU utilization
    Memory utilization
    Queue depth
    Database connections
"""
)


@dataclass
class Metric:
    name: str
    value: float
    unit: str


metrics = [
    Metric("request_rate", 1200, "requests/minute"),
    Metric("error_rate", 0.002, "ratio"),
    Metric("p95_latency", 180, "milliseconds"),
    Metric("cpu_utilization", 63, "percent"),
]

for metric in metrics:
    print(f"{metric.name}: {metric.value} {metric.unit}")


# =============================================================================
# 42. LOGGING
# =============================================================================

section("42. Structured Logging")

print(
    """
Structured logs represent fields separately instead of relying entirely on
free-form text.

Useful fields:

    timestamp
    request_id
    service
    operation
    status
    duration
    error
    user or tenant identifier where appropriate and permitted

Avoid logging secrets, passwords, tokens, or unnecessary sensitive data.
"""
)


def structured_log(
    level: str,
    service: str,
    message: str,
    **fields: Any,
) -> str:
    record = {
        "timestamp": time.time(),
        "level": level,
        "service": service,
        "message": message,
        **fields,
    }

    return json.dumps(record, sort_keys=True)


print(
    structured_log(
        "INFO",
        "order-service",
        "order created",
        order_id=1001,
        duration_ms=84,
    )
)


# =============================================================================
# 43. DISTRIBUTED TRACING
# =============================================================================

section("43. Distributed Tracing")

print(
    """
A trace represents one logical request.

A trace contains spans.

Example:

    Trace
      |
      +-- API Gateway span
      |
      +-- Order Service span
            |
            +-- Database span
            |
            +-- Payment Service span

A trace ID connects spans belonging to the same request.

Tracing helps identify where latency is introduced.
"""
)


@dataclass
class Span:
    trace_id: str
    span_id: str
    service: str
    operation: str
    duration_ms: float
    parent_span_id: Optional[str] = None


trace_id = str(uuid.uuid4())

spans = [
    Span(trace_id, "span-1", "api-gateway", "POST /orders", 18),
    Span(trace_id, "span-2", "order-service", "create-order", 85, "span-1"),
    Span(trace_id, "span-3", "database", "INSERT order", 32, "span-2"),
    Span(trace_id, "span-4", "payment-service", "authorize", 41, "span-2"),
]

for span in spans:
    print(
        span.service,
        span.operation,
        f"{span.duration_ms}ms",
        f"parent={span.parent_span_id}",
    )


# =============================================================================
# 44. PERFORMANCE AND LATENCY
# =============================================================================

section("44. Performance Architecture")

print(
    """
Performance includes:

    Latency
        Time taken for an operation.

    Throughput
        Amount of work completed per unit time.

    Concurrency
        Number of operations being handled at once.

    Saturation
        How close a resource is to its capacity.

A useful architectural principle is to identify the actual bottleneck before
optimizing.

Common performance techniques include:

    Caching
    Indexing
    Connection pooling
    Batching
    Compression
    Asynchronous processing
    Horizontal scaling
    CDN usage
    Query optimization
"""
)


def percentile(values: Iterable[float], percentage: float) -> float:
    sorted_values = sorted(values)

    if not sorted_values:
        raise ValueError("At least one value is required")

    if not 0 <= percentage <= 100:
        raise ValueError("Percentage must be between 0 and 100")

    position = (len(sorted_values) - 1) * percentage / 100

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return sorted_values[lower]

    fraction = position - lower

    return (
        sorted_values[lower]
        + (sorted_values[upper] - sorted_values[lower]) * fraction
    )


latencies = [20, 25, 28, 30, 35, 40, 45, 50, 70, 180]

print("Average latency:", statistics.mean(latencies))
print("P50 latency:", percentile(latencies, 50))
print("P95 latency:", percentile(latencies, 95))
print("P99 latency:", percentile(latencies, 99))


# =============================================================================
# 45. CONNECTION POOLING
# =============================================================================

section("45. Connection Pooling")

print(
    """
Opening a database connection can be expensive.

A connection pool keeps a limited number of reusable connections.

Benefits:

    Lower connection setup overhead
    Controlled database connection count
    Better application efficiency

The pool must be sized carefully.

Too small:
    Requests wait.

Too large:
    Database resources may be exhausted.
"""
)


class ConnectionPool:
    def __init__(self, size: int) -> None:
        if size <= 0:
            raise ValueError("Pool size must be positive")

        self.available = deque(
            f"connection-{number}"
            for number in range(1, size + 1)
        )
        self.in_use: set[str] = set()

    def acquire(self) -> str:
        if not self.available:
            raise RuntimeError("No database connections available")

        connection = self.available.popleft()
        self.in_use.add(connection)
        return connection

    def release(self, connection: str) -> None:
        if connection not in self.in_use:
            raise ValueError("Connection is not currently checked out")

        self.in_use.remove(connection)
        self.available.append(connection)


pool = ConnectionPool(2)

connection_1 = pool.acquire()
connection_2 = pool.acquire()

print("Connections in use:", pool.in_use)

pool.release(connection_1)
print("Available after release:", list(pool.available))

pool.release(connection_2)


# =============================================================================
# 46. CAP THEOREM
# =============================================================================

section("46. CAP Theorem")

print(
    """
CAP theorem concerns distributed data systems.

The three properties are:

    Consistency
        Reads observe an appropriately current value according to the chosen
        consistency model.

    Availability
        Every request receives a response according to the system's
        availability definition.

    Partition tolerance
        The system continues operating despite communication partitions.

A distributed system cannot simultaneously guarantee all three CAP
properties under a network partition.

In practice, network partitions are possible, so architects often make
trade-offs in how consistency and availability are handled.

CAP should not be confused with ordinary application performance or the
ACID transaction properties.
"""
)


@dataclass
class CAPChoice:
    name: str
    consistency_priority: bool
    availability_priority: bool
    partition_tolerance: bool


cap_choices = [
    CAPChoice("Consistency-oriented", True, False, True),
    CAPChoice("Availability-oriented", False, True, True),
]

for choice in cap_choices:
    print(choice)


# =============================================================================
# 47. CONSISTENCY MODELS
# =============================================================================

section("47. Consistency Models")

print(
    """
Strong consistency:
    A read is expected to observe the latest successful write according to
    the system's consistency contract.

Eventual consistency:
    If updates stop, replicas are expected to converge.

Read-after-write consistency:
    A client can read its own recent write.

Causal consistency:
    Causally related operations preserve their causal ordering.

The correct choice depends on business requirements.
"""
)


class EventuallyConsistentReplica:
    def __init__(self, initial_value: int = 0) -> None:
        self.value = initial_value
        self.pending_updates: deque[int] = deque()

    def write(self, value: int) -> None:
        self.pending_updates.append(value)

    def replicate(self) -> None:
        if self.pending_updates:
            self.value = self.pending_updates.popleft()

    def read(self) -> int:
        return self.value


replica = EventuallyConsistentReplica()

replica.write(10)

print("Before replication:", replica.read())

replica.replicate()

print("After replication:", replica.read())


# =============================================================================
# 48. DISTRIBUTED SYSTEM TIMEOUTS
# =============================================================================

section("48. Timeouts")

print(
    """
A distributed request should normally have a bounded timeout.

Without timeouts, one slow dependency can consume application resources for
an unbounded period.

Timeouts should be considered at multiple layers:

    Client timeout
    Gateway timeout
    Service timeout
    Database timeout

The timeout budget should be consistent with the end-to-end latency target.
"""
)


def simulate_request(
    processing_time: float,
    timeout: float,
) -> str:
    if processing_time > timeout:
        return "timeout"

    return "success"


print("Fast dependency:", simulate_request(0.2, 1.0))
print("Slow dependency:", simulate_request(1.5, 1.0))


# =============================================================================
# 49. CIRCUIT BREAKER
# =============================================================================

section("49. Circuit Breaker")

print(
    """
A circuit breaker prevents repeated calls to an unhealthy dependency.

Typical states:

    CLOSED
        Calls are allowed.

    OPEN
        Calls are blocked temporarily.

    HALF_OPEN
        Limited test calls determine whether the dependency recovered.

This prevents cascading failures.
"""
)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_seconds: float = 5,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at: Optional[float] = None

    def allow_request(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.opened_at is not None:
                if now - self.opened_at >= self.recovery_seconds:
                    self.state = CircuitState.HALF_OPEN
                    return True

            return False

        return True

    def record_success(self) -> None:
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None

    def record_failure(self, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now

        self.failures += 1

        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = now


breaker = CircuitBreaker(failure_threshold=3)

for failure in range(3):
    print("Request allowed:", breaker.allow_request(now=100))
    breaker.record_failure(now=100)

print("Circuit state:", breaker.state.value)
print("Request immediately allowed:", breaker.allow_request(now=101))
print("Request after recovery:", breaker.allow_request(now=106))


# =============================================================================
# 50. BULKHEAD PATTERN
# =============================================================================

section("50. Bulkhead Pattern")

print(
    """
The bulkhead pattern isolates resources so that failure in one workload does
not consume everything.

Example:

    Shared infrastructure
       |
       +-- Payment worker pool
       |
       +-- Email worker pool
       |
       +-- Reporting worker pool

If reporting becomes overloaded, payment processing retains dedicated
capacity.

The pattern is inspired by compartments in ships.
"""
)


@dataclass
class ResourcePool:
    name: str
    capacity: int
    active: int = 0

    def acquire(self) -> bool:
        if self.active >= self.capacity:
            return False

        self.active += 1
        return True

    def release(self) -> None:
        if self.active > 0:
            self.active -= 1


payment_pool = ResourcePool("payments", 3)
reporting_pool = ResourcePool("reporting", 2)

for _ in range(4):
    print("Payment capacity available:", payment_pool.acquire())

print("Reporting capacity available:", reporting_pool.acquire())


# =============================================================================
# 51. RATE LIMITING
# =============================================================================

section("51. Rate Limiting")

print(
    """
Rate limiting controls how much traffic a client can send.

Common algorithms:

    Fixed window
    Sliding window
    Token bucket
    Leaky bucket

Rate limiting protects:

    APIs
    Databases
    Expensive operations
    Authentication endpoints

It can also support fair resource sharing.
"""
)


class TokenBucket:
    def __init__(
        self,
        capacity: float,
        refill_rate: float,
    ) -> None:
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_time = time.time()

    def allow(
        self,
        cost: float = 1,
        now: Optional[float] = None,
    ) -> bool:
        now = time.time() if now is None else now

        elapsed = max(0.0, now - self.last_time)
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate,
        )
        self.last_time = now

        if self.tokens < cost:
            return False

        self.tokens -= cost
        return True


bucket = TokenBucket(capacity=3, refill_rate=1)

for timestamp in [100, 100, 100, 100, 101]:
    print(
        f"time={timestamp}, allowed={bucket.allow(now=timestamp)}, "
        f"tokens={bucket.tokens:.2f}"
    )


# =============================================================================
# 52. INFRASTRUCTURE AS CODE
# =============================================================================

section("52. Infrastructure as Code")

print(
    """
Infrastructure as Code represents infrastructure configuration in a
repeatable form.

Conceptual resources include:

    Network
    Subnets
    Security groups
    Databases
    Compute instances
    Load balancers
    Storage

Benefits:

    Repeatability
    Version control
    Review
    Automation
    Consistency

Important practices:

    Avoid hard-coded secrets.
    Separate environments.
    Review infrastructure changes.
    Prefer declarative descriptions where appropriate.
"""
)


@dataclass
class InfrastructureResource:
    resource_type: str
    name: str
    properties: dict[str, Any]


infrastructure_plan = [
    InfrastructureResource(
        "network",
        "main-vpc",
        {"cidr": "10.0.0.0/16"},
    ),
    InfrastructureResource(
        "subnet",
        "app-private-a",
        {"cidr": "10.0.11.0/24"},
    ),
    InfrastructureResource(
        "database",
        "main-db",
        {"engine": "postgresql", "private": True},
    ),
]

for resource in infrastructure_plan:
    print(
        resource.resource_type,
        resource.name,
        resource.properties,
    )


# =============================================================================
# 53. IMMUTABLE INFRASTRUCTURE
# =============================================================================

section("53. Immutable Infrastructure")

print(
    """
Immutable infrastructure treats deployed instances as replaceable rather
than manually modifying them indefinitely.

Instead of:

    Existing server
        -> SSH
        -> manually modify
        -> hope configuration is correct

the pattern is:

    Build version 2
        -> deploy version 2
        -> validate
        -> remove version 1

Benefits include reproducibility and reduced configuration drift.

The trade-off is that deployment pipelines and artifact management become
more important.
"""
)


@dataclass
class Deployment:
    version: str
    instances: list[str]


deployment_v1 = Deployment("1.0", ["instance-a", "instance-b"])
deployment_v2 = Deployment("2.0", ["instance-c", "instance-d"])

print("Old deployment:", deployment_v1)
print("New deployment:", deployment_v2)


# =============================================================================
# 54. BLUE-GREEN DEPLOYMENT
# =============================================================================

section("54. Blue-Green Deployment")

print(
    """
Blue-green deployment maintains two environments.

    Blue = current production
    Green = new version

Traffic is switched to green after validation.

Rollback can be relatively fast by switching traffic back to blue.

The trade-off is the cost of temporarily maintaining two environments.
"""
)


@dataclass
class Environment:
    name: str
    version: str
    healthy: bool


blue = Environment("blue", "1.0", True)
green = Environment("green", "2.0", True)

active_environment = blue

if green.healthy:
    active_environment = green

print("Active environment:", active_environment.name)
print("Version:", active_environment.version)


# =============================================================================
# 55. CANARY DEPLOYMENT
# =============================================================================

section("55. Canary Deployment")

print(
    """
Canary deployment gradually sends traffic to a new version.

Example:

    95% -> version 1
     5% -> version 2

If metrics remain healthy:

    80% -> version 1
    20% -> version 2

Then:

    50% -> version 1
    50% -> version 2

Eventually:

    0% -> version 1
    100% -> version 2

Canary releases reduce blast radius but require reliable monitoring and
traffic control.
"""
)


def canary_distribution(
    canary_percentage: float,
    total_requests: int,
) -> tuple[int, int]:
    if not 0 <= canary_percentage <= 100:
        raise ValueError("Percentage must be between 0 and 100")

    canary = round(total_requests * canary_percentage / 100)
    stable = total_requests - canary

    return stable, canary


for percentage in [5, 20, 50, 100]:
    print(
        f"{percentage}% canary:",
        canary_distribution(percentage, 1000),
    )


# =============================================================================
# 56. ROLLING DEPLOYMENT
# =============================================================================

section("56. Rolling Deployment")

print(
    """
A rolling deployment replaces instances gradually.

Example:

    Four old instances

    Step 1:
        3 old + 1 new

    Step 2:
        2 old + 2 new

    Step 3:
        1 old + 3 new

    Step 4:
        0 old + 4 new

The architecture must maintain enough healthy capacity during the rollout.
"""
)


def rolling_deployment(
    total_instances: int,
    batch_size: int,
) -> list[tuple[int, int]]:
    if total_instances <= 0 or batch_size <= 0:
        raise ValueError("Arguments must be positive")

    states = []
    remaining_old = total_instances

    while remaining_old > 0:
        replacement = min(batch_size, remaining_old)
        remaining_old -= replacement
        new_instances = total_instances - remaining_old
        states.append((remaining_old, new_instances))

    return states


print("Rolling deployment states:", rolling_deployment(4, 1))


# =============================================================================
# 57. MULTI-REGION ARCHITECTURE
# =============================================================================

section("57. Multi-Region Architecture")

print(
    """
Multi-region architecture places workloads in geographically separated
regions.

Possible patterns:

    Active-passive
        One region serves traffic; another is prepared for failover.

    Active-active
        Multiple regions serve traffic simultaneously.

Benefits:

    Geographic resilience
    Lower latency for global users
    Disaster recovery

Costs:

    Cross-region data transfer
    Replication complexity
    Operational complexity
    Data consistency challenges
    Higher cost
"""
)


@dataclass
class RegionStatus:
    name: str
    healthy: bool
    traffic_percentage: float


global_regions = [
    RegionStatus("region-a", True, 50),
    RegionStatus("region-b", True, 50),
]

print(
    "Traffic distribution:",
    [(region.name, region.traffic_percentage) for region in global_regions],
)

global_regions[0].healthy = False
global_regions[1].traffic_percentage = 100
global_regions[0].traffic_percentage = 0

print(
    "After region-a failure:",
    [(region.name, region.traffic_percentage) for region in global_regions],
)


# =============================================================================
# 58. COST ARCHITECTURE
# =============================================================================

section("58. Cloud Cost Architecture")

print(
    """
Cloud cost commonly comes from:

    Compute
    Storage
    Network transfer
    Managed databases
    Requests
    Logs
    Monitoring
    Data processing

Cost optimization techniques include:

    Right-sizing
    Autoscaling
    Removing unused resources
    Storage lifecycle policies
    Reserved or committed capacity where appropriate
    Architecture optimization
    Efficient data transfer
    Cost allocation and tagging

Lowest price is not necessarily lowest total cost.

A cheap architecture that creates outages or excessive engineering effort may
have a higher total cost.
"""
)


@dataclass
class CostComponent:
    name: str
    monthly_cost: float


cost_components = [
    CostComponent("Compute", 18000),
    CostComponent("Database", 12000),
    CostComponent("Storage", 2500),
    CostComponent("Network", 4500),
    CostComponent("Monitoring", 1500),
]

total_cost = sum(component.monthly_cost for component in cost_components)

print("Monthly illustrative cost:", total_cost)

for component in cost_components:
    percentage = component.monthly_cost / total_cost * 100
    print(f"{component.name}: {percentage:.1f}% of total")


# =============================================================================
# 59. COST VERSUS RELIABILITY
# =============================================================================

section("59. Architecture Trade-Offs")

print(
    """
Architecture rarely has one universally correct answer.

Typical trade-offs:

    Cost vs availability
    Cost vs performance
    Simplicity vs flexibility
    Consistency vs availability
    Managed services vs control
    Centralization vs autonomy
    Speed of delivery vs operational complexity
    Redundancy vs cost

Good architecture makes these trade-offs explicit.
"""
)


@dataclass
class ArchitectureOption:
    name: str
    monthly_cost: float
    availability_score: float
    complexity_score: float


options = [
    ArchitectureOption("Single zone", 100, 90, 20),
    ArchitectureOption("Multi-zone", 170, 99, 40),
    ArchitectureOption("Multi-region", 320, 99.9, 70),
]

for option in options:
    print(
        option.name,
        f"cost={option.monthly_cost}",
        f"availability={option.availability_score}",
        f"complexity={option.complexity_score}",
    )


# =============================================================================
# 60. TWELVE-FACTOR-STYLE APPLICATION DESIGN
# =============================================================================

section("60. Cloud-Native Application Principles")

print(
    """
Cloud-native applications commonly benefit from:

    Configuration separated from code
    Stateless processes
    Explicit dependencies
    Disposable instances
    Logs treated as event streams
    Fast startup and graceful shutdown
    Health checks
    Horizontal scaling
    Automated deployment
    Environment parity

The exact principles used should fit the application rather than being
applied mechanically.
"""
)


@dataclass
class ApplicationConfig:
    environment: str
    database_url: str
    log_level: str

    @classmethod
    def from_environment(
        cls,
        environment: str,
        database_url: str,
        log_level: str = "INFO",
    ) -> "ApplicationConfig":
        if not database_url:
            raise ValueError("Database URL is required")

        return cls(
            environment=environment,
            database_url=database_url,
            log_level=log_level,
        )


config = ApplicationConfig.from_environment(
    environment="development",
    database_url="postgresql://example",
)

print(config)


# =============================================================================
# 61. HEALTH CHECKS
# =============================================================================

section("61. Health Checks")

print(
    """
Health checks allow infrastructure to determine whether a workload should
receive traffic.

Common types:

    Liveness
        Is the process alive?

    Readiness
        Is the application ready to receive traffic?

A process can be alive but not ready.

For example:

    Application process running
        +
    Database connection unavailable
        =
    alive but not ready
"""
)


@dataclass
class HealthStatus:
    process_alive: bool
    database_available: bool
    dependencies_available: bool

    def liveness(self) -> bool:
        return self.process_alive

    def readiness(self) -> bool:
        return (
            self.process_alive
            and self.database_available
            and self.dependencies_available
        )


health = HealthStatus(True, True, False)

print("Liveness:", health.liveness())
print("Readiness:", health.readiness())


# =============================================================================
# 62. GRACEFUL SHUTDOWN
# =============================================================================

section("62. Graceful Shutdown")

print(
    """
Cloud workloads may be terminated during scaling, deployment, or failure.

Graceful shutdown allows a process to:

    Stop accepting new work
    Finish or safely cancel current work
    Close connections
    Flush important state
    Release resources

Applications should not assume that a process will run forever.
"""
)


class GracefulWorker:
    def __init__(self) -> None:
        self.accepting_work = True
        self.active_tasks = 0

    def start_task(self) -> bool:
        if not self.accepting_work:
            return False

        self.active_tasks += 1
        return True

    def finish_task(self) -> None:
        if self.active_tasks > 0:
            self.active_tasks -= 1

    def shutdown(self) -> None:
        self.accepting_work = False

        while self.active_tasks > 0:
            self.finish_task()


worker = GracefulWorker()

worker.start_task()
worker.start_task()

print("Active tasks before shutdown:", worker.active_tasks)

worker.shutdown()

print("Active tasks after shutdown:", worker.active_tasks)


# =============================================================================
# 63. DATA PARTITIONING / SHARDING
# =============================================================================

section("63. Database Partitioning and Sharding")

print(
    """
Partitioning divides data into manageable pieces.

Sharding distributes partitions across different database nodes.

Common shard keys might include:

    customer_id
    tenant_id
    geographic region
    account_id

A good shard key should distribute load evenly and align with access
patterns.

Poor shard keys can create hot partitions.
"""
)


def shard_for_key(key: str, shard_count: int) -> int:
    if shard_count <= 0:
        raise ValueError("Shard count must be positive")

    digest = hashlib.sha256(key.encode()).digest()

    return int.from_bytes(digest[:8], "big") % shard_count


for customer_id in ["customer-1", "customer-2", "customer-3", "customer-4"]:
    print(
        customer_id,
        "-> shard",
        shard_for_key(customer_id, 4),
    )


# =============================================================================
# 64. CONSISTENT HASHING
# =============================================================================

section("64. Consistent Hashing")

print(
    """
Consistent hashing is useful for distributed caches and routing systems.

The basic objective is to minimize how many keys move when nodes are added or
removed.

A simplified consistent-hashing ring can be represented by hash positions.
"""
)


class ConsistentHashRing:
    def __init__(self) -> None:
        self.nodes: list[tuple[int, str]] = []

    def add_node(self, node: str) -> None:
        position = int.from_bytes(
            hashlib.sha256(node.encode()).digest()[:8],
            "big",
        )

        self.nodes.append((position, node))
        self.nodes.sort()

    def remove_node(self, node: str) -> None:
        self.nodes = [
            item for item in self.nodes
            if item[1] != node
        ]

    def locate(self, key: str) -> str:
        if not self.nodes:
            raise RuntimeError("No nodes available")

        position = int.from_bytes(
            hashlib.sha256(key.encode()).digest()[:8],
            "big",
        )

        for node_position, node in self.nodes:
            if node_position >= position:
                return node

        return self.nodes[0][1]


ring = ConsistentHashRing()

for node in ["cache-a", "cache-b", "cache-c"]:
    ring.add_node(node)

for key in ["user:1", "user:2", "user:3", "user:4"]:
    print(key, "->", ring.locate(key))


# =============================================================================
# 65. MESSAGE ORDERING
# =============================================================================

section("65. Message Ordering")

print(
    """
Distributed messaging systems may provide different ordering guarantees.

Possible models:

    No ordering guarantee
    Ordering within a partition
    Ordering per key
    Global ordering

Global ordering can reduce scalability.

A common compromise is to preserve ordering for events belonging to the same
business entity.

For example:

    account-123:
        Deposit
        Withdrawal
        Transfer

while unrelated accounts can be processed independently.
"""
)


@dataclass
class OrderedEvent:
    key: str
    sequence: int
    event_type: str


events = [
    OrderedEvent("account-1", 1, "deposit"),
    OrderedEvent("account-1", 2, "withdrawal"),
    OrderedEvent("account-1", 3, "transfer"),
    OrderedEvent("account-2", 1, "deposit"),
]

for event in sorted(events, key=lambda item: (item.key, item.sequence)):
    print(event)


# =============================================================================
# 66. EXACTLY-ONCE MYTH AND DELIVERY SEMANTICS
# =============================================================================

section("66. Message Delivery Semantics")

print(
    """
Common delivery semantics include:

    At-most-once
        A message may be lost, but is not intentionally retried.

    At-least-once
        A message may be delivered more than once.

    Exactly-once
        Processing is defined so that the intended effect occurs once under
        the system's guarantees.

At-least-once delivery is common because it is practical.

Consumers should therefore often be idempotent.
"""
)


class IdempotentConsumer:
    def __init__(self) -> None:
        self.processed_ids: set[str] = set()
        self.processed_values: list[Any] = []

    def process(self, message: Message) -> bool:
        if message.message_id in self.processed_ids:
            return False

        self.processed_ids.add(message.message_id)
        self.processed_values.append(message.payload)

        return True


consumer = IdempotentConsumer()

message = Message("message-1", {"order_id": 100})

print("First processing:", consumer.process(message))
print("Duplicate processing:", consumer.process(message))


# =============================================================================
# 67. SAGA PATTERN
# =============================================================================

section("67. Distributed Transactions and Saga Pattern")

print(
    """
A distributed transaction across many independent services is difficult.

The Saga pattern breaks a business transaction into local transactions.

Example:

    Create order
        |
        v
    Reserve inventory
        |
        v
    Charge payment
        |
        v
    Confirm order

If payment fails:

    Release inventory
        |
        v
    Cancel order

Compensating actions reverse business effects rather than literally
undoing every database operation.
"""
)


@dataclass
class SagaStep:
    name: str
    action: Callable[[], bool]
    compensate: Callable[[], None]


def execute_saga(steps: list[SagaStep]) -> bool:
    completed: list[SagaStep] = []

    for step in steps:
        if step.action():
            completed.append(step)
            continue

        for completed_step in reversed(completed):
            completed_step.compensate()

        return False

    return True


saga_state: list[str] = []


def reserve_inventory() -> bool:
    saga_state.append("inventory-reserved")
    return True


def release_inventory() -> None:
    saga_state.append("inventory-released")


def charge_payment() -> bool:
    return False


def refund_payment() -> None:
    saga_state.append("payment-refunded")


saga = [
    SagaStep(
        "reserve-inventory",
        reserve_inventory,
        release_inventory,
    ),
    SagaStep(
        "charge-payment",
        charge_payment,
        refund_payment,
    ),
]

print("Saga successful:", execute_saga(saga))
print("Saga state:", saga_state)


# =============================================================================
# 68. CQRS
# =============================================================================

section("68. CQRS")

print(
    """
CQRS means Command Query Responsibility Segregation.

The basic idea is to separate:

    Commands
        Change state.

    Queries
        Read state.

This can be useful when read and write workloads have very different
requirements.

CQRS does not automatically require separate databases, though many
implementations eventually use separate read and write models.
"""
)


class CommandService:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {}

    def execute(self, key: str, value: Any) -> None:
        self.state[key] = value


class QueryService:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    def query(self, key: str) -> Any:
        return self.state.get(key)


command_service = CommandService()
command_service.execute("customer:1", {"name": "Asha"})

query_service = QueryService(command_service.state)

print("Query result:", query_service.query("customer:1"))


# =============================================================================
# 69. EVENT SOURCING
# =============================================================================

section("69. Event Sourcing")

print(
    """
Event sourcing stores state changes as an append-only sequence of events.

Instead of storing only:

    balance = 900

the system might store:

    AccountOpened
    Deposited 1000
    Withdrawn 100
    Deposited 0

Current state can be derived by replaying events.

Advantages:

    Auditability
    Historical reconstruction
    Event-driven integration

Costs:

    Event schema evolution
    Storage growth
    Replay complexity
    Operational complexity
"""
)


@dataclass
class AccountEvent:
    event_type: str
    amount: float


def rebuild_balance(events: list[AccountEvent]) -> float:
    balance = 0.0

    for event in events:
        if event.event_type == "deposit":
            balance += event.amount
        elif event.event_type == "withdraw":
            balance -= event.amount
        else:
            raise ValueError(f"Unknown event type: {event.event_type}")

    return balance


account_events = [
    AccountEvent("deposit", 1000),
    AccountEvent("withdraw", 100),
    AccountEvent("deposit", 250),
]

print("Rebuilt balance:", rebuild_balance(account_events))


# =============================================================================
# 70. DATA LAKES AND DATA WAREHOUSES
# =============================================================================

section("70. Data Lake Versus Data Warehouse")

print(
    """
Data lake:
    Often stores large volumes of raw or semi-structured data.

Data warehouse:
    Optimized for structured analytical queries and reporting.

Typical architecture:

    Applications
         |
         v
    Object Storage / Data Lake
         |
         v
    Transformation
         |
         v
    Data Warehouse
         |
         v
    BI / Analytics

The correct architecture depends on data volume, governance, query patterns,
latency requirements, and operational needs.
"""
)


@dataclass
class DataPipelineStage:
    name: str
    input_format: str
    output_format: str


pipeline = [
    DataPipelineStage("ingestion", "JSON/events", "raw files"),
    DataPipelineStage("transformation", "raw files", "validated tables"),
    DataPipelineStage("analytics", "validated tables", "business metrics"),
]

for stage in pipeline:
    print(
        f"{stage.name}: {stage.input_format} -> {stage.output_format}"
    )


# =============================================================================
# 71. DATA GOVERNANCE
# =============================================================================

section("71. Data Governance")

print(
    """
Cloud architecture must consider:

    Data ownership
    Classification
    Retention
    Access controls
    Encryption
    Auditability
    Data residency
    Deletion requirements
    Backup
    Recovery

Data classification might include:

    Public
    Internal
    Confidential
    Highly restricted

Controls should become stronger as sensitivity increases.
"""
)


class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


for classification in DataClassification:
    print(classification.value)


# =============================================================================
# 72. MULTI-TENANCY
# =============================================================================

section("72. Multi-Tenancy")

print(
    """
Multi-tenancy means one application serves multiple customers or tenants.

Common isolation models:

    Shared database, shared tables
    Shared database, separate schemas
    Separate database per tenant
    Separate infrastructure per tenant

There is a spectrum between:

    Operational simplicity
    Cost efficiency
    Isolation
    Customization

Tenant identifiers must be handled carefully to prevent cross-tenant data
access.
"""
)


@dataclass
class TenantRecord:
    tenant_id: str
    record_id: int
    value: str


def get_tenant_records(
    records: list[TenantRecord],
    tenant_id: str,
) -> list[TenantRecord]:
    return [
        record
        for record in records
        if record.tenant_id == tenant_id
    ]


tenant_records = [
    TenantRecord("tenant-a", 1, "A"),
    TenantRecord("tenant-b", 2, "B"),
    TenantRecord("tenant-a", 3, "C"),
]

print("Tenant-a records:", get_tenant_records(tenant_records, "tenant-a"))


# =============================================================================
# 73. API VERSIONING
# =============================================================================

section("73. API Versioning")

print(
    """
APIs evolve.

Common versioning approaches:

    URL:
        /v1/orders

    Header:
        Accept: application/vnd.example.v1+json

    Query parameter:
        ?version=1

Versioning requires decisions about:

    Backward compatibility
    Deprecation
    Migration
    Documentation
    Client support duration
"""
)


@dataclass
class APIVersion:
    version: str
    deprecated: bool = False


api_versions = [
    APIVersion("v1", deprecated=True),
    APIVersion("v2", deprecated=False),
]

for version in api_versions:
    print(version.version, "deprecated:", version.deprecated)


# =============================================================================
# 74. SECURITY THREAT MODELING
# =============================================================================

section("74. Threat Modeling")

print(
    """
Threat modeling identifies possible ways a system could be attacked.

Questions include:

    What are the assets?
    Who are the actors?
    What are the trust boundaries?
    What can go wrong?
    What controls reduce the risk?

STRIDE is one commonly used threat-modeling classification:

    Spoofing
    Tampering
    Repudiation
    Information disclosure
    Denial of service
    Elevation of privilege
"""
)


class ThreatType(Enum):
    SPOOFING = "Spoofing"
    TAMPERING = "Tampering"
    REPUDIATION = "Repudiation"
    INFORMATION_DISCLOSURE = "Information Disclosure"
    DENIAL_OF_SERVICE = "Denial of Service"
    ELEVATION_OF_PRIVILEGE = "Elevation of Privilege"


for threat in ThreatType:
    print(threat.value)


# =============================================================================
# 75. INPUT VALIDATION
# =============================================================================

section("75. Input Validation")

print(
    """
Cloud applications often sit behind public APIs.

Validation should occur before processing untrusted input.

Useful controls include:

    Type validation
    Length limits
    Range validation
    Schema validation
    Allow-lists
    Authentication
    Authorization

Validation is not a substitute for parameterized database queries, output
encoding, and other security controls.
"""
)


def validate_order_quantity(quantity: Any) -> int:
    if isinstance(quantity, bool):
        raise ValueError("Boolean is not a valid quantity")

    if not isinstance(quantity, int):
        raise TypeError("Quantity must be an integer")

    if not 1 <= quantity <= 100:
        raise ValueError("Quantity must be between 1 and 100")

    return quantity


for value in [1, 10, 100]:
    print("Valid quantity:", validate_order_quantity(value))

for value in [0, 101]:
    try:
        validate_order_quantity(value)
    except (ValueError, TypeError) as error:
        print("Rejected:", value, "-", error)


# =============================================================================
# 76. SECURE DEFAULTS
# =============================================================================

section("76. Secure Defaults")

print(
    """
Secure defaults reduce accidental exposure.

Examples:

    Database is private by default.
    Storage objects are private by default.
    Encryption is enabled by default.
    Logging is enabled for security events.
    Least privilege is the default.
    Administrative interfaces are not internet-accessible.
"""
)


@dataclass
class ResourceConfiguration:
    public_access: bool = False
    encryption_enabled: bool = True
    audit_logging: bool = True


secure_default = ResourceConfiguration()

print(secure_default)


# =============================================================================
# 77. FAULT TOLERANCE
# =============================================================================

section("77. Fault Tolerance")

print(
    """
Fault tolerance means the system continues operating despite failures.

Techniques include:

    Redundancy
    Replication
    Failover
    Retries
    Circuit breakers
    Bulkheads
    Graceful degradation
    Queue buffering

Graceful degradation means reducing functionality instead of failing the
entire application.

Example:

    Recommendation service unavailable
        -> checkout still works
        -> recommendations temporarily hidden
"""
)


def checkout_with_optional_recommendations(
    payment_available: bool,
    recommendations_available: bool,
) -> dict[str, Any]:
    if not payment_available:
        return {
            "checkout": "failed",
            "reason": "payment unavailable",
        }

    return {
        "checkout": "successful",
        "recommendations": (
            "shown"
            if recommendations_available
            else "temporarily unavailable"
        ),
    }


print(checkout_with_optional_recommendations(True, True))
print(checkout_with_optional_recommendations(True, False))


# =============================================================================
# 78. BACKPRESSURE
# =============================================================================

section("78. Backpressure")

print(
    """
Backpressure occurs when consumers cannot process work as quickly as
producers generate it.

Example:

    Producer: 1000 messages/sec
    Consumer: 500 messages/sec

The queue grows.

Architectural responses include:

    Scale consumers
    Rate-limit producers
    Batch work
    Drop non-critical work
    Increase capacity
    Apply admission control
"""
)


def queue_growth(
    production_rate: int,
    consumption_rate: int,
    seconds: int,
) -> int:
    return max(
        0,
        (production_rate - consumption_rate) * seconds,
    )


print(
    "Queue growth after 10 seconds:",
    queue_growth(1000, 500, 10),
)


# =============================================================================
# 79. ADMISSION CONTROL
# =============================================================================

section("79. Admission Control")

print(
    """
Admission control prevents a system from accepting more work than it can
safely process.

This is especially important during overload.

A service may return:

    HTTP 429 Too Many Requests
    HTTP 503 Service Unavailable

instead of allowing resource exhaustion to cascade.
"""
)


class AdmissionController:
    def __init__(self, maximum_concurrent: int) -> None:
        self.maximum_concurrent = maximum_concurrent
        self.current = 0

    def admit(self) -> bool:
        if self.current >= self.maximum_concurrent:
            return False

        self.current += 1
        return True

    def complete(self) -> None:
        if self.current > 0:
            self.current -= 1


admission = AdmissionController(2)

print(admission.admit())
print(admission.admit())
print(admission.admit())

admission.complete()

print(admission.admit())


# =============================================================================
# 80. SLO-DRIVEN ARCHITECTURE
# =============================================================================

section("80. SLO-Driven Architecture")

print(
    """
Architecture should start with measurable requirements.

Example:

    Availability SLO: 99.95%
    P95 latency: < 300 ms
    RTO: < 60 minutes
    RPO: < 15 minutes
    Maximum API error rate: < 0.1%

These requirements influence:

    Number of zones
    Replication
    Caching
    Database architecture
    Monitoring
    Disaster recovery
    Deployment strategy
"""
)


@dataclass
class ServiceObjectives:
    availability: float
    p95_latency_ms: float
    rto_minutes: int
    rpo_minutes: int


objectives = ServiceObjectives(
    availability=99.95,
    p95_latency_ms=300,
    rto_minutes=60,
    rpo_minutes=15,
)

print(objectives)


# =============================================================================
# 81. REFERENCE THREE-TIER ARCHITECTURE
# =============================================================================

section("81. Three-Tier Reference Architecture")

print(
    """
A traditional cloud web application can be organized into three logical
tiers:

    Presentation / Web Tier
        Handles HTTP requests and static content.

    Application Tier
        Implements business logic.

    Data Tier
        Stores durable application state.

Example:

        Users
          |
          v
        DNS
          |
          v
    CDN / Load Balancer
          |
          v
    Web/Application Tier
       /        \
      v          v
   Cache       Queue
      |
      v
   Database
      |
      v
 Object Storage

The actual architecture may combine or separate these layers differently.
"""
)


reference_architecture = {
    "edge": ["DNS", "CDN", "WAF", "Load Balancer"],
    "application": ["Web Servers", "API Services", "Workers"],
    "data": ["Relational Database", "Cache", "Object Storage"],
    "operations": ["Logs", "Metrics", "Traces", "Alerts"],
    "security": ["IAM", "Encryption", "Secrets", "Network Controls"],
}

for layer, components in reference_architecture.items():
    print(f"{layer}: {', '.join(components)}")


# =============================================================================
# 82. HIGHLY AVAILABLE WEB ARCHITECTURE
# =============================================================================

section("82. Highly Available Web Architecture")

print(
    """
A more resilient architecture can look like:

                   Internet
                       |
                       v
                    DNS/CDN
                       |
                       v
                Load Balancer
                  /       \
                 v         v
              Zone A     Zone B
                |           |
             App A1      App B1
             App A2      App B2
                 \         /
                  v       v
                  Shared Cache
                       |
                       v
              Multi-AZ Database
                       |
                       v
                Object Storage

Supporting systems:

    Monitoring
    Logging
    Alerting
    Backup
    Identity
    Secrets
"""
)


# =============================================================================
# 83. ZERO-DOWNTIME DEPLOYMENT ARCHITECTURE
# =============================================================================

section("83. Zero-Downtime Deployment Considerations")

print(
    """
Zero-downtime deployment requires more than replacing servers.

Important considerations:

    Multiple healthy instances
    Load balancer draining
    Backward-compatible APIs
    Database migration compatibility
    Health checks
    Deployment sequencing
    Rollback strategy

Database migrations often use an expand-and-contract approach:

    Expand:
        Add new schema without breaking old application.

    Migrate:
        Deploy application using new schema.

    Contract:
        Remove obsolete schema after all old clients are gone.
"""
)


@dataclass
class SchemaVersion:
    version: int
    supports_old_application: bool
    supports_new_application: bool


schema_versions = [
    SchemaVersion(1, True, False),
    SchemaVersion(2, True, True),
    SchemaVersion(3, False, True),
]

for schema in schema_versions:
    print(
        schema.version,
        "old-app:",
        schema.supports_old_application,
        "new-app:",
        schema.supports_new_application,
    )


# =============================================================================
# 84. ARCHITECTURE DECISION RECORD
# =============================================================================

section("84. Architecture Decision Records")

print(
    """
An Architecture Decision Record captures an important technical decision.

A useful ADR contains:

    Title
    Context
    Decision
    Alternatives considered
    Consequences

Example:

    Decision:
        Use asynchronous processing for image generation.

    Reason:
        Image generation is long-running and does not need to block the
        user's HTTP request.

    Consequences:
        Better user-facing latency, but eventual completion and job-status
        tracking are required.
"""
)


@dataclass
class ArchitectureDecision:
    title: str
    context: str
    decision: str
    alternatives: list[str]
    consequences: list[str]


adr = ArchitectureDecision(
    title="Asynchronous image processing",
    context="Image processing may take several seconds.",
    decision="Use queue-based asynchronous workers.",
    alternatives=[
        "Synchronous HTTP processing",
        "Dedicated long-running API process",
    ],
    consequences=[
        "Lower request latency",
        "Eventual completion",
        "Requires job tracking",
    ],
)

print(json.dumps(adr.__dict__, indent=2))


# =============================================================================
# 85. ARCHITECTURE REVIEW
# =============================================================================

section("85. Architecture Review Checklist")

print(
    """
A cloud architecture review should ask:

    Business
        - What business capability does the system provide?
        - What are the critical workflows?

    Availability
        - What are the SLOs?
        - What are the single points of failure?

    Scalability
        - What happens when traffic grows tenfold?
        - What scales horizontally?

    Performance
        - What is the latency target?
        - Where are likely bottlenecks?

    Security
        - Who can access each resource?
        - Is the network segmented?
        - Are secrets protected?

    Data
        - What data must be durable?
        - What consistency is required?
        - What is the backup and restore strategy?

    Reliability
        - What happens when a dependency fails?
        - Are retries bounded?
        - Are circuit breakers appropriate?

    Operations
        - Are logs, metrics, and traces available?
        - Can incidents be diagnosed?

    Deployment
        - Can releases be rolled back?
        - Are database migrations compatible?

    Cost
        - What are the major cost drivers?
        - Can capacity scale down?

    Compliance
        - Are data residency, retention, and audit requirements satisfied?
"""
)


# =============================================================================
# 86. ARCHITECTURE SCORING
# =============================================================================

@dataclass
class ArchitectureAssessment:
    security: int
    availability: int
    scalability: int
    performance: int
    observability: int
    cost_control: int

    def total(self) -> int:
        values = [
            self.security,
            self.availability,
            self.scalability,
            self.performance,
            self.observability,
            self.cost_control,
        ]

        return sum(values)

    def percentage(self) -> float:
        return self.total() / 60 * 100


assessment = ArchitectureAssessment(
    security=9,
    availability=8,
    scalability=9,
    performance=8,
    observability=9,
    cost_control=7,
)

print("Architecture score:", assessment.total(), "/ 60")
print(f"Architecture percentage: {assessment.percentage():.1f}%")


# =============================================================================
# 87. COMMON CLOUD ARCHITECTURE MISTAKES
# =============================================================================

section("87. Common Architecture Mistakes")

mistakes = [
    (
        "Putting databases directly on the public internet",
        "Increase isolation and use controlled private connectivity.",
    ),
    (
        "Hard-coding secrets in source code",
        "Use a secrets-management approach.",
    ),
    (
        "Assuming retries are always harmless",
        "Use bounded retries, backoff, and idempotency.",
    ),
    (
        "Using one availability zone for a critical service",
        "Distribute critical components across failure domains.",
    ),
    (
        "Creating microservices without a reason",
        "Start from business and operational requirements.",
    ),
    (
        "Ignoring observability until production",
        "Design logs, metrics, traces, and alerts with the service.",
    ),
    (
        "Choosing a database before understanding queries",
        "Start with access patterns and consistency requirements.",
    ),
    (
        "Treating backups as sufficient without restore testing",
        "Perform recovery tests.",
    ),
    (
        "Scaling only the application tier",
        "Check database, queue, network, cache, and downstream capacity.",
    ),
    (
        "Ignoring cost until the end",
        "Model major cost drivers during architecture design.",
    ),
]

for mistake, correction in mistakes:
    print(f"\nMistake: {mistake}\nBetter approach: {correction}")


# =============================================================================
# 88. EDGE CASES
# =============================================================================

section("88. Important Edge Cases")

print(
    """
Cloud architecture must account for cases such as:

    Zero healthy instances
    Partial zone failure
    Partial region failure
    Duplicate messages
    Delayed messages
    Out-of-order events
    Stale cache entries
    Expired credentials
    DNS caching
    Database replica lag
    Network partitions
    Sudden traffic spikes
    Slow dependencies
    Queue backlog
    Disk exhaustion
    Memory exhaustion
    Deployment incompatibility
    Invalid user input
    Partial transaction completion
    Clock differences
"""
)


def safe_average(values: list[float]) -> Optional[float]:
    if not values:
        return None

    return statistics.mean(values)


print("Average of empty list:", safe_average([]))
print("Average of values:", safe_average([10, 20, 30]))


# =============================================================================
# 89. ARCHITECTURE COMPARISON
# =============================================================================

section("89. Architectural Pattern Comparison")

comparison = {
    "Monolith": {
        "deployment": "single unit",
        "operational complexity": "low to medium",
        "scaling": "often coarse-grained",
        "distributed_failure": "lower",
    },
    "Microservices": {
        "deployment": "independent services",
        "operational complexity": "high",
        "scaling": "fine-grained",
        "distributed_failure": "high",
    },
    "Serverless": {
        "deployment": "functions/services",
        "operational complexity": "infrastructure abstracted",
        "scaling": "provider-managed",
        "distributed_failure": "depends on architecture",
    },
    "Event-driven": {
        "deployment": "producers/consumers",
        "operational complexity": "medium to high",
        "scaling": "consumer-based",
        "distributed_failure": "asynchronous",
    },
}

for pattern, properties in comparison.items():
    print(f"\n{pattern}")
    for key, value in properties.items():
        print(f"  {key}: {value}")


# =============================================================================
# 90. CLOUD ARCHITECTURE DESIGN PROCESS
# =============================================================================

section("90. A Systematic Cloud Architecture Design Process")

print(
    """
A practical architecture process can be organized as:

    1. Define business requirements.
    2. Define functional requirements.
    3. Define non-functional requirements.
    4. Identify users and workloads.
    5. Estimate traffic and data volume.
    6. Identify security requirements.
    7. Define availability and recovery objectives.
    8. Select an appropriate architecture style.
    9. Design networking.
   10. Design compute.
   11. Design storage and databases.
   12. Design application communication.
   13. Design identity and security controls.
   14. Design observability.
   15. Design deployment and rollback.
   16. Model failure scenarios.
   17. Estimate cost.
   18. Document important decisions.
   19. Test the architecture.
   20. Reassess as requirements change.
"""
)


# =============================================================================
# 91. REQUIREMENTS-TO-ARCHITECTURE MAPPING
# =============================================================================

section("91. Requirements-to-Architecture Mapping")


@dataclass
class Requirement:
    name: str
    value: Any
    architectural_implication: str


requirements = [
    Requirement(
        "High availability",
        "99.95%",
        "Use redundancy and remove critical single points of failure.",
    ),
    Requirement(
        "Low latency",
        "P95 < 300 ms",
        "Use caching, efficient queries, edge delivery, and low-latency paths.",
    ),
    Requirement(
        "RTO",
        "60 minutes",
        "Maintain an appropriate recovery strategy.",
    ),
    Requirement(
        "RPO",
        "15 minutes",
        "Use backups or replication at a suitable frequency.",
    ),
    Requirement(
        "Security",
        "Least privilege",
        "Use IAM, segmentation, encryption, and auditing.",
    ),
    Requirement(
        "Traffic growth",
        "10x",
        "Prefer scalable and elastic architecture.",
    ),
]

for requirement in requirements:
    print(
        f"{requirement.name}: {requirement.value}\n"
        f"  -> {requirement.architectural_implication}"
    )


# =============================================================================
# 92. SIMPLE REQUEST FLOW SIMULATION
# =============================================================================

section("92. End-to-End Request Flow")

print(
    """
The following simulation combines several concepts.

Request path:

    Client
      |
      v
    API Gateway
      |
      v
    Load Balancer
      |
      v
    Application
      |
      +----> Cache
      |
      +----> Database
      |
      +----> Queue
"""
)


@dataclass
class RequestResult:
    request_id: str
    status: int
    source: str
    latency_ms: float
    cache_hit: bool


class CloudApplicationSimulator:
    def __init__(self) -> None:
        self.cache: dict[str, dict[str, Any]] = {}
        self.database = {
            "product:1": {
                "id": 1,
                "name": "Laptop",
                "price": 75000,
            }
        }

    def request_product(self, product_id: int) -> RequestResult:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        key = f"product:{product_id}"

        if key in self.cache:
            result = self.cache[key]
            source = "cache"
            cache_hit = True
        else:
            result = self.database.get(key)

            if result is None:
                return RequestResult(
                    request_id=request_id,
                    status=404,
                    source="database",
                    latency_ms=0,
                    cache_hit=False,
                )

            self.cache[key] = result
            source = "database"
            cache_hit = False

        elapsed_ms = (time.perf_counter() - start) * 1000

        return RequestResult(
            request_id=request_id,
            status=200,
            source=source,
            latency_ms=elapsed_ms,
            cache_hit=cache_hit,
        )


simulator = CloudApplicationSimulator()

first_request = simulator.request_product(1)
second_request = simulator.request_product(1)

print("First request:", first_request)
print("Second request:", second_request)


# =============================================================================
# 93. FAILURE-INJECTION SIMULATION
# =============================================================================

section("93. Failure Injection")

print(
    """
Failure injection deliberately models failures so that architecture can be
tested against them.

Examples:

    Kill an application instance.
    Stop a worker.
    Make a dependency slow.
    Reject database connections.
    Fill a queue.
    Simulate zone loss.
    Simulate region loss.

The goal is to validate assumptions rather than wait for production failure.
"""
)


@dataclass
class Dependency:
    name: str
    healthy: bool = True
    latency_ms: int = 50


def call_dependency(dependency: Dependency) -> dict[str, Any]:
    if not dependency.healthy:
        return {
            "success": False,
            "error": f"{dependency.name} unavailable",
        }

    return {
        "success": True,
        "latency_ms": dependency.latency_ms,
    }


payment_dependency = Dependency("payment-service")

print(call_dependency(payment_dependency))

payment_dependency.healthy = False

print(call_dependency(payment_dependency))


# =============================================================================
# 94. PRODUCTION READINESS
# =============================================================================

section("94. Production Readiness")

print(
    """
A production cloud workload should normally have explicit answers for:

    Architecture
        - Dependencies documented
        - Failure domains understood

    Security
        - Least privilege
        - Encryption
        - Secrets protection
        - Network segmentation
        - Security logging

    Reliability
        - Health checks
        - Redundancy
        - Recovery plan
        - Backup and restore tests

    Operations
        - Logs
        - Metrics
        - Traces
        - Alerts
        - Runbooks

    Deployment
        - Automated build
        - Automated testing
        - Safe rollout
        - Rollback

    Performance
        - Capacity model
        - Load testing
        - Bottleneck identification

    Cost
        - Budget
        - Cost allocation
        - Resource cleanup

    Governance
        - Data classification
        - Retention
        - Access reviews
"""
)


@dataclass
class ProductionReadiness:
    architecture_documented: bool
    security_controls: bool
    backups_tested: bool
    monitoring: bool
    deployment_rollback: bool
    load_testing: bool
    cost_monitoring: bool

    def ready_items(self) -> int:
        return sum(
            [
                self.architecture_documented,
                self.security_controls,
                self.backups_tested,
                self.monitoring,
                self.deployment_rollback,
                self.load_testing,
                self.cost_monitoring,
            ]
        )

    def readiness_percentage(self) -> float:
        return self.ready_items() / 7 * 100


readiness = ProductionReadiness(
    architecture_documented=True,
    security_controls=True,
    backups_tested=True,
    monitoring=True,
    deployment_rollback=True,
    load_testing=False,
    cost_monitoring=True,
)

print(
    f"Production readiness: "
    f"{readiness.readiness_percentage():.1f}%"
)


# =============================================================================
# 95. UNIT TESTS
# =============================================================================

section("95. Built-In Tests")

print(
    """
Testing cloud architecture involves more than unit testing.

Useful layers include:

    Unit tests
        Individual functions and classes.

    Integration tests
        Interaction between components.

    Contract tests
        Compatibility between service interfaces.

    Load tests
        Behavior under expected and peak traffic.

    Resilience tests
        Behavior under failures.

    Security tests
        Authentication, authorization, configuration, and vulnerability
        controls.

    Disaster recovery tests
        Ability to restore service and data.
"""
)


def run_assertion_tests() -> None:
    assert same_subnet(
        "10.0.1.1",
        "10.0.1.2",
        "255.255.255.0",
    )

    assert not same_subnet(
        "10.0.1.1",
        "10.0.2.1",
        "255.255.255.0",
    )

    assert validate_order_quantity(1) == 1

    try:
        validate_order_quantity(0)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid quantity should fail")

    test_bucket = TokenBucket(2, 0)

    assert test_bucket.allow(now=100)
    assert test_bucket.allow(now=100)
    assert not test_bucket.allow(now=100)

    test_breaker = CircuitBreaker(2)

    assert test_breaker.allow_request(now=100)
    test_breaker.record_failure(now=100)
    test_breaker.record_failure(now=100)

    assert test_breaker.state == CircuitState.OPEN
    assert not test_breaker.allow_request(now=101)

    print("All built-in assertions passed.")


run_assertion_tests()


# =============================================================================
# 96. ARCHITECTURE KNOWLEDGE MAP
# =============================================================================

section("96. Cloud Architecture Knowledge Map")

knowledge_map = {
    "Cloud foundation": [
        "Service models",
        "Deployment models",
        "Regions",
        "Availability zones",
    ],
    "Compute": [
        "Virtual machines",
        "Containers",
        "Serverless",
        "Autoscaling",
    ],
    "Networking": [
        "IP addressing",
        "Subnets",
        "Routing",
        "Firewalls",
        "DNS",
        "Load balancing",
    ],
    "Storage": [
        "Block",
        "File",
        "Object",
        "Durability",
        "Backup",
    ],
    "Data": [
        "Relational databases",
        "NoSQL",
        "Replication",
        "Partitioning",
        "Consistency",
    ],
    "Application architecture": [
        "Monolith",
        "Microservices",
        "API gateways",
        "Queues",
        "Events",
        "CQRS",
        "Saga",
    ],
    "Security": [
        "IAM",
        "Least privilege",
        "Encryption",
        "Secrets",
        "Zero trust",
        "Segmentation",
    ],
    "Reliability": [
        "High availability",
        "Retries",
        "Circuit breakers",
        "Bulkheads",
        "Disaster recovery",
    ],
    "Operations": [
        "Logs",
        "Metrics",
        "Traces",
        "SLOs",
        "Deployment strategies",
    ],
    "Architecture governance": [
        "Cost",
        "ADRs",
        "Data governance",
        "Production readiness",
    ],
}

for category, topics in knowledge_map.items():
    print(f"\n{category}:")
    for topic in topics:
        print(f"  - {topic}")


# =============================================================================
# 97. FINAL INTEGRATED ARCHITECTURE MODEL
# =============================================================================

section("97. Integrated Cloud Architecture Model")

print(
    r"""
                         INTERNET USERS
                              |
                              v
                       DNS / GLOBAL ROUTING
                              |
                              v
                         CDN / WAF
                              |
                              v
                       LOAD BALANCER
                         /       \
                        /         \
                       v           v
                 AVAILABILITY   AVAILABILITY
                    ZONE A         ZONE B
                      |               |
                  APP NODE A      APP NODE B
                      |               |
                      +-------+-------+
                              |
                         SERVICE LAYER
                      /      |       \
                     /       |        \
                    v        v         v
                 CACHE     QUEUE      API
                              |
                              v
                          WORKERS
                              |
                 +------------+------------+
                 |            |            |
                 v            v            v
             DATABASE    OBJECT STORAGE   SEARCH
                 |
                 v
          REPLICATED BACKUPS
                 |
                 v
          SECONDARY REGION

Supporting architecture:

    IAM
    Secrets Management
    Encryption
    Network Segmentation
    Monitoring
    Logging
    Distributed Tracing
    Alerting
    Infrastructure as Code
    CI/CD
    Disaster Recovery
    Cost Management
    Governance

The architecture is a set of interacting systems rather than a collection
of isolated cloud services.

The most important architectural questions are:

    What must be available?
    What can fail?
    What must scale?
    What must remain consistent?
    What data must never be lost?
    Who can access what?
    How will failures be detected?
    How will the system recover?
    How will deployments be reversed?
    What will the architecture cost?
"""
)


# =============================================================================
# 98. COMPLETION CHECK
# =============================================================================

section("98. Study File Completion Check")

covered_sections = [
    "Cloud computing foundations",
    "Service and deployment models",
    "Cloud geography",
    "Compute",
    "Networking",
    "Storage",
    "Databases",
    "Caching",
    "CDN",
    "API gateway",
    "Queues",
    "Events",
    "Microservices",
    "Containers",
    "Serverless",
    "IAM",
    "Encryption",
    "Secrets",
    "Zero trust",
    "High availability",
    "Disaster recovery",
    "Observability",
    "Performance",
    "Distributed systems",
    "CAP and consistency",
    "Resilience patterns",
    "Infrastructure as Code",
    "Deployment strategies",
    "Multi-region",
    "Cost architecture",
    "Data architecture",
    "Security architecture",
    "Production readiness",
]

print(f"Major topic groups demonstrated: {len(covered_sections)}")

for number, topic in enumerate(covered_sections, start=1):
    print(f"{number:02d}. {topic}")

print("\nCloud architecture fundamentals study script completed successfully.")
