"use strict";

/*
 * Block storage is persistent storage presented to a compute system as a
 * block-addressable device. This model focuses on lifecycle events rather
 * than treating a disk as an ordinary JavaScript object.
 *
 * Run with:
 *   node block-storage.js
 */

class StorageError extends Error {
    constructor(message) {
        super(message);
        this.name = "StorageError";
    }
}

class Volume {
    constructor({ id, capacityGiB, type, zone }) {
        if (!id || capacityGiB <= 0) {
            throw new StorageError("A volume requires a positive capacity.");
        }

        if (!["hdd", "ssd", "nvme"].includes(type)) {
            throw new StorageError(`Unsupported volume type: ${type}`);
        }

        this.id = id;
        this.capacityGiB = capacityGiB;
        this.type = type;
        this.zone = zone;
        this.usedGiB = 0;
        this.attachedInstance = null;
        this.snapshots = [];
    }

    write(amountGiB) {
        if (amountGiB <= 0) {
            throw new StorageError("Write size must be positive.");
        }

        if (this.usedGiB + amountGiB > this.capacityGiB) {
            throw new StorageError(
                `Volume ${this.id} does not have enough free capacity.`
            );
        }

        this.usedGiB += amountGiB;
    }

    detach() {
        this.attachedInstance = null;
    }

    snapshot(snapshotId, changedBlocks) {
        const snapshot = {
            id: snapshotId,
            volumeId: this.id,
            createdAt: new Date().toISOString(),
            logicalSizeGiB: this.usedGiB,
            changedBlocks,
            parent:
                this.snapshots.length > 0
                    ? this.snapshots[this.snapshots.length - 1].id
                    : null
        };

        this.snapshots.push(snapshot);
        return snapshot;
    }
}

class ComputeNode {
    constructor(id, zone) {
        this.id = id;
        this.zone = zone;
        this.volumes = new Map();
    }

    attach(volume, mode = "rw") {
        if (volume.zone !== this.zone) {
            throw new StorageError(
                `Cannot attach ${volume.id}: zone mismatch.`
            );
        }

        if (volume.attachedInstance !== null) {
            throw new StorageError(
                `Volume ${volume.id} is already attached.`
            );
        }

        if (!["rw", "ro"].includes(mode)) {
            throw new StorageError(`Unsupported attachment mode: ${mode}`);
        }

        volume.attachedInstance = this.id;
        this.volumes.set(volume.id, mode);
    }

    detach(volume) {
        if (!this.volumes.has(volume.id)) {
            throw new StorageError(
                `${volume.id} is not attached to ${this.id}.`
            );
        }

        this.volumes.delete(volume.id);
        volume.detach();
    }
}

class RepositoryStoragePolicy {
    constructor({
        protectedBranch,
        requireReviews,
        requiredApprovals,
        requirePassingChecks
    }) {
        this.protectedBranch = protectedBranch;
        this.requireReviews = requireReviews;
        this.requiredApprovals = requiredApprovals;
        this.requirePassingChecks = requirePassingChecks;
    }
}

/*
 * The storage policy below is deliberately expressed as an operational
 * policy: production systems need explicit rules for capacity, attachment,
 * snapshots, and performance instead of relying on implicit assumptions.
 */
class BlockStorageController {
    constructor() {
        this.volumes = new Map();
        this.instances = new Map();
    }

    addVolume(volume) {
        if (this.volumes.has(volume.id)) {
            throw new StorageError(`Duplicate volume: ${volume.id}`);
        }
        this.volumes.set(volume.id, volume);
    }

    addInstance(instance) {
        if (this.instances.has(instance.id)) {
            throw new StorageError(`Duplicate instance: ${instance.id}`);
        }
        this.instances.set(instance.id, instance);
    }

    attach(volumeId, instanceId, mode = "rw") {
        const volume = this.volumes.get(volumeId);
        const instance = this.instances.get(instanceId);

        if (!volume || !instance) {
            throw new StorageError("Volume or compute node does not exist.");
        }

        instance.attach(volume, mode);
    }

    detach(volumeId, instanceId) {
        const volume = this.volumes.get(volumeId);
        const instance = this.instances.get(instanceId);

        if (!volume || !instance) {
            throw new StorageError("Volume or compute node does not exist.");
        }

        instance.detach(volume);
    }

    estimatePerformance(volume) {
        const profile = {
            hdd: { latencyMs: 8.0, throughputMiB: 180 },
            ssd: { latencyMs: 0.8, throughputMiB: 550 },
            nvme: { latencyMs: 0.15, throughputMiB: 3500 }
        };

        return profile[volume.type];
    }
}

async function asynchronousSnapshotOperation(volume, snapshotId) {
    // Promises model the fact that cloud storage operations are remote and
    // may complete asynchronously rather than behaving like local memory.
    await new Promise((resolve) => setTimeout(resolve, 50));

    return volume.snapshot(snapshotId, Math.ceil(volume.usedGiB * 256));
}

async function runScenario() {
    const controller = new BlockStorageController();

    const applicationNode = new ComputeNode("app-01", "zone-a");
    const backupNode = new ComputeNode("backup-01", "zone-a");

    const databaseVolume = new Volume({
        id: "database-nvme",
        capacityGiB: 250,
        type: "nvme",
        zone: "zone-a"
    });

    const backupVolume = new Volume({
        id: "backup-ssd",
        capacityGiB: 1000,
        type: "ssd",
        zone: "zone-a"
    });

    controller.addInstance(applicationNode);
    controller.addInstance(backupNode);
    controller.addVolume(databaseVolume);
    controller.addVolume(backupVolume);

    controller.attach("database-nvme", "app-01");
    controller.attach("backup-ssd", "backup-01");

    databaseVolume.write(90);
    backupVolume.write(320);

    const snapshotA = await asynchronousSnapshotOperation(
        databaseVolume,
        "database-before-maintenance"
    );

    databaseVolume.write(20);

    const snapshotB = await asynchronousSnapshotOperation(
        databaseVolume,
        "database-after-maintenance"
    );

    console.log("Snapshot lifecycle");
    console.log(snapshotA);
    console.log(snapshotB);

    console.log("\nPerformance characteristics");
    for (const volume of [databaseVolume, backupVolume]) {
        console.log(volume.id, controller.estimatePerformance(volume));
    }

    try {
        controller.attach("database-nvme", "backup-01");
    } catch (error) {
        console.log(`Expected attachment failure: ${error.message}`);
    }

    controller.detach("database-nvme", "app-01");

    console.log("\nFinal volume state");
    for (const volume of controller.volumes.values()) {
        console.log({
            id: volume.id,
            type: volume.type,
            usedGiB: volume.usedGiB,
            capacityGiB: volume.capacityGiB,
            attachedInstance: volume.attachedInstance,
            snapshotCount: volume.snapshots.length
        });
    }
}

runScenario().catch((error) => {
    console.error("Storage workflow failed:", error.message);
    process.exitCode = 1;
});
