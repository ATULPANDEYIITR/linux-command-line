#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

enum class DiskType {
    HDD,
    SSD,
    NVME
};

enum class AttachmentMode {
    ReadOnly,
    ReadWrite
};

std::string toString(DiskType type) {
    switch (type) {
        case DiskType::HDD: return "HDD";
        case DiskType::SSD: return "SSD";
        case DiskType::NVME: return "NVMe";
    }
    return "unknown";
}

struct PerformanceProfile {
    double latencyMs;
    double throughputMBps;
    int baselineIops;
};

PerformanceProfile performanceFor(DiskType type) {
    switch (type) {
        case DiskType::HDD:
            return {8.0, 180.0, 150};
        case DiskType::SSD:
            return {0.8, 550.0, 50000};
        case DiskType::NVME:
            return {0.15, 3500.0, 500000};
    }
    throw std::invalid_argument("Unsupported disk type");
}

struct Snapshot {
    std::string id;
    std::string sourceDisk;
    double logicalSizeGB;
    std::size_t changedBlocks;
    std::optional<std::string> parent;
};

struct Disk {
    std::string id;
    double capacityGB;
    double usedGB;
    DiskType type;
    std::string zone;
    std::optional<std::string> attachedInstance;
    std::vector<Snapshot> snapshots;

    double freeGB() const {
        return capacityGB - usedGB;
    }

    void write(double amountGB) {
        if (amountGB <= 0.0) {
            throw std::invalid_argument("Write size must be positive.");
        }

        if (amountGB > freeGB()) {
            throw std::runtime_error(
                "The write would exceed the disk capacity."
            );
        }

        usedGB += amountGB;
    }
};

struct Attachment {
    std::string diskId;
    AttachmentMode mode;
};

struct ComputeInstance {
    std::string id;
    std::string zone;
    std::map<std::string, AttachmentMode> disks;
};

class RepositoryStorageGovernance {
private:
    std::map<std::string, Disk> disks;
    std::map<std::string, ComputeInstance> instances;

public:
    void createDisk(
        const std::string& id,
        double capacityGB,
        DiskType type,
        const std::string& zone
    ) {
        if (capacityGB <= 0.0) {
            throw std::invalid_argument("Disk capacity must be positive.");
        }

        if (disks.contains(id)) {
            throw std::invalid_argument("Duplicate disk ID: " + id);
        }

        disks.emplace(
            id,
            Disk{id, capacityGB, 0.0, type, zone, std::nullopt, {}}
        );
    }

    void createInstance(
        const std::string& id,
        const std::string& zone
    ) {
        if (instances.contains(id)) {
            throw std::invalid_argument("Duplicate instance ID: " + id);
        }

        instances.emplace(id, ComputeInstance{id, zone, {}});
    }

    void attach(
        const std::string& diskId,
        const std::string& instanceId,
        AttachmentMode mode
    ) {
        auto diskIt = disks.find(diskId);
        auto instanceIt = instances.find(instanceId);

        if (diskIt == disks.end() || instanceIt == instances.end()) {
            throw std::runtime_error("Disk or compute instance not found.");
        }

        Disk& disk = diskIt->second;
        ComputeInstance& instance = instanceIt->second;

        if (disk.zone != instance.zone) {
            throw std::runtime_error("Cross-zone attachment is not permitted.");
        }

        if (disk.attachedInstance.has_value()) {
            throw std::runtime_error(
                "The disk is already attached to another instance."
            );
        }

        disk.attachedInstance = instance.id;
        instance.disks[disk.id] = mode;
    }

    void detach(
        const std::string& diskId,
        const std::string& instanceId
    ) {
        auto diskIt = disks.find(diskId);
        auto instanceIt = instances.find(instanceId);

        if (diskIt == disks.end() || instanceIt == instances.end()) {
            throw std::runtime_error("Disk or compute instance not found.");
        }

        Disk& disk = diskIt->second;
        ComputeInstance& instance = instanceIt->second;

        if (disk.attachedInstance != instance.id) {
            throw std::runtime_error(
                "The disk is not attached to the requested instance."
            );
        }

        instance.disks.erase(disk.id);
        disk.attachedInstance.reset();
    }

    void snapshot(
        const std::string& diskId,
        const std::string& snapshotId,
        std::size_t changedBlocks
    ) {
        auto diskIt = disks.find(diskId);

        if (diskIt == disks.end()) {
            throw std::runtime_error("Disk not found.");
        }

        Disk& disk = diskIt->second;

        std::optional<std::string> parent;
        if (!disk.snapshots.empty()) {
            parent = disk.snapshots.back().id;
        }

        disk.snapshots.push_back(
            Snapshot{
                snapshotId,
                disk.id,
                disk.usedGB,
                changedBlocks,
                parent
            }
        );
    }

    void printReport() const {
        std::cout << "\nStorage inventory\n";

        for (const auto& [id, disk] : disks) {
            const auto profile = performanceFor(disk.type);

            std::cout
                << std::left
                << std::setw(18) << id
                << std::setw(8) << toString(disk.type)
                << std::setw(10) << disk.capacityGB
                << std::setw(10) << disk.usedGB
                << std::setw(12) << profile.latencyMs
                << std::setw(14) << profile.throughputMBps
                << '\n';

            for (const auto& snapshot : disk.snapshots) {
                std::cout
                    << "  snapshot=" << snapshot.id
                    << ", size=" << snapshot.logicalSizeGB << " GB"
                    << ", changed blocks=" << snapshot.changedBlocks
                    << ", parent="
                    << (snapshot.parent ? *snapshot.parent : "none")
                    << '\n';
            }
        }
    }
};

int main() {
    try {
        RepositoryStorageGovernance storage;

        storage.createInstance("database-node", "zone-a");
        storage.createInstance("analytics-node", "zone-a");

        storage.createDisk(
            "database-volume",
            500.0,
            DiskType::NVME,
            "zone-a"
        );

        storage.createDisk(
            "analytics-volume",
            2000.0,
            DiskType::SSD,
            "zone-a"
        );

        storage.createDisk(
            "archive-volume",
            5000.0,
            DiskType::HDD,
            "zone-a"
        );

        storage.attach(
            "database-volume",
            "database-node",
            AttachmentMode::ReadWrite
        );

        storage.attach(
            "analytics-volume",
            "analytics-node",
            AttachmentMode::ReadWrite
        );

        storage.disks.at("database-volume").write(180.0);
        storage.disks.at("analytics-volume").write(620.0);
        storage.disks.at("archive-volume").write(1400.0);

        storage.snapshot(
            "database-volume",
            "database-before-upgrade",
            45000
        );

        storage.disks.at("database-volume").write(25.0);

        storage.snapshot(
            "database-volume",
            "database-after-upgrade",
            6250
        );

        storage.printReport();

        std::cout << "\nExpected failure checks\n";

        try {
            storage.attach(
                "database-volume",
                "analytics-node",
                AttachmentMode::ReadOnly
            );
        } catch (const std::exception& ex) {
            std::cout << "Attachment rejected: " << ex.what() << '\n';
        }

        try {
            storage.disks.at("database-volume").write(400.0);
        } catch (const std::exception& ex) {
            std::cout << "Capacity protection triggered: "
                      << ex.what() << '\n';
        }

        storage.detach("database-volume", "database-node");

        /*
         * The design intentionally keeps the Disk object independent from
         * ComputeInstance. Detaching a disk does not destroy its data,
         * representing the persistence property of block storage.
         */
        std::cout << "\nDatabase volume detached while storage remains "
                     "persistent.\n";

    } catch (const std::exception& ex) {
        std::cerr << "Fatal storage error: " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
