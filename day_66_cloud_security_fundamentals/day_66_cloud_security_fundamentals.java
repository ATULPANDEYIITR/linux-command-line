import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

public class CloudSecurityFundamentals {

    enum CloudServiceModel {
        IAAS, PAAS, SAAS
    }

    enum SecurityDomain {
        PHYSICAL_SECURITY,
        NETWORK_SECURITY,
        HOST_INFRASTRUCTURE,
        OPERATING_SYSTEM,
        APPLICATION_SECURITY,
        IDENTITY_AND_ACCESS,
        DATA_PROTECTION,
        CONFIGURATION,
        COMPLIANCE,
        BACKUP_AND_RECOVERY
    }

    enum Responsibility {
        PROVIDER,
        CUSTOMER,
        SHARED
    }

    enum FindingSeverity {
        LOW, MEDIUM, HIGH, CRITICAL
    }

    enum FindingStatus {
        OPEN, IN_PROGRESS, RESOLVED, ACCEPTED
    }

    enum AccessLevel {
        READ_ONLY, OPERATOR, ADMINISTRATOR
    }

    record SecurityControl(
            SecurityDomain domain,
            Responsibility responsibility,
            String description
    ) {
        SecurityControl {
            Objects.requireNonNull(domain);
            Objects.requireNonNull(responsibility);
            if (description == null || description.isBlank()) {
                throw new IllegalArgumentException("Control description is required");
            }
        }
    }

    record CloudResource(
            String resourceId,
            String resourceName,
            CloudServiceModel serviceModel,
            String owner
    ) {
        CloudResource {
            if (resourceId == null || resourceId.isBlank()
                    || resourceName == null || resourceName.isBlank()
                    || owner == null || owner.isBlank()) {
                throw new IllegalArgumentException("Invalid cloud resource");
            }
            Objects.requireNonNull(serviceModel);
        }
    }

    static class SecurityFinding {
        private final String findingId;
        private final String resourceId;
        private final SecurityDomain domain;
        private final FindingSeverity severity;
        private final String description;
        private FindingStatus status;
        private final Instant createdAt;

        SecurityFinding(
                String resourceId,
                SecurityDomain domain,
                FindingSeverity severity,
                String description
        ) {
            this.findingId = UUID.randomUUID().toString();
            this.resourceId = resourceId;
            this.domain = Objects.requireNonNull(domain);
            this.severity = Objects.requireNonNull(severity);
            this.description = Objects.requireNonNull(description);
            this.status = FindingStatus.OPEN;
            this.createdAt = Instant.now();
        }

        void updateStatus(FindingStatus newStatus) {
            Objects.requireNonNull(newStatus);

            if (status == FindingStatus.RESOLVED
                    || status == FindingStatus.ACCEPTED) {
                throw new IllegalStateException(
                        "Closed findings cannot be reopened through this operation"
                );
            }

            status = newStatus;
        }

        public String getFindingId() {
            return findingId;
        }

        public String getResourceId() {
            return resourceId;
        }

        public SecurityDomain getDomain() {
            return domain;
        }

        public FindingSeverity getSeverity() {
            return severity;
        }

        public FindingStatus getStatus() {
            return status;
        }

        public Instant getCreatedAt() {
            return createdAt;
        }

        @Override
        public String toString() {
            return "Finding{id='" + findingId.substring(0, 8)
                    + "', resource='" + resourceId
                    + "', domain=" + domain
                    + ", severity=" + severity
                    + ", status=" + status + "}";
        }
    }

    static class ResponsibilityMatrix {

        private final Map<CloudServiceModel,
                Map<SecurityDomain, Responsibility>> matrix =
                new EnumMap<>(CloudServiceModel.class);

        ResponsibilityMatrix() {
            initialize();
        }

        private void initialize() {
            Map<SecurityDomain, Responsibility> iaas =
                    new EnumMap<>(SecurityDomain.class);

            iaas.put(SecurityDomain.PHYSICAL_SECURITY, Responsibility.PROVIDER);
            iaas.put(SecurityDomain.HOST_INFRASTRUCTURE, Responsibility.PROVIDER);
            iaas.put(SecurityDomain.NETWORK_SECURITY, Responsibility.SHARED);
            iaas.put(SecurityDomain.OPERATING_SYSTEM, Responsibility.CUSTOMER);
            iaas.put(SecurityDomain.APPLICATION_SECURITY, Responsibility.CUSTOMER);
            iaas.put(SecurityDomain.IDENTITY_AND_ACCESS, Responsibility.CUSTOMER);
            iaas.put(SecurityDomain.DATA_PROTECTION, Responsibility.CUSTOMER);
            iaas.put(SecurityDomain.CONFIGURATION, Responsibility.CUSTOMER);
            iaas.put(SecurityDomain.COMPLIANCE, Responsibility.SHARED);
            iaas.put(SecurityDomain.BACKUP_AND_RECOVERY, Responsibility.CUSTOMER);

            Map<SecurityDomain, Responsibility> paas =
                    new EnumMap<>(SecurityDomain.class);

            paas.put(SecurityDomain.PHYSICAL_SECURITY, Responsibility.PROVIDER);
            paas.put(SecurityDomain.HOST_INFRASTRUCTURE, Responsibility.PROVIDER);
            paas.put(SecurityDomain.NETWORK_SECURITY, Responsibility.SHARED);
            paas.put(SecurityDomain.OPERATING_SYSTEM, Responsibility.PROVIDER);
            paas.put(SecurityDomain.APPLICATION_SECURITY, Responsibility.CUSTOMER);
            paas.put(SecurityDomain.IDENTITY_AND_ACCESS, Responsibility.SHARED);
            paas.put(SecurityDomain.DATA_PROTECTION, Responsibility.CUSTOMER);
            paas.put(SecurityDomain.CONFIGURATION, Responsibility.SHARED);
            paas.put(SecurityDomain.COMPLIANCE, Responsibility.SHARED);
            paas.put(SecurityDomain.BACKUP_AND_RECOVERY, Responsibility.SHARED);

            Map<SecurityDomain, Responsibility> saas =
                    new EnumMap<>(SecurityDomain.class);

            saas.put(SecurityDomain.PHYSICAL_SECURITY, Responsibility.PROVIDER);
            saas.put(SecurityDomain.HOST_INFRASTRUCTURE, Responsibility.PROVIDER);
            saas.put(SecurityDomain.NETWORK_SECURITY, Responsibility.PROVIDER);
            saas.put(SecurityDomain.OPERATING_SYSTEM, Responsibility.PROVIDER);
            saas.put(SecurityDomain.APPLICATION_SECURITY, Responsibility.PROVIDER);
            saas.put(SecurityDomain.IDENTITY_AND_ACCESS, Responsibility.SHARED);
            saas.put(SecurityDomain.DATA_PROTECTION, Responsibility.SHARED);
            saas.put(SecurityDomain.CONFIGURATION, Responsibility.SHARED);
            saas.put(SecurityDomain.COMPLIANCE, Responsibility.SHARED);
            saas.put(SecurityDomain.BACKUP_AND_RECOVERY, Responsibility.SHARED);

            matrix.put(CloudServiceModel.IAAS, iaas);
            matrix.put(CloudServiceModel.PAAS, paas);
            matrix.put(CloudServiceModel.SAAS, saas);
        }

        Responsibility getResponsibility(
                CloudServiceModel model,
                SecurityDomain domain
        ) {
            return matrix.get(model).get(domain);
        }

        void display(CloudServiceModel model) {
            System.out.println("\nResponsibility Matrix: " + model);

            matrix.get(model).forEach((domain, responsibility) ->
                    System.out.printf("%-25s %s%n", domain, responsibility)
            );
        }
    }

    record User(
            String username,
            Set<AccessLevel> permissions,
            boolean mfaEnabled,
            boolean active
    ) {
        User {
            if (username == null || username.isBlank()) {
                throw new IllegalArgumentException("Username is required");
            }

            permissions = Set.copyOf(permissions);
        }
    }

    static class AccessManager {

        private final Map<String, User> users = new HashMap<>();

        void register(User user) {
            if (users.putIfAbsent(user.username(), user) != null) {
                throw new IllegalArgumentException("User already exists");
            }
        }

        boolean authorize(String username, AccessLevel required) {
            User user = users.get(username);

            if (user == null || !user.active()) {
                return false;
            }

            if (!user.mfaEnabled()) {
                System.out.println("Access denied: MFA is not enabled");
                return false;
            }

            return user.permissions().contains(required)
                    || user.permissions().contains(AccessLevel.ADMINISTRATOR);
        }
    }

    static class CloudSecurityPlatform {

        private final Map<String, CloudResource> resources =
                new HashMap<>();

        private final List<SecurityFinding> findings =
                new ArrayList<>();

        private final ResponsibilityMatrix responsibilityMatrix =
                new ResponsibilityMatrix();

        private final AccessManager accessManager =
                new AccessManager();

        void registerResource(CloudResource resource) {
            if (resources.putIfAbsent(resource.resourceId(), resource) != null) {
                throw new IllegalArgumentException(
                        "Resource identifier already exists"
                );
            }
        }

        void registerUser(User user) {
            accessManager.register(user);
        }

        boolean checkAccess(String username, AccessLevel level) {
            return accessManager.authorize(username, level);
        }

        SecurityFinding createFinding(
                String resourceId,
                SecurityDomain domain,
                FindingSeverity severity,
                String description
        ) {
            CloudResource resource = resources.get(resourceId);

            if (resource == null) {
                throw new IllegalArgumentException("Unknown cloud resource");
            }

            Responsibility responsibility =
                    responsibilityMatrix.getResponsibility(
                            resource.serviceModel(), domain
                    );

            if (responsibility == Responsibility.PROVIDER) {
                System.out.println(
                        "Provider responsibility: coordinate with the provider"
                );
            }

            SecurityFinding finding = new SecurityFinding(
                    resourceId, domain, severity, description
            );

            findings.add(finding);
            return finding;
        }

        void updateFinding(
                String findingId,
                FindingStatus status,
                String username
        ) {
            if (!checkAccess(username, AccessLevel.OPERATOR)) {
                throw new SecurityException("Insufficient permissions");
            }

            SecurityFinding finding = findings.stream()
                    .filter(f -> f.getFindingId().equals(findingId))
                    .findFirst()
                    .orElseThrow(() ->
                            new IllegalArgumentException("Finding not found")
                    );

            finding.updateStatus(status);
        }

        void evaluateResource(String resourceId) {
            CloudResource resource = resources.get(resourceId);

            if (resource == null) {
                throw new IllegalArgumentException("Resource not found");
            }

            System.out.println("\nSecurity evaluation: " + resource.resourceName());

            List<SecurityFinding> resourceFindings = findings.stream()
                    .filter(f -> f.getResourceId().equals(resourceId))
                    .toList();

            if (resourceFindings.isEmpty()) {
                System.out.println("No security findings recorded.");
                return;
            }

            resourceFindings.forEach(System.out::println);

            long unresolvedCritical = resourceFindings.stream()
                    .filter(f -> f.getSeverity() == FindingSeverity.CRITICAL)
                    .filter(f -> f.getStatus() == FindingStatus.OPEN
                            || f.getStatus() == FindingStatus.IN_PROGRESS)
                    .count();

            System.out.println("Unresolved critical findings: "
                    + unresolvedCritical);
        }

        void generateReport() {
            System.out.println("\n========== SECURITY REPORT ==========");

            Map<FindingSeverity, Long> severityCounts =
                    findings.stream().collect(Collectors.groupingBy(
                            SecurityFinding::getSeverity,
                            () -> new EnumMap<>(FindingSeverity.class),
                            Collectors.counting()
                    ));

            for (FindingSeverity severity : FindingSeverity.values()) {
                System.out.printf("%-10s %d%n",
                        severity, severityCounts.getOrDefault(severity, 0L));
            }

            System.out.println("Total findings: " + findings.size());

            long openCount = findings.stream()
                    .filter(f -> f.getStatus() == FindingStatus.OPEN
                            || f.getStatus() == FindingStatus.IN_PROGRESS)
                    .count();

            System.out.println("Unresolved findings: " + openCount);
        }
    }

    public static void main(String[] args) {

        CloudSecurityPlatform platform = new CloudSecurityPlatform();

        platform.registerUser(new User(
                "security-analyst",
                Set.of(AccessLevel.READ_ONLY, AccessLevel.OPERATOR),
                true,
                true
        ));

        platform.registerUser(new User(
                "legacy-user",
                Set.of(AccessLevel.ADMINISTRATOR),
                false,
                true
        ));

        platform.registerResource(new CloudResource(
                "VM-001",
                "Production Virtual Machine",
                CloudServiceModel.IAAS,
                "Infrastructure Team"
        ));

        platform.registerResource(new CloudResource(
                "APP-001",
                "Managed Application Platform",
                CloudServiceModel.PAAS,
                "Application Team"
        ));

        platform.registerResource(new CloudResource(
                "CRM-001",
                "Enterprise CRM",
                CloudServiceModel.SAAS,
                "Business Operations"
        ));

        ResponsibilityMatrix matrix = new ResponsibilityMatrix();

        matrix.display(CloudServiceModel.IAAS);
        matrix.display(CloudServiceModel.PAAS);
        matrix.display(CloudServiceModel.SAAS);

        SecurityFinding finding1 = platform.createFinding(
                "VM-001",
                SecurityDomain.OPERATING_SYSTEM,
                FindingSeverity.CRITICAL,
                "Unpatched operating system"
        );

        platform.createFinding(
                "VM-001",
                SecurityDomain.NETWORK_SECURITY,
                FindingSeverity.HIGH,
                "Unrestricted inbound network access"
        );

        platform.createFinding(
                "APP-001",
                SecurityDomain.CONFIGURATION,
                FindingSeverity.MEDIUM,
                "Application configuration requires review"
        );

        platform.createFinding(
                "CRM-001",
                SecurityDomain.IDENTITY_AND_ACCESS,
                FindingSeverity.HIGH,
                "Weak access control configuration"
        );

        System.out.println("\nValid access: "
                + platform.checkAccess("security-analyst", AccessLevel.OPERATOR));

        System.out.println("Legacy administrator access: "
                + platform.checkAccess("legacy-user", AccessLevel.ADMINISTRATOR));

        platform.updateFinding(
                finding1.getFindingId(),
                FindingStatus.IN_PROGRESS,
                "security-analyst"
        );

        platform.evaluateResource("VM-001");
        platform.evaluateResource("APP-001");
        platform.evaluateResource("CRM-001");

        platform.generateReport();

        try {
            platform.createFinding(
                    "UNKNOWN",
                    SecurityDomain.DATA_PROTECTION,
                    FindingSeverity.HIGH,
                    "Invalid resource test"
            );
        } catch (IllegalArgumentException exception) {
            System.out.println("\nValidation test: " + exception.getMessage());
        }

        try {
            platform.updateFinding(
                    finding1.getFindingId(),
                    FindingStatus.RESOLVED,
                    "legacy-user"
            );
        } catch (SecurityException exception) {
            System.out.println("Authorization test: " + exception.getMessage());
        }
    }
}
