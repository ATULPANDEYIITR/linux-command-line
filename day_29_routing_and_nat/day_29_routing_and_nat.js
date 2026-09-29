/*
 * Routing and NAT
 *
 * This standalone JavaScript program demonstrates:
 * - IPv4 networks
 * - routing tables
 * - longest-prefix matching
 * - default gateways
 * - packet forwarding
 * - next-hop selection
 * - NAT/PAT
 * - stateful firewall behavior
 * - TTL
 * - route metrics
 * - route aggregation
 * - troubleshooting
 *
 * Run with:
 *     node routing_nat.js
 *
 * No external packages are required.
 */

"use strict";

// ============================================================================
// 1. IPv4 ADDRESS UTILITIES
// ============================================================================

function ipv4ToInteger(address) {
    const octets = address.split(".").map(Number);

    if (
        octets.length !== 4 ||
        octets.some(
            octet =>
                !Number.isInteger(octet) ||
                octet < 0 ||
                octet > 255
        )
    ) {
        throw new Error(`Invalid IPv4 address: ${address}`);
    }

    return (
        ((octets[0] << 24) >>> 0) +
        ((octets[1] << 16) >>> 0) +
        ((octets[2] << 8) >>> 0) +
        octets[3]
    ) >>> 0;
}

function integerToIPv4(value) {
    if (!Number.isInteger(value) || value < 0 || value > 0xFFFFFFFF) {
        throw new Error(`Invalid IPv4 integer: ${value}`);
    }

    return [
        (value >>> 24) & 255,
        (value >>> 16) & 255,
        (value >>> 8) & 255,
        value & 255
    ].join(".");
}

function prefixMask(prefixLength) {
    if (
        !Number.isInteger(prefixLength) ||
        prefixLength < 0 ||
        prefixLength > 32
    ) {
        throw new Error(`Invalid prefix length: ${prefixLength}`);
    }

    if (prefixLength === 0) {
        return 0;
    }

    return (0xFFFFFFFF << (32 - prefixLength)) >>> 0;
}

function networkAddress(address, prefixLength) {
    return (
        ipv4ToInteger(address) &
        prefixMask(prefixLength)
    ) >>> 0;
}

function cidrContains(cidr, address) {
    const [network, prefixText] = cidr.split("/");
    const prefixLength = Number(prefixText);

    const mask = prefixMask(prefixLength);
    const target = ipv4ToInteger(address);
    const networkValue = networkAddress(network, prefixLength);

    return (target & mask) >>> 0 === networkValue;
}

function normalizeCIDR(cidr) {
    const [network, prefixText] = cidr.split("/");
    const prefixLength = Number(prefixText);

    return `${integerToIPv4(networkAddress(network, prefixLength))}/${prefixLength}`;
}


// ============================================================================
// 2. BASIC NETWORK EXAMPLES
// ============================================================================

function demonstrateIPv4Basics() {
    console.log("\n" + "=".repeat(78));
    console.log("1. IPv4 BASICS");
    console.log("=".repeat(78));

    const examples = [
        "192.168.1.10",
        "10.0.0.25",
        "172.16.10.50",
        "8.8.8.8"
    ];

    for (const address of examples) {
        console.log(
            `${address.padEnd(16)} -> ${ipv4ToInteger(address)}`
        );
    }

    const cidr = "192.168.10.0/24";

    console.log(`\nNetwork: ${cidr}`);
    console.log(
        `192.168.10.50 belongs to network: ${
            cidrContains(cidr, "192.168.10.50")
        }`
    );

    console.log(
        `192.168.11.50 belongs to network: ${
            cidrContains(cidr, "192.168.11.50")
        }`
    );
}


// ============================================================================
// 3. ROUTE CLASS
// ============================================================================

class Route {
    constructor({
        destination,
        nextHop = null,
        interfaceName,
        metric = 1,
        administrativeDistance = 0,
        source = "connected"
    }) {
        this.destination = normalizeCIDR(destination);
        this.nextHop = nextHop;
        this.interfaceName = interfaceName;
        this.metric = metric;
        this.administrativeDistance = administrativeDistance;
        this.source = source;

        const [, prefix] = this.destination.split("/");
        this.prefixLength = Number(prefix);
    }

    matches(address) {
        return cidrContains(this.destination, address);
    }
}


// ============================================================================
// 4. ROUTING TABLE
// ============================================================================

class RoutingTable {
    constructor() {
        this.routes = [];
    }

    addRoute(route) {
        this.routes.push(route);
    }

    lookup(destination) {
        const matchingRoutes = this.routes.filter(
            route => route.matches(destination)
        );

        if (matchingRoutes.length === 0) {
            return null;
        }

        // Longest-prefix matching is the central routing decision.
        // The route with the greatest prefix length is the most specific.
        matchingRoutes.sort((a, b) => {
            if (a.prefixLength !== b.prefixLength) {
                return b.prefixLength - a.prefixLength;
            }

            if (
                a.administrativeDistance !==
                b.administrativeDistance
            ) {
                return (
                    a.administrativeDistance -
                    b.administrativeDistance
                );
            }

            return a.metric - b.metric;
        });

        return matchingRoutes[0];
    }

    display() {
        console.log(
            "Destination".padEnd(22) +
            "Next Hop".padEnd(18) +
            "Interface".padEnd(14) +
            "Metric".padEnd(9) +
            "Source"
        );

        console.log("-".repeat(78));

        for (const route of this.routes) {
            console.log(
                route.destination.padEnd(22) +
                String(route.nextHop ?? "direct").padEnd(18) +
                route.interfaceName.padEnd(14) +
                String(route.metric).padEnd(9) +
                route.source
            );
        }
    }
}


function demonstrateRoutingTable() {
    console.log("\n" + "=".repeat(78));
    console.log("2. ROUTING TABLE AND LONGEST-PREFIX MATCHING");
    console.log("=".repeat(78));

    const table = new RoutingTable();

    table.addRoute(
        new Route({
            destination: "0.0.0.0/0",
            nextHop: "192.168.1.1",
            interfaceName: "WAN",
            metric: 100,
            source: "static-default"
        })
    );

    table.addRoute(
        new Route({
            destination: "10.0.0.0/8",
            nextHop: "192.168.1.2",
            interfaceName: "CORE",
            metric: 20,
            source: "static"
        })
    );

    table.addRoute(
        new Route({
            destination: "10.20.0.0/16",
            nextHop: "192.168.1.3",
            interfaceName: "CORE",
            metric: 10,
            source: "static"
        })
    );

    table.addRoute(
        new Route({
            destination: "10.20.30.0/24",
            nextHop: "192.168.1.4",
            interfaceName: "CORE",
            metric: 5,
            source: "static"
        })
    );

    table.display();

    const destinations = [
        "10.20.30.55",
        "10.20.99.10",
        "10.99.10.10",
        "172.16.1.10"
    ];

    console.log("\nLookups:");

    for (const destination of destinations) {
        const route = table.lookup(destination);

        if (route) {
            console.log(
                `${destination} -> ${route.destination}, ` +
                `next-hop=${route.nextHop ?? destination}, ` +
                `interface=${route.interfaceName}`
            );
        } else {
            console.log(`${destination} -> NO ROUTE`);
        }
    }
}


// ============================================================================
// 5. ROUTER
// ============================================================================

class Router {
    constructor(name) {
        this.name = name;
        this.interfaces = new Map();
        this.routingTable = new RoutingTable();
    }

    addInterface(name, address, prefixLength) {
        this.interfaces.set(name, address);

        const network = normalizeCIDR(
            `${address}/${prefixLength}`
        );

        this.routingTable.addRoute(
            new Route({
                destination: network,
                nextHop: null,
                interfaceName: name,
                metric: 0,
                source: "connected"
            })
        );
    }

    addStaticRoute(
        destination,
        nextHop,
        interfaceName,
        metric = 1
    ) {
        this.routingTable.addRoute(
            new Route({
                destination,
                nextHop,
                interfaceName,
                metric,
                source: "static"
            })
        );
    }

    addDefaultRoute(nextHop, interfaceName, metric = 1) {
        this.addStaticRoute(
            "0.0.0.0/0",
            nextHop,
            interfaceName,
            metric
        );
    }

    forward(packet) {
        packet.history.push(this.name);

        if (packet.ttl <= 1) {
            throw new Error(
                `${this.name}: TTL expired`
            );
        }

        packet.ttl -= 1;

        return this.routingTable.lookup(
            packet.destinationIp
        );
    }
}


// ============================================================================
// 6. PACKET
// ============================================================================

class Packet {
    constructor({
        sourceIp,
        destinationIp,
        protocol = "TCP",
        sourcePort = null,
        destinationPort = null,
        ttl = 64,
        payloadSize = 100
    }) {
        this.sourceIp = sourceIp;
        this.destinationIp = destinationIp;
        this.protocol = protocol;
        this.sourcePort = sourcePort;
        this.destinationPort = destinationPort;
        this.ttl = ttl;
        this.payloadSize = payloadSize;
        this.history = [];
    }

    describe() {
        const portText =
            this.sourcePort !== null &&
            this.destinationPort !== null
                ? `:${this.sourcePort} -> :${this.destinationPort}`
                : "";

        return (
            `${this.sourceIp}${portText} -> ` +
            `${this.destinationIp} ` +
            `${this.protocol} TTL=${this.ttl}`
        );
    }
}


function demonstratePacketForwarding() {
    console.log("\n" + "=".repeat(78));
    console.log("3. PACKET FORWARDING");
    console.log("=".repeat(78));

    const router = new Router("EDGE");

    router.addInterface("LAN", "192.168.1.1", 24);
    router.addInterface("WAN", "203.0.113.2", 30);

    router.addStaticRoute(
        "10.50.0.0/16",
        "203.0.113.1",
        "WAN"
    );

    const packet = new Packet({
        sourceIp: "192.168.1.50",
        destinationIp: "10.50.20.10",
        sourcePort: 51000,
        destinationPort: 443
    });

    console.log(packet.describe());

    const route = router.forward(packet);

    if (route) {
        console.log(
            `Selected ${route.destination}, ` +
            `forward through ${route.interfaceName}, ` +
            `next-hop=${route.nextHop}, TTL=${packet.ttl}`
        );
    } else {
        console.log("NO ROUTE");
    }
}


// ============================================================================
// 7. DEFAULT GATEWAY
// ============================================================================

function demonstrateDefaultGateway() {
    console.log("\n" + "=".repeat(78));
    console.log("4. DEFAULT GATEWAY");
    console.log("=".repeat(78));

    const host = {
        address: "192.168.10.25",
        network: "192.168.10.0/24",
        gateway: "192.168.10.1"
    };

    const destinations = [
        "192.168.10.100",
        "8.8.8.8"
    ];

    for (const destination of destinations) {
        if (cidrContains(host.network, destination)) {
            console.log(
                `${destination}: send directly on local network`
            );
        } else {
            console.log(
                `${destination}: send to default gateway ${host.gateway}`
            );
        }
    }
}


// ============================================================================
// 8. INTERNET GATEWAY
// ============================================================================

class InternetGateway extends Router {
    constructor(name, publicIp) {
        super(name);
        this.publicIp = publicIp;
    }

    describe() {
        console.log(
            `${this.name}: public-facing address ${this.publicIp}`
        );
    }
}


function demonstrateInternetGateway() {
    console.log("\n" + "=".repeat(78));
    console.log("5. INTERNET GATEWAY");
    console.log("=".repeat(78));

    const gateway = new InternetGateway(
        "INTERNET-GW",
        "198.51.100.10"
    );

    gateway.addInterface("LAN", "192.168.50.1", 24);
    gateway.addInterface("WAN", "198.51.100.10", 24);

    gateway.describe();

    console.log(
        "Private host -> gateway -> external network -> Internet"
    );
}


// ============================================================================
// 9. NAT/PAT
// ============================================================================

class NatTranslation {
    constructor({
        privateIp,
        privatePort,
        publicIp,
        publicPort,
        remoteIp,
        remotePort,
        protocol
    }) {
        Object.assign(this, {
            privateIp,
            privatePort,
            publicIp,
            publicPort,
            remoteIp,
            remotePort,
            protocol
        });
    }
}


class NatTable {
    constructor(publicIp, firstPort = 40000) {
        this.publicIp = publicIp;
        this.nextPort = firstPort;
        this.outbound = new Map();
        this.inbound = new Map();
    }

    allocatePort() {
        for (let attempts = 0; attempts < 20000; attempts++) {
            const candidate = this.nextPort++;

            if (this.nextPort > 60000) {
                this.nextPort = 40000;
            }

            const occupied = [...this.outbound.values()]
                .some(
                    translation =>
                        translation.publicPort === candidate
                );

            if (!occupied) {
                return candidate;
            }
        }

        throw new Error("NAT port pool exhausted");
    }

    createKey(
        privateIp,
        privatePort,
        remoteIp,
        remotePort,
        protocol
    ) {
        return [
            privateIp,
            privatePort,
            remoteIp,
            remotePort,
            protocol
        ].join("|");
    }

    translateOutbound({
        privateIp,
        privatePort,
        remoteIp,
        remotePort,
        protocol
    }) {
        const key = this.createKey(
            privateIp,
            privatePort,
            remoteIp,
            remotePort,
            protocol
        );

        if (this.outbound.has(key)) {
            return this.outbound.get(key);
        }

        const publicPort = this.allocatePort();

        const translation = new NatTranslation({
            privateIp,
            privatePort,
            publicIp: this.publicIp,
            publicPort,
            remoteIp,
            remotePort,
            protocol
        });

        this.outbound.set(key, translation);

        const reverseKey = [
            this.publicIp,
            publicPort,
            protocol
        ].join("|");

        this.inbound.set(reverseKey, translation);

        return translation;
    }

    translateInbound({
        publicPort,
        destinationIp,
        protocol
    }) {
        const key = [
            destinationIp,
            publicPort,
            protocol
        ].join("|");

        return this.inbound.get(key) ?? null;
    }

    display() {
        console.log(
            "Private".padEnd(25) +
            "Public".padEnd(25) +
            "Remote".padEnd(25) +
            "Protocol"
        );

        console.log("-".repeat(85));

        for (const translation of this.outbound.values()) {
            const privateEndpoint =
                `${translation.privateIp}:${translation.privatePort}`;

            const publicEndpoint =
                `${translation.publicIp}:${translation.publicPort}`;

            const remoteEndpoint =
                `${translation.remoteIp}:${translation.remotePort}`;

            console.log(
                privateEndpoint.padEnd(25) +
                publicEndpoint.padEnd(25) +
                remoteEndpoint.padEnd(25) +
                translation.protocol
            );
        }
    }
}


function demonstrateNat() {
    console.log("\n" + "=".repeat(78));
    console.log("6. NAT AND PAT");
    console.log("=".repeat(78));

    const nat = new NatTable("203.0.113.10");

    const translation = nat.translateOutbound({
        privateIp: "192.168.1.20",
        privatePort: 51500,
        remoteIp: "93.184.216.34",
        remotePort: 443,
        protocol: "TCP"
    });

    console.log(
        `Private endpoint: ` +
        `${translation.privateIp}:${translation.privatePort}`
    );

    console.log(
        `Translated endpoint: ` +
        `${translation.publicIp}:${translation.publicPort}`
    );

    console.log(
        `Remote endpoint: ` +
        `${translation.remoteIp}:${translation.remotePort}`
    );

    nat.display();

    const reverse = nat.translateInbound({
        publicPort: translation.publicPort,
        destinationIp: translation.publicIp,
        protocol: "TCP"
    });

    console.log(
        reverse
            ? `Return traffic restored to ${reverse.privateIp}:${reverse.privatePort}`
            : "No NAT state for return traffic"
    );
}


// ============================================================================
// 10. STATEFUL FIREWALL
// ============================================================================

class StatefulFirewall {
    constructor() {
        this.connections = new Set();
    }

    key({
        sourceIp,
        sourcePort,
        destinationIp,
        destinationPort,
        protocol
    }) {
        return [
            sourceIp,
            sourcePort,
            destinationIp,
            destinationPort,
            protocol
        ].join("|");
    }

    allowOutbound(connection) {
        this.connections.add(
            this.key(connection)
        );

        return true;
    }

    allowInbound(connection) {
        const reverseKey = this.key({
            sourceIp: connection.destinationIp,
            sourcePort: connection.destinationPort,
            destinationIp: connection.sourceIp,
            destinationPort: connection.sourcePort,
            protocol: connection.protocol
        });

        return this.connections.has(reverseKey);
    }
}


function demonstrateStatefulFirewall() {
    console.log("\n" + "=".repeat(78));
    console.log("7. STATEFUL FIREWALL");
    console.log("=".repeat(78));

    const firewall = new StatefulFirewall();

    const outbound = {
        sourceIp: "192.168.1.20",
        sourcePort: 50000,
        destinationIp: "93.184.216.34",
        destinationPort: 443,
        protocol: "TCP"
    };

    console.log(
        `Outbound allowed: ${firewall.allowOutbound(outbound)}`
    );

    console.log(
        `Matching response allowed: ${
            firewall.allowInbound({
                sourceIp: "93.184.216.34",
                sourcePort: 443,
                destinationIp: "192.168.1.20",
                destinationPort: 50000,
                protocol: "TCP"
            })
        }`
    );

    console.log(
        `Unsolicited traffic allowed: ${
            firewall.allowInbound({
                sourceIp: "203.0.113.90",
                sourcePort: 9999,
                destinationIp: "192.168.1.20",
                destinationPort: 50000,
                protocol: "TCP"
            })
        }`
    );
}


// ============================================================================
// 11. NEIGHBOR CACHE
// ============================================================================

class NeighborCache {
    constructor() {
        this.entries = new Map();
    }

    learn(ip, macAddress) {
        this.entries.set(ip, macAddress);
    }

    resolve(ip) {
        return this.entries.get(ip) ?? null;
    }
}


function demonstrateNeighborResolution() {
    console.log("\n" + "=".repeat(78));
    console.log("8. NEXT-HOP / ARP-LIKE RESOLUTION");
    console.log("=".repeat(78));

    const neighbors = new NeighborCache();

    neighbors.learn(
        "192.168.1.1",
        "02:00:00:00:01:01"
    );

    const nextHop = "192.168.1.1";
    const mac = neighbors.resolve(nextHop);

    console.log(
        `${nextHop} -> ${mac ?? "not resolved"}`
    );
}


// ============================================================================
// 12. ROUTE METRICS
// ============================================================================

function chooseRoute(routes) {
    return routes
        .slice()
        .sort((a, b) => {
            if (
                a.administrativeDistance !==
                b.administrativeDistance
            ) {
                return (
                    a.administrativeDistance -
                    b.administrativeDistance
                );
            }

            return a.metric - b.metric;
        })[0];
}


function demonstrateRouteMetrics() {
    console.log("\n" + "=".repeat(78));
    console.log("9. ROUTE METRICS");
    console.log("=".repeat(78));

    const routes = [
        new Route({
            destination: "10.50.0.0/16",
            nextHop: "192.168.1.1",
            interfaceName: "OSPF-1",
            metric: 20,
            administrativeDistance: 110,
            source: "OSPF"
        }),
        new Route({
            destination: "10.50.0.0/16",
            nextHop: "192.168.2.1",
            interfaceName: "OSPF-2",
            metric: 5,
            administrativeDistance: 110,
            source: "OSPF"
        }),
        new Route({
            destination: "10.50.0.0/16",
            nextHop: "192.168.3.1",
            interfaceName: "RIP",
            metric: 1,
            administrativeDistance: 120,
            source: "RIP"
        })
    ];

    const selected = chooseRoute(routes);

    for (const route of routes) {
        console.log(
            `${route.source}: AD=${route.administrativeDistance}, ` +
            `metric=${route.metric}, next-hop=${route.nextHop}`
        );
    }

    console.log(
        `Selected route: ${selected.source} via ${selected.nextHop}`
    );
}


// ============================================================================
// 13. TTL AND ROUTING LOOPS
// ============================================================================

function demonstrateTtl() {
    console.log("\n" + "=".repeat(78));
    console.log("10. TTL");
    console.log("=".repeat(78));

    const packet = new Packet({
        sourceIp: "10.0.0.10",
        destinationIp: "10.0.0.20",
        ttl: 4
    });

    for (let hop = 1; hop <= 6; hop++) {
        if (packet.ttl <= 1) {
            console.log(
                `Hop ${hop}: packet discarded because TTL would expire`
            );
            break;
        }

        packet.ttl -= 1;

        console.log(
            `Hop ${hop}: forwarded, TTL=${packet.ttl}`
        );
    }
}


// ============================================================================
// 14. ROUTE AGGREGATION
// ============================================================================

function demonstrateAggregation() {
    console.log("\n" + "=".repeat(78));
    console.log("11. ROUTE AGGREGATION");
    console.log("=".repeat(78));

    const routes = [
        "10.10.0.0/24",
        "10.10.1.0/24",
        "10.10.2.0/24",
        "10.10.3.0/24"
    ];

    console.log("Specific routes:");

    for (const route of routes) {
        console.log(`  ${route}`);
    }

    console.log(
        "\nThese four /24 networks can be represented by " +
        "the aggregate 10.10.0.0/22 when the addressing plan allows it."
    );
}


// ============================================================================
// 15. COMPLETE ENTERPRISE SIMULATION
// ============================================================================

class EnterpriseNetwork {
    constructor() {
        this.edge = new Router("EDGE");
        this.core = new Router("CORE");
        this.nat = new NatTable("198.51.100.10");
        this.firewall = new StatefulFirewall();

        this.configure();
    }

    configure() {
        this.edge.addInterface(
            "LAN",
            "192.168.50.1",
            24
        );

        this.edge.addInterface(
            "TRANSIT",
            "10.0.0.1",
            30
        );

        this.core.addInterface(
            "TRANSIT",
            "10.0.0.2",
            30
        );

        this.core.addInterface(
            "WAN",
            "198.51.100.1",
            30
        );

        this.edge.addDefaultRoute(
            "10.0.0.2",
            "TRANSIT"
        );

        this.core.addStaticRoute(
            "192.168.50.0/24",
            "10.0.0.1",
            "TRANSIT"
        );
    }

    sendToInternet({
        sourceIp,
        sourcePort,
        destinationIp,
        destinationPort
    }) {
        const packet = new Packet({
            sourceIp,
            sourcePort,
            destinationIp,
            destinationPort,
            protocol: "TCP"
        });

        console.log("\nClient:");
        console.log(`  ${packet.describe()}`);

        const edgeRoute = this.edge.forward(packet);

        if (!edgeRoute) {
            throw new Error("EDGE: no route");
        }

        console.log(
            `EDGE -> ${edgeRoute.interfaceName}, ` +
            `next-hop=${edgeRoute.nextHop}`
        );

        const coreRoute = this.core.forward(packet);

        if (!coreRoute) {
            throw new Error("CORE: no route");
        }

        console.log(
            `CORE -> ${coreRoute.interfaceName}, ` +
            `next-hop=${coreRoute.nextHop}`
        );

        const connection = {
            sourceIp,
            sourcePort,
            destinationIp,
            destinationPort,
            protocol: "TCP"
        };

        if (!this.firewall.allowOutbound(connection)) {
            throw new Error("Firewall denied outbound connection");
        }

        const translation = this.nat.translateOutbound({
            privateIp: sourceIp,
            privatePort: sourcePort,
            remoteIp: destinationIp,
            remotePort: destinationPort,
            protocol: "TCP"
        });

        console.log(
            `NAT: ${translation.privateIp}:${translation.privatePort}` +
            ` -> ${translation.publicIp}:${translation.publicPort}`
        );

        console.log(
            `Internet server sees ` +
            `${translation.publicIp}:${translation.publicPort}`
        );

        const returnTranslation = this.nat.translateInbound({
            publicPort: translation.publicPort,
            destinationIp: translation.publicIp,
            protocol: "TCP"
        });

        if (!returnTranslation) {
            throw new Error("Return traffic has no NAT state");
        }

        const allowed = this.firewall.allowInbound({
            sourceIp: returnTranslation.remoteIp,
            sourcePort: returnTranslation.remotePort,
            destinationIp: returnTranslation.privateIp,
            destinationPort: returnTranslation.privatePort,
            protocol: returnTranslation.protocol
        });

        console.log(
            `Return traffic -> ` +
            `${returnTranslation.privateIp}:${returnTranslation.privatePort}`
        );

        console.log(
            `Stateful firewall return decision: ${allowed}`
        );
    }
}


function demonstrateEnterpriseNetwork() {
    console.log("\n" + "=".repeat(78));
    console.log("12. COMPLETE ENTERPRISE NETWORK");
    console.log("=".repeat(78));

    const network = new EnterpriseNetwork();

    network.sendToInternet({
        sourceIp: "192.168.50.25",
        sourcePort: 51500,
        destinationIp: "93.184.216.34",
        destinationPort: 443
    });
}


// ============================================================================
// 16. ERROR HANDLING AND EDGE CASES
// ============================================================================

function demonstrateEdgeCases() {
    console.log("\n" + "=".repeat(78));
    console.log("13. EDGE CASES");
    console.log("=".repeat(78));

    const tests = [
        {
            name: "Invalid IPv4 address",
            action: () => ipv4ToInteger("300.1.2.3")
        },
        {
            name: "Invalid prefix",
            action: () => prefixMask(33)
        },
        {
            name: "No route",
            action: () => {
                const table = new RoutingTable();
                return table.lookup("8.8.8.8");
            }
        }
    ];

    for (const test of tests) {
        try {
            const result = test.action();

            if (result === null) {
                console.log(`${test.name}: handled safely -> no route`);
            } else {
                console.log(`${test.name}: result=${result}`);
            }
        } catch (error) {
            console.log(
                `${test.name}: handled error -> ${error.message}`
            );
        }
    }
}


// ============================================================================
// 17. PERFORMANCE DISCUSSION THROUGH A SMALL EXPERIMENT
// ============================================================================

function performanceExperiment() {
    console.log("\n" + "=".repeat(78));
    console.log("14. ROUTING LOOKUP PERFORMANCE CONCEPT");
    console.log("=".repeat(78));

    const table = new RoutingTable();

    for (let prefix = 0; prefix <= 24; prefix++) {
        const network = prefix === 0
            ? "0.0.0.0/0"
            : `10.0.0.0/${prefix}`;

        table.addRoute(
            new Route({
                destination: network,
                nextHop: "192.168.1.1",
                interfaceName: "CORE",
                metric: prefix
            })
        );
    }

    const start = process.hrtime.bigint();

    let matches = 0;

    for (let i = 0; i < 10000; i++) {
        if (table.lookup("10.20.30.40")) {
            matches++;
        }
    }

    const elapsedNanoseconds =
        process.hrtime.bigint() - start;

    console.log(`Lookups: ${matches}`);
    console.log(
        `Elapsed: ${Number(elapsedNanoseconds) / 1e6} ms`
    );

    console.log(
        "This intentionally simple implementation scans routes. " +
        "Production routers use optimized forwarding structures."
    );
}


// ============================================================================
// 18. TROUBLESHOOTING
// ============================================================================

function printTroubleshootingChecklist() {
    console.log("\n" + "=".repeat(78));
    console.log("15. TROUBLESHOOTING CHECKLIST");
    console.log("=".repeat(78));

    const checklist = [
        "Verify the source IP and prefix length.",
        "Verify the default gateway.",
        "Test reachability of the local gateway.",
        "Inspect router interface state.",
        "Inspect the routing table.",
        "Confirm longest-prefix route selection.",
        "Verify next-hop reachability.",
        "Verify neighbor/MAC resolution.",
        "Inspect ACL and firewall policy.",
        "Inspect NAT/PAT state.",
        "Verify the return path.",
        "Check TTL and possible routing loops.",
        "Check MTU and fragmentation-related failures.",
        "Check routing-protocol state when dynamic routing is used.",
        "Use packet captures and logs when available."
    ];

    checklist.forEach(
        (item, index) => console.log(`${index + 1}. ${item}`)
    );
}


// ============================================================================
// 19. TESTS
// ============================================================================

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}


function testIPv4Conversion() {
    const address = "192.168.1.10";
    assert(
        integerToIPv4(ipv4ToInteger(address)) === address,
        "IPv4 conversion should be reversible"
    );
}


function testLongestPrefix() {
    const table = new RoutingTable();

    table.addRoute(
        new Route({
            destination: "0.0.0.0/0",
            nextHop: "192.168.1.1",
            interfaceName: "WAN"
        })
    );

    table.addRoute(
        new Route({
            destination: "10.0.0.0/8",
            nextHop: "192.168.1.2",
            interfaceName: "CORE"
        })
    );

    table.addRoute(
        new Route({
            destination: "10.20.0.0/16",
            nextHop: "192.168.1.3",
            interfaceName: "CORE"
        })
    );

    const route = table.lookup("10.20.30.40");

    assert(
        route.destination === "10.20.0.0/16",
        "Most specific route must win"
    );
}


function testDefaultRoute() {
    const table = new RoutingTable();

    table.addRoute(
        new Route({
            destination: "0.0.0.0/0",
            nextHop: "192.168.1.1",
            interfaceName: "WAN"
        })
    );

    const route = table.lookup("8.8.8.8");

    assert(
        route !== null &&
        route.destination === "0.0.0.0/0",
        "Default route should match external destination"
    );
}


function testNatRoundTrip() {
    const nat = new NatTable("203.0.113.10");

    const translation = nat.translateOutbound({
        privateIp: "192.168.1.10",
        privatePort: 50000,
        remoteIp: "93.184.216.34",
        remotePort: 443,
        protocol: "TCP"
    });

    const reverse = nat.translateInbound({
        publicPort: translation.publicPort,
        destinationIp: "203.0.113.10",
        protocol: "TCP"
    });

    assert(
        reverse !== null,
        "NAT state must support reverse lookup"
    );

    assert(
        reverse.privateIp === "192.168.1.10",
        "Private address must be restored"
    );

    assert(
        reverse.privatePort === 50000,
        "Private port must be restored"
    );
}


function testTtl() {
    const router = new Router("TEST");

    router.addInterface(
        "LAN",
        "10.0.0.1",
        24
    );

    const packet = new Packet({
        sourceIp: "10.0.0.10",
        destinationIp: "8.8.8.8",
        ttl: 1
    });

    let failed = false;

    try {
        router.forward(packet);
    } catch (error) {
        failed = error.message.includes("TTL expired");
    }

    assert(
        failed,
        "TTL expiration should be detected"
    );
}


function runTests() {
    console.log("\n" + "=".repeat(78));
    console.log("16. AUTOMATED TESTS");
    console.log("=".repeat(78));

    const tests = [
        testIPv4Conversion,
        testLongestPrefix,
        testDefaultRoute,
        testNatRoundTrip,
        testTtl
    ];

    let passed = 0;

    for (const test of tests) {
        try {
            test();
            console.log(`PASS  ${test.name}`);
            passed++;
        } catch (error) {
            console.log(
                `FAIL  ${test.name}: ${error.message}`
            );
        }
    }

    console.log(
        `\n${passed}/${tests.length} tests passed.`
    );
}


// ============================================================================
// 20. MAIN
// ============================================================================

function main() {
    console.log("=".repeat(78));
    console.log("ROUTING AND NAT: JAVASCRIPT STUDY PROGRAM");
    console.log("=".repeat(78));

    demonstrateIPv4Basics();
    demonstrateRoutingTable();
    demonstratePacketForwarding();
    demonstrateDefaultGateway();
    demonstrateInternetGateway();
    demonstrateNat();
    demonstrateStatefulFirewall();
    demonstrateNeighborResolution();
    demonstrateRouteMetrics();
    demonstrateTtl();
    demonstrateAggregation();
    demonstrateEnterpriseNetwork();
    demonstrateEdgeCases();
    performanceExperiment();
    printTroubleshootingChecklist();
    runTests();

    console.log("\n" + "=".repeat(78));
    console.log("END OF ROUTING AND NAT JAVASCRIPT PROGRAM");
    console.log("=".repeat(78));
}


main();
