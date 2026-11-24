#include <algorithm>
#include <chrono>
#include <functional>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include <queue>
#include <sstream>
#include <iomanip>

using namespace std;

enum class ServiceType {
    Frontend,
    Backend,
    Database,
    Cache,
    Worker
};

enum class ServiceStatus {
    Stopped,
    Starting,
    Running,
    Healthy,
    Unhealthy,
    Failed
};

enum class NetworkType {
    Public,
    Internal
};

struct Service {
    string name;
    ServiceType type;
    int containerPort;
    bool persistent;
    ServiceStatus status;
    NetworkType network;

    vector<string> dependencies;
    vector<string> healthChecks;
};

struct Volume {
    string name;
    string mountPath;
    bool persistent;
};

struct PortMapping {
    string service;
    int hostPort;
    int containerPort;
};

class ValidationError : public runtime_error {
public:
    explicit ValidationError(const string& message)
        : runtime_error(message) {}
};

class DockerTopology {
private:
    map<string, Service> services;
    vector<Volume> volumes;
    vector<PortMapping> ports;

    static bool validPort(int port) {
        return port >= 1 && port <= 65535;
    }

public:
    void addService(const Service& service) {
        if (service.name.empty()) {
            throw ValidationError("Service name cannot be empty.");
        }

        if (!validPort(service.containerPort)) {
            throw ValidationError("Invalid container port.");
        }

        if (services.count(service.name)) {
            throw ValidationError(
                "Duplicate service: " + service.name
            );
        }

        services.emplace(service.name, service);
    }

    void addVolume(const Volume& volume) {
        if (volume.name.empty() || volume.mountPath.empty()) {
            throw ValidationError("Invalid volume definition.");
        }

        auto existing = find_if(
            volumes.begin(),
            volumes.end(),
            [&](const Volume& item) {
                return item.name == volume.name;
            }
        );

        if (existing != volumes.end()) {
            throw ValidationError("Duplicate volume.");
        }

        volumes.push_back(volume);
    }

    void addPortMapping(const PortMapping& mapping) {
        if (!services.count(mapping.service)) {
            throw ValidationError("Unknown service in port mapping.");
        }

        if (!validPort(mapping.hostPort) ||
            !validPort(mapping.containerPort)) {
            throw ValidationError("Invalid port mapping.");
        }

        for (const auto& existing : ports) {
            if (existing.hostPort == mapping.hostPort) {
                throw ValidationError(
                    "Host port collision: " +
                    to_string(mapping.hostPort)
                );
            }
        }

        ports.push_back(mapping);
    }

    vector<string> dependencyOrder() const {
        map<string, int> indegree;
        map<string, vector<string>> adjacency;

        for (const auto& [name, service] : services) {
            indegree[name] = 0;
        }

        for (const auto& [name, service] : services) {
            for (const auto& dependency : service.dependencies) {
                if (!services.count(dependency)) {
                    throw ValidationError(
                        "Missing dependency: " + dependency
                    );
                }

                adjacency[dependency].push_back(name);
                indegree[name]++;
            }
        }

        queue<string> ready;

        for (const auto& [name, degree] : indegree) {
            if (degree == 0) {
                ready.push(name);
            }
        }

        vector<string> result;

        while (!ready.empty()) {
            string current = ready.front();
            ready.pop();

            result.push_back(current);

            for (const auto& dependent : adjacency[current]) {
                if (--indegree[dependent] == 0) {
                    ready.push(dependent);
                }
            }
        }

        if (result.size() != services.size()) {
            throw ValidationError(
                "Circular service dependency detected."
            );
        }

        return result;
    }

    void validateNetworkIsolation() const {
        for (const auto& [name, service] : services) {
            if (
                service.type == ServiceType::Database &&
                service.network == NetworkType::Public
            ) {
                throw ValidationError(
                    "Database must not be directly exposed "
                    "on the public application network."
                );
            }
        }
    }

    void validatePersistence() const {
        bool databaseHasVolume = false;

        for (const auto& volume : volumes) {
            if (
                volume.persistent &&
                volume.mountPath == "/var/lib/postgresql/data"
            ) {
                databaseHasVolume = true;
            }
        }

        for (const auto& [name, service] : services) {
            if (
                service.type == ServiceType::Database &&
                service.persistent &&
                !databaseHasVolume
            ) {
                throw ValidationError(
                    "Persistent database has no persistent volume."
                );
            }
        }
    }

    void validateHealthChecks() const {
        for (const auto& [name, service] : services) {
            if (
                service.status != ServiceStatus::Stopped &&
                service.healthChecks.empty()
            ) {
                throw ValidationError(
                    "Missing health check for service: " + name
                );
            }
        }
    }

    void validate() const {
        dependencyOrder();
        validateNetworkIsolation();
        validatePersistence();
        validateHealthChecks();
    }

    void printTopology() const {
        cout << "\nDOCKER PROJECT TOPOLOGY\n";
        cout << "=======================\n";

        for (const auto& [name, service] : services) {
            cout << "\nService: " << name
                 << "\nContainer port: " << service.containerPort
                 << "\nPersistent: "
                 << (service.persistent ? "Yes" : "No")
                 << "\nDependencies: ";

            if (service.dependencies.empty()) {
                cout << "None";
            } else {
                for (const auto& dependency : service.dependencies) {
                    cout << dependency << " ";
                }
            }

            cout << "\nHealth checks: ";

            for (const auto& check : service.healthChecks) {
                cout << check << " ";
            }

            cout << "\n";
        }

        cout << "\nPersistent volumes: " << volumes.size() << "\n";

        for (const auto& volume : volumes) {
            cout << volume.name
                 << " -> " << volume.mountPath << "\n";
        }

        cout << "\nStartup order:\n";

        for (const auto& service : dependencyOrder()) {
            cout << service << "\n";
        }
    }
};

class DeploymentEngine {
private:
    DockerTopology& topology;

    map<string, ServiceStatus> runtimeState;

public:
    explicit DeploymentEngine(DockerTopology& topology)
        : topology(topology) {}

    void initialize() {
        topology.validate();

        for (const string& name : topology.dependencyOrder()) {
            runtimeState[name] = ServiceStatus::Stopped;
        }
    }

    bool dependenciesHealthy(const Service& service) const {
        for (const auto& dependency : service.dependencies) {
            auto found = runtimeState.find(dependency);

            if (
                found == runtimeState.end() ||
                found->second != ServiceStatus::Healthy
            ) {
                return false;
            }
        }

        return true;
    }

    void transition(
        const string& service,
        ServiceStatus newStatus
    ) {
        if (!runtimeState.count(service)) {
            throw ValidationError("Unknown service transition.");
        }

        ServiceStatus current = runtimeState.at(service);

        if (
            newStatus == ServiceStatus::Healthy &&
            current != ServiceStatus::Running
        ) {
            throw ValidationError(
                "Only a running service can become healthy."
            );
        }

        if (
            newStatus == ServiceStatus::Running &&
            current != ServiceStatus::Starting
        ) {
            throw ValidationError(
                "Service must be starting before running."
            );
        }

        if (
            newStatus == ServiceStatus::Starting &&
            current != ServiceStatus::Stopped &&
            current != ServiceStatus::Failed
        ) {
            throw ValidationError(
                "Invalid service startup transition."
            );
        }

        runtimeState[service] = newStatus;
    }

    void deploy() {
        const auto order = topology.dependencyOrder();

        cout << "\nDEPLOYMENT EXECUTION\n";

        for (const auto& name : order) {
            if (runtimeState[name] == ServiceStatus::Healthy) {
                cout << name << " already healthy.\n";
                continue;
            }

            const Service& service = getService(name);

            if (!dependenciesHealthy(service)) {
                runtimeState[name] = ServiceStatus::Failed;

                throw ValidationError(
                    "Dependencies are not healthy for " + name
                );
            }

            transition(name, ServiceStatus::Starting);
            cout << "Starting " << name << "...\n";

            transition(name, ServiceStatus::Running);

            // Simulated health-check result.
            transition(name, ServiceStatus::Healthy);

            cout << name << " is healthy.\n";
        }
    }

    const Service& getService(const string& name) const {
        // Topology is deliberately modeled as immutable after initialization.
        // This method retrieves the matching service through a validated lookup.
        const auto order = topology.dependencyOrder();
        if (find(order.begin(), order.end(), name) == order.end()) {
            throw ValidationError("Service not found.");
        }

        // Runtime demonstration uses a local topology lookup interface.
        return serviceCache.at(name);
    }

    void registerService(const Service& service) {
        serviceCache[service.name] = service;
    }

    void report() const {
        cout << "\nRUNTIME STATUS\n";

        for (const auto& [name, state] : runtimeState) {
            string value;

            switch (state) {
                case ServiceStatus::Stopped: value = "STOPPED"; break;
                case ServiceStatus::Starting: value = "STARTING"; break;
                case ServiceStatus::Running: value = "RUNNING"; break;
                case ServiceStatus::Healthy: value = "HEALTHY"; break;
                case ServiceStatus::Unhealthy: value = "UNHEALTHY"; break;
                case ServiceStatus::Failed: value = "FAILED"; break;
            }

            cout << left << setw(15) << name << value << "\n";
        }
    }

private:
    map<string, Service> serviceCache;
};

int main() {
    try {
        DockerTopology topology;

        topology.addService({
            "database",
            ServiceType::Database,
            5432,
            true,
            ServiceStatus::Stopped,
            NetworkType::Internal,
            {},
            {"pg_isready"}
        });

        topology.addService({
            "backend",
            ServiceType::Backend,
            8000,
            false,
            ServiceStatus::Stopped,
            NetworkType::Internal,
            {"database"},
            {"/health"}
        });

        topology.addService({
            "frontend",
            ServiceType::Frontend,
            3000,
            false,
            ServiceStatus::Stopped,
            NetworkType::Public,
            {"backend"},
            {"/"}
        });

        topology.addVolume({
            "postgres_data",
            "/var/lib/postgresql/data",
            true
        });

        topology.addPortMapping({
            "frontend", 3000, 3000
        });

        topology.addPortMapping({
            "backend", 8000, 8000
        });

        topology.validate();
        topology.printTopology();

        DeploymentEngine engine(topology);

        for (const auto& name : topology.dependencyOrder()) {
            if (name == "database") {
                engine.registerService({
                    name,
                    ServiceType::Database,
                    5432,
                    true,
                    ServiceStatus::Stopped,
                    NetworkType::Internal,
                    {},
                    {"pg_isready"}
                });
            } else if (name == "backend") {
                engine.registerService({
                    name,
                    ServiceType::Backend,
                    8000,
                    false,
                    ServiceStatus::Stopped,
                    NetworkType::Internal,
                    {"database"},
                    {"/health"}
                });
            } else {
                engine.registerService({
                    name,
                    ServiceType::Frontend,
                    3000,
                    false,
                    ServiceStatus::Stopped,
                    NetworkType::Public,
                    {"backend"},
                    {"/"}
                });
            }
        }

        engine.initialize();
        engine.deploy();
        engine.report();

    } catch (const exception& error) {
        cerr << "DEPLOYMENT ERROR: "
             << error.what() << "\n";

        return 1;
    }

    return 0;
}
