"use strict";

/*
 * File storage in JavaScript is especially useful to understand through
 * asynchronous I/O and service-style abstractions. This program models:
 *
 * - a shared filesystem namespace,
 * - a network file-storage client,
 * - a distributed object store with replicas,
 * - asynchronous storage events,
 * - checksum verification,
 * - node failure and repair.
 *
 * It uses only Node.js built-in modules.
 */

const fs = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");
const os = require("node:os");

class StorageError extends Error {}
class CapacityError extends StorageError {}
class ConsistencyError extends StorageError {}
class PermissionError extends StorageError {}

function checksum(buffer) {
    return crypto.createHash("sha256").update(buffer).digest("hex");
}

class SharedFileSystem {
    constructor(root, capacityBytes = 10_000_000) {
        this.root = root;
        this.capacityBytes = capacityBytes;
    }

    async initialize() {
        await fs.mkdir(this.root, { recursive: true });
    }

    resolveSafe(relativePath) {
        const resolvedRoot = path.resolve(this.root);
        const resolvedPath = path.resolve(this.root, relativePath);

        // A storage API must prevent a caller from escaping its namespace.
        if (
            resolvedPath !== resolvedRoot &&
            !resolvedPath.startsWith(`${resolvedRoot}${path.sep}`)
        ) {
            throw new PermissionError("Path escapes storage namespace");
        }

        return resolvedPath;
    }

    async usedBytes() {
        let total = 0;

        async function walk(directory) {
            const entries = await fs.readdir(directory, { withFileTypes: true });

            for (const entry of entries) {
                const fullPath = path.join(directory, entry.name);

                if (entry.isDirectory()) {
                    await walk(fullPath);
                } else {
                    const stat = await fs.stat(fullPath);
                    total += stat.size;
                }
            }
        }

        await walk(this.root);
        return total;
    }

    async write(relativePath, content, owner) {
        const target = this.resolveSafe(relativePath);
        const buffer = Buffer.from(content);

        await fs.mkdir(path.dirname(target), { recursive: true });

        const oldSize = await fs
            .stat(target)
            .then(stat => stat.size)
            .catch(() => 0);

        const newUsage = (await this.usedBytes()) - oldSize + buffer.length;

        if (newUsage > this.capacityBytes) {
            throw new CapacityError(
                `Capacity exceeded: ${newUsage} > ${this.capacityBytes}`
            );
        }

        // Rename is used after writing a temporary file so readers do not see
        // a partially written final object.
        const temporary = `${target}.${process.pid}.${Date.now()}.tmp`;
        await fs.writeFile(temporary, buffer);
        await fs.rename(temporary, target);

        return {
            path: relativePath,
            owner,
            size: buffer.length,
            checksum: checksum(buffer)
        };
    }

    async read(relativePath) {
        const target = this.resolveSafe(relativePath);
        return fs.readFile(target);
    }

    async list() {
        const files = [];

        async function walk(directory, root) {
            const entries = await fs.readdir(directory, { withFileTypes: true });

            for (const entry of entries) {
                const fullPath = path.join(directory, entry.name);

                if (entry.isDirectory()) {
                    await walk(fullPath, root);
                } else {
                    files.push(path.relative(root, fullPath));
                }
            }
        }

        await walk(this.root, this.root);
        return files.sort();
    }
}

class NetworkFileClient {
    constructor(server, clientName) {
        this.server = server;
        this.clientName = clientName;
        this.mounted = false;
    }

    mount() {
        this.mounted = true;
        console.log(`${this.clientName}: network share mounted`);
    }

    requireMount() {
        if (!this.mounted) {
            throw new StorageError(`${this.clientName}: share is not mounted`);
        }
    }

    async upload(filePath, data, owner) {
        this.requireMount();
        return this.server.write(filePath, data, owner);
    }

    async download(filePath) {
        this.requireMount();
        return this.server.read(filePath);
    }

    async list() {
        this.requireMount();
        return this.server.list();
    }
}

class DistributedObjectStore {
    constructor(nodeNames, replicationFactor = 2) {
        if (nodeNames.length === 0) {
            throw new StorageError("Distributed storage needs at least one node");
        }

        if (
            replicationFactor < 1 ||
            replicationFactor > nodeNames.length
        ) {
            throw new StorageError("Invalid replication factor");
        }

        this.replicationFactor = replicationFactor;
        this.nodes = new Map(
            nodeNames.map(name => [
                name,
                {
                    name,
                    available: true,
                    objects: new Map()
                }
            ])
        );
    }

    availableNodes() {
        return [...this.nodes.values()].filter(node => node.available);
    }

    async put(objectName, data, owner) {
        const buffer = Buffer.from(data);
        const available = this.availableNodes();

        if (available.length < this.replicationFactor) {
            throw new StorageError("Not enough healthy nodes for replication");
        }

        const metadata = {
            objectName,
            owner,
            size: buffer.length,
            checksum: checksum(buffer),
            createdAt: new Date().toISOString()
        };

        const object = {
            metadata,
            content: Buffer.from(buffer)
        };

        for (const node of available.slice(0, this.replicationFactor)) {
            node.objects.set(objectName, {
                metadata: { ...metadata },
                content: Buffer.from(buffer)
            });
        }

        return metadata;
    }

    async get(objectName) {
        const candidates = [];

        for (const node of this.availableNodes()) {
            const object = node.objects.get(objectName);

            if (object) {
                candidates.push(object);
            }
        }

        if (candidates.length === 0) {
            throw new StorageError(`Object not available: ${objectName}`);
        }

        const expected = candidates[0].metadata.checksum;

        for (const object of candidates) {
            if (object.metadata.checksum !== expected) {
                throw new ConsistencyError(
                    `Replica metadata mismatch for ${objectName}`
                );
            }

            if (checksum(object.content) !== expected) {
                throw new ConsistencyError(
                    `Replica checksum mismatch for ${objectName}`
                );
            }
        }

        return Buffer.from(candidates[0].content);
    }

    setNodeAvailability(nodeName, available) {
        const node = this.nodes.get(nodeName);

        if (!node) {
            throw new StorageError(`Unknown node: ${nodeName}`);
        }

        node.available = available;
    }

    corrupt(nodeName, objectName, replacement) {
        const node = this.nodes.get(nodeName);

        if (!node || !node.objects.has(objectName)) {
            throw new StorageError("Replica does not exist");
        }

        const original = node.objects.get(objectName);

        node.objects.set(objectName, {
            metadata: { ...original.metadata },
            content: Buffer.from(replacement)
        });
    }

    distribution(objectName) {
        return Object.fromEntries(
            [...this.nodes.values()].map(node => [
                node.name,
                node.objects.has(objectName)
            ])
        );
    }

    async repair(objectName) {
        const verified = await this.get(objectName);
        const verifiedChecksum = checksum(verified);

        for (const node of this.availableNodes()) {
            const existing = node.objects.get(objectName);

            if (
                !existing ||
                existing.metadata.checksum !== verifiedChecksum ||
                checksum(existing.content) !== verifiedChecksum
            ) {
                node.objects.set(objectName, {
                    metadata: {
                        objectName,
                        owner: "repair-service",
                        size: verified.length,
                        checksum: verifiedChecksum,
                        repairedAt: new Date().toISOString()
                    },
                    content: Buffer.from(verified)
                });
            }
        }
    }
}

async function demonstrateSharedAndNetworkStorage(baseDirectory) {
    console.log("\n=== Shared and Network File Storage ===");

    const server = new SharedFileSystem(
        path.join(baseDirectory, "network-share")
    );

    await server.initialize();

    const clientA = new NetworkFileClient(server, "reporting-host");
    const clientB = new NetworkFileClient(server, "application-host");

    try {
        await clientA.download("reports/monthly.csv");
    } catch (error) {
        console.log("Before mount:", error.message);
    }

    clientA.mount();
    clientB.mount();

    await clientA.upload(
        "reports/monthly.csv",
        "month,revenue\n2026-09,150000\n2026-10,163500\n",
        "finance"
    );

    const content = await clientB.download("reports/monthly.csv");

    console.log("Second client reads:", content.toString());
    console.log("Shared namespace:", await clientB.list());

    try {
        server.resolveSafe("../../outside.txt");
    } catch (error) {
        if (error instanceof PermissionError) {
            console.log("Path traversal blocked:", error.message);
        }
    }
}

async function demonstrateDistributedStorage() {
    console.log("\n=== Distributed Object Storage ===");

    const store = new DistributedObjectStore(
        ["node-a", "node-b", "node-c"],
        2
    );

    const metadata = await store.put(
        "events/2026-10/customer-1042.json",
        JSON.stringify({
            event: "purchase",
            customer: "C-1042",
            amount: 2499
        }),
        "analytics"
    );

    console.log("Object checksum:", metadata.checksum);
    console.log(
        "Initial distribution:",
        store.distribution("events/2026-10/customer-1042.json")
    );

    store.setNodeAvailability("node-a", false);

    const afterFailure = await store.get(
        "events/2026-10/customer-1042.json"
    );

    console.log("Read after node-a failure:", afterFailure.toString());

    store.corrupt(
        "node-b",
        "events/2026-10/customer-1042.json",
        '{"event":"tampered"}'
    );

    try {
        await store.get("events/2026-10/customer-1042.json");
    } catch (error) {
        console.log("Corruption detected:", error.message);
    }

    store.setNodeAvailability("node-b", false);
    store.setNodeAvailability("node-a", true);

    await store.repair("events/2026-10/customer-1042.json");

    console.log(
        "Distribution after repair:",
        store.distribution("events/2026-10/customer-1042.json")
    );
}

async function demonstrateAsynchronousBehavior() {
    console.log("\n=== Asynchronous Storage Operations ===");

    const root = await fs.mkdtemp(
        path.join(os.tmpdir(), "storage-demo-")
    );

    try {
        const storage = new SharedFileSystem(root);
        await storage.initialize();

        // Promise.all models concurrent independent I/O operations. Actual
        // storage throughput is still constrained by the underlying device
        // and filesystem rather than by JavaScript alone.
        const results = await Promise.all([
            storage.write("batch/a.txt", "alpha", "worker-a"),
            storage.write("batch/b.txt", "beta", "worker-b"),
            storage.write("batch/c.txt", "gamma", "worker-c")
        ]);

        console.log(
            "Concurrent writes:",
            results.map(result => result.path)
        );
    } finally {
        await fs.rm(root, { recursive: true, force: true });
    }
}

async function main() {
    const temporaryDirectory = await fs.mkdtemp(
        path.join(os.tmpdir(), "file-storage-demo-")
    );

    try {
        await demonstrateSharedAndNetworkStorage(temporaryDirectory);
        await demonstrateDistributedStorage();
        await demonstrateAsynchronousBehavior();
    } finally {
        await fs.rm(temporaryDirectory, {
            recursive: true,
            force: true
        });
    }
}

main().catch(error => {
    console.error("Storage demonstration failed:", error);
    process.exitCode = 1;
});
