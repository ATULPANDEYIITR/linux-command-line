from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import mimetypes
import tempfile


class StorageClass(Enum):
    STANDARD = "STANDARD"
    INFREQUENT_ACCESS = "INFREQUENT_ACCESS"
    ARCHIVE = "ARCHIVE"


class VersioningState(Enum):
    ENABLED = "ENABLED"
    SUSPENDED = "SUSPENDED"


@dataclass
class ObjectVersion:
    version_id: str
    size: int
    checksum: str
    content_type: str
    created_at: datetime
    storage_class: StorageClass
    delete_marker: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ObjectRecord:
    key: str
    versions: List[ObjectVersion] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def current_version(self) -> Optional[ObjectVersion]:
        if not self.versions:
            return None
        return self.versions[-1]


@dataclass
class LifecycleRule:
    name: str
    prefix: str
    transition_after_days: Optional[int] = None
    transition_to: Optional[StorageClass] = None
    expire_after_days: Optional[int] = None


class ObjectStorageError(Exception):
    pass


class BucketNotFound(ObjectStorageError):
    pass


class BucketAlreadyExists(ObjectStorageError):
    pass


class ObjectNotFound(ObjectStorageError):
    pass


class InvalidOperation(ObjectStorageError):
    pass


class Bucket:
    def __init__(
        self,
        name: str,
        region: str,
        versioning: VersioningState = VersioningState.ENABLED,
    ):
        if not name or len(name) < 3:
            raise ValueError("Bucket names must contain at least three characters.")
        self.name = name
        self.region = region
        self.versioning = versioning
        self.objects: Dict[str, ObjectRecord] = {}
        self.lifecycle_rules: List[LifecycleRule] = []

    def add_lifecycle_rule(self, rule: LifecycleRule) -> None:
        if rule.transition_after_days is not None:
            if rule.transition_after_days < 0 or rule.transition_to is None:
                raise ValueError("A transition rule requires a non-negative age and target class.")
        if rule.expire_after_days is not None and rule.expire_after_days < 0:
            raise ValueError("Expiration age cannot be negative.")
        self.lifecycle_rules.append(rule)

    def put_object(
        self,
        key: str,
        content: bytes,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ObjectVersion:
        if not key or key.startswith("/"):
            raise ValueError("Object keys must be non-empty relative paths.")

        now = now or datetime.now(timezone.utc)
        metadata = dict(metadata or {})
        content_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"

        checksum = sha256(content).hexdigest()
        version_id = sha256(
            f"{self.name}:{key}:{checksum}:{now.timestamp()}".encode()
        ).hexdigest()[:16]

        if self.versioning == VersioningState.SUSPENDED:
            existing = self.objects.get(key)
            if existing:
                existing.versions.clear()

        record = self.objects.setdefault(key, ObjectRecord(key=key))
        version = ObjectVersion(
            version_id=version_id,
            size=len(content),
            checksum=checksum,
            content_type=content_type,
            created_at=now,
            storage_class=StorageClass.STANDARD,
            metadata=metadata,
        )
        record.metadata = metadata
        record.versions.append(version)
        return version

    def delete_object(
        self,
        key: str,
        version_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> None:
        record = self.objects.get(key)
        if record is None:
            raise ObjectNotFound(key)

        if version_id:
            before = len(record.versions)
            record.versions = [
                version for version in record.versions
                if version.version_id != version_id
            ]
            if len(record.versions) == before:
                raise ObjectNotFound(f"{key}@{version_id}")
            if not record.versions:
                del self.objects[key]
            return

        if self.versioning == VersioningState.ENABLED:
            now = now or datetime.now(timezone.utc)
            marker = ObjectVersion(
                version_id=sha256(
                    f"delete:{self.name}:{key}:{now.timestamp()}".encode()
                ).hexdigest()[:16],
                size=0,
                checksum=sha256(b"").hexdigest(),
                content_type="application/x-delete-marker",
                created_at=now,
                storage_class=StorageClass.STANDARD,
                delete_marker=True,
            )
            record.versions.append(marker)
        else:
            del self.objects[key]

    def get_object(self, key: str, version_id: Optional[str] = None) -> ObjectVersion:
        record = self.objects.get(key)
        if record is None:
            raise ObjectNotFound(key)

        if version_id:
            for version in record.versions:
                if version.version_id == version_id:
                    if version.delete_marker:
                        raise ObjectNotFound(f"{key} is deleted in version {version_id}")
                    return version
            raise ObjectNotFound(f"{key}@{version_id}")

        current = record.current_version
        if current is None or current.delete_marker:
            raise ObjectNotFound(key)
        return current

    def list_objects(self, prefix: str = "") -> List[Tuple[str, str, int]]:
        result = []
        for key, record in self.objects.items():
            if not key.startswith(prefix):
                continue
            current = record.current_version
            if current and not current.delete_marker:
                result.append((key, current.version_id, current.size))
        return sorted(result)

    def apply_lifecycle(self, now: datetime) -> List[str]:
        actions: List[str] = []

        for key, record in list(self.objects.items()):
            for version in list(record.versions):
                if version.delete_marker:
                    continue

                age_days = (now - version.created_at).total_seconds() / 86400

                for rule in self.lifecycle_rules:
                    if not key.startswith(rule.prefix):
                        continue

                    if (
                        rule.transition_after_days is not None
                        and rule.transition_to is not None
                        and age_days >= rule.transition_after_days
                        and version.storage_class != rule.transition_to
                    ):
                        version.storage_class = rule.transition_to
                        actions.append(
                            f"transition {key}@{version.version_id} -> "
                            f"{rule.transition_to.value}"
                        )

                    if (
                        rule.expire_after_days is not None
                        and age_days >= rule.expire_after_days
                    ):
                        record.versions.remove(version)
                        actions.append(f"expire {key}@{version.version_id}")
                        break

            if not record.versions:
                del self.objects[key]

        return actions


class ObjectStorageService:
    """
    A simplified object-storage control plane.

    The control plane manages bucket names, metadata, versions, and policies.
    Object bytes are represented by metadata in this simulation. A production
    object store separates metadata/control operations from durable data
    placement across storage nodes.
    """

    def __init__(self):
        self.buckets: Dict[str, Bucket] = {}

    def create_bucket(self, name: str, region: str) -> Bucket:
        if name in self.buckets:
            raise BucketAlreadyExists(name)
        bucket = Bucket(name=name, region=region)
        self.buckets[name] = bucket
        return bucket

    def get_bucket(self, name: str) -> Bucket:
        try:
            return self.buckets[name]
        except KeyError as exc:
            raise BucketNotFound(name) from exc

    def delete_bucket(self, name: str) -> None:
        bucket = self.get_bucket(name)
        if bucket.objects:
            raise InvalidOperation("A non-empty bucket cannot be deleted.")
        del self.buckets[name]


def demonstrate_local_object_storage() -> None:
    storage = ObjectStorageService()
    bucket = storage.create_bucket("analytics-archive", "ap-south-1")

    bucket.add_lifecycle_rule(
        LifecycleRule(
            name="archive-logs",
            prefix="logs/",
            transition_after_days=30,
            transition_to=StorageClass.INFREQUENT_ACCESS,
            expire_after_days=365,
        )
    )

    bucket.add_lifecycle_rule(
        LifecycleRule(
            name="archive-reports",
            prefix="reports/",
            transition_after_days=90,
            transition_to=StorageClass.ARCHIVE,
        )
    )

    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    first = bucket.put_object(
        "reports/quarterly.csv",
        b"region,revenue\nnorth,120000\nsouth,98000\n",
        metadata={"department": "finance", "classification": "internal"},
        content_type="text/csv",
        now=base_time,
    )

    second = bucket.put_object(
        "reports/quarterly.csv",
        b"region,revenue\nnorth,125000\nsouth,103000\n",
        metadata={"department": "finance", "classification": "internal"},
        content_type="text/csv",
        now=base_time + timedelta(days=10),
    )

    bucket.put_object(
        "logs/api-2026-01-01.json",
        b'{"request_id":"r-100","status":200}',
        metadata={"service": "api", "environment": "production"},
        content_type="application/json",
        now=base_time,
    )

    print("=== Bucket metadata ===")
    print(bucket.name, bucket.region, bucket.versioning.value)

    print("\n=== Current objects ===")
    for key, version_id, size in bucket.list_objects():
        print(f"{key}: version={version_id}, size={size} bytes")

    print("\n=== Version history ===")
    report = bucket.objects["reports/quarterly.csv"]
    for version in report.versions:
        print(
            version.version_id,
            version.created_at.date(),
            version.storage_class.value,
            version.size,
        )

    print("\n=== Explicit version retrieval ===")
    restored = bucket.get_object("reports/quarterly.csv", first.version_id)
    print(
        f"Retrieved old version {restored.version_id}; "
        f"checksum={restored.checksum}"
    )

    print("\n=== Lifecycle execution ===")
    lifecycle_time = base_time + timedelta(days=100)
    for action in bucket.apply_lifecycle(lifecycle_time):
        print(action)

    print("\n=== Current storage classes ===")
    for key, record in bucket.objects.items():
        current = record.current_version
        if current and not current.delete_marker:
            print(key, current.storage_class.value)

    print("\n=== Version-aware deletion ===")
    bucket.delete_object("reports/quarterly.csv", version_id=first.version_id)
    remaining = bucket.objects["reports/quarterly.csv"].versions
    print("Remaining versions:", [version.version_id for version in remaining])

    print("\n=== Metadata integrity check ===")
    current = bucket.get_object("reports/quarterly.csv")
    assert current.content_type == "text/csv"
    assert current.size > 0
    print("Content type:", current.content_type)
    print("SHA-256:", current.checksum)

    print("\n=== File-backed object example ===")
    with tempfile.TemporaryDirectory() as temporary_directory:
        source = Path(temporary_directory) / "deployment.json"
        source.write_text(
            '{"service":"billing","release":"2026.10.16"}',
            encoding="utf-8",
        )
        file_bytes = source.read_bytes()
        uploaded = bucket.put_object(
            "deployments/deployment.json",
            file_bytes,
            metadata={"source": "release-pipeline"},
            now=base_time + timedelta(days=100),
        )
        print(
            f"Uploaded {source.name}: "
            f"{uploaded.size} bytes, checksum={uploaded.checksum}"
        )


def demonstrate_failure_conditions() -> None:
    print("\n=== Failure conditions ===")
    storage = ObjectStorageService()
    bucket = storage.create_bucket("security-audit", "ap-south-1")

    try:
        bucket.get_object("missing.txt")
    except ObjectNotFound as exc:
        print("Expected missing-object error:", exc)

    bucket.put_object("empty.txt", b"", now=datetime.now(timezone.utc))
    bucket.delete_object("empty.txt")

    try:
        bucket.get_object("empty.txt")
    except ObjectNotFound as exc:
        print("Expected delete-marker error:", exc)

    try:
        storage.delete_bucket(bucket.name)
    except InvalidOperation as exc:
        print("Expected non-empty bucket error:", exc)


def main() -> None:
    demonstrate_local_object_storage()
    demonstrate_failure_conditions()


if __name__ == "__main__":
    main()
