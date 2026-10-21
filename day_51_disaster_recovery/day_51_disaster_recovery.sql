DROP SCHEMA IF EXISTS disaster_recovery CASCADE;
CREATE SCHEMA disaster_recovery;

SET search_path = disaster_recovery, public;

-- Recovery tiers represent progressively lower recovery latency.
CREATE TYPE recovery_tier AS ENUM (
    'backup_restore',
    'pilot_light',
    'warm_standby',
    'multi_region'
);

CREATE TYPE region_state AS ENUM (
    'primary',
    'secondary',
    'failed'
);

CREATE TYPE service_state AS ENUM (
    'healthy',
    'degraded',
    'recovering',
    'recovered'
);

CREATE TYPE backup_status AS ENUM (
    'completed',
    'failed',
    'verifying'
);

CREATE TYPE review_decision AS ENUM (
    'approved',
    'rejected',
    'dismissed'
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    owner_team TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE regions (
    region_id BIGSERIAL PRIMARY KEY,
    region_name TEXT NOT NULL UNIQUE,
    state region_state NOT NULL DEFAULT 'secondary',
    capacity_percent INTEGER NOT NULL DEFAULT 100
        CHECK (capacity_percent BETWEEN 0 AND 100)
);

CREATE TABLE services (
    service_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    service_name TEXT NOT NULL,
    state service_state NOT NULL DEFAULT 'healthy',
    recovery_tier recovery_tier NOT NULL,
    rpo_minutes INTEGER NOT NULL
        CHECK (rpo_minutes >= 0),
    rto_minutes INTEGER NOT NULL
        CHECK (rto_minutes > 0),
    primary_region_id BIGINT NOT NULL
        REFERENCES regions(region_id),
    UNIQUE (repository_id, service_name)
);

CREATE TABLE service_regions (
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,
    region_id BIGINT NOT NULL
        REFERENCES regions(region_id)
        ON DELETE CASCADE,
    is_configured BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (service_id, region_id)
);

CREATE TABLE backups (
    backup_id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,
    region_id BIGINT NOT NULL
        REFERENCES regions(region_id),
    backup_status backup_status NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    checksum TEXT NOT NULL,
    size_mb INTEGER NOT NULL CHECK (size_mb > 0),
    CHECK (
        backup_status <> 'completed'
        OR verified_at IS NOT NULL
    )
);

CREATE TABLE review_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL UNIQUE
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    required_approvals INTEGER NOT NULL
        CHECK (required_approvals > 0),
    dismiss_stale_approvals BOOLEAN NOT NULL DEFAULT TRUE,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE reviewers (
    reviewer_id BIGSERIAL PRIMARY KEY,
    reviewer_name TEXT NOT NULL UNIQUE,
    team_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE service_approvals (
    approval_id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES reviewers(reviewer_id),
    decision review_decision NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stale BOOLEAN NOT NULL DEFAULT FALSE,
    dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (service_id, reviewer_id)
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (service_id, check_name)
);

CREATE TABLE recovery_events (
    event_id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,
    failed_region_id BIGINT NOT NULL
        REFERENCES regions(region_id),
    target_region_id BIGINT NOT NULL
        REFERENCES regions(region_id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    result TEXT NOT NULL,
    CHECK (failed_region_id <> target_region_id)
);

CREATE INDEX idx_backups_service_created
    ON backups(service_id, created_at DESC);

CREATE INDEX idx_status_checks_service
    ON status_checks(service_id);

CREATE INDEX idx_approvals_service
    ON service_approvals(service_id);

CREATE INDEX idx_recovery_events_service_started
    ON recovery_events(service_id, started_at DESC);

CREATE OR REPLACE FUNCTION validate_primary_region()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    region_state_value region_state;
BEGIN
    SELECT state
    INTO region_state_value
    FROM regions
    WHERE region_id = NEW.primary_region_id;

    IF region_state_value IS NULL THEN
        RAISE EXCEPTION 'Primary region does not exist';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_primary_region
BEFORE INSERT OR UPDATE OF primary_region_id
ON services
FOR EACH ROW
EXECUTE FUNCTION validate_primary_region();

CREATE OR REPLACE FUNCTION evaluate_recovery(
    p_service_id BIGINT,
    p_target_region_id BIGINT
)
RETURNS TABLE (
    service_name TEXT,
    recovery_tier recovery_tier,
    primary_failed BOOLEAN,
    target_available BOOLEAN,
    target_configured BOOLEAN,
    backup_available BOOLEAN,
    rpo_met BOOLEAN,
    rto_met BOOLEAN,
    approvals_met BOOLEAN,
    status_checks_met BOOLEAN,
    estimated_rpo_minutes NUMERIC,
    estimated_rto_minutes INTEGER,
    recovery_eligible BOOLEAN
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_primary_region BIGINT;
    v_rpo INTEGER;
    v_rto INTEGER;
    v_tier recovery_tier;
    v_required_approvals INTEGER;
    v_latest_backup TIMESTAMPTZ;
    v_backup_verified BOOLEAN;
    v_primary_failed BOOLEAN;
    v_target_available BOOLEAN;
    v_target_configured BOOLEAN;
    v_backup_available BOOLEAN;
    v_rpo_met BOOLEAN;
    v_rto_met BOOLEAN;
    v_approvals_met BOOLEAN;
    v_checks_met BOOLEAN;
    v_estimated_rto INTEGER;
    v_estimated_rpo NUMERIC;
BEGIN
    SELECT
        s.service_name,
        s.primary_region_id,
        s.rpo_minutes,
        s.rto_minutes,
        s.recovery_tier
    INTO
        service_name,
        v_primary_region,
        v_rpo,
        v_rto,
        v_tier
    FROM services s
    WHERE s.service_id = p_service_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown service: %', p_service_id;
    END IF;

    SELECT
        COALESCE(r.state = 'failed', FALSE)
    INTO v_primary_failed
    FROM regions r
    WHERE r.region_id = v_primary_region;

    SELECT
        r.state <> 'failed'
        AND r.capacity_percent > 0
    INTO v_target_available
    FROM regions r
    WHERE r.region_id = p_target_region_id;

    IF v_target_available IS NULL THEN
        v_target_available := FALSE;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM service_regions sr
        WHERE sr.service_id = p_service_id
          AND sr.region_id = p_target_region_id
          AND sr.is_configured
    )
    INTO v_target_configured;

    SELECT
        b.created_at,
        TRUE
    INTO
        v_latest_backup,
        v_backup_verified
    FROM backups b
    WHERE b.service_id = p_service_id
      AND b.backup_status = 'completed'
      AND b.verified_at IS NOT NULL
    ORDER BY b.created_at DESC
    LIMIT 1;

    v_backup_available := v_latest_backup IS NOT NULL;

    IF v_backup_available THEN
        v_estimated_rpo :=
            EXTRACT(EPOCH FROM (now() - v_latest_backup)) / 60.0;
    ELSE
        v_estimated_rpo := NULL;
    END IF;

    v_rpo_met :=
        v_backup_available
        AND v_estimated_rpo <= v_rpo;

    v_estimated_rto := CASE v_tier
        WHEN 'backup_restore' THEN 90
        WHEN 'pilot_light' THEN 30
        WHEN 'warm_standby' THEN 10
        WHEN 'multi_region' THEN 2
    END;

    v_rto_met := v_estimated_rto <= v_rto;

    SELECT COUNT(*) >= rp.required_approvals
    INTO v_approvals_met
    FROM review_policies rp
    JOIN repositories r
      ON r.repository_id = rp.repository_id
    JOIN services s
      ON s.repository_id = r.repository_id
    JOIN service_approvals sa
      ON sa.service_id = s.service_id
    JOIN reviewers rv
      ON rv.reviewer_id = sa.reviewer_id
    WHERE s.service_id = p_service_id
      AND rv.active
      AND sa.decision = 'approved'
      AND NOT sa.stale
      AND NOT sa.dismissed;

    IF v_approvals_met IS NULL THEN
        v_approvals_met := FALSE;
    END IF;

    SELECT NOT EXISTS (
        SELECT 1
        FROM status_checks sc
        WHERE sc.service_id = p_service_id
          AND NOT sc.passed
    )
    AND EXISTS (
        SELECT 1
        FROM status_checks sc
        WHERE sc.service_id = p_service_id
    )
    INTO v_checks_met;

    recovery_tier := v_tier;
    target_available := v_target_available;
    target_configured := v_target_configured;
    backup_available := v_backup_available;
    rpo_met := v_rpo_met;
    rto_met := v_rto_met;
    approvals_met := v_approvals_met;
    status_checks_met := v_checks_met;
    estimated_rpo_minutes := v_estimated_rpo;
    estimated_rto_minutes := v_estimated_rto;

    recovery_eligible :=
        v_primary_failed
        AND v_target_available
        AND v_target_configured
        AND v_backup_available
        AND v_rpo_met
        AND v_rto_met
        AND v_approvals_met
        AND v_checks_met;

    primary_failed := v_primary_failed;

    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION execute_recovery(
    p_service_id BIGINT,
    p_target_region_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_primary_region BIGINT;
    v_eligible BOOLEAN;
BEGIN
    SELECT primary_region_id
    INTO v_primary_region
    FROM services
    WHERE service_id = p_service_id
    FOR UPDATE;

    IF v_primary_region IS NULL THEN
        RAISE EXCEPTION 'Service does not exist: %', p_service_id;
    END IF;

    SELECT recovery_eligible
    INTO v_eligible
    FROM evaluate_recovery(
        p_service_id,
        p_target_region_id
    );

    IF NOT v_eligible THEN
        RAISE EXCEPTION
            'Recovery policy rejected failover for service %',
            p_service_id;
    END IF;

    UPDATE services
    SET state = 'recovering'
    WHERE service_id = p_service_id;

    UPDATE regions
    SET state = 'failed'
    WHERE region_id = v_primary_region;

    UPDATE regions
    SET state = 'primary'
    WHERE region_id = p_target_region_id;

    UPDATE services
    SET
        primary_region_id = p_target_region_id,
        state = 'recovered'
    WHERE service_id = p_service_id;

    INSERT INTO recovery_events (
        service_id,
        failed_region_id,
        target_region_id,
        completed_at,
        result
    )
    VALUES (
        p_service_id,
        v_primary_region,
        p_target_region_id,
        now(),
        'completed'
    );
END;
$$;

CREATE OR REPLACE VIEW recovery_readiness AS
SELECT
    s.service_id,
    s.service_name,
    s.recovery_tier,
    s.rpo_minutes,
    s.rto_minutes,
    r.region_name AS primary_region,
    r.state AS primary_region_state,
    b.created_at AS latest_backup_at,
    EXTRACT(
        EPOCH FROM (now() - b.created_at)
    ) / 60.0 AS backup_age_minutes,
    (
        b.backup_id IS NOT NULL
        AND b.backup_status = 'completed'
        AND b.verified_at IS NOT NULL
    ) AS backup_ready
FROM services s
JOIN regions r
    ON r.region_id = s.primary_region_id
LEFT JOIN LATERAL (
    SELECT *
    FROM backups b
    WHERE b.service_id = s.service_id
    ORDER BY b.created_at DESC
    LIMIT 1
) b ON TRUE;

INSERT INTO repositories (
    repository_name,
    owner_team
)
VALUES
    ('payments-platform', 'platform-engineering'),
    ('analytics-platform', 'data-engineering'),
    ('catalog-platform', 'commerce-engineering');

INSERT INTO regions (
    region_name,
    state,
    capacity_percent
)
VALUES
    ('ap-south-1', 'primary', 100),
    ('ap-southeast-1', 'secondary', 100),
    ('eu-west-1', 'primary', 100),
    ('eu-central-1', 'secondary', 100),
    ('us-east-2', 'failed', 0);

INSERT INTO services (
    repository_id,
    service_name,
    recovery_tier,
    rpo_minutes,
    rto_minutes,
    primary_region_id
)
SELECT
    r.repository_id,
    'payments',
    'warm_standby',
    5,
    15,
    rg.region_id
FROM repositories r
JOIN regions rg
    ON rg.region_name = 'ap-south-1'
WHERE r.repository_name = 'payments-platform';

INSERT INTO services (
    repository_id,
    service_name,
    recovery_tier,
    rpo_minutes,
    rto_minutes,
    primary_region_id
)
SELECT
    r.repository_id,
    'analytics',
    'backup_restore',
    30,
    60,
    rg.region_id
FROM repositories r
JOIN regions rg
    ON rg.region_name = 'eu-west-1'
WHERE r.repository_name = 'analytics-platform';

INSERT INTO services (
    repository_id,
    service_name,
    recovery_tier,
    rpo_minutes,
    rto_minutes,
    primary_region_id
)
SELECT
    r.repository_id,
    'catalog',
    'multi_region',
    1,
    5,
    rg.region_id
FROM repositories r
JOIN regions rg
    ON rg.region_name = 'ap-southeast-1'
WHERE r.repository_name = 'catalog-platform';

INSERT INTO service_regions (
    service_id,
    region_id
)
SELECT s.service_id, r.region_id
FROM services s
JOIN regions r
    ON r.region_name IN ('ap-south-1', 'ap-southeast-1')
WHERE s.service_name = 'payments';

INSERT INTO service_regions (
    service_id,
    region_id
)
SELECT s.service_id, r.region_id
FROM services s
JOIN regions r
    ON r.region_name IN ('eu-west-1', 'eu-central-1')
WHERE s.service_name = 'analytics';

INSERT INTO service_regions (
    service_id,
    region_id
)
SELECT s.service_id, r.region_id
FROM services s
JOIN regions r
    ON r.region_name IN ('ap-southeast-1', 'us-east-2')
WHERE s.service_name = 'catalog';

INSERT INTO review_policies (
    repository_id,
    required_approvals,
    dismiss_stale_approvals,
    require_conversation_resolution
)
SELECT repository_id, 2, TRUE, TRUE
FROM repositories;

INSERT INTO reviewers (
    reviewer_name,
    team_name
)
VALUES
    ('platform-owner', 'platform-engineering'),
    ('security-owner', 'security'),
    ('analytics-owner', 'data-engineering');

INSERT INTO backups (
    service_id,
    region_id,
    backup_status,
    created_at,
    verified_at,
    checksum,
    size_mb
)
SELECT
    s.service_id,
    r.region_id,
    'completed',
    now() - interval '2 minutes',
    now() - interval '1 minute',
    'payments-checksum-001',
    512
FROM services s
JOIN regions r
    ON r.region_name = 'ap-southeast-1'
WHERE s.service_name = 'payments';

INSERT INTO backups (
    service_id,
    region_id,
    backup_status,
    created_at,
    verified_at,
    checksum,
    size_mb
)
SELECT
    s.service_id,
    r.region_id,
    'completed',
    now() - interval '45 minutes',
    now() - interval '44 minutes',
    'analytics-checksum-001',
    2048
FROM services s
JOIN regions r
    ON r.region_name = 'eu-central-1'
WHERE s.service_name = 'analytics';

INSERT INTO backups (
    service_id,
    region_id,
    backup_status,
    created_at,
    verified_at,
    checksum,
    size_mb
)
SELECT
    s.service_id,
    r.region_id,
    'completed',
    now(),
    now(),
    'catalog-checksum-001',
    1024
FROM services s
JOIN regions r
    ON r.region_name = 'us-east-2'
WHERE s.service_name = 'catalog';

INSERT INTO status_checks (
    service_id,
    check_name,
    passed
)
SELECT
    s.service_id,
    checks.check_name,
    checks.passed
FROM services s
CROSS JOIN (
    VALUES
        ('backup-integrity', TRUE),
        ('replication-health', TRUE),
        ('security-validation', TRUE)
) AS checks(check_name, passed);

INSERT INTO service_approvals (
    service_id,
    reviewer_id,
    decision,
    stale,
    dismissed
)
SELECT
    s.service_id,
    rv.reviewer_id,
    CASE
        WHEN s.service_name = 'analytics'
             AND rv.reviewer_name = 'security-owner'
            THEN 'rejected'::review_decision
        ELSE 'approved'::review_decision
    END,
    FALSE,
    FALSE
FROM services s
JOIN reviewers rv
    ON rv.reviewer_name IN (
        'platform-owner',
        'security-owner',
        'analytics-owner'
    );

-- Readiness report shows backup freshness independently of failover.
SELECT *
FROM recovery_readiness
ORDER BY service_name;

-- The payments service satisfies its five-minute RPO,
-- ten-minute warm-standby estimate, two-reviewer policy,
-- and all status checks.
SELECT *
FROM evaluate_recovery(
    (
        SELECT service_id
        FROM services
        WHERE service_name = 'payments'
    ),
    (
        SELECT region_id
        FROM regions
        WHERE region_name = 'ap-southeast-1'
    )
);

-- Analytics intentionally fails RPO and approval requirements.
SELECT *
FROM evaluate_recovery(
    (
        SELECT service_id
        FROM services
        WHERE service_name = 'analytics'
    ),
    (
        SELECT region_id
        FROM regions
        WHERE region_name = 'eu-central-1'
    )
);

-- Catalog has a configured second region, but it has zero capacity
-- and is therefore not an available recovery target.
SELECT *
FROM evaluate_recovery(
    (
        SELECT service_id
        FROM services
        WHERE service_name = 'catalog'
    ),
    (
        SELECT region_id
        FROM regions
        WHERE region_name = 'us-east-2'
    )
);

-- A transaction protects the state transition from partial updates.
BEGIN;

SELECT execute_recovery(
    (
        SELECT service_id
        FROM services
        WHERE service_name = 'payments'
    ),
    (
        SELECT region_id
        FROM regions
        WHERE region_name = 'ap-southeast-1'
    )
);

COMMIT;

-- After successful recovery, the former primary is failed and
-- the secondary is promoted.
SELECT
    s.service_name,
    r.region_name AS current_primary_region,
    r.state,
    s.state AS service_state
FROM services s
JOIN regions r
    ON r.region_id = s.primary_region_id
ORDER BY s.service_name;

-- CTE reporting identifies services whose latest verified backup
-- is older than the declared RPO.
WITH latest_verified_backup AS (
    SELECT DISTINCT ON (b.service_id)
        b.service_id,
        b.created_at
    FROM backups b
    WHERE b.backup_status = 'completed'
      AND b.verified_at IS NOT NULL
    ORDER BY b.service_id, b.created_at DESC
)
SELECT
    s.service_name,
    s.rpo_minutes,
    ROUND(
        EXTRACT(
            EPOCH FROM (now() - l.created_at)
        ) / 60.0,
        2
    ) AS backup_age_minutes,
    CASE
        WHEN EXTRACT(
            EPOCH FROM (now() - l.created_at)
        ) / 60.0 <= s.rpo_minutes
        THEN 'within_rpo'
        ELSE 'outside_rpo'
    END AS rpo_status
FROM services s
LEFT JOIN latest_verified_backup l
    ON l.service_id = s.service_id
ORDER BY s.service_name;

-- The following intentionally fails because execute_recovery()
-- enforces the complete recovery policy rather than changing only
-- the region state.
BEGIN;

DO $$
BEGIN
    BEGIN
        PERFORM execute_recovery(
            (
                SELECT service_id
                FROM services
                WHERE service_name = 'analytics'
            ),
            (
                SELECT region_id
                FROM regions
                WHERE region_name = 'eu-central-1'
            )
        );
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected recovery rejection: %', SQLERRM;
    END;
END;
$$;

ROLLBACK;
