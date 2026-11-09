#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Encryption Governance Engine
 *
 * C++17 implementation of encryption architecture governance.
 *
 * The C++17 standard library does not provide AES, RSA, or TLS.
 * This program therefore evaluates cryptographic configurations,
 * key lifecycle state, data classifications, and security policies.
 *
 * It does not implement cryptographic primitives or claim that
 * metadata validation encrypts actual application data.
 */

enum class EncryptionType {
    SYMMETRIC,
    PUBLIC_KEY,
    HYBRID
};

enum class StorageLocation {
    DATABASE,
    FILE_SYSTEM,
    BACKUP,
    NETWORK
};

enum class KeyState {
    ACTIVE,
    ROTATED,
    REVOKED,
    EXPIRED
};

enum class DataClassification {
    PUBLIC,
    INTERNAL,
    CONFIDENTIAL,
    RESTRICTED
};

enum class Decision {
    APPROVED,
    REJECTED,
    WARNING
};

struct EncryptionProfile {
    std::string algorithm;
    int keyBits;
    int nonceBits;
    int tagBits;
    bool authenticated;
    bool approved;
};

struct KeyRecord {
    std::string id;
    std::string algorithm;
    int keyBits;
    KeyState state;
    std::chrono::system_clock::time_point createdAt;
    std::optional<std::string> successorId;
};

struct ProtectedResource {
    std::string id;
    DataClassification classification;
    StorageLocation location;
    EncryptionType encryptionType;
    std::string keyId;
    std::string algorithm;
    bool tlsRequired;
};

struct SecurityPolicy {
    int minimumSymmetricBits = 256;
    int minimumRsaBits = 3072;
    int minimumTlsVersion = 12;
    int maximumKeyAgeDays = 365;
    bool requireAuthenticatedEncryption = true;
    bool prohibitDirectPublicDataEncryption = false;
};

struct EvaluationResult {
    Decision decision;
    std::vector<std::string> findings;
};

class ValidationError : public std::runtime_error {
public:
    explicit ValidationError(const std::string& message)
        : std::runtime_error(message) {}
};

class KeyVault {
private:
    std::unordered_map<std::string, KeyRecord> keys;

public:
    void registerKey(const KeyRecord& key) {
        if (key.id.empty() || key.id.size() > 100) {
            throw ValidationError("Invalid key identifier");
        }

        if (keys.count(key.id)) {
            throw ValidationError("Duplicate key identifier");
        }

        if (key.keyBits < 128) {
            throw ValidationError("Key size is below minimum");
        }

        keys.emplace(key.id, key);
    }

    const KeyRecord& get(const std::string& id) const {
        auto iterator = keys.find(id);

        if (iterator == keys.end()) {
            throw ValidationError("Unknown encryption key");
        }

        return iterator->second;
    }

    void rotate(
        const std::string& oldId,
        const std::string& newId
    ) {
        auto oldIterator = keys.find(oldId);

        if (oldIterator == keys.end()) {
            throw ValidationError("Old key does not exist");
        }

        if (oldIterator->second.state != KeyState::ACTIVE) {
            throw ValidationError("Only active keys can be rotated");
        }

        if (oldId == newId || keys.count(newId)) {
            throw ValidationError("Invalid successor key identifier");
        }

        KeyRecord replacement{
            newId,
            oldIterator->second.algorithm,
            oldIterator->second.keyBits,
            KeyState::ACTIVE,
            std::chrono::system_clock::now(),
            std::nullopt
        };

        // Prepare the replacement before changing the old record.
        keys.emplace(newId, replacement);

        oldIterator->second.state = KeyState::ROTATED;
        oldIterator->second.successorId = newId;
    }

    void revoke(const std::string& id) {
        auto iterator = keys.find(id);

        if (iterator == keys.end()) {
            throw ValidationError("Unknown key");
        }

        if (iterator->second.state == KeyState::REVOKED) {
            throw ValidationError("Key already revoked");
        }

        iterator->second.state = KeyState::REVOKED;
    }

    std::size_t size() const {
        return keys.size();
    }
};

class AlgorithmRegistry {
private:
    std::map<std::string, EncryptionProfile> profiles;

public:
    AlgorithmRegistry() {
        profiles.emplace(
            "AES-256-GCM",
            EncryptionProfile{
                "AES-256-GCM", 256, 96, 128, true, true
            }
        );

        profiles.emplace(
            "AES-128-GCM",
            EncryptionProfile{
                "AES-128-GCM", 128, 96, 128, true, true
            }
        );

        profiles.emplace(
            "RSA-OAEP-SHA256",
            EncryptionProfile{
                "RSA-OAEP-SHA256", 3072, 0, 0, false, true
            }
        );

        profiles.emplace(
            "AES-256-CBC",
            EncryptionProfile{
                "AES-256-CBC", 256, 128, 0, false, true
            }
        );

        profiles.emplace(
            "AES-256-GCM+RSA-OAEP-SHA256",
            EncryptionProfile{
                "AES-256-GCM+RSA-OAEP-SHA256",
                256, 96, 128, true, true
            }
        );
    }

    const EncryptionProfile& get(
        const std::string& algorithm
    ) const {
        auto iterator = profiles.find(algorithm);

        if (iterator == profiles.end()) {
            throw ValidationError("Unknown algorithm");
        }

        return iterator->second;
    }
};

class EncryptionGovernanceEngine {
private:
    const KeyVault& vault;
    const AlgorithmRegistry& registry;
    SecurityPolicy policy;

    int ageInDays(const KeyRecord& key) const {
        auto duration =
            std::chrono::system_clock::now() - key.createdAt;

        return static_cast<int>(
            std::chrono::duration_cast<std::chrono::hours>(
                duration
            ).count() / 24
        );
    }

public:
    EncryptionGovernanceEngine(
        const KeyVault& vaultReference,
        const AlgorithmRegistry& registryReference,
        SecurityPolicy securityPolicy
    )
        : vault(vaultReference),
          registry(registryReference),
          policy(securityPolicy) {}

    EvaluationResult evaluate(
        const ProtectedResource& resource,
        int tlsVersion
    ) const {

        EvaluationResult result{
            Decision::APPROVED,
            {}
        };

        auto reject = [&](const std::string& reason) {
            result.decision = Decision::REJECTED;
            result.findings.push_back(reason);
        };

        if (resource.id.empty()) {
            reject("Resource identifier is missing");
            return result;
        }

        const EncryptionProfile* profile = nullptr;
        const KeyRecord* key = nullptr;

        try {
            profile = &registry.get(resource.algorithm);
            key = &vault.get(resource.keyId);
        } catch (const std::exception& error) {
            reject(error.what());
            return result;
        }

        if (!profile->approved) {
            reject("Algorithm is not approved");
        }

        if (key->state == KeyState::REVOKED ||
            key->state == KeyState::EXPIRED) {
            reject("Encryption key is unavailable");
        }

        if (key->algorithm != resource.algorithm &&
            !(resource.encryptionType == EncryptionType::HYBRID &&
              key->algorithm == "AES-256-GCM")) {
            reject("Algorithm and key metadata do not match");
        }

        if (key->state == KeyState::ROTATED) {
            reject("Rotated key cannot protect new resources");
        }

        if (ageInDays(*key) > policy.maximumKeyAgeDays) {
            reject("Encryption key exceeds maximum age");
        }

        if (resource.encryptionType == EncryptionType::SYMMETRIC) {
            if (profile->algorithm.find("AES-") != 0) {
                reject("Symmetric encryption requires an AES profile");
            }

            if (profile->keyBits < policy.minimumSymmetricBits) {
                reject("Symmetric key size is insufficient");
            }
        }

        if (resource.encryptionType == EncryptionType::PUBLIC_KEY) {
            if (profile->algorithm.find("RSA-") != 0) {
                reject("Public-key encryption requires RSA profile");
            }

            if (profile->keyBits < policy.minimumRsaBits) {
                reject("RSA key size is insufficient");
            }
        }

        if (resource.encryptionType == EncryptionType::HYBRID) {
            if (resource.algorithm !=
                "AES-256-GCM+RSA-OAEP-SHA256") {
                reject("Hybrid encryption profile is not approved");
            }
        }

        if (policy.requireAuthenticatedEncryption &&
            !profile->authenticated) {
            reject("Authenticated encryption is required");
        }

        if (resource.classification != DataClassification::PUBLIC &&
            resource.location != StorageLocation::NETWORK &&
            !resource.tlsRequired) {
            result.findings.push_back(
                "TLS is required when this resource is transmitted"
            );
            result.decision = Decision::REJECTED;
        }

        if (resource.location == StorageLocation::NETWORK ||
            resource.tlsRequired) {
            if (tlsVersion < policy.minimumTlsVersion) {
                reject("TLS version is below the required minimum");
            }
        }

        if (result.decision == Decision::APPROVED) {
            result.findings.push_back(
                "Cryptographic configuration satisfies policy"
            );
        }

        return result;
    }
};

class Repository {
private:
    std::unordered_map<std::string, ProtectedResource> resources;

public:
    void registerResource(const ProtectedResource& resource) {
        if (resource.id.empty()) {
            throw ValidationError("Resource ID is required");
        }

        if (resources.count(resource.id)) {
            throw ValidationError("Duplicate resource");
        }

        resources.emplace(resource.id, resource);
    }

    const ProtectedResource& get(
        const std::string& id
    ) const {
        auto iterator = resources.find(id);

        if (iterator == resources.end()) {
            throw ValidationError("Resource not found");
        }

        return iterator->second;
    }

    std::size_t size() const {
        return resources.size();
    }
};

void printResult(
    const std::string& name,
    const EvaluationResult& result
) {
    std::cout << "\n" << name << "\n";

    std::cout << "Decision: ";

    switch (result.decision) {
        case Decision::APPROVED:
            std::cout << "APPROVED";
            break;
        case Decision::REJECTED:
            std::cout << "REJECTED";
            break;
        case Decision::WARNING:
            std::cout << "WARNING";
            break;
    }

    std::cout << "\n";

    for (const auto& finding : result.findings) {
        std::cout << " - " << finding << "\n";
    }
}

void runTests() {
    AlgorithmRegistry registry;
    KeyVault vault;

    const auto now = std::chrono::system_clock::now();

    vault.registerKey({
        "key-001",
        "AES-256-GCM",
        256,
        KeyState::ACTIVE,
        now,
        std::nullopt
    });

    vault.registerKey({
        "rsa-001",
        "RSA-OAEP-SHA256",
        3072,
        KeyState::ACTIVE,
        now,
        std::nullopt
    });

    SecurityPolicy policy;

    EncryptionGovernanceEngine engine(
        vault,
        registry,
        policy
    );

    ProtectedResource database{
        "customer-database",
        DataClassification::CONFIDENTIAL,
        StorageLocation::DATABASE,
        EncryptionType::SYMMETRIC,
        "key-001",
        "AES-256-GCM",
        true
    };

    auto approved = engine.evaluate(database, 13);

    if (approved.decision != Decision::APPROVED) {
        throw std::runtime_error("Valid configuration rejected");
    }

    ProtectedResource insecure{
        "legacy-backup",
        DataClassification::RESTRICTED,
        StorageLocation::BACKUP,
        EncryptionType::SYMMETRIC,
        "key-001",
        "AES-256-CBC",
        true
    };

    auto rejected = engine.evaluate(insecure, 13);

    if (rejected.decision != Decision::REJECTED) {
        throw std::runtime_error("Unauthenticated encryption accepted");
    }

    auto weakTls = engine.evaluate(database, 11);

    if (weakTls.decision != Decision::REJECTED) {
        throw std::runtime_error("Weak TLS accepted");
    }

    // Key rotation preserves historical key metadata.
    vault.rotate("key-001", "key-002");

    bool rotationRejected = false;

    try {
        engine.evaluate(database, 13);
    } catch (const std::exception&) {
        rotationRejected = true;
    }

    // The old key exists but cannot protect new resources.
    auto oldKeyResult = engine.evaluate(database, 13);

    if (oldKeyResult.decision != Decision::REJECTED) {
        throw std::runtime_error("Rotated key incorrectly approved");
    }

    ProtectedResource updated = database;
    updated.keyId = "key-002";

    auto newKeyResult = engine.evaluate(updated, 13);

    if (newKeyResult.decision != Decision::APPROVED) {
        throw std::runtime_error("Replacement key rejected");
    }

    vault.revoke("key-002");

    auto revokedResult = engine.evaluate(updated, 13);

    if (revokedResult.decision != Decision::REJECTED) {
        throw std::runtime_error("Revoked key incorrectly approved");
    }

    Repository repository;
    repository.registerResource(database);

    if (repository.size() != 1) {
        throw std::runtime_error("Repository count mismatch");
    }

    std::cout << "\nAll C++ governance tests passed.\n";
}

int main() {
    try {
        std::cout << "ENCRYPTION GOVERNANCE ENGINE\n";
        std::cout << "============================\n";

        AlgorithmRegistry registry;
        KeyVault vault;

        auto now = std::chrono::system_clock::now();

        vault.registerKey({
            "database-key-001",
            "AES-256-GCM",
            256,
            KeyState::ACTIVE,
            now,
            std::nullopt
        });

        vault.registerKey({
            "public-key-001",
            "RSA-OAEP-SHA256",
            3072,
            KeyState::ACTIVE,
            now,
            std::nullopt
        });

        SecurityPolicy policy;

        EncryptionGovernanceEngine engine(
            vault,
            registry,
            policy
        );

        ProtectedResource database{
            "customer-records",
            DataClassification::CONFIDENTIAL,
            StorageLocation::DATABASE,
            EncryptionType::SYMMETRIC,
            "database-key-001",
            "AES-256-GCM",
            true
        };

        ProtectedResource transmission{
            "api-document",
            DataClassification::RESTRICTED,
            StorageLocation::NETWORK,
            EncryptionType::HYBRID,
            "database-key-001",
            "AES-256-GCM+RSA-OAEP-SHA256",
            true
        };

        printResult(
            "Database encryption policy",
            engine.evaluate(database, 13)
        );

        printResult(
            "Hybrid transmission policy",
            engine.evaluate(transmission, 13)
        );

        ProtectedResource legacy{
            "legacy-storage",
            DataClassification::RESTRICTED,
            StorageLocation::BACKUP,
            EncryptionType::SYMMETRIC,
            "database-key-001",
            "AES-256-CBC",
            true
        };

        printResult(
            "Legacy encryption policy",
            engine.evaluate(legacy, 13)
        );

        runTests();

        std::cout << "\nRegistered keys: " << vault.size() << "\n";

        return 0;

    } catch (const std::exception& error) {
        std::cerr << "Governance failure: "
                  << error.what() << "\n";

        return 1;
    }
}
