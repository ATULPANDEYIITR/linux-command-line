#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

enum class Family {
    GeneralPurpose,
    ComputeOptimized,
    MemoryOptimized,
    Burstable,
    Accelerated
};

enum class State {
    Requested,
    Provisioning,
    Running,
    Stopped,
    Terminated,
    Failed
};

std::string toString(Family family) {
    switch (family) {
        case Family::GeneralPurpose: return "general-purpose";
        case Family::ComputeOptimized: return "compute-optimized";
        case Family::MemoryOptimized: return "memory-optimized";
        case Family::Burstable: return "burstable";
        case Family::Accelerated: return "accelerated";
    }
    throw std::logic_error("Unknown instance family");
}

std::string toString(State state) {
    switch (state) {
        case State::Requested: return "requested";
        case State::Provisioning: return "provisioning";
        case State::Running: return "running";
        case State::Stopped: return "stopped";
        case State::Terminated: return "terminated";
        case State::Failed: return "failed";
    }
    throw std::logic_error("Unknown instance state");
}

struct InstanceType {
    std::string name;
    Family family;
    int vcpus;
    double memoryGiB;
    double hourlyRate;
    double networkGbps;
    std::string architecture = "x86_64";

    void validate() const {
        if (name.empty() || vcpus <= 0 || memoryGiB <= 0 ||
            hourlyRate < 0 || networkGbps <= 0) {
            throw std::invalid_argument("Invalid instance specification");
        }
    }
};

struct ComputeRequest {
    std::string workload;
    int requiredVcpus;
    double requiredMemoryGiB;
    double maximumHourlyRate;
    std::set<std::string> allowedArchitectures;
};

struct Instance {
    std::string id;
    std::string workload;
    InstanceType type;
    State state = State::Requested;
    std::optional<std::string> hostId;
};

class Host {
private:
    std::string id_;
    int totalVcpus_;
    double totalMemoryGiB_;
    std::set<std::string> architectures_;
    int usedVcpus_ = 0;
    double usedMemoryGiB_ = 0;
    std::set<std::string> allocations_;

public:
    Host(std::string id, int vcpus, double memoryGiB,
         std::set<std::string> architectures)
        : id_(std::move(id)),
          totalVcpus_(vcpus),
          totalMemoryGiB_(memoryGiB),
          architectures_(std::move(architectures)) {
        if (id_.empty() || vcpus <= 0 || memoryGiB <= 0) {
            throw std::invalid_argument("Invalid physical host");
        }
    }

    bool canFit(const InstanceType& type) const {
        return architectures_.count(type.architecture) > 0 &&
               totalVcpus_ - usedVcpus_ >= type.vcpus &&
               totalMemoryGiB_ - usedMemoryGiB_ >= type.memoryGiB;
    }

    void reserve(const Instance& instance) {
        if (allocations_.count(instance.id)) {
            throw std::logic_error("Duplicate host allocation");
        }
        if (!canFit(instance.type)) {
            throw std::runtime_error("Insufficient compatible host capacity");
        }

        // Update both resource counters and the allocation registry together.
        allocations_.insert(instance.id);
        usedVcpus_ += instance.type.vcpus;
        usedMemoryGiB_ += instance.type.memoryGiB;
    }

    void release(const Instance& instance) {
        if (allocations_.erase(instance.id) == 0) {
            throw std::logic_error("Allocation was not present on host");
        }
        usedVcpus_ -= instance.type.vcpus;
        usedMemoryGiB_ -= instance.type.memoryGiB;
    }

    const std::string& id() const { return id_; }
    int freeVcpus() const { return totalVcpus_ - usedVcpus_; }
    double freeMemoryGiB() const {
        return totalMemoryGiB_ - usedMemoryGiB_;
    }

    void print() const {
        std::cout << id_ << ": " << freeVcpus() << "/"
                  << totalVcpus_ << " vCPUs free, "
                  << freeMemoryGiB() << "/" << totalMemoryGiB_
                  << " GiB RAM free\n";
    }
};

class GovernanceEngine {
private:
    std::map<std::string, InstanceType> catalog_;
    std::map<std::string, Host> hosts_;
    std::map<std::string, Instance> instances_;
    unsigned long nextId_ = 1;

    Instance& getInstance(const std::string& id) {
        auto it = instances_.find(id);
        if (it == instances_.end()) {
            throw std::runtime_error("Unknown instance: " + id);
        }
        return it->second;
    }

    void transition(Instance& instance, State target) {
        const std::map<State, std::set<State>> allowed = {
            {State::Requested, {State::Provisioning, State::Failed}},
            {State::Provisioning, {State::Running, State::Failed}},
            {State::Running, {State::Stopped, State::Terminated}},
            {State::Stopped, {State::Provisioning, State::Terminated}},
            {State::Failed, {State::Terminated}},
            {State::Terminated, {}}
        };

        if (!allowed.at(instance.state).count(target)) {
            throw std::logic_error(
                "Illegal transition from " + toString(instance.state) +
                " to " + toString(target));
        }
        instance.state = target;
    }

    void releaseHost(Instance& instance) {
        if (!instance.hostId) return;
        hosts_.at(*instance.hostId).release(instance);
        instance.hostId.reset();
    }

public:
    void addType(const InstanceType& type) {
        type.validate();
        if (!catalog_.emplace(type.name, type).second) {
            throw std::invalid_argument("Duplicate type: " + type.name);
        }
    }

    void addHost(Host host) {
        const std::string id = host.id();
        if (!hosts_.emplace(id, std::move(host)).second) {
            throw std::invalid_argument("Duplicate host: " + id);
        }
    }

    const InstanceType& select(const ComputeRequest& request) const {
        if (request.workload.empty() || request.requiredVcpus <= 0 ||
            request.requiredMemoryGiB <= 0 ||
            request.maximumHourlyRate < 0) {
            throw std::invalid_argument("Invalid compute request");
        }

        const InstanceType* best = nullptr;
        for (const auto& entry : catalog_) {
            const auto& type = entry.second;
            if (type.vcpus < request.requiredVcpus ||
                type.memoryGiB < request.requiredMemoryGiB ||
                type.hourlyRate > request.maximumHourlyRate ||
                !request.allowedArchitectures.count(type.architecture)) {
                continue;
            }

            // Cost is the primary objective. Resource excess breaks ties.
            if (!best ||
                type.hourlyRate < best->hourlyRate ||
                (type.hourlyRate == best->hourlyRate &&
                 type.vcpus < best->vcpus)) {
                best = &type;
            }
        }

        if (!best) {
            throw std::runtime_error("No instance type matches the request");
        }
        return *best;
    }

    Instance provision(const std::string& typeName,
                       const std::string& workload) {
        auto typeIt = catalog_.find(typeName);
        if (typeIt == catalog_.end()) {
            throw std::runtime_error("Unknown instance type: " + typeName);
        }
        if (workload.empty()) {
            throw std::invalid_argument("Workload name is required");
        }

        const std::string id = "vm-" + std::to_string(nextId_++);
        Instance instance{id, workload, typeIt->second};
        transition(instance, State::Provisioning);
        instances_.emplace(id, instance);
        Instance& stored = instances_.at(id);

        // Best-fit minimizes leftover memory, then CPU, among compatible hosts.
        std::vector<Host*> candidates;
        for (auto& entry : hosts_) candidates.push_back(&entry.second);
        std::sort(candidates.begin(), candidates.end(),
            [](const Host* a, const Host* b) {
                if (a->freeMemoryGiB() != b->freeMemoryGiB())
                    return a->freeMemoryGiB() < b->freeMemoryGiB();
                return a->freeVcpus() < b->freeVcpus();
            });

        for (Host* host : candidates) {
            if (!host->canFit(stored.type)) continue;
            host->reserve(stored);
            stored.hostId = host->id();
            transition(stored, State::Running);
            return stored;
        }

        transition(stored, State::Failed);
        throw std::runtime_error("No host can fit " + typeName);
    }

    void stop(const std::string& id) {
        Instance& instance = getInstance(id);
        transition(instance, State::Stopped);
        releaseHost(instance);
    }

    void start(const std::string& id) {
        Instance& instance = getInstance(id);
        transition(instance, State::Provisioning);

        for (auto& entry : hosts_) {
            Host& host = entry.second;
            if (!host.canFit(instance.type)) continue;
            host.reserve(instance);
            instance.hostId = host.id();
            transition(instance, State::Running);
            return;
        }

        transition(instance, State::Stopped);
        throw std::runtime_error("Restart failed: capacity exhausted");
    }

    void terminate(const std::string& id) {
        Instance& instance = getInstance(id);
        releaseHost(instance);
        transition(instance, State::Terminated);
    }

    void printInventory() const {
        std::cout << "\nCompute inventory\n"
                  << std::left << std::setw(12) << "ID"
                  << std::setw(22) << "WORKLOAD"
                  << std::setw(20) << "INSTANCE TYPE"
                  << std::setw(13) << "STATE"
                  << std::setw(12) << "HOST" << "\n";

        for (const auto& entry : instances_) {
            const auto& vm = entry.second;
            std::cout << std::left << std::setw(12) << vm.id
                      << std::setw(22) << vm.workload
                      << std::setw(20) << vm.type.name
                      << std::setw(13) << toString(vm.state)
                      << std::setw(12)
                      << vm.hostId.value_or("-") << "\n";
        }
    }

    void printHosts() const {
        std::cout << "\nHost capacity\n";
        for (const auto& entry : hosts_) entry.second.print();
    }
};

int main() {
    try {
        GovernanceEngine cloud;
        cloud.addType({"general-medium", Family::GeneralPurpose,
                       4, 16, 0.16, 10, "x86_64"});
        cloud.addType({"cpu-large", Family::ComputeOptimized,
                       8, 16, 0.24, 15, "x86_64"});
        cloud.addType({"memory-large", Family::MemoryOptimized,
                       4, 32, 0.22, 10, "x86_64"});
        cloud.addType({"arm-burst", Family::Burstable,
                       2, 4, 0.035, 2, "arm64"});

        cloud.addHost(Host("node-a", 16, 64, {"x86_64", "arm64"}));
        cloud.addHost(Host("node-b", 8, 32, {"x86_64"}));

        ComputeRequest request{
            "orders-database", 4, 24, 0.30, {"x86_64"}
        };
        const auto& selected = cloud.select(request);

        std::cout << "Database instance selection: " << selected.name
                  << " at $" << std::fixed << std::setprecision(3)
                  << selected.hourlyRate << "/hour\n";

        Instance database = cloud.provision(
            selected.name, "orders-database");
        Instance analytics = cloud.provision(
            "cpu-large", "nightly-analytics");
        cloud.printInventory();
        cloud.printHosts();

        double eightHourCost = 0.24 * 8 * 3;
        std::cout << "\nThree CPU instances for eight hours: $"
                  << eightHourCost << "\n";

        cloud.stop(analytics.id);
        cloud.start(analytics.id);
        cloud.terminate(analytics.id);
        cloud.terminate(database.id);

        try {
            cloud.provision("nonexistent", "bad-request");
        } catch (const std::exception& error) {
            std::cout << "Expected failure: " << error.what() << "\n";
        }

        cloud.printInventory();
        cloud.printHosts();
    } catch (const std::exception& error) {
        std::cerr << "Compute engine error: " << error.what() << "\n";
        return 1;
    }
    return 0;
}
