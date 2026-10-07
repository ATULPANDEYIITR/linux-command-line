#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Containers vs Virtual Machines
 *
 * Case study:
 * A platform engineering team must decide whether several workloads should
 * run as containers or virtual machines. The governance engine evaluates:
 *
 * - isolation requirements
 * - CPU and memory overhead
 * - workload density
 * - startup characteristics
 * - host operating-system compatibility
 * - guest-kernel requirements
 * - security-sensitive workloads
 *
 * The program is a C++17 executable and uses only the standard library.
 */

enum class WorkloadClass {
    Microservice,
    Database,
    LegacyApplication,
    BatchProcessing
};

enum class DeploymentType {
    Container,
    VirtualMachine
};

struct Host {
    std::string name;
    double cpuCores;
    double memoryGiB;
    double storageGiB;
    std::string kernel;
};

struct ResourceRequest {
    double cpuCores;
    double memoryGiB;
    double storageGiB;
};

struct IsolationModel {
    bool sharesHostKernel;
    bool hasGuestKernel;
    bool hasVirtualHardwareBoundary;
    double isolationScore;
    std::string securityBoundary;
};

struct RuntimeProfile {
    DeploymentType type;
    std::string name;
    IsolationModel isolation;
    double memoryOverheadGiB;
    double cpuOverheadPercent;
    double startupSeconds;
    double storageOverheadGiB;
    bool requiresCompatibleHostKernel;
};

struct Workload {
    std::string name;
    WorkloadClass classification;
    ResourceRequest request;
    bool requiresStrongIsolation;
    bool requiresSpecificGuestOs;
};

struct DeploymentEstimate {
    DeploymentType type;
    std::size_t instanceCount;
    double memoryGiB;
    double cpuCores;
    double storageGiB;
    double memoryUtilization;
    double cpuUtilization;
    double storageUtilization;
};

class CapacityError : public std::runtime_error {
public:
    explicit CapacityError(const std::string& message)
        : std::runtime_error(message) {}
};

class GovernanceEngine {
private:
    Host host;
    RuntimeProfile containerProfile;
    RuntimeProfile vmProfile;

    const RuntimeProfile& profileFor(DeploymentType type) const {
        return type == DeploymentType::Container
            ? containerProfile
            : vmProfile;
    }

public:
    GovernanceEngine(
        Host host,
        RuntimeProfile containerProfile,
        RuntimeProfile vmProfile)
        : host(std::move(host)),
          containerProfile(std::move(containerProfile)),
          vmProfile(std::move(vmProfile)) {}

    DeploymentEstimate estimate(
        DeploymentType type,
        const Workload& workload,
        std::size_t count) const {

        if (count == 0) {
            throw std::invalid_argument(
                "Instance count must be greater than zero.");
        }

        const auto& profile = profileFor(type);

        const double memory =
            count * (workload.request.memoryGiB +
                     profile.memoryOverheadGiB);

        const double cpu =
            count * workload.request.cpuCores *
            (1.0 + profile.cpuOverheadPercent / 100.0);

        const double storage =
            count * (workload.request.storageGiB +
                     profile.storageOverheadGiB);

        return {
            type,
            count,
            memory,
            cpu,
            storage,
            memory / host.memoryGiB * 100.0,
            cpu / host.cpuCores * 100.0,
            storage / host.storageGiB * 100.0
        };
    }

    bool isSuitable(
        DeploymentType type,
        const Workload& workload) const {

        const auto& profile = profileFor(type);

        if (workload.requiresStrongIsolation &&
            profile.isolation.isolationScore < 0.9) {
            return false;
        }

        if (workload.requiresSpecificGuestOs &&
            type != DeploymentType::VirtualMachine) {
            return false;
        }

        return true;
    }

    std::optional<std::string> validateCapacity(
        const DeploymentEstimate& estimate) const {

        if (estimate.memoryUtilization > 100.0) {
            return std::string("Memory capacity exceeded.");
        }

        if (estimate.cpuUtilization > 100.0) {
            return std::string("CPU capacity exceeded.");
        }

        if (estimate.storageUtilization > 100.0) {
            return std::string("Storage capacity exceeded.");
        }

        return std::nullopt;
    }

    const RuntimeProfile& profile(DeploymentType type) const {
        return profileFor(type);
    }
};

std::string workloadName(WorkloadClass value) {
    switch (value) {
        case WorkloadClass::Microservice:
            return "Microservice";
        case WorkloadClass::Database:
            return "Database";
        case WorkloadClass::LegacyApplication:
            return "Legacy application";
        case WorkloadClass::BatchProcessing:
            return "Batch processing";
    }

    return "Unknown";
}

std::string deploymentName(DeploymentType type) {
    return type == DeploymentType::Container
        ? "Container"
        : "Virtual Machine";
}

void printEstimate(const DeploymentEstimate& estimate) {
    std::cout << std::fixed << std::setprecision(2);

    std::cout
        << deploymentName(estimate.type)
        << " x " << estimate.instanceCount
        << " | RAM=" << estimate.memoryGiB << " GiB"
        << " | CPU=" << estimate.cpuCores
        << " | Storage=" << estimate.storageGiB << " GiB"
        << " | RAM=" << estimate.memoryUtilization << "%"
        << " | CPU=" << estimate.cpuUtilization << "%"
        << " | Storage=" << estimate.storageUtilization << "%\n";
}

void printArchitecture(const GovernanceEngine& engine) {
    std::cout << "\n=== Architecture ===\n";

    for (const auto type :
         {DeploymentType::Container, DeploymentType::VirtualMachine}) {

        const auto& profile = engine.profile(type);

        std::cout << "\n" << profile.name << "\n";
        std::cout
            << "Kernel model: "
            << (profile.isolation.sharesHostKernel
                    ? "shared host kernel"
                    : "independent guest kernel")
            << "\n";

        std::cout
            << "Virtual hardware boundary: "
            << (profile.isolation.hasVirtualHardwareBoundary
                    ? "yes"
                    : "no")
            << "\n";

        std::cout
            << "Isolation score: "
            << profile.isolation.isolationScore
            << "\n";

        std::cout
            << "Security boundary: "
            << profile.isolation.securityBoundary
            << "\n";
    }
}

void evaluateWorkload(
    const GovernanceEngine& engine,
    const Workload& workload,
    std::size_t count) {

    std::cout << "\n=== " << workload.name << " ===\n";
    std::cout
        << "Classification: "
        << workloadName(workload.classification)
        << "\n";

    for (const auto type :
         {DeploymentType::Container, DeploymentType::VirtualMachine}) {

        std::cout << "\n";

        if (!engine.isSuitable(type, workload)) {
            std::cout
                << deploymentName(type)
                << ": rejected by workload policy\n";
            continue;
        }

        const auto estimate =
            engine.estimate(type, workload, count);

        printEstimate(estimate);

        const auto validation =
            engine.validateCapacity(estimate);

        if (validation) {
            std::cout << "Capacity decision: "
                      << *validation << "\n";
        } else {
            std::cout << "Capacity decision: acceptable\n";
        }
    }
}

void startupComparison(const GovernanceEngine& engine) {
    std::cout << "\n=== Startup Characteristics ===\n";

    const double container =
        engine.profile(DeploymentType::Container).startupSeconds;

    const double vm =
        engine.profile(DeploymentType::VirtualMachine).startupSeconds;

    std::cout << "Container modeled startup: "
              << container << " seconds\n";

    std::cout << "VM modeled startup: "
              << vm << " seconds\n";

    std::cout << "VM/container startup ratio: "
              << vm / container << "x\n";

    std::cout
        << "The difference reflects application-process startup versus "
           "guest operating-system initialization."
        << "\n";
}

void portabilityComparison() {
    std::cout << "\n=== Portability Model ===\n";

    struct Target {
        std::string name;
        std::string kernel;
    };

    const std::vector<Target> targets{
        {"Linux cloud host", "Linux 6.12"},
        {"Linux bare-metal host", "Linux 6.8"},
        {"Windows Server host", "Windows Server 2025"},
        {"FreeBSD host", "FreeBSD 14"}
    };

    int containerCompatible = 0;
    int vmCompatible = 0;

    for (const auto& target : targets) {
        if (target.kernel.rfind("Linux", 0) == 0) {
            ++containerCompatible;
        }

        // The VM carries its guest kernel, so this simplified model marks
        // all listed host operating systems as compatible.
        ++vmCompatible;
    }

    std::cout
        << "Container compatibility: "
        << (100.0 * containerCompatible / targets.size())
        << "%\n";

    std::cout
        << "VM compatibility: "
        << (100.0 * vmCompatible / targets.size())
        << "%\n";

    std::cout
        << "Portability is not merely image portability. Containers also "
           "depend on compatible kernel facilities, while a VM includes "
           "the guest operating system."
        << "\n";
}

void exceptionHandlingDemo(const GovernanceEngine& engine) {
    std::cout << "\n=== Invalid Configuration Handling ===\n";

    try {
        Workload invalid{
            "Invalid service",
            WorkloadClass::Microservice,
            {-1.0, 1.0, 0.2},
            false,
            false
        };

        if (invalid.request.cpuCores <= 0 ||
            invalid.request.memoryGiB <= 0 ||
            invalid.request.storageGiB <= 0) {
            throw std::invalid_argument(
                "Workload resource requests must be positive.");
        }

        engine.estimate(
            DeploymentType::Container,
            invalid,
            1);
    }
    catch (const std::exception& error) {
        std::cout
            << "Invalid workload rejected: "
            << error.what()
            << "\n";
    }

    try {
        Workload valid{
            "API service",
            WorkloadClass::Microservice,
            {0.25, 1.0, 0.2},
            false,
            false
        };

        engine.estimate(
            DeploymentType::Container,
            valid,
            0);
    }
    catch (const std::exception& error) {
        std::cout
            << "Invalid instance count rejected: "
            << error.what()
            << "\n";
    }
}

int main() {
    try {
        const Host host{
            "production-node",
            16.0,
            64.0,
            500.0,
            "Linux 6.12"
        };

        const RuntimeProfile container{
            DeploymentType::Container,
            "Container",
            {
                true,
                false,
                false,
                0.72,
                "OS-level isolation with shared host kernel"
            },
            0.08,
            2.0,
            0.8,
            0.15,
            true
        };

        const RuntimeProfile vm{
            DeploymentType::VirtualMachine,
            "Virtual Machine",
            {
                false,
                true,
                true,
                0.96,
                "hardware-assisted virtualization boundary"
            },
            0.90,
            7.0,
            25.0,
            8.0,
            false
        };

        const GovernanceEngine engine(host, container, vm);

        printArchitecture(engine);

        const Workload microservice{
            "Payment API",
            WorkloadClass::Microservice,
            {0.25, 1.0, 0.20},
            false,
            false
        };

        const Workload legacy{
            "Legacy ERP connector",
            WorkloadClass::LegacyApplication,
            {1.5, 4.0, 8.0},
            true,
            true
        };

        const Workload database{
            "Transactional database",
            WorkloadClass::Database,
            {2.0, 8.0, 20.0},
            true,
            false
        };

        evaluateWorkload(engine, microservice, 30);
        evaluateWorkload(engine, legacy, 5);
        evaluateWorkload(engine, database, 4);

        startupComparison(engine);
        portabilityComparison();
        exceptionHandlingDemo(engine);

        std::cout << "\n=== Architectural Interpretation ===\n";
        std::cout
            << "Containers are favored when application density, fast "
               "startup, and efficient resource usage dominate."
            << "\n";

        std::cout
            << "VMs are favored when guest-kernel independence, stronger "
               "isolation, or heterogeneous operating-system requirements "
               "dominate."
            << "\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";
        return 1;
    }
}
