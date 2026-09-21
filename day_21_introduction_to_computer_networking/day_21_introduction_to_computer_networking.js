"use strict";

/*
 * Introduction to Computer Networking
 *
 * This file provides executable demonstrations of networking concepts using
 * standard JavaScript and Node.js APIs. It moves from simple models of
 * packets and protocols to sockets, HTTP, DNS, routing, validation,
 * asynchronous communication, and a small network service.
 *
 * Run with:
 *     node networking.js
 *
 * No external npm packages are required.
 */

const net = require("net");
const dns = require("dns").promises;
const crypto = require("crypto");
const { URL } = require("url");

// ============================================================================
// 1. NETWORKING FOUNDATIONS
// ============================================================================

function showFoundations() {
    console.log("\n" + "=".repeat(78));
    console.log("1. NETWORKING FOUNDATIONS");
    console.log("=".repeat(78));

    const concepts = {
        network: "Connected devices that exchange data.",
        client: "A program that requests a service.",
        server: "A program that provides a service.",
        protocol: "Rules defining how communication occurs.",
        packet: "A network-layer unit containing data and addressing information.",
        router: "A device that forwards packets between networks.",
        switch: "A local-network device that forwards frames.",
        ipAddress: "A logical network-layer address.",
        port: "A transport-layer identifier for an application endpoint.",
        latency: "The time required for communication to travel through a path.",
        bandwidth: "The capacity of a communication link.",
        throughput: "The actual useful transfer rate achieved.",
    };

    for (const [name, definition] of Object.entries(concepts)) {
        console.log(`${name.padEnd(12)} -> ${definition}`);
    }
}

// ============================================================================
// 2. ENCAPSULATION
// ============================================================================

function createApplicationMessage() {
    return {
        method: "GET",
        path: "/index.html",
        headers: {
            Host: "example.test",
            Accept: "text/html",
        },
    };
}

function encapsulateMessage(applicationMessage) {
    // Each layer adds information required by its own responsibilities.
    const transportSegment = {
        protocol: "TCP",
        sourcePort: 51500,
        destinationPort: 443,
        payload: applicationMessage,
    };

    const ipPacket = {
        protocol: "IPv4",
        sourceIp: "192.168.1.10",
        destinationIp: "93.184.216.34",
        payload: transportSegment,
    };

    return {
        protocol: "Ethernet",
        sourceMac: "AA:BB:CC:DD:EE:01",
        destinationMac: "AA:BB:CC:DD:EE:FE",
        payload: ipPacket,
    };
}

function demonstrateEncapsulation() {
    console.log("\n" + "=".repeat(78));
    console.log("2. ENCAPSULATION");
    console.log("=".repeat(78));

    const applicationMessage = createApplicationMessage();
    const frame = encapsulateMessage(applicationMessage);

    console.log("Application:");
    console.dir(applicationMessage, { depth: null });

    console.log("\nTransport:");
    console.dir(frame.payload.payload, { depth: null });

    console.log("\nNetwork:");
    console.dir(frame.payload, { depth: null });

    console.log("\nData link:");
    console.dir(frame, { depth: null });
}

// ============================================================================
// 3. IPV4 AND SUBNET CALCULATIONS
// ============================================================================

function ipv4ToInteger(address) {
    const parts = address.split(".").map(Number);

    if (
        parts.length !== 4 ||
        parts.some(
            (part) => !Number.isInteger(part) || part < 0 || part > 255
        )
    ) {
        throw new Error(`Invalid IPv4 address: ${address}`);
    }

    return (
        ((parts[0] << 24) |
            (parts[1] << 16) |
            (parts[2] << 8) |
            parts[3]) >>>
        0
    );
}

function integerToIpv4(value) {
    if (!Number.isInteger(value) || value < 0 || value > 0xffffffff) {
        throw new Error("Invalid IPv4 integer");
    }

    return [
        (value >>> 24) & 255,
        (value >>> 16) & 255,
        (value >>> 8) & 255,
        value & 255,
    ].join(".");
}

function prefixToMask(prefixLength) {
    if (
        !Number.isInteger(prefixLength) ||
        prefixLength < 0 ||
        prefixLength > 32
    ) {
        throw new Error("Prefix length must be between 0 and 32");
    }

    if (prefixLength === 0) {
        return 0;
    }

    return (0xffffffff << (32 - prefixLength)) >>> 0;
}

function calculateSubnet(address, prefixLength) {
    const addressInteger = ipv4ToInteger(address);
    const mask = prefixToMask(prefixLength);
    const network = (addressInteger & mask) >>> 0;
    const broadcast = (network | (~mask >>> 0)) >>> 0;

    return {
        address,
        prefixLength,
        network: integerToIpv4(network),
        broadcast: integerToIpv4(broadcast),
        totalAddresses: 2 ** (32 - prefixLength),
    };
}

function demonstrateIPv4() {
    console.log("\n" + "=".repeat(78));
    console.log("3. IPV4 ADDRESSING AND SUBNETTING");
    console.log("=".repeat(78));

    for (const [address, prefix] of [
        ["192.168.1.25", 24],
        ["10.20.30.40", 16],
        ["172.16.25.5", 20],
    ]) {
        console.log(calculateSubnet(address, prefix));
    }

    console.log("\nIPv4 integer representation:");
    const integer = ipv4ToInteger("192.168.1.10");
    console.log(integer);
    console.log(integerToIpv4(integer));
}

// ============================================================================
// 4. PACKETS
// ============================================================================

class Packet {
    constructor(id, source, destination, payload) {
        if (!Number.isInteger(id) || id <= 0) {
            throw new Error("Packet ID must be a positive integer");
        }

        if (!source || !destination) {
            throw new Error("Packet endpoints are required");
        }

        this.id = id;
        this.source = source;
        this.destination = destination;
        this.payload = payload;
        this.hops = [];
        this.createdAt = Date.now();
    }

    addHop(routerName) {
        this.hops.push(routerName);
    }

    summary() {
        return {
            id: this.id,
            source: this.source,
            destination: this.destination,
            payloadSize: Buffer.byteLength(this.payload, "utf8"),
            hops: [...this.hops],
        };
    }
}

function demonstratePackets() {
    console.log("\n" + "=".repeat(78));
    console.log("4. PACKETS");
    console.log("=".repeat(78));

    const packet = new Packet(
        1001,
        "192.168.1.10",
        "10.20.30.40",
        "Hello from the client"
    );

    packet.addHop("R1");
    packet.addHop("R5");

    console.dir(packet.summary(), { depth: null });
}

// ============================================================================
// 5. ROUTING
// ============================================================================

class RoutingTable {
    constructor() {
        this.routes = [];
    }

    addRoute(network, prefixLength, nextHop, metric = 1) {
        this.routes.push({
            network,
            prefixLength,
            nextHop,
            metric,
        });
    }

    lookup(destination) {
        const destinationInteger = ipv4ToInteger(destination);

        const matchingRoutes = this.routes.filter((route) => {
            const mask = prefixToMask(route.prefixLength);
            const networkInteger = ipv4ToInteger(route.network);
            return (destinationInteger & mask) >>> 0 ===
                (networkInteger & mask) >>> 0;
        });

        if (matchingRoutes.length === 0) {
            return null;
        }

        // Longest prefix match is the central rule used by ordinary IP routing.
        matchingRoutes.sort((a, b) => {
            if (b.prefixLength !== a.prefixLength) {
                return b.prefixLength - a.prefixLength;
            }
            return a.metric - b.metric;
        });

        return matchingRoutes[0];
    }
}

function demonstrateRouting() {
    console.log("\n" + "=".repeat(78));
    console.log("5. ROUTING");
    console.log("=".repeat(78));

    const table = new RoutingTable();

    table.addRoute("0.0.0.0", 0, "ISP", 100);
    table.addRoute("10.0.0.0", 8, "R2", 20);
    table.addRoute("10.20.0.0", 16, "R3", 10);
    table.addRoute("10.20.30.0", 24, "R4", 5);

    for (const destination of [
        "8.8.8.8",
        "10.40.1.1",
        "10.20.40.2",
        "10.20.30.100",
    ]) {
        console.log(destination, "->", table.lookup(destination));
    }
}

// ============================================================================
// 6. SWITCHING
// ============================================================================

class LearningSwitch {
    constructor() {
        this.macTable = new Map();
    }

    receive(sourceMac, destinationMac, ingressPort) {
        // A switch learns the source location from every received frame.
        this.macTable.set(sourceMac, ingressPort);

        if (this.macTable.has(destinationMac)) {
            return {
                action: "forward",
                port: this.macTable.get(destinationMac),
            };
        }

        return {
            action: "flood",
            port: null,
        };
    }

    table() {
        return Object.fromEntries(this.macTable.entries());
    }
}

function demonstrateSwitching() {
    console.log("\n" + "=".repeat(78));
    console.log("6. ETHERNET SWITCHING");
    console.log("=".repeat(78));

    const switchDevice = new LearningSwitch();

    const events = [
        ["AA:AA:AA:AA:AA:01", "BB:BB:BB:BB:BB:02", "port1"],
        ["BB:BB:BB:BB:BB:02", "AA:AA:AA:AA:AA:01", "port2"],
        ["AA:AA:AA:AA:AA:01", "BB:BB:BB:BB:BB:02", "port1"],
    ];

    for (const [source, destination, port] of events) {
        console.log(
            `${source} -> ${destination}`,
            switchDevice.receive(source, destination, port)
        );
    }

    console.log("Learned MAC table:", switchDevice.table());
}

// ============================================================================
// 7. TCP AND UDP
// ============================================================================

class ReliableMessageChannel {
    constructor() {
        this.nextSequence = 1;
        this.pending = new Map();
    }

    send(payload) {
        const message = {
            sequence: this.nextSequence++,
            payload,
            acknowledged: false,
        };

        this.pending.set(message.sequence, message);
        return message;
    }

    acknowledge(sequence) {
        const message = this.pending.get(sequence);

        if (!message) {
            return false;
        }

        message.acknowledged = true;
        this.pending.delete(sequence);
        return true;
    }

    pendingMessages() {
        return [...this.pending.values()];
    }
}

function demonstrateTransportProtocols() {
    console.log("\n" + "=".repeat(78));
    console.log("7. TCP AND UDP CONCEPTS");
    console.log("=".repeat(78));

    console.log("TCP: connection-oriented, reliable byte stream.");
    console.log("UDP: connectionless datagrams without built-in delivery guarantees.");

    const channel = new ReliableMessageChannel();

    const first = channel.send("first");
    const second = channel.send("second");

    channel.acknowledge(first.sequence);

    console.log("Acknowledged:", first);
    console.log("Still pending:", channel.pendingMessages());

    console.log(
        "An application can use sequence numbers and acknowledgements to model reliability."
    );
}

// ============================================================================
// 8. HTTP MESSAGE CONSTRUCTION
// ============================================================================

function createHttpRequest(method, path, host, body = "") {
    if (!method || !path || !host) {
        throw new Error("HTTP method, path, and host are required");
    }

    return {
        method,
        path,
        version: "HTTP/1.1",
        headers: {
            Host: host,
            "User-Agent": "NetworkingStudyClient/1.0",
            Accept: "application/json",
            ...(body ? { "Content-Length": Buffer.byteLength(body) } : {}),
        },
        body,
    };
}

function serializeHttpRequest(request) {
    const requestLine =
        `${request.method} ${request.path} ${request.version}`;

    const headers = Object.entries(request.headers)
        .map(([name, value]) => `${name}: ${value}`)
        .join("\r\n");

    return `${requestLine}\r\n${headers}\r\n\r\n${request.body}`;
}

function demonstrateHttp() {
    console.log("\n" + "=".repeat(78));
    console.log("8. HTTP");
    console.log("=".repeat(78));

    const request = createHttpRequest(
        "GET",
        "/api/users/42",
        "api.example.test"
    );

    console.log(serializeHttpRequest(request));

    console.log("\nHTTP status examples:");
    console.log("200 -> successful request");
    console.log("301/302 -> redirection");
    console.log("400 -> client-side request problem");
    console.log("401/403 -> authentication/authorization problem");
    console.log("404 -> resource not found");
    console.log("500 -> server-side failure");
}

// ============================================================================
// 9. DNS
// ============================================================================

async function demonstrateDns() {
    console.log("\n" + "=".repeat(78));
    console.log("9. DNS");
    console.log("=".repeat(78));

    for (const hostname of ["localhost", "example.com"]) {
        try {
            const addresses = await dns.lookup(hostname, {
                all: true,
            });

            console.log(hostname, "->", addresses);
        } catch (error) {
            console.log(
                hostname,
                "-> DNS lookup failed:",
                error.code || error.message
            );
        }
    }
}

// ============================================================================
// 10. SOCKET CLIENT-SERVER COMMUNICATION
// ============================================================================

function startLocalTcpServer() {
    return new Promise((resolve, reject) => {
        const server = net.createServer((socket) => {
            socket.setEncoding("utf8");

            socket.on("data", (data) => {
                if (data.trim() === "PING") {
                    socket.write("PONG");
                } else {
                    socket.write("ERROR");
                }
            });

            socket.on("error", () => {
                // The server intentionally keeps connection errors local.
            });
        });

        server.once("error", reject);

        server.listen(0, "127.0.0.1", () => {
            resolve(server);
        });
    });
}

function connectToServer(port) {
    return new Promise((resolve, reject) => {
        const socket = net.createConnection(
            {
                host: "127.0.0.1",
                port,
            },
            () => {
                socket.write("PING");
            }
        );

        const timeout = setTimeout(() => {
            socket.destroy();
            reject(new Error("client timeout"));
        }, 2000);

        socket.setEncoding("utf8");

        socket.once("data", (data) => {
            clearTimeout(timeout);
            resolve({
                response: data,
                socket,
            });
        });

        socket.once("error", (error) => {
            clearTimeout(timeout);
            reject(error);
        });
    });
}

async function demonstrateSockets() {
    console.log("\n" + "=".repeat(78));
    console.log("10. TCP SOCKET CLIENT-SERVER COMMUNICATION");
    console.log("=".repeat(78));

    let server;

    try {
        server = await startLocalTcpServer();
        const address = server.address();

        console.log(`Server listening on 127.0.0.1:${address.port}`);

        const result = await connectToServer(address.port);

        console.log("Client sent: PING");
        console.log("Client received:", result.response);

        result.socket.end();
    } catch (error) {
        console.log("Socket demonstration failed:", error.message);
    } finally {
        if (server) {
            await new Promise((resolve) => server.close(resolve));
        }
    }
}

// ============================================================================
// 11. ASYNCHRONOUS NETWORK OPERATIONS
// ============================================================================

async function runConcurrentLookups() {
    console.log("\n" + "=".repeat(78));
    console.log("11. ASYNCHRONOUS NETWORK OPERATIONS");
    console.log("=".repeat(78));

    const hosts = ["localhost", "example.com", "www.example.org"];

    // Promise.all allows independent network operations to run concurrently.
    const results = await Promise.all(
        hosts.map(async (hostname) => {
            try {
                const result = await dns.lookup(hostname);
                return {
                    hostname,
                    address: result.address,
                    status: "success",
                };
            } catch (error) {
                return {
                    hostname,
                    address: null,
                    status: "failed",
                    error: error.code || error.message,
                };
            }
        })
    );

    console.table(results);
}

// ============================================================================
// 12. TIMEOUT AND RETRY MODEL
// ============================================================================

function sleep(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function retryOperation(operation, attempts, delayMilliseconds) {
    if (attempts <= 0) {
        throw new Error("attempts must be positive");
    }

    let lastError;

    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        try {
            return await operation(attempt);
        } catch (error) {
            lastError = error;

            if (attempt < attempts) {
                await sleep(delayMilliseconds);
            }
        }
    }

    throw lastError;
}

async function demonstrateRetry() {
    console.log("\n" + "=".repeat(78));
    console.log("12. RETRIES AND FAILURE HANDLING");
    console.log("=".repeat(78));

    let successfulAttempt = 0;

    try {
        const result = await retryOperation(
            async (attempt) => {
                successfulAttempt += 1;

                if (attempt < 3) {
                    throw new Error("simulated transient network failure");
                }

                return "request completed";
            },
            4,
            50
        );

        console.log(result);
        console.log("Attempts required:", successfulAttempt);
    } catch (error) {
        console.log("Operation failed:", error.message);
    }

    console.log(
        "Retries should be bounded. Real systems often use exponential backoff and jitter."
    );
}

// ============================================================================
// 13. SERIALIZATION
// ============================================================================

function serializeMessage(message) {
    if (
        !message ||
        typeof message !== "object" ||
        typeof message.type !== "string"
    ) {
        throw new Error("Invalid network message");
    }

    return Buffer.from(JSON.stringify(message), "utf8");
}

function deserializeMessage(buffer) {
    try {
        const message = JSON.parse(buffer.toString("utf8"));

        if (
            !message ||
            typeof message !== "object" ||
            typeof message.type !== "string"
        ) {
            throw new Error("Invalid message structure");
        }

        return message;
    } catch (error) {
        throw new Error(`Message decoding failed: ${error.message}`);
    }
}

function demonstrateSerialization() {
    console.log("\n" + "=".repeat(78));
    console.log("13. SERIALIZATION");
    console.log("=".repeat(78));

    const message = {
        type: "user.lookup",
        requestId: 101,
        payload: {
            userId: 42,
            includeProfile: true,
        },
    };

    const encoded = serializeMessage(message);
    const decoded = deserializeMessage(encoded);

    console.log("Encoded:", encoded.toString("hex"));
    console.dir(decoded, { depth: null });
}

// ============================================================================
// 14. DATA INTEGRITY
// ============================================================================

function sha256(value) {
    return crypto
        .createHash("sha256")
        .update(value)
        .digest("hex");
}

function demonstrateIntegrity() {
    console.log("\n" + "=".repeat(78));
    console.log("14. DATA INTEGRITY");
    console.log("=".repeat(78));

    const original = "network message";
    const modified = "Network message";

    console.log("Original:", sha256(original));
    console.log("Modified:", sha256(modified));
    console.log("Equal:", sha256(original) === sha256(modified));

    console.log(
        "A cryptographic hash detects changes when a trusted reference exists."
    );
}

// ============================================================================
// 15. URL AND APPLICATION ADDRESSING
// ============================================================================

function demonstrateUrlStructure() {
    console.log("\n" + "=".repeat(78));
    console.log("15. APPLICATION ADDRESSING WITH URLS");
    console.log("=".repeat(78));

    const address = new URL(
        "https://api.example.com:443/users/42?active=true#profile"
    );

    console.log("Protocol :", address.protocol);
    console.log("Host     :", address.hostname);
    console.log("Port     :", address.port || "(default)");
    console.log("Path     :", address.pathname);
    console.log("Query    :", address.search);
    console.log("Fragment :", address.hash);
}

// ============================================================================
// 16. FIREWALL MODEL
// ============================================================================

class Firewall {
    constructor(rules = []) {
        this.rules = rules;
    }

    decide(protocol, destinationPort) {
        for (const rule of this.rules) {
            if (
                rule.protocol.toUpperCase() === protocol.toUpperCase() &&
                rule.destinationPort === destinationPort
            ) {
                return rule.action.toUpperCase();
            }
        }

        return "DENY";
    }
}

function demonstrateFirewall() {
    console.log("\n" + "=".repeat(78));
    console.log("16. FIREWALL CONCEPT");
    console.log("=".repeat(78));

    const firewall = new Firewall([
        { protocol: "TCP", destinationPort: 22, action: "allow" },
        { protocol: "TCP", destinationPort: 443, action: "allow" },
        { protocol: "TCP", destinationPort: 23, action: "deny" },
    ]);

    for (const [protocol, port] of [
        ["TCP", 22],
        ["TCP", 443],
        ["TCP", 23],
        ["UDP", 443],
    ]) {
        console.log(
            `${protocol}/${port} -> ${firewall.decide(protocol, port)}`
        );
    }
}

// ============================================================================
// 17. NETWORK PERFORMANCE
// ============================================================================

function calculateTransmissionTimeMs(payloadBytes, bandwidthMbps) {
    if (payloadBytes < 0 || bandwidthMbps <= 0) {
        throw new Error("Invalid transmission parameters");
    }

    const megabits = (payloadBytes * 8) / 1_000_000;
    return (megabits / bandwidthMbps) * 1000;
}

function demonstratePerformance() {
    console.log("\n" + "=".repeat(78));
    console.log("17. NETWORK PERFORMANCE");
    console.log("=".repeat(78));

    const payloadSize = 1500;
    const bandwidth = 100;

    console.log(
        "Transmission time:",
        calculateTransmissionTimeMs(payloadSize, bandwidth).toFixed(3),
        "ms"
    );

    console.log("Bandwidth is capacity; latency is delay.");
    console.log("Throughput is the achieved useful transfer rate.");
    console.log("Packet loss can cause retransmission and lower effective throughput.");
}

// ============================================================================
// 18. SIMPLE NETWORK MONITOR MODEL
// ============================================================================

class NetworkMonitor {
    constructor() {
        this.samples = [];
    }

    record({ latencyMs, packetLossPercent, throughputMbps }) {
        if (
            latencyMs < 0 ||
            packetLossPercent < 0 ||
            packetLossPercent > 100 ||
            throughputMbps < 0
        ) {
            throw new Error("Invalid network measurement");
        }

        this.samples.push({
            latencyMs,
            packetLossPercent,
            throughputMbps,
            timestamp: new Date().toISOString(),
        });
    }

    averages() {
        if (this.samples.length === 0) {
            return null;
        }

        const totals = this.samples.reduce(
            (accumulator, sample) => {
                accumulator.latencyMs += sample.latencyMs;
                accumulator.packetLossPercent += sample.packetLossPercent;
                accumulator.throughputMbps += sample.throughputMbps;
                return accumulator;
            },
            {
                latencyMs: 0,
                packetLossPercent: 0,
                throughputMbps: 0,
            }
        );

        const count = this.samples.length;

        return {
            latencyMs: totals.latencyMs / count,
            packetLossPercent: totals.packetLossPercent / count,
            throughputMbps: totals.throughputMbps / count,
        };
    }
}

function demonstrateMonitoring() {
    console.log("\n" + "=".repeat(78));
    console.log("18. NETWORK MONITORING");
    console.log("=".repeat(78));

    const monitor = new NetworkMonitor();

    monitor.record({
        latencyMs: 18,
        packetLossPercent: 0,
        throughputMbps: 92,
    });

    monitor.record({
        latencyMs: 22,
        packetLossPercent: 1,
        throughputMbps: 87,
    });

    monitor.record({
        latencyMs: 25,
        packetLossPercent: 2,
        throughputMbps: 81,
    });

    console.log("Average measurements:", monitor.averages());
}

// ============================================================================
// 19. SECURITY PRINCIPLES
// ============================================================================

function demonstrateSecurityPrinciples() {
    console.log("\n" + "=".repeat(78));
    console.log("19. NETWORK SECURITY");
    console.log("=".repeat(78));

    const principles = [
        "Encrypt sensitive traffic.",
        "Authenticate remote systems.",
        "Authorize actions using least privilege.",
        "Validate untrusted network input.",
        "Use bounded timeouts.",
        "Protect credentials and cryptographic keys.",
        "Segment networks according to trust boundaries.",
        "Log important events without exposing secrets.",
        "Prefer secure protocols such as HTTPS over plaintext HTTP for sensitive data.",
        "Treat DNS, IP addresses, headers, and payloads as potentially untrusted input.",
    ];

    for (const principle of principles) {
        console.log("-", principle);
    }
}

// ============================================================================
// 20. TROUBLESHOOTING WORKFLOW
// ============================================================================

function demonstrateTroubleshooting() {
    console.log("\n" + "=".repeat(78));
    console.log("20. NETWORK TROUBLESHOOTING WORKFLOW");
    console.log("=".repeat(78));

    const steps = [
        "Check physical or wireless connectivity.",
        "Check the local interface configuration.",
        "Check the subnet and default gateway.",
        "Test the local host networking stack.",
        "Test the gateway.",
        "Test a remote IP address.",
        "Test DNS separately.",
        "Test the destination application port.",
        "Check routing.",
        "Check firewalls and access controls.",
        "Measure latency and packet loss.",
        "Capture traffic when protocol-level evidence is necessary.",
    ];

    steps.forEach((step, index) => {
        console.log(`${index + 1}. ${step}`);
    });
}

// ============================================================================
// 21. SELF-TESTS
// ============================================================================

function runSelfTests() {
    console.log("\n" + "=".repeat(78));
    console.log("21. SELF-TESTS");
    console.log("=".repeat(78));

    console.assert(ipv4ToInteger("127.0.0.1") !== null);
    console.assert(integerToIpv4(ipv4ToInteger("192.168.1.1")) === "192.168.1.1");

    const subnet = calculateSubnet("192.168.1.25", 24);
    console.assert(subnet.network === "192.168.1.0");
    console.assert(subnet.broadcast === "192.168.1.255");

    const table = new RoutingTable();
    table.addRoute("0.0.0.0", 0, "WAN");
    table.addRoute("10.0.0.0", 8, "LAN");

    console.assert(table.lookup("10.1.1.1").nextHop === "LAN");
    console.assert(table.lookup("8.8.8.8").nextHop === "WAN");

    const encoded = serializeMessage({
        type: "test",
        payload: { value: 10 },
    });

    console.assert(deserializeMessage(encoded).payload.value === 10);

    console.log("Self-tests completed.");
}

// ============================================================================
// 22. MAIN
// ============================================================================

async function main() {
    console.log("=".repeat(78));
    console.log("INTRODUCTION TO COMPUTER NETWORKING");
    console.log("=".repeat(78));

    showFoundations();
    demonstrateEncapsulation();
    demonstrateIPv4();
    demonstratePackets();
    demonstrateRouting();
    demonstrateSwitching();
    demonstrateTransportProtocols();
    demonstrateHttp();
    await demonstrateDns();
    await demonstrateSockets();
    await runConcurrentLookups();
    await demonstrateRetry();
    demonstrateSerialization();
    demonstrateIntegrity();
    demonstrateUrlStructure();
    demonstrateFirewall();
    demonstratePerformance();
    demonstrateMonitoring();
    demonstrateSecurityPrinciples();
    demonstrateTroubleshooting();
    runSelfTests();

    console.log("\n" + "=".repeat(78));
    console.log("END OF JAVASCRIPT NETWORKING STUDY PROGRAM");
    console.log("=".repeat(78));
}

main().catch((error) => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});
