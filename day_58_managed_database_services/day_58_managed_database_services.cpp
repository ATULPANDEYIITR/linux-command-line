#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

enum class DatabaseState {
    Available,
    Maintenance,
    FailingOver,
    Degraded,
    Failed
};

enum class ReplicaState {
    Streaming,
    Lagging,
    Failed
};

enum class ReviewResult {
    Pass,
    Fail
};

struct StatusCheck {
    std::string name;
    bool passed;
    std::string message;
};

struct Replica {
    std::string id;
    std::string region;
    ReplicaState state{ReplicaState::Streaming};
    int lagSeconds{1};
    long replayedLsn{0};
};

struct Backup {
    std::string id;
    long lsn;
    int sizeGb;
    std::string checksum;
};

struct ProtectionPolicy {
    bool multiAz{true};
    bool requireBackup{true};
    bool requireHealthyReplica{true};
    bool requireStorageHeadroom{true};
    int maximumReplicaLagSeconds{60};
};

class ValidationError : public std::runtime_error {
public:
    explicit ValidationError(const std::string& message)
        : std::runtime_error(message) {}
};

class AvailabilityError : public std::runtime_error {
public:
    explicit AvailabilityError(const std::string& message)
        : std::runtime_error(message) {}
};

static std::string stateToString(DatabaseState state) {
    switch (state) {
        case DatabaseState::Available: return "available";
        case DatabaseState::Maintenance: return "maintenance";
        case DatabaseState::FailingOver: return "failing_over";
        case DatabaseState::Degraded: return "degraded";
        case DatabaseState::Failed: return "failed";
    }
    return "unknown";
}

static std::string replicaStateToString(ReplicaState state) {
    switch (state) {
        case ReplicaState::Streaming: return "streaming";
        case ReplicaState::Lagging: return "lagging";
        case ReplicaState::Failed: return "failed";
    }
    return "unknown";
}

class RepositoryGovernanceEngine {
private:
    std::string databaseName_;
    std::string engine_;
    std::string version_;
    std::string primaryRegion_;
    int storageGb_;
    int computeUnits_;
    bool multiAz_;
    DatabaseState state_{DatabaseState::Available};
    long lsn_{0};

    ProtectionPolicy policy_;
    std::map<std::string, Replica> replicas_;
    std::vector<Backup> backups_;

    unsigned long sequence_{0};

    std::string nextId(const std::string& prefix) {
        return prefix + "-" + std::to_string(++sequence_);
    }

    void requireAvailable() const {
        if (state_ != DatabaseState::Available &&
            state_ != DatabaseState::Degraded) {
            throw AvailabilityError(
                "Database operation rejected because service is " +
                stateToString(state_));
        }
    }

public:
    RepositoryGovernanceEngine(
        std::string databaseName,
        std::string engine,
        std::string version,
        std::string region,
        int storageGb,
        int computeUnits,
        bool multiAz,
        ProtectionPolicy policy)
        : databaseName_(std::move(databaseName)),
          engine_(std::move(engine)),
          version_(std::move(version)),
          primaryRegion_(std::move(region)),
          storageGb_(storageGb),
          computeUnits_(computeUnits),
          multiAz_(multiAz),
          policy_(policy) {

        if (databaseName_.empty() || engine_.empty() ||
            version_.empty() || primaryRegion_.empty()) {
            throw ValidationError("Database identity cannot be empty");
        }

        if (storageGb_ < 20) {
            throw ValidationError("Storage must be at least 20 GB");
        }

        if (computeUnits_ < 1) {
            throw ValidationError("Compute units must be positive");
        }
    }

    void write(long records) {
        requireAvailable();

        if (records <= 0) {
            throw ValidationError("Record count must be positive");
        }

        lsn_ += records;
    }

    std::string createBackup() {
        requireAvailable();

        Backup backup{
            nextId("backup"),
            lsn_,
            std::max(1, static_cast<int>(storageGb_ * 0.65)),
            "sha256-simulated-" + std::to_string(lsn_)
        };

        backups_.push_back(backup);
        return backup.id;
    }

    void addReplica(const std::string& region) {
        requireAvailable();

        if (region.empty() || region == primaryRegion_) {
            throw ValidationError(
                "Replica region must differ from primary region");
        }

        for (const auto& [id, replica] : replicas_) {
            if (replica.region == region) {
                throw ValidationError("Replica region already exists");
            }
        }

        Replica replica;
        replica.id = nextId("replica");
        replica.region = region;
        replica.replayedLsn = lsn_;
        replicas_.emplace(replica.id, replica);
    }

    void changeReplicaLag(const std::string& id, int seconds) {
        auto it = replicas_.find(id);

        if (it == replicas_.end()) {
            throw ValidationError("Replica does not exist");
        }

        Replica& replica = it->second;

        if (replica.state == ReplicaState::Failed) {
            throw AvailabilityError("Failed replica cannot be synchronized");
        }

        replica.lagSeconds = std::max(0, replica.lagSeconds + seconds);

        if (replica.lagSeconds > policy_.maximumReplicaLagSeconds) {
            replica.state = ReplicaState::Lagging;
        } else {
            replica.state = ReplicaState::Streaming;
            replica.replayedLsn = lsn_;
        }
    }

    void scaleStorage(int newStorageGb) {
        requireAvailable();

        if (newStorageGb < storageGb_) {
            throw ValidationError(
                "This operational path does not support storage reduction");
        }

        storageGb_ = newStorageGb;
    }

    void scaleCompute(int newComputeUnits) {
        requireAvailable();

        if (newComputeUnits < 1) {
            throw ValidationError("Compute units must be positive");
        }

        computeUnits_ = newComputeUnits;
    }

    void patch(const std::string& targetVersion, int requestedHour) {
        requireAvailable();

        if (targetVersion.empty()) {
            throw ValidationError("Target version cannot be empty");
        }

        if (requestedHour != 2) {
            throw ValidationError(
                "Patch is permitted only during the configured maintenance window");
        }

        state_ = DatabaseState::Maintenance;

        try {
            version_ = targetVersion;
            state_ = DatabaseState::Available;
        } catch (...) {
            state_ = DatabaseState::Failed;
            throw;
        }
    }

    bool evaluateMergeStyleOperationalPolicy() const {
        // The method intentionally treats operational readiness as a set
        // of independent gates rather than a single health flag.
        if (policy_.multiAz && !multiAz_) {
            return false;
        }

        if (policy_.requireBackup && backups_.empty()) {
            return false;
        }

        if (policy_.requireHealthyReplica) {
            bool healthy = std::any_of(
                replicas_.begin(),
                replicas_.end(),
                [&](const auto& item) {
                    const Replica& replica = item.second;
                    return replica.state == ReplicaState::Streaming &&
                           replica.lagSeconds <= policy_.maximumReplicaLagSeconds;
                });

            if (!healthy) {
                return false;
            }
        }

        if (policy_.requireStorageHeadroom && storageGb_ < 100) {
            return false;
        }

        return state_ == DatabaseState::Available;
    }

    void failover() {
        if (!multiAz_) {
            throw AvailabilityError(
                "Failover requires multi-AZ deployment");
        }

        auto healthy = std::find_if(
            replicas_.begin(),
            replicas_.end(),
            [&](const auto& item) {
                const Replica& replica = item.second;
                return replica.state == ReplicaState::Streaming &&
                       replica.lagSeconds <= policy_.maximumReplicaLagSeconds;
            });

        state_ = DatabaseState::FailingOver;

        if (healthy == replicas_.end()) {
            state_ = DatabaseState::Failed;
            throw AvailabilityError(
                "Failover failed because no healthy replica exists");
        }

        primaryRegion_ = healthy->second.region;
        state_ = DatabaseState::Available;
    }

    std::vector<StatusCheck> healthChecks() const {
        std::vector<StatusCheck> checks;

        checks.push_back({
            "storage_capacity",
            storageGb_ >= 20,
            "Storage is configured above the minimum"
        });

        checks.push_back({
            "compute_capacity",
            computeUnits_ >= 1,
            "Compute capacity is positive"
        });

        bool replicaHealthy = true;

        if (policy_.requireHealthyReplica) {
            replicaHealthy = std::any_of(
                replicas_.begin(),
                replicas_.end(),
                [&](const auto& item) {
                    return item.second.state == ReplicaState::Streaming &&
                           item.second.lagSeconds <=
                               policy_.maximumReplicaLagSeconds;
                });
        }

        checks.push_back({
            "replication",
            replicaHealthy,
            replicaHealthy
                ? "At least one replica satisfies the lag policy"
                : "No replica satisfies the lag policy"
        });

        checks.push_back({
            "backup",
            !policy_.requireBackup || !backups_.empty(),
            "Backup requirement evaluated"
        });

        checks.push_back({
            "service_state",
            state_ == DatabaseState::Available,
            "Service is available"
        });

        return checks;
    }

    void printReport() const {
        std::cout << "\n=== Managed Database ===\n";
        std::cout << "Name: " << databaseName_ << '\n';
        std::cout << "Engine: " << engine_ << " " << version_ << '\n';
        std::cout << "Primary region: " << primaryRegion_ << '\n';
        std::cout << "State: " << stateToString(state_) << '\n';
        std::cout << "Storage: " << storageGb_ << " GB\n";
        std::cout << "Compute: " << computeUnits_ << " units\n";
        std::cout << "LSN: " << lsn_ << '\n';

        std::cout << "\nReplicas:\n";
        for (const auto& [id, replica] : replicas_) {
            std::cout
                << "  " << id
                << " region=" << replica.region
                << " state=" << replicaStateToString(replica.state)
                << " lag=" << replica.lagSeconds << "s\n";
        }

        std::cout << "\nBackups: " << backups_.size() << '\n';
        std::cout
            << "Operational policy: "
            << (evaluateMergeStyleOperationalPolicy() ? "PASS" : "FAIL")
            << '\n';
    }
};

int main() {
    try {
        ProtectionPolicy policy;
        policy.multiAz = true;
        policy.requireBackup = true;
        policy.requireHealthyReplica = true;
        policy.requireStorageHeadroom = true;
        policy.maximumReplicaLagSeconds = 60;

        RepositoryGovernanceEngine database(
            "orders-prod",
            "PostgreSQL",
            "18.0",
            "ap-south-1",
            250,
            8,
            true,
            policy
        );

        database.write(1000);

        const std::string backupId = database.createBackup();
        std::cout << "Created backup: " << backupId << '\n';

        database.addReplica("ap-southeast-1");
        database.write(300);

        database.scaleStorage(400);
        database.scaleCompute(12);

        database.patch("18.1", 2);

        std::cout << "\n=== Health Checks ===\n";
        for (const auto& check : database.healthChecks()) {
            std::cout
                << check.name << ": "
                << (check.passed ? "PASS" : "FAIL")
                << " - " << check.message << '\n';
        }

        std::cout << "\nPolicy evaluation before failover: "
                  << (database.evaluateMergeStyleOperationalPolicy()
                          ? "PASS"
                          : "FAIL")
                  << '\n';

        database.failover();

        database.printReport();

        try {
            database.scaleStorage(100);
        } catch (const std::exception& ex) {
            std::cout << "\nExpected validation failure: "
                      << ex.what() << '\n';
        }

        try {
            database.patch("18.2", 15);
        } catch (const std::exception& ex) {
            std::cout << "Expected maintenance-window failure: "
                      << ex.what() << '\n';
        }

        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "Fatal operational error: " << ex.what() << '\n';
        return 1;
    }
}
