#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class InstanceState {
    Pending,
    Ready,
    Unhealthy
};

enum class ScalingAction {
    ScaleOut,
    ScaleIn,
    NoChange
};

struct MachineType {
    string name;
    int cpu_cores;
    double memory_gb;
    double requests_per_core;
    double hourly_cost;

    double capacity() const {
        return cpu_cores * requests_per_core;
    }
};

struct Instance {
    string id;
    MachineType machine;
    InstanceState state;
    int ready_at;
};

struct GovernancePolicy {
    int minimum_instances = 2;
    int maximum_instances = 12;
    int scale_out_step = 2;
    int scale_in_step = 1;
    int cooldown_seconds = 90;
    int warmup_seconds = 60;
    int evaluation_samples = 3;
    int maximum_change = 3;
    double scale_out_cpu = 75.0;
    double scale_in_cpu = 25.0;
    double target_cpu = 60.0;

    void validate() const {
        if (minimum_instances < 1 ||
            maximum_instances < minimum_instances) {
            throw invalid_argument("Invalid instance bounds.");
        }
        if (scale_out_step < 1 || scale_in_step < 1 ||
            evaluation_samples < 1 || maximum_change < 1) {
            throw invalid_argument("Scaling steps must be positive.");
        }
        if (cooldown_seconds < 0 || warmup_seconds < 0) {
            throw invalid_argument("Cooldown and warmup cannot be negative.");
        }
        if (!(scale_in_cpu >= 0 &&
              scale_in_cpu < scale_out_cpu &&
              scale_out_cpu <= 100)) {
            throw invalid_argument("Invalid CPU thresholds.");
        }
        if (!(target_cpu > 0 && target_cpu < 100)) {
            throw invalid_argument("Target CPU must be between 0 and 100.");
        }
    }
};

struct Metrics {
    int time;
    double incoming_rps;
    double capacity_rps;
    double cpu_percent;
    double served_rps;
    double rejected_rps;
    int desired_instances;
    int ready_instances;
    int pending_instances;
    double hourly_cost;
    double estimated_latency_ms;
};

struct AuditEvent {
    int time;
    string action;
    int previous_desired;
    int current_desired;
    string reason;
};

class RepositoryStyleAuditLog {
private:
    vector<AuditEvent> events;

public:
    void append(const AuditEvent& event) {
        events.push_back(event);
    }

    const vector<AuditEvent>& all() const {
        return events;
    }
};

class GovernanceEngine {
private:
    MachineType machine;
    GovernancePolicy policy;
    vector<Instance> instances;
    vector<double> cpu_samples;
    vector<Metrics> metrics_history;
    RepositoryStyleAuditLog audit;
    int now = 0;
    int sequence = 1;
    int last_action = -1000000;

    int ready_count() const {
        return static_cast<int>(count_if(
            instances.begin(), instances.end(),
            [](const Instance& item) {
                return item.state == InstanceState::Ready;
            }
        ));
    }

    int pending_count() const {
        return static_cast<int>(count_if(
            instances.begin(), instances.end(),
            [](const Instance& item) {
                return item.state == InstanceState::Pending;
            }
        ));
    }

    double ready_capacity() const {
        return ready_count() * machine.capacity();
    }

    double hourly_cost() const {
        // Pending instances are counted because infrastructure may be billed
        // while they initialize.
        return count_if(
            instances.begin(), instances.end(),
            [](const Instance& item) {
                return item.state != InstanceState::Unhealthy;
            }
        ) * machine.hourly_cost;
    }

    void record(
        const string& action,
        int previous,
        const string& reason
    ) {
        audit.append({
            now, action, previous,
            static_cast<int>(instances.size()), reason
        });
    }

public:
    GovernanceEngine(MachineType selected, GovernancePolicy rules)
        : machine(std::move(selected)), policy(rules) {
        policy.validate();

        if (machine.cpu_cores <= 0 ||
            machine.memory_gb <= 0 ||
            machine.requests_per_core <= 0 ||
            machine.hourly_cost < 0) {
            throw invalid_argument("Invalid machine specification.");
        }

        for (int i = 0; i < policy.minimum_instances; ++i) {
            instances.push_back({
                "node-" + to_string(sequence++),
                machine,
                InstanceState::Ready,
                0
            });
        }
    }

    void advance(int seconds) {
        if (seconds < 0) {
            throw invalid_argument("Time cannot move backwards.");
        }

        now += seconds;
        for (auto& instance : instances) {
            if (instance.state == InstanceState::Pending &&
                instance.ready_at <= now) {
                instance.state = InstanceState::Ready;
            }
        }
    }

    Metrics observe(double incoming_rps) {
        if (!isfinite(incoming_rps) || incoming_rps < 0) {
            throw invalid_argument("Traffic must be finite and non-negative.");
        }

        const double capacity = ready_capacity();
        const double served = min(incoming_rps, capacity);
        const double rejected = max(0.0, incoming_rps - capacity);
        const double cpu = capacity > 0
            ? min(100.0, incoming_rps / capacity * 100.0)
            : 100.0;

        // The queueing approximation increases sharply near saturation.
        const double utilization = capacity > 0
            ? min(0.999, incoming_rps / capacity)
            : 1.0;
        const double latency = rejected > 0
            ? 1000.0 + rejected * 10.0
            : 20.0 + 80.0 * utilization / max(0.01, 1.0 - utilization);

        Metrics result{
            now,
            incoming_rps,
            capacity,
            cpu,
            served,
            rejected,
            static_cast<int>(instances.size()),
            ready_count(),
            pending_count(),
            hourly_cost(),
            min(60000.0, latency)
        };

        metrics_history.push_back(result);
        cpu_samples.push_back(cpu);
        if (cpu_samples.size() > static_cast<size_t>(policy.evaluation_samples)) {
            cpu_samples.erase(cpu_samples.begin());
        }
        return result;
    }

    int scale_out(int requested, const string& reason) {
        if (requested <= 0) {
            throw invalid_argument("Scale-out request must be positive.");
        }

        const int allowed = min({
            requested,
            policy.maximum_instances - static_cast<int>(instances.size()),
            policy.maximum_change
        });

        if (allowed <= 0) return 0;

        const int previous = static_cast<int>(instances.size());
        for (int i = 0; i < allowed; ++i) {
            instances.push_back({
                "node-" + to_string(sequence++),
                machine,
                InstanceState::Pending,
                now + policy.warmup_seconds
            });
        }

        last_action = now;
        record("scale_out", previous, reason);
        return allowed;
    }

    int scale_in(int requested, const string& reason) {
        if (requested <= 0) {
            throw invalid_argument("Scale-in request must be positive.");
        }

        const int allowed = min({
            requested,
            static_cast<int>(instances.size()) - policy.minimum_instances,
            policy.maximum_change
        });

        if (allowed <= 0) return 0;

        const int previous = static_cast<int>(instances.size());

        // Terminate pending instances first so serving capacity is preserved.
        sort(instances.begin(), instances.end(),
             [](const Instance& a, const Instance& b) {
                 if (a.state != b.state) {
                     return a.state == InstanceState::Pending;
                 }
                 return a.id > b.id;
             });

        instances.erase(
            instances.begin(),
            instances.begin() + allowed
        );

        last_action = now;
        record("scale_in", previous, reason);
        return allowed;
    }

    ScalingAction evaluate() {
        if (cpu_samples.size() <
            static_cast<size_t>(policy.evaluation_samples)) {
            return ScalingAction::NoChange;
        }

        if (now - last_action < policy.cooldown_seconds) {
            return ScalingAction::NoChange;
        }

        const double average = accumulate(
            cpu_samples.begin(), cpu_samples.end(), 0.0
        ) / cpu_samples.size();

        if (average > policy.scale_out_cpu) {
            scale_out(
                policy.scale_out_step,
                "Average CPU exceeded scale-out threshold"
            );
            return ScalingAction::ScaleOut;
        }

        if (average < policy.scale_in_cpu) {
            scale_in(
                policy.scale_in_step,
                "Average CPU fell below scale-in threshold"
            );
            return ScalingAction::ScaleIn;
        }

        return ScalingAction::NoChange;
    }

    void fail_instance(const string& id) {
        auto found = find_if(
            instances.begin(), instances.end(),
            [&id](const Instance& instance) {
                return instance.id == id;
            }
        );

        if (found == instances.end()) {
            throw invalid_argument("Instance does not exist.");
        }

        found->state = InstanceState::Unhealthy;
        record("instance_failure", static_cast<int>(instances.size()),
               "Health check failure: " + id);
    }

    void replace_failed_instances() {
        const int failed = static_cast<int>(count_if(
            instances.begin(), instances.end(),
            [](const Instance& instance) {
                return instance.state == InstanceState::Unhealthy;
            }
        ));

        for (auto it = instances.begin(); it != instances.end();) {
            if (it->state == InstanceState::Unhealthy) {
                it = instances.erase(it);
            } else {
                ++it;
            }
        }

        // Replacement is bounded by the configured maximum capacity.
        const int required = min(
            failed,
            policy.maximum_instances - static_cast<int>(instances.size())
        );
        if (required > 0) {
            scale_out(required, "Replace failed instances");
        }
    }

    void print_report() const {
        cout << fixed << setprecision(1);
        cout << "\nTIME  TRAFFIC  CAPACITY  CPU%  READY  PENDING  REJECTED  COST/HR\n";
        cout << string(72, '-') << '\n';

        for (const auto& item : metrics_history) {
            cout << setw(4) << item.time << "  "
                 << setw(7) << item.incoming_rps << "  "
                 << setw(8) << item.capacity_rps << "  "
                 << setw(4) << item.cpu_percent << "  "
                 << setw(5) << item.ready_instances << "  "
                 << setw(7) << item.pending_instances << "  "
                 << setw(8) << item.rejected_rps << "  "
                 << setw(7) << item.hourly_cost << '\n';
        }

        cout << "\nScaling and failure audit\n";
        for (const auto& event : audit.all()) {
            cout << "t=" << event.time << " " << event.action << " "
                 << event.previous_desired << " -> "
                 << event.current_desired << ": "
                 << event.reason << '\n';
        }
    }

    const vector<Metrics>& history() const {
        return metrics_history;
    }

    int desired_count() const {
        return static_cast<int>(instances.size());
    }

    int healthy_ready_count() const {
        return ready_count();
    }
};

struct VerticalSizingResult {
    int required_instances;
    double hourly_cost;
};

VerticalSizingResult size_fleet(
    const MachineType& machine,
    double demand_rps,
    double target_utilization
) {
    if (!isfinite(demand_rps) || demand_rps < 0 ||
        !(target_utilization > 0 && target_utilization < 1)) {
        throw invalid_argument("Invalid vertical-sizing inputs.");
    }

    const int required = static_cast<int>(
        ceil(demand_rps / (machine.capacity() * target_utilization))
    );

    return {
        required,
        required * machine.hourly_cost
    };
}

int main() {
    try {
        const MachineType small{
            "general-small", 2, 4.0, 120.0, 0.08
        };
        const MachineType large{
            "general-large", 8, 16.0, 120.0, 0.30
        };

        GovernancePolicy policy;
        policy.minimum_instances = 2;
        policy.maximum_instances = 10;
        policy.scale_out_step = 2;
        policy.scale_in_step = 1;
        policy.cooldown_seconds = 60;
        policy.warmup_seconds = 60;
        policy.evaluation_samples = 2;
        policy.maximum_change = 3;
        policy.scale_out_cpu = 75.0;
        policy.scale_in_cpu = 25.0;

        GovernanceEngine engine(small, policy);

        // The traffic profile models a normal period, a release-day spike,
        // a sustained peak, and a quiet period after the event.
        vector<double> traffic;
        traffic.insert(traffic.end(), 4, 80.0);
        traffic.insert(traffic.end(), 5, 350.0);
        traffic.insert(traffic.end(), 7, 900.0);
        traffic.insert(traffic.end(), 5, 1400.0);
        traffic.insert(traffic.end(), 8, 90.0);

        for (double rps : traffic) {
            engine.advance(30);
            const Metrics result = engine.observe(rps);
            engine.evaluate();

            if (result.rejected_rps > 0) {
                cout << "Capacity warning at t=" << result.time
                     << ": rejected " << result.rejected_rps
                     << " requests/s.\n";
            }
        }

        engine.print_report();

        cout << "\nVertical sizing comparison for 900 requests/s\n";
        for (const MachineType* type : {&small, &large}) {
            const auto result = size_fleet(*type, 900.0, 0.60);
            cout << type->name
                 << ": instances=" << result.required_instances
                 << ", hourly cost=$" << fixed << setprecision(2)
                 << result.hourly_cost << '\n';
        }

        cout << "\nFailure recovery demonstration\n";
        if (engine.healthy_ready_count() > 0) {
            // This case study uses an illustrative instance identifier.
            engine.fail_instance("node-1");
            engine.replace_failed_instances();
            engine.advance(policy.warmup_seconds);
            cout << "Healthy instances after replacement: "
                 << engine.healthy_ready_count() << '\n';
        }

        // A sudden burst may exceed the scale-out warmup interval. Production
        // systems use queues, load shedding, predictive capacity, and spare
        // headroom to reduce the impact of that delay.
        const auto& history = engine.history();
        if (!history.empty()) {
            double rejected_total = 0;
            for (const auto& item : history) {
                rejected_total += item.rejected_rps;
            }
            cout << "Sum of sampled rejected request rates: "
                 << rejected_total << '\n';
        }

    } catch (const exception& error) {
        cerr << "Auto-scaling engine error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
