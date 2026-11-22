"use strict";

/*
 * Container Registry Management System
 *
 * JavaScript implementation emphasizing:
 * - Event-driven registry operations
 * - Asynchronous image distribution
 * - Repository and tag management
 * - Content-addressed image storage
 * - Role-based access control
 * - Immutable release tags
 * - Security policy evaluation
 * - Distribution retry and failure handling
 *
 * Runtime: Node.js 18+
 *
 * Execute:
 * node container_registry.js
 */

const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");

class RegistryError extends Error {}
class AuthenticationError extends RegistryError {}
class AuthorizationError extends RegistryError {}
class ValidationError extends RegistryError {}
class PolicyError extends RegistryError {}
class ImageNotFoundError extends RegistryError {}
class ImmutableTagError extends RegistryError {}

const Roles = Object.freeze({
    ADMIN: "admin",
    PUBLISHER: "publisher",
    CONSUMER: "consumer"
});

const Permissions = Object.freeze({
    admin: new Set(["CREATE", "PUSH", "PULL", "DELETE", "MANAGE"]),
    publisher: new Set(["PUSH", "PULL"]),
    consumer: new Set(["PULL"])
});

const RegistryEvents = Object.freeze({
    REPOSITORY_CREATED: "repository.created",
    IMAGE_PUSHED: "image.pushed",
    IMAGE_PULLED: "image.pulled",
    TAG_UPDATED: "tag.updated",
    IMAGE_DELETED: "image.deleted",
    DISTRIBUTION_COMPLETED: "distribution.completed",
    OPERATION_REJECTED: "operation.rejected"
});

function sha256(content) {
    return "sha256:" + crypto
        .createHash("sha256")
        .update(content)
        .digest("hex");
}

function validateRepositoryName(name) {
    if (
        typeof name !== "string" ||
        !/^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:\/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$/.test(name)
    ) {
        throw new ValidationError("Invalid repository name.");
    }
}

function validateTag(tag) {
    if (
        typeof tag !== "string" ||
        !/^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$/.test(tag)
    ) {
        throw new ValidationError("Invalid image tag.");
    }
}

class ContainerRegistry extends EventEmitter {
    constructor({
        name,
        maxImageSize = 50 * 1024 * 1024,
        requireSignedImages = true,
        maxVulnerabilities = 0
    }) {
        super();

        if (!name || !Number.isSafeInteger(maxImageSize) || maxImageSize <= 0) {
            throw new ValidationError("Invalid registry configuration.");
        }

        this.name = name;
        this.maxImageSize = maxImageSize;
        this.requireSignedImages = requireSignedImages;
        this.maxVulnerabilities = maxVulnerabilities;

        this.users = new Map();
        this.repositories = new Map();
        this.auditEvents = [];
    }

    registerUser(username, role) {
        if (
            !username ||
            this.users.has(username) ||
            !Object.hasOwn(Permissions, role)
        ) {
            throw new ValidationError("Invalid user registration.");
        }

        const token = crypto.randomBytes(32).toString("hex");

        const user = Object.freeze({
            username,
            role,
            token,
            active: true
        });

        this.users.set(username, user);
        return user;
    }

    authenticate(token) {
        if (typeof token !== "string") {
            throw new AuthenticationError("Missing credentials.");
        }

        const user = [...this.users.values()].find(
            candidate =>
                Buffer.byteLength(candidate.token) === Buffer.byteLength(token) &&
                crypto.timingSafeEqual(
                    Buffer.from(candidate.token),
                    Buffer.from(token)
                )
        );

        if (!user || !user.active) {
            throw new AuthenticationError("Invalid or inactive credentials.");
        }

        return user;
    }

    authorize(user, operation) {
        if (!Permissions[user.role]?.has(operation)) {
            throw new AuthorizationError(
                `${user.username} cannot execute ${operation}.`
            );
        }
    }

    repository(name) {
        const repository = this.repositories.get(name);

        if (!repository) {
            throw new ImageNotFoundError(`Repository not found: ${name}`);
        }

        return repository;
    }

    audit(user, operation, repository, reference, result) {
        const event = Object.freeze({
            timestamp: new Date().toISOString(),
            username: user.username,
            operation,
            repository,
            reference,
            result
        });

        this.auditEvents.push(event);
        return event;
    }

    createRepository(token, name, privateRepository = true) {
        const user = this.authenticate(token);
        this.authorize(user, "CREATE");
        validateRepositoryName(name);

        if (this.repositories.has(name)) {
            throw new ValidationError("Repository already exists.");
        }

        const repository = {
            name,
            private: privateRepository,
            manifests: new Map(),
            tags: new Map()
        };

        this.repositories.set(name, repository);

        this.audit(user, "CREATE", name, name, "SUCCESS");

        this.emit(RegistryEvents.REPOSITORY_CREATED, {
            repository: name,
            private: privateRepository
        });

        return repository;
    }

    evaluatePolicy({
        content,
        signed,
        vulnerabilities,
        architecture,
        os
    }) {
        if (!Buffer.isBuffer(content) || content.length === 0) {
            throw new ValidationError("Image content must be a nonempty Buffer.");
        }

        if (content.length > this.maxImageSize) {
            throw new PolicyError("Image exceeds configured size.");
        }

        if (this.requireSignedImages && signed !== true) {
            throw new PolicyError("Image signature verification is required.");
        }

        if (
            !Number.isInteger(vulnerabilities) ||
            vulnerabilities < 0 ||
            vulnerabilities > this.maxVulnerabilities
        ) {
            throw new PolicyError("Vulnerability policy failed.");
        }

        if (!architecture || !os) {
            throw new ValidationError("Image platform is required.");
        }
    }

    async push(token, repositoryName, tagName, image) {
        const user = this.authenticate(token);
        this.authorize(user, "PUSH");

        const repository = this.repository(repositoryName);

        validateTag(tagName);
        this.evaluatePolicy(image);

        const digest = sha256(image.content);
        const existingTag = repository.tags.get(tagName);

        if (existingTag?.immutable && existingTag.digest !== digest) {
            throw new ImmutableTagError("Cannot replace immutable tag.");
        }

        let manifest = repository.manifests.get(digest);

        if (!manifest) {
            manifest = Object.freeze({
                digest,
                size: image.content.length,
                architecture: image.architecture,
                os: image.os,
                signed: image.signed,
                vulnerabilities: image.vulnerabilities,
                mediaType: "application/vnd.oci.image.manifest.v1+json",
                createdAt: new Date().toISOString()
            });

            repository.manifests.set(digest, manifest);
        }

        repository.tags.set(tagName, Object.freeze({
            digest,
            immutable: image.immutableTag === true ||
                existingTag?.immutable === true,
            updatedAt: new Date().toISOString()
        }));

        this.audit(user, "PUSH", repositoryName, tagName, "SUCCESS");

        this.emit(RegistryEvents.IMAGE_PUSHED, {
            repository: repositoryName,
            tag: tagName,
            digest
        });

        this.emit(RegistryEvents.TAG_UPDATED, {
            repository: repositoryName,
            tag: tagName,
            digest
        });

        return manifest;
    }

    async pull(token, repositoryName, reference) {
        const user = this.authenticate(token);
        this.authorize(user, "PULL");

        const repository = this.repository(repositoryName);

        let digest = reference;

        if (!reference.startsWith("sha256:")) {
            const tag = repository.tags.get(reference);

            if (!tag) {
                this.audit(user, "PULL", repositoryName, reference, "NOT_FOUND");
                throw new ImageNotFoundError("Tag not found.");
            }

            digest = tag.digest;
        }

        const manifest = repository.manifests.get(digest);

        if (!manifest) {
            throw new ImageNotFoundError("Manifest not found.");
        }

        this.audit(user, "PULL", repositoryName, reference, "SUCCESS");

        this.emit(RegistryEvents.IMAGE_PULLED, {
            repository: repositoryName,
            reference,
            digest,
            consumer: user.username
        });

        return manifest;
    }

    deleteTag(token, repositoryName, tagName) {
        const user = this.authenticate(token);
        this.authorize(user, "DELETE");

        const repository = this.repository(repositoryName);
        const tag = repository.tags.get(tagName);

        if (!tag) {
            throw new ImageNotFoundError("Tag does not exist.");
        }

        if (tag.immutable) {
            throw new ImmutableTagError("Immutable tag cannot be deleted.");
        }

        repository.tags.delete(tagName);

        this.audit(user, "DELETE", repositoryName, tagName, "SUCCESS");

        this.emit(RegistryEvents.IMAGE_DELETED, {
            repository: repositoryName,
            tag: tagName
        });
    }

    async distribute(
        token,
        repositoryName,
        reference,
        targets,
        maxRetries = 2
    ) {
        const user = this.authenticate(token);
        this.authorize(user, "PULL");

        if (!Array.isArray(targets) || targets.length === 0) {
            throw new ValidationError("At least one target is required.");
        }

        if (!Number.isInteger(maxRetries) || maxRetries < 0 || maxRetries > 5) {
            throw new ValidationError("Invalid retry count.");
        }

        const manifest = await this.pull(
            token,
            repositoryName,
            reference
        );

        // Independent destinations are processed concurrently.
        const results = await Promise.allSettled(
            targets.map(async target => {
                if (typeof target !== "function") {
                    throw new ValidationError("Target must be a function.");
                }

                let lastError;

                for (let attempt = 0; attempt <= maxRetries; attempt++) {
                    try {
                        await target(manifest);
                        return {
                            digest: manifest.digest,
                            attempts: attempt + 1,
                            status: "DELIVERED"
                        };
                    } catch (error) {
                        lastError = error;
                    }
                }

                throw lastError;
            })
        );

        const report = results.map((result, index) => ({
            target: index,
            status: result.status === "fulfilled"
                ? "DELIVERED"
                : "FAILED",
            detail: result.status === "fulfilled"
                ? result.value
                : result.reason.message
        }));

        this.emit(RegistryEvents.DISTRIBUTION_COMPLETED, {
            repository: repositoryName,
            reference,
            report
        });

        this.audit(
            user,
            "DISTRIBUTE",
            repositoryName,
            reference,
            report.every(item => item.status === "DELIVERED")
                ? "SUCCESS"
                : "PARTIAL_FAILURE"
        );

        return report;
    }

    listTags(repositoryName) {
        const repository = this.repository(repositoryName);

        return [...repository.tags.entries()].map(([name, tag]) => ({
            name,
            digest: tag.digest,
            immutable: tag.immutable
        }));
    }

    garbageCollect(token) {
        const user = this.authenticate(token);
        this.authorize(user, "MANAGE");

        let deleted = 0;

        for (const repository of this.repositories.values()) {
            const referenced = new Set(
                [...repository.tags.values()].map(tag => tag.digest)
            );

            for (const digest of repository.manifests.keys()) {
                if (!referenced.has(digest)) {
                    repository.manifests.delete(digest);
                    deleted++;
                }
            }
        }

        this.audit(user, "MANAGE", "*", "GARBAGE_COLLECTION", "SUCCESS");

        return deleted;
    }
}

async function main() {
    const registry = new ContainerRegistry({
        name: "registry.example.internal",
        maxImageSize: 5_000_000,
        requireSignedImages: true,
        maxVulnerabilities: 1
    });

    // Event listeners implement independent monitoring and audit integrations.
    registry.on(RegistryEvents.IMAGE_PUSHED, event => {
        console.log("Image published:", event.tag, event.digest);
    });

    registry.on(RegistryEvents.IMAGE_PULLED, event => {
        console.log("Image downloaded by:", event.consumer);
    });

    registry.on(RegistryEvents.DISTRIBUTION_COMPLETED, event => {
        console.log("Distribution report:", event.report);
    });

    const admin = registry.registerUser("admin", Roles.ADMIN);
    const publisher = registry.registerUser("build-service", Roles.PUBLISHER);
    const consumer = registry.registerUser("deployment-service", Roles.CONSUMER);

    registry.createRepository(
        admin.token,
        "production/order-service",
        true
    );

    const image = {
        content: Buffer.from("order-service-image-v1"),
        architecture: "amd64",
        os: "linux",
        signed: true,
        vulnerabilities: 0,
        immutableTag: true
    };

    const manifest = await registry.push(
        publisher.token,
        "production/order-service",
        "1.0.0",
        image
    );

    await registry.push(
        publisher.token,
        "production/order-service",
        "latest",
        image
    );

    const pulled = await registry.pull(
        consumer.token,
        "production/order-service",
        "1.0.0"
    );

    console.log("\nContent integrity:");
    console.log("Published:", manifest.digest);
    console.log("Downloaded:", pulled.digest);
    console.log("Match:", manifest.digest === pulled.digest);

    // Simulate distribution to multiple deployment destinations.
    const destinations = [
        async artifact => {
            await new Promise(resolve => setTimeout(resolve, 50));
            console.log("Delivered to staging:", artifact.digest);
        },
        async artifact => {
            console.log("Delivered to production:", artifact.digest);
        },
        async () => {
            throw new Error("Remote destination unavailable.");
        }
    ];

    const distribution = await registry.distribute(
        consumer.token,
        "production/order-service",
        manifest.digest,
        destinations,
        1
    );

    console.log("\nFinal distribution:", distribution);

    try {
        await registry.push(
            publisher.token,
            "production/order-service",
            "1.0.0",
            {
                ...image,
                content: Buffer.from("different-content")
            }
        );
    } catch (error) {
        console.log("\nImmutable tag protection:", error.message);
    }

    try {
        await registry.push(
            publisher.token,
            "production/order-service",
            "2.0.0",
            {
                ...image,
                signed: false
            }
        );
    } catch (error) {
        console.log("Signature policy protection:", error.message);
    }

    console.log("\nRepository tags:");
    console.table(registry.listTags("production/order-service"));

    console.log("\nAudit event count:", registry.auditEvents.length);
}

main().catch(error => {
    console.error("Registry execution failed:", error.message);
    process.exitCode = 1;
});
