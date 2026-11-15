#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * Introduction to Containers
 *
 * C++17 container runtime and resource-isolation simulator.
 *
 * Models:
 * - Image packaging and layered filesystems
 * - Image identity and versioning
 * - Container lifecycle
 * - CPU and memory allocation
 * - Network port ownership
 * - Process isolation limits
 * - Security restrictions
 * - Health states
 * - Restart policies
 * - Deployment eligibility
 *
 * Educational simulation only.
 * Actual operating-system isolation requires a container runtime.
 */

enum class ContainerState {
    Created,
    Running,
    Stopped,
    Failed,
    Removed
};

enum class HealthStatus {
    Starting,
    Healthy,
    Unhealthy
};

enum class RestartPolicy {
    Never,
    OnFailure,
    Always
};

std::string toString(ContainerState state) {
    switch (state) {
        case ContainerState::Created: return "CREATED";
        case ContainerState::Running: return "RUNNING";
        case ContainerState::Stopped: return "STOPPED";
        case ContainerState::Failed: return "FAILED";
        case ContainerState::Removed: return "REMOVED";
    }

    throw std::logic_error("Unknown container state.");
}

std::string toString(HealthStatus status) {
    switch (status) {
        case HealthStatus::Starting: return "STARTING";
        case HealthStatus::Healthy: return "HEALTHY";
        case HealthStatus::Unhealthy: return "UNHEALTHY";
    }

    throw std::logic_error("Unknown health status.");
}

class ContainerException : public std::runtime_error {
public:
    explicit ContainerException(const std::string& message)
        : std::runtime_error(message) {}
};

struct ImageLayer {
    std::string instruction;
    std::string content;

    std::size_t size() const {
        return content.size();
    }
};

class ContainerImage {
private:
    std::string name_;
    std::string tag_;
    std::vector<ImageLayer> layers_;
    std::vector<int> exposedPorts_;
    std::string entrypoint_;
    std::string user_;
    int vulnerabilities_;

public:
    ContainerImage(
        std::string name,
        std::string tag,
        std::vector<ImageLayer> layers,
        std::vector<int> ports,
        std::string entrypoint,
        std::string user,
        int vulnerabilities = 0
    )
        : name_(std::move(name)),
          tag_(std::move(tag)),
          layers_(std::move(layers)),
          exposedPorts_(std::move(ports)),
          entrypoint_(std::move(entrypoint)),
          user_(std::move(user)),
          vulnerabilities_(vulnerabilities) {

        if (name_.empty() || tag_.empty()) {
            throw ContainerException("Image name and tag are required.");
        }

        if (layers_.empty()) {
            throw ContainerException("Image must contain layers.");
        }

        if (entrypoint_.empty()) {
            throw ContainerException("Entrypoint cannot be empty.");
        }

        if (vulnerabilities_ < 0) {
            throw ContainerException("Invalid vulnerability count.");
        }

        for (int port : exposedPorts_) {
            if (port < 1 || port > 65535) {
                throw ContainerException("Invalid exposed port.");
            }
        }

        std::sort(exposedPorts_.begin(), exposedPorts_.end());

        if (std::adjacent_find(
                exposedPorts_.begin(),
                exposedPorts_.end()
            ) != exposedPorts_.end()) {
            throw ContainerException("Duplicate exposed ports.");
        }
    }

    std::string reference() const {
        return name_ + ":" + tag_;
    }

    std::size_t sizeBytes() const {
        std::size_t total = 0;

        for (const auto& layer : layers_) {
            total += layer.size();
        }

        return total;
    }

    bool exposesPort(int port) const {
        return std::binary_search(
            exposedPorts_.begin(),
            exposedPorts_.end(),
            port
        );
    }

    int vulnerabilityCount() const {
        return vulnerabilities_;
    }

    const std::string& user() const {
        return user_;
    }

    const std::string& entrypoint() const {
        return entrypoint_;
    }

    std::size_t layerCount() const {
        return layers_.size();
    }
};

struct ResourceLimits {
    double cpuCores = 1.0;
    int memoryMB = 256;
    int processLimit = 100;

    void validate() const {
        if (
            !std::isfinite(cpuCores) ||
            cpuCores <= 0 ||
            cpuCores > 64
        ) {
            throw ContainerException("Invalid CPU allocation.");
        }

        if (memoryMB < 16 || memoryMB > 262144) {
            throw ContainerException("Invalid memory allocation.");
        }

        if (processLimit < 1 || processLimit > 32768) {
            throw ContainerException("Invalid process limit.");
        }
    }
};

struct ContainerConfig {
    ResourceLimits resources;
    std::map<int, int> portMappings;
    std::map<std::string, std::string> environment;
    RestartPolicy restartPolicy = RestartPolicy::Never;
    bool privileged = false;
    bool runAsRoot = false;
    bool readOnlyRootfs = true;

    void validate(const ContainerImage& image) const {
        resources.validate();

        if (privileged) {
            throw ContainerException("Privileged mode prohibited.");
        }

        if (runAsRoot || image.user() == "root") {
            throw ContainerException("Root execution prohibited.");
        }

        if (!readOnlyRootfs) {
            throw ContainerException("Read-only root filesystem required.");
        }

        for (const auto& mapping : portMappings) {
            int containerPort = mapping.first;
            int hostPort = mapping.second;

            if (!image.exposesPort(containerPort)) {
                throw ContainerException(
                    "Container port is not exposed by image."
                );
            }

            if (hostPort < 1 || hostPort > 65535) {
                throw ContainerException("Invalid host port.");
            }
        }

        std::set<int> hostPorts;

        for (const auto& mapping : portMappings) {
            if (!hostPorts.insert(mapping.second).second) {
                throw ContainerException("Duplicate host port.");
            }
        }

        for (const auto& variable : environment) {
            if (
                variable.first.empty() ||
                variable.first.size() > 128 ||
                variable.second.size() > 4096
            ) {
                throw ContainerException("Invalid environment configuration.");
            }
        }
    }
};

class ResourceManager {
private:
    double totalCPU_;
    int totalMemoryMB_;
    std::map<std::string, ResourceLimits> allocations_;

public:
    ResourceManager(double cpu, int memoryMB)
        : totalCPU_(cpu), totalMemoryMB_(memoryMB) {

        if (cpu <= 0 || memoryMB <= 0) {
            throw ContainerException("Invalid host capacity.");
        }
    }

    void allocate(
        const std::string& id,
        const ResourceLimits& request
    ) {
        if (allocations_.count(id)) {
            throw ContainerException("Resources already allocated.");
        }

        double usedCPU = 0;
        int usedMemory = 0;

        for (const auto& allocation : allocations_) {
            usedCPU += allocation.second.cpuCores;
            usedMemory += allocation.second.memoryMB;
        }

        if (usedCPU + request.cpuCores > totalCPU_) {
            throw ContainerException("CPU capacity exceeded.");
        }

        if (usedMemory + request.memoryMB > totalMemoryMB_) {
            throw ContainerException("Memory capacity exceeded.");
        }

        allocations_[id] = request;
    }

    void release(const std::string& id) {
        allocations_.erase(id);
    }

    void report() const {
        double cpu = 0;
        int memory = 0;

        for (const auto& allocation : allocations_) {
            cpu += allocation.second.cpuCores;
            memory += allocation.second.memoryMB;
        }

        std::cout << "Allocated CPU: " << cpu
                  << "/" << totalCPU_ << "\n";

        std::cout << "Allocated memory: " << memory
                  << "/" << totalMemoryMB_ << " MB\n";
    }
};

class NetworkManager {
private:
    std::map<int, std::string> portOwners_;

public:
    void reserve(
        const std::string& containerId,
        const std::map<int, int>& mappings
    ) {
        for (const auto& mapping : mappings) {
            int hostPort = mapping.second;

            auto it = portOwners_.find(hostPort);

            if (
                it != portOwners_.end() &&
                it->second != containerId
            ) {
                throw ContainerException("Host port already occupied.");
            }
        }

        for (const auto& mapping : mappings) {
            portOwners_[mapping.second] = containerId;
        }
    }

    void release(const std::string& containerId) {
        for (auto it = portOwners_.begin(); it != portOwners_.end();) {
            if (it->second == containerId) {
                it = portOwners_.erase(it);
            } else {
                ++it;
            }
        }
    }
};

class Container {
private:
    std::string id_;
    const ContainerImage& image_;
    ContainerConfig config_;
    ResourceManager& resources_;
    NetworkManager& network_;

    ContainerState state_ = ContainerState::Created;
    HealthStatus health_ = HealthStatus::Starting;
    int restartCount_ = 0;

    static int nextId_;

public:
    Container(
        const ContainerImage& image,
        ContainerConfig config,
        ResourceManager& resources,
        NetworkManager& network
    )
        : id_("container-" + std::to_string(++nextId_)),
          image_(image),
          config_(std::move(config)),
          resources_(resources),
          network_(network) {

        config_.validate(image_);
    }

    const std::string& id() const {
        return id_;
    }

    ContainerState state() const {
        return state_;
    }

    void start() {
        if (
            state_ != ContainerState::Created &&
            state_ != ContainerState::Stopped
        ) {
            throw ContainerException("Invalid start transition.");
        }

        resources_.allocate(id_, config_.resources);

        try {
            network_.reserve(id_, config_.portMappings);
        } catch (...) {
            resources_.release(id_);
            throw;
        }

        state_ = ContainerState::Running;
        health_ = HealthStatus::Starting;

        std::cout << id_ << " started using "
                  << image_.reference() << "\n";
    }

    void markHealthy() {
        if (state_ != ContainerState::Running) {
            throw ContainerException("Container is not running.");
        }

        health_ = HealthStatus::Healthy;
    }

    void stop() {
        if (state_ != ContainerState::Running) {
            throw ContainerException("Container is not running.");
        }

        resources_.release(id_);
        network_.release(id_);

        state_ = ContainerState::Stopped;
        health_ = HealthStatus::Unhealthy;
    }

    void fail() {
        if (state_ != ContainerState::Running) {
            throw ContainerException("Cannot fail inactive container.");
        }

        resources_.release(id_);
        network_.release(id_);

        state_ = ContainerState::Failed;
        health_ = HealthStatus::Unhealthy;
    }

    bool restart() {
        if (state_ != ContainerState::Failed) {
            throw ContainerException("Container has not failed.");
        }

        if (config_.restartPolicy == RestartPolicy::Never) {
            return false;
        }

        if (
            config_.restartPolicy == RestartPolicy::OnFailure &&
            restartCount_ >= 3
        ) {
            return false;
        }

        ++restartCount_;
        state_ = ContainerState::Stopped;
        start();

        return true;
    }

    void remove() {
        if (state_ == ContainerState::Running) {
            throw ContainerException("Stop before removal.");
        }

        if (state_ == ContainerState::Removed) {
            throw ContainerException("Already removed.");
        }

        state_ = ContainerState::Removed;
    }

    void report() const {
        std::cout << "\nContainer ID: " << id_ << "\n";
        std::cout << "Image: " << image_.reference() << "\n";
        std::cout << "State: " << toString(state_) << "\n";
        std::cout << "Health: " << toString(health_) << "\n";
        std::cout << "Restarts: " << restartCount_ << "\n";
    }
};

int Container::nextId_ = 0;

class ContainerRuntime {
private:
    ResourceManager resources_;
    NetworkManager network_;
    std::vector<std::unique_ptr<Container>> containers_;

public:
    ContainerRuntime(double cpu, int memoryMB)
        : resources_(cpu, memoryMB) {}

    Container& create(
        const ContainerImage& image,
        const ContainerConfig& config
    ) {
        if (image.vulnerabilityCount() > 0) {
            throw ContainerException("Image failed security scanning.");
        }

        auto container = std::make_unique<Container>(
            image,
            config,
            resources_,
            network_
        );

        Container& reference = *container;
        containers_.push_back(std::move(container));

        return reference;
    }

    void report() const {
        std::cout << "\n=== CONTAINER INVENTORY ===\n";

        for (const auto& container : containers_) {
            container->report();
        }

        std::cout << "\n=== RESOURCE USAGE ===\n";
        resources_.report();
    }
};

int main() {
    try {
        std::cout << "=== CONTAINERIZATION ENGINE ===\n";

        std::vector<ImageLayer> layers = {
            {"FROM", "ubuntu:24.04"},
            {"WORKDIR", "/application"},
            {"COPY", "application files"},
            {"RUN", "install application dependencies"},
            {"COPY", "server executable"}
        };

        ContainerImage image(
            "inventory-service",
            "1.0.0",
            layers,
            {8080},
            "/application/server",
            "app",
            0
        );

        std::cout << "\nImage: " << image.reference() << "\n";
        std::cout << "Layers: " << image.layerCount() << "\n";
        std::cout << "Image size: " << image.sizeBytes() << " bytes\n";

        ContainerRuntime runtime(8.0, 8192);

        ContainerConfig configuration;
        configuration.resources = {1.5, 512, 100};
        configuration.portMappings = {{8080, 9090}};
        configuration.environment = {
            {"APP_ENV", "production"},
            {"LOG_LEVEL", "info"}
        };
        configuration.restartPolicy = RestartPolicy::OnFailure;
        configuration.readOnlyRootfs = true;

        Container& container = runtime.create(image, configuration);

        container.start();
        container.markHealthy();

        runtime.report();

        std::cout << "\nSimulating process failure...\n";

        container.fail();

        std::cout << "Restart successful: "
                  << std::boolalpha
                  << container.restart()
                  << "\n";

        container.markHealthy();

        runtime.report();

        container.stop();
        container.remove();

        std::cout << "\nFinal state: "
                  << toString(container.state())
                  << "\n";

        // Security policy demonstration.
        try {
            ContainerConfig insecure;
            insecure.privileged = true;

            runtime.create(image, insecure);
        } catch (const ContainerException& error) {
            std::cout << "\nSecurity rejection: "
                      << error.what() << "\n";
        }

        // Resource validation demonstration.
        try {
            ResourceLimits invalid{0, 0, 0};
            invalid.validate();
        } catch (const ContainerException& error) {
            std::cout << "Resource rejection: "
                      << error.what() << "\n";
        }

    } catch (const std::exception& error) {
        std::cerr << "Runtime error: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
