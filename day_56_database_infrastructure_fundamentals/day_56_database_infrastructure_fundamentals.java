import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

public class DatabaseInfrastructureFundamentals {

    enum ServerRole {
        PRIMARY,
        REPLICA
    }

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ABORTED
    }

    enum ReplicationMode {
        ASYNCHRONOUS,
        SYNCHRONOUS
    }

    record WalRecord(
            long lsn,
            long transactionId,
            String operation,
            String key,
            String value,
            Instant createdAt) {
    }

    record HealthStatus(
            String server,
            ServerRole role,
            boolean available,
            long replayLsn,
            long latestLsn) {
    }

    static class DatabaseException extends RuntimeException {
        DatabaseException(String message) {
            super(message);
        }
    }

    static class TransactionException extends DatabaseException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class ReplicationException extends DatabaseException {
        ReplicationException(String message) {
            super(message);
        }
    }

    static final class StorageEngine {
        private final int pageCapacity;
        private final List<Map<String, String>> pages = new ArrayList<>();

        StorageEngine(int pageCapacity) {
            if (pageCapacity < 1) {
                throw new IllegalArgumentException(
                        "Page capacity must be positive");
            }
            this.pageCapacity = pageCapacity;
        }

        void write(String key, String value) {
            if (key == null || key.isBlank()) {
                throw new IllegalArgumentException(
                        "Storage key is required");
            }

            for (Map<String, String> page : pages) {
                if (page.containsKey(key) || page.size() < pageCapacity) {
                    page.put(key, value);
                    return;
                }
            }

            Map<String, String> page = new HashMap<>();
            page.put(key, value);
            pages.add(page);
        }

        void delete(String key) {
            for (Map<String, String> page : pages) {
                page.remove(key);
            }
        }

        Optional<String> read(String key) {
            for (Map<String, String> page : pages) {
                if (page.containsKey(key)) {
                    return Optional.ofNullable(page.get(key));
                }
            }
            return Optional.empty();
        }

        Map<String, String> snapshot() {
            Map<String, String> result = new HashMap<>();

            for (Map<String, String> page : pages) {
                result.putAll(page);
            }

            return result;
        }

        void restore(Map<String, String> snapshot) {
            pages.clear();

            for (Map.Entry<String, String> entry : snapshot.entrySet()) {
                write(entry.getKey(), entry.getValue());
            }
        }

        int pageCount() {
            return pages.size();
        }
    }

    static final class Transaction {
        private final long id;
        private TransactionState state = TransactionState.ACTIVE;
        private final Map<String, String> writes = new HashMap<>();
        private final Set<String> deletes = new HashSet<>();

        Transaction(long id) {
            this.id = id;
        }

        long id() {
            return id;
        }

        TransactionState state() {
            return state;
        }

        Map<String, String> writes() {
            return Collections.unmodifiableMap(writes);
        }

        Set<String> deletes() {
            return Collections.unmodifiableSet(deletes);
        }

        void upsert(String key, String value) {
            requireActive();
            if (value == null) {
                throw new IllegalArgumentException(
                        "Use delete for null values");
            }
            writes.put(key, value);
            deletes.remove(key);
        }

        void delete(String key) {
            requireActive();
            writes.remove(key);
            deletes.add(key);
        }

        void commit() {
            requireActive();
            state = TransactionState.COMMITTED;
        }

        void abort() {
            requireActive();
            writes.clear();
            deletes.clear();
            state = TransactionState.ABORTED;
        }

        private void requireActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionException(
                        "Transaction is not active");
            }
        }
    }

    static final class DatabaseServer {
        private final String name;
        private ServerRole role;
        private StorageEngine storage;
        private final List<WalRecord> wal = new ArrayList<>();
        private final Set<Long> committedTransactions = new HashSet<>();

        private long nextLsn = 1;
        private long nextTransactionId = 1;
        private long replayLsn = 0;
        private long checkpointLsn = 0;
        private boolean available = true;

        DatabaseServer(String name, ServerRole role, int pageCapacity) {
            this.name = Objects.requireNonNull(name);
            this.role = Objects.requireNonNull(role);
            this.storage = new StorageEngine(pageCapacity);
        }

        String name() {
            return name;
        }

        ServerRole role() {
            return role;
        }

        void role(ServerRole role) {
            this.role = Objects.requireNonNull(role);
        }

        long latestLsn() {
            return nextLsn - 1;
        }

        long replayLsn() {
            return replayLsn;
        }

        boolean available() {
            return available;
        }

        Transaction begin() {
            requireAvailable();
            return new Transaction(nextTransactionId++);
        }

        Optional<String> read(String key) {
            requireAvailable();
            return storage.read(key);
        }

        List<WalRecord> commit(Transaction transaction) {
            requireAvailable();

            if (role != ServerRole.PRIMARY) {
                throw new TransactionException(
                        "Only the primary accepts writes");
            }

            if (transaction.state() != TransactionState.ACTIVE) {
                throw new TransactionException(
                        "Transaction is not active");
            }

            List<WalRecord> records = new ArrayList<>();

            for (Map.Entry<String, String> entry :
                    transaction.writes().entrySet()) {

                records.add(new WalRecord(
                        nextLsn++,
                        transaction.id(),
                        "UPSERT",
                        entry.getKey(),
                        entry.getValue(),
                        Instant.now()));
            }

            for (String key : transaction.deletes()) {
                records.add(new WalRecord(
                        nextLsn++,
                        transaction.id(),
                        "DELETE",
                        key,
                        null,
                        Instant.now()));
            }

            wal.addAll(records);

            Map<String, String> backup = storage.snapshot();

            try {
                for (WalRecord record : records) {
                    if (record.operation().equals("DELETE")) {
                        storage.delete(record.key());
                    } else {
                        storage.write(record.key(), record.value());
                    }
                }

                transaction.commit();
                committedTransactions.add(transaction.id());

            } catch (RuntimeException error) {
                storage.restore(backup);
                transaction.abort();
                throw error;
            }

            return List.copyOf(records);
        }

        void rollback(Transaction transaction) {
            transaction.abort();
        }

        void checkpoint() {
            requireAvailable();
            checkpointLsn = latestLsn();
        }

        long checkpointLsn() {
            return checkpointLsn;
        }

        void crash() {
            available = false;
        }

        void recover() {
            /*
             * Rebuild storage from committed WAL records. A production
             * implementation would combine checkpoints with optimized
             * redo/undo recovery.
             */
            storage = new StorageEngine(4);

            for (WalRecord record : wal) {
                if (!committedTransactions.contains(record.transactionId())) {
                    continue;
                }

                if (record.operation().equals("DELETE")) {
                    storage.delete(record.key());
                } else {
                    storage.write(record.key(), record.value());
                }
            }

            available = true;
        }

        void apply(WalRecord record) {
            requireAvailable();

            if (record.lsn() <= replayLsn) {
                return;
            }

            if (record.operation().equals("DELETE")) {
                storage.delete(record.key());
            } else {
                storage.write(record.key(), record.value());
            }

            replayLsn = record.lsn();
        }

        int pageCount() {
            return storage.pageCount();
        }

        HealthStatus health() {
            return new HealthStatus(
                    name,
                    role,
                    available,
                    replayLsn,
                    latestLsn());
        }

        private void requireAvailable() {
            if (!available) {
                throw new DatabaseException(
                        "Server " + name + " is unavailable");
            }
        }
    }

    interface MergePolicy<T> {
        boolean accepts(T candidate);
    }

    static final class ReplicationCluster {
        private DatabaseServer primary;
        private final List<DatabaseServer> replicas = new ArrayList<>();
        private final Map<String, List<WalRecord>> queues = new HashMap<>();
        private ReplicationMode mode = ReplicationMode.ASYNCHRONOUS;

        ReplicationCluster(DatabaseServer primary) {
            if (primary.role() != ServerRole.PRIMARY) {
                throw new IllegalArgumentException(
                        "Cluster requires a primary");
            }
            this.primary = primary;
        }

        void setMode(ReplicationMode mode) {
            this.mode = Objects.requireNonNull(mode);
        }

        void addReplica(DatabaseServer replica) {
            if (replica.role() != ServerRole.REPLICA) {
                throw new IllegalArgumentException(
                        "Server must have REPLICA role");
            }

            replicas.add(replica);
            queues.put(replica.name(), new ArrayList<>());
        }

        void commit(
                Transaction transaction,
                int requiredAcks) {

            List<WalRecord> records = primary.commit(transaction);

            for (DatabaseServer replica : replicas) {
                queues.get(replica.name()).addAll(records);
            }

            if (mode == ReplicationMode.SYNCHRONOUS) {
                replicateAll();

                long targetLsn = records.isEmpty()
                        ? 0
                        : records.get(records.size() - 1).lsn();

                long acknowledgements = replicas.stream()
                        .filter(replica -> replica.replayLsn() >= targetLsn)
                        .count();

                if (acknowledgements < requiredAcks) {
                    throw new ReplicationException(
                            "Synchronous acknowledgement requirement failed");
                }
            }
        }

        void replicateAll() {
            for (DatabaseServer replica : replicas) {
                if (!replica.available()) {
                    continue;
                }

                List<WalRecord> queue = queues.get(replica.name());

                for (WalRecord record : queue) {
                    replica.apply(record);
                }

                queue.clear();
            }
        }

        long lag(DatabaseServer replica) {
            return Math.max(
                    0,
                    primary.latestLsn() - replica.replayLsn());
        }

        DatabaseServer failover(DatabaseServer replica) {
            if (!replicas.contains(replica)) {
                throw new ReplicationException(
                        "Replica does not belong to cluster");
            }

            if (!replica.available()) {
                throw new ReplicationException(
                        "Unavailable replica cannot become primary");
            }

            primary.role(ServerRole.REPLICA);
            replica.role(ServerRole.PRIMARY);
            primary = replica;

            return replica;
        }

        DatabaseServer primary() {
            return primary;
        }
    }

    static void validateEmployee(String name, double salary) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException(
                    "Employee name is required");
        }

        if (!Double.isFinite(salary) || salary < 0) {
            throw new IllegalArgumentException(
                    "Salary must be a finite non-negative value");
        }
    }

    public static void main(String[] args) {
        System.out.println("DATABASE INFRASTRUCTURE FUNDAMENTALS");
        System.out.println("====================================");

        DatabaseServer primary =
                new DatabaseServer(
                        "orders-primary",
                        ServerRole.PRIMARY,
                        2);

        DatabaseServer replicaA =
                new DatabaseServer(
                        "orders-replica-a",
                        ServerRole.REPLICA,
                        2);

        DatabaseServer replicaB =
                new DatabaseServer(
                        "orders-replica-b",
                        ServerRole.REPLICA,
                        2);

        ReplicationCluster cluster =
                new ReplicationCluster(primary);

        cluster.addReplica(replicaA);
        cluster.addReplica(replicaB);

        System.out.println("\nTRANSACTION");

        Transaction transaction = primary.begin();

        transaction.upsert(
                "customer:C100",
                "{\"name\":\"Riya\",\"creditLimit\":100000}");

        transaction.upsert(
                "order:O900",
                "{\"customer\":\"C100\",\"amount\":2499,\"state\":\"PAID\"}");

        cluster.commit(transaction, 0);

        System.out.println(
                "Primary order: "
                        + primary.read("order:O900").orElse("<missing>"));

        System.out.println("\nASYNCHRONOUS REPLICATION");

        System.out.println(
                "Replica A lag before replay: "
                        + cluster.lag(replicaA));

        cluster.replicateAll();

        System.out.println(
                "Replica A order: "
                        + replicaA.read("order:O900").orElse("<missing>"));

        System.out.println(
                "Replica A lag after replay: "
                        + cluster.lag(replicaA));

        System.out.println("\nSYNCHRONOUS REPLICATION");

        cluster.setMode(ReplicationMode.SYNCHRONOUS);

        Transaction synchronous = primary.begin();

        synchronous.upsert(
                "inventory:SKU-10",
                "{\"quantity\":75,\"warehouse\":\"LKO\"}");

        cluster.commit(synchronous, 2);

        System.out.println(
                "Two synchronous replica acknowledgements received.");

        System.out.println("\nCHECKPOINT AND RECOVERY");

        primary.checkpoint();

        System.out.println(
                "Checkpoint LSN: " + primary.checkpointLsn());

        primary.crash();

        try {
            primary.read("order:O900");
        } catch (DatabaseException error) {
            System.out.println(
                    "Expected availability failure: "
                            + error.getMessage());
        }

        primary.recover();

        System.out.println(
                "Recovered order: "
                        + primary.read("order:O900").orElse("<missing>"));

        System.out.println("\nVALIDATION");

        try {
            validateEmployee("", -5);
        } catch (IllegalArgumentException error) {
            System.out.println(
                    "Rejected invalid employee: "
                            + error.getMessage());
        }

        System.out.println("\nFAILOVER");

        cluster.replicateAll();

        DatabaseServer promoted = cluster.failover(replicaB);

        System.out.println(
                "Promoted server: " + promoted.name());

        System.out.println(
                "Promoted role: " + promoted.role());

        System.out.println("\nHEALTH");

        System.out.println(primary.health());
        System.out.println(replicaA.health());
        System.out.println(promoted.health());

        System.out.println("\nENGINEERING CONSIDERATIONS");
        System.out.println(
                "- Page scans are linear without indexes.");
        System.out.println(
                "- WAL supports crash recovery but requires durable logging.");
        System.out.println(
                "- Synchronous replication increases commit latency.");
        System.out.println(
                "- Asynchronous replication permits measurable lag.");
        System.out.println(
                "- Failover should prefer the most current healthy replica.");

        System.out.println("\nSECURITY CONTROLS");
        System.out.println(
                "- Authenticate replication peers.");
        System.out.println(
                "- Encrypt client and replication traffic.");
        System.out.println(
                "- Restrict failover operations using least privilege.");
        System.out.println(
                "- Protect database and WAL files from unauthorized access.");
    }
}
