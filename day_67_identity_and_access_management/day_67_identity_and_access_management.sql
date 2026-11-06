-- ============================================================
-- IDENTITY AND ACCESS MANAGEMENT
-- PostgreSQL 15+
--
-- Models:
-- Users -> Groups -> Roles -> Permissions
-- Policies -> Access evaluation -> Audit events
-- Temporary access requests -> Approval -> Expiration
--
-- Explicit DENY overrides ALLOW and role permissions.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS iam;

SET search_path TO iam, public;

-- ------------------------------------------------------------
-- ENUM TYPES
-- ------------------------------------------------------------

CREATE TYPE account_status AS ENUM (
    'ACTIVE',
    'DISABLED',
    'LOCKED'
);

CREATE TYPE policy_effect AS ENUM (
    'ALLOW',
    'DENY'
);

CREATE TYPE access_decision AS ENUM (
    'ALLOW',
    'DENY'
);

CREATE TYPE request_status AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'EXPIRED'
);

-- ------------------------------------------------------------
-- USERS
-- ------------------------------------------------------------

CREATE TABLE users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(80) NOT NULL,
    email VARCHAR(254) NOT NULL,
    department VARCHAR(100) NOT NULL,
    status account_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version BIGINT NOT NULL DEFAULT 1,

    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_username_nonempty
        CHECK (length(trim(username)) > 0),
    CONSTRAINT ck_email_format
        CHECK (email ~* '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
    CONSTRAINT ck_department_nonempty
        CHECK (length(trim(department)) > 0),
    CONSTRAINT ck_user_version
        CHECK (version > 0)
);

CREATE INDEX idx_users_department_status
ON users(department, status);

-- ------------------------------------------------------------
-- GROUPS
-- ------------------------------------------------------------

CREATE TABLE iam_groups (
    group_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_group_name
        CHECK (length(trim(group_name)) > 0)
);

-- A user may belong to several groups.
CREATE TABLE user_groups (
    user_id BIGINT NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL
        REFERENCES iam_groups(group_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_by BIGINT REFERENCES users(user_id),

    PRIMARY KEY (user_id, group_id)
);

CREATE INDEX idx_user_groups_group
ON user_groups(group_id, user_id);

-- ------------------------------------------------------------
-- ROLES
-- ------------------------------------------------------------

CREATE TABLE roles (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_privileged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_role_name
        CHECK (length(trim(role_name)) > 0)
);

CREATE TABLE group_roles (
    group_id BIGINT NOT NULL
        REFERENCES iam_groups(group_id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL
        REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (group_id, role_id)
);

CREATE INDEX idx_group_roles_role
ON group_roles(role_id, group_id);

-- Optional direct user-role assignments.
-- Direct assignments should be exceptional and audited.
CREATE TABLE user_roles (
    user_id BIGINT NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL
        REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    assigned_by BIGINT REFERENCES users(user_id),

    PRIMARY KEY (user_id, role_id),

    CONSTRAINT ck_user_role_expiration
        CHECK (
            expires_at IS NULL OR
            expires_at > assigned_at
        )
);

CREATE INDEX idx_user_roles_expiration
ON user_roles(expires_at)
WHERE expires_at IS NOT NULL;

-- ------------------------------------------------------------
-- PERMISSIONS
-- ------------------------------------------------------------

CREATE TABLE permissions (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(80) NOT NULL,
    description TEXT,

    CONSTRAINT uq_resource_action
        UNIQUE(resource, action),

    CONSTRAINT ck_permission_resource
        CHECK (length(trim(resource)) > 0),

    CONSTRAINT ck_permission_action
        CHECK (length(trim(action)) > 0)
);

CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL
        REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL
        REFERENCES permissions(permission_id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX idx_role_permissions_permission
ON role_permissions(permission_id, role_id);

-- ------------------------------------------------------------
-- ACCESS POLICIES
-- ------------------------------------------------------------

CREATE TABLE access_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name VARCHAR(150) NOT NULL UNIQUE,
    effect policy_effect NOT NULL,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_policy_name
        CHECK (length(trim(policy_name)) > 0)
);

CREATE TABLE policy_permissions (
    policy_id BIGINT NOT NULL
        REFERENCES access_policies(policy_id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL
        REFERENCES permissions(permission_id) ON DELETE CASCADE,

    PRIMARY KEY (policy_id, permission_id)
);

CREATE TABLE policy_departments (
    policy_id BIGINT NOT NULL
        REFERENCES access_policies(policy_id) ON DELETE CASCADE,
    department VARCHAR(100) NOT NULL,

    PRIMARY KEY (policy_id, department)
);

CREATE TABLE policy_excluded_users (
    policy_id BIGINT NOT NULL
        REFERENCES access_policies(policy_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,

    PRIMARY KEY (policy_id, user_id)
);

-- ------------------------------------------------------------
-- TEMPORARY ACCESS REQUESTS
-- ------------------------------------------------------------

CREATE TABLE access_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id),
    approver_id BIGINT NOT NULL
        REFERENCES users(user_id),
    permission_id BIGINT NOT NULL
        REFERENCES permissions(permission_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    status request_status NOT NULL DEFAULT 'PENDING',
    justification TEXT NOT NULL,

    CONSTRAINT ck_no_self_approval
        CHECK (user_id <> approver_id),

    CONSTRAINT ck_request_justification
        CHECK (length(trim(justification)) > 0),

    CONSTRAINT ck_request_expiration
        CHECK (
            expires_at IS NULL OR
            expires_at > requested_at
        )
);

CREATE INDEX idx_access_requests_pending
ON access_requests(status, requested_at)
WHERE status = 'PENDING';

CREATE INDEX idx_access_requests_user
ON access_requests(user_id, requested_at DESC);

-- ------------------------------------------------------------
-- AUDIT LOG
-- ------------------------------------------------------------

CREATE TABLE access_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    requested_resource VARCHAR(100) NOT NULL,
    requested_action VARCHAR(80) NOT NULL,
    decision access_decision NOT NULL,
    reason TEXT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    correlation_id UUID NOT NULL DEFAULT gen_random_uuid()
);

CREATE INDEX idx_audit_user_time
ON access_audit(user_id, evaluated_at DESC);

CREATE INDEX idx_audit_denied
ON access_audit(evaluated_at DESC)
WHERE decision = 'DENY';

-- ------------------------------------------------------------
-- USER ACCOUNT VERSION TRIGGER
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_user_metadata()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    NEW.version := OLD.version + 1;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_user_metadata
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_user_metadata();

-- ------------------------------------------------------------
-- APPROVAL WORKFLOW TRIGGER
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_access_request()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    requester_status account_status;
    approver_status account_status;
BEGIN
    SELECT status
    INTO requester_status
    FROM users
    WHERE user_id = NEW.user_id;

    SELECT status
    INTO approver_status
    FROM users
    WHERE user_id = NEW.approver_id;

    IF requester_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Inactive users cannot request access';
    END IF;

    IF approver_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Inactive users cannot approve access';
    END IF;

    IF NEW.user_id = NEW.approver_id THEN
        RAISE EXCEPTION
            'Self-approval is prohibited';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF OLD.status <> 'PENDING' THEN
            RAISE EXCEPTION
                'Only pending requests can transition';
        END IF;

        IF NEW.status NOT IN ('APPROVED', 'REJECTED') THEN
            RAISE EXCEPTION
                'Invalid request transition';
        END IF;

        IF NEW.status = 'APPROVED' AND NEW.expires_at IS NULL THEN
            RAISE EXCEPTION
                'Approved requests require expiration';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_access_request
BEFORE INSERT OR UPDATE ON access_requests
FOR EACH ROW
EXECUTE FUNCTION validate_access_request();

-- ------------------------------------------------------------
-- EFFECTIVE ROLE VIEW
-- Combines group-derived and direct role assignments.
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW effective_user_roles AS
SELECT
    ug.user_id,
    gr.role_id,
    'GROUP'::TEXT AS assignment_source
FROM user_groups ug
JOIN group_roles gr ON gr.group_id = ug.group_id

UNION

SELECT
    ur.user_id,
    ur.role_id,
    'DIRECT'::TEXT AS assignment_source
FROM user_roles ur
WHERE ur.expires_at IS NULL
   OR ur.expires_at > CURRENT_TIMESTAMP;

-- ------------------------------------------------------------
-- EFFECTIVE PERMISSION VIEW
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW effective_user_permissions AS
SELECT DISTINCT
    eur.user_id,
    p.permission_id,
    p.resource,
    p.action,
    eur.assignment_source
FROM effective_user_roles eur
JOIN role_permissions rp ON rp.role_id = eur.role_id
JOIN permissions p ON p.permission_id = rp.permission_id;

-- ------------------------------------------------------------
-- ACCESS EVALUATION FUNCTION
--
-- Decision order:
-- 1. Validate active identity.
-- 2. Find applicable policies.
-- 3. Explicit DENY.
-- 4. Explicit ALLOW.
-- 5. RBAC permission.
-- 6. Default DENY.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION evaluate_access(
    p_user_id BIGINT,
    p_resource VARCHAR,
    p_action VARCHAR
)
RETURNS TABLE (
    allowed BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_status account_status;
    v_department VARCHAR(100);
    v_permission_id BIGINT;
    v_deny_name VARCHAR(150);
    v_allow_name VARCHAR(150);
    v_has_permission BOOLEAN;
BEGIN
    SELECT status, department
    INTO v_status, v_department
    FROM users
    WHERE user_id = p_user_id;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Unknown user'::TEXT;
        RETURN;
    END IF;

    IF v_status <> 'ACTIVE' THEN
        RETURN QUERY
        SELECT FALSE, 'Account is not active'::TEXT;
        RETURN;
    END IF;

    SELECT permission_id
    INTO v_permission_id
    FROM permissions
    WHERE resource = p_resource
      AND action = p_action;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Unknown permission'::TEXT;
        RETURN;
    END IF;

    -- Identify applicable explicit deny policies.
    SELECT ap.policy_name
    INTO v_deny_name
    FROM access_policies ap
    JOIN policy_permissions pp
      ON pp.policy_id = ap.policy_id
    LEFT JOIN policy_departments pd
      ON pd.policy_id = ap.policy_id
    WHERE ap.enabled = TRUE
      AND ap.effect = 'DENY'
      AND pp.permission_id = v_permission_id
      AND (
          pd.policy_id IS NULL OR
          pd.department = v_department
      )
      AND NOT EXISTS (
          SELECT 1
          FROM policy_excluded_users peu
          WHERE peu.policy_id = ap.policy_id
            AND peu.user_id = p_user_id
      )
    ORDER BY ap.priority
    LIMIT 1;

    IF v_deny_name IS NOT NULL THEN
        RETURN QUERY
        SELECT
            FALSE,
            ('Explicit deny: ' || v_deny_name)::TEXT;
        RETURN;
    END IF;

    -- Applicable allow policies are checked after all denies.
    SELECT ap.policy_name
    INTO v_allow_name
    FROM access_policies ap
    JOIN policy_permissions pp
      ON pp.policy_id = ap.policy_id
    LEFT JOIN policy_departments pd
      ON pd.policy_id = ap.policy_id
    WHERE ap.enabled = TRUE
      AND ap.effect = 'ALLOW'
      AND pp.permission_id = v_permission_id
      AND (
          pd.policy_id IS NULL OR
          pd.department = v_department
      )
      AND NOT EXISTS (
          SELECT 1
          FROM policy_excluded_users peu
          WHERE peu.policy_id = ap.policy_id
            AND peu.user_id = p_user_id
      )
    ORDER BY ap.priority
    LIMIT 1;

    IF v_allow_name IS NOT NULL THEN
        RETURN QUERY
        SELECT
            TRUE,
            ('Policy allow: ' || v_allow_name)::TEXT;
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM effective_user_permissions eup
        WHERE eup.user_id = p_user_id
          AND eup.permission_id = v_permission_id
    )
    INTO v_has_permission;

    IF v_has_permission THEN
        RETURN QUERY
        SELECT TRUE, 'Role permission granted'::TEXT;
    ELSE
        RETURN QUERY
        SELECT FALSE, 'No matching permission'::TEXT;
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- AUDITED AUTHORIZATION FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION authorize_access(
    p_user_id BIGINT,
    p_resource VARCHAR,
    p_action VARCHAR
)
RETURNS BOOLEAN
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    v_allowed BOOLEAN;
    v_reason TEXT;
BEGIN
    SELECT e.allowed, e.reason
    INTO v_allowed, v_reason
    FROM evaluate_access(
        p_user_id,
        p_resource,
        p_action
    ) e;

    INSERT INTO access_audit (
        user_id,
        requested_resource,
        requested_action,
        decision,
        reason
    )
    VALUES (
        p_user_id,
        p_resource,
        p_action,
        CASE
            WHEN v_allowed THEN 'ALLOW'::access_decision
            ELSE 'DENY'::access_decision
        END,
        v_reason
    );

    RETURN v_allowed;
END;
$$;

-- ------------------------------------------------------------
-- APPROVE TEMPORARY ACCESS
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION approve_access_request(
    p_request_id BIGINT,
    p_approver_id BIGINT,
    p_duration_minutes INTEGER
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_request access_requests%ROWTYPE;
    v_approver_status account_status;
BEGIN
    IF p_duration_minutes < 1 OR p_duration_minutes > 480 THEN
        RAISE EXCEPTION
            'Duration must be between 1 and 480 minutes';
    END IF;

    SELECT *
    INTO v_request
    FROM access_requests
    WHERE request_id = p_request_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Access request not found';
    END IF;

    IF v_request.status <> 'PENDING' THEN
        RAISE EXCEPTION 'Request is not pending';
    END IF;

    IF v_request.approver_id <> p_approver_id THEN
        RAISE EXCEPTION 'Incorrect approver';
    END IF;

    SELECT status
    INTO v_approver_status
    FROM users
    WHERE user_id = p_approver_id;

    IF v_approver_status <> 'ACTIVE' THEN
        RAISE EXCEPTION 'Approver is inactive';
    END IF;

    UPDATE access_requests
    SET
        status = 'APPROVED',
        expires_at =
            CURRENT_TIMESTAMP +
            make_interval(mins => p_duration_minutes)
    WHERE request_id = p_request_id;

    RETURN TRUE;
END;
$$;

-- ------------------------------------------------------------
-- EXPIRE TEMPORARY REQUESTS
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION expire_access_requests()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE access_requests
    SET status = 'EXPIRED'
    WHERE status = 'APPROVED'
      AND expires_at <= CURRENT_TIMESTAMP;

    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN v_count;
END;
$$;

-- ------------------------------------------------------------
-- SAMPLE USERS
-- ------------------------------------------------------------

INSERT INTO users (
    username, email, department
)
VALUES
    ('alice', 'alice@example.com', 'Finance'),
    ('bob', 'bob@example.com', 'Engineering'),
    ('carol', 'carol@example.com', 'Security'),
    ('diana', 'diana@example.com', 'Finance');

-- Sample groups.
INSERT INTO iam_groups (group_name, description)
VALUES
    ('FinanceTeam', 'Finance department employees'),
    ('EngineeringTeam', 'Engineering department employees'),
    ('SecurityTeam', 'Security administrators');

-- Sample roles.
INSERT INTO roles (role_name, description, is_privileged)
VALUES
    ('ReportReader', 'Read business reports', FALSE),
    ('ReportEditor', 'Create and read reports', FALSE),
    ('SecurityAdministrator', 'Manage identity records', TRUE),
    ('PayrollAuditor', 'Read payroll records', TRUE);

-- Permissions.
INSERT INTO permissions (resource, action, description)
VALUES
    ('reports', 'read', 'Read reports'),
    ('reports', 'create', 'Create reports'),
    ('reports', 'delete', 'Delete reports'),
    ('users', 'manage', 'Manage user accounts'),
    ('users', 'delete', 'Delete user accounts'),
    ('payroll', 'read', 'Read payroll information'),
    ('analytics', 'read', 'Read analytics data');

-- ------------------------------------------------------------
-- ASSIGN GROUPS TO USERS
-- ------------------------------------------------------------

INSERT INTO user_groups (user_id, group_id)
SELECT u.user_id, g.group_id
FROM (
    VALUES
        ('alice', 'FinanceTeam'),
        ('bob', 'EngineeringTeam'),
        ('carol', 'SecurityTeam'),
        ('diana', 'FinanceTeam')
) AS assignments(username, group_name)
JOIN users u ON u.username = assignments.username
JOIN iam_groups g ON g.group_name = assignments.group_name;

-- ------------------------------------------------------------
-- ASSIGN ROLES TO GROUPS
-- ------------------------------------------------------------

INSERT INTO group_roles (group_id, role_id)
SELECT g.group_id, r.role_id
FROM (
    VALUES
        ('FinanceTeam', 'ReportReader'),
        ('EngineeringTeam', 'ReportReader'),
        ('SecurityTeam', 'SecurityAdministrator')
) AS assignments(group_name, role_name)
JOIN iam_groups g ON g.group_name = assignments.group_name
JOIN roles r ON r.role_name = assignments.role_name;

-- ------------------------------------------------------------
-- ROLE PERMISSIONS
-- ------------------------------------------------------------

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM (
    VALUES
        ('ReportReader', 'reports', 'read'),
        ('ReportEditor', 'reports', 'read'),
        ('ReportEditor', 'reports', 'create'),
        ('SecurityAdministrator', 'users', 'manage'),
        ('SecurityAdministrator', 'users', 'delete'),
        ('PayrollAuditor', 'payroll', 'read')
) AS assignments(role_name, resource, action)
JOIN roles r ON r.role_name = assignments.role_name
JOIN permissions p
  ON p.resource = assignments.resource
 AND p.action = assignments.action;

-- Direct role assignment example.
-- This is deliberately restricted to one user.
INSERT INTO user_roles (user_id, role_id, assigned_by)
SELECT u.user_id, r.role_id, NULL
FROM users u
CROSS JOIN roles r
WHERE u.username = 'diana'
  AND r.role_name = 'PayrollAuditor';

-- ------------------------------------------------------------
-- ACCESS POLICIES
-- ------------------------------------------------------------

INSERT INTO access_policies (
    policy_name,
    effect,
    description,
    priority
)
VALUES
    (
        'FinancePayrollRestriction',
        'DENY',
        'Protect payroll from ordinary finance users',
        1
    ),
    (
        'FinanceReportCreation',
        'ALLOW',
        'Allow finance users to create reports',
        10
    );

INSERT INTO policy_permissions (policy_id, permission_id)
SELECT ap.policy_id, p.permission_id
FROM access_policies ap
JOIN permissions p
  ON (
      ap.policy_name = 'FinancePayrollRestriction'
      AND p.resource = 'payroll'
      AND p.action = 'read'
  )
  OR (
      ap.policy_name = 'FinanceReportCreation'
      AND p.resource = 'reports'
      AND p.action = 'create'
  );

INSERT INTO policy_departments (policy_id, department)
SELECT policy_id, 'Finance'
FROM access_policies
WHERE policy_name IN (
    'FinancePayrollRestriction',
    'FinanceReportCreation'
);

-- ------------------------------------------------------------
-- SAMPLE ACCESS REQUEST
-- ------------------------------------------------------------

INSERT INTO access_requests (
    user_id,
    approver_id,
    permission_id,
    justification
)
SELECT
    requester.user_id,
    approver.user_id,
    p.permission_id,
    'Temporary analytics access for a reporting assignment'
FROM users requester
JOIN users approver
  ON approver.username = 'carol'
JOIN permissions p
  ON p.resource = 'analytics'
 AND p.action = 'read'
WHERE requester.username = 'alice';

-- ------------------------------------------------------------
-- RETRIEVAL
-- ------------------------------------------------------------

-- All active users and their group memberships.
SELECT
    u.username,
    u.department,
    u.status,
    g.group_name
FROM users u
LEFT JOIN user_groups ug ON ug.user_id = u.user_id
LEFT JOIN iam_groups g ON g.group_id = ug.group_id
ORDER BY u.username, g.group_name;

-- Effective roles for each user.
SELECT
    u.username,
    r.role_name,
    eur.assignment_source
FROM effective_user_roles eur
JOIN users u ON u.user_id = eur.user_id
JOIN roles r ON r.role_id = eur.role_id
ORDER BY u.username, r.role_name;

-- Effective permissions.
SELECT
    u.username,
    eup.resource,
    eup.action,
    eup.assignment_source
FROM effective_user_permissions eup
JOIN users u ON u.user_id = eup.user_id
ORDER BY u.username, eup.resource, eup.action;

-- ------------------------------------------------------------
-- VALIDATION
-- ------------------------------------------------------------

-- Find users with privileged roles.
SELECT DISTINCT
    u.username,
    r.role_name,
    eur.assignment_source
FROM effective_user_roles eur
JOIN users u ON u.user_id = eur.user_id
JOIN roles r ON r.role_id = eur.role_id
WHERE r.is_privileged = TRUE;

-- Find users with no assigned roles.
SELECT
    u.user_id,
    u.username,
    u.status
FROM users u
WHERE NOT EXISTS (
    SELECT 1
    FROM effective_user_roles eur
    WHERE eur.user_id = u.user_id
);

-- Detect direct privileged assignments.
SELECT
    u.username,
    r.role_name,
    ur.assigned_at,
    ur.expires_at
FROM user_roles ur
JOIN users u ON u.user_id = ur.user_id
JOIN roles r ON r.role_id = ur.role_id
WHERE r.is_privileged = TRUE;

-- ------------------------------------------------------------
-- AGGREGATION AND REPORTING
-- ------------------------------------------------------------

-- Number of users per department and account status.
SELECT
    department,
    status,
    COUNT(*) AS user_count
FROM users
GROUP BY department, status
ORDER BY department, status;

-- Group membership statistics.
SELECT
    g.group_name,
    COUNT(ug.user_id) AS member_count
FROM iam_groups g
LEFT JOIN user_groups ug ON ug.group_id = g.group_id
GROUP BY g.group_id, g.group_name
ORDER BY member_count DESC;

-- Role distribution.
SELECT
    r.role_name,
    COUNT(DISTINCT eur.user_id) AS assigned_users
FROM roles r
LEFT JOIN effective_user_roles eur
    ON eur.role_id = r.role_id
GROUP BY r.role_id, r.role_name
ORDER BY assigned_users DESC;

-- ------------------------------------------------------------
-- ACCESS EVALUATION
-- ------------------------------------------------------------

-- Alice can read reports through her group role.
SELECT *
FROM evaluate_access(
    (SELECT user_id FROM users WHERE username = 'alice'),
    'reports',
    'read'
);

-- Alice can create reports through a department policy.
SELECT *
FROM evaluate_access(
    (SELECT user_id FROM users WHERE username = 'alice'),
    'reports',
    'create'
);

-- Alice cannot read payroll because explicit deny takes precedence.
SELECT *
FROM evaluate_access(
    (SELECT user_id FROM users WHERE username = 'alice'),
    'payroll',
    'read'
);

-- Bob cannot create reports.
SELECT *
FROM evaluate_access(
    (SELECT user_id FROM users WHERE username = 'bob'),
    'reports',
    'create'
);

-- Carol has security administration permissions.
SELECT *
FROM evaluate_access(
    (SELECT user_id FROM users WHERE username = 'carol'),
    'users',
    'delete'
);

-- Unknown resource-action combinations are denied.
SELECT *
FROM evaluate_access(
    (SELECT user_id FROM users WHERE username = 'alice'),
    'unknown_resource',
    'unknown_action'
);

-- ------------------------------------------------------------
-- AUDITED ACCESS WORKFLOW
-- ------------------------------------------------------------

SELECT authorize_access(
    (SELECT user_id FROM users WHERE username = 'alice'),
    'reports',
    'read'
);

SELECT authorize_access(
    (SELECT user_id FROM users WHERE username = 'alice'),
    'payroll',
    'read'
);

SELECT authorize_access(
    (SELECT user_id FROM users WHERE username = 'bob'),
    'reports',
    'create'
);

-- Audit history.
SELECT
    audit_id,
    user_id,
    requested_resource,
    requested_action,
    decision,
    reason,
    evaluated_at,
    correlation_id
FROM access_audit
ORDER BY evaluated_at DESC;

-- Denial rate and decision counts.
SELECT
    decision,
    COUNT(*) AS decision_count
FROM access_audit
GROUP BY decision;

-- ------------------------------------------------------------
-- APPROVAL PROCESSING
-- ------------------------------------------------------------

-- Approve Alice's pending analytics request.
SELECT approve_access_request(
    (
        SELECT request_id
        FROM access_requests
        WHERE status = 'PENDING'
        ORDER BY request_id
        LIMIT 1
    ),
    (
        SELECT user_id
        FROM users
        WHERE username = 'carol'
    ),
    30
);

-- View approved and pending requests.
SELECT
    ar.request_id,
    requester.username AS requester,
    approver.username AS approver,
    p.resource,
    p.action,
    ar.status,
    ar.requested_at,
    ar.expires_at
FROM access_requests ar
JOIN users requester ON requester.user_id = ar.user_id
JOIN users approver ON approver.user_id = ar.approver_id
JOIN permissions p ON p.permission_id = ar.permission_id
ORDER BY ar.requested_at DESC;

-- Expire temporary access requests after their expiration.
SELECT expire_access_requests();

-- ------------------------------------------------------------
-- LEAST PRIVILEGE REPORT
-- ------------------------------------------------------------

WITH permission_counts AS (
    SELECT
        u.user_id,
        u.username,
        u.status,
        COUNT(DISTINCT eup.permission_id) AS permission_count
    FROM users u
    LEFT JOIN effective_user_permissions eup
        ON eup.user_id = u.user_id
    GROUP BY u.user_id, u.username, u.status
)
SELECT
    username,
    status,
    permission_count,
    CASE
        WHEN permission_count = 0 THEN 'NO_ACCESS'
        WHEN permission_count > 3 THEN 'REVIEW_REQUIRED'
        ELSE 'STANDARD'
    END AS access_review_status
FROM permission_counts
ORDER BY permission_count DESC;

-- ------------------------------------------------------------
-- FAILURE CASE DEMONSTRATIONS
-- ------------------------------------------------------------

-- Invalid duplicate identity.
DO $$
BEGIN
    BEGIN
        INSERT INTO users (
            username,
            email,
            department
        )
        VALUES (
            'alice',
            'duplicate@example.com',
            'Finance'
        );
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'Expected failure: duplicate username';
    END;
END;
$$;

-- Invalid self-approval.
DO $$
DECLARE
    v_user_id BIGINT;
    v_permission_id BIGINT;
BEGIN
    SELECT user_id
    INTO v_user_id
    FROM users
    WHERE username = 'alice';

    SELECT permission_id
    INTO v_permission_id
    FROM permissions
    WHERE resource = 'analytics'
      AND action = 'read';

    BEGIN
        INSERT INTO access_requests (
            user_id,
            approver_id,
            permission_id,
            justification
        )
        VALUES (
            v_user_id,
            v_user_id,
            v_permission_id,
            'Invalid self-approval attempt'
        );
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Expected failure: self-approval prohibited';
    END;
END;
$$;

-- Invalid permission reference.
DO $$
BEGIN
    BEGIN
        INSERT INTO role_permissions (
            role_id,
            permission_id
        )
        VALUES (
            999999,
            999999
        );
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'Expected failure: unknown role or permission';
    END;
END;
$$;

-- ------------------------------------------------------------
-- ACCOUNT DEACTIVATION
-- ------------------------------------------------------------

UPDATE users
SET status = 'DISABLED'
WHERE username = 'bob';

-- Disabled accounts must not receive access.
SELECT *
FROM evaluate_access(
    (SELECT user_id FROM users WHERE username = 'bob'),
    'reports',
    'read'
);

-- ------------------------------------------------------------
-- OPERATIONAL GOVERNANCE REPORT
-- ------------------------------------------------------------

SELECT
    COUNT(*) FILTER (
        WHERE status = 'ACTIVE'
    ) AS active_users,
    COUNT(*) FILTER (
        WHERE status = 'DISABLED'
    ) AS disabled_users,
    COUNT(*) FILTER (
        WHERE status = 'LOCKED'
    ) AS locked_users
FROM users;

SELECT
    COUNT(*) AS pending_requests
FROM access_requests
WHERE status = 'PENDING';

SELECT
    COUNT(*) AS expired_or_expiring_assignments
FROM user_roles
WHERE expires_at IS NOT NULL
  AND expires_at <= CURRENT_TIMESTAMP;

SELECT
    COUNT(*) AS denied_access_attempts
FROM access_audit
WHERE decision = 'DENY';

COMMIT;

-- ============================================================
-- PRODUCTION SECURITY NOTES
--
-- 1. Runtime database accounts should not own this schema.
-- 2. Restrict table writes through controlled service functions.
-- 3. Grant EXECUTE on authorization functions selectively.
-- 4. Enforce tenant boundaries where multiple organizations exist.
-- 5. Use transaction-level locking for approval workflows.
-- 6. Store immutable audit records in separately controlled storage.
-- 7. Use short-lived credentials and strong authentication.
-- 8. Use MFA for privileged identities.
-- 9. Review privileged access periodically.
-- 10. This schema models authorization but does not implement
--     authentication, password hashing, MFA or session security.
-- ============================================================
