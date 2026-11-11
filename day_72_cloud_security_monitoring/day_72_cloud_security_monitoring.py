#!/usr/bin/env python3
"""
Cloud Security Monitoring
-------------------------
A self-contained cloud security monitoring and incident investigation system.

Features:
- Structured cloud audit log ingestion
- Log normalization and validation
- Authentication and authorization monitoring
- Failed-login and privilege-escalation detection
- IP-based anomaly detection
- Security alert correlation
- Incident lifecycle management
- Risk scoring and severity classification
- Audit trail preservation
- JSON file persistence
- Automated tests and reporting

Python 3.10+
Uses only the standard library.
"""

from __future__ import annotations

import json
import logging
import hashlib
import ipaddress
import statistics
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

LOGGER = logging.getLogger("cloud_security")

DATA_DIRECTORY = Path("cloud_security_data")
LOG_FILE = DATA_DIRECTORY / "security_logs.jsonl"
INCIDENT_FILE = DATA_DIRECTORY / "incidents.json"

MAX_LOG_SIZE = 100_000
FAILED_LOGIN_THRESHOLD = 5
PRIVILEGE_CHANGE_THRESHOLD = 3
ANOMALY_THRESHOLD = 70


# ---------------------------------------------------------
# ENUMERATIONS
# ---------------------------------------------------------

class EventType(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    API_ACCESS = "api_access"
    PERMISSION_CHANGE = "permission_change"
    RESOURCE_CREATED = "resource_created"
    RESOURCE_DELETED = "resource_deleted"
    CONFIGURATION_CHANGE = "configuration_change"
    DATA_ACCESS = "data_access"
    NETWORK_ACCESS = "network_access"
    SECURITY_GROUP_CHANGE = "security_group_change"
    SECRET_ACCESS = "secret_access"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


# ---------------------------------------------------------
# EXCEPTIONS
# ---------------------------------------------------------

class SecurityMonitoringError(Exception):
    pass


class InvalidLogError(SecurityMonitoringError):
    pass


class IncidentTransitionError(SecurityMonitoringError):
    pass


class IntegrityError(SecurityMonitoringError):
    pass


# ---------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------

@dataclass(frozen=True)
class SecurityEvent:
    event_id: str
    timestamp: datetime
    event_type: EventType
    user_id: str
    source_ip: str
    resource: str
    action: str
    success: bool
    region: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise InvalidLogError("Timestamp must include timezone.")

        if not self.user_id or not self.resource or not self.action:
            raise InvalidLogError("Required event fields are missing.")

        try:
            ipaddress.ip_address(self.source_ip)
        except ValueError as exc:
            raise InvalidLogError("Invalid source IP address.") from exc

        if len(self.metadata) > 50:
            raise InvalidLogError("Metadata contains too many fields.")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["event_type"] = self.event_type.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityEvent:
        return cls(
            event_id=str(data["event_id"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=EventType(data["event_type"]),
            user_id=str(data["user_id"]),
            source_ip=str(data["source_ip"]),
            resource=str(data["resource"]),
            action=str(data["action"]),
            success=bool(data["success"]),
            region=str(data["region"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class SecurityAlert:
    alert_id: str
    rule_id: str
    timestamp: datetime
    user_id: str
    severity: Severity
    description: str
    risk_score: int
    event_ids: list[str]
    indicators: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "severity": self.severity.value,
            "description": self.description,
            "risk_score": self.risk_score,
            "event_ids": self.event_ids,
            "indicators": self.indicators
        }


@dataclass
class SecurityIncident:
    incident_id: str
    title: str
    severity: Severity
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    alert_ids: list[str]
    assigned_to: Optional[str] = None
    investigation_notes: list[str] = field(default_factory=list)
    evidence_hashes: list[str] = field(default_factory=list)

    def transition(self, new_status: IncidentStatus) -> None:
        allowed = {
            IncidentStatus.OPEN: {
                IncidentStatus.INVESTIGATING,
                IncidentStatus.CLOSED
            },
            IncidentStatus.INVESTIGATING: {
                IncidentStatus.CONTAINED,
                IncidentStatus.RESOLVED,
                IncidentStatus.CLOSED
            },
            IncidentStatus.CONTAINED: {
                IncidentStatus.INVESTIGATING,
                IncidentStatus.RESOLVED
            },
            IncidentStatus.RESOLVED: {
                IncidentStatus.CLOSED,
                IncidentStatus.INVESTIGATING
            },
            IncidentStatus.CLOSED: set()
        }

        if new_status not in allowed[self.status]:
            raise IncidentTransitionError(
                f"Invalid transition: {self.status.value} "
                f"to {new_status.value}"
            )

        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------
# LOG NORMALIZATION AND STORAGE
# ---------------------------------------------------------

class LogNormalizer:

    @staticmethod
    def normalize(raw: dict[str, Any]) -> SecurityEvent:
        required = {
            "timestamp", "event_type", "user_id",
            "source_ip", "resource", "action",
            "success", "region"
        }

        missing = required - raw.keys()

        if missing:
            raise InvalidLogError(
                f"Missing fields: {sorted(missing)}"
            )

        try:
            timestamp = datetime.fromisoformat(
                str(raw["timestamp"]).replace("Z", "+00:00")
            )

            if timestamp.tzinfo is None:
                raise InvalidLogError(
                    "Timezone information is required."
                )

            return SecurityEvent(
                event_id=str(raw.get("event_id", uuid4())),
                timestamp=timestamp,
                event_type=EventType(raw["event_type"]),
                user_id=str(raw["user_id"]),
                source_ip=str(raw["source_ip"]),
                resource=str(raw["resource"]),
                action=str(raw["action"]),
                success=raw["success"],
                region=str(raw["region"]),
                metadata=raw.get("metadata", {})
            )

        except (ValueError, TypeError) as exc:
            raise InvalidLogError(
                f"Log normalization failed: {exc}"
            ) from exc


class AuditLogStore:

    def __init__(self, path: Path = LOG_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[SecurityEvent] = []
        self._event_ids: set[str] = set()
        self._last_hash = "GENESIS"

    def add(self, event: SecurityEvent) -> None:
        if event.event_id in self._event_ids:
            raise InvalidLogError("Duplicate event identifier.")

        if len(self.events) >= MAX_LOG_SIZE:
            raise SecurityMonitoringError("Event capacity reached.")

        record = event.to_dict()

        canonical = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":")
        )

        digest = hashlib.sha256(
            (self._last_hash + canonical).encode()
        ).hexdigest()

        record["_previous_hash"] = self._last_hash
        record["_record_hash"] = digest

        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

        self._last_hash = digest
        self.events.append(event)
        self._event_ids.add(event.event_id)

    def verify_integrity(self) -> bool:
        previous_hash = "GENESIS"

        if not self.path.exists():
            return True

        with self.path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, 1):
                record = json.loads(line)

                supplied_previous = record.pop("_previous_hash")
                supplied_hash = record.pop("_record_hash")

                if supplied_previous != previous_hash:
                    raise IntegrityError(
                        f"Broken chain at line {line_number}"
                    )

                canonical = json.dumps(
                    record,
                    sort_keys=True,
                    separators=(",", ":")
                )

                expected = hashlib.sha256(
                    (previous_hash + canonical).encode()
                ).hexdigest()

                if expected != supplied_hash:
                    raise IntegrityError(
                        f"Tampering detected at line {line_number}"
                    )

                previous_hash = supplied_hash

        return True


# ---------------------------------------------------------
# BEHAVIORAL BASELINES
# ---------------------------------------------------------

class BehavioralBaseline:

    def __init__(self):
        self.user_ips: dict[str, Counter] = defaultdict(Counter)
        self.user_hours: dict[str, Counter] = defaultdict(Counter)
        self.event_counts: Counter = Counter()

    def learn(self, events: list[SecurityEvent]) -> None:
        for event in events:
            if event.success:
                self.user_ips[event.user_id][event.source_ip] += 1
                self.user_hours[event.user_id][
                    event.timestamp.hour
                ] += 1

            self.event_counts[event.user_id] += 1

    def unfamiliar_ip(
        self,
        user_id: str,
        source_ip: str
    ) -> bool:
        known = self.user_ips.get(user_id, Counter())
        return bool(known) and source_ip not in known

    def unusual_hour(
        self,
        user_id: str,
        hour: int
    ) -> bool:
        known = self.user_hours.get(user_id, Counter())

        if not known:
            return False

        return hour not in known


# ---------------------------------------------------------
# DETECTION ENGINE
# ---------------------------------------------------------

class DetectionEngine:

    def __init__(self):
        self.failed_logins: dict[str, deque] = defaultdict(deque)
        self.permission_changes: dict[str, deque] = defaultdict(deque)
        self.baseline = BehavioralBaseline()
        self.alerts: list[SecurityAlert] = []

    @staticmethod
    def classify(score: int) -> Severity:
        if score >= 90:
            return Severity.CRITICAL
        if score >= 70:
            return Severity.HIGH
        if score >= 40:
            return Severity.MEDIUM
        return Severity.LOW

    def create_alert(
        self,
        event: SecurityEvent,
        rule_id: str,
        score: int,
        description: str,
        indicators: dict[str, Any]
    ) -> SecurityAlert:

        alert = SecurityAlert(
            alert_id=str(uuid4()),
            rule_id=rule_id,
            timestamp=event.timestamp,
            user_id=event.user_id,
            severity=self.classify(score),
            description=description,
            risk_score=min(100, score),
            event_ids=[event.event_id],
            indicators=indicators
        )

        self.alerts.append(alert)
        return alert

    def process(
        self,
        event: SecurityEvent
    ) -> list[SecurityAlert]:

        generated = []
        now = event.timestamp

        if event.event_type == EventType.FAILED_LOGIN:
            attempts = self.failed_logins[event.user_id]
            attempts.append(now)

            cutoff = now - timedelta(minutes=10)

            while attempts and attempts[0] < cutoff:
                attempts.popleft()

            if len(attempts) >= FAILED_LOGIN_THRESHOLD:
                generated.append(
                    self.create_alert(
                        event,
                        "AUTH-001",
                        85,
                        "Repeated authentication failures.",
                        {
                            "attempt_count": len(attempts),
                            "window_minutes": 10,
                            "source_ip": event.source_ip
                        }
                    )
                )

        if event.event_type == EventType.PERMISSION_CHANGE:
            changes = self.permission_changes[event.user_id]
            changes.append(now)

            cutoff = now - timedelta(minutes=15)

            while changes and changes[0] < cutoff:
                changes.popleft()

            if len(changes) >= PRIVILEGE_CHANGE_THRESHOLD:
                generated.append(
                    self.create_alert(
                        event,
                        "IAM-001",
                        95,
                        "Rapid privilege modifications detected.",
                        {"change_count": len(changes)}
                    )
                )

            if not event.metadata.get("approved_change", False):
                generated.append(
                    self.create_alert(
                        event,
                        "IAM-002",
                        90,
                        "Permission modification lacks approval evidence.",
                        {"resource": event.resource}
                    )
                )

        if (
            event.success
            and self.baseline.unfamiliar_ip(
                event.user_id,
                event.source_ip
            )
        ):
            generated.append(
                self.create_alert(
                    event,
                    "ANOM-001",
                    75,
                    "Successful access from an unfamiliar IP.",
                    {"source_ip": event.source_ip}
                )
            )

        if (
            event.success
            and self.baseline.unusual_hour(
                event.user_id,
                event.timestamp.hour
            )
        ):
            generated.append(
                self.create_alert(
                    event,
                    "ANOM-002",
                    65,
                    "Access occurred outside the observed time baseline.",
                    {"hour": event.timestamp.hour}
                )
            )

        if event.event_type == EventType.SECRET_ACCESS:
            if not event.metadata.get("approved", False):
                generated.append(
                    self.create_alert(
                        event,
                        "DATA-001",
                        95,
                        "Unapproved secret access.",
                        {"resource": event.resource}
                    )
                )

        return generated


# ---------------------------------------------------------
# INCIDENT MANAGEMENT
# ---------------------------------------------------------

class IncidentManager:

    def __init__(self):
        self.incidents: dict[str, SecurityIncident] = {}

    def create_from_alert(
        self,
        alert: SecurityAlert
    ) -> SecurityIncident:

        incident = SecurityIncident(
            incident_id=str(uuid4()),
            title=alert.description,
            severity=alert.severity,
            status=IncidentStatus.OPEN,
            created_at=alert.timestamp,
            updated_at=alert.timestamp,
            alert_ids=[alert.alert_id]
        )

        self.incidents[incident.incident_id] = incident
        return incident

    def add_evidence(
        self,
        incident_id: str,
        evidence: str
    ) -> None:

        incident = self._get(incident_id)

        if incident.status == IncidentStatus.CLOSED:
            raise IncidentTransitionError(
                "Cannot modify a closed incident."
            )

        digest = hashlib.sha256(
            evidence.encode("utf-8")
        ).hexdigest()

        incident.evidence_hashes.append(digest)
        incident.updated_at = datetime.now(timezone.utc)

    def add_note(
        self,
        incident_id: str,
        note: str
    ) -> None:

        if not note.strip():
            raise ValueError("Investigation note cannot be empty.")

        incident = self._get(incident_id)

        if incident.status == IncidentStatus.CLOSED:
            raise IncidentTransitionError(
                "Cannot update a closed incident."
            )

        incident.investigation_notes.append(note)
        incident.updated_at = datetime.now(timezone.utc)

    def transition(
        self,
        incident_id: str,
        status: IncidentStatus
    ) -> None:
        self._get(incident_id).transition(status)

    def _get(self, incident_id: str) -> SecurityIncident:
        if incident_id not in self.incidents:
            raise KeyError("Incident does not exist.")

        return self.incidents[incident_id]

    def save(self, path: Path = INCIDENT_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        records = []

        for incident in self.incidents.values():
            record = asdict(incident)
            record["severity"] = incident.severity.value
            record["status"] = incident.status.value
            record["created_at"] = incident.created_at.isoformat()
            record["updated_at"] = incident.updated_at.isoformat()
            records.append(record)

        temporary = path.with_suffix(".tmp")

        temporary.write_text(
            json.dumps(records, indent=2),
            encoding="utf-8"
        )

        temporary.replace(path)


# ---------------------------------------------------------
# CENTRAL MONITORING SERVICE
# ---------------------------------------------------------

class CloudSecurityMonitor:

    def __init__(self):
        self.store = AuditLogStore()
        self.detector = DetectionEngine()
        self.incident_manager = IncidentManager()

    def ingest(self, raw: dict[str, Any]) -> list[SecurityAlert]:
        event = LogNormalizer.normalize(raw)

        # Persist evidence before evaluating security rules.
        self.store.add(event)

        alerts = self.detector.process(event)

        for alert in alerts:
            self.incident_manager.create_from_alert(alert)

            LOGGER.warning(
                "SECURITY ALERT | %s | %s | score=%d",
                alert.severity.value,
                alert.rule_id,
                alert.risk_score
            )

        return alerts

    def ingest_batch(
        self,
        records: list[dict[str, Any]]
    ) -> list[SecurityAlert]:

        results = []

        for record in records:
            try:
                results.extend(self.ingest(record))
            except SecurityMonitoringError as exc:
                LOGGER.error("Rejected security event: %s", exc)

        return results

    def report(self) -> dict[str, Any]:
        severity_counts = Counter(
            alert.severity.value
            for alert in self.detector.alerts
        )

        status_counts = Counter(
            incident.status.value
            for incident in self.incident_manager.incidents.values()
        )

        return {
            "total_events": len(self.store.events),
            "total_alerts": len(self.detector.alerts),
            "total_incidents": len(
                self.incident_manager.incidents
            ),
            "alerts_by_severity": dict(severity_counts),
            "incidents_by_status": dict(status_counts),
            "top_users": Counter(
                event.user_id for event in self.store.events
            ).most_common(5),
            "events_by_type": dict(
                Counter(
                    event.event_type.value
                    for event in self.store.events
                )
            )
        }


# ---------------------------------------------------------
# DEMONSTRATION DATA
# ---------------------------------------------------------

def demonstration_events() -> list[dict[str, Any]]:
    base = datetime.now(timezone.utc)

    records = []

    # Establish a normal user baseline.
    for index in range(3):
        timestamp = base - timedelta(days=3) + timedelta(hours=index)

        records.append({
            "timestamp": timestamp.isoformat(),
            "event_type": "login",
            "user_id": "admin-101",
            "source_ip": "10.10.1.10",
            "resource": "identity-service",
            "action": "authenticate",
            "success": True,
            "region": "ap-south-1",
            "metadata": {"mfa": True}
        })

    # Repeated authentication failures.
    for index in range(6):
        records.append({
            "timestamp": (
                base + timedelta(seconds=index * 30)
            ).isoformat(),
            "event_type": "failed_login",
            "user_id": "admin-101",
            "source_ip": "203.0.113.25",
            "resource": "identity-service",
            "action": "authenticate",
            "success": False,
            "region": "ap-south-1",
            "metadata": {"reason": "invalid_credentials"}
        })

    # Unapproved permission modification.
    records.append({
        "timestamp": (base + timedelta(minutes=5)).isoformat(),
        "event_type": "permission_change",
        "user_id": "admin-101",
        "source_ip": "203.0.113.25",
        "resource": "production-iam",
        "action": "grant_admin",
        "success": True,
        "region": "ap-south-1",
        "metadata": {
            "approved_change": False,
            "target_user": "service-202"
        }
    })

    # Unapproved access to a secret.
    records.append({
        "timestamp": (base + timedelta(minutes=6)).isoformat(),
        "event_type": "secret_access",
        "user_id": "service-202",
        "source_ip": "198.51.100.40",
        "resource": "production/database/password",
        "action": "read_secret",
        "success": True,
        "region": "ap-south-1",
        "metadata": {"approved": False}
    })

    return records


# ---------------------------------------------------------
# TESTING
# ---------------------------------------------------------

def run_tests() -> None:
    monitor = CloudSecurityMonitor()

    assert monitor.ingest_batch(
        demonstration_events()
    )

    assert len(monitor.store.events) == 11

    assert len(monitor.detector.alerts) >= 3

    assert monitor.store.verify_integrity()

    incident = next(
        iter(monitor.incident_manager.incidents.values())
    )

    incident.transition(IncidentStatus.INVESTIGATING)

    try:
        incident.transition(IncidentStatus.OPEN)
        raise AssertionError("Invalid transition was accepted.")
    except IncidentTransitionError:
        pass

    try:
        LogNormalizer.normalize({
            "timestamp": "invalid"
        })
        raise AssertionError("Invalid log was accepted.")
    except InvalidLogError:
        pass

    try:
        SecurityEvent(
            event_id="invalid",
            timestamp=datetime.now(),
            event_type=EventType.LOGIN,
            user_id="user",
            source_ip="invalid-ip",
            resource="resource",
            action="login",
            success=True,
            region="test"
        )
        raise AssertionError("Invalid IP was accepted.")
    except InvalidLogError:
        pass

    print("All security monitoring tests passed.")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main() -> None:
    DATA_DIRECTORY.mkdir(exist_ok=True)

    monitor = CloudSecurityMonitor()

    events = demonstration_events()
    alerts = monitor.ingest_batch(events)

    print("\nCLOUD SECURITY MONITORING REPORT")
    print("=" * 55)

    print(json.dumps(
        monitor.report(),
        indent=2
    ))

    print("\nGENERATED SECURITY ALERTS")
    print("=" * 55)

    for alert in alerts:
        print(
            f"{alert.severity.value:8} "
            f"{alert.rule_id:10} "
            f"Risk={alert.risk_score:3} "
            f"{alert.description}"
        )

    # Demonstrate incident investigation.
    for incident in monitor.incident_manager.incidents.values():
        incident.transition(IncidentStatus.INVESTIGATING)

        monitor.incident_manager.add_note(
            incident.incident_id,
            "Initial triage completed. Related audit events retained."
        )

    monitor.incident_manager.save()

    assert monitor.store.verify_integrity()

    run_tests()

    print("\nIncident records saved successfully.")
    print("Audit log integrity verification passed.")


if __name__ == "__main__":
    main()
