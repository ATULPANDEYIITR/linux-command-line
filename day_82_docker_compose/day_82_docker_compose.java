import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;

/*
 * Docker Compose: Enterprise application deployment model.
 *
 * Java 17 features:
 * - Records and immutable domain types
 * - Enums and sealed lifecycle concepts
 * - Service configuration validation
 * - Dependency graph evaluation
 * - Policy-based startup
 * - Health and restart management
 * - Deployment reporting
 * - Custom exceptions
 *
 * Compile:
 * javac DockerComposeEnterprise.java
 *
 * Run:
 * java DockerComposeEnterprise
 */

public class DockerComposeEnterprise {

    enum ServiceState {
        CREATED,
        STARTING,
        RUNNING,
        HEALTHY,
        UNHEALTHY,
        FAILED,
        STOPPED
    }

    enum DependencyCondition {
        SERVICE_STARTED,
        SERVICE_HEALTHY,
        SERVICE_COMPLETED_SUCCESSFULLY
    }

    enum RestartPolicy {
        NO,
        ALWAYS,
        ON_FAILURE,
        UNLESS_STOPPED
    }

    enum DeploymentState {
        CREATED,
        DEPLOYING,
        RUNNING,
        FAILED,
        STOPPED
    }

    static class ComposeException extends RuntimeException {
        ComposeException(String message) {
            super(message);
        }
    }

    static class ConfigurationException extends ComposeException {
        ConfigurationException(String message) {
            super(message);
        }
    }

    static class DependencyException extends ComposeException {
        DependencyException(String message) {
            super(message);
        }
    }

    static class DeploymentException extends ComposeException {
        DeploymentException(String message) {
            super(message);
        }
    }

    record PortMapping(int host, int container, String protocol) {
        PortMapping {
            if (host < 1 || host > 65535 ||
                container < 1 || container > 65535) {
                throw new ConfigurationException(
                    "Invalid port mapping"
                );
            }

            protocol = Objects.requireNonNull(protocol);

            if (!Set.of("tcp", "udp").contains(protocol)) {
                throw new ConfigurationException(
                    "Unsupported protocol"
                );
            }
        }
    }

    record VolumeMount(
        String source,
        String target,
        boolean readOnly
    ) {
        VolumeMount {
            if (source == null || source.isBlank() ||
                target == null || !target.startsWith("/") ||
                List.of(target.split("/")).contains("..")) {
                throw new ConfigurationException(
                    "Invalid volume mapping"
                );
            }
        }
    }

    record Dependency(
        String service,
        DependencyCondition condition
    ) {
        Dependency {
            Objects.requireNonNull(service);
            Objects.requireNonNull(condition);
        }
    }

    record HealthPolicy(
        String command,
        int intervalSeconds,
        int retries
    ) {
        HealthPolicy {
            if (command == null || command.isBlank() ||
                intervalSeconds < 1 || retries < 1) {
                throw new ConfigurationException(
                    "Invalid health policy"
                );
            }
        }
    }

    record ServiceDefinition(
        String name,
        String image,
        String command,
        Map<String, String> environment,
        List<PortMapping> ports,
        List<VolumeMount> volumes,
        Set<String> networks,
        List<Dependency> dependencies,
        HealthPolicy healthPolicy,
        RestartPolicy restartPolicy,
        int replicas
    ) {
        ServiceDefinition {
            if (name == null ||
                !name.matches("[a-zA-Z0-9][a-zA-Z0-9_.-]*")) {
                throw new ConfigurationException(
                    "Invalid service name"
                );
            }

            if (image == null || image.isBlank()) {
                throw new ConfigurationException(
                    name + ": image is required"
                );
            }

            if (replicas < 1) {
                throw new ConfigurationException(
                    "Replicas must be positive"
                );
            }

            environment = Map.copyOf(
                environment == null ? Map.of() : environment
            );

            ports = List.copyOf(
                ports == null ? List.of() : ports
            );

            volumes = List.copyOf(
                volumes == null ? List.of() : volumes
            );

            networks = Set.copyOf(
                networks == null ? Set.of() : networks
            );

            dependencies = List.copyOf(
                dependencies == null ? List.of() : dependencies
            );

            Objects.requireNonNull(restartPolicy);
        }
    }

    record DeploymentEvent(
        Instant timestamp,
        String service,
        String event,
        String details
    ) {}

    static final class ServiceRuntime {
        private final ServiceDefinition definition;
        private ServiceState state = ServiceState.CREATED;
        private int attempts;
        private String error;

        ServiceRuntime(ServiceDefinition definition) {
            this.definition = definition;
        }

        ServiceDefinition definition() {
            return definition;
        }

        ServiceState state() {
            return state;
        }

        int attempts() {
            return attempts;
        }

        String error() {
            return error;
        }

        void transition(ServiceState next) {
            if (!isAllowedTransition(state, next)) {
                throw new DeploymentException(
                    "Invalid transition: " + state + " -> " + next
                );
            }

            state = next;
        }

        private boolean isAllowedTransition(
            ServiceState current,
            ServiceState next
        ) {
            return switch (current) {
                case CREATED ->
                    Set.of(
                        ServiceState.STARTING,
                        ServiceState.STOPPED
                    ).contains(next);

                case STARTING ->
                    Set.of(
                        ServiceState.RUNNING,
                        ServiceState.HEALTHY,
                        ServiceState.FAILED,
                        ServiceState.STOPPED
                    ).contains(next);

                case RUNNING ->
                    Set.of(
                        ServiceState.UNHEALTHY,
                        ServiceState.FAILED,
                        ServiceState.STOPPED,
                        ServiceState.STARTING
                    ).contains(next);

                case HEALTHY ->
                    Set.of(
                        ServiceState.UNHEALTHY,
                        ServiceState.FAILED,
                        ServiceState.STOPPED,
                        ServiceState.STARTING
                    ).contains(next);

                case UNHEALTHY ->
                    Set.of(
                        ServiceState.FAILED,
                        ServiceState.STARTING,
                        ServiceState.STOPPED
                    ).contains(next);

                case FAILED ->
                    Set.of(
                        ServiceState.STARTING,
                        ServiceState.STOPPED
                    ).contains(next);

                case STOPPED ->
                    next == ServiceState.STARTING;
            };
        }

        void incrementAttempts() {
            attempts++;
        }

        void setError(String value) {
            error = value;
        }
    }

    interface DeploymentPolicy {
        boolean mayRestart(
            ServiceRuntime runtime,
            boolean manuallyStopped
        );
    }

    static final class DefaultDeploymentPolicy
        implements DeploymentPolicy {

        @Override
        public boolean mayRestart(
            ServiceRuntime runtime,
            boolean manuallyStopped
        ) {
            return switch (
                runtime.definition().restartPolicy()
            ) {
                case NO -> false;
                case ALWAYS -> true;
                case ON_FAILURE -> true;
                case UNLESS_STOPPED -> !manuallyStopped;
            };
        }
    }

    static final class ComposeProject {
        private final String projectName;

        private final Map<String, ServiceRuntime> services =
            new LinkedHashMap<>();

        private final Set<String> networks;
        private final Set<String> volumes;

        private final List<DeploymentEvent> events =
            new ArrayList<>();

        private final DeploymentPolicy restartPolicy =
            new DefaultDeploymentPolicy();

        private DeploymentState deploymentState =
            DeploymentState.CREATED;

        private boolean manuallyStopped;

        ComposeProject(
            String projectName,
            List<ServiceDefinition> definitions,
            Set<String> networks,
            Set<String> volumes
        ) {
            if (projectName == null || projectName.isBlank()) {
                throw new ConfigurationException(
                    "Project name is required"
                );
            }

            this.projectName = projectName;
            this.networks = Set.copyOf(networks);
            this.volumes = Set.copyOf(volumes);

            for (ServiceDefinition definition : definitions) {
                if (services.containsKey(definition.name())) {
                    throw new ConfigurationException(
                        "Duplicate service: " + definition.name()
                    );
                }

                services.put(
                    definition.name(),
                    new ServiceRuntime(definition)
                );
            }

            if (services.isEmpty()) {
                throw new ConfigurationException(
                    "At least one service is required"
                );
            }

            validate();
        }

        private void validate() {
            Set<String> hostPorts = new HashSet<>();

            for (ServiceRuntime runtime : services.values()) {
                ServiceDefinition definition =
                    runtime.definition();

                if (!networks.containsAll(definition.networks())) {
                    throw new ConfigurationException(
                        definition.name() +
                        " references an undefined network"
                    );
                }

                for (VolumeMount volume : definition.volumes()) {
                    if (!volumes.contains(volume.source())) {
                        throw new ConfigurationException(
                            "Undefined volume: " + volume.source()
                        );
                    }
                }

                for (PortMapping port : definition.ports()) {
                    String key = port.host() + "/" + port.protocol();

                    if (!hostPorts.add(key)) {
                        throw new ConfigurationException(
                            "Host port conflict: " + key
                        );
                    }
                }

                for (Dependency dependency :
                     definition.dependencies()) {

                    if (!services.containsKey(dependency.service())) {
                        throw new DependencyException(
                            "Unknown dependency: " +
                            dependency.service()
                        );
                    }

                    if (dependency.service().equals(definition.name())) {
                        throw new DependencyException(
                            "Self dependency is invalid"
                        );
                    }
                }
            }

            startupOrder();
        }

        private void record(
            String service,
            String event,
            String details
        ) {
            events.add(new DeploymentEvent(
                Instant.now(),
                service,
                event,
                details
            ));
        }

        List<String> startupOrder() {
            Map<String, Integer> indegree = new HashMap<>();
            Map<String, List<String>> children = new HashMap<>();

            for (String name : services.keySet()) {
                indegree.put(name, 0);
                children.put(name, new ArrayList<>());
            }

            for (ServiceRuntime runtime : services.values()) {
                String name = runtime.definition().name();

                for (Dependency dependency :
                     runtime.definition().dependencies()) {
                    indegree.merge(name, 1, Integer::sum);

                    children.get(dependency.service()).add(name);
                }
            }

            ArrayDeque<String> queue = new ArrayDeque<>();

            indegree.forEach((name, degree) -> {
                if (degree == 0) {
                    queue.add(name);
                }
            });

            List<String> result = new ArrayList<>();

            while (!queue.isEmpty()) {
                String current = queue.remove();
                result.add(current);

                for (String child : children.get(current)) {
                    int remaining = indegree.merge(
                        child,
                        -1,
                        Integer::sum
                    );

                    if (remaining == 0) {
                        queue.add(child);
                    }
                }
            }

            if (result.size() != services.size()) {
                throw new DependencyException(
                    "Circular service dependency detected"
                );
            }

            return List.copyOf(result);
        }

        private boolean dependencySatisfied(
            Dependency dependency
        ) {
            ServiceRuntime runtime =
                services.get(dependency.service());

            return switch (dependency.condition()) {
                case SERVICE_STARTED ->
                    Set.of(
                        ServiceState.RUNNING,
                        ServiceState.HEALTHY
                    ).contains(runtime.state());

                case SERVICE_HEALTHY ->
                    runtime.state() == ServiceState.HEALTHY;

                case SERVICE_COMPLETED_SUCCESSFULLY ->
                    runtime.state() == ServiceState.STOPPED;
            };
        }

        private void startService(String name) {
            ServiceRuntime runtime = services.get(name);

            if (runtime.state() == ServiceState.RUNNING ||
                runtime.state() == ServiceState.HEALTHY) {
                return;
            }

            for (Dependency dependency :
                 runtime.definition().dependencies()) {

                if (!dependencySatisfied(dependency)) {
                    throw new DeploymentException(
                        name + " cannot start because " +
                        dependency.service() +
                        " has not satisfied " +
                        dependency.condition()
                    );
                }
            }

            runtime.transition(ServiceState.STARTING);
            runtime.incrementAttempts();

            record(
                name,
                "starting",
                runtime.definition().image()
            );

            ServiceState finalState =
                runtime.definition().healthPolicy() == null
                ? ServiceState.RUNNING
                : ServiceState.HEALTHY;

            runtime.transition(finalState);

            record(name, "started", finalState.name());
        }

        void deploy() {
            if (deploymentState == DeploymentState.RUNNING) {
                return;
            }

            manuallyStopped = false;
            deploymentState = DeploymentState.DEPLOYING;

            record(projectName, "deployment-starting", "");

            try {
                for (String name : startupOrder()) {
                    startService(name);
                }

                deploymentState = DeploymentState.RUNNING;

                record(projectName, "deployment-completed", "");

            } catch (RuntimeException exception) {
                deploymentState = DeploymentState.FAILED;

                record(
                    projectName,
                    "deployment-failed",
                    exception.getMessage()
                );

                throw exception;
            }
        }

        boolean simulateFailure(
            String name,
            String reason
        ) {
            ServiceRuntime runtime = services.get(name);

            if (runtime == null) {
                throw new DeploymentException(
                    "Unknown service: " + name
                );
            }

            runtime.transition(ServiceState.FAILED);
            runtime.setError(reason);

            record(name, "failed", reason);

            if (!restartPolicy.mayRestart(
                runtime,
                manuallyStopped
            )) {
                return false;
            }

            runtime.transition(ServiceState.STARTING);
            runtime.incrementAttempts();

            ServiceState recovered =
                runtime.definition().healthPolicy() == null
                ? ServiceState.RUNNING
                : ServiceState.HEALTHY;

            runtime.transition(recovered);
            runtime.setError(null);

            record(name, "restarted", recovered.name());

            return true;
        }

        void shutdown() {
            manuallyStopped = true;

            List<String> order = new ArrayList<>(startupOrder());
            Collections.reverse(order);

            for (String name : order) {
                ServiceRuntime runtime = services.get(name);

                if (runtime.state() != ServiceState.STOPPED) {
                    runtime.transition(ServiceState.STOPPED);
                    record(name, "stopped", "");
                }
            }

            deploymentState = DeploymentState.STOPPED;

            record(projectName, "deployment-stopped", "");
        }

        Map<String, ServiceState> status() {
            return services.entrySet()
                .stream()
                .collect(Collectors.toUnmodifiableMap(
                    Map.Entry::getKey,
                    entry -> entry.getValue().state()
                ));
        }

        void printReport() {
            System.out.println("Project: " + projectName);
            System.out.println("Deployment: " + deploymentState);

            status().forEach((name, state) ->
                System.out.println(name + " -> " + state)
            );

            System.out.println("\nStartup order:");
            startupOrder().forEach(System.out::println);

            System.out.println("\nDeployment events:");

            events.forEach(event ->
                System.out.printf(
                    "%s | %s | %s | %s%n",
                    event.timestamp(),
                    event.service(),
                    event.event(),
                    event.details()
                )
            );
        }
    }

    private static ServiceDefinition service(
        String name,
        String image,
        Set<String> networks,
        List<Dependency> dependencies,
        List<PortMapping> ports,
        List<VolumeMount> volumes,
        boolean healthCheck,
        RestartPolicy restartPolicy
    ) {
        return new ServiceDefinition(
            name,
            image,
            "",
            Map.of(),
            ports,
            volumes,
            networks,
            dependencies,
            healthCheck
                ? new HealthPolicy("health-check-command", 10, 3)
                : null,
            restartPolicy,
            1
        );
    }

    public static void main(String[] args) {
        ServiceDefinition database = service(
            "database",
            "postgres:18",
            Set.of("backend"),
            List.of(),
            List.of(),
            List.of(
                new VolumeMount(
                    "database-data",
                    "/var/lib/postgresql/data",
                    false
                )
            ),
            true,
            RestartPolicy.UNLESS_STOPPED
        );

        ServiceDefinition cache = service(
            "cache",
            "redis:8",
            Set.of("backend"),
            List.of(),
            List.of(),
            List.of(),
            true,
            RestartPolicy.ALWAYS
        );

        ServiceDefinition api = service(
            "api",
            "inventory-api:1.0",
            Set.of("frontend", "backend"),
            List.of(
                new Dependency(
                    "database",
                    DependencyCondition.SERVICE_HEALTHY
                ),
                new Dependency(
                    "cache",
                    DependencyCondition.SERVICE_HEALTHY
                )
            ),
            List.of(new PortMapping(8000, 8000, "tcp")),
            List.of(),
            true,
            RestartPolicy.ON_FAILURE
        );

        ServiceDefinition web = service(
            "web",
            "inventory-web:1.0",
            Set.of("frontend"),
            List.of(
                new Dependency(
                    "api",
                    DependencyCondition.SERVICE_HEALTHY
                )
            ),
            List.of(new PortMapping(8080, 80, "tcp")),
            List.of(),
            false,
            RestartPolicy.UNLESS_STOPPED
        );

        ComposeProject project = new ComposeProject(
            "inventory-platform",
            List.of(database, cache, api, web),
            Set.of("frontend", "backend"),
            Set.of("database-data")
        );

        project.deploy();

        if (project.status().get("api") != ServiceState.HEALTHY) {
            throw new AssertionError("API is not healthy");
        }

        if (project.status().get("web") != ServiceState.RUNNING) {
            throw new AssertionError("Web service is not running");
        }

        boolean recovered = project.simulateFailure(
            "api",
            "Temporary database connection interruption"
        );

        if (!recovered ||
            project.status().get("api") != ServiceState.HEALTHY) {
            throw new AssertionError("API recovery failed");
        }

        project.printReport();
        project.shutdown();

        if (project.status().values().stream().anyMatch(
            state -> state != ServiceState.STOPPED
        )) {
            throw new AssertionError("Shutdown was incomplete");
        }

        // Validate rejection of a cyclic dependency graph.
        try {
            ServiceDefinition first = service(
                "first", "first:1",
                Set.of(), List.of(
                    new Dependency(
                        "second",
                        DependencyCondition.SERVICE_STARTED
                    )
                ),
                List.of(), List.of(), false, RestartPolicy.NO
            );

            ServiceDefinition second = service(
                "second", "second:1",
                Set.of(), List.of(
                    new Dependency(
                        "first",
                        DependencyCondition.SERVICE_STARTED
                    )
                ),
                List.of(), List.of(), false, RestartPolicy.NO
            );

            new ComposeProject(
                "invalid",
                List.of(first, second),
                Set.of(),
                Set.of()
            );

            throw new AssertionError(
                "Circular dependency was accepted"
            );

        } catch (DependencyException expected) {
            System.out.println(
                "\nCircular dependency validation passed."
            );
        }

        System.out.println(
            "All enterprise deployment tests passed."
        );
    }
}
