"""
Introduction to Computer Networking
===================================

A self-contained study program covering computer networking from absolute
beginner concepts through practical and advanced foundations.

The program uses executable demonstrations rather than relying only on prose.
It models clients, servers, protocols, packets, network infrastructure,
addressing, routing, DNS, HTTP, TCP/UDP behavior, reliability, latency,
throughput, security, and a small network simulation.

Run:
    python networking_fundamentals.py

No external packages are required.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import random
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from typing import Callable, Deque, Dict, Iterable, List, Optional, Tuple


# ============================================================================
# SECTION 1: FUNDAMENTAL TERMINOLOGY
# ============================================================================

def explain_foundations() -> None:
    print("\n" + "=" * 78)
    print("1. NETWORKING FOUNDATIONS")
    print("=" * 78)

    concepts = {
        "Network": "A collection of connected devices that can exchange data.",
        "Node": "Any participating device or endpoint in a network.",
        "Host": "A device that has an address and participates in communication.",
        "Client": "A program or device requesting a service.",
        "Server": "A program or device providing a service.",
        "Protocol": "A defined set of rules governing communication.",
        "Packet": "A unit of network-layer data carrying addressing information.",
        "Frame": "A data-link-layer unit used for local network delivery.",
        "Router": "A device that forwards packets between different networks.",
        "Switch": "A device that forwards local Ethernet frames between ports.",
        "IP address": "A logical address used for network-layer communication.",
        "MAC address": "A data-link-layer hardware/interface identifier.",
        "Port": "A transport-layer number identifying an application endpoint.",
        "Bandwidth": "The theoretical capacity of a communication link.",
        "Throughput": "The amount of useful data actually transferred per unit time.",
        "Latency": "The time required for data to travel through a communication path.",
        "DNS": "A distributed system that maps names such as example.com to addresses.",
        "HTTP": "An application-layer protocol commonly used by the Web.",
        "TCP": "A connection-oriented transport protocol providing reliable byte streams.",
        "UDP": "A connectionless transport protocol with low protocol overhead.",
    }

    for name, definition in concepts.items():
        print(f"{name:15} -> {definition}")


# ============================================================================
# SECTION 2: NETWORK LAYERS
# ============================================================================

OSI_LAYERS = [
    ("7", "Application", "HTTP, DNS, SMTP, SSH", "Application services"),
    ("6", "Presentation", "TLS concepts, encoding, serialization", "Representation"),
    ("5", "Session", "Session management concepts", "Communication sessions"),
    ("4", "Transport", "TCP, UDP", "End-to-end delivery"),
    ("3", "Network", "IP, ICMP, routing", "Logical addressing and routing"),
    ("2", "Data Link", "Ethernet, Wi-Fi, ARP", "Local network delivery"),
    ("1", "Physical", "Copper, fiber, radio", "Bits and signals"),
]

TCP_IP_LAYERS = [
    ("Application", "HTTP, DNS, SSH, SMTP"),
    ("Transport", "TCP, UDP"),
    ("Internet", "IPv4, IPv6, ICMP"),
    ("Link", "Ethernet, Wi-Fi"),
]


def demonstrate_layers() -> None:
    print("\n" + "=" * 78)
    print("2. NETWORK LAYERS")
    print("=" * 78)

    print("\nOSI reference model:")
    for number, layer, examples, purpose in OSI_LAYERS:
        print(f"Layer {number}: {layer:15} | {examples:35} | {purpose}")

    print("\nTCP/IP model:")
    for layer, examples in TCP_IP_LAYERS:
        print(f"{layer:12} | {examples}")


# ============================================================================
# SECTION 3: ENCAPSULATION
# ============================================================================

@dataclass
class ApplicationData:
    payload: str


@dataclass
class TransportSegment:
    source_port: int
    destination_port: int
    payload: ApplicationData


@dataclass
class IPPacket:
    source_ip: str
    destination_ip: str
    transport: TransportSegment


@dataclass
class EthernetFrame:
    source_mac: str
    destination_mac: str
    packet: IPPacket


def demonstrate_encapsulation() -> EthernetFrame:
    print("\n" + "=" * 78)
    print("3. ENCAPSULATION AND DECAPSULATION")
    print("=" * 78)

    application_data = ApplicationData("GET /index.html HTTP/1.1")
    segment = TransportSegment(51500, 443, application_data)
    packet = IPPacket("192.168.1.10", "93.184.216.34", segment)
    frame = EthernetFrame(
        "AA:BB:CC:DD:EE:01",
        "AA:BB:CC:DD:EE:FE",
        packet,
    )

    print("Application data:")
    print(f"  {application_data.payload}")

    print("\nTransport layer adds ports:")
    print(
        f"  source port={segment.source_port}, "
        f"destination port={segment.destination_port}"
    )

    print("\nNetwork layer adds logical addresses:")
    print(
        f"  source IP={packet.source_ip}, "
        f"destination IP={packet.destination_ip}"
    )

    print("\nData-link layer adds local delivery addresses:")
    print(
        f"  source MAC={frame.source_mac}, "
        f"destination MAC={frame.destination_mac}"
    )

    print("\nAt the receiver, these headers are processed in reverse order.")
    return frame


# ============================================================================
# SECTION 4: BINARY DATA AND PACKET STRUCTURE
# ============================================================================

def demonstrate_binary_representation() -> None:
    print("\n" + "=" * 78)
    print("4. BINARY DATA AND PACKET STRUCTURE")
    print("=" * 78)

    value = 192
    print(f"Decimal: {value}")
    print(f"Binary : {value:08b}")
    print(f"Hex    : {value:02x}")

    # IPv4 addresses are commonly represented as four octets.
    address = "192.168.1.25"
    octets = [int(part) for part in address.split(".")]
    packed = struct.pack("!BBBB", *octets)

    print(f"\nIPv4 address: {address}")
    print(f"Packed bytes: {packed!r}")
    print(f"Hex bytes   : {packed.hex()}")

    # Network protocols eventually become bytes transmitted over a medium.
    message = b"hello network"
    print(f"\nApplication bytes: {message}")
    print(f"Length: {len(message)} bytes")


# ============================================================================
# SECTION 5: IPv4 ADDRESSING AND SUBNETS
# ============================================================================

def demonstrate_ipv4() -> None:
    print("\n" + "=" * 78)
    print("5. IPv4 ADDRESSING AND SUBNETTING")
    print("=" * 78)

    examples = [
        ("192.168.1.10/24", "Private LAN host"),
        ("10.10.20.5/16", "Private enterprise host"),
        ("172.16.4.20/20", "Private network"),
        ("8.8.8.8/32", "Single-host route"),
    ]

    for address, description in examples:
        interface = ipaddress.ip_interface(address)
        network = interface.network

        print(f"\n{address} - {description}")
        print(f"  Address : {interface.ip}")
        print(f"  Network : {network.network_address}")
        print(f"  Netmask : {network.netmask}")
        print(f"  Prefix  : /{network.prefixlen}")
        print(f"  Hosts   : {network.num_addresses}")

    print("\nPrivate IPv4 ranges:")
    for network in [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    ]:
        print(f"  {network}")

    network = ipaddress.ip_network("192.168.10.0/26")
    print(f"\nSubnet example: {network}")
    print(f"Network address: {network.network_address}")
    print(f"Broadcast address: {network.broadcast_address}")
    print(f"Usable addresses: {network.num_addresses - 2}")

    test_addresses = ["192.168.10.20", "192.168.10.70"]
    for address in test_addresses:
        print(f"{address} belongs to subnet: {ipaddress.ip_address(address) in network}")


# ============================================================================
# SECTION 6: MAC ADDRESSES AND ARP CONCEPT
# ============================================================================

@dataclass
class ARPEntry:
    ip_address: str
    mac_address: str


class ARPCache:
    """A small conceptual ARP cache mapping local IP addresses to MAC addresses."""

    def __init__(self) -> None:
        self.entries: Dict[str, ARPEntry] = {}

    def learn(self, ip_address: str, mac_address: str) -> None:
        self.entries[ip_address] = ARPEntry(ip_address, mac_address)

    def lookup(self, ip_address: str) -> Optional[str]:
        entry = self.entries.get(ip_address)
        return entry.mac_address if entry else None

    def display(self) -> None:
        for entry in self.entries.values():
            print(f"  {entry.ip_address:15} -> {entry.mac_address}")


def demonstrate_arp() -> None:
    print("\n" + "=" * 78)
    print("6. MAC ADDRESSES AND ARP")
    print("=" * 78)

    cache = ARPCache()
    cache.learn("192.168.1.1", "AA:AA:AA:AA:AA:01")
    cache.learn("192.168.1.20", "BB:BB:BB:BB:BB:20")

    print("Conceptual ARP cache:")
    cache.display()

    target = "192.168.1.20"
    print(f"\nLookup for {target}: {cache.lookup(target)}")
    print(
        "\nARP resolves a local IPv4 address to a link-layer address. "
        "It is not a replacement for IP routing."
    )


# ============================================================================
# SECTION 7: CLIENT-SERVER COMMUNICATION
# ============================================================================

class SimpleServer:
    """In-memory server used to demonstrate request/response communication."""

    def __init__(self) -> None:
        self.handlers: Dict[str, Callable[[str], str]] = {
            "PING": lambda _: "PONG",
            "TIME": lambda _: time.strftime("%Y-%m-%d %H:%M:%S"),
            "ECHO": lambda payload: payload,
        }

    def handle(self, command: str, payload: str = "") -> str:
        if command not in self.handlers:
            return "ERROR: unknown command"
        return self.handlers[command](payload)


def demonstrate_client_server() -> None:
    print("\n" + "=" * 78)
    print("7. CLIENT-SERVER MODEL")
    print("=" * 78)

    server = SimpleServer()
    requests = [
        ("PING", ""),
        ("ECHO", "networking"),
        ("TIME", ""),
        ("INVALID", ""),
    ]

    for command, payload in requests:
        response = server.handle(command, payload)
        print(f"Client -> {command} {payload!r}")
        print(f"Server -> {response!r}")


# ============================================================================
# SECTION 8: DNS
# ============================================================================

def demonstrate_dns() -> None:
    print("\n" + "=" * 78)
    print("8. DNS NAME RESOLUTION")
    print("=" * 78)

    hostnames = ["localhost", "example.com", "www.python.org"]

    for hostname in hostnames:
        try:
            addresses = socket.getaddrinfo(
                hostname,
                None,
                proto=socket.IPPROTO_TCP,
            )
            unique_addresses = sorted(
                {
                    result[4][0]
                    for result in addresses
                    if result[4]
                }
            )
            print(f"{hostname:20} -> {', '.join(unique_addresses[:5])}")
        except socket.gaierror as exc:
            print(f"{hostname:20} -> resolution failed: {exc}")

    print(
        "\nDNS normally translates human-readable names into network addresses. "
        "A browser can use DNS before establishing an application connection."
    )


# ============================================================================
# SECTION 9: TCP AND UDP CONCEPTS
# ============================================================================

class DeliveryMode(Enum):
    TCP = "TCP"
    UDP = "UDP"


@dataclass
class TransportMessage:
    sequence_number: int
    payload: str
    acknowledged: bool = False


class ReliableChannel:
    """Conceptual reliable channel using sequence numbers and acknowledgements."""

    def __init__(self) -> None:
        self.next_sequence = 1
        self.unacknowledged: Dict[int, TransportMessage] = {}

    def send(self, payload: str) -> TransportMessage:
        message = TransportMessage(self.next_sequence, payload)
        self.unacknowledged[message.sequence_number] = message
        self.next_sequence += 1
        return message

    def acknowledge(self, sequence_number: int) -> bool:
        message = self.unacknowledged.get(sequence_number)
        if message is None:
            return False
        message.acknowledged = True
        del self.unacknowledged[sequence_number]
        return True

    def retransmission_candidates(self) -> List[TransportMessage]:
        return list(self.unacknowledged.values())


def demonstrate_tcp_udp() -> None:
    print("\n" + "=" * 78)
    print("9. TCP AND UDP")
    print("=" * 78)

    print("TCP characteristics:")
    print("  - connection-oriented")
    print("  - reliable byte stream")
    print("  - sequencing and acknowledgements")
    print("  - retransmission mechanisms")
    print("  - flow and congestion control")

    print("\nUDP characteristics:")
    print("  - connectionless")
    print("  - message/datagram oriented")
    print("  - lower protocol overhead")
    print("  - delivery is not guaranteed by UDP itself")
    print("  - useful where applications can tolerate loss or implement reliability")

    channel = ReliableChannel()

    first = channel.send("packet A")
    second = channel.send("packet B")

    print(f"\nSent sequence numbers: {first.sequence_number}, {second.sequence_number}")
    channel.acknowledge(first.sequence_number)

    print("Unacknowledged messages:")
    for message in channel.retransmission_candidates():
        print(f"  sequence={message.sequence_number}, payload={message.payload}")


# ============================================================================
# SECTION 10: HTTP MESSAGE STRUCTURE
# ============================================================================

@dataclass
class HTTPRequest:
    method: str
    path: str
    headers: Dict[str, str]
    body: str = ""

    def serialize(self) -> str:
        lines = [f"{self.method} {self.path} HTTP/1.1"]
        lines.extend(f"{name}: {value}" for name, value in self.headers.items())
        lines.append("")
        lines.append(self.body)
        return "\r\n".join(lines)


@dataclass
class HTTPResponse:
    status_code: int
    reason: str
    headers: Dict[str, str]
    body: str

    def serialize(self) -> str:
        lines = [f"HTTP/1.1 {self.status_code} {self.reason}"]
        lines.extend(f"{name}: {value}" for name, value in self.headers.items())
        lines.append("")
        lines.append(self.body)
        return "\r\n".join(lines)


def demonstrate_http() -> None:
    print("\n" + "=" * 78)
    print("10. HTTP REQUEST AND RESPONSE")
    print("=" * 78)

    request = HTTPRequest(
        method="GET",
        path="/users/42",
        headers={
            "Host": "api.example.test",
            "Accept": "application/json",
        },
    )

    response = HTTPResponse(
        status_code=200,
        reason="OK",
        headers={
            "Content-Type": "application/json",
            "Content-Length": "35",
        },
        body='{"id":42,"name":"Network Student"}',
    )

    print("HTTP request:")
    print(request.serialize())

    print("\nHTTP response:")
    print(response.serialize())


# ============================================================================
# SECTION 11: ROUTING
# ============================================================================

@dataclass
class Route:
    destination: ipaddress.IPv4Network
    next_hop: str
    interface: str
    metric: int = 1


class RoutingTable:
    """Longest-prefix-match routing table."""

    def __init__(self) -> None:
        self.routes: List[Route] = []

    def add_route(
        self,
        destination: str,
        next_hop: str,
        interface: str,
        metric: int = 1,
    ) -> None:
        self.routes.append(
            Route(
                ipaddress.ip_network(destination),
                next_hop,
                interface,
                metric,
            )
        )

    def lookup(self, address: str) -> Optional[Route]:
        target = ipaddress.ip_address(address)
        matching = [
            route
            for route in self.routes
            if target in route.destination
        ]

        if not matching:
            return None

        # Longest prefix wins. Metric resolves equal-prefix choices.
        return max(
            matching,
            key=lambda route: (route.destination.prefixlen, -route.metric),
        )


def demonstrate_routing() -> None:
    print("\n" + "=" * 78)
    print("11. ROUTING AND LONGEST-PREFIX MATCH")
    print("=" * 78)

    table = RoutingTable()
    table.add_route("0.0.0.0/0", "192.168.1.1", "WAN", 100)
    table.add_route("10.0.0.0/8", "192.168.1.254", "LAN-A", 20)
    table.add_route("10.20.0.0/16", "192.168.1.253", "LAN-B", 10)
    table.add_route("10.20.30.0/24", "192.168.1.252", "LAN-C", 5)

    for destination in [
        "8.8.8.8",
        "10.50.1.2",
        "10.20.40.5",
        "10.20.30.99",
    ]:
        route = table.lookup(destination)

        if route:
            print(
                f"{destination:15} -> {route.destination} "
                f"via {route.next_hop} on {route.interface}"
            )
        else:
            print(f"{destination:15} -> no route")


# ============================================================================
# SECTION 12: SWITCHING
# ============================================================================

class EthernetSwitch:
    """Small learning switch simulation."""

    def __init__(self) -> None:
        self.mac_table: Dict[str, str] = {}

    def receive(self, source_mac: str, destination_mac: str, port: str) -> str:
        # A switch learns where the source MAC address lives.
        self.mac_table[source_mac] = port

        if destination_mac in self.mac_table:
            destination_port = self.mac_table[destination_mac]
            return f"forward frame to port {destination_port}"

        return "destination unknown: flood frame to eligible ports"

    def show_table(self) -> None:
        print("Switch MAC table:")
        for mac, port in self.mac_table.items():
            print(f"  {mac} -> {port}")


def demonstrate_switching() -> None:
    print("\n" + "=" * 78)
    print("12. ETHERNET SWITCHING")
    print("=" * 78)

    switch = EthernetSwitch()

    events = [
        ("AA:AA:AA:AA:AA:01", "BB:BB:BB:BB:BB:02", "port1"),
        ("BB:BB:BB:BB:BB:02", "AA:AA:AA:AA:AA:01", "port2"),
        ("AA:AA:AA:AA:AA:01", "BB:BB:BB:BB:BB:02", "port1"),
    ]

    for source, destination, port in events:
        action = switch.receive(source, destination, port)
        print(f"{source} -> {destination}: {action}")

    print()
    switch.show_table()


# ============================================================================
# SECTION 13: PACKET LOSS, LATENCY, AND THROUGHPUT
# ============================================================================

@dataclass
class NetworkLink:
    bandwidth_mbps: float
    latency_ms: float
    packet_loss_probability: float = 0.0

    def transmission_time_ms(self, payload_bytes: int) -> float:
        bits = payload_bytes * 8
        megabits = bits / 1_000_000
        return megabits / self.bandwidth_mbps * 1000

    def transmit(self, payload: str, seed: int = 1) -> Tuple[bool, float]:
        generator = random.Random(seed)
        lost = generator.random() < self.packet_loss_probability
        total_time = self.latency_ms + self.transmission_time_ms(len(payload.encode()))
        return (not lost, total_time)


def demonstrate_network_performance() -> None:
    print("\n" + "=" * 78)
    print("13. LATENCY, BANDWIDTH, THROUGHPUT, AND LOSS")
    print("=" * 78)

    link = NetworkLink(
        bandwidth_mbps=100,
        latency_ms=20,
        packet_loss_probability=0.10,
    )

    payload = "x" * 1500
    delivered, delay = link.transmit(payload, seed=42)

    print(f"Link bandwidth : {link.bandwidth_mbps} Mbps")
    print(f"Link latency   : {link.latency_ms} ms")
    print(f"Packet size    : {len(payload)} bytes")
    print(f"Estimated time : {delay:.3f} ms")
    print(f"Delivered      : {delivered}")

    print(
        "\nBandwidth is capacity. Latency is delay. "
        "Throughput is achieved transfer rate. "
        "Packet loss represents data that fails to arrive."
    )


# ============================================================================
# SECTION 14: SERIALIZATION AND APPLICATION PROTOCOLS
# ============================================================================

@dataclass
class NetworkMessage:
    message_type: str
    request_id: int
    payload: Dict[str, object]

    def encode_json(self) -> bytes:
        document = {
            "type": self.message_type,
            "request_id": self.request_id,
            "payload": self.payload,
        }
        return json.dumps(document, separators=(",", ":")).encode("utf-8")

    @classmethod
    def decode_json(cls, raw: bytes) -> "NetworkMessage":
        document = json.loads(raw.decode("utf-8"))
        return cls(
            message_type=document["type"],
            request_id=int(document["request_id"]),
            payload=dict(document["payload"]),
        )


def demonstrate_serialization() -> None:
    print("\n" + "=" * 78)
    print("14. SERIALIZATION")
    print("=" * 78)

    message = NetworkMessage(
        "user.lookup",
        101,
        {"user_id": 42, "include_profile": True},
    )

    encoded = message.encode_json()
    decoded = NetworkMessage.decode_json(encoded)

    print(f"Serialized bytes: {encoded}")
    print(f"Decoded type: {decoded.message_type}")
    print(f"Decoded request ID: {decoded.request_id}")
    print(f"Decoded payload: {decoded.payload}")


# ============================================================================
# SECTION 15: CHECKSUMS AND INTEGRITY
# ============================================================================

def calculate_checksum(data: bytes) -> str:
    """SHA-256 is cryptographic integrity hashing, not a transport protocol."""
    return hashlib.sha256(data).hexdigest()


def demonstrate_integrity() -> None:
    print("\n" + "=" * 78)
    print("15. DATA INTEGRITY")
    print("=" * 78)

    original = b"important network message"
    modified = b"important network Message"

    original_hash = calculate_checksum(original)
    modified_hash = calculate_checksum(modified)

    print(f"Original hash : {original_hash}")
    print(f"Modified hash : {modified_hash}")
    print(f"Hashes equal? : {original_hash == modified_hash}")

    print(
        "\nA hash can detect changes when compared against a trusted value. "
        "Hashing alone does not prove who produced the data."
    )


# ============================================================================
# SECTION 16: SOCKET PROGRAMMING
# ============================================================================

def demonstrate_socket_api_without_network_connection() -> None:
    print("\n" + "=" * 78)
    print("16. SOCKET API")
    print("=" * 78)

    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        print(f"TCP socket family   : {tcp_socket.family}")
        print(f"TCP socket type     : {tcp_socket.type}")
        print(f"UDP socket family   : {udp_socket.family}")
        print(f"UDP socket type     : {udp_socket.type}")

        print(
            "\nTypical TCP server sequence:"
            "\n  socket -> bind -> listen -> accept -> recv/send -> close"
        )

        print(
            "\nTypical TCP client sequence:"
            "\n  socket -> connect -> send/recv -> close"
        )

        print(
            "\nTypical UDP exchange:"
            "\n  socket -> sendto/recvfrom -> close"
        )
    finally:
        tcp_socket.close()
        udp_socket.close()


# ============================================================================
# SECTION 17: A LOCAL TCP SERVER AND CLIENT
# ============================================================================

def run_local_tcp_demo() -> None:
    print("\n" + "=" * 78)
    print("17. LOCAL TCP CLIENT-SERVER DEMONSTRATION")
    print("=" * 78)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Binding to 127.0.0.1 keeps the demonstration on the local machine.
        server_socket.bind(("127.0.0.1", 0))
        server_socket.listen(1)

        host, port = server_socket.getsockname()
        print(f"Server listening locally on {host}:{port}")

        # A timeout prevents an accidental permanent block.
        server_socket.settimeout(2.0)

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(2.0)

        try:
            client_socket.connect((host, port))
            request = b"PING"
            client_socket.sendall(request)

            connection, client_address = server_socket.accept()
            connection.settimeout(2.0)

            try:
                received = connection.recv(1024)
                print(f"Server received: {received.decode()}")
                connection.sendall(b"PONG")
            finally:
                connection.close()

            response = client_socket.recv(1024)
            print(f"Client received: {response.decode()}")
            print(f"Client address as seen by server: {client_address}")
        finally:
            client_socket.close()

    except OSError as exc:
        print(f"Socket demonstration failed safely: {exc}")
    finally:
        server_socket.close()


# ============================================================================
# SECTION 18: TIMEOUTS, VALIDATION, AND FAILURE HANDLING
# ============================================================================

class NetworkClient:
    """Illustrates defensive handling of network operations."""

    def __init__(self, timeout_seconds: float = 2.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        self.timeout_seconds = timeout_seconds

    def resolve(self, hostname: str) -> List[str]:
        if not hostname or len(hostname) > 253:
            raise ValueError("invalid hostname length")

        try:
            results = socket.getaddrinfo(
                hostname,
                None,
                family=socket.AF_INET,
            )
        except socket.gaierror as exc:
            raise ConnectionError(
                f"DNS resolution failed for {hostname!r}"
            ) from exc

        return sorted({result[4][0] for result in results})


def demonstrate_error_handling() -> None:
    print("\n" + "=" * 78)
    print("18. NETWORK ERROR HANDLING")
    print("=" * 78)

    client = NetworkClient()

    for hostname in ["localhost", "", "this-hostname-should-not-exist.invalid"]:
        try:
            print(f"{hostname!r} -> {client.resolve(hostname)}")
        except (ValueError, ConnectionError) as exc:
            print(f"{hostname!r} -> handled error: {exc}")


# ============================================================================
# SECTION 19: FIREWALL CONCEPT
# ============================================================================

@dataclass
class FirewallRule:
    protocol: str
    destination_port: int
    action: str


class SimpleFirewall:
    """A simplified inbound rule evaluator."""

    def __init__(self, rules: Iterable[FirewallRule]) -> None:
        self.rules = list(rules)

    def decide(self, protocol: str, destination_port: int) -> str:
        for rule in self.rules:
            if (
                rule.protocol.upper() == protocol.upper()
                and rule.destination_port == destination_port
            ):
                return rule.action.upper()

        return "DENY"


def demonstrate_firewall() -> None:
    print("\n" + "=" * 78)
    print("19. FIREWALL BASICS")
    print("=" * 78)

    firewall = SimpleFirewall(
        [
            FirewallRule("TCP", 22, "allow"),
            FirewallRule("TCP", 443, "allow"),
            FirewallRule("TCP", 23, "deny"),
        ]
    )

    tests = [
        ("TCP", 22),
        ("TCP", 443),
        ("TCP", 23),
        ("UDP", 443),
    ]

    for protocol, port in tests:
        print(
            f"{protocol}/{port:5} -> "
            f"{firewall.decide(protocol, port)}"
        )

    print(
        "\nReal firewalls can inspect addresses, ports, protocols, connection "
        "state, interfaces, identities, application attributes, and more."
    )


# ============================================================================
# SECTION 20: BASIC ROUTER SIMULATION
# ============================================================================

@dataclass
class SimulatedPacket:
    packet_id: int
    source: str
    destination: str
    payload: str
    hops: List[str] = field(default_factory=list)


class SimulatedRouter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.routes: List[Tuple[ipaddress.IPv4Network, str]] = []

    def add_route(self, network: str, next_router: str) -> None:
        self.routes.append(
            (ipaddress.ip_network(network), next_router)
        )

    def route(self, destination: str) -> Optional[str]:
        target = ipaddress.ip_address(destination)
        matching = [
            (network, next_router)
            for network, next_router in self.routes
            if target in network
        ]

        if not matching:
            return None

        return max(
            matching,
            key=lambda item: item[0].prefixlen,
        )[1]


def demonstrate_router_simulation() -> None:
    print("\n" + "=" * 78)
    print("20. PACKET FORWARDING SIMULATION")
    print("=" * 78)

    router = SimulatedRouter("R1")
    router.add_route("10.1.0.0/16", "R2")
    router.add_route("10.1.20.0/24", "R3")
    router.add_route("0.0.0.0/0", "ISP")

    destinations = [
        "10.1.20.5",
        "10.1.99.5",
        "8.8.8.8",
    ]

    for destination in destinations:
        next_hop = router.route(destination)
        print(f"R1 -> {destination:15} -> {next_hop}")


# ============================================================================
# SECTION 21: NETWORK TESTING
# ============================================================================

def run_self_tests() -> None:
    print("\n" + "=" * 78)
    print("21. SELF-TESTS")
    print("=" * 78)

    network = ipaddress.ip_network("192.168.1.0/24")
    assert ipaddress.ip_address("192.168.1.20") in network
    assert ipaddress.ip_address("192.168.2.20") not in network

    table = RoutingTable()
    table.add_route("0.0.0.0/0", "gateway", "WAN")
    table.add_route("10.0.0.0/8", "internal", "LAN")

    assert table.lookup("10.2.3.4").interface == "LAN"
    assert table.lookup("8.8.8.8").interface == "WAN"

    message = NetworkMessage("test", 1, {"value": 10})
    assert NetworkMessage.decode_json(message.encode_json()).payload["value"] == 10

    firewall = SimpleFirewall([FirewallRule("TCP", 443, "allow")])
    assert firewall.decide("TCP", 443) == "ALLOW"
    assert firewall.decide("TCP", 80) == "DENY"

    print("All self-tests passed.")


# ============================================================================
# SECTION 22: PRACTICAL DIAGNOSTIC WORKFLOW
# ============================================================================

def diagnostic_workflow() -> None:
    print("\n" + "=" * 78)
    print("22. PRACTICAL NETWORK TROUBLESHOOTING WORKFLOW")
    print("=" * 78)

    steps = [
        "1. Check physical connectivity and link status.",
        "2. Verify the local interface has a valid address.",
        "3. Check subnet mask/prefix and default gateway.",
        "4. Test the local stack.",
        "5. Test the default gateway.",
        "6. Test another reachable network address.",
        "7. Test DNS resolution separately from connectivity.",
        "8. Test the application port.",
        "9. Inspect latency, packet loss, and routing.",
        "10. Inspect firewall and security controls.",
        "11. Capture traffic when packet-level evidence is required.",
        "12. Compare expected and observed protocol behavior.",
    ]

    for step in steps:
        print(step)


# ============================================================================
# SECTION 23: ADVANCED CONCEPTS
# ============================================================================

def discuss_advanced_topics() -> None:
    print("\n" + "=" * 78)
    print("23. ADVANCED NETWORKING CONCEPTS")
    print("=" * 78)

    topics = [
        ("CIDR", "Classless addressing and route aggregation."),
        ("NAT", "Translation between address/port spaces, commonly at network boundaries."),
        ("PAT", "Many private endpoints share a public address through port translation."),
        ("IPv6", "128-bit addressing with a much larger address space."),
        ("DHCP", "Automatic assignment of network configuration."),
        ("ICMP", "Control and diagnostic messaging used with IP."),
        ("TLS", "Cryptographic protection for application-layer connections."),
        ("VPN", "Protected communication over another network."),
        ("Proxy", "An intermediary that sends requests on behalf of clients."),
        ("Load balancer", "Distributes traffic across multiple service instances."),
        ("CDN", "Distributes content closer to users."),
        ("Anycast", "The same address can be announced from multiple locations."),
        ("QoS", "Techniques for managing traffic treatment and resource allocation."),
        ("Congestion control", "Transport behavior that adapts sending to network conditions."),
        ("MTU", "Maximum transmission unit of a link or path."),
        ("Fragmentation", "Splitting packets when size constraints require it."),
        ("Network namespace", "A mechanism for isolating network resources on a host."),
        ("SDN", "Software-defined networking separates control concepts from forwarding."),
    ]

    for name, definition in topics:
        print(f"{name:20} -> {definition}")


# ============================================================================
# SECTION 24: SECURITY PRINCIPLES
# ============================================================================

def discuss_security() -> None:
    print("\n" + "=" * 78)
    print("24. NETWORK SECURITY PRINCIPLES")
    print("=" * 78)

    principles = [
        "Use encryption for sensitive communication.",
        "Authenticate peers and services rather than trusting network location.",
        "Authorize access using least privilege.",
        "Validate input received from remote systems.",
        "Use timeouts so network failures cannot block resources indefinitely.",
        "Treat DNS and address data as untrusted input.",
        "Protect credentials and private keys.",
        "Segment networks when different trust levels require isolation.",
        "Log security-relevant events without exposing secrets.",
        "Patch network-facing services and dependencies.",
        "Use secure protocols rather than relying on private networks as security boundaries.",
        "Assume that packets can be delayed, duplicated, reordered, or dropped.",
    ]

    for principle in principles:
        print(f"- {principle}")


# ============================================================================
# SECTION 25: PERFORMANCE REASONING
# ============================================================================

def performance_examples() -> None:
    print("\n" + "=" * 78)
    print("25. PERFORMANCE REASONING")
    print("=" * 78)

    examples = [
        ("DNS lookup", "May add startup latency before an application connection."),
        ("TCP handshake", "Adds connection-establishment round trips."),
        ("TLS handshake", "Adds cryptographic negotiation and additional traffic."),
        ("Serialization", "Consumes CPU and increases payload size."),
        ("Packet loss", "Can reduce effective throughput and trigger retransmission."),
        ("Large RTT", "Makes request/response protocols slower even with high bandwidth."),
        ("Connection pooling", "Can avoid repeated connection setup."),
        ("Compression", "Can reduce network bytes while increasing CPU usage."),
        ("Caching", "Can reduce repeated network requests."),
        ("Keep-alive", "Can reuse established connections."),
    ]

    for mechanism, effect in examples:
        print(f"{mechanism:20} -> {effect}")


# ============================================================================
# SECTION 26: MAIN PROGRAM
# ============================================================================

def main() -> None:
    print("=" * 78)
    print("INTRODUCTION TO COMPUTER NETWORKING")
    print("=" * 78)
    print("From basic communication to practical protocol and infrastructure concepts.")

    explain_foundations()
    demonstrate_layers()
    demonstrate_encapsulation()
    demonstrate_binary_representation()
    demonstrate_ipv4()
    demonstrate_arp()
    demonstrate_client_server()
    demonstrate_dns()
    demonstrate_tcp_udp()
    demonstrate_http()
    demonstrate_routing()
    demonstrate_switching()
    demonstrate_network_performance()
    demonstrate_serialization()
    demonstrate_integrity()
    demonstrate_socket_api_without_network_connection()
    run_local_tcp_demo()
    demonstrate_error_handling()
    demonstrate_firewall()
    demonstrate_router_simulation()
    run_self_tests()
    diagnostic_workflow()
    discuss_advanced_topics()
    discuss_security()
    performance_examples()

    print("\n" + "=" * 78)
    print("END OF NETWORKING STUDY PROGRAM")
    print("=" * 78)


if __name__ == "__main__":
    main()
