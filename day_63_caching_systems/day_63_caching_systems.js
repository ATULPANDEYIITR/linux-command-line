'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs/promises');

class CacheError extends Error {}
class ValidationError extends CacheError {}
class CacheMiss extends CacheError {}

const CacheEvent = Object.freeze({
    HIT: 'hit',
    MISS: 'miss',
    SET: 'set',
    EVICT: 'evict',
    INVALIDATE: 'invalidate',
    STALE: 'stale'
});

class EventBus {
    constructor() {
        this.listeners = new Map();
    }

    on(event, listener) {
        if (typeof listener !== 'function') {
            throw new ValidationError('listener must be a function');
        }

        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }

        this.listeners.get(event).add(listener);

        return () => this.listeners.get(event)?.delete(listener);
    }

    emit(event, payload) {
        const listeners = this.listeners.get(event) ?? new Set();

        for (const listener of listeners) {
            try {
                listener(payload);
            } catch (error) {
                console.error(`cache event listener failed: ${error.message}`);
            }
        }
    }
}

class LruCache {
    constructor({ capacity = 100, ttlMs = 60_000, events = null } = {}) {
        if (!Number.isInteger(capacity) || capacity <= 0) {
            throw new ValidationError('capacity must be a positive integer');
        }

        if (ttlMs !== null && (!Number.isFinite(ttlMs) || ttlMs <= 0)) {
            throw new ValidationError('ttlMs must be positive or null');
        }

        this.capacity = capacity;
        this.ttlMs = ttlMs;
        this.entries = new Map();
        this.stats = {
            hits: 0,
            misses: 0,
            stale: 0,
            writes: 0,
            evictions: 0,
            invalidations: 0
        };
        this.events = events;
    }

    _expired(entry) {
        return entry.expiresAt !== null && Date.now() >= entry.expiresAt;
    }

    get(key) {
        if (typeof key !== 'string' || key.length === 0) {
            throw new ValidationError('cache key must be a non-empty string');
        }

        const entry = this.entries.get(key);

        if (!entry) {
            this.stats.misses++;
            this.events?.emit(CacheEvent.MISS, { key });
            return { status: CacheEvent.MISS, value: undefined };
        }

        if (this._expired(entry)) {
            this.entries.delete(key);
            this.stats.stale++;
            this.events?.emit(CacheEvent.STALE, { key });
            return { status: CacheEvent.STALE, value: undefined };
        }

        this.entries.delete(key);
        this.entries.set(key, entry);
        this.stats.hits++;
        this.events?.emit(CacheEvent.HIT, { key });
        return { status: CacheEvent.HIT, value: structuredClone(entry.value) };
    }

    set(key, value, { ttlMs = this.ttlMs, version = 1, tags = [] } = {}) {
        if (typeof key !== 'string' || key.length === 0) {
            throw new ValidationError('cache key must be a non-empty string');
        }

        if (ttlMs !== null && (!Number.isFinite(ttlMs) || ttlMs <= 0)) {
            throw new ValidationError('ttlMs must be positive or null');
        }

        if (!Number.isInteger(version) || version <= 0) {
            throw new ValidationError('version must be positive');
        }

        const tagSet = new Set(tags);

        const entry = {
            value: structuredClone(value),
            version,
            tags: tagSet,
            createdAt: Date.now(),
            expiresAt: ttlMs === null ? null : Date.now() + ttlMs
        };

        this.entries.delete(key);
        this.entries.set(key, entry);
        this.stats.writes++;

        while (this.entries.size > this.capacity) {
            const oldestKey = this.entries.keys().next().value;
            this.entries.delete(oldestKey);
            this.stats.evictions++;
            this.events?.emit(CacheEvent.EVICT, { key: oldestKey });
        }

        this.events?.emit(CacheEvent.SET, { key, version });
    }

    delete(key) {
        const deleted = this.entries.delete(key);

        if (deleted) {
            this.stats.invalidations++;
            this.events?.emit(CacheEvent.INVALIDATE, { key });
        }

        return deleted;
    }

    invalidateTag(tag) {
        let count = 0;

        for (const [key, entry] of this.entries) {
            if (entry.tags.has(tag)) {
                this.entries.delete(key);
                count++;
            }
        }

        this.stats.invalidations += count;
        return count;
    }

    snapshot() {
        const requests =
            this.stats.hits + this.stats.misses + this.stats.stale;

        return {
            size: this.entries.size,
            capacity: this.capacity,
            requests,
            hitRate: requests === 0 ? 0 : this.stats.hits / requests,
            ...this.stats
        };
    }
}

class ProductStore {
    constructor() {
        this.products = new Map([
            [101, { id: 101, name: 'Edge Router', price: 249.99, stock: 18, version: 1 }],
            [102, { id: 102, name: 'Secure Gateway', price: 499.00, stock: 7, version: 1 }],
            [103, { id: 103, name: 'Telemetry Node', price: 129.50, stock: 31, version: 1 }]
        ]);
    }

    async find(id) {
        const product = this.products.get(id);

        if (!product) {
            throw new CacheMiss(`product ${id} does not exist`);
        }

        return structuredClone(product);
    }

    async updatePrice(id, price) {
        if (!Number.isFinite(price) || price < 0) {
            throw new ValidationError('price must be non-negative');
        }

        const product = await this.find(id);
        product.price = price;
        product.version++;
        this.products.set(id, product);
        return structuredClone(product);
    }

    async purchase(id, quantity) {
        if (!Number.isInteger(quantity) || quantity <= 0) {
            throw new ValidationError('quantity must be a positive integer');
        }

        const product = await this.find(id);

        if (product.stock < quantity) {
            throw new ValidationError('insufficient stock');
        }

        product.stock -= quantity;
        product.version++;
        this.products.set(id, product);
        return structuredClone(product);
    }
}

class CacheAsideService {
    constructor(store, cache) {
        this.store = store;
        this.cache = cache;
    }

    key(id) {
        return `product:${id}`;
    }

    async get(id) {
        const key = this.key(id);
        const result = this.cache.get(key);

        if (result.status === CacheEvent.HIT) {
            return result.value;
        }

        const product = await this.store.find(id);

        this.cache.set(key, product, {
            ttlMs: 30_000,
            version: product.version,
            tags: ['product', `product:${id}`]
        });

        return product;
    }

    async updatePrice(id, price) {
        const product = await this.store.updatePrice(id, price);

        // Authoritative state is changed before invalidation.
        this.cache.delete(this.key(id));

        return product;
    }

    async purchase(id, quantity) {
        const product = await this.store.purchase(id, quantity);
        this.cache.delete(this.key(id));
        return product;
    }
}

class StaleWhileRevalidate {
    constructor({ staleMs = 5_000 } = {}) {
        this.staleMs = staleMs;
        this.entries = new Map();
        this.refreshes = new Map();
    }

    async get(key, loader) {
        const entry = this.entries.get(key);
        const now = Date.now();

        if (!entry) {
            const value = await loader();
            this.set(key, value, 30_000);
            return { value, stale: false };
        }

        if (now < entry.freshUntil) {
            return { value: structuredClone(entry.value), stale: false };
        }

        if (now < entry.staleUntil) {
            if (!this.refreshes.has(key)) {
                const refresh = Promise.resolve()
                    .then(loader)
                    .then(value => {
                        this.set(key, value, 30_000);
                        return value;
                    })
                    .finally(() => this.refreshes.delete(key));

                this.refreshes.set(key, refresh);
            }

            return { value: structuredClone(entry.value), stale: true };
        }

        this.entries.delete(key);
        const value = await loader();
        this.set(key, value, 30_000);
        return { value, stale: false };
    }

    set(key, value, ttlMs) {
        const freshUntil = Date.now() + ttlMs;

        this.entries.set(key, {
            value: structuredClone(value),
            freshUntil,
            staleUntil: freshUntil + this.staleMs
        });
    }
}

function secureKey(namespace, identifier) {
    if (!namespace || !identifier) {
        throw new ValidationError('namespace and identifier are required');
    }

    const digest = crypto
        .createHash('sha256')
        .update(identifier, 'utf8')
        .digest('hex');

    return `${namespace}:${digest}`;
}

async function main() {
    const events = new EventBus();

    events.on(CacheEvent.HIT, ({ key }) => {
        console.log(`HIT ${key}`);
    });

    events.on(CacheEvent.MISS, ({ key }) => {
        console.log(`MISS ${key}`);
    });

    events.on(CacheEvent.EVICT, ({ key }) => {
        console.log(`EVICT ${key}`);
    });

    const cache = new LruCache({
        capacity: 2,
        ttlMs: 60_000,
        events
    });

    cache.set('configuration', { region: 'IN', revision: 4 });
    cache.set('feature-flags', { checkoutV2: true });

    console.log(cache.get('configuration'));
    cache.set('session', { userId: 41 });
    console.log('eviction snapshot:', cache.snapshot());

    const store = new ProductStore();
    const service = new CacheAsideService(store, cache);

    console.log('\nProduct reads');
    console.log(await service.get(101));
    console.log(await service.get(101));

    console.log('\nMutation and invalidation');
    await service.updatePrice(101, 279.99);
    console.log(await service.get(101));

    try {
        await service.purchase(102, 100);
    } catch (error) {
        console.log(`expected failure: ${error.message}`);
    }

    console.log('\nStale-while-revalidate');
    const swr = new StaleWhileRevalidate({ staleMs: 1_000 });
    let loaderCalls = 0;

    const loader = async () => {
        loaderCalls++;
        return { configurationVersion: loaderCalls };
    };

    swr.set('application-config', { configurationVersion: 0 }, 10);
    await new Promise(resolve => setTimeout(resolve, 15));

    console.log(await swr.get('application-config', loader));
    console.log('refresh calls:', loaderCalls);

    console.log('\nSafe key');
    console.log(secureKey('customer', 'customer/123?region=IN'));

    const report = {
        cache: cache.snapshot(),
        secureKey: secureKey('diagnostic', '2026-11-02'),
        timestamp: new Date().toISOString()
    };

    const filePath = 'cache-report.json';
    await fs.writeFile(filePath, JSON.stringify(report, null, 2), {
        encoding: 'utf8',
        mode: 0o600
    });

    console.log(`diagnostic report written to ${filePath}`);

    if (report.cache.hits < 1) {
        throw new Error('expected at least one cache hit');
    }

    console.log('\nCompleted successfully.');
}

main().catch(error => {
    console.error(`fatal error: ${error.message}`);
    process.exitCode = 1;
});
