'use strict';

/*
 * Cloud Storage Fundamentals
 *
 * This file uses JavaScript's event-driven model to represent object
 * replication, asynchronous health checks, failure events, and policy
 * evaluation. It deliberately models availability separately from durability.
 */

const crypto = require('crypto');
const { EventEmitter } = require('events');

const StorageClass = Object.freeze({
    STANDARD: 'standard',
    INFREQUENT_ACCESS: 'infrequent-access',
    ARCHIVE: 'archive'
});

class StorageError extends Error {}

class ValidationError extends StorageError {}

class ObjectNotFoundError extends StorageError {}

class StorageObject {
    constructor(key, content, storageClass = StorageClass.STANDARD) {
        if (typeof key !== 'string' || key.trim().length === 0) {
            throw new ValidationError('Object key cannot be empty.');
        }

        if (!Buffer.isBuffer(content)) {
            throw new ValidationError('Object content must be a Buffer.');
        }

        this.key = key;
        this.sizeBytes = content.length;
        this.contentHash = crypto
            .createHash('sha256')
            .update(content)
            .digest('hex');
        this.storageClass = storageClass;
        this.createdAt = new Date();
    }
}

class Replica {
    constructor(region) {
        this.region = region;
        this.healthy = true;
        this.lastHealthCheck = null;
    }
}

class ObjectStore extends EventEmitter {
    constructor({ name, regions, replicationFactor }) {
        super();

        if (!name || !name.trim()) {
            throw new ValidationError('Storage name is required.');
        }

        if (!Array.isArray(regions) || regions.length === 0) {
            throw new ValidationError('At least one storage region is required.');
        }

        if (
            !Number.isInteger(replicationFactor) ||
            replicationFactor < 1 ||
            replicationFactor > regions.length
        ) {
            throw new ValidationError(
                'Replication factor must be between one and the region count.'
            );
        }

        this.name = name;
        this.regions = [...new Set(regions)];
        this.replicationFactor = replicationFactor;
        this.objects = new Map();
    }

    put(key, content, storageClass = StorageClass.STANDARD) {
        const object = new StorageObject(key, content, storageClass);

        const replicas = this.regions
            .slice(0, this.replicationFactor)
            .map(region => new Replica(region));

        this.objects.set(key, {
            object,
            replicas
        });

        this.emit('objectStored', {
            key,
            replicaRegions: replicas.map(replica => replica.region)
        });

        return object;
    }

    get(key) {
        const entry = this.objects.get(key);

        if (!entry) {
            throw new ObjectNotFoundError(`Object '${key}' was not found.`);
        }

        const available = entry.replicas.some(replica => replica.healthy);

        if (!available) {
            throw new StorageError(
                `Object '${key}' is currently unavailable.`
            );
        }

        this.emit('objectRead', {
            key,
            servedBy: entry.replicas.find(replica => replica.healthy).region
        });

        return entry.object;
    }

    failRegion(region) {
        if (!this.regions.includes(region)) {
            throw new ValidationError(`Unknown region: ${region}`);
        }

        for (const entry of this.objects.values()) {
            for (const replica of entry.replicas) {
                if (replica.region === region) {
                    replica.healthy = false;
                }
            }
        }

        this.emit('regionFailure', { region });
    }

    recoverRegion(region) {
        if (!this.regions.includes(region)) {
            throw new ValidationError(`Unknown region: ${region}`);
        }

        for (const entry of this.objects.values()) {
            for (const replica of entry.replicas) {
                if (replica.region === region) {
                    replica.healthy = true;
                }
            }
        }

        this.emit('regionRecovered', { region });
    }

    async healthCheck(key) {
        await new Promise(resolve => setTimeout(resolve, 25));

        const entry = this.objects.get(key);

        if (!entry) {
            throw new ObjectNotFoundError(`Object '${key}' was not found.`);
        }

        const checkedAt = new Date();

        for (const replica of entry.replicas) {
            replica.lastHealthCheck = checkedAt;
        }

        const healthyReplicas = entry.replicas.filter(
            replica => replica.healthy
        );

        return {
            key,
            healthyReplicaCount: healthyReplicas.length,
            configuredReplicaCount: entry.replicas.length,
            regions: healthyReplicas.map(replica => replica.region),
            availability:
                healthyReplicas.length === 0
                    ? 'UNAVAILABLE'
                    : healthyReplicas.length < entry.replicas.length
                        ? 'DEGRADED'
                        : 'AVAILABLE'
        };
    }
}

class StorageGovernancePolicy {
    constructor({
        minimumReplicationFactor,
        requireMultiRegion
    }) {
        this.minimumReplicationFactor = minimumReplicationFactor;
        this.requireMultiRegion = requireMultiRegion;
    }

    evaluate(store) {
        const reasons = [];

        if (store.replicationFactor < this.minimumReplicationFactor) {
            reasons.push(
                `Replication factor ${store.replicationFactor} is below ` +
                `the required ${this.minimumReplicationFactor}.`
            );
        }

        if (
            this.requireMultiRegion &&
            store.regions.length < 2
        ) {
            reasons.push('Multi-region placement is required.');
        }

        return {
            compliant: reasons.length === 0,
            reasons
        };
    }
}

function availabilityFromIndependentReplicas(
    replicaAvailability,
    replicaCount
) {
    if (
        replicaAvailability < 0 ||
        replicaAvailability > 1 ||
        !Number.isInteger(replicaCount) ||
        replicaCount < 1
    ) {
        throw new RangeError('Invalid availability parameters.');
    }

    return 1 - Math.pow(1 - replicaAvailability, replicaCount);
}

function estimatedIndependentLossProbability(
    annualFailureProbability,
    replicaCount
) {
    if (
        annualFailureProbability < 0 ||
        annualFailureProbability > 1 ||
        !Number.isInteger(replicaCount) ||
        replicaCount < 1
    ) {
        throw new RangeError('Invalid durability parameters.');
    }

    return Math.pow(annualFailureProbability, replicaCount);
}

async function main() {
    const store = new ObjectStore({
        name: 'production-assets',
        regions: ['Mumbai', 'Singapore', 'Frankfurt'],
        replicationFactor: 3
    });

    store.on('objectStored', event => {
        console.log(
            `Stored ${event.key} in ${event.replicaRegions.join(', ')}`
        );
    });

    store.on('regionFailure', event => {
        console.log(`Region failure event: ${event.region}`);
    });

    store.on('regionRecovered', event => {
        console.log(`Region recovery event: ${event.region}`);
    });

    store.put(
        'reports/quarterly.pdf',
        Buffer.from('Quarterly operational report'),
        StorageClass.STANDARD
    );

    console.log(await store.healthCheck('reports/quarterly.pdf'));

    store.failRegion('Mumbai');
    console.log(await store.healthCheck('reports/quarterly.pdf'));

    const policy = new StorageGovernancePolicy({
        minimumReplicationFactor: 3,
        requireMultiRegion: true
    });

    console.log('Governance:', policy.evaluate(store));

    store.recoverRegion('Mumbai');
    console.log(await store.healthCheck('reports/quarterly.pdf'));

    try {
        store.get('reports/missing.pdf');
    } catch (error) {
        console.log('Expected read failure:', error.message);
    }

    const availability = availabilityFromIndependentReplicas(0.999, 3);
    const lossProbability = estimatedIndependentLossProbability(0.001, 3);

    console.log(
        `Independent-replica availability: ${availability.toFixed(8)}`
    );
    console.log(
        `Estimated annual simultaneous loss probability: ` +
        `${lossProbability.toExponential(4)}`
    );

    console.log(
        'Replication improves resilience only when replicas are placed and ' +
        'operated with meaningful failure independence.'
    );
}

main().catch(error => {
    console.error('Fatal storage simulation error:', error.message);
    process.exitCode = 1;
});
