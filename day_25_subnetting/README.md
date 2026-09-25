# IPv4 Subnetting and CIDR

## Topic

**Subnetting: CIDR notation, subnet masks, network ranges, hosts, and subnet calculations**

This study implementation presents IPv4 subnetting through three complete programming implementations:

- Python: a broad educational subnet calculator and network-planning toolkit
- JavaScript: executable CIDR and subnetting utilities with application-oriented demonstrations
- C++: an enterprise network-planning case study using classes, VLSM allocation, overlap validation, route summarization, and longest-prefix routing

The implementations use only standard language features and standard libraries.

---

## 1. Introduction to IPv4 Subnetting

IPv4 uses 32-bit addresses.

An IPv4 address is normally written as four decimal octets:

`192.168.10.25`

Each octet represents 8 bits, so:

`8 + 8 + 8 + 8 = 32 bits`

The same address can be represented in binary:

`11000000.10101000.00001010.00011001`

An IPv4 address contains two logical components:

1. A network portion
2. A host portion

The subnet mask determines how many bits belong to the network portion.

For example:

`192.168.10.25/24`

The `/24` means that the first 24 bits are network bits and the remaining 8 bits are host bits.

---

## 2. CIDR Notation

CIDR means **Classless Inter-Domain Routing**.

CIDR expresses an IPv4 network using:

`address/prefix-length`

Examples:

- `10.0.0.0/8`
- `172.16.0.0/16`
- `192.168.1.0/24`
- `192.168.1.64/26`

The number after the slash is the prefix length.

A prefix can range from `/0` through `/32`.

### Prefix interpretation

For `/24`:

- Network bits = 24
- Host bits = 8
- Total bits = 32

Therefore:

`32 - 24 = 8 host bits`

The number of addresses is:

`2^8 = 256`

Under the traditional network/broadcast model, two addresses are reserved:

- Network address
- Broadcast address

Therefore:

`256 - 2 = 254 usable host addresses`

---

## 3. Subnet Masks

A subnet mask is another representation of the prefix.

Common examples include:

| CIDR | Subnet Mask | Host Bits | Total Addresses | Traditional Usable Hosts |
|---|---|---:|---:|---:|
| `/8` | `255.0.0.0` | 24 | 16,777,216 | 16,777,214 |
| `/16` | `255.255.0.0` | 16 | 65,536 | 65,534 |
| `/20` | `255.255.240.0` | 12 | 4,096 | 4,094 |
| `/24` | `255.255.255.0` | 8 | 256 | 254 |
| `/25` | `255.255.255.128` | 7 | 128 | 126 |
| `/26` | `255.255.255.192` | 6 | 64 | 62 |
| `/27` | `255.255.255.224` | 5 | 32 | 30 |
| `/28` | `255.255.255.240` | 4 | 16 | 14 |
| `/29` | `255.255.255.248` | 3 | 8 | 6 |
| `/30` | `255.255.255.252` | 2 | 4 | 2 |
| `/31` | `255.255.255.254` | 1 | 2 | Special |
| `/32` | `255.255.255.255` | 0 | 1 | Special |

The implementations calculate these values instead of storing a fixed lookup table.

---

## 4. Network Address

The network address identifies the subnet itself.

The fundamental calculation is:

`Network Address = IP Address AND Subnet Mask`

For example:

`192.168.10.77/26`

The `/26` mask is:

`255.255.255.192`

The last octet of the address is 77.

The relevant binary values are:

`77  = 01001101`

`192 = 11000000`

Applying bitwise AND:

`01001101`
`11000000`
`--------`
`01000000`

`01000000` is decimal 64.

Therefore:

`192.168.10.77/26`

belongs to:

`192.168.10.64/26`

The Python implementation explicitly demonstrates this calculation in `calculate_network_bitwise()`.

The JavaScript implementation performs the same fundamental operation using bitwise operators.

The C++ implementation performs it in the `IPv4Network` class.

---

## 5. Broadcast Address

For traditional IPv4 subnetting, the broadcast address is the final address in the subnet.

It can be calculated as:

`Broadcast = Network Address OR Wildcard Mask`

The wildcard mask is the inverse of the subnet mask.

For `/26`:

Subnet mask:

`255.255.255.192`

Wildcard:

`0.0.0.63`

For:

`192.168.10.64/26`

the range is:

- Network: `192.168.10.64`
- First host: `192.168.10.65`
- Last host: `192.168.10.126`
- Broadcast: `192.168.10.127`

There are 64 total addresses.

---

## 6. Host Bits

The number of host bits is:

`32 - prefix`

For `/26`:

`32 - 26 = 6`

Six host bits produce:

`2^6 = 64`

addresses.

Traditional usable hosts:

`64 - 2 = 62`

The two excluded addresses are normally:

- Network address
- Broadcast address

The code calculates host bits rather than relying on memorized values.

---

## 7. Network Ranges

A CIDR network defines a continuous address range.

For example:

`192.168.10.64/26`

contains:

- `192.168.10.64` as the network address
- `192.168.10.65` through `192.168.10.126` as traditional host addresses
- `192.168.10.127` as the broadcast address

The next `/26` begins at:

`192.168.10.128`

The complete `/24` therefore contains four `/26` networks:

- `192.168.10.0/26`
- `192.168.10.64/26`
- `192.168.10.128/26`
- `192.168.10.192/26`

The Python and JavaScript implementations generate these subnet boundaries programmatically.

The C++ implementation provides the same capability through `IPv4Network::child()`.

---

## 8. Equal-Size Subnetting

Subnetting divides a larger network into smaller networks.

If a `/24` is divided into `/26` networks, four additional network bits are not used. Two bits are borrowed:

`26 - 24 = 2`

The number of subnets is:

`2^2 = 4`

Each `/26` contains:

`2^(32-26) = 64`

addresses.

Therefore:

- Parent: `/24`
- Child: `/26`
- Number of children: 4
- Addresses per child: 64
- Traditional usable hosts per child: 62

This is demonstrated in all three implementations.

---

## 9. Subnetting and Borrowed Bits

Subnetting can be understood by moving the network/host boundary.

Suppose the original network is:

`192.168.1.0/24`

The final octet has eight host bits.

Changing to `/26` uses two of those bits for subnetting:

`/24 -> /26`

The result is:

- 26 network/subnet bits
- 6 host bits

Two borrowed bits create:

`2^2 = 4`

subnets.

The six remaining host bits create:

`2^6 = 64`

addresses per subnet.

This relationship is fundamental:

`Number of subnets = 2^(borrowed bits)`

and:

`Addresses per subnet = 2^(remaining host bits)`

---

## 10. Host Requirement Calculations

Network planning often begins with a host requirement rather than a prefix.

For example, suppose a department needs 50 hosts.

A `/27` provides:

`2^5 = 32`

total addresses, which is insufficient.

A `/26` provides:

`2^6 = 64`

total addresses.

Traditional usable capacity is:

`64 - 2 = 62`

Therefore `/26` satisfies a 50-host requirement under traditional subnet rules.

The implementations contain `minimum_prefix_for_hosts()`, `minimumPrefixForHosts()`, and the corresponding C++ function to calculate the smallest conventional prefix capable of satisfying a host requirement.

---

## 11. Important Host-Count Edge Cases

The traditional formula:

`2^host_bits - 2`

is not universally appropriate.

### `/31`

A `/31` contains two addresses.

Historically, the network and broadcast model would leave no conventional host addresses.

RFC 3021 introduced the use of `/31` prefixes for point-to-point links, allowing both addresses to be used on the link.

The implementations therefore treat `/31` specially.

### `/32`

A `/32` contains exactly one address.

It is commonly used for:

- Host routes
- Loopback addresses
- Routing table entries
- Specific endpoint identification

A `/32` is not a conventional LAN subnet with a range of host addresses.

---

## 12. Wildcard Masks

A wildcard mask is the bitwise inverse of the subnet mask.

For:

`255.255.255.192`

the wildcard mask is:

`0.0.0.63`

Wildcard masks are frequently encountered in access-control and routing-related configurations.

The implementations calculate wildcard masks directly from the CIDR prefix.

---

## 13. Subnet Membership

To determine whether an IP belongs to a subnet:

1. Convert the IP to its 32-bit representation.
2. Apply the subnet mask.
3. Compare the result with the network address.

For:

`192.168.1.100/24`

the network is:

`192.168.1.0`

Therefore:

`192.168.1.100`

belongs to:

`192.168.1.0/24`

while:

`192.168.2.100`

does not.

The Python, JavaScript, and C++ implementations demonstrate this membership operation.

---

## 14. Private IPv4 Address Space

Common private IPv4 ranges are:

- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`

These ranges are intended for private networks and are not globally routable in the ordinary public Internet addressing model.

Private addressing is commonly used for:

- Enterprise LANs
- Internal applications
- Virtual networks
- Cloud networks
- Home networks
- Internal infrastructure

The Python implementation demonstrates address classification.

---

## 15. VLSM

VLSM means **Variable Length Subnet Masking**.

Equal-size subnetting gives every subnet the same capacity.

VLSM allows different departments or network segments to receive different subnet sizes.

For example:

| Department | Hosts Required | Possible Allocation |
|---|---:|---|
| Engineering | 60 | `/26` |
| Operations | 30 | `/27` |
| Management | 12 | `/28` |
| Security | 6 | `/29` |

This avoids allocating a large `/24` to every department when their requirements differ substantially.

A common VLSM strategy is:

1. List requirements.
2. Sort requirements from largest to smallest.
3. Select the smallest suitable prefix for each requirement.
4. Align each subnet to a valid boundary.
5. Allocate sequentially.
6. Check that every subnet remains inside the parent network.
7. Validate that no allocations overlap.

The Python `allocate_vlsm()` function implements this process.

The JavaScript `allocateVLSM()` function implements the same planning logic.

The C++ `VLSMAllocator` class turns the process into a reusable system component.

---

## 16. Why Largest Requirements Are Allocated First

Subnet boundaries have alignment constraints.

A `/26` requires blocks of 64 addresses.

A `/27` requires blocks of 32 addresses.

A `/28` requires blocks of 16 addresses.

If small blocks are allocated carelessly before large blocks, the remaining address space can become fragmented.

Allocating larger requirements first reduces this risk.

This is a practical allocation heuristic. It is not a universal optimization algorithm for every possible address-allocation problem, but it is a useful approach for ordinary VLSM planning.

---

## 17. C++ Enterprise Case Study

The C++ program models an organization receiving:

`10.20.0.0/20`

The organization has different requirements for:

- Engineering
- Operations
- Finance
- HR
- Security
- Network management

The program does not assign one identical subnet to every group.

Instead, `VLSMAllocator` calculates the smallest appropriate subnet for each requirement and places those allocations inside the parent `/20`.

### Main components

`IPv4Address`

Represents a 32-bit IPv4 address.

Responsibilities include:

- Parsing dotted-decimal addresses
- Converting to integer representation
- Converting integers back to dotted decimal
- Producing binary representation

`IPv4Network`

Represents an IPv4 CIDR network.

Responsibilities include:

- CIDR parsing
- Network calculation
- Broadcast calculation
- Subnet-mask generation
- Wildcard-mask generation
- Host counting
- Membership checking
- Overlap checking
- Child subnet generation

`VLSMAllocator`

Allocates differently sized networks according to host requirements.

`RoutingTable`

Stores CIDR routes and performs longest-prefix matching.

The program therefore demonstrates subnetting as part of a larger network-management system rather than as isolated arithmetic.

---

## 18. Longest Prefix Match

Routers can have multiple routes that contain the same destination.

For example:

- `0.0.0.0/0`
- `10.0.0.0/8`
- `10.20.0.0/16`
- `10.20.30.0/24`

For destination:

`10.20.30.77`

all four routes may match.

The most specific route has the longest prefix:

`10.20.30.0/24`

Therefore, longest-prefix match selects the route with the greatest prefix length among matching routes.

The C++ `RoutingTable` class implements this logic.

The Python and JavaScript implementations also include standalone longest-prefix-match demonstrations.

---

## 19. Route Summarization

Route summarization combines multiple contiguous networks into a smaller routing representation when their boundaries permit it.

For example:

- `192.168.0.0/24`
- `192.168.1.0/24`
- `192.168.2.0/24`
- `192.168.3.0/24`

can be represented by:

`192.168.0.0/22`

because four consecutive `/24` networks contain:

`4 × 256 = 1024`

addresses.

A `/22` also contains:

`2^(32-22) = 1024`

addresses.

Correct alignment is important. Four arbitrary `/24` networks cannot necessarily be summarized into one `/22`.

The implementations include address-range summarization logic.

---

## 20. Network Overlap

Overlapping networks can cause addressing and routing problems.

For example:

`10.0.0.0/24`

and:

`10.0.0.128/25`

overlap because the second network is contained within the first.

A valid network planning system should detect such conflicts before deployment.

The Python implementation uses network overlap checks.

The JavaScript implementation uses numeric range comparison.

The C++ `IPv4Network::overlaps()` method performs the comparison directly.

---

## 21. Binary Representation

Subnetting is fundamentally a bit-level operation.

For example:

`192`

in binary is:

`11000000`

A `/24` mask is:

`255.255.255.0`

or:

`11111111.11111111.11111111.00000000`

The first 24 bits identify the network and the final 8 bits represent host positions.

Understanding binary makes subnet calculations more reliable than relying exclusively on memorized decimal patterns.

All three implementations provide binary or bitwise demonstrations.

---

## 22. Python Implementation

The Python implementation is designed as a broad educational toolkit.

Important components include:

- `ipv4_to_int()`
- `int_to_ipv4()`
- `ipv4_to_binary()`
- `prefix_to_mask()`
- `mask_to_prefix()`
- `prefix_to_wildcard()`
- `calculate_subnet()`
- `calculate_network_bitwise()`
- `split_network()`
- `minimum_prefix_for_hosts()`
- `ip_belongs_to_subnet()`
- `allocate_vlsm()`
- `summarize_networks()`
- `validate_network_plan()`
- `longest_prefix_match()`

Python's standard `ipaddress` module is used where it provides reliable IPv4 network parsing and range operations.

The program also implements fundamental calculations directly so that the underlying mechanics remain visible.

This combination is useful for comparing:

- Manual bitwise logic
- Standard-library abstractions
- Network planning algorithms

---

## 23. JavaScript Implementation

The JavaScript implementation emphasizes application-oriented CIDR processing.

It includes:

- IPv4 parsing
- Integer conversion
- Binary conversion
- CIDR parsing
- Network calculation
- Broadcast calculation
- Host calculations
- Membership checks
- Equal subnetting
- VLSM
- Overlap detection
- Longest-prefix routing
- Address-range summarization
- Error handling

JavaScript is useful for subnet calculators that eventually become browser applications or network-planning interfaces.

The implementation deliberately avoids external packages.

One important language consideration is that JavaScript bitwise operators work on signed 32-bit integers. The implementation therefore uses unsigned conversion where required.

IPv4 values are small enough to be represented exactly by JavaScript's numeric type, so arithmetic-based address manipulation is also practical.

---

## 24. C++ Implementation

C++ is used for a more structured network-management case study.

The implementation demonstrates:

- Encapsulation
- Classes
- Strongly typed integer values
- Exceptions
- Vectors
- Sorting
- Bitwise operations
- Network modeling
- VLSM allocation
- Route lookup
- Overlap validation

`IPv4Address` isolates address representation from network behavior.

`IPv4Network` isolates CIDR behavior.

`VLSMAllocator` handles address allocation.

`RoutingTable` handles route selection.

This separation makes the implementation closer to the architecture of a reusable network-management component.

---

## 25. Important Differences Between the Three Implementations

| Area | Python | JavaScript | C++ |
|---|---|---|---|
| Address abstraction | Functions and dataclasses | Functions and objects | Dedicated classes |
| IPv4 library | Standard `ipaddress` plus manual logic | No external library | Standard library only |
| VLSM | Functional/data-oriented | Application-oriented functions | `VLSMAllocator` class |
| Routing | Function-based | Function-based | `RoutingTable` class |
| Error handling | Exceptions | Exceptions | Exceptions |
| Memory control | Managed runtime | Managed runtime | Explicitly typed low-level representation |
| Primary emphasis | Complete study toolkit | Practical executable utility | Industry-style architecture |

The mathematical rules remain the same across the languages.

The differences mainly concern language design, abstraction, execution environment, and implementation style.

---

## 26. `/24`, `/25`, `/26`, `/27`, and `/28`

These prefixes are especially common in private network planning.

### `/24`

- 256 total addresses
- 254 traditional usable hosts

### `/25`

- 128 total addresses
- 126 traditional usable hosts

A `/24` can be divided into:

- `x.x.x.0/25`
- `x.x.x.128/25`

### `/26`

- 64 total addresses
- 62 traditional usable hosts

A `/24` contains four `/26` networks.

### `/27`

- 32 total addresses
- 30 traditional usable hosts

A `/24` contains eight `/27` networks.

### `/28`

- 16 total addresses
- 14 traditional usable hosts

A `/24` contains sixteen `/28` networks.

---

## 27. Common Subnetting Mistakes

### Mistake 1: Confusing prefix length with host count

`/24` does not mean 24 hosts.

It means 24 network bits.

### Mistake 2: Forgetting the network address

The first address in a traditional subnet is the network identifier.

### Mistake 3: Forgetting the broadcast address

The final address in a traditional IPv4 subnet is the broadcast address.

### Mistake 4: Using the wrong block size

For `/26`, the block size is:

`256 - 192 = 64`

Therefore boundaries occur at:

- 0
- 64
- 128
- 192

### Mistake 5: Ignoring alignment

A subnet is not valid merely because the IP address is numerically convenient.

The network address must align with the prefix's block size.

### Mistake 6: Treating `/31` like a normal LAN

`/31` is commonly used for point-to-point links and has special semantics.

### Mistake 7: Treating `/32` as a normal subnet

`/32` identifies one IPv4 address.

### Mistake 8: Creating overlapping VLSM allocations

Every allocation should be checked against the other allocations.

### Mistake 9: Assuming subnetting itself provides security

Subnetting organizes address space. Security requires additional controls.

---

## 28. Edge Cases

### `/0`

`0.0.0.0/0` contains the entire IPv4 address space.

It is commonly used as a default route.

### `/31`

Contains two addresses and is useful for point-to-point links.

### `/32`

Represents one IPv4 address.

### `255.255.255.255`

This is the IPv4 limited broadcast address.

### `0.0.0.0`

This address has special meanings depending on context, including unspecified address and default-route notation when combined with `/0`.

These meanings should not be confused with ordinary host addressing.

---

## 29. Validation Requirements

A production subnetting tool should validate:

- Exactly four IPv4 octets
- Numeric octets
- Octets from 0 through 255
- Prefixes from 0 through 32
- Valid CIDR syntax
- Correct subnet boundaries
- VLSM capacity
- Non-overlapping allocations
- Address-space exhaustion
- Special-prefix behavior

The three implementations deliberately include invalid-input demonstrations.

---

## 30. Performance Considerations

Basic subnet calculations are constant-time operations.

For one IPv4 address:

- Parsing is bounded by four octets.
- Mask calculation is constant-time.
- Network calculation requires a small number of integer operations.
- Broadcast calculation requires a small number of integer operations.

A simple overlap validator comparing every network with every other network requires:

`O(N²)`

pairwise comparisons for `N` networks.

For large routing tables, repeatedly scanning every route is inefficient.

Production routing systems use specialized data structures and algorithms for fast prefix matching.

The educational C++ routing table intentionally uses a straightforward linear scan so the longest-prefix rule remains visible.

---

## 31. Security Considerations

Subnetting should not be treated as a complete security mechanism.

A network can be divided into multiple subnets while still permitting unrestricted communication between them.

Security commonly requires additional controls such as:

- Firewalls
- Access-control lists
- Routing policies
- Authentication
- Network segmentation
- Monitoring
- Logging
- Encryption
- Identity-aware controls

Incorrect subnetting can also create security problems indirectly.

Examples include:

- Accidentally overlapping address space
- Incorrect routes
- Unexpected connectivity
- Incorrect ACL scope
- Misidentified network boundaries

Accurate subnet calculations are therefore part of reliable network security design, but they are not a substitute for security policy enforcement.

---

## 32. Implementation Design Considerations

A production network-planning system should generally separate:

1. Address representation
2. CIDR parsing
3. Network arithmetic
4. Allocation logic
5. Validation
6. Routing logic
7. Presentation

The C++ case study follows this separation through dedicated classes.

The Python implementation exposes functions that make individual calculations easy to test.

The JavaScript implementation uses reusable functions suitable for eventual integration into a browser-based subnet calculator or network-management application.

---

## 33. Practical Applications

Subnetting is used in:

- Enterprise LAN design
- Cloud virtual networks
- Data centers
- Internet routing
- VPN addressing
- Point-to-point links
- Network management
- Firewall rule design
- Routing-table organization
- Address allocation
- Infrastructure planning
- Network automation

CIDR also provides the addressing foundation for route aggregation and efficient routing-table organization.

---

## 34. Relationship Between Subnetting, VLSM, and Summarization

These concepts operate at different stages of network design.

**Subnetting** divides address space into smaller networks.

**VLSM** allows those smaller networks to have different sizes.

**Summarization** combines compatible address ranges into larger routing representations.

For example:

A company can receive:

`10.20.0.0/20`

then allocate:

- `/23`
- `/24`
- `/25`
- `/26`
- `/28`

using VLSM.

Routers can later summarize suitable contiguous networks where alignment permits.

These are related but distinct operations.

---

## 35. Formula Reference

### Host bits

`Host bits = 32 - prefix`

### Total addresses

`Total addresses = 2^host_bits`

### Traditional usable hosts

`Usable hosts = 2^host_bits - 2`

This traditional formula applies to ordinary IPv4 LAN subnetting, not all special-prefix situations.

### Number of equal-size subnets

`Number of subnets = 2^borrowed_bits`

### Borrowed bits

`Borrowed bits = new prefix - original prefix`

### Network address

`Network = IP AND subnet mask`

### Broadcast address

`Broadcast = Network OR wildcard mask`

### Wildcard mask

`Wildcard = NOT subnet mask`

These formulas form the mathematical foundation of the implementations.

---

## 36. Example Calculation

Consider:

`192.168.10.77/26`

### Step 1: Prefix

`/26`

### Step 2: Host bits

`32 - 26 = 6`

### Step 3: Total addresses

`2^6 = 64`

### Step 4: Subnet mask

`255.255.255.192`

### Step 5: Block size

`256 - 192 = 64`

### Step 6: Determine the boundary

The possible final-octet boundaries are:

- 0
- 64
- 128
- 192

77 lies between 64 and 127.

Therefore:

Network:

`192.168.10.64`

Broadcast:

`192.168.10.127`

Traditional usable range:

`192.168.10.65 - 192.168.10.126`

Traditional usable hosts:

`62`

The Python, JavaScript, and C++ implementations all produce these same fundamental results.

---

## 37. Production Network Planning Workflow

A practical network allocation process can be represented as:

1. Identify the parent address space.
2. Record current and future host requirements.
3. Separate different operational or administrative network segments.
4. Calculate required subnet sizes.
5. Allocate larger requirements first when using VLSM.
6. Align every subnet correctly.
7. Check for overlap.
8. Reserve appropriate growth capacity.
9. Document network and broadcast boundaries.
10. Define routing requirements.
11. Validate route summarization opportunities.
12. Apply security policy separately from address allocation.
13. Test the resulting plan before deployment.

The C++ enterprise case study demonstrates the computational portions of this workflow.

---

## 38. Technical Limitations of These Implementations

The programs focus on IPv4 subnetting.

They do not attempt to implement:

- Full BGP
- OSPF
- IS-IS
- DHCP servers
- DNS
- ARP
- Ethernet switching
- Packet transmission
- Firewall enforcement
- Real router configuration
- IPv6 subnetting
- Full routing protocol databases

The routing demonstration is an educational longest-prefix-match model rather than a production router.

The VLSM allocation algorithm demonstrates practical sequential allocation rather than a complete enterprise IP address-management platform.

---

## 39. Key Implementation Concepts Demonstrated

The Python program emphasizes breadth and direct experimentation.

The JavaScript program emphasizes reusable application-level calculations and JavaScript-specific integer behavior.

The C++ program emphasizes architectural separation and a realistic enterprise network-planning scenario.

Across all three implementations, the essential subnetting model remains:

`IPv4 address + prefix length -> subnet boundary + address range + host capacity`

Understanding that relationship is more important than memorizing isolated subnet tables.
