# Caching Systems

This project implements a complete caching case study covering in-memory caching, distributed-cache concepts, cache invalidation, cache-aside loading, LRU eviction, TTL expiration, stale-while-revalidate behavior, cache stampede control, version validation, cache tagging, operational metrics, and database-backed cache state.

The five implementations use the same domain problem but deliberately emphasize different engineering mechanisms.

## Domain Model

The central scenario is an inventory platform serving product information through application services.

The authoritative data path is:

Repository → Product State → Cache Population → Application Read

The mutation path is:

Client Mutation → Authoritative Store → Version Change → Cache Invalidation → Future Cache Miss → Refresh

The distributed model uses two conceptual cache layers:

Application Node
→ L1 Local Cache
→ L2 Distributed Cache
→ Authoritative Repository

The local cache reduces latency for repeated reads handled by the same process. The distributed cache allows multiple application nodes to share cached state. The authoritative repository remains the source of truth.

## Core Caching Concepts

### In-Memory Caching

An in-memory cache keeps frequently accessed values in process memory.

The Python, JavaScript, C++, and Java implementations maintain bounded cache structures. A cache entry contains a value, creation information, expiration information, version metadata, and optional tags.

A cache hit avoids an authoritative lookup.

A cache miss causes the service to load the value from the source and populate the cache.

The basic cache-aside sequence is:

Read request
→ Cache lookup
→ HIT → return cached value

Read request
→ Cache lookup
→ MISS → read source
→ populate cache
→ return value

The implementations treat the cache as an optimization rather than the authoritative data store.

### TTL

Time-to-live limits how long an entry is considered fresh.

The Python implementation uses `monotonic()` for elapsed-time calculations. This avoids problems caused by wall-clock adjustments.

The JavaScript implementation uses `Date.now()` because the example is based on millisecond-oriented Node.js timing.

The Java implementation uses `Instant`.

The C++ implementation uses `std::chrono::steady_clock`.

These choices prevent cache expiration logic from depending unnecessarily on changes to the system wall clock.

### LRU Eviction

A bounded cache needs an eviction strategy when capacity is reached.

Least Recently Used eviction removes the entry that has not been accessed for the longest time.

Python maintains access timestamps separately from entries.

JavaScript uses an access-ordered `Map`.

Java uses an access-ordered `LinkedHashMap`.

C++ maintains a value map plus ordered access metadata.

The result is that a frequently reused entry can remain resident while older unused entries are removed.

## Cache Invalidation

Expiration and invalidation solve different problems.

TTL answers:

> How long should a value remain fresh without another explicit event?

Invalidation answers:

> What should happen when the underlying value changes before its TTL expires?

For mutable product data, invalidation is necessary because a long TTL can otherwise expose old information.

The mutation workflow is:

1. Update authoritative product data.
2. Increment the product version.
3. Invalidate the corresponding cache key.
4. Allow the next read to repopulate the cache.

The implementations intentionally perform the authoritative mutation before invalidation. If the authoritative mutation fails, the existing cache entry is not unnecessarily destroyed.

## Version Validation

Each product has a monotonically increasing version.

A cached product therefore carries both:

- the product value
- the source version observed when the value was cached

The PostgreSQL implementation compares the cache version with the authoritative product version.

A matching version indicates that the cached representation corresponds to the observed source state.

A mismatch indicates that the cache should not be trusted as current.

Version metadata is useful when TTL alone cannot provide sufficiently precise freshness semantics.

## Cache Tags

Cache entries may belong to logical groups.

The examples use tags such as:

- `product`
- `product:101`
- `product:102`
- `product:103`

Tag invalidation allows an application to remove a related group of entries without knowing every key individually.

For example, a product-catalog deployment can invalidate the `product` tag when a broad catalog refresh occurs.

The PostgreSQL model stores tags in a separate relation rather than embedding them into a JSON document. This permits indexed tag lookup and referential cleanup when an entry is removed.

## Stale-While-Revalidate

A strict TTL strategy can produce a burst of misses when a popular entry expires.

Stale-while-revalidate introduces a second interval.

Fresh interval:

`request → fresh cache value → immediate response`

Stale interval:

`request → recently expired value → serve stale value → refresh`

After the stale window:

`request → unusable entry → authoritative load`

This approach can reduce latency spikes and prevent many clients from simultaneously waiting for the same expensive refresh operation.

The examples coordinate refresh ownership locally. A real multi-node deployment would normally use a distributed lease or lock when refresh ownership must be coordinated across processes.

## Cache Stampede

A cache stampede occurs when many requests observe an expired or missing popular key and all independently execute the expensive source query.

The C++ implementation includes a `CacheStampedeGuard` that models refresh ownership.

The important property is that only one refresh owner should be responsible for a particular key while other requests reuse an existing value or wait according to the selected policy.

A distributed implementation needs distributed coordination rather than an in-process set when multiple application nodes can refresh the same key.

## Python Implementation

The Python implementation is a complete executable model centered on a thread-safe `InMemoryCache`.

`CacheEntry` is a dataclass representing immutable cached state. `CacheStats` records hits, misses, stale reads, writes, evictions, and invalidations.

`RLock` protects cache state because cache operations may be called by concurrent application threads.

The implementation supports:

- LRU eviction
- TTL expiration
- explicit key invalidation
- tag invalidation
- prefix invalidation
- version metadata
- cache statistics
- cache-aside product loading
- two-level local/distributed cache modeling
- stale-while-revalidate behavior
- deterministic cache-key hashing
- assertions
- diagnostic file output

The `ProductRepository` represents authoritative state. `CachedProductService` implements the cache-aside pattern.

The `DistributedNode` class demonstrates how a local L1 cache can sit in front of a shared L2 cache. Both nodes use the same repository and distributed cache while retaining independent local caches.

The Python implementation also demonstrates safe cache-key construction using SHA-256 when arbitrary identifiers should not be embedded directly into backend keys.

## JavaScript Implementation

The JavaScript implementation emphasizes event-driven behavior.

`EventBus` provides a small event mechanism for cache events such as:

- hit
- miss
- set
- eviction
- invalidation
- stale access

The cache uses an insertion-ordered `Map`. Deleting and reinserting a key on successful access makes the map represent access order, allowing the oldest entry to be removed when capacity is exceeded.

The implementation uses asynchronous repository operations to model application services that perform I/O.

`structuredClone` separates cached values from mutable objects held by callers. This prevents accidental mutation of an object returned from the cache from silently changing the cached representation.

`StaleWhileRevalidate` uses Promises to coordinate refresh operations. A `Map` of active refresh Promises prevents duplicate refresh work for the same key within the process.

Node.js standard-library modules are used for:

- cryptographic cache-key hashing
- filesystem diagnostics
- asynchronous execution

No external npm dependency is required.

## C++17 Implementation

The C++ implementation treats caching as a performance-sensitive systems component.

`LruCache` uses:

- `std::unordered_map` for average constant-time value lookup
- ordered access metadata for eviction
- `std::chrono::steady_clock` for TTL measurement
- `std::set` for tags
- explicit exception handling for invalid states

The separation between value storage and access ordering demonstrates a common systems design trade-off: cache lookup and eviction metadata have different access patterns.

`ProductRepository` owns authoritative product state.

`GovernanceAwareCache` enforces the ordering of source mutation and cache invalidation.

`CacheStampedeGuard` provides a small refresh-ownership mechanism.

The C++ program validates products at object boundaries and reports cache metrics at the end of execution.

The implementation avoids external libraries so it can compile using standard C++17 facilities.

## Java 17 Implementation

The Java implementation models caching as an enterprise service with explicit domain types.

The product is represented as an immutable `record`.

`Repository<T, K>` defines a generic repository abstraction.

`LruCache<K, V>` is generic and uses an access-ordered `LinkedHashMap`. This provides a compact implementation of LRU behavior while keeping cache policy inside the cache abstraction.

`CacheMetrics`, `CacheRead`, `CacheEntry`, and the enums represent explicit domain concepts rather than relying on unstructured maps.

`CachedProductService` owns cache-aside behavior.

`InvalidationReason` distinguishes why an entry was removed:

- data mutation
- explicit purge
- policy change
- expiration

`StaleWhileRevalidate` demonstrates refresh ownership and stale-value serving.

Java's immutable records reduce accidental mutation of values after they have entered the cache. The generic cache design also allows the same cache abstraction to be reused for other value types.

## PostgreSQL Implementation

The PostgreSQL implementation models the caching system relationally.

The main relations are:

| Relation | Purpose |
|---|---|
| `repositories` | Identifies authoritative application repositories |
| `cache_policies` | Stores backend, capacity, TTL, stale-window, and value-size policies |
| `products` | Authoritative product data |
| `cache_namespaces` | Connects repositories with cache policies |
| `cache_entries` | Stores cached values and lifecycle state |
| `cache_tags` | Associates cache entries with logical invalidation groups |
| `cache_events` | Records cache activity for operational analysis |
| `invalidation_log` | Records explicit invalidation decisions |

The relational model separates policy from data.

A cache entry therefore does not need to contain every policy decision itself. The namespace points to the policy that controls it.

## Database Constraints

The PostgreSQL model uses database constraints to reject invalid states.

Product constraints enforce:

- non-negative prices
- non-negative inventory
- positive versions
- valid identifiers

Cache policy constraints enforce:

- positive capacity
- positive TTL
- non-negative stale windows
- positive value-size limits

Cache-entry constraints prevent invalid keys and invalid version values.

These checks protect the data even when an application-level validation layer is bypassed.

## PostgreSQL Functions

`cache_product_json` converts authoritative product state into a cache representation.

`put_cache_entry` performs policy-aware insertion or replacement and rejects values exceeding the configured size limit.

`read_cache_entry` updates access metadata and evaluates freshness.

`invalidate_cache_key` records an explicit invalidation reason.

`invalidate_by_tag` performs grouped invalidation.

`evict_lru` identifies least-recently-accessed entries and marks them as evicted.

The SQL functions keep important lifecycle behavior close to the data model.

## Transactional Integrity

The mutation example performs the following operations inside a transaction:

`UPDATE products`

followed by:

`invalidate_cache_key(...)`

The transaction ensures that the database mutation and corresponding invalidation participate in one transactional unit.

A production distributed cache may still require an external invalidation mechanism after transaction commit because a remote cache does not automatically participate in a PostgreSQL transaction.

The database model therefore demonstrates transactional integrity for authoritative state and invalidation records, while recognizing that a physical Redis or Memcached deployment introduces a separate consistency boundary.

## Failure Conditions

The implementations cover several important failures.

### Invalid Configuration

A cache with zero capacity is rejected.

A non-positive TTL is rejected.

Invalid product prices and inventory quantities are rejected.

### Missing Source Data

A product lookup for an unknown identifier raises an error instead of inserting an empty cache value.

### Insufficient Inventory

A purchase that exceeds available inventory fails before the authoritative product state changes.

The corresponding cache entry therefore remains valid.

### Oversized Cached Values

The PostgreSQL `put_cache_entry` function compares the serialized JSON size with the configured policy limit.

This prevents a single large value from consuming uncontrolled cache storage.

### Expired Entries

Expired entries are not treated as fresh hits.

Depending on the strategy, they are removed, marked stale, or temporarily served through stale-while-revalidate behavior.

### Cache Corruption

The Python service validates the expected cached product type before returning it. An unexpected cached object causes invalidation rather than silently returning malformed application state.

## Security Considerations

Caching changes the location and lifetime of application data.

Sensitive values should not automatically be cached simply because they are frequently accessed.

Cache keys should avoid unnecessary exposure of user-controlled information. The implementations demonstrate hashing arbitrary identifiers before constructing keys where appropriate.

Authorization-sensitive data requires special care. A key such as `profile:123` must not accidentally be reused for another security context when the cached value depends on permissions, tenant identity, or session state.

A safer conceptual key is:

`tenant + identity + authorization context + resource`

when all of those dimensions affect the returned value.

Cache contents should also receive access controls appropriate to their data sensitivity.

The PostgreSQL event and invalidation tables deliberately record metadata rather than copying entire application payloads into audit records.

## Performance Considerations

Caching improves performance only when the cost of maintaining the cache is lower than the cost of repeated source access.

Important measurements include:

| Metric | Meaning |
|---|---|
| Hit rate | Percentage of cacheable requests served from cache |
| Miss rate | Percentage requiring source access |
| Stale rate | Requests encountering expired values |
| Evictions | Entries removed because capacity was reached |
| Invalidation count | Explicit cache removals |
| Access count | Relative popularity of cached values |
| Cached bytes | Memory or storage pressure |

High hit rate is not automatically sufficient. A cache can have a high hit rate while serving incorrect data if invalidation is broken.

Conversely, an extremely low TTL may improve freshness but produce excessive source load.

## Cache Strategy Selection

| Strategy | Strength | Main Risk |
|---|---|---|
| Cache-aside | Simple and widely applicable | Application must manage invalidation |
| Write-through | Cache updated with writes | Write latency and cache dependency |
| Write-behind | Lower write latency | More complex durability guarantees |
| TTL-only | Simple expiration model | Can serve old values |
| Explicit invalidation | Stronger freshness | Invalidation paths must be complete |
| LRU | Preserves popular entries | Requires access metadata |
| Stale-while-revalidate | Smooths expiration spikes | Temporarily serves stale data |
| L1 + L2 | Low local latency plus sharing | More complex consistency |

The implementations primarily use cache-aside plus explicit invalidation because it makes source-of-truth boundaries clear.

## Consistency Boundary

A cache is normally not equivalent to the authoritative database.

The following states should remain distinct:

`Authoritative State`
→ current source representation

`Cached State`
→ previously observed representation

`Cache Metadata`
→ expiration, version, tags, access information

`Invalidation Record`
→ decision that cached state should no longer be used

Treating these as separate concepts prevents a cache from accidentally becoming the only copy of important application state.

## Practical Workflow

A product read follows this path:

`Request`
→ `L1 lookup`
→ `L2 lookup`
→ `Repository lookup`
→ `Cache population`
→ `Response`

A successful mutation follows:

`Request`
→ `Validate`
→ `Update authoritative state`
→ `Increment version`
→ `Invalidate affected cache`
→ `Commit`
→ `Future read repopulates cache`

A popular expired key follows:

`Expired entry`
→ `Serve stale if policy permits`
→ `Acquire refresh ownership`
→ `Load authoritative value`
→ `Replace cache entry`
→ `Release refresh ownership`

## Edge Cases

The implementations explicitly account for:

- zero or negative cache capacity
- invalid TTL values
- unknown product identifiers
- negative prices
- negative inventory
- insufficient inventory
- expired cache entries
- cache capacity pressure
- grouped invalidation
- version mismatch
- malformed cached values
- oversized database cache values
- duplicate refresh attempts
- interrupted Java execution
- failed authoritative mutations
- invalid cache keys

These cases are important because cache failures often occur at boundaries between freshness, capacity, concurrency, and source-of-truth behavior.

## Implementation Comparison

| Area | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Primary emphasis | Simulation and service behavior | Events and async processing | Systems-oriented cache engine | Enterprise domain model | Relational persistence and policy |
| LRU | Yes | Yes | Yes | Yes | LRU eviction query |
| TTL | Yes | Yes | Yes | Yes | Yes |
| Invalidation | Key, tag, prefix | Key, tag | Key, tag | Key, tag | Key, tag |
| Versioning | Yes | Yes | Yes | Yes | Yes |
| Stale-while-revalidate | Yes | Yes | Refresh guard | Yes | Stale state |
| Metrics | Yes | Yes | Yes | Yes | Reporting queries |
| Persistence | Diagnostic JSON | Diagnostic JSON | In-memory | In-memory | PostgreSQL |
| Concurrency model | Reentrant lock | Promise/event model | Explicit refresh guard | Synchronized services | Transactional SQL |

## Architectural Distinctions

The project keeps four levels of behavior separate.

**Cache storage** determines where values reside and how they are retrieved.

**Cache policy** determines TTL, capacity, size limits, and stale behavior.

**Invalidation** determines when a cached representation must stop being trusted.

**Authoritative state** determines the actual current application value.

A cache implementation is correct only when these boundaries remain explicit.

The central engineering rule is:

`Cache improves access to state; it does not define authoritative state.`

When freshness requirements, invalidation guarantees, capacity limits, concurrency behavior, and failure handling are designed together, caching becomes a controlled performance mechanism rather than an uncontrolled secondary database.
