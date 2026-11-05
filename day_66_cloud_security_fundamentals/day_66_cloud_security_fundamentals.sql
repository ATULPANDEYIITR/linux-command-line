-- ============================================================
-- CLOUD SECURITY FUNDAMENTALS
-- Shared Responsibility Model and Cloud Security Governance
-- PostgreSQL 15+
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS cloud_security;

SET search_path TO cloud_security, public;

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE service_model AS ENUM (
    'IAAS',
    'PAAS',
    'SAAS'
);

CREATE TYPE responsibility_type AS ENUM (
    'PROVIDER',
    'CUSTOMER',
    'SHARED'
);

CREATE TYPE security_domain AS ENUM (
    'PHYSICAL_SECURITY',
    'NETWORK_SECURITY',
    'HOST_INFRASTRUCTURE',
    'OPERATING_SYSTEM',
    'APPLICATION_SECURITY',
    'IDENTITY_AND_ACCESS',
    'DATA_PROTECTION',
    'CONFIGURATION',
    'COMPLIANCE',
    'BACKUP_AND_RECOVERY'
);

CREATE TYPE finding_severity AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE finding_status AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'RESOLVED',
    'ACCEPTED'
);

CREATE TYPE control_status AS ENUM (
    'NOT_ASSESSED',
    'COMPLIANT',
    'NON_COMPLIANT',
    'NOT_APPLICABLE'
);

-- ============================================================
-- CLOUD PROVIDERS
-- ============================================================

CREATE TABLE cloud_providers (
    provider_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider_name VARCHAR(120) NOT NULL UNIQUE,
    provider_region VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- USERS AND ACCESS MANAGEMENT
-- ============================================================

CREATE TABLE security_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(50) NOT NULL,
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_role CHECK (
        role IN (
            'SECURITY_ANALYST',
            'CLOUD_ADMIN',
            'AUDITOR',
            'APPLICATION_OWNER',
            'READ_ONLY'
        )
    )
);

-- ============================================================
-- CLOUD RESOURCES
-- ============================================================

CREATE TABLE cloud_resources (
    resource_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    provider_id BIGINT NOT NULL
        REFERENCES cloud_providers(provider_id),

    resource_name VARCHAR(150) NOT NULL,

    resource_type VARCHAR(80) NOT NULL,

    service_model service_model NOT NULL,

    region VARCHAR(100) NOT NULL,

    owner_id BIGINT NOT NULL
        REFERENCES security_users(user_id),

    environment VARCHAR(30) NOT NULL,

    encrypted_at_rest BOOLEAN NOT NULL DEFAULT FALSE,

    encrypted_in_transit BOOLEAN NOT NULL DEFAULT FALSE,

    publicly_accessible BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_environment CHECK (
        environment IN ('DEVELOPMENT', 'TESTING', 'STAGING', 'PRODUCTION')
    ),

    CONSTRAINT unique_resource_name
        UNIQUE (provider_id, resource_name, region)
);

-- ============================================================
-- SHARED RESPONSIBILITY MATRIX
-- ============================================================

CREATE TABLE responsibility_matrix (
    responsibility_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_model service_model NOT NULL,

    domain security_domain NOT NULL,

    responsible_party responsibility_type NOT NULL,

    control_description TEXT NOT NULL,

    CONSTRAINT unique_model_domain
        UNIQUE (service_model, domain)
);

-- ============================================================
-- SECURITY CONTROL CATALOG
-- ============================================================

CREATE TABLE security_controls (
    control_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    control_code VARCHAR(40) NOT NULL UNIQUE,

    control_name VARCHAR(150) NOT NULL,

    domain security_domain NOT NULL,

    description TEXT NOT NULL,

    mandatory BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- RESOURCE CONTROL ASSESSMENTS
-- ============================================================

CREATE TABLE control_assessments (
    assessment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_id BIGINT NOT NULL
        REFERENCES cloud_resources(resource_id),

    control_id BIGINT NOT NULL
        REFERENCES security_controls(control_id),

    assessed_by BIGINT NOT NULL
        REFERENCES security_users(user_id),

    status control_status NOT NULL DEFAULT 'NOT_ASSESSED',

    evidence_reference TEXT,

    assessment_notes TEXT,

    assessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_resource_control
        UNIQUE (resource_id, control_id)
);

-- ============================================================
-- SECURITY FINDINGS
-- ============================================================

CREATE TABLE security_findings (
    finding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_id BIGINT NOT NULL
        REFERENCES cloud_resources(resource_id),

    domain security_domain NOT NULL,

    severity finding_severity NOT NULL,

    status finding_status NOT NULL DEFAULT 'OPEN',

    finding_title VARCHAR(200) NOT NULL,

    description TEXT NOT NULL,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    assigned_to BIGINT
        REFERENCES security_users(user_id),

    resolved_at TIMESTAMPTZ,

    CONSTRAINT resolved_timestamp_consistency CHECK (
        (status = 'RESOLVED' AND resolved_at IS NOT NULL)
        OR
        (status <> 'RESOLVED' AND resolved_at IS NULL)
    )
);

-- ============================================================
-- SECURITY AUDIT EVENTS
-- ============================================================

CREATE TABLE security_audit_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id BIGINT REFERENCES security_users(user_id),

    resource_id BIGINT REFERENCES cloud_resources(resource_id),

    event_type VARCHAR(100) NOT NULL,

    event_description TEXT NOT NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_resources_service_model
    ON cloud_resources(service_model);

CREATE INDEX idx_resources_environment
    ON cloud_resources(environment);

CREATE INDEX idx_findings_resource_status
    ON security_findings(resource_id, status);

CREATE INDEX idx_findings_severity
    ON security_findings(severity, detected_at DESC);

CREATE INDEX idx_assessments_status
    ON control_assessments(status, assessed_at DESC);

CREATE INDEX idx_audit_resource_time
    ON security_audit_events(resource_id, occurred_at DESC);

-- ============================================================
-- RESPONSIBILITY MATRIX DATA
-- ============================================================

INSERT INTO responsibility_matrix
(service_model, domain, responsible_party, control_description)
VALUES

-- Infrastructure as a Service

('IAAS', 'PHYSICAL_SECURITY', 'PROVIDER',
 'Provider manages physical facilities and hardware security'),

('IAAS', 'HOST_INFRASTRUCTURE', 'PROVIDER',
 'Provider manages physical hosts and virtualization infrastructure'),

('IAAS', 'NETWORK_SECURITY', 'SHARED',
 'Provider secures underlying networks while customer configures network controls'),

('IAAS', 'OPERATING_SYSTEM', 'CUSTOMER',
 'Customer manages guest operating system updates and hardening'),

('IAAS', 'APPLICATION_SECURITY', 'CUSTOMER',
 'Customer secures applications deployed on infrastructure'),

('IAAS', 'IDENTITY_AND_ACCESS', 'CUSTOMER',
 'Customer manages identities and resource permissions'),

('IAAS', 'DATA_PROTECTION', 'CUSTOMER',
 'Customer manages data classification and encryption configuration'),

('IAAS', 'CONFIGURATION', 'CUSTOMER',
 'Customer configures virtual infrastructure securely'),

('IAAS', 'COMPLIANCE', 'SHARED',
 'Provider and customer maintain their respective compliance obligations'),

('IAAS', 'BACKUP_AND_RECOVERY', 'CUSTOMER',
 'Customer configures backups and recovery procedures'),

-- Platform as a Service

('PAAS', 'PHYSICAL_SECURITY', 'PROVIDER',
 'Provider protects physical infrastructure'),

('PAAS', 'HOST_INFRASTRUCTURE', 'PROVIDER',
 'Provider manages hosts and virtualization'),

('PAAS', 'NETWORK_SECURITY', 'SHARED',
 'Provider secures platform networking while customer configures access'),

('PAAS', 'OPERATING_SYSTEM', 'PROVIDER',
 'Provider manages underlying operating systems'),

('PAAS', 'APPLICATION_SECURITY', 'CUSTOMER',
 'Customer secures application code and dependencies'),

('PAAS', 'IDENTITY_AND_ACCESS', 'SHARED',
 'Provider supplies identity capabilities while customer manages access policies'),

('PAAS', 'DATA_PROTECTION', 'CUSTOMER',
 'Customer classifies and protects application data'),

('PAAS', 'CONFIGURATION', 'SHARED',
 'Provider secures platform configuration while customer configures workloads'),

('PAAS', 'COMPLIANCE', 'SHARED',
 'Both parties maintain applicable compliance responsibilities'),

('PAAS', 'BACKUP_AND_RECOVERY', 'SHARED',
 'Provider supplies platform capabilities while customer configures retention'),

-- Software as a Service

('SAAS', 'PHYSICAL_SECURITY', 'PROVIDER',
 'Provider manages facilities and physical infrastructure'),

('SAAS', 'HOST_INFRASTRUCTURE', 'PROVIDER',
 'Provider manages computing infrastructure'),

('SAAS', 'NETWORK_SECURITY', 'PROVIDER',
 'Provider manages application hosting network security'),

('SAAS', 'OPERATING_SYSTEM', 'PROVIDER',
 'Provider manages operating systems'),

('SAAS', 'APPLICATION_SECURITY', 'PROVIDER',
 'Provider manages application platform security'),

('SAAS', 'IDENTITY_AND_ACCESS', 'SHARED',
 'Provider supplies authentication features while customer manages users'),

('SAAS', 'DATA_PROTECTION', 'SHARED',
 'Provider protects platform data while customer manages classification and usage'),

('SAAS', 'CONFIGURATION', 'SHARED',
 'Provider secures platform while customer configures tenant settings'),

('SAAS', 'COMPLIANCE', 'SHARED',
 'Both parties maintain their respective compliance obligations'),

('SAAS', 'BACKUP_AND_RECOVERY', 'SHARED',
 'Provider manages platform recovery while customer verifies retention and export requirements');

-- ============================================================
-- CLOUD PROVIDERS
-- ============================================================

INSERT INTO cloud_providers
(provider_name, provider_region)
VALUES
('Example Cloud Provider', 'ap-south-1'),
('Enterprise SaaS Provider', 'ap-south-1');

-- ============================================================
-- SECURITY USERS
-- ============================================================

INSERT INTO security_users
(username, email, role, mfa_enabled)
VALUES
('cloud_admin', 'admin@example.com', 'CLOUD_ADMIN', TRUE),
('security_analyst', 'analyst@example.com', 'SECURITY_ANALYST', TRUE),
('auditor', 'auditor@example.com', 'AUDITOR', TRUE),
('application_owner', 'owner@example.com', 'APPLICATION_OWNER', TRUE),
('legacy_account', 'legacy@example.com', 'READ_ONLY', FALSE);

-- ============================================================
-- CLOUD RESOURCES
-- ============================================================

INSERT INTO cloud_resources
(
    provider_id,
    resource_name,
    resource_type,
    service_model,
    region,
    owner_id,
    environment,
    encrypted_at_rest,
    encrypted_in_transit,
    publicly_accessible
)
VALUES

(
    1,
    'production-vm',
    'VIRTUAL_MACHINE',
    'IAAS',
    'ap-south-1',
    4,
    'PRODUCTION',
    TRUE,
    TRUE,
    FALSE
),

(
    1,
    'customer-api',
    'MANAGED_APPLICATION',
    'PAAS',
    'ap-south-1',
    4,
    'PRODUCTION',
    TRUE,
    TRUE,
    FALSE
),

(
    2,
    'enterprise-crm',
    'BUSINESS_APPLICATION',
    'SAAS',
    'ap-south-1',
    4,
    'PRODUCTION',
    TRUE,
    TRUE,
    FALSE
),

(
    1,
    'development-storage',
    'OBJECT_STORAGE',
    'IAAS',
    'ap-south-1',
    4,
    'DEVELOPMENT',
    FALSE,
    TRUE,
    TRUE
);

-- ============================================================
-- SECURITY CONTROL CATALOG
-- ============================================================

INSERT INTO security_controls
(control_code, control_name, domain, description)
VALUES

('IAM-001', 'Multi-factor authentication',
 'IDENTITY_AND_ACCESS', 'Require MFA for privileged accounts'),

('IAM-002', 'Least privilege access',
 'IDENTITY_AND_ACCESS', 'Grant only required permissions'),

('NET-001', 'Network segmentation',
 'NETWORK_SECURITY', 'Separate workloads using network boundaries'),

('NET-002', 'Restrict public exposure',
 'NETWORK_SECURITY', 'Prevent unintended public network access'),

('DAT-001', 'Encryption at rest',
 'DATA_PROTECTION', 'Encrypt stored sensitive information'),

('DAT-002', 'Encryption in transit',
 'DATA_PROTECTION', 'Protect data using secure transport protocols'),

('OS-001', 'Operating system patching',
 'OPERATING_SYSTEM', 'Maintain supported and patched operating systems'),

('APP-001', 'Application security testing',
 'APPLICATION_SECURITY', 'Identify application vulnerabilities'),

('CFG-001', 'Secure configuration',
 'CONFIGURATION', 'Apply approved security configurations'),

('BKP-001', 'Backup validation',
 'BACKUP_AND_RECOVERY', 'Validate backup integrity and restoration'),

('CMP-001', 'Compliance evidence',
 'COMPLIANCE', 'Maintain evidence of applicable security controls');

-- ============================================================
-- CONTROL ASSESSMENTS
-- ============================================================

INSERT INTO control_assessments
(resource_id, control_id, assessed_by, status, assessment_notes)
VALUES

(1, 1, 2, 'COMPLIANT', 'MFA enabled for privileged identities'),

(1, 2, 2, 'COMPLIANT', 'Role-based access reviewed'),

(1, 7, 2, 'NON_COMPLIANT', 'Operating system patches are overdue'),

(2, 8, 2, 'COMPLIANT', 'Application security testing completed'),

(2, 9, 2, 'COMPLIANT', 'Platform configuration reviewed'),

(3, 1, 3, 'COMPLIANT', 'Tenant administrator MFA enabled'),

(4, 4, 2, 'NON_COMPLIANT', 'Development storage is publicly accessible'),

(4, 5, 2, 'NON_COMPLIANT', 'Encryption at rest is disabled');

-- ============================================================
-- SECURITY FINDINGS
-- ============================================================

INSERT INTO security_findings
(
    resource_id,
    domain,
    severity,
    status,
    finding_title,
    description,
    assigned_to
)
VALUES

(
    1,
    'OPERATING_SYSTEM',
    'CRITICAL',
    'OPEN',
    'Unpatched production operating system',
    'Critical operating system security updates are overdue.',
    2
),

(
    1,
    'NETWORK_SECURITY',
    'HIGH',
    'IN_PROGRESS',
    'Excessive inbound network access',
    'Network rules permit unnecessary inbound connections.',
    2
),

(
    4,
    'DATA_PROTECTION',
    'CRITICAL',
    'OPEN',
    'Unencrypted object storage',
    'Sensitive development data is stored without encryption at rest.',
    2
),

(
    4,
    'CONFIGURATION',
    'HIGH',
    'OPEN',
    'Public storage exposure',
    'Object storage permits unintended public access.',
    4
),

(
    3,
    'IDENTITY_AND_ACCESS',
    'MEDIUM',
    'RESOLVED',
    'Excessive tenant permissions',
    'An unnecessary tenant permission was removed.',
    2
);

-- ============================================================
-- AUDIT EVENTS
-- ============================================================

INSERT INTO security_audit_events
(user_id, resource_id, event_type, event_description)
VALUES

(1, 1, 'RESOURCE_REVIEW',
 'Production virtual machine security review initiated'),

(2, 4, 'SECURITY_FINDING',
 'Public storage exposure identified'),

(3, 3, 'COMPLIANCE_REVIEW',
 'SaaS tenant access configuration reviewed');

-- ============================================================
-- FUNCTION: DETERMINE RESPONSIBILITY
-- ============================================================

CREATE OR REPLACE FUNCTION get_responsibility(
    p_model service_model,
    p_domain security_domain
)
RETURNS responsibility_type
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_responsibility responsibility_type;
BEGIN
    SELECT responsible_party
    INTO v_responsibility
    FROM responsibility_matrix
    WHERE service_model = p_model
      AND domain = p_domain;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Responsibility mapping not found for model % and domain %',
            p_model, p_domain;
    END IF;

    RETURN v_responsibility;
END;
$$;

-- ============================================================
-- FUNCTION: RESOURCE SECURITY EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_resource_security(
    p_resource_id BIGINT
)
RETURNS TABLE (
    domain_name security_domain,
    responsible_party responsibility_type,
    total_controls BIGINT,
    compliant_controls BIGINT,
    non_compliant_controls BIGINT,
    unassessed_controls BIGINT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_model service_model;
BEGIN
    SELECT service_model
    INTO v_model
    FROM cloud_resources
    WHERE resource_id = p_resource_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown resource ID: %', p_resource_id;
    END IF;

    RETURN QUERY
    SELECT
        sc.domain,
        rm.responsible_party,
        COUNT(sc.control_id),
        COUNT(*) FILTER (
            WHERE ca.status = 'COMPLIANT'
        ),
        COUNT(*) FILTER (
            WHERE ca.status = 'NON_COMPLIANT'
        ),
        COUNT(*) FILTER (
            WHERE ca.assessment_id IS NULL
               OR ca.status = 'NOT_ASSESSED'
        )
    FROM security_controls sc
    JOIN responsibility_matrix rm
      ON rm.service_model = v_model
     AND rm.domain = sc.domain
    LEFT JOIN control_assessments ca
      ON ca.control_id = sc.control_id
     AND ca.resource_id = p_resource_id
    GROUP BY sc.domain, rm.responsible_party
    ORDER BY sc.domain;
END;
$$;

-- ============================================================
-- FUNCTION: RECORD SECURITY FINDING
-- ============================================================

CREATE OR REPLACE FUNCTION record_security_finding(
    p_resource_id BIGINT,
    p_domain security_domain,
    p_severity finding_severity,
    p_title VARCHAR,
    p_description TEXT,
    p_assigned_to BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_finding_id BIGINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM cloud_resources
        WHERE resource_id = p_resource_id
    ) THEN
        RAISE EXCEPTION 'Resource does not exist';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM responsibility_matrix rm
        JOIN cloud_resources cr
          ON cr.service_model = rm.service_model
        WHERE cr.resource_id = p_resource_id
          AND rm.domain = p_domain
    ) THEN
        RAISE EXCEPTION 'No responsibility mapping exists';
    END IF;

    INSERT INTO security_findings (
        resource_id,
        domain,
        severity,
        finding_title,
        description,
        assigned_to
    )
    VALUES (
        p_resource_id,
        p_domain,
        p_severity,
        p_title,
        p_description,
        p_assigned_to
    )
    RETURNING finding_id INTO v_finding_id;

    RETURN v_finding_id;
END;
$$;

-- ============================================================
-- PROCEDURE: RESOLVE SECURITY FINDING
-- ============================================================

CREATE OR REPLACE PROCEDURE resolve_security_finding(
    p_finding_id BIGINT,
    p_user_id BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM security_users
        WHERE user_id = p_user_id
          AND active = TRUE
          AND role IN ('CLOUD_ADMIN', 'SECURITY_ANALYST')
          AND mfa_enabled = TRUE
    ) THEN
        RAISE EXCEPTION
            'User is inactive, lacks the required role, or has MFA disabled';
    END IF;

    UPDATE security_findings
    SET status = 'RESOLVED',
        resolved_at = CURRENT_TIMESTAMP
    WHERE finding_id = p_finding_id
      AND status IN ('OPEN', 'IN_PROGRESS');

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Finding not found or cannot be resolved from its current state';
    END IF;

    INSERT INTO security_audit_events (
        user_id,
        event_type,
        event_description
    )
    VALUES (
        p_user_id,
        'FINDING_RESOLVED',
        'Security finding ' || p_finding_id || ' resolved'
    );
END;
$$;

-- ============================================================
-- TRIGGER: FINDING STATUS CONSISTENCY
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_finding_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status IN ('RESOLVED', 'ACCEPTED')
       AND NEW.status <> OLD.status THEN
        RAISE EXCEPTION
            'Closed findings cannot be reopened or changed';
    END IF;

    IF NEW.status = 'RESOLVED'
       AND NEW.resolved_at IS NULL THEN
        NEW.resolved_at := CURRENT_TIMESTAMP;
    END IF;

    IF NEW.status <> 'RESOLVED' THEN
        NEW.resolved_at := NULL;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_finding_status
BEFORE UPDATE ON security_findings
FOR EACH ROW
EXECUTE FUNCTION enforce_finding_status();

-- ============================================================
-- TRIGGER: CONTROL ASSESSMENT AUDIT
-- ============================================================

CREATE OR REPLACE FUNCTION audit_control_assessment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO security_audit_events (
        user_id,
        resource_id,
        event_type,
        event_description
    )
    VALUES (
        NEW.assessed_by,
        NEW.resource_id,
        'CONTROL_ASSESSMENT',
        'Control ' || NEW.control_id ||
        ' assessed as ' || NEW.status
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_control_assessment_audit
AFTER INSERT OR UPDATE ON control_assessments
FOR EACH ROW
EXECUTE FUNCTION audit_control_assessment();

-- ============================================================
-- VIEW: RESOURCE SECURITY OVERVIEW
-- ============================================================

CREATE OR REPLACE VIEW resource_security_overview AS
SELECT
    cr.resource_id,
    cr.resource_name,
    cr.service_model,
    cr.environment,
    cr.region,
    cr.publicly_accessible,
    cr.encrypted_at_rest,
    cr.encrypted_in_transit,

    COUNT(DISTINCT sf.finding_id) AS total_findings,

    COUNT(DISTINCT sf.finding_id) FILTER (
        WHERE sf.severity = 'CRITICAL'
          AND sf.status IN ('OPEN', 'IN_PROGRESS')
    ) AS unresolved_critical_findings,

    COUNT(DISTINCT ca.assessment_id) FILTER (
        WHERE ca.status = 'COMPLIANT'
    ) AS compliant_assessments,

    COUNT(DISTINCT ca.assessment_id) FILTER (
        WHERE ca.status = 'NON_COMPLIANT'
    ) AS non_compliant_assessments

FROM cloud_resources cr

LEFT JOIN security_findings sf
    ON sf.resource_id = cr.resource_id

LEFT JOIN control_assessments ca
    ON ca.resource_id = cr.resource_id

GROUP BY
    cr.resource_id,
    cr.resource_name,
    cr.service_model,
    cr.environment,
    cr.region,
    cr.publicly_accessible,
    cr.encrypted_at_rest,
    cr.encrypted_in_transit;

-- ============================================================
-- VIEW: OPEN SECURITY FINDINGS
-- ============================================================

CREATE OR REPLACE VIEW open_security_findings AS
SELECT
    sf.finding_id,
    cr.resource_name,
    cr.service_model,
    sf.domain,
    sf.severity,
    sf.status,
    sf.finding_title,
    sf.detected_at,
    su.username AS assigned_user
FROM security_findings sf
JOIN cloud_resources cr
    ON cr.resource_id = sf.resource_id
LEFT JOIN security_users su
    ON su.user_id = sf.assigned_to
WHERE sf.status IN ('OPEN', 'IN_PROGRESS');

-- ============================================================
-- VIEW: RESPONSIBILITY REPORT
-- ============================================================

CREATE OR REPLACE VIEW responsibility_report AS
SELECT
    cr.resource_id,
    cr.resource_name,
    cr.service_model,
    rm.domain,
    rm.responsible_party,
    rm.control_description
FROM cloud_resources cr
JOIN responsibility_matrix rm
    ON rm.service_model = cr.service_model;

-- ============================================================
-- QUERY 1: RETRIEVE CLOUD RESOURCES
-- ============================================================

SELECT
    resource_name,
    service_model,
    environment,
    region,
    publicly_accessible
FROM cloud_resources
ORDER BY resource_id;

-- ============================================================
-- QUERY 2: COMPARE RESPONSIBILITIES
-- ============================================================

SELECT
    domain,
    MAX(responsible_party::TEXT)
        FILTER (WHERE service_model = 'IAAS') AS iaas,
    MAX(responsible_party::TEXT)
        FILTER (WHERE service_model = 'PAAS') AS paas,
    MAX(responsible_party::TEXT)
        FILTER (WHERE service_model = 'SAAS') AS saas
FROM responsibility_matrix
GROUP BY domain
ORDER BY domain;

-- ============================================================
-- QUERY 3: RESOURCE SECURITY REPORT
-- ============================================================

SELECT *
FROM resource_security_overview
ORDER BY unresolved_critical_findings DESC;

-- ============================================================
-- QUERY 4: FIND UNRESOLVED CRITICAL ISSUES
-- ============================================================

SELECT
    finding_id,
    resource_name,
    finding_title,
    detected_at
FROM open_security_findings
WHERE severity = 'CRITICAL'
ORDER BY detected_at;

-- ============================================================
-- QUERY 5: CONTROL COMPLIANCE AGGREGATION
-- ============================================================

SELECT
    cr.resource_name,
    ca.status,
    COUNT(*) AS assessment_count
FROM control_assessments ca
JOIN cloud_resources cr
    ON cr.resource_id = ca.resource_id
GROUP BY cr.resource_name, ca.status
ORDER BY cr.resource_name, ca.status;

-- ============================================================
-- QUERY 6: IDENTIFY PUBLIC PRODUCTION RESOURCES
-- ============================================================

SELECT
    resource_name,
    service_model,
    region
FROM cloud_resources
WHERE environment = 'PRODUCTION'
  AND publicly_accessible = TRUE;

-- ============================================================
-- QUERY 7: IDENTIFY MISSING ENCRYPTION
-- ============================================================

SELECT
    resource_name,
    service_model,
    encrypted_at_rest,
    encrypted_in_transit
FROM cloud_resources
WHERE encrypted_at_rest = FALSE
   OR encrypted_in_transit = FALSE;

-- ============================================================
-- QUERY 8: EVALUATE RESOURCE RESPONSIBILITIES
-- ============================================================

SELECT *
FROM evaluate_resource_security(1);

-- ============================================================
-- QUERY 9: SECURITY FINDING AGGREGATION
-- ============================================================

SELECT
    severity,
    status,
    COUNT(*) AS finding_count
FROM security_findings
GROUP BY severity, status
ORDER BY severity, status;

-- ============================================================
-- QUERY 10: RESPONSIBILITY-BASED FINDING REVIEW
-- ============================================================

SELECT
    sf.finding_id,
    cr.resource_name,
    sf.domain,
    rm.responsible_party,
    sf.severity,
    sf.finding_title
FROM security_findings sf
JOIN cloud_resources cr
    ON cr.resource_id = sf.resource_id
JOIN responsibility_matrix rm
    ON rm.service_model = cr.service_model
   AND rm.domain = sf.domain
ORDER BY sf.detected_at DESC;

-- ============================================================
-- QUERY 11: UNASSESSED MANDATORY CONTROLS
-- ============================================================

SELECT
    cr.resource_name,
    sc.control_code,
    sc.control_name,
    sc.domain
FROM cloud_resources cr
CROSS JOIN security_controls sc
LEFT JOIN control_assessments ca
    ON ca.resource_id = cr.resource_id
   AND ca.control_id = sc.control_id
WHERE sc.mandatory = TRUE
  AND (
      ca.assessment_id IS NULL
      OR ca.status = 'NOT_ASSESSED'
  )
ORDER BY cr.resource_name, sc.control_code;

-- ============================================================
-- QUERY 12: SECURITY AUDIT HISTORY
-- ============================================================

SELECT
    event_id,
    event_type,
    event_description,
    occurred_at
FROM security_audit_events
ORDER BY occurred_at DESC;

-- ============================================================
-- TRANSACTION: CREATE AND RESOLVE A FINDING
-- ============================================================

SAVEPOINT before_workflow;

DO $$
DECLARE
    v_finding_id BIGINT;
BEGIN
    v_finding_id := record_security_finding(
        2,
        'APPLICATION_SECURITY',
        'MEDIUM',
        'Application dependency review',
        'A dependency review is required for the application.',
        2
    );

    RAISE NOTICE 'Created finding ID: %', v_finding_id;
END;
$$;

-- The transaction can be rolled back to the savepoint if needed.
-- Existing sample records remain unaffected.

RELEASE SAVEPOINT before_workflow;

COMMIT;

-- ============================================================
-- FINAL REPORT
-- ============================================================

SELECT
    service_model,
    COUNT(*) AS resource_count,
    COUNT(*) FILTER (
        WHERE publicly_accessible = TRUE
    ) AS public_resources,
    COUNT(*) FILTER (
        WHERE encrypted_at_rest = FALSE
    ) AS unencrypted_resources
FROM cloud_resources
GROUP BY service_model
ORDER BY service_model;
