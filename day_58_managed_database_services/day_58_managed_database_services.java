import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Predicate;

public class ManagedDatabaseService {

    enum DatabaseState {
        AVAILABLE,
        MAINTENANCE,
        FAILING_OVER,
        DEGRADED,
        FAILED
    }

    enum ReplicaState {
        STREAMING,
        LAGGING,
        FAILED
    }

    enum BackupType {
        SNAPSHOT,
        FULL
    }

    record Backup(
        String id,
        BackupType type,
        long lsn,
        int sizeGb,
        Instant createdAt
    ) {}

    record StatusCheck(
        String name,
        boolean passed,
        String message
    ) {}

    record OperationalPolicy(
        boolean requireMultiAz,
        boolean requireBackup,
        boolean requireHealthyReplica,
        int maximumReplicaLagSeconds,
        int minimumStorageGb
    ) {}

    static final class Replica {
        private final String id;
        private final String region;
        private ReplicaState state;
        private int lagSeconds;
        private long replayedLsn;

        Replica(String region, long currentLsn) {
            this.id = UUID.randomUUID().toString();
            this.region = Objects.requireNonNull(region);
            this.state = ReplicaState.STREAMING;
            this.lagSeconds = 1;
            this.replayedLsn = currentLsn;
        }

        String id() {
            return id;
        }

        String region() {
            return region;
        }

        ReplicaState state() {
            return state;
        }

        int lagSeconds() {
            return lagSeconds;
        }

        void applyLag(int seconds, long primaryLsn, int maximumLag) {
            if (state == ReplicaState.FAILED) {
                throw new AvailabilityException(
                    "A failed replica cannot replay changes."
                );
            }

            lagSeconds = Math.max(0, lagSeconds + seconds);

            if (lagSeconds > maximumLag) {
                state = ReplicaState.LAGGING;
            } else {
                state = ReplicaState.STREAMING;
                replayedLsn = primaryLsn;
            }
        }
    }

    interface OperationalRule {
        boolean evaluate(ManagedDatabase database);

        String name();
    }

    static final class ManagedDatabase {
        private final String name;
        private final String engine;
        private String version;
        private String primaryRegion;
        private int storageGb;
        private int computeUnits;
        private final boolean multiAz;
        private DatabaseState state = DatabaseState.AVAILABLE;
        private long lsn = 0;

        private final Map<String, Replica> replicas = new HashMap<>();
        private final List<Backup> backups = new ArrayList<>();
        private final List<String> auditEvents = new ArrayList<>();

        ManagedDatabase(
            String name,
            String engine,
            String version,
            String primaryRegion,
            int storageGb,
            int computeUnits,
            boolean multiAz
        ) {
            this.name = validateText(name, "name");
            this.engine = validateText(engine, "engine");
            this.version = validateText(version, "version");
            this.primaryRegion = validateText(primaryRegion, "primaryRegion");

            if (storageGb < 20) {
                throw new ValidationException(
                    "Storage must be at least 20 GB."
                );
            }

            if (computeUnits < 1) {
                throw new ValidationException(
                    "Compute units must be positive."
                );
            }

            this.storageGb = storageGb;
            this.computeUnits = computeUnits;
            this.multiAz = multiAz;
        }

        private static String validateText(String value, String field) {
            if (value == null || value.isBlank()) {
                throw new ValidationException(field + " cannot be empty.");
            }
            return value;
        }

        private void requireAvailable() {
            if (state != DatabaseState.AVAILABLE &&
                state != DatabaseState.DEGRADED) {
                throw new AvailabilityException(
                    "Operation rejected because state is " + state
                );
            }
        }

        private void audit(String event) {
            auditEvents.add(Instant.now() + " " + event);
        }

        void write(long records) {
            requireAvailable();

            if (records <= 0) {
                throw new ValidationException(
                    "Records written must be positive."
                );
            }

            lsn += records;
            audit("WRITE records=" + records + " lsn=" + lsn);
        }

        Backup createBackup(BackupType type) {
            requireAvailable();

            Backup backup = new Backup(
                UUID.randomUUID().toString(),
                type,
                lsn,
                Math.max(1, (int) (storageGb * 0.65)),
                Instant.now()
            );

            backups.add(backup);
            audit("BACKUP id=" + backup.id());

            return backup;
        }

        void addReplica(String region) {
            requireAvailable();

            if (region == null || region.isBlank()) {
                throw new ValidationException(
                    "Replica region cannot be empty."
                );
            }

            if (region.equals(primaryRegion)) {
                throw new ValidationException(
                    "Replica must use another region."
                );
            }

            if (replicas.values().stream()
                .anyMatch(replica -> replica.region().equals(region))) {
                throw new ValidationException(
                    "Replica already exists in this region."
                );
            }

            Replica replica = new Replica(region, lsn);
            replicas.put(replica.id(), replica);
            audit("REPLICA_CREATE region=" + region);
        }

        void patch(String targetVersion, int maintenanceHour) {
            requireAvailable();

            if (targetVersion == null || targetVersion.isBlank()) {
                throw new ValidationException(
                    "Target version cannot be empty."
                );
            }

            if (maintenanceHour != 2) {
                throw new ValidationException(
                    "Patch is outside the maintenance window."
                );
            }

            state = DatabaseState.MAINTENANCE;

            try {
                version = targetVersion;
                audit("PATCH version=" + targetVersion);
            } finally {
                if (state != DatabaseState.FAILED) {
                    state = DatabaseState.AVAILABLE;
                }
            }
        }

        void scaleStorage(int newStorageGb) {
            requireAvailable();

            if (newStorageGb < storageGb) {
                throw new ValidationException(
                    "Storage reduction is not supported."
                );
            }

            audit("STORAGE_SCALE from=" + storageGb + " to=" + newStorageGb);
            storageGb = newStorageGb;
        }

        void scaleCompute(int newComputeUnits) {
            requireAvailable();

            if (newComputeUnits < 1) {
                throw new ValidationException(
                    "Compute units must be positive."
                );
            }

            audit(
                "COMPUTE_SCALE from=" + computeUnits +
                " to=" + newComputeUnits
            );

            computeUnits = newComputeUnits;
        }

        void failover() {
            if (!multiAz) {
                throw new AvailabilityException(
                    "Failover requires multi-AZ deployment."
                );
            }

            Optional<Replica> candidate = replicas.values()
                .stream()
                .filter(replica -> replica.state() == ReplicaState.STREAMING)
                .findFirst();

            state = DatabaseState.FAILING_OVER;

            if (candidate.isEmpty()) {
                state = DatabaseState.FAILED;
                audit("FAILOVER failed");
                throw new AvailabilityException(
                    "No healthy replica is available."
                );
            }

            primaryRegion = candidate.get().region();
            state = DatabaseState.AVAILABLE;
            audit("FAILOVER newRegion=" + primaryRegion);
        }

        List<StatusCheck> healthChecks(OperationalPolicy policy) {
            List<StatusCheck> checks = new ArrayList<>();

            checks.add(new StatusCheck(
                "storage",
                storageGb >= policy.minimumStorageGb(),
                "Configured storage=" + storageGb + " GB"
            ));

            checks.add(new StatusCheck(
                "compute",
                computeUnits >= 1,
                "Configured compute units=" + computeUnits
            ));

            boolean healthyReplica = replicas.values()
                .stream()
                .anyMatch(replica ->
                    replica.state() == ReplicaState.STREAMING &&
                    replica.lagSeconds() <= policy.maximumReplicaLagSeconds()
                );

            checks.add(new StatusCheck(
                "replication",
                !policy.requireHealthyReplica() || healthyReplica,
                healthyReplica
                    ? "At least one replica is healthy"
                    : "No replica satisfies the lag policy"
            ));

            checks.add(new StatusCheck(
                "backup",
                !policy.requireBackup() || !backups.isEmpty(),
                backups.isEmpty()
                    ? "No backup exists"
                    : "Backup exists"
            ));

            checks.add(new StatusCheck(
                "multi_az",
                !policy.requireMultiAz() || multiAz,
                multiAz
                    ? "Multi-AZ enabled"
                    : "Multi-AZ disabled"
            ));

            return checks;
        }

        boolean evaluatePolicy(OperationalPolicy policy) {
            List<OperationalRule> rules = List.of(
                new SimpleRule(
                    "service_available",
                    db -> db.state == DatabaseState.AVAILABLE
                ),
                new SimpleRule(
                    "storage_requirement",
                    db -> db.storageGb >= policy.minimumStorageGb()
                ),
                new SimpleRule(
                    "backup_requirement",
                    db -> !policy.requireBackup() || !db.backups.isEmpty()
                ),
                new SimpleRule(
                    "multi_az_requirement",
                    db -> !policy.requireMultiAz() || db.multiAz
                ),
                new SimpleRule(
                    "healthy_replica_requirement",
                    db -> !policy.requireHealthyReplica() ||
                        db.replicas.values().stream().anyMatch(
                            replica ->
                                replica.state() == ReplicaState.STREAMING &&
                                replica.lagSeconds() <=
                                    policy.maximumReplicaLagSeconds()
                        )
                )
            );

            return rules.stream().allMatch(rule -> rule.evaluate(this));
        }

        void printReport() {
            System.out.println("\n=== Enterprise Database Report ===");
            System.out.println("Name: " + name);
            System.out.println("Engine: " + engine + " " + version);
            System.out.println("Primary region: " + primaryRegion);
            System.out.println("State: " + state);
            System.out.println("Storage: " + storageGb + " GB");
            System.out.println("Compute: " + computeUnits);
            System.out.println("LSN: " + lsn);
            System.out.println("Backups: " + backups.size());
            System.out.println("Replicas: " + replicas.size());
            System.out.println("Audit events: " + auditEvents.size());
        }
    }

    record SimpleRule(
        String name,
        Predicate<ManagedDatabase> predicate
    ) implements OperationalRule {
        @Override
        public boolean evaluate(ManagedDatabase database) {
            return predicate.test(database);
        }
    }

    static class ManagedDatabaseException extends RuntimeException {
        ManagedDatabaseException(String message) {
            super(message);
        }
    }

    static class ValidationException extends ManagedDatabaseException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class AvailabilityException extends ManagedDatabaseException {
        AvailabilityException(String message) {
            super(message);
        }
    }

    public static void main(String[] args) {
        OperationalPolicy policy = new OperationalPolicy(
            true,
            true,
            true,
            60,
            100
        );

        ManagedDatabase database = new ManagedDatabase(
            "orders-prod",
            "PostgreSQL",
            "18.0",
            "ap-south-1",
            250,
            8,
            true
        );

        database.write(1000);
        database.createBackup(BackupType.SNAPSHOT);
        database.addReplica("ap-southeast-1");

        database.write(250);
        database.scaleStorage(400);
        database.scaleCompute(12);

        database.patch("18.1", 2);

        System.out.println("\n=== Health Checks ===");
        database.healthChecks(policy).forEach(check ->
            System.out.println(
                check.name() + ": " +
                (check.passed() ? "PASS" : "FAIL") +
                " - " + check.message()
            )
        );

        System.out.println(
            "\nPolicy result before failover: " +
            (database.evaluatePolicy(policy) ? "PASS" : "FAIL")
        );

        database.failover();
        database.printReport();

        try {
            database.scaleStorage(100);
        } catch (ManagedDatabaseException ex) {
            System.out.println(
                "\nExpected storage failure: " + ex.getMessage()
            );
        }

        try {
            database.patch("18.2", 15);
        } catch (ManagedDatabaseException ex) {
            System.out.println(
                "Expected maintenance failure: " + ex.getMessage()
            );
        }

        System.out.println(
            "\nFinal policy result: " +
            (database.evaluatePolicy(policy) ? "PASS" : "FAIL")
        );
    }
}
