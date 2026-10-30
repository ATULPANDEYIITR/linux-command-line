#include <algorithm>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * C++17 database high-availability and merge-eligibility engine.
 *
 * The cluster uses a fixed voter set, majority quorum, multi-zone placement,
 * synchronous write acknowledgements, bounded replica lag, and fencing.
 *
 * Operations are serialized with a mutex because writes, health transitions,
 * and primary promotion must not race against one another.
 */

enum class NodeRole {
    Primary,
    Replica
};

enum class NodeState {
    Healthy,
    Suspect,
    Down,
    Fenced
};

struct Node {
    std::string id;
    std::string zone;
    NodeRole role;
    NodeState state;
    int priority;
    bool voter;
    bool reachable;
    bool fenced;
    long long appliedIndex;
    long long lagMs;

    bool isLiveVoter() const {
        return voter &&
               reachable &&
               state == NodeState::Healthy &&
               !fenced;
    }
};

struct HAPolicy {
    int expectedVoters = 3;
    int synchronousReplicaAcks = 1;
    long long maximumLagMs = 500;
    int minimumLiveZones = 2;

    void validate() const {
        if (expectedVoters < 3 || expectedVoters % 2 == 0) {
            throw std::invalid_argument(
                "Expected voter count must be an odd number of at least three."
            );
        }
        if (synchronousReplicaAcks < 1 ||
            synchronousReplicaAcks >= expectedVoters) {
            throw std::invalid_argument("Invalid synchronous acknowledgement count.");
        }
        if (maximumLagMs < 0) {
            throw std::invalid_argument("Maximum replication lag cannot be negative.");
        }
        if (minimumLiveZones < 1 || minimumLiveZones > expectedVoters) {
            throw std::invalid_argument("Invalid minimum live-zone requirement.");
        }
    }

    int quorum() const {
        return expectedVoters / 2 + 1;
    }
};

struct FailoverDecision {
    bool eligible = false;
    std::optional<std::string> candidateId;
    int liveVoters = 0;
    int liveZones = 0;
    std::string reason;
};

class HAError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class QuorumError : public HAError {
public:
    using HAError::HAError;
};

class UnsafePromotionError : public HAError {
public:
    using HAError::HAError;
};

class HACluster {
private:
    std::string clusterId;
    std::map<std::string, Node> nodes;
    HAPolicy policy;
    std::string primaryId;
    long long commitIndex = 0;
    long long term = 1;
    std::vector<std::string> audit;
    mutable std::mutex operationMutex;

    void record(const std::string& event) {
        audit.push_back(
            "term=" + std::to_string(term) +
            " index=" + std::to_string(commitIndex) +
            " event=" + event
        );
    }

    Node& primary() {
        auto it = nodes.find(primaryId);
        if (it == nodes.end()) {
            throw HAError("Configured primary does not exist.");
        }
        return it->second;
    }

    const Node& primary() const {
        auto it = nodes.find(primaryId);
        if (it == nodes.end()) {
            throw HAError("Configured primary does not exist.");
        }
        return it->second;
    }

    std::vector<Node*> liveVoters() {
        std::vector<Node*> result;
        for (auto& entry : nodes) {
            if (entry.second.isLiveVoter()) {
                result.push_back(&entry.second);
            }
        }
        return result;
    }

    std::vector<const Node*> liveVoters() const {
        std::vector<const Node*> result;
        for (const auto& entry : nodes) {
            if (entry.second.isLiveVoter()) {
                result.push_back(&entry.second);
            }
        }
        return result;
    }

    FailoverDecision evaluateUnlocked() const {
        FailoverDecision decision;
        const auto live = liveVoters();
        std::set<std::string> zones;

        for (const Node* node : live) {
            zones.insert(node->zone);
        }

        decision.liveVoters = static_cast<int>(live.size());
        decision.liveZones = static_cast<int>(zones.size());

        if (primary().isLiveVoter()) {
            decision.reason = "Current primary is healthy.";
            return decision;
        }

        if (decision.liveVoters < policy.quorum()) {
            decision.reason = "Majority quorum is unavailable.";
            return decision;
        }

        if (decision.liveZones < policy.minimumLiveZones) {
            decision.reason = "Insufficient live availability zones.";
            return decision;
        }

        // A candidate must contain every committed index, not merely have
        // a low measured lag. This protects the configured zero-data-loss policy.
        std::vector<const Node*> candidates;
        for (const Node* node : live) {
            if (node->role == NodeRole::Replica &&
                node->appliedIndex >= commitIndex &&
                node->lagMs <= policy.maximumLagMs) {
                candidates.push_back(node);
            }
        }

        if (candidates.empty()) {
            decision.reason = "No fully caught-up replica satisfies the lag policy.";
            return decision;
        }

        std::sort(
            candidates.begin(),
            candidates.end(),
            [](const Node* left, const Node* right) {
                if (left->appliedIndex != right->appliedIndex) {
                    return left->appliedIndex > right->appliedIndex;
                }
                if (left->priority != right->priority) {
                    return left->priority < right->priority;
                }
                return left->id < right->id;
            }
        );

        decision.eligible = true;
        decision.candidateId = candidates.front()->id;
        decision.reason = "Quorum and replication safety conditions are satisfied.";
        return decision;
    }

public:
    HACluster(
        std::string id,
        std::vector<Node> initialNodes,
        HAPolicy haPolicy = {}
    )
        : clusterId(std::move(id)), policy(haPolicy) {
        policy.validate();

        if (clusterId.empty()) {
            throw std::invalid_argument("Cluster identifier cannot be empty.");
        }
        if (static_cast<int>(initialNodes.size()) != policy.expectedVoters) {
            throw std::invalid_argument("Node count does not match expected voters.");
        }

        int primaryCount = 0;
        for (auto& node : initialNodes) {
            if (node.id.empty() || node.zone.empty()) {
                throw std::invalid_argument("Node identifier and zone are required.");
            }
            if (node.priority < 0 || node.appliedIndex < 0 || node.lagMs < 0) {
                throw std::invalid_argument("Invalid node priority or replication state.");
            }
            if (node.fenced && node.role == NodeRole::Primary) {
                throw std::invalid_argument("A fenced node cannot be primary.");
            }
            if (!node.voter) {
                throw std::invalid_argument("Every configured node must vote.");
            }
            if (node.role == NodeRole::Primary) {
                ++primaryCount;
                primaryId = node.id;
            }

            const std::string nodeId = node.id;
            if (!nodes.emplace(nodeId, std::move(node)).second) {
                throw std::invalid_argument("Duplicate node identifier.");
            }
        }

        if (primaryCount != 1) {
            throw std::invalid_argument("Exactly one initial primary is required.");
        }

        record("cluster_initialized primary=" + primaryId);
    }

    long long commitWrite(const std::string& payload) {
        if (payload.empty()) {
            throw std::invalid_argument("Write payload cannot be empty.");
        }
        if (payload.size() > 4096) {
            throw std::invalid_argument("Write payload exceeds 4096 bytes.");
        }

        std::lock_guard<std::mutex> guard(operationMutex);

        Node& activePrimary = primary();
        if (activePrimary.role != NodeRole::Primary ||
            !activePrimary.isLiveVoter()) {
            throw HAError("Current primary is not operational.");
        }

        const auto live = liveVoters();
        if (static_cast<int>(live.size()) < policy.quorum()) {
            throw QuorumError("Write rejected because majority quorum is unavailable.");
        }

        const int requiredAcks = std::max(
            policy.synchronousReplicaAcks,
            policy.quorum() - 1
        );

        std::vector<Node*> replicas;
        for (Node* node : live) {
            if (node->id != primaryId && node->role == NodeRole::Replica) {
                replicas.push_back(node);
            }
        }

        std::sort(
            replicas.begin(),
            replicas.end(),
            [](const Node* left, const Node* right) {
                if (left->priority != right->priority) {
                    return left->priority < right->priority;
                }
                return left->id < right->id;
            }
        );

        if (static_cast<int>(replicas.size()) < requiredAcks) {
            throw QuorumError("Not enough healthy replicas for synchronous acknowledgements.");
        }

        ++commitIndex;
        activePrimary.appliedIndex = commitIndex;
        activePrimary.lagMs = 0;

        for (int i = 0; i < static_cast<int>(replicas.size()); ++i) {
            if (i < requiredAcks) {
                replicas[i]->appliedIndex = commitIndex;
                replicas[i]->lagMs = 0;
            } else {
                // Unacknowledged asynchronous replicas may temporarily lag.
                replicas[i]->lagMs += 100;
            }
        }

        record("write_committed");
        return commitIndex;
    }

    void replicate(const std::string& nodeId) {
        std::lock_guard<std::mutex> guard(operationMutex);

        auto it = nodes.find(nodeId);
        if (it == nodes.end()) {
            throw HAError("Unknown replication target: " + nodeId);
        }

        Node& replica = it->second;
        if (replica.role != NodeRole::Replica || !replica.isLiveVoter()) {
            throw HAError("Replication target must be a healthy replica.");
        }

        replica.appliedIndex = commitIndex;
        replica.lagMs = 0;
        record("replica_caught_up node=" + nodeId);
    }

    void markDown(const std::string& nodeId) {
        std::lock_guard<std::mutex> guard(operationMutex);

        auto it = nodes.find(nodeId);
        if (it == nodes.end()) {
            throw HAError("Unknown node: " + nodeId);
        }
        if (it->second.fenced) {
            throw HAError("A fenced node must be rebuilt before recovery.");
        }

        it->second.state = NodeState::Down;
        it->second.reachable = false;
        record("node_down node=" + nodeId);
    }

    FailoverDecision evaluateFailover() const {
        std::lock_guard<std::mutex> guard(operationMutex);
        return evaluateUnlocked();
    }

    std::string failover() {
        std::lock_guard<std::mutex> guard(operationMutex);

        const FailoverDecision decision = evaluateUnlocked();
        if (!decision.eligible || !decision.candidateId.has_value()) {
            throw UnsafePromotionError(decision.reason);
        }

        Node& oldPrimary = primary();
        Node& candidate = nodes.at(*decision.candidateId);

        // Promotion is a state transition: disable the old writer first.
        oldPrimary.role = NodeRole::Replica;
        oldPrimary.state = NodeState::Fenced;
        oldPrimary.fenced = true;
        oldPrimary.reachable = false;

        candidate.role = NodeRole::Primary;
        candidate.state = NodeState::Healthy;
        candidate.fenced = false;
        candidate.reachable = true;

        primaryId = candidate.id;
        ++term;

        record(
            "automatic_failover old=" + oldPrimary.id +
            " new=" + candidate.id
        );

        return primaryId;
    }

    void rejoinAsReplica(const std::string& nodeId) {
        std::lock_guard<std::mutex> guard(operationMutex);

        auto it = nodes.find(nodeId);
        if (it == nodes.end() || nodeId == primaryId) {
            throw HAError("Recovery target must be a non-primary cluster node.");
        }

        Node& node = it->second;
        node.role = NodeRole::Replica;
        node.state = NodeState::Healthy;
        node.fenced = false;
        node.reachable = true;
        node.appliedIndex = commitIndex;
        node.lagMs = 0;

        record("node_rejoined_as_replica node=" + nodeId);
    }

    void printStatus() const {
        std::lock_guard<std::mutex> guard(operationMutex);

        const auto live = liveVoters();
        std::set<std::string> zones;
        for (const Node* node : live) {
            zones.insert(node->zone);
        }

        std::cout
            << "Cluster: " << clusterId
            << "\nPrimary: " << primaryId
            << "\nTerm: " << term
            << "\nCommit index: " << commitIndex
            << "\nLive voters: " << live.size()
            << "\nLive zones: " << zones.size()
            << "\nQuorum required: " << policy.quorum()
            << "\nNodes:\n";

        for (const auto& entry : nodes) {
            const Node& node = entry.second;
            std::cout
                << "  " << node.id
                << " zone=" << node.zone
                << " role=" << (node.role == NodeRole::Primary ? "primary" : "replica")
                << " index=" << node.appliedIndex
                << " lag_ms=" << node.lagMs
                << " reachable=" << std::boolalpha << node.reachable
                << " fenced=" << node.fenced
                << '\n';
        }
    }

    void printAudit() const {
        std::lock_guard<std::mutex> guard(operationMutex);
        std::cout << "\nAudit trail:\n";
        for (const auto& entry : audit) {
            std::cout << "  " << entry << '\n';
        }
    }
};

std::vector<Node> makeNodes() {
    return {
        {"db-a", "zone-a", NodeRole::Primary, NodeState::Healthy,
         0, true, true, false, 0, 0},
        {"db-b", "zone-b", NodeRole::Replica, NodeState::Healthy,
         1, true, true, false, 0, 0},
        {"db-c", "zone-c", NodeRole::Replica, NodeState::Healthy,
         2, true, true, false, 0, 0}
    };
}

int main() {
    try {
        HACluster cluster("payments-production", makeNodes());

        cluster.commitWrite("payment-5001");
        cluster.commitWrite("payment-5002");

        std::cout << "Before primary failure:\n";
        cluster.printStatus();

        cluster.markDown("db-a");

        const FailoverDecision decision = cluster.evaluateFailover();
        std::cout << "\nFailover decision: " << decision.reason
                  << "\nEligible: " << std::boolalpha << decision.eligible
                  << "\nLive voters: " << decision.liveVoters
                  << "\nLive zones: " << decision.liveZones
                  << '\n';

        if (!decision.eligible) {
            throw UnsafePromotionError(decision.reason);
        }

        const std::string newPrimary = cluster.failover();
        if (newPrimary != "db-b") {
            throw HAError("Unexpected promotion candidate.");
        }

        cluster.rejoinAsReplica("db-a");

        std::cout << "\nAfter failover and recovery:\n";
        cluster.printStatus();
        cluster.printAudit();

        // Quorum-loss case: one surviving voter cannot safely promote.
        HACluster isolated("quorum-loss", makeNodes());
        isolated.markDown("db-a");
        isolated.markDown("db-c");

        const auto rejected = isolated.evaluateFailover();
        if (rejected.eligible) {
            throw HAError("Quorum-loss test unexpectedly became eligible.");
        }

        std::cout << "\nExpected quorum-loss rejection: "
                  << rejected.reason << '\n';

    } catch (const std::exception& error) {
        std::cerr << "HA engine error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
