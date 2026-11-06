#!/usr/bin/env python3
"""
Identity and Access Management (IAM)
Demonstrates users, groups, roles, permissions, policies,
role-based access control, least privilege, and access auditing.

Python 3.10+
Uses only the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
import json
import logging
import secrets
import unittest


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("iam")


class IAMError(Exception):
    """Base exception for IAM operations."""


class ValidationError(IAMError):
    pass


class NotFoundError(IAMError):
    pass


class DuplicateError(IAMError):
    pass


class AuthorizationError(IAMError):
    pass


class AccountStatus(Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class Effect(Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class User:
    user_id: str
    username: str
    email: str
    department: str
    status: AccountStatus = AccountStatus.ACTIVE
    groups: set[str] = field(default_factory=set)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        if not self.username.strip():
            raise ValidationError("Username cannot be empty.")
        if "@" not in self.email:
            raise ValidationError("Invalid email address.")
        if not self.user_id.strip():
            raise ValidationError("User ID cannot be empty.")


@dataclass(frozen=True)
class Permission:
    resource: str
    action: str

    def __post_init__(self):
        if not self.resource.strip() or not self.action.strip():
            raise ValidationError("Permission fields cannot be empty.")


@dataclass
class Role:
    role_id: str
    name: str
    description: str
    permissions: set[Permission] = field(default_factory=set)


@dataclass
class Group:
    group_id: str
    name: str
    members: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Policy:
    policy_id: str
    name: str
    effect: Effect
    permissions: frozenset[Permission]
    departments: frozenset[str] = frozenset()
    excluded_users: frozenset[str] = frozenset()


@dataclass
class AuditEvent:
    timestamp: datetime
    user_id: str
    resource: str
    action: str
    allowed: bool
    reason: str


class IdentityAccessManager:
    def __init__(self):
        self.users: dict[str, User] = {}
        self.roles: dict[str, Role] = {}
        self.groups: dict[str, Group] = {}
        self.policies: dict[str, Policy] = {}
        self.audit_log: list[AuditEvent] = []

    def add_user(self, user: User):
        if user.user_id in self.users:
            raise DuplicateError("User ID already exists.")

        if any(
            existing.username.lower() == user.username.lower()
            or existing.email.lower() == user.email.lower()
            for existing in self.users.values()
        ):
            raise DuplicateError("Username or email already exists.")

        self.users[user.user_id] = user

    def add_role(self, role: Role):
        if role.role_id in self.roles:
            raise DuplicateError("Role already exists.")

        if not role.name.strip():
            raise ValidationError("Role name cannot be empty.")

        self.roles[role.role_id] = role

    def add_group(self, group: Group):
        if group.group_id in self.groups:
            raise DuplicateError("Group already exists.")

        if not group.name.strip():
            raise ValidationError("Group name cannot be empty.")

        self.groups[group.group_id] = group

    def add_policy(self, policy: Policy):
        if policy.policy_id in self.policies:
            raise DuplicateError("Policy already exists.")

        if not policy.permissions:
            raise ValidationError("Policy must contain permissions.")

        self.policies[policy.policy_id] = policy

    def add_user_to_group(self, user_id: str, group_id: str):
        user = self.get_user(user_id)
        group = self.get_group(group_id)

        user.groups.add(group_id)
        group.members.add(user_id)

    def remove_user_from_group(self, user_id: str, group_id: str):
        user = self.get_user(user_id)
        group = self.get_group(group_id)

        user.groups.discard(group_id)
        group.members.discard(user_id)

    def assign_role_to_group(self, group_id: str, role_id: str):
        group = self.get_group(group_id)
        self.get_role(role_id)
        group.roles.add(role_id)

    def revoke_role_from_group(self, group_id: str, role_id: str):
        group = self.get_group(group_id)
        group.roles.discard(role_id)

    def assign_role_to_user(self, user_id: str, role_id: str):
        user = self.get_user(user_id)
        role = self.get_role(role_id)

        # Direct assignments are supported but should be minimized.
        user.groups.add(f"direct-role:{role.role_id}")

    def get_user(self, user_id: str) -> User:
        try:
            return self.users[user_id]
        except KeyError:
            raise NotFoundError(f"User not found: {user_id}")

    def get_group(self, group_id: str) -> Group:
        try:
            return self.groups[group_id]
        except KeyError:
            raise NotFoundError(f"Group not found: {group_id}")

    def get_role(self, role_id: str) -> Role:
        try:
            return self.roles[role_id]
        except KeyError:
            raise NotFoundError(f"Role not found: {role_id}")

    def get_effective_roles(self, user_id: str) -> set[str]:
        user = self.get_user(user_id)
        effective_roles = set()

        for group_id in user.groups:
            if group_id.startswith("direct-role:"):
                effective_roles.add(group_id.split(":", 1)[1])
                continue

            group = self.get_group(group_id)
            effective_roles.update(group.roles)

        return effective_roles

    def get_effective_permissions(
        self, user_id: str
    ) -> set[Permission]:
        permissions = set()

        for role_id in self.get_effective_roles(user_id):
            role = self.get_role(role_id)
            permissions.update(role.permissions)

        return permissions

    def evaluate(
        self,
        user_id: str,
        resource: str,
        action: str,
        context: Optional[dict] = None
    ) -> tuple[bool, str]:
        user = self.get_user(user_id)
        context = context or {}

        if user.status != AccountStatus.ACTIVE:
            return False, "Account is not active."

        requested = Permission(resource, action)
        effective_permissions = self.get_effective_permissions(user_id)

        # Policies are evaluated independently of role permissions.
        matching_policies = [
            policy
            for policy in self.policies.values()
            if requested in policy.permissions
            and (
                not policy.departments
                or user.department in policy.departments
            )
            and user_id not in policy.excluded_users
        ]

        # Explicit deny takes precedence over every allow.
        for policy in matching_policies:
            if policy.effect == Effect.DENY:
                return False, f"Explicit deny: {policy.name}"

        for policy in matching_policies:
            if policy.effect == Effect.ALLOW:
                return True, f"Allowed by policy: {policy.name}"

        # RBAC permission evaluation.
        if requested in effective_permissions:
            return True, "Allowed by assigned role."

        return False, "No matching permission."

    def authorize(
        self,
        user_id: str,
        resource: str,
        action: str,
        context: Optional[dict] = None
    ) -> bool:
        allowed, reason = self.evaluate(
            user_id, resource, action, context
        )

        self.audit_log.append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                resource=resource,
                action=action,
                allowed=allowed,
                reason=reason
            )
        )

        logger.info(
            "Access decision user=%s resource=%s action=%s allowed=%s",
            user_id,
            resource,
            action,
            allowed
        )

        return allowed

    def require_access(
        self, user_id: str, resource: str, action: str
    ):
        if not self.authorize(user_id, resource, action):
            raise AuthorizationError(
                f"Access denied for {user_id}: {action} {resource}"
            )

    def disable_user(self, user_id: str):
        self.get_user(user_id).status = AccountStatus.DISABLED

    def enable_user(self, user_id: str):
        self.get_user(user_id).status = AccountStatus.ACTIVE

    def revoke_all_access(self, user_id: str):
        user = self.get_user(user_id)

        for group_id in list(user.groups):
            if not group_id.startswith("direct-role:"):
                self.remove_user_from_group(user_id, group_id)

        user.groups.clear()
        user.status = AccountStatus.DISABLED

    def least_privilege_report(self, user_id: str) -> dict:
        user = self.get_user(user_id)
        roles = self.get_effective_roles(user_id)
        permissions = self.get_effective_permissions(user_id)

        return {
            "user": user.username,
            "status": user.status.value,
            "groups": sorted(
                group_id for group_id in user.groups
                if not group_id.startswith("direct-role:")
            ),
            "roles": sorted(roles),
            "permissions": sorted(
                f"{p.resource}:{p.action}" for p in permissions
            ),
            "permission_count": len(permissions)
        }

    def export_audit_log(self, path: str):
        records = [
            {
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "resource": event.resource,
                "action": event.action,
                "allowed": event.allowed,
                "reason": event.reason
            }
            for event in self.audit_log
        ]

        with open(path, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)


def build_demo() -> IdentityAccessManager:
    iam = IdentityAccessManager()

    # Permissions define resource-action combinations.
    read_reports = Permission("reports", "read")
    create_reports = Permission("reports", "create")
    delete_users = Permission("users", "delete")
    read_payroll = Permission("payroll", "read")
    manage_users = Permission("users", "manage")

    iam.add_user(
        User("U001", "alice", "alice@example.com", "Finance")
    )
    iam.add_user(
        User("U002", "bob", "bob@example.com", "Engineering")
    )
    iam.add_user(
        User("U003", "charlie", "charlie@example.com", "Finance")
    )
    iam.add_user(
        User("U004", "diana", "diana@example.com", "Security")
    )

    iam.add_role(
        Role(
            "R001",
            "ReportReader",
            "Read business reports",
            {read_reports}
        )
    )

    iam.add_role(
        Role(
            "R002",
            "ReportAnalyst",
            "Read and create reports",
            {read_reports, create_reports}
        )
    )

    iam.add_role(
        Role(
            "R003",
            "SecurityAdministrator",
            "Manage user identities",
            {manage_users, delete_users}
        )
    )

    iam.add_role(
        Role(
            "R004",
            "PayrollAuditor",
            "Read payroll records",
            {read_payroll}
        )
    )

    iam.add_group(Group("G001", "FinanceTeam"))
    iam.add_group(Group("G002", "EngineeringTeam"))
    iam.add_group(Group("G003", "SecurityTeam"))

    iam.assign_role_to_group("G001", "R001")
    iam.assign_role_to_group("G002", "R001")
    iam.assign_role_to_group("G003", "R003")

    iam.add_user_to_group("U001", "G001")
    iam.add_user_to_group("U002", "G002")
    iam.add_user_to_group("U004", "G003")

    # Explicit denial protects payroll data.
    iam.add_policy(
        Policy(
            "P001",
            "FinancePayrollRestriction",
            Effect.DENY,
            frozenset({read_payroll}),
            departments=frozenset({"Finance"})
        )
    )

    # A narrowly scoped policy grants temporary project access.
    iam.add_policy(
        Policy(
            "P002",
            "FinanceReportCreation",
            Effect.ALLOW,
            frozenset({create_reports}),
            departments=frozenset({"Finance"})
        )
    )

    return iam


class IAMTests(unittest.TestCase):
    def setUp(self):
        self.iam = build_demo()

    def test_group_role_permission(self):
        self.assertTrue(
            self.iam.authorize("U001", "reports", "read")
        )

    def test_missing_permission(self):
        self.assertFalse(
            self.iam.authorize("U001", "users", "delete")
        )

    def test_explicit_deny(self):
        self.assertFalse(
            self.iam.authorize("U001", "payroll", "read")
        )

    def test_policy_allow(self):
        self.assertTrue(
            self.iam.authorize("U001", "reports", "create")
        )

    def test_disabled_account(self):
        self.iam.disable_user("U001")
        self.assertFalse(
            self.iam.authorize("U001", "reports", "read")
        )

    def test_revocation(self):
        self.iam.revoke_all_access("U001")
        self.assertFalse(
            self.iam.authorize("U001", "reports", "read")
        )

    def test_duplicate_user(self):
        with self.assertRaises(DuplicateError):
            self.iam.add_user(
                User("U005", "alice", "other@example.com", "Finance")
            )

    def test_missing_user(self):
        with self.assertRaises(NotFoundError):
            self.iam.get_user("UNKNOWN")


def main():
    iam = build_demo()

    print("\nIDENTITY AND ACCESS MANAGEMENT")
    print("=" * 55)

    requests = [
        ("U001", "reports", "read"),
        ("U001", "reports", "create"),
        ("U001", "payroll", "read"),
        ("U002", "reports", "create"),
        ("U002", "users", "delete"),
        ("U004", "users", "delete")
    ]

    for user_id, resource, action in requests:
        allowed, reason = iam.evaluate(
            user_id, resource, action
        )
        print(
            f"{user_id}: {action} {resource}: "
            f"{'ALLOW' if allowed else 'DENY'} ({reason})"
        )
        iam.authorize(user_id, resource, action)

    print("\nLEAST PRIVILEGE REPORT")
    print(json.dumps(
        iam.least_privilege_report("U001"),
        indent=2
    ))

    print("\nACCOUNT DEACTIVATION")
    iam.disable_user("U002")
    print(
        "Bob report access:",
        iam.authorize("U002", "reports", "read")
    )

    print("\nAUDIT")
    print("Recorded access decisions:", len(iam.audit_log))

    print("\nUNIT TESTS")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        IAMTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
