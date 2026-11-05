"use strict";

/*
 * Cloud Security Fundamentals
 * Event-driven cloud security policy evaluation.
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library only.
 */

const EventEmitter = require("node:events");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");

const ServiceModel = Object.freeze({
    IAAS: "IaaS",
    PAAS: "PaaS",
    SAAS: "SaaS"
});

const Severity = Object.freeze({
    CRITICAL: 4,
    HIGH: 3,
    MEDIUM: 2,
    LOW: 1
});

const Responsibility = Object.freeze({
    CUSTOMER: "CUSTOMER",
    PROVIDER: "PROVIDER",
    SHARED: "SHARED"
});

const AssetState = Object.freeze({
    ACTIVE: "ACTIVE",
    QUARANTINED: "QUARANTINED",
    RETIRED: "RETIRED"
});

class SecurityError extends Error {
    constructor(message) {
        super(message);
        this.name = "SecurityError";
    }
}

class CloudAsset {
    constructor({
        id,
        name,
        serviceModel,
        environment,
        configuration
    }) {
        if (!id || !name) {
            throw new SecurityError("Asset ID and name are required");
        }

        if (!Object.values(ServiceModel).includes(serviceModel)) {
            throw new SecurityError("Invalid cloud service model");
        }

        if (!["development", "testing", "staging", "production"]
            .includes(environment)) {
            throw new SecurityError("Invalid environment");
        }

        this.id = id;
        this.name = name;
        this.serviceModel = serviceModel;
        this.environment = environment;

        this.configuration = Object.freeze({
            publicAccess: false,
            encryptionAtRest: false,
            encryptionInTransit: false,
            mfa: false,
            logging: false,
            backup: false,
            leastPrivilege: false,
            patching: false,
            ...configuration
        });

        this.state = AssetState.ACTIVE;
        this.version = 1;
        this.createdAt = new Date();
    }

    updateConfiguration(changes) {
        if (this.state !== AssetState.ACTIVE) {
            throw new SecurityError(
                "Only active assets can be modified"
            );
        }

        this.configuration = Object.freeze({
            ...this.configuration,
            ...changes
        });

        this.version++;
    }
}

class ResponsibilityRegistry {
    constructor() {
        this.controls = new Map([
            ["PHYSICAL_SECURITY", {
                owner: Responsibility.PROVIDER,
                description: "Data center and physical hardware protection"
            }],
            ["HYPERVISOR", {
                owner: Responsibility.PROVIDER,
                description: "Hypervisor security"
            }],
            ["IDENTITY", {
                owner: Responsibility.SHARED,
                description: "Identity infrastructure and account configuration"
            }],
            ["NETWORK", {
                owner: Responsibility.SHARED,
                description: "Network infrastructure and customer traffic rules"
            }],
            ["DATA_PROTECTION", {
                owner: Responsibility.SHARED,
                description: "Data platform protection and customer configuration"
            }],
            ["APPLICATION_SECURITY", {
                owner: Responsibility.CUSTOMER,
                description: "Application security and secure development"
            }],
            ["GUEST_OS", {
                owner: Responsibility.CUSTOMER,
                description: "Guest operating system maintenance"
            }],
            ["MONITORING", {
                owner: Responsibility.SHARED,
                description: "Provider telemetry and customer monitoring configuration"
            }]
        ]);
    }

    get(controlId) {
        const control = this.controls.get(controlId);

        if (!control) {
            throw new SecurityError(
                `Unknown responsibility control: ${controlId}`
            );
        }

        return control;
    }
}

class SecurityRule {
    constructor({
        id,
        description,
        severity,
        responsibility,
        appliesTo,
        evaluate,
        remediation
    }) {
        this.id = id;
        this.description = description;
        this.severity = severity;
        this.responsibility = responsibility;
        this.appliesTo = new Set(appliesTo);
        this.evaluate = evaluate;
        this.remediation = remediation;
    }

    applies(asset) {
        return this.appliesTo.has(asset.serviceModel);
    }
}

class SecurityPolicyEngine extends EventEmitter {
    constructor() {
        super();

        this.rules = [];
        this.results = new Map();

        this.registerDefaultRules();
    }

    registerRule(rule) {
        if (!(rule instanceof SecurityRule)) {
            throw new SecurityError("Invalid security rule");
        }

        if (this.rules.some(existing => existing.id === rule.id)) {
            throw new SecurityError(
                `Duplicate security rule: ${rule.id}`
            );
        }

        this.rules.push(rule);
    }

    registerDefaultRules() {
        const allModels = Object.values(ServiceModel);

        this.registerRule(new SecurityRule({
            id: "ENCRYPTION_AT_REST",
            description: "Storage encryption must be enabled",
            severity: Severity.HIGH,
            responsibility: Responsibility.CUSTOMER,
            appliesTo: allModels,
            evaluate: asset => asset.configuration.encryptionAtRest,
            remediation: "Enable encryption at rest."
        }));

        this.registerRule(new SecurityRule({
            id: "ENCRYPTION_IN_TRANSIT",
            description: "Network communications must be encrypted",
            severity: Severity.HIGH,
            responsibility: Responsibility.SHARED,
            appliesTo: allModels,
            evaluate: asset => asset.configuration.encryptionInTransit,
            remediation: "Require TLS for data in transit."
        }));

        this.registerRule(new SecurityRule({
            id: "MFA_REQUIRED",
            description: "Multi-factor authentication must be enabled",
            severity: Severity.CRITICAL,
            responsibility: Responsibility.CUSTOMER,
            appliesTo: allModels,
            evaluate: asset => asset.configuration.mfa,
            remediation: "Enable MFA for users and privileged identities."
        }));

        this.registerRule(new SecurityRule({
            id: "LOGGING_REQUIRED",
            description: "Security event logging must be enabled",
            severity: Severity.HIGH,
            responsibility: Responsibility.SHARED,
            appliesTo: allModels,
            evaluate: asset => asset.configuration.logging,
            remediation: "Enable centralized security logging."
        }));

        this.registerRule(new SecurityRule({
            id: "BACKUP_REQUIRED",
            description: "Protected backups must be configured",
            severity: Severity.HIGH,
            responsibility: Responsibility.SHARED,
            appliesTo: allModels,
            evaluate: asset => asset.configuration.backup,
            remediation: "Configure protected backups and recovery testing."
        }));

        this.registerRule(new SecurityRule({
            id: "LEAST_PRIVILEGE",
            description: "Access must follow least privilege",
            severity: Severity.HIGH,
            responsibility: Responsibility.CUSTOMER,
            appliesTo: allModels,
            evaluate: asset => asset.configuration.leastPrivilege,
            remediation: "Remove excessive permissions."
        }));

        this.registerRule(new SecurityRule({
            id: "PRODUCTION_PUBLIC_ACCESS",
            description: "Production assets must not be unintentionally public",
            severity: Severity.CRITICAL,
            responsibility: Responsibility.CUSTOMER,
            appliesTo: allModels,
            evaluate: asset => !(
                asset.environment === "production" &&
                asset.configuration.publicAccess
            ),
            remediation: "Restrict public access using private endpoints and network policies."
        }));

        this.registerRule(new SecurityRule({
            id: "GUEST_OS_PATCHING",
            description: "IaaS guest operating systems must be patched",
            severity: Severity.HIGH,
            responsibility: Responsibility.CUSTOMER,
            appliesTo: [ServiceModel.IAAS],
            evaluate: asset => asset.configuration.patching,
            remediation: "Apply and verify operating system security patches."
        }));
    }

    async evaluateAsset(asset) {
        if (!(asset instanceof CloudAsset)) {
            throw new SecurityError("Invalid cloud asset");
        }

        if (asset.state !== AssetState.ACTIVE) {
            throw new SecurityError(
                `Asset ${asset.id} is not active`
            );
        }

        const evaluatedVersion = asset.version;

        // Simulate asynchronous policy evaluation.
        const findings = await Promise.all(
            this.rules
                .filter(rule => rule.applies(asset))
                .map(async rule => {
                    await Promise.resolve();

                    const passed = Boolean(rule.evaluate(asset));

                    return Object.freeze({
                        ruleId: rule.id,
                        description: rule.description,
                        responsibility: rule.responsibility,
                        severity: rule.severity,
                        compliant: passed,
                        remediation: passed ? null : rule.remediation
                    });
                })
        );

        // Avoid storing a result if configuration changed during evaluation.
        if (asset.version !== evaluatedVersion) {
            throw new SecurityError(
                "Asset changed during evaluation; retry required"
            );
        }

        const result = Object.freeze({
            assessmentId: crypto.randomUUID(),
            assetId: asset.id,
            assetVersion: evaluatedVersion,
            evaluatedAt: new Date().toISOString(),
            findings: Object.freeze(findings),
            riskScore: findings
                .filter(item => !item.compliant)
                .reduce((total, item) => total + item.severity, 0),
            compliant: findings.every(item => item.compliant)
        });

        this.results.set(asset.id, result);

        this.emit("assessmentCompleted", result);

        return result;
    }

    getSummary() {
        const summary = {
            assetsAudited: this.results.size,
            compliant: 0,
            nonCompliant: 0,
            findings: 0,
            severity: {
                CRITICAL: 0,
                HIGH: 0,
                MEDIUM: 0,
                LOW: 0
            }
        };

        for (const result of this.results.values()) {
            if (result.compliant) {
                summary.compliant++;
            } else {
                summary.nonCompliant++;
            }

            for (const finding of result.findings) {
                if (!finding.compliant) {
                    summary.findings++;

                    const severityName = Object.keys(Severity)
                        .find(key => Severity[key] === finding.severity);

                    summary.severity[severityName]++;
                }
            }
        }

        return summary;
    }

    async exportResults(filePath) {
        const output = {
            generatedAt: new Date().toISOString(),
            summary: this.getSummary(),
            assessments: Array.from(this.results.values())
        };

        // Restrictive permissions prevent other local users from
        // automatically receiving access to the report on POSIX systems.
        await fs.writeFile(
            filePath,
            JSON.stringify(output, null, 2),
            { mode: 0o600 }
        );
    }
}

class CloudSecurityPlatform {
    constructor() {
        this.assets = new Map();
        this.engine = new SecurityPolicyEngine();

        this.engine.on("assessmentCompleted", result => {
            console.log(
                `[EVENT] Assessment completed: ${result.assetId}, ` +
                `risk=${result.riskScore}`
            );
        });
    }

    register(asset) {
        if (this.assets.has(asset.id)) {
            throw new SecurityError("Duplicate asset registration");
        }

        this.assets.set(asset.id, asset);
    }

    async auditAll() {
        const results = [];

        // Sequential processing provides predictable resource usage.
        for (const asset of this.assets.values()) {
            try {
                results.push(
                    await this.engine.evaluateAsset(asset)
                );
            } catch (error) {
                console.error(
                    `Audit failed for ${asset.id}: ${error.message}`
                );
            }
        }

        return results;
    }

    quarantine(assetId) {
        const asset = this.assets.get(assetId);

        if (!asset) {
            throw new SecurityError("Asset not found");
        }

        if (asset.state !== AssetState.ACTIVE) {
            throw new SecurityError("Asset cannot be quarantined");
        }

        asset.state = AssetState.QUARANTINED;

        console.log(`[SECURITY] Asset ${assetId} quarantined`);
    }
}

async function runTests() {
    const registry = new ResponsibilityRegistry();

    console.assert(
        registry.get("PHYSICAL_SECURITY").owner === Responsibility.PROVIDER
    );

    console.assert(
        registry.get("IDENTITY").owner === Responsibility.SHARED
    );

    const engine = new SecurityPolicyEngine();

    const secureAsset = new CloudAsset({
        id: "TEST-001",
        name: "Secure API",
        serviceModel: ServiceModel.IAAS,
        environment: "production",
        configuration: {
            encryptionAtRest: true,
            encryptionInTransit: true,
            mfa: true,
            logging: true,
            backup: true,
            leastPrivilege: true,
            patching: true
        }
    });

    const result = await engine.evaluateAsset(secureAsset);

    console.assert(result.compliant);
    console.assert(result.riskScore === 0);

    const publicAsset = new CloudAsset({
        id: "TEST-002",
        name: "Exposed storage",
        serviceModel: ServiceModel.SAAS,
        environment: "production",
        configuration: {
            publicAccess: true
        }
    });

    const publicResult = await engine.evaluateAsset(publicAsset);

    console.assert(!publicResult.compliant);

    try {
        new CloudAsset({
            id: "INVALID",
            name: "Invalid",
            serviceModel: "UNKNOWN",
            environment: "production",
            configuration: {}
        });

        throw new Error("Invalid model was accepted");
    } catch (error) {
        if (!(error instanceof SecurityError)) {
            throw error;
        }
    }

    console.log("All JavaScript security tests passed.");
}

async function main() {
    const platform = new CloudSecurityPlatform();

    const assets = [
        new CloudAsset({
            id: "AWS-001",
            name: "Production EC2 server",
            serviceModel: ServiceModel.IAAS,
            environment: "production",
            configuration: {
                encryptionAtRest: true,
                encryptionInTransit: true,
                mfa: true,
                logging: true,
                backup: true,
                leastPrivilege: true,
                patching: true
            }
        }),

        new CloudAsset({
            id: "AZURE-002",
            name: "Managed application",
            serviceModel: ServiceModel.PAAS,
            environment: "production",
            configuration: {
                encryptionAtRest: true,
                encryptionInTransit: true,
                mfa: false,
                logging: true,
                backup: true,
                leastPrivilege: false
            }
        }),

        new CloudAsset({
            id: "SAAS-003",
            name: "Document management service",
            serviceModel: ServiceModel.SAAS,
            environment: "production",
            configuration: {
                encryptionAtRest: true,
                encryptionInTransit: true,
                publicAccess: true,
                mfa: false,
                logging: false,
                backup: false
            }
        })
    ];

    for (const asset of assets) {
        platform.register(asset);
    }

    const results = await platform.auditAll();

    console.log("\nASSESSMENT RESULTS");

    for (const result of results) {
        console.log(
            `${result.assetId}: ${result.compliant ? "COMPLIANT" : "NON-COMPLIANT"}`
        );

        for (const finding of result.findings) {
            if (!finding.compliant) {
                console.log(
                    `  ${finding.ruleId}: ${finding.remediation}`
                );
            }
        }
    }

    console.log("\nSUMMARY");
    console.log(JSON.stringify(platform.engine.getSummary(), null, 2));

    await platform.engine.exportResults("cloud_security_results.json");

    console.log("\nReport saved to cloud_security_results.json");

    await runTests();
}

main().catch(error => {
    console.error("Application failure:", error.message);
    process.exitCode = 1;
});
