import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import java.time.Duration;
import java.time.Instant;

import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/*
 * Docker Enterprise Deployment Monitor
 *
 * Java 17
 *
 * Models:
 * - Service registration
 * - Container lifecycle
 * - Service dependencies
 * - Health monitoring
 * - Deployment policies
 * - Failure recovery
 * - Persistent storage requirements
 * - Network isolation
 * - Deployment reports
 *
 * Run:
 * javac DockerProject.java
 * java DockerProject
 */

public class DockerProject {

    enum ServiceType {
        FRONTEND,
        BACKEND,
        DATABASE,
        CACHE,
        WORKER
    }

    enum ServiceStatus {
        CREATED,
        STARTING,
        RUNNING,
        HEALTHY,
        UNHEALTHY,
        STOPPED,
        FAILED
    }

    enum NetworkScope {
        PUBLIC,
        INTERNAL,
        ISOLATED
    }

    enum HealthStatus {
        PASS,
        FAIL,
        UNKNOWN
    }

    record HealthResult(
        HealthStatus status,
        String message,
        Instant checkedAt
    ) {
        HealthResult {
            Objects.requireNonNull(status);
            Objects.requireNonNull(message);
            Objects.requireNonNull(checkedAt);
        }
    }

    record VolumeDefinition(
        String name,
        String mountPath,
        boolean persistent
    ) {
        VolumeDefinition {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Volume name is required."
                );
            }

            if (mountPath == null || !mountPath.startsWith("/")) {
                throw new IllegalArgumentException(
                    "Volume mount path must be absolute."
                );
            }
        }
    }

    record DeploymentPolicy(
        boolean requireHealthCheck,
        boolean requirePersistentDatabase,
        boolean prohibitPublicDatabase,
        int maximumRetries
    ) {
        DeploymentPolicy {
            if (maximumRetries < 0 || maximumRetries > 10) {
                throw new IllegalArgumentException(
                    "Retries must be between 0 and 10."
                );
            }
        }
    }

    static final class DeploymentException extends RuntimeException {
        DeploymentException(String message) {
            super(message);
        }
    }

    static final class ServiceDefinition {
        private final String name;
        private final ServiceType type;
        private final int port;
        private final NetworkScope network;
        private final Set<String> dependencies;
        private final boolean persistent;
        private final boolean healthCheckRequired;

        ServiceDefinition(
            String name,
            ServiceType type,
            int port,
            NetworkScope network,
            Set<String> dependencies,
            boolean persistent,
            boolean healthCheckRequired
        ) {
            if (name == null || !name.matches("[a-z][a-z0-9-]{0,62}")) {
                throw new IllegalArgumentException(
                    "Invalid service name."
                );
            }

            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException(
                    "Invalid container port."
                );
            }

            this.name = name;
            this.type = Objects.requireNonNull(type);
            this.port = port;
            this.network = Objects.requireNonNull(network);
            this.dependencies = Set.copyOf(dependencies);
            this.persistent = persistent;
            this.healthCheckRequired = healthCheckRequired;
        }

        String name() {
            return name;
        }

        ServiceType type() {
            return type;
        }

        int port() {
            return port;
        }

        NetworkScope network() {
            return network;
        }

        Set<String> dependencies() {
            return dependencies;
        }

        boolean persistent() {
            return persistent;
        }

        boolean healthCheckRequired() {
            return healthCheckRequired;
        }
    }

    static final class ServiceInstance {
        private final ServiceDefinition definition;

        private ServiceStatus status = ServiceStatus.CREATED;

        private HealthResult health = new HealthResult(
            HealthStatus.UNKNOWN,
            "Not checked",
            Instant.now()
        );

        private int restartAttempts;

        ServiceInstance(ServiceDefinition definition) {
            this.definition = definition;
        }

        void transition(ServiceStatus next) {
            Map<ServiceStatus, Set<ServiceStatus>> allowed =
                new EnumMap<>(ServiceStatus.class);

            allowed.put(
                ServiceStatus.CREATED,
                Set.of(ServiceStatus.STARTING, ServiceStatus.STOPPED)
            );

            allowed.put(
                ServiceStatus.STARTING,
                Set.of(
                    ServiceStatus.RUNNING,
                    ServiceStatus.FAILED,
                    ServiceStatus.STOPPED
                )
            );

            allowed.put(
                ServiceStatus.RUNNING,
                Set.of(
                    ServiceStatus.HEALTHY,
                    ServiceStatus.UNHEALTHY,
                    ServiceStatus.FAILED,
                    ServiceStatus.STOPPED
                )
            );

            allowed.put(
                ServiceStatus.HEALTHY,
                Set.of(
                    ServiceStatus.UNHEALTHY,
                    ServiceStatus.STOPPED
                )
            );

            allowed.put(
                ServiceStatus.UNHEALTHY,
                Set.of(
                    ServiceStatus.HEALTHY,
                    ServiceStatus.FAILED,
                    ServiceStatus.STOPPED
                )
            );

            allowed.put(
                ServiceStatus.FAILED,
                Set.of(ServiceStatus.STARTING, ServiceStatus.STOPPED)
            );

            allowed.put(
                ServiceStatus.STOPPED,
                Set.of(ServiceStatus.STARTING)
            );

            if (!allowed.getOrDefault(
                status,
                Collections.emptySet()
            ).contains(next)) {
                throw new DeploymentException(
                    "Invalid transition: " + definition.name()
                    + " " + status + " -> " + next
                );
            }

            status = next;
        }

        void recordHealth(HealthResult result) {
            health = Objects.requireNonNull(result);

            if (status == ServiceStatus.RUNNING) {
                transition(
                    result.status() == HealthStatus.PASS
                        ? ServiceStatus.HEALTHY
                        : ServiceStatus.UNHEALTHY
                );
            } else if (
                status == ServiceStatus.UNHEALTHY &&
                result.status() == HealthStatus.PASS
            ) {
                transition(ServiceStatus.HEALTHY);
            }
        }

        void incrementRestart() {
            restartAttempts++;
        }

        ServiceDefinition definition() {
            return definition;
        }

        ServiceStatus status() {
            return status;
        }

        HealthResult health() {
            return health;
        }

        int restartAttempts() {
            return restartAttempts;
        }
    }

    static final class DockerRegistry {
        private final Map<String, ServiceInstance> services =
            new HashMap<>();

        private final List<VolumeDefinition> volumes =
            new ArrayList<>();

        void register(ServiceDefinition definition) {
            Objects.requireNonNull(definition);

            if (services.containsKey(definition.name())) {
                throw new DeploymentException(
                    "Duplicate service: " + definition.name()
                );
            }

            services.put(
                definition.name(),
                new ServiceInstance(definition)
            );
        }

        void addVolume(VolumeDefinition volume) {
            if (volumes.stream().anyMatch(
                existing -> existing.name().equals(volume.name())
            )) {
                throw new DeploymentException(
                    "Duplicate volume: " + volume.name()
                );
            }

            volumes.add(volume);
        }

        ServiceInstance get(String name) {
            ServiceInstance service = services.get(name);

            if (service == null) {
                throw new DeploymentException(
                    "Unknown service: " + name
                );
            }

            return service;
        }

        List<ServiceInstance> all() {
            return List.copyOf(services.values());
        }

        List<VolumeDefinition> volumes() {
            return List.copyOf(volumes);
        }

        List<String> startupOrder() {
            Map<String, Integer> indegree = new HashMap<>();
            Map<String, List<String>> adjacency = new HashMap<>();

            services.keySet().forEach(
                name -> indegree.put(name, 0)
            );

            for (ServiceInstance instance : services.values()) {
                String name = instance.definition().name();

                for (String dependency :
                    instance.definition().dependencies()) {

                    if (!services.containsKey(dependency)) {
                        throw new DeploymentException(
                            "Missing dependency: " + dependency
                        );
                    }

                    adjacency.computeIfAbsent(
                        dependency,
                        ignored -> new ArrayList<>()
                    ).add(name);

                    indegree.merge(name, 1, Integer::sum);
                }
            }

            List<String> ready = new ArrayList<>();

            indegree.forEach((name, degree) -> {
                if (degree == 0) ready.add(name);
            });

            Collections.sort(ready);

            List<String> result = new ArrayList<>();

            while (!ready.isEmpty()) {
                String current = ready.remove(0);
                result.add(current);

                for (String dependent :
                    adjacency.getOrDefault(
                        current,
                        Collections.emptyList()
                    )) {

                    int remaining = indegree.merge(
                        dependent,
                        -1,
                        Integer::sum
                    );

                    if (remaining == 0) {
                        ready.add(dependent);
                        Collections.sort(ready);
                    }
                }
            }

            if (result.size() != services.size()) {
                throw new DeploymentException(
                    "Circular dependency detected."
                );
            }

            return List.copyOf(result);
        }

        void validate(DeploymentPolicy policy) {
            startupOrder();

            for (ServiceInstance instance : services.values()) {
                ServiceDefinition definition = instance.definition();

                if (
                    policy.prohibitPublicDatabase() &&
                    definition.type() == ServiceType.DATABASE &&
                    definition.network() == NetworkScope.PUBLIC
                ) {
                    throw new DeploymentException(
                        "Database cannot use a public network."
                    );
                }

                if (
                    policy.requireHealthCheck() &&
                    !definition.healthCheckRequired()
                ) {
                    throw new DeploymentException(
                        "Missing health check: " + definition.name()
                    );
                }

                if (
                    definition.type() == ServiceType.DATABASE &&
                    policy.requirePersistentDatabase() &&
                    (!definition.persistent() ||
                    volumes.stream().noneMatch(VolumeDefinition::persistent))
                ) {
                    throw new DeploymentException(
                        "Database persistence requirement not satisfied."
                    );
                }
            }
        }
    }

    static final class HealthMonitor {
        private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

        HealthResult checkHttp(URI endpoint) {
            try {
                HttpRequest request = HttpRequest.newBuilder(endpoint)
                    .timeout(Duration.ofSeconds(5))
                    .GET()
                    .build();

                HttpResponse<String> response = client.send(
                    request,
                    HttpResponse.BodyHandlers.ofString()
                );

                return new HealthResult(
                    response.statusCode() >= 200 &&
                    response.statusCode() < 300
                        ? HealthStatus.PASS
                        : HealthStatus.FAIL,
                    "HTTP " + response.statusCode(),
                    Instant.now()
                );

            } catch (Exception exception) {
                return new HealthResult(
                    HealthStatus.FAIL,
                    "Health request failed",
                    Instant.now()
                );
            }
        }
    }

    static final class DeploymentService {
        private final DockerRegistry registry;
        private final DeploymentPolicy policy;

        DeploymentService(
            DockerRegistry registry,
            DeploymentPolicy policy
        ) {
            this.registry = registry;
            this.policy = policy;
        }

        void deploy() {
            registry.validate(policy);

            System.out.println("\nDEPLOYMENT PLAN");

            for (String name : registry.startupOrder()) {
                ServiceInstance instance = registry.get(name);

                boolean dependenciesHealthy =
                    instance.definition().dependencies().stream()
                        .allMatch(dependency ->
                            registry.get(dependency).status()
                                == ServiceStatus.HEALTHY
                        );

                if (!dependenciesHealthy) {
                    throw new DeploymentException(
                        "Dependency unavailable for " + name
                    );
                }

                instance.transition(ServiceStatus.STARTING);
                instance.transition(ServiceStatus.RUNNING);

                // In production, Docker Engine health status is obtained
                // from the Docker API rather than simulated here.
                instance.recordHealth(new HealthResult(
                    HealthStatus.PASS,
                    "Simulated deployment health check passed",
                    Instant.now()
                ));

                System.out.println(
                    name + " -> " + instance.status()
                );
            }
        }

        void report() {
            System.out.println("\nENTERPRISE DEPLOYMENT REPORT");

            for (ServiceInstance instance : registry.all()) {
                System.out.printf(
                    "%-15s %-12s %-12s Restarts=%d%n",
                    instance.definition().name(),
                    instance.status(),
                    instance.health().status(),
                    instance.restartAttempts()
                );
            }

            System.out.println(
                "Persistent volumes: " + registry.volumes().size()
            );
        }
    }

    public static void main(String[] args) {
        try {
            DockerRegistry registry = new DockerRegistry();

            registry.register(new ServiceDefinition(
                "database",
                ServiceType.DATABASE,
                5432,
                NetworkScope.INTERNAL,
                Set.of(),
                true,
                true
            ));

            registry.register(new ServiceDefinition(
                "backend",
                ServiceType.BACKEND,
                8000,
                NetworkScope.INTERNAL,
                Set.of("database"),
                false,
                true
            ));

            registry.register(new ServiceDefinition(
                "frontend",
                ServiceType.FRONTEND,
                3000,
                NetworkScope.PUBLIC,
                Set.of("backend"),
                false,
                true
            ));

            registry.addVolume(new VolumeDefinition(
                "postgres_data",
                "/var/lib/postgresql/data",
                true
            ));

            DeploymentPolicy policy = new DeploymentPolicy(
                true,
                true,
                true,
                3
            );

            DeploymentService deployment = new DeploymentService(
                registry,
                policy
            );

            deployment.deploy();
            deployment.report();

        } catch (DeploymentException | IllegalArgumentException error) {
            System.err.println(
                "DEPLOYMENT FAILED: " + error.getMessage()
            );

            System.exit(1);
        }
    }
}
