import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import java.util.stream.Collectors;

/*
 * Network Security: Enterprise Traffic Filtering System
 *
 * Java 17 implementation covering:
 * - Firewalls
 * - Stateful security groups
 * - Stateless network ACLs
 * - IPv4/CIDR validation
 * - Policy objects
 * - Connection tracking
 * - Rule priority
 * - Traffic inspection
 * - Audit events
 * - Security reporting
 *
 * Compile:
 * javac NetworkSecurity.java
 *
 * Run:
 * java NetworkSecurity
 */

public class NetworkSecurity {

    // ---------------------------------------------------
    // Enumerations
    // ---------------------------------------------------

    enum Protocol {
        TCP, UDP, ICMP, ANY
    }

    enum Direction {
        INBOUND, OUTBOUND
    }

    enum Action {
        ALLOW, DENY
    }

    enum Layer {
        FIREWALL, SECURITY_GROUP, NETWORK_ACL, VALIDATION
    }

    // ---------------------------------------------------
    // Custom Exceptions
    // ---------------------------------------------------

    static class SecurityConfigurationException
            extends RuntimeException {

        SecurityConfigurationException(String message) {
            super(message);
        }
    }

    static class InvalidPacketException
            extends RuntimeException {

        InvalidPacketException(String message) {
            super(message);
        }
    }

    // ---------------------------------------------------
    // IPv4 Address
    // ---------------------------------------------------

    record IPv4Address(long value) {

        IPv4Address {
            if (value < 0 || value > 0xFFFFFFFFL) {
                throw new IllegalArgumentException(
                    "IPv4 value outside unsigned 32-bit range"
                );
            }
        }

        static IPv4Address parse(String address) {
            String[] parts = address.split("\\.", -1);

            if (parts.length != 4) {
                throw new IllegalArgumentException(
                    "Invalid IPv4 address: " + address
                );
            }

            long result = 0;

            for (String part : parts) {
                if (part.isEmpty() ||
                    !part.matches("[0-9]{1,3}")) {
                    throw new IllegalArgumentException(
                        "Invalid IPv4 octet: " + part
                    );
                }

                int octet = Integer.parseInt(part);

                if (octet > 255) {
                    throw new IllegalArgumentException(
                        "IPv4 octet exceeds 255"
                    );
                }

                result = (result << 8) | octet;
            }

            return new IPv4Address(result);
        }

        @Override
        public String toString() {
            return ((value >> 24) & 255) + "." +
                   ((value >> 16) & 255) + "." +
                   ((value >> 8) & 255) + "." +
                   (value & 255);
        }
    }

    // ---------------------------------------------------
    // CIDR
    // ---------------------------------------------------

    record Cidr(IPv4Address network, int prefix) {

        Cidr {
            Objects.requireNonNull(network);

            if (prefix < 0 || prefix > 32) {
                throw new IllegalArgumentException(
                    "CIDR prefix must be between 0 and 32"
                );
            }
        }

        static Cidr parse(String value) {
            String[] parts = value.split("/", -1);

            if (parts.length != 2) {
                throw new IllegalArgumentException(
                    "CIDR must include a prefix"
                );
            }

            return new Cidr(
                IPv4Address.parse(parts[0]),
                Integer.parseInt(parts[1])
            );
        }

        private long mask() {
            return prefix == 0
                ? 0L
                : (0xFFFFFFFFL << (32 - prefix)) & 0xFFFFFFFFL;
        }

        public boolean contains(IPv4Address address) {
            return (address.value() & mask()) ==
                   (network.value() & mask());
        }
    }

    // ---------------------------------------------------
    // Packet Domain Model
    // ---------------------------------------------------

    record Packet(
        IPv4Address source,
        IPv4Address destination,
        int sourcePort,
        int destinationPort,
        Protocol protocol,
        Direction direction
    ) {

        Packet {
            Objects.requireNonNull(source);
            Objects.requireNonNull(destination);
            Objects.requireNonNull(protocol);
            Objects.requireNonNull(direction);

            validatePort(sourcePort);
            validatePort(destinationPort);

            if (protocol == Protocol.ICMP &&
                (sourcePort != 0 || destinationPort != 0)) {
                throw new InvalidPacketException(
                    "ICMP packets cannot contain transport ports"
                );
            }
        }

        private static void validatePort(int port) {
            if (port < 0 || port > 65535) {
                throw new InvalidPacketException(
                    "Port must be between 0 and 65535"
                );
            }
        }
    }

    // ---------------------------------------------------
    // Firewall Policy
    // ---------------------------------------------------

    record FirewallRule(
        String id,
        String name,
        Cidr source,
        Cidr destination,
        Protocol protocol,
        Direction direction,
        Action action,
        int priority,
        int portStart,
        int portEnd,
        boolean enabled
    ) {

        FirewallRule {
            if (id == null || id.isBlank() ||
                name == null || name.isBlank()) {
                throw new SecurityConfigurationException(
                    "Rule ID and name are mandatory"
                );
            }

            Objects.requireNonNull(source);
            Objects.requireNonNull(destination);
            Objects.requireNonNull(protocol);
            Objects.requireNonNull(direction);
            Objects.requireNonNull(action);

            if (priority < 0) {
                throw new SecurityConfigurationException(
                    "Priority cannot be negative"
                );
            }

            if (portStart < 0 ||
                portEnd > 65535 ||
                portStart > portEnd) {
                throw new SecurityConfigurationException(
                    "Invalid rule port range"
                );
            }

            if (protocol == Protocol.ICMP &&
                (portStart != 0 || portEnd != 65535)) {
                throw new SecurityConfigurationException(
                    "ICMP rules cannot restrict ports"
                );
            }
        }

        boolean matches(Packet packet) {
            if (!enabled || direction != packet.direction()) {
                return false;
            }

            if (protocol != Protocol.ANY &&
                protocol != packet.protocol()) {
                return false;
            }

            if (!source.contains(packet.source()) ||
                !destination.contains(packet.destination())) {
                return false;
            }

            if (packet.protocol() == Protocol.ICMP) {
                return true;
            }

            return packet.destinationPort() >= portStart &&
                   packet.destinationPort() <= portEnd;
        }
    }

    // ---------------------------------------------------
    // Connection Tracking
    // ---------------------------------------------------

    record ConnectionKey(
        IPv4Address source,
        IPv4Address destination,
        int sourcePort,
        int destinationPort,
        Protocol protocol
    ) {
        static ConnectionKey from(Packet packet) {
            return new ConnectionKey(
                packet.source(),
                packet.destination(),
                packet.sourcePort(),
                packet.destinationPort(),
                packet.protocol()
            );
        }

        ConnectionKey reverse() {
            return new ConnectionKey(
                destination,
                source,
                destinationPort,
                sourcePort,
                protocol
            );
        }
    }

    static class ConnectionTracker {

        private final Map<ConnectionKey, Instant> connections =
            new HashMap<>();

        void establish(Packet packet) {
            if (packet.protocol() == Protocol.TCP ||
                packet.protocol() == Protocol.UDP) {

                connections.put(
                    ConnectionKey.from(packet),
                    Instant.now()
                );
            }
        }

        boolean isEstablishedReturn(Packet packet) {
            return connections.containsKey(
                ConnectionKey.from(packet).reverse()
            );
        }

        void close(Packet packet) {
            connections.remove(ConnectionKey.from(packet));
        }

        int activeCount() {
            return connections.size();
        }
    }

    // ---------------------------------------------------
    // Evaluation Result
    // ---------------------------------------------------

    record Decision(
        boolean allowed,
        Layer layer,
        String reason,
        String matchedRule
    ) {}

    // ---------------------------------------------------
    // Policy Interface
    // ---------------------------------------------------

    interface TrafficPolicy {
        Decision evaluate(Packet packet);
    }

    // ---------------------------------------------------
    // Abstract Policy Engine
    // ---------------------------------------------------

    abstract static class AbstractPolicy implements TrafficPolicy {

        protected final List<FirewallRule> rules;
        protected final ConnectionTracker tracker;
        protected final boolean stateful;

        protected AbstractPolicy(
            List<FirewallRule> configuredRules,
            boolean stateful
        ) {
            this.stateful = stateful;
            this.tracker = new ConnectionTracker();

            Set<String> identifiers = new HashSet<>();

            for (FirewallRule rule : configuredRules) {
                if (!identifiers.add(rule.id())) {
                    throw new SecurityConfigurationException(
                        "Duplicate rule ID: " + rule.id()
                    );
                }
            }

            this.rules = configuredRules.stream()
                .sorted(Comparator.comparingInt(
                    FirewallRule::priority
                ))
                .toList();
        }

        protected Decision evaluateRules(
            Packet packet,
            Layer layer
        ) {
            if (stateful &&
                tracker.isEstablishedReturn(packet)) {

                return new Decision(
                    true,
                    layer,
                    "STATEFUL_RETURN",
                    null
                );
            }

            for (FirewallRule rule : rules) {
                if (!rule.matches(packet)) {
                    continue;
                }

                boolean allowed = rule.action() == Action.ALLOW;

                if (allowed && stateful) {
                    tracker.establish(packet);
                }

                return new Decision(
                    allowed,
                    layer,
                    "RULE_MATCH",
                    rule.id()
                );
            }

            return new Decision(
                false,
                layer,
                "DEFAULT_DENY",
                null
            );
        }
    }

    // ---------------------------------------------------
    // Stateful Firewall
    // ---------------------------------------------------

    static final class Firewall extends AbstractPolicy {

        Firewall(List<FirewallRule> rules) {
            super(rules, true);
        }

        @Override
        public Decision evaluate(Packet packet) {
            return evaluateRules(packet, Layer.FIREWALL);
        }
    }

    // ---------------------------------------------------
    // Security Group
    // ---------------------------------------------------

    static final class SecurityGroup extends AbstractPolicy {

        private final String groupId;

        SecurityGroup(
            String groupId,
            List<FirewallRule> inboundRules
        ) {
            super(inboundRules, true);
            this.groupId = groupId;
        }

        @Override
        public Decision evaluate(Packet packet) {
            if (packet.direction() != Direction.INBOUND) {
                throw new IllegalArgumentException(
                    "Security group expects inbound traffic"
                );
            }

            return evaluateRules(
                packet,
                Layer.SECURITY_GROUP
            );
        }
    }

    // ---------------------------------------------------
    // Stateless Network ACL
    // ---------------------------------------------------

    static final class NetworkACL extends AbstractPolicy {

        private final String aclId;

        NetworkACL(
            String aclId,
            List<FirewallRule> rules
        ) {
            super(rules, false);
            this.aclId = aclId;
        }

        @Override
        public Decision evaluate(Packet packet) {
            return evaluateRules(
                packet,
                Layer.NETWORK_ACL
            );
        }
    }

    // ---------------------------------------------------
    // Audit Event
    // ---------------------------------------------------

    record AuditEvent(
        Instant timestamp,
        String source,
        String destination,
        Protocol protocol,
        boolean allowed,
        Layer blockedBy,
        String reason,
        String ruleId
    ) {}

    // ---------------------------------------------------
    // Enterprise Security Service
    // ---------------------------------------------------

    static class NetworkSecurityService {

        private final Firewall firewall;
        private final SecurityGroup securityGroup;
        private final NetworkACL networkACL;

        private final List<AuditEvent> auditEvents =
            new ArrayList<>();

        NetworkSecurityService(
            Firewall firewall,
            SecurityGroup securityGroup,
            NetworkACL networkACL
        ) {
            this.firewall = firewall;
            this.securityGroup = securityGroup;
            this.networkACL = networkACL;
        }

        Decision inspect(Packet packet) {

            Decision result = firewall.evaluate(packet);

            if (!result.allowed()) {
                return record(packet, result);
            }

            if (packet.direction() == Direction.INBOUND) {
                result = securityGroup.evaluate(packet);

                if (!result.allowed()) {
                    return record(packet, result);
                }
            }

            result = networkACL.evaluate(packet);

            if (!result.allowed()) {
                return record(packet, result);
            }

            return record(
                packet,
                new Decision(
                    true,
                    Layer.NETWORK_ACL,
                    "ALL_SECURITY_CONTROLS_PASSED",
                    null
                )
            );
        }

        private Decision record(
            Packet packet,
            Decision decision
        ) {
            auditEvents.add(new AuditEvent(
                Instant.now(),
                packet.source().toString(),
                packet.destination().toString(),
                packet.protocol(),
                decision.allowed(),
                decision.allowed() ? null : decision.layer(),
                decision.reason(),
                decision.matchedRule()
            ));

            return decision;
        }

        Map<String, Long> generateReport() {
            Map<String, Long> report = new TreeMap<>();

            report.put("total", (long) auditEvents.size());

            report.put(
                "allowed",
                auditEvents.stream()
                    .filter(AuditEvent::allowed)
                    .count()
            );

            report.put(
                "denied",
                auditEvents.stream()
                    .filter(event -> !event.allowed())
                    .count()
            );

            for (Layer layer : Layer.values()) {
                long count = auditEvents.stream()
                    .filter(event -> layer.equals(event.blockedBy()))
                    .count();

                report.put("blocked_" + layer.name().toLowerCase(), count);
            }

            return report;
        }

        List<AuditEvent> auditEvents() {
            return List.copyOf(auditEvents);
        }
    }

    // ---------------------------------------------------
    // Configuration Factory
    // ---------------------------------------------------

    static FirewallRule rule(
        String id,
        String name,
        String source,
        String destination,
        Protocol protocol,
        Direction direction,
        Action action,
        int priority,
        int start,
        int end
    ) {
        return new FirewallRule(
            id,
            name,
            Cidr.parse(source),
            Cidr.parse(destination),
            protocol,
            direction,
            action,
            priority,
            start,
            end,
            true
        );
    }

    // ---------------------------------------------------
    // Demonstration
    // ---------------------------------------------------

    public static void main(String[] args) {

        try {
            List<FirewallRule> firewallRules = List.of(
                rule(
                    "FW001", "Allow HTTPS",
                    "10.0.0.0/8", "172.16.0.0/12",
                    Protocol.TCP, Direction.INBOUND,
                    Action.ALLOW, 100, 443, 443
                ),
                rule(
                    "FW002", "Block HTTP",
                    "0.0.0.0/0", "172.16.0.0/12",
                    Protocol.TCP, Direction.INBOUND,
                    Action.DENY, 200, 80, 80
                )
            );

            List<FirewallRule> groupRules = List.of(
                rule(
                    "SG001", "Application HTTPS",
                    "10.0.0.0/8", "172.16.0.0/12",
                    Protocol.TCP, Direction.INBOUND,
                    Action.ALLOW, 100, 443, 443
                )
            );

            List<FirewallRule> aclRules = List.of(
                rule(
                    "ACL001", "Inbound HTTPS",
                    "10.0.0.0/8", "172.16.0.0/12",
                    Protocol.TCP, Direction.INBOUND,
                    Action.ALLOW, 100, 443, 443
                ),
                rule(
                    "ACL002", "Outbound HTTPS response",
                    "172.16.0.0/12", "10.0.0.0/8",
                    Protocol.TCP, Direction.OUTBOUND,
                    Action.ALLOW, 100, 1024, 65535
                ),
                rule(
                    "ACL003", "Inbound DNS",
                    "10.0.0.0/8", "172.16.0.0/12",
                    Protocol.UDP, Direction.INBOUND,
                    Action.ALLOW, 200, 53, 53
                )
            );

            NetworkSecurityService service =
                new NetworkSecurityService(
                    new Firewall(firewallRules),
                    new SecurityGroup("WEB-SG", groupRules),
                    new NetworkACL("PRODUCTION-ACL", aclRules)
                );

            List<Packet> packets = List.of(
                new Packet(
                    IPv4Address.parse("10.1.1.10"),
                    IPv4Address.parse("172.16.1.20"),
                    51000, 443, Protocol.TCP, Direction.INBOUND
                ),
                new Packet(
                    IPv4Address.parse("203.0.113.25"),
                    IPv4Address.parse("172.16.1.20"),
                    51001, 80, Protocol.TCP, Direction.INBOUND
                ),
                new Packet(
                    IPv4Address.parse("10.1.1.10"),
                    IPv4Address.parse("172.16.1.20"),
                    51002, 22, Protocol.TCP, Direction.INBOUND
                ),
                new Packet(
                    IPv4Address.parse("10.1.1.10"),
                    IPv4Address.parse("172.16.1.20"),
                    51003, 53, Protocol.UDP, Direction.INBOUND
                )
            );

            System.out.println("ENTERPRISE NETWORK SECURITY\n");

            for (Packet packet : packets) {
                Decision decision = service.inspect(packet);

                System.out.printf(
                    "%s -> %s | %s | %s | %s | Rule: %s%n",
                    packet.source(),
                    packet.destination(),
                    packet.protocol(),
                    decision.allowed() ? "ALLOW" : "DENY",
                    decision.reason(),
                    decision.matchedRule()
                );
            }

            Packet response = new Packet(
                IPv4Address.parse("172.16.1.20"),
                IPv4Address.parse("10.1.1.10"),
                443, 51000,
                Protocol.TCP,
                Direction.OUTBOUND
            );

            System.out.println("\nSTATEFUL RETURN TRAFFIC");

            Decision returnDecision = service.inspect(response);

            System.out.println(returnDecision);

            System.out.println("\nSECURITY REPORT");

            service.generateReport().forEach(
                (key, value) ->
                    System.out.println(key + " = " + value)
            );

            // Validation tests.
            assert service.inspect(packets.get(0)).allowed();
            assert !service.inspect(packets.get(1)).allowed();
            assert !service.inspect(packets.get(2)).allowed();
            assert service.inspect(packets.get(3)).allowed();

            assert IPv4Address.parse("10.255.255.255").value() ==
                IPv4Address.parse("10.255.255.255").value();

            assert Cidr.parse("10.0.0.0/8").contains(
                IPv4Address.parse("10.10.10.10")
            );

            assert !Cidr.parse("10.0.0.0/8").contains(
                IPv4Address.parse("11.10.10.10")
            );

            System.out.println(
                "\nAll Java 17 network security tests passed."
            );

        } catch (RuntimeException exception) {
            System.err.println(
                "Security configuration or processing error: " +
                exception.getMessage()
            );

            System.exit(1);
        }
    }
}
