#!/usr/bin/env python3

"""
Managed Database Services: operational simulation.

Models:
- Automated patching
- Backups and point-in-time recovery
- Read replicas
- Storage and compute scaling
- Health/status checks
- Failover
- Maintenance windows
- Recovery objectives
- Operational audit events

The implementation uses only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional
import hashlib
import json
import random
import uuid


class DatabaseState(Enum):
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    FAILING_OVER = "failing_over"
    DEGRADED = "degraded"
    FAILED = "failed"


class BackupType(Enum):
    FULL = "full"
    SNAPSHOT = "snapshot"
    TRANSACTION_LOG = "transaction_log"


class ReplicaState(Enum):
    CREATING = "creating"
    STREAMING = "streaming"
    LAGGING = "lagging"
    FAILED = "failed"


class ManagedDatabaseError(Exception):
    """Base operational exception."""


class ValidationError(ManagedDatabaseError):
    """Invalid configuration or operation."""


class AvailabilityError(ManagedDatabaseError):
    """Operation cannot be performed because the service is unavailable."""


@dataclass(frozen=True)
class Backup:
    backup_id: str
    created_at: datetime
    backup_type: BackupType
    size_gb: float
    checksum: str


@dataclass
class Replica:
    replica_id: str
    region: str
    state: ReplicaState = ReplicaState.CREATING
    lag_seconds: int = 0
    last_replayed_lsn: int = 0


@dataclass
class StatusCheck:
    name: str
    passed: bool
    observed_at: datetime
    message: str


@dataclass
class AuditEvent:
    event_id: str
    timestamp: datetime
    action: str
    actor: str
    result: str
    details: Dict[str, object] = field(default_factory=dict)


@dataclass
class ManagedDatabase:
    name: str
    engine: str
    engine_version: str
    region: str
    storage_gb: int
    compute_units: int
    multi_az: bool
    backup_retention_days: int
    state: DatabaseState = DatabaseState.AVAILABLE
    lsn: int = 0
    backups: List[Backup] = field(default_factory=list)
    replicas: Dict[str, Replica] = field(default_factory=dict)
    audit_log: List[AuditEvent] = field(default_factory=list)
    status_checks: List[StatusCheck] = field(default_factory=list)
    last_patch: Optional[datetime] = None
    maintenance_window_hour: int = 2

    def __post_init__(self) -> None:
        self.validate_configuration()

    def validate_configuration(self) -> None:
        if not self.name.strip():
            raise ValidationError("Database name cannot be empty.")
        if self.storage_gb < 20:
            raise ValidationError("Managed database requires at least 20 GB.")
        if self.compute_units < 1:
            raise ValidationError("Compute units must be positive.")
        if not 0 <= self.backup_retention_days <= 35:
            raise ValidationError("Backup retention must be between 0 and 35 days.")
        if not 0 <= self.maintenance_window_hour <= 23:
            raise ValidationError("Maintenance window hour must be between 0 and 23.")

    def _audit(
        self,
        action: str,
        actor: str,
        result: str,
        details: Optional[Dict[str, object]] = None,
    ) -> None:
        self.audit_log.append(
            AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=action,
                actor=actor,
                result=result,
                details=details or {},
            )
        )

    def ensure_available(self) -> None:
        if self.state not in {DatabaseState.AVAILABLE, DatabaseState.DEGRADED}:
            raise AvailabilityError(
                f"Database is {self.state.value}; operation is unavailable."
            )

    def write(self, records: int = 1) -> int:
        if records < 1:
            raise ValidationError("Records written must be positive.")
        self.ensure_available()

        self.lsn += records
        self._audit(
            "write",
            "application",
            "success",
            {"records": records, "lsn": self.lsn},
        )
        return self.lsn

    def create_backup(
        self,
        backup_type: BackupType = BackupType.SNAPSHOT,
        size_gb: Optional[float] = None,
    ) -> Backup:
        self.ensure_available()

        if size_gb is None:
            size_gb = max(1.0, self.storage_gb * 0.65)

        payload = f"{self.name}:{self.lsn}:{datetime.now(timezone.utc).isoformat()}"
        checksum = hashlib.sha256(payload.encode()).hexdigest()

        backup = Backup(
            backup_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            backup_type=backup_type,
            size_gb=round(size_gb, 2),
            checksum=checksum,
        )

        self.backups.append(backup)
        self._audit(
            "backup_created",
            "managed-service",
            "success",
            {
                "backup_id": backup.backup_id,
                "type": backup.backup_type.value,
                "size_gb": backup.size_gb,
            },
        )
        return backup

    def purge_expired_backups(self, now: Optional[datetime] = None) -> int:
        if self.backup_retention_days == 0:
            removed = len(self.backups)
            self.backups.clear()
            return removed

        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.backup_retention_days)

        original_count = len(self.backups)
        self.backups = [b for b in self.backups if b.created_at >= cutoff]
        removed = original_count - len(self.backups)

        self._audit(
            "backup_retention_cleanup",
            "managed-service",
            "success",
            {"removed": removed},
        )
        return removed

    def restore_from_backup(self, backup_id: str) -> None:
        backup = next(
            (item for item in self.backups if item.backup_id == backup_id),
            None,
        )
        if backup is None:
            raise ValidationError("Requested backup does not exist.")

        previous_state = self.state
        self.state = DatabaseState.MAINTENANCE

        try:
            self.lsn = max(self.lsn, 1)
            self._audit(
                "restore",
                "managed-service",
                "success",
                {
                    "backup_id": backup_id,
                    "backup_type": backup.backup_type.value,
                },
            )
        except Exception:
            self.state = DatabaseState.FAILED
            raise
        finally:
            if self.state != DatabaseState.FAILED:
                self.state = previous_state

    def add_replica(self, region: str) -> Replica:
        if not region.strip():
            raise ValidationError("Replica region cannot be empty.")
        if region == self.region:
            raise ValidationError("Replica must use a different region.")
        if any(r.region == region for r in self.replicas.values()):
            raise ValidationError("A replica already exists in that region.")

        replica = Replica(
            replica_id=str(uuid.uuid4()),
            region=region,
            state=ReplicaState.STREAMING,
            lag_seconds=random.randint(1, 5),
            last_replayed_lsn=self.lsn,
        )
        self.replicas[replica.replica_id] = replica

        self._audit(
            "replica_created",
            "managed-service",
            "success",
            {
                "replica_id": replica.replica_id,
                "region": region,
            },
        )
        return replica

    def replicate(self, replica_id: str, additional_lag: int = 0) -> None:
        replica = self.replicas.get(replica_id)
        if replica is None:
            raise ValidationError("Replica does not exist.")
        if replica.state == ReplicaState.FAILED:
            raise AvailabilityError("Failed replica cannot replay changes.")

        replica.lag_seconds = max(0, replica.lag_seconds + additional_lag)

        if replica.lag_seconds > 60:
            replica.state = ReplicaState.LAGGING
        else:
            replica.state = ReplicaState.STREAMING
            replica.last_replayed_lsn = self.lsn

    def scale_storage(self, new_storage_gb: int) -> None:
        if new_storage_gb < self.storage_gb:
            raise ValidationError("Storage cannot be reduced by this operation.")
        if new_storage_gb == self.storage_gb:
            return

        old = self.storage_gb
        self.storage_gb = new_storage_gb
        self._audit(
            "scale_storage",
            "operator",
            "success",
            {"old_gb": old, "new_gb": new_storage_gb},
        )

    def scale_compute(self, new_compute_units: int) -> None:
        if new_compute_units < 1:
            raise ValidationError("Compute units must be positive.")

        old = self.compute_units
        self.compute_units = new_compute_units
        self._audit(
            "scale_compute",
            "operator",
            "success",
            {"old_units": old, "new_units": new_compute_units},
        )

    def automated_patch(self, target_version: str, scheduled_hour: int) -> None:
        if scheduled_hour != self.maintenance_window_hour:
            raise ValidationError("Patch attempted outside the maintenance window.")

        if not target_version.strip():
            raise ValidationError("Target engine version cannot be empty.")

        if self.state not in {
            DatabaseState.AVAILABLE,
            DatabaseState.DEGRADED,
        }:
            raise AvailabilityError("Database cannot be patched in its current state.")

        self.state = DatabaseState.MAINTENANCE

        try:
            self.engine_version = target_version
            self.last_patch = datetime.now(timezone.utc)
            self._audit(
                "automated_patch",
                "managed-service",
                "success",
                {"engine_version": target_version},
            )
        finally:
            self.state = DatabaseState.AVAILABLE

    def failover(self) -> None:
        if not self.multi_az:
            raise AvailabilityError("Failover requires multi-AZ deployment.")

        healthy_replica = next(
            (
                replica
                for replica in self.replicas.values()
                if replica.state == ReplicaState.STREAMING
            ),
            None,
        )

        self.state = DatabaseState.FAILING_OVER

        if healthy_replica is None:
            self.state = DatabaseState.FAILED
            self._audit(
                "failover",
                "managed-service",
                "failed",
                {"reason": "no healthy replica"},
            )
            raise AvailabilityError("No healthy replica is available for failover.")

        self.region = healthy_replica.region
        self.state = DatabaseState.AVAILABLE

        self._audit(
            "failover",
            "managed-service",
            "success",
            {"new_region": self.region},
        )

    def run_health_checks(self) -> List[StatusCheck]:
        now = datetime.now(timezone.utc)

        checks = [
            StatusCheck(
                "storage_capacity",
                self.storage_gb >= 20,
                now,
                f"{self.storage_gb} GB configured",
            ),
            StatusCheck(
                "compute_capacity",
                self.compute_units >= 1,
                now,
                f"{self.compute_units} compute units configured",
            ),
            StatusCheck(
                "replication",
                all(
                    replica.state == ReplicaState.STREAMING
                    for replica in self.replicas.values()
                ),
                now,
                "All replicas are streaming" if self.replicas else "No replicas configured",
            ),
            StatusCheck(
                "service_state",
                self.state in {DatabaseState.AVAILABLE, DatabaseState.DEGRADED},
                now,
                f"Database state is {self.state.value}",
            ),
        ]

        self.status_checks = checks

        if not all(check.passed for check in checks):
            self.state = DatabaseState.DEGRADED

        self._audit(
            "health_check",
            "monitoring",
            "success",
            {"passed": sum(c.passed for c in checks), "total": len(checks)},
        )

        return checks

    def report(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "region": self.region,
            "state": self.state.value,
            "storage_gb": self.storage_gb,
            "compute_units": self.compute_units,
            "multi_az": self.multi_az,
            "lsn": self.lsn,
            "backups": len(self.backups),
            "replicas": [
                {
                    "region": replica.region,
                    "state": replica.state.value,
                    "lag_seconds": replica.lag_seconds,
                }
                for replica in self.replicas.values()
            ],
            "audit_events": len(self.audit_log),
        }


def print_json(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(value, indent=2, default=str))


def main() -> None:
    database = ManagedDatabase(
        name="orders-prod",
        engine="PostgreSQL",
        engine_version="18.0",
        region="ap-south-1",
        storage_gb=250,
        compute_units=8,
        multi_az=True,
        backup_retention_days=7,
        maintenance_window_hour=2,
    )

    database.write(120)
    backup = database.create_backup(BackupType.SNAPSHOT)

    replica = database.add_replica("ap-southeast-1")
    database.write(50)
    database.replicate(replica.replica_id)

    database.scale_storage(400)
    database.scale_compute(12)

    database.automated_patch("18.1", scheduled_hour=2)

    checks = database.run_health_checks()
    print_json(
        "Health Checks",
        [
            {
                "name": check.name,
                "passed": check.passed,
                "message": check.message,
            }
            for check in checks
        ],
    )

    database.failover()
    database.restore_from_backup(backup.backup_id)
    database.purge_expired_backups()

    print_json("Managed Database Report", database.report())

    # Explicit failure-path checks.
    try:
        database.scale_storage(100)
    except ManagedDatabaseError as exc:
        print(f"\nExpected validation failure: {exc}")

    try:
        database.automated_patch("18.2", scheduled_hour=15)
    except ManagedDatabaseError as exc:
        print(f"Expected maintenance-window failure: {exc}")

    assert database.storage_gb == 400
    assert database.engine_version == "18.1"
    assert database.state == DatabaseState.AVAILABLE


if __name__ == "__main__":
    main()
