#include <algorithm>
#include <cstdint>
#include <exception>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

enum class ServerRole {
    Primary,
    Replica
};

enum class TransactionState {
    Active,
    Committed,
    Aborted
};

enum class ReplicationMode {
    Asynchronous,
    Synchronous
};

struct Record {
    std::string value;
};

struct Page {
    std::size_t id{};
    std::size_t capacity{};
    std::unordered_map<std::string, Record> records;

    bool hasSpace(const std::string& key) const {
        return records.find(key) != records.end() ||
               records.size() < capacity;
    }

    void put(const std::string& key, const Record& record) {
        if (!hasSpace(key)) {
            throw std::runtime_error("Storage page is full");
        }
        records[key] = record;
    }

    void erase(const std::string& key) {
        records.erase(key);
    }
};

class StorageEngine {
private:
    std::size_t pageCapacity_;
    std::vector<Page> pages_;

    Page& locatePage(const std::string& key) {
        for (auto& page : pages_) {
            if (page.records.find(key) != page.records.end()) {
                return page;
            }
        }

        for (auto& page : pages_) {
            if (page.hasSpace(key)) {
                return page;
            }
        }

        pages_.push_back(Page{
            pages_.size(),
            pageCapacity_,
            {}
        });

        return pages_.back();
    }

public:
    explicit StorageEngine(std::size_t pageCapacity = 4)
        : pageCapacity_(pageCapacity) {
        if (pageCapacity == 0) {
            throw std::invalid_argument("Page capacity must be positive");
        }
    }

    void write(const std::string& key, const std::string& value) {
        if (key.empty()) {
            throw std::invalid_argument("Storage key cannot be empty");
        }

        locatePage(key).put(key, Record{value});
    }

    void erase(const std::string& key) {
        for (auto& page : pages_) {
            if (page.records.find(key) != page.records.end()) {
                page.erase(key);
                return;
            }
        }
    }

    std::optional<std::string> read(const std::string& key) const {
        for (const auto& page : pages_) {
            auto it = page.records.find(key);
            if (it != page.records.end()) {
                return it->second.value;
            }
        }
        return std::nullopt;
    }

    std::map<std::string, std::string> snapshot() const {
        std::map<std::string, std::string> result;

        for (const auto& page : pages_) {
            for (const auto& [key, record] : page.records) {
                result[key] = record.value;
            }
        }

        return result;
    }

    void restore(const std::map<std::string, std::string>& snapshot) {
        pages_.clear();

        for (const auto& [key, value] : snapshot) {
            write(key, value);
        }
    }

    std::size_t pageCount() const {
        return pages_.size();
    }
};

struct WalRecord {
    std::uint64_t lsn{};
    std::uint64_t transactionId{};
    bool deletion{};
    std::string key;
    std::optional<std::string> value;
};

class Transaction {
private:
    std::uint64_t id_;
    TransactionState state_{TransactionState::Active};
    std::map<std::string, std::optional<std::string>> writes_;

public:
    explicit Transaction(std::uint64_t id)
        : id_(id) {}

    std::uint64_t id() const {
        return id_;
    }

    TransactionState state() const {
        return state_;
    }

    void stageWrite(
        const std::string& key,
        std::optional<std::string> value
    ) {
        if (state_ != TransactionState::Active) {
            throw std::logic_error("Transaction is not active");
        }

        writes_[key] = std::move(value);
    }

    const auto& writes() const {
        return writes_;
    }

    void commit() {
        if (state_ != TransactionState::Active) {
            throw std::logic_error("Invalid transaction transition");
        }
        state_ = TransactionState::Committed;
    }

    void abort() {
        if (state_ != TransactionState::Active) {
            throw std::logic_error("Invalid transaction transition");
        }
        writes_.clear();
        state_ = TransactionState::Aborted;
    }
};

class DatabaseServer {
private:
    std::string name_;
    ServerRole role_;
    StorageEngine storage_;
    std::vector<WalRecord> wal_;
    std::set<std::uint64_t> committedTransactions_;
    std::uint64_t nextLsn_{1};
    std::uint64_t nextTransactionId_{1};
    std::uint64_t replayLsn_{0};
    std::uint64_t checkpointLsn_{0};
    bool available_{true};

    void requireAvailable() const {
        if (!available_) {
            throw std::runtime_error(name_ + " is unavailable");
        }
    }

public:
    DatabaseServer(
        std::string name,
        ServerRole role,
        std::size_t pageCapacity = 4
    )
        : name_(std::move(name)),
          role_(role),
          storage_(pageCapacity) {}

    const std::string& name() const {
        return name_;
    }

    ServerRole role() const {
        return role_;
    }

    void setRole(ServerRole role) {
        role_ = role;
    }

    std::uint64_t replayLsn() const {
        return replayLsn_;
    }

    std::uint64_t latestLsn() const {
        return nextLsn_ == 0 ? 0 : nextLsn_ - 1;
    }

    Transaction begin() {
        requireAvailable();
        return Transaction(nextTransactionId_++);
    }

    std::optional<std::string> read(const std::string& key) const {
        requireAvailable();
        return storage_.read(key);
    }

    std::vector<WalRecord> commit(Transaction& transaction) {
        requireAvailable();

        if (role_ != ServerRole::Primary) {
            throw std::logic_error("Only primary accepts application writes");
        }

        if (transaction.state() != TransactionState::Active) {
            throw std::logic_error("Transaction is not active");
        }

        std::vector<WalRecord> records;

        for (const auto& [key, value] : transaction.writes()) {
            records.push_back(WalRecord{
                nextLsn_++,
                transaction.id(),
                !value.has_value(),
                key,
                value
            });
        }

        // WAL records are appended before data pages are modified.
        wal_.insert(wal_.end(), records.begin(), records.end());

        const auto backup = storage_.snapshot();

        try {
            for (const auto& record : records) {
                if (record.deletion) {
                    storage_.erase(record.key);
                } else {
                    storage_.write(record.key, *record.value);
                }
            }

            transaction.commit();
            committedTransactions_.insert(transaction.id());
        } catch (...) {
            storage_.restore(backup);
            transaction.abort();
            throw;
        }

        return records;
    }

    void rollback(Transaction& transaction) {
        transaction.abort();
    }

    void checkpoint() {
        requireAvailable();
        checkpointLsn_ = latestLsn();
    }

    std::uint64_t checkpointLsn() const {
        return checkpointLsn_;
    }

    void crash() {
        available_ = false;
    }

    void recover() {
        /*
         * This educational recovery procedure rebuilds storage by replaying
         * committed WAL records. A production engine normally uses checkpoints
         * plus optimized redo/undo processing.
         */
        storage_ = StorageEngine();

        for (const auto& record : wal_) {
            if (!committedTransactions_.contains(record.transactionId)) {
                continue;
            }

            if (record.deletion) {
                storage_.erase(record.key);
            } else {
                storage_.write(record.key, *record.value);
            }
        }

        available_ = true;
    }

    void applyReplicaRecord(const WalRecord& record) {
        requireAvailable();

        if (record.lsn <= replayLsn_) {
            return;
        }

        if (record.deletion) {
            storage_.erase(record.key);
        } else {
            storage_.write(record.key, *record.value);
        }

        replayLsn_ = record.lsn;
    }

    std::size_t pageCount() const {
        return storage_.pageCount();
    }
};

class ReplicationCluster {
private:
    DatabaseServer& primary_;
    std::vector<DatabaseServer*> replicas_;
    std::unordered_map<std::string, std::queue<WalRecord>> queues_;
    ReplicationMode mode_{ReplicationMode::Asynchronous};

public:
    explicit ReplicationCluster(DatabaseServer& primary)
        : primary_(primary) {
        if (primary.role() != ServerRole::Primary) {
            throw std::invalid_argument("Cluster requires a primary");
        }
    }

    void setMode(ReplicationMode mode) {
        mode_ = mode;
    }

    void addReplica(DatabaseServer& replica) {
        if (replica.role() != ServerRole::Replica) {
            throw std::invalid_argument("Replica role required");
        }

        replicas_.push_back(&replica);
        queues_.emplace(replica.name(), std::queue<WalRecord>{});
    }

    void commit(
        Transaction& transaction,
        std::size_t requiredSynchronousAcks = 0
    ) {
        const auto records = primary_.commit(transaction);

        for (auto* replica : replicas_) {
            auto& queue = queues_.at(replica->name());

            for (const auto& record : records) {
                queue.push(record);
            }
        }

        if (mode_ == ReplicationMode::Synchronous) {
            replicateAll();

            const auto targetLsn =
                records.empty() ? 0 : records.back().lsn;

            std::size_t acknowledgements = 0;

            for (auto* replica : replicas_) {
                if (replica->replayLsn() >= targetLsn) {
                    ++acknowledgements;
                }
            }

            if (acknowledgements < requiredSynchronousAcks) {
                throw std::runtime_error(
                    "Synchronous replication requirement failed"
                );
            }
        }
    }

    void replicateAll() {
        for (auto* replica : replicas_) {
            auto& queue = queues_.at(replica->name());

            try {
                while (!queue.empty()) {
                    replica->applyReplicaRecord(queue.front());
                    queue.pop();
                }
            } catch (const std::exception&) {
                // A failed replica retains unprocessed queue state.
            }
        }
    }

    std::uint64_t lag(const DatabaseServer& replica) const {
        if (primary_.latestLsn() < replica.replayLsn()) {
            return 0;
        }

        return primary_.latestLsn() - replica.replayLsn();
    }

    DatabaseServer& failover(DatabaseServer& replica) {
        const auto found = std::find(
            replicas_.begin(),
            replicas_.end(),
            &replica
        );

        if (found == replicas_.end()) {
            throw std::runtime_error("Replica is not part of cluster");
        }

        if (replica.role() != ServerRole::Replica) {
            throw std::runtime_error("Target is not a replica");
        }

        primary_.setRole(ServerRole::Replica);
        replica.setRole(ServerRole::Primary);

        return replica;
    }
};

static void printOptional(
    const std::string& label,
    const std::optional<std::string>& value
) {
    std::cout << label;

    if (value) {
        std::cout << *value;
    } else {
        std::cout << "<missing>";
    }

    std::cout << '\n';
}

int main() {
    try {
        std::cout << "DATABASE INFRASTRUCTURE FUNDAMENTALS\n";
        std::cout << "====================================\n";

        DatabaseServer primary(
            "orders-primary",
            ServerRole::Primary,
            2
        );

        DatabaseServer replicaA(
            "orders-replica-a",
            ServerRole::Replica,
            2
        );

        DatabaseServer replicaB(
            "orders-replica-b",
            ServerRole::Replica,
            2
        );

        ReplicationCluster cluster(primary);
        cluster.addReplica(replicaA);
        cluster.addReplica(replicaB);

        std::cout << "\nTRANSACTION AND WAL\n";

        auto transaction = primary.begin();

        transaction.stageWrite(
            "account:100",
            "{\"owner\":\"Riya\",\"balance\":1000}"
        );

        transaction.stageWrite(
            "account:200",
            "{\"owner\":\"Arjun\",\"balance\":500}"
        );

        cluster.commit(transaction);

        printOptional(
            "Primary account 100: ",
            primary.read("account:100")
        );

        std::cout << "\nASYNC REPLICATION\n";

        std::cout
            << "Replica A lag before replay: "
            << cluster.lag(replicaA)
            << '\n';

        cluster.replicateAll();

        printOptional(
            "Replica A account 100: ",
            replicaA.read("account:100")
        );

        std::cout
            << "Replica A lag after replay: "
            << cluster.lag(replicaA)
            << '\n';

        std::cout << "\nSYNCHRONOUS REPLICATION\n";

        cluster.setMode(ReplicationMode::Synchronous);

        auto synchronousTransaction = primary.begin();

        synchronousTransaction.stageWrite(
            "inventory:SKU-10",
            "{\"quantity\":75,\"warehouse\":\"LKO\"}"
        );

        cluster.commit(synchronousTransaction, 2);

        std::cout
            << "Synchronous acknowledgement requirement satisfied.\n";

        std::cout << "\nCHECKPOINT AND RECOVERY\n";

        primary.checkpoint();

        std::cout
            << "Checkpoint LSN: "
            << primary.checkpointLsn()
            << '\n';

        primary.crash();

        try {
            primary.read("account:100");
        } catch (const std::exception& error) {
            std::cout
                << "Expected availability failure: "
                << error.what()
                << '\n';
        }

        primary.recover();

        printOptional(
            "Recovered account 100: ",
            primary.read("account:100")
        );

        std::cout << "\nFAILOVER\n";

        cluster.replicateAll();

        DatabaseServer& promoted = cluster.failover(replicaB);

        std::cout
            << "Promoted server: "
            << promoted.name()
            << '\n';

        std::cout << "Promoted role: PRIMARY\n";

        std::cout << "\nSTORAGE\n";

        std::cout
            << "Primary page count after recovery: "
            << primary.pageCount()
            << '\n';

        std::cout
            << "Promoted replica page count: "
            << promoted.pageCount()
            << '\n';

        std::cout << "\nENGINEERING TRADE-OFFS\n";
        std::cout
            << "- Page scans are O(P) without an index.\n"
            << "- WAL improves crash recovery but adds write overhead.\n"
            << "- Synchronous replication reduces acknowledged-data loss risk "
               "but increases commit latency.\n"
            << "- Asynchronous replication improves write latency but permits "
               "replication lag.\n"
            << "- Failover should select a sufficiently current replica to "
               "avoid excessive data loss.\n";

        std::cout << "\nSECURITY CONTROLS\n";
        std::cout
            << "- Authenticate replication peers.\n"
            << "- Encrypt client and replication connections.\n"
            << "- Restrict administrative failover permissions.\n"
            << "- Protect database files and WAL from unauthorized access.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}
