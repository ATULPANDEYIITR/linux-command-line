from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


class StorageError(Exception):
    """Base exception for storage-related failures."""


class StorageCapacityError(StorageError):
    """Raised when a storage backend cannot accept more data."""


class StoragePermissionError(StorageError):
    """Raised when an operation violates storage permissions."""


class StorageConsistencyError(StorageError):
    """Raised when replicated or distributed copies disagree."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class FileMetadata:
    name: str
    size: int
    checksum: str
    owner: str
    permissions: str = "rw-r--r--"
    version: int = 1
    modified_at: float = field(default_factory=time.time)


@dataclass
class StoredFile:
    metadata: FileMetadata
    content: bytes


class LocalSharedFileSystem:
    """
    A filesystem-backed model of a shared file system.

    The class deliberately keeps the storage root explicit. In a real shared
    filesystem the root could be mounted from a SAN/NAS/export and multiple
    processes or hosts could access the same namespace.
    """

    def __init__(self, root: Path, capacity_bytes: int = 10_000_000):
        self.root = root
        self.capacity_bytes = capacity_bytes
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _used_bytes(self) -> int:
        return sum(
            path.stat().st_size
            for path in self.root.rglob("*")
            if path.is_file()
        )

    def _safe_path(self, relative_name: str) -> Path:
        candidate = (self.root / relative_name).resolve()
        if self.root.resolve() not in candidate.parents and candidate != self.root.resolve():
            raise StoragePermissionError("Path escapes the shared filesystem root")
        return candidate

    def write(self, relative_name: str, content: bytes, owner: str) -> FileMetadata:
        target = self._safe_path(relative_name)
        target.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            old_size = target.stat().st_size if target.exists() else 0
            new_used = self._used_bytes() - old_size + len(content)

            if new_used > self.capacity_bytes:
                raise StorageCapacityError(
                    f"Capacity exceeded: {new_used} > {self.capacity_bytes}"
                )

            # Atomic replacement avoids exposing a partially written file.
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, delete=False
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)

            os.replace(temporary_path, target)

        return FileMetadata(
            name=relative_name,
            size=len(content),
            checksum=sha256_bytes(content),
            owner=owner,
        )

    def read(self, relative_name: str) -> bytes:
        target = self._safe_path(relative_name)
        if not target.is_file():
            raise FileNotFoundError(relative_name)
        return target.read_bytes()

    def delete(self, relative_name: str) -> None:
        target = self._safe_path(relative_name)
        with self._lock:
            if not target.is_file():
                raise FileNotFoundError(relative_name)
            target.unlink()

    def list_files(self) -> List[str]:
        return sorted(
            str(path.relative_to(self.root))
            for path in self.root.rglob("*")
            if path.is_file()
        )


class NetworkFileStorageClient:
    """
    Models a network file-storage client.

    A network file service normally exposes a filesystem namespace through a
    protocol such as NFS or SMB. The application sees files and directories,
    while the storage server owns persistence, access control, and hardware.
    """

    def __init__(self, backend: LocalSharedFileSystem, client_name: str):
        self.backend = backend
        self.client_name = client_name
        self.mounted = False

    def mount(self) -> None:
        self.mounted = True

    def _require_mount(self) -> None:
        if not self.mounted:
            raise StorageError(f"{self.client_name}: network filesystem is not mounted")

    def upload(self, path: str, content: bytes, owner: str) -> FileMetadata:
        self._require_mount()
        return self.backend.write(path, content, owner)

    def download(self, path: str) -> bytes:
        self._require_mount()
        return self.backend.read(path)

    def directory(self) -> List[str]:
        self._require_mount()
        return self.backend.list_files()


@dataclass
class Replica:
    node: str
    files: Dict[str, StoredFile] = field(default_factory=dict)
    available: bool = True


class DistributedObjectStore:
    """
    A small distributed-storage model.

    Objects are replicated across independent nodes. Unlike a shared filesystem,
    clients do not depend on one globally mounted directory hierarchy. The
    store uses replication and checksums to tolerate node loss and detect
    corrupted data.
    """

    def __init__(self, nodes: Iterable[str], replication_factor: int = 2):
        node_names = list(nodes)
        if not node_names:
            raise ValueError("At least one storage node is required")
        if not 1 <= replication_factor <= len(node_names):
            raise ValueError("Invalid replication factor")

        self.replicas = {name: Replica(name) for name in node_names}
        self.replication_factor = replication_factor
        self._lock = threading.RLock()

    def _available_nodes(self) -> List[Replica]:
        return [node for node in self.replicas.values() if node.available]

    def put(self, object_name: str, content: bytes, owner: str) -> str:
        checksum = sha256_bytes(content)

        with self._lock:
            nodes = self._available_nodes()
            if len(nodes) < self.replication_factor:
                raise StorageError("Insufficient healthy nodes for required replication")

            metadata = FileMetadata(
                name=object_name,
                size=len(content),
                checksum=checksum,
                owner=owner,
            )

            stored = StoredFile(metadata, content)

            for node in nodes[: self.replication_factor]:
                node.files[object_name] = stored

        return checksum

    def get(self, object_name: str) -> bytes:
        with self._lock:
            candidates = []

            for node in self._available_nodes():
                stored = node.files.get(object_name)
                if stored is not None:
                    candidates.append(stored)

            if not candidates:
                raise FileNotFoundError(object_name)

            # All healthy replicas should agree on the checksum.
            checksums = {item.metadata.checksum for item in candidates}
            if len(checksums) != 1:
                raise StorageConsistencyError(
                    f"Replica disagreement for {object_name}: {checksums}"
                )

            selected = candidates[0]
            if sha256_bytes(selected.content) != selected.metadata.checksum:
                raise StorageConsistencyError(
                    f"Checksum validation failed for {object_name}"
                )

            return selected.content

    def mark_node_down(self, node_name: str) -> None:
        self.replicas[node_name].available = False

    def mark_node_up(self, node_name: str) -> None:
        self.replicas[node_name].available = True

    def corrupt_replica(self, node_name: str, object_name: str, content: bytes) -> None:
        node = self.replicas[node_name]
        stored = node.files[object_name]
        node.files[object_name] = StoredFile(stored.metadata, content)

    def repair(self, object_name: str) -> None:
        """
        Rebuild a missing or corrupted replica from a verified healthy copy.
        """
        content = self.get(object_name)
        checksum = sha256_bytes(content)

        with self._lock:
            metadata = FileMetadata(
                name=object_name,
                size=len(content),
                checksum=checksum,
                owner="repair-service",
            )
            healthy = [
                node for node in self._available_nodes()
                if object_name in node.files
                and sha256_bytes(node.files[object_name].content) == checksum
            ]

            for node in self._available_nodes():
                if node not in healthy:
                    node.files[object_name] = StoredFile(metadata, content)

    def distribution(self, object_name: str) -> Dict[str, bool]:
        return {
            node_name: object_name in node.files
            for node_name, node in self.replicas.items()
        }


def demonstrate_shared_filesystem(shared_root: Path) -> None:
    print("\n=== Shared File System ===")
    shared = LocalSharedFileSystem(shared_root, capacity_bytes=100_000)

    metadata = shared.write(
        "engineering/designs/storage-architecture.txt",
        b"Shared filesystem documentation",
        owner="alice",
    )

    print("Stored:", metadata.name)
    print("Checksum:", metadata.checksum)
    print("Files:", shared.list_files())

    content = shared.read("engineering/designs/storage-architecture.txt")
    print("Read:", content.decode())

    try:
        shared.read("../../outside.txt")
    except (StoragePermissionError, FileNotFoundError) as exc:
        print("Rejected unsafe access:", exc)


def demonstrate_network_storage(shared_root: Path) -> None:
    print("\n=== Network File Storage ===")

    server = LocalSharedFileSystem(shared_root / "network-share")
    analyst = NetworkFileStorageClient(server, "analytics-client")
    application = NetworkFileStorageClient(server, "application-client")

    try:
        analyst.download("reports/monthly.csv")
    except StorageError as exc:
        print("Access before mount:", exc)

    analyst.mount()
    application.mount()

    analyst.upload(
        "reports/monthly.csv",
        b"month,revenue\n2026-09,150000\n2026-10,163500\n",
        owner="finance",
    )

    # Both clients see the same namespace because they access one shared backend.
    print("Analyst sees:", analyst.directory())
    print("Application reads:")
    print(application.download("reports/monthly.csv").decode())


def demonstrate_distributed_storage() -> None:
    print("\n=== Distributed Storage ===")

    store = DistributedObjectStore(
        ["storage-a", "storage-b", "storage-c"],
        replication_factor=2,
    )

    checksum = store.put(
        "datasets/customer-events-2026-10.json",
        b'{"event":"purchase","customer":"C-1042","amount":2499}',
        owner="analytics",
    )

    print("Object checksum:", checksum)
    print("Replica distribution:", store.distribution("datasets/customer-events-2026-10.json"))

    store.mark_node_down("storage-a")
    print("Read after storage-a failure:", store.get("datasets/customer-events-2026-10.json"))

    store.corrupt_replica(
        "storage-b",
        "datasets/customer-events-2026-10.json",
        b"tampered payload",
    )

    try:
        store.get("datasets/customer-events-2026-10.json")
    except StorageConsistencyError as exc:
        print("Detected corruption:", exc)

    store.mark_node_down("storage-b")
    store.mark_node_up("storage-a")
    store.repair("datasets/customer-events-2026-10.json")

    print("After repair:", store.distribution("datasets/customer-events-2026-10.json"))


def compare_storage_models() -> None:
    print("\n=== Storage Model Comparison ===")

    models = {
        "shared filesystem": {
            "namespace": "directory tree",
            "access": "shared mount",
            "strength": "familiar POSIX-style file operations",
            "risk": "shared-state contention and server dependency",
        },
        "network file storage": {
            "namespace": "remote filesystem",
            "access": "NFS/SMB-style client",
            "strength": "centralized shared files for multiple hosts",
            "risk": "network latency and availability dependency",
        },
        "distributed storage": {
            "namespace": "object/block/distributed namespace",
            "access": "storage service or distributed protocol",
            "strength": "replication and node-level fault tolerance",
            "risk": "consistency, repair, placement, and operational complexity",
        },
    }

    for name, properties in models.items():
        print(f"\n{name}")
        for key, value in properties.items():
            print(f"  {key}: {value}")


def run_validation_tests() -> None:
    print("\n=== Validation and Failure Tests ===")

    with tempfile.TemporaryDirectory() as temporary:
        filesystem = LocalSharedFileSystem(Path(temporary), capacity_bytes=8)

        filesystem.write("small.txt", b"1234", "tester")

        try:
            filesystem.write("too-large.txt", b"123456789", "tester")
        except StorageCapacityError as exc:
            print("Capacity validation:", exc)

        try:
            filesystem.read("missing.txt")
        except FileNotFoundError as exc:
            print("Missing file validation:", exc)

    store = DistributedObjectStore(["a", "b", "c"], replication_factor=3)
    store.put("critical.bin", b"important", "system")

    store.mark_node_down("a")
    store.mark_node_down("b")

    try:
        store.put("another.bin", b"data", "system")
    except StorageError as exc:
        print("Replication validation:", exc)


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        demonstrate_shared_filesystem(root / "shared")
        demonstrate_network_storage(root)
        demonstrate_distributed_storage()
        compare_storage_models()
        run_validation_tests()


if __name__ == "__main__":
    main()
