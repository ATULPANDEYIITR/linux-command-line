from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Snapshot:
    snapshot_id: str
    source_disk: str
    created_at: float
    size_gb: float
    changed_blocks: int
    parent_snapshot: Optional[str] = None

    def describe(self) -> str:
        parent = self.parent_snapshot or "none"
        return (
            f"{self.snapshot_id}: disk={self.source_disk}, "
            f"size={self.size_gb:.1f} GB, changed_blocks={self.changed_blocks}, "
            f"parent={parent}"
        )


@dataclass
class Disk:
    disk_id: str
    capacity_gb: float
    disk_type: str
    zone: str
    attached_to: Optional[str] = None
    used_gb: float = 0.0
    block_size_kb: int = 4
    snapshots: List[Snapshot] = field(default_factory=list)

    @property
    def free_gb(self) -> float:
        return max(0.0, self.capacity_gb - self.used_gb)

    def write(self, amount_gb: float) -> None:
        if amount_gb < 0:
            raise ValueError("Write size cannot be negative.")
        if amount_gb > self.free_gb:
            raise RuntimeError(
                f"Disk {self.disk_id} has only {self.free_gb:.2f} GB free."
            )
        self.used_gb += amount_gb

    def read_latency_ms(self) -> float:
        profiles = {
            "hdd": 8.0,
            "ssd": 0.8,
            "nvme": 0.15,
        }
        if self.disk_type not in profiles:
            raise ValueError(f"Unsupported disk type: {self.disk_type}")
        return profiles[self.disk_type]


@dataclass
class ComputeInstance:
    instance_id: str
    zone: str
    attached_disks: Dict[str, str] = field(default_factory=dict)

    def attach(self, disk: Disk) -> None:
        if disk.zone != self.zone:
            raise RuntimeError(
                f"Zone mismatch: instance {self.zone}, disk {disk.zone}."
            )
        if disk.attached_to is not None:
            raise RuntimeError(f"Disk {disk.disk_id} is already attached.")
        disk.attached_to = self.instance_id
        self.attached_disks[disk.disk_id] = "rw"

    def detach(self, disk: Disk) -> None:
        if disk.disk_id not in self.attached_disks:
            raise RuntimeError(
                f"Disk {disk.disk_id} is not attached to {self.instance_id}."
            )
        del self.attached_disks[disk.disk_id]
        disk.attached_to = None


class BlockStorageSystem:
    """
    A small in-memory block-storage control plane.

    The model separates compute instances from persistent disks. A disk can
    outlive a compute instance, which is a central property of persistent
    block storage. Snapshots are represented as point-in-time metadata with
    incremental changed-block accounting.
    """

    def __init__(self) -> None:
        self.disks: Dict[str, Disk] = {}
        self.instances: Dict[str, ComputeInstance] = {}
        self.snapshots: Dict[str, Snapshot] = {}

    def create_instance(self, instance_id: str, zone: str) -> ComputeInstance:
        if instance_id in self.instances:
            raise ValueError(f"Instance already exists: {instance_id}")
        instance = ComputeInstance(instance_id, zone)
        self.instances[instance_id] = instance
        return instance

    def create_disk(
        self,
        disk_id: str,
        capacity_gb: float,
        disk_type: str,
        zone: str,
    ) -> Disk:
        if disk_id in self.disks:
            raise ValueError(f"Disk already exists: {disk_id}")
        if capacity_gb <= 0:
            raise ValueError("Disk capacity must be positive.")
        disk = Disk(disk_id, capacity_gb, disk_type.lower(), zone)
        self.disks[disk_id] = disk
        return disk

    def attach(self, disk_id: str, instance_id: str) -> None:
        disk = self.disks[disk_id]
        instance = self.instances[instance_id]
        instance.attach(disk)

    def detach(self, disk_id: str, instance_id: str) -> None:
        disk = self.disks[disk_id]
        instance = self.instances[instance_id]
        instance.detach(disk)

    def create_snapshot(
        self,
        snapshot_id: str,
        disk_id: str,
        changed_blocks: int,
    ) -> Snapshot:
        if snapshot_id in self.snapshots:
            raise ValueError(f"Snapshot already exists: {snapshot_id}")
        if changed_blocks < 0:
            raise ValueError("Changed blocks cannot be negative.")

        disk = self.disks[disk_id]
        parent = disk.snapshots[-1].snapshot_id if disk.snapshots else None
        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            source_disk=disk_id,
            created_at=time.time(),
            size_gb=disk.used_gb,
            changed_blocks=changed_blocks,
            parent_snapshot=parent,
        )
        disk.snapshots.append(snapshot)
        self.snapshots[snapshot_id] = snapshot
        return snapshot

    def restore_snapshot(
        self,
        snapshot_id: str,
        target_disk_id: str,
    ) -> None:
        snapshot = self.snapshots[snapshot_id]
        target = self.disks[target_disk_id]

        if target.attached_to is not None:
            raise RuntimeError(
                "Restoration requires the target disk to be detached."
            )
        if snapshot.size_gb > target.capacity_gb:
            raise RuntimeError(
                "Target disk is smaller than the snapshot data footprint."
            )

        target.used_gb = snapshot.size_gb

    def performance_report(self) -> List[Tuple[str, float, float]]:
        """
        Provides an intentionally simplified model:
        latency is media-dependent, while estimated sequential throughput
        reflects the characteristics of common storage classes.
        """
        throughput = {
            "hdd": 180.0,
            "ssd": 550.0,
            "nvme": 3500.0,
        }
        return [
            (
                disk.disk_id,
                disk.read_latency_ms(),
                throughput[disk.disk_type],
            )
            for disk in self.disks.values()
        ]

    def inventory(self) -> None:
        print("\nStorage inventory")
        for disk in self.disks.values():
            attachment = disk.attached_to or "detached"
            print(
                f"{disk.disk_id}: {disk.disk_type.upper()}, "
                f"{disk.used_gb:.1f}/{disk.capacity_gb:.1f} GB, "
                f"zone={disk.zone}, attachment={attachment}"
            )

        print("\nSnapshots")
        for snapshot in self.snapshots.values():
            print(snapshot.describe())


def calculate_iops(
    io_operations: int,
    elapsed_seconds: float,
) -> float:
    if io_operations < 0:
        raise ValueError("I/O operation count cannot be negative.")
    if elapsed_seconds <= 0:
        raise ValueError("Elapsed time must be positive.")
    return io_operations / elapsed_seconds


def estimate_transfer_time(
    size_gb: float,
    throughput_mb_per_second: float,
) -> float:
    if size_gb < 0:
        raise ValueError("Data size cannot be negative.")
    if throughput_mb_per_second <= 0:
        raise ValueError("Throughput must be positive.")
    return size_gb * 1024 / throughput_mb_per_second


def block_count(size_gb: float, block_size_kb: int = 4) -> int:
    if size_gb < 0 or block_size_kb <= 0:
        raise ValueError("Size and block size must be positive.")
    return math.ceil(size_gb * 1024 * 1024 / block_size_kb)


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def demonstrate_file_backed_volume() -> None:
    """
    A temporary file represents a tiny logical block device for demonstrating
    persistence independently of the compute process.
    """
    print("\nFile-backed volume demonstration")

    with tempfile.TemporaryDirectory() as directory:
        volume = Path(directory) / "volume.bin"

        payload = b"persistent block storage\n"
        with volume.open("wb") as stream:
            stream.write(payload)

        original_hash = checksum_file(volume)

        with volume.open("ab") as stream:
            stream.write(b"additional application data\n")

        current_hash = checksum_file(volume)

        print(f"Volume path: {volume}")
        print(f"Initial checksum: {original_hash}")
        print(f"Current checksum: {current_hash}")
        print(f"Persistent bytes: {volume.stat().st_size}")


def demonstrate_failure_conditions(storage: BlockStorageSystem) -> None:
    print("\nFailure-condition checks")

    try:
        storage.create_disk("invalid", -10, "ssd", "zone-a")
    except ValueError as exc:
        print(f"Rejected invalid capacity: {exc}")

    try:
        storage.attach("data-nvme", "compute-b")
    except RuntimeError as exc:
        print(f"Rejected invalid attachment: {exc}")

    try:
        storage.disks["data-nvme"].write(500)
    except RuntimeError as exc:
        print(f"Rejected capacity overflow: {exc}")


def main() -> None:
    storage = BlockStorageSystem()

    storage.create_instance("compute-a", "zone-a")
    storage.create_instance("compute-b", "zone-b")

    data_disk = storage.create_disk(
        "data-nvme",
        capacity_gb=200,
        disk_type="nvme",
        zone="zone-a",
    )
    backup_disk = storage.create_disk(
        "backup-ssd",
        capacity_gb=500,
        disk_type="ssd",
        zone="zone-a",
    )
    archive_disk = storage.create_disk(
        "archive-hdd",
        capacity_gb=1000,
        disk_type="hdd",
        zone="zone-a",
    )

    print("Block storage fundamentals")
    print(
        f"data-nvme contains {block_count(10):,} logical 4 KiB blocks "
        "for a 10 GiB logical workload."
    )

    storage.attach("data-nvme", "compute-a")
    storage.attach("backup-ssd", "compute-a")

    data_disk.write(72)
    backup_disk.write(140)
    archive_disk.write(620)

    first_snapshot = storage.create_snapshot(
        "snapshot-data-001",
        "data-nvme",
        changed_blocks=18432,
    )

    data_disk.write(18)

    second_snapshot = storage.create_snapshot(
        "snapshot-data-002",
        "data-nvme",
        changed_blocks=4096,
    )

    print("\nSnapshot chain")
    print(first_snapshot.describe())
    print(second_snapshot.describe())

    storage.detach("data-nvme", "compute-a")
    storage.restore_snapshot("snapshot-data-001", "data-nvme")
    storage.attach("data-nvme", "compute-a")

    storage.inventory()

    print("\nPerformance model")
    for disk_id, latency, throughput in storage.performance_report():
        print(
            f"{disk_id}: approximate read latency={latency:.2f} ms, "
            f"sequential throughput={throughput:.0f} MB/s"
        )

    print("\nPerformance calculations")
    print(
        f"Estimated NVMe transfer time for 20 GiB: "
        f"{estimate_transfer_time(20, 3500):.2f} seconds"
    )
    print(f"Example IOPS: {calculate_iops(125000, 2.5):,.0f}")

    demonstrate_failure_conditions(storage)
    demonstrate_file_backed_volume()

    print(
        "\nProduction considerations: real block storage involves I/O queues, "
        "provisioned IOPS or throughput, encryption, access control, "
        "multi-attachment rules, replication, snapshot consistency, "
        "monitoring, backup retention, and recovery objectives."
    )


if __name__ == "__main__":
    main()
