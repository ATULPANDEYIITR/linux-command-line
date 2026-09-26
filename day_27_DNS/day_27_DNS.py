"""
DNS: Domain Names, Resolution, Records, Recursive Resolvers,
Authoritative Servers, Caching, and Advanced Resolution Behavior.

This standalone study script progresses from absolute beginner concepts
to a practical DNS resolver simulation. It uses only Python's standard
library so it can run without installing third-party packages.

The examples model DNS behavior rather than querying arbitrary external
DNS infrastructure. This makes the demonstrations deterministic,
educational, and safe to run offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import random
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================================
# 1. FUNDAMENTALS: WHAT DNS DOES
# ============================================================================

def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def explain_basic_idea() -> None:
    print_section("1. DNS FUNDAMENTALS")

    print("A domain name is a human-readable name such as www.example.com.")
    print("An IP address identifies a network endpoint.")
    print("DNS maps names to data, commonly IP addresses.")
    print()
    print("Typical conceptual flow:")
    print("Application -> Stub Resolver -> Recursive Resolver")
    print("Recursive Resolver -> Root -> TLD -> Authoritative Server")
    print("Authoritative Server -> DNS Answer")
    print("Recursive Resolver -> Cache -> Application")

    print("\nExample:")
    domain = "www.example.com"
    address = "93.184.216.34"
    print(f"{domain} -> {address}")


# ============================================================================
# 2. DOMAIN NAME STRUCTURE
# ============================================================================

def split_domain_name(domain: str) -> List[str]:
    """
    Split a domain into labels.

    DNS names are hierarchical and are read from right to left:
    www.example.com.
        host  domain TLD root

    The final root label is normally represented by a trailing dot.
    """
    normalized = domain.strip().lower()
    if not normalized:
        return []

    normalized = normalized.rstrip(".")
    return normalized.split(".")


def explain_domain_hierarchy() -> None:
    print_section("2. DOMAIN NAME HIERARCHY")

    examples = [
        "www.example.com.",
        "api.shop.example.com.",
        "mail.department.example.org.",
    ]

    for domain in examples:
        labels = split_domain_name(domain)
        print(f"{domain}")
        for index, label in enumerate(reversed(labels)):
            if index == 0:
                role = "top-level label / TLD"
            elif index == 1:
                role = "registered-domain label"
            else:
                role = "subdomain/host label"
            print(f"  {label:15} -> {role}")

    print("\nThe root zone is represented by the empty label and is commonly")
    print("written as a final dot, for example example.com.")


# ============================================================================
# 3. DNS RECORD TYPES
# ============================================================================

class RecordType(str, Enum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    NS = "NS"
    TXT = "TXT"
    SOA = "SOA"
    PTR = "PTR"


@dataclass(frozen=True)
class DNSRecord:
    name: str
    record_type: RecordType
    value: str
    ttl: int = 300
    priority: Optional[int] = None

    def __post_init__(self) -> None:
        if self.ttl < 0:
            raise ValueError("TTL cannot be negative")

    def __str__(self) -> str:
        priority = f" priority={self.priority}" if self.priority is not None else ""
        return (
            f"{self.name} {self.ttl} IN {self.record_type.value} "
            f"{self.value}{priority}"
        )


def validate_record(record: DNSRecord) -> None:
    """
    Validate several common DNS record rules.

    Real DNS implementations contain more detailed syntax rules. These
    checks intentionally focus on concepts important to learners.
    """
    if not record.name:
        raise ValueError("Record name cannot be empty")

    if record.record_type == RecordType.A:
        ipaddress.IPv4Address(record.value)

    elif record.record_type == RecordType.AAAA:
        ipaddress.IPv6Address(record.value)

    elif record.record_type in {
        RecordType.CNAME,
        RecordType.MX,
        RecordType.NS,
        RecordType.PTR,
    }:
        if not record.value:
            raise ValueError(f"{record.record_type.value} target cannot be empty")

    elif record.record_type == RecordType.MX:
        if record.priority is None:
            raise ValueError("MX records require a priority")


def demonstrate_record_types() -> None:
    print_section("3. DNS RECORD TYPES")

    records = [
        DNSRecord("example.com.", RecordType.A, "192.0.2.10", 300),
        DNSRecord("example.com.", RecordType.AAAA, "2001:db8::10", 300),
        DNSRecord(
            "www.example.com.",
            RecordType.CNAME,
            "example.com.",
            600,
        ),
        DNSRecord(
            "example.com.",
            RecordType.MX,
            "mail.example.com.",
            3600,
            priority=10,
        ),
        DNSRecord(
            "example.com.",
            RecordType.NS,
            "ns1.example.net.",
            86400,
        ),
        DNSRecord(
            "example.com.",
            RecordType.TXT,
            "v=spf1 -all",
            3600,
        ),
        DNSRecord(
            "example.com.",
            RecordType.SOA,
            "ns1.example.net. hostmaster.example.com. 2026092701 3600 600 604800 300",
            3600,
        ),
    ]

    for record in records:
        validate_record(record)
        print(record)

    print("\nImportant distinctions:")
    print("A     -> IPv4 address")
    print("AAAA  -> IPv6 address")
    print("CNAME -> canonical-name alias")
    print("MX    -> mail exchanger")
    print("NS    -> authoritative name server")
    print("TXT   -> arbitrary text used by many verification/security systems")
    print("SOA   -> administrative information for a DNS zone")
    print("PTR   -> reverse-DNS mapping")


# ============================================================================
# 4. ZONES AND AUTHORITATIVE DATA
# ============================================================================

@dataclass
class DNSZone:
    origin: str
    records: Dict[Tuple[str, RecordType], List[DNSRecord]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def __post_init__(self) -> None:
        self.origin = normalize_name(self.origin)

    def add_record(self, record: DNSRecord) -> None:
        name = normalize_name(record.name)
        if not is_subdomain_or_equal(name, self.origin):
            raise ValueError(
                f"{record.name} does not belong to zone {self.origin}"
            )

        validate_record(record)
        normalized = DNSRecord(
            name=name,
            record_type=record.record_type,
            value=normalize_name(record.value)
            if record.record_type
            in {
                RecordType.CNAME,
                RecordType.MX,
                RecordType.NS,
                RecordType.PTR,
            }
            else record.value,
            ttl=record.ttl,
            priority=record.priority,
        )
        self.records[(name, normalized.record_type)].append(normalized)

    def query(
        self,
        name: str,
        record_type: RecordType,
    ) -> List[DNSRecord]:
        return list(
            self.records.get(
                (normalize_name(name), record_type),
                [],
            )
        )


def normalize_name(name: str) -> str:
    """
    Canonicalize a DNS presentation name.

    DNS names are case-insensitive. A final dot represents the root.
    """
    cleaned = name.strip().lower()
    if not cleaned:
        return "."
    if cleaned == ".":
        return "."
    return cleaned.rstrip(".") + "."


def is_subdomain_or_equal(name: str, parent: str) -> bool:
    name = normalize_name(name)
    parent = normalize_name(parent)
    return name == parent or name.endswith("." + parent)


def longest_matching_zone(
    name: str,
    zones: Iterable[DNSZone],
) -> Optional[DNSZone]:
    normalized = normalize_name(name)
    candidates = [
        zone
        for zone in zones
        if is_subdomain_or_equal(normalized, zone.origin)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda zone: len(zone.origin))


# ============================================================================
# 5. DNS SERVER ROLES
# ============================================================================

class ServerRole(str, Enum):
    ROOT = "root"
    TLD = "tld"
    AUTHORITATIVE = "authoritative"
    RECURSIVE = "recursive"


@dataclass
class DNSResponse:
    answer: List[DNSRecord]
    authority: List[DNSRecord] = field(default_factory=list)
    additional: List[DNSRecord] = field(default_factory=list)
    authoritative: bool = False
    from_cache: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class AuthoritativeServer:
    def __init__(self, name: str, zones: Sequence[DNSZone]) -> None:
        self.name = normalize_name(name)
        self.role = ServerRole.AUTHORITATIVE
        self.zones = list(zones)

    def query(
        self,
        name: str,
        record_type: RecordType,
    ) -> DNSResponse:
        zone = longest_matching_zone(name, self.zones)

        if zone is None:
            return DNSResponse(
                answer=[],
                authoritative=False,
                error="REFUSED: server is not authoritative for this name",
            )

        records = zone.query(name, record_type)

        if records:
            return DNSResponse(
                answer=records,
                authoritative=True,
            )

        # A real authoritative server may return NXDOMAIN or NOERROR/NODATA.
        # Here we distinguish a missing name from an existing name with no
        # requested record type only at a simplified educational level.
        known_name = any(
            record_name == normalize_name(name)
            for record_name, _ in zone.records
        )

        if known_name:
            return DNSResponse(
                answer=[],
                authoritative=True,
                error="NOERROR/NODATA",
            )

        return DNSResponse(
            answer=[],
            authoritative=True,
            error="NXDOMAIN",
        )


# ============================================================================
# 6. ROOT AND TLD DELEGATION
# ============================================================================

@dataclass
class Delegation:
    zone_name: str
    name_servers: List[str]


class RootServer:
    """
    Simplified root server.

    The real DNS root system consists of multiple root-server identities
    implemented through many distributed instances. This model represents
    the conceptual role: locating the authoritative servers for a TLD.
    """

    def __init__(self, delegations: Sequence[Delegation]) -> None:
        self.delegations = {
            normalize_name(d.zone_name): d
            for d in delegations
        }
        self.role = ServerRole.ROOT

    def query(self, name: str) -> DNSResponse:
        labels = split_domain_name(name)
        if not labels:
            return DNSResponse([], error="INVALID_NAME")

        tld = normalize_name(labels[-1])
        delegation = self.delegations.get(tld)

        if delegation is None:
            return DNSResponse([], error="NXDOMAIN")

        authority = [
            DNSRecord(
                name=tld,
                record_type=RecordType.NS,
                value=server,
                ttl=86400,
            )
            for server in delegation.name_servers
        ]

        return DNSResponse(
            answer=[],
            authority=authority,
            authoritative=True,
        )


class TLDServer:
    """
    Simplified TLD server.

    Its conceptual job is to delegate a registered domain to its
    authoritative name servers.
    """

    def __init__(self, tld: str, delegations: Sequence[Delegation]) -> None:
        self.tld = normalize_name(tld)
        self.role = ServerRole.TLD
        self.delegations = {
            normalize_name(d.zone_name): d
            for d in delegations
        }

    def query(self, name: str) -> DNSResponse:
        labels = split_domain_name(name)
        if not labels:
            return DNSResponse([], error="INVALID_NAME")

        domain = ".".join(labels[-2:])
        domain = normalize_name(domain)

        if not is_subdomain_or_equal(domain, self.tld):
            return DNSResponse([], error="NOT_IN_THIS_TLD")

        delegation = self.delegations.get(domain)
        if delegation is None:
            return DNSResponse([], error="NXDOMAIN")

        authority = [
            DNSRecord(
                name=domain,
                record_type=RecordType.NS,
                value=server,
                ttl=172800,
            )
            for server in delegation.name_servers
        ]

        return DNSResponse(
            answer=[],
            authority=authority,
            authoritative=True,
        )


# ============================================================================
# 7. CACHE AND TTL
# ============================================================================

@dataclass
class CacheEntry:
    records: List[DNSRecord]
    expires_at: float
    negative: bool = False

    def remaining_ttl(self, now: Optional[float] = None) -> int:
        if now is None:
            now = time.monotonic()
        return max(0, int(self.expires_at - now))


class DNSCache:
    """
    A simplified positive and negative cache.

    Caches normally honor TTL values. Negative caching is also part of DNS,
    with details governed by DNS standards and authoritative SOA information.
    """

    def __init__(self) -> None:
        self.entries: Dict[Tuple[str, RecordType], CacheEntry] = {}

    def get(
        self,
        name: str,
        record_type: RecordType,
        now: Optional[float] = None,
    ) -> Optional[CacheEntry]:
        key = (normalize_name(name), record_type)
        entry = self.entries.get(key)

        if entry is None:
            return None

        if now is None:
            now = time.monotonic()

        if now >= entry.expires_at:
            del self.entries[key]
            return None

        return entry

    def put(
        self,
        name: str,
        record_type: RecordType,
        records: List[DNSRecord],
        ttl: int,
        now: Optional[float] = None,
        negative: bool = False,
    ) -> None:
        if ttl <= 0:
            return

        if now is None:
            now = time.monotonic()

        self.entries[(normalize_name(name), record_type)] = CacheEntry(
            records=list(records),
            expires_at=now + ttl,
            negative=negative,
        )

    def clear(self) -> None:
        self.entries.clear()

    def size(self) -> int:
        return len(self.entries)


def demonstrate_cache() -> None:
    print_section("7. DNS CACHING AND TTL")

    cache = DNSCache()
    now = time.monotonic()

    record = DNSRecord(
        "www.example.com.",
        RecordType.A,
        "192.0.2.10",
        ttl=5,
    )

    cache.put(
        record.name,
        record.record_type,
        [record],
        ttl=record.ttl,
        now=now,
    )

    entry = cache.get(
        record.name,
        record.record_type,
        now=now + 2,
    )

    print("Cache entry after two seconds:")
    print(f"  remaining TTL: {entry.remaining_ttl(now + 2) if entry else 0}")

    expired = cache.get(
        record.name,
        record.record_type,
        now=now + 6,
    )

    print(f"Cache entry after six seconds: {expired}")


# ============================================================================
# 8. RECURSIVE RESOLVER
# ============================================================================

class RecursiveResolver:
    """
    Educational recursive resolver.

    It:
      1. Checks its cache.
      2. Contacts the root.
      3. Contacts the appropriate TLD server.
      4. Contacts an authoritative server.
      5. Follows CNAME records.
      6. Stores useful answers in cache.

    Real recursive resolvers contain substantial additional logic including
    transport handling, DNSSEC validation, retry strategies, rate controls,
    response validation, aggressive caching, ECS behavior in some systems,
    and protection against abuse.
    """

    def __init__(
        self,
        root_server: RootServer,
        tld_servers: Dict[str, TLDServer],
        authoritative_servers: Dict[str, AuthoritativeServer],
        cache: Optional[DNSCache] = None,
    ) -> None:
        self.root_server = root_server
        self.tld_servers = {
            normalize_name(name): server
            for name, server in tld_servers.items()
        }
        self.authoritative_servers = {
            normalize_name(name): server
            for name, server in authoritative_servers.items()
        }
        self.cache = cache or DNSCache()
        self.query_count = 0
        self.trace: List[str] = []

    def resolve(
        self,
        name: str,
        record_type: RecordType = RecordType.A,
        *,
        max_cname_depth: int = 8,
    ) -> DNSResponse:
        self.query_count += 1
        self.trace = []

        normalized = normalize_name(name)

        if not valid_dns_name(normalized):
            return DNSResponse([], error="INVALID_DOMAIN_NAME")

        return self._resolve(
            normalized,
            record_type,
            max_cname_depth,
            visited=set(),
        )

    def _resolve(
        self,
        name: str,
        record_type: RecordType,
        max_cname_depth: int,
        visited: set[str],
    ) -> DNSResponse:
        cached = self.cache.get(name, record_type)

        if cached is not None:
            self.trace.append(f"CACHE HIT: {name} {record_type.value}")
            return DNSResponse(
                answer=cached.records,
                from_cache=True,
                error="NXDOMAIN" if cached.negative else None,
            )

        self.trace.append(f"CACHE MISS: {name} {record_type.value}")

        root_response = self.root_server.query(name)
        self.trace.append("ROOT: locate TLD delegation")

        if root_response.error:
            return root_response

        if not root_response.authority:
            return DNSResponse([], error="ROOT_NO_DELEGATION")

        tld_name = split_domain_name(name)[-1]
        tld_server = self.tld_servers.get(normalize_name(tld_name))

        if tld_server is None:
            return DNSResponse([], error="TLD_SERVER_UNAVAILABLE")

        tld_response = tld_server.query(name)
        self.trace.append(f"TLD: locate authoritative server for {name}")

        if tld_response.error:
            return tld_response

        if not tld_response.authority:
            return DNSResponse([], error="TLD_NO_DELEGATION")

        authority_name = normalize_name(tld_response.authority[0].value)
        authoritative = self.authoritative_servers.get(authority_name)

        if authoritative is None:
            return DNSResponse(
                [],
                error=f"AUTHORITATIVE_SERVER_UNAVAILABLE: {authority_name}",
            )

        self.trace.append(
            f"AUTHORITATIVE: query {authority_name}"
        )

        response = authoritative.query(name, record_type)

        if response.answer:
            minimum_ttl = min(record.ttl for record in response.answer)
            self.cache.put(
                name,
                record_type,
                response.answer,
                minimum_ttl,
            )
            return response

        # Follow CNAME when asking for a non-CNAME record.
        cname_records = authoritative.query(
            name,
            RecordType.CNAME,
        )

        if cname_records and record_type != RecordType.CNAME:
            target = normalize_name(cname_records[0].value)
            self.trace.append(f"CNAME: {name} -> {target}")

            if target in visited:
                return DNSResponse([], error="CNAME_LOOP")

            if len(visited) >= max_cname_depth:
                return DNSResponse([], error="CNAME_CHAIN_TOO_LONG")

            visited.add(name)

            target_response = self._resolve(
                target,
                record_type,
                max_cname_depth,
                visited,
            )

            if target_response.answer:
                return DNSResponse(
                    answer=target_response.answer,
                    authority=cname_records,
                    additional=target_response.additional,
                    authoritative=target_response.authoritative,
                )

            return target_response

        # Cache negative result for a short educational TTL.
        if response.error == "NXDOMAIN":
            self.cache.put(
                name,
                record_type,
                [],
                ttl=30,
                negative=True,
            )

        return response


def valid_dns_name(name: str) -> bool:
    normalized = normalize_name(name)

    if normalized == ".":
        return False

    if len(normalized.rstrip(".")) > 253:
        return False

    labels = normalized.rstrip(".").split(".")

    for label in labels:
        if not label:
            return False
        if len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False

    return True


# ============================================================================
# 9. BUILD A SMALL DNS WORLD
# ============================================================================

def build_demo_dns() -> RecursiveResolver:
    example_zone = DNSZone("example.com.")

    example_zone.add_record(
        DNSRecord(
            "example.com.",
            RecordType.A,
            "192.0.2.10",
            300,
        )
    )

    example_zone.add_record(
        DNSRecord(
            "www.example.com.",
            RecordType.CNAME,
            "example.com.",
            120,
        )
    )

    example_zone.add_record(
        DNSRecord(
            "api.example.com.",
            RecordType.A,
            "192.0.2.20",
            60,
        )
    )

    example_zone.add_record(
        DNSRecord(
            "api.example.com.",
            RecordType.AAAA,
            "2001:db8::20",
            60,
        )
    )

    example_zone.add_record(
        DNSRecord(
            "mail.example.com.",
            RecordType.A,
            "192.0.2.30",
            300,
        )
    )

    example_zone.add_record(
        DNSRecord(
            "example.com.",
            RecordType.MX,
            "mail.example.com.",
            3600,
            priority=10,
        )
    )

    example_zone.add_record(
        DNSRecord(
            "example.com.",
            RecordType.NS,
            "ns1.example.net.",
            86400,
        )
    )

    authoritative = AuthoritativeServer(
        "ns1.example.net.",
        [example_zone],
    )

    root = RootServer(
        [
            Delegation(
                ".com.",
                ["a.gtld-servers.example."],
            )
        ]
    )

    com_tld = TLDServer(
        ".com.",
        [
            Delegation(
                "example.com.",
                ["ns1.example.net."],
            )
        ],
    )

    return RecursiveResolver(
        root_server=root,
        tld_servers={".com.": com_tld},
        authoritative_servers={
            "ns1.example.net.": authoritative,
        },
    )


# ============================================================================
# 10. RESOLUTION DEMONSTRATIONS
# ============================================================================

def demonstrate_resolution() -> None:
    print_section("10. COMPLETE DNS RESOLUTION SIMULATION")

    resolver = build_demo_dns()

    for domain, record_type in [
        ("example.com", RecordType.A),
        ("www.example.com", RecordType.A),
        ("api.example.com", RecordType.AAAA),
        ("example.com", RecordType.MX),
        ("does-not-exist.example.com", RecordType.A),
    ]:
        print(f"\nQuery: {domain} {record_type.value}")

        response = resolver.resolve(domain, record_type)

        for event in resolver.trace:
            print(f"  {event}")

        if response.answer:
            print("  Answer:")
            for record in response.answer:
                print(f"    {record}")
        else:
            print(f"  Result: {response.error}")


def demonstrate_cache_hit() -> None:
    print_section("11. REPEATED QUERY AND CACHE HIT")

    resolver = build_demo_dns()

    first = resolver.resolve("api.example.com", RecordType.A)
    first_trace = list(resolver.trace)

    second = resolver.resolve("api.example.com", RecordType.A)
    second_trace = list(resolver.trace)

    print("First query:")
    for item in first_trace:
        print(f"  {item}")

    print("\nSecond query:")
    for item in second_trace:
        print(f"  {item}")

    print(f"\nFirst response from cache: {first.from_cache}")
    print(f"Second response from cache: {second.from_cache}")


# ============================================================================
# 11. A / AAAA AND DUAL-STACK BEHAVIOR
# ============================================================================

def demonstrate_a_vs_aaaa() -> None:
    print_section("12. A AND AAAA RECORDS")

    resolver = build_demo_dns()

    ipv4 = resolver.resolve("api.example.com", RecordType.A)
    ipv6 = resolver.resolve("api.example.com", RecordType.AAAA)

    print("IPv4 answer:")
    for record in ipv4.answer:
        print(f"  {record}")

    print("IPv6 answer:")
    for record in ipv6.answer:
        print(f"  {record}")

    print(
        "\nApplications using both address families may implement "
        "connection strategies such as Happy Eyeballs."
    )


# ============================================================================
# 12. FORWARD VS REVERSE DNS
# ============================================================================

def ipv4_reverse_name(address: str) -> str:
    """
    Convert an IPv4 address into the in-addr.arpa reverse-DNS name.
    """
    ip = ipaddress.IPv4Address(address)
    reversed_octets = ".".join(reversed(str(ip).split(".")))
    return reversed_octets + ".in-addr.arpa."


def demonstrate_reverse_dns() -> None:
    print_section("13. FORWARD AND REVERSE DNS")

    domain = "server.example.com."
    address = "192.0.2.10"

    print(f"Forward DNS concept: {domain} -> {address}")
    print(
        f"Reverse DNS query name for {address}: "
        f"{ipv4_reverse_name(address)}"
    )

    print(
        "\nReverse DNS commonly uses PTR records and is distinct from "
        "forward A/AAAA lookup."
    )


# ============================================================================
# 13. DNS NEGATIVE ANSWERS
# ============================================================================

def demonstrate_negative_answers() -> None:
    print_section("14. NXDOMAIN, NODATA, AND ERRORS")

    resolver = build_demo_dns()

    missing_name = resolver.resolve(
        "unknown.example.com",
        RecordType.A,
    )

    print("Missing name:")
    print(f"  success={missing_name.success}")
    print(f"  error={missing_name.error}")

    existing_name_wrong_type = resolver.resolve(
        "example.com",
        RecordType.PTR,
    )

    print("\nExisting name but unsupported requested type:")
    print(f"  error={existing_name_wrong_type.error}")

    print(
        "\nNXDOMAIN indicates that the queried domain name does not exist. "
        "NODATA commonly means the name exists but no record of the requested "
        "type is available."
    )


# ============================================================================
# 14. CNAME LOOP EDGE CASE
# ============================================================================

def demonstrate_cname_loop() -> None:
    print_section("15. CNAME LOOP EDGE CASE")

    zone = DNSZone("loop.test.")

    zone.add_record(
        DNSRecord(
            "a.loop.test.",
            RecordType.CNAME,
            "b.loop.test.",
            60,
        )
    )

    zone.add_record(
        DNSRecord(
            "b.loop.test.",
            RecordType.CNAME,
            "a.loop.test.",
            60,
        )
    )

    auth = AuthoritativeServer(
        "ns.loop.test.",
        [zone],
    )

    root = RootServer(
        [Delegation(".test.", ["a.test-servers.example."])]
    )

    tld = TLDServer(
        ".test.",
        [Delegation("loop.test.", ["ns.loop.test."])],
    )

    resolver = RecursiveResolver(
        root,
        {".test.": tld},
        {"ns.loop.test.": auth},
    )

    response = resolver.resolve(
        "a.loop.test.",
        RecordType.A,
    )

    for event in resolver.trace:
        print(f"  {event}")

    print(f"Result: {response.error}")


# ============================================================================
# 15. DNS SECURITY CONCEPTS
# ============================================================================

def demonstrate_security_concepts() -> None:
    print_section("16. DNS SECURITY CONCEPTS")

    security_topics = {
        "DNSSEC":
            "Adds cryptographic authentication of DNS data using signatures.",
        "Cache poisoning":
            "Attempts to cause a resolver to cache forged DNS information.",
        "DNS over TLS (DoT)":
            "Carries DNS messages over TLS for transport privacy.",
        "DNS over HTTPS (DoH)":
            "Carries DNS messages through HTTPS.",
        "DNS over QUIC":
            "Uses QUIC transport for encrypted DNS communication.",
        "Split-horizon DNS":
            "Provides different answers depending on network or client context.",
        "DNS rebinding":
            "An attack pattern that can manipulate DNS answers over time.",
        "Open resolver":
            "A resolver exposed to clients that may be abused for reflection/amplification.",
    }

    for name, description in security_topics.items():
        print(f"{name}: {description}")

    print(
        "\nEncryption of the DNS transport does not itself prove that the "
        "returned DNS data is authentic. DNSSEC addresses data-origin "
        "authentication, while encrypted transports primarily protect the "
        "communication channel."
    )


# ============================================================================
# 16. DNS PERFORMANCE
# ============================================================================

def estimate_resolution_cost(
    root_rtt_ms: float,
    tld_rtt_ms: float,
    auth_rtt_ms: float,
) -> float:
    """
    Approximate sequential cold-cache lookup cost.

    This is deliberately simple. Real DNS can use parallelism, connection
    reuse, local caches, prefetching, and transport-specific optimizations.
    """
    return root_rtt_ms + tld_rtt_ms + auth_rtt_ms


def demonstrate_performance() -> None:
    print_section("17. PERFORMANCE AND CACHING")

    cold_lookup = estimate_resolution_cost(
        root_rtt_ms=25,
        tld_rtt_ms=20,
        auth_rtt_ms=30,
    )

    warm_lookup = 1.5

    print(f"Illustrative cold-cache latency: {cold_lookup:.1f} ms")
    print(f"Illustrative cache-hit latency:  {warm_lookup:.1f} ms")

    print("\nFactors affecting DNS performance:")
    for factor in [
        "Client-side caching",
        "Recursive resolver cache state",
        "Network latency",
        "Number of delegation steps",
        "Authoritative-server latency",
        "Packet loss and retries",
        "Transport selection",
        "DNSSEC validation work",
        "Resolver load",
        "Negative caching",
    ]:
        print(f"  - {factor}")


# ============================================================================
# 17. DOMAIN VALIDATION EDGE CASES
# ============================================================================

def demonstrate_validation() -> None:
    print_section("18. DOMAIN-NAME VALIDATION")

    candidates = [
        "example.com",
        "www.example.com.",
        "",
        "bad..example.com",
        "-bad.example.com",
        "good-name.example.com",
    ]

    for candidate in candidates:
        print(f"{candidate!r:30} -> {valid_dns_name(candidate)}")


# ============================================================================
# 18. DNS MESSAGE CONCEPTS
# ============================================================================

def demonstrate_dns_message_sections() -> None:
    print_section("19. DNS MESSAGE STRUCTURE")

    sections = [
        ("Header", "Transaction metadata, flags, response code, counters"),
        ("Question", "Name, query type, and query class"),
        ("Answer", "Records directly answering the question"),
        ("Authority", "Delegation or authoritative information"),
        ("Additional", "Related records that help interpret the response"),
    ]

    for name, purpose in sections:
        print(f"{name:12} -> {purpose}")

    print("\nCommon response codes:")
    print("  NOERROR  -> successful DNS response")
    print("  NXDOMAIN -> requested name does not exist")
    print("  SERVFAIL -> server could not successfully complete processing")
    print("  REFUSED  -> server refuses to perform the operation")


# ============================================================================
# 19. ITERATIVE VS RECURSIVE QUERIES
# ============================================================================

def demonstrate_query_modes() -> None:
    print_section("20. RECURSIVE VS ITERATIVE RESOLUTION")

    print("Recursive query:")
    print("  Client asks a resolver to obtain the final answer.")

    print("\nIterative query:")
    print("  Server returns the best information it has, often a referral.")
    print("  The querying resolver then contacts another server.")

    print("\nTypical public resolution:")
    print("  Stub client --recursive--> recursive resolver")
    print("  Recursive resolver --iterative--> root/TLD/authoritative servers")


# ============================================================================
# 20. PRODUCTION DESIGN CHECKLIST
# ============================================================================

def production_checklist() -> None:
    print_section("21. PRODUCTION DNS DESIGN")

    checklist = [
        "Use authoritative DNS servers with appropriate redundancy.",
        "Choose TTLs according to operational change requirements.",
        "Monitor authoritative availability and response latency.",
        "Protect recursive resolvers from unauthorized public access.",
        "Validate responses and reject malformed or unexpected data.",
        "Consider DNSSEC where authenticated DNS data is required.",
        "Monitor NXDOMAIN rates for anomalies.",
        "Plan domain and certificate lifecycle management.",
        "Use multiple authoritative locations or providers when appropriate.",
        "Document zone ownership and change procedures.",
        "Avoid unnecessary CNAME chains.",
        "Understand provider-specific propagation behavior.",
    ]

    for item in checklist:
        print(f"[ ] {item}")


# ============================================================================
# 21. MINI TEST SUITE
# ============================================================================

def run_tests() -> None:
    print_section("22. EXECUTABLE TESTS")

    resolver = build_demo_dns()

    response = resolver.resolve(
        "api.example.com",
        RecordType.A,
    )
    assert response.success
    assert response.answer[0].value == "192.0.2.20"

    response = resolver.resolve(
        "api.example.com",
        RecordType.AAAA,
    )
    assert response.success
    assert response.answer[0].value == "2001:db8::20"

    response = resolver.resolve(
        "www.example.com",
        RecordType.A,
    )
    assert response.success
    assert response.answer[0].value == "192.0.2.10"

    response = resolver.resolve(
        "unknown.example.com",
        RecordType.A,
    )
    assert response.error == "NXDOMAIN"

    response = resolver.resolve(
        "api.example.com",
        RecordType.A,
    )
    assert response.from_cache

    try:
        validate_record(
            DNSRecord(
                "invalid.example.com.",
                RecordType.A,
                "not-an-ip",
            )
        )
        raise AssertionError("Invalid IPv4 address was accepted")
    except ValueError:
        pass

    assert ipv4_reverse_name("192.0.2.10") == (
        "10.2.0.192.in-addr.arpa."
    )

    print("All tests passed.")


# ============================================================================
# 22. CAPSTONE: RESOLUTION REPORT
# ============================================================================

def generate_resolution_report(
    resolver: RecursiveResolver,
    domain: str,
    record_type: RecordType,
) -> None:
    print_section("23. CAPSTONE RESOLUTION REPORT")

    start = time.perf_counter()
    response = resolver.resolve(domain, record_type)
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(f"Name:           {normalize_name(domain)}")
    print(f"Type:           {record_type.value}")
    print(f"Success:        {response.success}")
    print(f"Cache hit:      {response.from_cache}")
    print(f"Elapsed:        {elapsed_ms:.4f} ms")
    print(f"Resolver calls: {resolver.query_count}")

    if response.answer:
        print("\nAnswers:")
        for record in response.answer:
            print(f"  {record}")
    else:
        print(f"\nError/status: {response.error}")

    print("\nResolution trace:")
    for event in resolver.trace:
        print(f"  {event}")


# ============================================================================
# 23. MAIN PROGRAM
# ============================================================================

def main() -> None:
    print("DNS COMPLETE STUDY AND RESOLUTION SIMULATOR")
    print("Python standard library only")

    explain_basic_idea()
    explain_domain_hierarchy()
    demonstrate_record_types()
    demonstrate_cache()
    demonstrate_resolution()
    demonstrate_cache_hit()
    demonstrate_a_vs_aaaa()
    demonstrate_reverse_dns()
    demonstrate_negative_answers()
    demonstrate_cname_loop()
    demonstrate_security_concepts()
    demonstrate_performance()
    demonstrate_validation()
    demonstrate_dns_message_sections()
    demonstrate_query_modes()
    production_checklist()
    run_tests()

    resolver = build_demo_dns()
    generate_resolution_report(
        resolver,
        "www.example.com",
        RecordType.A,
    )


if __name__ == "__main__":
    main()
