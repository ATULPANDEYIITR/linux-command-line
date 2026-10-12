import java.time.Instant;
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
import java.util.UUID;
import java.util.regex.Pattern;

/*
 * Enterprise virtual server provisioning and governance.
 *
 * Compile and run with Java 17:
 *   javac VirtualServerDeployment.java
 *   java VirtualServerDeployment
 *
 * This is an in-memory infrastructure simulation, not a cloud SDK client.
 */

public class VirtualServerDeployment {

    enum Environment {
        DEVELOPMENT, STAGING, PRODUCTION
    }

    enum State {
        REQUESTED, PROVISIONING, RUNNING, STOPPING, STOPPED,
        RESTARTING, TERMINATED, FAILED
    }

    enum Action {
        CREATE, START, STOP, RESTART, TERMINATE
    }

    record ComputeFlavor(
        String name,
        int vcpus,
        double memoryGiB,
        double hourlyRate
    ) {
        ComputeFlavor {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Flavor name is required.");
            }
            if (vcpus <= 0 || memoryGiB <= 0 || hourlyRate < 0) {
                throw new IllegalArgumentException("Invalid compute capacity.");
            }
        }
    }

    static final Map<String, ComputeFlavor> FLAVORS = Map.of(
        "small", new ComputeFlavor("small", 2, 4.0, 0.05),
        "medium", new ComputeFlavor("medium", 4, 16.0, 0.12),
        "large", new ComputeFlavor("large", 8, 32.0, 0.24)
    );

    record NetworkProfile(
        String subnetId,
        List<String> securityGroupIds,
        Set<Integer> ingressPorts,
        boolean publicIp
    ) {
        NetworkProfile {
            Objects.requireNonNull(subnetId, "Subnet is required.");
            securityGroupIds = List.copyOf(securityGroupIds);
            ingressPorts = Set.copyOf(ingressPorts);

            if (!Pattern.matches("subnet-[A-Za-z0-9-]{3,40}", subnetId)) {
                throw new IllegalArgumentException("Invalid subnet identifier.");
            }
            if (securityGroupIds.isEmpty()) {
                throw new IllegalArgumentException("Security groups are required.");
            }
            for (String group : securityGroupIds) {
                if (!Pattern.matches("sg-[A-Za-z0-9-]{3,40}", group)) {
                    throw new IllegalArgumentException(
                        "Invalid security group: " + group
                    );
                }
            }
            for (int port : ingressPorts) {
                if (port < 1 || port > 65535) {
                    throw new IllegalArgumentException("Invalid ingress port.");
                }
            }
        }
    }

    record ServerSpecification(
        String name,
        String imageId,
        String region,
        String flavor,
        Environment environment,
        NetworkProfile network,
        int rootDiskGiB,
        boolean encryptedDisk,
        boolean monitoringEnabled,
        String owner,
        Map<String, String> tags
    ) {
        ServerSpecification {
            Objects.requireNonNull(environment, "Environment is required.");
            Objects.requireNonNull(network, "Network profile is required.");
            Objects.requireNonNull(tags, "Tags are required.");
            Objects.requireNonNull(owner, "Owner is required.");

            tags = Map.copyOf(tags);
            validate();
        }

        private void validate() {
            if (name == null ||
                !Pattern.matches("[a-z][a-z0-9-]{1,39}", name)) {
                throw new IllegalArgumentException("Invalid server name.");
            }
            if (imageId == null ||
                !Pattern.matches("(img|ami)-[A-Za-z0-9-]{3,40}", imageId)) {
                throw new IllegalArgumentException("Invalid machine image.");
            }
            if (region == null ||
                !Pattern.matches("[a-z]{2}(-[a-z0-9]+)+-[0-9]+", region)) {
                throw new IllegalArgumentException("Invalid cloud region.");
            }
            if (!FLAVORS.containsKey(flavor)) {
                throw new IllegalArgumentException("Unknown compute flavor.");
            }
            if (rootDiskGiB < 8 || rootDiskGiB > 16384) {
                throw new IllegalArgumentException("Invalid root disk capacity.");
            }
            if (owner.isBlank()) {
                throw new IllegalArgumentException("An owner is required.");
            }
            if (environment == Environment.PRODUCTION &&
                (!encryptedDisk || !monitoringEnabled)) {
                throw new IllegalArgumentException(
                    "Production requires encryption and monitoring."
                );
            }
            if (!tags.containsKey("environment") ||
                !environment.name().equalsIgnoreCase(tags.get("environment"))) {
                throw new IllegalArgumentException(
                    "The environment tag must match the deployment environment."
                );
            }
        }
    }

    record AuditEvent(
        Instant timestamp,
        Action action,
        State previousState,
        State newState,
        String actor,
        String detail
    ) {}

    static class DeploymentException extends RuntimeException {
        DeploymentException(String message) {
            super(message);
        }
    }

    static class LifecycleException extends DeploymentException {
        LifecycleException(String message) {
            super(message);
        }
    }

    interface CloudAdapter {
        Allocation create(ServerSpecification specification);
        void stop(String providerId);
        Allocation start(String providerId);
        void restart(String providerId);
        void terminate(String providerId);
    }

    record Allocation(
        String providerId,
        String privateIp,
        String publicIp
    ) {}

    static final class SimulatedCloudAdapter implements CloudAdapter {
        private int nextHost = 10;
        private String failNextOperation;

        void failNext(String operation) {
            failNextOperation = operation;
        }

        private void checkFailure(String operation) {
            if (operation.equals(failNextOperation)) {
                failNextOperation = null;
                throw new DeploymentException(
                    "Provider operation failed: " + operation
                );
            }
        }

        @Override
        public Allocation create(ServerSpecification spec) {
            checkFailure("create");
            int host = nextHost++;
            String publicIp = spec.network().publicIp()
                ? "198.51.100." + host
                : null;

            return new Allocation(
                "cloud-" + UUID.randomUUID().toString().substring(0, 8),
                "10.50.0." + host,
                publicIp
            );
        }

        @Override
        public void stop(String providerId) {
            checkFailure("stop");
        }

        @Override
        public Allocation start(String providerId) {
            checkFailure("start");
            return new Allocation(providerId, "10.50.0." + nextHost++, null);
        }

        @Override
        public void restart(String providerId) {
            checkFailure("restart");
        }

        @Override
        public void terminate(String providerId) {
            checkFailure("terminate");
        }
    }

    static final class VirtualMachine {
        private final String id;
        private final ServerSpecification specification;
        private State state = State.REQUESTED;
        private String providerId;
        private String privateIp;
        private String publicIp;
        private String health = "unknown";
        private long bootCount;
        private Instant createdAt = Instant.now();
        private Instant updatedAt = createdAt;
        private final List<AuditEvent> audit = new ArrayList<>();

        VirtualMachine(ServerSpecification specification) {
            this.id = "vm-" + UUID.randomUUID().toString().substring(0, 12);
            this.specification = specification;
        }

        String id() { return id; }
        String name() { return specification.name(); }
        State state() { return state; }
        String health() { return health; }
        String privateIp() { return privateIp; }
        String publicIp() { return publicIp; }
        long bootCount() { return bootCount; }
        Instant createdAt() { return createdAt; }
        Instant updatedAt() { return updatedAt; }
        ServerSpecification specification() { return specification; }

        List<AuditEvent> auditTrail() {
            return Collections.unmodifiableList(audit);
        }
    }

    static final class LifecyclePolicy {
        private final Map<State, Set<State>> transitions =
            new EnumMap<>(State.class);

        LifecyclePolicy() {
            transitions.put(State.REQUESTED,
                Set.of(State.PROVISIONING, State.FAILED));
            transitions.put(State.PROVISIONING,
                Set.of(State.RUNNING, State.FAILED));
            transitions.put(State.RUNNING,
                Set.of(State.STOPPING, State.RESTARTING,
                       State.TERMINATED, State.FAILED));
            transitions.put(State.STOPPING,
                Set.of(State.STOPPED, State.FAILED));
            transitions.put(State.STOPPED,
                Set.of(State.PROVISIONING, State.TERMINATED, State.FAILED));
            transitions.put(State.RESTARTING,
                Set.of(State.RUNNING, State.FAILED));
            transitions.put(State.FAILED,
                Set.of(State.PROVISIONING, State.TERMINATED));
            transitions.put(State.TERMINATED, Set.of());
        }

        void assertAllowed(State from, State to) {
            if (!transitions.getOrDefault(from, Set.of()).contains(to)) {
                throw new LifecycleException(
                    "Transition " + from + " -> " + to + " is forbidden."
                );
            }
        }
    }

    static final class DeploymentService {
        private final CloudAdapter cloud;
        private final LifecyclePolicy lifecyclePolicy = new LifecyclePolicy();
        private final Map<String, VirtualMachine> instances = new HashMap<>();
        private final Map<String, String> nameIndex = new HashMap<>();

        DeploymentService(CloudAdapter cloud) {
            this.cloud = Objects.requireNonNull(cloud);
        }

        private void transition(
            VirtualMachine vm,
            State target,
            Action action,
            String actor,
            String detail
        ) {
            lifecyclePolicy.assertAllowed(vm.state, target);
            State previous = vm.state;
            vm.state = target;
            vm.updatedAt = Instant.now();
            vm.audit.add(new AuditEvent(
                vm.updatedAt, action, previous, target, actor, detail
            ));
        }

        VirtualMachine deploy(ServerSpecification specification) {
            Objects.requireNonNull(specification);

            if (nameIndex.containsKey(specification.name())) {
                throw new DeploymentException(
                    "Instance name already exists: " + specification.name()
                );
            }

            VirtualMachine vm = new VirtualMachine(specification);
            instances.put(vm.id, vm);
            nameIndex.put(specification.name(), vm.id);
            transition(vm, State.PROVISIONING, Action.CREATE,
                       "deployment-service", "");

            try {
                Allocation allocation = cloud.create(specification);
                applyAllocation(vm, allocation);
                vm.bootCount++;
                transition(vm, State.RUNNING, Action.CREATE,
                           "deployment-service", "Provisioning completed");
                vm.health = "healthy";
                return vm;
            } catch (RuntimeException error) {
                transition(vm, State.FAILED, Action.CREATE,
                           "deployment-service", error.getMessage());
                vm.health = "unhealthy";
                throw error;
            }
        }

        private void applyAllocation(VirtualMachine vm, Allocation allocation) {
            vm.providerId = allocation.providerId();
            vm.privateIp = allocation.privateIp();
            vm.publicIp = allocation.publicIp();
        }

        private VirtualMachine find(String id) {
            VirtualMachine vm = instances.get(id);
            if (vm == null) {
                throw new DeploymentException("Unknown instance: " + id);
            }
            return vm;
        }

        VirtualMachine stop(String id) {
            VirtualMachine vm = find(id);
            transition(vm, State.STOPPING, Action.STOP, "operator", "");

            try {
                cloud.stop(vm.providerId);
                transition(vm, State.STOPPED, Action.STOP, "operator", "");
                vm.health = "not-running";
                return vm;
            } catch (RuntimeException error) {
                transition(vm, State.FAILED, Action.STOP,
                           "operator", error.getMessage());
                vm.health = "unhealthy";
                throw error;
            }
        }

        VirtualMachine start(String id) {
            VirtualMachine vm = find(id);
            transition(vm, State.PROVISIONING, Action.START, "operator", "");

            try {
                Allocation allocation = cloud.start(vm.providerId);
                vm.privateIp = allocation.privateIp();
                vm.bootCount++;
                transition(vm, State.RUNNING, Action.START, "operator", "");
                vm.health = "healthy";
                return vm;
            } catch (RuntimeException error) {
                transition(vm, State.FAILED, Action.START,
                           "operator", error.getMessage());
                vm.health = "unhealthy";
                throw error;
            }
        }

        VirtualMachine restart(String id) {
            VirtualMachine vm = find(id);
            transition(vm, State.RESTARTING, Action.RESTART, "operator", "");

            try {
                cloud.restart(vm.providerId);
                vm.bootCount++;
                transition(vm, State.RUNNING, Action.RESTART, "operator", "");
                vm.health = "healthy";
                return vm;
            } catch (RuntimeException error) {
                transition(vm, State.FAILED, Action.RESTART,
                           "operator", error.getMessage());
                vm.health = "unhealthy";
                throw error;
            }
        }

        VirtualMachine terminate(String id) {
            VirtualMachine vm = find(id);
            cloud.terminate(vm.providerId);
            transition(vm, State.TERMINATED, Action.TERMINATE, "operator", "");
            vm.privateIp = null;
            vm.publicIp = null;
            vm.health = "terminated";
            return vm;
        }

        List<VirtualMachine> list(State state) {
            return instances.values().stream()
                .filter(vm -> state == null || vm.state == state)
                .sorted((left, right) -> left.createdAt.compareTo(right.createdAt))
                .toList();
        }

        double monthlyComputeEstimate(String id, double hours) {
            if (!Double.isFinite(hours) || hours < 0 || hours > 744) {
                throw new IllegalArgumentException("Invalid monthly billable hours.");
            }
            VirtualMachine vm = find(id);
            if (vm.state == State.TERMINATED) return 0.0;

            return Math.round(
                FLAVORS.get(vm.specification.flavor()).hourlyRate() * hours * 100
            ) / 100.0;
        }
    }

    static ServerSpecification specification(
        String name,
        String flavor,
        Environment environment
    ) {
        return new ServerSpecification(
            name,
            "img-linux2026",
            "ap-south-1",
            flavor,
            environment,
            new NetworkProfile(
                "subnet-app001",
                List.of("sg-app001"),
                Set.of(443),
                false
            ),
            40,
            true,
            true,
            "platform-operations",
            Map.of(
                "environment", environment.name().toLowerCase(),
                "owner", "platform-operations",
                "service", name
            )
        );
    }

    public static void main(String[] args) {
        SimulatedCloudAdapter adapter = new SimulatedCloudAdapter();
        DeploymentService service = new DeploymentService(adapter);

        VirtualMachine catalog = service.deploy(
            specification("catalog-api", "medium", Environment.DEVELOPMENT)
        );
        VirtualMachine payments = service.deploy(
            specification("payments-api", "large", Environment.PRODUCTION)
        );

        System.out.println("Enterprise virtual server inventory");
        for (VirtualMachine vm : service.list(null)) {
            System.out.printf(
                "%-18s %-14s %-8s %-15s monthly=$%.2f%n",
                vm.name(),
                vm.state(),
                vm.specification().flavor(),
                vm.privateIp(),
                service.monthlyComputeEstimate(vm.id(), 730)
            );
        }

        service.stop(catalog.id());
        service.start(catalog.id());
        service.restart(payments.id());

        adapter.failNext("stop");
        try {
            service.stop(payments.id());
        } catch (DeploymentException error) {
            System.out.println("Provider failure handled: " + error.getMessage());
        }

        System.out.println("\nPayments audit trail");
        for (AuditEvent event : payments.auditTrail()) {
            System.out.printf(
                "%s %-10s %-12s -> %-12s %s%n",
                event.timestamp(),
                event.action(),
                event.previousState(),
                event.newState(),
                event.detail()
            );
        }

        System.out.println("\nInventory after operational failure");
        for (VirtualMachine vm : service.list(null)) {
            System.out.printf("%-18s %-14s health=%s%n",
                vm.name(), vm.state(), vm.health());
        }

        service.terminate(catalog.id());
        System.out.printf(
            "Terminated catalog compute estimate: $%.2f%n",
            service.monthlyComputeEstimate(catalog.id(), 730)
        );

        try {
            service.start(catalog.id());
        } catch (LifecycleException error) {
            System.out.println("Terminal-state guard: " + error.getMessage());
        }
    }
}
