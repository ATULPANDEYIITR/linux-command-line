import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Predicate;

public class DeploymentGovernance {

    enum PodPhase {
        PENDING,
        RUNNING,
        TERMINATING,
        TERMINATED,
        FAILED
    }

    enum ReplicaSetPhase {
        ACTIVE,
        INACTIVE
    }

    enum DeploymentPhase {
        PROGRESSING,
        AVAILABLE,
        DEGRADED
    }

    enum Operation {
        CREATE,
        TERMINATE,
        WAIT,
        COMPLETED
    }

    static class DeploymentException extends RuntimeException {
        DeploymentException(String message) {
            super(message);
        }
    }

    record ContainerDefinition(
        String name,
        String image,
        int port,
        String cpuRequest,
        String memoryRequest
    ) {
        ContainerDefinition {
            Objects.requireNonNull(name);
            Objects.requireNonNull(image);
            Objects.requireNonNull(cpuRequest);
            Objects.requireNonNull(memoryRequest);

            if (name.isBlank() || image.isBlank()) {
                throw new IllegalArgumentException(
                    "Container name and image are required"
                );
            }

            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException("Invalid port");
            }
        }
    }

    record DeploymentPolicy(
        int replicas,
        int maxSurge,
        int maxUnavailable,
        int minReadySeconds,
        int revisionHistoryLimit
    ) {
        DeploymentPolicy {
            if (
                replicas < 0 ||
                maxSurge < 0 ||
                maxUnavailable < 0 ||
                minReadySeconds < 0 ||
                revisionHistoryLimit < 0
            ) {
                throw new IllegalArgumentException(
                    "Invalid deployment policy values"
                );
            }

            if (maxSurge == 0 && maxUnavailable == 0) {
                throw new IllegalArgumentException(
                    "Invalid rolling update policy"
                );
            }
        }
    }

    record Revision(
        int number,
        String image,
        String replicaSetId
    ) {}

    static final class Pod {
        private final String id = UUID.randomUUID().toString();
        private final String image;
        private final String replicaSetId;

        private PodPhase phase = PodPhase.PENDING;
        private boolean ready;
        private long readySince;

        Pod(String image, String replicaSetId) {
            this.image = Objects.requireNonNull(image);
            this.replicaSetId = Objects.requireNonNull(replicaSetId);
        }

        void start() {
            if (phase != PodPhase.PENDING) {
                throw new DeploymentException(
                    "Only pending pods can start"
                );
            }

            phase = PodPhase.RUNNING;
        }

        void markReady() {
            if (phase != PodPhase.RUNNING) {
                throw new DeploymentException(
                    "Pod must be running before readiness"
                );
            }

            ready = true;
            readySince = System.currentTimeMillis();
        }

        void markUnready() {
            ready = false;
            readySince = 0;
        }

        void terminate() {
            if (
                phase == PodPhase.TERMINATED ||
                phase == PodPhase.FAILED
            ) {
                return;
            }

            ready = false;
            phase = PodPhase.TERMINATING;
            phase = PodPhase.TERMINATED;
        }

        boolean isActive() {
            return phase != PodPhase.TERMINATED
                && phase != PodPhase.FAILED;
        }

        boolean isReady() {
            return ready && phase == PodPhase.RUNNING;
        }

        boolean isAvailable(int minimumSeconds) {
            return isReady()
                && System.currentTimeMillis() - readySince
                >= minimumSeconds * 1000L;
        }

        String getId() {
            return id;
        }

        String getImage() {
            return image;
        }

        String getReplicaSetId() {
            return replicaSetId;
        }

        PodPhase getPhase() {
            return phase;
        }
    }

    static final class ReplicaSet {
        private final String id = UUID.randomUUID().toString();
        private final String name;
        private final String image;
        private final int revision;

        private int desiredReplicas;
        private ReplicaSetPhase phase = ReplicaSetPhase.ACTIVE;

        private final Map<String, Pod> pods = new HashMap<>();

        ReplicaSet(
            String deploymentName,
            String image,
            int revision
        ) {
            this.name = deploymentName + "-" + id.substring(0, 8);
            this.image = image;
            this.revision = revision;
        }

        void addPod(Pod pod) {
            if (pods.putIfAbsent(pod.getId(), pod) != null) {
                throw new DeploymentException("Duplicate pod identifier");
            }
        }

        List<Pod> activePods() {
            return pods.values().stream()
                .filter(Pod::isActive)
                .toList();
        }

        long readyReplicas() {
            return activePods().stream()
                .filter(Pod::isReady)
                .count();
        }

        int activeReplicas() {
            return activePods().size();
        }

        void setDesiredReplicas(int desired) {
            if (desired < 0) {
                throw new IllegalArgumentException(
                    "Invalid replica count"
                );
            }

            desiredReplicas = desired;
        }

        void deactivate() {
            phase = ReplicaSetPhase.INACTIVE;
        }

        boolean isActive() {
            return phase == ReplicaSetPhase.ACTIVE;
        }

        String getId() {
            return id;
        }

        String getName() {
            return name;
        }

        String getImage() {
            return image;
        }

        int getRevision() {
            return revision;
        }

        int getDesiredReplicas() {
            return desiredReplicas;
        }

        List<Pod> getPods() {
            return List.copyOf(pods.values());
        }
    }

    record DeploymentStatus(
        int desiredReplicas,
        int updatedReplicas,
        int readyReplicas,
        int availableReplicas,
        int unavailableReplicas,
        DeploymentPhase phase
    ) {}

    static final class DeploymentService {

        private final String name;
        private final String namespace;
        private final ContainerDefinition container;

        private DeploymentPolicy policy;

        private String currentImage;

        private int revision = 1;
        private int generation = 1;
        private int createdResources = 0;

        private final Map<String, ReplicaSet> replicaSets =
            new HashMap<>();

        private final Map<Integer, Revision> history =
            new HashMap<>();

        private DeploymentStatus status;

        DeploymentService(
            String name,
            String namespace,
            ContainerDefinition container,
            DeploymentPolicy policy
        ) {
            this.name = Objects.requireNonNull(name);
            this.namespace = Objects.requireNonNull(namespace);
            this.container = Objects.requireNonNull(container);
            this.policy = Objects.requireNonNull(policy);

            if (name.isBlank() || namespace.isBlank()) {
                throw new IllegalArgumentException(
                    "Deployment identity is required"
                );
            }

            this.currentImage = container.image();

            createReplicaSet(currentImage);
            reconcile();
        }

        private ReplicaSet createReplicaSet(String image) {
            ReplicaSet rs = new ReplicaSet(
                name,
                image,
                revision
            );

            replicaSets.put(rs.getId(), rs);

            history.put(
                revision,
                new Revision(
                    revision,
                    image,
                    rs.getId()
                )
            );

            return rs;
        }

        private List<ReplicaSet> activeReplicaSets() {
            return replicaSets.values().stream()
                .filter(ReplicaSet::isActive)
                .toList();
        }

        private ReplicaSet currentReplicaSet() {
            return activeReplicaSets().stream()
                .filter(rs -> rs.getImage().equals(currentImage))
                .max(Comparator.comparingInt(ReplicaSet::getRevision))
                .orElseThrow(
                    () -> new DeploymentException(
                        "Current ReplicaSet does not exist"
                    )
                );
        }

        private Pod createPod(ReplicaSet rs) {
            Pod pod = new Pod(
                rs.getImage(),
                rs.getId()
            );

            pod.start();
            rs.addPod(pod);

            return pod;
        }

        private void sync(
            ReplicaSet rs,
            int desired
        ) {
            rs.setDesiredReplicas(desired);

            List<Pod> active = new ArrayList<>(rs.activePods());

            while (active.size() < desired) {
                active.add(createPod(rs));
            }

            while (active.size() > desired) {
                Pod pod = active.remove(active.size() - 1);
                pod.terminate();
            }
        }

        /*
         * Reconciliation is the controller's central operation.
         * It is repeated until actual state matches desired state.
         */
        public synchronized void reconcile() {
            if (activeReplicaSets().isEmpty()) {
                createReplicaSet(currentImage);
            }

            for (ReplicaSet rs : activeReplicaSets()) {
                int desired = rs.getImage().equals(currentImage)
                    ? policy.replicas()
                    : 0;

                sync(rs, desired);
            }

            refreshStatus();
        }

        private void refreshStatus() {
            List<Pod> pods = activeReplicaSets().stream()
                .flatMap(rs -> rs.activePods().stream())
                .toList();

            int ready = (int) pods.stream()
                .filter(Pod::isReady)
                .count();

            int available = (int) pods.stream()
                .filter(pod -> pod.isAvailable(policy.minReadySeconds()))
                .count();

            int updated = (int) pods.stream()
                .filter(pod -> pod.getImage().equals(currentImage))
                .count();

            int desired = policy.replicas();

            status = new DeploymentStatus(
                desired,
                updated,
                ready,
                available,
                Math.max(0, desired - available),
                available >= desired
                    ? DeploymentPhase.AVAILABLE
                    : DeploymentPhase.PROGRESSING
            );
        }

        public synchronized void markReady(String podId) {
            for (ReplicaSet rs : replicaSets.values()) {
                for (Pod pod : rs.getPods()) {
                    if (pod.getId().equals(podId)) {
                        pod.markReady();
                        refreshStatus();
                        return;
                    }
                }
            }

            throw new DeploymentException("Pod not found");
        }

        public synchronized void markCurrentPodsReady() {
            for (Pod pod : currentReplicaSet().activePods()) {
                if (!pod.isReady()) {
                    pod.markReady();
                }
            }

            refreshStatus();
        }

        public synchronized void scale(int replicas) {
            if (replicas < 0) {
                throw new IllegalArgumentException(
                    "Replica count cannot be negative"
                );
            }

            policy = new DeploymentPolicy(
                replicas,
                policy.maxSurge(),
                policy.maxUnavailable(),
                policy.minReadySeconds(),
                policy.revisionHistoryLimit()
            );

            generation++;
            reconcile();
        }

        public synchronized void updateImage(String newImage) {
            if (newImage == null || newImage.isBlank()) {
                throw new IllegalArgumentException(
                    "Image cannot be empty"
                );
            }

            if (newImage.equals(currentImage)) {
                return;
            }

            currentImage = newImage;
            revision++;
            generation++;

            activeReplicaSets().forEach(ReplicaSet::deactivate);

            createReplicaSet(newImage);
            reconcile();
        }

        public synchronized Operation rollingUpdateStep() {
            int desired = policy.replicas();

            List<ReplicaSet> oldSets = activeReplicaSets().stream()
                .filter(rs -> !rs.getImage().equals(currentImage))
                .toList();

            ReplicaSet target = currentReplicaSet();

            int total = activeReplicaSets().stream()
                .mapToInt(ReplicaSet::activeReplicas)
                .sum();

            int ready = activeReplicaSets().stream()
                .mapToInt(rs -> (int) rs.readyReplicas())
                .sum();

            int oldCount = oldSets.stream()
                .mapToInt(ReplicaSet::activeReplicas)
                .sum();

            int newCount = target.activeReplicas();

            int maxTotal = desired + policy.maxSurge();

            int minimumAvailable = Math.max(
                0,
                desired - policy.maxUnavailable()
            );

            if (newCount < desired && total < maxTotal) {
                createPod(target);
                refreshStatus();
                return Operation.CREATE;
            }

            if (oldCount > 0 && ready > minimumAvailable) {
                for (ReplicaSet rs : oldSets) {
                    List<Pod> pods = rs.activePods();

                    if (!pods.isEmpty()) {
                        pods.get(0).terminate();
                        refreshStatus();
                        return Operation.TERMINATE;
                    }
                }
            }

            if (oldCount == 0 && newCount >= desired) {
                oldSets.forEach(ReplicaSet::deactivate);
                refreshStatus();
                return Operation.COMPLETED;
            }

            return Operation.WAIT;
        }

        public synchronized List<Operation> rollingUpdate(
            int maximumSteps
        ) {
            if (maximumSteps <= 0) {
                throw new IllegalArgumentException(
                    "Maximum steps must be positive"
                );
            }

            List<Operation> operations = new ArrayList<>();

            for (int i = 0; i < maximumSteps; i++) {
                Operation operation = rollingUpdateStep();
                operations.add(operation);

                if (
                    operation == Operation.COMPLETED ||
                    operation == Operation.WAIT
                ) {
                    return List.copyOf(operations);
                }

                // Simulate successful readiness probes.
                markCurrentPodsReady();
            }

            throw new DeploymentException(
                "Rolling update exceeded its operation limit"
            );
        }

        public synchronized void rollback(int targetRevision) {
            Revision target = history.get(targetRevision);

            if (target == null) {
                throw new DeploymentException(
                    "Requested revision does not exist"
                );
            }

            if (target.image().equals(currentImage)) {
                return;
            }

            // Rollback produces a new revision, not a revision decrement.
            updateImage(target.image());
        }

        public synchronized void pruneHistory() {
            int limit = policy.revisionHistoryLimit();

            List<Integer> revisions = history.keySet().stream()
                .sorted()
                .toList();

            int keep = limit == 0 ? 1 : limit;

            for (
                int i = 0;
                i < revisions.size() - keep;
                i++
            ) {
                history.remove(revisions.get(i));
            }

            replicaSets.entrySet().removeIf(entry ->
                !entry.getValue().isActive()
                && !history.containsKey(
                    entry.getValue().getRevision()
                )
            );
        }

        public synchronized DeploymentStatus getStatus() {
            refreshStatus();
            return status;
        }

        public synchronized void report() {
            refreshStatus();

            System.out.println("\nDEPLOYMENT: " + name);
            System.out.println("NAMESPACE: " + namespace);
            System.out.println("IMAGE: " + currentImage);
            System.out.println("GENERATION: " + generation);
            System.out.println("REVISION: " + revision);

            System.out.println("\nREPLICASETS");

            for (ReplicaSet rs : activeReplicaSets()) {
                System.out.printf(
                    "%s | image=%s | desired=%d | active=%d | ready=%d%n",
                    rs.getName(),
                    rs.getImage(),
                    rs.getDesiredReplicas(),
                    rs.activeReplicas(),
                    rs.readyReplicas()
                );
            }

            System.out.println("\nSTATUS");
            System.out.println("Desired: " + status.desiredReplicas());
            System.out.println("Updated: " + status.updatedReplicas());
            System.out.println("Ready: " + status.readyReplicas());
            System.out.println("Available: " + status.availableReplicas());
            System.out.println("Unavailable: " + status.unavailableReplicas());
            System.out.println("Phase: " + status.phase());

            System.out.println("\nREVISION HISTORY");

            history.values().stream()
                .sorted(Comparator.comparingInt(Revision::number))
                .forEach(revision ->
                    System.out.println(
                        revision.number() + " -> " + revision.image()
                    )
                );
        }
    }

    public static void main(String[] args) {
        try {
            ContainerDefinition container =
                new ContainerDefinition(
                    "catalog",
                    "catalog-api:1.0.0",
                    8080,
                    "250m",
                    "256Mi"
                );

            DeploymentPolicy policy =
                new DeploymentPolicy(
                    3,
                    1,
                    0,
                    0,
                    5
                );

            DeploymentService deployment =
                new DeploymentService(
                    "catalog-api",
                    "production",
                    container,
                    policy
                );

            System.out.println("INITIAL DEPLOYMENT");

            deployment.markCurrentPodsReady();
            deployment.report();

            System.out.println("\nIMAGE UPDATE");

            deployment.updateImage("catalog-api:2.0.0");

            List<Operation> operations =
                deployment.rollingUpdate(50);

            operations.forEach(System.out::println);

            deployment.report();

            System.out.println("\nROLLBACK");

            deployment.rollback(1);
            deployment.markCurrentPodsReady();
            deployment.report();

            System.out.println("\nSCALING");

            deployment.scale(5);
            deployment.markCurrentPodsReady();
            deployment.report();

            deployment.pruneHistory();

        } catch (RuntimeException exception) {
            System.err.println(
                "DEPLOYMENT FAILURE: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
