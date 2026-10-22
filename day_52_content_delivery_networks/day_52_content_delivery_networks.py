from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict, defaultdict
from typing import Iterable
import time
import hashlib


class CacheStatus(Enum):
    MISS = "MISS"
    HIT = "HIT"
    STALE = "STALE"


@dataclass(frozen=True)
class Content:
    path: str
    body: bytes
    content_type: str
    cache_control: str = "public, max-age=60"

    @property
    def etag(self) -> str:
        return hashlib.sha256(self.body).hexdigest()[:16]


@dataclass
class CacheEntry:
    content: Content
    stored_at: float
    ttl: int

    def is_fresh(self, now: float) -> bool:
        return now - self.stored_at < self.ttl


class LRUCache:
    """A bounded edge cache using LRU eviction."""

    def __init__(self, capacity: int = 3):
        if capacity <= 0:
            raise ValueError("Cache capacity must be positive.")
        self.capacity = capacity
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, key: str, now: float) -> tuple[CacheStatus, Content | None]:
        entry = self._entries.get(key)
        if entry is None:
            return CacheStatus.MISS, None

        self._entries.move_to_end(key)

        if entry.is_fresh(now):
            return CacheStatus.HIT, entry.content

        return CacheStatus.STALE, entry.content

    def put(self, key: str, content: Content, ttl: int, now: float) -> None:
        self._entries[key] = CacheEntry(content, now, ttl)
        self._entries.move_to_end(key)

        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        return self._entries.pop(key, None) is not None

    def keys(self) -> list[str]:
        return list(self._entries.keys())


@dataclass
class OriginServer:
    name: str
    region: str
    latency_ms: int
    objects: dict[str, Content] = field(default_factory=dict)

    def fetch(self, path: str) -> Content:
        if path not in self.objects:
            raise FileNotFoundError(f"Origin object not found: {path}")
        return self.objects[path]


@dataclass
class EdgeLocation:
    name: str
    region: str
    cache: LRUCache
    origin: OriginServer

    def request(
        self,
        path: str,
        now: float,
        ttl: int = 60,
        allow_stale: bool = False,
    ) -> dict:
        status, content = self.cache.get(path, now)

        if status is CacheStatus.HIT:
            return {
                "edge": self.name,
                "status": status.value,
                "latency_ms": 8,
                "source": "edge-cache",
                "etag": content.etag,
            }

        if status is CacheStatus.STALE and allow_stale:
            return {
                "edge": self.name,
                "status": "STALE-SERVED",
                "latency_ms": 8,
                "source": "edge-cache",
                "etag": content.etag,
            }

        content = self.origin.fetch(path)
        self.cache.put(path, content, ttl, now)

        return {
            "edge": self.name,
            "status": status.value,
            "latency_ms": 8 + self.origin.latency_ms,
            "source": "origin",
            "etag": content.etag,
        }


class CDN:
    """
    Simple CDN model:
    client -> nearest edge -> edge cache -> origin.

    The simulation focuses on cache behavior and latency rather than
    implementing a network protocol.
    """

    def __init__(self, origin: OriginServer, edges: Iterable[EdgeLocation]):
        self.origin = origin
        self.edges = {edge.name: edge for edge in edges}

    def select_edge(self, client_region: str) -> EdgeLocation:
        regional = [
            edge for edge in self.edges.values()
            if edge.region == client_region
        ]
        if regional:
            return regional[0]

        return min(
            self.edges.values(),
            key=lambda edge: abs(
                hash(edge.region) - hash(client_region)
            ),
        )

    def fetch(
        self,
        client_region: str,
        path: str,
        now: float | None = None,
        ttl: int = 60,
    ) -> dict:
        if now is None:
            now = time.time()

        edge = self.select_edge(client_region)
        result = edge.request(path, now, ttl)
        result["client_region"] = client_region
        result["path"] = path
        return result

    def purge(self, path: str) -> int:
        removed = 0
        for edge in self.edges.values():
            if edge.cache.invalidate(path):
                removed += 1
        return removed


def build_demo_cdn() -> CDN:
    origin = OriginServer(
        name="origin-1",
        region="us-east",
        latency_ms=180,
        objects={
            "/index.html": Content(
                "/index.html",
                b"<html><body>Edge delivery demo</body></html>",
                "text/html",
                "public, max-age=60",
            ),
            "/app.js": Content(
                "/app.js",
                b"console.log('served through CDN');",
                "application/javascript",
                "public, max-age=300",
            ),
            "/private/report.json": Content(
                "/private/report.json",
                b'{"classification":"internal"}',
                "application/json",
                "private, no-store",
            ),
        },
    )

    edges = [
        EdgeLocation("delhi-edge", "asia", LRUCache(2), origin),
        EdgeLocation("frankfurt-edge", "europe", LRUCache(2), origin),
        EdgeLocation("virginia-edge", "us-east", LRUCache(2), origin),
    ]

    return CDN(origin, edges)


def validate_cacheability(content: Content) -> bool:
    """
    Private/no-store responses should not be placed into a shared CDN cache.
    """
    directives = {
        directive.strip().lower()
        for directive in content.cache_control.split(",")
    }
    return "private" not in directives and "no-store" not in directives


def run_demo() -> None:
    cdn = build_demo_cdn()
    clock = 1_000.0

    requests = [
        ("asia", "/index.html"),
        ("asia", "/index.html"),
        ("europe", "/index.html"),
        ("asia", "/app.js"),
    ]

    for region, path in requests:
        result = cdn.fetch(region, path, clock)
        print(result)

    print("\nCache state:")
    for edge in cdn.edges.values():
        print(edge.name, edge.cache.keys())

    print("\nExpiration:")
    clock += 61
    print(cdn.fetch("asia", "/index.html", clock))

    print("\nPurge:")
    print("Entries removed:", cdn.purge("/index.html"))
    print(cdn.fetch("asia", "/index.html", clock))

    print("\nCache-control validation:")
    private_object = cdn.origin.fetch("/private/report.json")
    print(
        private_object.path,
        "cacheable=",
        validate_cacheability(private_object),
    )

    print("\nEdge cache capacity / eviction:")
    for path in ("/index.html", "/app.js", "/private/report.json"):
        content = cdn.origin.fetch(path)
        if validate_cacheability(content):
            cdn.edges["asia"].cache.put(path, content, 60, clock)

    print(cdn.edges["asia"].cache.keys())


if __name__ == "__main__":
    run_demo()
