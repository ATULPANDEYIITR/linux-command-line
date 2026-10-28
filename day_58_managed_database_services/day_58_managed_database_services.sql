DROP SCHEMA IF EXISTS managed_db CASCADE;
CREATE SCHEMA managed_db;

SET search_path = managed_db, public;

-- Managed database services are represented as an operational control plane.
-- Application data is intentionally separate from service-management metadata.

CREATE TYPE database_state AS ENUM (
    'available',
    'maintenance',
    'failing_over',
    'degraded',
    'failed'
);

CREATE TYPE replica_state AS ENUM (
    'creating',
    'streaming',
    'lagging',
    'failed'
);

CREATE TYPE backup_type AS ENUM (
    'snapshot',
    'full',
    'transaction_log'
);

CREATE TYPE review_result AS ENUM (
    'pass',
    'fail'
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    owner_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE databases (
    database_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT REFERENCES repositories(repository_id),
    database_name TEXT NOT NULL UNIQUE,
    engine TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    primary_region TEXT NOT NULL,
    state database_state NOT NULL DEFAULT 'available',
    storage_gb INTEGER NOT NULL CHECK (storage_gb >= 20),
    compute_units INTEGER NOT NULL CHECK (compute_units > 0),
    multi_az BOOLEAN NOT NULL DEFAULT false,
    backup_retention_days INTEGER NOT NULL
        CHECK (backup_retention_days BETWEEN 0 AND 35),
    maintenance_window_start TIME NOT NULL DEFAULT '02:00',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    database_id BIGINT NOT NULL REFERENCES databases(database_id)
        ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    is_protected BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (database_id, branch_name)
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(branch_id)
        ON DELETE CASCADE,
    commit_hash CHAR(40) NOT NULL UNIQUE,
    message TEXT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pull_requests (
    pull_request_id BIGSERIAL PRIMARY KEY,
    database_id BIGINT NOT NULL REFERENCES databases(database_id)
        ON DELETE CASCADE,
    source_branch_id BIGINT NOT NULL REFERENCES branches(branch_id),
    target_branch_id BIGINT NOT NULL REFERENCES branches(branch_id),
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'open', 'closed', 'merged')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    merged_at TIMESTAMPTZ,
    CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE reviewers (
    reviewer_id BIGSERIAL PRIMARY KEY,
    reviewer_name TEXT NOT NULL UNIQUE,
    role_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL REFERENCES reviewers(reviewer_id),
    decision review_result NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stale BOOLEAN NOT NULL DEFAULT false,
    dismissed BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (pull_request_id, reviewer_id, submitted_at)
);

CREATE TABLE review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL REFERENCES reviews(review_id)
        ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    comment_text TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pull_request_id, check_name)
);

CREATE TABLE backups (
    backup_id BIGSERIAL PRIMARY KEY,
    database_id BIGINT NOT NULL REFERENCES databases(database_id)
        ON DELETE CASCADE,
    backup_type backup_type NOT NULL,
    lsn BIGINT NOT NULL CHECK (lsn >= 0),
    size_gb NUMERIC(12,2) NOT NULL CHECK (size_gb > 0),
    checksum TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE replicas (
    replica_id BIGSERIAL PRIMARY KEY,
    database_id BIGINT NOT NULL REFERENCES databases(database_id)
        ON DELETE CASCADE,
    region TEXT NOT NULL,
    state replica_state NOT NULL DEFAULT 'creating',
    lag_seconds INTEGER NOT NULL DEFAULT 0 CHECK (lag_seconds >= 0),
    replayed_lsn BIGINT NOT NULL DEFAULT 0 CHECK (replayed_lsn >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (database_id, region)
);

CREATE TABLE branch_protection_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE REFERENCES branches(branch_id)
        ON DELETE CASCADE,
    required_reviews INTEGER NOT NULL DEFAULT 1
        CHECK (required_reviews >= 0),
    require_status_checks BOOLEAN NOT NULL DEFAULT true,
    require_conversations_resolved BOOLEAN NOT NULL DEFAULT true,
    allow_direct_push BOOLEAN NOT NULL DEFAULT false,
    allow_force_push BOOLEAN NOT NULL DEFAULT false,
    allow_branch_deletion BOOLEAN NOT NULL DEFAULT false,
    require_linear_history BOOLEAN NOT NULL DEFAULT false,
    allow_administrator_bypass BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE approval_requirements (
    requirement_id BIGSERIAL PRIMARY KEY,
    policy_id BIGINT NOT NULL REFERENCES branch_protection_policies(policy_id)
        ON DELETE CASCADE,
    reviewer_role TEXT NOT NULL,
    minimum_count INTEGER NOT NULL CHECK (minimum_count > 0)
);

CREATE TABLE merge_eligibility (
    eligibility_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL UNIQUE
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    eligible BOOLEAN NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT NOT NULL
);

CREATE INDEX idx_backups_database_created
    ON backups (database_id, created_at DESC);

CREATE INDEX idx_replicas_database_state
    ON replicas (database_id, state);

CREATE INDEX idx_reviews_pr_active
    ON reviews (pull_request_id, stale, dismissed);

CREATE INDEX idx_status_checks_pr
    ON status_checks (pull_request_id, passed);

CREATE VIEW database_health AS
SELECT
    d.database_id,
    d.database_name,
    d.engine,
    d.engine_version,
    d.primary_region,
    d.state,
    d.storage_gb,
    d.compute_units,
    d.multi_az,
    COUNT(r.replica_id) AS replica_count,
    COUNT(*) FILTER (
        WHERE r.state = 'streaming'
          AND r.lag_seconds <= 60
    ) AS healthy_replica_count,
    COUNT(b.backup_id) AS backup_count
FROM databases d
LEFT JOIN replicas r ON r.database_id = d.database_id
LEFT JOIN backups b ON b.database_id = d.database_id
GROUP BY
    d.database_id,
    d.database_name,
    d.engine,
    d.engine_version,
    d.primary_region,
    d.state,
    d.storage_gb,
    d.compute_units,
    d.multi_az;

CREATE OR REPLACE FUNCTION validate_replica_region()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    primary_region TEXT;
BEGIN
    SELECT d.primary_region
    INTO primary_region
    FROM databases d
    WHERE d.database_id = NEW.database_id;

    IF NEW.region = primary_region THEN
        RAISE EXCEPTION
            'Replica region % cannot equal primary region %',
            NEW.region,
            primary_region;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_replica_region
BEFORE INSERT OR UPDATE ON replicas
FOR EACH ROW
EXECUTE FUNCTION validate_replica_region();

CREATE OR REPLACE FUNCTION validate_pr_branches()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    source_database BIGINT;
    target_database BIGINT;
BEGIN
    SELECT database_id INTO source_database
    FROM branches
    WHERE branch_id = NEW.source_branch_id;

    SELECT database_id INTO target_database
    FROM branches
    WHERE branch_id = NEW.target_branch_id;

    IF source_database <> NEW.database_id
       OR target_database <> NEW.database_id THEN
        RAISE EXCEPTION
            'Pull request branches must belong to the specified database';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_pr_branches
BEFORE INSERT OR UPDATE ON pull_requests
FOR EACH ROW
EXECUTE FUNCTION validate_pr_branches();

CREATE OR REPLACE FUNCTION evaluate_merge_eligibility(
    p_pull_request_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    pr RECORD;
    policy RECORD;
    approved_count INTEGER;
    failed_checks INTEGER;
    unresolved_comments INTEGER;
    database_ok BOOLEAN;
    healthy_replica_count INTEGER;
    backup_count INTEGER;
BEGIN
    SELECT
        pr.*,
        target.is_protected
    INTO pr
    FROM pull_requests pr
    JOIN branches target
      ON target.branch_id = pr.target_branch_id
    WHERE pr.pull_request_id = p_pull_request_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'Pull request does not exist';
        RETURN;
    END IF;

    IF pr.status <> 'open' THEN
        RETURN QUERY SELECT false, 'Pull request is not open';
        RETURN;
    END IF;

    SELECT *
    INTO policy
    FROM branch_protection_policies
    WHERE branch_id = pr.target_branch_id;

    SELECT COUNT(*)
    INTO approved_count
    FROM reviews r
    WHERE r.pull_request_id = p_pull_request_id
      AND r.decision = 'pass'
      AND NOT r.stale
      AND NOT r.dismissed;

    SELECT COUNT(*)
    INTO failed_checks
    FROM status_checks s
    WHERE s.pull_request_id = p_pull_request_id
      AND NOT s.passed;

    SELECT COUNT(*)
    INTO unresolved_comments
    FROM review_comments c
    JOIN reviews r ON r.review_id = c.review_id
    WHERE r.pull_request_id = p_pull_request_id
      AND NOT c.resolved;

    SELECT
        d.state = 'available',
        COUNT(DISTINCT r.replica_id)
            FILTER (
                WHERE r.state = 'streaming'
                  AND r.lag_seconds <= 60
            ),
        COUNT(DISTINCT b.backup_id)
    INTO database_ok, healthy_replica_count, backup_count
    FROM databases d
    LEFT JOIN replicas r ON r.database_id = d.database_id
    LEFT JOIN backups b ON b.database_id = d.database_id
    WHERE d.database_id = pr.database_id
    GROUP BY d.state;

    IF NOT database_ok THEN
        RETURN QUERY SELECT false, 'Managed database is not available';
        RETURN;
    END IF;

    IF policy.required_reviews > approved_count THEN
        RETURN QUERY SELECT false,
            format(
                'Required approvals=%s, valid approvals=%s',
                policy.required_reviews,
                approved_count
            );
        RETURN;
    END IF;

    IF policy.require_status_checks AND failed_checks > 0 THEN
        RETURN QUERY SELECT false, 'A required status check failed';
        RETURN;
    END IF;

    IF policy.require_conversations_resolved
       AND unresolved_comments > 0 THEN
        RETURN QUERY SELECT false, 'Unresolved review conversations exist';
        RETURN;
    END IF;

    IF healthy_replica_count = 0 THEN
        RETURN QUERY SELECT false, 'No healthy database replica exists';
        RETURN;
    END IF;

    IF backup_count = 0 THEN
        RETURN QUERY SELECT false, 'No database backup exists';
        RETURN;
    END IF;

    RETURN QUERY SELECT true,
        'Pull request satisfies repository and managed-database gates';
END;
$$;

CREATE OR REPLACE FUNCTION refresh_merge_eligibility(
    p_pull_request_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    evaluation RECORD;
BEGIN
    SELECT *
    INTO evaluation
    FROM evaluate_merge_eligibility(p_pull_request_id);

    INSERT INTO merge_eligibility (
        pull_request_id,
        eligible,
        reason
    )
    VALUES (
        p_pull_request_id,
        evaluation.eligible,
        evaluation.reason
    )
    ON CONFLICT (pull_request_id)
    DO UPDATE SET
        eligible = EXCLUDED.eligible,
        reason = EXCLUDED.reason,
        evaluated_at = now();
END;
$$;

BEGIN;

INSERT INTO repositories (
    repository_name,
    owner_name
)
VALUES (
    'orders-platform',
    'platform-team'
);

INSERT INTO databases (
    repository_id,
    database_name,
    engine,
    engine_version,
    primary_region,
    state,
    storage_gb,
    compute_units,
    multi_az,
    backup_retention_days
)
SELECT
    repository_id,
    'orders-prod',
    'PostgreSQL',
    '18.1',
    'ap-south-1',
    'available',
    500,
    12,
    true,
    7
FROM repositories
WHERE repository_name = 'orders-platform';

INSERT INTO branches (
    database_id,
    branch_name,
    is_protected
)
SELECT database_id, 'main', true
FROM databases
WHERE database_name = 'orders-prod';

INSERT INTO branches (
    database_id,
    branch_name,
    is_protected
)
SELECT database_id, 'feature/backup-policy', false
FROM databases
WHERE database_name = 'orders-prod';

INSERT INTO commits (
    branch_id,
    commit_hash,
    message
)
SELECT
    branch_id,
    '1111111111111111111111111111111111111111',
    'Configure automated database backup policy'
FROM branches
WHERE branch_name = 'feature/backup-policy';

INSERT INTO commits (
    branch_id,
    commit_hash,
    message
)
SELECT
    branch_id,
    '2222222222222222222222222222222222222222',
    'Update production database configuration'
FROM branches
WHERE branch_name = 'main';

INSERT INTO pull_requests (
    database_id,
    source_branch_id,
    target_branch_id,
    title,
    status
)
SELECT
    d.database_id,
    source.branch_id,
    target.branch_id,
    'Automate managed database backup configuration',
    'open'
FROM databases d
JOIN branches source
  ON source.database_id = d.database_id
 AND source.branch_name = 'feature/backup-policy'
JOIN branches target
  ON target.database_id = d.database_id
 AND target.branch_name = 'main'
WHERE d.database_name = 'orders-prod';

INSERT INTO reviewers (
    reviewer_name,
    role_name
)
VALUES
    ('platform-lead', 'database-admin'),
    ('security-reviewer', 'security-engineer'),
    ('developer-one', 'developer');

INSERT INTO branch_protection_policies (
    branch_id,
    required_reviews,
    require_status_checks,
    require_conversations_resolved,
    allow_direct_push,
    allow_force_push,
    allow_branch_deletion,
    require_linear_history,
    allow_administrator_bypass
)
SELECT
    branch_id,
    2,
    true,
    true,
    false,
    false,
    false,
    true,
    false
FROM branches
WHERE branch_name = 'main';

INSERT INTO approval_requirements (
    policy_id,
    reviewer_role,
    minimum_count
)
SELECT
    policy_id,
    'database-admin',
    1
FROM branch_protection_policies
WHERE required_reviews = 2;

INSERT INTO approval_requirements (
    policy_id,
    reviewer_role,
    minimum_count
)
SELECT
    policy_id,
    'security-engineer',
    1
FROM branch_protection_policies
WHERE required_reviews = 2;

INSERT INTO backups (
    database_id,
    backup_type,
    lsn,
    size_gb,
    checksum
)
SELECT
    database_id,
    'snapshot',
    12000,
    325.50,
    'sha256-orders-prod-12000'
FROM databases
WHERE database_name = 'orders-prod';

INSERT INTO replicas (
    database_id,
    region,
    state,
    lag_seconds,
    replayed_lsn
)
SELECT
    database_id,
    'ap-southeast-1',
    'streaming',
    3,
    12000
FROM databases
WHERE database_name = 'orders-prod';

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    decision,
    stale,
    dismissed
)
SELECT
    pr.pull_request_id,
    r.reviewer_id,
    'pass',
    false,
    false
FROM pull_requests pr
JOIN reviewers r
  ON r.reviewer_name IN ('platform-lead', 'security-reviewer');

INSERT INTO review_comments (
    review_id,
    file_path,
    line_number,
    comment_text,
    resolved
)
SELECT
    review_id,
    'database/backup-policy.sql',
    42,
    'Backup retention rule verified against production policy.',
    true
FROM reviews
WHERE decision = 'pass';

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    passed
)
SELECT
    pull_request_id,
    'database-schema-validation',
    true
FROM pull_requests;

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    passed
)
SELECT
    pull_request_id,
    'backup-policy-validation',
    true
FROM pull_requests;

COMMIT;

-- Successful eligibility evaluation.
SELECT refresh_merge_eligibility(pull_request_id)
FROM pull_requests
WHERE title = 'Automate managed database backup configuration';

SELECT *
FROM merge_eligibility;

-- Demonstrate stale approval behavior.
UPDATE reviews
SET stale = true
WHERE reviewer_id = (
    SELECT reviewer_id
    FROM reviewers
    WHERE reviewer_name = 'platform-lead'
)
AND pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE title = 'Automate managed database backup configuration'
);

SELECT refresh_merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Automate managed database backup configuration'
    )
);

SELECT *
FROM merge_eligibility;

-- Restore the approval for the final operational state.
UPDATE reviews
SET stale = false
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE title = 'Automate managed database backup configuration'
)
AND reviewer_id = (
    SELECT reviewer_id
    FROM reviewers
    WHERE reviewer_name = 'platform-lead'
);

SELECT refresh_merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Automate managed database backup configuration'
    )
);

-- Demonstrate a failed database gate.
UPDATE replicas
SET state = 'lagging',
    lag_seconds = 180
WHERE region = 'ap-southeast-1';

SELECT refresh_merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Automate managed database backup configuration'
    )
);

SELECT *
FROM merge_eligibility;

-- Restore healthy replication.
UPDATE replicas
SET state = 'streaming',
    lag_seconds = 3,
    replayed_lsn = 12000
WHERE region = 'ap-southeast-1';

SELECT refresh_merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Automate managed database backup configuration'
    )
);

-- Operational reporting.
SELECT *
FROM database_health
ORDER BY database_name;

SELECT
    d.database_name,
    d.engine,
    d.engine_version,
    d.primary_region,
    d.state,
    d.storage_gb,
    d.compute_units,
    d.multi_az,
    COUNT(DISTINCT b.backup_id) AS backups,
    COUNT(DISTINCT r.replica_id) AS replicas
FROM databases d
LEFT JOIN backups b ON b.database_id = d.database_id
LEFT JOIN replicas r ON r.database_id = d.database_id
GROUP BY
    d.database_id,
    d.database_name,
    d.engine,
    d.engine_version,
    d.primary_region,
    d.state,
    d.storage_gb,
    d.compute_units,
    d.multi_az;

-- Find replicas whose lag exceeds the operational threshold.
SELECT
    d.database_name,
    r.region,
    r.state,
    r.lag_seconds
FROM replicas r
JOIN databases d ON d.database_id = r.database_id
WHERE r.lag_seconds > 60
ORDER BY r.lag_seconds DESC;

-- Approval reporting excludes stale and dismissed approvals.
SELECT
    pr.pull_request_id,
    pr.title,
    COUNT(*) FILTER (
        WHERE r.decision = 'pass'
          AND NOT r.stale
          AND NOT r.dismissed
    ) AS valid_approvals,
    COUNT(*) FILTER (
        WHERE r.decision = 'fail'
          OR r.stale
          OR r.dismissed
    ) AS invalid_or_rejected_reviews
FROM pull_requests pr
LEFT JOIN reviews r
    ON r.pull_request_id = pr.pull_request_id
GROUP BY pr.pull_request_id, pr.title;
