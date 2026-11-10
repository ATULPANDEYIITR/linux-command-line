#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class KeyPurpose {
    Encryption,
    Signing,
    HMAC,
    KeyEncryption
};

enum class KeyStatus {
    Active,
    Rotated,
    Disabled,
    Revoked,
    Expired
};

enum class Role {
    Admin,
    CryptoOperator,
    Application,
    Auditor
};

enum class CheckStatus {
    Passed,
    Failed,
    Pending
};

string toString(KeyStatus status) {
    switch (status) {
        case KeyStatus::Active: return "ACTIVE";
        case KeyStatus::Rotated: return "ROTATED";
        case KeyStatus::Disabled: return "DISABLED";
        case KeyStatus::Revoked: return "REVOKED";
        case KeyStatus::Expired: return "EXPIRED";
    }
    return "UNKNOWN";
}

string toString(CheckStatus status) {
    switch (status) {
        case CheckStatus::Passed: return "PASSED";
        case CheckStatus::Failed: return "FAILED";
        case CheckStatus::Pending: return "PENDING";
    }
    return "UNKNOWN";
}

struct Principal {
    string id;
    Role role;
};

struct KeyVersion {
    string keyId;
    int version;
    KeyPurpose purpose;
    vector<uint8_t> material;
    KeyStatus status;
    chrono::system_clock::time_point createdAt;
    chrono::system_clock::time_point expiresAt;
    bool hardwareProtected;
};

struct AuditEvent {
    string actor;
    string action;
    string keyId;
    string result;
};

struct StatusCheck {
    string name;
    CheckStatus status;
};

struct Review {
    string reviewer;
    bool eligible;
    bool dismissed;
    bool stale;
    bool approved;
};

struct ProtectionPolicy {
    int requiredApprovals = 2;
    bool requirePassingChecks = true;
    bool requireResolvedConversations = true;
    bool prohibitDirectPush = true;
    bool prohibitForcePush = true;
    bool prohibitDeletion = true;
    bool requireLinearHistory = false;
    bool requireFreshApprovals = true;
    bool allowAdministratorBypass = false;
};

struct PullRequest {
    int id;
    string sourceBranch;
    string targetBranch;
    string author;
    bool draft = false;
    bool open = true;
    bool baseSynchronized = true;
    bool mergeConflict = false;
    bool conversationsResolved = true;
    bool directPushAttempt = false;
    bool forcePushAttempt = false;
    bool branchDeletionAttempt = false;
    bool linearHistory = true;
    bool administratorBypass = false;

    vector<string> commits;
    vector<Review> reviews;
    vector<StatusCheck> checks;
};

struct Evaluation {
    bool eligible;
    vector<string> reasons;
};

class SecureRandom {
private:
    random_device rd;

public:
    vector<uint8_t> generate(size_t size) {
        vector<uint8_t> output(size);

        for (auto& byte : output) {
            byte = static_cast<uint8_t>(rd());
        }

        return output;
    }
};

class AuditLogger {
private:
    vector<AuditEvent> events;

public:
    void record(
        const string& actor,
        const string& action,
        const string& keyId,
        const string& result
    ) {
        events.push_back({
            actor, action, keyId, result
        });
    }

    void print() const {
        for (const auto& event : events) {
            cout << event.actor << " | "
                 << event.action << " | "
                 << event.keyId << " | "
                 << event.result << '\n';
        }
    }
};

class KeyManagementService {
private:
    map<string, vector<KeyVersion>> keys;
    SecureRandom random;
    AuditLogger audit;
    int rotationDays;

    void authorize(
        const Principal& principal,
        bool adminOnly = false
    ) const {
        if (adminOnly && principal.role != Role::Admin) {
            throw runtime_error("Administrator permission required");
        }

        if (!adminOnly &&
            principal.role != Role::Admin &&
            principal.role != Role::CryptoOperator) {
            throw runtime_error("Cryptographic operation denied");
        }
    }

public:
    explicit KeyManagementService(int days = 90)
        : rotationDays(days) {
        if (days < 1) {
            throw invalid_argument("Invalid rotation period");
        }
    }

    string createKey(
        const Principal& principal,
        KeyPurpose purpose
    ) {
        authorize(principal);

        string keyId = "KEY-" + to_string(
            random.generate(8)[0]
        ) + "-" + to_string(keys.size() + 1);

        auto now = chrono::system_clock::now();

        KeyVersion key{
            keyId,
            1,
            purpose,
            random.generate(32),
            KeyStatus::Active,
            now,
            now + chrono::hours(24 * rotationDays),
            true
        };

        keys[keyId].push_back(move(key));

        audit.record(
            principal.id,
            "CREATE",
            keyId,
            "SUCCESS"
        );

        return keyId;
    }

    const KeyVersion& activeKey(
        const string& keyId
    ) {
        auto it = keys.find(keyId);

        if (it == keys.end() || it->second.empty()) {
            throw runtime_error("Key not found");
        }

        auto& key = it->second.back();

        if (key.status != KeyStatus::Active) {
            throw runtime_error("Key is not active");
        }

        if (chrono::system_clock::now() >= key.expiresAt) {
            key.status = KeyStatus::Expired;
            throw runtime_error("Key expired");
        }

        return key;
    }

    int rotate(
        const Principal& principal,
        const string& keyId
    ) {
        authorize(principal);

        const KeyVersion& current = activeKey(keyId);

        KeyVersion next{
            keyId,
            current.version + 1,
            current.purpose,
            random.generate(32),
            KeyStatus::Active,
            chrono::system_clock::now(),
            chrono::system_clock::now()
                + chrono::hours(24 * rotationDays),
            current.hardwareProtected
        };

        keys[keyId].back().status = KeyStatus::Rotated;

        keys[keyId].push_back(move(next));

        audit.record(
            principal.id,
            "ROTATE",
            keyId,
            "SUCCESS"
        );

        return keys[keyId].back().version;
    }

    void revoke(
        const Principal& principal,
        const string& keyId
    ) {
        authorize(principal, true);

        auto it = keys.find(keyId);

        if (it == keys.end()) {
            throw runtime_error("Key not found");
        }

        for (auto& key : it->second) {
            key.status = KeyStatus::Revoked;
        }

        audit.record(
            principal.id,
            "REVOKE",
            keyId,
            "SUCCESS"
        );
    }

    void printMetadata() const {
        for (const auto& [id, versions] : keys) {
            for (const auto& key : versions) {
                cout << id
                     << " version=" << key.version
                     << " state=" << toString(key.status)
                     << " hardware_protected="
                     << boolalpha
                     << key.hardwareProtected
                     << '\n';
            }
        }
    }

    void printAudit() const {
        audit.print();
    }
};

class GovernanceEngine {
private:
    ProtectionPolicy policy;

public:
    explicit GovernanceEngine(ProtectionPolicy p)
        : policy(p) {}

    Evaluation evaluate(
        const PullRequest& pr,
        const string& protectedBranch
    ) const {
        Evaluation result{true, {}};

        auto reject = [&](const string& reason) {
            result.eligible = false;
            result.reasons.push_back(reason);
        };

        if (!pr.open) {
            reject("Pull Request is closed");
        }

        if (pr.targetBranch != protectedBranch) {
            reject("Target branch does not match policy");
        }

        if (pr.draft) {
            reject("Draft Pull Request cannot be merged");
        }

        if (pr.commits.empty()) {
            reject("No commits in proposed changes");
        }

        if (!pr.baseSynchronized) {
            reject("Source branch is not synchronized");
        }

        if (pr.mergeConflict) {
            reject("Merge conflict exists");
        }

        if (policy.requireLinearHistory && !pr.linearHistory) {
            reject("Linear history required");
        }

        if (policy.requireResolvedConversations &&
            !pr.conversationsResolved) {
            reject("Unresolved review conversations");
        }

        if (policy.requirePassingChecks) {
            for (const auto& check : pr.checks) {
                if (check.status != CheckStatus::Passed) {
                    reject(
                        "Status check not passed: " + check.name
                    );
                }
            }

            if (pr.checks.empty()) {
                reject("Required status checks missing");
            }
        }

        if (pr.directPushAttempt && policy.prohibitDirectPush) {
            reject("Direct push prohibited");
        }

        if (pr.forcePushAttempt && policy.prohibitForcePush) {
            reject("Force push prohibited");
        }

        if (pr.branchDeletionAttempt && policy.prohibitDeletion) {
            reject("Branch deletion prohibited");
        }

        if (pr.administratorBypass &&
            !policy.allowAdministratorBypass) {
            reject("Administrator bypass is prohibited");
        }

        set<string> approvedReviewers;
        bool changesRequested = false;

        for (const auto& review : pr.reviews) {
            if (!review.eligible ||
                review.dismissed ||
                (policy.requireFreshApprovals && review.stale)) {
                continue;
            }

            if (review.approved) {
                approvedReviewers.insert(review.reviewer);
            }
        }

        for (const auto& review : pr.reviews) {
            if (review.eligible &&
                !review.dismissed &&
                review.approved == false &&
                !review.stale) {
                changesRequested = true;
            }
        }

        if (changesRequested) {
            reject("An active review requests changes");
        }

        if (static_cast<int>(approvedReviewers.size()) <
            policy.requiredApprovals) {
            reject("Insufficient eligible approvals");
        }

        return result;
    }
};

PullRequest createExamplePullRequest() {
    PullRequest pr;

    pr.id = 101;
    pr.sourceBranch = "feature/key-rotation";
    pr.targetBranch = "main";
    pr.author = "developer-01";

    pr.commits = {
        "commit-001",
        "commit-002",
        "commit-003"
    };

    pr.reviews = {
        {"reviewer-01", true, false, false, true},
        {"reviewer-02", true, false, false, true},
        {"reviewer-03", false, false, false, true}
    };

    pr.checks = {
        {"unit-tests", CheckStatus::Passed},
        {"security-scan", CheckStatus::Passed},
        {"dependency-audit", CheckStatus::Passed}
    };

    return pr;
}

int main() {
    try {
        cout << "KEY MANAGEMENT ENGINE\n\n";

        Principal admin{
            "security-admin", Role::Admin
        };

        Principal operatorUser{
            "crypto-operator", Role::CryptoOperator
        };

        KeyManagementService kms(90);

        string keyId = kms.createKey(
            operatorUser,
            KeyPurpose::KeyEncryption
        );

        cout << "Created key: " << keyId << '\n';

        int version = kms.rotate(
            operatorUser,
            keyId
        );

        cout << "Rotated to version: "
             << version << "\n\n";

        cout << "KEY METADATA\n";
        kms.printMetadata();

        cout << "\nREPOSITORY GOVERNANCE\n";

        ProtectionPolicy policy;
        policy.requiredApprovals = 2;
        policy.requirePassingChecks = true;
        policy.requireResolvedConversations = true;

        GovernanceEngine engine(policy);

        PullRequest pr = createExamplePullRequest();

        Evaluation evaluation = engine.evaluate(
            pr,
            "main"
        );

        cout << "Pull Request #" << pr.id << '\n';

        if (evaluation.eligible) {
            cout << "MERGE ELIGIBLE\n";
        } else {
            cout << "MERGE BLOCKED\n";

            for (const auto& reason : evaluation.reasons) {
                cout << " - " << reason << '\n';
            }
        }

        cout << "\nFAILURE SCENARIO\n";

        pr.checks[1].status = CheckStatus::Failed;
        pr.reviews[0].stale = true;
        pr.conversationsResolved = false;

        evaluation = engine.evaluate(pr, "main");

        for (const auto& reason : evaluation.reasons) {
            cout << " - " << reason << '\n';
        }

        cout << "\nREVOCATION\n";

        kms.revoke(admin, keyId);
        kms.printMetadata();

        cout << "\nAUDIT LOG\n";
        kms.printAudit();

    } catch (const exception& error) {
        cerr << "Security engine failure: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
