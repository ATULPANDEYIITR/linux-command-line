#include <algorithm>
#include <cctype>
#include <functional>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

/*
 * Docker Compose repository deployment and governance engine.
 *
 * Models:
 * - Projects and services
 * - Dependency conditions
 * - Networks, ports, and volumes
 * - Service lifecycle
 * - Health checks
 * - Restart policies
 * - Deployment eligibility
 * - Failure recovery
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic compose.cpp -o compose
 */

enum class State {
    Created,
    Starting,
    Running,
    Healthy,
    Unhealthy,
    Failed,
    Stopped
};

enum class Condition {
    Started,
    Healthy,
    CompletedSuccessfully
};

enum class RestartPolicy {
    No,
    Always,
    OnFailure,
    UnlessStopped
};

string toString(State state) {
    switch (state) {
        case State::Created: return "created";
        case State::Starting: return "starting";
        case State::Running: return "running";
        case State::Healthy: return "healthy";
        case State::Unhealthy: return "unhealthy";
        case State::Failed: return "failed";
        case State::Stopped: return "stopped";
    }
    return "unknown";
}

string toString(Condition condition) {
    switch (condition) {
        case Condition::Started: return "service_started";
        case Condition::Healthy: return "service_healthy";
        case Condition::CompletedSuccessfully:
            return "service_completed_successfully";
    }
    return "unknown";
}

struct Port {
    int host;
    int container;
    string protocol = "tcp";

    void validate() const {
        if (host < 1 || host > 65535 ||
            container < 1 || container > 65535) {
            throw invalid_argument("Invalid port mapping");
        }

        if (protocol != "tcp" && protocol != "udp") {
            throw invalid_argument("Invalid port protocol");
        }
    }
};

struct Volume {
    string source;
    string target;
    bool readOnly = false;

    void validate() const {
        if (source.empty() || target.empty() ||
            target.front() != '/' ||
            target.find("/../") != string::npos ||
            target.find("/..") == target.size() - 3) {
            throw invalid_argument("Invalid volume mapping");
        }
    }
};

struct Dependency {
    string service;
    Condition condition = Condition::Started;
};

struct HealthCheck {
    string command;
    int intervalSeconds = 10;
    int retries = 3;

    void validate() const {
        if (command.empty() ||
            intervalSeconds < 1 ||
            retries < 1) {
            throw invalid_argument("Invalid health check");
        }
    }
};

struct ServiceConfig {
    string name;
    string image;
    string command;

    vector<Port> ports;
    vector<Volume> volumes;
    vector<Dependency> dependencies;

    set<string> networks;

    RestartPolicy restart = RestartPolicy::No;
    int replicas = 1;

    bool hasHealthCheck = false;
    HealthCheck healthCheck;
};

struct Runtime {
    ServiceConfig config;
    State state = State::Created;
    int attempts = 0;
    string error;
};

struct Event {
    string service;
    string action;
    string detail;
};

class ComposeEngine {
private:
    string projectName;

    unordered_map<string, Runtime> services;
    set<string> networks;
    set<string> volumes;
    vector<Event> events;

    bool manuallyStopped = false;

    void log(
        const string& service,
        const string& action,
        const string& detail = ""
    ) {
        events.push_back({service, action, detail});
    }

    bool dependencySatisfied(const Dependency& dependency) const {
        auto it = services.find(dependency.service);

        if (it == services.end()) {
            return false;
        }

        State state = it->second.state;

        switch (dependency.condition) {
            case Condition::Started:
                return state == State::Running ||
                       state == State::Healthy;

            case Condition::Healthy:
                return state == State::Healthy;

            case Condition::CompletedSuccessfully:
                return state == State::Stopped;
        }

        return false;
    }

public:
    ComposeEngine(
        string name,
        vector<ServiceConfig> configurations,
        set<string> projectNetworks,
        set<string> projectVolumes
    )
        : projectName(std::move(name)),
          networks(std::move(projectNetworks)),
          volumes(std::move(projectVolumes)) {

        if (projectName.empty()) {
            throw invalid_argument("Project name is required");
        }

        for (auto& config : configurations) {
            if (config.name.empty() || config.image.empty()) {
                throw invalid_argument(
                    "Service name and image are required"
                );
            }

            if (config.replicas < 1) {
                throw invalid_argument("Invalid replica count");
            }

            if (services.count(config.name)) {
                throw invalid_argument("Duplicate service name");
            }

            for (const auto& port : config.ports) {
                port.validate();
            }

            for (const auto& volume : config.volumes) {
                volume.validate();

                if (volumes.count(volume.source) == 0) {
                    throw invalid_argument(
                        "Undefined named volume: " + volume.source
                    );
                }
            }

            for (const auto& network : config.networks) {
                if (networks.count(network) == 0) {
                    throw invalid_argument(
                        "Undefined network: " + network
                    );
                }
            }

            if (config.hasHealthCheck) {
                config.healthCheck.validate();
            }

            services.emplace(
                config.name,
                Runtime{std::move(config)}
            );
        }

        if (services.empty()) {
            throw invalid_argument("No services configured");
        }

        validatePorts();

        for (const auto& [name, runtime] : services) {
            for (const auto& dependency :
                 runtime.config.dependencies) {

                if (services.count(dependency.service) == 0) {
                    throw invalid_argument(
                        name + " depends on missing service " +
                        dependency.service
                    );
                }

                if (name == dependency.service) {
                    throw invalid_argument(
                        "Self dependency detected"
                    );
                }
            }
        }

        startupOrder();
    }

    void validatePorts() const {
        set<pair<int, string>> occupied;

        for (const auto& [name, runtime] : services) {
            for (const auto& port : runtime.config.ports) {
                auto key = make_pair(port.host, port.protocol);

                if (!occupied.insert(key).second) {
                    throw invalid_argument(
                        "Host port collision on " +
                        to_string(port.host)
                    );
                }
            }
        }
    }

    /*
     * Topological sorting.
     * Time complexity: O(V + E).
     */
    vector<string> startupOrder() const {
        map<string, int> indegree;
        map<string, vector<string>> children;

        for (const auto& [name, runtime] : services) {
            indegree[name] = 0;
        }

        for (const auto& [name, runtime] : services) {
            for (const auto& dependency :
                 runtime.config.dependencies) {
                indegree[name]++;
                children[dependency.service].push_back(name);
            }
        }

        vector<string> ready;

        for (const auto& [name, degree] : indegree) {
            if (degree == 0) {
                ready.push_back(name);
            }
        }

        vector<string> result;

        while (!ready.empty()) {
            string current = ready.back();
            ready.pop_back();

            result.push_back(current);

            for (const string& child : children[current]) {
                indegree[child]--;

                if (indegree[child] == 0) {
                    ready.push_back(child);
                }
            }
        }

        if (result.size() != services.size()) {
            throw runtime_error(
                "Circular dependency detected"
            );
        }

        return result;
    }

    void startService(const string& name) {
        auto it = services.find(name);

        if (it == services.end()) {
            throw runtime_error("Unknown service: " + name);
        }

        Runtime& runtime = it->second;

        if (runtime.state == State::Running ||
            runtime.state == State::Healthy) {
            return;
        }

        for (const auto& dependency :
             runtime.config.dependencies) {
            if (!dependencySatisfied(dependency)) {
                throw runtime_error(
                    name + " cannot start because " +
                    dependency.service + " has not satisfied " +
                    toString(dependency.condition)
                );
            }
        }

        runtime.state = State::Starting;
        runtime.attempts++;

        log(name, "starting", runtime.config.image);

        /*
         * This is a deterministic simulation.
         * Actual container creation and health checks
         * require communication with Docker Engine.
         */
        runtime.state = runtime.config.hasHealthCheck
            ? State::Healthy
            : State::Running;

        runtime.error.clear();

        log(name, "started", toString(runtime.state));
    }

    void up() {
        manuallyStopped = false;
        log(projectName, "deployment-started");

        for (const string& name : startupOrder()) {
            try {
                startService(name);
            } catch (const exception& error) {
                Runtime& runtime = services.at(name);
                runtime.state = State::Failed;
                runtime.error = error.what();

                log(name, "failed", error.what());

                throw;
            }
        }

        log(projectName, "deployment-completed");
    }

    void stopService(const string& name) {
        auto it = services.find(name);

        if (it == services.end()) {
            throw runtime_error("Unknown service: " + name);
        }

        it->second.state = State::Stopped;
        log(name, "stopped");
    }

    void down() {
        manuallyStopped = true;

        vector<string> order = startupOrder();
        reverse(order.begin(), order.end());

        for (const string& name : order) {
            stopService(name);
        }

        log(projectName, "deployment-stopped");
    }

    bool recover(const string& name, const string& reason) {
        auto it = services.find(name);

        if (it == services.end()) {
            throw runtime_error("Unknown service: " + name);
        }

        Runtime& runtime = it->second;

        runtime.state = State::Failed;
        runtime.error = reason;

        log(name, "failed", reason);

        RestartPolicy policy = runtime.config.restart;

        if (policy == RestartPolicy::No) {
            return false;
        }

        if (policy == RestartPolicy::UnlessStopped &&
            manuallyStopped) {
            return false;
        }

        runtime.state = State::Starting;
        runtime.attempts++;

        runtime.state = runtime.config.hasHealthCheck
            ? State::Healthy
            : State::Running;

        runtime.error.clear();

        log(name, "restarted", toString(runtime.state));

        return true;
    }

    State getState(const string& name) const {
        return services.at(name).state;
    }

    void printReport() const {
        cout << "\nProject: " << projectName << '\n';

        cout << "\nService status\n";

        for (const auto& [name, runtime] : services) {
            cout << name
                 << " | " << toString(runtime.state)
                 << " | attempts=" << runtime.attempts;

            if (!runtime.error.empty()) {
                cout << " | error=" << runtime.error;
            }

            cout << '\n';
        }

        cout << "\nStartup order\n";

        for (const auto& name : startupOrder()) {
            cout << name << '\n';
        }

        cout << "\nEvent history\n";

        for (const auto& event : events) {
            cout << event.service
                 << " | " << event.action
                 << " | " << event.detail << '\n';
        }
    }
};

int main() {
    try {
        ServiceConfig database;
        database.name = "database";
        database.image = "postgres:18";
        database.networks = {"backend"};
        database.volumes = {
            {"database-data", "/var/lib/postgresql/data", false}
        };
        database.hasHealthCheck = true;
        database.healthCheck = {
            "pg_isready", 10, 3
        };
        database.restart = RestartPolicy::UnlessStopped;

        ServiceConfig cache;
        cache.name = "cache";
        cache.image = "redis:8";
        cache.networks = {"backend"};
        cache.hasHealthCheck = true;
        cache.healthCheck = {
            "redis-cli ping", 10, 3
        };
        cache.restart = RestartPolicy::Always;

        ServiceConfig api;
        api.name = "api";
        api.image = "inventory-api:1.0";
        api.networks = {"frontend", "backend"};
        api.ports = {{8000, 8000, "tcp"}};
        api.dependencies = {
            {"database", Condition::Healthy},
            {"cache", Condition::Healthy}
        };
        api.restart = RestartPolicy::OnFailure;
        api.hasHealthCheck = true;
        api.healthCheck = {
            "curl localhost:8000/health", 10, 3
        };

        ServiceConfig web;
        web.name = "web";
        web.image = "inventory-web:1.0";
        web.networks = {"frontend"};
        web.ports = {{8080, 80, "tcp"}};
        web.dependencies = {
            {"api", Condition::Healthy}
        };
        web.restart = RestartPolicy::UnlessStopped;

        ComposeEngine engine(
            "inventory-platform",
            {database, cache, api, web},
            {"frontend", "backend"},
            {"database-data"}
        );

        engine.up();

        if (engine.getState("database") != State::Healthy ||
            engine.getState("api") != State::Healthy ||
            engine.getState("web") != State::Running) {
            throw runtime_error("Unexpected deployment state");
        }

        bool recovered = engine.recover(
            "api",
            "Temporary database connection interruption"
        );

        if (!recovered ||
            engine.getState("api") != State::Healthy) {
            throw runtime_error("API recovery failed");
        }

        engine.printReport();

        engine.down();

        if (engine.getState("web") != State::Stopped) {
            throw runtime_error("Shutdown failed");
        }

        // Validate cycle detection.
        try {
            ServiceConfig first;
            first.name = "first";
            first.image = "first:1";
            first.dependencies = {
                {"second", Condition::Started}
            };

            ServiceConfig second;
            second.name = "second";
            second.image = "second:1";
            second.dependencies = {
                {"first", Condition::Started}
            };

            ComposeEngine invalid(
                "invalid",
                {first, second},
                {},
                {}
            );

            throw runtime_error(
                "Circular dependency was not detected"
            );
        } catch (const runtime_error& error) {
            if (string(error.what()) ==
                "Circular dependency was not detected") {
                throw;
            }
        }

        cout << "\nAll governance engine tests passed.\n";

    } catch (const exception& error) {
        cerr << "Error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
