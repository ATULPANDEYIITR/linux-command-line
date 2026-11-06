# Identity and Access Management

## 1. Introduction

Identity and Access Management (IAM) is the framework used to establish digital identities, organize users, assign permissions, evaluate access requests, and control access to organizational resources.

IAM answers four fundamental questions:

- Who is requesting access?
- What resource is being requested?
- What operation is being performed?
- Under which organizational rules is the operation permitted?

The implementations demonstrate an enterprise IAM environment using Python, JavaScript, C++17, Java 17, and PostgreSQL.

The central security principle is least privilege: every identity should receive only the permissions necessary to perform its authorized responsibilities.

## 2. Core IAM Concepts

### 2.1 Identity

An identity represents a person, service, application, or other entity that interacts with an information system.

A user identity generally contains:

| Attribute | Purpose |
|---|---|
| User ID | Unique identity identifier |
| Username | Human-readable login identifier |
| Email | Communication and identity attribute |
| Department | Organizational classification |
| Status | Current account lifecycle state |
| Created timestamp | Identity creation record |
| Version | Identity modification tracking |

The implementations distinguish three account states:

- `ACTIVE`: The identity can request authorized operations.
- `DISABLED`: Access is suspended.
- `LOCKED`: Access is blocked because of a security or administrative condition.

A disabled identity must not receive permissions through previously assigned roles.

### 2.2 Users and Groups

Users represent individual identities. Groups organize identities according to organizational responsibilities.

Examples include:

- FinanceTeam
- EngineeringTeam
- SecurityTeam

A user can belong to multiple groups, and a group can contain multiple users.

This many-to-many relationship reduces administrative effort. Instead of assigning the same permissions independently to every employee, an administrator assigns roles to a group.

The relationship is:

`User → Group Membership → Group`

Removing a user from a group removes permissions inherited through that membership, subject to any remaining independent assignments.

### 2.3 Roles

A role represents a collection of permissions associated with a responsibility.

Examples:

| Role | Responsibility |
|---|---|
| ReportReader | Read business reports |
| ReportEditor | Read and create reports |
| PayrollAuditor | Read payroll information |
| SecurityAdministrator | Manage identity records |

Roles separate organizational responsibilities from individual identities.

A role does not represent a user. It represents a reusable permission collection.

The relationship is:

`User → Group → Role → Permission`

The implementations also demonstrate direct user-role assignments. These are useful in exceptional cases but should be minimized because group-based assignments are easier to govern and review.

### 2.4 Permissions

A permission defines an operation on a resource.

It consists of two components:

- Resource: The protected object or service.
- Action: The operation permitted on that resource.

Examples:

| Resource | Action | Meaning |
|---|---|---|
| reports | read | Read reports |
| reports | create | Create reports |
| reports | delete | Delete reports |
| users | manage | Manage user identities |
| users | delete | Delete user accounts |
| payroll | read | Read payroll information |

Permissions are more specific than roles.

A role groups permissions, while a permission defines an individual authorization capability.

## 3. Role-Based Access Control

Role-Based Access Control (RBAC) assigns permissions to roles and assigns roles to users through groups or direct assignments.

The authorization process follows this sequence:

1. Identify the requesting user.
2. Confirm that the account is active.
3. Retrieve group memberships.
4. Identify assigned roles.
5. Collect role permissions.
6. Evaluate applicable access policies.
7. Return an authorization decision.
8. Record the decision in the audit log.

For example:

`Alice → FinanceTeam → ReportReader → reports:read`

Alice can read reports because her group inherits the ReportReader role.

She does not automatically receive permission to delete reports or manage user accounts.

### RBAC Advantages

- Centralized permission administration.
- Reusable organizational roles.
- Easier employee onboarding.
- Consistent access assignment.
- Simplified access reviews.
- Reduced individual permission administration.

### RBAC Limitations

- Poorly designed roles can accumulate excessive permissions.
- Large organizations may develop role proliferation.
- Group membership changes can affect many identities.
- RBAC alone may not express all contextual authorization requirements.

## 4. Access Control Policies

A policy defines additional conditions governing access.

The implementations support two policy effects:

| Effect | Meaning |
|---|---|
| ALLOW | Grants access when applicable |
| DENY | Explicitly prohibits access |

Policies can be restricted by department and excluded users.

For example, a finance policy can allow report creation to Finance employees without giving the same permission to Engineering employees.

Another policy can prohibit finance users from reading payroll information.

### 4.1 Policy Evaluation Order

The implementations use the following authorization precedence:

1. Reject unknown identities.
2. Reject disabled or locked accounts.
3. Identify matching policies.
4. Apply explicit DENY policies.
5. Apply applicable ALLOW policies.
6. Check assigned RBAC permissions.
7. Deny access by default.

The important rule is that an explicit denial takes precedence over role permissions and policy allows.

This prevents a broad role assignment from overriding a security restriction.

### 4.2 Default Deny

Default deny means that access is prohibited unless an applicable authorization rule explicitly permits it.

For example, a user without `reports:delete` cannot delete reports even when that operation is technically available in the application.

Default deny reduces accidental exposure caused by incomplete policy definitions.

## 5. Least Privilege

Least privilege is the practice of restricting each identity to the minimum access required for its responsibilities.

Consider the following example:

| User | Assigned responsibility | Appropriate access |
|---|---|---|
| Alice | Finance reporting | Read reports |
| Bob | Engineering | Read reports |
| Carol | Security administration | Manage user identities |
| Diana | Payroll auditing | Read payroll |

Granting every employee administrative access would violate least privilege.

The source implementations demonstrate least-privilege reporting through effective groups, roles, and permissions.

Important controls include:

- Avoid broad administrative roles.
- Remove unused group memberships.
- Review direct role assignments.
- Restrict sensitive resources.
- Disable inactive identities.
- Use temporary access for exceptional requirements.
- Record and investigate denied operations.
- Review privileged permissions periodically.

A permission count can help identify unusually broad access, but permission count alone does not establish whether an identity is overprivileged. Resource sensitivity and business responsibility must also be considered.

## 6. Temporary Access and Approval

Some operations require access for a limited period.

Examples include:

- Temporary analytics access.
- Emergency infrastructure maintenance.
- Short-term project participation.
- Time-limited audit access.

The implementations model an approval workflow.

### Access Request Lifecycle

`REQUESTED → PENDING → APPROVED → EXPIRED`

A request contains:

- Requesting user.
- Designated approver.
- Requested resource.
- Requested action.
- Business justification.
- Request timestamp.
- Expiration timestamp.
- Current status.

The approval process validates:

1. The requester exists.
2. The approver exists.
3. Both identities are active.
4. The requester cannot approve their own request.
5. The designated approver must perform the approval.
6. The requested duration must fall within the configured limit.
7. Only pending requests can be approved.

The JavaScript and Java implementations model approval records and expiration timestamps. The PostgreSQL implementation includes row-level locking with `FOR UPDATE` to prevent concurrent processing of the same pending request.

An approved request is not automatically equivalent to a permanent role assignment. Production systems must enforce its expiration during every authorization decision.

## 7. Identity Lifecycle Management

IAM covers the lifecycle of an identity, not only permission evaluation.

A typical lifecycle includes:

| Stage | Operation |
|---|---|
| Provisioning | Create a new identity |
| Assignment | Add groups and roles |
| Activation | Enable authorized access |
| Modification | Change department or responsibilities |
| Review | Reassess assigned permissions |
| Suspension | Temporarily disable access |
| Deprovisioning | Revoke access and disable the identity |

### Provisioning

A new employee receives an identity record and appropriate group membership.

### Modification

A department transfer can require removing old group memberships and assigning new ones.

### Suspension

A disabled account cannot access protected resources, even if group memberships remain.

### Deprovisioning

Access revocation removes group memberships and disables the identity.

The Python, C++, and Java examples implement access revocation by clearing group membership and disabling the account.

## 8. Audit Logging

An authorization decision must be traceable.

An audit record contains:

| Field | Description |
|---|---|
| Event ID | Unique audit identifier |
| User ID | Requesting identity |
| Resource | Requested resource |
| Action | Requested operation |
| Decision | ALLOW or DENY |
| Reason | Authorization explanation |
| Timestamp | Evaluation time |
| Correlation ID | Related operation identifier |

Audit events help identify:

- Unauthorized access attempts.
- Repeated authorization failures.
- Privileged account activity.
- Unexpected permission assignments.
- Account misuse.
- Policy configuration errors.

A useful distinction exists between authentication logs and authorization logs.

Authentication logs record identity verification events. Authorization logs record decisions about whether an authenticated identity can perform a requested operation.

The implementations concentrate on authorization auditing.

Production audit systems should use restricted write permissions, centralized retention, tamper-resistant storage, and appropriate access controls.

## 9. Python Implementation

**File:** `iam.py`

The Python implementation provides a complete in-memory IAM management system.

### Main Components

| Component | Responsibility |
|---|---|
| `User` | Identity information and account state |
| `Role` | Permission collection |
| `Group` | Membership and role assignment |
| `Permission` | Resource-action pair |
| `Policy` | Conditional authorization rule |
| `AuditEvent` | Access decision record |
| `IdentityAccessManager` | IAM management and authorization |

### Important Mechanisms

**Dataclasses**

Dataclasses represent users, roles, groups, policies, and audit records with explicit fields.

**Sets**

Sets prevent duplicate group memberships and permission assignments.

**Dictionaries**

Dictionaries provide efficient lookup of users, groups, roles, and policies by identifier.

**Exceptions**

Custom exceptions distinguish validation failures, duplicate records, missing identities, and authorization failures.

**Effective Permission Calculation**

The `get_effective_roles()` method collects roles inherited through group membership.

The `get_effective_permissions()` method combines the permissions associated with those roles.

**Policy Evaluation**

The `evaluate()` method checks account status, explicit denials, policy allows, and role permissions.

**Audit Export**

The `export_audit_log()` method exports access decisions as JSON.

**Testing**

The `IAMTests` class checks role inheritance, missing permissions, explicit denials, policy allows, disabled accounts, revocation, and validation failures.

Run using Python 3:

`python iam.py`

The script uses only standard-library modules.

## 10. JavaScript Implementation

**File:** `iam.js`

The JavaScript implementation uses an event-driven architecture.

### Main Components

| Component | Responsibility |
|---|---|
| `User` | Identity state |
| `Role` | Permission collection |
| `Group` | Group membership |
| `Policy` | Conditional access policy |
| `AuditEvent` | Immutable-style event snapshot |
| `IAMEngine` | Access management and policy evaluation |

### Engineering Decisions

**Maps**

Maps store identity objects, roles, groups, policies, and pending requests.

**Sets**

Sets provide efficient membership testing and prevent duplicate assignments.

**Private Class Fields**

Private fields prevent external code from directly modifying internal IAM collections.

**EventEmitter**

The system emits events when identities are created, memberships change, statuses change, access is requested, and access is evaluated.

This separates IAM operations from monitoring and audit consumers.

**Asynchronous Approval**

The temporary access request workflow uses asynchronous methods and explicit approval.

The requester and approver must be different active users.

**Cryptographic Identifiers**

`crypto.randomUUID()` generates unique identifiers for access requests and audit events.

Run using Node.js:

`node iam.js`

The implementation does not require npm dependencies.

## 11. C++17 Implementation

**File:** `iam.cpp`

The C++ implementation focuses on a repository-independent enterprise authorization engine using explicit domain models and STL containers.

### Main Components

- `User`
- `Role`
- `Group`
- `Permission`
- `Policy`
- `AuditRecord`
- `Evaluation`
- `IAMEngine`

### Engineering Decisions

**Ordered Maps**

The implementation uses `std::map` for deterministic identity, role, group, and policy lookup.

Lookup complexity is approximately \(O(\log n)\).

**Sets**

Permission and membership collections use `std::set`, providing logarithmic lookup and preventing duplicate entries.

**Policy Evaluation**

The engine evaluates applicable policies before role permissions.

Explicit DENY takes precedence.

**State Management**

The `changeStatus()` method changes identity status, while `revokeAllAccess()` removes group memberships and disables the account.

**Failure Handling**

Exceptions distinguish missing identities, duplicate identifiers, and invalid inputs.

**Audit Records**

Every completed authorization evaluation is recorded with a timestamp and reason.

Compile using:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic iam.cpp -o iam`

Run using:

`./iam`

The program requires no external libraries.

## 12. Java 17 Implementation

**File:** `IAMApplication.java`

The Java implementation uses an enterprise-oriented service architecture.

### Domain Types

| Type | Purpose |
|---|---|
| `User` | Identity entity |
| `Role` | Role definition |
| `Group` | Group membership |
| `Permission` | Immutable resource-action record |
| `Policy` | Immutable authorization rule |
| `AccessRequest` | Temporary access request |
| `AuditEvent` | Authorization history |
| `LeastPrivilegeReport` | Effective access report |

### Interfaces and Services

The `AccessEvaluator` interface separates authorization evaluation from identity administration.

`DefaultAccessEvaluator` implements the default policy precedence.

`IAMService` coordinates identity registration, role assignments, membership management, permission resolution, authorization, temporary requests, and audit reporting.

### Java 17 Features

- Records for immutable domain data.
- Enums for controlled lifecycle states.
- Streams for effective role and permission aggregation.
- Collections for identity and policy management.
- Custom exceptions for predictable failure handling.
- Interfaces for separating evaluation logic.
- `Instant` for timezone-independent timestamps.
- UUIDs for audit and request identifiers.

### State Transitions

Temporary access requests use explicit statuses:

- `PENDING`
- `APPROVED`
- `REJECTED`
- `EXPIRED`

An approval generates an expiration timestamp.

The example models approval metadata. It does not automatically add temporary permissions to the authorization evaluator. Production enforcement must connect approved requests to the effective permission calculation and verify expiration on each access request.

Compile using:

`javac IAMApplication.java`

Run using:

`java IAMApplication`

No third-party dependencies are required.

## 13. PostgreSQL Implementation

**File:** `iam.sql`

The SQL implementation provides a relational IAM data model with authorization functions, triggers, views, audit records, and temporary access workflows.

### 13.1 Relational Model

The main relationships are:

| Table | Responsibility |
|---|---|
| `users` | Identity records |
| `iam_groups` | Organizational groups |
| `user_groups` | User-group membership |
| `roles` | Role definitions |
| `group_roles` | Group-role assignment |
| `user_roles` | Direct role assignments |
| `permissions` | Resource-action definitions |
| `role_permissions` | Role-permission assignment |
| `access_policies` | Authorization policies |
| `policy_permissions` | Policy-permission association |
| `policy_departments` | Department restrictions |
| `policy_excluded_users` | Policy exclusions |
| `access_requests` | Temporary access workflow |
| `access_audit` | Authorization history |

### 13.2 Database Integrity

Primary keys identify records.

Foreign keys maintain referential integrity between identities, groups, roles, permissions, and policies.

Unique constraints prevent duplicate usernames, emails, role names, and group names.

Check constraints validate non-empty identifiers and prevent self-approval.

Indexes support frequent access patterns, including:

- User-to-group lookup.
- Group-to-role lookup.
- Role-to-permission lookup.
- User audit history.
- Pending access request retrieval.
- Expiring direct role assignments.

### 13.3 Effective Role View

`effective_user_roles` combines group-derived roles and direct role assignments.

The `UNION` operation prevents duplicate effective role records.

Expired direct assignments are excluded.

### 13.4 Effective Permission View

`effective_user_permissions` joins effective roles to role permissions.

This view provides a reusable representation of a user's currently inherited permissions.

### 13.5 Authorization Function

`evaluate_access()` evaluates a resource-action request.

It applies the following precedence:

`Active Identity → Explicit DENY → Policy ALLOW → RBAC Permission → Default DENY`

The function returns a Boolean decision and an explanatory reason.

`authorize_access()` records the result in `access_audit`.

### 13.6 Database Triggers

`trg_user_metadata` updates timestamps and increments the user version after modifications.

`trg_validate_access_request` validates the requester and approver and restricts invalid request transitions.

### 13.7 Approval Processing

`approve_access_request()` uses `SELECT ... FOR UPDATE` to lock the request during approval.

This reduces the risk of two concurrent transactions approving the same pending request.

`expire_access_requests()` updates approved requests whose expiration timestamps have passed.

### 13.8 Reporting

The SQL script includes:

- User and group retrieval.
- Effective role retrieval.
- Effective permission retrieval.
- Privileged role identification.
- Users without assigned roles.
- Group membership aggregation.
- Role distribution.
- Authorization evaluation.
- Access audit reporting.
- Temporary access approval.
- Expiration processing.
- Least-privilege classification.
- Account status reporting.

Execute the SQL script using PostgreSQL 15 or later.

The script uses PostgreSQL's `gen_random_uuid()` function for audit correlation identifiers.

## 14. Differences Between IAM Concepts

The following concepts are related but have different responsibilities.

| Concept | Primary responsibility |
|---|---|
| Identity | Represents the requesting entity |
| Authentication | Verifies the identity |
| User | Represents an individual account |
| Group | Organizes users |
| Role | Collects related permissions |
| Permission | Defines a resource-action capability |
| Policy | Applies authorization rules and conditions |
| Authorization | Determines whether an operation is allowed |
| Audit | Records authorization decisions |
| Least privilege | Restricts access to necessary capabilities |

Authentication and authorization must not be treated as interchangeable.

A successful login proves that an identity has been authenticated. It does not establish that the identity can access every resource.

## 15. Performance Considerations

IAM systems frequently evaluate permissions across many identities and resources.

Important performance considerations include:

**Efficient identity lookup**

Index identity identifiers, usernames, and email addresses.

**Permission caching**

Frequently accessed effective permissions can be cached, but cache invalidation must occur when group memberships, roles, policies, or account status change.

**Role inheritance**

Group-based role assignment reduces duplicate permission records and administrative operations.

**Database indexing**

Indexes should reflect actual query patterns rather than being created indiscriminately.

**Audit volume**

Authorization systems can generate substantial audit traffic. Partitioning audit tables by time can improve retention and query performance.

**Policy evaluation**

Policies should be evaluated using indexed resource-action associations and clearly defined precedence.

## 16. Security Considerations and Limitations

These implementations demonstrate authorization and identity administration. They are educational IAM models rather than complete production identity providers.

A production IAM deployment also requires:

- Secure authentication.
- Strong password hashing where passwords are managed.
- Multi-factor authentication.
- Secure session management.
- Credential rotation.
- Protection against credential theft.
- Rate limiting.
- Privileged account monitoring.
- Centralized security logging.
- Secure administrative interfaces.
- Periodic access certification.
- Controlled emergency access.
- Data retention and privacy controls.

Additional implementation limitations include:

1. The in-memory Python, JavaScript, C++, and Java implementations do not persist identity data between executions.
2. The sample policy engines use resource-action permissions rather than a complete attribute-based authorization language.
3. The temporary approval examples store approval and expiration metadata. They require integration into effective permission evaluation before they can grant temporary access.
4. The SQL authorization functions assume that callers are already authenticated and that the supplied user ID has been securely established.
5. The SQL script demonstrates relational integrity but does not establish a complete database privilege boundary. Production deployments must restrict direct table modification and control function execution.
6. The sample department policies do not implement organizational hierarchy, tenant isolation, resource ownership, or geographic restrictions.
7. Real deployments must account for concurrent membership changes, cache invalidation, policy versioning, and audit retention.

## 17. Integrated IAM Workflow

The five implementations demonstrate the following logical workflow:

`Identity Creation`

`↓`

`User Registration`

`↓`

`Group Membership Assignment`

`↓`

`Role Assignment`

`↓`

`Permission Resolution`

`↓`

`Policy Evaluation`

`↓`

`Authorization Decision`

`↓`

`Audit Recording`

`↓`

`Periodic Access Review or Revocation`

Temporary access follows a separate approval lifecycle:

`Access Request`

`↓`

`Requester and Approver Validation`

`↓`

`Approval or Rejection`

`↓`

`Time-Limited Access`

`↓`

`Expiration and Revocation`

The central design principle is that identity, group membership, role assignment, permission definition, policy evaluation, and audit recording are separate responsibilities. Their controlled interaction provides a manageable and reviewable access-control system.
