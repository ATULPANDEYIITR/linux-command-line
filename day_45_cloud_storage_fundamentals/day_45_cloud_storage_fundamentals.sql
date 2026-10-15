CREATE SCHEMA IF NOT EXISTS cloud_storage;

DROP VIEW IF EXISTS cloud_storage.object_storage_health;
DROP VIEW IF EXISTS cloud_storage.merge_eligibility;
DROP TABLE IF EXISTS cloud_storage.storage_events CASCADE;
DROP TABLE IF EXISTS cloud_storage.status_checks CASCADE;
DROP TABLE IF EXISTS cloud_storage.reviews CASCADE;
DROP TABLE IF EXISTS cloud_storage.reviewers CASCADE;
DROP TABLE IF EXISTS cloud_storage.objects CASCADE;
DROP TABLE IF EXISTS cloud_storage.replica_health CASCADE;
DROP TABLE IF EXISTS cloud_storage.replicas CASCADE;
DROP TABLE IF EXISTS cloud_storage.branch_protection CASCADE;
DROP TABLE IF EXISTS cloud_storage.buckets CASCADE;
DROP TABLE IF EXISTS cloud_storage.regions CASCADE;

CREATE TABLE cloud_storage.regions (
    region_id BIGSERIAL PRIMARY KEY,
    region_code TEXT NOT NULL UNIQUE,
    region_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE cloud_storage.buckets (
    bucket_id BIGSERIAL PRIMARY KEY,
    bucket_name TEXT NOT NULL UNIQUE,
    replication_factor INTEGER NOT NULL,
    encryption_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    versioning_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (replication_factor >= 1)
);

CREATE TABLE cloud_storage.branch_protection (
    policy_id BIGSERIAL PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES cloud_storage.buckets(bucket_id),
    minimum_healthy_replicas INTEGER NOT NULL,
    require_multi_region BOOLEAN NOT NULL DEFAULT TRUE,
    require_encryption BOOLEAN NOT NULL DEFAULT TRUE,
    prevent_unprotected_writes BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (minimum_healthy_replicas >= 1),
    UNIQUE (bucket_id)
);

CREATE TABLE cloud_storage.replicas (
    replica_id BIGSERIAL PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES cloud_storage.buckets(bucket_id),
    region_id BIGINT NOT NULL REFERENCES cloud_storage.regions(region_id),
    state TEXT NOT NULL DEFAULT 'healthy',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (state IN ('healthy', 'failed', 'repairing')),
    UNIQUE (bucket_id, region_id)
);

CREATE TABLE cloud_storage.objects (
    object_id BIGSERIAL PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES cloud_storage.buckets(bucket_id),
    object_key TEXT NOT NULL,
    object_size_bytes BIGINT NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    storage_class TEXT NOT NULL DEFAULT 'standard',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,
    CHECK (object_size_bytes > 0),
    CHECK (
        storage_class IN (
            'standard',
            'infrequent_access',
            'archive'
        )
    ),
    UNIQUE (bucket_id, object_key)
);

CREATE TABLE cloud_storage.replica_health (
    health_id BIGSERIAL PRIMARY KEY,
    object_id BIGINT NOT NULL REFERENCES cloud_storage.objects(object_id),
    replica_id BIGINT NOT NULL REFERENCES cloud_storage.replicas(replica_id),
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checksum_valid BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (checksum_valid = TRUE OR checksum_valid = FALSE),
    UNIQUE (object_id, replica_id)
);

CREATE TABLE cloud_storage.reviewers (
    reviewer_id BIGSERIAL PRIMARY KEY,
    reviewer_name TEXT NOT NULL,
    role_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE cloud_storage.reviews (
    review_id BIGSERIAL PRIMARY KEY,
    object_id BIGINT NOT NULL REFERENCES cloud_storage.objects(object_id),
    reviewer_id BIGINT NOT NULL REFERENCES cloud_storage.reviewers(reviewer_id),
    review_state TEXT NOT NULL,
    review_comment TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        review_state IN (
            'commented',
            'changes_requested',
            'approved'
        )
    )
);

CREATE TABLE cloud_storage.status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES cloud_storage.buckets(bucket_id),
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('pending', 'passed', 'failed')),
    UNIQUE (bucket_id, check_name)
);

CREATE TABLE cloud_storage.storage_events (
    event_id BIGSERIAL PRIMARY KEY,
    bucket_id BIGINT REFERENCES cloud_storage.buckets(bucket_id),
    object_id BIGINT REFERENCES cloud_storage.objects(object_id),
    event_type TEXT NOT NULL,
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_replicas_bucket_state
    ON cloud_storage.replicas(bucket_id, state);

CREATE INDEX idx_replica_health_object
    ON cloud_storage.replica_health(object_id);

CREATE INDEX idx_objects_bucket_class
    ON cloud_storage.objects(bucket_id, storage_class);

CREATE INDEX idx_storage_events_bucket_time
    ON cloud_storage.storage_events(bucket_id, occurred_at DESC);

INSERT INTO cloud_storage.regions
    (region_code, region_name)
VALUES
    ('ap-south-1', 'Mumbai'),
    ('ap-south-2', 'Hyderabad'),
    ('ap-southeast-1', 'Singapore'),
    ('eu-central-1', 'Frankfurt');

INSERT INTO cloud_storage.buckets
    (bucket_name, replication_factor, encryption_enabled, versioning_enabled)
VALUES
    ('production-data', 3, TRUE, TRUE),
    ('archive-data', 2, TRUE, TRUE);

INSERT INTO cloud_storage.branch_protection
    (bucket_id, minimum_healthy_replicas, require_multi_region,
     require_encryption, prevent_unprotected_writes)
SELECT
    bucket_id,
    CASE
        WHEN bucket_name = 'production-data' THEN 2
        ELSE 1
    END,
    TRUE,
    TRUE,
    TRUE
FROM cloud_storage.buckets;

INSERT INTO cloud_storage.replicas
    (bucket_id, region_id, state)
SELECT
    b.bucket_id,
    r.region_id,
    'healthy'
FROM cloud_storage.buckets b
JOIN cloud_storage.regions r
    ON (
        (b.bucket_name = 'production-data'
         AND r.region_code IN (
             'ap-south-1',
             'ap-southeast-1',
             'eu-central-1'
         ))
        OR
        (b.bucket_name = 'archive-data'
         AND r.region_code IN (
             'ap-south-1',
             'ap-south-2'
         ))
    );

INSERT INTO cloud_storage.objects
    (bucket_id, object_key, object_size_bytes, content_sha256, storage_class)
SELECT
    b.bucket_id,
    'datasets/market-data-2026-10-15.parquet',
    268435456,
    repeat('a', 64),
    'standard'
FROM cloud_storage.buckets b
WHERE b.bucket_name = 'production-data';

INSERT INTO cloud_storage.objects
    (bucket_id, object_key, object_size_bytes, content_sha256, storage_class)
SELECT
    b.bucket_id,
    'archive/market-data-2025.parquet',
    1073741824,
    repeat('b', 64),
    'archive'
FROM cloud_storage.buckets b
WHERE b.bucket_name = 'archive-data';

INSERT INTO cloud_storage.replica_health
    (object_id, replica_id, checksum_valid)
SELECT
    o.object_id,
    r.replica_id,
    TRUE
FROM cloud_storage.objects o
JOIN cloud_storage.replicas r
    ON r.bucket_id = o.bucket_id;

INSERT INTO cloud_storage.reviewers
    (reviewer_name, role_name)
VALUES
    ('Asha Rao', 'Storage Platform Engineer'),
    ('Vikram Singh', 'Site Reliability Engineer'),
    ('Neha Sharma', 'Security Engineer');

INSERT INTO cloud_storage.status_checks
    (bucket_id, check_name, status)
SELECT
    bucket_id,
    'replica-integrity',
    'passed'
FROM cloud_storage.buckets;

INSERT INTO cloud_storage.status_checks
    (bucket_id, check_name, status)
SELECT
    bucket_id,
    'encryption-policy',
    CASE
        WHEN encryption_enabled THEN 'passed'
        ELSE 'failed'
    END
FROM cloud_storage.buckets;

CREATE OR REPLACE VIEW cloud_storage.object_storage_health AS
SELECT
    o.object_id,
    b.bucket_name,
    o.object_key,
    o.object_size_bytes,
    o.storage_class,
    COUNT(r.replica_id) AS configured_replicas,
    COUNT(r.replica_id) FILTER (
        WHERE r.state = 'healthy'
    ) AS healthy_replicas,
    COUNT(r.replica_id) FILTER (
        WHERE r.state = 'failed'
    ) AS failed_replicas,
    COUNT(DISTINCT r.region_id) AS replica_regions,
    CASE
        WHEN COUNT(r.replica_id) FILTER (
            WHERE r.state = 'healthy'
        ) = 0 THEN 'UNAVAILABLE'
        WHEN COUNT(r.replica_id) FILTER (
            WHERE r.state = 'healthy'
        ) < b.replication_factor THEN 'DEGRADED'
        ELSE 'AVAILABLE'
    END AS availability_state
FROM cloud_storage.objects o
JOIN cloud_storage.buckets b
    ON b.bucket_id = o.bucket_id
LEFT JOIN cloud_storage.replicas r
    ON r.bucket_id = b.bucket_id
WHERE o.deleted_at IS NULL
GROUP BY
    o.object_id,
    b.bucket_name,
    o.object_key,
    o.object_size_bytes,
    o.storage_class,
    b.replication_factor;

SELECT *
FROM cloud_storage.object_storage_health
ORDER BY bucket_name, object_key;

SELECT
    b.bucket_name,
    SUM(o.object_size_bytes) AS logical_bytes,
    SUM(o.object_size_bytes * b.replication_factor)
        AS replicated_capacity_bytes
FROM cloud_storage.buckets b
JOIN cloud_storage.objects o
    ON o.bucket_id = b.bucket_id
WHERE o.deleted_at IS NULL
GROUP BY b.bucket_name;

SELECT
    b.bucket_name,
    COUNT(DISTINCT r.region_id) AS region_count,
    b.replication_factor,
    CASE
        WHEN COUNT(DISTINCT r.region_id) >= 2
             AND b.replication_factor >= 2
        THEN 'MULTI_REGION_REDUNDANCY'
        ELSE 'SINGLE_FAILURE_DOMAIN'
    END AS redundancy_profile
FROM cloud_storage.buckets b
LEFT JOIN cloud_storage.replicas r
    ON r.bucket_id = b.bucket_id
GROUP BY
    b.bucket_name,
    b.replication_factor;

SELECT
    b.bucket_name,
    p.minimum_healthy_replicas,
    COUNT(r.replica_id) FILTER (
        WHERE r.state = 'healthy'
    ) AS healthy_replicas,
    CASE
        WHEN COUNT(r.replica_id) FILTER (
            WHERE r.state = 'healthy'
        ) >= p.minimum_healthy_replicas
        AND (
            NOT p.require_multi_region
            OR COUNT(DISTINCT r.region_id) >= 2
        )
        AND (
            NOT p.require_encryption
            OR b.encryption_enabled
        )
        THEN 'COMPLIANT'
        ELSE 'NON_COMPLIANT'
    END AS policy_state
FROM cloud_storage.buckets b
JOIN cloud_storage.branch_protection p
    ON p.bucket_id = b.bucket_id
LEFT JOIN cloud_storage.replicas r
    ON r.bucket_id = b.bucket_id
GROUP BY
    b.bucket_name,
    p.minimum_healthy_replicas,
    p.require_multi_region,
    p.require_encryption,
    b.encryption_enabled;

BEGIN;

UPDATE cloud_storage.replicas
SET state = 'failed'
WHERE bucket_id = (
    SELECT bucket_id
    FROM cloud_storage.buckets
    WHERE bucket_name = 'production-data'
)
AND region_id = (
    SELECT region_id
    FROM cloud_storage.regions
    WHERE region_code = 'ap-south-1'
);

INSERT INTO cloud_storage.storage_events
    (bucket_id, event_type, event_payload)
SELECT
    bucket_id,
    'regional_failure',
    jsonb_build_object(
        'region', 'Mumbai',
        'reason', 'simulated infrastructure failure'
    )
FROM cloud_storage.buckets
WHERE bucket_name = 'production-data';

COMMIT;

SELECT *
FROM cloud_storage.object_storage_health
WHERE bucket_name = 'production-data';

BEGIN;

UPDATE cloud_storage.replicas
SET state = 'failed'
WHERE bucket_id = (
    SELECT bucket_id
    FROM cloud_storage.buckets
    WHERE bucket_name = 'production-data'
)
AND region_id = (
    SELECT region_id
    FROM cloud_storage.regions
    WHERE region_code = 'ap-southeast-1'
);

SELECT
    bucket_name,
    object_key,
    availability_state
FROM cloud_storage.object_storage_health
WHERE bucket_name = 'production-data';

ROLLBACK;

SELECT
    b.bucket_name,
    COUNT(*) AS object_count,
    SUM(o.object_size_bytes) AS logical_bytes,
    ROUND(
        SUM(o.object_size_bytes) / 1024.0 / 1024.0,
        2
    ) AS logical_mib,
    ROUND(
        SUM(o.object_size_bytes * b.replication_factor)
        / 1024.0 / 1024.0,
        2
    ) AS replicated_mib
FROM cloud_storage.buckets b
JOIN cloud_storage.objects o
    ON o.bucket_id = b.bucket_id
WHERE o.deleted_at IS NULL
GROUP BY b.bucket_name, b.replication_factor
ORDER BY logical_bytes DESC;
