/*
 * OSI Model: Comprehensive JavaScript Demonstration
 *
 * This file demonstrates the seven-layer OSI model through executable
 * JavaScript examples:
 *
 * 1. Physical
 * 2. Data Link
 * 3. Network
 * 4. Transport
 * 5. Session
 * 6. Presentation
 * 7. Application
 *
 * Runtime: Node.js 18+ recommended.
 *
 * No external npm packages are required.
 */

"use strict";

const crypto = require("crypto");


// ============================================================
// 1. OSI MODEL DEFINITIONS
// ============================================================

const OSI_LAYERS = Object.freeze([
    {
        number: 1,
        name: "Physical",
        pdu: "Bits",
        responsibility: "Transmits raw signals and bits.",
        examples: ["Copper", "Fiber", "Radio", "Physical Ethernet"],
    },
    {
        number: 2,
        name: "Data Link",
        pdu: "Frame",
        responsibility: "Provides local node-to-node delivery.",
        examples: ["Ethernet", "Wi-Fi", "VLAN", "ARP"],
    },
    {
        number: 3,
        name: "Network",
        pdu: "Packet",
        responsibility: "Provides logical addressing and routing.",
        examples: ["IPv4", "IPv6", "ICMP", "IPsec"],
    },
    {
        number: 4,
        name: "Transport",
        pdu: "Segment / Datagram",
        responsibility: "Provides process-to-process communication.",
        examples: ["TCP", "UDP", "SCTP", "QUIC"],
    },
    {
        number: 5,
        name: "Session",
        pdu: "Data",
        responsibility: "Manages logical communication sessions.",
        examples: ["RPC session concepts", "Session state"],
    },
    {
        number: 6,
        name: "Presentation",
        pdu: "Data",
        responsibility: "Handles representation and transformation.",
        examples: ["UTF-8", "JSON", "TLS", "Compression"],
    },
    {
        number: 7,
        name: "Application",
        pdu: "Data",
        responsibility: "Provides network services to applications.",
        examples: ["HTTP", "DNS", "SMTP", "SSH"],
    },
]);


function printOsiLayers() {
    console.log("\n" + "=".repeat(72));
    console.log("OSI MODEL");
    console.log("=".repeat(72));

    [...OSI_LAYERS].reverse().forEach((layer) => {
        console.log(
            `Layer ${layer.number}: ${layer.name.padEnd(13)} | ` +
            `${layer.responsibility}`
        );
    });
}


function printProtocolMap() {
    console.log("\n" + "=".repeat(72));
    console.log("PROTOCOL AND TECHNOLOGY ASSOCIATIONS");
    console.log("=".repeat(72));

    OSI_LAYERS.forEach((layer) => {
        console.log(
            `${layer.number}. ${layer.name.padEnd(13)}: ` +
            layer.examples.join(", ")
        );
    });
}


// ============================================================
// 2. MAC ADDRESS HANDLING
// ============================================================

function normalizeMac(mac) {
    const cleaned = mac
        .replace(/-/g, ":")
        .replace(/\./g, "")
        .toLowerCase();

    if (cleaned.includes(":")) {
        const parts = cleaned.split(":");

        if (
            parts.length !== 6 ||
            parts.some((part) => !/^[0-9a-f]{2}$/.test(part))
        ) {
            throw new Error(`Invalid MAC address: ${mac}`);
        }

        return parts.join(":");
    }

    if (!/^[0-9a-f]{12}$/.test(cleaned)) {
        throw new Error(`Invalid MAC address: ${mac}`);
    }

    return cleaned.match(/.{2}/g).join(":");
}


// ============================================================
// 3. DATA LINK LAYER
// ============================================================

class EthernetFrame {
    constructor(destinationMac, sourceMac, etherType, payload) {
        this.destinationMac = normalizeMac(destinationMac);
        this.sourceMac = normalizeMac(sourceMac);

        if (!Number.isInteger(etherType) || etherType < 0 || etherType > 0xffff) {
            throw new Error("EtherType must fit within 16 bits.");
        }

        if (!Buffer.isBuffer(payload)) {
            throw new TypeError("Ethernet payload must be a Buffer.");
        }

        this.etherType = etherType;
        this.payload = payload;
    }

    summary() {
        return (
            `Ethernet Frame: ${this.sourceMac} -> ${this.destinationMac}, ` +
            `EtherType=0x${this.etherType.toString(16).padStart(4, "0")}, ` +
            `payload=${this.payload.length} bytes`
        );
    }

    serializeWithoutFcs() {
        const destination = Buffer.from(this.destinationMac.replace(/:/g, ""), "hex");
        const source = Buffer.from(this.sourceMac.replace(/:/g, ""), "hex");
        const type = Buffer.alloc(2);

        type.writeUInt16BE(this.etherType, 0);

        return Buffer.concat([
            destination,
            source,
            type,
            this.payload,
        ]);
    }
}


// ============================================================
// 4. NETWORK LAYER
// ============================================================

function ipv4ToInteger(address) {
    const parts = address.split(".").map(Number);

    if (
        parts.length !== 4 ||
        parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)
    ) {
        throw new Error(`Invalid IPv4 address: ${address}`);
    }

    return (
        ((parts[0] << 24) >>> 0) |
        (parts[1] << 16) |
        (parts[2] << 8) |
        parts[3]
    ) >>> 0;
}


function integerToIpv4(value) {
    return [
        (value >>> 24) & 255,
        (value >>> 16) & 255,
        (value >>> 8) & 255,
        value & 255,
    ].join(".");
}


function prefixToMask(prefixLength) {
    if (!Number.isInteger(prefixLength) || prefixLength < 0 || prefixLength > 32) {
        throw new Error("Prefix length must be between 0 and 32.");
    }

    if (prefixLength === 0) {
        return 0;
    }

    return (0xffffffff << (32 - prefixLength)) >>> 0;
}


class IPv4Packet {
    constructor(
        sourceIp,
        destinationIp,
        protocol,
        payload,
        ttl = 64,
        identification = 1
    ) {
        ipv4ToInteger(sourceIp);
        ipv4ToInteger(destinationIp);

        if (!Number.isInteger(protocol) || protocol < 0 || protocol > 255) {
            throw new Error("Protocol must fit in 8 bits.");
        }

        if (!Number.isInteger(ttl) || ttl < 1 || ttl > 255) {
            throw new Error("TTL must be between 1 and 255.");
        }

        this.sourceIp = sourceIp;
        this.destinationIp = destinationIp;
        this.protocol = protocol;
        this.payload = Buffer.from(payload);
        this.ttl = ttl;
        this.identification = identification;
    }

    decrementTtl() {
        if (this.ttl <= 1) {
            throw new Error("TTL expired.");
        }

        this.ttl -= 1;
    }

    summary() {
        return (
            `IPv4 Packet: ${this.sourceIp} -> ${this.destinationIp}, ` +
            `protocol=${this.protocol}, TTL=${this.ttl}, ` +
            `payload=${this.payload.length} bytes`
        );
    }
}


// ============================================================
// 5. TRANSPORT LAYER: TCP
// ============================================================

const TCP_FLAGS = Object.freeze({
    FIN: 0x001,
    SYN: 0x002,
    RST: 0x004,
    PSH: 0x008,
    ACK: 0x010,
});


class TcpSegment {
    constructor(
        sourcePort,
        destinationPort,
        sequenceNumber,
        acknowledgmentNumber,
        flags,
        payload = Buffer.alloc(0)
    ) {
        this.validatePort(sourcePort);
        this.validatePort(destinationPort);

        if (sequenceNumber < 0 || acknowledgmentNumber < 0) {
            throw new Error("Sequence and acknowledgment numbers cannot be negative.");
        }

        this.sourcePort = sourcePort;
        this.destinationPort = destinationPort;
        this.sequenceNumber = sequenceNumber;
        this.acknowledgmentNumber = acknowledgmentNumber;
        this.flags = flags;
        this.payload = Buffer.from(payload);
    }

    validatePort(port) {
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
            throw new Error(`Invalid port: ${port}`);
        }
    }

    flagNames() {
        return Object.entries(TCP_FLAGS)
            .filter(([, value]) => (this.flags & value) !== 0)
            .map(([name]) => name);
    }

    summary() {
        const flags = this.flagNames().join(",") || "NONE";

        return (
            `TCP ${this.sourcePort} -> ${this.destinationPort}, ` +
            `seq=${this.sequenceNumber}, ` +
            `ack=${this.acknowledgmentNumber}, ` +
            `flags=${flags}, payload=${this.payload.length} bytes`
        );
    }
}


// ============================================================
// 6. UDP
// ============================================================

class UdpDatagram {
    constructor(sourcePort, destinationPort, payload) {
        this.validatePort(sourcePort);
        this.validatePort(destinationPort);

        this.sourcePort = sourcePort;
        this.destinationPort = destinationPort;
        this.payload = Buffer.from(payload);
    }

    validatePort(port) {
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
            throw new Error(`Invalid UDP port: ${port}`);
        }
    }

    get length() {
        return 8 + this.payload.length;
    }

    summary() {
        return (
            `UDP ${this.sourcePort} -> ${this.destinationPort}, ` +
            `length=${this.length} bytes`
        );
    }
}


// ============================================================
// 7. PORT CLASSIFICATION
// ============================================================

const WELL_KNOWN_PORTS = new Map([
    [20, "FTP Data"],
    [21, "FTP Control"],
    [22, "SSH"],
    [23, "Telnet"],
    [25, "SMTP"],
    [53, "DNS"],
    [67, "DHCP Server"],
    [68, "DHCP Client"],
    [80, "HTTP"],
    [110, "POP3"],
    [123, "NTP"],
    [143, "IMAP"],
    [161, "SNMP"],
    [443, "HTTPS"],
    [587, "SMTP Submission"],
]);


function classifyPort(port) {
    if (!Number.isInteger(port) || port < 0 || port > 65535) {
        throw new Error("Port must be between 0 and 65535.");
    }

    if (WELL_KNOWN_PORTS.has(port)) {
        return WELL_KNOWN_PORTS.get(port);
    }

    if (port >= 49152) {
        return "Dynamic / Ephemeral Port";
    }

    if (port >= 1024) {
        return "Registered Port";
    }

    return "Reserved / Special Port";
}


// ============================================================
// 8. APPLICATION AND PRESENTATION
// ============================================================

function buildHttpRequest(host, path = "/") {
    if (!host || /\s/.test(host)) {
        throw new Error("Host must be non-empty and contain no spaces.");
    }

    if (!path.startsWith("/")) {
        throw new Error("HTTP path must begin with '/'.");
    }

    return [
        `GET ${path} HTTP/1.1`,
        `Host: ${host}`,
        "Accept: */*",
        "Connection: close",
        "",
        "",
    ].join("\r\n");
}


function demonstrateEncoding() {
    console.log("\n" + "=".repeat(72));
    console.log("PRESENTATION LAYER");
    console.log("=".repeat(72));

    const originalText = "OSI networking: café";
    const encoded = Buffer.from(originalText, "utf8");
    const decoded = encoded.toString("utf8");

    console.log("Original:", originalText);
    console.log("UTF-8 bytes:", encoded);
    console.log("Decoded:", decoded);

    const object = {
        protocol: "HTTP",
        status: 200,
        message: "OK",
    };

    const jsonText = JSON.stringify(object);
    const restoredObject = JSON.parse(jsonText);

    console.log("JSON:", jsonText);
    console.log("Restored:", restoredObject);
}


function demonstrateHashing() {
    const data = Buffer.from("network packet");

    const digest = crypto
        .createHash("sha256")
        .update(data)
        .digest("hex");

    console.log("\nSHA-256:");
    console.log(digest);
}


// ============================================================
// 9. ROUTING
// ============================================================

class Route {
    constructor(network, prefixLength, nextHop, interfaceName, metric = 1) {
        this.network = ipv4ToInteger(network);
        this.prefixLength = prefixLength;
        this.nextHop = nextHop;
        this.interfaceName = interfaceName;
        this.metric = metric;
        this.mask = prefixToMask(prefixLength);
    }

    contains(destination) {
        const destinationInteger = ipv4ToInteger(destination);
        return (destinationInteger & this.mask) === (this.network & this.mask);
    }

    networkAddress() {
        return integerToIpv4(this.network & this.mask);
    }
}


class RoutingTable {
    constructor() {
        this.routes = [];
    }

    addRoute(route) {
        this.routes.push(route);
    }

    lookup(destination) {
        const matchingRoutes = this.routes.filter((route) =>
            route.contains(destination)
        );

        if (matchingRoutes.length === 0) {
            return null;
        }

        return matchingRoutes.sort((a, b) => {
            if (b.prefixLength !== a.prefixLength) {
                return b.prefixLength - a.prefixLength;
            }

            return a.metric - b.metric;
        })[0];
    }

    display() {
        this.routes.forEach((route) => {
            console.log(
                `${route.networkAddress()}/${route.prefixLength} -> ` +
                `${route.nextHop} ${route.interfaceName} ` +
                `metric=${route.metric}`
            );
        });
    }
}


function demonstrateRouting() {
    console.log("\n" + "=".repeat(72));
    console.log("NETWORK LAYER: ROUTING");
    console.log("=".repeat(72));

    const table = new RoutingTable();

    table.addRoute(
        new Route("192.168.1.0", 24, "direct", "eth0")
    );

    table.addRoute(
        new Route("10.0.0.0", 8, "10.0.0.1", "eth1", 20)
    );

    table.addRoute(
        new Route("10.20.0.0", 16, "10.20.0.1", "eth2", 10)
    );

    table.addRoute(
        new Route("0.0.0.0", 0, "192.168.1.1", "eth0", 100)
    );

    table.display();

    [
        "192.168.1.50",
        "10.20.5.10",
        "10.90.1.1",
        "8.8.8.8",
    ].forEach((destination) => {
        const route = table.lookup(destination);

        console.log(
            `${destination} -> ` +
            (route
                ? `${route.networkAddress()}/${route.prefixLength}`
                : "No route")
        );
    });
}


// ============================================================
// 10. TCP STATE MACHINE
// ============================================================

const TCP_STATES = Object.freeze({
    CLOSED: "CLOSED",
    LISTEN: "LISTEN",
    SYN_SENT: "SYN-SENT",
    SYN_RECEIVED: "SYN-RECEIVED",
    ESTABLISHED: "ESTABLISHED",
    FIN_WAIT: "FIN-WAIT",
});


class TcpConnection {
    constructor() {
        this.state = TCP_STATES.CLOSED;
    }

    listen() {
        if (this.state !== TCP_STATES.CLOSED) {
            throw new Error("LISTEN requires CLOSED state.");
        }

        this.state = TCP_STATES.LISTEN;
    }

    activeOpen() {
        if (this.state !== TCP_STATES.CLOSED) {
            throw new Error("Active open requires CLOSED state.");
        }

        this.state = TCP_STATES.SYN_SENT;
    }

    receiveSyn() {
        if (this.state !== TCP_STATES.LISTEN) {
            throw new Error("SYN is invalid in current state.");
        }

        this.state = TCP_STATES.SYN_RECEIVED;
    }

    receiveSynAck() {
        if (this.state !== TCP_STATES.SYN_SENT) {
            throw new Error("SYN-ACK is invalid in current state.");
        }

        this.state = TCP_STATES.ESTABLISHED;
    }

    receiveAck() {
        if (this.state !== TCP_STATES.SYN_RECEIVED) {
            throw new Error("ACK is invalid in current state.");
        }

        this.state = TCP_STATES.ESTABLISHED;
    }

    toString() {
        return `TCP state=${this.state}`;
    }
}


function demonstrateTcpHandshake() {
    console.log("\n" + "=".repeat(72));
    console.log("TCP THREE-WAY HANDSHAKE");
    console.log("=".repeat(72));

    const client = new TcpConnection();
    const server = new TcpConnection();

    server.listen();
    console.log("Server:", server.toString());

    client.activeOpen();
    console.log("Client sends SYN:", client.toString());

    server.receiveSyn();
    console.log("Server sends SYN-ACK:", server.toString());

    client.receiveSynAck();
    console.log("Client sends ACK:", client.toString());

    server.receiveAck();
    console.log("Server:", server.toString());
}


// ============================================================
// 11. ASYNCHRONOUS SESSION SIMULATION
// ============================================================

function wait(milliseconds) {
    return new Promise((resolve) => {
        setTimeout(resolve, milliseconds);
    });
}


async function simulateSession() {
    console.log("\n" + "=".repeat(72));
    console.log("SESSION-LAYER ASYNCHRONOUS SIMULATION");
    console.log("=".repeat(72));

    console.log("Session: starting");
    await wait(20);

    console.log("Session: authenticated");
    await wait(20);

    console.log("Session: application data exchanged");
    await wait(20);

    console.log("Session: closed");
}


// ============================================================
// 12. ENCAPSULATION
// ============================================================

function simulateEncapsulation() {
    console.log("\n" + "=".repeat(72));
    console.log("ENCAPSULATION");
    console.log("=".repeat(72));

    const applicationData = Buffer.from(
        buildHttpRequest("example.com", "/osi"),
        "utf8"
    );

    const tcp = new TcpSegment(
        52000,
        443,
        1000,
        5000,
        TCP_FLAGS.PSH | TCP_FLAGS.ACK,
        applicationData
    );

    const ipPacket = new IPv4Packet(
        "192.168.1.10",
        "93.184.216.34",
        6,
        applicationData
    );

    const ethernet = new EthernetFrame(
        "00:11:22:33:44:55",
        "AA:BB:CC:DD:EE:FF",
        0x0800,
        Buffer.from(ipPacket.payload)
    );

    console.log(`Layer 7: ${applicationData.length} bytes`);
    console.log(`Layer 4: ${tcp.summary()}`);
    console.log(`Layer 3: ${ipPacket.summary()}`);
    console.log(`Layer 2: ${ethernet.summary()}`);
    console.log("Layer 1: bits/signals transmitted");
}


// ============================================================
// 13. MTU
// ============================================================

function demonstrateMtu() {
    console.log("\n" + "=".repeat(72));
    console.log("MTU CALCULATION");
    console.log("=".repeat(72));

    const mtu = 1500;
    const ipv4Header = 20;
    const tcpHeader = 20;

    const maximumTcpPayload = mtu - ipv4Header - tcpHeader;

    console.log(`MTU: ${mtu}`);
    console.log(`IPv4 header: ${ipv4Header}`);
    console.log(`TCP header: ${tcpHeader}`);
    console.log(`Approximate TCP payload: ${maximumTcpPayload}`);
}


// ============================================================
// 14. SECURITY
// ============================================================

const SECURITY_CONTROLS = {
    1: ["Physical access controls"],
    2: ["802.1X", "VLAN segmentation", "Port security"],
    3: ["ACLs", "IPsec", "Anti-spoofing"],
    4: ["Firewalls", "Port filtering", "Rate limiting"],
    5: ["Session timeout", "Session invalidation"],
    6: ["TLS", "Certificate validation"],
    7: ["Authentication", "Authorization", "Input validation"],
};


function demonstrateSecurity() {
    console.log("\n" + "=".repeat(72));
    console.log("SECURITY BY OSI LAYER");
    console.log("=".repeat(72));

    Object.entries(SECURITY_CONTROLS).forEach(([layer, controls]) => {
        console.log(
            `Layer ${layer} (${OSI_LAYERS[layer - 1].name}): ` +
            controls.join(", ")
        );
    });
}


// ============================================================
// 15. TROUBLESHOOTING
// ============================================================

const TROUBLESHOOTING = [
    {
        symptom: "No physical link",
        layers: [1],
        examples: ["Cable failure", "Interface failure", "Power issue"],
    },
    {
        symptom: "Wrong VLAN or MAC behavior",
        layers: [2],
        examples: ["VLAN mismatch", "Switch configuration", "Layer-2 loop"],
    },
    {
        symptom: "Cannot reach remote network",
        layers: [3],
        examples: ["Wrong IP", "Wrong gateway", "Routing failure"],
    },
    {
        symptom: "Server is reachable but port is unavailable",
        layers: [4],
        examples: ["Firewall", "Closed port", "TCP state problem"],
    },
    {
        symptom: "Encrypted connection negotiation fails",
        layers: [6],
        examples: ["Certificate", "Protocol", "Cipher mismatch"],
    },
    {
        symptom: "DNS resolution fails",
        layers: [7],
        examples: ["Resolver", "DNS configuration", "Application configuration"],
    },
];


function demonstrateTroubleshooting() {
    console.log("\n" + "=".repeat(72));
    console.log("OSI TROUBLESHOOTING");
    console.log("=".repeat(72));

    TROUBLESHOOTING.forEach((item) => {
        const layers = item.layers
            .map((number) => `${number} (${OSI_LAYERS[number - 1].name})`)
            .join(", ");

        console.log(`\nSymptom: ${item.symptom}`);
        console.log(`Likely layers: ${layers}`);
        console.log(`Examples: ${item.examples.join(", ")}`);
    });
}


// ============================================================
// 16. PACKET RECEIVE PIPELINE
// ============================================================

class PacketPipeline {
    constructor() {
        this.events = [];
    }

    physicalReceive(bitCount) {
        this.events.push(
            `Layer 1 received approximately ${bitCount} bits.`
        );
    }

    dataLinkReceive(frame) {
        this.events.push(
            `Layer 2 accepted frame from ${frame.sourceMac}.`
        );

        return true;
    }

    networkReceive(packet) {
        this.events.push(
            `Layer 3 processed packet for ${packet.destinationIp}.`
        );

        return true;
    }

    transportReceive(segment) {
        this.events.push(
            `Layer 4 delivered TCP data to port ` +
            `${segment.destinationPort}.`
        );

        return true;
    }

    sessionProcess() {
        this.events.push(
            "Layer 5 verified session context."
        );
    }

    presentationDecode(buffer) {
        const text = buffer.toString("utf8");

        this.events.push(
            "Layer 6 decoded UTF-8 application data."
        );

        return text;
    }

    applicationReceive(text) {
        this.events.push(
            `Layer 7 received: ${text.split("\r\n")[0]}`
        );
    }

    display() {
        this.events.forEach((event, index) => {
            console.log(`${index + 1}. ${event}`);
        });
    }
}


function demonstratePacketPipeline() {
    console.log("\n" + "=".repeat(72));
    console.log("PACKET PROCESSING PIPELINE");
    console.log("=".repeat(72));

    const applicationData = Buffer.from(
        buildHttpRequest("example.com", "/network"),
        "utf8"
    );

    const tcp = new TcpSegment(
        53000,
        443,
        1,
        1,
        TCP_FLAGS.PSH | TCP_FLAGS.ACK,
        applicationData
    );

    const packet = new IPv4Packet(
        "192.168.1.20",
        "93.184.216.34",
        6,
        applicationData
    );

    const frame = new EthernetFrame(
        "00:11:22:33:44:55",
        "AA:BB:CC:DD:EE:FF",
        0x0800,
        packet.payload
    );

    const pipeline = new PacketPipeline();

    pipeline.physicalReceive(frame.payload.length * 8);
    pipeline.dataLinkReceive(frame);
    pipeline.networkReceive(packet);
    pipeline.transportReceive(tcp);
    pipeline.sessionProcess();

    const decoded = pipeline.presentationDecode(applicationData);
    pipeline.applicationReceive(decoded);

    pipeline.display();
}


// ============================================================
// 17. ERROR HANDLING AND EDGE CASES
// ============================================================

function demonstrateEdgeCases() {
    console.log("\n" + "=".repeat(72));
    console.log("VALIDATION AND EDGE CASES");
    console.log("=".repeat(72));

    const tests = [
        [
            "Invalid MAC",
            () => normalizeMac("GG:11:22:33:44:55"),
        ],
        [
            "Invalid IP",
            () => ipv4ToInteger("300.1.1.1"),
        ],
        [
            "Invalid port",
            () => classifyPort(70000),
        ],
        [
            "Invalid HTTP path",
            () => buildHttpRequest("example.com", "wrong"),
        ],
    ];

    tests.forEach(([name, operation]) => {
        try {
            operation();
            console.log(`${name}: unexpectedly accepted`);
        } catch (error) {
            console.log(`${name}: correctly rejected -> ${error.message}`);
        }
    });
}


// ============================================================
// 18. TCP VS UDP
// ============================================================

function compareTcpUdp() {
    console.log("\n" + "=".repeat(72));
    console.log("TCP VS UDP");
    console.log("=".repeat(72));

    const rows = [
        ["Connection", "Connection-oriented", "Connectionless"],
        ["Reliability", "Built-in reliability", "No inherent reliability"],
        ["Ordering", "Ordered byte stream", "No ordering guarantee"],
        ["Retransmission", "Yes", "Application-dependent"],
        ["Flow control", "Yes", "Not TCP-style"],
        ["Congestion control", "Yes", "Not inherent"],
        ["Overhead", "Higher", "Lower"],
    ];

    rows.forEach(([feature, tcp, udp]) => {
        console.log(
            `${feature.padEnd(18)} | TCP: ${tcp.padEnd(28)} | UDP: ${udp}`
        );
    });
}


// ============================================================
// 19. OSI VS TCP/IP
// ============================================================

function compareOsiAndTcpIp() {
    console.log("\n" + "=".repeat(72));
    console.log("OSI VS TCP/IP");
    console.log("=".repeat(72));

    console.log(
        "OSI: seven-layer reference model."
    );

    console.log(
        "TCP/IP: practical protocol architecture used by the Internet."
    );

    console.log(
        "OSI Application + Presentation + Session are commonly mapped " +
        "into the TCP/IP Application layer."
    );

    console.log(
        "OSI Network maps broadly to the TCP/IP Internet layer."
    );

    console.log(
        "OSI Data Link + Physical map broadly to the TCP/IP Link layer."
    );
}


// ============================================================
// 20. SELF-TESTS
// ============================================================

function runTests() {
    console.log("\n" + "=".repeat(72));
    console.log("SELF-TESTS");
    console.log("=".repeat(72));

    console.assert(
        normalizeMac("AA-BB-CC-DD-EE-FF") === "aa:bb:cc:dd:ee:ff",
        "MAC normalization failed"
    );

    console.assert(
        ipv4ToInteger("192.168.1.1") === 3232235777,
        "IPv4 conversion failed"
    );

    console.assert(
        integerToIpv4(3232235777) === "192.168.1.1",
        "IPv4 reverse conversion failed"
    );

    console.assert(
        classifyPort(443) === "HTTPS",
        "Port classification failed"
    );

    const routeTable = new RoutingTable();

    routeTable.addRoute(
        new Route("10.0.0.0", 8, "10.0.0.1", "eth0")
    );

    routeTable.addRoute(
        new Route("10.10.0.0", 16, "10.10.0.1", "eth1")
    );

    const selected = routeTable.lookup("10.10.5.1");

    console.assert(
        selected.prefixLength === 16,
        "Longest-prefix route selection failed"
    );

    const packet = new IPv4Packet(
        "192.168.1.10",
        "192.168.1.20",
        6,
        Buffer.from("hello")
    );

    console.assert(
        packet.payload.toString() === "hello",
        "Packet payload failed"
    );

    console.log("All self-tests passed.");
}


// ============================================================
// 21. MAIN
// ============================================================

async function main() {
    console.log("=".repeat(72));
    console.log("OSI MODEL: JAVASCRIPT STUDY AND SIMULATION");
    console.log("=".repeat(72));

    printOsiLayers();
    printProtocolMap();

    console.log("\nPDU progression:");
    console.log("Application -> Transport -> Network -> Data Link -> Physical");

    console.log("\nPort examples:");
    [22, 53, 80, 443, 50000].forEach((port) => {
        console.log(`${port}: ${classifyPort(port)}`);
    });

    demonstrateEncoding();
    demonstrateHashing();

    console.log("\nApplication example:");
    console.log(buildHttpRequest("example.com", "/osi"));

    simulateEncapsulation();
    demonstrateRouting();
    demonstrateTcpHandshake();
    compareTcpUdp();
    demonstrateMtu();
    demonstrateSecurity();
    demonstrateTroubleshooting();
    demonstratePacketPipeline();
    demonstrateEdgeCases();
    compareOsiAndTcpIp();

    await simulateSession();

    runTests();

    console.log("\n" + "=".repeat(72));
    console.log("KEY OSI STUDY CHECKPOINTS");
    console.log("=".repeat(72));

    [
        "Layer responsibilities",
        "PDU names",
        "MAC, IP, and port addressing",
        "Encapsulation and decapsulation",
        "TCP and UDP",
        "Routing and longest-prefix matching",
        "MTU and packet sizing",
        "Session and presentation concepts",
        "Layer-oriented troubleshooting",
        "Cross-layer security",
        "OSI versus TCP/IP",
    ].forEach((item) => console.log(`[x] ${item}`));
}


main().catch((error) => {
    console.error("Program failed:", error.message);
    process.exitCode = 1;
});
