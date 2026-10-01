/*
 * Introduction to Virtualization
 *
 * C++17 case study:
 * A repository-style virtualization governance engine for a small private
 * cloud. The engine evaluates whether virtual machines can be placed on a
 * physical host, tracks lifecycle state, accounts for allocated resources,
 * estimates current consumption, and determines whether CPU overcommit is
 * acceptable.
 *
 * Build:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic virtualization.cpp -o virtualization
 *
 * Run:
 *   ./virtualization
 */

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

struct Resources {
    double cpuCores{};
    double memoryGiB{};
    double storageGiB{};
    double networkGbps{};

    Resources operator+(const Resources& other) const {
        return {
            cpuCores + other.cpuCores,
            memoryGiB + other.memoryGiB,
            storageGiB + other.storageGiB,
            networkGbps + other.networkGbps
        };
    }
};

static bool exceeds(const Resources& used, const Resources& capacity) {
    return used.cpuCores > capacity.cpuCores ||
           used.memoryGiB > capacity.memoryGiB ||
           used.storageGiB > capacity.storageGiB ||
           used.networkGbps > capacity.networkGbps;
}

static void printResources(const Resources& resources) {
    std::cout << std::fixed << std::setprecision(1)
              << "CPU=" << resources.cpuCores << " cores, "
              << "RAM=" << resources.memoryGiB << " GiB, "
              << "Storage=" << resources.storageGiB << " GiB, "
              << "Network=" << resources.networkGbps << " Gbps";
}

enum class VMState {
    Stopped,
    Running,
    Paused
};

static std::string stateName(VMState state) {
    switch (state) {
        case VMState::Stopped:
            return "stopped";
        case VMState::Running:
            return "running";
        case VMState::Paused:
            return "paused";
    }

    return "unknown";
}

struct VirtualMachine {
    std::string name;
    std::string operatingSystem;
    Resources allocation;
    VMState state{VMState::Stopped};

    // Workload utilization is separated from configured virtual capacity.
    double cpuUtilization{};
    double memoryUtilization{};
    double storageUtilization{};
    double networkUtilization{};

    Resources currentUsage() const {
        if (state != VMState::Running) {
            return {};
        }

        return {
            allocation.cpuCores * cpuUtilization / 100.0,
            allocation.memoryGiB * memoryUtilization / 100.0,
            allocation.storageGiB * storageUtilization / 100.0,
            allocation.networkGbps * networkUtilization / 100.0
        };
    }

    void start() {
        if (state == VMState::Running) {
            throw std::logic_error("VM is already running.");
        }

        state = VMState::Running;
    }

    void stop() {
        if (state == VMState::Stopped) {
            throw std::logic_error("VM is already stopped.");
        }

        state = VMState::Stopped;
    }

    void pause() {
        if (state != VMState::Running) {
            throw std::logic_error("Only a running VM can be paused.");
        }

        state = VMState::Paused;
    }

    void resume() {
        if (state != VMState::Paused) {
            throw std::logic_error("Only a paused VM can be resumed.");
        }

        state = VMState::Running;
    }
};

class PhysicalHost {
private:
    std::string name_;
    Resources capacity_;

public:
    PhysicalHost(std::string name, Resources capacity)
        : name_(std::move(name)), capacity_(capacity) {
        if (capacity_.cpuCores <= 0 ||
            capacity_.memoryGiB <= 0 ||
            capacity_.storageGiB <= 0 ||
            capacity_.networkGbps <= 0) {
            throw std::invalid_argument(
                "Physical host capacity must be positive."
            );
        }
    }

    const std::string& name() const {
        return name_;
    }

    const Resources& capacity() const {
        return capacity_;
    }
};

class VirtualizationCluster {
private:
    struct HostRecord {
        PhysicalHost host;
        std::map<std::string, VirtualMachine> virtualMachines;
        bool allowCpuOvercommit{true};

        HostRecord(PhysicalHost physicalHost, bool overcommit)
            : host(std::move(physicalHost)),
              allowCpuOvercommit(overcommit) {}
    };

    std::map<std::string, HostRecord> hosts_;

    static void validateRequest(const Resources& request) {
        if (request.cpuCores <= 0 ||
            request.memoryGiB <= 0 ||
            request.storageGiB <= 0 ||
            request.networkGbps <= 0) {
            throw std::invalid_argument(
                "VM resource allocations must be positive."
            );
        }
    }

    static Resources allocatedResources(const HostRecord& record) {
        Resources total{};

        for (const auto& [name, vm] : record.virtualMachines) {
            (void)name;
            total = total + vm.allocation;
        }

        return total;
    }

    static Resources activeUsage(const HostRecord& record) {
        Resources total{};

        for (const auto& [name, vm] : record.virtualMachines) {
            (void)name;
            total = total + vm.currentUsage();
        }

        return total;
    }

public:
    void addHost(
        const std::string& hostName,
        Resources capacity,
        bool allowCpuOvercommit
    ) {
        if (hosts_.contains(hostName)) {
            throw std::invalid_argument("Host already exists.");
        }

        hosts_.emplace(
            std::piecewise_construct,
            std::forward_as_tuple(hostName),
            std::forward_as_tuple(
                PhysicalHost(hostName, capacity),
                allowCpuOvercommit
            )
        );
    }

    VirtualMachine& createVM(
        const std::string& hostName,
        const std::string& vmName,
        const std::string& operatingSystem,
        Resources request
    ) {
        auto hostIt = hosts_.find(hostName);

        if (hostIt == hosts_.end()) {
            throw std::invalid_argument("Unknown physical host.");
        }

        auto& record = hostIt->second;

        if (record.virtualMachines.contains(vmName)) {
            throw std::invalid_argument("VM already exists.");
        }

        validateRequest(request);

        const Resources allocated = allocatedResources(record);
        const Resources projected = allocated + request;
        const Resources capacity = record.host.capacity();

        // CPU can be overcommitted in this policy because a scheduler can
        // multiplex virtual CPU demand over physical execution units.
        if (!record.allowCpuOvercommit &&
            projected.cpuCores > capacity.cpuCores) {
            throw std::runtime_error(
                "CPU allocation exceeds physical host capacity."
            );
        }

        // Memory, storage, and network remain hard capacity constraints in
        // this case study. Real platforms may implement additional policies.
        if (projected.memoryGiB > capacity.memoryGiB) {
            throw std::runtime_error(
                "Memory allocation exceeds physical host capacity."
            );
        }

        if (projected.storageGiB > capacity.storageGiB) {
            throw std::runtime_error(
                "Storage allocation exceeds physical host capacity."
            );
        }

        if (projected.networkGbps > capacity.networkGbps) {
            throw std::runtime_error(
                "Network allocation exceeds physical host capacity."
            );
        }

        auto [iterator, inserted] = record.virtualMachines.emplace(
            vmName,
            VirtualMachine{
                vmName,
                operatingSystem,
                request
            }
        );

        if (!inserted) {
            throw std::runtime_error("Failed to create VM.");
        }

        return iterator->second;
    }

    void printHostReport(const std::string& hostName) const {
        auto hostIt = hosts_.find(hostName);

        if (hostIt == hosts_.end()) {
            throw std::invalid_argument("Unknown physical host.");
        }

        const auto& record = hostIt->second;
        const Resources allocated = allocatedResources(record);
        const Resources usage = activeUsage(record);
        const Resources capacity = record.host.capacity();

        std::cout << "\nHost: " << record.host.name() << '\n';

        std::cout << "Physical capacity: ";
        printResources(capacity);
        std::cout << '\n';

        std::cout << "Virtual allocation: ";
        printResources(allocated);
        std::cout << '\n';

        std::cout << "Current workload use: ";
        printResources(usage);
        std::cout << '\n';

        std::cout << "CPU overcommit: "
                  << (record.allowCpuOvercommit ? "enabled" : "disabled")
                  << '\n';

        std::cout << "Virtual machines:\n";

        for (const auto& [name, vm] : record.virtualMachines) {
            std::cout << "  " << name
                      << " [" << vm.operatingSystem << "] "
                      << stateName(vm.state)
                      << " | ";
            printResources(vm.allocation);
            std::cout << '\n';
        }
    }

    bool memorySafe(const std::string& hostName) const {
        auto hostIt = hosts_.find(hostName);

        if (hostIt == hosts_.end()) {
            return false;
        }

        const auto& record = hostIt->second;
        const Resources allocated = allocatedResources(record);

        return allocated.memoryGiB <= record.host.capacity().memoryGiB;
    }
};

// ---------------------------------------------------------------------------
// CPU scheduler
// ---------------------------------------------------------------------------

class ProportionalCpuScheduler {
private:
    double physicalCores_;

public:
    explicit ProportionalCpuScheduler(double physicalCores)
        : physicalCores_(physicalCores) {
        if (physicalCores_ <= 0) {
            throw std::invalid_argument("Physical CPU capacity must be positive.");
        }
    }

    std::map<std::string, double> schedule(
        const std::map<std::string, double>& demand
    ) const {
        double totalDemand = 0;

        for (const auto& [name, requested] : demand) {
            (void)name;
            totalDemand += std::max(0.0, requested);
        }

        std::map<std::string, double> result;

        if (totalDemand == 0) {
            for (const auto& [name, requested] : demand) {
                (void)requested;
                result[name] = 0;
            }
            return result;
        }

        const double factor =
            totalDemand <= physicalCores_
                ? 1.0
                : physicalCores_ / totalDemand;

        for (const auto& [name, requested] : demand) {
            result[name] = std::max(0.0, requested) * factor;
        }

        return result;
    }
};

// ---------------------------------------------------------------------------
// Case study
// ---------------------------------------------------------------------------

void runPrivateCloudCaseStudy() {
    std::cout << "INTRODUCTION TO VIRTUALIZATION\n";
    std::cout << "Private-cloud host placement and VM resource governance\n";

    VirtualizationCluster cluster;

    cluster.addHost(
        "compute-01",
        Resources{
            16,
            64,
            1200,
            10
        },
        true
    );

    auto& web = cluster.createVM(
        "compute-01",
        "web-production",
        "Linux",
        Resources{4, 12, 120, 2}
    );

    auto& database = cluster.createVM(
        "compute-01",
        "database-production",
        "Linux",
        Resources{8, 32, 400, 4}
    );

    auto& analytics = cluster.createVM(
        "compute-01",
        "analytics",
        "Linux",
        Resources{8, 12, 250, 3}
    );

    web.start();
    database.start();
    analytics.start();

    web.cpuUtilization = 30;
    web.memoryUtilization = 50;
    web.storageUtilization = 20;
    web.networkUtilization = 15;

    database.cpuUtilization = 75;
    database.memoryUtilization = 80;
    database.storageUtilization = 65;
    database.networkUtilization = 50;

    analytics.cpuUtilization = 20;
    analytics.memoryUtilization = 40;
    analytics.storageUtilization = 30;
    analytics.networkUtilization = 10;

    cluster.printHostReport("compute-01");

    std::cout << "\nMemory capacity check: "
              << (cluster.memorySafe("compute-01") ? "PASS" : "FAIL")
              << '\n';

    std::cout << "\nCPU allocation is intentionally overcommitted:\n";
    std::cout << "  Physical CPU: 16 cores\n";
    std::cout << "  Virtual CPU:  20 cores\n";
    std::cout << "  Policy:       scheduler-based sharing\n";

    ProportionalCpuScheduler scheduler(16);

    std::map<std::string, double> cpuDemand{
        {"web-production", 2.0},
        {"database-production", 7.0},
        {"analytics", 6.0}
    };

    const auto scheduled = scheduler.schedule(cpuDemand);

    std::cout << "\nIllustrative CPU scheduler result:\n";

    for (const auto& [vmName, cores] : scheduled) {
        std::cout << "  " << std::setw(20)
                  << std::left << vmName
                  << std::fixed << std::setprecision(2)
                  << cores << " physical-core equivalent\n";
    }
}

void runFailureScenarios() {
    std::cout << "\n\nFAILURE AND VALIDATION SCENARIOS\n";

    VirtualizationCluster cluster;

    cluster.addHost(
        "small-host",
        Resources{8, 16, 500, 2},
        false
    );

    const std::vector<std::pair<std::string, Resources>> requests{
        {"memory-heavy", Resources{2, 32, 50, 0.5}},
        {"storage-heavy", Resources{2, 4, 700, 0.5}},
        {"network-heavy", Resources{2, 4, 50, 5}},
        {"valid-vm", Resources{2, 4, 50, 0.5}}
    };

    for (const auto& [name, resources] : requests) {
        try {
            cluster.createVM(
                "small-host",
                name,
                "Linux",
                resources
            );

            std::cout << name << ": accepted\n";
        } catch (const std::exception& error) {
            std::cout << name << ": rejected\n";
            std::cout << "  Reason: " << error.what() << '\n';
        }
    }
}

void runLifecycleCase() {
    std::cout << "\n\nVM LIFECYCLE CASE\n";

    VirtualizationCluster cluster;

    cluster.addHost(
        "lifecycle-host",
        Resources{8, 32, 500, 5},
        false
    );

    auto& vm = cluster.createVM(
        "lifecycle-host",
        "application",
        "Linux",
        Resources{2, 8, 100, 1}
    );

    std::cout << "Initial state: " << stateName(vm.state) << '\n';

    vm.start();
    std::cout << "After start:   " << stateName(vm.state) << '\n';

    vm.pause();
    std::cout << "After pause:   " << stateName(vm.state) << '\n';

    vm.resume();
    std::cout << "After resume:  " << stateName(vm.state) << '\n';

    vm.stop();
    std::cout << "After stop:    " << stateName(vm.state) << '\n';

    try {
        vm.resume();
    } catch (const std::exception& error) {
        std::cout << "Expected lifecycle error: "
                  << error.what() << '\n';
    }
}

void explainArchitecture() {
    std::cout << "\n\nARCHITECTURAL MODEL\n";

    std::cout
        << "Physical hardware\n"
        << "        |\n"
        << "        v\n"
        << "Hypervisor / virtualization layer\n"
        << "        |\n"
        << "  +-----+-----+-----+\n"
        << "  |           |     |\n"
        << "  v           v     v\n"
        << " VM Web    VM DB   VM Analytics\n\n";

    std::cout
        << "The host owns the physical CPU, memory, storage, and network devices. "
        << "The hypervisor presents virtual hardware to each guest. The guest "
        << "operating system therefore interacts with an abstracted machine "
        << "rather than directly controlling the complete physical server.\n";
}

int main() {
    try {
        runPrivateCloudCaseStudy();
        runFailureScenarios();
        runLifecycleCase();
        explainArchitecture();

        std::cout
            << "\n\nPRODUCTION TRADE-OFFS\n"
            << "Virtualization improves consolidation and hardware utilization, "
            << "but the physical host remains a finite failure and performance "
            << "domain. Production capacity planning must account for peak CPU "
            << "demand, memory pressure, storage I/O, network throughput, "
            << "redundancy, backups, host failure, and security of the "
            << "hypervisor management plane.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}
