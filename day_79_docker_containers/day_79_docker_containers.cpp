#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

/*
 * Docker Container Governance and Lifecycle Engine
 *
 * C++17 implementation of:
 * - Container domain modeling
 * - Lifecycle state transitions
 * - Network and volume management
 * - Environment configuration
 * - Resource constraints
 * - Deployment validation
 * - Health evaluation
 * - Container execution simulation
 * - Merge-like deployment eligibility decisions
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra docker_engine.cpp -o docker_engine
 *
 * Run:
 * ./docker_engine
 */

enum class ContainerState {
    Created,
    Running,
    Paused,
    Restarting,
    Exited,
    Dead
};

enum class NetworkDriver {
    Bridge,
    Host,
    None,
    Overlay
};

enum class RestartPolicy {
    No,
    Always,
    UnlessStopped,
    OnFailure
};

enum class CheckStatus {
    Pending,
    Passed,
    Failed
};

string toString(ContainerState state) {
    switch (state) {
        case ContainerState::Created: return "CREATED";
        case ContainerState::Running: return "RUNNING";
        case ContainerState::Paused: return "PAUSED";
        case ContainerState::Restarting: return "RESTARTING";
        case ContainerState::Exited: return "EXITED";
        case ContainerState::Dead: return "DEAD";
    }

    return "UNKNOWN";
}

class ContainerException : public runtime_error {
public:
    explicit ContainerException(const string& message)
        : runtime_error(message) {}
};

struct PortMapping {
    int hostPort;
    int containerPort;
    string protocol = "tcp";

    void validate() const {
        if (hostPort < 1 || hostPort > 65535 ||
            containerPort < 1 || containerPort > 65535) {
            throw ContainerException("Invalid port mapping.");
        }

        if (protocol != "tcp" && protocol != "udp") {
            throw ContainerException("Unsupported protocol.");
        }
    }
};

struct ResourceLimits {
    double cpuCores = 0.5;
    long long memoryBytes = 128LL * 1024 * 1024;

    void validate() const {
        if (!isfinite(cpuCores) || cpuCores <= 0 || cpuCores > 256) {
            throw ContainerException("Invalid CPU allocation.");
        }

        if (memoryBytes < 16LL * 1024 * 1024) {
            throw ContainerException("Memory allocation is too small.");
        }
    }
};

struct Volume {
    string source;
    string destination;
    bool readOnly = false;

    void validate() const {
        if (source.empty() || destination.empty()) {
            throw ContainerException("Volume paths cannot be empty.");
        }

        if (destination.front() != '/') {
            throw ContainerException(
                "Container volume destination must be absolute."
            );
        }

        if (destination.find("..") != string::npos) {
            throw ContainerException("Unsafe volume destination.");
        }
    }
};

struct Network {
    string name;
    NetworkDriver driver = NetworkDriver::Bridge;
    set<string> attachedContainers;
};

struct Environment {
    map<string, string> variables;

    void set(const string& key, const string& value) {
        if (key.empty() ||
            !(isalpha(static_cast<unsigned char>(key[0])) ||
              key[0] == '_')) {
            throw ContainerException("Invalid environment variable name.");
        }

        for (char ch : key) {
            if (!(isalnum(static_cast<unsigned char>(ch)) || ch == '_')) {
                throw ContainerException("Invalid environment key.");
            }
        }

        if (value.find('\0') != string::npos) {
            throw ContainerException("NUL character is not permitted.");
        }

        variables[key] = value;
    }
};

struct HealthCheck {
    CheckStatus status = CheckStatus::Pending;
    int retries = 3;
    int failures = 0;

    bool evaluate(bool successful) {
        if (successful) {
            status = CheckStatus::Passed;
            failures = 0;
            return true;
        }

        failures++;

        if (failures >= retries) {
            status = CheckStatus::Failed;
        }

        return false;
    }
};

struct Container {
    string id;
    string name;
    string image;
    vector<string> command;

    ContainerState state = ContainerState::Created;

    Environment environment;
    vector<PortMapping> ports;
    vector<Volume> volumes;

    optional<string> networkName;

    ResourceLimits limits;
    RestartPolicy restartPolicy = RestartPolicy::UnlessStopped;

    HealthCheck health;

    chrono::system_clock::time_point createdAt =
        chrono::system_clock::now();

    bool privileged = false;
    bool readOnlyRootFilesystem = true;

    void validate() const {
        if (name.empty() || name.size() > 128) {
            throw ContainerException("Invalid container name.");
        }

        for (char ch : name) {
            if (!(isalnum(static_cast<unsigned char>(ch)) ||
                  ch == '-' || ch == '_' || ch == '.')) {
                throw ContainerException("Invalid container name.");
            }
        }

        if (image.empty() || image.front() == '-') {
            throw ContainerException("Image reference is required.");
        }

        limits.validate();

        set<int> hostPorts;

        for (const auto& port : ports) {
            port.validate();

            if (!hostPorts.insert(port.hostPort).second) {
                throw ContainerException("Duplicate host port.");
            }
        }

        for (const auto& volume : volumes) {
            volume.validate();
        }

        if (privileged) {
            throw ContainerException(
                "Privileged containers are prohibited by default."
            );
        }
    }

    bool transition(ContainerState next) {
        bool allowed = false;

        switch (state) {
            case ContainerState::Created:
                allowed = next == ContainerState::Running ||
                          next == ContainerState::Exited ||
                          next == ContainerState::Dead;
                break;

            case ContainerState::Running:
                allowed = next == ContainerState::Paused ||
                          next == ContainerState::Restarting ||
                          next == ContainerState::Exited ||
                          next == ContainerState::Dead;
                break;

            case ContainerState::Paused:
                allowed = next == ContainerState::Running ||
                          next == ContainerState::Exited ||
                          next == ContainerState::Dead;
                break;

            case ContainerState::Restarting:
                allowed = next == ContainerState::Running ||
                          next == ContainerState::Exited ||
                          next == ContainerState::Dead;
                break;

            case ContainerState::Exited:
                allowed = next == ContainerState::Running ||
                          next == ContainerState::Dead;
                break;

            case ContainerState::Dead:
                allowed = false;
                break;
        }

        if (!allowed) {
            throw ContainerException(
                "Invalid lifecycle transition: " +
                toString(state) + " -> " + toString(next)
            );
        }

        state = next;
        return true;
    }
};

struct DeploymentResult {
    bool eligible = false;
    vector<string> errors;
    vector<string> warnings;
};

class Repository {
private:
    map<string, Container> containers;
    map<string, Network> networks;
    set<string> volumes;

public:
    void createNetwork(const Network& network) {
        if (network.name.empty()) {
            throw ContainerException("Network name is required.");
        }

        if (networks.count(network.name)) {
            throw ContainerException("Network already exists.");
        }

        networks.emplace(network.name, network);
    }

    void createVolume(const string& name) {
        if (name.empty()) {
            throw ContainerException("Volume name is required.");
        }

        if (!volumes.insert(name).second) {
            throw ContainerException("Volume already exists.");
        }
    }

    void deploy(Container container) {
        container.validate();

        if (containers.count(container.name)) {
            throw ContainerException("Container already exists.");
        }

        if (container.networkName &&
            !networks.count(*container.networkName)) {
            throw ContainerException("Requested network does not exist.");
        }

        container.transition(ContainerState::Running);

        if (container.networkName) {
            networks[*container.networkName]
                .attachedContainers.insert(container.name);
        }

        containers.emplace(container.name, std::move(container));
    }

    Container& get(const string& name) {
        auto iterator = containers.find(name);

        if (iterator == containers.end()) {
            throw ContainerException("Container not found: " + name);
        }

        return iterator->second;
    }

    const Container& get(const string& name) const {
        auto iterator = containers.find(name);

        if (iterator == containers.end()) {
            throw ContainerException("Container not found: " + name);
        }

        return iterator->second;
    }

    void stop(const string& name) {
        auto& container = get(name);
        container.transition(ContainerState::Exited);

        if (container.networkName) {
            networks[*container.networkName]
                .attachedContainers.erase(name);
        }
    }

    void start(const string& name) {
        auto& container = get(name);

        if (container.networkName &&
            !networks[*container.networkName]
                .attachedContainers.count(name)) {
            networks[*container.networkName]
                .attachedContainers.insert(name);
        }

        container.transition(ContainerState::Running);
    }

    void pause(const string& name) {
        get(name).transition(ContainerState::Paused);
    }

    void unpause(const string& name) {
        get(name).transition(ContainerState::Running);
    }

    void restart(const string& name) {
        auto& container = get(name);

        if (container.state == ContainerState::Running) {
            container.transition(ContainerState::Restarting);
        } else if (container.state == ContainerState::Exited) {
            container.transition(ContainerState::Running);
            return;
        } else {
            throw ContainerException(
                "Container cannot restart from current state."
            );
        }

        container.transition(ContainerState::Running);
    }

    void remove(const string& name) {
        auto iterator = containers.find(name);

        if (iterator == containers.end()) {
            throw ContainerException("Container does not exist.");
        }

        if (iterator->second.state == ContainerState::Running ||
            iterator->second.state == ContainerState::Paused) {
            throw ContainerException(
                "Stop the container before removing it."
            );
        }

        if (iterator->second.networkName) {
            networks[*iterator->second.networkName]
                .attachedContainers.erase(name);
        }

        containers.erase(iterator);
    }

    DeploymentResult evaluate(const string& name) const {
        const Container& container = get(name);
        DeploymentResult result;

        if (container.state != ContainerState::Running) {
            result.errors.push_back("Container is not running.");
        }

        if (container.health.status == CheckStatus::Failed) {
            result.errors.push_back("Health check has failed.");
        }

        if (container.privileged) {
            result.errors.push_back("Privileged mode is prohibited.");
        }

        if (!container.readOnlyRootFilesystem) {
            result.warnings.push_back(
                "Root filesystem is writable."
            );
        }

        if (container.health.status == CheckStatus::Pending) {
            result.warnings.push_back(
                "Health status has not been established."
            );
        }

        result.eligible = result.errors.empty();
        return result;
    }

    void printInventory() const {
        cout << "\nCONTAINER INVENTORY\n";
        cout << left
             << setw(25) << "NAME"
             << setw(20) << "IMAGE"
             << setw(15) << "STATE"
             << setw(12) << "CPU"
             << "MEMORY\n";

        cout << string(85, '-') << '\n';

        for (const auto& [name, container] : containers) {
            cout << left
                 << setw(25) << name
                 << setw(20) << container.image
                 << setw(15) << toString(container.state)
                 << setw(12) << container.limits.cpuCores
                 << container.limits.memoryBytes / (1024 * 1024)
                 << " MB\n";
        }
    }
};

Container makeWebContainer() {
    Container container;

    container.id = "ctr-001";
    container.name = "web-nginx";
    container.image = "nginx:alpine";

    container.environment.set("APP_ENV", "production");
    container.environment.set("APP_PORT", "80");

    container.ports.push_back({8080, 80, "tcp"});

    container.volumes.push_back({
        "nginx-data",
        "/usr/share/nginx/html",
        true
    });

    container.networkName = "application-network";

    container.limits.cpuCores = 0.5;
    container.limits.memoryBytes = 128LL * 1024 * 1024;

    container.readOnlyRootFilesystem = true;
    container.privileged = false;

    return container;
}

void runTests() {
    Container container = makeWebContainer();
    container.validate();

    container.transition(ContainerState::Running);
    container.transition(ContainerState::Paused);
    container.transition(ContainerState::Running);

    bool rejected = false;

    try {
        container.transition(ContainerState::Created);
    } catch (const ContainerException&) {
        rejected = true;
    }

    if (!rejected) {
        throw ContainerException(
            "Invalid lifecycle transition was accepted."
        );
    }

    Environment environment;
    rejected = false;

    try {
        environment.set("INVALID-KEY", "value");
    } catch (const ContainerException&) {
        rejected = true;
    }

    if (!rejected) {
        throw ContainerException("Invalid environment key was accepted.");
    }

    cout << "All C++ validation tests passed.\n";
}

int main() {
    try {
        runTests();

        Repository repository;

        repository.createNetwork({
            "application-network",
            NetworkDriver::Bridge,
            {}
        });

        repository.createVolume("nginx-data");

        Container web = makeWebContainer();

        repository.deploy(web);

        cout << "\nContainer deployed successfully.\n";

        repository.printInventory();

        const auto decision = repository.evaluate("web-nginx");

        cout << "\nDEPLOYMENT ELIGIBILITY\n";
        cout << "Eligible: "
             << (decision.eligible ? "YES" : "NO")
             << '\n';

        for (const auto& error : decision.errors) {
            cout << "ERROR: " << error << '\n';
        }

        for (const auto& warning : decision.warnings) {
            cout << "WARNING: " << warning << '\n';
        }

        cout << "\nPausing container...\n";
        repository.pause("web-nginx");

        cout << "Resuming container...\n";
        repository.unpause("web-nginx");

        cout << "Restarting container...\n";
        repository.restart("web-nginx");

        cout << "Stopping container...\n";
        repository.stop("web-nginx");

        cout << "Removing container...\n";
        repository.remove("web-nginx");

        cout << "\nFinal inventory:\n";
        repository.printInventory();

    } catch (const exception& exception) {
        cerr << "ERROR: " << exception.what() << '\n';
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
