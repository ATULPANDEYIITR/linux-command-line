'use strict';

/*
 * Content Delivery Network simulation.
 *
 * The model separates:
 *   client -> edge selection -> cache lookup -> origin fetch
 *
 * It also models TTL expiration, ETags, cache-control decisions,
 * invalidation, LRU eviction, and asynchronous origin access.
 */

const crypto = require('crypto');

class ContentObject {
    constructor(path, body, contentType, cacheControl = 'public, max-age=60') {
        if (!path.startsWith('/')) {
            throw new Error('Content path must begin with /.');
        }

        this.path = path;
        this.body = body;
        this.contentType = contentType;
        this.cacheControl = cacheControl;
        this.etag = crypto
            .createHash('sha256')
            .update(body)
            .digest('hex')
            .slice(0, 16);
    }
}

class OriginServer {
    constructor(name, region, latencyMs) {
        this.name = name;
        this.region = region;
        this.latencyMs = latencyMs;
        this.objects = new Map();
    }

    publish(content) {
        this.objects.set(content.path, content);
    }

    async fetch(path) {
        const content = this.objects.get(path);

        if (!content) {
            const error = new Error(`Origin object not found: ${path}`);
            error.code = 'NOT_FOUND';
            throw error;
        }

        await new Promise(resolve => setTimeout(resolve, this.latencyMs));
        return content;
    }
}

class LRUCache {
    constructor(capacity) {
        if (!Number.isInteger(capacity) || capacity <= 0) {
            throw new Error('Cache capacity must be a positive integer.');
        }

        this.capacity = capacity;
        this.entries = new Map();
    }

    get(key, now) {
        const entry = this.entries.get(key);

        if (!entry) {
            return { status: 'MISS', content: null };
        }

        this.entries.delete(key);
        this.entries.set(key, entry);

        if (now < entry.expiresAt) {
            return { status: 'HIT', content: entry.content };
        }

        return { status: 'STALE', content: entry.content };
    }

    put(key, content, ttlSeconds, now) {
        this.entries.delete(key);
        this.entries.set(key, {
            content,
            expiresAt: now + ttlSeconds * 1000
        });

        while (this.entries.size > this.capacity) {
            const oldest = this.entries.keys().next().value;
            this.entries.delete(oldest);
        }
    }

    invalidate(key) {
        return this.entries.delete(key);
    }

    clear() {
        this.entries.clear();
    }

    keys() {
        return [...this.entries.keys()];
    }
}

class EdgeLocation {
    constructor(name, region, origin, cacheCapacity = 3) {
        this.name = name;
        this.region = region;
        this.origin = origin;
        this.cache = new LRUCache(cacheCapacity);
    }

    async request(path, now) {
        const cached = this.cache.get(path, now);

        if (cached.status === 'HIT') {
            return {
                edge: this.name,
                cacheStatus: 'HIT',
                source: 'edge-cache',
                latencyMs: 8,
                etag: cached.content.etag
            };
        }

        const content = await this.origin.fetch(path);

        if (isSharedCacheable(content)) {
            const ttl = parseMaxAge(content.cacheControl);
            if (ttl > 0) {
                this.cache.put(path, content, ttl, now);
            }
        }

        return {
            edge: this.name,
            cacheStatus: cached.status,
            source: 'origin',
            latencyMs: 8 + this.origin.latencyMs,
            etag: content.etag
        };
    }
}

class CDN {
    constructor(edges) {
        this.edges = edges;
    }

    selectEdge(clientRegion) {
        const exact = this.edges.find(edge => edge.region === clientRegion);
        return exact || this.edges[0];
    }

    async fetch(clientRegion, path, now = Date.now()) {
        const edge = this.selectEdge(clientRegion);
        const result = await edge.request(path, now);

        return {
            clientRegion,
            path,
            ...result
        };
    }

    purge(path) {
        let removed = 0;

        for (const edge of this.edges) {
            if (edge.cache.invalidate(path)) {
                removed++;
            }
        }

        return removed;
    }
}

function parseMaxAge(cacheControl) {
    const match = cacheControl.match(/(?:^|,)\s*max-age\s*=\s*(\d+)/i);
    return match ? Number(match[1]) : 0;
}

function isSharedCacheable(content) {
    const directives = content.cacheControl
        .split(',')
        .map(value => value.trim().toLowerCase());

    return !directives.includes('private') &&
           !directives.includes('no-store');
}

async function main() {
    const origin = new OriginServer('origin-us-east', 'us-east', 20);

    origin.publish(new ContentObject(
        '/index.html',
        '<html><body>CDN edge delivery</body></html>',
        'text/html',
        'public, max-age=60'
    ));

    origin.publish(new ContentObject(
        '/app.js',
        'console.log("edge-delivered asset");',
        'application/javascript',
        'public, max-age=300'
    ));

    origin.publish(new ContentObject(
        '/account/profile.json',
        '{"account":"private"}',
        'application/json',
        'private, no-store'
    ));

    const cdn = new CDN([
        new EdgeLocation('delhi-edge', 'asia', origin, 2),
        new EdgeLocation('frankfurt-edge', 'europe', origin, 2),
        new EdgeLocation('virginia-edge', 'us-east', origin, 2)
    ]);

    let clock = Date.now();

    console.log(await cdn.fetch('asia', '/index.html', clock));
    console.log(await cdn.fetch('asia', '/index.html', clock));

    console.log(await cdn.fetch('europe', '/index.html', clock));
    console.log(await cdn.fetch('asia', '/app.js', clock));

    console.log('\nCache contents:');
    for (const edge of cdn.edges) {
        console.log(edge.name, edge.cache.keys());
    }

    clock += 61_000;
    console.log('\nAfter TTL expiration:');
    console.log(await cdn.fetch('asia', '/index.html', clock));

    console.log('\nGlobal purge:');
    console.log(`Removed from ${cdn.purge('/index.html')} edge caches.`);
    console.log(await cdn.fetch('asia', '/index.html', clock));

    console.log('\nPrivate content policy:');
    const privateContent = origin.objects.get('/account/profile.json');
    console.log({
        cacheable: isSharedCacheable(privateContent),
        cacheControl: privateContent.cacheControl
    });

    console.log('\nLRU eviction:');
    await cdn.fetch('asia', '/index.html', clock);
    await cdn.fetch('asia', '/app.js', clock);
    console.log(await cdn.fetch('asia', '/index.html', clock));
    console.log(await cdn.fetch('asia', '/account/profile.json', clock));
    console.log('Final cache:', cdn.edges[0].cache.keys());
}

main().catch(error => {
    console.error('CDN simulation failed:', error.message);
    process.exitCode = 1;
});
