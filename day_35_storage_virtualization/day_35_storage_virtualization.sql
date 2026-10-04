-- Storage Virtualization
-- PostgreSQL-compatible implementation.
--
-- Domain:
-- physical disks -> storage pools -> virtual disks -> logical volumes
-- -> logical blocks
--
-- The schema separates logical capacity from physical allocation. This is
-- essential for modeling thin provisioning, where a virtual disk can expose
-- more logical address space than it has physically allocated at creation.
--
-- The script also models snapshots, reviewers of storage operations through
-- audit records, status checks, and database-level integrity constraints.

DROP SCHEMA IF EXISTS storage_virtualization CASCADE;

CREATE SCHEMA storage_virtualization;

SET search_path = storage_virtualization, public;

CREATE TYPE disk_state AS ENUM (
    'online',
    'degraded',
    'failed'
);

CREATE TYPE provisioning_type AS ENUM (
    'thick',
    'thin'
);

CREATE TYPE volume_state AS ENUM (
    'available',
    'read_only',
    'offline'
);

CREATE TYPE operation_type AS ENUM (
    'create_pool',
    'create_virtual_disk',
    'create_volume',
    'allocate_block',
    'read_block',
    'write_block',
    'snapshot',
    'restore',
    'disk_failure'
);

CREATE TABLE storage_pool (
    pool_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pool_name        TEXT NOT NULL UNIQUE,
    description      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(pool_name)) > 0)
);

CREATE TABLE physical_disk (
    disk_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pool_id          BIGINT NOT NULL REFERENCES storage_pool(pool_id)
                     ON DELETE RESTRICT,
    device_name      TEXT NOT NULL UNIQUE,
    capacity_gib     NUMERIC(12,2) NOT NULL,
    allocated_gib    NUMERIC(12,2) NOT NULL DEFAULT 0,
    state            disk_state NOT NULL DEFAULT 'online',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT physical_disk_positive_capacity
        CHECK (capacity_gib > 0),

    CONSTRAINT physical_disk_nonnegative_allocation
        CHECK (allocated_gib >= 0),

    CONSTRAINT physical_disk_allocation_not_exceed_capacity
        CHECK (allocated_gib <= capacity_gib),

    CONSTRAINT physical_disk_name_not_blank
        CHECK (length(trim(device_name)) > 0)
);

CREATE TABLE virtual_disk (
    virtual_disk_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pool_id               BIGINT NOT NULL REFERENCES storage_pool(pool_id)
                          ON DELETE RESTRICT,
    disk_name              TEXT NOT NULL UNIQUE,
    logical_capacity_gib   NUMERIC(12,2) NOT NULL,
    physical_allocated_gib NUMERIC(12,2) NOT NULL DEFAULT 0,
    provisioning           provisioning_type NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT virtual_disk_positive_logical_capacity
        CHECK (logical_capacity_gib > 0),

    CONSTRAINT virtual_disk_nonnegative_physical_allocation
        CHECK (physical_allocated_gib >= 0),

    CONSTRAINT virtual_disk_physical_not_above_logical
        CHECK (physical_allocated_gib <= logical_capacity_gib),

    CONSTRAINT virtual_disk_name_not_blank
        CHECK (length(trim(disk_name)) > 0),

    -- A thick disk is fully reserved when created. Thin disks can have less
    -- physical allocation than logical capacity.
    CONSTRAINT thick_disk_must_be_fully_reserved
        CHECK (
            provisioning = 'thin'
            OR physical_allocated_gib = logical_capacity_gib
        )
);

CREATE TABLE logical_volume (
    volume_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    virtual_disk_id    BIGINT NOT NULL REFERENCES virtual_disk(virtual_disk_id)
                       ON DELETE RESTRICT,
    volume_name        TEXT NOT NULL UNIQUE,
    block_size_bytes   INTEGER NOT NULL DEFAULT 4096,
    logical_blocks     BIGINT NOT NULL,
    state              volume_state NOT NULL DEFAULT 'available',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT volume_positive_block_size
        CHECK (block_size_bytes > 0),

    CONSTRAINT volume_block_size_power_of_two
        CHECK (
            block_size_bytes & (block_size_bytes - 1) = 0
        ),

    CONSTRAINT volume_positive_block_count
        CHECK (logical_blocks > 0)
);

CREATE TABLE logical_block (
    volume_id          BIGINT NOT NULL REFERENCES logical_volume(volume_id)
                       ON DELETE CASCADE,
    block_number       BIGINT NOT NULL,
    payload            BYTEA,
    physical_disk_id   BIGINT REFERENCES physical_disk(disk_id)
                       ON DELETE RESTRICT,
    allocation_gib     NUMERIC(12,4) NOT NULL DEFAULT 0,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (volume_id, block_number),

    CONSTRAINT logical_block_nonnegative_number
        CHECK (block_number >= 0),

    CONSTRAINT logical_block_nonnegative_allocation
        CHECK (allocation_gib >= 0),

    CONSTRAINT logical_block_allocation_requires_payload
        CHECK (
            payload IS NOT NULL
            OR allocation_gib = 0
        )
);

CREATE TABLE storage_snapshot (
    snapshot_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    volume_id          BIGINT NOT NULL REFERENCES logical_volume(volume_id)
                       ON DELETE RESTRICT,
    snapshot_name      TEXT NOT NULL UNIQUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE snapshot_block (
    snapshot_id        BIGINT NOT NULL REFERENCES storage_snapshot(snapshot_id)
                       ON DELETE CASCADE,
    block_number       BIGINT NOT NULL,
    payload            BYTEA,
    PRIMARY KEY (snapshot_id, block_number),

    CONSTRAINT snapshot_block_nonnegative_number
        CHECK (block_number >= 0)
);

CREATE TABLE storage_audit (
    audit_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operation          operation_type NOT NULL,
    pool_id            BIGINT REFERENCES storage_pool(pool_id),
    virtual_disk_id    BIGINT REFERENCES virtual_disk(virtual_disk_id),
    volume_id          BIGINT REFERENCES logical_volume(volume_id),
    disk_id            BIGINT REFERENCES physical_disk(disk_id),
    success            BOOLEAN NOT NULL,
    details            TEXT,
    occurred_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- These indexes support common operational queries without changing the
-- logical storage abstraction.
CREATE INDEX idx_physical_disk_pool_state
    ON physical_disk(pool_id, state);

CREATE INDEX idx_virtual_disk_pool
    ON virtual_disk(pool_id);

CREATE INDEX idx_logical_volume_virtual_disk
    ON logical_volume(virtual_disk_id);

CREATE INDEX idx_logical_block_volume_updated
    ON logical_block(volume_id, updated_at);

CREATE INDEX idx_snapshot_volume_created
    ON storage_snapshot(volume_id, created_at DESC);

CREATE INDEX idx_storage_audit_volume_time
    ON storage_audit(volume_id, occurred_at DESC);

-- Sample storage infrastructure.
INSERT INTO storage_pool (pool_name, description)
VALUES
    ('production-block-pool',
     'NVMe-backed pool for transactional and analytical workloads'),
    ('archive-block-pool',
     'Capacity-oriented pool for long-lived block volumes');

INSERT INTO physical_disk
    (pool_id, device_name, capacity_gib, allocated_gib, state)
SELECT
    pool_id, 'nvme-prod-01', 100, 0, 'online'
FROM storage_pool
WHERE pool_name = 'production-block-pool';

INSERT INTO physical_disk
    (pool_id, device_name, capacity_gib, allocated_gib, state)
SELECT
    pool_id, 'nvme-prod-02', 100, 0, 'online'
FROM storage_pool
WHERE pool_name = 'production-block-pool';

INSERT INTO physical_disk
    (pool_id, device_name, capacity_gib, allocated_gib, state)
SELECT
    pool_id, 'nvme-prod-03', 100, 0, 'online'
FROM storage_pool
WHERE pool_name = 'production-block-pool';

INSERT INTO physical_disk
    (pool_id, device_name, capacity_gib, allocated_gib, state)
SELECT
    pool_id, 'archive-01', 250, 0, 'online'
FROM storage_pool
WHERE pool_name = 'archive-block-pool';

-- Thick provisioning reserves the complete logical capacity.
INSERT INTO virtual_disk
    (
        pool_id,
        disk_name,
        logical_capacity_gib,
        physical_allocated_gib,
        provisioning
    )
SELECT
    pool_id,
    'vd-transactions',
    120,
    120,
    'thick'
FROM storage_pool
WHERE pool_name = 'production-block-pool';

-- Thin provisioning exposes capacity without reserving all backing space.
INSERT INTO virtual_disk
    (
        pool_id,
        disk_name,
        logical_capacity_gib,
        physical_allocated_gib,
        provisioning
    )
SELECT
    pool_id,
    'vd-analytics',
    180,
    0,
    'thin'
FROM storage_pool
WHERE pool_name = 'production-block-pool';

INSERT INTO virtual_disk
    (
        pool_id,
        disk_name,
        logical_capacity_gib,
        physical_allocated_gib,
        provisioning
    )
SELECT
    pool_id,
    'vd-archive',
    200,
    200,
    'thick'
FROM storage_pool
WHERE pool_name = 'archive-block-pool';

INSERT INTO logical_volume
    (
        virtual_disk_id,
        volume_name,
        block_size_bytes,
        logical_blocks
    )
SELECT
    virtual_disk_id,
    'lv-transactions',
    4096,
    (120::BIGINT * 1024 * 1024 * 1024) / 4096
FROM virtual_disk
WHERE disk_name = 'vd-transactions';

INSERT INTO logical_volume
    (
        virtual_disk_id,
        volume_name,
        block_size_bytes,
        logical_blocks
    )
SELECT
    virtual_disk_id,
    'lv-analytics',
    4096,
    (180::BIGINT * 1024 * 1024 * 1024) / 4096
FROM virtual_disk
WHERE disk_name = 'vd-analytics';

INSERT INTO logical_volume
    (
        virtual_disk_id,
        volume_name,
        block_size_bytes,
        logical_blocks
    )
SELECT
    virtual_disk_id,
    'lv-archive',
    4096,
    (200::BIGINT * 1024 * 1024 * 1024) / 4096
FROM virtual_disk
WHERE disk_name = 'vd-archive';

-- Assign representative logical blocks to physical devices.
-- In a real implementation this would be performed by an allocation engine
-- and would account for extents, redundancy, and placement constraints.
INSERT INTO logical_block
    (
        volume_id,
        block_number,
        payload,
        physical_disk_id,
        allocation_gib
    )
SELECT
    lv.volume_id,
    100,
    convert_to(
        'transaction=TX-2026-8842;state=SETTLED',
        'UTF8'
    ),
    pd.disk_id,
    1
FROM logical_volume lv
JOIN physical_disk pd
  ON pd.device_name = 'nvme-prod-01'
WHERE lv.volume_name = 'lv-transactions';

INSERT INTO logical_block
    (
        volume_id,
        block_number,
        payload,
        physical_disk_id,
        allocation_gib
    )
SELECT
    lv.volume_id,
    10000,
    convert_to(
        'metric=revenue;period=2026-09',
        'UTF8'
    ),
    pd.disk_id,
    1
FROM logical_volume lv
JOIN physical_disk pd
  ON pd.device_name = 'nvme-prod-02'
WHERE lv.volume_name = 'lv-analytics';

-- The thin virtual disk's physical allocation is increased only when a
-- previously unallocated logical block receives backing storage.
UPDATE virtual_disk
SET physical_allocated_gib = physical_allocated_gib + 1
WHERE disk_name = 'vd-analytics';

UPDATE physical_disk
SET allocated_gib = allocated_gib + 1
WHERE device_name = 'nvme-prod-02';

-- Snapshot captures logical blocks at a point in time.
INSERT INTO storage_snapshot (volume_id, snapshot_name)
SELECT volume_id, 'transactions-before-correction'
FROM logical_volume
WHERE volume_name = 'lv-transactions';

INSERT INTO snapshot_block
    (snapshot_id, block_number, payload)
SELECT
    snapshot.snapshot_id,
    block.block_number,
    block.payload
FROM storage_snapshot snapshot
JOIN logical_volume volume
  ON volume.volume_id = snapshot.volume_id
JOIN logical_block block
  ON block.volume_id = volume.volume_id
WHERE snapshot.snapshot_name = 'transactions-before-correction';

-- Change the live logical block after the snapshot.
UPDATE logical_block
SET
    payload = convert_to(
        'transaction=TX-2026-8842;state=REVERSED',
        'UTF8'
    ),
    updated_at = CURRENT_TIMESTAMP
WHERE volume_id = (
    SELECT volume_id
    FROM logical_volume
    WHERE volume_name = 'lv-transactions'
)
AND block_number = 100;

-- Query the current live state.
SELECT
    volume.volume_name,
    block.block_number,
    convert_from(block.payload, 'UTF8') AS current_value,
    block.physical_disk_id
FROM logical_volume volume
JOIN logical_block block
  ON block.volume_id = volume.volume_id
WHERE volume.volume_name = 'lv-transactions'
  AND block.block_number = 100;

-- Query the snapshot state separately. This illustrates the distinction
-- between current logical state and a point-in-time copy.
SELECT
    snapshot.snapshot_name,
    snapshot_block.block_number,
    convert_from(snapshot_block.payload, 'UTF8') AS snapshot_value
FROM storage_snapshot snapshot
JOIN snapshot_block
  ON snapshot_block.snapshot_id = snapshot.snapshot_id
WHERE snapshot.snapshot_name = 'transactions-before-correction';

-- Storage-pool capacity report.
SELECT
    pool.pool_name,
    ROUND(SUM(disk.capacity_gib), 2) AS total_gib,
    ROUND(
        SUM(
            CASE
                WHEN disk.state <> 'failed'
                THEN disk.capacity_gib
                ELSE 0
            END
        ),
        2
    ) AS usable_gib,
    ROUND(SUM(disk.allocated_gib), 2) AS physical_allocated_gib,
    ROUND(
        SUM(
            CASE
                WHEN disk.state <> 'failed'
                THEN disk.capacity_gib - disk.allocated_gib
                ELSE 0
            END
        ),
        2
    ) AS free_gib
FROM storage_pool pool
JOIN physical_disk disk
  ON disk.pool_id = pool.pool_id
GROUP BY pool.pool_id, pool.pool_name
ORDER BY pool.pool_name;

-- Compare logical capacity with physical allocation to expose thin
-- provisioning behavior.
SELECT
    disk_name,
    provisioning,
    logical_capacity_gib,
    physical_allocated_gib,
    ROUND(
        physical_allocated_gib
        / NULLIF(logical_capacity_gib, 0) * 100,
        2
    ) AS physical_allocation_percent
FROM virtual_disk
ORDER BY disk_name;

-- Find logical blocks whose physical backing is unavailable.
-- This query is intentionally diagnostic: a failed disk does not automatically
-- imply recoverability. Redundancy must exist elsewhere in the architecture.
SELECT
    volume.volume_name,
    block.block_number,
    disk.device_name,
    disk.state
FROM logical_block block
JOIN logical_volume volume
  ON volume.volume_id = block.volume_id
JOIN physical_disk disk
  ON disk.disk_id = block.physical_disk_id
WHERE disk.state = 'failed';

-- Demonstrate a transaction that atomically records a physical allocation
-- and the corresponding virtual-disk accounting.
BEGIN;

WITH selected_disk AS (
    SELECT disk_id
    FROM physical_disk
    WHERE device_name = 'nvme-prod-03'
      AND state = 'online'
      AND capacity_gib - allocated_gib >= 1
    FOR UPDATE
    LIMIT 1
)
UPDATE physical_disk disk
SET allocated_gib = allocated_gib + 1
FROM selected_disk
WHERE disk.disk_id = selected_disk.disk_id;

UPDATE virtual_disk
SET physical_allocated_gib = physical_allocated_gib + 1
WHERE disk_name = 'vd-analytics'
  AND physical_allocated_gib + 1 <= logical_capacity_gib;

INSERT INTO storage_audit
    (operation, pool_id, virtual_disk_id, success, details)
SELECT
    'allocate_block',
    virtual_disk.pool_id,
    virtual_disk.virtual_disk_id,
    TRUE,
    'Allocated one GiB backing extent transactionally'
FROM virtual_disk
WHERE disk_name = 'vd-analytics';

COMMIT;

-- Trigger enforcing that a logical block cannot reference a disk belonging to
-- another storage pool than the virtual disk's pool.
CREATE OR REPLACE FUNCTION validate_block_placement()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    volume_pool_id BIGINT;
    disk_pool_id BIGINT;
BEGIN
    IF NEW.physical_disk_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT vd.pool_id
    INTO volume_pool_id
    FROM logical_volume lv
    JOIN virtual_disk vd
      ON vd.virtual_disk_id = lv.virtual_disk_id
    WHERE lv.volume_id = NEW.volume_id;

    SELECT pool_id
    INTO disk_pool_id
    FROM physical_disk
    WHERE disk_id = NEW.physical_disk_id;

    IF volume_pool_id IS NULL OR disk_pool_id IS NULL THEN
        RAISE EXCEPTION
            'Logical block placement references an unknown storage object';
    END IF;

    IF volume_pool_id <> disk_pool_id THEN
        RAISE EXCEPTION
            'Logical block cannot be placed on a disk from another pool';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_block_placement
BEFORE INSERT OR UPDATE OF physical_disk_id
ON logical_block
FOR EACH ROW
EXECUTE FUNCTION validate_block_placement();

-- Trigger protecting the database from allocation metadata that exceeds the
-- physical disk capacity.
CREATE OR REPLACE FUNCTION validate_disk_allocation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.allocated_gib > NEW.capacity_gib THEN
        RAISE EXCEPTION
            'Allocated physical capacity cannot exceed disk capacity';
    END IF;

    IF NEW.allocated_gib < 0 THEN
        RAISE EXCEPTION
            'Allocated physical capacity cannot be negative';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_disk_allocation
BEFORE INSERT OR UPDATE OF allocated_gib, capacity_gib
ON physical_disk
FOR EACH ROW
EXECUTE FUNCTION validate_disk_allocation();

-- Demonstrate physical-device degradation. The update is valid because a
-- failed disk may still contain historical allocation metadata; usability
-- calculations exclude it from available capacity.
UPDATE physical_disk
SET state = 'failed'
WHERE device_name = 'nvme-prod-03';

INSERT INTO storage_audit
    (operation, disk_id, success, details)
SELECT
    'disk_failure',
    disk_id,
    TRUE,
    'Physical disk transitioned to failed state'
FROM physical_disk
WHERE device_name = 'nvme-prod-03';

-- Post-failure capacity report.
SELECT
    pool.pool_name,
    ROUND(SUM(disk.capacity_gib), 2) AS total_gib,
    ROUND(
        SUM(
            CASE
                WHEN disk.state <> 'failed'
                THEN disk.capacity_gib
                ELSE 0
            END
        ),
        2
    ) AS usable_gib,
    ROUND(SUM(disk.allocated_gib), 2) AS recorded_allocation_gib
FROM storage_pool pool
JOIN physical_disk disk
  ON disk.pool_id = pool.pool_id
GROUP BY pool.pool_name
ORDER BY pool.pool_name;

-- A CTE identifies thin-provisioned disks whose physical allocation has
-- crossed a useful operational threshold. The threshold is a monitoring rule,
-- not a storage-integrity rule.
WITH utilization AS (
    SELECT
        virtual_disk_id,
        disk_name,
        logical_capacity_gib,
        physical_allocated_gib,
        physical_allocated_gib
            / NULLIF(logical_capacity_gib, 0) AS ratio
    FROM virtual_disk
    WHERE provisioning = 'thin'
)
SELECT
    disk_name,
    logical_capacity_gib,
    physical_allocated_gib,
    ROUND(ratio * 100, 2) AS physical_usage_percent,
    CASE
        WHEN ratio >= 0.80 THEN 'capacity planning required'
        WHEN ratio >= 0.60 THEN 'monitor growth'
        ELSE 'normal'
    END AS operational_state
FROM utilization
ORDER BY ratio DESC;

-- Audit trail for the storage workflow.
SELECT
    audit_id,
    operation,
    success,
    details,
    occurred_at
FROM storage_audit
ORDER BY occurred_at, audit_id;
