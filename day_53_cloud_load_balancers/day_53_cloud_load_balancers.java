import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * Enterprise Cloud Load Balancer Governance Model.
 *
 * Java 17, standard library only.
 *
 * The program models:
 * - Load balancer listeners
 * - TLS termination
 * - Backend target groups
 * - Health checks
 * - Weighted and least-connection routing
 * - Sticky sessions
 * - Backend state transitions
 * - Routing policies
 * - Operational validation
 * - Audit logging
 */
public class CloudLoadBalancerEnterprise {

    enum Protocol {
        HTTP,
        HTTPS
    }

    enum TargetState {
        HEALTHY,
        UNHEALTHY,
        DRAINING
    }

    enum RoutingAlgorithm {
        WEIGHTED,
        LEAST_CONNECTIONS
    }

    enum HealthOutcome {
        SUCCESS,
        FAILURE
    }

    record HealthCheckPolicy(
        String path,
        int healthyThreshold,
        int unhealthyThreshold,
        int timeoutMillis
    ) {
        public HealthCheckPolicy {
            Objects.requireNonNull(path, "Health-check path is required");

            if (!path.startsWith("/")) {
                throw new IllegalArgumentException(
                    "Health-check path must begin with '/'"
                );
            }

            if (
                healthyThreshold < 1 ||
                unhealthyThreshold < 1 ||
                timeoutMillis <= 0
            ) {
                throw new IllegalArgumentException(
                    "Invalid health-check policy"
                );
            }
        }
    }

    record TlsPolicy(
        String certificateHostname,
        String certificateId,
        String minimumVersion
    ) {
        public TlsPolicy {
            Objects.requireNonNull(certificateHostname);
            Objects.requireNonNull(certificateId);
            Objects.requireNonNull(minimumVersion);

            if (!certificateHostname.contains(".")) {
                throw new IllegalArgumentException(
                    "Certificate hostname is invalid"
                );
            }

            if (
                !minimumVersion.equals("TLSv1.2") &&
                !minimumVersion.equals("TLSv1.3")
            ) {
                throw new IllegalArgumentException(
                    "Only TLSv1.2 and TLSv1.3 are supported"
                );
            }
        }
    }

    record ClientRequest(
        String requestId,
        String clientIp,
        String host,
        String path,
        Protocol protocol,
        String sessionId
    ) {
        public ClientRequest {
            Objects.requireNonNull(requestId);
            Objects.requireNonNull(clientIp);
            Objects.requireNonNull(host);
            Objects.requireNonNull(path);
            Objects.requireNonNull(protocol);

            if (requestId.isBlank() || clientIp.isBlank()) {
                throw new IllegalArgumentException(
                    "Request identity cannot be blank"
                );
            }

            if (!path.startsWith("/")) {
                throw new IllegalArgumentException(
                    "Request path must begin with '/'"
                );
            }
        }
    }

    record RouteDecision(
        int status,
        String targetId,
        boolean tlsTerminated,
        String reason
    ) {}

    record AuditEvent(
        Instant timestamp,
        String requestId,
        String eventType,
        String targetId,
        String detail
    ) {}

    static final class BackendTarget {
        private final String id;
        private final String host;
        private final int port;
        private final int weight;
        private final int latencyMillis;

        private TargetState state = TargetState.HEALTHY;
        private boolean simulatedHealth = true;

        private int consecutiveSuccesses;
        private int consecutiveFailures;
        private int activeConnections;
        private long requests;
        private long failedRequests;

        BackendTarget(
            String id,
            String host,
            int port,
            int weight,
            int latencyMillis
        ) {
            this.id = Objects.requireNonNull(id);
            this.host = Objects.requireNonNull(host);
            this.port = port;
            this.weight = weight;
            this.latencyMillis = latencyMillis;

            validate();
        }

        private void validate() {
            if (
                id.isBlank() ||
                host.isBlank() ||
                port < 1 ||
                port > 65535
            ) {
                throw new IllegalArgumentException(
                    "Invalid backend target definition"
                );
            }

            if (weight < 1 || latencyMillis < 0) {
                throw new IllegalArgumentException(
                    "Invalid target weight or latency"
                );
            }
        }

        public String id() {
            return id;
        }

        public int weight() {
            return weight;
        }

        public int activeConnections() {
            return activeConnections;
        }

        public int latencyMillis() {
            return latencyMillis;
        }

        public TargetState state() {
            return state;
        }

        public long requests() {
            return requests;
        }

        public long failedRequests() {
            return failedRequests;
        }

        public void setSimulatedHealth(boolean healthy) {
            this.simulatedHealth = healthy;
        }

        public boolean available() {
            return state == TargetState.HEALTHY;
        }

        public HealthOutcome healthCheck(HealthCheckPolicy policy) {
            if (state == TargetState.DRAINING) {
                return HealthOutcome.FAILURE;
            }

            if (simulatedHealth) {
                consecutiveSuccesses++;
                consecutiveFailures = 0;

                if (consecutiveSuccesses >= policy.healthyThreshold()) {
                    state = TargetState.HEALTHY;
                }

                return HealthOutcome.SUCCESS;
            }

            consecutiveFailures++;
            consecutiveSuccesses = 0;

            if (consecutiveFailures >= policy.unhealthyThreshold()) {
                state = TargetState.UNHEALTHY;
            }

            return HealthOutcome.FAILURE;
        }

        public void beginRequest() {
            if (!available()) {
                throw new IllegalStateException(
                    "Target is not eligible for new traffic: " + id
                );
            }

            activeConnections++;
            requests++;
        }

        public void finishRequest(boolean failed) {
            if (activeConnections > 0) {
                activeConnections--;
            }

            if (failed) {
                failedRequests++;
            }
        }
    }

    static final class TargetGroup {
        private final String name;
        private final HealthCheckPolicy healthPolicy;
        private final RoutingAlgorithm algorithm;
        private final Map<String, BackendTarget> targets =
            new HashMap<>();

        TargetGroup(
            String name,
            HealthCheckPolicy healthPolicy,
            RoutingAlgorithm algorithm
        ) {
            this.name = Objects.requireNonNull(name);
            this.healthPolicy = Objects.requireNonNull(healthPolicy);
            this.algorithm = Objects.requireNonNull(algorithm);

            if (name.isBlank()) {
                throw new IllegalArgumentException(
                    "Target-group name cannot be blank"
                );
            }
        }

        public String name() {
            return name;
        }

        public void register(BackendTarget target) {
            if (targets.containsKey(target.id())) {
                throw new IllegalArgumentException(
                    "Duplicate backend target: " + target.id()
                );
            }

            targets.put(target.id(), target);
        }

        public Optional<BackendTarget> find(String targetId) {
            return Optional.ofNullable(targets.get(targetId));
        }

        public void runHealthChecks() {
            targets.values().forEach(
                target -> target.healthCheck(healthPolicy)
            );
        }

        public List<BackendTarget> healthyTargets() {
            return targets.values()
                .stream()
                .filter(BackendTarget::available)
                .toList();
        }

        public BackendTarget select(String routingKey) {
            List<BackendTarget> healthy = healthyTargets();

            if (healthy.isEmpty()) {
                throw new IllegalStateException(
                    "No healthy targets in " + name
                );
            }

            if (algorithm == RoutingAlgorithm.LEAST_CONNECTIONS) {
                return healthy.stream()
                    .min(
                        Comparator
                            .comparingInt(
                                BackendTarget::activeConnections
                            )
                            .thenComparingInt(
                                BackendTarget::latencyMillis
                            )
                            .thenComparing(
                                BackendTarget::id
                            )
                    )
                    .orElseThrow();
            }

            int totalWeight = healthy.stream()
                .mapToInt(BackendTarget::weight)
                .sum();

            int point = Math.floorMod(
                routingKey.hashCode(),
                totalWeight
            );

            for (BackendTarget target : healthy) {
                if (point < target.weight()) {
                    return target;
                }

                point -= target.weight();
            }

            return healthy.get(healthy.size() - 1);
        }

        public List<BackendTarget> targets() {
            return new ArrayList<>(targets.values());
        }
    }

    static final class LoadBalancer {
        private final String name;
        private final TlsPolicy tlsPolicy;
        private final boolean stickySessions;

        private final Map<String, TargetGroup> groups =
            new HashMap<>();

        private final Map<String, String> sessionTargets =
            new HashMap<>();

        private final List<AuditEvent> auditEvents =
            new ArrayList<>();

        LoadBalancer(
            String name,
            TlsPolicy tlsPolicy,
            boolean stickySessions
        ) {
            this.name = Objects.requireNonNull(name);
            this.tlsPolicy = Objects.requireNonNull(tlsPolicy);
            this.stickySessions = stickySessions;

            if (name.isBlank()) {
                throw new IllegalArgumentException(
                    "Load-balancer name cannot be blank"
                );
            }
        }

        public void addTargetGroup(TargetGroup group) {
            if (groups.containsKey(group.name())) {
                throw new IllegalArgumentException(
                    "Duplicate target group: " + group.name()
                );
            }

            groups.put(group.name(), group);
        }

        public void synchronizeHealth() {
            groups.values().forEach(TargetGroup::runHealthChecks);

            auditEvents.add(
                new AuditEvent(
                    Instant.now(),
                    "system",
                    "HEALTH_CHECK_CYCLE",
                    null,
                    "All configured target groups evaluated"
                )
            );
        }

        private void validateTls(ClientRequest request) {
            if (request.protocol() != Protocol.HTTPS) {
                return;
            }

            if (
                !request.host().equals(
                    tlsPolicy.certificateHostname()
                )
            ) {
                throw new SecurityException(
                    "TLS certificate hostname mismatch"
                );
            }
        }

        public RouteDecision route(
            ClientRequest request,
            String groupName
        ) {
            TargetGroup group = groups.get(groupName);

            if (group == null) {
                return new RouteDecision(
                    503,
                    null,
                    false,
                    "Target group does not exist"
                );
            }

            try {
                validateTls(request);
            } catch (SecurityException exception) {
                auditEvents.add(
                    new AuditEvent(
                        Instant.now(),
                        request.requestId(),
                        "TLS_REJECTED",
                        null,
                        exception.getMessage()
                    )
                );

                return new RouteDecision(
                    421,
                    null,
                    false,
                    exception.getMessage()
                );
            }

            BackendTarget target = null;

            if (
                stickySessions &&
                request.sessionId() != null &&
                !request.sessionId().isBlank()
            ) {
                String mappedId =
                    sessionTargets.get(request.sessionId());

                if (mappedId != null) {
                    target = group.find(mappedId)
                        .filter(BackendTarget::available)
                        .orElse(null);
                }
            }

            if (target == null) {
                try {
                    target = group.select(
                        request.sessionId() != null
                            ? request.sessionId()
                            : request.requestId()
                    );
                } catch (IllegalStateException exception) {
                    return new RouteDecision(
                        503,
                        null,
                        request.protocol() == Protocol.HTTPS,
                        exception.getMessage()
                    );
                }

                if (
                    stickySessions &&
                    request.sessionId() != null &&
                    !request.sessionId().isBlank()
                ) {
                    sessionTargets.put(
                        request.sessionId(),
                        target.id()
                    );
                }
            }

            target.beginRequest();

            boolean failed = !target.available();

            try {
                auditEvents.add(
                    new AuditEvent(
                        Instant.now(),
                        request.requestId(),
                        failed ? "BACKEND_FAILURE" : "REQUEST_SERVED",
                        target.id(),
                        failed
                            ? "Backend unavailable"
                            : "TLS terminated and request routed"
                    )
                );

                return new RouteDecision(
                    failed ? 502 : 200,
                    target.id(),
                    request.protocol() == Protocol.HTTPS,
                    failed
                        ? "Backend target unavailable"
                        : "Request routed successfully"
                );
            } finally {
                target.finishRequest(failed);
            }
        }

        public List<AuditEvent> auditEvents() {
            return List.copyOf(auditEvents);
        }
    }

    private static void printTargets(TargetGroup group) {
        System.out.println("\nTarget group: " + group.name());

        group.targets().stream()
            .sorted(Comparator.comparing(BackendTarget::id))
            .forEach(
                target -> System.out.printf(
                    "  %s state=%s weight=%d requests=%d failures=%d%n",
                    target.id(),
                    target.state(),
                    target.weight(),
                    target.requests(),
                    target.failedRequests()
                )
            );
    }

    public static void main(String[] args) {
        HealthCheckPolicy healthPolicy =
            new HealthCheckPolicy(
                "/health",
                2,
                2,
                2000
            );

        TlsPolicy tlsPolicy =
            new TlsPolicy(
                "api.example.com",
                "prod-certificate-2026",
                "TLSv1.2"
            );

        TargetGroup production =
            new TargetGroup(
                "api-production",
                healthPolicy,
                RoutingAlgorithm.LEAST_CONNECTIONS
            );

        BackendTarget apiA =
            new BackendTarget(
                "api-a",
                "10.20.0.10",
                8080,
                1,
                15
            );

        BackendTarget apiB =
            new BackendTarget(
                "api-b",
                "10.20.0.11",
                8080,
                1,
                20
            );

        BackendTarget apiC =
            new BackendTarget(
                "api-c",
                "10.20.0.12",
                8080,
                1,
                27
            );

        production.register(apiA);
        production.register(apiB);
        production.register(apiC);

        LoadBalancer loadBalancer =
            new LoadBalancer(
                "enterprise-api-lb",
                tlsPolicy,
                true
            );

        loadBalancer.addTargetGroup(production);

        /*
         * The threshold is two consecutive successes. This prevents a
         * backend from being trusted based on a single probe.
         */
        loadBalancer.synchronizeHealth();
        loadBalancer.synchronizeHealth();

        System.out.println("Initial routing");

        for (int i = 1; i <= 9; i++) {
            ClientRequest request =
                new ClientRequest(
                    "req-" + i,
                    "192.0.2." + (10 + i),
                    "api.example.com",
                    "/orders",
                    Protocol.HTTPS,
                    "customer-" + (i % 3)
                );

            RouteDecision decision =
                loadBalancer.route(
                    request,
                    "api-production"
                );

            System.out.printf(
                "%s -> status=%d target=%s reason=%s%n",
                request.requestId(),
                decision.status(),
                decision.targetId(),
                decision.reason()
            );
        }

        printTargets(production);

        /*
         * The backend is deliberately marked unhealthy. Two failed checks
         * transition it to UNHEALTHY, after which routing excludes it.
         */
        apiB.setSimulatedHealth(false);

        loadBalancer.synchronizeHealth();
        loadBalancer.synchronizeHealth();

        System.out.println("\nAfter api-b health failure");
        printTargets(production);

        ClientRequest failoverRequest =
            new ClientRequest(
                "failover-1",
                "198.51.100.20",
                "api.example.com",
                "/orders",
                Protocol.HTTPS,
                "new-session"
            );

        System.out.println(
            loadBalancer.route(
                failoverRequest,
                "api-production"
            )
        );

        /*
         * Recovery requires another two successful checks.
         */
        apiB.setSimulatedHealth(true);

        loadBalancer.synchronizeHealth();
        loadBalancer.synchronizeHealth();

        System.out.println("\nAfter api-b recovery");
        printTargets(production);

        ClientRequest invalidTls =
            new ClientRequest(
                "tls-error",
                "203.0.113.20",
                "wrong.example.net",
                "/orders",
                Protocol.HTTPS,
                null
            );

        System.out.println("\nTLS validation:");
        System.out.println(
            loadBalancer.route(
                invalidTls,
                "api-production"
            )
        );

        System.out.println("\nAudit events:");
        loadBalancer.auditEvents()
            .forEach(
                event -> System.out.printf(
                    "%s | %s | request=%s | target=%s | %s%n",
                    event.timestamp(),
                    event.eventType(),
                    event.requestId(),
                    event.targetId(),
                    event.detail()
                )
            );
    }
}
