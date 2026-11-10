-- ============================================================
-- KEY MANAGEMENT AND SECRETS GOVERNANCE
-- PostgreSQL 15+
--
-- Models:
--   Cryptographic keys and versions
--   Key lifecycle and rotation
--   Envelope encryption metadata
--   Secrets and encrypted data references
--   HSM providers
--   Access policies and principals
--   Audit events
--   Rotation workflows
--   Key revocation and expiration
--   Approval and operational controls
--
-- Important:
-- Actual key material is NOT stored in this database.
-- Key operations must execute in a KMS/HSM security boundary.
-- Encrypted payloads may be stored separately.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS key_management;

SET search_path TO key_management, public;

-- ============================================================
-- 1. ENUM TYPES
-- ============================================================

CREATE TYPE principal_role AS ENUM (
    'ADMIN',
    'CRYPTO_OPERATOR',
    'APPLICATION',
    'AUDITOR'
);

CREATE TYPE key_purpose AS ENUM (
    'ENCRYPTION',
    'SIGNING',
    'HMAC',
    'KEY_ENCRYPTION'
);

CREATE TYPE key_status AS ENUM (
    'ACTIVE',
    'ROTATED',
    'DISABLED',
    'REVOKED',
    'EXPIRED'
);

CREATE TYPE provider_type AS ENUM (
    'SOFTWARE_KMS',
    'CLOUD_KMS',
    'HARDWARE_HSM'
);

CREATE TYPE rotation_status AS ENUM (
    'SCHEDULED',
    'IN_PROGRESS',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);

CREATE TYPE review_state AS ENUM (
    'APPROVED',
    'CHANGES_REQUESTED',
    'COMMENTED',
    'DISMISSED'
);

CREATE TYPE check_status AS ENUM (
    'PASSED',
    'FAILED',
    'PENDING'
);

-- ============================================================
-- 2. SECURITY PRINCIPALS
-- ============================================================

CREATE TABLE principals (
    principal_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    principal_name VARCHAR(128) NOT NULL UNIQUE,

    role principal_role NOT NULL,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_authenticated_at TIMESTAMPTZ
);

INSERT INTO principals (
    principal_name,
    role
)
VALUES
    ('security-admin', 'ADMIN'),
    ('crypto-operator', 'CRYPTO_OPERATOR'),
    ('payment-service', 'APPLICATION'),
    ('security-auditor', 'AUDITOR'),
    ('reporting-service', 'APPLICATION');

-- ============================================================
-- 3. KMS AND HSM PROVIDERS
-- ============================================================

CREATE TABLE key_providers (
    provider_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    provider_name VARCHAR(150) NOT NULL UNIQUE,

    provider_type provider_type NOT NULL,

    region VARCHAR(100),

    hardware_backed BOOLEAN NOT NULL DEFAULT FALSE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        provider_type <> 'HARDWARE_HSM'
        OR hardware_backed = TRUE
    )
);

INSERT INTO key_providers (
    provider_name,
    provider_type,
    region,
    hardware_backed
)
VALUES
    (
        'Enterprise-HSM-01',
        'HARDWARE_HSM',
        'ap-south-1',
        TRUE
    ),
    (
        'Application-KMS',
        'SOFTWARE_KMS',
        'ap-south-1',
        FALSE
    ),
    (
        'Cloud-KMS-Production',
        'CLOUD_KMS',
        'ap-south-1',
        TRUE
    );

-- ============================================================
-- 4. KEY DEFINITIONS
--
-- A key definition represents a logical cryptographic key.
-- Actual material remains outside PostgreSQL.
-- ============================================================

CREATE TABLE cryptographic_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    key_name VARCHAR(150) NOT NULL UNIQUE,

    purpose key_purpose NOT NULL,

    algorithm VARCHAR(80) NOT NULL,

    key_size_bits INTEGER NOT NULL,

    provider_id BIGINT NOT NULL
        REFERENCES key_providers(provider_id),

    created_by BIGINT NOT NULL
        REFERENCES principals(principal_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    rotation_interval_days INTEGER NOT NULL DEFAULT 90,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CHECK (key_size_bits IN (128, 192, 256, 384, 521)),

    CHECK (rotation_interval_days BETWEEN 1 AND 3650)
);

INSERT INTO cryptographic_keys (
    key_name,
    purpose,
    algorithm,
    key_size_bits,
    provider_id,
    created_by,
    rotation_interval_days
)
SELECT
    'payment-data-key',
    'ENCRYPTION',
    'AES-256-GCM',
    256,
    p.provider_id,
    u.principal_id,
    90
FROM key_providers p
CROSS JOIN principals u
WHERE p.provider_name = 'Enterprise-HSM-01'
AND u.principal_name = 'crypto-operator';

INSERT INTO cryptographic_keys (
    key_name,
    purpose,
    algorithm,
    key_size_bits,
    provider_id,
    created_by,
    rotation_interval_days
)
SELECT
    'payment-key-encryption-key',
    'KEY_ENCRYPTION',
    'AES-256-GCM',
    256,
    p.provider_id,
    u.principal_id,
    180
FROM key_providers p
CROSS JOIN principals u
WHERE p.provider_name = 'Cloud-KMS-Production'
AND u.principal_name = 'crypto-operator';

-- ============================================================
-- 5. KEY VERSIONS
--
-- Previous versions remain available for controlled
-- decryption until retention and destruction policies permit
-- their removal.
-- ============================================================

CREATE TABLE key_versions (
    key_version_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    key_id UUID NOT NULL
        REFERENCES cryptographic_keys(key_id),

    version_number INTEGER NOT NULL,

    status key_status NOT NULL DEFAULT 'ACTIVE',

    provider_reference VARCHAR(255) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    rotated_at TIMESTAMPTZ,

    revoked_at TIMESTAMPTZ,

    hardware_protected BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE (key_id, version_number),

    UNIQUE (provider_reference),

    CHECK (version_number > 0),

    CHECK (expires_at > created_at),

    CHECK (
        status <> 'REVOKED'
        OR revoked_at IS NOT NULL
    )
);

-- One active version per logical key.
CREATE UNIQUE INDEX uq_active_key_version
ON key_versions(key_id)
WHERE status = 'ACTIVE';

INSERT INTO key_versions (
    key_id,
    version_number,
    status,
    provider_reference,
    expires_at,
    hardware_protected
)
SELECT
    key_id,
    1,
    'ACTIVE',
    'HSM-REFERENCE-PAYMENT-V1',
    NOW() + INTERVAL '90 days',
    TRUE
FROM cryptographic_keys
WHERE key_name = 'payment-data-key';

INSERT INTO key_versions (
    key_id,
    version_number,
    status,
    provider_reference,
    expires_at,
    hardware_protected
)
SELECT
    key_id,
    1,
    'ACTIVE',
    'CLOUD-KMS-REFERENCE-KEK-V1',
    NOW() + INTERVAL '180 days',
    TRUE
FROM cryptographic_keys
WHERE key_name = 'payment-key-encryption-key';

-- ============================================================
-- 6. KEY ACCESS POLICIES
-- ============================================================

CREATE TABLE key_access_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    key_id UUID NOT NULL
        REFERENCES cryptographic_keys(key_id),

    principal_id BIGINT NOT NULL
        REFERENCES principals(principal_id),

    can_encrypt BOOLEAN NOT NULL DEFAULT FALSE,

    can_decrypt BOOLEAN NOT NULL DEFAULT FALSE,

    can_rotate BOOLEAN NOT NULL DEFAULT FALSE,

    can_revoke BOOLEAN NOT NULL DEFAULT FALSE,

    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ,

    granted_by BIGINT NOT NULL
        REFERENCES principals(principal_id),

    UNIQUE (key_id, principal_id),

    CHECK (
        expires_at IS NULL
        OR expires_at > granted_at
    )
);

INSERT INTO key_access_policies (
    key_id,
    principal_id,
    can_encrypt,
    can_decrypt,
    granted_by
)
SELECT
    k.key_id,
    app.principal_id,
    TRUE,
    TRUE,
    admin.principal_id
FROM cryptographic_keys k
CROSS JOIN principals app
CROSS JOIN principals admin
WHERE k.key_name = 'payment-data-key'
AND app.principal_name = 'payment-service'
AND admin.principal_name = 'security-admin';

INSERT INTO key_access_policies (
    key_id,
    principal_id,
    can_rotate,
    can_revoke,
    granted_by
)
SELECT
    k.key_id,
    op.principal_id,
    TRUE,
    FALSE,
    admin.principal_id
FROM cryptographic_keys k
CROSS JOIN principals op
CROSS JOIN principals admin
WHERE k.key_name = 'payment-data-key'
AND op.principal_name = 'crypto-operator'
AND admin.principal_name = 'security-admin';

-- ============================================================
-- 7. ENCRYPTED SECRET REGISTRY
--
-- Only references and encrypted payload metadata are kept.
-- Secret plaintext and raw key material are not stored.
-- ============================================================

CREATE TABLE managed_secrets (
    secret_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    secret_name VARCHAR(150) NOT NULL UNIQUE,

    key_id UUID NOT NULL
        REFERENCES cryptographic_keys(key_id),

    key_version_id BIGINT NOT NULL
        REFERENCES key_versions(key_version_id),

    encrypted_payload BYTEA NOT NULL,

    nonce BYTEA NOT NULL,

    authentication_tag BYTEA NOT NULL,

    encryption_algorithm VARCHAR(80) NOT NULL,

    created_by BIGINT NOT NULL
        REFERENCES principals(principal_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ,

    CHECK (OCTET_LENGTH(encrypted_payload) > 0),

    CHECK (OCTET_LENGTH(nonce) > 0),

    CHECK (OCTET_LENGTH(authentication_tag) > 0)
);

INSERT INTO managed_secrets (
    secret_name,
    key_id,
    key_version_id,
    encrypted_payload,
    nonce,
    authentication_tag,
    encryption_algorithm,
    created_by,
    expires_at
)
SELECT
    'payment-db-credential',
    k.key_id,
    v.key_version_id,
    DECODE('AABBCCDD', 'hex'),
    DECODE('00112233445566778899AABB', 'hex'),
    DECODE('00112233445566778899AABBCCDDEEFF', 'hex'),
    'AES-256-GCM',
    p.principal_id,
    NOW() + INTERVAL '30 days'
FROM cryptographic_keys k
JOIN key_versions v ON v.key_id = k.key_id
JOIN principals p
    ON p.principal_name = 'payment-service'
WHERE k.key_name = 'payment-data-key';

-- ============================================================
-- 8. KEY ROTATION WORKFLOW
-- ============================================================

CREATE TABLE rotation_jobs (
    rotation_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    key_id UUID NOT NULL
        REFERENCES cryptographic_keys(key_id),

    old_version_id BIGINT
        REFERENCES key_versions(key_version_id),

    new_version_id BIGINT
        REFERENCES key_versions(key_version_id),

    status rotation_status NOT NULL DEFAULT 'SCHEDULED',

    requested_by BIGINT NOT NULL
        REFERENCES principals(principal_id),

    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    failure_reason TEXT,

    CHECK (
        status <> 'COMPLETED'
        OR (
            new_version_id IS NOT NULL
            AND completed_at IS NOT NULL
        )
    )
);

CREATE INDEX idx_rotation_jobs_status
ON rotation_jobs(status, requested_at);

-- ============================================================
-- 9. SECURITY AUDIT LOG
-- ============================================================

CREATE TABLE key_audit_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    principal_id BIGINT
        REFERENCES principals(principal_id),

    action VARCHAR(80) NOT NULL,

    resource_type VARCHAR(80) NOT NULL,

    resource_reference VARCHAR(255),

    outcome VARCHAR(30) NOT NULL,

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        outcome IN (
            'SUCCESS',
            'FAILURE',
            'DENIED'
        )
    )
);

CREATE INDEX idx_audit_created
ON key_audit_events(created_at DESC);

CREATE INDEX idx_audit_principal_action
ON key_audit_events(principal_id, action);

CREATE INDEX idx_audit_details
ON key_audit_events
USING GIN(event_details);

-- ============================================================
-- 10. AUDIT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION log_key_version_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO key_audit_events (
        action,
        resource_type,
        resource_reference,
        outcome,
        event_details
    )
    VALUES (
        'KEY_VERSION_STATE_CHANGE',
        'KEY_VERSION',
        NEW.key_version_id::TEXT,
        'SUCCESS',
        JSONB_BUILD_OBJECT(
            'key_id', NEW.key_id,
            'version', NEW.version_number,
            'old_status', OLD.status,
            'new_status', NEW.status
        )
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_key_version_audit
AFTER UPDATE OF status ON key_versions
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION log_key_version_change();

-- ============================================================
-- 11. APPROVAL GOVERNANCE
-- ============================================================

CREATE TABLE key_rotation_approvals (
    approval_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    rotation_id BIGINT NOT NULL
        REFERENCES rotation_jobs(rotation_id),

    reviewer_id BIGINT NOT NULL
        REFERENCES principals(principal_id),

    approved BOOLEAN NOT NULL,

    decision_reason TEXT,

    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (rotation_id, reviewer_id)
);

-- ============================================================
-- 12. KEY LIFECYCLE FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION get_key_lifecycle(
    p_key_id UUID
)
RETURNS TABLE (
    key_name VARCHAR,
    version_number INTEGER,
    version_status key_status,
    expires_at TIMESTAMPTZ,
    days_remaining INTEGER
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        k.key_name,
        v.version_number,
        v.status,
        v.expires_at,
        GREATEST(
            0,
            CEIL(
                EXTRACT(
                    EPOCH FROM (v.expires_at - NOW())
                ) / 86400
            )::INTEGER
        )
    FROM cryptographic_keys k
    JOIN key_versions v ON v.key_id = k.key_id
    WHERE k.key_id = p_key_id
    ORDER BY v.version_number DESC;
$$;

-- ============================================================
-- 13. ACCESS VALIDATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION can_access_key(
    p_principal_id BIGINT,
    p_key_id UUID,
    p_operation TEXT
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM principals p
        JOIN key_access_policies a
            ON a.principal_id = p.principal_id
        JOIN cryptographic_keys k
            ON k.key_id = a.key_id
        JOIN key_versions v
            ON v.key_id = k.key_id
        WHERE p.principal_id = p_principal_id
          AND a.key_id = p_key_id
          AND p.enabled = TRUE
          AND k.enabled = TRUE
          AND v.status = 'ACTIVE'
          AND v.expires_at > NOW()
          AND (
              a.expires_at IS NULL
              OR a.expires_at > NOW()
          )
          AND CASE p_operation
              WHEN 'ENCRYPT' THEN a.can_encrypt
              WHEN 'DECRYPT' THEN a.can_decrypt
              WHEN 'ROTATE' THEN a.can_rotate
              WHEN 'REVOKE' THEN a.can_revoke
              ELSE FALSE
          END
    );
$$;

-- ============================================================
-- 14. ROTATION SCHEDULING PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE schedule_expiring_keys()
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO rotation_jobs (
        key_id,
        old_version_id,
        status,
        requested_by
    )
    SELECT
        k.key_id,
        v.key_version_id,
        'SCHEDULED',
        p.principal_id
    FROM cryptographic_keys k
    JOIN key_versions v
        ON v.key_id = k.key_id
    CROSS JOIN principals p
    WHERE p.principal_name = 'crypto-operator'
      AND v.status = 'ACTIVE'
      AND v.expires_at <= NOW() + INTERVAL '15 days'
      AND NOT EXISTS (
          SELECT 1
          FROM rotation_jobs r
          WHERE r.key_id = k.key_id
            AND r.status IN (
                'SCHEDULED',
                'IN_PROGRESS'
            )
      );
END;
$$;

-- ============================================================
-- 15. KEY VERSION ROTATION PROCEDURE
--
-- The provider_reference represents an external KMS/HSM
-- operation identifier, not raw key material.
-- ============================================================

CREATE OR REPLACE PROCEDURE rotate_key_version(
    p_key_id UUID,
    p_actor_id BIGINT,
    p_provider_reference VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    current_version key_versions%ROWTYPE;
    new_version_id BIGINT;
    next_version INTEGER;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM principals
        WHERE principal_id = p_actor_id
          AND enabled = TRUE
          AND role IN ('ADMIN', 'CRYPTO_OPERATOR')
    ) THEN
        RAISE EXCEPTION
            'Unauthorized rotation request';
    END IF;

    IF p_provider_reference IS NULL
       OR LENGTH(TRIM(p_provider_reference)) = 0 THEN
        RAISE EXCEPTION
            'Provider reference is required';
    END IF;

    SELECT *
    INTO current_version
    FROM key_versions
    WHERE key_id = p_key_id
      AND status = 'ACTIVE'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No active key version available';
    END IF;

    next_version := current_version.version_number + 1;

    UPDATE key_versions
    SET
        status = 'ROTATED',
        rotated_at = NOW()
    WHERE key_version_id =
        current_version.key_version_id;

    INSERT INTO key_versions (
        key_id,
        version_number,
        status,
        provider_reference,
        expires_at,
        hardware_protected
    )
    VALUES (
        p_key_id,
        next_version,
        'ACTIVE',
        p_provider_reference,
        NOW() + INTERVAL '90 days',
        current_version.hardware_protected
    )
    RETURNING key_version_id
    INTO new_version_id;

    INSERT INTO rotation_jobs (
        key_id,
        old_version_id,
        new_version_id,
        status,
        requested_by,
        completed_at
    )
    VALUES (
        p_key_id,
        current_version.key_version_id,
        new_version_id,
        'COMPLETED',
        p_actor_id,
        NOW()
    );

    INSERT INTO key_audit_events (
        principal_id,
        action,
        resource_type,
        resource_reference,
        outcome,
        event_details
    )
    VALUES (
        p_actor_id,
        'ROTATE_KEY',
        'KEY',
        p_key_id::TEXT,
        'SUCCESS',
        JSONB_BUILD_OBJECT(
            'old_version',
            current_version.version_number,
            'new_version',
            next_version
        )
    );
END;
$$;

-- ============================================================
-- 16. CONTROLLED REVOCATION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE revoke_key(
    p_key_id UUID,
    p_actor_id BIGINT,
    p_reason TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM principals
        WHERE principal_id = p_actor_id
          AND enabled = TRUE
          AND role = 'ADMIN'
    ) THEN
        RAISE EXCEPTION
            'Only administrators can revoke keys';
    END IF;

    IF p_reason IS NULL
       OR LENGTH(TRIM(p_reason)) < 5 THEN
        RAISE EXCEPTION
            'A revocation reason is required';
    END IF;

    UPDATE key_versions
    SET
        status = 'REVOKED',
        revoked_at = NOW()
    WHERE key_id = p_key_id
      AND status <> 'REVOKED';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No revocable key versions found';
    END IF;

    INSERT INTO key_audit_events (
        principal_id,
        action,
        resource_type,
        resource_reference,
        outcome,
        event_details
    )
    VALUES (
        p_actor_id,
        'REVOKE_KEY',
        'KEY',
        p_key_id::TEXT,
        'SUCCESS',
        JSONB_BUILD_OBJECT(
            'reason', p_reason
        )
    );
END;
$$;

-- ============================================================
-- 17. SECRET RE-ENCRYPTION REGISTRY UPDATE
--
-- The actual decrypt/encrypt operation must happen in a
-- trusted KMS/HSM-backed application service.
-- This procedure records the resulting envelope metadata.
-- ============================================================

CREATE OR REPLACE PROCEDURE register_secret_reencryption(
    p_secret_id UUID,
    p_new_version_id BIGINT,
    p_new_payload BYTEA,
    p_new_nonce BYTEA,
    p_new_tag BYTEA,
    p_actor_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    old_key_id UUID;
    new_key_id UUID;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM principals
        WHERE principal_id = p_actor_id
          AND enabled = TRUE
          AND role IN ('ADMIN', 'CRYPTO_OPERATOR')
    ) THEN
        RAISE EXCEPTION
            'Re-encryption registration denied';
    END IF;

    SELECT key_id
    INTO old_key_id
    FROM managed_secrets
    WHERE secret_id = p_secret_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Secret not found';
    END IF;

    SELECT key_id
    INTO new_key_id
    FROM key_versions
    WHERE key_version_id = p_new_version_id
      AND status = 'ACTIVE'
      AND expires_at > NOW();

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'New key version is not active';
    END IF;

    IF old_key_id <> new_key_id THEN
        RAISE EXCEPTION
            'Secret key identity mismatch';
    END IF;

    IF p_new_payload IS NULL
       OR p_new_nonce IS NULL
       OR p_new_tag IS NULL THEN
        RAISE EXCEPTION
            'Encrypted envelope is incomplete';
    END IF;

    UPDATE managed_secrets
    SET
        key_version_id = p_new_version_id,
        encrypted_payload = p_new_payload,
        nonce = p_new_nonce,
        authentication_tag = p_new_tag,
        updated_at = NOW()
    WHERE secret_id = p_secret_id;

    INSERT INTO key_audit_events (
        principal_id,
        action,
        resource_type,
        resource_reference,
        outcome
    )
    VALUES (
        p_actor_id,
        'SECRET_REENCRYPTION',
        'SECRET',
        p_secret_id::TEXT,
        'SUCCESS'
    );
END;
$$;

-- ============================================================
-- 18. OPERATIONAL VIEWS
-- ============================================================

CREATE VIEW active_key_inventory AS
SELECT
    k.key_name,
    k.algorithm,
    k.purpose,
    v.version_number,
    v.status,
    v.created_at,
    v.expires_at,
    p.provider_name,
    p.provider_type,
    v.hardware_protected
FROM cryptographic_keys k
JOIN key_versions v
    ON v.key_id = k.key_id
JOIN key_providers p
    ON p.provider_id = k.provider_id
WHERE v.status = 'ACTIVE';

CREATE VIEW expiring_key_report AS
SELECT
    k.key_name,
    v.version_number,
    v.expires_at,
    CEIL(
        EXTRACT(EPOCH FROM (v.expires_at - NOW()))
        / 86400
    )::INTEGER AS days_remaining
FROM cryptographic_keys k
JOIN key_versions v
    ON v.key_id = k.key_id
WHERE v.status = 'ACTIVE'
  AND v.expires_at <= NOW() + INTERVAL '30 days';

CREATE VIEW secret_encryption_inventory AS
SELECT
    s.secret_name,
    k.key_name,
    v.version_number,
    v.status,
    s.encryption_algorithm,
    s.created_at,
    s.updated_at,
    s.expires_at
FROM managed_secrets s
JOIN cryptographic_keys k
    ON k.key_id = s.key_id
JOIN key_versions v
    ON v.key_version_id = s.key_version_id;

-- ============================================================
-- 19. APPROVAL AND ROTATION REPORT
-- ============================================================

CREATE VIEW rotation_approval_report AS
SELECT
    r.rotation_id,
    k.key_name,
    r.status,
    COUNT(a.approval_id) AS total_reviews,
    COUNT(a.approval_id)
        FILTER (WHERE a.approved) AS approvals,
    COUNT(a.approval_id)
        FILTER (WHERE NOT a.approved) AS rejections
FROM rotation_jobs r
JOIN cryptographic_keys k
    ON k.key_id = r.key_id
LEFT JOIN key_rotation_approvals a
    ON a.rotation_id = r.rotation_id
GROUP BY
    r.rotation_id,
    k.key_name,
    r.status;

-- ============================================================
-- 20. SAMPLE WORKFLOW
-- ============================================================

BEGIN;

CALL schedule_expiring_keys();

COMMIT;

-- ============================================================
-- 21. RETRIEVAL QUERIES
-- ============================================================

SELECT *
FROM active_key_inventory
ORDER BY key_name;

SELECT *
FROM get_key_lifecycle(
    (
        SELECT key_id
        FROM cryptographic_keys
        WHERE key_name = 'payment-data-key'
    )
);

SELECT *
FROM secret_encryption_inventory;

-- ============================================================
-- 22. ACCESS VALIDATION
-- ============================================================

SELECT
    p.principal_name,
    k.key_name,
    can_access_key(
        p.principal_id,
        k.key_id,
        'ENCRYPT'
    ) AS encryption_allowed,
    can_access_key(
        p.principal_id,
        k.key_id,
        'DECRYPT'
    ) AS decryption_allowed
FROM principals p
CROSS JOIN cryptographic_keys k
WHERE k.key_name = 'payment-data-key';

-- ============================================================
-- 23. AGGREGATION AND REPORTING
-- ============================================================

SELECT
    status,
    COUNT(*) AS version_count
FROM key_versions
GROUP BY status
ORDER BY status;

SELECT
    p.provider_name,
    COUNT(k.key_id) AS managed_keys,
    COUNT(v.key_version_id) AS total_versions,
    COUNT(v.key_version_id)
        FILTER (
            WHERE v.status = 'ACTIVE'
        ) AS active_versions
FROM key_providers p
LEFT JOIN cryptographic_keys k
    ON k.provider_id = p.provider_id
LEFT JOIN key_versions v
    ON v.key_id = k.key_id
GROUP BY p.provider_name
ORDER BY managed_keys DESC;

SELECT *
FROM expiring_key_report;

SELECT *
FROM rotation_approval_report;

-- ============================================================
-- 24. CTE: KEY ROTATION ELIGIBILITY
-- ============================================================

WITH active_versions AS (
    SELECT
        k.key_id,
        k.key_name,
        v.key_version_id,
        v.expires_at,
        k.rotation_interval_days
    FROM cryptographic_keys k
    JOIN key_versions v
        ON v.key_id = k.key_id
    WHERE v.status = 'ACTIVE'
),
eligibility AS (
    SELECT
        *,
        CASE
            WHEN expires_at <= NOW()
                THEN 'EXPIRED'
            WHEN expires_at <= NOW() + INTERVAL '15 days'
                THEN 'ROTATION_REQUIRED'
            WHEN expires_at <= NOW() + INTERVAL '30 days'
                THEN 'ROTATION_WARNING'
            ELSE 'HEALTHY'
        END AS lifecycle_decision
    FROM active_versions
)
SELECT *
FROM eligibility
ORDER BY expires_at;

-- ============================================================
-- 25. SAMPLE FAILURE CASES
-- These are deliberately invalid statements.
-- Execute individually to inspect the constraint failures.
-- ============================================================

-- Invalid key size:
-- INSERT INTO cryptographic_keys (
--     key_name, purpose, algorithm, key_size_bits,
--     provider_id, created_by
-- )
-- VALUES (
--     'invalid-key', 'ENCRYPTION', 'AES', 64, 1, 1
-- );

-- Duplicate active version:
-- INSERT INTO key_versions (
--     key_id, version_number, status,
--     provider_reference, expires_at
-- )
-- SELECT
--     key_id, 2, 'ACTIVE',
--     'INVALID-DUPLICATE-ACTIVE',
--     NOW() + INTERVAL '90 days'
-- FROM cryptographic_keys
-- WHERE key_name = 'payment-data-key';

-- Invalid operation:
-- SELECT can_access_key(1, gen_random_uuid(), 'DELETE');

-- ============================================================
-- 26. DATABASE SECURITY
--
-- Suggested production grants:
-- Separate schema ownership from application access.
-- Applications should not own tables or procedures.
-- Restrict direct table updates.
-- Use a dedicated connection role for each service.
-- Enable TLS and database encryption at rest.
-- Keep key material exclusively in KMS/HSM.
-- Audit privileged operations externally as well.
-- ============================================================

-- Example role setup:
--
-- CREATE ROLE key_management_reader NOLOGIN;
-- CREATE ROLE key_management_operator NOLOGIN;
--
-- GRANT USAGE ON SCHEMA key_management
-- TO key_management_reader, key_management_operator;
--
-- GRANT SELECT ON ALL TABLES IN SCHEMA key_management
-- TO key_management_reader;
--
-- GRANT SELECT, INSERT ON key_audit_events
-- TO key_management_operator;
--
-- GRANT EXECUTE ON PROCEDURE
-- key_management.schedule_expiring_keys()
-- TO key_management_operator;
--
-- Do not grant unrestricted UPDATE or DELETE
-- on cryptographic_keys or key_versions.
--
-- Production ownership, SECURITY DEFINER functions,
-- search_path hardening and RLS must be configured
-- according to the deployment's privilege model.

RESET search_path;
