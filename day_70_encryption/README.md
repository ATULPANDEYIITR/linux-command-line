# Encryption Engineering and Security

## 1. Technical Scope

Encryption protects information by transforming readable plaintext into ciphertext using cryptographic algorithms and keys.

This project implements four related but distinct areas:

1. Encryption at rest protects stored information.
2. Encryption in transit protects information moving between systems.
3. Symmetric encryption uses the same secret key for encryption and decryption.
4. Public-key cryptography uses mathematically related public and private keys.

Hybrid encryption combines symmetric encryption with public-key cryptography to obtain efficient data encryption and controlled key distribution.

The five implementations approach these requirements through practical cryptographic operations, configuration validation, enterprise key management, and relational security governance.

## 2. Fundamental Cryptographic Concepts

| Term | Meaning |
|---|---|
| Plaintext | Original readable information |
| Ciphertext | Encrypted representation of information |
| Encryption key | Cryptographic value controlling encryption |
| Decryption | Recovery of plaintext from ciphertext |
| Cipher | Algorithm used for encryption and decryption |
| Nonce | Value used once with a particular cryptographic key |
| Initialization vector | Input used by certain encryption modes |
| Authentication tag | Value used to verify ciphertext integrity and authenticity |
| Key exchange | Establishment of shared cryptographic secrets |
| Key rotation | Replacement of an existing key |
| Key revocation | Withdrawal of permission to use a key |
| KMS | Key Management Service |
| HSM | Hardware Security Module |
| TLS | Transport Layer Security |
| AEAD | Authenticated Encryption with Associated Data |
| OAEP | Optimal Asymmetric Encryption Padding |

Encryption provides confidentiality. Authenticated encryption also provides integrity and protection against undetected ciphertext modification.

Encryption alone does not guarantee application authorization, endpoint security, availability, or protection against compromised encryption keys.

## 3. Encryption at Rest

Encryption at rest protects information stored on persistent storage.

Typical protected locations include:

- Relational database tables.
- Database transaction logs.
- File systems.
- Application documents.
- Object storage.
- Backups.
- Storage snapshots.
- Archived records.

### Encryption mechanisms

Encryption at rest can operate at different architectural layers.

| Mechanism | Protection boundary |
|---|---|
| Full-disk encryption | Entire storage device or volume |
| File-system encryption | Selected directories or files |
| Database transparent encryption | Database files and associated storage |
| Column-level encryption | Selected database values |
| Application-level encryption | Data encrypted before persistence |
| Backup encryption | Exported database and backup artifacts |

These mechanisms are not interchangeable.

For example, full-disk encryption protects storage media against certain physical-access attacks. It does not necessarily protect information from an authorized database session or a compromised application account.

Application-level encryption provides a narrower protection boundary because the application can encrypt selected information before sending it to persistent storage.

### AES-256-GCM

The Python, JavaScript, and Java implementations use AES-256-GCM.

AES is a symmetric block cipher. GCM is an authenticated encryption mode.

The operation produces:

- Ciphertext.
- A nonce.
- An authentication tag.

The decryption process verifies the authentication tag before returning plaintext.

If ciphertext, the nonce, authentication tag, or authenticated associated data is modified, authentication fails.

The implementations use a 96-bit nonce and a 128-bit authentication tag.

Nonce uniqueness under a given AES-GCM key is essential. Reusing a nonce with the same key can compromise confidentiality and authentication.

For high-volume systems, nonce allocation and encryption limits must be designed explicitly rather than relying on an unlimited number of random nonce generations.

### Associated authenticated data

Associated authenticated data, or AAD, contains information that must be authenticated but does not need to be encrypted.

Examples include:

- Customer identifiers.
- Database record identifiers.
- Resource identifiers.
- Record types.
- Encryption format versions.

The Python implementation associates encrypted records with a resource identifier.

The JavaScript implementation authenticates a file name.

The Java implementation stores associated data in the encryption envelope and supplies it during decryption.

This prevents ciphertext from being successfully substituted into a different authenticated context when the expected AAD differs.

AAD is not secret. Its purpose is integrity protection.

### Encryption-at-rest workflow

Plaintext → Key selection → Nonce generation → AES-GCM encryption → Ciphertext persistence → Key lookup → Authentication verification → Plaintext recovery

## 4. Encryption in Transit

Encryption in transit protects information transferred between communicating systems.

Examples include:

- Browser-to-server communication.
- Application-to-database communication.
- Microservice communication.
- API requests.
- Remote administration.
- File transfers.
- Inter-region data replication.

TLS is the principal transport security mechanism demonstrated in this project.

### TLS architecture

TLS provides:

- Server authentication.
- Optional client authentication.
- Negotiated cryptographic parameters.
- Secure session key establishment.
- Confidentiality.
- Integrity protection.

TLS 1.3 and TLS 1.2 are accepted by the configuration-validation examples.

TLS 1.0 and TLS 1.1 are rejected.

### Certificate verification

A valid encrypted connection requires more than enabling encryption.

The client must verify:

- Certificate validity.
- Certificate-chain trust.
- Certificate expiration.
- Certificate usage constraints.
- Server hostname.
- Negotiated protocol version.

Disabling certificate verification can expose encrypted communication to man-in-the-middle attacks.

A connection may use encryption while communicating with an attacker if authentication is not correctly performed.

### TLS versus application encryption

| Property | TLS | Application encryption |
|---|---|---|
| Protection scope | Communication channel | Selected application data |
| Main purpose | Secure transmission | Protect information independently of transport |
| Termination | At TLS endpoints | At authorized application decryption endpoints |
| Persistence | Does not automatically protect stored plaintext | Can protect persisted ciphertext |
| Authentication | Certificates and optional client credentials | Depends on application key distribution and authentication |

TLS does not replace encryption at rest.

An application may correctly use TLS while storing sensitive database fields as plaintext.

Conversely, an encrypted database field may remain protected even when transferred through a different trusted processing environment, provided its key remains unavailable to unauthorized parties.

## 5. Symmetric Encryption

Symmetric encryption uses one shared secret key.

The same key is required for encryption and decryption.

AES is a widely deployed symmetric block cipher.

### AES operating modes

| Mode | Main characteristic | Security consideration |
|---|---|---|
| AES-GCM | Authenticated encryption | Nonce uniqueness is critical |
| AES-CCM | Authenticated encryption | Requires correct nonce and parameter management |
| AES-CBC | Block encryption | Requires separate integrity protection and correct padding handling |
| AES-CTR | Counter-based encryption | Requires unique counter values and separate authentication |

The implementations prefer AES-GCM because confidentiality and authentication are provided together.

CBC is included in the governance registry as a legacy configuration. The C++ and PostgreSQL examples reject unauthenticated encryption where policy requires authenticated encryption.

### Symmetric encryption advantages

- Efficient for large data volumes.
- Relatively low computational overhead.
- Suitable for files, database records, and application payloads.
- Supported by common cryptographic libraries.
- Appropriate for bulk encryption.

### Symmetric encryption limitations

The communicating parties must obtain the same secret key securely.

A compromised shared key can expose every protected record encrypted with that key, depending on the key's scope and usage.

Key distribution, storage, rotation, revocation, and access control are therefore essential components of symmetric encryption architecture.

## 6. Public-Key Cryptography

Public-key cryptography uses a key pair.

| Key | Responsibility |
|---|---|
| Public key | Can be distributed to parties that need to encrypt information or verify signatures |
| Private key | Must remain protected and is used for decryption or signing |

RSA is included as the public-key algorithm in the implementations.

### RSA-OAEP

RSA-OAEP is an asymmetric encryption padding scheme.

The Python, JavaScript, and Java examples use RSA-OAEP with SHA-256.

The private key decrypts the encrypted data key.

The RSA implementation uses a 3072-bit key.

RSA is not suitable for directly encrypting arbitrarily large files or application databases. Its encryption input size is limited by the RSA modulus and padding overhead.

It is therefore primarily used in this project to protect small symmetric keys.

### Public-key encryption versus digital signatures

Encryption and digital signatures solve different security problems.

| Operation | Key used | Purpose |
|---|---|---|
| Public-key encryption | Recipient's public key | Confidentiality |
| Public-key decryption | Recipient's private key | Recovery of confidential information |
| Digital signing | Signer's private key | Authenticity and integrity |
| Signature verification | Signer's public key | Verification of signature |

An RSA encryption operation does not automatically establish the identity of the sender.

Digital signatures require a separate signing and verification workflow.

## 7. Hybrid Encryption

Hybrid encryption combines symmetric and asymmetric cryptography.

It uses symmetric encryption for the actual information and public-key encryption for protecting the symmetric data key.

### Workflow

1. Generate a random AES-256 data key.
2. Generate a unique 96-bit nonce.
3. Encrypt the plaintext using AES-256-GCM.
4. Obtain ciphertext and authentication tag.
5. Encrypt the AES data key using the recipient's RSA public key.
6. Store or transmit the encrypted data key alongside the ciphertext.
7. The recipient uses the RSA private key to recover the AES key.
8. AES-GCM verifies the authentication tag and decrypts the information.

Plaintext
→ Random AES data key
→ AES-256-GCM
→ Ciphertext + Authentication tag

AES data key
→ RSA-OAEP using public key
→ Encrypted data key

Recipient
→ RSA private-key decryption
→ Recovered AES key
→ AES-GCM authentication and decryption
→ Plaintext

### Advantages

- Efficient encryption of large data.
- Public-key-based key distribution.
- Reduced need to share a long-term symmetric key.
- Separation between data encryption and key protection.

### Limitations

- Private-key management remains essential.
- RSA introduces computational overhead.
- The recipient must possess the correct private key.
- Key rotation and historical data recovery require explicit lifecycle planning.
- The encrypted data key and ciphertext must be associated with the correct envelope.

The Python, JavaScript, and Java programs implement complete hybrid encryption and decryption workflows.

## 8. Key Management and Lifecycle

Encryption security depends heavily on key management.

A strong algorithm cannot compensate for a compromised or improperly managed key.

### Key lifecycle

Key generation
→ Registration
→ Secure storage
→ Controlled activation
→ Cryptographic usage
→ Rotation
→ Historical decryption
→ Revocation or expiration
→ Secure destruction

### Key states

| State | Meaning | New encryption |
|---|---|---|
| ACTIVE | Key is authorized for current use | Permitted |
| ROTATED | Replaced by another key | Not permitted |
| REVOKED | Administratively withdrawn | Not permitted |
| EXPIRED | Beyond its permitted lifetime | Not permitted |

Historical decryption and new encryption must be treated separately.

After rotation, old ciphertext may still require the previous key.

A rotated key should therefore remain available for authorized historical decryption until the retention and migration requirements have been satisfied.

Revocation is different. A revoked key must not be used, even if historical ciphertext still depends on it.

### Key storage

Production key material should be protected through appropriate mechanisms, such as:

- Hardware Security Modules.
- Cloud Key Management Services.
- Dedicated secrets-management infrastructure.
- Restricted operating-system permissions.
- Access-controlled key-encryption hierarchies.

Encryption keys should not be stored beside ciphertext without an independent protection boundary.

The Python, JavaScript, and Java key managers are educational in-memory implementations. They demonstrate key identifiers, lifecycle transitions, and historical decryption but are not substitutes for production KMS or HSM integration.

## 9. Python Implementation

The Python implementation provides an executable encryption laboratory using the `cryptography` package.

### Main components

| Component | Responsibility |
|---|---|
| `KeyManager` | Key generation, lookup, rotation, and revocation |
| `ManagedKey` | Key metadata and lifecycle state |
| `SymmetricEncryption` | AES-256-GCM encryption and decryption |
| `HybridEncryption` | AES-GCM with RSA-OAEP key protection |
| `TLSConfiguration` | TLS protocol and certificate validation |
| `SecureFileStore` | Encrypted file persistence |
| `derive_subkey` | HKDF-based key derivation |
| `EncryptionTests` | Automated security behavior tests |

### HKDF

HKDF is a key derivation function.

It derives cryptographically separated keys from input key material.

The implementation uses:

- SHA-256.
- A 32-byte output.
- Application-specific context information.

Different context strings produce different derived keys.

This supports key separation between application components, provided the input key material is managed securely.

### File persistence

The file-storage implementation:

- Encrypts file contents before writing.
- Stores a structured encryption envelope.
- Applies restrictive creation permissions.
- Uses associated data to bind the ciphertext to its file name.
- Rejects symbolic links.
- Applies file-size limits.
- Converts authentication failures into controlled exceptions.

The example does not provide complete protection against concurrent file replacement, privileged filesystem attacks, or all platform-specific permission differences.

### Execution

Install the dependency with `pip install cryptography`.

Run the file using Python 3.10 or newer.

The automated tests verify encryption, decryption, authentication failure, key rotation, hybrid encryption, TLS policy, key derivation, and file persistence.

## 10. JavaScript Implementation

The JavaScript implementation uses Node.js standard-library cryptography.

It emphasizes asynchronous file processing, event-driven auditing, and encapsulated key management.

### Main components

| Component | Responsibility |
|---|---|
| `AuditLog` | Event-driven security records |
| `KeyVault` | Private key storage and lifecycle |
| `AESGCMService` | Authenticated symmetric encryption |
| `HybridEncryptionService` | RSA-OAEP and AES-GCM |
| `TransportSecurityPolicy` | TLS configuration validation |
| `EncryptedFileRepository` | Asynchronous encrypted persistence |

### Event-driven auditing

The `AuditLog` class extends `EventEmitter`.

It records events such as:

- `KEY_CREATED`
- `KEY_ROTATED`
- `KEY_REVOKED`
- `DATA_ENCRYPTED`
- `DATA_DECRYPTED`

Audit records contain metadata rather than plaintext or raw key material.

An event-driven design allows other components to subscribe to security events without tightly coupling those components to encryption operations.

### Asynchronous file operations

The file repository uses Node.js promises for file operations.

The implementation writes encrypted content to a temporary file and renames it after successful writing.

This reduces exposure to partially written final files.

It does not by itself guarantee crash durability or protection against all filesystem races.

### Execution

Run with Node.js 20 or newer.

No npm dependencies are required.

The test workflow checks encryption, tamper detection, associated data, key rotation, hybrid encryption, TLS validation, and encrypted file persistence.

## 11. C++17 Implementation

The C++17 implementation provides a cryptographic governance engine rather than implementing cryptographic primitives.

The C++17 standard library does not provide AES, RSA, or TLS implementations.

Using custom cryptographic algorithms would introduce unnecessary security risk.

The program therefore focuses on validating encryption architecture and configuration.

### Main components

| Component | Responsibility |
|---|---|
| `KeyVault` | Key metadata and lifecycle |
| `AlgorithmRegistry` | Approved algorithm profiles |
| `EncryptionGovernanceEngine` | Configuration and policy evaluation |
| `Repository` | Protected-resource registration |
| `SecurityPolicy` | Minimum cryptographic requirements |
| `ProtectedResource` | Resource classification and encryption configuration |
| `EvaluationResult` | Security decision and findings |

### Governance evaluation

The engine checks:

- Algorithm availability.
- Algorithm approval.
- Encryption category.
- Key size.
- Key lifecycle status.
- Key-to-algorithm consistency.
- Key age.
- Authenticated encryption requirements.
- TLS protocol requirements.

The evaluation returns either an approved or rejected configuration.

The engine also demonstrates key rotation, successor relationships, and revocation.

### Engineering considerations

The implementation uses:

- `unordered_map` for average constant-time key and resource lookup.
- `map` for algorithm registry lookup.
- `optional` for successor-key relationships.
- Enums for controlled security states.
- Exceptions for invalid operations.
- Immutable configuration structures where appropriate.

The governance engine is a policy evaluator, not an encryption provider. Actual encryption should be delegated to a maintained cryptographic library and a controlled key-management infrastructure.

## 12. Java 17 Implementation

The Java implementation provides an enterprise-oriented cryptographic service architecture.

It uses Java Cryptography Architecture and Java Cryptography Extension.

### Main components

| Component | Responsibility |
|---|---|
| `KeyManagementService` | AES key lifecycle |
| `ManagedKey` | Key metadata and status |
| `SymmetricEncryptionService` | AES-GCM operations |
| `HybridEncryptionService` | RSA-OAEP and AES-GCM |
| `TransportSecurityService` | TLS policy checks |
| `EncryptionPolicyService` | Enterprise policy evaluation |
| `ProtectedAsset` | Enterprise resource representation |
| `EncryptionEnvelope` | Immutable encrypted-data metadata |

### Java Cryptography Architecture

JCA provides provider-based cryptographic operations.

The implementation uses:

- `KeyGenerator` for AES key generation.
- `Cipher` for encryption and decryption.
- `GCMParameterSpec` for GCM parameters.
- `KeyPairGenerator` for RSA key generation.
- `OAEPParameterSpec` for explicit OAEP configuration.
- `SecureRandom` for cryptographically secure random values.
- `SecretKey` for symmetric key representation.

The RSA implementation explicitly configures SHA-256 for OAEP and MGF1.

Explicit parameter configuration avoids ambiguity between provider defaults.

### Enterprise policy evaluation

The policy service evaluates an asset using:

- Classification.
- Storage location.
- Encryption category.
- Algorithm.
- Key identifier.
- Key lifecycle status.
- TLS requirements.

This separates cryptographic operations from organizational security decisions.

### Execution

Compile using Java 17:

`javac EncryptionEnterprise.java`

Run using:

`java EncryptionEnterprise`

No external dependencies are required.

## 13. PostgreSQL Encryption Architecture

The PostgreSQL implementation models encryption metadata, resource ownership, key lifecycle, transport configuration, and policy evaluation.

It also demonstrates actual symmetric encryption through the `pgcrypto` extension.

### Relational entities

| Table | Purpose |
|---|---|
| `organizations` | Organizational ownership |
| `security_teams` | Security team structure |
| `security_users` | Authorized security personnel |
| `encryption_algorithms` | Cryptographic algorithm registry |
| `encryption_keys` | Key references and lifecycle metadata |
| `protected_resources` | Protected application resources |
| `transport_security` | TLS verification information |
| `encryption_policies` | Security requirements |
| `policy_assignments` | Resource-to-policy relationships |
| `encryption_audit` | Security event history |
| `policy_evaluations` | Policy evaluation results |
| `encrypted_customer_records` | Encrypted sample database values |

### Relational relationships

Organizations
→ Security Users
→ Encryption Key Metadata
→ Protected Resources
→ Encryption Policies
→ Policy Assignments
→ Policy Evaluations
→ Security Audit Events

### Integrity controls

The schema uses:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Enumerated security states.
- Timestamp defaults.
- Indexes for operational queries.
- Triggers for resource validation.
- Procedures for key rotation.

The resource-validation trigger prevents insertion of resources that use unapproved algorithms, revoked keys, mismatched key metadata, or insufficient key sizes.

### Policy evaluation

The `evaluate_encryption_policy` function checks:

- Encryption availability.
- Algorithm approval.
- Authentication requirements.
- Key status.
- Key age.
- Symmetric key size.
- Public-key size.
- TLS configuration.
- Certificate verification.
- Hostname verification.

It returns a decision and structured JSON findings.

The `policy_evaluations` table preserves the evaluation result for reporting and auditing.

### Key rotation procedure

The `rotate_encryption_key` procedure:

1. Locks the existing key row.
2. Verifies the existing key is active.
3. Checks the replacement identifier.
4. Creates replacement key metadata.
5. Marks the original key as rotated.
6. Records the replacement relationship.
7. Inserts an audit event.

Resource migration is performed separately.

This distinction is important because creating a replacement key does not automatically re-encrypt previously stored ciphertext.

### PostgreSQL encryption using pgcrypto

The demonstration uses:

- `pgp_sym_encrypt`.
- `pgp_sym_decrypt`.
- AES-256 symmetric encryption.

The sample password exists only to make the isolated demonstration executable.

Production applications should obtain encryption keys through a separate key-management system.

Database access controls, TLS, backup encryption, and encryption-key separation remain necessary.

## 14. Four Distinct Security Responsibilities

| Security area | Main responsibility | Primary mechanism |
|---|---|---|
| Encryption at rest | Protect persisted information | Disk, database, file, or application encryption |
| Encryption in transit | Protect communication channels | TLS |
| Symmetric encryption | Efficient confidential data encryption | AES |
| Public-key cryptography | Public/private-key operations | RSA |

These areas are related but not interchangeable.

For example, using RSA to protect an AES key does not automatically encrypt a database backup.

Likewise, enabling TLS does not automatically protect database files stored on disk.

An enterprise encryption architecture must define each protection boundary explicitly.

## 15. Security Threats and Failure Conditions

| Threat | Potential consequence | Relevant control |
|---|---|---|
| Key theft | Unauthorized decryption | KMS, HSM, access restrictions |
| Nonce reuse | AES-GCM security compromise | Unique nonce allocation |
| Ciphertext modification | Undetected data alteration | Authentication tags |
| Weak TLS configuration | Transport compromise | TLS version enforcement |
| Certificate validation bypass | Man-in-the-middle attack | Certificate and hostname validation |
| Key reuse across unrelated systems | Increased compromise impact | Key separation |
| Key expiration | Decryption or availability problems | Lifecycle monitoring |
| Improper key rotation | Historical data inaccessible | Controlled migration and retention |
| Plaintext logging | Confidentiality loss | Data minimization and log filtering |
| Weak access controls | Unauthorized cryptographic operations | Role-based authorization |
| Backup exposure | Recovery data compromise | Backup encryption and access control |
| Application compromise | Access to decrypted information | Endpoint hardening and least privilege |

### Error handling

The implementations distinguish invalid input, unavailable keys, authentication failures, unsupported algorithms, and policy violations.

Security errors should not expose plaintext, secret key material, or sensitive cryptographic internals.

Audit records should contain enough information to support investigation without becoming another source of confidential information.

## 16. Performance and Scalability

Symmetric encryption is generally more efficient than public-key encryption for large data.

Hybrid encryption uses asymmetric cryptography only for data-key protection.

| Operation | Performance characteristic |
|---|---|
| AES-GCM encryption | Suitable for bulk data |
| AES-GCM decryption | Requires authentication before plaintext is trusted |
| RSA-OAEP | Computationally more expensive and input-size limited |
| TLS | Adds handshake and record-processing overhead |
| Key lookup | Depends on KMS or local key-management architecture |
| Key rotation | May require substantial data migration |
| Database encryption | Adds processing and storage overhead |

For large systems, encryption architecture should consider:

- Encryption throughput.
- Data size.
- Key-access latency.
- KMS availability.
- Concurrent encryption workloads.
- Nonce allocation.
- Rotation windows.
- Historical ciphertext retention.
- Recovery procedures.

The examples impose data-size limits to prevent uncontrolled memory consumption.

Production systems should use streaming or chunked authenticated encryption for large files, with an independently authenticated format and careful nonce management.

## 17. Limitations and Production Boundaries

The implementations demonstrate cryptographic mechanisms and selected operational controls.

They are not complete production key-management platforms.

Important boundaries include:

- Python and JavaScript key material is held in application memory.
- The Java key manager is an in-memory implementation.
- The C++ program evaluates metadata and does not perform actual encryption.
- The PostgreSQL key registry stores references and metadata rather than production master keys.
- TLS examples validate configuration but do not establish a real network connection.
- Certificate validation examples do not implement a complete PKI.
- Key rotation examples do not automatically migrate every historical encrypted record.
- Demonstration passwords must not be reused in production.
- File permissions and atomic file operations remain platform-dependent.
- Key destruction and memory zeroization require additional controls.

Production deployments should integrate managed key storage, restricted cryptographic permissions, authenticated application identities, secure backups, monitoring, recovery procedures, and independent security testing.

## 18. Comparative Implementation Matrix

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| AES-256-GCM | Yes | Yes | No | Yes | pgcrypto demonstration uses PGP symmetric encryption |
| RSA-OAEP | Yes | Yes | No | Yes | Metadata model |
| Hybrid encryption | Yes | Yes | Policy model | Yes | Algorithm metadata |
| Key rotation | Yes | Yes | Yes | Yes | Procedure |
| Key revocation | Yes | Yes | Yes | Yes | Status model |
| TLS validation | Configuration model | Configuration model | Policy model | Configuration model | Transport records |
| File encryption | Yes | Yes | No | No | Not applicable |
| Database encryption | File-oriented demonstration | File-oriented demonstration | Governance model | Service model | Yes |
| Automated validation | Yes | Yes | Yes | Yes | Constraints and functions |
| Audit capability | Logging | Event-driven | Evaluation findings | Application output | Audit table |

## 19. Practical Application Scenarios

### Financial information systems

- Encrypt account information at rest.
- Protect payment communication using TLS.
- Use AES-GCM for sensitive records.
- Protect data keys through managed public-key or KMS mechanisms.
- Record key rotation and access events.

### Healthcare systems

- Encrypt patient information and clinical documents.
- Separate encryption keys by application or data domain.
- Protect clinical communication through authenticated TLS.
- Maintain controlled access to historical encrypted records.

### Enterprise document management

- Encrypt documents before persistence.
- Use hybrid encryption for recipient-based distribution.
- Authenticate document metadata.
- Rotate keys according to retention and security policies.

### Cloud applications

- Use managed encryption keys.
- Separate data-encryption keys from key-encryption keys.
- Apply TLS to service communication.
- Encrypt backups and storage snapshots.
- Monitor key status and cryptographic policy compliance.

## 20. Core Engineering Distinctions

The central architectural distinction is between protecting information, managing cryptographic keys, and enforcing security policy.

Encryption algorithms transform data.

Keys control the ability to perform cryptographic operations.

Key-management services control key lifecycle and access.

Transport security protects communication channels.

Governance systems determine whether the configured mechanisms satisfy organizational requirements.

A secure system requires these responsibilities to work together without treating one mechanism as a replacement for another.
