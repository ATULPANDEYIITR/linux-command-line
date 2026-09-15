#include <algorithm>
#include <array>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
 * C++17 case study:
 *
 * Secure shared document repository
 *
 * The system models a small enterprise document repository in which:
 *
 *   - users have UID/GID identities;
 *   - users belong to groups;
 *   - documents have Unix-like owner/group/other permissions;
 *   - application roles provide an additional authorization layer;
 *   - privileged administrative operations require explicit authority;
 *   - audit events record security-sensitive actions;
 *   - permission checks follow least privilege;
 *   - invalid identities and malformed operations are rejected.
 *
 * This is a simulation. It deliberately does not modify the host operating
 * system or execute privileged commands.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic users_groups_case_study.cpp -o users_groups_case_study
 *
 * Run:
 *   ./users_groups_case_study
 */

using UID = std::uint32_t;
using GID = std::uint32_t;

enum class Permission : std::uint8_t {
    Read = 4,
    Write = 2,
    Execute = 1
};

enum class AccessClass {
    Owner,
    Group,
    Other
};

enum class Role {
    Viewer,
    Editor,
    SecurityAdministrator,
    SystemAdministrator
};

struct User {
    UID uid;
    std::string username;
    GID primaryGroup;
    std::set<GID> supplementaryGroups;
    std::set<Role> roles;
    bool active{true};

    bool belongsTo(GID gid) const {
        return primaryGroup == gid || supplementaryGroups.contains(gid);
    }
};

struct Group {
    GID gid;
    std::string name;
    std::set<UID> members;
};

struct Document {
    std::uint64_t id;
    std::string name;
    UID ownerUid;
    GID groupGid;
    std::uint16_t mode;
    std::string contents;
    bool confidential{false};
};

struct AuditEvent {
    std::string username;
    std::string action;
    std::string resource;
    bool allowed;
    std::string reason;
};

class AuditLog {
private:
    std::vector<AuditEvent> events;

public:
    void record(
        const User& user,
        const std::string& action,
        const std::string& resource,
        bool allowed,
        const std::string& reason
    ) {
        events.push_back({
            user.username,
            action,
            resource,
            allowed,
            reason
        });
    }

    void print() const {
        std::cout << "\n=== Security audit log ===\n";

        for (const auto& event : events) {
            std::cout
                << "[" << (event.allowed ? "ALLOW" : "DENY") << "] "
                << event.username
                << " -> "
                << event.action
                << " -> "
                << event.resource
                << " | "
                << event.reason
                << '\n';
        }
    }
};

class Repository {
private:
    std::unordered_map<UID, User> users;
    std::unordered_map<GID, Group> groups;
    std::unordered_map<std::uint64_t, Document> documents;
    AuditLog audit;
    std::uint64_t nextDocumentId{1};

    static bool hasBit(std::uint16_t mode, int shift, int permission) {
        return ((mode >> shift) & permission) != 0;
    }

    std::optional<AccessClass> selectAccessClass(
        const User& user,
        const Document& document
    ) const {
        /*
         * Traditional Unix permission evaluation:
         *
         * 1. If UID matches owner UID, owner bits apply.
         * 2. Otherwise, if the user's identity belongs to the file group,
         *    group bits apply.
         * 3. Otherwise, other bits apply.
         *
         * The classes are not merged together.
         */
        if (user.uid == document.ownerUid) {
            return AccessClass::Owner;
        }

        if (user.belongsTo(document.groupGid)) {
            return AccessClass::Group;
        }

        return AccessClass::Other;
    }

    bool hasPermission(
        const User& user,
        const Document& document,
        Permission requested
    ) const {
        const auto accessClass = selectAccessClass(user, document);

        if (!accessClass.has_value()) {
            return false;
        }

        const int permissionValue = static_cast<int>(requested);

        switch (*accessClass) {
            case AccessClass::Owner:
                return hasBit(document.mode, 6, permissionValue);

            case AccessClass::Group:
                return hasBit(document.mode, 3, permissionValue);

            case AccessClass::Other:
                return hasBit(document.mode, 0, permissionValue);
        }

        return false;
    }

    bool hasRole(const User& user, Role role) const {
        return user.roles.contains(role);
    }

    bool isPrivilegedAdministrator(const User& user) const {
        return hasRole(user, Role::SystemAdministrator)
            || hasRole(user, Role::SecurityAdministrator);
    }

public:
    void addGroup(GID gid, const std::string& name) {
        if (groups.contains(gid)) {
            throw std::runtime_error("GID already exists: " + std::to_string(gid));
        }

        groups.emplace(gid, Group{gid, name, {}});
    }

    void addUser(
        UID uid,
        const std::string& username,
        GID primaryGroup,
        std::set<Role> roles = {}
    ) {
        if (users.contains(uid)) {
            throw std::runtime_error("UID already exists");
        }

        if (!groups.contains(primaryGroup)) {
            throw std::runtime_error("Primary group does not exist");
        }

        User user{
            uid,
            username,
            primaryGroup,
            {},
            std::move(roles),
            true
        };

        users.emplace(uid, user);
        groups.at(primaryGroup).members.insert(uid);
    }

    void addUserToGroup(UID uid, GID gid) {
        if (!users.contains(uid)) {
            throw std::runtime_error("Unknown UID");
        }

        if (!groups.contains(gid)) {
            throw std::runtime_error("Unknown GID");
        }

        users.at(uid).supplementaryGroups.insert(gid);
        groups.at(gid).members.insert(uid);
    }

    const User& getUser(UID uid) const {
        const auto iterator = users.find(uid);

        if (iterator == users.end()) {
            throw std::runtime_error("Unknown user");
        }

        return iterator->second;
    }

    Document& getDocument(std::uint64_t documentId) {
        auto iterator = documents.find(documentId);

        if (iterator == documents.end()) {
            throw std::runtime_error("Unknown document");
        }

        return iterator->second;
    }

    const Document& getDocument(std::uint64_t documentId) const {
        auto iterator = documents.find(documentId);

        if (iterator == documents.end()) {
            throw std::runtime_error("Unknown document");
        }

        return iterator->second;
    }

    std::uint64_t createDocument(
        UID ownerUid,
        GID groupGid,
        const std::string& name,
        std::uint16_t mode,
        bool confidential
    ) {
        const User& owner = getUser(ownerUid);

        if (!owner.active) {
            throw std::runtime_error("Inactive users cannot create documents");
        }

        if (!owner.belongsTo(groupGid)) {
            throw std::runtime_error(
                "Owner must belong to the document's owning group"
            );
        }

        if (mode > 0777) {
            throw std::runtime_error("Invalid ordinary permission mode");
        }

        const std::uint64_t id = nextDocumentId++;

        documents.emplace(
            id,
            Document{
                id,
                name,
                ownerUid,
                groupGid,
                mode,
                "",
                confidential
            }
        );

        audit.record(
            owner,
            "CREATE",
            name,
            true,
            "Document created"
        );

        return id;
    }

    bool readDocument(UID uid, std::uint64_t documentId) {
        User& user = users.at(uid);
        Document& document = getDocument(documentId);

        if (!user.active) {
            audit.record(
                user,
                "READ",
                document.name,
                false,
                "Account is inactive"
            );
            return false;
        }

        if (document.confidential && !isPrivilegedAdministrator(user)) {
            /*
             * Confidentiality is an application-level rule layered above
             * ordinary file permissions. This demonstrates why Unix mode bits
             * alone are not always sufficient for a complete application.
             */
            if (!hasPermission(user, document, Permission::Read)) {
                audit.record(
                    user,
                    "READ",
                    document.name,
                    false,
                    "Permission denied"
                );
                return false;
            }
        } else if (!hasPermission(user, document, Permission::Read)) {
            audit.record(
                user,
                "READ",
                document.name,
                false,
                "Permission denied"
            );
            return false;
        }

        audit.record(
            user,
            "READ",
            document.name,
            true,
            "Read permission granted"
        );

        std::cout
            << "\n[" << user.username << "] reads "
            << document.name
            << ":\n"
            << document.contents
            << '\n';

        return true;
    }

    bool writeDocument(
        UID uid,
        std::uint64_t documentId,
        const std::string& newContents
    ) {
        User& user = users.at(uid);
        Document& document = getDocument(documentId);

        if (!user.active) {
            audit.record(
                user,
                "WRITE",
                document.name,
                false,
                "Account is inactive"
            );
            return false;
        }

        if (!hasPermission(user, document, Permission::Write)) {
            audit.record(
                user,
                "WRITE",
                document.name,
                false,
                "Write permission denied"
            );
            return false;
        }

        document.contents = newContents;

        audit.record(
            user,
            "WRITE",
            document.name,
            true,
            "Write permission granted"
        );

        return true;
    }

    bool changeMode(
        UID uid,
        std::uint64_t documentId,
        std::uint16_t newMode
    ) {
        User& user = users.at(uid);
        Document& document = getDocument(documentId);

        /*
         * chmod is normally restricted to the owner or an appropriately
         * privileged identity. This simulation uses that simplified rule.
         */
        const bool authorized =
            user.uid == document.ownerUid
            || isPrivilegedAdministrator(user);

        if (newMode > 0777) {
            audit.record(
                user,
                "CHMOD",
                document.name,
                false,
                "Invalid permission mode"
            );
            return false;
        }

        if (!authorized) {
            audit.record(
                user,
                "CHMOD",
                document.name,
                false,
                "Only owner or administrator may change mode"
            );
            return false;
        }

        document.mode = newMode;

        audit.record(
            user,
            "CHMOD",
            document.name,
            true,
            "Permission mode changed"
        );

        return true;
    }

    bool changeGroup(
        UID uid,
        std::uint64_t documentId,
        GID newGroup
    ) {
        User& user = users.at(uid);
        Document& document = getDocument(documentId);

        if (!groups.contains(newGroup)) {
            audit.record(
                user,
                "CHGRP",
                document.name,
                false,
                "Target group does not exist"
            );
            return false;
        }

        /*
         * Group ownership changes are security-sensitive. The simulation
         * permits administrators to perform them, avoiding an over-broad
         * assumption that every owner can arbitrarily transfer ownership.
         */
        if (!isPrivilegedAdministrator(user)) {
            audit.record(
                user,
                "CHGRP",
                document.name,
                false,
                "Administrative privilege required"
            );
            return false;
        }

        document.groupGid = newGroup;

        audit.record(
            user,
            "CHGRP",
            document.name,
            true,
            "Owning group changed"
        );

        return true;
    }

    bool disableUser(UID actorUid, UID targetUid) {
        User& actor = users.at(actorUid);
        User& target = users.at(targetUid);

        if (!isPrivilegedAdministrator(actor)) {
            audit.record(
                actor,
                "DISABLE_USER",
                target.username,
                false,
                "Administrative privilege required"
            );
            return false;
        }

        target.active = false;

        audit.record(
            actor,
            "DISABLE_USER",
            target.username,
            true,
            "Account disabled"
        );

        return true;
    }

    void printUsers() const {
        std::cout << "\n=== Users ===\n";

        for (const auto& [uid, user] : users) {
            std::cout
                << "UID=" << uid
                << " username=" << user.username
                << " primaryGID=" << user.primaryGroup
                << " active=" << std::boolalpha << user.active
                << " groups={";

            bool first = true;

            for (GID gid : user.supplementaryGroups) {
                if (!first) {
                    std::cout << ',';
                }

                std::cout << gid;
                first = false;
            }

            std::cout << "}\n";
        }
    }

    void printDocuments() const {
        std::cout << "\n=== Documents ===\n";

        for (const auto& [id, document] : documents) {
            std::cout
                << "ID=" << id
                << " name=" << document.name
                << " ownerUID=" << document.ownerUid
                << " groupGID=" << document.groupGid
                << " mode=" << std::oct << std::setw(3)
                << std::setfill('0') << document.mode
                << std::dec << std::setfill(' ')
                << " confidential=" << std::boolalpha
                << document.confidential
                << '\n';
        }
    }

    void printAudit() const {
        audit.print();
    }
};

std::string modeToSymbolic(std::uint16_t mode) {
    std::string result = "----------";

    const std::array<char, 9> symbols{
        'r', 'w', 'x',
        'r', 'w', 'x',
        'r', 'w', 'x'
    };

    const std::array<int, 9> bits{
        8, 7, 6,
        5, 4, 3,
        2, 1, 0
    };

    for (std::size_t i = 0; i < symbols.size(); ++i) {
        if ((mode >> bits[i]) & 1U) {
            result[i + 1] = symbols[i];
        }
    }

    return result;
}

void demonstratePermissionTheory() {
    std::cout << "\n=== Permission model ===\n";

    const std::array<std::uint16_t, 6> modes{
        0600, 0640, 0644, 0700, 0750, 0755
    };

    for (const auto mode : modes) {
        std::cout
            << std::oct
            << mode
            << std::dec
            << " -> "
            << modeToSymbolic(mode)
            << '\n';
    }

    std::cout << "\nPermission values:\n";
    std::cout << "read=4, write=2, execute=1\n";
}

void demonstrateUmask() {
    std::cout << "\n=== umask calculation ===\n";

    const std::array<std::uint16_t, 3> masks{
        0022, 0027, 0077
    };

    for (const auto mask : masks) {
        const auto fileMode =
            static_cast<std::uint16_t>(0666 & ~mask);

        const auto directoryMode =
            static_cast<std::uint16_t>(0777 & ~mask);

        std::cout
            << "umask "
            << std::oct << std::setw(3) << std::setfill('0')
            << mask
            << std::setfill(' ') << std::dec
            << " -> file "
            << std::oct << fileMode
            << ", directory "
            << directoryMode
            << std::dec
            << '\n';
    }
}

void demonstrateTests() {
    std::cout << "\n=== Direct permission tests ===\n";

    User owner{1000, "alice", 100, {200}, {}, true};
    User groupMember{1001, "bob", 200, {100}, {}, true};
    User outsider{1002, "eve", 300, {}, {}, true};

    Document document{
        1,
        "financial-report",
        1000,
        100,
        0640,
        "",
        false
    };

    auto evaluate = [&](const User& user, Permission permission) {
        if (user.uid == document.ownerUid) {
            return (document.mode >> 6)
                & static_cast<int>(permission);
        }

        if (user.belongsTo(document.groupGid)) {
            return (document.mode >> 3)
                & static_cast<int>(permission);
        }

        return document.mode
            & static_cast<int>(permission);
    };

    struct Test {
        std::string name;
        const User& user;
        Permission permission;
        bool expected;
    };

    const std::vector<Test> tests{
        {"owner can read", owner, Permission::Read, true},
        {"owner can write", owner, Permission::Write, true},
        {"owner cannot execute", owner, Permission::Execute, false},
        {"group member can read", groupMember, Permission::Read, true},
        {"group member cannot write", groupMember, Permission::Write, false},
        {"outsider cannot read", outsider, Permission::Read, false}
    };

    std::size_t passed = 0;

    for (const auto& test : tests) {
        const bool actual = evaluate(test.user, test.permission) != 0;
        const bool success = actual == test.expected;

        std::cout
            << (success ? "PASS " : "FAIL ")
            << test.name
            << '\n';

        if (success) {
            ++passed;
        }
    }

    std::cout
        << passed
        << '/'
        << tests.size()
        << " tests passed\n";
}

void runCaseStudy() {
    std::cout << "Secure Document Repository Case Study\n";
    std::cout << "====================================\n";

    Repository repository;

    /*
     * Organization:
     *
     * developers -> application developers
     * finance    -> financial analysts
     * security   -> security administrators
     * operations -> operational administrators
     */
    repository.addGroup(100, "developers");
    repository.addGroup(200, "finance");
    repository.addGroup(300, "security");
    repository.addGroup(400, "operations");

    repository.addUser(
        1000,
        "alice",
        100,
        {Role::Editor}
    );

    repository.addUser(
        1001,
        "bob",
        200,
        {Role::Viewer}
    );

    repository.addUser(
        1002,
        "carol",
        300,
        {Role::SecurityAdministrator}
    );

    repository.addUser(
        1003,
        "dave",
        400,
        {Role::SystemAdministrator}
    );

    repository.addUserToGroup(1000, 200);

    /*
     * Alice is a developer whose supplementary finance membership lets her
     * collaborate on finance documents. This illustrates the difference
     * between primary and supplementary group membership.
     */
    const auto publicDocument =
        repository.createDocument(
            1000,
            100,
            "engineering-notes.txt",
            0640,
            false
        );

    const auto financeDocument =
        repository.createDocument(
            1000,
            200,
            "quarterly-finance.txt",
            0640,
            true
        );

    repository.writeDocument(
        1000,
        publicDocument,
        "Architecture review and deployment notes."
    );

    repository.writeDocument(
        1000,
        financeDocument,
        "Confidential financial planning information."
    );

    repository.readDocument(1001, publicDocument);
    repository.readDocument(1001, financeDocument);

    /*
     * Bob belongs to the finance group. The permission bits therefore
     * authorize group-level reading of the finance document.
     */
    repository.writeDocument(
        1001,
        financeDocument,
        "Bob attempts an unauthorized write."
    );

    repository.changeMode(
        1001,
        financeDocument,
        0666
    );

    /*
     * Carol is a security administrator. The application policy allows
     * her to perform administrative actions that ordinary users cannot.
     */
    repository.changeMode(
        1002,
        financeDocument,
        0660
    );

    /*
     * Dave has system administrator authority and can change group ownership
     * and disable accounts.
     */
    repository.changeGroup(
        1003,
        publicDocument,
        400
    );

    repository.disableUser(1003, 1001);

    /*
     * Bob's account is now disabled. His next access is denied even if
     * document permissions would otherwise permit it.
     */
    repository.readDocument(1001, financeDocument);

    repository.printUsers();
    repository.printDocuments();
    repository.printAudit();
}

int main() {
    try {
        demonstratePermissionTheory();
        demonstrateUmask();
        demonstrateTests();
        runCaseStudy();

        std::cout << "\n=== Design observations ===\n";
        std::cout
            << "1. Authentication and authorization are separate controls.\n"
            << "2. Groups simplify shared access management.\n"
            << "3. Owner/group/other permission classes are compact but limited.\n"
            << "4. Application authorization can add rules beyond Unix mode bits.\n"
            << "5. Least privilege reduces the impact of compromised identities.\n"
            << "6. Privileged actions should be explicit and auditable.\n"
            << "7. Disabling an account is an independent authorization control.\n"
            << "8. ACLs, capabilities, SELinux/AppArmor, containers, and sandboxing\n"
            << "   can provide additional controls in real Linux environments.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }
}
