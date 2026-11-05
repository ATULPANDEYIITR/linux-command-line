#!/usr/bin/env python3
"""
Cloud Security Fundamentals
Demonstrates shared responsibility, cloud service models, security controls,
policy evaluation, configuration auditing, and risk assessment.

Python 3.10+
Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import defaultdict
import json
import logging
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("cloud_security")


class ServiceModel(Enum):
    IAAS = "IaaS"
    PAAS = "PaaS"
    SAAS = "SaaS"


class Responsibility(Enum):
    CUSTOMER = "Customer"
    PROVIDER = "Provider"
    SHARED = "Shared"


class ControlStatus(Enum):
    COMPLIANT = "Compliant"
    NON_COMPLIANT = "Non-compliant"
    NOT_APPLICABLE = "Not applicable"


class Severity(Enum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1


@dataclass(frozen=True)
class CloudControl:
    control_id: str
    name: str
    description: str
    customer_owned: bool
    provider_owned: bool

    @property
    def responsibility(self) -> Responsibility:
        if self.customer_owned and self.provider_owned:
            return Responsibility.SHARED
        if self.customer_owned:
            return Responsibility.CUSTOMER
        return Responsibility.PROVIDER


@dataclass
class CloudAsset:
    asset_id: str
    name: str
    service_model: ServiceModel
    environment: str
    public_access: bool = False
    encryption_at_rest: bool = False
    encryption_in_transit: bool = False
    mfa_enabled: bool = False
    logging_enabled: bool = False
    backup_enabled: bool = False
    least_privilege: bool = False
    patching_enabled: bool = False
    data_classification: str = "Internal"

    def validate(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("Asset ID cannot be empty")

        if not self.name.strip():
            raise ValueError("Asset name cannot be empty")

        if self.environment not in {
            "development", "testing", "staging", "production"
        }:
            raise ValueError("Invalid environment")

        if self.data_classification not in {
            "Public", "Internal", "Confidential", "Restricted"
        }:
            raise ValueError("Invalid data classification")


@dataclass
class Finding:
    asset_id: str
    control_id: str
    control_name: str
    responsibility: Responsibility
    status: ControlStatus
    severity: Severity
    recommendation: str


@dataclass
class SecurityReport:
    asset_id: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def risk_score(self) -> int:
        return sum(
            finding.severity.value
            for finding in self.findings
            if finding.status == ControlStatus.NON_COMPLIANT
        )

    @property
    def compliant(self) -> bool:
        return self.risk_score == 0


class SharedResponsibilityModel:
    """
    Simplified responsibility mapping.

    Actual responsibility boundaries depend on the provider,
    service configuration, managed-service agreement and deployment.
    """

    def __init__(self):
        self.controls: dict[str, CloudControl] = {
            "IDENTITY": CloudControl(
                "IDENTITY",
                "Identity and access management",
                "Authentication, authorization and account security",
                True, True
            ),
            "PHYSICAL": CloudControl(
                "PHYSICAL",
                "Physical infrastructure security",
                "Data center facilities and physical hardware",
                False, True
            ),
            "NETWORK": CloudControl(
                "NETWORK",
                "Network security",
                "Network segmentation and traffic protection",
                True, True
            ),
            "APPLICATION": CloudControl(
                "APPLICATION",
                "Application security",
                "Application vulnerabilities and secure development",
                True, False
            ),
            "DATA": CloudControl(
                "DATA",
                "Data protection",
                "Data classification, access and encryption configuration",
                True, True
            ),
            "HYPERVISOR": CloudControl(
                "HYPERVISOR",
                "Virtualization infrastructure",
                "Hypervisor and underlying virtualization security",
                False, True
            ),
            "OPERATING_SYSTEM": CloudControl(
                "OPERATING_SYSTEM",
                "Operating system security",
                "Guest operating system hardening and patching",
                True, False
            ),
            "MONITORING": CloudControl(
                "MONITORING",
                "Security monitoring",
                "Logging, alerting and incident detection",
                True, True
            ),
            "BACKUP": CloudControl(
                "BACKUP",
                "Backup and recovery",
                "Backup configuration, protection and recovery",
                True, True
            )
        }

    def get_responsibility(self, control_id: str) -> Responsibility:
        try:
            return self.controls[control_id].responsibility
        except KeyError:
            raise ValueError(f"Unknown control: {control_id}")

    def display(self) -> None:
        print("\nSHARED RESPONSIBILITY MODEL")
        print("-" * 75)

        for control in self.controls.values():
            print(
                f"{control.control_id:<20} "
                f"{control.responsibility.value:<12} "
                f"{control.name}"
            )


class SecurityPolicy:
    """Defines minimum security requirements for a cloud asset."""

    def __init__(
        self,
        require_encryption: bool = True,
        require_mfa: bool = True,
        require_logging: bool = True,
        require_backup: bool = True,
        require_least_privilege: bool = True,
        prohibit_public_production: bool = True,
        require_patching_for_iaas: bool = True
    ):
        self.require_encryption = require_encryption
        self.require_mfa = require_mfa
        self.require_logging = require_logging
        self.require_backup = require_backup
        self.require_least_privilege = require_least_privilege
        self.prohibit_public_production = prohibit_public_production
        self.require_patching_for_iaas = require_patching_for_iaas


class CloudSecurityAuditor:
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy

    def evaluate(self, asset: CloudAsset) -> SecurityReport:
        asset.validate()
        report = SecurityReport(asset_id=asset.asset_id)

        def check(
            control_id: str,
            name: str,
            condition: bool,
            severity: Severity,
            recommendation: str
        ) -> None:
            report.findings.append(
                Finding(
                    asset_id=asset.asset_id,
                    control_id=control_id,
                    control_name=name,
                    responsibility=Responsibility.CUSTOMER,
                    status=(
                        ControlStatus.COMPLIANT
                        if condition
                        else ControlStatus.NON_COMPLIANT
                    ),
                    severity=severity,
                    recommendation=recommendation
                )
            )

        check(
            "ENCRYPTION",
            "Encryption at rest",
            asset.encryption_at_rest
            if self.policy.require_encryption else True,
            Severity.HIGH,
            "Enable encryption at rest using managed or customer-managed keys."
        )

        check(
            "TLS",
            "Encryption in transit",
            asset.encryption_in_transit
            if self.policy.require_encryption else True,
            Severity.HIGH,
            "Require TLS for network communications."
        )

        check(
            "MFA",
            "Multi-factor authentication",
            asset.mfa_enabled if self.policy.require_mfa else True,
            Severity.CRITICAL,
            "Enforce MFA for privileged and user accounts."
        )

        check(
            "LOGGING",
            "Security logging",
            asset.logging_enabled if self.policy.require_logging else True,
            Severity.HIGH,
            "Enable centralized security logging and monitoring."
        )

        check(
            "BACKUP",
            "Backup protection",
            asset.backup_enabled if self.policy.require_backup else True,
            Severity.HIGH,
            "Enable protected backups and test restoration."
        )

        check(
            "LEAST_PRIVILEGE",
            "Least privilege",
            asset.least_privilege
            if self.policy.require_least_privilege else True,
            Severity.HIGH,
            "Restrict permissions to the minimum required."
        )

        check(
            "PUBLIC_ACCESS",
            "Public access restrictions",
            not (
                asset.public_access
                and asset.environment == "production"
                and self.policy.prohibit_public_production
            ),
            Severity.CRITICAL,
            "Remove unintended public exposure and restrict network access."
        )

        # Guest operating system patching is a customer responsibility
        # in this simplified IaaS model.
        patching_required = (
            asset.service_model == ServiceModel.IAAS
            and self.policy.require_patching_for_iaas
        )

        if patching_required:
            check(
                "PATCHING",
                "Guest operating system patching",
                asset.patching_enabled,
                Severity.HIGH,
                "Establish a tested guest operating system patching process."
            )

        return report


class CloudSecurityPlatform:
    """Manages assets, auditing and report generation."""

    def __init__(self, policy: SecurityPolicy):
        self.assets: dict[str, CloudAsset] = {}
        self.auditor = CloudSecurityAuditor(policy)

    def register_asset(self, asset: CloudAsset) -> None:
        asset.validate()

        if asset.asset_id in self.assets:
            raise ValueError(f"Duplicate asset ID: {asset.asset_id}")

        self.assets[asset.asset_id] = asset
        logger.info("Registered asset %s", asset.asset_id)

    def audit_all(self) -> list[SecurityReport]:
        reports = []

        for asset in self.assets.values():
            try:
                reports.append(self.auditor.evaluate(asset))
            except ValueError:
                logger.exception("Unable to audit asset %s", asset.asset_id)

        return reports

    @staticmethod
    def generate_summary(reports: list[SecurityReport]) -> dict:
        severity_counts = defaultdict(int)
        compliant_assets = 0
        total_findings = 0

        for report in reports:
            if report.compliant:
                compliant_assets += 1

            for finding in report.findings:
                if finding.status == ControlStatus.NON_COMPLIANT:
                    severity_counts[finding.severity.name] += 1
                    total_findings += 1

        return {
            "total_assets": len(reports),
            "compliant_assets": compliant_assets,
            "non_compliant_assets": len(reports) - compliant_assets,
            "total_findings": total_findings,
            "severity_distribution": dict(severity_counts)
        }

    @staticmethod
    def export_json(
        reports: list[SecurityReport],
        output_file: str
    ) -> None:
        data = []

        for report in reports:
            data.append({
                "asset_id": report.asset_id,
                "risk_score": report.risk_score,
                "compliant": report.compliant,
                "findings": [
                    {
                        "control_id": finding.control_id,
                        "control_name": finding.control_name,
                        "responsibility": finding.responsibility.value,
                        "status": finding.status.value,
                        "severity": finding.severity.name,
                        "recommendation": finding.recommendation
                    }
                    for finding in report.findings
                ]
            })

        path = Path(output_file)
        path.write_text(
            json.dumps(data, indent=4),
            encoding="utf-8"
        )


def display_reports(reports: list[SecurityReport]) -> None:
    print("\nCLOUD SECURITY AUDIT")
    print("=" * 90)

    for report in reports:
        print(
            f"\nAsset: {report.asset_id} | "
            f"Risk score: {report.risk_score} | "
            f"Compliant: {report.compliant}"
        )

        for finding in report.findings:
            if finding.status == ControlStatus.NON_COMPLIANT:
                print(
                    f"  [{finding.severity.name}] "
                    f"{finding.control_name}: "
                    f"{finding.recommendation}"
                )


def run_tests() -> None:
    model = SharedResponsibilityModel()

    assert model.get_responsibility("PHYSICAL") == Responsibility.PROVIDER
    assert model.get_responsibility("DATA") == Responsibility.SHARED

    policy = SecurityPolicy()
    auditor = CloudSecurityAuditor(policy)

    secure_asset = CloudAsset(
        asset_id="CLOUD-001",
        name="Production API",
        service_model=ServiceModel.IAAS,
        environment="production",
        encryption_at_rest=True,
        encryption_in_transit=True,
        mfa_enabled=True,
        logging_enabled=True,
        backup_enabled=True,
        least_privilege=True,
        patching_enabled=True
    )

    secure_report = auditor.evaluate(secure_asset)
    assert secure_report.compliant

    insecure_asset = CloudAsset(
        asset_id="CLOUD-002",
        name="Public Storage",
        service_model=ServiceModel.SAAS,
        environment="production",
        public_access=True
    )

    insecure_report = auditor.evaluate(insecure_asset)
    assert not insecure_report.compliant
    assert insecure_report.risk_score > 0

    try:
        CloudAsset(
            asset_id="",
            name="Invalid",
            service_model=ServiceModel.IAAS,
            environment="production"
        ).validate()
        raise AssertionError("Invalid asset should fail validation")
    except ValueError:
        pass

    print("\nAll security tests passed.")


def main() -> None:
    responsibility_model = SharedResponsibilityModel()
    responsibility_model.display()

    platform = CloudSecurityPlatform(SecurityPolicy())

    assets = [
        CloudAsset(
            asset_id="AWS-EC2-001",
            name="Production application server",
            service_model=ServiceModel.IAAS,
            environment="production",
            encryption_at_rest=True,
            encryption_in_transit=True,
            mfa_enabled=True,
            logging_enabled=True,
            backup_enabled=True,
            least_privilege=True,
            patching_enabled=True
        ),
        CloudAsset(
            asset_id="AZURE-APP-002",
            name="Managed application service",
            service_model=ServiceModel.PAAS,
            environment="production",
            public_access=False,
            encryption_at_rest=True,
            encryption_in_transit=True,
            mfa_enabled=False,
            logging_enabled=True,
            backup_enabled=True,
            least_privilege=False
        ),
        CloudAsset(
            asset_id="SAAS-003",
            name="Enterprise document platform",
            service_model=ServiceModel.SAAS,
            environment="production",
            public_access=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            mfa_enabled=False,
            logging_enabled=False,
            backup_enabled=False,
            least_privilege=False
        )
    ]

    for asset in assets:
        platform.register_asset(asset)

    reports = platform.audit_all()

    display_reports(reports)

    print("\nSECURITY SUMMARY")
    print(json.dumps(
        platform.generate_summary(reports),
        indent=4
    ))

    platform.export_json(reports, "cloud_security_audit.json")
    print("\nReport saved to cloud_security_audit.json")

    run_tests()


if __name__ == "__main__":
    main()
