#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
 * Storage Performance Governance Case Study
 *
 * Scenario:
 * A data platform receives storage requests from database, analytics,
 * backup, and archival workloads. The storage planner evaluates IOPS,
 * throughput, latency, caching, and storage tiers before assigning a
 * workload to a suitable tier.
 *
 * The implementation deliberately uses C++ data structures and algorithms
 * to model a policy engine rather than reproducing a scripting-language
 * benchmark.
 */

enum class Operation {
    Read,
    Write
};

enum class StorageTier {
    NVMe,
    SSD,
    HDD,
    Archive
};

std::string tierName(StorageTier tier) {
    switch (tier) {
        case StorageTier::NVMe: return "NVMe";
        case StorageTier::SSD: return "SSD";
        case StorageTier::HDD: return "HDD";
        case StorageTier::Archive: return "Archive";
    }

    throw std::logic_error("Unknown storage tier");
}

struct TierProfile {
    StorageTier tier;
    double maximumIops;
    double throughputMiBPerSecond;
    double baseLatencyMs;
    double monthlyCostPerGiB;
};

const std::vector<TierProfile> profiles = {
    {StorageTier::NVMe, 900000, 7000, 0.08, 0.12},
    {StorageTier::SSD, 120000, 1200, 0.45, 0.07},
    {StorageTier::HDD, 300, 250, 8.0, 0.025},
    {StorageTier::Archive, 50, 100, 80.0, 0.008}
};

const TierProfile& profileFor(StorageTier tier) {
    auto it = std::find_if(
        profiles.begin(),
        profiles.end(),
        [tier](const TierProfile& profile) {
            return profile.tier == tier;
        }
    );

    if (it == profiles.end()) {
        throw std::invalid_argument("Storage tier does not exist");
    }

    return *it;
}

struct StorageRequest {
    std::string workloadName;
    Operation operation;
    std::size_t requestSizeBytes;
    double requestsPerSecond;
    double latencyTargetMs;
    bool sequential;
};

struct Evaluation {
    StorageTier tier;
    double sustainableIops;
    double throughputMiBPerSecond;
    double expectedLatencyMs;
    double monthlyCost;
    bool acceptable;
    std::vector<std::string> reasons;
};

double bandwidthLimitedIops(
    const TierProfile& profile,
    std::size_t requestSizeBytes
) {
    if (requestSizeBytes == 0) {
        throw std::invalid_argument("Request size cannot be zero");
    }

    constexpr double MiB = 1024.0 * 1024.0;

    return profile.throughputMiBPerSecond * MiB /
           static_cast<double>(requestSizeBytes);
}

Evaluation evaluateRequest(
    const StorageRequest& request,
    StorageTier tier,
    double capacityGiB
) {
    if (request.requestSizeBytes == 0) {
        throw std::invalid_argument("Request size cannot be zero");
    }

    if (request.requestsPerSecond <= 0) {
        throw std::invalid_argument("Request rate must be positive");
    }

    const auto& profile = profileFor(tier);

    const double bandwidthIops =
        bandwidthLimitedIops(profile, request.requestSizeBytes);

    const double sustainableIops =
        std::min(profile.maximumIops, bandwidthIops);

    const double expectedLatency =
        profile.baseLatencyMs +
        1000.0 / sustainableIops;

    Evaluation evaluation{
        tier,
        sustainableIops,
        profile.throughputMiBPerSecond,
        expectedLatency,
        capacityGiB * profile.monthlyCostPerGiB,
        true,
        {}
    };

    if (request.requestsPerSecond > sustainableIops) {
        evaluation.acceptable = false;
        evaluation.reasons.push_back(
            "Requested IOPS exceed the tier's sustainable request rate"
        );
    }

    if (expectedLatency > request.latencyTargetMs) {
        evaluation.acceptable = false;
        evaluation.reasons.push_back(
            "Estimated latency exceeds the workload target"
        );
    }

    if (request.sequential) {
        evaluation.reasons.push_back(
            "Sequential access can exploit the tier's bandwidth efficiently"
        );
    } else {
        evaluation.reasons.push_back(
            "Random access makes IOPS and latency more important"
        );
    }

    return evaluation;
}

class LRUCache {
private:
    struct Entry {
        std::string key;
        std::size_t bytes;
    };

    std::size_t capacityBytes;
    std::size_t currentBytes{0};
    std::vector<Entry> entries;

public:
    explicit LRUCache(std::size_t capacityBytes)
        : capacityBytes(capacityBytes) {
        if (capacityBytes == 0) {
            throw std::invalid_argument("Cache capacity must be positive");
        }
    }

    bool get(const std::string& key) {
        auto it = std::find_if(
            entries.begin(),
            entries.end(),
            [&key](const Entry& entry) {
                return entry.key == key;
            }
        );

        if (it == entries.end()) {
            return false;
        }

        Entry entry = *it;
        entries.erase(it);
        entries.push_back(entry);
        return true;
    }

    void put(const std::string& key, std::size_t bytes) {
        if (bytes > capacityBytes) {
            return;
        }

        auto existing = std::find_if(
            entries.begin(),
            entries.end(),
            [&key](const Entry& entry) {
                return entry.key == key;
            }
        );

        if (existing != entries.end()) {
            currentBytes -= existing->bytes;
            entries.erase(existing);
        }

        while (
            currentBytes + bytes > capacityBytes &&
            !entries.empty()
        ) {
            currentBytes -= entries.front().bytes;
            entries.erase(entries.begin());
        }

        entries.push_back({key, bytes});
        currentBytes += bytes;
    }

    std::size_t size() const {
        return entries.size();
    }
};

struct CacheExperiment {
    std::size_t hits{0};
    std::size_t misses{0};

    double hitRate() const {
        const std::size_t total = hits + misses;
        return total == 0
            ? 0.0
            : static_cast<double>(hits) / total;
    }
};

CacheExperiment simulateCache(
    std::size_t operations,
    std::size_t hotSetSize,
    std::size_t cacheCapacity
) {
    if (operations == 0 || hotSetSize == 0 || cacheCapacity == 0) {
        throw std::invalid_argument("Cache experiment parameters must be positive");
    }

    LRUCache cache(cacheCapacity);
    CacheExperiment result;

    std::mt19937 generator(42);
    std::uniform_int_distribution<std::size_t> distribution(
        0,
        hotSetSize - 1
    );

    for (std::size_t i = 0; i < operations; ++i) {
        const std::string key =
            "block-" + std::to_string(distribution(generator));

        if (cache.get(key)) {
            ++result.hits;
        } else {
            ++result.misses;
            cache.put(key, 4096);
        }
    }

    return result;
}

class WorkloadPlanner {
private:
    std::map<std::string, StorageRequest> requests;

public:
    void addWorkload(const StorageRequest& request) {
        if (request.workloadName.empty()) {
            throw std::invalid_argument("Workload name cannot be empty");
        }

        if (request.requestSizeBytes == 0) {
            throw std::invalid_argument("Workload request size cannot be zero");
        }

        requests.insert_or_assign(request.workloadName, request);
    }

    std::optional<StorageTier> chooseTier(
        const std::string& workloadName,
        double capacityGiB
    ) const {
        const auto it = requests.find(workloadName);

        if (it == requests.end()) {
            throw std::out_of_range("Workload does not exist");
        }

        const auto& request = it->second;

        std::optional<Evaluation> best;

        for (const auto& profile : profiles) {
            Evaluation current =
                evaluateRequest(request, profile.tier, capacityGiB);

            if (!current.acceptable) {
                continue;
            }

            if (
                !best.has_value() ||
                current.monthlyCost < best->monthlyCost
            ) {
                best = current;
            }
        }

        if (!best.has_value()) {
            return std::nullopt;
        }

        return best->tier;
    }

    void explain(const std::string& workloadName, double capacityGiB) const {
        const auto it = requests.find(workloadName);

        if (it == requests.end()) {
            throw std::out_of_range("Workload does not exist");
        }

        std::cout << "\nWorkload: " << workloadName << '\n';

        for (const auto& profile : profiles) {
            const Evaluation evaluation =
                evaluateRequest(it->second, profile.tier, capacityGiB);

            std::cout
                << std::left
                << std::setw(10)
                << tierName(profile.tier)
                << " IOPS="
                << std::setw(10)
                << std::fixed
                << std::setprecision(0)
                << evaluation.sustainableIops
                << " latency="
                << std::setprecision(3)
                << evaluation.expectedLatencyMs
                << " ms cost=$"
                << std::setprecision(2)
                << evaluation.monthlyCost
                << " acceptable="
                << (evaluation.acceptable ? "yes" : "no")
                << '\n';

            for (const auto& reason : evaluation.reasons) {
                std::cout << "    " << reason << '\n';
            }
        }

        const auto selected = chooseTier(workloadName, capacityGiB);

        if (selected.has_value()) {
            std::cout
                << "Selected tier: "
                << tierName(*selected)
                << '\n';
        } else {
            std::cout
                << "No tier satisfies all declared performance requirements.\n";
        }
    }
};

void demonstrateMetrics() {
    std::cout << "=== Fundamental Performance Relationships ===\n";

    constexpr double seconds = 2.0;
    constexpr std::size_t operations = 200000;
    constexpr std::size_t requestSize = 4096;

    const double iops = operations / seconds;
    const double throughput =
        operations * requestSize / (1024.0 * 1024.0) / seconds;

    std::cout << "IOPS: " << iops << '\n';
    std::cout << "Throughput: " << throughput << " MiB/s\n";

    std::cout
        << "The request size determines how IOPS translate into data rate.\n";
}

void demonstrateCache() {
    std::cout << "\n=== Cache Locality Experiment ===\n";

    const auto smallCache =
        simulateCache(10000, 256, 32 * 4096);

    const auto largeCache =
        simulateCache(10000, 256, 256 * 4096);

    std::cout
        << "32-block cache hit rate: "
        << std::fixed
        << std::setprecision(2)
        << smallCache.hitRate() * 100
        << "%\n";

    std::cout
        << "256-block cache hit rate: "
        << largeCache.hitRate() * 100
        << "%\n";

    std::cout
        << "The cache improves effective latency only when the workload "
        << "reuses data within the cache's working set.\n";
}

void demonstrateTiming() {
    std::cout << "\n=== CPU Measurement Overhead ===\n";

    const auto start = std::chrono::steady_clock::now();

    volatile std::size_t checksum = 0;

    for (std::size_t i = 0; i < 2'000'000; ++i) {
        checksum ^= i;
    }

    const auto end = std::chrono::steady_clock::now();

    const std::chrono::duration<double, std::milli> elapsed =
        end - start;

    std::cout
        << "Measured CPU interval: "
        << elapsed.count()
        << " ms, checksum="
        << checksum
        << '\n';

    std::cout
        << "A storage benchmark must distinguish application CPU time "
        << "from actual device latency.\n";
}

int main() {
    try {
        demonstrateMetrics();
        demonstrateCache();
        demonstrateTiming();

        WorkloadPlanner planner;

        planner.addWorkload({
            "OLTP database",
            Operation::Read,
            4096,
            80000,
            2.0,
            false
        });

        planner.addWorkload({
            "Analytics scan",
            Operation::Read,
            1024 * 1024,
            1000,
            20.0,
            true
        });

        planner.addWorkload({
            "Backup repository",
            Operation::Write,
            4 * 1024 * 1024,
            50,
            100.0,
            true
        });

        planner.addWorkload({
            "Long-term archive",
            Operation::Write,
            1024 * 1024,
            5,
            500.0,
            true
        });

        planner.explain("OLTP database", 500);
        planner.explain("Analytics scan", 500);
        planner.explain("Backup repository", 2000);
        planner.explain("Long-term archive", 10000);

        std::cout << "\n=== Engineering Trade-offs ===\n";
        std::cout
            << "IOPS dominates small random I/O decisions.\n"
            << "Throughput dominates large sequential transfers.\n"
            << "Latency targets must be evaluated separately from peak bandwidth.\n"
            << "Caching can reduce backend load but requires a workload with locality.\n"
            << "Higher queue depth can expose parallelism but does not remove device saturation.\n"
            << "Tiering converts workload characteristics into cost/performance decisions.\n";
    }
    catch (const std::exception& error) {
        std::cerr
            << "Storage planning error: "
            << error.what()
            << '\n';
        return 1;
    }

    return 0;
}
