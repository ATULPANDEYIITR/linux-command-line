# Compliance and Governance Management System

## 1. Project Scope

Compliance and governance provide the organizational mechanisms required to manage information responsibly, protect personal data, enforce internal policies, demonstrate regulatory accountability, and maintain reliable evidence of operational decisions.

This project implements a multi-language compliance management system using Python, JavaScript, C++17, Java 17, and PostgreSQL.

The implementations cover seven connected operational areas:

1. Data privacy and information classification.
2. Regulatory frameworks and obligations.
3. Consent and lawful processing.
4. Governance policies and access controls.
5. Data subject rights and retention management.
6. Compliance assessments and risk findings.
7. Audit evidence and governance reporting.

The central distinction is between **regulatory compliance** and **organizational governance**.

- Compliance determines whether applicable legal and regulatory obligations are being satisfied.
- Governance establishes organizational responsibilities, decision-making authority, policies, controls, and accountability.
- Risk management identifies and prioritizes conditions that may prevent an organization from meeting its obligations.
- Auditing examines evidence to determine whether controls operate as intended.

A policy can exist without being effectively implemented. A control can operate without sufficient evidence. A successful technical check does not independently establish legal compliance.

## 2. Regulatory Frameworks

The implementations use four regulatory and governance references.

| Framework | Jurisdiction | Main concern |
|---|---|---|
| GDPR | European Union | Personal data processing, individual rights, lawful bases, accountability |
| Digital Personal Data Protection Act, 2023 | India | Digital personal data processing and protection |
| ISO/IEC 27001 | International | Information security management systems |
| HIPAA | United States | Protected health information safeguards |

These frameworks are not interchangeable.

### 2.1 GDPR

The General Data Protection Regulation establishes requirements for personal data processing in the European Union and relevant cross-border processing activities.

Important concepts include:

- Lawfulness, fairness, and transparency.
- Purpose limitation.
- Data minimization.
- Accuracy.
- Storage limitation.
- Integrity and confidentiality.
- Accountability.
- Data subject rights.
- Appropriate technical and organizational safeguards.

The lawful bases represented in the implementations are:

| Legal basis | Meaning |
|---|---|
| Consent | The individual has provided valid consent for a specified purpose |
| Contract | Processing is necessary for a contract or relevant pre-contractual steps |
| Legal obligation | Processing is necessary to comply with a legal obligation |
| Legitimate interest | Processing is supported by a legitimate interest, subject to applicable conditions and balancing |
| Public task | Processing is necessary for a qualifying public-interest task |
| Vital interest | Processing is necessary to protect vital interests |

Consent is only one possible legal basis. Withdrawal of consent does not automatically invalidate processing that independently relies on another lawful basis.

### 2.2 Digital Personal Data Protection Act, 2023

India's Digital Personal Data Protection Act, 2023 establishes a framework for processing digital personal data.

Relevant operational concepts include:

- Data fiduciary responsibilities.
- Data principal rights.
- Lawful processing.
- Consent management.
- Security safeguards.
- Personal data breach responsibilities.
- Retention and erasure obligations.
- Grievance handling.
- Accountability.

Applicability, exemptions, commencement notifications, rules, and implementation requirements must be assessed against the legal position applicable to the organization and processing activity.

The database uses `DPDPA` as a regulatory mapping identifier. It does not independently determine statutory applicability.

### 2.3 ISO/IEC 27001

ISO/IEC 27001 concerns the establishment, implementation, maintenance, and continual improvement of an information security management system.

Its organizational approach includes:

- Information security risk assessment.
- Risk treatment.
- Defined security responsibilities.
- Access control.
- Asset management.
- Incident management.
- Supplier security.
- Operational controls.
- Internal audits.
- Management review.
- Continual improvement.

An organization cannot claim ISO/IEC 27001 certification merely because it implements individual security controls.

Certification concerns the assessed management system and its defined scope.

### 2.4 HIPAA

HIPAA establishes requirements relevant to protected health information in the United States.

Its major regulatory components include:

- Privacy Rule.
- Security Rule.
- Breach Notification Rule.

The project uses HIPAA as a framework-mapping example. It does not implement the complete HIPAA Security Rule, business associate arrangements, or all applicable privacy and breach notification obligations.

## 3. Data Privacy and Classification

Data classification determines how information must be handled according to its sensitivity, business value, and potential consequences of unauthorized disclosure.

The project uses five classifications.

| Classification | Description | Example |
|---|---|---|
| PUBLIC | Approved for unrestricted disclosure | Public product catalogue |
| INTERNAL | Intended for organizational use | Operational reports |
| CONFIDENTIAL | Restricted business information | Internal commercial records |
| PERSONAL | Information relating to an identifiable individual | Customer identity records |
| SENSITIVE_PERSONAL | Highly sensitive personal information | Health-related records |

Classification and regulatory applicability are different concepts.

A confidential business record is not necessarily personal data. Personal data may also be confidential, but its regulatory treatment depends on the applicable legal framework.

Sensitive information requires stronger safeguards and more careful processing assessments.

### 3.1 Data Asset Register

A data asset is a managed information resource with an identifiable owner, processing purpose, classification, legal basis, and retention period.

The project models:

- Unique asset identifiers.
- Asset names.
- Ownership.
- Privacy classification.
- Processing purpose.
- Legal basis.
- Applicable frameworks.
- Encryption status.
- Retention duration.
- Active or inactive status.

The Python implementation uses `DataAsset` dataclasses.

The JavaScript implementation uses structured objects stored in Maps.

The C++ implementation uses a strongly typed `DataAsset` structure.

Java uses an immutable `DataAsset` record.

PostgreSQL uses the relational `data_assets` table and associated framework mapping table.

### 3.2 Data Minimization

Data minimization means collecting and processing only the personal data necessary for a defined purpose.

An organization should establish:

- Which data fields are necessary.
- Why each field is collected.
- Whether a less intrusive alternative exists.
- Which employees require access.
- How long the information is needed.

The project stores processing purposes with data assets so that consent and governance decisions can be associated with a defined processing activity.

A production implementation should also maintain field-level inventories and processing records.

### 3.3 Purpose Limitation

Personal data collected for one purpose should not automatically be reused for an unrelated purpose.

For example:

A customer identity record collected for account administration should not automatically become available for unrelated marketing analytics.

The implementations validate that a consent record matches the purpose declared for its asset.

Purpose compatibility and further-processing assessments require additional legal and contextual evaluation.

## 4. Consent and Lawful Processing

Consent management establishes whether a processing activity relying on consent has the necessary authorization.

The project represents three consent states:

| State | Meaning |
|---|---|
| GRANTED | Consent has been recorded |
| WITHDRAWN | Consent has been withdrawn |
| EXPIRED | The recorded consent has passed its expiration date |

A consent record contains:

- Consent identifier.
- Subject reference.
- Associated asset.
- Processing purpose.
- Grant timestamp.
- Expiration timestamp.
- Withdrawal status.

### 4.1 Consent Validation

Processing based on consent requires a matching record.

The system evaluates:

1. Whether the data asset exists.
2. Whether the asset remains active.
3. Whether the asset declares consent as its legal basis.
4. Whether the subject reference matches.
5. Whether the processing purpose matches.
6. Whether consent remains valid.
7. Whether consent has been withdrawn.

The principal processing rule is:

`Processing permitted = Active asset AND Matching subject AND Matching purpose AND Valid consent`

This is a simplified technical rule, not a complete legal assessment of consent validity.

### 4.2 Consent Withdrawal

Withdrawal changes the authorization state of the consent record.

After withdrawal, a processing attempt relying exclusively on that consent is denied.

The system preserves the consent record rather than deleting the evidence of the original decision.

This supports accountability and historical review.

A production system must distinguish:

- Withdrawal of consent.
- Erasure of personal data.
- Restriction of processing.
- Expiration of retention.
- Processing supported by another valid legal basis.

These are separate legal and operational events.

## 5. Governance Policies

A governance policy specifies organizational expectations and control requirements.

Examples include:

- Personal data encryption policy.
- Data retention policy.
- Access management policy.
- Information classification policy.
- Audit logging policy.
- Third-party data handling policy.
- Incident response policy.

The project models policies with:

| Attribute | Purpose |
|---|---|
| Policy ID | Unique identifier |
| Policy name | Descriptive name |
| Encryption requirement | Determines whether encryption is mandatory |
| Maximum retention | Defines an organizational retention limit |
| Enabled state | Determines whether the policy is active |
| Applicable categories | Defines the information classifications covered |

### 5.1 Policy Evaluation

The governance engine evaluates an asset against applicable policies.

For example:

A personal information asset may be subject to a policy requiring encryption and a maximum retention period of 3,650 days.

The evaluation produces:

- Policy-compliant conditions.
- Policy violations.
- Risk findings.
- Governance blockers.
- Optional warnings.

A failed policy check does not necessarily establish a statutory violation. It identifies an organizational control failure requiring assessment.

### 5.2 Policy Conflicts

Policy conflicts can occur when two active policies impose inconsistent requirements.

Examples include:

- One policy requiring deletion after a short period while another specifies a longer retention requirement.
- A business unit requesting broader access than an information classification policy permits.
- A regulatory preservation obligation conflicting with a routine deletion schedule.

The project evaluates applicable policy requirements but does not implement a complete legal precedence or conflict-resolution engine.

In an enterprise environment, conflicts should be escalated to authorized privacy, legal, security, and records-management personnel.

## 6. Identity and Access Management

Access control determines which users may perform particular operations.

The implementations use role-based access control.

| Role | Responsibilities |
|---|---|
| COMPLIANCE_ADMIN | Manages assets, policies, requests, and governance |
| PRIVACY_OFFICER | Manages consent and subject requests |
| ANALYST | Reads authorized asset records |
| AUDITOR | Reviews compliance and audit evidence |

Permissions are represented independently from users.

This separation allows permissions to be changed without rewriting individual user records.

### 6.1 Authorization Workflow

The authorization process is:

`User → Active Account → Assigned Role → Permission Check → Operation`

If authorization fails:

1. The operation is rejected.
2. An access-denied event is recorded.
3. The protected operation is not executed.

### 6.2 Least Privilege

Least privilege means granting users only the access required for their responsibilities.

An analyst does not automatically receive policy-management or consent-management permissions.

An auditor receives evidence-review permissions without automatically receiving permission to modify governance policies.

### 6.3 Security Limitations

The source implementations demonstrate authorization logic but do not provide complete production identity infrastructure.

Production deployments should incorporate:

- Strong authentication.
- Multi-factor authentication.
- Centralized identity management.
- Session expiration.
- Secure credential storage.
- Privileged access management.
- Separation of duties.
- Periodic access certification.
- Emergency access controls.
- Centralized authorization enforcement.

The example database stores role assignments and permissions. It does not implement password authentication.

## 7. Data Subject Rights Management

Data subject rights allow individuals to exercise legally recognized rights concerning their personal data.

The project represents five request categories.

| Request | Purpose |
|---|---|
| ACCESS | Obtain information about personal data processing |
| RECTIFICATION | Request correction of inaccurate information |
| ERASURE | Request deletion where applicable |
| PORTABILITY | Request qualifying personal data in a portable format |
| RESTRICTION | Request restriction of processing under applicable conditions |

The exact rights, conditions, exceptions, and response periods depend on the applicable jurisdiction and legal framework.

### 7.1 Request Lifecycle

The implementations use the following workflow:

`RECEIVED → VERIFIED → IN_PROGRESS → COMPLETED`

A request may also transition to `REJECTED` where an appropriate decision is made.

The workflow prevents invalid transitions.

For example:

- A request cannot move directly from RECEIVED to COMPLETED.
- A completed request cannot be reopened through the normal transition process.
- A rejected request cannot continue through the ordinary processing lifecycle.

### 7.2 Request Tracking

Each request contains:

- Unique request identifier.
- Subject reference.
- Request category.
- Current status.
- Receipt timestamp.
- Response deadline.
- Processing version.
- Completion timestamp where applicable.

The JavaScript and Java implementations use optimistic concurrency checks to prevent updates based on stale request versions.

The PostgreSQL implementation uses row-level locking during transactional workflow updates.

### 7.3 Operational Implications

A mature subject-rights process should support:

- Identity verification.
- Request classification.
- Scope determination.
- Data discovery.
- Legal exception assessment.
- Departmental coordination.
- Response preparation.
- Deadline monitoring.
- Evidence preservation.
- Secure delivery.
- Closure documentation.

The source programs implement the workflow state and validation layer, not complete identity verification or data discovery across external systems.

## 8. Data Retention and Erasure

Retention governance determines how long an organization should keep information.

Retention requirements may arise from:

- Legal obligations.
- Contractual requirements.
- Business necessity.
- Regulatory preservation requirements.
- Litigation holds.
- Security investigation requirements.

The project associates a retention period with each asset.

The expiration calculation is:

`Retention expiration = Asset creation timestamp + Retention duration`

The Python and JavaScript implementations identify assets whose retention periods have expired.

The PostgreSQL implementation provides the `retention_status` view and `deactivate_expired_assets` procedure.

### 8.1 Retention Is Not Automatic Erasure

Deactivating an asset is not equivalent to securely deleting every copy of its personal data.

Actual erasure may require:

- Primary database deletion.
- Replica handling.
- Backup lifecycle management.
- Object-storage deletion.
- Search-index cleanup.
- Cache invalidation.
- Third-party processor coordination.
- Legal-hold evaluation.
- Deletion evidence.

The sample implementations use asset deactivation as a governance demonstration.

Production systems must separately manage actual data deletion and its verification.

## 9. Compliance Assessment and Risk Findings

A compliance assessment evaluates whether defined controls satisfy organizational or regulatory requirements.

A control should have:

- Control identifier.
- Control description.
- Assessment result.
- Mandatory or optional classification.
- Evidence reference.
- Assessment timestamp.
- Assessor identity.

The project uses three control outcomes:

| Status | Meaning |
|---|---|
| PASSED | The control has passed assessment |
| FAILED | The control has failed assessment |
| NOT_RUN | No assessment result is available |

### 9.1 Risk Severity

The project uses four risk levels.

| Severity | Interpretation |
|---|---|
| LOW | Limited control deficiency |
| MEDIUM | Material issue requiring remediation |
| HIGH | Significant governance or security concern |
| CRITICAL | Serious control failure requiring urgent attention |

Examples include:

- Missing regulatory mapping: MEDIUM.
- Retention exceeding policy limits: HIGH.
- Missing mandatory encryption: CRITICAL.

These are example risk assignments. Actual severity should be determined using organizational risk criteria, data sensitivity, likelihood, impact, exposure, and applicable obligations.

### 9.2 Findings Lifecycle

A compliance finding should be:

1. Identified.
2. Recorded.
3. Classified.
4. Assigned.
5. Investigated.
6. Remediated.
7. Independently verified.
8. Closed with evidence.

The implementations record findings and provide resolved-state information in the relational model.

A full corrective-action management system would also include ownership, remediation deadlines, root-cause analysis, verification evidence, and escalation rules.

## 10. Audit Logging and Accountability

Audit logging records significant operations so that organizational actions can be investigated and independently reviewed.

The project records events such as:

- Asset registration.
- Asset access.
- Consent creation.
- Consent withdrawal.
- Unauthorized access.
- Policy registration.
- Subject request transitions.
- Retention enforcement.
- Governance evaluation.

An audit record contains:

| Field | Purpose |
|---|---|
| Event identifier | Identifies the event |
| Timestamp | Establishes event time |
| Actor | Identifies the responsible user |
| Action | Describes the operation |
| Resource | Identifies the affected object |
| Details | Stores contextual information |
| Previous hash | Links to the preceding event |
| Event hash | Provides integrity evidence |

### 10.1 Hash Chaining

The Python, JavaScript, and PostgreSQL implementations demonstrate hash-linked audit records.

Conceptually:

`H(n) = SHA256(PreviousHash + EventPayload)`

Each new record incorporates the hash of the preceding record.

A modification to an earlier event causes subsequent integrity verification to fail.

The PostgreSQL implementation uses the `pgcrypto` extension.

### 10.2 Integrity Versus Immutability

Hash chaining provides tamper evidence, not complete immutability.

An attacker who can rewrite the complete event history and recalculate all hashes may defeat a simple hash chain.

The implementations also differ in their protections:

- Python uses an in-memory event sequence.
- JavaScript uses an in-memory event ledger.
- C++ records audit information in an in-memory collection.
- Java maintains a synchronized in-memory audit service.
- PostgreSQL prevents ordinary updates and deletes through a trigger and uses a serialized audit-writing function.

A production audit architecture should incorporate:

- Restricted database privileges.
- Independent audit storage.
- Cryptographic signing or trusted integrity checkpoints.
- Separation of administrative responsibilities.
- Secure timestamp management.
- Monitoring for missing events.
- Backup and recovery controls.
- Periodic integrity verification.
- Retention and legal preservation rules.

Audit records themselves may contain personal or confidential information. Their contents must also be protected.

## 11. Governance Reporting

Compliance reporting transforms operational records into management information.

The project reports:

- Total registered assets.
- Active assets.
- Asset classifications.
- Encryption status.
- Consent status.
- Subject request states.
- Open findings.
- Audit record counts.
- Governance eligibility.

These measurements provide an operational view of governance performance.

Useful management indicators include:

| Indicator | Measurement |
|---|---|
| Asset inventory coverage | Registered assets against identified assets |
| Encryption coverage | Encrypted assets against applicable assets |
| Consent validity | Valid consent records against consent-dependent processing |
| Request completion | Completed subject requests against total requests |
| Overdue requests | Requests exceeding applicable deadlines |
| Open findings | Unresolved compliance findings |
| Policy compliance | Passed applicable controls against assessed controls |
| Audit integrity | Successful verification of recorded audit evidence |

A dashboard is not proof of legal compliance. Its reliability depends on the completeness and accuracy of the underlying data.

## 12. Python Implementation

**File:** `compliance.py`

The Python implementation uses an object-oriented workflow model.

Important components:

| Component | Responsibility |
|---|---|
| `DataAsset` | Represents classified information assets |
| `User` | Represents authorized organizational users |
| `Consent` | Tracks consent status and validity |
| `Policy` | Represents governance requirements |
| `SubjectRequest` | Represents an individual rights request |
| `AuditLogger` | Maintains hash-linked audit records |
| `ComplianceManager` | Coordinates governance operations |

### Python-specific mechanisms

- Dataclasses provide structured domain models.
- Enums prevent arbitrary classification and status values.
- Dictionaries provide identifier-based lookup.
- Sets support permission and framework validation.
- Exceptions represent policy and authorization failures.
- `unittest` validates important business rules.
- JSON serialization supports audit export.
- SHA-256 provides audit-chain integrity checks.

The implementation uses standard-library components and does not require third-party packages.

### Execution

Run with Python 3.10 or later:

`python compliance.py`

The script executes a demonstration followed by validation tests.

## 13. JavaScript Implementation

**File:** `compliance.js`

The JavaScript implementation provides an event-driven compliance engine.

Its main components are:

| Component | Responsibility |
|---|---|
| `ComplianceEngine` | Coordinates compliance operations |
| `EventBus` | Publishes governance events |
| `AuditLedger` | Maintains audit evidence |
| `AccessPolicy` | Evaluates role permissions |
| `ComplianceEngine.registerAsset()` | Registers classified assets |
| `ComplianceEngine.transitionRequest()` | Processes asynchronous request transitions |

### JavaScript-specific mechanisms

**Maps**

Maps provide direct access to assets, users, policies, consents, and requests.

**Sets**

Sets maintain role permissions and prevent duplicate framework mappings.

**Promises**

Asynchronous event processing separates domain operations from audit-event consumers.

**Optimistic concurrency**

Each subject request has a version. An update using an obsolete version is rejected.

**Event-driven auditing**

Asset registration, consent withdrawal, and request transitions publish events that are handled by subscribers.

### Execution

Run using Node.js 18 or later:

`node compliance.js`

No npm dependencies are required.

## 14. C++17 Implementation

**File:** `compliance.cpp`

The C++ implementation focuses on strongly typed governance decisions and efficient in-memory evaluation.

Important components:

| Component | Responsibility |
|---|---|
| `DataAsset` | Defines the information asset |
| `Consent` | Represents subject authorization |
| `Policy` | Defines organizational constraints |
| `StatusCheck` | Represents control-assessment results |
| `Finding` | Represents an identified deficiency |
| `ComplianceEngine` | Enforces governance operations |
| `GovernanceDecision` | Returns eligibility and blockers |

### C++ engineering mechanisms

- Structures model domain objects.
- Enums restrict domain states.
- Maps provide indexed entity lookup.
- Sets provide permission and framework membership checks.
- Vectors maintain audit records and findings.
- Exceptions handle invalid operations.
- Switch-based transitions enforce request lifecycle rules.
- Policy evaluation produces explicit governance blockers.

Map-based lookups generally provide logarithmic complexity, while set membership checks are logarithmic.

Evaluating all policies against an asset has complexity proportional to the number of applicable policies.

### Execution

Compile with a C++17-compatible compiler:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic compliance.cpp -o compliance`

Run:

`./compliance`

On Windows:

`compliance.exe`

No external libraries are required.

## 15. Java 17 Implementation

**File:** `ComplianceGovernance.java`

The Java implementation uses an enterprise-oriented domain architecture.

| Component | Responsibility |
|---|---|
| `RegulatoryRegistry` | Validates regulatory mappings |
| `AccessControlService` | Enforces role permissions |
| `AuditService` | Maintains audit events |
| `RequestWorkflowService` | Manages subject request transitions |
| `GovernanceService` | Coordinates enterprise governance |
| `GovernancePolicy` | Represents policy constraints |
| `GovernanceResult` | Returns eligibility and blockers |

### Java 17 mechanisms

**Records**

Records model immutable domain information such as assets, policies, users, findings, and requests.

**Interfaces and service boundaries**

The implementation separates authorization, audit management, request processing, and governance evaluation into dedicated service classes.

**Collections**

Maps maintain entity relationships, sets represent permissions, and lists store audit and assessment results.

**Streams**

Streams aggregate privacy classifications and request states for reporting.

**Concurrency**

`ReentrantLock` protects request workflow modifications.

Version checks prevent updates using outdated request states.

**Custom exceptions**

Dedicated exceptions distinguish authorization failures, validation failures, policy violations, and concurrent update conflicts.

### Execution

Compile:

`javac ComplianceGovernance.java`

Run:

`java ComplianceGovernance`

Java 17 is required.

## 16. PostgreSQL Implementation

**File:** `compliance.sql`

The PostgreSQL implementation provides a normalized relational model.

It establishes the `governance` schema and uses native PostgreSQL capabilities.

### 16.1 Relational Architecture

The principal entity relationships are:

    Organizations
        |
        +---- Governance Users
        |          |
        |          +---- Governance Roles
        |                    |
        |                    +---- Role Permissions
        |
        +---- Data Assets
                   |
                   +---- Asset Frameworks
                   |          |
                   |          +---- Regulatory Frameworks
                   |
                   +---- Consent Records
                   |
                   +---- Compliance Assessments
                   |          |
                   |          +---- Control Results
                   |
                   +---- Compliance Findings
                   |
                   +---- Governance Policies
                              |
                              +---- Policy Categories
                              |
                              +---- Policy Frameworks

    Subject Requests
        |
        +---- Assigned Governance User

    Audit Events
        |
        +---- Governance User

### 16.2 Database Integrity

The database uses:

- Primary keys for entity identification.
- Foreign keys for relationship integrity.
- Unique constraints for business identifiers.
- Check constraints for valid values.
- Enum types for controlled states.
- Triggers for workflow enforcement.
- Procedures for transactional operations.
- Views for operational reporting.
- Functions for eligibility and processing checks.

The `asset_frameworks` table implements a many-to-many relationship between assets and regulatory frameworks.

The `role_permissions` table implements a many-to-many relationship between roles and permissions.

### 16.3 Indexing

The database includes indexes for common operational access patterns.

| Index | Purpose |
|---|---|
| `idx_assets_category` | Classification filtering |
| `idx_assets_owner` | Asset ownership lookup |
| `idx_assets_active` | Active asset retrieval |
| `idx_consent_subject_asset` | Subject and asset consent lookup |
| `idx_requests_status_deadline` | Request processing and deadline monitoring |
| `idx_findings_open` | Unresolved finding retrieval |
| `idx_audit_actor_timestamp` | Actor-based audit investigation |
| `idx_assessments_asset_date` | Historical asset assessment retrieval |

Indexes improve retrieval performance but increase storage and write costs.

### 16.4 Triggers

Three major integrity mechanisms are implemented.

**Consent validation**

The consent trigger verifies that the associated asset relies on consent and that the processing purpose matches.

**Request transition validation**

The request trigger rejects invalid workflow transitions and updates the version and completion timestamp.

**Audit immutability**

The audit trigger prevents ordinary updates and deletes of audit records.

These controls help preserve relational integrity even when an operation originates outside the main application workflow.

### 16.5 Database Functions and Procedures

| Database object | Function |
|---|---|
| `append_audit_event` | Appends a hash-linked audit event |
| `verify_audit_chain` | Verifies audit-chain integrity |
| `can_process_asset` | Evaluates processing authorization |
| `evaluate_asset_eligibility` | Evaluates active governance policies |
| `transition_subject_request` | Performs a version-checked request transition |
| `deactivate_expired_assets` | Deactivates assets exceeding retention periods |

### 16.6 Transactions

The SQL script executes schema creation, reference data insertion, sample data insertion, and reporting setup inside a transaction.

The subject-request procedure uses row-level locking to protect concurrent updates.

The version check provides an additional safeguard against stale updates.

A failed transaction can be rolled back without leaving partially committed workflow changes.

## 17. Governance Eligibility

Governance eligibility is a decision produced after evaluating applicable conditions.

The project distinguishes between:

- Processing authorization.
- Compliance assessment.
- Policy evaluation.
- Risk findings.
- Governance eligibility.

These are related but separate decisions.

For example, an asset may have valid consent but still violate an organizational encryption policy.

An asset may satisfy an encryption policy but lack an appropriate legal basis for processing.

A successful control assessment may still be insufficient if other applicable obligations remain unverified.

The general evaluation sequence is:

    Identify Asset
         |
         v
    Determine Classification
         |
         v
    Establish Processing Purpose
         |
         v
    Validate Legal Basis
         |
         v
    Check Authorization
         |
         v
    Evaluate Applicable Policies
         |
         v
    Assess Mandatory Controls
         |
         v
    Record Findings
         |
         v
    Determine Governance Eligibility

The implementations use `ELIGIBLE` and `BLOCKED` as operational decision states.

`ELIGIBLE` means that the modeled conditions have passed. It does not constitute legal certification or proof of compliance with every applicable obligation.

## 18. Practical Governance Scenario

Consider an enterprise maintaining a customer identity database.

The organization processes personal data for customer account administration.

Its governance process includes:

**Asset registration**

The database is registered with its owner, purpose, classification, legal basis, and retention duration.

**Regulatory mapping**

Applicable frameworks are associated with the asset according to the organization's processing activities and jurisdictional assessment.

**Access control**

The compliance administrator manages the asset while analysts receive only authorized access.

**Consent management**

Where consent is the declared legal basis, the system checks whether a matching consent record exists and remains valid.

**Control assessment**

An auditor evaluates encryption, access reviews, retention controls, and supporting documentation.

**Subject rights**

A customer submits an access request. The organization verifies the request and processes it through the controlled workflow.

**Policy evaluation**

The governance engine checks the asset against applicable organizational policies.

**Audit evidence**

Registration, access, consent changes, and workflow transitions are recorded.

**Reporting**

The compliance dashboard presents asset classifications, open findings, request states, and governance results.

This scenario demonstrates how governance controls connect operational data management with accountability and compliance evidence.

## 19. Edge Cases and Failure Handling

The implementations explicitly handle several operational failures.

| Scenario | Expected behavior |
|---|---|
| Duplicate asset identifier | Registration rejected |
| Unknown regulatory framework | Validation failure |
| Invalid privacy classification | Validation failure |
| Sensitive data without encryption | Policy violation |
| Unknown or inactive user | Authorization failure |
| Missing permission | Access denied and audited |
| Consent for unknown asset | Rejected |
| Consent purpose mismatch | Rejected |
| Withdrawn consent | Consent-based processing denied |
| Expired consent | Consent-based processing denied |
| Invalid subject request transition | Rejected |
| Stale request version | Conflict error |
| Expired retention period | Asset flagged or deactivated |
| Missing mandatory control | Governance eligibility blocked |
| Excessive retention | Policy finding or governance blocker |
| Modified audit record | Integrity verification failure |

The implementations use in-memory collections for the application examples. Their operational state is not automatically synchronized across separate application processes.

PostgreSQL provides persistent relational storage, transactional behavior, and database-level constraints.

## 20. Security and Production Considerations

A production compliance platform requires safeguards beyond the demonstration implementations.

### Data protection

- Encrypt data at rest.
- Use TLS for network communication.
- Protect encryption keys separately from encrypted information.
- Apply field-level encryption where justified.
- Avoid logging personal data unnecessarily.
- Restrict sensitive database exports.
- Establish backup protection and recovery procedures.

### Identity and access

- Integrate with enterprise identity providers.
- Enforce multi-factor authentication.
- Apply least privilege.
- Review privileged accounts.
- Implement separation of duties.
- Monitor unusual access patterns.
- Use short-lived credentials and controlled sessions.

### Audit management

- Store audit evidence independently.
- Restrict modification privileges.
- Verify event-chain integrity.
- Use trusted timestamps.
- Preserve required evidence.
- Monitor missing or unexpected events.

### Governance operations

- Maintain a current asset inventory.
- Document processing activities.
- Establish retention schedules.
- Track third-party processors.
- Define incident escalation.
- Conduct periodic privacy assessments.
- Review policies when regulations or business processes change.

### Operational resilience

- Use database backups.
- Test recovery procedures.
- Monitor failed workflows.
- Apply transactional updates.
- Use idempotency for retried operations.
- Introduce durable message queues for asynchronous event processing.
- Monitor application and database performance.

### Regulatory interpretation

The system does not automatically determine which laws apply to an organization.

Legal applicability depends on factors such as:

- Organization location.
- Individual location.
- Processing purpose.
- Nature of information.
- Organizational role.
- Industry.
- Cross-border processing.
- Statutory exemptions.
- Effective regulatory requirements.

Legal and privacy professionals must validate these matters.

## 21. Technical Limitations

| Area | Current implementation | Production requirement |
|---|---|---|
| Asset inventory | Structured in-memory and relational records | Enterprise-wide discovery and reconciliation |
| Privacy classification | Five predefined categories | Organization-specific classification taxonomy |
| Consent | Basic grant, withdrawal, and expiry | Evidence of valid consent and preference management |
| Legal basis | Enumerated categories | Contextual legal assessment |
| Access control | Role-based permission checks | Centralized identity and authorization |
| Subject rights | Controlled state transitions | Identity verification and distributed data discovery |
| Retention | Period-based expiration | Legal holds, backup deletion, and verified erasure |
| Risk | Rule-based findings | Formal likelihood and impact assessment |
| Audit | Hash-linked event records | Independently protected and monitored evidence |
| Reporting | Operational counts | Validated enterprise metrics and audit reconciliation |
| Governance | Policy evaluation | Complete organizational governance framework |

The sample programs demonstrate the core mechanisms and relationships. They do not provide a complete certified compliance management platform.

## 22. Learning Outcomes

The five implementations demonstrate how compliance and governance concepts can be translated into practical engineering mechanisms.

| Technical concept | Governance application |
|---|---|
| Data modeling | Privacy asset inventories |
| Enumerations | Controlled compliance states |
| Role-based access | Least-privilege enforcement |
| Policy evaluation | Organizational control validation |
| State machines | Subject rights workflows |
| Concurrency control | Reliable request processing |
| Event-driven architecture | Governance event handling |
| Hash chaining | Audit tamper evidence |
| Relational normalization | Regulatory and policy relationships |
| SQL triggers | Database integrity enforcement |
| Transactions | Atomic governance operations |
| Indexing | Efficient compliance reporting |
| Aggregation | Management dashboards |
| Exception handling | Safe failure management |

The central engineering principle is that compliance governance requires coordinated controls, defined responsibilities, reliable records, enforceable policies, and verifiable evidence. A single successful technical operation is not sufficient to establish that an organization meets all of its legal and governance obligations.
