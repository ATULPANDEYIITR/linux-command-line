"use strict";

/*
 * Storage Virtualization
 *
 * This Node.js program models a block-storage service in which physical disks
 * are aggregated into a storage pool and exposed through virtual disks and
 * logical volumes.
 *
 * The implementation deliberately uses JavaScript-specific event-driven behavior:
 * storage operations emit lifecycle events, and asynchronous API-style methods
 * expose the sort of interface an application service could consume.
 *
 * Run with:
 *   node storage_virtualization.js
 */

const crypto = require("crypto");
const { EventEmitter } = require("events");

const VolumeType = Object.freeze({
    THICK: "thick",
    THIN: "thin"
});

const DiskState = Object.freeze({
    ONLINE: "online",
    DEGRADED: "degraded",
    FAILED: "failed"
});

class StorageError extends Error {
    constructor(message) {
        super(message);
        this.name = "StorageError";
    }
}

class CapacityError extends StorageError {
    constructor(message) {
        super(message);
        this.name = "CapacityError";
    }
}

class ValidationError extends StorageError {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

class NotFoundError extends StorageError {
    constructor(message) {
        super(message);
        this.name = "NotFoundError";
    }
}

function assertPositiveInteger(value, fieldName) {
    if (!Number.isInteger(value) || value <= 0) {
        throw new ValidationError(`${fieldName} must be a positive integer.`);
    }
}

class PhysicalDisk {
    constructor(id, capacityGiB) {
        assertPositiveInteger(capacityGiB, "capacityGiB");

        this.id = id;
        this.capacityGiB = capacityGiB;
        this.allocatedGiB = 0;
        this.state = DiskState.ONLINE;
    }

    get freeGiB() {
        return this.capacityGiB - this.allocatedGiB;
    }

    allocate(amountGiB) {
        assertPositiveInteger(amountGiB, "amountGiB");

        if (this.state === DiskState.FAILED) {
            throw new StorageError(`Physical disk ${this.id} has failed.`);
        }

        if (amountGiB > this.freeGiB) {
            throw new CapacityError(`Disk ${this.id} does not have enough capacity.`);
        }

        this.allocatedGiB += amountGiB;
    }

    release(amountGiB) {
        assertPositiveInteger(amountGiB, "amountGiB");

        if (amountGiB > this.allocatedGiB) {
            throw new ValidationError(`Disk ${this.id} cannot release unallocated capacity.`);
        }

        this.allocatedGiB -= amountGiB;
    }

    fail() {
        this.state = DiskState.FAILED;
    }
}

class StoragePool {
    constructor(id) {
        this.id = id;
        this.disks = new Map();
    }

    addDisk(disk) {
        if (this.disks.has(disk.id)) {
            throw new ValidationError(`Disk ${disk.id} already exists.`);
        }

        this.disks.set(disk.id, disk);
    }

    get totalGiB() {
        return [...this.disks.values()]
            .reduce((sum, disk) => sum + disk.capacityGiB, 0);
    }

    get usableGiB() {
        return [...this.disks.values()]
            .filter(disk => disk.state !== DiskState.FAILED)
            .reduce((sum, disk) => sum + disk.capacityGiB, 0);
    }

    get allocatedGiB() {
        return [...this.disks.values()]
            .reduce((sum, disk) => sum + disk.allocatedGiB, 0);
    }

    get freeGiB() {
        return this.usableGiB - this.allocatedGiB;
    }

    allocate(amountGiB) {
        assertPositiveInteger(amountGiB, "amountGiB");

        if (amountGiB > this.freeGiB) {
            throw new CapacityError(
                `Pool ${this.id} has only ${this.freeGiB} GiB free.`
            );
        }

        let remaining = amountGiB;
        const placements = [];

        // Largest-free-first placement is intentionally simple. Real storage
        // pools may use RAID stripes, extents, replication groups, or topology
        // awareness instead of this policy.
        const disks = [...this.disks.values()]
            .filter(disk => disk.state !== DiskState.FAILED)
            .sort((a, b) => b.freeGiB - a.freeGiB);

        for (const disk of disks) {
            const amount = Math.min(remaining, disk.freeGiB);

            if (amount > 0) {
                disk.allocate(amount);
                placements.push({
                    diskId: disk.id,
                    amountGiB: amount
                });
                remaining -= amount;
            }

            if (remaining === 0) {
                break;
            }
        }

        if (remaining !== 0) {
            for (const placement of placements) {
                this.disks.get(placement.diskId).release(placement.amountGiB);
            }

            throw new CapacityError("Pool placement failed and was rolled back.");
        }

        return placements;
    }

    release(placements) {
        for (const placement of placements) {
            const disk = this.disks.get(placement.diskId);

            if (!disk) {
                throw new NotFoundError(`Disk ${placement.diskId} does not exist.`);
            }

            disk.release(placement.amountGiB);
        }
    }
}

class VirtualDisk {
    constructor({ id, poolId, capacityGiB, volumeType, placements, allocatedGiB }) {
        this.id = id;
        this.poolId = poolId;
        this.capacityGiB = capacityGiB;
        this.volumeType = volumeType;
        this.placements = placements;
        this.allocatedGiB = allocatedGiB;
    }
}

class LogicalVolume {
    constructor(id, virtualDiskId, blockSize = 4096) {
        assertPositiveInteger(blockSize, "blockSize");

        if ((blockSize & (blockSize - 1)) !== 0) {
            throw new ValidationError("blockSize must be a power of two.");
        }

        this.id = id;
        this.virtualDiskId = virtualDiskId;
        this.blockSize = blockSize;
        this.blocks = new Map();
        this.logicalBlocks = 0;
    }

    configureCapacity(capacityGiB) {
        const bytes = capacityGiB * 1024 ** 3;
        this.logicalBlocks = Math.floor(bytes / this.blockSize);

        if (this.logicalBlocks === 0) {
            throw new ValidationError("Volume capacity is smaller than one block.");
        }
    }

    validateBlock(blockNumber, data = null) {
        if (!Number.isInteger(blockNumber) ||
            blockNumber < 0 ||
            blockNumber >= this.logicalBlocks) {
            throw new ValidationError(
                `Block ${blockNumber} is outside volume ${this.id}.`
            );
        }

        if (data !== null && data.length > this.blockSize) {
            throw new ValidationError(
                `Payload exceeds ${this.blockSize}-byte block size.`
            );
        }
    }

    write(blockNumber, data) {
        this.validateBlock(blockNumber, data);

        // Buffer makes the block content explicit and prevents accidental
        // mutation through a shared ArrayBuffer reference.
        const block = Buffer.alloc(this.blockSize);
        data.copy(block);
        this.blocks.set(blockNumber, block);
    }

    read(blockNumber) {
        this.validateBlock(blockNumber);

        if (!this.blocks.has(blockNumber)) {
            return Buffer.alloc(this.blockSize);
        }

        return Buffer.from(this.blocks.get(blockNumber));
    }
}

class StorageService extends EventEmitter {
    constructor() {
        super();
        this.pools = new Map();
        this.virtualDisks = new Map();
        this.volumes = new Map();
        this.snapshots = new Map();
        this.generation = 0;
    }

    createPool(id) {
        if (this.pools.has(id)) {
            throw new ValidationError(`Pool ${id} already exists.`);
        }

        const pool = new StoragePool(id);
        this.pools.set(id, pool);
        this.emit("pool.created", { poolId: id });
        return pool;
    }

    createVirtualDisk(id, poolId, capacityGiB, volumeType) {
        assertPositiveInteger(capacityGiB, "capacityGiB");

        if (this.virtualDisks.has(id)) {
            throw new ValidationError(`Virtual disk ${id} already exists.`);
        }

        const pool = this.pools.get(poolId);
        if (!pool) {
            throw new NotFoundError(`Pool ${poolId} does not exist.`);
        }

        if (!Object.values(VolumeType).includes(volumeType)) {
            throw new ValidationError(`Unsupported volume type: ${volumeType}`);
        }

        const physicalReservation =
            volumeType === VolumeType.THICK ? capacityGiB : 0;

        const placements = physicalReservation
            ? pool.allocate(physicalReservation)
            : [];

        const virtualDisk = new VirtualDisk({
            id,
            poolId,
            capacityGiB,
            volumeType,
            placements,
            allocatedGiB: physicalReservation
        });

        this.virtualDisks.set(id, virtualDisk);
        this.emit("virtual-disk.created", {
            virtualDiskId: id,
            capacityGiB,
            volumeType
        });

        return virtualDisk;
    }

    createVolume(id, virtualDiskId, blockSize = 4096) {
        if (this.volumes.has(id)) {
            throw new ValidationError(`Volume ${id} already exists.`);
        }

        const virtualDisk = this.virtualDisks.get(virtualDiskId);
        if (!virtualDisk) {
            throw new NotFoundError(`Virtual disk ${virtualDiskId} does not exist.`);
        }

        const volume = new LogicalVolume(id, virtualDiskId, blockSize);
        volume.configureCapacity(virtualDisk.capacityGiB);
        this.volumes.set(id, volume);

        this.emit("volume.created", {
            volumeId: id,
            virtualDiskId,
            logicalBlocks: volume.logicalBlocks
        });

        return volume;
    }

    ensureThinBacking(virtualDisk) {
        if (virtualDisk.volumeType !== VolumeType.THIN) {
            return;
        }

        const pool = this.pools.get(virtualDisk.poolId);
        const placement = pool.allocate(1);

        if (virtualDisk.allocatedGiB + 1 > virtualDisk.capacityGiB) {
            pool.release(placement);
            throw new CapacityError(
                `Thin virtual disk ${virtualDisk.id} reached its logical capacity.`
            );
        }

        virtualDisk.placements.push(...placement);
        virtualDisk.allocatedGiB += 1;
    }

    async writeBlock(volumeId, blockNumber, text) {
        // Promise-based scheduling resembles an I/O service boundary even though
        // this simulation performs the operation entirely in memory.
        await new Promise(resolve => setImmediate(resolve));

        const volume = this.volumes.get(volumeId);
        if (!volume) {
            throw new NotFoundError(`Volume ${volumeId} does not exist.`);
        }

        const data = Buffer.from(text, "utf8");
        volume.validateBlock(blockNumber, data);

        if (!volume.blocks.has(blockNumber)) {
            this.ensureThinBacking(this.virtualDisks.get(volume.virtualDiskId));
        }

        volume.write(blockNumber, data);
        this.generation += 1;

        this.emit("block.written", {
            volumeId,
            blockNumber,
            generation: this.generation,
            bytes: data.length
        });
    }

    async readBlock(volumeId, blockNumber) {
        await new Promise(resolve => setImmediate(resolve));

        const volume = this.volumes.get(volumeId);
        if (!volume) {
            throw new NotFoundError(`Volume ${volumeId} does not exist.`);
        }

        const data = volume.read(blockNumber);

        this.emit("block.read", {
            volumeId,
            blockNumber,
            generation: this.generation
        });

        return data;
    }

    createSnapshot(snapshotId, volumeId) {
        if (this.snapshots.has(snapshotId)) {
            throw new ValidationError(`Snapshot ${snapshotId} already exists.`);
        }

        const volume = this.volumes.get(volumeId);
        if (!volume) {
            throw new NotFoundError(`Volume ${volumeId} does not exist.`);
        }

        // Copy-on-write systems normally avoid copying every block immediately.
        // This educational model copies mappings so snapshot semantics remain
        // easy to inspect.
        const blocks = new Map(
            [...volume.blocks.entries()]
                .map(([number, buffer]) => [number, Buffer.from(buffer)])
        );

        this.snapshots.set(snapshotId, {
            id: snapshotId,
            volumeId,
            generation: this.generation,
            blocks
        });

        this.emit("snapshot.created", {
            snapshotId,
            volumeId,
            generation: this.generation
        });
    }

    restoreSnapshot(snapshotId) {
        const snapshot = this.snapshots.get(snapshotId);
        if (!snapshot) {
            throw new NotFoundError(`Snapshot ${snapshotId} does not exist.`);
        }

        const volume = this.volumes.get(snapshot.volumeId);
        if (!volume) {
            throw new NotFoundError(`Volume ${snapshot.volumeId} does not exist.`);
        }

        volume.blocks = new Map(
            [...snapshot.blocks.entries()]
                .map(([number, buffer]) => [number, Buffer.from(buffer)])
        );

        this.generation += 1;

        this.emit("snapshot.restored", {
            snapshotId,
            volumeId: volume.id,
            generation: this.generation
        });
    }

    status() {
        return {
            generation: this.generation,
            pools: [...this.pools.values()].map(pool => ({
                id: pool.id,
                totalGiB: pool.totalGiB,
                usableGiB: pool.usableGiB,
                allocatedGiB: pool.allocatedGiB,
                freeGiB: pool.freeGiB
            })),
            virtualDisks: [...this.virtualDisks.values()].map(disk => ({
                id: disk.id,
                logicalGiB: disk.capacityGiB,
                physicalGiB: disk.allocatedGiB,
                type: disk.volumeType
            })),
            volumes: [...this.volumes.values()].map(volume => ({
                id: volume.id,
                blocks: volume.logicalBlocks,
                allocatedBlocks: volume.blocks.size
            }))
        };
    }
}

function digest(buffer) {
    return crypto.createHash("sha256").update(buffer).digest("hex");
}

function registerAuditListeners(service) {
    service.on("block.written", event => {
        console.log(
            `[audit] WRITE volume=${event.volumeId} ` +
            `block=${event.blockNumber} generation=${event.generation}`
        );
    });

    service.on("snapshot.created", event => {
        console.log(
            `[audit] SNAPSHOT ${event.snapshotId} ` +
            `volume=${event.volumeId} generation=${event.generation}`
        );
    });

    service.on("snapshot.restored", event => {
        console.log(
            `[audit] RESTORE ${event.snapshotId} ` +
            `volume=${event.volumeId} generation=${event.generation}`
        );
    });
}

async function runCaseStudy() {
    console.log("=== STORAGE VIRTUALIZATION EVENT-DRIVEN CASE STUDY ===");

    const service = new StorageService();
    registerAuditListeners(service);

    const pool = service.createPool("production-pool");
    pool.addDisk(new PhysicalDisk("ssd-01", 40));
    pool.addDisk(new PhysicalDisk("ssd-02", 40));
    pool.addDisk(new PhysicalDisk("ssd-03", 40));

    service.createVirtualDisk(
        "vd-orders",
        "production-pool",
        50,
        VolumeType.THICK
    );

    service.createVirtualDisk(
        "vd-reporting",
        "production-pool",
        70,
        VolumeType.THIN
    );

    service.createVolume("orders", "vd-orders", 4096);
    service.createVolume("reporting", "vd-reporting", 4096);

    await service.writeBlock(
        "orders",
        20,
        "order_id=ORD-2026-0042 state=PAID"
    );

    const firstRead = await service.readBlock("orders", 20);
    console.log("Read value:", firstRead.toString("utf8").replace(/\0+$/, ""));
    console.log("Checksum:", digest(firstRead));

    await service.writeBlock(
        "reporting",
        1000,
        "monthly revenue aggregation result"
    );

    service.createSnapshot("orders-before-correction", "orders");

    await service.writeBlock(
        "orders",
        20,
        "order_id=ORD-2026-0042 state=REFUNDED"
    );

    console.log(
        "Changed value:",
        (await service.readBlock("orders", 20))
            .toString("utf8")
            .replace(/\0+$/, "")
    );

    service.restoreSnapshot("orders-before-correction");

    console.log(
        "Restored value:",
        (await service.readBlock("orders", 20))
            .toString("utf8")
            .replace(/\0+$/, "")
    );

    console.log("\n=== RESOURCE STATUS ===");
    console.table(service.status().pools);
    console.table(service.status().virtualDisks);
    console.table(service.status().volumes);

    console.log("\n=== FAILURE TESTS ===");

    try {
        await service.readBlock("orders", -1);
    } catch (error) {
        console.log(`Invalid block rejected: ${error.message}`);
    }

    try {
        await service.createVirtualDisk(
            "vd-too-large",
            "production-pool",
            500,
            VolumeType.THICK
        );
    } catch (error) {
        console.log(`Capacity request rejected: ${error.message}`);
    }

    pool.disks.get("ssd-03").fail();

    console.log(
        `Pool usable capacity after physical failure: ${pool.usableGiB} GiB`
    );

    console.log("\n=== DESIGN BOUNDARY ===");
    console.log(
        "Applications address logical volumes. Virtual disks hide physical "
        + "placement. The storage pool owns capacity allocation."
    );
    console.log(
        "This model does not claim that a failed disk is automatically recoverable. "
        + "Real resilience requires replication, RAID, or erasure coding."
    );
}

runCaseStudy().catch(error => {
    console.error(`Fatal storage operation: ${error.message}`);
    process.exitCode = 1;
});
