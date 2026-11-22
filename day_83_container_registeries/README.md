# Container Registries: Image Repositories, Tagging, Versioning, Private Registries, and Image Distribution

## 1. Introduction

A container registry is a centralized service for storing, managing, securing, and distributing container images.

Container images package an application's executable components, dependencies, libraries, configuration defaults, and filesystem layers. A registry provides a controlled location from which development pipelines, deployment systems, Kubernetes clusters, and other container runtimes can retrieve these images.

A registry is more than a file-storage service. It manages image references, content integrity, access permissions, security policies, release versions, and distribution workflows.

The implementations in this project model a registry used by an enterprise software development organization.

The example organization publishes payment, inventory, customer, and order-processing services. Development teams publish images, security policies evaluate them, and deployment systems retrieve approved releases.

## 2. Container Registry Architecture

### 2.1 Main components

| Component | Responsibility |
|---|---|
| Registry | Provides image storage and distribution services |
| Repository | Organizes images belonging to an application or service |
| Image manifest | Describes an image and identifies its content |
| Image layer | Represents a filesystem or application layer |
| Tag | Provides a readable reference to an image |
| Digest | Identifies content using a cryptographic hash |
| Registry account | Represents an authenticated user or service |
| Access policy | Determines permitted registry operations |
| Signature | Provides evidence of image authenticity |
| Vulnerability scanner | Identifies known security vulnerabilities |
| Distribution target | Represents a deployment destination |
| Audit log | Records registry operations |

### 2.2 Registry architecture

    Application Source Code
             |
             v
       Build Pipeline
             |
             v
       Container Image
             |
             v
       Image Manifest
             |
             v
       Container Registry
             |
       +-----+------+
       |            |
       v            v
    Repository   Image Tags
       |
       v
    Security Evaluation
       |
       +------------------+
       |                  |
       v                  v
    Approved          Rejected
       |
       v
    Image Distribution
       |
       +---------+----------+
       |         |          |
       v         v          v
    Staging  Production  Regional
    Cluster    Cluster    Cluster

The registry separates image publication from image consumption. Build services publish artifacts, while deployment services retrieve specific approved versions.

## 3. Container Image Repositories

### 3.1 Repository definition

A repository is a logical collection of container images belonging to an application or service.

Examples:

- `production/payment-api`
- `production/inventory-service`
- `development/analytics-api`
- `platform/authentication-service`

Repositories organize images by application, team, environment, or organizational ownership.

A registry can contain multiple repositories, and each repository can contain multiple image manifests and tags.

### 3.2 Repository naming

A repository reference generally follows this structure:

    registry-host/namespace/repository:tag

Example:

    registry.example.internal/production/payment-api:1.0.0

Its components are:

| Component | Value | Meaning |
|---|---|---|
| Registry host | `registry.example.internal` | Registry endpoint |
| Namespace | `production` | Organizational grouping |
| Repository | `payment-api` | Application image collection |
| Tag | `1.0.0` | Human-readable image version |

The registry hostname may be omitted when using a container runtime's default registry.

### 3.3 Repository organization strategies

| Strategy | Example | Purpose |
|---|---|---|
| Application-based | `payment-api` | Separate application ownership |
| Environment-based | `production/payment-api` | Separate deployment environments |
| Team-based | `finance/payment-api` | Organize ownership |
| Platform-based | `platform/nginx` | Shared infrastructure images |

Environment-specific repositories can simplify access management, but they may also create unnecessary duplication. A repository structure should reflect organizational ownership and release management rather than simply duplicating every image for each environment.

## 4. Image Manifests and Content-Addressable Storage

### 4.1 Image manifest

An image manifest contains metadata identifying the image configuration and its filesystem layers.

An OCI image manifest generally references:

- Image configuration.
- Layer descriptors.
- Media types.
- Content digests.
- Content sizes.

A manifest does not necessarily contain all image bytes. It references separately stored content objects.

The OCI image specification defines standard formats for image manifests, image indexes, and configuration objects.

### 4.2 Image layers

Container images commonly consist of multiple filesystem layers.

For example:

    Application Image
          |
          +-- Application Layer
          |
          +-- Runtime Layer
          |
          +-- Dependency Layer
          |
          +-- Base Operating System Layer

Layers can be reused between images when their content is identical.

This reduces storage requirements and network transfer when multiple applications share common dependencies.

### 4.3 Content-addressable storage

Container registries commonly identify content using cryptographic digests.

A SHA-256 digest has the following general structure:

    sha256:<64 hexadecimal characters>

For example:

    sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

The digest identifies the content rather than its human-readable version.

Two references can point to the same digest:

    payment-api:1.0.0
    payment-api:stable

Both can identify the same image content.

When content changes, its digest changes with overwhelming probability.

### 4.4 Digest verification

Digest verification checks whether downloaded content matches the expected content identifier.

The process is:

1. Retrieve the expected digest from a trusted image reference.
2. Download the image content.
3. Calculate its cryptographic digest.
4. Compare the calculated digest with the expected digest.
5. Reject the content if the values differ.

The Python and Java implementations use SHA-256 for image identification and integrity checks.

The C++ implementation uses a deterministic demonstration fingerprint instead of cryptographic SHA-256. It explicitly identifies this limitation and must not be used as a production integrity mechanism.

The JavaScript implementation uses Node.js cryptographic facilities.

A digest establishes content identity. It does not independently establish who published the image or whether its contents are safe.

## 5. Image Tagging

### 5.1 Definition

A tag is a human-readable reference associated with an image manifest.

Example:

    payment-api:1.0.0
    payment-api:1.1.0
    payment-api:latest

A tag makes images easier to identify and retrieve.

Unlike a digest, a normal tag can be reassigned to another manifest.

### 5.2 Mutable tags

A mutable tag can point to different image digests over time.

Example:

| Publication | Tag | Digest |
|---|---|---|
| First publication | `latest` | Digest A |
| Second publication | `latest` | Digest B |
| Third publication | `latest` | Digest C |

The reference remains the same while the referenced content changes.

The `latest` tag is not automatically guaranteed to identify the newest semantic version. Its meaning depends on the publishing workflow.

Mutable tags are useful for:

- Development builds.
- Testing environments.
- Continuously updated integration images.
- Moving release channels.

They are less suitable as the only reference for production deployment.

### 5.3 Immutable tags

An immutable tag cannot be reassigned to different image content.

Example:

    payment-api:1.0.0

Once published, the tag continues to reference its original digest.

Immutable release tags improve:

- Deployment reproducibility.
- Release traceability.
- Incident investigation.
- Rollback reliability.
- Software supply-chain governance.

The Python, C++, Java, JavaScript, and PostgreSQL implementations demonstrate immutable release-tag enforcement.

An important distinction is that tag immutability and digest immutability are separate concepts. A digest identifies content. A registry policy controls whether a tag can be changed or deleted.

## 6. Image Versioning

### 6.1 Semantic versioning

Semantic Versioning uses the following structure:

    MAJOR.MINOR.PATCH

Example:

    2.4.7

| Component | Meaning | Example change |
|---|---|---|
| MAJOR | Incompatible changes | 2.0.0 to 3.0.0 |
| MINOR | Backward-compatible functionality | 2.4.0 to 2.5.0 |
| PATCH | Backward-compatible fixes | 2.4.6 to 2.4.7 |

A typical release progression is:

    1.0.0
      |
      v
    1.0.1
      |
      v
    1.1.0
      |
      v
    2.0.0

### 6.2 Version tags and image digests

Version numbers and digests solve different problems.

| Property | Version tag | Digest |
|---|---|---|
| Human readability | High | Low |
| Content identification | Indirect | Direct |
| Can change its reference | Usually yes | No, for a fixed content digest |
| Suitable for release naming | Yes | Less convenient |
| Suitable for exact content pinning | Only with immutability controls | Yes |

A production deployment should preferably use a digest-pinned image reference.

Example:

    registry.example.internal/production/payment-api@sha256:<digest>

This prevents a deployment from silently resolving to different image content when a mutable tag changes.

### 6.3 Multi-platform images

A container image can target multiple architectures.

Common platforms include:

- `linux/amd64`
- `linux/arm64`
- `linux/arm/v7`

An OCI image index can reference multiple platform-specific manifests.

A container runtime can select the appropriate manifest for its execution environment.

The Java, Python, and C++ examples model architecture metadata and permitted-platform policies. The JavaScript implementation similarly validates platform information.

The implementations model registry metadata and policy behavior rather than implementing complete OCI image-index serialization.

## 7. Private Container Registries

### 7.1 Definition

A private registry restricts image access to authenticated and authorized users or services.

Private registries are commonly used by:

- Enterprise software development teams.
- Financial institutions.
- Government organizations.
- Internal platform engineering teams.
- Organizations operating private Kubernetes clusters.

A private registry can store proprietary applications, internal base images, approved dependencies, and controlled release artifacts.

### 7.2 Authentication

Authentication establishes the identity of a user or service.

Common authentication mechanisms include:

- Username and password.
- Personal access tokens.
- Robot accounts.
- Service credentials.
- OAuth-based authentication.
- Cloud identity integrations.
- Short-lived access tokens.

A registry should not store plaintext credentials.

The PostgreSQL implementation stores a credential-hash field rather than plaintext credentials. The programming examples use demonstration tokens to model authentication.

Production systems should use secure credential hashing or managed identity providers, appropriate token expiration, rotation, and revocation.

### 7.3 Authorization

Authorization determines what an authenticated identity is permitted to do.

The project implements three roles.

| Role | Create repository | Push | Pull | Delete | Manage |
|---|---:|---:|---:|---:|---:|
| Administrator | Yes | Yes | Yes | Yes | Yes |
| Publisher | No | Yes | Yes | No | No |
| Consumer | No | No | Yes | No | No |

A publisher can publish images but cannot change registry-wide configuration.

A consumer can retrieve approved images without being permitted to publish or delete them.

An administrator manages repositories and registry operations.

This is a simplified role-based access-control model. Production registries commonly support repository-level permissions, organizational groups, scoped tokens, and additional administrative controls.

### 7.4 Private registry access workflow

    Service Identity
          |
          v
    Authentication
          |
          v
    Identity Validation
          |
          v
    Role Evaluation
          |
          v
    Repository Permission Check
          |
          +-------------------+
          |                   |
          v                   v
       Allowed             Rejected
          |
          v
    Registry Operation

Authentication and authorization are independent controls. A valid identity does not automatically receive permission to publish or download every repository.

## 8. Image Publication and Push Operations

### 8.1 Push workflow

Publishing an image generally involves:

1. Building the container image.
2. Assigning a repository and tag.
3. Authenticating to the registry.
4. Checking publication permissions.
5. Preparing the image manifest and layers.
6. Uploading required content.
7. Registering or reusing content-addressed objects.
8. Associating the tag with the manifest.
9. Recording publication metadata.

The logical publication flow is:

    Build Image
         |
         v
    Assign Tag
         |
         v
    Authenticate
         |
         v
    Validate Image
         |
         v
    Upload Content
         |
         v
    Store Manifest
         |
         v
    Associate Tag
         |
         v
    Record Audit Event

### 8.2 Content deduplication

If identical image content already exists, a registry can reuse its stored representation rather than storing another identical copy.

The implementations maintain a manifest collection indexed by digest.

Multiple tags can reference the same manifest.

This demonstrates content deduplication at the manifest level. Real OCI registries also deduplicate content-addressed blobs and layers.

### 8.3 Publication failures

Common publication failures include:

- Invalid repository names.
- Invalid tag formats.
- Missing credentials.
- Insufficient permissions.
- Image size exceeding configured limits.
- Unsigned images.
- Vulnerability policy violations.
- Attempts to overwrite immutable tags.
- Unavailable storage.
- Network interruptions.

A failed publication must not create an incorrect tag reference.

The SQL publication procedure uses a database transaction context so that database-side manifest and tag changes can be committed or rolled back together.

The source implementations simulate registry metadata operations. They do not implement a complete OCI Distribution API client or real network upload protocol.

## 9. Image Pull and Retrieval Operations

### 9.1 Pull workflow

Pulling retrieves an image from a registry for execution or further processing.

    Deployment System
          |
          v
    Authenticate
          |
          v
    Check Pull Permission
          |
          v
    Resolve Tag or Digest
          |
          v
    Retrieve Manifest
          |
          v
    Download Required Layers
          |
          v
    Verify Content Digests
          |
          v
    Prepare Image
          |
          v
    Container Runtime

### 9.2 Tag resolution

When a consumer requests:

    payment-api:1.0.0

The registry resolves the tag to its associated digest.

The runtime can then retrieve the exact manifest and referenced content.

A digest-based reference avoids dependence on a mutable tag.

### 9.3 Pull authorization

Pull access should be checked before returning private repository content.

The examples distinguish:

- Authentication failure.
- Authorization failure.
- Missing repository.
- Missing tag.
- Missing manifest.
- Unavailable image.
- Integrity verification failure.

These failures should be recorded and monitored because repeated unauthorized access or unexpected image retrieval may indicate security issues.

## 10. Image Distribution

### 10.1 Definition

Image distribution is the process of delivering container images from a registry to systems that need them.

Typical destinations include:

- Kubernetes clusters.
- Virtual machines.
- Container hosts.
- Regional registries.
- Disaster-recovery environments.
- Edge computing infrastructure.

Distribution can involve direct image pulls, registry replication, mirroring, or managed artifact synchronization.

### 10.2 Distribution workflow

    Central Registry
          |
          v
    Image Selection
          |
          v
    Policy Evaluation
          |
          v
    Target Validation
          |
          v
    Distribution Queue
          |
          +-------------+-------------+
          |             |             |
          v             v             v
       Staging      Production     Regional
       Cluster       Cluster       Registry
          |             |             |
          v             v             v
       Success       Success       Failure

### 10.3 Distribution status

The implementations use three principal states.

| Status | Meaning |
|---|---|
| Pending | Distribution has been initiated |
| Delivered | Destination accepted the image |
| Failed | Distribution did not complete successfully |

The JavaScript implementation uses asynchronous operations and `Promise.allSettled()` to process multiple destinations independently.

This allows one destination to fail without preventing the application from collecting results from other destinations.

It also demonstrates bounded retries.

The Java implementation models destination eligibility and distribution results.

The PostgreSQL implementation stores distribution jobs, target information, retry counts, and failure messages.

### 10.4 Distribution failures

Possible failures include:

- Network interruption.
- Destination registry unavailability.
- Authentication failure.
- Insufficient destination storage.
- Rate limiting.
- Architecture incompatibility.
- Image policy rejection.

A production distribution system should implement exponential backoff, retry limits, idempotency, destination health checks, delivery verification, and monitoring.

The sample implementations model the workflow rather than performing actual network replication.

## 11. OCI and Docker Registry Standards

### 11.1 Open Container Initiative

The Open Container Initiative (OCI) defines specifications for interoperable container images and runtimes.

Important specifications include:

| Specification | Purpose |
|---|---|
| OCI Image Format Specification | Defines image configuration, manifests, indexes, and layers |
| OCI Distribution Specification | Defines registry operations and content distribution |
| OCI Runtime Specification | Defines how container runtimes execute containers |

OCI compatibility allows different container tools and registries to exchange standardized artifacts.

### 11.2 OCI image manifest

An OCI image manifest contains information such as:

- Schema version.
- Media type.
- Configuration descriptor.
- Layer descriptors.
- Content digests.
- Content sizes.

An image index can reference multiple manifests, including platform-specific variants.

### 11.3 Registry API operations

A registry generally exposes operations corresponding to:

| Operation | Purpose |
|---|---|
| Retrieve manifest | Resolve image metadata |
| Upload blob | Store image content |
| Download blob | Retrieve image content |
| Check blob existence | Avoid unnecessary uploads |
| Delete manifest | Remove supported content references |
| List tags | Discover available image references |

The OCI Distribution Specification provides the standardized protocol for these interactions.

The six deliverables model registry concepts and workflows. They are not complete implementations of the OCI Distribution API.

## 12. Image Security and Supply-Chain Governance

### 12.1 Image signing

Image signing provides evidence connecting an image or artifact to a signing identity.

A signature verification process evaluates whether the artifact's signature is valid under the configured trust policy.

It can help establish:

- Publisher authenticity.
- Artifact integrity.
- Release provenance.
- Compliance with publication policies.

A Boolean signature field in an educational model represents a previously verified signature result. It does not implement cryptographic signing or certificate-chain validation.

Production systems should use established signing and verification mechanisms, protected signing identities, key rotation, and verifiable provenance attestations.

### 12.2 Vulnerability scanning

Container images may contain vulnerable operating-system packages, application dependencies, libraries, or utilities.

A vulnerability scanner identifies packages and compares them against vulnerability intelligence.

Typical severity categories are:

- Critical.
- High.
- Medium.
- Low.

A registry policy can reject images exceeding permitted vulnerability thresholds.

The sample registry policy evaluates a maximum vulnerability count.

The PostgreSQL implementation also records severity-specific scan results.

A production policy should distinguish vulnerability severity, exploitability, affected package versions, available fixes, exceptions, and risk acceptance.

### 12.3 Quarantine

Quarantine prevents an image from being distributed while an issue is investigated.

Examples include:

- Failed signature verification.
- Critical vulnerabilities.
- Unexpected image provenance.
- Policy violations.
- Suspected malicious content.

The domain models include image states such as `available`, `quarantined`, and `deleted`.

A quarantined image should not be treated as an approved deployment artifact.

### 12.4 Software supply-chain security

A secure image publication workflow can include:

1. Source-code verification.
2. Controlled build environments.
3. Dependency scanning.
4. Image construction.
5. Image signing.
6. Vulnerability scanning.
7. Registry policy evaluation.
8. Artifact publication.
9. Deployment-time verification.
10. Continuous monitoring.

A registry is one component of software supply-chain security. It does not replace secure source-code management, build-system security, provenance verification, or runtime protection.

## 13. Image Retention and Garbage Collection

### 13.1 Why garbage collection is required

Image registries can accumulate large quantities of image data.

Development pipelines may publish hundreds of temporary images, while production repositories retain multiple releases.

Removing unused content helps control storage consumption.

### 13.2 Tagged and untagged manifests

A tagged manifest is referenced by at least one image tag.

An unreferenced manifest has no remaining tag references.

The sample implementations identify unreferenced manifests and remove them during garbage collection.

### 13.3 Safe deletion conditions

Before deleting content, a production registry should verify:

- No active tags reference the manifest.
- No pending distribution operation requires it.
- The retention period has expired.
- No legal or compliance hold applies.
- No replication operation is using the content.
- The deletion does not break required rollback releases.

A database-level foreign key prevents deletion of a manifest that is still referenced by an image tag.

The SQL garbage-collection query also excludes manifests associated with pending distribution jobs.

Real registries may require more sophisticated blob-reference tracking because multiple manifests can share the same content layers.

## 14. Implementation Architecture

### 14.1 Python implementation

The Python implementation models a registry as a collection of domain objects.

Main components:

| Component | Responsibility |
|---|---|
| `ContainerRegistry` | Coordinates registry operations |
| `User` | Stores user identity and role |
| `Repository` | Stores manifests and tags |
| `ImageManifest` | Represents image content metadata |
| `ImageTag` | Associates a readable reference with a digest |
| `AuditEvent` | Records registry operations |
| `RegistryError` | Provides a common exception hierarchy |

Important mechanisms:

- Dataclasses represent registry entities.
- Enums define roles, operations, and image states.
- Dictionaries provide repository and digest lookup.
- SHA-256 calculates content identifiers.
- Constant-time token comparison reduces timing leakage.
- Exceptions distinguish authorization, validation, and policy failures.
- Assertions verify successful image retrieval.
- Garbage collection removes unreferenced manifests.

The dictionary-based design provides expected constant-time lookups for repositories, manifests, and tags.

The example uses in-memory storage. Restarting the application loses its state.

### 14.2 JavaScript implementation

The JavaScript implementation emphasizes event-driven operations and asynchronous distribution.

Main components:

| Component | Responsibility |
|---|---|
| `ContainerRegistry` | Registry operation coordinator |
| `EventEmitter` | Publishes registry lifecycle events |
| `Permissions` | Defines role-based capabilities |
| `evaluatePolicy()` | Validates image publication rules |
| `push()` | Publishes image metadata |
| `pull()` | Retrieves image metadata |
| `distribute()` | Processes multiple delivery targets |
| `garbageCollect()` | Removes unreferenced manifests |

JavaScript-specific mechanisms include:

- `Map` for repository and user indexing.
- `Set` for permission collections.
- `Buffer` for image content.
- `crypto.createHash()` for SHA-256.
- `EventEmitter` for registry events.
- `async` and `await` for asynchronous operations.
- `Promise.allSettled()` for independent distribution results.
- Bounded retry loops for destination failures.

The event model separates registry operations from monitoring and integration logic.

For example, an image publication event can trigger external audit processing or monitoring without embedding those responsibilities into the publication method.

### 14.3 C++17 implementation

The C++ implementation emphasizes explicit domain modeling and efficient container operations.

Main components:

| Component | Responsibility |
|---|---|
| `ContainerRegistry` | Coordinates registry operations |
| `RegistryPolicy` | Defines publication restrictions |
| `Repository` | Holds tags and manifests |
| `Manifest` | Represents image metadata |
| `Tag` | Represents an image reference |
| `User` | Represents registry identity |
| `AuditEvent` | Records operation results |

The implementation uses:

- `struct` for domain records.
- `enum class` for controlled states.
- `std::map` for ordered repository data.
- `std::unordered_map` for user lookup.
- `std::set` for digest-reference tracking.
- `std::vector` for audit events.
- Exceptions for failure handling.

The demonstration uses a noncryptographic fingerprint to avoid introducing external dependencies. This is intentionally unsuitable for production image verification.

A production C++ implementation should integrate a validated cryptographic library and implement actual OCI-compatible manifest and distribution handling.

### 14.4 Java 17 implementation

The Java implementation emphasizes enterprise domain boundaries and explicit policy services.

Main components:

| Component | Responsibility |
|---|---|
| `ContainerRegistryService` | Coordinates registry lifecycle operations |
| `AccessControlService` | Enforces role permissions |
| `ImagePolicyService` | Evaluates publication restrictions |
| `RegistryPolicy` | Defines registry-wide restrictions |
| `Repository` | Maintains image manifests and tags |
| `ImageManifest` | Represents image metadata |
| `DistributionTarget` | Represents a destination |
| `DistributionResult` | Represents a delivery outcome |
| `AuditEvent` | Captures registry activity |

Java 17 features include:

- Records for immutable domain data.
- Enums for operation and state modeling.
- Collections for repository and user management.
- Streams for querying and filtering.
- Defensive copying for image content.
- Custom exceptions for policy and authorization failures.
- Dedicated service classes for access control and image validation.

The service-oriented structure separates access decisions from image publication and distribution.

### 14.5 PostgreSQL implementation

The PostgreSQL implementation provides a relational model for persistent registry governance.

Main tables:

| Table | Responsibility |
|---|---|
| `registries` | Registry configuration |
| `registry_users` | Registry identities |
| `registry_permissions` | Registry role assignments |
| `repositories` | Repository metadata |
| `image_manifests` | Content-addressed image metadata |
| `image_tags` | Image tag associations |
| `image_signatures` | Signature verification records |
| `vulnerability_scans` | Security scan results |
| `distribution_targets` | Distribution destinations |
| `image_distributions` | Delivery workflow |
| `registry_audit` | Operation history |

Important database mechanisms:

- Primary keys provide row identity.
- Foreign keys preserve relational integrity.
- Unique constraints prevent duplicate repository and tag references.
- Check constraints validate metadata.
- Indexes improve common retrieval operations.
- Triggers protect immutable tags.
- Functions evaluate permissions and image eligibility.
- Procedures manage publication and distribution.
- Views simplify image inventory and reporting.
- Transactions protect multi-statement publication workflows.
- JSONB stores additional audit metadata.

The database stores image metadata and content references rather than implementing binary OCI blob storage.

## 15. Cross-Language Design Comparison

| Engineering concern | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Domain modeling | Dataclasses | Classes and objects | Structs and classes | Records and classes | Relational tables |
| Identity management | Dictionaries | Maps | Unordered maps | Hash maps | Relational keys |
| Authorization | Enums and policies | Permission sets | Role evaluation | Access-control service | SQL functions |
| Digest calculation | SHA-256 | Node crypto | Demonstration fingerprint | SHA-256 | Stored digest metadata |
| Image tagging | Dictionaries | Maps | Ordered maps | Hash maps | Indexed tables |
| Distribution | Synchronous model | Async promises | Synchronous model | Service workflow | Distribution procedures |
| Audit | Event records | EventEmitter | Vectors | Collections | Audit table |
| Persistence | In-memory | In-memory | In-memory | In-memory | Relational database |
| Integrity enforcement | Digest comparison | Digest comparison | Demonstration fingerprint | Digest comparison | Constraints and references |
| Policy enforcement | Registry methods | Policy evaluation | Registry policy | Dedicated service | Functions and procedures |

The languages provide different approaches to registry modeling, but the domain concepts remain consistent.

## 16. PostgreSQL Relational Design

### 16.1 Relationship structure

    REGISTRIES
        |
        +----------------------+
        |                      |
        v                      v
    REGISTRY_PERMISSIONS    REPOSITORIES
        |                      |
        v                      v
    REGISTRY_USERS        IMAGE_MANIFESTS
                               |
                     +---------+----------+
                     |                    |
                     v                    v
                 IMAGE_TAGS         IMAGE_SIGNATURES
                                          |
                                          v
                                  VULNERABILITY_SCANS

    IMAGE_MANIFESTS
          |
          v
    IMAGE_DISTRIBUTIONS
          |
          v
    DISTRIBUTION_TARGETS

    REGISTRIES
          |
          v
    REGISTRY_AUDIT

### 16.2 Referential integrity

A manifest belongs to a repository.

A tag references a manifest within the same repository.

A signature belongs to a manifest.

A vulnerability scan belongs to a manifest.

A distribution record identifies a manifest and a destination.

These relationships prevent invalid references and support consistent reporting.

### 16.3 Indexing decisions

The SQL script creates indexes for:

- Repository lookup by registry.
- Manifest lookup by digest.
- Manifest filtering by status.
- Tag lookup by repository and name.
- Distribution filtering by status.
- Audit retrieval by registry and timestamp.
- Permission lookup by user and registry.

These indexes support common application queries.

Indexes require storage and increase write costs. They should be selected according to actual query frequency and execution plans.

### 16.4 Transaction behavior

The publication procedure performs related database operations:

    Validate Permission
          |
          v
    Validate Registry Policy
          |
          v
    Resolve Repository
          |
          v
    Check Existing Tag
          |
          v
    Insert or Reuse Manifest
          |
          v
    Update Tag
          |
          v
    Record Audit Event

A failure raises an exception, allowing the surrounding transaction to roll back its database changes.

The SQL demonstration uses explicit transactions for setup and garbage collection.

The sample script is intended for an isolated learning database because it creates a dedicated schema and database objects.

## 17. Performance Considerations

### 17.1 Digest-based lookup

A digest is a natural identifier for image content.

Using a map or indexed database column avoids repeatedly scanning every manifest.

Expected lookup performance:

| Structure | Typical lookup complexity |
|---|---|
| Python dictionary | O(1) average |
| JavaScript Map | Sublinear average lookup |
| C++ unordered_map | O(1) average |
| Java HashMap | O(1) average under normal hashing conditions |
| PostgreSQL B-tree index | O(log n) |

Actual performance depends on data distribution, memory, indexing, concurrency, and implementation details.

### 17.2 Layer reuse

Content-addressable storage enables layer reuse.

If multiple images contain identical layers, the registry can store shared content once and reference it from multiple manifests.

This reduces redundant storage and network transfers.

### 17.3 Concurrent image distribution

A registry serving multiple clusters must handle concurrent downloads.

Performance considerations include:

- Network bandwidth.
- Storage throughput.
- Parallel downloads.
- Connection limits.
- Caching.
- Regional replication.
- Rate limiting.
- Registry availability.

The JavaScript example demonstrates concurrent destination processing. It does not implement a production streaming or bandwidth-management system.

### 17.4 Database scalability

A production database can accumulate substantial manifest, tag, scan, and audit information.

Potential improvements include:

- Partitioning audit records by time.
- Archiving historical distribution jobs.
- Indexing frequently queried columns.
- Separating high-volume event ingestion.
- Applying retention policies.
- Avoiding unnecessarily large JSONB records.

## 18. Security and Operational Considerations

A production container registry should address the following areas.

| Area | Required control |
|---|---|
| Authentication | Managed identities and short-lived credentials |
| Authorization | Repository-scoped role permissions |
| Transport security | TLS |
| Image integrity | Cryptographic digest verification |
| Publisher authenticity | Signature verification |
| Vulnerabilities | Automated image scanning |
| Provenance | Build and source attestations |
| Tag governance | Immutable release references |
| Storage | Encryption and access restrictions |
| Audit | Tamper-resistant operation records |
| Distribution | Authenticated delivery and verification |
| Availability | Backups, replication, and recovery |
| Retention | Controlled image and layer cleanup |

Credentials must not be embedded in source code or container images.

Private registry endpoints should be protected from unauthorized access.

Production deployments should use digest-pinned images and verify their signatures and provenance against organizational trust policies.

A successful registry upload alone does not establish that an image is safe for production use.

## 19. Limitations of the Implementations

These programs are executable domain models, not complete commercial container registry products.

| Capability | Implementation status |
|---|---|
| Repository management | Implemented |
| Image metadata | Implemented |
| Tag assignment | Implemented |
| Immutable tag protection | Implemented |
| Digest-based identification | Implemented |
| Role-based access | Implemented |
| Image size validation | Implemented |
| Signature policy representation | Implemented |
| Vulnerability threshold evaluation | Implemented |
| Audit logging | Implemented |
| Distribution workflow simulation | Implemented |
| Retry behavior | Implemented in JavaScript |
| Manifest garbage collection | Implemented |
| Actual OCI blob upload | Not implemented |
| OCI Distribution HTTP API | Not implemented |
| Complete OCI image serialization | Not implemented |
| Cryptographic signature creation | Not implemented |
| External vulnerability scanner integration | Not implemented |
| Kubernetes deployment integration | Not implemented |
| Persistent storage in language examples | Not implemented |
| Production-grade concurrent storage | Not implemented |

The PostgreSQL implementation stores image metadata, digest references, and security records. It does not store or distribute the actual image layers.

The JavaScript and Java implementations model distribution outcomes rather than transferring binary images to real remote registries.

The C++ fingerprint is explicitly noncryptographic.

These boundaries distinguish domain-level registry behavior from the infrastructure required to operate a complete registry service.

## 20. Execution Instructions

### Python

Requirements: Python 3.10 or later.

Save the first implementation as `container_registry.py`.

Execute:

    python container_registry.py

The program creates an in-memory registry, registers identities, publishes images, retrieves them, tests access restrictions, and displays an audit report.

### JavaScript

Requirements: Node.js 18 or later.

Save the second implementation as `container_registry.js`.

Execute:

    node container_registry.js

The program demonstrates event-driven publication, image retrieval, asynchronous distribution, retry handling, and security policy enforcement.

### C++17

Requirements: A C++17-compatible compiler.

Save the third implementation as `container_registry.cpp`.

Compile:

    g++ -std=c++17 -O2 -Wall -Wextra -pedantic container_registry.cpp -o container_registry

Execute:

    ./container_registry

The program demonstrates repository governance, content identification, access control, tag immutability, and image retrieval.

On Windows:

    g++ -std=c++17 -O2 -Wall -Wextra -pedantic container_registry.cpp -o container_registry.exe

    .\container_registry.exe

### Java 17

Requirements: JDK 17 or later.

Save the fourth implementation as `ContainerRegistry.java`.

Compile:

    javac ContainerRegistry.java

Execute:

    java ContainerRegistry

The program demonstrates enterprise registry services, access-control policies, publication validation, and distribution reporting.

### PostgreSQL

Requirements: PostgreSQL 15 or later.

Save the fifth implementation as `container_registry.sql`.

Execute:

    psql -U postgres -d postgres -f container_registry.sql

The script creates the `container_registry` schema, domain types, tables, indexes, triggers, functions, procedures, sample records, and reporting queries.

Use a dedicated learning database rather than an existing production database.

## 21. Practical Enterprise Workflow

Consider a financial institution operating a payment-processing platform.

The development team builds a new payment API image.

The workflow proceeds as follows:

**Stage 1: Build**

The build service creates a container image containing the application, runtime, and required dependencies.

**Stage 2: Publish**

The build service authenticates to the private registry and publishes the image using a release tag.

**Stage 3: Identify**

The registry calculates or records the content digest and associates it with the release tag.

**Stage 4: Verify**

The security workflow checks the image signature and vulnerability scan results.

**Stage 5: Approve**

The registry policy determines whether the image satisfies the configured publication and distribution requirements.

**Stage 6: Distribute**

The approved image is made available to staging and production deployment environments.

**Stage 7: Deploy**

The deployment service retrieves the exact image digest and verifies its integrity.

**Stage 8: Audit**

The registry retains publication, retrieval, and distribution records for operational investigation.

This workflow establishes a traceable relationship between the built artifact, its published identity, its security evaluation, and its deployment destinations.
