#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

class ComplianceError : public runtime_error {
public:
    using runtime_error::runtime_error;
};

enum class PrivacyCategory {
    Public,
    Internal,
    Confidential,
    Personal,
    SensitivePersonal
};

enum class LegalBasis {
    Consent,
    Contract,
    LegalObligation,
    LegitimateInterest,
    PublicTask,
    VitalInterest
};

enum class ReviewStatus {
    Pending,
    Approved,
    Rejected
};

enum class RequestStatus {
    Received,
    Verified,
    InProgress,
    Completed,
    Rejected
};

enum class Severity {
    Low,
    Medium,
    High,
    Critical
};

enum class MergeDecision {
    Eligible,
    Blocked
};

string toString(PrivacyCategory value) {
    switch (value) {
        case PrivacyCategory::Public: return "PUBLIC";
        case PrivacyCategory::Internal: return "INTERNAL";
        case PrivacyCategory::Confidential: return "CONFIDENTIAL";
        case PrivacyCategory::Personal: return "PERSONAL";
        case PrivacyCategory::SensitivePersonal:
            return "SENSITIVE_PERSONAL";
    }
    return "UNKNOWN";
}

string toString(Severity value) {
    switch (value) {
        case Severity::Low: return "LOW";
        case Severity::Medium: return "MEDIUM";
        case Severity::High: return "HIGH";
        case Severity::Critical: return "CRITICAL";
    }
    return "UNKNOWN";
}

string toString(RequestStatus value) {
    switch (value) {
        case RequestStatus::Received: return "RECEIVED";
        case RequestStatus::Verified: return "VERIFIED";
        case RequestStatus::InProgress: return "IN_PROGRESS";
        case RequestStatus::Completed: return "COMPLETED";
        case RequestStatus::Rejected: return "REJECTED";
    }
    return "UNKNOWN";
}

struct DataAsset {
    string id;
    string name;
    string owner;
    string purpose;
    PrivacyCategory category;
    LegalBasis legalBasis;
    set<string> frameworks;
    int retentionDays;
    bool encrypted;
    bool active;
};

struct Consent {
    string id;
    string subjectId;
    string assetId;
    string purpose;
    bool granted;
    chrono::system_clock::time_point expiresAt;
    bool hasExpiration;
};

struct User {
    string id;
    string role;
    set<string> permissions;
    bool active;
};

struct Policy {
    string id;
    string name;
    bool encryptionRequired;
    int maximumRetentionDays;
    bool enabled;
};

struct StatusCheck {
    string name;
    bool passed;
    bool required;
    string message;
};

struct Finding {
    string id;
    string assetId;
    Severity severity;
    string description;
    bool resolved;
};

struct SubjectRequest {
    string id;
    string subjectId;
    RequestStatus status;
};

struct GovernanceDecision {
    MergeDecision decision;
    vector<string> blockers;
};

class ComplianceEngine {
private:
    map<string, DataAsset> assets;
    map<string, User> users;
    map<string, Consent> consents;
    map<string, Policy> policies;
    map<string, SubjectRequest> requests;
    vector<Finding> findings;
    vector<string> auditLog;

    static string currentTimestamp() {
        auto now = chrono::system_clock::now();
        time_t timestamp = chrono::system_clock::to_time_t(now);

        stringstream output;
        output << put_time(gmtime(&timestamp), "%Y-%m-%dT%H:%M:%SZ");

        return output.str();
    }

    void log(
        const string& actor,
        const string& action,
        const string& resource
    ) {
        auditLog.push_back(
            currentTimestamp() + " | " +
            actor + " | " + action + " | " + resource
        );
    }

    void authorize(
        const string& actorId,
        const string& permission
    ) {
        auto iterator = users.find(actorId);

        if (
            iterator == users.end() ||
            !iterator->second.active
        ) {
            throw ComplianceError("Unknown or inactive user.");
        }

        if (
            iterator->second.permissions.find(permission)
            == iterator->second.permissions.end()
        ) {
            log(actorId, "ACCESS_DENIED", permission);
            throw ComplianceError("Permission denied.");
        }
    }

    static bool validFramework(const string& framework) {
        static const set<string> allowed = {
            "GDPR",
            "DPDPA",
            "ISO27001",
            "HIPAA"
        };

        return allowed.count(framework) != 0;
    }

public:
    void registerUser(const User& user) {
        if (user.id.empty() || user.role.empty()) {
            throw ComplianceError("Invalid user.");
        }

        if (users.count(user.id)) {
            throw ComplianceError("Duplicate user.");
        }

        users.emplace(user.id, user);
    }

    void registerPolicy(const Policy& policy) {
        if (
            policy.id.empty() ||
            policy.name.empty() ||
            policy.maximumRetentionDays <= 0
        ) {
            throw ComplianceError("Invalid governance policy.");
        }

        if (policies.count(policy.id)) {
            throw ComplianceError("Duplicate policy.");
        }

        policies.emplace(policy.id, policy);
    }

    void registerAsset(
        const string& actorId,
        const DataAsset& asset
    ) {
        authorize(actorId, "asset:create");

        if (
            asset.id.empty() ||
            asset.name.empty() ||
            asset.owner.empty() ||
            asset.purpose.empty()
        ) {
            throw ComplianceError("Incomplete asset definition.");
        }

        if (asset.retentionDays <= 0) {
            throw ComplianceError("Invalid retention duration.");
        }

        if (
            asset.category == PrivacyCategory::SensitivePersonal &&
            !asset.encrypted
        ) {
            throw ComplianceError(
                "Sensitive personal data requires encryption."
            );
        }

        for (const auto& framework : asset.frameworks) {
            if (!validFramework(framework)) {
                throw ComplianceError(
                    "Unsupported regulatory framework: " + framework
                );
            }
        }

        if (assets.count(asset.id)) {
            throw ComplianceError("Asset already exists.");
        }

        assets.emplace(asset.id, asset);

        log(actorId, "ASSET_REGISTERED", asset.id);
    }

    void grantConsent(
        const string& actorId,
        const Consent& consent
    ) {
        authorize(actorId, "consent:manage");

        auto asset = assets.find(consent.assetId);

        if (asset == assets.end()) {
            throw ComplianceError("Unknown asset.");
        }

        if (
            asset->second.legalBasis != LegalBasis::Consent ||
            consent.purpose != asset->second.purpose
        ) {
            throw ComplianceError("Consent does not match processing.");
        }

        if (consent.id.empty() || consent.subjectId.empty()) {
            throw ComplianceError("Invalid consent record.");
        }

        if (consents.count(consent.id)) {
            throw ComplianceError("Duplicate consent.");
        }

        consents.emplace(consent.id, consent);

        log(actorId, "CONSENT_GRANTED", consent.id);
    }

    void withdrawConsent(
        const string& actorId,
        const string& consentId
    ) {
        authorize(actorId, "consent:manage");

        auto iterator = consents.find(consentId);

        if (iterator == consents.end()) {
            throw ComplianceError("Consent not found.");
        }

        iterator->second.granted = false;

        log(actorId, "CONSENT_WITHDRAWN", consentId);
    }

    bool canProcess(
        const string& assetId,
        const string& subjectId
    ) const {
        auto asset = assets.find(assetId);

        if (
            asset == assets.end() ||
            !asset->second.active
        ) {
            return false;
        }

        if (asset->second.legalBasis != LegalBasis::Consent) {
            return true;
        }

        const auto now = chrono::system_clock::now();

        for (const auto& [id, consent] : consents) {
            if (
                consent.assetId == assetId &&
                consent.subjectId == subjectId &&
                consent.purpose == asset->second.purpose &&
                consent.granted &&
                (
                    !consent.hasExpiration ||
                    now < consent.expiresAt
                )
            ) {
                return true;
            }
        }

        return false;
    }

    void readAsset(
        const string& actorId,
        const string& assetId,
        const string& subjectId
    ) {
        authorize(actorId, "asset:read");

        if (!canProcess(assetId, subjectId)) {
            throw ComplianceError(
                "Processing authorization is unavailable."
            );
        }

        log(actorId, "ASSET_READ", assetId);
    }

    vector<Finding> evaluateAsset(const string& assetId) {
        auto iterator = assets.find(assetId);

        if (iterator == assets.end()) {
            throw ComplianceError("Asset not found.");
        }

        const DataAsset& asset = iterator->second;

        vector<Finding> generated;

        auto addFinding = [&](Severity severity, string description) {
            generated.push_back({
                "F-" + to_string(findings.size() + generated.size() + 1),
                assetId,
                severity,
                description,
                false
            });
        };

        if (!asset.encrypted) {
            addFinding(
                Severity::Critical,
                "Encryption is not enabled."
            );
        }

        if (asset.frameworks.empty()) {
            addFinding(
                Severity::Medium,
                "Regulatory mapping is missing."
            );
        }

        if (asset.retentionDays > 3650) {
            addFinding(
                Severity::Medium,
                "Retention exceeds ten years."
            );
        }

        for (const auto& [id, policy] : policies) {
            if (!policy.enabled) {
                continue;
            }

            if (
                policy.encryptionRequired &&
                !asset.encrypted
            ) {
                addFinding(
                    Severity::Critical,
                    "Policy " + policy.id + " requires encryption."
                );
            }

            if (
                asset.retentionDays > policy.maximumRetentionDays
            ) {
                addFinding(
                    Severity::High,
                    "Policy " + policy.id + " retention limit exceeded."
                );
            }
        }

        findings.insert(
            findings.end(),
            generated.begin(),
            generated.end()
        );

        return generated;
    }

    void submitRequest(
        const string& actorId,
        const string& requestId,
        const string& subjectId
    ) {
        authorize(actorId, "request:manage");

        if (requestId.empty() || subjectId.empty()) {
            throw ComplianceError("Invalid subject request.");
        }

        if (requests.count(requestId)) {
            throw ComplianceError("Duplicate request.");
        }

        requests.emplace(
            requestId,
            SubjectRequest{
                requestId,
                subjectId,
                RequestStatus::Received
            }
        );

        log(actorId, "REQUEST_RECEIVED", requestId);
    }

    void transitionRequest(
        const string& actorId,
        const string& requestId,
        RequestStatus next
    ) {
        authorize(actorId, "request:manage");

        auto iterator = requests.find(requestId);

        if (iterator == requests.end()) {
            throw ComplianceError("Request not found.");
        }

        const RequestStatus current = iterator->second.status;

        bool allowed = false;

        switch (current) {
            case RequestStatus::Received:
                allowed = (
                    next == RequestStatus::Verified ||
                    next == RequestStatus::Rejected
                );
                break;

            case RequestStatus::Verified:
                allowed = (
                    next == RequestStatus::InProgress ||
                    next == RequestStatus::Rejected
                );
                break;

            case RequestStatus::InProgress:
                allowed = (
                    next == RequestStatus::Completed ||
                    next == RequestStatus::Rejected
                );
                break;

            case RequestStatus::Completed:
            case RequestStatus::Rejected:
                allowed = false;
                break;
        }

        if (!allowed) {
            throw ComplianceError("Invalid request transition.");
        }

        iterator->second.status = next;

        log(actorId, "REQUEST_TRANSITION", requestId);
    }

    GovernanceDecision evaluateGovernance(
        const string& actorId,
        const string& assetId,
        const vector<StatusCheck>& checks
    ) {
        authorize(actorId, "governance:evaluate");

        GovernanceDecision decision{
            MergeDecision::Eligible,
            {}
        };

        auto asset = assets.find(assetId);

        if (asset == assets.end()) {
            throw ComplianceError("Asset not found.");
        }

        if (!asset->second.active) {
            decision.blockers.push_back("Asset is inactive.");
        }

        for (const auto& check : checks) {
            if (check.required && !check.passed) {
                decision.blockers.push_back(
                    "Required control failed: " + check.name
                );
            }
        }

        for (const auto& [id, policy] : policies) {
            if (!policy.enabled) {
                continue;
            }

            if (
                policy.encryptionRequired &&
                !asset->second.encrypted
            ) {
                decision.blockers.push_back(
                    "Encryption policy violation: " + id
                );
            }

            if (
                asset->second.retentionDays >
                policy.maximumRetentionDays
            ) {
                decision.blockers.push_back(
                    "Retention policy violation: " + id
                );
            }
        }

        if (!decision.blockers.empty()) {
            decision.decision = MergeDecision::Blocked;
        }

        log(
            actorId,
            decision.decision == MergeDecision::Eligible
                ? "GOVERNANCE_ELIGIBLE"
                : "GOVERNANCE_BLOCKED",
            assetId
        );

        return decision;
    }

    void printReport() const {
        cout << "\n=== COMPLIANCE REPORT ===\n";

        cout << "Registered assets: " << assets.size() << "\n";
        cout << "Consent records: " << consents.size() << "\n";
        cout << "Subject requests: " << requests.size() << "\n";
        cout << "Compliance findings: " << findings.size() << "\n";
        cout << "Audit records: " << auditLog.size() << "\n";

        map<string, int> categoryCounts;

        for (const auto& [id, asset] : assets) {
            categoryCounts[toString(asset.category)]++;
        }

        cout << "\nPrivacy classification:\n";

        for (const auto& [category, count] : categoryCounts) {
            cout << category << ": " << count << "\n";
        }

        cout << "\nUnresolved findings:\n";

        for (const auto& finding : findings) {
            if (!finding.resolved) {
                cout << finding.id
                     << " | " << toString(finding.severity)
                     << " | " << finding.description << "\n";
            }
        }

        cout << "\nAudit events:\n";

        for (const string& event : auditLog) {
            cout << event << "\n";
        }
    }
};

int main() {
    try {
        ComplianceEngine engine;

        engine.registerUser({
            "admin",
            "COMPLIANCE_ADMIN",
            {
                "asset:create",
                "asset:read",
                "consent:manage",
                "request:manage",
                "governance:evaluate"
            },
            true
        });

        engine.registerUser({
            "analyst",
            "ANALYST",
            {"asset:read"},
            true
        });

        engine.registerPolicy({
            "POLICY-001",
            "Personal Data Security Policy",
            true,
            3650,
            true
        });

        DataAsset customerAsset{
            "ASSET-001",
            "Customer Identity Database",
            "Data Governance Office",
            "Customer account administration",
            PrivacyCategory::Personal,
            LegalBasis::Consent,
            {"GDPR", "DPDPA"},
            730,
            true,
            true
        };

        engine.registerAsset("admin", customerAsset);

        Consent consent{
            "CONSENT-001",
            "SUBJECT-001",
            "ASSET-001",
            "Customer account administration",
            true,
            {},
            false
        };

        engine.grantConsent("admin", consent);

        engine.readAsset(
            "analyst",
            "ASSET-001",
            "SUBJECT-001"
        );

        engine.submitRequest(
            "admin",
            "REQUEST-001",
            "SUBJECT-001"
        );

        engine.transitionRequest(
            "admin",
            "REQUEST-001",
            RequestStatus::Verified
        );

        engine.transitionRequest(
            "admin",
            "REQUEST-001",
            RequestStatus::InProgress
        );

        engine.transitionRequest(
            "admin",
            "REQUEST-001",
            RequestStatus::Completed
        );

        engine.withdrawConsent(
            "admin",
            "CONSENT-001"
        );

        try {
            engine.readAsset(
                "analyst",
                "ASSET-001",
                "SUBJECT-001"
            );
        } catch (const ComplianceError& error) {
            cout << "\nExpected access restriction: "
                 << error.what() << "\n";
        }

        vector<Finding> findings =
            engine.evaluateAsset("ASSET-001");

        cout << "\nNew compliance findings: "
             << findings.size() << "\n";

        vector<StatusCheck> checks = {
            {"Encryption verification", true, true, "Passed"},
            {"Access review", true, true, "Passed"},
            {"Retention assessment", false, true, "Failed"},
            {"Optional documentation", false, false, "Skipped"}
        };

        GovernanceDecision decision =
            engine.evaluateGovernance(
                "admin",
                "ASSET-001",
                checks
            );

        cout << "\nGovernance decision: "
             << (
                 decision.decision == MergeDecision::Eligible
                    ? "ELIGIBLE"
                    : "BLOCKED"
             ) << "\n";

        for (const string& blocker : decision.blockers) {
            cout << "BLOCKER: " << blocker << "\n";
        }

        engine.printReport();

        return 0;

    } catch (const exception& error) {
        cerr << "Fatal compliance error: "
             << error.what() << "\n";

        return 1;
    }
}
