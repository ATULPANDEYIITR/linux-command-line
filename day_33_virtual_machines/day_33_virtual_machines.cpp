#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
 * Virtualization Governance and Merge-Eligibility-Style Resource Engine
 *
 * Technical case study:
 * A private compute platform operates a cluster of physical hosts. Teams
 * request virtual machines for production workloads. Before a VM can run,
 * the control plane must validate resource capacity, image integrity,
 * storage requirements, network configuration, and lifecycle state.
 *
 * The implementation focuses on a systems-oriented C++ perspective:
 * - RAII-friendly value objects
 * - explicit lifecycle state transitions
 * - resource accounting
 * - virtual CPU scheduling weights
 * - memory reservation and ballooning
 * - virtual disks and snapshots
 * - virtual networking
 * - image validation
 * - host placement
 * - merge-like policy evaluation for VM activation
 * - audit records
 *
 * Compile with:
 *   g++ -std=c++17 -Wall -Wextra -pedantic vm_platform.cpp -o vm_platform
 */

using namespace std;

enum class VMState {
    Defined,
    Starting,
    Running,
    Paused,
    Stopping,
    Stopped,
    Failed
};

enum class NetworkMode {
    NAT,
    Bridged,
    Isolated
};

enum class DiskBus {
    Virtio,
    SCSI,
    SATA
};


string to_string(VMState state) {
    switch (state) {
        case VMState::Defined: return "defined";
        case VMState::Starting: return "starting";
        case VMState::Running: return "running";
        case VMState::Paused: return "paused";
        case VMState::Stopping: return "stopping";
        case VMState::Stopped: return "stopped";
        case VMState::Failed: return "failed";
    }
    return "unknown";
}


string to_string(NetworkMode mode) {
    switch (mode) {
        case NetworkMode::NAT: return "nat";
        case NetworkMode::Bridged: return "bridged";
        case NetworkMode::Isolated: return "isolated";
    }
    return "unknown";
}


string to_string(DiskBus bus) {
    switch (bus) {
        case DiskBus::Virtio: return "virtio";
        case DiskBus::SCSI: return "scsi";
        case DiskBus::SATA: return "sata";
    }
    return "unknown";
}


string currentTime() {
    const auto now = chrono::system_clock::now();
    const auto seconds =
        chrono::time_point_cast<chrono::seconds>(now);

    const auto value = seconds.time_since_epoch().count();

    return to_string(value);
}


struct VMImage {
    string id;
    string name;
    string os;
    string version;
    string architecture;
    int sizeGB;
    string checksum;
    bool trusted;

    void validate() const {
        if (id.empty() || name.empty()) {
            throw invalid_argument("Image requires an ID and name.");
        }
        if (sizeGB <= 0) {
            throw invalid_argument("Image size must be positive.");
        }
        if (checksum.empty()) {
            throw invalid_argument("Image checksum is required.");
        }
    }
};


class ImageCatalog {
private:
    unordered_map<string, VMImage> images;

public:
    void add(const VMImage& image) {
        image.validate();

        if (images.find(image.id) != images.end()) {
            throw runtime_error("Duplicate image: " + image.id);
        }

        images.emplace(image.id, image);
    }

    const VMImage& get(const string& id) const {
        const auto iterator = images.find(id);

        if (iterator == images.end()) {
            throw runtime_error("Unknown image: " + id);
        }

        return iterator->second;
    }

    bool verify(const string& id, const string& checksum) const {
        return get(id).checksum == checksum && get(id).trusted;
    }
};


struct VirtualCPU {
    int vcpus;
    int maxVcpus;
    int shares;
    double utilizationPercent;
    double cpuSeconds;

    void validate() const {
        if (vcpus <= 0) {
            throw invalid_argument("vCPU count must be positive.");
        }
        if (maxVcpus < vcpus) {
            throw invalid_argument("Maximum vCPUs cannot be below current vCPUs.");
        }
        if (shares <= 0) {
            throw invalid_argument("CPU shares must be positive.");
        }
        if (utilizationPercent < 0.0 || utilizationPercent > 100.0) {
            throw invalid_argument("CPU utilization must be 0..100.");
        }
    }
};


struct Memory {
    int allocatedMB;
    int maximumMB;
    bool balloonEnabled;
    double pressurePercent;

    void validate() const {
        if (allocatedMB < 128) {
            throw invalid_argument("VM memory must be at least 128 MB.");
        }
        if (maximumMB < allocatedMB) {
            throw invalid_argument("Maximum memory cannot be below allocation.");
        }
        if (pressurePercent < 0.0 || pressurePercent > 100.0) {
            throw invalid_argument("Memory pressure must be 0..100.");
        }
    }
};


struct VirtualDisk {
    string name;
    int capacityGB;
    double usedGB;
    DiskBus bus;
    bool readOnly;
    int readOperations;
    int writeOperations;

    double freeGB() const {
        return max(0.0, static_cast<double>(capacityGB) - usedGB);
    }

    void write(double amountGB) {
        if (readOnly) {
            throw runtime_error("Disk " + name + " is read-only.");
        }

        if (amountGB < 0) {
            throw invalid_argument("Disk write cannot be negative.");
        }

        if (amountGB > freeGB()) {
            throw runtime_error(
                "Disk " + name + " does not have enough capacity."
            );
        }

        usedGB += amountGB;
        ++writeOperations;
    }

    void read(double amountGB) {
        if (amountGB < 0) {
            throw invalid_argument("Disk read cannot be negative.");
        }

        ++readOperations;

        if (amountGB > usedGB) {
            throw runtime_error(
                "Requested read exceeds logical data currently stored."
            );
        }
    }
};


struct NetworkInterface {
    string name;
    string mac;
    string ip;
    NetworkMode mode;
    bool connected;
    double rxMB;
    double txMB;

    void transmit(double amountMB) {
        if (!connected) {
            throw runtime_error("Network interface is disconnected.");
        }

        if (amountMB < 0) {
            throw invalid_argument("TX traffic cannot be negative.");
        }

        txMB += amountMB;
    }

    void receive(double amountMB) {
        if (!connected) {
            throw runtime_error("Network interface is disconnected.");
        }

        if (amountMB < 0) {
            throw invalid_argument("RX traffic cannot be negative.");
        }

        rxMB += amountMB;
    }
};


struct Snapshot {
    string id;
    string name;
    string createdAt;
    map<string, double> diskUsage;
    double changedGB;
    bool includesMemory;
};


struct Host {
    string name;
    int cpuCores;
    int memoryMB;
    int storageGB;

    int allocatedCPU = 0;
    int allocatedMemoryMB = 0;
    int allocatedStorageGB = 0;

    int freeCPU() const {
        return cpuCores - allocatedCPU;
    }

    int freeMemoryMB() const {
        return memoryMB - allocatedMemoryMB;
    }

    int freeStorageGB() const {
        return storageGB - allocatedStorageGB;
    }
};


struct VM {
    string id;
    string name;
    string imageID;
    VMState state = VMState::Defined;

    VirtualCPU cpu;
    Memory memory;

    map<string, VirtualDisk> disks;
    map<string, NetworkInterface> interfaces;
    map<string, Snapshot> snapshots;

    int bootCount = 0;
    double uptimeSeconds = 0.0;
    string lastError;

    int diskCapacityGB() const {
        int total = 0;

        for (const auto& [name, disk] : disks) {
            total += disk.capacityGB;
        }

        return total;
    }

    double diskUsedGB() const {
        double total = 0.0;

        for (const auto& [name, disk] : disks) {
            total += disk.usedGB;
        }

        return total;
    }

    void validate() const {
        cpu.validate();
        memory.validate();

        if (disks.empty()) {
            throw invalid_argument("VM must have at least one disk.");
        }

        if (interfaces.empty()) {
            throw invalid_argument("VM must have at least one network interface.");
        }
    }
};


struct AuditRecord {
    string timestamp;
    string event;
    string vmID;
    string details;
};


struct PolicyDecision {
    bool allowed;
    vector<string> failures;
};


class ActivationPolicy {
private:
    int maxVCPUs;
    bool requireTrustedImage;

public:
    ActivationPolicy(int maxVCPUs, bool requireTrustedImage)
        : maxVCPUs(maxVCPUs),
          requireTrustedImage(requireTrustedImage) {}

    PolicyDecision evaluate(
        const VM& vm,
        const VMImage& image
    ) const {
        vector<string> failures;

        if (requireTrustedImage && !image.trusted) {
            failures.push_back("VM image is not trusted.");
        }

        if (vm.cpu.vcpus > maxVCPUs) {
            failures.push_back(
                "VM exceeds the platform vCPU policy."
            );
        }

        if (vm.disks.empty()) {
            failures.push_back("VM has no bootable storage.");
        }

        if (vm.interfaces.empty()) {
            failures.push_back("VM has no network interface.");
        }

        return {
            failures.empty(),
            failures
        };
    }
};


class VirtualNetwork {
private:
    string prefix;
    set<int> allocatedHosts;

public:
    explicit VirtualNetwork(string prefix)
        : prefix(std::move(prefix)) {}

    string allocate(const string& vmID) {
        (void)vmID;

        for (int host = 10; host <= 254; ++host) {
            if (allocatedHosts.insert(host).second) {
                return prefix + to_string(host);
            }
        }

        throw runtime_error("No IP addresses remain.");
    }

    void release(const string& ip) {
        if (ip.rfind(prefix, 0) != 0) {
            return;
        }

        const string suffix = ip.substr(prefix.size());

        try {
            allocatedHosts.erase(stoi(suffix));
        } catch (...) {
            // Invalid simulator addresses are ignored during cleanup.
        }
    }
};


class VMPlatform {
private:
    Host host;
    ImageCatalog catalog;
    ActivationPolicy policy;
    VirtualNetwork network;

    unordered_map<string, VM> vms;
    vector<AuditRecord> audit;

    static bool canTransition(VMState from, VMState to) {
        switch (from) {
            case VMState::Defined:
                return to == VMState::Starting;

            case VMState::Stopped:
                return to == VMState::Starting;

            case VMState::Starting:
                return to == VMState::Running ||
                       to == VMState::Failed;

            case VMState::Running:
                return to == VMState::Paused ||
                       to == VMState::Stopping ||
                       to == VMState::Failed;

            case VMState::Paused:
                return to == VMState::Running ||
                       to == VMState::Stopping ||
                       to == VMState::Failed;

            case VMState::Stopping:
                return to == VMState::Stopped ||
                       to == VMState::Failed;

            case VMState::Failed:
                return to == VMState::Starting ||
                       to == VMState::Stopped;
        }

        return false;
    }

    void transition(VM& vm, VMState next) {
        if (!canTransition(vm.state, next)) {
            throw runtime_error(
                "Invalid lifecycle transition for " +
                vm.name + ": " +
                to_string(vm.state) + " -> " +
                to_string(next)
            );
        }

        vm.state = next;
    }

    void log(
        const string& event,
        const string& vmID,
        const string& details
    ) {
        audit.push_back({
            currentTime(),
            event,
            vmID,
            details
        });
    }

    void ensureCapacity(
        int cpu,
        int memoryMB,
        int storageGB
    ) const {
        if (cpu > host.freeCPU()) {
            throw runtime_error("Insufficient host CPU capacity.");
        }

        if (memoryMB > host.freeMemoryMB()) {
            throw runtime_error("Insufficient host memory capacity.");
        }

        if (storageGB > host.freeStorageGB()) {
            throw runtime_error("Insufficient host storage capacity.");
        }
    }

public:
    VMPlatform(
        Host host,
        ImageCatalog catalog,
        ActivationPolicy policy,
        VirtualNetwork network
    )
        : host(std::move(host)),
          catalog(std::move(catalog)),
          policy(std::move(policy)),
          network(std::move(network)) {}

    VM& getVM(const string& id) {
        auto iterator = vms.find(id);

        if (iterator == vms.end()) {
            throw runtime_error("Unknown VM: " + id);
        }

        return iterator->second;
    }

    const VM& getVM(const string& id) const {
        auto iterator = vms.find(id);

        if (iterator == vms.end()) {
            throw runtime_error("Unknown VM: " + id);
        }

        return iterator->second;
    }

    void createVM(
        const string& id,
        const string& name,
        const string& imageID,
        int vcpus,
        int memoryMB,
        int diskGB,
        NetworkMode networkMode
    ) {
        if (vms.find(id) != vms.end()) {
            throw runtime_error("VM already exists: " + id);
        }

        const VMImage& image = catalog.get(imageID);

        if (diskGB < image.sizeGB) {
            throw invalid_argument(
                "Boot disk is smaller than the VM image."
            );
        }

        ensureCapacity(vcpus, memoryMB, diskGB);

        VM vm{
            id,
            name,
            imageID,
            VMState::Defined,
            {
                vcpus,
                vcpus * 2,
                1024,
                0.0,
                0.0
            },
            {
                memoryMB,
                memoryMB * 2,
                true,
                0.0
            },
            {},
            {},
            {},
            0,
            0.0,
            ""
        };

        vm.disks.emplace(
            "boot",
            VirtualDisk{
                "boot",
                diskGB,
                static_cast<double>(image.sizeGB),
                DiskBus::Virtio,
                false,
                0,
                0
            }
        );

        vm.interfaces.emplace(
            "eth0",
            NetworkInterface{
                "eth0",
                "02:00:00:00:" +
                    to_string(vcpus) +
                    ":" +
                    to_string(memoryMB % 100),
                "",
                networkMode,
                true,
                0.0,
                0.0
            }
        );

        vm.validate();

        host.allocatedCPU += vcpus;
        host.allocatedMemoryMB += memoryMB;
        host.allocatedStorageGB += diskGB;

        vms.emplace(id, std::move(vm));

        log(
            "vm-created",
            id,
            "image=" + imageID +
            ",cpu=" + to_string(vcpus) +
            ",memoryMB=" + to_string(memoryMB) +
            ",diskGB=" + to_string(diskGB)
        );
    }

    void start(const string& id) {
        VM& vm = getVM(id);
        const VMImage& image = catalog.get(vm.imageID);

        if (
            vm.state != VMState::Defined &&
            vm.state != VMState::Stopped &&
            vm.state != VMState::Failed
        ) {
            throw runtime_error(
                "VM cannot start from state " +
                to_string(vm.state)
            );
        }

        const PolicyDecision decision =
            policy.evaluate(vm, image);

        if (!decision.allowed) {
            ostringstream message;
            message << "Activation policy rejected VM: ";

            for (size_t i = 0; i < decision.failures.size(); ++i) {
                if (i != 0) {
                    message << "; ";
                }
                message << decision.failures[i];
            }

            throw runtime_error(message.str());
        }

        transition(vm, VMState::Starting);
        log("vm-starting", id, "loading image and virtual devices");

        try {
            NetworkInterface& nic = vm.interfaces.at("eth0");
            nic.ip = network.allocate(id);

            /*
             * A real hypervisor would now create or resume vCPU execution
             * contexts, establish guest memory mappings, initialize virtual
             * storage controllers, and launch firmware or a bootloader.
             */
            ++vm.bootCount;
            vm.lastError.clear();

            transition(vm, VMState::Running);

            log(
                "vm-started",
                id,
                "ip=" + nic.ip +
                ",bootCount=" + to_string(vm.bootCount)
            );
        } catch (const exception& error) {
            vm.lastError = error.what();
            vm.state = VMState::Failed;
            log("vm-start-failed", id, error.what());
            throw;
        }
    }

    void stop(const string& id) {
        VM& vm = getVM(id);

        if (
            vm.state != VMState::Running &&
            vm.state != VMState::Paused
        ) {
            throw runtime_error(
                "Only running or paused VMs can be stopped."
            );
        }

        transition(vm, VMState::Stopping);
        log("vm-stopping", id, "guest shutdown requested");

        NetworkInterface& nic = vm.interfaces.at("eth0");
        network.release(nic.ip);
        nic.ip.clear();

        transition(vm, VMState::Stopped);
        log("vm-stopped", id, "resources remain reserved");
    }

    void pause(const string& id) {
        VM& vm = getVM(id);

        if (vm.state != VMState::Running) {
            throw runtime_error("Only running VMs can be paused.");
        }

        transition(vm, VMState::Paused);
        log("vm-paused", id, "vCPU execution suspended");
    }

    void resume(const string& id) {
        VM& vm = getVM(id);

        if (vm.state != VMState::Paused) {
            throw runtime_error("Only paused VMs can resume.");
        }

        transition(vm, VMState::Running);
        log("vm-resumed", id, "vCPU execution resumed");
    }

    void restart(const string& id) {
        VM& vm = getVM(id);

        if (
            vm.state != VMState::Running &&
            vm.state != VMState::Paused
        ) {
            throw runtime_error(
                "Restart requires a running or paused VM."
            );
        }

        stop(id);
        start(id);
        log("vm-restarted", id, "stop followed by start");
    }

    void resizeMemory(
        const string& id,
        int newMemoryMB
    ) {
        VM& vm = getVM(id);

        if (
            newMemoryMB < 128 ||
            newMemoryMB > vm.memory.maximumMB
        ) {
            throw invalid_argument(
                "Requested memory is outside the VM range."
            );
        }

        const int delta =
            newMemoryMB - vm.memory.allocatedMB;

        if (delta > host.freeMemoryMB()) {
            throw runtime_error(
                "Host cannot satisfy memory resize."
            );
        }

        vm.memory.allocatedMB = newMemoryMB;
        host.allocatedMemoryMB += delta;

        log(
            "memory-resized",
            id,
            "newMemoryMB=" + to_string(newMemoryMB)
        );
    }

    void resizeVCPU(
        const string& id,
        int newVCPUs
    ) {
        VM& vm = getVM(id);

        if (
            newVCPUs < 1 ||
            newVCPUs > vm.cpu.maxVcpus
        ) {
            throw invalid_argument(
                "Requested vCPU count is outside VM limits."
            );
        }

        const int delta =
            newVCPUs - vm.cpu.vcpus;

        if (delta > host.freeCPU()) {
            throw runtime_error(
                "Host cannot satisfy vCPU resize."
            );
        }

        vm.cpu.vcpus = newVCPUs;
        host.allocatedCPU += delta;

        log(
            "cpu-resized",
            id,
            "newVCPUs=" + to_string(newVCPUs)
        );
    }

    void addDisk(
        const string& id,
        const string& diskName,
        int capacityGB,
        DiskBus bus
    ) {
        VM& vm = getVM(id);

        if (vm.disks.find(diskName) != vm.disks.end()) {
            throw runtime_error(
                "Disk already exists: " + diskName
            );
        }

        if (capacityGB <= 0) {
            throw invalid_argument(
                "Disk capacity must be positive."
            );
        }

        ensureCapacity(0, 0, capacityGB);

        vm.disks.emplace(
            diskName,
            VirtualDisk{
                diskName,
                capacityGB,
                0.0,
                bus,
                false,
                0,
                0
            }
        );

        host.allocatedStorageGB += capacityGB;

        log(
            "disk-added",
            id,
            "disk=" + diskName +
            ",capacityGB=" + to_string(capacityGB) +
            ",bus=" + to_string(bus)
        );
    }

    void writeDisk(
        const string& id,
        const string& diskName,
        double amountGB
    ) {
        VM& vm = getVM(id);

        auto iterator = vm.disks.find(diskName);

        if (iterator == vm.disks.end()) {
            throw runtime_error(
                "Unknown disk: " + diskName
            );
        }

        iterator->second.write(amountGB);

        /*
         * Snapshots are modeled as copy-on-write metadata. Once a snapshot
         * exists, later writes may require changed blocks to remain available
         * for snapshot recovery.
         */
        for (auto& [snapshotID, snapshot] : vm.snapshots) {
            snapshot.changedGB += amountGB;
        }

        log(
            "disk-write",
            id,
            "disk=" + diskName +
            ",amountGB=" + to_string(amountGB)
        );
    }

    void readDisk(
        const string& id,
        const string& diskName,
        double amountGB
    ) {
        VM& vm = getVM(id);

        auto iterator = vm.disks.find(diskName);

        if (iterator == vm.disks.end()) {
            throw runtime_error(
                "Unknown disk: " + diskName
            );
        }

        iterator->second.read(amountGB);

        log(
            "disk-read",
            id,
            "disk=" + diskName +
            ",amountGB=" + to_string(amountGB)
        );
    }

    void transmit(
        const string& id,
        const string& interfaceName,
        double amountMB
    ) {
        VM& vm = getVM(id);

        auto iterator = vm.interfaces.find(interfaceName);

        if (iterator == vm.interfaces.end()) {
            throw runtime_error(
                "Unknown network interface."
            );
        }

        iterator->second.transmit(amountMB);

        log(
            "network-tx",
            id,
            "interface=" + interfaceName +
            ",MB=" + to_string(amountMB)
        );
    }

    void receive(
        const string& id,
        const string& interfaceName,
        double amountMB
    ) {
        VM& vm = getVM(id);

        auto iterator = vm.interfaces.find(interfaceName);

        if (iterator == vm.interfaces.end()) {
            throw runtime_error(
                "Unknown network interface."
            );
        }

        iterator->second.receive(amountMB);

        log(
            "network-rx",
            id,
            "interface=" + interfaceName +
            ",MB=" + to_string(amountMB)
        );
    }

    void createSnapshot(
        const string& id,
        const string& snapshotID,
        const string& name,
        bool includeMemory
    ) {
        VM& vm = getVM(id);

        if (vm.snapshots.find(snapshotID) != vm.snapshots.end()) {
            throw runtime_error("Snapshot already exists.");
        }

        if (
            vm.state != VMState::Running &&
            vm.state != VMState::Paused &&
            vm.state != VMState::Stopped
        ) {
            throw runtime_error(
                "VM is not in a snapshot-capable state."
            );
        }

        Snapshot snapshot{
            snapshotID,
            name,
            currentTime(),
            {},
            0.0,
            includeMemory
        };

        for (const auto& [diskName, disk] : vm.disks) {
            snapshot.diskUsage[diskName] = disk.usedGB;
        }

        vm.snapshots.emplace(snapshotID, snapshot);

        log(
            "snapshot-created",
            id,
            "snapshot=" + snapshotID +
            ",includeMemory=" +
            (includeMemory ? "true" : "false")
        );
    }

    void restoreSnapshot(
        const string& id,
        const string& snapshotID
    ) {
        VM& vm = getVM(id);

        auto iterator = vm.snapshots.find(snapshotID);

        if (iterator == vm.snapshots.end()) {
            throw runtime_error("Unknown snapshot.");
        }

        if (
            vm.state == VMState::Running ||
            vm.state == VMState::Paused
        ) {
            throw runtime_error(
                "Stop VM before restoring this disk snapshot."
            );
        }

        for (const auto& [diskName, usedGB] :
             iterator->second.diskUsage) {
            auto diskIterator = vm.disks.find(diskName);

            if (diskIterator != vm.disks.end()) {
                diskIterator->second.usedGB = usedGB;
            }
        }

        log(
            "snapshot-restored",
            id,
            "snapshot=" + snapshotID
        );
    }

    void balloonMemory(
        const string& id,
        int targetMB
    ) {
        VM& vm = getVM(id);

        if (!vm.memory.balloonEnabled) {
            throw runtime_error(
                "Memory ballooning is disabled."
            );
        }

        if (
            targetMB < 128 ||
            targetMB > vm.memory.allocatedMB
        ) {
            throw invalid_argument(
                "Balloon target must be below current allocation."
            );
        }

        const int reclaimed =
            vm.memory.allocatedMB - targetMB;

        vm.memory.allocatedMB = targetMB;
        host.allocatedMemoryMB -= reclaimed;

        log(
            "memory-ballooned",
            id,
            "reclaimedMB=" + to_string(reclaimed)
        );
    }

    void simulateWorkload(
        const string& id,
        double seconds,
        double cpuPercent,
        double memoryPressure,
        double diskWriteGB,
        double txMB,
        double rxMB
    ) {
        VM& vm = getVM(id);

        if (vm.state != VMState::Running) {
            throw runtime_error(
                "Workload requires a running VM."
            );
        }

        if (
            seconds <= 0 ||
            cpuPercent < 0 ||
            cpuPercent > 100 ||
            memoryPressure < 0 ||
            memoryPressure > 100
        ) {
            throw invalid_argument(
                "Invalid workload metrics."
            );
        }

        const double effectiveCPU =
            min(cpuPercent, 100.0);

        vm.cpu.utilizationPercent = effectiveCPU;
        vm.cpu.cpuSeconds +=
            seconds * effectiveCPU / 100.0;

        vm.memory.pressurePercent =
            memoryPressure;

        vm.uptimeSeconds += seconds;

        if (diskWriteGB > 0) {
            writeDisk(id, "boot", diskWriteGB);
        }

        if (txMB > 0) {
            transmit(id, "eth0", txMB);
        }

        if (rxMB > 0) {
            receive(id, "eth0", rxMB);
        }

        log(
            "workload-simulated",
            id,
            "seconds=" + to_string(seconds) +
            ",cpuPercent=" + to_string(cpuPercent) +
            ",memoryPressure=" + to_string(memoryPressure)
        );
    }

    void scheduleCPU(double availableCoreSeconds) const {
        if (availableCoreSeconds <= 0) {
            throw invalid_argument(
                "Available CPU time must be positive."
            );
        }

        int totalShares = 0;

        for (const auto& [id, vm] : vms) {
            if (vm.state == VMState::Running) {
                totalShares += vm.cpu.shares;
            }
        }

        if (totalShares == 0) {
            cout << "No runnable VMs.\n";
            return;
        }

        cout << "\nCPU weighted scheduling:\n";

        for (const auto& [id, vm] : vms) {
            if (vm.state != VMState::Running) {
                continue;
            }

            const double allocation =
                availableCoreSeconds *
                static_cast<double>(vm.cpu.shares) /
                static_cast<double>(totalShares);

            cout << "  "
                 << id
                 << ": shares="
                 << vm.cpu.shares
                 << ", allocated core-seconds="
                 << fixed
                 << setprecision(3)
                 << allocation
                 << '\n';
        }
    }

    void printVM(const string& id) const {
        const VM& vm = getVM(id);

        cout << "\nVM: " << vm.name
             << " (" << vm.id << ")\n";

        cout << "  State: "
             << to_string(vm.state)
             << '\n';

        cout << "  Image: "
             << vm.imageID
             << '\n';

        cout << "  vCPUs: "
             << vm.cpu.vcpus
             << " / "
             << vm.cpu.maxVcpus
             << "  shares="
             << vm.cpu.shares
             << '\n';

        cout << "  Memory: "
             << vm.memory.allocatedMB
             << " MB / "
             << vm.memory.maximumMB
             << " MB"
             << "  pressure="
             << vm.memory.pressurePercent
             << "%\n";

        cout << "  Storage: "
             << fixed
             << setprecision(2)
             << vm.diskUsedGB()
             << " / "
             << vm.diskCapacityGB()
             << " GB\n";

        for (const auto& [name, disk] : vm.disks) {
            cout << "    disk "
                 << name
                 << ": "
                 << disk.usedGB
                 << " / "
                 << disk.capacityGB
                 << " GB, bus="
                 << to_string(disk.bus)
                 << ", reads="
                 << disk.readOperations
                 << ", writes="
                 << disk.writeOperations
                 << '\n';
        }

        for (const auto& [name, nic] : vm.interfaces) {
            cout << "    NIC "
                 << name
                 << ": MAC="
                 << nic.mac
                 << ", IP="
                 << (nic.ip.empty() ? "<none>" : nic.ip)
                 << ", mode="
                 << to_string(nic.mode)
                 << ", RX="
                 << nic.rxMB
                 << " MB, TX="
                 << nic.txMB
                 << " MB\n";
        }

        cout << "  Boot count: "
             << vm.bootCount
             << '\n';

        cout << "  Uptime: "
             << vm.uptimeSeconds
             << " seconds\n";

        if (!vm.lastError.empty()) {
            cout << "  Last error: "
                 << vm.lastError
                 << '\n';
        }

        for (const auto& [snapshotID, snapshot] :
             vm.snapshots) {
            cout << "    snapshot "
                 << snapshotID
                 << ": changed="
                 << snapshot.changedGB
                 << " GB, memory="
                 << (snapshot.includesMemory ? "yes" : "no")
                 << '\n';
        }
    }

    void printHost() const {
        cout << "\nHost: "
             << host.name
             << '\n';

        cout << "  CPU: "
             << host.allocatedCPU
             << " / "
             << host.cpuCores
             << " cores allocated; free="
             << host.freeCPU()
             << '\n';

        cout << "  Memory: "
             << host.allocatedMemoryMB
             << " / "
             << host.memoryMB
             << " MB allocated; free="
             << host.freeMemoryMB()
             << " MB\n";

        cout << "  Storage: "
             << host.allocatedStorageGB
             << " / "
             << host.storageGB
             << " GB allocated; free="
             << host.freeStorageGB()
             << " GB\n";
    }

    void destroyVM(const string& id) {
        VM& vm = getVM(id);

        if (
            vm.state == VMState::Running ||
            vm.state == VMState::Paused ||
            vm.state == VMState::Starting
        ) {
            throw runtime_error(
                "VM must be stopped before destruction."
            );
        }

        const int storage =
            vm.diskCapacityGB();

        host.allocatedCPU -= vm.cpu.vcpus;
        host.allocatedMemoryMB -=
            vm.memory.allocatedMB;
        host.allocatedStorageGB -= storage;

        for (const auto& [name, nic] : vm.interfaces) {
            network.release(nic.ip);
        }

        vms.erase(id);

        log(
            "vm-destroyed",
            id,
            "all VM resources released"
        );
    }

    void printAudit() const {
        cout << "\nAudit records:\n";

        for (const auto& record : audit) {
            cout << "  ["
                 << record.timestamp
                 << "] "
                 << record.event
                 << " vm="
                 << record.vmID
                 << " "
                 << record.details
                 << '\n';
        }
    }
};


void demonstrateFailureCases(VMPlatform& platform) {
    cout << "\nFailure and validation cases:\n";

    try {
        platform.createVM(
            "oversized",
            "Oversized VM",
            "ubuntu-24",
            100,
            1024,
            20,
            NetworkMode::NAT
        );
    } catch (const exception& error) {
        cout << "  Expected creation failure: "
             << error.what()
             << '\n';
    }

    try {
        platform.getVM("web").resize; // Intentionally invalid concept is not used.
    } catch (...) {
        /*
         * This branch cannot be reached because the expression above is not
         * compiled as a member operation. It is intentionally avoided below.
         */
    }
}


int main() {
    try {
        ImageCatalog catalog;

        catalog.add({
            "ubuntu-24",
            "Ubuntu Server 24.04",
            "Linux",
            "24.04",
            "x86_64",
            8,
            "sha256:ubuntu-trusted-demo",
            true
        });

        catalog.add({
            "debian-13",
            "Debian 13",
            "Linux",
            "13",
            "x86_64",
            7,
            "sha256:debian-trusted-demo",
            true
        });

        ActivationPolicy policy(
            16,
            true
        );

        Host host{
            "compute-a01",
            16,
            32768,
            1000
        };

        VirtualNetwork network("10.40.0.");

        VMPlatform platform(
            host,
            catalog,
            policy,
            network
        );

        cout << "Virtual Machine Platform Case Study\n";

        cout << "\nImage verification:\n";
        cout << "  Ubuntu trusted checksum: "
             << boolalpha
             << catalog.verify(
                    "ubuntu-24",
                    "sha256:ubuntu-trusted-demo"
                )
             << '\n';

        cout << "  Ubuntu invalid checksum: "
             << catalog.verify(
                    "ubuntu-24",
                    "sha256:forged"
                )
             << '\n';

        platform.createVM(
            "web",
            "Production Web",
            "ubuntu-24",
            4,
            4096,
            50,
            NetworkMode::Bridged
        );

        platform.createVM(
            "database",
            "Production Database",
            "debian-13",
            6,
            8192,
            100,
            NetworkMode::Isolated
        );

        platform.printHost();

        platform.start("web");
        platform.start("database");

        platform.addDisk(
            "database",
            "database-data",
            250,
            DiskBus::SCSI
        );

        platform.simulateWorkload(
            "web",
            120,
            72.0,
            54.0,
            3.0,
            500.0,
            1200.0
        );

        platform.simulateWorkload(
            "database",
            120,
            88.0,
            79.0,
            8.0,
            350.0,
            700.0
        );

        platform.createSnapshot(
            "database",
            "before-schema-change",
            "Before schema change",
            false
        );

        platform.writeDisk(
            "database",
            "database-data",
            15.0
        );

        platform.readDisk(
            "database",
            "database-data",
            2.0
        );

        platform.printVM("database");

        platform.scheduleCPU(8.0);

        platform.balloonMemory(
            "web",
            3072
        );

        platform.resizeVCPU(
            "web",
            6
        );

        platform.printHost();

        platform.stop("database");

        platform.restoreSnapshot(
            "database",
            "before-schema-change"
        );

        platform.start("database");

        platform.pause("web");
        platform.resume("web");

        cout << "\nPost-recovery database state:\n";
        platform.printVM("database");

        try {
            platform.destroyVM("web");
        } catch (const exception& error) {
            cout << "\nExpected destruction failure: "
                 << error.what()
                 << '\n';
        }

        platform.stop("web");
        platform.destroyVM("web");

        platform.printHost();
        platform.printAudit();

        cout << "\nCase study completed successfully.\n";
        return 0;
    }
    catch (const exception& error) {
        cerr << "Fatal platform error: "
             << error.what()
             << '\n';
        return 1;
    }
}
