"""
Subnetting and CIDR: Complete Study and Demonstration Program

This standalone program teaches IPv4 subnetting from fundamentals through
advanced calculations. It demonstrates:

- IPv4 representation
- Binary conversion
- CIDR notation
- Subnet masks
- Network and broadcast addresses
- Usable host ranges
- Prefix lengths
- Wildcard masks
- Subnet calculations
- Host-count calculations
- Subnet membership
- Address classification
- Private/public addressing
- VLSM
- Supernetting and summarization
- Route containment
- Overlap detection
- Validation
- Edge cases such as /31 and /32
- Address allocation for requirements
- Practical network planning
- Complexity and implementation considerations

No external packages are required.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, summarize_address_range
from typing import Iterable


# ---------------------------------------------------------------------------
# SECTION 1: FUNDAMENTALS
# ---------------------------------------------------------------------------

def heading(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def ipv4_to_int(address: str) -> int:
    """Convert dotted-decimal IPv4 into its 32-bit integer representation."""
    return int(IPv4Address(address))


def int_to_ipv4(value: int) -> str:
    """Convert a 32-bit integer into dotted-decimal IPv4 notation."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("IPv4 integer must be between 0 and 2^32 - 1.")
    return str(IPv4Address(value))


def ipv4_to_binary(address: str) -> str:
    """Return an IPv4 address as four 8-bit binary octets."""
    return ".".join(f"{octet:08b}" for octet in IPv4Address(address).packed)


def mask_to_binary(mask: str) -> str:
    """Return an IPv4 subnet mask in binary."""
    return ipv4_to_binary(mask)


def prefix_to_mask(prefix: int) -> str:
    """
    Convert CIDR prefix length to a dotted-decimal subnet mask.

    Example:
        /24 -> 255.255.255.0
        /26 -> 255.255.255.192
    """
    if not 0 <= prefix <= 32:
        raise ValueError("CIDR prefix must be between 0 and 32.")

    if prefix == 0:
        mask_value = 0
    else:
        mask_value = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF

    return int_to_ipv4(mask_value)


def mask_to_prefix(mask: str) -> int:
    """
    Convert a contiguous IPv4 subnet mask into CIDR prefix length.

    A valid subnet mask contains consecutive 1 bits followed by 0 bits.
    """
    mask_value = ipv4_to_int(mask)
    binary = f"{mask_value:032b}"

    if "01" in binary:
        raise ValueError(
            f"{mask} is not a valid contiguous IPv4 subnet mask."
        )

    return binary.count("1")


def prefix_to_wildcard(prefix: int) -> str:
    """Convert a CIDR prefix to a wildcard mask."""
    mask = ipv4_to_int(prefix_to_mask(prefix))
    wildcard = (~mask) & 0xFFFFFFFF
    return int_to_ipv4(wildcard)


def host_bits(prefix: int) -> int:
    """Return the number of host bits in an IPv4 prefix."""
    if not 0 <= prefix <= 32:
        raise ValueError("Prefix must be between 0 and 32.")
    return 32 - prefix


def total_addresses(prefix: int) -> int:
    """Return the total number of IPv4 addresses in a prefix."""
    return 2 ** host_bits(prefix)


def conventional_usable_hosts(prefix: int) -> int:
    """
    Return usable hosts using the traditional network/broadcast rule.

    /31 and /32 are special cases and therefore return 0 here.
    """
    if prefix >= 31:
        return 0
    return total_addresses(prefix) - 2


def address_count_description(prefix: int) -> str:
    """Explain how many addresses a prefix contains."""
    total = total_addresses(prefix)

    if prefix == 32:
        return "one address"
    if prefix == 31:
        return "two addresses, commonly used for point-to-point links"
    if prefix == 0:
        return f"{total:,} addresses, representing the entire IPv4 space"
    return f"{total:,} total addresses, normally {total - 2:,} usable host addresses"


# ---------------------------------------------------------------------------
# SECTION 2: CORE SUBNET CALCULATION
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubnetInformation:
    """Structured result of a subnet calculation."""

    cidr: str
    address: str
    prefix: int
    subnet_mask: str
    wildcard_mask: str
    network_address: str
    broadcast_address: str
    first_usable: str | None
    last_usable: str | None
    total_addresses: int
    conventional_usable_hosts: int
    host_bits: int
    is_private: bool
    is_loopback: bool
    is_link_local: bool
    is_multicast: bool


def calculate_subnet(cidr: str, strict: bool = False) -> SubnetInformation:
    """
    Calculate all major properties of an IPv4 CIDR network.

    strict=False allows an address such as 192.168.1.37/24 and normalizes it
    to the containing network 192.168.1.0/24.

    strict=True requires the supplied address to already be the network address.
    """
    try:
        network = IPv4Network(cidr, strict=strict)
    except ValueError as exc:
        raise ValueError(f"Invalid CIDR '{cidr}': {exc}") from exc

    prefix = network.prefixlen
    total = network.num_addresses

    if prefix <= 30:
        first = str(network.network_address + 1)
        last = str(network.broadcast_address - 1)
        usable = total - 2
    elif prefix == 31:
        # RFC 3021 allows both addresses on a point-to-point link.
        first = str(network.network_address)
        last = str(network.broadcast_address)
        usable = 2
    else:
        # A /32 represents one individual host address.
        first = str(network.network_address)
        last = str(network.network_address)
        usable = 1

    address = str(network.network_address)

    return SubnetInformation(
        cidr=network.with_prefixlen,
        address=address,
        prefix=prefix,
        subnet_mask=str(network.netmask),
        wildcard_mask=str(network.hostmask),
        network_address=str(network.network_address),
        broadcast_address=str(network.broadcast_address),
        first_usable=first,
        last_usable=last,
        total_addresses=total,
        conventional_usable_hosts=conventional_usable_hosts(prefix),
        host_bits=32 - prefix,
        is_private=network.is_private,
        is_loopback=network.is_loopback,
        is_link_local=network.is_link_local,
        is_multicast=network.is_multicast,
    )


def print_subnet_info(cidr: str) -> None:
    """Display a complete subnet calculation."""
    info = calculate_subnet(cidr)

    print(f"CIDR:                  {info.cidr}")
    print(f"Network address:       {info.network_address}")
    print(f"Prefix length:         /{info.prefix}")
    print(f"Subnet mask:           {info.subnet_mask}")
    print(f"Wildcard mask:         {info.wildcard_mask}")
    print(f"Binary network:        {ipv4_to_binary(info.network_address)}")
    print(f"Binary subnet mask:    {mask_to_binary(info.subnet_mask)}")
    print(f"Host bits:             {info.host_bits}")
    print(f"Total addresses:       {info.total_addresses}")
    print(f"Broadcast address:     {info.broadcast_address}")
    print(f"First usable:          {info.first_usable}")
    print(f"Last usable:           {info.last_usable}")
    print(f"Conventional hosts:    {info.conventional_usable_hosts}")
    print(f"Private:               {info.is_private}")
    print(f"Loopback:              {info.is_loopback}")
    print(f"Link-local:            {info.is_link_local}")
    print(f"Multicast:             {info.is_multicast}")


# ---------------------------------------------------------------------------
# SECTION 3: BASIC CONCEPTS
# ---------------------------------------------------------------------------

def demonstrate_ipv4_binary() -> None:
    heading("IPv4 Address Representation")

    addresses = [
        "0.0.0.0",
        "10.0.0.1",
        "172.16.10.20",
        "192.168.1.100",
        "255.255.255.255",
    ]

    for address in addresses:
        print(f"{address:16} -> {ipv4_to_binary(address)}")


def demonstrate_masks() -> None:
    heading("CIDR Prefixes, Subnet Masks, and Wildcard Masks")

    prefixes = [8, 16, 20, 24, 25, 26, 27, 28, 30, 31, 32]

    print(
        f"{'CIDR':>6} {'Subnet Mask':>18} {'Wildcard':>18} "
        f"{'Addresses':>12} {'Traditional Hosts':>20}"
    )
    print("-" * 82)

    for prefix in prefixes:
        print(
            f"/{prefix:<5} "
            f"{prefix_to_mask(prefix):>18} "
            f"{prefix_to_wildcard(prefix):>18} "
            f"{total_addresses(prefix):>12,} "
            f"{conventional_usable_hosts(prefix):>20,}"
        )


# ---------------------------------------------------------------------------
# SECTION 4: NETWORK ADDRESS CALCULATION BY BITWISE LOGIC
# ---------------------------------------------------------------------------

def calculate_network_bitwise(address: str, prefix: int) -> str:
    """
    Calculate the network address using the fundamental bitwise AND rule.

    Network address = IP address AND subnet mask.
    """
    address_value = ipv4_to_int(address)
    mask_value = ipv4_to_int(prefix_to_mask(prefix))
    return int_to_ipv4(address_value & mask_value)


def demonstrate_bitwise_networking() -> None:
    heading("Bitwise Network Address Calculation")

    address = "192.168.10.77"
    prefix = 26
    mask = prefix_to_mask(prefix)

    print(f"Address:       {address}")
    print(f"Binary:        {ipv4_to_binary(address)}")
    print(f"Mask:          {mask}")
    print(f"Mask binary:   {ipv4_to_binary(mask)}")
    print(f"AND result:    {calculate_network_bitwise(address, prefix)}")

    print("\nThe same calculation through IPv4Network:")
    print(calculate_subnet(f"{address}/{prefix}").network_address)


# ---------------------------------------------------------------------------
# SECTION 5: SUBNET BOUNDARIES
# ---------------------------------------------------------------------------

def subnet_boundaries(cidr: str) -> list[str]:
    """Return all subnet network addresses contained in a parent CIDR."""
    network = IPv4Network(cidr, strict=True)
    return [str(subnet.network_address) for subnet in network.subnets()]


def split_network(cidr: str, new_prefix: int) -> list[IPv4Network]:
    """
    Split a network into equal-size subnets.

    new_prefix must be greater than or equal to the original prefix.
    """
    network = IPv4Network(cidr, strict=True)

    if new_prefix < network.prefixlen:
        raise ValueError("New prefix cannot be shorter than the parent prefix.")

    if new_prefix > 32:
        raise ValueError("Prefix cannot exceed 32.")

    return list(network.subnets(new_prefix=new_prefix))


def demonstrate_equal_subnetting() -> None:
    heading("Equal-Size Subnetting")

    parent = "192.168.10.0/24"

    for new_prefix in [25, 26, 27, 28]:
        subnets = split_network(parent, new_prefix)
        print(
            f"\n{parent} split into /{new_prefix}: "
            f"{len(subnets)} subnets"
        )

        for subnet in subnets:
            print(f"  {subnet}")


# ---------------------------------------------------------------------------
# SECTION 6: HOST REQUIREMENTS
# ---------------------------------------------------------------------------

def minimum_prefix_for_hosts(required_hosts: int) -> int:
    """
    Find the smallest prefix capable of providing the requested number of
    conventional usable hosts.

    For normal Ethernet LAN planning:
        usable hosts = 2^host_bits - 2
    """
    if required_hosts < 1:
        raise ValueError("Required host count must be positive.")

    for prefix in range(31, -1, -1):
        if conventional_usable_hosts(prefix) >= required_hosts:
            return prefix

    raise ValueError("Requirement cannot be represented in IPv4.")


def addresses_needed_for_hosts(required_hosts: int) -> int:
    """Return total addresses required under traditional subnet rules."""
    return 2 ** ((required_hosts + 2 - 1).bit_length())


def demonstrate_host_planning() -> None:
    heading("Choosing a Prefix from Host Requirements")

    requirements = [2, 6, 14, 30, 50, 100, 200, 500, 1000, 2000]

    print(f"{'Required':>10} {'Prefix':>10} {'Mask':>18} {'Usable':>12}")
    print("-" * 54)

    for required in requirements:
        prefix = minimum_prefix_for_hosts(required)
        print(
            f"{required:>10} "
            f"/{prefix:<9} "
            f"{prefix_to_mask(prefix):>18} "
            f"{conventional_usable_hosts(prefix):>12}"
        )


# ---------------------------------------------------------------------------
# SECTION 7: SUBNET MEMBERSHIP
# ---------------------------------------------------------------------------

def ip_belongs_to_subnet(address: str, cidr: str) -> bool:
    """Determine whether an IPv4 address belongs to a CIDR network."""
    return IPv4Address(address) in IPv4Network(cidr, strict=False)


def demonstrate_membership() -> None:
    heading("Subnet Membership")

    tests = [
        ("192.168.1.10", "192.168.1.0/24"),
        ("192.168.1.255", "192.168.1.0/24"),
        ("192.168.2.1", "192.168.1.0/24"),
        ("10.5.10.20", "10.0.0.0/8"),
        ("172.31.10.20", "172.16.0.0/12"),
    ]

    for address, cidr in tests:
        print(f"{address:16} in {cidr:18} -> {ip_belongs_to_subnet(address, cidr)}")


# ---------------------------------------------------------------------------
# SECTION 8: PRIVATE AND SPECIAL ADDRESS SPACE
# ---------------------------------------------------------------------------

def classify_ipv4(address: str) -> str:
    """Return a useful classification for a single IPv4 address."""
    ip = IPv4Address(address)

    if ip.is_loopback:
        return "Loopback"
    if ip.is_link_local:
        return "Link-local"
    if ip.is_multicast:
        return "Multicast"
    if ip.is_private:
        return "Private/reserved according to Python's IPv4 classification"
    if ip == IPv4Address("255.255.255.255"):
        return "Limited broadcast"
    if ip.is_unspecified:
        return "Unspecified"
    return "Globally routed/public space"


def demonstrate_address_classes() -> None:
    heading("IPv4 Address Classification")

    addresses = [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "127.0.0.1",
        "169.254.10.20",
        "224.0.0.1",
        "8.8.8.8",
        "0.0.0.0",
        "255.255.255.255",
    ]

    for address in addresses:
        print(f"{address:18} -> {classify_ipv4(address)}")


# ---------------------------------------------------------------------------
# SECTION 9: VLSM
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VLSMRequirement:
    """One department or network requirement."""

    name: str
    hosts_required: int


@dataclass(frozen=True)
class VLSMAssignment:
    """Allocated CIDR block for a requirement."""

    name: str
    hosts_required: int
    cidr: str
    usable_hosts: int
    first_host: str
    last_host: str


def allocate_vlsm(
    parent_cidr: str,
    requirements: Iterable[VLSMRequirement],
) -> list[VLSMAssignment]:
    """
    Allocate variable-length subnets from a parent network.

    Requirements are sorted by descending host demand. This is important
    because allocating large blocks first reduces fragmentation.
    """
    parent = IPv4Network(parent_cidr, strict=True)

    requirements_list = list(requirements)

    if not requirements_list:
        return []

    if any(r.hosts_required < 1 for r in requirements_list):
        raise ValueError("Every VLSM requirement must request at least one host.")

    sorted_requirements = sorted(
        requirements_list,
        key=lambda requirement: requirement.hosts_required,
        reverse=True,
    )

    assignments: list[VLSMAssignment] = []
    current = int(parent.network_address)

    for requirement in sorted_requirements:
        prefix = minimum_prefix_for_hosts(requirement.hosts_required)
        block_size = total_addresses(prefix)

        # Align the next block to its required subnet boundary.
        remainder = current % block_size
        if remainder:
            current += block_size - remainder

        candidate = IPv4Network(
            f"{int_to_ipv4(current)}/{prefix}",
            strict=True,
        )

        if not candidate.subnet_of(parent):
            raise ValueError(
                f"Requirement '{requirement.name}' does not fit inside "
                f"{parent.with_prefixlen}."
            )

        assignments.append(
            VLSMAssignment(
                name=requirement.name,
                hosts_required=requirement.hosts_required,
                cidr=candidate.with_prefixlen,
                usable_hosts=conventional_usable_hosts(prefix),
                first_host=str(candidate.network_address + 1),
                last_host=str(candidate.broadcast_address - 1),
            )
        )

        current = int(candidate.broadcast_address) + 1

    return assignments


def demonstrate_vlsm() -> None:
    heading("Variable Length Subnet Masking (VLSM)")

    parent = "192.168.50.0/24"

    requirements = [
        VLSMRequirement("Engineering", 60),
        VLSMRequirement("Operations", 30),
        VLSMRequirement("Management", 12),
        VLSMRequirement("Security appliances", 6),
        VLSMRequirement("Point-to-point link", 2),
    ]

    assignments = allocate_vlsm(parent, requirements)

    print(f"Parent network: {parent}")
    print()

    for assignment in assignments:
        print(
            f"{assignment.name:22} "
            f"needs={assignment.hosts_required:3} "
            f"allocated={assignment.cidr:18} "
            f"usable={assignment.usable_hosts:3} "
            f"range={assignment.first_host}-{assignment.last_host}"
        )


# ---------------------------------------------------------------------------
# SECTION 10: SUPERNETTING AND ROUTE SUMMARIZATION
# ---------------------------------------------------------------------------

def summarize_networks(networks: Iterable[str]) -> list[str]:
    """
    Produce the smallest set of CIDR networks that exactly summarizes a set
    of contiguous ranges when possible.
    """
    parsed = [IPv4Network(network, strict=True) for network in networks]

    if not parsed:
        return []

    first = min(network.network_address for network in parsed)
    last = max(network.broadcast_address for network in parsed)

    return [str(network) for network in summarize_address_range(first, last)]


def demonstrate_summarization() -> None:
    heading("Supernetting and Route Summarization")

    networks = [
        "192.168.0.0/24",
        "192.168.1.0/24",
        "192.168.2.0/24",
        "192.168.3.0/24",
    ]

    print("Input networks:")
    for network in networks:
        print(f"  {network}")

    print("\nAddress-range summary:")
    for summary in summarize_networks(networks):
        print(f"  {summary}")

    print(
        "\nFour consecutive /24 networks can be represented by one /22 "
        "when their boundaries are correctly aligned."
    )


# ---------------------------------------------------------------------------
# SECTION 11: OVERLAP DETECTION
# ---------------------------------------------------------------------------

def networks_overlap(first: str, second: str) -> bool:
    """Determine whether two CIDR ranges share any address."""
    a = IPv4Network(first, strict=True)
    b = IPv4Network(second, strict=True)

    return a.overlaps(b)


def validate_network_plan(networks: Iterable[str]) -> list[tuple[str, str]]:
    """Return every overlapping pair in a network plan."""
    parsed = [IPv4Network(network, strict=True) for network in networks]
    overlaps: list[tuple[str, str]] = []

    for index, first in enumerate(parsed):
        for second in parsed[index + 1:]:
            if first.overlaps(second):
                overlaps.append((str(first), str(second)))

    return overlaps


def demonstrate_overlap_detection() -> None:
    heading("Network Overlap Detection")

    plan = [
        "10.0.0.0/24",
        "10.0.1.0/24",
        "10.0.0.128/25",
        "10.0.2.0/24",
    ]

    print("Network plan:")
    for network in plan:
        print(f"  {network}")

    overlaps = validate_network_plan(plan)

    print("\nDetected overlaps:")
    if overlaps:
        for first, second in overlaps:
            print(f"  {first} <-> {second}")
    else:
        print("  None")


# ---------------------------------------------------------------------------
# SECTION 12: ROUTE LOOKUP CONCEPT
# ---------------------------------------------------------------------------

def longest_prefix_match(
    address: str,
    routes: Iterable[str],
) -> str | None:
    """
    Perform a simplified longest-prefix-match routing decision.

    Routers prefer the matching route with the longest prefix.
    """
    ip = IPv4Address(address)
    matching = [
        IPv4Network(route, strict=True)
        for route in routes
        if ip in IPv4Network(route, strict=True)
    ]

    if not matching:
        return None

    best = max(matching, key=lambda network: network.prefixlen)
    return best.with_prefixlen


def demonstrate_longest_prefix_match() -> None:
    heading("Longest Prefix Match")

    routes = [
        "0.0.0.0/0",
        "10.0.0.0/8",
        "10.20.0.0/16",
        "10.20.30.0/24",
    ]

    test_addresses = [
        "8.8.8.8",
        "10.50.1.1",
        "10.20.40.1",
        "10.20.30.77",
    ]

    print("Routing table:")
    for route in routes:
        print(f"  {route}")

    print("\nSelected routes:")
    for address in test_addresses:
        print(f"  {address:16} -> {longest_prefix_match(address, routes)}")


# ---------------------------------------------------------------------------
# SECTION 13: EDGE CASES
# ---------------------------------------------------------------------------

def demonstrate_edge_cases() -> None:
    heading("Important CIDR Edge Cases")

    examples = [
        "0.0.0.0/0",
        "192.168.1.0/30",
        "192.168.1.0/31",
        "192.168.1.50/32",
    ]

    for cidr in examples:
        print()
        print_subnet_info(cidr)

    print(
        "\nTraditional subnetting normally reserves network and broadcast "
        "addresses. /31 is an exception commonly used for point-to-point "
        "links, while /32 represents one host route."
    )


# ---------------------------------------------------------------------------
# SECTION 14: COMMON ERRORS
# ---------------------------------------------------------------------------

def demonstrate_validation() -> None:
    heading("Validation and Common Errors")

    invalid_examples = [
        "192.168.1.0/33",
        "192.168.1.0/24/10",
        "192.168.1.256/24",
        "192.168.1.0/255.0.255.0",
    ]

    for value in invalid_examples:
        try:
            calculate_subnet(value)
        except ValueError as exc:
            print(f"Rejected {value!r}: {exc}")

    invalid_masks = [
        "255.0.255.0",
        "255.255.128.255",
        "255.255.255.1",
    ]

    print()
    for mask in invalid_masks:
        try:
            print(f"{mask} -> /{mask_to_prefix(mask)}")
        except ValueError as exc:
            print(f"Rejected mask {mask}: {exc}")


# ---------------------------------------------------------------------------
# SECTION 15: PRACTICAL NETWORK DESIGN
# ---------------------------------------------------------------------------

@dataclass
class NetworkRequirement:
    """Business requirement for a network segment."""

    department: str
    hosts: int
    purpose: str


def build_practical_plan(
    parent_cidr: str,
    requirements: list[NetworkRequirement],
) -> None:
    """Create and display a practical VLSM network plan."""
    vlsm_requirements = [
        VLSMRequirement(r.department, r.hosts)
        for r in requirements
    ]

    assignments = allocate_vlsm(parent_cidr, vlsm_requirements)

    assignment_by_name = {item.name: item for item in assignments}

    print(f"Parent address space: {parent_cidr}")
    print()
    print(
        f"{'Department':18} {'Purpose':24} "
        f"{'CIDR':18} {'Usable Hosts':14}"
    )
    print("-" * 78)

    for requirement in requirements:
        assignment = assignment_by_name[requirement.department]

        print(
            f"{requirement.department:18} "
            f"{requirement.purpose:24} "
            f"{assignment.cidr:18} "
            f"{assignment.usable_hosts:14}"
        )


def demonstrate_practical_design() -> None:
    heading("Practical Network Design")

    requirements = [
        NetworkRequirement("Engineering", 100, "Application development"),
        NetworkRequirement("Finance", 30, "Financial systems"),
        NetworkRequirement("HR", 20, "Human resources"),
        NetworkRequirement("Security", 12, "Security infrastructure"),
        NetworkRequirement("Network", 6, "Network management"),
    ]

    build_practical_plan("10.100.0.0/23", requirements)


# ---------------------------------------------------------------------------
# SECTION 16: STUDY EXERCISES WITH SOLUTIONS
# ---------------------------------------------------------------------------

def exercise_solutions() -> None:
    heading("Worked Subnetting Exercises")

    exercises = [
        ("192.168.10.0/26", "Four /26 networks fit into a /24."),
        ("172.16.0.0/20", "A /20 contains 4096 total addresses."),
        ("10.20.30.40/27", "The containing network begins at 10.20.30.32."),
    ]

    for cidr, explanation in exercises:
        info = calculate_subnet(cidr)
        print(f"\nInput: {cidr}")
        print(f"Network:   {info.network_address}")
        print(f"Broadcast: {info.broadcast_address}")
        print(f"Hosts:     {info.first_usable} - {info.last_usable}")
        print(f"Explanation: {explanation}")


# ---------------------------------------------------------------------------
# SECTION 17: PERFORMANCE AND SECURITY
# ---------------------------------------------------------------------------

def performance_and_security_notes() -> None:
    heading("Implementation, Performance, and Security Considerations")

    notes = [
        "IPv4 subnet calculations are fundamentally bitwise operations.",
        "Integer-based address calculations are efficient and deterministic.",
        "Network overlap checks across N networks require O(N^2) pairwise "
        "comparisons in the straightforward implementation.",
        "Large routing tables normally require specialized structures or "
        "optimized longest-prefix-match algorithms rather than linear scans.",
        "Subnetting is an addressing mechanism; it does not itself provide "
        "security isolation.",
        "Security boundaries should be enforced with routing policy, ACLs, "
        "firewalls, segmentation controls, authentication, and monitoring.",
        "Incorrect subnet masks can cause unreachable hosts, unintended "
        "routing, overlapping address space, or accidental exposure.",
        "Network plans should reserve address space deliberately for growth.",
    ]

    for index, note in enumerate(notes, start=1):
        print(f"{index}. {note}")


# ---------------------------------------------------------------------------
# SECTION 18: MAIN PROGRAM
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the complete subnetting study program."""
    heading("IPv4 SUBNETTING AND CIDR COMPLETE STUDY PROGRAM")

    print(
        "This program demonstrates IPv4 subnetting from binary fundamentals "
        "to VLSM, route summarization, overlap detection, and routing."
    )

    demonstrate_ipv4_binary()
    demonstrate_masks()
    demonstrate_bitwise_networking()
    demonstrate_equal_subnetting()
    demonstrate_host_planning()
    demonstrate_membership()
    demonstrate_address_classes()
    demonstrate_vlsm()
    demonstrate_summarization()
    demonstrate_overlap_detection()
    demonstrate_longest_prefix_match()
    demonstrate_edge_cases()
    demonstrate_validation()
    demonstrate_practical_design()
    exercise_solutions()
    performance_and_security_notes()

    heading("Interactive Calculator")

    print("Enter a CIDR such as 192.168.1.37/26.")
    print("Press Enter to finish.")

    try:
        user_input = input("CIDR: ").strip()
    except (EOFError, KeyboardInterrupt):
        user_input = ""

    if user_input:
        try:
            print()
            print_subnet_info(user_input)
        except ValueError as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
