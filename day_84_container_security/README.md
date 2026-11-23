# Container Security: Image Scanning, Minimal Images, Secrets, Runtime Security, and Vulnerability Management

## 1. Technical Scope

Container security protects the software supply chain, container images, deployment infrastructure, runtime processes, application credentials, and the systems that manage container workloads.

A container image is an immutable package containing an application, its runtime dependencies, operating system components, configuration, and metadata. A running container is an instance created from an image with additional runtime configuration, filesystem mounts, network access, resource limits, and security permissions.

Container security requires controls throughout the lifecycle rather than relying on a single vulnerability scanner.

The implementations in this project model five connected security capabilities:

| Security capability | Primary responsibility |
|---|---|
| Image scanning | Identify vulnerabilities and insecure image configurations |
| Minimal images | Reduce unnecessary packages, dependencies, and attack surface |
| Secret management | Detect exposed credentials and prevent their distribution |
| Runtime security | Identify suspicious activities inside running containers |
| Vulnerability management | Prioritize, assign, remediate, and verify security findings |

The implementations use different engineering approaches:

- Python provides a repository and container security simulation.
- JavaScript implements an event-driven scanning and policy pipeline.
- C++17 implements a container governance and deployment authorization engine.
- Java 17 models an enterprise security architecture with explicit domain types and services.
- PostgreSQL maintains the relational security inventory, findings, policies, decisions, and remediation history.

## 2. Container Image Architecture

A container image consists of multiple filesystem layers and image configuration metadata.

A simplified architecture is:

Container Image
    |
    +-- Base Image
    |      |
    |      +-- Operating System
    |      +-- System Libraries
    |
    +-- Application Dependencies
    |
    +-- Application Files
    |
    +-- Configuration Metadata
    |      |
    |      +-- USER
    |      +-- ENTRYPOINT
    |      +-- CMD
    |      +-- ENV
    |      +-- EXPOSE
    |      +-- HEALTHCHECK
    |
    +-- Image Manifest
           |
           +-- Layer References
           +-- Image Configuration
           +-- Content Digests

A running container adds another security boundary:

```
Container Image
      |
      v
Container Runtime
      |
      +-- Process Namespace
      +-- Network Namespace
      +-- Mount Namespace
      +-- User Namespace
      +-- Capabilities
      +-- Seccomp Policy
      +-- Linux Security Modules
      |
      v
Running Container
      |
      +-- Application Processes
      +-- Mounted Filesystems
      +-- Runtime Secrets
      +-- Network Connections
      +-- System Calls
```

An image scanner primarily examines image contents and metadata. Runtime monitoring examines behavior after a container starts.

These activities address different attack surfaces.

## **3. Container Image Scanning**

### **3.1 Purpose**

Image scanning examines container images for known vulnerabilities, insecure configurations, exposed credentials, and compliance violations.

A typical scanning workflow is:


Image Build
    |
    v
Image Registration
    |
    v
Package Discovery
    |
    v
Vulnerability Assessment
    |
    v
Secret Detection
    |
    v
Configuration Assessment
    |
    v
Security Policy Evaluation
    |
    +----------------------+
    |                      |
    v                      v
Approved                Blocked
    |                      |
    v                      v
Deployment             Remediation

The Python, JavaScript, C++17, and Java 17 implementations use separate scanner components for different finding categories.

This separation prevents vulnerability identification from becoming confused with configuration compliance or runtime behavior.

### **3.2 Vulnerability identification**

A vulnerability is a security weakness in a software component.

Common vulnerability information includes:

| Field                | Meaning                                         |
| -------------------- | ----------------------------------------------- |
| CVE                  | Common Vulnerabilities and Exposures identifier |
| Package              | Affected software component                     |
| Installed version    | Version present in the image                    |
| Fixed version        | Version containing an applicable correction     |
| Severity             | Estimated impact category                       |
| CVSS                 | Common Vulnerability Scoring System score       |
| Exploit availability | Whether an exploit is known to exist            |
| Active exploitation  | Whether exploitation has been observed          |

The sample implementations use illustrative vulnerability records.

For example:

| CVE            | Component       | Installed version | Fixed version | Severity |
| -------------- | --------------- | ----------------- | ------------- | -------- |
| CVE-2025-10001 | OpenSSL         | 1.0.2             | 3.0.15        | Critical |
| CVE-2025-10002 | curl            | 7.50.0            | 8.10.0        | High     |
| CVE-2025-10003 | Example library | 2.0.0             | 2.5.1         | Medium   |

These records demonstrate scanner behavior. They are not assertions about the current vulnerability status of those package versions.

A production scanner must obtain vulnerability intelligence from maintained vulnerability databases and match package identifiers, distributions, versions, and affected-version ranges correctly.

### **3.3 Severity classification**

The implementations distinguish five severity categories.

| Severity | Interpretation                | Typical response                      |
| -------- | ----------------------------- | ------------------------------------- |
| CRITICAL | Severe security exposure      | Block deployment                      |
| HIGH     | Significant security weakness | Remediate before deployment           |
| MEDIUM   | Moderate exposure             | Apply remediation according to policy |
| LOW      | Limited exposure              | Schedule correction                   |
| INFO     | Informational observation     | Record and monitor                    |

Severity is not the only prioritization factor.

A vulnerability with an available exploit and active exploitation may require faster remediation than another vulnerability with a similar numerical score.

Other relevant factors include:

- Internet exposure.
- Application criticality.
- Package reachability.
- Available compensating controls.
- Vulnerability age.
- Exploit maturity.
- Business impact.

### **3.4 Software Bill of Materials**

A Software Bill of Materials (SBOM) is a structured inventory of software components included in an application or container image.

An SBOM helps security teams establish:

- Which packages are installed.
- Which versions are deployed.
- Which suppliers provide components.
- Which applications depend on affected packages.
- Which images require rebuilding after a vulnerability disclosure.

The PostgreSQL implementation models this inventory through `image_packages`.

The relational structure is:

container_images
       |
       +---- image_packages
       |
       +---- image_vulnerabilities
                    |
                    v
           vulnerability_catalog
```

Package inventory and vulnerability intelligence are separate because one package can be associated with multiple vulnerabilities.

An SBOM should be generated and retained as a build artifact. It should also be associated with the precise image digest rather than only a mutable tag.

## **4. Minimal Container Images**

### **4.1 Definition**

A minimal container image contains only the components required to execute the intended application.

An unnecessarily large image can contain:

- Compilers.
- Package managers.
- Debugging utilities.
- Unused operating system packages.
- Development dependencies.
- Shell utilities.
- Unnecessary libraries.
- Temporary build files.

Each unnecessary component may introduce additional vulnerabilities or provide tools that an attacker could misuse after compromising the container.

Reducing the image attack surface improves security, distribution efficiency, and operational consistency.

### **4.2 Image construction approaches**

| Image approach             | Characteristics                                                                         |
| -------------------------- | --------------------------------------------------------------------------------------- |
| General-purpose image      | Contains broad operating system functionality                                           |
| Slim image                 | Removes selected unnecessary packages                                                   |
| Minimal distribution image | Provides a reduced operating system environment                                         |
| Distroless image           | Contains application dependencies without a conventional package-management environment |
| Scratch-based image        | Starts from an empty image filesystem                                                   |

The appropriate approach depends on application requirements.

For example, a Python application requires an appropriate Python runtime and its application dependencies. A statically compiled application may be suitable for a scratch-based image if all required runtime functionality is included.

Minimal does not automatically mean secure. A minimal image can still contain vulnerable libraries, unsafe permissions, compromised binaries, or exposed credentials.

### **4.3 Multi-stage builds**

Multi-stage builds separate compilation from application execution.

The first stage contains build tools. The final stage receives only the required application artifacts and runtime dependencies.

Conceptually:

```
BUILD STAGE
    |
    +-- Compiler
    +-- Development Dependencies
    +-- Source Files
    +-- Build Tools
    |
    v
Compiled Application
    |
    v
RUNTIME STAGE
    |
    +-- Minimal Base Image
    +-- Application Binary
    +-- Required Runtime Libraries
    +-- Non-root User
    +-- Entrypoint


This approach reduces the number of unnecessary tools included in the production image.

The final image must still be scanned independently. Security properties of the build stage do not automatically establish the security of the runtime image.

### **4.4 Image optimization controls**

The implementations evaluate:

- Image size.
- Number of filesystem layers.
- Base image selection.
- Runtime user.
- Explicit entrypoint.
- Health-check configuration.
- Image signing.
- Immutable digest availability.

The sample policy uses a 200 MB image-size threshold and a 15-layer observation threshold.

These values are demonstration policy settings rather than universal security standards.

### **4.5 Non-root execution**

Running a container as root increases the consequences of certain application compromises.

A non-root user reduces available privileges within the container.

The implementations reject the following runtime identities under strict policy:

- `root`
- `0`
- `0:0`

An application can use a dedicated numeric user such as `10001`.

A production deployment should also consider:

- User namespace remapping.
- Linux capabilities.
- Read-only root filesystems.
- Filesystem ownership.
- Writable temporary directories.
- Supplemental groups.
- Host filesystem mounts.

A non-root container is not automatically isolated from its host. Runtime configuration remains essential.

## **5. Container Secrets Management**

### **5.1 What constitutes a secret?**

A secret is confidential information used to authenticate, authorize, encrypt, or access a protected resource.

Examples include:

- Database passwords.
- API keys.
- Cloud access credentials.
- Private cryptographic keys.
- Authentication tokens.
- Signing credentials.
- Service account credentials.

Secrets should not be embedded in application source files, image layers, build arguments, or permanent container environment configuration.

### **5.2 Secret exposure mechanisms**

Secrets can enter container images through several mechanisms:

| Exposure mechanism           | Security consequence                                           |
| ---------------------------- | -------------------------------------------------------------- |
| Hardcoded source credentials | Credentials become part of the source history                  |
| Dockerfile `ENV`             | Values may become image configuration metadata                 |
| Dockerfile `ARG`             | Build-time values may leak through build processes or metadata |
| Copied configuration files   | Credentials become part of image layers                        |
| Build logs                   | Sensitive values may be recorded                               |
| Environment variables        | Values may be accessible through process or runtime inspection |
| Build cache                  | Sensitive intermediate artifacts may remain accessible         |
| Mounted files                | Incorrect mount permissions can expose credentials             |

Deleting a secret in a later image layer does not reliably remove the original secret from earlier layers.

Credential rotation is necessary when exposure is suspected.

### **5.3 Secret scanning**

The Python, JavaScript, C++17, and Java 17 implementations inspect environment configuration using patterns for:

- AWS-style access keys.
- Private key headers.
- Password assignments.
- API keys.
- Access tokens.

The sample scanners deliberately avoid printing detected secret values.

The PostgreSQL schema stores secret type, source location, and a masked fingerprint rather than the actual credential.

This separation reduces the risk of creating a second secret repository inside the security reporting database.

### **5.4 False positives and false negatives**

Pattern-based scanning is useful for identifying common credential formats but cannot establish whether every detected value is a valid secret.

False positives occur when ordinary configuration resembles a credential.

False negatives occur when:

- Credentials use an unknown format.
- Secrets are encoded or transformed.
- Credentials are split across multiple files.
- Custom authentication mechanisms are used.
- A secret is injected only after image creation.

Production systems should combine pattern scanning, entropy analysis, provider-specific detection, repository scanning, build-system controls, and secret-manager integration.

### **5.5 Secure secret delivery**

A secure secret-management workflow is:

```
Application Deployment
        |
        v
Workload Identity
        |
        v
Authentication to Secret Manager
        |
        v
Authorization Check
        |
        v
Secret Retrieval
        |
        v
Controlled Runtime Injection
        |
        v
Application
```

Secrets should be:

- Encrypted in transit.
- Protected at rest.
- Access-controlled.
- Audited.
- Rotated periodically.
- Revoked when no longer required.
- Restricted to authorized workloads.

Where supported, workload identity and short-lived credentials reduce reliance on permanently stored passwords.

## **6. Runtime Container Security**

### **6.1 Image security versus runtime security**

Image scanning evaluates an image before deployment.

Runtime security evaluates actual container activity after deployment.

| Image security                | Runtime security                               |
| ----------------------------- | ---------------------------------------------- |
| Examines software packages    | Examines process behavior                      |
| Detects known vulnerabilities | Detects suspicious activity                    |
| Inspects image configuration  | Monitors runtime permissions                   |
| Detects embedded credentials  | Detects unexpected secret access               |
| Evaluates image provenance    | Observes container behavior                    |
| Produces deployment findings  | Produces runtime alerts or enforcement actions |

Both controls are required because a clean image can still be operated insecurely.

### **6.2 Runtime event categories**

The implementations model five event categories.

**Process execution**

Detects unexpected executables, suspicious processes, and potentially dangerous utilities.

**File modification**

Detects attempts to modify protected operating system files.

**Network connections**

Provides a domain for examining unexpected destinations and suspicious network behavior.

**Privilege changes**

Detects operations involving unexpected privilege escalation.

**Unknown activity**

Represents events that cannot be classified under the configured runtime policy.

The sample runtime policies restrict selected utilities such as `nc`, `ncat`, `socat`, `tcpdump`, and `chroot`.

They also identify attempts to modify:

- `/etc/shadow`
- `/etc/passwd`
- `/root/.ssh/authorized_keys`

These rules demonstrate event evaluation. A production implementation requires operating-system-level event collection and a properly configured enforcement mechanism.

### **6.3 Linux runtime isolation mechanisms**

Linux container isolation depends on several kernel mechanisms.

| Mechanism                 | Security function                                          |
| ------------------------- | ---------------------------------------------------------- |
| Namespaces                | Isolate process, network, mount, and other resource views  |
| Cgroups                   | Limit and account for resource consumption                 |
| Linux capabilities        | Divide privileged operations into smaller permission units |
| Seccomp                   | Restrict available system calls                            |
| AppArmor                  | Apply mandatory access-control profiles                    |
| SELinux                   | Enforce mandatory access-control policies                  |
| User namespaces           | Map container users to different host identities           |
| Read-only root filesystem | Restrict modifications to the container root filesystem    |

These controls operate at different levels.

For example, seccomp restricts system calls, whereas cgroups primarily control resource usage.

Neither mechanism replaces vulnerability management.

### **6.4 Runtime policy decisions**

The C++17 and Java implementations return explicit decisions containing:

- Whether the activity is allowed.
- Its severity.
- The reason for the decision.

The JavaScript implementation uses `ALLOW`, `BLOCK`, and `ALERT` actions.

The distinction is important:

- `ALLOW` permits an activity.
- `BLOCK` rejects an activity.
- `ALERT` records suspicious behavior for investigation.

Not every suspicious event should automatically terminate a container. Enforcement decisions must consider the risk, operational impact, and reliability of the detection mechanism.

## **7. Vulnerability Management Lifecycle**

Vulnerability management is a continuing process rather than a one-time image scan.

A typical workflow is:

```
Vulnerability Discovery
        |
        v
Finding Validation
        |
        v
Severity Assessment
        |
        v
Exploitability Assessment
        |
        v
Ticket Assignment
        |
        v
Remediation
        |
        v
Image Rebuild
        |
        v
Rescan
        |
        v
Verification
        |
        v
Closure
```

### **7.1 Remediation states**

The four source implementations model remediation using explicit states.

| State         | Meaning                                                     |
| ------------- | ----------------------------------------------------------- |
| OPEN          | Finding requires action                                     |
| IN_PROGRESS   | Remediation has started                                     |
| MITIGATED     | A temporary or compensating control is active               |
| RESOLVED      | The issue has been corrected and verified                   |
| ACCEPTED_RISK | An authorized decision accepts the documented residual risk |

Valid transitions are controlled by a state machine.

```
                  +----------------+
                  |      OPEN      |
                  +----------------+
                     |          |
                     v          v
               IN_PROGRESS  ACCEPTED_RISK
                  |   \          |
                  |    \         |
                  v     v        v
              MITIGATED RESOLVED OPEN
                  |
                  v
                RESOLVED
```

A ticket should not transition arbitrarily between states.

For example, moving directly from `OPEN` to `RESOLVED` without remediation or verification is not accepted by the sample state machines.

Risk acceptance should include a documented justification, an authorized owner, and an appropriate review date.

### **7.2 Risk-based prioritization**

Vulnerability priority should consider more than severity.

A practical assessment includes:

1. CVSS severity.
2. Known exploit availability.
3. Active exploitation.
4. Application criticality.
5. External network exposure.
6. Package reachability.
7. Available compensating controls.
8. Remediation availability.
9. Business impact.

A critical vulnerability in an internet-facing payment service requires a different response from a low-severity vulnerability in an isolated development workload.

### **7.3 Rebuilding and rescanning**

Updating a package does not automatically update an existing deployed container image.

The corrected application image must be rebuilt, scanned, verified, and deployed.

A remediation process should establish that:

- The affected package has been updated.
- The corrected image has a new digest.
- The vulnerability is no longer detected.
- The image signature is valid.
- Deployment policy is satisfied.
- The old image is no longer deployed where appropriate.

A closed ticket without a verified corrected image provides weak evidence of remediation.

## **8. Security Policy and Deployment Governance**

### **8.1 Policy-driven deployment**

The implementations use explicit security policies to determine whether an image can be deployed.

The demonstration production policy applies the following requirements:

| Control                  | Production policy            |
| ------------------------ | ---------------------------- |
| Critical findings        | Zero permitted               |
| High findings            | Zero permitted               |
| Medium findings          | Maximum three                |
| Non-root execution       | Required                     |
| Verified image signature | Required                     |
| Immutable image digest   | Required                     |
| Health check             | Required                     |
| Secret exposure          | Deployment blocked           |
| Image size               | Maximum 200 MB in SQL policy |

These thresholds are configurable.

A deployment decision is not the same as a scan result.

A scan identifies security observations. The policy engine interprets those observations and determines whether deployment is permitted.

### **8.2 Decision process**

```
Scan Report
    |
    v
Severity Aggregation
    |
    v
Secret Detection Check
    |
    v
Runtime User Check
    |
    v
Image Signature Check
    |
    v
Digest Verification
    |
    v
Health Check Validation
    |
    v
Image Size Evaluation
    |
    v
Deployment Decision
    |
    +----------------------+
    |                      |
    v                      v
APPROVED                 BLOCKED
    |                      |
    v                      v
Deployment             Remediation
```

The C++17 governance engine provides an explicit evaluation function.

The Java implementation separates policy definition from policy evaluation.

The Python implementation combines independent scanners with a centralized policy engine.

The JavaScript implementation publishes scan events and deployment decisions through an event-driven pipeline.

### **8.3 Image signatures and provenance**

A signature helps establish the authenticity and integrity of an image.

Image signing should be combined with:

- Trusted signer identities.
- Signature verification.
- Build provenance.
- Trusted build environments.
- Artifact digest verification.
- Access restrictions on publishing credentials.

Signing an image does not prove that its software is free of vulnerabilities.

A signed vulnerable image remains vulnerable.

The PostgreSQL model separates `signed` from `signature_verified` because signing and successful verification are different states.

### **8.4 Immutable image references**

Tags are human-readable image identifiers.

Tags can be reassigned to different image contents.

An immutable digest identifies particular image content.

A deployment process should verify the image digest and use the verified artifact rather than assuming that a previously approved tag will always identify the same image.

## **9. Python Implementation**

**File:** `container_security.py`

The Python implementation uses standard-library features to model a complete container security workflow.

### **9.1 Architecture**

| Component               | Responsibility                            |
| ----------------------- | ----------------------------------------- |
| `ContainerImage`        | Represents an image and its configuration |
| `Vulnerability`         | Represents a known vulnerability          |
| `Finding`               | Represents a security observation         |
| `VulnerabilityScanner`  | Identifies vulnerability records          |
| `SecretScanner`         | Detects potential credential exposure     |
| `ConfigurationScanner`  | Evaluates image hardening                 |
| `SecurityPolicy`        | Defines deployment requirements           |
| `PolicyEngine`          | Determines deployment eligibility         |
| `RuntimeSecurityEngine` | Evaluates runtime events                  |
| `VulnerabilityTicket`   | Manages remediation transitions           |

### **9.2 Implementation decisions**

Dataclasses represent image metadata, vulnerabilities, runtime events, findings, and remediation records.

Enums constrain security severity, finding categories, deployment decisions, and remediation states.

The scanning platform aggregates findings from independent scanners.

The policy engine evaluates the complete finding collection before issuing a deployment decision.

The image fingerprint is calculated using SHA-256 over a deterministic representation of selected image metadata.

This is a demonstration fingerprint, not a substitute for an OCI image manifest digest or registry-verified artifact identity.

### **9.3 Execution**

Run:

`python container_security.py`

The script:

- Creates an insecure image.
- Creates a hardened image.
- Scans both images.
- Evaluates deployment eligibility.
- Tests runtime restrictions.
- Tests remediation transitions.
- Prints structured JSON security reports.

No external Python packages are required.

## **10. JavaScript Implementation**

**File:** `container_security.js`

The JavaScript implementation emphasizes asynchronous workflows and event-driven security operations.

### **10.1 Architecture**

| Component                   | Responsibility                     |
| --------------------------- | ---------------------------------- |
| `ImageRegistry`             | Maintains image inventory          |
| `VulnerabilityScanner`      | Assesses known vulnerabilities     |
| `SecretScanner`             | Searches environment configuration |
| `ImageConfigurationScanner` | Evaluates hardening requirements   |
| `SecurityPolicy`            | Applies deployment rules           |
| `ContainerSecurityPipeline` | Coordinates scanning and events    |
| `RuntimeMonitor`            | Evaluates runtime activity         |
| `RemediationTicket`         | Maintains remediation history      |

### **10.2 Event-driven behavior**

The scanning pipeline extends Node.js `EventEmitter`.

It emits:

- `scanStarted`
- `scanCompleted`
- `imageApproved`
- `imageBlocked`
- `scanFailed`

This allows separate application components to react to security events.

For example, a deployment controller can subscribe to `imageApproved`, while a ticket-management service can respond to `imageBlocked`.

The pipeline uses asynchronous execution to support integration into larger deployment systems.

The sample image registry uses an in-memory `Map`, while `Set` supports efficient membership checks in runtime policy evaluation.

### **10.3 Execution**

Run:

`node container_security.js`

The program registers two images, executes asynchronous scans, evaluates runtime events, and verifies remediation state transitions.

It requires Node.js 18 or later and no third-party npm dependencies.

## **11. C++17 Implementation**

**File:** `container_security.cpp`

The C++17 implementation focuses on a governance engine that determines image deployment eligibility.

### **11.1 Architecture**

| Component                   | Responsibility                         |
| --------------------------- | -------------------------------------- |
| `ContainerImage`            | Image domain model                     |
| `VulnerabilityScanner`      | Vulnerability assessment               |
| `SecretScanner`             | Credential detection                   |
| `ConfigurationScanner`     | Image hardening evaluation             |
| `SecurityPolicy`            | Configurable policy thresholds         |
| `PolicyEngine`              | Deployment eligibility                 |
| `ContainerGovernanceEngine` | Coordinates scanning                   |
| `RuntimeSecurityEngine`     | Evaluates runtime events               |
| `RemediationTicket`         | Enforces remediation state transitions |

### **11.2 Engineering decisions**

The implementation uses STL containers and algorithms to avoid external dependencies.

`vector` stores packages, findings, and vulnerabilities.

`map` stores environment variables and severity counts.

`set` provides membership checks for blocked processes and protected paths.

`optional` represents the possibility that a fixed package version is unavailable.

The governance engine validates input before executing the scanning pipeline.

Policy evaluation is deterministic for the supplied image metadata and finding collection.

### **11.3 Complexity**

Let:

- \(P\) represent the number of packages.
- \(V\) represent the number of vulnerability records.
- \(E\) represent the number of environment variables.
- \(F\) represent the number of security findings.
- \(R\) represent the number of runtime events.

The main computational costs are:

| Operation                     | Approximate complexity                                                |
| ----------------------------- | --------------------------------------------------------------------- |
| Package validation            | \(O(P \log P)\) using ordered-set insertion                         |
| Vulnerability processing      | \(O(V)\)                                                            |
| Secret environment processing | \(O(E \times L)\), where \(L\) is average inspected string length |
| Finding aggregation           | \(O(F \log S)\), where \(S\) is the number of severity categories |
| Runtime process lookup        | \(O(\log B)\), where \(B\) is the number of blocked executables   |

The implementation is suitable for demonstrating policy evaluation. Large-scale image analysis requires external registry, package intelligence, and runtime monitoring integrations.

### **11.4 Compilation and execution**

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic container_security.cpp -o container_security`

Run:

`./container_security`

The program uses no third-party libraries.

## **12. Java 17 Implementation**

**File:** `ContainerSecurityEnterprise.java`

The Java implementation represents an enterprise-oriented container security platform.

### **12.1 Architecture**

The design separates domain objects, scanning services, policy evaluation, runtime monitoring, remediation, and auditing.

| Component                 | Responsibility                 |
| ------------------------- | ------------------------------ |
| `ContainerImage`          | Validated image aggregate      |
| `Vulnerability`           | Immutable vulnerability record |
| `Finding`                 | Immutable security observation |
| `Scanner`                 | Common scanning contract       |
| `VulnerabilityScanner`    | Vulnerability detection        |
| `SecretScanner`           | Secret detection               |
| `ConfigurationScanner`    | Image configuration assessment |
| `ReviewPolicy`            | Immutable production policy    |
| `PolicyEvaluationService` | Deployment authorization       |
| `ImageScanningService`    | Scanner orchestration          |
| `RuntimeSecurityService`  | Runtime policy evaluation      |
| `RemediationService`      | State-transition enforcement   |
| `AuditService`            | Records security operations    |

### **12.2 Domain modeling**

Java records represent immutable data structures.

The `Scanner` interface defines a common contract for independent scanning services.

The policy object is immutable after construction.

The image aggregate validates its metadata before it can enter the scanning workflow.

Custom exceptions distinguish validation failures from policy violations.

### **12.3 Enterprise considerations**

The architecture supports extension through separate services.

Additional scanner implementations can be introduced without rewriting the policy evaluation logic.

The audit service records:

- Security actions.
- Resource identities.
- Actor information.
- Timestamps.
- Event identifiers.

The remediation service maintains an immutable history of state transitions through recorded history entries.

The implementation uses in-memory collections. A production deployment should persist domain state in a database and apply transactional concurrency controls.

### **12.4 Compilation and execution**

Compile:

`javac ContainerSecurityEnterprise.java`

Run:

`java ContainerSecurityEnterprise`

Java 17 is required.

## **13. PostgreSQL Implementation**

**File:** `container_security.sql`

The PostgreSQL implementation models container security as a relational information system.

### **13.1 Database architecture**

The database separates ownership, image inventory, package inventory, vulnerability intelligence, scanning, findings, deployment policies, runtime events, and remediation.

```
security_teams
      |
      v
repositories
      |
      v
container_images
      |
      +---------------------+
      |                     |
      v                     v
image_packages       image_scans
      |                     |
      v                     v
image_vulnerabilities  security_findings
      |                     |
      v                     +------> secret_detections
vulnerability_catalog       |
                            +------> image_configuration_checks

security_policies
      |
      v
repository_policy_assignments
      |
      v
deployment_decisions

image_vulnerabilities
      |
      v
remediation_tickets
      |
      v
remediation_history

container_images
      |
      v
runtime_events

security_audit_log
```

### **13.2 Core relational entities**

| Table                           | Purpose                              |
| ------------------------------- | ------------------------------------ |
| `security_teams`                | Security and engineering ownership   |
| `repositories`                  | Application repository inventory     |
| `container_images`              | Container image metadata             |
| `image_packages`                | Package inventory and SBOM records   |
| `vulnerability_catalog`         | Vulnerability intelligence           |
| `image_vulnerabilities`         | Vulnerability-to-image relationships |
| `image_scans`                   | Scan execution history               |
| `security_findings`             | Scanner observations                 |
| `secret_detections`             | Credential exposure metadata         |
| `image_configuration_checks`    | Image hardening assessments          |
| `security_policies`             | Deployment security requirements     |
| `repository_policy_assignments` | Repository policy relationships      |
| `deployment_decisions`          | Recorded deployment eligibility      |
| `remediation_tickets`           | Vulnerability remediation ownership  |
| `remediation_history`           | State-transition history             |
| `runtime_events`                | Runtime security observations        |
| `security_audit_log`            | Centralized audit records            |

### **13.3 Referential integrity**

Foreign keys maintain relationships between images, packages, vulnerabilities, scans, findings, policies, and remediation records.

Unique constraints prevent duplicate records within defined business keys.

Check constraints enforce valid severity scores, image dimensions, port ranges, and remediation metadata.

Indexes support common retrieval operations.

The partial index on unresolved findings is particularly useful because operational dashboards generally prioritize findings that remain open.

### **13.4 Triggers**

Three important database mechanisms are implemented.

**Image security metadata validation**

The image trigger prevents a verified signature from being recorded for an unsigned image and prevents immutable deployment from being enabled without a digest.

**Finding counter maintenance**

The finding trigger recalculates severity counts after findings are inserted, updated, or deleted.

**Remediation state validation**

The remediation trigger validates permitted state transitions and inserts corresponding history records.

The database therefore enforces important integrity rules independently of application-level validation.

### **13.5 Deployment eligibility function**

`evaluate_image_eligibility` evaluates an image against a completed scan and an active security policy.

It checks:

- Critical findings.
- High findings.
- Medium findings.
- Secret exposure.
- Root execution.
- Image signature verification.
- Immutable image digest.
- Health-check configuration.

It returns a Boolean eligibility decision, an explanation, and severity counts.

`complete_image_scan` finalizes a running scan and records its severity distribution.

### **13.6 Reporting views**

The database provides five principal views:

| View                            | Purpose                           |
| ------------------------------- | --------------------------------- |
| `image_security_inventory`      | Image and repository inventory    |
| `vulnerability_exposure_report` | Vulnerability exposure            |
| `open_remediation_report`       | Unresolved remediation activities |
| `latest_image_scan_report`      | Most recent scan per image        |
| `runtime_security_dashboard`    | Aggregated runtime activity       |

### **13.7 Execution**

Execute the complete SQL file using PostgreSQL:

`psql -U postgres -d your_database -f container_security.sql`

The script creates the `container_security` schema, database objects, triggers, functions, sample records, and reporting queries.

The SQL script uses a transaction for schema creation and sample data initialization.

## **14. Container Security Controls in CI/CD**

Container security should be integrated into the software delivery pipeline.

A representative workflow is:

```
Source Repository
       |
       v
Dependency Assessment
       |
       v
Application Build
       |
       v
Container Image Build
       |
       v
SBOM Generation
       |
       v
Image Vulnerability Scan
       |
       v
Secret Scan
       |
       v
Image Configuration Assessment
       |
       v
Security Policy Evaluation
       |
       +-----------------------+
       |                       |
       v                       v
    Approved                Rejected
       |                       |
       v                       v
Image Signing             Remediation
       |
       v
Registry Publication
       |
       v
Signature Verification
       |
       v
Deployment Authorization
       |
       v
Runtime Monitoring
       |
       v
Continuous Vulnerability Management
```

The key distinction is between finding vulnerabilities and enforcing deployment policy.

A scanner reports findings. A deployment policy determines the consequences of those findings.

## **15. Operational Security Metrics**

A container security program should monitor both technical findings and remediation performance.

| Metric                       | Purpose                                   |
| ---------------------------- | ----------------------------------------- |
| Critical vulnerability count | Measures severe outstanding exposure      |
| High vulnerability count     | Measures significant outstanding exposure |
| Vulnerable image percentage  | Measures image inventory exposure         |
| Unverified image percentage | Measures provenance-control gaps          |
| Root-container percentage    | Measures privilege configuration          |
| Secret exposure count        | Measures credential leakage               |
| Mean time to remediate       | Measures remediation efficiency           |
| Overdue remediation tickets  | Measures unresolved ownership             |
| Image rescan frequency       | Measures vulnerability reassessment       |
| Runtime blocked-event count  | Measures detected prohibited activity     |
| Policy rejection rate        | Measures deployment governance outcomes   |

Useful calculations include:

**Vulnerable image percentage**

\[
\frac{\text{Images with open vulnerabilities}}{\text{Total scanned images}} \times 100
\]

**Mean time to remediate**

\[
MTTR = \frac{\sum \text{Remediation Duration}}{\text{Resolved Vulnerability Count}}
\]

**Policy rejection rate**

\[
\frac{\text{Blocked Deployment Decisions}}{\text{Total Deployment Decisions}} \times 100
\]

Metrics should be calculated over defined reporting periods and should distinguish new findings from previously unresolved findings.

## **16. Security Limitations and Production Considerations**

The implementations are executable security-domain simulations, not replacements for production container security infrastructure.

### **16.1 Vulnerability intelligence**

The demonstration implementations use supplied vulnerability records.

A production scanner must integrate maintained vulnerability intelligence and account for distribution-specific package metadata, backported patches, version ranges, and vulnerability applicability.

A package version comparison alone is not always sufficient to determine whether a vulnerability is present.

### **16.2 Image scanning coverage**

Production image scanning should examine:

- Operating system packages.
- Application dependencies.
- Language-specific packages.
- Embedded binaries.
- Image configuration.
- Image layers.
- SBOM contents.
- Build provenance.
- Secret exposure.

Scanning only the final package list may miss vulnerable files or components that are not represented in the available package metadata.

### **16.3 Secret detection**

Regular-expression scanning cannot identify every credential.

Production secret detection should combine multiple detection methods and should never expose the actual secret in security logs or reports.

Detected credentials must be rotated and their previous permissions revoked.

### **16.4 Runtime enforcement**

The runtime implementations evaluate illustrative events.

They do not independently collect operating-system events, inspect kernel behavior, or enforce actual system-call restrictions.

Real runtime protection requires a trusted event-collection and enforcement mechanism with appropriate operating-system integration.

### **16.5 Image signing**

The demonstration code models signature state through Boolean values.

Production verification must validate actual signatures, trusted identities, artifact digests, and build provenance.

A Boolean signature flag is not cryptographic verification.

### **16.6 Image digest generation**

The source-language implementations use simplified fingerprints for demonstration.

The Python, JavaScript, and Java implementations do not generate authentic OCI manifest digests.

The database stores a correctly formatted digest field but does not verify that a supplied digest corresponds to the actual registry artifact.

Production systems must obtain digests from the container registry and verify artifact integrity.

### **16.7 Database security**

The PostgreSQL implementation establishes relational integrity but does not configure a complete production access-control environment.

Production deployment should include:

- Least-privilege database roles.
- Schema-level permissions.
- Row-level security where required.
- TLS connections.
- Encrypted backups.
- Audit retention.
- Credential rotation.
- Restricted administrative access.
- Transaction isolation appropriate to concurrent processing.

The audit table is an application-level audit mechanism. It is not inherently tamper-proof against database administrators.

### **16.8 Distributed deployment considerations**

A large container platform may contain thousands of images and continuously changing workloads.

Production architecture should support:

- Distributed scanning workers.
- Scan deduplication.
- Registry event processing.
- Asynchronous remediation workflows.
- Image inventory synchronization.
- Vulnerability feed updates.
- Policy versioning.
- Deployment decision caching.
- Runtime event aggregation.
- Audit retention and archival.

Security decisions should be associated with the exact image digest, scan version, and policy version used for evaluation.

This preserves traceability when vulnerability intelligence or security policies change.

## **17. Technical Distinctions**

The five security capabilities should remain separate while operating as a coordinated system.

| Capability               | Main question                                                      | Output                                  |
| ------------------------ | ------------------------------------------------------------------ | --------------------------------------- |
| Image scanning           | What weaknesses exist in the image?                                | Findings                                |
| Minimal images           | What unnecessary components can be removed?                        | Reduced attack surface                  |
| Secret management        | Are credentials exposed or improperly delivered?                   | Secret findings and credential controls |
| Runtime security         | Is the running container behaving safely?                          | Runtime decisions and alerts            |
| Vulnerability management | Who must correct an identified weakness, and has it been verified? | Remediation records                     |

The central governance relationship is:

**Image scanning identifies security findings.**

**Minimal image construction reduces unnecessary attack surface.**

**Secret management protects credentials.**

**Runtime security evaluates live container behavior.**

**Vulnerability management tracks correction and verification.**

Deployment authorization connects these controls by evaluating whether a particular image, identified by its digest, satisfies the applicable security policy.
