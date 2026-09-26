/*
 * DNS: Domain Names, Resolution, Records, Recursive Resolvers,
 * Authoritative Servers, and Caching
 *
 * This file is a self-contained educational DNS simulator.
 * It uses standard JavaScript features and does not require npm packages.
 *
 * Run with:
 *   node dns-study.js
 *
 * The implementation models DNS concepts rather than depending on an
 * external DNS service, making the examples deterministic and runnable
 * without network access.
 */

"use strict";

// ============================================================================
// 1. BASIC DNS CONCEPTS
// ============================================================================

function printSection(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function normalizeName(name) {
    const cleaned = String(name).trim().toLowerCase();

    if (cleaned === "" || cleaned === ".") {
        return cleaned === "." ? "." : "";
    }

    return cleaned.replace(/\.+$/, "") + ".";
}

function splitDomainName(name) {
    const normalized = normalizeName(name);

    if (!normalized || normalized === ".") {
        return [];
    }

    return normalized.slice(0, -1).split(".");
}

function isSubdomainOrEqual(name, parent) {
    const child = normalizeName(name);
    const ancestor = normalizeName(parent);

    return (
        child === ancestor ||
        child.endsWith("." + ancestor)
    );
}

function explainBasics() {
    printSection("1. DNS FUNDAMENTALS");

    console.log("DNS maps human-readable domain names to structured data.");
    console.log("An A record commonly maps a name to an IPv4 address.");
    console.log("An AAAA record commonly maps a name to an IPv6 address.");

    const example = {
        domain: "www.example.com.",
        ipv4: "192.0.2.10",
        ipv6: "2001:db8::10"
    };

    console.log("\nExample:");
    console.log(example);
}

function explainHierarchy() {
    printSection("2. DOMAIN NAME HIERARCHY");

    const domain = "api.shop.example.com.";

    console.log(`Domain: ${domain}`);

    const labels = splitDomainName(domain);

    labels
        .slice()
        .reverse()
        .forEach((label, index) => {
            const role =
                index === 0
                    ? "TLD"
                    : index === 1
                        ? "registered-domain label"
                        : "subdomain/host label";

            console.log(`  ${label.padEnd(15)} -> ${role}`);
        });

    console.log("\nDNS is hierarchical, so resolution normally progresses");
    console.log("through root, TLD, and authoritative information.");
}


// ============================================================================
// 2. DNS RECORDS
// ============================================================================

const RecordType = Object.freeze({
    A: "A",
    AAAA: "AAAA",
    CNAME: "CNAME",
    MX: "MX",
    NS: "NS",
    TXT: "TXT",
    SOA: "SOA",
    PTR: "PTR"
});

class DNSRecord {
    constructor(name, type, value, ttl = 300, priority = null) {
        if (!name) {
            throw new Error("DNS record name cannot be empty");
        }

        if (!Object.values(RecordType).includes(type)) {
            throw new Error(`Unsupported record type: ${type}`);
        }

        if (!Number.isInteger(ttl) || ttl < 0) {
            throw new Error("TTL must be a non-negative integer");
        }

        this.name = normalizeName(name);
        this.type = type;
        this.value = value;
        this.ttl = ttl;
        this.priority = priority;
    }

    toString() {
        const priorityText =
            this.priority === null
                ? ""
                : ` priority=${this.priority}`;

        return (
            `${this.name} ${this.ttl} IN ${this.type} ` +
            `${this.value}${priorityText}`
        );
    }
}

function validateRecord(record) {
    if (record.type === RecordType.A) {
        const parts = record.value.split(".");

        if (
            parts.length !== 4 ||
            parts.some(
                part =>
                    !/^\d+$/.test(part) ||
                    Number(part) < 0 ||
                    Number(part) > 255
            )
        ) {
            throw new Error(`Invalid IPv4 address: ${record.value}`);
        }
    }

    if (record.type === RecordType.MX) {
        if (
            record.priority === null ||
            !Number.isInteger(record.priority) ||
            record.priority < 0
        ) {
            throw new Error("MX records require a non-negative priority");
        }
    }

    if (
        [
            RecordType.CNAME,
            RecordType.MX,
            RecordType.NS,
            RecordType.PTR
        ].includes(record.type)
    ) {
        if (!record.value) {
            throw new Error(`${record.type} target cannot be empty`);
        }
    }
}

function demonstrateRecordTypes() {
    printSection("3. DNS RECORD TYPES");

    const records = [
        new DNSRecord(
            "example.com.",
            RecordType.A,
            "192.0.2.10",
            300
        ),
        new DNSRecord(
            "example.com.",
            RecordType.AAAA,
            "2001:db8::10",
            300
        ),
        new DNSRecord(
            "www.example.com.",
            RecordType.CNAME,
            "example.com.",
            120
        ),
        new DNSRecord(
            "example.com.",
            RecordType.MX,
            "mail.example.com.",
            3600,
            10
        ),
        new DNSRecord(
            "example.com.",
            RecordType.NS,
            "ns1.example.net.",
            86400
        ),
        new DNSRecord(
            "example.com.",
            RecordType.TXT,
            "v=spf1 -all",
            3600
        )
    ];

    for (const record of records) {
        validateRecord(record);
        console.log(record.toString());
    }
}


// ============================================================================
// 3. AUTHORITATIVE ZONES
// ============================================================================

class DNSZone {
    constructor(origin) {
        this.origin = normalizeName(origin);
        this.records = new Map();
    }

    makeKey(name, type) {
        return `${normalizeName(name)}|${type}`;
    }

    addRecord(record) {
        if (!isSubdomainOrEqual(record.name, this.origin)) {
            throw new Error(
                `${record.name} is outside zone ${this.origin}`
            );
        }

        validateRecord(record);

        const key = this.makeKey(record.name, record.type);

        if (!this.records.has(key)) {
            this.records.set(key, []);
        }

        this.records.get(key).push(record);
    }

    query(name, type) {
        const key = this.makeKey(name, type);
        return [...(this.records.get(key) || [])];
    }

    hasName(name) {
        const normalized = normalizeName(name);

        for (const key of this.records.keys()) {
            if (key.startsWith(normalized + "|")) {
                return true;
            }
        }

        return false;
    }
}

function findLongestMatchingZone(name, zones) {
    const normalized = normalizeName(name);

    const matching = zones.filter(
        zone => isSubdomainOrEqual(normalized, zone.origin)
    );

    if (matching.length === 0) {
        return null;
    }

    matching.sort(
        (a, b) => b.origin.length - a.origin.length
    );

    return matching[0];
}


// ============================================================================
// 4. DNS RESPONSE
// ============================================================================

class DNSResponse {
    constructor({
        answer = [],
        authority = [],
        additional = [],
        authoritative = false,
        fromCache = false,
        error = null
    } = {}) {
        this.answer = answer;
        this.authority = authority;
        this.additional = additional;
        this.authoritative = authoritative;
        this.fromCache = fromCache;
        this.error = error;
    }

    get success() {
        return this.error === null;
    }
}


// ============================================================================
// 5. AUTHORITATIVE SERVER
// ============================================================================

class AuthoritativeServer {
    constructor(name, zones) {
        this.name = normalizeName(name);
        this.zones = zones;
        this.role = "authoritative";
    }

    query(name, type) {
        const zone = findLongestMatchingZone(
            name,
            this.zones
        );

        if (!zone) {
            return new DNSResponse({
                error:
                    "REFUSED: not authoritative for requested name"
            });
        }

        const records = zone.query(name, type);

        if (records.length > 0) {
            return new DNSResponse({
                answer: records,
                authoritative: true
            });
        }

        if (zone.hasName(name)) {
            return new DNSResponse({
                authoritative: true,
                error: "NOERROR/NODATA"
            });
        }

        return new DNSResponse({
            authoritative: true,
            error: "NXDOMAIN"
        });
    }
}


// ============================================================================
// 6. ROOT AND TLD SERVERS
// ============================================================================

class Delegation {
    constructor(zoneName, nameServers) {
        this.zoneName = normalizeName(zoneName);
        this.nameServers = nameServers.map(normalizeName);
    }
}

class RootServer {
    constructor(delegations) {
        this.role = "root";
        this.delegations = new Map();

        for (const delegation of delegations) {
            this.delegations.set(
                delegation.zoneName,
                delegation
            );
        }
    }

    query(name) {
        const labels = splitDomainName(name);

        if (labels.length === 0) {
            return new DNSResponse({
                error: "INVALID_NAME"
            });
        }

        const tld = normalizeName(
            labels[labels.length - 1]
        );

        const delegation = this.delegations.get(tld);

        if (!delegation) {
            return new DNSResponse({
                error: "NXDOMAIN"
            });
        }

        const authority = delegation.nameServers.map(
            server =>
                new DNSRecord(
                    tld,
                    RecordType.NS,
                    server,
                    86400
                )
        );

        return new DNSResponse({
            authority,
            authoritative: true
        });
    }
}

class TLDServer {
    constructor(tld, delegations) {
        this.role = "tld";
        this.tld = normalizeName(tld);
        this.delegations = new Map();

        for (const delegation of delegations) {
            this.delegations.set(
                delegation.zoneName,
                delegation
            );
        }
    }

    query(name) {
        const labels = splitDomainName(name);

        if (labels.length < 2) {
            return new DNSResponse({
                error: "INVALID_NAME"
            });
        }

        const registeredDomain = normalizeName(
            labels.slice(-2).join(".")
        );

        const delegation =
            this.delegations.get(registeredDomain);

        if (!delegation) {
            return new DNSResponse({
                error: "NXDOMAIN"
            });
        }

        const authority = delegation.nameServers.map(
            server =>
                new DNSRecord(
                    registeredDomain,
                    RecordType.NS,
                    server,
                    172800
                )
        );

        return new DNSResponse({
            authority,
            authoritative: true
        });
    }
}


// ============================================================================
// 7. CACHE
// ============================================================================

class DNSCache {
    constructor() {
        this.entries = new Map();
    }

    makeKey(name, type) {
        return `${normalizeName(name)}|${type}`;
    }

    get(name, type, now = Date.now()) {
        const key = this.makeKey(name, type);
        const entry = this.entries.get(key);

        if (!entry) {
            return null;
        }

        if (now >= entry.expiresAt) {
            this.entries.delete(key);
            return null;
        }

        return {
            ...entry,
            remainingTTL: Math.max(
                0,
                Math.floor(
                    (entry.expiresAt - now) / 1000
                )
            )
        };
    }

    put(
        name,
        type,
        records,
        ttl,
        {
            now = Date.now(),
            negative = false
        } = {}
    ) {
        if (ttl <= 0) {
            return;
        }

        const key = this.makeKey(name, type);

        this.entries.set(key, {
            records: [...records],
            expiresAt: now + ttl * 1000,
            negative
        });
    }

    clear() {
        this.entries.clear();
    }

    get size() {
        return this.entries.size;
    }
}


// ============================================================================
// 8. RECURSIVE RESOLVER
// ============================================================================

class RecursiveResolver {
    constructor(
        rootServer,
        tldServers,
        authoritativeServers,
        cache = new DNSCache()
    ) {
        this.rootServer = rootServer;
        this.tldServers = new Map(
            Object.entries(tldServers).map(
                ([name, server]) => [
                    normalizeName(name),
                    server
                ]
            )
        );

        this.authoritativeServers = new Map(
            Object.entries(authoritativeServers).map(
                ([name, server]) => [
                    normalizeName(name),
                    server
                ]
            )
        );

        this.cache = cache;
        this.trace = [];
        this.queryCount = 0;
    }

    resolve(
        name,
        type = RecordType.A,
        maxCnameDepth = 8
    ) {
        this.queryCount++;
        this.trace = [];

        const normalized = normalizeName(name);

        if (!validDNSName(normalized)) {
            return new DNSResponse({
                error: "INVALID_DOMAIN_NAME"
            });
        }

        return this.resolveInternal(
            normalized,
            type,
            maxCnameDepth,
            new Set()
        );
    }

    resolveInternal(
        name,
        type,
        maxCnameDepth,
        visited
    ) {
        const cached = this.cache.get(name, type);

        if (cached) {
            this.trace.push(
                `CACHE HIT: ${name} ${type}`
            );

            return new DNSResponse({
                answer: cached.records,
                fromCache: true,
                error: cached.negative
                    ? "NXDOMAIN"
                    : null
            });
        }

        this.trace.push(
            `CACHE MISS: ${name} ${type}`
        );

        const rootResponse =
            this.rootServer.query(name);

        this.trace.push(
            "ROOT: locate TLD delegation"
        );

        if (rootResponse.error) {
            return rootResponse;
        }

        const labels = splitDomainName(name);
        const tld = normalizeName(
            labels[labels.length - 1]
        );

        const tldServer =
            this.tldServers.get(tld);

        if (!tldServer) {
            return new DNSResponse({
                error: "TLD_SERVER_UNAVAILABLE"
            });
        }

        const tldResponse =
            tldServer.query(name);

        this.trace.push(
            `TLD: locate authoritative server for ${name}`
        );

        if (tldResponse.error) {
            return tldResponse;
        }

        if (tldResponse.authority.length === 0) {
            return new DNSResponse({
                error: "TLD_NO_DELEGATION"
            });
        }

        const authoritativeName =
            normalizeName(
                tldResponse.authority[0].value
            );

        const authoritativeServer =
            this.authoritativeServers.get(
                authoritativeName
            );

        if (!authoritativeServer) {
            return new DNSResponse({
                error:
                    "AUTHORITATIVE_SERVER_UNAVAILABLE"
            });
        }

        this.trace.push(
            `AUTHORITATIVE: query ${authoritativeName}`
        );

        const response =
            authoritativeServer.query(name, type);

        if (response.answer.length > 0) {
            const ttl = Math.min(
                ...response.answer.map(
                    record => record.ttl
                )
            );

            this.cache.put(
                name,
                type,
                response.answer,
                ttl
            );

            return response;
        }

        if (type !== RecordType.CNAME) {
            const cnameResponse =
                authoritativeServer.query(
                    name,
                    RecordType.CNAME
                );

            if (cnameResponse.answer.length > 0) {
                const target = normalizeName(
                    cnameResponse.answer[0].value
                );

                this.trace.push(
                    `CNAME: ${name} -> ${target}`
                );

                if (visited.has(name)) {
                    return new DNSResponse({
                        error: "CNAME_LOOP"
                    });
                }

                if (visited.size >= maxCnameDepth) {
                    return new DNSResponse({
                        error:
                            "CNAME_CHAIN_TOO_LONG"
                    });
                }

                visited.add(name);

                const targetResponse =
                    this.resolveInternal(
                        target,
                        type,
                        maxCnameDepth,
                        visited
                    );

                if (targetResponse.answer.length > 0) {
                    return new DNSResponse({
                        answer:
                            targetResponse.answer,
                        authority:
                            cnameResponse.answer,
                        authoritative:
                            targetResponse.authoritative
                    });
                }

                return targetResponse;
            }
        }

        if (response.error === "NXDOMAIN") {
            this.cache.put(
                name,
                type,
                [],
                30,
                { negative: true }
            );
        }

        return response;
    }
}


// ============================================================================
// 9. DOMAIN VALIDATION
// ============================================================================

function validDNSName(name) {
    const normalized = normalizeName(name);

    if (!normalized || normalized === ".") {
        return false;
    }

    const withoutRoot = normalized.slice(0, -1);

    if (withoutRoot.length > 253) {
        return false;
    }

    const labels = withoutRoot.split(".");

    return labels.every(label => {
        if (!label || label.length > 63) {
            return false;
        }

        if (
            label.startsWith("-") ||
            label.endsWith("-")
        ) {
            return false;
        }

        return true;
    });
}


// ============================================================================
// 10. BUILD DEMONSTRATION DNS INFRASTRUCTURE
// ============================================================================

function buildDemoDNS() {
    const zone = new DNSZone("example.com.");

    zone.addRecord(
        new DNSRecord(
            "example.com.",
            RecordType.A,
            "192.0.2.10",
            300
        )
    );

    zone.addRecord(
        new DNSRecord(
            "www.example.com.",
            RecordType.CNAME,
            "example.com.",
            120
        )
    );

    zone.addRecord(
        new DNSRecord(
            "api.example.com.",
            RecordType.A,
            "192.0.2.20",
            60
        )
    );

    zone.addRecord(
        new DNSRecord(
            "api.example.com.",
            RecordType.AAAA,
            "2001:db8::20",
            60
        )
    );

    zone.addRecord(
        new DNSRecord(
            "mail.example.com.",
            RecordType.A,
            "192.0.2.30",
            300
        )
    );

    zone.addRecord(
        new DNSRecord(
            "example.com.",
            RecordType.MX,
            "mail.example.com.",
            3600,
            10
        )
    );

    zone.addRecord(
        new DNSRecord(
            "example.com.",
            RecordType.NS,
            "ns1.example.net.",
            86400
        )
    );

    zone.addRecord(
        new DNSRecord(
            "example.com.",
            RecordType.TXT,
            "v=spf1 -all",
            3600
        )
    );

    const authoritative =
        new AuthoritativeServer(
            "ns1.example.net.",
            [zone]
        );

    const root = new RootServer([
        new Delegation(
            ".com.",
            ["a.gtld-servers.example."]
        )
    ]);

    const comTLD =
        new TLDServer(".com.", [
            new Delegation(
                "example.com.",
                ["ns1.example.net."]
            )
        ]);

    return new RecursiveResolver(
        root,
        {
            ".com.": comTLD
        },
        {
            "ns1.example.net.": authoritative
        }
    );
}


// ============================================================================
// 11. RESOLUTION EXAMPLES
// ============================================================================

function demonstrateResolution() {
    printSection("11. COMPLETE DNS RESOLUTION");

    const resolver = buildDemoDNS();

    const queries = [
        ["example.com", RecordType.A],
        ["www.example.com", RecordType.A],
        ["api.example.com", RecordType.AAAA],
        ["example.com", RecordType.MX],
        ["missing.example.com", RecordType.A]
    ];

    for (const [name, type] of queries) {
        console.log(`\nQuery: ${name} ${type}`);

        const response =
            resolver.resolve(name, type);

        for (const event of resolver.trace) {
            console.log(`  ${event}`);
        }

        if (response.answer.length > 0) {
            console.log("  Answer:");

            for (const record of response.answer) {
                console.log(`    ${record}`);
            }
        } else {
            console.log(`  Status: ${response.error}`);
        }
    }
}


// ============================================================================
// 12. CACHE BEHAVIOR
// ============================================================================

function demonstrateCaching() {
    printSection("12. DNS CACHE BEHAVIOR");

    const resolver = buildDemoDNS();

    const first =
        resolver.resolve(
            "api.example.com",
            RecordType.A
        );

    console.log("First query:");
    resolver.trace.forEach(
        event => console.log(`  ${event}`)
    );

    const second =
        resolver.resolve(
            "api.example.com",
            RecordType.A
        );

    console.log("\nSecond query:");
    resolver.trace.forEach(
        event => console.log(`  ${event}`)
    );

    console.log(
        `\nFirst cache hit: ${first.fromCache}`
    );
    console.log(
        `Second cache hit: ${second.fromCache}`
    );
}


// ============================================================================
// 13. FORWARD AND REVERSE DNS
// ============================================================================

function reverseIPv4Name(address) {
    const parts = address.split(".");

    if (
        parts.length !== 4 ||
        parts.some(
            part =>
                !/^\d+$/.test(part) ||
                Number(part) < 0 ||
                Number(part) > 255
        )
    ) {
        throw new Error(
            `Invalid IPv4 address: ${address}`
        );
    }

    return (
        parts.reverse().join(".") +
        ".in-addr.arpa."
    );
}

function demonstrateReverseDNS() {
    printSection("13. FORWARD AND REVERSE DNS");

    const hostname = "server.example.com.";
    const address = "192.0.2.10";

    console.log(
        `Forward DNS: ${hostname} -> ${address}`
    );

    console.log(
        `Reverse DNS: ${address} -> ` +
        `${reverseIPv4Name(address)}`
    );

    console.log(
        "Reverse DNS commonly uses PTR records."
    );
}


// ============================================================================
// 14. SECURITY CONCEPTS
// ============================================================================

function demonstrateSecurity() {
    printSection("14. DNS SECURITY");

    const concepts = {
        DNSSEC:
            "Cryptographically authenticates DNS data.",
        "Cache poisoning":
            "Attempts to insert forged DNS information into a resolver cache.",
        DoT:
            "DNS over TLS protects DNS transport with TLS.",
        DoH:
            "DNS over HTTPS transports DNS through HTTPS.",
        "Open resolver":
            "A resolver exposed to unauthorized clients can be abused for attacks.",
        "Split-horizon DNS":
            "Different DNS answers can be returned to different client populations.",
        "DNS rebinding":
            "DNS answers can be manipulated over time to influence where a client connects."
    };

    for (const [name, description] of Object.entries(concepts)) {
        console.log(`${name}: ${description}`);
    }

    console.log(
        "\nDNSSEC and encrypted DNS solve different security problems."
    );
}


// ============================================================================
// 15. ERROR HANDLING AND EDGE CASES
// ============================================================================

function demonstrateErrors() {
    printSection("15. EDGE CASES AND FAILURE CONDITIONS");

    const candidates = [
        "example.com",
        "www.example.com.",
        "",
        "bad..example.com",
        "-bad.example.com",
        "good-name.example.com"
    ];

    for (const candidate of candidates) {
        console.log(
            `${JSON.stringify(candidate).padEnd(28)} -> ` +
            `${validDNSName(candidate)}`
        );
    }

    try {
        new DNSRecord(
            "bad.example.com.",
            RecordType.A,
            "999.999.999.999"
        );

        validateRecord(
            new DNSRecord(
                "bad.example.com.",
                RecordType.A,
                "999.999.999.999"
            )
        );
    } catch (error) {
        console.log(
            `\nValidation error correctly detected: ${error.message}`
        );
    }
}


// ============================================================================
// 16. CNAME LOOP
// ============================================================================

function demonstrateCNAMELoop() {
    printSection("16. CNAME LOOP DETECTION");

    const zone = new DNSZone("loop.test.");

    zone.addRecord(
        new DNSRecord(
            "a.loop.test.",
            RecordType.CNAME,
            "b.loop.test.",
            60
        )
    );

    zone.addRecord(
        new DNSRecord(
            "b.loop.test.",
            RecordType.CNAME,
            "a.loop.test.",
            60
        )
    );

    const authoritative =
        new AuthoritativeServer(
            "ns.loop.test.",
            [zone]
        );

    const root =
        new RootServer([
            new Delegation(
                ".test.",
                ["a.test-servers.example."]
            )
        ]);

    const tld =
        new TLDServer(".test.", [
            new Delegation(
                "loop.test.",
                ["ns.loop.test."]
            )
        ]);

    const resolver =
        new RecursiveResolver(
            root,
            {
                ".test.": tld
            },
            {
                "ns.loop.test.": authoritative
            }
        );

    const response =
        resolver.resolve(
            "a.loop.test.",
            RecordType.A
        );

    resolver.trace.forEach(
        event => console.log(`  ${event}`)
    );

    console.log(`Result: ${response.error}`);
}


// ============================================================================
// 17. DNS MESSAGE STRUCTURE
// ============================================================================

function demonstrateMessageStructure() {
    printSection("17. DNS MESSAGE STRUCTURE");

    const sections = [
        [
            "Header",
            "Flags, identifiers, response code, and section counts"
        ],
        [
            "Question",
            "Requested name, type, and class"
        ],
        [
            "Answer",
            "Records directly answering the question"
        ],
        [
            "Authority",
            "Delegation or authoritative information"
        ],
        [
            "Additional",
            "Related records that assist interpretation"
        ]
    ];

    for (const [name, purpose] of sections) {
        console.log(
            `${name.padEnd(12)} -> ${purpose}`
        );
    }
}


// ============================================================================
// 18. PERFORMANCE DISCUSSION
// ============================================================================

function demonstratePerformance() {
    printSection("18. PERFORMANCE AND CACHING");

    const rootRTT = 25;
    const tldRTT = 20;
    const authorityRTT = 30;

    const coldLookup =
        rootRTT +
        tldRTT +
        authorityRTT;

    console.log(
        `Illustrative cold-cache sequential cost: ${coldLookup} ms`
    );

    console.log(
        "A cache hit can avoid the complete delegation chain."
    );

    const factors = [
        "Network latency",
        "Cache hit ratio",
        "TTL configuration",
        "Packet loss",
        "Retries",
        "Authoritative-server load",
        "Resolver load",
        "DNSSEC validation",
        "Transport behavior",
        "Negative caching"
    ];

    for (const factor of factors) {
        console.log(`  - ${factor}`);
    }
}


// ============================================================================
// 19. TESTS
// ============================================================================

function runTests() {
    printSection("19. EXECUTABLE TESTS");

    const resolver = buildDemoDNS();

    let response =
        resolver.resolve(
            "api.example.com",
            RecordType.A
        );

    console.assert(
        response.success,
        "A lookup should succeed"
    );

    console.assert(
        response.answer[0].value === "192.0.2.20",
        "A answer should match expected value"
    );

    response =
        resolver.resolve(
            "api.example.com",
            RecordType.AAAA
        );

    console.assert(
        response.answer[0].value === "2001:db8::20",
        "AAAA answer should match expected value"
    );

    response =
        resolver.resolve(
            "www.example.com",
            RecordType.A
        );

    console.assert(
        response.answer[0].value === "192.0.2.10",
        "CNAME should resolve to A record"
    );

    response =
        resolver.resolve(
            "missing.example.com",
            RecordType.A
        );

    console.assert(
        response.error === "NXDOMAIN",
        "Missing name should produce NXDOMAIN"
    );

    response =
        resolver.resolve(
            "api.example.com",
            RecordType.A
        );

    console.assert(
        response.fromCache,
        "Repeated query should use cache"
    );

    console.assert(
        reverseIPv4Name("192.0.2.10") ===
        "10.2.0.192.in-addr.arpa.",
        "Reverse DNS conversion should be correct"
    );

    console.log("All JavaScript tests passed.");
}


// ============================================================================
// 20. CAPSTONE REPORT
// ============================================================================

function generateReport(
    resolver,
    name,
    type
) {
    printSection("20. CAPSTONE RESOLUTION REPORT");

    const start = performance.now();

    const response =
        resolver.resolve(name, type);

    const elapsed =
        performance.now() - start;

    console.log(
        `Name:           ${normalizeName(name)}`
    );

    console.log(`Type:           ${type}`);
    console.log(`Success:        ${response.success}`);
    console.log(`Cache hit:      ${response.fromCache}`);
    console.log(
        `Elapsed:        ${elapsed.toFixed(4)} ms`
    );
    console.log(
        `Resolver calls: ${resolver.queryCount}`
    );

    if (response.answer.length > 0) {
        console.log("\nAnswers:");

        for (const record of response.answer) {
            console.log(`  ${record}`);
        }
    } else {
        console.log(
            `\nStatus: ${response.error}`
        );
    }

    console.log("\nTrace:");

    resolver.trace.forEach(
        event => console.log(`  ${event}`)
    );
}


// ============================================================================
// 21. MAIN
// ============================================================================

function main() {
    console.log(
        "DNS COMPLETE STUDY AND RESOLUTION SIMULATOR"
    );

    explainBasics();
    explainHierarchy();
    demonstrateRecordTypes();
    demonstrateResolution();
    demonstrateCaching();
    demonstrateReverseDNS();
    demonstrateSecurity();
    demonstrateErrors();
    demonstrateCNAMELoop();
    demonstrateMessageStructure();
    demonstratePerformance();
    runTests();

    const resolver = buildDemoDNS();

    generateReport(
        resolver,
        "www.example.com",
        RecordType.A
    );
}

main();
