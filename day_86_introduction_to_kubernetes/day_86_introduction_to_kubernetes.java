import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

/**
 * Kubernetes Enterprise Cluster Management Model
 *
 * Java 17 implementation covering:
 * - Kubernetes architecture
 * - Cluster management
 * - Control-plane and worker nodes
 * - Pod and container lifecycle
 * - Resource-aware scheduling
 * - Deployment reconciliation
 * - Service discovery
 * - Health checks
 * - Rolling updates
 * - Failure recovery
 * - Enterprise audit events
 *
 * Dependencies: Java 17 standard library.
 *
 * Run:
 * javac KubernetesEnterprise.java
 * java KubernetesEnterprise
 */
public class KubernetesEnterprise {

    // ========================================================
    // EXCEPTIONS
    // ========================================================

    static class KubernetesException extends RuntimeException {
        KubernetesException(String message) {
            super(message);
        }
    }

    static class ValidationException extends KubernetesException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class SchedulingException extends KubernetesException {
        SchedulingException(String message) {
            super(message);
        }
    }

    static class ResourceNotFoundException extends KubernetesException {
        ResourceNotFoundException(String message) {
            super(message);
        }
    }

    // ========================================================
    // ENUMERATIONS
    // ========================================================

    enum NodeRole {
        CONTROL_PLANE,
        WORKER
    }

    enum NodeStatus {
        READY,
        NOT_READY
    }

    enum PodStatus {
        PENDING,
        RUNNING,
        FAILED,
        TERMINATING
    }

    enum DeploymentStatus {
        ACTIVE,
        DEGRADED,
        SCALING
    }

    enum ServiceType {
        CLUSTER_IP,
        NODE_PORT,
        LOAD_BALANCER
    }

    enum EventType {
        NODE_ADDED,
        NODE_FAILED,
        NODE_RECOVERED,
        POD_CREATED,
        POD_SCHEDULED,
        POD_FAILED,
        DEPLOYMENT_RECONCILED,
        DEPLOYMENT_SCALED,
        ROLLING_UPDATE,
        SERVICE_CREATED
    }

    // ========================================================
    // IMMUTABLE RESOURCE OBJECT
    // ========================================================

    record ResourceRequirements(
        int cpuMillicores,
        int memoryMB
    ) {

        ResourceRequirements {
            if (cpuMillicores <= 0 || memoryMB <= 0) {
                throw new ValidationException(
                    "Resource requests must be positive."
                );
            }
        }

        ResourceRequirements add(ResourceRequirements other) {
            return new ResourceRequirements(
                Math.addExact(
                    cpuMillicores,
                    other.cpuMillicores
                ),
                Math.addExact(
                    memoryMB,
                    other.memoryMB
                )
            );
        }
    }

    // ========================================================
    // CONTAINER
    // ========================================================

    static final class Container {

        private final String name;
        private final String image;
        private final ResourceRequirements resources;

        private boolean ready = true;
        private int restartCount = 0;

        Container(
            String name,
            String image,
            ResourceRequirements resources
        ) {

            if (
                name == null || name.isBlank() ||
                image == null || image.isBlank()
            ) {
                throw new ValidationException(
                    "Container name and image are required."
                );
            }

            this.name = name;
            this.image = image;
            this.resources = Objects.requireNonNull(resources);
        }

        String name() {
            return name;
        }

        String image() {
            return image;
        }

        ResourceRequirements resources() {
            return resources;
        }

        boolean isReady() {
            return ready;
        }

        void setReady(boolean ready) {
            this.ready = ready;
        }

        int restartCount() {
            return restartCount;
        }

        void restart() {
            restartCount++;
            ready = true;
        }
    }

    // ========================================================
    // POD
    // ========================================================

    static final class Pod {

        private final UUID id;
        private final String name;
        private final String namespace;

        private final List<Container> containers;
        private final Map<String, String> labels;

        private PodStatus status = PodStatus.PENDING;
        private String nodeName;

        Pod(
            String name,
            String namespace,
            List<Container> containers,
            Map<String, String> labels
        ) {

            if (name == null || name.isBlank()) {
                throw new ValidationException(
                    "Pod name is required."
                );
            }

            if (namespace == null || namespace.isBlank()) {
                throw new ValidationException(
                    "Namespace is required."
                );
            }

            if (containers == null || containers.isEmpty()) {
                throw new ValidationException(
                    "Pod must contain at least one container."
                );
            }

            if (labels == null || labels.isEmpty()) {
                throw new ValidationException(
                    "Pod labels are required."
                );
            }

            this.id = UUID.randomUUID();
            this.name = name;
            this.namespace = namespace;
            this.containers = new ArrayList<>(containers);
            this.labels = Map.copyOf(labels);
        }

        ResourceRequirements requirements() {

            int cpu = 0;
            int memory = 0;

            for (Container container : containers) {
                cpu = Math.addExact(
                    cpu,
                    container.resources().cpuMillicores()
                );

                memory = Math.addExact(
                    memory,
                    container.resources().memoryMB()
                );
            }

            return new ResourceRequirements(cpu, memory);
        }

        boolean isReady() {

            return status == PodStatus.RUNNING
                && containers.stream().allMatch(Container::isReady);
        }

        boolean matches(Map<String, String> selector) {

            return selector.entrySet().stream().allMatch(
                entry -> Objects.equals(
                    labels.get(entry.getKey()),
                    entry.getValue()
                )
            );
        }

        UUID id() {
            return id;
        }

        String name() {
            return name;
        }

        String namespace() {
            return namespace;
        }

        String nodeName() {
            return nodeName;
        }

        PodStatus status() {
            return status;
        }

        void setStatus(PodStatus status) {
            this.status = status;
        }

        void setNodeName(String nodeName) {
            this.nodeName = nodeName;
        }

        String image() {
            return containers.getFirst().image();
        }

        List<Container> containers() {
            return Collections.unmodifiableList(containers);
        }
    }

    // ========================================================
    // NODE
    // ========================================================

    static final class Node {

        private final String name;
        private final NodeRole role;
        private final ResourceRequirements capacity;

        private final Set<UUID> podIds =
            new java.util.HashSet<>();

        private NodeStatus status = NodeStatus.READY;

        private int allocatedCPU;
        private int allocatedMemory;

        Node(
            String name,
            NodeRole role,
            ResourceRequirements capacity
        ) {

            if (name == null || name.isBlank()) {
                throw new ValidationException(
                    "Node name is required."
                );
            }

            this.name = name;
            this.role = Objects.requireNonNull(role);
            this.capacity = Objects.requireNonNull(capacity);
        }

        boolean canSchedule(ResourceRequirements requested) {

            return role == NodeRole.WORKER
                && status == NodeStatus.READY
                && allocatedCPU + requested.cpuMillicores()
                    <= capacity.cpuMillicores()
                && allocatedMemory + requested.memoryMB()
                    <= capacity.memoryMB();
        }

        void allocate(Pod pod) {

            ResourceRequirements resources = pod.requirements();

            if (!canSchedule(resources)) {
                throw new SchedulingException(
                    "Insufficient capacity on " + name
                );
            }

            if (podIds.contains(pod.id())) {
                throw new ValidationException(
                    "Pod already allocated."
                );
            }

            allocatedCPU += resources.cpuMillicores();
            allocatedMemory += resources.memoryMB();

            podIds.add(pod.id());
        }

        void release(Pod pod) {

            if (!podIds.remove(pod.id())) {
                return;
            }

            ResourceRequirements resources = pod.requirements();

            allocatedCPU -= resources.cpuMillicores();
            allocatedMemory -= resources.memoryMB();

            if (allocatedCPU < 0 || allocatedMemory < 0) {
                throw new KubernetesException(
                    "Resource accounting invariant violated."
                );
            }
        }

        void fail() {
            status = NodeStatus.NOT_READY;
        }

        void recover() {
            status = NodeStatus.READY;
        }

        String name() {
            return name;
        }

        NodeRole role() {
            return role;
        }

        NodeStatus status() {
            return status;
        }

        ResourceRequirements capacity() {
            return capacity;
        }

        int allocatedCPU() {
            return allocatedCPU;
        }

        int allocatedMemory() {
            return allocatedMemory;
        }

        int podCount() {
            return podIds.size();
        }

        Set<UUID> podIds() {
            return Set.copyOf(podIds);
        }
    }

    // ========================================================
    // DEPLOYMENT
    // ========================================================

    static final class Deployment {

        private final String name;
        private final Map<String, String> labels;
        private final ResourceRequirements resources;

        private String image;
        private int desiredReplicas;
        private int generation = 1;

        private final List<UUID> podIds = new ArrayList<>();

        Deployment(
            String name,
            String image,
            int replicas,
            Map<String, String> labels,
            ResourceRequirements resources
        ) {

            if (
                name == null || name.isBlank() ||
                image == null || image.isBlank()
            ) {
                throw new ValidationException(
                    "Deployment name and image are required."
                );
            }

            if (replicas < 0) {
                throw new ValidationException(
                    "Replicas cannot be negative."
                );
            }

            if (labels == null || labels.isEmpty()) {
                throw new ValidationException(
                    "Deployment labels are required."
                );
            }

            this.name = name;
            this.image = image;
            this.desiredReplicas = replicas;
            this.labels = Map.copyOf(labels);
            this.resources = Objects.requireNonNull(resources);
        }

        String name() {
            return name;
        }

        String image() {
            return image;
        }

        int desiredReplicas() {
            return desiredReplicas;
        }

        int generation() {
            return generation;
        }

        List<UUID> podIds() {
            return List.copyOf(podIds);
        }
    }

    // ========================================================
    // SERVICE
    // ========================================================

    record Service(
        String name,
        ServiceType type,
        Map<String, String> selector,
        int port,
        int targetPort,
        String clusterIP
    ) {

        Service {

            if (name == null || name.isBlank()) {
                throw new ValidationException(
                    "Service name is required."
                );
            }

            if (selector == null || selector.isEmpty()) {
                throw new ValidationException(
                    "Service selector is required."
                );
            }

            if (
                port < 1 || port > 65535 ||
                targetPort < 1 || targetPort > 65535
            ) {
                throw new ValidationException(
                    "Invalid Service port."
                );
            }

            Objects.requireNonNull(type);
            selector = Map.copyOf(selector);
        }
    }

    // ========================================================
    // AUDIT EVENTS
    // ========================================================

    record ClusterEvent(
        long sequence,
        Instant timestamp,
        EventType type,
        String resource,
        String description
    ) {}

    // ========================================================
    // SCHEDULER INTERFACE
    // ========================================================

    interface SchedulingPolicy {

        Optional<Node> selectNode(
            Pod pod,
            List<Node> nodes
        );
    }

    static final class BestFitPolicy
        implements SchedulingPolicy {

        @Override
        public Optional<Node> selectNode(
            Pod pod,
            List<Node> nodes
        ) {

            return nodes.stream()
                .filter(node -> node.canSchedule(pod.requirements()))
                .min(
                    Comparator.comparingInt(
                        node -> node.capacity().cpuMillicores()
                            - node.allocatedCPU()
                            - pod.requirements().cpuMillicores()
                    )
                );
        }
    }

    // ========================================================
    // CLUSTER SERVICE
    // ========================================================

    static final class ClusterService {

        private final String clusterName;

        private final Map<String, Node> nodes =
            new LinkedHashMap<>();

        private final Map<UUID, Pod> pods =
            new LinkedHashMap<>();

        private final Map<String, Deployment> deployments =
            new LinkedHashMap<>();

        private final Map<String, Service> services =
            new LinkedHashMap<>();

        private final List<ClusterEvent> auditLog =
            new ArrayList<>();

        private final SchedulingPolicy schedulingPolicy;

        private final AtomicLong eventSequence =
            new AtomicLong();

        private int serviceIPSequence = 10;

        ClusterService(
            String clusterName,
            SchedulingPolicy schedulingPolicy
        ) {

            if (clusterName == null || clusterName.isBlank()) {
                throw new ValidationException(
                    "Cluster name is required."
                );
            }

            this.clusterName = clusterName;
            this.schedulingPolicy =
                Objects.requireNonNull(schedulingPolicy);
        }

        private void record(
            EventType type,
            String resource,
            String description
        ) {

            auditLog.add(
                new ClusterEvent(
                    eventSequence.incrementAndGet(),
                    Instant.now(),
                    type,
                    resource,
                    description
                )
            );
        }

        void addNode(Node node) {

            if (nodes.containsKey(node.name())) {
                throw new ValidationException(
                    "Duplicate node: " + node.name()
                );
            }

            nodes.put(node.name(), node);

            record(
                EventType.NODE_ADDED,
                node.name(),
                "Registered " + node.role()
            );
        }

        private Node schedule(Pod pod) {

            Node node = schedulingPolicy.selectNode(
                pod,
                new ArrayList<>(nodes.values())
            ).orElseThrow(
                () -> new SchedulingException(
                    "No suitable node for " + pod.name()
                )
            );

            node.allocate(pod);

            pod.setNodeName(node.name());
            pod.setStatus(PodStatus.RUNNING);

            record(
                EventType.POD_SCHEDULED,
                pod.name(),
                "Scheduled on " + node.name()
            );

            return node;
        }

        private void createPod(Pod pod) {

            pods.put(pod.id(), pod);

            record(
                EventType.POD_CREATED,
                pod.name(),
                "Pod registered in cluster state"
            );

            try {
                schedule(pod);
            } catch (SchedulingException error) {
                pod.setStatus(PodStatus.PENDING);
            }
        }

        private void deletePod(UUID id) {

            Pod pod = pods.get(id);

            if (pod == null) {
                throw new ResourceNotFoundException(
                    "Pod not found: " + id
                );
            }

            pod.setStatus(PodStatus.TERMINATING);

            if (pod.nodeName() != null) {
                Node node = nodes.get(pod.nodeName());

                if (node != null) {
                    node.release(pod);
                }
            }

            pods.remove(id);
        }

        private List<Pod> activePods(Deployment deployment) {

            return deployment.podIds.stream()
                .map(pods::get)
                .filter(Objects::nonNull)
                .filter(pod ->
                    pod.status() == PodStatus.RUNNING ||
                    pod.status() == PodStatus.PENDING
                )
                .collect(Collectors.toCollection(ArrayList::new));
        }

        private void reconcile(Deployment deployment) {

            List<Pod> current = activePods(deployment);

            while (current.size() < deployment.desiredReplicas) {

                int number = deployment.podIds.size() + 1;

                Pod pod = new Pod(
                    deployment.name + "-" + number,
                    "default",
                    List.of(
                        new Container(
                            "application",
                            deployment.image,
                            deployment.resources
                        )
                    ),
                    deployment.labels
                );

                createPod(pod);

                deployment.podIds.add(pod.id());
                current.add(pod);
            }

            while (current.size() > deployment.desiredReplicas) {

                Pod pod = current.remove(current.size() - 1);

                deletePod(pod.id());
                deployment.podIds.remove(pod.id());
            }

            record(
                EventType.DEPLOYMENT_RECONCILED,
                deployment.name,
                "Desired replicas: "
                    + deployment.desiredReplicas
                    + ", observed: " + current.size()
            );
        }

        void createDeployment(Deployment deployment) {

            if (deployments.containsKey(deployment.name)) {
                throw new ValidationException(
                    "Deployment already exists."
                );
            }

            deployments.put(deployment.name, deployment);

            reconcile(deployment);
        }

        void scale(String name, int replicas) {

            if (replicas < 0) {
                throw new ValidationException(
                    "Invalid replica count."
                );
            }

            Deployment deployment = deployments.get(name);

            if (deployment == null) {
                throw new ResourceNotFoundException(name);
            }

            deployment.desiredReplicas = replicas;
            deployment.generation++;

            reconcile(deployment);

            record(
                EventType.DEPLOYMENT_SCALED,
                name,
                "Replica count changed to " + replicas
            );
        }

        void addService(
            String name,
            ServiceType type,
            Map<String, String> selector,
            int port,
            int targetPort
        ) {

            if (services.containsKey(name)) {
                throw new ValidationException(
                    "Service already exists."
                );
            }

            String clusterIP =
                "10.96.0." + serviceIPSequence++;

            Service service = new Service(
                name,
                type,
                selector,
                port,
                targetPort,
                clusterIP
            );

            services.put(name, service);

            record(
                EventType.SERVICE_CREATED,
                name,
                "ClusterIP assigned: " + clusterIP
            );
        }

        List<String> endpoints(String serviceName) {

            Service service = services.get(serviceName);

            if (service == null) {
                throw new ResourceNotFoundException(
                    serviceName
                );
            }

            return pods.values().stream()
                .filter(Pod::isReady)
                .filter(pod -> pod.matches(service.selector()))
                .map(Pod::name)
                .sorted()
                .toList();
        }

        void failNode(String name) {

            Node node = nodes.get(name);

            if (node == null) {
                throw new ResourceNotFoundException(name);
            }

            node.fail();

            for (UUID id : node.podIds()) {

                Pod pod = pods.get(id);

                if (pod == null) {
                    continue;
                }

                node.release(pod);

                pod.setNodeName(null);
                pod.setStatus(PodStatus.FAILED);

                record(
                    EventType.POD_FAILED,
                    pod.name(),
                    "Node failure"
                );
            }

            for (Deployment deployment : deployments.values()) {
                reconcile(deployment);
            }

            record(
                EventType.NODE_FAILED,
                name,
                "Node marked NotReady"
            );
        }

        void recoverNode(String name) {

            Node node = nodes.get(name);

            if (node == null) {
                throw new ResourceNotFoundException(name);
            }

            node.recover();

            for (Pod pod : pods.values()) {

                if (pod.status() != PodStatus.PENDING) {
                    continue;
                }

                try {
                    schedule(pod);
                } catch (SchedulingException ignored) {
                    // Remain Pending until capacity becomes available.
                }
            }

            record(
                EventType.NODE_RECOVERED,
                name,
                "Node marked Ready"
            );
        }

        void rollingUpdate(
            String name,
            String newImage
        ) {

            if (newImage == null || newImage.isBlank()) {
                throw new ValidationException(
                    "Updated image is required."
                );
            }

            Deployment deployment = deployments.get(name);

            if (deployment == null) {
                throw new ResourceNotFoundException(name);
            }

            String oldImage = deployment.image;
            int oldGeneration = deployment.generation;

            List<UUID> oldIds =
                new ArrayList<>(deployment.podIds);

            List<UUID> replacements = new ArrayList<>();

            deployment.image = newImage;
            deployment.generation++;

            try {

                for (int i = 0; i < deployment.desiredReplicas; i++) {

                    Pod pod = new Pod(
                        name + "-rollout-" + deployment.generation
                            + "-" + (i + 1),
                        "default",
                        List.of(
                            new Container(
                                "application",
                                newImage,
                                deployment.resources
                            )
                        ),
                        deployment.labels
                    );

                    createPod(pod);

                    if (pod.status() != PodStatus.RUNNING) {
                        throw new SchedulingException(
                            "New replica could not become ready."
                        );
                    }

                    replacements.add(pod.id());
                }

                // Existing Pods are retained if replacement scheduling fails.
                for (UUID id : oldIds) {
                    deletePod(id);
                }

                deployment.podIds.clear();
                deployment.podIds.addAll(replacements);

                record(
                    EventType.ROLLING_UPDATE,
                    name,
                    "Updated image to " + newImage
                );

            } catch (RuntimeException error) {

                for (UUID id : replacements) {
                    if (pods.containsKey(id)) {
                        deletePod(id);
                    }
                }

                deployment.image = oldImage;
                deployment.generation = oldGeneration;

                deployment.podIds.clear();
                deployment.podIds.addAll(oldIds);

                throw error;
            }
        }

        DeploymentStatus status(Deployment deployment) {

            List<Pod> current = activePods(deployment);

            long ready = current.stream()
                .filter(Pod::isReady)
                .count();

            if (ready == deployment.desiredReplicas) {
                return DeploymentStatus.ACTIVE;
            }

            if (ready == 0) {
                return DeploymentStatus.DEGRADED;
            }

            return DeploymentStatus.SCALING;
        }

        void printReport() {

            System.out.println(
                "\nCLUSTER: " + clusterName
            );

            System.out.println("\nNODE INVENTORY");

            nodes.values().forEach(node ->
                System.out.printf(
                    "%-15s %-15s %-10s CPU %d/%d MEMORY %d/%d MB PODS %d%n",
                    node.name(),
                    node.role(),
                    node.status(),
                    node.allocatedCPU(),
                    node.capacity().cpuMillicores(),
                    node.allocatedMemory(),
                    node.capacity().memoryMB(),
                    node.podCount()
                )
            );

            System.out.println("\nPOD STATUS");

            Map<PodStatus, Long> podCounts =
                pods.values().stream().collect(
                    Collectors.groupingBy(
                        Pod::status,
                        () -> new TreeMap<>(
                            Comparator.comparing(Enum::name)
                        ),
                        Collectors.counting()
                    )
                );

            podCounts.forEach(
                (status, count) ->
                    System.out.println(status + ": " + count)
            );

            System.out.println("\nDEPLOYMENTS");

            deployments.values().forEach(deployment ->
                System.out.printf(
                    "%s | Desired: %d | Observed: %d | Status: %s | Image: %s%n",
                    deployment.name,
                    deployment.desiredReplicas,
                    activePods(deployment).size(),
                    status(deployment),
                    deployment.image
                )
            );

            System.out.println("\nSERVICES");

            services.forEach((name, service) ->
                System.out.printf(
                    "%s | %s | Port: %d | Endpoints: %d%n",
                    name,
                    service.clusterIP(),
                    service.port(),
                    endpoints(name).size()
                )
            );

            System.out.println(
                "\nAUDIT EVENTS: " + auditLog.size()
            );
        }

        void validateInvariants() {

            for (Node node : nodes.values()) {

                if (
                    node.allocatedCPU() < 0 ||
                    node.allocatedMemory() < 0 ||
                    node.allocatedCPU()
                        > node.capacity().cpuMillicores() ||
                    node.allocatedMemory()
                        > node.capacity().memoryMB()
                ) {
                    throw new KubernetesException(
                        "Resource invariant violated on "
                            + node.name()
                    );
                }
            }

            for (Pod pod : pods.values()) {

                if (
                    pod.status() == PodStatus.RUNNING &&
                    pod.nodeName() == null
                ) {
                    throw new KubernetesException(
                        "Running Pod lacks node assignment."
                    );
                }
            }
        }

        List<ClusterEvent> auditLog() {
            return List.copyOf(auditLog);
        }
    }

    // ========================================================
    // APPLICATION ENTRY POINT
    // ========================================================

    public static void main(String[] args) {

        try {

            ClusterService cluster = new ClusterService(
                "enterprise-production",
                new BestFitPolicy()
            );

            cluster.addNode(
                new Node(
                    "master-01",
                    NodeRole.CONTROL_PLANE,
                    new ResourceRequirements(8000, 16384)
                )
            );

            cluster.addNode(
                new Node(
                    "worker-01",
                    NodeRole.WORKER,
                    new ResourceRequirements(4000, 8192)
                )
            );

            cluster.addNode(
                new Node(
                    "worker-02",
                    NodeRole.WORKER,
                    new ResourceRequirements(4000, 8192)
                )
            );

            cluster.addNode(
                new Node(
                    "worker-03",
                    NodeRole.WORKER,
                    new ResourceRequirements(2000, 4096)
                )
            );

            Deployment deployment = new Deployment(
                "customer-api",
                "customer-api:1.0.0",
                3,
                Map.of(
                    "app", "customer",
                    "environment", "production"
                ),
                new ResourceRequirements(500, 512)
            );

            cluster.createDeployment(deployment);

            cluster.addService(
                "customer-service",
                ServiceType.CLUSTER_IP,
                Map.of("app", "customer"),
                80,
                8080
            );

            System.out.println("\nINITIAL STATE");

            cluster.printReport();

            System.out.println("\nSERVICE DISCOVERY");

            cluster.endpoints("customer-service")
                .forEach(System.out::println);

            System.out.println("\nSCALING TO FIVE REPLICAS");

            cluster.scale("customer-api", 5);

            cluster.printReport();

            System.out.println("\nROLLING UPDATE");

            cluster.rollingUpdate(
                "customer-api",
                "customer-api:2.0.0"
            );

            cluster.printReport();

            System.out.println("\nSIMULATING NODE FAILURE");

            cluster.failNode("worker-01");

            cluster.validateInvariants();
            cluster.printReport();

            System.out.println("\nRECOVERING NODE");

            cluster.recoverNode("worker-01");

            cluster.validateInvariants();
            cluster.printReport();

            System.out.println(
                "\nAll enterprise cluster invariants passed."
            );

        } catch (KubernetesException error) {

            System.err.println(
                "Cluster operation failed: " + error.getMessage()
            );

            System.exitCode = 1;
        }
    }
}
