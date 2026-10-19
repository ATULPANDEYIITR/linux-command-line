"use strict";

/*
 * Storage Performance Laboratory
 *
 * This Node.js program models storage performance using JavaScript-specific
 * event-driven behavior. It focuses on:
 * IOPS, throughput, latency, caching, storage tiers, queue depth,
 * asynchronous completion, batching, and workload measurement.
 *
 * No third-party packages are required.
 */

const { performance } = require("node:perf_hooks");

const MiB = 1024 * 1024;

const StorageTier = Object.freeze({
    NVME: "NVMe",
    SSD: "SSD",
    HDD: "HDD",
    ARCHIVE: "Archive"
});

const profiles = Object.freeze({
    [StorageTier.NVME]: {
        iops: 900000,
        throughputMiB: 7000,
        latencyMs: 0.08,
        jitterMs: 0.04
    },
    [StorageTier.SSD]: {
        iops: 120000,
        throughputMiB: 1200,
        latencyMs: 0.45,
        jitterMs: 0.20
    },
    [StorageTier.HDD]: {
        iops: 300,
        throughputMiB: 250,
        latencyMs: 8,
        jitterMs: 3
    },
    [StorageTier.ARCHIVE]: {
        iops: 50,
        throughputMiB: 100,
        latencyMs: 80,
        jitterMs: 20
    }
});

function validatePositive(value, name) {
    if (!Number.isFinite(value) || value <= 0) {
        throw new RangeError(`${name} must be a positive finite number`);
    }
}

function theoreticalIOPS(latencyMs, queueDepth = 1) {
    validatePositive(latencyMs, "Latency");
    validatePositive(queueDepth, "Queue depth");
    return queueDepth / (latencyMs / 1000);
}

function throughputMiBPerSecond(bytes, seconds) {
    validatePositive(bytes, "Bytes");
    validatePositive(seconds, "Seconds");
    return bytes / MiB / seconds;
}

function bandwidthLimitedIOPS(throughputMiB, ioSizeBytes) {
    validatePositive(throughputMiB, "Throughput");
    validatePositive(ioSizeBytes, "I/O size");
    return throughputMiB * MiB / ioSizeBytes;
}

class LRUCache {
    constructor(capacityBytes) {
        validatePositive(capacityBytes, "Cache capacity");
        this.capacityBytes = capacityBytes;
        this.entries = new Map();
        this.currentBytes = 0;
    }

    get(key) {
        if (!this.entries.has(key)) {
            return undefined;
        }

        const value = this.entries.get(key);

        // Map insertion order provides a compact LRU implementation:
        // deleting and reinserting makes the key most recently used.
        this.entries.delete(key);
        this.entries.set(key, value);

        return value;
    }

    set(key, value) {
        const size = value.byteLength;

        if (size > this.capacityBytes) {
            return;
        }

        if (this.entries.has(key)) {
            this.currentBytes -= this.entries.get(key).byteLength;
            this.entries.delete(key);
        }

        while (
            this.currentBytes + size > this.capacityBytes &&
            this.entries.size > 0
        ) {
            const oldestKey = this.entries.keys().next().value;
            const oldestValue = this.entries.get(oldestKey);
            this.entries.delete(oldestKey);
            this.currentBytes -= oldestValue.byteLength;
        }

        this.entries.set(key, value);
        this.currentBytes += size;
    }

    get size() {
        return this.entries.size;
    }
}

class StorageDevice extends EventTarget {
    constructor(tier, cacheBytes = 0) {
        super();

        if (!profiles[tier]) {
            throw new Error(`Unknown storage tier: ${tier}`);
        }

        this.tier = tier;
        this.profile = profiles[tier];
        this.cache = cacheBytes > 0 ? new LRUCache(cacheBytes) : null;
    }

    calculateLatency(sizeBytes) {
        validatePositive(sizeBytes, "I/O size");

        const bandwidthMs =
            (sizeBytes / MiB) / this.profile.throughputMiB * 1000;

        const iopsMs = 1000 / this.profile.iops;

        return (
            this.profile.latencyMs +
            Math.max(bandwidthMs, iopsMs) +
            Math.random() * this.profile.jitterMs
        );
    }

    read(blockId, sizeBytes) {
        validatePositive(sizeBytes, "Read size");

        if (this.cache) {
            const cached = this.cache.get(blockId);

            if (cached) {
                const result = {
                    operation: "read",
                    blockId,
                    sizeBytes,
                    latencyMs: 0.03,
                    cacheHit: true,
                    tier: this.tier
                };

                this.dispatchEvent(
                    new CustomEvent("complete", { detail: result })
                );

                return Promise.resolve(result);
            }
        }

        const latencyMs = this.calculateLatency(sizeBytes);

        return new Promise((resolve) => {
            // setTimeout represents asynchronous device completion rather than
            // blocking the Node.js event loop while an I/O request is pending.
            setTimeout(() => {
                if (this.cache) {
                    this.cache.set(blockId, new Uint8Array(sizeBytes));
                }

                const result = {
                    operation: "read",
                    blockId,
                    sizeBytes,
                    latencyMs,
                    cacheHit: false,
                    tier: this.tier
                };

                this.dispatchEvent(
                    new CustomEvent("complete", { detail: result })
                );

                resolve(result);
            }, Math.max(0, latencyMs));
        });
    }

    write(blockId, sizeBytes) {
        validatePositive(sizeBytes, "Write size");

        const latencyMs = this.calculateLatency(sizeBytes);

        return new Promise((resolve) => {
            setTimeout(() => {
                if (this.cache) {
                    this.cache.set(blockId, new Uint8Array(sizeBytes));
                }

                const result = {
                    operation: "write",
                    blockId,
                    sizeBytes,
                    latencyMs,
                    cacheHit: false,
                    tier: this.tier
                };

                this.dispatchEvent(
                    new CustomEvent("complete", { detail: result })
                );

                resolve(result);
            }, Math.max(0, latencyMs));
        });
    }
}

class PerformanceCollector {
    constructor() {
        this.operations = [];
    }

    record(result) {
        this.operations.push(result);
    }

    get count() {
        return this.operations.length;
    }

    get bytes() {
        return this.operations.reduce(
            (total, operation) => total + operation.sizeBytes,
            0
        );
    }

    get averageLatencyMs() {
        if (!this.operations.length) {
            return 0;
        }

        return (
            this.operations.reduce(
                (total, operation) => total + operation.latencyMs,
                0
            ) / this.operations.length
        );
    }

    percentile(percent) {
        if (this.operations.length === 0) {
            return 0;
        }

        const values = this.operations
            .map((operation) => operation.latencyMs)
            .sort((a, b) => a - b);

        const position = (values.length - 1) * percent / 100;
        const lower = Math.floor(position);
        const upper = Math.ceil(position);

        if (lower === upper) {
            return values[lower];
        }

        return (
            values[lower] +
            (values[upper] - values[lower]) * (position - lower)
        );
    }

    get cacheHitRate() {
        if (!this.operations.length) {
            return 0;
        }

        const hits = this.operations.filter(
            operation => operation.cacheHit
        ).length;

        return hits / this.operations.length;
    }
}

function createHotSetWorkload(count, blockSize, hotBlocks) {
    validatePositive(count, "Count");
    validatePositive(blockSize, "Block size");
    validatePositive(hotBlocks, "Hot block count");

    return Array.from({ length: count }, () => {
        const blockId = Math.floor(Math.random() * hotBlocks);

        return {
            operation: "read",
            blockId,
            sizeBytes: blockSize
        };
    });
}

async function runConcurrentWorkload(
    device,
    requests,
    queueDepth
) {
    validatePositive(queueDepth, "Queue depth");

    const collector = new PerformanceCollector();
    let nextRequest = 0;

    async function worker() {
        while (true) {
            const index = nextRequest++;

            if (index >= requests.length) {
                return;
            }

            const request = requests[index];

            const result = request.operation === "read"
                ? await device.read(request.blockId, request.sizeBytes)
                : await device.write(request.blockId, request.sizeBytes);

            collector.record(result);
        }
    }

    const workers = Array.from(
        { length: Math.min(queueDepth, requests.length) },
        () => worker()
    );

    await Promise.all(workers);
    return collector;
}

function printMetrics(label, collector, elapsedSeconds) {
    console.log(`\n${label}`);
    console.log(`Operations:      ${collector.count}`);
    console.log(`Throughput:      ${throughputMiBPerSecond(
        collector.bytes,
        elapsedSeconds
    ).toFixed(2)} MiB/s`);
    console.log(`Observed IOPS:    ${(
        collector.count / elapsedSeconds
    ).toFixed(2)}`);
    console.log(`Average latency: ${collector.averageLatencyMs.toFixed(3)} ms`);
    console.log(`P95 latency:     ${collector.percentile(95).toFixed(3)} ms`);
    console.log(`P99 latency:     ${collector.percentile(99).toFixed(3)} ms`);
    console.log(`Cache hit rate:  ${(collector.cacheHitRate * 100).toFixed(2)}%`);
}

function showIOPSBandwidthRelationship() {
    console.log("\n=== IOPS versus Throughput ===");

    const profile = profiles[StorageTier.NVME];

    for (const ioSize of [4096, 65536, 1048576]) {
        const bandwidthLimit = bandwidthLimitedIOPS(
            profile.throughputMiB,
            ioSize
        );

        console.log(
            `${ioSize} bytes -> bandwidth-limited IOPS ` +
            `${bandwidthLimit.toFixed(0)}`
        );
    }
}

async function compareQueueDepths() {
    console.log("\n=== Queue Depth Experiment ===");

    const requests = Array.from({ length: 80 }, (_, index) => ({
        operation: "read",
        blockId: index,
        sizeBytes: 4096
    }));

    for (const queueDepth of [1, 4, 16, 32]) {
        const device = new StorageDevice(StorageTier.SSD);

        const start = performance.now();
        const collector = await runConcurrentWorkload(
            device,
            requests,
            queueDepth
        );
        const elapsedSeconds = (performance.now() - start) / 1000;

        printMetrics(
            `SSD with queue depth ${queueDepth}`,
            collector,
            elapsedSeconds
        );
    }
}

async function compareCaching() {
    console.log("\n=== Cache Experiment ===");

    const workload = createHotSetWorkload(
        200,
        4096,
        16
    );

    for (const cacheBytes of [0, 16 * 4096]) {
        const device = new StorageDevice(
            StorageTier.SSD,
            cacheBytes
        );

        const start = performance.now();
        const collector = await runConcurrentWorkload(
            device,
            workload,
            8
        );
        const elapsedSeconds = (performance.now() - start) / 1000;

        printMetrics(
            cacheBytes === 0 ? "No cache" : "16-block LRU cache",
            collector,
            elapsedSeconds
        );
    }
}

function evaluateTier({
    tier,
    dailyOperations,
    averageRequestBytes,
    latencyTargetMs
}) {
    const profile = profiles[tier];

    const bandwidthIops = bandwidthLimitedIOPS(
        profile.throughputMiB,
        averageRequestBytes
    );

    const sustainableIops = Math.min(
        profile.iops,
        bandwidthIops
    );

    return {
        tier,
        sustainableIops,
        meetsLatencyTarget: profile.latencyMs <= latencyTargetMs,
        estimatedDailyDataGiB:
            dailyOperations * averageRequestBytes / (1024 ** 3)
    };
}

function demonstrateTierSelection() {
    console.log("\n=== Workload-Aware Tier Selection ===");

    const workload = {
        dailyOperations: 5_000_000,
        averageRequestBytes: 16 * 1024,
        latencyTargetMs: 2
    };

    for (const tier of Object.values(StorageTier)) {
        const evaluation = evaluateTier({
            tier,
            ...workload
        });

        console.log(
            `${tier}: ${evaluation.sustainableIops.toFixed(0)} IOPS, ` +
            `latency target=${evaluation.meetsLatencyTarget ? "yes" : "no"}`
        );
    }
}

async function main() {
    console.log("Storage Performance Laboratory");

    showIOPSBandwidthRelationship();
    demonstrateTierSelection();
    await compareQueueDepths();
    await compareCaching();

    console.log("\n=== Performance Engineering Notes ===");
    console.log(
        "IOPS is request rate; throughput is data rate. " +
        "They are connected by I/O size."
    );
    console.log(
        "Caching can reduce backend traffic but can also introduce " +
        "staleness, eviction, memory pressure, and invalidation complexity."
    );
    console.log(
        "Queue depth exposes parallelism but excessive concurrency can " +
        "increase tail latency after the device reaches saturation."
    );
    console.log(
        "Storage tier selection should match latency, workload shape, " +
        "capacity, durability, and cost requirements."
    );
}

main().catch((error) => {
    console.error("Storage performance experiment failed:", error);
    process.exitCode = 1;
});
