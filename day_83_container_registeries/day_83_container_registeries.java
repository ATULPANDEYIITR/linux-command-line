import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

/*
 * Enterprise Container Registry Governance System
 *
 * Java 17 implementation covering:
 * - Domain-driven registry modeling
 * - OCI-oriented image manifest metadata
 * - Immutable image references
 * - Role-based access control
 * - Enterprise release policies
 * - Image signing requirements
 * - Vulnerability thresholds
 * - Repository lifecycle management
 * - Asynchronous distribution eligibility
 * - Audit and garbage collection
 *
 * Compile:
 * javac ContainerRegistry.java
 *
 * Execute:
 * java ContainerRegistry
 */

public class ContainerRegistry {

    enum Role {
        ADMIN,
        PUBLISHER,
        CONSUMER
    }

    enum Operation {
        CREATE,
        PUSH,
        PULL,
        DELETE,
        MANAGE
    }

    enum ImageStatus {
        AVAILABLE,
        QUARANTINED,
        DELETED
    }

    enum DistributionStatus {
        PENDING,
        DELIVERED,
        FAILED
    }

    static class RegistryException extends RuntimeException {
        RegistryException(String message) {
            super(message);
        }
    }

    static class AuthorizationException extends RegistryException {
        AuthorizationException(String message) {
            super(message);
        }
    }

    static class PolicyException extends RegistryException {
        PolicyException(String message) {
            super(message);
        }
    }

    static class ImmutableTagException extends RegistryException {
        ImmutableTagException(String message) {
            super(message);
        }
    }

    record RegistryUser(
        String username,
        String token,
        Role role,
        boolean active
    ) {
        RegistryUser {
            Objects.requireNonNull(username);
            Objects.requireNonNull(token);
            Objects.requireNonNull(role);

            if (username.isBlank() || token.isBlank()) {
                throw new IllegalArgumentException(
                    "Username and token are required."
                );
            }
        }
    }

    record RegistryPolicy(
        long maximumImageSize,
        int maximumVulnerabilities,
        boolean signatureRequired,
        Set<String> permittedArchitectures
    ) {
        RegistryPolicy {
            if (maximumImageSize <= 0 ||
                maximumVulnerabilities < 0) {
                throw new IllegalArgumentException(
                    "Invalid registry policy."
                );
            }

            permittedArchitectures =
                Set.copyOf(permittedArchitectures);
        }
    }

    record ImageManifest(
        String repository,
        String digest,
        byte[] content,
        String mediaType,
        String architecture,
        String operatingSystem,
        long size,
        boolean signed,
        int vulnerabilities,
        Instant createdAt,
        ImageStatus status
    ) {
        ImageManifest {
            Objects.requireNonNull(repository);
            Objects.requireNonNull(digest);
            Objects.requireNonNull(content);
            Objects.requireNonNull(status);

            // Prevent callers from changing stored image bytes.
            content = content.clone();
        }

        @Override
        public byte[] content() {
            return content.clone();
        }
    }

    record ImageTag(
        String name,
        String digest,
        boolean immutable,
        Instant updatedAt
    ) {}

    record AuditEvent(
        Instant timestamp,
        String username,
        Operation operation,
        String repository,
        String reference,
        String result
    ) {}

    record DistributionTarget(
        String name,
        boolean available
    ) {}

    record DistributionResult(
        String target,
        DistributionStatus status,
        String digest
    ) {}

    static final class Repository {
        private final String name;
        private final boolean privateRepository;

        private final Map<String, ImageManifest> manifests =
            new HashMap<>();

        private final Map<String, ImageTag> tags =
            new HashMap<>();

        Repository(String name, boolean privateRepository) {
            this.name = name;
            this.privateRepository = privateRepository;
        }

        String name() {
            return name;
        }

        boolean isPrivate() {
            return privateRepository;
        }

        Map<String, ImageManifest> manifests() {
            return Map.copyOf(manifests);
        }

        Map<String, ImageTag> tags() {
            return Map.copyOf(tags);
        }
    }

    static final class AccessControlService {

        private final Map<Role, Set<Operation>> permissions =
            Map.of(
                Role.ADMIN,
                EnumSet.allOf(Operation.class),

                Role.PUBLISHER,
                EnumSet.of(Operation.PUSH, Operation.PULL),

                Role.CONSUMER,
                EnumSet.of(Operation.PULL)
            );

        void verify(
            RegistryUser user,
            Operation operation
        ) {
            if (!user.active()) {
                throw new AuthorizationException(
                    "User account is inactive."
                );
            }

            if (!permissions.get(user.role()).contains(operation)) {
                throw new AuthorizationException(
                    "Role cannot perform " + operation
                );
            }
        }
    }

    static final class ImagePolicyService {

        private final RegistryPolicy policy;

        ImagePolicyService(RegistryPolicy policy) {
            this.policy = policy;
        }

        void validate(
            byte[] content,
            boolean signed,
            int vulnerabilities,
            String architecture,
            String os
        ) {
            if (content == null || content.length == 0) {
                throw new PolicyException(
                    "Image content cannot be empty."
                );
            }

            if (content.length > policy.maximumImageSize()) {
                throw new PolicyException(
                    "Image exceeds configured size."
                );
            }

            if (policy.signatureRequired() && !signed) {
                throw new PolicyException(
                    "Signed image required."
                );
            }

            if (vulnerabilities < 0 ||
                vulnerabilities > policy.maximumVulnerabilities()) {
                throw new PolicyException(
                    "Vulnerability policy violation."
                );
            }

            if (!policy.permittedArchitectures().contains(architecture)) {
                throw new PolicyException(
                    "Architecture is not permitted."
                );
            }

            if (os == null || os.isBlank()) {
                throw new PolicyException(
                    "Operating system is required."
                );
            }
        }
    }

    static final class ContainerRegistryService {

        private static final Pattern REPOSITORY_PATTERN =
            Pattern.compile(
                "^[a-z0-9]+(?:[._-][a-z0-9]+)*" +
                "(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$"
            );

        private static final Pattern TAG_PATTERN =
            Pattern.compile("^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$");

        private final String registryName;

        private final Map<String, RegistryUser> users =
            new HashMap<>();

        private final Map<String, Repository> repositories =
            new HashMap<>();

        private final List<AuditEvent> auditEvents =
            new ArrayList<>();

        private final AccessControlService accessControl =
            new AccessControlService();

        private final ImagePolicyService imagePolicy;

        ContainerRegistryService(
            String registryName,
            RegistryPolicy policy
        ) {
            if (registryName == null || registryName.isBlank()) {
                throw new IllegalArgumentException(
                    "Registry name is required."
                );
            }

            this.registryName = registryName;
            this.imagePolicy = new ImagePolicyService(policy);
        }

        void registerUser(RegistryUser user) {
            if (users.putIfAbsent(user.username(), user) != null) {
                throw new RegistryException(
                    "User already registered."
                );
            }
        }

        RegistryUser authenticate(String token) {
            return users.values()
                .stream()
                .filter(user -> MessageDigest.isEqual(
                    user.token().getBytes(StandardCharsets.UTF_8),
                    token.getBytes(StandardCharsets.UTF_8)
                ))
                .filter(RegistryUser::active)
                .findFirst()
                .orElseThrow(() ->
                    new RegistryException(
                        "Authentication failed."
                    )
                );
        }

        void createRepository(
            String token,
            String name,
            boolean privateRepository
        ) {
            RegistryUser user = authenticate(token);

            accessControl.verify(user, Operation.CREATE);

            if (!REPOSITORY_PATTERN.matcher(name).matches()) {
                throw new IllegalArgumentException(
                    "Invalid repository name."
                );
            }

            Repository repository =
                new Repository(name, privateRepository);

            if (repositories.putIfAbsent(name, repository) != null) {
                throw new RegistryException(
                    "Repository already exists."
                );
            }

            audit(
                user,
                Operation.CREATE,
                name,
                name,
                "SUCCESS"
            );
        }

        private Repository getRepository(String name) {
            Repository repository = repositories.get(name);

            if (repository == null) {
                throw new RegistryException(
                    "Repository not found."
                );
            }

            return repository;
        }

        private static String calculateDigest(byte[] content) {
            try {
                MessageDigest digest =
                    MessageDigest.getInstance("SHA-256");

                byte[] bytes = digest.digest(content);

                StringBuilder output = new StringBuilder("sha256:");

                for (byte value : bytes) {
                    output.append(
                        String.format("%02x", value & 0xff)
                    );
                }

                return output.toString();

            } catch (NoSuchAlgorithmException exception) {
                throw new IllegalStateException(
                    "SHA-256 is unavailable.",
                    exception
                );
            }
        }

        private void audit(
            RegistryUser user,
            Operation operation,
            String repository,
            String reference,
            String result
        ) {
            auditEvents.add(
                new AuditEvent(
                    Instant.now(),
                    user.username(),
                    operation,
                    repository,
                    reference,
                    result
                )
            );
        }

        ImageManifest push(
            String token,
            String repositoryName,
            String tagName,
            byte[] content,
            String architecture,
            String os,
            boolean signed,
            int vulnerabilities,
            boolean immutable
        ) {
            RegistryUser user = authenticate(token);

            accessControl.verify(user, Operation.PUSH);

            Repository repository = getRepository(repositoryName);

            if (!TAG_PATTERN.matcher(tagName).matches()) {
                throw new IllegalArgumentException("Invalid tag.");
            }

            imagePolicy.validate(
                content,
                signed,
                vulnerabilities,
                architecture,
                os
            );

            String digest = calculateDigest(content);

            ImageTag existingTag = repository.tags.get(tagName);

            if (existingTag != null &&
                existingTag.immutable() &&
                !existingTag.digest().equals(digest)) {
                throw new ImmutableTagException(
                    "Cannot overwrite immutable tag."
                );
            }

            ImageManifest manifest =
                repository.manifests.computeIfAbsent(
                    digest,
                    ignored -> new ImageManifest(
                        repositoryName,
                        digest,
                        content,
                        "application/vnd.oci.image.manifest.v1+json",
                        architecture,
                        os,
                        content.length,
                        signed,
                        vulnerabilities,
                        Instant.now(),
                        ImageStatus.AVAILABLE
                    )
                );

            if (manifest.status() != ImageStatus.AVAILABLE) {
                throw new PolicyException(
                    "Manifest is not available."
                );
            }

            boolean finalImmutable =
                immutable ||
                (existingTag != null && existingTag.immutable());

            repository.tags.put(
                tagName,
                new ImageTag(
                    tagName,
                    digest,
                    finalImmutable,
                    Instant.now()
                )
            );

            audit(
                user,
                Operation.PUSH,
                repositoryName,
                tagName,
                "SUCCESS"
            );

            return manifest;
        }

        ImageManifest pull(
            String token,
            String repositoryName,
            String reference
        ) {
            RegistryUser user = authenticate(token);

            accessControl.verify(user, Operation.PULL);

            Repository repository = getRepository(repositoryName);

            String digest = reference;

            if (!reference.startsWith("sha256:")) {
                ImageTag tag = repository.tags.get(reference);

                if (tag == null) {
                    throw new RegistryException("Tag not found.");
                }

                digest = tag.digest();
            }

            ImageManifest manifest =
                repository.manifests.get(digest);

            if (manifest == null ||
                manifest.status() != ImageStatus.AVAILABLE) {
                throw new RegistryException(
                    "Image is unavailable."
                );
            }

            if (!calculateDigest(manifest.content()).equals(digest)) {
                throw new RegistryException(
                    "Image integrity verification failed."
                );
            }

            audit(
                user,
                Operation.PULL,
                repositoryName,
                reference,
                "SUCCESS"
            );

            return manifest;
        }

        void deleteTag(
            String token,
            String repositoryName,
            String tagName
        ) {
            RegistryUser user = authenticate(token);

            accessControl.verify(user, Operation.DELETE);

            Repository repository = getRepository(repositoryName);

            ImageTag tag = repository.tags.get(tagName);

            if (tag == null) {
                throw new RegistryException("Tag does not exist.");
            }

            if (tag.immutable()) {
                throw new ImmutableTagException(
                    "Immutable tag cannot be deleted."
                );
            }

            repository.tags.remove(tagName);

            audit(
                user,
                Operation.DELETE,
                repositoryName,
                tagName,
                "SUCCESS"
            );
        }

        List<DistributionResult> distribute(
            String token,
            String repositoryName,
            String reference,
            List<DistributionTarget> targets
        ) {
            ImageManifest manifest =
                pull(token, repositoryName, reference);

            if (targets == null || targets.isEmpty()) {
                throw new IllegalArgumentException(
                    "Distribution targets are required."
                );
            }

            List<DistributionResult> results = new ArrayList<>();

            for (DistributionTarget target : targets) {
                DistributionStatus status = target.available()
                    ? DistributionStatus.DELIVERED
                    : DistributionStatus.FAILED;

                results.add(
                    new DistributionResult(
                        target.name(),
                        status,
                        manifest.digest()
                    )
                );
            }

            return List.copyOf(results);
        }

        int garbageCollect(String token) {
            RegistryUser user = authenticate(token);

            accessControl.verify(user, Operation.MANAGE);

            int removed = 0;

            for (Repository repository : repositories.values()) {
                Set<String> referenced = new HashSet<>();

                for (ImageTag tag : repository.tags.values()) {
                    referenced.add(tag.digest());
                }

                List<String> unreferenced =
                    repository.manifests.keySet()
                        .stream()
                        .filter(digest -> !referenced.contains(digest))
                        .toList();

                for (String digest : unreferenced) {
                    repository.manifests.remove(digest);
                    removed++;
                }
            }

            audit(
                user,
                Operation.MANAGE,
                "*",
                "GARBAGE_COLLECTION",
                "SUCCESS"
            );

            return removed;
        }

        void printRepository(String repositoryName) {
            Repository repository = getRepository(repositoryName);

            System.out.println("\nRepository: " + repository.name());

            repository.tags()
                .values()
                .stream()
                .sorted((a, b) -> a.name().compareTo(b.name()))
                .forEach(tag -> System.out.println(
                    tag.name() +
                    " -> " + tag.digest() +
                    " | immutable=" + tag.immutable()
                ));
        }

        void printAudit() {
            System.out.println("\nAudit events:");

            auditEvents.forEach(System.out::println);
        }
    }

    public static void main(String[] args) {

        RegistryPolicy policy = new RegistryPolicy(
            5_000_000,
            1,
            true,
            Set.of("amd64", "arm64")
        );

        ContainerRegistryService registry =
            new ContainerRegistryService(
                "registry.enterprise.internal",
                policy
            );

        registry.registerUser(
            new RegistryUser(
                "admin",
                "admin-token",
                Role.ADMIN,
                true
            )
        );

        registry.registerUser(
            new RegistryUser(
                "build-service",
                "publisher-token",
                Role.PUBLISHER,
                true
            )
        );

        registry.registerUser(
            new RegistryUser(
                "deployment-service",
                "consumer-token",
                Role.CONSUMER,
                true
            )
        );

        registry.createRepository(
            "admin-token",
            "production/customer-service",
            true
        );

        byte[] imageV1 =
            "customer-service-container-v1"
                .getBytes(StandardCharsets.UTF_8);

        ImageManifest published = registry.push(
            "publisher-token",
            "production/customer-service",
            "1.0.0",
            imageV1,
            "amd64",
            "linux",
            true,
            0,
            true
        );

        registry.push(
            "publisher-token",
            "production/customer-service",
            "latest",
            imageV1,
            "amd64",
            "linux",
            true,
            0,
            false
        );

        ImageManifest downloaded = registry.pull(
            "consumer-token",
            "production/customer-service",
            "latest"
        );

        System.out.println("Registry: registry.enterprise.internal");
        System.out.println("Published digest: " + published.digest());
        System.out.println("Downloaded digest: " + downloaded.digest());

        System.out.println(
            "Integrity verified: " +
            published.digest().equals(downloaded.digest())
        );

        List<DistributionTarget> targets = List.of(
            new DistributionTarget("staging-cluster", true),
            new DistributionTarget("production-cluster", true),
            new DistributionTarget("regional-cluster", false)
        );

        System.out.println("\nDistribution results:");

        registry.distribute(
            "consumer-token",
            "production/customer-service",
            "1.0.0",
            targets
        ).forEach(System.out::println);

        try {
            registry.push(
                "publisher-token",
                "production/customer-service",
                "1.0.0",
                "different-image".getBytes(StandardCharsets.UTF_8),
                "amd64",
                "linux",
                true,
                0,
                true
            );
        } catch (ImmutableTagException exception) {
            System.out.println(
                "\nImmutable release protection: " +
                exception.getMessage()
            );
        }

        try {
            registry.push(
                "publisher-token",
                "production/customer-service",
                "2.0.0",
                "unsigned-image".getBytes(StandardCharsets.UTF_8),
                "amd64",
                "linux",
                false,
                0,
                false
            );
        } catch (PolicyException exception) {
            System.out.println(
                "Security policy rejection: " +
                exception.getMessage()
            );
        }

        registry.printRepository("production/customer-service");

        System.out.println(
            "\nGarbage-collected manifests: " +
            registry.garbageCollect("admin-token")
        );

        registry.printAudit();
    }
}
