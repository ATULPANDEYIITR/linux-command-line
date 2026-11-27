import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

/*
 * KUBERNETES ENTERPRISE POD AND WORKLOAD MANAGEMENT
 *
 * Java 17
 *
 * Features:
 * - Strongly typed workload domain
 * - Immutable resource specifications
 * - Container and Pod lifecycle
 * - Init container processing
 * - Resource-aware scheduling
 * - Readiness and liveness policies
 * - Deployment reconciliation
 * - Rolling updates
 * - Replica management
 * - Operational monitoring
 * - Validation and exception handling
 *
 * Compile:
 * javac PodManagement.java
 *
 * Run:
 * java PodManagement
 */

public class PodManagement {

    // ========================================================
    // 1. ENUMERATIONS
    // ========================================================

    enum PodPhase {
        PENDING,
        RUNNING,
        SUCCEEDED,
        FAILED,
        UNKNOWN
    }

    enum ContainerState {
        WAITING,
        RUNNING,
        TERMINATED
    }

    enum RestartPolicy {
        ALWAYS,
        ON_FAILURE,
        NEVER
    }

    enum WorkloadType {
        DEPLOYMENT,
        JOB,
        DAEMONSET,
        STATEFULSET
    }

    enum ConditionType {
        POD_SCHEDULED,
        INITIALIZED,
        CONTAINERS_READY,
        READY
    }

    // ========================================================
    // 2. CUSTOM EXCEPTIONS
    // ========================================================

    static class PodManagementException extends RuntimeException {
        public PodManagementException(String message) {
            super(message);
        }
    }

    static class SchedulingException extends PodManagementException {
        public SchedulingException(String message) {
            super(message);
        }
    }

    static class ValidationException extends PodManagementException {
        public ValidationException(String message) {
            super(message);
        }
    }

    static class LifecycleException extends PodManagementException {
        public LifecycleException(String message) {
            super(message);
        }
    }

    // ========================================================
    // 3. RESOURCE SPECIFICATION
    // ========================================================

    record ResourceRequirements(
        double cpuRequest,
        double cpuLimit,
        int memoryRequest,
        int memoryLimit
    ) {
        ResourceRequirements {
            if (
                !Double.isFinite(cpuRequest) ||
                !Double.isFinite(cpuLimit) ||
                cpuRequest < 0 ||
                cpuLimit <= 0 ||
                cpuRequest > cpuLimit
            ) {
                throw new ValidationException(
                    "Invalid CPU requests or limits."
                );
            }

            if (
                memoryRequest < 0 ||
                memoryLimit <= 0 ||
                memoryRequest > memoryLimit
            ) {
                throw new ValidationException(
                    "Invalid memory requests or limits."
                );
            }
        }

        static ResourceRequirements defaults() {
            return new ResourceRequirements(
                0.1,
                0.5,
                128,
                512
            );
        }
    }

    record ResourceRequest(double cpu, int memory) {
        ResourceRequest {
            if (
                !Double.isFinite(cpu) ||
                cpu < 0 ||
                memory < 0
            ) {
                throw new ValidationException(
                    "Invalid aggregate resource request."
                );
            }
        }

        ResourceRequest plus(ResourceRequest other) {
            return new ResourceRequest(
                cpu + other.cpu,
                memory + other.memory
            );
        }
    }

    // ========================================================
    // 4. PROBE POLICY
    // ========================================================

    record ProbePolicy(
        String path,
        int initialDelaySeconds,
        int periodSeconds,
        int failureThreshold
    ) {
        ProbePolicy {
            if (
                path == null ||
                !path.startsWith("/") ||
                initialDelaySeconds < 0 ||
                periodSeconds <= 0 ||
                failureThreshold <= 0
            ) {
                throw new ValidationException(
                    "Invalid probe configuration."
                );
            }
        }
    }

    // ========================================================
    // 5. CONTAINER DOMAIN OBJECT
    // ========================================================

    static final class Container {

        private final String name;
        private final String image;
        private final ResourceRequirements resources;
        private final Map<String, String> environment;

        private ContainerState state = ContainerState.WAITING;
        private boolean ready = false;
        private int restartCount = 0;
        private Integer exitCode;

        private final List<String> logs = new ArrayList<>();

        Container(
            String name,
            String image,
            ResourceRequirements resources,
            Map<String, String> environment
        ) {
            if (
                name == null ||
                !name.matches(
                    "[a-z0-9]([-a-z0-9]*[a-z0-9])?"
                )
            ) {
                throw new ValidationException(
                    "Invalid container name."
                );
            }

            if (
                image == null ||
                image.isBlank() ||
                image.chars().anyMatch(Character::isWhitespace)
            ) {
                throw new ValidationException(
                    "Invalid container image."
                );
            }

            this.name = name;
            this.image = image;
            this.resources = Objects.requireNonNull(resources);

            this.environment = Collections.unmodifiableMap(
                new HashMap<>(environment)
            );
        }

        void start() {
            if (state == ContainerState.RUNNING) {
                throw new LifecycleException(
                    "Container already running: " + name
                );
            }

            state = ContainerState.RUNNING;
            ready = false;
            exitCode = null;

            logs.add("Container started.");
        }

        void markReady() {
            if (state != ContainerState.RUNNING) {
                throw new LifecycleException(
                    "Container is not running."
                );
            }

            ready = true;
            logs.add("Readiness check succeeded.");
        }

        void terminate(int code) {
            if (state != ContainerState.RUNNING) {
                throw new LifecycleException(
                    "Container is not running."
                );
            }

            state = ContainerState.TERMINATED;
            ready = false;
            exitCode = code;

            logs.add("Container terminated: " + code);
        }

        void restart() {
            restartCount++;
            state = ContainerState.WAITING;
            ready = false;
            exitCode = null;

            logs.add("Container restart requested.");
        }

        String getName() {
            return name;
        }

        String getImage() {
            return image;
        }

        ResourceRequirements getResources() {
            return resources;
        }

        ContainerState getState() {
            return state;
        }

        boolean isReady() {
            return ready;
        }

        int getRestartCount() {
            return restartCount;
        }

        Integer getExitCode() {
            return exitCode;
        }

        List<String> getLogs() {
            return List.copyOf(logs);
        }
    }

    // ========================================================
    // 6. NODE AND RESOURCE ACCOUNTING
    // ========================================================

    static final class Node {

        private final String name;
        private final double cpuCapacity;
        private final int memoryCapacity;

        private final Map<String, ResourceRequest> allocations =
            new HashMap<>();

        Node(
            String name,
            double cpuCapacity,
            int memoryCapacity
        ) {
            if (
                name == null ||
                name.isBlank() ||
                !Double.isFinite(cpuCapacity) ||
                cpuCapacity <= 0 ||
                memoryCapacity <= 0
            ) {
                throw new ValidationException(
                    "Invalid worker node configuration."
                );
            }

            this.name = name;
            this.cpuCapacity = cpuCapacity;
            this.memoryCapacity = memoryCapacity;
        }

        ResourceRequest allocated() {
            double cpu = 0;
            int memory = 0;

            for (ResourceRequest request : allocations.values()) {
                cpu += request.cpu();
                memory += request.memory();
            }

            return new ResourceRequest(cpu, memory);
        }

        boolean canFit(ResourceRequest request) {
            ResourceRequest current = allocated();

            return (
                current.cpu() + request.cpu()
                    <= cpuCapacity + 1e-9 &&
                current.memory() + request.memory()
                    <= memoryCapacity
            );
        }

        boolean reserve(
            String podId,
            ResourceRequest request
        ) {
            if (allocations.containsKey(podId)) {
                throw new SchedulingException(
                    "Pod already allocated."
                );
            }

            if (!canFit(request)) {
                return false;
            }

            allocations.put(podId, request);
            return true;
        }

        void release(String podId) {
            allocations.remove(podId);
        }

        String getName() {
            return name;
        }

        double getCpuCapacity() {
            return cpuCapacity;
        }

        int getMemoryCapacity() {
            return memoryCapacity;
        }
    }

    // ========================================================
    // 7. POD DOMAIN OBJECT
    // ========================================================

    static final class Pod {

        private final String id;
        private final String name;
        private final String namespace;

        private final List<Container> containers;
        private final List<Container> initContainers;

        private final RestartPolicy restartPolicy;
        private final Map<String, String> labels;

        private final EnumMap<ConditionType, Boolean> conditions =
            new EnumMap<>(ConditionType.class);

        private final List<String> events = new ArrayList<>();

        private PodPhase phase = PodPhase.PENDING;
        private Node node;

        Pod(
            String id,
            String name,
            String namespace,
            List<Container> containers,
            List<Container> initContainers,
            RestartPolicy restartPolicy,
            Map<String, String> labels
        ) {
            if (
                id == null || id.isBlank() ||
                name == null || name.isBlank() ||
                namespace == null || namespace.isBlank()
            ) {
                throw new ValidationException(
                    "Invalid Pod identity."
                );
            }

            if (containers == null || containers.isEmpty()) {
                throw new ValidationException(
                    "A Pod requires an application container."
                );
            }

            this.id = id;
            this.name = name;
            this.namespace = namespace;
            this.containers = new ArrayList<>(containers);
            this.initContainers = new ArrayList<>(initContainers);
            this.restartPolicy = Objects.requireNonNull(
                restartPolicy
            );

            this.labels = Collections.unmodifiableMap(
                new HashMap<>(labels)
            );

            Set<String> names = new HashSet<>();

            for (
                Container container :
                combinedContainers()
            ) {
                if (!names.add(container.getName())) {
                    throw new ValidationException(
                        "Duplicate container name."
                    );
                }
            }

            for (ConditionType condition : ConditionType.values()) {
                conditions.put(condition, false);
            }

            conditions.put(
                ConditionType.INITIALIZED,
                initContainers.isEmpty()
            );

            record("Pod created.");
        }

        private List<Container> combinedContainers() {
            List<Container> all = new ArrayList<>();
            all.addAll(containers);
            all.addAll(initContainers);
            return all;
        }

        ResourceRequest schedulingRequest() {
            double applicationCpu = 0;
            int applicationMemory = 0;

            for (Container container : containers) {
                applicationCpu +=
                    container.getResources().cpuRequest();

                applicationMemory +=
                    container.getResources().memoryRequest();
            }

            double initCpu = 0;
            int initMemory = 0;

            // Init containers execute sequentially, so their
            // resource requirement is the maximum, not the sum.
            for (Container container : initContainers) {
                initCpu = Math.max(
                    initCpu,
                    container.getResources().cpuRequest()
                );

                initMemory = Math.max(
                    initMemory,
                    container.getResources().memoryRequest()
                );
            }

            return new ResourceRequest(
                Math.max(applicationCpu, initCpu),
                Math.max(applicationMemory, initMemory)
            );
        }

        void assignNode(Node assignedNode) {
            if (node != null) {
                throw new LifecycleException(
                    "Pod already scheduled."
                );
            }

            node = Objects.requireNonNull(assignedNode);

            conditions.put(
                ConditionType.POD_SCHEDULED,
                true
            );

            record("Scheduled on " + node.getName());
        }

        void initialize() {
            if (node == null || phase != PodPhase.PENDING) {
                throw new LifecycleException(
                    "Pod cannot be initialized."
                );
            }

            for (Container container : initContainers) {
                container.start();
                container.markReady();
                container.terminate(0);

                record(
                    "Init container completed: " +
                    container.getName()
                );
            }

            conditions.put(
                ConditionType.INITIALIZED,
                true
            );
        }

        void start() {
            if (
                node == null ||
                !conditions.get(ConditionType.INITIALIZED) ||
                phase != PodPhase.PENDING
            ) {
                throw new LifecycleException(
                    "Pod startup prerequisites are incomplete."
                );
            }

            containers.forEach(Container::start);

            phase = PodPhase.RUNNING;
            record("Application containers started.");
        }

        boolean evaluateReadiness() {
            boolean ready =
                phase == PodPhase.RUNNING &&
                containers.stream().allMatch(
                    container ->
                        container.getState() ==
                            ContainerState.RUNNING &&
                        container.isReady()
                );

            conditions.put(
                ConditionType.CONTAINERS_READY,
                ready
            );

            conditions.put(
                ConditionType.READY,
                ready
            );

            return ready;
        }

        void readinessProbe(boolean successful) {
            if (phase != PodPhase.RUNNING) {
                throw new LifecycleException(
                    "Pod is not running."
                );
            }

            for (Container container : containers) {
                if (
                    successful &&
                    container.getState() == ContainerState.RUNNING
                ) {
                    container.markReady();
                }
            }

            if (successful) {
                evaluateReadiness();
            } else {
                conditions.put(
                    ConditionType.CONTAINERS_READY,
                    false
                );

                conditions.put(
                    ConditionType.READY,
                    false
                );
            }

            record(
                successful
                    ? "Readiness probe passed."
                    : "Readiness probe failed."
            );
        }

        void handleContainerFailure(
            String containerName,
            int exitCode
        ) {
            Container container = containers.stream()
                .filter(c -> c.getName().equals(containerName))
                .findFirst()
                .orElseThrow(
                    () -> new ValidationException(
                        "Unknown application container."
                    )
                );

            container.terminate(exitCode);

            boolean shouldRestart =
                restartPolicy == RestartPolicy.ALWAYS ||
                (
                    restartPolicy == RestartPolicy.ON_FAILURE &&
                    exitCode != 0
                );

            if (shouldRestart) {
                container.restart();
                container.start();

                record(
                    "Container restarted: " + containerName
                );
            } else {
                boolean allTerminated = containers.stream()
                    .allMatch(
                        c -> c.getState() ==
                            ContainerState.TERMINATED
                    );

                if (allTerminated) {
                    boolean successful = containers.stream()
                        .allMatch(c -> Objects.equals(c.getExitCode(), 0));

                    phase = successful
                        ? PodPhase.SUCCEEDED
                        : PodPhase.FAILED;
                }
            }

            evaluateReadiness();
        }

        void complete(int exitCode) {
            if (phase != PodPhase.RUNNING) {
                throw new LifecycleException(
                    "Only running Pods can complete."
                );
            }

            for (Container container : containers) {
                if (container.getState() == ContainerState.RUNNING) {
                    container.terminate(exitCode);
                }
            }

            phase = exitCode == 0
                ? PodPhase.SUCCEEDED
                : PodPhase.FAILED;

            conditions.put(ConditionType.READY, false);
            conditions.put(ConditionType.CONTAINERS_READY, false);

            record("Pod completed.");
        }

        private void record(String event) {
            events.add(
                java.time.Instant.now() + " " + event
            );
        }

        String getId() {
            return id;
        }

        String getName() {
            return name;
        }

        PodPhase getPhase() {
            return phase;
        }

        boolean isReady() {
            return conditions.get(ConditionType.READY);
        }

        Node getNode() {
            return node;
        }

        List<Container> getContainers() {
            return Collections.unmodifiableList(containers);
        }

        List<String> getEvents() {
            return List.copyOf(events);
        }

        void print() {
            System.out.println("\nPod: " + name);
            System.out.println("Namespace: " + namespace);
            System.out.println("Phase: " + phase);
            System.out.println(
                "Node: " + (node == null ? "Unscheduled" : node.getName())
            );
            System.out.println("Ready: " + isReady());

            for (Container container : containers) {
                System.out.printf(
                    "  %-12s %-28s %-12s Restarts=%d%n",
                    container.getName(),
                    container.getImage(),
                    container.getState(),
                    container.getRestartCount()
                );
            }
        }
    }

    // ========================================================
    // 8. SCHEDULER SERVICE
    // ========================================================

    static final class Scheduler {

        private final List<Node> nodes;

        Scheduler(List<Node> nodes) {
            if (nodes == null || nodes.isEmpty()) {
                throw new ValidationException(
                    "At least one node is required."
                );
            }

            this.nodes = List.copyOf(nodes);
        }

        String schedule(Pod pod) {
            ResourceRequest request = pod.schedulingRequest();

            List<Node> candidates = nodes.stream()
                .filter(node -> node.canFit(request))
                .sorted(
                    Comparator.comparingDouble(
                        node ->
                            node.getCpuCapacity() -
                            node.allocated().cpu() -
                            request.cpu()
                    )
                )
                .toList();

            for (Node node : candidates) {
                if (node.reserve(pod.getId(), request)) {
                    pod.assignNode(node);
                    return node.getName();
                }
            }

            throw new SchedulingException(
                "No node has sufficient capacity for " +
                pod.getName()
            );
        }

        void release(Pod pod) {
            nodes.forEach(
                node -> node.release(pod.getId())
            );
        }
    }

    // ========================================================
    // 9. DEPLOYMENT SERVICE
    // ========================================================

    static final class Deployment {

        private final String name;
        private final String namespace;

        private String image;
        private int desiredReplicas;
        private int generation = 1;

        private final AtomicInteger sequence =
            new AtomicInteger(1);

        private final Map<String, Pod> pods =
            new LinkedHashMap<>();

        Deployment(
            String name,
            String namespace,
            String image,
            int replicas
        ) {
            if (
                name == null ||
                name.isBlank() ||
                namespace == null ||
                namespace.isBlank() ||
                image == null ||
                image.isBlank() ||
                replicas < 0
            ) {
                throw new ValidationException(
                    "Invalid Deployment specification."
                );
            }

            this.name = name;
            this.namespace = namespace;
            this.image = image;
            this.desiredReplicas = replicas;
        }

        private Pod createPod(String selectedImage) {
            int id = sequence.getAndIncrement();

            return new Pod(
                name + "-" + id,
                name + "-" + id,
                namespace,
                List.of(
                    new Container(
                        "application",
                        selectedImage,
                        ResourceRequirements.defaults(),
                        Map.of()
                    )
                ),
                List.of(),
                RestartPolicy.ALWAYS,
                Map.of("app", name)
            );
        }

        void reconcile() {
            List<Pod> active = pods.values().stream()
                .filter(
                    pod ->
                        pod.getPhase() != PodPhase.FAILED &&
                        pod.getPhase() != PodPhase.SUCCEEDED
                )
                .collect(Collectors.toCollection(ArrayList::new));

            while (active.size() < desiredReplicas) {
                Pod pod = createPod(image);
                pods.put(pod.getId(), pod);
                active.add(pod);
            }

            while (active.size() > desiredReplicas) {
                Pod pod = active.remove(active.size() - 1);
                pods.remove(pod.getId());
            }
        }

        void rollingUpdate(Scheduler scheduler, String newImage) {
            if (newImage == null || newImage.isBlank()) {
                throw new ValidationException(
                    "Replacement image is required."
                );
            }

            int nextGeneration = generation + 1;

            List<Pod> replacements = new ArrayList<>();
            List<Pod> reserved = new ArrayList<>();

            try {
                for (int i = 0; i < desiredReplicas; i++) {
                    Pod replacement = createPod(newImage);

                    scheduler.schedule(replacement);
                    reserved.add(replacement);

                    replacement.initialize();
                    replacement.start();
                    replacement.readinessProbe(true);

                    if (!replacement.isReady()) {
                        throw new LifecycleException(
                            "Replacement failed readiness validation."
                        );
                    }

                    replacements.add(replacement);
                }
            } catch (RuntimeException exception) {
                reserved.forEach(scheduler::release);
                throw new SchedulingException(
                    "Rolling update aborted: " + exception.getMessage()
                );
            }

            // Replace the old workload only after all new replicas
            // have passed readiness validation.
            pods.values().forEach(scheduler::release);

            pods.clear();

            for (Pod pod : replacements) {
                pods.put(pod.getId(), pod);
            }

            image = newImage;
            generation = nextGeneration;
        }

        void scale(int replicas) {
            if (replicas < 0) {
                throw new ValidationException(
                    "Replica count cannot be negative."
                );
            }

            desiredReplicas = replicas;
            generation++;
        }

        List<Pod> getPods() {
            return List.copyOf(pods.values());
        }

        void printStatus() {
            long ready = pods.values().stream()
                .filter(Pod::isReady)
                .count();

            System.out.println("\nDeployment: " + name);
            System.out.println("Image: " + image);
            System.out.println("Desired: " + desiredReplicas);
            System.out.println("Actual: " + pods.size());
            System.out.println("Ready: " + ready);
            System.out.println("Generation: " + generation);
        }
    }

    // ========================================================
    // 10. CLUSTER MONITORING
    // ========================================================

    record ClusterMetrics(
        int total,
        int pending,
        int running,
        int succeeded,
        int failed,
        int ready,
        int restarts
    ) {}

    static ClusterMetrics monitor(List<Pod> pods) {
        int pending = 0;
        int running = 0;
        int succeeded = 0;
        int failed = 0;
        int ready = 0;
        int restarts = 0;

        for (Pod pod : pods) {
            switch (pod.getPhase()) {
                case PENDING -> pending++;
                case RUNNING -> running++;
                case SUCCEEDED -> succeeded++;
                case FAILED -> failed++;
                default -> {
                }
            }

            if (pod.isReady()) {
                ready++;
            }

            restarts += pod.getContainers().stream()
                .mapToInt(Container::getRestartCount)
                .sum();
        }

        return new ClusterMetrics(
            pods.size(),
            pending,
            running,
            succeeded,
            failed,
            ready,
            restarts
        );
    }

    // ========================================================
    // 11. APPLICATION ENTRY POINT
    // ========================================================

    public static void main(String[] args) {

        try {
            System.out.println(
                "\nKUBERNETES ENTERPRISE POD MANAGEMENT"
            );

            System.out.println(
                "====================================="
            );

            Node worker1 = new Node(
                "worker-01",
                8,
                16384
            );

            Node worker2 = new Node(
                "worker-02",
                4,
                8192
            );

            Scheduler scheduler = new Scheduler(
                List.of(worker1, worker2)
            );

            ResourceRequirements apiResources =
                new ResourceRequirements(
                    0.5,
                    1.0,
                    256,
                    512
                );

            Pod apiPod = new Pod(
                "api-001",
                "api-pod",
                "production",
                List.of(
                    new Container(
                        "api",
                        "python:3.13-slim",
                        apiResources,
                        Map.of("APP_ENV", "production")
                    ),
                    new Container(
                        "metrics",
                        "busybox:1.36",
                        ResourceRequirements.defaults(),
                        Map.of()
                    )
                ),
                List.of(
                    new Container(
                        "database-init",
                        "busybox:1.36",
                        ResourceRequirements.defaults(),
                        Map.of()
                    )
                ),
                RestartPolicy.ALWAYS,
                Map.of("app", "api")
            );

            System.out.println("\n1. Pod scheduling");

            System.out.println(
                "Assigned node: " + scheduler.schedule(apiPod)
            );

            System.out.println("\n2. Initialization");
            apiPod.initialize();

            System.out.println("\n3. Application startup");
            apiPod.start();

            System.out.println("\n4. Readiness validation");
            apiPod.readinessProbe(true);

            if (!apiPod.isReady()) {
                throw new LifecycleException(
                    "Pod did not become ready."
                );
            }

            apiPod.print();

            System.out.println("\n5. Container failure");

            apiPod.handleContainerFailure("api", 1);

            System.out.println(
                "Restart count: " +
                apiPod.getContainers().get(0).getRestartCount()
            );

            System.out.println("\n6. Deployment creation");

            Deployment deployment = new Deployment(
                "frontend",
                "production",
                "nginx:1.27",
                3
            );

            deployment.reconcile();
            deployment.printStatus();

            System.out.println("\n7. Scheduling deployment replicas");

            for (Pod pod : deployment.getPods()) {
                scheduler.schedule(pod);
                pod.initialize();
                pod.start();
                pod.readinessProbe(true);
            }

            deployment.printStatus();

            System.out.println("\n8. Rolling update");

            deployment.rollingUpdate(
                scheduler,
                "nginx:1.28"
            );

            deployment.printStatus();

            System.out.println("\n9. Cluster monitoring");

            List<Pod> allPods = new ArrayList<>();
            allPods.add(apiPod);
            allPods.addAll(deployment.getPods());

            System.out.println(monitor(allPods));

            System.out.println("\n10. Edge-case validation");

            boolean rejected = false;

            try {
                new ResourceRequirements(
                    2.0,
                    1.0,
                    256,
                    512
                );
            } catch (ValidationException exception) {
                rejected = true;
                System.out.println(
                    "Invalid resource specification rejected."
                );
            }

            if (!rejected) {
                throw new AssertionError(
                    "Invalid resource specification was accepted."
                );
            }

            rejected = false;

            try {
                deployment.scale(-1);
            } catch (ValidationException exception) {
                rejected = true;
            }

            if (!rejected) {
                throw new AssertionError(
                    "Negative replica count was accepted."
                );
            }

            System.out.println("All validation checks passed.");

        } catch (PodManagementException exception) {
            System.err.println(
                "Pod management failure: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
