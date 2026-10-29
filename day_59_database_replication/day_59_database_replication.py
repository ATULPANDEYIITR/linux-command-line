#!/usr/bin/env python3
"""
Database replication learning model.

Models:
- primary-replica topology
- synchronous and asynchronous replication
- write-ahead log positions
- replication lag
- replica promotion and failover
- read routing
- stale replica detection
- recovery after primary failure

The model is deliberately deterministic so that failure cases can be
observed without external database dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import time


class ReplicationMode(Enum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"


class NodeRole(Enum):
    PRIMARY = "primary"
    REPLICA = "replica"
    OFFLINE = "offline"


class ReplicationError(Exception):
    """Base exception for replication failures."""


class NoPrimaryError(ReplicationError):
    """Raised when no writable primary exists."""


class ReplicationLagError(ReplicationError):
    """Raised when a read requires a sufficiently fresh replica."""


@dataclass(frozen=True)
class WalEntry:
    position: int
    key: str
    value: str
    committed_at: float


@dataclass
class Replica:
    name: str
    mode: ReplicationMode
    role: NodeRole = NodeRole.REPLICA
    online: bool = True
    applied_position: int = 0
    pending: List[WalEntry] = field(default_factory=list)
    data: Dict[str, str] = field(default_factory=dict)

    def receive(self, entry: WalEntry) -> None:
        if not self.online:
            return
        if entry.position > self.applied_position:
            self.pending.append(entry)

    def apply_pending(self, max_entries: Optional[int] = None) -> int:
        if not self.online:
            return 0

        applied = 0
        while self.pending and (
            max_entries is None or applied < max_entries
        ):
            entry = self.pending.pop(0)
            if entry.position == self.applied_position + 1:
                self.data[entry.key] = entry.value
                self.applied_position = entry.position
                applied += 1
            elif entry.position <= self.applied_position:
                continue
            else:
                self.pending.insert(0, entry)
                break
        return applied


class ReplicationCluster:
    """Small primary-replica replication simulator."""

    def __init__(self) -> None:
        self.primary_name = "db-primary-1"
        self.nodes: Dict[str, Replica] = {
            "db-replica-sync": Replica(
                "db-replica-sync", ReplicationMode.SYNCHRONOUS
            ),
            "db-replica-async": Replica(
                "db-replica-async", ReplicationMode.ASYNCHRONOUS
            ),
        }
        self.data: Dict[str, str] = {}
        self.wal: List[WalEntry] = []
        self.next_position = 1
        self.primary_online = True

    @property
    def primary_position(self) -> int:
        return self.wal[-1].position if self.wal else 0

    def _primary_required(self) -> None:
        if not self.primary_online:
            raise NoPrimaryError("No writable primary is available.")

    def write(self, key: str, value: str) -> WalEntry:
        self._primary_required()

        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string.")
        if not isinstance(value, str):
            raise ValueError("Value must be a string.")

        entry = WalEntry(
            position=self.next_position,
            key=key,
            value=value,
            committed_at=time.time(),
        )
        self.next_position += 1
        self.wal.append(entry)
        self.data[key] = value

        for replica in self.nodes.values():
            replica.receive(entry)

        # Synchronous replication waits for the synchronous replica
        # to durably apply the current WAL entry before acknowledging.
        for replica in self.nodes.values():
            if (
                replica.mode == ReplicationMode.SYNCHRONOUS
                and replica.online
            ):
                replica.apply_pending()

        return entry

    def acknowledge_write(self, entry: WalEntry) -> bool:
        sync_replicas = [
            r
            for r in self.nodes.values()
            if r.mode == ReplicationMode.SYNCHRONOUS
        ]

        if not sync_replicas:
            return False

        return all(
            r.online and r.applied_position >= entry.position
            for r in sync_replicas
        )

    def async_tick(self, entries: Optional[int] = None) -> int:
        total = 0
        for replica in self.nodes.values():
            if replica.mode == ReplicationMode.ASYNCHRONOUS:
                total += replica.apply_pending(entries)
        return total

    def replication_status(self) -> List[dict]:
        result = []
        primary_position = self.primary_position

        for replica in self.nodes.values():
            result.append(
                {
                    "node": replica.name,
                    "mode": replica.mode.value,
                    "role": replica.role.value,
                    "online": replica.online,
                    "applied_position": replica.applied_position,
                    "lag": primary_position - replica.applied_position,
                }
            )
        return result

    def read(
        self,
        key: str,
        preferred_replica: Optional[str] = None,
        minimum_position: Optional[int] = None,
    ) -> Optional[str]:
        if preferred_replica is None:
            return self.data.get(key)

        replica = self.nodes.get(preferred_replica)
        if replica is None or not replica.online:
            raise ReplicationError("Requested replica is unavailable.")

        if (
            minimum_position is not None
            and replica.applied_position < minimum_position
        ):
            raise ReplicationLagError(
                f"{replica.name} is at WAL position "
                f"{replica.applied_position}, required {minimum_position}."
            )

        return replica.data.get(key)

    def fail_primary(self) -> None:
        self.primary_online = False

    def promote(self, replica_name: str) -> None:
        replica = self.nodes.get(replica_name)
        if replica is None:
            raise ReplicationError("Unknown replica.")
        if not replica.online:
            raise ReplicationError("Offline replica cannot be promoted.")

        # A promoted replica becomes the new writable authority.
        self.primary_name = replica.name
        self.data = dict(replica.data)

        for node in self.nodes.values():
            node.role = NodeRole.REPLICA

        replica.role = NodeRole.PRIMARY
        self.primary_online = True

    def reconnect_old_primary(self) -> None:
        """
        Rejoining an old primary requires reconciliation in a real system.
        Here it is converted to a replica and caught up from the new WAL.
        """
        if self.primary_name == "db-primary-1":
            return

        old_primary = Replica(
            "db-primary-1",
            ReplicationMode.ASYNCHRONOUS,
            role=NodeRole.REPLICA,
            online=True,
        )
        old_primary.data = dict(self.data)
        old_primary.applied_position = self.primary_position
        self.nodes["db-primary-1"] = old_primary


def demonstrate() -> None:
    cluster = ReplicationCluster()

    first = cluster.write("customer:1001", "active")
    assert cluster.acknowledge_write(first)

    cluster.write("order:5001", "paid")

    # Async replica has not necessarily applied the second transaction yet.
    stale_read_position = cluster.nodes["db-replica-async"].applied_position

    print("Initial replication status:")
    for row in cluster.replication_status():
        print(row)

    print("\nPrimary read:", cluster.read("order:5001"))

    try:
        cluster.read(
            "order:5001",
            preferred_replica="db-replica-async",
            minimum_position=cluster.primary_position,
        )
    except ReplicationLagError as exc:
        print("Expected stale-read protection:", exc)

    cluster.async_tick()

    print(
        "Async replica after catch-up:",
        cluster.read(
            "order:5001",
            preferred_replica="db-replica-async",
            minimum_position=cluster.primary_position,
        ),
    )

    # Failure and promotion.
    cluster.fail_primary()
    print("\nPrimary failed.")

    cluster.promote("db-replica-sync")
    print("Promoted:", cluster.primary_name)

    failover_write = cluster.write("customer:1001", "verified")
    print(
        "Failover write acknowledged:",
        cluster.acknowledge_write(failover_write),
    )

    # Defensive checks for invalid operations.
    try:
        cluster.nodes["db-replica-async"].online = False
        cluster.promote("db-replica-async")
    except ReplicationError as exc:
        print("Expected promotion failure:", exc)
    finally:
        cluster.nodes["db-replica-async"].online = True

    print("\nFinal replication status:")
    for row in cluster.replication_status():
        print(row)

    print("\nPreviously observed async position:", stale_read_position)


if __name__ == "__main__":
    demonstrate()
