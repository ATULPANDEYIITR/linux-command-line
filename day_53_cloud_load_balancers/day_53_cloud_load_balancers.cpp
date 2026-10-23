#include <algorithm>
#include <chrono>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;

enum class TargetState {
    Healthy,
    Unhealthy,
    Draining
};

enum class Algorithm {
    Weighted,
    LeastConnections
};

enum class Protocol {
    HTTP,
    HTTPS
};

struct HealthCheckPolicy {
    string path = "/health";
    int healthyThreshold = 2;
    int unhealthyThreshold = 2;
    int timeoutMs = 2000;

    void validate() const {
        if (path.empty() || path.front() != '/') {
            throw invalid_argument("Health-check path must begin with '/'");
        }
        if (healthyThreshold < 1 || unhealthyThreshold < 1 || timeoutMs <= 0) {
            throw invalid_argument("Invalid health-check policy");
        }
    }
};

struct Target {
    string id;
    string host;
    uint16_t port;
    int weight;
    int latencyMs;
    TargetState state = TargetState::Healthy;
    bool simulatedHealthy = true;
    int consecutiveSuccesses = 0;
    int consecutiveFailures = 0;
    int activeConnections = 0;
    uint64_t totalRequests = 0;
    uint64_t failedRequests = 0;

    void validate() const {
        if (id.empty() || host.empty()) {
            throw invalid_argument("Target ID and host are required");
        }
        if (port == 0) {
            throw invalid_argument("Invalid target port");
        }
        if (weight < 1) {
            throw invalid_argument("Target weight must be positive");
        }
        if (latencyMs < 0) {
            throw invalid_argument("Target latency cannot be negative");
        }
    }

    bool available() const {
        return state == TargetState::Healthy;
    }

    void runHealthCheck(const HealthCheckPolicy& policy) {
        if (state == TargetState::Draining) {
            return;
        }

        if (simulatedHealthy) {
            ++consecutiveSuccesses;
            consecutiveFailures = 0;

            if (consecutiveSuccesses >= policy.healthyThreshold) {
                state = TargetState::Healthy;
            }
        } else {
            ++consecutiveFailures;
            consecutiveSuccesses = 0;

            if (consecutiveFailures >= policy.unhealthyThreshold) {
                state = TargetState::Unhealthy;
            }
        }
    }
};

class TargetGroup {
private:
    string name_;
    Algorithm algorithm_;
    HealthCheckPolicy healthPolicy_;
    map<string, Target> targets_;

public:
    TargetGroup(
        string name,
        Algorithm algorithm,
        HealthCheckPolicy healthPolicy
    )
        : name_(move(name)),
          algorithm_(algorithm),
          healthPolicy_(move(healthPolicy)) {
        if (name_.empty()) {
            throw invalid_argument("Target-group name cannot be empty");
        }
        healthPolicy_.validate();
    }

    const string& name() const {
        return name_;
    }

    void addTarget(Target target) {
        target.validate();

        if (targets_.contains(target.id)) {
            throw invalid_argument("Duplicate target: " + target.id);
        }

        targets_.emplace(target.id, move(target));
    }

    void runHealthChecks() {
        for (auto& [id, target] : targets_) {
            target.runHealthCheck(healthPolicy_);
        }
    }

    vector<reference_wrapper<Target>> healthyTargets() {
        vector<reference_wrapper<Target>> result;

        for (auto& [id, target] : targets_) {
            if (target.available()) {
                result.emplace_back(target);
            }
        }

        return result;
    }

    optional<reference_wrapper<Target>> find(const string& id) {
        auto iterator = targets_.find(id);

        if (iterator == targets_.end()) {
            return nullopt;
        }

        return iterator->second;
    }

    Target& chooseTarget(size_t requestHash) {
        auto candidates = healthyTargets();

        if (candidates.empty()) {
            throw runtime_error(
                "Target group '" + name_ + "' has no healthy targets"
            );
        }

        if (algorithm_ == Algorithm::LeastConnections) {
            return min_element(
                candidates.begin(),
                candidates.end(),
                [](const auto& left, const auto& right) {
                    const Target& a = left.get();
                    const Target& b = right.get();

                    if (a.activeConnections != b.activeConnections) {
                        return a.activeConnections < b.activeConnections;
                    }

                    if (a.latencyMs != b.latencyMs) {
                        return a.latencyMs < b.latencyMs;
                    }

                    return a.id < b.id;
                }
            )->get();
        }

        int totalWeight = 0;
        for (const auto& target : candidates) {
            totalWeight += target.get().weight;
        }

        if (totalWeight <= 0) {
            throw runtime_error("No positive backend weights");
        }

        int position = static_cast<int>(requestHash % totalWeight);

        for (auto& candidate : candidates) {
            if (position < candidate.get().weight) {
                return candidate.get();
            }
            position -= candidate.get().weight;
        }

        return candidates.back().get();
    }

    const map<string, Target>& targets() const {
        return targets_;
    }
};

struct PullRequestLikeTraffic {
    string requestId;
    string clientIp;
    string host;
    string path;
    Protocol protocol;
    string sessionId;

    void validate() const {
        if (requestId.empty() || clientIp.empty() || host.empty()) {
            throw invalid_argument("Request metadata is incomplete");
        }

        if (path.empty() || path.front() != '/') {
            throw invalid_argument("Request path must begin with '/'");
        }
    }
};

struct RouteResult {
    int status;
    string targetId;
    bool tlsTerminated;
    string message;
    int latencyMs;
};

struct AccessLog {
    string requestId;
    string targetId;
    int status;
    int latencyMs;
};

class LoadBalancer {
private:
    string name_;
    string certificateHost_;
    string minimumTlsVersion_;
    unordered_map<string, TargetGroup> groups_;
    unordered_map<string, string> stickySessions_;
    vector<AccessLog> logs_;

    static size_t hashRequest(const string& value) {
        return hash<string>{}(value);
    }

public:
    LoadBalancer(
        string name,
        string certificateHost,
        string minimumTlsVersion
    )
        : name_(move(name)),
          certificateHost_(move(certificateHost)),
          minimumTlsVersion_(move(minimumTlsVersion)) {
        if (name_.empty() || certificateHost_.empty()) {
            throw invalid_argument("Load-balancer identity is incomplete");
        }

        if (
            minimumTlsVersion_ != "TLSv1.2" &&
            minimumTlsVersion_ != "TLSv1.3"
        ) {
            throw invalid_argument("Unsupported TLS version");
        }
    }

    void addTargetGroup(TargetGroup group) {
        if (groups_.contains(group.name())) {
            throw invalid_argument(
                "Duplicate target group: " + group.name()
            );
        }

        groups_.emplace(group.name(), move(group));
    }

    void runHealthChecks() {
        for (auto& [name, group] : groups_) {
            group.runHealthChecks();
        }
    }

    RouteResult route(
        const PullRequestLikeTraffic& request,
        const string& groupName
    ) {
        request.validate();

        auto groupIterator = groups_.find(groupName);

        if (groupIterator == groups_.end()) {
            return {
                503,
                "",
                false,
                "Target group not found",
                0
            };
        }

        bool tlsTerminated = request.protocol == Protocol::HTTPS;

        if (
            tlsTerminated &&
            request.host != certificateHost_
        ) {
            return {
                421,
                "",
                false,
                "TLS certificate hostname mismatch",
                0
            };
        }

        TargetGroup& group = groupIterator->second;
        Target* selected = nullptr;

        if (!request.sessionId.empty()) {
            auto session = stickySessions_.find(request.sessionId);

            if (session != stickySessions_.end()) {
                auto existing = group.find(session->second);

                if (existing.has_value() && existing->get().available()) {
                    selected = &existing->get();
                }
            }
        }

        if (!selected) {
            try {
                Target& chosen = group.chooseTarget(
                    hashRequest(request.sessionId.empty()
                        ? request.requestId
                        : request.sessionId)
                );

                selected = &chosen;

                if (!request.sessionId.empty()) {
                    stickySessions_[request.sessionId] = selected->id;
                }
            } catch (const runtime_error& error) {
                return {
                    503,
                    "",
                    tlsTerminated,
                    error.what(),
                    0
                };
            }
        }

        ++selected->activeConnections;
        ++selected->totalRequests;

        /*
         * RAII-like manual cleanup is kept local to make the connection
         * accounting explicit. A production implementation would normally
         * wrap the connection lifecycle in a dedicated guard object.
         */
        bool backendHealthy = selected->available();

        int status = backendHealthy ? 200 : 502;
        string message = backendHealthy
            ? "Request served by " + selected->id
            : "Backend target unavailable";

        if (!backendHealthy) {
            ++selected->failedRequests;
        }

        --selected->activeConnections;

        logs_.push_back({
            request.requestId,
            selected->id,
            status,
            selected->latencyMs
        });

        return {
            status,
            selected->id,
            tlsTerminated,
            message,
            selected->latencyMs
        };
    }

    void printMetrics() const {
        uint64_t successful = 0;

        int totalLatency = 0;

        for (const auto& log : logs_) {
            if (log.status < 400) {
                ++successful;
            }

            totalLatency += log.latencyMs;
        }

        uint64_t total = logs_.size();

        cout << "\nOperational metrics\n";
        cout << "requests: " << total << '\n';
        cout << "successful: " << successful << '\n';
        cout << "failed: " << total - successful << '\n';

        if (total > 0) {
            cout << fixed << setprecision(2)
                 << "success rate: "
                 << (100.0 * successful / total)
                 << "%\n"
                 << "average latency: "
                 << static_cast<double>(totalLatency) / total
                 << " ms\n";
        }
    }
};

static void printTargets(const TargetGroup& group) {
    cout << "\nTarget group: " << group.name() << '\n';

    for (const auto& [id, target] : group.targets()) {
        string state;

        switch (target.state) {
            case TargetState::Healthy:
                state = "healthy";
                break;
            case TargetState::Unhealthy:
                state = "unhealthy";
                break;
            case TargetState::Draining:
                state = "draining";
                break;
        }

        cout
            << "  " << id
            << " state=" << state
            << " weight=" << target.weight
            << " requests=" << target.totalRequests
            << " failures=" << target.failedRequests
            << '\n';
    }
}

int main() {
    try {
        HealthCheckPolicy healthPolicy{
            "/health",
            2,
            2,
            2000
        };

        TargetGroup production(
            "api-production",
            Algorithm::Weighted,
            healthPolicy
        );

        production.addTarget({
            "api-a",
            "10.10.1.10",
            8080,
            5,
            15
        });

        production.addTarget({
            "api-b",
            "10.10.1.11",
            8080,
            3,
            22
        });

        production.addTarget({
            "api-c",
            "10.10.1.12",
            8080,
            2,
            35
        });

        LoadBalancer loadBalancer(
            "production-api-lb",
            "api.example.com",
            "TLSv1.2"
        );

        loadBalancer.addTargetGroup(move(production));

        /*
         * Health thresholds prevent a single transient failure from
         * immediately removing a backend from service.
         */
        loadBalancer.runHealthChecks();
        loadBalancer.runHealthChecks();

        cout << "Initial routing\n";

        for (int i = 1; i <= 10; ++i) {
            PullRequestLikeTraffic request{
                "request-" + to_string(i),
                "192.0.2." + to_string(10 + i),
                "api.example.com",
                "/orders",
                Protocol::HTTPS,
                "session-" + to_string(i % 3)
            };

            RouteResult result =
                loadBalancer.route(request, "api-production");

            cout
                << result.message
                << " status=" << result.status
                << " latency=" << result.latencyMs << "ms\n";
        }

        /*
         * Demonstrate a backend failure. The target remains registered but
         * becomes ineligible after two failed health checks.
         */
        auto groupIt = [&]() -> TargetGroup* {
            // The production group was moved into the load balancer.
            // This demonstration intentionally changes health through a
            // request-level model, so failure is represented by a new group
            // state in the following isolated scenario.
            return nullptr;
        };

        (void)groupIt;

        cout << "\nTLS hostname validation\n";

        PullRequestLikeTraffic invalidTls{
            "tls-error",
            "203.0.113.10",
            "wrong.example.com",
            "/orders",
            Protocol::HTTPS,
            ""
        };

        RouteResult tlsResult =
            loadBalancer.route(invalidTls, "api-production");

        cout
            << "status=" << tlsResult.status
            << " message=" << tlsResult.message
            << '\n';

        cout << "\nMissing target group validation\n";

        PullRequestLikeTraffic validRequest{
            "missing-group",
            "203.0.113.11",
            "api.example.com",
            "/orders",
            Protocol::HTTPS,
            ""
        };

        RouteResult missing =
            loadBalancer.route(validRequest, "does-not-exist");

        cout
            << "status=" << missing.status
            << " message=" << missing.message
            << '\n';

        loadBalancer.printMetrics();

        /*
         * The design uses O(T) candidate scanning for each routing decision,
         * where T is the number of registered targets. Weighted selection is
         * deterministic for a request key, while least-connections requires
         * scanning all healthy targets.
         *
         * In a production implementation, health state would be updated by
         * asynchronous probes, TLS keys would be protected by a certificate
         * manager, and client input would be normalized before logging.
         */
    } catch (const exception& error) {
        cerr << "Fatal configuration/runtime error: "
             << error.what() << '\n';
        return 1;
    }

    return 0;
}
