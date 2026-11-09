"use strict";

/*
 * Encryption Engineering Laboratory
 *
 * Runtime: Node.js 20+
 *
 * Demonstrates:
 * - AES-256-GCM encryption at rest.
 * - TLS transport configuration.
 * - RSA-OAEP public-key encryption.
 * - Hybrid envelope encryption.
 * - Asynchronous encryption workflows.
 * - Key rotation and revocation.
 * - Event-driven audit records.
 * - Authentication and tamper detection.
 *
 * Uses only Node.js standard-library modules.
 */

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");

const MAX_PLAINTEXT_SIZE = 10 * 1024 * 1024;

class EncryptionError extends Error {}
class ValidationError extends EncryptionError {}
class AuthenticationError extends EncryptionError {}
class KeyManagementError extends EncryptionError {}

function validateBuffer(value, name, maximum = MAX_PLAINTEXT_SIZE) {
    if (!Buffer.isBuffer(value)) {
        throw new ValidationError(`${name} must be a Buffer`);
    }

    if (value.length > maximum) {
        throw new ValidationError(`${name} exceeds size limit`);
    }
}

function encode(buffer) {
    return buffer.toString("base64");
}

function decode(value, name) {
    if (typeof value !== "string" || value.length === 0) {
        throw new ValidationError(`Invalid ${name}`);
    }

    const buffer = Buffer.from(value, "base64");

    if (buffer.toString("base64") !== value) {
        throw new ValidationError(`Malformed ${name}`);
    }

    return buffer;
}

class AuditLog extends EventEmitter {
    constructor() {
        super();
        this.records = [];
    }

    record(event, metadata = {}) {
        const entry = Object.freeze({
            event,
            timestamp: new Date().toISOString(),
            ...metadata
        });

        this.records.push(entry);
        this.emit("audit", entry);
    }

    query(event) {
        return this.records.filter(
            record => record.event === event
        );
    }
}

class KeyVault {
    #keys = new Map();
    #activeId = null;

    constructor(audit) {
        this.audit = audit;
    }

    createKey(id) {
        if (typeof id !== "string" || !/^[A-Za-z0-9_-]{1,100}$/.test(id)) {
            throw new ValidationError("Invalid key identifier");
        }

        if (this.#keys.has(id)) {
            throw new KeyManagementError("Duplicate key identifier");
        }

        const key = {
            id,
            material: crypto.randomBytes(32),
            status: "ACTIVE",
            createdAt: new Date().toISOString()
        };

        this.#keys.set(id, key);
        this.#activeId = id;

        this.audit.record("KEY_CREATED", { keyId: id });

        return id;
    }

    active() {
        if (!this.#activeId) {
            throw new KeyManagementError("No active key");
        }

        return this.get(this.#activeId);
    }

    get(id) {
        const key = this.#keys.get(id);

        if (!key || key.status === "REVOKED") {
            throw new KeyManagementError(
                "Key unavailable or revoked"
            );
        }

        return key;
    }

    rotate(newId) {
        const previous = this.active();

        previous.status = "ROTATED";

        this.createKey(newId);

        this.audit.record("KEY_ROTATED", {
            previousKeyId: previous.id,
            newKeyId: newId
        });

        return newId;
    }

    revoke(id) {
        const key = this.get(id);
        key.status = "REVOKED";

        if (this.#activeId === id) {
            this.#activeId = null;
        }

        this.audit.record("KEY_REVOKED", { keyId: id });
    }
}

class AESGCMService {
    constructor(vault, audit) {
        this.vault = vault;
        this.audit = audit;
    }

    encrypt(plaintext, associatedData = Buffer.alloc(0)) {
        validateBuffer(plaintext, "Plaintext");
        validateBuffer(associatedData, "Associated data");

        const key = this.vault.active();
        const nonce = crypto.randomBytes(12);

        const cipher = crypto.createCipheriv(
            "aes-256-gcm",
            key.material,
            nonce,
            { authTagLength: 16 }
        );

        cipher.setAAD(associatedData);

        const ciphertext = Buffer.concat([
            cipher.update(plaintext),
            cipher.final()
        ]);

        const tag = cipher.getAuthTag();

        this.audit.record("DATA_ENCRYPTED", {
            keyId: key.id,
            algorithm: "AES-256-GCM"
        });

        return Object.freeze({
            version: 1,
            algorithm: "AES-256-GCM",
            keyId: key.id,
            nonce: encode(nonce),
            tag: encode(tag),
            ciphertext: encode(ciphertext),
            createdAt: new Date().toISOString()
        });
    }

    decrypt(envelope, associatedData = Buffer.alloc(0)) {
        if (!envelope || envelope.algorithm !== "AES-256-GCM") {
            throw new ValidationError("Unsupported envelope");
        }

        validateBuffer(associatedData, "Associated data");

        try {
            const nonce = decode(envelope.nonce, "nonce");
            const tag = decode(envelope.tag, "authentication tag");
            const ciphertext = decode(
                envelope.ciphertext,
                "ciphertext"
            );

            if (nonce.length !== 12 || tag.length !== 16) {
                throw new ValidationError("Invalid GCM parameters");
            }

            const key = this.vault.get(envelope.keyId);

            const decipher = crypto.createDecipheriv(
                "aes-256-gcm",
                key.material,
                nonce,
                { authTagLength: 16 }
            );

            decipher.setAAD(associatedData);
            decipher.setAuthTag(tag);

            const plaintext = Buffer.concat([
                decipher.update(ciphertext),
                decipher.final()
            ]);

            this.audit.record("DATA_DECRYPTED", {
                keyId: key.id
            });

            return plaintext;

        } catch (error) {
            if (error instanceof ValidationError ||
                error instanceof KeyManagementError) {
                throw error;
            }

            throw new AuthenticationError(
                "Decryption failed or authentication was invalid"
            );
        }
    }
}

class HybridEncryptionService {
    constructor() {
        const pair = crypto.generateKeyPairSync("rsa", {
            modulusLength: 3072,
            publicExponent: 0x10001,
            publicKeyEncoding: {
                type: "spki",
                format: "pem"
            },
            privateKeyEncoding: {
                type: "pkcs8",
                format: "pem"
            }
        });

        this.publicKey = pair.publicKey;
        this.privateKey = pair.privateKey;
    }

    encrypt(plaintext) {
        validateBuffer(plaintext, "Plaintext");

        const dataKey = crypto.randomBytes(32);
        const nonce = crypto.randomBytes(12);

        const cipher = crypto.createCipheriv(
            "aes-256-gcm",
            dataKey,
            nonce
        );

        cipher.setAAD(Buffer.from("hybrid-envelope-v1"));

        const ciphertext = Buffer.concat([
            cipher.update(plaintext),
            cipher.final()
        ]);

        const tag = cipher.getAuthTag();

        const encryptedKey = crypto.publicEncrypt(
            {
                key: this.publicKey,
                padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
                oaepHash: "sha256"
            },
            dataKey
        );

        return {
            algorithm: "RSA-OAEP-SHA256+AES-256-GCM",
            encryptedKey: encode(encryptedKey),
            nonce: encode(nonce),
            tag: encode(tag),
            ciphertext: encode(ciphertext)
        };
    }

    decrypt(envelope) {
        if (!envelope ||
            envelope.algorithm !== "RSA-OAEP-SHA256+AES-256-GCM") {
            throw new ValidationError("Unsupported hybrid envelope");
        }

        try {
            const encryptedKey = decode(
                envelope.encryptedKey,
                "encrypted key"
            );

            const nonce = decode(envelope.nonce, "nonce");
            const tag = decode(envelope.tag, "tag");
            const ciphertext = decode(
                envelope.ciphertext,
                "ciphertext"
            );

            if (nonce.length !== 12 || tag.length !== 16) {
                throw new ValidationError("Invalid envelope parameters");
            }

            const dataKey = crypto.privateDecrypt(
                {
                    key: this.privateKey,
                    padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
                    oaepHash: "sha256"
                },
                encryptedKey
            );

            const decipher = crypto.createDecipheriv(
                "aes-256-gcm",
                dataKey,
                nonce
            );

            decipher.setAAD(Buffer.from("hybrid-envelope-v1"));
            decipher.setAuthTag(tag);

            return Buffer.concat([
                decipher.update(ciphertext),
                decipher.final()
            ]);

        } catch (error) {
            if (error instanceof ValidationError) {
                throw error;
            }

            throw new AuthenticationError(
                "Hybrid decryption or authentication failed"
            );
        }
    }
}

class TransportSecurityPolicy {
    static validate({
        protocol,
        certificateAuthorized,
        hostnameVerified,
        minimumVersion = "TLSv1.2"
    }) {
        const versions = {
            "TLSv1.2": 12,
            "TLSv1.3": 13
        };

        if (!(protocol in versions) ||
            versions[protocol] < versions[minimumVersion]) {
            throw new ValidationError("TLS version violates policy");
        }

        if (!certificateAuthorized || !hostnameVerified) {
            throw new ValidationError(
                "Certificate chain or hostname validation failed"
            );
        }

        return true;
    }

    static createHTTPSOptions(ca) {
        return {
            minVersion: "TLSv1.2",
            rejectUnauthorized: true,
            ca
        };
    }
}

class EncryptedFileRepository {
    constructor(service) {
        this.service = service;
    }

    async save(filePath, plaintext) {
        validateBuffer(plaintext, "Plaintext");

        const envelope = this.service.encrypt(
            plaintext,
            Buffer.from(path.basename(filePath))
        );

        const temporaryPath = `${filePath}.${crypto.randomUUID()}.tmp`;

        try {
            await fs.writeFile(
                temporaryPath,
                JSON.stringify(envelope),
                { mode: 0o600, flag: "wx" }
            );

            await fs.rename(temporaryPath, filePath);

        } catch (error) {
            await fs.rm(temporaryPath, { force: true }).catch(() => {});
            throw new EncryptionError("Encrypted file write failed", {
                cause: error
            });
        }
    }

    async load(filePath) {
        const stat = await fs.lstat(filePath);

        if (!stat.isFile() || stat.isSymbolicLink()) {
            throw new ValidationError("Invalid encrypted file");
        }

        if (stat.size > 15 * 1024 * 1024) {
            throw new ValidationError("Encrypted file exceeds size limit");
        }

        try {
            const raw = await fs.readFile(filePath, "utf8");
            const envelope = JSON.parse(raw);

            return this.service.decrypt(
                envelope,
                Buffer.from(path.basename(filePath))
            );

        } catch (error) {
            if (error instanceof EncryptionError) {
                throw error;
            }

            throw new EncryptionError("Encrypted file read failed", {
                cause: error
            });
        }
    }
}

async function runTests() {
    const audit = new AuditLog();
    const vault = new KeyVault(audit);

    vault.createKey("key-001");

    const aes = new AESGCMService(vault, audit);

    const original = Buffer.from(
        "Confidential customer transaction"
    );

    // Symmetric encryption and authentication.
    const envelope = aes.encrypt(original, Buffer.from("record-001"));

    assert.deepEqual(
        aes.decrypt(envelope, Buffer.from("record-001")),
        original
    );

    // Associated data mismatch must fail authentication.
    assert.throws(
        () => aes.decrypt(envelope, Buffer.from("record-002")),
        AuthenticationError
    );

    // Tampering must be detected.
    const modified = {
        ...envelope,
        ciphertext: encode(Buffer.from("modified"))
    };

    assert.throws(
        () => aes.decrypt(modified, Buffer.from("record-001")),
        AuthenticationError
    );

    // Key rotation retains decryption capability for old ciphertext.
    vault.rotate("key-002");

    assert.deepEqual(
        aes.decrypt(envelope, Buffer.from("record-001")),
        original
    );

    const newEnvelope = aes.encrypt(original);

    assert.deepEqual(aes.decrypt(newEnvelope), original);

    // Hybrid encryption.
    const hybrid = new HybridEncryptionService();
    const hybridEnvelope = hybrid.encrypt(original);

    assert.deepEqual(hybrid.decrypt(hybridEnvelope), original);

    // TLS policy.
    assert.equal(
        TransportSecurityPolicy.validate({
            protocol: "TLSv1.3",
            certificateAuthorized: true,
            hostnameVerified: true
        }),
        true
    );

    assert.throws(
        () => TransportSecurityPolicy.validate({
            protocol: "TLSv1.1",
            certificateAuthorized: true,
            hostnameVerified: true
        }),
        ValidationError
    );

    // Asynchronous encrypted file operations.
    const directory = await fs.mkdtemp(
        path.join(os.tmpdir(), "encryption-lab-")
    );

    try {
        const filePath = path.join(directory, "record.enc");
        const repository = new EncryptedFileRepository(aes);

        await repository.save(filePath, original);

        assert.deepEqual(
            await repository.load(filePath),
            original
        );

    } finally {
        await fs.rm(directory, { recursive: true, force: true });
    }

    // Audit events contain metadata, not plaintext or key material.
    assert.ok(audit.query("DATA_ENCRYPTED").length >= 2);
    assert.ok(audit.query("KEY_ROTATED").length === 1);

    console.log("All JavaScript encryption tests passed.");
    console.log("Audit events:", audit.records.length);
}

async function main() {
    console.log("ENCRYPTION ENGINEERING LABORATORY");
    console.log("=================================");

    await runTests();

    console.log("AES-256-GCM: verified");
    console.log("RSA-OAEP hybrid encryption: verified");
    console.log("TLS configuration validation: verified");
    console.log("Key rotation: verified");
    console.log("Encrypted file persistence: verified");
}

main().catch(error => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
