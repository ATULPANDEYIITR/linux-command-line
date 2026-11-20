/*
    DOCKER VOLUMES
    Persistent Storage and Data Management

    PostgreSQL 15+

    Relational model for:
    - Storage resources
    - Named volumes
    - Anonymous volumes
    - Bind mounts
    - Containers
    - Mount configurations
    - Storage files
    - Backup operations
    - Storage policies
    - Volume references
    - Lifecycle events
    - Storage reporting

    The database models Docker storage governance.
    It does not directly control the Docker daemon.
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS docker_storage;

SET search_path TO docker_storage, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE storage_type AS ENUM (
    'named',
    'anonymous',
    'bind'
);

CREATE TYPE container_state AS ENUM (
    'created',
    'running',
    'stopped',
    'removed'
);

CREATE TYPE mount_access AS ENUM (
    'read_write',
    'read_only'
);

CREATE TYPE backup_state AS ENUM (
    'pending',
    'completed',
    'failed'
);

CREATE TYPE storage_event_type AS ENUM (
    'volume_created',
    'volume_removed',
    'container_created',
    'container_started',
    'container_stopped',
    'container_removed',
    'mount_attached',
    'mount_detached',
    'file_written',
    'backup_created',
    'backup_failed'
);

-- ============================================================
-- 2. REPOSITORY-STYLE STORAGE OWNERSHIP
-- ============================================================

CREATE TABLE storage_owners (
    owner_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_name VARCHAR(120) NOT NULL UNIQUE,
    owner_email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE storage_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(120) NOT NULL UNIQUE,

    allow_read BOOLEAN NOT NULL DEFAULT TRUE,
    allow_write BOOLEAN NOT NULL DEFAULT TRUE,
    allow_delete BOOLEAN NOT NULL DEFAULT TRUE,

    maximum_bytes BIGINT CHECK (
        maximum_bytes IS NULL OR maximum_bytes >= 0
    ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. VOLUMES
-- ============================================================

CREATE TABLE volumes (
    volume_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    volume_name VARCHAR(128) NOT NULL UNIQUE,

    volume_type storage_type NOT NULL,

    host_path TEXT NOT NULL,

    owner_id BIGINT NOT NULL
        REFERENCES storage_owners(owner_id)
        ON DELETE RESTRICT,

    policy_id BIGINT NOT NULL
        REFERENCES storage_policies(policy_id)
        ON DELETE RESTRICT,

    labels JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    removed_at TIMESTAMPTZ,

    CHECK (
        volume_name ~ '^[a-zA-Z0-9_.-]{1,128}$'
    ),

    CHECK (
        host_path <> ''
    ),

    CHECK (
        jsonb_typeof(labels) = 'object'
    ),

    CHECK (
        removed_at IS NULL OR removed_at >= created_at
    ),

    UNIQUE (volume_id, volume_type)
);

CREATE INDEX idx_volumes_owner
ON volumes(owner_id);

CREATE INDEX idx_volumes_type
ON volumes(volume_type);

CREATE INDEX idx_volumes_active
ON volumes(created_at DESC)
WHERE removed_at IS NULL;

CREATE INDEX idx_volumes_labels
ON volumes USING GIN(labels);

-- ============================================================
-- 4. CONTAINERS
-- ============================================================

CREATE TABLE containers (
    container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_name VARCHAR(128) NOT NULL UNIQUE,

    image_name VARCHAR(255) NOT NULL,

    image_digest VARCHAR(255),

    state container_state NOT NULL DEFAULT 'created',

    owner_id BIGINT NOT NULL
        REFERENCES storage_owners(owner_id)
        ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    started_at TIMESTAMPTZ,

    stopped_at TIMESTAMPTZ,

    removed_at TIMESTAMPTZ,

    CHECK (
        container_name ~ '^[a-zA-Z0-9_.-]{1,128}$'
    ),

    CHECK (
        image_name <> ''
    ),

    CHECK (
        started_at IS NULL OR started_at >= created_at
    ),

    CHECK (
        stopped_at IS NULL OR stopped_at >= created_at
    )
);

CREATE INDEX idx_containers_state
ON containers(state);

CREATE INDEX idx_containers_owner
ON containers(owner_id);

-- ============================================================
-- 5. MOUNT CONFIGURATIONS
-- ============================================================

CREATE TABLE container_mounts (
    mount_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES containers(container_id)
        ON DELETE RESTRICT,

    volume_id BIGINT NOT NULL,

    volume_type storage_type NOT NULL,

    container_target TEXT NOT NULL,

    access_mode mount_access NOT NULL DEFAULT 'read_write',

    attached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    detached_at TIMESTAMPTZ,

    FOREIGN KEY (volume_id, volume_type)
        REFERENCES volumes(volume_id, volume_type)
        ON DELETE RESTRICT,

    CHECK (
        container_target LIKE '/%'
    ),

    CHECK (
        container_target NOT LIKE '%/../%'
    ),

    CHECK (
        detached_at IS NULL OR detached_at >= attached_at
    )
);

CREATE UNIQUE INDEX uq_active_container_mount_target
ON container_mounts(container_id, container_target)
WHERE detached_at IS NULL;

CREATE INDEX idx_mounts_volume_active
ON container_mounts(volume_id)
WHERE detached_at IS NULL;

CREATE INDEX idx_mounts_container
ON container_mounts(container_id);

-- ============================================================
-- 6. STORAGE FILE INVENTORY
-- ============================================================

CREATE TABLE storage_files (
    file_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    volume_id BIGINT NOT NULL
        REFERENCES volumes(volume_id)
        ON DELETE RESTRICT,

    relative_path TEXT NOT NULL,

    file_size_bytes BIGINT NOT NULL DEFAULT 0,

    checksum_sha256 VARCHAR(64),

    is_directory BOOLEAN NOT NULL DEFAULT FALSE,

    modified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        relative_path <> ''
        AND relative_path NOT LIKE '/%'
        AND relative_path <> '..'
        AND relative_path NOT LIKE '../%'
        AND relative_path NOT LIKE '%/../%'
        AND relative_path NOT LIKE '%/..'
    ),

    CHECK (
        file_size_bytes >= 0
    ),

    CHECK (
        checksum_sha256 IS NULL
        OR checksum_sha256 ~ '^[a-fA-F0-9]{64}$'
    ),

    UNIQUE (volume_id, relative_path)
);

CREATE INDEX idx_storage_files_volume
ON storage_files(volume_id);

CREATE INDEX idx_storage_files_modified
ON storage_files(modified_at DESC);

-- ============================================================
-- 7. BACKUPS
-- ============================================================

CREATE TABLE volume_backups (
    backup_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    volume_id BIGINT NOT NULL
        REFERENCES volumes(volume_id)
        ON DELETE RESTRICT,

    backup_name VARCHAR(255) NOT NULL UNIQUE,

    backup_location TEXT NOT NULL,

    backup_state backup_state NOT NULL DEFAULT 'pending',

    total_bytes BIGINT NOT NULL DEFAULT 0,

    checksum_sha256 VARCHAR(64),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CHECK (total_bytes >= 0),

    CHECK (
        checksum_sha256 IS NULL
        OR checksum_sha256 ~ '^[a-fA-F0-9]{64}$'
    ),

    CHECK (
        backup_state <> 'completed'
        OR completed_at IS NOT NULL
    )
);

CREATE INDEX idx_backups_volume
ON volume_backups(volume_id, created_at DESC);

CREATE INDEX idx_backups_state
ON volume_backups(backup_state);

-- ============================================================
-- 8. STORAGE AUDIT LOG
-- ============================================================

CREATE TABLE storage_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    event_type storage_event_type NOT NULL,

    volume_id BIGINT
        REFERENCES volumes(volume_id)
        ON DELETE RESTRICT,

    container_id BIGINT
        REFERENCES containers(container_id)
        ON DELETE RESTRICT,

    actor_id BIGINT
        REFERENCES storage_owners(owner_id)
        ON DELETE RESTRICT,

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        jsonb_typeof(event_details) = 'object'
    )
);

CREATE INDEX idx_storage_events_time
ON storage_events(occurred_at DESC);

CREATE INDEX idx_storage_events_volume
ON storage_events(volume_id, occurred_at DESC);

-- ============================================================
-- 9. POLICY ENFORCEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION validate_mount_policy()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_removed_at TIMESTAMPTZ;
    v_allow_write BOOLEAN;
    v_allow_read BOOLEAN;
    v_volume_type storage_type;
BEGIN
    SELECT
        v.removed_at,
        v.volume_type,
        p.allow_read,
        p.allow_write
    INTO
        v_removed_at,
        v_volume_type,
        v_allow_read,
        v_allow_write
    FROM volumes v
    JOIN storage_policies p
        ON p.policy_id = v.policy_id
    WHERE v.volume_id = NEW.volume_id
    FOR UPDATE OF v;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Storage resource does not exist';
    END IF;

    IF v_removed_at IS NOT NULL THEN
        RAISE EXCEPTION 'Removed storage cannot be mounted';
    END IF;

    IF NEW.volume_type <> v_volume_type THEN
        RAISE EXCEPTION 'Mount type mismatch';
    END IF;

    IF NEW.access_mode = 'read_write' AND NOT v_allow_write THEN
        RAISE EXCEPTION 'Storage policy prohibits writes';
    END IF;

    IF NEW.access_mode = 'read_only' AND NOT v_allow_read THEN
        RAISE EXCEPTION 'Storage policy prohibits reads';
    END IF;

    IF NEW.container_target !~ '^/' THEN
        RAISE EXCEPTION 'Mount destination must be absolute';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_mount_policy
BEFORE INSERT ON container_mounts
FOR EACH ROW
EXECUTE FUNCTION validate_mount_policy();

-- ============================================================
-- 10. CONTAINER STATE VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_container_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'removed' THEN
        RAISE EXCEPTION 'Removed containers cannot be modified';
    END IF;

    IF NEW.state = 'running' AND OLD.state = 'removed' THEN
        RAISE EXCEPTION 'Removed container cannot restart';
    END IF;

    IF NEW.state = 'removed' AND EXISTS (
        SELECT 1
        FROM container_mounts
        WHERE container_id = OLD.container_id
          AND detached_at IS NULL
    ) THEN
        RAISE EXCEPTION
            'Detach active mounts before removing a container';
    END IF;

    IF NEW.state = 'running' THEN
        NEW.started_at = COALESCE(NEW.started_at, NOW());
        NEW.stopped_at = NULL;
        NEW.removed_at = NULL;
    ELSIF NEW.state = 'stopped' THEN
        NEW.stopped_at = NOW();
    ELSIF NEW.state = 'removed' THEN
        NEW.removed_at = NOW();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_state
BEFORE UPDATE OF state ON containers
FOR EACH ROW
WHEN (OLD.state IS DISTINCT FROM NEW.state)
EXECUTE FUNCTION validate_container_state();

-- ============================================================
-- 11. EVENT GENERATION
-- ============================================================

CREATE OR REPLACE FUNCTION record_mount_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_event storage_event_type;
    v_container_id BIGINT;
    v_volume_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_event := 'mount_attached';
        v_container_id := NEW.container_id;
        v_volume_id := NEW.volume_id;
    ELSE
        v_event := 'mount_detached';
        v_container_id := OLD.container_id;
        v_volume_id := OLD.volume_id;
    END IF;

    INSERT INTO storage_events (
        event_type,
        volume_id,
        container_id,
        event_details
    )
    VALUES (
        v_event,
        v_volume_id,
        v_container_id,
        jsonb_build_object(
            'operation', TG_OP,
            'target',
            CASE
                WHEN TG_OP = 'INSERT' THEN NEW.container_target
                ELSE OLD.container_target
            END
        )
    );

    RETURN CASE
        WHEN TG_OP = 'DELETE' THEN OLD
        ELSE NEW
    END;
END;
$$;

CREATE TRIGGER trg_mount_event
AFTER INSERT OR DELETE ON container_mounts
FOR EACH ROW
EXECUTE FUNCTION record_mount_event();

-- ============================================================
-- 12. VOLUME LIFECYCLE PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE detach_container_mounts(
    p_container_id BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE container_mounts
    SET detached_at = NOW()
    WHERE container_id = p_container_id
      AND detached_at IS NULL;

    UPDATE containers
    SET state = 'removed'
    WHERE container_id = p_container_id
      AND state <> 'removed';
END;
$$;

-- ============================================================
-- 13. VOLUME INSPECTION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION inspect_volume(
    p_volume_id BIGINT
)
RETURNS TABLE (
    volume_name VARCHAR,
    volume_type storage_type,
    owner_name VARCHAR,
    active_mount_count BIGINT,
    total_file_bytes NUMERIC,
    storage_path TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        v.volume_name,
        v.volume_type,
        o.owner_name,
        COUNT(DISTINCT cm.mount_id),
        COALESCE(SUM(sf.file_size_bytes), 0),
        v.host_path
    FROM volumes v
    JOIN storage_owners o
        ON o.owner_id = v.owner_id
    LEFT JOIN container_mounts cm
        ON cm.volume_id = v.volume_id
       AND cm.detached_at IS NULL
    LEFT JOIN storage_files sf
        ON sf.volume_id = v.volume_id
    WHERE v.volume_id = p_volume_id
    GROUP BY
        v.volume_id,
        v.volume_name,
        v.volume_type,
        o.owner_name,
        v.host_path;
$$;

-- ============================================================
-- 14. MERGE ELIGIBILITY / STORAGE MOUNT ELIGIBILITY
-- ============================================================

CREATE OR REPLACE FUNCTION check_mount_eligibility(
    p_volume_id BIGINT,
    p_container_id BIGINT,
    p_target TEXT,
    p_access mount_access
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_removed_at TIMESTAMPTZ;
    v_state container_state;
    v_allow_write BOOLEAN;
    v_allow_read BOOLEAN;
BEGIN
    SELECT
        v.removed_at,
        p.allow_write,
        p.allow_read
    INTO
        v_removed_at,
        v_allow_write,
        v_allow_read
    FROM volumes v
    JOIN storage_policies p
        ON p.policy_id = v.policy_id
    WHERE v.volume_id = p_volume_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Volume not found';
        RETURN;
    END IF;

    IF v_removed_at IS NOT NULL THEN
        RETURN QUERY SELECT FALSE, 'Volume has been removed';
        RETURN;
    END IF;

    SELECT state
    INTO v_state
    FROM containers
    WHERE container_id = p_container_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Container not found';
        RETURN;
    END IF;

    IF v_state = 'removed' THEN
        RETURN QUERY SELECT FALSE, 'Container has been removed';
        RETURN;
    END IF;

    IF p_access = 'read_write' AND NOT v_allow_write THEN
        RETURN QUERY SELECT FALSE, 'Write policy denied';
        RETURN;
    END IF;

    IF p_access = 'read_only' AND NOT v_allow_read THEN
        RETURN QUERY SELECT FALSE, 'Read policy denied';
        RETURN;
    END IF;

    IF p_target !~ '^/' OR p_target LIKE '%/../%' THEN
        RETURN QUERY SELECT FALSE, 'Invalid mount target';
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM container_mounts cm
        WHERE cm.container_id = p_container_id
          AND cm.container_target = p_target
          AND cm.detached_at IS NULL
    ) THEN
        RETURN QUERY SELECT FALSE, 'Mount target already occupied';
        RETURN;
    END IF;

    RETURN QUERY SELECT TRUE, 'Mount is eligible';
END;
$$;

-- ============================================================
-- 15. REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW active_storage_inventory AS
SELECT
    v.volume_id,
    v.volume_name,
    v.volume_type,
    o.owner_name,
    p.policy_name,
    COUNT(DISTINCT cm.container_id) AS attached_containers,
    COUNT(DISTINCT sf.file_id) AS tracked_files,
    COALESCE(SUM(sf.file_size_bytes), 0) AS total_bytes,
    v.created_at
FROM volumes v
JOIN storage_owners o
    ON o.owner_id = v.owner_id
JOIN storage_policies p
    ON p.policy_id = v.policy_id
LEFT JOIN container_mounts cm
    ON cm.volume_id = v.volume_id
   AND cm.detached_at IS NULL
LEFT JOIN storage_files sf
    ON sf.volume_id = v.volume_id
WHERE v.removed_at IS NULL
GROUP BY
    v.volume_id,
    v.volume_name,
    v.volume_type,
    o.owner_name,
    p.policy_name,
    v.created_at;

-- ============================================================
-- 16. SAMPLE OWNERS AND POLICIES
-- ============================================================

INSERT INTO storage_owners (
    owner_name,
    owner_email
)
VALUES
    ('Platform Engineering', 'platform@example.com'),
    ('Database Operations', 'database@example.com'),
    ('Application Team', 'application@example.com');

INSERT INTO storage_policies (
    policy_name,
    allow_read,
    allow_write,
    allow_delete,
    maximum_bytes
)
VALUES
    ('standard_storage', TRUE, TRUE, TRUE, 10737418240),
    ('read_only_storage', TRUE, FALSE, FALSE, 1073741824),
    ('restricted_storage', TRUE, TRUE, FALSE, 5368709120);

-- ============================================================
-- 17. SAMPLE VOLUMES
-- ============================================================

INSERT INTO volumes (
    volume_name,
    volume_type,
    host_path,
    owner_id,
    policy_id,
    labels
)
SELECT
    'postgres_data',
    'named',
    '/var/lib/docker/volumes/postgres_data/_data',
    o.owner_id,
    p.policy_id,
    '{"environment":"development","service":"postgres"}'
FROM storage_owners o
CROSS JOIN storage_policies p
WHERE o.owner_name = 'Database Operations'
  AND p.policy_name = 'standard_storage';

INSERT INTO volumes (
    volume_name,
    volume_type,
    host_path,
    owner_id,
    policy_id,
    labels
)
SELECT
    'application_config',
    'bind',
    '/srv/application/config',
    o.owner_id,
    p.policy_id,
    '{"environment":"production","purpose":"configuration"}'
FROM storage_owners o
CROSS JOIN storage_policies p
WHERE o.owner_name = 'Application Team'
  AND p.policy_name = 'read_only_storage';

INSERT INTO volumes (
    volume_name,
    volume_type,
    host_path,
    owner_id,
    policy_id,
    labels
)
SELECT
    'temporary_cache',
    'anonymous',
    '/var/lib/docker/volumes/anonymous_cache/_data',
    o.owner_id,
    p.policy_id,
    '{"purpose":"cache"}'
FROM storage_owners o
CROSS JOIN storage_policies p
WHERE o.owner_name = 'Platform Engineering'
  AND p.policy_name = 'standard_storage';

-- ============================================================
-- 18. SAMPLE CONTAINERS
-- ============================================================

INSERT INTO containers (
    container_name,
    image_name,
    image_digest,
    state,
    owner_id
)
SELECT
    'postgres',
    'postgres:17',
    'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'running',
    owner_id
FROM storage_owners
WHERE owner_name = 'Database Operations';

INSERT INTO containers (
    container_name,
    image_name,
    state,
    owner_id
)
SELECT
    'application',
    'nginx:stable',
    'running',
    owner_id
FROM storage_owners
WHERE owner_name = 'Application Team';

INSERT INTO containers (
    container_name,
    image_name,
    state,
    owner_id
)
SELECT
    'cache-worker',
    'redis:7',
    'stopped',
    owner_id
FROM storage_owners
WHERE owner_name = 'Platform Engineering';

-- ============================================================
-- 19. SAMPLE MOUNTS
-- ============================================================

INSERT INTO container_mounts (
    container_id,
    volume_id,
    volume_type,
    container_target,
    access_mode
)
SELECT
    c.container_id,
    v.volume_id,
    v.volume_type,
    '/var/lib/postgresql/data',
    'read_write'
FROM containers c
CROSS JOIN volumes v
WHERE c.container_name = 'postgres'
  AND v.volume_name = 'postgres_data';

INSERT INTO container_mounts (
    container_id,
    volume_id,
    volume_type,
    container_target,
    access_mode
)
SELECT
    c.container_id,
    v.volume_id,
    v.volume_type,
    '/etc/application',
    'read_only'
FROM containers c
CROSS JOIN volumes v
WHERE c.container_name = 'application'
  AND v.volume_name = 'application_config';

INSERT INTO container_mounts (
    container_id,
    volume_id,
    volume_type,
    container_target,
    access_mode
)
SELECT
    c.container_id,
    v.volume_id,
    v.volume_type,
    '/data',
    'read_write'
FROM containers c
CROSS JOIN volumes v
WHERE c.container_name = 'cache-worker'
  AND v.volume_name = 'temporary_cache';

-- ============================================================
-- 20. SAMPLE FILE INVENTORY
-- ============================================================

INSERT INTO storage_files (
    volume_id,
    relative_path,
    file_size_bytes,
    checksum_sha256
)
SELECT
    volume_id,
    'base/database.dat',
    1048576,
    repeat('a', 64)
FROM volumes
WHERE volume_name = 'postgres_data';

INSERT INTO storage_files (
    volume_id,
    relative_path,
    file_size_bytes
)
SELECT
    volume_id,
    'global/pg_control',
    8192
FROM volumes
WHERE volume_name = 'postgres_data';

INSERT INTO storage_files (
    volume_id,
    relative_path,
    file_size_bytes
)
SELECT
    volume_id,
    'application.conf',
    4096
FROM volumes
WHERE volume_name = 'application_config';

INSERT INTO storage_files (
    volume_id,
    relative_path,
    file_size_bytes
)
SELECT
    volume_id,
    'cache/index.dat',
    2048
FROM volumes
WHERE volume_name = 'temporary_cache';

-- ============================================================
-- 21. SAMPLE BACKUP
-- ============================================================

INSERT INTO volume_backups (
    volume_id,
    backup_name,
    backup_location,
    backup_state,
    total_bytes,
    checksum_sha256,
    completed_at
)
SELECT
    volume_id,
    'postgres_backup_001',
    '/backups/postgres_backup_001.tar',
    'completed',
    1056768,
    repeat('b', 64),
    NOW()
FROM volumes
WHERE volume_name = 'postgres_data';

-- ============================================================
-- 22. STORAGE EVENT RECORDS
-- ============================================================

INSERT INTO storage_events (
    event_type,
    volume_id,
    container_id,
    event_details
)
SELECT
    'volume_created',
    volume_id,
    NULL,
    '{"source":"initialization"}'
FROM volumes;

INSERT INTO storage_events (
    event_type,
    volume_id,
    container_id,
    event_details
)
SELECT
    'container_started',
    v.volume_id,
    c.container_id,
    '{"service":"postgres","status":"healthy"}'
FROM volumes v
JOIN container_mounts cm
    ON cm.volume_id = v.volume_id
JOIN containers c
    ON c.container_id = cm.container_id
WHERE c.container_name = 'postgres';

-- ============================================================
-- 23. RETRIEVAL QUERIES
-- ============================================================

-- All managed volumes and their current policies.
SELECT *
FROM active_storage_inventory
ORDER BY volume_name;

-- Container mount configuration.
SELECT
    c.container_name,
    c.state,
    v.volume_name,
    v.volume_type,
    cm.container_target,
    cm.access_mode
FROM containers c
JOIN container_mounts cm
    ON cm.container_id = c.container_id
JOIN volumes v
    ON v.volume_id = cm.volume_id
WHERE cm.detached_at IS NULL
ORDER BY c.container_name;

-- ============================================================
-- 24. VALIDATION QUERIES
-- ============================================================

-- Volumes with no active container references.
SELECT
    v.volume_name,
    v.volume_type,
    v.created_at
FROM volumes v
WHERE v.removed_at IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM container_mounts cm
      WHERE cm.volume_id = v.volume_id
        AND cm.detached_at IS NULL
  );

-- Active containers without storage mounts.
SELECT
    c.container_name,
    c.state
FROM containers c
WHERE c.state IN ('created', 'running', 'stopped')
  AND NOT EXISTS (
      SELECT 1
      FROM container_mounts cm
      WHERE cm.container_id = c.container_id
        AND cm.detached_at IS NULL
  );

-- Verify volume size against policy limits.
SELECT
    v.volume_name,
    p.maximum_bytes,
    COALESCE(SUM(sf.file_size_bytes), 0) AS tracked_bytes,
    COALESCE(SUM(sf.file_size_bytes), 0) <= p.maximum_bytes
        AS within_limit
FROM volumes v
JOIN storage_policies p
    ON p.policy_id = v.policy_id
LEFT JOIN storage_files sf
    ON sf.volume_id = v.volume_id
GROUP BY v.volume_id, v.volume_name, p.maximum_bytes;

-- ============================================================
-- 25. AGGREGATION AND REPORTING
-- ============================================================

-- Total tracked storage by storage type.
SELECT
    v.volume_type,
    COUNT(DISTINCT v.volume_id) AS volume_count,
    COALESCE(SUM(sf.file_size_bytes), 0) AS total_bytes
FROM volumes v
LEFT JOIN storage_files sf
    ON sf.volume_id = v.volume_id
GROUP BY v.volume_type
ORDER BY v.volume_type;

-- Storage consumption by owner.
SELECT
    o.owner_name,
    COUNT(DISTINCT v.volume_id) AS volume_count,
    COALESCE(SUM(sf.file_size_bytes), 0) AS total_bytes
FROM storage_owners o
LEFT JOIN volumes v
    ON v.owner_id = o.owner_id
   AND v.removed_at IS NULL
LEFT JOIN storage_files sf
    ON sf.volume_id = v.volume_id
GROUP BY o.owner_id, o.owner_name
ORDER BY total_bytes DESC;

-- Backup health.
SELECT
    v.volume_name,
    COUNT(b.backup_id) AS backup_count,
    COUNT(*) FILTER (
        WHERE b.backup_state = 'completed'
    ) AS successful_backups,
    COUNT(*) FILTER (
        WHERE b.backup_state = 'failed'
    ) AS failed_backups
FROM volumes v
LEFT JOIN volume_backups b
    ON b.volume_id = v.volume_id
GROUP BY v.volume_id, v.volume_name;

-- ============================================================
-- 26. ELIGIBILITY EVALUATION
-- ============================================================

SELECT *
FROM check_mount_eligibility(
    (SELECT volume_id FROM volumes WHERE volume_name = 'postgres_data'),
    (SELECT container_id FROM containers WHERE container_name = 'postgres'),
    '/var/lib/postgresql/new-data',
    'read_write'
);

-- Expected denial: write access to read-only storage.
SELECT *
FROM check_mount_eligibility(
    (SELECT volume_id FROM volumes WHERE volume_name = 'application_config'),
    (SELECT container_id FROM containers WHERE container_name = 'application'),
    '/etc/application/extra',
    'read_write'
);

-- ============================================================
-- 27. VOLUME INSPECTION
-- ============================================================

SELECT *
FROM inspect_volume(
    (SELECT volume_id FROM volumes WHERE volume_name = 'postgres_data')
);

-- ============================================================
-- 28. TRANSACTIONAL WORKFLOW
-- ============================================================

-- Stop, detach and remove a container as one database transaction.
-- This updates the governance model, not the actual Docker daemon.

SAVEPOINT before_container_cleanup;

UPDATE containers
SET state = 'stopped'
WHERE container_name = 'cache-worker'
  AND state = 'running';

CALL detach_container_mounts(
    (SELECT container_id
     FROM containers
     WHERE container_name = 'cache-worker')
);

-- Validate the resulting state.
SELECT
    container_name,
    state,
    removed_at
FROM containers
WHERE container_name = 'cache-worker';

COMMIT;

-- ============================================================
-- 29. FAILURE CASE: DUPLICATE MOUNT DESTINATION
-- ============================================================

-- The following statement is intentionally commented out.
-- Uncomment separately to observe the unique constraint failure.
--
-- INSERT INTO container_mounts (
--     container_id,
--     volume_id,
--     volume_type,
--     container_target,
--     access_mode
-- )
-- SELECT
--     c.container_id,
--     v.volume_id,
--     v.volume_type,
--     '/var/lib/postgresql/data',
--     'read_write'
-- FROM containers c
-- CROSS JOIN volumes v
-- WHERE c.container_name = 'postgres'
--   AND v.volume_name = 'postgres_data';

-- ============================================================
-- 30. FAILURE CASE: WRITE TO READ-ONLY STORAGE
-- ============================================================

-- The trigger rejects this operation.
-- Execute independently to observe the policy violation.
--
-- INSERT INTO container_mounts (
--     container_id,
--     volume_id,
--     volume_type,
--     container_target,
--     access_mode
-- )
-- SELECT
--     c.container_id,
--     v.volume_id,
--     v.volume_type,
--     '/readonly-test',
--     'read_write'
-- FROM containers c
-- CROSS JOIN volumes v
-- WHERE c.container_name = 'application'
--   AND v.volume_name = 'application_config';

-- ============================================================
-- 31. FINAL STORAGE AUDIT
-- ============================================================

SELECT
    event_type,
    occurred_at,
    event_details
FROM storage_events
ORDER BY occurred_at DESC, event_id DESC;

SELECT
    volume_name,
    volume_type,
    attached_containers,
    tracked_files,
    total_bytes
FROM active_storage_inventory
ORDER BY total_bytes DESC;

COMMIT;
