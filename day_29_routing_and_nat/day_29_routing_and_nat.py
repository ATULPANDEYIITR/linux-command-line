"""
Routing and NAT: Routers, Routing Tables, Gateways, NAT, Internet Gateways,
and Packet Forwarding

This standalone study program models the major concepts involved in IPv4
routing and Network Address Translation (NAT).

The examples progress from:
1. IP addresses and networks
2. Routing tables and longest-prefix matching
3. Default gateways
4. Packet forwarding
5. Static routes
6. Internet gateways
7. ARP-like next-hop resolution
8. NAT and reverse translation
9. Port Address Translation (PAT)
10. Stateful firewall behavior
11. TTL and routing loops
12. Fragmentation concepts
13. Routing metrics
14. Multi-router forwarding
15. Failure conditions
16. A complete simulated enterprise network

The simulation does not send real packets. It models the decision-making
performed by networking devices so that the behavior can be observed safely
and deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import random
import time


# ============================================================================
# SECTION 1: FUNDAMENTAL IP ADDRESS AND NETWORK CONCEPTS
# ============================================================================

def demonstrate_ip_basics() -> None:
    print("\n" + "=" * 80)
    print("1. IP ADDRESS AND NETWORK BASICS")
    print("=" * 80)

    addresses = [
        "192.168.1.10",
        "192.168.1.200",
        "10.0.0.5",
        "172.16.20.25",
    ]

    for address in addresses:
        ip = IPv4Address(address)
        print(f"{address:16} integer={int(ip):12}")

    network = IPv4Network("192.168.1.0/24")
    print(f"\nNetwork:       {network}")
    print(f"Network ID:    {network.network_address}")
    print(f"Broadcast:     {network.broadcast_address}")
    print(f"Prefix length: {network.prefixlen}")
    print(f"Netmask:       {network.netmask}")
    print(f"Host count:    {network.num_addresses - 2}")

    test_ip = IPv4Address("192.168.1.50")
    print(f"{test_ip} belongs to {network}: {test_ip in network}")

    other_ip = IPv4Address("192.168.2.50")
    print(f"{other_ip} belongs to {network}: {other_ip in network}")

    print("\nPrivate IPv4 ranges:")
    private_networks = [
        IPv4Network("10.0.0.0/8"),
        IPv4Network("172.16.0.0/12"),
        IPv4Network("192.168.0.0/16"),
    ]

    for private_network in private_networks:
        print(f"  {private_network}")


# ============================================================================
# SECTION 2: ROUTING TERMINOLOGY
# ============================================================================

@dataclass(frozen=True)
class Route:
    """
    A routing-table entry.

    destination:
        Network that can be reached.

    next_hop:
        Router address to which the packet should be forwarded.
        None means the destination network is directly connected.

    interface:
        Logical interface used for forwarding.

    metric:
        Lower values normally represent a preferred path when routes have
        equivalent prefix specificity.

    administrative_distance:
        Simplified representation of route-source preference.
    """

    destination: IPv4Network
    next_hop: Optional[IPv4Address]
    interface: str
    metric: int = 1
    administrative_distance: int = 0
    source: str = "connected"

    def matches(self, destination_ip: IPv4Address) -> bool:
        return destination_ip in self.destination


class RoutingTable:
    """
    Routing table supporting longest-prefix matching.

    The critical rule is that a router does not simply choose the first
    matching route. It normally selects the most specific matching prefix.
    """

    def __init__(self) -> None:
        self.routes: List[Route] = []

    def add_route(self, route: Route) -> None:
        self.routes.append(route)

    def remove_route(self, destination: IPv4Network) -> None:
        self.routes = [
            route for route in self.routes
            if route.destination != destination
        ]

    def lookup(self, destination_ip: IPv4Address) -> Optional[Route]:
        matching_routes = [
            route for route in self.routes
            if route.matches(destination_ip)
        ]

        if not matching_routes:
            return None

        # Longest prefix first.
        # For equally specific routes, prefer lower administrative distance
        # and then lower metric.
        matching_routes.sort(
            key=lambda route: (
                -route.destination.prefixlen,
                route.administrative_distance,
                route.metric,
            )
        )

        return matching_routes[0]

    def display(self) -> None:
        print(
            f"{'Destination':20}"
            f"{'Next Hop':16}"
            f"{'Interface':12}"
            f"{'Metric':8}"
            f"{'AD':6}"
            f"{'Source':12}"
        )

        print("-" * 76)

        for route in sorted(
            self.routes,
            key=lambda item: (
                -item.destination.prefixlen,
                str(item.destination),
            ),
        ):
            next_hop = str(route.next_hop) if route.next_hop else "direct"
            print(
                f"{str(route.destination):20}"
                f"{next_hop:16}"
                f"{route.interface:12}"
                f"{route.metric:<8}"
                f"{route.administrative_distance:<6}"
                f"{route.source:12}"
            )


def demonstrate_longest_prefix_matching() -> None:
    print("\n" + "=" * 80)
    print("2. ROUTING TABLES AND LONGEST-PREFIX MATCHING")
    print("=" * 80)

    table = RoutingTable()

    table.add_route(
        Route(
            IPv4Network("0.0.0.0/0"),
            IPv4Address("192.168.1.1"),
            "eth0",
            metric=100,
            source="static-default",
        )
    )

    table.add_route(
        Route(
            IPv4Network("10.0.0.0/8"),
            IPv4Address("192.168.1.2"),
            "eth1",
            metric=20,
            source="static",
        )
    )

    table.add_route(
        Route(
            IPv4Network("10.20.0.0/16"),
            IPv4Address("192.168.1.3"),
            "eth2",
            metric=10,
            source="static",
        )
    )

    table.add_route(
        Route(
            IPv4Network("10.20.30.0/24"),
            IPv4Address("192.168.1.4"),
            "eth3",
            metric=5,
            source="static",
        )
    )

    table.display()

    destinations = [
        "10.20.30.55",
        "10.20.99.10",
        "10.99.10.10",
        "172.16.0.10",
    ]

    print("\nLookup results:")

    for destination in destinations:
        ip = IPv4Address(destination)
        route = table.lookup(ip)

        if route:
            print(
                f"{destination:16} -> "
                f"{route.destination} via "
                f"{route.next_hop or 'direct'} on {route.interface}"
            )
        else:
            print(f"{destination:16} -> no route")


# ============================================================================
# SECTION 3: HOSTS, SUBNETS, AND DEFAULT GATEWAYS
# ============================================================================

@dataclass
class Host:
    name: str
    ip: IPv4Address
    network: IPv4Network
    default_gateway: Optional[IPv4Address]


def demonstrate_default_gateway() -> None:
    print("\n" + "=" * 80)
    print("3. DEFAULT GATEWAY")
    print("=" * 80)

    host = Host(
        name="Laptop",
        ip=IPv4Address("192.168.10.25"),
        network=IPv4Network("192.168.10.0/24"),
        default_gateway=IPv4Address("192.168.10.1"),
    )

    destinations = [
        IPv4Address("192.168.10.50"),
        IPv4Address("8.8.8.8"),
    ]

    for destination in destinations:
        if destination in host.network:
            decision = "send directly on the local network"
        elif host.default_gateway:
            decision = f"send to default gateway {host.default_gateway}"
        else:
            decision = "no route"

        print(f"{host.ip} -> {destination}: {decision}")

    print(
        "\nA default gateway is normally the local router interface used "
        "when no more-specific route exists on the host."
    )


# ============================================================================
# SECTION 4: PACKET MODEL
# ============================================================================

@dataclass
class Packet:
    source_ip: IPv4Address
    destination_ip: IPv4Address
    protocol: str = "TCP"
    source_port: Optional[int] = None
    destination_port: Optional[int] = None
    ttl: int = 64
    payload_size: int = 100
    history: List[str] = field(default_factory=list)

    def describe(self) -> str:
        ports = ""

        if self.source_port is not None and self.destination_port is not None:
            ports = f":{self.source_port} -> :{self.destination_port}"

        return (
            f"{self.source_ip}{ports} -> "
            f"{self.destination_ip} "
            f"{self.protocol} TTL={self.ttl}"
        )


class Router:
    """
    Simplified IPv4 router.

    The router:
    1. receives a packet,
    2. decrements TTL,
    3. performs a routing-table lookup,
    4. chooses a next hop/interface,
    5. forwards the packet if a route exists.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.routing_table = RoutingTable()
        self.interfaces: Dict[str, IPv4Address] = {}

    def add_interface(
        self,
        interface_name: str,
        address: str,
        prefix_length: int,
    ) -> None:
        ip = IPv4Address(address)
        network = IPv4Network(f"{address}/{prefix_length}", strict=False)

        self.interfaces[interface_name] = ip

        self.routing_table.add_route(
            Route(
                destination=network,
                next_hop=None,
                interface=interface_name,
                metric=0,
                source="connected",
            )
        )

    def add_static_route(
        self,
        destination: str,
        next_hop: str,
        interface: str,
        metric: int = 1,
    ) -> None:
        self.routing_table.add_route(
            Route(
                destination=IPv4Network(destination),
                next_hop=IPv4Address(next_hop),
                interface=interface,
                metric=metric,
                source="static",
            )
        )

    def add_default_route(
        self,
        next_hop: str,
        interface: str,
        metric: int = 1,
    ) -> None:
        self.add_static_route(
            "0.0.0.0/0",
            next_hop,
            interface,
            metric,
        )

    def forward(self, packet: Packet) -> Optional[Route]:
        packet.history.append(self.name)

        if packet.ttl <= 1:
            raise RuntimeError(
                f"{self.name}: TTL expired for {packet.destination_ip}"
            )

        packet.ttl -= 1

        route = self.routing_table.lookup(packet.destination_ip)

        if route is None:
            return None

        return route


def demonstrate_packet_forwarding() -> None:
    print("\n" + "=" * 80)
    print("4. PACKET FORWARDING")
    print("=" * 80)

    router = Router("R1")

    router.add_interface("LAN", "192.168.1.1", 24)
    router.add_interface("WAN", "203.0.113.2", 30)
    router.add_static_route(
        "10.10.0.0/16",
        "203.0.113.1",
        "WAN",
    )

    packet = Packet(
        source_ip=IPv4Address("192.168.1.50"),
        destination_ip=IPv4Address("10.10.20.30"),
        protocol="TCP",
        source_port=50000,
        destination_port=443,
    )

    route = router.forward(packet)

    print(f"Packet: {packet.describe()}")

    if route:
        next_hop = route.next_hop or packet.destination_ip
        print(f"Selected route: {route.destination}")
        print(f"Forward via: {route.interface}")
        print(f"Next hop: {next_hop}")
        print(f"Remaining TTL: {packet.ttl}")
    else:
        print("No route to destination.")


# ============================================================================
# SECTION 5: INTERNET GATEWAY
# ============================================================================

class InternetGateway(Router):
    """
    A conceptual Internet gateway.

    In real environments, an Internet gateway can be implemented through
    different architectures. This simulation models the common idea of a
    boundary device that connects a private network to an external network.
    """

    def __init__(self, name: str, public_address: str) -> None:
        super().__init__(name)
        self.public_address = IPv4Address(public_address)

    def describe(self) -> None:
        print(
            f"{self.name}: external/public-facing address "
            f"{self.public_address}"
        )


def demonstrate_internet_gateway() -> None:
    print("\n" + "=" * 80)
    print("5. INTERNET GATEWAY")
    print("=" * 80)

    gateway = InternetGateway("EDGE-GW", "198.51.100.10")
    gateway.add_interface("LAN", "192.168.50.1", 24)
    gateway.add_interface("WAN", "198.51.100.10", 24)
    gateway.describe()

    print(
        "\nPrivate host -> default gateway -> edge gateway -> "
        "upstream network -> Internet destination"
    )


# ============================================================================
# SECTION 6: NAT
# ============================================================================

@dataclass(frozen=True)
class NATKey:
    private_ip: IPv4Address
    private_port: int
    remote_ip: IPv4Address
    remote_port: int
    protocol: str


@dataclass
class NATTranslation:
    private_ip: IPv4Address
    private_port: int
    public_ip: IPv4Address
    public_port: int
    remote_ip: IPv4Address
    remote_port: int
    protocol: str
    created_at: float = field(default_factory=time.time)


class NATTable:
    """
    Stateful NAT/PAT table.

    This implementation models source NAT for outbound connections.

    Example:

        192.168.1.10:51500
            becomes
        203.0.113.10:40000

    The remote server sees the public address and translated source port.
    """

    def __init__(self, public_ip: str, first_port: int = 40000) -> None:
        self.public_ip = IPv4Address(public_ip)
        self.next_port = first_port

        self.outbound: Dict[NATKey, NATTranslation] = {}
        self.inbound: Dict[
            Tuple[IPv4Address, int, str],
            NATTranslation
        ] = {}

    def _allocate_port(self) -> int:
        start = self.next_port

        while True:
            candidate = self.next_port
            self.next_port += 1

            if self.next_port > 60000:
                self.next_port = 40000

            occupied = any(
                translation.public_port == candidate
                for translation in self.outbound.values()
            )

            if not occupied:
                return candidate

            if self.next_port == start:
                raise RuntimeError("NAT port pool exhausted")

    def translate_outbound(
        self,
        source_ip: IPv4Address,
        source_port: int,
        destination_ip: IPv4Address,
        destination_port: int,
        protocol: str,
    ) -> NATTranslation:

        key = NATKey(
            source_ip,
            source_port,
            destination_ip,
            destination_port,
            protocol,
        )

        if key in self.outbound:
            return self.outbound[key]

        public_port = self._allocate_port()

        translation = NATTranslation(
            private_ip=source_ip,
            private_port=source_port,
            public_ip=self.public_ip,
            public_port=public_port,
            remote_ip=destination_ip,
            remote_port=destination_port,
            protocol=protocol,
        )

        self.outbound[key] = translation

        self.inbound[
            (self.public_ip, public_port, protocol)
        ] = translation

        return translation

    def translate_inbound(
        self,
        public_port: int,
        destination_ip: IPv4Address,
        destination_port: int,
        protocol: str,
    ) -> Optional[NATTranslation]:

        translation = self.inbound.get(
            (destination_ip, public_port, protocol)
        )

        if translation is None:
            return None

        return translation

    def display(self) -> None:
        print(
            f"{'Private':24}"
            f"{'Public':24}"
            f"{'Remote':24}"
            f"{'Protocol':10}"
        )

        print("-" * 82)

        for translation in self.outbound.values():
            private = (
                f"{translation.private_ip}:"
                f"{translation.private_port}"
            )

            public = (
                f"{translation.public_ip}:"
                f"{translation.public_port}"
            )

            remote = (
                f"{translation.remote_ip}:"
                f"{translation.remote_port}"
            )

            print(
                f"{private:24}"
                f"{public:24}"
                f"{remote:24}"
                f"{translation.protocol:10}"
            )


def demonstrate_nat() -> None:
    print("\n" + "=" * 80)
    print("6. NAT AND PAT")
    print("=" * 80)

    nat = NATTable("203.0.113.10")

    private_packet = Packet(
        source_ip=IPv4Address("192.168.1.20"),
        destination_ip=IPv4Address("93.184.216.34"),
        protocol="TCP",
        source_port=51500,
        destination_port=443,
    )

    translation = nat.translate_outbound(
        private_packet.source_ip,
        private_packet.source_port,
        private_packet.destination_ip,
        private_packet.destination_port,
        private_packet.protocol,
    )

    print("Before NAT:")
    print(f"  {private_packet.describe()}")

    print("\nAfter source NAT/PAT:")
    print(
        f"  {translation.public_ip}:{translation.public_port} -> "
        f"{translation.remote_ip}:{translation.remote_port}"
    )

    nat.display()

    return_packet = nat.translate_inbound(
        public_port=translation.public_port,
        destination_ip=translation.public_ip,
        destination_port=translation.public_port,
        protocol="TCP",
    )

    print("\nInbound response:")
    if return_packet:
        print(
            f"  Restore destination to "
            f"{return_packet.private_ip}:{return_packet.private_port}"
        )
    else:
        print("  No matching NAT state.")


# ============================================================================
# SECTION 7: NAT TYPES AND BEHAVIOR
# ============================================================================

def explain_nat_variants() -> None:
    print("\n" + "=" * 80)
    print("7. NAT VARIANTS")
    print("=" * 80)

    variants = {
        "Static NAT": (
            "A stable one-to-one mapping between a private and public address."
        ),
        "Dynamic NAT": (
            "Private addresses are mapped to addresses selected from a pool."
        ),
        "PAT/NAT overload": (
            "Multiple private hosts share one public IP by using transport "
            "layer port numbers."
        ),
        "Destination NAT": (
            "The destination address or port is rewritten, often for inbound "
            "port forwarding."
        ),
        "Source NAT": (
            "The source address is rewritten, commonly for outbound traffic."
        ),
    }

    for name, description in variants.items():
        print(f"{name}: {description}")


# ============================================================================
# SECTION 8: NEXT-HOP AND ARP-LIKE RESOLUTION
# ============================================================================

class NeighborCache:
    """
    Small conceptual equivalent of a host/router neighbor cache.

    IPv4 routers commonly use ARP on Ethernet networks to map an IPv4
    next-hop address to a MAC address.
    """

    def __init__(self) -> None:
        self.entries: Dict[IPv4Address, str] = {}

    def learn(self, ip: str, mac: str) -> None:
        self.entries[IPv4Address(ip)] = mac

    def resolve(self, ip: IPv4Address) -> Optional[str]:
        return self.entries.get(ip)


def demonstrate_next_hop_resolution() -> None:
    print("\n" + "=" * 80)
    print("8. NEXT-HOP RESOLUTION")
    print("=" * 80)

    cache = NeighborCache()

    cache.learn("192.168.1.1", "02:00:00:00:01:01")
    cache.learn("192.168.1.20", "02:00:00:00:01:20")

    next_hop = IPv4Address("192.168.1.1")

    mac = cache.resolve(next_hop)

    print(f"Next hop: {next_hop}")

    if mac:
        print(f"Resolved MAC address: {mac}")
    else:
        print("No neighbor entry; an ARP request would normally be needed.")


# ============================================================================
# SECTION 9: ROUTING METRICS
# ============================================================================

def choose_best_equal_prefix_route(routes: List[Route]) -> Route:
    """
    Select a route when prefix length is already known to be equal.

    Lower administrative distance is preferred first, followed by lower
    metric.
    """
    return min(
        routes,
        key=lambda route: (
            route.administrative_distance,
            route.metric,
        ),
    )


def demonstrate_metrics() -> None:
    print("\n" + "=" * 80)
    print("9. ROUTE METRICS AND ROUTE SOURCES")
    print("=" * 80)

    routes = [
        Route(
            IPv4Network("10.50.0.0/16"),
            IPv4Address("192.168.1.1"),
            "eth1",
            metric=20,
            administrative_distance=110,
            source="OSPF",
        ),
        Route(
            IPv4Network("10.50.0.0/16"),
            IPv4Address("192.168.2.1"),
            "eth2",
            metric=5,
            administrative_distance=110,
            source="OSPF",
        ),
        Route(
            IPv4Network("10.50.0.0/16"),
            IPv4Address("192.168.3.1"),
            "eth3",
            metric=1,
            administrative_distance=120,
            source="RIP",
        ),
    ]

    selected = choose_best_equal_prefix_route(routes)

    for route in routes:
        print(
            f"{route.source:8} "
            f"AD={route.administrative_distance:<3} "
            f"metric={route.metric:<3} "
            f"next-hop={route.next_hop}"
        )

    print(f"\nSelected route: {selected.source} via {selected.next_hop}")

    print(
        "\nRouting protocols can use different metrics and administrative "
        "distances. The exact selection process depends on the routing "
        "platform and protocol."
    )


# ============================================================================
# SECTION 10: TTL AND ROUTING LOOPS
# ============================================================================

def demonstrate_ttl() -> None:
    print("\n" + "=" * 80)
    print("10. TTL AND ROUTING LOOPS")
    print("=" * 80)

    packet = Packet(
        source_ip=IPv4Address("10.0.0.10"),
        destination_ip=IPv4Address("10.0.0.20"),
        ttl=3,
    )

    print(f"Initial TTL: {packet.ttl}")

    for router_number in range(1, 5):
        if packet.ttl <= 1:
            print(
                f"Router {router_number}: TTL would expire; "
                "packet is discarded."
            )
            break

        packet.ttl -= 1
        print(
            f"Router {router_number}: "
            f"forwarded, TTL={packet.ttl}"
        )

    print(
        "\nTTL prevents a packet caught in a persistent routing loop "
        "from circulating indefinitely."
    )


# ============================================================================
# SECTION 11: ROUTING LOOP SIMULATION
# ============================================================================

def demonstrate_routing_loop() -> None:
    print("\n" + "=" * 80)
    print("11. ROUTING LOOP SIMULATION")
    print("=" * 80)

    router_a = Router("R-A")
    router_b = Router("R-B")

    router_a.add_interface("link", "10.0.0.1", 24)
    router_b.add_interface("link", "10.0.0.2", 24)

    router_a.add_static_route(
        "172.16.0.0/16",
        "10.0.0.2",
        "link",
    )

    router_b.add_static_route(
        "172.16.0.0/16",
        "10.0.0.1",
        "link",
    )

    packet = Packet(
        source_ip=IPv4Address("192.168.1.10"),
        destination_ip=IPv4Address("172.16.10.10"),
        ttl=6,
    )

    routers = [router_a, router_b]

    for index in range(10):
        router = routers[index % 2]

        try:
            route = router.forward(packet)
        except RuntimeError as error:
            print(error)
            break

        print(
            f"{router.name}: destination={packet.destination_ip}, "
            f"next-hop={route.next_hop if route else 'none'}, "
            f"TTL={packet.ttl}"
        )

        if route is None:
            print("Packet discarded because no route exists.")
            break


# ============================================================================
# SECTION 12: ROUTER WITH MULTIPLE NETWORKS
# ============================================================================

class MultiNetworkRouter(Router):
    """
    Router used for a realistic enterprise-style topology.
    """

    def show_interfaces(self) -> None:
        print(f"\nInterfaces for {self.name}:")
        for name, address in self.interfaces.items():
            print(f"  {name:12} {address}")


def demonstrate_multi_network_router() -> None:
    print("\n" + "=" * 80)
    print("12. MULTI-NETWORK ROUTER")
    print("=" * 80)

    router = MultiNetworkRouter("CORE-R1")

    router.add_interface("LAN_USERS", "10.10.10.1", 24)
    router.add_interface("LAN_SERVERS", "10.10.20.1", 24)
    router.add_interface("LAN_IOT", "10.10.30.1", 24)
    router.add_interface("WAN", "198.51.100.2", 30)

    router.add_default_route(
        "198.51.100.1",
        "WAN",
    )

    router.show_interfaces()

    for destination in [
        "10.10.10.50",
        "10.10.20.50",
        "10.10.30.50",
        "1.1.1.1",
    ]:
        route = router.routing_table.lookup(
            IPv4Address(destination)
        )

        print(
            f"{destination:16} -> "
            f"{route.destination if route else 'NO ROUTE'} "
            f"via {route.interface if route else '-'}"
        )


# ============================================================================
# SECTION 13: PACKET FORWARDING PIPELINE
# ============================================================================

class ForwardingPipeline:
    """
    Conceptual forwarding pipeline.

    A real implementation has considerably more complexity, but the core
    logical stages can be represented as:
        ingress
        validation
        routing lookup
        policy
        next-hop resolution
        egress
    """

    def __init__(self, router: Router) -> None:
        self.router = router

    def process(self, packet: Packet) -> str:
        if packet.ttl <= 1:
            return "DROP: TTL expired"

        if packet.payload_size < 0:
            return "DROP: invalid payload size"

        route = self.router.forward(packet)

        if route is None:
            return "DROP: no route"

        return (
            f"FORWARD: interface={route.interface}, "
            f"next-hop={route.next_hop or packet.destination_ip}, "
            f"ttl={packet.ttl}"
        )


def demonstrate_forwarding_pipeline() -> None:
    print("\n" + "=" * 80)
    print("13. FORWARDING PIPELINE")
    print("=" * 80)

    router = Router("R-EDGE")
    router.add_interface("LAN", "10.0.0.1", 24)
    router.add_interface("WAN", "198.51.100.2", 30)
    router.add_default_route("198.51.100.1", "WAN")

    pipeline = ForwardingPipeline(router)

    packets = [
        Packet(
            IPv4Address("10.0.0.20"),
            IPv4Address("8.8.8.8"),
            ttl=64,
        ),
        Packet(
            IPv4Address("10.0.0.20"),
            IPv4Address("8.8.8.8"),
            ttl=1,
        ),
    ]

    for packet in packets:
        print(packet.describe())
        print("  " + pipeline.process(packet))


# ============================================================================
# SECTION 14: EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print("\n" + "=" * 80)
    print("14. IMPORTANT EDGE CASES")
    print("=" * 80)

    edge_cases = [
        (
            "Destination is the router itself",
            "A router may consume locally addressed traffic rather than "
            "forwarding it."
        ),
        (
            "No matching route",
            "The packet is normally discarded and an ICMP destination "
            "unreachable message may be generated."
        ),
        (
            "TTL reaches zero",
            "The packet is discarded and an ICMP Time Exceeded message may "
            "be generated."
        ),
        (
            "Overlapping routes",
            "Longest-prefix matching selects the most specific route."
        ),
        (
            "Multiple equal-cost paths",
            "A platform may use equal-cost multipath behavior."
        ),
        (
            "NAT state missing",
            "A return packet may not be associated with an existing "
            "translation and can be dropped."
        ),
        (
            "NAT port exhaustion",
            "A PAT gateway cannot create additional translations when its "
            "available transport identifiers are exhausted."
        ),
        (
            "Asymmetric routing",
            "The forward and return paths can differ, which can interact "
            "with stateful firewalls and NAT."
        ),
    ]

    for name, explanation in edge_cases:
        print(f"\n{name}:")
        print(f"  {explanation}")


# ============================================================================
# SECTION 15: SECURITY CONSIDERATIONS
# ============================================================================

def demonstrate_security_concepts() -> None:
    print("\n" + "=" * 80)
    print("15. SECURITY CONSIDERATIONS")
    print("=" * 80)

    security_points = [
        "NAT is not a replacement for a firewall.",
        "A stateful firewall tracks connection state and applies policy.",
        "Unexpected inbound traffic should be evaluated against policy.",
        "Management interfaces should not be exposed unnecessarily.",
        "Routing protocols should use authentication where supported.",
        "Route advertisements should be controlled and validated.",
        "Network segmentation limits unnecessary lateral communication.",
        "Logging should capture important routing, NAT, and security events.",
        "NAT mappings can expose metadata even though private addresses are "
        "not directly visible externally.",
        "IPv4 NAT does not provide confidentiality; encryption is still needed."
    ]

    for point in security_points:
        print(f"- {point}")


# ============================================================================
# SECTION 16: STATEFUL FIREWALL CONCEPT
# ============================================================================

@dataclass(frozen=True)
class Connection:
    source_ip: IPv4Address
    source_port: int
    destination_ip: IPv4Address
    destination_port: int
    protocol: str


class StatefulFirewall:
    """
    Simplified stateful firewall.

    Outbound connections create state. Return traffic is accepted when it
    matches the reverse direction of a known connection.
    """

    def __init__(self) -> None:
        self.connections: set[Connection] = set()

    def allow_outbound(self, connection: Connection) -> bool:
        self.connections.add(connection)
        return True

    def allow_inbound(
        self,
        source_ip: IPv4Address,
        source_port: int,
        destination_ip: IPv4Address,
        destination_port: int,
        protocol: str,
    ) -> bool:

        for connection in self.connections:
            if (
                connection.source_ip == destination_ip
                and connection.source_port == destination_port
                and connection.destination_ip == source_ip
                and connection.destination_port == source_port
                and connection.protocol == protocol
            ):
                return True

        return False


def demonstrate_stateful_firewall() -> None:
    print("\n" + "=" * 80)
    print("16. STATEFUL FIREWALL")
    print("=" * 80)

    firewall = StatefulFirewall()

    outbound = Connection(
        IPv4Address("192.168.1.20"),
        50000,
        IPv4Address("93.184.216.34"),
        443,
        "TCP",
    )

    print(
        "Outbound connection allowed:",
        firewall.allow_outbound(outbound),
    )

    return_allowed = firewall.allow_inbound(
        IPv4Address("93.184.216.34"),
        443,
        IPv4Address("192.168.1.20"),
        50000,
        "TCP",
    )

    print("Matching response allowed:", return_allowed)

    unsolicited = firewall.allow_inbound(
        IPv4Address("203.0.113.90"),
        5555,
        IPv4Address("192.168.1.20"),
        50000,
        "TCP",
    )

    print("Unsolicited traffic allowed:", unsolicited)


# ============================================================================
# SECTION 17: COMPLETE NETWORK SIMULATION
# ============================================================================

class NetworkSimulator:
    """
    Small end-to-end network simulation.

    Topology:

        Client
          |
       LAN switch
          |
        EDGE
          |
       CORE
          |
      Internet

    The simulator models:
        - default gateway
        - routing
        - NAT
        - stateful firewall
        - forwarding
    """

    def __init__(self) -> None:
        self.edge = Router("EDGE")
        self.core = Router("CORE")

        self.nat = NATTable("198.51.100.10")
        self.firewall = StatefulFirewall()

        self._build_topology()

    def _build_topology(self) -> None:
        self.edge.add_interface("LAN", "192.168.50.1", 24)
        self.edge.add_interface("TRANSIT", "10.0.0.1", 30)

        self.core.add_interface("TRANSIT", "10.0.0.2", 30)
        self.core.add_interface("WAN", "198.51.100.1", 30)

        self.edge.add_default_route(
            "10.0.0.2",
            "TRANSIT",
        )

        self.core.add_route(
            Route(
                IPv4Network("192.168.50.0/24"),
                IPv4Address("10.0.0.1"),
                "TRANSIT",
                source="static",
            )
        )

    def send_to_internet(
        self,
        source_ip: str,
        source_port: int,
        destination_ip: str,
        destination_port: int,
    ) -> None:
        packet = Packet(
            source_ip=IPv4Address(source_ip),
            destination_ip=IPv4Address(destination_ip),
            protocol="TCP",
            source_port=source_port,
            destination_port=destination_port,
        )

        print("\nClient creates packet:")
        print(f"  {packet.describe()}")

        edge_route = self.edge.forward(packet)

        if edge_route is None:
            print("EDGE: no route")
            return

        print(
            f"EDGE: forward via {edge_route.interface}, "
            f"next-hop={edge_route.next_hop}"
        )

        core_route = self.core.forward(packet)

        if core_route is None:
            print("CORE: no route")
            return

        print(
            f"CORE: forward via {core_route.interface}, "
            f"next-hop={core_route.next_hop}"
        )

        if packet.source_port is None or packet.destination_port is None:
            print("Transport ports required for this NAT simulation.")
            return

        connection = Connection(
            packet.source_ip,
            packet.source_port,
            packet.destination_ip,
            packet.destination_port,
            packet.protocol,
        )

        if not self.firewall.allow_outbound(connection):
            print("Firewall: outbound connection denied.")
            return

        translation = self.nat.translate_outbound(
            packet.source_ip,
            packet.source_port,
            packet.destination_ip,
            packet.destination_port,
            packet.protocol,
        )

        print("\nNAT gateway:")
        print(
            f"  {translation.private_ip}:{translation.private_port}"
            f" -> "
            f"{translation.public_ip}:{translation.public_port}"
        )

        print(
            f"\nInternet server sees source "
            f"{translation.public_ip}:{translation.public_port}"
        )

        response = self.nat.translate_inbound(
            public_port=translation.public_port,
            destination_ip=translation.public_ip,
            destination_port=translation.public_port,
            protocol=translation.protocol,
        )

        if response is None:
            print("Return traffic: no NAT state")
            return

        print(
            "Return traffic translated to "
            f"{response.private_ip}:{response.private_port}"
        )

        accepted = self.firewall.allow_inbound(
            source_ip=response.remote_ip,
            source_port=response.remote_port,
            destination_ip=response.private_ip,
            destination_port=response.private_port,
            protocol=response.protocol,
        )

        print(f"Stateful firewall permits return traffic: {accepted}")

    def add_route(
        self,
        route: Route,
    ) -> None:
        self.core.routing_table.add_route(route)


def demonstrate_complete_network() -> None:
    print("\n" + "=" * 80)
    print("17. COMPLETE NETWORK SIMULATION")
    print("=" * 80)

    simulator = NetworkSimulator()

    simulator.send_to_internet(
        source_ip="192.168.50.25",
        source_port=51500,
        destination_ip="93.184.216.34",
        destination_port=443,
    )


# ============================================================================
# SECTION 18: ROUTE AGGREGATION
# ============================================================================

def demonstrate_route_aggregation() -> None:
    print("\n" + "=" * 80)
    print("18. ROUTE AGGREGATION")
    print("=" * 80)

    specific_routes = [
        IPv4Network("10.10.0.0/24"),
        IPv4Network("10.10.1.0/24"),
        IPv4Network("10.10.2.0/24"),
        IPv4Network("10.10.3.0/24"),
    ]

    aggregate = IPv4Network("10.10.0.0/22")

    print("Specific routes:")

    for network in specific_routes:
        print(f"  {network}")

    print(f"\nPossible aggregate: {aggregate}")

    for network in specific_routes:
        print(
            f"{network} contained by {aggregate}: "
            f"{network.subnet_of(aggregate)}"
        )

    print(
        "\nAggregation can reduce routing-table size and routing-update "
        "volume when address allocation supports it."
    )


# ============================================================================
# SECTION 19: ROUTING VERSUS SWITCHING
# ============================================================================

def explain_routing_vs_switching() -> None:
    print("\n" + "=" * 80)
    print("19. ROUTING VERSUS SWITCHING")
    print("=" * 80)

    comparison = [
        ("Primary addressing", "IP address", "MAC address"),
        ("Typical layer", "Network layer", "Data-link layer"),
        ("Main decision", "Destination network", "Destination MAC"),
        ("Typical device", "Router / Layer-3 switch", "Ethernet switch"),
        ("Broadcast domains", "Separates them", "Normally forwards within VLAN"),
        ("Path selection", "Routing table", "MAC address table"),
    ]

    print(
        f"{'Concept':24}{'Routing':28}{'Switching':28}"
    )
    print("-" * 80)

    for row in comparison:
        print(f"{row[0]:24}{row[1]:28}{row[2]:28}")


# ============================================================================
# SECTION 20: PERFORMANCE CONSIDERATIONS
# ============================================================================

def explain_performance() -> None:
    print("\n" + "=" * 80)
    print("20. PERFORMANCE CONSIDERATIONS")
    print("=" * 80)

    points = [
        (
            "Longest-prefix lookup",
            "Routers use optimized lookup structures rather than scanning "
            "every route linearly."
        ),
        (
            "Forwarding plane",
            "High-performance routers commonly separate control-plane "
            "routing decisions from packet forwarding."
        ),
        (
            "Caching",
            "Implementations may cache information, though exact mechanisms "
            "depend on platform architecture."
        ),
        (
            "NAT state",
            "Large NAT tables require efficient lookup and state expiration."
        ),
        (
            "Hardware acceleration",
            "Routers and switches may use specialized hardware or ASICs "
            "for high packet rates."
        ),
        (
            "Control-plane protection",
            "Excessive routing or management traffic can consume CPU and "
            "memory even when the forwarding plane remains healthy."
        ),
    ]

    for name, explanation in points:
        print(f"{name}:")
        print(f"  {explanation}")


# ============================================================================
# SECTION 21: TESTING
# ============================================================================

def test_longest_prefix() -> None:
    table = RoutingTable()

    table.add_route(
        Route(
            IPv4Network("0.0.0.0/0"),
            IPv4Address("192.168.1.1"),
            "default",
        )
    )

    table.add_route(
        Route(
            IPv4Network("10.0.0.0/8"),
            IPv4Address("192.168.1.2"),
            "specific",
        )
    )

    table.add_route(
        Route(
            IPv4Network("10.20.0.0/16"),
            IPv4Address("192.168.1.3"),
            "more-specific",
        )
    )

    route = table.lookup(IPv4Address("10.20.30.40"))

    assert route is not None
    assert route.destination == IPv4Network("10.20.0.0/16")


def test_default_route() -> None:
    table = RoutingTable()

    table.add_route(
        Route(
            IPv4Network("0.0.0.0/0"),
            IPv4Address("192.168.1.1"),
            "wan",
        )
    )

    route = table.lookup(IPv4Address("8.8.8.8"))

    assert route is not None
    assert route.destination == IPv4Network("0.0.0.0/0")


def test_no_route() -> None:
    table = RoutingTable()

    route = table.lookup(
        IPv4Address("192.168.100.1")
    )

    assert route is None


def test_nat_round_trip() -> None:
    nat = NATTable("203.0.113.10")

    translation = nat.translate_outbound(
        IPv4Address("192.168.1.10"),
        50000,
        IPv4Address("93.184.216.34"),
        443,
        "TCP",
    )

    reverse = nat.translate_inbound(
        translation.public_port,
        translation.public_ip,
        translation.public_port,
        "TCP",
    )

    assert reverse is not None
    assert reverse.private_ip == IPv4Address("192.168.1.10")
    assert reverse.private_port == 50000


def test_ttl_expiration() -> None:
    router = Router("R1")

    router.add_interface("LAN", "10.0.0.1", 24)

    packet = Packet(
        IPv4Address("10.0.0.10"),
        IPv4Address("8.8.8.8"),
        ttl=1,
    )

    try:
        router.forward(packet)
    except RuntimeError as error:
        assert "TTL expired" in str(error)
    else:
        raise AssertionError("TTL expiration was not detected")


def run_tests() -> None:
    print("\n" + "=" * 80)
    print("21. AUTOMATED TESTS")
    print("=" * 80)

    tests = [
        test_longest_prefix,
        test_default_route,
        test_no_route,
        test_nat_round_trip,
        test_ttl_expiration,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
            passed += 1
        except AssertionError as error:
            print(f"FAIL  {test.__name__}: {error}")

    print(f"\n{passed}/{len(tests)} tests passed.")


# ============================================================================
# SECTION 22: PRACTICAL TROUBLESHOOTING MODEL
# ============================================================================

def troubleshooting_checklist() -> None:
    print("\n" + "=" * 80)
    print("22. ROUTING AND NAT TROUBLESHOOTING")
    print("=" * 80)

    checklist = [
        "1. Verify the source host has a valid IP address.",
        "2. Verify the subnet mask/prefix length.",
        "3. Verify the default gateway.",
        "4. Verify the host can reach its gateway.",
        "5. Inspect the router interface state.",
        "6. Inspect the routing table.",
        "7. Verify the longest-prefix route selected.",
        "8. Verify the next-hop address.",
        "9. Verify next-hop neighbor resolution.",
        "10. Inspect ACL/firewall policy.",
        "11. Inspect NAT/PAT translations.",
        "12. Check whether return traffic follows a valid path.",
        "13. Check TTL-related failures and routing loops.",
        "14. Check DNS separately from IP routing.",
        "15. Check MTU and fragmentation/PMTUD when large packets fail.",
        "16. Check routing protocol state when dynamic routing is used.",
        "17. Inspect logs and packet captures where available.",
    ]

    for item in checklist:
        print(item)


# ============================================================================
# SECTION 23: COMMON MISTAKES
# ============================================================================

def common_mistakes() -> None:
    print("\n" + "=" * 80)
    print("23. COMMON MISTAKES")
    print("=" * 80)

    mistakes = [
        (
            "Confusing a router with a default gateway",
            "A default gateway is a configured next-hop concept. A router "
            "can provide that gateway function, but the terms are not "
            "identical in every context."
        ),
        (
            "Assuming NAT equals security",
            "NAT changes addressing. Security policy requires filtering, "
            "firewalling, authentication, segmentation, or other controls."
        ),
        (
            "Ignoring return routing",
            "A forward path alone does not establish successful "
            "bidirectional communication."
        ),
        (
            "Using only the first matching route",
            "Routing normally uses longest-prefix matching."
        ),
        (
            "Assuming private addresses are globally routable",
            "RFC 1918 private IPv4 addresses are intended for private use "
            "and normally require translation or another architecture "
            "before Internet communication."
        ),
        (
            "Forgetting state",
            "NAT and stateful firewalls maintain connection-related state."
        ),
        (
            "Ignoring asymmetric paths",
            "Different forward and return paths can affect stateful devices."
        ),
    ]

    for name, explanation in mistakes:
        print(f"\n{name}")
        print(f"  {explanation}")


# ============================================================================
# SECTION 24: MAIN PROGRAM
# ============================================================================

def main() -> None:
    print("=" * 80)
    print("ROUTING AND NAT: COMPLETE PYTHON STUDY PROGRAM")
    print("=" * 80)
    print(
        "Topic: routers, routing tables, gateways, NAT, Internet gateways, "
        "and packet forwarding"
    )

    demonstrate_ip_basics()
    demonstrate_longest_prefix_matching()
    demonstrate_default_gateway()
    demonstrate_packet_forwarding()
    demonstrate_internet_gateway()
    demonstrate_nat()
    explain_nat_variants()
    demonstrate_next_hop_resolution()
    demonstrate_metrics()
    demonstrate_ttl()
    demonstrate_routing_loop()
    demonstrate_multi_network_router()
    demonstrate_forwarding_pipeline()
    demonstrate_edge_cases()
    demonstrate_security_concepts()
    demonstrate_stateful_firewall()
    demonstrate_complete_network()
    demonstrate_route_aggregation()
    explain_routing_vs_switching()
    explain_performance()
    run_tests()
    troubleshooting_checklist()
    common_mistakes()

    print("\n" + "=" * 80)
    print("END OF ROUTING AND NAT STUDY PROGRAM")
    print("=" * 80)


if __name__ == "__main__":
    main()
