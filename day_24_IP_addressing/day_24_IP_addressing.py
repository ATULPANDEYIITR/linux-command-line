#!/usr/bin/env python3
"""
IP Addressing: IPv4, IPv6, Public IPs, Private IPs, and Address Allocation

A self-contained study and demonstration program covering:
- IPv4 structure and binary representation
- IPv4 subnet masks and CIDR
- Network, broadcast, host, and usable address ranges
- Public and private IPv4 addressing
- Special IPv4 ranges
- VLSM and address allocation
- IPv6 structure and notation
- IPv6 address types and scopes
- IPv6 subnetting
- IPv4 versus IPv6
- NAT concepts
- DHCP and static allocation
- Route summarization
- Address validation and classification
- Practical allocation simulations
- Edge cases, errors, and security considerations

The program uses only Python's standard library.
"""

from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# Section 1: Basic concepts
# ---------------------------------------------------------------------------

def print_title(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def explain_address_basics() -> None:
    print_title("1. IP ADDRESSING FUNDAMENTALS")

    print(
        """
An IP address identifies an interface or endpoint at the network layer.

IPv4 uses 32 bits and is normally written as four decimal octets:

    192.168.1.10

Each octet contains 8 bits and therefore ranges from 0 through 255.

IPv6 uses 128 bits and is normally written as eight groups of hexadecimal
digits:

    2001:db8:1234:0000:0000:0000:0000:0010

An address by itself does not fully describe a network. A prefix length or
subnet mask determines which bits identify the network and which bits are
available to identify interfaces.
"""
    )

    ipv4 = "192.168.1.10"
    octets = [int(part) for part in ipv4.split(".")]
    binary = ".".join(f"{octet:08b}" for octet in octets)

    print(f"IPv4 address:       {ipv4}")
    print(f"Binary form:        {binary}")
    print(f"Total IPv4 bits:    {len(binary.replace('.', ''))}")

    ipv6 = ipaddress.IPv6Address("2001:db8:1234::10")
    print(f"IPv6 address:       {ipv6}")
    print(f"Expanded IPv6:      {ipv6.exploded}")
    print(f"Total IPv6 bits:    {ipv6.max_prefixlen}")


# ---------------------------------------------------------------------------
# Section 2: IPv4 bit-level demonstrations
# ---------------------------------------------------------------------------

def ipv4_to_binary(address: str) -> str:
    """Convert a dotted-decimal IPv4 address into a 32-bit binary string."""
    parsed = ipaddress.IPv4Address(address)
    return f"{int(parsed):032b}"


def binary_to_ipv4(binary: str) -> str:
    """Convert exactly 32 binary digits into dotted-decimal IPv4."""
    if len(binary) != 32 or any(bit not in "01" for bit in binary):
        raise ValueError("Binary IPv4 input must contain exactly 32 bits.")

    octets = [int(binary[index:index + 8], 2) for index in range(0, 32, 8)]
    return ".".join(map(str, octets))


def demonstrate_ipv4_binary() -> None:
    print_title("2. IPV4 BINARY REPRESENTATION")

    address = "192.168.10.25"
    binary = ipv4_to_binary(address)

    print(f"Address: {address}")
    print(f"Binary:  {binary}")
    print(f"Back to IPv4: {binary_to_ipv4(binary)}")

    print("\nThe four octets:")
    for index, octet in enumerate(address.split("."), start=1):
        print(f"  Octet {index}: {octet:>3} = {int(octet):08b}")


# ---------------------------------------------------------------------------
# Section 3: IPv4 subnetting and CIDR
# ---------------------------------------------------------------------------

def cidr_information(cidr: str) -> dict[str, object]:
    """Return common properties of an IPv4 network."""
    network = ipaddress.ip_network(cidr, strict=False)

    if network.version != 4:
        raise ValueError("This function expects an IPv4 network.")

    hosts = list(network.hosts())

    return {
        "network": network,
        "network_address": network.network_address,
        "broadcast_address": network.broadcast_address,
        "prefix_length": network.prefixlen,
        "netmask": network.netmask,
        "hostmask": network.hostmask,
        "total_addresses": network.num_addresses,
        "usable_hosts": len(hosts),
        "first_host": hosts[0] if hosts else None,
        "last_host": hosts[-1] if hosts else None,
    }


def demonstrate_subnetting() -> None:
    print_title("3. IPV4 SUBNETTING AND CIDR")

    examples = [
        "192.168.1.0/24",
        "192.168.1.0/26",
        "10.20.0.0/20",
        "172.16.10.128/25",
        "192.168.1.10/32",
    ]

    for cidr in examples:
        info = cidr_information(cidr)
        print(f"\nCIDR:               {cidr}")
        print(f"Network:            {info['network_address']}")
        print(f"Prefix length:      /{info['prefix_length']}")
        print(f"Subnet mask:        {info['netmask']}")
        print(f"Host mask:          {info['hostmask']}")
        print(f"Total addresses:    {info['total_addresses']}")
        print(f"Usable host count:  {info['usable_hosts']}")
        print(f"First usable host:  {info['first_host']}")
        print(f"Last usable host:   {info['last_host']}")
        print(f"Broadcast:          {info['broadcast_address']}")

    print(
        """
CIDR means Classless Inter-Domain Routing.

The /24 in 192.168.1.0/24 means that the first 24 bits identify the
network prefix. The remaining 8 bits identify addresses within that
network.

For ordinary IPv4 host subnets, two addresses traditionally have special
roles:
- the first address is the network address;
- the final address is the directed broadcast address.

Therefore a /24 has 256 total addresses but normally 254 usable host
addresses. Point-to-point links, infrastructure networks, and modern
routing designs can use address blocks differently, so the usable-host
formula must not be applied blindly to every situation.
"""
    )


# ---------------------------------------------------------------------------
# Section 4: IPv4 address classes, modern classification, and special ranges
# ---------------------------------------------------------------------------

def classify_ipv4(address: str) -> list[str]:
    """Return useful classifications for an IPv4 address."""
    ip = ipaddress.IPv4Address(address)
    labels: list[str] = []

    if ip.is_private:
        labels.append("private")
    if ip.is_global:
        labels.append("globally routable according to Python's address database")
    if ip.is_loopback:
        labels.append("loopback")
    if ip.is_link_local:
        labels.append("link-local")
    if ip.is_multicast:
        labels.append("multicast")
    if ip.is_unspecified:
        labels.append("unspecified")
    if ip.is_reserved:
        labels.append("reserved")
    if ip.is_private and ip in ipaddress.IPv4Network("100.64.0.0/10"):
        labels.append("shared address space / carrier-grade NAT")
    if ip in ipaddress.IPv4Network("192.0.0.0/24"):
        labels.append("IETF protocol-purpose address space")

    return labels or ["ordinary address with no special classification detected"]


def demonstrate_ipv4_classes_and_special_ranges() -> None:
    print_title("4. IPV4 ADDRESS TYPES AND SPECIAL RANGES")

    examples = [
        "8.8.8.8",
        "192.168.1.10",
        "10.0.0.25",
        "172.16.5.10",
        "127.0.0.1",
        "169.254.10.20",
        "224.0.0.1",
        "0.0.0.0",
        "255.255.255.255",
        "100.64.12.5",
        "198.51.100.10",
        "203.0.113.20",
    ]

    for address in examples:
        print(f"{address:16} -> {', '.join(classify_ipv4(address))}")

    print(
        """
Historically, IPv4 was divided into Class A, B, C, D, and E ranges.
Modern IP allocation and routing use CIDR rather than classful addressing.

Important private IPv4 blocks are:
- 10.0.0.0/8
- 172.16.0.0/12
- 192.168.0.0/16

Private addresses are intended for internal networks and are normally not
advertised as ordinary public Internet destinations.

Other important spaces include:
- 127.0.0.0/8: loopback
- 169.254.0.0/16: IPv4 link-local
- 224.0.0.0/4: multicast
- 100.64.0.0/10: shared address space commonly used with carrier-grade NAT
- 192.0.2.0/24: documentation
- 198.51.100.0/24: documentation
- 203.0.113.0/24: documentation

Documentation addresses should not be used as if they were assigned public
Internet addresses.
"""
    )


# ---------------------------------------------------------------------------
# Section 5: Network membership and routing
# ---------------------------------------------------------------------------

def demonstrate_network_membership() -> None:
    print_title("5. NETWORK MEMBERSHIP")

    network = ipaddress.ip_network("192.168.50.0/24")

    candidates = [
        "192.168.50.1",
        "192.168.50.200",
        "192.168.51.1",
        "192.168.50.255",
    ]

    print(f"Network: {network}")
    for candidate in candidates:
        address = ipaddress.ip_address(candidate)
        print(f"{candidate:16} -> {'inside' if address in network else 'outside'}")

    print("\nSubnets of 192.168.50.0/24 when divided into /26 networks:")
    for subnet in network.subnets(new_prefix=26):
        print(f"  {subnet}")


def find_smallest_covering_network(addresses: Iterable[str]) -> ipaddress.IPv4Network:
    """Find the smallest IPv4 network containing all supplied addresses."""
    parsed = [ipaddress.IPv4Address(address) for address in addresses]
    if not parsed:
        raise ValueError("At least one address is required.")

    minimum = min(parsed)
    maximum = max(parsed)
    differing_bits = int(minimum) ^ int(maximum)

    if differing_bits == 0:
        prefix_length = 32
    else:
        prefix_length = 32 - differing_bits.bit_length()

    return ipaddress.ip_network(f"{minimum}/{prefix_length}", strict=False)


def demonstrate_route_summarization() -> None:
    print_title("6. ROUTE SUMMARIZATION")

    networks = [
        ipaddress.ip_network("10.20.0.0/24"),
        ipaddress.ip_network("10.20.1.0/24"),
        ipaddress.ip_network("10.20.2.0/24"),
        ipaddress.ip_network("10.20.3.0/24"),
    ]

    addresses = [str(network.network_address) for network in networks]
    summary = find_smallest_covering_network(addresses)

    print("Individual networks:")
    for network in networks:
        print(f"  {network}")

    print(f"Smallest covering summary: {summary}")

    print(
        """
Route summarization reduces the number of routing entries by representing
multiple contiguous networks with one larger prefix.

A summary must not accidentally include unrelated address space when routing
policy or security policy requires more specific boundaries. Summarization
is therefore both an efficiency technique and a design decision.
"""
    )


# ---------------------------------------------------------------------------
# Section 7: Public and private addressing with NAT
# ---------------------------------------------------------------------------

@dataclass
class NatTranslation:
    private_ip: str
    private_port: int
    public_ip: str
    public_port: int
    destination_ip: str
    destination_port: int


def simulate_pat_translation(
    private_ip: str,
    private_port: int,
    public_ip: str,
    public_port: int,
    destination_ip: str,
    destination_port: int,
) -> NatTranslation:
    """
    Demonstrate the data maintained by a simplified PAT/NAT table.

    Real NAT implementations are more complex and can track protocol,
    connection state, timeouts, checksums, and additional metadata.
    """
    if not ipaddress.ip_address(private_ip).is_private:
        raise ValueError("The simulated source address should be private.")
    if not 1 <= private_port <= 65535:
        raise ValueError("Private port must be between 1 and 65535.")
    if not 1 <= public_port <= 65535:
        raise ValueError("Public port must be between 1 and 65535.")

    return NatTranslation(
        private_ip=private_ip,
        private_port=private_port,
        public_ip=public_ip,
        public_port=public_port,
        destination_ip=destination_ip,
        destination_port=destination_port,
    )


def demonstrate_nat() -> None:
    print_title("7. PRIVATE ADDRESSING AND NAT/PAT")

    translation = simulate_pat_translation(
        private_ip="192.168.1.25",
        private_port=51515,
        public_ip="203.0.113.10",
        public_port=40001,
        destination_ip="198.51.100.40",
        destination_port=443,
    )

    print("Simplified translation:")
    print(
        f"  {translation.private_ip}:{translation.private_port}"
        f" -> {translation.public_ip}:{translation.public_port}"
    )
    print(
        f"  Destination: {translation.destination_ip}:"
        f"{translation.destination_port}"
    )

    print(
        """
NAT changes addressing information between network boundaries.

Port Address Translation (PAT), often called NAT overload, allows many
private clients to share one public IPv4 address by distinguishing flows
using transport-layer ports.

NAT is not equivalent to a firewall. A firewall applies security policy;
NAT primarily changes address and/or port information. A NAT device may
also affect inbound reachability, but security behavior depends on the
actual device and configuration.
"""
    )


# ---------------------------------------------------------------------------
# Section 8: IPv4 address allocation
# ---------------------------------------------------------------------------

@dataclass
class AllocationRequest:
    name: str
    hosts_required: int


def smallest_ipv4_prefix_for_hosts(hosts_required: int) -> int:
    """
    Determine the smallest conventional IPv4 subnet prefix capable of
    providing the requested number of usable host addresses.

    For ordinary LAN-style networks, network and broadcast addresses are
    excluded. /31 and /32 require special handling and are therefore not
    selected by this function.
    """
    if hosts_required < 1:
        raise ValueError("hosts_required must be positive.")

    for prefix in range(30, -1, -1):
        total = 2 ** (32 - prefix)
        usable = total - 2
        if usable >= hosts_required:
            return prefix

    raise ValueError("The request is too large for an IPv4 /0 allocation.")


def allocate_vlsm(
    base_network: str,
    requests: list[AllocationRequest],
) -> list[tuple[str, ipaddress.IPv4Network, int]]:
    """
    Allocate variable-length subnets from a base network.

    Requests are sorted from largest to smallest because allocating large
    blocks first reduces the chance of fragmentation.
    """
    base = ipaddress.ip_network(base_network, strict=True)

    if base.version != 4:
        raise ValueError("VLSM example requires an IPv4 base network.")

    sorted_requests = sorted(
        requests,
        key=lambda request: request.hosts_required,
        reverse=True,
    )

    cursor = int(base.network_address)
    base_end = int(base.broadcast_address)
    results: list[tuple[str, ipaddress.IPv4Network, int]] = []

    for request in sorted_requests:
        prefix = smallest_ipv4_prefix_for_hosts(request.hosts_required)
        block_size = 2 ** (32 - prefix)

        aligned_cursor = ((cursor + block_size - 1) // block_size) * block_size
        candidate = ipaddress.ip_network(
            f"{ipaddress.IPv4Address(aligned_cursor)}/{prefix}",
            strict=True,
        )

        if int(candidate.broadcast_address) > base_end:
            raise ValueError(
                f"Insufficient address space for {request.name} "
                f"requiring {request.hosts_required} hosts."
            )

        results.append((request.name, candidate, request.hosts_required))
        cursor = int(candidate.broadcast_address) + 1

    return results


def demonstrate_vlsm() -> None:
    print_title("8. VARIABLE-LENGTH SUBNET MASKING (VLSM)")

    requests = [
        AllocationRequest("Engineering", 100),
        AllocationRequest("Operations", 50),
        AllocationRequest("Management", 20),
        AllocationRequest("Point-to-point infrastructure", 2),
    ]

    allocations = allocate_vlsm("10.50.0.0/24", requests)

    print("Base network: 10.50.0.0/24")
    print("Allocation order: largest requirement first\n")

    for name, network, requested_hosts in allocations:
        usable = max(network.num_addresses - 2, 0)
        print(
            f"{name:32} {str(network):18} "
            f"requested={requested_hosts:3} usable={usable:3}"
        )

    print(
        """
VLSM allows different subnet sizes inside the same larger allocation.

The traditional host formula for an ordinary IPv4 subnet is:

    usable hosts = 2^(host bits) - 2

The subtraction accounts for the network and broadcast addresses.
This formula is not universally applicable to /31 point-to-point networks,
where both addresses can be used under RFC 3021-style operation.
"""
    )


# ---------------------------------------------------------------------------
# Section 9: DHCP and static addressing concepts
# ---------------------------------------------------------------------------

@dataclass
class DhcpLease:
    client_id: str
    address: ipaddress.IPv4Address
    expires_at: int


class SimpleDhcpPool:
    """
    Educational DHCP pool.

    This is intentionally not a network server. It models the allocation
    state maintained by a simplified address-management system.
    """

    def __init__(self, network: str, first_host: int, last_host: int) -> None:
        self.network = ipaddress.ip_network(network, strict=True)
        self.available = [
            ipaddress.IPv4Address(value)
            for value in range(
                int(self.network.network_address) + first_host,
                int(self.network.network_address) + last_host + 1,
            )
            if ipaddress.IPv4Address(value) in self.network
        ]
        self.leases: dict[str, DhcpLease] = {}

    def request(self, client_id: str, current_time: int, duration: int) -> DhcpLease:
        if client_id in self.leases:
            existing = self.leases[client_id]
            existing.expires_at = current_time + duration
            return existing

        leased_addresses = {lease.address for lease in self.leases.values()}

        for address in self.available:
            if address not in leased_addresses:
                lease = DhcpLease(
                    client_id=client_id,
                    address=address,
                    expires_at=current_time + duration,
                )
                self.leases[client_id] = lease
                return lease

        raise RuntimeError("DHCP pool is exhausted.")

    def release(self, client_id: str) -> None:
        self.leases.pop(client_id, None)

    def expire(self, current_time: int) -> None:
        expired = [
            client_id
            for client_id, lease in self.leases.items()
            if lease.expires_at <= current_time
        ]
        for client_id in expired:
            del self.leases[client_id]


def demonstrate_dhcp() -> None:
    print_title("9. DHCP ADDRESS ALLOCATION")

    pool = SimpleDhcpPool("192.168.100.0/24", 10, 13)

    clients = ["laptop-A", "laptop-B", "printer-A"]

    for client in clients:
        lease = pool.request(client, current_time=1000, duration=3600)
        print(
            f"{client:12} -> {lease.address} "
            f"expires_at={lease.expires_at}"
        )

    pool.release("laptop-B")

    new_lease = pool.request("phone-A", current_time=1100, duration=3600)
    print(f"phone-A      -> {new_lease.address}")

    pool.expire(5000)
    print(f"Leases after expiration: {len(pool.leases)}")

    print(
        """
A DHCP client commonly follows a DORA-style process:

    Discover -> Offer -> Request -> Acknowledgement

DHCP can provide more than an IP address. Depending on the configuration,
clients may receive subnet information, default gateway, DNS servers,
lease duration, and other options.

Static addressing is useful for infrastructure whose address must remain
predictable. DHCP is convenient for large dynamic populations.
"""
    )


# ---------------------------------------------------------------------------
# Section 10: IPv6 fundamentals
# ---------------------------------------------------------------------------

def demonstrate_ipv6() -> None:
    print_title("10. IPV6 ADDRESSING")

    examples = [
        "2001:0db8:0000:0000:0000:ff00:0042:8329",
        "2001:db8::1",
        "::1",
        "fe80::1234",
        "fc00::10",
        "ff02::1",
        "::",
    ]

    for text in examples:
        address = ipaddress.IPv6Address(text)
        print(f"\nInput:       {text}")
        print(f"Compressed:  {address.compressed}")
        print(f"Expanded:    {address.exploded}")
        print(f"Integer:     {int(address)}")
        print(f"Private:     {address.is_private}")
        print(f"Global:      {address.is_global}")
        print(f"Loopback:    {address.is_loopback}")
        print(f"Link-local:  {address.is_link_local}")
        print(f"Multicast:   {address.is_multicast}")
        print(f"Unspecified: {address.is_unspecified}")

    print(
        """
IPv6 addresses contain 128 bits.

Hexadecimal is used because one hexadecimal digit represents four bits.
Eight groups therefore represent 32 hexadecimal digits, equivalent to
128 bits.

IPv6 permits two important textual compression rules:

1. Leading zeros within a 16-bit group may be removed.
2. One contiguous sequence of all-zero groups may be replaced by ::.

The :: notation can appear only once because otherwise the number of
omitted groups would be ambiguous.

IPv6 does not use broadcast addressing. Multicast provides group-oriented
delivery, and neighbor discovery uses ICMPv6 rather than IPv4 ARP.
"""
    )


# ---------------------------------------------------------------------------
# Section 11: IPv6 address categories
# ---------------------------------------------------------------------------

def classify_ipv6(address: str) -> list[str]:
    ip = ipaddress.IPv6Address(address)
    labels: list[str] = []

    if ip.is_loopback:
        labels.append("loopback")
    if ip.is_unspecified:
        labels.append("unspecified")
    if ip.is_link_local:
        labels.append("link-local")
    if ip.is_multicast:
        labels.append("multicast")
    if ip.is_private:
        labels.append("unique-local/private-style")
    if ip.is_global:
        labels.append("global")
    if not labels:
        labels.append("ordinary or special-purpose IPv6 address")

    return labels


def demonstrate_ipv6_categories() -> None:
    print_title("11. IPV6 ADDRESS CATEGORIES")

    examples = {
        "::1": "IPv6 loopback",
        "::": "IPv6 unspecified",
        "fe80::1": "link-local example",
        "fc00::1": "unique-local example",
        "fd12:3456:789a::1": "unique-local example",
        "2001:db8::1": "documentation prefix",
        "ff02::1": "multicast",
    }

    for address, description in examples.items():
        print(
            f"{address:28} {description:30} "
            f"-> {', '.join(classify_ipv6(address))}"
        )

    print(
        """
Important IPv6 concepts include:

- Global unicast: globally routable unicast addressing.
- Link-local: normally fe80::/10 and used for communication on the local link.
- Unique local: fc00::/7, with fd00::/8 commonly used for locally assigned
  unique-local prefixes.
- Multicast: ff00::/8.
- Loopback: ::1.
- Unspecified: ::.

The documentation prefix 2001:db8::/32 is reserved for examples and
documentation and should not be treated as ordinary production public
address space.
"""
    )


# ---------------------------------------------------------------------------
# Section 12: IPv6 subnet allocation
# ---------------------------------------------------------------------------

def demonstrate_ipv6_subnetting() -> None:
    print_title("12. IPV6 SUBNETTING")

    allocation = ipaddress.IPv6Network("2001:db8:abcd::/48")

    print(f"Parent allocation: {allocation}")
    print(f"Prefix length:     /{allocation.prefixlen}")
    print(f"Total addresses:   {allocation.num_addresses:,}")

    subnets = list(allocation.subnets(new_prefix=64))

    print("\nFirst five /64 subnets:")
    for subnet in subnets[:5]:
        print(f"  {subnet}")

    print(
        f"\nNumber of /64 subnets inside the /48: {len(subnets):,}"
    )

    print(
        """
A common IPv6 design assigns /64 prefixes to LAN-like subnets. A /48
contains 16 additional subnet bits before reaching /64, resulting in:

    2^(64 - 48) = 65,536 /64 subnets

IPv6 networks therefore provide enormous address space for hierarchical
allocation. The exact prefix sizes used by service providers, enterprises,
cloud platforms, and special links depend on architecture and policy.
"""
    )


# ---------------------------------------------------------------------------
# Section 13: IPv6 interface identifiers and SLAAC concepts
# ---------------------------------------------------------------------------

def demonstrate_slaac_concept() -> None:
    print_title("13. IPV6 SLAAC CONCEPT")

    prefix = ipaddress.IPv6Network("2001:db8:100:20::/64")
    interface_identifier = ipaddress.IPv6Address("::abcd:1234:5678:9abc")

    if interface_identifier > ipaddress.IPv6Address("::ffff:ffff:ffff:ffff"):
        raise ValueError("Interface identifier does not fit the lower 64 bits.")

    combined = ipaddress.IPv6Address(
        int(prefix.network_address) | int(interface_identifier)
    )

    print(f"Network prefix:      {prefix}")
    print(f"Example IID:         {interface_identifier}")
    print(f"Constructed address: {combined}")

    print(
        """
IPv6 Stateless Address Autoconfiguration (SLAAC) allows hosts to construct
addresses using information advertised by routers.

Modern IPv6 implementations can use privacy-oriented temporary addresses
so that a stable interface identifier is not necessarily exposed in every
outgoing connection.

The historical EUI-64 mechanism is therefore only one part of the history
of IPv6 interface identifiers and should not be assumed to describe every
modern operating system.
"""
    )


# ---------------------------------------------------------------------------
# Section 14: IPv4 versus IPv6 comparison
# ---------------------------------------------------------------------------

def compare_ipv4_ipv6() -> None:
    print_title("14. IPV4 AND IPV6 COMPARISON")

    comparison = [
        ("Address size", "32 bits", "128 bits"),
        ("Typical notation", "Dotted decimal", "Colon-separated hexadecimal"),
        ("Broadcast", "Supported", "Not used"),
        ("Multicast", "224.0.0.0/4", "ff00::/8"),
        ("Loopback", "127.0.0.0/8", "::1"),
        ("Link-local", "169.254.0.0/16", "fe80::/10"),
        ("Private/internal", "RFC 1918 ranges", "Unique-local fc00::/7"),
        ("Neighbor resolution", "ARP", "Neighbor Discovery / ICMPv6"),
        ("Address configuration", "Static/DHCP/common", "Static/DHCPv6/SLAAC"),
        ("NAT dependence", "Widely deployed", "Not required for address scarcity"),
    ]

    for feature, ipv4, ipv6 in comparison:
        print(f"{feature:24} | IPv4: {ipv4:32} | IPv6: {ipv6}")


# ---------------------------------------------------------------------------
# Section 15: Address validation and error handling
# ---------------------------------------------------------------------------

def validate_address_input(value: str) -> str:
    """Return a useful message for valid or invalid IPv4/IPv6 input."""
    value = value.strip()

    if not value:
        return "Invalid: empty input."

    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return f"Invalid IP address: {value}"

    family = "IPv4" if address.version == 4 else "IPv6"

    properties = []
    if address.is_private:
        properties.append("private")
    if address.is_global:
        properties.append("global")
    if address.is_loopback:
        properties.append("loopback")
    if address.is_link_local:
        properties.append("link-local")
    if address.is_multicast:
        properties.append("multicast")
    if address.is_unspecified:
        properties.append("unspecified")

    description = ", ".join(properties) if properties else "ordinary"
    return f"Valid {family}: {address} ({description})"


def demonstrate_validation() -> None:
    print_title("15. VALIDATION AND EDGE CASES")

    test_values = [
        "192.168.1.1",
        "192.168.1.999",
        "2001:db8::1",
        "2001:db8:::1",
        "",
        "127.0.0.1",
        "255.255.255.255",
        "::",
        "::1",
    ]

    for value in test_values:
        print(f"{value!r:24} -> {validate_address_input(value)}")

    print(
        """
Common validation mistakes include:
- accepting an IPv4 octet larger than 255;
- confusing an address with a network;
- accepting malformed IPv6 compression;
- treating a private address as globally routable;
- assuming every IPv4 address can be assigned to a host;
- ignoring address family differences;
- using a documentation address in a production environment.
"""
    )


# ---------------------------------------------------------------------------
# Section 16: Prefix arithmetic
# ---------------------------------------------------------------------------

def prefix_capacity(prefix_length: int, version: int) -> int:
    """Return total addresses represented by a prefix."""
    max_prefix = 32 if version == 4 else 128

    if not 0 <= prefix_length <= max_prefix:
        raise ValueError("Invalid prefix length.")

    return 2 ** (max_prefix - prefix_length)


def demonstrate_prefix_arithmetic() -> None:
    print_title("16. PREFIX-LENGTH ARITHMETIC")

    print("IPv4:")
    for prefix in [8, 16, 24, 25, 26, 27, 30, 31, 32]:
        print(
            f"  /{prefix:<2} -> "
            f"{prefix_capacity(prefix, 4):,} total addresses"
        )

    print("\nIPv6:")
    for prefix in [32, 48, 56, 64, 96, 128]:
        print(
            f"  /{prefix:<3} -> "
            f"{prefix_capacity(prefix, 6):,} total addresses"
        )


# ---------------------------------------------------------------------------
# Section 17: Address planning for an organization
# ---------------------------------------------------------------------------

@dataclass
class Department:
    name: str
    devices: int


def plan_enterprise_network(
    base_network: str,
    departments: list[Department],
) -> list[tuple[str, ipaddress.IPv4Network]]:
    requests = [
        AllocationRequest(department.name, department.devices)
        for department in departments
    ]

    allocations = allocate_vlsm(base_network, requests)
    return [(name, network) for name, network, _ in allocations]


def demonstrate_enterprise_planning() -> None:
    print_title("17. ENTERPRISE ADDRESS PLANNING")

    departments = [
        Department("Research", 180),
        Department("Production", 90),
        Department("Finance", 35),
        Department("Security", 18),
        Department("Network infrastructure", 6),
    ]

    try:
        plan = plan_enterprise_network("10.60.0.0/22", departments)

        for name, network in plan:
            print(f"{name:28} -> {network}")
    except ValueError as error:
        print(f"Allocation error: {error}")

    print(
        """
A practical address plan should consider more than today's device count.

Planning inputs can include:
- current endpoints;
- expected growth;
- VLAN boundaries;
- security zones;
- routing boundaries;
- management networks;
- infrastructure links;
- cloud connectivity;
- VPN users;
- guest networks;
- operational and monitoring systems.

The objective is to avoid both excessive fragmentation and premature
consumption of address space.
"""
    )


# ---------------------------------------------------------------------------
# Section 18: Security considerations
# ---------------------------------------------------------------------------

def demonstrate_security_considerations() -> None:
    print_title("18. SECURITY CONSIDERATIONS")

    security_rules = [
        "Do not treat a private IP address as proof that traffic is trustworthy.",
        "Use firewall policy to control traffic rather than relying on NAT alone.",
        "Validate and normalize IP input before using it in access-control logic.",
        "Do not assume an address is safe because it belongs to a familiar range.",
        "Separate administrative, user, guest, server, and security-sensitive networks.",
        "Apply least privilege to network access.",
        "Monitor unusual address usage and unexpected source addresses.",
        "Consider both IPv4 and IPv6 when implementing security controls.",
        "Avoid security rules that unintentionally protect IPv4 while leaving IPv6 exposed.",
        "Use documentation ranges in examples rather than real production addresses.",
    ]

    for number, rule in enumerate(security_rules, start=1):
        print(f"{number:2}. {rule}")

    print(
        """
IP addressing is a foundation for security architecture, but an IP address
is not an identity in the strong authentication sense. Addresses can be
shared, translated, dynamically assigned, spoofed in some contexts, or
changed over time.

Security systems should therefore combine network addressing with
authentication, authorization, encryption, endpoint controls, logging,
segmentation, and stateful policy where appropriate.
"""
    )


# ---------------------------------------------------------------------------
# Section 19: Performance and design considerations
# ---------------------------------------------------------------------------

def demonstrate_design_tradeoffs() -> None:
    print_title("19. DESIGN TRADE-OFFS")

    tradeoffs = [
        (
            "Static addressing",
            "Predictable infrastructure addresses",
            "Manual administration and configuration drift",
        ),
        (
            "DHCP",
            "Centralized dynamic allocation",
            "Depends on DHCP availability and correct configuration",
        ),
        (
            "Large subnet",
            "Simple addressing and fewer routing boundaries",
            "Potentially larger broadcast/security domain in IPv4",
        ),
        (
            "Many small subnets",
            "Segmentation and controlled routing boundaries",
            "More routing and address-management complexity",
        ),
        (
            "NAT/PAT",
            "Conserves public IPv4 addresses",
            "Breaks end-to-end assumptions and complicates some protocols",
        ),
        (
            "IPv6",
            "Huge address space and hierarchical design",
            "Requires IPv6-aware operational and security practices",
        ),
    ]

    for mechanism, benefit, tradeoff in tradeoffs:
        print(f"\n{mechanism}")
        print(f"  Benefit:  {benefit}")
        print(f"  Tradeoff: {tradeoff}")


# ---------------------------------------------------------------------------
# Section 20: Small interactive analyzer
# ---------------------------------------------------------------------------

def analyze_input(value: str) -> None:
    value = value.strip()

    try:
        if "/" in value:
            network = ipaddress.ip_network(value, strict=False)
            print(f"Network:            {network}")
            print(f"Version:            IPv{network.version}")
            print(f"Network address:    {network.network_address}")
            print(f"Broadcast address:  {network.broadcast_address}")
            print(f"Prefix length:      /{network.prefixlen}")
            print(f"Netmask:            {network.netmask}")
            print(f"Hostmask:           {network.hostmask}")
            print(f"Total addresses:    {network.num_addresses:,}")

            if network.version == 4:
                usable = max(network.num_addresses - 2, 0)
                print(f"Conventional usable hosts: {usable:,}")
            return

        address = ipaddress.ip_address(value)
        print(f"Address:            {address}")
        print(f"Version:            IPv{address.version}")
        print(f"Compressed:         {address.compressed}")
        print(f"Private:            {address.is_private}")
        print(f"Global:             {address.is_global}")
        print(f"Loopback:           {address.is_loopback}")
        print(f"Link-local:         {address.is_link_local}")
        print(f"Multicast:          {address.is_multicast}")
        print(f"Unspecified:        {address.is_unspecified}")

    except ValueError as error:
        print(f"Input error: {error}")


def optional_interactive_mode() -> None:
    print_title("21. OPTIONAL INTERACTIVE IP ANALYZER")
    print(
        "Enter an IP address or CIDR network. Press Enter without input "
        "to return to the main demonstration."
    )

    while True:
        try:
            value = input("IP/CIDR> ").strip()
        except EOFError:
            print()
            break

        if not value:
            break

        analyze_input(value)


# ---------------------------------------------------------------------------
# Section 22: Assertions and educational tests
# ---------------------------------------------------------------------------

def run_self_tests() -> None:
    print_title("22. SELF-TESTS")

    assert ipv4_to_binary("255.255.255.255") == "1" * 32
    assert binary_to_ipv4("0" * 32) == "0.0.0.0"
    assert ipaddress.ip_address("192.168.1.10") in ipaddress.ip_network(
        "192.168.1.0/24"
    )
    assert ipaddress.ip_address("10.0.0.1").is_private
    assert ipaddress.ip_address("127.0.0.1").is_loopback
    assert ipaddress.ip_address("169.254.1.1").is_link_local
    assert ipaddress.ip_address("224.0.0.1").is_multicast
    assert ipaddress.ip_address("::1").is_loopback
    assert ipaddress.ip_address("fe80::1").is_link_local
    assert prefix_capacity(24, 4) == 256
    assert prefix_capacity(64, 6) == 2 ** 64

    assert smallest_ipv4_prefix_for_hosts(1) == 30
    assert smallest_ipv4_prefix_for_hosts(2) == 29
    assert smallest_ipv4_prefix_for_hosts(30) == 27
    assert smallest_ipv4_prefix_for_hosts(62) == 26
    assert smallest_ipv4_prefix_for_hosts(254) == 24

    print("All self-tests passed.")


# ---------------------------------------------------------------------------
# Section 23: Main program
# ---------------------------------------------------------------------------

def main() -> None:
    print_title("IP ADDRESSING STUDY PROGRAM")
    print(
        """
Topic:
    IPv4, IPv6, public IPs, private IPs, and address allocation

This program is an executable reference covering address representation,
subnetting, allocation, classification, routing concepts, NAT, DHCP,
IPv6, validation, security, and network design.
"""
    )

    explain_address_basics()
    demonstrate_ipv4_binary()
    demonstrate_subnetting()
    demonstrate_ipv4_classes_and_special_ranges()
    demonstrate_network_membership()
    demonstrate_route_summarization()
    demonstrate_nat()
    demonstrate_vlsm()
    demonstrate_dhcp()
    demonstrate_ipv6()
    demonstrate_ipv6_categories()
    demonstrate_ipv6_subnetting()
    demonstrate_slaac_concept()
    compare_ipv4_ipv6()
    demonstrate_validation()
    demonstrate_prefix_arithmetic()
    demonstrate_enterprise_planning()
    demonstrate_security_considerations()
    demonstrate_design_tradeoffs()
    run_self_tests()

    # Interactive mode is deliberately disabled by default so the file can
    # run unattended in terminals, IDEs, CI systems, and automated tests.
    #
    # Uncomment the following line for manual experimentation:
    #
    # optional_interactive_mode()

    print_title("END OF IP ADDRESSING DEMONSTRATION")
    print("The examples above can be modified to experiment with different prefixes,")
    print("address ranges, host requirements, and IPv4/IPv6 classification rules.")


if __name__ == "__main__":
    main()
