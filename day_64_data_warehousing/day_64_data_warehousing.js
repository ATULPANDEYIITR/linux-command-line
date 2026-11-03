"use strict";

/*
 * Data Warehousing: event-driven ETL and analytical query demonstration.
 *
 * Run with Node.js 18 or later:
 *   node data-warehouse.js
 *
 * This implementation uses an event-driven source, asynchronous batch
 * processing, immutable staging records, Map-based dimensions, a
 * deduplicated fact store, quality quarantine and OLAP-style aggregation.
 */

const { EventEmitter } = require("node:events");

const MAX_SAFE_CENTS = Number.MAX_SAFE_INTEGER;

class DataQualityError extends Error {
    constructor(message, recordId) {
        super(message);
        this.name = "DataQualityError";
        this.recordId = recordId;
    }
}

class SourceStore extends EventEmitter {
    constructor() {
        super();

        this.customers = new Map([
            ["C001", Object.freeze({
                customerId: "C001",
                name: "Asha Mehta",
                region: "North"
            })],
            ["C002", Object.freeze({
                customerId: "C002",
                name: "Rohan Singh",
                region: "South"
            })],
            ["C003", Object.freeze({
                customerId: "C003",
                name: "Mira Das",
                region: "West"
            })]
        ]);

        this.products = new Map([
            ["P100", Object.freeze({
                productId: "P100",
                name: "Laptop",
                category: "Electronics"
            })],
            ["P200", Object.freeze({
                productId: "P200",
                name: "Monitor",
                category: "Electronics"
            })],
            ["P300", Object.freeze({
                productId: "P300",
                name: "Office Chair",
                category: "Furniture"
            })]
        ]);

        this.changeLog = [];
        this.nextSequence = 1;
    }

    publishSale(sale) {
        const required = [
            "saleId",
            "customerId",
            "productId",
            "saleDate",
            "quantity",
            "unitPriceCents",
            "status"
        ];

        for (const field of required) {
            if (!(field in sale)) {
                throw new TypeError(`Missing source field: ${field}`);
            }
        }

        if (typeof sale.saleId !== "string" || sale.saleId.trim() === "") {
            throw new TypeError("saleId must be a non-empty string");
        }

        if (typeof sale.customerId !== "string" ||
            typeof sale.productId !== "string") {
            throw new TypeError("Dimension identifiers must be strings");
        }

        if (typeof sale.saleDate !== "string" ||
            !/^\d{4}-\d{2}-\d{2}$/.test(sale.saleDate)) {
            throw new TypeError("saleDate must use YYYY-MM-DD format");
        }

        if (!Number.isSafeInteger(sale.quantity) ||
            !Number.isSafeInteger(sale.unitPriceCents)) {
            throw new TypeError("Quantity and price must be safe integers");
        }

        if (!["COMPLETED", "CANCELLED", "PENDING"].includes(sale.status)) {
            throw new TypeError("Unsupported sale status");
        }

        const change = Object.freeze({
            ...sale,
            sequence: this.nextSequence++,
            changedAt: new Date().toISOString()
        });

        this.changeLog.push(change);
        this.emit("sale.changed", change);

        return change.sequence;
    }

    async *readChangesAfter(sequence, batchSize = 100) {
        if (!Number.isSafeInteger(sequence) || sequence < 0) {
            throw new RangeError("Invalid change sequence");
        }

        if (!Number.isSafeInteger(batchSize) || batchSize < 1) {
            throw new RangeError("Batch size must be a positive integer");
        }

        const changes = this.changeLog.filter(
            item => item.sequence > sequence
        );

        for (let offset = 0; offset < changes.length; offset += batchSize) {
            await Promise.resolve();
            yield changes.slice(offset, offset + batchSize);
        }
    }
}

class AnalyticalStore {
    constructor() {
        this.customers = new Map();
        this.products = new Map();
        this.facts = new Map();
        this.quarantine = new Map();
        this.lastSequence = 0;
        this.loadHistory = [];
    }

    snapshot() {
        return {
            customers: new Map(this.customers),
            products: new Map(this.products),
            facts: new Map(this.facts),
            quarantine: new Map(this.quarantine),
            lastSequence: this.lastSequence,
            loadHistory: [...this.loadHistory]
        };
    }

    commit(snapshot) {
        this.customers = snapshot.customers;
        this.products = snapshot.products;
        this.facts = snapshot.facts;
        this.quarantine = snapshot.quarantine;
        this.lastSequence = snapshot.lastSequence;
        this.loadHistory = snapshot.loadHistory;
    }

    revenueByRegion() {
        const groups = new Map();

        for (const fact of this.facts.values()) {
            const customer = this.customers.get(fact.customerId);
            if (!customer) {
                throw new Error(
                    `Warehouse integrity error: missing ${fact.customerId}`
                );
            }

            const current = groups.get(customer.region) || {
                region: customer.region,
                sales: 0,
                units: 0,
                revenueCents: 0
            };

            current.sales += 1;
            current.units += fact.quantity;
            current.revenueCents += fact.grossCents;
            groups.set(customer.region, current);
        }

        return [...groups.values()].sort(
            (a, b) => b.revenueCents - a.revenueCents
        );
    }

    revenueByProduct() {
        const groups = new Map();

        for (const fact of this.facts.values()) {
            const product = this.products.get(fact.productId);
            if (!product) {
                throw new Error(
                    `Warehouse integrity error: missing ${fact.productId}`
                );
            }

            const current = groups.get(product.productId) || {
                product: product.name,
                category: product.category,
                units: 0,
                revenueCents: 0
            };

            current.units += fact.quantity;
            current.revenueCents += fact.grossCents;
            groups.set(product.productId, current);
        }

        return [...groups.values()].sort(
            (a, b) => b.revenueCents - a.revenueCents
        );
    }
}

class WarehousePipeline extends EventEmitter {
    constructor(source, warehouse, options = {}) {
        super();

        this.source = source;
        this.warehouse = warehouse;
        this.batchSize = options.batchSize ?? 2;
        this.maxRejectRatio = options.maxRejectRatio ?? 0.30;
        this.isRunning = false;

        if (!Number.isSafeInteger(this.batchSize) || this.batchSize < 1) {
            throw new RangeError("Invalid batch size");
        }

        if (this.maxRejectRatio < 0 || this.maxRejectRatio > 1) {
            throw new RangeError("Reject ratio must be between 0 and 1");
        }

        // Events expose source activity and operational failures without
        // coupling the source system to warehouse implementation details.
        this.sourceListener = change => {
            this.emit("source.received", change.sequence);
        };

        this.source.on("sale.changed", this.sourceListener);
    }

    validate(change, customers, products) {
        if (!Number.isSafeInteger(change.quantity) || change.quantity <= 0) {
            throw new DataQualityError(
                "Quantity must be greater than zero",
                change.saleId
            );
        }

        if (!Number.isSafeInteger(change.unitPriceCents) ||
            change.unitPriceCents < 0) {
            throw new DataQualityError(
                "Unit price must be a non-negative integer",
                change.saleId
            );
        }

        if (change.quantity * change.unitPriceCents > MAX_SAFE_CENTS) {
            throw new DataQualityError(
                "Gross amount exceeds safe integer precision",
                change.saleId
            );
        }

        const parsedDate = new Date(`${change.saleDate}T00:00:00Z`);
        if (Number.isNaN(parsedDate.getTime()) ||
            parsedDate.toISOString().slice(0, 10) !== change.saleDate) {
            throw new DataQualityError("Invalid calendar date", change.saleId);
        }

        if (!customers.has(change.customerId)) {
            throw new DataQualityError(
                "Unknown customer dimension key",
                change.saleId
            );
        }

        if (!products.has(change.productId)) {
            throw new DataQualityError(
                "Unknown product dimension key",
                change.saleId
            );
        }
    }

    async processBatch(changes) {
        const state = this.warehouse.snapshot();

        const metrics = {
            extracted: changes.length,
            loadedOrUpdated: 0,
            unchanged: 0,
            quarantined: 0,
            skipped: 0
        };

        try {
            for (const change of changes) {
                // Incomplete operational transactions are not facts in the
                // analytical sales model.
                if (change.status !== "COMPLETED") {
                    metrics.skipped += 1;
                    state.lastSequence = Math.max(
                        state.lastSequence,
                        change.sequence
                    );
                    continue;
                }

                try {
                    this.validate(
                        change,
                        this.source.customers,
                        this.source.products
                    );
                } catch (error) {
                    if (!(error instanceof DataQualityError)) {
                        throw error;
                    }

                    state.quarantine.set(change.sequence, Object.freeze({
                        sequence: change.sequence,
                        saleId: change.saleId,
                        reason: error.message,
                        capturedAt: new Date().toISOString()
                    }));

                    metrics.quarantined += 1;
                    state.lastSequence = Math.max(
                        state.lastSequence,
                        change.sequence
                    );
                    continue;
                }

                // Dimensions are copied into warehouse-owned maps. A source
                // update does not expose mutable source objects to reports.
                state.customers.set(
                    change.customerId,
                    Object.freeze({ ...this.source.customers.get(change.customerId) })
                );

                state.products.set(
                    change.productId,
                    Object.freeze({ ...this.source.products.get(change.productId) })
                );

                const previous = state.facts.get(change.saleId);

                if (previous &&
                    previous.sourceSequence >= change.sequence) {
                    metrics.unchanged += 1;
                } else {
                    const fact = Object.freeze({
                        saleId: change.saleId,
                        sourceSequence: change.sequence,
                        customerId: change.customerId,
                        productId: change.productId,
                        saleDate: change.saleDate,
                        quantity: change.quantity,
                        unitPriceCents: change.unitPriceCents,
                        grossCents: change.quantity * change.unitPriceCents
                    });

                    state.facts.set(change.saleId, fact);
                    metrics.loadedOrUpdated += 1;
                }

                state.lastSequence = Math.max(
                    state.lastSequence,
                    change.sequence
                );
            }

            const rejectRatio = metrics.extracted === 0
                ? 0
                : metrics.quarantined / metrics.extracted;

            if (rejectRatio > this.maxRejectRatio) {
                throw new Error(
                    `Quality gate failed: reject ratio ${rejectRatio.toFixed(3)} ` +
                    `exceeds ${this.maxRejectRatio.toFixed(3)}`
                );
            }

            state.loadHistory.push(Object.freeze({
                completedAt: new Date().toISOString(),
                ...metrics
            }));

            // State is replaced only after the batch satisfies the quality
            // policy. Technical or policy failures do not partially load it.
            this.warehouse.commit(state);
            this.emit("batch.loaded", metrics);

            return metrics;
        } catch (error) {
            this.emit("batch.failed", error);
            throw error;
        }
    }

    async run() {
        if (this.isRunning) {
            throw new Error("A pipeline run is already active");
        }

        this.isRunning = true;
        const allMetrics = [];

        try {
            for await (
                const batch of this.source.readChangesAfter(
                    this.warehouse.lastSequence,
                    this.batchSize
                )
            ) {
                const result = await this.processBatch(batch);
                allMetrics.push(result);
            }

            this.emit("pipeline.completed", allMetrics);
            return allMetrics;
        } finally {
            this.isRunning = false;
        }
    }

    close() {
        this.source.off("sale.changed", this.sourceListener);
    }
}

function displayReport(title, rows) {
    console.log(`\n${title}`);

    if (rows.length === 0) {
        console.log("No facts are available.");
        return;
    }

    for (const row of rows) {
        const revenue = (row.revenueCents / 100).toFixed(2);
        console.log(`${JSON.stringify(row)} | revenue=${revenue}`);
    }
}

async function main() {
    const source = new SourceStore();
    const warehouse = new AnalyticalStore();

    const pipeline = new WarehousePipeline(source, warehouse, {
        batchSize: 2,
        maxRejectRatio: 0.30
    });

    pipeline.on("batch.loaded", metrics => {
        console.log("Batch committed:", metrics);
    });

    pipeline.on("batch.failed", error => {
        console.error("Batch failed:", error.message);
    });

    pipeline.on("source.received", sequence => {
        console.log(`Source change received: ${sequence}`);
    });

    source.publishSale({
        saleId: "S1001",
        customerId: "C001",
        productId: "P100",
        saleDate: "2026-10-01",
        quantity: 2,
        unitPriceCents: 75000,
        status: "COMPLETED"
    });

    source.publishSale({
        saleId: "S1002",
        customerId: "C002",
        productId: "P200",
        saleDate: "2026-10-02",
        quantity: 1,
        unitPriceCents: 22000,
        status: "COMPLETED"
    });

    source.publishSale({
        saleId: "S1003",
        customerId: "C003",
        productId: "P300",
        saleDate: "2026-10-03",
        quantity: 3,
        unitPriceCents: 12000,
        status: "COMPLETED"
    });

    source.publishSale({
        saleId: "S1004",
        customerId: "C001",
        productId: "P200",
        saleDate: "2026-10-04",
        quantity: -1,
        unitPriceCents: 22000,
        status: "COMPLETED"
    });

    source.publishSale({
        saleId: "S1005",
        customerId: "C002",
        productId: "P100",
        saleDate: "2026-10-05",
        quantity: 1,
        unitPriceCents: 75000,
        status: "CANCELLED"
    });

    const firstRun = await pipeline.run();
    console.log("\nInitial batch count:", firstRun.length);
    console.log("Fact count:", warehouse.facts.size);
    console.log("Quarantine count:", warehouse.quarantine.size);

    displayReport("Revenue by region", warehouse.revenueByRegion());
    displayReport("Revenue by product", warehouse.revenueByProduct());

    // A corrected event uses the same business sale ID and a higher source
    // sequence. The warehouse updates the fact instead of duplicating it.
    source.publishSale({
        saleId: "S1001",
        customerId: "C001",
        productId: "P100",
        saleDate: "2026-10-01",
        quantity: 3,
        unitPriceCents: 75000,
        status: "COMPLETED"
    });

    await pipeline.run();

    const corrected = warehouse.facts.get("S1001");
    if (corrected.quantity !== 3) {
        throw new Error("Correction was not applied");
    }

    if (warehouse.facts.size !== 3) {
        throw new Error("Idempotency check failed");
    }

    const emptyRun = await pipeline.run();
    if (emptyRun.length !== 0) {
        throw new Error("A no-change run should not create batches");
    }

    console.log("\nCorrected sale quantity:", corrected.quantity);
    console.log("Final fact count:", warehouse.facts.size);
    console.log("All checks passed.");

    pipeline.close();
}

main().catch(error => {
    console.error("Warehouse execution failed:", error.message);
    process.exitCode = 1;
});
