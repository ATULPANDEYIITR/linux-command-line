-- ============================================================
-- CONTAINER SECURITY GOVERNANCE DATABASE
-- PostgreSQL 15+
--
-- Domains:
-- 1. Container image inventory
-- 2. Image scanning and vulnerability management
-- 3. Secret detection
-- 4. Minimal image and configuration compliance
-- 5. Runtime security monitoring
-- 6. Security policies
-- 7. Deployment authorization
-- 8. Vulnerability remediation
-- 9. Audit and reporting
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS container_security;

SET search_path TO container_security, public;

-- ============================================================
-- 1. ENUMERATIONS
-- ============================================================

CREATE TYPE severity_level AS ENUM (
    'CRITICAL',
    'HIGH',
    'MEDIUM',
    'LOW',
    'INFO'
);

CREATE TYPE finding_type AS ENUM (
    'VULNERABILITY',
    'SECRET',
    'MISCONFIGURATION',
    'COMPLIANCE'
);

CREATE TYPE deployment_status AS ENUM (
    'APPROVED',
    'BLOCKED',
    'REVIEW_REQUIRED'
);

CREATE TYPE remediation_status AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'MITIGATED',
    'RESOLVED',
    'ACCEPTED_RISK'
);

CREATE TYPE runtime_event_type AS ENUM (
    'PROCESS_EXECUTION',
    'FILE_MODIFICATION',
    'NETWORK_CONNECTION',
    'PRIVILEGE_CHANGE',
    'UNKNOWN'
);

-- ============================================================
-- 2. REPOSITORIES AND OWNERS
-- ============================================================

CREATE TABLE security_teams (
    team_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_name VARCHAR(120) NOT NULL UNIQUE,
    contact_email VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (team_name <> ''),
    CHECK (contact_email ~ '^[^@ ]+@[^@ ]+\.[^@ ]+$')
);

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_id BIGINT NOT NULL REFERENCES security_teams(team_id),
    repository_name VARCHAR(200) NOT NULL,
    repository_url TEXT NOT NULL,
    criticality VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (team_id, repository_name),

    CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
);

-- ============================================================
-- 3. IMAGE INVENTORY
-- ============================================================

CREATE TABLE container_images (
    image_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id),

    image_name VARCHAR(255) NOT NULL,
    image_tag VARCHAR(100) NOT NULL,
    image_digest VARCHAR(71),

    base_image VARCHAR(255) NOT NULL,

    image_size_mb NUMERIC(12,2) NOT NULL,
    layer_count INTEGER NOT NULL,

    runtime_user VARCHAR(100) NOT NULL DEFAULT 'root',

    signed BOOLEAN NOT NULL DEFAULT FALSE,
    signature_verified BOOLEAN NOT NULL DEFAULT FALSE,

    healthcheck_configured BOOLEAN NOT NULL DEFAULT FALSE,
    immutable_deployment BOOLEAN NOT NULL DEFAULT FALSE,

    exposed_ports INTEGER[] NOT NULL DEFAULT '{}',

    image_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (repository_id, image_name, image_tag, image_digest),

    CHECK (image_size_mb > 0),
    CHECK (layer_count > 0),

    CHECK (
        image_digest IS NULL OR
        image_digest ~ '^sha256:[0-9a-f]{64}$'
    ),

    CHECK (
        signature_verified = FALSE OR signed = TRUE
    ),

    CHECK (
        NOT immutable_deployment OR image_digest IS NOT NULL
    ),

    CHECK (
        NOT EXISTS (
            SELECT 1 FROM unnest(exposed_ports) AS port
            WHERE port < 1 OR port > 65535
        )
    )
);

CREATE INDEX idx_images_repository
    ON container_images(repository_id);

CREATE INDEX idx_images_digest
    ON container_images(image_digest);

CREATE INDEX idx_images_registered
    ON container_images(registered_at DESC);

-- ============================================================
-- 4. PACKAGE INVENTORY AND SOFTWARE BILL OF MATERIALS
-- ============================================================

CREATE TABLE image_packages (
    package_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id) ON DELETE CASCADE,

    package_name VARCHAR(255) NOT NULL,
    package_version VARCHAR(100) NOT NULL,

    package_type VARCHAR(30) NOT NULL DEFAULT 'APPLICATION',

    supplier VARCHAR(255),
    purl TEXT,

    UNIQUE (image_id, package_name, package_version),

    CHECK (
        package_type IN (
            'OPERATING_SYSTEM',
            'APPLICATION',
            'RUNTIME',
            'LIBRARY',
            'BUILD'
        )
    )
);

CREATE INDEX idx_packages_name
    ON image_packages(package_name);

CREATE INDEX idx_packages_image
    ON image_packages(image_id);

-- ============================================================
-- 5. VULNERABILITY INTELLIGENCE
-- ============================================================

CREATE TABLE vulnerability_catalog (
    vulnerability_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cve_id VARCHAR(30) NOT NULL UNIQUE,

    description TEXT NOT NULL,

    severity severity_level NOT NULL,

    cvss_score NUMERIC(3,1),

    published_at TIMESTAMPTZ,
    last_modified_at TIMESTAMPTZ,

    exploit_available BOOLEAN NOT NULL DEFAULT FALSE,

    actively_exploited BOOLEAN NOT NULL DEFAULT FALSE,

    known_fixed_version VARCHAR(100),

    source_name VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        cve_id ~ '^CVE-[0-9]{4}-[0-9]+$'
    ),

    CHECK (
        cvss_score IS NULL OR
        cvss_score BETWEEN 0 AND 10
    )
);

CREATE TABLE image_vulnerabilities (
    image_vulnerability_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id) ON DELETE CASCADE,

    vulnerability_id BIGINT NOT NULL
        REFERENCES vulnerability_catalog(vulnerability_id),

    package_id BIGINT
        REFERENCES image_packages(package_id),

    installed_version VARCHAR(100) NOT NULL,

    fixed_version VARCHAR(100),

    affected BOOLEAN NOT NULL DEFAULT TRUE,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (image_id, vulnerability_id, installed_version)
);

CREATE INDEX idx_image_vulnerability_image
    ON image_vulnerabilities(image_id);

CREATE INDEX idx_image_vulnerability_vulnerability
    ON image_vulnerabilities(vulnerability_id);

-- ============================================================
-- 6. SCAN EXECUTION
-- ============================================================

CREATE TABLE image_scans (
    scan_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id),

    scanner_name VARCHAR(100) NOT NULL,
    scanner_version VARCHAR(50),

    scan_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scan_completed_at TIMESTAMPTZ,

    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',

    total_findings INTEGER NOT NULL DEFAULT 0,

    critical_count INTEGER NOT NULL DEFAULT 0,
    high_count INTEGER NOT NULL DEFAULT 0,
    medium_count INTEGER NOT NULL DEFAULT 0,
    low_count INTEGER NOT NULL DEFAULT 0,
    info_count INTEGER NOT NULL DEFAULT 0,

    error_message TEXT,

    CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),

    CHECK (
        total_findings =
        critical_count + high_count + medium_count +
        low_count + info_count
        OR status <> 'COMPLETED'
    ),

    CHECK (total_findings >= 0),
    CHECK (critical_count >= 0),
    CHECK (high_count >= 0),
    CHECK (medium_count >= 0),
    CHECK (low_count >= 0),
    CHECK (info_count >= 0),

    CHECK (
        scan_completed_at IS NULL OR
        scan_completed_at >= scan_started_at
    )
);

CREATE INDEX idx_scans_image_date
    ON image_scans(image_id, scan_started_at DESC);

CREATE INDEX idx_scans_status
    ON image_scans(status);

-- ============================================================
-- 7. SECURITY FINDINGS
-- ============================================================

CREATE TABLE security_findings (
    finding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    scan_id BIGINT NOT NULL
        REFERENCES image_scans(scan_id) ON DELETE CASCADE,

    finding_type finding_type NOT NULL,

    severity severity_level NOT NULL,

    resource_name VARCHAR(255) NOT NULL,

    finding_identifier VARCHAR(255),

    description TEXT NOT NULL,

    remediation TEXT,

    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolved_at TIMESTAMPTZ,

    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,

    CHECK (
        resolved_at IS NULL OR resolved_at >= first_detected_at
    ),

    CHECK (
        is_resolved = FALSE OR resolved_at IS NOT NULL
    )
);

CREATE INDEX idx_findings_scan
    ON security_findings(scan_id);

CREATE INDEX idx_findings_severity
    ON security_findings(severity);

CREATE INDEX idx_findings_type
    ON security_findings(finding_type);

CREATE INDEX idx_findings_open
    ON security_findings(severity, first_detected_at DESC)
    WHERE is_resolved = FALSE;

-- ============================================================
-- 8. SECRET DETECTION
-- ============================================================

CREATE TABLE secret_detections (
    secret_detection_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id),

    scan_id BIGINT NOT NULL
        REFERENCES image_scans(scan_id),

    finding_id BIGINT
        REFERENCES security_findings(finding_id),

    secret_type VARCHAR(100) NOT NULL,

    source_location TEXT NOT NULL,

    masked_fingerprint VARCHAR(128),

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    rotated BOOLEAN NOT NULL DEFAULT FALSE,

    rotated_at TIMESTAMPTZ,

    CHECK (
        rotated_at IS NULL OR rotated = TRUE
    )
);

CREATE INDEX idx_secret_image
    ON secret_detections(image_id);

CREATE INDEX idx_secret_unrotated
    ON secret_detections(detected_at DESC)
    WHERE rotated = FALSE;

-- Never store actual secret values in this table.

-- ============================================================
-- 9. BRANCHLESS IMAGE SECURITY CONFIGURATION
-- ============================================================

CREATE TABLE image_configuration_checks (
    configuration_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id),

    scan_id BIGINT NOT NULL
        REFERENCES image_scans(scan_id),

    check_name VARCHAR(100) NOT NULL,

    expected_value TEXT,
    observed_value TEXT,

    passed BOOLEAN NOT NULL,

    severity severity_level NOT NULL,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (scan_id, check_name)
);

-- ============================================================
-- 10. SECURITY POLICY DEFINITIONS
-- ============================================================

CREATE TABLE security_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(150) NOT NULL UNIQUE,

    description TEXT,

    maximum_critical INTEGER NOT NULL DEFAULT 0,
    maximum_high INTEGER NOT NULL DEFAULT 0,
    maximum_medium INTEGER NOT NULL DEFAULT 3,

    require_non_root BOOLEAN NOT NULL DEFAULT TRUE,
    require_signature BOOLEAN NOT NULL DEFAULT TRUE,
    require_digest BOOLEAN NOT NULL DEFAULT TRUE,
    require_healthcheck BOOLEAN NOT NULL DEFAULT TRUE,

    block_secrets BOOLEAN NOT NULL DEFAULT TRUE,

    maximum_image_size_mb NUMERIC(12,2) NOT NULL DEFAULT 200,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (maximum_critical >= 0),
    CHECK (maximum_high >= 0),
    CHECK (maximum_medium >= 0),
    CHECK (maximum_image_size_mb > 0)
);

CREATE TABLE repository_policy_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id),

    policy_id BIGINT NOT NULL
        REFERENCES security_policies(policy_id),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    assigned_by VARCHAR(150) NOT NULL,

    UNIQUE (repository_id, policy_id)
);

CREATE INDEX idx_policy_assignment_repository
    ON repository_policy_assignments(repository_id);

-- ============================================================
-- 11. DEPLOYMENT ELIGIBILITY DECISIONS
-- ============================================================

CREATE TABLE deployment_decisions (
    decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id),

    scan_id BIGINT NOT NULL
        REFERENCES image_scans(scan_id),

    policy_id BIGINT NOT NULL
        REFERENCES security_policies(policy_id),

    decision deployment_status NOT NULL,

    decision_reason TEXT NOT NULL,

    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    evaluated_by VARCHAR(150) NOT NULL,

    UNIQUE (image_id, scan_id, policy_id)
);

CREATE INDEX idx_deployment_decisions_status
    ON deployment_decisions(decision, evaluated_at DESC);

-- ============================================================
-- 12. VULNERABILITY REMEDIATION
-- ============================================================

CREATE TABLE remediation_tickets (
    ticket_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_vulnerability_id BIGINT NOT NULL
        REFERENCES image_vulnerabilities(image_vulnerability_id),

    owner_team_id BIGINT NOT NULL
        REFERENCES security_teams(team_id),

    assigned_to VARCHAR(150) NOT NULL,

    status remediation_status NOT NULL DEFAULT 'OPEN',

    priority severity_level NOT NULL,

    due_date DATE NOT NULL,

    accepted_risk_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolved_at TIMESTAMPTZ,

    CHECK (
        status <> 'ACCEPTED_RISK' OR
        accepted_risk_reason IS NOT NULL
    ),

    CHECK (
        resolved_at IS NULL OR
        status = 'RESOLVED'
    )
);

CREATE INDEX idx_remediation_status_due
    ON remediation_tickets(status, due_date);

CREATE INDEX idx_remediation_owner
    ON remediation_tickets(owner_team_id);

-- ============================================================
-- 13. REMEDIATION AUDIT HISTORY
-- ============================================================

CREATE TABLE remediation_history (
    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ticket_id BIGINT NOT NULL
        REFERENCES remediation_tickets(ticket_id),

    previous_status remediation_status,
    new_status remediation_status NOT NULL,

    changed_by VARCHAR(150) NOT NULL,

    change_reason TEXT,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_remediation_history_ticket
    ON remediation_history(ticket_id, changed_at DESC);

-- ============================================================
-- 14. RUNTIME SECURITY EVENTS
-- ============================================================

CREATE TABLE runtime_events (
    runtime_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id),

    container_instance_id VARCHAR(255) NOT NULL,

    event_type runtime_event_type NOT NULL,

    process_name VARCHAR(255),

    destination TEXT,

    privileged BOOLEAN NOT NULL DEFAULT FALSE,

    action_taken VARCHAR(20) NOT NULL,

    severity severity_level NOT NULL,

    event_description TEXT NOT NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (action_taken IN ('ALLOW', 'BLOCK', 'ALERT'))
);

CREATE INDEX idx_runtime_image_time
    ON runtime_events(image_id, occurred_at DESC);

CREATE INDEX idx_runtime_high_severity
    ON runtime_events(severity, occurred_at DESC)
    WHERE severity IN ('CRITICAL', 'HIGH');

-- ============================================================
-- 15. CENTRALIZED AUDIT LOG
-- ============================================================

CREATE TABLE security_audit_log (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    actor VARCHAR(150) NOT NULL,

    action VARCHAR(100) NOT NULL,

    resource_type VARCHAR(100) NOT NULL,

    resource_id VARCHAR(255) NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_security_audit_time
    ON security_audit_log(created_at DESC);

CREATE INDEX idx_security_audit_resource
    ON security_audit_log(resource_type, resource_id);

-- ============================================================
-- 16. REMEDIATION STATE TRANSITION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_remediation_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    allowed BOOLEAN := FALSE;
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    allowed := CASE OLD.status
        WHEN 'OPEN' THEN
            NEW.status IN ('IN_PROGRESS', 'ACCEPTED_RISK')

        WHEN 'IN_PROGRESS' THEN
            NEW.status IN (
                'MITIGATED',
                'RESOLVED',
                'ACCEPTED_RISK'
            )

        WHEN 'MITIGATED' THEN
            NEW.status IN (
                'RESOLVED',
                'IN_PROGRESS'
            )

        WHEN 'RESOLVED' THEN
            NEW.status = 'OPEN'

        WHEN 'ACCEPTED_RISK' THEN
            NEW.status IN (
                'OPEN',
                'IN_PROGRESS'
            )

        ELSE FALSE
    END;

    IF NOT allowed THEN
        RAISE EXCEPTION
            'Invalid remediation transition: % -> %',
            OLD.status,
            NEW.status;
    END IF;

    IF NEW.status = 'ACCEPTED_RISK'
       AND NEW.accepted_risk_reason IS NULL THEN
        RAISE EXCEPTION
            'Risk acceptance requires a documented reason.';
    END IF;

    NEW.updated_at := NOW();

    IF NEW.status = 'RESOLVED' THEN
        NEW.resolved_at := NOW();
    ELSE
        NEW.resolved_at := NULL;
    END IF;

    INSERT INTO remediation_history (
        ticket_id,
        previous_status,
        new_status,
        changed_by,
        change_reason
    )
    VALUES (
        OLD.ticket_id,
        OLD.status,
        NEW.status,
        NEW.assigned_to,
        NEW.accepted_risk_reason
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_remediation_transition
BEFORE UPDATE OF status
ON remediation_tickets
FOR EACH ROW
EXECUTE FUNCTION validate_remediation_transition();

-- ============================================================
-- 17. IMAGE VALIDATION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION validate_image_security_metadata()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.signature_verified AND NOT NEW.signed THEN
        RAISE EXCEPTION
            'An unsigned image cannot have a verified signature.';
    END IF;

    IF NEW.immutable_deployment AND NEW.image_digest IS NULL THEN
        RAISE EXCEPTION
            'Immutable deployment requires an image digest.';
    END IF;

    IF NEW.runtime_user IN ('root', '0', '0:0') THEN
        RAISE NOTICE
            'Image % is configured to execute as root.',
            NEW.image_name;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_image_security_metadata
BEFORE INSERT OR UPDATE
ON container_images
FOR EACH ROW
EXECUTE FUNCTION validate_image_security_metadata();

-- ============================================================
-- 18. FINDING COUNTER VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION update_scan_finding_counts()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_scan_id BIGINT;
BEGIN
    target_scan_id := COALESCE(NEW.scan_id, OLD.scan_id);

    UPDATE image_scans
    SET
        critical_count = (
            SELECT COUNT(*)
            FROM security_findings
            WHERE scan_id = target_scan_id
              AND severity = 'CRITICAL'
              AND NOT is_resolved
        ),
        high_count = (
            SELECT COUNT(*)
            FROM security_findings
            WHERE scan_id = target_scan_id
              AND severity = 'HIGH'
              AND NOT is_resolved
        ),
        medium_count = (
            SELECT COUNT(*)
            FROM security_findings
            WHERE scan_id = target_scan_id
              AND severity = 'MEDIUM'
              AND NOT is_resolved
        ),
        low_count = (
            SELECT COUNT(*)
            FROM security_findings
            WHERE scan_id = target_scan_id
              AND severity = 'LOW'
              AND NOT is_resolved
        ),
        info_count = (
            SELECT COUNT(*)
            FROM security_findings
            WHERE scan_id = target_scan_id
              AND severity = 'INFO'
              AND NOT is_resolved
        ),
        total_findings = (
            SELECT COUNT(*)
            FROM security_findings
            WHERE scan_id = target_scan_id
              AND NOT is_resolved
        )
    WHERE scan_id = target_scan_id;

    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_update_finding_counts
AFTER INSERT OR UPDATE OR DELETE
ON security_findings
FOR EACH ROW
EXECUTE FUNCTION update_scan_finding_counts();

-- ============================================================
-- 19. DEPLOYMENT ELIGIBILITY FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_image_eligibility(
    p_image_id BIGINT,
    p_scan_id BIGINT,
    p_policy_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT,
    critical_findings BIGINT,
    high_findings BIGINT,
    medium_findings BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    image_record RECORD;
    policy_record RECORD;

    critical_total BIGINT;
    high_total BIGINT;
    medium_total BIGINT;
    secret_total BIGINT;
BEGIN
    SELECT *
    INTO image_record
    FROM container_images
    WHERE image_id = p_image_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Image % does not exist.', p_image_id;
    END IF;

    SELECT *
    INTO policy_record
    FROM security_policies
    WHERE policy_id = p_policy_id
      AND active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active policy % does not exist.',
            p_policy_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM image_scans
        WHERE scan_id = p_scan_id
          AND image_id = p_image_id
          AND status = 'COMPLETED'
    ) THEN
        RAISE EXCEPTION
            'A completed scan for this image is required.';
    END IF;

    SELECT
        COUNT(*) FILTER (
            WHERE severity = 'CRITICAL'
        ),
        COUNT(*) FILTER (
            WHERE severity = 'HIGH'
        ),
        COUNT(*) FILTER (
            WHERE severity = 'MEDIUM'
        ),
        COUNT(*) FILTER (
            WHERE finding_type = 'SECRET'
        )
    INTO
        critical_total,
        high_total,
        medium_total,
        secret_total
    FROM security_findings
    WHERE scan_id = p_scan_id
      AND NOT is_resolved;

    eligible := TRUE;
    reason := 'All deployment policy conditions satisfied.';

    IF critical_total > policy_record.maximum_critical THEN
        eligible := FALSE;
        reason := 'Critical finding threshold exceeded.';

    ELSIF high_total > policy_record.maximum_high THEN
        eligible := FALSE;
        reason := 'High finding threshold exceeded.';

    ELSIF medium_total > policy_record.maximum_medium THEN
        eligible := FALSE;
        reason := 'Medium finding threshold exceeded.';

    ELSIF policy_record.block_secrets AND secret_total > 0 THEN
        eligible := FALSE;
        reason := 'Secret exposure detected.';

    ELSIF policy_record.require_non_root
          AND image_record.runtime_user IN ('root', '0', '0:0') THEN
        eligible := FALSE;
        reason := 'Root execution is prohibited.';

    ELSIF policy_record.require_signature
          AND NOT image_record.signature_verified THEN
        eligible := FALSE;
        reason := 'Verified signature required.';

    ELSIF policy_record.require_digest
          AND image_record.image_digest IS NULL THEN
        eligible := FALSE;
        reason := 'Immutable digest required.';

    ELSIF policy_record.require_healthcheck
          AND NOT image_record.healthcheck_configured THEN
        eligible := FALSE;
        reason := 'Health check required.';

    ELSIF image_record.image_size_mb >
          policy_record.maximum_image_size_mb THEN
        eligible := FALSE;
        reason := 'Image size exceeds policy threshold.';
    END IF;

    critical_findings := critical_total;
    high_findings := high_total;
    medium_findings := medium_total;

    RETURN NEXT;
END;
$$;

-- ============================================================
-- 20. SCAN COMPLETION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE complete_image_scan(
    p_scan_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    counts RECORD;
BEGIN
    SELECT
        COUNT(*) FILTER (
            WHERE severity = 'CRITICAL' AND NOT is_resolved
        ) AS critical_count,

        COUNT(*) FILTER (
            WHERE severity = 'HIGH' AND NOT is_resolved
        ) AS high_count,

        COUNT(*) FILTER (
            WHERE severity = 'MEDIUM' AND NOT is_resolved
        ) AS medium_count,

        COUNT(*) FILTER (
            WHERE severity = 'LOW' AND NOT is_resolved
        ) AS low_count,

        COUNT(*) FILTER (
            WHERE severity = 'INFO' AND NOT is_resolved
        ) AS info_count,

        COUNT(*) FILTER (
            WHERE NOT is_resolved
        ) AS total_count

    INTO counts
    FROM security_findings
    WHERE scan_id = p_scan_id;

    UPDATE image_scans
    SET
        status = 'COMPLETED',
        scan_completed_at = NOW(),
        critical_count = counts.critical_count,
        high_count = counts.high_count,
        medium_count = counts.medium_count,
        low_count = counts.low_count,
        info_count = counts.info_count,
        total_findings = counts.total_count
    WHERE scan_id = p_scan_id
      AND status = 'RUNNING';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Scan % does not exist or is not running.',
            p_scan_id;
    END IF;
END;
$$;

-- ============================================================
-- 21. VIEWS FOR SECURITY REPORTING
-- ============================================================

CREATE VIEW image_security_inventory AS
SELECT
    i.image_id,
    r.repository_name,
    t.team_name,
    i.image_name,
    i.image_tag,
    i.image_digest,
    i.base_image,
    i.image_size_mb,
    i.runtime_user,
    i.signed,
    i.signature_verified,
    i.healthcheck_configured,
    i.immutable_deployment,
    i.registered_at
FROM container_images i
JOIN repositories r
    ON r.repository_id = i.repository_id
JOIN security_teams t
    ON t.team_id = r.team_id;

CREATE VIEW vulnerability_exposure_report AS
SELECT
    i.image_id,
    i.image_name,
    i.image_tag,
    vc.cve_id,
    vc.severity,
    vc.cvss_score,
    vc.exploit_available,
    vc.actively_exploited,
    iv.installed_version,
    COALESCE(
        iv.fixed_version,
        vc.known_fixed_version
    ) AS remediation_version,
    iv.detected_at
FROM image_vulnerabilities iv
JOIN container_images i
    ON i.image_id = iv.image_id
JOIN vulnerability_catalog vc
    ON vc.vulnerability_id = iv.vulnerability_id
WHERE iv.affected = TRUE;

CREATE VIEW open_remediation_report AS
SELECT
    rt.ticket_id,
    vc.cve_id,
    vc.severity,
    i.image_name,
    i.image_tag,
    st.team_name,
    rt.assigned_to,
    rt.status,
    rt.priority,
    rt.due_date,
    rt.created_at,
    CASE
        WHEN rt.due_date < CURRENT_DATE THEN 'OVERDUE'
        WHEN rt.due_date = CURRENT_DATE THEN 'DUE_TODAY'
        ELSE 'ON_TRACK'
    END AS deadline_status
FROM remediation_tickets rt
JOIN image_vulnerabilities iv
    ON iv.image_vulnerability_id =
       rt.image_vulnerability_id
JOIN vulnerability_catalog vc
    ON vc.vulnerability_id = iv.vulnerability_id
JOIN container_images i
    ON i.image_id = iv.image_id
JOIN security_teams st
    ON st.team_id = rt.owner_team_id
WHERE rt.status NOT IN ('RESOLVED');

CREATE VIEW latest_image_scan_report AS
SELECT DISTINCT ON (s.image_id)
    s.image_id,
    i.image_name,
    i.image_tag,
    s.scan_id,
    s.status,
    s.total_findings,
    s.critical_count,
    s.high_count,
    s.medium_count,
    s.low_count,
    s.info_count,
    s.scan_started_at,
    s.scan_completed_at
FROM image_scans s
JOIN container_images i
    ON i.image_id = s.image_id
ORDER BY s.image_id, s.scan_started_at DESC;

CREATE VIEW runtime_security_dashboard AS
SELECT
    i.image_name,
    re.container_instance_id,
    re.event_type,
    re.process_name,
    re.action_taken,
    re.severity,
    COUNT(*) AS event_count,
    MAX(re.occurred_at) AS last_observed
FROM runtime_events re
JOIN container_images i
    ON i.image_id = re.image_id
GROUP BY
    i.image_name,
    re.container_instance_id,
    re.event_type,
    re.process_name,
    re.action_taken,
    re.severity;

-- ============================================================
-- 22. SAMPLE DATA
-- ============================================================

INSERT INTO security_teams (
    team_name,
    contact_email
)
VALUES
    ('Platform Security', 'platform-security@example.com'),
    ('Application Engineering', 'application-team@example.com');

INSERT INTO repositories (
    team_id,
    repository_name,
    repository_url,
    criticality
)
VALUES
    (
        1,
        'payment-service',
        'https://github.com/example/payment-service',
        'CRITICAL'
    ),
    (
        2,
        'inventory-service',
        'https://github.com/example/inventory-service',
        'HIGH'
    );

INSERT INTO container_images (
    repository_id,
    image_name,
    image_tag,
    image_digest,
    base_image,
    image_size_mb,
    layer_count,
    runtime_user,
    signed,
    signature_verified,
    healthcheck_configured,
    immutable_deployment,
    exposed_ports
)
VALUES
    (
        1,
        'payment-api',
        'latest',
        NULL,
        'ubuntu:latest',
        850,
        24,
        'root',
        FALSE,
        FALSE,
        FALSE,
        FALSE,
        ARRAY[22, 8080]
    ),
    (
        2,
        'inventory-api',
        '2.1.0',
        'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        'python:3.12-slim',
        95,
        7,
        '10001',
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        ARRAY[8080]
    );

INSERT INTO image_packages (
    image_id,
    package_name,
    package_version,
    package_type,
    supplier
)
VALUES
    (1, 'openssl', '1.0.2', 'OPERATING_SYSTEM', 'OpenSSL'),
    (1, 'curl', '7.50.0', 'OPERATING_SYSTEM', 'curl'),
    (1, 'python', '3.12', 'RUNTIME', 'Python'),
    (2, 'python', '3.12', 'RUNTIME', 'Python'),
    (2, 'inventory-app', '2.1.0', 'APPLICATION', 'Internal');

INSERT INTO vulnerability_catalog (
    cve_id,
    description,
    severity,
    cvss_score,
    exploit_available,
    actively_exploited,
    known_fixed_version,
    source_name
)
VALUES
    (
        'CVE-2025-10001',
        'Critical cryptographic library vulnerability.',
        'CRITICAL',
        9.8,
        TRUE,
        TRUE,
        '3.0.15',
        'NVD'
    ),
    (
        'CVE-2025-10002',
        'Network request handling vulnerability.',
        'HIGH',
        8.1,
        FALSE,
        FALSE,
        '8.10.0',
        'NVD'
    ),
    (
        'CVE-2025-10003',
        'Moderate library vulnerability.',
        'MEDIUM',
        5.5,
        FALSE,
        FALSE,
        '2.5.1',
        'NVD'
    );

INSERT INTO image_vulnerabilities (
    image_id,
    vulnerability_id,
    package_id,
    installed_version,
    fixed_version
)
VALUES
    (
        1,
        1,
        1,
        '1.0.2',
        '3.0.15'
    ),
    (
        1,
        2,
        2,
        '7.50.0',
        '8.10.0'
    );

INSERT INTO security_policies (
    policy_name,
    description,
    maximum_critical,
    maximum_high,
    maximum_medium,
    require_non_root,
    require_signature,
    require_digest,
    require_healthcheck,
    block_secrets,
    maximum_image_size_mb
)
VALUES
    (
        'Production Strict',
        'Production deployment security requirements.',
        0,
        0,
        3,
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        200
    ),
    (
        'Development Controlled',
        'Development environment policy.',
        0,
        2,
        10,
        TRUE,
        FALSE,
        FALSE,
        FALSE,
        TRUE,
        500
    );

INSERT INTO repository_policy_assignments (
    repository_id,
    policy_id,
    assigned_by
)
VALUES
    (1, 1, 'security-admin'),
    (2, 1, 'security-admin');

-- ============================================================
-- 23. SAMPLE SCAN EXECUTION
-- ============================================================

INSERT INTO image_scans (
    image_id,
    scanner_name,
    scanner_version,
    status
)
VALUES
    (1, 'Container Security Scanner', '2.1.0', 'RUNNING'),
    (2, 'Container Security Scanner', '2.1.0', 'RUNNING');

INSERT INTO security_findings (
    scan_id,
    finding_type,
    severity,
    resource_name,
    finding_identifier,
    description,
    remediation
)
VALUES
    (
        1,
        'VULNERABILITY',
        'CRITICAL',
        'openssl',
        'CVE-2025-10001',
        'Critical cryptographic vulnerability.',
        'Upgrade OpenSSL to 3.0.15.'
    ),
    (
        1,
        'VULNERABILITY',
        'HIGH',
        'curl',
        'CVE-2025-10002',
        'Network request vulnerability.',
        'Upgrade curl to 8.10.0.'
    ),
    (
        1,
        'SECRET',
        'CRITICAL',
        'DATABASE_PASSWORD',
        'PASSWORD_EXPOSURE',
        'Potential hardcoded database credential.',
        'Rotate and inject the credential securely.'
    ),
    (
        1,
        'MISCONFIGURATION',
        'HIGH',
        'USER',
        'ROOT_EXECUTION',
        'Container runs as root.',
        'Configure a non-root user.'
    ),
    (
        1,
        'MISCONFIGURATION',
        'MEDIUM',
        'IMAGE_SIZE',
        'LARGE_IMAGE',
        'Image exceeds size threshold.',
        'Use a minimal runtime image.'
    ),
    (
        2,
        'MISCONFIGURATION',
        'LOW',
        'IMAGE_LAYERS',
        'LAYER_REVIEW',
        'Minor image layer optimization opportunity.',
        'Review build layer consolidation.'
    );

-- Sample secret record contains no actual credential.
INSERT INTO secret_detections (
    image_id,
    scan_id,
    finding_id,
    secret_type,
    source_location,
    masked_fingerprint
)
VALUES (
    1,
    1,
    3,
    'DATABASE_PASSWORD',
    'image environment metadata',
    'sha256:masked-fingerprint'
);

INSERT INTO image_configuration_checks (
    image_id,
    scan_id,
    check_name,
    expected_value,
    observed_value,
    passed,
    severity
)
VALUES
    (
        1,
        1,
        'NON_ROOT_USER',
        'non-root',
        'root',
        FALSE,
        'HIGH'
    ),
    (
        1,
        1,
        'IMAGE_SIGNATURE',
        'verified',
        'unsigned',
        FALSE,
        'HIGH'
    ),
    (
        2,
        2,
        'NON_ROOT_USER',
        'non-root',
        '10001',
        TRUE,
        'HIGH'
    ),
    (
        2,
        2,
        'IMAGE_SIGNATURE',
        'verified',
        'verified',
        TRUE,
        'HIGH'
    );

-- ============================================================
-- 24. COMPLETE SAMPLE SCANS
-- ============================================================

CALL complete_image_scan(1);
CALL complete_image_scan(2);

-- ============================================================
-- 25. SAMPLE REMEDIATION TICKET
-- ============================================================

INSERT INTO remediation_tickets (
    image_vulnerability_id,
    owner_team_id,
    assigned_to,
    status,
    priority,
    due_date
)
VALUES
    (
        1,
        1,
        'security-engineer',
        'OPEN',
        'CRITICAL',
        CURRENT_DATE + 2
    ),
    (
        2,
        1,
        'platform-engineer',
        'IN_PROGRESS',
        'HIGH',
        CURRENT_DATE + 7
    );

-- ============================================================
-- 26. RUNTIME SECURITY EVENTS
-- ============================================================

INSERT INTO runtime_events (
    image_id,
    container_instance_id,
    event_type,
    process_name,
    destination,
    privileged,
    action_taken,
    severity,
    event_description
)
VALUES
    (
        2,
        'container-inventory-101',
        'PROCESS_EXECUTION',
        '/usr/local/bin/python',
        NULL,
        FALSE,
        'ALLOW',
        'INFO',
        'Approved application process execution.'
    ),
    (
        1,
        'container-payment-101',
        'PROCESS_EXECUTION',
        '/usr/bin/nc',
        NULL,
        FALSE,
        'BLOCK',
        'HIGH',
        'Restricted network utility execution.'
    ),
    (
        1,
        'container-payment-101',
        'FILE_MODIFICATION',
        'file-writer',
        '/etc/shadow',
        FALSE,
        'BLOCK',
        'CRITICAL',
        'Attempted modification of protected system file.'
    ),
    (
        1,
        'container-payment-101',
        'PRIVILEGE_CHANGE',
        'privilege-escalation',
        NULL,
        TRUE,
        'BLOCK',
        'CRITICAL',
        'Unexpected privileged operation.'
    );

-- ============================================================
-- 27. TRANSACTIONAL DEPLOYMENT ELIGIBILITY EVALUATION
-- ============================================================

DO $$
DECLARE
    evaluation RECORD;
BEGIN
    SELECT *
    INTO evaluation
    FROM evaluate_image_eligibility(1, 1, 1);

    INSERT INTO deployment_decisions (
        image_id,
        scan_id,
        policy_id,
        decision,
        decision_reason,
        evaluated_by
    )
    VALUES (
        1,
        1,
        1,
        CASE
            WHEN evaluation.eligible THEN 'APPROVED'
            ELSE 'BLOCKED'
        END,
        evaluation.reason,
        'deployment-security-service'
    );

    SELECT *
    INTO evaluation
    FROM evaluate_image_eligibility(2, 2, 1);

    INSERT INTO deployment_decisions (
        image_id,
        scan_id,
        policy_id,
        decision,
        decision_reason,
        evaluated_by
    )
    VALUES (
        2,
        2,
        1,
        CASE
            WHEN evaluation.eligible THEN 'APPROVED'
            ELSE 'BLOCKED'
        END,
        evaluation.reason,
        'deployment-security-service'
    );
END;
$$;

-- ============================================================
-- 28. AUDIT RECORDS
-- ============================================================

INSERT INTO security_audit_log (
    actor,
    action,
    resource_type,
    resource_id,
    details
)
VALUES
    (
        'security-scanner',
        'IMAGE_SCAN_COMPLETED',
        'CONTAINER_IMAGE',
        '1',
        '{"scanner":"2.1.0","environment":"production"}'
    ),
    (
        'deployment-security-service',
        'DEPLOYMENT_EVALUATED',
        'CONTAINER_IMAGE',
        '1',
        '{"decision":"BLOCKED","policy":"Production Strict"}'
    ),
    (
        'deployment-security-service',
        'DEPLOYMENT_EVALUATED',
        'CONTAINER_IMAGE',
        '2',
        '{"decision":"APPROVED","policy":"Production Strict"}'
    );

COMMIT;

-- ============================================================
-- 29. RETRIEVAL QUERIES
-- ============================================================

-- Complete image inventory.
SELECT *
FROM image_security_inventory
ORDER BY repository_name, image_name;

-- Packages belonging to an image.
SELECT
    i.image_name,
    i.image_tag,
    p.package_name,
    p.package_version,
    p.package_type
FROM container_images i
JOIN image_packages p
    ON p.image_id = i.image_id
ORDER BY i.image_id, p.package_name;

-- Known vulnerability exposure.
SELECT *
FROM vulnerability_exposure_report
ORDER BY
    CASE severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
        ELSE 5
    END;

-- ============================================================
-- 30. VALIDATION QUERIES
-- ============================================================

-- Detect root containers.
SELECT
    image_id,
    image_name,
    image_tag,
    runtime_user
FROM container_images
WHERE runtime_user IN ('root', '0', '0:0');

-- Find unsigned or unverified images.
SELECT
    image_id,
    image_name,
    signed,
    signature_verified
FROM container_images
WHERE NOT signature_verified;

-- Find mutable image tags.
SELECT
    image_id,
    image_name,
    image_tag
FROM container_images
WHERE image_tag = 'latest';

-- Find unrotated secrets.
SELECT
    secret_detection_id,
    image_id,
    secret_type,
    source_location,
    detected_at
FROM secret_detections
WHERE rotated = FALSE;

-- ============================================================
-- 31. AGGREGATION AND SECURITY METRICS
-- ============================================================

-- Severity distribution.
SELECT
    severity,
    COUNT(*) AS finding_count
FROM security_findings
WHERE is_resolved = FALSE
GROUP BY severity
ORDER BY finding_count DESC;

-- Vulnerability exposure by image.
SELECT
    i.image_name,
    i.image_tag,
    vc.severity,
    COUNT(*) AS vulnerability_count
FROM image_vulnerabilities iv
JOIN container_images i
    ON i.image_id = iv.image_id
JOIN vulnerability_catalog vc
    ON vc.vulnerability_id = iv.vulnerability_id
WHERE iv.affected = TRUE
GROUP BY
    i.image_name,
    i.image_tag,
    vc.severity
ORDER BY i.image_name, vulnerability_count DESC;

-- Mean image size by repository.
SELECT
    r.repository_name,
    ROUND(AVG(i.image_size_mb), 2) AS average_size_mb,
    COUNT(i.image_id) AS image_count
FROM repositories r
JOIN container_images i
    ON i.repository_id = r.repository_id
GROUP BY r.repository_name;

-- Runtime blocked-event count.
SELECT
    severity,
    COUNT(*) AS blocked_events
FROM runtime_events
WHERE action_taken = 'BLOCK'
GROUP BY severity
ORDER BY blocked_events DESC;

-- ============================================================
-- 32. DEPLOYMENT ELIGIBILITY
-- ============================================================

SELECT
    i.image_name,
    i.image_tag,
    e.eligible,
    e.reason,
    e.critical_findings,
    e.high_findings,
    e.medium_findings
FROM container_images i
CROSS JOIN LATERAL evaluate_image_eligibility(
    i.image_id,
    CASE i.image_id
        WHEN 1 THEN 1
        WHEN 2 THEN 2
    END,
    1
) e
WHERE i.image_id IN (1, 2);

-- ============================================================
-- 33. REMEDIATION REPORTING
-- ============================================================

SELECT *
FROM open_remediation_report
ORDER BY
    CASE priority
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
        ELSE 5
    END,
    due_date;

-- Overdue vulnerability remediation.
SELECT
    ticket_id,
    assigned_to,
    priority,
    due_date,
    status
FROM remediation_tickets
WHERE due_date < CURRENT_DATE
  AND status NOT IN ('RESOLVED');

-- ============================================================
-- 34. SCAN REPORTING
-- ============================================================

SELECT *
FROM latest_image_scan_report
ORDER BY scan_started_at DESC;

-- Scan history for every image.
SELECT
    i.image_name,
    s.scan_id,
    s.status,
    s.total_findings,
    s.critical_count,
    s.high_count,
    s.scan_started_at,
    s.scan_completed_at
FROM image_scans s
JOIN container_images i
    ON i.image_id = s.image_id
ORDER BY s.scan_started_at DESC;

-- ============================================================
-- 35. RUNTIME MONITORING
-- ============================================================

SELECT *
FROM runtime_security_dashboard
ORDER BY last_observed DESC;

-- Critical runtime incidents.
SELECT
    runtime_event_id,
    container_instance_id,
    event_type,
    process_name,
    destination,
    action_taken,
    occurred_at
FROM runtime_events
WHERE severity = 'CRITICAL'
ORDER BY occurred_at DESC;

-- ============================================================
-- 36. GOVERNANCE AUDIT
-- ============================================================

SELECT
    actor,
    action,
    resource_type,
    resource_id,
    details,
    created_at
FROM security_audit_log
ORDER BY created_at DESC;

-- ============================================================
-- 37. POLICY ASSIGNMENT REPORT
-- ============================================================

SELECT
    r.repository_name,
    p.policy_name,
    p.maximum_critical,
    p.maximum_high,
    p.maximum_medium,
    p.require_non_root,
    p.require_signature,
    p.require_digest,
    p.block_secrets
FROM repository_policy_assignments a
JOIN repositories r
    ON r.repository_id = a.repository_id
JOIN security_policies p
    ON p.policy_id = a.policy_id
WHERE p.active = TRUE
ORDER BY r.repository_name;
