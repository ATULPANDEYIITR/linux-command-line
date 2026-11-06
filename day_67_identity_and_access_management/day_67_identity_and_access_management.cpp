#include <algorithm>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class AccountStatus {
    Active,
    Disabled,
    Locked
};

enum class PolicyEffect {
    Allow,
    Deny
};

enum class Decision {
    Allowed,
    Denied
};

string toString(AccountStatus status) {
    switch (status) {
        case AccountStatus::Active: return "ACTIVE";
        case AccountStatus::Disabled: return "DISABLED";
        case AccountStatus::Locked: return "LOCKED";
    }
    return "UNKNOWN";
}

struct Permission {
    string resource;
    string action;

    bool operator<(const Permission& other) const {
        return tie(resource, action) <
               tie(other.resource, other.action);
    }

    bool operator==(const Permission& other) const {
        return resource == other.resource &&
               action == other.action;
    }
};

struct User {
    string id;
    string username;
    string department;
    AccountStatus status = AccountStatus::Active;
    set<string> groups;
};

struct Role {
    string id;
    string name;
    set<Permission> permissions;
};

struct Group {
    string id;
    string name;
    set<string> members;
    set<string> roles;
};

struct Policy {
    string id;
    string name;
    PolicyEffect effect;
    set<Permission> permissions;
    set<string> departments;
    set<string> excludedUsers;
};

struct AuditRecord {
    string userId;
    string resource;
    string action;
    Decision decision;
    string reason;
    time_t timestamp;
};

struct Evaluation {
    Decision decision;
    string reason;
};

class IAMEngine {
private:
    map<string, User> users;
    map<string, Role> roles;
    map<string, Group> groups;
    map<string, Policy> policies;
    vector<AuditRecord> audit;

    static void validateNonEmpty(
        const string& value,
        const string& field
    ) {
        if (value.empty() ||
            value.find_first_not_of(" \t\n") == string::npos) {
            throw invalid_argument(field + " cannot be empty.");
        }
    }

public:
    void addUser(const User& user) {
        validateNonEmpty(user.id, "User ID");
        validateNonEmpty(user.username, "Username");

        if (users.count(user.id)) {
            throw runtime_error("Duplicate user ID.");
        }

        for (const auto& [id, existing] : users) {
            if (existing.username == user.username) {
                throw runtime_error("Duplicate username.");
            }
        }

        users.emplace(user.id, user);
    }

    void addRole(const Role& role) {
        validateNonEmpty(role.id, "Role ID");

        if (roles.count(role.id)) {
            throw runtime_error("Duplicate role ID.");
        }

        roles.emplace(role.id, role);
    }

    void addGroup(const Group& group) {
        validateNonEmpty(group.id, "Group ID");

        if (groups.count(group.id)) {
            throw runtime_error("Duplicate group ID.");
        }

        groups.emplace(group.id, group);
    }

    void addPolicy(const Policy& policy) {
        validateNonEmpty(policy.id, "Policy ID");

        if (policies.count(policy.id)) {
            throw runtime_error("Duplicate policy ID.");
        }

        if (policy.permissions.empty()) {
            throw invalid_argument(
                "Policy requires at least one permission."
            );
        }

        policies.emplace(policy.id, policy);
    }

    User& getUser(const string& id) {
        auto it = users.find(id);
        if (it == users.end()) {
            throw out_of_range("User not found: " + id);
        }
        return it->second;
    }

    Group& getGroup(const string& id) {
        auto it = groups.find(id);
        if (it == groups.end()) {
            throw out_of_range("Group not found: " + id);
        }
        return it->second;
    }

    Role& getRole(const string& id) {
        auto it = roles.find(id);
        if (it == roles.end()) {
            throw out_of_range("Role not found: " + id);
        }
        return it->second;
    }

    void addMember(
        const string& userId,
        const string& groupId
    ) {
        User& user = getUser(userId);
        Group& group = getGroup(groupId);

        user.groups.insert(groupId);
        group.members.insert(userId);
    }

    void removeMember(
        const string& userId,
        const string& groupId
    ) {
        User& user = getUser(userId);
        Group& group = getGroup(groupId);

        user.groups.erase(groupId);
        group.members.erase(userId);
    }

    void assignRole(
        const string& groupId,
        const string& roleId
    ) {
        Group& group = getGroup(groupId);
        getRole(roleId);

        group.roles.insert(roleId);
    }

    set<string> effectiveRoles(const string& userId) {
        const User& user = getUser(userId);
        set<string> result;

        for (const string& groupId : user.groups) {
            const Group& group = getGroup(groupId);

            result.insert(
                group.roles.begin(),
                group.roles.end()
            );
        }

        return result;
    }

    set<Permission> effectivePermissions(
        const string& userId
    ) {
        set<Permission> result;

        for (const string& roleId : effectiveRoles(userId)) {
            const Role& role = getRole(roleId);

            result.insert(
                role.permissions.begin(),
                role.permissions.end()
            );
        }

        return result;
    }

    Evaluation evaluate(
        const string& userId,
        const Permission& requested
    ) {
        const User& user = getUser(userId);

        if (user.status != AccountStatus::Active) {
            return {
                Decision::Denied,
                "Account is not active."
            };
        }

        vector<const Policy*> applicable;

        for (const auto& [id, policy] : policies) {
            if (!policy.permissions.count(requested)) {
                continue;
            }

            if (
                !policy.departments.empty() &&
                !policy.departments.count(user.department)
            ) {
                continue;
            }

            if (policy.excludedUsers.count(userId)) {
                continue;
            }

            applicable.push_back(&policy);
        }

        // Explicit denial always overrides permissions and allows.
        for (const Policy* policy : applicable) {
            if (policy->effect == PolicyEffect::Deny) {
                return {
                    Decision::Denied,
                    "Explicit deny: " + policy->name
                };
            }
        }

        for (const Policy* policy : applicable) {
            if (policy->effect == PolicyEffect::Allow) {
                return {
                    Decision::Allowed,
                    "Policy allow: " + policy->name
                };
            }
        }

        const auto permissions =
            effectivePermissions(userId);

        if (permissions.count(requested)) {
            return {
                Decision::Allowed,
                "Assigned role permission."
            };
        }

        return {
            Decision::Denied,
            "No matching permission."
        };
    }

    Evaluation authorize(
        const string& userId,
        const Permission& permission
    ) {
        Evaluation result = evaluate(userId, permission);

        audit.push_back({
            userId,
            permission.resource,
            permission.action,
            result.decision,
            result.reason,
            time(nullptr)
        });

        return result;
    }

    void changeStatus(
        const string& userId,
        AccountStatus status
    ) {
        getUser(userId).status = status;
    }

    void revokeAllAccess(const string& userId) {
        User& user = getUser(userId);

        for (const string& groupId : user.groups) {
            getGroup(groupId).members.erase(userId);
        }

        user.groups.clear();
        user.status = AccountStatus::Disabled;
    }

    void printLeastPrivilegeReport(
        const string& userId
    ) {
        const User& user = getUser(userId);

        cout << "\nLEAST PRIVILEGE REPORT\n";
        cout << "User: " << user.username << '\n';
        cout << "Status: " << toString(user.status) << '\n';

        cout << "Groups: ";
        for (const auto& group : user.groups) {
            cout << group << " ";
        }

        cout << "\nRoles: ";
        for (const auto& role : effectiveRoles(userId)) {
            cout << role << " ";
        }

        cout << "\nEffective permissions:\n";

        for (const auto& permission :
             effectivePermissions(userId)) {
            cout << "  "
                 << permission.resource
                 << ":"
                 << permission.action
                 << '\n';
        }
    }

    void printAudit() const {
        cout << "\nACCESS AUDIT\n";

        for (const auto& event : audit) {
            cout << event.userId
                 << " | "
                 << event.action
                 << " "
                 << event.resource
                 << " | "
                 << (
                     event.decision == Decision::Allowed
                     ? "ALLOW"
                     : "DENY"
                 )
                 << " | "
                 << event.reason
                 << '\n';
        }
    }

    size_t auditCount() const {
        return audit.size();
    }
};

void printDecision(
    const string& userId,
    const string& resource,
    const string& action,
    const Evaluation& evaluation
) {
    cout << userId << " -> "
         << action << " "
         << resource << " : "
         << (
             evaluation.decision == Decision::Allowed
             ? "ALLOW"
             : "DENY"
         )
         << " (" << evaluation.reason << ")\n";
}

int main() {
    try {
        IAMEngine iam;

        // Enterprise identity records.
        iam.addUser({
            "U001", "Alice", "Finance"
        });

        iam.addUser({
            "U002", "Bob", "Engineering"
        });

        iam.addUser({
            "U003", "Carol", "Security"
        });

        // Roles contain permissions, not users.
        iam.addRole({
            "R001",
            "ReportReader",
            {
                {"reports", "read"}
            }
        });

        iam.addRole({
            "R002",
            "SecurityAdministrator",
            {
                {"users", "manage"},
                {"users", "delete"}
            }
        });

        iam.addRole({
            "R003",
            "ReportEditor",
            {
                {"reports", "read"},
                {"reports", "create"}
            }
        });

        iam.addGroup({
            "G001", "Finance", {}, {}
        });

        iam.addGroup({
            "G002", "Engineering", {}, {}
        });

        iam.addGroup({
            "G003", "Security", {}, {}
        });

        iam.assignRole("G001", "R001");
        iam.assignRole("G002", "R001");
        iam.assignRole("G003", "R002");

        iam.addMember("U001", "G001");
        iam.addMember("U002", "G002");
        iam.addMember("U003", "G003");

        // A deny policy protects finance payroll information.
        iam.addPolicy({
            "P001",
            "PayrollProtection",
            PolicyEffect::Deny,
            {
                {"payroll", "read"}
            },
            {"Finance"},
            {}
        });

        // A department-specific allow policy.
        iam.addPolicy({
            "P002",
            "FinanceReportCreation",
            PolicyEffect::Allow,
            {
                {"reports", "create"}
            },
            {"Finance"},
            {}
        });

        cout << "IDENTITY AND ACCESS MANAGEMENT\n";
        cout << "====================================\n";

        vector<tuple<string, string, string>> requests = {
            {"U001", "reports", "read"},
            {"U001", "reports", "create"},
            {"U001", "payroll", "read"},
            {"U002", "reports", "create"},
            {"U003", "users", "delete"}
        };

        for (const auto& [user, resource, action] : requests) {
            printDecision(
                user,
                resource,
                action,
                iam.authorize(
                    user,
                    {resource, action}
                )
            );
        }

        iam.printLeastPrivilegeReport("U001");

        cout << "\nACCOUNT DEACTIVATION\n";
        iam.changeStatus("U002", AccountStatus::Disabled);

        printDecision(
            "U002",
            "reports",
            "read",
            iam.authorize("U002", {"reports", "read"})
        );

        cout << "\nACCESS REVOCATION\n";
        iam.revokeAllAccess("U001");

        printDecision(
            "U001",
            "reports",
            "read",
            iam.authorize("U001", {"reports", "read"})
        );

        // Duplicate identifiers must fail.
        try {
            iam.addUser({
                "U001", "AnotherUser", "Engineering"
            });
        } catch (const exception& error) {
            cout << "Expected validation failure: "
                 << error.what() << '\n';
        }

        // Unknown identities must fail safely.
        try {
            iam.authorize(
                "UNKNOWN",
                {"reports", "read"}
            );
        } catch (const exception& error) {
            cout << "Expected lookup failure: "
                 << error.what() << '\n';
        }

        iam.printAudit();

        cout << "\nAudit records: "
             << iam.auditCount() << '\n';

    } catch (const exception& error) {
        cerr << "IAM failure: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
