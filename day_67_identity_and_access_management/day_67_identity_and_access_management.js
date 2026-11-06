"use strict";

/**
 * Identity and Access Management
 *
 * Event-driven IAM policy engine using Node.js standard libraries.
 * Demonstrates RBAC, group inheritance, policy evaluation,
 * explicit deny, account lifecycle, access requests and auditing.
 *
 * Runtime: Node.js 18+
 */

const crypto = require("node:crypto");
const EventEmitter = require("node:events");
const assert = require("node:assert/strict");

class IAMError extends Error {}
class ValidationError extends IAMError {}
class DuplicateError extends IAMError {}
class NotFoundError extends IAMError {}
class AuthorizationError extends IAMError {}

const AccountStatus = Object.freeze({
    ACTIVE: "ACTIVE",
    DISABLED: "DISABLED",
    LOCKED: "LOCKED"
});

const Effect = Object.freeze({
    ALLOW: "ALLOW",
    DENY: "DENY"
});

function validateIdentifier(value, field) {
    if (
        typeof value !== "string" ||
        !/^[A-Za-z0-9_-]{2,64}$/.test(value)
    ) {
        throw new ValidationError(`Invalid ${field}.`);
    }
}

function permissionKey(resource, action) {
    if (
        typeof resource !== "string" ||
        typeof action !== "string" ||
        !resource.trim() ||
        !action.trim()
    ) {
        throw new ValidationError("Invalid permission.");
    }

    return `${resource.trim().toLowerCase()}:${action.trim().toLowerCase()}`;
}

class User {
    constructor({ id, username, email, department }) {
        validateIdentifier(id, "user ID");

        if (!username || !username.trim()) {
            throw new ValidationError("Username is required.");
        }

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            throw new ValidationError("Invalid email.");
        }

        this.id = id;
        this.username = username.trim();
        this.email = email.toLowerCase();
        this.department = department;
        this.status = AccountStatus.ACTIVE;
        this.groups = new Set();
        this.createdAt = new Date();
        this.version = 1;
    }
}

class Role {
    constructor(id, name, permissions = []) {
        validateIdentifier(id, "role ID");

        if (!name || !name.trim()) {
            throw new ValidationError("Role name is required.");
        }

        this.id = id;
        this.name = name;
        this.permissions = new Set(
            permissions.map(p => permissionKey(p.resource, p.action))
        );
    }
}

class Group {
    constructor(id, name) {
        validateIdentifier(id, "group ID");

        this.id = id;
        this.name = name;
        this.members = new Set();
        this.roles = new Set();
    }
}

class Policy {
    constructor({
        id,
        name,
        effect,
        permissions,
        departments = [],
        excludedUsers = []
    }) {
        validateIdentifier(id, "policy ID");

        if (![Effect.ALLOW, Effect.DENY].includes(effect)) {
            throw new ValidationError("Invalid policy effect.");
        }

        if (!permissions.length) {
            throw new ValidationError(
                "A policy requires at least one permission."
            );
        }

        this.id = id;
        this.name = name;
        this.effect = effect;
        this.permissions = new Set(
            permissions.map(p => permissionKey(p.resource, p.action))
        );
        this.departments = new Set(departments);
        this.excludedUsers = new Set(excludedUsers);
    }
}

class AuditEvent {
    constructor(data) {
        this.id = crypto.randomUUID();
        this.timestamp = new Date().toISOString();
        Object.assign(this, data);
    }
}

class IAMEngine extends EventEmitter {
    #users = new Map();
    #roles = new Map();
    #groups = new Map();
    #policies = new Map();
    #audit = [];
    #pendingRequests = new Map();

    addUser(user) {
        if (this.#users.has(user.id)) {
            throw new DuplicateError("Duplicate user ID.");
        }

        for (const existing of this.#users.values()) {
            if (
                existing.email === user.email ||
                existing.username.toLowerCase() ===
                    user.username.toLowerCase()
            ) {
                throw new DuplicateError(
                    "Username or email already registered."
                );
            }
        }

        this.#users.set(user.id, user);
        this.emit("user.created", { userId: user.id });
    }

    addRole(role) {
        if (this.#roles.has(role.id)) {
            throw new DuplicateError("Duplicate role.");
        }

        this.#roles.set(role.id, role);
    }

    addGroup(group) {
        if (this.#groups.has(group.id)) {
            throw new DuplicateError("Duplicate group.");
        }

        this.#groups.set(group.id, group);
    }

    addPolicy(policy) {
        if (this.#policies.has(policy.id)) {
            throw new DuplicateError("Duplicate policy.");
        }

        this.#policies.set(policy.id, policy);
    }

    getUser(id) {
        const user = this.#users.get(id);
        if (!user) throw new NotFoundError(`Unknown user: ${id}`);
        return user;
    }

    getGroup(id) {
        const group = this.#groups.get(id);
        if (!group) throw new NotFoundError(`Unknown group: ${id}`);
        return group;
    }

    getRole(id) {
        const role = this.#roles.get(id);
        if (!role) throw new NotFoundError(`Unknown role: ${id}`);
        return role;
    }

    addMember(userId, groupId) {
        const user = this.getUser(userId);
        const group = this.getGroup(groupId);

        user.groups.add(groupId);
        group.members.add(userId);
        user.version++;

        this.emit("membership.changed", {
            userId,
            groupId,
            operation: "ADD"
        });
    }

    removeMember(userId, groupId) {
        const user = this.getUser(userId);
        const group = this.getGroup(groupId);

        user.groups.delete(groupId);
        group.members.delete(userId);
        user.version++;

        this.emit("membership.changed", {
            userId,
            groupId,
            operation: "REMOVE"
        });
    }

    assignRole(groupId, roleId) {
        const group = this.getGroup(groupId);
        this.getRole(roleId);
        group.roles.add(roleId);
    }

    effectiveRoles(userId) {
        const user = this.getUser(userId);
        const result = new Set();

        for (const groupId of user.groups) {
            for (const roleId of this.getGroup(groupId).roles) {
                result.add(roleId);
            }
        }

        return result;
    }

    effectivePermissions(userId) {
        const result = new Set();

        for (const roleId of this.effectiveRoles(userId)) {
            for (const permission of this.getRole(roleId).permissions) {
                result.add(permission);
            }
        }

        return result;
    }

    evaluate(userId, resource, action) {
        const user = this.getUser(userId);
        const requested = permissionKey(resource, action);

        if (user.status !== AccountStatus.ACTIVE) {
            return {
                allowed: false,
                reason: "Account is not active."
            };
        }

        const applicable = [...this.#policies.values()].filter(policy => {
            return (
                policy.permissions.has(requested) &&
                (
                    policy.departments.size === 0 ||
                    policy.departments.has(user.department)
                ) &&
                !policy.excludedUsers.has(userId)
            );
        });

        // Explicit deny overrides role permissions and policy allows.
        const deny = applicable.find(
            policy => policy.effect === Effect.DENY
        );

        if (deny) {
            return {
                allowed: false,
                reason: `Explicit deny: ${deny.name}`
            };
        }

        const allow = applicable.find(
            policy => policy.effect === Effect.ALLOW
        );

        if (allow) {
            return {
                allowed: true,
                reason: `Policy allow: ${allow.name}`
            };
        }

        if (this.effectivePermissions(userId).has(requested)) {
            return {
                allowed: true,
                reason: "Role permission granted."
            };
        }

        return {
            allowed: false,
            reason: "No matching permission."
        };
    }

    authorize(userId, resource, action) {
        const result = this.evaluate(userId, resource, action);

        const event = new AuditEvent({
            userId,
            resource,
            action,
            allowed: result.allowed,
            reason: result.reason
        });

        this.#audit.push(event);
        this.emit("access.evaluated", event);

        return result.allowed;
    }

    requireAccess(userId, resource, action) {
        if (!this.authorize(userId, resource, action)) {
            throw new AuthorizationError(
                `${userId} cannot ${action} ${resource}`
            );
        }
    }

    changeStatus(userId, status) {
        if (!Object.values(AccountStatus).includes(status)) {
            throw new ValidationError("Invalid account status.");
        }

        const user = this.getUser(userId);
        user.status = status;
        user.version++;

        this.emit("user.status.changed", {
            userId,
            status,
            version: user.version
        });
    }

    // Access requests are asynchronous and require explicit approval.
    async requestTemporaryAccess({
        userId,
        resource,
        action,
        approverId,
        durationMinutes
    }) {
        const user = this.getUser(userId);
        const approver = this.getUser(approverId);

        if (user.status !== AccountStatus.ACTIVE) {
            throw new AuthorizationError("Inactive requester.");
        }

        if (approver.status !== AccountStatus.ACTIVE) {
            throw new AuthorizationError("Inactive approver.");
        }

        if (userId === approverId) {
            throw new AuthorizationError(
                "Self-approval is prohibited."
            );
        }

        if (
            !Number.isInteger(durationMinutes) ||
            durationMinutes < 1 ||
            durationMinutes > 480
        ) {
            throw new ValidationError(
                "Access duration must be 1-480 minutes."
            );
        }

        const id = crypto.randomUUID();

        const request = {
            id,
            userId,
            resource,
            action,
            approverId,
            status: "PENDING",
            expiresAt: null,
            requestedAt: new Date().toISOString(),
            durationMinutes
        };

        this.#pendingRequests.set(id, request);
        this.emit("access.requested", { ...request });

        return { ...request };
    }

    approveTemporaryAccess(requestId, approverId) {
        const request = this.#pendingRequests.get(requestId);

        if (!request) {
            throw new NotFoundError("Access request not found.");
        }

        if (request.status !== "PENDING") {
            throw new IAMError("Request is not pending.");
        }

        if (request.approverId !== approverId) {
            throw new AuthorizationError("Incorrect approver.");
        }

        const approver = this.getUser(approverId);

        if (approver.status !== AccountStatus.ACTIVE) {
            throw new AuthorizationError("Approver is inactive.");
        }

        request.status = "APPROVED";
        request.expiresAt = new Date(
            Date.now() + request.durationMinutes * 60000
        ).toISOString();

        this.emit("access.approved", { ...request });
        return { ...request };
    }

    getAuditReport() {
        return this.#audit.map(event => ({ ...event }));
    }

    getLeastPrivilegeReport(userId) {
        const user = this.getUser(userId);

        return {
            username: user.username,
            groups: [...user.groups],
            roles: [...this.effectiveRoles(userId)],
            permissions: [...this.effectivePermissions(userId)].sort(),
            status: user.status,
            version: user.version
        };
    }
}

async function main() {
    const iam = new IAMEngine();

    iam.on("access.evaluated", event => {
        console.log(
            `[AUDIT] ${event.userId} ${event.action} ${event.resource}:`,
            event.allowed ? "ALLOW" : "DENY"
        );
    });

    iam.on("membership.changed", event => {
        console.log(
            `[EVENT] Membership ${event.operation}:`,
            event.userId,
            event.groupId
        );
    });

    const users = [
        new User({
            id: "U001",
            username: "alice",
            email: "alice@example.com",
            department: "Finance"
        }),
        new User({
            id: "U002",
            username: "bob",
            email: "bob@example.com",
            department: "Engineering"
        }),
        new User({
            id: "U003",
            username: "carol",
            email: "carol@example.com",
            department: "Security"
        })
    ];

    users.forEach(user => iam.addUser(user));

    iam.addRole(new Role("R001", "ReportReader", [
        { resource: "reports", action: "read" }
    ]));

    iam.addRole(new Role("R002", "SecurityAdmin", [
        { resource: "users", action: "manage" },
        { resource: "users", action: "delete" }
    ]));

    iam.addGroup(new Group("G001", "Finance"));
    iam.addGroup(new Group("G002", "Engineering"));
    iam.addGroup(new Group("G003", "Security"));

    iam.assignRole("G001", "R001");
    iam.assignRole("G002", "R001");
    iam.assignRole("G003", "R002");

    iam.addMember("U001", "G001");
    iam.addMember("U002", "G002");
    iam.addMember("U003", "G003");

    iam.addPolicy(new Policy({
        id: "P001",
        name: "PayrollProtection",
        effect: Effect.DENY,
        permissions: [
            { resource: "payroll", action: "read" }
        ],
        departments: ["Finance"]
    }));

    iam.addPolicy(new Policy({
        id: "P002",
        name: "FinanceReportCreation",
        effect: Effect.ALLOW,
        permissions: [
            { resource: "reports", action: "create" }
        ],
        departments: ["Finance"]
    }));

    console.log("\nACCESS EVALUATION");

    const checks = [
        ["U001", "reports", "read"],
        ["U001", "reports", "create"],
        ["U001", "payroll", "read"],
        ["U002", "reports", "create"],
        ["U003", "users", "delete"]
    ];

    for (const [user, resource, action] of checks) {
        const result = iam.evaluate(user, resource, action);
        console.log({
            user,
            resource,
            action,
            ...result
        });
        iam.authorize(user, resource, action);
    }

    console.log("\nLEAST PRIVILEGE");
    console.log(iam.getLeastPrivilegeReport("U001"));

    console.log("\nTEMPORARY ACCESS REQUEST");

    const request = await iam.requestTemporaryAccess({
        userId: "U001",
        resource: "analytics",
        action: "read",
        approverId: "U003",
        durationMinutes: 30
    });

    console.log(
        iam.approveTemporaryAccess(request.id, "U003")
    );

    console.log("\nACCOUNT DEACTIVATION");
    iam.changeStatus("U002", AccountStatus.DISABLED);

    assert.equal(
        iam.authorize("U002", "reports", "read"),
        false
    );

    assert.throws(
        () => iam.requireAccess("U001", "users", "delete"),
        AuthorizationError
    );

    assert.throws(
        () => iam.addMember("UNKNOWN", "G001"),
        NotFoundError
    );

    console.log("\nAUDIT EVENTS:", iam.getAuditReport().length);
    console.log("All IAM assertions passed.");
}

main().catch(error => {
    console.error("IAM execution failed:", error.message);
    process.exitCode = 1;
});
