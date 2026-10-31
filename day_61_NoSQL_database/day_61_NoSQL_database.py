from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from typing import Any, Iterable
import json
import time


class DatabaseType(Enum):
    KEY_VALUE = "key-value"
    DOCUMENT = "document"
    WIDE_COLUMN = "wide-column"
    GRAPH = "graph"


class ValidationError(ValueError):
    pass


class NotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    category: str
    price: float
    tags: tuple[str, ...]


@dataclass
class DocumentStore:
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)

    def insert(self, document: dict[str, Any]) -> None:
        document_id = document.get("id")
        if not isinstance(document_id, str) or not document_id:
            raise ValidationError("Document requires a non-empty string id")
        if document_id in self.documents:
            raise ValidationError(f"Document {document_id!r} already exists")
        self.documents[document_id] = json.loads(json.dumps(document))

    def find(self, predicate) -> list[dict[str, Any]]:
        return [
            json.loads(json.dumps(doc))
            for doc in self.documents.values()
            if predicate(doc)
        ]

    def update(self, document_id: str, changes: dict[str, Any]) -> None:
        if document_id not in self.documents:
            raise NotFoundError(document_id)
        self.documents[document_id].update(changes)


@dataclass
class KeyValueStore:
    data: dict[str, Any] = field(default_factory=dict)
    expires_at: dict[str, float] = field(default_factory=dict)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        if not key or len(key) > 256:
            raise ValidationError("Key must contain 1-256 characters")
        self.data[key] = value
        if ttl_seconds is not None:
            if ttl_seconds <= 0:
                raise ValidationError("TTL must be positive")
            self.expires_at[key] = time.monotonic() + ttl_seconds
        else:
            self.expires_at.pop(key, None)

    def get(self, key: str) -> Any:
        if key not in self.data:
            raise NotFoundError(key)
        expiration = self.expires_at.get(key)
        if expiration is not None and time.monotonic() >= expiration:
            self.delete(key)
            raise NotFoundError(key)
        return self.data[key]

    def delete(self, key: str) -> None:
        self.data.pop(key, None)
        self.expires_at.pop(key, None)


@dataclass
class WideColumnStore:
    # A row key maps to sparse column families.
    rows: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def put(
        self,
        row_key: str,
        family: str,
        columns: dict[str, Any],
    ) -> None:
        if not row_key or not family:
            raise ValidationError("Row key and column family are required")
        if not columns:
            raise ValidationError("At least one column is required")
        self.rows.setdefault(row_key, {}).setdefault(family, {}).update(columns)

    def get(
        self,
        row_key: str,
        family: str,
    ) -> dict[str, Any]:
        try:
            return dict(self.rows[row_key][family])
        except KeyError as exc:
            raise NotFoundError(f"{row_key}/{family}") from exc

    def scan_family(self, family: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            (row_key, dict(families[family]))
            for row_key, families in self.rows.items()
            if family in families
        ]


@dataclass
class GraphStore:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[str, list[tuple[str, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add_node(self, node_id: str, **attributes: Any) -> None:
        if not node_id:
            raise ValidationError("Node id cannot be empty")
        if node_id in self.nodes:
            raise ValidationError(f"Node {node_id!r} already exists")
        self.nodes[node_id] = attributes

    def add_edge(self, source: str, relation: str, target: str) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise NotFoundError("Both graph endpoints must exist")
        self.edges[source].append((relation, target))

    def shortest_path(self, start: str, target: str) -> list[str] | None:
        if start not in self.nodes or target not in self.nodes:
            raise NotFoundError("Graph endpoint does not exist")

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()
            if current == target:
                return path

            for _, neighbor in self.edges.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def related_by(self, node_id: str, relation: str) -> list[str]:
        if node_id not in self.nodes:
            raise NotFoundError(node_id)
        return [
            target
            for edge_relation, target in self.edges.get(node_id, [])
            if edge_relation == relation
        ]


def choose_architecture(
    access_pattern: str,
    needs_relationship_traversal: bool,
    needs_flexible_documents: bool,
    needs_high_volume_partitioned_rows: bool,
) -> DatabaseType:
    if needs_relationship_traversal:
        return DatabaseType.GRAPH
    if needs_flexible_documents:
        return DatabaseType.DOCUMENT
    if needs_high_volume_partitioned_rows:
        return DatabaseType.WIDE_COLUMN
    if access_pattern in {"session", "cache", "counter", "token"}:
        return DatabaseType.KEY_VALUE
    raise ValidationError("No suitable architecture matched the access pattern")


def build_catalog() -> tuple[
    KeyValueStore,
    DocumentStore,
    WideColumnStore,
    GraphStore,
]:
    cache = KeyValueStore()
    catalog = DocumentStore()
    activity = WideColumnStore()
    graph = GraphStore()

    # Key-value: low-latency session state.
    cache.set(
        "session:user-1001",
        {"user_id": "user-1001", "role": "analyst"},
        ttl_seconds=3600,
    )

    # Document: variable product attributes.
    products = [
        Product(
            "p100",
            "Edge Gateway",
            "networking",
            149.50,
            ("iot", "gateway", "edge"),
        ),
        Product(
            "p200",
            "Graph Sensor",
            "telemetry",
            89.00,
            ("sensor", "graph"),
        ),
        Product(
            "p300",
            "Column Node",
            "storage",
            310.00,
            ("storage", "wide-column"),
        ),
    ]

    for product in products:
        catalog.insert(
            {
                "id": product.product_id,
                "name": product.name,
                "category": product.category,
                "price": product.price,
                "tags": list(product.tags),
                "inventory": {"available": 42},
                "attributes": {
                    "region": "asia-south",
                    "active": True,
                },
            }
        )

    catalog.update("p100", {"attributes": {"region": "asia-south", "active": True, "version": 2}})

    # Wide-column: sparse time-oriented telemetry.
    activity.put(
        "device-001",
        "telemetry",
        {"2026-10-31T11:55Z": 43.2, "2026-10-31T12:00Z": 44.1},
    )
    activity.put(
        "device-002",
        "telemetry",
        {"2026-10-31T11:55Z": 37.8, "2026-10-31T12:00Z": 38.5},
    )

    # Graph: dependencies between services.
    for node_id, kind in [
        ("api", "service"),
        ("orders", "service"),
        ("inventory", "service"),
        ("payments", "service"),
        ("inventory-db", "database"),
    ]:
        graph.add_node(node_id, kind=kind)

    graph.add_edge("api", "calls", "orders")
    graph.add_edge("orders", "calls", "inventory")
    graph.add_edge("orders", "calls", "payments")
    graph.add_edge("inventory", "reads", "inventory-db")

    return cache, catalog, activity, graph


def run_assertions() -> None:
    cache, catalog, activity, graph = build_catalog()

    assert cache.get("session:user-1001")["role"] == "analyst"

    expensive = catalog.find(
        lambda doc: doc["price"] >= 100
        and doc["attributes"]["active"] is True
    )
    assert [doc["id"] for doc in expensive] == ["p100", "p300"]

    telemetry = activity.scan_family("telemetry")
    assert len(telemetry) == 2

    path = graph.shortest_path("api", "inventory-db")
    assert path == ["api", "orders", "inventory", "inventory-db"]

    assert graph.related_by("orders", "calls") == [
        "inventory",
        "payments",
    ]

    try:
        catalog.insert({"id": "p100"})
    except ValidationError:
        pass
    else:
        raise AssertionError("Duplicate documents must be rejected")

    try:
        cache.get("missing-key")
    except NotFoundError:
        pass
    else:
        raise AssertionError("Missing key must raise NotFoundError")


def print_architecture_report() -> None:
    cases = [
        (
            "Session cache",
            choose_architecture(
                "session", False, False, False
            ),
        ),
        (
            "Product catalog",
            choose_architecture(
                "catalog", False, True, False
            ),
        ),
        (
            "Telemetry",
            choose_architecture(
                "telemetry", False, False, True
            ),
        ),
        (
            "Service dependencies",
            choose_architecture(
                "dependency graph", True, False, False
            ),
        ),
    ]

    print("NoSQL architecture selection")
    for workload, database_type in cases:
        print(f"- {workload}: {database_type.value}")


def main() -> None:
    print_architecture_report()
    run_assertions()

    cache, catalog, activity, graph = build_catalog()

    print("\nKey-value")
    print(cache.get("session:user-1001"))

    print("\nDocument")
    print(catalog.find(lambda doc: "edge" in doc["tags"]))

    print("\nWide-column")
    print(activity.scan_family("telemetry"))

    print("\nGraph")
    print("Dependency path:", graph.shortest_path("api", "inventory-db"))

    print("\nValidation and architecture checks passed.")


if __name__ == "__main__":
    main()
