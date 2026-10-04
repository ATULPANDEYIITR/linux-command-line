import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/*
 * StorageVirtualization.java
 *
 * Enterprise-oriented storage virtualization model.
 *
 * Domain flow:
 * PhysicalDisk -> StoragePool -> VirtualDisk -> LogicalVolume -> Block
 *
 * The Java implementation uses explicit domain types, immutable records for
 * placement metadata, enums for state, service classes for orchestration, and
 * custom exceptions for invalid storage operations.
 *
 * Compile:
 *   javac StorageVirtualization.java
 *
 * Run:
 *   java StorageVirtualization
 */
public class StorageVirtualization {

    private static final long BYTES_PER_GIB = 1024L * 1024L * 1024L;

    enum DiskState {
        ONLINE,
        DEGRADED,
        FAILED
    }

    enum ProvisioningType {
        THICK,
        THIN
    }

    static class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    static class CapacityException extends StorageException {
        CapacityException(String message) {
            super(message);
        }
    }

    static class ValidationException extends StorageException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class NotFoundException extends StorageException {
        NotFoundException(String message) {
            super(message);
        }
    }

    record PhysicalExtent(String diskId, long sizeGiB) {
        PhysicalExtent {
            Objects.requireNonNull(diskId, "diskId");

            if (sizeGiB <= 0) {
                throw new IllegalArgumentException(
                    "Physical extent size must be positive"
                );
            }
        }
    }

    static final class PhysicalDisk {
        private final String id;
        private final long capacityGiB;
        private long allocatedGiB;
        private DiskState state;

        PhysicalDisk(String id, long capacityGiB) {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Disk ID is required");
            }

            if (capacityGiB <= 0) {
                throw new ValidationException(
                    "Physical disk capacity must be positive"
                );
            }

            this.id = id;
            this.capacityGiB = capacityGiB;
            this.state = DiskState.ONLINE;
        }

        String id() {
            return id;
        }

        long capacityGiB() {
            return capacityGiB;
        }

        long allocatedGiB() {
            return allocatedGiB;
        }

        long freeGiB() {
            return capacityGiB - allocatedGiB;
        }

        DiskState state() {
            return state;
        }

        void allocate(long amountGiB) {
            if (state == DiskState.FAILED) {
                throw new StorageException(
                    "Disk " + id + " is failed"
                );
            }

            if (amountGiB <= 0 || amountGiB > freeGiB()) {
                throw new CapacityException(
                    "Disk " + id + " cannot allocate " + amountGiB + " GiB"
                );
            }

            allocatedGiB += amountGiB;
        }

        void release(long amountGiB) {
            if (amountGiB <= 0 || amountGiB > allocatedGiB) {
                throw new ValidationException(
                    "Invalid release on disk " + id
                );
            }

            allocatedGiB -= amountGiB;
        }

        void fail() {
            state = DiskState.FAILED;
        }
    }

    static final class StoragePool {
        private final String id;
        private final Map<String, PhysicalDisk> disks = new LinkedHashMap<>();

        StoragePool(String id) {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Pool ID is required");
            }

            this.id = id;
        }

        String id() {
            return id;
        }

        void addDisk(PhysicalDisk disk) {
            if (disks.containsKey(disk.id())) {
                throw new ValidationException(
                    "Duplicate disk " + disk.id()
                );
            }

            disks.put(disk.id(), disk);
        }

        long totalGiB() {
            return disks.values()
                .stream()
                .mapToLong(PhysicalDisk::capacityGiB)
                .sum();
        }

        long usableGiB() {
            return disks.values()
                .stream()
                .filter(disk -> disk.state() != DiskState.FAILED)
                .mapToLong(PhysicalDisk::capacityGiB)
                .sum();
        }

        long allocatedGiB() {
            return disks.values()
                .stream()
                .mapToLong(PhysicalDisk::allocatedGiB)
                .sum();
        }

        long freeGiB() {
            return usableGiB() - allocatedGiB();
        }

        List<PhysicalExtent> allocate(long amountGiB) {
            if (amountGiB <= 0) {
                throw new ValidationException(
                    "Pool allocation must be positive"
                );
            }

            if (amountGiB > freeGiB()) {
                throw new CapacityException(
                    "Pool " + id + " has only " + freeGiB()
                    + " GiB free"
                );
            }

            List<PhysicalDisk> candidates = disks.values()
                .stream()
                .filter(disk -> disk.state() != DiskState.FAILED)
                .sorted(
                    Comparator.comparingLong(
                        PhysicalDisk::freeGiB
                    ).reversed()
                )
                .toList();

            long remaining = amountGiB;
            List<PhysicalExtent> extents = new ArrayList<>();

            for (PhysicalDisk disk : candidates) {
                long allocation = Math.min(
                    remaining,
                    disk.freeGiB()
                );

                if (allocation > 0) {
                    disk.allocate(allocation);
                    extents.add(
                        new PhysicalExtent(disk.id(), allocation)
                    );
                    remaining -= allocation;
                }

                if (remaining == 0) {
                    break;
                }
            }

            if (remaining != 0) {
                for (PhysicalExtent extent : extents) {
                    disks.get(extent.diskId())
                        .release(extent.sizeGiB());
                }

                throw new CapacityException(
                    "Pool allocation was rolled back"
                );
            }

            return extents;
        }

        void release(List<PhysicalExtent> extents) {
            for (PhysicalExtent extent : extents) {
                PhysicalDisk disk = disks.get(extent.diskId());

                if (disk == null) {
                    throw new NotFoundException(
                        "Disk " + extent.diskId() + " does not exist"
                    );
                }

                disk.release(extent.sizeGiB());
            }
        }

        void failDisk(String diskId) {
            PhysicalDisk disk = disks.get(diskId);

            if (disk == null) {
                throw new NotFoundException(
                    "Disk " + diskId + " does not exist"
                );
            }

            disk.fail();
        }

        void printStatus() {
            System.out.println(
                "Pool " + id
                + " total=" + totalGiB()
                + " GiB usable=" + usableGiB()
                + " GiB allocated=" + allocatedGiB()
                + " GiB free=" + freeGiB()
                + " GiB"
            );

            disks.values().forEach(disk ->
                System.out.println(
                    "  " + disk.id()
                    + " capacity=" + disk.capacityGiB()
                    + " GiB allocated=" + disk.allocatedGiB()
                    + " GiB state=" + disk.state()
                )
            );
        }
    }

    static final class VirtualDisk {
        private final String id;
        private final String poolId;
        private final long logicalCapacityGiB;
        private final ProvisioningType provisioningType;
        private final List<PhysicalExtent> extents;
        private long physicalAllocationGiB;

        VirtualDisk(
            String id,
            String poolId,
            long logicalCapacityGiB,
            ProvisioningType provisioningType,
            List<PhysicalExtent> extents,
            long physicalAllocationGiB
        ) {
            this.id = id;
            this.poolId = poolId;
            this.logicalCapacityGiB = logicalCapacityGiB;
            this.provisioningType = provisioningType;
            this.extents = new ArrayList<>(extents);
            this.physicalAllocationGiB = physicalAllocationGiB;
        }

        String id() {
            return id;
        }

        String poolId() {
            return poolId;
        }

        long logicalCapacityGiB() {
            return logicalCapacityGiB;
        }

        long physicalAllocationGiB() {
            return physicalAllocationGiB;
        }

        ProvisioningType provisioningType() {
            return provisioningType;
        }

        List<PhysicalExtent> extents() {
            return List.copyOf(extents);
        }

        void addExtents(List<PhysicalExtent> newExtents) {
            extents.addAll(newExtents);
            physicalAllocationGiB += newExtents.stream()
                .mapToLong(PhysicalExtent::sizeGiB)
                .sum();
        }
    }

    record BlockRecord(String data, boolean allocated) {
        BlockRecord {
            Objects.requireNonNull(data, "data");
        }
    }

    static final class LogicalVolume {
        private final String id;
        private final String virtualDiskId;
        private final int blockSize;
        private final long blockCount;
        private Map<Long, BlockRecord> blocks = new HashMap<>();

        LogicalVolume(
            String id,
            String virtualDiskId,
            int blockSize,
            long blockCount
        ) {
            this.id = id;
            this.virtualDiskId = virtualDiskId;
            this.blockSize = blockSize;
            this.blockCount = blockCount;
        }

        String id() {
            return id;
        }

        String virtualDiskId() {
            return virtualDiskId;
        }

        int blockSize() {
            return blockSize;
        }

        long blockCount() {
            return blockCount;
        }

        long allocatedBlockCount() {
            return blocks.size();
        }

        void validateBlock(long blockNumber) {
            if (blockNumber < 0 || blockNumber >= blockCount) {
                throw new ValidationException(
                    "Block " + blockNumber
                    + " is outside logical volume " + id
                );
            }
        }

        void write(long blockNumber, String data) {
            validateBlock(blockNumber);

            if (data.getBytes().length > blockSize) {
                throw new ValidationException(
                    "Data exceeds logical block size"
                );
            }

            blocks.put(
                blockNumber,
                new BlockRecord(data, true)
            );
        }

        String read(long blockNumber) {
            validateBlock(blockNumber);

            return Optional.ofNullable(blocks.get(blockNumber))
                .map(BlockRecord::data)
                .orElse("");
        }

        Map<Long, BlockRecord> copyBlocks() {
            return new HashMap<>(blocks);
        }

        void restore(Map<Long, BlockRecord> snapshotBlocks) {
            blocks = new HashMap<>(snapshotBlocks);
        }
    }

    record Snapshot(
        String id,
        String sourceVolumeId,
        Map<Long, BlockRecord> blocks
    ) {
        Snapshot {
            blocks = Map.copyOf(blocks);
        }
    }

    static final class StorageService {
        private final Map<String, StoragePool> pools = new LinkedHashMap<>();
        private final Map<String, VirtualDisk> virtualDisks =
            new LinkedHashMap<>();
        private final Map<String, LogicalVolume> volumes =
            new LinkedHashMap<>();
        private final Map<String, Snapshot> snapshots =
            new LinkedHashMap<>();

        StoragePool createPool(String id) {
            if (pools.containsKey(id)) {
                throw new ValidationException(
                    "Pool already exists: " + id
                );
            }

            StoragePool pool = new StoragePool(id);
            pools.put(id, pool);
            return pool;
        }

        VirtualDisk createVirtualDisk(
            String id,
            String poolId,
            long capacityGiB,
            ProvisioningType type
        ) {
            if (virtualDisks.containsKey(id)) {
                throw new ValidationException(
                    "Virtual disk already exists: " + id
                );
            }

            if (capacityGiB <= 0) {
                throw new ValidationException(
                    "Virtual disk capacity must be positive"
                );
            }

            StoragePool pool = getPool(poolId);

            List<PhysicalExtent> extents = type == ProvisioningType.THICK
                ? pool.allocate(capacityGiB)
                : List.of();

            long physicalAllocation =
                type == ProvisioningType.THICK
                    ? capacityGiB
                    : 0;

            VirtualDisk disk = new VirtualDisk(
                id,
                poolId,
                capacityGiB,
                type,
                extents,
                physicalAllocation
            );

            virtualDisks.put(id, disk);
            return disk;
        }

        LogicalVolume createLogicalVolume(
            String id,
            String virtualDiskId,
            int blockSize
        ) {
            if (volumes.containsKey(id)) {
                throw new ValidationException(
                    "Logical volume already exists: " + id
                );
            }

            if (blockSize <= 0 ||
                (blockSize & (blockSize - 1)) != 0) {
                throw new ValidationException(
                    "Block size must be a power of two"
                );
            }

            VirtualDisk disk = getVirtualDisk(virtualDiskId);
            long blockCount =
                (disk.logicalCapacityGiB() * BYTES_PER_GIB)
                / blockSize;

            if (blockCount <= 0) {
                throw new ValidationException(
                    "Logical volume has no addressable blocks"
                );
            }

            LogicalVolume volume = new LogicalVolume(
                id,
                virtualDiskId,
                blockSize,
                blockCount
            );

            volumes.put(id, volume);
            return volume;
        }

        private void ensureThinBacking(
            VirtualDisk disk
        ) {
            if (disk.provisioningType() != ProvisioningType.THIN) {
                return;
            }

            if (disk.physicalAllocationGiB() >=
                disk.logicalCapacityGiB()) {
                throw new CapacityException(
                    "Thin virtual disk has reached its logical capacity"
                );
            }

            StoragePool pool = getPool(disk.poolId());

            List<PhysicalExtent> extents = pool.allocate(1);
            disk.addExtents(extents);
        }

        void writeBlock(
            String volumeId,
            long blockNumber,
            String data
        ) {
            LogicalVolume volume = getVolume(volumeId);
            volume.validateBlock(blockNumber);

            boolean firstWrite =
                volume.allocatedBlockCount() == 0
                || !volume.copyBlocks().containsKey(blockNumber);

            if (firstWrite) {
                ensureThinBacking(
                    getVirtualDisk(volume.virtualDiskId())
                );
            }

            volume.write(blockNumber, data);
        }

        String readBlock(
            String volumeId,
            long blockNumber
        ) {
            return getVolume(volumeId).read(blockNumber);
        }

        void createSnapshot(
            String snapshotId,
            String volumeId
        ) {
            if (snapshots.containsKey(snapshotId)) {
                throw new ValidationException(
                    "Snapshot already exists: " + snapshotId
                );
            }

            LogicalVolume volume = getVolume(volumeId);

            snapshots.put(
                snapshotId,
                new Snapshot(
                    snapshotId,
                    volumeId,
                    volume.copyBlocks()
                )
            );
        }

        void restoreSnapshot(String snapshotId) {
            Snapshot snapshot = snapshots.get(snapshotId);

            if (snapshot == null) {
                throw new NotFoundException(
                    "Snapshot does not exist: " + snapshotId
                );
            }

            getVolume(snapshot.sourceVolumeId())
                .restore(snapshot.blocks());
        }

        StoragePool getPool(String id) {
            StoragePool pool = pools.get(id);

            if (pool == null) {
                throw new NotFoundException(
                    "Pool does not exist: " + id
                );
            }

            return pool;
        }

        VirtualDisk getVirtualDisk(String id) {
            VirtualDisk disk = virtualDisks.get(id);

            if (disk == null) {
                throw new NotFoundException(
                    "Virtual disk does not exist: " + id
                );
            }

            return disk;
        }

        LogicalVolume getVolume(String id) {
            LogicalVolume volume = volumes.get(id);

            if (volume == null) {
                throw new NotFoundException(
                    "Logical volume does not exist: " + id
                );
            }

            return volume;
        }

        void report() {
            System.out.println("\n=== ENTERPRISE STORAGE REPORT ===");

            pools.values().forEach(StoragePool::printStatus);

            System.out.println("\nVirtual disks:");

            virtualDisks.values().forEach(disk ->
                System.out.println(
                    "  " + disk.id()
                    + " logical=" + disk.logicalCapacityGiB()
                    + " GiB physical=" + disk.physicalAllocationGiB()
                    + " GiB type=" + disk.provisioningType()
                )
            );

            System.out.println("\nLogical volumes:");

            volumes.values().forEach(volume ->
                System.out.println(
                    "  " + volume.id()
                    + " blocks=" + volume.blockCount()
                    + " allocatedBlocks="
                    + volume.allocatedBlockCount()
                )
            );
        }
    }

    static void demonstrate() {
        System.out.println(
            "=== STORAGE VIRTUALIZATION ENTERPRISE CASE STUDY ==="
        );

        StorageService service = new StorageService();

        StoragePool pool = service.createPool("production-block-pool");

        pool.addDisk(new PhysicalDisk("array-a", 50));
        pool.addDisk(new PhysicalDisk("array-b", 50));
        pool.addDisk(new PhysicalDisk("array-c", 50));

        /*
         * The transaction database receives a thick virtual disk. The tenant
         * is guaranteed a 70 GiB logical device because that capacity is
         * reserved from the pool at creation time.
         */
        VirtualDisk databaseDisk = service.createVirtualDisk(
            "vd-transactions",
            pool.id(),
            70,
            ProvisioningType.THICK
        );

        LogicalVolume database = service.createLogicalVolume(
            "lv-transactions",
            databaseDisk.id(),
            4096
        );

        service.writeBlock(
            database.id(),
            44,
            "transaction=TX-2026-8842;state=SETTLED"
        );

        System.out.println(
            "Database block: "
            + service.readBlock(database.id(), 44)
        );

        /*
         * Analytics receives a thin-provisioned logical address space. The
         * platform exposes 100 GiB while physical allocation starts at zero.
         */
        VirtualDisk analyticsDisk = service.createVirtualDisk(
            "vd-analytics",
            pool.id(),
            100,
            ProvisioningType.THIN
        );

        LogicalVolume analytics = service.createLogicalVolume(
            "lv-analytics",
            analyticsDisk.id(),
            4096
        );

        System.out.println(
            "Analytics physical allocation before writes: "
            + analyticsDisk.physicalAllocationGiB()
            + " GiB"
        );

        service.writeBlock(
            analytics.id(),
            10_000,
            "metric=revenue;month=2026-09"
        );

        service.writeBlock(
            analytics.id(),
            10_001,
            "metric=retention;month=2026-09"
        );

        System.out.println(
            "Analytics physical allocation after writes: "
            + analyticsDisk.physicalAllocationGiB()
            + " GiB"
        );

        /*
         * Snapshot behavior belongs to the logical-volume layer. The snapshot
         * preserves the logical mapping as it existed at creation time.
         */
        service.createSnapshot(
            "transaction-before-correction",
            database.id()
        );

        service.writeBlock(
            database.id(),
            44,
            "transaction=TX-2026-8842;state=REVERSED"
        );

        System.out.println(
            "Changed transaction: "
            + service.readBlock(database.id(), 44)
        );

        service.restoreSnapshot(
            "transaction-before-correction"
        );

        System.out.println(
            "Restored transaction: "
            + service.readBlock(database.id(), 44)
        );

        service.report();

        System.out.println("\n=== POLICY AND FAILURE VALIDATION ===");

        try {
            service.readBlock(
                database.id(),
                database.blockCount()
            );
        } catch (StorageException exception) {
            System.out.println(
                "Boundary validation: " + exception.getMessage()
            );
        }

        try {
            service.writeBlock(
                database.id(),
                1,
                "x".repeat(5000)
            );
        } catch (StorageException exception) {
            System.out.println(
                "Block-size validation: " + exception.getMessage()
            );
        }

        try {
            service.createVirtualDisk(
                "vd-capacity-error",
                pool.id(),
                500,
                ProvisioningType.THICK
            );
        } catch (StorageException exception) {
            System.out.println(
                "Capacity validation: " + exception.getMessage()
            );
        }

        pool.failDisk("array-c");

        System.out.println(
            "Usable pool capacity after disk failure: "
            + pool.usableGiB()
            + " GiB"
        );

        System.out.println(
            "A failed device is not automatically recoverable merely because "
            + "the pool knows about the failure. Data redundancy requires "
            + "replication, RAID, or erasure coding."
        );
    }

    public static void main(String[] args) {
        try {
            demonstrate();
        } catch (StorageException exception) {
            System.err.println(
                "Storage operation failed: "
                + exception.getMessage()
            );
            System.exit(1);
        }
    }
}
