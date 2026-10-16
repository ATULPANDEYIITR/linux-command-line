DROP SCHEMA IF EXISTS object_storage_demo CASCADE;

CREATE SCHEMA object_storage_demo;

SET search_path = object_storage_demo;

CREATE TYPE storage_class AS ENUM (
    'STANDARD',
    'INFREQUENT_ACCESS',
    'ARCHIVE'
);

CREATE TYPE versioning_state AS ENUM (
    'ENABLED',
    'SUSPENDED'
);

CREATE TYPE object_state AS ENUM (
    'ACTIVE',
    'DELETE_MARKER'
);

CREATE TYPE review_event_type AS ENUM (
    'PUT',
    'DELETE_MARKER',
    'VERSION_DELETE',
    'LIFECYCLE_TRANSITION',
    'LIFECYCLE_EXPIRATION'
);

CREATE TABLE buckets (
    bucket_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_name VARCHAR(63) NOT NULL UNIQUE,
    region VARCHAR(64) NOT NULL,
    versioning versioning_state NOT NULL DEFAULT 'ENABLED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT bucket_name_format
        CHECK (
            bucket_name ~ '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$'
        )
);

CREATE TABLE objects (
    object_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES buckets(bucket_id)
        ON DELETE RESTRICT,
    object_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bucket_id, object_key)
);

CREATE TABLE object_versions (
    object_version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    object_id BIGINT NOT NULL REFERENCES objects(object_id)
        ON DELETE CASCADE,
    version_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    object_state object_state NOT NULL DEFAULT 'ACTIVE',
    size_bytes BIGINT NOT NULL,
    checksum_sha256 CHAR(64) NOT NULL,
    content_type TEXT NOT NULL,
    storage_class storage_class NOT NULL DEFAULT 'STANDARD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT non_negative_object_size
        CHECK (size_bytes >= 0),
    CONSTRAINT valid_sha256
        CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT delete_marker_size
        CHECK (
            object_state = 'ACTIVE'
            OR size_bytes = 0
        )
);

CREATE TABLE object_metadata (
    object_version_id BIGINT NOT NULL
        REFERENCES object_versions(object_version_id)
        ON DELETE CASCADE,
    metadata_key TEXT NOT NULL,
    metadata_value TEXT NOT NULL,
    PRIMARY KEY(object_version_id, metadata_key),
    CONSTRAINT metadata_key_not_blank
        CHECK (btrim(metadata_key) <> '')
);

CREATE TABLE lifecycle_rules (
    lifecycle_rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES buckets(bucket_id)
        ON DELETE CASCADE,
    rule_name TEXT NOT NULL,
    object_prefix TEXT NOT NULL DEFAULT '',
    transition_after_days INTEGER,
    transition_to storage_class,
    expire_after_days INTEGER,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT lifecycle_transition_pair
        CHECK (
            (transition_after_days IS NULL AND transition_to IS NULL)
            OR
            (
                transition_after_days IS NOT NULL
                AND transition_to IS NOT NULL
                AND transition_after_days >= 0
            )
        ),
    CONSTRAINT lifecycle_expiration_valid
        CHECK (
            expire_after_days IS NULL
            OR expire_after_days >= 0
        )
);

CREATE TABLE object_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES buckets(bucket_id),
    object_id BIGINT REFERENCES objects(object_id),
    object_version_id BIGINT REFERENCES object_versions(object_version_id),
    event_type review_event_type NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_objects_bucket_key
    ON objects(bucket_id, object_key);

CREATE INDEX idx_versions_object_created
    ON object_versions(object_id, created_at DESC);

CREATE INDEX idx_versions_storage_class
    ON object_versions(storage_class, created_at);

CREATE INDEX idx_metadata_key_value
    ON object_metadata(metadata_key, metadata_value);

CREATE INDEX idx_lifecycle_bucket_prefix
    ON lifecycle_rules(bucket_id, object_prefix)
    WHERE enabled = TRUE;

CREATE INDEX idx_events_bucket_time
    ON object_events(bucket_id, event_time DESC);

INSERT INTO buckets (
    bucket_name,
    region,
    versioning
)
VALUES
    ('enterprise-data-store', 'ap-south-1', 'ENABLED'),
    ('temporary-ingestion-store', 'ap-south-1', 'SUSPENDED');

INSERT INTO lifecycle_rules (
    bucket_id,
    rule_name,
    object_prefix,
    transition_after_days,
    transition_to,
    expire_after_days
)
SELECT
    bucket_id,
    'Archive analytics datasets',
    'analytics/',
    30,
    'INFREQUENT_ACCESS',
    365
FROM buckets
WHERE bucket_name = 'enterprise-data-store';

INSERT INTO lifecycle_rules (
    bucket_id,
    rule_name,
    object_prefix,
    transition_after_days,
    transition_to
)
SELECT
    bucket_id,
    'Deep archive historical reports',
    'reports/',
    90,
    'ARCHIVE'
FROM buckets
WHERE bucket_name = 'enterprise-data-store';

INSERT INTO objects (
    bucket_id,
    object_key,
    created_at
)
SELECT
    bucket_id,
    'analytics/events.parquet',
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM buckets
WHERE bucket_name = 'enterprise-data-store';

INSERT INTO objects (
    bucket_id,
    object_key,
    created_at
)
SELECT
    bucket_id,
    'reports/monthly.json',
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM buckets
WHERE bucket_name = 'enterprise-data-store';

INSERT INTO objects (
    bucket_id,
    object_key,
    created_at
)
SELECT
    bucket_id,
    'audit/access.log',
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM buckets
WHERE bucket_name = 'enterprise-data-store';

INSERT INTO object_versions (
    object_id,
    version_id,
    object_state,
    size_bytes,
    checksum_sha256,
    content_type,
    storage_class,
    created_at
)
SELECT
    o.object_id,
    '11111111-1111-1111-1111-111111111111',
    'ACTIVE',
    2500000,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'application/vnd.apache.parquet',
    'STANDARD',
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM objects o
JOIN buckets b ON b.bucket_id = o.bucket_id
WHERE b.bucket_name = 'enterprise-data-store'
  AND o.object_key = 'analytics/events.parquet';

INSERT INTO object_versions (
    object_id,
    version_id,
    object_state,
    size_bytes,
    checksum_sha256,
    content_type,
    storage_class,
    created_at
)
SELECT
    o.object_id,
    '22222222-2222-2222-2222-222222222222',
    'ACTIVE',
    2700000,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'application/vnd.apache.parquet',
    'STANDARD',
    TIMESTAMPTZ '2026-01-10 00:00:00+00'
FROM objects o
JOIN buckets b ON b.bucket_id = o.bucket_id
WHERE b.bucket_name = 'enterprise-data-store'
  AND o.object_key = 'analytics/events.parquet';

INSERT INTO object_versions (
    object_id,
    version_id,
    object_state,
    size_bytes,
    checksum_sha256,
    content_type,
    storage_class,
    created_at
)
SELECT
    o.object_id,
    '33333333-3333-3333-3333-333333333333',
    'ACTIVE',
    84000,
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    'application/json',
    'STANDARD',
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM objects o
JOIN buckets b ON b.bucket_id = o.bucket_id
WHERE b.bucket_name = 'enterprise-data-store'
  AND o.object_key = 'reports/monthly.json';

INSERT INTO object_versions (
    object_id,
    version_id,
    object_state,
    size_bytes,
    checksum_sha256,
    content_type,
    storage_class,
    created_at
)
SELECT
    o.object_id,
    '44444444-4444-4444-4444-444444444444',
    'ACTIVE',
    12400,
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
    'text/plain',
    'STANDARD',
    TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM objects o
JOIN buckets b ON b.bucket_id = o.bucket_id
WHERE b.bucket_name = 'enterprise-data-store'
  AND o.object_key = 'audit/access.log';

INSERT INTO object_metadata (
    object_version_id,
    metadata_key,
    metadata_value
)
SELECT
    ov.object_version_id,
    metadata.metadata_key,
    metadata.metadata_value
FROM object_versions ov
CROSS JOIN LATERAL (
    VALUES
        ('owner', 'data-platform'),
        ('classification', 'internal'),
        ('retention', 'business')
) AS metadata(metadata_key, metadata_value)
WHERE ov.version_id =
    '22222222-2222-2222-2222-222222222222';

INSERT INTO object_metadata (
    object_version_id,
    metadata_key,
    metadata_value
)
SELECT
    ov.object_version_id,
    metadata.metadata_key,
    metadata.metadata_value
FROM object_versions ov
CROSS JOIN LATERAL (
    VALUES
        ('service', 'identity'),
        ('retention', 'regulated')
) AS metadata(metadata_key, metadata_value)
WHERE ov.version_id =
    '44444444-4444-4444-4444-444444444444';

INSERT INTO object_events (
    bucket_id,
    object_id,
    object_version_id,
    event_type,
    event_time,
    details
)
SELECT
    b.bucket_id,
    o.object_id,
    ov.object_version_id,
    'PUT',
    ov.created_at,
    jsonb_build_object(
        'key', o.object_key,
        'storage_class', ov.storage_class
    )
FROM object_versions ov
JOIN objects o ON o.object_id = ov.object_id
JOIN buckets b ON b.bucket_id = o.bucket_id;

CREATE OR REPLACE VIEW current_objects AS
WITH ranked_versions AS (
    SELECT
        ov.*,
        ROW_NUMBER() OVER (
            PARTITION BY ov.object_id
            ORDER BY ov.created_at DESC, ov.object_version_id DESC
        ) AS version_rank
    FROM object_versions ov
)
SELECT
    b.bucket_name,
    b.region,
    o.object_key,
    rv.version_id,
    rv.size_bytes,
    rv.content_type,
    rv.storage_class,
    rv.object_state,
    rv.created_at
FROM ranked_versions rv
JOIN objects o ON o.object_id = rv.object_id
JOIN buckets b ON b.bucket_id = o.bucket_id
WHERE rv.version_rank = 1;

CREATE OR REPLACE FUNCTION apply_lifecycle(
    evaluation_time TIMESTAMPTZ
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    changed_count INTEGER := 0;
BEGIN
    UPDATE object_versions ov
    SET storage_class = lr.transition_to
    FROM objects o
    JOIN lifecycle_rules lr
      ON lr.bucket_id = o.bucket_id
     AND lr.enabled = TRUE
     AND o.object_key LIKE lr.object_prefix || '%'
    WHERE ov.object_id = o.object_id
      AND ov.object_state = 'ACTIVE'
      AND lr.transition_after_days IS NOT NULL
      AND lr.transition_to IS NOT NULL
      AND ov.created_at
          <= evaluation_time
             - make_interval(days => lr.transition_after_days)
      AND ov.storage_class <> lr.transition_to;

    GET DIAGNOSTICS changed_count = ROW_COUNT;

    INSERT INTO object_events (
        bucket_id,
        object_id,
        object_version_id,
        event_type,
        event_time,
        details
    )
    SELECT
        o.bucket_id,
        o.object_id,
        ov.object_version_id,
        'LIFECYCLE_TRANSITION',
        evaluation_time,
        jsonb_build_object(
            'storage_class', ov.storage_class
        )
    FROM object_versions ov
    JOIN objects o ON o.object_id = ov.object_id
    JOIN lifecycle_rules lr
      ON lr.bucket_id = o.bucket_id
     AND lr.enabled = TRUE
     AND o.object_key LIKE lr.object_prefix || '%'
    WHERE ov.object_state = 'ACTIVE'
      AND ov.created_at
          <= evaluation_time
             - make_interval(days => lr.transition_after_days);

    RETURN changed_count;
END;
$$;

SELECT *
FROM current_objects
ORDER BY bucket_name, object_key;

SELECT
    bucket_name,
    object_key,
    version_id,
    size_bytes,
    storage_class,
    created_at
FROM current_objects
WHERE object_key LIKE 'analytics/%'
ORDER BY object_key;

SELECT
    o.object_key,
    COUNT(*) AS version_count,
    SUM(ov.size_bytes) AS total_versioned_bytes
FROM objects o
JOIN object_versions ov
    ON ov.object_id = o.object_id
GROUP BY o.object_key
ORDER BY o.object_key;

SELECT
    o.object_key,
    ov.version_id,
    om.metadata_key,
    om.metadata_value
FROM object_metadata om
JOIN object_versions ov
    ON ov.object_version_id = om.object_version_id
JOIN objects o
    ON o.object_id = ov.object_id
ORDER BY o.object_key, om.metadata_key;

BEGIN;

SELECT
    b.bucket_name,
    o.object_key,
    ov.version_id
FROM object_versions ov
JOIN objects o ON o.object_id = ov.object_id
JOIN buckets b ON b.bucket_id = o.bucket_id
WHERE b.bucket_name = 'enterprise-data-store'
  AND o.object_key = 'analytics/events.parquet'
ORDER BY ov.created_at DESC
FOR UPDATE;

UPDATE object_versions
SET storage_class = 'INFREQUENT_ACCESS'
WHERE version_id =
    '11111111-1111-1111-1111-111111111111';

INSERT INTO object_events (
    bucket_id,
    object_id,
    object_version_id,
    event_type,
    details
)
SELECT
    o.bucket_id,
    o.object_id,
    ov.object_version_id,
    'LIFECYCLE_TRANSITION',
    jsonb_build_object(
        'reason', 'manual policy evaluation'
    )
FROM object_versions ov
JOIN objects o ON o.object_id = ov.object_id
WHERE ov.version_id =
    '11111111-1111-1111-1111-111111111111';

COMMIT;

SELECT apply_lifecycle(
    TIMESTAMPTZ '2026-04-15 00:00:00+00'
);

SELECT
    bucket_name,
    object_key,
    version_id,
    storage_class,
    created_at
FROM current_objects
ORDER BY object_key;

-- PostgreSQL constraints intentionally reject invalid states such as
-- negative object sizes and malformed SHA-256 values.
-- The following statements are examples of invalid operations and should
-- be tested independently rather than executed as part of the successful
-- workflow:
--
-- INSERT INTO object_versions (
--     object_id, size_bytes, checksum_sha256, content_type
-- )
-- VALUES (
--     1, -50, 'invalid', 'text/plain'
-- );
