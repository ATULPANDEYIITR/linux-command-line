/*
 * CLOUD SECURITY GOVERNANCE DATABASE
 *
 * PostgreSQL 15+
 *
 * Relational model for:
 * - Cloud accounts and identities
 * - IAM roles and permissions
 * - Cloud resources
 * - Network isolation rules
 * - Encryption configurations
 * - Audit logging
 * - Security monitoring
 * - Security incidents
 * - Governance policies
 * - Access eligibility
 *
 * The script is designed for an isolated learning database.
 */

BEGIN;

CREATE SCHEMA IF NOT EXISTS cloud_security;

SET search_path TO cloud_security, public;

CREATE TYPE resource_state AS ENUM (
    'ACTIVE',
    'QUARANTINED',
    'DISABLED'
);

CREATE TYPE access_decision AS ENUM (
    'ALLOW',
    'DENY'
);

CREATE TYPE review_severity AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE network_direction AS ENUM (
    'INGRESS',
    'EGRESS'
);

CREATE TYPE incident_state AS ENUM (
    'OPEN',
    'INVESTIGATING',
    'CONTAINED',
    'RESOLVED'
);

CREATE TABLE cloud_accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_name VARCHAR(150) NOT NULL UNIQUE,
    cloud_provider VARCHAR(40) NOT NULL,
    region VARCHAR(80) NOT NULL,
    environment VARCHAR(30) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_environment CHECK (
        environment IN (
            'DEVELOPMENT',
            'TESTING',
            'STAGING',
            'PRODUCTION'
        )
    )
);

CREATE TABLE identities (
    identity_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES cloud_accounts(account_id),
    username VARCHAR(120) NOT NULL,
    identity_type VARCHAR(30) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    last_authenticated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (account_id, username),

    CHECK (
        identity_type IN (
            'HUMAN',
            'SERVICE',
            'APPLICATION'
        )
    )
);

CREATE TABLE iam_roles (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES cloud_accounts(account_id),
    role_name VARCHAR(100) NOT NULL,
    description TEXT,
    privileged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (account_id, role_name)
);

CREATE TABLE iam_permissions (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action VARCHAR(150) NOT NULL,
    resource_pattern VARCHAR(200) NOT NULL,
    effect VARCHAR(10) NOT NULL DEFAULT 'ALLOW',

    CHECK (effect IN ('ALLOW', 'DENY'))
);

CREATE TABLE identity_roles (
    identity_id BIGINT NOT NULL REFERENCES identities(identity_id),
    role_id BIGINT NOT NULL REFERENCES iam_roles(role_id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by BIGINT REFERENCES identities(identity_id),

    PRIMARY KEY (identity_id, role_id)
);

CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL REFERENCES iam_roles(role_id),
    permission_id BIGINT NOT NULL REFERENCES iam_permissions(permission_id),

    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE cloud_resources (
    resource_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES cloud_accounts(account_id),
    resource_name VARCHAR(150) NOT NULL,
    resource_type VARCHAR(60) NOT NULL,
    owner_identity_id BIGINT REFERENCES identities(identity_id),
    public_access BOOLEAN NOT NULL DEFAULT FALSE,
    state resource_state NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (account_id, resource_name)
);

CREATE TABLE encryption_configurations (
    encryption_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT NOT NULL UNIQUE
        REFERENCES cloud_resources(resource_id),
    at_rest_enabled BOOLEAN NOT NULL,
    in_transit_enabled BOOLEAN NOT NULL,
    algorithm VARCHAR(40) NOT NULL,
    key_reference VARCHAR(200) NOT NULL,
    key_rotation_days INTEGER NOT NULL DEFAULT 90,
    last_rotated_at TIMESTAMPTZ,
    key_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CHECK (key_rotation_days BETWEEN 1 AND 365),
    CHECK (
        algorithm IN (
            'AES-256',
            'AES-128',
            'AES-256-GCM'
        )
    )
);

CREATE TABLE network_security_rules (
    rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT NOT NULL REFERENCES cloud_resources(resource_id),
    direction network_direction NOT NULL,
    protocol VARCHAR(10) NOT NULL,
    port_start INTEGER NOT NULL,
    port_end INTEGER NOT NULL,
    cidr CIDR NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,

    CHECK (protocol IN ('TCP', 'UDP', 'ICMP')),
    CHECK (port_start BETWEEN 0 AND 65535),
    CHECK (port_end BETWEEN port_start AND 65535)
);

CREATE TABLE branch_security_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES cloud_accounts(account_id),
    policy_name VARCHAR(150) NOT NULL,
    minimum_mfa BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    public_access_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    maximum_key_age_days INTEGER NOT NULL DEFAULT 90,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE (account_id, policy_name),
    CHECK (maximum_key_age_days BETWEEN 1 AND 365)
);

CREATE TABLE audit_logs (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity_id BIGINT REFERENCES identities(identity_id),
    resource_id BIGINT REFERENCES cloud_resources(resource_id),
    action VARCHAR(150) NOT NULL,
    source_ip INET,
    decision access_decision NOT NULL,
    severity review_severity NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE security_incidents (
    incident_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity_id BIGINT REFERENCES identities(identity_id),
    resource_id BIGINT REFERENCES cloud_resources(resource_id),
    incident_type VARCHAR(100) NOT NULL,
    severity review_severity NOT NULL,
    state incident_state NOT NULL DEFAULT 'OPEN',
    description TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    CHECK (
        (state <> 'RESOLVED') OR resolved_at IS NOT NULL
    )
);

CREATE TABLE security_monitoring_rules (
    monitoring_rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_name VARCHAR(150) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    threshold_count INTEGER NOT NULL,
    time_window_minutes INTEGER NOT NULL,
    severity review_severity NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CHECK (threshold_count > 0),
    CHECK (time_window_minutes > 0)
);

-- Indexes support common security investigation queries.

CREATE INDEX idx_identity_account
ON identities(account_id, enabled);

CREATE INDEX idx_resource_account_state
ON cloud_resources(account_id, state);

CREATE INDEX idx_audit_identity_time
ON audit_logs(identity_id, event_time DESC);

CREATE INDEX idx_audit_resource_time
ON audit_logs(resource_id, event_time DESC);

CREATE INDEX idx_audit_denied
ON audit_logs(event_time DESC)
WHERE decision = 'DENY';

CREATE INDEX idx_audit_details
ON audit_logs USING GIN(details);

CREATE INDEX idx_incidents_state
ON security_incidents(state, severity, detected_at DESC);

CREATE INDEX idx_network_resource
ON network_security_rules(resource_id, direction)
WHERE enabled = TRUE;

CREATE INDEX idx_identity_roles_role
ON identity_roles(role_id);

-- Prevent changes to the primary identity and sequence of audit events.
-- Production audit immutability also requires database privileges,
-- external retention and independently controlled storage.

CREATE FUNCTION prevent_audit_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Audit records cannot be modified or deleted';
END;
$$;

CREATE TRIGGER audit_immutable
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_mutation();

-- Validate resource registration against encryption and exposure rules.

CREATE FUNCTION validate_resource_security()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    encryption_exists BOOLEAN;
    rest_enabled BOOLEAN;
    transit_enabled BOOLEAN;
BEGIN
    SELECT
        TRUE,
        at_rest_enabled,
        in_transit_enabled
    INTO
        encryption_exists,
        rest_enabled,
        transit_enabled
    FROM encryption_configurations
    WHERE resource_id = NEW.resource_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Encryption configuration required for resource %',
            NEW.resource_id;
    END IF;

    IF NOT rest_enabled OR NOT transit_enabled THEN
        RAISE EXCEPTION
            'At-rest and in-transit encryption are mandatory';
    END IF;

    IF NEW.public_access THEN
        RAISE EXCEPTION
            'Public resource access is prohibited by baseline policy';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER resource_security_validation
BEFORE INSERT OR UPDATE OF public_access ON cloud_resources
FOR EACH ROW
WHEN (NEW.public_access = TRUE)
EXECUTE FUNCTION validate_resource_security();

-- A separate trigger validates encryption configuration changes.

CREATE FUNCTION validate_encryption_configuration()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT NEW.at_rest_enabled OR NOT NEW.in_transit_enabled THEN
        RAISE EXCEPTION 'Both encryption controls must remain enabled';
    END IF;

    IF NOT NEW.key_enabled THEN
        RAISE EXCEPTION 'Encryption key must be enabled';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER encryption_validation
BEFORE INSERT OR UPDATE ON encryption_configurations
FOR EACH ROW
EXECUTE FUNCTION validate_encryption_configuration();

-- Resolve IAM wildcard patterns for a requested action and resource.
-- Explicit DENY takes precedence over any ALLOW.

CREATE FUNCTION evaluate_iam(
    p_identity_id BIGINT,
    p_action TEXT,
    p_resource_name TEXT
)
RETURNS access_decision
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    has_allow BOOLEAN;
    has_deny BOOLEAN;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM identities
        WHERE identity_id = p_identity_id
          AND enabled = TRUE
          AND mfa_enabled = TRUE
    ) THEN
        RETURN 'DENY';
    END IF;

    SELECT
        COALESCE(BOOL_OR(permission.effect = 'ALLOW'), FALSE),
        COALESCE(BOOL_OR(permission.effect = 'DENY'), FALSE)
    INTO has_allow, has_deny
    FROM identity_roles ir
    JOIN role_permissions rp
        ON rp.role_id = ir.role_id
    JOIN iam_permissions permission
        ON permission.permission_id = rp.permission_id
    WHERE ir.identity_id = p_identity_id
      AND (
          permission.action = '*'
          OR permission.action = p_action
      )
      AND (
          permission.resource_pattern = '*'
          OR permission.resource_pattern = p_resource_name
          OR (
              RIGHT(permission.resource_pattern, 1) = '*'
              AND LEFT(
                  p_resource_name,
                  LENGTH(permission.resource_pattern) - 1
              ) = LEFT(
                  permission.resource_pattern,
                  LENGTH(permission.resource_pattern) - 1
              )
          )
      );

    IF has_deny THEN
        RETURN 'DENY';
    END IF;

    IF has_allow THEN
        RETURN 'ALLOW';
    END IF;

    RETURN 'DENY';
END;
$$;

-- Network eligibility uses PostgreSQL's native CIDR operators.

CREATE FUNCTION evaluate_network(
    p_resource_id BIGINT,
    p_source_ip INET,
    p_port INTEGER,
    p_direction network_direction
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM network_security_rules
        WHERE resource_id = p_resource_id
          AND direction = p_direction
          AND enabled = TRUE
          AND p_source_ip <<= cidr
          AND (
              protocol = 'TCP'
              AND p_port BETWEEN port_start AND port_end
          )
    );
$$;

-- Central access eligibility service.
-- Both IAM and network conditions must pass.

CREATE FUNCTION check_access_eligibility(
    p_identity_id BIGINT,
    p_resource_id BIGINT,
    p_action TEXT,
    p_source_ip INET,
    p_port INTEGER
)
RETURNS access_decision
LANGUAGE plpgsql
AS $$
DECLARE
    resource_name TEXT;
    account_active BOOLEAN;
    resource_status resource_state;
    iam_result access_decision;
    network_result BOOLEAN;
BEGIN
    IF p_port NOT BETWEEN 1 AND 65535 THEN
        RAISE EXCEPTION 'Invalid port';
    END IF;

    SELECT
        resource.resource_name,
        resource.state,
        account.active
    INTO
        resource_name,
        resource_status,
        account_active
    FROM cloud_resources resource
    JOIN cloud_accounts account
        ON account.account_id = resource.account_id
    WHERE resource.resource_id = p_resource_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown resource';
    END IF;

    IF NOT account_active OR resource_status <> 'ACTIVE' THEN
        RETURN 'DENY';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM encryption_configurations
        WHERE resource_id = p_resource_id
          AND at_rest_enabled
          AND in_transit_enabled
          AND key_enabled
    ) THEN
        RETURN 'DENY';
    END IF;

    iam_result := evaluate_iam(
        p_identity_id,
        p_action,
        resource_name
    );

    network_result := evaluate_network(
        p_resource_id,
        p_source_ip,
        p_port,
        'INGRESS'
    );

    IF iam_result = 'ALLOW' AND network_result THEN
        RETURN 'ALLOW';
    END IF;

    RETURN 'DENY';
END;
$$;

-- Store a decision and its audit evidence in one transaction.

CREATE FUNCTION record_access_attempt(
    p_identity_id BIGINT,
    p_resource_id BIGINT,
    p_action TEXT,
    p_source_ip INET,
    p_port INTEGER
)
RETURNS access_decision
LANGUAGE plpgsql
AS $$
DECLARE
    result access_decision;
    severity_value review_severity;
BEGIN
    result := check_access_eligibility(
        p_identity_id,
        p_resource_id,
        p_action,
        p_source_ip,
        p_port
    );

    severity_value := CASE
        WHEN result = 'ALLOW' THEN 'LOW'::review_severity
        ELSE 'HIGH'::review_severity
    END;

    INSERT INTO audit_logs (
        identity_id,
        resource_id,
        action,
        source_ip,
        decision,
        severity,
        details
    )
    VALUES (
        p_identity_id,
        p_resource_id,
        p_action,
        p_source_ip,
        result,
        severity_value,
        jsonb_build_object(
            'port', p_port,
            'evaluation', 'IAM_AND_NETWORK'
        )
    );

    RETURN result;
END;
$$;

-- Aggregate failed access attempts by identity over a time window.

CREATE FUNCTION detect_repeated_denials(
    p_threshold INTEGER DEFAULT 3,
    p_window_minutes INTEGER DEFAULT 15
)
RETURNS TABLE (
    detected_identity BIGINT,
    denial_count BIGINT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        identity_id,
        COUNT(*)
    FROM audit_logs
    WHERE decision = 'DENY'
      AND event_time >=
          NOW() - make_interval(mins => p_window_minutes)
      AND identity_id IS NOT NULL
    GROUP BY identity_id
    HAVING COUNT(*) >= p_threshold;
$$;

-- Create incidents from repeated unauthorized access.

CREATE PROCEDURE process_security_alerts(
    p_threshold INTEGER DEFAULT 3,
    p_window_minutes INTEGER DEFAULT 15
)
LANGUAGE plpgsql
AS $$
DECLARE
    finding RECORD;
BEGIN
    IF p_threshold < 1 OR p_window_minutes < 1 THEN
        RAISE EXCEPTION 'Invalid alert configuration';
    END IF;

    FOR finding IN
        SELECT *
        FROM detect_repeated_denials(
            p_threshold,
            p_window_minutes
        )
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM security_incidents
            WHERE identity_id = finding.detected_identity
              AND incident_type = 'REPEATED_ACCESS_DENIAL'
              AND state IN ('OPEN', 'INVESTIGATING')
              AND detected_at >=
                  NOW() - make_interval(mins => p_window_minutes)
        ) THEN
            INSERT INTO security_incidents (
                identity_id,
                incident_type,
                severity,
                description
            )
            VALUES (
                finding.detected_identity,
                'REPEATED_ACCESS_DENIAL',
                'HIGH',
                format(
                    'Detected %s denied requests in the monitoring window',
                    finding.denial_count
                )
            );
        END IF;
    END LOOP;
END;
$$;

-- Security posture view.

CREATE VIEW security_posture AS
SELECT
    account.account_name,
    account.environment,
    resource.resource_id,
    resource.resource_name,
    resource.resource_type,
    resource.state,
    resource.public_access,
    encryption.at_rest_enabled,
    encryption.in_transit_enabled,
    encryption.algorithm,
    encryption.key_enabled,
    encryption.last_rotated_at,
    CASE
        WHEN resource.public_access THEN 'CRITICAL'
        WHEN encryption.resource_id IS NULL THEN 'CRITICAL'
        WHEN NOT encryption.at_rest_enabled THEN 'HIGH'
        WHEN NOT encryption.in_transit_enabled THEN 'HIGH'
        WHEN NOT encryption.key_enabled THEN 'HIGH'
        WHEN resource.state <> 'ACTIVE' THEN 'MEDIUM'
        ELSE 'COMPLIANT'
    END AS security_status
FROM cloud_resources resource
JOIN cloud_accounts account
    ON account.account_id = resource.account_id
LEFT JOIN encryption_configurations encryption
    ON encryption.resource_id = resource.resource_id;

-- Audit reporting view.

CREATE VIEW identity_security_summary AS
SELECT
    identity.identity_id,
    identity.username,
    COUNT(audit.audit_id) AS total_requests,
    COUNT(*) FILTER (
        WHERE audit.decision = 'ALLOW'
    ) AS allowed_requests,
    COUNT(*) FILTER (
        WHERE audit.decision = 'DENY'
    ) AS denied_requests,
    MAX(audit.event_time) AS latest_activity
FROM identities identity
LEFT JOIN audit_logs audit
    ON audit.identity_id = identity.identity_id
GROUP BY identity.identity_id, identity.username;

-- Sample accounts.

INSERT INTO cloud_accounts (
    account_name,
    cloud_provider,
    region,
    environment
)
VALUES
    ('finance-production', 'AWS', 'ap-south-1', 'PRODUCTION'),
    ('engineering-development', 'AZURE', 'centralindia', 'DEVELOPMENT');

INSERT INTO identities (
    account_id,
    username,
    identity_type,
    enabled,
    mfa_enabled
)
SELECT
    account_id,
    'cloud-operator',
    'HUMAN',
    TRUE,
    TRUE
FROM cloud_accounts
WHERE account_name = 'finance-production';

INSERT INTO identities (
    account_id,
    username,
    identity_type,
    enabled,
    mfa_enabled
)
SELECT
    account_id,
    'security-auditor',
    'HUMAN',
    TRUE,
    TRUE
FROM cloud_accounts
WHERE account_name = 'finance-production';

INSERT INTO identities (
    account_id,
    username,
    identity_type,
    enabled,
    mfa_enabled
)
SELECT
    account_id,
    'untrusted-service',
    'SERVICE',
    TRUE,
    FALSE
FROM cloud_accounts
WHERE account_name = 'finance-production';

INSERT INTO iam_roles (
    account_id,
    role_name,
    description,
    privileged
)
SELECT
    account_id,
    'storage-reader',
    'Read-only access to finance storage',
    FALSE
FROM cloud_accounts
WHERE account_name = 'finance-production';

INSERT INTO iam_roles (
    account_id,
    role_name,
    description,
    privileged
)
SELECT
    account_id,
    'security-auditor',
    'Security audit access',
    FALSE
FROM cloud_accounts
WHERE account_name = 'finance-production';

INSERT INTO iam_permissions (
    action,
    resource_pattern,
    effect
)
VALUES
    ('storage:read', 'bucket-finance-001', 'ALLOW'),
    ('storage:delete', '*', 'DENY'),
    ('audit:read', '*', 'ALLOW');

INSERT INTO identity_roles (identity_id, role_id)
SELECT identity.identity_id, role.role_id
FROM identities identity
JOIN iam_roles role
    ON role.role_name = 'storage-reader'
WHERE identity.username = 'cloud-operator';

INSERT INTO identity_roles (identity_id, role_id)
SELECT identity.identity_id, role.role_id
FROM identities identity
JOIN iam_roles role
    ON role.role_name = 'security-auditor'
WHERE identity.username = 'security-auditor';

INSERT INTO role_permissions (role_id, permission_id)
SELECT role.role_id, permission.permission_id
FROM iam_roles role
JOIN iam_permissions permission
    ON permission.action IN (
        'storage:read',
        'storage:delete'
    )
WHERE role.role_name = 'storage-reader';

INSERT INTO role_permissions (role_id, permission_id)
SELECT role.role_id, permission.permission_id
FROM iam_roles role
JOIN iam_permissions permission
    ON permission.action = 'audit:read'
WHERE role.role_name = 'security-auditor';

INSERT INTO cloud_resources (
    account_id,
    resource_name,
    resource_type,
    owner_identity_id,
    public_access
)
SELECT
    account.account_id,
    'bucket-finance-001',
    'OBJECT_STORAGE',
    identity.identity_id,
    FALSE
FROM cloud_accounts account
JOIN identities identity
    ON identity.username = 'cloud-operator'
WHERE account.account_name = 'finance-production';

INSERT INTO encryption_configurations (
    resource_id,
    at_rest_enabled,
    in_transit_enabled,
    algorithm,
    key_reference,
    key_rotation_days,
    last_rotated_at,
    key_enabled
)
SELECT
    resource_id,
    TRUE,
    TRUE,
    'AES-256-GCM',
    'kms/finance/key-001',
    90,
    NOW() - INTERVAL '20 days',
    TRUE
FROM cloud_resources
WHERE resource_name = 'bucket-finance-001';

INSERT INTO network_security_rules (
    resource_id,
    direction,
    protocol,
    port_start,
    port_end,
    cidr,
    description
)
SELECT
    resource_id,
    'INGRESS',
    'TCP',
    443,
    443,
    '10.20.0.0/16',
    'Restricted internal HTTPS access'
FROM cloud_resources
WHERE resource_name = 'bucket-finance-001';

INSERT INTO branch_security_policies (
    account_id,
    policy_name,
    minimum_mfa,
    encryption_mandatory,
    public_access_allowed,
    maximum_key_age_days
)
SELECT
    account_id,
    'production-baseline',
    TRUE,
    TRUE,
    FALSE,
    90
FROM cloud_accounts
WHERE account_name = 'finance-production';

INSERT INTO security_monitoring_rules (
    rule_name,
    event_type,
    threshold_count,
    time_window_minutes,
    severity
)
VALUES (
    'repeated-denials',
    'ACCESS_DENIED',
    3,
    15,
    'HIGH'
);

-- Valid access request.
SELECT record_access_attempt(
    identity.identity_id,
    resource.resource_id,
    'storage:read',
    '10.20.1.15'::INET,
    443
)
FROM identities identity
CROSS JOIN cloud_resources resource
WHERE identity.username = 'cloud-operator'
  AND resource.resource_name = 'bucket-finance-001';

-- Invalid network access: request from outside permitted CIDR.
SELECT record_access_attempt(
    identity.identity_id,
    resource.resource_id,
    'storage:read',
    '192.168.1.10'::INET,
    443
)
FROM identities identity
CROSS JOIN cloud_resources resource
WHERE identity.username = 'cloud-operator'
  AND resource.resource_name = 'bucket-finance-001';

-- Unauthorized principal: MFA and IAM requirements both fail.
SELECT record_access_attempt(
    identity.identity_id,
    resource.resource_id,
    'storage:read',
    '10.20.1.20'::INET,
    443
)
FROM identities identity
CROSS JOIN cloud_resources resource
WHERE identity.username = 'untrusted-service'
  AND resource.resource_name = 'bucket-finance-001';

-- Explicit deny takes precedence over an allow decision.
SELECT evaluate_iam(
    identity.identity_id,
    'storage:delete',
    'bucket-finance-001'
)
FROM identities identity
WHERE identity.username = 'cloud-operator';

-- Generate repeated denied attempts.
DO $$
DECLARE
    i INTEGER;
    identity_value BIGINT;
    resource_value BIGINT;
BEGIN
    SELECT identity_id
    INTO identity_value
    FROM identities
    WHERE username = 'untrusted-service';

    SELECT resource_id
    INTO resource_value
    FROM cloud_resources
    WHERE resource_name = 'bucket-finance-001';

    FOR i IN 1..3 LOOP
        PERFORM record_access_attempt(
            identity_value,
            resource_value,
            'storage:read',
            '10.20.1.20'::INET,
            443
        );
    END LOOP;
END;
$$;

-- Create an incident based on repeated denied requests.
CALL process_security_alerts(3, 15);

-- Eligibility and reporting queries.

-- 1. Resource security posture.
SELECT *
FROM security_posture
ORDER BY security_status, resource_name;

-- 2. Identity access statistics.
SELECT *
FROM identity_security_summary
ORDER BY denied_requests DESC;

-- 3. IAM role and permission retrieval.
SELECT
    identity.username,
    role.role_name,
    permission.action,
    permission.resource_pattern,
    permission.effect
FROM identities identity
JOIN identity_roles ir
    ON ir.identity_id = identity.identity_id
JOIN iam_roles role
    ON role.role_id = ir.role_id
JOIN role_permissions rp
    ON rp.role_id = role.role_id
JOIN iam_permissions permission
    ON permission.permission_id = rp.permission_id
ORDER BY identity.username, role.role_name;

-- 4. Network isolation inspection.
SELECT
    resource.resource_name,
    rule.direction,
    rule.protocol,
    rule.port_start,
    rule.port_end,
    rule.cidr
FROM network_security_rules rule
JOIN cloud_resources resource
    ON resource.resource_id = rule.resource_id
ORDER BY resource.resource_name;

-- 5. Security incident reporting.
SELECT
    incident_type,
    severity,
    state,
    COUNT(*) AS incident_count
FROM security_incidents
GROUP BY incident_type, severity, state
ORDER BY severity DESC;

-- 6. Current encryption key rotation status.
SELECT
    resource.resource_name,
    encryption.key_reference,
    encryption.last_rotated_at,
    encryption.key_rotation_days,
    NOW() - encryption.last_rotated_at AS key_age,
    (
        encryption.last_rotated_at <
        NOW() - make_interval(
            days => encryption.key_rotation_days
        )
    ) AS rotation_overdue
FROM encryption_configurations encryption
JOIN cloud_resources resource
    ON resource.resource_id = encryption.resource_id;

-- 7. Access failure aggregation.
SELECT *
FROM detect_repeated_denials(3, 15);

-- 8. Recent denied requests.
SELECT
    audit.event_time,
    identity.username,
    resource.resource_name,
    audit.action,
    audit.source_ip,
    audit.details
FROM audit_logs audit
LEFT JOIN identities identity
    ON identity.identity_id = audit.identity_id
LEFT JOIN cloud_resources resource
    ON resource.resource_id = audit.resource_id
WHERE audit.decision = 'DENY'
ORDER BY audit.event_time DESC;

-- Transactional resource quarantine example.
BEGIN;

UPDATE cloud_resources
SET state = 'QUARANTINED'
WHERE resource_name = 'bucket-finance-001';

-- Verify the transition before committing.
SELECT resource_name, state
FROM cloud_resources
WHERE resource_name = 'bucket-finance-001';

COMMIT;

-- Verify the quarantined resource can no longer receive access.
SELECT record_access_attempt(
    identity.identity_id,
    resource.resource_id,
    'storage:read',
    '10.20.1.15'::INET,
    443
)
FROM identities identity
CROSS JOIN cloud_resources resource
WHERE identity.username = 'cloud-operator'
  AND resource.resource_name = 'bucket-finance-001';

-- Final assessment.
SELECT
    COUNT(*) AS total_resources,
    COUNT(*) FILTER (
        WHERE security_status = 'COMPLIANT'
    ) AS compliant_resources,
    COUNT(*) FILTER (
        WHERE security_status <> 'COMPLIANT'
    ) AS resources_with_findings
FROM security_posture;

COMMIT;
