#!/usr/bin/env python3
"""
Database high availability simulator.

Models a three-voter database cluster with:
- Multiple availability zones
- Majority quorum
- Synchronous quorum acknowledgements
- Asynchronous replica lag
- Safe automatic failover
- Primary fencing
- Replica recovery and rejoining
- Failover eligibility evaluation
- An in-memory audit trail

The simulator models control-plane decisions. It does not configure physical
database replication or replace a production database orchestration system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Optional


class Role(str, Enum):
    PRIMARY = "primary"
    REPLICA = "replica"


class NodeState(str, Enum):
    HEALTHY = "healthy"
    SUSPECT = "suspect"
    DOWN = "down"
    FENCED = "fenced"


class HAError(Exception):
    """Base exception for cluster operations."""


class QuorumError(HAError):
    """Raised when the cluster cannot establish a majority."""


class UnsafePromotionError(HAError):
    """Raised when no replica is safe to promote."""


@dataclass(slots=True)
class Node:
    node_id: str
    zone: str
    role: Role
    priority: int
    voter: bool = True
    reachable: bool = True
    state: NodeState = NodeState.HEALTHY
    fenced: bool = False
    applied_index: int = 0
    replication_lag_ms: int = 0

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("Node identifier cannot be empty.")
        if not self.zone.strip():
            raise ValueError("Availability zone cannot be empty.")
        if self.priority < 0:
            raise ValueError("Node priority cannot be negative.")
        if self.applied_index < 0 or self.replication_lag_ms < 0:
            raise ValueError("Replication values cannot be negative.")
        if self.fenced and self.role == Role.PRIMARY:
            raise ValueError("A fenced node cannot be primary.")
        if self.state == NodeState.DOWN and self.reachable:
            raise ValueError("A down node cannot be reachable.")

    @property
    def is_live_voter(self) -> bool:
        return (
            self.voter
            and self.reachable
            and self.state == NodeState.HEALTHY
            and not self.fenced
        )


@dataclass(frozen=True, slots=True)
class HAPolicy:
    expected_voters: int = 3
    synchronous_replica_acks: int = 1
    maximum_replication_lag_ms: int = 500
    minimum_live_zones: int = 2

    def __post_init__(self) -> None:
        if self.expected_voters < 3 or self.expected_voters % 2 == 0:
            raise ValueError("Expected voters must be an odd number of at least three.")
        if not 1 <= self.synchronous_replica_acks < self.expected_voters:
            raise ValueError("Invalid synchronous acknowledgement requirement.")
        if self.maximum_replication_lag_ms < 0:
            raise ValueError("Maximum replication lag cannot be negative.")
        if not 1 <= self.minimum_live_zones <= self.expected_voters:
            raise ValueError("Invalid minimum live-zone requirement.")

    @property
    def quorum(self) -> int:
        return self.expected_voters // 2 + 1


@dataclass(frozen=True, slots=True)
class FailoverDecision:
    eligible: bool
    candidate_id: Optional[str]
    live_voters: int
    live_zones: int
    reason: str


@dataclass
class HACluster:
    cluster_id: str
    nodes: dict[str, Node]
    policy: HAPolicy = field(default_factory=HAPolicy)
    commit_index: int = 0
    term: int = 1
    primary_id: str = ""
    audit_log: list[dict[str, object]] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def __post_init__(self) -> None:
        if not self.cluster_id.strip():
            raise ValueError("Cluster identifier cannot be empty.")
        if len(self.nodes) != self.policy.expected_voters:
            raise ValueError("Node count must match the configured voter count.")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("Duplicate node identifiers.")
        if any(key != node.node_id for key, node in self.nodes.items()):
            raise ValueError("Node dictionary keys must match node identifiers.")

        primaries = [node for node in self.nodes.values() if node.role == Role.PRIMARY]
        if len(primaries) != 1:
            raise ValueError("A cluster must start with exactly one primary.")

        self.primary_id = primaries[0].node_id
        if not all(node.voter for node in self.nodes.values()):
            raise ValueError("This simulator requires all configured nodes to vote.")
        self._record("cluster_initialized", primary=self.primary_id)

    def _record(self, event: str, **details: object) -> None:
        self.audit_log.append(
            {
                "event": event,
                "cluster_id": self.cluster_id,
                "term": self.term,
                "commit_index": self.commit_index,
                **details,
            }
        )

    def _live_voters(self) -> list[Node]:
        return [node for node in self.nodes.values() if node.is_live_voter]

    def _primary(self) -> Node:
        try:
            return self.nodes[self.primary_id]
        except KeyError as exc:
            raise HAError("Configured primary does not exist.") from exc

    def commit_write(self, payload: str) -> int:
        """Commit a write only after a majority of voters can acknowledge it."""
        if not isinstance(payload, str) or not payload.strip():
            raise ValueError("Write payload must be a non-empty string.")
        if len(payload.encode("utf-8")) > 4096:
            raise ValueError("Write payload exceeds the 4096-byte limit.")

        with self._lock:
            primary = self._primary()
            if not primary.is_live_voter or primary.role != Role.PRIMARY:
                raise HAError("The current primary is not operational.")

            live = self._live_voters()
            if len(live) < self.policy.quorum:
                raise QuorumError("Write rejected: majority quorum is unavailable.")

            required_acks = max(
                self.policy.synchronous_replica_acks,
                self.policy.quorum - 1,
            )
            replicas = sorted(
                (
                    node
                    for node in live
                    if node.node_id != self.primary_id and node.role == Role.REPLICA
                ),
                key=lambda node: (node.priority, node.node_id),
            )

            if len(replicas) < required_acks:
                raise QuorumError("Not enough healthy replicas for synchronous acknowledgement.")

            self.commit_index += 1
            primary.applied_index = self.commit_index
            primary.replication_lag_ms = 0

            # Only the configured acknowledgement set is synchronous.
            # Other healthy replicas may remain behind until replication catches up.
            acknowledged = replicas[:required_acks]
            acknowledged_ids = {node.node_id for node in acknowledged}

            for replica in acknowledged:
                replica.applied_index = self.commit_index
                replica.replication_lag_ms = 0

            for replica in replicas[required_acks:]:
                replica.replication_lag_ms += 100

            self._record(
                "write_committed",
                acknowledged_nodes=sorted(acknowledged_ids),
            )
            return self.commit_index

    def replicate(self, replica_id: str) -> None:
        """Catch up a healthy replica to the current committed position."""
        with self._lock:
            replica = self.nodes.get(replica_id)
            if replica is None:
                raise HAError(f"Unknown node: {replica_id}")
            if replica_id == self.primary_id or replica.role != Role.REPLICA:
                raise HAError("Replication target must be a replica.")
            if not replica.is_live_voter:
                raise HAError("Replication target is not operational.")

            replica.applied_index = self.commit_index
            replica.replication_lag_ms = 0
            self._record("replica_caught_up", node_id=replica_id)

    def mark_down(self, node_id: str) -> None:
        with self._lock:
            node = self.nodes.get(node_id)
            if node is None:
                raise HAError(f"Unknown node: {node_id}")
            if node.fenced:
                raise HAError("A fenced node must be rebuilt before recovery.")

            node.state = NodeState.DOWN
            node.reachable = False
            self._record("node_down", node_id=node_id)

    def evaluate_failover(self) -> FailoverDecision:
        """Evaluate promotion without changing cluster state."""
        with self._lock:
            live = self._live_voters()
            live_zones = len({node.zone for node in live})
            primary = self._primary()

            if primary.is_live_voter:
                return FailoverDecision(
                    False, None, len(live), live_zones,
                    "Current primary is healthy.",
                )

            if len(live) < self.policy.quorum:
                return FailoverDecision(
                    False, None, len(live), live_zones,
                    "Majority quorum is unavailable.",
                )

            if live_zones < self.policy.minimum_live_zones:
                return FailoverDecision(
                    False, None, len(live), live_zones,
                    "Insufficient live availability zones.",
                )

            candidates = [
                node
                for node in live
                if node.role == Role.REPLICA
                and node.applied_index >= self.commit_index
                and node.replication_lag_ms <= self.policy.maximum_replication_lag_ms
            ]

            if not candidates:
                return FailoverDecision(
                    False, None, len(live), live_zones,
                    "No replica has all committed writes within the lag policy.",
                )

            candidates.sort(
                key=lambda node: (
                    -node.applied_index,
                    node.priority,
                    node.node_id,
                )
            )
            return FailoverDecision(
                True, candidates[0].node_id, len(live), live_zones,
                "Quorum, zone diversity, fencing conditions, and replication state are valid.",
            )

    def failover(self) -> str:
        """Fence the old primary before promoting a fully caught-up replica."""
        with self._lock:
            decision = self.evaluate_failover()
            if not decision.eligible or decision.candidate_id is None:
                raise UnsafePromotionError(decision.reason)

            old_primary = self._primary()
            candidate = self.nodes[decision.candidate_id]

            # Fencing prevents the former primary from accepting writes if it recovers.
            old_primary.role = Role.REPLICA
            old_primary.state = NodeState.FENCED
            old_primary.fenced = True
            old_primary.reachable = False

            candidate.role = Role.PRIMARY
            candidate.state = NodeState.HEALTHY
            candidate.fenced = False
            candidate.reachable = True

            self.primary_id = candidate.node_id
            self.term += 1

            self._record(
                "automatic_failover",
                old_primary=old_primary.node_id,
                new_primary=candidate.node_id,
                candidate_applied_index=candidate.applied_index,
            )
            return candidate.node_id

    def rejoin_as_replica(self, node_id: str) -> None:
        """Rebuild and synchronize a former primary as a replica."""
        with self._lock:
            node = self.nodes.get(node_id)
            if node is None:
                raise HAError(f"Unknown node: {node_id}")
            if node_id == self.primary_id:
                raise HAError("The active primary cannot rejoin as a replica.")

            node.role = Role.REPLICA
            node.state = NodeState.HEALTHY
            node.fenced = False
            node.reachable = True
            node.applied_index = self.commit_index
            node.replication_lag_ms = 0
            self._record("node_rejoined_as_replica", node_id=node_id)

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "cluster_id": self.cluster_id,
                "primary": self.primary_id,
                "term": self.term,
                "commit_index": self.commit_index,
                "quorum_required": self.policy.quorum,
                "live_voters": len(self._live_voters()),
                "nodes": {
                    node_id: {
                        "zone": node.zone,
                        "role": node.role.value,
                        "state": node.state.value,
                        "applied_index": node.applied_index,
                        "lag_ms": node.replication_lag_ms,
                        "fenced": node.fenced,
                    }
                    for node_id, node in self.nodes.items()
                },
            }


def build_cluster(cluster_id: str = "orders-production") -> HACluster:
    nodes = {
        "db-a": Node("db-a", "zone-a", Role.PRIMARY, priority=0),
        "db-b": Node("db-b", "zone-b", Role.REPLICA, priority=1),
        "db-c": Node("db-c", "zone-c", Role.REPLICA, priority=2),
    }
    return HACluster(cluster_id, nodes, HAPolicy())


def demonstrate_safe_failover() -> None:
    cluster = build_cluster()

    # db-b acknowledges both writes; db-c remains an asynchronous replica.
    cluster.commit_write("order-1001")
    cluster.commit_write("order-1002")

    print("Before failure:")
    print(cluster.status())

    cluster.mark_down("db-a")
    decision = cluster.evaluate_failover()
    print("\nFailover evaluation:")
    print(decision)

    new_primary = cluster.failover()
    assert new_primary == "db-b"
    assert cluster.nodes["db-a"].fenced
    assert cluster.nodes["db-b"].role == Role.PRIMARY
    assert cluster.nodes["db-b"].applied_index == cluster.commit_index

    # The former primary is rebuilt and rejoined as a replica.
    cluster.rejoin_as_replica("db-a")
    assert cluster.nodes["db-a"].role == Role.REPLICA
    assert not cluster.nodes["db-a"].fenced

    print("\nAfter failover and recovery:")
    print(cluster.status())
    print("\nAudit events:")
    for event in cluster.audit_log:
        print(event)


def demonstrate_quorum_loss() -> None:
    cluster = build_cluster("quorum-loss-test")
    cluster.mark_down("db-a")
    cluster.mark_down("db-c")

    decision = cluster.evaluate_failover()
    assert not decision.eligible

    try:
        cluster.failover()
    except UnsafePromotionError as exc:
        print("\nExpected failover rejection:", exc)


def main() -> None:
    demonstrate_safe_failover()
    demonstrate_quorum_loss()


if __name__ == "__main__":
    main()
