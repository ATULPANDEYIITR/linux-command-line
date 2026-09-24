# IP addressing: IPv4, IPv6, public IPs, private IPs, and address allocation

## Introduction

IP addressing is the system used to identify interfaces and organize networks at the Internet Protocol layer. Addressing is fundamental to routing because routers use destination IP prefixes to determine where packets should be forwarded.

This study covers IPv4 and IPv6, address representation, CIDR notation, subnetting, public and private address space, special-purpose ranges, NAT, DHCP-style allocation, variable-length subnetting, route summarization, IPv6 address categories, IPv6 subnetting, validation, security considerations, and practical address planning.

The three implementations approach the subject differently:

- Python provides a high-level and standards-aware exploration using the standard `ipaddress` module.
- JavaScript implements important address calculations manually and demonstrates application-level and asynchronous behavior.
- C++ develops an industry-style enterprise network case study with custom IPv4 and IPv6 classes, VLSM allocation, DHCP-style leases, NAT/PAT, validation, and route summarization.

---

## Fundamental concept: what an IP address represents

An IP address is a logical network-layer identifier associated with an interface or endpoint. The address alone is not enough to determine the network boundary. A prefix length or subnet mask defines which portion of the address represents the network prefix.

For example, `192.168.1.25/24` contains two pieces of information:

- `192.168.1.25` is the host address.
- `/24` says that the first 24 bits form the network prefix.

The corresponding network is `192.168.1.0/24`.

A network-layer address should not automatically be interpreted as a permanent identity. Addresses can be dynamically assigned, translated through NAT, shared by multiple users, reassigned to different devices, or used for special purposes.

---

## IPv4

IPv4 uses 32 bits.

The normal textual representation divides those 32 bits into four 8-bit octets:

`192.168.1.25`

Each octet has a range from `0` through `255`.

The four octets contain:

`8 + 8 + 8 + 8 = 32 bits`

The Python implementation converts IPv4 addresses between dotted-decimal and binary forms. The JavaScript implementation converts IPv4 addresses into integer form and applies bit masks. The C++ implementation stores an IPv4 address as a 32-bit unsigned integer.

### Binary representation

For `192.168.10.25`, the binary representation is:

`11000000.10101000.00001010.00011001`

Each decimal octet corresponds to eight binary bits.

Binary representation is useful because subnetting is fundamentally a bit-level operation. A subnet mask selects the network bits while leaving the host bits available for addresses within that network.

---

## IPv4 subnet masks

A subnet mask determines which IPv4 bits represent the network.

A traditional dotted-decimal subnet mask for `/24` is:

`255.255.255.0`

In binary:

`11111111.11111111.11111111.00000000`

The first 24 bits are network bits and the final 8 bits are host bits.

For a `/26`:

`255.255.255.192`

The first 26 bits identify the network and six bits remain for host addressing.

### CIDR notation

CIDR means Classless Inter-Domain Routing.

Instead of relying on historical address classes, CIDR explicitly specifies the prefix length:

- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.1.0/24`
- `192.168.1.0/26`
- `2001:db8::/32`

The number after `/` is the number of leading network bits.

---

## IPv4 address capacity

The total number of addresses in an IPv4 prefix is:

`2^(32 - prefix length)`

Examples:

| Prefix | Total addresses |
|---|---:|
| `/8` | 16,777,216 |
| `/16` | 65,536 |
| `/24` | 256 |
| `/25` | 128 |
| `/26` | 64 |
| `/27` | 32 |
| `/30` | 4 |
| `/31` | 2 |
| `/32` | 1 |

For a conventional IPv4 LAN subnet, the first address represents the network and the last address represents the broadcast address. Therefore the conventional usable-host calculation is:

`2^host_bits - 2`

For example, `/24` has 256 total addresses and traditionally provides 254 ordinary host addresses.

The subtraction is not universal. `/31` point-to-point links are specifically designed to use both addresses as endpoints, while `/32` represents a single address rather than an ordinary multi-host subnet.

The Python, JavaScript, and C++ implementations deliberately distinguish these cases instead of blindly applying the `total - 2` formula to every prefix.

---

## Network address

The network address is produced by applying the subnet mask to the IP address.

Conceptually:

`network = IP address AND subnet mask`

For:

`192.168.1.25/24`

the network is:

`192.168.1.0`

The Python implementation obtains this information through `ipaddress.ip_network`. The JavaScript implementation performs the bit-mask operation directly. The C++ implementation performs the operation using a 32-bit integer.

---

## Broadcast address

In an ordinary IPv4 subnet, the broadcast address has all host bits set to one.

For:

`192.168.1.0/24`

the broadcast address is:

`192.168.1.255`

The broadcast address is used for IPv4 broadcast delivery within the relevant subnet.

IPv6 does not use broadcast addressing. IPv6 uses multicast for group-oriented communication.

---

## Network membership

A basic routing and access-control operation is determining whether an address belongs to a prefix.

For example:

`192.168.1.20` belongs to `192.168.1.0/24`.

`192.168.2.20` does not belong to that prefix.

The JavaScript and C++ implementations explicitly calculate this using a bit mask. This is an important low-level mechanism because network devices repeatedly perform prefix comparisons when processing routes.

The operation is constant time for a fixed-width IP address.

---

## Historical IPv4 classes

Older IPv4 terminology divided address space into Class A, Class B, Class C, Class D, and Class E.

The historical model is useful for understanding the development of IPv4 but is not the modern mechanism for Internet address allocation and routing.

Modern networking uses CIDR prefixes.

The important practical distinction is:

- Classful addressing associates fixed boundaries with historical classes.
- CIDR allows arbitrary prefix lengths such as `/13`, `/21`, `/26`, or `/29`.

The code therefore focuses on prefix lengths rather than attempting to allocate networks according to Class A, B, or C boundaries.

---

## Private IPv4 addresses

The major private IPv4 blocks used for internal addressing are:

| Private block | Prefix |
|---|---|
| `10.0.0.0` through `10.255.255.255` | `/8` |
| `172.16.0.0` through `172.31.255.255` | `/12` |
| `192.168.0.0` through `192.168.255.255` | `/16` |

These ranges are intended for private networks and are not ordinary globally routed Internet destinations.

A private address can be used inside a home, enterprise, laboratory, cloud environment, or other private network.

A device with a private IPv4 address may reach external networks through NAT, a proxy, or another gateway mechanism.

Private addressing does not mean that the host is secure. A private network can still contain compromised systems, malicious traffic, weak access controls, and exposed services.

---

## Public IPv4 addresses

A public IPv4 address is generally an address that can participate in global Internet routing according to allocation and routing policy.

The public/private distinction should not be reduced to a simple numerical test. Some address ranges have special purposes and are neither ordinary private RFC 1918 space nor ordinary public host space.

The Python implementation uses the standard library's address classification properties. The JavaScript and C++ examples explicitly model important ranges for educational purposes.

Production systems should use authoritative address-allocation data and current standards when making security-sensitive or routing-sensitive decisions.

---

## Special IPv4 ranges

Important IPv4 ranges include:

| Range | Purpose |
|---|---|
| `10.0.0.0/8` | Private |
| `172.16.0.0/12` | Private |
| `192.168.0.0/16` | Private |
| `127.0.0.0/8` | Loopback |
| `169.254.0.0/16` | Link-local |
| `224.0.0.0/4` | Multicast |
| `100.64.0.0/10` | Shared address space |
| `192.0.2.0/24` | Documentation |
| `198.51.100.0/24` | Documentation |
| `203.0.113.0/24` | Documentation |

Documentation ranges are particularly useful for technical examples because they should not be confused with actual production public services.

The implementations use documentation addresses such as `203.0.113.10` for simulated public NAT addresses.

---

## Loopback addressing

IPv4 loopback space is `127.0.0.0/8`.

The most familiar address is:

`127.0.0.1`

It refers to the local host.

The Python implementation identifies loopback addresses using `ipaddress`. The JavaScript and C++ implementations explicitly recognize the relevant range or address behavior where appropriate.

IPv6 uses:

`::1`

for loopback.

---

## Link-local addressing

IPv4 link-local addressing uses:

`169.254.0.0/16`

IPv6 link-local addressing uses:

`fe80::/10`

Link-local addresses are designed for communication on the local network segment or link and are not ordinary globally routed addresses.

IPv6 link-local addresses are particularly important because IPv6-enabled interfaces commonly use them for local-link operations and neighbor discovery.

---

## Multicast

IPv4 multicast occupies:

`224.0.0.0/4`

IPv6 multicast occupies:

`ff00::/8`

Multicast represents communication to a group rather than a single destination.

IPv6 relies heavily on multicast because it does not use broadcast.

---

## Shared address space

The IPv4 range:

`100.64.0.0/10`

is designated as shared address space and is commonly associated with carrier-grade NAT deployments.

It should not be treated as equivalent to RFC 1918 private addressing.

The Python demonstration explicitly calls attention to this distinction.

---

## NAT and PAT

Network Address Translation changes address information between network boundaries.

A common IPv4 design uses private addresses internally and translates selected traffic to a public IPv4 address.

Port Address Translation, often called NAT overload, allows multiple internal connections to share one public address by differentiating flows using transport-layer ports.

For example:

`192.168.1.25:51515`

might be represented externally as:

`203.0.113.10:40001`

The JavaScript and C++ programs implement simplified NAT tables.

These implementations intentionally model the central idea rather than attempting to become full protocol-compliant NAT devices.

A production NAT implementation may track:

- source addresses;
- source ports;
- destination addresses;
- destination ports;
- protocol;
- connection state;
- timeouts;
- checksums;
- translation lifecycle;
- filtering policy;
- resource exhaustion.

### NAT is not a firewall

NAT and firewalling are different functions.

NAT changes addressing information. A firewall enforces traffic policy.

A device may provide both functions, but the concepts should not be treated as interchangeable.

---

## DHCP and address allocation

DHCP provides dynamic network configuration to clients.

A common IPv4 DHCP exchange is described as:

`Discover -> Offer -> Request -> Acknowledgement`

DHCP can provide:

- IP address;
- subnet mask;
- default gateway;
- DNS server information;
- lease duration;
- other configuration options.

The Python, JavaScript, and C++ programs implement simplified DHCP-style allocation pools.

These are address-management simulations, not actual DHCP servers.

A production DHCP system must manage:

- leases;
- client identifiers;
- persistence;
- expiration;
- conflict detection;
- reservations;
- failover or high availability;
- network reachability;
- DHCP options;
- security controls;
- concurrent clients.

---

## Static addressing

Static addressing assigns an address explicitly rather than dynamically.

Static addresses are useful for infrastructure whose location must remain predictable, such as:

- routers;
- management interfaces;
- selected servers;
- network appliances;
- monitoring systems;
- infrastructure services.

Static configuration can create administrative overhead and configuration drift when deployed across large populations.

DHCP provides centralized dynamic management but introduces dependencies on DHCP service availability and correct configuration.

---

## Variable-Length Subnet Masking

VLSM means Variable-Length Subnet Masking.

VLSM allows different subnet sizes to be allocated inside one larger address block.

Suppose an organization needs:

- 100 addresses for Engineering;
- 50 for Operations;
- 20 for Management;
- 2 for an infrastructure link.

Giving every group a `/24` would consume substantially more address space than necessary.

VLSM instead assigns different prefix sizes.

The implementations allocate the largest requirements first. This is a common practical strategy because large blocks have stricter alignment requirements and are easier to place before smaller blocks fragment the available address space.

### Host requirement calculation

For an ordinary IPv4 subnet:

`usable hosts = 2^host_bits - 2`

Examples:

| Required hosts | Suitable conventional prefix |
|---:|---:|
| 1 | `/30` |
| 2 | `/29` |
| 20 | `/27` |
| 50 | `/26` |
| 100 | `/25` |
| 180 | `/24` |

The table is based on conventional host-subnet rules and intentionally does not treat `/31` point-to-point addressing as an ordinary LAN subnet.

---

## VLSM implementation

The Python implementation uses the `AllocationRequest` data class and `allocate_vlsm()` function.

The JavaScript implementation uses objects and `allocateVLSM()`.

The C++ implementation defines:

- `AllocationRequest`;
- `Allocation`;
- `prefixForHosts()`;
- `allocateVLSM()`.

The C++ version is the most explicit systems-oriented implementation because it represents addresses as integer values and performs alignment and range checks directly.

The allocation algorithm is:

1. Convert each host requirement to the smallest suitable prefix.
2. Sort requirements from largest to smallest.
3. Start at the beginning of the parent network.
4. Align the cursor to the required block boundary.
5. Allocate the block.
6. Move the cursor to the next available address.
7. Reject the allocation if the block would exceed the parent network.

Sorting requires `O(n log n)` time. The allocation pass itself is `O(n)` after sorting.

---

## Route summarization

Route summarization represents multiple networks using a common larger prefix.

For example:

- `10.20.0.0/24`
- `10.20.1.0/24`
- `10.20.2.0/24`
- `10.20.3.0/24`

can be covered by:

`10.20.0.0/22`

when the address ranges are correctly aligned.

Summarization can reduce routing-table size and simplify routing design.

It must be used carefully. A summary may cover addresses that should not be reachable through the same path.

The Python and C++ implementations calculate a smallest covering prefix for a set of addresses.

---

## IPv6

IPv6 uses 128-bit addresses.

A fully expanded IPv6 address contains eight groups of four hexadecimal digits:

`2001:0db8:0000:0000:0000:ff00:0042:8329`

Each hexadecimal digit represents four bits.

Therefore:

`8 groups × 16 bits = 128 bits`

IPv6 provides a vastly larger address space than IPv4.

The JavaScript implementation manually parses and compresses IPv6 addresses. The C++ implementation creates an `IPv6Address` class that stores eight 16-bit groups.

---

## IPv6 notation

IPv6 supports two important textual compression rules.

### Leading-zero suppression

A group such as:

`0db8`

can be written as:

`db8`

A group containing only zero can be written as:

`0`

### Zero-group compression

One contiguous sequence of zero groups can be replaced by:

`::`

For example:

`2001:0db8:0000:0000:0000:0000:0000:0001`

becomes:

`2001:db8::1`

The `::` notation can occur only once in an address because otherwise it would be impossible to determine how many zero groups were omitted.

When multiple zero runs exist, the longest run is normally selected for compression. A zero run of length one is not normally replaced with `::`.

---

## IPv6 address categories

Important IPv6 categories include:

| Category | Example or prefix |
|---|---|
| Global unicast | `2000::/3` |
| Link-local | `fe80::/10` |
| Unique local | `fc00::/7` |
| Multicast | `ff00::/8` |
| Loopback | `::1` |
| Unspecified | `::` |
| Documentation | `2001:db8::/32` |

Unique-local addressing occupies `fc00::/7`. In practical local deployments, `fd00::/8` is commonly used for locally assigned unique-local prefixes.

The documentation range `2001:db8::/32` is intended for examples and documentation.

---

## IPv6 does not use broadcast

IPv4 has broadcast addressing.

IPv6 does not use broadcast.

IPv6 uses multicast for group communication.

This is an important architectural distinction because IPv6 network behavior should not be modeled simply as IPv4 with a larger address field.

---

## IPv6 Neighbor Discovery

IPv4 commonly uses ARP for address resolution.

IPv6 uses Neighbor Discovery Protocol mechanisms carried by ICMPv6.

Neighbor Discovery supports functions including:

- neighbor resolution;
- router discovery;
- prefix discovery;
- address autoconfiguration support;
- neighbor reachability information.

Security controls must therefore account for ICMPv6 rather than treating all ICMP traffic as unnecessary.

---

## IPv6 SLAAC

SLAAC means Stateless Address Autoconfiguration.

Routers can advertise network prefixes to hosts. Hosts can use the advertised prefix together with an interface identifier to construct IPv6 addresses.

The Python implementation demonstrates the conceptual combination of a `/64` prefix and an interface identifier.

The JavaScript implementation focuses on IPv6 representation and subnet calculations.

Modern IPv6 systems can use privacy-oriented temporary addresses. Therefore, the historical assumption that an interface identifier is always permanently derived from a hardware address is not valid for all modern systems.

---

## IPv6 subnetting

A common IPv6 LAN prefix is `/64`.

Suppose an organization receives:

`2001:db8:abcd::/48`

and assigns `/64` networks to individual segments.

The number of `/64` networks is:

`2^(64 - 48)`

which equals:

`65,536`

The Python implementation directly generates the first `/64` networks using `ipaddress`.

The JavaScript implementation uses `BigInt` because JavaScript's normal `Number` type cannot exactly represent every 128-bit integer.

The C++ implementation calculates the number of available subnets using a 64-bit count for the `/48` to `/64` example.

---

## Why JavaScript needs BigInt for IPv6 arithmetic

JavaScript's ordinary `Number` uses IEEE 754 double-precision floating-point representation.

It cannot exactly represent every integer in the complete 128-bit IPv6 address range.

The JavaScript implementation therefore uses `BigInt` for IPv6 arithmetic.

For example, IPv6 values can be represented using:

`2n ** BigInt(numberOfBits)`

This avoids the precision loss that would occur if a complete IPv6 address were stored as an ordinary JavaScript `Number`.

This is an important language-specific implementation issue.

---

## IPv4 and IPv6 comparison

| Feature | IPv4 | IPv6 |
|---|---|---|
| Address size | 32 bits | 128 bits |
| Normal notation | Dotted decimal | Hexadecimal groups |
| Broadcast | Supported | Not used |
| Multicast | `224.0.0.0/4` | `ff00::/8` |
| Loopback | `127.0.0.0/8` | `::1` |
| Link-local | `169.254.0.0/16` | `fe80::/10` |
| Private/internal addressing | RFC 1918 | Unique local |
| Neighbor discovery | ARP | ICMPv6 Neighbor Discovery |
| Address configuration | Static/DHCP | Static/DHCPv6/SLAAC |
| Address scarcity | Major design constraint | Vast address space |

IPv6 does not merely enlarge IPv4. It changes several architectural assumptions, including neighbor discovery, multicast use, address configuration, and the absence of broadcast.

---

## Python implementation

The Python program uses the standard-library `ipaddress` module.

Important components include:

- `IPv4Address`;
- `IPv4Network`;
- `IPv6Address`;
- `IPv6Network`;
- CIDR parsing;
- network membership;
- subnet generation;
- address classification;
- binary representation;
- VLSM allocation;
- DHCP-style lease management;
- NAT translation modeling;
- route summarization;
- IPv6 subnetting;
- validation.

Python is particularly useful for this topic because the standard library provides mature IP address and network abstractions. This allows the implementation to concentrate on network concepts instead of reproducing every parsing rule manually.

The program also includes executable self-tests.

---

## JavaScript implementation

The JavaScript program deliberately implements several operations manually.

It includes:

- IPv4-to-integer conversion;
- integer-to-IPv4 conversion;
- IPv4 binary conversion;
- CIDR parsing;
- subnet masks;
- network and broadcast calculations;
- network membership;
- subnet generation;
- VLSM allocation;
- DHCP-style pools;
- NAT/PAT modeling;
- IPv6 expansion;
- IPv6 compression;
- IPv6 classification;
- IPv6 subnet arithmetic with `BigInt`;
- asynchronous address provisioning;
- validation and self-tests.

This approach exposes mechanisms that are normally hidden behind networking libraries.

The asynchronous provisioning example also demonstrates how an application could model address allocation as an asynchronous operation without pretending to implement the DHCP protocol itself.

---

## C++ case study

The C++ program models a medium-sized enterprise receiving:

`10.40.0.0/22`

as its internal IPv4 address block.

The organization needs address space for:

- Engineering;
- Production;
- Finance;
- Security;
- Infrastructure.

The program calculates appropriate VLSM subnets and verifies that each allocation remains inside the parent network and does not overlap another allocation.

### Major C++ components

`IPv4Address` represents a 32-bit IPv4 address.

It provides:

- parsing;
- dotted-decimal formatting;
- binary representation;
- integer access;
- comparisons.

`IPv4Network` represents a CIDR network.

It provides:

- prefix length;
- subnet mask;
- network address;
- broadcast address;
- total capacity;
- conventional host capacity;
- membership checking.

`DHCPPool` models a small address-management pool.

It supports:

- lease allocation;
- lease renewal;
- release;
- expiration;
- active-lease counting.

`NATTable` models simplified PAT.

It maps private source addresses and ports to a public address and translated port.

`IPv6Address` stores eight 16-bit groups and demonstrates:

- parsing;
- compression;
- loopback detection;
- unspecified-address detection;
- link-local detection;
- multicast detection;
- unique-local detection.

---

## C++ enterprise allocation scenario

The parent network is:

`10.40.0.0/22`

It contains:

`2^(32-22) = 1024`

total addresses.

The case study sorts department requirements from largest to smallest before allocation.

For example, Engineering requires 180 hosts, so the program determines the smallest conventional subnet that provides at least 180 usable hosts.

A `/24` contains 256 total addresses and 254 conventional usable host addresses.

Production requires 90 hosts, which fits in a `/25`, providing 126 conventional usable hosts.

Finance requires 35 hosts, which fits in a `/26`, providing 62 conventional usable hosts.

Security requires 18 hosts, which fits in a `/27`, providing 30 conventional usable hosts.

Infrastructure requires 6 hosts, which fits in a `/28`, providing 14 conventional usable hosts.

The exact placement is determined by block alignment and the sequential VLSM allocator.

---

## DHCP case study

The C++ program creates a DHCP-style pool inside:

`10.40.3.0/24`

and assigns addresses from:

`10.40.3.50`

through:

`10.40.3.54`

Three clients receive leases.

One lease is then released, allowing another client to receive an available address.

The program also demonstrates lease expiration.

This is an address-management model rather than a real DHCP implementation. It does not send DHCP packets or implement the full DHCP protocol.

---

## NAT/PAT case study

The C++ case study uses the documentation public address:

`203.0.113.10`

as a simulated public address.

Internal connections such as:

`10.40.0.10:51515`

are mapped to a translated public port.

A second internal client can use the same public address because its translated port is different.

The purpose is to demonstrate the central PAT relationship:

`private address + source port -> public address + translated port`

Real NAT implementations require considerably more state and protocol handling.

---

## Route summarization case study

The C++ program takes four contiguous `/24` networks:

- `10.40.8.0/24`
- `10.40.9.0/24`
- `10.40.10.0/24`
- `10.40.11.0/24`

and calculates a covering summary.

The result is:

`10.40.8.0/22`

This demonstrates how several routing entries can sometimes be represented using a single prefix.

A summary is appropriate only when the resulting address range and routing policy are compatible.

---

## Address validation

Address validation is important in:

- configuration systems;
- firewall interfaces;
- network-management software;
- logging pipelines;
- APIs;
- routing tools;
- access-control systems;
- automation.

Common validation errors include:

- accepting an IPv4 octet greater than 255;
- accepting an IPv4 address with too few octets;
- accepting non-numeric IPv4 octets;
- allowing malformed IPv6 compression;
- confusing a host address with a network;
- accepting an invalid prefix length;
- treating a special-purpose range as ordinary public space.

The three implementations deliberately include invalid input tests.

---

## Edge cases

### `/32`

An IPv4 `/32` represents exactly one address.

It is commonly used when a single address is needed, such as a host route or loopback-style route.

### `/31`

A `/31` contains exactly two IPv4 addresses.

It can be used for point-to-point links under appropriate standards and device support.

The conventional `total - 2` LAN-host formula should not automatically be applied to `/31`.

### `/0`

An IPv4 `/0` represents the entire IPv4 address space.

It is commonly associated with a default route.

An IPv6 `/0` similarly represents the entire IPv6 address space.

### IPv6 `::`

`::` represents the unspecified IPv6 address when used as the complete address.

It is not the same thing as the IPv6 loopback address.

### IPv6 `::1`

`::1` is the IPv6 loopback address.

### Multiple IPv6 compression markers

An address such as:

`2001:db8:::1`

is invalid because the compressed zero-group notation is malformed.

### Multiple `::` sequences

An address cannot contain two separate `::` sequences because the number of omitted groups would be ambiguous.

---

## Common mistakes

### Confusing an IP address with a network

`192.168.1.25` is an address.

`192.168.1.0/24` is a network.

The prefix length is essential when discussing network boundaries.

### Treating private addresses as secure

A private address is an addressing property, not a security guarantee.

### Treating NAT as a firewall

NAT and firewalling solve different problems.

### Forgetting IPv6

A security policy that only considers IPv4 can be incomplete when IPv6 is enabled.

### Applying `2^host_bits - 2` to every IPv4 prefix

The formula is a conventional rule for ordinary host subnets, not a universal rule for every possible IPv4 use.

### Using documentation addresses in production

Ranges such as `192.0.2.0/24`, `198.51.100.0/24`, and `203.0.113.0/24` exist for documentation and examples.

### Treating IPv6 as formatted IPv4

IPv6 has different addressing architecture, neighbor discovery, multicast behavior, configuration mechanisms, and address size.

### Using JavaScript Number for full IPv6 arithmetic

A JavaScript `Number` cannot exactly represent the complete 128-bit integer range.

`BigInt` is appropriate for exact IPv6 integer calculations.

### Ignoring address alignment

A subnet must begin at a boundary appropriate to its prefix length. An arbitrary starting address cannot simply be treated as the beginning of any CIDR block.

---

## Performance considerations

IP address calculations are generally efficient because IPv4 and IPv6 addresses have fixed sizes.

IPv4 network membership is a constant-time bit-mask operation.

VLSM allocation involves sorting requests, giving an overall complexity of approximately:

`O(n log n)`

for `n` allocation requests.

The sequential allocation pass after sorting is:

`O(n)`

The C++ DHCP implementation uses an ordered map for lease records, providing logarithmic lookup by client identifier, while scanning the available pool can require time proportional to the pool size.

The Python `ipaddress` module handles the fixed-width address operations efficiently while providing a higher-level API.

JavaScript requires special care with numeric precision when dealing with IPv6. `BigInt` provides exact integer arithmetic but is not interchangeable with `Number`.

---

## Security considerations

IP addressing should be considered part of a broader security architecture.

Important principles include:

- Do not use private addressing as an authentication mechanism.
- Do not assume a local address is trustworthy.
- Use firewalls and explicit policy to control traffic.
- Segment networks according to trust and application requirements.
- Validate addresses before using them in access-control decisions.
- Log dynamic address assignments where operationally necessary.
- Monitor unexpected address assignments.
- Protect both IPv4 and IPv6 paths.
- Ensure routing summaries do not unintentionally expose protected networks.
- Use documentation addresses for technical examples.
- Treat NAT as an address-translation mechanism rather than a substitute for security architecture.

IPv6 security requires explicit attention because disabling or ignoring IPv6 is not a reliable strategy on networks where IPv6 is active.

---

## Address allocation design considerations

A useful address plan considers more than current device count.

Important inputs include:

- current hosts;
- expected growth;
- network segmentation;
- routing boundaries;
- security zones;
- infrastructure links;
- guest networks;
- management networks;
- server networks;
- cloud connectivity;
- VPN requirements;
- monitoring systems;
- operational overhead.

An address plan that allocates every available address immediately can make future expansion difficult.

An address plan that creates excessive fragmentation can increase routing and operational complexity.

VLSM allows the allocation to match actual requirements more closely.

---

## Static addressing versus DHCP

| Characteristic | Static addressing | DHCP |
|---|---|---|
| Predictability | High | Depends on lease/reservation policy |
| Central management | Lower | Higher |
| Manual configuration | Required | Usually reduced |
| Large-scale deployment | Operationally expensive | Well suited |
| Infrastructure use | Common | Also possible with reservations |
| Failure dependency | Configuration-dependent | DHCP availability matters |
| Address changes | Manual | Dynamic |

Neither method is universally appropriate. The correct design depends on the role of the endpoint and operational requirements.

---

## Large subnet versus many small subnets

A large subnet can simplify address planning and routing.

Smaller subnets can provide clearer segmentation and more controlled routing boundaries.

The trade-off is between:

- simplicity;
- address efficiency;
- routing complexity;
- broadcast behavior in IPv4;
- security segmentation;
- administrative overhead;
- growth requirements.

The correct boundary is an architectural decision rather than simply a mathematical calculation.

---

## Public addressing versus private addressing

| Property | Private addressing | Public addressing |
|---|---|---|
| Typical use | Internal networks | Internet-facing/global connectivity |
| RFC 1918 IPv4 examples | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` | Allocated global IPv4 space |
| Internet routing | Not ordinary global destination space | Can be globally routed subject to routing policy |
| NAT commonly used | Often | May be translated or directly used |
| Security meaning | Not inherently trusted | Not inherently untrusted |
| Allocation | Local organization | Address authority/provider allocation |

The distinction is about address scope and allocation, not a direct statement about security.

---

## IPv4 address allocation hierarchy

IPv4 allocation can be understood hierarchically:

`Global allocation -> organization -> site -> network -> subnet -> host`

At Internet scale, address allocation is coordinated through regional Internet registries and other allocation mechanisms.

Within an organization, administrators can divide an assigned block into:

- sites;
- regions;
- buildings;
- VLANs;
- departments;
- server segments;
- infrastructure networks.

CIDR makes this hierarchy flexible.

---

## IPv6 address allocation hierarchy

IPv6's larger address space makes hierarchical allocation particularly important.

An organization might receive a large prefix and divide it into:

- sites;
- departments;
- buildings;
- security zones;
- cloud environments;
- infrastructure segments.

A common design pattern is to assign `/64` prefixes to LAN-like segments.

The large number of available `/64` networks inside a larger allocation supports structured addressing without the same IPv4 scarcity pressure.

---

## Implementation considerations

### Python

Python is suitable for rapid experimentation and network-management utilities.

Its standard `ipaddress` module provides:

- address parsing;
- network objects;
- subnet operations;
- membership tests;
- address properties;
- IPv4 and IPv6 support.

This makes Python useful for configuration generation, validation tools, planning utilities, and educational experiments.

### JavaScript

JavaScript is useful when IP-addressing logic must operate inside:

- browser applications;
- dashboards;
- network-management interfaces;
- Node.js services;
- configuration tools;
- asynchronous web applications.

The implementation shows why numeric representation and `BigInt` matter when JavaScript processes IPv6 addresses.

### C++

C++ is useful when the addressing logic forms part of a performance-sensitive or systems-oriented application.

The case study demonstrates explicit representation of fixed-width network data, class-based modeling, validation, allocation algorithms, and data structures.

---

## Production considerations

The implementations are educational models rather than complete network infrastructure products.

A production IP address-management system may need:

- persistent storage;
- transactional updates;
- concurrency control;
- authentication;
- authorization;
- audit logging;
- conflict detection;
- IPv4 and IPv6 dual-stack support;
- DHCP integration;
- DNS integration;
- cloud-provider integration;
- routing integration;
- high availability;
- backup and recovery;
- monitoring;
- alerting;
- API validation;
- role-based access control;
- configuration versioning.

A real DHCP server must implement the protocol rather than merely allocating addresses from an in-memory collection.

A real NAT device must implement protocol-aware state management and packet processing rather than simply recording translation tuples.

A real routing system must account for routing protocols, administrative distance, metrics, policy, convergence, and forwarding behavior.

---

## Practical applications

IP addressing concepts appear in:

- enterprise networks;
- home networks;
- cloud VPCs and virtual networks;
- data centers;
- Internet service providers;
- carrier networks;
- VPN infrastructure;
- security appliances;
- firewalls;
- routers;
- load balancers;
- service meshes;
- container platforms;
- network monitoring;
- IP address management systems;
- network automation;
- infrastructure-as-code systems.

Understanding prefixes and allocation is especially important when designing systems that span multiple environments.

---

## Relationship between addressing and routing

Addressing and routing are closely connected.

A router does not normally need a separate route for every host. It can use prefixes to represent groups of addresses.

For example:

`10.40.0.0/22`

represents a contiguous range containing 1024 IPv4 addresses.

More-specific routes can represent smaller regions of that space.

Routing therefore depends heavily on:

- prefix length;
- address boundaries;
- longest-prefix matching;
- route aggregation;
- route summarization;
- administrative policy.

The address plan directly affects the structure and scalability of the routing system.

---

## Relationship between addressing and network security

Network segmentation often uses IP prefixes as one component of a security architecture.

For example, an organization may create separate ranges for:

- users;
- production servers;
- development systems;
- security infrastructure;
- management systems;
- guests.

The prefixes make the boundaries explicit, but the security outcome depends on enforcement mechanisms such as firewalls, access-control lists, authentication, endpoint controls, and monitoring.

An IP address should therefore be treated as a network attribute rather than a complete security identity.

---

## Relationship between IPv4 scarcity and NAT

IPv4 has approximately 4.29 billion possible 32-bit address values, but not all values are available as ordinary globally routable host addresses.

The limited global address space contributed to widespread use of private addressing and NAT.

NAT allows many internal devices to share public IPv4 addresses.

This helped extend the practical life of IPv4, but it also introduced architectural complications for applications that benefit from direct end-to-end addressing.

IPv6's 128-bit address space provides a fundamentally larger pool and reduces the need to use NAT merely as an address-conservation mechanism.

---

## Important distinctions

### Private versus public

Private addresses are intended for private addressing environments. Public addresses participate in global Internet addressing subject to allocation and routing.

### Address versus network

An address identifies a specific value. A network prefix describes a range of addresses.

### Subnet mask versus prefix length

A subnet mask is a dotted-decimal representation of IPv4 network bits.

A prefix length is the CIDR representation of the same boundary.

### NAT versus firewall

NAT translates addresses and ports.

A firewall applies security policy.

### IPv4 versus IPv6

IPv6 has a larger address space and different protocol mechanisms. It should not be treated as merely an IPv4 address with additional digits.

### DHCP versus static assignment

DHCP provides dynamic configuration and lease management.

Static assignment explicitly configures an address.

### VLSM versus route summarization

VLSM divides address space into different-sized networks.

Route summarization combines multiple routes into a larger representation when the addressing and routing policy permit it.

---

## Testing demonstrated by the implementations

The programs contain self-tests for important operations.

The Python tests verify:

- IPv4 binary conversion;
- network membership;
- private and special ranges;
- IPv6 loopback;
- IPv6 link-local behavior;
- prefix capacity;
- VLSM calculations.

The JavaScript tests verify:

- IPv4 integer conversion;
- IPv4 binary conversion;
- broadcast calculation;
- network membership;
- IPv6 expansion;
- IPv6 compression;
- IPv6 classification;
- host-capacity calculations.

The C++ tests verify:

- IPv4 round trips;
- IPv4 binary representation;
- broadcast calculation;
- network membership;
- IPv6 categories;
- VLSM allocation.

Testing is especially important for IP-addressing software because one incorrect bit can change the network boundary and potentially affect routing or access-control behavior.

---

## Key formulas

### IPv4 total addresses

`2^(32 - prefix)`

### IPv6 total addresses

`2^(128 - prefix)`

### Conventional IPv4 usable hosts

`2^(32 - prefix) - 2`

for ordinary host subnets where the network and broadcast addresses are excluded.

### Number of IPv6 child prefixes

`2^(child_prefix - parent_prefix)`

For example:

`/48 -> /64`

gives:

`2^(64 - 48) = 65,536`

child `/64` prefixes.

### Network address

Conceptually:

`IP address AND subnet mask`

These formulas form the mathematical foundation of CIDR and subnet planning.

---

## File execution

The Python program can be executed with:

`python ip_addressing.py`

The JavaScript program can be executed with a modern Node.js runtime:

`node ip_addressing.js`

The C++ program can be compiled with C++17 or later:

`g++ -std=c++17 -O2 -Wall -Wextra ip_addressing.cpp -o ip_addressing`

and then executed with:

`./ip_addressing`

On Windows with a compatible compiler, the resulting executable can be run directly.

The programs do not require external libraries.

---

## Scope of the implementations

The code focuses on IP addressing and address allocation rather than implementing complete network protocols.

The Python program uses the standard library to provide standards-aware address manipulation.

The JavaScript program exposes lower-level parsing and arithmetic so that the internal mechanics remain visible.

The C++ program combines address representation, subnet calculation, allocation algorithms, DHCP-style lease management, NAT/PAT modeling, IPv6 processing, route summarization, validation, and testing into one coherent enterprise scenario.

Together, these implementations demonstrate how the same addressing principles can be represented at high-level application, language-runtime, and systems-programming levels.
