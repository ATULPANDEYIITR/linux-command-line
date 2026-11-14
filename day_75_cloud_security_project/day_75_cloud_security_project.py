#!/usr/bin/env python3
"""
CLOUD SECURITY GOVERNANCE PLATFORM

Implements a self-contained cloud infrastructure security simulation covering:
- Identity and Access Management (IAM)
- Role-based access control
- Network isolation and security groups
- Encryption at rest and in transit
- Centralized audit logging
- Security monitoring and incident detection
- Security policy evaluation
- Configuration validation
- Automated security posture assessment

Runtime: Python 3.10+
Dependencies: Python standard library only
"""

from __future__ import annotations

import json
import logging
import hashlib
import secrets
import ipaddress
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict, Counter
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("cloud-security")


class SecurityError(Exception):
    """Base exception for security operations."""


class AuthorizationError(SecurityError):
    pass


class ValidationError(SecurityError):
    pass


class PolicyViolation(SecurityError):
    pass


class AccessDecision(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class ResourceState(Enum):
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    DISABLED = "DISABLED"


class Severity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EncryptionMode(Enum):
    AES_256 = "AES-256"
    AES_128 = "AES-128"


@dataclass(frozen=True)
class Permission:
    action: str
    resource: str

    def matches(self, action: str, resource: str) -> bool:
        action_match = self.action == "*" or self.action == action
        resource_match = (
            self.resource == "*"
            or self.resource == resource
            or (
                self.resource.endswith("*")
                and resource.startswith(self.resource[:-1])
            )
        )
        return action_match and resource_match


@dataclass
class Role:
    name: str
    permissions: set[Permission] = field(default_factory=set)


@dataclass
class Principal:
    principal_id: str
    roles: set[str] = field(default_factory=set)
    enabled: bool = True
    mfa_enabled: bool = False


@dataclass
class CloudResource:
    resource_id: str
    resource_type: str
    owner: str
    encrypted_at_rest: bool
    encrypted_in_transit: bool
    public_access: bool = False
    state: ResourceState = ResourceState.ACTIVE


@dataclass(frozen=True)
class NetworkRule:
    protocol: str
    port: int
    cidr: str
    direction: str

    def validate(self) -> None:
        if self.protocol not in {"TCP", "UDP", "ICMP"}:
            raise ValidationError("Unsupported network protocol")

        if self.direction not in {"INGRESS", "EGRESS"}:
            raise ValidationError("Invalid network direction")

        if not 0 <= self.port <= 65535:
            raise ValidationError("Invalid network port")

        try:
            ipaddress.ip_network(self.cidr, strict=False)
        except ValueError as exc:
            raise ValidationError("Invalid CIDR range") from exc


@dataclass
class SecurityEvent:
    event_id: str
    timestamp: datetime
    principal_id: str
    action: str
    resource_id: str
    decision: AccessDecision
    severity: Severity
    description: str


@dataclass
class SecurityAlert:
    alert_id: str
    severity: Severity
    description: str
    event_ids: list[str]
    created_at: datetime


class AuditLogger:
    """Append-only in-memory audit chain with tamper-evident hashes."""

    def __init__(self):
        self.events: list[SecurityEvent] = []
        self.previous_hash = "0" * 64
        self.chain_hashes: list[str] = []

    def record(self, event: SecurityEvent) -> None:
        payload = json.dumps(
            {
                "event": asdict(event),
                "previous_hash": self.previous_hash,
            },
            default=lambda value: (
                value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if isinstance(value, Enum)
                else sorted(value)
                if isinstance(value, set)
                else value
            ),
            sort_keys=True,
        )

        digest = hashlib.sha256(payload.encode()).hexdigest()

        self.events.append(event)
        self.chain_hashes.append(digest)
        self.previous_hash = digest

    def verify_integrity(self) -> bool:
        previous = "0" * 64

        for event, stored_hash in zip(self.events, self.chain_hashes):
            payload = json.dumps(
                {
                    "event": asdict(event),
                    "previous_hash": previous,
                },
                default=lambda value: (
                    value.isoformat()
                    if isinstance(value, datetime)
                    else value.value
                    if isinstance(value, Enum)
                    else sorted(value)
                    if isinstance(value, set)
                    else value
                ),
                sort_keys=True,
            )

            calculated = hashlib.sha256(payload.encode()).hexdigest()

            if not secrets.compare_digest(calculated, stored_hash):
                return False

            previous = calculated

        return len(self.events) == len(self.chain_hashes)


class IAMService:
    """Role-based access control with explicit deny-by-default behavior."""

    def __init__(self):
        self.roles: dict[str, Role] = {}
        self.principals: dict[str, Principal] = {}

    def create_role(self, role: Role) -> None:
        if not role.name or role.name in self.roles:
            raise ValidationError("Invalid or duplicate role")
        self.roles[role.name] = role

    def create_principal(self, principal: Principal) -> None:
        if principal.principal_id in self.principals:
            raise ValidationError("Duplicate principal")

        unknown = principal.roles - self.roles.keys()
        if unknown:
            raise ValidationError(f"Unknown roles: {unknown}")

        self.principals[principal.principal_id] = principal

    def authorize(
        self,
        principal_id: str,
        action: str,
        resource: str,
        require_mfa: bool = False,
    ) -> AccessDecision:

        principal = self.principals.get(principal_id)

        if principal is None or not principal.enabled:
            return AccessDecision.DENY

        if require_mfa and not principal.mfa_enabled:
            return AccessDecision.DENY

        for role_name in principal.roles:
            role = self.roles[role_name]

            if any(
                permission.matches(action, resource)
                for permission in role.permissions
            ):
                return AccessDecision.ALLOW

        return AccessDecision.DENY


class NetworkSecurityService:
    """Evaluates inbound and outbound network rules."""

    def __init__(self):
        self.rules: dict[str, list[NetworkRule]] = defaultdict(list)

    def add_rule(self, resource_id: str, rule: NetworkRule) -> None:
        rule.validate()
        self.rules[resource_id].append(rule)

    def allows(
        self,
        resource_id: str,
        source_ip: str,
        port: int,
        direction: str = "INGRESS",
        protocol: str = "TCP",
    ) -> bool:

        try:
            address = ipaddress.ip_address(source_ip)
        except ValueError:
            raise ValidationError("Invalid source IP address")

        for rule in self.rules.get(resource_id, []):
            network = ipaddress.ip_network(rule.cidr, strict=False)

            if (
                rule.direction == direction
                and rule.protocol == protocol
                and rule.port == port
                and address in network
            ):
                return True

        return False


class EncryptionService:
    """Models encryption configuration and key metadata."""

    def __init__(self):
        self.keys: dict[str, dict] = {}

    def create_key(self, key_id: str, mode: EncryptionMode) -> None:
        if not key_id or key_id in self.keys:
            raise ValidationError("Invalid or duplicate encryption key")

        self.keys[key_id] = {
            "algorithm": mode.value,
            "created_at": datetime.now(timezone.utc),
            "enabled": True,
            "rotation_interval_days": 90,
        }

    def validate_key(self, key_id: str) -> bool:
        key = self.keys.get(key_id)
        return bool(key and key["enabled"])

    def rotate_key(self, key_id: str) -> None:
        if not self.validate_key(key_id):
            raise ValidationError("Encryption key unavailable")

        self.keys[key_id]["created_at"] = datetime.now(timezone.utc)


class MonitoringService:
    """Detects suspicious activity using configurable event thresholds."""

    def __init__(self, threshold: int = 3):
        if threshold < 1:
            raise ValidationError("Threshold must be positive")

        self.threshold = threshold
        self.alerts: list[SecurityAlert] = []

    def analyze(
        self,
        events: list[SecurityEvent],
    ) -> list[SecurityAlert]:

        failures = defaultdict(list)

        for event in events:
            if event.decision == AccessDecision.DENY:
                failures[event.principal_id].append(event)

        for principal_id, rejected in failures.items():
            if len(rejected) >= self.threshold:
                alert = SecurityAlert(
                    alert_id=secrets.token_hex(8),
                    severity=Severity.HIGH,
                    description=(
                        f"Repeated unauthorized access by {principal_id}: "
                        f"{len(rejected)} denied requests"
                    ),
                    event_ids=[event.event_id for event in rejected],
                    created_at=datetime.now(timezone.utc),
                )
                self.alerts.append(alert)

        return self.alerts.copy()


class CloudSecurityPlatform:

    def __init__(self):
        self.iam = IAMService()
        self.network = NetworkSecurityService()
        self.encryption = EncryptionService()
        self.audit = AuditLogger()
        self.monitoring = MonitoringService(threshold=3)
        self.resources: dict[str, CloudResource] = {}

    def register_resource(self, resource: CloudResource) -> None:
        if resource.resource_id in self.resources:
            raise ValidationError("Resource already registered")

        if not resource.encrypted_at_rest:
            raise PolicyViolation("Encryption at rest is mandatory")

        if not resource.encrypted_in_transit:
            raise PolicyViolation("Encryption in transit is mandatory")

        if resource.public_access:
            raise PolicyViolation("Public access is prohibited by default")

        self.resources[resource.resource_id] = resource

    def access_resource(
        self,
        principal_id: str,
        action: str,
        resource_id: str,
        source_ip: str,
        port: int = 443,
    ) -> AccessDecision:

        resource = self.resources.get(resource_id)

        if resource is None:
            raise ValidationError("Resource does not exist")

        if resource.state != ResourceState.ACTIVE:
            decision = AccessDecision.DENY
            description = "Resource is not active"
        else:
            iam_allowed = (
                self.iam.authorize(
                    principal_id,
                    action,
                    resource_id,
                    require_mfa=True,
                )
                == AccessDecision.ALLOW
            )

            network_allowed = self.network.allows(
                resource_id,
                source_ip,
                port,
            )

            decision = (
                AccessDecision.ALLOW
                if iam_allowed and network_allowed
                else AccessDecision.DENY
            )

            description = (
                "Authorized access"
                if decision == AccessDecision.ALLOW
                else "IAM or network policy denied access"
            )

        event = SecurityEvent(
            event_id=secrets.token_hex(8),
            timestamp=datetime.now(timezone.utc),
            principal_id=principal_id,
            action=action,
            resource_id=resource_id,
            decision=decision,
            severity=(
                Severity.LOW
                if decision == AccessDecision.ALLOW
                else Severity.HIGH
            ),
            description=description,
        )

        self.audit.record(event)

        if decision == AccessDecision.DENY:
            logger.warning(
                "Access denied: principal=%s resource=%s",
                principal_id,
                resource_id,
            )

        return decision

    def security_assessment(self) -> dict:
        findings = []

        for resource in self.resources.values():
            if not resource.encrypted_at_rest:
                findings.append(
                    f"{resource.resource_id}: missing at-rest encryption"
                )

            if not resource.encrypted_in_transit:
                findings.append(
                    f"{resource.resource_id}: missing transport encryption"
                )

            if resource.public_access:
                findings.append(
                    f"{resource.resource_id}: public access enabled"
                )

            if resource.state != ResourceState.ACTIVE:
                findings.append(
                    f"{resource.resource_id}: {resource.state.value}"
                )

        return {
            "resources_assessed": len(self.resources),
            "findings": findings,
            "audit_integrity": self.audit.verify_integrity(),
            "alerts": len(self.monitoring.alerts),
            "assessment_time": datetime.now(timezone.utc).isoformat(),
        }


def build_demo() -> CloudSecurityPlatform:
    platform = CloudSecurityPlatform()

    platform.iam.create_role(
        Role(
            "cloud-operator",
            {
                Permission("storage:read", "storage-*"),
                Permission("storage:write", "storage-*"),
            },
        )
    )

    platform.iam.create_role(
        Role(
            "security-auditor",
            {
                Permission("audit:read", "*"),
            },
        )
    )

    platform.iam.create_principal(
        Principal(
            "operator-001",
            {"cloud-operator"},
            enabled=True,
            mfa_enabled=True,
        )
    )

    platform.iam.create_principal(
        Principal(
            "auditor-001",
            {"security-auditor"},
            enabled=True,
            mfa_enabled=True,
        )
    )

    platform.iam.create_principal(
        Principal(
            "untrusted-001",
            set(),
            enabled=True,
            mfa_enabled=False,
        )
    )

    platform.encryption.create_key(
        "key-storage-001",
        EncryptionMode.AES_256,
    )

    platform.register_resource(
        CloudResource(
            resource_id="storage-finance-001",
            resource_type="OBJECT_STORAGE",
            owner="finance-team",
            encrypted_at_rest=True,
            encrypted_in_transit=True,
        )
    )

    platform.network.add_rule(
        "storage-finance-001",
        NetworkRule(
            protocol="TCP",
            port=443,
            cidr="10.20.0.0/16",
            direction="INGRESS",
        ),
    )

    return platform


def run_tests() -> None:
    platform = build_demo()

    assert platform.encryption.validate_key("key-storage-001")

    assert platform.access_resource(
        "operator-001",
        "storage:read",
        "storage-finance-001",
        "10.20.1.15",
    ) == AccessDecision.ALLOW

    assert platform.access_resource(
        "operator-001",
        "storage:write",
        "storage-finance-001",
        "192.168.1.10",
    ) == AccessDecision.DENY

    for _ in range(3):
        platform.access_resource(
            "untrusted-001",
            "storage:read",
            "storage-finance-001",
            "10.20.1.20",
        )

    alerts = platform.monitoring.analyze(platform.audit.events)

    assert len(alerts) >= 1
    assert platform.audit.verify_integrity()

    assessment = platform.security_assessment()

    assert assessment["resources_assessed"] == 1
    assert assessment["audit_integrity"]

    print("\nCLOUD SECURITY ASSESSMENT")
    print(json.dumps(assessment, indent=2))

    print("\nSECURITY ALERTS")
    for alert in alerts:
        print(
            alert.severity.value,
            alert.description,
        )

    print("\nAll security tests passed.")


if __name__ == "__main__":
    run_tests()
