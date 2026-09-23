"""
TCP/IP MODEL: A COMPREHENSIVE STUDY SCRIPT

This standalone program teaches the four-layer TCP/IP model:

    Application
    Transport
    Internet
    Network Access

The demonstrations are intentionally self-contained and use only Python's
standard library. They model protocol behavior where direct access to the
operating system's network stack would make the lesson harder to understand,
while also showing real socket-based TCP and UDP examples.

The program is organized from fundamentals to progressively more advanced
networking concepts.

Run:
    python tcp_ip_model.py
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import random
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


# ============================================================================
# 1. BASIC TCP/IP MODEL CONCEPTS
# ============================================================================

class Layer(Enum):
    APPLICATION = "Application"
    TRANSPORT = "Transport"
    INTERNET = "Internet"
    NETWORK_ACCESS = "Network Access"


LAYER_PURPOSES = {
    Layer.APPLICATION: (
        "Provides network services directly to applications. "
        "Examples include HTTP, DNS, SMTP, SSH, and DHCP."
    ),
    Layer.TRANSPORT: (
        "Provides end-to-end communication between processes. "
        "TCP and UDP operate here."
    ),
    Layer.INTERNET: (
        "Provides logical addressing and routing between networks. "
        "IP, ICMP, and related protocols operate here."
    ),
    Layer.NETWORK_ACCESS: (
        "Moves frames across the local network medium. "
        "Ethernet, Wi-Fi, ARP, and link-layer technologies belong here."
    ),
}


def print_model() -> None:
    print("\nTCP/IP MODEL")
    print("=" * 72)

    for layer in Layer:
        print(f"{layer.value:18} | {LAYER_PURPOSES[layer]}")

    print("\nTypical encapsulation:")
    print("Application data")
    print("    ↓")
    print("Transport segment/datagram")
    print("    ↓")
    print("IP packet")
    print("    ↓")
    print("Link-layer frame")
    print("    ↓")
    print("Physical transmission")


# ============================================================================
# 2. TERMINOLOGY
# ============================================================================

def explain_terminology() -> None:
    terminology = {
        "Host": "A device participating in network communication.",
        "Client": "A program that initiates a service request.",
        "Server": "A program that listens for and responds to requests.",
        "Protocol": "A defined set of communication rules.",
        "Socket": "An operating-system interface representing a network endpoint.",
        "IP address": "A logical address used for communication across networks.",
        "Port": "A transport-layer identifier for a process or service.",
        "MAC address": "A link-layer hardware/network-interface identifier.",
        "Packet": "A common name for an IP-layer unit of data.",
        "Segment": "A TCP transport-layer data unit.",
        "Datagram": "A connectionless transport unit, commonly associated with UDP.",
        "Frame": "A network-access-layer unit containing link-layer information.",
        "Encapsulation": "Adding protocol metadata as data moves down the stack.",
        "Decapsulation": "Removing protocol metadata as data moves up the stack.",
        "Routing": "Selecting a path between IP networks.",
        "Switching": "Forwarding frames within a local link.",
        "MTU": "Maximum Transmission Unit supported by a link.",
        "DNS": "Maps domain names to information such as IP addresses.",
    }

    print("\nIMPORTANT TERMINOLOGY")
    print("=" * 72)

    for name, definition in terminology.items():
        print(f"{name:18} : {definition}")


# ============================================================================
# 3. APPLICATION-LAYER EXAMPLE
# ============================================================================

class SimpleHttpRequest:
    """A minimal representation of an HTTP request."""

    def __init__(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        body: str = "",
    ) -> None:
        self.method = method.upper()
        self.path = path
        self.headers = headers or {}
        self.body = body

    def serialize(self) -> str:
        lines = [f"{self.method} {self.path} HTTP/1.1"]

        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")

        lines.append("")
        lines.append(self.body)

        return "\r\n".join(lines)


class SimpleHttpResponse:
    """A minimal HTTP response parser."""

    def __init__(
        self,
        status_code: int,
        reason: str,
        headers: dict[str, str],
        body: str,
    ) -> None:
        self.status_code = status_code
        self.reason = reason
        self.headers = headers
        self.body = body

    def serialize(self) -> str:
        lines = [f"HTTP/1.1 {self.status_code} {self.reason}"]

        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")

        lines.append("")
        lines.append(self.body)

        return "\r\n".join(lines)


def application_layer_demo() -> None:
    request = SimpleHttpRequest(
        method="GET",
        path="/students?course=networking",
        headers={
            "Host": "example.test",
            "Accept": "application/json",
            "Connection": "close",
        },
    )

    print("\nAPPLICATION LAYER")
    print("=" * 72)
    print(request.serialize())

    response_body = json.dumps(
        {
            "course": "TCP/IP",
            "status": "available",
            "students": 42,
        }
    )

    response = SimpleHttpResponse(
        status_code=200,
        reason="OK",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(response_body.encode())),
        },
        body=response_body,
    )

    print("\nServer response:")
    print(response.serialize())


# ============================================================================
# 4. DNS CONCEPT DEMONSTRATION
# ============================================================================

def dns_demo() -> None:
    print("\nDNS DEMONSTRATION")
    print("=" * 72)

    hostnames = ["localhost", "example.com"]

    for hostname in hostnames:
        try:
            addresses = socket.getaddrinfo(
                hostname,
                None,
                type=socket.SOCK_STREAM,
            )

            unique_addresses = sorted(
                {
                    result[4][0]
                    for result in addresses
                    if result[4]
                }
            )

            print(f"{hostname:20} -> {unique_addresses}")

        except socket.gaierror as error:
            print(f"{hostname:20} -> DNS resolution failed: {error}")


# ============================================================================
# 5. TRANSPORT LAYER: PORTS AND SOCKETS
# ============================================================================

def explain_ports() -> None:
    examples = {
        20: "FTP data",
        21: "FTP control",
        22: "SSH",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        123: "NTP",
        443: "HTTPS",
        3306: "Common MySQL port",
        5432: "Common PostgreSQL port",
    }

    print("\nCOMMON TRANSPORT PORT EXAMPLES")
    print("=" * 72)

    for port, service in examples.items():
        print(f"{port:5} -> {service}")


def demonstrate_socket_addresses() -> None:
    print("\nSOCKET ADDRESS CONCEPT")
    print("=" * 72)

    server_address = ("192.0.2.10", 443)
    client_address = ("198.51.100.20", 53000)

    print(f"Server endpoint: {server_address[0]}:{server_address[1]}")
    print(f"Client endpoint: {client_address[0]}:{client_address[1]}")
    print(
        "A transport conversation can distinguish processes using "
        "IP addresses and port numbers."
    )


# ============================================================================
# 6. TCP CHARACTERISTICS
# ============================================================================

@dataclass
class TcpSegment:
    sequence_number: int
    acknowledgment_number: int
    syn: bool = False
    ack: bool = False
    fin: bool = False
    rst: bool = False
    payload: bytes = b""

    @property
    def payload_length(self) -> int:
        return len(self.payload)

    def describe(self) -> str:
        flags = []

        if self.syn:
            flags.append("SYN")
        if self.ack:
            flags.append("ACK")
        if self.fin:
            flags.append("FIN")
        if self.rst:
            flags.append("RST")

        return (
            f"seq={self.sequence_number}, "
            f"ack={self.acknowledgment_number}, "
            f"flags={','.join(flags) or '-'}, "
            f"payload={self.payload_length} bytes"
        )


def tcp_three_way_handshake() -> list[TcpSegment]:
    initial_client_sequence = 1000
    initial_server_sequence = 7000

    syn = TcpSegment(
        sequence_number=initial_client_sequence,
        acknowledgment_number=0,
        syn=True,
    )

    syn_ack = TcpSegment(
        sequence_number=initial_server_sequence,
        acknowledgment_number=initial_client_sequence + 1,
        syn=True,
        ack=True,
    )

    ack = TcpSegment(
        sequence_number=initial_client_sequence + 1,
        acknowledgment_number=initial_server_sequence + 1,
        ack=True,
    )

    return [syn, syn_ack, ack]


def tcp_handshake_demo() -> None:
    print("\nTCP THREE-WAY HANDSHAKE")
    print("=" * 72)

    steps = tcp_three_way_handshake()

    print("1. Client -> Server :", steps[0].describe())
    print("2. Server -> Client :", steps[1].describe())
    print("3. Client -> Server :", steps[2].describe())

    print(
        "\nThe handshake establishes initial sequence-number state and "
        "confirms that both endpoints can communicate."
    )


# ============================================================================
# 7. TCP RELIABILITY MODEL
# ============================================================================

@dataclass
class ReliableChannel:
    next_sequence_number: int = 0
    received: bytearray = field(default_factory=bytearray)

    def send(self, data: bytes) -> TcpSegment:
        segment = TcpSegment(
            sequence_number=self.next_sequence_number,
            acknowledgment_number=0,
            ack=False,
            payload=data,
        )

        self.next_sequence_number += len(data)
        return segment

    def acknowledge(self, segment: TcpSegment) -> int:
        return segment.sequence_number + segment.payload_length

    def receive(self, segment: TcpSegment) -> None:
        self.received.extend(segment.payload)


def tcp_reliability_demo() -> None:
    print("\nTCP SEQUENCE AND ACKNOWLEDGMENT DEMONSTRATION")
    print("=" * 72)

    sender = ReliableChannel()

    messages = [
        b"TCP ",
        b"provides ",
        b"ordered ",
        b"delivery.",
    ]

    for message in messages:
        segment = sender.send(message)
        acknowledgment = sender.acknowledge(segment)
        print(
            f"Sent {message!r}: "
            f"SEQ={segment.sequence_number}, "
            f"ACK expected={acknowledgment}"
        )


# ============================================================================
# 8. UDP CHARACTERISTICS
# ============================================================================

@dataclass
class UdpDatagram:
    source_port: int
    destination_port: int
    payload: bytes

    def describe(self) -> str:
        return (
            f"{self.source_port} -> {self.destination_port}, "
            f"{len(self.payload)} bytes"
        )


def udp_demo() -> None:
    print("\nUDP DEMONSTRATION")
    print("=" * 72)

    datagrams = [
        UdpDatagram(50000, 53, b"DNS query"),
        UdpDatagram(50001, 123, b"NTP request"),
        UdpDatagram(50002, 9999, b"telemetry"),
    ]

    for datagram in datagrams:
        print(datagram.describe())

    print(
        "\nUDP does not establish a TCP-style connection and does not "
        "provide TCP's built-in reliable ordered byte-stream behavior."
    )


# ============================================================================
# 9. TCP VS UDP
# ============================================================================

def compare_tcp_udp() -> None:
    comparison = [
        ("Connection", "Connection-oriented", "Connectionless"),
        ("Reliability", "Built-in reliable delivery", "No built-in reliability"),
        ("Ordering", "Ordered byte stream", "Datagrams are independent"),
        ("Retransmission", "Supported by TCP", "Application must implement it if required"),
        ("Flow control", "Yes", "No TCP-style mechanism"),
        ("Congestion control", "Yes", "No TCP-style mechanism"),
        ("Typical uses", "HTTP, SSH, database connections", "DNS, streaming, telemetry, games"),
    ]

    print("\nTCP VS UDP")
    print("=" * 72)

    for property_name, tcp_value, udp_value in comparison:
        print(f"{property_name:16} | TCP: {tcp_value}")
        print(f"{'':16} | UDP: {udp_value}")
        print("-" * 72)


# ============================================================================
# 10. INTERNET LAYER: IPv4
# ============================================================================

def ipv4_demo() -> None:
    print("\nINTERNET LAYER: IPv4")
    print("=" * 72)

    addresses = [
        "192.168.1.10",
        "10.0.0.5",
        "172.16.20.30",
        "8.8.8.8",
        "127.0.0.1",
    ]

    for address in addresses:
        ip = ipaddress.ip_address(address)

        print(
            f"{address:16} "
            f"version={ip.version}, "
            f"private={ip.is_private}, "
            f"loopback={ip.is_loopback}"
        )


# ============================================================================
# 11. SUBNETTING
# ============================================================================

def subnet_demo() -> None:
    print("\nSUBNETTING")
    print("=" * 72)

    networks = [
        ipaddress.ip_network("192.168.1.0/24"),
        ipaddress.ip_network("10.10.0.0/16"),
        ipaddress.ip_network("172.16.10.0/28"),
    ]

    for network in networks:
        usable_hosts = max(network.num_addresses - 2, 0)

        print(
            f"{network} | "
            f"network={network.network_address} | "
            f"broadcast={network.broadcast_address} | "
            f"addresses={network.num_addresses} | "
            f"typical usable hosts={usable_hosts}"
        )

    print("\nSubnet /28 contains 16 total IPv4 addresses.")
    print("In a conventional IPv4 LAN, 14 are normally usable by hosts.")


# ============================================================================
# 12. CIDR LONGEST-PREFIX MATCH
# ============================================================================

@dataclass(frozen=True)
class Route:
    network: ipaddress.IPv4Network
    next_hop: str


class RoutingTable:
    def __init__(self, routes: Iterable[Route]) -> None:
        self.routes = list(routes)

    def lookup(self, destination: str) -> Route | None:
        ip = ipaddress.ip_address(destination)

        matching = [
            route
            for route in self.routes
            if ip in route.network
        ]

        if not matching:
            return None

        return max(
            matching,
            key=lambda route: route.network.prefixlen,
        )


def routing_demo() -> None:
    print("\nROUTING AND LONGEST-PREFIX MATCH")
    print("=" * 72)

    table = RoutingTable(
        [
            Route(ipaddress.ip_network("0.0.0.0/0"), "ISP"),
            Route(ipaddress.ip_network("10.0.0.0/8"), "Router-A"),
            Route(ipaddress.ip_network("10.20.0.0/16"), "Router-B"),
            Route(ipaddress.ip_network("10.20.30.0/24"), "Router-C"),
        ]
    )

    destinations = [
        "10.20.30.15",
        "10.20.99.15",
        "10.50.1.1",
        "8.8.8.8",
    ]

    for destination in destinations:
        route = table.lookup(destination)

        if route:
            print(
                f"{destination:15} -> "
                f"{route.network} via {route.next_hop}"
            )
        else:
            print(f"{destination:15} -> no route")


# ============================================================================
# 13. IPv4 HEADER CONCEPTS
# ============================================================================

def ipv4_header_demo() -> None:
    print("\nIPv4 HEADER CONCEPTS")
    print("=" * 72)

    fields = {
        "Version": "Identifies IPv4.",
        "IHL": "Header length.",
        "DSCP/ECN": "Traffic-classification and congestion-related signaling.",
        "Total Length": "Entire IP packet size.",
        "Identification": "Used in fragmentation/reassembly.",
        "Flags": "Includes fragmentation-related control bits.",
        "Fragment Offset": "Position of a fragment.",
        "TTL": "Limits packet lifetime across routers.",
        "Protocol": "Identifies the upper-layer protocol, such as TCP or UDP.",
        "Header Checksum": "IPv4 header integrity check.",
        "Source Address": "Origin IPv4 address.",
        "Destination Address": "Target IPv4 address.",
    }

    for field_name, purpose in fields.items():
        print(f"{field_name:20} : {purpose}")


# ============================================================================
# 14. TTL AND ROUTING LOOP CONCEPT
# ============================================================================

def ttl_simulation(initial_ttl: int, hops: int) -> str:
    if initial_ttl <= 0:
        return "Packet is already expired."

    remaining = initial_ttl

    for _ in range(hops):
        remaining -= 1

        if remaining <= 0:
            return "TTL expired; router would discard the packet."

    return f"Packet survived {hops} hops with TTL={remaining}."


def ttl_demo() -> None:
    print("\nTTL SIMULATION")
    print("=" * 72)

    for ttl, hops in [(64, 5), (3, 3), (2, 5)]:
        print(f"TTL={ttl}, hops={hops} -> {ttl_simulation(ttl, hops)}")


# ============================================================================
# 15. ICMP CONCEPTS
# ============================================================================

def icmp_demo() -> None:
    print("\nICMP")
    print("=" * 72)

    messages = {
        "Echo Request": "Used by ping to request an echo response.",
        "Echo Reply": "Response to an echo request.",
        "Destination Unreachable": "Reports inability to deliver traffic.",
        "Time Exceeded": "Can occur when TTL reaches zero.",
        "Redirect": "Can communicate certain routing information.",
    }

    for message_type, explanation in messages.items():
        print(f"{message_type:25} : {explanation}")


# ============================================================================
# 16. NETWORK ACCESS LAYER
# ============================================================================

def mac_address_demo() -> None:
    print("\nNETWORK ACCESS LAYER")
    print("=" * 72)

    mac_addresses = [
        "00:11:22:33:44:55",
        "AA:BB:CC:DD:EE:FF",
        "02:42:AC:11:00:02",
    ]

    for mac in mac_addresses:
        octets = mac.split(":")
        valid = (
            len(octets) == 6
            and all(
                len(part) == 2
                and all(character in "0123456789abcdefABCDEF" for character in part)
                for part in octets
            )
        )

        print(f"{mac:20} valid={valid}")


# ============================================================================
# 17. ETHERNET FRAME CONCEPT
# ============================================================================

@dataclass
class EthernetFrame:
    destination_mac: str
    source_mac: str
    ether_type: int
    payload: bytes

    def describe(self) -> str:
        return (
            f"dst={self.destination_mac}, "
            f"src={self.source_mac}, "
            f"EtherType=0x{self.ether_type:04X}, "
            f"payload={len(self.payload)} bytes"
        )


def ethernet_demo() -> None:
    print("\nETHERNET FRAME")
    print("=" * 72)

    frame = EthernetFrame(
        destination_mac="AA:BB:CC:DD:EE:FF",
        source_mac="00:11:22:33:44:55",
        ether_type=0x0800,
        payload=b"IPv4 packet",
    )

    print(frame.describe())
    print("EtherType 0x0800 identifies IPv4.")


# ============================================================================
# 18. ARP CONCEPT
# ============================================================================

@dataclass
class ArpCache:
    entries: dict[str, str] = field(default_factory=dict)

    def add(self, ip_address: str, mac_address: str) -> None:
        self.entries[ip_address] = mac_address

    def lookup(self, ip_address: str) -> str | None:
        return self.entries.get(ip_address)


def arp_demo() -> None:
    print("\nARP CONCEPT")
    print("=" * 72)

    cache = ArpCache()

    cache.add("192.168.1.1", "AA:BB:CC:DD:EE:01")
    cache.add("192.168.1.20", "AA:BB:CC:DD:EE:20")

    target = "192.168.1.20"

    print(f"ARP cache lookup for {target}: {cache.lookup(target)}")
    print(
        "ARP associates IPv4 addresses with link-layer addresses "
        "on an IPv4 local network."
    )


# ============================================================================
# 19. ENCAPSULATION
# ============================================================================

@dataclass
class EncapsulatedData:
    application_data: bytes
    transport_header: bytes = b""
    ip_header: bytes = b""
    link_header: bytes = b""

    def encapsulate(self) -> bytes:
        transport_unit = self.transport_header + self.application_data
        ip_packet = self.ip_header + transport_unit
        frame = self.link_header + ip_packet
        return frame


def encapsulation_demo() -> None:
    print("\nENCAPSULATION AND DECAPSULATION")
    print("=" * 72)

    data = EncapsulatedData(
        application_data=b"Hello TCP/IP",
        transport_header=b"[TCP HEADER]",
        ip_header=b"[IPv4 HEADER]",
        link_header=b"[ETHERNET HEADER]",
    )

    frame = data.encapsulate()

    print(f"Application data : {data.application_data!r}")
    print(f"Transport unit   : {data.transport_header + data.application_data!r}")
    print(f"IP packet        : {data.ip_header + data.transport_header + data.application_data!r}")
    print(f"Frame            : {frame!r}")


# ============================================================================
# 20. MTU AND FRAGMENTATION CONCEPT
# ============================================================================

def fragmentation_demo() -> None:
    print("\nMTU CONCEPT")
    print("=" * 72)

    mtu = 1500
    ipv4_header_size = 20
    payload_size = 4000

    max_payload = mtu - ipv4_header_size
    fragments = math.ceil(payload_size / max_payload)

    print(f"MTU: {mtu} bytes")
    print(f"IPv4 header: {ipv4_header_size} bytes")
    print(f"Payload: {payload_size} bytes")
    print(f"Maximum payload per 1500-byte packet: {max_payload} bytes")
    print(f"Approximate number of packets: {fragments}")

    print(
        "\nModern networks often use Path MTU Discovery to avoid relying "
        "on fragmentation where possible."
    )


# ============================================================================
# 21. IPv6
# ============================================================================

def ipv6_demo() -> None:
    print("\nIPv6")
    print("=" * 72)

    addresses = [
        "2001:db8::1",
        "::1",
        "fe80::1234",
        "2001:4860:4860::8888",
    ]

    for address in addresses:
        ip = ipaddress.ip_address(address)

        print(
            f"{address:30} "
            f"version={ip.version}, "
            f"loopback={ip.is_loopback}, "
            f"link_local={ip.is_link_local}"
        )

    print(
        "\nIPv6 uses 128-bit addresses and has a redesigned header format. "
        "IPv4 and IPv6 are related Internet-layer protocols but are not "
        "address-format-compatible."
    )


# ============================================================================
# 22. REAL TCP SOCKET SERVER
# ============================================================================

def tcp_server_demo() -> None:
    """
    Demonstrates actual TCP sockets without requiring an external server.

    The server runs on localhost, receives one line, and sends a response.
    A short timeout prevents the educational example from hanging forever.
    """

    print("\nREAL TCP SOCKET DEMONSTRATION")
    print("=" * 72)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)

        host, port = server.getsockname()

        print(f"Server listening on {host}:{port}")

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            client.settimeout(2)
            client.connect((host, port))

            connection, address = server.accept()

            with connection:
                connection.settimeout(2)
                received = client.recv(1024)

                print(f"Server received: {received!r}")

                connection.sendall(b"TCP response")

            response = client.recv(1024)
            print(f"Client received: {response!r}")

        finally:
            client.close()

    except OSError as error:
        print(f"Socket demonstration failed: {error}")

    finally:
        server.close()


# ============================================================================
# 23. REAL UDP SOCKET DEMONSTRATION
# ============================================================================

def udp_socket_demo() -> None:
    print("\nREAL UDP SOCKET DEMONSTRATION")
    print("=" * 72)

    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        receiver.bind(("127.0.0.1", 0))
        host, port = receiver.getsockname()
        receiver.settimeout(2)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            sender.sendto(b"UDP message", (host, port))
            data, address = receiver.recvfrom(1024)

            print(f"Receiver got {data!r} from {address}")

        finally:
            sender.close()

    except OSError as error:
        print(f"UDP demonstration failed: {error}")

    finally:
        receiver.close()


# ============================================================================
# 24. CLIENT-SERVER APPLICATION ARCHITECTURE
# ============================================================================

@dataclass
class ApplicationMessage:
    message_type: str
    request_id: int
    payload: dict[str, Any]

    def encode(self) -> bytes:
        document = {
            "type": self.message_type,
            "request_id": self.request_id,
            "payload": self.payload,
        }

        return (json.dumps(document) + "\n").encode("utf-8")


def application_protocol_demo() -> None:
    print("\nAPPLICATION PROTOCOL OVER TCP")
    print("=" * 72)

    request = ApplicationMessage(
        message_type="GET_USER",
        request_id=101,
        payload={"user_id": 42},
    )

    response = ApplicationMessage(
        message_type="USER_RESULT",
        request_id=101,
        payload={
            "user_id": 42,
            "name": "Example User",
            "active": True,
        },
    )

    print("Request:")
    print(request.encode().decode().strip())

    print("\nResponse:")
    print(response.encode().decode().strip())

    print(
        "\nThe application protocol defines message meaning. "
        "TCP transports the resulting byte stream."
    )


# ============================================================================
# 25. TCP IS A STREAM, NOT A MESSAGE PROTOCOL
# ============================================================================

def tcp_stream_demo() -> None:
    print("\nTCP STREAM SEMANTICS")
    print("=" * 72)

    stream = b"HELLO|WORLD|TCP"

    chunks = [
        stream[:2],
        stream[2:8],
        stream[8:],
    ]

    print(f"Original application stream: {stream!r}")
    print("Possible recv() chunks:")

    for chunk in chunks:
        print(f"  {chunk!r}")

    print(
        "\nAn application must define framing when it needs message boundaries. "
        "Common approaches include length-prefix framing, delimiters, or "
        "structured formats with a framing strategy."
    )


# ============================================================================
# 26. LENGTH-PREFIXED APPLICATION PROTOCOL
# ============================================================================

def encode_length_prefixed(message: bytes) -> bytes:
    if len(message) > 2**32 - 1:
        raise ValueError("Message is too large for a 32-bit length prefix.")

    return struct.pack("!I", len(message)) + message


def decode_length_prefixed(buffer: bytearray) -> tuple[bytes | None, int]:
    if len(buffer) < 4:
        return None, 0

    length = struct.unpack("!I", buffer[:4])[0]

    if len(buffer) < 4 + length:
        return None, 0

    message = bytes(buffer[4:4 + length])
    return message, 4 + length


def framing_demo() -> None:
    print("\nAPPLICATION MESSAGE FRAMING")
    print("=" * 72)

    original = b"hello network"
    encoded = encode_length_prefixed(original)

    print(f"Encoded bytes: {encoded!r}")

    decoded, consumed = decode_length_prefixed(bytearray(encoded))

    print(f"Decoded message: {decoded!r}")
    print(f"Bytes consumed: {consumed}")


# ============================================================================
# 27. CHECKSUM AND INTEGRITY CONCEPT
# ============================================================================

def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def integrity_demo() -> None:
    print("\nDATA INTEGRITY DEMONSTRATION")
    print("=" * 72)

    original = b"important payload"
    modified = b"important payloaD"

    original_hash = sha256_digest(original)
    modified_hash = sha256_digest(modified)

    print(f"Original hash : {original_hash}")
    print(f"Modified hash : {modified_hash}")
    print(f"Hashes equal  : {original_hash == modified_hash}")

    print(
        "\nCryptographic hashes can detect changes, but a hash alone does "
        "not authenticate who created the data."
    )


# ============================================================================
# 28. SECURITY CONCEPTS
# ============================================================================

def security_demo() -> None:
    print("\nNETWORK SECURITY CONCEPTS")
    print("=" * 72)

    security_points = [
        "TCP does not encrypt application data.",
        "IP addresses are not proof of application identity.",
        "TLS can provide encryption and authentication above TCP.",
        "Firewalls can filter traffic using addresses, ports, and protocol information.",
        "Input received from a network must be treated as untrusted.",
        "Authentication and authorization are application-level concerns.",
        "Rate limiting can reduce resource-exhaustion risk.",
        "Timeouts prevent indefinite waiting on unresponsive peers.",
        "Encryption protects confidentiality but does not automatically make an application secure.",
    ]

    for point in security_points:
        print(f"- {point}")


# ============================================================================
# 29. ERROR HANDLING
# ============================================================================

def validate_port(port: int) -> None:
    if not isinstance(port, int):
        raise TypeError("Port must be an integer.")

    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")


def validate_port_demo() -> None:
    print("\nVALIDATION AND FAILURE CONDITIONS")
    print("=" * 72)

    test_ports = [80, 443, 0, 70000, "443"]

    for port in test_ports:
        try:
            validate_port(port)
            print(f"{port!r}: valid")

        except (TypeError, ValueError) as error:
            print(f"{port!r}: invalid -> {error}")


# ============================================================================
# 30. PERFORMANCE CONSIDERATIONS
# ============================================================================

def performance_demo() -> None:
    print("\nPERFORMANCE CONSIDERATIONS")
    print("=" * 72)

    considerations = [
        "Latency measures time taken for communication.",
        "Bandwidth measures the capacity of a link.",
        "Throughput measures the amount of useful data transferred over time.",
        "Packet loss can reduce application performance.",
        "Retransmission consumes bandwidth and adds latency.",
        "Large application messages may interact with MTU and buffering.",
        "Connection setup has a cost, which matters for short-lived requests.",
        "Persistent connections can reduce repeated connection establishment.",
        "Concurrency models affect how many simultaneous connections a server can handle.",
        "DNS resolution and TLS handshakes can contribute to request latency.",
    ]

    for item in considerations:
        print(f"- {item}")


# ============================================================================
# 31. NETWORK TROUBLESHOOTING ORDER
# ============================================================================

def troubleshooting_demo() -> None:
    print("\nTROUBLESHOOTING BY TCP/IP LAYERS")
    print("=" * 72)

    checks = [
        ("Application", "Is the service running? Is the protocol request valid?"),
        ("Transport", "Is the expected port reachable? Is TCP or UDP correct?"),
        ("Internet", "Is the destination IP correct? Is routing available?"),
        ("Network Access", "Is the interface connected? Is local link communication working?"),
    ]

    for layer, question in checks:
        print(f"{layer:18} -> {question}")

    print(
        "\nA layered troubleshooting process narrows a failure to the "
        "smallest plausible part of the communication path."
    )


# ============================================================================
# 32. COMPLETE END-TO-END SIMULATION
# ============================================================================

@dataclass
class NetworkMessage:
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    payload: bytes


def end_to_end_simulation() -> None:
    print("\nEND-TO-END ENCAPSULATION SIMULATION")
    print("=" * 72)

    message = NetworkMessage(
        source_ip="192.168.1.20",
        destination_ip="203.0.113.50",
        source_port=53000,
        destination_port=443,
        payload=b"GET / HTTP/1.1",
    )

    print("Application:")
    print(f"  Payload = {message.payload!r}")

    print("\nTransport:")
    print(
        f"  TCP source port = {message.source_port}, "
        f"destination port = {message.destination_port}"
    )

    print("\nInternet:")
    print(
        f"  IPv4 source = {message.source_ip}, "
        f"destination = {message.destination_ip}"
    )

    print("\nNetwork access:")
    print(
        "  Ethernet/Wi-Fi frame carries the IP packet across the local link."
    )

    print("\nConceptual path:")
    print(
        "Application data -> TCP segment -> IP packet -> Ethernet/Wi-Fi frame"
    )


# ============================================================================
# 33. SIMPLE UNIT TESTS
# ============================================================================

def run_tests() -> None:
    print("\nSELF-TESTS")
    print("=" * 72)

    assert validate_port(443) is None

    try:
        validate_port(0)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid port was accepted.")

    network = ipaddress.ip_network("192.168.1.0/24")
    assert ipaddress.ip_address("192.168.1.20") in network

    table = RoutingTable(
        [
            Route(ipaddress.ip_network("0.0.0.0/0"), "default"),
            Route(ipaddress.ip_network("10.0.0.0/8"), "private"),
            Route(ipaddress.ip_network("10.10.0.0/16"), "specific"),
        ]
    )

    assert table.lookup("10.10.5.1").next_hop == "specific"
    assert table.lookup("8.8.8.8").next_hop == "default"

    original = b"networking"
    encoded = encode_length_prefixed(original)
    decoded, consumed = decode_length_prefixed(bytearray(encoded))

    assert decoded == original
    assert consumed == len(encoded)

    handshake = tcp_three_way_handshake()
    assert handshake[0].syn
    assert handshake[1].syn and handshake[1].ack
    assert handshake[2].ack

    print("All self-tests passed.")


# ============================================================================
# 34. MAIN PROGRAM
# ============================================================================

def main() -> None:
    print("=" * 72)
    print("TCP/IP MODEL - COMPREHENSIVE PYTHON STUDY PROGRAM")
    print("=" * 72)

    print_model()
    explain_terminology()
    application_layer_demo()
    dns_demo()
    explain_ports()
    demonstrate_socket_addresses()
    tcp_handshake_demo()
    tcp_reliability_demo()
    udp_demo()
    compare_tcp_udp()
    ipv4_demo()
    subnet_demo()
    routing_demo()
    ipv4_header_demo()
    ttl_demo()
    icmp_demo()
    mac_address_demo()
    ethernet_demo()
    arp_demo()
    encapsulation_demo()
    fragmentation_demo()
    ipv6_demo()
    tcp_stream_demo()
    framing_demo()
    application_protocol_demo()
    integrity_demo()
    security_demo()
    validate_port_demo()
    performance_demo()
    troubleshooting_demo()
    end_to_end_simulation()
    tcp_server_demo()
    udp_socket_demo()
    run_tests()

    print("\nPROGRAM COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
