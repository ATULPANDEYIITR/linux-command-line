# Authentication and Authorization

## 1. Technical Scope

Authentication and authorization are separate security processes used to control access to applications, services, APIs, and protected information.

**Authentication answers:** Who is making the request?

**Authorization answers:** What is that authenticated identity permitted to do?

The implementations demonstrate an identity-management workflow covering password verification, multifactor authentication, session management, access tokens, OAuth 2.0, and role-based access control.

| Security mechanism | Primary responsibility |
|---|---|
| Password authentication | Verify an identity using a knowledge factor |
| Multi-factor authentication | Require an independent additional authentication factor |
| Session management | Maintain authenticated state |
| Access tokens | Represent delegated or granted access |
| OAuth 2.0 | Delegate authorization to an application |
| Role-based access control | Determine permissions through assigned roles |
| Scope-based authorization | Restrict the operations available through a token |
| Security auditing | Record authentication and authorization events |

## 2. Password Authentication

A password is a knowledge-based authentication factor.

The application must never store plaintext passwords. Instead, it stores a password verifier derived through a password-hashing algorithm.

### Password hashing workflow

1. The user supplies a password.
2. The application validates its length and input format.
3. A cryptographically random salt is generated.
4. A password-hashing algorithm derives a verifier.
5. The salt, verifier, and algorithm configuration are stored.
6. During login, the supplied password is processed using the stored configuration.
7. The resulting verifier is compared with the stored verifier.

The Python implementation uses PBKDF2-HMAC-SHA256.

The JavaScript implementation uses asynchronous Node.js `scrypt`.

The Java implementation uses `PBKDF2WithHmacSHA256`.

The C++ implementation defines a credential-verification interface because secure password hashing is not available in the C++17 standard library.

### Important terminology

| Term | Meaning |
|---|---|
| Salt | Random value added to password derivation |
| Password hash | Derived verifier stored by the application |
| Work factor | Computational cost of password derivation |
| PBKDF2 | Password-based key derivation function |
| scrypt | Memory-hard password derivation function |
| Argon2id | Memory-hard password-hashing algorithm |
| Constant-time comparison | Comparison designed to reduce timing leakage |

A salt must be unique and unpredictable. It does not need to be secret.

Argon2id is generally a preferred choice for new password-storage systems when an appropriate implementation is available. Parameters must be calibrated against the deployment environment.

### Account lockout

Repeated failed authentication attempts can indicate credential guessing or automated attacks.

The implementations model:

- Failed-attempt counters.
- Temporary account lockout.
- Lockout expiration.
- Counter reset following successful authentication.
- Failure-event recording.

Account lockout requires operational care. Attackers can otherwise deliberately lock legitimate users out. Production systems should combine throttling, progressive delays, monitoring, and recovery controls.

## 3. Multi-Factor Authentication

Multi-factor authentication requires evidence from at least two different authentication-factor categories.

The principal categories are:

- Knowledge: something the user knows, such as a password.
- Possession: something the user possesses, such as an authenticator device.
- Inherence: something the user is, such as a biometric characteristic.

Two passwords do not constitute two independent factors.

### Time-Based One-Time Password

The Python, JavaScript, and Java implementations implement TOTP.

TOTP is based on HMAC and a time-dependent counter.

The basic process is:

1. Generate a random shared secret.
2. Provision the secret to an authenticator.
3. Calculate the current time counter.
4. Generate an HMAC value.
5. Apply dynamic truncation.
6. Produce a six-digit one-time password.
7. Verify the supplied value against an accepted time window.

The demonstration uses a 30-second interval and a one-step clock-drift window.

TOTP verification must consider clock synchronization, secret protection, replay prevention, recovery procedures, and rate limiting.

A successful TOTP verification should not allow the same time-step code to be accepted repeatedly. Production implementations should track the last accepted counter atomically.

WebAuthn and FIDO2 provide stronger phishing-resistant authentication capabilities and are appropriate considerations for enterprise identity systems.

## 4. Session Management

A session maintains authenticated state across multiple requests.

A session is different from a password and different from an access token.

The session model contains:

- Session identifier.
- Associated user identifier.
- Creation timestamp.
- Expiration timestamp.
- Revocation status.

### Session lifecycle

    Unauthenticated
          |
          v
    Credential verification
          |
          v
    MFA verification
          |
          v
    Session created
          |
          v
    Authenticated requests
          |
          +------> Session expiration
          |
          +------> Explicit logout
          |
          +------> Administrative revocation

A session must be rejected when it is expired, revoked, or associated with a disabled account.

Production browser applications should use appropriately configured secure cookies with `HttpOnly`, `Secure`, and suitable `SameSite` settings.

Session identifiers must be unpredictable. Session renewal after authentication and privilege changes reduces session-fixation risks.

## 5. Access Tokens

An access token represents authorization to access a protected resource.

A token can contain:

- Subject identifier.
- Granted scopes.
- Issuance time.
- Expiration time.
- Unique token identifier.

The Python, JavaScript, and Java implementations model signed token claims using HMAC-SHA256.

The C++ implementation models token lifecycle and authorization state without pretending that the standard library provides cryptographic signing.

### Token validation

A resource server must validate:

1. Token structure.
2. Cryptographic signature.
3. Accepted signing algorithm.
4. Issuer, where applicable.
5. Intended audience.
6. Expiration time.
7. Issuance time.
8. Subject and required claims.
9. Revocation status or applicable revocation policy.
10. Required scopes.

A token's possession does not automatically grant every permission belonging to its subject.

### JWT and opaque tokens

| Property | JWT | Opaque token |
|---|---|---|
| Structure | Encoded claims | Unstructured identifier |
| Validation | Cryptographic verification | Server-side lookup or introspection |
| Information | Claims can be readable | No embedded claims required |
| Revocation | Requires additional strategy | Central revocation is straightforward |
| Common use | Distributed resource servers | Centralized authorization systems |

JWT encoding is not encryption. Sensitive information must not be placed in readable token claims.

Short expiration periods, signing-key rotation, and controlled token issuance are important security requirements.

## 6. OAuth 2.0

OAuth 2.0 is an authorization framework that enables an application to obtain limited access to protected resources.

It is not, by itself, an authentication protocol.

OpenID Connect adds an identity layer on top of OAuth 2.0.

### Principal components

| Component | Responsibility |
|---|---|
| Resource owner | Authorizes access to protected resources |
| Client | Requests delegated authorization |
| Authorization server | Issues authorization codes and tokens |
| Resource server | Hosts protected resources |
| Redirect URI | Receives the authorization response |
| Authorization code | Short-lived credential exchanged for tokens |
| Scope | Describes requested access |
| State | Helps correlate and protect the authorization response |
| PKCE | Protects authorization-code exchange against interception |

### Authorization-code workflow

    Resource Owner
          |
          v
    OAuth Client
          |
          v
    Authorization Request
          |
          v
    Authorization Server
          |
          v
    User Authentication
          |
          v
    User Consent
          |
          v
    Authorization Code
          |
          v
    Client Token Exchange
          |
          v
    PKCE Verification
          |
          v
    Access Token
          |
          v
    Resource Server

The implementations model authorization-code issuance, client validation, redirect URI matching, expiration, single-use consumption, and PKCE.

### PKCE

Proof Key for Code Exchange protects the authorization-code flow.

The client generates a high-entropy verifier and calculates an S256 challenge:

    code_challenge =
        BASE64URL(SHA256(code_verifier))

The authorization server stores the challenge during authorization.

During code exchange, the client supplies the original verifier. The server calculates its SHA-256 challenge and compares the result with the stored challenge.

A mismatch prevents token issuance.

The production flow must also validate the original `state` value at the client callback, and must not accept arbitrary redirect URIs.

The executable demonstrations model state creation and return but do not implement a complete browser redirect and callback protocol.

For production use, follow current OAuth security practices and use established authorization-server implementations.

## 7. Role-Based Access Control

Role-based access control, or RBAC, associates permissions with roles and assigns roles to users.

Instead of defining every permission individually for every user, the system maintains reusable permission groups.

### Implemented roles

| Role | Permissions |
|---|---|
| Admin | User management, reporting, settings |
| Manager | User reading and updating, reporting |
| Analyst | Report reading and exporting |
| Viewer | Report reading |

### RBAC relationship

    User
      |
      v
    User Role Assignment
      |
      v
    Role
      |
      v
    Role Permissions
      |
      v
    Protected Operation

The authorization engine evaluates the role's permissions before allowing an operation.

The database implementation models this relationship through:

- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`

This normalized structure avoids duplicating permission definitions across user records.

### Deny-by-default principle

An operation must be denied when:

- The user does not exist.
- The account is disabled.
- The role is unknown.
- The permission is not assigned.
- The required token scope is missing.
- The token has expired or been revoked.

## 8. Scope-Based Authorization

A scope describes the access granted through a token.

For example:

- `reports.read`
- `reports.export`
- `users.read`
- `settings.manage`

Scopes restrict the permissions available through a particular token.

The implementations combine role authorization and token-scope evaluation.

A request is permitted only when both conditions are satisfied:

    Effective Permission =
        User Role Permission
        AND
        Token Scope Permission

An analyst may have permission to read reports, but a token issued with only `reports.export` must not automatically provide `reports.read`.

This distinction is important when applications use delegated authorization.

Scopes should be limited to the smallest set necessary for the requested operation.

## 9. C++17 Engineering Perspective

The C++ implementation emphasizes explicit domain modeling and dependency injection.

Its main components include:

| Component | Responsibility |
|---|---|
| `User` | Identity and account state |
| `Session` | Authenticated session |
| `AccessToken` | Token lifecycle |
| `OAuthClient` | Registered OAuth client |
| `AuthorizationCode` | Temporary authorization grant |
| `CredentialVerifier` | Password-verification interface |
| `MFAVerifier` | MFA-verification interface |
| `PKCEVerifier` | PKCE-verification interface |
| `AuthorizationPolicy` | Permission evaluation |
| `IdentityService` | Authentication workflow |

The demonstration adapters intentionally avoid presenting ordinary string comparison as secure password hashing or cryptographic token signing.

Real C++ integrations must supply audited cryptographic implementations.

The use of `std::map` and `std::set` provides ordered lookup and duplicate prevention, with logarithmic lookup complexity.

## 10. Java 17 Engineering Perspective

The Java implementation uses enterprise-oriented domain objects and service boundaries.

Its design includes:

- Immutable records for token claims and audit events.
- Enums for roles, account states, and token states.
- Dedicated password and MFA services.
- A separate OAuth authorization server.
- An authorization policy object.
- Custom exception types.
- Explicit session and token state transitions.

The `PasswordService` uses the standard Java cryptography APIs.

The OAuth implementation consumes authorization codes before issuing tokens, preventing repeated exchanges within the in-memory demonstration.

The separation between authentication services and authorization policy makes it possible to test each security responsibility independently.

## 11. PostgreSQL Data Model

The SQL implementation provides a relational identity-management model.

### Entity relationships

    USERS
      |
      +---- PASSWORD_CREDENTIALS
      |
      +---- MFA_FACTORS
      |          |
      |          +---- MFA_REPLAY_PROTECTION
      |
      +---- USER_ROLES
      |          |
      |          +---- ROLES
      |                  |
      |                  +---- ROLE_PERMISSIONS
      |                              |
      |                              +---- PERMISSIONS
      |
      +---- SESSIONS
      |
      +---- ACCESS_TOKENS
      |          |
      |          +---- ACCESS_TOKEN_SCOPES
      |
      +---- OAUTH_AUTHORIZATION_CODES
      |
      +---- AUTHENTICATION_AUDIT

    OAUTH_CLIENTS
      |
      +---- OAUTH_REDIRECT_URIS
      |
      +---- OAUTH_CLIENT_SCOPES
      |
      +---- OAUTH_AUTHORIZATION_CODES

### Database integrity

The schema uses:

- Primary keys to identify records.
- Foreign keys to preserve relationships.
- Unique constraints to prevent duplicate identities.
- Check constraints to validate account and token states.
- Partial indexes for active sessions and tokens.
- GIN indexes for JSONB audit details.
- Views for active permissions and sessions.
- Functions for authorization evaluation.
- Procedures for failed-login processing.
- Transactions for multi-operation workflows.

### Important database design decisions

Password verification is performed outside the database. The database stores the resulting password verifier and its configuration.

TOTP secrets are stored encrypted rather than in plaintext.

Opaque bearer tokens and session identifiers are represented by cryptographic hashes in persistent storage.

The OAuth authorization-code function enforces single-use consumption, while PKCE verification is performed by the trusted authorization server before consumption.

Database constraints do not replace application-level security controls.

The database role used by the application should have only the privileges necessary to perform its operations.

## 12. Security Failure Scenarios

| Failure scenario | Expected behavior |
|---|---|
| Incorrect password | Reject authentication |
| Repeated password failures | Apply throttling or account lockout |
| Disabled account | Reject login and protected requests |
| Missing MFA code | Reject MFA-protected login |
| Incorrect TOTP | Reject authentication |
| Replayed TOTP | Reject previously accepted time-step |
| Expired session | Require authentication again |
| Revoked session | Reject subsequent requests |
| Invalid token signature | Reject the token |
| Expired token | Reject the token |
| Revoked token | Reject access |
| Unknown permission | Deny by default |
| Missing token scope | Deny the operation |
| Invalid OAuth redirect URI | Reject authorization |
| Expired authorization code | Reject token exchange |
| Reused authorization code | Reject replay |
| Incorrect PKCE verifier | Reject token exchange |

## 13. Performance and Operational Considerations

Password hashing is intentionally computationally expensive. It should be performed with bounded concurrency and carefully calibrated parameters.

Important operational considerations include:

- Avoid unnecessary password-hash recalculation.
- Apply request-level authentication throttling.
- Use indexed identity lookups.
- Keep authorization policy data efficiently accessible.
- Use database transactions for state-changing authentication operations.
- Keep authorization codes short-lived.
- Remove expired sessions and tokens through scheduled cleanup.
- Rotate cryptographic keys using a controlled key-management process.
- Maintain reliable system clocks for TOTP and expiration checks.
- Separate authentication failures from internal application errors.
- Protect audit records against unauthorized modification.
- Avoid recording passwords, raw access tokens, session secrets, and OTP values in logs.

For high-volume systems, token revocation and session state should use a durable shared store rather than process-local collections.

## 14. Implementation Limitations

The implementations are executable educational models rather than complete production identity providers.

| Implementation | Specific limitation |
|---|---|
| Python | In-memory accounts, sessions, tokens, and OAuth state |
| JavaScript | In-memory state and demonstration-only token format |
| C++17 | Demonstration credential, MFA, and PKCE adapters; no cryptographic token signing |
| Java 17 | In-memory state and token-claim lifecycle model rather than a complete serialized JWT protocol |
| PostgreSQL | Database-side workflow and integrity model; external cryptographic verification remains necessary |

The JavaScript and Python token examples demonstrate HMAC signing and validation, but production JWT validation must also enforce issuer, audience, key rotation, and an explicit trusted-key policy.

The SQL demonstration uses PostgreSQL's `pgcrypto` functions for sample hashes and assumes the extension is available in the database. Execute `CREATE EXTENSION IF NOT EXISTS pgcrypto;` before the SQL script if it is not already installed.

The sample SQL password verifier is illustrative and must never be used as a real credential.

A complete deployment also requires secure password-reset workflows, account recovery, device management, CSRF protection where applicable, transport security, secrets management, and monitoring.

## 15. Execution Requirements

| Deliverable | Runtime | Dependencies |
|---|---|---|
| Python | Python 3.10+ | Standard library |
| JavaScript | Node.js 20+ | Node.js standard library |
| C++17 | C++17 compiler | Standard library |
| Java | Java 17 | Standard library |
| PostgreSQL | PostgreSQL 15+ | `pgcrypto` extension |

The Python, JavaScript, and Java examples use real cryptographic primitives for their implemented password, MFA, or token mechanisms. The C++ program explicitly isolates cryptographic integration behind interfaces rather than claiming unsupported security guarantees.

The five implementations demonstrate how identity verification, additional authentication factors, delegated authorization, access-token restrictions, session lifecycle, and centralized permission enforcement work together in an application security architecture.
