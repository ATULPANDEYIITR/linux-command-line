#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Linux Administration Case Study
 *
 * Scenario
 * --------
 * A small production web server must be prepared for an application team.
 *
 * The server requires:
 *
 *   - named user accounts
 *   - groups for role-based access
 *   - SSH public-key authentication
 *   - controlled file permissions
 *   - package installation
 *   - system services
 *   - firewall rules
 *   - monitoring
 *   - audit logging
 *   - backup policy
 *   - desired-state validation
 *
 * This is a safe administrative simulator. It does not modify the host
 * operating system. Instead, it models the state that an administrator would
 * establish using Linux commands such as useradd, chmod, chown, apt, systemctl,
 * ssh-keygen, journalctl, and ss.
 *
 * Compile:
 *
 *   g++ -std=c++17 -Wall -Wextra -pedantic linux_administration_case_study.cpp -o linux_admin
 *
 * Run:
 *
 *   ./linux_admin
 */

using namespace std;


// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

string yesNo(bool value) {
    return value ? "yes" : "no";
}

void section(const string& title) {
    cout << "\n" << string(78, '=') << "\n";
    cout << title << "\n";
    cout << string(78, '=') << "\n";
}

void subsection(const string& title) {
    cout << "\n" << string(78, '-') << "\n";
    cout << title << "\n";
    cout << string(78, '-') << "\n";
}


// ---------------------------------------------------------------------------
// Users and groups
// ---------------------------------------------------------------------------

class LinuxUser {
private:
    string username_;
    int uid_;
    string primaryGroup_;
    set<string> groups_;
    string homeDirectory_;
    string shell_;
    bool locked_;

public:
    LinuxUser(
        string username,
        int uid,
        string primaryGroup,
        string homeDirectory,
        string shell
    )
        : username_(move(username)),
          uid_(uid),
          primaryGroup_(move(primaryGroup)),
          homeDirectory_(move(homeDirectory)),
          shell_(move(shell)),
          locked_(false) {
        groups_.insert(primaryGroup_);
    }

    const string& username() const {
        return username_;
    }

    int uid() const {
        return uid_;
    }

    const string& primaryGroup() const {
        return primaryGroup_;
    }

    const set<string>& groups() const {
        return groups_;
    }

    void addGroup(const string& group) {
        groups_.insert(group);
    }

    void lock() {
        locked_ = true;
    }

    void unlock() {
        locked_ = false;
    }

    bool locked() const {
        return locked_;
    }

    void print() const {
        cout << "User: " << username_ << "\n";
        cout << "UID: " << uid_ << "\n";
        cout << "Primary group: " << primaryGroup_ << "\n";
        cout << "Groups: ";

        bool first = true;

        for (const auto& group : groups_) {
            if (!first) {
                cout << ", ";
            }

            cout << group;
            first = false;
        }

        cout << "\n";
        cout << "Home: " << homeDirectory_ << "\n";
        cout << "Shell: " << shell_ << "\n";
        cout << "Locked: " << yesNo(locked_) << "\n";
    }
};


class UserManager {
private:
    map<string, LinuxUser> users_;
    map<string, set<string>> groups_;

public:
    UserManager() {
        createGroup("root");

        users_.emplace(
            piecewise_construct,
            forward_as_tuple("root"),
            forward_as_tuple(
                "root",
                0,
                "root",
                "/root",
                "/bin/bash"
            )
        );

        groups_["root"].insert("root");
    }

    void createGroup(const string& group) {
        if (groups_.count(group)) {
            throw runtime_error("Group already exists: " + group);
        }

        groups_[group] = {};
    }

    void createUser(
        const string& username,
        int uid,
        const string& primaryGroup
    ) {
        if (users_.count(username)) {
            throw runtime_error("User already exists: " + username);
        }

        if (!groups_.count(primaryGroup)) {
            createGroup(primaryGroup);
        }

        users_.emplace(
            piecewise_construct,
            forward_as_tuple(username),
            forward_as_tuple(
                username,
                uid,
                primaryGroup,
                "/home/" + username,
                "/bin/bash"
            )
        );

        groups_[primaryGroup].insert(username);
    }

    void addToGroup(
        const string& username,
        const string& group
    ) {
        auto user = users_.find(username);

        if (user == users_.end()) {
            throw runtime_error("Unknown user: " + username);
        }

        if (!groups_.count(group)) {
            throw runtime_error("Unknown group: " + group);
        }

        user->second.addGroup(group);
        groups_[group].insert(username);
    }

    LinuxUser& user(const string& username) {
        auto iterator = users_.find(username);

        if (iterator == users_.end()) {
            throw runtime_error("Unknown user: " + username);
        }

        return iterator->second;
    }

    const LinuxUser& user(const string& username) const {
        auto iterator = users_.find(username);

        if (iterator == users_.end()) {
            throw runtime_error("Unknown user: " + username);
        }

        return iterator->second;
    }

    void printUsers() const {
        for (const auto& [name, user] : users_) {
            cout << left
                 << setw(16) << name
                 << "uid=" << setw(6) << user.uid()
                 << "locked=" << yesNo(user.locked())
                 << "\n";
        }
    }
};


// ---------------------------------------------------------------------------
// Permissions
// ---------------------------------------------------------------------------

struct Permission {
    bool read = false;
    bool write = false;
    bool execute = false;

    int numeric() const {
        return
            (read ? 4 : 0) +
            (write ? 2 : 0) +
            (execute ? 1 : 0);
    }

    string symbolic() const {
        string result;

        result += read ? 'r' : '-';
        result += write ? 'w' : '-';
        result += execute ? 'x' : '-';

        return result;
    }
};


class FileEntry {
private:
    string path_;
    string owner_;
    string group_;
    Permission ownerPermission_;
    Permission groupPermission_;
    Permission otherPermission_;
    bool directory_;

public:
    FileEntry(
        string path,
        string owner,
        string group,
        Permission ownerPermission,
        Permission groupPermission,
        Permission otherPermission,
        bool directory = false
    )
        : path_(move(path)),
          owner_(move(owner)),
          group_(move(group)),
          ownerPermission_(ownerPermission),
          groupPermission_(groupPermission),
          otherPermission_(otherPermission),
          directory_(directory) {}

    const string& path() const {
        return path_;
    }

    Permission effectivePermission(
        const LinuxUser& user
    ) const {
        if (user.username() == owner_) {
            return ownerPermission_;
        }

        if (user.groups().count(group_)) {
            return groupPermission_;
        }

        return otherPermission_;
    }

    int numericMode() const {
        return
            ownerPermission_.numeric() * 100 +
            groupPermission_.numeric() * 10 +
            otherPermission_.numeric();
    }

    string symbolicMode() const {
        return
            string(directory_ ? "d" : "-") +
            ownerPermission_.symbolic() +
            groupPermission_.symbolic() +
            otherPermission_.symbolic();
    }

    void print() const {
        cout << symbolicMode()
             << " " << owner_
             << ":" << group_
             << " " << path_
             << " mode=" << numericMode()
             << "\n";
    }
};


// ---------------------------------------------------------------------------
// Packages
// ---------------------------------------------------------------------------

struct Package {
    string name;
    string version;
    bool installed = false;
};


class PackageManager {
private:
    map<string, Package> packages_;

public:
    void addPackage(
        const string& name,
        const string& version
    ) {
        packages_[name] = Package{name, version, false};
    }

    void install(const string& name) {
        auto iterator = packages_.find(name);

        if (iterator == packages_.end()) {
            throw runtime_error("Package not found: " + name);
        }

        iterator->second.installed = true;
    }

    bool installed(const string& name) const {
        auto iterator = packages_.find(name);

        if (iterator == packages_.end()) {
            return false;
        }

        return iterator->second.installed;
    }

    void print() const {
        for (const auto& [name, package] : packages_) {
            if (package.installed) {
                cout << left
                     << setw(20) << package.name
                     << package.version
                     << "\n";
            }
        }
    }
};


// ---------------------------------------------------------------------------
// Services
// ---------------------------------------------------------------------------

enum class ServiceState {
    Stopped,
    Running,
    Failed
};

string serviceStateText(ServiceState state) {
    switch (state) {
        case ServiceState::Stopped:
            return "stopped";

        case ServiceState::Running:
            return "running";

        case ServiceState::Failed:
            return "failed";
    }

    return "unknown";
}


class Service {
private:
    string name_;
    string description_;
    ServiceState state_;
    bool enabled_;

public:
    Service(string name, string description)
        : name_(move(name)),
          description_(move(description)),
          state_(ServiceState::Stopped),
          enabled_(false) {}

    const string& name() const {
        return name_;
    }

    void start() {
        if (state_ == ServiceState::Failed) {
            throw runtime_error(
                "Cannot start failed service before diagnosis: " + name_
            );
        }

        state_ = ServiceState::Running;
    }

    void stop() {
        state_ = ServiceState::Stopped;
    }

    void restart() {
        stop();
        start();
    }

    void enable() {
        enabled_ = true;
    }

    bool enabled() const {
        return enabled_;
    }

    ServiceState state() const {
        return state_;
    }

    void print() const {
        cout << left
             << setw(12) << name_
             << "state=" << setw(9) << serviceStateText(state_)
             << "enabled=" << yesNo(enabled_)
             << "\n";
    }
};


class ServiceManager {
private:
    map<string, Service> services_;

public:
    void registerService(
        const string& name,
        const string& description
    ) {
        services_.emplace(
            piecewise_construct,
            forward_as_tuple(name),
            forward_as_tuple(name, description)
        );
    }

    Service& service(const string& name) {
        auto iterator = services_.find(name);

        if (iterator == services_.end()) {
            throw runtime_error("Unknown service: " + name);
        }

        return iterator->second;
    }

    const Service& service(const string& name) const {
        auto iterator = services_.find(name);

        if (iterator == services_.end()) {
            throw runtime_error("Unknown service: " + name);
        }

        return iterator->second;
    }

    void print() const {
        for (const auto& [name, service] : services_) {
            service.print();
        }
    }
};


// ---------------------------------------------------------------------------
// SSH configuration
// ---------------------------------------------------------------------------

class SSHConfiguration {
private:
    int port_;
    bool passwordAuthentication_;
    bool publicKeyAuthentication_;
    bool directRootLogin_;
    int maxAuthenticationAttempts_;
    set<string> allowedUsers_;

public:
    SSHConfiguration()
        : port_(22),
          passwordAuthentication_(false),
          publicKeyAuthentication_(true),
          directRootLogin_(false),
          maxAuthenticationAttempts_(3) {}

    void allowUser(const string& username) {
        allowedUsers_.insert(username);
    }

    vector<string> validate() const {
        vector<string> errors;

        if (port_ < 1 || port_ > 65535) {
            errors.push_back("SSH port is outside the valid TCP port range.");
        }

        if (!publicKeyAuthentication_ && !passwordAuthentication_) {
            errors.push_back("No SSH authentication mechanism is enabled.");
        }

        if (directRootLogin_) {
            errors.push_back("Direct root SSH login is enabled.");
        }

        if (maxAuthenticationAttempts_ < 1) {
            errors.push_back("Max authentication attempts is invalid.");
        }

        return errors;
    }

    void print() const {
        cout << "Port " << port_ << "\n";
        cout << "PasswordAuthentication "
             << (passwordAuthentication_ ? "yes" : "no") << "\n";
        cout << "PubkeyAuthentication "
             << (publicKeyAuthentication_ ? "yes" : "no") << "\n";
        cout << "PermitRootLogin "
             << (directRootLogin_ ? "yes" : "no") << "\n";
        cout << "MaxAuthTries "
             << maxAuthenticationAttempts_ << "\n";

        if (!allowedUsers_.empty()) {
            cout << "AllowUsers ";

            bool first = true;

            for (const auto& user : allowedUsers_) {
                if (!first) {
                    cout << " ";
                }

                cout << user;
                first = false;
            }

            cout << "\n";
        }
    }
};


// ---------------------------------------------------------------------------
// Firewall
// ---------------------------------------------------------------------------

struct FirewallRule {
    int port;
    string protocol;
    string reason;
};


class Firewall {
private:
    vector<FirewallRule> rules_;
    string defaultIncomingPolicy_ = "deny";

public:
    void allow(
        int port,
        const string& protocol,
        const string& reason
    ) {
        if (port < 1 || port > 65535) {
            throw runtime_error("Invalid firewall port.");
        }

        rules_.push_back({port, protocol, reason});
    }

    bool allows(int port, const string& protocol) const {
        return any_of(
            rules_.begin(),
            rules_.end(),
            [port, &protocol](const FirewallRule& rule) {
                return rule.port == port &&
                       rule.protocol == protocol;
            }
        );
    }

    void print() const {
        cout << "Default incoming policy: "
             << defaultIncomingPolicy_ << "\n";

        for (const auto& rule : rules_) {
            cout << "  "
                 << rule.protocol
                 << "/"
                 << rule.port
                 << " -> "
                 << rule.reason
                 << "\n";
        }
    }
};


// ---------------------------------------------------------------------------
// Audit logging
// ---------------------------------------------------------------------------

enum class Severity {
    Info,
    Warning,
    Error
};

string severityText(Severity severity) {
    switch (severity) {
        case Severity::Info:
            return "INFO";

        case Severity::Warning:
            return "WARN";

        case Severity::Error:
            return "ERROR";
    }

    return "UNKNOWN";
}


struct LogEvent {
    string service;
    Severity severity;
    string message;
    chrono::system_clock::time_point timestamp;
};


class AuditLogger {
private:
    vector<LogEvent> events_;

public:
    void record(
        const string& service,
        Severity severity,
        const string& message
    ) {
        events_.push_back({
            service,
            severity,
            message,
            chrono::system_clock::now()
        });
    }

    void print() const {
        for (const auto& event : events_) {
            const auto time =
                chrono::system_clock::to_time_t(event.timestamp);

            cout << put_time(
                localtime(&time),
                "%Y-%m-%d %H:%M:%S"
            );

            cout << " "
                 << left
                 << setw(10) << event.service
                 << setw(8) << severityText(event.severity)
                 << event.message
                 << "\n";
        }
    }
};


// ---------------------------------------------------------------------------
// Monitoring
// ---------------------------------------------------------------------------

class ServerMetrics {
private:
    double cpuPercent_ = 0.0;
    double memoryPercent_ = 0.0;
    double diskPercent_ = 0.0;

public:
    void update(
        double cpu,
        double memory,
        double disk
    ) {
        cpuPercent_ = cpu;
        memoryPercent_ = memory;
        diskPercent_ = disk;
    }

    string health() const {
        if (
            diskPercent_ >= 95.0 ||
            memoryPercent_ >= 95.0 ||
            cpuPercent_ >= 99.0
        ) {
            return "critical";
        }

        if (
            diskPercent_ >= 85.0 ||
            memoryPercent_ >= 85.0 ||
            cpuPercent_ >= 90.0
        ) {
            return "warning";
        }

        return "healthy";
    }

    void print() const {
        cout << fixed << setprecision(1);
        cout << "CPU: " << cpuPercent_ << "%\n";
        cout << "Memory: " << memoryPercent_ << "%\n";
        cout << "Disk: " << diskPercent_ << "%\n";
        cout << "Health: " << health() << "\n";
    }
};


// ---------------------------------------------------------------------------
// Backup policy
// ---------------------------------------------------------------------------

class BackupPolicy {
private:
    string source_;
    string destination_;
    int retentionDays_;
    bool encryptionRequired_;

public:
    BackupPolicy(
        string source,
        string destination,
        int retentionDays,
        bool encryptionRequired
    )
        : source_(move(source)),
          destination_(move(destination)),
          retentionDays_(retentionDays),
          encryptionRequired_(encryptionRequired) {}

    vector<string> validate() const {
        vector<string> errors;

        if (source_.empty()) {
            errors.push_back("Backup source is empty.");
        }

        if (destination_.empty()) {
            errors.push_back("Backup destination is empty.");
        }

        if (retentionDays_ < 1) {
            errors.push_back("Retention must be positive.");
        }

        if (!encryptionRequired_) {
            errors.push_back("Backup encryption is not required.");
        }

        return errors;
    }

    void print() const {
        cout << "Source: " << source_ << "\n";
        cout << "Destination: " << destination_ << "\n";
        cout << "Retention: " << retentionDays_ << " days\n";
        cout << "Encryption required: "
             << yesNo(encryptionRequired_)
             << "\n";
    }
};


// ---------------------------------------------------------------------------
// Desired state
// ---------------------------------------------------------------------------

struct DesiredConfiguration {
    set<string> requiredUsers;
    set<string> requiredPackages;
    set<string> requiredServices;
};


class LinuxServer {
private:
    string hostname_;
    UserManager users_;
    PackageManager packages_;
    ServiceManager services_;
    SSHConfiguration ssh_;
    Firewall firewall_;
    AuditLogger audit_;
    ServerMetrics metrics_;
    BackupPolicy backup_;

public:
    LinuxServer(
        string hostname,
        BackupPolicy backup
    )
        : hostname_(move(hostname)),
          backup_(move(backup)) {}

    UserManager& users() {
        return users_;
    }

    PackageManager& packages() {
        return packages_;
    }

    ServiceManager& services() {
        return services_;
    }

    SSHConfiguration& ssh() {
        return ssh_;
    }

    Firewall& firewall() {
        return firewall_;
    }

    AuditLogger& audit() {
        return audit_;
    }

    ServerMetrics& metrics() {
        return metrics_;
    }

    const string& hostname() const {
        return hostname_;
    }

    void printStatus() const {
        cout << "Hostname: " << hostname_ << "\n";

        cout << "\nUsers:\n";
        users_.printUsers();

        cout << "\nInstalled packages:\n";
        packages_.print();

        cout << "\nServices:\n";
        services_.print();

        cout << "\nSSH:\n";
        ssh_.print();

        cout << "\nFirewall:\n";
        firewall_.print();

        cout << "\nMonitoring:\n";
        metrics_.print();

        cout << "\nBackup policy:\n";
        backup_.print();
    }
};


// ---------------------------------------------------------------------------
// Desired-state comparison
// ---------------------------------------------------------------------------

vector<string> calculateChanges(
    const LinuxServer& server,
    const DesiredConfiguration& desired
) {
    vector<string> changes;

    for (const auto& username : desired.requiredUsers) {
        try {
            server.users().user(username);
        } catch (const runtime_error&) {
            changes.push_back("Create user: " + username);
        }
    }

    for (const auto& package : desired.requiredPackages) {
        if (!server.packages().installed(package)) {
            changes.push_back("Install package: " + package);
        }
    }

    for (const auto& service : desired.requiredServices) {
        try {
            const auto& instance = server.services().service(service);

            if (!instance.enabled()) {
                changes.push_back("Enable service: " + service);
            }
        } catch (const runtime_error&) {
            changes.push_back("Register service: " + service);
        }
    }

    return changes;
}


// ---------------------------------------------------------------------------
// Case study construction
// ---------------------------------------------------------------------------

LinuxServer buildProductionServer() {
    BackupPolicy backup(
        "/etc/application",
        "/backup/application",
        30,
        true
    );

    LinuxServer server(
        "production-app-01",
        backup
    );

    // User and group design.
    server.users().createGroup("developers");
    server.users().createGroup("operations");
    server.users().createGroup("auditors");

    server.users().createUser(
        "alice",
        1000,
        "developers"
    );

    server.users().createUser(
        "serveradmin",
        1001,
        "operations"
    );

    server.users().addToGroup("alice", "operations");
    server.users().addToGroup("alice", "auditors");
    server.users().addToGroup("serveradmin", "auditors");

    // SSH policy.
    server.ssh().allowUser("alice");
    server.ssh().allowUser("serveradmin");

    // Package inventory.
    server.packages().addPackage("openssh-server", "9.x");
    server.packages().addPackage("nginx", "1.x");
    server.packages().addPackage("python3", "3.x");
    server.packages().addPackage("git", "2.x");

    server.packages().install("openssh-server");
    server.packages().install("nginx");
    server.packages().install("python3");

    // Service architecture.
    server.services().registerService(
        "ssh",
        "OpenSSH server"
    );

    server.services().registerService(
        "nginx",
        "HTTP server"
    );

    server.services().registerService(
        "cron",
        "Scheduled task service"
    );

    server.services().service("ssh").start();
    server.services().service("ssh").enable();

    server.services().service("nginx").start();
    server.services().service("nginx").enable();

    // Firewall policy.
    server.firewall().allow(
        22,
        "tcp",
        "SSH administration"
    );

    server.firewall().allow(
        80,
        "tcp",
        "HTTP"
    );

    server.firewall().allow(
        443,
        "tcp",
        "HTTPS"
    );

    // Monitoring baseline.
    server.metrics().update(
        31.5,
        48.2,
        61.0
    );

    // Audit trail.
    server.audit().record(
        "systemd",
        Severity::Info,
        "Server initialization completed"
    );

    server.audit().record(
        "sshd",
        Severity::Info,
        "Public-key authentication policy enabled"
    );

    server.audit().record(
        "nginx",
        Severity::Info,
        "Web service started"
    );

    return server;
}


// ---------------------------------------------------------------------------
// Demonstrations
// ---------------------------------------------------------------------------

void demonstrateUserAdministration(LinuxServer& server) {
    section("1. User and group administration");

    server.users().user("alice").print();

    cout << "\nEquivalent Linux commands:\n";
    cout << "  sudo groupadd developers\n";
    cout << "  sudo useradd -m -s /bin/bash alice\n";
    cout << "  sudo usermod -aG operations alice\n";
    cout << "  id alice\n";
    cout << "  groups alice\n";
}

void demonstratePermissions(LinuxServer& server) {
    section("2. File permission design");

    FileEntry applicationFile(
        "/srv/application/deploy.sh",
        "alice",
        "developers",
        Permission{true, true, true},
        Permission{true, true, false},
        Permission{false, false, false}
    );

    applicationFile.print();

    const auto& alice = server.users().user("alice");
    const Permission effective =
        applicationFile.effectivePermission(alice);

    cout << "\nAlice effective permissions: "
         << effective.symbolic()
         << "\n";

    cout << "Equivalent command: chmod "
         << applicationFile.numericMode()
         << " /srv/application/deploy.sh\n";

    cout << "Ownership command: "
         << "chown alice:developers /srv/application/deploy.sh\n";

    cout << "\nSecurity interpretation:\n";
    cout << "  Owner: read/write/execute\n";
    cout << "  Group: read/write\n";
    cout << "  Other: no access\n";
}

void demonstrateSSH(LinuxServer& server) {
    section("3. SSH administration");

    server.ssh().print();

    const vector<string> errors = server.ssh().validate();

    if (errors.empty()) {
        cout << "\nSSH configuration validation: PASS\n";
    } else {
        cout << "\nSSH configuration validation: FAIL\n";

        for (const auto& error : errors) {
            cout << "  - " << error << "\n";
        }
    }

    cout << "\nTypical workflow:\n";
    cout << "  ssh-keygen -t ed25519\n";
    cout << "  ssh-copy-id alice@server\n";
    cout << "  ssh alice@server\n";
}

void demonstratePackages(LinuxServer& server) {
    section("4. Package management");

    cout << "Package database:\n";
    server.packages().print();

    cout << "\nRepresentative Debian/Ubuntu commands:\n";
    cout << "  sudo apt update\n";
    cout << "  sudo apt upgrade\n";
    cout << "  sudo apt install nginx\n";
    cout << "  sudo apt remove nginx\n";

    cout << "\nThe exact package manager depends on the Linux distribution.\n";
}

void demonstrateServices(LinuxServer& server) {
    section("5. Service management");

    server.services().print();

    cout << "\nTypical systemd commands:\n";
    cout << "  systemctl status nginx\n";
    cout << "  sudo systemctl start nginx\n";
    cout << "  sudo systemctl stop nginx\n";
    cout << "  sudo systemctl restart nginx\n";
    cout << "  sudo systemctl enable nginx\n";
    cout << "  sudo systemctl disable nginx\n";
    cout << "  journalctl -u nginx\n";
}

void demonstrateFirewall(LinuxServer& server) {
    section("6. Firewall design");

    server.firewall().print();

    cout << "\nDesign principle:\n";
    cout << "Only expose ports required by the application.\n";
    cout << "A default-deny incoming policy reduces unnecessary exposure.\n";
}

void demonstrateDesiredState(LinuxServer& server) {
    section("7. Desired-state validation");

    DesiredConfiguration desired;

    desired.requiredUsers = {
        "alice",
        "serveradmin"
    };

    desired.requiredPackages = {
        "openssh-server",
        "nginx",
        "python3",
        "git"
    };

    desired.requiredServices = {
        "ssh",
        "nginx"
    };

    const vector<string> changes =
        calculateChanges(server, desired);

    if (changes.empty()) {
        cout << "Server matches desired state.\n";
    } else {
        cout << "Changes required:\n";

        for (const auto& change : changes) {
            cout << "  - " << change << "\n";
        }
    }

    cout << "\nIdempotence means that once the desired state has been reached,\n";
    cout << "running the same configuration logic again should not create\n";
    cout << "unnecessary additional changes.\n";
}

void demonstrateMonitoring(LinuxServer& server) {
    section("8. Monitoring");

    server.metrics().print();

    cout << "\nImportant metrics:\n";
    cout << "  CPU utilization\n";
    cout << "  Memory utilization\n";
    cout << "  Disk utilization\n";
    cout << "  Load average\n";
    cout << "  Network throughput\n";
    cout << "  Service availability\n";
    cout << "  Process counts\n";
}

void demonstrateAuditLogging(LinuxServer& server) {
    section("9. Audit logging");

    server.audit().record(
        "sshd",
        Severity::Warning,
        "Example failed authentication event"
    );

    server.audit().record(
        "backup",
        Severity::Error,
        "Example backup destination failure"
    );

    server.audit().print();

    cout << "\nLogs should support:\n";
    cout << "  event reconstruction\n";
    cout << "  incident investigation\n";
    cout << "  operational troubleshooting\n";
    cout << "  security auditing\n";
}

void demonstrateBackup() {
    section("10. Backup policy");

    BackupPolicy policy(
        "/var/lib/application",
        "/backup/application",
        30,
        true
    );

    const vector<string> errors = policy.validate();

    policy.print();

    if (errors.empty()) {
        cout << "\nBackup policy validation: PASS\n";
    } else {
        cout << "\nBackup policy validation: FAIL\n";

        for (const auto& error : errors) {
            cout << "  - " << error << "\n";
        }
    }

    cout << "\nA backup is useful only if restoration has been tested.\n";
}

void demonstrateTroubleshooting() {
    section("11. Troubleshooting methodology");

    const map<string, vector<string>> troubleshooting = {
        {
            "SSH connection failure",
            {
                "Check network reachability.",
                "Check IP configuration and routing.",
                "Check sshd service state.",
                "Check listening sockets.",
                "Check firewall rules.",
                "Validate SSH configuration.",
                "Inspect authentication logs."
            }
        },
        {
            "Permission denied",
            {
                "Inspect file ownership.",
                "Inspect rwx permissions.",
                "Check user identity.",
                "Check group membership.",
                "Check parent directory traversal.",
                "Check ACLs.",
                "Check mandatory access controls."
            }
        },
        {
            "Service failure",
            {
                "Run systemctl status SERVICE.",
                "Read journalctl -u SERVICE.",
                "Validate configuration syntax.",
                "Check dependencies.",
                "Check port conflicts.",
                "Check storage and memory."
            }
        }
    };

    for (const auto& [problem, steps] : troubleshooting) {
        cout << "\n" << problem << ":\n";

        for (size_t i = 0; i < steps.size(); ++i) {
            cout << "  " << (i + 1)
                 << ". " << steps[i] << "\n";
        }
    }
}

void demonstrateCommandReference() {
    section("12. Linux command reference");

    const vector<pair<string, string>> commands = {
        {"Identity", "id"},
        {"Current user", "whoami"},
        {"Users", "getent passwd"},
        {"Groups", "getent group"},
        {"Processes", "ps aux"},
        {"Sockets", "ss -tulpn"},
        {"Disk", "df -h"},
        {"Directory usage", "du -sh /path"},
        {"Permissions", "ls -l"},
        {"Change permissions", "chmod 640 file"},
        {"Change ownership", "chown user:group file"},
        {"Package update", "sudo apt update"},
        {"Package install", "sudo apt install package"},
        {"Service status", "systemctl status service"},
        {"Service start", "sudo systemctl start service"},
        {"Service enable", "sudo systemctl enable service"},
        {"Service logs", "journalctl -u service"},
        {"SSH key generation", "ssh-keygen -t ed25519"},
        {"Scheduled jobs", "crontab -e"}
    };

    for (const auto& [purpose, cmd] : commands) {
        cout << left
             << setw(24)
             << purpose
             << cmd
             << "\n";
    }
}


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void runTests(LinuxServer& server) {
    section("13. Tests");

    int passed = 0;
    int total = 0;

    auto test = [&](const string& name, const auto& function) {
        ++total;

        try {
            function();
            cout << "PASS " << name << "\n";
            ++passed;
        } catch (const exception& error) {
            cout << "FAIL " << name
                 << ": " << error.what() << "\n";
        }
    };

    test("user exists", [&]() {
        assert(server.users().user("alice").uid() == 1000);
    });

    test("group membership", [&]() {
        assert(
            server.users()
                .user("alice")
                .groups()
                .count("operations") == 1
        );
    });

    test("SSH policy", [&]() {
        assert(server.ssh().validate().empty());
    });

    test("Nginx installed", [&]() {
        assert(server.packages().installed("nginx"));
    });

    test("Nginx running", [&]() {
        assert(
            server.services()
                .service("nginx")
                .state() == ServiceState::Running
        );
    });

    test("SSH firewall rule", [&]() {
        assert(server.firewall().allows(22, "tcp"));
    });

    cout << "\n"
         << passed
         << "/"
         << total
         << " tests passed.\n";
}


// ---------------------------------------------------------------------------
// Main case study
// ---------------------------------------------------------------------------

int main() {
    try {
        cout << "Linux Administration Case Study\n";
        cout << "Production Web Server Administration Simulation\n";

        LinuxServer server = buildProductionServer();

        demonstrateUserAdministration(server);
        demonstratePermissions(server);
        demonstrateSSH(server);
        demonstratePackages(server);
        demonstrateServices(server);
        demonstrateFirewall(server);
        demonstrateDesiredState(server);
        demonstrateMonitoring(server);
        demonstrateAuditLogging(server);
        demonstrateBackup();
        demonstrateTroubleshooting();
        demonstrateCommandReference();
        runTests(server);

        section("14. Integrated server state");

        server.printStatus();

        section("15. Administrative architecture");

        cout << "Users and groups\n";
        cout << "      |\n";
        cout << "      +--> File ownership and permissions\n";
        cout << "      |\n";
        cout << "      +--> SSH authentication\n";
        cout << "      |\n";
        cout << "      +--> Administrative roles\n";
        cout << "\n";

        cout << "Packages\n";
        cout << "      |\n";
        cout << "      +--> Installed software\n";
        cout << "      |\n";
        cout << "      +--> Services\n";
        cout << "\n";

        cout << "Services\n";
        cout << "      |\n";
        cout << "      +--> systemd supervision\n";
        cout << "      |\n";
        cout << "      +--> Logs\n";
        cout << "      |\n";
        cout << "      +--> Monitoring\n";
        cout << "\n";

        cout << "Network\n";
        cout << "      |\n";
        cout << "      +--> Firewall\n";
        cout << "      |\n";
        cout << "      +--> Listening ports\n";
        cout << "      |\n";
        cout << "      +--> Remote access\n";

        section("16. Administrative principles");

        const vector<string> principles = {
            "Least privilege",
            "Defense in depth",
            "Minimal attack surface",
            "Explicit configuration",
            "Idempotent automation",
            "Observability",
            "Test before production",
            "Backups and restoration testing",
            "Patch management",
            "Documented changes",
            "Separation of duties",
            "Controlled remote access"
        };

        for (size_t i = 0; i < principles.size(); ++i) {
            cout << setw(2) << (i + 1)
                 << ". "
                 << principles[i]
                 << "\n";
        }

        return 0;
    } catch (const exception& error) {
        cerr << "Fatal error: "
             << error.what()
             << "\n";

        return 1;
    }
}
