"""
TCP AND UDP: CONNECTION-ORIENTED AND CONNECTIONLESS NETWORK COMMUNICATION
==========================================================================

A standalone study program covering TCP and UDP from beginner to advanced
concepts, including:

- Network communication fundamentals
- IP addresses, ports, sockets, protocols
- TCP connection-oriented communication
- TCP three-way handshake
- TCP sequence numbers, acknowledgements, retransmission, flow control,
  congestion control, ordering, and connection termination
- UDP connectionless communication
- Datagram semantics, message boundaries, checksum, and limitations
- TCP versus UDP
- Practical socket programming
- Blocking and timeout behavior
- Client/server communication
- TCP framing
- UDP request/response
- Reliability implemented at the application layer
- Performance and security considerations
- Edge cases and common mistakes
- A small reliable-message protocol built over UDP
- Local demonstrations that do not require external servers

The examples use Python's standard library only.
"""

from __future__ import annotations

import json
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional


# ============================================================================
# 1. FUNDAMENTAL NETWORKING CONCEPTS
# ============================================================================

def section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def explain_network_endpoint() -> None:
    section("1. NETWORK ENDPOINTS, IP ADDRESSES, PORTS, AND SOCKETS")

    print(
        """
A network application normally communicates through an endpoint.

An endpoint is commonly identified by:

    IP address + transport protocol + port number

Examples:

    192.168.1.20 + TCP + 443
    192.168.1.20 + UDP + 53

The IP layer identifies a host/interface.
The transport layer identifies an application process through a port.

TCP and UDP are transport-layer protocols carried by IP.

A socket is the operating-system abstraction through which an application
sends and receives network data.

Python examples:

    socket.AF_INET
        IPv4

    socket.AF_INET6
        IPv6

    socket.SOCK_STREAM
        Stream socket, normally TCP

    socket.SOCK_DGRAM
        Datagram socket, normally UDP
        """
    )

    examples = {
        "IPv4 address": "127.0.0.1",
        "TCP port": 5000,
        "UDP port": 5353,
        "TCP socket type": socket.SOCK_STREAM,
        "UDP socket type": socket.SOCK_DGRAM,
    }

    for name, value in examples.items():
        print(f"{name:20}: {value}")


# ============================================================================
# 2. TCP FUNDAMENTALS
# ============================================================================

def explain_tcp() -> None:
    section("2. TCP: TRANSMISSION CONTROL PROTOCOL")

    print(
        """
TCP is a connection-oriented transport protocol.

Important characteristics:

1. A logical connection is established before application data is exchanged.
2. Data is presented to the application as an ordered byte stream.
3. TCP uses sequence numbers and acknowledgements.
4. Lost data can be retransmitted.
5. TCP detects corrupted segments using a checksum.
6. TCP provides flow control so a fast sender does not overwhelm a receiver.
7. TCP uses congestion-control mechanisms to respond to network congestion.
8. TCP does not preserve application message boundaries.
9. TCP is reliable in the sense that it attempts to deliver an ordered,
   duplicate-free byte stream, subject to connection/network failure.
10. TCP does not guarantee that a connection will remain available forever.

Typical applications:

- HTTP/HTTPS
- SSH
- SMTP
- IMAP
- many database connections
- many application APIs
"""
    )

    print("Conceptual TCP lifecycle:")
    print("CLIENT -> SYN")
    print("SERVER -> SYN + ACK")
    print("CLIENT -> ACK")
    print("CLIENT <==== ordered byte stream ====> SERVER")
    print("CLIENT -> FIN")
    print("SERVER -> ACK")
    print("SERVER -> FIN")
    print("CLIENT -> ACK")


# ============================================================================
# 3. TCP THREE-WAY HANDSHAKE
# ============================================================================

@dataclass
class TCPSegment:
    """A simplified educational representation of TCP control information."""

    source_port: int
    destination_port: int
    sequence_number: int
    acknowledgement_number: int
    syn: bool = False
    ack: bool = False
    fin: bool = False
    payload: bytes = b""


def demonstrate_tcp_handshake() -> None:
    section("3. TCP THREE-WAY HANDSHAKE")

    client_isn = 1000
    server_isn = 5000

    syn = TCPSegment(
        source_port=40000,
        destination_port=8000,
        sequence_number=client_isn,
        acknowledgement_number=0,
        syn=True,
    )

    syn_ack = TCPSegment(
        source_port=8000,
        destination_port=40000,
        sequence_number=server_isn,
        acknowledgement_number=client_isn + 1,
        syn=True,
        ack=True,
    )

    ack = TCPSegment(
        source_port=40000,
        destination_port=8000,
        sequence_number=client_isn + 1,
        acknowledgement_number=server_isn + 1,
        ack=True,
    )

    print("1. Client sends SYN:")
    print(syn)

    print("\n2. Server sends SYN-ACK:")
    print(syn_ack)

    print("\n3. Client sends ACK:")
    print(ack)

    print(
        """
Why three messages?

The endpoints need to establish that:

- the client can send to the server,
- the server can send to the client,
- both sides have synchronized sequence-number state.

The numbers above are simplified educational values, not a complete model
of every TCP implementation detail.
"""
    )


# ============================================================================
# 4. TCP BYTE STREAM AND MESSAGE FRAMING
# ============================================================================

def demonstrate_tcp_framing() -> None:
    section("4. TCP IS A BYTE STREAM, NOT A MESSAGE QUEUE")

    print(
        """
Suppose an application sends:

    send(b"HELLO")
    send(b"WORLD")

The receiver is NOT guaranteed to receive:

    recv(...) -> b"HELLO"
    recv(...) -> b"WORLD"

It could receive:

    b"HELLOWORLD"

or:

    b"HE"
    b"LLOW"
    b"ORLD"

or another segmentation.

This is why application protocols running over TCP commonly define framing.

A common framing technique is:

    [4-byte payload length][payload]

The receiver first reads exactly four bytes and interprets them as the
payload length. It then reads exactly that many payload bytes.
"""
    )

    def encode_message(message: bytes) -> bytes:
        if len(message) > 10_000_000:
            raise ValueError("Message is too large")
        return struct.pack("!I", len(message)) + message

    def decode_stream(buffer: bytearray) -> list[bytes]:
        messages: list[bytes] = []

        while len(buffer) >= 4:
            payload_length = struct.unpack("!I", buffer[:4])[0]

            if payload_length > 10_000_000:
                raise ValueError("Invalid payload length")

            total_length = 4 + payload_length

            if len(buffer) < total_length:
                break

            messages.append(bytes(buffer[4:total_length]))
            del buffer[:total_length]

        return messages

    encoded = encode_message(b"HELLO")
    encoded += encode_message(b"WORLD")

    receiver_buffer = bytearray()

    # Deliberately simulate arbitrary TCP receive boundaries.
    chunks = [encoded[:2], encoded[2:7], encoded[7:]]

    for chunk in chunks:
        receiver_buffer.extend(chunk)
        decoded = decode_stream(receiver_buffer)
        print(f"Received chunk: {chunk!r}")
        print(f"Decoded complete messages: {decoded}")

    print(f"Remaining incomplete bytes: {bytes(receiver_buffer)!r}")


# ============================================================================
# 5. REAL TCP SERVER AND CLIENT
# ============================================================================

def tcp_server(
    ready_event: threading.Event,
    result: dict,
) -> None:
    """
    Start a local TCP server.

    The server uses localhost so the example does not depend on an external
    network service.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # SO_REUSEADDR helps avoid some bind problems after quick restarts.
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server.bind(("127.0.0.1", 0))
        server.listen(1)

        result["address"] = server.getsockname()
        ready_event.set()

        connection, address = server.accept()

        with connection:
            connection.settimeout(5)
            print(f"\nTCP server accepted connection from {address}")

            data = connection.recv(4096)

            if data:
                print(f"TCP server received: {data!r}")
                response = b"TCP server response: " + data
                connection.sendall(response)

    except Exception as exc:
        result["error"] = exc
        ready_event.set()

    finally:
        server.close()


def demonstrate_tcp_socket() -> None:
    section("5. REAL LOCAL TCP CLIENT/SERVER EXAMPLE")

    ready = threading.Event()
    result: dict = {}

    server_thread = threading.Thread(
        target=tcp_server,
        args=(ready, result),
        daemon=True,
    )
    server_thread.start()

    if not ready.wait(timeout=3):
        raise RuntimeError("TCP server did not become ready")

    if "error" in result:
        raise result["error"]

    host, port = result["address"]
    print(f"TCP server listening on {host}:{port}")

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client.settimeout(5)
        client.connect((host, port))

        request = b"Hello over TCP"
        client.sendall(request)

        response = client.recv(4096)

        print(f"TCP client sent:     {request!r}")
        print(f"TCP client received: {response!r}")

    finally:
        client.close()

    server_thread.join(timeout=3)


# ============================================================================
# 6. TCP ERROR HANDLING AND TIMEOUTS
# ============================================================================

def demonstrate_tcp_timeout() -> None:
    section("6. TCP TIMEOUT AND ERROR HANDLING")

    print(
        """
A socket operation can block indefinitely unless the application defines
appropriate timeouts or uses non-blocking/asynchronous I/O.

A production application should consider:

- connection timeout,
- read timeout,
- write timeout where supported by the chosen architecture,
- retry policy,
- cancellation,
- maximum message size,
- graceful shutdown,
- handling connection reset,
- handling peer disappearance.

Timeouts do not make TCP unreliable. They define how long the application
is willing to wait before treating the operation as unsuccessful.
"""
    )

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(0.2)

        try:
            server.accept()
        except socket.timeout:
            print("Expected demonstration: accept() timed out safely.")

    finally:
        server.close()


# ============================================================================
# 7. TCP CONNECTION TERMINATION
# ============================================================================

def demonstrate_tcp_termination() -> None:
    section("7. TCP CONNECTION TERMINATION")

    print(
        """
TCP normally uses FIN and ACK signaling when an endpoint performs an
orderly shutdown.

A simplified sequence is:

    A -> FIN
    B -> ACK
    B -> FIN
    A -> ACK

TCP supports half-close behavior, meaning one direction can be closed
while the other direction remains usable.

In Python:

    sock.shutdown(socket.SHUT_WR)

can indicate that the local application has finished sending while it may
still receive data.

close() releases the socket resource. shutdown() controls communication
directions before the socket is closed.
"""
    )


# ============================================================================
# 8. UDP FUNDAMENTALS
# ============================================================================

def explain_udp() -> None:
    section("8. UDP: USER DATAGRAM PROTOCOL")

    print(
        """
UDP is a connectionless transport protocol.

A UDP sender creates individual datagrams.

Important characteristics:

- no TCP-style connection establishment,
- no built-in retransmission,
- no built-in ordered byte stream,
- datagram boundaries are preserved,
- a packet can be lost,
- a packet can arrive more than once at the application,
- packets can arrive out of order,
- congestion behavior is largely an application/system concern,
- UDP has lower protocol overhead and no connection handshake.

UDP is useful when an application values low latency, simple request/
response communication, message boundaries, multicast/broadcast support,
or application-specific reliability.

Common examples include:

- DNS
- DHCP
- NTP
- real-time media
- online games
- telemetry
- discovery protocols
- QUIC transport underneath HTTP/3 uses UDP as its packet substrate
"""
    )


# ============================================================================
# 9. REAL UDP SERVER AND CLIENT
# ============================================================================

def udp_server(
    ready_event: threading.Event,
    result: dict,
) -> None:
    """Start a local UDP echo server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        server.bind(("127.0.0.1", 0))
        result["address"] = server.getsockname()
        ready_event.set()

        server.settimeout(5)
        data, address = server.recvfrom(4096)

        print(f"\nUDP server received {data!r} from {address}")
        server.sendto(b"UDP server response: " + data, address)

    except Exception as exc:
        result["error"] = exc
        ready_event.set()

    finally:
        server.close()


def demonstrate_udp_socket() -> None:
    section("9. REAL LOCAL UDP CLIENT/SERVER EXAMPLE")

    ready = threading.Event()
    result: dict = {}

    server_thread = threading.Thread(
        target=udp_server,
        args=(ready, result),
        daemon=True,
    )
    server_thread.start()

    if not ready.wait(timeout=3):
        raise RuntimeError("UDP server did not become ready")

    if "error" in result:
        raise result["error"]

    host, port = result["address"]

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        client.settimeout(5)

        message = b"Hello over UDP"
        client.sendto(message, (host, port))

        response, address = client.recvfrom(4096)

        print(f"UDP client sent:     {message!r}")
        print(f"UDP client received: {response!r}")
        print(f"Response came from:  {address}")

    finally:
        client.close()

    server_thread.join(timeout=3)


# ============================================================================
# 10. UDP MESSAGE BOUNDARIES
# ============================================================================

def demonstrate_udp_message_boundaries() -> None:
    section("10. UDP PRESERVES DATAGRAM BOUNDARIES")

    print(
        """
If a sender performs:

    sendto(b"ONE")
    sendto(b"TWO")

the receiver normally obtains one datagram per recvfrom() operation:

    recvfrom(...) -> b"ONE"
    recvfrom(...) -> b"TWO"

This differs fundamentally from TCP's byte-stream abstraction.

A UDP datagram is still subject to IP/network limitations. Applications
should not assume that arbitrary large datagrams are safe to transmit.
Fragmentation can create reliability and performance problems, so practical
protocols commonly keep UDP payloads reasonably small.
"""
    )

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)

        address = receiver.getsockname()

        sender.sendto(b"ONE", address)
        sender.sendto(b"TWO", address)

        first, _ = receiver.recvfrom(100)
        second, _ = receiver.recvfrom(100)

        print("First datagram: ", first)
        print("Second datagram:", second)

    finally:
        sender.close()
        receiver.close()


# ============================================================================
# 11. TCP VS UDP COMPARISON
# ============================================================================

def compare_tcp_udp() -> None:
    section("11. TCP VERSUS UDP")

    comparison = [
        ("Connection setup", "TCP handshake", "No TCP-style handshake"),
        ("Communication model", "Byte stream", "Datagrams"),
        ("Ordering", "Built in", "Not guaranteed"),
        ("Retransmission", "Built in", "Not built in"),
        ("Duplicate suppression", "TCP manages stream delivery", "Application responsibility"),
        ("Flow control", "Built in", "Not provided by UDP"),
        ("Congestion control", "Built into TCP", "Not provided by basic UDP"),
        ("Message boundaries", "Not preserved", "Preserved"),
        ("Typical overhead", "Higher", "Lower"),
        ("Broadcast/multicast", "Not normal TCP behavior", "Supported by UDP/IP"),
        ("Typical use", "Web, SSH, databases", "DNS, telemetry, real-time traffic"),
    ]

    headers = ("Property", "TCP", "UDP")

    widths = [28, 30, 38]
    print(
        f"{headers[0]:<{widths[0]}} | "
        f"{headers[1]:<{widths[1]}} | "
        f"{headers[2]:<{widths[2]}}"
    )
    print("-" * 102)

    for row in comparison:
        print(
            f"{row[0]:<{widths[0]}} | "
            f"{row[1]:<{widths[1]}} | "
            f"{row[2]:<{widths[2]}}"
        )


# ============================================================================
# 12. UDP DOES NOT MEAN "NO SOCKET STATE"
# ============================================================================

def demonstrate_udp_connect() -> None:
    section("12. UDP CONNECT() DOES NOT TURN UDP INTO TCP")

    print(
        """
A UDP socket can call connect().

This does NOT perform a TCP-style three-way handshake.

For a UDP socket, connect() typically records a default peer so that:

- send() can be used instead of sendto(),
- recv() can be used instead of recvfrom(),
- datagrams from unrelated peers can be filtered by the OS,
- certain asynchronous errors can be associated with the peer.

UDP remains datagram-based and does not gain TCP's reliability guarantees.
"""
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect(("127.0.0.1", 9999))
        print("UDP socket connected logically to peer 127.0.0.1:9999")
        print("No TCP three-way handshake was performed by this call.")
    finally:
        sock.close()


# ============================================================================
# 13. APPLICATION-LAYER RELIABILITY OVER UDP
# ============================================================================

@dataclass
class ReliablePacket:
    """
    A small educational reliability header.

    Fields:
        sequence: monotonically increasing message identifier
        timestamp: sender-side creation time
        payload: application bytes
    """

    sequence: int
    timestamp: float
    payload: bytes

    def encode(self) -> bytes:
        if len(self.payload) > 1200:
            raise ValueError("Payload exceeds demonstration limit")

        header = struct.pack(
            "!IdI",
            self.sequence,
            self.timestamp,
            len(self.payload),
        )

        return header + self.payload

    @classmethod
    def decode(cls, data: bytes) -> "ReliablePacket":
        header_size = struct.calcsize("!IdI")

        if len(data) < header_size:
            raise ValueError("Packet is too short")

        sequence, timestamp, payload_length = struct.unpack(
            "!IdI",
            data[:header_size],
        )

        payload = data[header_size:]

        if payload_length != len(payload):
            raise ValueError("Payload length mismatch")

        if payload_length > 1200:
            raise ValueError("Payload exceeds maximum")

        return cls(
            sequence=sequence,
            timestamp=timestamp,
            payload=payload,
        )


def demonstrate_application_reliability() -> None:
    section("13. BUILDING RELIABILITY ABOVE UDP")

    print(
        """
UDP itself does not acknowledge, reorder, or retransmit application
messages.

An application can implement selected reliability features.

A basic protocol might contain:

    sequence number
    timestamp
    payload length
    payload

The receiver can:

    1. validate the packet,
    2. reject malformed packets,
    3. detect duplicate sequence numbers,
    4. detect missing sequence numbers,
    5. acknowledge received messages,
    6. request or trigger retransmission,
    7. discard packets after a timeout.

This example implements packet structure and validation. It intentionally
does not pretend to reproduce the complexity of TCP's mature congestion
and retransmission algorithms.
"""
    )

    packet = ReliablePacket(
        sequence=42,
        timestamp=time.time(),
        payload=b"critical telemetry",
    )

    encoded = packet.encode()
    decoded = ReliablePacket.decode(encoded)

    print("Encoded packet size:", len(encoded))
    print("Decoded sequence:   ", decoded.sequence)
    print("Decoded payload:    ", decoded.payload)


# ============================================================================
# 14. SIMPLE RETRANSMISSION SIMULATION
# ============================================================================

class SimulatedUnreliableNetwork:
    """
    Educational network simulator.

    It randomly drops messages to demonstrate why an application that needs
    reliability must detect loss and retry when using a connectionless
    transport.
    """

    def __init__(self, loss_probability: float, seed: int = 7):
        if not 0 <= loss_probability <= 1:
            raise ValueError("loss_probability must be between 0 and 1")

        self.loss_probability = loss_probability
        self.random = random.Random(seed)

    def transmit(self, packet: ReliablePacket) -> Optional[ReliablePacket]:
        if self.random.random() < self.loss_probability:
            return None
        return packet


def demonstrate_udp_retransmission_strategy() -> None:
    section("14. UDP RETRANSMISSION STRATEGY")

    network = SimulatedUnreliableNetwork(loss_probability=0.35)

    packet = ReliablePacket(
        sequence=1,
        timestamp=time.time(),
        payload=b"important event",
    )

    maximum_attempts = 5
    delivered = False

    for attempt in range(1, maximum_attempts + 1):
        result = network.transmit(packet)

        if result is None:
            print(f"Attempt {attempt}: packet lost")
        else:
            print(f"Attempt {attempt}: packet delivered")
            delivered = True
            break

    if delivered:
        print("Application-level reliability simulation succeeded.")
    else:
        print("Application-level reliability simulation failed after retries.")


# ============================================================================
# 15. TCP PERFORMANCE CONSIDERATIONS
# ============================================================================

def explain_tcp_performance() -> None:
    section("15. TCP PERFORMANCE CONSIDERATIONS")

    print(
        """
TCP performance is influenced by more than raw bandwidth.

Important concepts include:

- round-trip time (RTT),
- bandwidth-delay product,
- congestion window,
- receive window,
- slow start,
- congestion avoidance,
- retransmissions,
- delayed acknowledgements,
- packet loss,
- receiver processing speed,
- sender buffering,
- application-level framing.

Bandwidth-delay product:

    BDP = bandwidth × RTT

For example, a 100 Mbps path with a 50 ms RTT has approximately:

    100,000,000 bits/s × 0.050 s
    = 5,000,000 bits
    = 625,000 bytes

A TCP flow may need a sufficiently large effective window to keep such a
path fully utilized.

Modern TCP implementations contain sophisticated algorithms, so a simple
textbook formula should not be treated as a complete performance model.
"""
    )

    bandwidth_bits_per_second = 100_000_000
    rtt_seconds = 0.050
    bdp_bytes = bandwidth_bits_per_second * rtt_seconds / 8

    print(f"Example BDP: {bdp_bytes:,.0f} bytes")


# ============================================================================
# 16. UDP PERFORMANCE CONSIDERATIONS
# ============================================================================

def explain_udp_performance() -> None:
    section("16. UDP PERFORMANCE CONSIDERATIONS")

    print(
        """
UDP removes TCP's connection establishment and reliability machinery, but
that does not automatically make an application faster.

The application may need to implement:

- loss detection,
- retransmission,
- sequencing,
- rate limiting,
- congestion response,
- authentication,
- encryption,
- duplicate detection,
- connection/session state.

Sending packets too aggressively can cause congestion and packet loss.

Low protocol overhead is useful only when the application's requirements
match UDP's semantics.
"""
    )


# ============================================================================
# 17. SOCKET BUFFER AND MTU CONSIDERATIONS
# ============================================================================

def explain_packet_size() -> None:
    section("17. DATAGRAM SIZE, MTU, AND FRAGMENTATION")

    print(
        """
MTU means Maximum Transmission Unit.

Ethernet commonly uses an MTU around 1500 bytes, although actual paths
can differ.

IPv4 and IPv6 add headers, and UDP adds its own header.

Applications should avoid assuming that a large UDP payload will travel
efficiently without fragmentation.

Fragmentation can increase loss impact:

If a datagram is split into multiple fragments and one fragment is lost,
the complete datagram may become unusable.

This is one reason practical UDP protocols often keep packets comfortably
below the path MTU.
"""
    )


# ============================================================================
# 18. SECURITY CONSIDERATIONS
# ============================================================================

def explain_security() -> None:
    section("18. SECURITY CONSIDERATIONS")

    print(
        """
Neither TCP nor UDP automatically provides application-level encryption.

TCP:
    TCP provides transport reliability, not confidentiality.

UDP:
    UDP provides neither confidentiality nor application authentication.

Security-sensitive applications should consider:

- encryption,
- authentication,
- integrity protection,
- replay protection,
- input validation,
- rate limiting,
- resource limits,
- amplification resistance,
- authorization,
- logging without leaking secrets.

TLS is commonly used above TCP.

Modern protocols can also provide encrypted transport semantics over UDP.
QUIC is an important example: it runs over UDP and incorporates reliability,
security, multiplexing, and congestion control into a higher-level transport
protocol.

Never assume that "UDP" means insecure or that "TCP" means secure.
Security is determined by the complete protocol stack and configuration.
"""
    )


# ============================================================================
# 19. COMMON MISTAKES
# ============================================================================

def explain_common_mistakes() -> None:
    section("19. COMMON TCP AND UDP MISTAKES")

    mistakes = [
        (
            "Mistake",
            "TCP recv() returns one complete application message.",
            "TCP is a byte stream. Implement explicit framing."
        ),
        (
            "Mistake",
            "UDP packets always arrive.",
            "UDP provides no delivery guarantee."
        ),
        (
            "Mistake",
            "UDP connect() creates a TCP-like connection.",
            "UDP connect() configures a default peer; no TCP handshake occurs."
        ),
        (
            "Mistake",
            "TCP is encrypted.",
            "TCP alone does not encrypt application data."
        ),
        (
            "Mistake",
            "UDP is always faster.",
            "Performance depends on protocol behavior and application needs."
        ),
        (
            "Mistake",
            "Closing a TCP socket immediately means all data was delivered.",
            "Application shutdown semantics and network failure still matter."
        ),
        (
            "Mistake",
            "A timeout proves the server is down.",
            "A timeout only proves the operation did not complete within the limit."
        ),
        (
            "Mistake",
            "A large UDP datagram is always safe.",
            "MTU and fragmentation can make large datagrams problematic."
        ),
    ]

    for label, mistake, correction in mistakes:
        print(f"\n{label}: {mistake}")
        print(f"Correction: {correction}")


# ============================================================================
# 20. DECISION GUIDELINES
# ============================================================================

def explain_use_cases() -> None:
    section("20. COMMON USE CASES")

    use_cases = {
        "Web pages and APIs": "Usually TCP-based HTTP/1.1 or HTTP/2; HTTP/3 uses QUIC over UDP.",
        "SSH": "TCP is appropriate because ordered reliable delivery is essential.",
        "Database sessions": "Typically TCP because transactions require reliable ordered communication.",
        "DNS": "Traditionally UDP for many queries, with TCP also used for specific cases and larger/zone-transfer traffic.",
        "Real-time voice/video": "UDP-based approaches can avoid waiting for retransmission of stale data.",
        "Online games": "UDP is often useful for latency-sensitive state updates, while some traffic may use reliable transports.",
        "Telemetry": "UDP can be suitable when occasional loss is acceptable or application reliability is implemented separately.",
        "File transfer": "Reliable ordered delivery is generally required, making TCP or another reliable transport appropriate.",
        "Service discovery": "UDP can be useful because multicast/broadcast-style communication is supported.",
    }

    for application, transport in use_cases.items():
        print(f"\n{application}:")
        print(f"  {transport}")


# ============================================================================
# 21. ADVANCED SOCKET PATTERNS
# ============================================================================

def explain_advanced_patterns() -> None:
    section("21. ADVANCED SOCKET DESIGN PATTERNS")

    print(
        """
Production network services commonly need:

1. Multiple clients
   - Threading
   - Processes
   - Async I/O
   - Event loops

2. Backpressure
   - Do not allow unbounded queues.
   - Apply limits when producers are faster than consumers.

3. Framing
   - Length-prefix messages
   - Delimiter-based messages
   - Fixed-size records

4. Timeouts
   - Connection timeout
   - Read timeout
   - Protocol deadline

5. Graceful shutdown
   - Stop accepting new work.
   - Finish or cancel existing work.
   - Close sockets predictably.

6. Validation
   - Reject malformed packets.
   - Enforce maximum sizes.
   - Validate protocol fields.

7. Observability
   - Request IDs
   - Connection counts
   - latency
   - error rates
   - packet loss where measurable

8. Security
   - authentication
   - encryption
   - authorization
   - rate limiting
"""
    )


# ============================================================================
# 22. SIMPLE TCP PROTOCOL IMPLEMENTATION
# ============================================================================

class FramedTCPProtocol:
    """Educational length-prefixed TCP protocol."""

    MAX_MESSAGE_SIZE = 1_000_000

    @staticmethod
    def encode(message: bytes) -> bytes:
        if len(message) > FramedTCPProtocol.MAX_MESSAGE_SIZE:
            raise ValueError("Message exceeds protocol limit")

        return struct.pack("!I", len(message)) + message

    @staticmethod
    def feed(buffer: bytearray) -> list[bytes]:
        messages: list[bytes] = []

        while True:
            if len(buffer) < 4:
                break

            length = struct.unpack("!I", buffer[:4])[0]

            if length > FramedTCPProtocol.MAX_MESSAGE_SIZE:
                raise ValueError("Invalid message length")

            if len(buffer) < length + 4:
                break

            message = bytes(buffer[4:length + 4])
            del buffer[:length + 4]
            messages.append(message)

        return messages


def demonstrate_protocol_parser() -> None:
    section("22. ROBUST TCP APPLICATION-LAYER FRAMING")

    stream = (
        FramedTCPProtocol.encode(b"first")
        + FramedTCPProtocol.encode(b"second")
        + FramedTCPProtocol.encode(b"third")
    )

    fragments = [
        stream[:1],
        stream[1:5],
        stream[5:11],
        stream[11:],
    ]

    buffer = bytearray()

    for fragment in fragments:
        buffer.extend(fragment)
        messages = FramedTCPProtocol.feed(buffer)

        print(f"Added {len(fragment)} bytes; complete messages: {messages}")

    print("Unconsumed bytes:", len(buffer))


# ============================================================================
# 23. TESTING AND VALIDATION
# ============================================================================

def run_self_tests() -> None:
    section("23. SELF-TESTS")

    encoded = FramedTCPProtocol.encode(b"hello")
    buffer = bytearray(encoded)

    assert FramedTCPProtocol.feed(buffer) == [b"hello"]
    assert buffer == bytearray()

    packet = ReliablePacket(
        sequence=7,
        timestamp=123.456,
        payload=b"data",
    )

    decoded = ReliablePacket.decode(packet.encode())

    assert decoded.sequence == 7
    assert decoded.payload == b"data"

    try:
        FramedTCPProtocol.feed(
            bytearray(struct.pack("!I", 2_000_000))
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Oversized message was not rejected")

    try:
        ReliablePacket.decode(b"bad")
    except ValueError:
        pass
    else:
        raise AssertionError("Malformed UDP packet was not rejected")

    print("All self-tests passed.")


# ============================================================================
# 24. PRACTICAL CHECKLIST
# ============================================================================

def print_practical_checklist() -> None:
    section("24. PRACTICAL TRANSPORT-SELECTION CHECKLIST")

    questions = [
        "Do I need ordered, reliable byte-stream delivery?",
        "Can my application tolerate packet loss?",
        "Does every application message need to preserve its boundaries?",
        "Can stale data become useless after a deadline?",
        "Do I need multicast or broadcast communication?",
        "Will I implement reliability, sequencing, or retransmission myself?",
        "How will congestion be handled?",
        "What packet/message size is safe?",
        "What authentication and encryption are required?",
        "What happens when the peer disappears?",
        "What are the connection, read, and application deadlines?",
        "How will malformed or hostile input be handled?",
    ]

    for number, question in enumerate(questions, start=1):
        print(f"{number:2}. {question}")


# ============================================================================
# 25. MAIN
# ============================================================================

def main() -> None:
    section("TCP AND UDP STUDY PROGRAM")

    print(
        """
This program demonstrates transport-layer concepts using local simulations
and loopback sockets. Network behavior in production depends on operating
systems, network paths, firewalls, routers, NAT, kernel configuration, and
the complete application protocol.
"""
    )

    explain_network_endpoint()
    explain_tcp()
    demonstrate_tcp_handshake()
    demonstrate_tcp_framing()
    demonstrate_tcp_socket()
    demonstrate_tcp_timeout()
    demonstrate_tcp_termination()

    explain_udp()
    demonstrate_udp_socket()
    demonstrate_udp_message_boundaries()
    compare_tcp_udp()
    demonstrate_udp_connect()

    demonstrate_application_reliability()
    demonstrate_udp_retransmission_strategy()

    explain_tcp_performance()
    explain_udp_performance()
    explain_packet_size()
    explain_security()
    explain_common_mistakes()
    explain_use_cases()
    explain_advanced_patterns()
    demonstrate_protocol_parser()
    run_self_tests()
    print_practical_checklist()

    section("END OF TCP AND UDP STUDY PROGRAM")

    print(
        """
Key conceptual distinction:

TCP:
    connection-oriented + reliable ordered byte stream

UDP:
    connectionless + independent datagrams without built-in reliability

Neither is universally superior. Transport selection should follow the
communication semantics required by the application.
"""
    )


if __name__ == "__main__":
    main()
