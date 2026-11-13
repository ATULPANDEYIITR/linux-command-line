"use strict";

/*
 * Compliance and Governance Event Engine.
 *
 * Demonstrates event-driven policy evaluation, asynchronous
 * subject-request processing, privacy controls, consent,
 * retention, audit events, and compliance reporting.
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const crypto = require("node:crypto");
const fs = require("node:fs/promises");

class ComplianceError extends Error {}
class ValidationError extends ComplianceError {}
class AuthorizationError extends ComplianceError {}
class PolicyViolation extends ComplianceError {}
class ConflictError extends ComplianceError {}

const PrivacyCategory = Object.freeze({
    PUBLIC: "PUBLIC",
    INTERNAL: "INTERNAL",
    CONFIDENTIAL: "CONFIDENTIAL",
    PERSONAL: "PERSONAL",
    SENSITIVE_PERSONAL: "SENSITIVE_PERSONAL"
});

const LegalBasis = Object.freeze({
    CONSENT: "CONSENT",
    CONTRACT: "CONTRACT",
    LEGAL_OBLIGATION: "LEGAL_OBLIGATION",
    LEGITIMATE_INTEREST: "LEGITIMATE_INTEREST",
    VITAL_INTEREST: "VITAL_INTEREST",
    PUBLIC_TASK: "PUBLIC_TASK"
});

const RequestStatus = Object.freeze({
    RECEIVED: "RECEIVED",
    VERIFIED: "VERIFIED",
    IN_PROGRESS: "IN_PROGRESS",
    COMPLETED: "COMPLETED",
    REJECTED: "REJECTED"
});

const RequestType = Object.freeze({
    ACCESS: "ACCESS",
    RECTIFICATION: "RECTIFICATION",
    ERASURE: "ERASURE",
    PORTABILITY: "PORTABILITY",
    RESTRICTION: "RESTRICTION"
});

const TRANSITIONS = Object.freeze({
    RECEIVED: ["VERIFIED", "REJECTED"],
    VERIFIED: ["IN_PROGRESS", "REJECTED"],
    IN_PROGRESS: ["COMPLETED", "REJECTED"],
    COMPLETED: [],
    REJECTED: []
});

const FRAMEWORKS = new Map([
    ["GDPR", "European Union"],
    ["DPDPA", "India"],
    ["ISO27001", "International"],
    ["HIPAA", "United States"]
]);

function requireValue(value, field) {
    if (
        value === undefined ||
        value === null ||
        String(value).trim() === ""
    ) {
        throw new ValidationError(`${field} is required.`);
    }
}

function validateEnum(value, allowed, field) {
    if (!Object.values(allowed).includes(value)) {
        throw new ValidationError(`Invalid ${field}: ${value}`);
    }
}

function deepFreeze(value) {
    if (value && typeof value === "object") {
        Object.freeze(value);

        Object.values(value).forEach(deepFreeze);
    }

    return value;
}

class EventBus {
    constructor() {
        this.listeners = new Map();
    }

    subscribe(eventType, listener) {
        if (typeof listener !== "function") {
            throw new ValidationError("Listener must be a function.");
        }

        const listeners = this.listeners.get(eventType) ?? new Set();

        listeners.add(listener);
        this.listeners.set(eventType, listeners);

        return () => listeners.delete(listener);
    }

    async publish(event) {
        const listeners = this.listeners.get(event.type) ?? [];

        // Each listener receives the same immutable event.
        await Promise.all(
            [...listeners].map(listener => listener(event))
        );
    }
}

class AuditLedger {
    constructor() {
        this.events = [];
        this.previousHash = "GENESIS";
    }

    append(actor, action, resource, details = {}) {
        const payload = {
            sequence: this.events.length + 1,
            actor,
            action,
            resource,
            details,
            timestamp: new Date().toISOString(),
            previousHash: this.previousHash
        };

        const serialized = JSON.stringify(payload);

        const hash = crypto
            .createHash("sha256")
            .update(serialized)
            .digest("hex");

        const event = Object.freeze({
            ...payload,
            hash
        });

        this.events.push(event);
        this.previousHash = hash;

        return event;
    }

    verify() {
        let previous = "GENESIS";

        for (const event of this.events) {
            if (event.previousHash !== previous) {
                return false;
            }

            const payload = {
                sequence: event.sequence,
                actor: event.actor,
                action: event.action,
                resource: event.resource,
                details: event.details,
                timestamp: event.timestamp,
                previousHash: previous
            };

            const expected = crypto
                .createHash("sha256")
                .update(JSON.stringify(payload))
                .digest("hex");

            if (expected !== event.hash) {
                return false;
            }

            previous = event.hash;
        }

        return true;
    }

    async export(filename) {
        await fs.writeFile(
            filename,
            JSON.stringify(this.events, null, 2),
            { encoding: "utf8", mode: 0o600 }
        );
    }
}

class AccessPolicy {
    constructor() {
        this.roles = new Map([
            ["COMPLIANCE_ADMIN", new Set([
                "asset:create",
                "asset:read",
                "consent:manage",
                "request:manage",
                "policy:manage",
                "retention:manage",
                "report:read"
            ])],
            ["PRIVACY_OFFICER", new Set([
                "asset:read",
                "consent:manage",
                "request:manage",
                "report:read"
            ])],
            ["ANALYST", new Set([
                "asset:read"
            ])],
            ["AUDITOR", new Set([
                "report:read",
                "audit:read"
            ])]
        ]);
    }

    authorize(user, permission) {
        if (!user || !user.active) {
            throw new AuthorizationError("Inactive user.");
        }

        const permissions = this.roles.get(user.role);

        if (!permissions || !permissions.has(permission)) {
            throw new AuthorizationError(
                `Role ${user.role} cannot perform ${permission}.`
            );
        }
    }
}

class ComplianceEngine {
    constructor() {
        this.assets = new Map();
        this.users = new Map();
        this.consents = new Map();
        this.requests = new Map();
        this.policies = new Map();
        this.findings = [];
        this.processingLocks = new Set();

        this.accessPolicy = new AccessPolicy();
        this.audit = new AuditLedger();
        this.events = new EventBus();

        this.events.subscribe("ASSET_REGISTERED", async event => {
            this.audit.append(
                event.actor,
                "ASSET_REGISTERED",
                event.resource
            );
        });

        this.events.subscribe("CONSENT_WITHDRAWN", async event => {
            this.audit.append(
                event.actor,
                "CONSENT_WITHDRAWN",
                event.resource
            );
        });

        this.events.subscribe("REQUEST_TRANSITIONED", async event => {
            this.audit.append(
                event.actor,
                "REQUEST_TRANSITIONED",
                event.resource,
                event.details
            );
        });
    }

    registerUser(user) {
        requireValue(user.id, "User ID");
        requireValue(user.role, "Role");

        if (this.users.has(user.id)) {
            throw new ConflictError("User already exists.");
        }

        if (!this.accessPolicy.roles.has(user.role)) {
            throw new ValidationError("Unknown role.");
        }

        this.users.set(user.id, {
            id: user.id,
            role: user.role,
            active: user.active !== false
        });
    }

    authorize(actorId, permission) {
        const user = this.users.get(actorId);

        try {
            this.accessPolicy.authorize(user, permission);
        } catch (error) {
            this.audit.append(
                actorId,
                "ACCESS_DENIED",
                permission
            );

            throw error;
        }

        return user;
    }

    registerAsset(actorId, input) {
        this.authorize(actorId, "asset:create");

        requireValue(input.id, "Asset ID");
        requireValue(input.name, "Asset name");
        requireValue(input.owner, "Asset owner");
        requireValue(input.purpose, "Purpose");

        validateEnum(
            input.category,
            PrivacyCategory,
            "privacy category"
        );

        validateEnum(
            input.legalBasis,
            LegalBasis,
            "legal basis"
        );

        const retentionDays = input.retentionDays ?? 365;

        if (
            !Number.isSafeInteger(retentionDays) ||
            retentionDays <= 0
        ) {
            throw new ValidationError("Invalid retention period.");
        }

        const frameworks = input.frameworks ?? [];

        for (const framework of frameworks) {
            if (!FRAMEWORKS.has(framework)) {
                throw new ValidationError(
                    `Unsupported framework: ${framework}`
                );
            }
        }

        if (
            input.category === PrivacyCategory.SENSITIVE_PERSONAL &&
            input.encrypted !== true
        ) {
            throw new PolicyViolation(
                "Sensitive data requires encryption."
            );
        }

        if (this.assets.has(input.id)) {
            throw new ConflictError("Asset already exists.");
        }

        const asset = {
            ...input,
            retentionDays,
            frameworks: [...new Set(frameworks)],
            encrypted: input.encrypted === true,
            active: true,
            createdAt: new Date().toISOString()
        };

        this.assets.set(input.id, asset);

        this.events.publish({
            type: "ASSET_REGISTERED",
            actor: actorId,
            resource: input.id
        }).catch(error => {
            console.error("Audit event delivery failure:", error.message);
        });

        return asset;
    }

    grantConsent(actorId, input) {
        this.authorize(actorId, "consent:manage");

        requireValue(input.id, "Consent ID");
        requireValue(input.subjectId, "Subject ID");
        requireValue(input.assetId, "Asset ID");
        requireValue(input.purpose, "Purpose");

        const asset = this.assets.get(input.assetId);

        if (!asset || !asset.active) {
            throw new ValidationError("Asset is unavailable.");
        }

        if (asset.legalBasis !== LegalBasis.CONSENT) {
            throw new PolicyViolation(
                "Consent records must match the declared legal basis."
            );
        }

        if (input.purpose !== asset.purpose) {
            throw new PolicyViolation("Purpose mismatch.");
        }

        if (this.consents.has(input.id)) {
            throw new ConflictError("Consent ID already exists.");
        }

        this.consents.set(input.id, {
            ...input,
            status: "GRANTED",
            grantedAt: new Date().toISOString(),
            withdrawnAt: null,
            expiresAt: input.expiresAt ?? null
        });
    }

    withdrawConsent(actorId, consentId) {
        this.authorize(actorId, "consent:manage");

        const consent = this.consents.get(consentId);

        if (!consent) {
            throw new ValidationError("Consent not found.");
        }

        if (consent.status === "WITHDRAWN") {
            throw new ConflictError("Consent already withdrawn.");
        }

        consent.status = "WITHDRAWN";
        consent.withdrawnAt = new Date().toISOString();

        return this.events.publish({
            type: "CONSENT_WITHDRAWN",
            actor: actorId,
            resource: consentId
        });
    }

    canProcess(assetId, subjectId) {
        const asset = this.assets.get(assetId);

        if (!asset || !asset.active) {
            return false;
        }

        if (asset.legalBasis !== LegalBasis.CONSENT) {
            return true;
        }

        return [...this.consents.values()].some(consent => {
            return (
                consent.assetId === assetId &&
                consent.subjectId === subjectId &&
                consent.purpose === asset.purpose &&
                consent.status === "GRANTED" &&
                (
                    consent.expiresAt === null ||
                    Date.now() < Date.parse(consent.expiresAt)
                )
            );
        });
    }

    readAsset(actorId, assetId, subjectId) {
        this.authorize(actorId, "asset:read");

        const asset = this.assets.get(assetId);

        if (!asset) {
            throw new ValidationError("Asset not found.");
        }

        if (!this.canProcess(assetId, subjectId)) {
            throw new PolicyViolation(
                "No valid processing authorization."
            );
        }

        this.audit.append(
            actorId,
            "ASSET_READ",
            assetId
        );

        return Object.freeze({ ...asset });
    }

    addPolicy(actorId, policy) {
        this.authorize(actorId, "policy:manage");

        requireValue(policy.id, "Policy ID");
        requireValue(policy.name, "Policy name");

        if (this.policies.has(policy.id)) {
            throw new ConflictError("Policy already exists.");
        }

        this.policies.set(policy.id, {
            ...policy,
            enabled: policy.enabled !== false
        });
    }

    evaluateAsset(assetId) {
        const asset = this.assets.get(assetId);

        if (!asset) {
            throw new ValidationError("Asset not found.");
        }

        const findings = [];

        const add = (severity, rule, description) => {
            findings.push({
                id: crypto.randomUUID(),
                assetId,
                severity,
                rule,
                description,
                createdAt: new Date().toISOString(),
                resolved: false
            });
        };

        if (!asset.encrypted) {
            add(
                "CRITICAL",
                "ENCRYPTION_REQUIRED",
                "Asset is not encrypted."
            );
        }

        if (asset.frameworks.length === 0) {
            add(
                "MEDIUM",
                "FRAMEWORK_MAPPING",
                "No regulatory framework has been mapped."
            );
        }

        if (asset.retentionDays > 3650) {
            add(
                "MEDIUM",
                "RETENTION_REVIEW",
                "Retention exceeds ten years."
            );
        }

        if (
            asset.category === PrivacyCategory.SENSITIVE_PERSONAL &&
            asset.legalBasis === LegalBasis.LEGITIMATE_INTEREST
        ) {
            add(
                "HIGH",
                "LEGAL_BASIS_REVIEW",
                "Additional necessity and legal assessment required."
            );
        }

        this.findings.push(...findings);

        return findings;
    }

    submitRequest(actorId, input) {
        this.authorize(actorId, "request:manage");

        requireValue(input.subjectId, "Subject ID");

        validateEnum(input.type, RequestType, "request type");

        const request = {
            id: crypto.randomUUID(),
            subjectId: input.subjectId,
            type: input.type,
            status: RequestStatus.RECEIVED,
            receivedAt: new Date().toISOString(),
            deadline: new Date(
                Date.now() + (input.deadlineDays ?? 30) * 86400000
            ).toISOString(),
            version: 1
        };

        if (
            !Number.isSafeInteger(input.deadlineDays ?? 30) ||
            (input.deadlineDays ?? 30) <= 0
        ) {
            throw new ValidationError("Invalid request deadline.");
        }

        this.requests.set(request.id, request);

        return { ...request };
    }

    async transitionRequest(
        actorId,
        requestId,
        nextStatus,
        expectedVersion
    ) {
        this.authorize(actorId, "request:manage");

        validateEnum(nextStatus, RequestStatus, "request status");

        const request = this.requests.get(requestId);

        if (!request) {
            throw new ValidationError("Request not found.");
        }

        // Optimistic concurrency prevents stale concurrent updates.
        if (request.version !== expectedVersion) {
            throw new ConflictError("Request version conflict.");
        }

        if (!TRANSITIONS[request.status].includes(nextStatus)) {
            throw new PolicyViolation("Invalid state transition.");
        }

        if (this.processingLocks.has(requestId)) {
            throw new ConflictError("Request is being processed.");
        }

        this.processingLocks.add(requestId);

        try {
            request.status = nextStatus;
            request.version++;

            await this.events.publish({
                type: "REQUEST_TRANSITIONED",
                actor: actorId,
                resource: requestId,
                details: {
                    status: nextStatus,
                    version: request.version
                }
            });

            return { ...request };
        } finally {
            this.processingLocks.delete(requestId);
        }
    }

    enforceRetention(actorId) {
        this.authorize(actorId, "retention:manage");

        const now = Date.now();
        const expired = [];

        for (const asset of this.assets.values()) {
            const expiration =
                Date.parse(asset.createdAt) +
                asset.retentionDays * 86400000;

            if (asset.active && now > expiration) {
                asset.active = false;
                expired.push(asset.id);

                this.audit.append(
                    actorId,
                    "RETENTION_EXPIRED",
                    asset.id
                );
            }
        }

        return expired;
    }

    report(actorId) {
        this.authorize(actorId, "report:read");

        const countBy = (items, property, values) => {
            return Object.fromEntries(
                values.map(value => [
                    value,
                    items.filter(item => item[property] === value).length
                ])
            );
        };

        return {
            generatedAt: new Date().toISOString(),
            totalAssets: this.assets.size,
            activeAssets: [...this.assets.values()]
                .filter(asset => asset.active).length,
            privacyCategories: countBy(
                [...this.assets.values()],
                "category",
                Object.values(PrivacyCategory)
            ),
            requestStates: countBy(
                [...this.requests.values()],
                "status",
                Object.values(RequestStatus)
            ),
            openFindings: this.findings
                .filter(finding => !finding.resolved).length,
            auditIntegrity: this.audit.verify()
        };
    }
}

async function main() {
    const engine = new ComplianceEngine();

    engine.registerUser({
        id: "admin-01",
        role: "COMPLIANCE_ADMIN"
    });

    engine.registerUser({
        id: "analyst-01",
        role: "ANALYST"
    });

    engine.registerAsset("admin-01", {
        id: "ASSET-100",
        name: "Customer Identity Records",
        owner: "Data Governance Office",
        category: PrivacyCategory.PERSONAL,
        purpose: "Customer account administration",
        legalBasis: LegalBasis.CONSENT,
        frameworks: ["GDPR", "DPDPA"],
        retentionDays: 730,
        encrypted: true
    });

    engine.grantConsent("admin-01", {
        id: "CONSENT-100",
        subjectId: "SUBJECT-100",
        assetId: "ASSET-100",
        purpose: "Customer account administration"
    });

    console.log(
        "Authorized access:",
        engine.readAsset(
            "analyst-01",
            "ASSET-100",
            "SUBJECT-100"
        ).name
    );

    const request = engine.submitRequest("admin-01", {
        subjectId: "SUBJECT-100",
        type: RequestType.ACCESS,
        deadlineDays: 30
    });

    let updated = await engine.transitionRequest(
        "admin-01",
        request.id,
        RequestStatus.VERIFIED,
        1
    );

    updated = await engine.transitionRequest(
        "admin-01",
        request.id,
        RequestStatus.IN_PROGRESS,
        updated.version
    );

    updated = await engine.transitionRequest(
        "admin-01",
        request.id,
        RequestStatus.COMPLETED,
        updated.version
    );

    await engine.withdrawConsent(
        "admin-01",
        "CONSENT-100"
    );

    try {
        engine.readAsset(
            "analyst-01",
            "ASSET-100",
            "SUBJECT-100"
        );
    } catch (error) {
        console.log("Expected denial:", error.message);
    }

    console.log(
        "Findings:",
        engine.evaluateAsset("ASSET-100")
    );

    console.log(
        "Governance report:",
        JSON.stringify(
            engine.report("admin-01"),
            null,
            2
        )
    );

    console.log(
        "Audit integrity:",
        engine.audit.verify()
    );

    // A second transition using an obsolete version must fail.
    try {
        await engine.transitionRequest(
            "admin-01",
            request.id,
            RequestStatus.REJECTED,
            1
        );
    } catch (error) {
        console.log("Expected concurrency protection:", error.message);
    }

    console.log("Final request:", updated);
}

main().catch(error => {
    console.error("Compliance engine failure:", error);
    process.exitCode = 1;
});
