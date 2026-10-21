import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

public class DisasterRecoveryGovernance {

    enum RecoveryTier {
        BACKUP_RESTORE,
        PILOT_LIGHT,
        WARM_STANDBY,
        MULTI_REGION
    }

    enum RegionState {
        PRIMARY,
        SECONDARY,
        FAILED
    }

    enum ServiceState {
        HEALTHY,
        DEGRADED,
        RECOVERING,
        RECOVERED
    }

    record RecoveryObjective(int rpoMinutes, int rtoMinutes) {
        RecoveryObjective {
            if (rpoMinutes < 0) {
                throw new IllegalArgumentException(
                    "RPO cannot be negative"
                );
            }

            if (rtoMinutes <= 0) {
                throw new IllegalArgumentException(
                    "RTO must be positive"
                );
            }
        }
    }

    record StatusCheck(String name, boolean passed) {}

    record Backup(
        String id,
        Instant createdAt,
        boolean verified
    ) {}

    record Approval(
        String reviewer,
        boolean eligible,
        boolean approved
    ) {}

    static final class Region {
        private final String name;
        private RegionState state;
        private final int capacityPercent;

        Region(
            String name,
            RegionState state,
            int capacityPercent
        ) {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Region name is required"
                );
            }

            if (capacityPercent < 0 || capacityPercent > 100) {
                throw new IllegalArgumentException(
                    "Invalid capacity"
                );
            }

            this.name = name;
            this.state = Objects.requireNonNull(state);
            this.capacityPercent = capacityPercent;
        }

        String name() {
            return name;
        }

        RegionState state() {
            return state;
        }

        void fail() {
            state = RegionState.FAILED;
        }

        void promote() {
            if (state == RegionState.FAILED) {
                throw new IllegalStateException(
                    "Failed region cannot be promoted"
                );
            }

            state = RegionState.PRIMARY;
        }

        boolean available() {
            return state != RegionState.FAILED
                && capacityPercent > 0;
        }
    }

    static final class RecoveryService {
        private final String name;
        private final RecoveryObjective objective;
        private final RecoveryTier tier;
        private final Set<String> configuredRegions;
        private final List<Backup> backups = new ArrayList<>();
        private final List<StatusCheck> statusChecks = new ArrayList<>();
        private final List<Approval> approvals = new ArrayList<>();
        private ServiceState state = ServiceState.HEALTHY;

        RecoveryService(
            String name,
            RecoveryObjective objective,
            RecoveryTier tier,
            Set<String> configuredRegions
        ) {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Service name is required"
                );
            }

            if (configuredRegions == null ||
                configuredRegions.isEmpty()) {
                throw new IllegalArgumentException(
                    "At least one recovery region is required"
                );
            }

            this.name = name;
            this.objective = objective;
            this.tier = Objects.requireNonNull(tier);
            this.configuredRegions =
                Set.copyOf(configuredRegions);
        }

        String name() {
            return name;
        }

        RecoveryObjective objective() {
            return objective;
        }

        RecoveryTier tier() {
            return tier;
        }

        ServiceState state() {
            return state;
        }

        void addBackup(Backup backup) {
            backups.add(Objects.requireNonNull(backup));
        }

        void addStatusCheck(StatusCheck check) {
            statusChecks.add(Objects.requireNonNull(check));
        }

        void addApproval(Approval approval) {
            approvals.add(Objects.requireNonNull(approval));
        }

        Backup latestBackup() {
            if (backups.isEmpty()) {
                return null;
            }

            return backups.get(backups.size() - 1);
        }

        boolean configuredIn(String region) {
            return configuredRegions.contains(region);
        }

        boolean statusChecksPassed() {
            return statusChecks.stream()
                .allMatch(StatusCheck::passed);
        }

        long eligibleApprovals() {
            return approvals.stream()
                .filter(Approval::eligible)
                .filter(Approval::approved)
                .count();
        }

        void markRecovering() {
            state = ServiceState.RECOVERING;
        }

        void markRecovered() {
            state = ServiceState.RECOVERED;
        }
    }

    record RecoveryEvaluation(
        boolean primaryFailed,
        boolean targetAvailable,
        boolean targetConfigured,
        boolean backupAvailable,
        boolean rpoSatisfied,
        boolean rtoSatisfied,
        boolean checksPassed,
        boolean approvalsSatisfied,
        long backupAgeMinutes,
        int estimatedRtoMinutes
    ) {
        boolean eligible() {
            return primaryFailed
                && targetAvailable
                && targetConfigured
                && backupAvailable
                && rpoSatisfied
                && rtoSatisfied
                && checksPassed
                && approvalsSatisfied;
        }
    }

    static final class RecoveryPolicy {
        private static final Map<RecoveryTier, Integer> RTO_ESTIMATES =
            Map.of(
                RecoveryTier.BACKUP_RESTORE, 90,
                RecoveryTier.PILOT_LIGHT, 30,
                RecoveryTier.WARM_STANDBY, 10,
                RecoveryTier.MULTI_REGION, 2
            );

        private final int requiredApprovals;

        RecoveryPolicy(int requiredApprovals) {
            if (requiredApprovals <= 0) {
                throw new IllegalArgumentException(
                    "Required approvals must be positive"
                );
            }

            this.requiredApprovals = requiredApprovals;
        }

        RecoveryEvaluation evaluate(
            RecoveryService service,
            Region primary,
            Region target,
            Instant now
        ) {
            Backup backup = service.latestBackup();

            boolean backupAvailable = backup != null;

            long backupAgeMinutes = backup == null
                ? Long.MAX_VALUE
                : Duration.between(
                    backup.createdAt(),
                    now
                ).toMinutes();

            boolean rpoSatisfied =
                backupAvailable
                && backup.verified()
                && backupAgeMinutes
                    <= service.objective().rpoMinutes();

            int estimatedRto =
                RTO_ESTIMATES.get(service.tier());

            boolean rtoSatisfied =
                estimatedRto
                    <= service.objective().rtoMinutes();

            boolean approvalsSatisfied =
                service.eligibleApprovals()
                    >= requiredApprovals;

            return new RecoveryEvaluation(
                primary.state() == RegionState.FAILED,
                target.available(),
                service.configuredIn(target.name()),
                backupAvailable,
                rpoSatisfied,
                rtoSatisfied,
                service.statusChecksPassed(),
                approvalsSatisfied,
                backupAgeMinutes,
                estimatedRto
            );
        }
    }

    static final class RecoveryServiceManager {
        private final RecoveryPolicy policy;

        RecoveryServiceManager(RecoveryPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
        }

        void failover(
            RecoveryService service,
            Region primary,
            Region target,
            Instant now
        ) {
            if (primary == target) {
                throw new IllegalArgumentException(
                    "Primary and target cannot be identical"
                );
            }

            RecoveryEvaluation evaluation =
                policy.evaluate(
                    service,
                    primary,
                    target,
                    now
                );

            printEvaluation(evaluation);

            if (!evaluation.eligible()) {
                throw new IllegalStateException(
                    "Recovery policy rejected failover"
                );
            }

            service.markRecovering();

            primary.fail();
            target.promote();

            service.markRecovered();
        }

        private void printEvaluation(
            RecoveryEvaluation evaluation
        ) {
            System.out.println(
                "Recovery evaluation:"
            );

            System.out.println(
                "  primary failed = "
                    + evaluation.primaryFailed()
            );

            System.out.println(
                "  target available = "
                    + evaluation.targetAvailable()
            );

            System.out.println(
                "  target configured = "
                    + evaluation.targetConfigured()
            );

            System.out.println(
                "  backup available = "
                    + evaluation.backupAvailable()
            );

            System.out.println(
                "  RPO satisfied = "
                    + evaluation.rpoSatisfied()
                    + " ("
                    + evaluation.backupAgeMinutes()
                    + " minutes)"
            );

            System.out.println(
                "  RTO satisfied = "
                    + evaluation.rtoSatisfied()
                    + " ("
                    + evaluation.estimatedRtoMinutes()
                    + " minutes)"
            );

            System.out.println(
                "  status checks passed = "
                    + evaluation.checksPassed()
            );

            System.out.println(
                "  approvals satisfied = "
                    + evaluation.approvalsSatisfied()
            );

            System.out.println(
                "  eligible = "
                    + evaluation.eligible()
            );

            System.out.println();
        }
    }

    private static Backup recentBackup(String id) {
        return new Backup(
            id,
            Instant.now().minusSeconds(120),
            true
        );
    }

    private static Backup staleBackup(String id) {
        return new Backup(
            id,
            Instant.now().minusSeconds(45 * 60L),
            true
        );
    }

    public static void main(String[] args) {
        Region primary =
            new Region(
                "ap-south-1",
                RegionState.PRIMARY,
                100
            );

        Region warmStandby =
            new Region(
                "ap-southeast-1",
                RegionState.SECONDARY,
                100
            );

        RecoveryService payments =
            new RecoveryService(
                "payments",
                new RecoveryObjective(5, 15),
                RecoveryTier.WARM_STANDBY,
                Set.of(
                    primary.name(),
                    warmStandby.name()
                )
            );

        payments.addBackup(
            recentBackup("payments-001")
        );

        payments.addStatusCheck(
            new StatusCheck(
                "backup-integrity",
                true
            )
        );

        payments.addStatusCheck(
            new StatusCheck(
                "replication-health",
                true
            )
        );

        payments.addApproval(
            new Approval(
                "platform-owner",
                true,
                true
            )
        );

        payments.addApproval(
            new Approval(
                "security-owner",
                true,
                true
            )
        );

        RecoveryServiceManager manager =
            new RecoveryServiceManager(
                new RecoveryPolicy(2)
            );

        primary.fail();

        manager.failover(
            payments,
            primary,
            warmStandby,
            Instant.now()
        );

        System.out.println(
            "Payments state: "
                + payments.state()
        );

        Region euPrimary =
            new Region(
                "eu-west-1",
                RegionState.PRIMARY,
                100
            );

        Region euStandby =
            new Region(
                "eu-central-1",
                RegionState.SECONDARY,
                100
            );

        RecoveryService analytics =
            new RecoveryService(
                "analytics",
                new RecoveryObjective(30, 60),
                RecoveryTier.BACKUP_RESTORE,
                Set.of(
                    euPrimary.name(),
                    euStandby.name()
                )
            );

        analytics.addBackup(
            staleBackup("analytics-001")
        );

        analytics.addStatusCheck(
            new StatusCheck(
                "backup-integrity",
                true
            )
        );

        analytics.addApproval(
            new Approval(
                "analytics-owner",
                true,
                true
            )
        );

        analytics.addApproval(
            new Approval(
                "security-owner",
                true,
                false
            )
        );

        euPrimary.fail();

        try {
            manager.failover(
                analytics,
                euPrimary,
                euStandby,
                Instant.now()
            );
        } catch (IllegalStateException error) {
            System.out.println(
                "Expected analytics rejection: "
                    + error.getMessage()
            );
        }

        // A configured region can still be unusable because its
        // infrastructure capacity has failed.
        Region unavailable =
            new Region(
                "us-east-2",
                RegionState.FAILED,
                100
            );

        RecoveryService catalog =
            new RecoveryService(
                "catalog",
                new RecoveryObjective(1, 5),
                RecoveryTier.MULTI_REGION,
                Set.of(
                    warmStandby.name(),
                    unavailable.name()
                )
            );

        catalog.addBackup(
            recentBackup("catalog-001")
        );

        catalog.addStatusCheck(
            new StatusCheck(
                "replication-health",
                true
            )
        );

        catalog.addApproval(
            new Approval(
                "platform-owner",
                true,
                true
            )
        );

        catalog.addApproval(
            new Approval(
                "security-owner",
                true,
                true
            )
        );

        try {
            manager.failover(
                catalog,
                warmStandby,
                unavailable,
                Instant.now()
            );
        } catch (IllegalStateException error) {
            System.out.println(
                "Expected unavailable-target rejection: "
                    + error.getMessage()
            );
        }
    }
}
