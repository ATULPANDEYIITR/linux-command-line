from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import RLock
from time import monotonic, sleep
from typing import Any, Callable, Optional
import hashlib
import json
import logging
import tempfile


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


class CacheError(Exception):
    """Base exception for cache failures."""


class CacheMiss(CacheError):
    """Raised when a required cache entry is absent or unusable."""


class CachePolicyError(CacheError):
    """Raised when a cache operation violates a policy."""


class CacheStatus(str, Enum):
    HIT = "hit"
    MISS = "miss"
    STALE = "stale"


class EvictionPolicy(str, Enum):
    LRU = "lru"
    TTL = "ttl"


@dataclass(frozen=True)
class CacheEntry:
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float]
    version: int = 1
    tags: frozenset[str] = frozenset()

    def expired(self, now: float) -> bool:
        return self.expires_at is not None and now >= self.expires_at


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    stale: int = 0
    writes: int = 0
    evictions: int = 0
    invalidations: int = 0

    @property
    def requests(self) -> int:
        return self.hits + self.misses + self.stale

    @property
    def hit_rate(self) -> float:
        return self.hits / self.requests if self.requests else 0.0


class InMemoryCache:
    """
    Thread-safe bounded cache.

    The cache stores immutable CacheEntry objects. LRU metadata is maintained
    separately so replacement and invalidation cannot mutate callers' values.
    """

    def __init__(
        self,
        capacity: int = 1000,
        default_ttl: Optional[float] = 60.0,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if default_ttl is not None and default_ttl <= 0:
            raise ValueError("default_ttl must be positive or None")

        self.capacity = capacity
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy
        self._entries: dict[str, CacheEntry] = {}
        self._access_order: dict[str, int] = {}
        self._counter = 0
        self._lock = RLock()
        self.stats = CacheStats()

    def _touch(self, key: str) -> None:
        self._counter += 1
        self._access_order[key] = self._counter

    def get(self, key: str) -> tuple[CacheStatus, Any | None]:
        if not key:
            raise ValueError("cache key cannot be empty")

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.stats.misses += 1
                return CacheStatus.MISS, None

            if entry.expired(monotonic()):
                self._entries.pop(key, None)
                self._access_order.pop(key, None)
                self.stats.stale += 1
                return CacheStatus.STALE, None

            self._touch(key)
            self.stats.hits += 1
            return CacheStatus.HIT, entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        version: int = 1,
        tags: set[str] | frozenset[str] | None = None,
    ) -> None:
        if not key:
            raise ValueError("cache key cannot be empty")
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive or None")
        if version <= 0:
            raise ValueError("version must be positive")

        effective_ttl = self.default_ttl if ttl is None else ttl
        now = monotonic()
        expires_at = None if effective_ttl is None else now + effective_ttl

        with self._lock:
            self._entries[key] = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                version=version,
                tags=frozenset(tags or set()),
            )
            self._touch(key)
            self.stats.writes += 1
            self._evict_if_needed()

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._entries
            self._entries.pop(key, None)
            self._access_order.pop(key, None)
            if existed:
                self.stats.invalidations += 1
            return existed

    def invalidate_tag(self, tag: str) -> int:
        if not tag:
            raise ValueError("tag cannot be empty")

        with self._lock:
            keys = [
                key
                for key, entry in self._entries.items()
                if tag in entry.tags
            ]
            for key in keys:
                self._entries.pop(key, None)
                self._access_order.pop(key, None)

            self.stats.invalidations += len(keys)
            return len(keys)

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._entries if key.startswith(prefix)]
            for key in keys:
                self._entries.pop(key, None)
                self._access_order.pop(key, None)
            self.stats.invalidations += len(keys)
            return len(keys)

    def _evict_if_needed(self) -> None:
        while len(self._entries) > self.capacity:
            if self.eviction_policy == EvictionPolicy.LRU:
                victim = min(
                    self._access_order,
                    key=self._access_order.get,
                )
            else:
                victim = min(
                    self._entries,
                    key=lambda k: (
                        self._entries[k].expires_at
                        if self._entries[k].expires_at is not None
                        else float("inf")
                    ),
                )

            self._entries.pop(victim, None)
            self._access_order.pop(victim, None)
            self.stats.evictions += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._entries),
                "capacity": self.capacity,
                "hit_rate": round(self.stats.hit_rate, 4),
                "hits": self.stats.hits,
                "misses": self.stats.misses,
                "stale": self.stats.stale,
                "writes": self.stats.writes,
                "evictions": self.stats.evictions,
                "invalidations": self.stats.invalidations,
            }


@dataclass
class Product:
    product_id: int
    name: str
    price: float
    inventory: int
    version: int = 1

    def validate(self) -> None:
        if self.product_id <= 0:
            raise ValueError("product_id must be positive")
        if not self.name.strip():
            raise ValueError("product name cannot be empty")
        if self.price < 0:
            raise ValueError("price cannot be negative")
        if self.inventory < 0:
            raise ValueError("inventory cannot be negative")


class ProductRepository:
    def __init__(self) -> None:
        self._products: dict[int, Product] = {
            101: Product(101, "Edge Router", 249.99, 18),
            102: Product(102, "Secure Gateway", 499.00, 7),
            103: Product(103, "Telemetry Node", 129.50, 31),
        }

    def find(self, product_id: int) -> Product:
        product = self._products.get(product_id)
        if product is None:
            raise KeyError(f"product {product_id} not found")
        return Product(**vars(product))

    def update_inventory(self, product_id: int, quantity: int) -> Product:
        if quantity < 0:
            raise ValueError("quantity cannot be negative")

        product = self.find(product_id)
        if product.inventory < quantity:
            raise ValueError("insufficient inventory")

        product.inventory -= quantity
        product.version += 1
        self._products[product_id] = product
        return Product(**vars(product))

    def update_price(self, product_id: int, price: float) -> Product:
        if price < 0:
            raise ValueError("price cannot be negative")

        product = self.find(product_id)
        product.price = price
        product.version += 1
        self._products[product_id] = product
        return Product(**vars(product))


class CachedProductService:
    """
    Cache-aside service.

    Reads check the cache first. A miss loads authoritative data and populates
    the cache. Mutations update the repository before invalidating the cache,
    preventing a failed write from unnecessarily destroying a valid entry.
    """

    def __init__(
        self,
        repository: ProductRepository,
        cache: InMemoryCache,
    ) -> None:
        self.repository = repository
        self.cache = cache

    @staticmethod
    def _key(product_id: int) -> str:
        return f"product:{product_id}"

    def get_product(self, product_id: int) -> Product:
        key = self._key(product_id)
        status, cached = self.cache.get(key)

        if status == CacheStatus.HIT:
            product = cached
            if not isinstance(product, Product):
                self.cache.delete(key)
                raise CacheError("cache contained invalid product data")
            return Product(**vars(product))

        product = self.repository.find(product_id)
        self.cache.set(
            key,
            Product(**vars(product)),
            ttl=30,
            version=product.version,
            tags={"product", f"product:{product_id}"},
        )
        return product

    def update_price(self, product_id: int, price: float) -> Product:
        product = self.repository.update_price(product_id, price)
        self.cache.delete(self._key(product_id))
        return product

    def purchase(self, product_id: int, quantity: int) -> Product:
        product = self.repository.update_inventory(product_id, quantity)
        self.cache.delete(self._key(product_id))
        return product


class DistributedNode:
    """
    Simulates one application node backed by a shared distributed cache.

    The shared cache models Redis/Memcached-like shared state without requiring
    a network dependency. A local L1 cache reduces repeated distributed reads.
    """

    def __init__(
        self,
        node_id: str,
        shared_cache: InMemoryCache,
        repository: ProductRepository,
    ) -> None:
        self.node_id = node_id
        self.l1 = InMemoryCache(capacity=50, default_ttl=2)
        self.shared = shared_cache
        self.repository = repository

    def get(self, product_id: int) -> Product:
        key = f"product:{product_id}"

        status, value = self.l1.get(key)
        if status == CacheStatus.HIT:
            return Product(**vars(value))

        status, value = self.shared.get(key)
        if status == CacheStatus.HIT:
            self.l1.set(
                key,
                Product(**vars(value)),
                ttl=2,
                version=value.version,
                tags={"product"},
            )
            return Product(**vars(value))

        product = self.repository.find(product_id)
        self.shared.set(
            key,
            Product(**vars(product)),
            ttl=30,
            version=product.version,
            tags={"product", f"product:{product_id}"},
        )
        self.l1.set(
            key,
            Product(**vars(product)),
            ttl=2,
            version=product.version,
            tags={"product"},
        )
        return product

    def invalidate(self, product_id: int) -> None:
        key = f"product:{product_id}"
        self.l1.delete(key)
        self.shared.delete(key)


class StaleWhileRevalidateCache:
    """
    Keeps a short stale window to avoid a cache stampede.

    Values past the normal TTL can be served temporarily while one refresh
    callback repopulates the key. A production implementation would coordinate
    refresh ownership with a distributed lock or lease.
    """

    def __init__(self, refresh_window: float = 10.0) -> None:
        if refresh_window <= 0:
            raise ValueError("refresh_window must be positive")
        self.refresh_window = refresh_window
        self._entries: dict[str, tuple[Any, float, float]] = {}
        self._refreshing: set[str] = set()
        self._lock = RLock()

    def put(self, key: str, value: Any, ttl: float) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        now = monotonic()
        with self._lock:
            self._entries[key] = (value, now + ttl, now + ttl + self.refresh_window)

    def get(
        self,
        key: str,
        loader: Callable[[], Any],
    ) -> tuple[Any, bool]:
        now = monotonic()

        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                value, fresh_until, stale_until = entry

                if now < fresh_until:
                    return value, False

                if now < stale_until:
                    if key not in self._refreshing:
                        self._refreshing.add(key)
                        try:
                            refreshed = loader()
                            self._entries[key] = (
                                refreshed,
                                now + 30,
                                now + 40,
                            )
                        finally:
                            self._refreshing.discard(key)
                    return value, True

                self._entries.pop(key, None)

        value = loader()
        self.put(key, value, ttl=30)
        return value, False


def stable_cache_key(namespace: str, identifier: str) -> str:
    """
    Avoid placing uncontrolled long input directly into a cache key.

    Hashing is useful when identifiers can contain arbitrary user input or
    exceed backend key-length conventions.
    """
    if not namespace or not identifier:
        raise ValueError("namespace and identifier are required")

    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def demonstrate_cache() -> None:
    print("=== In-memory cache ===")
    cache = InMemoryCache(capacity=2, default_ttl=60)

    cache.set("a", {"value": 1}, tags={"demo"})
    cache.set("b", {"value": 2}, tags={"demo"})

    print(cache.get("a"))
    cache.set("c", {"value": 3}, tags={"demo"})

    print("LRU snapshot:", cache.snapshot())
    print("b after capacity eviction:", cache.get("b"))

    print("\n=== Cache-aside product service ===")
    repository = ProductRepository()
    service = CachedProductService(repository, cache)

    first = service.get_product(101)
    second = service.get_product(101)
    print("first:", first)
    print("second:", second)
    print("stats:", cache.snapshot())

    service.update_price(101, 279.99)
    refreshed = service.get_product(101)
    print("after invalidation:", refreshed)

    try:
        service.purchase(102, 100)
    except ValueError as exc:
        print("expected failure:", exc)

    print("\n=== L1 + distributed cache ===")
    shared = InMemoryCache(capacity=100, default_ttl=60)
    node_a = DistributedNode("node-a", shared, repository)
    node_b = DistributedNode("node-b", shared, repository)

    print("node-a:", node_a.get(103))
    print("node-b:", node_b.get(103))

    changed = repository.update_price(103, 149.50)
    print("authoritative update:", changed)

    node_a.invalidate(103)
    node_b.invalidate(103)

    print("node-a refreshed:", node_a.get(103))

    print("\n=== Stale-while-revalidate ===")
    swr = StaleWhileRevalidateCache(refresh_window=2)
    calls = {"count": 0}

    def loader() -> dict[str, Any]:
        calls["count"] += 1
        return {"version": calls["count"]}

    swr.put("config", {"version": 0}, ttl=0.05)
    sleep(0.06)
    print("stale read:", swr.get("config", loader))
    print("refresh count:", calls["count"])

    print("\n=== Safe cache-key construction ===")
    print(stable_cache_key("session", "customer/123?region=IN"))

    print("\n=== Assertions ===")
    assert service.get_product(101).price == 279.99
    assert calls["count"] == 1
    assert cache.snapshot()["requests"] >= 1

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "cache-report.json"
        path.write_text(
            json.dumps(cache.snapshot(), indent=2),
            encoding="utf-8",
        )
        print("diagnostic report:", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    demonstrate_cache()
