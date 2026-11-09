/*
===============================================================================
ENCRYPTION MANAGEMENT AND GOVERNANCE DATABASE
PostgreSQL 15+

Demonstrates:
- Encryption at rest metadata.
- Encryption in transit policy.
- Symmetric encryption.
- Public-key cryptography.
- Hybrid encryption.
- Key lifecycle and rotation.
- AES encryption using pgcrypto.
- Resource classification.
- Encryption policy enforcement.
- Audit logging.
- Validation, reporting, and transaction management.

Security boundary:
pgcrypto encrypts selected database values. It does not replace full-disk
encryption, database backup encryption, TLS, or external key management.

The sample database uses pgcrypto for executable demonstrations.
Production master keys must not be stored in ordinary application tables.
===============================================================================
*/

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS encryption_lab;

SET search_path TO encryption_lab, public;

-- ============================================================================
-- ENUMERATIONS
-- ============================================================================

CREATE TYPE key_status AS ENUM (
    'ACTIVE',
    'ROTATED',
    'REVOKED',
    'EXPIRED'
);

CREATE TYPE encryption_type AS ENUM (
    'SYMMETRIC',
    'PUBLIC_KEY',
    'HYBRID'
);

CREATE TYPE storage_location AS ENUM (
    'DATABASE',
    'FILE_SYSTEM',
    'BACKUP',
    'NETWORK'
);

CREATE TYPE data_classification AS ENUM (
    'PUBLIC',
    'INTERNAL',
    'CONFIDENTIAL',
    'RESTRICTED'
);

CREATE TYPE decision_status AS ENUM (
    'APPROVED',
    'REJECTED'
);

-- ============================================================================
-- ORGANIZATIONAL STRUCTURE
-- ============================================================================

CREATE TABLE organizations (
    organization_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE security_teams (
    team_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),
    team_name VARCHAR(100) NOT NULL,
    UNIQUE (organization_id, team_name)
);

CREATE TABLE security_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),
    username VARCHAR(100) NOT NULL,
    role_name VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (organization_id, username)
);

-- ============================================================================
-- CRYPTOGRAPHIC ALGORITHM REGISTRY
-- ============================================================================

CREATE TABLE encryption_algorithms (
    algorithm_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    algorithm_name VARCHAR(100) NOT NULL UNIQUE,
    encryption_category encryption_type NOT NULL,
    minimum_key_bits INTEGER NOT NULL,
    authenticated BOOLEAN NOT NULL,
    approved BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (minimum_key_bits >= 128)
);

INSERT INTO encryption_algorithms (
    algorithm_name,
    encryption_category,
    minimum_key_bits,
    authenticated,
    approved,
    description
)
VALUES
(
    'AES-256-GCM',
    'SYMMETRIC',
    256,
    TRUE,
    TRUE,
    'Authenticated symmetric encryption'
),
(
    'RSA-OAEP-SHA256',
    'PUBLIC_KEY',
    3072,
    FALSE,
    TRUE,
    'RSA public-key encryption with OAEP and SHA-256'
),
(
    'AES-256-GCM+RSA-OAEP-SHA256',
    'HYBRID',
    3072,
    TRUE,
    TRUE,
    'AES data encryption with RSA-protected data keys'
),
(
    'AES-256-CBC',
    'SYMMETRIC',
    256,
    FALSE,
    TRUE,
    'Legacy encryption requiring separate authentication'
),
(
    'DES',
    'SYMMETRIC',
    56,
    FALSE,
    FALSE,
    'Obsolete encryption algorithm'
);

-- ============================================================================
-- KEY REGISTRY
--
-- The table stores key metadata, not production master-key material.
-- Actual key material belongs in a protected KMS or HSM.
-- ============================================================================

CREATE TABLE encryption_keys (
    key_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key_reference VARCHAR(150) NOT NULL UNIQUE,
    algorithm_id BIGINT NOT NULL
        REFERENCES encryption_algorithms(algorithm_id),
    key_bits INTEGER NOT NULL,
    status key_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    rotated_to BIGINT REFERENCES encryption_keys(key_id),
    created_by BIGINT REFERENCES security_users(user_id),

    CHECK (key_bits >= 128),
    CHECK (expires_at IS NULL OR expires_at > created_at),
    CHECK (rotated_to IS NULL OR rotated_to <> key_id)
);

CREATE INDEX idx_encryption_keys_status
    ON encryption_keys(status);

CREATE INDEX idx_encryption_keys_expiration
    ON encryption_keys(expires_at)
    WHERE status = 'ACTIVE';

-- ============================================================================
-- PROTECTED RESOURCES
-- ============================================================================

CREATE TABLE protected_resources (
    resource_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_name VARCHAR(150) NOT NULL UNIQUE,
    classification data_classification NOT NULL,
    storage storage_location NOT NULL,
    encryption encryption_type NOT NULL,
    algorithm_id BIGINT NOT NULL
        REFERENCES encryption_algorithms(algorithm_id),
    key_id BIGINT NOT NULL
        REFERENCES encryption_keys(key_id),
    encryption_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    tls_required BOOLEAN NOT NULL DEFAULT TRUE,
    owner_id BIGINT REFERENCES security_users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_resources_classification
    ON protected_resources(classification);

CREATE INDEX idx_resources_storage
    ON protected_resources(storage);

CREATE INDEX idx_resources_key
    ON protected_resources(key_id);

-- ============================================================================
-- TRANSPORT SECURITY CONFIGURATION
-- ============================================================================

CREATE TABLE transport_security (
    transport_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT NOT NULL
        REFERENCES protected_resources(resource_id)
        ON DELETE CASCADE,
    tls_version VARCHAR(20) NOT NULL,
    certificate_verified BOOLEAN NOT NULL,
    hostname_verified BOOLEAN NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (tls_version IN ('TLSv1.2', 'TLSv1.3'))
);

-- ============================================================================
-- REPOSITORY-STYLE SECURITY POLICY CONFIGURATION
-- ============================================================================

CREATE TABLE encryption_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),
    policy_name VARCHAR(150) NOT NULL,
    minimum_symmetric_bits INTEGER NOT NULL DEFAULT 256,
    minimum_public_key_bits INTEGER NOT NULL DEFAULT 3072,
    minimum_tls_version VARCHAR(20) NOT NULL DEFAULT 'TLSv1.2',
    require_authenticated_encryption BOOLEAN NOT NULL DEFAULT TRUE,
    require_tls BOOLEAN NOT NULL DEFAULT TRUE,
    maximum_key_age_days INTEGER NOT NULL DEFAULT 365,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (minimum_symmetric_bits >= 256),
    CHECK (minimum_public_key_bits >= 3072),
    CHECK (minimum_tls_version IN ('TLSv1.2', 'TLSv1.3')),
    CHECK (maximum_key_age_days > 0),
    UNIQUE (organization_id, policy_name)
);

CREATE TABLE policy_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_id BIGINT NOT NULL
        REFERENCES encryption_policies(policy_id),
    resource_id BIGINT NOT NULL
        REFERENCES protected_resources(resource_id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (policy_id, resource_id)
);

-- ============================================================================
-- ENCRYPTION AUDIT EVENTS
-- ============================================================================

CREATE TABLE encryption_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT REFERENCES protected_resources(resource_id),
    key_id BIGINT REFERENCES encryption_keys(key_id),
    actor_id BIGINT REFERENCES security_users(user_id),
    event_type VARCHAR(60) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    event_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (outcome IN ('SUCCESS', 'FAILURE', 'WARNING'))
);

CREATE INDEX idx_encryption_audit_resource_time
    ON encryption_audit(resource_id, occurred_at DESC);

CREATE INDEX idx_encryption_audit_event
    ON encryption_audit(event_type, occurred_at DESC);

-- ============================================================================
-- ENCRYPTION POLICY EVALUATION RESULTS
-- ============================================================================

CREATE TABLE policy_evaluations (
    evaluation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT NOT NULL
        REFERENCES protected_resources(resource_id),
    policy_id BIGINT NOT NULL
        REFERENCES encryption_policies(policy_id),
    decision decision_status NOT NULL,
    findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_policy_evaluations_resource
    ON policy_evaluations(resource_id, evaluated_at DESC);

-- ============================================================================
-- TRIGGER: AUTOMATIC RESOURCE UPDATE TIMESTAMP
-- ============================================================================

CREATE OR REPLACE FUNCTION update_resource_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_resource_updated
BEFORE UPDATE ON protected_resources
FOR EACH ROW
EXECUTE FUNCTION update_resource_timestamp();

-- ============================================================================
-- TRIGGER: PREVENT INVALID RESOURCE ENCRYPTION CONFIGURATIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_resource_encryption()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    algorithm_record RECORD;
    key_record RECORD;
BEGIN
    SELECT
        algorithm_name,
        encryption_category,
        minimum_key_bits,
        authenticated,
        approved
    INTO algorithm_record
    FROM encryption_algorithms
    WHERE algorithm_id = NEW.algorithm_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Encryption algorithm not found';
    END IF;

    SELECT
        key_id,
        algorithm_id,
        key_bits,
        status,
        expires_at
    INTO key_record
    FROM encryption_keys
    WHERE key_id = NEW.key_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Encryption key not found';
    END IF;

    IF NOT algorithm_record.approved THEN
        RAISE EXCEPTION 'Encryption algorithm is not approved';
    END IF;

    IF key_record.status <> 'ACTIVE' THEN
        RAISE EXCEPTION 'New resource requires an active key';
    END IF;

    IF key_record.expires_at IS NOT NULL
       AND key_record.expires_at <= CURRENT_TIMESTAMP THEN
        RAISE EXCEPTION 'Encryption key has expired';
    END IF;

    IF algorithm_record.encryption_category <> NEW.encryption THEN
        RAISE EXCEPTION 'Encryption category does not match algorithm';
    END IF;

    IF key_record.key_bits < algorithm_record.minimum_key_bits THEN
        RAISE EXCEPTION 'Encryption key size is insufficient';
    END IF;

    IF key_record.algorithm_id <> NEW.algorithm_id THEN
        RAISE EXCEPTION 'Key algorithm does not match resource algorithm';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_resource_encryption
BEFORE INSERT OR UPDATE OF algorithm_id, key_id, encryption
ON protected_resources
FOR EACH ROW
EXECUTE FUNCTION validate_resource_encryption();

-- ============================================================================
-- KEY ROTATION PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE rotate_encryption_key(
    p_old_key_id BIGINT,
    p_new_key_reference VARCHAR(150),
    p_actor_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    old_key encryption_keys%ROWTYPE;
    new_key_id BIGINT;
BEGIN
    SELECT *
    INTO old_key
    FROM encryption_keys
    WHERE key_id = p_old_key_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Previous key does not exist';
    END IF;

    IF old_key.status <> 'ACTIVE' THEN
        RAISE EXCEPTION 'Only active keys can be rotated';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM encryption_keys
        WHERE key_reference = p_new_key_reference
    ) THEN
        RAISE EXCEPTION 'Replacement key reference already exists';
    END IF;

    INSERT INTO encryption_keys (
        key_reference,
        algorithm_id,
        key_bits,
        status,
        created_by
    )
    VALUES (
        p_new_key_reference,
        old_key.algorithm_id,
        old_key.key_bits,
        'ACTIVE',
        p_actor_id
    )
    RETURNING key_id INTO new_key_id;

    UPDATE encryption_keys
    SET status = 'ROTATED',
        rotated_to = new_key_id
    WHERE key_id = p_old_key_id;

    INSERT INTO encryption_audit (
        key_id,
        actor_id,
        event_type,
        outcome,
        event_details
    )
    VALUES (
        new_key_id,
        p_actor_id,
        'KEY_ROTATION',
        'SUCCESS',
        jsonb_build_object(
            'previous_key_id', p_old_key_id,
            'replacement_key_id', new_key_id
        )
    );
END;
$$;

-- ============================================================================
-- FUNCTION: EVALUATE ENCRYPTION POLICY
-- ============================================================================

CREATE OR REPLACE FUNCTION evaluate_encryption_policy(
    p_resource_id BIGINT,
    p_policy_id BIGINT
)
RETURNS TABLE (
    result decision_status,
    findings JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    resource_record RECORD;
    policy_record RECORD;
    key_record RECORD;
    algorithm_record RECORD;
    transport_record RECORD;

    issues JSONB := '[]'::jsonb;
BEGIN
    SELECT *
    INTO resource_record
    FROM protected_resources
    WHERE resource_id = p_resource_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource does not exist';
    END IF;

    SELECT *
    INTO policy_record
    FROM encryption_policies
    WHERE policy_id = p_policy_id
      AND enabled = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Policy does not exist or is disabled';
    END IF;

    SELECT *
    INTO key_record
    FROM encryption_keys
    WHERE key_id = resource_record.key_id;

    SELECT *
    INTO algorithm_record
    FROM encryption_algorithms
    WHERE algorithm_id = resource_record.algorithm_id;

    IF NOT resource_record.encryption_enabled THEN
        issues := issues || jsonb_build_array(
            'Encryption is disabled'
        );
    END IF;

    IF key_record.status <> 'ACTIVE' THEN
        issues := issues || jsonb_build_array(
            'Resource does not use an active encryption key'
        );
    END IF;

    IF key_record.created_at <
       CURRENT_TIMESTAMP -
       make_interval(days => policy_record.maximum_key_age_days) THEN
        issues := issues || jsonb_build_array(
            'Encryption key exceeds maximum permitted age'
        );
    END IF;

    IF NOT algorithm_record.approved THEN
        issues := issues || jsonb_build_array(
            'Algorithm is not approved'
        );
    END IF;

    IF policy_record.require_authenticated_encryption
       AND NOT algorithm_record.authenticated THEN
        issues := issues || jsonb_build_array(
            'Authenticated encryption is required'
        );
    END IF;

    IF resource_record.encryption = 'SYMMETRIC'
       AND key_record.key_bits <
           policy_record.minimum_symmetric_bits THEN
        issues := issues || jsonb_build_array(
            'Symmetric key size is insufficient'
        );
    END IF;

    IF resource_record.encryption = 'PUBLIC_KEY'
       AND key_record.key_bits <
           policy_record.minimum_public_key_bits THEN
        issues := issues || jsonb_build_array(
            'Public key size is insufficient'
        );
    END IF;

    IF (resource_record.storage = 'NETWORK'
        OR policy_record.require_tls)
       AND resource_record.tls_required THEN

        SELECT *
        INTO transport_record
        FROM transport_security
        WHERE resource_id = p_resource_id
          AND enabled = TRUE
        ORDER BY verified_at DESC
        LIMIT 1;

        IF NOT FOUND THEN
            issues := issues || jsonb_build_array(
                'Verified TLS configuration is missing'
            );
        ELSE
            IF transport_record.tls_version NOT IN (
                'TLSv1.2',
                'TLSv1.3'
            ) THEN
                issues := issues || jsonb_build_array(
                    'TLS protocol is below minimum'
                );
            END IF;

            IF NOT transport_record.certificate_verified
               OR NOT transport_record.hostname_verified THEN
                issues := issues || jsonb_build_array(
                    'TLS certificate or hostname verification failed'
                );
            END IF;

            IF policy_record.minimum_tls_version = 'TLSv1.3'
               AND transport_record.tls_version <> 'TLSv1.3' THEN
                issues := issues || jsonb_build_array(
                    'TLS 1.3 is required by policy'
                );
            END IF;
        END IF;
    END IF;

    result := CASE
        WHEN jsonb_array_length(issues) = 0
            THEN 'APPROVED'::decision_status
        ELSE 'REJECTED'::decision_status
    END;

    findings := issues;

    RETURN NEXT;
END;
$$;

-- ============================================================================
-- VIEW: ENCRYPTION RESOURCE INVENTORY
-- ============================================================================

CREATE OR REPLACE VIEW encryption_inventory AS
SELECT
    r.resource_id,
    r.resource_name,
    r.classification,
    r.storage,
    r.encryption,
    a.algorithm_name,
    a.authenticated,
    k.key_reference,
    k.key_bits,
    k.status AS key_status,
    r.encryption_enabled,
    r.tls_required,
    r.updated_at
FROM protected_resources r
JOIN encryption_algorithms a
    ON a.algorithm_id = r.algorithm_id
JOIN encryption_keys k
    ON k.key_id = r.key_id;

-- ============================================================================
-- VIEW: KEY ROTATION MONITORING
-- ============================================================================

CREATE OR REPLACE VIEW key_rotation_monitor AS
SELECT
    key_id,
    key_reference,
    status,
    created_at,
    expires_at,
    rotated_to,
    EXTRACT(
        DAY FROM CURRENT_TIMESTAMP - created_at
    )::INTEGER AS age_days
FROM encryption_keys;

-- ============================================================================
-- DEMONSTRATION DATA
-- ============================================================================

INSERT INTO organizations (organization_name)
VALUES ('Enterprise Security Division');

INSERT INTO security_teams (
    organization_id,
    team_name
)
SELECT organization_id, 'Cryptographic Operations'
FROM organizations
WHERE organization_name = 'Enterprise Security Division';

INSERT INTO security_users (
    organization_id,
    username,
    role_name
)
SELECT organization_id, 'security_admin', 'KEY_ADMIN'
FROM organizations
WHERE organization_name = 'Enterprise Security Division';

INSERT INTO security_users (
    organization_id,
    username,
    role_name
)
SELECT organization_id, 'application_owner', 'RESOURCE_OWNER'
FROM organizations
WHERE organization_name = 'Enterprise Security Division';

INSERT INTO encryption_policies (
    organization_id,
    policy_name,
    minimum_symmetric_bits,
    minimum_public_key_bits,
    minimum_tls_version,
    require_authenticated_encryption,
    require_tls,
    maximum_key_age_days
)
SELECT
    organization_id,
    'Enterprise Encryption Standard',
    256,
    3072,
    'TLSv1.2',
    TRUE,
    TRUE,
    365
FROM organizations
WHERE organization_name = 'Enterprise Security Division';

INSERT INTO encryption_keys (
    key_reference,
    algorithm_id,
    key_bits,
    status,
    created_by
)
SELECT
    'kms/database-key-001',
    algorithm_id,
    256,
    'ACTIVE',
    (
        SELECT user_id
        FROM security_users
        WHERE username = 'security_admin'
    )
FROM encryption_algorithms
WHERE algorithm_name = 'AES-256-GCM';

INSERT INTO encryption_keys (
    key_reference,
    algorithm_id,
    key_bits,
    status,
    created_by
)
SELECT
    'kms/database-key-legacy',
    algorithm_id,
    256,
    'ACTIVE',
    (
        SELECT user_id
        FROM security_users
        WHERE username = 'security_admin'
    )
FROM encryption_algorithms
WHERE algorithm_name = 'AES-256-CBC';

INSERT INTO protected_resources (
    resource_name,
    classification,
    storage,
    encryption,
    algorithm_id,
    key_id,
    owner_id
)
SELECT
    'customer_database',
    'CONFIDENTIAL',
    'DATABASE',
    'SYMMETRIC',
    a.algorithm_id,
    k.key_id,
    u.user_id
FROM encryption_algorithms a
CROSS JOIN encryption_keys k
CROSS JOIN security_users u
WHERE a.algorithm_name = 'AES-256-GCM'
  AND k.key_reference = 'kms/database-key-001'
  AND u.username = 'application_owner';

INSERT INTO protected_resources (
    resource_name,
    classification,
    storage,
    encryption,
    algorithm_id,
    key_id,
    owner_id
)
SELECT
    'legacy_archive',
    'RESTRICTED',
    'BACKUP',
    'SYMMETRIC',
    a.algorithm_id,
    k.key_id,
    u.user_id
FROM encryption_algorithms a
CROSS JOIN encryption_keys k
CROSS JOIN security_users u
WHERE a.algorithm_name = 'AES-256-CBC'
  AND k.key_reference = 'kms/database-key-legacy'
  AND u.username = 'application_owner';

INSERT INTO transport_security (
    resource_id,
    tls_version,
    certificate_verified,
    hostname_verified
)
SELECT
    resource_id,
    'TLSv1.3',
    TRUE,
    TRUE
FROM protected_resources
WHERE resource_name = 'customer_database';

INSERT INTO policy_assignments (
    policy_id,
    resource_id
)
SELECT
    p.policy_id,
    r.resource_id
FROM encryption_policies p
CROSS JOIN protected_resources r
WHERE p.policy_name = 'Enterprise Encryption Standard';

-- ============================================================================
-- DATABASE ENCRYPTION EXAMPLE
--
-- Demonstrates pgcrypto symmetric encryption.
-- The sample password is deliberately restricted to this isolated
-- demonstration. Never place production encryption passwords in SQL files.
-- ============================================================================

CREATE TABLE encrypted_customer_records (
    record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_reference VARCHAR(100) NOT NULL UNIQUE,
    encrypted_payload BYTEA NOT NULL,
    encryption_algorithm VARCHAR(50) NOT NULL DEFAULT 'AES-256',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Store authenticated encrypted data using pgcrypto.
INSERT INTO encrypted_customer_records (
    customer_reference,
    encrypted_payload
)
VALUES (
    'CUSTOMER-1001',
    pgp_sym_encrypt(
        'Confidential customer account information',
        'DEMO-ONLY-ENCRYPTION-PASSWORD',
        'cipher-algo=aes256, compress-algo=0'
    )
);

-- Controlled demonstration of decryption.
-- Production applications should retrieve keys from an external KMS.
SELECT
    record_id,
    customer_reference,
    pgp_sym_decrypt(
        encrypted_payload,
        'DEMO-ONLY-ENCRYPTION-PASSWORD'
    ) AS decrypted_payload
FROM encrypted_customer_records;

-- ============================================================================
-- EVALUATION AND REPORTING WORKFLOWS
-- ============================================================================

-- Retrieve all registered encryption resources.
SELECT *
FROM encryption_inventory
ORDER BY resource_id;

-- Evaluate resources against assigned policies.
INSERT INTO policy_evaluations (
    resource_id,
    policy_id,
    decision,
    findings
)
SELECT
    assignment.resource_id,
    assignment.policy_id,
    evaluation.result,
    evaluation.findings
FROM policy_assignments assignment
CROSS JOIN LATERAL evaluate_encryption_policy(
    assignment.resource_id,
    assignment.policy_id
) evaluation;

-- Show policy evaluation results.
SELECT
    resource.resource_name,
    policy.policy_name,
    evaluation.decision,
    evaluation.findings,
    evaluation.evaluated_at
FROM policy_evaluations evaluation
JOIN protected_resources resource
    ON resource.resource_id = evaluation.resource_id
JOIN encryption_policies policy
    ON policy.policy_id = evaluation.policy_id
ORDER BY evaluation.evaluated_at DESC;

-- Aggregate resources by encryption algorithm.
SELECT
    algorithm_name,
    COUNT(*) AS resource_count,
    COUNT(*) FILTER (
        WHERE authenticated
    ) AS authenticated_resource_count
FROM encryption_inventory
GROUP BY algorithm_name
ORDER BY resource_count DESC;

-- Identify inactive or expired encryption keys.
SELECT
    key_reference,
    status,
    created_at,
    expires_at
FROM encryption_keys
WHERE status <> 'ACTIVE'
   OR (expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP);

-- Identify resources with unsuccessful encryption evaluations.
SELECT
    resource_name,
    classification,
    findings
FROM policy_evaluations evaluation
JOIN protected_resources resource
    ON resource.resource_id = evaluation.resource_id
WHERE decision = 'REJECTED';

-- ============================================================================
-- AUDIT WORKFLOW
-- ============================================================================

INSERT INTO encryption_audit (
    resource_id,
    key_id,
    event_type,
    outcome,
    event_details
)
SELECT
    resource.resource_id,
    resource.key_id,
    'ENCRYPTION_POLICY_CHECK',
    CASE
        WHEN evaluation.decision = 'APPROVED' THEN 'SUCCESS'
        ELSE 'FAILURE'
    END,
    jsonb_build_object(
        'decision', evaluation.decision,
        'findings', evaluation.findings
    )
FROM policy_evaluations evaluation
JOIN protected_resources resource
    ON resource.resource_id = evaluation.resource_id;

-- Audit activity grouped by event type.
SELECT
    event_type,
    outcome,
    COUNT(*) AS event_count
FROM encryption_audit
GROUP BY event_type, outcome
ORDER BY event_count DESC;

-- ============================================================================
-- KEY ROTATION DEMONSTRATION
--
-- The procedure creates replacement metadata and marks the old key ROTATED.
-- Resource migration is a separate controlled operation.
-- ============================================================================

CALL rotate_encryption_key(
    (
        SELECT key_id
        FROM encryption_keys
        WHERE key_reference = 'kms/database-key-001'
    ),
    'kms/database-key-002',
    (
        SELECT user_id
        FROM security_users
        WHERE username = 'security_admin'
    )
);

-- Migrate the resource to the replacement key.
UPDATE protected_resources
SET key_id = (
    SELECT key_id
    FROM encryption_keys
    WHERE key_reference = 'kms/database-key-002'
)
WHERE resource_name = 'customer_database';

-- Re-evaluate after rotation.
SELECT
    resource_name,
    key_reference,
    key_status
FROM encryption_inventory
WHERE resource_name = 'customer_database';

-- ============================================================================
-- FAILURE CASE DEMONSTRATION
--
-- The following DO block attempts to register a resource using an
-- unapproved algorithm. The exception is caught so the script can continue.
-- ============================================================================

DO $$
BEGIN
    BEGIN
        INSERT INTO protected_resources (
            resource_name,
            classification,
            storage,
            encryption,
            algorithm_id,
            key_id
        )
        SELECT
            'rejected_legacy_resource',
            'RESTRICTED',
            'DATABASE',
            'SYMMETRIC',
            a.algorithm_id,
            k.key_id
        FROM encryption_algorithms a
        CROSS JOIN encryption_keys k
        WHERE a.algorithm_name = 'DES'
          AND k.key_reference = 'kms/database-key-002';

    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE
                'Expected policy rejection: %',
                SQLERRM;
    END;
END;
$$;

-- ============================================================================
-- TRANSACTIONAL INTEGRITY CHECK
-- ============================================================================

DO $$
DECLARE
    resource_count INTEGER;
    active_key_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO resource_count
    FROM protected_resources;

    SELECT COUNT(*)
    INTO active_key_count
    FROM encryption_keys
    WHERE status = 'ACTIVE';

    IF resource_count < 1 THEN
        RAISE EXCEPTION 'No protected resources registered';
    END IF;

    IF active_key_count < 1 THEN
        RAISE EXCEPTION 'No active encryption keys available';
    END IF;

    RAISE NOTICE 'Registered resources: %', resource_count;
    RAISE NOTICE 'Active keys: %', active_key_count;
END;
$$;

COMMIT;

-- ============================================================================
-- FINAL REPORT
-- ============================================================================

SELECT
    resource_name,
    classification,
    storage,
    algorithm_name,
    key_reference,
    key_status,
    authenticated,
    encryption_enabled
FROM encryption_inventory
ORDER BY resource_name;

SELECT
    event_type,
    outcome,
    occurred_at,
    event_details
FROM encryption_audit
ORDER BY occurred_at DESC;

SELECT
    key_reference,
    status,
    age_days,
    rotated_to
FROM key_rotation_monitor
ORDER BY created_at DESC;
