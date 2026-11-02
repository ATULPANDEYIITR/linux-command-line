#include <algorithm>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using Clock = std::chrono::steady_clock;

enum class EntryState {
    Fresh,
    Stale,
    Missing
};

enum class MergeResult {
    Hit,
    Miss,
    Stale
};

struct CacheStats {
    std::size_t hits = 0;
    std::size_t misses = 0;
    std::size_t stale = 0;
    std::size_t writes = 0;
    std::size_t evictions = 0;
    std::size_t invalidations = 0;
};

struct Product {
    int id;
    std::string name;
    double price;
    int stock;
    std::uint64_t version;

    void validate() const {
        if (id <= 0) {
            throw std::invalid_argument("product id must be positive");
        }
        if (name.empty()) {
            throw std::invalid_argument("product name cannot be empty");
        }
        if (price < 0.0) {
            throw std::invalid_argument("price cannot be negative");
        }
        if (stock < 0) {
            throw std::invalid_argument("stock cannot be negative");
        }
        if (version == 0) {
            throw std::invalid_argument("version must be positive");
        }
    }
};

struct CacheEntry {
    Product value;
    Clock::time_point created;
    std::optional<Clock::time_point> expires;
    std::uint64_t version;
    std::set<std::string> tags;

    bool expired() const {
        return expires.has_value() && Clock::now() >= *expires;
    }
};

class LruCache {
public:
    explicit LruCache(std::size_t capacity, std::chrono::seconds ttl)
        : capacity_(capacity), ttl_(ttl) {
        if (capacity == 0) {
            throw std::invalid_argument("cache capacity must be positive");
        }
        if (ttl.count() <= 0) {
            throw std::invalid_argument("ttl must be positive");
        }
    }

    MergeResult get(const std::string& key, Product& output) {
        auto it = entries_.find(key);

        if (it == entries_.end()) {
            ++stats_.misses;
            return MergeResult::Miss;
        }

        if (it->second.expired()) {
            entries_.erase(it);
            ++stats_.stale;
            return MergeResult::Stale;
        }

        touch(key);
        output = it->second.value;
        ++stats_.hits;
        return MergeResult::Hit;
    }

    void set(
        const std::string& key,
        const Product& product,
        const std::set<std::string>& tags = {}
    ) {
        product.validate();

        CacheEntry entry{
            product,
            Clock::now(),
            Clock::now() + ttl_,
            product.version,
            tags
        };

        entries_[key] = std::move(entry);
        touch(key);
        ++stats_.writes;

        while (entries_.size() > capacity_) {
            auto victim = accessOrder_.begin();
            entries_.erase(victim->second);
            accessOrder_.erase(victim);
            ++stats_.evictions;
        }
    }

    bool erase(const std::string& key) {
        auto it = entries_.find(key);

        if (it == entries_.end()) {
            return false;
        }

        entries_.erase(it);
        removeFromOrder(key);
        ++stats_.invalidations;
        return true;
    }

    std::size_t invalidateTag(const std::string& tag) {
        std::vector<std::string> victims;

        for (const auto& [key, entry] : entries_) {
            if (entry.tags.contains(tag)) {
                victims.push_back(key);
            }
        }

        for (const auto& key : victims) {
            erase(key);
        }

        return victims.size();
    }

    const CacheStats& stats() const {
        return stats_;
    }

    std::size_t size() const {
        return entries_.size();
    }

private:
    std::size_t capacity_;
    std::chrono::seconds ttl_;

    std::unordered_map<std::string, CacheEntry> entries_;

    // Ordered sequence is maintained separately from the value map so
    // cache lookup remains average O(1), while eviction is O(1).
    std::map<std::uint64_t, std::string> accessOrder_;
    std::unordered_map<std::string, std::uint64_t> accessIndex_;
    std::uint64_t sequence_ = 0;

    CacheStats stats_;

    void touch(const std::string& key) {
        removeFromOrder(key);
        ++sequence_;
        accessOrder_[sequence_] = key;
        accessIndex_[key] = sequence_;
    }

    void removeFromOrder(const std::string& key) {
        auto it = accessIndex_.find(key);

        if (it == accessIndex_.end()) {
            return;
        }

        accessOrder_.erase(it->second);
        accessIndex_.erase(it);
    }
};

class ProductRepository {
public:
    ProductRepository() {
        products_.emplace(
            101,
            Product{101, "Edge Router", 249.99, 18, 1}
        );
        products_.emplace(
            102,
            Product{102, "Secure Gateway", 499.00, 7, 1}
        );
        products_.emplace(
            103,
            Product{103, "Telemetry Node", 129.50, 31, 1}
        );
    }

    Product find(int id) const {
        auto it = products_.find(id);

        if (it == products_.end()) {
            throw std::out_of_range("product does not exist");
        }

        return it->second;
    }

    Product updatePrice(int id, double price) {
        if (price < 0.0) {
            throw std::invalid_argument("price cannot be negative");
        }

        auto& product = products_.at(id);
        product.price = price;
        ++product.version;
        product.validate();
        return product;
    }

    Product purchase(int id, int quantity) {
        if (quantity <= 0) {
            throw std::invalid_argument("quantity must be positive");
        }

        auto& product = products_.at(id);

        if (product.stock < quantity) {
            throw std::runtime_error("insufficient stock");
        }

        product.stock -= quantity;
        ++product.version;
        product.validate();
        return product;
    }

private:
    std::unordered_map<int, Product> products_;
};

class GovernanceAwareCache {
public:
    GovernanceAwareCache(
        ProductRepository& repository,
        LruCache& cache
    )
        : repository_(repository), cache_(cache) {}

    Product get(int id) {
        const std::string key = keyFor(id);
        Product product{};

        const MergeResult result = cache_.get(key, product);

        if (result == MergeResult::Hit) {
            return product;
        }

        product = repository_.find(id);

        cache_.set(
            key,
            product,
            {"product", "product:" + std::to_string(id)}
        );

        return product;
    }

    Product updatePrice(int id, double price) {
        // The source of truth changes first. Invalidation occurs only after
        // the authoritative mutation succeeds.
        Product updated = repository_.updatePrice(id, price);
        cache_.erase(keyFor(id));
        return updated;
    }

    Product purchase(int id, int quantity) {
        Product updated = repository_.purchase(id, quantity);
        cache_.erase(keyFor(id));
        return updated;
    }

private:
    ProductRepository& repository_;
    LruCache& cache_;

    static std::string keyFor(int id) {
        if (id <= 0) {
            throw std::invalid_argument("invalid product id");
        }
        return "product:" + std::to_string(id);
    }
};

class CacheStampedeGuard {
public:
    explicit CacheStampedeGuard(std::size_t maxRefreshers)
        : maxRefreshers_(maxRefreshers) {
        if (maxRefreshers == 0) {
            throw std::invalid_argument("maxRefreshers must be positive");
        }
    }

    bool tryAcquire(const std::string& key) {
        if (active_.size() >= maxRefreshers_) {
            return false;
        }

        return active_.insert(key).second;
    }

    void release(const std::string& key) {
        active_.erase(key);
    }

private:
    std::size_t maxRefreshers_;
    std::set<std::string> active_;
};

static void printProduct(const Product& p) {
    std::cout
        << p.id << " | "
        << p.name << " | price=" << std::fixed << std::setprecision(2)
        << p.price << " | stock=" << p.stock
        << " | version=" << p.version << '\n';
}

int main() {
    try {
        ProductRepository repository;
        LruCache cache(2, std::chrono::seconds(60));
        GovernanceAwareCache service(repository, cache);

        std::cout << "=== Cache-aside reads ===\n";

        Product first = service.get(101);
        printProduct(first);

        Product second = service.get(101);
        printProduct(second);

        std::cout << "\n=== Capacity and LRU eviction ===\n";

        service.get(102);
        service.get(103);

        std::cout
            << "cache size after three product keys with capacity 2: "
            << cache.size() << '\n';

        std::cout << "\n=== Authoritative mutation ===\n";

        Product changed = service.updatePrice(101, 279.99);
        printProduct(changed);

        Product refreshed = service.get(101);
        printProduct(refreshed);

        std::cout << "\n=== Transactional failure behavior ===\n";

        try {
            service.purchase(102, 100);
        } catch (const std::exception& ex) {
            std::cout << "expected failure: " << ex.what() << '\n';
        }

        std::cout << "\n=== Tag invalidation ===\n";

        service.get(101);
        service.get(103);

        std::size_t invalidated = cache.invalidateTag("product");
        std::cout << "invalidated entries: " << invalidated << '\n';

        std::cout << "\n=== Stampede guard ===\n";

        CacheStampedeGuard guard(1);

        if (guard.tryAcquire("product:101")) {
            std::cout << "refresh lease acquired\n";

            if (!guard.tryAcquire("product:101")) {
                std::cout << "duplicate refresh prevented\n";
            }

            guard.release("product:101");
        }

        std::cout << "\n=== Cache statistics ===\n";

        const CacheStats& stats = cache.stats();
        const std::size_t requests =
            stats.hits + stats.misses + stats.stale;

        const double hitRate =
            requests == 0
                ? 0.0
                : static_cast<double>(stats.hits) / requests;

        std::cout
            << "hits=" << stats.hits
            << " misses=" << stats.misses
            << " stale=" << stats.stale
            << " writes=" << stats.writes
            << " evictions=" << stats.evictions
            << " invalidations=" << stats.invalidations
            << " hit_rate=" << std::setprecision(3)
            << hitRate << '\n';

        if (stats.hits == 0) {
            throw std::logic_error("cache did not record a hit");
        }

        if (hitRate <= 0.0 || hitRate > 1.0) {
            throw std::logic_error("invalid hit rate");
        }

        std::cout << "\nScenario completed successfully.\n";
    } catch (const std::exception& ex) {
        std::cerr << "fatal error: " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
