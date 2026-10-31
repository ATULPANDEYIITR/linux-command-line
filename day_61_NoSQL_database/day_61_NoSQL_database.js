'use strict';

/*
 * NoSQL architecture laboratory:
 * - Key-value: session and cache state
 * - Document: flexible product records
 * - Wide-column: sparse time-series telemetry
 * - Graph: dependency traversal
 *
 * The implementation uses Node.js standard-library features only.
 */

const { EventEmitter } = require('node:events');

class ValidationError extends Error {}
class NotFoundError extends Error {}

class KeyValueStore extends EventEmitter {
    constructor() {
        super();
        this.data = new Map();
        this.expirations = new Map();
    }

    set(key, value, ttlMs = null) {
        if (typeof key !== 'string' || key.length === 0 || key.length > 256) {
            throw new ValidationError('Key must contain 1-256 characters');
        }
        if (ttlMs !== null && (!Number.isInteger(ttlMs) || ttlMs <= 0)) {
            throw new ValidationError('TTL must be a positive integer');
        }

        this.data.set(key, structuredClone(value));

        if (ttlMs === null) {
            this.expirations.delete(key);
        } else {
            this.expirations.set(key, Date.now() + ttlMs);
        }

        this.emit('changed', { type: 'set', key });
    }

    get(key) {
        if (!this.data.has(key)) {
            throw new NotFoundError(`Key ${key} does not exist`);
        }

        const expiration = this.expirations.get(key);
        if (expiration !== undefined && Date.now() >= expiration) {
            this.delete(key);
            throw new NotFoundError(`Key ${key} has expired`);
        }

        return structuredClone(this.data.get(key));
    }

    delete(key) {
        const existed = this.data.delete(key);
        this.expirations.delete(key);
        if (existed) {
            this.emit('changed', { type: 'delete', key });
        }
    }
}

class DocumentCollection {
    constructor() {
        this.documents = new Map();
    }

    insert(document) {
        if (
            document === null ||
            typeof document !== 'object' ||
            typeof document.id !== 'string' ||
            document.id.length === 0
        ) {
            throw new ValidationError('Document requires a non-empty string id');
        }

        if (this.documents.has(document.id)) {
            throw new ValidationError(`Duplicate document: ${document.id}`);
        }

        this.documents.set(document.id, structuredClone(document));
    }

    find(predicate) {
        return [...this.documents.values()]
            .filter(predicate)
            .map((document) => structuredClone(document));
    }

    update(id, patch) {
        const current = this.documents.get(id);
        if (!current) {
            throw new NotFoundError(`Document ${id} does not exist`);
        }

        this.documents.set(id, {
            ...current,
            ...structuredClone(patch),
        });
    }
}

class WideColumnTable {
    constructor() {
        this.rows = new Map();
    }

    put(rowKey, family, columns) {
        if (!rowKey || !family || Object.keys(columns).length === 0) {
            throw new ValidationError('Row key, family, and columns are required');
        }

        if (!this.rows.has(rowKey)) {
            this.rows.set(rowKey, new Map());
        }

        const families = this.rows.get(rowKey);
        const current = families.get(family) || {};

        families.set(family, {
            ...current,
            ...structuredClone(columns),
        });
    }

    scanFamily(family) {
        const result = [];

        for (const [rowKey, families] of this.rows) {
            if (families.has(family)) {
                result.push({
                    rowKey,
                    columns: structuredClone(families.get(family)),
                });
            }
        }

        return result;
    }
}

class Graph {
    constructor() {
        this.nodes = new Map();
        this.edges = new Map();
    }

    addNode(id, attributes = {}) {
        if (!id) {
            throw new ValidationError('Graph node id cannot be empty');
        }
        if (this.nodes.has(id)) {
            throw new ValidationError(`Duplicate node: ${id}`);
        }

        this.nodes.set(id, structuredClone(attributes));
        this.edges.set(id, []);
    }

    addEdge(source, relation, target) {
        if (!this.nodes.has(source) || !this.nodes.has(target)) {
            throw new NotFoundError('Both graph endpoints must exist');
        }

        this.edges.get(source).push({ relation, target });
    }

    shortestPath(start, target) {
        if (!this.nodes.has(start) || !this.nodes.has(target)) {
            throw new NotFoundError('Graph endpoint does not exist');
        }

        const queue = [{ node: start, path: [start] }];
        const visited = new Set([start]);

        while (queue.length > 0) {
            const { node, path } = queue.shift();

            if (node === target) {
                return path;
            }

            for (const edge of this.edges.get(node)) {
                if (!visited.has(edge.target)) {
                    visited.add(edge.target);
                    queue.push({
                        node: edge.target,
                        path: [...path, edge.target],
                    });
                }
            }
        }

        return null;
    }
}

function selectArchitecture(workload) {
    if (workload.relationshipTraversal) {
        return 'graph';
    }
    if (workload.flexibleDocuments) {
        return 'document';
    }
    if (workload.highVolumePartitionedRows) {
        return 'wide-column';
    }
    if (['session', 'cache', 'counter', 'token'].includes(workload.accessPattern)) {
        return 'key-value';
    }
    throw new ValidationError(`No architecture selected for ${workload.name}`);
}

async function publishTelemetry(table, events) {
    // Async iteration models an ingestion stream without external services.
    for await (const event of events) {
        table.put(event.device, 'telemetry', {
            [event.timestamp]: event.value,
        });
        await new Promise((resolve) => setImmediate(resolve));
    }
}

async function* telemetryEvents() {
    yield {
        device: 'device-001',
        timestamp: '2026-10-31T12:00:00Z',
        value: 44.1,
    };
    yield {
        device: 'device-002',
        timestamp: '2026-10-31T12:00:00Z',
        value: 38.5,
    };
}

async function main() {
    const cache = new KeyValueStore();
    const products = new DocumentCollection();
    const telemetry = new WideColumnTable();
    const dependencies = new Graph();

    cache.on('changed', (event) => {
        console.log(`Key-value event: ${event.type} ${event.key}`);
    });

    cache.set(
        'session:user-1001',
        { userId: 'user-1001', role: 'analyst' },
        60_000
    );

    products.insert({
        id: 'p100',
        name: 'Edge Gateway',
        category: 'networking',
        price: 149.50,
        tags: ['iot', 'gateway'],
        attributes: { region: 'asia-south', active: true },
    });

    products.insert({
        id: 'p200',
        name: 'Graph Sensor',
        category: 'telemetry',
        price: 89.00,
        tags: ['sensor', 'graph'],
        attributes: { region: 'asia-south', active: true },
    });

    products.update('p100', {
        attributes: {
            region: 'asia-south',
            active: true,
            firmwareVersion: '2.1',
        },
    });

    await publishTelemetry(telemetry, telemetryEvents());

    for (const [id, type] of [
        ['api', 'service'],
        ['orders', 'service'],
        ['inventory', 'service'],
        ['payments', 'service'],
        ['inventory-db', 'database'],
    ]) {
        dependencies.addNode(id, { type });
    }

    dependencies.addEdge('api', 'calls', 'orders');
    dependencies.addEdge('orders', 'calls', 'inventory');
    dependencies.addEdge('orders', 'calls', 'payments');
    dependencies.addEdge('inventory', 'reads', 'inventory-db');

    const workloads = [
        {
            name: 'Session state',
            accessPattern: 'session',
        },
        {
            name: 'Product catalog',
            flexibleDocuments: true,
        },
        {
            name: 'Telemetry',
            highVolumePartitionedRows: true,
        },
        {
            name: 'Service dependency analysis',
            relationshipTraversal: true,
        },
    ];

    console.log('\nArchitecture selection');
    for (const workload of workloads) {
        console.log(`${workload.name}: ${selectArchitecture(workload)}`);
    }

    console.log('\nKey-value');
    console.log(cache.get('session:user-1001'));

    console.log('\nDocument');
    console.log(
        products.find(
            (product) =>
                product.price >= 100 &&
                product.attributes.active === true
        )
    );

    console.log('\nWide-column');
    console.log(telemetry.scanFamily('telemetry'));

    console.log('\nGraph');
    console.log(
        'Dependency path:',
        dependencies.shortestPath('api', 'inventory-db')
    );

    try {
        products.insert({ id: 'p100', name: 'Duplicate' });
    } catch (error) {
        if (!(error instanceof ValidationError)) {
            throw error;
        }
        console.log('\nValidation rejected duplicate document.');
    }

    try {
        cache.get('missing-key');
    } catch (error) {
        if (!(error instanceof NotFoundError)) {
            throw error;
        }
        console.log('Validation rejected missing key access.');
    }
}

main().catch((error) => {
    console.error('Application failure:', error.message);
    process.exitCode = 1;
});
