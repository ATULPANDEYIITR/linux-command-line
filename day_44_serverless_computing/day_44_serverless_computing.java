import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public class ServerlessArchitectureDemo {

    enum EventType {
        HTTP_REQUEST,
        FILE_UPLOADED,
        ORDER_CREATED,
        TIMER
    }

    enum PullRequestState {
        DRAFT,
        OPEN,
        MERGED,
        CLOSED
    }

    record Event(
        String id,
        EventType type,
        Map<String, String> payload,
        Instant createdAt
    ) {
        static Event create(
            EventType type,
            Map<String, String> payload
        ) {
            return new Event(
                UUID.randomUUID().toString(),
                type,
                Map.copyOf(payload),
                Instant.now()
            );
        }
    }

    record FunctionMetrics(
        long invocations,
        long failures,
        double totalDurationMs
    ) {
        double averageDurationMs() {
            return invocations == 0
                ? 0.0
                : totalDurationMs / invocations;
        }
    }

    @FunctionalInterface
    interface EventHandler {
        Map<String, Object> handle(Event event) throws Exception;
    }

    static final class ServerlessFunction {
        private final String name;
        private final EventHandler handler;
        private final long timeoutMs;
        private final int memoryMb;

        private long invocations;
        private long failures;
        private double totalDurationMs;
        private boolean warm;

        ServerlessFunction(
            String name,
            EventHandler handler,
            long timeoutMs,
            int memoryMb
        ) {
            if (timeoutMs <= 0 || memoryMb <= 0) {
                throw new IllegalArgumentException(
                    "Invalid function configuration"
                );
            }

            this.name = name;
            this.handler = handler;
            this.timeoutMs = timeoutMs;
            this.memoryMb = memoryMb;
        }

        CompletableFuture<Map<String, Object>> invoke(
            Event event,
            ExecutorService executor
        ) {
            return CompletableFuture.supplyAsync(
                () -> {
                    long started = System.nanoTime();
                    invocations++;

                    boolean coldStart = !warm;

                    try {
                        if (!warm) {
                            warm = true;
                            sleep(25);
                        }

                        Map<String, Object> result =
                            handler.handle(event);

                        double durationMs =
                            elapsedMilliseconds(started);

                        if (durationMs > timeoutMs) {
                            throw new RuntimeException(
                                "Function timeout: " + name
                            );
                        }

                        totalDurationMs += durationMs;

                        Map<String, Object> response =
                            new HashMap<>(result);

                        response.put("function", name);
                        response.put("eventId", event.id());
                        response.put("coldStart", coldStart);

                        return response;
                    } catch (Exception ex) {
                        failures++;
                        totalDurationMs +=
                            elapsedMilliseconds(started);

                        throw new CompletionException(ex);
                    }
                },
                executor
            );
        }

        FunctionMetrics metrics() {
            return new FunctionMetrics(
                invocations,
                failures,
                totalDurationMs
            );
        }

        String name() {
            return name;
        }

        private static double elapsedMilliseconds(
            long started
        ) {
            return (System.nanoTime() - started) / 1_000_000.0;
        }
    }

    static final class EventRouter {
        private final Map<EventType, List<ServerlessFunction>>
            subscriptions = new EnumMap<>(EventType.class);

        void subscribe(
            EventType type,
            ServerlessFunction function
        ) {
            subscriptions
                .computeIfAbsent(
                    type,
                    ignored -> new ArrayList<>()
                )
                .add(function);
        }

        CompletableFuture<Void> publish(
            Event event,
            ExecutorService executor
        ) {
            List<ServerlessFunction> consumers =
                subscriptions.getOrDefault(
                    event.type(),
                    List.of()
                );

            CompletableFuture<?>[] futures =
                consumers.stream()
                    .map(
                        function ->
                            function.invoke(event, executor)
                    )
                    .toArray(CompletableFuture[]::new);

            return CompletableFuture.allOf(futures);
        }
    }

    static final class IdempotencyStore {
        private final Map<String, Map<String, Object>> results =
            new ConcurrentHashMap<>();

        boolean contains(String eventId) {
            return results.containsKey(eventId);
        }

        Map<String, Object> get(String eventId) {
            return results.get(eventId);
        }

        void save(
            String eventId,
            Map<String, Object> result
        ) {
            results.putIfAbsent(eventId, result);
        }
    }

    record BranchProtectionPolicy(
        int requiredApprovals,
        Set<String> requiredChecks,
        boolean blockDirectPush,
        boolean blockForcePush,
        boolean requireLinearHistory
    ) {
        BranchProtectionPolicy {
            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                    "requiredApprovals cannot be negative"
                );
            }

            requiredChecks = Set.copyOf(requiredChecks);
        }
    }

    static final class PullRequest {
        private final int number;
        private final String sourceBranch;
        private final String targetBranch;

        private PullRequestState state;
        private boolean mergeable;
        private boolean approvalsStale;

        private final Set<String> reviewers =
            new HashSet<>();

        private final Set<String> approvals =
            new HashSet<>();

        private final Set<String> completedChecks =
            new HashSet<>();

        PullRequest(
            int number,
            String sourceBranch,
            String targetBranch
        ) {
            if (sourceBranch.equals(targetBranch)) {
                throw new IllegalArgumentException(
                    "Source and target branches must differ"
                );
            }

            this.number = number;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.state = PullRequestState.DRAFT;
            this.mergeable = true;
        }

        void markReadyForReview() {
            if (state != PullRequestState.DRAFT) {
                throw new IllegalStateException(
                    "Only drafts can become ready"
                );
            }

            state = PullRequestState.OPEN;
        }

        void addReviewer(String reviewer) {
            if (reviewer.isBlank()) {
                throw new IllegalArgumentException(
                    "Reviewer cannot be blank"
                );
            }

            reviewers.add(reviewer);
        }

        void approve(String reviewer) {
            if (state != PullRequestState.OPEN) {
                throw new IllegalStateException(
                    "Only open Pull Requests can be approved"
                );
            }

            if (!reviewers.contains(reviewer)) {
                throw new IllegalStateException(
                    "Reviewer is not eligible"
                );
            }

            approvals.add(reviewer);
        }

        void completeCheck(String check) {
            completedChecks.add(check);
        }

        void markApprovalsStale() {
            approvalsStale = true;
        }

        void setMergeable(boolean mergeable) {
            this.mergeable = mergeable;
        }

        String targetBranch() {
            return targetBranch;
        }

        Set<String> approvals() {
            return Set.copyOf(approvals);
        }

        Set<String> completedChecks() {
            return Set.copyOf(completedChecks);
        }

        boolean isMergeable() {
            return mergeable;
        }

        boolean approvalsAreStale() {
            return approvalsStale;
        }

        PullRequestState state() {
            return state;
        }

        int number() {
            return number;
        }
    }

    static final class MergeEligibilityService {
        private final Map<String, BranchProtectionPolicy> policies =
            new HashMap<>();

        void protect(
            String branch,
            BranchProtectionPolicy policy
        ) {
            policies.put(branch, policy);
        }

        List<String> blockers(PullRequest pr) {
            List<String> blockers = new ArrayList<>();

            if (pr.state() != PullRequestState.OPEN) {
                blockers.add("Pull Request is not open");
            }

            if (!pr.isMergeable()) {
                blockers.add("Branch conflict exists");
            }

            if (pr.approvalsAreStale()) {
                blockers.add("Approvals are stale");
            }

            BranchProtectionPolicy policy =
                policies.get(pr.targetBranch());

            if (policy == null) {
                return blockers;
            }

            if (
                pr.approvals().size()
                    < policy.requiredApprovals()
            ) {
                blockers.add(
                    "Required approval count not reached"
                );
            }

            for (String check : policy.requiredChecks()) {
                if (!pr.completedChecks().contains(check)) {
                    blockers.add(
                        "Required check missing: " + check
                    );
                }
            }

            return blockers;
        }

        boolean canMerge(PullRequest pr) {
            return blockers(pr).isEmpty();
        }
    }

    static Map<String, Object> httpHandler(Event event) {
        String method = event.payload().get("method");
        String path = event.payload().get("path");

        if (
            method == null ||
            !Set.of("GET", "POST", "PUT", "DELETE").contains(method)
        ) {
            throw new IllegalArgumentException(
                "Invalid HTTP method"
            );
        }

        if (path == null || !path.startsWith("/")) {
            throw new IllegalArgumentException(
                "Invalid HTTP path"
            );
        }

        return Map.of(
            "status", 200,
            "method", method,
            "path", path
        );
    }

    static Map<String, Object> orderHandler(Event event) {
        String customer = event.payload().get("customer");
        String amount = event.payload().get("amount");

        if (customer == null || amount == null) {
            throw new IllegalArgumentException(
                "Incomplete order event"
            );
        }

        return Map.of(
            "status", "accepted",
            "customer", customer,
            "amount", amount
        );
    }

    static void demonstrateServerlessFunctions(
        ExecutorService executor
    ) throws Exception {
        System.out.println(
            "\n=== Function and Event Execution ==="
        );

        ServerlessFunction httpFunction =
            new ServerlessFunction(
                "http-api",
                ServerlessArchitectureDemo::httpHandler,
                3000,
                256
            );

        ServerlessFunction orderFunction =
            new ServerlessFunction(
                "order-processor",
                ServerlessArchitectureDemo::orderHandler,
                3000,
                512
            );

        Event request = Event.create(
            EventType.HTTP_REQUEST,
            Map.of(
                "method", "GET",
                "path", "/api/orders"
            )
        );

        System.out.println(
            httpFunction
                .invoke(request, executor)
                .get()
        );

        Event order = Event.create(
            EventType.ORDER_CREATED,
            Map.of(
                "customer", "customer-42",
                "amount", "1499.50"
            )
        );

        System.out.println(
            orderFunction
                .invoke(order, executor)
                .get()
        );

        System.out.println(
            "Order metrics: "
                + orderFunction.metrics()
        );
    }

    static void demonstrateIdempotency(
        ExecutorService executor
    ) throws Exception {
        System.out.println(
            "\n=== Idempotent Event Handling ==="
        );

        IdempotencyStore store =
            new IdempotencyStore();

        ServerlessFunction processor =
            new ServerlessFunction(
                "idempotent-order",
                ServerlessArchitectureDemo::orderHandler,
                3000,
                256
            );

        Event event = Event.create(
            EventType.ORDER_CREATED,
            Map.of(
                "customer", "customer-7",
                "amount", "2500"
            )
        );

        if (!store.contains(event.id())) {
            Map<String, Object> result =
                processor.invoke(event, executor).get();

            store.save(event.id(), result);
            System.out.println(result);
        }

        if (store.contains(event.id())) {
            System.out.println(
                "Duplicate event detected; "
                    + "cached result returned"
            );
        }
    }

    static void demonstrateGovernance() {
        System.out.println(
            "\n=== Enterprise Serverless Governance Model ==="
        );

        MergeEligibilityService service =
            new MergeEligibilityService();

        service.protect(
            "main",
            new BranchProtectionPolicy(
                2,
                Set.of(
                    "build",
                    "unit-tests",
                    "security-scan"
                ),
                true,
                true,
                true
            )
        );

        PullRequest pr =
            new PullRequest(
                42,
                "feature/payment-validation",
                "main"
            );

        pr.markReadyForReview();
        pr.addReviewer("alice");
        pr.addReviewer("bob");

        pr.approve("alice");
        pr.completeCheck("build");
        pr.completeCheck("unit-tests");

        System.out.println(
            "Initial blockers: "
                + service.blockers(pr)
        );

        pr.approve("bob");
        pr.completeCheck("security-scan");

        System.out.println(
            "After policy conditions: "
                + service.blockers(pr)
        );

        System.out.println(
            "Can merge: "
                + service.canMerge(pr)
        );

        pr.markApprovalsStale();

        System.out.println(
            "After approval dismissal: "
                + service.blockers(pr)
        );
    }

    static void demonstrateScaling() {
        System.out.println(
            "\n=== Scaling Capacity ==="
        );

        int minInstances = 0;
        int maxInstances = 8;
        int targetConcurrency = 4;

        for (int queueDepth :
            List.of(0, 1, 4, 5, 12, 25, 100)) {

            int desired =
                queueDepth == 0
                    ? minInstances
                    : Math.min(
                        maxInstances,
                        Math.max(
                            minInstances,
                            (queueDepth
                                + targetConcurrency
                                - 1)
                                / targetConcurrency
                        )
                    );

            System.out.printf(
                "queue=%d desiredInstances=%d%n",
                queueDepth,
                desired
            );
        }
    }

    static void sleep(long milliseconds) {
        try {
            Thread.sleep(milliseconds);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(
                "Interrupted during function execution",
                ex
            );
        }
    }

    public static void main(String[] args)
        throws Exception {

        ExecutorService executor =
            Executors.newFixedThreadPool(8);

        try {
            demonstrateServerlessFunctions(executor);
            demonstrateIdempotency(executor);
            demonstrateGovernance();
            demonstrateScaling();
        } finally {
            executor.shutdown();

            if (!executor.awaitTermination(
                5,
                TimeUnit.SECONDS
            )) {
                executor.shutdownNow();
            }
        }
    }
}
