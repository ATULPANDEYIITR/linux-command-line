#!/usr/bin/env python3
"""
Database Infrastructure Fundamentals

A self-contained simulation of database infrastructure concepts:
- database server and storage
- page-oriented storage
- transactions and ACID properties
- write-ahead logging
- checkpoints
- primary/replica replication
- synchronous and asynchronous acknowledgement
- replication lag
- availability and failover
- transaction isolation
- validation and failure handling

The implementation is intentionally a simulation rather than a replacement
for a production database engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional
import copy
import hashlib
import json
import time


class TransactionState(Enum):
    ACTIVE = auto()
    COMMITTED = auto()
    ABORTED = auto()


class ReplicationMode(Enum):
    ASYNCHRONOUS = auto()
    SYNCHRONOUS = auto()


class ServerRole(Enum):
    PRIMARY = auto()
    REPLICA = auto()


class StorageError(Exception):
    """Raised when storage cannot safely complete an operation."""


class TransactionError(Exception):
    """Raised for invalid transaction state transitions."""


class ReplicationError(Exception):
    """Raised for replication failures."""


@dataclass(frozen=True)
class LogRecord:
    lsn: int
    transaction_id: int
    operation: str
    key: str
    value: Optional[dict[str, Any]]
    checksum: str

    @staticmethod
    def create(
        lsn: int,
        transaction_id: int,
        operation: str,
        key: str,
        value: Optional[dict[str, Any]],
    ) -> "LogRecord":
        payload = {
            "lsn": lsn,
            "transaction_id": transaction_id,
            "operation": operation,
            "key": key,
            "value": value,
        }
        checksum = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return LogRecord(
            lsn=lsn,
            transaction_id=transaction_id,
            operation=operation,
            key=key,
            value=copy.deepcopy(value),
            checksum=checksum,
        )


@dataclass
class StoragePage:
    page_id: int
    capacity: int = 4
    records: Dict[str, dict[str, Any]] = field(default_factory=dict)

    def has_space(self, key: str) -> bool:
        return key in self.records or len(self.records) < self.capacity

    def put(self, key: str, value: dict[str, Any]) -> None:
        if not self.has_space(key):
            raise StorageError(f"Page {self.page_id} is full")
        self.records[key] = copy.deepcopy(value)

    def delete(self, key: str) -> None:
        self.records.pop(key, None)


class StorageEngine:
    """
    Simple page-oriented storage engine.

    A real engine normally adds buffer pools, indexes, free-space management,
    crash recovery, checksums, background flushing, and durable I/O.
    """

    def __init__(self, page_capacity: int = 4) -> None:
        if page_capacity < 1:
            raise ValueError("page_capacity must be positive")
        self.page_capacity = page_capacity
        self.pages: List[StoragePage] = []

    def _find_page(self, key: str) -> StoragePage:
        for page in self.pages:
            if key in page.records:
                return page

        for page in self.pages:
            if page.has_space(key):
                return page

        page = StoragePage(len(self.pages), self.page_capacity)
        self.pages.append(page)
        return page

    def write(self, key: str, value: dict[str, Any]) -> None:
        if not key:
            raise StorageError("Storage key cannot be empty")
        if not isinstance(value, dict):
            raise StorageError("Stored value must be a dictionary")
        self._find_page(key).put(key, value)

    def delete(self, key: str) -> None:
        for page in self.pages:
            if key in page.records:
                page.delete(key)
                return

    def read(self, key: str) -> Optional[dict[str, Any]]:
        for page in self.pages:
            if key in page.records:
                return copy.deepcopy(page.records[key])
        return None

    def snapshot(self) -> Dict[str, dict[str, Any]]:
        result: Dict[str, dict[str, Any]] = {}
        for page in self.pages:
            for key, value in page.records.items():
                result[key] = copy.deepcopy(value)
        return result

    def restore(self, snapshot: Dict[str, dict[str, Any]]) -> None:
        self.pages.clear()
        for key, value in snapshot.items():
            self.write(key, value)

    def page_count(self) -> int:
        return len(self.pages)


@dataclass
class Transaction:
    transaction_id: int
    state: TransactionState = TransactionState.ACTIVE
    writes: Dict[str, Optional[dict[str, Any]]] = field(default_factory=dict)

    def stage_write(self, key: str, value: Optional[dict[str, Any]]) -> None:
        if self.state is not TransactionState.ACTIVE:
            raise TransactionError("Only active transactions can be modified")
        self.writes[key] = copy.deepcopy(value)


class DatabaseServer:
    def __init__(
        self,
        name: str,
        role: ServerRole,
        page_capacity: int = 4,
    ) -> None:
        self.name = name
        self.role = role
        self.storage = StorageEngine(page_capacity)
        self.wal: List[LogRecord] = []
        self.next_lsn = 1
        self.next_transaction_id = 1
        self.committed_transactions: set[int] = set()
        self.replay_lsn = 0
        self.is_available = True
        self.lock = RLock()
        self.checkpoint_lsn = 0

    def begin(self) -> Transaction:
        self._ensure_available()
        transaction = Transaction(self.next_transaction_id)
        self.next_transaction_id += 1
        return transaction

    def read(self, key: str, transaction: Optional[Transaction] = None):
        self._ensure_available()
        if transaction and key in transaction.writes:
            return copy.deepcopy(transaction.writes[key])
        return self.storage.read(key)

    def commit(self, transaction: Transaction) -> List[LogRecord]:
        self._ensure_available()

        if self.role is not ServerRole.PRIMARY:
            raise TransactionError("Only the primary accepts application writes")

        if transaction.state is not TransactionState.ACTIVE:
            raise TransactionError("Transaction is not active")

        generated: List[LogRecord] = []

        with self.lock:
            # WAL records are generated before data pages are changed.
            for key, value in transaction.writes.items():
                operation = "DELETE" if value is None else "UPSERT"
                record = LogRecord.create(
                    self.next_lsn,
                    transaction.transaction_id,
                    operation,
                    key,
                    value,
                )
                self.next_lsn += 1
                self.wal.append(record)
                generated.append(record)

            # A transaction is applied atomically to the in-memory storage.
            backup = self.storage.snapshot()
            try:
                for record in generated:
                    if record.operation == "DELETE":
                        self.storage.delete(record.key)
                    else:
                        assert record.value is not None
                        self.storage.write(record.key, record.value)
            except Exception:
                self.storage.restore(backup)
                transaction.state = TransactionState.ABORTED
                raise

            transaction.state = TransactionState.COMMITTED
            self.committed_transactions.add(transaction.transaction_id)

        return generated

    def rollback(self, transaction: Transaction) -> None:
        if transaction.state is not TransactionState.ACTIVE:
            raise TransactionError("Only active transactions can be rolled back")
        transaction.writes.clear()
        transaction.state = TransactionState.ABORTED

    def checkpoint(self) -> None:
        self._ensure_available()
        self.checkpoint_lsn = self.wal[-1].lsn if self.wal else 0

    def crash(self) -> None:
        self.is_available = False

    def recover(self) -> None:
        """
        Recovery starts from a clean storage snapshot and replays committed
        WAL records. Real engines optimize recovery with checkpoints and
        redo/undo algorithms rather than replaying every historical record.
        """
        self.storage = StorageEngine(self.storage.page_capacity)

        committed = self.committed_transactions
        for record in self.wal:
            if record.transaction_id not in committed:
                continue
            if not self._valid_checksum(record):
                raise StorageError(f"Corrupt WAL record at LSN {record.lsn}")
            if record.operation == "DELETE":
                self.storage.delete(record.key)
            else:
                assert record.value is not None
                self.storage.write(record.key, record.value)

        self.is_available = True

    def _valid_checksum(self, record: LogRecord) -> bool:
        expected = LogRecord.create(
            record.lsn,
            record.transaction_id,
            record.operation,
            record.key,
            record.value,
        ).checksum
        return expected == record.checksum

    def _ensure_available(self) -> None:
        if not self.is_available:
            raise StorageError(f"Server {self.name} is unavailable")


class ReplicationCluster:
    """
    Primary/replica replication model.

    WAL records are queued on replicas. Synchronous replication requires the
    selected replica to acknowledge replay before the commit is reported as
    complete. Asynchronous replication allows the primary to acknowledge first.
    """

    def __init__(self, primary: DatabaseServer) -> None:
        if primary.role is not ServerRole.PRIMARY:
            raise ValueError("Cluster primary must have PRIMARY role")
        self.primary = primary
        self.replicas: List[DatabaseServer] = []
        self.mode = ReplicationMode.ASYNCHRONOUS
        self.replication_queue: Dict[str, List[LogRecord]] = {}

    def add_replica(self, replica: DatabaseServer) -> None:
        if replica.role is not ServerRole.REPLICA:
            raise ValueError("Only replica servers can be added")
        self.replicas.append(replica)
        self.replication_queue[replica.name] = []

    def commit(
        self,
        transaction: Transaction,
        required_sync_replicas: int = 0,
    ) -> None:
        records = self.primary.commit(transaction)

        for replica in self.replicas:
            self.replication_queue[replica.name].extend(records)

        if self.mode is ReplicationMode.SYNCHRONOUS:
            self.replicate_all()

            acknowledgements = sum(
                1
                for replica in self.replicas
                if replica.replay_lsn >= (records[-1].lsn if records else 0)
            )

            if acknowledgements < required_sync_replicas:
                raise ReplicationError(
                    "Synchronous replication requirement was not satisfied"
                )

    def replicate_all(self) -> None:
        for replica in self.replicas:
            if not replica.is_available:
                continue

            queue = self.replication_queue[replica.name]
            for record in queue:
                if record.lsn <= replica.replay_lsn:
                    continue

                if record.operation == "DELETE":
                    replica.storage.delete(record.key)
                else:
                    assert record.value is not None
                    replica.storage.write(record.key, record.value)

                replica.replay_lsn = record.lsn

            queue.clear()

    def replication_lag(self, replica: DatabaseServer) -> int:
        return max(0, self.primary.next_lsn - 1 - replica.replay_lsn)

    def failover(self, replica: DatabaseServer) -> DatabaseServer:
        if replica not in self.replicas:
            raise ReplicationError("Replica is not part of this cluster")
        if not replica.is_available:
            raise ReplicationError("Unavailable replica cannot become primary")

        replica.role = ServerRole.PRIMARY
        self.primary.role = ServerRole.REPLICA
        self.primary = replica
        return replica


def demonstrate_transactions(server: DatabaseServer) -> None:
    print("\nTRANSACTIONS")

    transaction = server.begin()
    transaction.stage_write(
        "account:100",
        {"owner": "Riya", "balance": 1000},
    )
    transaction.stage_write(
        "account:200",
        {"owner": "Arjun", "balance": 500},
    )
    server.commit(transaction)

    print("Committed transaction:", transaction.transaction_id)
    print("Account 100:", server.read("account:100"))

    failed = server.begin()
    failed.stage_write("account:100", {"owner": "Riya", "balance": -100})
    server.rollback(failed)
    print("Rolled-back transaction:", failed.transaction_id)


def demonstrate_wal_and_recovery(server: DatabaseServer) -> None:
    print("\nWAL AND RECOVERY")

    server.checkpoint()
    print("Checkpoint LSN:", server.checkpoint_lsn)

    transaction = server.begin()
    transaction.stage_write(
        "order:9001",
        {"customer": "C-44", "amount": 2499, "state": "PAID"},
    )
    server.commit(transaction)

    before_crash = server.read("order:9001")
    server.crash()

    try:
        server.read("order:9001")
    except StorageError as exc:
        print("Expected failure:", exc)

    server.recover()
    after_recovery = server.read("order:9001")

    print("Before crash:", before_crash)
    print("After recovery:", after_recovery)


def demonstrate_replication() -> None:
    print("\nREPLICATION AND AVAILABILITY")

    primary = DatabaseServer("db-primary", ServerRole.PRIMARY)
    replica_a = DatabaseServer("db-replica-a", ServerRole.REPLICA)
    replica_b = DatabaseServer("db-replica-b", ServerRole.REPLICA)

    cluster = ReplicationCluster(primary)
    cluster.add_replica(replica_a)
    cluster.add_replica(replica_b)

    transaction = primary.begin()
    transaction.stage_write(
        "inventory:SKU-1",
        {"quantity": 100, "warehouse": "LKO"},
    )
    cluster.commit(transaction)

    print("Primary committed inventory.")
    print("Replica A before replay:", replica_a.read("inventory:SKU-1"))
    print("Replica A lag:", cluster.replication_lag(replica_a))

    cluster.replicate_all()

    print("Replica A after replay:", replica_a.read("inventory:SKU-1"))
    print("Replica B after replay:", replica_b.read("inventory:SKU-1"))

    cluster.mode = ReplicationMode.SYNCHRONOUS

    transaction = primary.begin()
    transaction.stage_write(
        "inventory:SKU-2",
        {"quantity": 40, "warehouse": "DEL"},
    )
    cluster.commit(transaction, required_sync_replicas=2)

    print("Synchronous commit acknowledged by both replicas.")

    replica_a.crash()
    failed_transaction = primary.begin()
    failed_transaction.stage_write(
        "inventory:SKU-3",
        {"quantity": 10, "warehouse": "BOM"},
    )
    cluster.commit(failed_transaction, required_sync_replicas=1)

    promoted = cluster.failover(replica_b)
    print("Failover promoted:", promoted.name)
    print("Promoted server role:", promoted.role.name)


def demonstrate_constraints(server: DatabaseServer) -> None:
    print("\nVALIDATION")

    transaction = server.begin()
    transaction.stage_write(
        "employee:1",
        {"name": "Meera", "salary": 85000},
    )
    server.commit(transaction)

    invalid = server.begin()
    invalid.stage_write(
        "employee:2",
        {"name": "", "salary": -5},
    )

    candidate = server.read("employee:2", invalid)
    if not candidate or not candidate["name"].strip() or candidate["salary"] < 0:
        server.rollback(invalid)
        print("Rejected invalid employee record.")
    else:
        server.commit(invalid)


def main() -> None:
    print("DATABASE INFRASTRUCTURE FUNDAMENTALS")
    print("=" * 42)

    server = DatabaseServer(
        name="orders-primary",
        role=ServerRole.PRIMARY,
        page_capacity=2,
    )

    demonstrate_transactions(server)
    demonstrate_wal_and_recovery(server)
    demonstrate_replication()
    demonstrate_constraints(server)

    print("\nSTORAGE")
    print("Page count:", server.storage.page_count())
    print("Stored keys:", sorted(server.storage.snapshot().keys()))

    print("\nPERFORMANCE NOTES")
    print("- Page lookup is O(P) in this educational engine.")
    print("- Production engines use indexes to reduce lookup cost.")
    print("- WAL makes recovery possible but introduces write and I/O overhead.")
    print("- Replication improves availability but creates lag and consistency trade-offs.")

    print("\nSECURITY NOTES")
    print("- Validate values before committing application data.")
    print("- Restrict administrative failover operations.")
    print("- Protect WAL and database files from unauthorized modification.")
    print("- Use encrypted transport and authenticated replication in production.")

    assert server.read("employee:2") is None
    print("\nAssertions passed.")


if __name__ == "__main__":
    main()
