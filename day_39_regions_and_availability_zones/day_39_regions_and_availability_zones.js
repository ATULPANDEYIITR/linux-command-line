"use strict";

/*
 * Event-driven geographic infrastructure simulator.
 *
 * Demonstrates zone health events, regional isolation, capacity reservations,
 * failover eligibility, recovery objectives, and idempotent event handling.
 * Run with Node.js 18 or later; no third-party packages are required.
 */

const { EventEmitter } = require("node:events");
const assert = require("node:assert/strict");

class InfrastructureError extends Error {}

class Zone {
    constructor({ id, regionId, capacity, latencyMs, residencyGroup }) {
        if (!id || !regionId || !residencyGroup) {
            throw new InfrastructureError("Zone identifiers and residency are required.");
        }
        if (!Number.isInteger(capacity) || capacity < 0 || latencyMs < 0) {
            throw new InfrastructureError("Invalid capacity or latency.");
        }

        this.id = id;
        this.regionId = regionId;
        this.capacity = capacity;
        this.latencyMs = latencyMs;
        this.residencyGroup = residencyGroup;
        this.healthy = true;
        this.allocations = new Map();
    }

    get usedCapacity() {
        return [...this.allocations.values()].reduce((sum, units) => sum + units, 0);
    }

    get freeCapacity() {
        return this.healthy ? this.capacity - this.usedCapacity : 0;
    }

    reserve(workloadId, units) {
        if (!this.healthy) throw new InfrastructureError(`${this.id} is unhealthy.`);
        if (!Number.isInteger(units) || units <= 0) {
            throw new InfrastructureError("Reservation units must be positive integers.");
        }
        if (units > this.freeCapacity) {
            throw new InfrastructureError(`Insufficient capacity in ${this.id}.`);
        }

        this.allocations.set(workloadId, (this.allocations.get(workloadId) || 0) + units);
    }

    release(workloadId) {
        this.allocations.delete(workloadId);
    }
}

class Region {
    constructor({ id, residencyGroup, endpoint }) {
        this.id = id;
        this.residencyGroup = residencyGroup;
        this.endpoint = endpoint;
        this.healthy = true;
        this.zoneIds = new Set();
    }
}

class Workload {
    constructor({
        id,
        requiredUnits,
        minimumZones,
        maximumLatencyMs,
        residencyGroup,
        critical = true
    }) {
        if (!id || !Number.isInteger(requiredUnits) || requiredUnits <= 0) {
            throw new InfrastructureError("Workload ID and positive capacity are required.");
        }
        if (!Number.isInteger(minimumZones) || minimumZones < 1) {
            throw new InfrastructureError("minimumZones must be positive.");
        }

        Object.assign(this, {
            id,
            requiredUnits,
            minimumZones,
            maximumLatencyMs,
            residencyGroup,
            critical
        });
        this.placement = new Map();
    }
}

class GeographicScheduler extends EventEmitter {
    constructor() {
        super();
        this.regions = new Map();
        this.zones = new Map();
        this.processedEvents = new Set();

        this.on("zone-failed", ({ zoneId }) => this.applyZoneFailure(zoneId));
        this.on("zone-recovered", ({ zoneId }) => this.applyZoneRecovery(zoneId));
        this.on("region-failed", ({ regionId }) => this.applyRegionFailure(regionId));
        this.on("region-recovered", ({ regionId }) => this.applyRegionRecovery(regionId));
    }

    addRegion(region) {
        if (this.regions.has(region.id)) {
            throw new InfrastructureError(`Duplicate region: ${region.id}`);
        }
        this.regions.set(region.id, region);
    }

    addZone(zone) {
        if (this.zones.has(zone.id)) {
            throw new InfrastructureError(`Duplicate zone: ${zone.id}`);
        }
        const region = this.regions.get(zone.regionId);
        if (!region || region.residencyGroup !== zone.residencyGroup) {
            throw new InfrastructureError("Zone and region residency configuration conflicts.");
        }
        this.zones.set(zone.id, zone);
        region.zoneIds.add(zone.id);
    }

    eligibleZones(workload, allowedRegionIds) {
        return [...this.zones.values()]
            .filter(zone => {
                const region = this.regions.get(zone.regionId);
                return (
                    allowedRegionIds.includes(zone.regionId) &&
                    region.healthy &&
                    zone.healthy &&
                    zone.residencyGroup === workload.residencyGroup &&
                    zone.latencyMs <= workload.maximumLatencyMs
                );
            })
            .sort((a, b) =>
                a.latencyMs - b.latencyMs ||
                b.freeCapacity - a.freeCapacity ||
                a.id.localeCompare(b.id)
            );
    }

    deploy(workload, allowedRegionIds) {
        if (workload.placement.size > 0) {
            throw new InfrastructureError("Workload is already placed.");
        }

        const candidates = this.eligibleZones(workload, allowedRegionIds);
        if (candidates.length < workload.minimumZones) {
            throw new InfrastructureError("Insufficient eligible independent zones.");
        }

        // Reserve one unit per initial zone, then distribute the remainder.
        // Rollback prevents partial reservations if any allocation fails.
        const planned = new Map();
        let remaining = workload.requiredUnits;

        for (const zone of candidates) {
            if (planned.size < workload.minimumZones && remaining > 0) {
                planned.set(zone.id, 1);
                remaining--;
            }
        }

        for (const zone of candidates) {
            if (remaining === 0) break;
            const current = planned.get(zone.id) || 0;
            const additional = Math.min(remaining, zone.freeCapacity - current);
            if (additional > 0) {
                planned.set(zone.id, current + additional);
                remaining -= additional;
            }
        }

        if (remaining > 0) {
            throw new InfrastructureError("Eligible zones lack sufficient aggregate capacity.");
        }

        const reserved = [];
        try {
            for (const [zoneId, units] of planned) {
                this.zones.get(zoneId).reserve(workload.id, units);
                reserved.push(zoneId);
            }
            workload.placement = planned;
        } catch (error) {
            for (const zoneId of reserved) this.zones.get(zoneId).release(workload.id);
            throw error;
        }

        return new Map(workload.placement);
    }

    applyZoneFailure(zoneId) {
        const zone = this.zones.get(zoneId);
        if (!zone) throw new InfrastructureError(`Unknown zone: ${zoneId}`);
        zone.healthy = false;
    }

    applyZoneRecovery(zoneId) {
        const zone = this.zones.get(zoneId);
        if (!zone) throw new InfrastructureError(`Unknown zone: ${zoneId}`);
        zone.healthy = true;
    }

    applyRegionFailure(regionId) {
        const region = this.regions.get(regionId);
        if (!region) throw new InfrastructureError(`Unknown region: ${regionId}`);
        region.healthy = false;
        for (const zoneId of region.zoneIds) this.zones.get(zoneId).healthy = false;
    }

    applyRegionRecovery(regionId) {
        const region = this.regions.get(regionId);
        if (!region) throw new InfrastructureError(`Unknown region: ${regionId}`);
        region.healthy = true;
        for (const zoneId of region.zoneIds) this.zones.get(zoneId).healthy = true;
    }

    emitOnce(eventId, eventName, payload) {
        if (!eventId) throw new InfrastructureError("Event ID is required.");
        if (this.processedEvents.has(eventId)) return false;

        // Mark only after a successful state update, allowing retries on errors.
        this.emit(eventName, payload);
        this.processedEvents.add(eventId);
        return true;
    }

    healthReport(workload) {
        let survivingUnits = 0;
        let survivingZones = 0;

        for (const [zoneId, units] of workload.placement) {
            if (this.zones.get(zoneId).healthy) {
                survivingUnits += units;
                if (units > 0) survivingZones++;
            }
        }

        return {
            workloadId: workload.id,
            requiredUnits: workload.requiredUnits,
            survivingUnits,
            survivingZones,
            capacityAvailable: survivingUnits >= workload.requiredUnits,
            zoneSpreadAvailable: survivingZones >= workload.minimumZones
        };
    }
}

function assessRecovery({ detectionMinutes, failoverMinutes, replicationLagMinutes, rtoMinutes, rpoMinutes }) {
    for (const value of Object.values(arguments[0])) {
        if (!Number.isFinite(value) || value < 0) {
            throw new InfrastructureError("Recovery measurements must be non-negative numbers.");
        }
    }

    return {
        actualRtoMinutes: detectionMinutes + failoverMinutes,
        actualRpoMinutes: replicationLagMinutes,
        rtoMet: detectionMinutes + failoverMinutes <= rtoMinutes,
        rpoMet: replicationLagMinutes <= rpoMinutes
    };
}

function buildDemo() {
    const scheduler = new GeographicScheduler();

    scheduler.addRegion(new Region({
        id: "india-west",
        residencyGroup: "india",
        endpoint: "payments.example.in"
    }));
    scheduler.addRegion(new Region({
        id: "india-south",
        residencyGroup: "india",
        endpoint: "payments-dr.example.in"
    }));
    scheduler.addRegion(new Region({
        id: "singapore",
        residencyGroup: "apac",
        endpoint: "payments-apac.example.net"
    }));

    for (const zone of [
        { id: "west-a", regionId: "india-west", capacity: 8, latencyMs: 10, residencyGroup: "india" },
        { id: "west-b", regionId: "india-west", capacity: 8, latencyMs: 13, residencyGroup: "india" },
        { id: "west-c", regionId: "india-west", capacity: 8, latencyMs: 16, residencyGroup: "india" },
        { id: "south-a", regionId: "india-south", capacity: 10, latencyMs: 22, residencyGroup: "india" },
        { id: "south-b", regionId: "india-south", capacity: 10, latencyMs: 25, residencyGroup: "india" },
        { id: "south-c", regionId: "india-south", capacity: 10, latencyMs: 27, residencyGroup: "india" },
        { id: "sg-a", regionId: "singapore", capacity: 12, latencyMs: 55, residencyGroup: "apac" }
    ]) {
        scheduler.addZone(new Zone(zone));
    }

    return scheduler;
}

function main() {
    const scheduler = buildDemo();

    const paymentService = new Workload({
        id: "payment-api",
        requiredUnits: 9,
        minimumZones: 3,
        maximumLatencyMs: 30,
        residencyGroup: "india"
    });

    scheduler.deploy(paymentService, ["india-west"]);

    console.log("Initial placement:", Object.fromEntries(paymentService.placement));
    console.log("Healthy state:", scheduler.healthReport(paymentService));

    scheduler.emitOnce("evt-001", "zone-failed", { zoneId: "west-b" });
    console.log("After zone failure:", scheduler.healthReport(paymentService));

    // A duplicate delivery does not apply a second state transition.
    console.log(
        "Duplicate failure event accepted:",
        scheduler.emitOnce("evt-001", "zone-failed", { zoneId: "west-b" })
    );

    scheduler.emitOnce("evt-002", "zone-recovered", { zoneId: "west-b" });
    scheduler.emitOnce("evt-003", "region-failed", { regionId: "india-west" });
    console.log("After regional failure:", scheduler.healthReport(paymentService));

    scheduler.emitOnce("evt-004", "region-recovered", { regionId: "india-west" });

    const recovery = assessRecovery({
        detectionMinutes: 3,
        failoverMinutes: 8,
        replicationLagMinutes: 2,
        rtoMinutes: 15,
        rpoMinutes: 5
    });
    console.log("Recovery objectives:", recovery);

    assert.equal(scheduler.healthReport(paymentService).survivingUnits, 9);
    assert.equal(recovery.rtoMet, true);
    assert.equal(recovery.rpoMet, true);

    const restricted = new Workload({
        id: "restricted-ledger",
        requiredUnits: 4,
        minimumZones: 2,
        maximumLatencyMs: 20,
        residencyGroup: "india"
    });

    try {
        scheduler.deploy(restricted, ["singapore"]);
    } catch (error) {
        console.log("Residency or latency policy rejected placement:", error.message);
    }

    console.log("Simulation checks passed.");
}

if (require.main === module) {
    main();
}

module.exports = {
    Zone,
    Region,
    Workload,
    GeographicScheduler,
    assessRecovery
};
