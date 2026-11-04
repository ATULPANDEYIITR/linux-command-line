import java.time.Instant;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class DatabaseInfrastructure {

    enum Role {
        PRIMARY,
        REPLICA
    }

    enum NodeState {
        HEALTHY,
        DEGRADED,
        FAILED,
        RECOVERING
    }

    enum BackupType {
        FULL,
        INCREMENTAL
    }

    enum AlertSeverity {
        INFO,
        WARNING,
        CRITICAL
    }

    record InfrastructurePolicy(
        int maximumReplicationLag,
        int minimumHealthyReplicas,
        int maximumConnections,
        double maximumCpu,
        double maximumMemory,
        Duration cacheTtl,
        Duration backupRetention,
        Duration recoveryPointObjective,
        Duration recoveryTimeObjective
    ) {
        InfrastructurePolicy {
            if (maximumReplicationLag < 0 ||
                minimumHealthyReplicas < 0 ||
                maximumConnections <= 0 ||
                maximumCpu <= 0 ||
                maximumCpu > 100 ||
                maximumMemory <= 0 ||
                maximumMemory > 100) {
                throw new IllegalArgumentException(
                    "Invalid infrastructure policy"
                );
            }

            Objects.requireNonNull(cacheTtl);
            Objects.requireNonNull(backupRetention);
            Objects.requireNonNull(recoveryPointObjective);
            Objects.requireNonNull(recoveryTimeObjective);

            if (cacheTtl.isNegative() || cacheTtl.isZero() ||
                backupRetention.isNegative() ||
                backupRetention.isZero() ||
                recoveryPointObjective.isNegative() ||
                recoveryTimeObjective.isNegative()) {
                throw new IllegalArgumentException(
                    "Policy durations must be positive"
                );
            }
        }

        static InfrastructurePolicy production() {
            return new InfrastructurePolicy(
                5,
                1,
                100,
                85,
                90,
                Duration.ofSeconds(60),
                Duration.ofDays(30),
                Duration.ofMinutes(5),
                Duration.ofMinutes(2)
            );
        }
    }

    static final class InfrastructureException extends Exception {
        InfrastructureException(String message) {
            super(message);
        }
    }

    static final class DatabaseNode {
        private final String id;
        private final String region;
        private final String availabilityZone;

        private Role role;
        private NodeState state = NodeState.HEALTHY;

        private long transactionPosition;
        private int replicationLag;
        private int activeConnections;
        private final int connectionLimit;

        private double cpu;
        private double memory;
        private Instant lastHeartbeat;

        DatabaseNode(
            String id,
            String region,
            String availabilityZone,
            Role role,
            int connectionLimit
        ) {
            if (id == null || id.isBlank() ||
                region == null || region.isBlank() ||
                availabilityZone == null ||
                availabilityZone.isBlank() ||
                connectionLimit <= 0) {
                throw new IllegalArgumentException(
                    "Invalid database node configuration"
                );
            }

            this.id = id;
            this.region = region;
            this.availabilityZone = availabilityZone;
            this.role = Objects.requireNonNull(role);
            this.connectionLimit = connectionLimit;
            this.cpu = 20;
            this.memory = 40;
            this.lastHeartbeat = Instant.now();
        }

        synchronized boolean isAvailable() {
            return state == NodeState.HEALTHY &&
                activeConnections < connectionLimit;
        }

        synchronized void acquire()
            throws InfrastructureException {

            if (!isAvailable()) {
                throw new InfrastructureException(
                    "Node unavailable: " + id
                );
            }

            activeConnections++;
        }

        synchronized void release() {
            activeConnections = Math.max(
                0,
                activeConnections - 1
            );
        }

        synchronized void heartbeat() {
            if (state != NodeState.FAILED) {
                lastHeartbeat = Instant.now();
            }
        }

        synchronized void fail() {
            state = NodeState.FAILED;
        }

        synchronized void promote() {
            if (state != NodeState.HEALTHY) {
                throw new IllegalStateException(
                    "Only healthy nodes can be promoted"
                );
            }

            role = Role.PRIMARY;
            replicationLag = 0;
        }

        synchronized void rejoin(long primaryPosition) {
            if (role == Role.PRIMARY && state == NodeState.HEALTHY) {
                throw new IllegalStateException(
                    "Active primary cannot rejoin as replica"
                );
            }

            state = NodeState.RECOVERING;
            role = Role.REPLICA;
            transactionPosition = primaryPosition;
            replicationLag = 0;
            state = NodeState.HEALTHY;
            heartbeat();
        }

        synchronized void setMetrics(
            double cpu,
            double memory
        ) {
            if (cpu < 0 || cpu > 100 ||
                memory < 0 || memory > 100) {
                throw new IllegalArgumentException(
                    "Metrics must be between 0 and 100"
                );
            }

            this.cpu = cpu;
            this.memory = memory;
        }

        synchronized void commit(long count) {
            if (count <= 0) {
                throw new IllegalArgumentException(
                    "Commit count must be positive"
                );
            }

            transactionPosition += count;
        }

        synchronized void addLag(int amount) {
            replicationLag += amount;
        }

        synchronized void applyReplication(
            long primaryPosition,
            int amount
        ) {
            if (amount < 0) {
                throw new IllegalArgumentException(
                    "Replication amount cannot be negative"
                );
            }

            if (role != Role.REPLICA ||
                state != NodeState.HEALTHY) {
                throw new IllegalStateException(
                    "Node is not an available replica"
                );
            }

            replicationLag = Math.max(
                0,
                replicationLag - amount
            );

            transactionPosition = Math.max(
                0,
                primaryPosition - replicationLag
            );
        }

        synchronized long position() {
            return transactionPosition;
        }

        synchronized int lag() {
            return replicationLag;
        }

        synchronized Role role() {
            return role;
        }

        synchronized NodeState state() {
            return state;
        }

        synchronized String id() {
            return id;
        }

        synchronized double cpu() {
            return cpu;
        }

        synchronized double memory() {
            return memory;
        }

        synchronized int connections() {
            return activeConnections;
        }

        synchronized Instant lastHeartbeat() {
            return lastHeartbeat;
        }

        String region() {
            return region;
        }

        String availabilityZone() {
            return availabilityZone;
        }

        synchronized String describe() {
            return String.format(
                "%-16s %-8s %-12s position=%d lag=%d connections=%d",
                id,
                role,
                state,
                transactionPosition,
                replicationLag,
                activeConnections
            );
        }
    }

    record Backup(
        String id,
        BackupType type,
        Instant createdAt,
        long transactionPosition,
        String checksum,
        boolean verified,
        String parentBackupId
    ) {}

    interface BackupRepository {
        void save(Backup backup);

        Optional<Backup> findById(String id);

        List<Backup> findAll();
    }

    static final class InMemoryBackupRepository
        implements BackupRepository {

        private final Map<String, Backup> storage =
            new ConcurrentHashMap<>();

        @Override
        public void save(Backup backup) {
            storage.put(backup.id(), backup);
        }

        @Override
        public Optional<Backup> findById(String id) {
            return Optional.ofNullable(storage.get(id));
        }

        @Override
        public List<Backup> findAll() {
            return new ArrayList<>(storage.values());
        }
    }

    static final class BackupService {
        private final BackupRepository repository;
        private final AtomicInteger sequence =
            new AtomicInteger();

        BackupService(BackupRepository repository) {
            this.repository = Objects.requireNonNull(repository);
        }

        synchronized Backup create(
            DatabaseNode primary,
            BackupType type
        ) throws InfrastructureException {

            if (primary.role() != Role.PRIMARY ||
                !primary.isAvailable()) {
                throw new InfrastructureException(
                    "Backup requires an available primary"
                );
            }

            String parentId = null;

            if (type == BackupType.INCREMENTAL) {
                Backup parent = repository.findAll()
                    .stream()
                    .filter(b -> b.type() == BackupType.FULL)
                    .filter(Backup::verified)
                    .max(Comparator.comparing(Backup::createdAt))
                    .orElseThrow(() ->
                        new IllegalStateException(
                            "No verified full backup exists"
                        )
                    );

                parentId = parent.id();
            }

            Instant now = Instant.now();

            String id = "backup-" + sequence.incrementAndGet();

            String source = primary.id() + ":" +
                primary.position() + ":" +
                now + ":" + type;

            // The demonstration uses a SHA-256 digest.
            String checksum = sha256(source);

            Backup backup = new Backup(
                id,
                type,
                now,
                primary.position(),
                checksum,
                true,
                parentId
            );

            repository.save(backup);
            return backup;
        }

        boolean verify(String backupId) {
            Optional<Backup> result =
                repository.findById(backupId);

            if (result.isEmpty()) return false;

            Backup backup = result.get();

            if (!backup.verified()) return false;

            if (backup.type() == BackupType.INCREMENTAL) {
                return backup.parentBackupId() != null &&
                    repository.findById(backup.parentBackupId())
                        .filter(Backup::verified)
                        .filter(b -> b.type() == BackupType.FULL)
                        .isPresent();
            }

            return true;
        }

        void restore(
            String backupId,
            DatabaseNode target
        ) throws InfrastructureException {

            if (!verify(backupId)) {
                throw new InfrastructureException(
                    "Backup dependency chain is invalid"
                );
            }

            Backup backup = repository.findById(backupId)
                .orElseThrow();

            target.rejoin(backup.transactionPosition());
        }

        List<Backup> inventory() {
            return repository.findAll()
                .stream()
                .sorted(
                    Comparator.comparing(Backup::createdAt)
                )
                .toList();
        }

        private static String sha256(String value)
            throws InfrastructureException {

            try {
                java.security.MessageDigest digest =
                    java.security.MessageDigest.getInstance("SHA-256");

                byte[] bytes = digest.digest(
                    value.getBytes(java.nio.charset.StandardCharsets.UTF_8)
                );

                StringBuilder output = new StringBuilder();

                for (byte b : bytes) {
                    output.append(String.format("%02x", b));
                }

                return output.toString();
            } catch (java.security.NoSuchAlgorithmException error) {
                throw new InfrastructureException(
                    "SHA-256 is unavailable"
                );
            }
        }
    }

    static final class CacheEntry<T> {
        final T value;
        final Instant expiresAt;

        CacheEntry(T value, Instant expiresAt) {
            this.value = value;
            this.expiresAt = expiresAt;
        }
    }

    static final class CacheService<T> {
        private final Map<String, CacheEntry<T>> entries =
            new ConcurrentHashMap<>();

        private final Duration ttl;

        private final AtomicInteger hits = new AtomicInteger();
        private final AtomicInteger misses = new AtomicInteger();

        CacheService(Duration ttl) {
            if (ttl.isNegative() || ttl.isZero()) {
                throw new IllegalArgumentException(
                    "Cache TTL must be positive"
                );
            }
            this.ttl = ttl;
        }

        Optional<T> get(String key) {
            CacheEntry<T> entry = entries.get(key);

            if (entry == null ||
                !Instant.now().isBefore(entry.expiresAt)) {
                entries.remove(key);
                misses.incrementAndGet();
                return Optional.empty();
            }

            hits.incrementAndGet();
            return Optional.of(entry.value);
        }

        void put(String key, T value) {
            entries.put(
                key,
                new CacheEntry<>(
                    Objects.requireNonNull(value),
                    Instant.now().plus(ttl)
                )
            );
        }

        void invalidate(String key) {
            entries.remove(key);
        }

        void clear() {
            entries.clear();
        }

        double hitRatio() {
            int total = hits.get() + misses.get();

            return total == 0
                ? 0
                : (double) hits.get() / total;
        }

        int size() {
            return entries.size();
        }
    }

    record MonitoringMetric(
        Instant timestamp,
        String nodeId,
        String metricName,
        double value,
        AlertSeverity severity
    ) {}

    static final class MonitoringService {
        private final InfrastructurePolicy policy;
        private final List<MonitoringMetric> history =
            new ArrayList<>();

        MonitoringService(InfrastructurePolicy policy) {
            this.policy = policy;
        }

        synchronized List<MonitoringMetric> collect(
            List<DatabaseNode> nodes
        ) {
            List<MonitoringMetric> current = new ArrayList<>();

            for (DatabaseNode node : nodes) {
                add(current, node, "CPU", node.cpu(),
                    policy.maximumCpu());

                add(current, node, "MEMORY", node.memory(),
                    policy.maximumMemory());

                add(current, node, "REPLICATION_LAG", node.lag(),
                    policy.maximumReplicationLag());

                if (node.state() == NodeState.FAILED) {
                    current.add(new MonitoringMetric(
                        Instant.now(),
                        node.id(),
                        "NODE_STATE",
                        1,
                        AlertSeverity.CRITICAL
                    ));
                }
            }

            history.addAll(current);
            return List.copyOf(current);
        }

        private void add(
            List<MonitoringMetric> result,
            DatabaseNode node,
            String name,
            double value,
            double threshold
        ) {
            AlertSeverity severity = value >= threshold
                ? AlertSeverity.WARNING
                : AlertSeverity.INFO;

            result.add(new MonitoringMetric(
                Instant.now(),
                node.id(),
                name,
                value,
                severity
            ));
        }

        synchronized List<MonitoringMetric> history() {
            return List.copyOf(history);
        }
    }

    static final class DatabaseCluster {
        private final Map<String, DatabaseNode> nodes =
            new HashMap<>();

        private final InfrastructurePolicy policy;
        private final List<String> failoverHistory =
            new ArrayList<>();

        private boolean failoverInProgress;

        DatabaseCluster(
            List<DatabaseNode> initialNodes,
            InfrastructurePolicy policy
        ) {
            this.policy = policy;

            if (initialNodes == null || initialNodes.isEmpty()) {
                throw new IllegalArgumentException(
                    "Cluster cannot be empty"
                );
            }

            long primaryCount = initialNodes.stream()
                .filter(n -> n.role() == Role.PRIMARY)
                .count();

            if (primaryCount != 1) {
                throw new IllegalArgumentException(
                    "Exactly one primary is required"
                );
            }

            for (DatabaseNode node : initialNodes) {
                if (nodes.putIfAbsent(node.id(), node) != null) {
                    throw new IllegalArgumentException(
                        "Duplicate node ID: " + node.id()
                    );
                }
            }
        }

        synchronized DatabaseNode primary() {
            return nodes.values()
                .stream()
                .filter(n -> n.role() == Role.PRIMARY)
                .findFirst()
                .orElseThrow(() ->
                    new IllegalStateException("Primary not found")
                );
        }

        synchronized List<DatabaseNode> replicas() {
            return nodes.values()
                .stream()
                .filter(n -> n.role() == Role.REPLICA)
                .toList();
        }

        synchronized List<DatabaseNode> healthyReplicas() {
            return replicas().stream()
                .filter(DatabaseNode::isAvailable)
                .filter(n ->
                    n.lag() <= policy.maximumReplicationLag()
                )
                .toList();
        }

        synchronized long write(long transactionCount)
            throws InfrastructureException {

            if (transactionCount <= 0) {
                throw new IllegalArgumentException(
                    "Transaction count must be positive"
                );
            }

            DatabaseNode leader = primary();
            leader.acquire();

            try {
                leader.commit(transactionCount);

                int lagIncrement = Math.toIntExact(transactionCount);

                for (DatabaseNode replica : replicas()) {
                    if (replica.state() == NodeState.HEALTHY) {
                        replica.addLag(lagIncrement);
                    }
                }

                return leader.position();
            } finally {
                leader.release();
            }
        }

        synchronized void replicate(
            String replicaId,
            int transactionCount
        ) {
            DatabaseNode replica = nodes.get(replicaId);

            if (replica == null) {
                throw new IllegalArgumentException(
                    "Unknown replica"
                );
            }

            replica.applyReplication(
                primary().position(),
                transactionCount
            );
        }

        synchronized DatabaseNode selectReadNode() {
            return healthyReplicas()
                .stream()
                .min(
                    Comparator.comparingInt(DatabaseNode::lag)
                        .thenComparingInt(DatabaseNode::connections)
                        .thenComparingDouble(DatabaseNode::cpu)
                )
                .orElseGet(() -> {
                    if (primary().isAvailable()) {
                        return primary();
                    }

                    throw new IllegalStateException(
                        "No readable database node"
                    );
                });
        }

        synchronized Map<String, Object> read(
            String key,
            CacheService<Map<String, Object>> cache
        ) throws InfrastructureException {

            if (key == null || key.isBlank()) {
                throw new IllegalArgumentException(
                    "Read key cannot be empty"
                );
            }

            Optional<Map<String, Object>> cached = cache.get(key);

            if (cached.isPresent()) {
                return cached.get();
            }

            DatabaseNode node = selectReadNode();
            node.acquire();

            try {
                Map<String, Object> result = Map.of(
                    "key", key,
                    "servedBy", node.id(),
                    "transactionPosition", node.position(),
                    "replicationLag", node.lag()
                );

                cache.put(key, result);
                return result;
            } finally {
                node.release();
            }
        }

        synchronized String failover()
            throws InfrastructureException {

            if (failoverInProgress) {
                throw new InfrastructureException(
                    "Failover already running"
                );
            }

            failoverInProgress = true;

            try {
                DatabaseNode oldPrimary = primary();
                oldPrimary.fail();

                List<DatabaseNode> candidates = healthyReplicas();

                if (candidates.isEmpty()) {
                    throw new InfrastructureException(
                        "No eligible replica for promotion"
                    );
                }

                DatabaseNode promoted = candidates.stream()
                    .max(
                        Comparator.comparingLong(
                            DatabaseNode::position
                        )
                    )
                    .orElseThrow();

                promoted.promote();

                String event = oldPrimary.id() +
                    " -> " + promoted.id() +
                    " at position " + promoted.position();

                failoverHistory.add(event);
                return event;
            } finally {
                failoverInProgress = false;
            }
        }

        synchronized void rejoin(String nodeId) {
            DatabaseNode node = nodes.get(nodeId);

            if (node == null) {
                throw new IllegalArgumentException(
                    "Unknown recovery node"
                );
            }

            if (node.id().equals(primary().id())) {
                throw new IllegalStateException(
                    "Active primary cannot rejoin"
                );
            }

            node.rejoin(primary().position());
        }

        synchronized List<DatabaseNode> allNodes() {
            return List.copyOf(nodes.values());
        }

        synchronized List<String> failoverHistory() {
            return List.copyOf(failoverHistory);
        }

        synchronized boolean hasRequiredReplicas() {
            return healthyReplicas().size() >=
                policy.minimumHealthyReplicas();
        }
    }

    static final class InfrastructureService {
        private final InfrastructurePolicy policy;
        private final DatabaseCluster cluster;
        private final BackupService backupService;
        private final CacheService<Map<String, Object>> cache;
        private final MonitoringService monitoring;

        InfrastructureService() {
            policy = InfrastructurePolicy.production();

            List<DatabaseNode> nodes = List.of(
                new DatabaseNode(
                    "db-primary",
                    "ap-south-1",
                    "zone-a",
                    Role.PRIMARY,
                    policy.maximumConnections()
                ),
                new DatabaseNode(
                    "db-replica-1",
                    "ap-south-1",
                    "zone-b",
                    Role.REPLICA,
                    policy.maximumConnections()
                ),
                new DatabaseNode(
                    "db-replica-2",
                    "ap-south-2",
                    "zone-c",
                    Role.REPLICA,
                    policy.maximumConnections()
                )
            );

            cluster = new DatabaseCluster(nodes, policy);

            backupService = new BackupService(
                new InMemoryBackupRepository()
            );

            cache = new CacheService<>(policy.cacheTtl());
            monitoring = new MonitoringService(policy);
        }

        void run() throws InfrastructureException {
            System.out.println("1. Transaction processing");

            cluster.write(20);
            cluster.write(10);

            System.out.println("2. Replica synchronization");

            cluster.replicate("db-replica-1", 25);
            cluster.replicate("db-replica-2", 20);

            System.out.println("3. Read routing and caching");

            System.out.println(
                cluster.read("customer:1001", cache)
            );

            System.out.println(
                cluster.read("customer:1001", cache)
            );

            System.out.println(
                "Cache hit ratio: " + cache.hitRatio()
            );

            System.out.println("4. Backup workflow");

            Backup full = backupService.create(
                cluster.primary(),
                BackupType.FULL
            );

            Backup incremental = backupService.create(
                cluster.primary(),
                BackupType.INCREMENTAL
            );

            System.out.println(full);
            System.out.println(incremental);

            System.out.println("5. Monitoring");

            cluster.primary().setMetrics(91, 45);

            List<MonitoringMetric> metrics =
                monitoring.collect(cluster.allNodes());

            metrics.stream()
                .filter(m ->
                    m.severity() != AlertSeverity.INFO
                )
                .forEach(System.out::println);

            System.out.println("6. Automatic failover");

            cluster.primary().fail();

            String failover = cluster.failover();
            cache.clear();

            System.out.println(failover);

            System.out.println("7. Recover previous primary");

            cluster.rejoin("db-primary");

            System.out.println("8. Backup restoration test");

            DatabaseNode restoreNode = new DatabaseNode(
                "restore-node",
                "ap-south-1",
                "zone-d",
                Role.REPLICA,
                50
            );

            backupService.restore(full.id(), restoreNode);

            System.out.println(
                "Restored position: " + restoreNode.position()
            );

            System.out.println("9. Final infrastructure state");

            cluster.allNodes().stream()
                .map(DatabaseNode::describe)
                .forEach(System.out::println);

            System.out.println(
                "Replica policy satisfied: " +
                cluster.hasRequiredReplicas()
            );

            System.out.println(
                "Failovers: " + cluster.failoverHistory()
            );

            System.out.println(
                "Verified backups: " +
                backupService.inventory().stream()
                    .filter(Backup::verified)
                    .count()
            );
        }
    }

    static void runTests() throws InfrastructureException {
        InfrastructurePolicy policy =
            InfrastructurePolicy.production();

        DatabaseCluster cluster = new DatabaseCluster(
            List.of(
                new DatabaseNode(
                    "primary",
                    "region-a",
                    "zone-a",
                    Role.PRIMARY,
                    10
                ),
                new DatabaseNode(
                    "replica",
                    "region-a",
                    "zone-b",
                    Role.REPLICA,
                    10
                )
            ),
            policy
        );

        CacheService<Map<String, Object>> cache =
            new CacheService<>(Duration.ofSeconds(30));

        assert cluster.write(10) == 10;

        cluster.replicate("replica", 10);

        Map<String, Object> first =
            cluster.read("test-key", cache);

        Map<String, Object> second =
            cluster.read("test-key", cache);

        assert first.equals(second);
        assert cache.hitRatio() == 0.5;

        BackupService backupService = new BackupService(
            new InMemoryBackupRepository()
        );

        Backup full = backupService.create(
            cluster.primary(),
            BackupType.FULL
        );

        assert backupService.verify(full.id());

        cluster.primary().fail();

        String event = cluster.failover();
        assert event.contains("replica");

        cluster.rejoin("primary");

        assert cluster.primary().id().equals("replica");

        System.out.println("All Java 17 infrastructure tests passed.");
    }

    public static void main(String[] args) {
        try {
            if (args.length > 0 && args[0].equals("--test")) {
                runTests();
                return;
            }

            new InfrastructureService().run();
        } catch (Exception error) {
            System.err.println(
                "Infrastructure failure: " + error.getMessage()
            );
            System.exit(1);
        }
    }
}
