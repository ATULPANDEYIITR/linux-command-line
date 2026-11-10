"use strict";

/*
 * Key Management and Secrets Lifecycle Engine
 *
 * Node.js 18+
 *
 * Implements:
 * - AES-256-GCM encryption and authentication
 * - Cryptographically secure key generation
 * - Key versioning and rotation
 * - Envelope encryption
 * - Secret storage and re-encryption
 * - Event-driven audit logging
 * - Role-based authorization
 * - Simulated HSM integration
 * - Key revocation and access policies
 *
 * Production deployment should use an external KMS/HSM,
 * persistent encrypted storage and independent access controls.
 */

const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");

const KeyStatus = Object.freeze({
    ACTIVE: "ACTIVE",
    ROTATED: "ROTATED",
    DISABLED: "DISABLED",
    REVOKED: "REVOKED",
    EXPIRED: "EXPIRED"
});

const KeyPurpose = Object.freeze({
    ENCRYPTION: "ENCRYPTION",
    SIGNING: "SIGNING",
    HMAC: "HMAC",
    KEY_ENCRYPTION: "KEY_ENCRYPTION"
});

const Role = Object.freeze({
    ADMIN: "ADMIN",
    CRYPTO_OPERATOR: "CRYPTO_OPERATOR",
    APPLICATION: "APPLICATION",
    AUDITOR: "AUDITOR"
});

class SecurityError extends Error {}
class NotFoundError extends Error {}
class StateError extends Error {}

class AuditService extends EventEmitter {
    constructor() {
        super();
        this.events = [];

        this.on("audit", event => {
            this.events.push(
                Object.freeze({
                    timestamp: new Date().toISOString(),
                    ...event
                })
            );
        });
    }

    record(actor, action, keyId, outcome, details = "") {
        this.emit("audit", {
            actor,
            action,
            keyId,
            outcome,
            details
        });
    }
}

class SimulatedHSM {
    generateKey() {
        return crypto.randomBytes(32);
    }

    fingerprint(key) {
        return crypto
            .createHash("sha256")
            .update(key)
            .digest("hex");
    }
}

class KeyVersion {
    constructor({
        keyId,
        version,
        purpose,
        material,
        expiresAt,
        hardwareProtected
    }) {
        this.keyId = keyId;
        this.version = version;
        this.purpose = purpose;
        this.material = Buffer.from(material);
        this.createdAt = new Date();
        this.expiresAt = expiresAt;
        this.hardwareProtected = hardwareProtected;
        this.status = KeyStatus.ACTIVE;
    }

    metadata() {
        return {
            keyId: this.keyId,
            version: this.version,
            purpose: this.purpose,
            createdAt: this.createdAt.toISOString(),
            expiresAt: this.expiresAt.toISOString(),
            status: this.status,
            hardwareProtected: this.hardwareProtected
        };
    }
}

class KeyManager {
    constructor({
        rotationDays = 90,
        hsm = new SimulatedHSM()
    } = {}) {
        if (!Number.isInteger(rotationDays) ||
            rotationDays < 1) {
            throw new TypeError(
                "Rotation period must be positive"
            );
        }

        this.rotationDays = rotationDays;
        this.hsm = hsm;
        this.keys = new Map();
        this.audit = new AuditService();
    }

    authorize(principal, allowedRoles) {
        if (!principal ||
            !allowedRoles.includes(principal.role)) {
            throw new SecurityError(
                "Operation not authorized"
            );
        }
    }

    createKey(principal, purpose) {
        this.authorize(principal, [
            Role.ADMIN,
            Role.CRYPTO_OPERATOR
        ]);

        if (!Object.values(KeyPurpose).includes(purpose)) {
            throw new TypeError("Invalid key purpose");
        }

        const keyId = crypto.randomUUID();

        const key = new KeyVersion({
            keyId,
            version: 1,
            purpose,
            material: this.hsm.generateKey(),
            expiresAt: new Date(
                Date.now() +
                this.rotationDays * 86400000
            ),
            hardwareProtected: true
        });

        this.keys.set(keyId, [key]);

        this.audit.record(
            principal.id,
            "CREATE",
            keyId,
            "SUCCESS"
        );

        return key;
    }

    activeKey(keyId) {
        const versions = this.keys.get(keyId);

        if (!versions || versions.length === 0) {
            throw new NotFoundError("Key not found");
        }

        const key = versions[versions.length - 1];

        if (key.status !== KeyStatus.ACTIVE) {
            throw new StateError(
                "Key is not active"
            );
        }

        if (Date.now() >= key.expiresAt.getTime()) {
            key.status = KeyStatus.EXPIRED;
            throw new StateError("Key expired");
        }

        return key;
    }

    rotate(principal, keyId) {
        this.authorize(principal, [
            Role.ADMIN,
            Role.CRYPTO_OPERATOR
        ]);

        const current = this.activeKey(keyId);
        current.status = KeyStatus.ROTATED;

        const next = new KeyVersion({
            keyId,
            version: current.version + 1,
            purpose: current.purpose,
            material: this.hsm.generateKey(),
            expiresAt: new Date(
                Date.now() +
                this.rotationDays * 86400000
            ),
            hardwareProtected: current.hardwareProtected
        });

        this.keys.get(keyId).push(next);

        this.audit.record(
            principal.id,
            "ROTATE",
            keyId,
            "SUCCESS",
            `Version ${next.version}`
        );

        return next;
    }

    revoke(principal, keyId) {
        this.authorize(principal, [Role.ADMIN]);

        const versions = this.keys.get(keyId);

        if (!versions) {
            throw new NotFoundError("Key not found");
        }

        for (const version of versions) {
            version.status = KeyStatus.REVOKED;
        }

        this.audit.record(
            principal.id,
            "REVOKE",
            keyId,
            "SUCCESS"
        );
    }

    disable(principal, keyId) {
        this.authorize(principal, [
            Role.ADMIN,
            Role.CRYPTO_OPERATOR
        ]);

        const key = this.activeKey(keyId);
        key.status = KeyStatus.DISABLED;

        this.audit.record(
            principal.id,
            "DISABLE",
            keyId,
            "SUCCESS"
        );
    }

    metadata() {
        return Array.from(this.keys.values())
            .flatMap(versions =>
                versions.map(key => key.metadata())
            );
    }
}

class AEADCipher {
    static encrypt(plaintext, key) {
        if (!Buffer.isBuffer(plaintext)) {
            throw new TypeError(
                "Plaintext must be a Buffer"
            );
        }

        if (key.length !== 32) {
            throw new TypeError(
                "AES-256 requires a 32-byte key"
            );
        }

        const nonce = crypto.randomBytes(12);

        const cipher = crypto.createCipheriv(
            "aes-256-gcm",
            key,
            nonce
        );

        const ciphertext = Buffer.concat([
            cipher.update(plaintext),
            cipher.final()
        ]);

        return Object.freeze({
            nonce: nonce.toString("base64"),
            ciphertext: ciphertext.toString("base64"),
            tag: cipher.getAuthTag().toString("base64")
        });
    }

    static decrypt(envelope, key) {
        try {
            const nonce = Buffer.from(
                envelope.nonce,
                "base64"
            );

            const ciphertext = Buffer.from(
                envelope.ciphertext,
                "base64"
            );

            const tag = Buffer.from(
                envelope.tag,
                "base64"
            );

            if (nonce.length !== 12 || tag.length !== 16) {
                throw new Error("Invalid envelope");
            }

            const decipher = crypto.createDecipheriv(
                "aes-256-gcm",
                key,
                nonce
            );

            decipher.setAuthTag(tag);

            return Buffer.concat([
                decipher.update(ciphertext),
                decipher.final()
            ]);
        } catch {
            throw new SecurityError(
                "Authentication or decryption failed"
            );
        }
    }
}

class SecretsVault {
    constructor(keyManager) {
        this.keyManager = keyManager;
        this.records = new Map();
    }

    store(principal, name, value, keyId) {
        this.keyManager.authorize(
            principal,
            [Role.APPLICATION]
        );

        if (typeof name !== "string" ||
            !/^[a-zA-Z0-9_.-]{1,128}$/.test(name)) {
            throw new TypeError("Invalid secret name");
        }

        if (typeof value !== "string" ||
            value.length === 0) {
            throw new TypeError("Invalid secret value");
        }

        if (this.records.has(name)) {
            throw new Error("Secret already exists");
        }

        const key = this.keyManager.activeKey(keyId);

        const envelope = AEADCipher.encrypt(
            Buffer.from(value, "utf8"),
            key.material
        );

        this.records.set(name, {
            keyId,
            version: key.version,
            envelope
        });
    }

    retrieve(principal, name) {
        this.keyManager.authorize(
            principal,
            [Role.ADMIN, Role.APPLICATION]
        );

        const record = this.records.get(name);

        if (!record) {
            throw new NotFoundError(
                "Secret not found"
            );
        }

        const versions = this.keyManager.keys.get(
            record.keyId
        );

        if (!versions) {
            throw new NotFoundError(
                "Encryption key unavailable"
            );
        }

        const key = versions.find(
            item => item.version === record.version
        );

        if (!key || key.status === KeyStatus.REVOKED) {
            throw new StateError(
                "Encryption key unavailable or revoked"
            );
        }

        const plaintext = AEADCipher.decrypt(
            record.envelope,
            key.material
        );

        return plaintext.toString("utf8");
    }

    rotateSecret(principal, name) {
        this.keyManager.authorize(
            principal,
            [Role.ADMIN, Role.CRYPTO_OPERATOR]
        );

        const record = this.records.get(name);

        if (!record) {
            throw new NotFoundError(
                "Secret not found"
            );
        }

        const versions = this.keyManager.keys.get(
            record.keyId
        );

        const oldKey = versions?.find(
            item => item.version === record.version
        );

        if (!oldKey ||
            oldKey.status === KeyStatus.REVOKED) {
            throw new StateError(
                "Old key unavailable"
            );
        }

        const plaintext = AEADCipher.decrypt(
            record.envelope,
            oldKey.material
        );

        const newKey = this.keyManager.activeKey(
            record.keyId
        );

        record.envelope = AEADCipher.encrypt(
            plaintext,
            newKey.material
        );

        record.version = newKey.version;

        this.keyManager.audit.record(
            principal.id,
            "REENCRYPT",
            record.keyId,
            "SUCCESS",
            name
        );
    }
}

async function runWorkflow() {
    const admin = {
        id: "security-admin",
        role: Role.ADMIN
    };

    const operator = {
        id: "key-operator",
        role: Role.CRYPTO_OPERATOR
    };

    const application = {
        id: "payment-service",
        role: Role.APPLICATION
    };

    const manager = new KeyManager({
        rotationDays: 90
    });

    const vault = new SecretsVault(manager);

    // Key creation.
    const key = manager.createKey(
        operator,
        KeyPurpose.KEY_ENCRYPTION
    );

    console.log("Created:", key.metadata());

    // Secret storage.
    vault.store(
        application,
        "database.password",
        "Secure-Database-Password-2026",
        key.keyId
    );

    console.log(
        "Retrieved:",
        vault.retrieve(
            application,
            "database.password"
        )
    );

    // Rotation retains the old version for migration.
    const next = manager.rotate(
        operator,
        key.keyId
    );

    console.log("Rotated:", next.metadata());

    // Re-encrypt stored data with the current version.
    vault.rotateSecret(
        operator,
        "database.password"
    );

    console.log(
        "After migration:",
        vault.retrieve(
            application,
            "database.password"
        )
    );

    // Asynchronous operation and failure isolation.
    const operations = await Promise.allSettled([
        Promise.resolve().then(() =>
            vault.retrieve(application, "database.password")
        ),
        Promise.resolve().then(() =>
            vault.retrieve(
                { id: "auditor", role: Role.AUDITOR },
                "database.password"
            )
        )
    ]);

    console.log(
        "Concurrent results:",
        operations.map(result => result.status)
    );

    // Revocation invalidates all versions.
    manager.revoke(admin, key.keyId);

    try {
        manager.activeKey(key.keyId);
    } catch (error) {
        console.log(
            "Revocation enforced:",
            error.message
        );
    }

    console.log(
        "Audit events:",
        manager.audit.events.length
    );

    console.log(
        "Key metadata:",
        manager.metadata()
    );
}

runWorkflow().catch(error => {
    console.error("Workflow failure:", error.message);
    process.exitCode = 1;
});
