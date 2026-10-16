#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

enum class StorageClass {
    Standard,
    InfrequentAccess,
    Archive
};

std::string toString(StorageClass storageClass) {
    switch (storageClass) {
        case StorageClass::Standard:
            return "STANDARD";
        case StorageClass::InfrequentAccess:
            return "INFREQUENT_ACCESS";
        case StorageClass::Archive:
            return "ARCHIVE";
    }
    return "UNKNOWN";
}

enum class ReviewState {
    None,
    Pending,
    Approved,
    Rejected
};

struct StatusCheck {
    std::string name;
    bool passed;
};

struct ObjectVersion {
    std::string versionId;
    std::size_t size;
    std::string checksum;
    std::string contentType;
    std::string createdAt;
    StorageClass storageClass;
    bool deleteMarker;
};

struct ObjectRecord {
    std::string key;
    std::vector<ObjectVersion> versions;
};

struct LifecyclePolicy {
    std::string prefix;
    int transitionAfterDays;
    StorageClass transitionTarget;
    std::optional<int> expireAfterDays;
};

class ObjectStorageException : public std::runtime_error {
public:
    explicit ObjectStorageException(const std::string& message)
        : std::runtime_error(message) {}
};

class Bucket {
private:
    std::string name_;
    std::string region_;
    std::map<std::string, ObjectRecord> objects_;
    std::vector<LifecyclePolicy> lifecyclePolicies_;

    static std::string makeVersionId(
        const std::string& key,
        const std::string& content,
        const std::string& timestamp
    ) {
        std::hash<std::string> hasher;
        const auto value = hasher(key + "|" + content + "|" + timestamp);
        std::ostringstream stream;
        stream << std::hex << value;
        return stream.str();
    }

public:
    Bucket(std::string name, std::string region)
        : name_(std::move(name)), region_(std::move(region)) {}

    const std::string& name() const {
        return name_;
    }

    void addLifecyclePolicy(LifecyclePolicy policy) {
        if (policy.prefix.empty()) {
            throw ObjectStorageException("Lifecycle prefix cannot be empty.");
        }

        if (policy.transitionAfterDays < 0) {
            throw ObjectStorageException("Transition age cannot be negative.");
        }

        if (
            policy.expireAfterDays.has_value() &&
            policy.expireAfterDays.value() < policy.transitionAfterDays
        ) {
            throw ObjectStorageException(
                "Expiration cannot precede the configured transition."
            );
        }

        lifecyclePolicies_.push_back(std::move(policy));
    }

    ObjectVersion putObject(
        const std::string& key,
        const std::string& content,
        const std::string& contentType,
        const std::string& timestamp
    ) {
        if (key.empty() || key.front() == '/') {
            throw ObjectStorageException("Invalid object key.");
        }

        auto& object = objects_[key];
        object.key = key;

        ObjectVersion version{
            makeVersionId(key, content, timestamp),
            content.size(),
            makeVersionId(content, "", "checksum"),
            contentType,
            timestamp,
            StorageClass::Standard,
            false
        };

        object.versions.push_back(version);
        return version;
    }

    void deleteObject(const std::string& key, const std::string& timestamp) {
        auto iterator = objects_.find(key);
        if (iterator == objects_.end()) {
            throw ObjectStorageException("Object does not exist: " + key);
        }

        ObjectVersion marker{
            makeVersionId(key, "DELETE", timestamp),
            0,
            makeVersionId("", "DELETE", timestamp),
            "application/x-delete-marker",
            timestamp,
            StorageClass::Standard,
            true
        };

        iterator->second.versions.push_back(marker);
    }

    const ObjectVersion& currentObject(const std::string& key) const {
        const auto iterator = objects_.find(key);

        if (iterator == objects_.end() || iterator->second.versions.empty()) {
            throw ObjectStorageException("Object not found: " + key);
        }

        const auto& version = iterator->second.versions.back();

        if (version.deleteMarker) {
            throw ObjectStorageException(
                "Current object is hidden by a delete marker: " + key
            );
        }

        return version;
    }

    void applyLifecycle(int objectAgeDays) {
        for (auto& [key, object] : objects_) {
            for (auto& version : object.versions) {
                if (version.deleteMarker) {
                    continue;
                }

                for (const auto& policy : lifecyclePolicies_) {
                    if (key.rfind(policy.prefix, 0) != 0) {
                        continue;
                    }

                    if (objectAgeDays >= policy.transitionAfterDays) {
                        if (version.storageClass != policy.transitionTarget) {
                            version.storageClass = policy.transitionTarget;

                            std::cout
                                << "Transitioned "
                                << key
                                << "@"
                                << version.versionId
                                << " to "
                                << toString(version.storageClass)
                                << '\n';
                        }
                    }
                }
            }
        }
    }

    void printInventory() const {
        for (const auto& [key, object] : objects_) {
            std::cout << key << '\n';

            for (const auto& version : object.versions) {
                std::cout
                    << "  version=" << version.versionId
                    << " size=" << version.size
                    << " class=" << toString(version.storageClass)
                    << " deleted=" << std::boolalpha
                    << version.deleteMarker
                    << '\n';
            }
        }
    }
};

class StorageControlPlane {
private:
    std::unordered_map<std::string, Bucket> buckets_;

public:
    Bucket& createBucket(
        const std::string& name,
        const std::string& region
    ) {
        if (buckets_.contains(name)) {
            throw ObjectStorageException(
                "Bucket already exists: " + name
            );
        }

        auto [iterator, inserted] =
            buckets_.emplace(
                std::piecewise_construct,
                std::forward_as_tuple(name),
                std::forward_as_tuple(name, region)
            );

        if (!inserted) {
            throw ObjectStorageException("Bucket creation failed.");
        }

        return iterator->second;
    }

    Bucket& getBucket(const std::string& name) {
        auto iterator = buckets_.find(name);

        if (iterator == buckets_.end()) {
            throw ObjectStorageException(
                "Bucket not found: " + name
            );
        }

        return iterator->second;
    }
};

struct StorageRequest {
    std::string bucket;
    std::string objectKey;
    std::size_t expectedMinimumSize;
};

bool validateRequest(
    const StorageRequest& request,
    const Bucket& bucket
) {
    if (request.bucket != bucket.name()) {
        return false;
    }

    if (request.objectKey.empty()) {
        return false;
    }

    try {
        const auto& object = bucket.currentObject(request.objectKey);
        return object.size >= request.expectedMinimumSize;
    } catch (const ObjectStorageException&) {
        return false;
    }
}

int main() {
    try {
        StorageControlPlane controlPlane;

        Bucket& bucket =
            controlPlane.createBucket(
                "research-dataset-store",
                "ap-south-1"
            );

        bucket.addLifecyclePolicy({
            "datasets/",
            30,
            StorageClass::InfrequentAccess,
            365
        });

        bucket.addLifecyclePolicy({
            "models/",
            90,
            StorageClass::Archive,
            std::nullopt
        });

        const auto datasetVersion =
            bucket.putObject(
                "datasets/customer-events.parquet",
                "partitioned-data-placeholder-representation",
                "application/vnd.apache.parquet",
                "2026-01-01T00:00:00Z"
            );

        bucket.putObject(
            "datasets/customer-events.parquet",
            "new-partitioned-data-representation",
            "application/vnd.apache.parquet",
            "2026-01-05T00:00:00Z"
        );

        bucket.putObject(
            "models/fraud-model.bin",
            "binary-model-representation",
            "application/octet-stream",
            "2026-01-01T00:00:00Z"
        );

        std::cout << "=== Object storage inventory ===\n";
        bucket.printInventory();

        std::cout << "\n=== Historical version access ===\n";
        std::cout
            << "Original dataset version: "
            << datasetVersion.versionId
            << ", size="
            << datasetVersion.size
            << '\n';

        std::cout << "\n=== Lifecycle transition ===\n";
        bucket.applyLifecycle(100);

        std::cout << "\n=== Current object validation ===\n";
        StorageRequest request{
            "research-dataset-store",
            "datasets/customer-events.parquet",
            10
        };

        std::cout
            << std::boolalpha
            << "Request accepted: "
            << validateRequest(request, bucket)
            << '\n';

        std::cout << "\n=== Version-aware deletion ===\n";
        bucket.deleteObject(
            "datasets/customer-events.parquet",
            "2026-04-15T00:00:00Z"
        );

        try {
            bucket.currentObject("datasets/customer-events.parquet");
        } catch (const ObjectStorageException& error) {
            std::cout << error.what() << '\n';
        }

        std::cout << "\n=== Final inventory ===\n";
        bucket.printInventory();
    } catch (const std::exception& error) {
        std::cerr << "Storage failure: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
