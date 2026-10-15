import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

public class CloudStorageGovernance {

    enum StorageClass {
        STANDARD,
        INFREQUENT_ACCESS,
        ARCHIVE
    }

    enum ReplicaState {
        HEALTHY,
        FAILED,
        REPAIRING
    }

    enum AvailabilityState {
        AVAILABLE,
        DEGRADED,
        UNAVAILABLE
    }

    record Replica(String region, ReplicaState state) {
        Replica {
            Objects.requireNonNull(region, "region");
            Objects.requireNonNull(state, "state");
        }
    }

    record StorageObject(
        String key,
        long sizeBytes,
        StorageClass storageClass,
        Instant createdAt
    ) {
        StorageObject {
            if (key == null || key.isBlank()) {
                throw new IllegalArgumentException(
                    "Object key cannot be blank."
                );
            }

            if (sizeBytes <= 0) {
                throw new IllegalArgumentException(
                    "Object size must be positive."
                );
            }

            Objects.requireNonNull(storageClass);
            Objects.requireNonNull(createdAt);
        }
    }

    record ProtectionPolicy(
        int minimumReplicas,
        boolean requireMultiRegion,
        boolean requireEncryption
    ) {
        ProtectionPolicy {
            if (minimumReplicas < 1) {
                throw new IllegalArgumentException(
                    "Minimum replica count must be positive."
                );
            }
        }
    }

    record StoragePolicyResult(
        boolean compliant,
        List<String> violations
    ) {}

    static final class StoredObject {
        private final StorageObject object;
        private final List<Replica> replicas;
        private final boolean encrypted;

        StoredObject(
            StorageObject object,
            List<Replica> replicas,
            boolean encrypted
        ) {
            this.object = object;
            this.replicas = new ArrayList<>(replicas);
            this.encrypted = encrypted;
        }

        StorageObject object() {
            return object;
        }

        List<Replica> replicas() {
            return List.copyOf(replicas);
        }

        boolean encrypted() {
            return encrypted;
        }

        void failRegion(String region) {
            for (int i = 0; i < replicas.size(); i++) {
                Replica replica = replicas.get(i);

                if (replica.region().equals(region)) {
                    replicas.set(
                        i,
                        new Replica(
                            replica.region(),
                            ReplicaState.FAILED
                        )
                    );
                }
            }
        }

        void recoverRegion(String region) {
            for (int i = 0; i < replicas.size(); i++) {
                Replica replica = replicas.get(i);

                if (replica.region().equals(region)) {
                    replicas.set(
                        i,
                        new Replica(
                            replica.region(),
                            ReplicaState.HEALTHY
                        )
                    );
                }
            }
        }

        long healthyReplicaCount() {
            return replicas.stream()
                .filter(replica ->
                    replica.state() == ReplicaState.HEALTHY
                )
                .count();
        }

        AvailabilityState availability(int configuredReplicaCount) {
            long healthy = healthyReplicaCount();

            if (healthy == 0) {
                return AvailabilityState.UNAVAILABLE;
            }

            if (healthy < configuredReplicaCount) {
                return AvailabilityState.DEGRADED;
            }

            return AvailabilityState.AVAILABLE;
        }
    }

    static final class StorageService {
        private final String serviceName;
        private final Set<String> regions;
        private final int replicationFactor;
        private final Map<String, StoredObject> objects =
            new ConcurrentHashMap<>();

        StorageService(
            String serviceName,
            Set<String> regions,
            int replicationFactor
        ) {
            if (serviceName == null || serviceName.isBlank()) {
                throw new IllegalArgumentException(
                    "Service name is required."
                );
            }

            if (regions == null || regions.isEmpty()) {
                throw new IllegalArgumentException(
                    "At least one region is required."
                );
            }

            if (
                replicationFactor < 1 ||
                replicationFactor > regions.size()
            ) {
                throw new IllegalArgumentException(
                    "Invalid replication factor."
                );
            }

            this.serviceName = serviceName;
            this.regions = Set.copyOf(regions);
            this.replicationFactor = replicationFactor;
        }

        void store(
            StorageObject object,
            boolean encrypted
        ) {
            List<String> selectedRegions = regions.stream()
                .limit(replicationFactor)
                .toList();

            List<Replica> replicas = selectedRegions.stream()
                .map(region ->
                    new Replica(region, ReplicaState.HEALTHY)
                )
                .collect(Collectors.toCollection(ArrayList::new));

            objects.put(
                object.key(),
                new StoredObject(
                    object,
                    replicas,
                    encrypted
                )
            );
        }

        StorageObject retrieve(String key) {
            StoredObject stored = objects.get(key);

            if (stored == null) {
                throw new IllegalArgumentException(
                    "Object does not exist: " + key
                );
            }

            if (
                stored.availability(replicationFactor) ==
                AvailabilityState.UNAVAILABLE
            ) {
                throw new IllegalStateException(
                    "Object is unavailable: " + key
                );
            }

            return stored.object();
        }

        void failRegion(String region) {
            requireKnownRegion(region);

            objects.values().forEach(
                object -> object.failRegion(region)
            );
        }

        void recoverRegion(String region) {
            requireKnownRegion(region);

            objects.values().forEach(
                object -> object.recoverRegion(region)
            );
        }

        StoragePolicyResult evaluate(
            String key,
            ProtectionPolicy policy
        ) {
            StoredObject stored = objects.get(key);

            if (stored == null) {
                return new StoragePolicyResult(
                    false,
                    List.of("Object does not exist.")
                );
            }

            List<String> violations = new ArrayList<>();

            if (replicationFactor < policy.minimumReplicas()) {
                violations.add(
                    "Replication factor is below policy minimum."
                );
            }

            if (
                policy.requireMultiRegion() &&
                regions.size() < 2
            ) {
                violations.add(
                    "Policy requires more than one region."
                );
            }

            if (
                policy.requireEncryption() &&
                !stored.encrypted()
            ) {
                violations.add(
                    "Object encryption requirement is not satisfied."
                );
            }

            return new StoragePolicyResult(
                violations.isEmpty(),
                List.copyOf(violations)
            );
        }

        AvailabilityState availability(String key) {
            StoredObject stored = objects.get(key);

            if (stored == null) {
                throw new IllegalArgumentException(
                    "Object does not exist: " + key
                );
            }

            return stored.availability(replicationFactor);
        }

        long healthyReplicaCount(String key) {
            StoredObject stored = objects.get(key);

            if (stored == null) {
                throw new IllegalArgumentException(
                    "Object does not exist: " + key
                );
            }

            return stored.healthyReplicaCount();
        }

        private void requireKnownRegion(String region) {
            if (!regions.contains(region)) {
                throw new IllegalArgumentException(
                    "Unknown region: " + region
                );
            }
        }

        String serviceName() {
            return serviceName;
        }

        int replicationFactor() {
            return replicationFactor;
        }
    }

    static double independentAvailability(
        double replicaAvailability,
        int replicas
    ) {
        if (
            replicaAvailability < 0 ||
            replicaAvailability > 1 ||
            replicas < 1
        ) {
            throw new IllegalArgumentException(
                "Invalid availability parameters."
            );
        }

        return 1 - Math.pow(
            1 - replicaAvailability,
            replicas
        );
    }

    static double independentLossProbability(
        double replicaFailureProbability,
        int replicas
    ) {
        if (
            replicaFailureProbability < 0 ||
            replicaFailureProbability > 1 ||
            replicas < 1
        ) {
            throw new IllegalArgumentException(
                "Invalid durability parameters."
            );
        }

        return Math.pow(
            replicaFailureProbability,
            replicas
        );
    }

    public static void main(String[] args) {
        StorageService service = new StorageService(
            "enterprise-data-store",
            Set.of(
                "Mumbai",
                "Singapore",
                "Frankfurt"
            ),
            3
        );

        StorageObject object = new StorageObject(
            "finance/2026/market-snapshot.parquet",
            250L * 1024L * 1024L,
            StorageClass.STANDARD,
            Instant.now()
        );

        service.store(object, true);

        ProtectionPolicy policy = new ProtectionPolicy(
            3,
            true,
            true
        );

        System.out.println(
            "Service: " + service.serviceName()
        );

        System.out.println(
            "Initial state: " +
            service.availability(object.key())
        );

        System.out.println(
            "Policy: " +
            service.evaluate(object.key(), policy)
        );

        service.failRegion("Mumbai");

        System.out.println(
            "After Mumbai failure: " +
            service.availability(object.key())
        );

        System.out.println(
            "Healthy replicas: " +
            service.healthyReplicaCount(object.key())
        );

        service.failRegion("Singapore");

        System.out.println(
            "After Singapore failure: " +
            service.availability(object.key())
        );

        service.recoverRegion("Mumbai");

        System.out.println(
            "After Mumbai recovery: " +
            service.availability(object.key())
        );

        StorageObject retrieved =
            service.retrieve(object.key());

        System.out.println(
            "Retrieved object: " + retrieved.key()
        );

        double availability = independentAvailability(
            0.999,
            3
        );

        double lossProbability =
            independentLossProbability(
                0.001,
                3
            );

        System.out.printf(
            "Modeled independent availability: %.8f%n",
            availability
        );

        System.out.printf(
            "Modeled simultaneous replica loss: %.8e%n",
            lossProbability
        );

        /*
         * EnumSet is useful when policies need combinations of explicit
         * protection capabilities. It is shown here as a domain-level
         * representation rather than as a generic collections exercise.
         */
        EnumSet<StorageClass> managedClasses =
            EnumSet.of(
                StorageClass.STANDARD,
                StorageClass.INFREQUENT_ACCESS,
                StorageClass.ARCHIVE
            );

        System.out.println(
            "Managed storage classes: " + managedClasses
        );
    }
}
