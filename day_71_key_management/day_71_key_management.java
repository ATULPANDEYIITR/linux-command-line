import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

import java.security.GeneralSecurityException;
import java.security.SecureRandom;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/*
 * Enterprise Key Management System
 *
 * Java 17
 *
 * Features:
 * - AES-256-GCM authenticated encryption
 * - Key versioning
 * - Key rotation and revocation
 * - Envelope encryption
 * - Secrets management
 * - HSM abstraction
 * - Role-based authorization
 * - Repository governance and merge eligibility
 * - Audit events
 *
 * Key material is kept out of metadata and logs.
 * A production HSM adapter must replace the simulated provider.
 */

public class KeyManagementEnterprise {

    enum Role {
        ADMIN,
        CRYPTO_OPERATOR,
        APPLICATION,
        AUDITOR
    }

    enum KeyPurpose {
        ENCRYPTION,
        SIGNING,
        HMAC,
        KEY_ENCRYPTION
    }

    enum KeyStatus {
        ACTIVE,
        ROTATED,
        DISABLED,
        REVOKED,
        EXPIRED
    }

    enum ReviewState {
        APPROVED,
        CHANGES_REQUESTED,
        COMMENTED,
        DISMISSED
    }

    enum CheckState {
        PASSED,
        FAILED,
        PENDING
    }

    record Principal(String id, Role role) {
        Principal {
            Objects.requireNonNull(id);
            Objects.requireNonNull(role);

            if (id.isBlank()) {
                throw new IllegalArgumentException(
                    "Principal ID cannot be empty"
                );
            }
        }
    }

    record AuditEvent(
        Instant timestamp,
        String actor,
        String action,
        String resource,
        String outcome
    ) {}

    record EncryptedEnvelope(
        byte[] nonce,
        byte[] ciphertext,
        byte[] authenticationTag
    ) {
        EncryptedEnvelope {
            nonce = nonce.clone();
            ciphertext = ciphertext.clone();
            authenticationTag = authenticationTag.clone();
        }

        @Override
        public byte[] nonce() {
            return nonce.clone();
        }

        @Override
        public byte[] ciphertext() {
            return ciphertext.clone();
        }

        @Override
        public byte[] authenticationTag() {
            return authenticationTag.clone();
        }
    }

    static class SecurityException extends RuntimeException {
        SecurityException(String message) {
            super(message);
        }
    }

    static class KeyVersion {
        private final String keyId;
        private final int version;
        private final KeyPurpose purpose;
        private final SecretKey material;
        private final Instant createdAt;
        private final Instant expiresAt;
        private final boolean hardwareProtected;

        private KeyStatus status;

        KeyVersion(
            String keyId,
            int version,
            KeyPurpose purpose,
            SecretKey material,
            Instant expiresAt,
            boolean hardwareProtected
        ) {
            this.keyId = keyId;
            this.version = version;
            this.purpose = purpose;
            this.material = material;
            this.createdAt = Instant.now();
            this.expiresAt = expiresAt;
            this.hardwareProtected = hardwareProtected;
            this.status = KeyStatus.ACTIVE;
        }

        String keyId() {
            return keyId;
        }

        int version() {
            return version;
        }

        KeyPurpose purpose() {
            return purpose;
        }

        SecretKey material() {
            return material;
        }

        KeyStatus status() {
            return status;
        }

        void setStatus(KeyStatus status) {
            this.status = status;
        }

        boolean isExpired() {
            return Instant.now().isAfter(expiresAt);
        }

        String metadata() {
            return "KeyVersion{" +
                "keyId='" + keyId + '\'' +
                ", version=" + version +
                ", purpose=" + purpose +
                ", status=" + status +
                ", createdAt=" + createdAt +
                ", expiresAt=" + expiresAt +
                ", hardwareProtected=" + hardwareProtected +
                '}';
        }
    }

    interface HardwareSecurityProvider {
        SecretKey generateKey() throws GeneralSecurityException;
    }

    static class SimulatedHSM
        implements HardwareSecurityProvider {

        @Override
        public SecretKey generateKey()
            throws GeneralSecurityException {

            KeyGenerator generator =
                KeyGenerator.getInstance("AES");

            generator.init(256, new SecureRandom());

            return generator.generateKey();
        }
    }

    static class AuditService {
        private final List<AuditEvent> events =
            Collections.synchronizedList(
                new ArrayList<>()
            );

        void record(
            String actor,
            String action,
            String resource,
            String outcome
        ) {
            events.add(new AuditEvent(
                Instant.now(),
                actor,
                action,
                resource,
                outcome
            ));
        }

        List<AuditEvent> events() {
            synchronized (events) {
                return List.copyOf(events);
            }
        }
    }

    static class KeyManagementService {
        private final Map<String, List<KeyVersion>> keys =
            new ConcurrentHashMap<>();

        private final HardwareSecurityProvider hsm;
        private final AuditService audit;
        private final int rotationDays;

        KeyManagementService(
            HardwareSecurityProvider hsm,
            AuditService audit,
            int rotationDays
        ) {
            this.hsm = Objects.requireNonNull(hsm);
            this.audit = Objects.requireNonNull(audit);

            if (rotationDays < 1) {
                throw new IllegalArgumentException(
                    "Invalid rotation period"
                );
            }

            this.rotationDays = rotationDays;
        }

        private void authorize(
            Principal principal,
            Role... allowed
        ) {
            Set<Role> roles = EnumSet.copyOf(
                List.of(allowed)
            );

            if (principal == null ||
                !roles.contains(principal.role())) {
                throw new SecurityException(
                    "Permission denied"
                );
            }
        }

        String createKey(
            Principal principal,
            KeyPurpose purpose
        ) throws GeneralSecurityException {

            authorize(
                principal,
                Role.ADMIN,
                Role.CRYPTO_OPERATOR
            );

            String keyId = UUID.randomUUID().toString();

            KeyVersion key = new KeyVersion(
                keyId,
                1,
                purpose,
                hsm.generateKey(),
                Instant.now().plus(
                    rotationDays,
                    ChronoUnit.DAYS
                ),
                true
            );

            List<KeyVersion> versions =
                Collections.synchronizedList(
                    new ArrayList<>()
                );

            versions.add(key);

            keys.put(keyId, versions);

            audit.record(
                principal.id(),
                "CREATE",
                keyId,
                "SUCCESS"
            );

            return keyId;
        }

        KeyVersion activeKey(String keyId) {
            List<KeyVersion> versions = keys.get(keyId);

            if (versions == null || versions.isEmpty()) {
                throw new IllegalArgumentException(
                    "Key not found"
                );
            }

            synchronized (versions) {
                KeyVersion key =
                    versions.get(versions.size() - 1);

                if (key.status() != KeyStatus.ACTIVE) {
                    throw new IllegalStateException(
                        "Key is not active"
                    );
                }

                if (key.isExpired()) {
                    key.setStatus(KeyStatus.EXPIRED);

                    throw new IllegalStateException(
                        "Key expired"
                    );
                }

                return key;
            }
        }

        int rotate(
            Principal principal,
            String keyId
        ) throws GeneralSecurityException {

            authorize(
                principal,
                Role.ADMIN,
                Role.CRYPTO_OPERATOR
            );

            List<KeyVersion> versions = keys.get(keyId);

            if (versions == null) {
                throw new IllegalArgumentException(
                    "Key not found"
                );
            }

            synchronized (versions) {
                KeyVersion current =
                    activeKey(keyId);

                KeyVersion next = new KeyVersion(
                    keyId,
                    current.version() + 1,
                    current.purpose(),
                    hsm.generateKey(),
                    Instant.now().plus(
                        rotationDays,
                        ChronoUnit.DAYS
                    ),
                    true
                );

                current.setStatus(KeyStatus.ROTATED);
                versions.add(next);

                audit.record(
                    principal.id(),
                    "ROTATE",
                    keyId,
                    "SUCCESS"
                );

                return next.version();
            }
        }

        void revoke(
            Principal principal,
            String keyId
        ) {
            authorize(principal, Role.ADMIN);

            List<KeyVersion> versions = keys.get(keyId);

            if (versions == null) {
                throw new IllegalArgumentException(
                    "Key not found"
                );
            }

            synchronized (versions) {
                versions.forEach(
                    key -> key.setStatus(KeyStatus.REVOKED)
                );
            }

            audit.record(
                principal.id(),
                "REVOKE",
                keyId,
                "SUCCESS"
            );
        }

        KeyVersion version(
            String keyId,
            int version
        ) {
            List<KeyVersion> versions = keys.get(keyId);

            if (versions == null) {
                throw new IllegalArgumentException(
                    "Key not found"
                );
            }

            synchronized (versions) {
                return versions.stream()
                    .filter(k -> k.version() == version)
                    .findFirst()
                    .orElseThrow(() ->
                        new IllegalArgumentException(
                            "Version not found"
                        )
                    );
            }
        }

        List<String> metadata() {
            return keys.values().stream()
                .flatMap(List::stream)
                .map(KeyVersion::metadata)
                .collect(Collectors.toUnmodifiableList());
        }
    }

    static class AEADCipher {
        private static final int NONCE_SIZE = 12;
        private static final int TAG_SIZE = 128;

        private static final SecureRandom RANDOM =
            new SecureRandom();

        static EncryptedEnvelope encrypt(
            byte[] plaintext,
            SecretKey key
        ) throws GeneralSecurityException {

            byte[] nonce = new byte[NONCE_SIZE];
            RANDOM.nextBytes(nonce);

            Cipher cipher = Cipher.getInstance(
                "AES/GCM/NoPadding"
            );

            cipher.init(
                Cipher.ENCRYPT_MODE,
                key,
                new GCMParameterSpec(TAG_SIZE, nonce)
            );

            byte[] combined = cipher.doFinal(plaintext);

            int ciphertextLength =
                combined.length - TAG_SIZE / 8;

            byte[] ciphertext = new byte[ciphertextLength];
            byte[] tag = new byte[TAG_SIZE / 8];

            System.arraycopy(
                combined, 0,
                ciphertext, 0,
                ciphertextLength
            );

            System.arraycopy(
                combined, ciphertextLength,
                tag, 0,
                tag.length
            );

            return new EncryptedEnvelope(
                nonce,
                ciphertext,
                tag
            );
        }

        static byte[] decrypt(
            EncryptedEnvelope envelope,
            SecretKey key
        ) throws GeneralSecurityException {

            Cipher cipher = Cipher.getInstance(
                "AES/GCM/NoPadding"
            );

            cipher.init(
                Cipher.DECRYPT_MODE,
                key,
                new GCMParameterSpec(
                    TAG_SIZE,
                    envelope.nonce()
                )
            );

            byte[] ciphertext = envelope.ciphertext();
            byte[] tag = envelope.authenticationTag();

            byte[] combined = new byte[
                ciphertext.length + tag.length
            ];

            System.arraycopy(
                ciphertext, 0,
                combined, 0,
                ciphertext.length
            );

            System.arraycopy(
                tag, 0,
                combined, ciphertext.length,
                tag.length
            );

            return cipher.doFinal(combined);
        }
    }

    static class SecretsVault {
        private record SecretRecord(
            String keyId,
            int version,
            EncryptedEnvelope envelope
        ) {}

        private final Map<String, SecretRecord> secrets =
            new ConcurrentHashMap<>();

        private final KeyManagementService kms;
        private final AuditService audit;

        SecretsVault(
            KeyManagementService kms,
            AuditService audit
        ) {
            this.kms = kms;
            this.audit = audit;
        }

        void store(
            Principal principal,
            String name,
            String value,
            String keyId
        ) throws GeneralSecurityException {

            if (principal.role() != Role.APPLICATION) {
                throw new SecurityException(
                    "Application role required"
                );
            }

            if (name == null ||
                !name.matches("[A-Za-z0-9_.-]{1,128}")) {
                throw new IllegalArgumentException(
                    "Invalid secret name"
                );
            }

            if (value == null || value.isEmpty()) {
                throw new IllegalArgumentException(
                    "Empty secret"
                );
            }

            KeyVersion key = kms.activeKey(keyId);

            EncryptedEnvelope envelope =
                AEADCipher.encrypt(
                    value.getBytes(
                        java.nio.charset.StandardCharsets.UTF_8
                    ),
                    key.material()
                );

            SecretRecord record = new SecretRecord(
                keyId,
                key.version(),
                envelope
            );

            if (secrets.putIfAbsent(name, record) != null) {
                throw new IllegalStateException(
                    "Secret already exists"
                );
            }

            audit.record(
                principal.id(),
                "STORE_SECRET",
                name,
                "SUCCESS"
            );
        }

        String retrieve(
            Principal principal,
            String name
        ) throws GeneralSecurityException {

            if (!EnumSet.of(
                Role.ADMIN,
                Role.APPLICATION
            ).contains(principal.role())) {
                throw new SecurityException(
                    "Secret access denied"
                );
            }

            SecretRecord record = secrets.get(name);

            if (record == null) {
                throw new IllegalArgumentException(
                    "Secret not found"
                );
            }

            KeyVersion key = kms.version(
                record.keyId(),
                record.version()
            );

            if (key.status() == KeyStatus.REVOKED ||
                key.status() == KeyStatus.DISABLED ||
                key.status() == KeyStatus.EXPIRED) {
                throw new IllegalStateException(
                    "Key cannot decrypt this secret"
                );
            }

            byte[] plaintext = AEADCipher.decrypt(
                record.envelope(),
                key.material()
            );

            return new String(
                plaintext,
                java.nio.charset.StandardCharsets.UTF_8
            );
        }

        void reencrypt(
            Principal principal,
            String name
        ) throws GeneralSecurityException {

            if (!EnumSet.of(
                Role.ADMIN,
                Role.CRYPTO_OPERATOR
            ).contains(principal.role())) {
                throw new SecurityException(
                    "Re-encryption denied"
                );
            }

            SecretRecord record = secrets.get(name);

            if (record == null) {
                throw new IllegalArgumentException(
                    "Secret not found"
                );
            }

            KeyVersion oldKey = kms.version(
                record.keyId(),
                record.version()
            );

            if (oldKey.status() == KeyStatus.REVOKED) {
                throw new IllegalStateException(
                    "Old key is revoked"
                );
            }

            byte[] plaintext = AEADCipher.decrypt(
                record.envelope(),
                oldKey.material()
            );

            KeyVersion current = kms.activeKey(
                record.keyId()
            );

            EncryptedEnvelope nextEnvelope =
                AEADCipher.encrypt(
                    plaintext,
                    current.material()
                );

            secrets.put(
                name,
                new SecretRecord(
                    current.keyId(),
                    current.version(),
                    nextEnvelope
                )
            );

            audit.record(
                principal.id(),
                "REENCRYPT",
                name,
                "SUCCESS"
            );
        }
    }

    record Review(
        String reviewer,
        boolean eligible,
        boolean dismissed,
        boolean stale,
        ReviewState state
    ) {}

    record StatusCheck(
        String name,
        CheckState state
    ) {}

    record ReviewPolicy(
        int requiredApprovals,
        boolean requireFreshApprovals,
        boolean requireResolvedConversations,
        boolean requirePassingChecks,
        boolean requireLinearHistory
    ) {
        ReviewPolicy {
            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                    "Invalid approval count"
                );
            }
        }
    }

    record PullRequest(
        int id,
        String sourceBranch,
        String targetBranch,
        String author,
        boolean open,
        boolean draft,
        boolean synchronizedWithBase,
        boolean conflicts,
        boolean conversationsResolved,
        boolean linearHistory,
        List<String> commits,
        List<Review> reviews,
        List<StatusCheck> checks
    ) {
        PullRequest {
            commits = List.copyOf(commits);
            reviews = List.copyOf(reviews);
            checks = List.copyOf(checks);
        }
    }

    record MergeDecision(
        boolean eligible,
        List<String> reasons
    ) {}

    static class MergeEligibilityService {
        private final ReviewPolicy policy;

        MergeEligibilityService(ReviewPolicy policy) {
            this.policy = policy;
        }

        MergeDecision evaluate(PullRequest pr) {
            List<String> reasons = new ArrayList<>();

            if (!pr.open()) {
                reasons.add("Pull Request is closed");
            }

            if (pr.draft()) {
                reasons.add("Draft cannot be merged");
            }

            if (pr.commits().isEmpty()) {
                reasons.add("No proposed commits");
            }

            if (!pr.synchronizedWithBase()) {
                reasons.add("Base branch synchronization required");
            }

            if (pr.conflicts()) {
                reasons.add("Merge conflicts exist");
            }

            if (policy.requireLinearHistory() &&
                !pr.linearHistory()) {
                reasons.add("Linear history required");
            }

            if (policy.requireResolvedConversations() &&
                !pr.conversationsResolved()) {
                reasons.add("Unresolved conversations");
            }

            if (policy.requirePassingChecks()) {
                if (pr.checks().isEmpty()) {
                    reasons.add("Required checks are missing");
                }

                for (StatusCheck check : pr.checks()) {
                    if (check.state() != CheckState.PASSED) {
                        reasons.add(
                            "Check not passed: " + check.name()
                        );
                    }
                }
            }

            Set<String> approvals = new HashSet<>();
            boolean changesRequested = false;

            for (Review review : pr.reviews()) {
                if (!review.eligible() ||
                    review.dismissed() ||
                    (policy.requireFreshApprovals() &&
                     review.stale())) {
                    continue;
                }

                if (review.state() == ReviewState.APPROVED) {
                    approvals.add(review.reviewer());
                }

                if (review.state() ==
                    ReviewState.CHANGES_REQUESTED) {
                    changesRequested = true;
                }
            }

            if (changesRequested) {
                reasons.add(
                    "Active changes-requested review exists"
                );
            }

            if (approvals.size() <
                policy.requiredApprovals()) {
                reasons.add("Approval threshold not met");
            }

            return new MergeDecision(
                reasons.isEmpty(),
                List.copyOf(reasons)
            );
        }
    }

    public static void main(String[] args) {
        try {
            Principal admin = new Principal(
                "security-admin",
                Role.ADMIN
            );

            Principal operator = new Principal(
                "crypto-operator",
                Role.CRYPTO_OPERATOR
            );

            Principal application = new Principal(
                "payment-service",
                Role.APPLICATION
            );

            AuditService audit = new AuditService();

            KeyManagementService kms =
                new KeyManagementService(
                    new SimulatedHSM(),
                    audit,
                    90
                );

            SecretsVault vault = new SecretsVault(
                kms,
                audit
            );

            String keyId = kms.createKey(
                operator,
                KeyPurpose.KEY_ENCRYPTION
            );

            System.out.println("KEY CREATED: " + keyId);

            vault.store(
                application,
                "database.password",
                "Enterprise-Secret-2026",
                keyId
            );

            System.out.println(
                "SECRET: " +
                vault.retrieve(
                    application,
                    "database.password"
                )
            );

            int version = kms.rotate(
                operator,
                keyId
            );

            System.out.println(
                "ROTATED VERSION: " + version
            );

            vault.reencrypt(
                operator,
                "database.password"
            );

            System.out.println(
                "AFTER ROTATION: " +
                vault.retrieve(
                    application,
                    "database.password"
                )
            );

            ReviewPolicy policy = new ReviewPolicy(
                2,
                true,
                true,
                true,
                true
            );

            PullRequest pr = new PullRequest(
                101,
                "feature/key-rotation",
                "main",
                "developer-01",
                true,
                false,
                true,
                false,
                true,
                true,
                List.of("commit-001", "commit-002"),
                List.of(
                    new Review(
                        "reviewer-01",
                        true,
                        false,
                        false,
                        ReviewState.APPROVED
                    ),
                    new Review(
                        "reviewer-02",
                        true,
                        false,
                        false,
                        ReviewState.APPROVED
                    )
                ),
                List.of(
                    new StatusCheck(
                        "unit-tests",
                        CheckState.PASSED
                    ),
                    new StatusCheck(
                        "security-scan",
                        CheckState.PASSED
                    )
                )
            );

            MergeEligibilityService service =
                new MergeEligibilityService(policy);

            MergeDecision decision = service.evaluate(pr);

            System.out.println(
                "\nMERGE ELIGIBLE: " + decision.eligible()
            );

            decision.reasons().forEach(
                System.out::println
            );

            kms.revoke(admin, keyId);

            System.out.println(
                "\nREVOKED KEY METADATA:"
            );

            kms.metadata().forEach(
                System.out::println
            );

            System.out.println(
                "\nAUDIT EVENTS: " + audit.events().size()
            );

        } catch (GeneralSecurityException |
                 RuntimeException exception) {
            System.err.println(
                "Operation failed: " +
                exception.getMessage()
            );

            System.exit(1);
        }
    }
}
