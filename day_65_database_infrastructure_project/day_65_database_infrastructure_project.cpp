#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class NodeRole {
    Primary,
    Replica
};

enum class NodeState {
    Healthy,
    Degraded,
    Failed,
    Recovering
};

enum class BackupType {
    Full,
    Incremental
};

string toString(NodeRole role) {
    return role == NodeRole::Primary ? "PRIMARY" : "REPLICA";
}

string toString(NodeState state) {
    switch (state) {
        case NodeState::Healthy: return "HEALTHY";
        case NodeState::Degraded: return "DEGRADED";
        case NodeState::Failed: return "FAILED";
        case NodeState::Recovering: return "RECOVERING";
    }
    return "UNKNOWN";
}

struct Configuration {
    int maxReplicationLag = 5;
    int requiredReplicas = 1;
    int connectionLimit = 100;
    double maxCpu = 85.0;
    double maxMemory = 90.0;

    void validate() const {
        if (maxReplicationLag < 0 ||
            requiredReplicas < 0 ||
            connectionLimit <= 0 ||
            maxCpu <= 0 ||
            maxMemory <= 0) {
            throw invalid_argument("Invalid infrastructure configuration");
        }
    }
};

struct DatabaseNode {
    string id;
    string region;
    string availabilityZone;
    NodeRole role;
    NodeState state = NodeState::Healthy;

    long long transactionPosition = 0;
    int replicationLag = 0;
    int connections = 0;
    int connectionLimit = 100;

    double cpu = 20.0;
    double memory = 40.0;

    DatabaseNode(
        string nodeId,
        string nodeRegion,
        string zone,
        NodeRole nodeRole,
        int limit
    ) :
        id(move(nodeId)),
        region(move(nodeRegion)),
        availabilityZone(move(zone)),
        role(nodeRole),
        connectionLimit(limit) {

        if (id.empty() || region.empty() ||
            availabilityZone.empty() || limit <= 0) {
            throw invalid_argument("Invalid database node");
        }
    }

    bool available() const {
        return state == NodeState::Healthy &&
               connections < connectionLimit;
    }

    bool acquire() {
        if (!available()) return false;
        ++connections;
        return true;
    }

    void release() {
        connections = max(0, connections - 1);
    }
};

struct Backup {
    string id;
    BackupType type;
    long long transactionPosition;
    string checksum;
    bool verified;
    optional<string> parentId;
};

struct Metric {
    string nodeId;
    string name;
    double value;
    string severity;
};

struct FailoverEvent {
    string oldPrimary;
    string newPrimary;
    long long promotedPosition;
};

class BackupManager {
private:
    vector<Backup> backups;
    int sequence = 0;

public:
    const Backup& create(const DatabaseNode& primary, BackupType type) {
        if (primary.role != NodeRole::Primary ||
            primary.state != NodeState::Healthy) {
            throw runtime_error("Backup requires a healthy primary");
        }

        optional<string> parent;

        if (type == BackupType::Incremental) {
            auto it = find_if(
                backups.rbegin(),
                backups.rend(),
                [](const Backup& backup) {
                    return backup.type == BackupType::Full &&
                           backup.verified;
                }
            );

            if (it == backups.rend()) {
                throw runtime_error(
                    "Incremental backup requires a verified full backup"
                );
            }

            parent = it->id;
        }

        string id = "backup-" + to_string(++sequence);

        string payload =
            primary.id + ":" +
            to_string(primary.transactionPosition) + ":" + id;

        // A deterministic demonstration fingerprint, not a production
        // cryptographic checksum. Production backups require SHA-256.
        size_t hash = std::hash<string>{}(payload);

        ostringstream checksum;
        checksum << hex << hash;

        backups.push_back({
            id,
            type,
            primary.transactionPosition,
            checksum.str(),
            true,
            parent
        });

        return backups.back();
    }

    bool verify(const string& id) const {
        auto it = find_if(
            backups.begin(),
            backups.end(),
            [&](const Backup& backup) {
                return backup.id == id;
            }
        );

        if (it == backups.end() || !it->verified) {
            return false;
        }

        if (it->type == BackupType::Incremental) {
            if (!it->parentId) return false;

            return any_of(
                backups.begin(),
                backups.end(),
                [&](const Backup& parent) {
                    return parent.id == *it->parentId &&
                           parent.type == BackupType::Full &&
                           parent.verified;
                }
            );
        }

        return true;
    }

    void restore(const string& id, DatabaseNode& target) const {
        if (!verify(id)) {
            throw runtime_error("Backup verification failed");
        }

        auto it = find_if(
            backups.begin(),
            backups.end(),
            [&](const Backup& backup) {
                return backup.id == id;
            }
        );

        target.state = NodeState::Recovering;
        target.transactionPosition = it->transactionPosition;
        target.replicationLag = 0;
        target.state = NodeState::Healthy;
    }

    void print() const {
        cout << "\nBackup inventory\n";

        for (const auto& backup : backups) {
            cout << backup.id
                 << " | position=" << backup.transactionPosition
                 << " | verified=" << boolalpha << backup.verified
                 << " | checksum=" << backup.checksum
                 << '\n';
        }
    }
};

class Cache {
private:
    struct Entry {
        string value;
        chrono::steady_clock::time_point expiresAt;
    };

    map<string, Entry> entries;
    chrono::seconds ttl;
    size_t hits = 0;
    size_t misses = 0;

public:
    explicit Cache(int ttlSeconds) : ttl(ttlSeconds) {
        if (ttlSeconds <= 0) {
            throw invalid_argument("Cache TTL must be positive");
        }
    }

    optional<string> get(const string& key) {
        auto it = entries.find(key);

        if (it == entries.end()) {
            ++misses;
            return nullopt;
        }

        if (chrono::steady_clock::now() >= it->second.expiresAt) {
            entries.erase(it);
            ++misses;
            return nullopt;
        }

        ++hits;
        return it->second.value;
    }

    void put(const string& key, const string& value) {
        entries[key] = {
            value,
            chrono::steady_clock::now() + ttl
        };
    }

    void invalidate(const string& key) {
        entries.erase(key);
    }

    void clear() {
        entries.clear();
    }

    void report() const {
        size_t total = hits + misses;
        double ratio = total
            ? static_cast<double>(hits) / total
            : 0.0;

        cout << "Cache hits: " << hits
             << ", misses: " << misses
             << ", hit ratio: " << fixed << setprecision(2)
             << ratio * 100 << "%\n";
    }
};

class MonitoringService {
private:
    vector<Metric> metrics;

public:
    void collect(const DatabaseNode& node, const Configuration& config) {
        auto addMetric = [&](string name, double value, double threshold) {
            string severity =
                value >= threshold ? "WARNING" : "NORMAL";

            metrics.push_back({
                node.id,
                name,
                value,
                severity
            });

            if (severity == "WARNING") {
                cout << "[ALERT] " << node.id
                     << " " << name << "=" << value << '\n';
            }
        };

        addMetric("CPU", node.cpu, config.maxCpu);
        addMetric("MEMORY", node.memory, config.maxMemory);
        addMetric(
            "REPLICATION_LAG",
            node.replicationLag,
            config.maxReplicationLag
        );

        if (node.state == NodeState::Failed) {
            metrics.push_back({
                node.id,
                "NODE_STATE",
                1,
                "CRITICAL"
            });
        }
    }

    void report() const {
        cout << "\nCollected monitoring records: "
             << metrics.size() << '\n';
    }
};

class DatabaseCluster {
private:
    vector<DatabaseNode> nodes;
    Configuration config;
    vector<FailoverEvent> history;
    bool failoverInProgress = false;

    DatabaseNode* findNode(const string& id) {
        auto it = find_if(
            nodes.begin(),
            nodes.end(),
            [&](const DatabaseNode& node) {
                return node.id == id;
            }
        );

        return it == nodes.end() ? nullptr : &(*it);
    }

public:
    DatabaseCluster(
        vector<DatabaseNode> clusterNodes,
        Configuration configuration
    ) :
        nodes(move(clusterNodes)),
        config(configuration) {

        config.validate();

        int primaryCount = count_if(
            nodes.begin(),
            nodes.end(),
            [](const DatabaseNode& node) {
                return node.role == NodeRole::Primary;
            }
        );

        if (primaryCount != 1) {
            throw invalid_argument(
                "Cluster must have exactly one primary"
            );
        }

        set<string> ids;

        for (const auto& node : nodes) {
            if (!ids.insert(node.id).second) {
                throw invalid_argument("Duplicate node identifier");
            }
        }
    }

    DatabaseNode& primary() {
        for (auto& node : nodes) {
            if (node.role == NodeRole::Primary) {
                return node;
            }
        }
        throw runtime_error("No primary exists");
    }

    const vector<DatabaseNode>& getNodes() const {
        return nodes;
    }

    vector<DatabaseNode*> healthyReplicas() {
        vector<DatabaseNode*> result;

        for (auto& node : nodes) {
            if (node.role == NodeRole::Replica &&
                node.available() &&
                node.replicationLag <= config.maxReplicationLag) {
                result.push_back(&node);
            }
        }

        return result;
    }

    long long write(int transactions) {
        if (transactions <= 0) {
            throw invalid_argument("Transaction count must be positive");
        }

        auto& leader = primary();

        if (!leader.acquire()) {
            throw runtime_error("Primary unavailable");
        }

        try {
            leader.transactionPosition += transactions;

            for (auto& node : nodes) {
                if (node.role == NodeRole::Replica &&
                    node.state == NodeState::Healthy) {
                    node.replicationLag += transactions;
                }
            }

            leader.release();
            return leader.transactionPosition;
        } catch (...) {
            leader.release();
            throw;
        }
    }

    void replicate(const string& replicaId, int transactions) {
        if (transactions < 0) {
            throw invalid_argument("Negative replication amount");
        }

        DatabaseNode* replica = findNode(replicaId);

        if (!replica ||
            replica->role != NodeRole::Replica ||
            replica->state != NodeState::Healthy) {
            throw runtime_error("Invalid replication target");
        }

        replica->replicationLag = max(
            0,
            replica->replicationLag - transactions
        );

        replica->transactionPosition =
            primary().transactionPosition - replica->replicationLag;
    }

    DatabaseNode& selectReadNode() {
        auto replicas = healthyReplicas();

        if (!replicas.empty()) {
            auto best = min_element(
                replicas.begin(),
                replicas.end(),
                [](const DatabaseNode* a, const DatabaseNode* b) {
                    if (a->replicationLag != b->replicationLag) {
                        return a->replicationLag < b->replicationLag;
                    }

                    if (a->connections != b->connections) {
                        return a->connections < b->connections;
                    }

                    return a->cpu < b->cpu;
                }
            );

            return **best;
        }

        if (primary().available()) {
            return primary();
        }

        throw runtime_error("No readable node available");
    }

    string read(const string& key, Cache& cache) {
        if (key.empty()) {
            throw invalid_argument("Read key cannot be empty");
        }

        auto cached = cache.get(key);

        if (cached) {
            return *cached;
        }

        auto& node = selectReadNode();

        if (!node.acquire()) {
            throw runtime_error("Read node saturated");
        }

        string result =
            "key=" + key +
            ",served_by=" + node.id +
            ",position=" + to_string(node.transactionPosition);

        cache.put(key, result);
        node.release();

        return result;
    }

    FailoverEvent failover() {
        if (failoverInProgress) {
            throw runtime_error("Concurrent failover rejected");
        }

        failoverInProgress = true;

        try {
            auto& oldPrimary = primary();
            oldPrimary.state = NodeState::Failed;

            auto candidates = healthyReplicas();

            if (candidates.empty()) {
                throw runtime_error("No promotable replica");
            }

            auto best = max_element(
                candidates.begin(),
                candidates.end(),
                [](const DatabaseNode* a, const DatabaseNode* b) {
                    return a->transactionPosition <
                           b->transactionPosition;
                }
            );

            DatabaseNode& promoted = **best;

            promoted.role = NodeRole::Primary;
            promoted.replicationLag = 0;

            FailoverEvent event {
                oldPrimary.id,
                promoted.id,
                promoted.transactionPosition
            };

            history.push_back(event);

            failoverInProgress = false;
            return event;
        } catch (...) {
            failoverInProgress = false;
            throw;
        }
    }

    void rejoin(const string& nodeId) {
        DatabaseNode* node = findNode(nodeId);

        if (!node) {
            throw runtime_error("Unknown recovery node");
        }

        if (node->id == primary().id) {
            throw runtime_error("Cannot rejoin active primary");
        }

        node->role = NodeRole::Replica;
        node->state = NodeState::Recovering;
        node->transactionPosition = primary().transactionPosition;
        node->replicationLag = 0;
        node->state = NodeState::Healthy;
    }

    void report() const {
        cout << "\nDATABASE CLUSTER REPORT\n";

        for (const auto& node : nodes) {
            cout << left << setw(18) << node.id
                 << setw(10) << toString(node.role)
                 << setw(12) << toString(node.state)
                 << "position=" << node.transactionPosition
                 << " lag=" << node.replicationLag
                 << " connections=" << node.connections
                 << '\n';
        }

        cout << "Healthy replicas: "
             << count_if(
                 nodes.begin(),
                 nodes.end(),
                 [&](const DatabaseNode& node) {
                     return node.role == NodeRole::Replica &&
                            node.available() &&
                            node.replicationLag <= config.maxReplicationLag;
                 }
             ) << '\n';

        cout << "Failover events: " << history.size() << '\n';
    }
};

class InfrastructureApplication {
private:
    Configuration config;
    DatabaseCluster cluster;
    Cache cache;
    BackupManager backups;
    MonitoringService monitoring;

public:
    InfrastructureApplication() :
        config(),
        cluster(
            {
                DatabaseNode(
                    "primary-01", "ap-south-1", "zone-a",
                    NodeRole::Primary, 100
                ),
                DatabaseNode(
                    "replica-01", "ap-south-1", "zone-b",
                    NodeRole::Replica, 100
                ),
                DatabaseNode(
                    "replica-02", "ap-south-2", "zone-c",
                    NodeRole::Replica, 100
                )
            },
            config
        ),
        cache(60) {}

    void run() {
        cout << "HIGH AVAILABILITY DATABASE INFRASTRUCTURE\n";

        cout << "\n1. Write transactions\n";
        cluster.write(20);
        cluster.write(10);

        cout << "\n2. Synchronize replicas\n";
        cluster.replicate("replica-01", 25);
        cluster.replicate("replica-02", 20);

        cout << "\n3. Route reads through replicas and cache\n";
        cout << cluster.read("customer:1001", cache) << '\n';
        cout << cluster.read("customer:1001", cache) << '\n';
        cache.report();

        cout << "\n4. Create full and incremental backups\n";
        const Backup& full = backups.create(
            cluster.primary(),
            BackupType::Full
        );

        const Backup& incremental = backups.create(
            cluster.primary(),
            BackupType::Incremental
        );

        cout << "Created " << full.id
             << " and " << incremental.id << '\n';

        cout << "\n5. Collect metrics\n";

        for (const auto& node : cluster.getNodes()) {
            monitoring.collect(node, config);
        }

        cout << "\n6. Simulate primary failure\n";
        cluster.primary().state = NodeState::Failed;

        FailoverEvent event = cluster.failover();

        cout << "Promoted " << event.newPrimary
             << " at transaction position "
             << event.promotedPosition << '\n';

        cache.clear();

        cout << "\n7. Recover the previous primary\n";
        cluster.rejoin("primary-01");

        cout << "\n8. Restore backup to isolated node\n";

        DatabaseNode restoreTarget(
            "restore-test",
            "ap-south-1",
            "zone-d",
            NodeRole::Replica,
            50
        );

        backups.restore(full.id, restoreTarget);

        cout << "Restored transaction position: "
             << restoreTarget.transactionPosition << '\n';

        backups.print();
        monitoring.report();
        cluster.report();
    }
};

void runTests() {
    Configuration config;

    DatabaseCluster cluster(
        {
            DatabaseNode(
                "p", "region-a", "zone-a",
                NodeRole::Primary, 10
            ),
            DatabaseNode(
                "r1", "region-a", "zone-b",
                NodeRole::Replica, 10
            )
        },
        config
    );

    Cache cache(60);

    assert(cluster.write(10) == 10);
    cluster.replicate("r1", 10);

    assert(cluster.read("test", cache).find("r1") != string::npos);
    assert(cluster.read("test", cache).find("r1") != string::npos);

    cluster.primary().state = NodeState::Failed;

    auto event = cluster.failover();
    assert(event.newPrimary == "r1");

    cluster.rejoin("p");
    assert(cluster.primary().id == "r1");

    BackupManager backups;
    const Backup& full = backups.create(
        cluster.primary(),
        BackupType::Full
    );

    assert(backups.verify(full.id));

    cout << "All C++17 infrastructure tests passed.\n";
}

int main(int argc, char* argv[]) {
    try {
        if (argc > 1 && string(argv[1]) == "--test") {
            runTests();
        } else {
            InfrastructureApplication application;
            application.run();
        }

        return 0;
    } catch (const exception& error) {
        cerr << "Infrastructure error: "
             << error.what() << '\n';
        return 1;
    }
}
