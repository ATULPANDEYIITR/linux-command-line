"""
OSI MODEL — COMPREHENSIVE PYTHON STUDY PROGRAM
================================================

This executable study program teaches the seven-layer OSI model from
beginner concepts through protocol behavior, encapsulation, addressing,
packet traversal, troubleshooting, security, and performance analysis.

The program uses simulations rather than requiring real packet-capture
libraries or privileged network access. The goal is to make the behavior
of each OSI layer observable through Python objects and functions.

OSI layers, from top to bottom:

7. Application
6. Presentation
5. Session
4. Transport
3. Network
2. Data Link
1. Physical

A common way to remember the direction:

Application
    ↓
Presentation
    ↓
Session
    ↓
Transport
    ↓
Network
    ↓
Data Link
    ↓
Physical

At the receiving endpoint the process is reversed.

The examples deliberately distinguish:
- protocol
- address
- data unit
- encapsulation
- decapsulation
- device
- service
- reliability
- routing
- switching
- transmission

No external package is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import ipaddress
import json
import random
import socket
import struct
import time
import zlib
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


# ============================================================================
# SECTION 1 — FUNDAMENTAL TERMINOLOGY
# ============================================================================

def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


OSI_LAYERS = {
    7: "Application",
    6: "Presentation",
    5: "Session",
    4: "Transport",
    3: "Network",
    2: "Data Link",
    1: "Physical",
}

COMMON_PROTOCOLS = {
    7: ["HTTP", "HTTPS", "DNS", "SMTP", "IMAP", "FTP", "SSH", "DHCP"],
    6: ["TLS", "JSON", "XML", "UTF-8", "JPEG", "PNG"],
    5: ["RPC", "session management", "dialog control"],
    4: ["TCP", "UDP", "SCTP", "QUIC*"],
    3: ["IPv4", "IPv6", "ICMP", "IPsec"],
    2: ["Ethernet", "802.11 Wi-Fi", "ARP", "VLAN", "PPP"],
    1: ["copper", "fiber", "radio", "electrical signaling", "optical signaling"],
}

DATA_UNITS = {
    7: "Data",
    6: "Data",
    5: "Data",
    4: "Segment / Datagram",
    3: "Packet",
    2: "Frame",
    1: "Bits / Signals",
}

DEVICES = {
    1: "Repeater, hub, physical media equipment",
    2: "Switch, bridge",
    3: "Router",
    4: "Layer-4 load balancer / firewall",
    7: "Proxy, application gateway, web server",
}


def print_osi_table() -> None:
    section("THE SEVEN OSI LAYERS")

    for number in range(7, 0, -1):
        print(
            f"Layer {number}: {OSI_LAYERS[number]:<15} | "
            f"PDU: {DATA_UNITS[number]:<18} | "
            f"Examples: {', '.join(COMMON_PROTOCOLS[number])}"
        )

    print("\nImportant distinction:")
    print("The OSI model is a conceptual reference model.")
    print("The Internet commonly uses the TCP/IP model in actual implementations.")
    print("Some real protocols do not fit perfectly into exactly one OSI layer.")


# ============================================================================
# SECTION 2 — LAYER 7: APPLICATION
# ============================================================================

@dataclass
class ApplicationMessage:
    method: str
    resource: str
    headers: Dict[str, str]
    body: str = ""

    def serialize(self) -> bytes:
        lines = [f"{self.method} {self.resource}"]
        lines.extend(f"{key}: {value}" for key, value in self.headers.items())
        lines.append("")
        lines.append(self.body)
        return "\r\n".join(lines).encode("utf-8")

    @classmethod
    def parse(cls, raw: bytes) -> "ApplicationMessage":
        text = raw.decode("utf-8")
        header_section, _, body = text.partition("\r\n\r\n")
        lines = header_section.split("\r\n")
        request_line = lines[0]
        method, resource = request_line.split(" ", 1)

        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if ": " in line:
                key, value = line.split(": ", 1)
                headers[key] = value

        return cls(method, resource, headers, body)


def application_layer_demo() -> None:
    subsection("Layer 7 — Application Layer")

    message = ApplicationMessage(
        method="GET",
        resource="/networking/osi",
        headers={
            "Host": "example.com",
            "Accept": "application/json",
            "User-Agent": "OSI-Study-Client",
        },
    )

    raw = message.serialize()

    print("Human-readable application message:")
    print(raw.decode("utf-8"))

    parsed = ApplicationMessage.parse(raw)

    print("Parsed method:", parsed.method)
    print("Parsed resource:", parsed.resource)
    print("Parsed Host:", parsed.headers["Host"])

    print("\nLayer 7 provides network services to applications.")
    print("It does not mean the application itself is necessarily Layer 7.")


# ============================================================================
# SECTION 3 — LAYER 6: PRESENTATION
# ============================================================================

def xor_transform(data: bytes, key: int) -> bytes:
    """
    A tiny reversible transformation used only to demonstrate the concept
    of transforming representation before transmission.

    This is NOT cryptographic security.
    """
    return bytes(byte ^ key for byte in data)


def presentation_layer_demo() -> None:
    subsection("Layer 6 — Presentation Layer")

    original = "OSI model: representation matters."
    encoded = original.encode("utf-8")
    compressed = zlib.compress(encoded)
    restored = zlib.decompress(compressed).decode("utf-8")

    print("Original text:", original)
    print("UTF-8 bytes:", encoded)
    print("Original size:", len(encoded))
    print("Compressed size:", len(compressed))
    print("Restored text:", restored)

    transformed = xor_transform(encoded, 0x5A)
    recovered = xor_transform(transformed, 0x5A).decode("utf-8")

    print("Representation transformation:", transformed)
    print("Recovered representation:", recovered)

    print("\nPresentation responsibilities can include:")
    print("- character encoding")
    print("- serialization")
    print("- compression")
    print("- encryption-related representation")
    print("- data format conversion")

    print("\nImportant modern networking detail:")
    print("TLS is often described in relation to the presentation/session area")
    print("of the OSI model, but modern protocol stacks do not map perfectly")


# ============================================================================
# SECTION 4 — LAYER 5: SESSION
# ============================================================================

@dataclass
class Session:
    session_id: str
    state: str = "NEW"
    sequence_number: int = 0

    def open(self) -> None:
        if self.state != "NEW":
            raise RuntimeError("Session cannot be opened from current state.")
        self.state = "ESTABLISHED"

    def send(self, payload: str) -> int:
        if self.state != "ESTABLISHED":
            raise RuntimeError("Session is not established.")
        self.sequence_number += 1
        return self.sequence_number

    def close(self) -> None:
        if self.state != "ESTABLISHED":
            raise RuntimeError("Session is not established.")
        self.state = "CLOSED"


def session_layer_demo() -> None:
    subsection("Layer 5 — Session Layer")

    session = Session(session_id="SESSION-001")

    print("Initial state:", session.state)
    session.open()
    print("After opening:", session.state)

    for message in ["Hello", "Data packet one", "Data packet two"]:
        sequence = session.send(message)
        print(f"Sent logical session message #{sequence}: {message}")

    session.close()
    print("After closing:", session.state)

    print("\nSession concepts:")
    print("- establishment")
    print("- maintenance")
    print("- synchronization")
    print("- dialog management")
    print("- termination")


# ============================================================================
# SECTION 5 — LAYER 4: TRANSPORT
# ============================================================================

class TransportProtocol(Enum):
    TCP = "TCP"
    UDP = "UDP"


@dataclass
class TransportSegment:
    source_port: int
    destination_port: int
    payload: bytes
    protocol: TransportProtocol
    sequence_number: Optional[int] = None
    acknowledgment_number: Optional[int] = None
    checksum: Optional[int] = None
    flags: List[str] = field(default_factory=list)

    def calculate_checksum(self) -> int:
        material = (
            self.source_port.to_bytes(2, "big")
            + self.destination_port.to_bytes(2, "big")
            + self.payload
        )
        return zlib.crc32(material) & 0xFFFFFFFF

    def finalize(self) -> None:
        self.checksum = self.calculate_checksum()

    def verify(self) -> bool:
        return self.checksum == self.calculate_checksum()


def transport_layer_demo() -> None:
    subsection("Layer 4 — Transport Layer")

    tcp_segment = TransportSegment(
        source_port=51500,
        destination_port=443,
        payload=b"GET / HTTP/1.1",
        protocol=TransportProtocol.TCP,
        sequence_number=1000,
        flags=["SYN"],
    )
    tcp_segment.finalize()

    print("TCP segment:", tcp_segment)
    print("Checksum valid:", tcp_segment.verify())

    tcp_segment.payload = b"tampered"
    print("After payload modification:", tcp_segment.verify())

    udp_segment = TransportSegment(
        source_port=53000,
        destination_port=53,
        payload=b"DNS QUERY",
        protocol=TransportProtocol.UDP,
    )
    udp_segment.finalize()

    print("\nUDP datagram:", udp_segment)
    print("UDP checksum simulation valid:", udp_segment.verify())

    print("\nTCP characteristics:")
    print("- connection-oriented")
    print("- ordered byte stream")
    print("- retransmission")
    print("- flow control")
    print("- congestion control")
    print("- reliability")

    print("\nUDP characteristics:")
    print("- connectionless at the transport abstraction")
    print("- message-oriented datagrams")
    print("- low protocol overhead")
    print("- no TCP-style delivery guarantee")


# ============================================================================
# SECTION 6 — TCP THREE-WAY HANDSHAKE
# ============================================================================

@dataclass
class TCPEndpoint:
    name: str
    initial_sequence: int
    state: str = "CLOSED"

    def syn(self) -> Dict[str, Any]:
        self.state = "SYN-SENT"
        return {
            "SYN": 1,
            "SEQ": self.initial_sequence,
            "ACK": 0,
        }

    def syn_ack(self, received_sequence: int) -> Dict[str, Any]:
        self.state = "SYN-RECEIVED"
        return {
            "SYN": 1,
            "ACK": 1,
            "SEQ": self.initial_sequence,
            "ACK_NUMBER": received_sequence + 1,
        }

    def ack(self, received_sequence: int) -> Dict[str, Any]:
        self.state = "ESTABLISHED"
        return {
            "SYN": 0,
            "ACK": 1,
            "ACK_NUMBER": received_sequence + 1,
        }


def tcp_handshake_demo() -> None:
    subsection("TCP Three-Way Handshake Simulation")

    client = TCPEndpoint("Client", 10000)
    server = TCPEndpoint("Server", 50000)

    first = client.syn()
    print("1. Client -> Server:", first)

    second = server.syn_ack(first["SEQ"])
    print("2. Server -> Client:", second)

    third = client.ack(second["SEQ"])
    print("3. Client -> Server:", third)

    server.state = "ESTABLISHED"

    print("Client state:", client.state)
    print("Server state:", server.state)


# ============================================================================
# SECTION 7 — LAYER 3: NETWORK
# ============================================================================

@dataclass
class IPv4Packet:
    source_ip: str
    destination_ip: str
    ttl: int
    protocol: str
    payload: bytes

    def validate(self) -> None:
        ipaddress.IPv4Address(self.source_ip)
        ipaddress.IPv4Address(self.destination_ip)

        if not 0 <= self.ttl <= 255:
            raise ValueError("TTL must be between 0 and 255.")


def network_layer_demo() -> None:
    subsection("Layer 3 — Network Layer")

    packet = IPv4Packet(
        source_ip="192.168.1.10",
        destination_ip="8.8.8.8",
        ttl=64,
        protocol="TCP",
        payload=b"transport segment",
    )

    packet.validate()

    print("Source IP:", packet.source_ip)
    print("Destination IP:", packet.destination_ip)
    print("TTL:", packet.ttl)
    print("Protocol:", packet.protocol)

    packet.ttl -= 1
    print("TTL after one router hop:", packet.ttl)

    print("\nLayer 3 responsibilities include:")
    print("- logical addressing")
    print("- routing")
    print("- forwarding")
    print("- packet lifetime control")
    print("- inter-network communication")


# ============================================================================
# SECTION 8 — SUBNETTING
# ============================================================================

def subnet_demo() -> None:
    subsection("IPv4 Addressing and Subnetting")

    networks = [
        ipaddress.ip_network("192.168.1.0/24"),
        ipaddress.ip_network("10.0.0.0/16"),
        ipaddress.ip_network("172.16.10.0/28"),
    ]

    for network in networks:
        print(
            f"{network}: "
            f"prefix={network.prefixlen}, "
            f"addresses={network.num_addresses}, "
            f"network={network.network_address}, "
            f"broadcast={network.broadcast_address}"
        )

    host_a = ipaddress.ip_address("192.168.1.10")
    host_b = ipaddress.ip_address("192.168.1.200")
    network = ipaddress.ip_network("192.168.1.0/24")

    print("\nHost A belongs to network:", host_a in network)
    print("Host B belongs to network:", host_b in network)

    different_network = ipaddress.ip_network("192.168.2.0/24")
    print("Host A belongs to another subnet:", host_a in different_network)


# ============================================================================
# SECTION 9 — ROUTING
# ============================================================================

@dataclass
class Route:
    network: ipaddress.IPv4Network
    next_hop: str
    interface: str
    metric: int


class RoutingTable:
    def __init__(self, routes: Optional[List[Route]] = None) -> None:
        self.routes = routes or []

    def add_route(self, route: Route) -> None:
        self.routes.append(route)

    def lookup(self, destination: str) -> Optional[Route]:
        address = ipaddress.ip_address(destination)
        matching = [
            route
            for route in self.routes
            if address in route.network
        ]

        if not matching:
            return None

        # Longest-prefix matching is a fundamental routing concept.
        return max(
            matching,
            key=lambda route: (route.network.prefixlen, -route.metric),
        )


def routing_demo() -> None:
    subsection("Routing Table and Longest Prefix Match")

    table = RoutingTable([
        Route(
            ipaddress.ip_network("0.0.0.0/0"),
            "192.168.1.1",
            "eth0",
            100,
        ),
        Route(
            ipaddress.ip_network("10.0.0.0/8"),
            "192.168.1.254",
            "eth1",
            20,
        ),
        Route(
            ipaddress.ip_network("10.10.0.0/16"),
            "192.168.1.253",
            "eth2",
            10,
        ),
    ])

    for destination in [
        "10.10.5.20",
        "10.20.1.10",
        "8.8.8.8",
    ]:
        route = table.lookup(destination)
        print(
            f"{destination} -> "
            f"{route.network if route else 'NO ROUTE'} -> "
            f"{route.next_hop if route else 'DROP'}"
        )


# ============================================================================
# SECTION 10 — LAYER 2: DATA LINK
# ============================================================================

@dataclass
class EthernetFrame:
    destination_mac: str
    source_mac: str
    ether_type: int
    payload: bytes
    frame_check_sequence: Optional[int] = None

    def calculate_fcs(self) -> int:
        header = (
            self.destination_mac.encode()
            + self.source_mac.encode()
            + self.ether_type.to_bytes(2, "big")
        )
        return zlib.crc32(header + self.payload) & 0xFFFFFFFF

    def finalize(self) -> None:
        self.frame_check_sequence = self.calculate_fcs()

    def verify(self) -> bool:
        return self.frame_check_sequence == self.calculate_fcs()


def data_link_demo() -> None:
    subsection("Layer 2 — Data Link Layer")

    frame = EthernetFrame(
        destination_mac="AA:BB:CC:DD:EE:FF",
        source_mac="11:22:33:44:55:66",
        ether_type=0x0800,
        payload=b"IPv4 packet",
    )

    frame.finalize()

    print("Destination MAC:", frame.destination_mac)
    print("Source MAC:", frame.source_mac)
    print("EtherType:", hex(frame.ether_type))
    print("FCS:", frame.frame_check_sequence)
    print("Frame valid:", frame.verify())

    print("\nLayer 2 concepts:")
    print("- MAC addressing")
    print("- framing")
    print("- local delivery")
    print("- error detection")
    print("- switching")
    print("- VLAN segmentation")


# ============================================================================
# SECTION 11 — ARP CONCEPT
# ============================================================================

@dataclass
class ARPEntry:
    ip_address: str
    mac_address: str
    expires_at: float


class ARPCache:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds
        self.entries: Dict[str, ARPEntry] = {}

    def learn(self, ip_address: str, mac_address: str) -> None:
        self.entries[ip_address] = ARPEntry(
            ip_address,
            mac_address,
            time.time() + self.ttl_seconds,
        )

    def lookup(self, ip_address: str) -> Optional[str]:
        entry = self.entries.get(ip_address)

        if entry is None:
            return None

        if time.time() >= entry.expires_at:
            del self.entries[ip_address]
            return None

        return entry.mac_address


def arp_demo() -> None:
    subsection("ARP — Connecting Layer 3 and Layer 2")

    cache = ARPCache(ttl_seconds=60)

    cache.learn(
        "192.168.1.20",
        "AA:AA:AA:AA:AA:20",
    )

    print("MAC for 192.168.1.20:", cache.lookup("192.168.1.20"))
    print("MAC for unknown host:", cache.lookup("192.168.1.99"))

    print("\nARP resolves an IPv4 address to a MAC address on a local network.")
    print("ARP is commonly associated with Layer 2, although its role bridges")
    print("the logical addressing of Layer 3 and hardware addressing of Layer 2.")


# ============================================================================
# SECTION 12 — LAYER 1: PHYSICAL
# ============================================================================

@dataclass
class PhysicalSignal:
    medium: str
    bitrate: int
    voltage_or_signal_level: float
    bits: str


def physical_layer_demo() -> None:
    subsection("Layer 1 — Physical Layer")

    signal = PhysicalSignal(
        medium="fiber",
        bitrate=10_000_000_000,
        voltage_or_signal_level=1.0,
        bits="101100101",
    )

    print("Medium:", signal.medium)
    print("Bit rate:", signal.bitrate, "bits/second")
    print("Signal level:", signal.voltage_or_signal_level)
    print("Bits:", signal.bits)

    print("\nPhysical-layer concerns:")
    print("- connectors")
    print("- cables")
    print("- radio frequencies")
    print("- optical signals")
    print("- electrical characteristics")
    print("- modulation")
    print("- signal timing")
    print("- bit transmission")


# ============================================================================
# SECTION 13 — ENCAPSULATION
# ============================================================================

@dataclass
class Encapsulation:
    application_data: bytes
    transport_header: bytes = b""
    network_header: bytes = b""
    data_link_header: bytes = b""
    data_link_trailer: bytes = b""

    def build_transport(self) -> bytes:
        return self.transport_header + self.application_data

    def build_network(self) -> bytes:
        return self.network_header + self.build_transport()

    def build_frame(self) -> bytes:
        return (
            self.data_link_header
            + self.build_network()
            + self.data_link_trailer
        )


def encapsulation_demo() -> None:
    subsection("Encapsulation and Decapsulation")

    data = b"HELLO"

    packet = Encapsulation(
        application_data=data,
        transport_header=b"[TCP HEADER]",
        network_header=b"[IP HEADER]",
        data_link_header=b"[ETH HEADER]",
        data_link_trailer=b"[FCS]",
    )

    transport = packet.build_transport()
    network = packet.build_network()
    frame = packet.build_frame()

    print("Application data:", data)
    print("After transport:", transport)
    print("After network:", network)
    print("After data link:", frame)

    print("\nConceptual encapsulation:")
    print("Data")
    print("  -> TCP segment")
    print("      -> IP packet")
    print("          -> Ethernet frame")
    print("              -> physical signals")


# ============================================================================
# SECTION 14 — FULL END-TO-END SIMULATION
# ============================================================================

@dataclass
class NetworkHost:
    hostname: str
    ip: str
    mac: str


@dataclass
class SimulatedNetwork:
    client: NetworkHost
    router: NetworkHost
    server: NetworkHost
    routing_table: RoutingTable
    arp_cache: ARPCache

    def send(self, message: str) -> None:
        print("\n--- END-TO-END TRANSMISSION ---")

        print(f"Application: {self.client.hostname} sends {message!r}")

        application_data = message.encode("utf-8")

        transport = TransportSegment(
            source_port=51500,
            destination_port=443,
            payload=application_data,
            protocol=TransportProtocol.TCP,
            sequence_number=1,
            flags=["ACK"],
        )
        transport.finalize()

        print("Layer 4: TCP segment created.")

        route = self.routing_table.lookup(self.server.ip)

        if route is None:
            raise RuntimeError("No route to destination.")

        print(
            f"Layer 3: route selected via {route.next_hop} "
            f"on {route.interface}."
        )

        packet = IPv4Packet(
            source_ip=self.client.ip,
            destination_ip=self.server.ip,
            ttl=64,
            protocol="TCP",
            payload=application_data,
        )

        packet.validate()

        print(
            f"Layer 3: IP packet {packet.source_ip} -> "
            f"{packet.destination_ip}, TTL={packet.ttl}"
        )

        destination_mac = self.arp_cache.lookup(self.router.ip)

        if destination_mac is None:
            raise RuntimeError(
                "ARP cache miss: an ARP request would be required."
            )

        frame = EthernetFrame(
            destination_mac=destination_mac,
            source_mac=self.client.mac,
            ether_type=0x0800,
            payload=packet.payload,
        )
        frame.finalize()

        print(
            f"Layer 2: Ethernet frame "
            f"{frame.source_mac} -> {frame.destination_mac}"
        )
        print("Layer 1: frame converted into physical signals.")
        print("Network transmission complete.")


def end_to_end_demo() -> None:
    subsection("Complete End-to-End OSI Simulation")

    client = NetworkHost(
        hostname="client",
        ip="192.168.1.10",
        mac="11:22:33:44:55:66",
    )

    router = NetworkHost(
        hostname="router",
        ip="192.168.1.1",
        mac="AA:BB:CC:DD:EE:01",
    )

    server = NetworkHost(
        hostname="server",
        ip="10.10.10.20",
        mac="AA:BB:CC:DD:EE:20",
    )

    routing_table = RoutingTable([
        Route(
            ipaddress.ip_network("10.10.0.0/16"),
            "192.168.1.1",
            "eth0",
            10,
        ),
        Route(
            ipaddress.ip_network("0.0.0.0/0"),
            "192.168.1.1",
            "eth0",
            100,
        ),
    ])

    arp_cache = ARPCache()
    arp_cache.learn(router.ip, router.mac)

    network = SimulatedNetwork(
        client=client,
        router=router,
        server=server,
        routing_table=routing_table,
        arp_cache=arp_cache,
    )

    network.send("Hello from the client")


# ============================================================================
# SECTION 15 — DNS CONCEPT
# ============================================================================

def dns_demo() -> None:
    subsection("DNS — Application-Layer Name Resolution")

    domain = "example.com"

    try:
        addresses = socket.getaddrinfo(
            domain,
            443,
            type=socket.SOCK_STREAM,
        )

        unique_addresses = sorted(
            {
                result[4][0]
                for result in addresses
            }
        )

        print(f"Resolved {domain}:")
        for address in unique_addresses:
            print(" ", address)

    except socket.gaierror as error:
        print("DNS resolution failed:", error)

    print("\nDNS translates human-readable names into network addresses.")
    print("DNS itself uses application-level messages transported over a network.")


# ============================================================================
# SECTION 16 — PORTS AND SOCKETS
# ============================================================================

def port_demo() -> None:
    subsection("Ports, Sockets, and Process Delivery")

    examples = [
        ("HTTP", 80),
        ("HTTPS", 443),
        ("DNS", 53),
        ("SSH", 22),
        ("SMTP", 25),
    ]

    for protocol, port in examples:
        print(f"{protocol:<8} -> port {port}")

    print(
        "\nAn IP address identifies a network endpoint at Layer 3; "
        "a transport port identifies an application endpoint within "
        "that host's transport namespace."
    )


# ============================================================================
# SECTION 17 — ERROR DETECTION
# ============================================================================

def error_detection_demo() -> None:
    subsection("Error Detection")

    data = b"network frame payload"
    checksum = zlib.crc32(data) & 0xFFFFFFFF

    print("Original CRC:", checksum)
    print("Verification:", (zlib.crc32(data) & 0xFFFFFFFF) == checksum)

    damaged = data[:-1] + bytes([data[-1] ^ 0xFF])

    print("Damaged CRC:", zlib.crc32(damaged) & 0xFFFFFFFF)
    print(
        "Damaged frame accepted:",
        (zlib.crc32(damaged) & 0xFFFFFFFF) == checksum,
    )

    print(
        "\nChecksums and CRCs help detect corruption. "
        "Detection is not the same as correction."
    )


# ============================================================================
# SECTION 18 — LATENCY AND THROUGHPUT
# ============================================================================

def performance_demo() -> None:
    subsection("Latency, Bandwidth, Throughput, and Serialization")

    payload_size_bytes = 1_000_000
    bandwidth_bits_per_second = 100_000_000
    propagation_delay_seconds = 0.020

    serialization_delay = (
        payload_size_bytes * 8
    ) / bandwidth_bits_per_second

    total_one_way_estimate = (
        serialization_delay
        + propagation_delay_seconds
    )

    print("Payload:", payload_size_bytes, "bytes")
    print("Bandwidth:", bandwidth_bits_per_second, "bits/s")
    print("Serialization delay:", serialization_delay, "seconds")
    print("Propagation delay:", propagation_delay_seconds, "seconds")
    print("Estimated one-way time:", total_one_way_estimate, "seconds")

    print("\nBandwidth is capacity.")
    print("Throughput is achieved data transfer rate.")
    print("Latency is delay.")
    print("High bandwidth does not automatically imply low latency.")


# ============================================================================
# SECTION 19 — SECURITY MAPPING
# ============================================================================

def security_demo() -> None:
    subsection("Security Considerations Across OSI Layers")

    security_controls = {
        7: [
            "authentication",
            "authorization",
            "input validation",
            "HTTP security headers",
        ],
        6: [
            "secure encoding handling",
            "cryptographic representation",
            "certificate validation",
        ],
        5: [
            "session expiration",
            "session identifiers",
            "session fixation protection",
        ],
        4: [
            "stateful firewalling",
            "port filtering",
            "connection exhaustion protection",
        ],
        3: [
            "ACLs",
            "routing controls",
            "IP filtering",
            "IPsec",
        ],
        2: [
            "VLAN segmentation",
            "MAC filtering",
            "802.1X",
        ],
        1: [
            "physical access control",
            "cable security",
            "radio isolation",
        ],
    }

    for layer in range(7, 0, -1):
        print(
            f"Layer {layer} {OSI_LAYERS[layer]}: "
            + ", ".join(security_controls[layer])
        )

    print(
        "\nSecurity is not restricted to one OSI layer. "
        "Real systems use controls across multiple layers."
    )


# ============================================================================
# SECTION 20 — TROUBLESHOOTING METHODOLOGY
# ============================================================================

def troubleshooting_demo() -> None:
    subsection("OSI-Based Troubleshooting")

    cases = [
        ("No link light", 1, "Inspect cable, interface, transceiver, power."),
        ("Wrong VLAN", 2, "Inspect switch port and VLAN configuration."),
        ("ARP failure", 2, "Inspect local addressing and ARP behavior."),
        ("No route", 3, "Inspect IP configuration and routing table."),
        ("Port blocked", 4, "Inspect firewall and transport port."),
        ("TLS failure", 6, "Inspect certificates, versions, and cryptography."),
        ("HTTP 404", 7, "Inspect application resource and server behavior."),
    ]

    for symptom, layer, action in cases:
        print(
            f"{symptom:<20} | "
            f"Layer {layer} {OSI_LAYERS[layer]:<15} | "
            f"{action}"
        )

    print(
        "\nThe OSI model is useful as a troubleshooting framework, "
        "but actual faults can cross multiple layers."
    )


# ============================================================================
# SECTION 21 — COMMON MISCONCEPTIONS
# ============================================================================

def misconception_demo() -> None:
    subsection("Common Misconceptions")

    misconceptions = [
        (
            "Every real protocol belongs to exactly one OSI layer.",
            "False. Real protocols can span or interact with multiple conceptual layers."
        ),
        (
            "The Internet literally implements seven independent layers.",
            "False. The OSI model is primarily a reference model."
        ),
        (
            "Routers use MAC addresses to route between networks.",
            "Routers make Layer 3 forwarding decisions; Layer 2 framing is still used on each local link."
        ),
        (
            "A switch and router do exactly the same thing.",
            "False. A switch commonly forwards frames within a Layer 2 domain; a router forwards packets between Layer 3 networks."
        ),
        (
            "TCP guarantees that an application request succeeded.",
            "False. TCP reliability concerns delivery of the byte stream, not application-level success."
        ),
        (
            "HTTPS is simply HTTP at Layer 4.",
            "False. HTTPS is HTTP carried through a secure TLS-enabled transport path."
        ),
    ]

    for claim, correction in misconceptions:
        print("\nClaim:", claim)
        print("Correction:", correction)


# ============================================================================
# SECTION 22 — ADVANCED TCP CONCEPTS
# ============================================================================

@dataclass
class TCPFlow:
    congestion_window: int
    slow_start_threshold: int
    receiver_window: int
    retransmission_timeout: float

    @property
    def effective_window(self) -> int:
        return min(self.congestion_window, self.receiver_window)

    def acknowledge(self, amount: int) -> None:
        self.congestion_window += amount

    def timeout(self) -> None:
        self.slow_start_threshold = max(
            2,
            self.congestion_window // 2,
        )
        self.congestion_window = 1


def tcp_flow_control_demo() -> None:
    subsection("Advanced TCP Concepts")

    flow = TCPFlow(
        congestion_window=10,
        slow_start_threshold=64,
        receiver_window=20,
        retransmission_timeout=0.5,
    )

    print("Initial effective window:", flow.effective_window)

    flow.acknowledge(5)
    print("After acknowledgments:", flow.effective_window)

    flow.timeout()
    print("After timeout:")
    print("  congestion window:", flow.congestion_window)
    print("  slow-start threshold:", flow.slow_start_threshold)

    print(
        "\nReal TCP congestion control is significantly more complex "
        "than this educational model."
    )


# ============================================================================
# SECTION 23 — IPv6
# ============================================================================

def ipv6_demo() -> None:
    subsection("IPv6")

    addresses = [
        "2001:db8::1",
        "::1",
        "fe80::abcd",
    ]

    for address in addresses:
        parsed = ipaddress.IPv6Address(address)
        print(
            f"{address:<20} compressed={parsed.compressed:<20} "
            f"exploded={parsed.exploded}"
        )

    network = ipaddress.ip_network("2001:db8:1234::/48")
    print("IPv6 network:", network)
    print("Prefix length:", network.prefixlen)

    print("\nIPv6 provides a much larger address space than IPv4.")
    print("IPv6 does not use ARP; Neighbor Discovery serves related functions.")


# ============================================================================
# SECTION 24 — VLAN CONCEPT
# ============================================================================

@dataclass
class VLANFrame:
    source_mac: str
    destination_mac: str
    vlan_id: int
    payload: bytes


def vlan_demo() -> None:
    subsection("VLAN Concept")

    frames = [
        VLANFrame(
            "AA:AA:AA:AA:AA:01",
            "BB:BB:BB:BB:BB:01",
            10,
            b"Finance data",
        ),
        VLANFrame(
            "AA:AA:AA:AA:AA:02",
            "BB:BB:BB:BB:BB:02",
            20,
            b"Engineering data",
        ),
    ]

    for frame in frames:
        print(
            f"VLAN {frame.vlan_id}: "
            f"{frame.source_mac} -> {frame.destination_mac}"
        )

    print(
        "\nVLANs allow logical Layer 2 segmentation over shared switching infrastructure."
    )


# ============================================================================
# SECTION 25 — DATA VALIDATION AND EDGE CASES
# ============================================================================

def validation_demo() -> None:
    subsection("Validation and Edge Cases")

    tests = [
        "192.168.1.1",
        "192.168.1.999",
        "10.0.0.1",
        "not-an-ip",
        "::1",
    ]

    for value in tests:
        try:
            parsed = ipaddress.ip_address(value)
            print(f"{value:<18} VALID -> {parsed.version=}")
        except ValueError:
            print(f"{value:<18} INVALID")

    print("\nTTL edge cases:")
    for ttl in [0, 1, 64, 255, 256, -1]:
        try:
            if not 0 <= ttl <= 255:
                raise ValueError("TTL outside IPv4 field range")
            print(f"TTL {ttl}: valid")
        except ValueError as error:
            print(f"TTL {ttl}: invalid ({error})")


# ============================================================================
# SECTION 26 — PERFORMANCE OF ROUTING LOOKUPS
# ============================================================================

def routing_benchmark_demo() -> None:
    subsection("Routing Lookup Complexity")

    table = RoutingTable()

    for prefix in range(8, 25):
        network = ipaddress.ip_network(f"10.{prefix}.0.0/16", strict=False)
        table.add_route(
            Route(
                network=network,
                next_hop="192.168.1.1",
                interface="eth0",
                metric=10,
            )
        )

    destination = "10.10.5.20"

    start = time.perf_counter()

    for _ in range(10_000):
        table.lookup(destination)

    elapsed = time.perf_counter() - start

    print("10,000 routing lookups:", elapsed, "seconds")
    print(
        "\nThis educational routing table performs a linear scan. "
        "Production routers use highly optimized lookup structures and hardware."
    )


# ============================================================================
# SECTION 27 — HASHING AND DATA INTEGRITY
# ============================================================================

def hashing_demo() -> None:
    subsection("Hashing for Integrity")

    message = b"network packet payload"

    digest = hashlib.sha256(message).hexdigest()

    print("SHA-256:", digest)

    modified = message + b"!"
    modified_digest = hashlib.sha256(modified).hexdigest()

    print("Modified SHA-256:", modified_digest)
    print("Hashes equal:", digest == modified_digest)

    print(
        "\nA cryptographic hash detects changes with strong collision-resistance "
        "properties, but a hash alone does not authenticate who produced the data."
    )


# ============================================================================
# SECTION 28 — LAYER COMPARISON
# ============================================================================

def comparison_demo() -> None:
    subsection("Layer-by-Layer Comparison")

    rows = [
        (7, "Application", "HTTP/DNS/SMTP", "Data", "Application services"),
        (6, "Presentation", "TLS/UTF-8/JSON", "Data", "Representation"),
        (5, "Session", "Session/RPC", "Data", "Dialog/session"),
        (4, "Transport", "TCP/UDP", "Segment", "Process-to-process delivery"),
        (3, "Network", "IP/ICMP", "Packet", "Routing"),
        (2, "Data Link", "Ethernet/Wi-Fi", "Frame", "Local delivery"),
        (1, "Physical", "Fiber/copper/radio", "Bits", "Signals"),
    ]

    print(
        f"{'Layer':<7}{'Name':<17}{'Examples':<25}"
        f"{'PDU':<12}{'Primary role'}"
    )

    for row in rows:
        print(
            f"{row[0]:<7}{row[1]:<17}{row[2]:<25}"
            f"{row[3]:<12}{row[4]}"
        )


# ============================================================================
# SECTION 29 — MAIN STUDY PROGRAM
# ============================================================================

def main() -> None:
    print_osi_table()

    application_layer_demo()
    presentation_layer_demo()
    session_layer_demo()
    transport_layer_demo()
    tcp_handshake_demo()
    network_layer_demo()
    subnet_demo()
    routing_demo()
    data_link_demo()
    arp_demo()
    physical_layer_demo()
    encapsulation_demo()
    end_to_end_demo()
    dns_demo()
    port_demo()
    error_detection_demo()
    performance_demo()
    security_demo()
    troubleshooting_demo()
    misconception_demo()
    tcp_flow_control_demo()
    ipv6_demo()
    vlan_demo()
    validation_demo()
    routing_benchmark_demo()
    hashing_demo()
    comparison_demo()

    section("STUDY CHECKLIST")

    checklist = [
        "Identify all seven OSI layers in correct order.",
        "Explain the purpose of each layer.",
        "Identify common protocols associated with each layer.",
        "Distinguish MAC addresses from IP addresses.",
        "Distinguish ports from IP addresses.",
        "Explain encapsulation and decapsulation.",
        "Explain TCP versus UDP.",
        "Explain the TCP three-way handshake.",
        "Explain routing and longest-prefix matching.",
        "Explain Ethernet framing.",
        "Explain ARP and IPv6 Neighbor Discovery conceptually.",
        "Explain VLAN segmentation.",
        "Distinguish bandwidth, throughput, and latency.",
        "Map common troubleshooting symptoms to likely layers.",
        "Recognize that the OSI model is conceptual rather than a literal implementation blueprint.",
    ]

    for index, item in enumerate(checklist, start=1):
        print(f"{index:02d}. {item}")

    section("END OF OSI MODEL STUDY PROGRAM")
    print(
        "The examples above intentionally use simplified models where "
        "real network stacks are substantially more complex."
    )


if __name__ == "__main__":
    main()
