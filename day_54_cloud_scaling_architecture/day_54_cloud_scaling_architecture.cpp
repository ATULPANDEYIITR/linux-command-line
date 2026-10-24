#include <algorithm>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

enum class InstanceState {
    Starting,
    Healthy,
    Unhealthy,
    Draining,
    Terminated
};

enum class ScalingAction {
    ScaleOut,
    ScaleIn,
    Hold
};

struct Instance {
    std::string id;
    int capacityRps;
    InstanceState state{InstanceState::Starting};
    int activeRequests{0};

    int availableCapacity() const {
        if (state != InstanceState::Healthy) {
            return 0;
        }
        return std::max(0, capacityRps - activeRequests);
    }
};

struct ScalingPolicy {
    double scaleOutThreshold{0.75};
    double scaleInThreshold{0.30};
    int minInstances{2};
    int maxInstances{8};
    int cooldownTicks{2};
};

struct RoutingResult {
    std::map<std::string, int> allocation;
    int served{0};
    int rejected{0};
};

class LoadBalancer {
private:
    std::size_t cursor_{0};

public:
    std::vector<Instance*> healthyTargets(
        std::vector<Instance>& instances) const {

        std::vector<Instance*> result;

        for (auto& instance : instances) {
            if (instance.state == InstanceState::Healthy) {
                result.push_back(&instance);
            }
        }

        return result;
    }

    RoutingResult route(
        int requests,
        std::vector<Instance>& instances) {

        if (requests < 0) {
            throw std::invalid_argument(
                "Request count cannot be negative");
        }

        auto targets = healthyTargets(instances);

        if (targets.empty()) {
            throw std::runtime_error(
                "Load balancer has no healthy targets");
        }

        RoutingResult result;

        for (const auto& instance : instances) {
            result.allocation[instance.id] = 0;
        }

        int remaining = requests;
        const std::size_t start = cursor_ % targets.size();

        while (remaining > 0) {
            bool progress = false;

            for (std::size_t offset = 0;
                 offset < targets.size();
                 ++offset) {

                Instance* instance =
                    targets[(start + offset) % targets.size()];

                const int capacity = instance->availableCapacity();

                if (capacity <= 0) {
                    continue;
                }

                const int assigned =
                    std::min(capacity, remaining);

                instance->activeRequests += assigned;
                result.allocation[instance->id] += assigned;
                remaining -= assigned;
                progress = true;

                if (remaining == 0) {
                    break;
                }
            }

            if (!progress) {
                break;
            }
        }

        result.served = requests - remaining;
        result.rejected = remaining;
        cursor_ = (start + 1) % targets.size();

        return result;
    }
};

class AutoScaler {
private:
    ScalingPolicy policy_;
    int cooldownRemaining_{0};

public:
    explicit AutoScaler(ScalingPolicy policy)
        : policy_(policy) {

        if (policy_.minInstances < 1 ||
            policy_.maxInstances < policy_.minInstances) {
            throw std::invalid_argument(
                "Invalid instance limits");
        }

        if (!(policy_.scaleInThreshold > 0.0 &&
              policy_.scaleInThreshold <
                  policy_.scaleOutThreshold &&
              policy_.scaleOutThreshold <= 1.0)) {
            throw std::invalid_argument(
                "Invalid scaling thresholds");
        }
    }

    ScalingAction evaluate(
        int requests,
        int totalCapacity) {

        if (totalCapacity <= 0) {
            return ScalingAction::ScaleOut;
        }

        if (cooldownRemaining_ > 0) {
            --cooldownRemaining_;
            return ScalingAction::Hold;
        }

        const double utilization =
            static_cast<double>(requests) /
            static_cast<double>(totalCapacity);

        if (utilization > policy_.scaleOutThreshold) {
            return ScalingAction::ScaleOut;
        }

        if (utilization < policy_.scaleInThreshold) {
            return ScalingAction::ScaleIn;
        }

        return ScalingAction::Hold;
    }

    void startCooldown() {
        cooldownRemaining_ = policy_.cooldownTicks;
    }

    const ScalingPolicy& policy() const {
        return policy_;
    }
};

class GovernanceEngine {
private:
    ScalingPolicy policy_;
    AutoScaler scaler_;
    LoadBalancer loadBalancer_;
    std::vector<Instance> instances_;
    int nextId_{1};

    int activeInstanceCount() const {
        return static_cast<int>(
            std::count_if(
                instances_.begin(),
                instances_.end(),
                [](const Instance& instance) {
                    return instance.state !=
                           InstanceState::Terminated;
                }));
    }

    int healthyCapacity() const {
        int total = 0;

        for (const auto& instance : instances_) {
            if (instance.state == InstanceState::Healthy) {
                total += instance.capacityRps;
            }
        }

        return total;
    }

    Instance createInstance() {
        // Deterministic capacity makes the case study reproducible.
        const int capacity =
            100 + ((nextId_ * 19) % 31);

        Instance instance{
            "compute-" +
                (nextId_ < 10
                    ? "0" + std::to_string(nextId_)
                    : std::to_string(nextId_)),
            capacity
        };

        ++nextId_;
        return instance;
    }

    void activateStartingInstances() {
        for (auto& instance : instances_) {
            if (instance.state == InstanceState::Starting) {
                instance.state = InstanceState::Healthy;
            }
        }
    }

public:
    explicit GovernanceEngine(ScalingPolicy policy)
        : policy_(policy),
          scaler_(policy) {

        scaleTo(policy_.minInstances);
        activateStartingInstances();
    }

    void scaleTo(int desired) {
        desired = std::max(
            policy_.minInstances,
            std::min(policy_.maxInstances, desired));

        int active = activeInstanceCount();

        while (active < desired) {
            instances_.push_back(createInstance());
            ++active;
        }

        if (active > desired) {
            for (auto& instance : instances_) {
                if (active <= desired) {
                    break;
                }

                if (instance.state == InstanceState::Healthy &&
                    instance.activeRequests == 0) {

                    instance.state = InstanceState::Terminated;
                    --active;
                }
            }
        }

        activateStartingInstances();
    }

    void setHealth(
        const std::string& id,
        bool healthy) {

        auto it = std::find_if(
            instances_.begin(),
            instances_.end(),
            [&id](const Instance& instance) {
                return instance.id == id &&
                       instance.state !=
                           InstanceState::Terminated;
            });

        if (it == instances_.end()) {
            throw std::out_of_range(
                "Unknown compute instance");
        }

        it->state = healthy
            ? InstanceState::Healthy
            : InstanceState::Unhealthy;
    }

    struct Decision {
        ScalingAction action;
        RoutingResult routing;
        int instances;
        int healthy;
        int capacity;
    };

    Decision process(int requestRate) {
        if (requestRate < 0) {
            throw std::invalid_argument(
                "Request rate cannot be negative");
        }

        for (auto& instance : instances_) {
            instance.activeRequests = 0;
        }

        const ScalingAction action =
            scaler_.evaluate(
                requestRate,
                healthyCapacity());

        if (action == ScalingAction::ScaleOut) {
            scaleTo(activeInstanceCount() + 1);
            scaler_.startCooldown();
        } else if (action == ScalingAction::ScaleIn) {
            scaleTo(activeInstanceCount() - 1);
            scaler_.startCooldown();
        }

        RoutingResult routing;

        try {
            routing =
                loadBalancer_.route(
                    requestRate,
                    instances_);
        } catch (const std::exception&) {
            routing.rejected = requestRate;
        }

        for (auto& instance : instances_) {
            instance.activeRequests = 0;
        }

        const int healthy =
            static_cast<int>(
                std::count_if(
                    instances_.begin(),
                    instances_.end(),
                    [](const Instance& instance) {
                        return instance.state ==
                               InstanceState::Healthy;
                    }));

        return {
            action,
            routing,
            activeInstanceCount(),
            healthy,
            healthyCapacity()
        };
    }

    const std::vector<Instance>& instances() const {
        return instances_;
    }
};

std::string actionName(ScalingAction action) {
    switch (action) {
        case ScalingAction::ScaleOut:
            return "scale_out";
        case ScalingAction::ScaleIn:
            return "scale_in";
        default:
            return "hold";
    }
}

void runAssertions() {
    GovernanceEngine engine(
        ScalingPolicy{
            0.75,
            0.30,
            2,
            4,
            2
        });

    if (engine.instances().size() != 2) {
        throw std::runtime_error(
            "Minimum capacity assertion failed");
    }

    const auto result = engine.process(20);

    if (result.routing.served != 20 ||
        result.routing.rejected != 0) {
        throw std::runtime_error(
            "Normal routing assertion failed");
    }

    engine.setHealth("compute-01", false);

    const auto degraded = engine.process(20);

    if (degraded.healthy != 1) {
        throw std::runtime_error(
            "Health isolation assertion failed");
    }

    try {
        engine.process(-5);
        throw std::runtime_error(
            "Negative request validation failed");
    } catch (const std::invalid_argument&) {
        // Expected failure.
    }
}

void runSimulation() {
    GovernanceEngine engine(
        ScalingPolicy{
            0.75,
            0.30,
            2,
            6,
            2
        });

    const std::vector<int> traffic{
        80, 130, 190, 260, 450,
        610, 320, 150, 70
    };

    std::cout << "Cloud Scaling Architecture\n";
    std::cout << std::string(76, '=') << '\n';

    for (std::size_t tick = 0;
         tick < traffic.size();
         ++tick) {

        if (tick == 5 &&
            !engine.instances().empty()) {

            engine.setHealth(
                engine.instances().front().id,
                false);
        }

        const auto result =
            engine.process(traffic[tick]);

        std::cout
            << "Tick " << std::setw(2) << tick + 1
            << " | requests=" << std::setw(3)
            << traffic[tick]
            << " | action=" << std::setw(9)
            << actionName(result.action)
            << " | instances=" << result.instances
            << " | healthy=" << result.healthy
            << " | capacity=" << result.capacity
            << " | served=" << result.routing.served
            << " | rejected=" << result.routing.rejected
            << '\n';

        if (tick == 6) {
            for (const auto& instance :
                 engine.instances()) {

                if (instance.state ==
                    InstanceState::Unhealthy) {

                    engine.setHealth(
                        instance.id,
                        true);
                }
            }
        }
    }

    std::cout << "\nFinal compute pool:\n";

    for (const auto& instance : engine.instances()) {
        std::cout
            << "  " << instance.id
            << " capacity=" << instance.capacityRps
            << " state=";

        switch (instance.state) {
            case InstanceState::Healthy:
                std::cout << "healthy";
                break;
            case InstanceState::Unhealthy:
                std::cout << "unhealthy";
                break;
            case InstanceState::Terminated:
                std::cout << "terminated";
                break;
            case InstanceState::Starting:
                std::cout << "starting";
                break;
            case InstanceState::Draining:
                std::cout << "draining";
                break;
        }

        std::cout << '\n';
    }
}

int main() {
    try {
        runAssertions();
        runSimulation();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr
            << "Fatal error: "
            << exception.what()
            << '\n';
        return 1;
    }
}
