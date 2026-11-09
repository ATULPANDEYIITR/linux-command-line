import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.AEADBadTagException;
import javax.crypto.spec.GCMParameterSpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PublicKey;
import java.security.PrivateKey;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/*
 * Enterprise Encryption Management System
 *
 * Java 17 implementation using standard JCA/JCE.
 *
 * Features:
 * - AES-256-GCM symmetric encryption.
 * - RSA-OAEP public-key encryption.
 * - Hybrid envelope encryption.
 * - Encryption-at-rest service.
 * - TLS policy validation.
 * - Key lifecycle management.
 * - Immutable encryption envelopes.
 * - Enterprise approval and validation rules.
 */

public class EncryptionEnterprise {

    private static final SecureRandom RANDOM = new SecureRandom();

    private static final int GCM_NONCE_BYTES = 12;
    private static final int GCM_TAG_BITS = 128;
    private static final int MAX_DATA_SIZE = 10 * 1024 * 1024;

    enum KeyStatus {
        ACTIVE,
        ROTATED,
        REVOKED
    }

    enum Classification {
        PUBLIC,
        INTERNAL,
        CONFIDENTIAL,
        RESTRICTED
    }

    enum StorageType {
        DATABASE,
        FILE,
        BACKUP,
        NETWORK
    }

    enum EncryptionType {
        SYMMETRIC,
        PUBLIC_KEY,
        HYBRID
    }

    enum Decision {
        APPROVED,
        REJECTED
    }

    static class EncryptionException extends RuntimeException {
        EncryptionException(String message) {
            super(message);
        }

        EncryptionException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    static class PolicyViolationException
            extends EncryptionException {

        PolicyViolationException(String message) {
            super(message);
        }
    }

    record EncryptionEnvelope(
            String algorithm,
            String keyId,
            String nonce,
            String ciphertext,
            String tag,
            String createdAt,
            String associatedData
    ) {
        EncryptionEnvelope {
            Objects.requireNonNull(algorithm);
            Objects.requireNonNull(keyId);
            Objects.requireNonNull(nonce);
            Objects.requireNonNull(ciphertext);
            Objects.requireNonNull(tag);
            Objects.requireNonNull(createdAt);
            Objects.requireNonNull(associatedData);
        }
    }

    record HybridEnvelope(
            String algorithm,
            String encryptedDataKey,
            String nonce,
            String ciphertext,
            String tag
    ) {}

    record EncryptionPolicy(
            int minimumAesBits,
            int minimumRsaBits,
            int minimumTlsVersion,
            boolean requireAuthenticatedEncryption,
            boolean requireCertificateVerification
    ) {
        EncryptionPolicy {
            if (minimumAesBits < 256 ||
                minimumRsaBits < 3072 ||
                minimumTlsVersion < 12) {
                throw new IllegalArgumentException(
                    "Security policy is below minimum requirements"
                );
            }
        }
    }

    record ProtectedAsset(
            String assetId,
            Classification classification,
            StorageType storageType,
            EncryptionType encryptionType,
            String algorithm,
            String keyId,
            boolean tlsRequired
    ) {
        ProtectedAsset {
            if (assetId == null || assetId.isBlank()) {
                throw new IllegalArgumentException(
                    "Asset identifier is required"
                );
            }

            Objects.requireNonNull(classification);
            Objects.requireNonNull(storageType);
            Objects.requireNonNull(encryptionType);
            Objects.requireNonNull(algorithm);
            Objects.requireNonNull(keyId);
        }
    }

    static final class ManagedKey {
        private final String id;
        private final String algorithm;
        private final int bits;
        private final Instant createdAt;

        private SecretKey secretKey;
        private KeyStatus status;

        ManagedKey(
                String id,
                SecretKey secretKey,
                String algorithm,
                int bits
        ) {
            this.id = id;
            this.secretKey = secretKey;
            this.algorithm = algorithm;
            this.bits = bits;
            this.status = KeyStatus.ACTIVE;
            this.createdAt = Instant.now();
        }

        String id() {
            return id;
        }

        String algorithm() {
            return algorithm;
        }

        int bits() {
            return bits;
        }

        KeyStatus status() {
            return status;
        }

        Instant createdAt() {
            return createdAt;
        }

        SecretKey secretKey() {
            if (status == KeyStatus.REVOKED) {
                throw new EncryptionException("Key is revoked");
            }

            return secretKey;
        }

        void setStatus(KeyStatus status) {
            this.status = status;
        }
    }

    static final class KeyManagementService {

        private final Map<String, ManagedKey> keys =
                new HashMap<>();

        private String activeKeyId;

        synchronized ManagedKey createKey(String id) {
            if (id == null ||
                !id.matches("[A-Za-z0-9_-]{1,100}")) {
                throw new IllegalArgumentException(
                    "Invalid key identifier"
                );
            }

            if (keys.containsKey(id)) {
                throw new EncryptionException(
                    "Key identifier already exists"
                );
            }

            try {
                KeyGenerator generator =
                        KeyGenerator.getInstance("AES");

                generator.init(256, RANDOM);

                ManagedKey key = new ManagedKey(
                        id,
                        generator.generateKey(),
                        "AES",
                        256
                );

                keys.put(id, key);
                activeKeyId = id;

                return key;

            } catch (GeneralSecurityException exception) {
                throw new EncryptionException(
                    "Key generation failed",
                    exception
                );
            }
        }

        synchronized ManagedKey activeKey() {
            if (activeKeyId == null) {
                throw new EncryptionException(
                    "No active key is configured"
                );
            }

            return get(activeKeyId);
        }

        synchronized ManagedKey get(String id) {
            ManagedKey key = keys.get(id);

            if (key == null || key.status() == KeyStatus.REVOKED) {
                throw new EncryptionException(
                    "Key is unavailable"
                );
            }

            return key;
        }

        synchronized ManagedKey rotate(String newId) {
            ManagedKey previous = activeKey();

            ManagedKey replacement = createKey(newId);

            previous.setStatus(KeyStatus.ROTATED);

            return replacement;
        }

        synchronized void revoke(String id) {
            ManagedKey key = get(id);
            key.setStatus(KeyStatus.REVOKED);

            if (id.equals(activeKeyId)) {
                activeKeyId = null;
            }
        }

        synchronized int size() {
            return keys.size();
        }
    }

    static final class SymmetricEncryptionService {

        private final KeyManagementService keyManager;

        SymmetricEncryptionService(
                KeyManagementService keyManager
        ) {
            this.keyManager = keyManager;
        }

        EncryptionEnvelope encrypt(
                byte[] plaintext,
                String associatedData
        ) {
            validateData(plaintext);

            try {
                ManagedKey key = keyManager.activeKey();

                byte[] nonce = new byte[GCM_NONCE_BYTES];
                RANDOM.nextBytes(nonce);

                Cipher cipher = Cipher.getInstance(
                        "AES/GCM/NoPadding"
                );

                cipher.init(
                        Cipher.ENCRYPT_MODE,
                        key.secretKey(),
                        new GCMParameterSpec(GCM_TAG_BITS, nonce)
                );

                byte[] aad = associatedData.getBytes(
                        StandardCharsets.UTF_8
                );

                cipher.updateAAD(aad);

                // JCA returns ciphertext followed by the GCM tag.
                byte[] combined = cipher.doFinal(plaintext);

                int tagLength = GCM_TAG_BITS / 8;
                int ciphertextLength = combined.length - tagLength;

                byte[] ciphertext = new byte[ciphertextLength];
                byte[] tag = new byte[tagLength];

                System.arraycopy(
                        combined, 0, ciphertext, 0, ciphertextLength
                );

                System.arraycopy(
                        combined,
                        ciphertextLength,
                        tag,
                        0,
                        tagLength
                );

                Base64.Encoder encoder = Base64.getEncoder();

                return new EncryptionEnvelope(
                        "AES-256-GCM",
                        key.id(),
                        encoder.encodeToString(nonce),
                        encoder.encodeToString(ciphertext),
                        encoder.encodeToString(tag),
                        Instant.now().toString(),
                        encoder.encodeToString(aad)
                );

            } catch (GeneralSecurityException exception) {
                throw new EncryptionException(
                    "Encryption operation failed",
                    exception
                );
            }
        }

        byte[] decrypt(EncryptionEnvelope envelope) {
            Objects.requireNonNull(envelope);

            if (!"AES-256-GCM".equals(envelope.algorithm())) {
                throw new EncryptionException(
                    "Unsupported algorithm"
                );
            }

            try {
                Base64.Decoder decoder = Base64.getDecoder();

                byte[] nonce = decoder.decode(envelope.nonce());
                byte[] ciphertext =
                        decoder.decode(envelope.ciphertext());
                byte[] tag = decoder.decode(envelope.tag());
                byte[] aad =
                        decoder.decode(envelope.associatedData());

                if (nonce.length != GCM_NONCE_BYTES ||
                    tag.length != GCM_TAG_BITS / 8) {
                    throw new EncryptionException(
                        "Invalid encryption parameters"
                    );
                }

                ManagedKey key = keyManager.get(envelope.keyId());

                byte[] combined = new byte[
                        ciphertext.length + tag.length
                ];

                System.arraycopy(
                        ciphertext, 0, combined, 0, ciphertext.length
                );

                System.arraycopy(
                        tag,
                        0,
                        combined,
                        ciphertext.length,
                        tag.length
                );

                Cipher cipher = Cipher.getInstance(
                        "AES/GCM/NoPadding"
                );

                cipher.init(
                        Cipher.DECRYPT_MODE,
                        key.secretKey(),
                        new GCMParameterSpec(GCM_TAG_BITS, nonce)
                );

                cipher.updateAAD(aad);

                return cipher.doFinal(combined);

            } catch (AEADBadTagException exception) {
                throw new EncryptionException(
                    "Authentication failed: ciphertext or metadata modified",
                    exception
                );

            } catch (GeneralSecurityException |
                     IllegalArgumentException exception) {
                throw new EncryptionException(
                    "Decryption failed",
                    exception
                );
            }
        }

        private static void validateData(byte[] data) {
            if (data == null || data.length > MAX_DATA_SIZE) {
                throw new IllegalArgumentException(
                    "Invalid plaintext or size limit exceeded"
                );
            }
        }
    }

    static final class HybridEncryptionService {

        private final KeyPair keyPair;

        HybridEncryptionService() {
            try {
                KeyPairGenerator generator =
                        KeyPairGenerator.getInstance("RSA");

                generator.initialize(3072, RANDOM);

                this.keyPair = generator.generateKeyPair();

            } catch (GeneralSecurityException exception) {
                throw new EncryptionException(
                    "RSA key generation failed",
                    exception
                );
            }
        }

        HybridEnvelope encrypt(byte[] plaintext) {
            if (plaintext == null ||
                plaintext.length > MAX_DATA_SIZE) {
                throw new IllegalArgumentException(
                    "Invalid plaintext"
                );
            }

            try {
                KeyGenerator generator =
                        KeyGenerator.getInstance("AES");

                generator.init(256, RANDOM);

                SecretKey dataKey = generator.generateKey();

                byte[] nonce = new byte[GCM_NONCE_BYTES];
                RANDOM.nextBytes(nonce);

                Cipher aes = Cipher.getInstance(
                        "AES/GCM/NoPadding"
                );

                aes.init(
                        Cipher.ENCRYPT_MODE,
                        dataKey,
                        new GCMParameterSpec(GCM_TAG_BITS, nonce)
                );

                byte[] aad = "hybrid-envelope-v1".getBytes(
                        StandardCharsets.UTF_8
                );

                aes.updateAAD(aad);

                byte[] encryptedData = aes.doFinal(plaintext);

                Cipher rsa = Cipher.getInstance(
                        "RSA/ECB/OAEPWithSHA-256AndMGF1Padding"
                );

                rsa.init(
                        Cipher.ENCRYPT_MODE,
                        keyPair.getPublic(),
                        new javax.crypto.spec.OAEPParameterSpec(
                                "SHA-256",
                                "MGF1",
                                java.security.spec.MGF1ParameterSpec.SHA256,
                                javax.crypto.spec.PSource.PSpecified.DEFAULT
                        )
                );

                byte[] encryptedKey = rsa.doFinal(
                        dataKey.getEncoded()
                );

                int tagLength = GCM_TAG_BITS / 8;
                int ciphertextLength = encryptedData.length - tagLength;

                byte[] ciphertext = new byte[ciphertextLength];
                byte[] tag = new byte[tagLength];

                System.arraycopy(
                        encryptedData, 0, ciphertext, 0, ciphertextLength
                );

                System.arraycopy(
                        encryptedData,
                        ciphertextLength,
                        tag,
                        0,
                        tagLength
                );

                Base64.Encoder encoder = Base64.getEncoder();

                return new HybridEnvelope(
                        "AES-256-GCM+RSA-OAEP-SHA256",
                        encoder.encodeToString(encryptedKey),
                        encoder.encodeToString(nonce),
                        encoder.encodeToString(ciphertext),
                        encoder.encodeToString(tag)
                );

            } catch (GeneralSecurityException exception) {
                throw new EncryptionException(
                    "Hybrid encryption failed",
                    exception
                );
            }
        }

        byte[] decrypt(HybridEnvelope envelope) {
            if (envelope == null ||
                !"AES-256-GCM+RSA-OAEP-SHA256".equals(
                        envelope.algorithm()
                )) {
                throw new EncryptionException(
                    "Unsupported hybrid envelope"
                );
            }

            try {
                Base64.Decoder decoder = Base64.getDecoder();

                byte[] encryptedKey =
                        decoder.decode(envelope.encryptedDataKey());

                byte[] nonce = decoder.decode(envelope.nonce());
                byte[] ciphertext =
                        decoder.decode(envelope.ciphertext());
                byte[] tag = decoder.decode(envelope.tag());

                if (nonce.length != GCM_NONCE_BYTES ||
                    tag.length != GCM_TAG_BITS / 8) {
                    throw new EncryptionException(
                        "Invalid hybrid parameters"
                    );
                }

                Cipher rsa = Cipher.getInstance(
                        "RSA/ECB/OAEPWithSHA-256AndMGF1Padding"
                );

                rsa.init(
                        Cipher.DECRYPT_MODE,
                        keyPair.getPrivate(),
                        new javax.crypto.spec.OAEPParameterSpec(
                                "SHA-256",
                                "MGF1",
                                java.security.spec.MGF1ParameterSpec.SHA256,
                                javax.crypto.spec.PSource.PSpecified.DEFAULT
                        )
                );

                byte[] rawKey = rsa.doFinal(encryptedKey);

                SecretKey dataKey = new javax.crypto.spec.SecretKeySpec(
                        rawKey, "AES"
                );

                byte[] combined = new byte[
                        ciphertext.length + tag.length
                ];

                System.arraycopy(
                        ciphertext, 0, combined, 0, ciphertext.length
                );

                System.arraycopy(
                        tag, 0, combined, ciphertext.length, tag.length
                );

                Cipher aes = Cipher.getInstance(
                        "AES/GCM/NoPadding"
                );

                aes.init(
                        Cipher.DECRYPT_MODE,
                        dataKey,
                        new GCMParameterSpec(GCM_TAG_BITS, nonce)
                );

                aes.updateAAD(
                        "hybrid-envelope-v1".getBytes(
                                StandardCharsets.UTF_8
                        )
                );

                return aes.doFinal(combined);

            } catch (GeneralSecurityException exception) {
                throw new EncryptionException(
                    "Hybrid authentication or decryption failed",
                    exception
                );
            }
        }

        PublicKey publicKey() {
            return keyPair.getPublic();
        }

        PrivateKey privateKey() {
            return keyPair.getPrivate();
        }
    }

    static final class TransportSecurityService {

        static void validate(
                String tlsVersion,
                boolean certificateValid,
                boolean hostnameValid
        ) {
            if (!List.of("TLSv1.2", "TLSv1.3").contains(tlsVersion)) {
                throw new PolicyViolationException(
                    "TLS version is not permitted"
                );
            }

            if (!certificateValid || !hostnameValid) {
                throw new PolicyViolationException(
                    "TLS certificate verification failed"
                );
            }
        }
    }

    static final class EncryptionPolicyService {

        private final EncryptionPolicy policy;
        private final KeyManagementService keyManager;

        EncryptionPolicyService(
                EncryptionPolicy policy,
                KeyManagementService keyManager
        ) {
            this.policy = policy;
            this.keyManager = keyManager;
        }

        Decision evaluate(ProtectedAsset asset) {
            ManagedKey key = keyManager.get(asset.keyId());

            if (key.status() != KeyStatus.ACTIVE) {
                return Decision.REJECTED;
            }

            if (key.bits() < policy.minimumAesBits()) {
                return Decision.REJECTED;
            }

            if (asset.classification() != Classification.PUBLIC &&
                asset.storageType() == StorageType.NETWORK &&
                !asset.tlsRequired()) {
                return Decision.REJECTED;
            }

            if (asset.encryptionType() == EncryptionType.SYMMETRIC &&
                !asset.algorithm().equals("AES-256-GCM")) {
                return Decision.REJECTED;
            }

            if (asset.encryptionType() == EncryptionType.HYBRID &&
                !asset.algorithm().equals(
                    "AES-256-GCM+RSA-OAEP-SHA256"
                )) {
                return Decision.REJECTED;
            }

            if (asset.encryptionType() == EncryptionType.PUBLIC_KEY &&
                !asset.algorithm().equals("RSA-OAEP-SHA256")) {
                return Decision.REJECTED;
            }

            return Decision.APPROVED;
        }
    }

    private static void require(
            boolean condition,
            String message
    ) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    static void runTests() {
        KeyManagementService manager =
                new KeyManagementService();

        manager.createKey("enterprise-key-001");

        SymmetricEncryptionService symmetric =
                new SymmetricEncryptionService(manager);

        byte[] plaintext = "Enterprise confidential record".getBytes(
                StandardCharsets.UTF_8
        );

        EncryptionEnvelope envelope = symmetric.encrypt(
                plaintext,
                "record-001"
        );

        require(
                java.util.Arrays.equals(
                        plaintext,
                        symmetric.decrypt(envelope)
                ),
                "AES-GCM round trip failed"
        );

        EncryptionEnvelope modified = new EncryptionEnvelope(
                envelope.algorithm(),
                envelope.keyId(),
                envelope.nonce(),
                Base64.getEncoder().encodeToString(
                        "modified".getBytes(StandardCharsets.UTF_8)
                ),
                envelope.tag(),
                envelope.createdAt(),
                envelope.associatedData()
        );

        boolean tamperingDetected = false;

        try {
            symmetric.decrypt(modified);
        } catch (EncryptionException exception) {
            tamperingDetected = true;
        }

        require(tamperingDetected, "Tampering was not detected");

        HybridEncryptionService hybrid =
                new HybridEncryptionService();

        HybridEnvelope hybridEnvelope = hybrid.encrypt(plaintext);

        require(
                java.util.Arrays.equals(
                        plaintext,
                        hybrid.decrypt(hybridEnvelope)
                ),
                "Hybrid encryption failed"
        );

        TransportSecurityService.validate(
                "TLSv1.3", true, true
        );

        boolean weakTlsRejected = false;

        try {
            TransportSecurityService.validate(
                    "TLSv1.1", true, true
            );
        } catch (PolicyViolationException exception) {
            weakTlsRejected = true;
        }

        require(weakTlsRejected, "Weak TLS was accepted");

        // Historical ciphertext remains decryptable after rotation.
        manager.rotate("enterprise-key-002");

        require(
                java.util.Arrays.equals(
                        plaintext,
                        symmetric.decrypt(envelope)
                ),
                "Historical key lookup failed"
        );

        EncryptionEnvelope current = symmetric.encrypt(
                plaintext,
                "record-002"
        );

        require(
                java.util.Arrays.equals(
                        plaintext,
                        symmetric.decrypt(current)
                ),
                "Replacement key failed"
        );

        EncryptionPolicy policy = new EncryptionPolicy(
                256,
                3072,
                12,
                true,
                true
        );

        EncryptionPolicyService policyService =
                new EncryptionPolicyService(policy, manager);

        ProtectedAsset asset = new ProtectedAsset(
                "customer-database",
                Classification.CONFIDENTIAL,
                StorageType.DATABASE,
                EncryptionType.SYMMETRIC,
                "AES-256-GCM",
                "enterprise-key-002",
                true
        );

        require(
                policyService.evaluate(asset) == Decision.APPROVED,
                "Valid policy rejected"
        );

        manager.revoke("enterprise-key-002");

        boolean revokedRejected = false;

        try {
            policyService.evaluate(asset);
        } catch (EncryptionException exception) {
            revokedRejected = true;
        }

        require(revokedRejected, "Revoked key accepted");

        System.out.println("All Java 17 encryption tests passed.");
    }

    public static void main(String[] args) {
        try {
            System.out.println("ENTERPRISE ENCRYPTION SYSTEM");
            System.out.println("============================");

            KeyManagementService manager =
                    new KeyManagementService();

            manager.createKey("database-key-001");

            SymmetricEncryptionService symmetric =
                    new SymmetricEncryptionService(manager);

            byte[] data = "Confidential enterprise transaction".getBytes(
                    StandardCharsets.UTF_8
            );

            EncryptionEnvelope encrypted = symmetric.encrypt(
                    data,
                    "transaction-1001"
            );

            System.out.println("\nSymmetric Encryption");
            System.out.println("Algorithm: " + encrypted.algorithm());
            System.out.println(
                    "Recovered: " +
                    new String(
                            symmetric.decrypt(encrypted),
                            StandardCharsets.UTF_8
                    )
            );

            HybridEncryptionService hybrid =
                    new HybridEncryptionService();

            HybridEnvelope hybridEnvelope = hybrid.encrypt(data);

            System.out.println("\nHybrid Encryption");
            System.out.println("Algorithm: " + hybridEnvelope.algorithm());
            System.out.println(
                    "Recovered: " +
                    new String(
                            hybrid.decrypt(hybridEnvelope),
                            StandardCharsets.UTF_8
                    )
            );

            TransportSecurityService.validate(
                    "TLSv1.3", true, true
            );

            System.out.println("\nTransport Security");
            System.out.println("TLS certificate and protocol accepted");

            manager.rotate("database-key-002");

            System.out.println("\nKey Management");
            System.out.println(
                    "Active key: " + manager.activeKey().id()
            );

            runTests();

        } catch (Exception exception) {
            System.err.println(
                    "Security operation failed: " +
                    exception.getMessage()
            );

            System.exit(1);
        }
    }
}
