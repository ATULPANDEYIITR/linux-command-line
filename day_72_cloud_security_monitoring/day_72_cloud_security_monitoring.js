"use strict";

/*
 * Cloud Security Monitoring
 * Node.js 18+
 *
 * Event-driven monitoring engine featuring:
 * - Structured audit event ingestion
 * - Asynchronous event processing
 * - Sliding-window detection
 * - Authentication anomaly detection
 * - Privilege escalation monitoring
 * - Security alert correlation
 * - Risk-based prioritization
 * - Incident investigation workflows
 * - Append-only hash-chained audit storage
 * - Policy-based access decisions
 * - JSON reporting
 *
 * Dependencies: Node.js standard library only.
 */

const fs = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");
const EventEmitter = require("node:events");


const CONFIG = Object.freeze({
    DATA_DIRECTORY: path.resolve("cloud_security_js"),
    AUDIT_FILE: path.resolve(
        "cloud_security_js",
        "audit.jsonl"
    ),
    INCIDENT_FILE: path.resolve(
        "cloud_security_js",
        "incidents.json"
    ),
    FAILED_LOGIN_LIMIT: 5,
    FAILED_LOGIN_WINDOW_MS: 10 * 60 * 1000,
    PRIVILEGE_LIMIT: 3,
    PRIVILEGE_WINDOW_MS: 15 * 60 * 1000,
    MAX_EVENTS: 100000,
    MAX_EVENT_AGE_MS: 365 * 24 * 60 * 60 * 1000
});


const EVENT_TYPES = new Set([
    "login",
    "logout",
    "failed_login",
    "api_access",
    "permission_change",
    "resource_created",
    "resource_deleted",
    "configuration_change",
    "data_access",
    "network_access",
    "security_group_change",
    "secret_access"
]);


const SEVERITY = Object.freeze({
    LOW: "LOW",
    MEDIUM: "MEDIUM",
    HIGH: "HIGH",
    CRITICAL: "CRITICAL"
});


const INCIDENT_STATUS = Object.freeze({
    OPEN: "OPEN",
    INVESTIGATING: "INVESTIGATING",
    CONTAINED: "CONTAINED",
    RESOLVED: "RESOLVED",
    CLOSED: "CLOSED"
});


const TRANSITIONS = Object.freeze({
    OPEN: ["INVESTIGATING", "CLOSED"],
    INVESTIGATING: ["CONTAINED", "RESOLVED", "CLOSED"],
    CONTAINED: ["INVESTIGATING", "RESOLVED"],
    RESOLVED: ["CLOSED", "INVESTIGATING"],
    CLOSED: []
});


class MonitoringError extends Error {
    constructor(message) {
        super(message);
        this.name = "MonitoringError";
    }
}


class ValidationError extends MonitoringError {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}


class IntegrityError extends MonitoringError {
    constructor(message) {
        super(message);
        this.name = "IntegrityError";
    }
}


function generateId() {
    return crypto.randomUUID();
}


function sha256(value) {
    return crypto
        .createHash("sha256")
        .update(value)
        .digest("hex");
}


function classifySeverity(score) {
    if (score >= 90) return SEVERITY.CRITICAL;
    if (score >= 70) return SEVERITY.HIGH;
    if (score >= 40) return SEVERITY.MEDIUM;
    return SEVERITY.LOW;
}


function validateEvent(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
        throw new ValidationError("Event must be an object.");
    }

    const required = [
        "timestamp",
        "eventType",
        "userId",
        "sourceIp",
        "resource",
        "action",
        "success",
        "region"
    ];

    for (const field of required) {
        if (!(field in raw)) {
            throw new ValidationError(
                `Missing field: ${field}`
            );
        }
    }

    if (!EVENT_TYPES.has(raw.eventType)) {
        throw new ValidationError(
            "Unsupported event type."
        );
    }

    for (const field of [
        "userId",
        "resource",
        "action",
        "region"
    ]) {
        if (
            typeof raw[field] !== "string" ||
            raw[field].trim().length === 0 ||
            raw[field].length > 256
        ) {
            throw new ValidationError(
                `Invalid ${field}.`
            );
        }
    }

    if (typeof raw.success !== "boolean") {
        throw new ValidationError(
            "success must be a boolean."
        );
    }

    if (
        !crypto.isIP(raw.sourceIp) ||
        raw.sourceIp.length > 45
    ) {
        throw new ValidationError("Invalid IP address.");
    }

    const timestamp = Date.parse(raw.timestamp);

    if (!Number.isFinite(timestamp)) {
        throw new ValidationError("Invalid timestamp.");
    }

    const now = Date.now();

    if (timestamp > now + 5 * 60 * 1000) {
        throw new ValidationError(
            "Event timestamp is too far in the future."
        );
    }

    if (now - timestamp > CONFIG.MAX_EVENT_AGE_MS) {
        throw new ValidationError(
            "Event exceeds the accepted retention window."
        );
    }

    const metadata = raw.metadata ?? {};

    if (
        typeof metadata !== "object" ||
        metadata === null ||
        Array.isArray(metadata) ||
        Object.keys(metadata).length > 50
    ) {
        throw new ValidationError(
            "Invalid event metadata."
        );
    }

    return Object.freeze({
        eventId: raw.eventId ?? generateId(),
        timestamp: new Date(timestamp).toISOString(),
        eventType: raw.eventType,
        userId: raw.userId,
        sourceIp: raw.sourceIp,
        resource: raw.resource,
        action: raw.action,
        success: raw.success,
        region: raw.region,
        metadata: structuredClone(metadata)
    });
}


// ---------------------------------------------------------
// ASYNCHRONOUS AUDIT STORAGE
// ---------------------------------------------------------

class AuditRepository {

    constructor(filePath) {
        this.filePath = filePath;
        this.previousHash = "GENESIS";
        this.eventIds = new Set();
        this.count = 0;
        this.queue = Promise.resolve();
    }

    async initialize() {
        await fs.mkdir(
            path.dirname(this.filePath),
            { recursive: true }
        );

        try {
            await fs.access(this.filePath);
        } catch {
            await fs.writeFile(
                this.filePath,
                "",
                { flag: "wx" }
            );
        }

        await this.verifyIntegrity();

        const content = await fs.readFile(
            this.filePath,
            "utf8"
        );

        for (const line of content.split("\n")) {
            if (!line.trim()) continue;

            const record = JSON.parse(line);
            this.eventIds.add(record.event.eventId);
            this.count++;
        }
    }

    append(event) {
        // Serialize concurrent writes to preserve hash-chain order.
        const operation = this.queue.then(
            () => this._append(event)
        );

        this.queue = operation.catch(() => {});

        return operation;
    }

    async _append(event) {
        if (this.eventIds.has(event.eventId)) {
            throw new ValidationError(
                "Duplicate event identifier."
            );
        }

        if (this.count >= CONFIG.MAX_EVENTS) {
            throw new MonitoringError(
                "Audit storage capacity reached."
            );
        }

        const canonical = JSON.stringify({
            previousHash: this.previousHash,
            event
        });

        const recordHash = sha256(canonical);

        const record = {
            previousHash: this.previousHash,
            event,
            recordHash
        };

        await fs.appendFile(
            this.filePath,
            JSON.stringify(record) + "\n",
            { encoding: "utf8", flag: "a" }
        );

        this.previousHash = recordHash;
        this.eventIds.add(event.eventId);
        this.count++;

        return recordHash;
    }

    async verifyIntegrity() {
        let previous = "GENESIS";

        const content = await fs.readFile(
            this.filePath,
            "utf8"
        );

        const lines = content.split("\n");

        for (let index = 0; index < lines.length; index++) {
            const line = lines[index];

            if (!line.trim()) continue;

            let record;

            try {
                record = JSON.parse(line);
            } catch {
                throw new IntegrityError(
                    `Invalid JSON at line ${index + 1}.`
                );
            }

            if (record.previousHash !== previous) {
                throw new IntegrityError(
                    `Broken chain at line ${index + 1}.`
                );
            }

            const expected = sha256(
                JSON.stringify({
                    previousHash: previous,
                    event: record.event
                })
            );

            if (expected !== record.recordHash) {
                throw new IntegrityError(
                    `Tampering detected at line ${index + 1}.`
                );
            }

            previous = record.recordHash;
        }

        this.previousHash = previous;
        return true;
    }
}


// ---------------------------------------------------------
// SLIDING WINDOW DETECTION
// ---------------------------------------------------------

class SlidingWindowCounter {

    constructor(windowMilliseconds) {
        this.windowMilliseconds = windowMilliseconds;
        this.records = new Map();
    }

    add(key, timestamp) {
        const values = this.records.get(key) ?? [];

        values.push(timestamp);

        const cutoff = timestamp - this.windowMilliseconds;

        let firstValid = 0;

        while (
            firstValid < values.length &&
            values[firstValid] < cutoff
        ) {
            firstValid++;
        }

        const remaining = values.slice(firstValid);

        this.records.set(key, remaining);

        return remaining.length;
    }
}


// ---------------------------------------------------------
// BASELINE LEARNING
// ---------------------------------------------------------

class UserBaseline {

    constructor() {
        this.knownIPs = new Map();
        this.knownHours = new Map();
    }

    observe(event) {
        if (!event.success) return;

        if (!this.knownIPs.has(event.userId)) {
            this.knownIPs.set(event.userId, new Set());
        }

        if (!this.knownHours.has(event.userId)) {
            this.knownHours.set(event.userId, new Set());
        }

        this.knownIPs.get(event.userId).add(event.sourceIp);

        this.knownHours.get(event.userId).add(
            new Date(event.timestamp).getUTCHours()
        );
    }

    unfamiliarIP(event) {
        const known = this.knownIPs.get(event.userId);

        return (
            known &&
            known.size > 0 &&
            !known.has(event.sourceIp)
        );
    }

    unusualHour(event) {
        const known = this.knownHours.get(event.userId);

        if (!known || known.size === 0) return false;

        const hour = new Date(
            event.timestamp
        ).getUTCHours();

        return !known.has(hour);
    }
}


// ---------------------------------------------------------
// ALERT CORRELATION
// ---------------------------------------------------------

class AlertCorrelator {

    constructor() {
        this.alerts = [];
        this.groups = new Map();
    }

    add(alert) {
        const key = `${alert.userId}:${alert.ruleId}`;

        if (!this.groups.has(key)) {
            this.groups.set(key, {
                userId: alert.userId,
                ruleId: alert.ruleId,
                count: 0,
                alertIds: [],
                highestScore: 0
            });
        }

        const group = this.groups.get(key);

        group.count++;
        group.alertIds.push(alert.alertId);
        group.highestScore = Math.max(
            group.highestScore,
            alert.riskScore
        );

        this.alerts.push(alert);
    }

    report() {
        return [...this.groups.values()]
            .sort(
                (a, b) => b.highestScore - a.highestScore
            );
    }
}


// ---------------------------------------------------------
// DETECTION SERVICE
// ---------------------------------------------------------

class DetectionService {

    constructor() {
        this.failedLogins = new SlidingWindowCounter(
            CONFIG.FAILED_LOGIN_WINDOW_MS
        );

        this.permissionChanges = new SlidingWindowCounter(
            CONFIG.PRIVILEGE_WINDOW_MS
        );

        this.baseline = new UserBaseline();
        this.correlator = new AlertCorrelator();
    }

    createAlert(event, ruleId, score, description) {
        const alert = Object.freeze({
            alertId: generateId(),
            ruleId,
            timestamp: event.timestamp,
            userId: event.userId,
            severity: classifySeverity(score),
            riskScore: score,
            description,
            eventIds: [event.eventId],
            sourceIp: event.sourceIp,
            resource: event.resource
        });

        this.correlator.add(alert);

        return alert;
    }

    evaluate(event) {
        const alerts = [];
        const timestamp = Date.parse(event.timestamp);

        if (event.eventType === "failed_login") {
            const count = this.failedLogins.add(
                event.userId,
                timestamp
            );

            if (count >= CONFIG.FAILED_LOGIN_LIMIT) {
                alerts.push(
                    this.createAlert(
                        event,
                        "AUTH-001",
                        85,
                        `Repeated failed authentication: ${count} attempts`
                    )
                );
            }
        }

        if (event.eventType === "permission_change") {
            const count = this.permissionChanges.add(
                event.userId,
                timestamp
            );

            if (count >= CONFIG.PRIVILEGE_LIMIT) {
                alerts.push(
                    this.createAlert(
                        event,
                        "IAM-001",
                        95,
                        `Rapid privilege changes: ${count}`
                    )
                );
            }

            if (event.metadata.approvedChange !== true) {
                alerts.push(
                    this.createAlert(
                        event,
                        "IAM-002",
                        90,
                        "Permission modification lacks approval."
                    )
                );
            }
        }

        if (
            event.eventType === "secret_access" &&
            event.success &&
            event.metadata.approved !== true
        ) {
            alerts.push(
                this.createAlert(
                    event,
                    "DATA-001",
                    95,
                    "Unapproved access to a sensitive secret."
                )
            );
        }

        if (
            event.success &&
            this.baseline.unfamiliarIP(event)
        ) {
            alerts.push(
                this.createAlert(
                    event,
                    "ANOM-001",
                    75,
                    "Access from an unfamiliar IP address."
                )
            );
        }

        if (
            event.success &&
            this.baseline.unusualHour(event)
        ) {
            alerts.push(
                this.createAlert(
                    event,
                    "ANOM-002",
                    65,
                    "Access outside normal activity hours."
                )
            );
        }

        this.baseline.observe(event);

        return alerts;
    }
}


// ---------------------------------------------------------
// INCIDENT DOMAIN
// ---------------------------------------------------------

class SecurityIncident {

    constructor(alert) {
        this.incidentId = generateId();
        this.title = alert.description;
        this.severity = alert.severity;
        this.status = INCIDENT_STATUS.OPEN;
        this.createdAt = alert.timestamp;
        this.updatedAt = alert.timestamp;
        this.alertIds = [alert.alertId];
        this.assignedTo = null;
        this.notes = [];
        this.evidence = [];
    }

    transition(nextStatus) {
        const allowed = TRANSITIONS[this.status];

        if (!allowed.includes(nextStatus)) {
            throw new MonitoringError(
                `Invalid incident transition: ${this.status} -> ${nextStatus}`
            );
        }

        this.status = nextStatus;
        this.updatedAt = new Date().toISOString();
    }

    assign(analystId) {
        if (this.status === INCIDENT_STATUS.CLOSED) {
            throw new MonitoringError(
                "Closed incidents cannot be reassigned."
            );
        }

        if (
            typeof analystId !== "string" ||
            !analystId.trim()
        ) {
            throw new ValidationError(
                "Valid analyst identifier required."
            );
        }

        this.assignedTo = analystId;
    }

    addNote(note) {
        if (
            typeof note !== "string" ||
            !note.trim() ||
            note.length > 5000
        ) {
            throw new ValidationError(
                "Invalid investigation note."
            );
        }

        if (this.status === INCIDENT_STATUS.CLOSED) {
            throw new MonitoringError(
                "Closed incidents cannot be modified."
            );
        }

        this.notes.push({
            note,
            timestamp: new Date().toISOString()
        });
    }

    addEvidence(content) {
        if (
            typeof content !== "string" ||
            !content.length
        ) {
            throw new ValidationError(
                "Evidence must contain data."
            );
        }

        if (this.status === INCIDENT_STATUS.CLOSED) {
            throw new MonitoringError(
                "Closed incidents cannot accept evidence."
            );
        }

        this.evidence.push({
            hash: sha256(content),
            timestamp: new Date().toISOString()
        });
    }
}


// ---------------------------------------------------------
// EVENT-DRIVEN MONITOR
// ---------------------------------------------------------

class CloudSecurityMonitor extends EventEmitter {

    constructor() {
        super();

        this.audit = new AuditRepository(CONFIG.AUDIT_FILE);
        this.detector = new DetectionService();
        this.incidents = new Map();
        this.processing = Promise.resolve();
        this.processedCount = 0;
    }

    async initialize() {
        await this.audit.initialize();

        this.on("securityAlert", alert => {
            const incident = new SecurityIncident(alert);

            this.incidents.set(
                incident.incidentId,
                incident
            );

            console.log(
                `[ALERT] ${alert.severity} ${alert.ruleId}: ` +
                alert.description
            );
        });
    }

    ingest(raw) {
        const operation = this.processing.then(
            () => this._ingest(raw)
        );

        this.processing = operation.catch(() => {});

        return operation;
    }

    async _ingest(raw) {
        const event = validateEvent(raw);

        // Preserve the audit record before detection.
        await this.audit.append(event);

        const alerts = this.detector.evaluate(event);

        for (const alert of alerts) {
            this.emit("securityAlert", alert);
        }

        this.processedCount++;

        this.emit("eventProcessed", {
            eventId: event.eventId,
            alertCount: alerts.length
        });

        return alerts;
    }

    async ingestBatch(events) {
        const results = [];

        for (const event of events) {
            try {
                results.push(...await this.ingest(event));
            } catch (error) {
                this.emit("ingestionError", {
                    message: error.message
                });
            }
        }

        return results;
    }

    report() {
        const severity = new Map();

        for (const alert of this.detector.correlator.alerts) {
            severity.set(
                alert.severity,
                (severity.get(alert.severity) ?? 0) + 1
            );
        }

        return {
            processedEvents: this.processedCount,
            totalAlerts: this.detector.correlator.alerts.length,
            totalIncidents: this.incidents.size,
            alertsBySeverity: Object.fromEntries(severity),
            correlatedGroups: this.detector.correlator.report(),
            incidents: [...this.incidents.values()].map(
                incident => ({
                    incidentId: incident.incidentId,
                    severity: incident.severity,
                    status: incident.status,
                    assignedTo: incident.assignedTo
                })
            )
        };
    }

    async saveIncidents() {
        const data = JSON.stringify(
            [...this.incidents.values()],
            null,
            2
        );

        const temporary = CONFIG.INCIDENT_FILE + ".tmp";

        await fs.writeFile(
            temporary,
            data,
            { mode: 0o600 }
        );

        await fs.rename(
            temporary,
            CONFIG.INCIDENT_FILE
        );
    }
}


// ---------------------------------------------------------
// SAMPLE EVENTS
// ---------------------------------------------------------

function sampleEvents() {
    const now = Date.now();

    const timestamp = offset =>
        new Date(now + offset).toISOString();

    const records = [];

    for (let i = 0; i < 3; i++) {
        records.push({
            timestamp: timestamp(-3 * 86400000 + i * 3600000),
            eventType: "login",
            userId: "cloud-admin",
            sourceIp: "10.10.1.10",
            resource: "identity-service",
            action: "authenticate",
            success: true,
            region: "ap-south-1",
            metadata: { mfa: true }
        });
    }

    for (let i = 0; i < 6; i++) {
        records.push({
            timestamp: timestamp(i * 30000),
            eventType: "failed_login",
            userId: "cloud-admin",
            sourceIp: "203.0.113.25",
            resource: "identity-service",
            action: "authenticate",
            success: false,
            region: "ap-south-1",
            metadata: { reason: "invalid_credentials" }
        });
    }

    records.push({
        timestamp: timestamp(400000),
        eventType: "permission_change",
        userId: "cloud-admin",
        sourceIp: "203.0.113.25",
        resource: "production-iam",
        action: "grant_admin",
        success: true,
        region: "ap-south-1",
        metadata: { approvedChange: false }
    });

    records.push({
        timestamp: timestamp(410000),
        eventType: "secret_access",
        userId: "service-account",
        sourceIp: "198.51.100.40",
        resource: "production/database/password",
        action: "read_secret",
        success: true,
        region: "ap-south-1",
        metadata: { approved: false }
    });

    return records;
}


// ---------------------------------------------------------
// TESTS
// ---------------------------------------------------------

async function runTests() {
    const monitor = new CloudSecurityMonitor();

    await monitor.initialize();

    const alerts = await monitor.ingestBatch(
        sampleEvents()
    );

    if (monitor.processedCount !== 11) {
        throw new Error("Event count test failed.");
    }

    if (alerts.length < 3) {
        throw new Error("Detection test failed.");
    }

    await monitor.audit.verifyIntegrity();

    const incident = monitor.incidents.values().next().value;

    incident.transition(INCIDENT_STATUS.INVESTIGATING);

    let rejected = false;

    try {
        incident.transition(INCIDENT_STATUS.OPEN);
    } catch {
        rejected = true;
    }

    if (!rejected) {
        throw new Error("Transition validation failed.");
    }

    rejected = false;

    try {
        validateEvent({
            eventType: "unknown"
        });
    } catch {
        rejected = true;
    }

    if (!rejected) {
        throw new Error("Event validation failed.");
    }

    console.log("All JavaScript monitoring tests passed.");

    return monitor;
}


// ---------------------------------------------------------
// APPLICATION ENTRY POINT
// ---------------------------------------------------------

async function main() {
    const monitor = await runTests();

    for (const incident of monitor.incidents.values()) {
        incident.assign("soc-analyst-01");

        incident.addNote(
            "Initial triage completed. Audit evidence retained."
        );

        incident.transition(
            INCIDENT_STATUS.INVESTIGATING
        );
    }

    await monitor.saveIncidents();

    console.log("\nCLOUD SECURITY MONITORING REPORT");

    console.log(
        JSON.stringify(
            monitor.report(),
            null,
            2
        )
    );

    console.log("\nAudit integrity:", 
        await monitor.audit.verifyIntegrity()
    );
}


if (require.main === module) {
    main().catch(error => {
        console.error("Monitoring failure:", error.message);
        process.exitCode = 1;
    });
}


module.exports = {
    CloudSecurityMonitor,
    SecurityIncident,
    DetectionService,
    validateEvent,
    classifySeverity
};
