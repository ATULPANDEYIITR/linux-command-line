#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

/*
 * Data Warehousing in C++17.
 *
 * Scenario:
 *   Operational retail sales are transformed into a compact columnar fact
 *   store. The engine validates source records, resolves dimension keys,
 *   rejects duplicates, commits batches atomically and performs OLAP
 *   aggregations.
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic data_warehouse.cpp -o warehouse
 */

enum class SaleStatus {
    Completed,
    Cancelled,
    Pending
};

struct Customer {
    std::string id;
    std::string name;
    std::string region;
};

struct Product {
    std::string id;
    std::string name;
    std::string category;
};

struct SaleEvent {
    std::uint64_t sequence;
    std::string sourceSaleId;
    std::string customerId;
    std::string productId;
    std::string saleDate;
    std::int64_t quantity;
    std::int64_t unitPriceCents;
    SaleStatus status;
};

struct RejectedRecord {
    std::string sourceSaleId;
    std::string reason;
};

struct ColumnarFacts {
    /*
     * Each attribute is stored in a separate vector. This structure-of-arrays
     * representation can improve cache locality for analytical scans that
     * read only a subset of fact attributes.
     */
    std::vector<std::string> saleIds;
    std::vector<std::uint64_t> sourceSequences;
    std::vector<std::string> customerIds;
    std::vector<std::string> productIds;
    std::vector<std::string> saleDates;
    std::vector<std::int64_t> quantities;
    std::vector<std::int64_t> unitPrices;
    std::vector<std::int64_t> grossAmounts;

    std::unordered_set<std::string> loadedSaleIds;

    std::size_t size() const {
        return saleIds.size();
    }

    void append(const SaleEvent& event, std::int64_t grossCents) {
        saleIds.push_back(event.sourceSaleId);
        sourceSequences.push_back(event.sequence);
        customerIds.push_back(event.customerId);
        productIds.push_back(event.productId);
        saleDates.push_back(event.saleDate);
        quantities.push_back(event.quantity);
        unitPrices.push_back(event.unitPriceCents);
        grossAmounts.push_back(grossCents);
        loadedSaleIds.insert(event.sourceSaleId);
    }

    void assertConsistent() const {
        const std::size_t expected = saleIds.size();

        if (sourceSequences.size() != expected ||
            customerIds.size() != expected ||
            productIds.size() != expected ||
            saleDates.size() != expected ||
            quantities.size() != expected ||
            unitPrices.size() != expected ||
            grossAmounts.size() != expected ||
            loadedSaleIds.size() != expected) {
            throw std::logic_error("Columnar fact store is inconsistent");
        }
    }
};

struct GroupKey {
    std::string region;
    std::string product;

    bool operator<(const GroupKey& other) const {
        if (region != other.region) {
            return region < other.region;
        }
        return product < other.product;
    }
};

struct Aggregate {
    std::int64_t units = 0;
    std::int64_t revenueCents = 0;
    std::size_t saleCount = 0;
};

struct BatchMetrics {
    std::size_t extracted = 0;
    std::size_t loaded = 0;
    std::size_t unchanged = 0;
    std::size_t rejected = 0;
    std::size_t skipped = 0;
};

class WarehouseEngine {
private:
    std::map<std::string, Customer> customers;
    std::map<std::string, Product> products;
    ColumnarFacts facts;
    std::vector<RejectedRecord> quarantine;
    std::uint64_t lastSequence = 0;

    static bool isValidDate(const std::string& value) {
        if (value.size() != 10 ||
            value[4] != '-' ||
            value[7] != '-') {
            return false;
        }

        for (std::size_t i = 0; i < value.size(); ++i) {
            if (i == 4 || i == 7) {
                continue;
            }
            if (value[i] < '0' || value[i] > '9') {
                return false;
            }
        }

        const int month = std::stoi(value.substr(5, 2));
        const int day = std::stoi(value.substr(8, 2));

        return month >= 1 && month <= 12 && day >= 1 && day <= 31;
    }

    static std::int64_t calculateGross(const SaleEvent& event) {
        if (event.quantity <= 0) {
            throw std::invalid_argument("Quantity must be positive");
        }

        if (event.unitPriceCents < 0) {
            throw std::invalid_argument("Unit price cannot be negative");
        }

        if (event.unitPriceCents != 0 &&
            event.quantity >
                std::numeric_limits<std::int64_t>::max() /
                event.unitPriceCents) {
            throw std::overflow_error("Gross amount exceeds int64 range");
        }

        return event.quantity * event.unitPriceCents;
    }

    static void validateIdentity(const SaleEvent& event) {
        if (event.sourceSaleId.empty()) {
            throw std::invalid_argument("Missing source sale ID");
        }

        if (event.customerId.empty() || event.productId.empty()) {
            throw std::invalid_argument("Missing dimension identifier");
        }

        if (!isValidDate(event.saleDate)) {
            throw std::invalid_argument("Invalid sale date");
        }
    }

public:
    void addCustomer(const Customer& customer) {
        if (customer.id.empty() ||
            customer.name.empty() ||
            customer.region.empty()) {
            throw std::invalid_argument("Invalid customer dimension");
        }

        customers[customer.id] = customer;
    }

    void addProduct(const Product& product) {
        if (product.id.empty() ||
            product.name.empty() ||
            product.category.empty()) {
            throw std::invalid_argument("Invalid product dimension");
        }

        products[product.id] = product;
    }

    BatchMetrics ingest(const std::vector<SaleEvent>& batch) {
        BatchMetrics metrics;
        metrics.extracted = batch.size();

        /*
         * Copy-on-write provides batch-level atomicity. The existing fact
         * store changes only after all records have been examined and the
         * staged structure has passed its integrity check.
         */
        ColumnarFacts stagedFacts = facts;
        std::vector<RejectedRecord> stagedQuarantine = quarantine;
        std::uint64_t stagedSequence = lastSequence;

        for (const SaleEvent& event : batch) {
            if (event.sequence <= stagedSequence) {
                // An event older than the committed watermark is stale.
                ++metrics.unchanged;
                continue;
            }

            stagedSequence = event.sequence;

            if (event.status != SaleStatus::Completed) {
                ++metrics.skipped;
                continue;
            }

            try {
                validateIdentity(event);

                if (customers.find(event.customerId) == customers.end()) {
                    throw std::invalid_argument(
                        "Unknown customer dimension key"
                    );
                }

                if (products.find(event.productId) == products.end()) {
                    throw std::invalid_argument(
                        "Unknown product dimension key"
                    );
                }

                const std::int64_t grossCents = calculateGross(event);

                if (stagedFacts.loadedSaleIds.find(event.sourceSaleId) !=
                    stagedFacts.loadedSaleIds.end()) {
                    ++metrics.unchanged;
                    continue;
                }

                stagedFacts.append(event, grossCents);
                ++metrics.loaded;
            } catch (const std::exception& error) {
                stagedQuarantine.push_back({
                    event.sourceSaleId,
                    error.what()
                });
                ++metrics.rejected;
            }
        }

        stagedFacts.assertConsistent();

        // Commit all warehouse-side state together.
        facts = std::move(stagedFacts);
        quarantine = std::move(stagedQuarantine);
        lastSequence = stagedSequence;

        return metrics;
    }

    std::map<GroupKey, Aggregate> aggregateByRegionAndProduct() const {
        facts.assertConsistent();

        std::map<GroupKey, Aggregate> result;

        for (std::size_t i = 0; i < facts.size(); ++i) {
            const auto customerIt =
                customers.find(facts.customerIds[i]);

            const auto productIt =
                products.find(facts.productIds[i]);

            if (customerIt == customers.end() ||
                productIt == products.end()) {
                throw std::logic_error(
                    "Fact references a missing dimension record"
                );
            }

            GroupKey key{
                customerIt->second.region,
                productIt->second.name
            };

            Aggregate& aggregate = result[key];

            if (facts.quantities[i] >
                std::numeric_limits<std::int64_t>::max() -
                aggregate.units) {
                throw std::overflow_error("Unit aggregate overflow");
            }

            if (facts.grossAmounts[i] >
                std::numeric_limits<std::int64_t>::max() -
                aggregate.revenueCents) {
                throw std::overflow_error("Revenue aggregate overflow");
            }

            aggregate.units += facts.quantities[i];
            aggregate.revenueCents += facts.grossAmounts[i];
            ++aggregate.saleCount;
        }

        return result;
    }

    void printOperationalLookup(const std::string& saleId) const {
        /*
         * This is a warehouse fact lookup for demonstration. An actual OLTP
         * system would be optimized for frequent, selective transactions.
         */
        for (std::size_t i = 0; i < facts.size(); ++i) {
            if (facts.saleIds[i] == saleId) {
                std::cout
                    << "Sale " << saleId
                    << ": quantity=" << facts.quantities[i]
                    << ", gross cents=" << facts.grossAmounts[i]
                    << '\n';
                return;
            }
        }

        std::cout << "Sale " << saleId << " not found\n";
    }

    void printAnalyticalReport() const {
        const auto report = aggregateByRegionAndProduct();

        std::cout << "\nOLAP report: revenue by region and product\n";
        std::cout << std::left
                  << std::setw(12) << "Region"
                  << std::setw(18) << "Product"
                  << std::right
                  << std::setw(10) << "Sales"
                  << std::setw(10) << "Units"
                  << std::setw(15) << "Revenue"
                  << '\n';

        for (const auto& entry : report) {
            const GroupKey& key = entry.first;
            const Aggregate& aggregate = entry.second;

            std::cout << std::left
                      << std::setw(12) << key.region
                      << std::setw(18) << key.product
                      << std::right
                      << std::setw(10) << aggregate.saleCount
                      << std::setw(10) << aggregate.units
                      << std::setw(15)
                      << std::fixed << std::setprecision(2)
                      << static_cast<double>(aggregate.revenueCents) / 100.0
                      << '\n';
        }
    }

    void printQuarantine() const {
        std::cout << "\nQuarantined records\n";

        for (const RejectedRecord& record : quarantine) {
            std::cout << record.sourceSaleId
                      << ": " << record.reason << '\n';
        }
    }

    std::size_t factCount() const {
        return facts.size();
    }

    std::size_t quarantineCount() const {
        return quarantine.size();
    }
};

static void printMetrics(
    const std::string& label,
    const BatchMetrics& metrics
) {
    std::cout << "\n" << label << '\n'
              << "Extracted: " << metrics.extracted << '\n'
              << "Loaded: " << metrics.loaded << '\n'
              << "Unchanged: " << metrics.unchanged << '\n'
              << "Rejected: " << metrics.rejected << '\n'
              << "Skipped: " << metrics.skipped << '\n';
}

int main() {
    try {
        WarehouseEngine warehouse;

        warehouse.addCustomer({"C001", "Asha Mehta", "North"});
        warehouse.addCustomer({"C002", "Rohan Singh", "South"});
        warehouse.addCustomer({"C003", "Mira Das", "West"});

        warehouse.addProduct({
            "P100", "Laptop", "Electronics"
        });
        warehouse.addProduct({
            "P200", "Monitor", "Electronics"
        });
        warehouse.addProduct({
            "P300", "Office Chair", "Furniture"
        });

        const std::vector<SaleEvent> firstBatch = {
            {
                1, "S1001", "C001", "P100", "2026-10-01",
                2, 75000, SaleStatus::Completed
            },
            {
                2, "S1002", "C002", "P200", "2026-10-02",
                1, 22000, SaleStatus::Completed
            },
            {
                3, "S1003", "C003", "P300", "2026-10-03",
                3, 12000, SaleStatus::Completed
            },
            {
                4, "S1004", "C001", "P200", "2026-10-04",
                -1, 22000, SaleStatus::Completed
            },
            {
                5, "S1005", "C002", "P100", "2026-10-05",
                1, 75000, SaleStatus::Cancelled
            },
            {
                6, "S1006", "C404", "P100", "2026-10-06",
                1, 75000, SaleStatus::Completed
            }
        };

        const BatchMetrics firstMetrics = warehouse.ingest(firstBatch);
        printMetrics("Initial ETL batch", firstMetrics);

        if (firstMetrics.loaded != 3 ||
            firstMetrics.rejected != 2 ||
            firstMetrics.skipped != 1 ||
            warehouse.factCount() != 3) {
            throw std::runtime_error(
                "Initial batch validation failed"
            );
        }

        warehouse.printOperationalLookup("S1001");
        warehouse.printAnalyticalReport();
        warehouse.printQuarantine();

        /*
         * A correction with a new event sequence but the same business ID
         * represents a source change. This compact example uses insert-only
         * fact identity; a production CDC implementation would use a
         * source-version column and update the existing fact atomically.
         */
        const std::vector<SaleEvent> correctionBatch = {
            {
                7, "S1007", "C001", "P100", "2026-10-07",
                1, 30000, SaleStatus::Completed
            }
        };

        const BatchMetrics correctionMetrics =
            warehouse.ingest(correctionBatch);

        printMetrics("New incremental batch", correctionMetrics);

        if (warehouse.factCount() != 4) {
            throw std::runtime_error(
                "Incremental load produced an unexpected fact count"
            );
        }

        // Reprocessing the identical source event must not create a duplicate.
        const BatchMetrics duplicateMetrics =
            warehouse.ingest(correctionBatch);

        printMetrics("Duplicate event batch", duplicateMetrics);

        if (duplicateMetrics.unchanged != 1 ||
            warehouse.factCount() != 4) {
            throw std::runtime_error("Idempotency check failed");
        }

        warehouse.printAnalyticalReport();

        std::cout << "\nAll checks passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Warehouse failure: "
                  << error.what() << '\n';
        return 1;
    }
}
