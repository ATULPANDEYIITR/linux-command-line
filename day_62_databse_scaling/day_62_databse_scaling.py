from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from math import ceil
from random import Random
from typing import Iterable


class ScalingMode(Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class PartitionStrategy(Enum):
    RANGE = "range"
    HASH = "hash"


class ShardStrategy(Enum):
    HASH = "hash"
    RANGE = "range"


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    amount: float
    region: str


@dataclass
class Node:
    node_id: str
    capacity: int
    used: int = 0
    healthy: bool = True

    @property
    def utilization(self) -> float:
        return self.used / self.capacity if self.capacity else 1.0

    def can_accept(self, amount: int = 1) -> bool:
        return self.healthy and self.used + amount <= self.capacity


@dataclass
class Cluster:
    nodes: list[Node] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        if any(existing.node_id == node.node_id for existing in self.nodes):
            raise ValueError(f"Duplicate node: {node.node_id}")
        if node.capacity <= 0:
            raise ValueError("Node capacity must be positive")
        self.nodes.append(node)

    def route_round_robin(self, count: int) -> list[str]:
        if count < 0:
            raise ValueError("Count cannot be negative")
        healthy = [node for node in self.nodes if node.healthy]
        if not healthy:
            raise RuntimeError("No healthy nodes available")

        selected: list[str] = []
        for index in range(count):
            node = healthy[index % len(healthy)]
            if not node.can_accept():
                raise RuntimeError(f"Capacity exhausted on {node.node_id}")
            node.used += 1
            selected.append(node.node_id)
        return selected


class VerticalScaler:
    """Models increasing resources on one database server."""

    def __init__(self, node: Node) -> None:
        self.node = node

    def resize(self, new_capacity: int) -> None:
        if new_capacity <= 0:
            raise ValueError("Capacity must be positive")
        if new_capacity < self.node.used:
            raise ValueError("New capacity cannot be below current usage")
        self.node.capacity = new_capacity


class HorizontalScaler:
    """Models adding/removing database nodes while preserving availability."""

    def __init__(self, cluster: Cluster) -> None:
        self.cluster = cluster

    def add_capacity(self, node_id: str, capacity: int) -> None:
        self.cluster.add_node(Node(node_id=node_id, capacity=capacity))

    def remove_node(self, node_id: str) -> None:
        target = next((node for node in self.cluster.nodes if node.node_id == node_id), None)
        if target is None:
            raise KeyError(node_id)
        if target.used:
            raise RuntimeError("Cannot remove a node containing active workload")
        if len(self.cluster.nodes) == 1:
            raise RuntimeError("Cannot remove the last node")
        self.cluster.nodes.remove(target)


class Partitioner:
    """Partitions logical data before sharding distributes it across machines."""

    def __init__(self, strategy: PartitionStrategy, partitions: int) -> None:
        if partitions <= 0:
            raise ValueError("Partition count must be positive")
        self.strategy = strategy
        self.partitions = partitions

    def locate(self, order: Order) -> int:
        if self.strategy is PartitionStrategy.HASH:
            digest = sha256(str(order.customer_id).encode()).digest()
            return int.from_bytes(digest[:8], "big") % self.partitions

        # Range partitioning uses customer-id intervals.
        return min(order.customer_id // 1000, self.partitions - 1)


class ShardedStore:
    def __init__(
        self,
        shard_count: int,
        strategy: ShardStrategy = ShardStrategy.HASH,
    ) -> None:
        if shard_count <= 0:
            raise ValueError("Shard count must be positive")
        self.shard_count = shard_count
        self.strategy = strategy
        self.shards: list[dict[int, Order]] = [dict() for _ in range(shard_count)]

    def shard_for(self, customer_id: int) -> int:
        if customer_id < 0:
            raise ValueError("Customer ID cannot be negative")

        if self.strategy is ShardStrategy.HASH:
            return hash(customer_id) % self.shard_count

        return min(customer_id // 1000, self.shard_count - 1)

    def insert(self, order: Order) -> int:
        shard = self.shard_for(order.customer_id)
        if order.order_id in self.shards[shard]:
            raise ValueError(f"Duplicate order ID: {order.order_id}")
        self.shards[shard][order.order_id] = order
        return shard

    def get(self, order_id: int, customer_id: int) -> Order | None:
        shard = self.shard_for(customer_id)
        return self.shards[shard].get(order_id)

    def rebalance(self, new_shard_count: int) -> "ShardedStore":
        if new_shard_count <= self.shard_count:
            raise ValueError("This demonstration only supports scale-out")

        replacement = ShardedStore(new_shard_count, self.strategy)
        for shard in self.shards:
            for order in shard.values():
                replacement.insert(order)
        return replacement

    def distribution(self) -> list[int]:
        return [len(shard) for shard in self.shards]


def estimate_vertical_capacity(current_capacity: int, growth: float) -> int:
    if current_capacity <= 0:
        raise ValueError("Current capacity must be positive")
    if growth < 0:
        raise ValueError("Growth cannot be negative")
    return ceil(current_capacity * (1 + growth))


def generate_orders(count: int, seed: int = 42) -> list[Order]:
    if count < 0:
        raise ValueError("Count cannot be negative")

    random = Random(seed)
    regions = ["north", "south", "east", "west"]
    return [
        Order(
            order_id=index,
            customer_id=random.randint(1, 9999),
            amount=round(random.uniform(10, 5000), 2),
            region=regions[index % len(regions)],
        )
        for index in range(1, count + 1)
    ]


def print_cluster(cluster: Cluster) -> None:
    for node in cluster.nodes:
        print(
            f"{node.node_id}: capacity={node.capacity}, "
            f"used={node.used}, utilization={node.utilization:.1%}, "
            f"healthy={node.healthy}"
        )


def main() -> None:
    print("DATABASE SCALING CASE STUDY")

    # Vertical scaling: one database server receives more capacity.
    primary = Node("db-primary", capacity=100, used=72)
    vertical = VerticalScaler(primary)
    new_capacity = estimate_vertical_capacity(primary.capacity, 0.50)
    vertical.resize(new_capacity)

    print("\n1. Vertical scaling")
    print_cluster(Cluster([primary]))

    # Horizontal scaling: workload is spread over multiple database nodes.
    cluster = Cluster()
    horizontal = HorizontalScaler(cluster)
    horizontal.add_capacity("db-01", 50)
    horizontal.add_capacity("db-02", 50)
    horizontal.add_capacity("db-03", 50)
    horizontal.add_capacity("db-04", 50)
    assignments = cluster.route_round_robin(120)

    print("\n2. Horizontal scaling")
    print_cluster(cluster)
    print(f"Assigned requests: {len(assignments)}")

    # Partitioning divides logical rows into independently manageable groups.
    orders = generate_orders(100)
    partitioner = Partitioner(PartitionStrategy.HASH, partitions=8)
    partition_counts = [0] * partitioner.partitions
    for order in orders:
        partition_counts[partitioner.locate(order)] += 1

    print("\n3. Partitioning")
    print(f"Partition distribution: {partition_counts}")

    # Sharding distributes partitions across independent database machines.
    store = ShardedStore(shard_count=4, strategy=ShardStrategy.HASH)
    for order in orders:
        store.insert(order)

    print("\n4. Sharding")
    print(f"Initial shard distribution: {store.distribution()}")

    target = orders[25]
    found = store.get(target.order_id, target.customer_id)
    assert found == target
    print(f"Point lookup order {target.order_id}: found")

    # Adding shards requires redistribution. The example explicitly rebuilds
    # the placement map so that every row receives its new shard assignment.
    expanded = store.rebalance(8)
    print(f"After scale-out: {expanded.distribution()}")

    # Failure handling: an unhealthy node is excluded from new placement.
    cluster.nodes[0].healthy = False
    try:
        cluster.route_round_robin(1)
    except RuntimeError as exc:
        print(f"Expected capacity/failure condition: {exc}")

    # Security-sensitive identifiers should not be exposed in diagnostic output.
    safe_lookup = expanded.get(target.order_id, target.customer_id)
    print(f"Validated lookup amount: {safe_lookup.amount:.2f}")

    # Basic invariants act as executable regression checks.
    assert sum(store.distribution()) == len(orders)
    assert sum(expanded.distribution()) == len(orders)
    assert primary.capacity == 150
    assert len(cluster.nodes) == 4

    print("\nScaling model completed successfully.")


if __name__ == "__main__":
    main()
