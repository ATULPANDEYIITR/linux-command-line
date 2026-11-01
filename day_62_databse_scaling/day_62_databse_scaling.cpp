#include <algorithm>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

enum class PartitionStrategy {
    Hash,
    Range
};

enum class MergeCondition {
    Ready,
    Blocked
};

struct Order {
    std::uint64_t id;
    std::uint64_t customerId;
    double amount;
    std::string region;
};

struct DatabaseNode {
    std::string id;
    std::size_t capacity;
    std::size_t used{0};
    bool healthy{true};

    double utilization() const {
        if (capacity == 0) {
            return 1.0;
        }
        return static_cast<double>(used) / capacity;
    }

    bool available() const {
        return healthy && used < capacity;
    }
};

class ScalingError : public std::runtime_error {
public:
    explicit ScalingError(const std::string& message)
        : std::runtime_error(message) {}
};

class RepositoryGovernance {
private:
    std::vector<DatabaseNode> nodes_;

public:
    void addNode(std::string id, std::size_t capacity) {
        if (id.empty()) {
            throw ScalingError("Node ID cannot be empty");
        }
        if (capacity == 0) {
            throw ScalingError("Node capacity must be positive");
        }

        const auto duplicate = std::find_if(
            nodes_.begin(),
            nodes_.end(),
            [&](const DatabaseNode& node) { return node.id == id; }
        );

        if (duplicate != nodes_.end()) {
            throw ScalingError("Duplicate node: " + id);
        }

        nodes_.push_back({std::move(id), capacity, 0, true});
    }

    void resizeNode(const std::string& id, std::size_t newCapacity) {
        if (newCapacity == 0) {
            throw ScalingError("New capacity must be positive");
        }

        auto it = std::find_if(
            nodes_.begin(),
            nodes_.end(),
            [&](const DatabaseNode& node) { return node.id == id; }
        );

        if (it == nodes_.end()) {
            throw ScalingError("Unknown node: " + id);
        }

        if (newCapacity < it->used) {
            throw ScalingError("Capacity cannot be below current usage");
        }

        it->capacity = newCapacity;
    }

    std::string routeRequest() {
        auto it = std::min_element(
            nodes_.begin(),
            nodes_.end(),
            [](const DatabaseNode& a, const DatabaseNode& b) {
                if (!a.available()) {
                    return false;
                }
                if (!b.available()) {
                    return true;
                }
                return a.utilization() < b.utilization();
            }
        );

        if (it == nodes_.end() || !it->available()) {
            throw ScalingError("No healthy node has available capacity");
        }

        ++it->used;
        return it->id;
    }

    void markUnhealthy(const std::string& id) {
        auto it = std::find_if(
            nodes_.begin(),
            nodes_.end(),
            [&](const DatabaseNode& node) { return node.id == id; }
        );

        if (it == nodes_.end()) {
            throw ScalingError("Unknown node: " + id);
        }

        it->healthy = false;
    }

    void print() const {
        for (const auto& node : nodes_) {
            std::cout
                << node.id
                << " capacity=" << node.capacity
                << " used=" << node.used
                << " utilization=" << std::fixed << std::setprecision(1)
                << node.utilization() * 100.0 << "%"
                << " healthy=" << std::boolalpha << node.healthy
                << '\n';
        }
    }

    std::size_t nodeCount() const {
        return nodes_.size();
    }
};

class Partitioner {
private:
    PartitionStrategy strategy_;
    std::size_t partitionCount_;

public:
    Partitioner(PartitionStrategy strategy, std::size_t partitionCount)
        : strategy_(strategy), partitionCount_(partitionCount) {
        if (partitionCount == 0) {
            throw ScalingError("Partition count must be positive");
        }
    }

    std::size_t locate(std::uint64_t customerId) const {
        if (strategy_ == PartitionStrategy::Hash) {
            // Explicit unsigned arithmetic provides deterministic behavior
            // without depending on implementation-specific string hashes.
            std::uint64_t mixed = customerId;
            mixed ^= mixed >> 33;
            mixed *= 0xff51afd7ed558ccdULL;
            mixed ^= mixed >> 33;
            return static_cast<std::size_t>(mixed % partitionCount_);
        }

        return std::min<std::size_t>(
            static_cast<std::size_t>(customerId / 1000),
            partitionCount_ - 1
        );
    }
};

class ShardMap {
private:
    std::vector<std::unordered_map<std::uint64_t, Order>> shards_;

public:
    explicit ShardMap(std::size_t shardCount)
        : shards_(shardCount) {
        if (shardCount == 0) {
            throw ScalingError("Shard count must be positive");
        }
    }

    std::size_t shardFor(std::uint64_t customerId) const {
        std::uint64_t value = customerId;
        value ^= value >> 33;
        value *= 0xff51afd7ed558ccdULL;
        value ^= value >> 33;
        return static_cast<std::size_t>(value % shards_.size());
    }

    std::size_t insert(Order order) {
        const auto shard = shardFor(order.customerId);

        auto [it, inserted] =
            shards_[shard].emplace(order.id, std::move(order));

        if (!inserted) {
            throw ScalingError("Duplicate order ID");
        }

        return shard;
    }

    std::optional<Order> find(
        std::uint64_t orderId,
        std::uint64_t customerId
    ) const {
        const auto shard = shardFor(customerId);
        const auto it = shards_[shard].find(orderId);

        if (it == shards_[shard].end()) {
            return std::nullopt;
        }

        return it->second;
    }

    std::vector<std::size_t> distribution() const {
        std::vector<std::size_t> result;
        result.reserve(shards_.size());

        for (const auto& shard : shards_) {
            result.push_back(shard.size());
        }

        return result;
    }
};

std::vector<Order> generateOrders(std::size_t count) {
    std::mt19937_64 generator(42);
    std::uniform_int_distribution<std::uint64_t> customer(1, 9999);
    std::uniform_real_distribution<double> amount(10.0, 5000.0);

    const std::vector<std::string> regions{
        "north", "south", "east", "west"
    };

    std::vector<Order> orders;
    orders.reserve(count);

    for (std::size_t i = 1; i <= count; ++i) {
        orders.push_back({
            i,
            customer(generator),
            amount(generator),
            regions[(i - 1) % regions.size()]
        });
    }

    return orders;
}

void printDistribution(const std::vector<std::size_t>& distribution) {
    std::cout << '[';

    for (std::size_t i = 0; i < distribution.size(); ++i) {
        if (i != 0) {
            std::cout << ", ";
        }
        std::cout << distribution[i];
    }

    std::cout << "]\n";
}

int main() {
    try {
        std::cout << "DATABASE SCALING CASE STUDY\n\n";

        /*
         * Vertical scaling increases the capacity of an existing machine.
         * It is operationally simple but has a physical upper bound.
         */
        RepositoryGovernance cluster;
        cluster.addNode("db-primary", 100);
        cluster.resizeNode("db-primary", 200);

        /*
         * Horizontal scaling adds independent nodes. Routing chooses the
         * least-utilized healthy node, providing basic load distribution.
         */
        cluster.addNode("db-node-02", 100);
        cluster.addNode("db-node-03", 100);

        for (int i = 0; i < 120; ++i) {
            cluster.routeRequest();
        }

        std::cout << "1. Horizontal capacity\n";
        cluster.print();

        /*
         * Partitioning creates logical data segments. The partition function
         * can be range-based or hash-based without requiring separate servers.
         */
        const auto orders = generateOrders(500);
        Partitioner partitioner(PartitionStrategy::Hash, 16);

        std::vector<std::size_t> partitionCounts(16, 0);

        for (const auto& order : orders) {
            ++partitionCounts[partitioner.locate(order.customerId)];
        }

        std::cout << "\n2. Logical partitioning\n";
        printDistribution(partitionCounts);

        /*
         * Sharding is a physical distribution decision: each bucket represents
         * an independently managed database shard.
         */
        ShardMap store(8);

        for (const auto& order : orders) {
            store.insert(order);
        }

        const auto shardDistribution = store.distribution();

        std::cout << "\n3. Sharding\n";
        printDistribution(shardDistribution);

        const auto& selected = orders.at(250);
        const auto result =
            store.find(selected.id, selected.customerId);

        if (!result.has_value() || result->id != selected.id) {
            throw ScalingError("Point lookup invariant failed");
        }

        std::cout
            << "Point lookup succeeded for order "
            << selected.id << '\n';

        /*
         * A failed node must not receive new work. Existing connections would
         * require separate recovery/retry logic in a real database service.
         */
        cluster.markUnhealthy("db-node-02");

        std::cout << "\n4. Failure handling\n";
        for (int i = 0; i < 10; ++i) {
            cluster.routeRequest();
        }
        cluster.print();

        /*
         * The total row count must remain invariant across distribution.
         * This is an important property when rebalancing or migrating shards.
         */
        const auto totalRows = std::accumulate(
            shardDistribution.begin(),
            shardDistribution.end(),
            std::size_t{0}
        );

        if (totalRows != orders.size()) {
            throw ScalingError("Shard row-count invariant failed");
        }

        std::cout << "\nScaling model completed successfully.\n";
        return 0;
    }
    catch (const std::exception& error) {
        std::cerr << "Failure: " << error.what() << '\n';
        return 1;
    }
}
