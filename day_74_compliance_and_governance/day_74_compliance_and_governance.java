import java.time.Instant;
import java.time.Duration;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantLock;
import java.util.stream.Collectors;

/**
 * Enterprise Compliance and Governance Management System.
 *
 * Java 17, standard library only.
 *
 * Domain capabilities:
 * - Regulatory framework mapping
 * - Privacy classification
 * - Consent and legal-basis evaluation
 * - Role-based access control
 * - Data subject request workflows
 * - Compliance policy evaluation
 * - Retention governance
 * - Audit evidence
 * - Compliance reporting
 */
public class ComplianceGovernance {

    enum PrivacyCategory {
        PUBLIC,
        INTERNAL,
        CONFIDENTIAL,
        PERSONAL,
        SENSITIVE_PERSONAL
    }

    enum LegalBasis {
        CONSENT,
        CONTRACT,
        LEGAL_OBLIGATION,
        LEGITIMATE_INTEREST,
        PUBLIC_TASK,
        VITAL_INTEREST
    }

    enum ConsentStatus {
        GRANTED,
        WITHDRAWN,
        EXPIRED
    }

    enum RequestType {
        ACCESS,
        RECTIFICATION,
        ERASURE,
        PORTABILITY,
        RESTRICTION
    }

    enum RequestStatus {
        RECEIVED,
        VERIFIED,
        IN_PROGRESS,
        COMPLETED,
        REJECTED
    }

    enum RiskLevel {
        LOW,
        MEDIUM,
        HIGH,
        CRITICAL
    }

    enum Decision {
        ELIGIBLE,
        BLOCKED
    }

    enum CheckStatus {
        PASSED,
        FAILED,
        NOT_RUN
    }

    static class ComplianceException extends RuntimeException {
        ComplianceException(String message) {
            super(message);
        }
    }

    static class AuthorizationException extends ComplianceException {
        AuthorizationException(String message) {
            super(message);
        }
    }

    static class PolicyException extends ComplianceException {
        PolicyException(String message) {
            super(message);
        }
    }

    static class ValidationException extends ComplianceException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class ConflictException extends ComplianceException {
        ConflictException(String message) {
            super(message);
        }
    }

    record RegulatoryFramework(
        String code,
        String name,
        String jurisdiction
    ) {}

    record User(
        String id,
        String role,
        boolean active
    ) {
        User {
            requireText(id, "User ID");
            requireText(role, "Role");
        }
    }

    record DataAsset(
        String id,
        String name,
        String owner,
        String purpose,
        PrivacyCategory category,
        LegalBasis legalBasis,
        Set<String> frameworks,
        int retentionDays,
        boolean encrypted,
        Instant createdAt,
        boolean active
    ) {
        DataAsset {
            requireText(id, "Asset ID");
            requireText(name, "Asset name");
            requireText(owner, "Asset owner");
            requireText(purpose, "Processing purpose");

            Objects.requireNonNull(category);
            Objects.requireNonNull(legalBasis);
            Objects.requireNonNull(createdAt);

            if (retentionDays <= 0) {
                throw new ValidationException(
                    "Retention must be positive."
                );
            }

            frameworks = Set.copyOf(frameworks);

            if (
                category == PrivacyCategory.SENSITIVE_PERSONAL &&
                !encrypted
            ) {
                throw new PolicyException(
                    "Sensitive personal data requires encryption."
                );
            }
        }
    }

    record Consent(
        String id,
        String subjectId,
        String assetId,
        String purpose,
        ConsentStatus status,
        Instant grantedAt,
        Instant expiresAt
    ) {
        Consent {
            requireText(id, "Consent ID");
            requireText(subjectId, "Subject ID");
            requireText(assetId, "Asset ID");
            requireText(purpose, "Purpose");

            Objects.requireNonNull(status);
            Objects.requireNonNull(grantedAt);
        }

        boolean isValid(Instant now) {
            return status == ConsentStatus.GRANTED &&
                (expiresAt == null || now.isBefore(expiresAt));
        }

        Consent withdraw() {
            return new Consent(
                id,
                subjectId,
                assetId,
                purpose,
                ConsentStatus.WITHDRAWN,
                grantedAt,
                expiresAt
            );
        }
    }

    record GovernancePolicy(
        String id,
        String name,
        boolean encryptionRequired,
        int maximumRetentionDays,
        boolean enabled,
        Set<String> applicableCategories
    ) {
        GovernancePolicy {
            requireText(id, "Policy ID");
            requireText(name, "Policy name");

            if (maximumRetentionDays <= 0) {
                throw new ValidationException(
                    "Invalid policy retention."
                );
            }

            applicableCategories = Set.copyOf(
                applicableCategories
            );
        }

        boolean appliesTo(DataAsset asset) {
            return enabled &&
                (
                    applicableCategories.isEmpty() ||
                    applicableCategories.contains(
                        asset.category().name()
                    )
                );
        }
    }

    record ComplianceFinding(
        String id,
        String assetId,
        String policyId,
        RiskLevel severity,
        String description,
        Instant detectedAt
    ) {}

    record StatusCheck(
        String name,
        CheckStatus status,
        boolean mandatory
    ) {
        StatusCheck {
            requireText(name, "Check name");
            Objects.requireNonNull(status);
        }
    }

    record SubjectRequest(
        String id,
        String subjectId,
        RequestType type,
        RequestStatus status,
        Instant receivedAt,
        Instant deadline,
        long version
    ) {
        SubjectRequest {
            requireText(id, "Request ID");
            requireText(subjectId, "Subject ID");

            Objects.requireNonNull(type);
            Objects.requireNonNull(status);
            Objects.requireNonNull(receivedAt);
            Objects.requireNonNull(deadline);

            if (!deadline.isAfter(receivedAt)) {
                throw new ValidationException(
                    "Request deadline must follow receipt."
                );
            }
        }

        SubjectRequest transition(RequestStatus next) {
            return new SubjectRequest(
                id,
                subjectId,
                type,
                next,
                receivedAt,
                deadline,
                version + 1
            );
        }
    }

    record AuditEvent(
        long sequence,
        Instant timestamp,
        String actor,
        String action,
        String resource,
        String details
    ) {}

    record GovernanceResult(
        Decision decision,
        List<String> blockers,
        List<String> warnings
    ) {
        GovernanceResult {
            blockers = List.copyOf(blockers);
            warnings = List.copyOf(warnings);
        }
    }

    static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new ValidationException(
                field + " is required."
            );
        }
    }

    static class RegulatoryRegistry {

        private final Map<String, RegulatoryFramework> frameworks =
            Map.of(
                "GDPR",
                new RegulatoryFramework(
                    "GDPR",
                    "General Data Protection Regulation",
                    "European Union"
                ),
                "DPDPA",
                new RegulatoryFramework(
                    "DPDPA",
                    "Digital Personal Data Protection Act, 2023",
                    "India"
                ),
                "ISO27001",
                new RegulatoryFramework(
                    "ISO27001",
                    "Information Security Management System",
                    "International"
                ),
                "HIPAA",
                new RegulatoryFramework(
                    "HIPAA",
                    "Health Insurance Portability and Accountability Act",
                    "United States"
                )
            );

        RegulatoryFramework find(String code) {
            RegulatoryFramework framework = frameworks.get(code);

            if (framework == null) {
                throw new ValidationException(
                    "Unknown framework: " + code
                );
            }

            return framework;
        }

        void validateMappings(Set<String> codes) {
            codes.forEach(this::find);
        }

        Set<String> supportedCodes() {
            return frameworks.keySet();
        }
    }

    static class AccessControlService {

        private final Map<String, Set<String>> rolePermissions =
            new HashMap<>();

        AccessControlService() {
            rolePermissions.put(
                "COMPLIANCE_ADMIN",
                Set.of(
                    "asset:create",
                    "asset:read",
                    "consent:manage",
                    "request:manage",
                    "policy:manage",
                    "report:read",
                    "retention:manage"
                )
            );

            rolePermissions.put(
                "PRIVACY_OFFICER",
                Set.of(
                    "asset:read",
                    "consent:manage",
                    "request:manage",
                    "report:read"
                )
            );

            rolePermissions.put(
                "ANALYST",
                Set.of("asset:read")
            );

            rolePermissions.put(
                "AUDITOR",
                Set.of("report:read", "audit:read")
            );
        }

        void authorize(User user, String permission) {
            if (user == null || !user.active()) {
                throw new AuthorizationException(
                    "User is inactive or unknown."
                );
            }

            Set<String> permissions =
                rolePermissions.get(user.role());

            if (
                permissions == null ||
                !permissions.contains(permission)
            ) {
                throw new AuthorizationException(
                    "Permission denied: " + permission
                );
            }
        }
    }

    static class AuditService {

        private final List<AuditEvent> events = new ArrayList<>();

        synchronized void record(
            String actor,
            String action,
            String resource,
            String details
        ) {
            events.add(
                new AuditEvent(
                    events.size() + 1L,
                    Instant.now(),
                    actor,
                    action,
                    resource,
                    details
                )
            );
        }

        synchronized List<AuditEvent> events() {
            return List.copyOf(events);
        }

        synchronized long count() {
            return events.size();
        }
    }

    static class RequestWorkflowService {

        private final Map<String, SubjectRequest> requests =
            new LinkedHashMap<>();

        private final ReentrantLock lock = new ReentrantLock();

        private final Map<RequestStatus, Set<RequestStatus>> transitions =
            Map.of(
                RequestStatus.RECEIVED,
                Set.of(
                    RequestStatus.VERIFIED,
                    RequestStatus.REJECTED
                ),
                RequestStatus.VERIFIED,
                Set.of(
                    RequestStatus.IN_PROGRESS,
                    RequestStatus.REJECTED
                ),
                RequestStatus.IN_PROGRESS,
                Set.of(
                    RequestStatus.COMPLETED,
                    RequestStatus.REJECTED
                ),
                RequestStatus.COMPLETED,
                Set.of(),
                RequestStatus.REJECTED,
                Set.of()
            );

        SubjectRequest submit(
            String subjectId,
            RequestType type,
            int deadlineDays
        ) {
            if (deadlineDays <= 0) {
                throw new ValidationException(
                    "Deadline must be positive."
                );
            }

            Instant now = Instant.now();

            SubjectRequest request = new SubjectRequest(
                UUID.randomUUID().toString(),
                subjectId,
                type,
                RequestStatus.RECEIVED,
                now,
                now.plus(Duration.ofDays(deadlineDays)),
                1
            );

            lock.lock();

            try {
                requests.put(request.id(), request);
            } finally {
                lock.unlock();
            }

            return request;
        }

        SubjectRequest transition(
            String requestId,
            RequestStatus next,
            long expectedVersion
        ) {
            lock.lock();

            try {
                SubjectRequest current = requests.get(requestId);

                if (current == null) {
                    throw new ValidationException(
                        "Request not found."
                    );
                }

                if (current.version() != expectedVersion) {
                    throw new ConflictException(
                        "Concurrent request update detected."
                    );
                }

                if (
                    !transitions.get(current.status()).contains(next)
                ) {
                    throw new PolicyException(
                        "Invalid request state transition."
                    );
                }

                SubjectRequest updated = current.transition(next);

                requests.put(requestId, updated);

                return updated;

            } finally {
                lock.unlock();
            }
        }

        List<SubjectRequest> all() {
            lock.lock();

            try {
                return List.copyOf(requests.values());
            } finally {
                lock.unlock();
            }
        }
    }

    static class GovernanceService {

        private final Map<String, DataAsset> assets =
            new LinkedHashMap<>();

        private final Map<String, Consent> consents =
            new LinkedHashMap<>();

        private final Map<String, GovernancePolicy> policies =
            new LinkedHashMap<>();

        private final List<ComplianceFinding> findings =
            new ArrayList<>();

        private final RegulatoryRegistry registry =
            new RegulatoryRegistry();

        private final AccessControlService accessControl =
            new AccessControlService();

        private final AuditService audit =
            new AuditService();

        private final RequestWorkflowService requestWorkflow =
            new RequestWorkflowService();

        private User requireUser(String id) {
            return users.get(id);
        }

        private final Map<String, User> users =
            new LinkedHashMap<>();

        void registerUser(User user) {
            if (users.putIfAbsent(user.id(), user) != null) {
                throw new ConflictException(
                    "User already registered."
                );
            }
        }

        private User authorize(
            String actorId,
            String permission
        ) {
            User user = requireUser(actorId);

            try {
                accessControl.authorize(user, permission);
            } catch (AuthorizationException error) {
                audit.record(
                    actorId,
                    "ACCESS_DENIED",
                    permission,
                    error.getMessage()
                );

                throw error;
            }

            return user;
        }

        void registerPolicy(
            String actorId,
            GovernancePolicy policy
        ) {
            authorize(actorId, "policy:manage");

            if (
                policies.putIfAbsent(policy.id(), policy) != null
            ) {
                throw new ConflictException(
                    "Policy already exists."
                );
            }

            audit.record(
                actorId,
                "POLICY_REGISTERED",
                policy.id(),
                policy.name()
            );
        }

        void registerAsset(
            String actorId,
            DataAsset asset
        ) {
            authorize(actorId, "asset:create");

            registry.validateMappings(asset.frameworks());

            if (assets.containsKey(asset.id())) {
                throw new ConflictException(
                    "Asset already registered."
                );
            }

            assets.put(asset.id(), asset);

            audit.record(
                actorId,
                "ASSET_REGISTERED",
                asset.id(),
                asset.category().name()
            );
        }

        void grantConsent(
            String actorId,
            Consent consent
        ) {
            authorize(actorId, "consent:manage");

            DataAsset asset = assets.get(consent.assetId());

            if (asset == null || !asset.active()) {
                throw new ValidationException(
                    "Unknown or inactive asset."
                );
            }

            if (
                asset.legalBasis() != LegalBasis.CONSENT ||
                !asset.purpose().equals(consent.purpose())
            ) {
                throw new PolicyException(
                    "Consent does not match declared processing."
                );
            }

            if (consents.putIfAbsent(consent.id(), consent) != null) {
                throw new ConflictException(
                    "Consent already exists."
                );
            }

            audit.record(
                actorId,
                "CONSENT_GRANTED",
                consent.id(),
                consent.subjectId()
            );
        }

        void withdrawConsent(
            String actorId,
            String consentId
        ) {
            authorize(actorId, "consent:manage");

            Consent consent = consents.get(consentId);

            if (consent == null) {
                throw new ValidationException(
                    "Consent not found."
                );
            }

            if (consent.status() != ConsentStatus.GRANTED) {
                throw new ConflictException(
                    "Consent is not currently granted."
                );
            }

            consents.put(consentId, consent.withdraw());

            audit.record(
                actorId,
                "CONSENT_WITHDRAWN",
                consentId,
                consent.subjectId()
            );
        }

        boolean canProcess(
            String assetId,
            String subjectId
        ) {
            DataAsset asset = assets.get(assetId);

            if (asset == null || !asset.active()) {
                return false;
            }

            if (asset.legalBasis() != LegalBasis.CONSENT) {
                return true;
            }

            Instant now = Instant.now();

            return consents.values().stream().anyMatch(
                consent ->
                    consent.assetId().equals(assetId) &&
                    consent.subjectId().equals(subjectId) &&
                    consent.purpose().equals(asset.purpose()) &&
                    consent.isValid(now)
            );
        }

        DataAsset readAsset(
            String actorId,
            String assetId,
            String subjectId
        ) {
            authorize(actorId, "asset:read");

            DataAsset asset = assets.get(assetId);

            if (asset == null) {
                throw new ValidationException("Asset not found.");
            }

            if (!canProcess(assetId, subjectId)) {
                throw new PolicyException(
                    "Processing is not authorized."
                );
            }

            audit.record(
                actorId,
                "ASSET_READ",
                assetId,
                subjectId
            );

            return asset;
        }

        List<ComplianceFinding> evaluateAsset(
            String assetId
        ) {
            DataAsset asset = assets.get(assetId);

            if (asset == null) {
                throw new ValidationException("Asset not found.");
            }

            List<ComplianceFinding> generated =
                new ArrayList<>();

            for (GovernancePolicy policy : policies.values()) {
                if (!policy.appliesTo(asset)) {
                    continue;
                }

                if (
                    policy.encryptionRequired() &&
                    !asset.encrypted()
                ) {
                    generated.add(
                        finding(
                            assetId,
                            policy.id(),
                            RiskLevel.CRITICAL,
                            "Encryption requirement failed."
                        )
                    );
                }

                if (
                    asset.retentionDays() >
                    policy.maximumRetentionDays()
                ) {
                    generated.add(
                        finding(
                            assetId,
                            policy.id(),
                            RiskLevel.HIGH,
                            "Retention exceeds policy limit."
                        )
                    );
                }
            }

            if (asset.frameworks().isEmpty()) {
                generated.add(
                    finding(
                        assetId,
                        "REGULATORY_MAPPING",
                        RiskLevel.MEDIUM,
                        "Regulatory mapping is missing."
                    )
                );
            }

            findings.addAll(generated);

            return List.copyOf(generated);
        }

        private ComplianceFinding finding(
            String assetId,
            String policyId,
            RiskLevel severity,
            String description
        ) {
            return new ComplianceFinding(
                UUID.randomUUID().toString(),
                assetId,
                policyId,
                severity,
                description,
                Instant.now()
            );
        }

        SubjectRequest submitRequest(
            String actorId,
            String subjectId,
            RequestType type,
            int deadlineDays
        ) {
            authorize(actorId, "request:manage");

            SubjectRequest request = requestWorkflow.submit(
                subjectId,
                type,
                deadlineDays
            );

            audit.record(
                actorId,
                "REQUEST_RECEIVED",
                request.id(),
                type.name()
            );

            return request;
        }

        SubjectRequest transitionRequest(
            String actorId,
            String requestId,
            RequestStatus next,
            long expectedVersion
        ) {
            authorize(actorId, "request:manage");

            SubjectRequest request = requestWorkflow.transition(
                requestId,
                next,
                expectedVersion
            );

            audit.record(
                actorId,
                "REQUEST_TRANSITIONED",
                requestId,
                next.name()
            );

            return request;
        }

        GovernanceResult evaluateGovernance(
            String actorId,
            String assetId,
            List<StatusCheck> checks
        ) {
            authorize(actorId, "report:read");

            DataAsset asset = assets.get(assetId);

            if (asset == null) {
                throw new ValidationException("Asset not found.");
            }

            List<String> blockers = new ArrayList<>();
            List<String> warnings = new ArrayList<>();

            if (!asset.active()) {
                blockers.add("Asset is inactive.");
            }

            for (StatusCheck check : checks) {
                if (
                    check.mandatory() &&
                    check.status() != CheckStatus.PASSED
                ) {
                    blockers.add(
                        "Mandatory control failed: " + check.name()
                    );
                } else if (
                    !check.mandatory() &&
                    check.status() == CheckStatus.FAILED
                ) {
                    warnings.add(
                        "Optional control failed: " + check.name()
                    );
                }
            }

            for (GovernancePolicy policy : policies.values()) {
                if (!policy.appliesTo(asset)) {
                    continue;
                }

                if (
                    policy.encryptionRequired() &&
                    !asset.encrypted()
                ) {
                    blockers.add(
                        "Encryption policy failed: " + policy.id()
                    );
                }

                if (
                    asset.retentionDays() >
                    policy.maximumRetentionDays()
                ) {
                    blockers.add(
                        "Retention policy failed: " + policy.id()
                    );
                }
            }

            Decision decision = blockers.isEmpty()
                ? Decision.ELIGIBLE
                : Decision.BLOCKED;

            audit.record(
                actorId,
                "GOVERNANCE_EVALUATED",
                assetId,
                decision.name()
            );

            return new GovernanceResult(
                decision,
                blockers,
                warnings
            );
        }

        Map<String, Object> report(String actorId) {
            authorize(actorId, "report:read");

            Map<PrivacyCategory, Long> categoryCounts =
                assets.values().stream().collect(
                    Collectors.groupingBy(
                        DataAsset::category,
                        () -> new EnumMap<>(PrivacyCategory.class),
                        Collectors.counting()
                    )
                );

            Map<RequestStatus, Long> requestCounts =
                requestWorkflow.all().stream().collect(
                    Collectors.groupingBy(
                        SubjectRequest::status,
                        Collectors.toMap(
                            status -> status,
                            status -> 1L,
                            Long::sum,
                            () -> new EnumMap<>(RequestStatus.class)
                        )
                    )
                );

            Map<String, Object> result = new LinkedHashMap<>();

            result.put("generatedAt", Instant.now().toString());
            result.put("totalAssets", assets.size());
            result.put(
                "activeAssets",
                assets.values().stream()
                    .filter(DataAsset::active)
                    .count()
            );
            result.put("privacyCategories", categoryCounts);
            result.put("requestStates", requestCounts);
            result.put("totalConsents", consents.size());
            result.put("totalPolicies", policies.size());
            result.put("openFindings", findings.size());
            result.put("auditEvents", audit.count());

            return result;
        }

        List<AuditEvent> auditEvents() {
            return audit.events();
        }
    }

    public static void main(String[] args) {

        GovernanceService service = new GovernanceService();

        service.registerUser(
            new User(
                "admin",
                "COMPLIANCE_ADMIN",
                true
            )
        );

        service.registerUser(
            new User(
                "analyst",
                "ANALYST",
                true
            )
        );

        service.registerUser(
            new User(
                "auditor",
                "AUDITOR",
                true
            )
        );

        service.registerPolicy(
            "admin",
            new GovernancePolicy(
                "POLICY-001",
                "Customer Personal Data Policy",
                true,
                3650,
                true,
                Set.of(
                    "PERSONAL",
                    "SENSITIVE_PERSONAL"
                )
            )
        );

        DataAsset asset = new DataAsset(
            "ASSET-001",
            "Customer Identity Records",
            "Data Governance Office",
            "Customer account administration",
            PrivacyCategory.PERSONAL,
            LegalBasis.CONSENT,
            Set.of("GDPR", "DPDPA"),
            730,
            true,
            Instant.now(),
            true
        );

        service.registerAsset("admin", asset);

        Consent consent = new Consent(
            "CONSENT-001",
            "SUBJECT-001",
            "ASSET-001",
            "Customer account administration",
            ConsentStatus.GRANTED,
            Instant.now(),
            null
        );

        service.grantConsent("admin", consent);

        DataAsset accessible = service.readAsset(
            "analyst",
            "ASSET-001",
            "SUBJECT-001"
        );

        System.out.println(
            "Authorized asset: " + accessible.name()
        );

        SubjectRequest request = service.submitRequest(
            "admin",
            "SUBJECT-001",
            RequestType.ACCESS,
            30
        );

        request = service.transitionRequest(
            "admin",
            request.id(),
            RequestStatus.VERIFIED,
            request.version()
        );

        request = service.transitionRequest(
            "admin",
            request.id(),
            RequestStatus.IN_PROGRESS,
            request.version()
        );

        request = service.transitionRequest(
            "admin",
            request.id(),
            RequestStatus.COMPLETED,
            request.version()
        );

        service.withdrawConsent(
            "admin",
            "CONSENT-001"
        );

        try {
            service.readAsset(
                "analyst",
                "ASSET-001",
                "SUBJECT-001"
            );
        } catch (PolicyException error) {
            System.out.println(
                "Expected processing denial: " + error.getMessage()
            );
        }

        List<StatusCheck> checks = List.of(
            new StatusCheck(
                "Encryption verification",
                CheckStatus.PASSED,
                true
            ),
            new StatusCheck(
                "Access review",
                CheckStatus.PASSED,
                true
            ),
            new StatusCheck(
                "Retention assessment",
                CheckStatus.FAILED,
                true
            ),
            new StatusCheck(
                "Optional documentation",
                CheckStatus.NOT_RUN,
                false
            )
        );

        GovernanceResult governance =
            service.evaluateGovernance(
                "admin",
                "ASSET-001",
                checks
            );

        System.out.println(
            "\nGovernance decision: " + governance.decision()
        );

        governance.blockers().forEach(
            blocker -> System.out.println("BLOCKER: " + blocker)
        );

        governance.warnings().forEach(
            warning -> System.out.println("WARNING: " + warning)
        );

        service.evaluateAsset("ASSET-001");

        System.out.println("\nCompliance report:");

        service.report("auditor").forEach(
            (key, value) ->
                System.out.println(key + ": " + value)
        );

        System.out.println(
            "\nAudit records: " + service.auditEvents().size()
        );

        System.out.println(
            "Final request status: " + request.status()
        );
    }
}
