import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Container Security Enterprise Governance System.
 *
 * Java 17
 * No third-party dependencies.
 *
 * Features:
 * - Container image inventory
 * - Vulnerability assessment
 * - Secret detection
 * - Image hardening
 * - Policy-driven deployment authorization
 * - Runtime security
 * - Remediation management
 * - Audit records
 */
public class ContainerSecurityEnterprise {

    // ========================================================
    // 1. ENUMERATIONS
    // ========================================================

    enum Severity {
        CRITICAL,
        HIGH,
        MEDIUM,
        LOW,
        INFO
    }

    enum FindingType {
        VULNERABILITY,
        SECRET,
        MISCONFIGURATION,
        COMPLIANCE
    }

    enum DeploymentStatus {
        APPROVED,
        BLOCKED,
        REVIEW_REQUIRED
    }

    enum RemediationStatus {
        OPEN,
        IN_PROGRESS,
        MITIGATED,
        RESOLVED,
        ACCEPTED_RISK
    }

    enum RuntimeEventType {
        PROCESS_EXECUTION,
        FILE_MODIFICATION,
        NETWORK_CONNECTION,
        PRIVILEGE_CHANGE,
        UNKNOWN
    }

    // ========================================================
    // 2. CUSTOM EXCEPTIONS
    // ========================================================

    static class SecurityValidationException
            extends RuntimeException {

        SecurityValidationException(String message) {
            super(message);
        }
    }

    static class PolicyViolationException
            extends RuntimeException {

        PolicyViolationException(String message) {
            super(message);
        }
    }

    // ========================================================
    // 3. IMMUTABLE DOMAIN RECORDS
    // ========================================================

    record PackageInfo(
            String name,
            String version,
            String packageType
    ) {
        PackageInfo {
            if (name == null || name.isBlank() ||
                version == null || version.isBlank()) {
                throw new SecurityValidationException(
                    "Package name and version are required."
                );
            }

            packageType = Objects.requireNonNullElse(
                packageType,
                "APPLICATION"
            );
        }
    }

    record Vulnerability(
            String cve,
            String packageName,
            String installedVersion,
            Optional<String> fixedVersion,
            Severity severity,
            String description,
            boolean exploitable
    ) {
        Vulnerability {
            if (cve == null || !cve.matches("CVE-\\d{4}-\\d+")) {
                throw new SecurityValidationException(
                    "Invalid CVE identifier."
                );
            }

            if (packageName == null || packageName.isBlank()) {
                throw new SecurityValidationException(
                    "Package name is required."
                );
            }

            Objects.requireNonNull(severity);
            Objects.requireNonNull(fixedVersion);
        }
    }

    record Finding(
            FindingType type,
            Severity severity,
            String resource,
            String description,
            String remediation
    ) {
        Finding {
            Objects.requireNonNull(type);
            Objects.requireNonNull(severity);

            if (resource == null || resource.isBlank()) {
                throw new SecurityValidationException(
                    "Finding resource is required."
                );
            }
        }
    }

    record ScanReport(
            String imageReference,
            String imageDigest,
            Instant scannedAt,
            List<Finding> findings,
            DeploymentStatus status,
            Map<Severity, Long> severityCounts
    ) {
        ScanReport {
            findings = List.copyOf(findings);

            severityCounts = Collections.unmodifiableMap(
                new EnumMap<>(severityCounts)
            );
        }
    }

    // ========================================================
    // 4. CONTAINER IMAGE AGGREGATE
    // ========================================================

    static final class ContainerImage {

        private final String name;
        private final String tag;
        private final String baseImage;

        private final List<PackageInfo> packages;
        private final List<Vulnerability> vulnerabilities;

        private final Set<Integer> exposedPorts;
        private final Map<String, String> environment;
        private final Map<String, String> labels;

        private final String user;
        private final List<String> entrypoint;

        private final int layers;
        private final double sizeMB;

        private final boolean signed;
        private final boolean healthcheck;
        private final Optional<String> digest;

        ContainerImage(
                String name,
                String tag,
                String baseImage,
                List<PackageInfo> packages,
                List<Vulnerability> vulnerabilities,
                Set<Integer> exposedPorts,
                Map<String, String> environment,
                Map<String, String> labels,
                String user,
                List<String> entrypoint,
                int layers,
                double sizeMB,
                boolean signed,
                boolean healthcheck,
                Optional<String> digest
        ) {
            this.name = Objects.requireNonNull(name);
            this.tag = Objects.requireNonNull(tag);
            this.baseImage = Objects.requireNonNull(baseImage);

            this.packages = List.copyOf(packages);
            this.vulnerabilities = List.copyOf(vulnerabilities);

            this.exposedPorts = Set.copyOf(exposedPorts);
            this.environment = Map.copyOf(environment);
            this.labels = Map.copyOf(labels);

            this.user = Objects.requireNonNull(user);
            this.entrypoint = List.copyOf(entrypoint);

            this.layers = layers;
            this.sizeMB = sizeMB;

            this.signed = signed;
            this.healthcheck = healthcheck;
            this.digest = Objects.requireNonNull(digest);

            validate();
        }

        private void validate() {
            if (name.isBlank() || tag.isBlank() || baseImage.isBlank()) {
                throw new SecurityValidationException(
                    "Image identity is incomplete."
                );
            }

            if (layers < 1 || sizeMB <= 0) {
                throw new SecurityValidationException(
                    "Invalid image dimensions."
                );
            }

            Set<String> packageNames = packages.stream()
                .map(PackageInfo::name)
                .collect(Collectors.toSet());

            if (packageNames.size() != packages.size()) {
                throw new SecurityValidationException(
                    "Duplicate package names."
                );
            }

            for (int port : exposedPorts) {
                if (port < 1 || port > 65535) {
                    throw new SecurityValidationException(
                        "Invalid exposed port."
                    );
                }
            }
        }

        String reference() {
            return name + ":" + tag;
        }

        String user() {
            return user;
        }

        int layers() {
            return layers;
        }

        double sizeMB() {
            return sizeMB;
        }

        boolean signed() {
            return signed;
        }

        boolean healthcheck() {
            return healthcheck;
        }

        Optional<String> digest() {
            return digest;
        }

        List<Vulnerability> vulnerabilities() {
            return vulnerabilities;
        }

        Map<String, String> environment() {
            return environment;
        }

        List<String> entrypoint() {
            return entrypoint;
        }
    }

    // ========================================================
    // 5. IMAGE IDENTITY SERVICE
    // ========================================================

    static final class ImageIdentityService {

        String generateDigest(ContainerImage image) {
            String identity = image.reference()
                + "|" + image.baseImage
                + "|" + image.user
                + "|" + image.packages.stream()
                    .map(p -> p.name() + ":" + p.version())
                    .sorted()
                    .collect(Collectors.joining(","))
                + "|" + image.entrypoint;

            try {
                var digest = java.security.MessageDigest
                    .getInstance("SHA-256");

                byte[] hash = digest.digest(
                    identity.getBytes(
                        java.nio.charset.StandardCharsets.UTF_8
                    )
                );

                StringBuilder result = new StringBuilder("sha256:");

                for (byte b : hash) {
                    result.append(
                        String.format("%02x", b & 0xff)
                    );
                }

                return result.toString();

            } catch (java.security.NoSuchAlgorithmException e) {
                throw new IllegalStateException(
                    "SHA-256 is unavailable.", e
                );
            }
        }
    }

    // ========================================================
    // 6. VULNERABILITY ASSESSMENT SERVICE
    // ========================================================

    interface Scanner {
        List<Finding> scan(ContainerImage image);
    }

    static final class VulnerabilityScanner implements Scanner {

        @Override
        public List<Finding> scan(ContainerImage image) {
            return image.vulnerabilities().stream()
                .map(vulnerability -> new Finding(
                    FindingType.VULNERABILITY,
                    vulnerability.severity(),
                    vulnerability.packageName(),
                    vulnerability.cve() + ": "
                        + vulnerability.description(),
                    vulnerability.fixedVersion()
                        .map(version -> "Upgrade to " + version)
                        .orElse(
                            "Apply an approved mitigation or replace "
                            + "the affected package."
                        )
                ))
                .toList();
        }
    }

    // ========================================================
    // 7. SECRET SCANNING SERVICE
    // ========================================================

    static final class SecretScanner implements Scanner {

        private static final Map<String, Pattern> PATTERNS =
            Map.of(
                "AWS_ACCESS_KEY",
                Pattern.compile("\\bAKIA[0-9A-Z]{16}\\b"),

                "PRIVATE_KEY",
                Pattern.compile(
                    "-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
                ),

                "PASSWORD",
                Pattern.compile(
                    "(?i)(password|passwd|secret|api_key)\\s*=\\s*"
                    + "[^$\\s][^\\s]{5,}"
                ),

                "ACCESS_TOKEN",
                Pattern.compile(
                    "(?i)(access_token|auth_token)\\s*=\\s*"
                    + "[^$\\s][^\\s]{5,}"
                )
            );

        @Override
        public List<Finding> scan(ContainerImage image) {
            List<Finding> findings = new ArrayList<>();

            image.environment().forEach((key, value) -> {
                String combined = key + "=" + value;

                for (var entry : PATTERNS.entrySet()) {
                    if (entry.getValue().matcher(combined).find()) {
                        findings.add(new Finding(
                            FindingType.SECRET,
                            Severity.CRITICAL,
                            key,
                            "Potential " + entry.getKey()
                                + " exposure detected.",
                            "Remove and rotate the credential. "
                                + "Use a managed secret provider."
                        ));

                        break;
                    }
                }
            });

            return findings;
        }
    }

    // ========================================================
    // 8. MINIMAL IMAGE AND HARDENING SCANNER
    // ========================================================

    static final class ConfigurationScanner implements Scanner {

        @Override
        public List<Finding> scan(ContainerImage image) {
            List<Finding> findings = new ArrayList<>();

            if (Set.of("root", "0", "0:0")
                    .contains(image.user().toLowerCase())) {
                findings.add(new Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.HIGH,
                    "USER",
                    "Container runs as root.",
                    "Configure a non-root runtime user."
                ));
            }

            if (image.sizeMB() > 200) {
                findings.add(new Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.MEDIUM,
                    "IMAGE_SIZE",
                    "Image exceeds the 200 MB threshold.",
                    "Use a minimal runtime image."
                ));
            }

            if (image.layers() > 15) {
                findings.add(new Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.LOW,
                    "IMAGE_LAYERS",
                    "Image has excessive layers.",
                    "Reduce unnecessary build layers."
                ));
            }

            if (!image.signed()) {
                findings.add(new Finding(
                    FindingType.COMPLIANCE,
                    Severity.HIGH,
                    "SIGNATURE",
                    "Image signature is missing.",
                    "Sign the image and verify its provenance."
                ));
            }

            if (image.digest().isEmpty()) {
                findings.add(new Finding(
                    FindingType.COMPLIANCE,
                    Severity.MEDIUM,
                    "DIGEST",
                    "Immutable image digest is missing.",
                    "Deploy using a verified immutable digest."
                ));
            }

            if (!image.healthcheck()) {
                findings.add(new Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.LOW,
                    "HEALTHCHECK",
                    "Health check is missing.",
                    "Configure a meaningful health check."
                ));
            }

            if (image.entrypoint().isEmpty()) {
                findings.add(new Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.MEDIUM,
                    "ENTRYPOINT",
                    "Explicit entrypoint is missing.",
                    "Define an executable entrypoint."
                ));
            }

            return findings;
        }
    }

    // ========================================================
    // 9. ENTERPRISE REVIEW POLICY
    // ========================================================

    record ReviewPolicy(
            int maximumCritical,
            int maximumHigh,
            int maximumMedium,
            boolean requireNonRoot,
            boolean requireSignature,
            boolean requireDigest,
            boolean requireHealthcheck,
            boolean blockSecrets
    ) {
        ReviewPolicy {
            if (maximumCritical < 0 ||
                maximumHigh < 0 ||
                maximumMedium < 0) {
                throw new SecurityValidationException(
                    "Policy thresholds cannot be negative."
                );
            }
        }

        static ReviewPolicy production() {
            return new ReviewPolicy(
                0,
                0,
                3,
                true,
                true,
                true,
                true,
                true
            );
        }
    }

    // ========================================================
    // 10. POLICY EVALUATION SERVICE
    // ========================================================

    static final class PolicyEvaluationService {

        private final ReviewPolicy policy;

        PolicyEvaluationService(ReviewPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
        }

        DeploymentStatus evaluate(
                ContainerImage image,
                List<Finding> findings
        ) {
            Map<Severity, Long> counts = findings.stream()
                .collect(Collectors.groupingBy(
                    Finding::severity,
                    () -> new EnumMap<>(Severity.class),
                    Collectors.counting()
                ));

            long critical = counts.getOrDefault(
                Severity.CRITICAL, 0L
            );

            long high = counts.getOrDefault(
                Severity.HIGH, 0L
            );

            long medium = counts.getOrDefault(
                Severity.MEDIUM, 0L
            );

            if (critical > policy.maximumCritical() ||
                high > policy.maximumHigh() ||
                medium > policy.maximumMedium()) {
                return DeploymentStatus.BLOCKED;
            }

            if (policy.blockSecrets() &&
                findings.stream().anyMatch(
                    f -> f.type() == FindingType.SECRET
                )) {
                return DeploymentStatus.BLOCKED;
            }

            if (policy.requireNonRoot() &&
                Set.of("root", "0", "0:0")
                    .contains(image.user().toLowerCase())) {
                return DeploymentStatus.BLOCKED;
            }

            if (policy.requireSignature() && !image.signed()) {
                return DeploymentStatus.BLOCKED;
            }

            if (policy.requireDigest() && image.digest().isEmpty()) {
                return DeploymentStatus.BLOCKED;
            }

            if (policy.requireHealthcheck() &&
                !image.healthcheck()) {
                return DeploymentStatus.BLOCKED;
            }

            return DeploymentStatus.APPROVED;
        }
    }

    // ========================================================
    // 11. IMAGE SCANNING ORCHESTRATION
    // ========================================================

    static final class ImageScanningService {

        private final List<Scanner> scanners;
        private final PolicyEvaluationService policyService;
        private final ImageIdentityService identityService;

        ImageScanningService(
                ReviewPolicy policy,
                ImageIdentityService identityService
        ) {
            this.scanners = List.of(
                new VulnerabilityScanner(),
                new SecretScanner(),
                new ConfigurationScanner()
            );

            this.policyService =
                new PolicyEvaluationService(policy);

            this.identityService = identityService;
        }

        ScanReport scan(ContainerImage image) {
            List<Finding> findings = scanners.stream()
                .flatMap(scanner -> scanner.scan(image).stream())
                .toList();

            DeploymentStatus status =
                policyService.evaluate(image, findings);

            Map<Severity, Long> counts =
                new EnumMap<>(Severity.class);

            for (Severity severity : Severity.values()) {
                counts.put(
                    severity,
                    findings.stream()
                        .filter(f -> f.severity() == severity)
                        .count()
                );
            }

            return new ScanReport(
                image.reference(),
                identityService.generateDigest(image),
                Instant.now(),
                findings,
                status,
                counts
            );
        }
    }

    // ========================================================
    // 12. RUNTIME SECURITY
    // ========================================================

    record RuntimeEvent(
            String containerId,
            RuntimeEventType type,
            String process,
            String destination,
            boolean privileged
    ) {
        RuntimeEvent {
            if (containerId == null || containerId.isBlank()) {
                throw new SecurityValidationException(
                    "Container ID is required."
                );
            }

            Objects.requireNonNull(type);
            Objects.requireNonNull(process);
        }
    }

    record RuntimeDecision(
            boolean allowed,
            Severity severity,
            String reason
    ) {}

    static final class RuntimeSecurityService {

        private final Set<String> blockedProcesses = Set.of(
            "nc",
            "ncat",
            "socat",
            "tcpdump",
            "chroot"
        );

        private final Set<String> protectedPaths = Set.of(
            "/etc/shadow",
            "/etc/passwd",
            "/root/.ssh/authorized_keys"
        );

        RuntimeDecision evaluate(RuntimeEvent event) {
            if (event.privileged()) {
                return new RuntimeDecision(
                    false,
                    Severity.CRITICAL,
                    "Unexpected privileged operation."
                );
            }

            if (event.type() ==
                    RuntimeEventType.PROCESS_EXECUTION) {

                String executable = event.process()
                    .substring(
                        event.process().lastIndexOf('/') + 1
                    )
                    .toLowerCase();

                if (blockedProcesses.contains(executable)) {
                    return new RuntimeDecision(
                        false,
                        Severity.HIGH,
                        "Restricted executable detected."
                    );
                }
            }

            if (event.type() ==
                    RuntimeEventType.FILE_MODIFICATION &&
                protectedPaths.contains(event.destination())) {

                return new RuntimeDecision(
                    false,
                    Severity.CRITICAL,
                    "Protected file modification detected."
                );
            }

            if (event.type() == RuntimeEventType.UNKNOWN) {
                return new RuntimeDecision(
                    false,
                    Severity.HIGH,
                    "Unrecognized runtime behavior."
                );
            }

            return new RuntimeDecision(
                true,
                Severity.INFO,
                "Runtime activity permitted."
            );
        }
    }

    // ========================================================
    // 13. REMEDIATION STATE MACHINE
    // ========================================================

    record RemediationHistory(
            RemediationStatus previous,
            RemediationStatus next,
            Instant timestamp
    ) {}

    static final class RemediationService {

        private static final Map<RemediationStatus,
                Set<RemediationStatus>> TRANSITIONS = Map.of(
            RemediationStatus.OPEN,
            Set.of(
                RemediationStatus.IN_PROGRESS,
                RemediationStatus.ACCEPTED_RISK
            ),

            RemediationStatus.IN_PROGRESS,
            Set.of(
                RemediationStatus.MITIGATED,
                RemediationStatus.RESOLVED,
                RemediationStatus.ACCEPTED_RISK
            ),

            RemediationStatus.MITIGATED,
            Set.of(
                RemediationStatus.RESOLVED,
                RemediationStatus.IN_PROGRESS
            ),

            RemediationStatus.RESOLVED,
            Set.of(RemediationStatus.OPEN),

            RemediationStatus.ACCEPTED_RISK,
            Set.of(
                RemediationStatus.OPEN,
                RemediationStatus.IN_PROGRESS
            )
        );

        private final String ticketId;
        private final String cve;
        private final String owner;
        private final LocalDate dueDate;

        private RemediationStatus status =
            RemediationStatus.OPEN;

        private final List<RemediationHistory> history =
            new ArrayList<>();

        RemediationService(
                String ticketId,
                String cve,
                String owner,
                LocalDate dueDate
        ) {
            this.ticketId = Objects.requireNonNull(ticketId);
            this.cve = Objects.requireNonNull(cve);
            this.owner = Objects.requireNonNull(owner);
            this.dueDate = Objects.requireNonNull(dueDate);

            if (ticketId.isBlank() || owner.isBlank()) {
                throw new SecurityValidationException(
                    "Ticket ID and owner are required."
                );
            }
        }

        void transition(RemediationStatus next) {
            if (!TRANSITIONS.get(status).contains(next)) {
                throw new PolicyViolationException(
                    "Invalid transition: " + status + " -> " + next
                );
            }

            history.add(new RemediationHistory(
                status,
                next,
                Instant.now()
            ));

            status = next;
        }

        RemediationStatus status() {
            return status;
        }

        List<RemediationHistory> history() {
            return List.copyOf(history);
        }

        String ticketId() {
            return ticketId;
        }

        String cve() {
            return cve;
        }

        String owner() {
            return owner;
        }

        LocalDate dueDate() {
            return dueDate;
        }
    }

    // ========================================================
    // 14. ENTERPRISE AUDIT SERVICE
    // ========================================================

    record AuditEvent(
            String eventId,
            String action,
            String resource,
            Instant timestamp,
            String actor
    ) {}

    static final class AuditService {

        private final List<AuditEvent> events =
            new ArrayList<>();

        void record(String action, String resource, String actor) {
            if (action == null || resource == null ||
                actor == null || actor.isBlank()) {
                throw new SecurityValidationException(
                    "Audit event fields are mandatory."
                );
            }

            events.add(new AuditEvent(
                UUID.randomUUID().toString(),
                action,
                resource,
                Instant.now(),
                actor
            ));
        }

        List<AuditEvent> getEvents() {
            return List.copyOf(events);
        }
    }

    // ========================================================
    // 15. SAMPLE IMAGE DATA
    // ========================================================

    static ContainerImage unsafeImage() {
        return new ContainerImage(
            "order-service",
            "latest",
            "ubuntu:latest",

            List.of(
                new PackageInfo("openssl", "1.0.2", "OS"),
                new PackageInfo("curl", "7.50.0", "OS"),
                new PackageInfo("python", "3.12", "APPLICATION")
            ),

            List.of(
                new Vulnerability(
                    "CVE-2025-10001",
                    "openssl",
                    "1.0.2",
                    Optional.of("3.0.15"),
                    Severity.CRITICAL,
                    "Critical cryptographic vulnerability.",
                    true
                ),

                new Vulnerability(
                    "CVE-2025-10002",
                    "curl",
                    "7.50.0",
                    Optional.of("8.10.0"),
                    Severity.HIGH,
                    "Network request vulnerability.",
                    false
                )
            ),

            Set.of(22, 8080),

            Map.of(
                "DATABASE_PASSWORD",
                "production_password_123"
            ),

            Map.of(
                "environment",
                "production"
            ),

            "root",

            List.of("python", "app.py"),

            24,
            850,

            false,
            false,
            Optional.empty()
        );
    }

    static ContainerImage secureImage() {
        return new ContainerImage(
            "order-service",
            "2.1.0",
            "python:3.12-slim",

            List.of(
                new PackageInfo("python", "3.12", "RUNTIME"),
                new PackageInfo("application", "2.1.0", "APPLICATION")
            ),

            List.of(),

            Set.of(8080),

            Map.of(
                "APP_MODE", "production",
                "DATABASE_HOST", "database.internal"
            ),

            Map.of(
                "environment", "production",
                "owner", "platform-team"
            ),

            "10001",

            List.of(
                "python",
                "-m",
                "order_service"
            ),

            7,
            95,

            true,
            true,
            Optional.of("sha256:verified-production-digest")
        );
    }

    // ========================================================
    // 16. REPORTING
    // ========================================================

    static void printReport(ScanReport report) {
        System.out.println("\n======================================");
        System.out.println("IMAGE: " + report.imageReference());
        System.out.println("DIGEST: " + report.imageDigest());
        System.out.println("STATUS: " + report.status());
        System.out.println("======================================");

        report.severityCounts().forEach(
            (severity, count) ->
                System.out.println(severity + ": " + count)
        );

        for (Finding finding : report.findings()) {
            System.out.println(
                "\n[" + finding.severity() + "] "
                    + finding.type()
            );

            System.out.println("Resource: " + finding.resource());
            System.out.println("Issue: " + finding.description());
            System.out.println(
                "Remediation: " + finding.remediation()
            );
        }
    }

    // ========================================================
    // 17. AUTOMATED TESTS
    // ========================================================

    static void runTests() {
        ImageIdentityService identity =
            new ImageIdentityService();

        ImageScanningService scanner =
            new ImageScanningService(
                ReviewPolicy.production(),
                identity
            );

        ScanReport unsafe = scanner.scan(unsafeImage());
        ScanReport secure = scanner.scan(secureImage());

        if (unsafe.status() != DeploymentStatus.BLOCKED) {
            throw new AssertionError("Unsafe image was not blocked.");
        }

        if (secure.status() != DeploymentStatus.APPROVED) {
            throw new AssertionError("Secure image was not approved.");
        }

        boolean secretDetected = unsafe.findings().stream()
            .anyMatch(f -> f.type() == FindingType.SECRET);

        if (!secretDetected) {
            throw new AssertionError("Secret was not detected.");
        }

        RuntimeSecurityService runtime =
            new RuntimeSecurityService();

        RuntimeDecision permitted = runtime.evaluate(
            new RuntimeEvent(
                "container-101",
                RuntimeEventType.PROCESS_EXECUTION,
                "/usr/local/bin/python",
                null,
                false
            )
        );

        RuntimeDecision prohibited = runtime.evaluate(
            new RuntimeEvent(
                "container-101",
                RuntimeEventType.PROCESS_EXECUTION,
                "/usr/bin/nc",
                null,
                false
            )
        );

        if (!permitted.allowed() || prohibited.allowed()) {
            throw new AssertionError(
                "Runtime policy evaluation failed."
            );
        }

        RemediationService remediation =
            new RemediationService(
                "SEC-1001",
                "CVE-2025-10001",
                "platform-team",
                LocalDate.of(2026, 11, 25)
            );

        remediation.transition(RemediationStatus.IN_PROGRESS);

        if (remediation.status() != RemediationStatus.IN_PROGRESS) {
            throw new AssertionError(
                "Remediation transition failed."
            );
        }

        boolean invalidTransitionRejected = false;

        try {
            remediation.transition(RemediationStatus.OPEN);
        } catch (PolicyViolationException exception) {
            invalidTransitionRejected = true;
        }

        if (!invalidTransitionRejected) {
            throw new AssertionError(
                "Invalid transition was accepted."
            );
        }

        System.out.println("All Java 17 security tests passed.");
    }

    // ========================================================
    // 18. APPLICATION ENTRY POINT
    // ========================================================

    public static void main(String[] args) {
        try {
            runTests();

            ImageIdentityService identity =
                new ImageIdentityService();

            ImageScanningService scanning =
                new ImageScanningService(
                    ReviewPolicy.production(),
                    identity
                );

            List<ContainerImage> inventory = List.of(
                unsafeImage(),
                secureImage()
            );

            List<ScanReport> reports = inventory.stream()
                .map(scanning::scan)
                .toList();

            reports.forEach(
                ContainerSecurityEnterprise::printReport
            );

            RuntimeSecurityService runtime =
                new RuntimeSecurityService();

            List<RuntimeEvent> events = List.of(
                new RuntimeEvent(
                    "container-101",
                    RuntimeEventType.PROCESS_EXECUTION,
                    "/usr/local/bin/python",
                    null,
                    false
                ),

                new RuntimeEvent(
                    "container-101",
                    RuntimeEventType.FILE_MODIFICATION,
                    "file-writer",
                    "/etc/shadow",
                    false
                ),

                new RuntimeEvent(
                    "container-101",
                    RuntimeEventType.PRIVILEGE_CHANGE,
                    "privilege-escalation",
                    null,
                    true
                )
            );

            System.out.println("\nRUNTIME SECURITY");

            for (RuntimeEvent event : events) {
                RuntimeDecision decision =
                    runtime.evaluate(event);

                System.out.println(
                    (decision.allowed() ? "ALLOW" : "BLOCK")
                        + " | " + decision.severity()
                        + " | " + decision.reason()
                );
            }

            AuditService audit = new AuditService();

            for (ScanReport report : reports) {
                audit.record(
                    "IMAGE_SCAN_" + report.status(),
                    report.imageReference(),
                    "security-pipeline"
                );
            }

            System.out.println(
                "\nAudit records: " + audit.getEvents().size()
            );

        } catch (SecurityValidationException |
                 PolicyViolationException exception) {

            System.err.println(
                "Security policy failure: " + exception.getMessage()
            );

            System.exit(1);

        } catch (Exception exception) {
            System.err.println(
                "Application failure: " + exception.getMessage()
            );

            System.exit(2);
        }
    }
}
