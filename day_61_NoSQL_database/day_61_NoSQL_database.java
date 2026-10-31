import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class NoSQLArchitectureEnterprise {

    enum DatabaseType {
        KEY_VALUE,
        DOCUMENT,
        WIDE_COLUMN,
        GRAPH
    }

    enum ReviewState {
        CREATED,
        ACTIVE,
        FAILED,
        COMPLETED
    }

    record Product(
        String id,
        String name,
        String category,
        double price,
        List<String> tags
    ) {
        Product {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Product id is required");
            }
            if (name == null || name.isBlank()) {
                throw new ValidationException("Product name is required");
            }
            if (price < 0) {
                throw new ValidationException("Product price cannot be negative");
            }
            tags = List.copyOf(tags);
        }
    }

    record TelemetryPoint(
        String timestamp,
        double value
    ) {}

    static class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class NotFoundException extends RuntimeException {
        NotFoundException(String message) {
            super(message);
        }
    }

    interface NoSQLRepository<T> {
        void save(T value);
        Optional<T> find(String id);
        List<T> query(Predicate<T> predicate);
    }

    static final class DocumentRepository
        implements NoSQLRepository<Product> {

        private final Map<String, Product> products = new HashMap<>();

        @Override
        public void save(Product product) {
            Objects.requireNonNull(product, "product");
            if (products.containsKey(product.id())) {
                throw new ValidationException(
                    "Duplicate document: " + product.id()
                );
            }
            products.put(product.id(), product);
        }

        @Override
        public Optional<Product> find(String id) {
            return Optional.ofNullable(products.get(id));
        }

        @Override
        public List<Product> query(Predicate<Product> predicate) {
            return products.values()
                .stream()
                .filter(predicate)
                .toList();
        }

        public void replace(Product product) {
            if (!products.containsKey(product.id())) {
                throw new NotFoundException(
                    "Product does not exist: " + product.id()
                );
            }
            products.put(product.id(), product);
        }
    }

    static final class KeyValueRepository {
        private record Entry(
            String value,
            Instant expiresAt
        ) {}

        private final Map<String, Entry> values = new HashMap<>();

        public void put(
            String key,
            String value,
            Optional<Instant> expiresAt
        ) {
            if (key == null || key.isBlank() || key.length() > 256) {
                throw new ValidationException(
                    "Key must contain 1-256 characters"
                );
            }

            if (expiresAt.isPresent() &&
                expiresAt.get().isBefore(Instant.now())) {
                throw new ValidationException("Expiration is already in the past");
            }

            values.put(
                key,
                new Entry(value, expiresAt.orElse(null))
            );
        }

        public String get(String key) {
            Entry entry = values.get(key);

            if (entry == null) {
                throw new NotFoundException("Missing key: " + key);
            }

            if (entry.expiresAt() != null &&
                !entry.expiresAt().isAfter(Instant.now())) {
                values.remove(key);
                throw new NotFoundException("Expired key: " + key);
            }

            return entry.value();
        }
    }

    static final class WideColumnRepository {
        private final Map<String, Map<String, Map<String, Double>>> rows =
            new HashMap<>();

        public void write(
            String rowKey,
            String family,
            String column,
            double value
        ) {
            if (rowKey == null || rowKey.isBlank() ||
                family == null || family.isBlank() ||
                column == null || column.isBlank()) {
                throw new ValidationException(
                    "Row key, family, and column are required"
                );
            }

            rows.computeIfAbsent(rowKey, ignored -> new HashMap<>())
                .computeIfAbsent(family, ignored -> new HashMap<>())
                .put(column, value);
        }

        public Map<String, Map<String, Double>> readFamily(
            String family
        ) {
            Map<String, Map<String, Double>> result = new HashMap<>();

            rows.forEach((rowKey, families) -> {
                if (families.containsKey(family)) {
                    result.put(
                        rowKey,
                        Map.copyOf(families.get(family))
                    );
                }
            });

            return Collections.unmodifiableMap(result);
        }
    }

    record GraphEdge(String relation, String target) {}

    static final class DependencyGraph {
        private final Set<String> nodes = new HashSet<>();
        private final Map<String, List<GraphEdge>> edges = new HashMap<>();

        public void addNode(String node) {
            if (!nodes.add(node)) {
                throw new ValidationException(
                    "Duplicate graph node: " + node
                );
            }
            edges.put(node, new ArrayList<>());
        }

        public void addEdge(
            String source,
            String relation,
            String target
        ) {
            if (!nodes.contains(source) || !nodes.contains(target)) {
                throw new NotFoundException(
                    "Both graph endpoints must exist"
                );
            }

            edges.get(source).add(
                new GraphEdge(relation, target)
            );
        }

        public Optional<List<String>> shortestPath(
            String start,
            String target
        ) {
            if (!nodes.contains(start) || !nodes.contains(target)) {
                throw new NotFoundException(
                    "Graph endpoint does not exist"
                );
            }

            record State(String node, List<String> path) {}

            ArrayDeque<State> queue = new ArrayDeque<>();
            Set<String> visited = new HashSet<>();

            queue.add(new State(start, List.of(start)));
            visited.add(start);

            while (!queue.isEmpty()) {
                State state = queue.removeFirst();

                if (state.node().equals(target)) {
                    return Optional.of(state.path());
                }

                for (GraphEdge edge :
                    edges.getOrDefault(state.node(), List.of())) {

                    if (visited.add(edge.target())) {
                        List<String> nextPath =
                            new ArrayList<>(state.path());
                        nextPath.add(edge.target());
                        queue.addLast(
                            new State(edge.target(), List.copyOf(nextPath))
                        );
                    }
                }
            }

            return Optional.empty();
        }
    }

    static final class ArchitecturePolicy {
        private final EnumMap<DatabaseType, Integer> scores =
            new EnumMap<>(DatabaseType.class);

        DatabaseType select(
            boolean directLookup,
            boolean flexibleDocuments,
            boolean partitionedTimeSeries,
            boolean relationshipTraversal
        ) {
            scores.clear();

            for (DatabaseType type : DatabaseType.values()) {
                scores.put(type, 0);
            }

            if (directLookup) {
                scores.merge(DatabaseType.KEY_VALUE, 5, Integer::sum);
            }
            if (flexibleDocuments) {
                scores.merge(DatabaseType.DOCUMENT, 5, Integer::sum);
            }
            if (partitionedTimeSeries) {
                scores.merge(DatabaseType.WIDE_COLUMN, 5, Integer::sum);
            }
            if (relationshipTraversal) {
                scores.merge(DatabaseType.GRAPH, 5, Integer::sum);
            }

            return scores.entrySet()
                .stream()
                .max(Map.Entry.comparingByValue())
                .filter(entry -> entry.getValue() > 0)
                .map(Map.Entry::getKey)
                .orElseThrow(() ->
                    new ValidationException(
                        "No workload characteristic selected"
                    )
                );
        }
    }

    static final class WorkflowService {
        private ReviewState state = ReviewState.CREATED;

        public void activate() {
            requireState(ReviewState.CREATED);
            state = ReviewState.ACTIVE;
        }

        public void fail() {
            if (state != ReviewState.ACTIVE) {
                throw new ValidationException(
                    "Only active workflows can fail"
                );
            }
            state = ReviewState.FAILED;
        }

        public void complete() {
            requireState(ReviewState.ACTIVE);
            state = ReviewState.COMPLETED;
        }

        public ReviewState state() {
            return state;
        }

        private void requireState(ReviewState expected) {
            if (state != expected) {
                throw new ValidationException(
                    "Invalid state transition from " +
                    state + " to " + expected
                );
            }
        }
    }

    public static void main(String[] args) {
        try {
            ArchitecturePolicy policy = new ArchitecturePolicy();

            System.out.println("Architecture policy");

            System.out.println(
                "Session: " +
                policy.select(true, false, false, false)
            );

            System.out.println(
                "Catalog: " +
                policy.select(false, true, false, false)
            );

            System.out.println(
                "Telemetry: " +
                policy.select(false, false, true, false)
            );

            System.out.println(
                "Dependencies: " +
                policy.select(false, false, false, true)
            );

            KeyValueRepository sessions =
                new KeyValueRepository();

            sessions.put(
                "session:user-1001",
                "role=analyst",
                Optional.of(Instant.now().plusSeconds(3600))
            );

            DocumentRepository catalog =
                new DocumentRepository();

            catalog.save(
                new Product(
                    "p100",
                    "Edge Gateway",
                    "networking",
                    149.50,
                    List.of("iot", "gateway")
                )
            );

            catalog.save(
                new Product(
                    "p200",
                    "Graph Sensor",
                    "telemetry",
                    89.00,
                    List.of("sensor", "graph")
                )
            );

            List<Product> expensiveProducts =
                catalog.query(product -> product.price() >= 100);

            System.out.println(
                "\nExpensive products: " +
                expensiveProducts.stream()
                    .map(Product::name)
                    .collect(Collectors.joining(", "))
            );

            WideColumnRepository telemetry =
                new WideColumnRepository();

            telemetry.write(
                "device-001",
                "telemetry",
                "2026-10-31T12:00:00Z",
                44.1
            );

            telemetry.write(
                "device-001",
                "telemetry",
                "2026-10-31T12:05:00Z",
                45.2
            );

            telemetry.write(
                "device-002",
                "telemetry",
                "2026-10-31T12:00:00Z",
                38.5
            );

            System.out.println(
                "Telemetry rows: " +
                telemetry.readFamily("telemetry").size()
            );

            DependencyGraph graph =
                new DependencyGraph();

            for (String node :
                List.of(
                    "api",
                    "orders",
                    "inventory",
                    "payments",
                    "inventory-db"
                )) {
                graph.addNode(node);
            }

            graph.addEdge("api", "calls", "orders");
            graph.addEdge("orders", "calls", "inventory");
            graph.addEdge("orders", "calls", "payments");
            graph.addEdge("inventory", "reads", "inventory-db");

            System.out.println(
                "Dependency path: " +
                graph.shortestPath("api", "inventory-db")
                    .orElseThrow()
            );

            WorkflowService workflow =
                new WorkflowService();

            workflow.activate();
            workflow.complete();

            System.out.println(
                "Workflow state: " + workflow.state()
            );

            try {
                catalog.save(
                    new Product(
                        "p100",
                        "Duplicate",
                        "invalid",
                        1.0,
                        List.of()
                    )
                );
            } catch (ValidationException error) {
                System.out.println(
                    "Duplicate document rejected: " +
                    error.getMessage()
                );
            }

            try {
                sessions.get("missing");
            } catch (NotFoundException error) {
                System.out.println(
                    "Missing key rejected: " +
                    error.getMessage()
                );
            }

            System.out.println(
                "Enterprise NoSQL model completed."
            );

        } catch (RuntimeException error) {
            System.err.println(
                "Application failure: " + error.getMessage()
            );
            System.exit(1);
        }
    }
}
