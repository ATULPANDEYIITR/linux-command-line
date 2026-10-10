import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/**
 * Enterprise-oriented cloud infrastructure governance model.
 *
 * The design separates:
 * - resource state
 * - network policy
 * - identity permissions
 * - storage attachment
 * - infrastructure-level validation
 *
 * Java records are used for immutable configuration values, while domain
 * classes own state transitions and reject invalid operations.
 */
public class CloudInfrastructure {

    enum InstanceState {
        STOPPED,
        RUNNING,
        TERMINATED
    }

    enum Protocol {
        TCP,
        UDP,
        ALL
    }

    enum Permission {
        COMPUTE,
        NETWORK,
        STORAGE,
        SECURITY,
        STORAGE_READ
    }

    record NetworkRule(
        Protocol protocol,
        Integer port,
        String sourceCidr
    ) {
        NetworkRule {
            Objects.requireNonNull(protocol);
            Objects.requireNonNull(sourceCidr);

            if (port != null && (port < 1 || port > 65535)) {
                throw new IllegalArgumentException(
                    "Port must be between 1 and 65535"
                );
            }
        }

        boolean matches(
            Protocol requestedProtocol,
            int requestedPort,
            String sourceIp
        ) {
            boolean protocolMatches =
                protocol == Protocol.ALL ||
                protocol == requestedProtocol;

            boolean portMatches =
                port == null ||
                port == requestedPort;

            boolean sourceMatches =
                sourceCidr.equals("0.0.0.0/0") ||
                sourceIp.startsWith(
                    sourceCidr.substring(
                        0,
                        sourceCidr.lastIndexOf('.') + 1
                    )
                );

            return protocolMatches
                && portMatches
                && sourceMatches;
        }
    }

    static final class SecurityGroup {
        private final String name;
        private final List<NetworkRule> inboundRules =
            new ArrayList<>();

        SecurityGroup(String name) {
            this.name = Objects.requireNonNull(name);
        }

        void addInboundRule(NetworkRule rule) {
            inboundRules.add(rule);
        }

        boolean permits(
            Protocol protocol,
            int port,
            String sourceIp
        ) {
            return inboundRules.stream()
                .anyMatch(rule ->
                    rule.matches(
                        protocol,
                        port,
                        sourceIp
                    )
                );
        }

        String name() {
            return name;
        }
    }

    static final class VirtualNetwork {
        private final String name;
        private final String cidr;
        private final Map<String, String> subnets =
            new HashMap<>();

        VirtualNetwork(String name, String cidr) {
            this.name = Objects.requireNonNull(name);
            this.cidr = Objects.requireNonNull(cidr);
        }

        void addSubnet(String name, String cidr) {
            if (subnets.containsKey(name)) {
                throw new IllegalArgumentException(
                    "Subnet already exists: " + name
                );
            }

            subnets.put(name, cidr);
        }

        String name() {
            return name;
        }

        String cidr() {
            return cidr;
        }

        Map<String, String> subnets() {
            return Map.copyOf(subnets);
        }
    }

    static final class ComputeInstance {
        private final String id;
        private final String hostname;
        private final String subnet;
        private final String privateIp;
        private final SecurityGroup securityGroup;
        private final Set<String> volumes =
            new HashSet<>();

        private InstanceState state =
            InstanceState.STOPPED;

        ComputeInstance(
            String id,
            String hostname,
            String subnet,
            String privateIp,
            SecurityGroup securityGroup
        ) {
            this.id = Objects.requireNonNull(id);
            this.hostname = Objects.requireNonNull(hostname);
            this.subnet = Objects.requireNonNull(subnet);
            this.privateIp = Objects.requireNonNull(privateIp);
            this.securityGroup =
                Objects.requireNonNull(securityGroup);
        }

        void start() {
            if (state == InstanceState.TERMINATED) {
                throw new IllegalStateException(
                    "A terminated instance cannot start"
                );
            }

            state = InstanceState.RUNNING;
        }

        void stop() {
            if (state == InstanceState.TERMINATED) {
                throw new IllegalStateException(
                    "A terminated instance cannot stop"
                );
            }

            state = InstanceState.STOPPED;
        }

        void terminate() {
            state = InstanceState.TERMINATED;
        }

        void attachVolume(String volumeName) {
            if (state == InstanceState.TERMINATED) {
                throw new IllegalStateException(
                    "Terminated instances cannot receive volumes"
                );
            }

            volumes.add(volumeName);
        }

        boolean isRunning() {
            return state == InstanceState.RUNNING;
        }

        String id() {
            return id;
        }

        String hostname() {
            return hostname;
        }

        String subnet() {
            return subnet;
        }

        String privateIp() {
            return privateIp;
        }

        SecurityGroup securityGroup() {
            return securityGroup;
        }

        InstanceState state() {
            return state;
        }

        Set<String> volumes() {
            return Set.copyOf(volumes);
        }
    }

    static final class BlockVolume {
        private final String name;
        private final long sizeGb;
        private final boolean encrypted;
        private Optional<String> attachedInstance =
            Optional.empty();

        BlockVolume(
            String name,
            long sizeGb,
            boolean encrypted
        ) {
            if (sizeGb <= 0) {
                throw new IllegalArgumentException(
                    "Volume size must be positive"
                );
            }

            this.name = Objects.requireNonNull(name);
            this.sizeGb = sizeGb;
            this.encrypted = encrypted;
        }

        void attach(String instanceId) {
            if (attachedInstance.isPresent()) {
                throw new IllegalStateException(
                    "Volume is already attached"
                );
            }

            if (!encrypted) {
                throw new SecurityException(
                    "Encrypted block storage is required"
                );
            }

            attachedInstance = Optional.of(instanceId);
        }

        String name() {
            return name;
        }

        long sizeGb() {
            return sizeGb;
        }

        boolean encrypted() {
            return encrypted;
        }

        Optional<String> attachedInstance() {
            return attachedInstance;
        }
    }

    static final class Identity {
        private final String username;
        private final Set<Permission> permissions =
            EnumSet.noneOf(Permission.class);

        Identity(
            String username,
            Permission... permissions
        ) {
            this.username = Objects.requireNonNull(username);

            for (Permission permission : permissions) {
                this.permissions.add(permission);
            }
        }

        boolean can(Permission permission) {
            return permissions.contains(permission);
        }

        String username() {
            return username;
        }
    }

    static final class CloudPolicy {
        boolean canManageCompute(Identity identity) {
            return identity.can(Permission.COMPUTE);
        }

        boolean canManageNetwork(Identity identity) {
            return identity.can(Permission.NETWORK);
        }

        boolean canReadStorage(Identity identity) {
            return identity.can(Permission.STORAGE)
                || identity.can(Permission.STORAGE_READ);
        }
    }

    private final Map<String, VirtualNetwork> networks =
        new HashMap<>();

    private final Map<String, SecurityGroup> securityGroups =
        new HashMap<>();

    private final Map<String, ComputeInstance> instances =
        new HashMap<>();

    private final Map<String, BlockVolume> volumes =
        new HashMap<>();

    private final CloudPolicy policy =
        new CloudPolicy();

    void addNetwork(VirtualNetwork network) {
        if (networks.putIfAbsent(
            network.name(),
            network
        ) != null) {
            throw new IllegalArgumentException(
                "Network already exists"
            );
        }
    }

    void addSecurityGroup(SecurityGroup group) {
        if (securityGroups.putIfAbsent(
            group.name(),
            group
        ) != null) {
            throw new IllegalArgumentException(
                "Security group already exists"
            );
        }
    }

    void addInstance(ComputeInstance instance) {
        if (instances.putIfAbsent(
            instance.id(),
            instance
        ) != null) {
            throw new IllegalArgumentException(
                "Instance already exists"
            );
        }
    }

    void addVolume(BlockVolume volume) {
        if (volumes.putIfAbsent(
            volume.name(),
            volume
        ) != null) {
            throw new IllegalArgumentException(
                "Volume already exists"
            );
        }
    }

    void attachVolume(
        String volumeName,
        String instanceId
    ) {
        BlockVolume volume = requireVolume(volumeName);
        ComputeInstance instance =
            requireInstance(instanceId);

        if (!instance.isRunning()) {
            throw new IllegalStateException(
                "Storage can only be attached to a running workload"
            );
        }

        volume.attach(instanceId);
        instance.attachVolume(volumeName);
    }

    boolean canConnect(
        String sourceId,
        String destinationId,
        Protocol protocol,
        int port
    ) {
        ComputeInstance source =
            requireInstance(sourceId);

        ComputeInstance destination =
            requireInstance(destinationId);

        if (!source.isRunning() ||
            !destination.isRunning()) {
            return false;
        }

        return destination
            .securityGroup()
            .permits(
                protocol,
                port,
                source.privateIp()
            );
    }

    private ComputeInstance requireInstance(
        String id
    ) {
        ComputeInstance instance =
            instances.get(id);

        if (instance == null) {
            throw new IllegalArgumentException(
                "Unknown instance: " + id
            );
        }

        return instance;
    }

    private BlockVolume requireVolume(
        String name
    ) {
        BlockVolume volume =
            volumes.get(name);

        if (volume == null) {
            throw new IllegalArgumentException(
                "Unknown volume: " + name
            );
        }

        return volume;
    }

    void printReport() {
        System.out.println("=== Enterprise Cloud Report ===");

        System.out.println(
            "Networks: " + networks.size()
        );

        System.out.println(
            "Security groups: " +
            securityGroups.size()
        );

        System.out.println(
            "Compute instances: " +
            instances.size()
        );

        System.out.println(
            "Block volumes: " +
            volumes.size()
        );

        instances.values()
            .forEach(instance ->
                System.out.printf(
                    "%s [%s] %s volumes=%s%n",
                    instance.id(),
                    instance.state(),
                    instance.privateIp(),
                    instance.volumes().size()
                )
            );
    }

    public static void main(String[] args) {
        CloudInfrastructure cloud =
            new CloudInfrastructure();

        VirtualNetwork network =
            new VirtualNetwork(
                "production-vpc",
                "10.0.0.0/16"
            );

        network.addSubnet(
            "public-web",
            "10.0.1.0/24"
        );

        network.addSubnet(
            "private-app",
            "10.0.10.0/24"
        );

        network.addSubnet(
            "private-database",
            "10.0.20.0/24"
        );

        cloud.addNetwork(network);

        SecurityGroup webSecurity =
            new SecurityGroup("web-sg");

        webSecurity.addInboundRule(
            new NetworkRule(
                Protocol.TCP,
                443,
                "0.0.0.0/0"
            )
        );

        webSecurity.addInboundRule(
            new NetworkRule(
                Protocol.TCP,
                22,
                "10.0.10.0/24"
            )
        );

        SecurityGroup databaseSecurity =
            new SecurityGroup("database-sg");

        databaseSecurity.addInboundRule(
            new NetworkRule(
                Protocol.TCP,
                5432,
                "10.0.10.0/24"
            )
        );

        cloud.addSecurityGroup(webSecurity);
        cloud.addSecurityGroup(databaseSecurity);

        ComputeInstance web =
            new ComputeInstance(
                "web-01",
                "web-server",
                "public-web",
                "10.0.1.10",
                webSecurity
            );

        ComputeInstance application =
            new ComputeInstance(
                "app-01",
                "application-server",
                "private-app",
                "10.0.10.10",
                webSecurity
            );

        ComputeInstance database =
            new ComputeInstance(
                "db-01",
                "database-server",
                "private-database",
                "10.0.20.10",
                databaseSecurity
            );

        cloud.addInstance(web);
        cloud.addInstance(application);
        cloud.addInstance(database);

        web.start();
        application.start();
        database.start();

        BlockVolume databaseVolume =
            new BlockVolume(
                "database-data",
                100,
                true
            );

        cloud.addVolume(databaseVolume);
        cloud.attachVolume(
            databaseVolume.name(),
            database.id()
        );

        Identity developer =
            new Identity(
                "application-developer",
                Permission.COMPUTE,
                Permission.STORAGE
            );

        Identity auditor =
            new Identity(
                "audit-user",
                Permission.STORAGE_READ
            );

        System.out.println(
            "Developer can manage compute: " +
            cloud.policy.canManageCompute(developer)
        );

        System.out.println(
            "Developer can manage network: " +
            cloud.policy.canManageNetwork(developer)
        );

        System.out.println(
            "Auditor can read storage: " +
            cloud.policy.canReadStorage(auditor)
        );

        System.out.println(
            "Application -> database: " +
            cloud.canConnect(
                application.id(),
                database.id(),
                Protocol.TCP,
                5432
            )
        );

        System.out.println(
            "Web -> database: " +
            cloud.canConnect(
                web.id(),
                database.id(),
                Protocol.TCP,
                5432
            )
        );

        try {
            database.terminate();
            database.start();
        } catch (IllegalStateException error) {
            System.out.println(
                "Invalid lifecycle transition rejected: " +
                error.getMessage()
            );
        }

        cloud.printReport();
    }
}
