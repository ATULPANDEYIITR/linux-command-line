"""
Cloud Infrastructure Components: Beginner to Advanced
=======================================================

A self-contained educational study script covering:

1. Servers and compute
2. Storage
3. Networking
4. Virtualization
5. Hypervisors
6. Data centers
7. Cloud regions
8. Availability zones
9. Reliability and fault domains
10. Infrastructure architecture
11. Scaling and load balancing
12. Security fundamentals
13. Performance and cost considerations
14. Capacity planning
15. Failure simulation
16. Infrastructure design exercises
17. Testing and validation

The script uses only Python's standard library.

Run:
    python cloud_infrastructure_components.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from ipaddress import IPv4Network, IPv4Address
from math import ceil
from random import Random
from typing import Dict, List, Optional, Tuple


# =============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# =============================================================================

def section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    """Print a subsection heading."""
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def explain_fundamentals() -> None:
    section("1. CLOUD INFRASTRUCTURE FUNDAMENTALS")

    concepts = {
        "Cloud infrastructure": (
            "The physical and virtual computing resources used to run workloads "
            "through a cloud platform."
        ),
        "Compute": (
            "CPU and memory resources used to execute operating systems, "
            "applications, services, and workloads."
        ),
        "Storage": (
            "Resources used to persist data. Common models are block, file, "
            "and object storage."
        ),
        "Networking": (
            "The connectivity layer that allows systems to communicate with "
            "each other and with external networks."
        ),
        "Virtualization": (
            "A technique that abstracts physical hardware into logical resources "
            "such as virtual machines."
        ),
        "Hypervisor": (
            "Software or firmware that creates and manages virtual machines."
        ),
        "Data center": (
            "A physical facility containing servers, storage, networking, power, "
            "cooling, security, and operational infrastructure."
        ),
        "Region": (
            "A geographic cloud deployment area containing one or more isolated "
            "availability zones."
        ),
        "Availability Zone": (
            "An isolated infrastructure location within a region designed to "
            "reduce the impact of localized failures."
        ),
        "Fault domain": (
            "A set of resources that may fail together because they share "
            "infrastructure or dependencies."
        ),
    }

    for name, definition in concepts.items():
        print(f"{name:22} : {definition}")

    print(
        "\nCore abstraction:\n"
        "Physical hardware -> Data center -> Availability Zone -> Region -> "
        "Cloud service -> Application workload"
    )


# =============================================================================
# 2. SERVERS AND COMPUTE
# =============================================================================

class ServerType(Enum):
    PHYSICAL = "Physical Server"
    VIRTUAL = "Virtual Machine"
    CONTAINER_HOST = "Container Host"
    BARE_METAL = "Bare Metal"


@dataclass
class Server:
    """Simplified model of a compute server."""

    name: str
    cpu_cores: int
    memory_gb: int
    storage_gb: int
    server_type: ServerType = ServerType.PHYSICAL
    operating_system: str = "Linux"
    utilization_percent: float = 0.0
    running: bool = True

    def cpu_capacity(self) -> int:
        return self.cpu_cores

    def memory_capacity(self) -> int:
        return self.memory_gb

    def allocate_cpu(self, cores: float) -> bool:
        """Allocate CPU if sufficient unused capacity exists."""
        if not self.running or cores < 0:
            return False

        current_usage = self.cpu_cores * self.utilization_percent / 100
        if current_usage + cores > self.cpu_cores:
            return False

        self.utilization_percent = (
            (current_usage + cores) / self.cpu_cores * 100
        )
        return True

    def release_cpu(self, cores: float) -> None:
        """Release CPU allocation while preventing negative utilization."""
        if self.cpu_cores <= 0:
            return

        current_usage = self.cpu_cores * self.utilization_percent / 100
        current_usage = max(0.0, current_usage - max(0.0, cores))
        self.utilization_percent = current_usage / self.cpu_cores * 100

    def stop(self) -> None:
        self.running = False

    def start(self) -> None:
        self.running = True

    def status(self) -> str:
        state = "RUNNING" if self.running else "STOPPED"
        return (
            f"{self.name}: {state}, "
            f"{self.cpu_cores} CPU cores, "
            f"{self.memory_gb} GB RAM, "
            f"{self.storage_gb} GB local storage, "
            f"{self.utilization_percent:.1f}% CPU"
        )


def demonstrate_servers() -> None:
    section("2. SERVERS AND COMPUTE")

    subsection("Physical server")

    physical = Server(
        name="physical-01",
        cpu_cores=32,
        memory_gb=128,
        storage_gb=2000,
        server_type=ServerType.PHYSICAL,
    )

    print(physical.status())
    print("CPU allocation successful:", physical.allocate_cpu(8))
    print(physical.status())
    physical.release_cpu(3)
    print("After releasing 3 cores:")
    print(physical.status())

    subsection("Server characteristics")

    characteristics = [
        ("CPU", "Executes instructions and determines computational capacity."),
        ("RAM", "Fast volatile memory used by running processes."),
        ("Local disk", "Persistent storage physically attached to the server."),
        ("NIC", "Network Interface Card used for network communication."),
        ("Power supply", "Provides electrical power; redundant PSUs improve resilience."),
        ("Motherboard", "Connects major physical hardware components."),
        ("GPU", "Specialized processor useful for parallel workloads such as ML."),
    ]

    for component, purpose in characteristics:
        print(f"{component:18} -> {purpose}")

    subsection("Compute capacity calculation")

    workload_cpu = 3.5
    workload_memory = 10
    host_cpu = 16
    host_memory = 64

    cpu_hosts = ceil(workload_cpu / host_cpu)
    memory_hosts = ceil(workload_memory / host_memory)

    print(f"One workload requires {workload_cpu} CPU cores and {workload_memory} GB RAM.")
    print(f"CPU-only minimum hosts: {cpu_hosts}")
    print(f"Memory-only minimum hosts: {memory_hosts}")
    print(
        "A real placement decision must consider both dimensions, "
        "operating-system overhead, redundancy, and workload growth."
    )


# =============================================================================
# 3. STORAGE
# =============================================================================

class StorageType(Enum):
    BLOCK = "Block Storage"
    FILE = "File Storage"
    OBJECT = "Object Storage"


@dataclass
class StorageVolume:
    """Simplified storage resource."""

    name: str
    capacity_gb: int
    storage_type: StorageType
    used_gb: int = 0
    encrypted: bool = True

    def write(self, amount_gb: int) -> bool:
        if amount_gb < 0:
            raise ValueError("Write amount cannot be negative.")

        if self.used_gb + amount_gb > self.capacity_gb:
            return False

        self.used_gb += amount_gb
        return True

    def delete(self, amount_gb: int) -> None:
        if amount_gb < 0:
            raise ValueError("Delete amount cannot be negative.")

        self.used_gb = max(0, self.used_gb - amount_gb)

    @property
    def free_gb(self) -> int:
        return self.capacity_gb - self.used_gb

    @property
    def utilization_percent(self) -> float:
        if self.capacity_gb == 0:
            return 0.0
        return self.used_gb / self.capacity_gb * 100


def demonstrate_storage() -> None:
    section("3. STORAGE")

    subsection("Storage models")

    storage_models = {
        StorageType.BLOCK: (
            "Provides raw volumes to operating systems. Suitable for databases "
            "and virtual-machine disks."
        ),
        StorageType.FILE: (
            "Provides a shared hierarchical file system. Useful when multiple "
            "systems need shared files."
        ),
        StorageType.OBJECT: (
            "Stores objects with metadata and identifiers. Suitable for backups, "
            "media, logs, archives, and large unstructured datasets."
        ),
    }

    for storage_type, description in storage_models.items():
        print(f"{storage_type.value:18} -> {description}")

    subsection("Storage demonstration")

    database_disk = StorageVolume(
        name="database-volume",
        capacity_gb=1000,
        storage_type=StorageType.BLOCK,
        encrypted=True,
    )

    print("Encrypted:", database_disk.encrypted)
    print("Write 400 GB:", database_disk.write(400))
    print("Write 500 GB:", database_disk.write(500))
    print("Write 200 GB:", database_disk.write(200))
    print(
        f"Used={database_disk.used_gb} GB, "
        f"Free={database_disk.free_gb} GB, "
        f"Utilization={database_disk.utilization_percent:.1f}%"
    )

    subsection("Important storage distinctions")

    comparisons = [
        ("Block", "Low-level volume", "Databases, VM disks", "Usually low latency"),
        ("File", "Shared filesystem", "Shared application files", "Filesystem semantics"),
        ("Object", "Object + metadata", "Backups, media, archives", "Highly scalable"),
    ]

    for model, abstraction, workload, characteristic in comparisons:
        print(
            f"{model:8} | {abstraction:22} | "
            f"{workload:28} | {characteristic}"
        )


# =============================================================================
# 4. NETWORKING
# =============================================================================

@dataclass
class NetworkPacket:
    source: IPv4Address
    destination: IPv4Address
    protocol: str
    payload_size_bytes: int


@dataclass
class FirewallRule:
    source_network: IPv4Network
    destination_port: int
    protocol: str
    action: str = "ALLOW"

    def matches(self, packet: NetworkPacket, destination_port: int) -> bool:
        return (
            packet.source in self.source_network
            and destination_port == self.destination_port
            and packet.protocol.upper() == self.protocol.upper()
        )


class SimpleFirewall:
    """Educational state-free firewall model."""

    def __init__(self, default_action: str = "DENY") -> None:
        self.rules: List[FirewallRule] = []
        self.default_action = default_action.upper()

    def add_rule(self, rule: FirewallRule) -> None:
        if rule.action.upper() not in {"ALLOW", "DENY"}:
            raise ValueError("Firewall action must be ALLOW or DENY.")
        self.rules.append(rule)

    def evaluate(self, packet: NetworkPacket, destination_port: int) -> str:
        # First matching rule wins in this simplified model.
        for rule in self.rules:
            if rule.matches(packet, destination_port):
                return rule.action.upper()
        return self.default_action


@dataclass
class Route:
    destination: IPv4Network
    next_hop: str


class RouteTable:
    """Longest-prefix-match routing demonstration."""

    def __init__(self) -> None:
        self.routes: List[Route] = []

    def add_route(self, destination: str, next_hop: str) -> None:
        self.routes.append(
            Route(
                destination=IPv4Network(destination),
                next_hop=next_hop,
            )
        )

    def lookup(self, address: str) -> Optional[str]:
        target = IPv4Address(address)
        matching_routes = [
            route
            for route in self.routes
            if target in route.destination
        ]

        if not matching_routes:
            return None

        # Longest prefix wins.
        best_route = max(
            matching_routes,
            key=lambda route: route.destination.prefixlen,
        )
        return best_route.next_hop


def demonstrate_networking() -> None:
    section("4. NETWORKING")

    subsection("Core networking components")

    components = [
        ("IP address", "Logical address identifying a network interface."),
        ("Subnet", "A logical subdivision of an IP network."),
        ("Router", "Forwards packets between networks."),
        ("Switch", "Connects devices within a local network."),
        ("DNS", "Maps human-readable names to network addresses."),
        ("Load balancer", "Distributes traffic across backend resources."),
        ("Firewall", "Controls traffic according to security policy."),
        ("Gateway", "A path or service through which traffic reaches another network."),
        ("Port", "Logical endpoint identifying a service."),
        ("Protocol", "Rules governing communication, such as TCP or UDP."),
    ]

    for name, definition in components:
        print(f"{name:16} -> {definition}")

    subsection("Subnet calculation")

    network = IPv4Network("10.0.0.0/24")
    print("Network:", network)
    print("Network address:", network.network_address)
    print("Broadcast address:", network.broadcast_address)
    print("Prefix length:", network.prefixlen)
    print("Total addresses:", network.num_addresses)

    usable_addresses = max(0, network.num_addresses - 2)
    print("Traditional IPv4 usable host addresses:", usable_addresses)

    subsection("Routing and longest-prefix matching")

    route_table = RouteTable()
    route_table.add_route("0.0.0.0/0", "internet-gateway")
    route_table.add_route("10.0.0.0/8", "private-router")
    route_table.add_route("10.20.0.0/16", "application-router")
    route_table.add_route("10.20.5.0/24", "database-router")

    for address in ["8.8.8.8", "10.1.2.3", "10.20.7.8", "10.20.5.20"]:
        print(f"{address:15} -> {route_table.lookup(address)}")

    subsection("Firewall evaluation")

    firewall = SimpleFirewall(default_action="DENY")
    firewall.add_rule(
        FirewallRule(
            source_network=IPv4Network("10.0.0.0/8"),
            destination_port=443,
            protocol="TCP",
            action="ALLOW",
        )
    )

    packets = [
        NetworkPacket(
            source=IPv4Address("10.1.1.10"),
            destination=IPv4Address("10.2.2.20"),
            protocol="TCP",
            payload_size_bytes=1200,
        ),
        NetworkPacket(
            source=IPv4Address("192.168.1.10"),
            destination=IPv4Address("10.2.2.20"),
            protocol="TCP",
            payload_size_bytes=1200,
        ),
        NetworkPacket(
            source=IPv4Address("10.1.1.10"),
            destination=IPv4Address("10.2.2.20"),
            protocol="UDP",
            payload_size_bytes=800,
        ),
    ]

    for packet in packets:
        decision = firewall.evaluate(packet, 443)
        print(
            f"{packet.source} -> {packet.destination}:443 "
            f"{packet.protocol} => {decision}"
        )


# =============================================================================
# 5. VIRTUALIZATION
# =============================================================================

@dataclass
class VirtualMachine:
    """Virtual machine allocated from a physical host."""

    name: str
    vcpu: int
    memory_gb: int
    disk_gb: int
    running: bool = True


@dataclass
class Hypervisor:
    """
    Simplified Type 1 hypervisor.

    Type 1 hypervisors run directly on hardware.
    Type 2 hypervisors run above a host operating system.
    """

    host: Server
    virtual_machines: List[VirtualMachine] = field(default_factory=list)

    @property
    def allocated_cpu(self) -> int:
        return sum(vm.vcpu for vm in self.virtual_machines if vm.running)

    @property
    def allocated_memory(self) -> int:
        return sum(vm.memory_gb for vm in self.virtual_machines if vm.running)

    @property
    def allocated_disk(self) -> int:
        return sum(vm.disk_gb for vm in self.virtual_machines)

    def create_vm(
        self,
        name: str,
        vcpu: int,
        memory_gb: int,
        disk_gb: int,
    ) -> Optional[VirtualMachine]:
        if vcpu <= 0 or memory_gb <= 0 or disk_gb <= 0:
            raise ValueError("VM resources must be positive.")

        if self.allocated_cpu + vcpu > self.host.cpu_cores:
            return None

        if self.allocated_memory + memory_gb > self.host.memory_gb:
            return None

        if self.allocated_disk + disk_gb > self.host.storage_gb:
            return None

        vm = VirtualMachine(
            name=name,
            vcpu=vcpu,
            memory_gb=memory_gb,
            disk_gb=disk_gb,
        )

        self.virtual_machines.append(vm)
        return vm

    def destroy_vm(self, name: str) -> bool:
        for index, vm in enumerate(self.virtual_machines):
            if vm.name == name:
                del self.virtual_machines[index]
                return True
        return False

    def inventory(self) -> None:
        print(f"Hypervisor host: {self.host.name}")
        print(
            f"Allocated CPU: {self.allocated_cpu}/"
            f"{self.host.cpu_cores} cores"
        )
        print(
            f"Allocated RAM: {self.allocated_memory}/"
            f"{self.host.memory_gb} GB"
        )
        print(
            f"Allocated disk: {self.allocated_disk}/"
            f"{self.host.storage_gb} GB"
        )

        for vm in self.virtual_machines:
            print(
                f"  {vm.name}: "
                f"{vm.vcpu} vCPU, "
                f"{vm.memory_gb} GB RAM, "
                f"{vm.disk_gb} GB disk"
            )


def demonstrate_virtualization() -> None:
    section("5. VIRTUALIZATION AND HYPERVISORS")

    subsection("Virtualization concepts")

    print(
        "Virtualization allows one physical server to host multiple isolated "
        "virtual machines."
    )
    print(
        "A hypervisor provides CPU, memory, storage, and device abstraction "
        "to virtual machines."
    )

    subsection("Type 1 vs Type 2")

    comparison = [
        ("Type 1", "Hardware", "Server/cloud environments", "Lower abstraction overhead"),
        ("Type 2", "Host operating system", "Desktop/development", "Simpler for personal use"),
    ]

    print(f"{'Type':10} | {'Runs on':22} | {'Common use':25} | Characteristic")
    for item in comparison:
        print(f"{item[0]:10} | {item[1]:22} | {item[2]:25} | {item[3]}")

    subsection("VM creation")

    host = Server(
        name="hypervisor-01",
        cpu_cores=16,
        memory_gb=64,
        storage_gb=1000,
        server_type=ServerType.BARE_METAL,
    )

    hypervisor = Hypervisor(host)

    for name, cpu, memory, disk in [
        ("web-01", 2, 8, 100),
        ("web-02", 2, 8, 100),
        ("api-01", 4, 16, 150),
        ("database-01", 8, 32, 400),
    ]:
        vm = hypervisor.create_vm(name, cpu, memory, disk)
        print(f"Created {name}: {vm is not None}")

    hypervisor.inventory()

    print(
        "\nAttempting an over-capacity VM:",
        hypervisor.create_vm("large-vm", 4, 16, 100) is not None,
    )

    subsection("Virtualization trade-offs")

    tradeoffs = [
        ("Isolation", "VMs provide strong workload isolation.", "Isolation is not identical to a security boundary in every design."),
        ("Density", "Many VMs can share one physical host.", "Oversubscription can cause contention."),
        ("Flexibility", "VMs can be provisioned and moved efficiently.", "Virtualization adds management complexity."),
        ("Hardware utilization", "Unused physical capacity can be consolidated.", "Poor capacity planning can still waste resources."),
    ]

    for topic, advantage, concern in tradeoffs:
        print(f"{topic:22} | Advantage: {advantage}")
        print(f"{'':22} | Concern:   {concern}")


# =============================================================================
# 6. DATA CENTERS
# =============================================================================

@dataclass
class DataCenter:
    name: str
    region: str
    power_capacity_mw: float
    cooling_capacity_mw: float
    server_count: int
    network_redundancy: int = 2
    power_redundancy: int = 2

    def can_support_load(self, compute_load_mw: float) -> bool:
        return (
            compute_load_mw <= self.power_capacity_mw
            and compute_load_mw <= self.cooling_capacity_mw
        )

    def resilience_score(self) -> float:
        """
        Educational score, not an industry-standard metric.
        """
        score = 0.0
        score += min(self.network_redundancy, 4) * 25
        score += min(self.power_redundancy, 4) * 25
        return min(score, 100.0)


def demonstrate_data_centers() -> None:
    section("6. DATA CENTERS")

    subsection("Physical infrastructure")

    systems = [
        ("Servers", "Execute workloads."),
        ("Storage arrays", "Provide persistent data storage."),
        ("Network fabric", "Connect servers, storage, and external networks."),
        ("Power systems", "Provide electrical power and backup capacity."),
        ("Cooling systems", "Remove heat generated by IT equipment."),
        ("Physical security", "Controls access to facilities and hardware."),
        ("Fire suppression", "Protects infrastructure from fire events."),
        ("Monitoring", "Measures power, temperature, network, hardware, and health."),
    ]

    for system, purpose in systems:
        print(f"{system:20} -> {purpose}")

    subsection("Data center capacity")

    dc = DataCenter(
        name="DC-A",
        region="Region-1",
        power_capacity_mw=10.0,
        cooling_capacity_mw=9.0,
        server_count=5000,
        network_redundancy=2,
        power_redundancy=2,
    )

    print("Data center:", dc.name)
    print("Server count:", dc.server_count)
    print("Can support 8 MW:", dc.can_support_load(8.0))
    print("Can support 9.5 MW:", dc.can_support_load(9.5))
    print("Educational resilience score:", dc.resilience_score())

    print(
        "\nImportant principle: power, cooling, network capacity, rack space, "
        "and compute capacity are separate constraints."
    )


# =============================================================================
# 7. REGIONS AND AVAILABILITY ZONES
# =============================================================================

@dataclass
class AvailabilityZone:
    name: str
    data_centers: List[DataCenter]
    healthy: bool = True

    @property
    def server_capacity(self) -> int:
        return sum(dc.server_count for dc in self.data_centers)


@dataclass
class Region:
    name: str
    geography: str
    availability_zones: List[AvailabilityZone]

    def total_servers(self) -> int:
        return sum(
            zone.server_capacity
            for zone in self.availability_zones
        )

    def healthy_zones(self) -> List[AvailabilityZone]:
        return [zone for zone in self.availability_zones if zone.healthy]


def demonstrate_regions_and_zones() -> None:
    section("7. REGIONS AND AVAILABILITY ZONES")

    dc_a = DataCenter(
        name="DC-A1",
        region="region-india",
        power_capacity_mw=20,
        cooling_capacity_mw=20,
        server_count=4000,
    )
    dc_b = DataCenter(
        name="DC-B1",
        region="region-india",
        power_capacity_mw=20,
        cooling_capacity_mw=20,
        server_count=4000,
    )
    dc_c = DataCenter(
        name="DC-C1",
        region="region-india",
        power_capacity_mw=20,
        cooling_capacity_mw=20,
        server_count=4000,
    )

    zones = [
        AvailabilityZone("az-1", [dc_a]),
        AvailabilityZone("az-2", [dc_b]),
        AvailabilityZone("az-3", [dc_c]),
    ]

    region = Region(
        name="region-india",
        geography="India",
        availability_zones=zones,
    )

    print("Region:", region.name)
    print("Geography:", region.geography)
    print("Total server capacity:", region.total_servers())

    for zone in region.availability_zones:
        print(
            f"{zone.name}: healthy={zone.healthy}, "
            f"server capacity={zone.server_capacity}"
        )

    subsection("Availability-zone failure")

    region.availability_zones[1].healthy = False

    print("Failed:", region.availability_zones[1].name)
    print("Healthy zones:", [z.name for z in region.healthy_zones()])
    print(
        "Remaining capacity:",
        sum(z.server_capacity for z in region.healthy_zones()),
    )

    print(
        "\nDesign implication: distributing workloads across independent "
        "availability zones can prevent a localized infrastructure failure "
        "from becoming a complete application outage."
    )


# =============================================================================
# 8. LOAD BALANCING AND HIGH AVAILABILITY
# =============================================================================

@dataclass
class Backend:
    name: str
    zone: str
    healthy: bool = True
    request_count: int = 0


class RoundRobinLoadBalancer:
    """Simple health-aware round-robin load balancer."""

    def __init__(self, backends: List[Backend]) -> None:
        self.backends = backends
        self.position = 0

    def choose_backend(self) -> Optional[Backend]:
        healthy = [backend for backend in self.backends if backend.healthy]

        if not healthy:
            return None

        selected = healthy[self.position % len(healthy)]
        self.position += 1
        selected.request_count += 1
        return selected


def demonstrate_load_balancing() -> None:
    section("8. LOAD BALANCING AND HIGH AVAILABILITY")

    backends = [
        Backend("web-01", "az-1"),
        Backend("web-02", "az-2"),
        Backend("web-03", "az-3"),
    ]

    load_balancer = RoundRobinLoadBalancer(backends)

    print("Initial request distribution:")
    for request_number in range(1, 10):
        backend = load_balancer.choose_backend()
        print(
            f"Request {request_number:2} -> "
            f"{backend.name if backend else 'NO HEALTHY BACKEND'}"
        )

    print("\nBackend counters:")
    for backend in backends:
        print(backend.name, backend.request_count)

    subsection("Failure of one zone")

    backends[1].healthy = False

    for request_number in range(10, 17):
        backend = load_balancer.choose_backend()
        print(
            f"Request {request_number:2} -> "
            f"{backend.name if backend else 'NO HEALTHY BACKEND'}"
        )

    print(
        "\nA load balancer can improve availability, but it itself must be "
        "highly available. A single load-balancer instance can become a "
        "single point of failure."
    )


# =============================================================================
# 9. SCALING
# =============================================================================

@dataclass
class ScalingPolicy:
    minimum_instances: int
    maximum_instances: int
    target_cpu_percent: float

    def desired_instances(
        self,
        current_instances: int,
        average_cpu_percent: float,
    ) -> int:
        if current_instances <= 0:
            current_instances = 1

        if average_cpu_percent > self.target_cpu_percent:
            multiplier = average_cpu_percent / self.target_cpu_percent
            desired = ceil(current_instances * multiplier)
        elif average_cpu_percent < self.target_cpu_percent * 0.5:
            desired = max(
                self.minimum_instances,
                current_instances - 1,
            )
        else:
            desired = current_instances

        return max(
            self.minimum_instances,
            min(self.maximum_instances, desired),
        )


def demonstrate_scaling() -> None:
    section("9. SCALING")

    subsection("Vertical scaling")

    print(
        "Vertical scaling increases the capacity of an existing resource, "
        "such as moving from 4 CPU cores to 8 CPU cores."
    )
    print("Advantage: simple application topology.")
    print("Limitation: hardware/resource limits remain.")

    subsection("Horizontal scaling")

    print(
        "Horizontal scaling adds more instances, such as increasing "
        "from 3 application servers to 10."
    )
    print("Advantage: can provide large capacity and redundancy.")
    print("Requirement: applications often need to tolerate multiple instances.")

    subsection("Auto-scaling policy")

    policy = ScalingPolicy(
        minimum_instances=2,
        maximum_instances=20,
        target_cpu_percent=60,
    )

    for cpu in [30, 50, 60, 80, 120, 200]:
        desired = policy.desired_instances(
            current_instances=4,
            average_cpu_percent=cpu,
        )
        print(f"Average CPU={cpu:3}% -> desired instances={desired}")


# =============================================================================
# 10. CLOUD NETWORK ARCHITECTURE
# =============================================================================

@dataclass
class Subnet:
    name: str
    cidr: IPv4Network
    zone: str
    public: bool

    def contains(self, address: str) -> bool:
        return IPv4Address(address) in self.cidr


@dataclass
class VirtualNetwork:
    name: str
    cidr: IPv4Network
    subnets: List[Subnet] = field(default_factory=list)

    def add_subnet(self, subnet: Subnet) -> None:
        if not subnet.cidr.subnet_of(self.cidr):
            raise ValueError(
                f"{subnet.cidr} is outside virtual network {self.cidr}."
            )

        for existing in self.subnets:
            if subnet.cidr.overlaps(existing.cidr):
                raise ValueError(
                    f"Subnet {subnet.cidr} overlaps {existing.cidr}."
                )

        self.subnets.append(subnet)

    def locate(self, address: str) -> Optional[Subnet]:
        for subnet in self.subnets:
            if subnet.contains(address):
                return subnet
        return None


def demonstrate_cloud_network() -> None:
    section("10. VIRTUAL CLOUD NETWORK DESIGN")

    vpc = VirtualNetwork(
        name="production-network",
        cidr=IPv4Network("10.0.0.0/16"),
    )

    subnets = [
        Subnet(
            name="public-az1",
            cidr=IPv4Network("10.0.1.0/24"),
            zone="az-1",
            public=True,
        ),
        Subnet(
            name="public-az2",
            cidr=IPv4Network("10.0.2.0/24"),
            zone="az-2",
            public=True,
        ),
        Subnet(
            name="private-app-az1",
            cidr=IPv4Network("10.0.11.0/24"),
            zone="az-1",
            public=False,
        ),
        Subnet(
            name="private-app-az2",
            cidr=IPv4Network("10.0.12.0/24"),
            zone="az-2",
            public=False,
        ),
        Subnet(
            name="private-db-az1",
            cidr=IPv4Network("10.0.21.0/24"),
            zone="az-1",
            public=False,
        ),
        Subnet(
            name="private-db-az2",
            cidr=IPv4Network("10.0.22.0/24"),
            zone="az-2",
            public=False,
        ),
    ]

    for subnet in subnets:
        vpc.add_subnet(subnet)

    print("Virtual network:", vpc.name)
    print("CIDR:", vpc.cidr)

    for subnet in vpc.subnets:
        print(
            f"{subnet.name:18} | {subnet.cidr} | "
            f"{subnet.zone} | "
            f"{'PUBLIC' if subnet.public else 'PRIVATE'}"
        )

    subsection("Address lookup")

    for address in [
        "10.0.1.50",
        "10.0.11.20",
        "10.0.21.15",
        "10.1.1.1",
    ]:
        subnet = vpc.locate(address)
        print(
            f"{address:15} -> "
            f"{subnet.name if subnet else 'outside configured subnets'}"
        )


# =============================================================================
# 11. DNS AND SERVICE DISCOVERY
# =============================================================================

class DNSResolver:
    """Minimal DNS A-record simulation."""

    def __init__(self) -> None:
        self.records: Dict[str, IPv4Address] = {}

    def add_record(self, hostname: str, address: str) -> None:
        self.records[hostname.lower()] = IPv4Address(address)

    def resolve(self, hostname: str) -> Optional[IPv4Address]:
        return self.records.get(hostname.lower())


def demonstrate_dns() -> None:
    section("11. DNS AND SERVICE DISCOVERY")

    resolver = DNSResolver()
    resolver.add_record("api.example.internal", "10.0.11.10")
    resolver.add_record("database.example.internal", "10.0.21.10")

    for hostname in [
        "api.example.internal",
        "database.example.internal",
        "missing.example.internal",
    ]:
        print(f"{hostname:30} -> {resolver.resolve(hostname)}")

    print(
        "\nDNS is a naming system, not merely a web-address mechanism. "
        "Infrastructure frequently uses DNS for service discovery, endpoint "
        "abstraction, traffic steering, and failover."
    )


# =============================================================================
# 12. RELIABILITY, REDUNDANCY, AND FAILURE DOMAINS
# =============================================================================

@dataclass
class ServiceInstance:
    name: str
    zone: str
    healthy: bool = True


def service_available(instances: List[ServiceInstance]) -> bool:
    return any(instance.healthy for instance in instances)


def demonstrate_reliability() -> None:
    section("12. RELIABILITY, REDUNDANCY, AND FAILURE DOMAINS")

    subsection("Redundancy")

    instances = [
        ServiceInstance("service-1", "az-1"),
        ServiceInstance("service-2", "az-2"),
        ServiceInstance("service-3", "az-3"),
    ]

    print("Service available:", service_available(instances))

    instances[0].healthy = False
    print("After az-1 instance failure:", service_available(instances))

    instances[1].healthy = False
    print("After az-2 instance failure:", service_available(instances))

    instances[2].healthy = False
    print("After all instances fail:", service_available(instances))

    subsection("Availability intuition")

    print(
        "For independent components, the probability that all redundant "
        "components fail can be much smaller than the probability of one "
        "component failing."
    )

    component_failure_probability = 0.01
    independent_components = 3

    all_fail = component_failure_probability ** independent_components
    availability = 1 - all_fail

    print(
        f"Assuming independent 1% failure probability for each of "
        f"{independent_components} components:"
    )
    print(f"Approximate probability all fail: {all_fail:.8f}")
    print(f"Approximate availability: {availability:.8%}")

    print(
        "\nThis calculation is illustrative. Real systems have correlated "
        "failures, shared dependencies, maintenance events, network failures, "
        "software bugs, and common-mode failure."
    )

    subsection("Single point of failure")

    examples = [
        "One physical host",
        "One database instance",
        "One network path",
        "One power feed",
        "One load balancer without redundancy",
        "One DNS dependency",
        "One availability zone",
    ]

    for example in examples:
        print("Potential SPOF:", example)


# =============================================================================
# 13. LATENCY, BANDWIDTH, AND PERFORMANCE
# =============================================================================

def calculate_transfer_time(
    data_size_gigabytes: float,
    bandwidth_gigabits_per_second: float,
) -> float:
    """Approximate transfer time in seconds, ignoring protocol overhead."""
    if data_size_gigabytes < 0:
        raise ValueError("Data size cannot be negative.")
    if bandwidth_gigabits_per_second <= 0:
        raise ValueError("Bandwidth must be positive.")

    gigabits = data_size_gigabytes * 8
    return gigabits / bandwidth_gigabits_per_second


def demonstrate_performance() -> None:
    section("13. PERFORMANCE CONSIDERATIONS")

    subsection("Latency vs bandwidth")

    print(
        "Latency is the time required for an operation or network round trip."
    )
    print(
        "Bandwidth is the amount of data that can be transferred per unit time."
    )
    print(
        "A connection can have high bandwidth but still have high latency."
    )

    subsection("Transfer calculation")

    for size, bandwidth in [
        (1, 1),
        (10, 1),
        (10, 10),
        (100, 100),
    ]:
        seconds = calculate_transfer_time(size, bandwidth)
        print(
            f"{size:6.1f} GB over {bandwidth:6.1f} Gbps "
            f"-> {seconds:.2f} seconds"
        )

    subsection("Performance dimensions")

    dimensions = [
        "CPU utilization",
        "Memory utilization",
        "Disk IOPS",
        "Disk throughput",
        "Network bandwidth",
        "Network latency",
        "Packet loss",
        "Connection limits",
        "Load-balancer capacity",
        "Database connection pools",
        "Queue depth",
        "Application response time",
    ]

    for dimension in dimensions:
        print("-", dimension)


# =============================================================================
# 14. CAPACITY PLANNING
# =============================================================================

@dataclass
class WorkloadRequirement:
    name: str
    cpu_per_instance: float
    memory_per_instance_gb: float
    instances: int

    @property
    def total_cpu(self) -> float:
        return self.cpu_per_instance * self.instances

    @property
    def total_memory(self) -> float:
        return self.memory_per_instance_gb * self.instances


def capacity_plan(
    workloads: List[WorkloadRequirement],
    host_cpu: float,
    host_memory_gb: float,
    reserve_percent: float = 20.0,
) -> Tuple[int, float, float]:
    """
    Estimate host count.

    CPU and memory are evaluated independently. The larger requirement
    determines the minimum host count. A reserve is then applied.
    """
    if host_cpu <= 0 or host_memory_gb <= 0:
        raise ValueError("Host capacity must be positive.")

    if not 0 <= reserve_percent < 100:
        raise ValueError("Reserve must be between 0 and 100.")

    total_cpu = sum(w.total_cpu for w in workloads)
    total_memory = sum(w.total_memory for w in workloads)

    cpu_hosts = ceil(total_cpu / host_cpu)
    memory_hosts = ceil(total_memory / host_memory_gb)

    minimum_hosts = max(cpu_hosts, memory_hosts)

    hosts_with_reserve = ceil(
        minimum_hosts / (1 - reserve_percent / 100)
    )

    return hosts_with_reserve, total_cpu, total_memory


def demonstrate_capacity_planning() -> None:
    section("14. CAPACITY PLANNING")

    workloads = [
        WorkloadRequirement("web", 2, 4, 10),
        WorkloadRequirement("api", 4, 8, 6),
        WorkloadRequirement("worker", 2, 8, 4),
    ]

    hosts, total_cpu, total_memory = capacity_plan(
        workloads,
        host_cpu=32,
        host_memory_gb=128,
        reserve_percent=20,
    )

    print("Total CPU requirement:", total_cpu)
    print("Total memory requirement:", total_memory)
    print("Estimated hosts with 20% reserve:", hosts)

    print(
        "\nCapacity planning must account for peak demand, failure capacity, "
        "growth, maintenance, noisy neighbors, and workload placement."
    )


# =============================================================================
# 15. COST MODELING
# =============================================================================

@dataclass
class ResourceCost:
    name: str
    monthly_cost: float

    def annual_cost(self) -> float:
        return self.monthly_cost * 12


def demonstrate_cost_modeling() -> None:
    section("15. CLOUD INFRASTRUCTURE COST CONSIDERATIONS")

    resources = [
        ResourceCost("Compute", 500.00),
        ResourceCost("Block storage", 150.00),
        ResourceCost("Object storage", 80.00),
        ResourceCost("Database", 600.00),
        ResourceCost("Load balancing", 75.00),
        ResourceCost("Network transfer", 200.00),
    ]

    monthly_total = sum(resource.monthly_cost for resource in resources)

    for resource in resources:
        print(
            f"{resource.name:20} "
            f"${resource.monthly_cost:8.2f}/month "
            f"${resource.annual_cost():9.2f}/year"
        )

    print("-" * 60)
    print(f"{'Total':20} ${monthly_total:8.2f}/month")
    print(f"{'Annual':20} ${monthly_total * 12:8.2f}/year")

    subsection("Cost drivers")

    drivers = [
        "Compute hours",
        "Memory allocation",
        "Storage capacity",
        "Storage operations",
        "Database capacity",
        "Network egress",
        "Load balancer usage",
        "Snapshots and backups",
        "Monitoring and logging",
        "Reserved capacity or committed usage",
    ]

    for driver in drivers:
        print("-", driver)

    print(
        "\nA technically efficient architecture is not automatically the "
        "least expensive architecture. Cost must be evaluated against "
        "performance, availability, durability, operational complexity, "
        "and business requirements."
    )


# =============================================================================
# 16. SECURITY
# =============================================================================

@dataclass
class SecurityControl:
    name: str
    objective: str


def demonstrate_security() -> None:
    section("16. CLOUD INFRASTRUCTURE SECURITY")

    controls = [
        SecurityControl(
            "Identity and access management",
            "Control who can access infrastructure and what they can do.",
        ),
        SecurityControl(
            "Network segmentation",
            "Separate workloads to reduce unnecessary connectivity.",
        ),
        SecurityControl(
            "Firewalls",
            "Restrict network traffic according to explicit rules.",
        ),
        SecurityControl(
            "Encryption at rest",
            "Protect stored data from unauthorized access.",
        ),
        SecurityControl(
            "Encryption in transit",
            "Protect network communication from interception.",
        ),
        SecurityControl(
            "Secrets management",
            "Protect credentials, tokens, and cryptographic secrets.",
        ),
        SecurityControl(
            "Patch management",
            "Reduce exposure to known software vulnerabilities.",
        ),
        SecurityControl(
            "Logging",
            "Create evidence for troubleshooting, detection, and auditing.",
        ),
        SecurityControl(
            "Monitoring",
            "Detect operational and security anomalies.",
        ),
        SecurityControl(
            "Backup and recovery",
            "Protect against data loss and destructive incidents.",
        ),
    ]

    for control in controls:
        print(f"{control.name:25} -> {control.objective}")

    subsection("Defense-in-depth example")

    print(
        "Internet -> Edge firewall -> Load balancer -> Application subnet "
        "-> Database subnet -> Encrypted storage"
    )

    print(
        "\nSecurity principle: do not depend on a single control. "
        "Layer identity, network, host, application, data, monitoring, "
        "and recovery controls."
    )


# =============================================================================
# 17. BACKUP, SNAPSHOT, RPO, AND RTO
# =============================================================================

@dataclass
class RecoveryPlan:
    recovery_point_objective_minutes: int
    recovery_time_objective_minutes: int
    backup_interval_minutes: int

    def worst_case_data_loss_minutes(self) -> int:
        return self.backup_interval_minutes

    def meets_rpo(self) -> bool:
        return self.backup_interval_minutes <= self.recovery_point_objective_minutes


def demonstrate_recovery() -> None:
    section("17. BACKUP AND DISASTER RECOVERY")

    print(
        "RPO (Recovery Point Objective): maximum acceptable amount of "
        "data loss measured in time."
    )
    print(
        "RTO (Recovery Time Objective): maximum acceptable time to restore "
        "service after an incident."
    )

    plan = RecoveryPlan(
        recovery_point_objective_minutes=15,
        recovery_time_objective_minutes=60,
        backup_interval_minutes=10,
    )

    print("Configured RPO:", plan.recovery_point_objective_minutes, "minutes")
    print("Configured RTO:", plan.recovery_time_objective_minutes, "minutes")
    print("Backup interval:", plan.backup_interval_minutes, "minutes")
    print("Meets RPO:", plan.meets_rpo())
    print(
        "Illustrative worst-case backup-window data loss:",
        plan.worst_case_data_loss_minutes(),
        "minutes",
    )

    print(
        "\nA backup is not equivalent to a complete disaster-recovery strategy. "
        "Recovery also requires usable copies, appropriate credentials, "
        "network access, compatible infrastructure, tested procedures, "
        "and sufficient recovery capacity."
    )


# =============================================================================
# 18. FAILURE SIMULATION
# =============================================================================

class InfrastructureSimulator:
    """Simple deterministic infrastructure failure simulator."""

    def __init__(self, seed: int = 42) -> None:
        self.random = Random(seed)

    def run(
        self,
        zones: List[AvailabilityZone],
        failure_probability: float,
        rounds: int,
    ) -> Dict[str, int]:
        if not 0 <= failure_probability <= 1:
            raise ValueError("Failure probability must be between 0 and 1.")

        results = {
            "healthy_rounds": 0,
            "degraded_rounds": 0,
            "outage_rounds": 0,
        }

        for _ in range(rounds):
            zone_states = []

            for zone in zones:
                failed = self.random.random() < failure_probability
                zone_states.append(not failed)

            healthy_count = sum(zone_states)

            if healthy_count == len(zones):
                results["healthy_rounds"] += 1
            elif healthy_count > 0:
                results["degraded_rounds"] += 1
            else:
                results["outage_rounds"] += 1

        return results


def demonstrate_failure_simulation() -> None:
    section("18. FAILURE SIMULATION")

    zones = [
        AvailabilityZone("az-1", []),
        AvailabilityZone("az-2", []),
        AvailabilityZone("az-3", []),
    ]

    simulator = InfrastructureSimulator(seed=7)

    results = simulator.run(
        zones=zones,
        failure_probability=0.02,
        rounds=10000,
    )

    print("Simulation rounds:", sum(results.values()))

    for category, count in results.items():
        print(f"{category:20}: {count}")

    print(
        "\nSimulation demonstrates why redundancy changes failure behavior. "
        "Real reliability analysis should model correlated failures and "
        "dependencies rather than assuming perfect independence."
    )


# =============================================================================
# 19. CONTAINERIZATION VS VIRTUAL MACHINES
# =============================================================================

@dataclass
class Container:
    name: str
    image: str
    cpu_limit: float
    memory_limit_gb: float


def demonstrate_containers() -> None:
    section("19. VIRTUAL MACHINES VS CONTAINERS")

    print(
        "A virtual machine virtualizes a complete machine environment, "
        "including a guest operating system."
    )
    print(
        "A container generally shares the host operating-system kernel while "
        "isolating processes, filesystems, networking, and resource usage."
    )

    comparison = [
        ("Isolation", "VM: strong machine abstraction", "Container: process-level abstraction"),
        ("Startup", "VM: usually slower", "Container: usually faster"),
        ("Image size", "VM: often larger", "Container: often smaller"),
        ("Kernel", "VM: guest kernel", "Container: shared host kernel"),
        ("Density", "VM: lower than containers in many cases", "Container: often higher"),
        ("Security", "VM: strong isolation boundary", "Container: isolation depends on runtime/kernel"),
    ]

    for category, vm, container in comparison:
        print(f"{category:12} | {vm:40} | {container}")

    subsection("Container resource limits")

    container = Container(
        name="api-container",
        image="example-api:v1",
        cpu_limit=1.5,
        memory_limit_gb=2,
    )

    print(container)


# =============================================================================
# 20. STORAGE DURABILITY AND AVAILABILITY
# =============================================================================

def demonstrate_storage_properties() -> None:
    section("20. STORAGE DURABILITY VS AVAILABILITY")

    print(
        "Durability describes the likelihood that stored data remains intact."
    )
    print(
        "Availability describes whether the storage service is accessible "
        "when needed."
    )

    scenarios = [
        (
            "Highly durable, temporarily unavailable",
            "Data survives but access may be interrupted.",
        ),
        (
            "Highly available, weak durability",
            "Data may be accessible frequently but can still be lost.",
        ),
        (
            "High durability and high availability",
            "Strong target for critical production data.",
        ),
    ]

    for name, explanation in scenarios:
        print(f"{name:35} -> {explanation}")

    print(
        "\nReplication can improve both availability and durability, "
        "but replication alone is not protection against every failure. "
        "Accidental deletion or corruption may be replicated too."
    )


# =============================================================================
# 21. MULTI-REGION ARCHITECTURE
# =============================================================================

@dataclass
class RegionService:
    region: str
    healthy: bool
    traffic_weight: int


def route_across_regions(
    services: List[RegionService],
    request_count: int,
) -> Dict[str, int]:
    healthy = [service for service in services if service.healthy]

    if not healthy:
        return {}

    total_weight = sum(service.traffic_weight for service in healthy)

    if total_weight <= 0:
        return {}

    distribution: Dict[str, int] = {}

    remaining = request_count

    for index, service in enumerate(healthy):
        if index == len(healthy) - 1:
            allocated = remaining
        else:
            allocated = round(
                request_count * service.traffic_weight / total_weight
            )
            remaining -= allocated

        distribution[service.region] = allocated

    return distribution


def demonstrate_multi_region() -> None:
    section("21. MULTI-REGION ARCHITECTURE")

    services = [
        RegionService("region-a", True, 60),
        RegionService("region-b", True, 40),
    ]

    print("Traffic distribution:", route_across_regions(services, 1000))

    services[0].healthy = False

    print(
        "After region-a failure:",
        route_across_regions(services, 1000),
    )

    print(
        "\nMulti-region design can improve geographic resilience and "
        "reduce latency for globally distributed users."
    )

    print(
        "Trade-offs include replication complexity, data consistency, "
        "higher cost, cross-region network latency, operational complexity, "
        "and more complicated disaster recovery."
    )


# =============================================================================
# 22. CONSISTENCY AND STATEFUL INFRASTRUCTURE
# =============================================================================

def demonstrate_stateful_design() -> None:
    section("22. STATEFUL VS STATELESS ARCHITECTURE")

    print(
        "A stateless application instance does not require local instance "
        "memory to preserve user state between requests."
    )
    print(
        "A stateful component maintains information that affects future "
        "operations, such as database records or session state."
    )

    stateless_pattern = [
        "Load balancer",
        "Application instances",
        "Shared database",
        "Shared object storage",
    ]

    stateful_pattern = [
        "Database",
        "Persistent block storage",
        "Message queue with durable state",
        "Stateful cache",
    ]

    print("\nCommonly stateless layers:")
    for item in stateless_pattern:
        print("-", item)

    print("\nCommonly stateful layers:")
    for item in stateful_pattern:
        print("-", item)

    print(
        "\nSeparating compute from persistent state often makes horizontal "
        "scaling easier, though the shared stateful layer still requires "
        "careful availability, replication, backup, and consistency design."
    )


# =============================================================================
# 23. OBSERVABILITY
# =============================================================================

@dataclass
class Metric:
    name: str
    value: float
    unit: str


def demonstrate_observability() -> None:
    section("23. INFRASTRUCTURE OBSERVABILITY")

    metrics = [
        Metric("CPU utilization", 67.5, "%"),
        Metric("Memory utilization", 71.0, "%"),
        Metric("Disk utilization", 63.2, "%"),
        Metric("Network throughput", 4.5, "Gbps"),
        Metric("Request latency", 120, "ms"),
        Metric("Error rate", 0.4, "%"),
    ]

    for metric in metrics:
        print(
            f"{metric.name:25} {metric.value:8.2f} {metric.unit}"
        )

    print(
        "\nThree useful observability categories are metrics, logs, and traces."
    )
    print(
        "Metrics describe numerical system behavior. Logs provide event "
        "records. Traces follow requests through distributed components."
    )


# =============================================================================
# 24. INFRASTRUCTURE DESIGN EXERCISE
# =============================================================================

@dataclass
class ArchitectureComponent:
    name: str
    role: str
    zone: str
    redundant: bool


def validate_architecture(
    components: List[ArchitectureComponent],
) -> List[str]:
    """
    Perform basic architecture checks.

    This is deliberately educational and is not a production architecture
    validation engine.
    """
    findings: List[str] = []

    by_role: Dict[str, List[ArchitectureComponent]] = {}

    for component in components:
        by_role.setdefault(component.role, []).append(component)

    for role, role_components in by_role.items():
        zones = {component.zone for component in role_components}

        if len(role_components) == 1:
            findings.append(
                f"Potential single point of failure: {role}"
            )

        if len(zones) == 1 and len(role_components) > 1:
            findings.append(
                f"{role} instances are concentrated in one zone."
            )

        if any(not component.redundant for component in role_components):
            findings.append(
                f"{role} contains at least one non-redundant component."
            )

    return findings


def demonstrate_architecture_validation() -> None:
    section("24. ARCHITECTURE DESIGN AND VALIDATION")

    architecture = [
        ArchitectureComponent(
            "lb-1", "load-balancer", "az-1", True
        ),
        ArchitectureComponent(
            "lb-2", "load-balancer", "az-2", True
        ),
        ArchitectureComponent(
            "app-1", "application", "az-1", True
        ),
        ArchitectureComponent(
            "app-2", "application", "az-2", True
        ),
        ArchitectureComponent(
            "db-1", "database", "az-1", False
        ),
    ]

    print("Architecture components:")
    for component in architecture:
        print(
            f"{component.name:8} | "
            f"{component.role:15} | "
            f"{component.zone:5} | "
            f"redundant={component.redundant}"
        )

    print("\nValidation findings:")
    findings = validate_architecture(architecture)

    for finding in findings:
        print("-", finding)

    print(
        "\nThe database is a critical stateful dependency. A production "
        "architecture would need an explicit strategy for database "
        "replication, failover, backup, recovery, and consistency."
    )


# =============================================================================
# 25. INFRASTRUCTURE AS CODE CONCEPT
# =============================================================================

@dataclass
class InfrastructureResource:
    resource_type: str
    name: str
    properties: Dict[str, str]


class InfrastructureState:
    """Tiny state model illustrating declarative infrastructure."""

    def __init__(self) -> None:
        self.resources: Dict[str, InfrastructureResource] = {}

    def apply(self, desired: List[InfrastructureResource]) -> List[str]:
        actions: List[str] = []

        desired_keys = {
            f"{resource.resource_type}:{resource.name}"
            for resource in desired
        }

        current_keys = set(self.resources)

        for resource in desired:
            key = f"{resource.resource_type}:{resource.name}"

            if key not in self.resources:
                self.resources[key] = resource
                actions.append(f"CREATE {key}")
            elif self.resources[key].properties != resource.properties:
                self.resources[key] = resource
                actions.append(f"UPDATE {key}")
            else:
                actions.append(f"NO-OP {key}")

        for key in current_keys - desired_keys:
            del self.resources[key]
            actions.append(f"DELETE {key}")

        return actions


def demonstrate_infrastructure_as_code() -> None:
    section("25. INFRASTRUCTURE AS CODE")

    state = InfrastructureState()

    desired_v1 = [
        InfrastructureResource(
            resource_type="network",
            name="production",
            properties={"cidr": "10.0.0.0/16"},
        ),
        InfrastructureResource(
            resource_type="server",
            name="web-01",
            properties={"cpu": "4", "memory": "16"},
        ),
    ]

    print("First apply:")
    for action in state.apply(desired_v1):
        print("-", action)

    desired_v2 = [
        InfrastructureResource(
            resource_type="network",
            name="production",
            properties={"cidr": "10.0.0.0/16"},
        ),
        InfrastructureResource(
            resource_type="server",
            name="web-01",
            properties={"cpu": "8", "memory": "32"},
        ),
        InfrastructureResource(
            resource_type="server",
            name="web-02",
            properties={"cpu": "4", "memory": "16"},
        ),
    ]

    print("\nSecond apply:")
    for action in state.apply(desired_v2):
        print("-", action)

    print(
        "\nDeclarative infrastructure describes desired state. "
        "An orchestration system determines the changes required to "
        "move actual infrastructure toward that state."
    )


# =============================================================================
# 26. COMMON MISTAKES
# =============================================================================

def demonstrate_common_mistakes() -> None:
    section("26. COMMON INFRASTRUCTURE MISTAKES")

    mistakes = [
        (
            "Using one server for a critical production service",
            "Creates a single point of failure.",
        ),
        (
            "Placing all replicas in one availability zone",
            "A zone-level failure can remove every replica.",
        ),
        (
            "Treating backups as automatically reliable",
            "Backups must be tested for restoration and integrity.",
        ),
        (
            "Ignoring network egress",
            "Large data transfers can become a significant cost driver.",
        ),
        (
            "Overprovisioning everything",
            "Improves headroom but can create unnecessary cost.",
        ),
        (
            "Underprovisioning everything",
            "Can cause saturation, latency, and availability problems.",
        ),
        (
            "Assuming redundancy removes all failure risk",
            "Shared dependencies and correlated failures remain possible.",
        ),
        (
            "Putting databases directly on public networks",
            "Expands the attack surface unnecessarily.",
        ),
        (
            "Hard-coding infrastructure addresses",
            "Makes scaling and failure recovery more difficult.",
        ),
        (
            "Skipping monitoring",
            "Makes failures harder to detect and diagnose.",
        ),
        (
            "Confusing durability with availability",
            "Data can be durable while temporarily inaccessible.",
        ),
        (
            "Assuming virtualization means unlimited capacity",
            "Physical resources remain finite.",
        ),
    ]

    for mistake, consequence in mistakes:
        print(f"\nMistake:     {mistake}")
        print(f"Consequence: {consequence}")


# =============================================================================
# 27. ADVANCED DESIGN PRINCIPLES
# =============================================================================

def demonstrate_advanced_principles() -> None:
    section("27. ADVANCED CLOUD INFRASTRUCTURE PRINCIPLES")

    principles = [
        (
            "Blast radius",
            "Limit how much infrastructure can be affected by one failure."
        ),
        (
            "Fault isolation",
            "Separate resources so failures do not propagate unnecessarily."
        ),
        (
            "Defense in depth",
            "Use multiple independent security controls."
        ),
        (
            "Least privilege",
            "Give identities only the permissions they require."
        ),
        (
            "Immutable infrastructure",
            "Replace infrastructure rather than manually modifying it."
        ),
        (
            "Stateless compute",
            "Keep persistent state outside replaceable compute instances."
        ),
        (
            "Elasticity",
            "Adjust resource capacity according to workload demand."
        ),
        (
            "Idempotency",
            "Repeated infrastructure operations should converge safely."
        ),
        (
            "Graceful degradation",
            "Continue providing partial service when dependencies fail."
        ),
        (
            "Backpressure",
            "Prevent overloaded components from being overwhelmed by upstream traffic."
        ),
        (
            "Cell-based architecture",
            "Partition workloads into relatively independent cells to limit failures."
        ),
        (
            "Control plane vs data plane",
            "Separate management operations from workload traffic and execution."
        ),
    ]

    for principle, definition in principles:
        print(f"{principle:28} -> {definition}")


# =============================================================================
# 28. PRODUCTION CHECKLIST
# =============================================================================

def production_checklist() -> None:
    section("28. PRODUCTION INFRASTRUCTURE CHECKLIST")

    checklist = [
        "Compute capacity is sufficient for normal and peak workloads.",
        "Critical workloads have appropriate redundancy.",
        "Failure domains are intentionally separated.",
        "Networking is segmented according to trust and workload boundaries.",
        "Ingress and egress paths are explicitly controlled.",
        "Storage has appropriate performance and durability characteristics.",
        "Critical data is backed up.",
        "Restoration procedures have been tested.",
        "RPO and RTO requirements are defined.",
        "Monitoring and alerting cover important infrastructure signals.",
        "Logs are retained according to operational and security requirements.",
        "Secrets are not embedded directly in application source code.",
        "Access follows least-privilege principles.",
        "Encryption requirements are defined.",
        "Capacity growth is monitored.",
        "Cloud costs are monitored and attributed.",
        "Infrastructure changes are reproducible.",
        "Failure scenarios have been considered.",
        "Disaster-recovery dependencies are documented.",
        "Operational ownership and escalation paths are clear.",
    ]

    for index, item in enumerate(checklist, start=1):
        print(f"{index:2}. [ ] {item}")


# =============================================================================
# 29. KNOWLEDGE TESTS
# =============================================================================

def run_knowledge_checks() -> None:
    section("29. KNOWLEDGE CHECKS")

    questions = [
        (
            "1. What does a hypervisor manage?",
            "Virtual machines and their virtualized hardware resources."
        ),
        (
            "2. What is the primary difference between block and object storage?",
            "Block storage exposes volumes, while object storage manages objects with metadata and identifiers."
        ),
        (
            "3. Why use multiple availability zones?",
            "To reduce the impact of localized infrastructure failures."
        ),
        (
            "4. What is horizontal scaling?",
            "Adding more instances rather than increasing the size of one instance."
        ),
        (
            "5. What does RPO measure?",
            "The acceptable amount of data loss measured in time."
        ),
        (
            "6. What does RTO measure?",
            "The acceptable time to restore service."
        ),
        (
            "7. What is a single point of failure?",
            "A component whose failure can cause the service to fail because no sufficient redundancy exists."
        ),
        (
            "8. What is longest-prefix matching?",
            "Routing selects the most specific matching network prefix."
        ),
        (
            "9. What is durability?",
            "The likelihood that stored data remains intact over time."
        ),
        (
            "10. Why is monitoring important?",
            "It provides visibility into system health, performance, failures, and anomalies."
        ),
    ]

    for question, answer in questions:
        print(f"\n{question}")
        print(f"Answer: {answer}")


# =============================================================================
# 30. INTEGRATED REFERENCE ARCHITECTURE
# =============================================================================

def demonstrate_reference_architecture() -> None:
    section("30. INTEGRATED CLOUD REFERENCE ARCHITECTURE")

    architecture_layers = [
        (
            "Users",
            "Clients access the application through public endpoints."
        ),
        (
            "DNS",
            "Maps application names to traffic entry points."
        ),
        (
            "Edge / Load Balancer",
            "Receives traffic and distributes it across healthy application instances."
        ),
        (
            "Public Subnets",
            "Contain controlled internet-facing components."
        ),
        (
            "Private Application Subnets",
            "Contain application servers that do not need direct public exposure."
        ),
        (
            "Private Data Subnets",
            "Contain databases and other sensitive stateful systems."
        ),
        (
            "Persistent Storage",
            "Stores durable application data, backups, and objects."
        ),
        (
            "Monitoring",
            "Collects metrics, logs, traces, and health signals."
        ),
        (
            "Identity and Security",
            "Controls access and protects infrastructure and data."
        ),
        (
            "Multiple Availability Zones",
            "Distribute critical components across independent failure domains."
        ),
        (
            "Multiple Regions",
            "Can provide geographic resilience when business requirements justify it."
        ),
    ]

    for layer, role in architecture_layers:
        print(f"{layer:28} -> {role}")

    print(
        "\nReference flow:\n"
        "User -> DNS -> Load Balancer -> Application -> Database/Object Storage\n"
        "                 |                    |\n"
        "                 +-> Monitoring <------+"
    )


# =============================================================================
# 31. EDGE CASES AND VALIDATION
# =============================================================================

def demonstrate_edge_cases() -> None:
    section("31. EDGE CASES AND VALIDATION")

    subsection("Storage overflow")

    volume = StorageVolume(
        name="small-volume",
        capacity_gb=10,
        storage_type=StorageType.BLOCK,
    )

    print("Write 10 GB:", volume.write(10))
    print("Write 1 GB beyond capacity:", volume.write(1))

    subsection("Invalid bandwidth")

    try:
        calculate_transfer_time(10, 0)
    except ValueError as exc:
        print("Handled error:", exc)

    subsection("Invalid subnet")

    network = VirtualNetwork(
        name="test-network",
        cidr=IPv4Network("10.0.0.0/16"),
    )

    try:
        network.add_subnet(
            Subnet(
                name="outside",
                cidr=IPv4Network("192.168.1.0/24"),
                zone="az-1",
                public=False,
            )
        )
    except ValueError as exc:
        print("Handled error:", exc)

    subsection("Overlapping subnet")

    network.add_subnet(
        Subnet(
            name="subnet-a",
            cidr=IPv4Network("10.0.1.0/24"),
            zone="az-1",
            public=False,
        )
    )

    try:
        network.add_subnet(
            Subnet(
                name="subnet-overlap",
                cidr=IPv4Network("10.0.1.128/25"),
                zone="az-1",
                public=False,
            )
        )
    except ValueError as exc:
        print("Handled error:", exc)

    subsection("No healthy backends")

    backend = Backend("only-backend", "az-1", healthy=False)
    load_balancer = RoundRobinLoadBalancer([backend])

    print("Backend selected:", load_balancer.choose_backend())


# =============================================================================
# 32. BASIC UNIT TESTS
# =============================================================================

def run_tests() -> None:
    section("32. BUILT-IN TESTS")

    # Storage capacity test.
    volume = StorageVolume(
        name="test-volume",
        capacity_gb=100,
        storage_type=StorageType.BLOCK,
    )
    assert volume.write(70)
    assert not volume.write(31)
    assert volume.free_gb == 30

    # Routing test.
    router = RouteTable()
    router.add_route("0.0.0.0/0", "default")
    router.add_route("10.0.0.0/8", "private")
    router.add_route("10.1.0.0/16", "specific")
    assert router.lookup("10.1.2.3") == "specific"
    assert router.lookup("10.2.2.3") == "private"
    assert router.lookup("8.8.8.8") == "default"

    # Firewall test.
    firewall = SimpleFirewall()
    firewall.add_rule(
        FirewallRule(
            source_network=IPv4Network("10.0.0.0/8"),
            destination_port=443,
            protocol="TCP",
            action="ALLOW",
        )
    )

    packet = NetworkPacket(
        source=IPv4Address("10.1.1.1"),
        destination=IPv4Address("10.2.2.2"),
        protocol="TCP",
        payload_size_bytes=100,
    )

    assert firewall.evaluate(packet, 443) == "ALLOW"
    assert firewall.evaluate(packet, 22) == "DENY"

    # VM capacity test.
    host = Server(
        name="test-host",
        cpu_cores=4,
        memory_gb=8,
        storage_gb=100,
        server_type=ServerType.BARE_METAL,
    )

    hypervisor = Hypervisor(host)

    assert hypervisor.create_vm("vm-1", 2, 4, 50) is not None
    assert hypervisor.create_vm("vm-2", 2, 4, 50) is not None
    assert hypervisor.create_vm("vm-3", 1, 1, 10) is None

    # Network subnet test.
    virtual_network = VirtualNetwork(
        name="test",
        cidr=IPv4Network("10.0.0.0/16"),
    )

    virtual_network.add_subnet(
        Subnet(
            name="subnet",
            cidr=IPv4Network("10.0.1.0/24"),
            zone="az-1",
            public=False,
        )
    )

    assert virtual_network.locate("10.0.1.5") is not None
    assert virtual_network.locate("10.1.1.1") is None

    print("All tests passed.")


# =============================================================================
# 33. MAIN PROGRAM
# =============================================================================

def main() -> None:
    """
    Execute the complete educational demonstration.

    Each section is independent enough to study separately, while the
    complete execution shows how the infrastructure concepts relate.
    """
    explain_fundamentals()
    demonstrate_servers()
    demonstrate_storage()
    demonstrate_networking()
    demonstrate_virtualization()
    demonstrate_data_centers()
    demonstrate_regions_and_zones()
    demonstrate_load_balancing()
    demonstrate_scaling()
    demonstrate_cloud_network()
    demonstrate_dns()
    demonstrate_reliability()
    demonstrate_performance()
    demonstrate_capacity_planning()
    demonstrate_cost_modeling()
    demonstrate_security()
    demonstrate_recovery()
    demonstrate_failure_simulation()
    demonstrate_containers()
    demonstrate_storage_properties()
    demonstrate_multi_region()
    demonstrate_stateful_design()
    demonstrate_observability()
    demonstrate_architecture_validation()
    demonstrate_infrastructure_as_code()
    demonstrate_common_mistakes()
    demonstrate_advanced_principles()
    production_checklist()
    run_knowledge_checks()
    demonstrate_reference_architecture()
    demonstrate_edge_cases()
    run_tests()

    section("END OF CLOUD INFRASTRUCTURE STUDY SCRIPT")
    print(
        "The script demonstrated compute, storage, networking, virtualization, "
        "hypervisors, data centers, regions, availability zones, reliability, "
        "security, scaling, performance, cost, recovery, and production design."
    )


if __name__ == "__main__":
    main()
