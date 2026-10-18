#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;

enum class NodeState {
    Online,
    Offline
};

enum class StorageKind {
    SharedFilesystem,
    NetworkFileStorage,
    DistributedObjectStorage
};

struct FileRecord {
    string path;
    string owner;
    string content;
    uint64_t version;
    uint64_t size;
};

struct ReplicaRecord {
    string node;
    FileRecord file;
};

class StorageException : public runtime_error {
public:
    explicit StorageException(const string& message)
        : runtime_error(message) {}
};

class CapacityException : public StorageException {
public:
    explicit CapacityException(const string& message)
        : StorageException(message) {}
};

class ConsistencyException : public StorageException {
public:
    explicit ConsistencyException(const string& message)
        : StorageException(message) {}
};

class RepositoryStorageNode {
private:
    string name_;
    NodeState state_;
    unordered_map<string, FileRecord> objects_;

public:
    explicit RepositoryStorageNode(string name)
        : name_(move(name)), state_(NodeState::Online) {}

    const string& name() const {
        return name_;
    }

    bool online() const {
        return state_ == NodeState::Online;
    }

    void setState(NodeState state) {
        state_ = state;
    }

    void put(const FileRecord& record) {
        if (!online()) {
            throw StorageException("Cannot write to offline node " + name_);
        }
        objects_[record.path] = record;
    }

    optional<FileRecord> get(const string& path) const {
        auto iterator = objects_.find(path);

        if (iterator == objects_.end()) {
            return nullopt;
        }

        return iterator->second;
    }

    void corrupt(const string& path, const string& replacement) {
        auto iterator = objects_.find(path);

        if (iterator == objects_.end()) {
            throw StorageException("Replica does not exist");
        }

        iterator->second.content = replacement;
    }
};

class DistributedStorageEngine {
private:
    vector<unique_ptr<RepositoryStorageNode>> nodes_;
    size_t replicationFactor_;

    static uint64_t calculateChecksum(const string& data) {
        // std::hash is used only to make the case study self-contained.
        // Production integrity verification should use a cryptographic
        // digest such as SHA-256 supplied by a suitable cryptographic library.
        return hash<string>{}(data);
    }

    vector<RepositoryStorageNode*> onlineNodes() {
        vector<RepositoryStorageNode*> result;

        for (auto& node : nodes_) {
            if (node->online()) {
                result.push_back(node.get());
            }
        }

        return result;
    }

public:
    DistributedStorageEngine(
        vector<string> nodeNames,
        size_t replicationFactor
    )
        : replicationFactor_(replicationFactor) {

        if (nodeNames.empty()) {
            throw StorageException("At least one storage node is required");
        }

        if (
            replicationFactor == 0 ||
            replicationFactor > nodeNames.size()
        ) {
            throw StorageException("Invalid replication factor");
        }

        for (const auto& name : nodeNames) {
            nodes_.push_back(
                make_unique<RepositoryStorageNode>(name)
            );
        }
    }

    void store(
        const string& path,
        const string& owner,
        const string& content
    ) {
        auto healthy = onlineNodes();

        if (healthy.size() < replicationFactor_) {
            throw StorageException(
                "Insufficient online nodes for requested replication"
            );
        }

        FileRecord record{
            path,
            owner,
            content,
            1,
            static_cast<uint64_t>(content.size())
        };

        for (size_t index = 0; index < replicationFactor_; ++index) {
            healthy[index]->put(record);
        }

        cout << "Stored " << path
             << " on " << replicationFactor_
             << " replicas\n";
    }

    string readVerified(const string& path) {
        vector<FileRecord> candidates;

        for (auto& node : nodes_) {
            if (!node->online()) {
                continue;
            }

            auto record = node->get(path);

            if (record.has_value()) {
                candidates.push_back(*record);
            }
        }

        if (candidates.empty()) {
            throw StorageException("Object is unavailable: " + path);
        }

        const uint64_t expected =
            calculateChecksum(candidates.front().content);

        for (const auto& candidate : candidates) {
            if (calculateChecksum(candidate.content) != expected) {
                throw ConsistencyException(
                    "Replica checksum mismatch for " + path
                );
            }
        }

        return candidates.front().content;
    }

    void setNodeState(
        const string& name,
        NodeState state
    ) {
        for (auto& node : nodes_) {
            if (node->name() == name) {
                node->setState(state);
                return;
            }
        }

        throw StorageException("Unknown storage node " + name);
    }

    void corruptReplica(
        const string& nodeName,
        const string& path,
        const string& replacement
    ) {
        for (auto& node : nodes_) {
            if (node->name() == nodeName) {
                node->corrupt(path, replacement);
                return;
            }
        }

        throw StorageException("Unknown storage node");
    }

    void repair(const string& path) {
        string verifiedContent = readVerified(path);

        FileRecord repaired{
            path,
            "repair-service",
            verifiedContent,
            2,
            static_cast<uint64_t>(verifiedContent.size())
        };

        for (auto& node : nodes_) {
            if (node->online()) {
                node->put(repaired);
            }
        }

        cout << "Repair completed for " << path << '\n';
    }
};

class SharedFilesystem {
private:
    unordered_map<string, FileRecord> files_;
    uint64_t capacity_;
    uint64_t used_ = 0;

public:
    explicit SharedFilesystem(uint64_t capacity)
        : capacity_(capacity) {}

    void write(
        const string& path,
        const string& owner,
        const string& content
    ) {
        uint64_t oldSize = 0;

        auto existing = files_.find(path);
        if (existing != files_.end()) {
            oldSize = existing->second.size;
        }

        uint64_t proposed =
            used_ - oldSize + static_cast<uint64_t>(content.size());

        if (proposed > capacity_) {
            throw CapacityException(
                "Shared filesystem capacity exceeded"
            );
        }

        FileRecord record{
            path,
            owner,
            content,
            existing == files_.end()
                ? 1
                : existing->second.version + 1,
            static_cast<uint64_t>(content.size())
        };

        files_[path] = record;
        used_ = proposed;
    }

    optional<FileRecord> read(const string& path) const {
        auto iterator = files_.find(path);

        if (iterator == files_.end()) {
            return nullopt;
        }

        return iterator->second;
    }

    uint64_t used() const {
        return used_;
    }
};

struct StorageDecision {
    StorageKind kind;
    bool sharedNamespace;
    bool networkDependent;
    bool replicated;
    string reason;
};

StorageDecision chooseStorage(
    bool requiresPosixSemantics,
    bool multipleHostsNeedSameFiles,
    bool needsNodeFailureTolerance
) {
    if (needsNodeFailureTolerance) {
        return {
            StorageKind::DistributedObjectStorage,
            false,
            true,
            true,
            "Replication and node-level fault tolerance dominate"
        };
    }

    if (multipleHostsNeedSameFiles) {
        return {
            StorageKind::NetworkFileStorage,
            true,
            true,
            false,
            "Multiple hosts need one shared filesystem namespace"
        };
    }

    return {
        StorageKind::SharedFilesystem,
        true,
        false,
        false,
        requiresPosixSemantics
            ? "Local filesystem semantics are required"
            : "Simple shared filesystem semantics are sufficient"
    };
}

void printDecision(const StorageDecision& decision) {
    cout << "Storage decision: ";

    switch (decision.kind) {
        case StorageKind::SharedFilesystem:
            cout << "shared filesystem";
            break;
        case StorageKind::NetworkFileStorage:
            cout << "network file storage";
            break;
        case StorageKind::DistributedObjectStorage:
            cout << "distributed object storage";
            break;
    }

    cout << "\nReason: " << decision.reason << '\n';
}

int main() {
    cout << "=== File Storage Governance Case Study ===\n\n";

    try {
        SharedFilesystem sharedFilesystem(1024);

        sharedFilesystem.write(
            "/engineering/architecture.md",
            "architect",
            "Shared filesystem design"
        );

        auto document =
            sharedFilesystem.read("/engineering/architecture.md");

        if (document.has_value()) {
            cout << "Shared filesystem read: "
                 << document->content << '\n';
        }

        DistributedStorageEngine distributed(
            {"storage-a", "storage-b", "storage-c"},
            2
        );

        distributed.store(
            "datasets/events/2026-10.bin",
            "analytics-service",
            "customer event payload"
        );

        cout << "Distributed read: "
             << distributed.readVerified(
                    "datasets/events/2026-10.bin"
                )
             << '\n';

        distributed.setNodeState(
            "storage-a",
            NodeState::Offline
        );

        cout << "Read after node failure: "
             << distributed.readVerified(
                    "datasets/events/2026-10.bin"
                )
             << '\n';

        distributed.setNodeState(
            "storage-a",
            NodeState::Online
        );

        distributed.corruptReplica(
            "storage-b",
            "datasets/events/2026-10.bin",
            "corrupted payload"
        );

        try {
            distributed.readVerified(
                "datasets/events/2026-10.bin"
            );
        } catch (const ConsistencyException& exception) {
            cout << "Corruption detected: "
                 << exception.what() << '\n';
        }

        // The corrupted replica is excluded by taking the healthy node back
        // as the authoritative source, after which repair rewrites replicas.
        distributed.setNodeState(
            "storage-b",
            NodeState::Offline
        );

        distributed.repair(
            "datasets/events/2026-10.bin"
        );

        distributed.setNodeState(
            "storage-b",
            NodeState::Online
        );

        cout << "Post-repair read: "
             << distributed.readVerified(
                    "datasets/events/2026-10.bin"
                )
             << '\n';

        cout << '\n';

        printDecision(
            chooseStorage(false, true, false)
        );

        printDecision(
            chooseStorage(false, false, true)
        );

        try {
            SharedFilesystem constrained(5);
            constrained.write(
                "/large.bin",
                "service",
                "123456789"
            );
        } catch (const CapacityException& exception) {
            cout << "Capacity failure: "
                 << exception.what() << '\n';
        }

    } catch (const exception& exception) {
        cerr << "Storage case study failed: "
             << exception.what() << '\n';
        return 1;
    }

    return 0;
}
