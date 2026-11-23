#!/usr/bin/env python3
"""
Container Security: Image Scanning, Minimal Images, Secrets,
Runtime Security, and Vulnerability Management.

Python 3.10+
Standard-library only.
"""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ============================================================
# 1. DOMAIN TYPES
# ============================================================

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingType(str, Enum):
    VULNERABILITY = "VULNERABILITY"
    MISCONFIGURATION = "MISCONFIGURATION"
    SECRET = "SECRET"
    COMPLIANCE = "COMPLIANCE"


class DeploymentStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class Vulnerability:
    cve_id: str
    package: str
    installed_version: str
    fixed_version: Optional[str]
    severity: Severity
    description: str
    exploitable: bool = False


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    package_type: str = "APPLICATION"


@dataclass
class ContainerImage:
    name: str
    tag: str
    base_image: str
    packages: list[Package]
    vulnerabilities: list[Vulnerability]
    exposed_ports: list[int] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    user: str = "root"
    entrypoint: list[str] = field(default_factory=list)
    layers: int = 1
    size_mb: float = 100.0
    signed: bool = False
    immutable_digest: Optional[str] = None
    healthcheck: bool = False

    @property
    def reference(self) -> str:
        return f"{self.name}:{self.tag}"


@dataclass(frozen=True)
class Finding:
    finding_type: FindingType
    severity: Severity
    resource: str
    description: str
    remediation: str


@dataclass
class ScanReport:
    image_reference: str
    image_digest: str
    scan_timestamp: str
    findings: list[Finding]
    status: DeploymentStatus

    def severity_counts(self) -> dict[str, int]:
        counts = {severity.value: 0 for severity in Severity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "image": self.image_reference,
            "digest": self.image_digest,
            "timestamp": self.scan_timestamp,
            "status": self.status.value,
            "severity_counts": self.severity_counts(),
            "findings": [
                {
                    "type": finding.finding_type.value,
                    "severity": finding.severity.value,
                    "resource": finding.resource,
                    "description": finding.description,
                    "remediation": finding.remediation,
                }
                for finding in self.findings
            ],
        }


# ============================================================
# 2. IMAGE IDENTITY AND VALIDATION
# ============================================================

def calculate_image_digest(image: ContainerImage) -> str:
    """Calculate a deterministic demonstration fingerprint."""

    payload = {
        "name": image.name,
        "tag": image.tag,
        "base": image.base_image,
        "packages": sorted(
            (p.name, p.version, p.package_type)
            for p in image.packages
        ),
        "vulnerabilities": sorted(
            (v.cve_id, v.package, v.installed_version)
            for v in image.vulnerabilities
        ),
        "user": image.user,
        "ports": sorted(image.exposed_ports),
        "entrypoint": image.entrypoint,
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_image(image: ContainerImage) -> None:
    if not image.name.strip():
        raise ValueError("Image name cannot be empty.")

    if not image.tag.strip():
        raise ValueError("Image tag cannot be empty.")

    if image.size_mb <= 0:
        raise ValueError("Image size must be positive.")

    if image.layers < 1:
        raise ValueError("An image must contain at least one layer.")

    if not image.base_image.strip():
        raise ValueError("Base image is required.")

    if any(port < 1 or port > 65535 for port in image.exposed_ports):
        raise ValueError("Invalid exposed port.")

    package_names = [p.name for p in image.packages]

    if len(package_names) != len(set(package_names)):
        raise ValueError("Duplicate package names are not allowed.")


# ============================================================
# 3. VULNERABILITY SCANNING
# ============================================================

class VulnerabilityScanner:

    def scan(self, image: ContainerImage) -> list[Finding]:
        findings = []

        for vulnerability in image.vulnerabilities:
            findings.append(
                Finding(
                    finding_type=FindingType.VULNERABILITY,
                    severity=vulnerability.severity,
                    resource=vulnerability.package,
                    description=(
                        f"{vulnerability.cve_id}: "
                        f"{vulnerability.description}"
                    ),
                    remediation=(
                        f"Upgrade {vulnerability.package} to "
                        f"{vulnerability.fixed_version}"
                        if vulnerability.fixed_version
                        else "Replace the affected package or apply "
                             "an approved mitigation."
                    )
                )
            )

        return findings


# ============================================================
# 4. SECRET DETECTION
# ============================================================

class SecretScanner:
    """
    Demonstration scanner.

    Production scanners should inspect image layers, build logs,
    configuration files, source files and mounted secrets.
    """

    PATTERNS = {
        "AWS_ACCESS_KEY": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "PRIVATE_KEY": re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
        "PASSWORD_ASSIGNMENT": re.compile(
            r"(?i)(password|passwd|secret|api_key)\s*=\s*"
            r"[^$\s][^\s]{5,}"
        ),
        "TOKEN_ASSIGNMENT": re.compile(
            r"(?i)(access_token|auth_token)\s*=\s*"
            r"[^$\s][^\s]{5,}"
        ),
    }

    def scan(self, environment: dict[str, str]) -> list[Finding]:
        findings = []

        for key, value in environment.items():
            for secret_type, pattern in self.PATTERNS.items():
                if pattern.search(f"{key}={value}"):
                    findings.append(
                        Finding(
                            FindingType.SECRET,
                            Severity.CRITICAL,
                            key,
                            f"Potential {secret_type} detected.",
                            "Remove the secret, rotate its credential, "
                            "and use a managed secret injection mechanism."
                        )
                    )
                    break

        return findings


# ============================================================
# 5. IMAGE CONFIGURATION AND MINIMAL IMAGE ANALYSIS
# ============================================================

class ConfigurationScanner:

    def scan(self, image: ContainerImage) -> list[Finding]:
        findings = []

        if image.user.strip().lower() in ("root", "0", "0:0"):
            findings.append(
                Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.HIGH,
                    "USER",
                    "Container executes as root.",
                    "Configure a dedicated non-root runtime user."
                )
            )

        if not image.healthcheck:
            findings.append(
                Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.LOW,
                    "HEALTHCHECK",
                    "No container health check is configured.",
                    "Configure a meaningful health check."
                )
            )

        if image.size_mb > 200:
            findings.append(
                Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.MEDIUM,
                    "IMAGE_SIZE",
                    f"Image size is {image.size_mb} MB.",
                    "Use a minimal runtime image and remove build dependencies."
                )
            )

        if image.layers > 15:
            findings.append(
                Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.LOW,
                    "IMAGE_LAYERS",
                    f"Image contains {image.layers} layers.",
                    "Consolidate unnecessary layers."
                )
            )

        if not image.signed:
            findings.append(
                Finding(
                    FindingType.COMPLIANCE,
                    Severity.HIGH,
                    "IMAGE_SIGNATURE",
                    "Image signature has not been verified.",
                    "Sign the image and enforce signature verification."
                )
            )

        if image.tag.lower() == "latest":
            findings.append(
                Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.MEDIUM,
                    "IMAGE_TAG",
                    "Mutable latest tag is used.",
                    "Deploy an immutable image digest."
                )
            )

        if not image.entrypoint:
            findings.append(
                Finding(
                    FindingType.MISCONFIGURATION,
                    Severity.MEDIUM,
                    "ENTRYPOINT",
                    "No explicit entrypoint is configured.",
                    "Define an explicit executable entrypoint."
                )
            )

        if image.immutable_digest is None:
            findings.append(
                Finding(
                    FindingType.COMPLIANCE,
                    Severity.MEDIUM,
                    "IMAGE_DIGEST",
                    "No immutable deployment digest is recorded.",
                    "Record and deploy the verified image digest."
                )
            )

        return findings


# ============================================================
# 6. SECURITY POLICY ENGINE
# ============================================================

@dataclass(frozen=True)
class SecurityPolicy:
    maximum_critical: int = 0
    maximum_high: int = 0
    maximum_medium: int = 5
    require_non_root: bool = True
    require_signature: bool = True
    require_digest: bool = True
    require_healthcheck: bool = True
    block_secrets: bool = True


class PolicyEngine:

    def __init__(self, policy: SecurityPolicy):
        self.policy = policy

    def evaluate(
        self,
        image: ContainerImage,
        findings: list[Finding]
    ) -> DeploymentStatus:

        counts = {severity: 0 for severity in Severity}

        for finding in findings:
            counts[finding.severity] += 1

        if counts[Severity.CRITICAL] > self.policy.maximum_critical:
            return DeploymentStatus.BLOCKED

        if counts[Severity.HIGH] > self.policy.maximum_high:
            return DeploymentStatus.BLOCKED

        if counts[Severity.MEDIUM] > self.policy.maximum_medium:
            return DeploymentStatus.BLOCKED

        if self.policy.block_secrets:
            if any(
                finding.finding_type == FindingType.SECRET
                for finding in findings
            ):
                return DeploymentStatus.BLOCKED

        if self.policy.require_non_root:
            if image.user.strip().lower() in ("root", "0", "0:0"):
                return DeploymentStatus.BLOCKED

        if self.policy.require_signature and not image.signed:
            return DeploymentStatus.BLOCKED

        if self.policy.require_digest and not image.immutable_digest:
            return DeploymentStatus.BLOCKED

        if self.policy.require_healthcheck and not image.healthcheck:
            return DeploymentStatus.BLOCKED

        return DeploymentStatus.APPROVED


# ============================================================
# 7. COMPLETE IMAGE SCANNING PIPELINE
# ============================================================

class ContainerSecurityPlatform:

    def __init__(self, policy: SecurityPolicy):
        self.vulnerability_scanner = VulnerabilityScanner()
        self.secret_scanner = SecretScanner()
        self.configuration_scanner = ConfigurationScanner()
        self.policy_engine = PolicyEngine(policy)

    def scan(self, image: ContainerImage) -> ScanReport:
        validate_image(image)

        findings = []

        findings.extend(
            self.vulnerability_scanner.scan(image)
        )

        findings.extend(
            self.secret_scanner.scan(image.environment)
        )

        findings.extend(
            self.configuration_scanner.scan(image)
        )

        status = self.policy_engine.evaluate(image, findings)

        return ScanReport(
            image_reference=image.reference,
            image_digest=calculate_image_digest(image),
            scan_timestamp=datetime.now(timezone.utc).isoformat(),
            findings=findings,
            status=status
        )


# ============================================================
# 8. RUNTIME SECURITY
# ============================================================

class RuntimeEventType(str, Enum):
    EXEC = "EXEC"
    NETWORK = "NETWORK"
    FILE_WRITE = "FILE_WRITE"
    PRIVILEGE_CHANGE = "PRIVILEGE_CHANGE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RuntimeEvent:
    container_id: str
    event_type: RuntimeEventType
    process: str
    destination: Optional[str] = None
    privileged: bool = False
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class RuntimeDecision:
    allowed: bool
    reason: str
    severity: Severity


class RuntimeSecurityEngine:

    BLOCKED_PROCESSES = {
        "nc",
        "ncat",
        "socat",
        "tcpdump",
        "chroot"
    }

    BLOCKED_PATHS = {
        "/etc/shadow",
        "/etc/passwd",
        "/root/.ssh/authorized_keys"
    }

    def evaluate(self, event: RuntimeEvent) -> RuntimeDecision:

        if event.privileged:
            return RuntimeDecision(
                False,
                "Unexpected privileged execution.",
                Severity.CRITICAL
            )

        if event.event_type == RuntimeEventType.EXEC:
            process_name = event.process.split("/")[-1].lower()

            if process_name in self.BLOCKED_PROCESSES:
                return RuntimeDecision(
                    False,
                    "Execution of a restricted utility.",
                    Severity.HIGH
                )

        if event.event_type == RuntimeEventType.FILE_WRITE:
            if event.destination in self.BLOCKED_PATHS:
                return RuntimeDecision(
                    False,
                    "Write to a protected system file.",
                    Severity.CRITICAL
                )

        if event.event_type == RuntimeEventType.UNKNOWN:
            return RuntimeDecision(
                False,
                "Unrecognized runtime activity.",
                Severity.HIGH
            )

        return RuntimeDecision(
            True,
            "Activity permitted by runtime policy.",
            Severity.INFO
        )


# ============================================================
# 9. VULNERABILITY REMEDIATION TRACKING
# ============================================================

class RemediationStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"


@dataclass
class VulnerabilityTicket:
    ticket_id: str
    cve_id: str
    image_reference: str
    severity: Severity
    status: RemediationStatus
    owner: str
    due_date: str

    def update_status(self, new_status: RemediationStatus) -> None:
        allowed = {
            RemediationStatus.OPEN: {
                RemediationStatus.IN_PROGRESS,
                RemediationStatus.ACCEPTED_RISK
            },
            RemediationStatus.IN_PROGRESS: {
                RemediationStatus.MITIGATED,
                RemediationStatus.RESOLVED,
                RemediationStatus.ACCEPTED_RISK
            },
            RemediationStatus.MITIGATED: {
                RemediationStatus.RESOLVED,
                RemediationStatus.IN_PROGRESS
            },
            RemediationStatus.ACCEPTED_RISK: {
                RemediationStatus.OPEN,
                RemediationStatus.IN_PROGRESS
            },
            RemediationStatus.RESOLVED: {
                RemediationStatus.OPEN
            }
        }

        if new_status not in allowed[self.status]:
            raise ValueError(
                f"Invalid remediation transition: "
                f"{self.status.value} -> {new_status.value}"
            )

        self.status = new_status


# ============================================================
# 10. REALISTIC TEST SCENARIO
# ============================================================

def create_unsafe_image() -> ContainerImage:
    return ContainerImage(
        name="payment-service",
        tag="latest",
        base_image="ubuntu:latest",
        packages=[
            Package("openssl", "1.0.2"),
            Package("curl", "7.50.0"),
            Package("python", "3.12")
        ],
        vulnerabilities=[
            Vulnerability(
                "CVE-2025-10001",
                "openssl",
                "1.0.2",
                "3.0.15",
                Severity.CRITICAL,
                "Critical cryptographic vulnerability.",
                True
            ),
            Vulnerability(
                "CVE-2025-10002",
                "curl",
                "7.50.0",
                "8.10.0",
                Severity.HIGH,
                "Network request handling vulnerability."
            )
        ],
        exposed_ports=[22, 8080],
        environment={
            "DATABASE_PASSWORD": "production_password_123",
            "APP_MODE": "production"
        },
        user="root",
        entrypoint=["python", "app.py"],
        layers=24,
        size_mb=850,
        signed=False,
        healthcheck=False
    )


def create_secure_image() -> ContainerImage:
    image = ContainerImage(
        name="payment-service",
        tag="2.1.0",
        base_image="python:3.12-slim",
        packages=[
            Package("python", "3.12"),
            Package("application", "2.1.0")
        ],
        vulnerabilities=[],
        exposed_ports=[8080],
        environment={
            "APP_MODE": "production",
            "DATABASE_HOST": "database.internal"
        },
        labels={
            "maintainer": "security-team",
            "environment": "production"
        },
        user="10001",
        entrypoint=["python", "-m", "payment_service"],
        layers=7,
        size_mb=95,
        signed=True,
        healthcheck=True
    )

    image.immutable_digest = calculate_image_digest(image)
    return image


def run_tests() -> None:
    policy = SecurityPolicy(
        maximum_critical=0,
        maximum_high=0,
        maximum_medium=3,
        require_non_root=True,
        require_signature=True,
        require_digest=True,
        require_healthcheck=True,
        block_secrets=True
    )

    platform = ContainerSecurityPlatform(policy)

    unsafe = create_unsafe_image()
    unsafe_report = platform.scan(unsafe)

    assert unsafe_report.status == DeploymentStatus.BLOCKED
    assert any(
        f.finding_type == FindingType.SECRET
        for f in unsafe_report.findings
    )

    secure = create_secure_image()
    secure_report = platform.scan(secure)

    assert secure_report.status == DeploymentStatus.APPROVED
    assert secure_report.findings == []

    runtime = RuntimeSecurityEngine()

    permitted_event = RuntimeEvent(
        "container-101",
        RuntimeEventType.EXEC,
        "/usr/local/bin/python"
    )

    prohibited_event = RuntimeEvent(
        "container-101",
        RuntimeEventType.EXEC,
        "/usr/bin/nc",
        privileged=False
    )

    assert runtime.evaluate(permitted_event).allowed
    assert not runtime.evaluate(prohibited_event).allowed

    ticket = VulnerabilityTicket(
        "SEC-1001",
        "CVE-2025-10001",
        unsafe.reference,
        Severity.CRITICAL,
        RemediationStatus.OPEN,
        "platform-team",
        "2026-11-25"
    )

    ticket.update_status(RemediationStatus.IN_PROGRESS)

    assert ticket.status == RemediationStatus.IN_PROGRESS

    print("All container security tests passed.")


# ============================================================
# 11. EXECUTION AND REPORTING
# ============================================================

def main() -> None:
    run_tests()

    platform = ContainerSecurityPlatform(
        SecurityPolicy()
    )

    images = [
        create_unsafe_image(),
        create_secure_image()
    ]

    for image in images:
        report = platform.scan(image)

        print("\n" + "=" * 65)
        print(f"IMAGE: {image.reference}")
        print("=" * 65)

        print(
            json.dumps(
                report.to_dict(),
                indent=2
            )
        )

        print(
            f"\nDEPLOYMENT DECISION: {report.status.value}"
        )


if __name__ == "__main__":
    main()
