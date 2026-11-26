import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

/**
 * Enterprise Kubernetes Control Plane Model.
 *
 * Java 17 implementation covering:
 * - API server request processing
 * - Versioned persistent state
 * - Scheduler filtering and scoring
 * - Controller reconciliation
 * - Component health
 * - Control plane governance
 * - Leader election
 * - Audit records
 * - Failure recovery
 *
 * No third-party dependencies.
 */
public class KubernetesControlPlane {

    // ========================================================
    // 1. ENUMERATIONS
    // ========================================================

    enum PodPhase {
        PENDING,
        RUNNING,
        FAILED,
        SUCCEEDED
    }

    enum NodeStatus {
        READY,
        NOT_READY,
        UNKNOWN
    }

    enum ComponentStatus {
        HEALTHY,
        DEGRADED,
        UNAVAILABLE
    }

    enum CheckStatus {
        PENDING,
        PASSING,
        FAILING
    }

    enum OperationType {
        CREATE,
        UPDATE,
        DELETE,
        SCHEDULE,
        RECONCILE
    }

    // ========================================================
    // 2. EXCEPTIONS
    // ========================================================

    static class ControlPlaneException extends RuntimeException {
        ControlPlaneException(String message) {
            super(message);
        }
    }

    static class ValidationException extends ControlPlaneException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class NotFoundException extends ControlPlaneException {
        NotFoundException(String message) {
            super(message);
        }
    }

    static class ConflictException extends ControlPlaneException {
        ConflictException(String message) {
            super(message);
        }
    }

    static class SchedulingException extends ControlPlaneException {
        SchedulingException(String message) {
            super(message);
        }
    }

    // ========================================================
    // 3. DOMAIN RECORDS
    // ========================================================

    record ResourceMetadata(
        String name,
        String namespace,
        String uid,
        long resourceVersion,
        Map<String, String> labels
    ) {
        ResourceMetadata {
            if (name == null || name.isBlank() ||
                namespace == null || namespace.isBlank()) {
                throw new ValidationException("Invalid resource metadata");
            }

            if (name.length() > 253 || namespace.length() > 63) {
                throw new ValidationException("Metadata exceeds limits");
            }

            uid = uid == null ? UUID.randomUUID().toString() : uid;

            labels = labels == null
                ? Map.of()
                : Map.copyOf(labels);
        }

        ResourceMetadata withVersion(long version) {
            return new ResourceMetadata(
                name,
                namespace,
                uid,
                version,
                labels
            );
        }
    }

    record ContainerSpec(
        String name,
        String image,
        int cpuRequest,
        int memoryRequest
    ) {
        ContainerSpec {
            if (name == null || name.isBlank() ||
                image == null || image.isBlank()) {
                throw new ValidationException(
                    "Container name and image required"
                );
            }

            if (cpuRequest <= 0 || memoryRequest <= 0) {
                throw new ValidationException(
                    "Resource requests must be positive"
                );
            }
        }
    }

    record AuditRecord(
        Instant timestamp,
        OperationType operation,
        String resource,
        String actor,
        String result,
        String details
    ) {}

    record ControlPlaneEvent(
        Instant timestamp,
        String component,
        String eventType,
        String message
    ) {}

    record StatusCheck(
        String name,
        CheckStatus status,
        String details
    ) {}

    // ========================================================
    // 4. POD AGGREGATE
    // ========================================================

    static final class Pod {
        private ResourceMetadata metadata;
        private final List<ContainerSpec> containers;
        private PodPhase phase;
        private String nodeName;
        private int restartCount;

        Pod(ResourceMetadata metadata, List<ContainerSpec> containers) {
            this.metadata = Objects.requireNonNull(metadata);
            this.containers = List.copyOf(containers);
            this.phase = PodPhase.PENDING;
            this.restartCount = 0;

            validate();
        }

        void validate() {
            if (containers.isEmpty()) {
                throw new ValidationException(
                    "Pod requires at least one container"
                );
            }

            Set<String> names = new HashSet<>();

            for (ContainerSpec container : containers) {
                if (!names.add(container.name())) {
                    throw new ValidationException(
                        "Duplicate container name"
                    );
                }
            }

            if (cpuRequest() <= 0 || memoryRequest() <= 0) {
                throw new ValidationException(
                    "Invalid aggregate resource requests"
                );
            }
        }

        int cpuRequest() {
            return containers.stream()
                .mapToInt(ContainerSpec::cpuRequest)
                .sum();
        }

        int memoryRequest() {
            return containers.stream()
                .mapToInt(ContainerSpec::memoryRequest)
                .sum();
        }

        ResourceMetadata metadata() {
            return metadata;
        }

        PodPhase phase() {
            return phase;
        }

        String nodeName() {
            return nodeName;
        }

        void updateVersion(long version) {
            metadata = metadata.withVersion(version);
        }

        void markRunning(String node) {
            if (phase != PodPhase.PENDING) {
                throw new ConflictException(
                    "Only pending pods can become running"
                );
            }

            nodeName = node;
            phase = PodPhase.RUNNING;
        }

        void markFailed() {
            phase = PodPhase.FAILED;
            restartCount++;
        }

        void markPending() {
            phase = PodPhase.PENDING;
            nodeName = null;
        }
    }

    // ========================================================
    // 5. NODE RESOURCE MANAGEMENT
    // ========================================================

    static final class Node {
        private final String name;
        private final int cpuCapacity;
        private final int memoryCapacity;

        private int cpuAllocated;
        private int memoryAllocated;

        private NodeStatus status;

        Node(String name, int cpuCapacity, int memoryCapacity) {
            if (name == null || name.isBlank() ||
                cpuCapacity <= 0 || memoryCapacity <= 0) {
                throw new ValidationException("Invalid node configuration");
            }

            this.name = name;
            this.cpuCapacity = cpuCapacity;
            this.memoryCapacity = memoryCapacity;
            this.status = NodeStatus.READY;
        }

        String name() {
            return name;
        }

        int availableCPU() {
            return cpuCapacity - cpuAllocated;
        }

        int availableMemory() {
            return memoryCapacity - memoryAllocated;
        }

        NodeStatus status() {
            return status;
        }

        void setStatus(NodeStatus status) {
            this.status = Objects.requireNonNull(status);
        }

        boolean canHost(Pod pod) {
            return status == NodeStatus.READY
                && availableCPU() >= pod.cpuRequest()
                && availableMemory() >= pod.memoryRequest();
        }

        synchronized void allocate(Pod pod) {
            if (!canHost(pod)) {
                throw new SchedulingException(
                    "Node is not feasible: " + name
                );
            }

            cpuAllocated += pod.cpuRequest();
            memoryAllocated += pod.memoryRequest();
        }

        synchronized void release(Pod pod) {
            if (cpuAllocated < pod.cpuRequest() ||
                memoryAllocated < pod.memoryRequest()) {
                throw new ConflictException(
                    "Node allocation accounting underflow"
                );
            }

            cpuAllocated -= pod.cpuRequest();
            memoryAllocated -= pod.memoryRequest();
        }

        Map<String, Object> report() {
            return Map.of(
                "name", name,
                "status", status.name(),
                "cpuCapacity", cpuCapacity,
                "cpuAllocated", cpuAllocated,
                "memoryCapacity", memoryCapacity,
                "memoryAllocated", memoryAllocated
            );
        }
    }

    // ========================================================
    // 6. VERSIONED PERSISTENT STORE
    // ========================================================

    static final class EtcdStore {
        private record Entry(Object value, long revision) {}

        private final ConcurrentHashMap<String, Entry> records =
            new ConcurrentHashMap<>();

        private final AtomicLong revision = new AtomicLong();

        long revision() {
            return revision.get();
        }

        synchronized long put(
            String key,
            Object value,
            Long expectedRevision
        ) {
            if (key == null || !key.startsWith("/")) {
                throw new ValidationException("Invalid storage key");
            }

            Entry current = records.get(key);

            long actual = current == null ? 0 : current.revision();

            if (expectedRevision != null &&
                expectedRevision != actual) {
                throw new ConflictException(
                    "Optimistic concurrency conflict"
                );
            }

            long next = revision.incrementAndGet();

            records.put(
                key,
                new Entry(value, next)
            );

            return next;
        }

        synchronized Entry getEntry(String key) {
            Entry entry = records.get(key);

            if (entry == null) {
                throw new NotFoundException(
                    "Resource not found: " + key
                );
            }

            return entry;
        }

        Object get(String key) {
            return getEntry(key).value();
        }

        List<Object> list(String prefix) {
            return records.entrySet().stream()
                .filter(entry -> entry.getKey().startsWith(prefix))
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> entry.getValue().value())
                .toList();
        }

        synchronized void delete(String key) {
            if (records.remove(key) == null) {
                throw new NotFoundException("Resource not found");
            }

            revision.incrementAndGet();
        }
    }

    // ========================================================
    // 7. API SERVER SERVICE
    // ========================================================

    static final class APIServer {
        private final EtcdStore store;
        private final List<AuditRecord> auditLog =
            new ArrayList<>();

        APIServer(EtcdStore store) {
            this.store = store;
        }

        private String podKey(Pod pod) {
            return "/registry/pods/" +
                pod.metadata().namespace() + "/" +
                pod.metadata().name();
        }

        synchronized void createPod(Pod pod, String actor) {
            try {
                pod.validate();

                String key = podKey(pod);

                if (store.list(key).size() > 0) {
                    throw new ConflictException("Pod already exists");
                }

                long version = store.put(
                    key,
                    pod,
                    null
                );

                pod.updateVersion(version);

                audit(
                    OperationType.CREATE,
                    key,
                    actor,
                    "SUCCESS",
                    "Resource persisted"
                );

            } catch (RuntimeException exception) {
                audit(
                    OperationType.CREATE,
                    pod.metadata().name(),
                    actor,
                    "FAILED",
                    exception.getMessage()
                );

                throw exception;
            }
        }

        synchronized void updatePod(Pod pod, String actor) {
            String key = podKey(pod);

            try {
                pod.validate();

                EtcdStore.Entry current = store.getEntry(key);

                long version = store.put(
                    key,
                    pod,
                    current.revision()
                );

                pod.updateVersion(version);

                audit(
                    OperationType.UPDATE,
                    key,
                    actor,
                    "SUCCESS",
                    "Resource updated"
                );

            } catch (RuntimeException exception) {
                audit(
                    OperationType.UPDATE,
                    key,
                    actor,
                    "FAILED",
                    exception.getMessage()
                );

                throw exception;
            }
        }

        Pod getPod(String namespace, String name) {
            return (Pod) store.get(
                "/registry/pods/" + namespace + "/" + name
            );
        }

        synchronized void deletePod(Pod pod, String actor) {
            String key = podKey(pod);

            store.delete(key);

            audit(
                OperationType.DELETE,
                key,
                actor,
                "SUCCESS",
                "Resource deleted"
            );
        }

        synchronized void audit(
            OperationType operation,
            String resource,
            String actor,
            String result,
            String details
        ) {
            auditLog.add(
                new AuditRecord(
                    Instant.now(),
                    operation,
                    resource,
                    actor,
                    result,
                    details
                )
            );
        }

        List<AuditRecord> auditLog() {
            return List.copyOf(auditLog);
        }
    }

    // ========================================================
    // 8. SCHEDULER SERVICE
    // ========================================================

    static final class SchedulerService {
        private final List<Node> nodes;
        private final APIServer apiServer;

        SchedulerService(List<Node> nodes, APIServer apiServer) {
            this.nodes = nodes;
            this.apiServer = apiServer;
        }

        String schedule(Pod pod) {
            if (pod.phase() != PodPhase.PENDING) {
                throw new SchedulingException(
                    "Pod is not pending"
                );
            }

            Optional<Node> selected = nodes.stream()
                .filter(node -> node.canHost(pod))
                .min(
                    Comparator
                        .comparingInt(
                            (Node node) ->
                                node.availableCPU() - pod.cpuRequest()
                        )
                        .thenComparingInt(
                            node ->
                                node.availableMemory() -
                                pod.memoryRequest()
                        )
                        .thenComparing(Node::name)
                );

            if (selected.isEmpty()) {
                throw new SchedulingException(
                    "No feasible node for " + pod.metadata().name()
                );
            }

            Node node = selected.get();

            node.allocate(pod);
            pod.markRunning(node.name());

            try {
                apiServer.updatePod(pod, "scheduler");
                return node.name();
            } catch (RuntimeException exception) {
                node.release(pod);
                pod.markPending();
                throw exception;
            }
        }
    }

    // ========================================================
    // 9. DEPLOYMENT CONTROLLER
    // ========================================================

    record Deployment(
        String name,
        String namespace,
        String image,
        int replicas,
        int cpu,
        int memory
    ) {
        Deployment {
            if (name == null || name.isBlank() ||
                namespace == null || namespace.isBlank() ||
                image == null || image.isBlank() ||
                replicas < 0 || cpu <= 0 || memory <= 0) {
                throw new ValidationException(
                    "Invalid deployment specification"
                );
            }
        }
    }

    static final class DeploymentController {
        private final APIServer apiServer;

        DeploymentController(APIServer apiServer) {
            this.apiServer = apiServer;
        }

        int reconcile(Deployment deployment) {
            String prefix =
                "/registry/pods/" + deployment.namespace() +
                "/" + deployment.name() + "-";

            int observed = apiServer.store.list(prefix).size();

            int created = 0;

            for (int i = observed; i < deployment.replicas(); i++) {
                ResourceMetadata metadata = new ResourceMetadata(
                    deployment.name() + "-" + i,
                    deployment.namespace(),
                    null,
                    0,
                    Map.of("app", deployment.name())
                );

                Pod pod = new Pod(
                    metadata,
                    List.of(
                        new ContainerSpec(
                            "application",
                            deployment.image(),
                            deployment.cpu(),
                            deployment.memory()
                        )
                    )
                );

                apiServer.createPod(
                    pod,
                    "deployment-controller"
                );

                created++;
            }

            return created;
        }
    }

    // ========================================================
    // 10. CONTROL PLANE MONITORING
    // ========================================================

    static final class ComponentMonitor {
        private static final class Component {
            private final String name;
            private final String version;
            private ComponentStatus status;
            private Instant lastHeartbeat;

            Component(String name, String version) {
                this.name = name;
                this.version = version;
                this.status = ComponentStatus.HEALTHY;
                this.lastHeartbeat = Instant.now();
            }
        }

        private final Map<String, Component> components =
            new HashMap<>();

        void register(String name, String version) {
            if (components.containsKey(name)) {
                throw new ConflictException(
                    "Component already registered"
                );
            }

            components.put(name, new Component(name, version));
        }

        void heartbeat(String name) {
            Component component = components.get(name);

            if (component == null) {
                throw new NotFoundException(
                    "Component not found"
                );
            }

            component.lastHeartbeat = Instant.now();
            component.status = ComponentStatus.HEALTHY;
        }

        void setStatus(String name, ComponentStatus status) {
            Component component = components.get(name);

            if (component == null) {
                throw new NotFoundException(
                    "Component not found"
                );
            }

            component.status = status;
        }

        Map<String, ComponentStatus> evaluate(long timeoutSeconds) {
            if (timeoutSeconds <= 0) {
                throw new ValidationException(
                    "Invalid heartbeat timeout"
                );
            }

            Instant now = Instant.now();

            Map<String, ComponentStatus> result = new HashMap<>();

            for (Component component : components.values()) {
                if (component.lastHeartbeat.plusSeconds(
                    timeoutSeconds
                ).isBefore(now)) {
                    component.status = ComponentStatus.UNAVAILABLE;
                }

                result.put(component.name, component.status);
            }

            return Map.copyOf(result);
        }
    }

    // ========================================================
    // 11. ENTERPRISE GOVERNANCE POLICY
    // ========================================================

    record ControlPlanePolicy(
        boolean requireApiServer,
        boolean requireScheduler,
        boolean requireControllerManager,
        boolean requireEtcd,
        boolean rejectDegradedComponents,
        int minimumReadyNodes
    ) {
        ControlPlanePolicy {
            if (minimumReadyNodes < 0) {
                throw new ValidationException(
                    "Minimum ready nodes cannot be negative"
                );
            }
        }
    }

    record PolicyEvaluation(
        boolean accepted,
        List<String> violations
    ) {
        PolicyEvaluation {
            violations = List.copyOf(violations);
        }
    }

    static final class GovernanceService {
        private final ControlPlanePolicy policy;

        GovernanceService(ControlPlanePolicy policy) {
            this.policy = policy;
        }

        PolicyEvaluation evaluate(
            Map<String, ComponentStatus> components,
            List<Node> nodes
        ) {
            List<String> violations = new ArrayList<>();

            Map<String, Boolean> required = Map.of(
                "kube-apiserver", policy.requireApiServer(),
                "kube-scheduler", policy.requireScheduler(),
                "kube-controller-manager",
                    policy.requireControllerManager(),
                "etcd", policy.requireEtcd()
            );

            for (var entry : required.entrySet()) {
                if (!entry.getValue()) {
                    continue;
                }

                ComponentStatus status = components.get(entry.getKey());

                if (status == null) {
                    violations.add(
                        "Missing component: " + entry.getKey()
                    );
                    continue;
                }

                if (status == ComponentStatus.UNAVAILABLE) {
                    violations.add(
                        "Unavailable: " + entry.getKey()
                    );
                }

                if (policy.rejectDegradedComponents() &&
                    status == ComponentStatus.DEGRADED) {
                    violations.add(
                        "Degraded: " + entry.getKey()
                    );
                }
            }

            long readyNodes = nodes.stream()
                .filter(node -> node.status() == NodeStatus.READY)
                .count();

            if (readyNodes < policy.minimumReadyNodes()) {
                violations.add("Insufficient ready nodes");
            }

            return new PolicyEvaluation(
                violations.isEmpty(),
                violations
            );
        }
    }

    // ========================================================
    // 12. LEADER ELECTION
    // ========================================================

    static final class LeaderElection {
        private final long leaseDurationMillis;
        private String holder;
        private long renewedAt;

        LeaderElection(long leaseDurationMillis) {
            if (leaseDurationMillis <= 0) {
                throw new ValidationException(
                    "Lease duration must be positive"
                );
            }

            this.leaseDurationMillis = leaseDurationMillis;
        }

        synchronized boolean acquire(String candidate) {
            if (candidate == null || candidate.isBlank()) {
                throw new ValidationException(
                    "Candidate identity required"
                );
            }

            long now = System.currentTimeMillis();

            boolean expired = holder == null ||
                now - renewedAt >= leaseDurationMillis;

            if (expired || holder.equals(candidate)) {
                holder = candidate;
                renewedAt = now;
                return true;
            }

            return false;
        }

        synchronized boolean isLeader(String candidate) {
            return Objects.equals(holder, candidate) &&
                System.currentTimeMillis() - renewedAt <
                    leaseDurationMillis;
        }
    }

    // ========================================================
    // 13. CLUSTER SERVICE
    // ========================================================

    static final class ClusterService {
        private final EtcdStore etcd = new EtcdStore();
        private final APIServer apiServer = new APIServer(etcd);

        private final List<Node> nodes = List.of(
            new Node("worker-01", 8, 2048),
            new Node("worker-02", 4, 1024),
            new Node("worker-03", 8, 4096)
        );

        private final SchedulerService scheduler =
            new SchedulerService(nodes, apiServer);

        private final DeploymentController controller =
            new DeploymentController(apiServer);

        private final ComponentMonitor monitor =
            new ComponentMonitor();

        private final LeaderElection election =
            new LeaderElection(15000);

        ClusterService() {
            monitor.register("kube-apiserver", "v1.32.0");
            monitor.register("kube-scheduler", "v1.32.0");
            monitor.register("kube-controller-manager", "v1.32.0");
            monitor.register("etcd", "3.5.17");
        }

        void deploy(Deployment deployment) {
            controller.reconcile(deployment);
        }

        List<String> schedulePending() {
            List<String> results = new ArrayList<>();

            for (Object value : etcd.list("/registry/pods/")) {
                Pod pod = (Pod) value;

                if (pod.phase() != PodPhase.PENDING) {
                    continue;
                }

                try {
                    String node = scheduler.schedule(pod);

                    results.add(
                        pod.metadata().name() + " -> " + node
                    );

                } catch (SchedulingException exception) {
                    results.add(
                        pod.metadata().name() + " -> UNSCHEDULABLE"
                    );
                }
            }

            return results;
        }

        Map<String, Object> report() {
            List<Pod> pods = etcd.list("/registry/pods/")
                .stream()
                .map(Pod.class::cast)
                .toList();

            Map<String, Long> phaseCounts = pods.stream()
                .collect(
                    Collectors.groupingBy(
                        pod -> pod.phase().name(),
                        Collectors.counting()
                    )
                );

            Map<String, Object> result = new HashMap<>();

            result.put("etcdRevision", etcd.revision());
            result.put("podCount", pods.size());
            result.put("phaseCounts", phaseCounts);

            result.put(
                "nodes",
                nodes.stream().map(Node::report).toList()
            );

            result.put(
                "components",
                monitor.evaluate(30)
            );

            result.put(
                "auditRecords",
                apiServer.auditLog().size()
            );

            return result;
        }
    }

    // ========================================================
    // 14. EXECUTABLE TESTS
    // ========================================================

    public static void main(String[] args) {
        try {
            ClusterService cluster = new ClusterService();

            if (!cluster.election.acquire("controller-01")) {
                throw new ControlPlaneException(
                    "Leader election failed"
                );
            }

            if (!cluster.election.isLeader("controller-01")) {
                throw new ControlPlaneException(
                    "Leadership verification failed"
                );
            }

            Deployment deployment = new Deployment(
                "web",
                "production",
                "nginx:1.27",
                3,
                1,
                256
            );

            cluster.deploy(deployment);

            List<String> scheduling = cluster.schedulePending();

            if (scheduling.size() != 3) {
                throw new ControlPlaneException(
                    "Unexpected scheduling count"
                );
            }

            for (String result : scheduling) {
                System.out.println(result);
            }

            ControlPlanePolicy policy = new ControlPlanePolicy(
                true,
                true,
                true,
                true,
                true,
                2
            );

            GovernanceService governance =
                new GovernanceService(policy);

            PolicyEvaluation initial = governance.evaluate(
                cluster.monitor.evaluate(30),
                cluster.nodes
            );

            if (!initial.accepted()) {
                throw new ControlPlaneException(
                    "Initial governance validation failed"
                );
            }

            System.out.println("\nINITIAL GOVERNANCE: ACCEPTED");

            // Simulate etcd unavailability.
            cluster.monitor.setStatus(
                "etcd",
                ComponentStatus.UNAVAILABLE
            );

            PolicyEvaluation failed = governance.evaluate(
                cluster.monitor.evaluate(30),
                cluster.nodes
            );

            if (failed.accepted()) {
                throw new ControlPlaneException(
                    "Etcd outage was not detected"
                );
            }

            System.out.println("\nETCD FAILURE DETECTED");

            failed.violations().forEach(
                System.out::println
            );

            // Restore service.
            cluster.monitor.heartbeat("etcd");

            PolicyEvaluation recovered = governance.evaluate(
                cluster.monitor.evaluate(30),
                cluster.nodes
            );

            if (!recovered.accepted()) {
                throw new ControlPlaneException(
                    "Recovery validation failed"
                );
            }

            System.out.println("\nRECOVERY: ACCEPTED");

            // Invalid container validation.
            try {
                new ContainerSpec(
                    "invalid",
                    "nginx",
                    0,
                    128
                );

                throw new ControlPlaneException(
                    "Invalid container was accepted"
                );

            } catch (ValidationException expected) {
                System.out.println(
                    "INVALID RESOURCE: REJECTED"
                );
            }

            // Unschedulable workload.
            Pod oversized = new Pod(
                new ResourceMetadata(
                    "oversized",
                    "production",
                    null,
                    0,
                    Map.of()
                ),
                List.of(
                    new ContainerSpec(
                        "application",
                        "large-image",
                        100,
                        100000
                    )
                )
            );

            try {
                cluster.scheduler.schedule(oversized);

                throw new ControlPlaneException(
                    "Oversized pod was scheduled"
                );

            } catch (SchedulingException expected) {
                System.out.println(
                    "UNSCHEDULABLE POD: REJECTED"
                );
            }

            System.out.println("\nCLUSTER REPORT");

            System.out.println(
                cluster.report()
            );

            System.out.println(
                "\nAUDIT RECORD COUNT: " +
                cluster.apiServer.auditLog().size()
            );

            System.out.println(
                "\nALL TESTS PASSED"
            );

        } catch (RuntimeException exception) {
            System.err.println(
                "CONTROL PLANE ERROR: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
