#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

enum class RecoveryTier {
    BackupRestore,
    PilotLight,
    WarmStandby,
    MultiRegion
};

enum class RegionState {
    Primary,
    Secondary,
    Failed
};

struct RecoveryObjective {
    int rpoMinutes;
    int rtoMinutes;

    void validate() const {
        if (rpoMinutes < 0) {
            throw std::invalid_argument("RPO cannot be negative");
        }
        if (rtoMinutes <= 0) {
            throw std::invalid_argument("RTO must be positive");
        }
    }
};

struct StatusCheck {
    std::string name;
    bool passed;
};

struct ReviewDecision {
    std::string reviewer;
    bool eligible;
    bool approved;
};

struct Backup {
    std::string id;
    long long createdEpochMinutes;
    bool verified;
};

struct PullRequestRecoveryRecord {
    std::string service;
    RecoveryTier tier;
    RecoveryObjective objective;
    std::string primaryRegion;
    std::set<std::string> recoveryRegions;
    std::vector<StatusCheck> statusChecks;
    std::vector<ReviewDecision> approvals;
    std::vector<Backup> backups;
};

struct Region {
    std::string name;
    RegionState state;
    int capacityPercent;

    bool available() const {
        return state != RegionState::Failed && capacityPercent > 0;
    }
};

struct Evaluation {
    bool primaryFailed;
    bool targetAvailable;
    bool targetConfigured;
    bool backupAvailable;
    bool rpoMet;
    bool rtoMet;
    bool statusChecksPassed;
    bool approvalsSatisfied;
    int estimatedRto;
    int estimatedRpo;

    bool eligible() const {
        return primaryFailed &&
               targetAvailable &&
               targetConfigured &&
               backupAvailable &&
               rpoMet &&
               rtoMet &&
               statusChecksPassed &&
               approvalsSatisfied;
    }
};

class GovernanceEngine {
private:
    std::map<std::string, Region> regions_;

    static int recoveryTime(RecoveryTier tier) {
        switch (tier) {
            case RecoveryTier::BackupRestore:
                return 90;
            case RecoveryTier::PilotLight:
                return 30;
            case RecoveryTier::WarmStandby:
                return 10;
            case RecoveryTier::MultiRegion:
                return 2;
        }

        throw std::logic_error("Unknown recovery tier");
    }

    static bool isRpoSatisfied(
        const PullRequestRecoveryRecord& service,
        long long nowMinutes,
        int& age
    ) {
        if (service.backups.empty()) {
            age = 0;
            return false;
        }

        const Backup& latest = service.backups.back();

        if (!latest.verified) {
            age = 0;
            return false;
        }

        age = static_cast<int>(
            std::max(0LL, nowMinutes - latest.createdEpochMinutes)
        );

        return age <= service.objective.rpoMinutes;
    }

public:
    void addRegion(Region region) {
        if (region.capacityPercent < 0 ||
            region.capacityPercent > 100) {
            throw std::invalid_argument("Invalid region capacity");
        }

        if (regions_.contains(region.name)) {
            throw std::invalid_argument("Duplicate region");
        }

        regions_.emplace(region.name, std::move(region));
    }

    void failRegion(const std::string& name) {
        auto it = regions_.find(name);

        if (it == regions_.end()) {
            throw std::out_of_range("Unknown region");
        }

        it->second.state = RegionState::Failed;
    }

    Evaluation evaluate(
        const PullRequestRecoveryRecord& service,
        const std::string& targetRegion,
        long long nowMinutes
    ) const {
        service.objective.validate();

        auto primary = regions_.find(service.primaryRegion);
        auto target = regions_.find(targetRegion);

        if (primary == regions_.end()) {
            throw std::out_of_range("Unknown primary region");
        }

        if (target == regions_.end()) {
            throw std::out_of_range("Unknown target region");
        }

        int backupAge = 0;

        bool rpoMet = isRpoSatisfied(
            service,
            nowMinutes,
            backupAge
        );

        bool statusChecksPassed = std::all_of(
            service.statusChecks.begin(),
            service.statusChecks.end(),
            [](const StatusCheck& check) {
                return check.passed;
            }
        );

        int eligibleApprovals = 0;

        for (const auto& approval : service.approvals) {
            if (approval.eligible && approval.approved) {
                ++eligibleApprovals;
            }
        }

        bool approvalsSatisfied = eligibleApprovals >= 2;

        int estimatedRto = recoveryTime(service.tier);

        return Evaluation{
            .primaryFailed =
                primary->second.state == RegionState::Failed,
            .targetAvailable =
                target->second.available(),
            .targetConfigured =
                service.recoveryRegions.contains(targetRegion),
            .backupAvailable =
                !service.backups.empty(),
            .rpoMet = rpoMet,
            .rtoMet =
                estimatedRto <= service.objective.rtoMinutes,
            .statusChecksPassed = statusChecksPassed,
            .approvalsSatisfied = approvalsSatisfied,
            .estimatedRto = estimatedRto,
            .estimatedRpo = backupAge
        };
    }

    void printEvaluation(
        const Evaluation& evaluation
    ) const {
        std::cout << "Recovery eligibility\n"
                  << "  primary failed: "
                  << std::boolalpha
                  << evaluation.primaryFailed << '\n'
                  << "  target available: "
                  << evaluation.targetAvailable << '\n'
                  << "  target configured: "
                  << evaluation.targetConfigured << '\n'
                  << "  backup available: "
                  << evaluation.backupAvailable << '\n'
                  << "  RPO satisfied: "
                  << evaluation.rpoMet
                  << " (" << evaluation.estimatedRpo
                  << " minutes)\n"
                  << "  RTO satisfied: "
                  << evaluation.rtoMet
                  << " (" << evaluation.estimatedRto
                  << " minutes)\n"
                  << "  status checks passed: "
                  << evaluation.statusChecksPassed << '\n'
                  << "  approvals satisfied: "
                  << evaluation.approvalsSatisfied << '\n'
                  << "  FINAL ELIGIBILITY: "
                  << evaluation.eligible() << "\n\n";
    }

    void executeFailover(
        PullRequestRecoveryRecord& service,
        const std::string& targetRegion,
        long long nowMinutes
    ) {
        Evaluation evaluation =
            evaluate(service, targetRegion, nowMinutes);

        printEvaluation(evaluation);

        if (!evaluation.eligible()) {
            throw std::runtime_error(
                "Failover rejected because recovery policy "
                "conditions are not satisfied"
            );
        }

        regions_.at(service.primaryRegion).state =
            RegionState::Failed;

        regions_.at(targetRegion).state =
            RegionState::Primary;

        service.primaryRegion = targetRegion;

        std::cout
            << "Failover completed successfully: "
            << service.service
            << " -> "
            << targetRegion
            << "\n\n";
    }
};

int main() {
    try {
        GovernanceEngine engine;

        engine.addRegion({
            "ap-south-1",
            RegionState::Primary,
            100
        });

        engine.addRegion({
            "ap-southeast-1",
            RegionState::Secondary,
            100
        });

        engine.addRegion({
            "eu-west-1",
            RegionState::Primary,
            100
        });

        engine.addRegion({
            "eu-central-1",
            RegionState::Secondary,
            100
        });

        const long long nowMinutes =
            std::chrono::duration_cast<std::chrono::minutes>(
                std::chrono::system_clock::now()
                    .time_since_epoch()
            ).count();

        PullRequestRecoveryRecord payments{
            .service = "payments",
            .tier = RecoveryTier::WarmStandby,
            .objective = {5, 15},
            .primaryRegion = "ap-south-1",
            .recoveryRegions = {
                "ap-south-1",
                "ap-southeast-1"
            },
            .statusChecks = {
                {"backup-integrity", true},
                {"replication-health", true},
                {"security-validation", true}
            },
            .approvals = {
                {"platform-owner", true, true},
                {"security-owner", true, true},
                {"temporary-reviewer", false, true}
            },
            .backups = {
                {
                    "payments-backup-001",
                    nowMinutes - 2,
                    true
                }
            }
        };

        engine.failRegion("ap-south-1");

        engine.executeFailover(
            payments,
            "ap-southeast-1",
            nowMinutes
        );

        PullRequestRecoveryRecord analytics{
            .service = "analytics",
            .tier = RecoveryTier::BackupRestore,
            .objective = {30, 60},
            .primaryRegion = "eu-west-1",
            .recoveryRegions = {
                "eu-west-1",
                "eu-central-1"
            },
            .statusChecks = {
                {"backup-integrity", true},
                {"replication-health", true}
            },
            .approvals = {
                {"analytics-owner", true, true},
                {"security-owner", true, false}
            },
            .backups = {
                {
                    "analytics-backup-001",
                    nowMinutes - 45,
                    true
                }
            }
        };

        engine.failRegion("eu-west-1");

        try {
            engine.executeFailover(
                analytics,
                "eu-central-1",
                nowMinutes
            );
        } catch (const std::exception& error) {
            std::cout
                << "Expected analytics rejection: "
                << error.what()
                << "\n\n";
        }

        // A failed recovery target demonstrates that a configured
        // secondary is not necessarily an available recovery target.
        PullRequestRecoveryRecord catalog{
            .service = "catalog",
            .tier = RecoveryTier::MultiRegion,
            .objective = {1, 5},
            .primaryRegion = "ap-southeast-1",
            .recoveryRegions = {
                "ap-southeast-1",
                "ap-south-1"
            },
            .statusChecks = {
                {"replication-health", true}
            },
            .approvals = {
                {"platform-owner", true, true},
                {"security-owner", true, true}
            },
            .backups = {
                {
                    "catalog-backup-001",
                    nowMinutes,
                    true
                }
            }
        };

        engine.failRegion("ap-southeast-1");

        try {
            engine.executeFailover(
                catalog,
                "ap-south-1",
                nowMinutes
            );
        } catch (const std::exception& error) {
            std::cout
                << "Expected target rejection: "
                << error.what()
                << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal configuration error: "
            << error.what()
            << '\n';
        return 1;
    }

    return 0;
}
