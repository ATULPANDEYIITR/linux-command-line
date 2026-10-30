import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Function;
import java.util.stream.Collectors;

/*
 * Java 17 enterprise database high-availability model.
 *
 * Domain boundaries:
 * - Node: database instance and its operational state.
 * - HaPolicy: immutable quorum and replication requirements.
 * - HealthMonitor: concurrent health probing.
 * - HaCluster: aggregate that protects cluster invariants.
 * - FailoverDecision: immutable policy-evaluation result.
 *
 * All cluster mutations are serialized. Health probes execute concurrently,
 * but their results are applied as one controlled state transition.
 */
public class DatabaseHA {

    enum Role {
        PRIMARY,
        REPLICA
    }

    enum NodeState {
        HEALTHY,
        SUSPECT,
        DOWN,
        FENCED
    }

    static class HaException extends RuntimeException {
        HaException(String message) {
            super(message);
        }
    }

    static final class QuorumException extends HaException {
        QuorumException(String message) {
            super(message);
        }
    }

    static final class UnsafePromotionException extends HaException {
        UnsafePromotionException(String message) {
            super(message);
        }
    }

    record HaPolicy(
        int expectedVoters,
        int synchronousReplicaAcks,
        long maximumLagMs,
        int minimumLiveZones
    ) {
        HaPolicy {
            if (expectedVoters < 3 || expectedVoters % 2 == 0) {
                throw new IllegalArgumentException(
                    "Expected voter count must be an odd number of at least three."
                );
            }
            if (synchronousReplicaAcks < 1 ||
                synchronousReplicaAcks >= expectedVoters) {
                throw new IllegalArgumentException("Invalid synchronous acknowledgement count.");
            }
            if (maximumLagMs < 0) {
                throw new IllegalArgumentException("Maximum lag cannot be negative.");
            }
            if (minimumLiveZones < 1 || minimumLiveZones > expectedVoters) {
                throw new IllegalArgumentException("Invalid minimum live-zone requirement.");
            }
        }

        int quorum() {
            return expectedVoters / 2 + 1;
        }

        static HaPolicy productionDefault() {
            return new HaPolicy(3, 1, 500, 2);
        }
    }

    record NodeSnapshot(
        String id,
        String zone,
        Role role,
        NodeState state,
        boolean voter,
        boolean reachable,
        boolean fenced,
        long appliedIndex,
        long lagMs,
        int priority
    ) {
    }

    record ProbeResult(
        String nodeId,
        boolean completed,
        boolean healthy,
        String detail
    ) {
    }

    record FailoverDecision(
        boolean eligible,
        Optional<String> candidateId,
        int liveVoters,
        int liveZones,
        List<String> blockers,
        String reason
    ) {
        FailoverDecision {
            candidateId = Objects.requireNonNull(candidateId);
            blockers = List.copyOf(blockers);
        }
    }

    @FunctionalInterface
    interface HealthProbe {
        boolean isHealthy(NodeSnapshot node) throws Exception;
    }

    static final class Node {
        private final String id;
        private final String zone;
        private final int priority;
        private final boolean voter;

        private Role role;
        private NodeState state;
        private boolean reachable;
        private boolean fenced;
        private long appliedIndex;
        private long lagMs;

        Node(
            String id,
            String zone,
            Role role,
            int priority,
            boolean voter
        ) {
            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException("Node identifier is required.");
            }
            if (zone == null || zone.isBlank()) {
                throw new IllegalArgumentException("Availability zone is required.");
            }
            if (role == null || priority < 0) {
                throw new IllegalArgumentException("Invalid node role or priority.");
            }

            this.id = id;
            this.zone = zone;
            this.role = role;
            this.priority = priority;
            this.voter = voter;
            this.state = NodeState.HEALTHY;
            this.reachable = true;
        }

        boolean isLiveVoter() {
            return voter &&
                   reachable &&
                   state == NodeState.HEALTHY &&
                   !fenced;
        }

        NodeSnapshot snapshot() {
            return new NodeSnapshot(
                id,
                zone,
                role,
                state,
                voter,
                reachable,
                fenced,
                appliedIndex,
                lagMs,
                priority
            );
        }
    }

    static final class HealthMonitor implements AutoCloseable {
        private final ExecutorService executor;

        HealthMonitor(int parallelism) {
            if (parallelism < 1) {
                throw new IllegalArgumentException("Parallelism must be positive.");
            }
            this.executor = Executors.newFixedThreadPool(parallelism);
        }

        List<ProbeResult> probeAll(
            Collection<NodeSnapshot> nodes,
            HealthProbe probe
        ) {
            Objects.requireNonNull(nodes);
            Objects.requireNonNull(probe);

            List<CompletableFuture<ProbeResult>> futures = nodes.stream()
                .map(node -> CompletableFuture.supplyAsync(() -> {
                    try {
                        boolean healthy = probe.isHealthy(node);
                        return new ProbeResult(
                            node.id(),
                            true,
                            healthy,
                            healthy ? "probe succeeded" : "node did not respond"
                        );
                    } catch (Exception exception) {
                        return new ProbeResult(
                            node.id(),
                            false,
                            false,
                            exception.getClass().getSimpleName()
                        );
                    }
                }, executor))
                .toList();

            return futures.stream()
                .map(CompletableFuture::join)
                .toList();
        }

        @Override
        public void close() {
            executor.shutdown();
        }
    }

    static final class HaCluster {
        private final String clusterId;
        private final HaPolicy policy;
        private final Map<String, Node> nodes = new LinkedHashMap<>();
        private final List<String> audit = new ArrayList<>();
        private final ReentrantLock lock = new ReentrantLock();

        private String primaryId;
        private long commitIndex;
        private long term = 1;

        HaCluster(
            String clusterId,
            Collection<Node> initialNodes,
            HaPolicy policy
        ) {
            if (clusterId == null || clusterId.isBlank()) {
                throw new IllegalArgumentException("Cluster identifier is required.");
            }

            this.clusterId = clusterId;
            this.policy = Objects.requireNonNull(policy);

            if (initialNodes.size() != policy.expectedVoters()) {
                throw new IllegalArgumentException("Node count does not match expected voters.");
            }

            long primaryCount = 0;
            for (Node node : initialNodes) {
                if (!node.voter) {
                    throw new IllegalArgumentException("All configured nodes must be voters.");
                }
                if (nodes.putIfAbsent(node.id, node) != null) {
                    throw new IllegalArgumentException("Duplicate node: " + node.id);
                }
                if (node.role == Role.PRIMARY) {
                    primaryCount++;
                    primaryId = node.id;
                }
            }

            if (primaryCount != 1) {
                throw new IllegalArgumentException("Exactly one initial primary is required.");
            }

            record("cluster_initialized primary=" + primaryId);
        }

        private void record(String event) {
            audit.add(
                "time=" + Instant.now() +
                " term=" + term +
                " index=" + commitIndex +
                " event=" + event
            );
        }

        private Node primary() {
            Node node = nodes.get(primaryId);
            if (node == null) {
                throw new HaException("Configured primary does not exist.");
            }
            return node;
        }

        private List<Node> liveVoters() {
            return nodes.values().stream()
                .filter(Node::isLiveVoter)
                .toList();
        }

        List<NodeSnapshot> snapshots() {
            lock.lock();
            try {
                return nodes.values().stream()
                    .map(Node::snapshot)
                    .toList();
            } finally {
                lock.unlock();
            }
        }

        void applyProbeResults(List<ProbeResult> results) {
            lock.lock();
            try {
                for (ProbeResult result : results) {
                    Node node = nodes.get(result.nodeId());
                    if (node == null) {
                        throw new HaException("Health result references an unknown node.");
                    }

                    if (!result.completed() || !result.healthy()) {
                        if (!node.fenced) {
                            node.state = NodeState.DOWN;
                            node.reachable = false;
                        }
                    } else if (!node.fenced) {
                        node.state = NodeState.HEALTHY;
                        node.reachable = true;
                    }

                    record(
                        "health_probe node=" + node.id +
                        " detail=" + result.detail()
                    );
                }
            } finally {
                lock.unlock();
            }
        }

        long commitWrite(String payload) {
            if (payload == null || payload.isBlank()) {
                throw new IllegalArgumentException("Write payload cannot be empty.");
            }
            if (payload.getBytes(StandardCharsets.UTF_8).length > 4096) {
                throw new IllegalArgumentException("Write payload exceeds 4096 bytes.");
            }

            lock.lock();
            try {
                Node activePrimary = primary();
                if (activePrimary.role != Role.PRIMARY || !activePrimary.isLiveVoter()) {
                    throw new HaException("Current primary is not operational.");
                }

                List<Node> live = liveVoters();
                if (live.size() < policy.quorum()) {
                    throw new QuorumException("Write rejected because majority quorum is unavailable.");
                }

                int requiredAcks = Math.max(
                    policy.synchronousReplicaAcks(),
                    policy.quorum() - 1
                );

                List<Node> replicas = live.stream()
                    .filter(node -> node.role == Role.REPLICA)
                    .sorted(
                        Comparator.comparingInt((Node node) -> node.priority)
                            .thenComparing(node -> node.id)
                    )
                    .toList();

                if (replicas.size() < requiredAcks) {
                    throw new QuorumException(
                        "Insufficient healthy replicas for synchronous acknowledgement."
                    );
                }

                commitIndex++;
                activePrimary.appliedIndex = commitIndex;
                activePrimary.lagMs = 0;

                for (int i = 0; i < replicas.size(); i++) {
                    Node replica = replicas.get(i);
                    if (i < requiredAcks) {
                        replica.appliedIndex = commitIndex;
                        replica.lagMs = 0;
                    } else {
                        replica.lagMs += 100;
                    }
                }

                record("write_committed");
                return commitIndex;
            } finally {
                lock.unlock();
            }
        }

        void replicate(String nodeId) {
            lock.lock();
            try {
                Node replica = nodes.get(nodeId);
                if (replica == null ||
                    replica.role != Role.REPLICA ||
                    !replica.isLiveVoter()) {
                    throw new HaException("Replication target must be a healthy replica.");
                }

                replica.appliedIndex = commitIndex;
                replica.lagMs = 0;
                record("replica_caught_up node=" + nodeId);
            } finally {
                lock.unlock();
            }
        }

        FailoverDecision evaluateFailover() {
            lock.lock();
            try {
                return evaluateUnlocked();
            } finally {
                lock.unlock();
            }
        }

        private FailoverDecision evaluateUnlocked() {
            List<Node> live = liveVoters();
            Set<String> zones = live.stream()
                .map(node -> node.zone)
                .collect(Collectors.toSet());

            List<String> blockers = new ArrayList<>();

            if (primary().isLiveVoter()) {
                blockers.add("Current primary is healthy.");
                return new FailoverDecision(
                    false, Optional.empty(), live.size(), zones.size(),
                    blockers, "Primary failure has not been established."
                );
            }

            if (live.size() < policy.quorum()) {
                blockers.add("Majority quorum is unavailable.");
            }
            if (zones.size() < policy.minimumLiveZones()) {
                blockers.add("Insufficient live availability zones.");
            }

            Optional<Node> candidate = live.stream()
                .filter(node -> node.role == Role.REPLICA)
                .filter(node -> node.appliedIndex >= commitIndex)
                .filter(node -> node.lagMs <= policy.maximumLagMs())
                .sorted(
                    Comparator.comparingLong((Node node) -> node.appliedIndex)
                        .reversed()
                        .thenComparingInt(node -> node.priority)
                        .thenComparing(node -> node.id)
                )
                .findFirst();

            if (candidate.isEmpty()) {
                blockers.add("No fully caught-up replica satisfies the lag policy.");
            }

            boolean eligible = blockers.isEmpty() && candidate.isPresent();
            return new FailoverDecision(
                eligible,
                candidate.map(node -> node.id),
                live.size(),
                zones.size(),
                blockers,
                eligible
                    ? "Quorum and replication conditions are satisfied."
                    : String.join(" ", blockers)
            );
        }

        String failover() {
            lock.lock();
            try {
                FailoverDecision decision = evaluateUnlocked();
                if (!decision.eligible() || decision.candidateId().isEmpty()) {
                    throw new UnsafePromotionException(decision.reason());
                }

                Node oldPrimary = primary();
                Node candidate = nodes.get(decision.candidateId().orElseThrow());

                // The old writer becomes fenced before the candidate is promoted.
                oldPrimary.role = Role.REPLICA;
                oldPrimary.state = NodeState.FENCED;
                oldPrimary.fenced = true;
                oldPrimary.reachable = false;

                candidate.role = Role.PRIMARY;
                candidate.state = NodeState.HEALTHY;
                candidate.fenced = false;
                candidate.reachable = true;

                primaryId = candidate.id;
                term++;

                record(
                    "automatic_failover old=" + oldPrimary.id +
                    " new=" + candidate.id
                );

                return primaryId;
            } finally {
                lock.unlock();
            }
        }

        void markDown(String nodeId) {
            lock.lock();
            try {
                Node node = nodes.get(nodeId);
                if (node == null) {
                    throw new HaException("Unknown node: " + nodeId);
                }
                if (node.fenced) {
                    throw new HaException("Fenced node requires rebuild before recovery.");
                }

                node.state = NodeState.DOWN;
                node.reachable = false;
                record("node_down node=" + nodeId);
            } finally {
                lock.unlock();
            }
        }

        void rejoinAsReplica(String nodeId) {
            lock.lock();
            try {
                Node node = nodes.get(nodeId);
                if (node == null || nodeId.equals(primaryId)) {
                    throw new HaException("Recovery target must be a non-primary node.");
                }

                node.role = Role.REPLICA;
                node.state = NodeState.HEALTHY;
                node.fenced = false;
                node.reachable = true;
                node.appliedIndex = commitIndex;
                node.lagMs = 0;

                record("node_rejoined_as_replica node=" + nodeId);
            } finally {
                lock.unlock();
            }
        }

        void printStatus() {
            lock.lock();
            try {
                System.out.println(
                    "\nCluster=" + clusterId +
                    " primary=" + primaryId +
                    " term=" + term +
                    " commitIndex=" + commitIndex +
                    " quorum=" + policy.quorum()
                );

                for (Node node : nodes.values()) {
                    System.out.println(
                        "  " + node.id +
                        " zone=" + node.zone +
                        " role=" + node.role +
                        " state=" + node.state +
                        " appliedIndex=" + node.appliedIndex +
                        " lagMs=" + node.lagMs +
                        " fenced=" + node.fenced
                    );
                }
            } finally {
                lock.unlock();
            }
        }

        void printAudit() {
            lock.lock();
            try {
                System.out.println("\nAudit trail:");
                audit.forEach(System.out::println);
            } finally {
                lock.unlock();
            }
        }
    }

    private static List<Node> createNodes() {
        return List.of(
            new Node("db-a", "zone-a", Role.PRIMARY, 0, true),
            new Node("db-b", "zone-b", Role.REPLICA, 1, true),
            new Node("db-c", "zone-c", Role.REPLICA, 2, true)
        );
    }

    public static void main(String[] args) {
        try {
            HaCluster cluster = new HaCluster(
                "customer-records-production",
                createNodes(),
                HaPolicy.productionDefault()
            );

            cluster.commitWrite("customer-7001");
            cluster.commitWrite("customer-7002");

            System.out.println("Before primary failure:");
            cluster.printStatus();

            // Health checks run in parallel. Their results are applied together.
            try (HealthMonitor monitor = new HealthMonitor(3)) {
                List<ProbeResult> results = monitor.probeAll(
                    cluster.snapshots(),
                    node -> !node.id().equals("db-a")
                );
                cluster.applyProbeResults(results);
            }

            FailoverDecision decision = cluster.evaluateFailover();
            System.out.println("\nFailover decision: " + decision.reason());

            String promoted = cluster.failover();
            if (!"db-b".equals(promoted)) {
                throw new HaException("Unexpected failover candidate.");
            }

            cluster.rejoinAsReplica("db-a");

            System.out.println("\nAfter failover and recovery:");
            cluster.printStatus();
            cluster.printAudit();

            // An isolated cluster cannot promote with only one surviving voter.
            HaCluster isolated = new HaCluster(
                "isolated-cluster",
                createNodes(),
                HaPolicy.productionDefault()
            );
            isolated.markDown("db-a");
            isolated.markDown("db-c");

            FailoverDecision rejected = isolated.evaluateFailover();
            if (rejected.eligible()) {
                throw new HaException("Quorum-loss test unexpectedly became eligible.");
            }

            System.out.println("\nExpected quorum-loss rejection: " + rejected.reason());

        } catch (HaException | IllegalArgumentException exception) {
            System.err.println(
                "Database HA failure: " +
                exception.getClass().getSimpleName() +
                ": " + exception.getMessage()
            );
            System.exitCode = 1;
        }
    }
}
