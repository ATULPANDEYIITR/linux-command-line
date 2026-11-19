import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

/**
 * Docker Networking Enterprise Governance Model.
 *
 * Java 17.
 *
 * Models network configuration, service discovery, bridge connectivity,
 * host networking, port publishing, network segmentation, lifecycle,
 * and enterprise network policies.
 */
public class DockerNetworkingEnterprise {

    enum NetworkMode {
        BRIDGE,
        HOST,
        NONE
    }

    enum Protocol {
        TCP,
        UDP
    }

    enum DecisionStatus {
        ALLOWED,
        DENIED
    }

    static class NetworkException extends RuntimeException {
        NetworkException(String message) {
            super(message);
        }
    }

    record Decision(
        DecisionStatus status,
        String source,
        String destination,
        int destinationPort,
        String reason,
        Instant evaluatedAt
    ) {
        Decision {
            Objects.requireNonNull(status);
            Objects.requireNonNull(source);
            Objects.requireNonNull(destination);
            Objects.requireNonNull(reason);
            Objects.requireNonNull(evaluatedAt);
        }
    }

    record PortBinding(
        String hostAddress,
        int hostPort,
        String containerName,
        int containerPort,
        Protocol protocol
    ) {
        PortBinding {
            validatePort(hostPort);
            validatePort(containerPort);

            Objects.requireNonNull(hostAddress);
            Objects.requireNonNull(containerName);
            Objects.requireNonNull(protocol);
        }
    }

    record NetworkPolicy(
        String networkName,
        boolean internal,
        boolean allowInterNetworkRouting,
        Set<String> permittedServices
    ) {
        NetworkPolicy {
            Objects.requireNonNull(networkName);

            permittedServices = Set.copyOf(permittedServices);
        }
    }

    static void validatePort(int port) {
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException(
                "Port must be between 1 and 65535."
            );
        }
    }

    static final class NetworkSegment {

        private final String name;
        private final String subnet;
        private final String gateway;
        private final boolean internal;

        private final Map<String, String> addresses =
            new LinkedHashMap<>();

        private final Set<String> members =
            new TreeSet<>();

        private long nextAddress;

        NetworkSegment(
            String name,
            String subnet,
            String gateway,
            boolean internal
        ) {
            if (
                name == null || name.isBlank()
                || subnet == null || subnet.isBlank()
            ) {
                throw new IllegalArgumentException(
                    "Network name and subnet are required."
                );
            }

            this.name = name;
            this.subnet = subnet;
            this.gateway = gateway;
            this.internal = internal;

            String[] parts = subnet.split("/");

            if (parts.length != 2) {
                throw new IllegalArgumentException("Invalid CIDR.");
            }

            long base = parseIPv4(parts[0]);
            int prefix = Integer.parseInt(parts[1]);

            if (prefix < 16 || prefix > 29) {
                throw new IllegalArgumentException(
                    "Unsupported IPv4 prefix."
                );
            }

            long mask = (0xFFFFFFFFL << (32 - prefix))
                & 0xFFFFFFFFL;

            long networkAddress = base & mask;

            this.nextAddress = networkAddress + 2;

            long gatewayValue = parseIPv4(gateway);

            if (
                (gatewayValue & mask) != networkAddress
            ) {
                throw new IllegalArgumentException(
                    "Gateway is outside subnet."
                );
            }
        }

        private static long parseIPv4(String address) {
            String[] parts = address.split("\\.");

            if (parts.length != 4) {
                throw new IllegalArgumentException(
                    "Invalid IPv4 address."
                );
            }

            long result = 0;

            for (String part : parts) {
                int value = Integer.parseInt(part);

                if (value < 0 || value > 255) {
                    throw new IllegalArgumentException(
                        "Invalid IPv4 octet."
                    );
                }

                result = (result << 8) | value;
            }

            return result;
        }

        synchronized String attach(String containerName) {
            if (members.contains(containerName)) {
                throw new NetworkException(
                    "Container already belongs to network."
                );
            }

            if (nextAddress > 0xFFFFFFFFL) {
                throw new NetworkException(
                    "Address allocation failed."
                );
            }

            String address = String.format(
                "%d.%d.%d.%d",
                (nextAddress >>> 24) & 255,
                (nextAddress >>> 16) & 255,
                (nextAddress >>> 8) & 255,
                nextAddress & 255
            );

            nextAddress++;

            addresses.put(containerName, address);
            members.add(containerName);

            return address;
        }

        synchronized void detach(String containerName) {
            if (!members.remove(containerName)) {
                throw new NetworkException(
                    "Container is not attached."
                );
            }

            addresses.remove(containerName);
        }

        boolean contains(String containerName) {
            return members.contains(containerName);
        }

        Optional<String> addressOf(String containerName) {
            return Optional.ofNullable(addresses.get(containerName));
        }

        String name() {
            return name;
        }

        String subnet() {
            return subnet;
        }

        String gateway() {
            return gateway;
        }

        boolean internal() {
            return internal;
        }

        Set<String> members() {
            return Collections.unmodifiableSet(members);
        }
    }

    static final class Container {

        private final String id;
        private final String name;
        private final String image;
        private final NetworkMode mode;

        private final Set<Integer> exposedPorts;
        private final Map<String, String> networks =
            new LinkedHashMap<>();

        private boolean running = true;

        Container(
            String id,
            String name,
            String image,
            NetworkMode mode,
            Set<Integer> ports
        ) {
            if (
                id == null || id.isBlank()
                || name == null || name.isBlank()
                || image == null || image.isBlank()
            ) {
                throw new IllegalArgumentException(
                    "Container properties are required."
                );
            }

            this.id = id;
            this.name = name;
            this.image = image;
            this.mode = Objects.requireNonNull(mode);

            this.exposedPorts = Set.copyOf(ports);

            this.exposedPorts.forEach(
                DockerNetworkingEnterprise::validatePort
            );
        }

        String name() {
            return name;
        }

        NetworkMode mode() {
            return mode;
        }

        boolean running() {
            return running;
        }

        Set<Integer> exposedPorts() {
            return exposedPorts;
        }

        Map<String, String> networks() {
            return Collections.unmodifiableMap(networks);
        }
    }

    interface NetworkAuthorizationService {
        Decision evaluate(
            Container source,
            Container destination,
            int port,
            Map<String, NetworkSegment> networks,
            NetworkPolicy policy
        );
    }

    static final class DefaultNetworkAuthorizationService
        implements NetworkAuthorizationService {

        @Override
        public Decision evaluate(
            Container source,
            Container destination,
            int port,
            Map<String, NetworkSegment> networks,
            NetworkPolicy policy
        ) {
            validatePort(port);

            if (!source.running() || !destination.running()) {
                return deny(
                    source.name(),
                    destination.name(),
                    port,
                    "A container is stopped."
                );
            }

            if (source.name().equals(destination.name())) {
                return allow(
                    source.name(),
                    destination.name(),
                    port,
                    "Same container."
                );
            }

            if (
                source.mode() == NetworkMode.NONE
                || destination.mode() == NetworkMode.NONE
            ) {
                return deny(
                    source.name(),
                    destination.name(),
                    port,
                    "None networking prevents connectivity."
                );
            }

            if (
                source.mode() == NetworkMode.HOST
                && destination.mode() == NetworkMode.HOST
            ) {
                return allow(
                    source.name(),
                    destination.name(),
                    port,
                    "Shared host network namespace."
                );
            }

            if (
                source.mode() != NetworkMode.BRIDGE
                || destination.mode() != NetworkMode.BRIDGE
            ) {
                return deny(
                    source.name(),
                    destination.name(),
                    port,
                    "No compatible bridge network."
                );
            }

            for (String networkName : source.networks().keySet()) {
                if (
                    destination.networks().containsKey(networkName)
                    && networks.get(networkName).contains(source.name())
                    && networks.get(networkName).contains(destination.name())
                    && destination.exposedPorts().contains(port)
                ) {
                    return allow(
                        source.name(),
                        destination.name(),
                        port,
                        "Shared bridge network: " + networkName
                    );
                }
            }

            return deny(
                source.name(),
                destination.name(),
                port,
                "Network isolation or port policy denied access."
            );
        }

        private Decision allow(
            String source,
            String target,
            int port,
            String reason
        ) {
            return new Decision(
                DecisionStatus.ALLOWED,
                source,
                target,
                port,
                reason,
                Instant.now()
            );
        }

        private Decision deny(
            String source,
            String target,
            int port,
            String reason
        ) {
            return new Decision(
                DecisionStatus.DENIED,
                source,
                target,
                port,
                reason,
                Instant.now()
            );
        }
    }

    static final class NetworkRegistry {

        private final Map<String, NetworkSegment> networks =
            new LinkedHashMap<>();

        private final Map<String, Container> containers =
            new LinkedHashMap<>();

        private final Map<String, PortBinding> bindings =
            new LinkedHashMap<>();

        private final AtomicLong eventCounter = new AtomicLong();

        private final List<String> auditLog =
            new ArrayList<>();

        synchronized void createNetwork(NetworkSegment network) {
            if (networks.containsKey(network.name())) {
                throw new NetworkException(
                    "Network already exists."
                );
            }

            networks.put(network.name(), network);

            audit("NETWORK_CREATED:" + network.name());
        }

        synchronized void registerContainer(
            Container container,
            String networkName
        ) {
            if (containers.containsKey(container.name())) {
                throw new NetworkException(
                    "Container name already registered."
                );
            }

            if (
                container.mode() == NetworkMode.BRIDGE
                && networkName == null
            ) {
                throw new NetworkException(
                    "Bridge mode requires a network."
                );
            }

            if (
                container.mode() != NetworkMode.BRIDGE
                && networkName != null
            ) {
                throw new NetworkException(
                    "Host and none modes cannot join bridge networks."
                );
            }

            if (networkName != null) {
                NetworkSegment network = requireNetwork(networkName);

                String address = network.attach(container.name());

                container.networks.put(networkName, address);
            }

            containers.put(container.name(), container);

            audit("CONTAINER_REGISTERED:" + container.name());
        }

        synchronized String connect(
            String containerName,
            String networkName
        ) {
            Container container = requireRunning(containerName);

            if (container.mode() != NetworkMode.BRIDGE) {
                throw new NetworkException(
                    "Only bridge containers can join user networks."
                );
            }

            NetworkSegment network = requireNetwork(networkName);

            String address = network.attach(containerName);

            container.networks.put(networkName, address);

            audit(
                "CONTAINER_CONNECTED:"
                + containerName + ":" + networkName
            );

            return address;
        }

        synchronized void disconnect(
            String containerName,
            String networkName
        ) {
            Container container = requireRunning(containerName);
            NetworkSegment network = requireNetwork(networkName);

            network.detach(containerName);
            container.networks.remove(networkName);

            audit(
                "CONTAINER_DISCONNECTED:"
                + containerName + ":" + networkName
            );
        }

        synchronized String resolve(
            String sourceName,
            String targetName,
            String networkName
        ) {
            Container source = requireRunning(sourceName);
            Container target = requireRunning(targetName);

            NetworkSegment network = requireNetwork(networkName);

            if (
                !source.networks.containsKey(networkName)
                || !target.networks.containsKey(networkName)
            ) {
                throw new NetworkException(
                    "Service discovery denied."
                );
            }

            if (!network.contains(targetName)) {
                throw new NetworkException(
                    "Target DNS record unavailable."
                );
            }

            return target.networks.get(networkName);
        }

        synchronized void publish(
            String containerName,
            String hostAddress,
            int hostPort,
            int containerPort,
            Protocol protocol
        ) {
            Container container = requireRunning(containerName);

            if (container.mode() != NetworkMode.BRIDGE) {
                throw new NetworkException(
                    "Publishing requires bridge networking."
                );
            }

            validatePort(hostPort);
            validatePort(containerPort);

            if (!container.exposedPorts().contains(containerPort)) {
                throw new NetworkException(
                    "Destination port is not exposed."
                );
            }

            PortBinding candidate = new PortBinding(
                hostAddress,
                hostPort,
                containerName,
                containerPort,
                protocol
            );

            for (PortBinding existing : bindings.values()) {
                boolean addressConflict =
                    existing.hostAddress().equals("0.0.0.0")
                    || hostAddress.equals("0.0.0.0")
                    || existing.hostAddress().equals(hostAddress);

                if (
                    addressConflict
                    && existing.hostPort() == hostPort
                    && existing.protocol() == protocol
                ) {
                    throw new NetworkException(
                        "Host port is already allocated."
                    );
                }
            }

            String key = hostAddress + ":" + hostPort + "/" + protocol;

            bindings.put(key, candidate);

            audit("PORT_PUBLISHED:" + key);
        }

        synchronized boolean externalAccess(
            int hostPort,
            int containerPort,
            Protocol protocol
        ) {
            validatePort(hostPort);
            validatePort(containerPort);

            return bindings.values().stream().anyMatch(binding -> {
                Container container =
                    containers.get(binding.containerName());

                return container != null
                    && container.running()
                    && binding.hostPort() == hostPort
                    && binding.containerPort() == containerPort
                    && binding.protocol() == protocol;
            });
        }

        synchronized void stop(String name) {
            Container container = requireRunning(name);

            for (String networkName :
                new ArrayList<>(container.networks.keySet())) {

                networks.get(networkName).detach(name);
            }

            container.networks.clear();
            container.running = false;

            bindings.entrySet().removeIf(
                entry -> entry.getValue().containerName().equals(name)
            );

            audit("CONTAINER_STOPPED:" + name);
        }

        synchronized Container requireRunning(String name) {
            Container container = containers.get(name);

            if (container == null) {
                throw new NetworkException(
                    "Unknown container: " + name
                );
            }

            if (!container.running()) {
                throw new NetworkException(
                    "Container is stopped: " + name
                );
            }

            return container;
        }

        private NetworkSegment requireNetwork(String name) {
            NetworkSegment network = networks.get(name);

            if (network == null) {
                throw new NetworkException(
                    "Unknown network: " + name
                );
            }

            return network;
        }

        synchronized void audit(String event) {
            auditLog.add(
                eventCounter.incrementAndGet()
                + "|" + Instant.now()
                + "|" + event
            );
        }

        synchronized List<String> auditLog() {
            return List.copyOf(auditLog);
        }

        synchronized void printReport() {
            System.out.println("\nNETWORK REGISTRY");

            networks.values().forEach(network -> {
                System.out.println(
                    network.name()
                    + " | " + network.subnet()
                    + " | internal=" + network.internal()
                );

                network.members().forEach(member ->
                    System.out.println(
                        "  " + member + " -> "
                        + network.addressOf(member).orElse("")
                    )
                );
            });

            System.out.println("\nCONTAINER REGISTRY");

            containers.values().forEach(container ->
                System.out.println(
                    container.name()
                    + " | mode=" + container.mode()
                    + " | running=" + container.running()
                    + " | networks=" + container.networks()
                )
            );
        }
    }

    static final class NetworkPolicyService {

        private final NetworkRegistry registry;

        private final NetworkAuthorizationService authorization;

        NetworkPolicyService(NetworkRegistry registry) {
            this.registry = registry;

            this.authorization =
                new DefaultNetworkAuthorizationService();
        }

        Decision evaluate(
            String sourceName,
            String targetName,
            int port,
            NetworkPolicy policy
        ) {
            Container source =
                registry.requireRunning(sourceName);

            Container target =
                registry.requireRunning(targetName);

            Decision decision = authorization.evaluate(
                source,
                target,
                port,
                getNetworks(),
                policy
            );

            registry.audit(
                "CONNECTIVITY_" + decision.status()
                + ":" + sourceName
                + ":" + targetName
                + ":" + port
            );

            return decision;
        }

        private Map<String, NetworkSegment> getNetworks() {
            // Policy evaluation uses the same network registry.
            return NetworkAccess.networks(registry);
        }
    }

    /**
     * Controlled access to the registry's network state.
     */
    static final class NetworkAccess {
        private NetworkAccess() {}

        static Map<String, NetworkSegment> networks(
            NetworkRegistry registry
        ) {
            return Collections.unmodifiableMap(
                registry.networks
            );
        }
    }

    public static void main(String[] args) {
        try {
            NetworkRegistry registry = new NetworkRegistry();

            registry.createNetwork(
                new NetworkSegment(
                    "frontend-net",
                    "172.20.0.0/24",
                    "172.20.0.1",
                    false
                )
            );

            registry.createNetwork(
                new NetworkSegment(
                    "backend-net",
                    "172.21.0.0/24",
                    "172.21.0.1",
                    true
                )
            );

            registry.registerContainer(
                new Container(
                    "c001",
                    "frontend",
                    "nginx:stable",
                    NetworkMode.BRIDGE,
                    Set.of(80)
                ),
                "frontend-net"
            );

            registry.registerContainer(
                new Container(
                    "c002",
                    "api",
                    "python:3.13-slim",
                    NetworkMode.BRIDGE,
                    Set.of(8000)
                ),
                "frontend-net"
            );

            registry.connect("api", "backend-net");

            registry.registerContainer(
                new Container(
                    "c003",
                    "database",
                    "postgres:18",
                    NetworkMode.BRIDGE,
                    Set.of(5432)
                ),
                "backend-net"
            );

            registry.registerContainer(
                new Container(
                    "c004",
                    "host-monitor",
                    "monitor:latest",
                    NetworkMode.HOST,
                    Set.of(9090)
                ),
                null
            );

            System.out.println(
                "Database DNS: "
                + registry.resolve(
                    "api",
                    "database",
                    "backend-net"
                )
            );

            NetworkPolicyService policyService =
                new NetworkPolicyService(registry);

            NetworkPolicy policy = new NetworkPolicy(
                "enterprise-default",
                true,
                false,
                Set.of("api", "database")
            );

            List<Decision> decisions = List.of(
                policyService.evaluate(
                    "frontend", "api", 8000, policy
                ),
                policyService.evaluate(
                    "api", "database", 5432, policy
                ),
                policyService.evaluate(
                    "frontend", "database", 5432, policy
                )
            );

            System.out.println("\nCONNECTIVITY DECISIONS");

            decisions.forEach(decision ->
                System.out.println(
                    decision.source()
                    + " -> " + decision.destination()
                    + ":" + decision.destinationPort()
                    + " = " + decision.status()
                    + " | " + decision.reason()
                )
            );

            registry.publish(
                "frontend",
                "127.0.0.1",
                8080,
                80,
                Protocol.TCP
            );

            System.out.println(
                "\nExternal access: "
                + registry.externalAccess(
                    8080,
                    80,
                    Protocol.TCP
                )
            );

            if (
                decisions.get(0).status()
                    != DecisionStatus.ALLOWED
                || decisions.get(1).status()
                    != DecisionStatus.ALLOWED
                || decisions.get(2).status()
                    != DecisionStatus.DENIED
            ) {
                throw new NetworkException(
                    "Connectivity policy verification failed."
                );
            }

            registry.printReport();

            System.out.println("\nAUDIT EVENTS");

            registry.auditLog().forEach(System.out::println);

            System.out.println("\nALL NETWORK TESTS PASSED");

        } catch (Exception exception) {
            System.err.println(
                "NETWORK ERROR: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
