#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
 * Container Registry Governance Engine
 *
 * C++17 implementation covering:
 * - Repository and manifest management
 * - SHA-256-style content identifiers
 * - Image tags and release channels
 * - Registry access permissions
 * - Immutable production releases
 * - Image security policies
 * - Platform compatibility
 * - Pull and distribution eligibility
 * - Garbage collection
 *
 * The demonstration uses a deterministic content fingerprint.
 * Production implementations must use a cryptographic SHA-256
 * implementation and OCI-compatible manifest serialization.
 */

enum class Role {
    Admin,
    Publisher,
    Consumer
};

enum class ImageState {
    Available,
    Quarantined,
    Deleted
};

enum class Operation {
    Create,
    Push,
    Pull,
    Delete,
    Manage
};

struct User {
    std::string username;
    std::string token;
    Role role;
    bool active = true;
};

struct Manifest {
    std::string digest;
    std::string content;
    std::string architecture;
    std::string operatingSystem;
    std::size_t size = 0;
    bool signedImage = false;
    int vulnerabilities = 0;
    ImageState state = ImageState::Available;
};

struct Tag {
    std::string name;
    std::string digest;
    bool immutable = false;
};

struct Repository {
    std::string name;
    bool privateRepository = true;

    std::map<std::string, Manifest> manifests;
    std::map<std::string, Tag> tags;
};

struct RegistryPolicy {
    std::size_t maximumImageSize = 10'000'000;
    int maximumVulnerabilities = 0;
    bool requireSignature = true;
    std::set<std::string> permittedArchitectures{
        "amd64", "arm64"
    };
};

struct AuditEvent {
    std::string username;
    std::string operation;
    std::string repository;
    std::string reference;
    std::string result;
};

class RegistryException : public std::runtime_error {
public:
    explicit RegistryException(const std::string& message)
        : std::runtime_error(message) {}
};

class ContainerRegistry {
private:
    std::string registryName;
    RegistryPolicy policy;

    std::unordered_map<std::string, User> users;
    std::map<std::string, Repository> repositories;

    std::vector<AuditEvent> audit;

    static std::string operationName(Operation operation) {
        switch (operation) {
            case Operation::Create: return "CREATE";
            case Operation::Push: return "PUSH";
            case Operation::Pull: return "PULL";
            case Operation::Delete: return "DELETE";
            case Operation::Manage: return "MANAGE";
        }

        throw RegistryException("Unknown operation.");
    }

    static bool validRepository(const std::string& name) {
        if (name.empty() || name.size() > 255) {
            return false;
        }

        if (name.front() == '/' || name.back() == '/') {
            return false;
        }

        for (char c : name) {
            const bool valid =
                (c >= 'a' && c <= 'z') ||
                (c >= '0' && c <= '9') ||
                c == '/' || c == '.' || c == '_' || c == '-';

            if (!valid) return false;
        }

        return true;
    }

    static bool validTag(const std::string& tag) {
        if (tag.empty() || tag.size() > 128) return false;

        const char first = tag.front();

        if (!std::isalnum(static_cast<unsigned char>(first)) &&
            first != '_') {
            return false;
        }

        for (char c : tag) {
            if (!std::isalnum(static_cast<unsigned char>(c)) &&
                c != '_' && c != '.' && c != '-') {
                return false;
            }
        }

        return true;
    }

    static std::string fingerprint(const std::string& content) {
        // Noncryptographic demonstration only.
        // Never use std::hash for production image integrity.
        std::uint64_t hash = 14695981039346656037ULL;

        for (unsigned char c : content) {
            hash ^= c;
            hash *= 1099511628211ULL;
        }

        std::ostringstream output;
        output << "demo:" << std::hex
               << std::setw(16) << std::setfill('0')
               << hash;

        return output.str();
    }

    User& authenticate(const std::string& token) {
        for (auto& [username, user] : users) {
            if (user.token == token) {
                if (!user.active) {
                    throw RegistryException("Account is disabled.");
                }

                return user;
            }
        }

        throw RegistryException("Authentication failed.");
    }

    void authorize(const User& user, Operation operation) const {
        bool permitted = false;

        switch (user.role) {
            case Role::Admin:
                permitted = true;
                break;

            case Role::Publisher:
                permitted =
                    operation == Operation::Push ||
                    operation == Operation::Pull;
                break;

            case Role::Consumer:
                permitted = operation == Operation::Pull;
                break;
        }

        if (!permitted) {
            throw RegistryException(
                "Role does not permit " + operationName(operation)
            );
        }
    }

    Repository& getRepository(const std::string& name) {
        auto it = repositories.find(name);

        if (it == repositories.end()) {
            throw RegistryException("Repository not found.");
        }

        return it->second;
    }

    void record(
        const User& user,
        Operation operation,
        const std::string& repository,
        const std::string& reference,
        const std::string& result
    ) {
        audit.push_back({
            user.username,
            operationName(operation),
            repository,
            reference,
            result
        });
    }

    void evaluatePolicy(
        const std::string& content,
        const std::string& architecture,
        const std::string& os,
        bool signedImage,
        int vulnerabilities
    ) const {
        if (content.empty()) {
            throw RegistryException("Empty image content.");
        }

        if (content.size() > policy.maximumImageSize) {
            throw RegistryException("Image exceeds size limit.");
        }

        if (policy.requireSignature && !signedImage) {
            throw RegistryException("Image signature required.");
        }

        if (vulnerabilities < 0 ||
            vulnerabilities > policy.maximumVulnerabilities) {
            throw RegistryException("Vulnerability policy failed.");
        }

        if (!policy.permittedArchitectures.count(architecture)) {
            throw RegistryException("Unsupported architecture.");
        }

        if (os.empty()) {
            throw RegistryException("Operating system is required.");
        }
    }

public:
    explicit ContainerRegistry(
        std::string name,
        RegistryPolicy registryPolicy = {}
    )
        : registryName(std::move(name)),
          policy(std::move(registryPolicy)) {

        if (registryName.empty()) {
            throw RegistryException("Registry name is required.");
        }
    }

    void registerUser(User user) {
        if (user.username.empty() ||
            user.token.empty() ||
            users.count(user.username)) {
            throw RegistryException("Invalid user registration.");
        }

        users.emplace(user.username, std::move(user));
    }

    void createRepository(
        const std::string& token,
        const std::string& name,
        bool privateRepository = true
    ) {
        User& user = authenticate(token);
        authorize(user, Operation::Create);

        if (!validRepository(name)) {
            throw RegistryException("Invalid repository name.");
        }

        if (repositories.count(name)) {
            throw RegistryException("Repository already exists.");
        }

        repositories.emplace(
            name,
            Repository{name, privateRepository, {}, {}}
        );

        record(user, Operation::Create, name, name, "SUCCESS");
    }

    std::string push(
        const std::string& token,
        const std::string& repositoryName,
        const std::string& tagName,
        const std::string& content,
        const std::string& architecture,
        const std::string& os,
        bool signedImage,
        int vulnerabilities,
        bool immutable = false
    ) {
        User& user = authenticate(token);
        authorize(user, Operation::Push);

        Repository& repository = getRepository(repositoryName);

        if (!validTag(tagName)) {
            throw RegistryException("Invalid tag.");
        }

        evaluatePolicy(
            content,
            architecture,
            os,
            signedImage,
            vulnerabilities
        );

        const std::string digest = fingerprint(content);

        auto existingTag = repository.tags.find(tagName);

        if (existingTag != repository.tags.end() &&
            existingTag->second.immutable &&
            existingTag->second.digest != digest) {
            throw RegistryException("Immutable tag cannot be replaced.");
        }

        auto manifest = repository.manifests.find(digest);

        if (manifest == repository.manifests.end()) {
            repository.manifests.emplace(
                digest,
                Manifest{
                    digest,
                    content,
                    architecture,
                    os,
                    content.size(),
                    signedImage,
                    vulnerabilities,
                    ImageState::Available
                }
            );
        }

        const bool finalImmutable =
            immutable ||
            (existingTag != repository.tags.end() &&
             existingTag->second.immutable);

        repository.tags[tagName] = Tag{
            tagName,
            digest,
            finalImmutable
        };

        record(user, Operation::Push, repositoryName, tagName, "SUCCESS");

        return digest;
    }

    const Manifest& pull(
        const std::string& token,
        const std::string& repositoryName,
        const std::string& reference
    ) {
        User& user = authenticate(token);
        authorize(user, Operation::Pull);

        Repository& repository = getRepository(repositoryName);

        std::string digest = reference;

        if (reference.rfind("demo:", 0) != 0) {
            auto tag = repository.tags.find(reference);

            if (tag == repository.tags.end()) {
                throw RegistryException("Image tag not found.");
            }

            digest = tag->second.digest;
        }

        auto manifest = repository.manifests.find(digest);

        if (manifest == repository.manifests.end() ||
            manifest->second.state != ImageState::Available) {
            throw RegistryException("Image is unavailable.");
        }

        if (fingerprint(manifest->second.content) != digest) {
            throw RegistryException("Content integrity check failed.");
        }

        record(user, Operation::Pull, repositoryName, reference, "SUCCESS");

        return manifest->second;
    }

    void deleteTag(
        const std::string& token,
        const std::string& repositoryName,
        const std::string& tagName
    ) {
        User& user = authenticate(token);
        authorize(user, Operation::Delete);

        Repository& repository = getRepository(repositoryName);

        auto tag = repository.tags.find(tagName);

        if (tag == repository.tags.end()) {
            throw RegistryException("Tag not found.");
        }

        if (tag->second.immutable) {
            throw RegistryException("Cannot delete immutable tag.");
        }

        repository.tags.erase(tag);

        record(user, Operation::Delete, repositoryName, tagName, "SUCCESS");
    }

    std::size_t garbageCollect(const std::string& token) {
        User& user = authenticate(token);
        authorize(user, Operation::Manage);

        std::size_t removed = 0;

        for (auto& [name, repository] : repositories) {
            std::set<std::string> referenced;

            for (const auto& [tagName, tag] : repository.tags) {
                referenced.insert(tag.digest);
            }

            for (auto it = repository.manifests.begin();
                 it != repository.manifests.end();) {

                if (!referenced.count(it->first)) {
                    it = repository.manifests.erase(it);
                    ++removed;
                } else {
                    ++it;
                }
            }
        }

        record(
            user,
            Operation::Manage,
            "*",
            "GARBAGE_COLLECTION",
            "SUCCESS"
        );

        return removed;
    }

    void printRepository(const std::string& name) const {
        auto repository = repositories.find(name);

        if (repository == repositories.end()) {
            throw RegistryException("Repository not found.");
        }

        std::cout << "\nRepository: " << name << '\n';

        for (const auto& [tagName, tag] : repository->second.tags) {
            std::cout
                << "Tag: " << tagName
                << " | Digest: " << tag.digest
                << " | Immutable: "
                << std::boolalpha << tag.immutable
                << '\n';
        }
    }

    void printAudit() const {
        std::cout << "\nRegistry audit:\n";

        for (const auto& event : audit) {
            std::cout
                << event.username << " | "
                << event.operation << " | "
                << event.repository << " | "
                << event.reference << " | "
                << event.result << '\n';
        }
    }
};

int main() {
    try {
        RegistryPolicy policy;
        policy.maximumImageSize = 1'000'000;
        policy.maximumVulnerabilities = 1;
        policy.requireSignature = true;

        ContainerRegistry registry(
            "registry.internal.example",
            policy
        );

        registry.registerUser({
            "admin",
            "admin-secret",
            Role::Admin
        });

        registry.registerUser({
            "build-service",
            "publisher-secret",
            Role::Publisher
        });

        registry.registerUser({
            "deployment-service",
            "consumer-secret",
            Role::Consumer
        });

        registry.createRepository(
            "admin-secret",
            "production/inventory-service",
            true
        );

        const std::string digest = registry.push(
            "publisher-secret",
            "production/inventory-service",
            "1.0.0",
            "inventory-container-image-v1",
            "amd64",
            "linux",
            true,
            0,
            true
        );

        registry.push(
            "publisher-secret",
            "production/inventory-service",
            "latest",
            "inventory-container-image-v1",
            "amd64",
            "linux",
            true,
            0
        );

        const Manifest& downloaded = registry.pull(
            "consumer-secret",
            "production/inventory-service",
            "1.0.0"
        );

        std::cout << "Registry: registry.internal.example\n";
        std::cout << "Published digest: " << digest << '\n';
        std::cout << "Downloaded digest: " << downloaded.digest << '\n';
        std::cout << "Image size: " << downloaded.size << " bytes\n";

        if (digest == downloaded.digest) {
            std::cout << "Integrity verification: PASSED\n";
        }

        // An immutable production release cannot be overwritten.
        try {
            registry.push(
                "publisher-secret",
                "production/inventory-service",
                "1.0.0",
                "different-image",
                "amd64",
                "linux",
                true,
                0
            );
        } catch (const RegistryException& error) {
            std::cout << "\nImmutable tag rejection: "
                      << error.what() << '\n';
        }

        // A consumer cannot publish an image.
        try {
            registry.push(
                "consumer-secret",
                "production/inventory-service",
                "2.0.0",
                "unauthorized-image",
                "amd64",
                "linux",
                true,
                0
            );
        } catch (const RegistryException& error) {
            std::cout << "Authorization rejection: "
                      << error.what() << '\n';
        }

        // Unsigned images fail the security policy.
        try {
            registry.push(
                "publisher-secret",
                "production/inventory-service",
                "2.0.0",
                "unsigned-image",
                "amd64",
                "linux",
                false,
                0
            );
        } catch (const RegistryException& error) {
            std::cout << "Security rejection: "
                      << error.what() << '\n';
        }

        registry.printRepository("production/inventory-service");

        std::cout << "\nUnreferenced manifests removed: "
                  << registry.garbageCollect("admin-secret") << '\n';

        registry.printAudit();

    } catch (const std::exception& error) {
        std::cerr << "Registry failure: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
