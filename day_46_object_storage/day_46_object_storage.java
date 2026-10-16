import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

public class ObjectStorageGovernance {

    enum StorageClass {
        STANDARD,
        INFREQUENT_ACCESS,
        ARCHIVE
    }

    enum VersioningState {
        ENABLED,
        SUSPENDED
    }

    enum ObjectState {
        ACTIVE,
        DELETE_MARKER
    }

    record LifecycleRule(
        String name,
        String prefix,
        Duration transitionAfter,
        StorageClass transitionTarget,
        Optional<Duration> expirationAfter
    ) {
        LifecycleRule {
            Objects.requireNonNull(name);
            Objects.requireNonNull(prefix);
            Objects.requireNonNull(transitionAfter);
            Objects.requireNonNull(transitionTarget);
            Objects.requireNonNull(expirationAfter);

            if (transitionAfter.isNegative()) {
                throw new IllegalArgumentException(
                    "Transition duration cannot be negative."
                );
            }
        }

        boolean appliesTo(String objectKey) {
            return objectKey.startsWith(prefix);
        }
    }

    static final class ObjectVersion {
        private final String versionId;
        private final long size;
        private final String checksum;
        private final String contentType;
        private final Instant createdAt;
        private final Map<String, String> metadata;
        private StorageClass storageClass;
        private final ObjectState state;

        ObjectVersion(
            String versionId,
            long size,
            String checksum,
            String contentType,
            Instant createdAt,
            Map<String, String> metadata,
            StorageClass storageClass,
            ObjectState state
        ) {
            this.versionId = Objects.requireNonNull(versionId);
            this.size = size;
            this.checksum = Objects.requireNonNull(checksum);
            this.contentType = Objects.requireNonNull(contentType);
            this.createdAt = Objects.requireNonNull(createdAt);
            this.metadata = Map.copyOf(metadata);
            this.storageClass = Objects.requireNonNull(storageClass);
            this.state = Objects.requireNonNull(state);
        }

        String versionId() {
            return versionId;
        }

        long size() {
            return size;
        }

        StorageClass storageClass() {
            return storageClass;
        }

        void transitionTo(StorageClass target) {
            storageClass = target;
        }

        ObjectState state() {
            return state;
        }

        Instant createdAt() {
            return createdAt;
        }

        String contentType() {
            return contentType;
        }

        String checksum() {
            return checksum;
        }

        Map<String, String> metadata() {
            return metadata;
        }
    }

    static final class StoredObject {
        private final String key;
        private final List<ObjectVersion> versions = new ArrayList<>();

        StoredObject(String key) {
            this.key = Objects.requireNonNull(key);
        }

        String key() {
            return key;
        }

        List<ObjectVersion> versions() {
            return Collections.unmodifiableList(versions);
        }

        ObjectVersion currentVersion() {
            if (versions.isEmpty()) {
                throw new StorageException("No versions exist for " + key);
            }
            return versions.get(versions.size() - 1);
        }

        void append(ObjectVersion version) {
            versions.add(version);
        }

        void removeVersion(String versionId) {
            boolean removed = versions.removeIf(
                version -> version.versionId().equals(versionId)
            );

            if (!removed) {
                throw new StorageException(
                    "Version does not exist: " + versionId
                );
            }
        }
    }

    static final class Bucket {
        private final String name;
        private final String region;
        private VersioningState versioningState;
        private final Map<String, StoredObject> objects = new HashMap<>();
        private final List<LifecycleRule> lifecycleRules = new ArrayList<>();

        Bucket(
            String name,
            String region,
            VersioningState versioningState
        ) {
            if (name == null || name.length() < 3) {
                throw new IllegalArgumentException("Invalid bucket name.");
            }

            this.name = name;
            this.region = Objects.requireNonNull(region);
            this.versioningState = Objects.requireNonNull(versioningState);
        }

        String name() {
            return name;
        }

        String region() {
            return region;
        }

        VersioningState versioningState() {
            return versioningState;
        }

        void addLifecycleRule(LifecycleRule rule) {
            lifecycleRules.add(Objects.requireNonNull(rule));
        }

        void setVersioningState(VersioningState state) {
            versioningState = Objects.requireNonNull(state);
        }

        void putObject(
            String key,
            long size,
            String checksum,
            String contentType,
            Map<String, String> metadata,
            Instant createdAt
        ) {
            validateKey(key);

            if (versioningState == VersioningState.SUSPENDED) {
                objects.remove(key);
            }

            StoredObject object =
                objects.computeIfAbsent(key, StoredObject::new);

            String versionId =
                Integer.toHexString(
                    Objects.hash(
                        key,
                        size,
                        checksum,
                        createdAt
                    )
                );

            object.append(
                new ObjectVersion(
                    versionId,
                    size,
                    checksum,
                    contentType,
                    createdAt,
                    metadata,
                    StorageClass.STANDARD,
                    ObjectState.ACTIVE
                )
            );
        }

        void deleteObject(String key, Instant timestamp) {
            StoredObject object = objects.get(key);

            if (object == null) {
                throw new StorageException(
                    "Object does not exist: " + key
                );
            }

            if (versioningState == VersioningState.ENABLED) {
                String markerId =
                    Integer.toHexString(
                        Objects.hash(key, "DELETE", timestamp)
                    );

                object.append(
                    new ObjectVersion(
                        markerId,
                        0,
                        "EMPTY",
                        "application/x-delete-marker",
                        timestamp,
                        Map.of(),
                        StorageClass.STANDARD,
                        ObjectState.DELETE_MARKER
                    )
                );
            } else {
                objects.remove(key);
            }
        }

        ObjectVersion current(String key) {
            StoredObject object = objects.get(key);

            if (object == null) {
                throw new StorageException("Object not found: " + key);
            }

            ObjectVersion current = object.currentVersion();

            if (current.state() == ObjectState.DELETE_MARKER) {
                throw new StorageException(
                    "Object is currently hidden by a delete marker."
                );
            }

            return current;
        }

        void deleteSpecificVersion(String key, String versionId) {
            StoredObject object = objects.get(key);

            if (object == null) {
                throw new StorageException("Object not found: " + key);
            }

            object.removeVersion(versionId);

            if (object.versions().isEmpty()) {
                objects.remove(key);
            }
        }

        List<String> applyLifecycle(Instant evaluationTime) {
            List<String> actions = new ArrayList<>();

            for (StoredObject object : objects.values()) {
                for (ObjectVersion version : object.versions()) {
                    if (version.state() == ObjectState.DELETE_MARKER) {
                        continue;
                    }

                    Duration age =
                        Duration.between(
                            version.createdAt(),
                            evaluationTime
                        );

                    for (LifecycleRule rule : lifecycleRules) {
                        if (!rule.appliesTo(object.key())) {
                            continue;
                        }

                        if (
                            age.compareTo(rule.transitionAfter()) >= 0 &&
                            version.storageClass() != rule.transitionTarget()
                        ) {
                            version.transitionTo(rule.transitionTarget());

                            actions.add(
                                object.key()
                                    + "@"
                                    + version.versionId()
                                    + " -> "
                                    + version.storageClass()
                            );
                        }
                    }
                }
            }

            return actions;
        }

        Map<String, StoredObject> objects() {
            return Collections.unmodifiableMap(objects);
        }

        private static void validateKey(String key) {
            if (key == null || key.isBlank() || key.startsWith("/")) {
                throw new IllegalArgumentException(
                    "Object key must be a non-empty relative key."
                );
            }
        }
    }

    static final class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    interface LifecycleExecutor {
        List<String> evaluate(Bucket bucket, Instant time);
    }

    static final class DefaultLifecycleExecutor
        implements LifecycleExecutor {

        @Override
        public List<String> evaluate(Bucket bucket, Instant time) {
            return bucket.applyLifecycle(time);
        }
    }

    static final class StorageService {
        private final Map<String, Bucket> buckets = new HashMap<>();

        Bucket createBucket(String name, String region) {
            if (buckets.containsKey(name)) {
                throw new StorageException(
                    "Bucket already exists: " + name
                );
            }

            Bucket bucket =
                new Bucket(
                    name,
                    region,
                    VersioningState.ENABLED
                );

            buckets.put(name, bucket);
            return bucket;
        }

        Bucket getBucket(String name) {
            Bucket bucket = buckets.get(name);

            if (bucket == null) {
                throw new StorageException(
                    "Bucket not found: " + name
                );
            }

            return bucket;
        }

        void deleteBucket(String name) {
            Bucket bucket = getBucket(name);

            if (!bucket.objects().isEmpty()) {
                throw new StorageException(
                    "Bucket deletion requires an empty bucket."
                );
            }

            buckets.remove(name);
        }
    }

    static void printObjectInventory(Bucket bucket) {
        System.out.println(
            "Bucket: " + bucket.name()
                + " | region=" + bucket.region()
                + " | versioning=" + bucket.versioningState()
        );

        for (StoredObject object : bucket.objects().values()) {
            System.out.println("Object: " + object.key());

            for (ObjectVersion version : object.versions()) {
                System.out.println(
                    "  version=" + version.versionId()
                        + " size=" + version.size()
                        + " class=" + version.storageClass()
                        + " state=" + version.state()
                        + " type=" + version.contentType()
                        + " checksum=" + version.checksum()
                        + " metadata=" + version.metadata()
                );
            }
        }
    }

    public static void main(String[] args) {
        StorageService service = new StorageService();
        Bucket bucket =
            service.createBucket(
                "enterprise-object-store",
                "ap-south-1"
            );

        bucket.addLifecycleRule(
            new LifecycleRule(
                "archive-audit-objects",
                "audit/",
                Duration.ofDays(30),
                StorageClass.INFREQUENT_ACCESS,
                Optional.of(Duration.ofDays(365))
            )
        );

        bucket.addLifecycleRule(
            new LifecycleRule(
                "archive-analytics",
                "analytics/",
                Duration.ofDays(90),
                StorageClass.ARCHIVE,
                Optional.empty()
            )
        );

        Instant creationTime =
            Instant.parse("2026-01-01T00:00:00Z");

        bucket.putObject(
            "analytics/events.parquet",
            2_500_000,
            "sha256:analytics-001",
            "application/vnd.apache.parquet",
            Map.of(
                "owner", "data-platform",
                "classification", "internal"
            ),
            creationTime
        );

        bucket.putObject(
            "analytics/events.parquet",
            2_700_000,
            "sha256:analytics-002",
            "application/vnd.apache.parquet",
            Map.of(
                "owner", "data-platform",
                "classification", "internal"
            ),
            creationTime.plus(Duration.ofDays(5))
        );

        bucket.putObject(
            "audit/access.json",
            12_400,
            "sha256:audit-001",
            "application/json",
            Map.of(
                "retention", "regulated",
                "service", "identity"
            ),
            creationTime
        );

        System.out.println("=== Enterprise object inventory ===");
        printObjectInventory(bucket);

        System.out.println("\n=== Current object retrieval ===");
        ObjectVersion current =
            bucket.current("analytics/events.parquet");

        System.out.println(
            "Current size: " + current.size()
                + ", class: " + current.storageClass()
        );

        System.out.println("\n=== Lifecycle policy evaluation ===");

        LifecycleExecutor executor =
            new DefaultLifecycleExecutor();

        List<String> actions =
            executor.evaluate(
                bucket,
                creationTime.plus(Duration.ofDays(100))
            );

        actions.forEach(action -> System.out.println(
            "Lifecycle transition: " + action
        ));

        System.out.println("\n=== Delete-marker semantics ===");

        bucket.deleteObject(
            "audit/access.json",
            creationTime.plus(Duration.ofDays(100))
        );

        try {
            bucket.current("audit/access.json");
        } catch (StorageException exception) {
            System.out.println(
                "Expected current-object failure: "
                    + exception.getMessage()
            );
        }

        System.out.println("\n=== Explicit version deletion ===");

        StoredObject analytics =
            bucket.objects().get("analytics/events.parquet");

        String oldVersionId =
            analytics.versions().get(0).versionId();

        bucket.deleteSpecificVersion(
            "analytics/events.parquet",
            oldVersionId
        );

        System.out.println(
            "Removed historical version: " + oldVersionId
        );

        System.out.println("\n=== Non-empty bucket deletion ===");

        try {
            service.deleteBucket(bucket.name());
        } catch (StorageException exception) {
            System.out.println(
                "Expected bucket deletion failure: "
                    + exception.getMessage()
            );
        }

        System.out.println("\n=== Final inventory ===");
        printObjectInventory(bucket);
    }
}
