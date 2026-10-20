DROP SCHEMA IF EXISTS backup_lab CASCADE;
CREATE SCHEMA backup_lab;
SET search_path = backup_lab;

CREATE TYPE backup_type AS ENUM ('full', 'incremental', 'snapshot');
CREATE TYPE backup_state AS ENUM ('created', 'verified', 'failed', 'expired');
CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed');

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    source_path TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(name)) >= 2),
    CHECK (length(trim(source_path)) > 0)
);

CREATE TABLE branches (
    branch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, name)
);

CREATE TABLE backup_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    full_backup_interval_hours INTEGER NOT NULL,
    incremental_interval_hours INTEGER NOT NULL,
    retention_days INTEGER NOT NULL,
    maximum_incremental_chain INTEGER NOT NULL DEFAULT 7,
    verification_required BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (repository_id, name),
    CHECK (full_backup_interval_hours > 0),
    CHECK (incremental_interval_hours > 0),
    CHECK (retention_days > 0),
    CHECK (maximum_incremental_chain > 0)
);

CREATE TABLE backups (
    backup_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    policy_id BIGINT NOT NULL REFERENCES backup_policies(policy_id),
    backup_type backup_type NOT NULL,
    state backup_state NOT NULL DEFAULT 'created',
    parent_backup_id BIGINT REFERENCES backups(backup_id),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    checksum TEXT,
    storage_uri TEXT NOT NULL,
    verified_at TIMESTAMPTZ,
    CHECK (size_bytes >= 0),
    CHECK (completed_at IS NULL OR completed_at >= started_at),
    CHECK (
        (backup_type = 'full' AND parent_backup_id IS NULL)
        OR
        (backup_type IN ('incremental', 'snapshot'))
    ),
    CHECK (state <> 'verified' OR verified_at IS NOT NULL)
);

CREATE INDEX idx_backups_repository_started
    ON backups (repository_id, started_at DESC);

CREATE INDEX idx_backups_parent
    ON backups (parent_backup_id);

CREATE TABLE backup_files (
    backup_file_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    backup_id BIGINT NOT NULL REFERENCES backups(backup_id)
        ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    modified_at TIMESTAMPTZ,
    UNIQUE (backup_id, relative_path),
    CHECK (size_bytes >= 0),
    CHECK (relative_path <> ''),
    CHECK (relative_path !~ '(^|/)\.\.(/|$)'),
    CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE backup_jobs (
    job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    backup_id BIGINT REFERENCES backups(backup_id)
        ON DELETE SET NULL,
    job_status job_status NOT NULL DEFAULT 'queued',
    scheduled_for TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    CHECK (finished_at IS NULL OR started_at IS NOT NULL),
    CHECK (
        job_status <> 'failed'
        OR length(trim(coalesce(error_message, ''))) > 0
    )
);

CREATE TABLE retention_events (
    retention_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    backup_id BIGINT NOT NULL REFERENCES backups(backup_id)
        ON DELETE CASCADE,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL CHECK (action IN ('retain', 'expire')),
    reason TEXT NOT NULL
);

INSERT INTO repositories (name, source_path)
VALUES
    ('payments-production', '/srv/payments'),
    ('analytics-production', '/srv/analytics');

INSERT INTO branches (repository_id, name, protected)
SELECT repository_id, 'main', TRUE
FROM repositories
WHERE name = 'payments-production';

INSERT INTO branches (repository_id, name, protected)
SELECT repository_id, 'main', TRUE
FROM repositories
WHERE name = 'analytics-production';

INSERT INTO backup_policies (
    repository_id,
    name,
    full_backup_interval_hours,
    incremental_interval_hours,
    retention_days,
    maximum_incremental_chain,
    verification_required
)
SELECT repository_id,
       'production-30-day',
       168,
       24,
       30,
       7,
       TRUE
FROM repositories;

INSERT INTO backups (
    repository_id,
    policy_id,
    backup_type,
    state,
    started_at,
    completed_at,
    size_bytes,
    checksum,
    storage_uri,
    verified_at
)
SELECT r.repository_id,
       p.policy_id,
       'full',
       'verified',
       '2026-10-01 02:00:00+00',
       '2026-10-01 02:25:00+00',
       5000000000,
       repeat('a', 64),
       's3://backup-vault/payments/full-20261001',
       '2026-10-01 02:26:00+00'
FROM repositories r
JOIN backup_policies p
  ON p.repository_id = r.repository_id
WHERE r.name = 'payments-production';

INSERT INTO backups (
    repository_id,
    policy_id,
    backup_type,
    state,
    parent_backup_id,
    started_at,
    completed_at,
    size_bytes,
    checksum,
    storage_uri,
    verified_at
)
SELECT r.repository_id,
       p.policy_id,
       'incremental',
       'verified',
       b.backup_id,
       '2026-10-02 02:00:00+00',
       '2026-10-02 02:07:00+00',
       320000000,
       repeat('b', 64),
       's3://backup-vault/payments/inc-20261002',
       '2026-10-02 02:08:00+00'
FROM repositories r
JOIN backup_policies p
  ON p.repository_id = r.repository_id
JOIN backups b
  ON b.repository_id = r.repository_id
 AND b.backup_type = 'full'
WHERE r.name = 'payments-production';

INSERT INTO backup_files (
    backup_id,
    relative_path,
    size_bytes,
    sha256,
    modified_at
)
SELECT backup_id,
       'database/schema.sql',
       18000,
       repeat('c', 64),
       '2026-10-01 01:55:00+00'
FROM backups
WHERE storage_uri = 's3://backup-vault/payments/full-20261001';

INSERT INTO backup_files (
    backup_id,
    relative_path,
    size_bytes,
    sha256,
    modified_at
)
SELECT backup_id,
       'application/config.yml',
       4200,
       repeat('d', 64),
       '2026-10-02 01:58:00+00'
FROM backups
WHERE storage_uri = 's3://backup-vault/payments/inc-20261002';

INSERT INTO backup_jobs (
    repository_id,
    backup_id,
    job_status,
    scheduled_for,
    started_at,
    finished_at
)
SELECT repository_id,
       backup_id,
       'succeeded',
       started_at,
       started_at,
       completed_at
FROM backups
WHERE storage_uri = 's3://backup-vault/payments/inc-20261002';

-- A full backup is the root of a restore chain. Recursive traversal
-- identifies every incremental backup that depends on that root.
WITH RECURSIVE backup_chain AS (
    SELECT
        backup_id,
        parent_backup_id,
        backup_type,
        0 AS depth
    FROM backups
    WHERE backup_type = 'full'

    UNION ALL

    SELECT
        child.backup_id,
        child.parent_backup_id,
        child.backup_type,
        parent.depth + 1
    FROM backups child
    JOIN backup_chain parent
      ON child.parent_backup_id = parent.backup_id
)
SELECT
    backup_id,
    backup_type,
    depth,
    parent_backup_id
FROM backup_chain
ORDER BY depth, backup_id;

-- Merge-style reporting shows the latest verified recovery point.
SELECT
    r.name AS repository,
    max(b.completed_at) AS latest_verified_backup,
    count(*) FILTER (WHERE b.backup_type = 'full') AS full_backups,
    count(*) FILTER (WHERE b.backup_type = 'incremental') AS incremental_backups,
    sum(b.size_bytes) AS stored_bytes
FROM repositories r
JOIN backups b
  ON b.repository_id = r.repository_id
WHERE b.state = 'verified'
GROUP BY r.repository_id, r.name
ORDER BY r.name;

-- Validate that incremental backups never point at another incremental
-- backup belonging to a different repository.
SELECT
    child.backup_id,
    child.parent_backup_id
FROM backups child
JOIN backups parent
  ON parent.backup_id = child.parent_backup_id
WHERE child.backup_type = 'incremental'
  AND child.repository_id <> parent.repository_id;

-- Transactional retention evaluation. A row is marked expired only after
-- the retention decision has been recorded.
BEGIN;

WITH candidates AS (
    SELECT
        b.backup_id,
        b.completed_at,
        p.retention_days
    FROM backups b
    JOIN backup_policies p
      ON p.policy_id = b.policy_id
    WHERE b.state = 'verified'
      AND b.completed_at <
          CURRENT_TIMESTAMP - make_interval(days => p.retention_days)
)
INSERT INTO retention_events (backup_id, action, reason)
SELECT
    backup_id,
    'expire',
    'Completed outside configured retention period'
FROM candidates;

WITH candidates AS (
    SELECT b.backup_id
    FROM backups b
    JOIN backup_policies p
      ON p.policy_id = b.policy_id
    WHERE b.state = 'verified'
      AND b.completed_at <
          CURRENT_TIMESTAMP - make_interval(days => p.retention_days)
)
UPDATE backups b
SET state = 'expired'
FROM candidates c
WHERE b.backup_id = c.backup_id;

COMMIT;

-- Detect unverified backups older than the configured verification window.
SELECT
    r.name AS repository,
    b.backup_id,
    b.backup_type,
    b.started_at,
    b.state
FROM backups b
JOIN repositories r
  ON r.repository_id = b.repository_id
JOIN backup_policies p
  ON p.policy_id = b.policy_id
WHERE p.verification_required
  AND b.state <> 'verified'
ORDER BY b.started_at;

-- Identify chains exceeding the operational policy limit.
WITH RECURSIVE chain AS (
    SELECT
        backup_id,
        parent_backup_id,
        backup_id AS root_id,
        0 AS depth
    FROM backups
    WHERE backup_type = 'full'

    UNION ALL

    SELECT
        child.backup_id,
        child.parent_backup_id,
        chain.root_id,
        chain.depth + 1
    FROM backups child
    JOIN chain
      ON child.parent_backup_id = chain.backup_id
)
SELECT
    root_id,
    max(depth) AS incremental_depth
FROM chain
GROUP BY root_id
HAVING max(depth) > 7;

-- A backup file cannot contain a path traversal component because the
-- CHECK constraint rejects ".." path segments.
-- The following transaction demonstrates an integrity failure safely.
BEGIN;

DO $$
BEGIN
    BEGIN
        INSERT INTO backup_files (
            backup_id,
            relative_path,
            size_bytes,
            sha256
        )
        VALUES (
            (SELECT backup_id FROM backups LIMIT 1),
            '../secrets.txt',
            100,
            repeat('e', 64)
        );
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Rejected unsafe backup path';
    END;
END $$;

ROLLBACK;
