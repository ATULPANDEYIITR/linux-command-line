"use strict";

/*
 * Linux Administration Project
 *
 * This JavaScript file complements the Python implementation by modelling
 * Linux administration concepts as application-level objects and workflows.
 *
 * The program is deliberately safe: it generates and validates administrative
 * plans instead of modifying the host operating system.
 *
 * Topics demonstrated:
 *   - Users and groups
 *   - File permissions
 *   - SSH policy
 *   - Package management
 *   - Services
 *   - Desired state
 *   - Idempotence
 *   - Configuration validation
 *   - Logging
 *   - Backup planning
 *   - Automation
 *   - Monitoring
 *   - Troubleshooting
 *   - Security hardening
 *
 * Run with:
 *
 *   node linux-administration-project.js
 */


// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

function section(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function subsection(title) {
    console.log("\n" + "-".repeat(78));
    console.log(title);
    console.log("-".repeat(78));
}

function command(...parts) {
    return parts
        .map(part => {
            const text = String(part);
            return /\s/.test(text) ? `"${text.replaceAll('"', '\\"')}"` : text;
        })
        .join(" ");
}

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function isValidUsername(username) {
    return /^[a-z_][a-z0-9_-]{0,31}$/.test(username);
}


// ---------------------------------------------------------------------------
// Users and groups
// ---------------------------------------------------------------------------

class LinuxUser {
    constructor({
        username,
        uid,
        primaryGroup,
        homeDirectory = null,
        shell = "/bin/bash",
    }) {
        if (!isValidUsername(username)) {
            throw new Error(`Invalid Linux username: ${username}`);
        }

        this.username = username;
        this.uid = uid;
        this.primaryGroup = primaryGroup;
        this.groups = new Set([primaryGroup]);
        this.homeDirectory = homeDirectory ?? `/home/${username}`;
        this.shell = shell;
        this.locked = false;
        this.authorizedKeys = [];
    }

    addGroup(group) {
        this.groups.add(group);
    }

    lock() {
        this.locked = true;
    }

    unlock() {
        this.locked = false;
    }
}

class UserDirectory {
    constructor() {
        this.users = new Map();
        this.groups = new Map();

        this.addGroup("root");
        this.addUser({
            username: "root",
            uid: 0,
            primaryGroup: "root",
            homeDirectory: "/root",
        });
    }

    addGroup(group) {
        if (!/^[a-z_][a-z0-9_-]{0,31}$/.test(group)) {
            throw new Error(`Invalid group name: ${group}`);
        }

        if (this.groups.has(group)) {
            throw new Error(`Group already exists: ${group}`);
        }

        this.groups.set(group, new Set());
    }

    addUser(options) {
        if (this.users.has(options.username)) {
            throw new Error(`User already exists: ${options.username}`);
        }

        if (!this.groups.has(options.primaryGroup)) {
            this.addGroup(options.primaryGroup);
        }

        const user = new LinuxUser(options);
        this.users.set(user.username, user);
        this.groups.get(user.primaryGroup).add(user.username);

        return user;
    }

    addUserToGroup(username, group) {
        const user = this.users.get(username);

        if (!user) {
            throw new Error(`Unknown user: ${username}`);
        }

        if (!this.groups.has(group)) {
            throw new Error(`Unknown group: ${group}`);
        }

        user.addGroup(group);
        this.groups.get(group).add(username);
    }

    describe(username) {
        const user = this.users.get(username);

        if (!user) {
            throw new Error(`Unknown user: ${username}`);
        }

        return {
            username: user.username,
            uid: user.uid,
            groups: [...user.groups].sort(),
            home: user.homeDirectory,
            shell: user.shell,
            locked: user.locked,
        };
    }
}


// ---------------------------------------------------------------------------
// File permissions
// ---------------------------------------------------------------------------

class PermissionSet {
    constructor(read = false, write = false, execute = false) {
        this.read = read;
        this.write = write;
        this.execute = execute;
    }

    numeric() {
        return (
            (this.read ? 4 : 0) +
            (this.write ? 2 : 0) +
            (this.execute ? 1 : 0)
        );
    }

    symbolic() {
        return (
            `${this.read ? "r" : "-"}`
            + `${this.write ? "w" : "-"}`
            + `${this.execute ? "x" : "-"}`
        );
    }
}

class FilePermission {
    constructor({
        owner,
        group,
        ownerPermission,
        groupPermission,
        otherPermission,
        directory = false,
    }) {
        this.owner = owner;
        this.group = group;
        this.ownerPermission = ownerPermission;
        this.groupPermission = groupPermission;
        this.otherPermission = otherPermission;
        this.directory = directory;
    }

    symbolic() {
        const prefix = this.directory ? "d" : "-";

        return (
            prefix
            + this.ownerPermission.symbolic()
            + this.groupPermission.symbolic()
            + this.otherPermission.symbolic()
        );
    }

    numeric() {
        return (
            this.ownerPermission.numeric() * 100
            + this.groupPermission.numeric() * 10
            + this.otherPermission.numeric()
        );
    }

    effectiveFor(username, groups) {
        if (username === this.owner) {
            return this.ownerPermission;
        }

        if (groups.has(this.group)) {
            return this.groupPermission;
        }

        return this.otherPermission;
    }
}


// ---------------------------------------------------------------------------
// SSH policy
// ---------------------------------------------------------------------------

class SSHPolicy {
    constructor({
        port = 22,
        rootLogin = "prohibit-password",
        passwordAuthentication = false,
        publicKeyAuthentication = true,
        maxAuthenticationAttempts = 3,
        allowedUsers = [],
    } = {}) {
        this.port = port;
        this.rootLogin = rootLogin;
        this.passwordAuthentication = passwordAuthentication;
        this.publicKeyAuthentication = publicKeyAuthentication;
        this.maxAuthenticationAttempts = maxAuthenticationAttempts;
        this.allowedUsers = new Set(allowedUsers);
    }

    validate() {
        const errors = [];

        if (this.port < 1 || this.port > 65535) {
            errors.push("SSH port must be between 1 and 65535.");
        }

        if (this.maxAuthenticationAttempts < 1) {
            errors.push("Authentication attempts must be positive.");
        }

        if (this.rootLogin === "yes") {
            errors.push("Direct root SSH login is explicitly permitted.");
        }

        if (!this.passwordAuthentication && !this.publicKeyAuthentication) {
            errors.push("No SSH authentication mechanism is enabled.");
        }

        if (this.passwordAuthentication && !this.publicKeyAuthentication) {
            errors.push(
                "Password-only SSH authentication requires additional controls."
            );
        }

        return errors;
    }

    toConfigText() {
        const lines = [
            `Port ${this.port}`,
            `PermitRootLogin ${this.rootLogin}`,
            `PasswordAuthentication ${this.passwordAuthentication ? "yes" : "no"}`,
            `PubkeyAuthentication ${this.publicKeyAuthentication ? "yes" : "no"}`,
            `MaxAuthTries ${this.maxAuthenticationAttempts}`,
        ];

        if (this.allowedUsers.size > 0) {
            lines.push(`AllowUsers ${[...this.allowedUsers].sort().join(" ")}`);
        }

        return lines.join("\n");
    }
}


// ---------------------------------------------------------------------------
// Package management
// ---------------------------------------------------------------------------

class PackageManager {
    constructor(type = "apt") {
        const valid = new Set(["apt", "dnf", "yum", "pacman"]);

        if (!valid.has(type)) {
            throw new Error(`Unsupported package manager: ${type}`);
        }

        this.type = type;
        this.packages = new Map();
    }

    addPackage(name, version) {
        this.packages.set(name, {
            name,
            version,
            installed: false,
        });
    }

    install(name) {
        const packageEntry = this.packages.get(name);

        if (!packageEntry) {
            throw new Error(`Package is not in the simulated repository: ${name}`);
        }

        packageEntry.installed = true;
    }

    installCommand(name) {
        switch (this.type) {
            case "apt":
                return command("sudo", "apt", "install", "-y", name);
            case "dnf":
                return command("sudo", "dnf", "install", "-y", name);
            case "yum":
                return command("sudo", "yum", "install", "-y", name);
            case "pacman":
                return command("sudo", "pacman", "-S", name);
            default:
                throw new Error("Unsupported package manager.");
        }
    }

    updateCommand() {
        switch (this.type) {
            case "apt":
                return "sudo apt update";
            case "dnf":
                return "sudo dnf makecache";
            case "yum":
                return "sudo yum makecache";
            case "pacman":
                return "sudo pacman -Sy";
            default:
                throw new Error("Unsupported package manager.");
        }
    }
}


// ---------------------------------------------------------------------------
// Service management
// ---------------------------------------------------------------------------

const ServiceState = Object.freeze({
    STOPPED: "stopped",
    RUNNING: "running",
    FAILED: "failed",
});

class Service {
    constructor(name, description = "") {
        this.name = name;
        this.description = description;
        this.state = ServiceState.STOPPED;
        this.enabled = false;
    }

    start() {
        if (this.state === ServiceState.FAILED) {
            throw new Error(
                `${this.name} is failed and requires diagnosis before restart.`
            );
        }

        this.state = ServiceState.RUNNING;
    }

    stop() {
        this.state = ServiceState.STOPPED;
    }

    restart() {
        this.stop();
        this.start();
    }

    enable() {
        this.enabled = true;
    }

    disable() {
        this.enabled = false;
    }
}

class ServiceManager {
    constructor() {
        this.services = new Map();
    }

    register(service) {
        this.services.set(service.name, service);
    }

    status(name) {
        const service = this.services.get(name);

        if (!service) {
            throw new Error(`Unknown service: ${name}`);
        }

        return service;
    }

    systemctlCommands(name) {
        return [
            `systemctl status ${name}`,
            `sudo systemctl start ${name}`,
            `sudo systemctl stop ${name}`,
            `sudo systemctl restart ${name}`,
            `sudo systemctl enable ${name}`,
            `sudo systemctl disable ${name}`,
            `journalctl -u ${name}`,
        ];
    }
}


// ---------------------------------------------------------------------------
// Desired state and idempotence
// ---------------------------------------------------------------------------

class DesiredState {
    constructor() {
        this.users = new Map();
        this.packages = new Set();
        this.services = new Set();
    }

    ensureUser(username, groups = []) {
        this.users.set(username, new Set(groups));
    }

    ensurePackage(packageName) {
        this.packages.add(packageName);
    }

    ensureService(serviceName) {
        this.services.add(serviceName);
    }
}

function calculateChanges(desired, users, packages, services) {
    const changes = [];

    for (const [username, desiredGroups] of desired.users) {
        if (!users.users.has(username)) {
            changes.push(`Create user ${username}`);
            continue;
        }

        const actualUser = users.users.get(username);

        for (const group of desiredGroups) {
            if (!actualUser.groups.has(group)) {
                changes.push(`Add ${username} to group ${group}`);
            }
        }
    }

    for (const packageName of desired.packages) {
        const packageEntry = packages.packages.get(packageName);

        if (!packageEntry) {
            changes.push(`Package unavailable: ${packageName}`);
        } else if (!packageEntry.installed) {
            changes.push(`Install package ${packageName}`);
        }
    }

    for (const serviceName of desired.services) {
        const service = services.services.get(serviceName);

        if (!service) {
            changes.push(`Unknown service: ${serviceName}`);
        } else if (!service.enabled) {
            changes.push(`Enable service ${serviceName}`);
        }
    }

    return changes;
}


// ---------------------------------------------------------------------------
// Logging
// ---------------------------------------------------------------------------

class AuditLogger {
    constructor() {
        this.events = [];
    }

    log(service, severity, message) {
        this.events.push({
            timestamp: new Date().toISOString(),
            service,
            severity,
            message,
        });
    }

    filter(severity) {
        return this.events.filter(event => event.severity === severity);
    }

    print() {
        for (const event of this.events) {
            console.log(
                `${event.timestamp} `
                + `${event.service.padEnd(10)} `
                + `${event.severity.padEnd(8)} `
                + event.message
            );
        }
    }
}


// ---------------------------------------------------------------------------
// Backup planning
// ---------------------------------------------------------------------------

class BackupPlan {
    constructor({
        source,
        destination,
        retentionDays,
        encryptionRequired,
    }) {
        this.source = source;
        this.destination = destination;
        this.retentionDays = retentionDays;
        this.encryptionRequired = encryptionRequired;
    }

    validate() {
        const errors = [];

        if (!this.source) {
            errors.push("Backup source is empty.");
        }

        if (!this.destination) {
            errors.push("Backup destination is empty.");
        }

        if (this.retentionDays < 1) {
            errors.push("Retention must be at least one day.");
        }

        if (!this.encryptionRequired) {
            errors.push("Backup encryption is not required.");
        }

        return errors;
    }
}


// ---------------------------------------------------------------------------
// Monitoring
// ---------------------------------------------------------------------------

class ServerMetrics {
    constructor() {
        this.cpuPercent = 0;
        this.memoryPercent = 0;
        this.diskPercent = 0;
        this.loadAverage = 0;
    }

    update({ cpuPercent, memoryPercent, diskPercent, loadAverage }) {
        this.cpuPercent = cpuPercent;
        this.memoryPercent = memoryPercent;
        this.diskPercent = diskPercent;
        this.loadAverage = loadAverage;
    }

    healthStatus() {
        if (
            this.diskPercent >= 95 ||
            this.memoryPercent >= 95 ||
            this.cpuPercent >= 99
        ) {
            return "critical";
        }

        if (
            this.diskPercent >= 85 ||
            this.memoryPercent >= 85 ||
            this.cpuPercent >= 90
        ) {
            return "warning";
        }

        return "healthy";
    }
}


// ---------------------------------------------------------------------------
// Firewall model
// ---------------------------------------------------------------------------

class FirewallPolicy {
    constructor() {
        this.allowedTcpPorts = new Set();
        this.defaultIncomingPolicy = "deny";
    }

    allowTcp(port, reason) {
        if (port < 1 || port > 65535) {
            throw new Error(`Invalid TCP port: ${port}`);
        }

        this.allowedTcpPorts.add({
            port,
            reason,
        });
    }

    rules() {
        return [...this.allowedTcpPorts];
    }
}


// ---------------------------------------------------------------------------
// Server model
// ---------------------------------------------------------------------------

class LinuxServer {
    constructor(hostname) {
        this.hostname = hostname;
        this.users = new UserDirectory();
        this.packages = new PackageManager("apt");
        this.services = new ServiceManager();
        this.ssh = new SSHPolicy();
        this.firewall = new FirewallPolicy();
        this.logger = new AuditLogger();
        this.metrics = new ServerMetrics();
    }

    securityValidation() {
        const errors = [];

        errors.push(...this.ssh.validate());

        if (this.firewall.defaultIncomingPolicy !== "deny") {
            errors.push("Firewall default incoming policy is not deny.");
        }

        if (!this.firewall.allowedTcpPorts.some(rule => rule.port === 22)) {
            errors.push("SSH is not explicitly represented in firewall policy.");
        }

        return errors;
    }

    report() {
        console.log(`Hostname: ${this.hostname}`);

        console.log("\nUsers:");
        for (const user of this.users.users.values()) {
            console.log(
                `  ${user.username.padEnd(15)} `
                + `uid=${String(user.uid).padEnd(5)} `
                + `groups=${[...user.groups].sort().join(",")}`
            );
        }

        console.log("\nPackages:");
        for (const pkg of this.packages.packages.values()) {
            if (pkg.installed) {
                console.log(`  ${pkg.name} ${pkg.version}`);
            }
        }

        console.log("\nServices:");
        for (const service of this.services.services.values()) {
            console.log(
                `  ${service.name.padEnd(12)} `
                + `state=${service.state.padEnd(8)} `
                + `enabled=${service.enabled}`
            );
        }

        console.log("\nSSH configuration:");
        console.log(this.ssh.toConfigText());

        console.log("\nFirewall:");
        for (const rule of this.firewall.rules()) {
            console.log(`  TCP ${rule.port}: ${rule.reason}`);
        }

        console.log(`\nHealth: ${this.metrics.healthStatus()}`);
    }
}


// ---------------------------------------------------------------------------
// Build an example server
// ---------------------------------------------------------------------------

function buildServer() {
    const server = new LinuxServer("app-server-01");

    server.users.addGroup("developers");
    server.users.addGroup("operations");
    server.users.addGroup("auditors");

    server.users.addUser({
        username: "alice",
        uid: 1000,
        primaryGroup: "developers",
    });

    server.users.addUser({
        username: "serveradmin",
        uid: 1001,
        primaryGroup: "operations",
    });

    server.users.addUserToGroup("alice", "operations");
    server.users.addUserToGroup("alice", "auditors");
    server.users.addUserToGroup("serveradmin", "auditors");

    server.users.users.get("alice").authorizedKeys.push(
        "ssh-ed25519 AAAAEXAMPLEKEY alice@example"
    );

    server.ssh = new SSHPolicy({
        port: 22,
        rootLogin: "prohibit-password",
        passwordAuthentication: false,
        publicKeyAuthentication: true,
        maxAuthenticationAttempts: 3,
        allowedUsers: ["serveradmin", "alice"],
    });

    server.packages.addPackage("openssh-server", "9.x");
    server.packages.addPackage("nginx", "1.x");
    server.packages.addPackage("git", "2.x");
    server.packages.addPackage("python3", "3.x");

    server.packages.install("openssh-server");
    server.packages.install("nginx");
    server.packages.install("python3");

    server.services.register(
        new Service("ssh", "OpenSSH server")
    );

    server.services.register(
        new Service("nginx", "Web server")
    );

    server.services.register(
        new Service("cron", "Job scheduler")
    );

    server.services.status("ssh").start();
    server.services.status("ssh").enable();

    server.services.status("nginx").start();
    server.services.status("nginx").enable();

    server.firewall.allowTcp(22, "SSH administration");
    server.firewall.allowTcp(80, "HTTP");
    server.firewall.allowTcp(443, "HTTPS");

    server.metrics.update({
        cpuPercent: 32,
        memoryPercent: 47,
        diskPercent: 61,
        loadAverage: 0.72,
    });

    return server;
}


// ---------------------------------------------------------------------------
// Demonstrations
// ---------------------------------------------------------------------------

function demonstrateUsers(server) {
    section("1. Users and groups");

    console.log(server.users.describe("alice"));

    console.log("\nRepresentative Linux commands:");
    console.log("  sudo groupadd developers");
    console.log("  sudo useradd -m -s /bin/bash alice");
    console.log("  sudo usermod -aG operations alice");
    console.log("  id alice");
    console.log("  groups alice");
}

function demonstratePermissions() {
    section("2. Permissions");

    const permissions = new FilePermission({
        owner: "alice",
        group: "developers",
        ownerPermission: new PermissionSet(true, true, true),
        groupPermission: new PermissionSet(true, true, false),
        otherPermission: new PermissionSet(false, false, false),
    });

    console.log(`Symbolic: ${permissions.symbolic()}`);
    console.log(`Numeric: ${permissions.numeric()}`);

    const aliceGroups = new Set(["developers", "operations"]);

    const effective = permissions.effectiveFor("alice", aliceGroups);

    console.log(
        `Alice effective permissions: ${effective.symbolic()}`
    );

    console.log("\nCommon commands:");
    console.log("  chmod 750 deploy.sh");
    console.log("  chown alice:developers deploy.sh");
    console.log("  chmod u+x deploy.sh");
}

function demonstrateSSH(server) {
    section("3. SSH");

    console.log(server.ssh.toConfigText());

    const errors = server.ssh.validate();

    console.log(
        errors.length === 0
            ? "\nSSH validation: PASS"
            : `\nSSH validation errors:\n${errors.join("\n")}`
    );

    console.log("\nKey workflow:");
    console.log("  ssh-keygen -t ed25519");
    console.log("  ssh-copy-id alice@server");
    console.log("  ssh alice@server");
}

function demonstratePackages(server) {
    section("4. Packages");

    console.log(`Repository metadata command: ${server.packages.updateCommand()}`);
    console.log(
        `Install command: ${server.packages.installCommand("nginx")}`
    );

    for (const pkg of server.packages.packages.values()) {
        console.log(
            `${pkg.name.padEnd(20)} `
            + `${pkg.version.padEnd(5)} `
            + `${pkg.installed ? "installed" : "not installed"}`
        );
    }
}

function demonstrateServices(server) {
    section("5. Services");

    for (const service of server.services.services.values()) {
        console.log(
            `${service.name.padEnd(10)} `
            + `state=${service.state.padEnd(8)} `
            + `enabled=${service.enabled}`
        );
    }

    console.log("\nUseful commands:");
    for (const cmd of server.services.systemctlCommands("nginx")) {
        console.log(`  ${cmd}`);
    }
}

function demonstrateDesiredState(server) {
    section("6. Desired state and idempotence");

    const desired = new DesiredState();

    desired.ensureUser("alice", ["developers", "operations"]);
    desired.ensureUser("serveradmin", ["operations"]);
    desired.ensurePackage("nginx");
    desired.ensurePackage("git");
    desired.ensureService("ssh");
    desired.ensureService("nginx");

    const changes = calculateChanges(
        desired,
        server.users,
        server.packages,
        server.services
    );

    if (changes.length === 0) {
        console.log("No changes required. Server already matches desired state.");
    } else {
        for (const change of changes) {
            console.log(`  ${change}`);
        }
    }
}

function demonstrateLogging(server) {
    section("7. Logging and auditing");

    server.logger.log(
        "sshd",
        "INFO",
        "Accepted public key for alice"
    );

    server.logger.log(
        "nginx",
        "INFO",
        "Worker started"
    );

    server.logger.log(
        "sshd",
        "WARN",
        "Authentication failure"
    );

    server.logger.log(
        "backup",
        "ERROR",
        "Remote backup target unavailable"
    );

    server.logger.print();

    console.log(
        `\nWarnings recorded: ${server.logger.filter("WARN").length}`
    );
}

function demonstrateBackupPlanning() {
    section("8. Backup planning");

    const plan = new BackupPlan({
        source: "/etc/application",
        destination: "/backup/application",
        retentionDays: 30,
        encryptionRequired: true,
    });

    const errors = plan.validate();

    if (errors.length === 0) {
        console.log("Backup plan validation: PASS");
    } else {
        console.log("Backup plan validation: FAIL");
        console.log(errors);
    }

    console.log("\nBackup design considerations:");
    console.log("  Source data");
    console.log("  Destination independence");
    console.log("  Encryption");
    console.log("  Retention");
    console.log("  Restoration testing");
    console.log("  RPO");
    console.log("  RTO");
}

function demonstrateMonitoring(server) {
    section("9. Monitoring");

    console.log(`CPU: ${server.metrics.cpuPercent}%`);
    console.log(`Memory: ${server.metrics.memoryPercent}%`);
    console.log(`Disk: ${server.metrics.diskPercent}%`);
    console.log(`Load average: ${server.metrics.loadAverage}`);
    console.log(`Health state: ${server.metrics.healthStatus()}`);

    console.log("\nLinux commands:");
    console.log("  uptime");
    console.log("  free -h");
    console.log("  df -h");
    console.log("  vmstat");
    console.log("  iostat");
    console.log("  ss -tulpn");
}

function demonstrateTroubleshooting() {
    section("10. Troubleshooting decision process");

    const cases = {
        "SSH unavailable": [
            "Check network interface.",
            "Check routing.",
            "Check whether sshd is running.",
            "Check listening ports.",
            "Check firewall policy.",
            "Check SSH configuration.",
            "Inspect authentication logs.",
        ],
        "Permission denied": [
            "Check ls -l.",
            "Check id USER.",
            "Check group membership.",
            "Check parent-directory traversal permissions.",
            "Check ACLs.",
            "Check security modules.",
        ],
        "Service failed": [
            "systemctl status SERVICE",
            "journalctl -u SERVICE",
            "Validate configuration.",
            "Check ports and dependencies.",
            "Check disk and memory.",
        ],
    };

    for (const [problem, steps] of Object.entries(cases)) {
        console.log(`\n${problem}:`);

        steps.forEach((step, index) => {
            console.log(`  ${index + 1}. ${step}`);
        });
    }
}

function demonstrateSecurity(server) {
    section("11. Security hardening");

    const issues = server.securityValidation();

    if (issues.length === 0) {
        console.log("Security policy validation: PASS");
    } else {
        console.log("Security policy validation: FAIL");

        for (const issue of issues) {
            console.log(`  - ${issue}`);
        }
    }

    console.log("\nCore controls:");
    console.log("  Least privilege");
    console.log("  SSH key authentication");
    console.log("  Firewall");
    console.log("  Package patching");
    console.log("  Minimal services");
    console.log("  File permissions");
    console.log("  Logging");
    console.log("  Backups");
    console.log("  Monitoring");
}

function demonstrateAsyncAutomation(server) {
    section("12. Event-driven automation");

    /*
     * JavaScript is particularly useful for application-level automation
     * because asynchronous operations can be represented with Promises.
     *
     * This example simulates health checks without executing privileged
     * commands.
     */

    const checks = [
        Promise.resolve({
            name: "SSH service",
            healthy: server.services.status("ssh").state === ServiceState.RUNNING,
        }),
        Promise.resolve({
            name: "Nginx service",
            healthy: server.services.status("nginx").state === ServiceState.RUNNING,
        }),
        Promise.resolve({
            name: "Disk usage",
            healthy: server.metrics.diskPercent < 90,
        }),
    ];

    return Promise.all(checks).then(results => {
        for (const result of results) {
            console.log(
                `${result.name.padEnd(20)} `
                + `${result.healthy ? "PASS" : "FAIL"}`
            );
        }

        return results;
    });
}


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

function runTests(server) {
    section("13. Tests");

    const tests = [
        {
            name: "username validation",
            run: () => {
                assert(isValidUsername("alice"), "alice should be valid");
                assert(!isValidUsername("Alice!"), "Alice! should be invalid");
            },
        },
        {
            name: "permission conversion",
            run: () => {
                const permission = new PermissionSet(true, true, false);

                assert(
                    permission.numeric() === 6,
                    "rw- should equal numeric 6"
                );

                assert(
                    permission.symbolic() === "rw-",
                    "Permission should be rw-"
                );
            },
        },
        {
            name: "group membership",
            run: () => {
                const alice = server.users.users.get("alice");

                assert(
                    alice.groups.has("developers"),
                    "Alice should belong to developers"
                );

                assert(
                    alice.groups.has("operations"),
                    "Alice should belong to operations"
                );
            },
        },
        {
            name: "SSH policy",
            run: () => {
                assert(
                    server.ssh.validate().length === 0,
                    "SSH policy should be valid"
                );
            },
        },
        {
            name: "services",
            run: () => {
                assert(
                    server.services.status("nginx").state === ServiceState.RUNNING,
                    "Nginx should be running"
                );
            },
        },
    ];

    let passed = 0;

    for (const test of tests) {
        try {
            test.run();
            console.log(`PASS ${test.name}`);
            passed++;
        } catch (error) {
            console.log(`FAIL ${test.name}: ${error.message}`);
        }
    }

    console.log(`\n${passed}/${tests.length} tests passed.`);
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
    console.log("Linux Administration Project");
    console.log("Application-level administration simulator");

    const server = buildServer();

    demonstrateUsers(server);
    demonstratePermissions();
    demonstrateSSH(server);
    demonstratePackages(server);
    demonstrateServices(server);
    demonstrateDesiredState(server);
    demonstrateLogging(server);
    demonstrateBackupPlanning();
    demonstrateMonitoring(server);
    demonstrateTroubleshooting();
    demonstrateSecurity(server);

    await demonstrateAsyncAutomation(server);

    runTests(server);

    section("14. Integrated server report");
    server.report();

    section("15. Administrative command reference");

    const references = [
        ["Identity", "id"],
        ["Current user", "whoami"],
        ["Users", "getent passwd"],
        ["Groups", "getent group"],
        ["SSH status", "systemctl status ssh"],
        ["SSH logs", "journalctl -u ssh"],
        ["Processes", "ps aux"],
        ["Sockets", "ss -tulpn"],
        ["Storage", "df -h"],
        ["Directory usage", "du -sh /path"],
        ["Permissions", "ls -l"],
        ["Change mode", "chmod 640 FILE"],
        ["Change owner", "chown USER:GROUP FILE"],
        ["Package update", "sudo apt update"],
        ["Package install", "sudo apt install PACKAGE"],
        ["Service start", "sudo systemctl start SERVICE"],
        ["Service enable", "sudo systemctl enable SERVICE"],
        ["Scheduled tasks", "crontab -e"],
    ];

    for (const [purpose, cmd] of references) {
        console.log(`${purpose.padEnd(20)} ${cmd}`);
    }
}

main().catch(error => {
    console.error("\nFatal error:", error.message);
    process.exitCode = 1;
});
