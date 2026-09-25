/*
 * IPv4 Subnetting and CIDR
 *
 * Self-contained JavaScript study implementation.
 *
 * Demonstrates:
 * - IPv4 binary representation
 * - CIDR prefix lengths
 * - Subnet masks
 * - Wildcard masks
 * - Network and broadcast addresses
 * - Host calculations
 * - Equal-size subnetting
 * - VLSM planning
 * - Network membership
 * - Overlap detection
 * - Route summarization
 * - Longest-prefix matching
 * - Validation
 * - /31 and /32 edge cases
 *
 * Run with:
 *   node subnetting.js
 *
 * No external packages are required.
 */

"use strict";

// -----------------------------------------------------------------------------
// SECTION 1: IPv4 CONVERSION
// -----------------------------------------------------------------------------

function assertIntegerRange(value, minimum, maximum, description) {
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
        throw new Error(`${description} must be an integer between ${minimum} and ${maximum}.`);
    }
}

function parseIPv4(address) {
    if (typeof address !== "string") {
        throw new Error("IPv4 address must be a string.");
    }

    const parts = address.split(".");

    if (parts.length !== 4) {
        throw new Error(`Invalid IPv4 address: ${address}`);
    }

    const octets = parts.map((part) => {
        if (!/^\d+$/.test(part)) {
            throw new Error(`Invalid IPv4 octet: ${part}`);
        }

        const value = Number(part);

        if (!Number.isInteger(value) || value < 0 || value > 255) {
            throw new Error(`IPv4 octet out of range: ${part}`);
        }

        return value;
    });

    return octets;
}

function ipv4ToInteger(address) {
    const [a, b, c, d] = parseIPv4(address);

    // JavaScript bitwise operators use signed 32-bit integers.
    // >>> 0 converts the result into an unsigned 32-bit representation.
    return (((a * 256 + b) * 256 + c) * 256 + d) >>> 0;
}

function integerToIPv4(value) {
    assertIntegerRange(value, 0, 0xFFFFFFFF, "IPv4 integer");

    const a = Math.floor(value / 16777216) % 256;
    const b = Math.floor(value / 65536) % 256;
    const c = Math.floor(value / 256) % 256;
    const d = value % 256;

    return `${a}.${b}.${c}.${d}`;
}

function ipv4ToBinary(address) {
    return parseIPv4(address)
        .map((octet) => octet.toString(2).padStart(8, "0"))
        .join(".");
}


// -----------------------------------------------------------------------------
// SECTION 2: CIDR MASK OPERATIONS
// -----------------------------------------------------------------------------

function prefixToMaskInteger(prefix) {
    assertIntegerRange(prefix, 0, 32, "CIDR prefix");

    if (prefix === 0) {
        return 0;
    }

    return (0xFFFFFFFF * (2 ** prefix) / (2 ** 32)) >>> 0;
}

function prefixToMask(prefix) {
    return integerToIPv4(prefixToMaskInteger(prefix));
}

function prefixToWildcard(prefix) {
    const mask = prefixToMaskInteger(prefix);
    return integerToIPv4((~mask) >>> 0);
}

function totalAddresses(prefix) {
    assertIntegerRange(prefix, 0, 32, "CIDR prefix");
    return 2 ** (32 - prefix);
}

function traditionalUsableHosts(prefix) {
    if (prefix >= 31) {
        return 0;
    }

    return totalAddresses(prefix) - 2;
}

function parseCIDR(cidr) {
    if (typeof cidr !== "string") {
        throw new Error("CIDR must be a string.");
    }

    const parts = cidr.split("/");

    if (parts.length !== 2) {
        throw new Error(`Invalid CIDR notation: ${cidr}`);
    }

    const address = parts[0];
    const prefix = Number(parts[1]);

    parseIPv4(address);
    assertIntegerRange(prefix, 0, 32, "CIDR prefix");

    return {
        address,
        prefix
    };
}


// -----------------------------------------------------------------------------
// SECTION 3: NETWORK CALCULATION
// -----------------------------------------------------------------------------

function networkAddress(address, prefix) {
    const ip = ipv4ToInteger(address);
    const mask = prefixToMaskInteger(prefix);

    // Fundamental subnetting rule:
    // network = IP AND subnet mask
    return integerToIPv4((ip & mask) >>> 0);
}

function broadcastAddress(address, prefix) {
    const network = ipv4ToInteger(networkAddress(address, prefix));
    const mask = prefixToMaskInteger(prefix);

    // Broadcast = network OR inverse subnet mask
    return integerToIPv4((network | ((~mask) >>> 0)) >>> 0);
}

function calculateSubnet(cidr) {
    const { address, prefix } = parseCIDR(cidr);

    const network = networkAddress(address, prefix);
    const broadcast = broadcastAddress(address, prefix);
    const total = totalAddresses(prefix);

    let firstUsable;
    let lastUsable;
    let usableHosts;

    if (prefix <= 30) {
        firstUsable = integerToIPv4(ipv4ToInteger(network) + 1);
        lastUsable = integerToIPv4(ipv4ToInteger(broadcast) - 1);
        usableHosts = total - 2;
    } else if (prefix === 31) {
        // /31 is useful for point-to-point links where network/broadcast
        // reservation is not applied in the traditional way.
        firstUsable = network;
        lastUsable = broadcast;
        usableHosts = 2;
    } else {
        // /32 identifies exactly one IPv4 address.
        firstUsable = network;
        lastUsable = network;
        usableHosts = 1;
    }

    return {
        input: cidr,
        network,
        prefix,
        mask: prefixToMask(prefix),
        wildcard: prefixToWildcard(prefix),
        broadcast,
        firstUsable,
        lastUsable,
        totalAddresses: total,
        usableHosts
    };
}

function displaySubnet(cidr) {
    const result = calculateSubnet(cidr);

    console.log(`\nCIDR:             ${result.input}`);
    console.log(`Network:          ${result.network}`);
    console.log(`Prefix:           /${result.prefix}`);
    console.log(`Subnet mask:      ${result.mask}`);
    console.log(`Wildcard mask:    ${result.wildcard}`);
    console.log(`Broadcast:        ${result.broadcast}`);
    console.log(`First usable:     ${result.firstUsable}`);
    console.log(`Last usable:      ${result.lastUsable}`);
    console.log(`Total addresses:  ${result.totalAddresses}`);
    console.log(`Usable hosts:     ${result.usableHosts}`);
}


// -----------------------------------------------------------------------------
// SECTION 4: MEMBERSHIP
// -----------------------------------------------------------------------------

function ipBelongsToSubnet(address, cidr) {
    const { prefix } = parseCIDR(cidr);
    const network = ipv4ToInteger(networkAddress(address, prefix));
    const ip = ipv4ToInteger(address);

    return ip === (ipv4ToInteger(networkAddress(address, prefix)))
        ? true
        : (() => {
            const mask = prefixToMaskInteger(prefix);
            return (ip & mask) >>> 0 === network;
        })();
}


// -----------------------------------------------------------------------------
// SECTION 5: EQUAL-SIZE SUBNETTING
// -----------------------------------------------------------------------------

function splitNetwork(cidr, newPrefix) {
    const parsed = parseCIDR(cidr);

    if (newPrefix < parsed.prefix) {
        throw new Error("New prefix cannot be shorter than the parent prefix.");
    }

    const parentNetwork = ipv4ToInteger(
        networkAddress(parsed.address, parsed.prefix)
    );

    const childCount = 2 ** (newPrefix - parsed.prefix);
    const childSize = totalAddresses(newPrefix);

    const children = [];

    for (let index = 0; index < childCount; index += 1) {
        const childNetwork = parentNetwork + index * childSize;
        children.push(`${integerToIPv4(childNetwork)}/${newPrefix}`);
    }

    return children;
}


// -----------------------------------------------------------------------------
// SECTION 6: HOST REQUIREMENTS
// -----------------------------------------------------------------------------

function minimumPrefixForHosts(requiredHosts) {
    if (!Number.isInteger(requiredHosts) || requiredHosts < 1) {
        throw new Error("Required hosts must be a positive integer.");
    }

    for (let prefix = 30; prefix >= 0; prefix -= 1) {
        if (traditionalUsableHosts(prefix) >= requiredHosts) {
            return prefix;
        }
    }

    throw new Error("No IPv4 subnet can satisfy this requirement.");
}


// -----------------------------------------------------------------------------
// SECTION 7: NETWORK OVERLAP
// -----------------------------------------------------------------------------

function cidrRange(cidr) {
    const result = calculateSubnet(cidr);

    return {
        network: ipv4ToInteger(result.network),
        broadcast: ipv4ToInteger(result.broadcast)
    };
}

function networksOverlap(firstCIDR, secondCIDR) {
    const first = cidrRange(firstCIDR);
    const second = cidrRange(secondCIDR);

    return first.network <= second.broadcast &&
           second.network <= first.broadcast;
}

function findOverlaps(networks) {
    const overlaps = [];

    for (let i = 0; i < networks.length; i += 1) {
        for (let j = i + 1; j < networks.length; j += 1) {
            if (networksOverlap(networks[i], networks[j])) {
                overlaps.push([networks[i], networks[j]]);
            }
        }
    }

    return overlaps;
}


// -----------------------------------------------------------------------------
// SECTION 8: LONGEST PREFIX MATCH
// -----------------------------------------------------------------------------

function longestPrefixMatch(address, routes) {
    const ip = ipv4ToInteger(address);
    const matchingRoutes = [];

    for (const route of routes) {
        const parsed = parseCIDR(route);
        const network = ipv4ToInteger(networkAddress(parsed.address, parsed.prefix));
        const mask = prefixToMaskInteger(parsed.prefix);

        if (((ip & mask) >>> 0) === network) {
            matchingRoutes.push({
                route,
                prefix: parsed.prefix
            });
        }
    }

    if (matchingRoutes.length === 0) {
        return null;
    }

    matchingRoutes.sort((a, b) => b.prefix - a.prefix);

    return matchingRoutes[0].route;
}


// -----------------------------------------------------------------------------
// SECTION 9: ADDRESS-RANGE SUMMARIZATION
// -----------------------------------------------------------------------------

function commonPrefixLength(firstInteger, secondInteger) {
    let xor = (firstInteger ^ secondInteger) >>> 0;
    let count = 0;

    while (xor !== 0) {
        xor = (xor << 1) >>> 0;
        count += 1;
    }

    return 32 - count;
}

function summarizeAddressRange(firstAddress, lastAddress) {
    let start = ipv4ToInteger(firstAddress);
    const end = ipv4ToInteger(lastAddress);

    if (start > end) {
        throw new Error("First address must not exceed last address.");
    }

    const summaries = [];

    while (start <= end) {
        let largestBlockPrefix = 32;

        // The block must be aligned at start and must not exceed end.
        while (largestBlockPrefix > 0) {
            const size = 2 ** (32 - largestBlockPrefix);
            const aligned = start % size === 0;
            const blockEnd = start + size - 1;

            if (aligned && blockEnd <= end) {
                break;
            }

            largestBlockPrefix -= 1;
        }

        summaries.push(`${integerToIPv4(start)}/${largestBlockPrefix}`);
        start += 2 ** (32 - largestBlockPrefix);
    }

    return summaries;
}


// -----------------------------------------------------------------------------
// SECTION 10: VLSM
// -----------------------------------------------------------------------------

function allocateVLSM(parentCIDR, requirements) {
    const parent = calculateSubnet(parentCIDR);
    const parentStart = ipv4ToInteger(parent.network);
    const parentEnd = ipv4ToInteger(parent.broadcast);

    const sorted = [...requirements].sort(
        (a, b) => b.hostsRequired - a.hostsRequired
    );

    const assignments = [];
    let current = parentStart;

    for (const requirement of sorted) {
        if (!Number.isInteger(requirement.hostsRequired) ||
            requirement.hostsRequired < 1) {
            throw new Error(`Invalid host requirement for ${requirement.name}.`);
        }

        const prefix = minimumPrefixForHosts(requirement.hostsRequired);
        const blockSize = totalAddresses(prefix);

        // Align the block to a valid subnet boundary.
        const remainder = current % blockSize;

        if (remainder !== 0) {
            current += blockSize - remainder;
        }

        const candidateEnd = current + blockSize - 1;

        if (candidateEnd > parentEnd) {
            throw new Error(
                `Requirement '${requirement.name}' does not fit inside ${parentCIDR}.`
            );
        }

        const cidr = `${integerToIPv4(current)}/${prefix}`;

        assignments.push({
            name: requirement.name,
            purpose: requirement.purpose,
            hostsRequired: requirement.hostsRequired,
            cidr,
            usableHosts: traditionalUsableHosts(prefix),
            firstHost: integerToIPv4(current + 1),
            lastHost: integerToIPv4(candidateEnd - 1)
        });

        current = candidateEnd + 1;
    }

    return assignments;
}


// -----------------------------------------------------------------------------
// SECTION 11: DEMONSTRATIONS
// -----------------------------------------------------------------------------

function demonstrateFundamentals() {
    console.log("\n" + "=".repeat(78));
    console.log("IPv4 BINARY AND CIDR FUNDAMENTALS");
    console.log("=".repeat(78));

    const addresses = [
        "10.0.0.1",
        "172.16.10.20",
        "192.168.1.100",
        "255.255.255.255"
    ];

    for (const address of addresses) {
        console.log(`${address.padEnd(18)} ${ipv4ToBinary(address)}`);
    }

    console.log("\nPrefix table:");

    const prefixes = [8, 16, 20, 24, 25, 26, 27, 28, 30, 31, 32];

    for (const prefix of prefixes) {
        console.log(
            `/${String(prefix).padEnd(2)} ` +
            `${prefixToMask(prefix).padEnd(18)} ` +
            `addresses=${String(totalAddresses(prefix)).padStart(10)} ` +
            `traditionalHosts=${String(traditionalUsableHosts(prefix)).padStart(10)}`
        );
    }
}

function demonstrateSubnetting() {
    console.log("\n" + "=".repeat(78));
    console.log("EQUAL-SIZE SUBNETTING");
    console.log("=".repeat(78));

    const parent = "192.168.10.0/24";

    for (const prefix of [25, 26, 27, 28]) {
        const subnets = splitNetwork(parent, prefix);

        console.log(`\n${parent} -> /${prefix}`);

        for (const subnet of subnets) {
            console.log(`  ${subnet}`);
        }
    }
}

function demonstrateHostPlanning() {
    console.log("\n" + "=".repeat(78));
    console.log("HOST REQUIREMENT PLANNING");
    console.log("=".repeat(78));

    for (const required of [2, 6, 14, 30, 50, 100, 200, 500]) {
        const prefix = minimumPrefixForHosts(required);

        console.log(
            `Need ${String(required).padStart(4)} hosts -> ` +
            `/${prefix} -> ${prefixToMask(prefix)} -> ` +
            `${traditionalUsableHosts(prefix)} traditional usable hosts`
        );
    }
}

function demonstrateMembership() {
    console.log("\n" + "=".repeat(78));
    console.log("SUBNET MEMBERSHIP");
    console.log("=".repeat(78));

    const tests = [
        ["192.168.1.10", "192.168.1.0/24"],
        ["192.168.2.10", "192.168.1.0/24"],
        ["10.20.30.40", "10.0.0.0/8"],
        ["172.31.20.1", "172.16.0.0/12"]
    ];

    for (const [address, cidr] of tests) {
        console.log(
            `${address.padEnd(18)} in ${cidr.padEnd(18)} -> ` +
            `${ipBelongsToSubnet(address, cidr)}`
        );
    }
}

function demonstrateVLSM() {
    console.log("\n" + "=".repeat(78));
    console.log("VLSM NETWORK DESIGN");
    console.log("=".repeat(78));

    const requirements = [
        {
            name: "Engineering",
            purpose: "Application development",
            hostsRequired: 60
        },
        {
            name: "Operations",
            purpose: "Operations systems",
            hostsRequired: 30
        },
        {
            name: "Management",
            purpose: "Management systems",
            hostsRequired: 12
        },
        {
            name: "Security",
            purpose: "Security infrastructure",
            hostsRequired: 6
        }
    ];

    const assignments = allocateVLSM("192.168.50.0/24", requirements);

    for (const assignment of assignments) {
        console.log(
            `${assignment.name.padEnd(16)} ` +
            `${assignment.cidr.padEnd(18)} ` +
            `usable=${String(assignment.usableHosts).padStart(3)} ` +
            `${assignment.firstHost}-${assignment.lastHost}`
        );
    }
}

function demonstrateRouting() {
    console.log("\n" + "=".repeat(78));
    console.log("LONGEST PREFIX MATCH");
    console.log("=".repeat(78));

    const routes = [
        "0.0.0.0/0",
        "10.0.0.0/8",
        "10.20.0.0/16",
        "10.20.30.0/24"
    ];

    for (const address of [
        "8.8.8.8",
        "10.50.1.1",
        "10.20.40.1",
        "10.20.30.77"
    ]) {
        console.log(
            `${address.padEnd(18)} -> ${longestPrefixMatch(address, routes)}`
        );
    }
}

function demonstrateSummarization() {
    console.log("\n" + "=".repeat(78));
    console.log("ROUTE SUMMARIZATION");
    console.log("=".repeat(78));

    const summary = summarizeAddressRange(
        "192.168.0.0",
        "192.168.3.255"
    );

    console.log("192.168.0.0 through 192.168.3.255:");

    for (const route of summary) {
        console.log(`  ${route}`);
    }
}

function demonstrateOverlapDetection() {
    console.log("\n" + "=".repeat(78));
    console.log("NETWORK OVERLAP VALIDATION");
    console.log("=".repeat(78));

    const networks = [
        "10.0.0.0/24",
        "10.0.1.0/24",
        "10.0.0.128/25",
        "10.0.2.0/24"
    ];

    const overlaps = findOverlaps(networks);

    if (overlaps.length === 0) {
        console.log("No overlaps detected.");
    } else {
        for (const [first, second] of overlaps) {
            console.log(`Overlap: ${first} <-> ${second}`);
        }
    }
}

function demonstrateEdgeCases() {
    console.log("\n" + "=".repeat(78));
    console.log("CIDR EDGE CASES");
    console.log("=".repeat(78));

    for (const cidr of [
        "0.0.0.0/0",
        "192.168.1.0/30",
        "192.168.1.0/31",
        "192.168.1.50/32"
    ]) {
        displaySubnet(cidr);
    }
}


// -----------------------------------------------------------------------------
// SECTION 12: ERROR HANDLING
// -----------------------------------------------------------------------------

function demonstrateValidation() {
    console.log("\n" + "=".repeat(78));
    console.log("VALIDATION AND ERROR HANDLING");
    console.log("=".repeat(78));

    const invalidValues = [
        "192.168.1.256/24",
        "192.168.1.0/33",
        "192.168.1.0/24/10",
        "abc.def.1.2/24"
    ];

    for (const value of invalidValues) {
        try {
            calculateSubnet(value);
            console.log(`${value}: unexpectedly accepted`);
        } catch (error) {
            console.log(`${value}: rejected -> ${error.message}`);
        }
    }
}


// -----------------------------------------------------------------------------
// SECTION 13: MAIN
// -----------------------------------------------------------------------------

function main() {
    console.log("IPv4 SUBNETTING AND CIDR COMPLETE JAVASCRIPT STUDY PROGRAM");

    demonstrateFundamentals();
    demonstrateSubnetting();
    demonstrateHostPlanning();
    demonstrateMembership();
    demonstrateVLSM();
    demonstrateRouting();
    demonstrateSummarization();
    demonstrateOverlapDetection();
    demonstrateEdgeCases();
    demonstrateValidation();

    console.log("\n" + "=".repeat(78));
    console.log("INTERACTIVE-STYLE CALCULATIONS");
    console.log("=".repeat(78));

    displaySubnet("192.168.10.77/26");

    console.log("\nPoint-to-point /31:");
    displaySubnet("10.0.0.0/31");

    console.log("\nHost route /32:");
    displaySubnet("10.0.0.25/32");
}

main();
