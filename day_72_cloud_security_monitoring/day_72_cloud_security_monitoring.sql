/*
===============================================================================
CLOUD SECURITY MONITORING
PostgreSQL 15+

Relational monitoring and incident investigation platform.

Implemented capabilities:
1. Cloud organizations and repositories of audit evidence.
2. Cloud resources and resource sensitivity classifications.
3. Identity and security event ingestion.
4. Immutable audit-event identification.
5. Detection rules and security alerts.
6. Alert correlation and incident investigation.
7. Analyst assignment and evidence tracking.
8. Security policies and access decisions.
9. Detection-window evaluation.
10. Incident lifecycle enforcement.
11. Risk aggregation and operational reporting.
12. Transaction-controlled event ingestion.

All objects are contained in the cloud_security schema.

The demonstration data uses synthetic records and reserved documentation
IP addresses.
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS cloud_security;

SET search_path TO cloud_security, public;


/* ============================================================================
   1. ENUMERATIONS
============================================================================ */

CREATE TYPE event_type AS ENUM (
    'LOGIN',
    'LOGOUT',
    'FAILED_LOGIN',
    'API_ACCESS',
    'PERMISSION_CHANGE',
    'RESOURCE_CREATED',
    'RESOURCE_DELETED',
    'CONFIGURATION_CHANGE',
    'DATA_ACCESS',
    'SECRET_ACCESS',
    'NETWORK_ACCESS'
);

CREATE TYPE severity_level AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE incident_status AS ENUM (
    'OPEN',
    'INVESTIGATING',
    'CONTAINED',
    'RESOLVED',
    'CLOSED'
);

CREATE TYPE review_outcome AS ENUM (
    'NOT_REVIEWED',
    'CONFIRMED',
    'FALSE_POSITIVE',
    'ESCALATED'
);

CREATE TYPE alert_status AS ENUM (
    'NEW',
    'ACKNOWLEDGED',
    'CORRELATED',
    'CLOSED'
);


/* ============================================================================
   2. ORGANIZATIONAL IDENTITIES
============================================================================ */

CREATE TABLE analysts (
    analyst_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    username VARCHAR(100) NOT NULL UNIQUE,

    email VARCHAR(255) NOT NULL UNIQUE,

    role VARCHAR(30) NOT NULL CHECK (
        role IN (
            'SECURITY_ADMIN',
            'SOC_ANALYST',
            'INCIDENT_RESPONDER',
            'AUDITOR',
            'READ_ONLY'
        )
    ),

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE cloud_accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    provider VARCHAR(30) NOT NULL CHECK (
        provider IN (
            'AWS',
            'AZURE',
            'GCP',
            'PRIVATE_CLOUD'
        )
    ),

    external_account_id VARCHAR(150) NOT NULL,

    account_name VARCHAR(150) NOT NULL,

    region VARCHAR(80) NOT NULL,

    environment VARCHAR(30) NOT NULL CHECK (
        environment IN (
            'PRODUCTION',
            'STAGING',
            'DEVELOPMENT',
            'TEST'
        )
    ),

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(provider, external_account_id)
);


CREATE TABLE cloud_resources (
    resource_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    account_id BIGINT NOT NULL REFERENCES cloud_accounts(account_id),

    resource_external_id VARCHAR(255) NOT NULL,

    resource_name VARCHAR(200) NOT NULL,

    resource_type VARCHAR(80) NOT NULL,

    sensitivity SMALLINT NOT NULL DEFAULT 1 CHECK (
        sensitivity BETWEEN 1 AND 5
    ),

    contains_sensitive_data BOOLEAN NOT NULL DEFAULT FALSE,

    public_exposure BOOLEAN NOT NULL DEFAULT FALSE,

    encrypted BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(account_id, resource_external_id)
);


/* ============================================================================
   3. SECURITY POLICIES
============================================================================ */

CREATE TABLE monitoring_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(150) NOT NULL UNIQUE,

    failed_login_threshold INTEGER NOT NULL DEFAULT 5 CHECK (
        failed_login_threshold > 0
    ),

    failed_login_window INTERVAL NOT NULL DEFAULT INTERVAL '10 minutes'
        CHECK (failed_login_window > INTERVAL '0 seconds'),

    privilege_change_threshold INTEGER NOT NULL DEFAULT 3 CHECK (
        privilege_change_threshold > 0
    ),

    privilege_change_window INTERVAL NOT NULL DEFAULT INTERVAL '15 minutes'
        CHECK (privilege_change_window > INTERVAL '0 seconds'),

    minimum_risk_score SMALLINT NOT NULL DEFAULT 70 CHECK (
        minimum_risk_score BETWEEN 0 AND 100
    ),

    require_mfa_for_sensitive_resources BOOLEAN NOT NULL DEFAULT TRUE,

    require_approved_privilege_changes BOOLEAN NOT NULL DEFAULT TRUE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE detection_rules (
    rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    rule_code VARCHAR(40) NOT NULL UNIQUE,

    rule_name VARCHAR(150) NOT NULL,

    description TEXT NOT NULL,

    category VARCHAR(40) NOT NULL CHECK (
        category IN (
            'AUTHENTICATION',
            'AUTHORIZATION',
            'NETWORK',
            'DATA_PROTECTION',
            'CONFIGURATION',
            'ANOMALY'
        )
    ),

    base_risk_score SMALLINT NOT NULL CHECK (
        base_risk_score BETWEEN 0 AND 100
    ),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


/* ============================================================================
   4. CLOUD AUDIT EVENTS
============================================================================ */

CREATE TABLE audit_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_uuid UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,

    account_id BIGINT NOT NULL REFERENCES cloud_accounts(account_id),

    resource_id BIGINT REFERENCES cloud_resources(resource_id),

    event_timestamp TIMESTAMPTZ NOT NULL,

    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    event_type event_type NOT NULL,

    user_identifier VARCHAR(255) NOT NULL,

    source_ip INET NOT NULL,

    action VARCHAR(150) NOT NULL,

    success BOOLEAN NOT NULL,

    region VARCHAR(80) NOT NULL,

    mfa_used BOOLEAN NOT NULL DEFAULT FALSE,

    approved_action BOOLEAN NOT NULL DEFAULT FALSE,

    request_id VARCHAR(200),

    correlation_id UUID,

    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    previous_record_hash TEXT,

    record_hash TEXT,

    CHECK (
        jsonb_typeof(metadata) = 'object'
    ),

    CHECK (
        length(user_identifier) BETWEEN 1 AND 255
    ),

    CHECK (
        length(action) BETWEEN 1 AND 150
    ),

    CHECK (
        ingestion_timestamp >= event_timestamp
        OR event_timestamp >= ingestion_timestamp - INTERVAL '5 minutes'
    )
);


/* ============================================================================
   5. AUDIT INDEXES
============================================================================ */

CREATE INDEX idx_audit_event_timestamp
ON audit_events(event_timestamp DESC);

CREATE INDEX idx_audit_account_timestamp
ON audit_events(account_id, event_timestamp DESC);

CREATE INDEX idx_audit_user_timestamp
ON audit_events(user_identifier, event_timestamp DESC);

CREATE INDEX idx_audit_event_type_timestamp
ON audit_events(event_type, event_timestamp DESC);

CREATE INDEX idx_audit_source_ip
ON audit_events(source_ip);

CREATE INDEX idx_audit_resource_timestamp
ON audit_events(resource_id, event_timestamp DESC)
WHERE resource_id IS NOT NULL;

CREATE INDEX idx_audit_metadata
ON audit_events USING GIN(metadata);

CREATE INDEX idx_audit_correlation
ON audit_events(correlation_id)
WHERE correlation_id IS NOT NULL;


/* ============================================================================
   6. ALERTS
============================================================================ */

CREATE TABLE security_alerts (
    alert_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    alert_uuid UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,

    rule_id BIGINT NOT NULL REFERENCES detection_rules(rule_id),

    account_id BIGINT NOT NULL REFERENCES cloud_accounts(account_id),

    event_id BIGINT NOT NULL REFERENCES audit_events(event_id),

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    user_identifier VARCHAR(255) NOT NULL,

    severity severity_level NOT NULL,

    risk_score SMALLINT NOT NULL CHECK (
        risk_score BETWEEN 0 AND 100
    ),

    description TEXT NOT NULL,

    status alert_status NOT NULL DEFAULT 'NEW',

    indicators JSONB NOT NULL DEFAULT '{}'::JSONB,

    CHECK (jsonb_typeof(indicators) = 'object')
);


CREATE INDEX idx_alert_severity_time
ON security_alerts(severity, detected_at DESC);

CREATE INDEX idx_alert_status_time
ON security_alerts(status, detected_at DESC);

CREATE INDEX idx_alert_user_time
ON security_alerts(user_identifier, detected_at DESC);

CREATE INDEX idx_alert_account_time
ON security_alerts(account_id, detected_at DESC);


/* ============================================================================
   7. INCIDENT MANAGEMENT
============================================================================ */

CREATE TABLE security_incidents (
    incident_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    incident_uuid UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,

    title VARCHAR(255) NOT NULL,

    description TEXT,

    severity severity_level NOT NULL,

    status incident_status NOT NULL DEFAULT 'OPEN',

    review_result review_outcome NOT NULL DEFAULT 'NOT_REVIEWED',

    assigned_analyst_id BIGINT REFERENCES analysts(analyst_id),

    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    contained_at TIMESTAMPTZ,

    resolved_at TIMESTAMPTZ,

    closed_at TIMESTAMPTZ,

    resolution_notes TEXT,

    CHECK (updated_at >= opened_at),

    CHECK (
        contained_at IS NULL OR contained_at >= opened_at
    ),

    CHECK (
        resolved_at IS NULL OR resolved_at >= opened_at
    ),

    CHECK (
        closed_at IS NULL OR closed_at >= opened_at
    )
);


CREATE TABLE incident_alerts (
    incident_id BIGINT NOT NULL REFERENCES
        security_incidents(incident_id),

    alert_id BIGINT NOT NULL REFERENCES
        security_alerts(alert_id),

    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY(incident_id, alert_id),

    UNIQUE(alert_id)
);


CREATE TABLE incident_evidence (
    evidence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    incident_id BIGINT NOT NULL REFERENCES
        security_incidents(incident_id),

    evidence_type VARCHAR(40) NOT NULL CHECK (
        evidence_type IN (
            'AUDIT_EVENT',
            'NETWORK_CAPTURE',
            'CONFIGURATION',
            'FILE_HASH',
            'ANALYST_NOTE',
            'EXTERNAL_INDICATOR'
        )
    ),

    evidence_reference TEXT NOT NULL,

    evidence_sha256 CHAR(64) NOT NULL,

    collected_by BIGINT REFERENCES analysts(analyst_id),

    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    description TEXT NOT NULL
);


CREATE TABLE incident_notes (
    note_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    incident_id BIGINT NOT NULL REFERENCES
        security_incidents(incident_id),

    analyst_id BIGINT NOT NULL REFERENCES analysts(analyst_id),

    note TEXT NOT NULL CHECK (
        length(note) BETWEEN 1 AND 5000
    ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE incident_status_history (
    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    incident_id BIGINT NOT NULL REFERENCES
        security_incidents(incident_id),

    previous_status incident_status,

    new_status incident_status NOT NULL,

    changed_by BIGINT REFERENCES analysts(analyst_id),

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    reason TEXT NOT NULL
);


CREATE INDEX idx_incident_status_severity
ON security_incidents(status, severity, opened_at DESC);

CREATE INDEX idx_incident_assignment
ON security_incidents(assigned_analyst_id, status);


/* ============================================================================
   8. AUDIT EVENT IMMUTABILITY
============================================================================ */

CREATE OR REPLACE FUNCTION prevent_audit_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Audit events are append-only. Updates and deletions are prohibited.';
END;
$$;


CREATE TRIGGER trg_audit_immutable
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_mutation();


/* ============================================================================
   9. INCIDENT STATE TRANSITIONS
============================================================================ */

CREATE OR REPLACE FUNCTION validate_incident_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    valid_transition BOOLEAN := FALSE;
BEGIN
    IF NEW.status = OLD.status THEN
        NEW.updated_at := NOW();
        RETURN NEW;
    END IF;

    CASE OLD.status

        WHEN 'OPEN' THEN
            valid_transition :=
                NEW.status IN ('INVESTIGATING', 'CLOSED');

        WHEN 'INVESTIGATING' THEN
            valid_transition :=
                NEW.status IN (
                    'CONTAINED',
                    'RESOLVED',
                    'CLOSED'
                );

        WHEN 'CONTAINED' THEN
            valid_transition :=
                NEW.status IN (
                    'INVESTIGATING',
                    'RESOLVED'
                );

        WHEN 'RESOLVED' THEN
            valid_transition :=
                NEW.status IN (
                    'CLOSED',
                    'INVESTIGATING'
                );

        WHEN 'CLOSED' THEN
            valid_transition := FALSE;

    END CASE;

    IF NOT valid_transition THEN
        RAISE EXCEPTION
            'Invalid incident transition: % -> %',
            OLD.status,
            NEW.status;
    END IF;

    NEW.updated_at := NOW();

    IF NEW.status = 'CONTAINED' THEN
        NEW.contained_at := NOW();
    END IF;

    IF NEW.status = 'RESOLVED' THEN
        NEW.resolved_at := NOW();
    END IF;

    IF NEW.status = 'CLOSED' THEN
        NEW.closed_at := NOW();
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_incident_transition
BEFORE UPDATE OF status ON security_incidents
FOR EACH ROW
EXECUTE FUNCTION validate_incident_transition();


/* ============================================================================
   10. INCIDENT STATUS AUDIT
============================================================================ */

CREATE OR REPLACE FUNCTION record_incident_status_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO incident_status_history (
            incident_id,
            previous_status,
            new_status,
            reason
        )
        VALUES (
            NEW.incident_id,
            OLD.status,
            NEW.status,
            COALESCE(
                NEW.resolution_notes,
                'Incident status changed.'
            )
        );
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_incident_history
AFTER UPDATE OF status ON security_incidents
FOR EACH ROW
EXECUTE FUNCTION record_incident_status_change();


/* ============================================================================
   11. SECURITY REPORTING VIEWS
============================================================================ */

CREATE VIEW v_recent_security_events AS
SELECT
    e.event_id,
    e.event_uuid,
    e.event_timestamp,
    e.event_type,
    e.user_identifier,
    e.source_ip,
    e.action,
    e.success,
    e.region,
    a.provider,
    a.account_name,
    r.resource_name,
    r.sensitivity
FROM audit_events e
JOIN cloud_accounts a
    ON a.account_id = e.account_id
LEFT JOIN cloud_resources r
    ON r.resource_id = e.resource_id;


CREATE VIEW v_security_alert_dashboard AS
SELECT
    al.alert_id,
    al.alert_uuid,
    al.detected_at,
    al.severity,
    al.risk_score,
    al.status,
    al.user_identifier,
    dr.rule_code,
    dr.rule_name,
    ca.account_name,
    ca.provider
FROM security_alerts al
JOIN detection_rules dr
    ON dr.rule_id = al.rule_id
JOIN cloud_accounts ca
    ON ca.account_id = al.account_id;


CREATE VIEW v_incident_dashboard AS
SELECT
    i.incident_id,
    i.incident_uuid,
    i.title,
    i.severity,
    i.status,
    i.review_result,
    i.opened_at,
    i.updated_at,
    an.username AS assigned_analyst,
    COUNT(ia.alert_id) AS linked_alert_count
FROM security_incidents i
LEFT JOIN analysts an
    ON an.analyst_id = i.assigned_analyst_id
LEFT JOIN incident_alerts ia
    ON ia.incident_id = i.incident_id
GROUP BY
    i.incident_id,
    an.username;


/* ============================================================================
   12. AGGREGATED USER RISK VIEW
============================================================================ */

CREATE VIEW v_user_security_risk AS
SELECT
    user_identifier,
    COUNT(*) AS event_count,

    COUNT(*) FILTER (
        WHERE event_type = 'FAILED_LOGIN'
    ) AS failed_login_count,

    COUNT(*) FILTER (
        WHERE event_type = 'PERMISSION_CHANGE'
    ) AS permission_change_count,

    COUNT(*) FILTER (
        WHERE event_type = 'SECRET_ACCESS'
    ) AS secret_access_count,

    COUNT(*) FILTER (
        WHERE success = FALSE
    ) AS unsuccessful_events,

    COUNT(*) FILTER (
        WHERE mfa_used = FALSE
          AND event_type IN (
              'LOGIN',
              'SECRET_ACCESS',
              'DATA_ACCESS'
          )
    ) AS events_without_mfa,

    MAX(event_timestamp) AS last_activity

FROM audit_events
GROUP BY user_identifier;


/* ============================================================================
   13. DETECTION FUNCTION
============================================================================ */

CREATE OR REPLACE FUNCTION evaluate_security_event(
    p_event_id BIGINT
)
RETURNS TABLE (
    rule_code VARCHAR,
    risk_score INTEGER,
    explanation TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_event audit_events%ROWTYPE;

    v_failed_count INTEGER;
    v_permission_count INTEGER;
    v_sensitivity SMALLINT;
BEGIN
    SELECT *
    INTO v_event
    FROM audit_events
    WHERE event_id = p_event_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Audit event % does not exist.',
            p_event_id;
    END IF;

    /*
     * Rule AUTH-001:
     * Repeated failed authentication within ten minutes.
     */

    IF v_event.event_type = 'FAILED_LOGIN' THEN

        SELECT COUNT(*)
        INTO v_failed_count
        FROM audit_events e
        WHERE e.user_identifier = v_event.user_identifier
          AND e.event_type = 'FAILED_LOGIN'
          AND e.event_timestamp BETWEEN
              v_event.event_timestamp - INTERVAL '10 minutes'
              AND v_event.event_timestamp;

        IF v_failed_count >= 5 THEN
            RETURN QUERY
            SELECT
                'AUTH-001'::VARCHAR,
                85,
                'Repeated authentication failures.'::TEXT;
        END IF;

    END IF;


    /*
     * Rule IAM-001:
     * Rapid privilege changes.
     */

    IF v_event.event_type = 'PERMISSION_CHANGE' THEN

        SELECT COUNT(*)
        INTO v_permission_count
        FROM audit_events e
        WHERE e.user_identifier = v_event.user_identifier
          AND e.event_type = 'PERMISSION_CHANGE'
          AND e.event_timestamp BETWEEN
              v_event.event_timestamp - INTERVAL '15 minutes'
              AND v_event.event_timestamp;

        IF v_permission_count >= 3 THEN
            RETURN QUERY
            SELECT
                'IAM-001'::VARCHAR,
                95,
                'Rapid privilege modifications.'::TEXT;
        END IF;

        IF NOT v_event.approved_action THEN
            RETURN QUERY
            SELECT
                'IAM-002'::VARCHAR,
                95,
                'Unapproved privilege modification.'::TEXT;
        END IF;

    END IF;


    /*
     * Rule DATA-001:
     * Unapproved access to secrets.
     */

    IF
        v_event.event_type = 'SECRET_ACCESS'
        AND v_event.success
        AND NOT v_event.approved_action
    THEN
        RETURN QUERY
        SELECT
            'DATA-001'::VARCHAR,
            95,
            'Unapproved secret access.'::TEXT;
    END IF;


    /*
     * Rule IAM-003:
     * Sensitive resources require MFA.
     */

    SELECT r.sensitivity
    INTO v_sensitivity
    FROM cloud_resources r
    WHERE r.resource_id = v_event.resource_id;

    IF
        v_event.success
        AND COALESCE(v_sensitivity, 1) >= 4
        AND NOT v_event.mfa_used
    THEN
        RETURN QUERY
        SELECT
            'IAM-003'::VARCHAR,
            90,
            'Sensitive resource accessed without MFA.'::TEXT;
    END IF;

END;
$$;


/* ============================================================================
   14. ALERT CREATION PROCEDURE
============================================================================ */

CREATE OR REPLACE PROCEDURE process_security_event(
    p_event_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_event audit_events%ROWTYPE;
    v_rule RECORD;
    v_rule_id BIGINT;
BEGIN
    SELECT *
    INTO v_event
    FROM audit_events
    WHERE event_id = p_event_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Event % does not exist.',
            p_event_id;
    END IF;

    FOR v_rule IN
        SELECT *
        FROM evaluate_security_event(p_event_id)
    LOOP

        SELECT rule_id
        INTO v_rule_id
        FROM detection_rules
        WHERE rule_code = v_rule.rule_code
          AND enabled = TRUE;

        IF v_rule_id IS NULL THEN
            CONTINUE;
        END IF;

        INSERT INTO security_alerts (
            rule_id,
            account_id,
            event_id,
            detected_at,
            user_identifier,
            severity,
            risk_score,
            description,
            indicators
        )
        VALUES (
            v_rule_id,
            v_event.account_id,
            v_event.event_id,
            NOW(),
            v_event.user_identifier,

            CASE
                WHEN v_rule.risk_score >= 90 THEN 'CRITICAL'
                WHEN v_rule.risk_score >= 70 THEN 'HIGH'
                WHEN v_rule.risk_score >= 40 THEN 'MEDIUM'
                ELSE 'LOW'
            END::severity_level,

            v_rule.risk_score,
            v_rule.explanation,

            jsonb_build_object(
                'source_ip', v_event.source_ip::TEXT,
                'resource_id', v_event.resource_id,
                'event_uuid', v_event.event_uuid
            )
        );

    END LOOP;

END;
$$;


/* ============================================================================
   15. INCIDENT CREATION PROCEDURE
============================================================================ */

CREATE OR REPLACE PROCEDURE create_incident_from_alert(
    p_alert_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_alert security_alerts%ROWTYPE;
    v_incident_id BIGINT;
BEGIN
    SELECT *
    INTO v_alert
    FROM security_alerts
    WHERE alert_id = p_alert_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Alert does not exist.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM incident_alerts
        WHERE alert_id = p_alert_id
    ) THEN
        RAISE EXCEPTION
            'Alert is already associated with an incident.';
    END IF;

    INSERT INTO security_incidents (
        title,
        description,
        severity,
        status
    )
    VALUES (
        v_alert.description,
        'Incident created from security alert.',
        v_alert.severity,
        'OPEN'
    )
    RETURNING incident_id INTO v_incident_id;

    INSERT INTO incident_alerts (
        incident_id,
        alert_id
    )
    VALUES (
        v_incident_id,
        p_alert_id
    );

    UPDATE security_alerts
    SET status = 'CORRELATED'
    WHERE alert_id = p_alert_id;

END;
$$;


/* ============================================================================
   16. ELIGIBILITY AND RISK REPORTING
============================================================================ */

CREATE OR REPLACE FUNCTION get_user_risk_score(
    p_user_identifier VARCHAR,
    p_window INTERVAL DEFAULT INTERVAL '24 hours'
)
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_score INTEGER := 0;
    v_failed INTEGER;
    v_privilege INTEGER;
    v_secret INTEGER;
    v_unapproved INTEGER;
BEGIN
    IF p_window <= INTERVAL '0 seconds' THEN
        RAISE EXCEPTION
            'Risk evaluation window must be positive.';
    END IF;

    SELECT
        COUNT(*) FILTER (
            WHERE event_type = 'FAILED_LOGIN'
        ),
        COUNT(*) FILTER (
            WHERE event_type = 'PERMISSION_CHANGE'
        ),
        COUNT(*) FILTER (
            WHERE event_type = 'SECRET_ACCESS'
        ),
        COUNT(*) FILTER (
            WHERE NOT approved_action
              AND event_type IN (
                  'PERMISSION_CHANGE',
                  'SECRET_ACCESS'
              )
        )
    INTO
        v_failed,
        v_privilege,
        v_secret,
        v_unapproved
    FROM audit_events
    WHERE user_identifier = p_user_identifier
      AND event_timestamp >= NOW() - p_window;

    v_score :=
        LEAST(v_failed * 10, 40)
        + LEAST(v_privilege * 15, 30)
        + LEAST(v_secret * 20, 30)
        + LEAST(v_unapproved * 10, 30);

    RETURN LEAST(v_score, 100);
END;
$$;


/* ============================================================================
   17. OPERATIONAL REPORTING QUERIES
============================================================================ */

/*
Query A: Recent audit activity.
*/

SELECT
    event_timestamp,
    event_type,
    user_identifier,
    source_ip,
    action,
    success,
    region
FROM audit_events
ORDER BY event_timestamp DESC
LIMIT 20;


/*
Query B: Alert aggregation by severity.
*/

SELECT
    severity,
    COUNT(*) AS alert_count,
    ROUND(AVG(risk_score), 2) AS average_risk,
    MAX(detected_at) AS latest_alert
FROM security_alerts
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        ELSE 4
    END;


/*
Query C: User risk analysis using a CTE.
*/

WITH user_activity AS (
    SELECT
        user_identifier,
        COUNT(*) AS total_events,

        COUNT(*) FILTER (
            WHERE event_type = 'FAILED_LOGIN'
        ) AS failed_logins,

        COUNT(*) FILTER (
            WHERE event_type = 'PERMISSION_CHANGE'
        ) AS privilege_changes,

        COUNT(*) FILTER (
            WHERE event_type = 'SECRET_ACCESS'
        ) AS secret_accesses

    FROM audit_events
    WHERE event_timestamp >= NOW() - INTERVAL '24 hours'
    GROUP BY user_identifier
)
SELECT
    user_identifier,
    total_events,
    failed_logins,
    privilege_changes,
    secret_accesses,
    get_user_risk_score(
        user_identifier,
        INTERVAL '24 hours'
    ) AS risk_score
FROM user_activity
ORDER BY risk_score DESC;


/*
Query D: Unresolved critical incidents.
*/

SELECT
    incident_id,
    title,
    severity,
    status,
    opened_at,
    assigned_analyst_id
FROM security_incidents
WHERE severity = 'CRITICAL'
  AND status NOT IN ('RESOLVED', 'CLOSED')
ORDER BY opened_at;


/*
Query E: Incident investigation evidence.
*/

SELECT
    i.incident_id,
    i.title,
    e.evidence_type,
    e.evidence_reference,
    e.evidence_sha256,
    e.collected_at
FROM security_incidents i
JOIN incident_evidence e
    ON e.incident_id = i.incident_id
ORDER BY e.collected_at DESC;


/* ============================================================================
   18. SAMPLE DATA
============================================================================ */

INSERT INTO analysts (
    username,
    email,
    role
)
VALUES
(
    'soc_analyst_01',
    'soc01@example.org',
    'SOC_ANALYST'
),
(
    'security_admin_01',
    'admin01@example.org',
    'SECURITY_ADMIN'
),
(
    'incident_responder_01',
    'responder01@example.org',
    'INCIDENT_RESPONDER'
),
(
    'auditor_01',
    'auditor01@example.org',
    'AUDITOR'
);


INSERT INTO cloud_accounts (
    provider,
    external_account_id,
    account_name,
    region,
    environment
)
VALUES
(
    'AWS',
    '123456789012',
    'Production Account',
    'ap-south-1',
    'PRODUCTION'
),
(
    'AZURE',
    'azure-prod-001',
    'Azure Production',
    'centralindia',
    'PRODUCTION'
),
(
    'GCP',
    'gcp-development-001',
    'Development Account',
    'asia-south1',
    'DEVELOPMENT'
);


INSERT INTO cloud_resources (
    account_id,
    resource_external_id,
    resource_name,
    resource_type,
    sensitivity,
    contains_sensitive_data,
    public_exposure,
    encrypted
)
VALUES
(
    1,
    'iam-prod-001',
    'Production IAM',
    'IDENTITY_SERVICE',
    5,
    TRUE,
    FALSE,
    TRUE
),
(
    1,
    'database-prod-001',
    'Production Database',
    'DATABASE',
    5,
    TRUE,
    FALSE,
    TRUE
),
(
    1,
    'storage-prod-001',
    'Production Storage',
    'OBJECT_STORAGE',
    4,
    TRUE,
    FALSE,
    TRUE
),
(
    3,
    'dev-logs-001',
    'Development Logs',
    'LOG_STORAGE',
    2,
    FALSE,
    FALSE,
    TRUE
);


INSERT INTO monitoring_policies (
    policy_name,
    failed_login_threshold,
    failed_login_window,
    privilege_change_threshold,
    privilege_change_window,
    minimum_risk_score,
    require_mfa_for_sensitive_resources,
    require_approved_privilege_changes
)
VALUES (
    'Production Security Policy',
    5,
    INTERVAL '10 minutes',
    3,
    INTERVAL '15 minutes',
    70,
    TRUE,
    TRUE
);


INSERT INTO detection_rules (
    rule_code,
    rule_name,
    description,
    category,
    base_risk_score
)
VALUES
(
    'AUTH-001',
    'Repeated Failed Authentication',
    'Detects repeated failed authentication attempts.',
    'AUTHENTICATION',
    85
),
(
    'IAM-001',
    'Privilege Modification Burst',
    'Detects rapid privilege changes.',
    'AUTHORIZATION',
    95
),
(
    'IAM-002',
    'Unapproved Permission Change',
    'Detects permission modifications without approval.',
    'AUTHORIZATION',
    95
),
(
    'DATA-001',
    'Unapproved Secret Access',
    'Detects unauthorized access to secrets.',
    'DATA_PROTECTION',
    95
),
(
    'IAM-003',
    'Missing MFA',
    'Detects sensitive access without MFA.',
    'AUTHENTICATION',
    90
);


/* ============================================================================
   19. SYNTHETIC AUDIT EVENTS
============================================================================ */

DO $$
DECLARE
    v_base TIMESTAMPTZ := NOW();

    v_event_type event_type;
    v_user VARCHAR(255);
    v_ip INET;
    v_success BOOLEAN;
    v_resource BIGINT;
    v_approved BOOLEAN;
    v_mfa BOOLEAN;

    i INTEGER;
BEGIN

    -- Three historical successful logins establish normal activity.
    FOR i IN 1..3 LOOP
        INSERT INTO audit_events (
            account_id,
            resource_id,
            event_timestamp,
            event_type,
            user_identifier,
            source_ip,
            action,
            success,
            region,
            mfa_used,
            approved_action,
            metadata
        )
        VALUES (
            1,
            1,
            v_base - INTERVAL '3 days'
                + (i * INTERVAL '1 hour'),
            'LOGIN',
            'cloud-admin',
            '10.10.1.10'::INET,
            'authenticate',
            TRUE,
            'ap-south-1',
            TRUE,
            TRUE,
            jsonb_build_object(
                'mfa_method',
                'totp',
                'historical_baseline',
                TRUE
            )
        );
    END LOOP;


    -- Six failed logins within a ten-minute window.
    FOR i IN 1..6 LOOP
        INSERT INTO audit_events (
            account_id,
            resource_id,
            event_timestamp,
            event_type,
            user_identifier,
            source_ip,
            action,
            success,
            region,
            mfa_used,
            approved_action,
            metadata
        )
        VALUES (
            1,
            1,
            v_base + (i * INTERVAL '30 seconds'),
            'FAILED_LOGIN',
            'cloud-admin',
            '203.0.113.25'::INET,
            'authenticate',
            FALSE,
            'ap-south-1',
            FALSE,
            FALSE,
            jsonb_build_object(
                'failure_reason',
                'invalid_credentials',
                'attempt',
                i
            )
        );
    END LOOP;


    -- Unapproved privilege escalation.
    INSERT INTO audit_events (
        account_id,
        resource_id,
        event_timestamp,
        event_type,
        user_identifier,
        source_ip,
        action,
        success,
        region,
        mfa_used,
        approved_action,
        metadata
    )
    VALUES (
        1,
        1,
        v_base + INTERVAL '5 minutes',
        'PERMISSION_CHANGE',
        'cloud-admin',
        '203.0.113.25'::INET,
        'grant_admin',
        TRUE,
        'ap-south-1',
        FALSE,
        FALSE,
        jsonb_build_object(
            'target_user',
            'service-account',
            'requested_role',
            'ADMINISTRATOR'
        )
    );


    -- Unapproved secret access.
    INSERT INTO audit_events (
        account_id,
        resource_id,
        event_timestamp,
        event_type,
        user_identifier,
        source_ip,
        action,
        success,
        region,
        mfa_used,
        approved_action,
        metadata
    )
    VALUES (
        1,
        2,
        v_base + INTERVAL '6 minutes',
        'SECRET_ACCESS',
        'service-account',
        '198.51.100.40'::INET,
        'read_secret',
        TRUE,
        'ap-south-1',
        FALSE,
        FALSE,
        jsonb_build_object(
            'secret_name',
            'database-password',
            'access_method',
            'api'
        )
    );


    -- Valid, approved development activity.
    INSERT INTO audit_events (
        account_id,
        resource_id,
        event_timestamp,
        event_type,
        user_identifier,
        source_ip,
        action,
        success,
        region,
        mfa_used,
        approved_action,
        metadata
    )
    VALUES (
        3,
        4,
        v_base + INTERVAL '7 minutes',
        'LOGIN',
        'developer-101',
        '192.0.2.20'::INET,
        'authenticate',
        TRUE,
        'asia-south1',
        FALSE,
        TRUE,
        jsonb_build_object(
            'environment',
            'development'
        )
    );

END;
$$;


/* ============================================================================
   20. TRANSACTIONAL EVENT PROCESSING
============================================================================ */

DO $$
DECLARE
    v_event RECORD;
BEGIN
    /*
     * Process only the events that have not yet produced alerts.
     * Each event's evaluation and alert insertion are transactional.
     */

    FOR v_event IN
        SELECT e.event_id
        FROM audit_events e
        WHERE NOT EXISTS (
            SELECT 1
            FROM security_alerts a
            WHERE a.event_id = e.event_id
        )
        ORDER BY e.event_timestamp, e.event_id
    LOOP
        CALL process_security_event(v_event.event_id);
    END LOOP;

END;
$$;


/* ============================================================================
   21. INCIDENT CORRELATION
============================================================================ */

DO $$
DECLARE
    v_alert RECORD;
BEGIN
    FOR v_alert IN
        SELECT alert_id
        FROM security_alerts
        WHERE status = 'NEW'
        ORDER BY risk_score DESC, detected_at
    LOOP
        CALL create_incident_from_alert(
            v_alert.alert_id
        );
    END LOOP;
END;
$$;


/* ============================================================================
   22. INVESTIGATION WORKFLOW
============================================================================ */

DO $$
DECLARE
    v_incident BIGINT;
    v_analyst BIGINT;
BEGIN

    SELECT analyst_id
    INTO v_analyst
    FROM analysts
    WHERE username = 'soc_analyst_01';

    SELECT incident_id
    INTO v_incident
    FROM security_incidents
    WHERE status = 'OPEN'
    ORDER BY
        CASE severity
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            ELSE 4
        END,
        opened_at
    LIMIT 1;

    IF v_incident IS NOT NULL THEN

        UPDATE security_incidents
        SET
            assigned_analyst_id = v_analyst,
            status = 'INVESTIGATING'
        WHERE incident_id = v_incident;

        INSERT INTO incident_notes (
            incident_id,
            analyst_id,
            note
        )
        VALUES (
            v_incident,
            v_analyst,
            'Initial triage completed. Audit events retained.'
        );

        INSERT INTO incident_evidence (
            incident_id,
            evidence_type,
            evidence_reference,
            evidence_sha256,
            collected_by,
            description
        )
        VALUES (
            v_incident,
            'ANALYST_NOTE',
            'audit-event-investigation',
            encode(
                sha256(
                    convert_to(
                        'Synthetic cloud investigation evidence',
                        'UTF8'
                    )
                ),
                'hex'
            ),
            v_analyst,
            'Initial investigation evidence fingerprint.'
        );

    END IF;

END;
$$;


/* ============================================================================
   23. VALIDATION QUERIES
============================================================================ */

/*
Detect failed authentication bursts.
*/

SELECT
    user_identifier,
    source_ip,
    COUNT(*) AS failed_attempts,
    MIN(event_timestamp) AS first_attempt,
    MAX(event_timestamp) AS last_attempt
FROM audit_events
WHERE event_type = 'FAILED_LOGIN'
  AND event_timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY
    user_identifier,
    source_ip
HAVING COUNT(*) >= 5;


/*
Find unapproved privilege changes.
*/

SELECT
    event_id,
    user_identifier,
    source_ip,
    resource_id,
    event_timestamp,
    metadata
FROM audit_events
WHERE event_type = 'PERMISSION_CHANGE'
  AND approved_action = FALSE;


/*
Identify sensitive resource access without MFA.
*/

SELECT
    e.event_id,
    e.user_identifier,
    e.event_timestamp,
    r.resource_name,
    r.sensitivity
FROM audit_events e
JOIN cloud_resources r
    ON r.resource_id = e.resource_id
WHERE e.success
  AND e.mfa_used = FALSE
  AND r.sensitivity >= 4;


/* ============================================================================
   24. AGGREGATION AND REPORTING
============================================================================ */

SELECT
    provider,
    environment,
    COUNT(*) AS account_count
FROM cloud_accounts
GROUP BY provider, environment
ORDER BY provider, environment;


SELECT
    severity,
    status,
    COUNT(*) AS incident_count
FROM security_incidents
GROUP BY severity, status
ORDER BY severity, status;


SELECT
    username,
    role,
    active
FROM analysts
ORDER BY role, username;


SELECT
    rule_code,
    rule_name,
    COUNT(al.alert_id) AS generated_alerts,
    ROUND(AVG(al.risk_score), 2) AS average_risk
FROM detection_rules dr
LEFT JOIN security_alerts al
    ON al.rule_id = dr.rule_id
GROUP BY
    dr.rule_id,
    dr.rule_code,
    dr.rule_name
ORDER BY generated_alerts DESC;


/* ============================================================================
   25. USER RISK EVALUATION
============================================================================ */

SELECT
    user_identifier,
    get_user_risk_score(
        user_identifier,
        INTERVAL '24 hours'
    ) AS risk_score
FROM (
    SELECT DISTINCT user_identifier
    FROM audit_events
) users
ORDER BY risk_score DESC;


/* ============================================================================
   26. INCIDENT INVESTIGATION REPORT
============================================================================ */

SELECT
    i.incident_id,
    i.title,
    i.severity,
    i.status,
    a.username AS analyst,
    COUNT(DISTINCT ia.alert_id) AS alerts,
    COUNT(DISTINCT ev.evidence_id) AS evidence_items,
    COUNT(DISTINCT n.note_id) AS investigation_notes
FROM security_incidents i
LEFT JOIN analysts a
    ON a.analyst_id = i.assigned_analyst_id
LEFT JOIN incident_alerts ia
    ON ia.incident_id = i.incident_id
LEFT JOIN incident_evidence ev
    ON ev.incident_id = i.incident_id
LEFT JOIN incident_notes n
    ON n.incident_id = i.incident_id
GROUP BY
    i.incident_id,
    a.username
ORDER BY i.opened_at DESC;


/* ============================================================================
   27. POLICY VALIDATION REPORT
============================================================================ */

SELECT
    ca.account_name,
    r.resource_name,
    r.sensitivity,
    r.contains_sensitive_data,
    r.public_exposure,
    r.encrypted,

    CASE
        WHEN r.sensitivity >= 4 AND NOT r.encrypted
            THEN 'CRITICAL: SENSITIVE RESOURCE NOT ENCRYPTED'

        WHEN r.sensitivity >= 4 AND r.public_exposure
            THEN 'HIGH: SENSITIVE RESOURCE PUBLICLY EXPOSED'

        WHEN r.sensitivity >= 4
            THEN 'REQUIRES STRONG ACCESS CONTROLS'

        ELSE 'STANDARD MONITORING'
    END AS policy_result

FROM cloud_resources r
JOIN cloud_accounts ca
    ON ca.account_id = r.account_id
ORDER BY r.sensitivity DESC;


/* ============================================================================
   28. PERFORMANCE STATISTICS
============================================================================ */

ANALYZE analysts;
ANALYZE cloud_accounts;
ANALYZE cloud_resources;
ANALYZE audit_events;
ANALYZE security_alerts;
ANALYZE security_incidents;
ANALYZE incident_alerts;
ANALYZE incident_evidence;


/* ============================================================================
   29. FINAL DASHBOARD
============================================================================ */

SELECT
    (SELECT COUNT(*) FROM audit_events) AS total_events,

    (SELECT COUNT(*) FROM security_alerts) AS total_alerts,

    (SELECT COUNT(*) FROM security_incidents) AS total_incidents,

    (
        SELECT COUNT(*)
        FROM security_incidents
        WHERE status IN ('OPEN', 'INVESTIGATING')
    ) AS active_incidents,

    (
        SELECT COUNT(*)
        FROM security_alerts
        WHERE severity = 'CRITICAL'
    ) AS critical_alerts,

    (
        SELECT COUNT(*)
        FROM security_incidents
        WHERE status = 'CONTAINED'
    ) AS contained_incidents;


/*
The transaction is committed only after the schema, synthetic evidence,
detections, alert records, and incident workflow have been created.
*/

COMMIT;


===============================================================================
OPERATIONAL SECURITY NOTES

1. Audit events are append-only at the database trigger level.
2. Database administrators can still bypass ordinary trigger controls;
   production evidence protection requires restricted privileges,
   independent backups, and external tamper-evident storage.
3. The event-processing procedure is transaction-safe but does not provide
   an external message-queue delivery guarantee.
4. The detection function evaluates deterministic rules, not a trained
   statistical anomaly-detection model.
5. User risk scoring is a configurable heuristic, not a probability.
6. The sample source addresses are reserved documentation addresses.
7. Production deployment should use row-level security, separate ingestion
   and analyst roles, encrypted connections, secret management, and
   controlled retention policies.
===============================================================================
*/
