import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

public class DatabaseReplicationEnterprise {

    enum ReplicationMode {
        SYNCHRONOUS,
        ASYNCHRONOUS
    }

    enum NodeRole {
        PRIMARY,
        REPLICA,
        OFFLINE
    }

    enum NodeState {
        HEALTHY,
        DEGRADED,
        FAILED
    }

    record WalEntry(
        long position,
        String key,
        String value,
        Instant committedAt
    ) {}

    record ReplicationStatus(
        String node,
        ReplicationMode mode,
        NodeRole role,
        NodeState state,
        long appliedPosition,
        long lag
    ) {}

    static class ReplicationException extends Exception {
        ReplicationException(String message) {
            super(message);
        }
    }

    static final class ReplicaNode {
        private final String name;
        private final ReplicationMode mode;
        private final Map<String, String> data = new ConcurrentHashMap<>();
        private final Deque<WalEntry> queue = new ArrayDeque<>();

        private volatile NodeRole role = NodeRole.REPLICA;
        private volatile NodeState state = NodeState.HEALTHY;
        private volatile long appliedPosition;

        ReplicaNode(String name, ReplicationMode mode) {
            this.name = Objects.requireNonNull(name);
            this.mode = Objects.requireNonNull(mode);
        }

        void receive(WalEntry entry) {
            if (state != NodeState.FAILED &&
                entry.position() > appliedPosition) {
                queue.addLast(entry);
            }
        }

        int apply(int limit) {
            if (state == NodeState.FAILED) {
                return 0;
            }

            int count = 0;

            while (!queue.isEmpty() && count < limit) {
                WalEntry entry = queue.peekFirst();

                if (entry.position() <= appliedPosition) {
                    queue.removeFirst();
                    continue;
                }

                if (entry.position() != appliedPosition + 1) {
                    state = NodeState.DEGRADED;
                    break;
                }

                data.put(entry.key(), entry.value());
                appliedPosition = entry.position();
                queue.removeFirst();
                state = NodeState.HEALTHY;
                count++;
            }

            return count;
        }

        void fail() {
            state = NodeState.FAILED;
            role = NodeRole.OFFLINE;
        }

        boolean available() {
            return state != NodeState.FAILED;
        }

        long appliedPosition() {
            return appliedPosition;
        }

        Map<String, String> snapshot() {
            return Map.copyOf(data);
        }
    }

    interface ApprovalPolicy {
        boolean accepts(ReplicaNode node, long requiredPosition);
    }

    static final class SynchronousDurabilityPolicy
        implements ApprovalPolicy {

        @Override
        public boolean accepts(
            ReplicaNode node,
            long requiredPosition
        ) {
            return node.available()
                && node.mode == ReplicationMode.SYNCHRONOUS
                && node.appliedPosition() >= requiredPosition;
        }
    }

    static final class ReplicationService {
        private final Map<String, ReplicaNode> replicas =
            new ConcurrentHashMap<>();

        private final Map<String, String> primaryData =
            new ConcurrentHashMap<>();

        private final List<WalEntry> wal = new ArrayList<>();
        private final ApprovalPolicy durabilityPolicy =
            new SynchronousDurabilityPolicy();

        private String primaryName = "primary-01";
        private boolean primaryOnline = true;
        private long nextPosition = 1;

        ReplicationService() {
            replicas.put(
                "sync-01",
                new ReplicaNode(
                    "sync-01",
                    ReplicationMode.SYNCHRONOUS
                )
            );

            replicas.put(
                "async-01",
                new ReplicaNode(
                    "async-01",
                    ReplicationMode.ASYNCHRONOUS
                )
            );
        }

        synchronized WalEntry write(String key, String value)
            throws ReplicationException {

            if (!primaryOnline) {
                throw new ReplicationException(
                    "No writable primary is available."
                );
            }

            validate(key, value);

            WalEntry entry = new WalEntry(
                nextPosition++,
                key,
                value,
                Instant.now()
            );

            wal.add(entry);
            primaryData.put(key, value);

            replicas.values().forEach(replica -> replica.receive(entry));

            // Synchronous replicas participate directly in commit
            // acknowledgement. Async replicas are deliberately excluded.
            replicas.values().stream()
                .filter(
                    replica ->
                        replica.mode == ReplicationMode.SYNCHRONOUS
                )
                .forEach(replica -> replica.apply(1));

            if (!walEntryDurable(entry)) {
                throw new ReplicationException(
                    "Synchronous durability requirement was not met."
                );
            }

            return entry;
        }

        private boolean walEntryDurable(WalEntry entry) {
            return replicas.values().stream()
                .filter(
                    replica ->
                        replica.mode == ReplicationMode.SYNCHRONOUS
                )
                .allMatch(
                    replica ->
                        durabilityPolicy.accepts(
                            replica,
                            entry.position()
                        )
                );
        }

        void processAsync(int batchSize) {
            replicas.values().stream()
                .filter(
                    replica ->
                        replica.mode == ReplicationMode.ASYNCHRONOUS
                )
                .forEach(replica -> replica.apply(batchSize));
        }

        String read(
            String key,
            String replicaName,
            long minimumPosition
        ) throws ReplicationException {

            ReplicaNode replica = replicas.get(replicaName);

            if (replica == null || !replica.available()) {
                throw new ReplicationException(
                    "Requested replica is unavailable."
                );
            }

            if (replica.appliedPosition() < minimumPosition) {
                throw new ReplicationException(
                    "Replica has not reached required WAL position."
                );
            }

            return replica.snapshot().get(key);
        }

        void failPrimary() {
            primaryOnline = false;
        }

        synchronized void promote(String replicaName)
            throws ReplicationException {

            ReplicaNode candidate = replicas.get(replicaName);

            if (candidate == null || !candidate.available()) {
                throw new ReplicationException(
                    "Only an available replica can be promoted."
                );
            }

            replicas.values().forEach(
                replica -> replica.role = NodeRole.REPLICA
            );

            candidate.role = NodeRole.PRIMARY;
            primaryName = replicaName;
            primaryData.clear();
            primaryData.putAll(candidate.snapshot());
            primaryOnline = true;
        }

        List<ReplicationStatus> status() {
            long primaryPosition =
                wal.isEmpty() ? 0 : wal.get(wal.size() - 1).position();

            return replicas.values().stream()
                .map(
                    replica ->
                        new ReplicationStatus(
                            replica.name,
                            replica.mode,
                            replica.role,
                            replica.state,
                            replica.appliedPosition(),
                            primaryPosition -
                                replica.appliedPosition()
                        )
                )
                .toList();
        }

        private static void validate(String key, String value)
            throws ReplicationException {

            if (key == null || key.isBlank() || key.length() > 256) {
                throw new ReplicationException(
                    "Invalid replication key."
                );
            }

            if (value == null || value.length() > 4096) {
                throw new ReplicationException(
                    "Invalid replication value."
                );
            }
        }

        String primaryName() {
            return primaryName;
        }
    }

    public static void main(String[] args) {
        try {
            ReplicationService service = new ReplicationService();

            WalEntry first =
                service.write("customer:101", "active");

            System.out.println(
                "Committed WAL position: " + first.position()
            );

            service.write("invoice:7001", "paid");

            System.out.println("\nInitial status:");
            service.status().forEach(System.out::println);

            try {
                service.read(
                    "invoice:7001",
                    "async-01",
                    2
                );
            } catch (ReplicationException ex) {
                System.out.println(
                    "Expected stale-read rejection: "
                    + ex.getMessage()
                );
            }

            service.processAsync(100);

            System.out.println(
                "Replica value after catch-up: "
                + service.read(
                    "invoice:7001",
                    "async-01",
                    2
                )
            );

            service.failPrimary();
            service.promote("sync-01");

            service.write("customer:101", "verified");

            System.out.println(
                "\nPromoted primary: " + service.primaryName()
            );

            System.out.println("Final status:");
            service.status().forEach(System.out::println);

        } catch (ReplicationException ex) {
            System.err.println(
                "Replication operation failed: " + ex.getMessage()
            );
            System.exit(1);
        }
    }
}
