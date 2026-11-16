import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/*
 * Docker Fundamentals: Enterprise Container Management System.
 *
 * Java 17 implementation featuring:
 * - Docker architecture
 * - Immutable image manifests
 * - Image layer management
 * - Registry authentication
 * - Container lifecycle management
 * - Resource allocation policies
 * - Port and volume validation
 * - Enterprise deployment services
 * - State transition auditing
 * - Exception handling
 * - Unit-style tests
 *
 * Compile:
 * javac DockerFundamentals.java
 *
 * Execute:
 * java DockerFundamentals
 * java DockerFundamentals test
 */

public class DockerFundamentals {

    // ========================================================
    // 1. ENUMERATIONS
    // ========================================================

    enum ContainerState {
        CREATED,
        RUNNING,
        PAUSED,
        RESTARTING,
        EXITED,
        DEAD
    }

    enum ImageOrigin {
        BUILT,
        REGISTRY,
        LOCAL
    }

    enum DockerComponent {
        CLI,
        DOCKER_DAEMON,
        CONTAINERD,
        RUNC,
        BUILDKIT,
        REGISTRY
    }

    // ========================================================
    // 2. CUSTOM EXCEPTIONS
    // ========================================================

    static class DockerException extends RuntimeException {
        DockerException(String message) {
            super(message);
        }
    }

    static class ResourcePolicyException extends DockerException {
        ResourcePolicyException(String message) {
            super(message);
        }
    }

    static class RegistryAuthenticationException
            extends DockerException {

        RegistryAuthenticationException(String message) {
            super(message);
        }
    }

    static class InvalidStateTransitionException
            extends DockerException {

        InvalidStateTransitionException(String message) {
            super(message);
        }
    }

    // ========================================================
    // 3. VALIDATION
    // ========================================================

    static final class Validation {

        private Validation() {}

        static String required(String value, String field) {
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException(
                    field + " is required"
                );
            }

            if (value.length() > 255 || value.indexOf('\0') >= 0) {
                throw new IllegalArgumentException(
                    field + " has an invalid length or character"
                );
            }

            return value.trim();
        }

        static void imageReference(String repository, String tag) {
            String reference = required(repository, "Repository")
                + ":" + required(tag, "Tag");

            if (!reference.matches(
                "^(?:[a-zA-Z0-9.-]+(?::\\d+)?/)?"
                + "[a-z0-9]+(?:[._-][a-z0-9]+)*"
                + "(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*"
                + ":[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$"
            )) {
                throw new IllegalArgumentException(
                    "Invalid image reference: " + reference
                );
            }
        }

        static void port(int port) {
            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException(
                    "Invalid port: " + port
                );
            }
        }

        static void resources(double cpu, int memoryMB) {
            if (!Double.isFinite(cpu) || cpu <= 0) {
                throw new IllegalArgumentException(
                    "CPU allocation must be positive"
                );
            }

            if (memoryMB < 6) {
                throw new IllegalArgumentException(
                    "Memory must be at least 6 MB"
                );
            }
        }
    }

    // ========================================================
    // 4. DOCKER ARCHITECTURE
    // ========================================================

    record ArchitectureInfo(
        DockerComponent component,
        String responsibility
    ) {}

    static class ArchitectureService {

        static List<ArchitectureInfo> components() {
            return List.of(
                new ArchitectureInfo(
                    DockerComponent.CLI,
                    "Receives commands and communicates through the Docker API."
                ),
                new ArchitectureInfo(
                    DockerComponent.DOCKER_DAEMON,
                    "Manages images, containers, networks and volumes."
                ),
                new ArchitectureInfo(
                    DockerComponent.CONTAINERD,
                    "Manages container lifecycle operations."
                ),
                new ArchitectureInfo(
                    DockerComponent.RUNC,
                    "Creates isolated container processes."
                ),
                new ArchitectureInfo(
                    DockerComponent.BUILDKIT,
                    "Builds and optimizes container images."
                ),
                new ArchitectureInfo(
                    DockerComponent.REGISTRY,
                    "Stores and distributes images."
                )
            );
        }

        static void display() {
            System.out.println("\nDOCKER ARCHITECTURE");

            components().forEach(component ->
                System.out.println(
                    component.component() + ": "
                    + component.responsibility()
                )
            );
        }
    }

    // ========================================================
    // 5. IMAGE LAYER
    // ========================================================

    record ImageLayer(
        String id,
        String instruction,
        double sizeMB
    ) {
        ImageLayer {
            id = Validation.required(id, "Layer ID");

            instruction = Validation.required(
                instruction,
                "Layer instruction"
            );

            if (!Double.isFinite(sizeMB) || sizeMB < 0) {
                throw new IllegalArgumentException(
                    "Layer size cannot be negative"
                );
            }
        }
    }

    // ========================================================
    // 6. IMMUTABLE IMAGE MANIFEST
    // ========================================================

    record ImageManifest(
        String repository,
        String tag,
        List<ImageLayer> layers,
        ImageOrigin origin,
        Instant createdAt
    ) {
        ImageManifest {
            repository = Validation.required(
                repository,
                "Repository"
            );

            tag = Validation.required(tag, "Tag");

            Validation.imageReference(repository, tag);

            Objects.requireNonNull(origin);
            Objects.requireNonNull(createdAt);

            layers = List.copyOf(layers);

            if (layers.isEmpty()) {
                throw new IllegalArgumentException(
                    "Image requires at least one layer"
                );
            }

            Set<String> identifiers = new HashSet<>();

            for (ImageLayer layer : layers) {
                if (!identifiers.add(layer.id())) {
                    throw new IllegalArgumentException(
                        "Duplicate image layer: " + layer.id()
                    );
                }
            }
        }

        String reference() {
            return repository + ":" + tag;
        }

        double sizeMB() {
            return layers.stream()
                .mapToDouble(ImageLayer::sizeMB)
                .sum();
        }

        int layerCount() {
            return layers.size();
        }
    }

    // ========================================================
    // 7. IMAGE REPOSITORY
    // ========================================================

    static class ImageRepository {

        private final Map<String, ImageManifest> images =
            new LinkedHashMap<>();

        public synchronized void save(ImageManifest image) {
            Objects.requireNonNull(image);

            images.put(image.reference(), image);
        }

        public synchronized ImageManifest find(String reference) {
            ImageManifest image = images.get(reference);

            if (image == null) {
                throw new DockerException(
                    "Image not found: " + reference
                );
            }

            return image;
        }

        public synchronized boolean exists(String reference) {
            return images.containsKey(reference);
        }

        public synchronized List<ImageManifest> findAll() {
            return List.copyOf(images.values());
        }

        public synchronized void delete(String reference) {
            if (images.remove(reference) == null) {
                throw new DockerException(
                    "Image does not exist: " + reference
                );
            }
        }
    }

    // ========================================================
    // 8. REGISTRY SERVICE
    // ========================================================

    static class RegistryService {

        private final String hostname;

        private final Map<String, ImageManifest> remoteImages =
            new HashMap<>();

        private final Set<String> authenticatedUsers =
            new HashSet<>();

        RegistryService(String hostname) {
            this.hostname = Validation.required(
                hostname,
                "Registry hostname"
            );
        }

        public synchronized void login(
            String username,
            String token
        ) {
            username = Validation.required(username, "Username");
            Validation.required(token, "Token");

            // Only identity is retained. Authentication secrets
            // must not be stored in application logs or inventories.
            authenticatedUsers.add(username);
        }

        public synchronized void logout(String username) {
            authenticatedUsers.remove(username);
        }

        public synchronized String push(
            ImageManifest image,
            String username
        ) {
            Objects.requireNonNull(image);

            if (!authenticatedUsers.contains(username)) {
                throw new RegistryAuthenticationException(
                    "Registry login required"
                );
            }

            String remoteReference =
                hostname + "/" + image.reference();

            remoteImages.put(remoteReference, image);

            return remoteReference;
        }

        public synchronized ImageManifest pull(
            String remoteReference
        ) {
            ImageManifest image = remoteImages.get(remoteReference);

            if (image == null) {
                throw new DockerException(
                    "Registry image not found: " + remoteReference
                );
            }

            return image;
        }

        public synchronized int imageCount() {
            return remoteImages.size();
        }
    }

    // ========================================================
    // 9. CONTAINER CONFIGURATION
    // ========================================================

    record ContainerConfiguration(
        String name,
        String imageReference,
        Map<Integer, Integer> ports,
        Map<String, String> volumes,
        Map<String, String> environment,
        double cpu,
        int memoryMB
    ) {
        ContainerConfiguration {
            name = Validation.required(name, "Container name");

            imageReference = Validation.required(
                imageReference,
                "Image reference"
            );

            ports = Map.copyOf(ports);
            volumes = Map.copyOf(volumes);
            environment = Map.copyOf(environment);

            Validation.resources(cpu, memoryMB);

            ports.forEach((host, container) -> {
                Validation.port(host);
                Validation.port(container);
            });

            environment.forEach((key, value) -> {
                if (!key.matches("[A-Za-z_][A-Za-z0-9_]*")) {
                    throw new IllegalArgumentException(
                        "Invalid environment key: " + key
                    );
                }

                if (value == null || value.indexOf('\0') >= 0) {
                    throw new IllegalArgumentException(
                        "Invalid environment value"
                    );
                }
            });
        }
    }

    // ========================================================
    // 10. RESOURCE POLICY
    // ========================================================

    interface DeploymentPolicy {
        void evaluate(ContainerConfiguration configuration);
    }

    static class EnterpriseResourcePolicy
            implements DeploymentPolicy {

        private final double maximumCPU;
        private final int maximumMemoryMB;
        private final int maximumPorts;

        EnterpriseResourcePolicy(
            double maximumCPU,
            int maximumMemoryMB,
            int maximumPorts
        ) {
            Validation.resources(maximumCPU, maximumMemoryMB);

            if (maximumPorts < 1) {
                throw new IllegalArgumentException(
                    "Maximum ports must be positive"
                );
            }

            this.maximumCPU = maximumCPU;
            this.maximumMemoryMB = maximumMemoryMB;
            this.maximumPorts = maximumPorts;
        }

        @Override
        public void evaluate(
            ContainerConfiguration configuration
        ) {
            List<String> violations = new ArrayList<>();

            if (configuration.cpu() > maximumCPU) {
                violations.add("CPU allocation exceeds policy");
            }

            if (configuration.memoryMB() > maximumMemoryMB) {
                violations.add("Memory allocation exceeds policy");
            }

            if (configuration.ports().size() > maximumPorts) {
                violations.add("Port allocation exceeds policy");
            }

            if (!violations.isEmpty()) {
                throw new ResourcePolicyException(
                    String.join("; ", violations)
                );
            }
        }
    }

    // ========================================================
    // 11. CONTAINER DOMAIN ENTITY
    // ========================================================

    static class ContainerEntity {

        private final String id = UUID.randomUUID().toString();

        private final ContainerConfiguration configuration;
        private final ImageManifest image;

        private ContainerState state = ContainerState.CREATED;

        private int restartCount = 0;

        private final List<String> auditLog =
            new ArrayList<>();

        ContainerEntity(
            ContainerConfiguration configuration,
            ImageManifest image
        ) {
            this.configuration = Objects.requireNonNull(
                configuration
            );

            this.image = Objects.requireNonNull(image);
        }

        private void transition(
            ContainerState expected,
            ContainerState next
        ) {
            if (state != expected) {
                throw new InvalidStateTransitionException(
                    "Cannot transition from "
                    + state + " to " + next
                );
            }

            ContainerState previous = state;
            state = next;

            auditLog.add(
                Instant.now() + " | "
                + previous + " -> " + next
            );
        }

        public synchronized void start() {
            if (
                state != ContainerState.CREATED &&
                state != ContainerState.EXITED
            ) {
                throw new InvalidStateTransitionException(
                    "Container cannot start from " + state
                );
            }

            transition(state, ContainerState.RUNNING);
        }

        public synchronized void pause() {
            transition(
                ContainerState.RUNNING,
                ContainerState.PAUSED
            );
        }

        public synchronized void unpause() {
            transition(
                ContainerState.PAUSED,
                ContainerState.RUNNING
            );
        }

        public synchronized void stop() {
            if (
                state != ContainerState.RUNNING &&
                state != ContainerState.PAUSED
            ) {
                throw new InvalidStateTransitionException(
                    "Container cannot stop from " + state
                );
            }

            transition(state, ContainerState.EXITED);
        }

        public synchronized void restart() {
            if (state == ContainerState.DEAD) {
                throw new InvalidStateTransitionException(
                    "Dead container cannot restart"
                );
            }

            if (
                state == ContainerState.RUNNING ||
                state == ContainerState.PAUSED
            ) {
                stop();
            }

            if (state != ContainerState.EXITED) {
                throw new InvalidStateTransitionException(
                    "Container is not restartable"
                );
            }

            transition(
                ContainerState.EXITED,
                ContainerState.RESTARTING
            );

            restartCount++;

            transition(
                ContainerState.RESTARTING,
                ContainerState.RUNNING
            );
        }

        public synchronized void remove(boolean force) {
            if (
                (state == ContainerState.RUNNING ||
                 state == ContainerState.PAUSED) &&
                !force
            ) {
                throw new InvalidStateTransitionException(
                    "Active container requires force removal"
                );
            }

            ContainerState previous = state;
            state = ContainerState.DEAD;

            auditLog.add(
                Instant.now() + " | "
                + previous + " -> DEAD"
            );
        }

        public String id() {
            return id;
        }

        public String name() {
            return configuration.name();
        }

        public synchronized ContainerState state() {
            return state;
        }

        public int restartCount() {
            return restartCount;
        }

        public List<String> auditLog() {
            return List.copyOf(auditLog);
        }

        public Map<String, Object> inspect() {
            Map<String, Object> details = new LinkedHashMap<>();

            details.put("id", id);
            details.put("name", configuration.name());
            details.put("image", image.reference());
            details.put("state", state);
            details.put("cpu", configuration.cpu());
            details.put("memoryMB", configuration.memoryMB());
            details.put("ports", configuration.ports());
            details.put("volumes", configuration.volumes());
            details.put("restartCount", restartCount);

            return Collections.unmodifiableMap(details);
        }
    }

    // ========================================================
    // 12. ENTERPRISE DEPLOYMENT SERVICE
    // ========================================================

    static class ContainerDeploymentService {

        private final ImageRepository imageRepository;
        private final DeploymentPolicy policy;

        private final Map<String, ContainerEntity> containers =
            new LinkedHashMap<>();

        ContainerDeploymentService(
            ImageRepository imageRepository,
            DeploymentPolicy policy
        ) {
            this.imageRepository = Objects.requireNonNull(
                imageRepository
            );

            this.policy = Objects.requireNonNull(policy);
        }

        public synchronized ContainerEntity deploy(
            ContainerConfiguration configuration
        ) {
            if (containers.containsKey(configuration.name())) {
                throw new DockerException(
                    "Container name already exists"
                );
            }

            policy.evaluate(configuration);

            ImageManifest image = imageRepository.find(
                configuration.imageReference()
            );

            ContainerEntity container = new ContainerEntity(
                configuration,
                image
            );

            containers.put(container.name(), container);

            return container;
        }

        public synchronized ContainerEntity find(String name) {
            ContainerEntity container = containers.get(name);

            if (container == null) {
                throw new DockerException(
                    "Container not found: " + name
                );
            }

            return container;
        }

        public synchronized void remove(
            String name,
            boolean force
        ) {
            ContainerEntity container = find(name);

            container.remove(force);
            containers.remove(name);
        }

        public synchronized List<ContainerEntity> findAll() {
            return List.copyOf(containers.values());
        }

        public synchronized List<ContainerEntity> runningContainers() {
            return containers.values().stream()
                .filter(c -> c.state() == ContainerState.RUNNING)
                .collect(Collectors.toList());
        }
    }

    // ========================================================
    // 13. DEMONSTRATION
    // ========================================================

    static void demonstrate() {

        ArchitectureService.display();

        ImageManifest image = new ImageManifest(
            "enterprise/customer-api",
            "2.0.0",
            List.of(
                new ImageLayer(
                    "layer-001",
                    "FROM eclipse-temurin:17",
                    85
                ),
                new ImageLayer(
                    "layer-002",
                    "COPY dependencies",
                    25
                ),
                new ImageLayer(
                    "layer-003",
                    "COPY application",
                    12
                )
            ),
            ImageOrigin.BUILT,
            Instant.now()
        );

        System.out.println("\nIMAGE MANIFEST");
        System.out.println("Reference: " + image.reference());
        System.out.println("Layers: " + image.layerCount());
        System.out.println("Size: " + image.sizeMB() + " MB");

        RegistryService registry = new RegistryService(
            "registry.example.com"
        );

        registry.login("deployment-user", "demo-secret");

        String remote = registry.push(
            image,
            "deployment-user"
        );

        System.out.println("\nPUSHED IMAGE: " + remote);

        ImageRepository imageRepository =
            new ImageRepository();

        imageRepository.save(registry.pull(remote));

        DeploymentPolicy policy =
            new EnterpriseResourcePolicy(
                4.0,
                2048,
                20
            );

        ContainerDeploymentService deploymentService =
            new ContainerDeploymentService(
                imageRepository,
                policy
            );

        ContainerConfiguration configuration =
            new ContainerConfiguration(
                "customer-api",
                image.reference(),
                Map.of(
                    8080, 8080,
                    8443, 8443
                ),
                Map.of(
                    "/srv/customer-data", "/app/data",
                    "/srv/customer-logs", "/app/logs"
                ),
                Map.of(
                    "APP_ENV", "production",
                    "LOG_LEVEL", "info"
                ),
                2.0,
                1024
            );

        ContainerEntity container =
            deploymentService.deploy(configuration);

        System.out.println("\nCONTAINER LIFECYCLE");

        container.start();
        container.pause();
        container.unpause();
        container.restart();
        container.stop();
        container.start();

        System.out.println("\nCONTAINER INSPECTION");
        container.inspect().forEach(
            (key, value) ->
                System.out.println(key + ": " + value)
        );

        System.out.println("\nAUDIT TRAIL");
        container.auditLog().forEach(System.out::println);

        System.out.println(
            "\nRUNNING CONTAINERS: "
            + deploymentService.runningContainers().size()
        );

        try {
            ContainerConfiguration excessive =
                new ContainerConfiguration(
                    "invalid-container",
                    image.reference(),
                    Map.of(),
                    Map.of(),
                    Map.of(),
                    10,
                    8192
                );

            deploymentService.deploy(excessive);

        } catch (ResourcePolicyException error) {
            System.out.println(
                "\nEXPECTED POLICY FAILURE: " + error.getMessage()
            );
        }

        try {
            registry.push(image, "unauthorized");

        } catch (RegistryAuthenticationException error) {
            System.out.println(
                "EXPECTED REGISTRY FAILURE: " + error.getMessage()
            );
        }
    }

    // ========================================================
    // 14. AUTOMATED TESTS
    // ========================================================

    static void runTests() {

        ImageManifest image = new ImageManifest(
            "test/service",
            "1.0",
            List.of(
                new ImageLayer("base", "FROM scratch", 10)
            ),
            ImageOrigin.BUILT,
            Instant.now()
        );

        ImageRepository repository = new ImageRepository();
        repository.save(image);

        ContainerDeploymentService service =
            new ContainerDeploymentService(
                repository,
                new EnterpriseResourcePolicy(2, 1024, 5)
            );

        ContainerConfiguration configuration =
            new ContainerConfiguration(
                "test-container",
                image.reference(),
                Map.of(8080, 80),
                Map.of(),
                Map.of("APP_ENV", "test"),
                1,
                256
            );

        ContainerEntity container = service.deploy(configuration);

        container.start();

        assert container.state() == ContainerState.RUNNING;

        container.pause();

        assert container.state() == ContainerState.PAUSED;

        container.unpause();
        container.restart();

        assert container.restartCount() == 1;

        container.stop();

        boolean rejected = false;

        try {
            container.pause();
        } catch (InvalidStateTransitionException error) {
            rejected = true;
        }

        assert rejected : "Invalid transition must be rejected";

        rejected = false;

        try {
            Validation.port(70000);
        } catch (IllegalArgumentException error) {
            rejected = true;
        }

        assert rejected : "Invalid port must be rejected";

        rejected = false;

        try {
            new ContainerConfiguration(
                "invalid",
                image.reference(),
                Map.of(),
                Map.of(),
                Map.of(),
                1,
                2
            );
        } catch (IllegalArgumentException error) {
            rejected = true;
        }

        assert rejected : "Invalid memory must be rejected";

        System.out.println("All Java 17 tests passed.");
    }

    // ========================================================
    // 15. MAIN
    // ========================================================

    public static void main(String[] args) {

        try {
            String command = args.length == 0
                ? "demo"
                : args[0];

            if (command.equals("demo")) {
                demonstrate();
            } else if (command.equals("test")) {
                runTests();
            } else {
                System.err.println(
                    "Usage: java DockerFundamentals [demo|test]"
                );

                System.exit(2);
            }

        } catch (DockerException | IllegalArgumentException error) {
            System.err.println(
                "Execution failed: " + error.getMessage()
            );

            System.exit(1);
        }
    }
}
