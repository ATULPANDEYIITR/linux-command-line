import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/*
 * Enterprise Storage Performance Policy Engine
 *
 * Java 17 program modeling storage performance for enterprise workloads.
 * The domain model separates workload requirements, storage tiers, cache
 * behavior, and the policy used to select an economically viable tier.
 */

public class StoragePerformanceEnterprise {

    enum StorageTier {
        NVME,
        SSD,
        HDD,
        ARCHIVE
    }

    enum AccessPattern {
        RANDOM,
        SEQUENTIAL
    }

    record TierProfile(
            StorageTier tier,
            double maximumIops,
            double throughputMiBPerSecond,
            double baseLatencyMs,
            double monthlyCostPerGiB) {

        TierProfile {
            Objects.requireNonNull(tier);

            if (maximumIops <= 0
                    || throughputMiBPerSecond <= 0
                    || baseLatencyMs <= 0
                    || monthlyCostPerGiB < 0) {
                throw new IllegalArgumentException(
                        "Tier performance values must be valid");
            }
        }
    }

    record Workload(
            String name,
            long requestSizeBytes,
            double requestsPerSecond,
            double latencyTargetMs,
            double capacityGiB,
            AccessPattern accessPattern) {

        Workload {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                        "Workload name is required");
            }

            if (requestSizeBytes <= 0
                    || requestsPerSecond <= 0
                    || latencyTargetMs <= 0
                    || capacityGiB <= 0) {
                throw new IllegalArgumentException(
                        "Workload performance requirements must be positive");
            }

            Objects.requireNonNull(accessPattern);
        }
    }

    record TierEvaluation(
            StorageTier tier,
            double sustainableIops,
            double estimatedLatencyMs,
            double monthlyCost,
            boolean acceptable,
            List<String> reasons) {

        TierEvaluation {
            reasons = List.copyOf(reasons);
        }
    }

    static final class StorageCatalog {
        private final Map<StorageTier, TierProfile> profiles =
                new EnumMap<>(StorageTier.class);

        StorageCatalog() {
            profiles.put(
                    StorageTier.NVME,
                    new TierProfile(
                            StorageTier.NVME,
                            900_000,
                            7_000,
                            0.08,
                            0.12));

            profiles.put(
                    StorageTier.SSD,
                    new TierProfile(
                            StorageTier.SSD,
                            120_000,
                            1_200,
                            0.45,
                            0.07));

            profiles.put(
                    StorageTier.HDD,
                    new TierProfile(
                            StorageTier.HDD,
                            300,
                            250,
                            8.0,
                            0.025));

            profiles.put(
                    StorageTier.ARCHIVE,
                    new TierProfile(
                            StorageTier.ARCHIVE,
                            50,
                            100,
                            80.0,
                            0.008));
        }

        TierProfile profile(StorageTier tier) {
            TierProfile profile = profiles.get(tier);

            if (profile == null) {
                throw new IllegalArgumentException(
                        "No profile exists for " + tier);
            }

            return profile;
        }

        List<TierProfile> all() {
            return List.copyOf(profiles.values());
        }
    }

    static final class PerformancePolicy {

        private final StorageCatalog catalog;

        PerformancePolicy(StorageCatalog catalog) {
            this.catalog = Objects.requireNonNull(catalog);
        }

        TierEvaluation evaluate(
                Workload workload,
                StorageTier tier) {

            TierProfile profile = catalog.profile(tier);

            double bytesPerMiB = 1024.0 * 1024.0;

            double bandwidthLimitedIops =
                    profile.throughputMiBPerSecond()
                            * bytesPerMiB
                            / workload.requestSizeBytes();

            double sustainableIops = Math.min(
                    profile.maximumIops(),
                    bandwidthLimitedIops);

            double estimatedLatency =
                    profile.baseLatencyMs()
                            + 1000.0 / sustainableIops;

            boolean iopsSatisfied =
                    workload.requestsPerSecond() <= sustainableIops;

            boolean latencySatisfied =
                    estimatedLatency <= workload.latencyTargetMs();

            List<String> reasons = new ArrayList<>();

            if (iopsSatisfied) {
                reasons.add("Required IOPS fit within the tier limit.");
            } else {
                reasons.add("Required IOPS exceed the tier limit.");
            }

            if (latencySatisfied) {
                reasons.add("Estimated latency satisfies the target.");
            } else {
                reasons.add("Estimated latency violates the target.");
            }

            if (workload.accessPattern() == AccessPattern.RANDOM) {
                reasons.add(
                        "Random access makes IOPS and latency primary constraints.");
            } else {
                reasons.add(
                        "Sequential access can exploit sustained bandwidth.");
            }

            return new TierEvaluation(
                    tier,
                    sustainableIops,
                    estimatedLatency,
                    workload.capacityGiB()
                            * profile.monthlyCostPerGiB(),
                    iopsSatisfied && latencySatisfied,
                    reasons);
        }

        Optional<TierEvaluation> select(
                Workload workload) {

            return catalog.all()
                    .stream()
                    .map(profile -> evaluate(workload, profile.tier()))
                    .filter(TierEvaluation::acceptable)
                    .min(Comparator.comparingDouble(
                            TierEvaluation::monthlyCost));
        }
    }

    static final class CachePolicy {
        private final int maximumEntries;
        private final Map<String, byte[]> entries =
                new java.util.LinkedHashMap<>(16, 0.75f, true);

        CachePolicy(int maximumEntries) {
            if (maximumEntries <= 0) {
                throw new IllegalArgumentException(
                        "Cache size must be positive");
            }

            this.maximumEntries = maximumEntries;
        }

        synchronized boolean contains(String key) {
            return entries.containsKey(key);
        }

        synchronized void put(String key, byte[] value) {
            Objects.requireNonNull(key);
            Objects.requireNonNull(value);

            entries.put(key, value);

            while (entries.size() > maximumEntries) {
                String oldestKey = entries.keySet()
                        .iterator()
                        .next();
                entries.remove(oldestKey);
            }
        }

        synchronized int size() {
            return entries.size();
        }
    }

    static final class StorageService {
        private final PerformancePolicy policy;
        private final CachePolicy cache;

        StorageService(
                PerformancePolicy policy,
                CachePolicy cache) {
            this.policy = Objects.requireNonNull(policy);
            this.cache = Objects.requireNonNull(cache);
        }

        boolean canServe(Workload workload, StorageTier tier) {
            return policy.evaluate(workload, tier).acceptable();
        }

        boolean readFromCache(String objectId) {
            return cache.contains(objectId);
        }

        void cacheReadResult(
                String objectId,
                int sizeBytes) {

            if (sizeBytes <= 0) {
                throw new IllegalArgumentException(
                        "Cached object size must be positive");
            }

            cache.put(
                    objectId,
                    new byte[sizeBytes]);
        }

        int cacheEntries() {
            return cache.size();
        }
    }

    static void printEvaluation(
            Workload workload,
            TierEvaluation evaluation) {

        System.out.printf(
                "%n%s -> %s%n",
                workload.name(),
                evaluation.tier());

        System.out.printf(
                "Sustainable IOPS: %.0f%n",
                evaluation.sustainableIops());

        System.out.printf(
                "Estimated latency: %.3f ms%n",
                evaluation.estimatedLatencyMs());

        System.out.printf(
                "Estimated monthly capacity cost: $%.2f%n",
                evaluation.monthlyCost());

        System.out.println(
                "Acceptable: "
                        + evaluation.acceptable());

        for (String reason : evaluation.reasons()) {
            System.out.println("  " + reason);
        }
    }

    static void demonstrateEnterpriseWorkloads() {
        StorageCatalog catalog = new StorageCatalog();
        PerformancePolicy policy = new PerformancePolicy(catalog);

        StorageService service =
                new StorageService(
                        policy,
                        new CachePolicy(128));

        List<Workload> workloads = List.of(
                new Workload(
                        "Payment transaction database",
                        4 * 1024,
                        75_000,
                        2.0,
                        500,
                        AccessPattern.RANDOM),

                new Workload(
                        "Data warehouse scan",
                        1024 * 1024,
                        800,
                        25.0,
                        4000,
                        AccessPattern.SEQUENTIAL),

                new Workload(
                        "Nightly backup",
                        4 * 1024 * 1024,
                        50,
                        200.0,
                        10000,
                        AccessPattern.SEQUENTIAL),

                new Workload(
                        "Compliance archive",
                        1024 * 1024,
                        2,
                        500.0,
                        50000,
                        AccessPattern.SEQUENTIAL)
        );

        for (Workload workload : workloads) {
            System.out.println(
                    "\n=== " + workload.name() + " ===");

            for (StorageTier tier : StorageTier.values()) {
                printEvaluation(
                        workload,
                        policy.evaluate(workload, tier));
            }

            Optional<TierEvaluation> selected =
                    policy.select(workload);

            System.out.println(
                    selected
                            .map(evaluation ->
                                    "Cost-aware selected tier: "
                                            + evaluation.tier())
                            .orElse(
                                    "No tier satisfies all declared requirements"));
        }

        System.out.println("\n=== Cache State Model ===");

        service.cacheReadResult(
                "customer-42",
                4096);

        service.cacheReadResult(
                "customer-43",
                4096);

        System.out.println(
                "customer-42 cached: "
                        + service.readFromCache("customer-42"));

        System.out.println(
                "customer-99 cached: "
                        + service.readFromCache("customer-99"));

        System.out.println(
                "Cache entries: "
                        + service.cacheEntries());
    }

    static void demonstrateInvalidState() {
        System.out.println("\n=== Validation Failure ===");

        try {
            new Workload(
                    "Invalid workload",
                    0,
                    100,
                    2,
                    100,
                    AccessPattern.RANDOM);
        } catch (IllegalArgumentException exception) {
            System.out.println(
                    "Rejected invalid workload: "
                            + exception.getMessage());
        }
    }

    public static void main(String[] args) {
        demonstrateEnterpriseWorkloads();
        demonstrateInvalidState();

        System.out.println(
                "\nThe policy engine keeps workload requirements, " +
                "tier capabilities, cache state, and selection rules " +
                "as separate domain concerns.");
    }
}
