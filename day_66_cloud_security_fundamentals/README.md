# Cloud Security Fundamentals

## 1. Introduction

Cloud security is the set of policies, technologies, processes, and controls used to protect cloud-based infrastructure, applications, identities, networks, and information.

Cloud environments operate under a shared responsibility model. Security responsibilities are distributed between the cloud service provider and the customer according to the service being consumed.

Understanding this division is essential because using a cloud provider does not automatically make every customer workload secure.

This project implements cloud security fundamentals through five technical perspectives:

| File | Implementation |
|---|---|
| Python | Cloud security simulation and responsibility evaluation |
| JavaScript | Event-driven cloud security policy evaluation |
| C++17 | Resource governance and security assessment engine |
| Java 17 | Enterprise cloud security management system |
| PostgreSQL | Relational cloud security governance and assessment database |

## 2. Shared Responsibility Model

The shared responsibility model defines which security activities are performed by the cloud provider and which remain the customer's responsibility.

The provider is generally responsible for security of the cloud, while customers are responsible for security in the cloud.

The precise boundary depends on the cloud service model, provider agreements, architecture, and selected configuration.

### 2.1 Infrastructure as a Service (IaaS)

IaaS provides virtualized computing infrastructure, storage, and networking.

The provider manages physical infrastructure and virtualization. The customer generally manages the guest operating system, installed applications, workload identities, and data.

| Security domain | Typical responsibility |
|---|---|
| Physical security | Provider |
| Host infrastructure | Provider |
| Network security | Shared |
| Guest operating system | Customer |
| Application security | Customer |
| Identity and access | Customer |
| Data protection | Customer |
| Configuration | Customer |
| Compliance | Shared |
| Backup and recovery | Customer |

Example: A customer deploying a virtual machine must patch its operating system, configure its firewall, restrict administrative access, and protect application data.

### 2.2 Platform as a Service (PaaS)

PaaS provides a managed application development and execution environment.

The provider manages the underlying infrastructure and operating system. The customer generally manages application code, application dependencies, identities, and data.

| Security domain | Typical responsibility |
|---|---|
| Physical security | Provider |
| Host infrastructure | Provider |
| Network security | Shared |
| Operating system | Provider |
| Application security | Customer |
| Identity and access | Shared |
| Data protection | Customer |
| Configuration | Shared |
| Compliance | Shared |
| Backup and recovery | Shared |

Example: A developer deploying an application to a managed platform does not normally patch the underlying operating system, but remains responsible for application vulnerabilities and access permissions.

### 2.3 Software as a Service (SaaS)

SaaS provides complete applications through a cloud service.

The provider generally manages the infrastructure, operating system, and application platform. The customer remains responsible for appropriate tenant configuration, user management, data classification, and secure service usage.

| Security domain | Typical responsibility |
|---|---|
| Physical security | Provider |
| Host infrastructure | Provider |
| Network security | Provider |
| Operating system | Provider |
| Application security | Provider |
| Identity and access | Shared |
| Data protection | Shared |
| Configuration | Shared |
| Compliance | Shared |
| Backup and recovery | Shared |

Example: An organization using a cloud-based CRM application does not maintain its provider's operating system. It must still configure MFA, manage user privileges, control information sharing, and understand data retention arrangements.

### 2.4 Comparing Service Models

| Characteristic | IaaS | PaaS | SaaS |
|---|---|---|---|
| Physical infrastructure | Provider | Provider | Provider |
| Virtualization | Provider | Provider | Provider |
| Operating system | Customer | Provider | Provider |
| Application code | Customer | Customer | Provider |
| User access | Customer | Shared | Shared |
| Data classification | Customer | Customer | Shared |
| Customer configuration | Extensive | Moderate | Tenant-level |

The table represents typical arrangements. Actual responsibility boundaries must be verified against the selected provider's service documentation and contractual commitments.

## 3. Cloud Security Principles

### 3.1 Confidentiality

Confidentiality ensures that information is accessible only to authorized individuals and systems.

Important controls include:

- Identity verification.
- Role-based access control.
- Encryption at rest.
- Encryption in transit.
- Data classification.
- Secure key management.
- Restricted information sharing.

Example: Customer records stored in cloud object storage should be encrypted and accessible only to authorized application identities.

### 3.2 Integrity

Integrity protects information against unauthorized modification, destruction, or corruption.

Important controls include:

- Cryptographic hashes.
- Digital signatures.
- Access restrictions.
- Audit logging.
- Database constraints.
- Change management.
- Backup verification.

Example: An organization can use cryptographic hashes to detect unexpected changes in stored backup files.

### 3.3 Availability

Availability ensures that authorized users can access services when required.

Important controls include:

- Redundant infrastructure.
- Disaster recovery.
- Automated backups.
- Load balancing.
- Monitoring.
- Capacity planning.
- Recovery testing.

Example: A production application can use multiple availability zones to reduce the impact of infrastructure failure.

### 3.4 Least Privilege

Least privilege means granting users and systems only the permissions necessary to perform their responsibilities.

An application service should not receive unrestricted administrative access when it only needs permission to read specific database records.

### 3.5 Defense in Depth

Defense in depth uses multiple independent security controls.

A cloud application may use:

1. Network segmentation.
2. Identity verification.
3. MFA.
4. Application authentication.
5. Encryption.
6. Logging and monitoring.
7. Incident response.

A failure in one control should not automatically expose the entire environment.

### 3.6 Zero Trust

Zero Trust is a security approach based on continuous verification rather than automatic trust based on network location.

Its central principles include:

- Verify explicitly.
- Apply least privilege.
- Assume breach.
- Evaluate identity and device context.
- Continuously monitor access.

Being connected to an internal network does not automatically authorize access to sensitive cloud resources.

## 4. Identity and Access Management

Identity and Access Management (IAM) controls who can access cloud resources and what actions they can perform.

### Authentication

Authentication verifies the identity of a user or system.

Common mechanisms include:

- Password authentication.
- Multi-factor authentication.
- Certificates.
- Federated identity.
- Hardware security keys.
- Workload identities.

### Authorization

Authorization determines which operations an authenticated identity can perform.

For example:

| Role | Typical permissions |
|---|---|
| Security Analyst | Read security findings and update assigned findings |
| Cloud Administrator | Manage cloud infrastructure |
| Auditor | Read compliance evidence |
| Application Owner | Manage application-level configuration |
| Read Only | View permitted resources |

### Multi-Factor Authentication

MFA requires multiple independent authentication factors.

Examples include:

- Something the user knows.
- Something the user possesses.
- Something the user is.

MFA is particularly important for privileged accounts and administrative operations.

### Role-Based Access Control

RBAC associates permissions with roles rather than individually assigning every permission to every user.

This simplifies permission management and supports consistent authorization.

## 5. Cloud Network Security

Cloud network security protects communication between users, applications, services, and infrastructure.

Important mechanisms include:

| Mechanism | Purpose |
|---|---|
| Virtual Private Cloud | Isolates cloud networking environments |
| Subnets | Separates workload groups |
| Security Groups | Controls resource-level traffic |
| Network ACLs | Applies subnet-level traffic rules |
| Web Application Firewall | Filters application-layer traffic |
| VPN | Protects private network connectivity |
| Private Endpoints | Restricts access through private networking |
| Network Segmentation | Limits unauthorized lateral movement |

### Public and Private Resources

A public-facing web server may require inbound HTTPS access.

A database server normally should not expose its database port directly to the public internet.

A secure architecture separates public application components from private data components.

## 6. Cloud Data Protection

Cloud data protection involves securing information throughout its lifecycle.

### 6.1 Data Classification

Data should be classified according to its sensitivity.

Typical categories include:

- Public.
- Internal.
- Confidential.
- Restricted.

Classification determines handling, storage, sharing, encryption, and retention requirements.

### 6.2 Encryption at Rest

Encryption at rest protects stored information.

Examples include:

- Encrypted block storage.
- Database encryption.
- Object storage encryption.
- Encrypted backups.

Key management must include access restrictions, rotation, recovery, and separation of duties.

### 6.3 Encryption in Transit

Encryption in transit protects information moving between systems.

TLS is commonly used to secure application communication.

### 6.4 Backup and Recovery

A backup strategy should define:

- Backup frequency.
- Retention period.
- Encryption requirements.
- Storage isolation.
- Recovery objectives.
- Restoration testing.

Two important recovery measurements are:

**Recovery Time Objective (RTO):** Maximum acceptable time required to restore a service.

**Recovery Point Objective (RPO):** Maximum acceptable amount of data loss measured in time.

A backup is not sufficient evidence of recoverability until restoration has been tested.

## 7. Cloud Security Misconfigurations

Misconfiguration is a significant source of cloud security exposure.

Common examples include:

| Misconfiguration | Potential impact | Security control |
|---|---|---|
| Public storage bucket | Data exposure | Restrict public access |
| Missing MFA | Account compromise | Enforce MFA |
| Excessive permissions | Privilege escalation | Least privilege |
| Unencrypted storage | Data disclosure | Encryption at rest |
| Open firewall rules | Unauthorized access | Network restrictions |
| Unpatched operating system | Exploitation | Patch management |
| Missing audit logs | Reduced visibility | Centralized logging |
| Weak backup configuration | Data loss | Backup validation |

The PostgreSQL implementation includes examples of public storage exposure and missing encryption.

## 8. Security Monitoring and Incident Management

Cloud security monitoring identifies abnormal activity and potential security incidents.

Typical monitored events include:

- Failed authentication attempts.
- Privilege changes.
- Unusual API activity.
- Public resource configuration changes.
- Unexpected network connections.
- Security policy violations.
- Suspicious data access.
- Changes to encryption settings.

### Security Finding Lifecycle

The implementations use the following finding states:

| State | Meaning |
|---|---|
| OPEN | Issue has been identified |
| IN_PROGRESS | Remediation is underway |
| RESOLVED | Remediation has been completed |
| ACCEPTED | Risk has been formally accepted |

A finding should contain:

- Affected resource.
- Security domain.
- Severity.
- Description.
- Detection timestamp.
- Assigned owner.
- Current status.
- Resolution information.

A critical finding should receive priority according to its actual risk and potential business impact.

## 9. Python Implementation

The Python implementation models cloud security through reusable classes, enumerations, and dictionaries.

### Main Components

| Component | Responsibility |
|---|---|
| CloudServiceModel | Represents IaaS, PaaS, and SaaS |
| SecurityDomain | Defines security responsibility areas |
| ResponsibilityMatrix | Maps responsibility by service model |
| CloudResource | Represents a cloud resource |
| SecurityFinding | Stores security issues |
| AccessManager | Evaluates user permissions |
| CloudSecurityPlatform | Coordinates security operations |

### Implemented Operations

- Register cloud resources.
- Register security users.
- Evaluate access permissions.
- Check MFA requirements.
- Create security findings.
- Update finding status.
- Evaluate individual resources.
- Generate severity reports.
- Validate resource identifiers.
- Reject unauthorized operations.

The responsibility matrix uses enumerations to prevent inconsistent responsibility values.

The security findings collection supports aggregation by severity and resource.

The implementation uses in-memory storage. It is intended for workflow simulation rather than persistent production security management.

## 10. JavaScript Implementation

The JavaScript implementation provides an event-driven security evaluation model using Node.js capabilities.

Its engineering perspective emphasizes asynchronous security checks and policy evaluation.

### Main Components

| Component | Responsibility |
|---|---|
| CloudResource | Stores cloud resource properties |
| SecurityPolicy | Defines resource security requirements |
| ResponsibilityEvaluator | Evaluates responsibility boundaries |
| IdentityManager | Manages identity and access decisions |
| SecurityEventEmitter | Publishes security events |
| FindingManager | Tracks security findings |
| SecurityAuditLog | Maintains event history |

The implementation uses:

- Classes and objects for domain modeling.
- Maps for resource and identity registries.
- Sets for permissions and security controls.
- Promises for asynchronous operations.
- Event-driven notifications.
- Validation for invalid resource configurations.
- Structured audit events.

Asynchronous security checks allow independent resource evaluations to execute concurrently.

For production systems, concurrency limits should be applied when evaluating large resource inventories.

## 11. C++17 Implementation

The C++ implementation provides a resource-oriented security assessment engine.

Its design focuses on structured security data, efficient collections, and explicit validation.

### Main Components

| Component | Responsibility |
|---|---|
| CloudResource | Represents a cloud resource |
| SecurityControl | Represents a security requirement |
| ResponsibilityMatrix | Determines responsibility ownership |
| SecurityFinding | Represents a detected security issue |
| SecurityAssessment | Evaluates resource controls |
| SecurityReport | Aggregates assessment results |

The implementation uses STL containers to store resources and security findings.

Enumerations distinguish:

- Service models.
- Responsibility categories.
- Security domains.
- Finding severity.
- Finding status.

The implementation validates resource references before recording findings.

Using hash-based containers provides average constant-time resource lookup, while sorting and reporting operations depend on the number of records being processed.

## 12. Java 17 Implementation

The Java implementation models an enterprise cloud security management platform.

It uses records, enums, collections, and service classes to separate responsibilities.

### Domain Components

| Component | Purpose |
|---|---|
| CloudResource | Immutable resource information |
| SecurityFinding | Security issue lifecycle |
| ResponsibilityMatrix | Shared responsibility evaluation |
| User | Identity and permissions |
| AccessManager | Access authorization |
| CloudSecurityPlatform | Security workflow orchestration |

### State Management

Security findings support controlled state transitions.

A resolved or accepted finding cannot be modified through the normal update operation.

This prevents accidental changes to closed security records.

### Authorization

The access manager checks:

- User existence.
- Account activation.
- MFA status.
- Required permission.
- Administrative permission.

The implementation demonstrates authorization decisions, but production systems require a complete IAM integration and independently enforced administrative controls.

## 13. PostgreSQL Database Design

The PostgreSQL implementation provides persistent relational storage for cloud security governance.

The database uses the `cloud_security` schema.

### 13.1 Entity Relationships

The principal relationship structure is:

Cloud Provider

→ Cloud Resources

→ Control Assessments

→ Security Controls

→ Security Findings

→ Security Audit Events

Users are connected to resources through ownership and to security operations through assessment, assignment, and audit records.

The responsibility matrix associates each cloud service model with a security domain and responsible party.

### 13.2 Database Tables

| Table | Purpose |
|---|---|
| cloud_providers | Cloud provider information |
| security_users | Security identities and roles |
| cloud_resources | Registered cloud resources |
| responsibility_matrix | Responsibility mapping |
| security_controls | Security control catalog |
| control_assessments | Control evaluation records |
| security_findings | Identified security issues |
| security_audit_events | Security activity history |

### 13.3 Integrity Constraints

The database uses:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Enumerated data types.
- Timestamp validation.

These mechanisms prevent invalid references and inconsistent records.

### 13.4 Functions

`get_responsibility()` retrieves the responsible party for a service model and security domain.

`evaluate_resource_security()` evaluates the controls associated with a resource and groups the results by security domain.

`record_security_finding()` validates a resource and responsibility mapping before creating a finding.

### 13.5 Procedures

`resolve_security_finding()` validates the user's role, account status, and MFA state before resolving an issue.

The procedure also records an audit event.

### 13.6 Triggers

The finding status trigger maintains status consistency and prevents closed findings from being reopened through ordinary updates.

The assessment audit trigger records control assessment changes.

### 13.7 Views

`resource_security_overview` provides resource-level security information.

`open_security_findings` displays unresolved findings.

`responsibility_report` provides responsibility information for registered resources.

### 13.8 Performance

Indexes support frequent operations involving:

- Resource service models.
- Deployment environments.
- Finding status.
- Finding severity.
- Control assessment status.
- Audit history.

For large deployments, additional considerations include partitioning historical audit events, retention policies, and carefully selected composite indexes.

## 14. Security Assessment Workflow

The five implementations represent different stages of a cloud security assessment process.

Plain-text workflow:

Cloud Resource Registration
        |
        v
Identify Cloud Service Model
        |
        v
Determine Responsibility Boundaries
        |
        v
Identify Applicable Security Controls
        |
        v
Evaluate Resource Configuration
        |
        v
Identify Security Findings
        |
        v
Classify Findings by Severity
        |
        v
Assign Remediation Responsibility
        |
        v
Implement Security Controls
        |
        v
Verify Remediation
        |
        v
Update Assessment and Audit Records

### Responsibility Assignment

A finding should be assigned to the party responsible for the affected security domain.

| Responsibility | Typical action |
|---|---|
| Provider | Raise a provider support or security issue |
| Customer | Remediate customer-controlled configuration |
| Shared | Coordinate implementation and verification |

Responsibility mapping should not be interpreted as proof that a control is effective. Actual security configuration and evidence must be assessed separately.

## 15. Important Security Distinctions

| Concept | Meaning |
|---|---|
| Authentication | Verifies identity |
| Authorization | Determines permitted actions |
| Encryption | Protects information confidentiality |
| Network segmentation | Limits network communication |
| IAM | Manages identities and permissions |
| Vulnerability management | Identifies and addresses weaknesses |
| Security monitoring | Detects suspicious activity |
| Incident response | Coordinates security incident handling |
| Compliance | Demonstrates conformity with applicable obligations |
| Governance | Establishes security policies and accountability |

These mechanisms complement each other but solve different security problems.

## 16. Practical Cloud Security Scenario

Consider an enterprise operating three cloud workloads:

| Workload | Service model | Security responsibility |
|---|---|---|
| Production virtual machine | IaaS | Customer manages operating system and workload security |
| Managed application platform | PaaS | Customer manages application security |
| Enterprise CRM | SaaS | Customer manages tenant configuration and user access |

During a security assessment, the organization identifies:

1. An unpatched production operating system.
2. Excessive inbound network access.
3. An application configuration weakness.
4. An unencrypted storage resource.
5. Weak tenant access configuration.

Each finding is associated with its cloud resource, security domain, severity, and responsible party.

The security team prioritizes critical findings, assigns remediation owners, tracks progress, and records the final assessment.

This scenario demonstrates why cloud security requires both provider-side assurance and customer-side configuration management.

## 17. Limitations and Production Considerations

The implementations demonstrate core security concepts and workflows. They do not constitute a complete cloud security product.

Important production considerations include:

- Integration with actual cloud provider APIs.
- Centralized identity federation.
- Hardware-backed MFA.
- Secure secrets and key management.
- Encryption key rotation.
- Continuous configuration monitoring.
- Vulnerability scanning.
- Centralized log collection.
- Immutable audit storage.
- Automated incident response.
- Backup restoration testing.
- Policy versioning.
- Compliance evidence retention.
- Database access restrictions.
- Encryption of database connections.
- Separation of administrative duties.

The Java and C++ implementations use in-memory state. Their records are not preserved after program termination.

The SQL implementation provides relational persistence, but its sample authorization checks are not a replacement for PostgreSQL role privileges, row-level security, or application-level authentication.

The responsibility matrix is a simplified educational model. Actual cloud responsibility varies by provider, product, deployment configuration, and contractual arrangement.
