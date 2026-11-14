import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/*
 * CLOUD SECURITY GOVERNANCE PLATFORM
 *
 * Java 17
 *
 * Enterprise-oriented domain model:
 * - IAM and role-based authorization
 * - Explicit deny-by-default decisions
 * - Network segmentation
 * - Encryption compliance
 * - Immutable audit events
 * - Monitoring and incident management
 * - Security posture evaluation
 */

public class CloudSecurityPlatform {

    enum Decision {
        ALLOW, DENY
    }

    enum Severity {
        LOW, MEDIUM, HIGH, CRITICAL
    }

    enum ResourceState {
        ACTIVE, QUARANTINED, DISABLED
    }

    enum Protocol {
        TCP, UDP
    }

    static class SecurityException extends RuntimeException {
        SecurityException(String message) {
            super(message);
        }
    }

    static class ValidationException extends SecurityException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class PolicyViolationException extends SecurityException {
        PolicyViolationException(String message) {
            super(message);
        }
    }

    record Permission(
        String action,
        String resource
    ) {
        Permission {
            Objects.requireNonNull(action);
            Objects.requireNonNull(resource);

            if (action.isBlank() || resource.isBlank()) {
                throw new ValidationException(
                    "Permission fields cannot be blank"
                );
            }
        }

        boolean matches(String requestedAction, String requestedResource) {
            boolean actionMatch =
                action.equals("*") ||
                action.equals(requestedAction);

            boolean resourceMatch =
                resource.equals("*") ||
                resource.equals(requestedResource) ||
                (
                    resource.endsWith("*") &&
                    requestedResource.startsWith(
                        resource.substring(0, resource.length() - 1)
                    )
                );

            return actionMatch && resourceMatch;
        }
    }

    record Role(
        String name,
        Set<Permission> permissions
    ) {
        Role {
            Objects.requireNonNull(name);
            permissions = Set.copyOf(permissions);

            if (name.isBlank()) {
                throw new ValidationException("Role name required");
            }
        }
    }

    static final class Principal {
        private final String id;
        private final Set<String> roles;
        private volatile boolean enabled;
        private volatile boolean mfaEnabled;

        Principal(
            String id,
            Set<String> roles,
            boolean enabled,
            boolean mfaEnabled
        ) {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Invalid principal");
            }

            this.id = id;
            this.roles = Set.copyOf(roles);
            this.enabled = enabled;
            this.mfaEnabled = mfaEnabled;
        }

        String id() {
            return id;
        }

        Set<String> roles() {
            return roles;
        }

        boolean enabled() {
            return enabled;
        }

        boolean mfaEnabled() {
            return mfaEnabled;
        }

        void disable() {
            enabled = false;
        }
    }

    static final class CloudResource {
        private final String id;
        private final String type;
        private final boolean encryptedAtRest;
        private final boolean encryptedInTransit;
        private final boolean publicAccess;
        private volatile ResourceState state;

        CloudResource(
            String id,
            String type,
            boolean encryptedAtRest,
            boolean encryptedInTransit,
            boolean publicAccess
        ) {
            if (id == null || id.isBlank() ||
                type == null || type.isBlank()) {
                throw new ValidationException("Invalid resource");
            }

            this.id = id;
            this.type = type;
            this.encryptedAtRest = encryptedAtRest;
            this.encryptedInTransit = encryptedInTransit;
            this.publicAccess = publicAccess;
            this.state = ResourceState.ACTIVE;
        }

        String id() {
            return id;
        }

        ResourceState state() {
            return state;
        }

        void quarantine() {
            state = ResourceState.QUARANTINED;
        }

        boolean compliant() {
            return encryptedAtRest &&
                encryptedInTransit &&
                !publicAccess;
        }
    }

    record NetworkRule(
        String cidr,
        int prefix,
        int port,
        Protocol protocol
    ) {
        NetworkRule {
            Objects.requireNonNull(protocol);

            if (
                prefix < 0 || prefix > 32 ||
                port < 1 || port > 65535
            ) {
                throw new ValidationException("Invalid network rule");
            }

            if (!validIPv4(cidr)) {
                throw new ValidationException("Invalid IPv4 address");
            }
        }

        private static boolean validIPv4(String address) {
            if (address == null) return false;

            String[] octets = address.split("\\.", -1);

            if (octets.length != 4) return false;

            for (String octet : octets) {
                try {
                    if (
                        octet.isEmpty() ||
                        octet.length() > 3 ||
                        Integer.parseInt(octet) < 0 ||
                        Integer.parseInt(octet) > 255
                    ) {
                        return false;
                    }
                } catch (NumberFormatException exception) {
                    return false;
                }
            }

            return true;
        }

        private static long toInteger(String address) {
            return Arrays.stream(address.split("\\."))
                .mapToLong(Long::parseLong)
                .reduce(0L, (value, octet) ->
                    (value << 8) | octet
                );
        }

        boolean contains(String address) {
            if (!validIPv4(address)) {
                throw new ValidationException("Invalid source IP");
            }

            long mask = prefix == 0
                ? 0L
                : (0xFFFFFFFFL << (32 - prefix)) & 0xFFFFFFFFL;

            return (
                toInteger(address) & mask
            ) == (
                toInteger(cidr) & mask
            );
        }
    }

    record AuditEvent(
        String eventId,
        Instant timestamp,
        String principalId,
        String action,
        String resourceId,
        Decision decision,
        Severity severity,
        String description
    ) {}

    record SecurityAlert(
        String alertId,
        String principalId,
        int failedAttempts,
        Severity severity,
        Instant timestamp,
        String description
    ) {}

    record Assessment(
        int resourcesAssessed,
        int compliantResources,
        int nonCompliantResources,
        int auditEvents,
        int alerts,
        List<String> findings
    ) {}

    interface AuditRepository {
        void append(AuditEvent event);
        List<AuditEvent> findAll();
    }

    static final class InMemoryAuditRepository
        implements AuditRepository {

        private final List<AuditEvent> events =
            Collections.synchronizedList(new ArrayList<>());

        @Override
        public void append(AuditEvent event) {
            events.add(event);
        }

        @Override
        public List<AuditEvent> findAll() {
            synchronized (events) {
                return List.copyOf(events);
            }
        }
    }

    static final class IAMService {
        private final Map<String, Role> roles =
            new ConcurrentHashMap<>();

        private final Map<String, Principal> principals =
            new ConcurrentHashMap<>();

        void registerRole(Role role) {
            if (roles.putIfAbsent(role.name(), role) != null) {
                throw new ValidationException("Duplicate role");
            }
        }

        void registerPrincipal(Principal principal) {
            for (String role : principal.roles()) {
                if (!roles.containsKey(role)) {
                    throw new ValidationException(
                        "Unknown role: " + role
                    );
                }
            }

            if (
                principals.putIfAbsent(
                    principal.id(),
                    principal
                ) != null
            ) {
                throw new ValidationException("Duplicate principal");
            }
        }

        Decision authorize(
            String principalId,
            String action,
            String resource,
            boolean requireMFA
        ) {
            Principal principal = principals.get(principalId);

            if (
                principal == null ||
                !principal.enabled() ||
                (requireMFA && !principal.mfaEnabled())
            ) {
                return Decision.DENY;
            }

            return principal.roles().stream()
                .map(roles::get)
                .flatMap(role -> role.permissions().stream())
                .anyMatch(permission ->
                    permission.matches(action, resource)
                )
                ? Decision.ALLOW
                : Decision.DENY;
        }

        void disable(String principalId) {
            Principal principal = principals.get(principalId);

            if (principal == null) {
                throw new ValidationException("Unknown principal");
            }

            principal.disable();
        }
    }

    static final class NetworkSecurityService {
        private final Map<String, List<NetworkRule>> rules =
            new ConcurrentHashMap<>();

        void addRule(
            String resourceId,
            NetworkRule rule
        ) {
            rules.computeIfAbsent(
                resourceId,
                key -> Collections.synchronizedList(
                    new ArrayList<>()
                )
            ).add(rule);
        }

        boolean allows(
            String resourceId,
            String sourceIP,
            int port,
            Protocol protocol
        ) {
            List<NetworkRule> resourceRules =
                rules.getOrDefault(resourceId, List.of());

            synchronized (resourceRules) {
                return resourceRules.stream().anyMatch(rule ->
                    rule.port() == port &&
                    rule.protocol() == protocol &&
                    rule.contains(sourceIP)
                );
            }
        }
    }

    static final class MonitoringService {
        private final int threshold;

        private final Map<String, Integer> failures =
            new ConcurrentHashMap<>();

        private final List<SecurityAlert> alerts =
            Collections.synchronizedList(new ArrayList<>());

        MonitoringService(int threshold) {
            if (threshold < 1) {
                throw new ValidationException(
                    "Threshold must be positive"
                );
            }

            this.threshold = threshold;
        }

        void process(AuditEvent event) {
            if (event.decision() != Decision.DENY) return;

            int count = failures.merge(
                event.principalId(),
                1,
                Integer::sum
            );

            if (count >= threshold) {
                SecurityAlert alert = new SecurityAlert(
                    UUID.randomUUID().toString(),
                    event.principalId(),
                    count,
                    Severity.HIGH,
                    Instant.now(),
                    "Repeated unauthorized access attempts"
                );

                alerts.add(alert);
            }
        }

        List<SecurityAlert> getAlerts() {
            synchronized (alerts) {
                return List.copyOf(alerts);
            }
        }
    }

    static final class CloudSecurityService {
        private final IAMService iam;
        private final NetworkSecurityService network;
        private final AuditRepository audit;
        private final MonitoringService monitoring;

        private final Map<String, CloudResource> resources =
            new ConcurrentHashMap<>();

        CloudSecurityService(
            IAMService iam,
            NetworkSecurityService network,
            AuditRepository audit,
            MonitoringService monitoring
        ) {
            this.iam = iam;
            this.network = network;
            this.audit = audit;
            this.monitoring = monitoring;
        }

        void registerResource(CloudResource resource) {
            if (!resource.compliant()) {
                throw new PolicyViolationException(
                    "Resource violates encryption or exposure policy"
                );
            }

            if (
                resources.putIfAbsent(resource.id(), resource) != null
            ) {
                throw new ValidationException("Duplicate resource");
            }
        }

        Decision evaluateAccess(
            String principalId,
            String action,
            String resourceId,
            String sourceIP,
            int port
        ) {
            CloudResource resource = resources.get(resourceId);

            if (resource == null) {
                throw new ValidationException("Unknown resource");
            }

            Decision decision = Decision.DENY;
            String reason = "IAM or network policy rejected request";

            if (resource.state() == ResourceState.ACTIVE) {
                Decision iamDecision = iam.authorize(
                    principalId,
                    action,
                    resourceId,
                    true
                );

                boolean networkDecision = network.allows(
                    resourceId,
                    sourceIP,
                    port,
                    Protocol.TCP
                );

                if (
                    iamDecision == Decision.ALLOW &&
                    networkDecision
                ) {
                    decision = Decision.ALLOW;
                    reason = "Access granted";
                }
            } else {
                reason = "Resource is unavailable";
            }

            AuditEvent event = new AuditEvent(
                UUID.randomUUID().toString(),
                Instant.now(),
                principalId,
                action,
                resourceId,
                decision,
                decision == Decision.ALLOW
                    ? Severity.LOW
                    : Severity.HIGH,
                reason
            );

            audit.append(event);
            monitoring.process(event);

            return decision;
        }

        void quarantine(String resourceId) {
            CloudResource resource = resources.get(resourceId);

            if (resource == null) {
                throw new ValidationException("Unknown resource");
            }

            resource.quarantine();
        }

        Assessment assess() {
            List<String> findings = new ArrayList<>();

            int compliant = 0;

            for (CloudResource resource : resources.values()) {
                if (resource.compliant()) {
                    compliant++;
                } else {
                    findings.add(
                        resource.id() + ": security baseline violation"
                    );
                }

                if (resource.state() != ResourceState.ACTIVE) {
                    findings.add(
                        resource.id() + ": " + resource.state()
                    );
                }
            }

            return new Assessment(
                resources.size(),
                compliant,
                resources.size() - compliant,
                audit.findAll().size(),
                monitoring.getAlerts().size(),
                List.copyOf(findings)
            );
        }
    }

    public static void main(String[] args) {
        IAMService iam = new IAMService();
        NetworkSecurityService network =
            new NetworkSecurityService();

        AuditRepository audit =
            new InMemoryAuditRepository();

        MonitoringService monitoring =
            new MonitoringService(3);

        CloudSecurityService cloud =
            new CloudSecurityService(
                iam,
                network,
                audit,
                monitoring
            );

        Role reader = new Role(
            "storage-reader",
            Set.of(
                new Permission(
                    "storage:read",
                    "bucket-finance-001"
                )
            )
        );

        iam.registerRole(reader);

        iam.registerPrincipal(
            new Principal(
                "operator-001",
                Set.of("storage-reader"),
                true,
                true
            )
        );

        iam.registerPrincipal(
            new Principal(
                "untrusted-001",
                Set.of(),
                true,
                false
            )
        );

        cloud.registerResource(
            new CloudResource(
                "bucket-finance-001",
                "OBJECT_STORAGE",
                true,
                true,
                false
            )
        );

        network.addRule(
            "bucket-finance-001",
            new NetworkRule(
                "10.20.0.0",
                16,
                443,
                Protocol.TCP
            )
        );

        System.out.println(
            "Authorized request: " +
            cloud.evaluateAccess(
                "operator-001",
                "storage:read",
                "bucket-finance-001",
                "10.20.1.10",
                443
            )
        );

        for (int i = 0; i < 3; i++) {
            cloud.evaluateAccess(
                "untrusted-001",
                "storage:read",
                "bucket-finance-001",
                "10.20.1.20",
                443
            );
        }

        System.out.println("\nSECURITY ASSESSMENT");

        Assessment assessment = cloud.assess();

        System.out.println(assessment);

        System.out.println("\nSECURITY ALERTS");

        monitoring.getAlerts().forEach(System.out::println);

        cloud.quarantine("bucket-finance-001");

        System.out.println(
            "\nAccess after quarantine: " +
            cloud.evaluateAccess(
                "operator-001",
                "storage:read",
                "bucket-finance-001",
                "10.20.1.10",
                443
            )
        );
    }
}
