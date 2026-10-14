'use strict';

/*
 * Serverless computing model:
 * - Functions execute in response to requests or events.
 * - Event producers are decoupled from consumers.
 * - Execution can scale horizontally according to workload.
 * - Functions should be short-lived, stateless, observable, and idempotent
 *   when duplicate event delivery is possible.
 */

const crypto = require('node:crypto');

const EventType = Object.freeze({
    HTTP_REQUEST: 'http.request',
    FILE_UPLOADED: 'storage.file_uploaded',
    ORDER_CREATED: 'commerce.order_created',
    TIMER: 'scheduler.timer'
});

function createEvent(type, payload) {
    if (!Object.values(EventType).includes(type)) {
        throw new Error(`Unsupported event type: ${type}`);
    }

    return Object.freeze({
        id: crypto.randomUUID(),
        type,
        payload: structuredClone(payload),
        createdAt: new Date().toISOString()
    });
}

class ServerlessFunction {
    constructor(name, handler, options = {}) {
        if (typeof handler !== 'function') {
            throw new TypeError('handler must be a function');
        }

        this.name = name;
        this.handler = handler;
        this.timeoutMs = options.timeoutMs ?? 3000;
        this.memoryMb = options.memoryMb ?? 256;
        this.invocations = 0;
        this.failures = 0;
        this.totalDurationMs = 0;
        this.warm = false;
    }

    async invoke(event) {
        const started = performance.now();
        this.invocations++;

        let coldStart = false;

        try {
            if (!this.warm) {
                coldStart = true;
                // A real platform initializes a runtime environment here.
                await delay(30);
                this.warm = true;
            }

            const result = await withTimeout(
                this.handler(event),
                this.timeoutMs
            );

            return {
                function: this.name,
                eventId: event.id,
                coldStart,
                result
            };
        } catch (error) {
            this.failures++;
            throw new Error(
                `${this.name} failed: ${error.message}`
            );
        } finally {
            this.totalDurationMs += performance.now() - started;
        }
    }

    metrics() {
        return {
            name: this.name,
            invocations: this.invocations,
            failures: this.failures,
            averageDurationMs:
                this.invocations === 0
                    ? 0
                    : this.totalDurationMs / this.invocations,
            memoryMb: this.memoryMb,
            timeoutMs: this.timeoutMs
        };
    }
}

class EventBus {
    constructor() {
        this.subscribers = new Map();
    }

    subscribe(type, serverlessFunction) {
        if (!this.subscribers.has(type)) {
            this.subscribers.set(type, []);
        }

        this.subscribers.get(type).push(serverlessFunction);
    }

    async publish(event) {
        const functions = this.subscribers.get(event.type) ?? [];

        return Promise.allSettled(
            functions.map(fn => fn.invoke(event))
        );
    }
}

class IdempotencyStore {
    constructor() {
        this.results = new Map();
    }

    has(eventId) {
        return this.results.has(eventId);
    }

    get(eventId) {
        return this.results.get(eventId);
    }

    set(eventId, result) {
        this.results.set(eventId, result);
    }
}

class RetryPolicy {
    constructor({ attempts = 3, baseDelayMs = 50 } = {}) {
        this.attempts = attempts;
        this.baseDelayMs = baseDelayMs;
    }

    async execute(operation) {
        let lastError;

        for (let attempt = 0; attempt < this.attempts; attempt++) {
            try {
                return await operation();
            } catch (error) {
                lastError = error;

                if (attempt === this.attempts - 1) {
                    break;
                }

                await delay(this.baseDelayMs * 2 ** attempt);
            }
        }

        throw lastError;
    }
}

class AutoScaler {
    constructor({
        minInstances = 0,
        maxInstances = 10,
        targetConcurrency = 4
    } = {}) {
        if (minInstances < 0 || maxInstances < minInstances) {
            throw new RangeError('Invalid instance limits');
        }

        this.minInstances = minInstances;
        this.maxInstances = maxInstances;
        this.targetConcurrency = targetConcurrency;
    }

    desiredInstances(queueDepth) {
        if (queueDepth <= 0) {
            return this.minInstances;
        }

        const desired = Math.ceil(
            queueDepth / this.targetConcurrency
        );

        return Math.min(
            this.maxInstances,
            Math.max(this.minInstances, desired)
        );
    }
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function withTimeout(promise, timeoutMs) {
    return Promise.race([
        promise,
        new Promise((_, reject) => {
            setTimeout(() => {
                reject(new Error(
                    `Function exceeded ${timeoutMs} ms timeout`
                ));
            }, timeoutMs);
        })
    ]);
}

async function validateHttpRequest(event) {
    const { method, path } = event.payload;

    if (!['GET', 'POST', 'PUT', 'DELETE'].includes(method)) {
        throw new Error('Unsupported HTTP method');
    }

    if (typeof path !== 'string' || !path.startsWith('/')) {
        throw new Error('Invalid request path');
    }

    return {
        statusCode: 200,
        method,
        path,
        body: { message: 'Request accepted' }
    };
}

async function processFileUpload(event) {
    const { filename, sizeBytes } = event.payload;

    if (!filename) {
        throw new Error('filename is required');
    }

    if (!Number.isSafeInteger(sizeBytes) || sizeBytes < 0) {
        throw new Error('sizeBytes must be a non-negative safe integer');
    }

    return {
        filename,
        sizeBytes,
        category:
            sizeBytes > 10_000_000
                ? 'large-file'
                : 'normal-file'
    };
}

async function processOrder(event) {
    const { customerId, amount } = event.payload;

    if (!customerId) {
        throw new Error('customerId is required');
    }

    if (!Number.isFinite(amount) || amount <= 0) {
        throw new Error('amount must be positive');
    }

    await delay(10);

    return {
        orderId: `order-${crypto.randomUUID()}`,
        customerId,
        amount,
        status: 'accepted'
    };
}

async function unreliableInventoryService(event) {
    // This simulates a transient downstream dependency.
    if (Math.random() < 0.4) {
        throw new Error('Inventory service unavailable');
    }

    return {
        sku: event.payload.sku,
        available: true
    };
}

async function main() {
    console.log('\n=== HTTP-triggered function ===');

    const httpFunction = new ServerlessFunction(
        'http-validator',
        validateHttpRequest,
        { timeoutMs: 1000, memoryMb: 256 }
    );

    const httpEvent = createEvent(
        EventType.HTTP_REQUEST,
        {
            method: 'GET',
            path: '/api/orders'
        }
    );

    console.log(
        await httpFunction.invoke(httpEvent)
    );

    console.log('\n=== Event-driven fan-out ===');

    const orderFunction = new ServerlessFunction(
        'order-processor',
        processOrder
    );

    const inventoryFunction = new ServerlessFunction(
        'inventory-check',
        unreliableInventoryService
    );

    const bus = new EventBus();

    bus.subscribe(EventType.ORDER_CREATED, orderFunction);
    bus.subscribe(EventType.ORDER_CREATED, inventoryFunction);

    const orderEvent = createEvent(
        EventType.ORDER_CREATED,
        {
            customerId: 'customer-42',
            amount: 1499.50,
            sku: 'LAPTOP-001'
        }
    );

    const results = await bus.publish(orderEvent);

    for (const result of results) {
        console.log(result);
    }

    console.log('\n=== Retry with exponential backoff ===');

    const retry = new RetryPolicy({
        attempts: 4,
        baseDelayMs: 25
    });

    try {
        const inventoryResult = await retry.execute(
            () => inventoryFunction.invoke(orderEvent)
        );

        console.log(inventoryResult);
    } catch (error) {
        console.error(error.message);
    }

    console.log('\n=== Idempotent processing ===');

    const store = new IdempotencyStore();

    const processExactlyOnceAtApplicationLevel = async event => {
        if (store.has(event.id)) {
            return {
                duplicate: true,
                cached: store.get(event.id)
            };
        }

        const result = await orderFunction.invoke(event);
        store.set(event.id, result);

        return {
            duplicate: false,
            result
        };
    };

    console.log(
        await processExactlyOnceAtApplicationLevel(orderEvent)
    );

    console.log(
        await processExactlyOnceAtApplicationLevel(orderEvent)
    );

    console.log('\n=== Auto-scaling model ===');

    const scaler = new AutoScaler({
        minInstances: 0,
        maxInstances: 8,
        targetConcurrency: 4
    });

    for (const queueDepth of [0, 1, 4, 5, 12, 25, 100]) {
        console.log({
            queueDepth,
            desiredInstances:
                scaler.desiredInstances(queueDepth)
        });
    }

    console.log('\n=== Object-storage event ===');

    const fileFunction = new ServerlessFunction(
        'file-processor',
        processFileUpload
    );

    const fileEvent = createEvent(
        EventType.FILE_UPLOADED,
        {
            filename: 'inspection-report.pdf',
            sizeBytes: 1_500_000
        }
    );

    console.log(
        await fileFunction.invoke(fileEvent)
    );

    console.log('\n=== Observability ===');

    console.table([
        httpFunction.metrics(),
        orderFunction.metrics(),
        inventoryFunction.metrics(),
        fileFunction.metrics()
    ]);
}

main().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
