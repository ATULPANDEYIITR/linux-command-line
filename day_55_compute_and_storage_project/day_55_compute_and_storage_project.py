#!/usr/bin/env python3
"""Scalable compute and storage architecture simulator using the Python standard library."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("cloud_architecture")


class InstanceState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNHEALTHY = "unhealthy"


class ObjectState(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class BackupState(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class ArchitectureError(Exception):
    """Base exception for architecture simulation failures."""


class ValidationError(ArchitectureError):
    """Raised when a request violates a domain rule."""


class CapacityError(ArchitectureError):
    """Raised when no eligible compute capacity exists."""


@dataclass(frozen=True)
class ComputeInstance:
    instance_id: str
    zone: str
    capacity_per_second: int
    state: InstanceState = InstanceState.RUNNING
    active_connections: int = 0

    def __post_init__(self) -> None:
        if not self.instance_id.strip() or not self.zone.strip():
            raise ValidationError("Instance ID and availability zone are required.")
        if self.capacity_per_second <= 0 or self.active_connections < 0:
            raise ValidationError("Invalid instance capacity or connection count.")


@dataclass(frozen=True)
class StoredObject:
    key: str
    version: int
    content: bytes
    checksum: str
    state: ObjectState = ObjectState.ACTIVE
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def create(cls, key: str, version: int, content: bytes) -> StoredObject:
        if not key or key.startswith("/") or ".." in Path(key).parts:
            raise ValidationError("Object keys must be relative and cannot traverse paths.")
        if not isinstance(content, bytes):
            raise ValidationError("Object content must be bytes.")
        return cls(
            key=key,
            version=version,
            content=content,
            checksum=hashlib.sha256(content).hexdigest(),
        )


@dataclass(frozen=True)
class Backup:
    backup_id: str
    created_at: str
    object_versions: dict[str, int]
    object_data: dict[str, bytes]
    state: BackupState
    checksum: str


class ObjectStorage:
    """Versioned object store with atomic in-memory metadata updates."""

    def __init__(self, max_object_bytes: int = 10_000_000) -> None:
        if max_object_bytes <= 0:
            raise ValidationError("Maximum object size must be positive.")
        self.max_object_bytes = max_object_bytes
        self._objects: dict[str, list[StoredObject]] = {}
        self._lock = threading.RLock()

    def put(self, key: str, content: bytes) -> StoredObject:
        if not isinstance(content, bytes):
            raise ValidationError("Object content must be bytes.")
        if len(content) > self.max_object_bytes:
            raise ValidationError("Object exceeds configured size limit.")

        with self._lock:
            versions = self._objects.setdefault(key, [])
            obj = StoredObject.create(key, len(versions) + 1, content)
            versions.append(obj)
            logger.info("Stored object %s version %d", key, obj.version)
            return obj

    def get(self, key: str, version: int | None = None) -> StoredObject:
        with self._lock:
            versions = self._objects.get(key, [])
            if version is None:
                candidates = [o for o in versions if o.state == ObjectState.ACTIVE]
                if not candidates:
                    raise KeyError(f"Active object not found: {key}")
                return candidates[-1]

            if version < 1 or version > len(versions):
                raise KeyError(f"Object version not found: {key}@{version}")
            return versions[version - 1]

    def delete(self, key: str) -> None:
        with self._lock:
            obj = self.get(key)
            versions = self._objects[key]
            versions[-1] = StoredObject(
                key=obj.key,
                version=obj.version,
                content=obj.content,
                checksum=obj.checksum,
                state=ObjectState.DELETED,
                created_at=obj.created_at,
            )

    def snapshot(self) -> tuple[dict[str, int], dict[str, bytes]]:
        with self._lock:
            versions: dict[str, int] = {}
            data: dict[str, bytes] = {}
            for key, history in self._objects.items():
                active = [obj for obj in history if obj.state == ObjectState.ACTIVE]
                if active:
                    obj = active[-1]
                    versions[key] = obj.version
                    data[key] = obj.content
            return versions, data

    def restore(self, backup: Backup) -> None:
        if backup.state != BackupState.COMPLETED:
            raise ArchitectureError("Cannot restore an incomplete backup.")

        calculated = hashlib.sha256(
            json.dumps(backup.object_versions, sort_keys=True).encode()
            + b"".join(
                key.encode() + backup.object_data[key]
                for key in sorted(backup.object_data)
            )
        ).hexdigest()

        if calculated != backup.checksum:
            raise ArchitectureError("Backup integrity verification failed.")
        if set(backup.object_versions) != set(backup.object_data):
            raise ArchitectureError("Backup manifest does not match backup data.")

        with self._lock:
            restored: dict[str, list[StoredObject]] = {}
            for key, data in backup.object_data.items():
                version = backup.object_versions[key]
                if version < 1:
                    raise ArchitectureError("Invalid version in backup manifest.")
                restored[key] = [
                    StoredObject.create(key, version, data)
                ]
            self._objects = restored


class BackupService:
    """Creates immutable logical snapshots and verifies their manifests."""

    @staticmethod
    def create(storage: ObjectStorage) -> Backup:
        versions, data = storage.snapshot()
        digest = hashlib.sha256(
            json.dumps(versions, sort_keys=True).encode()
            + b"".join(key.encode() + data[key] for key in sorted(data))
        ).hexdigest()

        return Backup(
            backup_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            object_versions=versions,
            object_data=data,
            state=BackupState.COMPLETED,
            checksum=digest,
        )


class LoadBalancer:
    """Least-connections routing with capacity and health checks."""

    def __init__(self, instances: list[ComputeInstance]) -> None:
        self.instances = {instance.instance_id: instance for instance in instances}
        self._lock = threading.Lock()

    def route(self) -> str:
        with self._lock:
            eligible = [
                instance
                for instance in self.instances.values()
                if instance.state == InstanceState.RUNNING
                and instance.active_connections < instance.capacity_per_second
            ]
            if not eligible:
                raise CapacityError("No healthy instance has available capacity.")

            selected = min(
                eligible,
                key=lambda instance: (
                    instance.active_connections / instance.capacity_per_second,
                    instance.instance_id,
                ),
            )
            updated = ComputeInstance(
                instance_id=selected.instance_id,
                zone=selected.zone,
                capacity_per_second=selected.capacity_per_second,
                state=selected.state,
                active_connections=selected.active_connections + 1,
            )
            self.instances[selected.instance_id] = updated
            return selected.instance_id

    def release(self, instance_id: str) -> None:
        with self._lock:
            instance = self.instances.get(instance_id)
            if instance is None:
                raise KeyError(f"Unknown instance: {instance_id}")
            if instance.active_connections == 0:
                raise ValidationError("No active connection to release.")

            self.instances[instance_id] = ComputeInstance(
                instance_id=instance.instance_id,
                zone=instance.zone,
                capacity_per_second=instance.capacity_per_second,
                state=instance.state,
                active_connections=instance.active_connections - 1,
            )

    def set_state(self, instance_id: str, state: InstanceState) -> None:
        with self._lock:
            instance = self.instances[instance_id]
            self.instances[instance_id] = ComputeInstance(
                instance_id=instance.instance_id,
                zone=instance.zone,
                capacity_per_second=instance.capacity_per_second,
                state=state,
                active_connections=instance.active_connections,
            )

    def report(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(i) for i in self.instances.values()]


@dataclass(frozen=True)
class ArchitecturePolicy:
    minimum_zones: int = 2
    required_backup_count: int = 1
    maximum_object_bytes: int = 10_000_000

    def validate(
        self, instances: list[ComputeInstance], backups: list[Backup]
    ) -> list[str]:
        errors: list[str] = []
        zones = {i.zone for i in instances if i.state == InstanceState.RUNNING}

        if len(zones) < self.minimum_zones:
            errors.append("Insufficient availability-zone diversity.")

        healthy = [i for i in instances if i.state == InstanceState.RUNNING]
        if not healthy:
            errors.append("At least one running compute instance is required.")

        if sum(b.state == BackupState.COMPLETED for b in backups) < self.required_backup_count:
            errors.append("Required completed backup count has not been met.")

        if any(i.capacity_per_second <= 0 for i in instances):
            errors.append("Compute capacity must be positive.")

        return errors


def simulate_request(
    balancer: LoadBalancer,
    storage: ObjectStorage,
    request_id: str,
) -> dict[str, str]:
    """Route a request and guarantee connection release after processing."""
    instance_id = balancer.route()
    try:
        payload = storage.get("config/app.json")
        return {
            "request_id": request_id,
            "instance_id": instance_id,
            "config_checksum": payload.checksum,
            "result": "served",
        }
    finally:
        balancer.release(instance_id)


def demonstrate() -> None:
    storage = ObjectStorage(max_object_bytes=4096)
    storage.put(
        "config/app.json",
        json.dumps({"service": "catalog", "revision": 1}).encode(),
    )
    storage.put("reports/quarterly.txt", b"Revenue report: internal")

    backup = BackupService.create(storage)
    instances = [
        ComputeInstance("vm-a", "zone-a", 2),
        ComputeInstance("vm-b", "zone-b", 2),
        ComputeInstance("vm-c", "zone-c", 1),
    ]
    balancer = LoadBalancer(instances)

    policy = ArchitecturePolicy(minimum_zones=2)
    errors = policy.validate(instances, [backup])
    if errors:
        raise ArchitectureError("; ".join(errors))

    for index in range(5):
        result = simulate_request(balancer, storage, f"req-{index + 1}")
        print(json.dumps(result, sort_keys=True))

    original = storage.get("config/app.json").content
    storage.put("config/app.json", b'{"service":"catalog","revision":2}')
    assert storage.get("config/app.json", 1).content == original

    storage.delete("reports/quarterly.txt")
    try:
        storage.get("reports/quarterly.txt")
    except KeyError:
        print("Deleted object is no longer visible as the active version.")

    storage.restore(backup)
    assert storage.get("config/app.json").content == original
    assert storage.get("reports/quarterly.txt").content == b"Revenue report: internal"

    balancer.set_state("vm-a", InstanceState.UNHEALTHY)
    print("Compute health report:")
    print(json.dumps(balancer.report(), default=lambda value: value.value, indent=2))

    with tempfile.TemporaryDirectory() as directory:
        report_path = Path(directory) / "architecture-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "backup_id": backup.backup_id,
                    "backup_checksum": backup.checksum,
                    "instances": balancer.report(),
                    "policy_errors": policy.validate(instances, [backup]),
                },
                default=lambda value: value.value,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Diagnostic report created: {report_path.name}")
        assert report_path.exists()

    try:
        storage.put("../outside.txt", b"unsafe")
    except ValidationError as error:
        print(f"Rejected invalid object key: {error}")

    try:
        LoadBalancer([]).route()
    except CapacityError as error:
        print(f"Capacity failure handled: {error}")

    assert math.ceil(10 / 3) == 4
    print("Architecture simulation completed successfully.")


if __name__ == "__main__":
    demonstrate()
