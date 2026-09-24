"use strict";

/*
 * IP Addressing: IPv4, IPv6, Public IPs, Private IPs, and Address Allocation
 *
 * Self-contained JavaScript study program.
 *
 * Demonstrates:
 * - IPv4 binary representation
 * - IPv4 CIDR and subnet calculations
 * - Public/private/special IPv4 ranges
 * - Network membership
 * - VLSM-style allocation
 * - DHCP-style lease allocation
 * - Simplified NAT/PAT
 * - IPv6 parsing and compression
 * - IPv6 categories
 * - IPv6 subnetting
 * - IPv4 versus IPv6
 * - Validation
 * - Security and design considerations
 *
 * No external npm packages are required.
 */

// ---------------------------------------------------------------------------
// 1. General utilities
// ---------------------------------------------------------------------------

function printTitle(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function assertCondition(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function ipv4ToInteger(address) {
    const parts = address.split(".");

    if (parts.length !== 4) {
        throw new Error("IPv4 address must contain four octets.");
    }

    let result = 0;

    for (const part of parts) {
        if (!/^\d+$/.test(part)) {
            throw new Error(`Invalid IPv4 octet: ${part}`);
        }

        const value = Number(part);

        if (value < 0 || value > 255) {
            throw new Error(`IPv4 octet out of range: ${part}`);
        }

        result = result * 256 + value;
    }

    return result;
}

function integerToIPv4(value) {
    if (!Number.isInteger(value) || value < 0 || value > 0xffffffff) {
        throw new Error("IPv4 integer must be between 0 and 2^32 - 1.");
    }

    return [
        Math.floor(value / 0x1000000) % 256,
        Math.floor(value / 0x10000) % 256,
        Math.floor(value / 0x100) % 256,
        value % 256
    ].join(".");
}

function ipv4ToBinary(address) {
    return address
        .split(".")
        .map(octet => Number(octet).toString(2).padStart(8, "0"))
        .join(".");
}

function prefixToMask(prefixLength) {
    if (!Number.isInteger(prefixLength) || prefixLength < 0 || prefixLength > 32) {
        throw new Error("IPv4 prefix length must be between 0 and 32.");
    }

    if (prefixLength === 0) {
        return 0;
    }

    return Math.floor(0xffffffff - 2 ** (32 - prefixLength) + 1);
}

function networkFromCidr(cidr) {
    const [addressText, prefixText] = cidr.split("/");

    if (prefixText === undefined) {
        throw new Error("CIDR must contain a prefix length.");
    }

    const prefixLength = Number(prefixText);

    if (!Number.isInteger(prefixLength) || prefixLength < 0 || prefixLength > 32) {
        throw new Error("Invalid IPv4 prefix length.");
    }

    const address = ipv4ToInteger(addressText);
    const mask = prefixToMask(prefixLength);
    const network = address & mask;

    return {
        cidr,
        prefixLength,
        address,
        network: network >>> 0,
        mask: mask >>> 0,
        broadcast: (network | (~mask >>> 0)) >>> 0,
        totalAddresses: 2 ** (32 - prefixLength)
    };
}

function cidrDetails(cidr) {
    const result = networkFromCidr(cidr);
    const firstHost =
        result.totalAddresses >= 2
            ? result.network + 1
            : result.network;

    const lastHost =
        result.totalAddresses >= 2
            ? result.broadcast - 1
            : result.broadcast;

    return {
        ...result,
        networkAddress: integerToIPv4(result.network),
        broadcastAddress: integerToIPv4(result.broadcast),
        firstHost: integerToIPv4(firstHost),
        lastHost: integerToIPv4(lastHost),
        maskAddress: integerToIPv4(result.mask >>> 0),
        usableHosts:
            result.prefixLength <= 30
                ? Math.max(result.totalAddresses - 2, 0)
                : result.prefixLength === 31
                    ? 2
                    : 1
    };
}

function ipInNetwork(address, cidr) {
    const addressInteger = ipv4ToInteger(address);
    const network = networkFromCidr(cidr);

    return (
        (addressInteger & network.mask) >>> 0
        === network.network
    );
}

// ---------------------------------------------------------------------------
// 2. IPv4 fundamentals
// ---------------------------------------------------------------------------

function demonstrateIPv4Fundamentals() {
    printTitle("1. IPV4 FUNDAMENTALS");

    const address = "192.168.10.25";

    console.log(`Address: ${address}`);
    console.log(`Binary:  ${ipv4ToBinary(address)}`);
    console.log(`Integer: ${ipv4ToInteger(address)}`);

    console.log("\nOctets:");

    address.split(".").forEach((octet, index) => {
        console.log(
            `  Octet ${index + 1}: ${octet.padStart(3, " ")} = ` +
            `${Number(octet).toString(2).padStart(8, "0")}`
        );
    });

    console.log(
        "\nIPv4 has 32 bits, normally divided into four 8-bit octets."
    );
}

// ---------------------------------------------------------------------------
// 3. IPv4 subnetting
// ---------------------------------------------------------------------------

function demonstrateIPv4Subnetting() {
    printTitle("2. IPV4 CIDR AND SUBNETTING");

    const examples = [
        "192.168.1.0/24",
        "192.168.1.0/26",
        "10.20.0.0/20",
        "192.168.1.10/32"
    ];

    for (const cidr of examples) {
        const details = cidrDetails(cidr);

        console.log(`\nCIDR:              ${cidr}`);
        console.log(`Network:           ${details.networkAddress}`);
        console.log(`Prefix:            /${details.prefixLength}`);
        console.log(`Subnet mask:       ${details.maskAddress}`);
        console.log(`Broadcast:         ${details.broadcastAddress}`);
        console.log(`Total addresses:   ${details.totalAddresses}`);
        console.log(`Usable host count: ${details.usableHosts}`);
        console.log(`First host:        ${details.firstHost}`);
        console.log(`Last host:         ${details.lastHost}`);
    }

    console.log(
        "\nCIDR describes how many leading bits form the network prefix."
    );
}

// ---------------------------------------------------------------------------
// 4. IPv4 special ranges
// ---------------------------------------------------------------------------

function addressInRange(address, cidr) {
    return ipInNetwork(address, cidr);
}

function classifyIPv4(address) {
    ipv4ToInteger(address);

    const classifications = [];

    const ranges = [
        ["private RFC 1918", "10.0.0.0/8"],
        ["private RFC 1918", "172.16.0.0/12"],
        ["private RFC 1918", "192.168.0.0/16"],
        ["loopback", "127.0.0.0/8"],
        ["link-local", "169.254.0.0/16"],
        ["multicast", "224.0.0.0/4"],
        ["shared address space", "100.64.0.0/10"],
        ["documentation", "192.0.2.0/24"],
        ["documentation", "198.51.100.0/24"],
        ["documentation", "203.0.113.0/24"]
    ];

    for (const [name, range] of ranges) {
        if (addressInRange(address, range)) {
            classifications.push(name);
        }
    }

    if (classifications.length === 0) {
        classifications.push("ordinary IPv4 address");
    }

    return classifications;
}

function demonstrateIPv4Classification() {
    printTitle("3. IPV4 ADDRESS CLASSIFICATION");

    const examples = [
        "8.8.8.8",
        "10.1.2.3",
        "172.16.10.20",
        "192.168.1.50",
        "127.0.0.1",
        "169.254.10.10",
        "224.0.0.1",
        "100.64.1.10",
        "192.0.2.10",
        "203.0.113.10"
    ];

    for (const address of examples) {
        console.log(
            `${address.padEnd(16)} -> ${classifyIPv4(address).join(", ")}`
        );
    }

    console.log(
        "\nModern allocation uses CIDR rather than the old Class A/B/C model."
    );
}

// ---------------------------------------------------------------------------
// 5. Subnet generation
// ---------------------------------------------------------------------------

function generateIPv4Subnets(parentCidr, newPrefix) {
    const parent = networkFromCidr(parentCidr);

    if (newPrefix < parent.prefixLength || newPrefix > 32) {
        throw new Error("New prefix must be equal to or longer than parent prefix.");
    }

    const numberOfSubnets = 2 ** (newPrefix - parent.prefixLength);
    const subnetSize = 2 ** (32 - newPrefix);

    const subnets = [];

    for (let index = 0; index < numberOfSubnets; index++) {
        const network = parent.network + index * subnetSize;
        const broadcast = network + subnetSize - 1;

        subnets.push({
            network: integerToIPv4(network),
            broadcast: integerToIPv4(broadcast),
            cidr: `${integerToIPv4(network)}/${newPrefix}`,
            totalAddresses: subnetSize
        });
    }

    return subnets;
}

function demonstrateSubnetGeneration() {
    printTitle("4. GENERATING IPV4 SUBNETS");

    const subnets = generateIPv4Subnets("192.168.50.0/24", 26);

    for (const subnet of subnets) {
        console.log(
            `${subnet.cidr.padEnd(20)} ` +
            `network=${subnet.network.padEnd(16)} ` +
            `broadcast=${subnet.broadcast}`
        );
    }
}

// ---------------------------------------------------------------------------
// 6. VLSM allocation
// ---------------------------------------------------------------------------

function prefixForHosts(hostsRequired) {
    if (!Number.isInteger(hostsRequired) || hostsRequired < 1) {
        throw new Error("Host requirement must be a positive integer.");
    }

    for (let prefix = 30; prefix >= 0; prefix--) {
        const total = 2 ** (32 - prefix);
        const usable = total - 2;

        if (usable >= hostsRequired) {
            return prefix;
        }
    }

    throw new Error("Host requirement is too large.");
}

function allocateVLSM(baseCidr, requests) {
    const base = networkFromCidr(baseCidr);

    const sortedRequests = [...requests].sort(
        (a, b) => b.hostsRequired - a.hostsRequired
    );

    let cursor = base.network;
    const baseEnd = base.broadcast;

    const allocations = [];

    for (const request of sortedRequests) {
        const prefix = prefixForHosts(request.hostsRequired);
        const blockSize = 2 ** (32 - prefix);

        const remainder = cursor % blockSize;
        if (remainder !== 0) {
            cursor += blockSize - remainder;
        }

        const broadcast = cursor + blockSize - 1;

        if (broadcast > baseEnd) {
            throw new Error(
                `Insufficient address space for ${request.name}.`
            );
        }

        allocations.push({
            name: request.name,
            requestedHosts: request.hostsRequired,
            cidr: `${integerToIPv4(cursor)}/${prefix}`,
            network: integerToIPv4(cursor),
            broadcast: integerToIPv4(broadcast),
            usableHosts: blockSize - 2
        });

        cursor = broadcast + 1;
    }

    return allocations;
}

function demonstrateVLSM() {
    printTitle("5. VLSM ADDRESS ALLOCATION");

    const requests = [
        { name: "Engineering", hostsRequired: 100 },
        { name: "Operations", hostsRequired: 50 },
        { name: "Management", hostsRequired: 20 },
        { name: "Infrastructure", hostsRequired: 2 }
    ];

    const allocations = allocateVLSM("10.50.0.0/24", requests);

    for (const allocation of allocations) {
        console.log(
            `${allocation.name.padEnd(18)} ` +
            `${allocation.cidr.padEnd(18)} ` +
            `requested=${String(allocation.requestedHosts).padStart(3)} ` +
            `usable=${String(allocation.usableHosts).padStart(3)}`
        );
    }
}

// ---------------------------------------------------------------------------
// 7. Simplified DHCP pool
// ---------------------------------------------------------------------------

class DHCPPool {
    constructor(networkCidr, firstOffset, lastOffset) {
        const details = networkFromCidr(networkCidr);

        this.networkCidr = networkCidr;
        this.network = details.network;
        this.broadcast = details.broadcast;
        this.available = [];

        for (
            let value = this.network + firstOffset;
            value <= this.network + lastOffset;
            value++
        ) {
            if (value <= this.broadcast) {
                this.available.push(integerToIPv4(value));
            }
        }

        this.leases = new Map();
    }

    requestLease(clientId, currentTime, duration) {
        if (this.leases.has(clientId)) {
            const existing = this.leases.get(clientId);
            existing.expiresAt = currentTime + duration;
            return existing;
        }

        const used = new Set(
            [...this.leases.values()].map(lease => lease.address)
        );

        const freeAddress = this.available.find(
            address => !used.has(address)
        );

        if (!freeAddress) {
            throw new Error("DHCP pool exhausted.");
        }

        const lease = {
            clientId,
            address: freeAddress,
            expiresAt: currentTime + duration
        };

        this.leases.set(clientId, lease);
        return lease;
    }

    release(clientId) {
        this.leases.delete(clientId);
    }

    expire(currentTime) {
        for (const [clientId, lease] of this.leases.entries()) {
            if (lease.expiresAt <= currentTime) {
                this.leases.delete(clientId);
            }
        }
    }
}

function demonstrateDHCP() {
    printTitle("6. DHCP-STYLE ADDRESS ALLOCATION");

    const pool = new DHCPPool("192.168.100.0/24", 10, 13);

    for (const clientId of ["laptop-A", "laptop-B", "printer-A"]) {
        const lease = pool.requestLease(clientId, 1000, 3600);

        console.log(
            `${clientId.padEnd(12)} -> ${lease.address} ` +
            `expires=${lease.expiresAt}`
        );
    }

    pool.release("laptop-B");

    const replacement = pool.requestLease("phone-A", 1100, 3600);
    console.log(`phone-A      -> ${replacement.address}`);
}

// ---------------------------------------------------------------------------
// 8. NAT/PAT model
// ---------------------------------------------------------------------------

class NATTable {
    constructor(publicIp) {
        this.publicIp = publicIp;
        this.translations = new Map();
    }

    createTranslation(privateIp, privatePort, destinationIp, destinationPort) {
        if (!classifyIPv4(privateIp).some(
            item => item === "private RFC 1918"
        )) {
            throw new Error(
                "This educational NAT example expects an RFC 1918 private address."
            );
        }

        if (privatePort < 1 || privatePort > 65535) {
            throw new Error("Invalid private port.");
        }

        const publicPort = 40000 + this.translations.size;
        const key = `${privateIp}:${privatePort}:${destinationIp}:${destinationPort}`;

        const translation = {
            privateIp,
            privatePort,
            publicIp: this.publicIp,
            publicPort,
            destinationIp,
            destinationPort
        };

        this.translations.set(key, translation);
        return translation;
    }
}

function demonstrateNAT() {
    printTitle("7. NAT AND PAT");

    const nat = new NATTable("203.0.113.10");

    const translation = nat.createTranslation(
        "192.168.1.25",
        51515,
        "198.51.100.40",
        443
    );

    console.log(
        `${translation.privateIp}:${translation.privatePort}` +
        ` -> ${translation.publicIp}:${translation.publicPort}`
    );

    console.log(
        `Destination: ${translation.destinationIp}:${translation.destinationPort}`
    );

    console.log(
        "\nPAT allows multiple private flows to share one public IPv4 address."
    );
}

// ---------------------------------------------------------------------------
// 9. IPv6 parsing without external libraries
// ---------------------------------------------------------------------------

function expandIPv6(address) {
    address = address.trim().toLowerCase();

    if (!address) {
        throw new Error("IPv6 address cannot be empty.");
    }

    if ((address.match(/::/g) || []).length > 1) {
        throw new Error("IPv6 compression :: may appear only once.");
    }

    let groups;

    if (address.includes("::")) {
        const parts = address.split("::");

        const left = parts[0] ? parts[0].split(":") : [];
        const right = parts[1] ? parts[1].split(":") : [];

        if (left.some(group => group.length > 4) ||
            right.some(group => group.length > 4)) {
            throw new Error("IPv6 group contains more than four hexadecimal digits.");
        }

        const missing = 8 - left.length - right.length;

        if (missing < 1) {
            throw new Error("Invalid IPv6 compressed form.");
        }

        groups = [
            ...left,
            ...Array(missing).fill("0"),
            ...right
        ];
    } else {
        groups = address.split(":");

        if (groups.length !== 8) {
            throw new Error("Expanded IPv6 address must contain eight groups.");
        }
    }

    if (groups.length !== 8) {
        throw new Error("IPv6 address must represent eight 16-bit groups.");
    }

    for (const group of groups) {
        if (!/^[0-9a-f]{1,4}$/.test(group)) {
            throw new Error(`Invalid IPv6 group: ${group}`);
        }
    }

    return groups.map(group => group.padStart(4, "0"));
}

function compressIPv6(address) {
    const groups = expandIPv6(address);

    let bestStart = -1;
    let bestLength = 0;

    let currentStart = -1;
    let currentLength = 0;

    for (let index = 0; index <= groups.length; index++) {
        const isZero = index < groups.length && groups[index] === "0000";

        if (isZero) {
            if (currentStart === -1) {
                currentStart = index;
                currentLength = 1;
            } else {
                currentLength++;
            }
        } else {
            if (currentLength > bestLength && currentLength >= 2) {
                bestStart = currentStart;
                bestLength = currentLength;
            }

            currentStart = -1;
            currentLength = 0;
        }
    }

    const simplified = groups.map(group => group.replace(/^0+/, "") || "0");

    if (bestStart === -1) {
        return simplified.join(":");
    }

    const left = simplified.slice(0, bestStart).join(":");
    const right = simplified
        .slice(bestStart + bestLength)
        .join(":");

    if (!left && !right) {
        return "::";
    }

    if (!left) {
        return `::${right}`;
    }

    if (!right) {
        return `${left}::`;
    }

    return `${left}::${right}`;
}

function demonstrateIPv6() {
    printTitle("8. IPV6 ADDRESSING");

    const examples = [
        "2001:0db8:0000:0000:0000:ff00:0042:8329",
        "2001:db8::1",
        "::1",
        "fe80::1234",
        "fd12:3456:789a::1",
        "ff02::1",
        "::"
    ];

    for (const address of examples) {
        console.log(`\nInput:     ${address}`);
        console.log(`Expanded:  ${expandIPv6(address).join(":")}`);
        console.log(`Compressed: ${compressIPv6(address)}`);
    }

    console.log(
        "\nIPv6 uses 128 bits and hexadecimal groups to represent the address."
    );
}

// ---------------------------------------------------------------------------
// 10. IPv6 categories
// ---------------------------------------------------------------------------

function ipv6IsLoopback(address) {
    return compressIPv6(address) === "::1";
}

function ipv6IsUnspecified(address) {
    return compressIPv6(address) === "::";
}

function ipv6IsLinkLocal(address) {
    const groups = expandIPv6(address);
    return groups[0].startsWith("fe8") ||
        groups[0].startsWith("fe9") ||
        groups[0].startsWith("fea") ||
        groups[0].startsWith("feb");
}

function ipv6IsMulticast(address) {
    return expandIPv6(address)[0].startsWith("ff");
}

function ipv6IsUniqueLocal(address) {
    return expandIPv6(address)[0].startsWith("fc") ||
        expandIPv6(address)[0].startsWith("fd");
}

function classifyIPv6(address) {
    const classifications = [];

    if (ipv6IsLoopback(address)) {
        classifications.push("loopback");
    }

    if (ipv6IsUnspecified(address)) {
        classifications.push("unspecified");
    }

    if (ipv6IsLinkLocal(address)) {
        classifications.push("link-local");
    }

    if (ipv6IsMulticast(address)) {
        classifications.push("multicast");
    }

    if (ipv6IsUniqueLocal(address)) {
        classifications.push("unique-local");
    }

    if (expandIPv6(address)[0] === "2001") {
        const compressed = compressIPv6(address);

        if (
            compressed === "::1" ||
            compressed === "::"
        ) {
            return classifications;
        }

        classifications.push("2001:: address space");
    }

    if (classifications.length === 0) {
        classifications.push("ordinary or special-purpose IPv6 address");
    }

    return classifications;
}

function demonstrateIPv6Classification() {
    printTitle("9. IPV6 ADDRESS CATEGORIES");

    const examples = [
        "::1",
        "::",
        "fe80::1",
        "fd12:3456:789a::1",
        "fc00::1",
        "ff02::1",
        "2001:db8::1"
    ];

    for (const address of examples) {
        console.log(
            `${address.padEnd(28)} -> ${classifyIPv6(address).join(", ")}`
        );
    }
}

// ---------------------------------------------------------------------------
// 11. IPv6 subnet calculations using BigInt
// ---------------------------------------------------------------------------

function ipv6ToBigInt(address) {
    const groups = expandIPv6(address);
    let result = 0n;

    for (const group of groups) {
        result = (result << 16n) + BigInt(`0x${group}`);
    }

    return result;
}

function bigIntToIPv6(value) {
    if (value < 0n || value >= (1n << 128n)) {
        throw new Error("IPv6 integer out of range.");
    }

    const groups = [];

    for (let index = 0; index < 8; index++) {
        const shift = BigInt((7 - index) * 16);
        const group = Number((value >> shift) & 0xffffn);
        groups.push(group.toString(16).padStart(4, "0"));
    }

    return compressIPv6(groups.join(":"));
}

function ipv6Network(address, prefixLength) {
    if (
        !Number.isInteger(prefixLength) ||
        prefixLength < 0 ||
        prefixLength > 128
    ) {
        throw new Error("IPv6 prefix must be between 0 and 128.");
    }

    const value = ipv6ToBigInt(address);

    if (prefixLength === 0) {
        return 0n;
    }

    const hostBits = 128 - prefixLength;
    const mask = ((1n << 128n) - 1n) ^ ((1n << BigInt(hostBits)) - 1n);

    return value & mask;
}

function generateIPv6Subnets(parentAddress, parentPrefix, newPrefix) {
    if (newPrefix < parentPrefix || newPrefix > 128) {
        throw new Error("New prefix must be longer than or equal to parent prefix.");
    }

    const parentNetwork = ipv6Network(parentAddress, parentPrefix);
    const count = 2n ** BigInt(newPrefix - parentPrefix);

    const subnetSize = 2n ** BigInt(128 - newPrefix);

    const result = [];

    for (let index = 0n; index < count && index < 8n; index++) {
        const network = parentNetwork + index * subnetSize;

        result.push(
            `${bigIntToIPv6(network)}/${newPrefix}`
        );
    }

    return result;
}

function demonstrateIPv6Subnetting() {
    printTitle("10. IPV6 SUBNETTING");

    const subnets = generateIPv6Subnets(
        "2001:db8:abcd::",
        48,
        64
    );

    console.log("First eight /64 subnets:");
    for (const subnet of subnets) {
        console.log(`  ${subnet}`);
    }

    console.log(
        "\nA /48 contains 65,536 /64 subnets because 64 - 48 = 16 subnet bits."
    );
}

// ---------------------------------------------------------------------------
// 12. IPv4 versus IPv6
// ---------------------------------------------------------------------------

function compareIPv4IPv6() {
    printTitle("11. IPV4 VERSUS IPV6");

    const comparison = [
        ["Address size", "32 bits", "128 bits"],
        ["Notation", "Dotted decimal", "Colon-separated hexadecimal"],
        ["Broadcast", "Supported", "Not used"],
        ["Multicast", "224.0.0.0/4", "ff00::/8"],
        ["Loopback", "127.0.0.0/8", "::1"],
        ["Link-local", "169.254.0.0/16", "fe80::/10"],
        ["Private/internal", "RFC 1918", "Unique local fc00::/7"],
        ["Neighbor resolution", "ARP", "ICMPv6 Neighbor Discovery"],
        ["Configuration", "Static/DHCP", "Static/DHCPv6/SLAAC"]
    ];

    for (const [feature, ipv4, ipv6] of comparison) {
        console.log(
            `${feature.padEnd(24)} | IPv4: ${ipv4.padEnd(30)} | IPv6: ${ipv6}`
        );
    }
}

// ---------------------------------------------------------------------------
// 13. Validation
// ---------------------------------------------------------------------------

function validateIPv4(address) {
    try {
        const integer = ipv4ToInteger(address);

        return {
            valid: true,
            address: integerToIPv4(integer),
            integer
        };
    } catch (error) {
        return {
            valid: false,
            error: error.message
        };
    }
}

function demonstrateValidation() {
    printTitle("12. VALIDATION AND EDGE CASES");

    const values = [
        "192.168.1.1",
        "192.168.1.999",
        "10.0.0.1",
        "127.0.0.1",
        "0.0.0.0",
        "255.255.255.255",
        "192.168.1",
        "192.168.1.a",
        ""
    ];

    for (const value of values) {
        const result = validateIPv4(value);

        console.log(
            `${JSON.stringify(value).padEnd(22)} -> ` +
            `${result.valid ? `valid (${result.address})` : `invalid (${result.error})`}`
        );
    }
}

// ---------------------------------------------------------------------------
// 14. Address allocation calculations
// ---------------------------------------------------------------------------

function demonstrateCapacity() {
    printTitle("13. ADDRESS CAPACITY");

    console.log("IPv4:");

    for (const prefix of [8, 16, 24, 25, 26, 27, 30, 31, 32]) {
        const total = 2 ** (32 - prefix);

        console.log(
            `  /${String(prefix).padEnd(2)} -> ${total.toLocaleString()} addresses`
        );
    }

    console.log("\nIPv6:");

    for (const prefix of [32, 48, 56, 64, 96, 128]) {
        const total = 2n ** BigInt(128 - prefix);

        console.log(
            `  /${String(prefix).padEnd(3)} -> ${total.toString()} addresses`
        );
    }
}

// ---------------------------------------------------------------------------
// 15. Security considerations
// ---------------------------------------------------------------------------

function demonstrateSecurityConsiderations() {
    printTitle("14. SECURITY CONSIDERATIONS");

    const points = [
        "Private IP space is not an authentication mechanism.",
        "NAT should not be treated as a replacement for firewall policy.",
        "Validate addresses before using them in access-control decisions.",
        "Segment sensitive systems with appropriate network boundaries.",
        "Do not protect only IPv4 if IPv6 is enabled.",
        "Monitor unexpected address assignments and routing behavior.",
        "Use documentation ranges in examples rather than real production IPs.",
        "Combine network controls with identity, encryption, authentication, and logging."
    ];

    points.forEach((point, index) => {
        console.log(`${String(index + 1).padStart(2)}. ${point}`);
    });
}

// ---------------------------------------------------------------------------
// 16. Async demonstration
// ---------------------------------------------------------------------------

function simulateAddressProvisioning(clientId, address, delayMs = 100) {
    /*
     * The asynchronous example models an application receiving an address
     * assignment from a provisioning service. It does not implement DHCP.
     */
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            try {
                const validation = validateIPv4(address);

                if (!validation.valid) {
                    throw new Error(validation.error);
                }

                resolve({
                    clientId,
                    address: validation.address,
                    status: "allocated"
                });
            } catch (error) {
                reject(error);
            }
        }, delayMs);
    });
}

async function demonstrateAsyncProvisioning() {
    printTitle("15. ASYNCHRONOUS ADDRESS PROVISIONING");

    const requests = [
        ["device-A", "192.168.20.10"],
        ["device-B", "192.168.20.11"],
        ["device-C", "192.168.20.12"]
    ];

    const results = await Promise.all(
        requests.map(([clientId, address]) =>
            simulateAddressProvisioning(clientId, address)
        )
    );

    for (const result of results) {
        console.log(
            `${result.clientId.padEnd(10)} -> ${result.address} (${result.status})`
        );
    }
}

// ---------------------------------------------------------------------------
// 17. Self-tests
// ---------------------------------------------------------------------------

function runSelfTests() {
    printTitle("16. SELF-TESTS");

    assertCondition(
        ipv4ToInteger("0.0.0.0") === 0,
        "0.0.0.0 should map to integer zero"
    );

    assertCondition(
        integerToIPv4(0xffffffff) === "255.255.255.255",
        "maximum IPv4 integer conversion"
    );

    assertCondition(
        ipv4ToBinary("255.255.255.255") === "11111111.11111111.11111111.11111111",
        "IPv4 binary conversion"
    );

    assertCondition(
        cidrDetails("192.168.1.0/24").broadcastAddress === "192.168.1.255",
        "IPv4 broadcast calculation"
    );

    assertCondition(
        ipInNetwork("192.168.1.20", "192.168.1.0/24"),
        "IPv4 membership"
    );

    assertCondition(
        !ipInNetwork("192.168.2.20", "192.168.1.0/24"),
        "IPv4 non-membership"
    );

    assertCondition(
        compressIPv6("2001:0db8:0000:0000:0000:0000:0000:0001") === "2001:db8::1",
        "IPv6 compression"
    );

    assertCondition(
        expandIPv6("::1").join(":") === "0000:0000:0000:0000:0000:0000:0000:0001",
        "IPv6 expansion"
    );

    assertCondition(
        ipv6IsLoopback("::1"),
        "IPv6 loopback classification"
    );

    assertCondition(
        ipv6IsLinkLocal("fe80::1"),
        "IPv6 link-local classification"
    );

    assertCondition(
        ipv6IsMulticast("ff02::1"),
        "IPv6 multicast classification"
    );

    assertCondition(
        prefixForHosts(62) === 26,
        "IPv4 host capacity"
    );

    console.log("All JavaScript self-tests passed.");
}

// ---------------------------------------------------------------------------
// 18. Main
// ---------------------------------------------------------------------------

async function main() {
    printTitle("IP ADDRESSING STUDY PROGRAM");

    console.log(
        "IPv4, IPv6, public/private addressing, subnetting, and allocation."
    );

    demonstrateIPv4Fundamentals();
    demonstrateIPv4Subnetting();
    demonstrateIPv4Classification();
    demonstrateSubnetGeneration();
    demonstrateVLSM();
    demonstrateDHCP();
    demonstrateNAT();
    demonstrateIPv6();
    demonstrateIPv6Classification();
    demonstrateIPv6Subnetting();
    compareIPv4IPv6();
    demonstrateValidation();
    demonstrateCapacity();
    demonstrateSecurityConsiderations();
    await demonstrateAsyncProvisioning();
    runSelfTests();

    printTitle("END");
}

main().catch(error => {
    console.error(`Program error: ${error.message}`);
    process.exitCode = 1;
});
