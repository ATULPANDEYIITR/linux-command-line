#include <algorithm>
#include <chrono>
#include <exception>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

enum class ReplicationMode {
    Synchronous,
    Asynchronous
};

enum class NodeRole {
    Primary,
    Replica,
    Offline
};

enum class MergeDecision {
    Eligible,
    NoPrimary,
    ReplicaUnavailable,
    RequiredChecksFailed,
    RequiredApprovalMissing,
    ConversationsOpen,
    BranchNotProtected
};

struct WalRecord {
    std::uint64_t position;
    std::string key;
    std::string value;
};

struct ReplicaNode {
    std::string name;
    ReplicationMode mode;
    NodeRole role{NodeRole::Replica};
    bool online{true};
    std::uint64_t appliedPosition{0};
    std::map<std::string, std::string> data;
    std::vector<WalRecord> queue;

    void receive(const WalRecord& record) {
        if (online && record.position > appliedPosition) {
            queue.push_back(record);
        }
    }

    std::size_t apply(std::size_t limit) {
        if (!online) {
            return 0;
        }

        std::size_t applied = 0;

        while (!queue.empty() && applied < limit) {
            const auto record = queue.front();

            if (record.position <= appliedPosition) {
                queue.erase(queue.begin());
                continue;
            }

            if (record.position != appliedPosition + 1) {
                break;
            }

            data[record.key] = record.value;
            appliedPosition = record.position;
            queue.erase(queue.begin());
            ++applied;
        }

        return applied;
    }
};

class ReplicationCluster {
private:
    std::string primaryName{"primary-01"};
    bool primaryOnline{true};
    std::uint64_t nextPosition{1};

    std::map<std::string, std::string> primaryData;
    std::vector<WalRecord> wal;

    std::map<std::string, ReplicaNode> replicas{
        {"sync-01", {"sync-01", ReplicationMode::Synchronous}},
        {"async-01", {"async-01", ReplicationMode::Asynchronous}}
    };

    std::uint64_t primaryPosition() const {
        return wal.empty() ? 0 : wal.back().position;
    }

public:
    WalRecord write(const std::string& key, const std::string& value) {
        if (!primaryOnline) {
            throw std::runtime_error("No writable primary exists.");
        }

        if (key.empty() || key.size() > 256) {
            throw std::invalid_argument("Invalid key length.");
        }

        if (value.size() > 4096) {
            throw std::invalid_argument("Value exceeds maximum size.");
        }

        WalRecord record{nextPosition++, key, value};
        wal.push_back(record);
        primaryData[key] = value;

        for (auto& [name, replica] : replicas) {
            replica.receive(record);
        }

        // Synchronous replication is part of the write acknowledgement
        // path. The primary does not consider the write durable until
        // every configured synchronous replica has applied the record.
        for (auto& [name, replica] : replicas) {
            if (replica.mode == ReplicationMode::Synchronous &&
                replica.online) {
                replica.apply(1);
            }
        }

        return record;
    }

    bool writeAcknowledged(const WalRecord& record) const {
        for (const auto& [name, replica] : replicas) {
            if (replica.mode == ReplicationMode::Synchronous) {
                if (!replica.online ||
                    replica.appliedPosition < record.position) {
                    return false;
                }
            }
        }
        return true;
    }

    void processAsynchronousReplication(std::size_t batch) {
        for (auto& [name, replica] : replicas) {
            if (replica.mode == ReplicationMode::Asynchronous) {
                replica.apply(batch);
            }
        }
    }

    std::optional<std::string> readFrom(
        const std::string& key,
        const std::string& nodeName,
        std::uint64_t requiredPosition
    ) const {
        const auto it = replicas.find(nodeName);

        if (it == replicas.end() || !it->second.online) {
            throw std::runtime_error("Replica is unavailable.");
        }

        const auto& replica = it->second;

        if (replica.appliedPosition < requiredPosition) {
            throw std::runtime_error(
                "Replica is too far behind the required WAL position."
            );
        }

        const auto value = replica.data.find(key);
        if (value == replica.data.end()) {
            return std::nullopt;
        }

        return value->second;
    }

    void failPrimary() {
        primaryOnline = false;
    }

    void promote(const std::string& replicaName) {
        auto it = replicas.find(replicaName);

        if (it == replicas.end()) {
            throw std::invalid_argument("Unknown replica.");
        }

        if (!it->second.online) {
            throw std::runtime_error("Offline replica cannot be promoted.");
        }

        for (auto& [name, replica] : replicas) {
            replica.role = NodeRole::Replica;
        }

        it->second.role = NodeRole::Primary;
        primaryName = replicaName;
        primaryData = it->second.data;
        primaryOnline = true;
    }

    void printStatus() const {
        std::cout << "Primary: " << primaryName
                  << ", WAL position: " << primaryPosition() << '\n';

        for (const auto& [name, replica] : replicas) {
            std::cout
                << name
                << " mode="
                << (replica.mode == ReplicationMode::Synchronous
                        ? "sync"
                        : "async")
                << " online=" << std::boolalpha << replica.online
                << " applied=" << replica.appliedPosition
                << " lag="
                << primaryPosition() - replica.appliedPosition
                << '\n';
        }
    }
};

int main() {
    try {
        ReplicationCluster cluster;

        const auto first = cluster.write("account:100", "active");
        std::cout
            << "First write acknowledged: "
            << std::boolalpha
            << cluster.writeAcknowledged(first)
            << '\n';

        cluster.write("invoice:9001", "paid");

        cluster.printStatus();

        try {
            const auto value = cluster.readFrom(
                "invoice:9001",
                "async-01",
                2
            );

            std::cout << "Async read: "
                      << value.value_or("<missing>") << '\n';
        } catch (const std::exception& ex) {
            std::cout << "Expected lag protection: "
                      << ex.what() << '\n';
        }

        cluster.processAsynchronousReplication(100);

        const auto value = cluster.readFrom(
            "invoice:9001",
            "async-01",
            2
        );

        std::cout << "Async read after catch-up: "
                  << value.value_or("<missing>") << '\n';

        // Failover promotes the replica with the current synchronized state.
        cluster.failPrimary();
        cluster.promote("sync-01");

        const auto failoverWrite =
            cluster.write("account:100", "verified");

        std::cout
            << "Failover write acknowledged: "
            << cluster.writeAcknowledged(failoverWrite)
            << '\n';

        cluster.printStatus();

        try {
            cluster.promote("does-not-exist");
        } catch (const std::exception& ex) {
            std::cout << "Expected promotion failure: "
                      << ex.what() << '\n';
        }

    } catch (const std::exception& ex) {
        std::cerr << "Fatal error: " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
