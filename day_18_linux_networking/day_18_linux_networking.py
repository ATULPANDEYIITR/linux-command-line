#!/usr/bin/env python3
"""
Linux Networking Study Program
==============================

A self-contained practical study file covering:

- Network interfaces
- MAC addresses and interface state
- IPv4 and IPv6 addresses
- CIDR and subnet concepts
- Default gateways and routing
- DNS configuration and name resolution
- ARP / neighbor discovery
- TCP and UDP
- Ports and sockets
- Network troubleshooting
- Latency and packet-loss concepts
- Route inspection
- DNS troubleshooting
- Connectivity testing
- Basic network monitoring
- Security and production considerations

The program uses only Python's standard library. It invokes common Linux
commands when available, while also demonstrating concepts with pure Python.

Recommended environment:
    Linux with Python 3.10+

Run:
    python3 linux_networking_study.py

Some demonstrations inspect the local machine and therefore produce results
specific to the current Linux host.
"""

from __future__ import annotations

import ipaddress
import os
import platform
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    print(f"\n--- {title} ---")


def run_command(command: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
    """Run a Linux command safely and return exit code, stdout, and stderr."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out: {' '.join(command)}"
    except OSError as exc:
        return 1, "", str(exc)


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def print_command_output(command: list[str], timeout: float = 5.0) -> None:
    """Display a command and its result without raising on normal failures."""
    print("$", " ".join(command))
    code, stdout, stderr = run_command(command, timeout)
    if stdout.strip():
        print(stdout.rstrip())
    if stderr.strip():
        print(stderr.rstrip(), file=sys.stderr)
    if code != 0:
        print(f"[exit code: {code}]")


# ---------------------------------------------------------------------------
# Fundamental networking concepts
# ---------------------------------------------------------------------------

section("1. FUNDAMENTAL NETWORKING CONCEPTS")

print(
    """
A network allows hosts to exchange data.

Important terms:

Host:
    A computer or other networked device.

Interface:
    A software-visible network adapter such as eth0, ens33, enp0s3, wlan0,
    or the loopback interface lo.

MAC address:
    A link-layer address normally associated with an Ethernet or Wi-Fi
    interface. Example: 02:42:ac:11:00:02.

IP address:
    A logical network-layer address used to identify an endpoint.

IPv4:
    32-bit addresses such as 192.168.1.25.

IPv6:
    128-bit addresses such as 2001:db8::25.

Subnet:
    A logical division of an IP network.

Gateway:
    A router used to reach destinations outside the local network.

Route:
    A rule telling the host where packets for a destination should be sent.

DNS:
    A naming system that maps names such as example.com to IP addresses.

TCP:
    Connection-oriented transport protocol providing reliable, ordered
    byte-stream delivery.

UDP:
    Connectionless transport protocol with lower protocol overhead but no
    built-in guarantee of delivery or ordering.

Port:
    A 16-bit transport-layer identifier used to distinguish services.
"""
)


# ---------------------------------------------------------------------------
# IP address fundamentals
# ---------------------------------------------------------------------------

section("2. IP ADDRESSES, CIDR, AND SUBNETTING")

subsection("IPv4 representation")

ipv4_examples = [
    "192.168.1.10",
    "10.0.0.1",
    "172.16.20.5",
    "127.0.0.1",
]

for address_text in ipv4_examples:
    address = ipaddress.ip_address(address_text)
    print(
        f"{address}: version={address.version}, "
        f"private={address.is_private}, loopback={address.is_loopback}"
    )

subsection("IPv6 representation")

ipv6_examples = [
    "2001:db8::1",
    "::1",
    "fe80::1234",
]

for address_text in ipv6_examples:
    address = ipaddress.ip_address(address_text)
    print(
        f"{address}: version={address.version}, "
        f"loopback={address.is_loopback}, link_local={address.is_link_local}"
    )

subsection("CIDR notation")

networks = [
    "192.168.1.0/24",
    "10.20.0.0/16",
    "172.16.10.0/28",
    "2001:db8:abcd::/64",
]

for network_text in networks:
    network = ipaddress.ip_network(network_text, strict=False)
    print(
        f"{network}: prefix={network.prefixlen}, "
        f"network={network.network_address}, "
        f"broadcast={getattr(network, 'broadcast_address', 'N/A')}, "
        f"hosts={network.num_addresses}"
    )

subsection("Checking whether an address belongs to a network")

network = ipaddress.ip_network("192.168.50.0/24")
addresses = ["192.168.50.10", "192.168.51.10", "192.168.50.255"]

for address_text in addresses:
    print(f"{address_text:16} -> {ipaddress.ip_address(address_text) in network}")

subsection("Subnetting")

parent = ipaddress.ip_network("192.168.100.0/24")
subnets = list(parent.subnets(new_prefix=26))

print(f"Parent network: {parent}")
for index, subnet in enumerate(subnets, start=1):
    print(f"Subnet {index}: {subnet}")

print(
    """
For IPv4, a /24 network contains 256 addresses. In traditional host
addressing, the first address identifies the network and the last address is
the broadcast address, leaving 254 ordinary host addresses.

Do not assume that every environment uses only traditional IPv4 subnet
rules. Point-to-point links, special-purpose networks, IPv6, cloud networks,
containers, and virtual interfaces can have different semantics.
"""
)


# ---------------------------------------------------------------------------
# Interface discovery
# ---------------------------------------------------------------------------

section("3. LINUX NETWORK INTERFACES")

print(
    """
Linux exposes network adapters as interfaces. The loopback interface is
normally named lo. Physical or virtual interfaces commonly have names such
as enp0s3, ens160, eth0, wlan0, docker0, or similar names.

Modern Linux commonly uses predictable interface naming. The exact names
depend on hardware, distribution, virtualization, and configuration.
"""
)

if command_exists("ip"):
    print_command_output(["ip", "-br", "link"])
    print_command_output(["ip", "-br", "address"])
else:
    print("The 'ip' command is not available on this system.")

subsection("Python interface information")

try:
    host_name = socket.gethostname()
    print("Hostname:", host_name)

    interface_names = socket.if_nameindex()
    for interface_index, interface_name in interface_names:
        print(f"index={interface_index:<4} interface={interface_name}")
except OSError as exc:
    print("Unable to enumerate interfaces:", exc)

subsection("MAC address from /sys")

for _, interface_name in socket.if_nameindex():
    mac_path = f"/sys/class/net/{interface_name}/address"
    try:
        with open(mac_path, "r", encoding="utf-8") as file:
            mac_address = file.read().strip()
        print(f"{interface_name:15} MAC={mac_address}")
    except OSError:
        print(f"{interface_name:15} MAC=<unavailable>")


# ---------------------------------------------------------------------------
# Interface state
# ---------------------------------------------------------------------------

section("4. INTERFACE STATE AND DIAGNOSTICS")

subsection("Reading interface operational state")

for _, interface_name in socket.if_nameindex():
    state_path = f"/sys/class/net/{interface_name}/operstate"
    try:
        with open(state_path, "r", encoding="utf-8") as file:
            state = file.read().strip()
        print(f"{interface_name:15} state={state}")
    except OSError:
        print(f"{interface_name:15} state=<unavailable>")

print(
    """
Typical states include:

up:
    The interface is operational.

down:
    The interface is administratively or operationally unavailable.

unknown:
    The kernel cannot provide a conventional state for the interface.

Useful commands:

    ip link
    ip -br link
    ip addr
    ip -br addr

An interface can exist without having a useful IP configuration. Likewise,
an IP address can be configured while the upstream network is unavailable.
Troubleshooting therefore proceeds through multiple layers rather than
assuming that an interface being "up" means Internet access works.
"""
)


# ---------------------------------------------------------------------------
# Local IP discovery
# ---------------------------------------------------------------------------

section("5. LOCAL IP ADDRESS DISCOVERY")

subsection("Socket-based hostname resolution")

try:
    hostname = socket.gethostname()
    addresses = socket.gethostbyname_ex(hostname)
    print("Hostname:", addresses[0])
    print("Aliases:", addresses[1])
    print("IPv4 addresses:", addresses[2])
except socket.gaierror as exc:
    print("Hostname lookup failed:", exc)

subsection("Inspecting kernel address configuration")

if command_exists("ip"):
    print_command_output(["ip", "addr", "show"])
else:
    print("Install or enable the iproute2 'ip' command for detailed address inspection.")


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

section("6. ROUTING BASICS")

print(
    """
Routing determines where an IP packet should be sent.

A Linux host normally has several classes of routes:

Connected route:
    Describes a directly reachable network.

Default route:
    Used when no more-specific route matches the destination.

Host route:
    Describes a specific destination address.

A routing table can contain multiple routes. The kernel selects the route
that best matches the destination prefix. Among otherwise comparable routes,
metrics can influence selection.

Example conceptual table:

    destination       gateway       device
    192.168.1.0/24    connected     eth0
    0.0.0.0/0         192.168.1.1   eth0

A packet for 192.168.1.50 matches the /24 route.
A packet for 8.8.8.8 does not match the /24, so the default route is used.
"""
)

subsection("Inspecting routes")

if command_exists("ip"):
    print_command_output(["ip", "route"])
    print_command_output(["ip", "-6", "route"])
else:
    print("The 'ip' command is not available.")

subsection("Asking the kernel how it would route a destination")

test_destinations = ["127.0.0.1", "8.8.8.8", "1.1.1.1"]

if command_exists("ip"):
    for destination in test_destinations:
        print_command_output(["ip", "route", "get", destination])


# ---------------------------------------------------------------------------
# Gateway discovery
# ---------------------------------------------------------------------------

section("7. DEFAULT GATEWAY")

if command_exists("ip"):
    code, output, error = run_command(["ip", "route", "show", "default"])
    if output.strip():
        print(output.rstrip())
    elif error.strip():
        print(error.rstrip())
    else:
        print("No IPv4 default route was reported.")
else:
    print("The 'ip' command is unavailable.")

print(
    """
A default gateway is not necessarily an Internet gateway. It can be the
next-hop router for a private network, enterprise network, VPN, laboratory,
cloud subnet, or other environment.

If a host can communicate with local peers but cannot reach remote networks,
inspect:

    1. interface state
    2. IP address and prefix
    3. local route
    4. default route
    5. gateway reachability
    6. DNS configuration
    7. firewall policy
    8. remote service availability
"""
)


# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------

section("8. DNS CONFIGURATION AND NAME RESOLUTION")

subsection("Reading /etc/resolv.conf")

resolv_conf = "/etc/resolv.conf"

try:
    with open(resolv_conf, "r", encoding="utf-8") as file:
        contents = file.read()
    print(contents.rstrip())
except OSError as exc:
    print(f"Cannot read {resolv_conf}: {exc}")

subsection("Parsing nameserver entries")

try:
    nameservers = []
    with open(resolv_conf, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line.startswith("nameserver"):
                parts = line.split()
                if len(parts) >= 2:
                    nameservers.append(parts[1])

    if nameservers:
        for server in nameservers:
            print("Configured resolver:", server)
    else:
        print("No nameserver lines found.")
except OSError as exc:
    print("DNS configuration unavailable:", exc)

subsection("Python getaddrinfo")

domains = ["localhost", "example.com"]

for domain in domains:
    try:
        results = socket.getaddrinfo(domain, None)
        unique_addresses = sorted(
            {result[4][0] for result in results if result[4]}
        )
        print(f"{domain}:")
        for address in unique_addresses:
            print("  ", address)
    except socket.gaierror as exc:
        print(f"{domain}: resolution failed: {exc}")

print(
    """
DNS resolution failure is different from general IP connectivity failure.

For example:

    ping 1.1.1.1 works
    ping example.com fails

can indicate a DNS problem.

The reverse situation is also possible. A DNS name may resolve correctly
while the destination service is blocked, offline, or listening on another
port.
"""
)

subsection("Using the 'getent' resolver path")

if command_exists("getent"):
    print_command_output(["getent", "hosts", "example.com"])
else:
    print("'getent' is unavailable.")


# ---------------------------------------------------------------------------
# DNS troubleshooting with explicit resolver
# ---------------------------------------------------------------------------

section("9. DNS TROUBLESHOOTING COMMANDS")

for command in [
    ["resolvectl", "status"],
    ["resolvectl", "query", "example.com"],
    ["dig", "example.com"],
    ["nslookup", "example.com"],
]:
    if command_exists(command[0]):
        print_command_output(command)
    else:
        print(f"Skipping {' '.join(command)} because {command[0]} is unavailable.")

print(
    """
The exact DNS management system differs among Linux distributions.

Possible components include:

    systemd-resolved
    NetworkManager
    resolvconf
    static /etc/resolv.conf
    container-specific DNS configuration
    VPN-provided DNS

Do not blindly overwrite /etc/resolv.conf on a managed system. It may be
generated by another service and your manual changes can disappear or cause
unexpected behavior.
"""
)


# ---------------------------------------------------------------------------
# ARP and IPv6 neighbor discovery
# ---------------------------------------------------------------------------

section("10. ARP AND NEIGHBOR DISCOVERY")

print(
    """
IPv4 uses ARP to associate local IPv4 addresses with link-layer addresses
such as Ethernet MAC addresses.

IPv6 does not use ARP. IPv6 uses Neighbor Discovery Protocol, implemented
through ICMPv6.

Linux exposes neighbor information through the neighbor table.
"""
)

if command_exists("ip"):
    print_command_output(["ip", "neigh"])
    print_command_output(["ip", "-6", "neigh"])
else:
    print("The 'ip' command is unavailable.")

print(
    """
A stale, incomplete, or failed neighbor entry can explain why a host cannot
communicate with another host on the same local network even when the IP
configuration appears correct.
"""
)


# ---------------------------------------------------------------------------
# TCP and UDP
# ---------------------------------------------------------------------------

section("11. TCP, UDP, PORTS, AND SOCKETS")

print(
    """
TCP provides:

    connection establishment
    reliable delivery
    ordering
    retransmission
    flow control
    congestion control

UDP provides:

    datagrams
    low protocol overhead
    no built-in connection handshake
    no built-in delivery guarantee
    no built-in ordering guarantee

Ports identify transport endpoints.

Examples:

    TCP 22   SSH
    TCP 80   HTTP
    TCP 443  HTTPS
    UDP 53   DNS, although DNS can also use TCP
"""
)

subsection("Listening sockets")

for command in [
    ["ss", "-tulpen"],
    ["ss", "-lnt"],
    ["ss", "-lnu"],
]:
    if command_exists(command[0]):
        print_command_output(command)
    else:
        print(f"Skipping {' '.join(command)}.")

print(
    """
When diagnosing an application:

    Is the process running?
    Is it listening?
    On which address?
    On which port?
    Is the firewall permitting traffic?
    Is the client connecting to the correct address and port?

A service listening only on 127.0.0.1 cannot normally accept connections
from another machine. A service bound to 0.0.0.0 for IPv4 can listen on all
local IPv4 interfaces, subject to firewall and routing policy.
"""
)


# ---------------------------------------------------------------------------
# Pure Python TCP server/client demonstration
# ---------------------------------------------------------------------------

section("12. PYTHON TCP SOCKET DEMONSTRATION")

@dataclass
class EchoResult:
    message: str
    response: str
    elapsed_ms: float


def run_tcp_echo_demo() -> EchoResult:
    """
    Demonstrate TCP connection establishment using loopback.

    Binding to 127.0.0.1 keeps the demonstration local to this machine.
    """
    import threading

    ready = threading.Event()
    port_holder: list[int] = []
    server_error: list[BaseException] = []

    def server() -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(("127.0.0.1", 0))
                server_socket.listen(1)

                port_holder.append(server_socket.getsockname()[1])
                ready.set()

                connection, address = server_socket.accept()
                with connection:
                    received = connection.recv(4096)
                    connection.sendall(b"ACK:" + received)
                    print(f"Server accepted connection from {address}")
        except BaseException as exc:
            server_error.append(exc)
            ready.set()

    thread = threading.Thread(target=server, daemon=True)
    thread.start()

    ready.wait(timeout=2.0)

    if server_error:
        raise RuntimeError(f"TCP server failed: {server_error[0]}")

    if not port_holder:
        raise RuntimeError("TCP server did not publish a listening port.")

    message = "Linux networking"
    started = time.perf_counter()

    with socket.create_connection(("127.0.0.1", port_holder[0]), timeout=2.0) as client:
        client.sendall(message.encode("utf-8"))
        response = client.recv(4096).decode("utf-8")

    elapsed_ms = (time.perf_counter() - started) * 1000

    thread.join(timeout=1.0)

    return EchoResult(message, response, elapsed_ms)


try:
    result = run_tcp_echo_demo()
    print("Client message :", result.message)
    print("Server response:", result.response)
    print(f"Round trip     : {result.elapsed_ms:.3f} ms")
except (OSError, RuntimeError) as exc:
    print("TCP demonstration failed:", exc)


# ---------------------------------------------------------------------------
# UDP demonstration
# ---------------------------------------------------------------------------

section("13. PYTHON UDP SOCKET DEMONSTRATION")

def run_udp_echo_demo() -> str:
    """Demonstrate a connectionless UDP exchange on loopback."""
    import threading

    ready = threading.Event()
    port_holder: list[int] = []
    errors: list[BaseException] = []

    def server() -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
                server_socket.bind(("127.0.0.1", 0))
                port_holder.append(server_socket.getsockname()[1])
                ready.set()

                data, client_address = server_socket.recvfrom(4096)
                server_socket.sendto(b"UDP-ACK:" + data, client_address)
        except BaseException as exc:
            errors.append(exc)
            ready.set()

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    ready.wait(timeout=2.0)

    if errors:
        raise RuntimeError(str(errors[0]))
    if not port_holder:
        raise RuntimeError("UDP server did not publish a port.")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(2.0)
        client.sendto(b"datagram", ("127.0.0.1", port_holder[0]))
        response, _ = client.recvfrom(4096)

    thread.join(timeout=1.0)
    return response.decode("utf-8")


try:
    print("UDP response:", run_udp_echo_demo())
except (OSError, RuntimeError) as exc:
    print("UDP demonstration failed:", exc)


# ---------------------------------------------------------------------------
# DNS timing
# ---------------------------------------------------------------------------

section("14. MEASURING DNS LOOKUP TIME")

def measure_dns_lookup(
    hostname: str,
    attempts: int = 3,
) -> list[float]:
    """Measure repeated resolver calls in milliseconds."""
    measurements = []

    for _ in range(attempts):
        started = time.perf_counter()
        try:
            socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        elapsed_ms = (time.perf_counter() - started) * 1000
        measurements.append(elapsed_ms)

    return measurements


measurements = measure_dns_lookup("example.com")

if measurements:
    print("Measurements (ms):", [round(value, 3) for value in measurements])
    print("Minimum:", round(min(measurements), 3), "ms")
    print("Average:", round(statistics.mean(measurements), 3), "ms")
else:
    print("DNS lookup could not be measured.")


# ---------------------------------------------------------------------------
# Connectivity testing
# ---------------------------------------------------------------------------

section("15. NETWORK CONNECTIVITY TESTING")

print(
    """
A useful troubleshooting method tests the network in layers.

Layer 1:
    Does the interface exist and show the expected state?

Layer 2:
    Can the host communicate with local neighbors?

Layer 3:
    Is the IP configuration and routing table correct?

Layer 3/4:
    Can a known IP and port be reached?

Application:
    Does the actual protocol work?

Naming:
    Does DNS resolve the expected hostname?

Security:
    Are firewall, ACL, VPN, proxy, and policy controls affecting traffic?
"""
)

subsection("Testing a TCP port with Python")

def test_tcp_port(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    """Attempt a TCP connection and return a human-readable result."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} accepted a TCP connection"
    except socket.timeout:
        return False, f"{host}:{port} timed out"
    except ConnectionRefusedError:
        return False, f"{host}:{port} actively refused the connection"
    except OSError as exc:
        return False, f"{host}:{port} failed: {exc}"


for host, port in [
    ("example.com", 443),
    ("example.com", 80),
]:
    success, message = test_tcp_port(host, port)
    print("PASS" if success else "FAIL", message)


# ---------------------------------------------------------------------------
# Ping and traceroute
# ---------------------------------------------------------------------------

section("16. PING AND TRACEROUTE")

print(
    """
ping normally uses ICMP Echo Request and Echo Reply for IPv4. IPv6 uses
ICMPv6. Ping is useful for measuring reachability and approximate round-trip
time, but failure does not always prove that the destination is unreachable.
Firewalls and hosts can deliberately filter ICMP.

traceroute/tracert-style tools reveal intermediate hops by exploiting
packet TTL or IPv6 Hop Limit behavior. A hop that does not respond can be
configured to suppress diagnostic traffic without actually forwarding
traffic incorrectly.
"""
)

if command_exists("ping"):
    # Use loopback so the demonstration does not depend on Internet access.
    ping_command = ["ping", "-c", "2", "127.0.0.1"]
    print_command_output(ping_command, timeout=5.0)
else:
    print("'ping' is unavailable.")

for command_name in ["traceroute", "tracepath"]:
    if command_exists(command_name):
        print_command_output([command_name, "127.0.0.1"], timeout=5.0)
        break


# ---------------------------------------------------------------------------
# Routing lookup model
# ---------------------------------------------------------------------------

section("17. ROUTING ALGORITHM MODEL IN PURE PYTHON")

@dataclass(frozen=True)
class Route:
    network: ipaddress._BaseNetwork
    gateway: str | None
    interface: str
    metric: int = 100

    def matches(self, destination: ipaddress._BaseAddress) -> bool:
        return destination in self.network


def choose_route(
    destination_text: str,
    routes: Iterable[Route],
) -> Route | None:
    """
    Simplified longest-prefix-match route selection.

    Real Linux routing decisions are more complex and can include policy
    routing, multiple routing tables, metrics, source address selection,
    firewall marks, VRFs, and other kernel mechanisms.
    """
    destination = ipaddress.ip_address(destination_text)
    candidates = [route for route in routes if route.matches(destination)]

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda route: (-route.network.prefixlen, route.metric),
    )


sample_routes = [
    Route(ipaddress.ip_network("0.0.0.0/0"), "192.168.1.1", "eth0", 100),
    Route(ipaddress.ip_network("192.168.1.0/24"), None, "eth0", 100),
    Route(ipaddress.ip_network("192.168.1.128/25"), None, "eth0", 50),
    Route(ipaddress.ip_network("10.0.0.0/8"), "192.168.1.254", "eth0", 200),
]

for destination in [
    "192.168.1.20",
    "192.168.1.200",
    "10.5.6.7",
    "8.8.8.8",
]:
    route = choose_route(destination, sample_routes)
    if route:
        print(
            f"{destination:15} -> {route.network:18} "
            f"gateway={route.gateway or 'direct':15} "
            f"device={route.interface}"
        )
    else:
        print(destination, "-> no route")


# ---------------------------------------------------------------------------
# Network configuration parser
# ---------------------------------------------------------------------------

section("18. PARSING LINUX IP OUTPUT")

def extract_ipv4_addresses(ip_output: str) -> dict[str, list[str]]:
    """
    Parse common 'ip -o -4 addr' output.

    Example input line:
        2: eth0    inet 192.168.1.10/24 ...
    """
    interface_addresses: dict[str, list[str]] = {}

    pattern = re.compile(
        r"^\d+:\s+([^\s]+)\s+inet\s+([0-9.]+/\d+)"
    )

    for line in ip_output.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue

        interface_name, cidr_address = match.groups()
        interface_addresses.setdefault(interface_name, []).append(cidr_address)

    return interface_addresses


if command_exists("ip"):
    code, output, _ = run_command(["ip", "-o", "-4", "addr", "show"])
    if code == 0:
        parsed = extract_ipv4_addresses(output)
        for interface_name, addresses in parsed.items():
            print(interface_name, "->", ", ".join(addresses))
    else:
        print("Unable to retrieve IPv4 interface data.")


# ---------------------------------------------------------------------------
# Validation and configuration reasoning
# ---------------------------------------------------------------------------

section("19. NETWORK CONFIGURATION VALIDATION")

@dataclass
class InterfaceConfiguration:
    name: str
    address: str
    expected_network: str


def validate_interface_configuration(
    configuration: InterfaceConfiguration,
) -> list[str]:
    """Validate address syntax and expected subnet membership."""
    errors: list[str] = []

    try:
        interface = ipaddress.ip_interface(configuration.address)
    except ValueError as exc:
        return [f"Invalid interface address: {exc}"]

    try:
        network = ipaddress.ip_network(configuration.expected_network, strict=False)
    except ValueError as exc:
        return [f"Invalid expected network: {exc}"]

    if interface.ip not in network:
        errors.append(
            f"{interface.ip} is not inside expected network {network}"
        )

    if interface.version != network.version:
        errors.append("IP version does not match the expected network.")

    return errors


configurations = [
    InterfaceConfiguration("eth0", "192.168.10.25/24", "192.168.10.0/24"),
    InterfaceConfiguration("eth1", "192.168.20.25/24", "192.168.10.0/24"),
    InterfaceConfiguration("eth2", "not-an-ip", "192.168.30.0/24"),
]

for configuration in configurations:
    problems = validate_interface_configuration(configuration)
    if problems:
        print(configuration.name, "INVALID")
        for problem in problems:
            print("  -", problem)
    else:
        print(configuration.name, "VALID")


# ---------------------------------------------------------------------------
# Network troubleshooting workflow
# ---------------------------------------------------------------------------

section("20. SYSTEMATIC NETWORK TROUBLESHOOTING WORKFLOW")

troubleshooting_steps = [
    (
        "1. Interface",
        "ip -br link",
        "Confirm that the expected interface exists and is operational.",
    ),
    (
        "2. Address",
        "ip -br addr",
        "Confirm IPv4/IPv6 addresses and prefix lengths.",
    ),
    (
        "3. Routes",
        "ip route",
        "Confirm connected routes and the expected default route.",
    ),
    (
        "4. Gateway",
        "ip route get <destination>",
        "Ask the kernel which route it would use.",
    ),
    (
        "5. Neighbor",
        "ip neigh",
        "Inspect local IPv4 ARP / neighbor state.",
    ),
    (
        "6. DNS",
        "resolvectl status / getent hosts example.com",
        "Check resolver configuration and actual name resolution.",
    ),
    (
        "7. Port",
        "ss -lntup",
        "Check whether the required service is listening.",
    ),
    (
        "8. Connectivity",
        "ping / tracepath / traceroute",
        "Test reachability and path behavior where permitted.",
    ),
    (
        "9. Application",
        "curl / client application",
        "Test the actual protocol rather than only lower layers.",
    ),
    (
        "10. Security",
        "nft list ruleset / firewall tooling",
        "Check policy controls if lower-level tests succeed but the service fails.",
    ),
]

for title, command, purpose in troubleshooting_steps:
    print(f"{title:15} {command:38} {purpose}")


# ---------------------------------------------------------------------------
# Common failure patterns
# ---------------------------------------------------------------------------

section("21. FAILURE PATTERNS")

failure_patterns = {
    "No interface": [
        "Hardware, driver, VM adapter, or interface naming problem.",
        "Check ip link and kernel logs.",
    ],
    "Interface down": [
        "Administrative or physical link problem.",
        "Check link state and network manager configuration.",
    ],
    "Wrong IP/prefix": [
        "Host may not communicate with intended local subnet.",
        "Compare ip addr output with network design.",
    ],
    "No default route": [
        "Local networks may work while remote networks fail.",
        "Inspect ip route.",
    ],
    "Gateway unreachable": [
        "Local Layer 2 path or gateway configuration may be incorrect.",
        "Inspect ip neigh and interface configuration.",
    ],
    "DNS failure": [
        "Names fail while direct IP connections may work.",
        "Inspect resolv.conf, resolvectl, and resolver behavior.",
    ],
    "Connection refused": [
        "Destination is reachable but no service accepted the TCP connection.",
        "Check server process, listening address, and port.",
    ],
    "Connection timeout": [
        "Traffic may be filtered, routed incorrectly, or the destination may be unavailable.",
        "Compare route, firewall, and packet-path behavior.",
    ],
    "Works locally but not remotely": [
        "Service may be bound only to loopback.",
        "Firewall or security policy may also be responsible.",
    ],
}

for failure, interpretations in failure_patterns.items():
    print(f"\n{failure}")
    for interpretation in interpretations:
        print("  ", interpretation)


# ---------------------------------------------------------------------------
# Performance concepts
# ---------------------------------------------------------------------------

section("22. NETWORK PERFORMANCE")

print(
    """
Important measurements:

Bandwidth:
    Maximum or configured data-transfer capacity.

Throughput:
    Actual useful data transferred per unit time.

Latency:
    Time required for traffic to travel between endpoints.

RTT:
    Round-trip time from sender to destination and back.

Jitter:
    Variation in packet delay.

Packet loss:
    Packets that fail to arrive at the intended destination.

MTU:
    Maximum Transmission Unit. Ethernet commonly uses 1500 bytes, but
    tunnels, VPNs, containers, and specialized networks can use different
    values.

A fast link can still feel slow because of high latency, packet loss,
congestion, DNS delay, server processing, or application behavior.
"""
)

subsection("Local timing example")

def measure_local_socket_connection(
    host: str,
    port: int,
    attempts: int = 3,
) -> list[float]:
    measurements: list[float] = []

    for _ in range(attempts):
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=2.0):
                elapsed = (time.perf_counter() - started) * 1000
                measurements.append(elapsed)
        except OSError:
            pass

    return measurements


connection_times = measure_local_socket_connection("example.com", 443)

if connection_times:
    print(
        "TCP connection times (ms):",
        [round(value, 3) for value in connection_times],
    )
    print(
        "Median:",
        round(statistics.median(connection_times), 3),
        "ms",
    )
else:
    print("No successful TCP measurements were recorded.")


# ---------------------------------------------------------------------------
# Packet capture concepts
# ---------------------------------------------------------------------------

section("23. PACKET CAPTURE")

print(
    """
Packet capture is one of the most powerful troubleshooting techniques.

Common tools:

    tcpdump
    Wireshark
    tshark

A capture can show:

    Ethernet frames
    ARP
    IPv4 / IPv6
    ICMP
    TCP handshakes
    UDP datagrams
    DNS requests
    TLS handshakes
    retransmissions
    TCP resets

Example commands:

    sudo tcpdump -ni any
    sudo tcpdump -ni eth0 port 443
    sudo tcpdump -ni eth0 host 192.168.1.20
    sudo tcpdump -ni eth0 'tcp port 443'

Encrypted application payloads such as HTTPS normally cannot simply be read
from a packet capture. Packet metadata such as addresses, ports, packet
sizes, timing, and handshake information can still be valuable.
"""
)

if command_exists("tcpdump"):
    print("tcpdump is installed.")
else:
    print("tcpdump is not installed; packet capture commands above are examples.")


# ---------------------------------------------------------------------------
# Security considerations
# ---------------------------------------------------------------------------

section("24. NETWORK SECURITY CONSIDERATIONS")

print(
    """
Network configuration is part of the security boundary.

Important practices:

1. Minimize listening services.
2. Bind services to appropriate interfaces.
3. Use host and network firewalls.
4. Avoid exposing administrative ports unnecessarily.
5. Prefer encrypted protocols such as SSH and HTTPS.
6. Validate certificates for TLS services.
7. Protect DNS configuration from unauthorized modification.
8. Restrict management access with appropriate ACLs.
9. Segment sensitive systems into appropriate network zones.
10. Monitor unexpected listening sockets and route changes.
11. Treat packet captures as potentially sensitive data.
12. Do not expose internal addressing, credentials, or private traffic in
    public diagnostic logs.

Security controls can intentionally make diagnostics ambiguous. A timeout can
result from filtering, while a refusal can reveal that a host actively
responded. Diagnostic interpretation must consider the security architecture.
"""
)

subsection("Listening socket inventory")

if command_exists("ss"):
    print_command_output(["ss", "-lntup"])
else:
    print("'ss' is unavailable.")


# ---------------------------------------------------------------------------
# Production considerations
# ---------------------------------------------------------------------------

section("25. PRODUCTION NETWORKING CONSIDERATIONS")

print(
    """
Production troubleshooting should be repeatable and evidence-based.

Record:

    timestamp
    affected host
    interface
    source and destination
    protocol
    port
    observed error
    route information
    DNS result
    relevant firewall state
    application logs
    packet capture when authorized

Avoid changing several variables simultaneously. If five configuration
changes are made at once, identifying the actual cause becomes difficult.

Automation should also avoid destructive operations by default. Commands such
as changing routes, flushing addresses, disabling interfaces, modifying
firewall rules, or rewriting DNS configuration can disconnect a machine.
This study program therefore focuses on inspection and local demonstrations.
"""
)


# ---------------------------------------------------------------------------
# Advanced Linux networking concepts
# ---------------------------------------------------------------------------

section("26. ADVANCED LINUX NETWORKING CONCEPTS")

advanced_topics = {
    "Network namespaces":
        "Provide isolated network stacks and are heavily used by containers.",
    "Virtual Ethernet pairs":
        "Connect network namespaces or virtual network components.",
    "Bridges":
        "Connect Layer-2 interfaces and are common in virtualization.",
    "VLANs":
        "Provide logical Layer-2 segmentation over shared infrastructure.",
    "Bonding":
        "Combines interfaces for redundancy or throughput depending on mode.",
    "Policy routing":
        "Allows routing decisions based on more than destination prefix.",
    "VRF":
        "Provides multiple isolated routing domains on one Linux system.",
    "Netfilter/nftables":
        "Provides packet filtering, NAT, and other kernel networking controls.",
    "Network namespaces":
        "Allow processes to have separate interfaces, routes, and ports.",
    "Containers":
        "Often combine namespaces, virtual Ethernet, bridges, NAT, and DNS.",
    "Socket options":
        "Allow applications to control details such as reuse, buffers, and timeouts.",
    "eBPF":
        "Provides programmable kernel instrumentation and networking capabilities.",
}

for topic, explanation in advanced_topics.items():
    print(f"{topic:25} {explanation}")


# ---------------------------------------------------------------------------
# IPv4 vs IPv6
# ---------------------------------------------------------------------------

section("27. IPv4 AND IPv6 COMPARISON")

comparison = [
    ("Address size", "32 bits", "128 bits"),
    ("Notation", "Dotted decimal", "Colon-separated hexadecimal"),
    ("Broadcast", "Supported", "No traditional broadcast"),
    ("Local neighbor discovery", "ARP", "Neighbor Discovery / ICMPv6"),
    ("Loopback", "127.0.0.1", "::1"),
    ("Private/local addressing", "RFC1918 private ranges", "Unique local addresses and link-local addressing"),
]

print(f"{'Concept':30} {'IPv4':28} IPv6")
print("-" * 90)
for concept, ipv4, ipv6 in comparison:
    print(f"{concept:30} {ipv4:28} {ipv6}")


# ---------------------------------------------------------------------------
# Practical diagnostic function
# ---------------------------------------------------------------------------

section("28. AUTOMATED BASIC HEALTH CHECK")

@dataclass
class HealthCheck:
    name: str
    passed: bool
    detail: str


def basic_network_health_check() -> list[HealthCheck]:
    checks: list[HealthCheck] = []

    # Check loopback resolution.
    try:
        loopback = socket.gethostbyname("localhost")
        checks.append(
            HealthCheck(
                "Local DNS/hosts",
                loopback.startswith("127."),
                f"localhost -> {loopback}",
            )
        )
    except socket.gaierror as exc:
        checks.append(HealthCheck("Local DNS/hosts", False, str(exc)))

    # Check that at least one network interface exists.
    try:
        interfaces = socket.if_nameindex()
        checks.append(
            HealthCheck(
                "Interfaces",
                bool(interfaces),
                f"{len(interfaces)} interface(s) discovered",
            )
        )
    except OSError as exc:
        checks.append(HealthCheck("Interfaces", False, str(exc)))

    # Check loopback TCP connectivity without requiring Internet access.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            checks.append(
                HealthCheck(
                    "Local TCP bind",
                    True,
                    f"Successfully bound local port {server.getsockname()[1]}",
                )
            )
    except OSError as exc:
        checks.append(HealthCheck("Local TCP bind", False, str(exc)))

    return checks


for check in basic_network_health_check():
    status = "PASS" if check.passed else "FAIL"
    print(f"[{status}] {check.name}: {check.detail}")


# ---------------------------------------------------------------------------
# Troubleshooting decision model
# ---------------------------------------------------------------------------

section("29. TROUBLESHOOTING DECISION MODEL")

def diagnose(
    interface_up: bool,
    has_address: bool,
    has_default_route: bool,
    gateway_reachable: bool,
    dns_works: bool,
    service_reachable: bool,
) -> str:
    """
    A deliberately simplified diagnostic decision tree.

    Real incidents require evidence from multiple systems and should not be
    reduced to a single Boolean decision.
    """
    if not interface_up:
        return "Inspect interface state, physical/virtual link, and network manager."
    if not has_address:
        return "Inspect DHCP/static address configuration and prefix length."
    if not has_default_route:
        return "Inspect the routing table and expected gateway configuration."
    if not gateway_reachable:
        return "Inspect local subnet, ARP/neighbor state, gateway, and VLAN configuration."
    if not dns_works:
        return "Inspect DNS configuration and resolver behavior."
    if not service_reachable:
        return "Inspect destination service, firewall, ACL, routing, and port configuration."
    return "Basic connectivity path appears functional; investigate application-level behavior."


scenarios = [
    (False, False, False, False, False, False),
    (True, False, False, False, False, False),
    (True, True, False, False, False, False),
    (True, True, True, False, False, False),
    (True, True, True, True, False, False),
    (True, True, True, True, True, False),
    (True, True, True, True, True, True),
]

for scenario in scenarios:
    print(scenario, "->", diagnose(*scenario))


# ---------------------------------------------------------------------------
# Common mistakes
# ---------------------------------------------------------------------------

section("30. COMMON NETWORKING MISTAKES")

mistakes = [
    "Confusing an interface name with an IP address.",
    "Confusing a MAC address with an IP address.",
    "Assuming interface UP means Internet access works.",
    "Forgetting the subnet prefix length.",
    "Using a gateway outside the directly reachable subnet without appropriate routing.",
    "Assuming a DNS failure means the Internet connection is down.",
    "Assuming ping failure proves TCP/HTTPS failure.",
    "Assuming an open port means the application is healthy.",
    "Binding a service only to loopback when remote access is required.",
    "Exposing a development service directly to an untrusted network.",
    "Changing firewall rules before collecting evidence.",
    "Overwriting /etc/resolv.conf without understanding which service manages it.",
    "Ignoring IPv6 while diagnosing a dual-stack application.",
    "Testing only one destination and concluding that the entire network is broken.",
]

for number, mistake in enumerate(mistakes, start=1):
    print(f"{number:2}. {mistake}")


# ---------------------------------------------------------------------------
# Final study reference
# ---------------------------------------------------------------------------

section("31. COMMAND REFERENCE")

commands = [
    ("ip -br link", "Compact interface state"),
    ("ip -br addr", "Compact IP address configuration"),
    ("ip route", "IPv4 routing table"),
    ("ip -6 route", "IPv6 routing table"),
    ("ip route get 8.8.8.8", "Kernel route decision"),
    ("ip neigh", "IPv4 neighbor table"),
    ("ip -6 neigh", "IPv6 neighbor table"),
    ("ss -lntup", "Listening TCP/UDP sockets"),
    ("resolvectl status", "systemd-resolved status"),
    ("getent hosts example.com", "Resolver-path hostname lookup"),
    ("ping 127.0.0.1", "Basic ICMP reachability test"),
    ("tracepath example.com", "Path/MTU-oriented diagnostic"),
    ("traceroute example.com", "Hop-by-hop path diagnostic"),
    ("tcpdump -ni any", "Packet capture"),
]

for command, purpose in commands:
    print(f"{command:38} {purpose}")


section("32. PROGRAM COMPLETE")

print(
    """
This program intentionally emphasizes observation before modification.

A disciplined Linux networking investigation moves from interface state to
addressing, routing, neighbor discovery, DNS, transport connectivity, and
application behavior. Each layer provides evidence that helps distinguish
local configuration problems from routing, naming, transport, security, or
application failures.
"""
)
