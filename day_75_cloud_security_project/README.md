# Cloud Security Governance and Infrastructure Protection

## Project Description

This project implements a cloud infrastructure security governance model using five complementary technical implementations: Python, JavaScript, C++17, Java 17, and PostgreSQL.

The system demonstrates how identity controls, network segmentation, encryption, audit logging, and security monitoring work together to protect cloud resources.

The implementations model a cloud environment containing identities, storage resources, access policies, network restrictions, encryption configurations, and security incidents.

The primary security objective is to ensure that a cloud resource is accessible only when identity authorization, network restrictions, resource availability, and encryption requirements are satisfied.

## Security Architecture

The system follows a layered security architecture.

| Security layer | Responsibility | Principal mechanism |
|---|---|---|
| Identity and Access Management | Determine who can perform an operation | Role-based access control |
| Network isolation | Restrict permitted network traffic | CIDR-based security rules |
| Encryption | Protect stored and transmitted information | Encryption configuration and key governance |
| Audit logging | Maintain records of security-relevant activities | Structured and append-oriented events |
| Security monitoring | Detect suspicious activity | Threshold-based event analysis |
| Governance | Enforce infrastructure security requirements | Policy evaluation and resource-state controls |

### Logical architecture

    Cloud Infrastructure
            |
            v
    Identity Authentication
            |
            v
    IAM Authorization
            |
            v
    Network Policy Evaluation
            |
            v
    Resource Security Validation
            |
            v
    Access Decision
       /         \
    ALLOW        DENY
       \         /
            v
       Audit Logging
            |
            v
       Security Monitoring
            |
            v
       Incident Detection
            |
            v
       Security Assessment

The architecture applies deny-by-default authorization. An identity does not receive access merely because it exists or belongs to an authenticated account.

## Identity and Access Management

Identity and Access Management (IAM) establishes which identities can perform operations on cloud resources.

An identity can represent:

- A human administrator.
- A developer.
- A service account.
- An application.
- An automated infrastructure process.

The implementations use Role-Based Access Control (RBAC).

RBAC separates identity assignment from permission definition.

The relationship is:

    Principal
        |
        v
      Role
        |
        v
    Permission
        |
        v
    Resource

A role contains one or more permissions. An identity receives one or more roles. Authorization evaluates whether the assigned roles provide permission for the requested operation.

### Permission structure

A permission contains:

| Attribute | Description |
|---|---|
| Action | Requested operation, such as `storage:read` |
| Resource | Resource identifier or permitted resource pattern |
| Effect | Allow or Deny |

The implementations support exact resource matching, wildcard actions, and resource-prefix matching.

For example, `storage:read` on `bucket-finance-001` permits a read operation on that resource when the identity satisfies the other security conditions.

### Authorization decisions

Three important conditions are evaluated:

1. The identity must exist and remain enabled.
2. The identity must have a matching permission.
3. MFA must be satisfied when required.

The JavaScript and PostgreSQL implementations also demonstrate explicit deny precedence.

An explicit denial overrides a matching allowance. An unmatched permission results in denial.

### Least privilege

Least privilege means assigning only the permissions necessary for an identity's operational responsibilities.

A storage reader should not automatically receive storage deletion or administrative permissions.

Service identities should have narrowly scoped permissions and should not inherit broad human administrator privileges.

MFA, identity lifecycle management, permission reviews, and account deactivation are important controls against unauthorized access.

## Network Isolation and Segmentation

Network isolation limits communication between cloud resources and external systems.

A cloud resource should not be exposed to every network merely because its identity permissions are correctly configured.

The project models network access through:

- IP address ranges.
- CIDR notation.
- TCP and UDP protocols.
- Port restrictions.
- Ingress and egress direction.
- Resource-specific network rules.

### CIDR notation

CIDR represents a network using an IP address and prefix length.

Examples:

| CIDR | Meaning |
|---|---|
| `10.20.0.0/16` | Private network containing a large address range |
| `10.20.1.0/24` | More narrowly scoped private subnet |
| `192.168.1.0/24` | Private network segment |
| `0.0.0.0/0` | All IPv4 addresses |

The network implementations evaluate whether a supplied source address belongs to an authorized network range.

A network rule must also match the requested protocol and port.

### Ingress and egress

Ingress describes traffic entering a resource.

Egress describes traffic leaving a resource.

The implementations distinguish these directions instead of treating network permission as a single unrestricted property.

The Python and C++ implementations use explicit direction fields. The JavaScript and Java examples implement inbound access evaluation. PostgreSQL stores both directions and evaluates the selected direction.

### Defense in depth

Network authorization is independent of IAM authorization.

A principal with valid IAM permissions must still originate from an allowed network.

Similarly, an allowed network address does not provide permissions to an unauthorized identity.

This prevents either control from becoming a substitute for the other.

## Encryption and Key Governance

Encryption protects information against unauthorized disclosure.

The project distinguishes two encryption requirements.

### Encryption at rest

Encryption at rest protects stored information.

Relevant resources include:

- Object storage.
- Database volumes.
- Snapshots.
- Backups.
- Persistent disks.

The resource registration process requires at-rest encryption.

### Encryption in transit

Encryption in transit protects information while it moves between systems.

HTTPS and TLS-based communication are common mechanisms for protecting network communications.

The project represents transport encryption as a security configuration requirement.

It does not implement a TLS server or encrypt application payloads.

### Encryption key management

Encryption depends on appropriate key lifecycle management.

Important key-management operations include:

- Key generation.
- Secure key storage.
- Key access restrictions.
- Key rotation.
- Key revocation.
- Key disablement.
- Key usage auditing.

The Python implementation models key creation, enablement, and rotation metadata.

The PostgreSQL implementation maintains key references, algorithms, rotation intervals, and rotation timestamps.

The Java and C++ implementations evaluate resource encryption configuration as a mandatory security condition.

AES-256-GCM is included in the database configuration as an authenticated encryption algorithm.

### Key rotation

Key rotation periodically replaces or updates encryption keys.

The database includes:

- `key_rotation_days`
- `last_rotated_at`
- `key_enabled`

These attributes support identifying keys whose rotation interval has expired.

A production key-management service must also preserve access to previously encrypted data during key transitions and securely control key material.

## Audit Logging

Audit logging provides evidence of security-relevant activities.

An audit record captures:

| Attribute | Purpose |
|---|---|
| Event identifier | Unique event reference |
| Timestamp | Time of occurrence |
| Principal | Identity performing the operation |
| Action | Requested operation |
| Resource | Target cloud resource |
| Source IP | Originating network address |
| Decision | Allow or Deny |
| Severity | Event importance |
| Details | Additional structured information |

The Python implementation uses an append-oriented hash chain.

Each record incorporates the hash of the previous record. Changing an earlier event consequently invalidates subsequent hash calculations.

The JavaScript implementation uses SHA-256 to calculate event hashes and provides a JSON export operation.

The Java implementation uses immutable records and a repository interface to separate audit persistence from access evaluation.

The C++ implementation uses sequential event identifiers.

The PostgreSQL implementation uses a dedicated `audit_logs` table and prevents ordinary updates and deletions through a trigger.

### Audit integrity limitations

A hash chain is a tamper-evidence mechanism, not an independent guarantee of immutability.

An administrator controlling both the events and the hashes may reconstruct a modified chain.

Production deployments should use separately controlled audit storage, restricted database privileges, durable retention, cryptographic integrity verification, and appropriate log replication.

Audit records should also avoid unnecessary secrets, access tokens, credentials, and sensitive personal information.

## Security Monitoring and Incident Detection

Security monitoring analyzes events to identify unusual or potentially malicious activity.

The project implements a threshold-based detection mechanism.

For example:

- Three denied access attempts from one identity.
- A repeated attempt to access a protected resource.
- An unauthorized request from an unapproved network.
- Attempts to access a resource in a disabled or quarantined state.

The monitoring model groups denied events by identity.

When the number of denials reaches the configured threshold, the system generates a high-severity alert.

### Detection workflow

    Security Event
          |
          v
    Event Classification
          |
          v
    Identity-Based Aggregation
          |
          v
    Threshold Evaluation
          |
       /      \
    Below    Reached
       |        |
    Continue   v
             Alert
               |
               v
          Incident Record

The Python, JavaScript, C++, and Java implementations maintain in-memory monitoring state.

The PostgreSQL implementation aggregates denied requests over a configurable time window and creates incident records.

### Incident lifecycle

The database supports four incident states:

| State | Meaning |
|---|---|
| OPEN | A security incident has been detected |
| INVESTIGATING | Investigation is in progress |
| CONTAINED | Immediate exposure has been controlled |
| RESOLVED | Incident handling has been completed |

A detected alert and a resolved incident are different concepts.

Detection establishes that an event pattern requires attention. Resolution requires an appropriate investigation and response.

### Monitoring limitations

A threshold-based detector is useful for demonstrating event aggregation, but it is not a complete threat detection system.

Production monitoring should consider:

- Unusual login locations.
- Impossible travel patterns.
- Privilege escalation.
- Unusual API usage.
- Unexpected data transfers.
- Abnormal resource creation.
- Configuration changes.
- Authentication failures.
- Suspicious service-account behavior.

Thresholds should be adjusted to workload characteristics to reduce false positives and missed detections.

## Security Policy Evaluation

The overall access decision combines independent controls.

The principal must satisfy all mandatory conditions:

| Condition | Requirement |
|---|---|
| Identity | Exists and is enabled |
| Authentication | MFA satisfied when required |
| IAM | Requested action is permitted |
| Network | Source IP and port are permitted |
| Resource | Resource is active |
| Encryption | At-rest and in-transit protection are enabled |
| Exposure | Public access complies with policy |

The simplified decision rule is:

    Access Allowed =
        Identity Valid
        AND MFA Valid
        AND IAM Permission Granted
        AND Network Permission Granted
        AND Resource Active
        AND Encryption Compliant

A failed mandatory condition results in denial.

The implementations intentionally separate authorization from resource availability. A user may possess the required IAM permission while the resource remains inaccessible because it has been quarantined.

## Resource Isolation and Quarantine

Quarantine is a containment mechanism.

It changes the operational state of a resource so that normal access requests are rejected.

The supported resource states are:

- `ACTIVE`: Resource can be considered for normal access evaluation.
- `QUARANTINED`: Access is restricted for investigation or containment.
- `DISABLED`: Resource is administratively unavailable.

Quarantine is particularly relevant when monitoring identifies suspicious behavior or when a resource violates security requirements.

The Python, C++, and Java implementations demonstrate resource-state transitions.

The PostgreSQL script demonstrates a transactional quarantine operation.

A production containment process should also account for dependent services, data preservation, business continuity, and recovery authorization.

## Implementation Architecture

Each language approaches the same security domain using its own engineering strengths.

### Python implementation

File role: Cloud security simulation and assessment.

Principal components:

| Component | Responsibility |
|---|---|
| `IAMService` | Role and principal authorization |
| `NetworkSecurityService` | CIDR and port evaluation |
| `EncryptionService` | Encryption key metadata |
| `AuditLogger` | Hash-linked audit events |
| `MonitoringService` | Repeated denial detection |
| `CloudSecurityPlatform` | Coordinates access evaluation |

Python uses dataclasses, enums, dictionaries, sets, and exceptions to express security entities.

The implementation includes executable assertions for successful authorization, network denial, unauthorized access, alert detection, and audit integrity.

The standard-library IP address module performs network validation.

The audit logger uses SHA-256 to produce a tamper-evident event chain.

### JavaScript implementation

File role: Event-driven security policy engine.

Principal components:

| Component | Responsibility |
|---|---|
| `IAMPolicy` | Policy statement evaluation |
| `IAMService` | Identity and policy association |
| `CIDR` | IPv4 network membership |
| `NetworkPolicy` | Network rule evaluation |
| `AuditService` | Structured event persistence and verification |
| `SecurityMonitor` | Event-driven alert generation |
| `CloudSecurityEngine` | Coordinates security operations |

JavaScript uses `Map` for identity and resource lookup, `Set` for policy assignments, and `EventEmitter` for security alert notifications.

The asynchronous access evaluation uses `Promise.all` to coordinate independent policy checks.

The audit service exports records using Node.js filesystem operations.

The export operation uses exclusive file creation and restrictive file permissions to reduce accidental overwriting and local file exposure.

The CIDR implementation intentionally supports IPv4 only.

### C++17 implementation

File role: Deterministic cloud governance and access-decision engine.

Principal components:

| Component | Responsibility |
|---|---|
| `IAMEngine` | Identity and permission evaluation |
| `NetworkEngine` | Network address and CIDR validation |
| `AuditEngine` | Ordered security event storage |
| `MonitoringEngine` | Denial aggregation |
| `CloudGovernanceEngine` | Central access and resource governance |

The implementation uses strongly typed enums, structures, ordered maps, sets, vectors, and STL algorithms.

The IPv4 implementation converts addresses into 32-bit integers and applies subnet masks.

This avoids repeatedly comparing textual IP addresses during rule evaluation.

Resource lookup uses ordered maps, giving logarithmic lookup complexity.

The engine demonstrates access denial following resource quarantine.

### Java 17 implementation

File role: Enterprise-oriented cloud security service model.

Principal components:

| Component | Responsibility |
|---|---|
| `IAMService` | Identity and role authorization |
| `NetworkSecurityService` | Network restrictions |
| `MonitoringService` | Security alert processing |
| `AuditRepository` | Audit persistence abstraction |
| `InMemoryAuditRepository` | Example audit repository |
| `CloudSecurityService` | Resource registration and access evaluation |

Java uses records for immutable domain objects, interfaces for repository abstraction, and concurrent collections for shared state.

The `AuditRepository` interface separates the security service from its persistence mechanism.

This design supports replacing the in-memory implementation with a durable database-backed repository.

Resource state is modeled explicitly, and quarantine changes subsequent authorization outcomes.

The Java implementation uses synchronized access to audit and network-rule collections where needed.

### PostgreSQL implementation

File role: Relational cloud security governance and audit database.

The database uses the `cloud_security` schema.

Its major entities are:

| Table | Purpose |
|---|---|
| `cloud_accounts` | Cloud accounts and deployment environments |
| `identities` | Human and machine identities |
| `iam_roles` | IAM role definitions |
| `iam_permissions` | Permission statements |
| `identity_roles` | Identity-role associations |
| `role_permissions` | Role-permission associations |
| `cloud_resources` | Infrastructure resources |
| `encryption_configurations` | Encryption and key metadata |
| `network_security_rules` | Network access rules |
| `branch_security_policies` | Account-level security requirements |
| `audit_logs` | Access event history |
| `security_incidents` | Detected security incidents |
| `security_monitoring_rules` | Monitoring thresholds |

The database uses primary keys, foreign keys, unique constraints, checks, indexes, views, functions, procedures, and triggers.

PostgreSQL's native `INET` and `CIDR` types provide network address validation and network membership operations.

JSONB stores additional audit information without requiring every event attribute to become a separate column.

The `evaluate_iam` function handles permission matching and explicit denial precedence.

The `evaluate_network` function checks network eligibility.

The `check_access_eligibility` function combines the two authorization mechanisms with resource-state and encryption validation.

The `record_access_attempt` function records the access decision and its audit evidence.

The `process_security_alerts` procedure converts repeated access denials into incident records.

## Database Integrity and Performance

### Referential integrity

Foreign keys preserve relationships between accounts, identities, roles, permissions, and resources.

For example, an identity cannot reference a nonexistent cloud account.

Role assignments cannot reference nonexistent roles.

This reduces inconsistent security configuration.

### Constraint enforcement

Check constraints validate:

- Identity types.
- Cloud environments.
- Permission effects.
- Encryption algorithms.
- Key rotation intervals.
- Network port ranges.
- Incident resolution states.

Triggers prevent ordinary modification of audit records and validate encryption configuration changes.

### Indexing strategy

The database includes indexes for:

- Identity lookup by account.
- Resource lookup by account and state.
- Audit history by identity.
- Audit history by resource.
- Denied access event retrieval.
- Incident investigation.
- Network rules by resource.
- Role assignment retrieval.

The partial index on denied audit events is intended to accelerate security investigations that focus on unsuccessful access attempts.

The GIN index on audit JSONB data supports queries involving structured event attributes.

### Transaction handling

The access-recording function evaluates authorization and inserts the associated audit event in the same database transaction.

The quarantine example demonstrates a transaction that changes the resource state and verifies the resulting value before committing.

A failed transaction should be rolled back to avoid partially applied state changes.

## Security Scenarios

The examples use a finance storage resource named `bucket-finance-001`.

The cloud environment contains:

- An authorized cloud operator.
- A security auditor.
- An unauthorized service identity.
- A storage reader role.
- A restricted internal network.
- An encryption configuration.
- An audit and monitoring mechanism.

The scenarios cover the following conditions.

| Scenario | Expected result | Security reason |
|---|---|---|
| Authorized operator, valid network, valid MFA | ALLOW | All mandatory conditions pass |
| Authorized operator from external network | DENY | Network restriction fails |
| Identity without assigned permissions | DENY | IAM authorization fails |
| Identity without required MFA | DENY | Authentication requirement fails |
| Resource quarantined | DENY | Resource is unavailable |
| Encryption configuration missing | DENY or registration failure | Security baseline is not satisfied |
| Public access enabled | Policy violation | Exposure restriction fails |
| Repeated denied requests | Security alert | Monitoring threshold reached |
| Explicit IAM denial | DENY | Explicit denial takes precedence |

## Security Considerations and Limitations

The project is an executable security-governance simulation, not a direct integration with a commercial cloud provider.

The implementations model security decisions and infrastructure configuration but do not provision actual cloud resources.

The following distinctions are important.

### Authentication versus authorization

Authentication establishes the identity of a user or service.

Authorization determines which operations that identity can perform.

MFA is an authentication requirement. IAM permissions are authorization requirements.

Neither should be treated as a replacement for the other.

### Encryption configuration versus encryption execution

The implementations validate encryption settings and key metadata.

They do not encrypt cloud objects, manage production cryptographic key material, or establish TLS connections.

A real implementation should integrate with a managed key-management service and enforce encryption through the relevant cloud storage, database, and network services.

### Audit integrity versus audit availability

The in-memory audit implementations demonstrate event recording and integrity checking.

They do not provide durable storage, replication, disaster recovery, or independent administrative separation.

Production audit infrastructure requires retention policies and access restrictions.

### Network simulation versus cloud network enforcement

The examples evaluate CIDR, protocol, and port rules.

They do not create virtual private clouds, subnets, route tables, firewalls, network access control lists, or security groups.

A cloud deployment must translate the security model into provider-specific network controls.

### Monitoring versus complete threat detection

Threshold-based monitoring detects repeated access denials.

It does not implement behavioral analytics, advanced anomaly detection, threat intelligence correlation, or comprehensive incident response.

Production monitoring must consider the broader context of cloud activity and operational baselines.

### Concurrency and persistence

The in-memory implementations are intended for controlled demonstrations.

A production deployment requires durable persistence, distributed coordination, atomic policy updates, reliable event delivery, and consistent security decisions across service instances.

Policy changes should be versioned and audited.

## Performance Characteristics

The main computational characteristics are:

| Operation | Implementation approach | Expected complexity |
|---|---|---|
| Python identity lookup | Dictionary | Average O(1) |
| Python permission evaluation | Permission-set iteration | O(P) |
| JavaScript identity lookup | Map | Average O(1) |
| JavaScript CIDR evaluation | Integer masking | O(1) per rule |
| C++ resource lookup | Ordered map | O(log R) |
| C++ network evaluation | Rule iteration | O(N) |
| Java identity lookup | ConcurrentHashMap | Average O(1) |
| Java role evaluation | Collection traversal | O(P) |
| PostgreSQL resource lookup | Indexed relational lookup | Index-dependent |
| PostgreSQL audit retrieval | B-tree and partial indexes | Index-dependent |

Where:

- `R` represents the number of registered resources.
- `P` represents the number of permissions examined.
- `N` represents the number of applicable network rules.

Large-scale deployments should use indexed policy evaluation, caching with controlled invalidation, distributed audit processing, and partitioned event storage.

## Execution Requirements

| Deliverable | Runtime | Dependencies |
|---|---|---|
| Python | Python 3.10+ | Standard library |
| JavaScript | Node.js 18+ | Node.js standard library |
| C++17 | C++17 compiler | Standard library |
| Java | Java 17 | JDK standard library |
| PostgreSQL | PostgreSQL 15+ | PostgreSQL database |

### Python

Run the script using Python 3.

The executable assertions validate access decisions, encryption key availability, audit integrity, and monitoring behavior.

### JavaScript

Run the file using Node.js.

The main function executes policy evaluation, asynchronous access requests, event monitoring, and security reporting.

### C++17

Compile using a C++17-compatible compiler.

The program executes the governance scenarios and displays access decisions and security alerts.

### Java 17

Compile and run the `CloudSecurityPlatform` class.

The program demonstrates enterprise-style service composition, access evaluation, and incident monitoring.

### PostgreSQL

Execute the SQL script in an isolated PostgreSQL database with permission to create schemas, types, tables, functions, triggers, and procedures.

The script creates its own schema and sample data.

The SQL examples include successful and unsuccessful access requests, permission evaluation, monitoring, incident generation, reporting, and resource quarantine.

## Educational Outcomes

The implementations establish the relationship between the major components of cloud security.

The central engineering principle is that infrastructure protection requires multiple independent controls.

IAM restricts identity permissions.

Network isolation restricts communication paths.

Encryption protects information.

Audit logging preserves security evidence.

Monitoring identifies suspicious behavior.

Governance combines these controls into enforceable security requirements.

A secure cloud access decision therefore depends on the combined state of the identity, its permissions, the network, the resource, and its security configuration.
