#include <algorithm>
#include <chrono>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
 * Load Balancing Governance and Merge Eligibility Engine
 *
 * Technical case study:
 * A company operates an HTTP API across several availability zones.
 * A front-end load-balancing tier receives client traffic, evaluates backend
 * health, applies a traffic-distribution algorithm, and exposes an operational
 * model for high availability.
 *
 * The program deliberately uses a C++ systems perspective:
 * - explicit types and invariants;
 * - classes representing backend infrastructure;
 * - algorithms for weighted routing and least connections;
 * - health-state transitions;
 * - graceful draining;
 * - request-level failure handling;
 * - zone-aware high availability policy;
 * - deterministic hashing;
 * - operational reporting.
 *
 * Build:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic load_balancing.cpp -o load_balancing
 */

enum class BackendState {
    Healthy,
    Unhealthy,
    Draining
};

enum class Algorithm {
    RoundRobin,
    WeightedRoundRobin,
    LeastConnections,
    ConsistentHash
};

std::string toString(BackendState state) {
    switch (state) {
        case BackendState::Healthy:
            return "healthy";
        case BackendState::Unhealthy:
            return "unhealthy";
        case BackendState::Draining:
            return "draining";
    }

    return "unknown";
}

std::string toString(Algorithm algorithm) {
    switch (algorithm) {
        case Algorithm::RoundRobin:
            return "round-robin";
        case Algorithm::WeightedRoundRobin:
            return "weighted-round-robin";
        case Algorithm::LeastConnections:
            return "least-connections";
        case Algorithm::ConsistentHash:
            return "consistent-hash";
    }

    return "unknown";
}

struct HttpRequest {
    std::string requestId;
    std::string clientIp;
    std::string host;
    std::string method;
    std::string path;
    std::optional<std::string> sessionId;
};

struct Backend {
    std::string name;
    std::string ip;
    int port;
    int weight;
    std::string zone;
    std::string service;
    BackendState state = BackendState::Healthy;

    int activeConnections = 0;
    long requests = 0;
    long failures = 0;
    double totalLatencyMs = 0.0;

    double simulatedFailureRate = 0.0;

    bool acceptsNewTraffic() const {
        return state == BackendState::Healthy;
    }

    double averageLatency() const {
        if (requests == 0) {
            return 0.0;
        }

        return totalLatencyMs / static_cast<double>(requests);
    }
};

struct HealthResult {
    bool healthy;
    double latencyMs;
    std::string reason;
};

class BackendPool {
private:
    std::vector<Backend> backends;

public:
    explicit BackendPool(std::vector<Backend> initial)
        : backends(std::move(initial)) {
        if (backends.empty()) {
            throw std::invalid_argument(
                "Backend pool must contain at least one backend."
            );
        }

        for (const auto& backend : backends) {
            if (backend.port < 1 || backend.port > 65535) {
                throw std::invalid_argument(
                    "Backend port must be between 1 and 65535."
                );
            }

            if (backend.weight <= 0) {
                throw std::invalid_argument(
                    "Backend weight must be positive."
                );
            }

            if (
                backend.simulatedFailureRate < 0.0 ||
                backend.simulatedFailureRate > 1.0
            ) {
                throw std::invalid_argument(
                    "Failure rate must be between zero and one."
                );
            }
        }
    }

    std::vector<Backend*> healthyBackends() {
        std::vector<Backend*> result;

        for (auto& backend : backends) {
            if (backend.acceptsNewTraffic()) {
                result.push_back(&backend);
            }
        }

        return result;
    }

    Backend& find(const std::string& name) {
        for (auto& backend : backends) {
            if (backend.name == name) {
                return backend;
            }
        }

        throw std::out_of_range("Unknown backend: " + name);
    }

    const std::vector<Backend>& all() const {
        return backends;
    }

    void startDraining(const std::string& name) {
        Backend& backend = find(name);

        if (backend.state == BackendState::Healthy) {
            backend.state = BackendState::Draining;
        }
    }

    void recover(const std::string& name) {
        find(name).state = BackendState::Healthy;
    }
};

class HealthMonitor {
private:
    int failureThreshold;
    int recoveryThreshold;

    std::unordered_map<std::string, int> failures;
    std::unordered_map<std::string, int> successes;

public:
    HealthMonitor(int failureThreshold, int recoveryThreshold)
        : failureThreshold(failureThreshold),
          recoveryThreshold(recoveryThreshold) {
        if (failureThreshold <= 0 || recoveryThreshold <= 0) {
            throw std::invalid_argument(
                "Health-check thresholds must be positive."
            );
        }
    }

    HealthResult probe(const Backend& backend) const {
        /*
         * Real systems may use TCP probes, HTTP health endpoints, TLS
         * handshakes, or application-specific checks. The case study models
         * the result without performing real network operations.
         */
        if (backend.simulatedFailureRate >= 0.8) {
            return {
                false,
                2000.0,
                "health endpoint unavailable or timed out"
            };
        }

        return {
            true,
            8.0,
            "health endpoint returned expected response"
        };
    }

    void apply(Backend& backend, const HealthResult& result) {
        if (result.healthy) {
            failures[backend.name] = 0;
            successes[backend.name] += 1;

            if (
                backend.state == BackendState::Unhealthy &&
                successes[backend.name] >= recoveryThreshold
            ) {
                backend.state = BackendState::Healthy;
            }
        } else {
            successes[backend.name] = 0;
            failures[backend.name] += 1;

            if (
                backend.state == BackendState::Healthy &&
                failures[backend.name] >= failureThreshold
            ) {
                backend.state = BackendState::Unhealthy;
            }
        }
    }
};

class LoadBalancer {
private:
    BackendPool& pool;
    Algorithm algorithm;
    std::size_t roundRobinIndex = 0;

    /*
     * A connection table models L4 flow affinity. Once a TCP connection has
     * been assigned, subsequent packets on that connection must continue to
     * reach the same backend.
     */
    std::unordered_map<std::string, std::string> connectionMap;

    /*
     * L7 session affinity is intentionally separate from connectionMap.
     * Several HTTP requests can use different transport connections while
     * carrying the same application session cookie.
     */
    std::unordered_map<std::string, std::string> sessionMap;

    std::mt19937 randomGenerator;

    Backend* roundRobin(const std::vector<Backend*>& candidates) {
        Backend* selected =
            candidates[roundRobinIndex % candidates.size()];

        ++roundRobinIndex;
        return selected;
    }

    Backend* weightedRoundRobin(
        const std::vector<Backend*>& candidates
    ) {
        std::vector<Backend*> expanded;

        for (Backend* backend : candidates) {
            for (int i = 0; i < backend->weight; ++i) {
                expanded.push_back(backend);
            }
        }

        if (expanded.empty()) {
            throw std::runtime_error(
                "Weighted algorithm has no usable backends."
            );
        }

        Backend* selected =
            expanded[roundRobinIndex % expanded.size()];

        ++roundRobinIndex;
        return selected;
    }

    Backend* leastConnections(
        const std::vector<Backend*>& candidates
    ) {
        return *std::min_element(
            candidates.begin(),
            candidates.end(),
            [](const Backend* left, const Backend* right) {
                if (
                    left->activeConnections !=
                    right->activeConnections
                ) {
                    return left->activeConnections <
                           right->activeConnections;
                }

                return left->name < right->name;
            }
        );
    }

    Backend* consistentHash(
        const std::vector<Backend*>& candidates,
        const std::string& key
    ) {
        std::hash<std::string> hasher;
        const std::size_t position =
            hasher(key) % candidates.size();

        return candidates[position];
    }

public:
    LoadBalancer(BackendPool& poolReference, Algorithm selectedAlgorithm)
        : pool(poolReference),
          algorithm(selectedAlgorithm),
          randomGenerator(42) {}

    Backend& openL4Connection(
        const std::string& connectionId,
        const std::string& clientIp
    ) {
        auto existing = connectionMap.find(connectionId);

        if (existing != connectionMap.end()) {
            return pool.find(existing->second);
        }

        std::vector<Backend*> candidates =
            pool.healthyBackends();

        if (candidates.empty()) {
            throw std::runtime_error(
                "No healthy backend is available for L4 traffic."
            );
        }

        Backend* selected = nullptr;

        switch (algorithm) {
            case Algorithm::RoundRobin:
                selected = roundRobin(candidates);
                break;

            case Algorithm::WeightedRoundRobin:
                selected = weightedRoundRobin(candidates);
                break;

            case Algorithm::LeastConnections:
                selected = leastConnections(candidates);
                break;

            case Algorithm::ConsistentHash:
                selected = consistentHash(candidates, clientIp);
                break;
        }

        selected->activeConnections += 1;
        connectionMap[connectionId] = selected->name;

        return *selected;
    }

    void closeL4Connection(const std::string& connectionId) {
        auto iterator = connectionMap.find(connectionId);

        if (iterator == connectionMap.end()) {
            return;
        }

        Backend& backend = pool.find(iterator->second);

        /*
         * Idempotent cleanup prevents repeated close events from producing
         * negative connection counts.
         */
        backend.activeConnections =
            std::max(0, backend.activeConnections - 1);

        connectionMap.erase(iterator);
    }

    Backend& routeL7(const HttpRequest& request) {
        std::vector<Backend*> candidates =
            pool.healthyBackends();

        if (candidates.empty()) {
            throw std::runtime_error(
                "No healthy backend is available for HTTP traffic."
            );
        }

        /*
         * L7 routing can distinguish application paths. Administrative
         * requests are isolated to administrative service nodes.
         */
        if (request.path.rfind("/admin", 0) == 0) {
            std::vector<Backend*> admin;

            for (Backend* backend : candidates) {
                if (backend->service == "admin") {
                    admin.push_back(backend);
                }
            }

            if (!admin.empty()) {
                return *roundRobin(admin);
            }
        }

        /*
         * Static assets can be served from an edge-oriented backend pool.
         */
        if (request.path.rfind("/static/", 0) == 0) {
            std::vector<Backend*> edge;

            for (Backend* backend : candidates) {
                if (backend->service == "edge") {
                    edge.push_back(backend);
                }
            }

            if (!edge.empty()) {
                return *roundRobin(edge);
            }
        }

        /*
         * Application session affinity is intentionally checked after
         * health filtering. A dead session target must not permanently
         * trap the session on an unavailable node.
         */
        if (request.sessionId.has_value()) {
            auto iterator =
                sessionMap.find(request.sessionId.value());

            if (iterator != sessionMap.end()) {
                Backend& sessionBackend =
                    pool.find(iterator->second);

                if (sessionBackend.acceptsNewTraffic()) {
                    return sessionBackend;
                }

                sessionMap.erase(iterator);
            }
        }

        Backend* selected = roundRobin(candidates);

        if (request.sessionId.has_value()) {
            sessionMap[request.sessionId.value()] =
                selected->name;
        }

        return *selected;
    }

    bool executeRequest(
        const HttpRequest& request,
        double latencyMs
    ) {
        Backend& backend = routeL7(request);

        std::uniform_real_distribution<double> distribution(0.0, 1.0);

        if (
            distribution(randomGenerator) <
            backend.simulatedFailureRate
        ) {
            backend.failures += 1;
            return false;
        }

        backend.requests += 1;
        backend.totalLatencyMs += latencyMs;

        return true;
    }
};

struct AvailabilityPolicy {
    std::size_t minimumHealthyBackends;
    std::size_t minimumHealthyZones;

    bool permitsService(const BackendPool& pool) const {
        std::size_t healthyCount = 0;
        std::set<std::string> zones;

        for (const Backend& backend : pool.all()) {
            if (backend.acceptsNewTraffic()) {
                ++healthyCount;
                zones.insert(backend.zone);
            }
        }

        return (
            healthyCount >= minimumHealthyBackends &&
            zones.size() >= minimumHealthyZones
        );
    }
};

class HighAvailabilityPair {
private:
    std::string primary;
    std::string standby;
    std::string active;
    unsigned long long epoch = 1;

public:
    HighAvailabilityPair(
        std::string primaryName,
        std::string standbyName
    )
        : primary(std::move(primaryName)),
          standby(std::move(standbyName)),
          active(primary) {}

    void failover() {
        active = (active == primary) ? standby : primary;
        ++epoch;
    }

    const std::string& activeNode() const {
        return active;
    }

    unsigned long long generation() const {
        return epoch;
    }
};

void printHeader(const std::string& title) {
    std::cout << "\n"
              << std::string(78, '=')
              << "\n"
              << title
              << "\n"
              << std::string(78, '=')
              << "\n";
}

void demonstrateHealthMonitoring(BackendPool& pool) {
    printHeader("HEALTH CHECK STATE MACHINE");

    HealthMonitor monitor(2, 2);
    Backend& backend = pool.find("api-b");

    backend.simulatedFailureRate = 1.0;

    for (int probe = 1; probe <= 3; ++probe) {
        HealthResult result = monitor.probe(backend);
        monitor.apply(backend, result);

        std::cout
            << "probe=" << probe
            << " healthy=" << std::boolalpha << result.healthy
            << " state=" << toString(backend.state)
            << " reason=" << result.reason
            << "\n";
    }

    backend.simulatedFailureRate = 0.0;

    for (int probe = 1; probe <= 2; ++probe) {
        HealthResult result = monitor.probe(backend);
        monitor.apply(backend, result);

        std::cout
            << "recovery_probe=" << probe
            << " healthy=" << std::boolalpha << result.healthy
            << " state=" << toString(backend.state)
            << "\n";
    }
}

void demonstrateL4(BackendPool& pool) {
    printHeader("LAYER 4 WEIGHTED TRAFFIC DISTRIBUTION");

    LoadBalancer loadBalancer(
        pool,
        Algorithm::WeightedRoundRobin
    );

    std::map<std::string, int> distribution;

    for (int i = 0; i < 12; ++i) {
        const std::string connectionId =
            "tcp-" + std::to_string(i);

        const std::string clientIp =
            "192.0.2." + std::to_string(10 + i);

        Backend& backend =
            loadBalancer.openL4Connection(
                connectionId,
                clientIp
            );

        ++distribution[backend.name];

        std::cout
            << std::left
            << std::setw(10)
            << connectionId
            << " -> "
            << backend.name
            << "\n";
    }

    std::cout << "\nDistribution:\n";

    for (const auto& [backend, count] : distribution) {
        std::cout
            << std::setw(12)
            << backend
            << count
            << "\n";
    }

    for (int i = 0; i < 12; i += 2) {
        loadBalancer.closeL4Connection(
            "tcp-" + std::to_string(i)
        );
    }
}

void demonstrateL7(BackendPool& pool) {
    printHeader("LAYER 7 APPLICATION-AWARE ROUTING");

    LoadBalancer loadBalancer(
        pool,
        Algorithm::RoundRobin
    );

    std::vector<HttpRequest> requests = {
        {
            "http-001",
            "198.51.100.10",
            "api.example.test",
            "GET",
            "/orders",
            std::nullopt
        },
        {
            "http-002",
            "198.51.100.11",
            "www.example.test",
            "GET",
            "/static/app.js",
            std::nullopt
        },
        {
            "http-003",
            "198.51.100.12",
            "admin.example.test",
            "GET",
            "/admin/users",
            std::nullopt
        },
        {
            "http-004",
            "198.51.100.13",
            "api.example.test",
            "GET",
            "/profile",
            std::string("session-42")
        },
        {
            "http-005",
            "198.51.100.13",
            "api.example.test",
            "GET",
            "/orders/500",
            std::string("session-42")
        }
    };

    for (const HttpRequest& request : requests) {
        Backend& selected =
            loadBalancer.routeL7(request);

        const bool success =
            loadBalancer.executeRequest(request, 15.0);

        std::cout
            << std::left
            << std::setw(12)
            << request.requestId
            << " "
            << std::setw(20)
            << request.path
            << " -> "
            << std::setw(12)
            << selected.name
            << " success="
            << std::boolalpha
            << success
            << "\n";
    }
}

void demonstrateLeastConnections(BackendPool& pool) {
    printHeader("LEAST-CONNECTIONS DECISION");

    LoadBalancer loadBalancer(
        pool,
        Algorithm::LeastConnections
    );

    pool.find("api-a").activeConnections = 5;
    pool.find("api-b").activeConnections = 1;
    pool.find("api-c").activeConnections = 3;

    for (int i = 0; i < 5; ++i) {
        Backend& backend =
            loadBalancer.openL4Connection(
                "least-" + std::to_string(i),
                "203.0.113." + std::to_string(10 + i)
            );

        std::cout
            << "connection="
            << i
            << " selected="
            << backend.name
            << " active="
            << backend.activeConnections
            << "\n";
    }
}

void demonstrateDraining(BackendPool& pool) {
    printHeader("GRACEFUL BACKEND DRAINING");

    Backend& backend = pool.find("api-c");

    backend.activeConnections = 4;
    pool.startDraining(backend.name);

    std::cout
        << backend.name
        << " state="
        << toString(backend.state)
        << " active="
        << backend.activeConnections
        << "\n";

    /*
     * Draining is different from failure. Existing work can complete while
     * the node is excluded from new traffic. A real implementation would
     * normally combine this with a drain timeout and connection tracking.
     */
    while (backend.activeConnections > 0) {
        --backend.activeConnections;
    }

    std::cout
        << backend.name
        << " drained active="
        << backend.activeConnections
        << "\n";

    pool.recover(backend.name);

    std::cout
        << backend.name
        << " state="
        << toString(backend.state)
        << "\n";
}

void demonstrateHighAvailability() {
    printHeader("ACTIVE/STANDBY LOAD-BALANCER HIGH AVAILABILITY");

    HighAvailabilityPair pair(
        "lb-primary",
        "lb-standby"
    );

    std::cout
        << "initial_active="
        << pair.activeNode()
        << " epoch="
        << pair.generation()
        << "\n";

    pair.failover();

    std::cout
        << "after_failover="
        << pair.activeNode()
        << " epoch="
        << pair.generation()
        << "\n";

    pair.failover();

    std::cout
        << "after_failback="
        << pair.activeNode()
        << " epoch="
        << pair.generation()
        << "\n";
}

void demonstrateAvailabilityPolicy(
    const BackendPool& pool
) {
    printHeader("ZONE-AWARE HIGH AVAILABILITY POLICY");

    AvailabilityPolicy policy{
        3,
        2
    };

    std::cout
        << "minimum_healthy_backends="
        << policy.minimumHealthyBackends
        << "\n"
        << "minimum_healthy_zones="
        << policy.minimumHealthyZones
        << "\n"
        << "service_permitted="
        << std::boolalpha
        << policy.permitsService(pool)
        << "\n";
}

void printOperationsReport(const BackendPool& pool) {
    printHeader("OPERATIONS REPORT");

    std::cout
        << std::left
        << std::setw(14)
        << "Backend"
        << std::setw(12)
        << "State"
        << std::setw(10)
        << "Requests"
        << std::setw(10)
        << "Failures"
        << std::setw(12)
        << "Connections"
        << "AvgLatency\n";

    for (const Backend& backend : pool.all()) {
        std::cout
            << std::left
            << std::setw(14)
            << backend.name
            << std::setw(12)
            << toString(backend.state)
            << std::setw(10)
            << backend.requests
            << std::setw(10)
            << backend.failures
            << std::setw(12)
            << backend.activeConnections
            << std::fixed
            << std::setprecision(2)
            << backend.averageLatency()
            << " ms\n";
    }
}

void runAssertions() {
    /*
     * Small executable invariants catch regressions in the core model without
     * introducing an external testing framework.
     */
    BackendPool pool({
        {
            "test-a",
            "10.10.0.1",
            8080,
            1,
            "zone-a",
            "api"
        },
        {
            "test-b",
            "10.10.0.2",
            8080,
            1,
            "zone-b",
            "api"
        }
    });

    LoadBalancer loadBalancer(
        pool,
        Algorithm::RoundRobin
    );

    Backend& first =
        loadBalancer.openL4Connection(
            "assert-1",
            "192.0.2.1"
        );

    Backend& second =
        loadBalancer.openL4Connection(
            "assert-2",
            "192.0.2.2"
        );

    if (first.name == second.name) {
        throw std::runtime_error(
            "Round-robin invariant failed."
        );
    }

    if (
        first.activeConnections != 1 ||
        second.activeConnections != 1
    ) {
        throw std::runtime_error(
            "Connection accounting invariant failed."
        );
    }

    loadBalancer.closeL4Connection("assert-1");

    if (first.activeConnections != 0) {
        throw std::runtime_error(
            "Connection cleanup invariant failed."
        );
    }

    pool.find("test-b").state =
        BackendState::Unhealthy;

    std::vector<Backend*> healthy =
        pool.healthyBackends();

    if (healthy.size() != 1 || healthy.front()->name != "test-a") {
        throw std::runtime_error(
            "Health filtering invariant failed."
        );
    }
}

int main() {
    try {
        runAssertions();

        BackendPool pool({
            {
                "api-a",
                "10.0.1.10",
                8080,
                3,
                "zone-a",
                "api"
            },
            {
                "api-b",
                "10.0.1.11",
                8080,
                2,
                "zone-b",
                "api"
            },
            {
                "api-c",
                "10.0.2.10",
                8080,
                1,
                "zone-b",
                "api"
            },
            {
                "edge-a",
                "10.0.9.10",
                8080,
                1,
                "zone-a",
                "edge"
            },
            {
                "admin-a",
                "10.0.8.10",
                8080,
                1,
                "zone-a",
                "admin"
            }
        });

        std::cout
            << "LOAD BALANCING SYSTEM CASE STUDY\n";

        demonstrateHealthMonitoring(pool);
        demonstrateL4(pool);
        demonstrateL7(pool);
        demonstrateLeastConnections(pool);
        demonstrateDraining(pool);
        demonstrateHighAvailability();
        demonstrateAvailabilityPolicy(pool);
        printOperationsReport(pool);

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal configuration or runtime error: "
            << error.what()
            << "\n";

        return 1;
    }
}
