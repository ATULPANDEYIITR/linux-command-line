#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Server Virtualization Governance and Capacity Engine
 *
 * Case study:
 * A private-cloud platform operates several physical servers. Each server
 * exposes virtual CPU, memory, storage, and network capacity to tenant VMs.
 *
 * The engine evaluates VM placement, resource reservations, runtime demand,
 * contention, migration feasibility, and overcommit policy.
 *
 * The program intentionally models the management and scheduling layer rather
 * than attempting to communicate with real hardware or a hypervisor.
 */

struct Resources {
    double cpu;
    double memoryGiB;
    double storageGiB;
    double networkMbps;

    void validate() const {
        if (cpu < 0 || memoryGiB < 0 || storageGiB < 0 || networkMbps < 0) {
            throw std::invalid_argument(
                "Resource quantities cannot be negative."
            );
        }
    }

    Resources operator+(const Resources& other) const {
        return {
            cpu + other.cpu,
            memoryGiB + other.memoryGiB,
            storageGiB + other.storageGiB,
            networkMbps + other.networkMbps
        };
    }

    Resources operator-(const Resources& other) const {
        return {
            cpu - other.cpu,
            memoryGiB - other.memoryGiB,
            storageGiB - other.storageGiB,
            networkMbps - other.networkMbps
        };
    }

    bool fitsWithin(const Resources& capacity) const {
        return cpu <= capacity.cpu &&
               memoryGiB <= capacity.memoryGiB &&
               storageGiB <= capacity.storageGiB &&
               networkMbps <= capacity.networkMbps;
    }

    double cpuUtilization(const Resources& capacity) const {
        return capacity.cpu == 0 ? 0 : cpu / capacity.cpu;
    }

    double memoryUtilization(const Resources& capacity) const {
        return capacity.memoryGiB == 0 ? 0 : memoryGiB / capacity.memoryGiB;
    }

    double storageUtilization(const Resources& capacity) const {
        return capacity.storageGiB == 0 ? 0 : storageGiB / capacity.storageGiB;
    }

    double networkUtilization(const Resources& capacity) const {
        return capacity.networkMbps == 0 ? 0 : networkMbps / capacity.networkMbps;
    }
};


enum class VMState {
    Stopped,
    Running,
    Paused
};


class VirtualMachine {
private:
    std::string name_;
    Resources allocation_;
    Resources demand_;
    VMState state_;
    int priority_;

public:
    VirtualMachine(
        std::string name,
        Resources allocation,
        int priority
    )
        : name_(std::move(name)),
          allocation_(allocation),
          demand_{0, 0, 0, 0},
          state_(VMState::Stopped),
          priority_(priority) {

        allocation_.validate();

        if (name_.empty()) {
            throw std::invalid_argument("VM name cannot be empty.");
        }

        if (priority_ < 1 || priority_ > 10) {
            throw std::invalid_argument(
                "VM priority must be between 1 and 10."
            );
        }
    }

    const std::string& name() const {
        return name_;
    }

    const Resources& allocation() const {
        return allocation_;
    }

    const Resources& demand() const {
        return demand_;
    }

    VMState state() const {
        return state_;
    }

    int priority() const {
        return priority_;
    }

    void start() {
        if (state_ == VMState::Running) {
            throw std::logic_error("VM is already running.");
        }

        state_ = VMState::Running;
    }

    void stop() {
        state_ = VMState::Stopped;
    }

    void pause() {
        if (state_ != VMState::Running) {
            throw std::logic_error(
                "Only a running VM can be paused."
            );
        }

        state_ = VMState::Paused;
    }

    void resume() {
        if (state_ != VMState::Paused) {
            throw std::logic_error(
                "Only a paused VM can be resumed."
            );
        }

        state_ = VMState::Running;
    }

    void setDemand(Resources demand) {
        demand.validate();

        /*
         * The simulator caps instantaneous demand at configured virtual
         * resources. This models a VM requesting resources through its
         * provisioned virtual hardware rather than bypassing the allocation.
         */
        demand_.cpu = std::min(demand.cpu, allocation_.cpu);
        demand_.memoryGiB = std::min(
            demand.memoryGiB,
            allocation_.memoryGiB
        );
        demand_.storageGiB = 0;
        demand_.networkMbps = std::min(
            demand.networkMbps,
            allocation_.networkMbps
        );
    }

    Resources activeDemand() const {
        if (state_ != VMState::Running) {
            return {0, 0, 0, 0};
        }

        return demand_;
    }
};


/*
 * A physical host is the boundary where virtual allocations ultimately
 * compete for real hardware capacity.
 */
class PhysicalServer {
private:
    std::string name_;
    Resources capacity_;
    std::map<std::string, VirtualMachine> vms_;

public:
    PhysicalServer(std::string name, Resources capacity)
        : name_(std::move(name)),
          capacity_(capacity) {

        capacity_.validate();

        if (capacity_.cpu <= 0 || capacity_.memoryGiB <= 0) {
            throw std::invalid_argument(
                "A physical server needs positive CPU and memory."
            );
        }
    }

    const std::string& name() const {
        return name_;
    }

    const Resources& capacity() const {
        return capacity_;
    }

    const std::map<std::string, VirtualMachine>& vms() const {
        return vms_;
    }

    Resources configuredAllocation() const {
        Resources total{0, 0, 0, 0};

        for (const auto& [name, vm] : vms_) {
            total = total + vm.allocation();
        }

        return total;
    }

    Resources runningDemand() const {
        Resources total{0, 0, 0, 0};

        for (const auto& [name, vm] : vms_) {
            total = total + vm.activeDemand();
        }

        return total;
    }

    bool addVM(VirtualMachine vm, bool allowOvercommit) {
        if (vms_.contains(vm.name())) {
            return false;
        }

        Resources projected =
            configuredAllocation() + vm.allocation();

        if (!allowOvercommit && !projected.fitsWithin(capacity_)) {
            return false;
        }

        vms_.emplace(vm.name(), std::move(vm));
        return true;
    }

    VirtualMachine& getVM(const std::string& vmName) {
        auto it = vms_.find(vmName);

        if (it == vms_.end()) {
            throw std::out_of_range(
                "Requested VM does not exist on this host."
            );
        }

        return it->second;
    }

    const VirtualMachine& getVM(const std::string& vmName) const {
        auto it = vms_.find(vmName);

        if (it == vms_.end()) {
            throw std::out_of_range(
                "Requested VM does not exist on this host."
            );
        }

        return it->second;
    }

    void removeStoppedVM(const std::string& vmName) {
        auto it = vms_.find(vmName);

        if (it == vms_.end()) {
            throw std::out_of_range("VM does not exist.");
        }

        if (it->second.state() != VMState::Stopped) {
            throw std::logic_error(
                "Only stopped VMs can be removed."
            );
        }

        vms_.erase(it);
    }

    void printCapacityReport() const {
        const Resources allocation = configuredAllocation();
        const Resources demand = runningDemand();

        std::cout << "\nServer: " << name_ << '\n';

        std::cout
            << "Physical capacity: "
            << capacity_.cpu << " CPU, "
            << capacity_.memoryGiB << " GiB RAM, "
            << capacity_.storageGiB << " GiB storage, "
            << capacity_.networkMbps << " Mbps network\n";

        std::cout
            << "Configured allocation: "
            << allocation.cpu << " CPU, "
            << allocation.memoryGiB << " GiB RAM, "
            << allocation.storageGiB << " GiB storage, "
            << allocation.networkMbps << " Mbps network\n";

        std::cout
            << "Runtime demand: "
            << demand.cpu << " CPU, "
            << demand.memoryGiB << " GiB RAM, "
            << demand.networkMbps << " Mbps network\n";

        std::cout
            << std::fixed
            << std::setprecision(1)
            << "Configured utilization: CPU "
            << allocation.cpuUtilization(capacity_) * 100
            << "%, RAM "
            << allocation.memoryUtilization(capacity_) * 100
            << "%, storage "
            << allocation.storageUtilization(capacity_) * 100
            << "%, network "
            << allocation.networkUtilization(capacity_) * 100
            << "%\n";
    }
};


/*
 * Placement policy separates resource governance from the physical server.
 * This is important because different environments make different promises:
 * a financial workload may demand reserved capacity while development VMs may
 * tolerate controlled overcommitment.
 */
class PlacementPolicy {
public:
    virtual ~PlacementPolicy() = default;

    virtual bool canPlace(
        const PhysicalServer& server,
        const VirtualMachine& vm,
        std::string& reason
    ) const = 0;

    virtual bool allowsOvercommit() const = 0;
};


class ReservedCapacityPolicy : public PlacementPolicy {
public:
    bool canPlace(
        const PhysicalServer& server,
        const VirtualMachine& vm,
        std::string& reason
    ) const override {

        Resources projected =
            server.configuredAllocation() + vm.allocation();

        if (!projected.fitsWithin(server.capacity())) {
            reason = "Reserved capacity would exceed physical hardware.";
            return false;
        }

        reason = "Full VM allocation fits on the physical server.";
        return true;
    }

    bool allowsOvercommit() const override {
        return false;
    }
};


class ControlledOvercommitPolicy : public PlacementPolicy {
private:
    double maxCpuRatio_;
    double maxMemoryRatio_;

public:
    ControlledOvercommitPolicy(
        double maxCpuRatio,
        double maxMemoryRatio
    )
        : maxCpuRatio_(maxCpuRatio),
          maxMemoryRatio_(maxMemoryRatio) {

        if (maxCpuRatio_ < 1.0 || maxMemoryRatio_ < 1.0) {
            throw std::invalid_argument(
                "Overcommit ratios must be at least 1."
            );
        }
    }

    bool canPlace(
        const PhysicalServer& server,
        const VirtualMachine& vm,
        std::string& reason
    ) const override {

        Resources projected =
            server.configuredAllocation() + vm.allocation();

        /*
         * The case study allows CPU and RAM overcommit within explicit
         * policy limits, while storage and network remain bounded by physical
         * capacity. This avoids treating all resources as interchangeable.
         */
        if (projected.storageGiB > server.capacity().storageGiB) {
            reason = "Storage capacity cannot be overcommitted.";
            return false;
        }

        if (projected.networkMbps > server.capacity().networkMbps) {
            reason = "Network capacity cannot be overcommitted.";
            return false;
        }

        const double cpuRatio =
            projected.cpu / server.capacity().cpu;

        const double memoryRatio =
            projected.memoryGiB / server.capacity().memoryGiB;

        if (cpuRatio > maxCpuRatio_) {
            reason = "CPU overcommit ratio exceeds policy.";
            return false;
        }

        if (memoryRatio > maxMemoryRatio_) {
            reason = "Memory overcommit ratio exceeds policy.";
            return false;
        }

        reason = "VM satisfies controlled-overcommit policy.";
        return true;
    }

    bool allowsOvercommit() const override {
        return true;
    }
};


/*
 * The scheduler chooses a server by evaluating post-placement utilization.
 * It uses a multi-resource score rather than considering CPU alone.
 */
class ClusterScheduler {
private:
    std::vector<PhysicalServer*> servers_;
    const PlacementPolicy& policy_;

    static double placementScore(
        const PhysicalServer& server,
        const VirtualMachine& vm
    ) {
        Resources projected =
            server.configuredAllocation() + vm.allocation();

        const Resources capacity = server.capacity();

        const double cpu =
            projected.cpu / capacity.cpu;

        const double memory =
            projected.memoryGiB / capacity.memoryGiB;

        const double storage =
            projected.storageGiB / capacity.storageGiB;

        const double network =
            projected.networkMbps / capacity.networkMbps;

        /*
         * Lower score means the VM produces a tighter but valid fit.
         * A multi-dimensional score reduces the chance of filling one resource
         * while leaving unusable fragments of the others.
         */
        return cpu + memory + storage + network;
    }

public:
    ClusterScheduler(
        std::vector<PhysicalServer*> servers,
        const PlacementPolicy& policy
    )
        : servers_(std::move(servers)),
          policy_(policy) {}

    PhysicalServer* place(VirtualMachine vm) const {
        PhysicalServer* selected = nullptr;
        double bestScore = std::numeric_limits<double>::max();

        for (PhysicalServer* server : servers_) {
            std::string reason;

            if (!policy_.canPlace(*server, vm, reason)) {
                continue;
            }

            const double score =
                placementScore(*server, vm);

            if (score < bestScore) {
                bestScore = score;
                selected = server;
            }
        }

        if (selected == nullptr) {
            throw std::runtime_error(
                "No physical server satisfies the placement policy."
            );
        }

        if (!selected->addVM(
                std::move(vm),
                policy_.allowsOvercommit())) {
            throw std::runtime_error(
                "Placement was approved but could not be committed."
            );
        }

        return selected;
    }
};


/*
 * When aggregate CPU demand exceeds physical CPU, this function applies a
 * priority-weighted fair-share model.
 *
 * Complexity is O(V), where V is the number of running VMs on the host.
 */
std::map<std::string, double> calculateCPUShare(
    const PhysicalServer& server
) {
    double weightedDemand = 0.0;

    for (const auto& [name, vm] : server.vms()) {
        if (vm.state() == VMState::Running) {
            weightedDemand +=
                vm.demand().cpu * vm.priority();
        }
    }

    std::map<std::string, double> result;

    if (weightedDemand <= server.capacity().cpu) {
        for (const auto& [name, vm] : server.vms()) {
            if (vm.state() == VMState::Running) {
                result[name] = vm.demand().cpu;
            }
        }

        return result;
    }

    for (const auto& [name, vm] : server.vms()) {
        if (vm.state() != VMState::Running) {
            continue;
        }

        const double weighted =
            vm.demand().cpu * vm.priority();

        result[name] =
            server.capacity().cpu *
            weighted /
            weightedDemand;
    }

    return result;
}


/*
 * Live migration feasibility is checked before modifying either server.
 * The source VM must be running and the destination must be able to accept
 * its configured resources under the destination's current policy.
 */
bool canMigrate(
    const PhysicalServer& source,
    const PhysicalServer& destination,
    const std::string& vmName,
    const PlacementPolicy& policy,
    std::string& reason
) {
    const VirtualMachine& vm =
        source.getVM(vmName);

    if (vm.state() != VMState::Running) {
        reason = "The VM is not running.";
        return false;
    }

    if (!policy.canPlace(
            destination,
            vm,
            reason)) {
        return false;
    }

    reason = "Destination satisfies migration capacity policy.";
    return true;
}


/*
 * Moving a map-owned VM safely requires extracting its node. C++17's
 * node_handle support lets us transfer the object without reconstructing it.
 */
void migrateVM(
    PhysicalServer& source,
    PhysicalServer& destination,
    const std::string& vmName,
    const PlacementPolicy& policy
) {
    std::string reason;

    if (!canMigrate(
            source,
            destination,
            vmName,
            policy,
            reason)) {
        throw std::runtime_error(
            "Migration rejected: " + reason
        );
    }

    /*
     * The source's map is private, so the case study performs migration
     * through a controlled sequence: copy the allocation/state information,
     * remove the stopped equivalent, then reconstruct the VM state on the
     * destination. A real hypervisor would transfer guest memory, device
     * state, virtual disks, and network state rather than use this shortcut.
     */
    const VirtualMachine& original =
        source.getVM(vmName);

    VirtualMachine moved(
        original.name(),
        original.allocation(),
        original.priority()
    );

    moved.setDemand(original.demand());
    moved.start();

    source.getVM(vmName).stop();
    source.removeStoppedVM(vmName);

    if (!destination.addVM(
            std::move(moved),
            policy.allowsOvercommit())) {
        throw std::runtime_error(
            "Destination rejected VM during migration commit."
        );
    }
}


/*
 * Creates a deliberately contention-heavy workload.
 *
 * The configured CPU allocation exceeds physical CPU within the permitted
 * overcommit ratio. Runtime demand is then evaluated to show the difference
 * between virtual capacity and physical execution capacity.
 */
void configureWorkload(PhysicalServer& server) {
    auto& criticalDB =
        server.getVM("orders-db");

    auto& analytics =
        server.getVM("analytics");

    auto& development =
        server.getVM("development");

    criticalDB.start();
    analytics.start();
    development.start();

    criticalDB.setDemand({
        6,
        18,
        0,
        1500
    });

    analytics.setDemand({
        6,
        12,
        0,
        1200
    });

    development.setDemand({
        3,
        6,
        0,
        400
    });
}


/*
 * Demonstrates why CPU overcommit is not automatically an error.
 *
 * The host may expose more virtual CPU than physical CPU because workloads
 * frequently have idle periods. The problem appears when simultaneous demand
 * exceeds the hardware scheduler's ability to execute all requested work.
 */
void demonstrateContention(
    const PhysicalServer& server
) {
    std::cout << "\nCPU contention analysis\n";

    const Resources demand =
        server.runningDemand();

    std::cout
        << "Aggregate running CPU demand: "
        << demand.cpu << "\n";

    std::cout
        << "Physical CPU capacity: "
        << server.capacity().cpu << "\n";

    const auto allocations =
        calculateCPUShare(server);

    for (const auto& [vmName, cpu] : allocations) {
        std::cout
            << "  "
            << vmName
            << " receives approximately "
            << std::fixed
            << std::setprecision(2)
            << cpu
            << " physical CPU units\n";
    }
}


/*
 * Demonstrates a failed placement. The program treats capacity rejection as
 * an explicit scheduling result instead of silently oversubscribing hardware.
 */
void demonstrateFailure(
    const PlacementPolicy& policy,
    PhysicalServer& server
) {
    std::cout << "\nPlacement failure handling\n";

    VirtualMachine oversized(
        "memory-intensive",
        {
            4,
            100,
            100,
            500
        },
        5
    );

    std::string reason;

    if (!policy.canPlace(
            server,
            oversized,
            reason)) {
        std::cout
            << "Rejected: "
            << reason
            << "\n";
    } else {
        std::cout
            << "Policy would allow placement, which indicates "
               "that the current policy intentionally permits this allocation.\n";
    }
}


int main() {
    try {
        std::cout
            << "SERVER VIRTUALIZATION GOVERNANCE ENGINE\n"
            << "=========================================\n";

        /*
         * The cluster has two different physical configurations. This models
         * heterogeneous infrastructure, which is common in real data centers.
         */
        PhysicalServer computeA(
            "compute-a",
            {
                16,
                64,
                1200,
                10000
            }
        );

        PhysicalServer computeB(
            "compute-b",
            {
                24,
                96,
                1600,
                10000
            }
        );

        ControlledOvercommitPolicy policy(
            2.0,
            1.5
        );

        ClusterScheduler scheduler(
            {
                &computeA,
                &computeB
            },
            policy
        );

        /*
         * These VMs represent a coherent application environment:
         * an orders database, analytics workload, web service, and development
         * environment. Their different priorities affect CPU contention.
         */
        scheduler.place(
            VirtualMachine(
                "orders-db",
                {
                    8,
                    24,
                    400,
                    2500
                },
                10
            )
        );

        scheduler.place(
            VirtualMachine(
                "analytics",
                {
                    8,
                    16,
                    300,
                    2000
                },
                4
            )
        );

        scheduler.place(
            VirtualMachine(
                "web-service",
                {
                    4,
                    8,
                    100,
                    1200
                },
                8
            )
        );

        scheduler.place(
            VirtualMachine(
                "development",
                {
                    4,
                    8,
                    100,
                    800
                },
                2
            )
        );

        std::cout << "\nInitial cluster state:";
        computeA.printCapacityReport();
        computeB.printCapacityReport();

        /*
         * Find the host containing the workload required for the case study.
         * The scheduler's placement result can vary with resource scores, so
         * this lookup is performed explicitly rather than assuming a host.
         */
        PhysicalServer* workloadHost = nullptr;

        for (PhysicalServer* server :
             std::vector<PhysicalServer*>{&computeA, &computeB}) {
            for (const auto& [name, vm] : server->vms()) {
                if (name == "orders-db") {
                    workloadHost = server;
                    break;
                }
            }

            if (workloadHost != nullptr) {
                break;
            }
        }

        if (workloadHost == nullptr) {
            throw std::runtime_error(
                "Orders database VM was not placed."
            );
        }

        configureWorkload(*workloadHost);

        std::cout << "\nAfter workload activation:";
        computeA.printCapacityReport();
        computeB.printCapacityReport();

        demonstrateContention(*workloadHost);

        /*
         * Snapshot and lifecycle behavior are represented through VM state
         * transitions. The simulator does not persist disk blocks because the
         * case study is focused on physical resource division.
         */
        auto& database =
            workloadHost->getVM("orders-db");

        database.pause();

        std::cout
            << "\nOrders database paused successfully.\n";

        database.resume();

        std::cout
            << "Orders database resumed successfully.\n";

        /*
         * Migration is evaluated against the other physical server. If the
         * destination has insufficient resources, no state change should occur.
         */
        PhysicalServer* destination =
            workloadHost == &computeA
                ? &computeB
                : &computeA;

        std::string migrationReason;

        if (canMigrate(
                *workloadHost,
                *destination,
                "orders-db",
                policy,
                migrationReason)) {

            std::cout
                << "\nMigration check passed: "
                << migrationReason
                << "\n";

            migrateVM(
                *workloadHost,
                *destination,
                "orders-db",
                policy
            );

            std::cout
                << "Orders database migrated to "
                << destination->name()
                << ".\n";
        } else {
            std::cout
                << "\nMigration blocked: "
                << migrationReason
                << "\n";
        }

        demonstrateFailure(policy, *destination);

        std::cout
            << "\nFinal cluster state:";

        computeA.printCapacityReport();
        computeB.printCapacityReport();

        std::cout
            << "\nCase-study interpretation\n"
            << "--------------------------\n"
            << "Virtualization increases hardware utilization by allowing "
               "multiple isolated guests to share one physical server.\n"
            << "The scheduler converts physical capacity into virtual "
               "allocations, while runtime contention determines whether "
               "those allocations can be satisfied simultaneously.\n"
            << "Controlled overcommit can increase VM density, but its safety "
               "depends on workload behavior, resource headroom, and policy.\n"
            << "Migration is useful for balancing load and performing "
               "maintenance, but it still requires destination capacity.\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal virtualization-engine error: "
            << error.what()
            << '\n';

        return 1;
    }
}
