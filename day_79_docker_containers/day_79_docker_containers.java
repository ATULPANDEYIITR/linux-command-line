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
import java.util.stream.Collectors;

/**
 * Enterprise Docker Container Management System
 *
 * Java 17 implementation covering:
 * - Container lifecycle management
 * - Immutable deployment configurations
 * - Environment variable validation
 * - Networking
 * - Persistent volumes
 * - Resource allocation
 * - Health evaluation
 * - Deployment policies
 * - State transitions
 * - Enterprise service orchestration
 *
 * Compile:
 * javac DockerEnterprise.java
 *
 * Run:
 * java DockerEnterprise
 */

public class DockerEnterprise {

    enum ContainerState {
        CREATED,
        RUNNING,
        PAUSED,
        RESTARTING,
        EXITED,
        DEAD
    }

    enum NetworkDriver {
        BRIDGE,
        HOST,
        OVERLAY,
        NONE
    }

    enum RestartPolicy {
        NO,
        ALWAYS,
        UNLESS_STOPPED,
        ON_FAILURE
    }

    enum HealthStatus {
        STARTING,
        HEALTHY,
        UNHEALTHY,
        NOT_CONFIGURED
    }

    enum ReviewResult {
        APPROVED,
        REJECTED
    }

    static class DomainException extends RuntimeException {
        DomainException(String message) {
            super(message);
        }
    }

    static class InvalidTransitionException extends DomainException {
        InvalidTransitionException(String message) {
            super(message);
        }
    }

    record PortMapping(
        int hostPort,
        int containerPort,
        String protocol
    ) {
        PortMapping {
            if (hostPort < 1 || hostPort > 65535 ||
                containerPort < 1 || containerPort > 65535) {
                throw new DomainException("Invalid port mapping.");
            }

            protocol = protocol == null ? "tcp" : protocol.toLowerCase();

            if (!Set.of("tcp", "udp").contains(protocol)) {
                throw new DomainException("Unsupported protocol.");
            }
        }
    }

    record ResourceAllocation(
        double cpuCores,
        long memoryBytes
    ) {
        ResourceAllocation {
            if (!Double.isFinite(cpuCores) ||
                cpuCores <= 0 || cpuCores > 256) {
                throw new DomainException("Invalid CPU allocation.");
            }

            if (memoryBytes < 16L * 1024 * 1024) {
                throw new DomainException("Insufficient memory allocation.");
            }
        }
    }

    record VolumeMount(
        String source,
        String destination,
        boolean readOnly
    ) {
        VolumeMount {
            Objects.requireNonNull(source);
            Objects.requireNonNull(destination);

            if (source.isBlank() ||
                !destination.startsWith("/") ||
                destination.contains("..")) {
                throw new DomainException("Invalid volume mount.");
            }
        }
    }

    record NetworkConfiguration(
        String name,
        NetworkDriver driver
    ) {
        NetworkConfiguration {
            if (name == null || name.isBlank()) {
                throw new DomainException("Network name required.");
            }

            Objects.requireNonNull(driver);
        }
    }

    record DeploymentPolicy(
        boolean allowPrivileged,
        boolean requireReadOnlyRoot,
        boolean requireHealthCheck,
        double maximumCpuCores,
        long maximumMemoryBytes,
        int maximumPublishedPorts
    ) {
        DeploymentPolicy {
            if (maximumCpuCores <= 0 ||
                maximumMemoryBytes <= 0 ||
                maximumPublishedPorts < 0) {
                throw new DomainException("Invalid deployment policy.");
            }
        }

        static DeploymentPolicy production() {
            return new DeploymentPolicy(
                false,
                true,
                true,
                4.0,
                2L * 1024 * 1024 * 1024,
                10
            );
        }
    }

    static final class ContainerConfiguration {

        private static final Pattern NAME_PATTERN =
            Pattern.compile("^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$");

        private final String name;
        private final String image;
        private final List<String> command;
        private final Map<String, String> environment;
        private final List<PortMapping> ports;
        private final List<VolumeMount> volumes;
        private final Optional<NetworkConfiguration> network;
        private final ResourceAllocation resources;
        private final RestartPolicy restartPolicy;
        private final boolean privileged;
        private final boolean readOnlyRoot;

        ContainerConfiguration(
            String name,
            String image,
            List<String> command,
            Map<String, String> environment,
            List<PortMapping> ports,
            List<VolumeMount> volumes,
            Optional<NetworkConfiguration> network,
            ResourceAllocation resources,
            RestartPolicy restartPolicy,
            boolean privileged,
            boolean readOnlyRoot
        ) {
            this.name = Objects.requireNonNull(name);
            this.image = Objects.requireNonNull(image);

            this.command = List.copyOf(command);
            this.environment = Map.copyOf(environment);
            this.ports = List.copyOf(ports);
            this.volumes = List.copyOf(volumes);

            this.network = Objects.requireNonNull(network);
            this.resources = Objects.requireNonNull(resources);
            this.restartPolicy = Objects.requireNonNull(restartPolicy);

            this.privileged = privileged;
            this.readOnlyRoot = readOnlyRoot;

            validate();
        }

        private void validate() {
            if (!NAME_PATTERN.matcher(name).matches()) {
                throw new DomainException("Invalid container name.");
            }

            if (image.isBlank() || image.startsWith("-")) {
                throw new DomainException("Invalid image reference.");
            }

            for (var entry : environment.entrySet()) {
                if (!entry.getKey().matches("[A-Za-z_][A-Za-z0-9_]*")) {
                    throw new DomainException(
                        "Invalid environment variable: " + entry.getKey()
                    );
                }

                if (entry.getValue().contains("\0")) {
                    throw new DomainException("Invalid environment value.");
                }
            }

            Set<Integer> hostPorts = new HashSet<>();

            for (PortMapping port : ports) {
                if (!hostPorts.add(port.hostPort())) {
                    throw new DomainException("Duplicate host port.");
                }
            }
        }

        String name() {
            return name;
        }

        String image() {
            return image;
        }

        List<String> command() {
            return command;
        }

        Map<String, String> environment() {
            return environment;
        }

        List<PortMapping> ports() {
            return ports;
        }

        List<VolumeMount> volumes() {
            return volumes;
        }

        Optional<NetworkConfiguration> network() {
            return network;
        }

        ResourceAllocation resources() {
            return resources;
        }

        RestartPolicy restartPolicy() {
            return restartPolicy;
        }

        boolean privileged() {
            return privileged;
        }

        boolean readOnlyRoot() {
            return readOnlyRoot;
        }
    }

    static final class HealthMonitor {

        private final int maximumFailures;
        private int failures;
        private HealthStatus status;

        HealthMonitor(int maximumFailures) {
            if (maximumFailures < 1) {
                throw new DomainException("Invalid failure threshold.");
            }

            this.maximumFailures = maximumFailures;
            this.status = HealthStatus.STARTING;
        }

        synchronized HealthStatus evaluate(boolean successful) {
            if (successful) {
                failures = 0;
                status = HealthStatus.HEALTHY;
            } else {
                failures++;

                if (failures >= maximumFailures) {
                    status = HealthStatus.UNHEALTHY;
                }
            }

            return status;
        }

        synchronized HealthStatus status() {
            return status;
        }
    }

    static final class ManagedContainer {

        private final String id;
        private final ContainerConfiguration configuration;
        private final Instant createdAt;

        private ContainerState state;
        private final HealthMonitor healthMonitor;

        ManagedContainer(ContainerConfiguration configuration) {
            this.id = UUID.randomUUID().toString();
            this.configuration = configuration;
            this.createdAt = Instant.now();
            this.state = ContainerState.CREATED;
            this.healthMonitor = new HealthMonitor(3);
        }

        synchronized void transition(ContainerState next) {
            Map<ContainerState, Set<ContainerState>> transitions =
                new EnumMap<>(ContainerState.class);

            transitions.put(ContainerState.CREATED,
                Set.of(ContainerState.RUNNING,
                       ContainerState.EXITED,
                       ContainerState.DEAD));

            transitions.put(ContainerState.RUNNING,
                Set.of(ContainerState.PAUSED,
                       ContainerState.RESTARTING,
                       ContainerState.EXITED,
                       ContainerState.DEAD));

            transitions.put(ContainerState.PAUSED,
                Set.of(ContainerState.RUNNING,
                       ContainerState.EXITED,
                       ContainerState.DEAD));

            transitions.put(ContainerState.RESTARTING,
                Set.of(ContainerState.RUNNING,
                       ContainerState.EXITED,
                       ContainerState.DEAD));

            transitions.put(ContainerState.EXITED,
                Set.of(ContainerState.RUNNING,
                       ContainerState.DEAD));

            transitions.put(ContainerState.DEAD, Set.of());

            if (!transitions.get(state).contains(next)) {
                throw new InvalidTransitionException(
                    state + " cannot transition to " + next
                );
            }

            state = next;
        }

        synchronized ContainerState state() {
            return state;
        }

        String id() {
            return id;
        }

        ContainerConfiguration configuration() {
            return configuration;
        }

        Instant createdAt() {
            return createdAt;
        }

        HealthMonitor healthMonitor() {
            return healthMonitor;
        }
    }

    static final class ContainerRegistry {

        private final Map<String, ManagedContainer> containers =
            new HashMap<>();

        public synchronized ManagedContainer register(
            ContainerConfiguration configuration
        ) {
            if (containers.containsKey(configuration.name())) {
                throw new DomainException("Container name already registered.");
            }

            ManagedContainer container =
                new ManagedContainer(configuration);

            containers.put(configuration.name(), container);

            return container;
        }

        public synchronized ManagedContainer find(String name) {
            ManagedContainer container = containers.get(name);

            if (container == null) {
                throw new DomainException("Container not found: " + name);
            }

            return container;
        }

        public synchronized List<ManagedContainer> all() {
            return List.copyOf(containers.values());
        }

        public synchronized void remove(String name) {
            ManagedContainer container = find(name);

            if (container.state() == ContainerState.RUNNING ||
                container.state() == ContainerState.PAUSED) {
                throw new DomainException(
                    "Running containers cannot be removed."
                );
            }

            containers.remove(name);
        }
    }

    static final class DeploymentService {

        private final ContainerRegistry registry;
        private final DeploymentPolicy policy;

        DeploymentService(
            ContainerRegistry registry,
            DeploymentPolicy policy
        ) {
            this.registry = registry;
            this.policy = policy;
        }

        private List<String> evaluatePolicy(
            ContainerConfiguration config
        ) {
            List<String> violations = new ArrayList<>();

            if (config.privileged() && !policy.allowPrivileged()) {
                violations.add("Privileged mode prohibited.");
            }

            if (policy.requireReadOnlyRoot() &&
                !config.readOnlyRoot()) {
                violations.add("Read-only root filesystem required.");
            }

            if (config.resources().cpuCores() >
                policy.maximumCpuCores()) {
                violations.add("CPU allocation exceeds policy.");
            }

            if (config.resources().memoryBytes() >
                policy.maximumMemoryBytes()) {
                violations.add("Memory allocation exceeds policy.");
            }

            if (config.ports().size() >
                policy.maximumPublishedPorts()) {
                violations.add("Too many published ports.");
            }

            if (policy.requireHealthCheck()) {
                // Health checks are evaluated after container startup.
                // A deployment is registered in STARTING state.
            }

            return violations;
        }

        public ManagedContainer deploy(
            ContainerConfiguration config
        ) {
            List<String> violations = evaluatePolicy(config);

            if (!violations.isEmpty()) {
                throw new DomainException(
                    "Deployment rejected: " +
                    String.join("; ", violations)
                );
            }

            ManagedContainer container = registry.register(config);

            container.transition(ContainerState.RUNNING);

            return container;
        }

        public void stop(String name) {
            ManagedContainer container = registry.find(name);
            container.transition(ContainerState.EXITED);
        }

        public void start(String name) {
            ManagedContainer container = registry.find(name);
            container.transition(ContainerState.RUNNING);
        }

        public void pause(String name) {
            registry.find(name).transition(ContainerState.PAUSED);
        }

        public void unpause(String name) {
            registry.find(name).transition(ContainerState.RUNNING);
        }

        public void restart(String name) {
            ManagedContainer container = registry.find(name);

            if (container.state() == ContainerState.RUNNING) {
                container.transition(ContainerState.RESTARTING);
                container.transition(ContainerState.RUNNING);
            } else if (container.state() == ContainerState.EXITED) {
                container.transition(ContainerState.RUNNING);
            } else {
                throw new DomainException(
                    "Restart not permitted in current state."
                );
            }
        }

        public ReviewResult evaluateHealth(String name, boolean success) {
            ManagedContainer container = registry.find(name);

            HealthStatus status =
                container.healthMonitor().evaluate(success);

            if (status == HealthStatus.UNHEALTHY) {
                return ReviewResult.REJECTED;
            }

            return ReviewResult.APPROVED;
        }

        public boolean mergeEligible(String name) {
            ManagedContainer container = registry.find(name);

            if (container.state() != ContainerState.RUNNING) {
                return false;
            }

            if (policy.requireHealthCheck()) {
                return container.healthMonitor().status() ==
                    HealthStatus.HEALTHY;
            }

            return container.healthMonitor().status() !=
                HealthStatus.UNHEALTHY;
        }
    }

    static ContainerConfiguration createWebConfiguration() {
        return new ContainerConfiguration(
            "enterprise-nginx",
            "nginx:alpine",
            List.of(),
            Map.of(
                "APP_ENV", "production",
                "APP_PORT", "80"
            ),
            List.of(
                new PortMapping(8080, 80, "tcp")
            ),
            List.of(
                new VolumeMount(
                    "nginx-data",
                    "/usr/share/nginx/html",
                    true
                )
            ),
            Optional.of(
                new NetworkConfiguration(
                    "enterprise-network",
                    NetworkDriver.BRIDGE
                )
            ),
            new ResourceAllocation(
                0.5,
                128L * 1024 * 1024
            ),
            RestartPolicy.UNLESS_STOPPED,
            false,
            true
        );
    }

    static void runTests() {
        ContainerConfiguration config = createWebConfiguration();

        ManagedContainer container = new ManagedContainer(config);

        container.transition(ContainerState.RUNNING);
        container.transition(ContainerState.PAUSED);
        container.transition(ContainerState.RUNNING);
        container.transition(ContainerState.EXITED);

        boolean rejected = false;

        try {
            container.transition(ContainerState.PAUSED);
        } catch (InvalidTransitionException exception) {
            rejected = true;
        }

        if (!rejected) {
            throw new AssertionError("Invalid transition accepted.");
        }

        HealthMonitor monitor = new HealthMonitor(3);

        monitor.evaluate(false);
        monitor.evaluate(false);
        monitor.evaluate(false);

        if (monitor.status() != HealthStatus.UNHEALTHY) {
            throw new AssertionError("Health evaluation failed.");
        }

        System.out.println("Java 17 tests passed.");
    }

    public static void main(String[] args) {
        try {
            runTests();

            ContainerRegistry registry = new ContainerRegistry();

            DeploymentService service = new DeploymentService(
                registry,
                DeploymentPolicy.production()
            );

            ManagedContainer container =
                service.deploy(createWebConfiguration());

            System.out.println("\nCONTAINER DEPLOYED");
            System.out.println("ID: " + container.id());
            System.out.println(
                "Name: " + container.configuration().name()
            );
            System.out.println(
                "Image: " + container.configuration().image()
            );
            System.out.println("State: " + container.state());
            System.out.println(
                "Created: " + container.createdAt()
            );

            System.out.println("\nEvaluating health...");

            service.evaluateHealth("enterprise-nginx", true);

            System.out.println(
                "Health: " +
                container.healthMonitor().status()
            );

            System.out.println(
                "Deployment eligible: " +
                service.mergeEligible("enterprise-nginx")
            );

            service.pause("enterprise-nginx");
            System.out.println("Paused: " + container.state());

            service.unpause("enterprise-nginx");
            System.out.println("Resumed: " + container.state());

            service.restart("enterprise-nginx");
            System.out.println("Restarted: " + container.state());

            service.stop("enterprise-nginx");
            System.out.println("Stopped: " + container.state());

            registry.remove("enterprise-nginx");

            System.out.println("Container removed from registry.");

        } catch (DomainException exception) {
            System.err.println("OPERATION FAILED: " + exception.getMessage());
            System.exit(1);
        }
    }
}
