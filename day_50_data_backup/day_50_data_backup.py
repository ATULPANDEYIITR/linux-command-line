#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


UTC = timezone.utc


class BackupError(Exception):
    """Raised when a backup operation cannot be completed safely."""


@dataclass(frozen=True)
class FileFingerprint:
    relative_path: str
    size: int
    modified_ns: int
    sha256: str


@dataclass
class BackupManifest:
    backup_id: str
    backup_type: str
    created_at: str
    source: str
    parent_backup_id: str | None
    files: dict[str, FileFingerprint] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type,
            "created_at": self.created_at,
            "source": self.source,
            "parent_backup_id": self.parent_backup_id,
            "files": {
                name: {
                    "relative_path": fp.relative_path,
                    "size": fp.size,
                    "modified_ns": fp.modified_ns,
                    "sha256": fp.sha256,
                }
                for name, fp in self.files.items()
            },
        }

    @classmethod
    def from_file(cls, path: Path) -> "BackupManifest":
        data = json.loads(path.read_text(encoding="utf-8"))
        files = {
            name: FileFingerprint(**value)
            for name, value in data["files"].items()
        }
        return cls(
            backup_id=data["backup_id"],
            backup_type=data["backup_type"],
            created_at=data["created_at"],
            source=data["source"],
            parent_backup_id=data.get("parent_backup_id"),
            files=files,
        )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def scan_directory(root: Path) -> dict[str, FileFingerprint]:
    if not root.is_dir():
        raise BackupError(f"Source directory does not exist: {root}")

    result: dict[str, FileFingerprint] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        result[relative] = FileFingerprint(
            relative_path=relative,
            size=stat.st_size,
            modified_ns=stat.st_mtime_ns,
            sha256=sha256_file(path),
        )

    return result


class BackupStore:
    def __init__(self, destination: Path):
        self.destination = destination
        self.destination.mkdir(parents=True, exist_ok=True)

    def _backup_path(self, backup_id: str) -> Path:
        return self.destination / backup_id

    def _write_manifest(self, backup_dir: Path, manifest: BackupManifest) -> None:
        manifest_path = backup_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2),
            encoding="utf-8",
        )

    def latest_manifest(self) -> BackupManifest | None:
        manifests = []

        for directory in self.destination.iterdir():
            if not directory.is_dir():
                continue

            manifest_path = directory / "manifest.json"
            if manifest_path.exists():
                try:
                    manifests.append(BackupManifest.from_file(manifest_path))
                except (OSError, json.JSONDecodeError, KeyError, TypeError):
                    continue

        if not manifests:
            return None

        return max(manifests, key=lambda item: item.created_at)

    def create_full(self, source: Path, now: datetime | None = None) -> BackupManifest:
        now = now or datetime.now(UTC)
        backup_id = f"full-{now.strftime('%Y%m%dT%H%M%SZ')}"
        backup_dir = self._backup_path(backup_id)

        if backup_dir.exists():
            raise BackupError(f"Backup already exists: {backup_id}")

        fingerprints = scan_directory(source)

        # A temporary directory prevents a partially copied backup from
        # appearing as a completed backup after an interrupted operation.
        with tempfile.TemporaryDirectory(
            dir=self.destination,
            prefix=f".{backup_id}-",
        ) as temporary:
            temporary_dir = Path(temporary)
            data_dir = temporary_dir / "data"
            data_dir.mkdir()

            for relative in fingerprints:
                source_file = source / relative
                target_file = data_dir / relative
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_file)

            manifest = BackupManifest(
                backup_id=backup_id,
                backup_type="full",
                created_at=now.isoformat(),
                source=str(source.resolve()),
                parent_backup_id=None,
                files=fingerprints,
            )
            self._write_manifest(temporary_dir, manifest)
            temporary_dir.rename(backup_dir)

        return manifest

    def create_incremental(
        self,
        source: Path,
        parent: BackupManifest | None = None,
        now: datetime | None = None,
    ) -> BackupManifest:
        now = now or datetime.now(UTC)
        parent = parent or self.latest_manifest()

        if parent is None:
            return self.create_full(source, now)

        current = scan_directory(source)
        changed = {
            name: fp
            for name, fp in current.items()
            if parent.files.get(name) != fp
        }

        backup_id = f"inc-{now.strftime('%Y%m%dT%H%M%SZ')}"
        backup_dir = self._backup_path(backup_id)

        with tempfile.TemporaryDirectory(
            dir=self.destination,
            prefix=f".{backup_id}-",
        ) as temporary:
            temporary_dir = Path(temporary)
            data_dir = temporary_dir / "data"
            data_dir.mkdir()

            for relative in changed:
                source_file = source / relative
                target_file = data_dir / relative
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_file)

            manifest = BackupManifest(
                backup_id=backup_id,
                backup_type="incremental",
                created_at=now.isoformat(),
                source=str(source.resolve()),
                parent_backup_id=parent.backup_id,
                files=changed,
            )
            self._write_manifest(temporary_dir, manifest)
            temporary_dir.rename(backup_dir)

        return manifest

    def verify(self, manifest: BackupManifest) -> tuple[bool, list[str]]:
        errors: list[str] = []
        backup_dir = self._backup_path(manifest.backup_id)
        data_dir = backup_dir / "data"

        if not backup_dir.is_dir():
            return False, ["Backup directory is missing"]

        for relative, fingerprint in manifest.files.items():
            file_path = data_dir / relative

            # Prevent path traversal if a corrupted manifest is introduced.
            try:
                file_path.resolve().relative_to(data_dir.resolve())
            except ValueError:
                errors.append(f"Unsafe backup path: {relative}")
                continue

            if not file_path.is_file():
                errors.append(f"Missing file: {relative}")
                continue

            if file_path.stat().st_size != fingerprint.size:
                errors.append(f"Size mismatch: {relative}")
                continue

            if sha256_file(file_path) != fingerprint.sha256:
                errors.append(f"Checksum mismatch: {relative}")

        return not errors, errors


class RetentionPolicy:
    def __init__(self, keep_days: int):
        if keep_days <= 0:
            raise ValueError("Retention period must be positive")
        self.keep_days = keep_days

    def eligible_for_deletion(
        self,
        manifests: Iterable[BackupManifest],
        now: datetime | None = None,
    ) -> list[BackupManifest]:
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(days=self.keep_days)

        return [
            manifest
            for manifest in manifests
            if datetime.fromisoformat(manifest.created_at) < cutoff
        ]


def list_manifests(store: BackupStore) -> list[BackupManifest]:
    manifests = []

    for directory in store.destination.iterdir():
        path = directory / "manifest.json"
        if path.exists():
            try:
                manifests.append(BackupManifest.from_file(path))
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                pass

    return sorted(manifests, key=lambda item: item.created_at)


def demonstrate() -> None:
    with tempfile.TemporaryDirectory() as workspace:
        root = Path(workspace)
        source = root / "application-data"
        repository = root / "backup-repository"

        (source / "config").mkdir(parents=True)
        (source / "logs").mkdir()

        (source / "config" / "application.conf").write_text(
            "database=production\nretention_days=30\n",
            encoding="utf-8",
        )
        (source / "logs" / "service.log").write_text(
            "service started\n",
            encoding="utf-8",
        )

        store = BackupStore(repository)

        first_time = datetime(2026, 10, 1, 2, 0, tzinfo=UTC)
        full = store.create_full(source, first_time)

        ok, errors = store.verify(full)
        print(f"Full backup verified: {ok}")
        if errors:
            print(errors)

        # Only changed and newly created files belong to this incremental set.
        (source / "logs" / "service.log").write_text(
            "service started\nbackup completed\n",
            encoding="utf-8",
        )
        (source / "config" / "feature.flags").write_text(
            "incremental_backup=true\n",
            encoding="utf-8",
        )

        incremental = store.create_incremental(
            source,
            parent=full,
            now=datetime(2026, 10, 2, 2, 0, tzinfo=UTC),
        )

        ok, errors = store.verify(incremental)
        print(f"Incremental backup verified: {ok}")
        if errors:
            print(errors)

        # Demonstrate a failed integrity check without damaging the original source.
        corrupt_file = repository / incremental.backup_id / "data" / "logs" / "service.log"
        corrupt_file.write_text("tampered\n", encoding="utf-8")

        ok, errors = store.verify(incremental)
        print(f"Corrupted incremental backup verified: {ok}")
        print("Integrity errors:", errors)

        manifests = list_manifests(store)
        policy = RetentionPolicy(keep_days=30)
        old = policy.eligible_for_deletion(
            manifests,
            now=datetime(2026, 11, 5, 2, 0, tzinfo=UTC),
        )
        print("Backups eligible for retention cleanup:")
        for manifest in old:
            print(f"  {manifest.backup_id}")


if __name__ == "__main__":
    demonstrate()
