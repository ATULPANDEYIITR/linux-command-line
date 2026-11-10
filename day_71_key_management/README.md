# Key Management: Encryption Keys, Rotation, Secrets Management and Hardware Security

## 1. Technical Scope

Key management is the controlled lifecycle of cryptographic keys used to protect information, authenticate systems, establish trust and maintain data confidentiality and integrity.

A cryptographic system is only as secure as its key-management process. Strong algorithms cannot compensate for exposed keys, uncontrolled access, incorrect rotation, insecure storage or incomplete revocation.

This project implements a key-management lifecycle across five technical perspectives:

| Implementation | Primary responsibility |
|---|---|
| Python | Key lifecycle simulation, access control, secret storage and authenticated educational encryption |
| JavaScript | Event-driven key management, AES-256-GCM and asynchronous secret operations |
| C++17 | Key lifecycle engine and repository-style policy evaluation |
| Java 17 | Enterprise key-management services, domain models and merge-policy evaluation |
| PostgreSQL | Relational key inventory, access policies, versioning, rotation workflows and audit reporting |

The central distinction is between cryptographic operations, key lifecycle management, secret management and hardware security. These mechanisms are related but perform different functions.

## 2. Cryptographic Key Fundamentals

A cryptographic key is a value used by an algorithm to perform encryption, decryption, authentication or digital signing.

### 2.1 Symmetric encryption keys

Symmetric cryptography uses the same secret key for encryption and decryption.

For example:

- AES-128 uses a 128-bit key.
- AES-192 uses a 192-bit key.
- AES-256 uses a 256-bit key.

The communicating parties must protect the shared secret.

Symmetric encryption is suitable for large amounts of data because it generally provides high performance.

### 2.2 Asymmetric cryptographic keys

Asymmetric cryptography uses a mathematically related public and private key pair.

| Key | Purpose |
|---|---|
| Public key | Encryption or signature verification, depending on the algorithm |
| Private key | Decryption or digital signature generation, depending on the algorithm |

Common asymmetric algorithms include RSA and elliptic-curve cryptography.

The private key must remain confidential. The public key may be distributed, but its authenticity must be established.

### 2.3 Hashing and message authentication

Hash functions produce fixed-length digests from input data.

SHA-256 is commonly used for integrity-related operations.

A hash function alone does not authenticate the sender because an attacker can calculate a new hash after modifying the data.

HMAC addresses this limitation by combining a cryptographic hash function with a secret key.

Digital signatures provide a different mechanism: they use asymmetric cryptography to verify authenticity and integrity.

### 2.4 Encryption versus key management

| Concept | Responsibility |
|---|---|
| Encryption | Protects data using cryptographic algorithms |
| Decryption | Recovers protected data |
| Key generation | Creates cryptographic key material |
| Key storage | Protects keys against unauthorized access |
| Key rotation | Replaces keys with newer versions |
| Key revocation | Prevents further use of compromised or invalid keys |
| Key destruction | Permanently eliminates key material when permitted |
| Key recovery | Restores access under controlled recovery procedures |

Encryption protects the information. Key management controls the lifecycle and availability of the cryptographic material required to access that information.

## 3. Key Lifecycle Management

A cryptographic key passes through several lifecycle stages.

### 3.1 Generation

Key generation must use a cryptographically secure random-number generator.

Weak random-number generation can produce predictable keys.

Key generation requirements include:

- Appropriate key size.
- Suitable algorithm selection.
- Cryptographically secure randomness.
- Correct purpose assignment.
- Unique key identifiers.
- Secure provider configuration.
- Audit recording.

The Python implementation uses `secrets.token_bytes()`, while JavaScript uses `crypto.randomBytes()`.

The C++ implementation uses `std::random_device` as an illustrative source, but its cryptographic guarantees depend on the implementation. A production C++ application should use an audited operating-system cryptographic provider.

Java uses `SecureRandom` through its cryptographic provider.

### 3.2 Activation

A generated key becomes active after its metadata and provider references are established.

An active key can perform only the operations authorized by its access policy.

A key should not automatically become usable merely because key generation succeeded. Activation should also depend on provider health, access-policy configuration and security validation.

### 3.3 Rotation

Key rotation replaces an existing active key version with a new version.

Example:

| Logical key | Version | State |
|---|---:|---|
| payment-data-key | 1 | ROTATED |
| payment-data-key | 2 | ACTIVE |
| payment-data-key | 3 | Not yet generated |

The logical key identity remains constant while its cryptographic versions change.

A rotation operation generally performs these actions:

1. Validate the operator's permissions.
2. Locate the active key version.
3. Generate a new cryptographic key through the trusted provider.
4. Register the new version.
5. Activate the new version.
6. Mark the previous version as rotated.
7. Migrate encrypted data where necessary.
8. Record the operation in the audit system.

The Python, JavaScript and Java implementations retain previous key versions to support decryption and controlled migration.

The PostgreSQL implementation enforces one active version per logical key through a partial unique index.

### 3.4 Deactivation and revocation

These operations have different meanings.

| State | Meaning |
|---|---|
| ACTIVE | Available for authorized cryptographic operations |
| ROTATED | Replaced by a newer version |
| DISABLED | Temporarily unavailable |
| REVOKED | Permanently invalidated for normal use |
| EXPIRED | Passed its configured validity period |

A disabled key may be re-enabled through an authorized process if policy permits.

A revoked key should not be restored simply by changing its database status. Recovery requires an explicit security procedure and appropriate evidence.

Revocation can affect data availability. An organization must consider whether historical ciphertext can still be recovered under an authorized recovery process.

### 3.5 Destruction and retention

Key destruction is the final stage of the lifecycle.

It should occur only after:

- Required retention periods have elapsed.
- Dependent encrypted information has been migrated or appropriately disposed of.
- Legal and operational retention obligations have been considered.
- Recovery requirements have been evaluated.
- Destruction authorization has been recorded.

A database row marked as revoked is not proof that the underlying key material has been securely destroyed.

Hardware-backed key destruction must be performed through the appropriate provider interface.

## 4. Key Rotation Strategies

Rotation is not simply the creation of a new key. It is a controlled transition between cryptographic versions.

### 4.1 Periodic rotation

Keys are replaced after a predefined interval.

For example:

| Key category | Illustrative rotation interval |
|---|---:|
| Application data key | 90 days |
| Key-encryption key | 180 days |
| High-risk service key | Policy-dependent |
| Signing key | Based on validity and compromise policy |

These are demonstration values, not universal security requirements.

### 4.2 Event-driven rotation

A key may require immediate replacement following:

- Suspected compromise.
- Unauthorized access.
- Personnel departure involving privileged access.
- Security incident.
- Cryptographic algorithm weakness.
- Provider security failure.
- Policy violation.

Event-driven rotation should not wait for the normal rotation schedule.

### 4.3 Lazy re-encryption

In lazy re-encryption, old ciphertext is migrated when the associated information is next accessed.

Advantages:

- Reduced immediate processing.
- Migration can be distributed over time.
- Lower peak infrastructure demand.

Disadvantages:

- Old key versions must remain available.
- Historical data may remain encrypted under previous keys.
- Migration completion requires monitoring.

### 4.4 Bulk re-encryption

Bulk re-encryption migrates all affected encrypted records within a planned workflow.

Advantages:

- More predictable migration completion.
- Easier inventory reconciliation.
- Reduced dependence on historical versions after migration.

Disadvantages:

- Higher processing demand.
- Greater operational complexity.
- Temporary impact on application performance.

### 4.5 Rotation state diagram

    ACTIVE VERSION 1
           |
           v
    GENERATE VERSION 2
           |
           v
    ACTIVATE VERSION 2
           |
           v
    VERSION 1 BECOMES ROTATED
           |
           v
    RE-ENCRYPT DEPENDENT DATA
           |
           v
    VERIFY MIGRATION
           |
           v
    RETAIN OR DESTROY VERSION 1
       ACCORDING TO POLICY

Rotation must not destroy the previous key before dependent data has been migrated or its retention requirements have been satisfied.

## 5. Envelope Encryption

Envelope encryption separates data encryption from key encryption.

It is widely used in enterprise key-management architectures.

### 5.1 Components

| Component | Function |
|---|---|
| Data Encryption Key (DEK) | Encrypts application data |
| Key Encryption Key (KEK) | Protects the DEK |
| Ciphertext | Encrypted application information |
| Nonce | Provides the required per-encryption uniqueness |
| Authentication tag | Detects unauthorized modification |
| KMS/HSM | Manages or protects cryptographic keys |

### 5.2 Encryption workflow

    APPLICATION DATA
           |
           v
    GENERATE DATA KEY
           |
           +--------------------+
           |                    |
           v                    v
    ENCRYPT DATA          PROTECT DATA KEY
    USING DEK             USING KEK
           |                    |
           v                    v
       CIPHERTEXT          WRAPPED DEK
           |                    |
           +---------+----------+
                     |
                     v
              STORE ENVELOPE
                     |
                     v
             ENCRYPTED RECORD

The encrypted record contains the ciphertext and the wrapped DEK, together with the metadata required for decryption.

The DEK is not stored as plaintext in the application database.

### 5.3 Decryption workflow

1. Retrieve the encrypted record.
2. Identify its key identifier and version.
3. Obtain authorization to use the KEK.
4. Unwrap the DEK through the trusted provider.
5. Verify the encrypted data's authentication tag.
6. Decrypt the ciphertext.
7. Return plaintext only to the authorized application.

### 5.4 Why envelope encryption matters

A single KEK can protect many data-encryption keys.

This reduces the need to expose the KEK to application processes and allows the KEK to be rotated independently of application data encryption.

The Python implementation models an educational encrypted envelope. JavaScript and Java implement AES-256-GCM for authenticated encryption.

The C++ implementation focuses on lifecycle and governance rather than introducing an unverified cryptographic primitive.

## 6. Secrets Management

Secrets are sensitive values required by applications and infrastructure.

Examples include:

- Database passwords.
- API credentials.
- Service authentication tokens.
- Private keys.
- Signing credentials.
- Connection credentials.
- Encryption configuration secrets.

### 6.1 Secrets versus encryption keys

A secret and a cryptographic key are not necessarily the same thing.

A database password authenticates an application to a database.

An AES key encrypts or decrypts data.

A private signing key creates digital signatures.

They require different access policies and lifecycle rules.

### 6.2 Secret-management workflow

    APPLICATION
         |
         v
    AUTHENTICATION
         |
         v
    AUTHORIZATION
         |
         v
    SECRET RETRIEVAL
         |
         v
    SECURE SECRET PROVIDER
         |
         v
    APPLICATION USE
         |
         v
    AUDIT EVENT

Applications should retrieve secrets through authenticated interfaces rather than embedding credentials in source files.

### 6.3 Secret rotation

Secret rotation changes the sensitive value itself.

For example, rotating a database password involves coordination between the secret provider and the database authentication configuration.

This is different from rotating the encryption key that protects the stored password.

| Operation | What changes |
|---|---|
| Secret rotation | The credential value |
| Encryption-key rotation | The key used to encrypt or decrypt the secret |
| KEK rotation | The key protecting the DEK |
| DEK rotation | The key encrypting application data |

### 6.4 Access control

The implementations distinguish four principal roles.

| Role | Intended responsibility |
|---|---|
| ADMIN | Privileged lifecycle and revocation operations |
| CRYPTO_OPERATOR | Key generation, rotation and controlled migration |
| APPLICATION | Authorized application encryption and decryption |
| AUDITOR | Inspection of permitted audit and metadata records |

Role-based access control should be combined with least privilege.

An application that needs decryption access should not automatically receive permission to rotate or revoke keys.

Production deployments should also use workload identity, short-lived credentials, service isolation and additional contextual authorization.

## 7. Hardware Security Modules

A Hardware Security Module (HSM) is a specialized security device designed to protect cryptographic operations and key material.

HSMs provide hardware-backed protection for sensitive cryptographic assets.

### 7.1 Core HSM functions

- Secure key generation.
- Protected key storage.
- Cryptographic operations.
- Digital signing.
- Key wrapping and unwrapping.
- Access-policy enforcement.
- Key import and export under controlled conditions.
- Audit support.
- Secure key destruction.

### 7.2 Software KMS versus HSM

| Characteristic | Software KMS | Hardware HSM |
|---|---|---|
| Key storage | Software-managed security boundary | Hardware security boundary |
| Cryptographic operations | Software provider | Hardware-backed provider |
| Isolation | Depends on host and platform | Dedicated security boundary |
| Key export | Provider-policy dependent | Strictly controlled |
| Physical protection | Infrastructure dependent | Hardware security controls |
| Deployment | Software or managed service | Dedicated hardware or managed HSM |

A cloud KMS may use HSM-backed infrastructure internally. Therefore, cloud KMS and HSM are not mutually exclusive categories.

### 7.3 HSM trust boundaries

    APPLICATION
         |
         v
    AUTHENTICATED KMS API
         |
         v
    ACCESS POLICY
         |
         v
    HSM SECURITY BOUNDARY
         |
         +----------------------+
         |                      |
         v                      v
    KEY STORAGE          CRYPTOGRAPHIC
                         OPERATIONS

The application should not receive unrestricted access to the HSM's internal key material.

### 7.4 Hardware security considerations

A production HSM architecture should consider:

- Physical tamper resistance.
- Administrative separation.
- Hardware security certifications.
- Secure initialization.
- Backup and recovery procedures.
- Redundant devices.
- Provider availability.
- Secure firmware updates.
- Operational audit trails.
- Key destruction procedures.

The HSM classes in the source implementations are simulations. They illustrate the interface and trust boundary but do not provide actual hardware-backed protection.

## 8. Source Implementation Architecture

### 8.1 Python: Lifecycle simulation

The Python implementation models the key lifecycle through domain classes.

Important components:

| Component | Responsibility |
|---|---|
| `KeyVersion` | Represents a versioned cryptographic key |
| `KeyManager` | Creates, rotates, disables and revokes keys |
| `SimulatedHSM` | Illustrates hardware-provider integration |
| `AuditLog` | Records lifecycle operations |
| `SecretsVault` | Stores and retrieves encrypted application secrets |
| `EducationalEnvelopeCipher` | Demonstrates authenticated educational encryption |

The implementation uses:

- Dataclasses for structured key metadata.
- Enums for purposes, roles and lifecycle states.
- Dictionaries for version management.
- Exceptions for security and state failures.
- `secrets` for cryptographically secure random generation.
- HMAC-SHA256 for the educational authenticated-encryption demonstration.

The Python cipher is deliberately not a production cryptographic implementation. Its construction is not a standardized AEAD scheme and must not protect real credentials or application data.

The Python vault demonstrates historical key-version lookup and re-encryption following rotation.

### 8.2 JavaScript: Event-driven cryptographic service

The JavaScript implementation uses Node.js built-in cryptographic functionality.

Its main components are:

| Component | Responsibility |
|---|---|
| `AuditService` | Event-driven security logging |
| `SimulatedHSM` | Cryptographic provider abstraction |
| `KeyVersion` | Versioned key metadata and state |
| `KeyManager` | Lifecycle and authorization management |
| `AEADCipher` | AES-256-GCM encryption and decryption |
| `SecretsVault` | Secret storage, retrieval and re-encryption |

AES-GCM provides confidentiality and authentication.

The implementation uses:

- `crypto.randomBytes()` for secure randomness.
- `crypto.createCipheriv()` for encryption.
- `crypto.createDecipheriv()` for decryption.
- `EventEmitter` for audit-event processing.
- `Map` for key and secret registries.
- `Promise.allSettled()` for independent asynchronous operations.

The encryption envelope separates the nonce, ciphertext and authentication tag.

Decryption fails when the authentication tag does not validate.

The asynchronous example also demonstrates how one unauthorized operation can fail without preventing another independent operation from completing.

### 8.3 C++17: Lifecycle and policy engine

The C++ implementation provides two separate engineering components.

The first is a key lifecycle service.

It includes:

- Key generation interfaces.
- Versioned key records.
- Key rotation.
- Key expiration.
- Key revocation.
- Role validation.
- Audit logging.

The second is a repository governance engine that evaluates proposed changes against policy conditions.

This policy engine evaluates:

- Pull Request state.
- Source and target branch synchronization.
- Draft status.
- Merge conflicts.
- Eligible approvals.
- Stale and dismissed reviews.
- Changes-requested decisions.
- Required status checks.
- Resolved conversations.
- Linear-history requirements.
- Administrator bypass restrictions.

The two components illustrate separate security and governance decision models. The repository engine is not a cryptographic key-management mechanism.

The C++ implementation uses `std::map`, `std::vector`, `std::set`, STL algorithms, enumerations and structured domain objects.

Its simulated random source is not a guarantee of cryptographic randomness across platforms. Production cryptographic key generation must use an audited cryptographic provider.

### 8.4 Java 17: Enterprise services

The Java implementation uses explicit domain types and service boundaries.

| Component | Responsibility |
|---|---|
| `Principal` | Represents an authenticated identity and role |
| `KeyVersion` | Models version-specific key state |
| `HardwareSecurityProvider` | Defines the provider interface |
| `SimulatedHSM` | Provides demonstration key generation |
| `KeyManagementService` | Manages lifecycle operations |
| `AEADCipher` | Performs AES-256-GCM operations |
| `SecretsVault` | Manages encrypted application secrets |
| `AuditService` | Captures security events |
| `MergeEligibilityService` | Evaluates repository merge policies |

The Java implementation uses records for immutable data structures and concurrent collections for shared registries.

The `HardwareSecurityProvider` interface provides a separation between business logic and cryptographic infrastructure.

The AES-GCM implementation uses a 96-bit nonce and a 128-bit authentication tag.

The enterprise model also separates review decisions from merge eligibility. A successful review does not independently authorize a merge when repository policy conditions remain unsatisfied.

### 8.5 PostgreSQL: Relational governance

The PostgreSQL implementation models persistent key-management metadata.

It separates the logical key from individual versions.

The main tables are:

| Table | Responsibility |
|---|---|
| `principals` | Users and service identities |
| `key_providers` | KMS and HSM provider inventory |
| `cryptographic_keys` | Logical key definitions |
| `key_versions` | Version-specific lifecycle state |
| `key_access_policies` | Principal permissions |
| `managed_secrets` | Encrypted secret metadata and payload references |
| `rotation_jobs` | Rotation workflow tracking |
| `key_audit_events` | Lifecycle and security event records |
| `key_rotation_approvals` | Rotation approval decisions |

The schema uses foreign keys, unique constraints, check constraints and indexes to enforce data integrity.

The partial unique index on active key versions prevents a logical key from having multiple active versions.

The rotation procedure uses row-level locking to coordinate version changes and avoid concurrent rotations creating conflicting active versions.

The SQL procedures accept provider references rather than raw cryptographic material.

The database is therefore a metadata and workflow layer, not a replacement for a KMS or HSM.

## 9. Enterprise Key Rotation Workflow

A practical enterprise rotation process involves multiple systems.

### 9.1 Operational sequence

| Stage | Operation | Responsible component |
|---|---|---|
| Initiation | Identify an expiring or compromised key | Monitoring or security service |
| Authorization | Validate operator permissions | IAM and policy service |
| Generation | Request a new version | KMS/HSM |
| Registration | Record new version metadata | Key-management database |
| Activation | Enable authorized use | KMS/HSM |
| Migration | Re-encrypt dependent data | Application or migration service |
| Verification | Validate ciphertext and migration results | Application and security service |
| Retirement | Restrict historical version use | KMS/HSM |
| Destruction | Destroy material according to retention policy | Authorized provider operator |
| Audit | Record lifecycle evidence | Audit service |

### 9.2 Failure handling

A rotation workflow must account for partial failures.

| Failure | Required response |
|---|---|
| New key generation fails | Keep the existing active key |
| Provider unavailable | Retry according to a controlled policy |
| Database registration fails | Reconcile provider state before retrying |
| Data migration fails | Preserve the old version and record failed records |
| Authentication fails | Reject corrupted or modified ciphertext |
| New version activation fails | Do not assume rotation completed |
| Old version is revoked prematurely | Initiate an authorized recovery assessment |
| Audit persistence fails | Treat the security operation as incomplete if audit persistence is mandatory |

A distributed rotation workflow cannot rely on a single database transaction to make KMS operations and application migrations atomic.

It requires idempotency, reconciliation and durable workflow state.

## 10. Repository Governance and Merge Eligibility

The C++ and Java implementations also model repository governance to demonstrate the distinction between policy evaluation and operational key security.

These concepts represent separate responsibilities.

| Concept | Responsibility |
|---|---|
| Pull Request | Proposes changes from a source branch into a target branch |
| Code Review | Evaluates the proposed changes |
| Approval | Records a reviewer's decision |
| Branch Protection | Enforces repository-level merge conditions |

A Pull Request does not change the source or target branch merely because it exists.

The source branch contains the proposed commits. The target branch is the destination against which those changes are evaluated.

A merge changes the target branch's history according to the selected merge strategy.

### 10.1 Review decisions

A review may produce:

- APPROVED
- CHANGES_REQUESTED
- COMMENTED
- DISMISSED

Approval indicates that an eligible reviewer accepts the proposed changes within the scope of their review.

It does not automatically establish that all merge conditions have been satisfied.

### 10.2 Approval eligibility

An approval policy may require:

- A minimum number of distinct reviewers.
- Reviewers with appropriate repository permissions.
- Reviews that have not been dismissed.
- Approvals that remain valid after the latest changes.
- No active changes-requested decision.

Stale approvals should not be counted when repository policy requires re-review after new commits.

### 10.3 Automated checks

Automated status checks evaluate conditions such as:

- Unit tests.
- Integration tests.
- Build validation.
- Security scanning.
- Dependency auditing.
- Static analysis.

A pending or failed mandatory check blocks merge eligibility.

### 10.4 Branch protection

Branch protection applies repository-level enforcement.

Typical controls include:

- Required approvals.
- Required status checks.
- Direct-push restrictions.
- Force-push restrictions.
- Branch deletion restrictions.
- Conversation resolution.
- Linear-history requirements.
- Restricted administrator bypass.

The governance engines implement an explicit policy evaluation rather than treating a successful approval as sufficient for merging.

### 10.5 Merge eligibility

The decision can be represented as:

    MERGE ELIGIBLE =
        OPEN PULL REQUEST
        AND NOT DRAFT
        AND VALID SOURCE AND TARGET
        AND BASE BRANCH SYNCHRONIZED
        AND NO MERGE CONFLICTS
        AND REQUIRED APPROVALS
        AND NO ACTIVE CHANGES REQUESTED
        AND REQUIRED STATUS CHECKS PASSED
        AND REVIEW CONVERSATIONS RESOLVED
        AND BRANCH PROTECTION SATISFIED

This is a simplified governance model. Actual repository platforms may implement additional rules, such as merge queues, code-owner requirements, signed commits and environment-specific restrictions.

## 11. Database Integrity and Performance

The PostgreSQL schema uses relational constraints to prevent invalid lifecycle records.

### 11.1 Integrity controls

- Primary keys uniquely identify records.
- Foreign keys prevent references to nonexistent principals, keys and versions.
- Unique constraints prevent duplicate key names and provider references.
- Check constraints restrict permitted key sizes and rotation intervals.
- A partial unique index limits active key versions.
- Triggers record key-version state changes.
- Procedures validate authorization before privileged lifecycle operations.

### 11.2 Indexing decisions

The implementation indexes:

- Rotation status and request time.
- Audit timestamps.
- Principal and action combinations.
- Structured JSONB audit details.
- Active key versions.

These indexes support operational retrieval and lifecycle monitoring.

Index selection should be reviewed against actual query patterns and data volume. Unnecessary indexes increase write costs and storage requirements.

### 11.3 Transaction handling

The rotation procedure uses `SELECT ... FOR UPDATE` to serialize changes to the active version.

This is important because concurrent rotation requests could otherwise attempt to replace the same key simultaneously.

The partial unique index provides an additional integrity safeguard.

### 11.4 Database privilege separation

Application identities should not receive unrestricted database privileges.

A production configuration should separate:

- Schema ownership.
- Metadata retrieval.
- Secret registration.
- Rotation operations.
- Revocation operations.
- Audit inspection.

Privileged functions should use carefully controlled execution privileges and a hardened search path.

## 12. Security Controls and Operational Risks

### 12.1 Key exposure

Keys should not appear in:

- Source repositories.
- Application logs.
- Error messages.
- Plaintext configuration files.
- Unprotected backups.
- Monitoring dashboards.
- Public artifacts.

The PostgreSQL design stores provider references instead of raw key material.

### 12.2 Nonce management

Authenticated encryption algorithms impose nonce requirements.

For AES-GCM, nonce reuse with the same key can seriously compromise security.

The JavaScript and Java examples use randomly generated 96-bit nonces.

Production systems must evaluate nonce collision probability, encryption volume and key usage limits. High-volume systems may require a carefully designed nonce allocation strategy.

### 12.3 Authentication failures

Authenticated decryption must reject ciphertext with an invalid authentication tag.

Applications must not return partially decrypted information after an authentication failure.

The JavaScript and Java implementations reject unsuccessful authenticated decryption.

### 12.4 Separation of duties

A single identity should not automatically control every stage of key lifecycle management.

For sensitive environments, key generation, approval, rotation, revocation and audit inspection should be separated according to risk.

### 12.5 Audit integrity

Audit records should capture:

- Actor identity.
- Operation.
- Resource.
- Timestamp.
- Outcome.
- Relevant non-secret metadata.

Production audit infrastructure should provide restricted modification privileges, external retention and tamper-evident storage.

### 12.6 Backup and disaster recovery

Key recovery is a critical availability requirement.

Encrypted data is not recoverable if the required decryption keys are permanently unavailable.

Recovery plans should account for:

- Provider redundancy.
- Backup encryption.
- Key backup authorization.
- Recovery testing.
- Administrative separation.
- Disaster recovery procedures.
- Provider migration.
- Retention requirements.

A backup of encrypted application data without its required key-recovery mechanism is incomplete.

## 13. Testing and Validation

The source implementations include executable demonstrations and failure checks.

Important test scenarios include:

| Test | Expected result |
|---|---|
| Generate a valid key | New active version |
| Request an invalid key purpose | Validation failure |
| Rotate an active key | New version becomes active |
| Retrieve an unknown key | Not-found failure |
| Access using unauthorized role | Access denied |
| Revoke a key | All versions become revoked |
| Use an expired key | Operation rejected |
| Modify authenticated ciphertext | Decryption rejected |
| Retrieve a secret after re-encryption | Original plaintext recovered |
| Submit a pending status check | Merge eligibility rejected |
| Submit stale approvals under a fresh-review policy | Approval threshold may fail |
| Submit unresolved review discussions | Merge blocked |
| Create two active versions | Database uniqueness violation |

For production deployment, tests should also cover:

- Concurrent rotations.
- Provider timeouts.
- Duplicate requests.
- Partial migrations.
- Key-provider outages.
- Audit-service failures.
- Recovery after application restart.
- Access-policy expiration.
- Large ciphertext migration.
- Key destruction and recovery controls.

## 14. Limitations and Production Boundaries

The implementations are executable learning models, not complete production KMS deployments.

| Area | Implementation limitation |
|---|---|
| Python encryption | Educational HMAC-derived construction, not standardized AEAD |
| Python HSM | Simulated hardware boundary |
| JavaScript HSM | Simulated provider |
| C++ randomness | `std::random_device` does not guarantee a cryptographic provider |
| Java HSM | Simulated provider using software cryptography |
| In-memory storage | Key and secret registries are not persistent |
| Audit storage | Demonstration logging is not tamper-proof |
| Distributed rotation | No distributed transaction coordinator |
| PostgreSQL | Does not execute actual KMS/HSM cryptographic operations |
| Access control | Demonstration roles are simpler than production IAM |

For real application data, use standardized, audited cryptographic implementations and a trusted KMS/HSM integration.

A production design must also establish provider-specific permissions, key backup and recovery, operational monitoring, lifecycle retention and incident-response procedures.

## 15. Execution Requirements

| Source file | Runtime | Dependencies |
|---|---|---|
| Python | Python 3.10+ | Standard library |
| JavaScript | Node.js 18+ | Node.js standard library |
| C++17 | C++17 compiler | Standard library |
| Java | Java 17 | JDK standard library |
| PostgreSQL | PostgreSQL 15+ | Database privileges for schema and procedure creation |

The PostgreSQL script uses `gen_random_uuid()`, available in supported modern PostgreSQL installations.

The sample encrypted payload is demonstration metadata, not a production ciphertext.

The SQL script should be executed using a database role authorized to create schemas, tables, types, indexes, functions, procedures and triggers.

## 16. Technical Concepts Covered

| Technical area | Implemented mechanism |
|---|---|
| Key generation | Secure random generation interfaces |
| Key versioning | Logical key identifiers and version records |
| Key rotation | Controlled active-version replacement |
| Key revocation | Lifecycle state enforcement |
| Authenticated encryption | AES-256-GCM in JavaScript and Java |
| Envelope encryption | DEK and KEK architecture |
| Secrets management | Encrypted secret registry |
| Access management | Role-based authorization |
| Hardware security | HSM provider abstraction |
| Audit | Structured security events |
| Data integrity | Authentication tags and relational constraints |
| Lifecycle automation | Rotation scheduling and procedures |
| Repository governance | Independent merge-policy evaluation |
| Database performance | Targeted indexes and transactional updates |

The key-management architecture maintains a clear separation between cryptographic key material, encrypted application data, identity permissions, lifecycle metadata and repository-level policy enforcement.
