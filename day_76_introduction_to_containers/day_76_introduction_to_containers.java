import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/*
 * Introduction to Containers
 *
 * Enterprise container deployment and governance simulator.
 *
 * Features:
 * - Immutable image metadata
 * - Layered application packaging
 * - Container lifecycle management
 * - Resource admission control
 * - CPU and memory allocation
 * - Network port reservation
 * - Security policies
 * - Health monitoring
 * - Restart policies
 * - Deployment services
 * - Audit events
 *
 * Java 17, no third-party dependencies.
 *
 * Educational simulation. It does not create real OS containers.
 */

public class ContainerEnterprise {

    enum ContainerState {
        CREATED,
        RUNNING,
        STOPPED,
        FAILED,
        REMOVED
    }

    enum HealthStatus {
        STARTING,
        HEALTHY,
        UNHEALTHY
    }

    enum RestartPolicy {
        NEVER,
        ON_FAILURE,
        ALWAYS
    }

    enum SecurityLevel {
        STANDARD,
        RESTRICTED
    }

    static class ContainerException extends RuntimeException {
        ContainerException(String message) {
            super(message);
        }
    }

    static class SecurityException extends ContainerException {
        SecurityException(String message) {
            super(message);
        }
    }

    static class ResourceException extends ContainerException {
        ResourceException(String message) {
            super(message);
        }
    }

    record ImageLayer(
        String instruction,
        String content,
        long sizeBytes
    ) {
        ImageLayer {
            Objects.requireNonNull(instruction);
            Objects.requireNonNull(content);

            if (instruction.isBlank() || sizeBytes < 0) {
                throw new IllegalArgumentException("Invalid image layer.");
            }
        }
    }

    record ContainerImage(
        String name,
        String tag,
        List<ImageLayer> layers,
        String entrypoint,
        Set<Integer> exposedPorts,
        String user,
        int vulnerabilities
    ) {
        ContainerImage {
            Objects.requireNonNull(name);
            Objects.requireNonNull(tag);
            Objects.requireNonNull(entrypoint);
            Objects.requireNonNull(user);

            if (name.isBlank() || tag.isBlank()) {
                throw new IllegalArgumentException("Image identity required.");
            }

            if (layers == null || layers.isEmpty()) {
                throw new IllegalArgumentException("Image layers required.");
            }

            if (entrypoint.isBlank()) {
                throw new IllegalArgumentException("Entrypoint required.");
            }

            if (vulnerabilities < 0) {
                throw new IllegalArgumentException("Invalid vulnerability count.");
            }

            layers = List.copyOf(layers);
            exposedPorts = Set.copyOf(exposedPorts);

            exposedPorts.forEach(ContainerImage::validatePort);
        }

        static void validatePort(int port) {
            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException("Invalid port: " + port);
            }
        }

        String reference() {
            return name + ":" + tag;
        }

        long imageSize() {
            return layers.stream()
                .mapToLong(ImageLayer::sizeBytes)
                .sum();
        }

        boolean exposesPort(int port) {
            return exposedPorts.contains(port);
        }
    }

    record ResourceLimits(
        double cpuCores,
        int memoryMB,
        int processLimit
    ) {
        ResourceLimits {
            if (
                !Double.isFinite(cpuCores) ||
                cpuCores <= 0 ||
                cpuCores > 64
            ) {
                throw new IllegalArgumentException("Invalid CPU limit.");
            }

            if (memoryMB < 16 || memoryMB > 262144) {
                throw new IllegalArgumentException("Invalid memory limit.");
            }

            if (processLimit < 1 || processLimit > 32768) {
                throw new IllegalArgumentException("Invalid process limit.");
            }
        }
    }

    record ContainerConfiguration(
        ResourceLimits resources,
        Map<String, String> environment,
        Map<Integer, Integer> portMappings,
        RestartPolicy restartPolicy,
        boolean privileged,
        boolean rootExecution,
        boolean readOnlyRootFilesystem
    ) {
        ContainerConfiguration {
            Objects.requireNonNull(resources);
            Objects.requireNonNull(restartPolicy);

            environment = Map.copyOf(environment);
            portMappings = Map.copyOf(portMappings);

            Set<Integer> hostPorts = new HashSet<>();

            portMappings.forEach((containerPort, hostPort) -> {
                ContainerImage.validatePort(containerPort);
                ContainerImage.validatePort(hostPort);

                if (!hostPorts.add(hostPort)) {
                    throw new IllegalArgumentException("Duplicate host port.");
                }
            });

            environment.forEach((key, value) -> {
                if (!key.matches("[A-Za-z_][A-Za-z0-9_]*")) {
                    throw new IllegalArgumentException("Invalid environment key.");
                }

                if (value == null || value.length() > 4096) {
                    throw new IllegalArgumentException("Invalid environment value.");
                }
            });
        }
    }

    record AuditEvent(
        Instant timestamp,
        String containerId,
        String action,
        String details
    ) {}

    interface SecurityPolicy {
        void validate(
            ContainerImage image,
            ContainerConfiguration configuration
        );
    }

    static class RestrictedSecurityPolicy implements SecurityPolicy {

        @Override
        public void validate(
            ContainerImage image,
            ContainerConfiguration configuration
        ) {
            if (image.vulnerabilities() > 0) {
                throw new SecurityException(
                    "Image contains known vulnerabilities."
                );
            }

            if ("root".equals(image.user())) {
                throw new SecurityException("Root-based images are prohibited.");
            }

            if (configuration.privileged()) {
                throw new SecurityException("Privileged execution prohibited.");
            }

            if (configuration.rootExecution()) {
                throw new SecurityException("Root execution prohibited.");
            }

            if (!configuration.readOnlyRootFilesystem()) {
                throw new SecurityException(
                    "Read-only root filesystem required."
                );
            }

            for (int port : configuration.portMappings().keySet()) {
                if (!image.exposesPort(port)) {
                    throw new SecurityException(
                        "Container port is not exposed by image: " + port
                    );
                }
            }
        }
    }

    static class ResourceManager {

        private final double maximumCPU;
        private final int maximumMemoryMB;

        private final Map<String, ResourceLimits> allocations =
            new HashMap<>();

        ResourceManager(double maximumCPU, int maximumMemoryMB) {
            if (maximumCPU <= 0 || maximumMemoryMB <= 0) {
                throw new IllegalArgumentException("Invalid host capacity.");
            }

            this.maximumCPU = maximumCPU;
            this.maximumMemoryMB = maximumMemoryMB;
        }

        synchronized void allocate(String id, ResourceLimits request) {
            if (allocations.containsKey(id)) {
                throw new ResourceException("Duplicate resource allocation.");
            }

            double usedCPU = allocations.values()
                .stream()
                .mapToDouble(ResourceLimits::cpuCores)
                .sum();

            int usedMemory = allocations.values()
                .stream()
                .mapToInt(ResourceLimits::memoryMB)
                .sum();

            if (usedCPU + request.cpuCores() > maximumCPU) {
                throw new ResourceException("Insufficient CPU capacity.");
            }

            if (usedMemory + request.memoryMB() > maximumMemoryMB) {
                throw new ResourceException("Insufficient memory capacity.");
            }

            allocations.put(id, request);
        }

        synchronized void release(String id) {
            allocations.remove(id);
        }

        synchronized Map<String, Number> usage() {
            double cpu = allocations.values()
                .stream()
                .mapToDouble(ResourceLimits::cpuCores)
                .sum();

            int memory = allocations.values()
                .stream()
                .mapToInt(ResourceLimits::memoryMB)
                .sum();

            return Map.of(
                "allocatedCPU", cpu,
                "allocatedMemoryMB", memory
            );
        }
    }

    static class NetworkManager {

        private final Map<Integer, String> portOwners = new HashMap<>();

        synchronized void reserve(
            String containerId,
            Map<Integer, Integer> mappings
        ) {
            for (int hostPort : mappings.values()) {
                String owner = portOwners.get(hostPort);

                if (owner != null && !owner.equals(containerId)) {
                    throw new ResourceException(
                        "Host port already allocated: " + hostPort
                    );
                }
            }

            mappings.values().forEach(
                port -> portOwners.put(port, containerId)
            );
        }

        synchronized void release(String containerId) {
            portOwners.entrySet().removeIf(
                entry -> entry.getValue().equals(containerId)
            );
        }
    }

    static class ImageRegistry {

        private final Map<String, ContainerImage> images = new HashMap<>();

        synchronized void push(ContainerImage image) {
            images.put(image.reference(), image);
        }

        synchronized ContainerImage pull(String reference) {
            ContainerImage image = images.get(reference);

            if (image == null) {
                throw new ContainerException(
                    "Image not found: " + reference
                );
            }

            return image;
        }

        synchronized List<String> list() {
            return Collections.unmodifiableList(
                new ArrayList<>(images.keySet())
            );
        }
    }

    static class Container {

        private final String id;
        private final ContainerImage image;
        private final ContainerConfiguration configuration;
        private final ResourceManager resourceManager;
        private final NetworkManager networkManager;

        private ContainerState state = ContainerState.CREATED;
        private HealthStatus health = HealthStatus.STARTING;
        private int restartCount = 0;

        private final List<AuditEvent> events = new ArrayList<>();

        Container(
            ContainerImage image,
            ContainerConfiguration configuration,
            ResourceManager resourceManager,
            NetworkManager networkManager
        ) {
            this.id = UUID.randomUUID().toString().substring(0, 12);
            this.image = image;
            this.configuration = configuration;
            this.resourceManager = resourceManager;
            this.networkManager = networkManager;

            record("CREATED", image.reference());
        }

        private void record(String action, String details) {
            events.add(
                new AuditEvent(
                    Instant.now(),
                    id,
                    action,
                    details
                )
            );
        }

        synchronized void start() {
            if (
                state != ContainerState.CREATED &&
                state != ContainerState.STOPPED
            ) {
                throw new ContainerException("Invalid start transition.");
            }

            resourceManager.allocate(id, configuration.resources());

            try {
                networkManager.reserve(
                    id,
                    configuration.portMappings()
                );
            } catch (RuntimeException error) {
                resourceManager.release(id);
                throw error;
            }

            state = ContainerState.RUNNING;
            health = HealthStatus.STARTING;

            record("STARTED", image.reference());
        }

        synchronized void markHealthy() {
            if (state != ContainerState.RUNNING) {
                throw new ContainerException("Container is not running.");
            }

            health = HealthStatus.HEALTHY;
            record("HEALTHY", "Health check passed");
        }

        synchronized void fail(String reason) {
            if (state != ContainerState.RUNNING) {
                throw new ContainerException("Container is not running.");
            }

            state = ContainerState.FAILED;
            health = HealthStatus.UNHEALTHY;

            resourceManager.release(id);
            networkManager.release(id);

            record("FAILED", reason);
        }

        synchronized void stop() {
            if (state != ContainerState.RUNNING) {
                throw new ContainerException("Container is not running.");
            }

            resourceManager.release(id);
            networkManager.release(id);

            state = ContainerState.STOPPED;
            health = HealthStatus.UNHEALTHY;

            record("STOPPED", "Graceful stop");
        }

        synchronized boolean restart() {
            if (state != ContainerState.FAILED) {
                throw new ContainerException("Container has not failed.");
            }

            RestartPolicy policy = configuration.restartPolicy();

            if (policy == RestartPolicy.NEVER) {
                return false;
            }

            if (
                policy == RestartPolicy.ON_FAILURE &&
                restartCount >= 3
            ) {
                return false;
            }

            restartCount++;
            state = ContainerState.STOPPED;
            start();

            record("RESTARTED", "Restart number " + restartCount);

            return true;
        }

        synchronized void remove() {
            if (state == ContainerState.RUNNING) {
                throw new ContainerException("Stop before removal.");
            }

            if (state == ContainerState.REMOVED) {
                throw new ContainerException("Already removed.");
            }

            state = ContainerState.REMOVED;
            record("REMOVED", "Container metadata retained for audit");
        }

        synchronized Map<String, Object> snapshot() {
            return Map.of(
                "id", id,
                "image", image.reference(),
                "state", state.name(),
                "health", health.name(),
                "restartCount", restartCount
            );
        }

        synchronized List<AuditEvent> events() {
            return List.copyOf(events);
        }

        String id() {
            return id;
        }

        ContainerState state() {
            return state;
        }
    }

    static class DeploymentService {

        private final ImageRegistry registry;
        private final ResourceManager resources;
        private final NetworkManager network;
        private final SecurityPolicy securityPolicy;

        private final Map<String, Container> containers =
            new HashMap<>();

        DeploymentService(
            ImageRegistry registry,
            ResourceManager resources,
            NetworkManager network,
            SecurityPolicy securityPolicy
        ) {
            this.registry = registry;
            this.resources = resources;
            this.network = network;
            this.securityPolicy = securityPolicy;
        }

        synchronized Container deploy(
            String imageReference,
            ContainerConfiguration configuration
        ) {
            ContainerImage image = registry.pull(imageReference);

            securityPolicy.validate(image, configuration);

            Container container = new Container(
                image,
                configuration,
                resources,
                network
            );

            container.start();

            containers.put(container.id(), container);

            return container;
        }

        synchronized List<Map<String, Object>> inventory() {
            return containers.values()
                .stream()
                .map(Container::snapshot)
                .collect(Collectors.toUnmodifiableList());
        }

        synchronized Container get(String id) {
            Container container = containers.get(id);

            if (container == null) {
                throw new ContainerException("Unknown container.");
            }

            return container;
        }
    }

    private static ContainerImage buildImage() {
        List<ImageLayer> layers = List.of(
            new ImageLayer("FROM", "eclipse-temurin:17-jre", 120000000),
            new ImageLayer("WORKDIR", "/application", 100),
            new ImageLayer("COPY", "application.jar", 25000000),
            new ImageLayer("USER", "app", 50),
            new ImageLayer("ENTRYPOINT", "java -jar application.jar", 100)
        );

        return new ContainerImage(
            "enterprise-inventory",
            "1.0.0",
            layers,
            "java -jar application.jar",
            Set.of(8080),
            "app",
            0
        );
    }

    private static ContainerConfiguration productionConfiguration() {
        return new ContainerConfiguration(
            new ResourceLimits(2.0, 1024, 150),
            Map.of(
                "APP_ENV", "production",
                "LOG_LEVEL", "INFO"
            ),
            Map.of(8080, 9080),
            RestartPolicy.ON_FAILURE,
            false,
            false,
            true
        );
    }

    public static void main(String[] args) {
        System.out.println("=== ENTERPRISE CONTAINER PLATFORM ===");

        ImageRegistry registry = new ImageRegistry();
        ResourceManager resources = new ResourceManager(16, 16384);
        NetworkManager network = new NetworkManager();

        SecurityPolicy policy = new RestrictedSecurityPolicy();

        DeploymentService deployment = new DeploymentService(
            registry,
            resources,
            network,
            policy
        );

        ContainerImage image = buildImage();

        registry.push(image);

        System.out.println("\nImage reference: " + image.reference());
        System.out.println("Image layers: " + image.layers().size());
        System.out.println("Image size: " + image.imageSize() + " bytes");

        Container container = deployment.deploy(
            image.reference(),
            productionConfiguration()
        );

        container.markHealthy();

        System.out.println("\nDeployment inventory:");
        deployment.inventory().forEach(System.out::println);

        System.out.println("\nResource usage:");
        System.out.println(resources.usage());

        container.fail("Simulated application process failure");

        System.out.println("\nRestart successful: " + container.restart());

        container.markHealthy();

        System.out.println("\nAudit events:");

        container.events().forEach(System.out::println);

        container.stop();
        container.remove();

        System.out.println("\nFinal state: " + container.state());

        // Validate rejection of privileged deployment.
        try {
            ContainerConfiguration insecure =
                new ContainerConfiguration(
                    new ResourceLimits(1, 256, 50),
                    Map.of(),
                    Map.of(),
                    RestartPolicy.NEVER,
                    true,
                    true,
                    false
                );

            deployment.deploy(image.reference(), insecure);

        } catch (SecurityException error) {
            System.out.println(
                "\nSecurity policy rejection: " + error.getMessage()
            );
        }

        // Validate resource limits.
        try {
            new ResourceLimits(0, 0, 0);

        } catch (IllegalArgumentException error) {
            System.out.println(
                "Resource validation rejection: " + error.getMessage()
            );
        }

        System.out.println("\nEnterprise deployment simulation completed.");
    }
}
