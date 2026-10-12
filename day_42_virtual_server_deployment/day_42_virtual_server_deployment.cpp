#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Repository-independent infrastructure governance case study:
 * a regional operations team deploys application virtual machines while
 * enforcing resource limits, security rules, lifecycle invariants, and
 * recoverable provider operations.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -Wpedantic virtual_server.cpp -o virtual_server
 *
 * The provider is simulated. IP addresses and costs are illustrative.
 */

enum class State {
    Requested,
    Provisioning,
    Running,
    Stopping,
    Stopped,
    Restarting,
    Terminated,
    Failed
};

enum class Environment {
    Development,
    Staging,
    Production
};

std::string to_string(State state) {
    switch (state) {
        case State::Requested: return "requested";
        case State::Provisioning: return "provisioning";
        case State::Running: return "running";
        case State::Stopping: return "stopping";
        case State::Stopped: return "stopped";
        case State::Restarting: return "restarting";
        case State::Terminated: return "terminated";
        case State::Failed: return "failed";
    }
    throw std::logic_error("Unknown instance state");
}

std::string to_string(Environment environment) {
    switch (environment) {
        case Environment::Development: return "development";
        case Environment::Staging: return "staging";
        case Environment::Production: return "production";
    }
    throw std::logic_error("Unknown environment");
}

class DeploymentError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class PolicyViolation : public DeploymentError {
public:
    using DeploymentError::DeploymentError;
};

class LifecycleViolation : public DeploymentError {
public:
    using DeploymentError::DeploymentError;
};

struct Flavor {
    std::string name;
    int vcpus;
    double memory_gib;
    double hourly_rate;
};

const std::map<std::string, Flavor> FLAVORS = {
    {"small", {"small", 2, 4.0, 0.05}},
    {"medium", {"medium", 4, 16.0, 0.12}},
    {"large", {"large", 8, 32.0, 0.24}}
};

struct NetworkPolicy {
    std::string subnet_id;
    std::vector<std::string> security_groups;
    std::set<int> ingress_ports;
    bool public_ip = false;
};

struct ServerSpec {
    std::string name;
    std::string image_id;
    std::string region;
    std::string flavor;
    Environment environment;
    NetworkPolicy network;
    int root_disk_gib = 30;
    bool encrypted_disk = true;
    bool monitoring_enabled = true;
    std::string owner;
};

struct AuditRecord {
    std::string action;
    State from;
    State to;
    std::string actor;
    std::string detail;
};

struct Instance {
    std::string id;
    ServerSpec spec;
    State state = State::Requested;
    std::optional<std::string> private_ip;
    std::optional<std::string> public_ip;
    std::string health = "unknown";
    unsigned int boot_count = 0;
    std::vector<AuditRecord> audit;
};

class PolicyEngine {
    static bool valid_name(const std::string& name) {
        if (name.size() < 2 || name.size() > 40) return false;
        if (name.front() < 'a' || name.front() > 'z') return false;

        return std::all_of(name.begin(), name.end(), [](unsigned char c) {
            return (c >= 'a' && c <= 'z') ||
                   (c >= '0' && c <= '9') || c == '-';
        }) && name.back() != '-';
    }

public:
    static void validate(const ServerSpec& spec) {
        if (!valid_name(spec.name)) {
            throw PolicyViolation("Invalid instance name: " + spec.name);
        }

        if (FLAVORS.find(spec.flavor) == FLAVORS.end()) {
            throw PolicyViolation("Unsupported compute flavor");
        }

        if (spec.image_id.rfind("img-", 0) != 0 &&
            spec.image_id.rfind("ami-", 0) != 0) {
            throw PolicyViolation("Image must use an img- or ami- identifier");
        }

        if (spec.region.empty() || spec.region.find(' ') != std::string::npos) {
            throw PolicyViolation("Invalid region");
        }

        if (spec.root_disk_gib < 8 || spec.root_disk_gib > 16384) {
            throw PolicyViolation("Root disk is outside the permitted range");
        }

        if (spec.network.subnet_id.rfind("subnet-", 0) != 0) {
            throw PolicyViolation("A valid subnet is required");
        }

        if (spec.network.security_groups.empty()) {
            throw PolicyViolation("At least one security group is required");
        }

        for (const auto& group : spec.network.security_groups) {
            if (group.rfind("sg-", 0) != 0) {
                throw PolicyViolation("Invalid security group: " + group);
            }
        }

        for (int port : spec.network.ingress_ports) {
            if (port < 1 || port > 65535) {
                throw PolicyViolation("Invalid network ingress port");
            }
        }

        if (spec.environment == Environment::Production) {
            if (!spec.encrypted_disk || !spec.monitoring_enabled) {
                throw PolicyViolation(
                    "Production requires encrypted disks and monitoring"
                );
            }
        }

        if (spec.owner.empty()) {
            throw PolicyViolation("Every server must have an accountable owner");
        }
    }

    static bool permits(const Instance& instance, State target) {
        switch (instance.state) {
            case State::Requested:
                return target == State::Provisioning || target == State::Failed;
            case State::Provisioning:
                return target == State::Running || target == State::Failed;
            case State::Running:
                return target == State::Stopping ||
                       target == State::Restarting ||
                       target == State::Terminated ||
                       target == State::Failed;
            case State::Stopping:
                return target == State::Stopped || target == State::Failed;
            case State::Stopped:
                return target == State::Provisioning ||
                       target == State::Terminated ||
                       target == State::Failed;
            case State::Restarting:
                return target == State::Running || target == State::Failed;
            case State::Failed:
                return target == State::Provisioning ||
                       target == State::Terminated;
            case State::Terminated:
                return false;
        }
        return false;
    }
};

class SimulatedProvider {
    unsigned int address_counter_ = 10;
    std::optional<std::string> fail_next_;

    void maybe_fail(const std::string& operation) {
        if (fail_next_ && *fail_next_ == operation) {
            fail_next_.reset();
            throw DeploymentError("Provider operation failed: " + operation);
        }
    }

public:
    void inject_failure(const std::string& operation) {
        fail_next_ = operation;
    }

    void create(Instance& instance) {
        maybe_fail("create");
        instance.private_ip = "10.40.0." + std::to_string(address_counter_);
        ++address_counter_;

        if (instance.spec.network.public_ip) {
            // Documentation-only TEST-NET addresses; no real public address
            // is allocated by this simulator.
            instance.public_ip =
                "198.51.100." + std::to_string(address_counter_++);
        }

        instance.boot_count++;
    }

    void start(Instance& instance) {
        maybe_fail("start");
        if (!instance.private_ip) {
            instance.private_ip =
                "10.40.0." + std::to_string(address_counter_++);
        }
        instance.boot_count++;
    }

    void stop() { maybe_fail("stop"); }
    void restart() { maybe_fail("restart"); }
    void terminate() { maybe_fail("terminate"); }
};

class DeploymentEngine {
    SimulatedProvider provider_;
    std::unordered_map<std::string, Instance> instances_;
    std::unordered_map<std::string, std::string> name_index_;
    unsigned long long next_id_ = 1;

    Instance& find(const std::string& id) {
        auto it = instances_.find(id);
        if (it == instances_.end()) {
            throw DeploymentError("Unknown instance: " + id);
        }
        return it->second;
    }

    void transition(
        Instance& instance,
        State target,
        const std::string& action,
        const std::string& actor,
        const std::string& detail = ""
    ) {
        if (!PolicyEngine::permits(instance, target)) {
            throw LifecycleViolation(
                "Invalid transition " + to_string(instance.state) +
                " -> " + to_string(target)
            );
        }

        State previous = instance.state;
        instance.state = target;
        instance.audit.push_back(
            {action, previous, target, actor, detail}
        );
    }

public:
    Instance& deploy(const ServerSpec& spec) {
        PolicyEngine::validate(spec);

        if (name_index_.count(spec.name)) {
            throw PolicyViolation("Duplicate instance name: " + spec.name);
        }

        Instance instance;
        instance.id = "vm-" + std::to_string(next_id_++);
        instance.spec = spec;

        const std::string id = instance.id;
        name_index_[spec.name] = id;
        auto [iterator, inserted] =
            instances_.emplace(id, std::move(instance));

        if (!inserted) {
            throw DeploymentError("Could not register instance");
        }

        Instance& stored = iterator->second;
        transition(stored, State::Provisioning, "create", "scheduler");

        try {
            provider_.create(stored);
            transition(
                stored, State::Running, "create", "scheduler",
                "Compute resources allocated"
            );
            stored.health = "healthy";
        } catch (const std::exception& error) {
            transition(stored, State::Failed, "create", "scheduler", error.what());
            stored.health = "unhealthy";
            throw;
        }

        return stored;
    }

    void stop(const std::string& id) {
        Instance& instance = find(id);
        if (instance.state != State::Running) {
            throw LifecycleViolation("Only running instances can be stopped");
        }

        transition(instance, State::Stopping, "stop", "operator");
        try {
            provider_.stop();
            transition(instance, State::Stopped, "stop", "operator");
            instance.health = "not-running";
        } catch (const std::exception& error) {
            transition(
                instance, State::Failed, "stop", "operator", error.what()
            );
            instance.health = "unhealthy";
            throw;
        }
    }

    void start(const std::string& id) {
        Instance& instance = find(id);
        if (instance.state != State::Stopped &&
            instance.state != State::Failed) {
            throw LifecycleViolation("Instance is not eligible to start");
        }

        transition(instance, State::Provisioning, "start", "operator");
        try {
            provider_.start(instance);
            transition(instance, State::Running, "start", "operator");
            instance.health = "healthy";
        } catch (const std::exception& error) {
            transition(
                instance, State::Failed, "start", "operator", error.what()
            );
            instance.health = "unhealthy";
            throw;
        }
    }

    void restart(const std::string& id) {
        Instance& instance = find(id);
        if (instance.state != State::Running) {
            throw LifecycleViolation("Only running instances can restart");
        }

        transition(instance, State::Restarting, "restart", "operator");
        try {
            provider_.restart();
            ++instance.boot_count;
            transition(instance, State::Running, "restart", "operator");
            instance.health = "healthy";
        } catch (const std::exception& error) {
            transition(
                instance, State::Failed, "restart", "operator", error.what()
            );
            instance.health = "unhealthy";
            throw;
        }
    }

    void terminate(const std::string& id) {
        Instance& instance = find(id);
        if (instance.state == State::Terminated) {
            throw LifecycleViolation("Instance already terminated");
        }

        try {
            provider_.terminate();
        } catch (const std::exception& error) {
            if (instance.state != State::Failed) {
                transition(
                    instance, State::Failed, "terminate", "operator", error.what()
                );
            }
            throw;
        }

        transition(instance, State::Terminated, "terminate", "operator");
        instance.private_ip.reset();
        instance.public_ip.reset();
        instance.health = "terminated";
    }

    void inject_provider_failure(const std::string& operation) {
        provider_.inject_failure(operation);
    }

    double monthly_compute_estimate(
        const std::string& id,
        double billable_hours = 730.0
    ) {
        if (!std::isfinite(billable_hours) ||
            billable_hours < 0 || billable_hours > 744) {
            throw PolicyViolation("Invalid monthly billable hours");
        }

        const Instance& instance = find(id);
        if (instance.state == State::Terminated) return 0.0;

        const double rate = FLAVORS.at(instance.spec.flavor).hourly_rate;
        return std::round(rate * billable_hours * 100.0) / 100.0;
    }

    void print_inventory() const {
        std::cout << std::left
                  << std::setw(12) << "Instance"
                  << std::setw(18) << "Name"
                  << std::setw(14) << "State"
                  << std::setw(12) << "Flavor"
                  << std::setw(14) << "Private IP"
                  << std::setw(12) << "Health"
                  << '\n';

        for (const auto& [id, instance] : instances_) {
            std::cout << std::left
                      << std::setw(12) << id
                      << std::setw(18) << instance.spec.name
                      << std::setw(14) << to_string(instance.state)
                      << std::setw(12) << instance.spec.flavor
                      << std::setw(14)
                      << instance.private_ip.value_or("none")
                      << std::setw(12) << instance.health
                      << '\n';
        }
    }

    void print_audit(const std::string& id) {
        const Instance& instance = find(id);
        for (const auto& event : instance.audit) {
            std::cout << event.action << ": "
                      << to_string(event.from) << " -> "
                      << to_string(event.to)
                      << " by " << event.actor;

            if (!event.detail.empty()) {
                std::cout << " (" << event.detail << ")";
            }
            std::cout << '\n';
        }
    }
};

ServerSpec make_spec(
    std::string name,
    std::string flavor,
    Environment environment
) {
    ServerSpec spec;
    spec.name = std::move(name);
    spec.image_id = "img-linux2026";
    spec.region = "ap-south-1";
    spec.flavor = std::move(flavor);
    spec.environment = environment;
    spec.network = {
        "subnet-app001",
        {"sg-app001"},
        {443},
        false
    };
    spec.root_disk_gib = 40;
    spec.encrypted_disk = true;
    spec.monitoring_enabled = true;
    spec.owner = "platform-operations";
    return spec;
}

int main() {
    try {
        DeploymentEngine engine;

        Instance& api = engine.deploy(
            make_spec("catalog-api", "medium", Environment::Development)
        );

        Instance& payments = engine.deploy(
            make_spec("payments-api", "large", Environment::Production)
        );

        std::cout << "Initial virtual server inventory\n";
        engine.print_inventory();

        std::cout << "\nEstimated monthly compute cost\n"
                  << api.spec.name << ": $"
                  << std::fixed << std::setprecision(2)
                  << engine.monthly_compute_estimate(api.id) << '\n'
                  << payments.spec.name << ": $"
                  << engine.monthly_compute_estimate(payments.id) << '\n';

        engine.stop(api.id);
        engine.start(api.id);
        engine.restart(payments.id);

        engine.inject_provider_failure("stop");
        try {
            engine.stop(payments.id);
        } catch (const DeploymentError& error) {
            std::cout << "\nExpected operational failure: "
                      << error.what() << '\n';
        }

        std::cout << "\nInventory after lifecycle operations\n";
        engine.print_inventory();

        std::cout << "\nPayments instance audit\n";
        engine.print_audit(payments.id);

        std::cout << "\nChecking governance boundaries\n";
        try {
            engine.start(payments.id);
            std::cout << "Recovery from failed state succeeded\n";
        } catch (const DeploymentError& error) {
            std::cout << "Recovery rejected: " << error.what() << '\n';
        }

        try {
            ServerSpec invalid =
                make_spec("unsafe-production", "small", Environment::Production);
            invalid.encrypted_disk = false;
            engine.deploy(invalid);
        } catch (const PolicyViolation& error) {
            std::cout << "Policy correctly rejected deployment: "
                      << error.what() << '\n';
        }

        engine.terminate(api.id);
        std::cout << "Terminated instance compute estimate: $"
                  << engine.monthly_compute_estimate(api.id) << '\n';

    } catch (const std::exception& error) {
        std::cerr << "Fatal deployment error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
