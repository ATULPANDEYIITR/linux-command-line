-- ============================================================
-- AUTHENTICATION AND AUTHORIZATION
-- PostgreSQL 15+
--
-- Domain:
-- Users, password credentials, MFA, sessions, OAuth clients,
-- authorization codes, access tokens, RBAC and audit events.
--
-- Password hashes and cryptographic secrets are generated
-- outside PostgreSQL using approved cryptographic libraries.
--
-- Never store plaintext passwords, OTP values, or bearer tokens.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS identity;

SET search_path TO identity, public;

-- ============================================================
-- ENUMERATIONS
-- ============================================================

CREATE TYPE account_status AS ENUM (
    'active',
    'locked',
    'disabled'
);

CREATE TYPE session_status AS ENUM (
    'active',
    'revoked',
    'expired'
);

CREATE TYPE mfa_method AS ENUM (
    'totp',
    'webauthn'
);

CREATE TYPE token_status AS ENUM (
    'active',
    'revoked',
    'expired'
);

CREATE TYPE oauth_code_status AS ENUM (
    'issued',
    'consumed',
    'expired',
    'revoked'
);

CREATE TYPE audit_result AS ENUM (
    'success',
    'failure',
    'denied'
);

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    username VARCHAR(80) NOT NULL UNIQUE,

    email VARCHAR(255) NOT NULL UNIQUE,

    status account_status NOT NULL DEFAULT 'active',

    failed_login_attempts INTEGER NOT NULL DEFAULT 0,

    locked_until TIMESTAMPTZ,

    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    password_expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_username
        CHECK (username ~ '^[A-Za-z0-9_.-]{3,80}$'),

    CONSTRAINT valid_email
        CHECK (POSITION('@' IN email) > 1),

    CONSTRAINT valid_failed_attempts
        CHECK (failed_login_attempts >= 0)
);

-- ============================================================
-- PASSWORD CREDENTIALS
-- ============================================================

CREATE TABLE password_credentials (
    user_id UUID PRIMARY KEY
        REFERENCES users(user_id) ON DELETE CASCADE,

    password_hash TEXT NOT NULL,

    algorithm VARCHAR(30) NOT NULL,

    salt BYTEA NOT NULL,

    iterations INTEGER,

    memory_cost INTEGER,

    last_rotated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT supported_algorithm
        CHECK (algorithm IN ('argon2id', 'scrypt', 'pbkdf2')),

    CONSTRAINT valid_password_hash
        CHECK (LENGTH(password_hash) >= 32),

    CONSTRAINT valid_salt
        CHECK (OCTET_LENGTH(salt) >= 16),

    CONSTRAINT valid_iterations
        CHECK (iterations IS NULL OR iterations > 0),

    CONSTRAINT valid_memory_cost
        CHECK (memory_cost IS NULL OR memory_cost > 0)
);

-- ============================================================
-- ROLES AND PERMISSIONS
-- ============================================================

CREATE TABLE roles (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    role_name VARCHAR(50) NOT NULL UNIQUE,

    description TEXT
);

CREATE TABLE permissions (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    permission_name VARCHAR(100) NOT NULL UNIQUE,

    description TEXT
);

CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL
        REFERENCES roles(role_id) ON DELETE CASCADE,

    permission_id BIGINT NOT NULL
        REFERENCES permissions(permission_id) ON DELETE CASCADE,

    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,

    role_id BIGINT NOT NULL
        REFERENCES roles(role_id) ON DELETE RESTRICT,

    assigned_by UUID
        REFERENCES users(user_id) ON DELETE SET NULL,

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, role_id)
);

-- ============================================================
-- MFA FACTORS
-- ============================================================

CREATE TABLE mfa_factors (
    factor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,

    method mfa_method NOT NULL,

    encrypted_secret BYTEA,

    credential_identifier TEXT,

    enabled BOOLEAN NOT NULL DEFAULT FALSE,

    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_used_at TIMESTAMPTZ,

    CONSTRAINT mfa_configuration
        CHECK (
            (
                method = 'totp'
                AND encrypted_secret IS NOT NULL
                AND credential_identifier IS NULL
            )
            OR
            (
                method = 'webauthn'
                AND credential_identifier IS NOT NULL
            )
        )
);

CREATE INDEX idx_mfa_user_enabled
ON mfa_factors(user_id, enabled);

-- Tracks the last accepted TOTP time-step to prevent reuse.
CREATE TABLE mfa_replay_protection (
    factor_id UUID PRIMARY KEY
        REFERENCES mfa_factors(factor_id) ON DELETE CASCADE,

    last_accepted_counter BIGINT NOT NULL DEFAULT -1,

    CONSTRAINT valid_counter
        CHECK (last_accepted_counter >= -1)
);

-- ============================================================
-- AUTHENTICATION SESSIONS
-- ============================================================

CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,

    session_token_hash BYTEA NOT NULL UNIQUE,

    status session_status NOT NULL DEFAULT 'active',

    ip_address INET,

    user_agent TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    revoked_at TIMESTAMPTZ,

    CONSTRAINT valid_session_period
        CHECK (expires_at > created_at)
);

CREATE INDEX idx_sessions_user_status
ON sessions(user_id, status);

CREATE INDEX idx_sessions_expiry
ON sessions(expires_at)
WHERE status = 'active';

-- ============================================================
-- OAUTH CLIENTS
-- ============================================================

CREATE TABLE oauth_clients (
    client_id VARCHAR(100) PRIMARY KEY,

    client_name VARCHAR(150) NOT NULL,

    client_type VARCHAR(20) NOT NULL,

    confidential BOOLEAN NOT NULL DEFAULT FALSE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_client_type
        CHECK (client_type IN ('web', 'native', 'service')),

    CONSTRAINT valid_confidential_client
        CHECK (
            NOT confidential OR client_type IN ('web', 'service')
        )
);

CREATE TABLE oauth_redirect_uris (
    redirect_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    client_id VARCHAR(100) NOT NULL
        REFERENCES oauth_clients(client_id) ON DELETE CASCADE,

    redirect_uri TEXT NOT NULL,

    UNIQUE (client_id, redirect_uri),

    CONSTRAINT secure_redirect_uri
        CHECK (redirect_uri ~ '^https://')
);

CREATE TABLE oauth_client_scopes (
    client_id VARCHAR(100) NOT NULL
        REFERENCES oauth_clients(client_id) ON DELETE CASCADE,

    scope VARCHAR(100) NOT NULL,

    PRIMARY KEY (client_id, scope)
);

-- ============================================================
-- OAUTH AUTHORIZATION CODES
-- ============================================================

CREATE TABLE oauth_authorization_codes (
    code_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code_hash BYTEA NOT NULL UNIQUE,

    client_id VARCHAR(100) NOT NULL
        REFERENCES oauth_clients(client_id) ON DELETE CASCADE,

    user_id UUID NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,

    redirect_uri TEXT NOT NULL,

    state_hash BYTEA NOT NULL,

    code_challenge VARCHAR(128) NOT NULL,

    code_challenge_method VARCHAR(10) NOT NULL DEFAULT 'S256',

    status oauth_code_status NOT NULL DEFAULT 'issued',

    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    consumed_at TIMESTAMPTZ,

    CONSTRAINT valid_code_expiry
        CHECK (expires_at > issued_at),

    CONSTRAINT supported_pkce_method
        CHECK (code_challenge_method = 'S256')
);

CREATE INDEX idx_oauth_codes_expiry
ON oauth_authorization_codes(expires_at)
WHERE status = 'issued';

-- ============================================================
-- OAUTH AUTHORIZATION CODE SCOPES
-- ============================================================

CREATE TABLE oauth_authorization_code_scopes (
    code_id UUID NOT NULL
        REFERENCES oauth_authorization_codes(code_id)
        ON DELETE CASCADE,

    scope VARCHAR(100) NOT NULL,

    PRIMARY KEY (code_id, scope)
);

-- ============================================================
-- ACCESS TOKENS
-- ============================================================

CREATE TABLE access_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    token_hash BYTEA NOT NULL UNIQUE,

    user_id UUID NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,

    client_id VARCHAR(100)
        REFERENCES oauth_clients(client_id) ON DELETE SET NULL,

    status token_status NOT NULL DEFAULT 'active',

    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    revoked_at TIMESTAMPTZ,

    CONSTRAINT valid_token_period
        CHECK (expires_at > issued_at)
);

CREATE INDEX idx_tokens_user_status
ON access_tokens(user_id, status);

CREATE INDEX idx_tokens_expiry
ON access_tokens(expires_at)
WHERE status = 'active';

CREATE TABLE access_token_scopes (
    token_id UUID NOT NULL
        REFERENCES access_tokens(token_id) ON DELETE CASCADE,

    scope VARCHAR(100) NOT NULL,

    PRIMARY KEY (token_id, scope)
);

-- ============================================================
-- SECURITY AUDIT LOG
-- ============================================================

CREATE TABLE authentication_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id UUID
        REFERENCES users(user_id) ON DELETE SET NULL,

    event_type VARCHAR(80) NOT NULL,

    result audit_result NOT NULL,

    ip_address INET,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user_time
ON authentication_audit(user_id, created_at DESC);

CREATE INDEX idx_audit_failed
ON authentication_audit(created_at DESC)
WHERE result IN ('failure', 'denied');

CREATE INDEX idx_audit_details
ON authentication_audit USING GIN(details);

-- ============================================================
-- ACCOUNT UPDATE TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION update_modified_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_modified_timestamp();

-- ============================================================
-- SECURITY AUDIT FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION log_authentication_event(
    p_user_id UUID,
    p_event_type VARCHAR,
    p_result audit_result,
    p_details JSONB DEFAULT '{}'::jsonb
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    generated_id BIGINT;
BEGIN
    INSERT INTO authentication_audit (
        user_id,
        event_type,
        result,
        details
    )
    VALUES (
        p_user_id,
        p_event_type,
        p_result,
        COALESCE(p_details, '{}'::jsonb)
    )
    RETURNING audit_id INTO generated_id;

    RETURN generated_id;
END;
$$;

-- ============================================================
-- ACCOUNT LOCKOUT PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE record_failed_login(
    p_user_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    current_attempts INTEGER;
BEGIN
    UPDATE users
    SET
        failed_login_attempts = failed_login_attempts + 1,
        status = CASE
            WHEN failed_login_attempts + 1 >= 5
                THEN 'locked'::account_status
            ELSE status
        END,
        locked_until = CASE
            WHEN failed_login_attempts + 1 >= 5
                THEN NOW() + INTERVAL '5 minutes'
            ELSE locked_until
        END
    WHERE user_id = p_user_id
      AND status = 'active'
    RETURNING failed_login_attempts INTO current_attempts;

    PERFORM log_authentication_event(
        p_user_id,
        'LOGIN_FAILURE',
        'failure',
        jsonb_build_object(
            'failed_attempts',
            current_attempts
        )
    );
END;
$$;

-- ============================================================
-- SUCCESSFUL LOGIN PROCEDURE
-- ============================================================

CREATE OR REPLACE FUNCTION record_successful_login(
    p_user_id UUID,
    p_session_hash BYTEA,
    p_expiry TIMESTAMPTZ
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    generated_session UUID;
BEGIN
    IF p_expiry <= NOW() THEN
        RAISE EXCEPTION 'Session expiry must be in the future';
    END IF;

    UPDATE users
    SET
        failed_login_attempts = 0,
        status = 'active',
        locked_until = NULL
    WHERE user_id = p_user_id
      AND status <> 'disabled';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User unavailable';
    END IF;

    INSERT INTO sessions (
        user_id,
        session_token_hash,
        expires_at
    )
    VALUES (
        p_user_id,
        p_session_hash,
        p_expiry
    )
    RETURNING session_id INTO generated_session;

    PERFORM log_authentication_event(
        p_user_id,
        'LOGIN_SUCCESS',
        'success'
    );

    RETURN generated_session;
END;
$$;

-- ============================================================
-- SESSION REVOCATION
-- ============================================================

CREATE OR REPLACE FUNCTION revoke_user_session(
    p_session_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    affected INTEGER;
BEGIN
    UPDATE sessions
    SET
        status = 'revoked',
        revoked_at = NOW()
    WHERE session_id = p_session_id
      AND status = 'active';

    GET DIAGNOSTICS affected = ROW_COUNT;

    RETURN affected = 1;
END;
$$;

-- ============================================================
-- ROLE-BASED PERMISSION EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION has_permission(
    p_user_id UUID,
    p_permission VARCHAR
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM users u
        JOIN user_roles ur
            ON ur.user_id = u.user_id
        JOIN role_permissions rp
            ON rp.role_id = ur.role_id
        JOIN permissions p
            ON p.permission_id = rp.permission_id
        WHERE u.user_id = p_user_id
          AND u.status = 'active'
          AND p.permission_name = p_permission
    );
$$;

-- ============================================================
-- TOKEN SCOPE EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION token_has_scope(
    p_token_id UUID,
    p_scope VARCHAR
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM access_tokens t
        JOIN access_token_scopes s
            ON s.token_id = t.token_id
        JOIN users u
            ON u.user_id = t.user_id
        WHERE t.token_id = p_token_id
          AND t.status = 'active'
          AND t.expires_at > NOW()
          AND u.status = 'active'
          AND s.scope = p_scope
    );
$$;

-- ============================================================
-- FINAL AUTHORIZATION DECISION
-- ============================================================

CREATE OR REPLACE FUNCTION authorize_request(
    p_user_id UUID,
    p_token_id UUID,
    p_permission VARCHAR
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT
        has_permission(p_user_id, p_permission)
        AND EXISTS (
            SELECT 1
            FROM access_tokens t
            WHERE t.token_id = p_token_id
              AND t.user_id = p_user_id
              AND t.status = 'active'
              AND t.expires_at > NOW()
        )
        AND token_has_scope(p_token_id, p_permission);
$$;

-- ============================================================
-- OAUTH AUTHORIZATION CODE CONSUMPTION
--
-- PKCE cryptographic verification must happen in the trusted
-- application or OAuth authorization server before this call.
-- This transaction function enforces single-use consumption.
-- ============================================================

CREATE OR REPLACE FUNCTION consume_authorization_code(
    p_code_hash BYTEA,
    p_client_id VARCHAR,
    p_redirect_uri TEXT
)
RETURNS TABLE (
    authorized_user_id UUID,
    authorized_code_id UUID
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    UPDATE oauth_authorization_codes c
    SET
        status = 'consumed',
        consumed_at = NOW()
    WHERE c.code_hash = p_code_hash
      AND c.client_id = p_client_id
      AND c.redirect_uri = p_redirect_uri
      AND c.status = 'issued'
      AND c.expires_at > NOW()
    RETURNING c.user_id, c.code_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Invalid, expired, or already consumed authorization code';
    END IF;
END;
$$;

-- ============================================================
-- ELIGIBILITY VIEW
-- ============================================================

CREATE OR REPLACE VIEW active_user_access AS
SELECT
    u.user_id,
    u.username,
    u.email,
    u.status,
    r.role_name,
    p.permission_name
FROM users u
JOIN user_roles ur
    ON ur.user_id = u.user_id
JOIN roles r
    ON r.role_id = ur.role_id
JOIN role_permissions rp
    ON rp.role_id = r.role_id
JOIN permissions p
    ON p.permission_id = rp.permission_id
WHERE u.status = 'active';

-- ============================================================
-- ACTIVE SESSION VIEW
-- ============================================================

CREATE OR REPLACE VIEW valid_sessions AS
SELECT
    s.session_id,
    s.user_id,
    u.username,
    s.created_at,
    s.expires_at,
    s.last_activity_at
FROM sessions s
JOIN users u
    ON u.user_id = s.user_id
WHERE s.status = 'active'
  AND s.expires_at > NOW()
  AND u.status = 'active';

-- ============================================================
-- SAMPLE ROLES
-- ============================================================

INSERT INTO roles(role_name, description)
VALUES
    ('admin', 'Full administrative access'),
    ('manager', 'User and reporting management'),
    ('analyst', 'Reporting and analytical access'),
    ('viewer', 'Read-only reporting access');

-- ============================================================
-- SAMPLE PERMISSIONS
-- ============================================================

INSERT INTO permissions(permission_name, description)
VALUES
    ('users.read', 'Read user accounts'),
    ('users.create', 'Create user accounts'),
    ('users.update', 'Update user accounts'),
    ('users.delete', 'Delete user accounts'),
    ('reports.read', 'Read reports'),
    ('reports.export', 'Export reports'),
    ('settings.manage', 'Manage application settings');

-- ============================================================
-- ROLE PERMISSION MAPPING
-- ============================================================

INSERT INTO role_permissions(role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
CROSS JOIN permissions p
WHERE
    r.role_name = 'admin'
    OR (
        r.role_name = 'manager'
        AND p.permission_name IN (
            'users.read',
            'users.update',
            'reports.read',
            'reports.export'
        )
    )
    OR (
        r.role_name = 'analyst'
        AND p.permission_name IN (
            'reports.read',
            'reports.export'
        )
    )
    OR (
        r.role_name = 'viewer'
        AND p.permission_name = 'reports.read'
    );

-- ============================================================
-- SAMPLE USERS
-- ============================================================

INSERT INTO users (
    user_id,
    username,
    email,
    status,
    failed_login_attempts
)
VALUES
(
    '10000000-0000-0000-0000-000000000001',
    'admin_user',
    'admin@example.com',
    'active',
    0
),
(
    '10000000-0000-0000-0000-000000000002',
    'analyst_user',
    'analyst@example.com',
    'active',
    0
),
(
    '10000000-0000-0000-0000-000000000003',
    'viewer_user',
    'viewer@example.com',
    'active',
    0
),
(
    '10000000-0000-0000-0000-000000000004',
    'locked_user',
    'locked@example.com',
    'locked',
    5
);

-- Sample hashes are illustrative encoded verifier values.
-- They are not valid production password hashes.
INSERT INTO password_credentials (
    user_id,
    password_hash,
    algorithm,
    salt,
    iterations,
    memory_cost
)
SELECT
    user_id,
    '$argon2id$sample_encoded_verifier_for_demonstration_only',
    'argon2id',
    decode('00112233445566778899aabbccddeeff', 'hex'),
    NULL,
    65536
FROM users;

-- ============================================================
-- USER ROLE ASSIGNMENTS
-- ============================================================

INSERT INTO user_roles(user_id, role_id)
SELECT u.user_id, r.role_id
FROM (
    VALUES
    (
        '10000000-0000-0000-0000-000000000001'::UUID,
        'admin'
    ),
    (
        '10000000-0000-0000-0000-000000000002'::UUID,
        'analyst'
    ),
    (
        '10000000-0000-0000-0000-000000000003'::UUID,
        'viewer'
    ),
    (
        '10000000-0000-0000-0000-000000000004'::UUID,
        'manager'
    )
) AS assignment(user_id, role_name)
JOIN users u
    ON u.user_id = assignment.user_id
JOIN roles r
    ON r.role_name = assignment.role_name;

-- ============================================================
-- SAMPLE MFA CONFIGURATION
-- ============================================================

INSERT INTO mfa_factors (
    user_id,
    method,
    encrypted_secret,
    enabled,
    verified_at
)
VALUES (
    '10000000-0000-0000-0000-000000000001',
    'totp',
    decode('aabbccddeeff00112233445566778899', 'hex'),
    TRUE,
    NOW()
);

-- ============================================================
-- SAMPLE OAUTH CLIENT
-- ============================================================

INSERT INTO oauth_clients (
    client_id,
    client_name,
    client_type,
    confidential,
    enabled
)
VALUES (
    'reporting-app',
    'Enterprise Reporting Application',
    'web',
    TRUE,
    TRUE
);

INSERT INTO oauth_redirect_uris(client_id, redirect_uri)
VALUES (
    'reporting-app',
    'https://client.example.com/callback'
);

INSERT INTO oauth_client_scopes(client_id, scope)
VALUES
    ('reporting-app', 'reports.read'),
    ('reporting-app', 'reports.export');

-- ============================================================
-- SAMPLE ACCESS TOKEN
--
-- token_hash is a hash of the opaque bearer token.
-- The bearer token itself is never stored.
-- ============================================================

INSERT INTO access_tokens (
    token_id,
    token_hash,
    user_id,
    client_id,
    status,
    expires_at
)
VALUES (
    '20000000-0000-0000-0000-000000000001',
    digest('demo-access-token', 'sha256'),
    '10000000-0000-0000-0000-000000000002',
    'reporting-app',
    'active',
    NOW() + INTERVAL '15 minutes'
);

INSERT INTO access_token_scopes(token_id, scope)
VALUES (
    '20000000-0000-0000-0000-000000000001',
    'reports.read'
);

-- ============================================================
-- SAMPLE SESSION
-- ============================================================

INSERT INTO sessions (
    session_id,
    user_id,
    session_token_hash,
    status,
    expires_at
)
VALUES (
    '30000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    digest('demo-session-token', 'sha256'),
    'active',
    NOW() + INTERVAL '1 hour'
);

-- ============================================================
-- SAMPLE AUDIT RECORDS
-- ============================================================

INSERT INTO authentication_audit (
    user_id,
    event_type,
    result,
    details
)
VALUES
(
    '10000000-0000-0000-0000-000000000001',
    'LOGIN_SUCCESS',
    'success',
    '{"mfa": true}'::jsonb
),
(
    '10000000-0000-0000-0000-000000000002',
    'LOGIN_SUCCESS',
    'success',
    '{"mfa": false}'::jsonb
),
(
    '10000000-0000-0000-0000-000000000004',
    'LOGIN_FAILURE',
    'failure',
    '{"reason": "account_locked"}'::jsonb
);

COMMIT;

-- ============================================================
-- QUERY 1: RETRIEVE USER ROLES AND PERMISSIONS
-- ============================================================

SELECT
    username,
    role_name,
    permission_name
FROM active_user_access
ORDER BY username, permission_name;

-- ============================================================
-- QUERY 2: EVALUATE ROLE AUTHORIZATION
-- ============================================================

SELECT
    u.username,
    p.permission_name,
    has_permission(
        u.user_id,
        p.permission_name
    ) AS permitted
FROM users u
CROSS JOIN permissions p
WHERE u.username IN (
    'admin_user',
    'analyst_user',
    'viewer_user'
)
ORDER BY u.username, p.permission_name;

-- ============================================================
-- QUERY 3: EVALUATE TOKEN AUTHORIZATION
-- ============================================================

SELECT
    u.username,
    t.token_id,
    s.scope,
    token_has_scope(t.token_id, s.scope) AS scope_valid
FROM access_tokens t
JOIN users u
    ON u.user_id = t.user_id
JOIN access_token_scopes s
    ON s.token_id = t.token_id;

-- ============================================================
-- QUERY 4: COMPLETE AUTHORIZATION DECISION
-- ============================================================

SELECT
    u.username,
    authorize_request(
        u.user_id,
        t.token_id,
        'reports.read'
    ) AS can_read_reports
FROM users u
JOIN access_tokens t
    ON t.user_id = u.user_id
WHERE u.username = 'analyst_user';

-- ============================================================
-- QUERY 5: ACCOUNT SECURITY REPORT
-- ============================================================

SELECT
    status,
    COUNT(*) AS account_count,
    SUM(failed_login_attempts) AS total_failed_attempts
FROM users
GROUP BY status
ORDER BY status;

-- ============================================================
-- QUERY 6: MFA ENROLLMENT REPORT
-- ============================================================

SELECT
    u.username,
    COUNT(m.factor_id) AS total_factors,
    COUNT(m.factor_id) FILTER (
        WHERE m.enabled
    ) AS enabled_factors
FROM users u
LEFT JOIN mfa_factors m
    ON m.user_id = u.user_id
GROUP BY u.user_id, u.username
ORDER BY u.username;

-- ============================================================
-- QUERY 7: ACTIVE AND EXPIRED SESSIONS
-- ============================================================

SELECT
    session_id,
    username,
    created_at,
    expires_at
FROM valid_sessions
ORDER BY expires_at;

-- ============================================================
-- QUERY 8: TOKEN EXPIRATION REPORT
-- ============================================================

SELECT
    u.username,
    t.token_id,
    t.status,
    t.issued_at,
    t.expires_at,
    EXTRACT(
        EPOCH FROM (t.expires_at - NOW())
    ) AS remaining_seconds
FROM access_tokens t
JOIN users u
    ON u.user_id = t.user_id
ORDER BY t.expires_at;

-- ============================================================
-- QUERY 9: FAILED AUTHENTICATION REPORT
-- ============================================================

SELECT
    u.username,
    COUNT(a.audit_id) AS failed_events,
    MAX(a.created_at) AS latest_failure
FROM authentication_audit a
LEFT JOIN users u
    ON u.user_id = a.user_id
WHERE a.result = 'failure'
GROUP BY u.username
ORDER BY failed_events DESC;

-- ============================================================
-- QUERY 10: OAUTH CLIENT SCOPE ELIGIBILITY
-- ============================================================

SELECT
    c.client_id,
    c.client_name,
    s.scope,
    c.enabled
FROM oauth_clients c
LEFT JOIN oauth_client_scopes s
    ON s.client_id = c.client_id
ORDER BY c.client_id, s.scope;

-- ============================================================
-- WORKFLOW: FAILED LOGIN WITH TRANSACTION
-- ============================================================

BEGIN;

CALL record_failed_login(
    '10000000-0000-0000-0000-000000000002'
);

COMMIT;

-- ============================================================
-- WORKFLOW: CREATE A SESSION AFTER EXTERNAL AUTHENTICATION
--
-- The application must verify the password and MFA before
-- calling this function. Only a hash of the session token is stored.
-- ============================================================

BEGIN;

SELECT record_successful_login(
    '10000000-0000-0000-0000-000000000002',
    digest('new-random-session-token', 'sha256'),
    NOW() + INTERVAL '1 hour'
);

COMMIT;

-- ============================================================
-- WORKFLOW: REVOKE AN ACTIVE TOKEN
-- ============================================================

BEGIN;

UPDATE access_tokens
SET
    status = 'revoked',
    revoked_at = NOW()
WHERE token_id = '20000000-0000-0000-0000-000000000001'
  AND status = 'active';

INSERT INTO authentication_audit (
    user_id,
    event_type,
    result,
    details
)
VALUES (
    '10000000-0000-0000-0000-000000000002',
    'TOKEN_REVOKED',
    'success',
    '{"reason": "administrative_revocation"}'::jsonb
);

COMMIT;

-- ============================================================
-- WORKFLOW: REVOKE EXPIRED SESSIONS AND TOKENS
-- ============================================================

BEGIN;

UPDATE sessions
SET
    status = 'expired'
WHERE status = 'active'
  AND expires_at <= NOW();

UPDATE access_tokens
SET
    status = 'expired'
WHERE status = 'active'
  AND expires_at <= NOW();

UPDATE oauth_authorization_codes
SET
    status = 'expired'
WHERE status = 'issued'
  AND expires_at <= NOW();

COMMIT;

-- ============================================================
-- VALIDATION: ACCOUNTS WITHOUT ROLES
-- ============================================================

SELECT
    u.user_id,
    u.username
FROM users u
LEFT JOIN user_roles ur
    ON ur.user_id = u.user_id
WHERE ur.user_id IS NULL;

-- ============================================================
-- VALIDATION: USERS WITHOUT PASSWORD CREDENTIALS
-- ============================================================

SELECT
    u.user_id,
    u.username
FROM users u
LEFT JOIN password_credentials pc
    ON pc.user_id = u.user_id
WHERE pc.user_id IS NULL;

-- ============================================================
-- VALIDATION: INVALID ROLE/PERMISSION CONFIGURATION
-- ============================================================

SELECT
    r.role_name,
    COUNT(rp.permission_id) AS permission_count
FROM roles r
LEFT JOIN role_permissions rp
    ON rp.role_id = r.role_id
GROUP BY r.role_id, r.role_name
ORDER BY r.role_name;

-- ============================================================
-- OPERATIONAL NOTES
--
-- 1. Execute password verification outside SQL.
-- 2. Encrypt TOTP secrets with managed encryption keys.
-- 3. Verify TOTP replay counters atomically.
-- 4. Verify PKCE S256 before consuming authorization codes.
-- 5. Generate cryptographically random session identifiers.
-- 6. Store only token hashes for opaque bearer tokens.
-- 7. Validate issuer, audience, signature and expiry for JWTs.
-- 8. Enforce least privilege and deny by default.
-- 9. Restrict direct table access through database roles.
-- 10. Partition large audit tables by timestamp.
-- ============================================================
