#!/usr/bin/env node
"use strict";

/*
 * Linux Networking with JavaScript / Node.js
 *
 * This file complements the Python study program by demonstrating networking
 * through Node.js APIs:
 *
 *   - Operating-system interface information
 *   - IPv4/IPv6 inspection
 *   - DNS resolution
 *   - TCP sockets
 *   - UDP datagrams
 *   - Port testing
 *   - HTTP connectivity
 *   - Latency measurement
 *   - Validation
 *   - Error handling
 *   - Concurrent diagnostics
 *
 * Run with:
 *   node linux_networking_study.js
 *
 * Node.js provides portable APIs, while Linux-specific commands such as
 * "ip", "ss", and "resolvectl" remain useful for kernel-level inspection.
 */

const os = require("os");
const dns = require("dns").promises;
const net = require("net");
const dgram = require("dgram");
const http = require("http");
const { execFile } = require("child_process");
const { promisify } = require("util");

const execFileAsync = promisify(execFile);


// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

function section(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function subsection(title) {
    console.log(`\n--- ${title} ---`);
}

function sleep(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function runCommand(command, args = [], timeout = 5000) {
    try {
        const result = await execFileAsync(command, args, {
            timeout,
            maxBuffer: 1024 * 1024
        });

        return {
            code: 0,
            stdout: result.stdout,
            stderr: result.stderr
        };
    } catch (error) {
        return {
            code: typeof error.code === "number" ? error.code : 1,
            stdout: error.stdout || "",
            stderr: error.stderr || error.message
        };
    }
}

async function showCommand(command, args = []) {
    console.log("$", command, ...args);

    const result = await runCommand(command, args);

    if (result.stdout.trim()) {
        console.log(result.stdout.trim());
    }

    if (result.stderr.trim()) {
        console.error(result.stderr.trim());
    }

    if (result.code !== 0) {
        console.log(`[exit code: ${result.code}]`);
    }
}


// ---------------------------------------------------------------------------
// Interface discovery
// ---------------------------------------------------------------------------

section("1. NETWORK INTERFACES");

console.log("Hostname:", os.hostname());
console.log("Platform:", process.platform);
console.log("Architecture:", process.arch);

const interfaces = os.networkInterfaces();

for (const [name, addresses] of Object.entries(interfaces)) {
    console.log(`\n${name}:`);

    for (const address of addresses) {
        console.log(
            `  family=${address.family} ` +
            `address=${address.address} ` +
            `netmask=${address.netmask} ` +
            `mac=${address.mac} ` +
            `internal=${address.internal} ` +
            `cidr=${address.cidr}`
        );
    }
}

console.log(
    "\nNode.js exposes interface information through os.networkInterfaces()."
);


// ---------------------------------------------------------------------------
// IP address validation
// ---------------------------------------------------------------------------

section("2. IP ADDRESS VALIDATION");

function isIPv4(address) {
    return net.isIPv4(address);
}

function isIPv6(address) {
    return net.isIPv6(address);
}

const addressExamples = [
    "127.0.0.1",
    "192.168.1.25",
    "::1",
    "2001:db8::25",
    "999.1.1.1"
];

for (const address of addressExamples) {
    console.log(
        `${address.padEnd(20)} ` +
        `IPv4=${isIPv4(address)} ` +
        `IPv6=${isIPv6(address)}`
    );
}


// ---------------------------------------------------------------------------
// CIDR validation
// ---------------------------------------------------------------------------

section("3. CIDR AND SUBNET VALIDATION");

function ipv4ToInteger(address) {
    const parts = address.split(".").map(Number);

    if (
        parts.length !== 4 ||
        parts.some(part => !Number.isInteger(part) || part < 0 || part > 255)
    ) {
        throw new Error(`Invalid IPv4 address: ${address}`);
    }

    return (
        ((parts[0] << 24) >>> 0) +
        (parts[1] << 16) +
        (parts[2] << 8) +
        parts[3]
    ) >>> 0;
}

function integerToIPv4(value) {
    return [
        (value >>> 24) & 255,
        (value >>> 16) & 255,
        (value >>> 8) & 255,
        value & 255
    ].join(".");
}

function cidrContainsIPv4(cidr, address) {
    const [networkAddress, prefixText] = cidr.split("/");
    const prefix = Number(prefixText);

    if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32) {
        throw new Error(`Invalid prefix: ${prefixText}`);
    }

    const network = ipv4ToInteger(networkAddress);
    const target = ipv4ToInteger(address);

    if (prefix === 0) {
        return true;
    }

    const mask = (0xffffffff << (32 - prefix)) >>> 0;

    return (network & mask) === (target & mask);
}

const subnetTests = [
    ["192.168.1.0/24", "192.168.1.25"],
    ["192.168.1.0/24", "192.168.2.25"],
    ["10.0.0.0/8", "10.200.30.40"]
];

for (const [cidr, address] of subnetTests) {
    console.log(
        `${address} in ${cidr}: ${cidrContainsIPv4(cidr, address)}`
    );
}

console.log(
    "Network address conversion:",
    integerToIPv4(ipv4ToInteger("192.168.1.25"))
);


// ---------------------------------------------------------------------------
// Linux command inspection
// ---------------------------------------------------------------------------

section("4. LINUX KERNEL NETWORKING INFORMATION");

if (process.platform === "linux") {
    await showCommand("ip", ["-br", "link"]);
    await showCommand("ip", ["-br", "addr"]);
    await showCommand("ip", ["route"]);
    await showCommand("ip", ["-6", "route"]);
    await showCommand("ip", ["neigh"]);
} else {
    console.log(
        "The Node.js APIs are available here, but Linux-specific " +
        "iproute2 commands are skipped."
    );
}


// ---------------------------------------------------------------------------
// DNS
// ---------------------------------------------------------------------------

section("5. DNS RESOLUTION");

async function resolveDomain(domain) {
    const started = process.hrtime.bigint();

    try {
        const addresses = await dns.lookup(domain, {
            all: true,
            verbatim: true
        });

        const elapsedMs =
            Number(process.hrtime.bigint() - started) / 1_000_000;

        return {
            domain,
            addresses,
            elapsedMs
        };
    } catch (error) {
        return {
            domain,
            error: error.code || error.message,
            elapsedMs:
                Number(process.hrtime.bigint() - started) / 1_000_000
        };
    }
}

for (const domain of ["localhost", "example.com"]) {
    const result = await resolveDomain(domain);

    console.log(`\n${domain}`);

    if (result.error) {
        console.log("  Error:", result.error);
    } else {
        for (const address of result.addresses) {
            console.log(
                `  ${address.address} family=${address.family}`
            );
        }
    }

    console.log(`  Lookup time: ${result.elapsedMs.toFixed(3)} ms`);
}

subsection("Explicit DNS record lookup");

try {
    const records = await dns.resolve4("example.com");
    console.log("A records:", records);
} catch (error) {
    console.log("A record lookup failed:", error.code || error.message);
}


// ---------------------------------------------------------------------------
// DNS configuration commands
// ---------------------------------------------------------------------------

section("6. DNS CONFIGURATION INSPECTION");

if (process.platform === "linux") {
    await showCommand("cat", ["/etc/resolv.conf"]);

    const resolverStatus = await runCommand("resolvectl", ["status"]);

    if (resolverStatus.code === 0) {
        console.log(resolverStatus.stdout);
    } else {
        console.log(
            "resolvectl is unavailable or failed. DNS may be managed by " +
            "another Linux networking component."
        );
    }
}


// ---------------------------------------------------------------------------
// TCP server and client
// ---------------------------------------------------------------------------

section("7. TCP SOCKET CASE STUDY");

function createTcpEchoServer() {
    return new Promise((resolve, reject) => {
        const server = net.createServer(socket => {
            socket.setEncoding("utf8");

            socket.on("data", data => {
                socket.write(`ACK:${data}`);
            });

            socket.on("error", error => {
                console.error("Server socket error:", error.message);
            });
        });

        server.once("error", reject);

        server.listen({
            host: "127.0.0.1",
            port: 0
        }, () => {
            const address = server.address();

            if (typeof address !== "object" || address === null) {
                reject(new Error("Unable to determine server address."));
                return;
            }

            resolve({ server, port: address.port });
        });
    });
}

function tcpRequest(host, port, message, timeoutMs = 2000) {
    return new Promise((resolve, reject) => {
        const started = process.hrtime.bigint();
        const socket = net.createConnection({
            host,
            port
        });

        let response = "";
        let settled = false;

        function finish(callback, value) {
            if (settled) {
                return;
            }

            settled = true;
            callback(value);
        }

        socket.setTimeout(timeoutMs);

        socket.setEncoding("utf8");

        socket.on("connect", () => {
            socket.write(message);
        });

        socket.on("data", chunk => {
            response += chunk;
            socket.end();
        });

        socket.on("end", () => {
            const elapsedMs =
                Number(process.hrtime.bigint() - started) / 1_000_000;

            finish(resolve, {
                response,
                elapsedMs
            });
        });

        socket.on("timeout", () => {
            socket.destroy();
            finish(reject, new Error("TCP connection timed out"));
        });

        socket.on("error", error => {
            finish(reject, error);
        });
    });
}

const tcpDemo = await createTcpEchoServer();

try {
    const result = await tcpRequest(
        "127.0.0.1",
        tcpDemo.port,
        "Linux TCP"
    );

    console.log("Response:", result.response);
    console.log(`Elapsed: ${result.elapsedMs.toFixed(3)} ms`);
} catch (error) {
    console.log("TCP demonstration failed:", error.message);
} finally {
    await new Promise(resolve => tcpDemo.server.close(resolve));
}


// ---------------------------------------------------------------------------
// UDP demonstration
// ---------------------------------------------------------------------------

section("8. UDP SOCKET CASE STUDY");

function createUdpEchoServer() {
    return new Promise((resolve, reject) => {
        const socket = dgram.createSocket("udp4");

        socket.once("error", error => {
            socket.close();
            reject(error);
        });

        socket.on("message", (message, remote) => {
            const response = Buffer.from(`UDP-ACK:${message.toString()}`);

            socket.send(
                response,
                remote.port,
                remote.address,
                error => {
                    if (error) {
                        console.error("UDP send error:", error.message);
                    }
                }
            );
        });

        socket.bind(0, "127.0.0.1", () => {
            const address = socket.address();

            if (typeof address !== "object" || address === null) {
                reject(new Error("Unable to determine UDP port."));
                return;
            }

            resolve({ socket, port: address.port });
        });
    });
}

function udpRequest(host, port, message, timeoutMs = 2000) {
    return new Promise((resolve, reject) => {
        const socket = dgram.createSocket("udp4");
        const started = process.hrtime.bigint();

        const timer = setTimeout(() => {
            socket.close();
            reject(new Error("UDP response timed out"));
        }, timeoutMs);

        socket.on("message", response => {
            clearTimeout(timer);

            const elapsedMs =
                Number(process.hrtime.bigint() - started) / 1_000_000;

            socket.close();

            resolve({
                response: response.toString(),
                elapsedMs
            });
        });

        socket.on("error", error => {
            clearTimeout(timer);
            socket.close();
            reject(error);
        });

        socket.send(
            Buffer.from(message),
            port,
            host,
            error => {
                if (error) {
                    clearTimeout(timer);
                    socket.close();
                    reject(error);
                }
            }
        );
    });
}

const udpDemo = await createUdpEchoServer();

try {
    const result = await udpRequest(
        "127.0.0.1",
        udpDemo.port,
        "Linux UDP"
    );

    console.log("Response:", result.response);
    console.log(`Elapsed: ${result.elapsedMs.toFixed(3)} ms`);
} catch (error) {
    console.log("UDP demonstration failed:", error.message);
} finally {
    udpDemo.socket.close();
}


// ---------------------------------------------------------------------------
// TCP port diagnostics
// ---------------------------------------------------------------------------

section("9. TCP PORT TESTING");

function testTcpPort(host, port, timeoutMs = 2000) {
    return new Promise(resolve => {
        const started = process.hrtime.bigint();

        const socket = net.createConnection({
            host,
            port
        });

        let finished = false;

        function complete(result) {
            if (finished) {
                return;
            }

            finished = true;
            socket.destroy();
            resolve(result);
        }

        socket.setTimeout(timeoutMs);

        socket.once("connect", () => {
            const elapsedMs =
                Number(process.hrtime.bigint() - started) / 1_000_000;

            complete({
                reachable: true,
                state: "open",
                elapsedMs
            });
        });

        socket.once("timeout", () => {
            complete({
                reachable: false,
                state: "timeout",
                elapsedMs:
                    Number(process.hrtime.bigint() - started) / 1_000_000
            });
        });

        socket.once("error", error => {
            complete({
                reachable: false,
                state: error.code || error.message,
                elapsedMs:
                    Number(process.hrtime.bigint() - started) / 1_000_000
            });
        });
    });
}

for (const [host, port] of [
    ["example.com", 443],
    ["example.com", 80],
    ["example.com", 1]
]) {
    const result = await testTcpPort(host, port);

    console.log(
        `${host}:${port} -> ${result.state}, ` +
        `${result.elapsedMs.toFixed(3)} ms`
    );
}


// ---------------------------------------------------------------------------
// HTTP application-level test
// ---------------------------------------------------------------------------

section("10. APPLICATION-LEVEL HTTP TEST");

function httpHeadRequest(hostname, timeoutMs = 3000) {
    return new Promise(resolve => {
        const started = process.hrtime.bigint();

        const request = http.request({
            hostname,
            port: 80,
            path: "/",
            method: "HEAD",
            timeout: timeoutMs
        }, response => {
            const elapsedMs =
                Number(process.hrtime.bigint() - started) / 1_000_000;

            response.resume();

            resolve({
                success: true,
                statusCode: response.statusCode,
                elapsedMs
            });
        });

        request.on("timeout", () => {
            request.destroy(new Error("HTTP request timed out"));
        });

        request.on("error", error => {
            const elapsedMs =
                Number(process.hrtime.bigint() - started) / 1_000_000;

            resolve({
                success: false,
                error: error.code || error.message,
                elapsedMs
            });
        });

        request.end();
    });
}

const httpResult = await httpHeadRequest("example.com");

if (httpResult.success) {
    console.log(
        `HTTP status=${httpResult.statusCode}, ` +
        `elapsed=${httpResult.elapsedMs.toFixed(3)} ms`
    );
} else {
    console.log(
        `HTTP failed: ${httpResult.error}, ` +
        `elapsed=${httpResult.elapsedMs.toFixed(3)} ms`
    );
}


// ---------------------------------------------------------------------------
// Concurrent diagnostics
// ---------------------------------------------------------------------------

section("11. CONCURRENT NETWORK DIAGNOSTICS");

async function diagnoseHost(hostname) {
    const dnsResult = await resolveDomain(hostname);

    const portTests = await Promise.all([
        testTcpPort(hostname, 80),
        testTcpPort(hostname, 443)
    ]);

    return {
        hostname,
        dns: dnsResult,
        ports: portTests
    };
}

const hostsToDiagnose = ["example.com"];

const diagnosticResults = await Promise.all(
    hostsToDiagnose.map(diagnoseHost)
);

for (const result of diagnosticResults) {
    console.log(`\nHost: ${result.hostname}`);

    if (result.dns.error) {
        console.log("DNS:", result.dns.error);
    } else {
        console.log(
            "DNS:",
            result.dns.addresses.map(item => item.address).join(", ")
        );
    }

    for (const portResult of result.ports) {
        console.log(
            `TCP test: ${portResult.state} ` +
            `(${portResult.elapsedMs.toFixed(3)} ms)`
        );
    }
}


// ---------------------------------------------------------------------------
// Network troubleshooting decision model
// ---------------------------------------------------------------------------

section("12. TROUBLESHOOTING DECISION MODEL");

function diagnose({
    interfaceUp,
    hasAddress,
    hasDefaultRoute,
    gatewayReachable,
    dnsWorks,
    serviceReachable
}) {
    if (!interfaceUp) {
        return "Inspect interface state and physical or virtual connectivity.";
    }

    if (!hasAddress) {
        return "Inspect DHCP/static configuration and subnet prefix.";
    }

    if (!hasDefaultRoute) {
        return "Inspect the routing table and default gateway.";
    }

    if (!gatewayReachable) {
        return "Inspect local subnet, neighbor discovery, VLAN, and gateway.";
    }

    if (!dnsWorks) {
        return "Inspect resolver configuration and DNS service reachability.";
    }

    if (!serviceReachable) {
        return "Inspect service state, port, firewall, ACL, and application logs.";
    }

    return "Basic network path appears operational; investigate application behavior.";
}

const scenarios = [
    {
        interfaceUp: false,
        hasAddress: false,
        hasDefaultRoute: false,
        gatewayReachable: false,
        dnsWorks: false,
        serviceReachable: false
    },
    {
        interfaceUp: true,
        hasAddress: true,
        hasDefaultRoute: true,
        gatewayReachable: true,
        dnsWorks: false,
        serviceReachable: false
    },
    {
        interfaceUp: true,
        hasAddress: true,
        hasDefaultRoute: true,
        gatewayReachable: true,
        dnsWorks: true,
        serviceReachable: false
    },
    {
        interfaceUp: true,
        hasAddress: true,
        hasDefaultRoute: true,
        gatewayReachable: true,
        dnsWorks: true,
        serviceReachable: true
    }
];

for (const scenario of scenarios) {
    console.log(diagnose(scenario));
}


// ---------------------------------------------------------------------------
// DNS error classification
// ---------------------------------------------------------------------------

section("13. DNS ERROR HANDLING");

const dnsErrorExamples = [
    "ENOTFOUND",
    "EAI_AGAIN",
    "ECONNREFUSED",
    "ETIMEOUT"
];

const dnsMeanings = {
    ENOTFOUND: "The requested name could not be resolved.",
    EAI_AGAIN: "A temporary resolver failure occurred.",
    ECONNREFUSED: "A connection was refused by the relevant service.",
    ETIMEOUT: "The operation exceeded its timeout."
};

for (const code of dnsErrorExamples) {
    console.log(`${code}: ${dnsMeanings[code]}`);
}


// ---------------------------------------------------------------------------
// Performance calculations
// ---------------------------------------------------------------------------

section("14. PERFORMANCE CONCEPTS");

function calculateThroughput(bytes, elapsedSeconds) {
    if (elapsedSeconds <= 0) {
        throw new Error("Elapsed time must be greater than zero.");
    }

    return bytes / elapsedSeconds;
}

const bytesTransferred = 10 * 1024 * 1024;
const elapsedSeconds = 2.0;
const throughputBytesPerSecond =
    calculateThroughput(bytesTransferred, elapsedSeconds);

console.log(
    "Throughput:",
    (throughputBytesPerSecond / (1024 * 1024)).toFixed(2),
    "MiB/s"
);

console.log(
    `
Bandwidth, throughput, latency, RTT, jitter, packet loss, MTU, TCP
congestion control, DNS delay, and server processing time are different
measurements. A high-bandwidth network can still have poor application
performance when latency, packet loss, congestion, or application behavior
dominates the total response time.
`
);


// ---------------------------------------------------------------------------
// Security considerations
// ---------------------------------------------------------------------------

section("15. SECURITY CONSIDERATIONS");

console.log(`
Important security rules:

- Do not expose development services unnecessarily.
- Avoid binding administrative services to public interfaces without a
  deliberate access-control design.
- Prefer TLS-protected application protocols.
- Validate certificates and hostnames.
- Restrict firewall rules to required traffic.
- Monitor unexpected listening ports.
- Treat DNS configuration as security-sensitive.
- Protect packet captures because they can contain sensitive metadata.
- Avoid logging credentials, authorization headers, or private payloads.
- Use least privilege when inspecting or modifying network configuration.
`);


// ---------------------------------------------------------------------------
// Final command reference
// ---------------------------------------------------------------------------

section("16. LINUX COMMAND REFERENCE");

const commands = [
    ["ip -br link", "Interface state"],
    ["ip -br addr", "IP configuration"],
    ["ip route", "IPv4 routes"],
    ["ip -6 route", "IPv6 routes"],
    ["ip route get 8.8.8.8", "Kernel route selection"],
    ["ip neigh", "Neighbor table"],
    ["ss -lntup", "Listening sockets"],
    ["resolvectl status", "DNS resolver status"],
    ["getent hosts example.com", "Resolver-path lookup"],
    ["ping 127.0.0.1", "ICMP test"],
    ["tracepath example.com", "Path and MTU diagnostics"],
    ["tcpdump -ni any", "Packet capture"]
];

for (const [command, purpose] of commands) {
    console.log(`${command.padEnd(38)} ${purpose}`);
}

console.log("\nLinux networking study program completed.");
