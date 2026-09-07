"""
Cloud Computing Challenges
==========================

A comprehensive, self-contained study script covering:

1. Vendor lock-in
2. Latency
3. Security concerns
4. Compliance
5. Cloud outages
6. Data residency
7. Cost management

The script progresses from beginner concepts to more advanced implementation
patterns, simulations, validation techniques, architectural trade-offs, and
production considerations.

All demonstrations use only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple
import hashlib
import json
import random
import statistics
import time


# =============================================================================
# 1. FUNDAMENTAL CLOUD COMPUTING CONTEXT
# =============================================================================

# Cloud computing provides computing resources such as servers, storage,
# databases, networking, and managed services through remote infrastructure.
#
# Common service models:
#
# IaaS: Infrastructure as a Service
#       The provider manages physical infrastructure while customers manage
#       operating systems, applications, and much of their configuration.
#
# PaaS: Platform as a Service
#       The provider manages infrastructure and platform components.
#       Customers focus primarily on applications and data.
#
# SaaS: Software as a Service
#       The provider operates the application and infrastructure.
#       Customers consume the software.
#
# A central cloud computing principle is the shared responsibility model.
# Cloud providers and customers have different security and operational
# responsibilities depending on the service model.


class ServiceModel(Enum):
    IAAS = "Infrastructure as a Service"
    PAAS = "Platform as a Service"
    SAAS = "Software as a Service"


SHARED_RESPONSIBILITY = {
    ServiceModel.IAAS: {
        "provider": {
            "physical_data_centers",
            "physical_servers",
            "network_backbone",
            "hypervisor",
        },
        "customer": {
            "operating_system",
            "application",
            "identity_configuration",
            "data",
            "network_configuration",
            "patching",
        },
    },
    ServiceModel.PAAS: {
        "provider": {
            "physical_data_centers",
            "physical_servers",
            "network_backbone",
            "operating_system",
            "runtime_platform",
        },
        "customer": {
            "application",
            "identity_configuration",
            "data",
            "application_configuration",
        },
    },
    ServiceModel.SAAS: {
        "provider": {
            "infrastructure",
            "platform",
            "application_availability",
        },
        "customer": {
            "user_access",
            "data_configuration",
            "identity_configuration",
            "data_classification",
        },
    },
}


def demonstrate_shared_responsibility() -> None:
    print("\n" + "=" * 80)
    print("1. SHARED RESPONSIBILITY MODEL")
    print("=" * 80)

    for model, responsibilities in SHARED_RESPONSIBILITY.items():
        print(f"\n{model.value}")
        print("  Provider responsibilities:")
        for responsibility in sorted(responsibilities["provider"]):
            print(f"    - {responsibility}")

        print("  Customer responsibilities:")
        for responsibility in sorted(responsibilities["customer"]):
            print(f"    - {responsibility}")


# =============================================================================
# 2. VENDOR LOCK-IN
# =============================================================================

# Vendor lock-in occurs when moving an application, workload, or dataset from
# one provider to another becomes technically difficult, expensive, risky, or
# operationally disruptive.
#
# Lock-in is not always bad. Managed proprietary services may reduce
# development effort and operational burden. The challenge is understanding
# the trade-off before the dependency becomes difficult to reverse.


class LockInType(Enum):
    DATA = "Data lock-in"
    TECHNOLOGY = "Technology lock-in"
    CONTRACTUAL = "Contractual lock-in"
    SKILLS = "Skills lock-in"
    OPERATIONAL = "Operational lock-in"


@dataclass
class CloudDependency:
    name: str
    lock_in_type: LockInType
    portability_score: int
    migration_effort_days: int
    proprietary: bool
    data_volume_tb: float = 0.0

    def lock_in_risk(self) -> str:
        """
        Estimate lock-in severity.

        portability_score:
            0  = extremely difficult to move
            100 = highly portable
        """
        if self.portability_score >= 80:
            return "LOW"
        if self.portability_score >= 50:
            return "MEDIUM"
        return "HIGH"


def calculate_lock_in_index(dependencies: Iterable[CloudDependency]) -> float:
    """
    Calculate a simplified weighted lock-in index.

    Higher values indicate greater migration difficulty.

    This is a teaching model rather than a universal industry metric.
    """
    dependencies = list(dependencies)

    if not dependencies:
        return 0.0

    total_risk = 0.0

    for dependency in dependencies:
        portability_risk = 100 - dependency.portability_score
        proprietary_multiplier = 1.5 if dependency.proprietary else 1.0
        migration_multiplier = min(dependency.migration_effort_days / 30, 5)
        data_multiplier = 1 + min(dependency.data_volume_tb / 100, 2)

        risk = (
            portability_risk
            * proprietary_multiplier
            * (1 + migration_multiplier / 10)
            * data_multiplier
        )

        total_risk += risk

    return round(total_risk / len(dependencies), 2)


class StorageProvider:
    """
    A provider-neutral interface.

    Applications depend on this abstraction rather than directly depending on
    a specific provider SDK throughout business logic.

    This reduces technology coupling but does not eliminate operational,
    data-format, network, identity, or contractual lock-in.
    """

    def put_object(self, key: str, value: bytes) -> None:
        raise NotImplementedError

    def get_object(self, key: str) -> bytes:
        raise NotImplementedError

    def delete_object(self, key: str) -> None:
        raise NotImplementedError


class InMemoryStorageProvider(StorageProvider):
    """
    A simple provider-neutral implementation for demonstration and testing.
    """

    def __init__(self) -> None:
        self._storage: Dict[str, bytes] = {}

    def put_object(self, key: str, value: bytes) -> None:
        self._storage[key] = value

    def get_object(self, key: str) -> bytes:
        if key not in self._storage:
            raise KeyError(f"Object not found: {key}")
        return self._storage[key]

    def delete_object(self, key: str) -> None:
        if key not in self._storage:
            raise KeyError(f"Object not found: {key}")
        del self._storage[key]


class ObjectRepository:
    """
    Business-level repository that depends on an abstraction.

    Benefits:
    - easier unit testing
    - easier provider replacement
    - centralized storage behavior
    - less provider-specific code in application logic
    """

    def __init__(self, provider: StorageProvider) -> None:
        self.provider = provider

    def save_json(self, key: str, data: Dict[str, object]) -> None:
        serialized = json.dumps(data, sort_keys=True).encode("utf-8")
        self.provider.put_object(key, serialized)

    def load_json(self, key: str) -> Dict[str, object]:
        raw = self.provider.get_object(key)
        return json.loads(raw.decode("utf-8"))


def demonstrate_vendor_lock_in() -> None:
    print("\n" + "=" * 80)
    print("2. VENDOR LOCK-IN")
    print("=" * 80)

    dependencies = [
        CloudDependency(
            name="Standard container runtime",
            lock_in_type=LockInType.TECHNOLOGY,
            portability_score=90,
            migration_effort_days=5,
            proprietary=False,
        ),
        CloudDependency(
            name="Proprietary serverless database",
            lock_in_type=LockInType.TECHNOLOGY,
            portability_score=25,
            migration_effort_days=120,
            proprietary=True,
            data_volume_tb=50,
        ),
        CloudDependency(
            name="Provider-specific machine learning API",
            lock_in_type=LockInType.SKILLS,
            portability_score=35,
            migration_effort_days=45,
            proprietary=True,
        ),
    ]

    for dependency in dependencies:
        print(
            f"{dependency.name}: "
            f"portability={dependency.portability_score}, "
            f"risk={dependency.lock_in_risk()}"
        )

    index = calculate_lock_in_index(dependencies)
    print(f"\nSimplified lock-in index: {index}")

    storage = InMemoryStorageProvider()
    repository = ObjectRepository(storage)

    repository.save_json(
        "users/1.json",
        {
            "id": 1,
            "name": "Asha",
            "role": "analyst",
        },
    )

    print("Provider-neutral repository output:")
    print(repository.load_json("users/1.json"))

    # Common mistake:
    #
    # Calling a cloud provider's SDK directly from hundreds of business methods.
    # This creates widespread coupling and makes migration much harder.
    #
    # Better design:
    #
    # Isolate provider-specific code behind well-defined boundaries.


# =============================================================================
# 3. DATA PORTABILITY AND MIGRATION
# =============================================================================

@dataclass
class DataExport:
    format_name: str
    records: List[Dict[str, object]]

    def serialize(self) -> bytes:
        """
        Export using a portable JSON representation.

        Real systems must also consider:
        - schema versioning
        - large dataset streaming
        - compression
        - encryption
        - integrity verification
        - character encoding
        """
        return json.dumps(
            self.records,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")

    def checksum(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()


def migrate_data(
    source_records: List[Dict[str, object]],
    target_validator: Callable[[Dict[str, object]], bool],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """
    Separate valid and rejected records during migration.

    Production migrations should usually support:
    - checkpoints
    - idempotency
    - retry handling
    - audit logs
    - rollback plans
    """
    migrated = []
    rejected = []

    for record in source_records:
        if target_validator(record):
            migrated.append(record)
        else:
            rejected.append(record)

    return migrated, rejected


def demonstrate_data_migration() -> None:
    print("\n" + "=" * 80)
    print("3. DATA PORTABILITY AND MIGRATION")
    print("=" * 80)

    records = [
        {"id": 1, "email": "a@example.com"},
        {"id": 2, "email": "b@example.com"},
        {"id": 3, "email": ""},
    ]

    export = DataExport(format_name="JSON", records=records)

    print(f"Export format: {export.format_name}")
    print(f"SHA-256 checksum: {export.checksum()}")

    def valid_record(record: Dict[str, object]) -> bool:
        return bool(record.get("id")) and bool(record.get("email"))

    migrated, rejected = migrate_data(records, valid_record)

    print(f"Migrated records: {len(migrated)}")
    print(f"Rejected records: {len(rejected)}")


# =============================================================================
# 4. LATENCY
# =============================================================================

# Latency is the time required for data or a request to travel through a system.
#
# Important components can include:
#
# DNS lookup latency
# TCP/TLS connection latency
# Network propagation latency
# Request processing time
# Database latency
# Queue waiting time
# Serialization/deserialization time
# Response transfer time
#
# Average latency is often insufficient. Percentiles are important:
#
# p50: median behavior
# p95: tail behavior affecting slower requests
# p99: extreme tail behavior
#
# A system with low average latency can still provide poor user experience if
# occasional slow requests are common.


@dataclass
class LatencyMeasurement:
    dns_ms: float
    connection_ms: float
    network_ms: float
    processing_ms: float
    database_ms: float
    response_transfer_ms: float

    @property
    def total_ms(self) -> float:
        return (
            self.dns_ms
            + self.connection_ms
            + self.network_ms
            + self.processing_ms
            + self.database_ms
            + self.response_transfer_ms
        )


def percentile(values: List[float], percentage: float) -> float:
    """
    Calculate a percentile using linear interpolation.

    Raises ValueError for invalid input.
    """
    if not values:
        raise ValueError("Cannot calculate a percentile of an empty list.")

    if not 0 <= percentage <= 100:
        raise ValueError("Percentage must be between 0 and 100.")

    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * percentage / 100
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index

    return (
        sorted_values[lower_index]
        + (sorted_values[upper_index] - sorted_values[lower_index]) * fraction
    )


def simulate_latency_samples(
    count: int,
    base_latency_ms: float,
    jitter_ms: float,
    spike_probability: float,
) -> List[float]:
    """
    Simulate realistic variability.

    Network and distributed systems rarely have perfectly constant latency.
    """
    if count <= 0:
        raise ValueError("count must be positive.")

    if not 0 <= spike_probability <= 1:
        raise ValueError("spike_probability must be between 0 and 1.")

    samples = []

    for _ in range(count):
        sample = max(
            0.0,
            random.gauss(base_latency_ms, jitter_ms),
        )

        # Tail latency spike.
        if random.random() < spike_probability:
            sample *= random.uniform(3, 10)

        samples.append(round(sample, 2))

    return samples


def demonstrate_latency() -> None:
    print("\n" + "=" * 80)
    print("4. LATENCY")
    print("=" * 80)

    measurement = LatencyMeasurement(
        dns_ms=5,
        connection_ms=15,
        network_ms=30,
        processing_ms=20,
        database_ms=40,
        response_transfer_ms=10,
    )

    print(f"Single request total latency: {measurement.total_ms:.2f} ms")

    random.seed(42)

    samples = simulate_latency_samples(
        count=1_000,
        base_latency_ms=80,
        jitter_ms=15,
        spike_probability=0.03,
    )

    print(f"Average latency: {statistics.mean(samples):.2f} ms")
    print(f"Median latency (p50): {percentile(samples, 50):.2f} ms")
    print(f"p95 latency: {percentile(samples, 95):.2f} ms")
    print(f"p99 latency: {percentile(samples, 99):.2f} ms")
    print(f"Maximum latency: {max(samples):.2f} ms")

    # Common mistake:
    #
    # Optimizing only average latency.
    #
    # Production systems should also monitor percentile distributions because
    # slow tail requests often have significant user and business impact.


# =============================================================================
# 5. CACHING AS A LATENCY MITIGATION
# =============================================================================

class SimpleTTLCache:
    """
    A simple in-memory TTL cache.

    This demonstrates:
    - cache hits
    - cache misses
    - expiration

    Limitations:
    - process-local only
    - not distributed
    - no eviction policy beyond expiration
    - not safe for all concurrent production use cases
    """

    def __init__(self) -> None:
        self._values: Dict[str, Tuple[object, float]] = {}

    def set(self, key: str, value: object, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")

        expiration = time.monotonic() + ttl_seconds
        self._values[key] = (value, expiration)

    def get(self, key: str) -> Optional[object]:
        entry = self._values.get(key)

        if entry is None:
            return None

        value, expiration = entry

        if time.monotonic() >= expiration:
            del self._values[key]
            return None

        return value


@lru_cache(maxsize=256)
def expensive_computation(number: int) -> int:
    """
    Demonstrates process-local memoization.

    The artificial loop represents an expensive CPU operation.
    """
    result = 0

    for value in range(number * 10_000):
        result += value % 7

    return result


def demonstrate_caching() -> None:
    print("\n" + "=" * 80)
    print("5. CACHING AND LATENCY")
    print("=" * 80)

    cache = SimpleTTLCache()

    print("Cache miss:", cache.get("country:IN"))

    cache.set(
        "country:IN",
        {"name": "India"},
        ttl_seconds=5,
    )

    print("Cache hit:", cache.get("country:IN"))

    start = time.perf_counter()
    first_result = expensive_computation(20)
    first_duration = time.perf_counter() - start

    start = time.perf_counter()
    second_result = expensive_computation(20)
    second_duration = time.perf_counter() - start

    print(f"First computation result: {first_result}")
    print(f"First duration: {first_duration:.6f} seconds")
    print(f"Cached duration: {second_duration:.6f} seconds")

    # Important cache trade-off:
    #
    # Caching improves latency but introduces data freshness challenges.
    # A stale cache can return outdated information.


# =============================================================================
# 6. SECURITY CONCERNS
# =============================================================================

# Common cloud security concerns include:
#
# - weak identity and access management
# - excessive permissions
# - exposed credentials
# - publicly accessible storage
# - insecure APIs
# - unencrypted sensitive data
# - poor key management
# - missing logs
# - misconfiguration
# - vulnerable dependencies
# - insecure network exposure
#
# Cloud security is strongly influenced by configuration. A secure cloud
# provider does not automatically make an insecure customer configuration safe.


class Permission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass(frozen=True)
class UserIdentity:
    username: str
    roles: Set[str]


@dataclass
class AccessPolicy:
    role_permissions: Dict[str, Set[Permission]] = field(
        default_factory=dict
    )

    def is_allowed(
        self,
        identity: UserIdentity,
        permission: Permission,
    ) -> bool:
        """
        Role-based access control.

        Access is granted when at least one assigned role contains the
        requested permission.
        """
        for role in identity.roles:
            permissions = self.role_permissions.get(role, set())

            if permission in permissions:
                return True

        return False


def require_permission(
    policy: AccessPolicy,
    identity: UserIdentity,
    permission: Permission,
) -> None:
    if not policy.is_allowed(identity, permission):
        raise PermissionError(
            f"{identity.username} does not have permission: "
            f"{permission.value}"
        )


def hash_secret(secret: str, salt: str) -> str:
    """
    Demonstration only.

    For password storage, production systems should use specialized password
    hashing algorithms such as Argon2, bcrypt, or scrypt.

    A simple SHA-256 hash is not appropriate for production password storage.
    """
    return hashlib.sha256(
        (salt + secret).encode("utf-8")
    ).hexdigest()


@dataclass
class SecureRecord:
    record_id: str
    owner: str
    classification: str
    content: str


class SecureRecordService:
    """
    Demonstrates authorization before data access.
    """

    def __init__(
        self,
        policy: AccessPolicy,
        records: Dict[str, SecureRecord],
    ) -> None:
        self.policy = policy
        self.records = records

    def read_record(
        self,
        identity: UserIdentity,
        record_id: str,
    ) -> SecureRecord:
        require_permission(
            self.policy,
            identity,
            Permission.READ,
        )

        if record_id not in self.records:
            raise KeyError("Record does not exist.")

        return self.records[record_id]


def demonstrate_security() -> None:
    print("\n" + "=" * 80)
    print("6. SECURITY CONCERNS")
    print("=" * 80)

    policy = AccessPolicy(
        role_permissions={
            "viewer": {Permission.READ},
            "editor": {
                Permission.READ,
                Permission.WRITE,
            },
            "administrator": {
                Permission.READ,
                Permission.WRITE,
                Permission.DELETE,
                Permission.ADMIN,
            },
        }
    )

    viewer = UserIdentity(
        username="viewer_user",
        roles={"viewer"},
    )

    administrator = UserIdentity(
        username="admin_user",
        roles={"administrator"},
    )

    records = {
        "record-1": SecureRecord(
            record_id="record-1",
            owner="system",
            classification="confidential",
            content="Sensitive business data",
        )
    }

    service = SecureRecordService(policy, records)

    print(
        "Viewer read:",
        service.read_record(viewer, "record-1").content,
    )

    try:
        require_permission(
            policy,
            viewer,
            Permission.DELETE,
        )
    except PermissionError as error:
        print("Expected authorization failure:", error)

    print(
        "Administrator can delete:",
        policy.is_allowed(
            administrator,
            Permission.DELETE,
        ),
    )

    # Security principle: least privilege.
    #
    # A user or service should receive only the permissions necessary to perform
    # its legitimate function.


# =============================================================================
# 7. SECRETS AND CONFIGURATION SECURITY
# =============================================================================

SENSITIVE_CONFIGURATION_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "private_key",
}


def redact_sensitive_configuration(
    configuration: Dict[str, str],
) -> Dict[str, str]:
    """
    Produce safer logs by redacting sensitive values.
    """
    redacted = {}

    for key, value in configuration.items():
        normalized_key = key.lower()

        if any(
            sensitive_word in normalized_key
            for sensitive_word in SENSITIVE_CONFIGURATION_KEYS
        ):
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value

    return redacted


def demonstrate_secret_handling() -> None:
    print("\n" + "=" * 80)
    print("7. SECRETS AND CONFIGURATION SECURITY")
    print("=" * 80)

    configuration = {
        "database_host": "database.internal",
        "api_key": "super-secret-value",
        "service_token": "another-secret",
        "environment": "production",
    }

    print("Safe log representation:")
    print(redact_sensitive_configuration(configuration))

    # Common mistake:
    #
    # Printing complete configuration dictionaries in application logs.
    #
    # Logs are often copied to monitoring systems and retained for long periods.
    # Secrets should not be embedded in source code or exposed in logs.


# =============================================================================
# 8. COMPLIANCE
# =============================================================================

# Compliance requirements may arise from:
#
# - laws and regulations
# - industry standards
# - contracts
# - organizational policies
#
# Examples of compliance concerns:
#
# - access control
# - audit logging
# - data retention
# - encryption
# - deletion requirements
# - data classification
# - regional storage requirements
# - evidence collection
#
# Compliance is not achieved merely by selecting a provider with a
# certification. The customer's architecture and operational practices must
# also satisfy applicable requirements.


class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class ComplianceRequirement:
    name: str
    required_controls: Set[str]


@dataclass
class CloudWorkload:
    name: str
    implemented_controls: Set[str]

    def check_compliance(
        self,
        requirement: ComplianceRequirement,
    ) -> Dict[str, Set[str]]:
        missing = (
            requirement.required_controls
            - self.implemented_controls
        )

        satisfied = (
            requirement.required_controls
            & self.implemented_controls
        )

        return {
            "satisfied": satisfied,
            "missing": missing,
        }


def demonstrate_compliance() -> None:
    print("\n" + "=" * 80)
    print("8. COMPLIANCE")
    print("=" * 80)

    workload = CloudWorkload(
        name="Customer Portal",
        implemented_controls={
            "encryption_at_rest",
            "encryption_in_transit",
            "audit_logging",
            "role_based_access_control",
        },
    )

    requirement = ComplianceRequirement(
        name="Example Sensitive Data Policy",
        required_controls={
            "encryption_at_rest",
            "encryption_in_transit",
            "audit_logging",
            "role_based_access_control",
            "retention_policy",
            "incident_response_process",
        },
    )

    result = workload.check_compliance(requirement)

    print("Satisfied controls:")
    for control in sorted(result["satisfied"]):
        print(f"  - {control}")

    print("Missing controls:")
    for control in sorted(result["missing"]):
        print(f"  - {control}")

    # Important distinction:
    #
    # Security and compliance overlap but are not identical.
    #
    # A system may be secure in certain technical respects while still failing
    # a regulatory requirement such as retention documentation or geographic
    # data handling restrictions.


# =============================================================================
# 9. AUDIT LOGGING
# =============================================================================

@dataclass
class AuditEvent:
    timestamp: datetime
    actor: str
    action: str
    resource: str
    outcome: str
    request_id: str


class AuditLogger:
    """
    Stores audit events in memory for demonstration.

    Production systems commonly send logs to durable, access-controlled,
    centralized logging infrastructure.
    """

    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    def record(
        self,
        actor: str,
        action: str,
        resource: str,
        outcome: str,
        request_id: str,
    ) -> None:
        self.events.append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                actor=actor,
                action=action,
                resource=resource,
                outcome=outcome,
                request_id=request_id,
            )
        )

    def find_by_actor(
        self,
        actor: str,
    ) -> List[AuditEvent]:
        return [
            event
            for event in self.events
            if event.actor == actor
        ]


def demonstrate_audit_logging() -> None:
    print("\n" + "=" * 80)
    print("9. AUDIT LOGGING")
    print("=" * 80)

    logger = AuditLogger()

    logger.record(
        actor="alice",
        action="READ",
        resource="customer/1001",
        outcome="SUCCESS",
        request_id="req-001",
    )

    logger.record(
        actor="alice",
        action="DELETE",
        resource="customer/1001",
        outcome="DENIED",
        request_id="req-002",
    )

    for event in logger.find_by_actor("alice"):
        print(
            event.timestamp.isoformat(),
            event.actor,
            event.action,
            event.resource,
            event.outcome,
        )


# =============================================================================
# 10. CLOUD OUTAGES
# =============================================================================

# Cloud outages can be caused by:
#
# - infrastructure failures
# - software defects
# - configuration mistakes
# - network problems
# - regional incidents
# - dependency failures
# - capacity exhaustion
# - human error
#
# A multi-region architecture can reduce some outage risks but introduces:
#
# - higher cost
# - replication complexity
# - consistency challenges
# - operational complexity
# - difficult failover testing
#
# Availability is not the same as durability.
#
# Availability:
#     Probability that a service is operational when needed.
#
# Durability:
#     Probability that stored data remains intact over time.


class ServiceUnavailableError(RuntimeError):
    pass


class SimulatedCloudService:
    """
    Simulates an unreliable remote service.
    """

    def __init__(
        self,
        name: str,
        failure_probability: float,
    ) -> None:
        if not 0 <= failure_probability <= 1:
            raise ValueError(
                "failure_probability must be between 0 and 1."
            )

        self.name = name
        self.failure_probability = failure_probability

    def request(self, payload: str) -> str:
        if random.random() < self.failure_probability:
            raise ServiceUnavailableError(
                f"{self.name} is unavailable."
            )

        return f"{self.name} processed: {payload}"


def retry(
    operation: Callable[[], str],
    max_attempts: int = 3,
    initial_delay_seconds: float = 0.1,
) -> str:
    """
    Retry transient operations using exponential backoff.

    Important production considerations:
    - retry only transient failures
    - avoid retrying unsafe non-idempotent operations blindly
    - add jitter to reduce synchronized retry storms
    - enforce deadlines
    """
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive.")

    delay = initial_delay_seconds
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()

        except ServiceUnavailableError as error:
            last_error = error

            if attempt == max_attempts:
                break

            jitter = random.uniform(0, delay * 0.2)
            time.sleep(delay + jitter)
            delay *= 2

    raise RuntimeError(
        f"Operation failed after {max_attempts} attempts."
    ) from last_error


class RegionalServiceRouter:
    """
    Attempts a primary service and falls back to another region.

    This example is simplified. Production failover requires careful handling
    of:
    - replication lag
    - split-brain scenarios
    - DNS propagation
    - session state
    - write consistency
    """

    def __init__(
        self,
        primary: SimulatedCloudService,
        secondary: SimulatedCloudService,
    ) -> None:
        self.primary = primary
        self.secondary = secondary

    def request(self, payload: str) -> str:
        try:
            return self.primary.request(payload)
        except ServiceUnavailableError:
            return self.secondary.request(payload)


def calculate_availability(
    uptime_minutes: float,
    downtime_minutes: float,
) -> float:
    total = uptime_minutes + downtime_minutes

    if total <= 0:
        raise ValueError("Total time must be positive.")

    return uptime_minutes / total * 100


def demonstrate_outages() -> None:
    print("\n" + "=" * 80)
    print("10. CLOUD OUTAGES AND RESILIENCE")
    print("=" * 80)

    random.seed(7)

    unstable_service = SimulatedCloudService(
        name="Primary API",
        failure_probability=0.5,
    )

    try:
        response = retry(
            lambda: unstable_service.request("important-request"),
            max_attempts=4,
        )
        print("Retry response:", response)
    except RuntimeError as error:
        print("Retries exhausted:", error)

    router = RegionalServiceRouter(
        primary=SimulatedCloudService(
            "Region-A",
            failure_probability=0.7,
        ),
        secondary=SimulatedCloudService(
            "Region-B",
            failure_probability=0.1,
        ),
    )

    try:
        print("Failover response:", router.request("customer-query"))
    except ServiceUnavailableError as error:
        print("All regions unavailable:", error)

    availability = calculate_availability(
        uptime_minutes=525_000,
        downtime_minutes=600,
    )

    print(f"Observed availability: {availability:.6f}%")

    # Important distinction:
    #
    # High availability does not mean zero downtime.
    # Every dependency has failure modes.


# =============================================================================
# 11. CIRCUIT BREAKERS
# =============================================================================

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    A simplified circuit breaker.

    CLOSED:
        Requests flow normally.

    OPEN:
        Requests fail immediately to avoid repeatedly calling a failing service.

    HALF_OPEN:
        A limited test request determines whether recovery may have occurred.
    """

    def __init__(
        self,
        failure_threshold: int,
        recovery_timeout_seconds: float,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.opened_at: Optional[float] = None

    def call(
        self,
        operation: Callable[[], str],
    ) -> str:
        current_time = time.monotonic()

        if self.state == CircuitState.OPEN:
            if (
                self.opened_at is not None
                and current_time - self.opened_at
                >= self.recovery_timeout_seconds
            ):
                self.state = CircuitState.HALF_OPEN
            else:
                raise ServiceUnavailableError(
                    "Circuit breaker is open."
                )

        try:
            result = operation()

        except Exception:
            self.failure_count += 1

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()

            raise

        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None

        return result


def demonstrate_circuit_breaker() -> None:
    print("\n" + "=" * 80)
    print("11. CIRCUIT BREAKERS")
    print("=" * 80)

    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_seconds=0.2,
    )

    def failing_operation() -> str:
        raise ServiceUnavailableError("Dependency failure")

    for attempt in range(1, 4):
        try:
            breaker.call(failing_operation)
        except ServiceUnavailableError as error:
            print(
                f"Attempt {attempt}: {error}; "
                f"state={breaker.state.value}"
            )

    # Circuit breakers reduce cascading failures by preventing a struggling
    # downstream dependency from being called continuously.


# =============================================================================
# 12. DATA RESIDENCY
# =============================================================================

# Data residency concerns where data is physically or logically stored.
#
# Data sovereignty can involve broader legal jurisdiction questions.
#
# A cloud architecture may need to account for:
#
# - primary storage location
# - backups
# - replicas
# - disaster recovery copies
# - logs
# - analytics pipelines
# - support access
# - metadata
#
# Simply selecting a primary region may not guarantee that every data-related
# artifact remains within the same jurisdiction.


@dataclass(frozen=True)
class Region:
    code: str
    country: str


@dataclass
class ResidencyPolicy:
    allowed_countries: Set[str]

    def validate_region(
        self,
        region: Region,
    ) -> bool:
        return region.country in self.allowed_countries


@dataclass
class DataPlacement:
    dataset_name: str
    primary_region: Region
    replica_regions: List[Region]

    def all_regions(self) -> List[Region]:
        return [
            self.primary_region,
            *self.replica_regions,
        ]


def validate_data_residency(
    placement: DataPlacement,
    policy: ResidencyPolicy,
) -> List[str]:
    violations = []

    for region in placement.all_regions():
        if not policy.validate_region(region):
            violations.append(
                f"{placement.dataset_name} stored in "
                f"{region.code} ({region.country})"
            )

    return violations


def demonstrate_data_residency() -> None:
    print("\n" + "=" * 80)
    print("12. DATA RESIDENCY")
    print("=" * 80)

    region_india = Region(
        code="region-india-1",
        country="India",
    )

    region_europe = Region(
        code="region-europe-1",
        country="Germany",
    )

    region_us = Region(
        code="region-us-1",
        country="United States",
    )

    placement = DataPlacement(
        dataset_name="citizen_records",
        primary_region=region_india,
        replica_regions=[
            region_india,
            region_us,
        ],
    )

    policy = ResidencyPolicy(
        allowed_countries={"India"}
    )

    violations = validate_data_residency(
        placement,
        policy,
    )

    if violations:
        print("Residency violations:")
        for violation in violations:
            print("  -", violation)
    else:
        print("Data placement satisfies residency policy.")

    # Common mistake:
    #
    # Checking only the primary database region while ignoring backups,
    # analytics copies, logs, disaster recovery replicas, and exports.


# =============================================================================
# 13. CLOUD COST MANAGEMENT
# =============================================================================

# Cloud costs can be variable and distributed across:
#
# - compute
# - storage
# - network transfer
# - managed databases
# - serverless execution
# - monitoring
# - logging
# - support
# - backup
#
# Cloud spending is often difficult to understand because small usage decisions
# can scale into large aggregate costs.


@dataclass
class CostItem:
    service: str
    quantity: Decimal
    unit_price: Decimal
    tags: Dict[str, str] = field(
        default_factory=dict
    )

    def cost(self) -> Decimal:
        return (
            self.quantity * self.unit_price
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )


def calculate_total_cost(
    items: Iterable[CostItem],
) -> Decimal:
    return sum(
        (item.cost() for item in items),
        Decimal("0.00"),
    )


def group_costs_by_tag(
    items: Iterable[CostItem],
    tag_name: str,
) -> Dict[str, Decimal]:
    grouped: Dict[str, Decimal] = {}

    for item in items:
        tag_value = item.tags.get(
            tag_name,
            "UNALLOCATED",
        )

        grouped[tag_value] = (
            grouped.get(
                tag_value,
                Decimal("0.00"),
            )
            + item.cost()
        )

    return grouped


@dataclass
class Budget:
    monthly_limit: Decimal
    alert_threshold_percentage: Decimal

    def should_alert(
        self,
        current_spend: Decimal,
    ) -> bool:
        threshold = (
            self.monthly_limit
            * self.alert_threshold_percentage
            / Decimal("100")
        )

        return current_spend >= threshold


def demonstrate_cost_management() -> None:
    print("\n" + "=" * 80)
    print("13. CLOUD COST MANAGEMENT")
    print("=" * 80)

    items = [
        CostItem(
            service="Virtual machines",
            quantity=Decimal("720"),
            unit_price=Decimal("0.08"),
            tags={
                "team": "engineering",
                "environment": "production",
            },
        ),
        CostItem(
            service="Object storage",
            quantity=Decimal("5000"),
            unit_price=Decimal("0.02"),
            tags={
                "team": "data",
                "environment": "production",
            },
        ),
        CostItem(
            service="Network transfer",
            quantity=Decimal("1200"),
            unit_price=Decimal("0.09"),
            tags={
                "team": "engineering",
                "environment": "production",
            },
        ),
        CostItem(
            service="Unallocated test resource",
            quantity=Decimal("100"),
            unit_price=Decimal("0.50"),
            tags={},
        ),
    ]

    total = calculate_total_cost(items)

    print(f"Total cost: ${total}")

    grouped = group_costs_by_tag(
        items,
        "team",
    )

    print("Cost by team:")
    for team, cost in sorted(grouped.items()):
        print(f"  {team}: ${cost}")

    budget = Budget(
        monthly_limit=Decimal("250.00"),
        alert_threshold_percentage=Decimal("80"),
    )

    print(
        "Budget alert:",
        budget.should_alert(total),
    )


# =============================================================================
# 14. COST ANOMALY DETECTION
# =============================================================================

def detect_cost_anomalies(
    historical_costs: List[float],
    current_cost: float,
    standard_deviation_multiplier: float = 2.5,
) -> bool:
    """
    Detect a simple statistical anomaly.

    Limitations:
    - assumes historical data is meaningful
    - seasonal workloads may create false positives
    - very small datasets are unreliable
    - does not understand business context
    """
    if len(historical_costs) < 2:
        raise ValueError(
            "At least two historical values are required."
        )

    mean = statistics.mean(historical_costs)
    deviation = statistics.stdev(historical_costs)

    if deviation == 0:
        return current_cost != mean

    z_score = abs(
        current_cost - mean
    ) / deviation

    return z_score > standard_deviation_multiplier


def demonstrate_cost_anomalies() -> None:
    print("\n" + "=" * 80)
    print("14. COST ANOMALY DETECTION")
    print("=" * 80)

    historical = [
        102,
        98,
        101,
        99,
        103,
        100,
        97,
        104,
        102,
        99,
    ]

    normal_cost = 105
    unusual_cost = 250

    print(
        f"${normal_cost} anomalous:",
        detect_cost_anomalies(
            historical,
            normal_cost,
        ),
    )

    print(
        f"${unusual_cost} anomalous:",
        detect_cost_anomalies(
            historical,
            unusual_cost,
        ),
    )


# =============================================================================
# 15. RESOURCE TAGGING AND ACCOUNTABILITY
# =============================================================================

REQUIRED_TAGS = {
    "owner",
    "environment",
    "cost_center",
}


@dataclass
class CloudResource:
    resource_id: str
    resource_type: str
    tags: Dict[str, str]


def validate_resource_tags(
    resource: CloudResource,
) -> Set[str]:
    """
    Return missing required tags.
    """
    return {
        tag
        for tag in REQUIRED_TAGS
        if not resource.tags.get(tag)
    }


def demonstrate_resource_tagging() -> None:
    print("\n" + "=" * 80)
    print("15. RESOURCE TAGGING")
    print("=" * 80)

    resource = CloudResource(
        resource_id="vm-123",
        resource_type="virtual_machine",
        tags={
            "owner": "platform-team",
            "environment": "production",
        },
    )

    missing = validate_resource_tags(resource)

    print("Missing tags:", sorted(missing))

    # Tags support:
    #
    # - cost allocation
    # - ownership
    # - lifecycle management
    # - incident investigation
    # - governance
    #
    # Untagged resources are often difficult to attribute and manage.


# =============================================================================
# 16. SECURITY MISCONFIGURATION DETECTION
# =============================================================================

@dataclass
class StorageConfiguration:
    bucket_name: str
    public_read: bool
    public_write: bool
    encryption_enabled: bool
    logging_enabled: bool


def validate_storage_security(
    configuration: StorageConfiguration,
) -> List[str]:
    issues = []

    if configuration.public_read:
        issues.append(
            "Public read access is enabled."
        )

    if configuration.public_write:
        issues.append(
            "Public write access is enabled."
        )

    if not configuration.encryption_enabled:
        issues.append(
            "Encryption at rest is disabled."
        )

    if not configuration.logging_enabled:
        issues.append(
            "Access logging is disabled."
        )

    return issues


def demonstrate_security_validation() -> None:
    print("\n" + "=" * 80)
    print("16. SECURITY MISCONFIGURATION VALIDATION")
    print("=" * 80)

    insecure_configuration = StorageConfiguration(
        bucket_name="example-sensitive-data",
        public_read=True,
        public_write=False,
        encryption_enabled=False,
        logging_enabled=False,
    )

    issues = validate_storage_security(
        insecure_configuration
    )

    print(
        f"Security issues for "
        f"{insecure_configuration.bucket_name}:"
    )

    for issue in issues:
        print(f"  - {issue}")


# =============================================================================
# 17. COMPLIANCE, RESIDENCY, SECURITY, AND COST IN ONE ARCHITECTURE REVIEW
# =============================================================================

@dataclass
class ArchitectureAssessment:
    lock_in_score: float
    residency_violations: List[str]
    security_issues: List[str]
    monthly_cost: Decimal
    budget_alert: bool

    def is_acceptable(self) -> bool:
        return (
            self.lock_in_score < 200
            and not self.residency_violations
            and not self.security_issues
            and not self.budget_alert
        )


def assess_architecture() -> ArchitectureAssessment:
    dependencies = [
        CloudDependency(
            name="Managed proprietary database",
            lock_in_type=LockInType.TECHNOLOGY,
            portability_score=30,
            migration_effort_days=90,
            proprietary=True,
            data_volume_tb=20,
        ),
        CloudDependency(
            name="Containerized application",
            lock_in_type=LockInType.TECHNOLOGY,
            portability_score=85,
            migration_effort_days=10,
            proprietary=False,
        ),
    ]

    lock_in_score = calculate_lock_in_index(
        dependencies
    )

    allowed_region = Region(
        code="region-a",
        country="India",
    )

    disallowed_region = Region(
        code="region-b",
        country="United States",
    )

    placement = DataPlacement(
        dataset_name="regulated_customer_data",
        primary_region=allowed_region,
        replica_regions=[disallowed_region],
    )

    residency_violations = validate_data_residency(
        placement,
        ResidencyPolicy(
            allowed_countries={"India"}
        ),
    )

    storage_configuration = StorageConfiguration(
        bucket_name="customer-data",
        public_read=False,
        public_write=False,
        encryption_enabled=True,
        logging_enabled=True,
    )

    security_issues = validate_storage_security(
        storage_configuration
    )

    costs = [
        CostItem(
            service="Compute",
            quantity=Decimal("1000"),
            unit_price=Decimal("0.12"),
        ),
        CostItem(
            service="Database",
            quantity=Decimal("1"),
            unit_price=Decimal("180"),
        ),
    ]

    monthly_cost = calculate_total_cost(
        costs
    )

    budget = Budget(
        monthly_limit=Decimal("500"),
        alert_threshold_percentage=Decimal("90"),
    )

    return ArchitectureAssessment(
        lock_in_score=lock_in_score,
        residency_violations=residency_violations,
        security_issues=security_issues,
        monthly_cost=monthly_cost,
        budget_alert=budget.should_alert(
            monthly_cost
        ),
    )


def demonstrate_integrated_assessment() -> None:
    print("\n" + "=" * 80)
    print("17. INTEGRATED CLOUD ARCHITECTURE ASSESSMENT")
    print("=" * 80)

    assessment = assess_architecture()

    print(
        f"Vendor lock-in score: "
        f"{assessment.lock_in_score}"
    )

    print(
        f"Residency violations: "
        f"{assessment.residency_violations}"
    )

    print(
        f"Security issues: "
        f"{assessment.security_issues}"
    )

    print(
        f"Monthly cost: "
        f"${assessment.monthly_cost}"
    )

    print(
        f"Budget alert: "
        f"{assessment.budget_alert}"
    )

    print(
        f"Architecture acceptable: "
        f"{assessment.is_acceptable()}"
    )


# =============================================================================
# 18. DISTRIBUTED SYSTEMS TRADE-OFFS
# =============================================================================

@dataclass
class ArchitectureChoice:
    name: str
    latency_score: int
    availability_score: int
    consistency_score: int
    complexity_score: int
    cost_score: int


def compare_architectures(
    architectures: List[ArchitectureChoice],
) -> None:
    print("\nArchitecture comparison:")
    print(
        f"{'Architecture':<25}"
        f"{'Latency':>10}"
        f"{'Availability':>15}"
        f"{'Consistency':>15}"
        f"{'Complexity':>15}"
        f"{'Cost':>10}"
    )

    for architecture in architectures:
        print(
            f"{architecture.name:<25}"
            f"{architecture.latency_score:>10}"
            f"{architecture.availability_score:>15}"
            f"{architecture.consistency_score:>15}"
            f"{architecture.complexity_score:>15}"
            f"{architecture.cost_score:>10}"
        )


def demonstrate_tradeoffs() -> None:
    print("\n" + "=" * 80)
    print("18. CLOUD ARCHITECTURE TRADE-OFFS")
    print("=" * 80)

    architectures = [
        ArchitectureChoice(
            name="Single Region",
            latency_score=9,
            availability_score=6,
            consistency_score=9,
            complexity_score=3,
            cost_score=9,
        ),
        ArchitectureChoice(
            name="Multi-AZ",
            latency_score=8,
            availability_score=9,
            consistency_score=8,
            complexity_score=6,
            cost_score=6,
        ),
        ArchitectureChoice(
            name="Multi-Region",
            latency_score=6,
            availability_score=10,
            consistency_score=6,
            complexity_score=10,
            cost_score=3,
        ),
    ]

    compare_architectures(architectures)

    # Higher scores are illustrative.
    #
    # A more resilient architecture usually increases operational complexity
    # and cost. There is no architecture that simultaneously maximizes every
    # desirable property.


# =============================================================================
# 19. TIMEOUTS AND DEADLINES
# =============================================================================

def call_with_timeout_simulation(
    operation_duration_ms: float,
    timeout_ms: float,
) -> str:
    """
    Simulate timeout logic without creating long-running work.
    """
    if operation_duration_ms > timeout_ms:
        raise TimeoutError(
            f"Operation exceeded timeout of {timeout_ms} ms."
        )

    return (
        f"Operation completed in "
        f"{operation_duration_ms} ms."
    )


def demonstrate_timeouts() -> None:
    print("\n" + "=" * 80)
    print("19. TIMEOUTS AND DEADLINES")
    print("=" * 80)

    print(
        call_with_timeout_simulation(
            operation_duration_ms=100,
            timeout_ms=500,
        )
    )

    try:
        print(
            call_with_timeout_simulation(
                operation_duration_ms=800,
                timeout_ms=500,
            )
        )
    except TimeoutError as error:
        print("Expected timeout:", error)

    # Common mistake:
    #
    # Omitting timeouts for remote calls.
    #
    # Without deadlines, failed dependencies can consume threads, connections,
    # memory, and other limited resources while waiting indefinitely.


# =============================================================================
# 20. IDEMPOTENCY
# =============================================================================

class PaymentProcessor:
    """
    Demonstrates idempotency keys.

    If a client retries a request because a network response was lost, the
    operation should not necessarily be performed twice.
    """

    def __init__(self) -> None:
        self.processed_keys: Dict[str, str] = {}

    def process(
        self,
        idempotency_key: str,
        amount: Decimal,
    ) -> str:
        if amount <= 0:
            raise ValueError(
                "Amount must be positive."
            )

        if idempotency_key in self.processed_keys:
            return (
                "Existing result: "
                f"{self.processed_keys[idempotency_key]}"
            )

        transaction_id = (
            f"txn-{len(self.processed_keys) + 1:05d}"
        )

        self.processed_keys[
            idempotency_key
        ] = transaction_id

        return (
            f"New transaction: "
            f"{transaction_id}"
        )


def demonstrate_idempotency() -> None:
    print("\n" + "=" * 80)
    print("20. IDEMPOTENCY")
    print("=" * 80)

    processor = PaymentProcessor()

    first = processor.process(
        idempotency_key="request-abc",
        amount=Decimal("50.00"),
    )

    retry_result = processor.process(
        idempotency_key="request-abc",
        amount=Decimal("50.00"),
    )

    print(first)
    print(retry_result)


# =============================================================================
# 21. PRODUCTION MONITORING METRICS
# =============================================================================

@dataclass
class RequestMetric:
    timestamp: datetime
    latency_ms: float
    successful: bool


def calculate_error_rate(
    metrics: List[RequestMetric],
) -> float:
    if not metrics:
        return 0.0

    failures = sum(
        not metric.successful
        for metric in metrics
    )

    return failures / len(metrics) * 100


def demonstrate_monitoring() -> None:
    print("\n" + "=" * 80)
    print("21. MONITORING METRICS")
    print("=" * 80)

    now = datetime.now(timezone.utc)

    metrics = [
        RequestMetric(
            timestamp=now,
            latency_ms=50,
            successful=True,
        ),
        RequestMetric(
            timestamp=now,
            latency_ms=60,
            successful=True,
        ),
        RequestMetric(
            timestamp=now,
            latency_ms=900,
            successful=False,
        ),
        RequestMetric(
            timestamp=now,
            latency_ms=70,
            successful=True,
        ),
    ]

    latencies = [
        metric.latency_ms
        for metric in metrics
    ]

    print(
        f"Error rate: "
        f"{calculate_error_rate(metrics):.2f}%"
    )

    print(
        f"p95 latency: "
        f"{percentile(latencies, 95):.2f} ms"
    )

    # Production monitoring should connect metrics with:
    #
    # - logs
    # - traces
    # - infrastructure events
    # - deployment events
    #
    # Observability helps determine not merely that a system failed, but where
    # and why it failed.


# =============================================================================
# 22. BACKUP AND RECOVERY CONCEPTS
# =============================================================================

@dataclass
class Backup:
    created_at: datetime
    data_checksum: str
    size_bytes: int


def recovery_point_age(
    latest_backup: Backup,
    current_time: datetime,
) -> timedelta:
    """
    Simplified Recovery Point Objective measurement.

    A smaller age indicates less potential data loss.
    """
    return current_time - latest_backup.created_at


def demonstrate_backup_concepts() -> None:
    print("\n" + "=" * 80)
    print("22. BACKUP AND RECOVERY")
    print("=" * 80)

    now = datetime.now(timezone.utc)

    backup = Backup(
        created_at=now - timedelta(minutes=30),
        data_checksum="example-checksum",
        size_bytes=1_000_000,
    )

    age = recovery_point_age(
        backup,
        now,
    )

    print(
        f"Latest backup age: "
        f"{age.total_seconds() / 60:.0f} minutes"
    )

    # RPO: Recovery Point Objective
    #      Maximum acceptable amount of data loss measured in time.
    #
    # RTO: Recovery Time Objective
    #      Maximum acceptable time required to restore service.
    #
    # Backups are useful only if restoration procedures are tested.


# =============================================================================
# 23. COMMON CLOUD COMPUTING CHALLENGES CHECKLIST
# =============================================================================

def print_production_checklist() -> None:
    print("\n" + "=" * 80)
    print("23. PRODUCTION CLOUD CHALLENGES CHECKLIST")
    print("=" * 80)

    checklist = {
        "Vendor lock-in": [
            "Identify proprietary dependencies.",
            "Document data export procedures.",
            "Use portable standards where appropriate.",
            "Evaluate migration cost before adoption.",
        ],
        "Latency": [
            "Measure p50, p95, and p99 latency.",
            "Deploy workloads near users when appropriate.",
            "Use caching carefully.",
            "Define request timeouts and deadlines.",
        ],
        "Security": [
            "Apply least privilege.",
            "Protect secrets.",
            "Encrypt sensitive data.",
            "Review configurations continuously.",
            "Maintain useful audit logs.",
        ],
        "Compliance": [
            "Identify applicable requirements.",
            "Map controls to technical implementations.",
            "Maintain evidence and documentation.",
            "Review changes that affect compliance scope.",
        ],
        "Outages": [
            "Identify dependency failure modes.",
            "Use retries carefully.",
            "Implement circuit breakers where appropriate.",
            "Test failover and recovery procedures.",
        ],
        "Data residency": [
            "Track primary and replica locations.",
            "Review backup locations.",
            "Review analytics and logging pipelines.",
            "Validate jurisdiction requirements.",
        ],
        "Cost management": [
            "Tag resources.",
            "Define budgets and alerts.",
            "Detect anomalies.",
            "Remove unused resources.",
            "Evaluate cost-performance trade-offs.",
        ],
    }

    for category, items in checklist.items():
        print(f"\n{category}")

        for item in items:
            print(f"  [ ] {item}")


# =============================================================================
# 24. MAIN PROGRAM
# =============================================================================

def main() -> None:
    """
    Execute every demonstration in a logical learning sequence.
    """
    demonstrate_shared_responsibility()

    demonstrate_vendor_lock_in()
    demonstrate_data_migration()

    demonstrate_latency()
    demonstrate_caching()

    demonstrate_security()
    demonstrate_secret_handling()
    demonstrate_security_validation()

    demonstrate_compliance()
    demonstrate_audit_logging()

    demonstrate_outages()
    demonstrate_circuit_breaker()

    demonstrate_data_residency()

    demonstrate_cost_management()
    demonstrate_cost_anomalies()
    demonstrate_resource_tagging()

    demonstrate_integrated_assessment()

    demonstrate_tradeoffs()
    demonstrate_timeouts()
    demonstrate_idempotency()

    demonstrate_monitoring()
    demonstrate_backup_concepts()

    print_production_checklist()


if __name__ == "__main__":
    main()
