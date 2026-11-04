#!/usr/bin/env python3
"""
Highly Available Database Infrastructure Simulator

Models:
- PostgreSQL primary and read replicas
- Health monitoring and automatic failover
- Replication lag and replica selection
- Backup scheduling and restore validation
- Read-through caching with TTL and invalidation
- Recovery point and recovery time objectives
- Infrastructure health reporting

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import statistics
import time

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("database_infrastructure")


class NodeRole(str, Enum):
    PRIMARY = "primary"
    REPLICA = "replica"


class NodeState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class InfrastructureError(Exception):
    pass


class NoHealthyNodeError(InfrastructureError):
    pass


class ReplicationError(InfrastructureError):
    pass


@dataclass
class DatabaseConfig:
    maximum_replication_lag: int = 5
    cache_ttl_seconds: int = 60
    backup_interval_minutes: int = 60
    maximum_backup_age_hours: int = 24
    required_healthy_replicas: int = 1
    read_only_replica_policy: bool = True
    recovery_point_objective_seconds: int = 300
    recovery_time_objective_seconds: int = 120

    def validate(self) -> None:
        if self.maximum_replication_lag < 0:
            raise ValueError("Replication lag cannot be negative")
        if self.cache_ttl_seconds <= 0:
            raise ValueError("Cache TTL must be positive")
        if self.backup_interval_minutes <= 0:
            raise ValueError("Backup interval must be positive")
        if self.required_healthy_replicas < 0:
            raise ValueError("Replica count cannot be negative")


@dataclass
class DatabaseNode:
    node_id: str
    host: str
    role: NodeRole
    state: NodeState = NodeState.HEALTHY
    replication_lag: int = 0
    transaction_position: int = 0
    connection_limit: int = 100
    active_connections: int = 0
    cpu_usage: float = 15.0
    memory_usage: float = 35.0
    last_heartbeat: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def is_available(self) -> bool:
        return (
            self.state == NodeState.HEALTHY
            and self.active_connections < self.connection_limit
        )

    def heartbeat(self) -> None:
        if self.state != NodeState.FAILED:
            self.last_heartbeat = datetime.now(timezone.utc)

    def acquire_connection(self) -> bool:
        if not self.is_available():
            return False
        self.active_connections += 1
        return True

    def release_connection(self) -> None:
        self.active_connections = max(0, self.active_connections - 1)


@dataclass
class Backup:
    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    transaction_position: int
    checksum: str
    size_bytes: int
    verified: bool = False
    parent_backup_id: str | None = None


@dataclass
class Metric:
    timestamp: datetime
    metric_name: str
    value: float
    node_id: str
    severity: str


class CacheEntry:
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = time.monotonic() + ttl


class ReadCache:
    """Thread-safe in-process cache with expiration and invalidation."""

    def __init__(self, ttl: int):
        from threading import RLock
        self.ttl = ttl
        self.entries: dict[str, CacheEntry] = {}
        self.lock = RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        with self.lock:
            entry = self.entries.get(key)

            if entry is None:
                self.misses += 1
                return None

            if time.monotonic() >= entry.expires_at:
                del self.entries[key]
                self.misses += 1
                return None

            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        with self.lock:
            self.entries[key] = CacheEntry(value, self.ttl)

    def invalidate(self, key: str) -> None:
        with self.lock:
            self.entries.pop(key, None)

    def clear(self) -> None:
        with self.lock:
            self.entries.clear()

    def statistics(self) -> dict[str, float | int]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "entries": len(self.entries),
            "hit_ratio": self.hits / total if total else 0.0,
        }


class BackupManager:
    """Creates and validates simulated backup artifacts."""

    def __init__(self):
        self.backups: list[Backup] = []

    def create_backup(
        self,
        primary: DatabaseNode,
        backup_type: BackupType = BackupType.FULL,
    ) -> Backup:
        if primary.role != NodeRole.PRIMARY:
            raise BackupError("Backup source must be the primary")

        if primary.state != NodeState.HEALTHY:
            raise BackupError("Cannot back up an unhealthy primary")

        parent = None

        if backup_type == BackupType.INCREMENTAL:
            full_backups = [
                b for b in self.backups
                if b.backup_type == BackupType.FULL and b.verified
            ]
            if not full_backups:
                raise BackupError("Incremental backup requires a verified full backup")
            parent = full_backups[-1].backup_id

        timestamp = datetime.now(timezone.utc)
        payload = (
            f"{primary.node_id}:{primary.transaction_position}:"
            f"{timestamp.isoformat()}:{backup_type.value}"
        )

        checksum = hashlib.sha256(payload.encode()).hexdigest()

        backup = Backup(
            backup_id=f"backup-{len(self.backups) + 1:05d}",
            backup_type=backup_type,
            timestamp=timestamp,
            transaction_position=primary.transaction_position,
            checksum=checksum,
            size_bytes=(
                1024 * 1024 * 100
                if backup_type == BackupType.FULL
                else 1024 * 1024 * 5
            ),
            verified=True,
            parent_backup_id=parent,
        )

        self.backups.append(backup)
        logger.info("Created backup %s", backup.backup_id)
        return backup

    def latest_verified(self) -> Backup | None:
        verified = [b for b in self.backups if b.verified]
        return max(verified, key=lambda b: b.timestamp) if verified else None

    def validate_retention(self, maximum_age_hours: int) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=maximum_age_hours
        )
        return [
            b.backup_id for b in self.backups
            if b.timestamp < cutoff
        ]

    def restore(
        self,
        backup_id: str,
        target: DatabaseNode,
    ) -> None:
        backup = next(
            (b for b in self.backups if b.backup_id == backup_id),
            None
        )

        if backup is None or not backup.verified:
            raise BackupError("Backup is missing or unverified")

        if backup.backup_type == BackupType.INCREMENTAL:
            parent = next(
                (
                    b for b in self.backups
                    if b.backup_id == backup.parent_backup_id
                    and b.verified
                ),
                None
            )
            if parent is None:
                raise BackupError("Required full backup is unavailable")

        target.state = NodeState.RECOVERING
        target.transaction_position = backup.transaction_position
        target.replication_lag = 0
        target.state = NodeState.HEALTHY

        logger.info(
            "Restored %s to transaction position %s",
            target.node_id,
            target.transaction_position,
        )


class BackupError(InfrastructureError):
    pass


class Monitor:
    """Collects infrastructure metrics and evaluates health thresholds."""

    def __init__(self):
        self.metrics: list[Metric] = []
        self.alerts: list[str] = []

    def collect(self, node: DatabaseNode) -> None:
        timestamp = datetime.now(timezone.utc)

        measurements = {
            "cpu_percent": node.cpu_usage,
            "memory_percent": node.memory_usage,
            "replication_lag": float(node.replication_lag),
            "active_connections": float(node.active_connections),
        }

        for name, value in measurements.items():
            severity = "normal"

            if name == "cpu_percent" and value >= 85:
                severity = "critical"
            elif name == "memory_percent" and value >= 90:
                severity = "critical"
            elif name == "replication_lag" and value > 5:
                severity = "warning"
            elif name == "active_connections" and value >= node.connection_limit:
                severity = "critical"

            metric = Metric(
                timestamp, name, value, node.node_id, severity
            )
            self.metrics.append(metric)

            if severity != "normal":
                alert = f"{node.node_id}: {name}={value} ({severity})"
                self.alerts.append(alert)
                logger.warning(alert)

    def node_health(self, nodes: list[DatabaseNode]) -> dict[str, Any]:
        return {
            node.node_id: {
                "state": node.state.value,
                "role": node.role.value,
                "replication_lag": node.replication_lag,
                "connections": node.active_connections,
                "cpu": node.cpu_usage,
                "memory": node.memory_usage,
            }
            for node in nodes
        }


class DatabaseCluster:
    """Manages primary selection, replicas and simulated failover."""

    def __init__(
        self,
        nodes: list[DatabaseNode],
        config: DatabaseConfig,
    ):
        config.validate()

        if not nodes:
            raise ValueError("Cluster requires at least one node")

        primaries = [
            n for n in nodes if n.role == NodeRole.PRIMARY
        ]

        if len(primaries) != 1:
            raise ValueError("Cluster must have exactly one primary")

        self.nodes = nodes
        self.config = config
        self.failover_history: list[dict[str, Any]] = []

    @property
    def primary(self) -> DatabaseNode:
        primaries = [
            n for n in self.nodes if n.role == NodeRole.PRIMARY
        ]
        if len(primaries) != 1:
            raise InfrastructureError("Cluster has no unique primary")
        return primaries[0]

    def healthy_replicas(self) -> list[DatabaseNode]:
        return [
            n for n in self.nodes
            if n.role == NodeRole.REPLICA
            and n.is_available()
            and n.replication_lag <= self.config.maximum_replication_lag
        ]

    def write(self, transaction_count: int = 1) -> int:
        if transaction_count <= 0:
            raise ValueError("Transaction count must be positive")

        primary = self.primary

        if not primary.is_available():
            raise NoHealthyNodeError("Primary cannot accept writes")

        if not primary.acquire_connection():
            raise NoHealthyNodeError("Primary connection limit reached")

        try:
            primary.transaction_position += transaction_count

            for replica in self.nodes:
                if replica.role == NodeRole.REPLICA:
                    if replica.state == NodeState.HEALTHY:
                        replica.replication_lag += transaction_count
                        replica.transaction_position = max(
                            0,
                            primary.transaction_position
                            - replica.replication_lag
                        )

            return primary.transaction_position
        finally:
            primary.release_connection()

    def replicate(self, replica_id: str, transactions: int) -> None:
        if transactions < 0:
            raise ValueError("Replication amount cannot be negative")

        replica = self.get_node(replica_id)

        if replica.role != NodeRole.REPLICA:
            raise ReplicationError("Target is not a replica")

        if replica.state != NodeState.HEALTHY:
            raise ReplicationError("Replica is unavailable")

        replica.replication_lag = max(
            0, replica.replication_lag - transactions
        )

        replica.transaction_position = max(
            0,
            self.primary.transaction_position - replica.replication_lag
        )

    def read_node(self) -> DatabaseNode:
        replicas = self.healthy_replicas()

        if replicas:
            return min(
                replicas,
                key=lambda n: (
                    n.replication_lag,
                    n.active_connections,
                    n.cpu_usage,
                ),
            )

        primary = self.primary

        if primary.is_available():
            return primary

        raise NoHealthyNodeError("No database node can serve reads")

    def read(self, key: str, cache: ReadCache) -> dict[str, Any]:
        cached = cache.get(key)

        if cached is not None:
            return cached

        node = self.read_node()

        if not node.acquire_connection():
            raise NoHealthyNodeError("Selected read node is saturated")

        try:
            result = {
                "key": key,
                "served_by": node.node_id,
                "transaction_position": node.transaction_position,
                "replication_lag": node.replication_lag,
            }
            cache.set(key, result)
            return result
        finally:
            node.release_connection()

    def failover(self) -> DatabaseNode:
        old_primary = self.primary
        old_primary.state = NodeState.FAILED

        candidates = self.healthy_replicas()

        if not candidates:
            raise NoHealthyNodeError(
                "Failover aborted: no eligible replica"
            )

        # Prefer the replica with the highest applied transaction position.
        promoted = max(
            candidates,
            key=lambda n: (
                n.transaction_position,
                -n.replication_lag,
            ),
        )

        promoted.role = NodeRole.PRIMARY
        promoted.replication_lag = 0

        self.failover_history.append({
            "old_primary": old_primary.node_id,
            "new_primary": promoted.node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "promoted_position": promoted.transaction_position,
        })

        logger.warning(
            "Failover: %s -> %s",
            old_primary.node_id,
            promoted.node_id,
        )

        return promoted

    def recover_old_primary(self, node_id: str) -> None:
        node = self.get_node(node_id)

        if node.role == NodeRole.PRIMARY and node.state == NodeState.HEALTHY:
            raise InfrastructureError("Node is already primary")

        if node_id == self.primary.node_id:
            raise InfrastructureError("Cannot rejoin the active primary")

        node.role = NodeRole.REPLICA
        node.state = NodeState.RECOVERING
        node.transaction_position = self.primary.transaction_position
        node.replication_lag = 0
        node.state = NodeState.HEALTHY

    def get_node(self, node_id: str) -> DatabaseNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(f"Unknown node: {node_id}")

    def evaluate_availability(self) -> dict[str, Any]:
        replicas = self.healthy_replicas()
        primary_available = self.primary.is_available()

        return {
            "primary_available": primary_available,
            "healthy_replicas": len(replicas),
            "required_replicas": self.config.required_healthy_replicas,
            "read_available": primary_available or bool(replicas),
            "write_available": primary_available,
            "replica_policy_satisfied": (
                len(replicas) >= self.config.required_healthy_replicas
            ),
        }


class Infrastructure:
    def __init__(self, config: DatabaseConfig):
        self.config = config

        self.cluster = DatabaseCluster(
            [
                DatabaseNode(
                    "db-primary", "10.0.1.10", NodeRole.PRIMARY
                ),
                DatabaseNode(
                    "db-replica-1", "10.0.1.11", NodeRole.REPLICA
                ),
                DatabaseNode(
                    "db-replica-2", "10.0.1.12", NodeRole.REPLICA
                ),
            ],
            config,
        )

        self.cache = ReadCache(config.cache_ttl_seconds)
        self.backups = BackupManager()
        self.monitor = Monitor()

    def run_health_checks(self) -> None:
        for node in self.cluster.nodes:
            self.monitor.collect(node)

    def create_backup(self) -> Backup:
        return self.backups.create_backup(self.cluster.primary)

    def report(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "availability": self.cluster.evaluate_availability(),
            "nodes": self.monitor.node_health(self.cluster.nodes),
            "cache": self.cache.statistics(),
            "backups": [
                {
                    "backup_id": b.backup_id,
                    "type": b.backup_type.value,
                    "position": b.transaction_position,
                    "verified": b.verified,
                    "timestamp": b.timestamp.isoformat(),
                }
                for b in self.backups.backups
            ],
            "alerts": self.monitor.alerts,
            "failovers": self.cluster.failover_history,
        }

    def export_report(self, filename: str) -> None:
        path = Path(filename)
        path.write_text(
            json.dumps(self.report(), indent=2),
            encoding="utf-8",
        )


def run_demo() -> None:
    config = DatabaseConfig()
    infrastructure = Infrastructure(config)

    cluster = infrastructure.cluster
    cache = infrastructure.cache

    print("\n1. Initial cluster")
    print(cluster.evaluate_availability())

    print("\n2. Writing transactions")
    cluster.write(10)
    cluster.write(5)

    print("\n3. Replicating transactions")
    cluster.replicate("db-replica-1", 12)
    cluster.replicate("db-replica-2", 10)

    print("\n4. Reading through cache")
    print(cluster.read("customer:1001", cache))
    print(cluster.read("customer:1001", cache))

    print("\n5. Creating verified backup")
    backup = infrastructure.create_backup()
    print(backup)

    print("\n6. Collecting monitoring metrics")
    infrastructure.run_health_checks()

    print("\n7. Simulating primary failure")
    cluster.primary.state = NodeState.FAILED
    promoted = cluster.failover()
    print("Promoted:", promoted.node_id)

    print("\n8. Restoring old primary as replica")
    cluster.recover_old_primary("db-primary")

    print("\n9. Validating backup")
    restored = DatabaseNode(
        "db-restore-test",
        "10.0.2.20",
        NodeRole.REPLICA,
    )
    infrastructure.backups.restore(backup.backup_id, restored)
    print("Restored position:", restored.transaction_position)

    print("\n10. Infrastructure report")
    infrastructure.run_health_checks()
    print(json.dumps(infrastructure.report(), indent=2))

    infrastructure.export_report("infrastructure_report.json")


def run_tests() -> None:
    config = DatabaseConfig()
    infrastructure = Infrastructure(config)
    cluster = infrastructure.cluster

    assert cluster.primary.node_id == "db-primary"

    position = cluster.write(10)
    assert position == 10

    cluster.replicate("db-replica-1", 10)
    assert cluster.read_node().node_id == "db-replica-1"

    cache = infrastructure.cache
    first = cluster.read("test-key", cache)
    second = cluster.read("test-key", cache)
    assert first == second
    assert cache.statistics()["hits"] == 1

    backup = infrastructure.create_backup()
    assert backup.verified

    cluster.primary.state = NodeState.FAILED
    promoted = cluster.failover()
    assert promoted.role == NodeRole.PRIMARY

    try:
        cluster.write(1)
    except NoHealthyNodeError:
        raise AssertionError("Promoted primary should accept writes")

    print("All infrastructure tests passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Highly available database infrastructure simulator"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in infrastructure tests",
    )
    parser.add_argument(
        "--report",
        default="infrastructure_report.json",
        help="Report output path",
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        run_demo()


if __name__ == "__main__":
    main()
