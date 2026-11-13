/*
===============================================================================
COMPLIANCE AND GOVERNANCE MANAGEMENT DATABASE
===============================================================================

PostgreSQL 15+

Implements:
- Regulatory frameworks and obligations
- Organizations and users
- Role-based permissions
- Data asset classification
- Processing purposes and legal bases
- Consent management
- Data subject requests
- Retention rules
- Governance policies
- Compliance assessments
- Audit evidence
- Access logging
- Risk findings
- Compliance reporting
- Governance eligibility determination

The database demonstrates governance controls and workflow integrity.
Regulatory applicability and legal compliance require jurisdiction-specific
assessment outside the database.
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS governance;

SET search_path TO governance, public;

-- ============================================================================
-- DOMAIN TYPES
-- ============================================================================

CREATE TYPE privacy_category AS ENUM (
    'PUBLIC',
    'INTERNAL',
    'CONFIDENTIAL',
    'PERSONAL',
    'SENSITIVE_PERSONAL'
);

CREATE TYPE legal_basis AS ENUM (
    'CONSENT',
    'CONTRACT',
    'LEGAL_OBLIGATION',
    'LEGITIMATE_INTEREST',
    'PUBLIC_TASK',
    'VITAL_INTEREST'
);

CREATE TYPE consent_status AS ENUM (
    'GRANTED',
    'WITHDRAWN',
    'EXPIRED'
);

CREATE TYPE request_type AS ENUM (
    'ACCESS',
    'RECTIFICATION',
    'ERASURE',
    'PORTABILITY',
    'RESTRICTION'
);

CREATE TYPE request_status AS ENUM (
    'RECEIVED',
    'VERIFIED',
    'IN_PROGRESS',
    'COMPLETED',
    'REJECTED'
);

CREATE TYPE risk_level AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE check_status AS ENUM (
    'PASSED',
    'FAILED',
    'NOT_RUN'
);

CREATE TYPE governance_decision AS ENUM (
    'ELIGIBLE',
    'BLOCKED'
);

-- ============================================================================
-- REFERENCE TABLES
-- ============================================================================

CREATE TABLE regulatory_frameworks (
    framework_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    jurisdiction VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO regulatory_frameworks
(code, name, jurisdiction, description)
VALUES
(
    'GDPR',
    'General Data Protection Regulation',
    'European Union',
    'Personal data protection and processing requirements.'
),
(
    'DPDPA',
    'Digital Personal Data Protection Act, 2023',
    'India',
    'Indian digital personal data protection framework.'
),
(
    'ISO27001',
    'Information Security Management System',
    'International',
    'Information security management requirements.'
),
(
    'HIPAA',
    'Health Insurance Portability and Accountability Act',
    'United States',
    'Protected health information safeguards.'
);

CREATE TABLE organizations (
    organization_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_name VARCHAR(200) NOT NULL UNIQUE,
    country_code CHAR(2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO organizations (organization_name, country_code)
VALUES
('Enterprise Data Governance Office', 'IN'),
('European Customer Operations', 'DE');

-- ============================================================================
-- IDENTITY AND ACCESS MANAGEMENT
-- ============================================================================

CREATE TABLE governance_roles (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name VARCHAR(80) NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE permissions (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permission_code VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL REFERENCES governance_roles(role_id),
    permission_id BIGINT NOT NULL REFERENCES permissions(permission_id),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE governance_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),
    role_id BIGINT NOT NULL REFERENCES governance_roles(role_id),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(254) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO governance_roles (role_name, description)
VALUES
('COMPLIANCE_ADMIN', 'Manages compliance governance'),
('PRIVACY_OFFICER', 'Manages privacy obligations'),
('ANALYST', 'Performs authorized data operations'),
('AUDITOR', 'Reviews governance evidence');

INSERT INTO permissions (permission_code, description)
VALUES
('asset:create', 'Register data assets'),
('asset:read', 'Read authorized data asset records'),
('consent:manage', 'Manage consent records'),
('request:manage', 'Manage subject requests'),
('policy:manage', 'Manage governance policies'),
('report:read', 'Read compliance reports'),
('retention:manage', 'Manage retention processing'),
('audit:read', 'Read audit evidence');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM governance_roles r
CROSS JOIN permissions p
WHERE
    (
        r.role_name = 'COMPLIANCE_ADMIN'
    )
    OR (
        r.role_name = 'PRIVACY_OFFICER'
        AND p.permission_code IN (
            'asset:read',
            'consent:manage',
            'request:manage',
            'report:read'
        )
    )
    OR (
        r.role_name = 'ANALYST'
        AND p.permission_code = 'asset:read'
    )
    OR (
        r.role_name = 'AUDITOR'
        AND p.permission_code IN ('report:read', 'audit:read')
    );

INSERT INTO governance_users
(organization_id, role_id, username, email)
SELECT
    o.organization_id,
    r.role_id,
    x.username,
    x.email
FROM (
    VALUES
        (
            'Enterprise Data Governance Office',
            'COMPLIANCE_ADMIN',
            'compliance_admin',
            'admin@example.org'
        ),
        (
            'Enterprise Data Governance Office',
            'PRIVACY_OFFICER',
            'privacy_officer',
            'privacy@example.org'
        ),
        (
            'Enterprise Data Governance Office',
            'ANALYST',
            'data_analyst',
            'analyst@example.org'
        ),
        (
            'Enterprise Data Governance Office',
            'AUDITOR',
            'internal_auditor',
            'auditor@example.org'
        )
) AS x(org_name, role_name, username, email)
JOIN organizations o
    ON o.organization_name = x.org_name
JOIN governance_roles r
    ON r.role_name = x.role_name;

-- ============================================================================
-- DATA ASSET MANAGEMENT
-- ============================================================================

CREATE TABLE data_assets (
    asset_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),
    asset_code VARCHAR(60) NOT NULL UNIQUE,
    asset_name VARCHAR(200) NOT NULL,
    owner_user_id BIGINT NOT NULL
        REFERENCES governance_users(user_id),
    category privacy_category NOT NULL,
    purpose TEXT NOT NULL,
    basis legal_basis NOT NULL,
    retention_days INTEGER NOT NULL CHECK (retention_days > 0),
    encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (LENGTH(TRIM(purpose)) > 0),

    CHECK (
        category <> 'SENSITIVE_PERSONAL'
        OR encrypted = TRUE
    )
);

CREATE TABLE asset_frameworks (
    asset_id BIGINT NOT NULL REFERENCES data_assets(asset_id),
    framework_id BIGINT NOT NULL
        REFERENCES regulatory_frameworks(framework_id),
    PRIMARY KEY (asset_id, framework_id)
);

CREATE INDEX idx_assets_category
    ON data_assets(category);

CREATE INDEX idx_assets_owner
    ON data_assets(owner_user_id);

CREATE INDEX idx_assets_active
    ON data_assets(active)
    WHERE active = TRUE;

CREATE INDEX idx_assets_retention
    ON data_assets(created_at, retention_days)
    WHERE active = TRUE;

-- ============================================================================
-- CONSENT MANAGEMENT
-- ============================================================================

CREATE TABLE consent_records (
    consent_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_reference VARCHAR(120) NOT NULL,
    asset_id BIGINT NOT NULL REFERENCES data_assets(asset_id),
    purpose TEXT NOT NULL,
    status consent_status NOT NULL DEFAULT 'GRANTED',
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    withdrawn_at TIMESTAMPTZ,

    CHECK (LENGTH(TRIM(subject_reference)) > 0),
    CHECK (LENGTH(TRIM(purpose)) > 0),
    CHECK (
        expires_at IS NULL
        OR expires_at > granted_at
    ),
    CHECK (
        (
            status = 'WITHDRAWN'
            AND withdrawn_at IS NOT NULL
        )
        OR
        (
            status <> 'WITHDRAWN'
            AND withdrawn_at IS NULL
        )
    )
);

CREATE INDEX idx_consent_subject_asset
    ON consent_records(subject_reference, asset_id);

CREATE INDEX idx_consent_active
    ON consent_records(asset_id, subject_reference, expires_at)
    WHERE status = 'GRANTED';

-- ============================================================================
-- DATA SUBJECT REQUESTS
-- ============================================================================

CREATE TABLE subject_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_reference VARCHAR(60) NOT NULL UNIQUE,
    subject_reference VARCHAR(120) NOT NULL,
    request_kind request_type NOT NULL,
    status request_status NOT NULL DEFAULT 'RECEIVED',
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deadline_at TIMESTAMPTZ NOT NULL,
    assigned_user_id BIGINT REFERENCES governance_users(user_id),
    completed_at TIMESTAMPTZ,
    notes TEXT,
    version INTEGER NOT NULL DEFAULT 1,

    CHECK (deadline_at > received_at),
    CHECK (version > 0),
    CHECK (
        (
            status = 'COMPLETED'
            AND completed_at IS NOT NULL
        )
        OR
        (
            status <> 'COMPLETED'
            AND completed_at IS NULL
        )
    )
);

CREATE INDEX idx_requests_status_deadline
    ON subject_requests(status, deadline_at);

CREATE INDEX idx_requests_subject
    ON subject_requests(subject_reference);

-- ============================================================================
-- GOVERNANCE POLICIES
-- ============================================================================

CREATE TABLE governance_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_code VARCHAR(60) NOT NULL UNIQUE,
    policy_name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    encryption_required BOOLEAN NOT NULL DEFAULT FALSE,
    maximum_retention_days INTEGER NOT NULL
        CHECK (maximum_retention_days > 0),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_until DATE,
    created_by BIGINT NOT NULL REFERENCES governance_users(user_id),

    CHECK (
        effective_until IS NULL
        OR effective_until >= effective_from
    )
);

CREATE TABLE policy_categories (
    policy_id BIGINT NOT NULL
        REFERENCES governance_policies(policy_id),
    category privacy_category NOT NULL,
    PRIMARY KEY (policy_id, category)
);

CREATE TABLE policy_frameworks (
    policy_id BIGINT NOT NULL
        REFERENCES governance_policies(policy_id),
    framework_id BIGINT NOT NULL
        REFERENCES regulatory_frameworks(framework_id),
    PRIMARY KEY (policy_id, framework_id)
);

INSERT INTO governance_policies (
    policy_code,
    policy_name,
    description,
    encryption_required,
    maximum_retention_days,
    created_by
)
SELECT
    'POLICY-PERSONAL-001',
    'Personal Data Security Policy',
    'Encryption and retention controls for personal information.',
    TRUE,
    3650,
    user_id
FROM governance_users
WHERE username = 'compliance_admin';

INSERT INTO policy_categories (policy_id, category)
SELECT policy_id, 'PERSONAL'
FROM governance_policies
WHERE policy_code = 'POLICY-PERSONAL-001';

INSERT INTO policy_categories (policy_id, category)
SELECT policy_id, 'SENSITIVE_PERSONAL'
FROM governance_policies
WHERE policy_code = 'POLICY-PERSONAL-001';

-- ============================================================================
-- CONTROL ASSESSMENTS AND FINDINGS
-- ============================================================================

CREATE TABLE compliance_assessments (
    assessment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES data_assets(asset_id),
    framework_id BIGINT
        REFERENCES regulatory_frameworks(framework_id),
    assessor_id BIGINT NOT NULL REFERENCES governance_users(user_id),
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assessment_notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE control_results (
    control_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assessment_id BIGINT NOT NULL
        REFERENCES compliance_assessments(assessment_id),
    control_code VARCHAR(80) NOT NULL,
    control_name VARCHAR(200) NOT NULL,
    status check_status NOT NULL,
    mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    evidence_reference VARCHAR(300),
    UNIQUE (assessment_id, control_code)
);

CREATE TABLE compliance_findings (
    finding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES data_assets(asset_id),
    policy_id BIGINT REFERENCES governance_policies(policy_id),
    severity risk_level NOT NULL,
    description TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by BIGINT REFERENCES governance_users(user_id),

    CHECK (
        (
            resolved = TRUE
            AND resolved_at IS NOT NULL
            AND resolved_by IS NOT NULL
        )
        OR
        (
            resolved = FALSE
            AND resolved_at IS NULL
            AND resolved_by IS NULL
        )
    )
);

CREATE INDEX idx_findings_open
    ON compliance_findings(severity, detected_at)
    WHERE resolved = FALSE;

CREATE INDEX idx_assessments_asset_date
    ON compliance_assessments(asset_id, assessed_at DESC);

-- ============================================================================
-- AUDIT LOGGING
-- ============================================================================

CREATE TABLE audit_events (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id BIGINT REFERENCES governance_users(user_id),
    action VARCHAR(80) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    resource_reference VARCHAR(120) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::JSONB
        CHECK (jsonb_typeof(details) = 'object'),
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);

CREATE INDEX idx_audit_actor_timestamp
    ON audit_events(actor_id, event_timestamp DESC);

CREATE INDEX idx_audit_resource
    ON audit_events(resource_type, resource_reference);

CREATE INDEX idx_audit_timestamp
    ON audit_events(event_timestamp DESC);

-- Hash chain using PostgreSQL pgcrypto.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE FUNCTION governance.append_audit_event(
    p_actor_id BIGINT,
    p_action VARCHAR,
    p_resource_type VARCHAR,
    p_resource_reference VARCHAR,
    p_details JSONB DEFAULT '{}'::JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = governance, public
AS $$
DECLARE
    v_previous_hash TEXT;
    v_payload TEXT;
    v_hash TEXT;
    v_id BIGINT;
BEGIN
    -- Serialize writers to preserve chain order.
    LOCK TABLE governance.audit_events IN EXCLUSIVE MODE;

    SELECT event_hash
    INTO v_previous_hash
    FROM governance.audit_events
    ORDER BY audit_id DESC
    LIMIT 1;

    v_previous_hash := COALESCE(v_previous_hash, 'GENESIS');

    v_payload :=
        jsonb_build_object(
            'actor_id', p_actor_id,
            'action', p_action,
            'resource_type', p_resource_type,
            'resource_reference', p_resource_reference,
            'details', p_details,
            'previous_hash', v_previous_hash
        )::TEXT;

    v_hash := encode(
        digest(
            v_previous_hash || '|' || v_payload,
            'sha256'
        ),
        'hex'
    );

    INSERT INTO governance.audit_events (
        actor_id,
        action,
        resource_type,
        resource_reference,
        details,
        previous_hash,
        event_hash
    )
    VALUES (
        p_actor_id,
        p_action,
        p_resource_type,
        p_resource_reference,
        COALESCE(p_details, '{}'::JSONB),
        v_previous_hash,
        v_hash
    )
    RETURNING audit_id INTO v_id;

    RETURN v_id;
END;
$$;

-- Prevent ordinary updates and deletes of audit evidence.
CREATE FUNCTION governance.prevent_audit_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Audit records are append-only through ordinary application operations.';
END;
$$;

CREATE TRIGGER trg_audit_immutable
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION governance.prevent_audit_mutation();

-- ============================================================================
-- INTEGRITY TRIGGERS
-- ============================================================================

CREATE FUNCTION governance.validate_consent_basis()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_basis legal_basis;
    v_purpose TEXT;
BEGIN
    SELECT basis, purpose
    INTO v_basis, v_purpose
    FROM data_assets
    WHERE asset_id = NEW.asset_id
      AND active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Asset is missing or inactive.';
    END IF;

    IF v_basis <> 'CONSENT' THEN
        RAISE EXCEPTION
            'Consent cannot be used as the declared basis for this asset.';
    END IF;

    IF NEW.purpose <> v_purpose THEN
        RAISE EXCEPTION
            'Consent purpose does not match asset purpose.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_consent
BEFORE INSERT OR UPDATE ON consent_records
FOR EACH ROW
EXECUTE FUNCTION governance.validate_consent_basis();

CREATE FUNCTION governance.validate_request_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (
            OLD.status = 'RECEIVED'
            AND NEW.status IN ('VERIFIED', 'REJECTED')
        )
        OR
        (
            OLD.status = 'VERIFIED'
            AND NEW.status IN ('IN_PROGRESS', 'REJECTED')
        )
        OR
        (
            OLD.status = 'IN_PROGRESS'
            AND NEW.status IN ('COMPLETED', 'REJECTED')
        )
    ) THEN
        RAISE EXCEPTION
            'Invalid subject request transition: % to %',
            OLD.status,
            NEW.status;
    END IF;

    NEW.version := OLD.version + 1;

    IF NEW.status = 'COMPLETED' THEN
        NEW.completed_at := NOW();
    ELSE
        NEW.completed_at := NULL;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_request_transition
BEFORE UPDATE OF status ON subject_requests
FOR EACH ROW
EXECUTE FUNCTION governance.validate_request_transition();

CREATE FUNCTION governance.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_asset_updated
BEFORE UPDATE ON data_assets
FOR EACH ROW
EXECUTE FUNCTION governance.set_updated_at();

-- ============================================================================
-- AUDIT INTEGRITY VERIFICATION
-- ============================================================================

CREATE FUNCTION governance.verify_audit_chain()
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_previous TEXT := 'GENESIS';
    v_payload TEXT;
    v_expected TEXT;
BEGIN
    FOR r IN
        SELECT *
        FROM audit_events
        ORDER BY audit_id
    LOOP
        IF r.previous_hash <> v_previous THEN
            RETURN FALSE;
        END IF;

        v_payload :=
            jsonb_build_object(
                'actor_id', r.actor_id,
                'action', r.action,
                'resource_type', r.resource_type,
                'resource_reference', r.resource_reference,
                'details', r.details,
                'previous_hash', v_previous
            )::TEXT;

        v_expected := encode(
            digest(v_previous || '|' || v_payload, 'sha256'),
            'hex'
        );

        IF v_expected <> r.event_hash THEN
            RETURN FALSE;
        END IF;

        v_previous := r.event_hash;
    END LOOP;

    RETURN TRUE;
END;
$$;

-- ============================================================================
-- ELIGIBILITY ENGINE
-- ============================================================================

CREATE FUNCTION governance.evaluate_asset_eligibility(
    p_asset_id BIGINT
)
RETURNS TABLE (
    decision governance_decision,
    blockers TEXT[],
    warnings TEXT[]
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_blockers TEXT[] := ARRAY[]::TEXT[];
    v_warnings TEXT[] := ARRAY[]::TEXT[];
    v_asset RECORD;
BEGIN
    SELECT *
    INTO v_asset
    FROM data_assets
    WHERE asset_id = p_asset_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown asset ID: %', p_asset_id;
    END IF;

    IF NOT v_asset.active THEN
        v_blockers := array_append(
            v_blockers,
            'Asset is inactive.'
        );
    END IF;

    FOR v_asset IN
        SELECT
            a.asset_id,
            a.encrypted,
            a.retention_days,
            p.policy_code,
            p.encryption_required,
            p.maximum_retention_days
        FROM data_assets a
        JOIN policy_categories pc
            ON pc.category = a.category
        JOIN governance_policies p
            ON p.policy_id = pc.policy_id
        WHERE a.asset_id = p_asset_id
          AND p.enabled = TRUE
          AND CURRENT_DATE >= p.effective_from
          AND (
              p.effective_until IS NULL
              OR CURRENT_DATE <= p.effective_until
          )
    LOOP
        IF
            v_asset.encryption_required
            AND NOT v_asset.encrypted
        THEN
            v_blockers := array_append(
                v_blockers,
                'Encryption policy failed: ' || v_asset.policy_code
            );
        END IF;

        IF
            v_asset.retention_days >
            v_asset.maximum_retention_days
        THEN
            v_blockers := array_append(
                v_blockers,
                'Retention policy failed: ' || v_asset.policy_code
            );
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM asset_frameworks
        WHERE asset_id = p_asset_id
    ) THEN
        v_warnings := array_append(
            v_warnings,
            'No regulatory framework mapping exists.'
        );
    END IF;

    RETURN QUERY
    SELECT
        CASE
            WHEN cardinality(v_blockers) = 0
                THEN 'ELIGIBLE'::governance_decision
            ELSE 'BLOCKED'::governance_decision
        END,
        v_blockers,
        v_warnings;
END;
$$;

-- ============================================================================
-- CONSENT VALIDATION FUNCTION
-- ============================================================================

CREATE FUNCTION governance.can_process_asset(
    p_asset_id BIGINT,
    p_subject_reference VARCHAR
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_basis legal_basis;
BEGIN
    SELECT basis
    INTO v_basis
    FROM data_assets
    WHERE asset_id = p_asset_id
      AND active = TRUE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_basis <> 'CONSENT' THEN
        RETURN TRUE;
    END IF;

    RETURN EXISTS (
        SELECT 1
        FROM consent_records
        WHERE asset_id = p_asset_id
          AND subject_reference = p_subject_reference
          AND status = 'GRANTED'
          AND (
              expires_at IS NULL
              OR expires_at > NOW()
          )
    );
END;
$$;

-- ============================================================================
-- SUBJECT REQUEST PROCESSING PROCEDURE
-- ============================================================================

CREATE PROCEDURE governance.transition_subject_request(
    p_request_id BIGINT,
    p_expected_version INTEGER,
    p_new_status request_status,
    p_actor_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_current_version INTEGER;
BEGIN
    SELECT version
    INTO v_current_version
    FROM subject_requests
    WHERE request_id = p_request_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Subject request not found.';
    END IF;

    IF v_current_version <> p_expected_version THEN
        RAISE EXCEPTION
            'Version conflict: expected %, actual %',
            p_expected_version,
            v_current_version;
    END IF;

    UPDATE subject_requests
    SET status = p_new_status
    WHERE request_id = p_request_id;

    PERFORM append_audit_event(
        p_actor_id,
        'REQUEST_TRANSITIONED',
        'SUBJECT_REQUEST',
        p_request_id::TEXT,
        jsonb_build_object('status', p_new_status)
    );
END;
$$;

-- ============================================================================
-- RETENTION REPORTING VIEW
-- ============================================================================

CREATE VIEW retention_status AS
SELECT
    a.asset_id,
    a.asset_code,
    a.asset_name,
    a.category,
    a.created_at,
    a.retention_days,
    a.created_at + make_interval(days => a.retention_days)
        AS retention_expiration,
    CASE
        WHEN NOW() >
            a.created_at + make_interval(days => a.retention_days)
        THEN 'EXPIRED'
        ELSE 'WITHIN_RETENTION'
    END AS retention_state
FROM data_assets a
WHERE a.active = TRUE;

-- ============================================================================
-- COMPLIANCE DASHBOARD VIEW
-- ============================================================================

CREATE VIEW compliance_dashboard AS
SELECT
    a.asset_id,
    a.asset_code,
    a.asset_name,
    a.category,
    a.basis,
    a.encrypted,
    a.active,
    COUNT(DISTINCT af.framework_id) AS framework_count,
    COUNT(DISTINCT cf.finding_id)
        FILTER (WHERE cf.resolved = FALSE) AS open_findings,
    COUNT(DISTINCT cr.consent_id)
        FILTER (
            WHERE cr.status = 'GRANTED'
              AND (
                  cr.expires_at IS NULL
                  OR cr.expires_at > NOW()
              )
        ) AS valid_consent_count
FROM data_assets a
LEFT JOIN asset_frameworks af
    ON af.asset_id = a.asset_id
LEFT JOIN compliance_findings cf
    ON cf.asset_id = a.asset_id
LEFT JOIN consent_records cr
    ON cr.asset_id = a.asset_id
GROUP BY
    a.asset_id,
    a.asset_code,
    a.asset_name,
    a.category,
    a.basis,
    a.encrypted,
    a.active;

-- ============================================================================
-- SAMPLE ASSETS
-- ============================================================================

INSERT INTO data_assets (
    organization_id,
    asset_code,
    asset_name,
    owner_user_id,
    category,
    purpose,
    basis,
    retention_days,
    encrypted
)
SELECT
    o.organization_id,
    x.asset_code,
    x.asset_name,
    u.user_id,
    x.category::privacy_category,
    x.purpose,
    x.basis::legal_basis,
    x.retention_days,
    x.encrypted
FROM (
    VALUES
    (
        'CUSTOMER-001',
        'Customer Identity Records',
        'PERSONAL',
        'Customer account administration',
        'CONSENT',
        730,
        TRUE
    ),
    (
        'INTERNAL-001',
        'Internal Operational Metrics',
        'INTERNAL',
        'Operational performance reporting',
        'LEGITIMATE_INTEREST',
        365,
        TRUE
    ),
    (
        'SENSITIVE-001',
        'Sensitive Health Records',
        'SENSITIVE_PERSONAL',
        'Healthcare administration',
        'CONTRACT',
        365,
        TRUE
    ),
    (
        'PUBLIC-001',
        'Public Product Catalogue',
        'PUBLIC',
        'Product publication',
        'PUBLIC_TASK',
        365,
        FALSE
    )
) AS x(
    asset_code,
    asset_name,
    category,
    purpose,
    basis,
    retention_days,
    encrypted
)
JOIN organizations o
    ON o.organization_name = 'Enterprise Data Governance Office'
JOIN governance_users u
    ON u.username = 'compliance_admin';

INSERT INTO asset_frameworks (asset_id, framework_id)
SELECT a.asset_id, f.framework_id
FROM data_assets a
JOIN regulatory_frameworks f
    ON f.code IN ('GDPR', 'DPDPA')
WHERE a.asset_code = 'CUSTOMER-001';

INSERT INTO asset_frameworks (asset_id, framework_id)
SELECT a.asset_id, f.framework_id
FROM data_assets a
JOIN regulatory_frameworks f
    ON f.code IN ('ISO27001')
WHERE a.asset_code IN ('INTERNAL-001', 'SENSITIVE-001');

INSERT INTO asset_frameworks (asset_id, framework_id)
SELECT a.asset_id, f.framework_id
FROM data_assets a
JOIN regulatory_frameworks f
    ON f.code = 'HIPAA'
WHERE a.asset_code = 'SENSITIVE-001';

-- ============================================================================
-- SAMPLE CONSENTS
-- ============================================================================

INSERT INTO consent_records (
    subject_reference,
    asset_id,
    purpose,
    status
)
SELECT
    'SUBJECT-001',
    asset_id,
    purpose,
    'GRANTED'
FROM data_assets
WHERE asset_code = 'CUSTOMER-001';

INSERT INTO consent_records (
    subject_reference,
    asset_id,
    purpose,
    status,
    withdrawn_at
)
SELECT
    'SUBJECT-002',
    asset_id,
    purpose,
    'WITHDRAWN',
    NOW()
FROM data_assets
WHERE asset_code = 'CUSTOMER-001';

-- ============================================================================
-- SAMPLE SUBJECT REQUESTS
-- ============================================================================

INSERT INTO subject_requests (
    request_reference,
    subject_reference,
    request_kind,
    status,
    deadline_at
)
VALUES
(
    'DSR-ACCESS-001',
    'SUBJECT-001',
    'ACCESS',
    'RECEIVED',
    NOW() + INTERVAL '30 days'
),
(
    'DSR-ERASURE-001',
    'SUBJECT-002',
    'ERASURE',
    'VERIFIED',
    NOW() + INTERVAL '30 days'
),
(
    'DSR-PORTABILITY-001',
    'SUBJECT-003',
    'PORTABILITY',
    'IN_PROGRESS',
    NOW() + INTERVAL '30 days'
);

-- ============================================================================
-- SAMPLE CONTROL ASSESSMENTS
-- ============================================================================

INSERT INTO compliance_assessments (
    asset_id,
    framework_id,
    assessor_id,
    assessment_notes
)
SELECT
    a.asset_id,
    f.framework_id,
    u.user_id,
    'Initial privacy and security control assessment.'
FROM data_assets a
JOIN regulatory_frameworks f
    ON f.code = 'ISO27001'
JOIN governance_users u
    ON u.username = 'internal_auditor'
WHERE a.asset_code = 'CUSTOMER-001';

INSERT INTO control_results (
    assessment_id,
    control_code,
    control_name,
    status,
    mandatory,
    evidence_reference
)
SELECT
    assessment_id,
    x.control_code,
    x.control_name,
    x.status::check_status,
    x.mandatory,
    x.evidence_reference
FROM compliance_assessments a
CROSS JOIN (
    VALUES
    (
        'ENC-001',
        'Encryption at rest',
        'PASSED',
        TRUE,
        'EVIDENCE-ENC-001'
    ),
    (
        'ACC-001',
        'Periodic access review',
        'PASSED',
        TRUE,
        'EVIDENCE-ACC-001'
    ),
    (
        'RET-001',
        'Retention verification',
        'FAILED',
        TRUE,
        'EVIDENCE-RET-001'
    ),
    (
        'DOC-001',
        'Optional documentation',
        'NOT_RUN',
        FALSE,
        NULL
    )
) AS x(
    control_code,
    control_name,
    status,
    mandatory,
    evidence_reference
)
WHERE a.assessment_notes LIKE 'Initial privacy%';

-- ============================================================================
-- SAMPLE FINDINGS
-- ============================================================================

INSERT INTO compliance_findings (
    asset_id,
    policy_id,
    severity,
    description
)
SELECT
    a.asset_id,
    p.policy_id,
    'MEDIUM',
    'Retention schedule requires documented justification.'
FROM data_assets a
JOIN governance_policies p
    ON p.policy_code = 'POLICY-PERSONAL-001'
WHERE a.asset_code = 'CUSTOMER-001';

-- ============================================================================
-- AUDIT EXAMPLES
-- ============================================================================

SELECT append_audit_event(
    u.user_id,
    'ASSET_REGISTERED',
    'DATA_ASSET',
    a.asset_code,
    jsonb_build_object(
        'category', a.category,
        'encrypted', a.encrypted
    )
)
FROM governance_users u
CROSS JOIN data_assets a
WHERE u.username = 'compliance_admin'
  AND a.asset_code = 'CUSTOMER-001';

-- ============================================================================
-- VALIDATION AND RETRIEVAL QUERIES
-- ============================================================================

-- 1. Retrieve classified assets and framework mappings.
SELECT
    a.asset_code,
    a.asset_name,
    a.category,
    a.basis,
    a.encrypted,
    f.code AS framework_code,
    f.jurisdiction
FROM data_assets a
LEFT JOIN asset_frameworks af
    ON af.asset_id = a.asset_id
LEFT JOIN regulatory_frameworks f
    ON f.framework_id = af.framework_id
ORDER BY a.asset_code, f.code;

-- 2. Evaluate whether processing is authorized.
SELECT
    asset_code,
    governance.can_process_asset(
        asset_id,
        'SUBJECT-001'
    ) AS subject_001_authorized,
    governance.can_process_asset(
        asset_id,
        'SUBJECT-002'
    ) AS subject_002_authorized
FROM data_assets
WHERE asset_code = 'CUSTOMER-001';

-- 3. Check expired retention.
SELECT *
FROM retention_status
WHERE retention_state = 'EXPIRED';

-- 4. Find overdue subject requests.
SELECT
    request_reference,
    subject_reference,
    request_kind,
    status,
    deadline_at
FROM subject_requests
WHERE deadline_at < NOW()
  AND status NOT IN ('COMPLETED', 'REJECTED');

-- 5. Aggregate data classifications.
SELECT
    category,
    COUNT(*) AS asset_count,
    COUNT(*) FILTER (WHERE encrypted) AS encrypted_count,
    COUNT(*) FILTER (WHERE active) AS active_count
FROM data_assets
GROUP BY category
ORDER BY category;

-- 6. Compliance findings by severity.
SELECT
    severity,
    COUNT(*) AS finding_count,
    COUNT(*) FILTER (WHERE NOT resolved) AS unresolved_count
FROM compliance_findings
GROUP BY severity
ORDER BY severity;

-- 7. Control failure reporting.
SELECT
    a.asset_code,
    c.control_code,
    c.control_name,
    c.status,
    c.mandatory
FROM control_results c
JOIN compliance_assessments ca
    ON ca.assessment_id = c.assessment_id
JOIN data_assets a
    ON a.asset_id = ca.asset_id
WHERE c.status = 'FAILED'
ORDER BY a.asset_code;

-- 8. Regulatory coverage.
SELECT
    f.code,
    f.jurisdiction,
    COUNT(DISTINCT af.asset_id) AS mapped_assets
FROM regulatory_frameworks f
LEFT JOIN asset_frameworks af
    ON af.framework_id = f.framework_id
GROUP BY f.framework_id, f.code, f.jurisdiction
ORDER BY f.code;

-- 9. Governance dashboard.
SELECT *
FROM compliance_dashboard
ORDER BY asset_code;

-- 10. Eligibility determination.
SELECT
    a.asset_code,
    e.decision,
    e.blockers,
    e.warnings
FROM data_assets a
CROSS JOIN LATERAL
    governance.evaluate_asset_eligibility(a.asset_id) e
ORDER BY a.asset_code;

-- ============================================================================
-- TRANSACTIONAL WORKFLOW EXAMPLE
-- ============================================================================

DO $$
DECLARE
    v_request_id BIGINT;
    v_actor_id BIGINT;
    v_version INTEGER;
BEGIN
    SELECT user_id
    INTO v_actor_id
    FROM governance_users
    WHERE username = 'privacy_officer';

    SELECT request_id, version
    INTO v_request_id, v_version
    FROM subject_requests
    WHERE request_reference = 'DSR-ACCESS-001'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Sample request not found.';
    END IF;

    CALL governance.transition_subject_request(
        v_request_id,
        v_version,
        'VERIFIED',
        v_actor_id
    );

    RAISE NOTICE 'Subject request verified: %', v_request_id;
END;
$$;

-- ============================================================================
-- RETENTION ENFORCEMENT
-- ============================================================================

CREATE PROCEDURE governance.deactivate_expired_assets(
    p_actor_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_asset RECORD;
BEGIN
    FOR v_asset IN
        SELECT asset_id, asset_code
        FROM data_assets
        WHERE active = TRUE
          AND NOW() >
              created_at + make_interval(days => retention_days)
        FOR UPDATE
    LOOP
        UPDATE data_assets
        SET active = FALSE
        WHERE asset_id = v_asset.asset_id;

        PERFORM append_audit_event(
            p_actor_id,
            'RETENTION_EXPIRED',
            'DATA_ASSET',
            v_asset.asset_code,
            jsonb_build_object(
                'reason', 'Retention period elapsed'
            )
        );
    END LOOP;
END;
$$;

-- ============================================================================
-- AUDIT INTEGRITY REPORT
-- ============================================================================

SELECT governance.verify_audit_chain() AS audit_chain_valid;

-- ============================================================================
-- FINAL GOVERNANCE REPORT
-- ============================================================================

SELECT
    COUNT(*) AS total_assets,
    COUNT(*) FILTER (WHERE active) AS active_assets,
    COUNT(*) FILTER (
        WHERE category IN ('PERSONAL', 'SENSITIVE_PERSONAL')
    ) AS personal_data_assets,
    COUNT(*) FILTER (
        WHERE encrypted
    ) AS encrypted_assets
FROM data_assets;

SELECT
    status,
    COUNT(*) AS request_count
FROM subject_requests
GROUP BY status
ORDER BY status;

SELECT
    action,
    COUNT(*) AS event_count
FROM audit_events
GROUP BY action
ORDER BY action;

COMMIT;
