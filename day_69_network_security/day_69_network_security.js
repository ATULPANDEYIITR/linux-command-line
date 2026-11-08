"use strict";

/*
 * Network Security Policy Engine
 *
 * Demonstrates:
 * - Firewall policy evaluation
 * - Stateful security groups
 * - Stateless network ACLs
 * - CIDR matching for IPv4
 * - Protocol and port filtering
 * - Rule priority
 * - Event-driven security monitoring
 * - Asynchronous traffic processing
 * - Audit records and policy management
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const net = require("node:net");
const fs = require("node:fs/promises");
const EventEmitter = require("node:events");

// -------------------------------------------------------
// Enumerations
// -------------------------------------------------------

const Protocol = Object.freeze({
    TCP: "TCP",
    UDP: "UDP",
    ICMP: "ICMP",
    ANY: "ANY"
});

const Direction = Object.freeze({
    INBOUND: "INBOUND",
    OUTBOUND: "OUTBOUND"
});

const Action = Object.freeze({
    ALLOW: "ALLOW",
    DENY: "DENY"
});

// -------------------------------------------------------
// Validation
// -------------------------------------------------------

function validateIPv4(address) {
    if (net.isIP(address) !== 4) {
        throw new Error(`Invalid IPv4 address: ${address}`);
    }
}

function validatePort(port) {
    if (!Number.isInteger(port) || port < 0 || port > 65535) {
        throw new Error(`Invalid port: ${port}`);
    }
}

// Convert IPv4 addresses into unsigned 32-bit integers.
function ipv4ToInteger(address) {
    validateIPv4(address);

    return address.split(".").reduce(
        (result, octet) => ((result << 8) | Number(octet)) >>> 0,
        0
    );
}

// -------------------------------------------------------
// CIDR Matching
// -------------------------------------------------------

class CIDR {
    constructor(value) {
        const parts = value.split("/");

        if (parts.length > 2) {
            throw new Error(`Invalid CIDR: ${value}`);
        }

        this.address = parts[0];
        this.prefix = parts.length === 2
            ? Number(parts[1])
            : 32;

        if (!Number.isInteger(this.prefix) ||
            this.prefix < 0 ||
            this.prefix > 32) {
            throw new Error(`Invalid CIDR prefix: ${value}`);
        }

        this.network = ipv4ToInteger(this.address);

        this.mask = this.prefix === 0
            ? 0
            : (0xFFFFFFFF << (32 - this.prefix)) >>> 0;

        this.network = (this.network & this.mask) >>> 0;
    }

    contains(address) {
        const candidate = ipv4ToInteger(address);

        return ((candidate & this.mask) >>> 0) === this.network;
    }
}

// -------------------------------------------------------
// Packet
// -------------------------------------------------------

class Packet {
    constructor({
        sourceIP,
        destinationIP,
        sourcePort = 0,
        destinationPort = 0,
        protocol,
        direction
    }) {
        this.sourceIP = sourceIP;
        this.destinationIP = destinationIP;
        this.sourcePort = sourcePort;
        this.destinationPort = destinationPort;
        this.protocol = protocol;
        this.direction = direction;

        this.validate();

        Object.freeze(this);
    }

    validate() {
        validateIPv4(this.sourceIP);
        validateIPv4(this.destinationIP);
        validatePort(this.sourcePort);
        validatePort(this.destinationPort);

        if (!Object.values(Protocol).includes(this.protocol)) {
            throw new Error("Unsupported protocol");
        }

        if (!Object.values(Direction).includes(this.direction)) {
            throw new Error("Unsupported direction");
        }

        if (this.protocol === Protocol.ICMP &&
            (this.sourcePort !== 0 || this.destinationPort !== 0)) {
            throw new Error("ICMP cannot contain TCP/UDP ports");
        }
    }

    get key() {
        return [
            this.sourceIP,
            this.sourcePort,
            this.destinationIP,
            this.destinationPort,
            this.protocol
        ].join(":");
    }

    get reverseKey() {
        return [
            this.destinationIP,
            this.destinationPort,
            this.sourceIP,
            this.sourcePort,
            this.protocol
        ].join(":");
    }
}

// -------------------------------------------------------
// Firewall Rule
// -------------------------------------------------------

class FirewallRule {
    constructor({
        id,
        name,
        sourceCIDR,
        destinationCIDR,
        protocol,
        direction,
        action,
        priority,
        portStart = 0,
        portEnd = 65535,
        enabled = true
    }) {
        if (!id || !name) {
            throw new Error("Rule ID and name are required");
        }

        if (!Object.values(Protocol).includes(protocol) ||
            !Object.values(Direction).includes(direction) ||
            !Object.values(Action).includes(action)) {
            throw new Error("Invalid rule configuration");
        }

        if (!Number.isInteger(priority) || priority < 0) {
            throw new Error("Priority must be non-negative");
        }

        validatePort(portStart);
        validatePort(portEnd);

        if (portStart > portEnd) {
            throw new Error("Invalid port range");
        }

        if (protocol === Protocol.ICMP &&
            (portStart !== 0 || portEnd !== 65535)) {
            throw new Error("ICMP rules cannot restrict ports");
        }

        this.id = id;
        this.name = name;
        this.source = new CIDR(sourceCIDR);
        this.destination = new CIDR(destinationCIDR);
        this.protocol = protocol;
        this.direction = direction;
        this.action = action;
        this.priority = priority;
        this.portStart = portStart;
        this.portEnd = portEnd;
        this.enabled = enabled;

        Object.freeze(this);
    }

    matches(packet) {
        if (!this.enabled) return false;
        if (this.direction !== packet.direction) return false;

        if (this.protocol !== Protocol.ANY &&
            this.protocol !== packet.protocol) {
            return false;
        }

        if (!this.source.contains(packet.sourceIP)) return false;
        if (!this.destination.contains(packet.destinationIP)) return false;

        if (packet.protocol === Protocol.ICMP) return true;

        return packet.destinationPort >= this.portStart &&
            packet.destinationPort <= this.portEnd;
    }
}

// -------------------------------------------------------
// Stateful Connection Table
// -------------------------------------------------------

class ConnectionTable {
    constructor() {
        this.active = new Map();
    }

    establish(packet) {
        if (packet.protocol === Protocol.ICMP ||
            packet.protocol === Protocol.ANY) {
            return;
        }

        this.active.set(packet.key, {
            establishedAt: new Date().toISOString(),
            protocol: packet.protocol
        });
    }

    isReturnTraffic(packet) {
        return this.active.has(packet.reverseKey);
    }

    close(packet) {
        this.active.delete(packet.key);
    }

    get size() {
        return this.active.size;
    }
}

// -------------------------------------------------------
// Policy Evaluator
// -------------------------------------------------------

class PolicyEvaluator {

    constructor(rules, { stateful = false } = {}) {
        this.rules = [...rules].sort(
            (a, b) => a.priority - b.priority
        );

        this.stateful = stateful;
        this.connections = new ConnectionTable();
    }

    evaluate(packet) {
        if (this.stateful &&
            this.connections.isReturnTraffic(packet)) {
            return {
                allowed: true,
                reason: "STATEFUL_RETURN",
                ruleID: null
            };
        }

        const matched = this.rules.find(
            rule => rule.matches(packet)
        );

        if (!matched) {
            return {
                allowed: false,
                reason: "DEFAULT_DENY",
                ruleID: null
            };
        }

        const allowed = matched.action === Action.ALLOW;

        if (allowed && this.stateful) {
            this.connections.establish(packet);
        }

        return {
            allowed,
            reason: "RULE_MATCH",
            ruleID: matched.id,
            ruleName: matched.name
        };
    }

    replaceRules(rules) {
        const ids = new Set();

        for (const rule of rules) {
            if (!(rule instanceof FirewallRule)) {
                throw new Error("All policies must be FirewallRule objects");
            }

            if (ids.has(rule.id)) {
                throw new Error(`Duplicate rule ID: ${rule.id}`);
            }

            ids.add(rule.id);
        }

        this.rules = [...rules].sort(
            (a, b) => a.priority - b.priority
        );
    }
}

// -------------------------------------------------------
// Security Group
// -------------------------------------------------------

class SecurityGroup {
    constructor(id, inboundRules) {
        this.id = id;
        this.evaluator = new PolicyEvaluator(
            inboundRules,
            { stateful: true }
        );
    }

    inspect(packet) {
        if (packet.direction !== Direction.INBOUND) {
            throw new Error("Security group expects inbound traffic");
        }

        return this.evaluator.evaluate(packet);
    }
}

// -------------------------------------------------------
// Network ACL
// -------------------------------------------------------

class NetworkACL {
    constructor(id, rules) {
        this.id = id;

        // NACL evaluation is stateless.
        this.evaluator = new PolicyEvaluator(
            rules,
            { stateful: false }
        );
    }

    inspect(packet) {
        return this.evaluator.evaluate(packet);
    }
}

// -------------------------------------------------------
// Firewall
// -------------------------------------------------------

class Firewall {
    constructor(rules) {
        this.evaluator = new PolicyEvaluator(
            rules,
            { stateful: true }
        );
    }

    inspect(packet) {
        return this.evaluator.evaluate(packet);
    }
}

// -------------------------------------------------------
// Network Security Gateway
// -------------------------------------------------------

class NetworkSecurityGateway extends EventEmitter {

    constructor(firewall, securityGroup, networkACL) {
        super();

        this.firewall = firewall;
        this.securityGroup = securityGroup;
        this.networkACL = networkACL;
        this.auditRecords = [];
    }

    inspect(packet) {
        const layers = [
            ["FIREWALL", () => this.firewall.inspect(packet)]
        ];

        if (packet.direction === Direction.INBOUND) {
            layers.push([
                "SECURITY_GROUP",
                () => this.securityGroup.inspect(packet)
            ]);
        }

        layers.push([
            "NETWORK_ACL",
            () => this.networkACL.inspect(packet)
        ]);

        for (const [layer, evaluator] of layers) {
            const decision = evaluator();

            if (!decision.allowed) {
                return this.record({
                    allowed: false,
                    blockedBy: layer,
                    ...decision
                }, packet);
            }
        }

        return this.record({
            allowed: true,
            blockedBy: null,
            reason: "ALL_CONTROLS_PASSED"
        }, packet);
    }

    record(decision, packet) {
        const event = Object.freeze({
            timestamp: new Date().toISOString(),
            sourceIP: packet.sourceIP,
            destinationIP: packet.destinationIP,
            protocol: packet.protocol,
            destinationPort: packet.destinationPort,
            ...decision
        });

        this.auditRecords.push(event);

        this.emit("security-event", event);

        return event;
    }

    report() {
        return {
            total: this.auditRecords.length,
            allowed: this.auditRecords.filter(
                item => item.allowed
            ).length,
            denied: this.auditRecords.filter(
                item => !item.allowed
            ).length,
            blockedBy: Object.groupBy(
                this.auditRecords.filter(item => !item.allowed),
                item => item.blockedBy
            )
        };
    }
}

// -------------------------------------------------------
// Asynchronous Traffic Processing
// -------------------------------------------------------

async function processPackets(gateway, packets) {
    const results = [];

    for (const packetData of packets) {
        // Validation failures are isolated per packet.
        try {
            const packet = new Packet(packetData);
            results.push(gateway.inspect(packet));
        } catch (error) {
            results.push({
                allowed: false,
                blockedBy: "VALIDATION",
                error: error.message
            });
        }
    }

    return results;
}

// -------------------------------------------------------
// Configuration Persistence
// -------------------------------------------------------

async function saveAudit(records, filename = "network-audit.json") {
    const data = JSON.stringify(records, null, 2);

    await fs.writeFile(filename, data, {
        encoding: "utf8",
        mode: 0o600
    });
}

// -------------------------------------------------------
// Application
// -------------------------------------------------------

async function main() {

    const firewallRules = [
        new FirewallRule({
            id: "FW-001",
            name: "Allow internal HTTPS",
            sourceCIDR: "10.0.0.0/8",
            destinationCIDR: "172.16.0.0/12",
            protocol: Protocol.TCP,
            direction: Direction.INBOUND,
            action: Action.ALLOW,
            priority: 100,
            portStart: 443,
            portEnd: 443
        }),
        new FirewallRule({
            id: "FW-002",
            name: "Block HTTP",
            sourceCIDR: "0.0.0.0/0",
            destinationCIDR: "172.16.0.0/12",
            protocol: Protocol.TCP,
            direction: Direction.INBOUND,
            action: Action.DENY,
            priority: 200,
            portStart: 80,
            portEnd: 80
        })
    ];

    const groupRules = [
        new FirewallRule({
            id: "SG-001",
            name: "Application HTTPS",
            sourceCIDR: "10.0.0.0/8",
            destinationCIDR: "172.16.0.0/12",
            protocol: Protocol.TCP,
            direction: Direction.INBOUND,
            action: Action.ALLOW,
            priority: 100,
            portStart: 443,
            portEnd: 443
        })
    ];

    const aclRules = [
        new FirewallRule({
            id: "ACL-100",
            name: "Allow inbound HTTPS",
            sourceCIDR: "10.0.0.0/8",
            destinationCIDR: "172.16.0.0/12",
            protocol: Protocol.TCP,
            direction: Direction.INBOUND,
            action: Action.ALLOW,
            priority: 100,
            portStart: 443,
            portEnd: 443
        }),
        new FirewallRule({
            id: "ACL-200",
            name: "Allow outbound HTTPS response",
            sourceCIDR: "172.16.0.0/12",
            destinationCIDR: "10.0.0.0/8",
            protocol: Protocol.TCP,
            direction: Direction.OUTBOUND,
            action: Action.ALLOW,
            priority: 100,
            portStart: 1024,
            portEnd: 65535
        })
    ];

    const gateway = new NetworkSecurityGateway(
        new Firewall(firewallRules),
        new SecurityGroup("WEB-SG", groupRules),
        new NetworkACL("PRODUCTION-ACL", aclRules)
    );

    gateway.on("security-event", event => {
        console.log(
            `[SECURITY EVENT] ${event.allowed ? "ALLOW" : "DENY"} |`,
            event.sourceIP,
            "->",
            event.destinationIP,
            "|",
            event.blockedBy || "NONE"
        );
    });

    const traffic = [
        {
            sourceIP: "10.1.1.10",
            destinationIP: "172.16.1.20",
            sourcePort: 51000,
            destinationPort: 443,
            protocol: Protocol.TCP,
            direction: Direction.INBOUND
        },
        {
            sourceIP: "203.0.113.25",
            destinationIP: "172.16.1.20",
            sourcePort: 51001,
            destinationPort: 80,
            protocol: Protocol.TCP,
            direction: Direction.INBOUND
        },
        {
            sourceIP: "10.1.1.10",
            destinationIP: "172.16.1.20",
            sourcePort: 51002,
            destinationPort: 22,
            protocol: Protocol.TCP,
            direction: Direction.INBOUND
        }
    ];

    console.log("\nNETWORK SECURITY TRAFFIC ANALYSIS\n");

    const results = await processPackets(gateway, traffic);

    console.table(results);

    console.log("\nSECURITY REPORT");
    console.log(JSON.stringify(gateway.report(), null, 2));

    // Return traffic must match the established firewall connection.
    const response = new Packet({
        sourceIP: "172.16.1.20",
        destinationIP: "10.1.1.10",
        sourcePort: 443,
        destinationPort: 51000,
        protocol: Protocol.TCP,
        direction: Direction.OUTBOUND
    });

    console.log("\nSTATEFUL RETURN TRAFFIC");
    console.log(gateway.firewall.inspect(response));

    console.log("\nSTATELESS ACL RETURN TRAFFIC");
    console.log(gateway.networkACL.inspect(response));

    await saveAudit(gateway.auditRecords);

    // Automated verification.
    if (!results[0].allowed) {
        throw new Error("HTTPS traffic should be allowed");
    }

    if (results[1].allowed || results[2].allowed) {
        throw new Error("Unauthorized traffic was accepted");
    }

    if (!gateway.firewall.inspect(response).allowed) {
        throw new Error("Established return traffic was denied");
    }

    console.log("\nAll network security tests passed.");
}

main().catch(error => {
    console.error("Network security processing failed:", error.message);
    process.exitCode = 1;
});
