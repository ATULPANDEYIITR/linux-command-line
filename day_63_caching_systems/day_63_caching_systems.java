import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

public class CacheGovernanceDemo {

    enum CacheStatus {
        HIT,
        MISS,
        STALE
    }

    enum InvalidationReason {
        DATA_MUTATION,
        EXPLICIT_PURGE,
        POLICY_CHANGE,
        EXPIRATION
    }

    record Product(
        int id,
        String name,
        double price,
        int stock,
        long version
    ) {
        Product {
            if (id <= 0) {
                throw new IllegalArgumentException("id must be positive");
            }
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("name is required");
            }
            if (price < 0) {
                throw new IllegalArgumentException("price cannot be negative");
            }
            if (stock < 0) {
                throw new IllegalArgumentException("stock cannot be negative");
            }
            if (version <= 0) {
                throw new IllegalArgumentException("version must be positive");
            }
        }
    }

    record CacheEntry<T>(
        T value,
        Instant createdAt,
        Instant expiresAt,
        long version,
        Set<String> tags
    ) {
        CacheEntry {
            Objects.requireNonNull(value);
            Objects.requireNonNull(createdAt);
            Objects.requireNonNull(tags);
            tags = Set.copyOf(tags);
        }

        boolean stale() {
            return expiresAt != null && !Instant.now().isBefore(expiresAt);
        }
    }

    record CacheRead<T>(CacheStatus status, T value) {
    }

    record CacheMetrics(
        long hits,
        long misses,
        long stale,
        long writes,
        long evictions,
        long invalidations
    ) {
        double hitRate() {
            long requests = hits + misses + stale;
            return requests == 0
                ? 0.0
                : (double) hits / requests;
        }
    }

    interface Repository<T, K> {
        T find(K key);

        T save(K key, T value);
    }

    static final class ProductRepository
        implements Repository<Product, Integer> {

        private final Map<Integer, Product> products = new HashMap<>();

        ProductRepository() {
            products.put(
                101,
                new Product(101, "Edge Router", 249.99, 18, 1)
            );
            products.put(
                102,
                new Product(102, "Secure Gateway", 499.00, 7, 1)
            );
            products.put(
                103,
                new Product(103, "Telemetry Node", 129.50, 31, 1)
            );
        }

        @Override
        public synchronized Product find(Integer id) {
            Product product = products.get(id);

            if (product == null) {
                throw new IllegalArgumentException(
                    "product " + id + " does not exist"
                );
            }

            return product;
        }

        @Override
        public synchronized Product save(Integer id, Product product) {
            products.put(id, product);
            return product;
        }

        synchronized Product updatePrice(int id, double price) {
            if (price < 0) {
                throw new IllegalArgumentException(
                    "price cannot be negative"
                );
            }

            Product current = find(id);

            return save(
                id,
                new Product(
                    current.id(),
                    current.name(),
                    price,
                    current.stock(),
                    current.version() + 1
                )
            );
        }

        synchronized Product purchase(int id, int quantity) {
            if (quantity <= 0) {
                throw new IllegalArgumentException(
                    "quantity must be positive"
                );
            }

            Product current = find(id);

            if (current.stock() < quantity) {
                throw new IllegalStateException(
                    "insufficient stock"
                );
            }

            return save(
                id,
                new Product(
                    current.id(),
                    current.name(),
                    current.price(),
                    current.stock() - quantity,
                    current.version() + 1
                )
            );
        }
    }

    static final class LruCache<K, V> {
        private record Entry<V>(
            V value,
            Instant expiresAt,
            long version,
            Set<String> tags
        ) {}

        private final int capacity;
        private final Duration defaultTtl;

        private final LinkedHashMap<K, Entry<V>> entries =
            new LinkedHashMap<>(16, 0.75f, true);

        private long hits;
        private long misses;
        private long stale;
        private long writes;
        private long evictions;
        private long invalidations;

        LruCache(int capacity, Duration defaultTtl) {
            if (capacity <= 0) {
                throw new IllegalArgumentException(
                    "capacity must be positive"
                );
            }

            if (defaultTtl.isNegative() || defaultTtl.isZero()) {
                throw new IllegalArgumentException(
                    "ttl must be positive"
                );
            }

            this.capacity = capacity;
            this.defaultTtl = defaultTtl;
        }

        synchronized CacheRead<V> get(K key) {
            Entry<V> entry = entries.get(key);

            if (entry == null) {
                misses++;
                return new CacheRead<>(CacheStatus.MISS, null);
            }

            if (
                entry.expiresAt() != null &&
                !Instant.now().isBefore(entry.expiresAt())
            ) {
                entries.remove(key);
                stale++;
                return new CacheRead<>(CacheStatus.STALE, null);
            }

            hits++;
            return new CacheRead<>(CacheStatus.HIT, entry.value());
        }

        synchronized void put(
            K key,
            V value,
            long version,
            Set<String> tags
        ) {
            Objects.requireNonNull(key);
            Objects.requireNonNull(value);

            Instant expiresAt =
                Instant.now().plus(defaultTtl);

            entries.put(
                key,
                new Entry<>(
                    value,
                    expiresAt,
                    version,
                    Set.copyOf(tags)
                )
            );

            writes++;

            while (entries.size() > capacity) {
                K eldest = entries.keySet().iterator().next();
                entries.remove(eldest);
                evictions++;
            }
        }

        synchronized boolean invalidate(
            K key,
            InvalidationReason reason
        ) {
            boolean removed = entries.remove(key) != null;

            if (removed) {
                invalidations++;
            }

            return removed;
        }

        synchronized int invalidateByTag(String tag) {
            List<K> keys = entries.entrySet()
                .stream()
                .filter(e -> e.getValue().tags().contains(tag))
                .map(Map.Entry::getKey)
                .toList();

            keys.forEach(key ->
                invalidate(key, InvalidationReason.EXPLICIT_PURGE)
            );

            return keys.size();
        }

        synchronized CacheMetrics metrics() {
            return new CacheMetrics(
                hits,
                misses,
                stale,
                writes,
                evictions,
                invalidations
            );
        }
    }

    static final class CachedProductService {
        private final ProductRepository repository;
        private final LruCache<String, Product> cache;

        CachedProductService(
            ProductRepository repository,
            LruCache<String, Product> cache
        ) {
            this.repository = repository;
            this.cache = cache;
        }

        private String key(int id) {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "product id must be positive"
                );
            }

            return "product:" + id;
        }

        Product get(int id) {
            String key = key(id);
            CacheRead<Product> read = cache.get(key);

            if (read.status() == CacheStatus.HIT) {
                return read.value();
            }

            Product product = repository.find(id);

            cache.put(
                key,
                product,
                product.version(),
                Set.of("product", key)
            );

            return product;
        }

        Product updatePrice(int id, double price) {
            Product updated =
                repository.updatePrice(id, price);

            cache.invalidate(
                key(id),
                InvalidationReason.DATA_MUTATION
            );

            return updated;
        }

        Product purchase(int id, int quantity) {
            Product updated =
                repository.purchase(id, quantity);

            cache.invalidate(
                key(id),
                InvalidationReason.DATA_MUTATION
            );

            return updated;
        }
    }

    static final class StaleWhileRevalidate<T> {
        private record StaleEntry<T>(
            T value,
            Instant freshUntil,
            Instant staleUntil
        ) {}

        private final Map<String, StaleEntry<T>> entries =
            new HashMap<>();

        private final Set<String> refreshing = new HashSet<>();

        synchronized T get(
            String key,
            Function<String, T> loader
        ) {
            StaleEntry<T> entry = entries.get(key);

            if (entry == null) {
                T value = loader.apply(key);
                put(key, value, Duration.ofSeconds(30));
                return value;
            }

            Instant now = Instant.now();

            if (now.isBefore(entry.freshUntil())) {
                return entry.value();
            }

            if (now.isBefore(entry.staleUntil())) {
                if (refreshing.add(key)) {
                    try {
                        T value = loader.apply(key);
                        put(key, value, Duration.ofSeconds(30));
                    } finally {
                        refreshing.remove(key);
                    }
                }

                return entry.value();
            }

            entries.remove(key);
            T value = loader.apply(key);
            put(key, value, Duration.ofSeconds(30));
            return value;
        }

        synchronized void put(
            String key,
            T value,
            Duration ttl
        ) {
            Instant freshUntil = Instant.now().plus(ttl);
            Instant staleUntil =
                freshUntil.plus(Duration.ofSeconds(10));

            entries.put(
                key,
                new StaleEntry<>(
                    value,
                    freshUntil,
                    staleUntil
                )
            );
        }
    }

    static String cacheKey(String namespace, String identifier) {
        if (namespace == null || namespace.isBlank()) {
            throw new IllegalArgumentException(
                "namespace is required"
            );
        }

        if (identifier == null || identifier.isBlank()) {
            throw new IllegalArgumentException(
                "identifier is required"
            );
        }

        return namespace + ":" +
            Integer.toUnsignedString(identifier.hashCode());
    }

    static void print(Product product) {
        System.out.printf(
            "%d | %s | %.2f | stock=%d | version=%d%n",
            product.id(),
            product.name(),
            product.price(),
            product.stock(),
            product.version()
        );
    }

    public static void main(String[] args) {
        ProductRepository repository =
            new ProductRepository();

        LruCache<String, Product> cache =
            new LruCache<>(
                2,
                Duration.ofSeconds(60)
            );

        CachedProductService service =
            new CachedProductService(repository, cache);

        System.out.println("=== Cache-aside workflow ===");

        print(service.get(101));
        print(service.get(101));

        System.out.println("\n=== Capacity pressure ===");

        service.get(102);
        service.get(103);

        System.out.println(
            "metrics after eviction pressure: " +
            cache.metrics()
        );

        System.out.println("\n=== Mutation invalidation ===");

        service.updatePrice(101, 279.99);
        print(service.get(101));

        System.out.println("\n=== Failure handling ===");

        try {
            service.purchase(102, 100);
        } catch (IllegalStateException ex) {
            System.out.println(
                "expected business failure: " +
                ex.getMessage()
            );
        }

        System.out.println("\n=== Tag purge ===");

        service.get(101);
        service.get(103);

        int purged = cache.invalidateByTag("product");

        System.out.println(
            "entries purged by tag: " + purged
        );

        System.out.println("\n=== Stale-while-revalidate ===");

        StaleWhileRevalidate<Map<String, Object>> swr =
            new StaleWhileRevalidate<>();

        swr.put(
            "config",
            Map.of("version", 1),
            Duration.ofMillis(10)
        );

        try {
            Thread.sleep(15);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(
                "interrupted during cache demonstration",
                ex
            );
        }

        Map<String, Object> refreshed =
            swr.get(
                "config",
                key -> Map.of(
                    "version",
                    2,
                    "source",
                    "authoritative-store"
                )
            );

        System.out.println(refreshed);

        System.out.println("\n=== Metrics ===");

        CacheMetrics metrics = cache.metrics();

        System.out.printf(
            "hits=%d misses=%d stale=%d writes=%d " +
            "evictions=%d invalidations=%d hitRate=%.3f%n",
            metrics.hits(),
            metrics.misses(),
            metrics.stale(),
            metrics.writes(),
            metrics.evictions(),
            metrics.invalidations(),
            metrics.hitRate()
        );

        String safeKey =
            cacheKey("customer", "customer/123?region=IN");

        System.out.println("safe key: " + safeKey);

        if (metrics.hits() == 0) {
            throw new IllegalStateException(
                "expected at least one cache hit"
            );
        }

        if (
            metrics.hitRate() < 0.0 ||
            metrics.hitRate() > 1.0
        ) {
            throw new IllegalStateException(
                "invalid hit-rate metric"
            );
        }

        System.out.println("\nCompleted successfully.");
    }
}
