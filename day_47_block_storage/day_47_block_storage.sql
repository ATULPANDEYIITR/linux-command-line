DROP SCHEMA IF EXISTS block_storage_lab CASCADE;
CREATE SCHEMA block_storage_lab;
SET search_path TO block_storage_lab;

-- PostgreSQL-compatible relational model for persistent block storage.
-- A volume is independent from a compute instance so that detachment does
-- not destroy persistent data.

CREATE TYPE disk_type AS ENUM ('hdd', 'ssd', 'nvme');
CREATE TYPE volume_state AS ENUM ('available', 'attached');
CREATE TYPE attachment_mode AS ENUM ('ro', 'rw');
CREATE TYPE snapshot_state AS ENUM ('ready', 'restoring', 'failed');

CREATE TABLE compute_instance (
    instance_id BIGSERIAL PRIMARY KEY,
    instance_name TEXT NOT NULL UNIQUE,
    availability_zone TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE volume (
    volume_id BIGSERIAL PRIMARY KEY,
    volume_name TEXT NOT NULL UNIQUE,
    capacity_gib NUMERIC(12,2) NOT NULL
        CHECK (capacity_gib > 0),
    used_gib NUMERIC(12,2) NOT NULL DEFAULT 0
        CHECK (used_gib >= 0 AND used_gib <= capacity_gib),
    media_type disk_type NOT NULL,
    availability_zone TEXT NOT NULL,
    state volume_state NOT NULL DEFAULT 'available',
    encrypted BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE volume_attachment (
    attachment_id BIGSERIAL PRIMARY KEY,
    volume_id BIGINT NOT NULL
        REFERENCES volume(volume_id) ON DELETE CASCADE,
    instance_id BIGINT NOT NULL
        REFERENCES compute_instance(instance_id) ON DELETE CASCADE,
    mode attachment_mode NOT NULL,
    attached_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    detached_at TIMESTAMPTZ,

    CHECK (
        detached_at IS NULL
        OR detached_at >= attached_at
    )
);

-- Only one active attachment is permitted by this simplified model.
-- Some production platforms support multi-attach with stricter
-- filesystem and application coordination.
CREATE UNIQUE INDEX one_active_attachment_per_volume
ON volume_attachment(volume_id)
WHERE detached_at IS NULL;

CREATE TABLE storage_snapshot (
    snapshot_id BIGSERIAL PRIMARY KEY,
    snapshot_name TEXT NOT NULL UNIQUE,
    volume_id BIGINT NOT NULL
        REFERENCES volume(volume_id) ON DELETE RESTRICT,
    parent_snapshot_id BIGINT
        REFERENCES storage_snapshot(snapshot_id) ON DELETE RESTRICT,
    logical_size_gib NUMERIC(12,2) NOT NULL
        CHECK (logical_size_gib >= 0),
    changed_blocks BIGINT NOT NULL
        CHECK (changed_blocks >= 0),
    state snapshot_state NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE storage_performance_profile (
    media_type disk_type PRIMARY KEY,
    approximate_latency_ms NUMERIC(10,3) NOT NULL
        CHECK (approximate_latency_ms > 0),
    sequential_throughput_mbps NUMERIC(12,2) NOT NULL
        CHECK (sequential_throughput_mbps > 0),
    baseline_iops BIGINT NOT NULL
        CHECK (baseline_iops > 0)
);

INSERT INTO storage_performance_profile (
    media_type,
    approximate_latency_ms,
    sequential_throughput_mbps,
    baseline_iops
)
VALUES
    ('hdd', 8.000, 180.00, 150),
    ('ssd', 0.800, 550.00, 50000),
    ('nvme', 0.150, 3500.00, 500000);

INSERT INTO compute_instance (
    instance_name,
    availability_zone
)
VALUES
    ('db-prod-01', 'zone-a'),
    ('analytics-01', 'zone-a'),
    ('backup-01', 'zone-b');

INSERT INTO volume (
    volume_name,
    capacity_gib,
    used_gib,
    media_type,
    availability_zone,
    encrypted
)
VALUES
    ('db-data', 500, 185, 'nvme', 'zone-a', TRUE),
    ('analytics-data', 2000, 640, 'ssd', 'zone-a', TRUE),
    ('archive-data', 5000, 2100, 'hdd', 'zone-a', TRUE),
    ('backup-target', 4000, 100, 'ssd', 'zone-b', TRUE);

-- The active attachment records represent current compute-to-volume
-- relationships. Historical detachments remain queryable.
INSERT INTO volume_attachment (
    volume_id,
    instance_id,
    mode
)
SELECT
    v.volume_id,
    i.instance_id,
    'rw'
FROM volume v
JOIN compute_instance i
    ON i.instance_name = 'db-prod-01'
WHERE v.volume_name = 'db-data';

INSERT INTO volume_attachment (
    volume_id,
    instance_id,
    mode
)
SELECT
    v.volume_id,
    i.instance_id,
    'rw'
FROM volume v
JOIN compute_instance i
    ON i.instance_name = 'analytics-01'
WHERE v.volume_name = 'analytics-data';

UPDATE volume
SET state = 'attached'
WHERE volume_name IN ('db-data', 'analytics-data');

INSERT INTO storage_snapshot (
    snapshot_name,
    volume_id,
    logical_size_gib,
    changed_blocks
)
SELECT
    'db-before-maintenance',
    volume_id,
    used_gib,
    47360
FROM volume
WHERE volume_name = 'db-data';

INSERT INTO storage_snapshot (
    snapshot_name,
    volume_id,
    parent_snapshot_id,
    logical_size_gib,
    changed_blocks
)
SELECT
    'db-after-maintenance',
    v.volume_id,
    s.snapshot_id,
    v.used_gib + 32,
    8192
FROM volume v
JOIN storage_snapshot s
    ON s.snapshot_name = 'db-before-maintenance'
WHERE v.volume_name = 'db-data';

-- Operational inventory: capacity, utilization, attachment and media.
SELECT
    v.volume_name,
    v.media_type,
    v.capacity_gib,
    v.used_gib,
    ROUND((v.used_gib / v.capacity_gib) * 100, 2)
        AS utilization_percent,
    v.state,
    v.encrypted,
    i.instance_name,
    i.availability_zone AS compute_zone
FROM volume v
LEFT JOIN volume_attachment a
    ON a.volume_id = v.volume_id
   AND a.detached_at IS NULL
LEFT JOIN compute_instance i
    ON i.instance_id = a.instance_id
ORDER BY v.volume_name;

-- Storage-performance comparison is intentionally media-specific:
-- latency and throughput have different operational consequences.
SELECT
    v.volume_name,
    v.media_type,
    p.approximate_latency_ms,
    p.sequential_throughput_mbps,
    p.baseline_iops,
    CASE
        WHEN p.baseline_iops >= 500000
            THEN 'latency-sensitive database workload'
        WHEN p.baseline_iops >= 50000
            THEN 'general application workload'
        ELSE 'capacity-oriented archive workload'
    END AS suitable_workload_class
FROM volume v
JOIN storage_performance_profile p
    ON p.media_type = v.media_type
ORDER BY p.baseline_iops DESC;

-- Snapshot lineage exposes the difference between a full logical volume
-- size and incremental changed-block metadata.
WITH RECURSIVE snapshot_chain AS (
    SELECT
        s.snapshot_id,
        s.snapshot_name,
        s.parent_snapshot_id,
        0 AS depth
    FROM storage_snapshot s
    WHERE s.parent_snapshot_id IS NULL

    UNION ALL

    SELECT
        child.snapshot_id,
        child.snapshot_name,
        child.parent_snapshot_id,
        parent.depth + 1
    FROM storage_snapshot child
    JOIN snapshot_chain parent
        ON parent.snapshot_id = child.parent_snapshot_id
)
SELECT
    snapshot_name,
    depth,
    parent_snapshot_id
FROM snapshot_chain
ORDER BY depth, snapshot_id;

-- Identify volumes approaching capacity before writes begin failing.
SELECT
    volume_name,
    capacity_gib,
    used_gib,
    capacity_gib - used_gib AS free_gib,
    ROUND((used_gib / capacity_gib) * 100, 2)
        AS utilization_percent
FROM volume
WHERE used_gib / capacity_gib >= 0.80
ORDER BY utilization_percent DESC;

-- Database-layer validation for a cross-zone attachment.
-- The query identifies violations before an application attempts the
-- operation. In production, this rule would normally be enforced by
-- transactional service logic or a trigger because it spans tables.
SELECT
    v.volume_name,
    i.instance_name,
    v.availability_zone AS volume_zone,
    i.availability_zone AS instance_zone
FROM volume v
JOIN volume_attachment a
    ON a.volume_id = v.volume_id
   AND a.detached_at IS NULL
JOIN compute_instance i
    ON i.instance_id = a.instance_id
WHERE v.availability_zone <> i.availability_zone;

-- Transactional example: detaching a volume changes both the historical
-- attachment record and the volume's state atomically.
BEGIN;

UPDATE volume_attachment
SET detached_at = CURRENT_TIMESTAMP
WHERE volume_id = (
    SELECT volume_id
    FROM volume
    WHERE volume_name = 'db-data'
)
AND detached_at IS NULL;

UPDATE volume
SET state = 'available'
WHERE volume_name = 'db-data';

COMMIT;

-- Integrity test: a negative capacity is rejected by CHECK constraints.
-- The statement is intentionally not executed because an executable script
-- should complete successfully. The constraint can be inspected directly.
SELECT
    conname,
    pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'block_storage_lab.volume'::regclass
ORDER BY conname;

-- Snapshot storage accounting based on changed blocks.
SELECT
    s.snapshot_name,
    v.volume_name,
    s.changed_blocks,
    ROUND(
        s.changed_blocks * 4.0 / 1024 / 1024,
        3
    ) AS changed_data_gib,
    s.state
FROM storage_snapshot s
JOIN volume v
    ON v.volume_id = s.volume_id
ORDER BY s.created_at;
