# TCP/IP model

## Introduction

The TCP/IP model is a layered framework for understanding how networked systems communicate. It groups networking responsibilities into four broad layers:

1. Application
2. Transport
3. Internet
4. Network Access

The layers work together rather than operating as four isolated systems. An application creates information, the transport layer provides process-to-process communication, the Internet layer provides logical addressing and routing, and the Network Access layer moves data across a local network technology.

A useful conceptual path is:

`Application data → transport segment/datagram → IP packet → link-layer frame`

At the receiving system, the process occurs in the opposite direction:

`Frame → IP packet → transport data → application data`

This process is called **encapsulation** when protocol information is added while data moves downward through the stack, and **decapsulation** when protocol information is removed while data moves upward.

The accompanying Python, JavaScript, and C++ programs use progressively different approaches to demonstrate these concepts.

## The four TCP/IP layers

| Layer | Main responsibility | Representative protocols or technologies |
|---|---|---|
| Application | Provides network services to applications | HTTP, DNS, SMTP, SSH, DHCP |
| Transport | Provides process-to-process communication | TCP, UDP |
| Internet | Provides logical addressing and routing | IPv4, IPv6, ICMP |
| Network Access | Provides local-link delivery | Ethernet, Wi-Fi, ARP |

The exact boundaries between real protocol specifications do not always fit perfectly into a simple four-row diagram. Some technologies perform functions that cross conceptual boundaries. The four-layer model is therefore most useful as an educational and architectural framework.

## Application layer

The Application layer is the layer closest to user-facing software. It defines the meaning and structure of application communication.

Examples include:

- HTTP for web communication
- DNS for name resolution
- SMTP for electronic mail transfer
- SSH for secure remote access
- DHCP for automatic network configuration

The Application layer is not the same thing as the application itself. A browser, mobile application, database client, or command-line program may use application-layer protocols.

### HTTP

HTTP defines messages such as requests and responses.

A simplified request has the conceptual structure:

`GET /index.html HTTP/1.1`

followed by headers and an optional body.

The Python implementation represents an HTTP request using `SimpleHttpRequest` and an HTTP response using `SimpleHttpResponse`.

The JavaScript implementation uses `buildHttpRequest()` to construct an HTTP-like message.

The C++ case study creates `HttpRequest` and `HttpResponse` structures as part of a larger simulated network service.

The examples demonstrate an important distinction: HTTP gives meaning to the application data, while TCP is responsible for transporting a byte stream.

## DNS

The Domain Name System translates names such as `example.com` into information such as IP addresses.

The Python implementation uses the standard library's `socket.getaddrinfo()` to perform real name resolution.

The JavaScript implementation uses Node.js's built-in `dns.promises.lookup()` API.

DNS is an Application-layer protocol even though the actual DNS exchange uses lower-layer protocols for transport.

A typical simplified process is:

`Application → DNS request → transport → IP → local network`

The response travels back through the same general layered structure.

## Transport layer

The Transport layer provides communication between processes rather than merely between machines.

The most important TCP/IP transport protocols are:

- TCP
- UDP

Port numbers are important because a host can run many network services simultaneously.

For example:

`192.168.1.20:53000`

identifies an endpoint using an IP address and a transport port.

A server might listen on:

`203.0.113.50:443`

The IP address identifies the network endpoint at the Internet layer, while the port identifies a transport-level service endpoint.

## TCP

TCP is a connection-oriented transport protocol.

Important TCP characteristics include:

- reliable delivery
- ordered byte-stream semantics
- sequence numbers
- acknowledgments
- retransmission
- flow control
- congestion control
- connection establishment
- connection termination

TCP does not preserve application message boundaries.

If an application sends:

`HELLO`

and then:

`WORLD`

the receiving application is not guaranteed to receive exactly two corresponding `recv()` operations.

The receiver could observe:

`HE`

followed by:

`LLOWOR`

followed by:

`LD`

The data is still the same byte stream.

The Python script demonstrates this concept with `tcp_stream_demo()`.

The JavaScript program demonstrates it through its TCP framing functions.

The C++ program uses `LengthPrefixedProtocol` to demonstrate how an application can define its own message boundaries.

## TCP three-way handshake

A simplified TCP connection establishment consists of:

1. SYN
2. SYN-ACK
3. ACK

The Python implementation models these using `TcpSegment`.

The JavaScript implementation uses the `TcpSegment` class.

The C++ case study uses `TcpConnection`.

A simplified example is:

`Client → Server: SYN, sequence = 1000`

`Server → Client: SYN-ACK, sequence = 7000, acknowledgment = 1001`

`Client → Server: ACK, acknowledgment = 7001`

The actual TCP protocol contains considerably more detail, including negotiated options and sequence-space behavior. The examples focus on the fundamental mechanism.

## TCP sequence numbers

TCP sequence numbers allow a byte stream to be tracked.

If a segment starts at sequence number 1000 and carries 100 bytes, the next byte is associated with sequence number 1100.

The acknowledgment number indicates the next sequence number the receiver expects.

This mechanism supports reliable ordered delivery.

The Python `ReliableChannel`, JavaScript `ReliableByteStream`, and C++ `TcpConnection` classes demonstrate simplified sequence-number behavior.

The implementations are educational models rather than replacements for an operating system TCP stack.

## TCP reliability

TCP can retransmit data when delivery is not successfully acknowledged.

Real TCP reliability is substantially more sophisticated than simply resending every unacknowledged packet. TCP uses timers, acknowledgment strategies, congestion control, retransmission algorithms, sequence numbers, and other mechanisms.

The important conceptual distinction is:

`TCP provides a reliable ordered byte stream`

rather than:

`TCP guarantees that every physical packet reaches the destination`

TCP operates over an underlying network where packets can be delayed, duplicated, reordered, or lost.

## TCP flow control

Flow control prevents a fast sender from overwhelming a receiver that cannot currently accept unlimited data.

TCP uses a receive window to communicate how much additional data the receiver is prepared to handle.

This is distinct from congestion control.

### Flow control versus congestion control

**Flow control** concerns the receiver's ability to process incoming data.

**Congestion control** concerns the condition of the network and attempts to avoid excessive network congestion.

These mechanisms solve related but different problems.

## UDP

UDP is a connectionless transport protocol.

UDP provides datagrams rather than TCP's reliable ordered byte stream.

UDP does not inherently provide:

- reliable delivery
- retransmission
- ordered delivery
- TCP-style flow control
- TCP-style congestion control

Applications can implement their own mechanisms when appropriate.

Typical uses include:

- DNS
- telemetry
- real-time applications
- certain game networking systems
- protocols designed around low-overhead datagrams

The Python and JavaScript implementations create UDP datagrams and also demonstrate real localhost UDP communication.

## TCP and UDP comparison

| Characteristic | TCP | UDP |
|---|---|---|
| Communication model | Connection-oriented | Connectionless |
| Data abstraction | Byte stream | Datagram |
| Reliability | Built in | Not built in |
| Ordering | Built in | Not guaranteed |
| Retransmission | Built in | Application responsibility |
| Flow control | Yes | No TCP-style mechanism |
| Congestion control | Yes | No TCP-style mechanism |
| Message boundaries | Not preserved | Datagram boundaries preserved |
| Typical examples | HTTP, SSH, database connections | DNS, telemetry, real-time traffic |

Neither protocol is universally appropriate. The correct choice depends on application requirements.

## Internet layer

The Internet layer provides logical addressing and routing.

Its central concepts include:

- IPv4
- IPv6
- routing
- subnetting
- packet forwarding
- TTL or Hop Limit
- ICMP

The Internet layer allows communication across multiple interconnected networks.

## IPv4

IPv4 uses 32-bit addresses.

An IPv4 address is conventionally represented as four decimal octets:

`192.168.1.20`

Each octet contains 8 bits, so the address contains:

`4 × 8 = 32 bits`

The Python implementation uses the standard `ipaddress` module.

The JavaScript implementation contains explicit IPv4 parsing and integer conversion functions.

The C++ implementation converts IPv4 addresses between dotted-decimal notation and a 32-bit integer.

## Private IPv4 addresses

Common private IPv4 ranges include:

- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`

Private addresses are normally used inside private networks and are not globally routable as ordinary public Internet destinations.

The Python, JavaScript, and C++ demonstrations distinguish address structure and routing behavior without assuming that an address's classification alone determines complete network reachability.

## Loopback

The IPv4 loopback range is used for communication with the local host.

The most familiar address is:

`127.0.0.1`

The JavaScript and Python socket demonstrations use loopback so that the examples can communicate locally without requiring another computer.

## Subnetting

Subnetting divides an address space into smaller networks.

CIDR notation expresses a prefix length:

`192.168.1.0/24`

The `/24` means that the first 24 bits form the network prefix.

An IPv4 address contains 32 bits, so the remaining:

`32 - 24 = 8`

bits are available for host addressing within the block.

A `/24` therefore contains:

`2^8 = 256`

total IPv4 addresses.

Traditional IPv4 host calculations commonly exclude the network address and broadcast address from ordinary host assignment, resulting in 254 typical usable host addresses for a conventional `/24` subnet.

## CIDR

CIDR means Classless Inter-Domain Routing.

It replaced the older class-based addressing approach and permits variable-length prefixes.

Examples include:

- `/8`
- `/16`
- `/24`
- `/28`
- `/32`

A `/32` represents one IPv4 address.

A `/0` represents the entire IPv4 address space and is commonly used as a default route.

The Python `ipaddress` module performs CIDR calculations.

The JavaScript implementation contains `cidrInfo()`.

The C++ implementation uses `prefixMask()` and related calculations.

## Routing

Routers make forwarding decisions based on destination addresses and routing information.

A simplified routing table might contain:

`0.0.0.0/0 → ISP`

`10.0.0.0/8 → Router-A`

`10.20.0.0/16 → Router-B`

`10.20.30.0/24 → Router-C`

A destination such as:

`10.20.30.15`

matches all four routes.

The router selects the most specific matching route, which is the route with the longest prefix.

This is known as **longest-prefix matching**.

The C++ case study implements this mechanism using the `RoutingTable` class.

The Python and JavaScript implementations implement equivalent routing-table behavior.

## Default route

The default route is commonly represented as:

`0.0.0.0/0`

It matches destinations that do not have a more specific route.

For example, a simplified host or router might send an unknown Internet destination to a default gateway.

A default route is not necessarily the actual path through the entire Internet. It is a local forwarding decision that delegates traffic to another router.

## TTL

IPv4 includes a Time To Live field.

Routers decrement TTL as packets pass through them. When the value reaches zero, the packet is discarded and an ICMP Time Exceeded message may be generated.

The purpose is to prevent packets caught in routing loops from circulating indefinitely.

The Python and JavaScript programs simulate this behavior.

TTL is also related to the behavior observed by tools such as traceroute, although traceroute involves additional protocol details.

## ICMP

ICMP is used for network control and diagnostic communication.

Examples include:

- Echo Request
- Echo Reply
- Destination Unreachable
- Time Exceeded

The `ping` utility commonly uses ICMP Echo Request and Echo Reply.

ICMP is not simply another transport protocol equivalent to TCP or UDP. It supports Internet-layer control and diagnostic functions.

## IPv6

IPv6 uses 128-bit addresses.

An example is:

`2001:db8::1`

IPv6 addresses are much larger than IPv4 addresses.

IPv6 also has important architectural differences, including a redesigned base header and different approaches to fragmentation and address configuration.

The Python implementation uses the standard `ipaddress` module to inspect IPv6 addresses.

The JavaScript implementation demonstrates representative IPv6 address categories.

The C++ case study concentrates on IPv4 because the routing and bitwise demonstrations are designed around a 32-bit address model.

## Network Access layer

The Network Access layer is concerned with communication across the local network.

Representative technologies include:

- Ethernet
- Wi-Fi
- ARP
- link-layer framing

The precise mapping of individual protocols can differ among descriptions of the TCP/IP architecture. ARP is commonly discussed alongside the Network Access layer because it connects Internet-layer IPv4 addresses with local link-layer addresses.

## MAC addresses

Ethernet and many other local networking technologies use MAC addresses.

A typical MAC address has 48 bits and is commonly written as six hexadecimal octets:

`00:11:22:33:44:55`

A MAC address is fundamentally different from an IP address.

An IP address is used for logical network-layer communication.

A MAC address is used for local-link delivery.

The fact that a device has both does not mean that they have interchangeable purposes.

## Ethernet frames

An Ethernet frame contains link-layer information and carries a payload.

A simplified conceptual structure is:

`Destination MAC | Source MAC | EtherType | Payload`

The Python `EthernetFrame`, JavaScript `EthernetFrame`, and C++ `EthernetFrame` classes model this structure.

The examples use EtherType `0x0800` to represent IPv4.

Real Ethernet frames contain additional fields and integrity mechanisms that are omitted from these educational structures.

## ARP

ARP is used in IPv4 local networks to determine the link-layer address associated with an IPv4 address.

For example, a host may know:

`192.168.1.1`

but need to discover the corresponding local MAC address before transmitting an Ethernet frame.

An ARP cache stores previously learned mappings.

The three implementations model an ARP cache with:

- Python dictionary-backed storage
- JavaScript `Map`
- C++ `unordered_map`

An ARP cache miss does not necessarily mean that communication is impossible. It means the mapping is not currently available in the local cache and an address-resolution process may be required.

## Encapsulation

Suppose an application wants to send:

`GET / HTTP/1.1`

A conceptual progression can be:

`Application data`

↓

`TCP header + application data`

↓

`IP header + TCP segment`

↓

`Ethernet header + IP packet`

Each layer treats the data from the layer above as its payload.

This separation allows protocols to evolve independently within defined interfaces.

The Python `EncapsulatedData` class, JavaScript buffer demonstration, and C++ case study illustrate this idea.

## Decapsulation

At the receiving host, the reverse conceptual process occurs.

The Network Access layer receives a frame.

The IP layer processes the IP packet.

The Transport layer processes TCP or UDP information.

The Application layer receives the resulting application data.

Each layer removes or interprets information associated with its responsibility.

## MTU

MTU means Maximum Transmission Unit.

A common Ethernet MTU is 1500 bytes for the IP packet payload carried by a standard Ethernet frame, although actual network configurations can differ.

An application or transport message larger than the effective path MTU may need to be handled through mechanisms such as segmentation or fragmentation.

Modern networking generally attempts to avoid unnecessary IPv4 fragmentation using Path MTU Discovery and appropriate transport behavior.

The Python program includes a numerical MTU example.

## TCP segmentation and IP fragmentation

These concepts should not be confused.

**TCP segmentation** divides a TCP byte stream into transport segments suitable for transmission.

**IP fragmentation** divides an IP packet when required under applicable IPv4 rules.

TCP segmentation is normally expected during ordinary large-data transfer.

IPv4 fragmentation is an Internet-layer mechanism with different semantics.

IPv6 handles fragmentation differently and does not permit intermediate routers to fragment packets in the same way IPv4 routers historically can.

## Application framing over TCP

Because TCP is a byte stream, applications need a framing mechanism when they need discrete messages.

Common strategies include:

### Delimiter-based framing

A message can end with a delimiter such as a newline.

Example:

`MESSAGE\n`

The limitation is that the delimiter must be escaped or otherwise handled if it can legitimately occur in the data.

### Length-prefix framing

The application sends the length before the message.

Conceptually:

`4-byte length + payload`

The Python, JavaScript, and C++ implementations all demonstrate length-prefixed framing.

### Structured protocol framing

Protocols such as HTTP define their own framing rules involving headers, content length, chunking, or other mechanisms.

## Application protocol design

A reliable transport does not automatically make an application protocol reliable in every semantic sense.

For example, TCP can reliably deliver:

`TRANSFER $100`

but it cannot determine whether:

- the user is authorized,
- the transaction is valid,
- the account has sufficient funds,
- the request is duplicated,
- the business operation should be rolled back.

Those are application-level concerns.

A production protocol may therefore need:

- request identifiers
- authentication
- authorization
- validation
- idempotency rules
- transaction handling
- timeouts
- rate limiting
- structured errors
- logging
- monitoring

## Python implementation

The Python script is designed as a broad study program.

It begins with the conceptual four-layer model and then demonstrates:

- TCP/IP terminology
- HTTP-like application messages
- DNS lookup
- transport ports
- TCP socket addresses
- TCP three-way handshake
- sequence numbers
- acknowledgment calculations
- UDP datagrams
- TCP versus UDP
- IPv4 addressing
- subnetting
- routing
- longest-prefix matching
- IPv4 header concepts
- TTL
- ICMP
- MAC addresses
- Ethernet frames
- ARP
- encapsulation
- MTU
- IPv6
- TCP stream behavior
- application framing
- data-integrity hashing
- security concepts
- validation
- performance considerations
- troubleshooting
- real TCP sockets
- real UDP sockets
- self-tests

The script uses Python's standard library rather than requiring third-party packages.

### Python application layer

`SimpleHttpRequest` and `SimpleHttpResponse` model application-layer HTTP structures.

The objects deliberately separate the HTTP message from TCP transport behavior.

### Python transport layer

`TcpSegment` represents important TCP fields such as:

- sequence number
- acknowledgment number
- SYN
- ACK
- FIN
- RST
- payload

`ReliableChannel` provides a simplified sequence-number demonstration.

The real socket examples use Python's `socket` module, allowing a localhost TCP server and client to communicate through the operating system's actual networking stack.

### Python Internet layer

Python's `ipaddress` module provides robust IPv4 and IPv6 address handling.

The custom `RoutingTable` class demonstrates longest-prefix matching.

This distinction is useful because a real operating system's routing subsystem is much more complex than a small educational class.

### Python Network Access layer

The script represents Ethernet frames and ARP caches using simple Python classes.

These classes model the concepts rather than directly constructing and transmitting raw Ethernet frames.

Raw link-layer programming can require operating-system-specific privileges and APIs, so it is intentionally not required for the core study program.

## JavaScript implementation

The JavaScript file complements the Python implementation by demonstrating networking concepts through Node.js.

It includes:

- HTTP-like request construction
- DNS lookup
- port validation
- TCP segment modeling
- TCP sequence-number behavior
- UDP datagrams
- IPv4 parsing
- CIDR calculations
- routing
- IPv6 concepts
- TTL simulation
- ARP caching
- Ethernet frames
- encapsulation
- TCP application framing
- SHA-256 integrity checking
- local network interface inspection
- real TCP sockets
- real UDP sockets
- security principles
- troubleshooting
- performance considerations
- self-tests

Node.js is particularly useful here because JavaScript can interact directly with operating-system networking APIs through the standard library.

### JavaScript TCP sockets

The `net` module provides TCP socket functionality.

The program creates a server on `127.0.0.1` using an automatically selected port.

The client connects to that server and exchanges data.

This demonstrates the difference between a conceptual TCP model and an actual operating-system socket interface.

### JavaScript UDP sockets

The `dgram` module provides UDP networking.

The example creates a UDP receiver and sender on localhost.

This demonstrates that UDP can send a datagram without establishing a TCP-style connection first.

### JavaScript asynchronous execution

Network operations are naturally asynchronous because data can arrive later.

The program therefore uses:

- Promises
- `async` and `await`
- event handlers
- callbacks

This is an important JavaScript-specific aspect of network programming.

The networking model remains the same, but the programming model used to access it differs from Python and C++.

## C++ case study

The C++ implementation models an industry-style network service.

The scenario is a client sending an HTTP-like request to a server.

The simulated path is:

`Application → TCP → IPv4 → Ethernet`

The case study includes:

- HTTP request and response objects
- TCP state management
- TCP handshake
- TCP segments
- sequence numbers
- UDP datagrams
- IPv4 packets
- CIDR calculations
- routing-table lookup
- longest-prefix matching
- ARP cache
- Ethernet frames
- length-prefixed application framing
- validation
- exception handling
- self-tests
- performance considerations
- security considerations

## C++ architecture

The main components are separated into classes and structures.

### HttpRequest and HttpResponse

These represent application-layer messages.

They demonstrate that the application protocol determines the meaning of the payload.

### TcpSegment

`TcpSegment` contains simplified TCP fields.

The `describe()` method produces a human-readable representation of the segment.

### TcpConnection

`TcpConnection` models a simplified TCP state machine.

The states include:

- CLOSED
- LISTEN
- SYN-SENT
- SYN-RECEIVED
- ESTABLISHED
- FIN-WAIT
- CLOSE-WAIT

A complete production TCP implementation contains many more states and transitions. The case study intentionally focuses on the concepts necessary to understand connection establishment and data transmission.

### Ipv4Packet

`Ipv4Packet` represents source address, destination address, TTL, protocol, and payload.

It demonstrates that the IP layer does not need to understand the application message's semantic meaning.

### Route and RoutingTable

The `Route` class represents a CIDR network and next hop.

`RoutingTable::lookup()` selects the matching route with the longest prefix.

This directly demonstrates an important Internet-layer forwarding principle.

### EthernetFrame

`EthernetFrame` represents local-link delivery information.

The IP packet becomes the payload of the Ethernet frame.

### ArpCache

`ArpCache` models local IPv4-to-MAC resolution state.

The implementation uses `unordered_map` for efficient average-case lookup.

### LengthPrefixedProtocol

This component solves a common TCP application-layer problem.

Because TCP provides a byte stream rather than messages, the application adds a four-byte length field before each message.

The receiver reads the length and waits until the complete message is available.

## C++ end-to-end request

The `NetworkService::processRequest()` method demonstrates the complete conceptual flow.

The request begins as an application message.

The transport layer creates a TCP connection and sends a TCP segment.

The Internet layer wraps the segment in an IPv4 packet.

The routing table selects a forwarding path.

The Network Access layer wraps the packet in an Ethernet frame.

The server then produces an HTTP-like application response.

This is the central architectural example in the C++ implementation.

## Layer boundaries

The TCP/IP layers should not be interpreted as completely independent pieces of code.

For example:

- an HTTP server uses TCP sockets;
- TCP depends on IP for packet delivery;
- IP depends on a local network interface;
- Ethernet or Wi-Fi carries IP packets;
- ARP may be used to resolve a local IPv4 next-hop address.

The layers cooperate through defined interfaces.

## Port numbers

A port is a transport-layer identifier.

A complete network endpoint can conceptually be represented as:

`IP address + transport protocol + port`

For example:

`192.168.1.20 + TCP + 53000`

A TCP connection is commonly described using a four-part endpoint relationship:

`source IP, source port, destination IP, destination port`

The transport protocol is also significant because TCP and UDP have independent port spaces.

## Sockets

A socket is an operating-system abstraction used by applications to communicate through networking protocols.

A TCP server commonly performs operations corresponding conceptually to:

`socket → bind → listen → accept → receive/send → close`

A TCP client commonly performs:

`socket → connect → send/receive → close`

UDP is different because a typical datagram socket does not require the same connection-establishment process.

The Python and JavaScript implementations demonstrate actual localhost sockets.

## Blocking and asynchronous behavior

A network operation may take an unpredictable amount of time.

Possible causes include:

- remote processing
- routing delay
- packet loss
- retransmission
- DNS resolution
- congestion
- server overload
- connection establishment

Applications therefore need timeouts and appropriate concurrency strategies.

Python can use blocking sockets, threads, asynchronous programming, or other concurrency models.

Node.js commonly uses event-driven asynchronous APIs.

C++ applications can use blocking sockets, asynchronous APIs, event loops, threads, or specialized networking frameworks.

The underlying TCP/IP behavior does not change merely because the programming model changes.

## Error handling

Network programming must expect failure.

Important conditions include:

- invalid addresses
- invalid ports
- connection refusal
- connection timeout
- connection reset
- DNS failure
- unreachable destinations
- malformed application messages
- incomplete messages
- peer disconnects
- resource exhaustion

The three implementations include validation and error-handling examples.

A robust network service should not assume that remote input is valid or that the network is reliable.

## Security considerations

TCP/IP itself does not make an application secure.

Important distinctions include:

### Transport versus encryption

TCP provides reliable byte-stream transport.

TCP does not encrypt the application payload.

TLS can provide encryption, integrity protection, and peer authentication for protocols such as HTTPS.

### Authentication

Authentication answers a question such as:

`Who is this peer?`

### Authorization

Authorization answers:

`What is this authenticated identity allowed to do?`

These are different security controls.

### Input validation

Network data must be treated as untrusted.

Validation should cover:

- message length
- field formats
- numeric ranges
- protocol states
- authentication data
- resource usage
- application-specific constraints

### Denial-of-service considerations

A server can be affected by excessive connections, oversized messages, slow clients, or expensive requests.

Useful controls include:

- connection limits
- request limits
- timeouts
- rate limiting
- bounded buffers
- resource quotas
- monitoring

## Performance considerations

Several measurements are important in networking.

### Latency

Latency describes the time required for communication or a particular operation.

A request may experience latency from:

- DNS lookup
- TCP connection establishment
- TLS negotiation
- network propagation
- routing
- server processing
- response transmission

### Bandwidth

Bandwidth describes the capacity of a communication link.

It does not necessarily equal the throughput experienced by an application.

### Throughput

Throughput describes the amount of useful data successfully transferred over time.

Packet loss, congestion, protocol overhead, server limitations, and latency can all influence throughput.

### Connection overhead

Repeatedly creating short-lived connections can add overhead.

Persistent connections can reduce repeated connection establishment costs.

### Buffering

Buffers allow applications and operating systems to absorb differences between producer and consumer rates.

Unbounded buffering can create memory-exhaustion risks, so production systems normally impose limits.

## Troubleshooting by layer

A layered model is useful when diagnosing network failures.

### Application

Questions include:

- Is the service running?
- Is the request syntactically correct?
- Is authentication valid?
- Is the requested resource available?
- What do application logs report?

### Transport

Questions include:

- Is the correct port being used?
- Is the server listening?
- Is TCP or UDP appropriate?
- Is the connection timing out?
- Is the connection being reset?

### Internet

Questions include:

- Is the destination IP correct?
- Is the local address correct?
- Is a route available?
- Is the default gateway configured?
- Is the packet reaching the expected network?

### Network Access

Questions include:

- Is the network interface active?
- Is the local link available?
- Is Wi-Fi connected?
- Is Ethernet connected?
- Is the local address resolution working?

This layered method helps narrow a failure without assuming that every problem is caused by the same layer.

## Important distinctions

### IP address versus MAC address

An IP address provides logical addressing used for routing.

A MAC address provides local link-layer addressing.

They solve different problems.

### Router versus switch

A router primarily makes forwarding decisions at the Internet layer.

A switch primarily forwards local-link frames using link-layer information.

Real devices can perform many functions simultaneously, so the distinction is architectural rather than a claim that every physical product performs exactly one role.

### TCP versus IP

TCP provides transport-layer communication.

IP provides Internet-layer addressing and packet delivery.

TCP does not replace IP, and IP does not provide TCP's reliable byte-stream behavior.

### TCP versus HTTP

HTTP defines application-level semantics.

TCP provides transport.

An HTTP request may be transported over TCP in traditional HTTP/1.1 deployments, while modern protocols such as HTTP/3 use QUIC over UDP.

This demonstrates why application protocol and transport protocol are distinct concepts.

## Common mistakes

### Treating TCP as message-oriented

TCP is a byte stream.

Applications requiring messages need framing.

### Assuming TCP guarantees instant delivery

TCP provides reliability mechanisms, but communication can still experience significant delay.

Applications need appropriate timeouts and failure handling.

### Treating UDP as inherently unreliable in every application sense

UDP itself does not provide TCP-style reliability.

An application can build reliability mechanisms on top of UDP when required.

### Confusing bandwidth with latency

A high-bandwidth link can still have high latency.

A low-bandwidth link can have low latency.

They describe different properties.

### Assuming an IP address uniquely identifies a process

An IP address identifies a network endpoint at the Internet layer.

Ports distinguish transport-level services.

Multiple processes can communicate through the same host address using different ports.

### Assuming a successful ping proves an application is working

ICMP reachability does not prove that:

- the application is running;
- the intended port is open;
- the application protocol is correct;
- authentication succeeds;
- the application resource exists.

Different tests operate at different layers.

## Edge cases

### Invalid IPv4 addresses

Values outside the `0` through `255` range for an octet are invalid.

Examples include:

`300.1.1.1`

and malformed addresses with missing octets.

The Python, JavaScript, and C++ programs validate addresses.

### Invalid ports

A TCP or UDP port is represented by a 16-bit value.

The usable numeric range is:

`0` through `65535`

Port zero has special semantics and is not normally used as an ordinary service port.

The example validation functions treat ports from `1` through `65535` as ordinary valid service ports.

### Empty application messages

An application protocol may need to distinguish an empty message from a missing message.

Length-prefixed protocols must define whether a zero-length message is legal.

### Incomplete TCP data

A receiver may obtain only part of a length-prefixed message.

The receiver must retain the incomplete bytes and wait for additional data.

The framing examples explicitly handle incomplete buffers.

### Oversized messages

Production systems should not accept unlimited message sizes.

A length field can be syntactically valid while still requesting an amount of memory that the application cannot safely allocate.

Therefore, a production implementation should validate a maximum permitted message size before allocating resources.

## Limitations of the examples

The implementations are educational models and do not attempt to reproduce a complete operating-system network stack.

The simplified TCP models omit many real mechanisms, including:

- congestion-control algorithms
- receive windows
- selective acknowledgments
- retransmission timers
- TCP options
- timestamp behavior
- full connection-state transitions
- simultaneous open
- retransmission edge cases
- packet reordering
- duplicate detection
- modern TCP extensions

The routing examples implement longest-prefix matching but do not reproduce the complete behavior of production routing protocols.

The Ethernet examples model frame structure rather than transmitting raw Ethernet frames.

The ARP examples model cached mappings rather than implementing an actual ARP exchange.

The IPv6 examples introduce addressing concepts but do not implement a complete IPv6 stack.

These limitations are intentional. They keep the underlying mechanisms visible without hiding them behind a complete operating-system implementation.

## Complexity considerations

The C++ routing table performs a linear scan over available routes.

If there are `R` routes, the basic lookup is:

`O(R)`

Production routers use specialized data structures and hardware mechanisms that can make forwarding decisions much faster than a simple educational linear scan.

The ARP cache uses an `unordered_map`, giving average-case constant-time lookup under normal hash-table assumptions.

Length-prefixed message decoding requires constant-time header interpretation followed by access to the payload. The amount of data ultimately processed is proportional to the message size.

IP address conversion processes a fixed number of IPv4 octets, so its computational cost is effectively constant with respect to network size.

## Why the three languages are useful

### Python

Python is useful for explaining networking because its syntax is concise and its standard library includes:

- sockets
- address handling
- hashing
- structured data
- exception handling

The Python implementation emphasizes conceptual clarity and direct experimentation.

### JavaScript

JavaScript, especially through Node.js, is useful for demonstrating:

- event-driven networking
- asynchronous operations
- callbacks
- Promises
- TCP streams
- UDP datagrams
- application-layer web behavior

It connects networking concepts with common server-side JavaScript programming patterns.

### C++

C++ makes memory, data representation, bit operations, classes, and performance considerations more explicit.

The C++ case study demonstrates how a network service can be decomposed into components representing application messages, transport segments, IP packets, routing, ARP, and Ethernet frames.

This makes C++ particularly useful for understanding how abstract networking concepts map toward lower-level system implementation.

## Real-world relevance

The TCP/IP model provides a practical framework for analyzing systems such as:

- web applications
- APIs
- cloud services
- databases
- distributed systems
- enterprise networks
- mobile applications
- IoT systems
- streaming systems
- remote administration
- network security infrastructure

A web request, for example, may involve:

`HTTP → TCP → IP → Ethernet/Wi-Fi`

with additional systems such as DNS, TLS, routers, switches, firewalls, load balancers, and proxies participating in the complete communication path.

Modern protocols can alter particular parts of this stack. HTTP/3, for example, uses QUIC over UDP rather than traditional HTTP-over-TCP transport. The four-layer model remains useful because it encourages separation of application, transport, Internet, and local-link responsibilities even when the exact protocol stack changes.

## Production implementation considerations

A production network service generally requires more than protocol knowledge.

Important engineering considerations include:

- explicit timeouts
- bounded memory usage
- connection limits
- structured logging
- metrics
- tracing
- authentication
- authorization
- encryption
- input validation
- graceful shutdown
- retry policies
- idempotency
- concurrency control
- configuration management
- failure isolation
- monitoring
- resource cleanup

The appropriate design depends on the application protocol and its operational requirements.

A network program should be designed with the assumption that remote peers can disconnect unexpectedly and that network communication can fail at any time.

## Practical conceptual model

When analyzing any networked application, the following questions help identify the relevant layer:

| Question | Layer |
|---|---|
| What does the message mean? | Application |
| Which process receives it? | Transport |
| Which IP destination should receive it? | Internet |
| Which local network interface or link carries it? | Network Access |
| How is reliability provided? | Usually Transport |
| How is routing performed? | Internet |
| How is a local next-hop address resolved? | Network Access support for Internet-layer communication |
| How is confidentiality provided? | Usually an upper-layer security protocol such as TLS |

The four layers are best understood as cooperating responsibilities rather than as four independent programs.

## Key implementation relationships

The Python implementation emphasizes executable demonstrations and standard-library networking.

The JavaScript implementation emphasizes Node.js networking, asynchronous execution, streams, and datagrams.

The C++ implementation emphasizes explicit system modeling, data structures, bitwise address calculations, state machines, routing, framing, validation, and an integrated network-service case study.

Together, the implementations demonstrate the same fundamental path:

`Application`

↓

`Transport`

↓

`Internet`

↓

`Network Access`

and the reverse process during reception.

The central architectural principle is that each layer provides services to the layer above it while relying on services from the layer below it.
