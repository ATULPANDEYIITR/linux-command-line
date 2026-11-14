"use strict";

/*
 * CLOUD SECURITY POLICY AND MONITORING ENGINE
 *
 * Node.js 18+
 * No third-party dependencies.
 *
 * Focus:
 * - Event-driven security monitoring
 * - IAM policy evaluation
 * - Network isolation
 * - Encryption compliance
 * - Audit event processing
 * - Security alert aggregation
 * - Asynchronous policy evaluation
 */

const crypto = require("node:crypto");
const net = require("node:net");
const { EventEmitter } = require("node:events");
const fs = require("node:fs/promises");

class SecurityError extends Error {}
class PolicyError extends SecurityError {}
class ValidationError extends SecurityError {}

const Decision = Object.freeze({
    ALLOW: "ALLOW",
    DENY: "DENY"
});

const Severity = Object.freeze({
    LOW: "LOW",
    MEDIUM: "MEDIUM",
    HIGH: "HIGH",
    CRITICAL: "CRITICAL"
});

function validateIdentifier(value, field) {
    if (
        typeof value !== "string" ||
        !/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/.test(value)
    ) {
        throw new ValidationError(`Invalid ${field}`);
    }
}

function validateIPv4(address) {
    if (net.isIP(address) !== 4) {
        throw new ValidationError("A valid IPv4 address is required");
    }
    return address.split(".").map(Number);
}

function ipv4ToInteger(address) {
    return validateIPv4(address).reduce(
        (result, octet) => ((result << 8) | octet) >>> 0,
        0
    );
}

class CIDR {
    constructor(value) {
        const parts = value.split("/");

        if (parts.length !== 2) {
            throw new ValidationError("CIDR notation required");
        }

        this.address = ipv4ToInteger(parts[0]);
        this.prefix = Number(parts[1]);

        if (
            !Number.isInteger(this.prefix) ||
            this.prefix < 0 ||
            this.prefix > 32
        ) {
            throw new ValidationError("Invalid CIDR prefix");
        }

        this.mask = this.prefix === 0
            ? 0
            : (0xffffffff << (32 - this.prefix)) >>> 0;
    }

    contains(address) {
        const candidate = ipv4ToInteger(address);
        return (
            (candidate & this.mask) >>> 0
        ) === (
            (this.address & this.mask) >>> 0
        );
    }
}

class IAMPolicy {
    constructor(name, statements) {
        validateIdentifier(name, "policy name");

        if (!Array.isArray(statements) || statements.length === 0) {
            throw new ValidationError("Policy requires statements");
        }

        this.name = name;
        this.statements = statements.map(statement => {
            if (
                !["Allow", "Deny"].includes(statement.effect) ||
                typeof statement.action !== "string" ||
                typeof statement.resource !== "string"
            ) {
                throw new ValidationError("Invalid IAM statement");
            }

            return Object.freeze({ ...statement });
        });
    }

    evaluate(action, resource) {
        let explicitlyDenied = false;
        let allowed = false;

        for (const statement of this.statements) {
            const actionMatch =
                statement.action === "*" ||
                statement.action === action;

            const resourceMatch =
                statement.resource === "*" ||
                statement.resource === resource ||
                (
                    statement.resource.endsWith("*") &&
                    resource.startsWith(
                        statement.resource.slice(0, -1)
                    )
                );

            if (actionMatch && resourceMatch) {
                if (statement.effect === "Deny") {
                    explicitlyDenied = true;
                }

                if (statement.effect === "Allow") {
                    allowed = true;
                }
            }
        }

        // Explicit deny always overrides allow.
        if (explicitlyDenied) return Decision.DENY;

        return allowed ? Decision.ALLOW : Decision.DENY;
    }
}

class IAMService {
    constructor() {
        this.identities = new Map();
        this.policies = new Map();
    }

    registerPolicy(policy) {
        if (this.policies.has(policy.name)) {
            throw new ValidationError("Duplicate policy");
        }
        this.policies.set(policy.name, policy);
    }

    registerIdentity(identity) {
        validateIdentifier(identity.id, "identity");

        if (this.identities.has(identity.id)) {
            throw new ValidationError("Identity already exists");
        }

        for (const policy of identity.policies) {
            if (!this.policies.has(policy)) {
                throw new ValidationError(
                    `Unknown policy: ${policy}`
                );
            }
        }

        this.identities.set(identity.id, {
            id: identity.id,
            policies: new Set(identity.policies),
            enabled: Boolean(identity.enabled),
            mfa: Boolean(identity.mfa)
        });
    }

    authorize(identityId, action, resource, requireMFA = true) {
        const identity = this.identities.get(identityId);

        if (
            !identity ||
            !identity.enabled ||
            (requireMFA && !identity.mfa)
        ) {
            return Decision.DENY;
        }

        let allowed = false;

        for (const policyName of identity.policies) {
            const decision = this.policies
                .get(policyName)
                .evaluate(action, resource);

            if (decision === Decision.DENY) {
                // This implementation treats unmatched and explicit
                // denies alike at policy level. Explicit policy denies
                // are also preserved by IAMPolicy.
                const policy = this.policies.get(policyName);
                const explicit = policy.statements.some(statement =>
                    statement.effect === "Deny" &&
                    (
                        statement.action === "*" ||
                        statement.action === action
                    ) &&
                    (
                        statement.resource === "*" ||
                        statement.resource === resource ||
                        (
                            statement.resource.endsWith("*") &&
                            resource.startsWith(
                                statement.resource.slice(0, -1)
                            )
                        )
                    )
                );

                if (explicit) return Decision.DENY;
            }

            if (decision === Decision.ALLOW) {
                allowed = true;
            }
        }

        return allowed ? Decision.ALLOW : Decision.DENY;
    }
}

class NetworkPolicy {
    constructor() {
        this.rules = new Map();
    }

    addRule(resourceId, rule) {
        validateIdentifier(resourceId, "resource");

        if (!["INGRESS", "EGRESS"].includes(rule.direction)) {
            throw new ValidationError("Invalid direction");
        }

        if (
            !["TCP", "UDP"].includes(rule.protocol) ||
            !Number.isInteger(rule.port) ||
            rule.port < 1 ||
            rule.port > 65535
        ) {
            throw new ValidationError("Invalid network rule");
        }

        const cidr = new CIDR(rule.cidr);

        if (!this.rules.has(resourceId)) {
            this.rules.set(resourceId, []);
        }

        this.rules.get(resourceId).push({
            ...rule,
            cidr
        });
    }

    allows(resourceId, ip, port, protocol = "TCP") {
        if (net.isIP(ip) !== 4) {
            throw new ValidationError(
                "Only IPv4 addresses are supported"
            );
        }

        return (this.rules.get(resourceId) || []).some(rule =>
            rule.direction === "INGRESS" &&
            rule.protocol === protocol &&
            rule.port === port &&
            rule.cidr.contains(ip)
        );
    }
}

class SecurityResource {
    constructor({
        id,
        type,
        encryptedAtRest,
        encryptedInTransit,
        publicAccess = false
    }) {
        validateIdentifier(id, "resource");

        if (!type) {
            throw new ValidationError("Resource type required");
        }

        this.id = id;
        this.type = type;
        this.encryptedAtRest = Boolean(encryptedAtRest);
        this.encryptedInTransit = Boolean(encryptedInTransit);
        this.publicAccess = Boolean(publicAccess);
        this.state = "ACTIVE";
    }
}

class AuditService {
    constructor() {
        this.events = [];
        this.previousHash = "0".repeat(64);
    }

    append(event) {
        const record = Object.freeze({
            id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            ...event,
            previousHash: this.previousHash
        });

        const digest = crypto
            .createHash("sha256")
            .update(JSON.stringify(record))
            .digest("hex");

        this.events.push(Object.freeze({
            ...record,
            hash: digest
        }));

        this.previousHash = digest;

        return this.events[this.events.length - 1];
    }

    verify() {
        let previous = "0".repeat(64);

        for (const event of this.events) {
            const { hash, ...record } = event;

            if (record.previousHash !== previous) {
                return false;
            }

            const calculated = crypto
                .createHash("sha256")
                .update(JSON.stringify(record))
                .digest("hex");

            if (
                !crypto.timingSafeEqual(
                    Buffer.from(calculated, "hex"),
                    Buffer.from(hash, "hex")
                )
            ) {
                return false;
            }

            previous = hash;
        }

        return true;
    }

    async exportJSON(filePath) {
        const data = JSON.stringify(this.events, null, 2);

        await fs.writeFile(filePath, data, {
            encoding: "utf8",
            flag: "wx",
            mode: 0o600
        });
    }
}

class SecurityMonitor extends EventEmitter {
    constructor(threshold = 3) {
        super();

        if (!Number.isInteger(threshold) || threshold < 1) {
            throw new ValidationError("Invalid threshold");
        }

        this.threshold = threshold;
        this.failures = new Map();
        this.alerts = [];
    }

    process(event) {
        if (event.decision !== Decision.DENY) return;

        const count = (this.failures.get(event.identityId) || 0) + 1;

        this.failures.set(event.identityId, count);

        if (count >= this.threshold) {
            const alert = Object.freeze({
                id: crypto.randomUUID(),
                identityId: event.identityId,
                severity: Severity.HIGH,
                description: "Repeated unauthorized access",
                failures: count,
                timestamp: new Date().toISOString()
            });

            this.alerts.push(alert);
            this.emit("security-alert", alert);
        }
    }

    reset(identityId) {
        this.failures.delete(identityId);
    }
}

class CloudSecurityEngine {
    constructor() {
        this.iam = new IAMService();
        this.network = new NetworkPolicy();
        this.audit = new AuditService();
        this.monitor = new SecurityMonitor(3);
        this.resources = new Map();
    }

    registerResource(resource) {
        if (this.resources.has(resource.id)) {
            throw new ValidationError("Duplicate resource");
        }

        if (
            !resource.encryptedAtRest ||
            !resource.encryptedInTransit ||
            resource.publicAccess
        ) {
            throw new PolicyError(
                "Resource violates baseline security policy"
            );
        }

        this.resources.set(resource.id, resource);
    }

    async authorizeRequest(request) {
        const {
            identityId,
            action,
            resourceId,
            sourceIP,
            port = 443
        } = request;

        const resource = this.resources.get(resourceId);

        if (!resource) {
            throw new ValidationError("Unknown resource");
        }

        if (resource.state !== "ACTIVE") {
            return this.recordDecision(
                identityId,
                action,
                resourceId,
                Decision.DENY,
                "Resource unavailable"
            );
        }

        const [iamDecision, networkAllowed] = await Promise.all([
            Promise.resolve(
                this.iam.authorize(
                    identityId,
                    action,
                    resourceId,
                    true
                )
            ),
            Promise.resolve(
                this.network.allows(
                    resourceId,
                    sourceIP,
                    port
                )
            )
        ]);

        const decision =
            iamDecision === Decision.ALLOW && networkAllowed
                ? Decision.ALLOW
                : Decision.DENY;

        return this.recordDecision(
            identityId,
            action,
            resourceId,
            decision,
            "IAM and network policy evaluation"
        );
    }

    recordDecision(
        identityId,
        action,
        resourceId,
        decision,
        reason
    ) {
        const event = this.audit.append({
            identityId,
            action,
            resourceId,
            decision,
            reason
        });

        this.monitor.process(event);

        return decision;
    }

    assess() {
        const findings = [];

        for (const resource of this.resources.values()) {
            if (!resource.encryptedAtRest) {
                findings.push(`${resource.id}: at-rest encryption missing`);
            }

            if (!resource.encryptedInTransit) {
                findings.push(`${resource.id}: transport encryption missing`);
            }

            if (resource.publicAccess) {
                findings.push(`${resource.id}: public exposure`);
            }
        }

        return {
            resources: this.resources.size,
            auditIntegrity: this.audit.verify(),
            events: this.audit.events.length,
            alerts: this.monitor.alerts.length,
            findings
        };
    }
}

async function main() {
    const cloud = new CloudSecurityEngine();

    cloud.iam.registerPolicy(
        new IAMPolicy("storage-reader", [
            {
                effect: "Allow",
                action: "storage:read",
                resource: "bucket-finance-001"
            },
            {
                effect: "Deny",
                action: "storage:delete",
                resource: "*"
            }
        ])
    );

    cloud.iam.registerIdentity({
        id: "operator-001",
        policies: ["storage-reader"],
        enabled: true,
        mfa: true
    });

    cloud.iam.registerIdentity({
        id: "untrusted-001",
        policies: [],
        enabled: true,
        mfa: false
    });

    cloud.registerResource(
        new SecurityResource({
            id: "bucket-finance-001",
            type: "OBJECT_STORAGE",
            encryptedAtRest: true,
            encryptedInTransit: true
        })
    );

    cloud.network.addRule("bucket-finance-001", {
        direction: "INGRESS",
        protocol: "TCP",
        port: 443,
        cidr: "10.10.0.0/16"
    });

    cloud.monitor.on("security-alert", alert => {
        console.error("SECURITY ALERT:", alert);
    });

    const requests = [
        {
            identityId: "operator-001",
            action: "storage:read",
            resourceId: "bucket-finance-001",
            sourceIP: "10.10.1.20"
        },
        ...Array.from({ length: 3 }, () => ({
            identityId: "untrusted-001",
            action: "storage:read",
            resourceId: "bucket-finance-001",
            sourceIP: "10.10.1.30"
        })),
        {
            identityId: "operator-001",
            action: "storage:delete",
            resourceId: "bucket-finance-001",
            sourceIP: "10.10.1.20"
        }
    ];

    for (const request of requests) {
        const result = await cloud.authorizeRequest(request);

        console.log(
            request.identityId,
            request.action,
            result
        );
    }

    console.log("\nSECURITY ASSESSMENT");
    console.log(JSON.stringify(cloud.assess(), null, 2));

    if (!cloud.audit.verify()) {
        throw new SecurityError("Audit integrity verification failed");
    }
}

main().catch(error => {
    console.error("SECURITY ENGINE FAILURE:", error.message);
    process.exitCode = 1;
});
