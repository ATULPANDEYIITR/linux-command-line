#!/usr/bin/env python3
"""
Docker Volumes: Persistent Storage and Data Management

A self-contained storage lifecycle simulator covering:
- Docker named volumes
- Bind mounts
- Anonymous volumes
- Container writable layers
- Mount configuration and validation
- Persistence across container removal
- Volume inspection, backup, restoration and deletion
- Shared volumes and reference tracking
- Storage usage and security policies

Run: python docker_volumes.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class StorageError(Exception):
    """Base exception for storage operations."""


class VolumeNotFoundError(StorageError):
    pass


class MountConflictError(StorageError):
    pass


class StoragePolicyError(StorageError):
    pass


class MountType(Enum):
    NAMED = "named"
    ANONYMOUS = "anonymous"
    BIND = "bind"


class ContainerState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    REMOVED = "removed"


@dataclass
class Volume:
    name: str
    mount_type: MountType
    host_path: Path
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    labels: dict[str, str] = field(default_factory=dict)
    references: set[str] = field(default_factory=set)
    read_only: bool = False


@dataclass
class Mount:
    source: str
    destination: str
    mount_type: MountType
    read_only: bool = False


@dataclass
class Container:
    name: str
    mounts: list[Mount]
    state: ContainerState = ContainerState.CREATED
    writable_layer: dict[str, str] = field(default_factory=dict)


class DockerStorageManager:
    def __init__(self, root: Optional[Path] = None):
        self._temporary_root = None

        if root is None:
            self._temporary_root = tempfile.TemporaryDirectory(
                prefix="docker-storage-"
            )
            root = Path(self._temporary_root.name)

        self.root = Path(root).resolve()
        self.volumes_dir = self.root / "volumes"
        self.bind_dir = self.root / "binds"
        self.backup_dir = self.root / "backups"

        for directory in (
            self.volumes_dir,
            self.bind_dir,
            self.backup_dir
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.volumes: dict[str, Volume] = {}
        self.containers: dict[str, Container] = {}

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name or len(name) > 128:
            raise ValueError("Name must contain 1 to 128 characters.")

        if not all(
            char.isalnum() or char in "_.-"
            for char in name
        ):
            raise ValueError("Invalid storage name.")

    @staticmethod
    def _validate_container_path(path: str) -> None:
        destination = Path(path)

        if not destination.is_absolute():
            raise ValueError("Container mount destination must be absolute.")

        if ".." in destination.parts:
            raise ValueError("Path traversal is not permitted.")

    def _safe_path(self, base: Path, name: str) -> Path:
        self._validate_name(name)
        result = (base / name).resolve()

        if result.parent != base.resolve():
            raise StoragePolicyError("Storage path escaped its root.")

        return result

    def create_volume(
        self,
        name: Optional[str] = None,
        labels: Optional[dict[str, str]] = None
    ) -> Volume:

        anonymous = name is None

        if anonymous:
            name = uuid.uuid4().hex[:16]

        self._validate_name(name)

        if name in self.volumes:
            raise StorageError(f"Volume already exists: {name}")

        path = self._safe_path(self.volumes_dir, name)
        path.mkdir(parents=True, exist_ok=False)

        volume = Volume(
            name=name,
            mount_type=(
                MountType.ANONYMOUS if anonymous else MountType.NAMED
            ),
            host_path=path,
            labels=labels or {}
        )

        self.volumes[name] = volume
        return volume

    def create_bind_mount(
        self,
        name: str,
        source: Path,
        read_only: bool = False
    ) -> Volume:

        self._validate_name(name)

        if name in self.volumes:
            raise StorageError(f"Mount already exists: {name}")

        source = Path(source).resolve()

        if not source.exists() or not source.is_dir():
            raise StorageError("Bind source must be an existing directory.")

        volume = Volume(
            name=name,
            mount_type=MountType.BIND,
            host_path=source,
            read_only=read_only
        )

        self.volumes[name] = volume
        return volume

    def create_container(
        self,
        name: str,
        mount_specs: list[dict]
    ) -> Container:

        self._validate_name(name)

        if name in self.containers:
            raise StorageError(f"Container already exists: {name}")

        mounts = []
        destinations = set()

        for spec in mount_specs:
            mount_type = MountType(spec["type"])
            source = spec["source"]
            destination = spec["target"]
            read_only = bool(spec.get("read_only", False))

            self._validate_container_path(destination)

            if destination in destinations:
                raise MountConflictError(
                    f"Duplicate mount destination: {destination}"
                )

            destinations.add(destination)

            if mount_type in (MountType.NAMED, MountType.ANONYMOUS):
                volume = self.volumes.get(source)

                if volume is None:
                    raise VolumeNotFoundError(source)

                if volume.mount_type == MountType.BIND:
                    raise StoragePolicyError(
                        "A bind mount cannot be used as a named volume."
                    )

                if volume.read_only and not read_only:
                    raise StoragePolicyError(
                        "Read-only storage cannot be mounted writable."
                    )

            elif mount_type == MountType.BIND:
                volume = self.volumes.get(source)

                if volume is None or volume.mount_type != MountType.BIND:
                    raise VolumeNotFoundError(source)

                if volume.read_only and not read_only:
                    raise StoragePolicyError(
                        "Bind mount is configured as read-only."
                    )

            mounts.append(
                Mount(source, destination, mount_type, read_only)
            )

        container = Container(name=name, mounts=mounts)

        # Register references only after all mount validations succeed.
        self.containers[name] = container

        for mount in mounts:
            self.volumes[mount.source].references.add(name)

        return container

    def start_container(self, name: str) -> None:
        container = self._get_container(name)

        if container.state == ContainerState.REMOVED:
            raise StorageError("Removed containers cannot be started.")

        if container.state == ContainerState.RUNNING:
            return

        container.state = ContainerState.RUNNING

    def stop_container(self, name: str) -> None:
        container = self._get_container(name)

        if container.state != ContainerState.RUNNING:
            raise StorageError("Container is not running.")

        container.state = ContainerState.STOPPED

    def _get_container(self, name: str) -> Container:
        container = self.containers.get(name)

        if container is None:
            raise StorageError(f"Container not found: {name}")

        return container

    def _resolve_mount(
        self,
        container: Container,
        container_path: str
    ) -> tuple[Mount, Path]:

        target = Path(container_path)

        matches = []

        for mount in container.mounts:
            destination = Path(mount.destination)

            try:
                relative = target.relative_to(destination)
            except ValueError:
                continue

            matches.append((len(destination.parts), mount, relative))

        if not matches:
            raise StorageError(
                "Path is not covered by a mounted storage location."
            )

        _, mount, relative = max(matches, key=lambda item: item[0])

        volume = self.volumes[mount.source]

        resolved = (volume.host_path / relative).resolve()

        if not resolved.is_relative_to(volume.host_path.resolve()):
            raise StoragePolicyError("Path traversal detected.")

        return mount, resolved

    def write_file(
        self,
        container_name: str,
        container_path: str,
        content: str
    ) -> None:

        container = self._get_container(container_name)

        if container.state != ContainerState.RUNNING:
            raise StorageError("Container must be running.")

        mount, destination = self._resolve_mount(
            container, container_path
        )

        if mount.read_only:
            raise StoragePolicyError("Cannot write to a read-only mount.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def read_file(
        self,
        container_name: str,
        container_path: str
    ) -> str:

        container = self._get_container(container_name)

        mount, source = self._resolve_mount(
            container, container_path
        )

        if not source.is_file():
            raise StorageError("File does not exist.")

        return source.read_text(encoding="utf-8")

    def write_container_layer(
        self,
        container_name: str,
        path: str,
        content: str
    ) -> None:

        container = self._get_container(container_name)

        if container.state != ContainerState.RUNNING:
            raise StorageError("Container must be running.")

        self._validate_container_path(path)

        # Writes outside mounted destinations remain in the container layer.
        for mount in container.mounts:
            if Path(path).is_relative_to(Path(mount.destination)):
                raise StorageError(
                    "Use write_file for mounted storage."
                )

        container.writable_layer[path] = content

    def remove_container(self, name: str) -> None:
        container = self._get_container(name)

        if container.state == ContainerState.RUNNING:
            self.stop_container(name)

        for mount in container.mounts:
            self.volumes[mount.source].references.discard(name)

        # The writable layer is discarded; mounted storage remains.
        container.writable_layer.clear()
        container.state = ContainerState.REMOVED

    def remove_volume(
        self,
        name: str,
        force: bool = False
    ) -> None:

        volume = self.volumes.get(name)

        if volume is None:
            raise VolumeNotFoundError(name)

        if volume.references and not force:
            raise StoragePolicyError(
                f"Volume is in use by: {sorted(volume.references)}"
            )

        if volume.mount_type != MountType.BIND:
            shutil.rmtree(volume.host_path)

        # Bind directories belong to the host and are never deleted here.
        del self.volumes[name]

    def inspect_volume(self, name: str) -> dict:
        volume = self.volumes.get(name)

        if volume is None:
            raise VolumeNotFoundError(name)

        return {
            "name": volume.name,
            "type": volume.mount_type.value,
            "host_path": str(volume.host_path),
            "created_at": volume.created_at,
            "labels": volume.labels,
            "references": sorted(volume.references),
            "read_only": volume.read_only,
            "exists": volume.host_path.exists()
        }

    def list_volumes(self) -> list[dict]:
        return [
            self.inspect_volume(name)
            for name in sorted(self.volumes)
        ]

    def backup_volume(self, name: str) -> Path:
        volume = self.volumes.get(name)

        if volume is None:
            raise VolumeNotFoundError(name)

        if volume.mount_type == MountType.BIND:
            raise StoragePolicyError(
                "This demonstration backs up managed volumes only."
            )

        backup = self.backup_dir / f"{name}.json"

        files = {}

        for file_path in volume.host_path.rglob("*"):
            if file_path.is_symlink():
                raise StoragePolicyError(
                    "Symbolic links are not supported in backups."
                )

            if file_path.is_file():
                relative = file_path.relative_to(volume.host_path)
                files[str(relative)] = file_path.read_text(
                    encoding="utf-8"
                )

        payload = {
            "volume": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files
        }

        backup.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8"
        )

        return backup

    def restore_volume(
        self,
        backup: Path,
        destination_name: str
    ) -> Volume:

        payload = json.loads(
            Path(backup).read_text(encoding="utf-8")
        )

        files = payload.get("files")

        if not isinstance(files, dict):
            raise StorageError("Invalid backup format.")

        volume = self.create_volume(
            destination_name,
            {"restored": "true"}
        )

        try:
            for relative, content in files.items():
                relative_path = Path(relative)

                if (
                    relative_path.is_absolute()
                    or ".." in relative_path.parts
                    or not isinstance(content, str)
                ):
                    raise StoragePolicyError(
                        "Invalid backup file entry."
                    )

                destination = (
                    volume.host_path / relative_path
                ).resolve()

                if not destination.is_relative_to(volume.host_path):
                    raise StoragePolicyError(
                        "Backup path escaped volume."
                    )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                destination.write_text(content, encoding="utf-8")

            return volume

        except Exception:
            self.remove_volume(destination_name, force=True)
            raise

    def storage_report(self) -> dict:
        report = []

        for volume in self.volumes.values():
            size = 0

            if volume.host_path.exists() and volume.host_path.is_dir():
                for file_path in volume.host_path.rglob("*"):
                    if file_path.is_file() and not file_path.is_symlink():
                        size += file_path.stat().st_size

            report.append({
                "name": volume.name,
                "type": volume.mount_type.value,
                "size_bytes": size,
                "references": len(volume.references)
            })

        return {
            "volume_count": len(report),
            "total_bytes": sum(item["size_bytes"] for item in report),
            "volumes": report
        }

    def close(self) -> None:
        if self._temporary_root:
            self._temporary_root.cleanup()


def run_tests() -> None:
    manager = DockerStorageManager()

    try:
        # Named volume persists independently of container lifecycle.
        manager.create_volume(
            "database_data",
            {"environment": "development", "owner": "platform"}
        )

        manager.create_container(
            "postgres",
            [{
                "type": "named",
                "source": "database_data",
                "target": "/var/lib/postgresql/data"
            }]
        )

        manager.start_container("postgres")

        manager.write_file(
            "postgres",
            "/var/lib/postgresql/data/database.txt",
            "Persistent PostgreSQL application data"
        )

        manager.write_container_layer(
            "postgres",
            "/tmp/session.txt",
            "Temporary container data"
        )

        assert manager.read_file(
            "postgres",
            "/var/lib/postgresql/data/database.txt"
        ) == "Persistent PostgreSQL application data"

        # A referenced volume cannot be deleted.
        try:
            manager.remove_volume("database_data")
            raise AssertionError("Expected in-use protection.")
        except StoragePolicyError:
            pass

        backup = manager.backup_volume("database_data")

        manager.remove_container("postgres")

        assert manager.inspect_volume("database_data")["exists"]

        # Restoration creates an independent volume.
        manager.restore_volume(backup, "database_restore")

        manager.create_container(
            "postgres_recovery",
            [{
                "type": "named",
                "source": "database_restore",
                "target": "/var/lib/postgresql/data"
            }]
        )

        manager.start_container("postgres_recovery")

        assert manager.read_file(
            "postgres_recovery",
            "/var/lib/postgresql/data/database.txt"
        ) == "Persistent PostgreSQL application data"

        # Bind mount points to an existing host directory.
        host_data = manager.root / "host-config"
        host_data.mkdir()

        (host_data / "settings.txt").write_text(
            "Host-managed configuration",
            encoding="utf-8"
        )

        manager.create_bind_mount(
            "host_configuration",
            host_data,
            read_only=True
        )

        manager.create_container(
            "application",
            [{
                "type": "bind",
                "source": "host_configuration",
                "target": "/etc/application",
                "read_only": True
            }]
        )

        manager.start_container("application")

        assert manager.read_file(
            "application",
            "/etc/application/settings.txt"
        ) == "Host-managed configuration"

        try:
            manager.write_file(
                "application",
                "/etc/application/settings.txt",
                "Unauthorized modification"
            )
            raise AssertionError("Expected read-only protection.")
        except StoragePolicyError:
            pass

        manager.remove_container("application")
        manager.remove_container("postgres_recovery")

        # An unreferenced named volume can be removed.
        manager.remove_volume("database_restore")
        assert "database_restore" not in manager.volumes

        print("All Docker storage lifecycle tests passed.")
        print(json.dumps(
            manager.storage_report(),
            indent=2
        ))

    finally:
        manager.close()


if __name__ == "__main__":
    run_tests()
