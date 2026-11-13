#!/usr/bin/env python3
"""
Compliance and Governance Management System

Demonstrates:
- Data privacy classification
- Regulatory obligation tracking
- Consent management
- Data subject rights
- Retention and deletion policies
- Access control
- Audit logging
- Compliance assessments
- Governance policy enforcement
- Compliance reporting

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import unittest

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

LOGGER = logging.getLogger("compliance")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ComplianceError(Exception):
    """Base exception for compliance operations."""


class ValidationError(ComplianceError):
    pass


class AuthorizationError(ComplianceError):
    pass


class PolicyViolation(ComplianceError):
    pass


class PrivacyCategory(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PERSONAL = "personal"
    SENSITIVE_PERSONAL = "sensitive_personal"


class LegalBasis(Enum):
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    LEGITIMATE_INTEREST = "legitimate_interest"
    VITAL_INTEREST = "vital_interest"
    PUBLIC_TASK = "public_task"


class ConsentStatus(Enum):
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class DataSubjectRequestType(Enum):
    ACCESS = "access"
    RECTIFICATION = "rectification"
    ERASURE = "erasure"
    PORTABILITY = "portability"
    RESTRICTION = "restriction"


class RequestStatus(Enum):
    RECEIVED = "received"
    VERIFIED = "verified"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditAction(Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    ACCESS_DENIED = "access_denied"
    POLICY_CHANGE = "policy_change"
    CONSENT_CHANGE = "consent_change"
    REQUEST_PROCESSED = "request_processed"


@dataclass(frozen=True)
class RegulatoryFramework:
    code: str
    name: str
    jurisdiction: str
    description: str


FRAMEWORKS = {
    "GDPR": RegulatoryFramework(
        "GDPR",
        "General Data Protection Regulation",
        "European Union",
        "Personal data protection and processing requirements."
    ),
    "DPDPA": RegulatoryFramework(
        "DPDPA",
        "Digital Personal Data Protection Act, 2023",
        "India",
        "Indian digital personal data protection framework."
    ),
    "ISO27001": RegulatoryFramework(
        "ISO27001",
        "Information Security Management System",
        "International",
        "Information security management requirements."
    ),
    "HIPAA": RegulatoryFramework(
        "HIPAA",
        "Health Insurance Portability and Accountability Act",
        "United States",
        "US protected health information safeguards."
    )
}


@dataclass
class DataAsset:
    asset_id: str
    name: str
    owner: str
    category: PrivacyCategory
    purpose: str
    legal_basis: LegalBasis
    framework_codes: set[str]
    created_at: datetime = field(default_factory=utc_now)
    retention_days: int = 365
    encrypted: bool = True
    active: bool = True

    def __post_init__(self):
        if not self.asset_id.strip() or not self.name.strip():
            raise ValidationError("Asset ID and name are required.")

        if self.retention_days <= 0:
            raise ValidationError("Retention period must be positive.")

        if not self.purpose.strip():
            raise ValidationError("Processing purpose is required.")

        unknown = self.framework_codes - FRAMEWORKS.keys()

        if unknown:
            raise ValidationError(
                f"Unknown regulatory frameworks: {unknown}"
            )

        if self.category == PrivacyCategory.SENSITIVE_PERSONAL:
            if not self.encrypted:
                raise PolicyViolation(
                    "Sensitive personal data must be encrypted."
                )


@dataclass
class User:
    user_id: str
    role: str
    permissions: set[str]
    active: bool = True


@dataclass
class Consent:
    consent_id: str
    subject_id: str
    asset_id: str
    purpose: str
    status: ConsentStatus
    granted_at: datetime
    expires_at: Optional[datetime] = None

    def is_valid(self) -> bool:
        return (
            self.status == ConsentStatus.GRANTED
            and (
                self.expires_at is None
                or utc_now() < self.expires_at
            )
        )


@dataclass
class Policy:
    policy_id: str
    name: str
    description: str
    mandatory: bool
    enabled: bool = True


@dataclass
class AuditEvent:
    event_id: str
    actor_id: str
    action: AuditAction
    resource_type: str
    resource_id: str
    timestamp: datetime
    details: dict
    previous_hash: str
    event_hash: str


@dataclass
class SubjectRequest:
    request_id: str
    subject_id: str
    request_type: DataSubjectRequestType
    status: RequestStatus
    received_at: datetime
    deadline: datetime
    notes: str = ""


@dataclass
class ComplianceFinding:
    finding_id: str
    asset_id: str
    risk: RiskLevel
    description: str
    framework_code: str
    resolved: bool = False


class AuditLogger:
    """
    Append-only hash-linked audit events.

    Hash chaining provides tamper-evidence, not guaranteed
    immutability. Production deployments require external
    protected storage and independent verification.
    """

    def __init__(self):
        self.events: list[AuditEvent] = []
        self._last_hash = "GENESIS"

    def record(
        self,
        actor_id: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        details: Optional[dict] = None
    ) -> AuditEvent:

        timestamp = utc_now()

        payload = {
            "actor_id": actor_id,
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": timestamp.isoformat(),
            "details": details or {},
            "previous_hash": self._last_hash
        }

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":")
        )

        event_hash = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

        event = AuditEvent(
            event_id=secrets.token_hex(8),
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=timestamp,
            details=details or {},
            previous_hash=self._last_hash,
            event_hash=event_hash
        )

        self.events.append(event)
        self._last_hash = event_hash

        return event

    def verify_integrity(self) -> bool:
        previous = "GENESIS"

        for event in self.events:
            payload = {
                "actor_id": event.actor_id,
                "action": event.action.value,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "timestamp": event.timestamp.isoformat(),
                "details": event.details,
                "previous_hash": previous
            }

            serialized = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":")
            )

            calculated = hashlib.sha256(
                serialized.encode("utf-8")
            ).hexdigest()

            if (
                event.previous_hash != previous
                or event.event_hash != calculated
            ):
                return False

            previous = event.event_hash

        return True

    def export_json(self, filename: str) -> None:
        records = []

        for event in self.events:
            record = asdict(event)
            record["action"] = event.action.value
            record["timestamp"] = event.timestamp.isoformat()
            records.append(record)

        Path(filename).write_text(
            json.dumps(records, indent=2),
            encoding="utf-8"
        )


class ComplianceManager:

    def __init__(self):
        self.assets: dict[str, DataAsset] = {}
        self.users: dict[str, User] = {}
        self.consents: dict[str, Consent] = {}
        self.policies: dict[str, Policy] = {}
        self.requests: dict[str, SubjectRequest] = {}
        self.findings: list[ComplianceFinding] = []
        self.audit = AuditLogger()

    def register_user(self, user: User) -> None:
        if user.user_id in self.users:
            raise ValidationError("User already exists.")

        self.users[user.user_id] = user

    def authorize(self, actor_id: str, permission: str) -> None:
        user = self.users.get(actor_id)

        if user is None or not user.active:
            raise AuthorizationError("Inactive or unknown user.")

        if permission not in user.permissions:
            self.audit.record(
                actor_id,
                AuditAction.ACCESS_DENIED,
                "permission",
                permission
            )
            raise AuthorizationError(
                f"Permission denied: {permission}"
            )

    def register_asset(
        self,
        actor_id: str,
        asset: DataAsset
    ) -> None:

        self.authorize(actor_id, "asset:create")

        if asset.asset_id in self.assets:
            raise ValidationError("Asset already registered.")

        self.assets[asset.asset_id] = asset

        self.audit.record(
            actor_id,
            AuditAction.CREATE,
            "data_asset",
            asset.asset_id,
            {"category": asset.category.value}
        )

    def grant_consent(
        self,
        actor_id: str,
        consent: Consent
    ) -> None:

        self.authorize(actor_id, "consent:manage")

        if consent.asset_id not in self.assets:
            raise ValidationError("Unknown data asset.")

        if consent.consent_id in self.consents:
            raise ValidationError("Duplicate consent ID.")

        if not consent.subject_id.strip() or not consent.purpose.strip():
            raise ValidationError("Invalid consent information.")

        self.consents[consent.consent_id] = consent

        self.audit.record(
            actor_id,
            AuditAction.CONSENT_CHANGE,
            "consent",
            consent.consent_id,
            {"status": consent.status.value}
        )

    def withdraw_consent(
        self,
        actor_id: str,
        consent_id: str
    ) -> None:

        self.authorize(actor_id, "consent:manage")

        consent = self.consents.get(consent_id)

        if consent is None:
            raise ValidationError("Consent not found.")

        consent.status = ConsentStatus.WITHDRAWN

        self.audit.record(
            actor_id,
            AuditAction.CONSENT_CHANGE,
            "consent",
            consent_id,
            {"status": "withdrawn"}
        )

    def can_process(
        self,
        asset_id: str,
        subject_id: str
    ) -> bool:

        asset = self.assets.get(asset_id)

        if asset is None or not asset.active:
            return False

        if asset.legal_basis == LegalBasis.CONSENT:
            return any(
                consent.asset_id == asset_id
                and consent.subject_id == subject_id
                and consent.purpose == asset.purpose
                and consent.is_valid()
                for consent in self.consents.values()
            )

        # Other legal bases must be independently documented
        # and assessed in production.
        return True

    def read_asset(
        self,
        actor_id: str,
        asset_id: str,
        subject_id: str
    ) -> DataAsset:

        self.authorize(actor_id, "asset:read")

        asset = self.assets.get(asset_id)

        if asset is None:
            raise ValidationError("Asset not found.")

        if not self.can_process(asset_id, subject_id):
            raise PolicyViolation(
                "Processing lacks a valid legal basis."
            )

        self.audit.record(
            actor_id,
            AuditAction.READ,
            "data_asset",
            asset_id
        )

        return asset

    def add_policy(self, policy: Policy) -> None:
        if policy.policy_id in self.policies:
            raise ValidationError("Policy already exists.")

        self.policies[policy.policy_id] = policy

    def evaluate_asset(self, asset_id: str) -> list[ComplianceFinding]:

        asset = self.assets.get(asset_id)

        if asset is None:
            raise ValidationError("Asset not found.")

        findings = []

        def add(risk, description, framework="ISO27001"):
            finding = ComplianceFinding(
                finding_id=secrets.token_hex(6),
                asset_id=asset_id,
                risk=risk,
                description=description,
                framework_code=framework
            )
            findings.append(finding)

        if not asset.encrypted:
            add(
                RiskLevel.CRITICAL,
                "Data encryption is not enabled."
            )

        if (
            asset.category == PrivacyCategory.SENSITIVE_PERSONAL
            and asset.legal_basis == LegalBasis.LEGITIMATE_INTEREST
        ):
            add(
                RiskLevel.HIGH,
                "Sensitive data requires additional legal and "
                "necessity assessment.",
                "GDPR"
            )

        if asset.retention_days > 3650:
            add(
                RiskLevel.MEDIUM,
                "Retention exceeds ten years and requires justification."
            )

        if not asset.framework_codes:
            add(
                RiskLevel.MEDIUM,
                "No regulatory framework is mapped."
            )

        self.findings.extend(findings)

        return findings

    def submit_subject_request(
        self,
        actor_id: str,
        subject_id: str,
        request_type: DataSubjectRequestType,
        deadline_days: int = 30
    ) -> SubjectRequest:

        self.authorize(actor_id, "request:manage")

        if not subject_id.strip():
            raise ValidationError("Subject identifier is required.")

        if deadline_days <= 0:
            raise ValidationError("Deadline must be positive.")

        request = SubjectRequest(
            request_id=secrets.token_hex(8),
            subject_id=subject_id,
            request_type=request_type,
            status=RequestStatus.RECEIVED,
            received_at=utc_now(),
            deadline=utc_now() + timedelta(days=deadline_days)
        )

        self.requests[request.request_id] = request

        self.audit.record(
            actor_id,
            AuditAction.CREATE,
            "subject_request",
            request.request_id,
            {"type": request_type.value}
        )

        return request

    def transition_request(
        self,
        actor_id: str,
        request_id: str,
        new_status: RequestStatus
    ) -> None:

        self.authorize(actor_id, "request:manage")

        request = self.requests.get(request_id)

        if request is None:
            raise ValidationError("Request not found.")

        allowed = {
            RequestStatus.RECEIVED: {
                RequestStatus.VERIFIED,
                RequestStatus.REJECTED
            },
            RequestStatus.VERIFIED: {
                RequestStatus.IN_PROGRESS,
                RequestStatus.REJECTED
            },
            RequestStatus.IN_PROGRESS: {
                RequestStatus.COMPLETED,
                RequestStatus.REJECTED
            },
            RequestStatus.COMPLETED: set(),
            RequestStatus.REJECTED: set()
        }

        if new_status not in allowed[request.status]:
            raise PolicyViolation("Invalid request state transition.")

        request.status = new_status

        self.audit.record(
            actor_id,
            AuditAction.REQUEST_PROCESSED,
            "subject_request",
            request_id,
            {"status": new_status.value}
        )

    def enforce_retention(self, actor_id: str) -> list[str]:
        self.authorize(actor_id, "retention:manage")

        now = utc_now()
        deleted = []

        for asset in self.assets.values():
            expiry = asset.created_at + timedelta(
                days=asset.retention_days
            )

            if asset.active and now > expiry:
                asset.active = False
                deleted.append(asset.asset_id)

                self.audit.record(
                    actor_id,
                    AuditAction.DELETE,
                    "data_asset",
                    asset.asset_id,
                    {"reason": "retention_expired"}
                )

        return deleted

    def report(self) -> dict:
        return {
            "total_assets": len(self.assets),
            "active_assets": sum(
                asset.active for asset in self.assets.values()
            ),
            "privacy_categories": {
                category.value: sum(
                    asset.category == category
                    for asset in self.assets.values()
                )
                for category in PrivacyCategory
            },
            "consents": {
                status.value: sum(
                    consent.status == status
                    for consent in self.consents.values()
                )
                for status in ConsentStatus
            },
            "open_findings": sum(
                not finding.resolved for finding in self.findings
            ),
            "requests": {
                status.value: sum(
                    request.status == status
                    for request in self.requests.values()
                )
                for status in RequestStatus
            },
            "audit_integrity": self.audit.verify_integrity()
        }


def demonstration() -> ComplianceManager:

    manager = ComplianceManager()

    manager.register_user(
        User(
            "compliance_admin",
            "COMPLIANCE_ADMIN",
            {
                "asset:create",
                "asset:read",
                "consent:manage",
                "request:manage",
                "retention:manage"
            }
        )
    )

    manager.register_user(
        User(
            "analyst",
            "ANALYST",
            {"asset:read"}
        )
    )

    asset = DataAsset(
        asset_id="ASSET-001",
        name="Customer Identity Records",
        owner="Data Governance Office",
        category=PrivacyCategory.PERSONAL,
        purpose="Customer account administration",
        legal_basis=LegalBasis.CONSENT,
        framework_codes={"GDPR", "DPDPA"},
        retention_days=730,
        encrypted=True
    )

    manager.register_asset("compliance_admin", asset)

    consent = Consent(
        consent_id="CONSENT-001",
        subject_id="SUBJECT-001",
        asset_id="ASSET-001",
        purpose="Customer account administration",
        status=ConsentStatus.GRANTED,
        granted_at=utc_now()
    )

    manager.grant_consent("compliance_admin", consent)

    manager.read_asset(
        "analyst",
        "ASSET-001",
        "SUBJECT-001"
    )

    request = manager.submit_subject_request(
        "compliance_admin",
        "SUBJECT-001",
        DataSubjectRequestType.ACCESS
    )

    manager.transition_request(
        "compliance_admin",
        request.request_id,
        RequestStatus.VERIFIED
    )

    manager.transition_request(
        "compliance_admin",
        request.request_id,
        RequestStatus.IN_PROGRESS
    )

    manager.transition_request(
        "compliance_admin",
        request.request_id,
        RequestStatus.COMPLETED
    )

    findings = manager.evaluate_asset("ASSET-001")

    print("\nCompliance findings:")

    for finding in findings:
        print(f"{finding.risk.value}: {finding.description}")

    manager.withdraw_consent(
        "compliance_admin",
        "CONSENT-001"
    )

    try:
        manager.read_asset(
            "analyst",
            "ASSET-001",
            "SUBJECT-001"
        )
    except PolicyViolation as error:
        print("\nExpected processing restriction:", error)

    print("\nCompliance report:")

    print(
        json.dumps(
            manager.report(),
            indent=2
        )
    )

    assert manager.audit.verify_integrity()

    return manager


class ComplianceTests(unittest.TestCase):

    def setUp(self):
        self.manager = ComplianceManager()

        self.manager.register_user(
            User(
                "admin",
                "ADMIN",
                {
                    "asset:create",
                    "asset:read",
                    "consent:manage",
                    "request:manage",
                    "retention:manage"
                }
            )
        )

    def test_sensitive_data_requires_encryption(self):
        with self.assertRaises(PolicyViolation):
            DataAsset(
                "A1",
                "Sensitive Records",
                "Owner",
                PrivacyCategory.SENSITIVE_PERSONAL,
                "Medical administration",
                LegalBasis.CONTRACT,
                {"GDPR"},
                encrypted=False
            )

    def test_unauthorized_operation(self):
        self.manager.register_user(
            User("reader", "READER", {"asset:read"})
        )

        with self.assertRaises(AuthorizationError):
            self.manager.authorize("reader", "asset:create")

    def test_consent_withdrawal(self):
        asset = DataAsset(
            "A2",
            "Customer Data",
            "Owner",
            PrivacyCategory.PERSONAL,
            "Account administration",
            LegalBasis.CONSENT,
            {"GDPR"}
        )

        self.manager.register_asset("admin", asset)

        consent = Consent(
            "C2",
            "S2",
            "A2",
            "Account administration",
            ConsentStatus.GRANTED,
            utc_now()
        )

        self.manager.grant_consent("admin", consent)

        self.assertTrue(self.manager.can_process("A2", "S2"))

        self.manager.withdraw_consent("admin", "C2")

        self.assertFalse(self.manager.can_process("A2", "S2"))

    def test_invalid_state_transition(self):
        request = self.manager.submit_subject_request(
            "admin",
            "S3",
            DataSubjectRequestType.ERASURE
        )

        with self.assertRaises(PolicyViolation):
            self.manager.transition_request(
                "admin",
                request.request_id,
                RequestStatus.COMPLETED
            )

    def test_audit_integrity(self):
        self.manager.audit.record(
            "admin",
            AuditAction.READ,
            "asset",
            "A1"
        )

        self.assertTrue(
            self.manager.audit.verify_integrity()
        )


if __name__ == "__main__":
    demonstration()

    print("\nRunning validation tests:")

    unittest.main(argv=["compliance.py"], exit=False)
