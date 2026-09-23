/*
 * TCP/IP MODEL
 *
 * A self-contained JavaScript study program covering:
 *   Application
 *   Transport
 *   Internet
 *   Network Access
 *
 * The examples use Node.js standard-library APIs where practical.
 * No third-party packages are required.
 */

"use strict";

const net = require("net");
const dgram = require("dgram");
const dns = require("dns").promises;
const crypto = require("crypto");
const os = require("os");

// ============================================================================
// 1. TCP/IP MODEL
// ============================================================================

const layers = [
    {
        name: "Application",
        purpose:
            "Provides network services directly to applications.",
        protocols: ["HTTP", "DNS", "SMTP", "SSH", "DHCP"],
    },
    {
        name: "Transport",
        purpose:
            "Provides process-to-process communication.",
        protocols: ["TCP", "UDP"],
    },
    {
        name: "Internet",
        purpose:
            "Provides logical addressing and routing between networks.",
        protocols: ["IPv4", "IPv6", "ICMP"],
    },
    {
        name: "Network Access",
        purpose:
            "Provides local-link communication using technologies such as Ethernet and Wi-Fi.",
        protocols: ["Ethernet", "Wi-Fi", "ARP"],
    },
];

function printModel() {
    console.log("\nTCP/IP MODEL");
    console.log("=".repeat(72));

    for (const layer of layers) {
        console.log(`${layer.name.padEnd(18)} | ${layer.purpose}`);
        console.log(`Protocols: ${layer.protocols.join(", ")}`);
    }
}

// ============================================================================
// 2. APPLICATION-LAYER HTTP MESSAGE
// ============================================================================

function buildHttpRequest(method, path, headers = {}, body = "") {
    if (!method || !path) {
        throw new Error("HTTP method and path are required.");
    }

    const lines = [`${method.toUpperCase()} ${path} HTTP/1.1`];

    for (const [name, value] of Object.entries(headers)) {
        lines.push(`${name}: ${value}`);
    }

    lines.push("");
    lines.push(body);

    return lines.join("\r\n");
}

function applicationLayerDemo() {
    console.log("\nAPPLICATION LAYER");
    console.log("=".repeat(72));

    const request = buildHttpRequest(
        "GET",
        "/networking?topic=tcp-ip",
        {
            Host: "example.test",
            Accept: "application/json",
            Connection: "close",
        }
    );

    console.log(request);

    const response = [
        "HTTP/1.1 200 OK",
        "Content-Type: application/json",
        "",
        JSON.stringify({
            topic: "TCP/IP",
            status: "available",
            layerCount: 4,
        }),
    ].join("\r\n");

    console.log("\nHTTP response:");
    console.log(response);
}

// ============================================================================
// 3. DNS
// ============================================================================

async function dnsDemo() {
    console.log("\nDNS DEMONSTRATION");
    console.log("=".repeat(72));

    for (const hostname of ["localhost", "example.com"]) {
        try {
            const addresses = await dns.lookup(hostname, {
                all: true,
            });

            console.log(
                `${hostname.padEnd(20)} ->`,
                addresses.map((item) => `${item.address} (${item.family})`)
            );
        } catch (error) {
            console.log(
                `${hostname.padEnd(20)} -> DNS lookup failed: ${error.message}`
            );
        }
    }
}

// ============================================================================
// 4. TRANSPORT LAYER: PORTS
// ============================================================================

function validatePort(port) {
    if (!Number.isInteger(port)) {
        throw new TypeError("Port must be an integer.");
    }

    if (port < 1 || port > 65535) {
        throw new RangeError("Port must be between 1 and 65535.");
    }

    return true;
}

function portDemo() {
    console.log("\nTRANSPORT PORTS");
    console.log("=".repeat(72));

    const ports = [22, 53, 80, 443, 3306, 5432];

    for (const port of ports) {
        validatePort(port);
        console.log(`${port}: valid transport-layer port number`);
    }

    for (const invalidPort of [0, 65536, 443.5]) {
        try {
            validatePort(invalidPort);
        } catch (error) {
            console.log(`${invalidPort}: ${error.message}`);
        }
    }
}

// ============================================================================
// 5. TCP SEGMENT MODEL
// ============================================================================

class TcpSegment {
    constructor({
        sequenceNumber,
        acknowledgmentNumber,
        syn = false,
        ack = false,
        fin = false,
        rst = false,
        payload = Buffer.alloc(0),
    }) {
        this.sequenceNumber = sequenceNumber;
        this.acknowledgmentNumber = acknowledgmentNumber;
        this.syn = syn;
        this.ack = ack;
        this.fin = fin;
        this.rst = rst;
        this.payload = Buffer.from(payload);
    }

    flags() {
        const result = [];

        if (this.syn) result.push("SYN");
        if (this.ack) result.push("ACK");
        if (this.fin) result.push("FIN");
        if (this.rst) result.push("RST");

        return result.length > 0 ? result.join(",") : "-";
    }

    describe() {
        return (
            `SEQ=${this.sequenceNumber}, ` +
            `ACK=${this.acknowledgmentNumber}, ` +
            `FLAGS=${this.flags()}, ` +
            `PAYLOAD=${this.payload.length} bytes`
        );
    }
}

function tcpHandshakeDemo() {
    console.log("\nTCP THREE-WAY HANDSHAKE");
    console.log("=".repeat(72));

    const clientInitialSequence = 1000;
    const serverInitialSequence = 7000;

    const syn = new TcpSegment({
        sequenceNumber: clientInitialSequence,
        acknowledgmentNumber: 0,
        syn: true,
    });

    const synAck = new TcpSegment({
        sequenceNumber: serverInitialSequence,
        acknowledgmentNumber: clientInitialSequence + 1,
        syn: true,
        ack: true,
    });

    const ack = new TcpSegment({
        sequenceNumber: clientInitialSequence + 1,
        acknowledgmentNumber: serverInitialSequence + 1,
        ack: true,
    });

    console.log("1. Client -> Server:", syn.describe());
    console.log("2. Server -> Client:", synAck.describe());
    console.log("3. Client -> Server:", ack.describe());
}

// ============================================================================
// 6. TCP RELIABILITY
// ============================================================================

class ReliableByteStream {
    constructor() {
        this.nextSequenceNumber = 0;
    }

    createSegment(data) {
        const payload = Buffer.from(data);

        const segment = new TcpSegment({
            sequenceNumber: this.nextSequenceNumber,
            acknowledgmentNumber: 0,
            payload,
        });

        this.nextSequenceNumber += payload.length;

        return segment;
    }

    expectedAcknowledgment(segment) {
        return segment.sequenceNumber + segment.payload.length;
    }
}

function tcpReliabilityDemo() {
    console.log("\nTCP SEQUENCE NUMBERS");
    console.log("=".repeat(72));

    const stream = new ReliableByteStream();

    for (const message of ["TCP ", "uses ", "sequence ", "numbers."]) {
        const segment = stream.createSegment(message);
        const acknowledgment =
            stream.expectedAcknowledgment(segment);

        console.log(
            `${JSON.stringify(message)} -> ` +
            `SEQ=${segment.sequenceNumber}, ` +
            `next ACK=${acknowledgment}`
        );
    }
}

// ============================================================================
// 7. UDP
// ============================================================================

class UdpDatagram {
    constructor(sourcePort, destinationPort, payload) {
        validatePort(sourcePort);
        validatePort(destinationPort);

        this.sourcePort = sourcePort;
        this.destinationPort = destinationPort;
        this.payload = Buffer.from(payload);
    }

    describe() {
        return (
            `${this.sourcePort} -> ${this.destinationPort}, ` +
            `${this.payload.length} bytes`
        );
    }
}

function udpDemo() {
    console.log("\nUDP");
    console.log("=".repeat(72));

    const datagrams = [
        new UdpDatagram(50000, 53, "DNS query"),
        new UdpDatagram(50001, 123, "NTP request"),
        new UdpDatagram(50002, 9999, "telemetry"),
    ];

    for (const datagram of datagrams) {
        console.log(datagram.describe());
    }
}

// ============================================================================
// 8. TCP VS UDP
// ============================================================================

function compareTcpUdp() {
    console.log("\nTCP VS UDP");
    console.log("=".repeat(72));

    const comparison = [
        ["Connection", "Connection-oriented", "Connectionless"],
        ["Ordering", "Ordered byte stream", "Independent datagrams"],
        ["Reliability", "Built in", "Not built in"],
        ["Retransmission", "TCP-managed", "Application responsibility"],
        ["Flow control", "Yes", "No TCP-style flow control"],
        ["Congestion control", "Yes", "No TCP-style mechanism"],
        ["Typical use", "HTTP, SSH, databases", "DNS, telemetry, real-time traffic"],
    ];

    for (const [property, tcp, udp] of comparison) {
        console.log(`${property.padEnd(18)} TCP=${tcp}`);
        console.log(`${"".padEnd(18)} UDP=${udp}`);
    }
}

// ============================================================================
// 9. IPv4 VALIDATION
// ============================================================================

function parseIpv4(address) {
    const parts = address.split(".");

    if (parts.length !== 4) {
        return null;
    }

    const numbers = parts.map(Number);

    if (
        numbers.some(
            (value, index) =>
                parts[index] === "" ||
                !Number.isInteger(value) ||
                value < 0 ||
                value > 255
        )
    ) {
        return null;
    }

    return numbers;
}

function isPrivateIpv4(address) {
    const parts = parseIpv4(address);

    if (!parts) {
        return false;
    }

    const [a, b] = parts;

    return (
        a === 10 ||
        (a === 172 && b >= 16 && b <= 31) ||
        (a === 192 && b === 168)
    );
}

function ipv4Demo() {
    console.log("\nINTERNET LAYER: IPv4");
    console.log("=".repeat(72));

    for (const address of [
        "192.168.1.10",
        "10.0.0.5",
        "172.16.20.30",
        "8.8.8.8",
        "127.0.0.1",
        "300.1.1.1",
    ]) {
        const parsed = parseIpv4(address);

        console.log(
            `${address.padEnd(16)} ` +
            `valid=${parsed !== null} ` +
            `private=${isPrivateIpv4(address)}`
        );
    }
}

// ============================================================================
// 10. CIDR AND SUBNET CALCULATIONS
// ============================================================================

function ipv4ToInteger(address) {
    const parts = parseIpv4(address);

    if (!parts) {
        throw new Error(`Invalid IPv4 address: ${address}`);
    }

    return (
        (((parts[0] << 24) >>> 0) |
            (parts[1] << 16) |
            (parts[2] << 8) |
            parts[3]) >>>
        0
    );
}

function integerToIpv4(value) {
    return [
        (value >>> 24) & 255,
        (value >>> 16) & 255,
        (value >>> 8) & 255,
        value & 255,
    ].join(".");
}

function cidrInfo(address, prefixLength) {
    if (
        !Number.isInteger(prefixLength) ||
        prefixLength < 0 ||
        prefixLength > 32
    ) {
        throw new RangeError("IPv4 prefix length must be 0 through 32.");
    }

    const ip = ipv4ToInteger(address);

    const mask =
        prefixLength === 0
            ? 0
            : (0xffffffff << (32 - prefixLength)) >>> 0;

    const network = ip & mask;
    const wildcard = (~mask) >>> 0;
    const broadcast = (network | wildcard) >>> 0;

    return {
        network: integerToIpv4(network >>> 0),
        broadcast: integerToIpv4(broadcast),
        totalAddresses:
            prefixLength === 32
                ? 1
                : 2 ** (32 - prefixLength),
        mask: integerToIpv4(mask),
    };
}

function subnetDemo() {
    console.log("\nCIDR SUBNETTING");
    console.log("=".repeat(72));

    for (const [address, prefix] of [
        ["192.168.1.20", 24],
        ["10.10.15.7", 16],
        ["172.16.20.40", 28],
    ]) {
        const info = cidrInfo(address, prefix);

        console.log(
            `${address}/${prefix} -> ` +
            `network=${info.network}, ` +
            `broadcast=${info.broadcast}, ` +
            `mask=${info.mask}, ` +
            `addresses=${info.totalAddresses}`
        );
    }
}

// ============================================================================
// 11. ROUTING
// ============================================================================

class Route {
    constructor(network, prefixLength, nextHop) {
        this.network = network;
        this.prefixLength = prefixLength;
        this.nextHop = nextHop;
        this.networkInteger = ipv4ToInteger(network);
    }

    matches(destination) {
        const destinationInteger = ipv4ToInteger(destination);

        const mask =
            this.prefixLength === 0
                ? 0
                : (0xffffffff << (32 - this.prefixLength)) >>> 0;

        return (
            (destinationInteger & mask) ===
            (this.networkInteger & mask)
        );
    }
}

class RoutingTable {
    constructor(routes) {
        this.routes = routes;
    }

    lookup(destination) {
        const matches = this.routes.filter((route) =>
            route.matches(destination)
        );

        if (matches.length === 0) {
            return null;
        }

        return matches.reduce((best, current) =>
            current.prefixLength > best.prefixLength
                ? current
                : best
        );
    }
}

function routingDemo() {
    console.log("\nLONGEST-PREFIX ROUTING");
    console.log("=".repeat(72));

    const table = new RoutingTable([
        new Route("0.0.0.0", 0, "ISP"),
        new Route("10.0.0.0", 8, "Router-A"),
        new Route("10.20.0.0", 16, "Router-B"),
        new Route("10.20.30.0", 24, "Router-C"),
    ]);

    for (const destination of [
        "10.20.30.15",
        "10.20.99.1",
        "10.50.1.1",
        "8.8.8.8",
    ]) {
        const route = table.lookup(destination);

        console.log(
            `${destination.padEnd(16)} -> ` +
            `${route.network}/${route.prefixLength} via ${route.nextHop}`
        );
    }
}

// ============================================================================
// 12. IPv6
// ============================================================================

function ipv6Demo() {
    console.log("\nIPv6");
    console.log("=".repeat(72));

    const addresses = [
        "::1",
        "fe80::1234",
        "2001:db8::1",
        "2001:4860:4860::8888",
    ];

    for (const address of addresses) {
        const normalized = address.toLowerCase();

        console.log(
            `${address.padEnd(30)} ` +
            `loopback=${normalized === "::1"} ` +
            `link-local=${normalized.startsWith("fe80:")}`
        );
    }

    console.log(
        "IPv6 uses 128-bit addresses and supports a much larger address space than IPv4."
    );
}

// ============================================================================
// 13. TTL
// ============================================================================

function simulateTtl(initialTtl, hops) {
    if (!Number.isInteger(initialTtl) || initialTtl <= 0) {
        throw new Error("TTL must be a positive integer.");
    }

    if (!Number.isInteger(hops) || hops < 0) {
        throw new Error("Hop count must be a non-negative integer.");
    }

    const remaining = initialTtl - hops;

    return remaining <= 0
        ? "TTL expired; the packet would be discarded."
        : `Packet survives with TTL=${remaining}.`;
}

function ttlDemo() {
    console.log("\nTTL");
    console.log("=".repeat(72));

    for (const [ttl, hops] of [
        [64, 5],
        [3, 3],
        [2, 5],
    ]) {
        console.log(`TTL=${ttl}, hops=${hops} -> ${simulateTtl(ttl, hops)}`);
    }
}

// ============================================================================
// 14. ARP CONCEPT
// ============================================================================

class ArpCache {
    constructor() {
        this.entries = new Map();
    }

    add(ipAddress, macAddress) {
        this.entries.set(ipAddress, macAddress.toUpperCase());
    }

    lookup(ipAddress) {
        return this.entries.get(ipAddress) ?? null;
    }
}

function arpDemo() {
    console.log("\nARP");
    console.log("=".repeat(72));

    const cache = new ArpCache();

    cache.add("192.168.1.1", "aa:bb:cc:dd:ee:01");
    cache.add("192.168.1.20", "aa:bb:cc:dd:ee:20");

    console.log(
        "192.168.1.20 ->",
        cache.lookup("192.168.1.20")
    );

    console.log(
        "ARP maps a local IPv4 address to a link-layer address."
    );
}

// ============================================================================
// 15. ETHERNET FRAME
// ============================================================================

class EthernetFrame {
    constructor(destinationMac, sourceMac, etherType, payload) {
        this.destinationMac = destinationMac;
        this.sourceMac = sourceMac;
        this.etherType = etherType;
        this.payload = Buffer.from(payload);
    }

    describe() {
        return (
            `dst=${this.destinationMac}, ` +
            `src=${this.sourceMac}, ` +
            `EtherType=0x${this.etherType
                .toString(16)
                .padStart(4, "0")
                .toUpperCase()}, ` +
            `payload=${this.payload.length} bytes`
        );
    }
}

function ethernetDemo() {
    console.log("\nETHERNET");
    console.log("=".repeat(72));

    const frame = new EthernetFrame(
        "AA:BB:CC:DD:EE:FF",
        "00:11:22:33:44:55",
        0x0800,
        "IPv4 packet"
    );

    console.log(frame.describe());
    console.log("0x0800 represents IPv4 in Ethernet.");
}

// ============================================================================
// 16. ENCAPSULATION
// ============================================================================

function encapsulationDemo() {
    console.log("\nENCAPSULATION");
    console.log("=".repeat(72));

    const applicationData = Buffer.from("Hello TCP/IP");
    const tcpHeader = Buffer.from("[TCP HEADER]");
    const ipHeader = Buffer.from("[IPv4 HEADER]");
    const ethernetHeader = Buffer.from("[ETHERNET HEADER]");

    const tcpSegment = Buffer.concat([
        tcpHeader,
        applicationData,
    ]);

    const ipPacket = Buffer.concat([
        ipHeader,
        tcpSegment,
    ]);

    const frame = Buffer.concat([
        ethernetHeader,
        ipPacket,
    ]);

    console.log("Application:", applicationData.toString());
    console.log("TCP segment:", tcpSegment.toString());
    console.log("IP packet:", ipPacket.toString());
    console.log("Ethernet frame:", frame.toString());
}

// ============================================================================
// 17. TCP STREAM FRAMING
// ============================================================================

function encodeLengthPrefixed(message) {
    const payload = Buffer.from(message);
    const header = Buffer.alloc(4);

    header.writeUInt32BE(payload.length, 0);

    return Buffer.concat([header, payload]);
}

function decodeLengthPrefixed(buffer) {
    if (buffer.length < 4) {
        return null;
    }

    const length = buffer.readUInt32BE(0);

    if (buffer.length < 4 + length) {
        return null;
    }

    return {
        message: buffer.subarray(4, 4 + length),
        consumed: 4 + length,
    };
}

function framingDemo() {
    console.log("\nTCP APPLICATION MESSAGE FRAMING");
    console.log("=".repeat(72));

    const encoded = encodeLengthPrefixed("hello network");

    console.log("Encoded:", encoded);

    const decoded = decodeLengthPrefixed(encoded);

    console.log(
        "Decoded:",
        decoded.message.toString(),
        "consumed:",
        decoded.consumed
    );

    console.log(
        "TCP provides a byte stream, so an application protocol must define message boundaries."
    );
}

// ============================================================================
// 18. HASH-BASED INTEGRITY
// ============================================================================

function sha256(data) {
    return crypto
        .createHash("sha256")
        .update(data)
        .digest("hex");
}

function integrityDemo() {
    console.log("\nINTEGRITY");
    console.log("=".repeat(72));

    const original = "important payload";
    const modified = "important payloaD";

    console.log("Original:", sha256(original));
    console.log("Modified:", sha256(modified));
    console.log("Equal:", sha256(original) === sha256(modified));

    console.log(
        "A hash detects changes but does not by itself authenticate the sender."
    );
}

// ============================================================================
// 19. REAL TCP SOCKET DEMONSTRATION
// ============================================================================

function tcpSocketDemo() {
    return new Promise((resolve) => {
        console.log("\nREAL TCP SOCKET");
        console.log("=".repeat(72));

        const server = net.createServer((socket) => {
            socket.setEncoding("utf8");

            socket.on("data", (data) => {
                console.log("Server received:", JSON.stringify(data));

                socket.write("TCP response");
                socket.end();
            });

            socket.on("error", (error) => {
                console.log("Server socket error:", error.message);
            });
        });

        server.on("error", (error) => {
            console.log("TCP server error:", error.message);
            resolve();
        });

        server.listen(0, "127.0.0.1", () => {
            const address = server.address();

            const client = net.createConnection({
                host: "127.0.0.1",
                port: address.port,
            });

            client.setEncoding("utf8");

            client.on("connect", () => {
                client.write("Hello TCP");
            });

            client.on("data", (data) => {
                console.log("Client received:", JSON.stringify(data));
            });

            client.on("end", () => {
                client.destroy();
                server.close(() => resolve());
            });

            client.on("error", (error) => {
                console.log("TCP client error:", error.message);
                client.destroy();
                server.close(() => resolve());
            });
        });
    });
}

// ============================================================================
// 20. REAL UDP SOCKET DEMONSTRATION
// ============================================================================

function udpSocketDemo() {
    return new Promise((resolve) => {
        console.log("\nREAL UDP SOCKET");
        console.log("=".repeat(72));

        const receiver = dgram.createSocket("udp4");

        receiver.on("message", (message, remote) => {
            console.log(
                `Receiver got ${JSON.stringify(
                    message.toString()
                )} from ${remote.address}:${remote.port}`
            );

            receiver.close();
        });

        receiver.on("error", (error) => {
            console.log("UDP receiver error:", error.message);
            receiver.close();
            resolve();
        });

        receiver.on("close", resolve);

        receiver.bind(0, "127.0.0.1", () => {
            const receiverAddress = receiver.address();

            const sender = dgram.createSocket("udp4");

            sender.send(
                Buffer.from("Hello UDP"),
                receiverAddress.port,
                receiverAddress.address,
                (error) => {
                    if (error) {
                        console.log("UDP sender error:", error.message);
                    }

                    sender.close();
                }
            );
        });
    });
}

// ============================================================================
// 21. LOCAL INTERFACE INFORMATION
// ============================================================================

function interfaceDemo() {
    console.log("\nLOCAL NETWORK INTERFACES");
    console.log("=".repeat(72));

    const interfaces = os.networkInterfaces();

    for (const [name, addresses] of Object.entries(interfaces)) {
        console.log(`Interface: ${name}`);

        for (const address of addresses ?? []) {
            console.log(
                `  address=${address.address}, ` +
                `family=${address.family}, ` +
                `internal=${address.internal}`
            );
        }
    }
}

// ============================================================================
// 22. SECURITY
// ============================================================================

function securityDemo() {
    console.log("\nNETWORK SECURITY");
    console.log("=".repeat(72));

    const principles = [
        "TCP does not encrypt application data.",
        "TLS can protect application traffic carried over TCP.",
        "Network input is untrusted input.",
        "Authentication determines who a peer claims to be.",
        "Authorization determines what an authenticated identity may do.",
        "Timeouts prevent indefinitely blocked operations.",
        "Rate limiting helps control resource exhaustion.",
        "Input validation prevents malformed network data from reaching unsafe logic.",
        "Firewalls can restrict traffic by addresses, ports, and protocols.",
    ];

    for (const principle of principles) {
        console.log(`- ${principle}`);
    }
}

// ============================================================================
// 23. TROUBLESHOOTING
// ============================================================================

function troubleshootingDemo() {
    console.log("\nTROUBLESHOOTING BY LAYER");
    console.log("=".repeat(72));

    const checks = [
        [
            "Application",
            "Check service state, request syntax, authentication, and application logs.",
        ],
        [
            "Transport",
            "Check port selection, listener state, connection errors, and timeouts.",
        ],
        [
            "Internet",
            "Check IP addressing, routes, gateways, and packet reachability.",
        ],
        [
            "Network Access",
            "Check interface state, local link connectivity, ARP, Ethernet, or Wi-Fi.",
        ],
    ];

    for (const [layer, check] of checks) {
        console.log(`${layer.padEnd(18)} -> ${check}`);
    }
}

// ============================================================================
// 24. PERFORMANCE
// ============================================================================

function performanceDemo() {
    console.log("\nPERFORMANCE CONSIDERATIONS");
    console.log("=".repeat(72));

    const factors = [
        "Latency is the time required for communication.",
        "Bandwidth is the theoretical capacity of a link.",
        "Throughput is the achieved useful data rate.",
        "Packet loss can trigger retransmission and reduce throughput.",
        "TCP connection setup introduces overhead.",
        "Persistent connections can avoid repeated connection establishment.",
        "DNS lookup time contributes to application latency.",
        "TLS handshakes add computational and communication work.",
        "Buffer sizes affect memory usage and throughput behavior.",
        "Concurrency architecture determines how many clients can be served efficiently.",
    ];

    for (const factor of factors) {
        console.log(`- ${factor}`);
    }
}

// ============================================================================
// 25. END-TO-END CASE
// ============================================================================

function endToEndDemo() {
    console.log("\nEND-TO-END TCP/IP EXAMPLE");
    console.log("=".repeat(72));

    const data = {
        application: "GET /index.html HTTP/1.1",
        sourcePort: 53000,
        destinationPort: 443,
        sourceIp: "192.168.1.20",
        destinationIp: "203.0.113.50",
        sourceMac: "00:11:22:33:44:55",
        destinationMac: "AA:BB:CC:DD:EE:FF",
    };

    console.log("Application:");
    console.log(`  ${data.application}`);

    console.log("\nTransport:");
    console.log(
        `  TCP ${data.sourcePort} -> ${data.destinationPort}`
    );

    console.log("\nInternet:");
    console.log(
        `  IP ${data.sourceIp} -> ${data.destinationIp}`
    );

    console.log("\nNetwork access:");
    console.log(
        `  Ethernet ${data.sourceMac} -> ${data.destinationMac}`
    );

    console.log(
        "\nConceptual encapsulation: application data -> TCP segment -> IP packet -> frame"
    );
}

// ============================================================================
// 26. SELF-TESTS
// ============================================================================

function runTests() {
    console.log("\nSELF-TESTS");
    console.log("=".repeat(72));

    console.assert(parseIpv4("192.168.1.1") !== null);
    console.assert(parseIpv4("999.1.1.1") === null);
    console.assert(isPrivateIpv4("10.0.0.1"));
    console.assert(!isPrivateIpv4("8.8.8.8"));

    const subnet = cidrInfo("192.168.1.100", 24);

    console.assert(subnet.network === "192.168.1.0");
    console.assert(subnet.broadcast === "192.168.1.255");
    console.assert(subnet.totalAddresses === 256);

    const table = new RoutingTable([
        new Route("0.0.0.0", 0, "default"),
        new Route("10.0.0.0", 8, "A"),
        new Route("10.10.0.0", 16, "B"),
    ]);

    console.assert(table.lookup("10.10.20.1").nextHop === "B");
    console.assert(table.lookup("8.8.8.8").nextHop === "default");

    const message = Buffer.from("testing");
    const encoded = encodeLengthPrefixed(message);
    const decoded = decodeLengthPrefixed(encoded);

    console.assert(decoded.message.toString() === "testing");
    console.assert(decoded.consumed === encoded.length);

    console.log("All self-tests completed.");
}

// ============================================================================
// 27. MAIN
// ============================================================================

async function main() {
    printModel();
    applicationLayerDemo();
    await dnsDemo();
    portDemo();
    tcpHandshakeDemo();
    tcpReliabilityDemo();
    udpDemo();
    compareTcpUdp();
    ipv4Demo();
    subnetDemo();
    routingDemo();
    ipv6Demo();
    ttlDemo();
    arpDemo();
    ethernetDemo();
    encapsulationDemo();
    framingDemo();
    integrityDemo();
    interfaceDemo();
    securityDemo();
    troubleshootingDemo();
    performanceDemo();
    endToEndDemo();
    runTests();

    await tcpSocketDemo();
    await udpSocketDemo();

    console.log("\nPROGRAM COMPLETE");
}

main().catch((error) => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});
