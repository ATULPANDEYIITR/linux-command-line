-- PostgreSQL 15+
-- Compute and storage architecture: virtual servers, load balancing,
-- object versioning, backup manifests, policy evaluation, and merge-free
-- deployment eligibility. Run in a disposable database with permission
-- to create the architecture_lab schema.

BEGIN;

DROP SCHEMA IF EXISTS architecture_lab CASCADE;
CREATE SCHEMA architecture_lab;
SET search_path TO architecture_lab, public;

CREATE TYPE instance_state AS ENUM ('running', 'stopped', 'unhealthy');
CREATE TYPE object_state AS ENUM ('active', 'deleted');
CREATE TYPE backup_state AS ENUM ('completed', 'failed');
CREATE TYPE request_state AS ENUM ('accepted', 'served', 'failed');

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(repository_name)) > 0),
    CHECK (length(trim(region)) > 0)
);

CREATE TABLE availability_zones (
    zone_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories ON DELETE CASCADE,
    zone_name TEXT NOT NULL,
    region TEXT NOT NULL,
    UNIQUE (repository_id, zone_name)
);

CREATE TABLE compute_instances (
    instance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories ON DELETE CASCADE,
    zone_id BIGINT NOT NULL REFERENCES availability_zones,
    instance_name TEXT NOT NULL,
    state instance_state NOT NULL DEFAULT 'running',
    capacity_per_second INTEGER NOT NULL,
    active_requests INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, instance_name),
    CHECK (capacity_per_second > 0),
    CHECK (active_requests >= 0),
    CHECK (active_requests <= capacity_per_second)
);

CREATE INDEX compute_routing_idx
    ON compute_instances(repository_id, state, active_requests)
    WHERE state = 'running';

CREATE TABLE storage_buckets (
    bucket_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories ON DELETE CASCADE,
    bucket_name TEXT NOT NULL,
    versioning_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    max_object_bytes BIGINT NOT NULL DEFAULT 10000000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, bucket_name),
    CHECK (max_object_bytes > 0)
);

CREATE TABLE stored_objects (
    object_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES storage_buckets ON DELETE CASCADE,
    object_key TEXT NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    content BYTEA NOT NULL,
    content_sha256 TEXT NOT NULL,
    state object_state NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (bucket_id, object_key),
    CHECK (current_version > 0),
    CHECK (object_key <> ''),
    CHECK (left(object_key, 1) <> '/'),
    CHECK (object_key !~ '(^|/)\.\.(/|$)'),
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE object_versions (
    version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    object_id BIGINT NOT NULL REFERENCES stored_objects ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content BYTEA NOT NULL,
    content_sha256 TEXT NOT NULL,
    state object_state NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (object_id, version_number),
    CHECK (version_number > 0),
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE INDEX object_versions_history_idx
    ON object_versions(object_id, version_number DESC);

CREATE TABLE backups (
    backup_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES storage_buckets ON DELETE CASCADE,
    state backup_state NOT NULL DEFAULT 'failed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    manifest_sha256 TEXT,
    object_count INTEGER NOT NULL DEFAULT 0,
    CHECK (object_count >= 0),
    CHECK (
        (state = 'completed' AND completed_at IS NOT NULL
            AND manifest_sha256 ~ '^[0-9a-f]{64}$')
        OR
        (state = 'failed' AND completed_at IS NULL)
    )
);

CREATE TABLE backup_items (
    backup_id BIGINT NOT NULL REFERENCES backups ON DELETE CASCADE,
    object_key TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    content BYTEA NOT NULL,
    content_sha256 TEXT NOT NULL,
    PRIMARY KEY (backup_id, object_key),
    CHECK (version_number > 0),
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE load_balancer_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories ON DELETE CASCADE,
    instance_id BIGINT REFERENCES compute_instances ON DELETE SET NULL,
    request_key UUID NOT NULL UNIQUE,
    state request_state NOT NULL DEFAULT 'accepted',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    failure_reason TEXT,
    CHECK (
        (state = 'served' AND completed_at IS NOT NULL AND failure_reason IS NULL)
        OR state <> 'served'
    )
);

CREATE INDEX request_reporting_idx
    ON load_balancer_requests(repository_id, started_at DESC, state);

CREATE TABLE architecture_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories ON DELETE CASCADE,
    minimum_zones INTEGER NOT NULL DEFAULT 2,
    minimum_running_instances INTEGER NOT NULL DEFAULT 1,
    require_backup BOOLEAN NOT NULL DEFAULT TRUE,
    maximum_object_bytes BIGINT NOT NULL DEFAULT 10000000,
    UNIQUE (repository_id),
    CHECK (minimum_zones >= 1),
    CHECK (minimum_running_instances >= 1),
    CHECK (maximum_object_bytes > 0)
);

CREATE TABLE policy_evaluations (
    evaluation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories ON DELETE CASCADE,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    eligible BOOLEAN NOT NULL,
    violations JSONB NOT NULL DEFAULT '[]'::jsonb,
    CHECK (jsonb_typeof(violations) = 'array')
);

-- Object content and its checksum are validated by the database.
CREATE OR REPLACE FUNCTION validate_object_content()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    allowed_bytes BIGINT;
BEGIN
    SELECT b.max_object_bytes
      INTO allowed_bytes
      FROM storage_buckets b
     WHERE b.bucket_id = NEW.bucket_id
     FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Storage bucket % does not exist', NEW.bucket_id;
    END IF;

    IF octet_length(NEW.content) > allowed_bytes THEN
        RAISE EXCEPTION 'Object exceeds bucket size limit of % bytes', allowed_bytes;
    END IF;

    IF encode(digest(NEW.content, 'sha256'), 'hex') <> NEW.content_sha256 THEN
        RAISE EXCEPTION 'Object checksum does not match its content';
    END IF;

    RETURN NEW;
END;
$$;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TRIGGER validate_stored_object_content
BEFORE INSERT OR UPDATE OF content, content_sha256, bucket_id
ON stored_objects
FOR EACH ROW EXECUTE FUNCTION validate_object_content();

CREATE TRIGGER validate_version_content
BEFORE INSERT OR UPDATE OF content, content_sha256
ON object_versions
FOR EACH ROW
EXECUTE FUNCTION validate_version_content();

-- The version table is the historical record. Updates create a new version
-- rather than overwriting a previous version's bytes.
CREATE OR REPLACE FUNCTION validate_version_content()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    max_bytes BIGINT;
BEGIN
    SELECT b.max_object_bytes
      INTO max_bytes
      FROM stored_objects o
      JOIN storage_buckets b ON b.bucket_id = o.bucket_id
     WHERE o.object_id = NEW.object_id
     FOR SHARE OF b;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Object % does not exist', NEW.object_id;
    END IF;

    IF octet_length(NEW.content) > max_bytes THEN
        RAISE EXCEPTION 'Version exceeds bucket size limit';
    END IF;

    IF encode(digest(NEW.content, 'sha256'), 'hex') <> NEW.content_sha256 THEN
        RAISE EXCEPTION 'Version checksum does not match content';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION record_object_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO object_versions (
            object_id, version_number, content, content_sha256, state
        )
        VALUES (
            NEW.object_id, NEW.current_version, NEW.content,
            NEW.content_sha256, NEW.state
        );
        RETURN NEW;
    END IF;

    IF NEW.bucket_id <> OLD.bucket_id OR NEW.object_key <> OLD.object_key THEN
        RAISE EXCEPTION 'Object identity cannot be changed';
    END IF;

    IF NEW.current_version <> OLD.current_version + 1
       AND (
           NEW.content IS DISTINCT FROM OLD.content
           OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
       ) THEN
        RAISE EXCEPTION 'Content changes must increment the version by one';
    END IF;

    IF NEW.current_version = OLD.current_version + 1 THEN
        INSERT INTO object_versions (
            object_id, version_number, content, content_sha256, state
        )
        VALUES (
            NEW.object_id, NEW.current_version, NEW.content,
            NEW.content_sha256, NEW.state
        );
    ELSIF NEW.state IS DISTINCT FROM OLD.state THEN
        UPDATE object_versions
           SET state = NEW.state
         WHERE object_id = OLD.object_id
           AND version_number = OLD.current_version;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER maintain_object_history
AFTER INSERT OR UPDATE ON stored_objects
FOR EACH ROW EXECUTE FUNCTION record_object_version();

-- Select one eligible instance using least normalized utilization.
-- Row locking serializes competing reservations for the selected instance.
CREATE OR REPLACE FUNCTION reserve_compute_instance(p_repository_id BIGINT)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_id BIGINT;
BEGIN
    SELECT instance_id
      INTO selected_id
      FROM compute_instances
     WHERE repository_id = p_repository_id
       AND state = 'running'
       AND active_requests < capacity_per_second
     ORDER BY active_requests::NUMERIC / capacity_per_second,
              instance_id
     FOR UPDATE SKIP LOCKED
     LIMIT 1;

    IF selected_id IS NULL THEN
        RAISE EXCEPTION 'No healthy compute capacity is available';
    END IF;

    UPDATE compute_instances
       SET active_requests = active_requests + 1
     WHERE instance_id = selected_id;

    RETURN selected_id;
END;
$$;

CREATE OR REPLACE FUNCTION release_compute_instance(p_instance_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE compute_instances
       SET active_requests = active_requests - 1
     WHERE instance_id = p_instance_id
       AND active_requests > 0;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown instance or no active request to release';
    END IF;
END;
$$;

-- A backup snapshots the current active object versions within one transaction.
-- Its manifest checksum covers sorted keys, versions, and content checksums.
CREATE OR REPLACE FUNCTION create_bucket_backup(p_bucket_id BIGINT)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    new_backup_id BIGINT;
    item_count INTEGER;
    manifest_hash TEXT;
BEGIN
    PERFORM 1
      FROM storage_buckets
     WHERE bucket_id = p_bucket_id
     FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown storage bucket %', p_bucket_id;
    END IF;

    INSERT INTO backups (bucket_id, state)
    VALUES (p_bucket_id, 'failed')
    RETURNING backup_id INTO new_backup_id;

    INSERT INTO backup_items (
        backup_id, object_key, version_number, content, content_sha256
    )
    SELECT new_backup_id, object_key, current_version, content, content_sha256
      FROM stored_objects
     WHERE bucket_id = p_bucket_id
       AND state = 'active'
     ORDER BY object_key;

    SELECT count(*)::INTEGER,
           encode(
               digest(
                   COALESCE(
                       string_agg(
                           object_key || ':' || version_number::TEXT || ':' ||
                           content_sha256,
                           E'\n' ORDER BY object_key
                       ),
                       ''
                   ),
                   'sha256'
               ),
               'hex'
           )
      INTO item_count, manifest_hash
      FROM backup_items
     WHERE backup_id = new_backup_id;

    UPDATE backups
       SET state = 'completed',
           completed_at = now(),
           manifest_sha256 = manifest_hash,
           object_count = item_count
     WHERE backup_id = new_backup_id;

    RETURN new_backup_id;
END;
$$;

CREATE OR REPLACE FUNCTION evaluate_architecture(p_repository_id BIGINT)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    policy architecture_policies%ROWTYPE;
    active_zones INTEGER;
    running_instances INTEGER;
    completed_backups INTEGER;
    violations JSONB := '[]'::jsonb;
    is_eligible BOOLEAN;
    result_id BIGINT;
BEGIN
    SELECT *
      INTO policy
      FROM architecture_policies
     WHERE repository_id = p_repository_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Architecture policy missing for repository %',
            p_repository_id;
    END IF;

    SELECT count(DISTINCT i.zone_id), count(*)
      INTO active_zones, running_instances
      FROM compute_instances i
     WHERE i.repository_id = p_repository_id
       AND i.state = 'running';

    IF active_zones < policy.minimum_zones THEN
        violations := violations || jsonb_build_array(
            'Insufficient availability-zone diversity'
        );
    END IF;

    IF running_instances < policy.minimum_running_instances THEN
        violations := violations || jsonb_build_array(
            'Insufficient running compute instances'
        );
    END IF;

    SELECT count(*)
      INTO completed_backups
      FROM backups b
      JOIN storage_buckets sb ON sb.bucket_id = b.bucket_id
     WHERE sb.repository_id = p_repository_id
       AND b.state = 'completed';

    IF policy.require_backup AND completed_backups = 0 THEN
        violations := violations || jsonb_build_array(
            'No completed backup is available'
        );
    END IF;

    IF EXISTS (
        SELECT 1
          FROM storage_buckets b
          JOIN stored_objects o ON o.bucket_id = b.bucket_id
         WHERE b.repository_id = p_repository_id
           AND octet_length(o.content) > policy.maximum_object_bytes
    ) THEN
        violations := violations || jsonb_build_array(
            'Object exceeds architecture policy size limit'
        );
    END IF;

    is_eligible := jsonb_array_length(violations) = 0;

    INSERT INTO policy_evaluations(repository_id, eligible, violations)
    VALUES (p_repository_id, is_eligible, violations)
    RETURNING evaluation_id INTO result_id;

    RETURN result_id;
END;
$$;

CREATE VIEW current_active_objects AS
SELECT
    r.repository_name,
    b.bucket_name,
    o.object_key,
    o.current_version,
    octet_length(o.content) AS size_bytes,
    o.content_sha256,
    o.created_at
FROM stored_objects o
JOIN storage_buckets b ON b.bucket_id = o.bucket_id
JOIN repositories r ON r.repository_id = b.repository_id
WHERE o.state = 'active';

CREATE VIEW compute_capacity_report AS
SELECT
    r.repository_name,
    z.zone_name,
    count(i.instance_id) FILTER (WHERE i.state = 'running') AS running_instances,
    COALESCE(sum(i.capacity_per_second) FILTER (
        WHERE i.state = 'running'
    ), 0) AS total_capacity,
    COALESCE(sum(i.active_requests) FILTER (
        WHERE i.state = 'running'
    ), 0) AS active_requests
FROM repositories r
LEFT JOIN compute_instances i ON i.repository_id = r.repository_id
LEFT JOIN availability_zones z ON z.zone_id = i.zone_id
GROUP BY r.repository_name, z.zone_name;

-- Sample architecture: three zones, three virtual servers, and versioned storage.
INSERT INTO repositories(repository_name, region)
VALUES ('inventory-platform', 'ap-south-1');

INSERT INTO availability_zones(repository_id, zone_name, region)
SELECT r.repository_id, z.zone_name, 'ap-south-1'
FROM repositories r
CROSS JOIN (
    VALUES ('zone-a'), ('zone-b'), ('zone-c')
) AS z(zone_name)
WHERE r.repository_name = 'inventory-platform';

INSERT INTO compute_instances(
    repository_id, zone_id, instance_name, capacity_per_second
)
SELECT r.repository_id, z.zone_id, 'vm-' || z.zone_name, capacity
FROM repositories r
JOIN availability_zones z ON z.repository_id = r.repository_id
JOIN (
    VALUES ('zone-a', 10), ('zone-b', 15), ('zone-c', 8)
) AS v(zone_name, capacity) USING (zone_name)
WHERE r.repository_name = 'inventory-platform';

INSERT INTO storage_buckets(repository_id, bucket_name, max_object_bytes)
SELECT repository_id, 'application-data', 4096
FROM repositories
WHERE repository_name = 'inventory-platform';

INSERT INTO architecture_policies(
    repository_id, minimum_zones, minimum_running_instances,
    require_backup, maximum_object_bytes
)
SELECT repository_id, 2, 2, TRUE, 4096
FROM repositories
WHERE repository_name = 'inventory-platform';

INSERT INTO stored_objects(
    bucket_id, object_key, current_version, content, content_sha256
)
SELECT
    b.bucket_id,
    v.object_key,
    1,
    convert_to(v.content, 'UTF8'),
    encode(digest(convert_to(v.content, 'UTF8'), 'sha256'), 'hex')
FROM storage_buckets b
CROSS JOIN (
    VALUES
        ('config/service.json', '{"service":"inventory","revision":1}'),
        ('reports/daily.txt', 'Inventory daily report')
) AS v(object_key, content)
WHERE b.bucket_name = 'application-data';

-- Transactional request: reserve capacity, create a request record,
-- and release capacity in the same transaction for this short simulation.
DO $$
DECLARE
    repo_id BIGINT;
    instance_id BIGINT;
    request_id BIGINT;
BEGIN
    SELECT repository_id INTO repo_id
      FROM repositories
     WHERE repository_name = 'inventory-platform';

    instance_id := reserve_compute_instance(repo_id);

    INSERT INTO load_balancer_requests(
        repository_id, instance_id, request_key, state
    )
    VALUES (repo_id, instance_id, gen_random_uuid(), 'accepted')
    RETURNING load_balancer_requests.request_id INTO request_id;

    UPDATE load_balancer_requests
       SET state = 'served', completed_at = now()
     WHERE load_balancer_requests.request_id = request_id;

    PERFORM release_compute_instance(instance_id);
END;
$$;

-- Create a verified backup of the active bucket contents.
SELECT create_bucket_backup(bucket_id)
FROM storage_buckets
WHERE bucket_name = 'application-data';

-- Demonstrate version preservation with a new content revision.
UPDATE stored_objects
   SET current_version = current_version + 1,
       content = convert_to(
           '{"service":"inventory","revision":2}', 'UTF8'
       ),
       content_sha256 = encode(
           digest(convert_to(
               '{"service":"inventory","revision":2}', 'UTF8'
           ), 'sha256'),
           'hex'
       )
 WHERE object_key = 'config/service.json';

-- Demonstrate a failed request when all compute instances are unavailable.
-- The nested exception block rolls back its failed reservation attempt.
DO $$
DECLARE
    repo_id BIGINT;
    instance_id BIGINT;
BEGIN
    SELECT repository_id INTO repo_id
      FROM repositories
     WHERE repository_name = 'inventory-platform';

    UPDATE compute_instances
       SET state = 'unhealthy'
     WHERE repository_id = repo_id;

    BEGIN
        instance_id := reserve_compute_instance(repo_id);
        RAISE EXCEPTION 'Unexpected reservation: %', instance_id;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Expected capacity failure: %', SQLERRM;
    END;

    -- Restore service availability for subsequent policy evaluation.
    UPDATE compute_instances
       SET state = 'running'
     WHERE repository_id = repo_id;
END;
$$;

SELECT evaluate_architecture(repository_id)
FROM repositories
WHERE repository_name = 'inventory-platform';

-- Reporting queries: capacity, current objects, backup integrity metadata,
-- request outcomes, and architecture policy violations.
SELECT * FROM compute_capacity_report ORDER BY repository_name, zone_name;

SELECT * FROM current_active_objects ORDER BY bucket_name, object_key;

SELECT
    b.backup_id,
    b.state,
    b.object_count,
    b.manifest_sha256,
    b.completed_at
FROM backups b
ORDER BY b.backup_id;

SELECT
    r.repository_name,
    q.state,
    count(*) AS request_count
FROM load_balancer_requests q
JOIN repositories r ON r.repository_id = q.repository_id
GROUP BY r.repository_name, q.state
ORDER BY r.repository_name, q.state;

SELECT
    r.repository_name,
    e.evaluated_at,
    e.eligible,
    e.violations
FROM policy_evaluations e
JOIN repositories r ON r.repository_id = e.repository_id
ORDER BY e.evaluated_at DESC;

-- Validate that a backup contains the expected number of entries and that
-- each stored item has a matching SHA-256 digest.
SELECT
    b.backup_id,
    b.state,
    b.object_count,
    count(i.backup_id) AS actual_items,
    bool_and(
        encode(digest(i.content, 'sha256'), 'hex') = i.content_sha256
    ) AS items_valid
FROM backups b
LEFT JOIN backup_items i ON i.backup_id = b.backup_id
GROUP BY b.backup_id, b.state, b.object_count
ORDER BY b.backup_id;

COMMIT;
