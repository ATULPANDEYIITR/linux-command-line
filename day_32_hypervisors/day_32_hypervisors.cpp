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
#include <unordered_map>
#include <vector>

/*
 * Hypervisor Governance and Virtual Machine Management Case Study
 *
 * This C++17 program models a small virtualization control plane for a
 * private infrastructure cluster.
 *
 * Scenario:
 * A platform team operates a physical server and needs to provision several
 * guest workloads. The management engine must decide whether a VM can be
 * created, allocate virtual CPUs and memory, attach virtual storage and
 * networking, enforce lifecycle rules, maintain snapshots, and report
 * resource pressure.
 *
 * The program is deliberately different from a real hypervisor. It models
 * management semantics and resource accounting; it does not execute guest
 * machine instructions or directly control virtualization hardware.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic hypervisor_case_study.cpp -o hypervisor
 */

enum class HypervisorType {
    Type1,
    Type2
};

enum class VMState {
    Created,
    Running,
    Paused,
    Stopped,
    Destroyed
};

enum class NetworkMode {
    NAT,
    Bridged,
    HostOnly
};


std::string toString(HypervisorType type) {
    switch (type) {
        case HypervisorType::Type1:
            return "Type 1 / bare-metal";
        case HypervisorType::Type2:
            return "Type 2 / hosted";
    }

    return "unknown";
}


std::string toString(VMState state) {
    switch (state) {
        case VMState::Created:
            return "created";
        case VMState::Running:
            return "running";
        case VMState::Paused:
            return "paused";
        case VMState::Stopped:
            return "stopped";
        case VMState::Destroyed:
            return "destroyed";
    }

    return "unknown";
}


std::string toString(NetworkMode mode) {
    switch (mode) {
        case NetworkMode::NAT:
            return "NAT";
        case NetworkMode::Bridged:
            return "bridged";
        case NetworkMode::HostOnly:
            return "host-only";
    }

    return "unknown";
}


/* -------------------------------------------------------------------------
 * Resource structures
 * ---------------------------------------------------------------------- */

struct HostResources {
    int cpuCores;
    int memoryMB;
    int storageGB;

    void validate() const {
        if (cpuCores <= 0) {
            throw std::invalid_argument("Host CPU capacity must be positive.");
        }

        if (memoryMB <= 0) {
            throw std::invalid_argument("Host memory must be positive.");
        }

        if (storageGB <= 0) {
            throw std::invalid_argument("Host storage must be positive.");
        }
    }
};


struct VirtualDisk {
    std::string path;
    int capacityGB;
    int usedGB = 0;
    bool thinProvisioned = true;

    void write(int amountGB) {
        if (amountGB < 0) {
            throw std::invalid_argument(
                "Disk write amount cannot be negative."
            );
        }

        if (usedGB + amountGB > capacityGB) {
            throw std::runtime_error(
                "Virtual disk capacity would be exceeded."
            );
        }

        usedGB += amountGB;
    }
};


struct VirtualNIC {
    std::string name;
    std::string macAddress;
    NetworkMode mode;
    bool connected = true;
};


/* -------------------------------------------------------------------------
 * Snapshot representation
 * ---------------------------------------------------------------------- */

struct Snapshot {
    std::string id;
    std::string name;
    VMState state;
    int vcpus;
    int memoryMB;
    std::map<std::string, int> diskUsage;
};


/* -------------------------------------------------------------------------
 * Virtual machine
 * ---------------------------------------------------------------------- */

class VirtualMachine {
private:
    static int nextNumericId;

    std::string id;
    std::string name;
    int vcpus;
    int memoryMB;
    int requestedStorageGB;
    std::string guestOS;
    VMState state = VMState::Created;

    std::vector<VirtualDisk> disks;
    std::vector<VirtualNIC> nics;
    std::map<std::string, Snapshot> snapshots;

    long long cpuTimeMs = 0;

    void requireMutable() const {
        if (state == VMState::Destroyed) {
            throw std::runtime_error(
                "Destroyed VM cannot be modified."
            );
        }
    }

public:
    VirtualMachine(
        std::string vmName,
        int cpuCount,
        int memory,
        int storage,
        std::string os
    )
        : id("vm-" + std::to_string(++nextNumericId)),
          name(std::move(vmName)),
          vcpus(cpuCount),
          memoryMB(memory),
          requestedStorageGB(storage),
          guestOS(std::move(os)) {

        if (vcpus <= 0) {
            throw std::invalid_argument(
                "VM must have at least one vCPU."
            );
        }

        if (memoryMB < 128) {
            throw std::invalid_argument(
                "VM memory must be at least 128 MB."
            );
        }

        if (requestedStorageGB <= 0) {
            throw std::invalid_argument(
                "VM storage must be positive."
            );
        }
    }

    const std::string& getId() const {
        return id;
    }

    const std::string& getName() const {
        return name;
    }

    int getVCPUs() const {
        return vcpus;
    }

    int getMemoryMB() const {
        return memoryMB;
    }

    int getStorageGB() const {
        return requestedStorageGB;
    }

    VMState getState() const {
        return state;
    }

    long long getCPUTimeMs() const {
        return cpuTimeMs;
    }

    void attachDisk(VirtualDisk disk) {
        requireMutable();
        disks.push_back(std::move(disk));
    }

    void attachNIC(VirtualNIC nic) {
        requireMutable();
        nics.push_back(std::move(nic));
    }

    void start() {
        if (
            state == VMState::Created ||
            state == VMState::Stopped ||
            state == VMState::Paused
        ) {
            state = VMState::Running;
            return;
        }

        if (state == VMState::Running) {
            return;
        }

        throw std::runtime_error(
            "Destroyed VM cannot be started."
        );
    }

    void pause() {
        if (state != VMState::Running) {
            throw std::runtime_error(
                "Only a running VM can be paused."
            );
        }

        state = VMState::Paused;
    }

    void resume() {
        if (state != VMState::Paused) {
            throw std::runtime_error(
                "Only a paused VM can be resumed."
            );
        }

        state = VMState::Running;
    }

    void shutdown() {
        if (
            state == VMState::Running ||
            state == VMState::Paused
        ) {
            state = VMState::Stopped;
        }
    }

    void destroy() {
        state = VMState::Destroyed;
    }

    void accountCPUTime(int milliseconds, int physicalSlots) {
        if (state != VMState::Running) {
            return;
        }

        const int executableVCPUs =
            std::min(vcpus, physicalSlots);

        cpuTimeMs +=
            static_cast<long long>(milliseconds) * executableVCPUs;
    }

    void writeToPrimaryDisk(int amountGB) {
        if (disks.empty()) {
            throw std::runtime_error(
                "VM has no attached virtual disk."
            );
        }

        disks.front().write(amountGB);
    }

    Snapshot createSnapshot(std::string snapshotName) {
        requireMutable();

        Snapshot snapshot;
        snapshot.id =
            id + "-snapshot-" +
            std::to_string(snapshots.size() + 1);
        snapshot.name = std::move(snapshotName);
        snapshot.state = state;
        snapshot.vcpus = vcpus;
        snapshot.memoryMB = memoryMB;

        for (const auto& disk : disks) {
            snapshot.diskUsage[disk.path] = disk.usedGB;
        }

        snapshots[snapshot.id] = snapshot;
        return snapshot;
    }

    void restoreSnapshot(const std::string& snapshotId) {
        auto iterator = snapshots.find(snapshotId);

        if (iterator == snapshots.end()) {
            throw std::runtime_error(
                "Snapshot does not exist."
            );
        }

        const Snapshot& snapshot = iterator->second;

        vcpus = snapshot.vcpus;
        memoryMB = snapshot.memoryMB;
        state = snapshot.state;

        for (auto& disk : disks) {
            auto usage = snapshot.diskUsage.find(disk.path);

            if (usage != snapshot.diskUsage.end()) {
                disk.usedGB = usage->second;
            }
        }
    }

    void printStatus() const {
        std::cout
            << std::left
            << std::setw(18) << name
            << std::setw(10) << id
            << std::setw(12) << toString(state)
            << std::setw(8) << vcpus
            << std::setw(10) << memoryMB
            << std::setw(12) << requestedStorageGB
            << guestOS
            << '\n';
    }

    void printNetworking() const {
        for (const auto& nic : nics) {
            std::cout
                << "  NIC " << nic.name
                << " MAC=" << nic.macAddress
                << " mode=" << toString(nic.mode)
                << " connected=" << std::boolalpha
                << nic.connected
                << '\n';
        }
    }
};

int VirtualMachine::nextNumericId = 0;


/* -------------------------------------------------------------------------
 * Hypervisor management engine
 * ---------------------------------------------------------------------- */

class Hypervisor {
private:
    std::string name;
    HypervisorType type;
    HostResources resources;
    bool memoryOvercommit;
    std::unordered_map<std::string, VirtualMachine> vms;

    std::string generateMac(const std::string& seed) const {
        /*
         * This deterministic transformation is only a simulator. Real
         * systems allocate MAC addresses according to platform-specific
         * rules and must prevent collisions within their virtual network.
         */
        std::hash<std::string> hasher;
        std::size_t value = hasher(seed);

        std::ostringstream stream;
        stream << "52:54:00:"
               << std::hex
               << ((value >> 16) & 0xff) << ":"
               << ((value >> 8) & 0xff) << ":"
               << (value & 0xff);

        return stream.str();
    }

    int allocatedCPU() const {
        int total = 0;

        for (const auto& [id, vm] : vms) {
            if (vm.getState() != VMState::Destroyed) {
                total += vm.getVCPUs();
            }
        }

        return total;
    }

    int allocatedMemory() const {
        int total = 0;

        for (const auto& [id, vm] : vms) {
            if (vm.getState() != VMState::Destroyed) {
                total += vm.getMemoryMB();
            }
        }

        return total;
    }

    int allocatedStorage() const {
        int total = 0;

        for (const auto& [id, vm] : vms) {
            if (vm.getState() != VMState::Destroyed) {
                total += vm.getStorageGB();
            }
        }

        return total;
    }

public:
    Hypervisor(
        std::string hypervisorName,
        HypervisorType hypervisorType,
        HostResources hostResources,
        bool allowMemoryOvercommit = false
    )
        : name(std::move(hypervisorName)),
          type(hypervisorType),
          resources(hostResources),
          memoryOvercommit(allowMemoryOvercommit) {

        resources.validate();
    }

    VirtualMachine& createVM(
        const std::string& vmName,
        int vcpus,
        int memoryMB,
        int storageGB,
        const std::string& guestOS
    ) {
        for (const auto& [id, vm] : vms) {
            if (
                vm.getState() != VMState::Destroyed &&
                vm.getName() == vmName
            ) {
                throw std::runtime_error(
                    "A VM with this name already exists."
                );
            }
        }

        if (vcpus <= 0) {
            throw std::invalid_argument(
                "vCPU count must be positive."
            );
        }

        if (memoryMB < 128) {
            throw std::invalid_argument(
                "Memory must be at least 128 MB."
            );
        }

        if (storageGB <= 0) {
            throw std::invalid_argument(
                "Storage must be positive."
            );
        }

        if (allocatedCPU() + vcpus > resources.cpuCores) {
            throw std::runtime_error(
                "Insufficient physical CPU capacity."
            );
        }

        if (
            !memoryOvercommit &&
            allocatedMemory() + memoryMB > resources.memoryMB
        ) {
            throw std::runtime_error(
                "Insufficient physical memory capacity."
            );
        }

        if (
            allocatedStorage() + storageGB >
            resources.storageGB
        ) {
            throw std::runtime_error(
                "Insufficient storage capacity."
            );
        }

        VirtualMachine vm(
            vmName,
            vcpus,
            memoryMB,
            storageGB,
            guestOS
        );

        vm.attachDisk({
            "/virtual-disks/" + vmName + ".qcow2",
            storageGB,
            0,
            true
        });

        vm.attachNIC({
            vmName + "-nic0",
            generateMac(vmName),
            NetworkMode::NAT,
            true
        });

        const std::string id = vm.getId();

        auto result = vms.emplace(
            id,
            std::move(vm)
        );

        return result.first->second;
    }

    VirtualMachine& getVM(const std::string& id) {
        auto iterator = vms.find(id);

        if (iterator == vms.end()) {
            throw std::runtime_error(
                "Unknown VM identifier."
            );
        }

        return iterator->second;
    }

    void scheduleCPU(int quantumMs) {
        if (quantumMs <= 0) {
            throw std::invalid_argument(
                "CPU scheduling quantum must be positive."
            );
        }

        for (auto& [id, vm] : vms) {
            vm.accountCPUTime(
                quantumMs,
                resources.cpuCores
            );
        }
    }

    double memoryPressure() const {
        return static_cast<double>(allocatedMemory()) /
               resources.memoryMB;
    }

    void printSummary() const {
        std::cout
            << "\nHypervisor: " << name
            << "\nArchitecture: " << toString(type)
            << "\nPhysical CPU cores: " << resources.cpuCores
            << "\nAllocated vCPUs: " << allocatedCPU()
            << "\nPhysical memory: " << resources.memoryMB << " MB"
            << "\nAllocated memory: " << allocatedMemory() << " MB"
            << "\nPhysical storage: " << resources.storageGB << " GB"
            << "\nAllocated storage: " << allocatedStorage() << " GB"
            << "\nMemory pressure: "
            << std::fixed
            << std::setprecision(2)
            << memoryPressure() * 100.0
            << "%\n";
    }

    void printVMTable() const {
        std::cout
            << "\n"
            << std::left
            << std::setw(18) << "Name"
            << std::setw(10) << "ID"
            << std::setw(12) << "State"
            << std::setw(8) << "vCPU"
            << std::setw(10) << "Memory"
            << std::setw(12) << "Storage"
            << "Guest OS"
            << '\n';

        std::cout << std::string(90, '-') << '\n';

        for (const auto& [id, vm] : vms) {
            if (vm.getState() != VMState::Destroyed) {
                vm.printStatus();
            }
        }
    }
};


/* -------------------------------------------------------------------------
 * Case study workflow
 * ---------------------------------------------------------------------- */

void printSection(const std::string& title) {
    std::cout
        << "\n"
        << std::string(72, '=')
        << "\n"
        << title
        << "\n"
        << std::string(72, '=')
        << "\n";
}


int main() {
    try {
        printSection("Virtualization Infrastructure Case Study");

        /*
         * The physical server exposes 16 CPU cores, 32 GB of RAM, and
         * 1 TB of storage. The hypervisor is Type 1, so the virtualization
         * layer is modeled as running directly on the physical host.
         */
        Hypervisor cluster(
            "Compute-01",
            HypervisorType::Type1,
            {16, 32768, 1000}
        );

        cluster.printSummary();

        printSection("Provision Production Workloads");

        auto& web = cluster.createVM(
            "web-frontend",
            2,
            4096,
            40,
            "Linux"
        );

        auto& database = cluster.createVM(
            "database-primary",
            4,
            8192,
            120,
            "Linux"
        );

        auto& monitoring = cluster.createVM(
            "monitoring",
            2,
            2048,
            30,
            "Linux"
        );

        web.start();
        database.start();
        monitoring.start();

        cluster.printVMTable();

        printSection("Virtual Networking");

        web.printNetworking();
        database.printNetworking();

        printSection("Guest Storage Activity");

        web.writeToPrimaryDisk(5);
        database.writeToPrimaryDisk(30);

        std::cout
            << "The web workload consumed 5 GB of its virtual disk.\n"
            << "The database workload consumed 30 GB of its virtual disk.\n"
            << "The virtual disk capacity remains independent of the guest "
               "operating system's logical filesystem view.\n";

        printSection("CPU Scheduling");

        /*
         * The scheduler accounts for simulated execution time. Real
         * hypervisors schedule vCPUs onto physical CPUs and may account for
         * priorities, affinity, NUMA topology, interrupt activity, and
         * virtualization overhead.
         */
        for (int cycle = 0; cycle < 10; ++cycle) {
            cluster.scheduleCPU(10);
        }

        std::cout
            << "Web CPU time: "
            << web.getCPUTimeMs()
            << " ms\n";

        std::cout
            << "Database CPU time: "
            << database.getCPUTimeMs()
            << " ms\n";

        printSection("Snapshot Before Maintenance");

        Snapshot snapshot =
            database.createSnapshot("pre-maintenance");

        std::cout
            << "Created snapshot "
            << snapshot.id
            << " for "
            << database.getName()
            << ".\n";

        database.pause();

        std::cout
            << "Database state during maintenance preparation: "
            << toString(database.getState())
            << '\n';

        database.resume();

        printSection("Failure Handling");

        try {
            cluster.createVM(
                "oversized-workload",
                20,
                65536,
                50,
                "Linux"
            );
        } catch (const std::exception& error) {
            std::cout
                << "Provisioning rejected: "
                << error.what()
                << '\n';
        }

        try {
            web.writeToPrimaryDisk(100);
        } catch (const std::exception& error) {
            std::cout
                << "Storage operation rejected: "
                << error.what()
                << '\n';
        }

        printSection("Restore After Maintenance Test");

        database.shutdown();

        std::cout
            << "Database after shutdown: "
            << toString(database.getState())
            << '\n';

        database.restoreSnapshot(snapshot.id);

        std::cout
            << "Database after snapshot restoration: "
            << toString(database.getState())
            << '\n';

        printSection("Resource Accounting");

        cluster.printSummary();
        cluster.printVMTable();

        printSection("Type 1 and Type 2 Architectural Distinction");

        std::cout
            << "Type 1 architecture:\n"
            << "  Physical hardware\n"
            << "       |\n"
            << "   Hypervisor\n"
            << "       |\n"
            << "   Guest VMs\n\n"
            << "Type 2 architecture:\n"
            << "  Physical hardware\n"
            << "       |\n"
            << "    Host OS\n"
            << "       |\n"
            << "   Hypervisor application\n"
            << "       |\n"
            << "   Guest VMs\n";

        printSection("Case Study Governance Notes");

        std::cout
            << "A production virtualization platform must protect the "
               "management plane, isolate guests, validate resource "
               "allocations, control privileged device operations, protect "
               "virtual storage, monitor host pressure, and maintain the "
               "hypervisor itself. VM isolation is a security boundary, not "
               "merely a software convenience.\n";

        printSection("Completed");

        std::cout
            << "The simulated infrastructure successfully modeled VM "
               "provisioning, lifecycle control, virtual networking, storage, "
               "snapshots, CPU scheduling, capacity validation, and failure "
               "handling.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal management error: "
            << error.what()
            << '\n';

        return 1;
    }
}
