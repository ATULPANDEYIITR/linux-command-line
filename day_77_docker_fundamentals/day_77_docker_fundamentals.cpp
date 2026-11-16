#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Docker Fundamentals: Repository and Container Governance Engine.
 *
 * C++17 implementation of:
 * - Docker architecture
 * - Image and layer management
 * - Registry distribution
 * - Container lifecycle
 * - Resource allocation policies
 * - Port and volume mappings
 * - Container inspection
 * - Merge-free image deployment workflow
 * - Validation and failure handling
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic docker_fundamentals.cpp -o docker_lab
 */

enum class ContainerState {
    Created,
    Running,
    Paused,
    Exited,
    Dead
};

enum class ImageOrigin {
    Built,
    Registry,
    Local
};

std::string toString(ContainerState state) {
    switch (state) {
        case ContainerState::Created: return "created";
        case ContainerState::Running: return "running";
        case ContainerState::Paused: return "paused";
        case ContainerState::Exited: return "exited";
        case ContainerState::Dead: return "dead";
    }

    throw std::logic_error("Unknown container state");
}

std::string toString(ImageOrigin origin) {
    switch (origin) {
        case ImageOrigin::Built: return "built";
        case ImageOrigin::Registry: return "registry";
        case ImageOrigin::Local: return "local";
    }

    throw std::logic_error("Unknown image origin");
}

// ============================================================
// 1. VALIDATION
// ============================================================

void requireNonEmpty(
    const std::string& value,
    const std::string& field
) {
    if (value.empty()) {
        throw std::invalid_argument(field + " cannot be empty");
    }

    if (value.find('\0') != std::string::npos) {
        throw std::invalid_argument(field + " contains invalid data");
    }
}

void validatePort(int port) {
    if (port < 1 || port > 65535) {
        throw std::invalid_argument(
            "Port must be between 1 and 65535"
        );
    }
}

void validateResources(double cpu, int memoryMB) {
    if (!std::isfinite(cpu) || cpu <= 0) {
        throw std::invalid_argument("CPU must be positive");
    }

    if (memoryMB < 6) {
        throw std::invalid_argument("Memory must be at least 6 MB");
    }
}

// ============================================================
// 2. ARCHITECTURE MODEL
// ============================================================

struct ArchitectureComponent {
    std::string name;
    std::string responsibility;
};

class DockerArchitecture {
public:
    static std::vector<ArchitectureComponent> components() {
        return {
            {
                "Docker CLI",
                "Accepts user commands and calls the Docker API."
            },
            {
                "Docker daemon",
                "Manages images, containers, networks and volumes."
            },
            {
                "containerd",
                "Manages container lifecycle operations."
            },
            {
                "runc",
                "Creates containers using Linux isolation mechanisms."
            },
            {
                "BuildKit",
                "Builds optimized container images."
            },
            {
                "Registry",
                "Stores and distributes image manifests and layers."
            }
        };
    }

    static void display() {
        std::cout << "\nDOCKER ARCHITECTURE\n";

        for (const auto& component : components()) {
            std::cout << component.name << "\n"
                      << "  " << component.responsibility
                      << "\n";
        }

        std::cout
            << "\nCommand flow:\n"
            << "CLI -> Docker API -> dockerd\n"
            << "dockerd -> containerd -> runc\n";
    }
};

// ============================================================
// 3. IMAGE LAYERS
// ============================================================

struct ImageLayer {
    std::string id;
    std::string instruction;
    double sizeMB;

    ImageLayer(
        std::string layerId,
        std::string command,
        double size
    )
        : id(std::move(layerId)),
          instruction(std::move(command)),
          sizeMB(size) {

        requireNonEmpty(id, "Layer ID");
        requireNonEmpty(instruction, "Instruction");

        if (!std::isfinite(sizeMB) || sizeMB < 0) {
            throw std::invalid_argument(
                "Layer size cannot be negative"
            );
        }
    }
};

// ============================================================
// 4. IMAGE DOMAIN MODEL
// ============================================================

class DockerImage {
private:
    std::string repository_;
    std::string tag_;
    std::vector<ImageLayer> layers_;
    ImageOrigin origin_;

public:
    DockerImage(
        std::string repository,
        std::string tag,
        std::vector<ImageLayer> layers,
        ImageOrigin origin
    )
        : repository_(std::move(repository)),
          tag_(std::move(tag)),
          layers_(std::move(layers)),
          origin_(origin) {

        requireNonEmpty(repository_, "Repository");
        requireNonEmpty(tag_, "Image tag");

        if (layers_.empty()) {
            throw std::invalid_argument(
                "Image must contain at least one layer"
            );
        }

        std::set<std::string> identifiers;

        for (const auto& layer : layers_) {
            if (!identifiers.insert(layer.id).second) {
                throw std::invalid_argument(
                    "Duplicate layer identifier"
                );
            }
        }
    }

    const std::string& repository() const {
        return repository_;
    }

    const std::string& tag() const {
        return tag_;
    }

    std::string reference() const {
        return repository_ + ":" + tag_;
    }

    const std::vector<ImageLayer>& layers() const {
        return layers_;
    }

    ImageOrigin origin() const {
        return origin_;
    }

    double sizeMB() const {
        double total = 0;

        for (const auto& layer : layers_) {
            total += layer.sizeMB;
        }

        return total;
    }

    std::size_t layerCount() const {
        return layers_.size();
    }
};

// ============================================================
// 5. IMAGE STORE
// ============================================================

class ImageStore {
private:
    std::unordered_map<
        std::string,
        std::shared_ptr<const DockerImage>
    > images_;

public:
    void add(std::shared_ptr<const DockerImage> image) {
        if (!image) {
            throw std::invalid_argument("Image cannot be null");
        }

        images_[image->reference()] = std::move(image);
    }

    std::shared_ptr<const DockerImage> get(
        const std::string& reference
    ) const {
        auto iterator = images_.find(reference);

        if (iterator == images_.end()) {
            throw std::runtime_error(
                "Local image not found: " + reference
            );
        }

        return iterator->second;
    }

    void remove(const std::string& reference) {
        if (images_.erase(reference) == 0) {
            throw std::runtime_error("Image not found");
        }
    }

    void display() const {
        std::cout << "\nLOCAL IMAGE INVENTORY\n";

        for (const auto& entry : images_) {
            const auto& image = *entry.second;

            std::cout
                << std::left << std::setw(30)
                << image.reference()
                << std::setw(12) << image.layerCount()
                << std::fixed << std::setprecision(2)
                << image.sizeMB() << " MB\n";
        }
    }
};

// ============================================================
// 6. REGISTRY
// ============================================================

class ImageRegistry {
private:
    std::string hostname_;

    std::unordered_map<
        std::string,
        std::shared_ptr<const DockerImage>
    > remoteImages_;

    std::set<std::string> authenticatedUsers_;

public:
    explicit ImageRegistry(std::string hostname)
        : hostname_(std::move(hostname)) {

        requireNonEmpty(hostname_, "Registry hostname");
    }

    void login(const std::string& username) {
        requireNonEmpty(username, "Username");
        authenticatedUsers_.insert(username);
    }

    void logout(const std::string& username) {
        authenticatedUsers_.erase(username);
    }

    std::string push(
        const std::shared_ptr<const DockerImage>& image,
        const std::string& username
    ) {
        if (!image) {
            throw std::invalid_argument("Image cannot be null");
        }

        if (authenticatedUsers_.count(username) == 0) {
            throw std::runtime_error(
                "Registry authentication required"
            );
        }

        std::string remoteReference =
            hostname_ + "/" + image->reference();

        remoteImages_[remoteReference] = image;

        return remoteReference;
    }

    std::shared_ptr<const DockerImage> pull(
        const std::string& reference
    ) const {
        auto iterator = remoteImages_.find(reference);

        if (iterator == remoteImages_.end()) {
            throw std::runtime_error(
                "Remote image not found: " + reference
            );
        }

        return iterator->second;
    }

    std::size_t imageCount() const {
        return remoteImages_.size();
    }
};

// ============================================================
// 7. RESOURCE CONFIGURATION
// ============================================================

struct ContainerConfiguration {
    std::string name;
    std::map<int, int> ports;
    std::map<std::string, std::string> volumes;
    std::map<std::string, std::string> environment;

    double cpu = 1.0;
    int memoryMB = 512;
};

class ResourcePolicy {
private:
    double maxCPU_;
    int maxMemoryMB_;
    std::size_t maxPorts_;

public:
    ResourcePolicy(
        double maxCPU,
        int maxMemoryMB,
        std::size_t maxPorts
    )
        : maxCPU_(maxCPU),
          maxMemoryMB_(maxMemoryMB),
          maxPorts_(maxPorts) {

        validateResources(maxCPU_, maxMemoryMB_);

        if (maxPorts_ == 0) {
            throw std::invalid_argument(
                "Maximum port count must be positive"
            );
        }
    }

    void evaluate(
        const ContainerConfiguration& configuration
    ) const {
        validateResources(
            configuration.cpu,
            configuration.memoryMB
        );

        if (configuration.cpu > maxCPU_) {
            throw std::runtime_error(
                "CPU allocation exceeds policy"
            );
        }

        if (configuration.memoryMB > maxMemoryMB_) {
            throw std::runtime_error(
                "Memory allocation exceeds policy"
            );
        }

        if (configuration.ports.size() > maxPorts_) {
            throw std::runtime_error(
                "Port mapping limit exceeded"
            );
        }

        for (const auto& mapping : configuration.ports) {
            validatePort(mapping.first);
            validatePort(mapping.second);
        }
    }
};

// ============================================================
// 8. CONTAINER
// ============================================================

class DockerContainer {
private:
    std::string id_;
    ContainerConfiguration configuration_;
    std::shared_ptr<const DockerImage> image_;
    ContainerState state_;
    unsigned int restartCount_;

    void transition(
        ContainerState expected,
        ContainerState next
    ) {
        if (state_ != expected) {
            throw std::runtime_error(
                "Invalid transition: " +
                toString(state_) + " -> " + toString(next)
            );
        }

        state_ = next;

        std::cout
            << "EVENT [" << configuration_.name
            << "]: " << toString(state_) << "\n";
    }

public:
    DockerContainer(
        std::string id,
        ContainerConfiguration configuration,
        std::shared_ptr<const DockerImage> image
    )
        : id_(std::move(id)),
          configuration_(std::move(configuration)),
          image_(std::move(image)),
          state_(ContainerState::Created),
          restartCount_(0) {

        requireNonEmpty(id_, "Container ID");
        requireNonEmpty(configuration_.name, "Container name");

        if (!image_) {
            throw std::invalid_argument("Container image is required");
        }
    }

    void start() {
        if (
            state_ != ContainerState::Created &&
            state_ != ContainerState::Exited
        ) {
            throw std::runtime_error(
                "Container cannot be started"
            );
        }

        transition(state_, ContainerState::Running);
    }

    void pause() {
        transition(
            ContainerState::Running,
            ContainerState::Paused
        );
    }

    void unpause() {
        transition(
            ContainerState::Paused,
            ContainerState::Running
        );
    }

    void stop() {
        if (
            state_ != ContainerState::Running &&
            state_ != ContainerState::Paused
        ) {
            throw std::runtime_error(
                "Container cannot be stopped"
            );
        }

        transition(state_, ContainerState::Exited);
    }

    void restart() {
        if (state_ == ContainerState::Dead) {
            throw std::runtime_error(
                "Dead container cannot restart"
            );
        }

        if (
            state_ == ContainerState::Running ||
            state_ == ContainerState::Paused
        ) {
            stop();
        }

        if (state_ != ContainerState::Exited) {
            throw std::runtime_error(
                "Container is not restartable"
            );
        }

        ++restartCount_;
        start();
    }

    void remove(bool force = false) {
        if (
            (state_ == ContainerState::Running ||
             state_ == ContainerState::Paused) &&
            !force
        ) {
            throw std::runtime_error(
                "Running container requires force removal"
            );
        }

        state_ = ContainerState::Dead;

        std::cout
            << "EVENT [" << configuration_.name
            << "]: dead\n";
    }

    ContainerState state() const {
        return state_;
    }

    const std::string& name() const {
        return configuration_.name;
    }

    std::string inspect() const {
        std::ostringstream output;

        output
            << "Container ID: " << id_ << "\n"
            << "Name: " << configuration_.name << "\n"
            << "Image: " << image_->reference() << "\n"
            << "State: " << toString(state_) << "\n"
            << "CPU: " << configuration_.cpu << "\n"
            << "Memory: " << configuration_.memoryMB << " MB\n"
            << "Restarts: " << restartCount_ << "\n";

        output << "Ports:\n";

        for (const auto& mapping : configuration_.ports) {
            output
                << "  " << mapping.first
                << " -> " << mapping.second << "\n";
        }

        output << "Volumes:\n";

        for (const auto& mapping : configuration_.volumes) {
            output
                << "  " << mapping.first
                << " -> " << mapping.second << "\n";
        }

        return output.str();
    }
};

// ============================================================
// 9. DOCKER ENGINE
// ============================================================

class DockerEngine {
private:
    ImageStore images_;
    ResourcePolicy policy_;

    std::map<std::string, std::unique_ptr<DockerContainer>>
        containers_;

    std::set<std::string> usedNames_;

    unsigned int nextId_ = 1;

public:
    explicit DockerEngine(ResourcePolicy policy)
        : policy_(std::move(policy)) {}

    ImageStore& imageStore() {
        return images_;
    }

    std::string createContainer(
        const ContainerConfiguration& configuration,
        const std::string& imageReference
    ) {
        requireNonEmpty(configuration.name, "Container name");

        if (usedNames_.count(configuration.name)) {
            throw std::runtime_error(
                "Duplicate container name"
            );
        }

        policy_.evaluate(configuration);

        auto image = images_.get(imageReference);

        std::ostringstream id;
        id << "container-" << std::setw(4)
           << std::setfill('0') << nextId_++;

        auto container = std::make_unique<DockerContainer>(
            id.str(),
            configuration,
            image
        );

        const std::string name = configuration.name;

        containers_[name] = std::move(container);
        usedNames_.insert(name);

        return name;
    }

    DockerContainer& getContainer(const std::string& name) {
        auto iterator = containers_.find(name);

        if (iterator == containers_.end()) {
            throw std::runtime_error(
                "Container not found: " + name
            );
        }

        return *iterator->second;
    }

    void removeContainer(
        const std::string& name,
        bool force = false
    ) {
        auto& container = getContainer(name);

        container.remove(force);

        containers_.erase(name);
        usedNames_.erase(name);
    }

    void displayContainers() const {
        std::cout << "\nCONTAINER INVENTORY\n";

        for (const auto& entry : containers_) {
            std::cout
                << std::left << std::setw(22)
                << entry.first
                << toString(entry.second->state())
                << "\n";
        }
    }
};

// ============================================================
// 10. WORKFLOW
// ============================================================

void demonstrateDockerWorkflow() {
    DockerArchitecture::display();

    auto image = std::make_shared<DockerImage>(
        "training/web-api",
        "1.0.0",
        std::vector<ImageLayer>{
            {"layer-001", "FROM python:3.13-slim", 45.0},
            {"layer-002", "RUN install dependencies", 18.0},
            {"layer-003", "COPY application", 4.0}
        },
        ImageOrigin::Built
    );

    std::cout << "\nIMAGE DETAILS\n";
    std::cout << "Reference: " << image->reference() << "\n";
    std::cout << "Layers: " << image->layerCount() << "\n";
    std::cout << "Size: " << image->sizeMB() << " MB\n";

    ImageRegistry registry("registry.example.com");

    registry.login("developer");

    const std::string remoteReference =
        registry.push(image, "developer");

    std::cout << "\nREGISTRY PUSH\n"
              << remoteReference << "\n";

    DockerEngine engine(
        ResourcePolicy(2.0, 1024, 10)
    );

    engine.imageStore().add(
        registry.pull(remoteReference)
    );

    ContainerConfiguration configuration;

    configuration.name = "production-api";
    configuration.cpu = 1.5;
    configuration.memoryMB = 768;

    configuration.ports = {
        {8080, 8000},
        {8443, 443}
    };

    configuration.volumes = {
        {"/srv/application", "/app/data"},
        {"/srv/logs", "/app/logs"}
    };

    configuration.environment = {
        {"APP_ENV", "production"},
        {"LOG_LEVEL", "info"}
    };

    const std::string name = engine.createContainer(
        configuration,
        image->reference()
    );

    auto& container = engine.getContainer(name);

    std::cout << "\nCONTAINER LIFECYCLE\n";

    container.start();
    container.pause();
    container.unpause();
    container.restart();
    container.stop();
    container.start();

    std::cout << "\nCONTAINER INSPECTION\n";
    std::cout << container.inspect();

    engine.imageStore().display();
    engine.displayContainers();

    std::cout << "\nREGISTRY IMAGE COUNT: "
              << registry.imageCount() << "\n";

    try {
        ContainerConfiguration invalid = configuration;
        invalid.name = "unauthorized-resource";
        invalid.cpu = 10;

        engine.createContainer(
            invalid,
            image->reference()
        );
    } catch (const std::exception& error) {
        std::cout
            << "\nEXPECTED POLICY FAILURE: "
            << error.what() << "\n";
    }

    try {
        container.pause();
    } catch (const std::exception& error) {
        std::cout
            << "\nEXPECTED STATE FAILURE: "
            << error.what() << "\n";
    }

    try {
        registry.push(image, "unknown-user");
    } catch (const std::exception& error) {
        std::cout
            << "\nEXPECTED REGISTRY FAILURE: "
            << error.what() << "\n";
    }
}

// ============================================================
// 11. TESTS
// ============================================================

void runTests() {
    auto image = std::make_shared<DockerImage>(
        "test/application",
        "1.0",
        std::vector<ImageLayer>{
            {"base", "FROM scratch", 10}
        },
        ImageOrigin::Built
    );

    DockerEngine engine(ResourcePolicy(2, 1024, 5));

    engine.imageStore().add(image);

    ContainerConfiguration configuration;
    configuration.name = "test-container";
    configuration.cpu = 1;
    configuration.memoryMB = 256;
    configuration.ports = {{8080, 80}};

    engine.createContainer(
        configuration,
        image->reference()
    );

    auto& container = engine.getContainer("test-container");

    container.start();

    if (container.state() != ContainerState::Running) {
        throw std::runtime_error("Start test failed");
    }

    container.pause();

    if (container.state() != ContainerState::Paused) {
        throw std::runtime_error("Pause test failed");
    }

    container.unpause();
    container.stop();
    container.start();

    bool rejected = false;

    try {
        container.pause();
        container.pause();
    } catch (const std::runtime_error&) {
        rejected = true;
    }

    if (!rejected) {
        throw std::runtime_error("Invalid transition test failed");
    }

    rejected = false;

    try {
        validatePort(90000);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }

    if (!rejected) {
        throw std::runtime_error("Port validation test failed");
    }

    rejected = false;

    try {
        ContainerConfiguration invalid = configuration;
        invalid.name = "excessive";
        invalid.cpu = 5;

        engine.createContainer(
            invalid,
            image->reference()
        );
    } catch (const std::runtime_error&) {
        rejected = true;
    }

    if (!rejected) {
        throw std::runtime_error("Resource policy test failed");
    }

    std::cout << "\nAll C++17 tests passed.\n";
}

// ============================================================
// 12. MAIN
// ============================================================

int main(int argc, char* argv[]) {
    try {
        std::string command = argc > 1 ? argv[1] : "demo";

        if (command == "demo") {
            demonstrateDockerWorkflow();
        } else if (command == "test") {
            runTests();
        } else {
            std::cerr
                << "Usage: docker_lab [demo|test]\n";
            return 2;
        }

        return 0;

    } catch (const std::exception& error) {
        std::cerr
            << "Execution failed: "
            << error.what() << "\n";

        return 1;
    }
}
