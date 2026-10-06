import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Enterprise-oriented network virtualization governance model.
 *
 * Demonstrates:
 * - virtual networks
 * - virtual switches
 * - SDN control/data-plane separation
 * - overlay VNI mapping
 * - explicit network policy states
 * - validation and failure handling
 * - immutable domain records
 * - service-oriented merge/deployment eligibility
 *
 * Compile:
 *   javac NetworkVirtualizationEnterprise.java
 *
 * Run:
 *   java NetworkVirtualizationEnterprise
 */
public class NetworkVirtualizationEnterprise {

    enum SegmentType {
        TENANT,
        MANAGEMENT,
        TRANSIT
    }

    enum DeviceState {
        ACTIVE,
        MAINTENANCE,
        FAILED
    }

    enum Decision {
        ALLOW,
        DENY
    }

    enum FlowState {
        PENDING,
        INSTALLED,
        EXPIRED
    }

    record VirtualNetwork(
            String name,
            String cidr,
            int vni,
            SegmentType type
    ) {
        VirtualNetwork {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Network name is required");
            }
            if (vni < 1 || vni > 0xFFFFFF) {
                throw new IllegalArgumentException("VNI must fit in 24 bits");
            }
            Objects.requireNonNull(type, "segment type");
        }
    }

    record Endpoint(
            String name,
            String mac,
            String ip,
            String networkName,
            String switchName,
            String port
    ) {
        Endpoint {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Endpoint name is required");
            }
            if (!mac.matches("(?i)([0-9a-f]{2}:){5}[0-9a-f]{2}")) {
                throw new IllegalArgumentException("Invalid MAC address: " + mac);
            }
            if (ip == null || ip.isBlank()) {
                throw new IllegalArgumentException("IP address is required");
            }
        }
    }

    record FlowKey(String destinationMac, int vni) {}

    record FlowRule(
            FlowKey key,
            String outputPort,
            int priority,
            FlowState state,
            Instant installedAt
    ) {}

    record StatusCheck(String name, boolean passed) {}

    record OverlayFrame(
            String sourceVtep,
            String destinationVtep,
            int vni,
            Endpoint source,
            Endpoint destination,
            String payload
    ) {}

    static final class VirtualSwitch {
        private final String name;
        private DeviceState state = DeviceState.ACTIVE;
        private final Map<String, Endpoint> portMap = new HashMap<>();
        private final Map<String, String> macTable = new HashMap<>();
        private final Map<FlowKey, FlowRule> flowTable = new HashMap<>();

        VirtualSwitch(String name) {
            this.name = Objects.requireNonNull(name);
        }

        String name() {
            return name;
        }

        void setState(DeviceState newState) {
            state = Objects.requireNonNull(newState);
        }

        DeviceState state() {
            return state;
        }

        void connect(String port, Endpoint endpoint) {
            if (state == DeviceState.FAILED) {
                throw new IllegalStateException(
                        "Cannot modify a failed switch"
                );
            }

            if (portMap.containsKey(port)) {
                throw new IllegalArgumentException(
                        "Port already connected: " + port
                );
            }

            portMap.put(port, endpoint);
        }

        void learn(String mac, String ingressPort) {
            if (!portMap.containsKey(ingressPort)) {
                throw new IllegalArgumentException(
                        "Unknown ingress port: " + ingressPort
                );
            }

            macTable.put(mac, ingressPort);
        }

        void installFlow(FlowRule rule) {
            if (!portMap.containsKey(rule.outputPort())) {
                throw new IllegalArgumentException(
                        "Flow output port is not connected: "
                                + rule.outputPort()
                );
            }

            flowTable.put(rule.key(), rule);
        }

        String forward(
                Endpoint source,
                Endpoint destination,
                int vni
        ) {
            if (state != DeviceState.ACTIVE) {
                return "DROP: virtual switch is not active";
            }

            learn(source.mac(), source.port());

            FlowKey key = new FlowKey(destination.mac(), vni);
            FlowRule rule = flowTable.get(key);

            if (rule != null && rule.state() == FlowState.INSTALLED) {
                return "FORWARD via programmed flow " + rule.outputPort();
            }

            String learnedPort = macTable.get(destination.mac());

            if (learnedPort != null) {
                return "FORWARD via learned MAC " + learnedPort;
            }

            return "FLOOD: destination MAC is unknown";
        }

        void printState() {
            System.out.println("Switch: " + name);
            System.out.println("  state: " + state);
            System.out.println("  learned MACs: " + macTable);
            System.out.println("  installed flows: " + flowTable.size());
        }
    }

    static final class PolicyEngine {
        private final Map<String, Decision> decisions = new HashMap<>();

        void setPolicy(int sourceVni, int destinationVni, Decision decision) {
            decisions.put(
                    policyKey(sourceVni, destinationVni),
                    Objects.requireNonNull(decision)
            );
        }

        Decision evaluate(int sourceVni, int destinationVni) {
            return decisions.getOrDefault(
                    policyKey(sourceVni, destinationVni),
                    Decision.DENY
            );
        }

        private String policyKey(int sourceVni, int destinationVni) {
            return sourceVni + ":" + destinationVni;
        }
    }

    static final class SdnController {
        private final Map<String, VirtualSwitch> switches = new HashMap<>();
        private final Map<String, VirtualNetwork> networks = new HashMap<>();
        private final PolicyEngine policyEngine = new PolicyEngine();
        private final List<String> auditEvents = new ArrayList<>();

        void registerNetwork(VirtualNetwork network) {
            if (networks.putIfAbsent(network.name(), network) != null) {
                throw new IllegalArgumentException(
                        "Duplicate network: " + network.name()
                );
            }

            auditEvents.add("registered network " + network.name());
        }

        void registerSwitch(VirtualSwitch virtualSwitch) {
            if (switches.putIfAbsent(
                    virtualSwitch.name(),
                    virtualSwitch
            ) != null) {
                throw new IllegalArgumentException(
                        "Duplicate switch: " + virtualSwitch.name()
                );
            }

            auditEvents.add("registered switch " + virtualSwitch.name());
        }

        PolicyEngine policy() {
            return policyEngine;
        }

        void installDestinationFlow(
                String switchName,
                Endpoint destination,
                int vni
        ) {
            VirtualSwitch virtualSwitch = switches.get(switchName);

            if (virtualSwitch == null) {
                throw new IllegalArgumentException(
                        "Unknown switch: " + switchName
                );
            }

            FlowKey key = new FlowKey(destination.mac(), vni);

            virtualSwitch.installFlow(
                    new FlowRule(
                            key,
                            destination.port(),
                            100,
                            FlowState.INSTALLED,
                            Instant.now()
                    )
            );

            auditEvents.add(
                    "installed flow on " + switchName +
                    " for " + destination.mac()
            );
        }

        Decision authorize(Endpoint source, Endpoint destination) {
            VirtualNetwork sourceNetwork =
                    requireNetwork(source.networkName());
            VirtualNetwork destinationNetwork =
                    requireNetwork(destination.networkName());

            Decision decision = policyEngine.evaluate(
                    sourceNetwork.vni(),
                    destinationNetwork.vni()
            );

            auditEvents.add(
                    "policy " + source.name() + " -> "
                            + destination.name() + ": " + decision
            );

            return decision;
        }

        VirtualNetwork requireNetwork(String name) {
            VirtualNetwork network = networks.get(name);

            if (network == null) {
                throw new IllegalArgumentException(
                        "Unknown virtual network: " + name
                );
            }

            return network;
        }

        VirtualSwitch requireSwitch(String name) {
            VirtualSwitch virtualSwitch = switches.get(name);

            if (virtualSwitch == null) {
                throw new IllegalArgumentException(
                        "Unknown virtual switch: " + name
                );
            }

            return virtualSwitch;
        }

        void printAudit() {
            System.out.println("Controller audit:");
            auditEvents.forEach(event -> System.out.println("  " + event));
        }
    }

    static final class OverlayService {
        private final Map<String, String> vteps = new HashMap<>();
        private final Map<String, Integer> networkVnis = new HashMap<>();

        void registerNetwork(VirtualNetwork network) {
            networkVnis.put(network.name(), network.vni());
        }

        void registerVtep(String switchName, String address) {
            vteps.put(switchName, address);
        }

        OverlayFrame encapsulate(
                Endpoint source,
                Endpoint destination,
                String payload
        ) {
            Integer vni = networkVnis.get(source.networkName());
            String sourceVtep = vteps.get(source.switchName());
            String destinationVtep = vteps.get(destination.switchName());

            if (vni == null) {
                throw new IllegalStateException(
                        "No VNI mapping for " + source.networkName()
                );
            }

            if (sourceVtep == null || destinationVtep == null) {
                throw new IllegalStateException(
                        "Both source and destination VTEPs are required"
                );
            }

            return new OverlayFrame(
                    sourceVtep,
                    destinationVtep,
                    vni,
                    source,
                    destination,
                    payload
            );
        }

        Endpoint decapsulate(
                OverlayFrame frame,
                VirtualNetwork expectedNetwork
        ) {
            if (frame.vni() != expectedNetwork.vni()) {
                throw new SecurityException(
                        "Overlay VNI does not match expected network"
                );
            }

            return frame.destination();
        }
    }

    static final class DeploymentGate {
        private final List<StatusCheck> checks = new ArrayList<>();

        void add(StatusCheck check) {
            checks.add(Objects.requireNonNull(check));
        }

        boolean isReady() {
            return checks.stream().allMatch(StatusCheck::passed);
        }

        void print() {
            checks.forEach(check ->
                    System.out.println(
                            "  " + check.name() + ": "
                                    + (check.passed() ? "PASS" : "FAIL")
                    )
            );
        }
    }

    private static Endpoint endpoint(
            String name,
            String mac,
            String ip,
            String network,
            String switchName,
            String port
    ) {
        return new Endpoint(
                name, mac, ip, network, switchName, port
        );
    }

    public static void main(String[] args) {
        try {
            System.out.println(
                    "=== Enterprise Network Virtualization Model ===\n"
            );

            VirtualNetwork tenantA = new VirtualNetwork(
                    "tenant-a",
                    "10.10.10.0/24",
                    1010,
                    SegmentType.TENANT
            );

            VirtualNetwork tenantB = new VirtualNetwork(
                    "tenant-b",
                    "10.20.20.0/24",
                    2020,
                    SegmentType.TENANT
            );

            Endpoint webA = endpoint(
                    "web-a",
                    "02:00:00:00:00:01",
                    "10.10.10.10",
                    "tenant-a",
                    "vswitch-a",
                    "p1"
            );

            Endpoint dbA = endpoint(
                    "db-a",
                    "02:00:00:00:00:02",
                    "10.10.10.20",
                    "tenant-a",
                    "vswitch-a",
                    "p2"
            );

            Endpoint webB = endpoint(
                    "web-b",
                    "02:00:00:00:00:11",
                    "10.20.20.10",
                    "tenant-b",
                    "vswitch-b",
                    "p1"
            );

            VirtualSwitch switchA = new VirtualSwitch("vswitch-a");
            VirtualSwitch switchB = new VirtualSwitch("vswitch-b");

            switchA.connect("p1", webA);
            switchA.connect("p2", dbA);
            switchB.connect("p1", webB);

            SdnController controller = new SdnController();
            controller.registerNetwork(tenantA);
            controller.registerNetwork(tenantB);
            controller.registerSwitch(switchA);
            controller.registerSwitch(switchB);

            controller.policy().setPolicy(
                    tenantA.vni(),
                    tenantA.vni(),
                    Decision.ALLOW
            );

            controller.policy().setPolicy(
                    tenantB.vni(),
                    tenantB.vni(),
                    Decision.ALLOW
            );

            controller.policy().setPolicy(
                    tenantA.vni(),
                    tenantB.vni(),
                    Decision.DENY
            );

            controller.policy().setPolicy(
                    tenantB.vni(),
                    tenantA.vni(),
                    Decision.DENY
            );

            System.out.println("Virtual network policy:");
            System.out.println(
                    "  tenant-a -> tenant-a: "
                            + controller.authorize(webA, dbA)
            );

            System.out.println(
                    "  tenant-a -> tenant-b: "
                            + controller.authorize(webA, webB)
            );

            System.out.println("\nVirtual-switch learning:");
            System.out.println(
                    "  " + switchA.forward(webA, dbA, tenantA.vni())
            );

            controller.installDestinationFlow(
                    switchA.name(),
                    dbA,
                    tenantA.vni()
            );

            System.out.println(
                    "  " + switchA.forward(webA, dbA, tenantA.vni())
            );

            OverlayService overlayService = new OverlayService();
            overlayService.registerNetwork(tenantA);
            overlayService.registerNetwork(tenantB);
            overlayService.registerVtep(
                    "vswitch-a",
                    "192.0.2.10"
            );
            overlayService.registerVtep(
                    "vswitch-b",
                    "192.0.2.20"
            );

            System.out.println("\nOverlay service:");

            OverlayFrame frame = overlayService.encapsulate(
                    webA,
                    dbA,
                    "database request"
            );

            System.out.println(
                    "  outer transport: "
                            + frame.sourceVtep()
                            + " -> "
                            + frame.destinationVtep()
            );
            System.out.println("  VNI: " + frame.vni());
            System.out.println(
                    "  inner flow: "
                            + frame.source().ip()
                            + " -> "
                            + frame.destination().ip()
            );

            overlayService.decapsulate(frame, tenantA);
            System.out.println("  decapsulation: accepted");

            try {
                overlayService.decapsulate(frame, tenantB);
                System.out.println(
                        "  ERROR: invalid tenant mapping accepted"
                );
            } catch (SecurityException exception) {
                System.out.println(
                        "  security validation: "
                                + exception.getMessage()
                );
            }

            System.out.println("\nDeployment gate:");

            DeploymentGate gate = new DeploymentGate();
            gate.add(new StatusCheck(
                    "underlay reachability", true
            ));
            gate.add(new StatusCheck(
                    "VTEP availability", true
            ));
            gate.add(new StatusCheck(
                    "VNI allocation consistency", true
            ));
            gate.add(new StatusCheck(
                    "tenant isolation policy", true
            ));

            gate.print();
            System.out.println(
                    "  deployment: "
                            + (gate.isReady() ? "READY" : "BLOCKED")
            );

            System.out.println("\nOperational state:");
            switchA.printState();
            switchB.printState();

            System.out.println();
            controller.printAudit();

        } catch (RuntimeException exception) {
            System.err.println(
                    "Configuration or runtime failure: "
                            + exception.getMessage()
            );
            System.exit(1);
        }
    }
}
