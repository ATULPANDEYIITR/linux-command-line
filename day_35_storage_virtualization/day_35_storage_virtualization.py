#!/usr/bin/env python3
"""
Storage Virtualization: logical volumes, virtual disks, block storage abstraction,
and storage pools.

This self-contained program models a small storage virtualization platform without
touching real disks. It demonstrates how physical storage capacity can be grouped
into a storage pool, exposed through virtual disks, and allocated to logical
volumes through a block-storage abstraction.

The model intentionally separates:
    Physical disks -> Storage pool -> Virtual disk -> Logical volume -> Blocks

The implementation includes allocation, reads/writes, snapshots, thin provisioning,
capacity accounting, validation, failure handling, and a small consistency test suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Dict, List, Optional, Set, Tuple
import hashlib
import random


BYTES_PER_GIB = 1024 ** 3


class StorageError(Exception):
    """Base exception for storage-domain failures."""


class CapacityError(StorageError):
    """Raised when an allocation cannot fit within available capacity."""


class ValidationError(StorageError):
    """Raised when a storage operation violates a domain rule."""


class NotFoundError(StorageError):
    """Raised when a requested storage object does not exist."""


class DeviceState(Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    FAILED = "failed"


class VolumeType(Enum):
    THICK = "thick"
    THIN = "thin"


@dataclass
class PhysicalDisk:
    """Represents a physical disk contributing blocks to a storage pool."""

    disk_id: str
    capacity_gib: int
    state: DeviceState = DeviceState.ONLINE
    allocated_gib: int = 0

    @property
    def free_gib(self) -> int:
        return self.capacity_gib - self.allocated_gib

    def allocate(self, gib: int) -> None:
        if gib < 0:
            raise ValidationError("Disk allocation cannot be negative.")
        if self.state == DeviceState.FAILED:
            raise StorageError(f"Disk {self.disk_id} has failed.")
        if gib > self.free_gib:
            raise CapacityError(f"Disk {self.disk_id} lacks {gib} GiB.")
        self.allocated_gib += gib

    def release(self, gib: int) -> None:
        if gib < 0 or gib > self.allocated_gib:
            raise ValidationError("Invalid disk release amount.")
        self.allocated_gib -= gib


@dataclass
class StoragePool:
    """
    Aggregates physical disks into one logical capacity domain.

    A real storage platform could use RAID, erasure coding, replication, or a
    distributed placement algorithm underneath this abstraction. This educational
    model uses simple capacity allocation while keeping the abstraction boundary.
    """

    pool_id: str
    disks: Dict[str, PhysicalDisk] = field(default_factory=dict)

    def add_disk(self, disk: PhysicalDisk) -> None:
        if disk.disk_id in self.disks:
            raise ValidationError(f"Disk {disk.disk_id} already exists.")
        if disk.capacity_gib <= 0:
            raise ValidationError("Disk capacity must be positive.")
        self.disks[disk.disk_id] = disk

    @property
    def total_gib(self) -> int:
        return sum(d.capacity_gib for d in self.disks.values())

    @property
    def usable_gib(self) -> int:
        return sum(
            d.capacity_gib for d in self.disks.values()
            if d.state != DeviceState.FAILED
        )

    @property
    def allocated_gib(self) -> int:
        return sum(d.allocated_gib for d in self.disks.values())

    @property
    def free_gib(self) -> int:
        return self.usable_gib - self.allocated_gib

    def allocate(self, gib: int) -> List[Tuple[str, int]]:
        """
        Allocate capacity across online disks.

        The placement is deliberately simple. It demonstrates that a virtual
        storage object does not need to know which physical disk holds its blocks.
        """
        if gib <= 0:
            raise ValidationError("Requested allocation must be positive.")
        if gib > self.free_gib:
            raise CapacityError(
                f"Pool {self.pool_id} has only {self.free_gib} GiB available."
            )

        remaining = gib
        placements: List[Tuple[str, int]] = []

        for disk in sorted(self.disks.values(), key=lambda d: d.free_gib, reverse=True):
            if disk.state == DeviceState.FAILED:
                continue

            amount = min(remaining, disk.free_gib)
            if amount:
                disk.allocate(amount)
                placements.append((disk.disk_id, amount))
                remaining -= amount

            if remaining == 0:
                break

        if remaining:
            # This should not happen after the free-capacity check, but rollback
            # protects the pool from partial allocation if placement logic changes.
            for disk_id, amount in placements:
                self.disks[disk_id].release(amount)
            raise CapacityError("Placement failed; allocation was rolled back.")

        return placements

    def release(self, placements: List[Tuple[str, int]]) -> None:
        for disk_id, amount in placements:
            if disk_id not in self.disks:
                raise NotFoundError(f"Disk {disk_id} no longer exists.")
            self.disks[disk_id].release(amount)

    def fail_disk(self, disk_id: str) -> None:
        disk = self.disks.get(disk_id)
        if not disk:
            raise NotFoundError(f"Disk {disk_id} does not exist.")
        disk.state = DeviceState.FAILED


@dataclass
class VirtualDisk:
    """
    A virtual disk is a logical block device backed by a storage pool.

    capacity_gib describes the capacity visible to a consumer. allocated_gib
    describes physical capacity actually consumed by the object.
    """

    disk_id: str
    pool_id: str
    capacity_gib: int
    volume_type: VolumeType
    placements: List[Tuple[str, int]]
    allocated_gib: int

    @property
    def logical_bytes(self) -> int:
        return self.capacity_gib * BYTES_PER_GIB

    @property
    def physical_bytes(self) -> int:
        return self.allocated_gib * BYTES_PER_GIB


@dataclass
class LogicalVolume:
    """
    Represents a logical volume exposed to an application.

    Blocks are stored as hashes plus data in this simulation. A real block device
    would return bytes through a kernel or storage protocol rather than keeping
    all blocks in a Python dictionary.
    """

    volume_id: str
    virtual_disk_id: str
    block_size: int
    logical_blocks: int
    blocks: Dict[int, bytes] = field(default_factory=dict)

    @property
    def capacity_bytes(self) -> int:
        return self.logical_blocks * self.block_size

    @property
    def used_blocks(self) -> int:
        return len(self.blocks)

    def validate_block(self, block_number: int, data: Optional[bytes] = None) -> None:
        if not 0 <= block_number < self.logical_blocks:
            raise ValidationError(
                f"Block {block_number} is outside volume {self.volume_id}."
            )
        if data is not None and len(data) > self.block_size:
            raise ValidationError(
                f"Block payload is {len(data)} bytes; maximum is {self.block_size}."
            )

    def write(self, block_number: int, data: bytes) -> None:
        self.validate_block(block_number, data)
        self.blocks[block_number] = data.ljust(self.block_size, b"\x00")

    def read(self, block_number: int) -> bytes:
        self.validate_block(block_number)
        return self.blocks.get(block_number, b"\x00" * self.block_size)

    def delete_block(self, block_number: int) -> None:
        self.validate_block(block_number)
        self.blocks.pop(block_number, None)


@dataclass
class Snapshot:
    """Point-in-time logical representation of a volume's mapped blocks."""

    snapshot_id: str
    source_volume_id: str
    blocks: Dict[int, bytes]
    created_generation: int


class StorageVirtualizationManager:
    """
    Coordinates storage-pool allocation and logical block-device operations.

    The manager intentionally keeps the public API at the virtualized layer:
    callers create a virtual disk and volume, then operate on logical blocks
    without specifying a physical disk.
    """

    def __init__(self) -> None:
        self.pools: Dict[str, StoragePool] = {}
        self.virtual_disks: Dict[str, VirtualDisk] = {}
        self.volumes: Dict[str, LogicalVolume] = {}
        self.snapshots: Dict[str, Snapshot] = {}
        self.generation = 0

    def create_pool(self, pool_id: str) -> StoragePool:
        if pool_id in self.pools:
            raise ValidationError(f"Pool {pool_id} already exists.")
        pool = StoragePool(pool_id)
        self.pools[pool_id] = pool
        return pool

    def create_virtual_disk(
        self,
        disk_id: str,
        pool_id: str,
        capacity_gib: int,
        volume_type: VolumeType = VolumeType.THICK,
    ) -> VirtualDisk:
        if disk_id in self.virtual_disks:
            raise ValidationError(f"Virtual disk {disk_id} already exists.")

        pool = self.pools.get(pool_id)
        if not pool:
            raise NotFoundError(f"Pool {pool_id} does not exist.")

        if capacity_gib <= 0:
            raise ValidationError("Virtual disk capacity must be positive.")

        # Thick provisioning reserves physical capacity immediately.
        # Thin provisioning exposes logical capacity while initially reserving
        # only a small allocation unit, allowing overcommit in the logical layer.
        physical_reservation = capacity_gib if volume_type == VolumeType.THICK else 0

        placements: List[Tuple[str, int]] = []
        if physical_reservation:
            placements = pool.allocate(physical_reservation)

        virtual_disk = VirtualDisk(
            disk_id=disk_id,
            pool_id=pool_id,
            capacity_gib=capacity_gib,
            volume_type=volume_type,
            placements=placements,
            allocated_gib=physical_reservation,
        )
        self.virtual_disks[disk_id] = virtual_disk
        return virtual_disk

    def create_volume(
        self,
        volume_id: str,
        virtual_disk_id: str,
        block_size: int = 4096,
    ) -> LogicalVolume:
        if volume_id in self.volumes:
            raise ValidationError(f"Volume {volume_id} already exists.")

        virtual_disk = self.virtual_disks.get(virtual_disk_id)
        if not virtual_disk:
            raise NotFoundError(f"Virtual disk {virtual_disk_id} does not exist.")

        if block_size <= 0 or block_size & (block_size - 1):
            raise ValidationError("Block size must be a positive power of two.")

        total_bytes = virtual_disk.logical_bytes
        logical_blocks = total_bytes // block_size

        if logical_blocks == 0:
            raise ValidationError("Virtual disk is smaller than one block.")

        volume = LogicalVolume(
            volume_id=volume_id,
            virtual_disk_id=virtual_disk_id,
            block_size=block_size,
            logical_blocks=logical_blocks,
        )
        self.volumes[volume_id] = volume
        return volume

    def _grow_thin_allocation(self, virtual_disk: VirtualDisk, volume: LogicalVolume) -> None:
        """
        Reserve physical storage for a new logical block on a thin disk.

        This simulation uses one GiB allocation units. Real systems often allocate
        extents or chunks rather than one physical reservation per block.
        """
        if virtual_disk.volume_type != VolumeType.THIN:
            return

        pool = self.pools[virtual_disk.pool_id]

        # The logical block is tiny compared with one GiB. We reserve a GiB the
        # first time the virtual disk needs physical space.
        allocation_unit_gib = 1
        placement = pool.allocate(allocation_unit_gib)
        virtual_disk.placements.extend(placement)
        virtual_disk.allocated_gib += allocation_unit_gib

        if virtual_disk.allocated_gib > virtual_disk.capacity_gib:
            pool.release(placement)
            virtual_disk.allocated_gib -= allocation_unit_gib
            virtual_disk.placements = virtual_disk.placements[:-len(placement)]
            raise CapacityError(
                f"Thin virtual disk {virtual_disk.disk_id} reached its logical limit."
            )

    def write_block(self, volume_id: str, block_number: int, data: bytes) -> None:
        volume = self.volumes.get(volume_id)
        if not volume:
            raise NotFoundError(f"Volume {volume_id} does not exist.")

        virtual_disk = self.virtual_disks[volume.virtual_disk_id]
        is_new_block = block_number not in volume.blocks

        volume.validate_block(block_number, data)

        if is_new_block and virtual_disk.volume_type == VolumeType.THIN:
            # Physical capacity grows only when data is actually written.
            self._grow_thin_allocation(virtual_disk, volume)

        volume.write(block_number, data)
        self.generation += 1

    def read_block(self, volume_id: str, block_number: int) -> bytes:
        volume = self.volumes.get(volume_id)
        if not volume:
            raise NotFoundError(f"Volume {volume_id} does not exist.")
        return volume.read(block_number)

    def snapshot(self, snapshot_id: str, volume_id: str) -> Snapshot:
        if snapshot_id in self.snapshots:
            raise ValidationError(f"Snapshot {snapshot_id} already exists.")

        volume = self.volumes.get(volume_id)
        if not volume:
            raise NotFoundError(f"Volume {volume_id} does not exist.")

        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            source_volume_id=volume_id,
            blocks=dict(volume.blocks),
            created_generation=self.generation,
        )
        self.snapshots[snapshot_id] = snapshot
        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> None:
        snapshot = self.snapshots.get(snapshot_id)
        if not snapshot:
            raise NotFoundError(f"Snapshot {snapshot_id} does not exist.")

        volume = self.volumes.get(snapshot.source_volume_id)
        if not volume:
            raise NotFoundError(
                f"Source volume {snapshot.source_volume_id} no longer exists."
            )

        virtual_disk = self.virtual_disks[volume.virtual_disk_id]

        # For a thin volume, restoration may require physical allocation for
        # blocks that no longer have backing storage.
        missing_blocks = set(snapshot.blocks) - set(volume.blocks)
        for _ in missing_blocks:
            self._grow_thin_allocation(virtual_disk, volume)

        volume.blocks = dict(snapshot.blocks)
        self.generation += 1

    def delete_volume(self, volume_id: str) -> None:
        volume = self.volumes.pop(volume_id, None)
        if not volume:
            raise NotFoundError(f"Volume {volume_id} does not exist.")

    def delete_virtual_disk(self, disk_id: str) -> None:
        virtual_disk = self.virtual_disks.pop(disk_id, None)
        if not virtual_disk:
            raise NotFoundError(f"Virtual disk {disk_id} does not exist.")

        pool = self.pools[virtual_disk.pool_id]
        pool.release(virtual_disk.placements)

    def report(self) -> None:
        print("\n=== STORAGE VIRTUALIZATION REPORT ===")

        for pool in self.pools.values():
            print(
                f"Pool {pool.pool_id}: "
                f"total={pool.total_gib} GiB, "
                f"usable={pool.usable_gib} GiB, "
                f"allocated={pool.allocated_gib} GiB, "
                f"free={pool.free_gib} GiB"
            )

            for disk in pool.disks.values():
                print(
                    f"  Physical disk {disk.disk_id}: "
                    f"{disk.capacity_gib} GiB, "
                    f"state={disk.state.value}, "
                    f"allocated={disk.allocated_gib} GiB"
                )

        for disk in self.virtual_disks.values():
            print(
                f"Virtual disk {disk.disk_id}: "
                f"logical={disk.capacity_gib} GiB, "
                f"type={disk.volume_type.value}, "
                f"physical={disk.allocated_gib} GiB"
            )

        for volume in self.volumes.values():
            print(
                f"Logical volume {volume.volume_id}: "
                f"capacity={volume.capacity_bytes / BYTES_PER_GIB:.2f} GiB, "
                f"used_blocks={volume.used_blocks}"
            )


def checksum(data: bytes) -> str:
    """SHA-256 is used only to verify simulated block integrity."""
    return hashlib.sha256(data).hexdigest()


def demonstrate_fundamentals() -> StorageVirtualizationManager:
    print("=== STORAGE VIRTUALIZATION CASE STUDY ===")

    manager = StorageVirtualizationManager()
    pool = manager.create_pool("pool-production")

    # Physical disks form the capacity substrate. Applications do not address
    # these disks directly once they have been incorporated into the pool.
    pool.add_disk(PhysicalDisk("disk-a", 20))
    pool.add_disk(PhysicalDisk("disk-b", 30))
    pool.add_disk(PhysicalDisk("disk-c", 50))

    # Thick provisioning reserves all requested physical capacity immediately.
    manager.create_virtual_disk(
        "vd-database",
        "pool-production",
        30,
        VolumeType.THICK,
    )

    database = manager.create_volume(
        "lv-database",
        "vd-database",
        block_size=4096,
    )

    payload = b"database page: customer_id=10042 status=ACTIVE"
    manager.write_block("lv-database", 12, payload)

    recovered = manager.read_block("lv-database", 12)
    print(f"Read block checksum: {checksum(recovered)}")
    print(f"Stored payload prefix: {recovered[:48]!r}")

    # Thin provisioning exposes logical capacity without reserving all backing
    # capacity. Physical usage increases as new blocks receive data.
    manager.create_virtual_disk(
        "vd-analytics",
        "pool-production",
        60,
        VolumeType.THIN,
    )
    analytics = manager.create_volume(
        "lv-analytics",
        "vd-analytics",
        block_size=4096,
    )

    print(f"Thin volume logical capacity: {analytics.capacity_bytes / BYTES_PER_GIB:.2f} GiB")
    print(
        "Thin virtual disk physical allocation before writes:",
        manager.virtual_disks["vd-analytics"].allocated_gib,
        "GiB",
    )

    manager.write_block(
        "lv-analytics",
        0,
        b"analytics event: purchase completed",
    )
    manager.write_block(
        "lv-analytics",
        900,
        b"analytics event: refund requested",
    )

    print(
        "Thin virtual disk physical allocation after writes:",
        manager.virtual_disks["vd-analytics"].allocated_gib,
        "GiB",
    )

    # Snapshots preserve the logical mapping visible at a particular generation.
    manager.snapshot("snap-before-update", "lv-database")
    manager.write_block(
        "lv-database",
        12,
        b"database page: customer_id=10042 status=SUSPENDED",
    )

    print("Current block:", manager.read_block("lv-database", 12)[:64])
    manager.restore_snapshot("snap-before-update")
    print("Restored block:", manager.read_block("lv-database", 12)[:64])

    manager.report()
    return manager


def demonstrate_validation(manager: StorageVirtualizationManager) -> None:
    print("\n=== VALIDATION AND FAILURE CONDITIONS ===")

    cases = [
        (
            "negative block",
            lambda: manager.read_block("lv-database", -1),
        ),
        (
            "block beyond capacity",
            lambda: manager.read_block(
                "lv-database",
                manager.volumes["lv-database"].logical_blocks,
            ),
        ),
        (
            "oversized block payload",
            lambda: manager.write_block(
                "lv-database",
                5,
                b"x" * 4097,
            ),
        ),
        (
            "unknown volume",
            lambda: manager.read_block("does-not-exist", 0),
        ),
    ]

    for name, operation in cases:
        try:
            operation()
        except StorageError as exc:
            print(f"{name}: rejected safely -> {exc}")


def demonstrate_capacity_failure() -> None:
    print("\n=== CAPACITY FAILURE ===")

    manager = StorageVirtualizationManager()
    pool = manager.create_pool("small-pool")
    pool.add_disk(PhysicalDisk("small-a", 5))
    pool.add_disk(PhysicalDisk("small-b", 5))

    manager.create_virtual_disk("vd-1", "small-pool", 8, VolumeType.THICK)

    try:
        manager.create_virtual_disk("vd-2", "small-pool", 3, VolumeType.THICK)
    except CapacityError as exc:
        print(f"Expected capacity rejection: {exc}")

    manager.report()


def demonstrate_disk_failure() -> None:
    print("\n=== PHYSICAL DISK FAILURE AND POOL USABILITY ===")

    manager = StorageVirtualizationManager()
    pool = manager.create_pool("resiliency-pool")
    pool.add_disk(PhysicalDisk("node-1-disk", 25))
    pool.add_disk(PhysicalDisk("node-2-disk", 25))
    pool.add_disk(PhysicalDisk("node-3-disk", 25))

    manager.create_virtual_disk(
        "vd-logs",
        "resiliency-pool",
        50,
        VolumeType.THICK,
    )

    print(f"Usable capacity before failure: {pool.usable_gib} GiB")
    pool.fail_disk("node-3-disk")
    print(f"Usable capacity after failure: {pool.usable_gib} GiB")

    # This model does not pretend that capacity availability equals data
    # availability. A real redundant pool needs RAID, replication, or erasure
    # coding to reconstruct data after physical-device loss.
    print(
        "Important distinction: this simulation tracks pool capacity, "
        "not redundant data reconstruction."
    )


def run_consistency_tests() -> None:
    print("\n=== CONSISTENCY TESTS ===")

    manager = StorageVirtualizationManager()
    pool = manager.create_pool("test-pool")
    pool.add_disk(PhysicalDisk("t1", 10))
    pool.add_disk(PhysicalDisk("t2", 10))

    thick = manager.create_virtual_disk(
        "test-thick",
        "test-pool",
        8,
        VolumeType.THICK,
    )
    assert thick.allocated_gib == 8

    volume = manager.create_volume("test-volume", "test-thick")
    test_data = b"block integrity test"
    manager.write_block("test-volume", 7, test_data)
    assert manager.read_block("test-volume", 7).startswith(test_data)

    snapshot = manager.snapshot("test-snapshot", "test-volume")
    assert snapshot.blocks[7].startswith(test_data)

    manager.write_block("test-volume", 7, b"changed")
    assert manager.read_block("test-volume", 7).startswith(b"changed")

    manager.restore_snapshot("test-snapshot")
    assert manager.read_block("test-volume", 7).startswith(test_data)

    try:
        manager.read_block("test-volume", volume.logical_blocks)
    except ValidationError:
        pass
    else:
        raise AssertionError("Out-of-range access was not rejected.")

    print("All consistency tests passed.")


def explain_capacity_math() -> None:
    print("\n=== CAPACITY MATH ===")

    logical_capacity_gib = 100
    block_size = 4096
    blocks = (logical_capacity_gib * BYTES_PER_GIB) // block_size

    print(f"Logical capacity: {logical_capacity_gib} GiB")
    print(f"Block size: {block_size} bytes")
    print(f"Addressable blocks: {blocks:,}")

    # A storage system often works with extents or allocation units rather than
    # individual blocks. Rounding matters when converting logical sizes.
    extent_mib = 4
    extents = ceil(logical_capacity_gib * 1024 / extent_mib)
    print(f"4 MiB extents required: {extents:,}")


def demonstrate_allocation_strategy() -> None:
    print("\n=== SIMPLE PLACEMENT STRATEGY ===")

    pool = StoragePool("placement-demo")
    pool.add_disk(PhysicalDisk("p1", 12))
    pool.add_disk(PhysicalDisk("p2", 30))
    pool.add_disk(PhysicalDisk("p3", 18))

    placements = pool.allocate(40)
    print("Requested 40 GiB.")
    print("Physical placements:", placements)

    pool.release(placements)
    print("Capacity after release:", pool.free_gib, "GiB")


def main() -> None:
    # Seed is fixed so any future extension using randomized placement can be
    # reproduced during debugging.
    random.seed(42)

    manager = demonstrate_fundamentals()
    demonstrate_validation(manager)
    demonstrate_capacity_failure()
    demonstrate_disk_failure()
    demonstrate_allocation_strategy()
    explain_capacity_math()
    run_consistency_tests()

    print("\n=== OPERATIONAL MODEL ===")
    print(
        "The abstraction boundary is: applications see logical blocks, "
        "virtual disks map those blocks to a storage pool, and the pool manages "
        "physical capacity."
    )
    print(
        "Production systems must add redundancy, persistent metadata, crash "
        "recovery, I/O scheduling, encryption, authentication, monitoring, "
        "quotas, and durable metadata journaling."
    )


if __name__ == "__main__":
    main()
