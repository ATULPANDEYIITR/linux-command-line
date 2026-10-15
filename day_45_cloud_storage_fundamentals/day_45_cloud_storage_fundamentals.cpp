#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

enum class StorageClass {
    Standard,
    InfrequentAccess,
    Archive
};

enum class Health {
    Healthy,
    Failed
};

struct Replica {
    std::string region;
    Health health{Health::Healthy};
};

struct StorageObject {
    std::string key;
    std::size_t logicalSizeBytes{};
    StorageClass storageClass{StorageClass::Standard};
    std::vector<Replica> replicas;
};

class StorageConfigurationError : public std::runtime_error {
public:
    explicit StorageConfigurationError(const std::string& message)
        : std::runtime_error(message) {}
};

class ObjectUnavailable : public std::runtime_error {
public:
    explicit ObjectUnavailable(const std::string& message)
        : std::runtime_error(message) {}
};

/*
 * Case study:
 *
 * A financial analytics repository stores daily market-data snapshots.
 * The governance engine must distinguish:
 *
 * - logical data size from physical replicated capacity,
 * - durability from immediate availability,
 * - a failed replica from complete data loss,
 * - a degraded service from an unavailable service.
 *
 * The class intentionally keeps storage policy separate from application
 * behavior so the same policy can evaluate multiple buckets.
 */
class RepositoryStorage {
private:
    std::string name_;
    std::vector<std::string> regions_;
    std::size_t replicationFactor_;
    std::map<std::string, StorageObject> objects_;

public:
    RepositoryStorage(
        std::string name,
        std::vector<std::string> regions,
        std::size_t replicationFactor)
        : name_(std::move(name)),
          regions_(std::move(regions)),
          replicationFactor_(replicationFactor) {

        if (name_.empty()) {
            throw StorageConfigurationError("Storage name cannot be empty.");
        }

        if (regions_.empty()) {
            throw StorageConfigurationError(
                "At least one region is required.");
        }

        if (replicationFactor_ == 0 ||
            replicationFactor_ > regions_.size()) {
            throw StorageConfigurationError(
                "Invalid replication factor.");
        }
    }

    void put(
        const std::string& key,
        std::size_t logicalSizeBytes,
        StorageClass storageClass) {

        if (key.empty()) {
            throw std::invalid_argument("Object key cannot be empty.");
        }

        if (logicalSizeBytes == 0) {
            throw std::invalid_argument(
                "Zero-byte objects are excluded from this case study.");
        }

        StorageObject object{
            key,
            logicalSizeBytes,
            storageClass,
            {}
        };

        for (std::size_t i = 0; i < replicationFactor_; ++i) {
            object.replicas.push_back({regions_[i], Health::Healthy});
        }

        objects_[key] = std::move(object);
    }

    void failRegion(const std::string& region) {
        bool known = std::find(
            regions_.begin(),
            regions_.end(),
            region
        ) != regions_.end();

        if (!known) {
            throw std::invalid_argument("Unknown region: " + region);
        }

        for (auto& [key, object] : objects_) {
            for (auto& replica : object.replicas) {
                if (replica.region == region) {
                    replica.health = Health::Failed;
                }
            }
        }
    }

    void recoverRegion(const std::string& region) {
        bool known = std::find(
            regions_.begin(),
            regions_.end(),
            region
        ) != regions_.end();

        if (!known) {
            throw std::invalid_argument("Unknown region: " + region);
        }

        for (auto& [key, object] : objects_) {
            for (auto& replica : object.replicas) {
                if (replica.region == region) {
                    replica.health = Health::Healthy;
                }
            }
        }
    }

    std::size_t healthyReplicaCount(const std::string& key) const {
        auto it = objects_.find(key);

        if (it == objects_.end()) {
            throw std::out_of_range("Object does not exist.");
        }

        return static_cast<std::size_t>(
            std::count_if(
                it->second.replicas.begin(),
                it->second.replicas.end(),
                [](const Replica& replica) {
                    return replica.health == Health::Healthy;
                }
            )
        );
    }

    std::string availability(const std::string& key) const {
        const std::size_t healthy = healthyReplicaCount(key);

        if (healthy == 0) {
            return "UNAVAILABLE";
        }

        if (healthy < replicationFactor_) {
            return "DEGRADED";
        }

        return "AVAILABLE";
    }

    std::size_t physicalCapacityBytes() const {
        std::size_t total = 0;

        for (const auto& [key, object] : objects_) {
            total += object.logicalSizeBytes * object.replicas.size();
        }

        return total;
    }

    std::size_t logicalCapacityBytes() const {
        std::size_t total = 0;

        for (const auto& [key, object] : objects_) {
            total += object.logicalSizeBytes;
        }

        return total;
    }

    const std::string& name() const {
        return name_;
    }

    std::size_t replicationFactor() const {
        return replicationFactor_;
    }
};

struct StoragePolicy {
    std::size_t minimumReplicationFactor;
    bool requireMultiRegion;

    bool compliant(
        const RepositoryStorage& storage,
        const std::vector<std::string>& regions) const {

        if (storage.replicationFactor() < minimumReplicationFactor) {
            return false;
        }

        if (requireMultiRegion && regions.size() < 2) {
            return false;
        }

        return true;
    }
};

double systemAvailability(
    double replicaAvailability,
    std::size_t replicaCount) {

    if (replicaAvailability < 0.0 ||
        replicaAvailability > 1.0 ||
        replicaCount == 0) {
        throw std::invalid_argument("Invalid availability inputs.");
    }

    return 1.0 -
           std::pow(1.0 - replicaAvailability,
                    static_cast<double>(replicaCount));
}

double simultaneousFailureProbability(
    double individualFailureProbability,
    std::size_t independentReplicaCount) {

    if (individualFailureProbability < 0.0 ||
        individualFailureProbability > 1.0 ||
        independentReplicaCount == 0) {
        throw std::invalid_argument("Invalid durability inputs.");
    }

    return std::pow(
        individualFailureProbability,
        static_cast<double>(independentReplicaCount)
    );
}

void printCapacity(const RepositoryStorage& storage) {
    const auto logical = storage.logicalCapacityBytes();
    const auto physical = storage.physicalCapacityBytes();

    std::cout << "Logical capacity:  "
              << logical / (1024.0 * 1024.0)
              << " MiB\n";

    std::cout << "Replicated capacity: "
              << physical / (1024.0 * 1024.0)
              << " MiB\n";
}

int main() {
    try {
        RepositoryStorage analyticsStorage(
            "market-data",
            {"Mumbai", "Singapore", "Frankfurt"},
            3
        );

        analyticsStorage.put(
            "2026-10-15/equities.snapshot",
            100 * 1024 * 1024,
            StorageClass::Standard
        );

        analyticsStorage.put(
            "2026-09-15/equities.snapshot",
            80 * 1024 * 1024,
            StorageClass::InfrequentAccess
        );

        std::cout << "Storage system: "
                  << analyticsStorage.name() << '\n';

        printCapacity(analyticsStorage);

        std::cout << "Initial availability: "
                  << analyticsStorage.availability(
                      "2026-10-15/equities.snapshot")
                  << '\n';

        analyticsStorage.failRegion("Mumbai");

        std::cout << "After one regional failure: "
                  << analyticsStorage.availability(
                      "2026-10-15/equities.snapshot")
                  << '\n';

        std::cout << "Healthy replicas: "
                  << analyticsStorage.healthyReplicaCount(
                      "2026-10-15/equities.snapshot")
                  << '\n';

        analyticsStorage.failRegion("Singapore");

        std::cout << "After two regional failures: "
                  << analyticsStorage.availability(
                      "2026-10-15/equities.snapshot")
                  << '\n';

        analyticsStorage.recoverRegion("Mumbai");

        std::cout << "After recovery: "
                  << analyticsStorage.availability(
                      "2026-10-15/equities.snapshot")
                  << '\n';

        StoragePolicy policy{
            3,
            true
        };

        const bool policyCompliant = policy.compliant(
            analyticsStorage,
            {"Mumbai", "Singapore", "Frankfurt"}
        );

        std::cout << "Storage policy compliant: "
                  << std::boolalpha
                  << policyCompliant
                  << '\n';

        const double availability = systemAvailability(
            0.999,
            3
        );

        const double dataLossProbability =
            simultaneousFailureProbability(
                0.001,
                3
            );

        std::cout << std::fixed << std::setprecision(8);
        std::cout << "Modeled independent availability: "
                  << availability << '\n';

        std::cout << std::scientific;
        std::cout << "Modeled simultaneous replica-loss probability: "
                  << dataLossProbability << '\n';

        /*
         * This model is intentionally not presented as a cloud-provider SLA.
         * Real providers use erasure coding, multiple failure domains,
         * background repair, integrity checks, metadata redundancy, and
         * provider-specific service guarantees. Independent replica math is
         * useful for understanding the concept, not for predicting a vendor's
         * exact durability number.
         */

    } catch (const std::exception& error) {
        std::cerr << "Storage simulation failed: "
                  << error.what()
                  << '\n';
        return 1;
    }

    return 0;
}
