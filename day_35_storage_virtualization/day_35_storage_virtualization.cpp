#include <algorithm>
#include <cassert>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Storage Virtualization Governance Case Study
 *
 * Scenario:
 * A private cloud platform provides block storage to application teams.
 * Physical disks are aggregated into storage pools. Tenants receive virtual
 * disks, and logical volumes expose addressable blocks without revealing the
 * physical placement.
 *
 * The program focuses on a C++-appropriate systems perspective:
 * - explicit domain types
 * - deterministic allocation
 * - ownership and lifetime through value types
 * - exception-based validation
 * - capacity accounting
 * - virtual-to-physical block mapping
 * - thin provisioning
 * - snapshot metadata
 * - health/failure state
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic storage_virtualization.cpp -o storage
 */

namespace storage {

constexpr std::uint64_t GiB = 1024ULL * 1024ULL * 1024ULL;

class StorageError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class CapacityError : public StorageError {
public:
    using StorageError::StorageError;
};

class ValidationError : public StorageError {
public:
    using StorageError::StorageError;
};

class NotFoundError : public StorageError {
public:
    using StorageError::StorageError;
};

enum class DiskState {
    Online,
    Degraded,
    Failed
};

enum class Provisioning {
    Thick,
    Thin
};

enum class BlockState {
    Unallocated,
    Allocated
};

struct PhysicalExtent {
    std::string diskId;
    std::uint64_t sizeGiB{};
};

struct PhysicalDisk {
    std::string id;
    std::uint64_t capacityGiB{};
    std::uint64_t allocatedGiB{};
    DiskState state{DiskState::Online};

    std::uint64_t freeGiB() const {
        return capacityGiB - allocatedGiB;
    }

    void allocate(std::uint64_t amount) {
        if (state == DiskState::Failed) {
            throw StorageError("Cannot allocate from failed disk " + id);
        }

        if (amount > freeGiB()) {
            throw CapacityError("Disk " + id + " lacks requested capacity");
        }

        allocatedGiB += amount;
    }

    void release(std::uint64_t amount) {
        if (amount > allocatedGiB) {
            throw ValidationError("Disk " + id + " release exceeds allocation");
        }

        allocatedGiB -= amount;
    }
};

class StoragePool {
private:
    std::string id_;
    std::map<std::string, PhysicalDisk> disks_;

public:
    explicit StoragePool(std::string id) : id_(std::move(id)) {}

    const std::string& id() const {
        return id_;
    }

    void addDisk(const PhysicalDisk& disk) {
        if (disk.capacityGiB == 0) {
            throw ValidationError("A storage disk must have positive capacity");
        }

        if (disks_.contains(disk.id)) {
            throw ValidationError("Duplicate physical disk " + disk.id);
        }

        disks_.emplace(disk.id, disk);
    }

    std::uint64_t totalGiB() const {
        std::uint64_t result = 0;

        for (const auto& [id, disk] : disks_) {
            result += disk.capacityGiB;
        }

        return result;
    }

    std::uint64_t usableGiB() const {
        std::uint64_t result = 0;

        for (const auto& [id, disk] : disks_) {
            if (disk.state != DiskState::Failed) {
                result += disk.capacityGiB;
            }
        }

        return result;
    }

    std::uint64_t allocatedGiB() const {
        std::uint64_t result = 0;

        for (const auto& [id, disk] : disks_) {
            result += disk.allocatedGiB;
        }

        return result;
    }

    std::uint64_t freeGiB() const {
        return usableGiB() - allocatedGiB();
    }

    std::vector<PhysicalExtent> allocate(std::uint64_t amount) {
        if (amount == 0) {
            throw ValidationError("Allocation must be greater than zero");
        }

        if (amount > freeGiB()) {
            throw CapacityError(
                "Pool " + id_ + " has insufficient free capacity"
            );
        }

        // Largest-free-first minimizes unnecessary fragmentation in this
        // small model. Production placement also considers fault domains,
        // device classes, latency, wear, and redundancy requirements.
        std::vector<std::reference_wrapper<PhysicalDisk>> candidates;

        for (auto& [id, disk] : disks_) {
            if (disk.state != DiskState::Failed) {
                candidates.push_back(disk);
            }
        }

        std::sort(
            candidates.begin(),
            candidates.end(),
            [](const auto& left, const auto& right) {
                return left.get().freeGiB() > right.get().freeGiB();
            }
        );

        std::uint64_t remaining = amount;
        std::vector<PhysicalExtent> result;

        for (auto& reference : candidates) {
            auto& disk = reference.get();
            const std::uint64_t placement =
                std::min(remaining, disk.freeGiB());

            if (placement > 0) {
                disk.allocate(placement);
                result.push_back({disk.id, placement});
                remaining -= placement;
            }

            if (remaining == 0) {
                break;
            }
        }

        if (remaining != 0) {
            for (const auto& extent : result) {
                disks_.at(extent.diskId).release(extent.sizeGiB);
            }

            throw CapacityError("Allocation transaction was rolled back");
        }

        return result;
    }

    void release(const std::vector<PhysicalExtent>& extents) {
        for (const auto& extent : extents) {
            auto iterator = disks_.find(extent.diskId);

            if (iterator == disks_.end()) {
                throw NotFoundError(
                    "Physical disk " + extent.diskId + " no longer exists"
                );
            }

            iterator->second.release(extent.sizeGiB);
        }
    }

    void failDisk(const std::string& diskId) {
        auto iterator = disks_.find(diskId);

        if (iterator == disks_.end()) {
            throw NotFoundError("Physical disk " + diskId + " does not exist");
        }

        iterator->second.state = DiskState::Failed;
    }

    void print() const {
        std::cout << "Storage pool: " << id_ << '\n'
                  << "  total:     " << totalGiB() << " GiB\n"
                  << "  usable:    " << usableGiB() << " GiB\n"
                  << "  allocated: " << allocatedGiB() << " GiB\n"
                  << "  free:      " << freeGiB() << " GiB\n";

        for (const auto& [id, disk] : disks_) {
            std::string state;

            switch (disk.state) {
                case DiskState::Online:
                    state = "online";
                    break;
                case DiskState::Degraded:
                    state = "degraded";
                    break;
                case DiskState::Failed:
                    state = "failed";
                    break;
            }

            std::cout << "  disk " << id
                      << ": capacity=" << disk.capacityGiB
                      << " GiB, allocated=" << disk.allocatedGiB
                      << " GiB, state=" << state << '\n';
        }
    }
};

struct VirtualDisk {
    std::string id;
    std::string poolId;
    std::uint64_t logicalCapacityGiB{};
    std::uint64_t physicalAllocationGiB{};
    Provisioning provisioning{Provisioning::Thick};
    std::vector<PhysicalExtent> extents;
};

struct Block {
    BlockState state{BlockState::Unallocated};
    std::string payload;
    std::optional<PhysicalExtent> backing;
};

struct LogicalVolume {
    std::string id;
    std::string virtualDiskId;
    std::uint64_t blockSize{};
    std::uint64_t blockCount{};
    std::map<std::uint64_t, Block> blocks;
};

struct Snapshot {
    std::string id;
    std::string volumeId;
    std::map<std::uint64_t, Block> blocks;
};

class BlockStorageEngine {
private:
    std::map<std::string, StoragePool> pools_;
    std::map<std::string, VirtualDisk> virtualDisks_;
    std::map<std::string, LogicalVolume> volumes_;
    std::map<std::string, Snapshot> snapshots_;

    static void validateBlock(
        const LogicalVolume& volume,
        std::uint64_t blockNumber
    ) {
        if (blockNumber >= volume.blockCount) {
            throw ValidationError(
                "Block " + std::to_string(blockNumber)
                + " exceeds logical volume boundary"
            );
        }
    }

public:
    StoragePool& createPool(const std::string& poolId) {
        if (pools_.contains(poolId)) {
            throw ValidationError("Pool already exists: " + poolId);
        }

        auto [iterator, inserted] =
            pools_.emplace(std::piecewise_construct,
                           std::forward_as_tuple(poolId),
                           std::forward_as_tuple(poolId));

        return iterator->second;
    }

    VirtualDisk& createVirtualDisk(
        const std::string& diskId,
        const std::string& poolId,
        std::uint64_t capacityGiB,
        Provisioning provisioning
    ) {
        if (virtualDisks_.contains(diskId)) {
            throw ValidationError("Virtual disk already exists: " + diskId);
        }

        auto poolIterator = pools_.find(poolId);

        if (poolIterator == pools_.end()) {
            throw NotFoundError("Unknown pool: " + poolId);
        }

        if (capacityGiB == 0) {
            throw ValidationError("Virtual disk capacity must be positive");
        }

        std::vector<PhysicalExtent> extents;
        std::uint64_t physicalAllocation = 0;

        if (provisioning == Provisioning::Thick) {
            extents = poolIterator->second.allocate(capacityGiB);
            physicalAllocation = capacityGiB;
        }

        VirtualDisk disk{
            diskId,
            poolId,
            capacityGiB,
            physicalAllocation,
            provisioning,
            std::move(extents)
        };

        auto [iterator, inserted] =
            virtualDisks_.emplace(diskId, std::move(disk));

        return iterator->second;
    }

    LogicalVolume& createVolume(
        const std::string& volumeId,
        const std::string& virtualDiskId,
        std::uint64_t blockSize
    ) {
        if (volumes_.contains(volumeId)) {
            throw ValidationError("Logical volume already exists: " + volumeId);
        }

        auto diskIterator = virtualDisks_.find(virtualDiskId);

        if (diskIterator == virtualDisks_.end()) {
            throw NotFoundError("Unknown virtual disk: " + virtualDiskId);
        }

        if (blockSize == 0 || (blockSize & (blockSize - 1)) != 0) {
            throw ValidationError("Block size must be a power of two");
        }

        const std::uint64_t bytes =
            diskIterator->second.logicalCapacityGiB * GiB;

        const std::uint64_t blockCount = bytes / blockSize;

        if (blockCount == 0) {
            throw ValidationError("Volume cannot contain zero blocks");
        }

        LogicalVolume volume{
            volumeId,
            virtualDiskId,
            blockSize,
            blockCount,
            {}
        };

        auto [iterator, inserted] =
            volumes_.emplace(volumeId, std::move(volume));

        return iterator->second;
    }

    void ensureThinCapacity(VirtualDisk& disk) {
        if (disk.provisioning != Provisioning::Thin) {
            return;
        }

        auto poolIterator = pools_.find(disk.poolId);

        if (poolIterator == pools_.end()) {
            throw NotFoundError("Backing pool disappeared");
        }

        // Extents are intentionally one GiB here. Real thin-provisioning
        // systems commonly use much smaller configurable allocation chunks.
        constexpr std::uint64_t allocationUnit = 1;

        if (disk.physicalAllocationGiB + allocationUnit >
            disk.logicalCapacityGiB) {
            throw CapacityError(
                "Thin virtual disk has reached its logical capacity"
            );
        }

        auto extents = poolIterator->second.allocate(allocationUnit);

        disk.extents.insert(
            disk.extents.end(),
            extents.begin(),
            extents.end()
        );

        disk.physicalAllocationGiB += allocationUnit;
    }

    void write(
        const std::string& volumeId,
        std::uint64_t blockNumber,
        const std::string& payload
    ) {
        auto volumeIterator = volumes_.find(volumeId);

        if (volumeIterator == volumes_.end()) {
            throw NotFoundError("Unknown logical volume: " + volumeId);
        }

        auto& volume = volumeIterator->second;
        validateBlock(volume, blockNumber);

        if (payload.size() > volume.blockSize) {
            throw ValidationError("Payload exceeds block size");
        }

        auto diskIterator = virtualDisks_.find(volume.virtualDiskId);

        if (diskIterator == virtualDisks_.end()) {
            throw NotFoundError("Backing virtual disk does not exist");
        }

        auto blockIterator = volume.blocks.find(blockNumber);
        const bool firstWrite = blockIterator == volume.blocks.end();

        if (firstWrite) {
            ensureThinCapacity(diskIterator->second);

            Block block;
            block.state = BlockState::Allocated;
            block.payload = payload;

            volume.blocks.emplace(blockNumber, std::move(block));
        } else {
            blockIterator->second.payload = payload;
        }
    }

    std::string read(
        const std::string& volumeId,
        std::uint64_t blockNumber
    ) const {
        auto volumeIterator = volumes_.find(volumeId);

        if (volumeIterator == volumes_.end()) {
            throw NotFoundError("Unknown logical volume: " + volumeId);
        }

        const auto& volume = volumeIterator->second;
        validateBlock(volume, blockNumber);

        auto blockIterator = volume.blocks.find(blockNumber);

        if (blockIterator == volume.blocks.end()) {
            return {};
        }

        return blockIterator->second.payload;
    }

    void createSnapshot(
        const std::string& snapshotId,
        const std::string& volumeId
    ) {
        if (snapshots_.contains(snapshotId)) {
            throw ValidationError("Snapshot already exists: " + snapshotId);
        }

        auto volumeIterator = volumes_.find(volumeId);

        if (volumeIterator == volumes_.end()) {
            throw NotFoundError("Unknown logical volume: " + volumeId);
        }

        snapshots_.emplace(
            snapshotId,
            Snapshot{
                snapshotId,
                volumeId,
                volumeIterator->second.blocks
            }
        );
    }

    void restoreSnapshot(const std::string& snapshotId) {
        auto snapshotIterator = snapshots_.find(snapshotId);

        if (snapshotIterator == snapshots_.end()) {
            throw NotFoundError("Unknown snapshot: " + snapshotId);
        }

        auto volumeIterator =
            volumes_.find(snapshotIterator->second.volumeId);

        if (volumeIterator == volumes_.end()) {
            throw NotFoundError("Snapshot source volume no longer exists");
        }

        volumeIterator->second.blocks =
            snapshotIterator->second.blocks;
    }

    void report() const {
        std::cout << "\n=== ENGINE REPORT ===\n";

        for (const auto& [id, pool] : pools_) {
            pool.print();
        }

        std::cout << "\nVirtual disks:\n";

        for (const auto& [id, disk] : virtualDisks_) {
            const std::string type =
                disk.provisioning == Provisioning::Thick
                    ? "thick"
                    : "thin";

            std::cout << "  " << id
                      << ": logical=" << disk.logicalCapacityGiB
                      << " GiB, physical=" << disk.physicalAllocationGiB
                      << " GiB, provisioning=" << type << '\n';
        }

        std::cout << "\nLogical volumes:\n";

        for (const auto& [id, volume] : volumes_) {
            std::cout << "  " << id
                      << ": blocks=" << volume.blockCount
                      << ", allocated logical blocks="
                      << volume.blocks.size() << '\n';
        }
    }
};

} // namespace storage

int main() {
    using namespace storage;

    try {
        std::cout << "=== BLOCK STORAGE VIRTUALIZATION CASE STUDY ===\n";

        BlockStorageEngine engine;

        auto& pool = engine.createPool("cloud-block-pool");

        pool.addDisk({"nvme-a", 40, 0, DiskState::Online});
        pool.addDisk({"nvme-b", 40, 0, DiskState::Online});
        pool.addDisk({"nvme-c", 40, 0, DiskState::Online});

        /*
         * The database workload receives a thick virtual disk. The cloud
         * tenant sees 60 GiB, while the pool immediately reserves 60 GiB.
         */
        auto& databaseDisk = engine.createVirtualDisk(
            "vd-database",
            "cloud-block-pool",
            60,
            Provisioning::Thick
        );

        auto& databaseVolume = engine.createVolume(
            "lv-database",
            databaseDisk.id,
            4096
        );

        /*
         * A logical block number is the abstraction visible to the consumer.
         * The caller does not identify nvme-a, nvme-b, or nvme-c.
         */
        engine.write(
            databaseVolume.id,
            100,
            "customer=10042;state=ACTIVE;region=IN"
        );

        std::cout
            << "Database block 100: "
            << engine.read(databaseVolume.id, 100)
            << '\n';

        /*
         * Reporting uses thin provisioning. The tenant receives a 90 GiB
         * logical address space, but physical allocation grows when blocks
         * are written.
         */
        auto& analyticsDisk = engine.createVirtualDisk(
            "vd-analytics",
            "cloud-block-pool",
            90,
            Provisioning::Thin
        );

        auto& analyticsVolume = engine.createVolume(
            "lv-analytics",
            analyticsDisk.id,
            4096
        );

        std::cout
            << "Analytics physical allocation before writes: "
            << analyticsDisk.physicalAllocationGiB
            << " GiB\n";

        engine.write(
            analyticsVolume.id,
            4'000,
            "report=monthly-revenue;period=2026-09"
        );

        engine.write(
            analyticsVolume.id,
            9'000,
            "report=customer-retention;period=2026-09"
        );

        std::cout
            << "Analytics physical allocation after writes: "
            << analyticsDisk.physicalAllocationGiB
            << " GiB\n";

        /*
         * Snapshot captures logical block state. Production snapshot engines
         * often use copy-on-write metadata so unchanged blocks are shared.
         */
        engine.createSnapshot(
            "snapshot-before-correction",
            databaseVolume.id
        );

        engine.write(
            databaseVolume.id,
            100,
            "customer=10042;state=SUSPENDED"
        );

        std::cout
            << "Changed database block: "
            << engine.read(databaseVolume.id, 100)
            << '\n';

        engine.restoreSnapshot("snapshot-before-correction");

        std::cout
            << "Restored database block: "
            << engine.read(databaseVolume.id, 100)
            << '\n';

        engine.report();

        std::cout << "\n=== VALIDATION ===\n";

        try {
            engine.read(databaseVolume.id, databaseVolume.blockCount);
        } catch (const StorageError& error) {
            std::cout << "Out-of-range read rejected: "
                      << error.what() << '\n';
        }

        try {
            engine.write(
                databaseVolume.id,
                0,
                std::string(4097, 'x')
            );
        } catch (const StorageError& error) {
            std::cout << "Oversized block rejected: "
                      << error.what() << '\n';
        }

        try {
            engine.createVirtualDisk(
                "vd-impossible",
                "cloud-block-pool",
                500,
                Provisioning::Thick
            );
        } catch (const CapacityError& error) {
            std::cout << "Pool capacity rejection: "
                      << error.what() << '\n';
        }

        std::cout << "\n=== DISK FAILURE MODEL ===\n";

        pool.failDisk("nvme-c");

        std::cout
            << "Pool usable capacity after nvme-c failure: "
            << pool.usableGiB()
            << " GiB\n";

        std::cout
            << "The model intentionally separates capacity accounting from "
            << "data redundancy. A real storage platform needs RAID, "
            << "replication, or erasure coding to recover data from a failed "
            << "device.\n";

        std::cout << "\n=== PERFORMANCE CHARACTERISTICS ===\n";
        std::cout
            << "Physical placement uses sorting, giving O(D log D) allocation "
            << "selection for D disks.\n";
        std::cout
            << "Logical block lookup uses std::map, giving O(log B) lookup "
            << "for B mapped blocks.\n";
        std::cout
            << "A production implementation could use extent maps, interval "
            << "trees, hash tables, persistent metadata journals, and "
            << "asynchronous I/O queues depending on workload requirements.\n";

        assert(engine.read(databaseVolume.id, 100) ==
               "customer=10042;state=ACTIVE;region=IN");

        std::cout << "\nConsistency assertion passed.\n";
    }
    catch (const std::exception& error) {
        std::cerr << "Fatal storage error: "
                  << error.what()
                  << '\n';
        return 1;
    }

    return 0;
}
