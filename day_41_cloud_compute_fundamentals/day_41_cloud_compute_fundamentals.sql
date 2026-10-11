-- PostgreSQL 15+
-- Cloud compute catalog, provisioning requests, resource allocations,
-- instance lifecycle, capacity reporting, and compute cost estimation.

BEGIN;

DROP VIEW IF EXISTS cloud_compute_capacity;
DROP VIEW IF EXISTS cloud_running_instance_inventory;
DROP TABLE IF EXISTS compute_cost_records CASCADE;
DROP TABLE IF EXISTS resource_allocations CASCADE;
DROP TABLE IF EXISTS compute_instances CASCADE;
DROP TABLE IF EXISTS provisioning_requests CASCADE;
DROP TABLE IF EXISTS physical_hosts CASCADE;
DROP TABLE IF EXISTS instance_types CASCADE;

CREATE TABLE instance_types (
    instance_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type_name TEXT NOT NULL UNIQUE,
    family TEXT NOT NULL CHECK (
        family IN (
            'general-purpose',
            'compute-optimized',
            'memory-optimized',
            'burstable',
            'accelerated'
        )
    ),
    architecture TEXT NOT NULL CHECK (
        architecture IN ('x86_64', 'arm64')
    ),
    vcpus INTEGER NOT NULL CHECK (vcpus > 0),
    memory_gib NUMERIC(10, 2) NOT NULL CHECK (memory_gib > 0),
    hourly_rate NUMERIC(12, 6) NOT NULL CHECK (hourly_rate >= 0),
    network_gbps NUMERIC(10, 2) NOT NULL CHECK (network_gbps > 0),
    local_storage_gib INTEGER NOT NULL DEFAULT 0
        CHECK (local_storage_gib >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE physical_hosts (
    host_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    host_name TEXT NOT NULL UNIQUE,
    total_vcpus INTEGER NOT NULL CHECK (total_vcpus > 0),
    total_memory_gib NUMERIC(10, 2) NOT NULL
        CHECK (total_memory_gib > 0),
    architecture TEXT NOT NULL CHECK (
        architecture IN ('x86_64', 'arm64')
    ),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE provisioning_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_name TEXT NOT NULL CHECK (length(trim(workload_name)) > 0),
    requested_vcpus INTEGER NOT NULL CHECK (requested_vcpus > 0),
    requested_memory_gib NUMERIC(10, 2) NOT NULL
        CHECK (requested_memory_gib > 0),
    max_hourly_rate NUMERIC(12, 6) NOT NULL
        CHECK (max_hourly_rate >= 0),
    required_family TEXT CHECK (
        required_family IS NULL OR required_family IN (
            'general-purpose',
            'compute-optimized',
            'memory-optimized',
            'burstable',
            'accelerated'
        )
    ),
    required_architecture TEXT NOT NULL DEFAULT 'x86_64'
        CHECK (required_architecture IN ('x86_64', 'arm64')),
    request_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            request_status IN (
                'pending', 'provisioned', 'rejected', 'cancelled'
            )
        ),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ
);

CREATE TABLE compute_instances (
    instance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_name TEXT NOT NULL UNIQUE,
    request_id BIGINT UNIQUE
        REFERENCES provisioning_requests(request_id),
    instance_type_id BIGINT NOT NULL
        REFERENCES instance_types(instance_type_id),
    workload_name TEXT NOT NULL CHECK (length(trim(workload_name)) > 0),
    lifecycle_state TEXT NOT NULL DEFAULT 'requested'
        CHECK (
            lifecycle_state IN (
                'requested',
                'provisioning',
                'running',
                'stopped',
                'terminated',
                'failed'
            )
        ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    terminated_at TIMESTAMPTZ,
    tags JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(tags) = 'object'),
    CHECK (
        (lifecycle_state = 'terminated' AND terminated_at IS NOT NULL)
        OR
        (lifecycle_state <> 'terminated' AND terminated_at IS NULL)
    )
);

-- One row represents the current host reservation for a running instance.
-- Releasing the row releases both vCPU and memory capacity in the views.
CREATE TABLE resource_allocations (
    allocation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_id BIGINT NOT NULL UNIQUE
        REFERENCES compute_instances(instance_id),
    host_id BIGINT NOT NULL REFERENCES physical_hosts(host_id),
    allocated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (instance_id, host_id)
);

CREATE TABLE compute_cost_records (
    cost_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_id BIGINT NOT NULL
        REFERENCES compute_instances(instance_id),
    usage_start TIMESTAMPTZ NOT NULL,
    usage_end TIMESTAMPTZ NOT NULL,
    hourly_rate NUMERIC(12, 6) NOT NULL CHECK (hourly_rate >= 0),
    billed_hours NUMERIC(12, 4) NOT NULL CHECK (billed_hours >= 0),
    amount NUMERIC(14, 4) GENERATED ALWAYS AS (
        hourly_rate * billed_hours
    ) STORED,
    CHECK (usage_end >= usage_start)
);

CREATE INDEX idx_instance_state
    ON compute_instances(lifecycle_state);

CREATE INDEX idx_allocations_host
    ON resource_allocations(host_id);

CREATE INDEX idx_cost_usage_start
    ON compute_cost_records(usage_start);

CREATE INDEX idx_instance_tags
    ON compute_instances USING GIN(tags);

INSERT INTO instance_types
    (type_name, family, architecture, vcpus, memory_gib,
     hourly_rate, network_gbps, local_storage_gib)
VALUES
    ('general-medium', 'general-purpose', 'x86_64',
     4, 16, 0.160000, 10, 0),
    ('cpu-large', 'compute-optimized', 'x86_64',
     8, 16, 0.240000, 15, 0),
    ('memory-large', 'memory-optimized', 'x86_64',
     4, 32, 0.220000, 10, 0),
    ('burst-small', 'burstable', 'arm64',
     2, 4, 0.035000, 2, 0),
    ('gpu-large', 'accelerated', 'x86_64',
     8, 32, 1.200000, 25, 100);

INSERT INTO physical_hosts
    (host_name, total_vcpus, total_memory_gib, architecture)
VALUES
    ('compute-node-a', 16, 64, 'x86_64'),
    ('compute-node-b', 8, 32, 'x86_64'),
    ('compute-node-c', 8, 32, 'arm64');

INSERT INTO provisioning_requests
    (workload_name, requested_vcpus, requested_memory_gib,
     max_hourly_rate, required_family, required_architecture)
VALUES
    ('orders-database', 4, 24, 0.300000,
     'memory-optimized', 'x86_64'),
    ('orders-api', 4, 12, 0.200000,
     'general-purpose', 'x86_64'),
    ('nightly-analytics', 8, 16, 0.300000,
     'compute-optimized', 'x86_64'),
    ('experimental-gpu', 8, 32, 0.500000,
     'accelerated', 'x86_64');

-- Show catalog entries that satisfy each request's declared resource,
-- architecture, family, and budget requirements.
SELECT
    r.request_id,
    r.workload_name,
    t.type_name,
    t.vcpus,
    t.memory_gib,
    t.hourly_rate
FROM provisioning_requests AS r
JOIN instance_types AS t
    ON t.vcpus >= r.requested_vcpus
   AND t.memory_gib >= r.requested_memory_gib
   AND t.hourly_rate <= r.max_hourly_rate
   AND t.architecture = r.required_architecture
   AND (r.required_family IS NULL OR t.family = r.required_family)
ORDER BY r.request_id, t.hourly_rate, t.type_name;

-- Provision two instances with explicit, catalog-backed type assignments.
WITH selected_types AS (
    SELECT
        r.request_id,
        r.workload_name,
        t.instance_type_id,
        row_number() OVER (
            PARTITION BY r.request_id
            ORDER BY t.hourly_rate, t.vcpus, t.memory_gib
        ) AS choice_rank
    FROM provisioning_requests AS r
    JOIN instance_types AS t
        ON t.vcpus >= r.requested_vcpus
       AND t.memory_gib >= r.requested_memory_gib
       AND t.hourly_rate <= r.max_hourly_rate
       AND t.architecture = r.required_architecture
       AND (r.required_family IS NULL OR t.family = r.required_family)
    WHERE r.workload_name IN ('orders-database', 'orders-api')
)
INSERT INTO compute_instances
    (instance_name, request_id, instance_type_id,
     workload_name, lifecycle_state, tags)
SELECT
    'vm-' || s.request_id,
    s.request_id,
    s.instance_type_id,
    s.workload_name,
    'running',
    jsonb_build_object(
        'environment', 'production',
        'managed_by', 'compute-control-plane'
    )
FROM selected_types AS s
WHERE s.choice_rank = 1
ON CONFLICT (instance_name) DO NOTHING;

UPDATE provisioning_requests AS r
SET request_status = 'provisioned',
    processed_at = CURRENT_TIMESTAMP
WHERE EXISTS (
    SELECT 1
    FROM compute_instances AS i
    WHERE i.request_id = r.request_id
);

UPDATE provisioning_requests AS r
SET request_status = 'rejected',
    processed_at = CURRENT_TIMESTAMP
WHERE r.request_status = 'pending'
  AND NOT EXISTS (
      SELECT 1
      FROM compute_instances AS i
      WHERE i.request_id = r.request_id
  );

UPDATE compute_instances
SET started_at = CURRENT_TIMESTAMP
WHERE lifecycle_state = 'running'
  AND started_at IS NULL;

-- Deterministic placement is suitable for this demonstration. A production
-- scheduler must serialize competing placements or lock host rows before
-- making allocation decisions to avoid concurrent overcommit.
WITH candidate_placements AS (
    SELECT
        i.instance_id,
        h.host_id,
        row_number() OVER (
            PARTITION BY i.instance_id
            ORDER BY h.host_id
        ) AS host_rank
    FROM compute_instances AS i
    JOIN instance_types AS t
        ON t.instance_type_id = i.instance_type_id
    JOIN physical_hosts AS h
        ON h.architecture = t.architecture
       AND h.enabled
    WHERE i.lifecycle_state = 'running'
      AND NOT EXISTS (
          SELECT 1
          FROM resource_allocations AS existing
          WHERE existing.instance_id = i.instance_id
      )
      AND t.vcpus <= h.total_vcpus
      AND t.memory_gib <= h.total_memory_gib
)
INSERT INTO resource_allocations (instance_id, host_id)
SELECT instance_id, host_id
FROM candidate_placements
WHERE host_rank = 1
ON CONFLICT (instance_id) DO NOTHING;

-- Report the current resource reservations per host.
CREATE VIEW cloud_compute_capacity AS
SELECT
    h.host_id,
    h.host_name,
    h.architecture,
    h.enabled,
    h.total_vcpus,
    COALESCE(SUM(t.vcpus), 0)::BIGINT AS used_vcpus,
    h.total_vcpus - COALESCE(SUM(t.vcpus), 0)::INTEGER AS free_vcpus,
    h.total_memory_gib,
    COALESCE(SUM(t.memory_gib), 0)::NUMERIC(10, 2) AS used_memory_gib,
    h.total_memory_gib -
        COALESCE(SUM(t.memory_gib), 0)::NUMERIC(10, 2) AS free_memory_gib
FROM physical_hosts AS h
LEFT JOIN resource_allocations AS a ON a.host_id = h.host_id
LEFT JOIN compute_instances AS i
    ON i.instance_id = a.instance_id
   AND i.lifecycle_state = 'running'
LEFT JOIN instance_types AS t
    ON t.instance_type_id = i.instance_type_id
GROUP BY
    h.host_id,
    h.host_name,
    h.architecture,
    h.enabled,
    h.total_vcpus,
    h.total_memory_gib;

CREATE VIEW cloud_running_instance_inventory AS
SELECT
    i.instance_id,
    i.instance_name,
    i.workload_name,
    i.lifecycle_state,
    t.type_name,
    t.family,
    t.vcpus,
    t.memory_gib,
    t.hourly_rate,
    h.host_name,
    i.tags
FROM compute_instances AS i
JOIN instance_types AS t
    ON t.instance_type_id = i.instance_type_id
LEFT JOIN resource_allocations AS a
    ON a.instance_id = i.instance_id
LEFT JOIN physical_hosts AS h
    ON h.host_id = a.host_id;

SELECT * FROM cloud_running_instance_inventory ORDER BY instance_id;
SELECT * FROM cloud_compute_capacity ORDER BY host_id;

-- Cost projections use 730 hours as a planning convention, not a guarantee
-- of billed hours. Real bills depend on provider metering and pricing rules.
SELECT
    type_name,
    hourly_rate,
    round(hourly_rate * 8, 2) AS eight_hour_cost,
    round(hourly_rate * 730, 2) AS estimated_monthly_cost,
    round(hourly_rate * 8760, 2) AS estimated_annual_cost
FROM instance_types
ORDER BY hourly_rate;

-- Persist a sample eight-hour usage interval for a running instance.
INSERT INTO compute_cost_records
    (instance_id, usage_start, usage_end, hourly_rate, billed_hours)
SELECT
    i.instance_id,
    CURRENT_TIMESTAMP - INTERVAL '8 hours',
    CURRENT_TIMESTAMP,
    t.hourly_rate,
    8
FROM compute_instances AS i
JOIN instance_types AS t
    ON t.instance_type_id = i.instance_type_id
WHERE i.workload_name = 'orders-api'
  AND i.lifecycle_state = 'running';

SELECT
    i.workload_name,
    SUM(c.billed_hours) AS billed_hours,
    SUM(c.amount) AS compute_cost
FROM compute_cost_records AS c
JOIN compute_instances AS i
    ON i.instance_id = c.instance_id
GROUP BY i.workload_name
ORDER BY i.workload_name;

-- Stop the API instance and release its reservation atomically.
BEGIN;

WITH stopped AS (
    UPDATE compute_instances
    SET lifecycle_state = 'stopped'
    WHERE workload_name = 'orders-api'
      AND lifecycle_state = 'running'
    RETURNING instance_id
)
DELETE FROM resource_allocations AS a
USING stopped AS s
WHERE a.instance_id = s.instance_id;

COMMIT;

SELECT * FROM cloud_compute_capacity ORDER BY host_id;

-- The following examples intentionally remain comments because each would
-- abort its transaction when the relevant constraint is violated.
--
-- Invalid catalog resource size:
-- INSERT INTO instance_types
-- (type_name, family, architecture, vcpus, memory_gib,
--  hourly_rate, network_gbps)
-- VALUES ('invalid-size', 'general-purpose', 'x86_64',
--         0, 8, 0.05, 2);
--
-- Invalid lifecycle state:
-- UPDATE compute_instances
-- SET lifecycle_state = 'migrating'
-- WHERE instance_id = 1;
--
-- Production enforcement should additionally use triggers or controlled
-- stored procedures to verify that every allocation matches instance
-- architecture, capacity, and lifecycle state under concurrent transactions.

COMMIT;
