#include <algorithm>
#include <chrono>
#include <deque>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

enum class DatabaseType {
    KeyValue,
    Document,
    WideColumn,
    Graph
};

std::string toString(DatabaseType type) {
    switch (type) {
        case DatabaseType::KeyValue:
            return "key-value";
        case DatabaseType::Document:
            return "document";
        case DatabaseType::WideColumn:
            return "wide-column";
        case DatabaseType::Graph:
            return "graph";
    }
    throw std::logic_error("Unknown database type");
}

class ValidationError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class NotFoundError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

struct Product {
    std::string id;
    std::string name;
    std::string category;
    double price;
    std::vector<std::string> tags;
};

class KeyValueStore {
private:
    std::unordered_map<std::string, std::string> values_;
    std::unordered_map<std::string, std::chrono::steady_clock::time_point> expiry_;

public:
    void put(
        const std::string& key,
        const std::string& value,
        std::optional<int> ttlSeconds = std::nullopt
    ) {
        if (key.empty() || key.size() > 256) {
            throw ValidationError("Key must contain 1-256 characters");
        }

        values_[key] = value;

        if (ttlSeconds.has_value()) {
            if (*ttlSeconds <= 0) {
                throw ValidationError("TTL must be positive");
            }

            expiry_[key] =
                std::chrono::steady_clock::now() +
                std::chrono::seconds(*ttlSeconds);
        } else {
            expiry_.erase(key);
        }
    }

    std::string get(const std::string& key) {
        auto value = values_.find(key);

        if (value == values_.end()) {
            throw NotFoundError("Key not found: " + key);
        }

        auto expiration = expiry_.find(key);
        if (expiration != expiry_.end() &&
            std::chrono::steady_clock::now() >= expiration->second) {
            erase(key);
            throw NotFoundError("Key expired: " + key);
        }

        return value->second;
    }

    void erase(const std::string& key) {
        values_.erase(key);
        expiry_.erase(key);
    }
};

class DocumentCollection {
private:
    std::unordered_map<std::string, Product> products_;

public:
    void insert(const Product& product) {
        if (product.id.empty() || product.name.empty()) {
            throw ValidationError("Product id and name are required");
        }

        if (product.price < 0.0) {
            throw ValidationError("Product price cannot be negative");
        }

        if (products_.contains(product.id)) {
            throw ValidationError("Duplicate product: " + product.id);
        }

        products_.emplace(product.id, product);
    }

    void updatePrice(const std::string& id, double newPrice) {
        if (newPrice < 0.0) {
            throw ValidationError("Price cannot be negative");
        }

        auto it = products_.find(id);
        if (it == products_.end()) {
            throw NotFoundError("Product not found: " + id);
        }

        it->second.price = newPrice;
    }

    std::vector<Product> findByCategory(const std::string& category) const {
        std::vector<Product> result;

        for (const auto& [id, product] : products_) {
            if (product.category == category) {
                result.push_back(product);
            }
        }

        return result;
    }
};

class WideColumnTable {
public:
    using Columns = std::unordered_map<std::string, double>;
    using Families = std::unordered_map<std::string, Columns>;

private:
    std::unordered_map<std::string, Families> rows_;

public:
    void put(
        const std::string& rowKey,
        const std::string& family,
        const std::string& column,
        double value
    ) {
        if (rowKey.empty() || family.empty() || column.empty()) {
            throw ValidationError("Row key, family, and column are required");
        }

        rows_[rowKey][family][column] = value;
    }

    std::vector<std::pair<std::string, Columns>>
    scanFamily(const std::string& family) const {
        std::vector<std::pair<std::string, Columns>> result;

        for (const auto& [rowKey, families] : rows_) {
            auto familyIt = families.find(family);
            if (familyIt != families.end()) {
                result.emplace_back(rowKey, familyIt->second);
            }
        }

        return result;
    }
};

struct Edge {
    std::string relation;
    std::string target;
};

class Graph {
private:
    std::unordered_set<std::string> nodes_;
    std::unordered_map<std::string, std::vector<Edge>> adjacency_;

public:
    void addNode(const std::string& id) {
        if (id.empty()) {
            throw ValidationError("Graph node id cannot be empty");
        }

        if (!nodes_.insert(id).second) {
            throw ValidationError("Duplicate graph node: " + id);
        }

        adjacency_[id];
    }

    void addEdge(
        const std::string& source,
        const std::string& relation,
        const std::string& target
    ) {
        if (!nodes_.contains(source) || !nodes_.contains(target)) {
            throw NotFoundError("Graph endpoint does not exist");
        }

        adjacency_[source].push_back({relation, target});
    }

    std::optional<std::vector<std::string>>
    shortestPath(
        const std::string& start,
        const std::string& target
    ) const {
        if (!nodes_.contains(start) || !nodes_.contains(target)) {
            throw NotFoundError("Graph endpoint does not exist");
        }

        std::deque<std::vector<std::string>> queue;
        std::unordered_set<std::string> visited;

        queue.push_back({start});
        visited.insert(start);

        while (!queue.empty()) {
            std::vector<std::string> path = std::move(queue.front());
            queue.pop_front();

            const std::string& current = path.back();

            if (current == target) {
                return path;
            }

            auto edges = adjacency_.find(current);
            if (edges == adjacency_.end()) {
                continue;
            }

            for (const auto& edge : edges->second) {
                if (visited.insert(edge.target).second) {
                    auto nextPath = path;
                    nextPath.push_back(edge.target);
                    queue.push_back(std::move(nextPath));
                }
            }
        }

        return std::nullopt;
    }
};

DatabaseType chooseArchitecture(
    bool keyValueAccess,
    bool flexibleDocuments,
    bool highVolumeRows,
    bool relationshipTraversal
) {
    if (relationshipTraversal) {
        return DatabaseType::Graph;
    }
    if (flexibleDocuments) {
        return DatabaseType::Document;
    }
    if (highVolumeRows) {
        return DatabaseType::WideColumn;
    }
    if (keyValueAccess) {
        return DatabaseType::KeyValue;
    }

    throw ValidationError("No database architecture selected");
}

int main() {
    try {
        KeyValueStore sessions;
        DocumentCollection catalog;
        WideColumnTable telemetry;
        Graph serviceGraph;

        sessions.put(
            "session:user-1001",
            R"({"user":"user-1001","role":"analyst"})",
            3600
        );

        catalog.insert({
            "p100",
            "Edge Gateway",
            "networking",
            149.50,
            {"iot", "gateway", "edge"}
        });

        catalog.insert({
            "p200",
            "Graph Sensor",
            "telemetry",
            89.00,
            {"sensor", "graph"}
        });

        catalog.updatePrice("p200", 92.50);

        telemetry.put(
            "device-001",
            "telemetry",
            "2026-10-31T12:00:00Z",
            44.1
        );
        telemetry.put(
            "device-001",
            "telemetry",
            "2026-10-31T12:05:00Z",
            45.2
        );
        telemetry.put(
            "device-002",
            "telemetry",
            "2026-10-31T12:00:00Z",
            38.5
        );

        for (const std::string& node :
             {"api", "orders", "inventory", "payments", "inventory-db"}) {
            serviceGraph.addNode(node);
        }

        serviceGraph.addEdge("api", "calls", "orders");
        serviceGraph.addEdge("orders", "calls", "inventory");
        serviceGraph.addEdge("orders", "calls", "payments");
        serviceGraph.addEdge("inventory", "reads", "inventory-db");

        std::cout << "Architecture selection\n";

        const std::vector<std::pair<std::string, DatabaseType>> cases = {
            {"Session state", chooseArchitecture(true, false, false, false)},
            {"Product catalog", chooseArchitecture(false, true, false, false)},
            {"Telemetry", chooseArchitecture(false, false, true, false)},
            {"Dependency graph", chooseArchitecture(false, false, false, true)}
        };

        for (const auto& [name, type] : cases) {
            std::cout << "- " << name << ": " << toString(type) << '\n';
        }

        std::cout << "\nKey-value\n";
        std::cout << sessions.get("session:user-1001") << '\n';

        std::cout << "\nDocument products in telemetry category\n";
        for (const auto& product : catalog.findByCategory("telemetry")) {
            std::cout << product.id << " " << product.name
                      << " $" << product.price << '\n';
        }

        std::cout << "\nWide-column telemetry rows\n";
        for (const auto& [rowKey, columns] :
             telemetry.scanFamily("telemetry")) {
            std::cout << rowKey << ": " << columns.size()
                      << " measurements\n";
        }

        std::cout << "\nGraph dependency path\n";
        auto path = serviceGraph.shortestPath("api", "inventory-db");

        if (path.has_value()) {
            for (std::size_t i = 0; i < path->size(); ++i) {
                if (i > 0) {
                    std::cout << " -> ";
                }
                std::cout << (*path)[i];
            }
            std::cout << '\n';
        }

        try {
            catalog.insert({
                "p100",
                "Duplicate",
                "invalid",
                1.0,
                {}
            });
        } catch (const ValidationError&) {
            std::cout << "\nDuplicate document rejected.\n";
        }

        try {
            sessions.get("missing");
        } catch (const NotFoundError&) {
            std::cout << "Missing key rejected.\n";
        }

        std::cout << "NoSQL case study completed successfully.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}
