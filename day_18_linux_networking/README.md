# Linux Networking

A practical study of Linux networking from fundamental concepts through network diagnostics, socket programming, routing, DNS, performance, security, and production-oriented troubleshooting.

## Topic introduction

Linux networking is the collection of kernel, user-space, protocol, interface, routing, naming, transport, and application mechanisms that allow Linux systems to communicate with other systems.

A useful mental model is layered:

- Network interface
- Link-layer connectivity
- IP addressing
- Routing
- Neighbor discovery
- Transport protocols
- DNS and naming
- Application protocols
- Security controls
- Monitoring and troubleshooting

A network failure at one layer can appear as an application failure at another layer. A disciplined troubleshooting process therefore tests the layers independently.

This repository contains three implementations:

- Python provides an extensive educational exploration using the standard library and Linux command-line tools.
- JavaScript provides a Node.js view of networking through operating-system APIs, DNS, TCP, UDP, and application-level requests.
- C++ develops a realistic Linux gateway case study using POSIX sockets, routing models, validation, concurrency, and resource-safe system programming.

## Fundamental concepts

### Network interface

A network interface is the Linux representation of a network connection or virtual networking endpoint.

Examples include:

- `lo`
- `eth0`
- `ens160`
- `enp0s3`
- `wlan0`
- `docker0`

The exact interface name depends on the operating system, hardware, virtualization environment, and configuration.

The loopback interface is especially important for local testing. IPv4 loopback commonly uses `127.0.0.0/8`, with `127.0.0.1` being the conventional localhost address.

Useful Linux commands include:

`ip link`

`ip -br link`

`ip addr`

`ip -br addr`

The Python implementation inspects interfaces through `socket.if_nameindex()` and `/sys/class/net`.

The JavaScript implementation uses Node.js `os.networkInterfaces()`.

The C++ case study models an interface configuration explicitly and validates its address against an expected network.

### Interface state

An interface can exist without being operational.

Typical states include:

- `up`
- `down`
- `unknown`

Interface state is not equivalent to Internet connectivity.

A machine can have an operational interface but still have:

- no IP address
- an incorrect prefix
- no default route
- an unreachable gateway
- broken DNS
- firewall restrictions
- an unavailable remote service

This distinction is fundamental to network troubleshooting.

## MAC addresses

A MAC address is a link-layer identifier commonly associated with Ethernet and Wi-Fi interfaces.

A typical representation is:

`02:42:ac:11:00:02`

MAC addresses operate at a different layer from IP addresses.

An IP address identifies a logical network endpoint. A MAC address is used by link-layer mechanisms on networks such as Ethernet.

The Python program reads Linux interface MAC addresses from `/sys/class/net/<interface>/address`.

## IPv4

IPv4 uses 32-bit addresses.

Examples include:

- `127.0.0.1`
- `192.168.1.10`
- `10.0.0.5`
- `172.16.20.4`

The Python implementation uses the standard-library `ipaddress` module to parse and classify IPv4 addresses.

Important classifications include:

- loopback
- private
- globally routable
- link-local
- special-purpose ranges

An address should always be interpreted together with its prefix length.

## IPv6

IPv6 uses 128-bit addresses.

Examples include:

`::1`

`2001:db8::1`

`fe80::1234`

The JavaScript implementation demonstrates IPv6 validation using `net.isIPv6()`.

The Python implementation uses `ipaddress.ip_address()` to distinguish IPv4 and IPv6.

IPv6 differs from IPv4 in several important ways:

| Concept | IPv4 | IPv6 |
|---|---|---|
| Address size | 32 bits | 128 bits |
| Common notation | Dotted decimal | Hexadecimal with colons |
| Loopback | `127.0.0.1` | `::1` |
| Neighbor mechanism | ARP | Neighbor Discovery |
| Traditional broadcast | Yes | No |
| Address space | Smaller | Very large |

IPv6 should not be treated simply as a longer IPv4 address. Its neighbor discovery, address configuration, multicast, and routing behavior differ significantly.

## CIDR notation

CIDR represents an IP network using an address and prefix length.

Examples:

`192.168.1.0/24`

`10.0.0.0/8`

`172.16.20.0/28`

The prefix length identifies how many leading bits represent the network portion.

For IPv4:

- `/8` leaves 24 host bits
- `/16` leaves 16 host bits
- `/24` leaves 8 host bits
- `/30` leaves 2 host bits

For a traditional `/24` IPv4 network, there are 256 total addresses. In conventional host addressing, the network and broadcast addresses have special meanings, leaving 254 ordinary host addresses.

The Python implementation demonstrates subnet creation with `ipaddress.ip_network()` and `.subnets()`.

The JavaScript implementation implements IPv4 integer conversion and CIDR membership manually to demonstrate the underlying bit operations.

The C++ implementation creates an `IPv4Network` class that calculates a mask and performs membership tests.

## Subnet membership

Consider:

`192.168.50.0/24`

The address:

`192.168.50.10`

belongs to that network.

The address:

`192.168.51.10`

does not.

Subnet membership matters because directly connected communication depends on the local network configuration. An incorrect prefix can cause a host to make incorrect assumptions about which destinations are local.

The Python program demonstrates membership using the `in` operator.

The JavaScript program demonstrates membership using bitwise operations.

The C++ program demonstrates membership using an integer mask.

## Routing basics

Routing determines where an IP packet should be sent.

A simplified routing table can look conceptually like:

`192.168.1.0/24    direct       eth0`

`0.0.0.0/0         192.168.1.1 eth0`

The first route describes the local network.

The second is the default route.

When a destination matches several routes, the most specific matching prefix generally takes precedence. This is known as longest-prefix matching.

For example:

- `/24` is more specific than `/16`
- `/25` is more specific than `/24`
- `/32` is more specific than `/25`

Linux routing can be substantially more sophisticated than this simplified model. Policy routing, multiple routing tables, metrics, firewall marks, VRFs, network namespaces, source-address selection, and other kernel mechanisms can affect actual decisions.

## Default gateway

A default gateway is a next-hop router used when no more-specific route matches a destination.

A common example is:

`0.0.0.0/0 via 192.168.1.1 dev eth0`

This does not necessarily mean that `192.168.1.1` is directly an Internet router. It may be a router inside an enterprise, laboratory, VPN, cloud environment, or private network.

The Python implementation demonstrates:

`ip route`

and:

`ip route get <destination>`

The latter is particularly useful because it asks the Linux kernel how it would route a particular destination.

## Neighbor discovery

For IPv4 Ethernet networks, ARP maps local IPv4 addresses to link-layer addresses.

For IPv6, Neighbor Discovery Protocol performs related functions through ICMPv6.

Linux exposes neighbor information with:

`ip neigh`

and:

`ip -6 neigh`

A neighbor entry may contain states such as reachable, stale, incomplete, or failed.

Neighbor problems can explain why two hosts on the same apparent subnet cannot communicate even when their IP addresses look correct.

## DNS

DNS is the naming system used to translate names into network addresses and perform other DNS-related functions.

For example:

`example.com`

can resolve to one or more IP addresses.

DNS should be separated conceptually from network connectivity.

If this works:

`ping 1.1.1.1`

but this fails:

`ping example.com`

DNS is one possible problem.

If a name resolves but the application cannot connect, the problem may instead involve:

- routing
- firewall rules
- TCP
- port availability
- TLS
- the remote application
- application-level authentication

## `/etc/resolv.conf`

Linux systems commonly expose resolver configuration through:

`/etc/resolv.conf`

A simple configuration can contain:

`nameserver 192.168.1.1`

Modern Linux systems may generate this file dynamically.

Possible DNS management components include:

- systemd-resolved
- NetworkManager
- resolvconf
- static configuration
- VPN software
- container-specific networking

Blindly replacing `/etc/resolv.conf` can therefore create configuration conflicts.

The Python implementation reads and parses nameserver entries.

The JavaScript implementation inspects the file on Linux and attempts `resolvectl status`.

## Name resolution APIs

Python provides:

`socket.getaddrinfo()`

JavaScript provides:

`dns.lookup()`

and:

`dns.resolve4()`

C++ uses:

`getaddrinfo()`

These APIs illustrate an important principle: application code normally should not assume that a hostname corresponds to one permanent IP address.

A hostname may resolve to:

- multiple IPv4 addresses
- multiple IPv6 addresses
- addresses that change over time
- addresses selected according to resolver and operating-system policy

## TCP

TCP is a connection-oriented transport protocol.

Important properties include:

- connection establishment
- reliable delivery
- ordered delivery
- retransmission
- flow control
- congestion control
- byte-stream semantics

The Python implementation creates a local TCP echo service using the loopback address.

The JavaScript implementation creates a Node.js TCP server and client.

The C++ implementation builds a POSIX TCP service with:

- socket creation
- `setsockopt`
- `bind`
- `listen`
- `accept`
- `connect`
- `send`
- `recv`

The C++ implementation also demonstrates why `send()` must not automatically be assumed to transmit every requested byte in one call.

## UDP

UDP provides datagrams rather than a reliable ordered byte stream.

Important characteristics include:

- no TCP-style connection establishment
- low protocol overhead
- datagram boundaries
- no built-in retransmission guarantee
- no built-in ordering guarantee
- no built-in congestion-control behavior equivalent to TCP

The Python and JavaScript implementations demonstrate local UDP echo communication.

The C++ case study demonstrates a telemetry sender.

A successful `sendto()` call does not prove that the remote application received the datagram.

Production UDP systems often implement application-level mechanisms when reliability is required, such as sequence numbers, acknowledgements, retransmission, integrity checks, authentication, or expiration.

## Ports

A port identifies a transport-layer endpoint.

Common examples include:

- TCP 22 for SSH
- TCP 80 for HTTP
- TCP 443 for HTTPS
- UDP 53 for DNS

DNS can also use TCP in appropriate circumstances.

Useful Linux commands include:

`ss -lnt`

`ss -lnu`

`ss -lntup`

The distinction between listening and reachable is important.

A process can be listening on a port while:

- a firewall blocks access
- routing is incorrect
- the service is bound only to loopback
- an ACL denies traffic
- the client uses the wrong address

## Binding addresses

A service bound to:

`127.0.0.1`

is intended for local access.

A service bound to:

`0.0.0.0`

can listen on all local IPv4 interfaces, subject to operating-system and security policy.

Binding broadly can expose a service unintentionally.

The C++ case study deliberately binds its demonstration service to loopback. This reduces exposure and makes the example safe to execute without creating an externally reachable service.

## Python implementation

The Python program is the broadest educational implementation.

It demonstrates:

- IPv4 and IPv6 parsing
- CIDR calculations
- interface discovery
- MAC-address inspection
- interface state
- hostname information
- address discovery
- Linux routing commands
- gateway inspection
- DNS configuration
- DNS resolution
- neighbor tables
- TCP and UDP sockets
- port testing
- route-selection modeling
- command-output parsing
- configuration validation
- connectivity testing
- troubleshooting decision logic
- performance measurements
- packet-capture concepts
- security considerations
- production considerations

The Python `ipaddress` module is especially useful because it provides explicit types for IP addresses and networks rather than requiring manual bit manipulation.

The program also uses subprocess execution to inspect Linux tools such as `ip`, `ss`, `ping`, `traceroute`, `tracepath`, `resolvectl`, `getent`, and `tcpdump` when they are available.

## JavaScript implementation

The JavaScript implementation uses Node.js rather than browser JavaScript.

This is important because normal browser JavaScript does not have arbitrary access to Linux network interfaces, raw sockets, or the operating system's routing table.

Node.js provides APIs that are appropriate for server-side networking.

The implementation demonstrates:

- `os.networkInterfaces()`
- `net.isIPv4()`
- `net.isIPv6()`
- TCP servers
- TCP clients
- UDP sockets
- DNS lookup
- DNS record resolution
- TCP port testing
- HTTP requests
- concurrent diagnostics with `Promise.all()`
- high-resolution timing
- Linux command execution
- network failure classification

JavaScript's event-driven model makes it especially useful for demonstrating asynchronous network operations.

## C++ case study

The C++ implementation models a small Linux service gateway.

The scenario combines several networking concerns instead of treating them as isolated syntax examples.

The system contains:

- interface configuration
- CIDR validation
- routing
- TCP service communication
- UDP telemetry
- DNS resolution
- port diagnostics
- telemetry analysis
- concurrent collection
- error handling
- RAII-based resource management

### Interface validation

The `InterfaceConfiguration` structure stores:

- interface name
- IPv4 address
- expected network

`ConfigurationValidator` verifies that the configured address belongs to the expected subnet.

This models an important operational check: syntactically valid configuration can still be logically incorrect.

### IPv4 implementation

`IPv4Address` wraps a 32-bit IPv4 representation.

The implementation uses:

`inet_pton()`

for parsing and:

`inet_ntop()`

for formatting.

The conversion to host-order integers makes subnet masking and comparisons straightforward.

### CIDR implementation

`IPv4Network` stores:

- network address
- prefix length
- subnet mask

The `contains()` method checks whether an IPv4 address belongs to the network.

This demonstrates the underlying mechanism behind CIDR membership rather than hiding the operation behind a library.

### Routing implementation

`RoutingTable` stores a collection of `Route` objects.

Each route contains:

- destination network
- gateway
- interface
- metric

The route lookup process:

1. Finds matching networks.
2. Prefers the longest prefix.
3. Uses metric when prefixes are otherwise equal.

This is an educational model rather than a replacement for the Linux kernel's actual routing subsystem.

### TCP architecture

The C++ TCP server uses:

`socket()`

`setsockopt()`

`bind()`

`listen()`

`accept()`

The client uses:

`socket()`

`connect()`

`send()`

`recv()`

The demonstration uses loopback to keep the service local.

The program uses a file-descriptor RAII wrapper so sockets are automatically closed when their owning object leaves scope.

This is an important C++ design consideration because network sockets are operating-system resources, not ordinary memory objects.

### Partial writes

TCP is a byte stream.

An application should not assume that one `send()` call transfers the entire buffer.

The C++ TCP server therefore loops until the intended response has been transmitted.

This distinction is less visible in small examples but becomes important in production systems.

### UDP architecture

The UDP telemetry sender uses:

`socket(AF_INET, SOCK_DGRAM, 0)`

and:

`sendto()`

The demonstration intentionally does not claim delivery success from the return value of `sendto()`.

This reflects an important difference between sending a datagram to the kernel and receiving it successfully at the remote application.

### DNS

The C++ case study uses:

`getaddrinfo()`

with `AF_UNSPEC`.

This permits both IPv4 and IPv6 results and illustrates why application code should avoid assuming that all network services are IPv4-only.

### Concurrency

The monitoring component uses C++ threads and a mutex-protected telemetry collection.

Multiple workers collect measurements concurrently.

A mutex protects shared state.

An atomic Boolean controls the running state.

The example demonstrates a common concurrency pattern:

- independent workers perform work
- shared data requires synchronization
- snapshots can be taken under a lock
- the resulting data can then be processed independently

## Network troubleshooting

A useful troubleshooting sequence is layered.

### Interface

Check:

`ip -br link`

Questions:

- Does the interface exist?
- Is it operational?
- Is the expected adapter present?

### Address

Check:

`ip -br addr`

Questions:

- Is the expected IPv4 address present?
- Is IPv6 configured?
- Is the prefix correct?
- Is the address attached to the correct interface?

### Routing

Check:

`ip route`

Questions:

- Is the local network route present?
- Is a default route present?
- Is the gateway correct?

### Specific route decision

Use:

`ip route get 8.8.8.8`

This is more informative than merely looking at a route table because it asks the kernel to evaluate a particular destination.

### Neighbor state

Check:

`ip neigh`

Questions:

- Is the expected local neighbor present?
- Is the entry incomplete?
- Is the gateway reachable at the link layer?

### DNS

Check:

`resolvectl status`

and:

`getent hosts example.com`

Questions:

- Which resolver is configured?
- Does the operating system resolve names?
- Is the resolver reachable?
- Is the failure temporary or persistent?

### Listening services

Check:

`ss -lntup`

Questions:

- Is the expected process listening?
- Which port is open?
- Which local address is it bound to?
- Is it listening on IPv4, IPv6, or both?

### Connectivity

Possible tests include:

`ping`

`tracepath`

`traceroute`

`tcpdump`

A failed ICMP test does not automatically prove that TCP or HTTPS is unavailable.

### Application

The final test should use the actual application protocol where possible.

For an HTTP service, an HTTP request is more meaningful than relying exclusively on ping.

## Ping

`ping` commonly uses ICMP Echo Request and Echo Reply.

It can provide useful information about:

- reachability
- approximate round-trip time
- packet loss

It has limitations.

A host can block ICMP while permitting TCP 443.

A router can suppress ICMP diagnostic responses while forwarding traffic correctly.

Therefore:

`ping failed`

does not necessarily mean:

`all communication failed`

## Traceroute and tracepath

Traceroute-style tools identify intermediate routing hops by manipulating TTL or IPv6 Hop Limit values.

They can help reveal:

- routing paths
- unexpected gateways
- routing loops
- path changes
- points where responses stop appearing

A missing hop response does not necessarily mean that the router is dropping forwarded traffic. Many network devices intentionally rate-limit or suppress diagnostic responses.

## Packet capture

Packet capture tools include:

`tcpdump`

`Wireshark`

`tshark`

A capture can reveal:

- Ethernet frames
- ARP
- IPv4
- IPv6
- ICMP
- TCP handshakes
- UDP traffic
- DNS queries
- TCP retransmissions
- TCP resets
- TLS handshakes

Example command:

`sudo tcpdump -ni any`

More focused captures can filter by interface, host, or port.

Packet captures can contain sensitive information and should only be collected, stored, and shared according to applicable authorization and security requirements.

## DNS versus connectivity

These cases illustrate why network diagnosis must separate layers.

### Case 1

`ping 1.1.1.1` succeeds.

`ping example.com` fails.

Possible explanation:

DNS resolution failure.

### Case 2

`example.com` resolves.

TCP 443 fails.

Possible explanations include:

- firewall
- routing
- service availability
- port filtering
- ACL
- remote host configuration

### Case 3

TCP 443 succeeds.

The application request fails.

Possible explanations include:

- TLS
- HTTP behavior
- authentication
- authorization
- application-level errors
- proxy configuration

### Case 4

The service works from the same machine but not remotely.

Possible explanations include:

- service bound to loopback
- host firewall
- network firewall
- ACL
- incorrect remote routing
- service-specific access policy

## Error interpretation

### Connection refused

A TCP connection was actively rejected.

A common interpretation is that the destination is reachable but no process accepted the connection on that address and port.

It can also be caused by explicit network policy that actively rejects traffic.

### Connection timeout

The connection attempt did not complete within the configured period.

Possible causes include:

- filtering
- routing failure
- unreachable destination
- packet loss
- service or infrastructure failure

A timeout is not proof of one specific cause.

### DNS not found

A hostname may not resolve because:

- the name does not exist
- the resolver cannot reach an authoritative source
- local resolver configuration is incorrect
- temporary DNS failure occurred
- search-domain behavior produced an unexpected name

The precise resolver error should be inspected rather than inferred from the application symptom alone.

## Performance considerations

### Bandwidth

Bandwidth describes the capacity of a communication link.

### Throughput

Throughput describes the actual amount of data transferred over time.

### Latency

Latency measures delay.

### Round-trip time

RTT measures the time for traffic to travel to a destination and return.

### Jitter

Jitter describes variation in packet delay.

### Packet loss

Packet loss occurs when packets do not reach their intended destination.

### MTU

The Maximum Transmission Unit determines the largest packet payload size that a network interface or path can carry without fragmentation at the relevant layer.

A common Ethernet MTU is 1500 bytes, but VPNs, tunnels, virtual networks, and specialized environments may use different values.

Performance problems can arise even when nominal bandwidth is high.

For example:

- high latency can make interactive applications feel slow
- packet loss can trigger retransmissions
- DNS delay can delay application startup
- congestion can reduce effective throughput
- server processing can dominate network transfer time

## Security considerations

Network configuration is part of the security boundary.

Important considerations include:

- minimize unnecessary listening services
- restrict exposed ports
- bind services to appropriate interfaces
- use encrypted protocols
- validate TLS certificates
- protect DNS configuration
- use firewall and ACL controls
- restrict management interfaces
- segment sensitive systems
- monitor unexpected route changes
- monitor unexpected listening ports
- protect packet captures
- avoid logging credentials and sensitive payloads

A service that listens on all interfaces is potentially more exposed than a service restricted to a specific internal interface.

The C++ case study demonstrates a conservative design by binding the example TCP service to `127.0.0.1`.

## Network namespaces

Linux network namespaces provide isolated network stacks.

A namespace can have its own:

- interfaces
- addresses
- routes
- neighbor tables
- ports

Containers commonly use network namespaces.

A virtual Ethernet pair can connect separate namespaces.

This architecture allows a Linux host to run multiple logically isolated network environments.

## Bridges

A Linux bridge connects Layer-2 interfaces.

Bridges are commonly used in:

- virtualization
- container networking
- laboratory networks
- software-defined network environments

A bridge is conceptually different from an IP router.

A bridge primarily forwards Ethernet frames.

A router forwards packets between IP networks.

## VLANs

VLANs provide logical Layer-2 segmentation.

They allow multiple logical networks to share physical infrastructure while remaining separated at the Layer-2 level.

Correct VLAN configuration can be critical when troubleshooting a host that appears correctly addressed but cannot communicate with the expected gateway.

## Policy routing

Basic routing focuses heavily on destination prefixes.

Linux can perform more sophisticated routing decisions.

Policy routing can consider factors such as:

- source address
- packet marks
- interface
- routing table
- policy rules

This becomes important in:

- multi-homed systems
- VPN gateways
- advanced cloud networking
- network appliances
- traffic engineering

## Network namespaces and containers

Containers commonly combine several Linux networking mechanisms:

- network namespaces
- virtual Ethernet interfaces
- bridges
- routing
- NAT
- firewall rules
- DNS configuration

This explains why container networking can appear complex even though each component has a well-defined purpose.

## Common mistakes

### Confusing MAC and IP addresses

A MAC address is associated with link-layer communication.

An IP address is used for network-layer addressing.

They serve different purposes.

### Assuming interface UP means Internet access

Interface state is only one part of connectivity.

Addressing, routing, gateway access, DNS, firewall policy, and remote service availability must also be considered.

### Ignoring prefix length

`192.168.1.10/24`

and:

`192.168.1.10/16`

describe different network relationships.

### Treating DNS as Internet connectivity

A working network can have broken DNS.

A working DNS resolver can exist while the target service is unreachable.

### Treating ping as proof of application availability

ICMP and TCP are different protocols.

A host can block ICMP while allowing HTTPS.

### Assuming an open port means the application is healthy

A listening socket proves that a process has opened a transport endpoint.

It does not prove that the application logic is healthy.

### Binding a service only to loopback unintentionally

A service listening on `127.0.0.1` is normally unavailable to remote clients.

### Binding unnecessarily to every interface

Binding broadly can expose a service to networks that were not intended to reach it.

### Rewriting `/etc/resolv.conf` without understanding the system

A resolver manager may regenerate the file.

Manual changes may disappear or conflict with the system's network management architecture.

### Ignoring IPv6

Dual-stack systems can produce different behavior between IPv4 and IPv6.

Applications should not assume that IPv4 is always the only relevant protocol.

## Python, JavaScript, and C++ comparison

| Aspect | Python | JavaScript / Node.js | C++ |
|---|---|---|---|
| Interface inspection | `socket`, `/sys`, Linux commands | `os.networkInterfaces()` and commands | POSIX/system APIs |
| DNS | `socket.getaddrinfo()` | `dns` module | `getaddrinfo()` |
| TCP | `socket` | `net` | POSIX sockets |
| UDP | `socket` | `dgram` | POSIX sockets |
| CIDR | Standard-library `ipaddress` | Manual bit operations | Explicit integer/mask model |
| Concurrency | Threads demonstrated | Event-driven asynchronous model | Threads, mutexes, atomics |
| Resource management | Context managers | Event-driven lifecycle | RAII |
| Linux integration | Subprocess and filesystem APIs | Child processes and filesystem access | Direct system calls |
| Best educational emphasis | Concepts and automation | Asynchronous application networking | Systems programming and kernel-facing APIs |

## Python design considerations

Python's `ipaddress` module reduces the risk of incorrect manual IP arithmetic.

Context managers are useful for sockets because resources are released automatically.

The Python TCP demonstration also uses explicit timeouts. Network operations should generally not be allowed to wait forever.

Subprocess calls are used for Linux inspection rather than attempting to recreate every Linux networking subsystem inside Python.

## JavaScript design considerations

Node.js networking is strongly event-driven.

TCP sockets emit events such as:

- `connect`
- `data`
- `end`
- `timeout`
- `error`

UDP sockets use event-driven message handling.

`Promise.all()` is used for independent diagnostic operations, allowing DNS and port checks to proceed concurrently.

This model is useful for network services where many operations may be waiting for I/O simultaneously.

## C++ design considerations

C++ provides direct access to POSIX networking primitives.

The C++ implementation demonstrates why system-level networking requires careful resource management.

The `FileDescriptor` wrapper provides RAII.

The TCP implementation handles partial writes.

Timeouts are configured on sockets.

Exceptions propagate failures to a central error handler.

The concurrent telemetry monitor protects shared state with a mutex.

These patterns are particularly relevant to systems programming.

## Algorithmic considerations

The educational routing model uses longest-prefix matching.

For each route:

1. Check whether the destination belongs to the route's network.
2. Discard non-matching routes.
3. Prefer the route with the longest prefix.
4. Use metric as a tie-breaking factor in the simplified implementation.

The educational C++ implementation sorts matching routes, which gives an easy-to-understand model but is not how a high-performance kernel routing implementation should be evaluated.

With `R` matching routes, sorting has approximately `O(R log R)` complexity.

Real routing implementations use optimized data structures and algorithms.

## Telemetry case study

The C++ gateway models telemetry containing:

- sequence number
- temperature
- packet-loss percentage

The telemetry analyzer calculates average values.

Multiple worker threads generate measurements.

A mutex protects the shared vector.

This illustrates how networking and data processing frequently meet in real systems.

A production telemetry system would need more considerations, including:

- timestamps
- message authentication
- integrity protection
- sequence tracking
- duplicate detection
- backpressure
- bounded queues
- persistent storage
- metrics
- alerting
- failure recovery

## Production networking

Production systems require more than basic socket functionality.

Important areas include:

### Reliability

Applications should handle:

- connection failure
- timeout
- retry
- partial transfer
- remote shutdown
- DNS failure
- temporary network interruption

Retries should be bounded and designed to avoid creating retry storms.

### Resource management

Servers need limits for:

- open connections
- memory
- socket buffers
- worker threads
- queued requests
- request duration

Unbounded resources can turn a temporary traffic spike into a service outage.

### Observability

Useful network metrics include:

- request latency
- connection latency
- DNS latency
- packet loss
- retransmissions
- active connections
- connection failures
- throughput
- interface errors

Logs should provide enough context to correlate network and application behavior.

### Security

Production network services should consider:

- TLS
- certificate validation
- authentication
- authorization
- firewalls
- ACLs
- segmentation
- least privilege
- secure DNS
- monitoring
- secrets management

### Change management

Network configuration changes can disconnect a host.

Commands that modify:

- addresses
- routes
- interfaces
- firewall rules
- DNS
- VLANs

should be applied carefully, preferably with a recovery mechanism.

## Important Linux commands

| Command | Purpose |
|---|---|
| `ip link` | Interface state |
| `ip -br link` | Compact interface state |
| `ip addr` | Address configuration |
| `ip -br addr` | Compact address configuration |
| `ip route` | IPv4 routing table |
| `ip -6 route` | IPv6 routing table |
| `ip route get <destination>` | Kernel route decision |
| `ip neigh` | IPv4 neighbor table |
| `ip -6 neigh` | IPv6 neighbor table |
| `ss -lntup` | Listening sockets |
| `resolvectl status` | Resolver status |
| `resolvectl query <name>` | Resolver query |
| `getent hosts <name>` | System resolver-path lookup |
| `ping <host>` | ICMP reachability test |
| `tracepath <host>` | Path and MTU diagnostics |
| `traceroute <host>` | Hop-by-hop path diagnostics |
| `tcpdump -ni any` | Packet capture |

## Practical diagnostic workflow

A structured investigation can follow this order:

`ip -br link`

Check interface presence and state.

`ip -br addr`

Check addresses and prefixes.

`ip route`

Check routes.

`ip route get <destination>`

Check the kernel's route selection.

`ip neigh`

Check local neighbor state.

`resolvectl status`

Check resolver configuration.

`getent hosts <hostname>`

Check actual system name resolution.

`ss -lntup`

Check listening services.

`ping <destination>`

Test ICMP where permitted.

`tracepath <destination>`

Investigate the path and possible MTU behavior.

`tcpdump`

Inspect actual packets when authorized and appropriate.

Application-specific tools should then test the actual service protocol.

## Limitations of the examples

The implementations are educational and intentionally conservative.

The Python program uses Linux commands when available, but command output can differ between Linux distributions and versions.

The JavaScript program uses Node.js APIs and Linux command execution. Browser JavaScript has substantially different security and networking restrictions.

The C++ routing implementation is a simplified model. It does not reproduce the full Linux routing subsystem.

The C++ case study uses IPv4 for its direct socket demonstrations while the DNS example supports both IPv4 and IPv6 through `getaddrinfo()`.

The examples do not attempt to modify network configuration automatically. This prevents a study program from unexpectedly disconnecting the host.

## Files

The repository contains:

- `linux_networking_study.py`
- `linux_networking_study.js`
- `linux_networking_case_study.cpp`
- `README.md`

The Python file emphasizes comprehensive concepts and Linux diagnostics.

The JavaScript file emphasizes Node.js networking and asynchronous application behavior.

The C++ file emphasizes POSIX sockets, systems programming, routing algorithms, concurrency, resource management, and a realistic service-gateway design.

## Execution

Python:

`python3 linux_networking_study.py`

JavaScript:

`node linux_networking_study.js`

C++:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic linux_networking_case_study.cpp -o network_case`

Then:

`./network_case`

Some demonstrations depend on Linux utilities being installed and on the machine's current network configuration.

The networking examples are primarily observational and use loopback for local socket demonstrations, reducing the risk of changing or exposing the host's network configuration.
