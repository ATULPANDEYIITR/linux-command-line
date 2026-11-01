import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class DatabaseScalingCaseStudy {

    enum ScalingMode {
        VERTICAL,
        HORIZONTAL
    }

    enum PartitionStrategy {
        HASH,
        RANGE
    }

    enum ShardStrategy {
        HASH,
        RANGE
    }

    enum NodeState {
        HEALTHY,
        DRAINING,
        UNHEALTHY
    }

    record Order(long id, long customerId, double amount, String region) {
        Order {
            if (id <= 0) {
                throw new IllegalArgumentException("Order ID must be positive");
            }
            if (customerId <= 0) {
                throw new IllegalArgumentException("Customer ID must be positive");
            }
            if (amount < 0) {
                throw new IllegalArgumentException("Amount cannot be negative");
            }
            Objects.requireNonNull(region, "Region is required");
        }
    }

    static final class ScalingException extends RuntimeException {
        ScalingException(String message) {
            super(message);
        }
    }

    static final class DatabaseNode {
        private final String id;
        private int capacity;
        private int active;
        private NodeState state;

        DatabaseNode(String id, int capacity) {
            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException("Node ID is required");
            }
            if (capacity <= 0) {
                throw new IllegalArgumentException("Capacity must be positive");
            }

            this.id = id;
            this.capacity = capacity;
            this.state = NodeState.HEALTHY;
        }

        String id() {
            return id;
        }

        int capacity() {
            return capacity;
        }

        int active() {
            return active;
        }

        NodeState state() {
            return state;
        }

        double utilization() {
            return (double) active / capacity;
        }

        boolean available() {
            return state == NodeState.HEALTHY && active < capacity;
        }

        void resize(int newCapacity) {
            if (newCapacity < active || newCapacity <= 0) {
                throw new ScalingException(
                    "New capacity is below active workload or invalid"
                );
            }
            capacity = newCapacity;
        }

        void acquire() {
            if (!available()) {
                throw new ScalingException(
                    "Node " + id + " cannot accept workload"
                );
            }
            active++;
        }

        void drain() {
            if (state == NodeState.UNHEALTHY) {
                throw new ScalingException("Unhealthy node cannot be drained");
            }
            state = NodeState.DRAINING;
        }

        void markUnhealthy() {
            state = NodeState.UNHEALTHY;
        }
    }

    static final class Cluster {
        private final Map<String, DatabaseNode> nodes = new HashMap<>();

        void add(DatabaseNode node) {
            if (nodes.putIfAbsent(node.id(), node) != null) {
                throw new ScalingException(
                    "Duplicate node: " + node.id()
                );
            }
        }

        DatabaseNode node(String id) {
            DatabaseNode node = nodes.get(id);
            if (node == null) {
                throw new ScalingException("Unknown node: " + id);
            }
            return node;
        }

        DatabaseNode route() {
            return nodes.values()
                .stream()
                .filter(DatabaseNode::available)
                .min(Comparator.comparingDouble(DatabaseNode::utilization))
                .map(node -> {
                    node.acquire();
                    return node;
                })
                .orElseThrow(() ->
                    new ScalingException("No node has available capacity"));
        }

        List<DatabaseNode> nodes() {
            return Collections.unmodifiableList(
                new ArrayList<>(nodes.values())
            );
        }
    }

    static final class PartitionPolicy {
        private final PartitionStrategy strategy;
        private final int count;

        PartitionPolicy(PartitionStrategy strategy, int count) {
            if (count <= 0) {
                throw new IllegalArgumentException(
                    "Partition count must be positive"
                );
            }
            this.strategy = Objects.requireNonNull(strategy);
            this.count = count;
        }

        int locate(long customerId) {
            if (customerId <= 0) {
                throw new IllegalArgumentException(
                    "Customer ID must be positive"
                );
            }

            if (strategy == PartitionStrategy.HASH) {
                return Math.floorMod(
                    Long.hashCode(customerId),
                    count
                );
            }

            return (int) Math.min(customerId / 1000, count - 1);
        }
    }

    static final class ShardRepository {
        private final ShardStrategy strategy;
        private final List<Map<Long, Order>> shards;

        ShardRepository(int shardCount, ShardStrategy strategy) {
            if (shardCount <= 0) {
                throw new IllegalArgumentException(
                    "Shard count must be positive"
                );
            }

            this.strategy = Objects.requireNonNull(strategy);
            this.shards = new ArrayList<>();

            for (int i = 0; i < shardCount; i++) {
                shards.add(new HashMap<>());
            }
        }

        int locate(long customerId) {
            if (customerId <= 0) {
                throw new IllegalArgumentException(
                    "Customer ID must be positive"
                );
            }

            if (strategy == ShardStrategy.HASH) {
                return Math.floorMod(
                    Long.hashCode(customerId),
                    shards.size()
                );
            }

            return (int) Math.min(
                customerId / 1000,
                shards.size() - 1
            );
        }

        void save(Order order) {
            int shard = locate(order.customerId());

            if (shards.get(shard).putIfAbsent(
                order.id(),
                order
            ) != null) {
                throw new ScalingException(
                    "Duplicate order: " + order.id()
                );
            }
        }

        Optional<Order> find(long orderId, long customerId) {
            return Optional.ofNullable(
                shards.get(locate(customerId)).get(orderId)
            );
        }

        List<Integer> distribution() {
            return shards.stream()
                .map(Map::size)
                .collect(Collectors.toUnmodifiableList());
        }
    }

    interface ScalingPolicy {
        boolean accepts(Cluster cluster);
        String reason();
    }

    static final class UtilizationPolicy implements ScalingPolicy {
        private final double threshold;

        UtilizationPolicy(double threshold) {
            if (threshold <= 0 || threshold > 1) {
                throw new IllegalArgumentException(
                    "Threshold must be in (0, 1]"
                );
            }
            this.threshold = threshold;
        }

        @Override
        public boolean accepts(Cluster cluster) {
            return cluster.nodes().stream()
                .filter(node -> node.state() == NodeState.HEALTHY)
                .noneMatch(node -> node.utilization() >= threshold);
        }

        @Override
        public String reason() {
            return "Healthy nodes must remain below utilization threshold";
        }
    }

    static List<Order> generateOrders(int count) {
        List<Order> orders = new ArrayList<>();

        for (int i = 1; i <= count; i++) {
            long customerId = 100 + ((long) i * 7919) % 9000;
            double amount = 25.0 + ((i * 17.37) % 2500.0);
            String region = switch ((i - 1) % 4) {
                case 0 -> "north";
                case 1 -> "south";
                case 2 -> "east";
                default -> "west";
            };

            orders.add(new Order(
                i,
                customerId,
                amount,
                region
            ));
        }

        return List.copyOf(orders);
    }

    static void printCluster(Cluster cluster) {
        cluster.nodes()
            .stream()
            .sorted(Comparator.comparing(DatabaseNode::id))
            .forEach(node -> System.out.printf(
                "%s capacity=%d active=%d utilization=%.1f%% state=%s%n",
                node.id(),
                node.capacity(),
                node.active(),
                node.utilization() * 100,
                node.state()
            ));
    }

    public static void main(String[] args) {
        try {
            System.out.println("DATABASE SCALING CASE STUDY");

            /*
             * Enterprise policy: vertical scaling changes the resource
             * boundary of one server without changing data placement.
             */
            Cluster cluster = new Cluster();

            DatabaseNode primary = new DatabaseNode("primary", 100);
            cluster.add(primary);
            primary.resize(180);

            /*
             * Horizontal scaling adds independently routable capacity.
             */
            cluster.add(new DatabaseNode("node-02", 80));
            cluster.add(new DatabaseNode("node-03", 80));

            for (int i = 0; i < 120; i++) {
                cluster.route();
            }

            System.out.println("\n1. Cluster state");
            printCluster(cluster);

            /*
             * A policy object evaluates whether current capacity is becoming
             * unsafe. It does not itself perform a scaling operation.
             */
            ScalingPolicy policy = new UtilizationPolicy(0.80);
            System.out.println(
                "\n2. Scaling policy accepted: " +
                policy.accepts(cluster)
            );
            System.out.println("Policy: " + policy.reason());

            List<Order> orders = generateOrders(500);

            /*
             * Partitioning is a logical data organization layer.
             */
            PartitionPolicy partitionPolicy =
                new PartitionPolicy(PartitionStrategy.HASH, 16);

            Map<Integer, Long> partitionCounts = orders.stream()
                .collect(Collectors.groupingBy(
                    order -> partitionPolicy.locate(order.customerId()),
                    Collectors.counting()
                ));

            System.out.println("\n3. Partition counts");
            System.out.println(partitionCounts);

            /*
             * Sharding assigns rows to independently managed data stores.
             */
            ShardRepository repository =
                new ShardRepository(8, ShardStrategy.HASH);

            orders.forEach(repository::save);

            System.out.println("\n4. Shard distribution");
            System.out.println(repository.distribution());

            Order selected = orders.get(249);

            Optional<Order> found =
                repository.find(selected.id(), selected.customerId());

            if (found.isEmpty() ||
                found.get().id() != selected.id()) {
                throw new ScalingException(
                    "Point lookup failed"
                );
            }

            System.out.println(
                "Point lookup succeeded for order " + selected.id()
            );

            /*
             * Draining prevents new traffic while allowing an operational
             * process to move existing workload away from a node.
             */
            cluster.node("node-02").drain();

            for (int i = 0; i < 20; i++) {
                cluster.route();
            }

            /*
             * A hard failure is different from planned draining. The routing
             * service excludes both states from new workload.
             */
            cluster.node("node-03").markUnhealthy();

            for (int i = 0; i < 10; i++) {
                cluster.route();
            }

            System.out.println("\n5. Post-failure cluster state");
            printCluster(cluster);

            long storedRows = repository.distribution()
                .stream()
                .mapToLong(Integer::longValue)
                .sum();

            if (storedRows != orders.size()) {
                throw new ScalingException(
                    "Data distribution invariant failed"
                );
            }

            System.out.println(
                "\nScaling model completed successfully."
            );

        } catch (RuntimeException error) {
            System.err.println(
                "Execution failure: " + error.getMessage()
            );
            System.exit(1);
        }
    }
}
