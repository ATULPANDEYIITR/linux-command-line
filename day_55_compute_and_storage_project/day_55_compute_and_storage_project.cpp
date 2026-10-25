#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * C++17 repository-independent cloud architecture case study.
 * Models request routing, compute health, versioned object storage,
 * backup integrity manifests, and deployment eligibility.
 */

enum class InstanceState { Running, Stopped, Unhealthy };
enum class ObjectState { Active, Deleted };

std::string toString(InstanceState state) {
    switch (state) {
        case InstanceState::Running: return "running";
        case InstanceState::Stopped: return "stopped";
        case InstanceState::Unhealthy: return "unhealthy";
    }
    throw std::logic_error("Unknown instance state");
}

struct ComputeInstance {
    std::string id;
    std::string zone;
    int capacity;
    int activeRequests = 0;
    InstanceState state = InstanceState::Running;

    ComputeInstance(std::string instanceId, std::string availabilityZone, int limit)
        : id(std::move(instanceId)),
          zone(std::move(availabilityZone)),
          capacity(limit) {
        if (id.empty() || zone.empty() || capacity <= 0) {
            throw std::invalid_argument("Invalid compute instance configuration");
        }
    }

    double utilization() const {
        return static_cast<double>(activeRequests) / capacity;
    }
};

struct ObjectVersion {
    std::string key;
    int version;
    std::string content;
    std::string checksum;
    ObjectState state = ObjectState::Active;
};

class ObjectStore {
private:
    std::map<std::string, std::vector<ObjectVersion>> objects_;
    std::size_t maximumBytes_;

    // FNV-1a is used as a deterministic demonstration checksum, not a
    // cryptographic integrity guarantee. Production systems need SHA-256
    // or an equivalent authenticated integrity mechanism.
    static std::string checksum(const std::string& content) {
        std::uint64_t hash = 14695981039346656037ULL;
        for (unsigned char byte : content) {
            hash ^= byte;
            hash *= 1099511628211ULL;
        }
        std::ostringstream out;
        out << std::hex << std::setw(16) << std::setfill('0') << hash;
        return out.str();
    }

    static void validateKey(const std::string& key) {
        if (key.empty() || key.front() == '/' ||
            key.find('\\') != std::string::npos ||
            key.find("../") != std::string::npos ||
            key == ".." ||
            (key.size() >= 3 && key.substr(key.size() - 3) == "/..")) {
            throw std::invalid_argument("Unsafe object key");
        }
    }

public:
    explicit ObjectStore(std::size_t maximumBytes = 1'000'000)
        : maximumBytes_(maximumBytes) {
        if (maximumBytes_ == 0) {
            throw std::invalid_argument("Object size limit must be positive");
        }
    }

    ObjectVersion put(const std::string& key, const std::string& content) {
        validateKey(key);
        if (content.size() > maximumBytes_) {
            throw std::length_error("Object exceeds storage limit");
        }

        auto& history = objects_[key];
        ObjectVersion object{
            key,
            static_cast<int>(history.size()) + 1,
            content,
            checksum(content),
            ObjectState::Active
        };
        history.push_back(object);
        return object;
    }

    ObjectVersion get(const std::string& key, int version = -1) const {
        auto found = objects_.find(key);
        if (found == objects_.end()) {
            throw std::out_of_range("Object not found: " + key);
        }

        const auto& history = found->second;
        if (version == -1) {
            for (auto it = history.rbegin(); it != history.rend(); ++it) {
                if (it->state == ObjectState::Active) return *it;
                break;
            }
        } else {
            if (version < 1 || version > static_cast<int>(history.size())) {
                throw std::out_of_range("Object version not found");
            }
            const auto& object = history[static_cast<std::size_t>(version - 1)];
            if (object.state == ObjectState::Active) return object;
        }
        throw std::out_of_range("Active object not found: " + key);
    }

    void erase(const std::string& key) {
        ObjectVersion object = get(key);
        auto& history = objects_.at(key);
        history.back().state = ObjectState::Deleted;
        (void)object;
    }

    std::map<std::string, ObjectVersion> snapshot() const {
        std::map<std::string, ObjectVersion> result;
        for (const auto& [key, history] : objects_) {
            if (!history.empty() && history.back().state == ObjectState::Active) {
                result.emplace(key, history.back());
            }
        }
        return result;
    }

    void restore(const std::map<std::string, ObjectVersion>& backup) {
        std::map<std::string, std::vector<ObjectVersion>> replacement;
        for (const auto& [key, object] : backup) {
            validateKey(key);
            if (object.version < 1 ||
                object.content.size() > maximumBytes_ ||
                checksum(object.content) != object.checksum) {
                throw std::runtime_error("Backup integrity verification failed");
            }
            replacement[key].push_back(object);
        }
        // Build the replacement completely before changing live state.
        objects_.swap(replacement);
    }
};

class LoadBalancer {
private:
    std::map<std::string, ComputeInstance> instances_;

public:
    explicit LoadBalancer(std::vector<ComputeInstance> instances) {
        for (auto& instance : instances) {
            const auto id = instance.id;
            if (!instances_.emplace(id, std::move(instance)).second) {
                throw std::invalid_argument("Duplicate instance ID");
            }
        }
    }

    std::string acquire() {
        ComputeInstance* selected = nullptr;
        for (auto& [id, instance] : instances_) {
            if (instance.state != InstanceState::Running ||
                instance.activeRequests >= instance.capacity) {
                continue;
            }

            if (selected == nullptr ||
                instance.utilization() < selected->utilization() ||
                (instance.utilization() == selected->utilization() &&
                 instance.id < selected->id)) {
                selected = &instance;
            }
        }

        if (selected == nullptr) {
            throw std::runtime_error("No healthy compute capacity available");
        }

        ++selected->activeRequests;
        return selected->id;
    }

    void release(const std::string& id) {
        auto found = instances_.find(id);
        if (found == instances_.end() || found->second.activeRequests <= 0) {
            throw std::invalid_argument("Invalid request release");
        }
        --found->second.activeRequests;
    }

    void setState(const std::string& id, InstanceState state) {
        auto found = instances_.find(id);
        if (found == instances_.end()) {
            throw std::out_of_range("Unknown instance");
        }
        found->second.state = state;
    }

    const std::map<std::string, ComputeInstance>& instances() const {
        return instances_;
    }
};

struct GovernancePolicy {
    std::size_t minimumZones = 2;
    bool requireBackup = true;

    std::vector<std::string> evaluate(
        const LoadBalancer& balancer,
        bool completedBackup
    ) const {
        std::set<std::string> zones;
        std::size_t running = 0;

        for (const auto& [id, instance] : balancer.instances()) {
            if (instance.state == InstanceState::Running) {
                zones.insert(instance.zone);
                ++running;
            }
        }

        std::vector<std::string> errors;
        if (running == 0) errors.push_back("No running compute instances");
        if (zones.size() < minimumZones) {
            errors.push_back("Insufficient availability-zone diversity");
        }
        if (requireBackup && !completedBackup) {
            errors.push_back("No completed backup is available");
        }
        return errors;
    }
};

int main() {
    try {
        ObjectStore storage(4096);
        storage.put("config/service.json", R"({"service":"orders","revision":1})");
        storage.put("reports/daily.txt", "Order processing report");

        const auto backup = storage.snapshot();

        LoadBalancer balancer({
            ComputeInstance("vm-a", "zone-a", 2),
            ComputeInstance("vm-b", "zone-b", 3),
            ComputeInstance("vm-c", "zone-c", 1)
        });

        GovernancePolicy policy;
        auto errors = policy.evaluate(balancer, !backup.empty());

        if (!errors.empty()) {
            for (const auto& error : errors) std::cerr << error << '\n';
            return 1;
        }

        std::cout << "Request routing:\n";
        for (int request = 1; request <= 8; ++request) {
            const std::string instanceId = balancer.acquire();
            std::cout << "request-" << request << " -> " << instanceId << '\n';
            balancer.release(instanceId);
        }

        const auto original = storage.get("config/service.json");
        storage.put("config/service.json", R"({"service":"orders","revision":2})");

        if (storage.get("config/service.json", 1).checksum != original.checksum) {
            throw std::runtime_error("Object version history was corrupted");
        }

        storage.erase("reports/daily.txt");
        try {
            storage.get("reports/daily.txt");
        } catch (const std::out_of_range&) {
            std::cout << "Deleted object is no longer active.\n";
        }

        storage.restore(backup);
        if (storage.get("config/service.json").checksum != original.checksum) {
            throw std::runtime_error("Restored object does not match backup");
        }

        balancer.setState("vm-a", InstanceState::Unhealthy);
        std::cout << "\nCompute health:\n";
        for (const auto& [id, instance] : balancer.instances()) {
            std::cout << id << " zone=" << instance.zone
                      << " state=" << toString(instance.state)
                      << " capacity=" << instance.capacity
                      << " active=" << instance.activeRequests << '\n';
        }

        auto updatedErrors = policy.evaluate(balancer, true);
        std::cout << "\nGovernance result: "
                  << (updatedErrors.empty() ? "eligible" : "ineligible") << '\n';

        try {
            storage.put("../secrets.txt", "sensitive");
        } catch (const std::invalid_argument& error) {
            std::cout << "Unsafe object key rejected: " << error.what() << '\n';
        }

        try {
            LoadBalancer emptyPool({});
            emptyPool.acquire();
        } catch (const std::runtime_error& error) {
            std::cout << "Capacity failure handled: " << error.what() << '\n';
        }

        std::cout << "\nArchitecture simulation completed successfully.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
