import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Cloud Security Monitoring
 *
 * Enterprise-oriented cloud security monitoring platform.
 *
 * Java 17
 * Standard library only.
 *
 * Features:
 * - Immutable audit event records
 * - Structured cloud audit processing
 * - Authentication and authorization monitoring
 * - Sliding-window detection
 * - User behavior baselines
 * - Resource classification policies
 * - Risk scoring
 * - Alert correlation
 * - Incident lifecycle management
 * - Evidence integrity fingerprints
 * - Analyst assignment
 * - Security reporting
 * - Validation and exception handling
 */
public class CloudSecurityMonitoring {

    // =====================================================
    // ENUMERATIONS
    // =====================================================

    enum EventType {
        LOGIN,
        LOGOUT,
        FAILED_LOGIN,
        API_ACCESS,
        PERMISSION_CHANGE,
        RESOURCE_CREATED,
        RESOURCE_DELETED,
        CONFIGURATION_CHANGE,
        DATA_ACCESS,
        SECRET_ACCESS,
        NETWORK_ACCESS
    }

    enum Severity {
        LOW,
        MEDIUM,
        HIGH,
        CRITICAL
    }

    enum IncidentStatus {
        OPEN,
        INVESTIGATING,
        CONTAINED,
        RESOLVED,
        CLOSED
    }

    enum ReviewOutcome {
        NOT_REVIEWED,
        CONFIRMED,
        FALSE_POSITIVE,
        ESCALATED
    }

    // =====================================================
    // EXCEPTIONS
    // =====================================================

    static class MonitoringException extends RuntimeException {
        MonitoringException(String message) {
            super(message);
        }
    }

    static class ValidationException extends MonitoringException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class PolicyViolationException
            extends MonitoringException {
        PolicyViolationException(String message) {
            super(message);
        }
    }

    static class IncidentStateException
            extends MonitoringException {
        IncidentStateException(String message) {
            super(message);
        }
    }

    // =====================================================
    // IDENTIFIER VALIDATION
    // =====================================================

    private static final Pattern IP_PATTERN = Pattern.compile(
        "^(?:(?:25[0-5]|2[0-4][0-9]|1?[0-9]?[0-9])\\.){3}" +
        "(?:25[0-5]|2[0-4][0-9]|1?[0-9]?[0-9])$"
    );

    private static final int MAX_METADATA_FIELDS = 50;

    private static String requireText(
            String value,
            String field) {

        if (
            value == null ||
            value.isBlank() ||
            value.length() > 256
        ) {
            throw new ValidationException(
                "Invalid field: " + field
            );
        }

        return value;
    }

    private static Severity classify(int score) {
        if (score >= 90) return Severity.CRITICAL;
        if (score >= 70) return Severity.HIGH;
        if (score >= 40) return Severity.MEDIUM;
        return Severity.LOW;
    }

    // =====================================================
    // IMMUTABLE EVENT MODEL
    // =====================================================

    record SecurityEvent(
        String eventId,
        Instant timestamp,
        EventType eventType,
        String userId,
        String sourceIp,
        String resource,
        String action,
        boolean success,
        String region,
        Map<String, Object> metadata
    ) {

        SecurityEvent {
            requireText(eventId, "eventId");
            requireText(userId, "userId");
            requireText(resource, "resource");
            requireText(action, "action");
            requireText(region, "region");

            Objects.requireNonNull(
                timestamp,
                "timestamp"
            );

            Objects.requireNonNull(
                eventType,
                "eventType"
            );

            if (
                !IP_PATTERN.matcher(
                    Objects.requireNonNull(sourceIp)
                ).matches()
            ) {
                throw new ValidationException(
                    "Invalid IPv4 address."
                );
            }

            Instant now = Instant.now();

            if (timestamp.isAfter(now.plus(Duration.ofMinutes(5)))) {
                throw new ValidationException(
                    "Event timestamp is in the future."
                );
            }

            if (timestamp.isBefore(
                now.minus(Duration.ofDays(365))
            )) {
                throw new ValidationException(
                    "Event exceeds accepted retention window."
                );
            }

            metadata = metadata == null
                ? Map.of()
                : Collections.unmodifiableMap(
                    new HashMap<>(metadata)
                );

            if (metadata.size() > MAX_METADATA_FIELDS) {
                throw new ValidationException(
                    "Too many metadata fields."
                );
            }
        }
    }

    // =====================================================
    // POLICY OBJECTS
    // =====================================================

    record MonitoringPolicy(
        int failedLoginThreshold,
        int privilegeChangeThreshold,
        Duration failedLoginWindow,
        Duration privilegeChangeWindow,
        int criticalRiskThreshold,
        boolean requireApprovedPrivilegeChanges
    ) {

        MonitoringPolicy {
            if (
                failedLoginThreshold < 1 ||
                privilegeChangeThreshold < 1 ||
                criticalRiskThreshold < 1 ||
                criticalRiskThreshold > 100
            ) {
                throw new ValidationException(
                    "Invalid monitoring policy thresholds."
                );
            }

            Objects.requireNonNull(failedLoginWindow);
            Objects.requireNonNull(privilegeChangeWindow);

            if (
                failedLoginWindow.isNegative() ||
                failedLoginWindow.isZero() ||
                privilegeChangeWindow.isNegative() ||
                privilegeChangeWindow.isZero()
            ) {
                throw new ValidationException(
                    "Detection windows must be positive."
                );
            }
        }

        static MonitoringPolicy defaults() {
            return new MonitoringPolicy(
                5,
                3,
                Duration.ofMinutes(10),
                Duration.ofMinutes(15),
                90,
                true
            );
        }
    }

    static class ResourcePolicy {

        private final Map<String, Integer> sensitivity =
            new HashMap<>();

        void register(
                String resource,
                int level) {

            requireText(resource, "resource");

            if (level < 1 || level > 5) {
                throw new ValidationException(
                    "Sensitivity must be between 1 and 5."
                );
            }

            sensitivity.put(resource, level);
        }

        int sensitivityOf(String resource) {
            return sensitivity.getOrDefault(resource, 1);
        }

        boolean requiresMfa(String resource) {
            return sensitivityOf(resource) >= 4;
        }
    }

    // =====================================================
    // ALERT MODEL
    // =====================================================

    record SecurityAlert(
        String alertId,
        String ruleId,
        Instant timestamp,
        String userId,
        Severity severity,
        int riskScore,
        String description,
        List<String> eventIds,
        Map<String, String> indicators
    ) {

        SecurityAlert {
            requireText(alertId, "alertId");
            requireText(ruleId, "ruleId");

            Objects.requireNonNull(severity);
            Objects.requireNonNull(timestamp);

            if (riskScore < 0 || riskScore > 100) {
                throw new ValidationException(
                    "Invalid risk score."
                );
            }

            eventIds = List.copyOf(eventIds);
            indicators = Map.copyOf(indicators);
        }
    }

    // =====================================================
    // SLIDING WINDOW DETECTOR
    // =====================================================

    static class SlidingWindowCounter {

        private final Duration window;

        private final Map<String, Deque<Instant>> counters =
            new HashMap<>();

        SlidingWindowCounter(Duration window) {
            this.window = window;
        }

        synchronized int add(
                String key,
                Instant timestamp) {

            Deque<Instant> queue = counters.computeIfAbsent(
                key,
                ignored -> new ArrayDeque<>()
            );

            queue.addLast(timestamp);

            Instant cutoff = timestamp.minus(window);

            while (
                !queue.isEmpty() &&
                queue.peekFirst().isBefore(cutoff)
            ) {
                queue.removeFirst();
            }

            return queue.size();
        }
    }

    // =====================================================
    // BEHAVIORAL BASELINE
    // =====================================================

    static class UserBehaviorBaseline {

        private final Map<String, Set<String>> userIPs =
            new HashMap<>();

        private final Map<String, Set<Integer>> userHours =
            new HashMap<>();

        synchronized void observe(SecurityEvent event) {
            if (!event.success()) return;

            userIPs.computeIfAbsent(
                event.userId(),
                ignored -> new HashSet<>()
            ).add(event.sourceIp());

            userHours.computeIfAbsent(
                event.userId(),
                ignored -> new HashSet<>()
            ).add(
                event.timestamp().atZone(
                    java.time.ZoneOffset.UTC
                ).getHour()
            );
        }

        boolean unfamiliarIP(SecurityEvent event) {
            Set<String> known = userIPs.get(
                event.userId()
            );

            return known != null &&
                !known.isEmpty() &&
                !known.contains(event.sourceIp());
        }

        boolean unusualHour(SecurityEvent event) {
            Set<Integer> known = userHours.get(
                event.userId()
            );

            if (known == null || known.isEmpty()) {
                return false;
            }

            int hour = event.timestamp()
                .atZone(java.time.ZoneOffset.UTC)
                .getHour();

            return !known.contains(hour);
        }
    }

    // =====================================================
    // ALERT CORRELATION
    // =====================================================

    record CorrelationKey(
        String userId,
        String ruleId
    ) {}

    static class AlertCorrelationService {

        private final Map<CorrelationKey, List<SecurityAlert>>
            groupedAlerts = new LinkedHashMap<>();

        synchronized void add(SecurityAlert alert) {
            CorrelationKey key = new CorrelationKey(
                alert.userId(),
                alert.ruleId()
            );

            groupedAlerts.computeIfAbsent(
                key,
                ignored -> new ArrayList<>()
            ).add(alert);
        }

        Map<CorrelationKey, Integer> getCounts() {
            Map<CorrelationKey, Integer> result =
                new LinkedHashMap<>();

            groupedAlerts.forEach(
                (key, alerts) ->
                    result.put(key, alerts.size())
            );

            return result;
        }

        List<SecurityAlert> allAlerts() {
            return groupedAlerts.values()
                .stream()
                .flatMap(List::stream)
                .toList();
        }
    }

    // =====================================================
    // DETECTION SERVICE
    // =====================================================

    static class DetectionService {

        private final MonitoringPolicy policy;

        private final SlidingWindowCounter failedLogins;
        private final SlidingWindowCounter permissionChanges;

        private final UserBehaviorBaseline baseline =
            new UserBehaviorBaseline();

        private final AlertCorrelationService correlation =
            new AlertCorrelationService();

        DetectionService(MonitoringPolicy policy) {
            this.policy = policy;

            failedLogins = new SlidingWindowCounter(
                policy.failedLoginWindow()
            );

            permissionChanges = new SlidingWindowCounter(
                policy.privilegeChangeWindow()
            );
        }

        private SecurityAlert createAlert(
                SecurityEvent event,
                String ruleId,
                int score,
                String description) {

            SecurityAlert alert = new SecurityAlert(
                UUID.randomUUID().toString(),
                ruleId,
                event.timestamp(),
                event.userId(),
                classify(score),
                score,
                description,
                List.of(event.eventId()),
                Map.of(
                    "sourceIp", event.sourceIp(),
                    "resource", event.resource()
                )
            );

            correlation.add(alert);

            return alert;
        }

        List<SecurityAlert> evaluate(
                SecurityEvent event,
                ResourcePolicy resources) {

            List<SecurityAlert> alerts =
                new ArrayList<>();

            if (
                event.eventType() ==
                EventType.FAILED_LOGIN
            ) {
                int count = failedLogins.add(
                    event.userId(),
                    event.timestamp()
                );

                if (count >= policy.failedLoginThreshold()) {
                    alerts.add(
                        createAlert(
                            event,
                            "AUTH-001",
                            85,
                            "Repeated authentication failures."
                        )
                    );
                }
            }

            if (
                event.eventType() ==
                EventType.PERMISSION_CHANGE
            ) {
                int count = permissionChanges.add(
                    event.userId(),
                    event.timestamp()
                );

                if (
                    count >=
                    policy.privilegeChangeThreshold()
                ) {
                    alerts.add(
                        createAlert(
                            event,
                            "IAM-001",
                            95,
                            "Rapid privilege modifications."
                        )
                    );
                }

                if (
                    policy.requireApprovedPrivilegeChanges() &&
                    !Boolean.TRUE.equals(
                        event.metadata().get("approvedChange")
                    )
                ) {
                    alerts.add(
                        createAlert(
                            event,
                            "IAM-002",
                            95,
                            "Unapproved privilege modification."
                        )
                    );
                }
            }

            if (
                event.eventType() == EventType.SECRET_ACCESS &&
                event.success() &&
                !Boolean.TRUE.equals(
                    event.metadata().get("approved")
                )
            ) {
                alerts.add(
                    createAlert(
                        event,
                        "DATA-001",
                        95,
                        "Unapproved sensitive secret access."
                    )
                );
            }

            if (
                event.success() &&
                baseline.unfamiliarIP(event)
            ) {
                alerts.add(
                    createAlert(
                        event,
                        "ANOM-001",
                        75,
                        "Successful access from unfamiliar IP."
                    )
                );
            }

            if (
                event.success() &&
                baseline.unusualHour(event)
            ) {
                alerts.add(
                    createAlert(
                        event,
                        "ANOM-002",
                        65,
                        "Access outside normal activity hours."
                    )
                );
            }

            if (
                event.success() &&
                resources.requiresMfa(event.resource()) &&
                !Boolean.TRUE.equals(
                    event.metadata().get("mfa")
                )
            ) {
                alerts.add(
                    createAlert(
                        event,
                        "IAM-003",
                        90,
                        "Sensitive access without MFA."
                    )
                );
            }

            baseline.observe(event);

            return alerts;
        }

        AlertCorrelationService correlation() {
            return correlation;
        }
    }

    // =====================================================
    // INCIDENT DOMAIN
    // =====================================================

    static class SecurityIncident {

        private final String incidentId;
        private final String title;
        private final Severity severity;
        private final Instant createdAt;

        private Instant updatedAt;
        private IncidentStatus status;
        private ReviewOutcome reviewOutcome;

        private String assignedAnalyst;

        private final List<String> alertIds =
            new ArrayList<>();

        private final List<String> evidenceHashes =
            new ArrayList<>();

        private final List<String> investigationNotes =
            new ArrayList<>();

        SecurityIncident(SecurityAlert alert) {
            incidentId = UUID.randomUUID().toString();
            title = alert.description();
            severity = alert.severity();
            createdAt = alert.timestamp();
            updatedAt = alert.timestamp();

            status = IncidentStatus.OPEN;
            reviewOutcome = ReviewOutcome.NOT_REVIEWED;

            alertIds.add(alert.alertId());
        }

        synchronized void transition(
                IncidentStatus next) {

            Map<IncidentStatus, Set<IncidentStatus>>
                transitions = Map.of(
                    IncidentStatus.OPEN,
                    Set.of(
                        IncidentStatus.INVESTIGATING,
                        IncidentStatus.CLOSED
                    ),

                    IncidentStatus.INVESTIGATING,
                    Set.of(
                        IncidentStatus.CONTAINED,
                        IncidentStatus.RESOLVED,
                        IncidentStatus.CLOSED
                    ),

                    IncidentStatus.CONTAINED,
                    Set.of(
                        IncidentStatus.INVESTIGATING,
                        IncidentStatus.RESOLVED
                    ),

                    IncidentStatus.RESOLVED,
                    Set.of(
                        IncidentStatus.CLOSED,
                        IncidentStatus.INVESTIGATING
                    ),

                    IncidentStatus.CLOSED,
                    Set.of()
                );

            if (
                !transitions.get(status).contains(next)
            ) {
                throw new IncidentStateException(
                    "Invalid transition: " +
                    status + " -> " + next
                );
            }

            status = next;
            updatedAt = Instant.now();
        }

        synchronized void assign(String analyst) {
            requireText(analyst, "analyst");

            if (status == IncidentStatus.CLOSED) {
                throw new IncidentStateException(
                    "Cannot assign a closed incident."
                );
            }

            assignedAnalyst = analyst;
        }

        synchronized void addEvidence(String content) {
            if (
                content == null ||
                content.isBlank() ||
                content.length() > 100000
            ) {
                throw new ValidationException(
                    "Invalid evidence."
                );
            }

            if (status == IncidentStatus.CLOSED) {
                throw new IncidentStateException(
                    "Closed incidents cannot accept evidence."
                );
            }

            try {
                var digest = java.security.MessageDigest
                    .getInstance("SHA-256");

                byte[] hash = digest.digest(
                    content.getBytes(
                        java.nio.charset.StandardCharsets.UTF_8
                    )
                );

                evidenceHashes.add(
                    java.util.HexFormat.of().formatHex(hash)
                );

            } catch (
                java.security.NoSuchAlgorithmException exception
            ) {
                throw new MonitoringException(
                    "SHA-256 is unavailable."
                );
            }

            updatedAt = Instant.now();
        }

        synchronized void addNote(String note) {
            if (
                note == null ||
                note.isBlank() ||
                note.length() > 5000
            ) {
                throw new ValidationException(
                    "Invalid investigation note."
                );
            }

            if (status == IncidentStatus.CLOSED) {
                throw new IncidentStateException(
                    "Closed incident cannot be modified."
                );
            }

            investigationNotes.add(note);
            updatedAt = Instant.now();
        }

        synchronized void recordReview(
                ReviewOutcome outcome) {

            if (status == IncidentStatus.CLOSED) {
                throw new IncidentStateException(
                    "Closed incident cannot be reviewed."
                );
            }

            reviewOutcome = Objects.requireNonNull(outcome);
        }

        String incidentId() {
            return incidentId;
        }

        String title() {
            return title;
        }

        Severity severity() {
            return severity;
        }

        IncidentStatus status() {
            return status;
        }

        ReviewOutcome reviewOutcome() {
            return reviewOutcome;
        }

        String assignedAnalyst() {
            return assignedAnalyst;
        }
    }

    // =====================================================
    // INCIDENT SERVICE
    // =====================================================

    static class IncidentService {

        private final Map<String, SecurityIncident> incidents =
            new LinkedHashMap<>();

        synchronized SecurityIncident create(
                SecurityAlert alert) {

            SecurityIncident incident =
                new SecurityIncident(alert);

            incidents.put(
                incident.incidentId(),
                incident
            );

            return incident;
        }

        synchronized SecurityIncident get(String id) {
            SecurityIncident incident = incidents.get(id);

            if (incident == null) {
                throw new MonitoringException(
                    "Incident does not exist: " + id
                );
            }

            return incident;
        }

        List<SecurityIncident> all() {
            return List.copyOf(incidents.values());
        }

        Map<IncidentStatus, Long> aggregateByStatus() {
            return incidents.values()
                .stream()
                .collect(
                    Collectors.groupingBy(
                        SecurityIncident::status,
                        Collectors.counting()
                    )
                );
        }
    }

    // =====================================================
    // AUDIT REPOSITORY
    // =====================================================

    interface AuditRepository {
        void append(SecurityEvent event);
        List<SecurityEvent> findAll();
    }

    static class InMemoryAuditRepository
            implements AuditRepository {

        private final List<SecurityEvent> events =
            new ArrayList<>();

        private final Set<String> eventIds =
            new HashSet<>();

        @Override
        public synchronized void append(
                SecurityEvent event) {

            if (!eventIds.add(event.eventId())) {
                throw new ValidationException(
                    "Duplicate audit event."
                );
            }

            events.add(event);
        }

        @Override
        public synchronized List<SecurityEvent> findAll() {
            return List.copyOf(events);
        }
    }

    // =====================================================
    // CENTRAL ENTERPRISE SERVICE
    // =====================================================

    static class CloudSecurityService {

        private final MonitoringPolicy policy;

        private final ResourcePolicy resources =
            new ResourcePolicy();

        private final AuditRepository audit;

        private final DetectionService detection;

        private final IncidentService incidents =
            new IncidentService();

        CloudSecurityService(
                MonitoringPolicy policy,
                AuditRepository audit) {

            this.policy = policy;
            this.audit = audit;

            detection = new DetectionService(policy);

            resources.register(
                "production/iam",
                5
            );

            resources.register(
                "production/database",
                5
            );

            resources.register(
                "development/logs",
                2
            );
        }

        synchronized List<SecurityAlert> ingest(
                SecurityEvent event) {

            Objects.requireNonNull(event);

            // Audit persistence precedes detection.
            audit.append(event);

            List<SecurityAlert> alerts =
                detection.evaluate(event, resources);

            alerts.forEach(incidents::create);

            return List.copyOf(alerts);
        }

        Map<String, Object> report() {
            List<SecurityAlert> alerts =
                detection.correlation().allAlerts();

            Map<Severity, Long> severityCounts =
                alerts.stream().collect(
                    Collectors.groupingBy(
                        SecurityAlert::severity,
                        Collectors.counting()
                    )
                );

            Map<EventType, Long> eventCounts =
                audit.findAll().stream().collect(
                    Collectors.groupingBy(
                        SecurityEvent::eventType,
                        Collectors.counting()
                    )
                );

            Map<String, Object> report =
                new LinkedHashMap<>();

            report.put(
                "totalEvents",
                audit.findAll().size()
            );

            report.put(
                "totalAlerts",
                alerts.size()
            );

            report.put(
                "totalIncidents",
                incidents.all().size()
            );

            report.put(
                "eventsByType",
                eventCounts
            );

            report.put(
                "alertsBySeverity",
                severityCounts
            );

            report.put(
                "incidentsByStatus",
                incidents.aggregateByStatus()
            );

            return Collections.unmodifiableMap(report);
        }

        IncidentService incidentService() {
            return incidents;
        }

        DetectionService detectionService() {
            return detection;
        }

        AuditRepository auditRepository() {
            return audit;
        }
    }

    // =====================================================
    // SAMPLE EVENT FACTORY
    // =====================================================

    static List<SecurityEvent> sampleEvents() {
        Instant now = Instant.now();

        List<SecurityEvent> events =
            new ArrayList<>();

        for (int i = 0; i < 3; i++) {
            events.add(
                new SecurityEvent(
                    "EVT-" + (i + 1),
                    now.minus(3, ChronoUnit.DAYS)
                        .plus(i, ChronoUnit.HOURS),
                    EventType.LOGIN,
                    "cloud-admin",
                    "10.10.1.10",
                    "production/iam",
                    "authenticate",
                    true,
                    "ap-south-1",
                    Map.of("mfa", true)
                )
            );
        }

        for (int i = 0; i < 6; i++) {
            events.add(
                new SecurityEvent(
                    "EVT-" + (i + 4),
                    now.plusSeconds(i * 30L),
                    EventType.FAILED_LOGIN,
                    "cloud-admin",
                    "203.0.113.25",
                    "production/iam",
                    "authenticate",
                    false,
                    "ap-south-1",
                    Map.of(
                        "reason",
                        "invalid_credentials"
                    )
                )
            );
        }

        events.add(
            new SecurityEvent(
                "EVT-10",
                now.plusSeconds(400),
                EventType.PERMISSION_CHANGE,
                "cloud-admin",
                "203.0.113.25",
                "production/iam",
                "grant_admin",
                true,
                "ap-south-1",
                Map.of("approvedChange", false)
            )
        );

        events.add(
            new SecurityEvent(
                "EVT-11",
                now.plusSeconds(500),
                EventType.SECRET_ACCESS,
                "service-account",
                "198.51.100.40",
                "production/database",
                "read_secret",
                true,
                "ap-south-1",
                Map.of(
                    "approved", false,
                    "mfa", false
                )
            )
        );

        return events;
    }

    // =====================================================
    // TESTING
    // =====================================================

    static void runTests(
            CloudSecurityService service) {

        if (
            service.auditRepository()
                .findAll().size() != 11
        ) {
            throw new AssertionError(
                "Audit event count mismatch."
            );
        }

        if (
            service.detectionService()
                .correlation()
                .allAlerts().size() < 3
        ) {
            throw new AssertionError(
                "Expected alerts were not generated."
            );
        }

        SecurityIncident incident =
            service.incidentService().all().get(0);

        incident.transition(
            IncidentStatus.INVESTIGATING
        );

        boolean rejected = false;

        try {
            incident.transition(IncidentStatus.OPEN);
        } catch (IncidentStateException exception) {
            rejected = true;
        }

        if (!rejected) {
            throw new AssertionError(
                "Invalid incident transition was accepted."
            );
        }

        rejected = false;

        try {
            new SecurityEvent(
                "INVALID",
                Instant.now(),
                EventType.LOGIN,
                "user",
                "999.999.999.999",
                "resource",
                "login",
                true,
                "region",
                Map.of()
            );
        } catch (ValidationException exception) {
            rejected = true;
        }

        if (!rejected) {
            throw new AssertionError(
                "Invalid IP was accepted."
            );
        }

        System.out.println(
            "All Java 17 monitoring tests passed."
        );
    }

    // =====================================================
    // MAIN
    // =====================================================

    public static void main(String[] args) {

        try {
            MonitoringPolicy policy =
                MonitoringPolicy.defaults();

            AuditRepository repository =
                new InMemoryAuditRepository();

            CloudSecurityService service =
                new CloudSecurityService(
                    policy,
                    repository
                );

            List<SecurityEvent> events =
                sampleEvents();

            for (SecurityEvent event : events) {
                service.ingest(event);
            }

            // Analyst workflow.
            for (
                SecurityIncident incident :
                service.incidentService().all()
            ) {
                incident.assign("soc-analyst-01");

                incident.addNote(
                    "Initial triage completed. " +
                    "Related audit events retained."
                );

                incident.transition(
                    IncidentStatus.INVESTIGATING
                );
            }

            runTests(service);

            System.out.println(
                "\nCLOUD SECURITY MONITORING REPORT"
            );

            System.out.println(
                "========================================"
            );

            service.report().forEach(
                (key, value) ->
                    System.out.println(
                        key + ": " + value
                    )
            );

            System.out.println(
                "\nIncident details:"
            );

            for (
                SecurityIncident incident :
                service.incidentService().all()
            ) {
                System.out.println(
                    incident.incidentId() +
                    " | " + incident.severity() +
                    " | " + incident.status() +
                    " | " + incident.assignedAnalyst()
                );
            }

        } catch (MonitoringException exception) {
            System.err.println(
                "Monitoring failure: " +
                exception.getMessage()
            );

            System.exit(1);
        }
    }
}
