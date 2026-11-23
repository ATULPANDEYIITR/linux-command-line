"use strict";

/**
 * Container Security Management Engine
 *
 * Node.js 18+
 * Standard-library only.
 *
 * Covers:
 * - Image inventory and scanning
 * - Vulnerability assessment
 * - Secret detection
 * - Minimal image policies
 * - Event-driven security evaluation
 * - Runtime threat detection
 * - Deployment authorization
 * - Remediation lifecycle
 */

const { EventEmitter } = require("node:events");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");

// ==========================================================
// 1. DOMAIN CONSTANTS
// ==========================================================

const Severity = Object.freeze({
    CRITICAL: "CRITICAL",
    HIGH: "HIGH",
    MEDIUM: "MEDIUM",
    LOW: "LOW",
    INFO: "INFO"
});

const Status = Object.freeze({
    APPROVED: "APPROVED",
    BLOCKED: "BLOCKED",
    REVIEW_REQUIRED: "REVIEW_REQUIRED"
});

const RuntimeAction = Object.freeze({
    ALLOW: "ALLOW",
    BLOCK: "BLOCK",
    ALERT: "ALERT"
});

const RemediationState = Object.freeze({
    OPEN: "OPEN",
    IN_PROGRESS: "IN_PROGRESS",
    MITIGATED: "MITIGATED",
    RESOLVED: "RESOLVED",
    ACCEPTED_RISK: "ACCEPTED_RISK"
});

const SEVERITY_WEIGHT = Object.freeze({
    CRITICAL: 5,
    HIGH: 4,
    MEDIUM: 3,
    LOW: 2,
    INFO: 1
});

// ==========================================================
// 2. VALIDATION
// ==========================================================

class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

class SecurityError extends Error {
    constructor(message) {
        super(message);
        this.name = "SecurityError";
    }
}

function validateImage(image) {
    if (!image || typeof image !== "object") {
        throw new ValidationError("Image must be an object.");
    }

    if (!image.name || !image.tag || !image.baseImage) {
        throw new ValidationError(
            "Image name, tag and base image are required."
        );
    }

    if (!Array.isArray(image.packages)) {
        throw new ValidationError("Packages must be an array.");
    }

    if (!Array.isArray(image.vulnerabilities)) {
        throw new ValidationError(
            "Vulnerabilities must be an array."
        );
    }

    if (!Number.isFinite(image.sizeMB) || image.sizeMB <= 0) {
        throw new ValidationError("Invalid image size.");
    }

    if (!Number.isInteger(image.layers) || image.layers < 1) {
        throw new ValidationError("Invalid image layer count.");
    }

    for (const port of image.ports ?? []) {
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
            throw new ValidationError(`Invalid port: ${port}`);
        }
    }
}

// ==========================================================
// 3. IMAGE INVENTORY
// ==========================================================

class ImageRegistry {

    #images = new Map();

    register(image) {
        validateImage(image);

        const key = `${image.name}:${image.tag}`;

        if (this.#images.has(key)) {
            throw new SecurityError(
                `Image already registered: ${key}`
            );
        }

        const immutableImage = structuredClone(image);

        immutableImage.digest = this.calculateDigest(
            immutableImage
        );

        this.#images.set(key, immutableImage);

        return structuredClone(immutableImage);
    }

    calculateDigest(image) {
        const canonical = JSON.stringify({
            name: image.name,
            tag: image.tag,
            baseImage: image.baseImage,
            packages: [...image.packages].sort(
                (a, b) => a.name.localeCompare(b.name)
            ),
            vulnerabilities: [...image.vulnerabilities].sort(
                (a, b) => a.cve.localeCompare(b.cve)
            ),
            user: image.user,
            ports: [...(image.ports ?? [])].sort((a, b) => a - b)
        });

        return "sha256:" + crypto
            .createHash("sha256")
            .update(canonical)
            .digest("hex");
    }

    get(reference) {
        const image = this.#images.get(reference);

        if (!image) {
            throw new SecurityError(
                `Unknown image: ${reference}`
            );
        }

        return structuredClone(image);
    }

    list() {
        return Array.from(this.#images.values()).map(
            image => structuredClone(image)
        );
    }
}

// ==========================================================
// 4. VULNERABILITY SCANNER
// ==========================================================

class VulnerabilityScanner {

    scan(image) {
        return image.vulnerabilities.map(vulnerability => ({
            category: "VULNERABILITY",
            severity: vulnerability.severity,
            resource: vulnerability.package,
            identifier: vulnerability.cve,
            description: vulnerability.description,
            fixedVersion: vulnerability.fixedVersion ?? null,
            exploitable: Boolean(vulnerability.exploitable),
            remediation: vulnerability.fixedVersion
                ? `Upgrade to ${vulnerability.fixedVersion}`
                : "Apply an approved mitigation or replace the package."
        }));
    }
}

// ==========================================================
// 5. SECRET SCANNER
// ==========================================================

class SecretScanner {

    #patterns = [
        {
            name: "AWS_ACCESS_KEY",
            pattern: /\bAKIA[0-9A-Z]{16}\b/
        },
        {
            name: "PRIVATE_KEY",
            pattern: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/
        },
        {
            name: "PASSWORD",
            pattern: /(?i)/ // Replaced below with a compatible expression.
        }
    ];

    scan(environment) {
        const findings = [];

        for (const [key, value] of Object.entries(environment ?? {})) {
            if (typeof value !== "string") {
                throw new ValidationError(
                    `Environment value for ${key} must be a string.`
                );
            }

            const content = `${key}=${value}`;

            const secretPatterns = [
                ["AWS_ACCESS_KEY", /\bAKIA[0-9A-Z]{16}\b/],
                [
                    "PRIVATE_KEY",
                    /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/
                ],
                [
                    "PASSWORD",
                    /(password|passwd|secret|api_key)\s*=\s*[^$\s][^\s]{5,}/i
                ],
                [
                    "ACCESS_TOKEN",
                    /(access_token|auth_token)\s*=\s*[^$\s][^\s]{5,}/i
                ]
            ];

            for (const [name, pattern] of secretPatterns) {
                if (pattern.test(content)) {
                    findings.push({
                        category: "SECRET",
                        severity: Severity.CRITICAL,
                        resource: key,
                        identifier: name,
                        description: `Potential ${name} exposure.`,
                        remediation:
                            "Remove and rotate the credential. " +
                            "Use a managed secret injection mechanism."
                    });

                    break;
                }
            }
        }

        return findings;
    }
}

// ==========================================================
// 6. MINIMAL IMAGE AND CONFIGURATION POLICY
// ==========================================================

class ImageConfigurationScanner {

    scan(image) {
        const findings = [];

        if (["root", "0", "0:0"].includes(
            String(image.user).toLowerCase()
        )) {
            findings.push({
                category: "MISCONFIGURATION",
                severity: Severity.HIGH,
                resource: "USER",
                description: "Container runs as root.",
                remediation: "Use a dedicated non-root user."
            });
        }

        if (image.sizeMB > 200) {
            findings.push({
                category: "MISCONFIGURATION",
                severity: Severity.MEDIUM,
                resource: "IMAGE_SIZE",
                description: `Image size is ${image.sizeMB} MB.`,
                remediation:
                    "Use a smaller runtime base and remove build tools."
            });
        }

        if (image.layers > 15) {
            findings.push({
                category: "MISCONFIGURATION",
                severity: Severity.LOW,
                resource: "IMAGE_LAYERS",
                description: "Excessive image layers.",
                remediation: "Consolidate unnecessary build layers."
            });
        }

        if (!image.signed) {
            findings.push({
                category: "COMPLIANCE",
                severity: Severity.HIGH,
                resource: "SIGNATURE",
                description: "Image signature is not verified.",
                remediation: "Sign the image and verify its provenance."
            });
        }

        if (!image.digest) {
            findings.push({
                category: "COMPLIANCE",
                severity: Severity.HIGH,
                resource: "DIGEST",
                description: "No immutable image digest is recorded.",
                remediation: "Deploy a verified immutable image digest."
            });
        }

        if (!image.healthcheck) {
            findings.push({
                category: "MISCONFIGURATION",
                severity: Severity.LOW,
                resource: "HEALTHCHECK",
                description: "No health check is configured.",
                remediation: "Configure an application health check."
            });
        }

        if (!image.entrypoint?.length) {
            findings.push({
                category: "MISCONFIGURATION",
                severity: Severity.MEDIUM,
                resource: "ENTRYPOINT",
                description: "Image has no explicit entrypoint.",
                remediation: "Configure an explicit executable entrypoint."
            });
        }

        if (image.tag === "latest") {
            findings.push({
                category: "MISCONFIGURATION",
                severity: Severity.MEDIUM,
                resource: "IMAGE_TAG",
                description: "Mutable latest tag is used.",
                remediation: "Use a versioned tag and verified digest."
            });
        }

        return findings;
    }
}

// ==========================================================
// 7. SECURITY POLICY
// ==========================================================

class SecurityPolicy {

    constructor(configuration = {}) {
        this.maxCritical = configuration.maxCritical ?? 0;
        this.maxHigh = configuration.maxHigh ?? 0;
        this.maxMedium = configuration.maxMedium ?? 3;

        this.requireNonRoot =
            configuration.requireNonRoot ?? true;

        this.requireSignature =
            configuration.requireSignature ?? true;

        this.requireDigest =
            configuration.requireDigest ?? true;

        this.requireHealthcheck =
            configuration.requireHealthcheck ?? true;

        this.blockSecrets =
            configuration.blockSecrets ?? true;

        for (const value of [
            this.maxCritical,
            this.maxHigh,
            this.maxMedium
        ]) {
            if (!Number.isInteger(value) || value < 0) {
                throw new ValidationError(
                    "Severity thresholds must be non-negative integers."
                );
            }
        }

        Object.freeze(this);
    }

    evaluate(image, findings) {
        const counts = {
            CRITICAL: 0,
            HIGH: 0,
            MEDIUM: 0,
            LOW: 0,
            INFO: 0
        };

        for (const finding of findings) {
            if (!(finding.severity in counts)) {
                throw new ValidationError(
                    `Unknown severity: ${finding.severity}`
                );
            }

            counts[finding.severity]++;
        }

        const reasons = [];

        if (counts.CRITICAL > this.maxCritical) {
            reasons.push("Critical vulnerability threshold exceeded.");
        }

        if (counts.HIGH > this.maxHigh) {
            reasons.push("High severity threshold exceeded.");
        }

        if (counts.MEDIUM > this.maxMedium) {
            reasons.push("Medium severity threshold exceeded.");
        }

        if (
            this.blockSecrets &&
            findings.some(f => f.category === "SECRET")
        ) {
            reasons.push("Secret exposure detected.");
        }

        if (
            this.requireNonRoot &&
            ["root", "0", "0:0"].includes(
                String(image.user).toLowerCase()
            )
        ) {
            reasons.push("Root execution is prohibited.");
        }

        if (this.requireSignature && !image.signed) {
            reasons.push("Verified image signature required.");
        }

        if (this.requireDigest && !image.digest) {
            reasons.push("Immutable image digest required.");
        }

        if (this.requireHealthcheck && !image.healthcheck) {
            reasons.push("Health check required.");
        }

        return {
            status: reasons.length
                ? Status.BLOCKED
                : Status.APPROVED,
            counts,
            reasons
        };
    }
}

// ==========================================================
// 8. EVENT-DRIVEN SECURITY PIPELINE
// ==========================================================

class ContainerSecurityPipeline extends EventEmitter {

    constructor(registry, policy) {
        super();

        this.registry = registry;
        this.policy = policy;

        this.vulnerabilityScanner = new VulnerabilityScanner();
        this.secretScanner = new SecretScanner();
        this.configurationScanner = new ImageConfigurationScanner();
    }

    async scan(reference) {
        const image = this.registry.get(reference);

        this.emit("scanStarted", {
            reference,
            timestamp: new Date().toISOString()
        });

        try {
            const findings = [
                ...this.vulnerabilityScanner.scan(image),
                ...this.secretScanner.scan(image.environment),
                ...this.configurationScanner.scan(image)
            ];

            const decision = this.policy.evaluate(
                image,
                findings
            );

            const report = {
                reference,
                digest: image.digest,
                timestamp: new Date().toISOString(),
                status: decision.status,
                counts: decision.counts,
                reasons: decision.reasons,
                findings
            };

            this.emit("scanCompleted", report);

            this.emit(
                decision.status === Status.APPROVED
                    ? "imageApproved"
                    : "imageBlocked",
                report
            );

            return report;
        } catch (error) {
            this.emit("scanFailed", {
                reference,
                error: error.message
            });

            throw error;
        }
    }
}

// ==========================================================
// 9. RUNTIME THREAT DETECTION
// ==========================================================

class RuntimeMonitor {

    #blockedProcesses = new Set([
        "nc",
        "ncat",
        "socat",
        "tcpdump",
        "chroot"
    ]);

    #protectedPaths = new Set([
        "/etc/shadow",
        "/etc/passwd",
        "/root/.ssh/authorized_keys"
    ]);

    evaluate(event) {
        if (!event.containerId || !event.type || !event.process) {
            throw new ValidationError(
                "Runtime event requires containerId, type and process."
            );
        }

        if (event.privileged === true) {
            return {
                action: RuntimeAction.BLOCK,
                severity: Severity.CRITICAL,
                reason: "Unexpected privileged execution."
            };
        }

        if (event.type === "EXEC") {
            const executable = event.process
                .split("/")
                .pop()
                .toLowerCase();

            if (this.#blockedProcesses.has(executable)) {
                return {
                    action: RuntimeAction.BLOCK,
                    severity: Severity.HIGH,
                    reason: "Restricted executable detected."
                };
            }
        }

        if (event.type === "FILE_WRITE") {
            if (this.#protectedPaths.has(event.destination)) {
                return {
                    action: RuntimeAction.BLOCK,
                    severity: Severity.CRITICAL,
                    reason: "Protected file modification."
                };
            }
        }

        if (event.type === "UNKNOWN") {
            return {
                action: RuntimeAction.ALERT,
                severity: Severity.HIGH,
                reason: "Unrecognized runtime activity."
            };
        }

        return {
            action: RuntimeAction.ALLOW,
            severity: Severity.INFO,
            reason: "Activity allowed."
        };
    }
}

// ==========================================================
// 10. VULNERABILITY REMEDIATION
// ==========================================================

class RemediationTicket {

    #transitions = {
        OPEN: ["IN_PROGRESS", "ACCEPTED_RISK"],
        IN_PROGRESS: ["MITIGATED", "RESOLVED", "ACCEPTED_RISK"],
        MITIGATED: ["RESOLVED", "IN_PROGRESS"],
        RESOLVED: ["OPEN"],
        ACCEPTED_RISK: ["OPEN", "IN_PROGRESS"]
    };

    constructor({
        id,
        cve,
        image,
        severity,
        owner,
        dueDate
    }) {
        if (!id || !cve || !image || !owner || !dueDate) {
            throw new ValidationError(
                "Remediation ticket fields are required."
            );
        }

        if (!(severity in SEVERITY_WEIGHT)) {
            throw new ValidationError("Invalid severity.");
        }

        this.id = id;
        this.cve = cve;
        this.image = image;
        this.severity = severity;
        this.owner = owner;
        this.dueDate = dueDate;
        this.state = RemediationState.OPEN;
        this.history = [];
    }

    transition(nextState) {
        const permitted = this.#transitions[this.state];

        if (!permitted.includes(nextState)) {
            throw new SecurityError(
                `Invalid transition: ${this.state} -> ${nextState}`
            );
        }

        this.history.push({
            from: this.state,
            to: nextState,
            timestamp: new Date().toISOString()
        });

        this.state = nextState;
    }
}

// ==========================================================
// 11. SAMPLE CONTAINER INVENTORY
// ==========================================================

function unsafeImage() {
    return {
        name: "payment-api",
        tag: "latest",
        baseImage: "ubuntu:latest",
        packages: [
            { name: "openssl", version: "1.0.2" },
            { name: "curl", version: "7.50.0" }
        ],
        vulnerabilities: [
            {
                cve: "CVE-2025-10001",
                package: "openssl",
                severity: Severity.CRITICAL,
                description: "Critical cryptographic weakness.",
                fixedVersion: "3.0.15",
                exploitable: true
            },
            {
                cve: "CVE-2025-10002",
                package: "curl",
                severity: Severity.HIGH,
                description: "Network request vulnerability.",
                fixedVersion: "8.10.0"
            }
        ],
        ports: [22, 8080],
        environment: {
            DATABASE_PASSWORD: "production_password_123"
        },
        user: "root",
        entrypoint: ["python", "app.py"],
        layers: 24,
        sizeMB: 850,
        signed: false,
        healthcheck: false
    };
}

function secureImage() {
    return {
        name: "payment-api",
        tag: "2.1.0",
        baseImage: "python:3.12-slim",
        packages: [
            { name: "python", version: "3.12" },
            { name: "application", version: "2.1.0" }
        ],
        vulnerabilities: [],
        ports: [8080],
        environment: {
            APP_MODE: "production",
            DATABASE_HOST: "database.internal"
        },
        user: "10001",
        entrypoint: ["python", "-m", "payment_service"],
        layers: 7,
        sizeMB: 95,
        signed: true,
        healthcheck: true
    };
}

// ==========================================================
// 12. TESTS AND EXECUTION
// ==========================================================

async function main() {

    const registry = new ImageRegistry();

    const insecure = registry.register(unsafeImage());
    const secure = registry.register(secureImage());

    const policy = new SecurityPolicy({
        maxCritical: 0,
        maxHigh: 0,
        maxMedium: 3,
        requireNonRoot: true,
        requireSignature: true,
        requireDigest: true,
        requireHealthcheck: true,
        blockSecrets: true
    });

    const pipeline = new ContainerSecurityPipeline(
        registry,
        policy
    );

    pipeline.on("scanStarted", event => {
        console.log(`Scanning ${event.reference}`);
    });

    pipeline.on("imageApproved", report => {
        console.log(`APPROVED: ${report.reference}`);
    });

    pipeline.on("imageBlocked", report => {
        console.log(`BLOCKED: ${report.reference}`);
    });

    pipeline.on("scanFailed", event => {
        console.error("Scan failed:", event.error);
    });

    const insecureReport = await pipeline.scan(
        `${insecure.name}:${insecure.tag}`
    );

    const secureReport = await pipeline.scan(
        `${secure.name}:${secure.tag}`
    );

    assert.equal(insecureReport.status, Status.BLOCKED);
    assert.equal(secureReport.status, Status.APPROVED);

    const monitor = new RuntimeMonitor();

    const allowed = monitor.evaluate({
        containerId: "container-101",
        type: "EXEC",
        process: "/usr/local/bin/python",
        privileged: false
    });

    const blocked = monitor.evaluate({
        containerId: "container-101",
        type: "EXEC",
        process: "/usr/bin/nc",
        privileged: false
    });

    assert.equal(allowed.action, RuntimeAction.ALLOW);
    assert.equal(blocked.action, RuntimeAction.BLOCK);

    const ticket = new RemediationTicket({
        id: "SEC-1001",
        cve: "CVE-2025-10001",
        image: "payment-api:latest",
        severity: Severity.CRITICAL,
        owner: "platform-team",
        dueDate: "2026-11-25"
    });

    ticket.transition(RemediationState.IN_PROGRESS);

    assert.equal(
        ticket.state,
        RemediationState.IN_PROGRESS
    );

    assert.throws(
        () => ticket.transition(RemediationState.OPEN),
        SecurityError
    );

    console.log("\nSecurity test suite passed.");

    console.log("\nImage security reports:");

    console.log(JSON.stringify([
        insecureReport,
        secureReport
    ], null, 2));

    console.log("\nRuntime decisions:");

    console.log({ allowed, blocked });

    console.log("\nRemediation ticket:");

    console.log({
        id: ticket.id,
        cve: ticket.cve,
        state: ticket.state,
        history: ticket.history
    });
}

main().catch(error => {
    console.error("Fatal security pipeline error:", error);
    process.exitCode = 1;
});
