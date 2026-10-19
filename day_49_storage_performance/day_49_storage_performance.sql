-- PostgreSQL Storage Performance Laboratory
--
-- The model represents:
-- repositories of storage workloads, storage tiers, workload requirements,
-- benchmark observations, cache policies, and tier recommendations.
--
-- PostgreSQL features used here include:
-- primary/foreign keys, CHECK constraints, ENUM types, indexes, views,
-- CTEs, generated calculations, functions, and transactional updates.

DROP SCHEMA IF EXISTS storage_performance CASCADE;
CREATE SCHEMA storage_performance;
SET search_path TO storage_performance;

CREATE TYPE storage_tier AS ENUM (
    'NVME',
    'SSD',
    'HDD',
    'ARCHIVE'
);

CREATE TYPE access_pattern AS ENUM (
    'RANDOM',
    'SEQUENTIAL'
);

CREATE TYPE operation_type AS ENUM (
    'READ',
    'WRITE'
);

CREATE TABLE storage_tier_profile (
    tier storage_tier PRIMARY KEY,
    maximum_iops numeric(14,2) NOT NULL CHECK (maximum_iops > 0),
    throughput_mib_s numeric(14,2) NOT NULL CHECK (throughput_mib_s > 0),
    base_latency_ms numeric(12,4) NOT NULL CHECK (base_latency_ms > 0),
    monthly_cost_per_gib numeric(12,6) NOT NULL CHECK (monthly_cost_per_gib >= 0),
    maximum_capacity_gib numeric(18,2) NOT NULL CHECK (maximum_capacity_gib > 0)
);

INSERT INTO storage_tier_profile
    (tier, maximum_iops, throughput_mib_s, base_latency_ms,
     monthly_cost_per_gib, maximum_capacity_gib)
VALUES
    ('NVME',    900000, 7000,  0.08, 0.120000,   2000),
    ('SSD',     120000, 1200,  0.45, 0.070000,   8000),
    ('HDD',        300,  250,  8.00, 0.025000,  20000),
    ('ARCHIVE',     50,  100, 80.00, 0.008000, 100000);

CREATE TABLE storage_workload (
    workload_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_name text NOT NULL UNIQUE,
    operation operation_type NOT NULL,
    request_size_bytes bigint NOT NULL CHECK (request_size_bytes > 0),
    requests_per_second numeric(14,2) NOT NULL CHECK (requests_per_second > 0),
    latency_target_ms numeric(12,4) NOT NULL CHECK (latency_target_ms > 0),
    capacity_gib numeric(18,2) NOT NULL CHECK (capacity_gib > 0),
    access_pattern access_pattern NOT NULL,
    cacheable boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_workload_pattern
    ON storage_workload (access_pattern, operation);

CREATE INDEX idx_workload_iops
    ON storage_workload (requests_per_second);

INSERT INTO storage_workload
    (workload_name, operation, request_size_bytes,
     requests_per_second, latency_target_ms, capacity_gib,
     access_pattern, cacheable)
VALUES
    ('Payment OLTP', 'READ', 4096, 75000, 2.0, 500, 'RANDOM', true),
    ('Warehouse Scan', 'READ', 1048576, 800, 25.0, 4000, 'SEQUENTIAL', false),
    ('Nightly Backup', 'WRITE', 4194304, 50, 200.0, 10000, 'SEQUENTIAL', false),
    ('Compliance Archive', 'WRITE', 1048576, 2, 500.0, 50000, 'SEQUENTIAL', false),
    ('Product Catalog Cache', 'READ', 16384, 25000, 5.0, 300, 'RANDOM', true);

CREATE TABLE benchmark_run (
    benchmark_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_id bigint NOT NULL
        REFERENCES storage_workload(workload_id)
        ON DELETE CASCADE,
    tier storage_tier NOT NULL
        REFERENCES storage_tier_profile(tier),
    queue_depth integer NOT NULL CHECK (queue_depth > 0),
    measured_iops numeric(14,2) NOT NULL CHECK (measured_iops >= 0),
    measured_throughput_mib_s numeric(14,2) NOT NULL CHECK (measured_throughput_mib_s >= 0),
    average_latency_ms numeric(12,4) NOT NULL CHECK (average_latency_ms >= 0),
    p95_latency_ms numeric(12,4) NOT NULL CHECK (p95_latency_ms >= 0),
    p99_latency_ms numeric(12,4) NOT NULL CHECK (p99_latency_ms >= 0),
    cache_hit_rate numeric(6,5) NOT NULL
        CHECK (cache_hit_rate BETWEEN 0 AND 1),
    measured_at timestamptz NOT NULL DEFAULT now(),

    CHECK (p95_latency_ms >= average_latency_ms),
    CHECK (p99_latency_ms >= p95_latency_ms)
);

CREATE INDEX idx_benchmark_workload_tier
    ON benchmark_run (workload_id, tier, measured_at DESC);

CREATE TABLE cache_policy (
    cache_policy_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_id bigint NOT NULL UNIQUE
        REFERENCES storage_workload(workload_id)
        ON DELETE CASCADE,
    cache_capacity_gib numeric(12,3) NOT NULL
        CHECK (cache_capacity_gib > 0),
    eviction_policy text NOT NULL
        CHECK (eviction_policy IN ('LRU', 'LFU', 'FIFO')),
    write_policy text NOT NULL
        CHECK (write_policy IN ('WRITE_THROUGH', 'WRITE_BACK')),
    minimum_hit_rate numeric(6,5) NOT NULL
        CHECK (minimum_hit_rate BETWEEN 0 AND 1)
);

INSERT INTO cache_policy
    (workload_id, cache_capacity_gib, eviction_policy,
     write_policy, minimum_hit_rate)
SELECT
    workload_id,
    CASE workload_name
        WHEN 'Payment OLTP' THEN 32
        WHEN 'Product Catalog Cache' THEN 64
        ELSE 8
    END,
    'LRU',
    'WRITE_THROUGH',
    0.80
FROM storage_workload
WHERE cacheable = true;

CREATE TABLE tier_recommendation (
    recommendation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_id bigint NOT NULL
        REFERENCES storage_workload(workload_id)
        ON DELETE CASCADE,
    tier storage_tier NOT NULL
        REFERENCES storage_tier_profile(tier),
    sustainable_iops numeric(14,2) NOT NULL CHECK (sustainable_iops > 0),
    estimated_latency_ms numeric(12,4) NOT NULL CHECK (estimated_latency_ms > 0),
    estimated_monthly_cost numeric(18,4) NOT NULL CHECK (estimated_monthly_cost >= 0),
    acceptable boolean NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workload_id, tier)
);

CREATE OR REPLACE FUNCTION estimate_sustainable_iops(
    p_request_size_bytes bigint,
    p_tier storage_tier
)
RETURNS numeric
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    p_profile storage_tier_profile;
    bandwidth_iops numeric;
BEGIN
    IF p_request_size_bytes <= 0 THEN
        RAISE EXCEPTION 'Request size must be positive';
    END IF;

    SELECT *
    INTO p_profile
    FROM storage_tier_profile
    WHERE tier = p_tier;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown storage tier: %', p_tier;
    END IF;

    bandwidth_iops :=
        p_profile.throughput_mib_s * 1024 * 1024
        / p_request_size_bytes;

    RETURN LEAST(
        p_profile.maximum_iops,
        bandwidth_iops
    );
END;
$$;

CREATE OR REPLACE FUNCTION populate_tier_recommendations()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO tier_recommendation (
        workload_id,
        tier,
        sustainable_iops,
        estimated_latency_ms,
        estimated_monthly_cost,
        acceptable
    )
    SELECT
        w.workload_id,
        p.tier,
        estimate_sustainable_iops(
            w.request_size_bytes,
            p.tier
        ),
        p.base_latency_ms
            + 1000 / estimate_sustainable_iops(
                w.request_size_bytes,
                p.tier
            ),
        w.capacity_gib * p.monthly_cost_per_gib,
        (
            w.requests_per_second
                <= estimate_sustainable_iops(
                    w.request_size_bytes,
                    p.tier
                )
            AND
            p.base_latency_ms
                + 1000 / estimate_sustainable_iops(
                    w.request_size_bytes,
                    p.tier
                )
                <= w.latency_target_ms
        )
    FROM storage_workload w
    CROSS JOIN storage_tier_profile p
    ON CONFLICT (workload_id, tier)
    DO UPDATE SET
        sustainable_iops = EXCLUDED.sustainable_iops,
        estimated_latency_ms = EXCLUDED.estimated_latency_ms,
        estimated_monthly_cost = EXCLUDED.estimated_monthly_cost,
        acceptable = EXCLUDED.acceptable,
        generated_at = now();
END;
$$;

SELECT populate_tier_recommendations();

CREATE VIEW workload_tier_analysis AS
SELECT
    w.workload_name,
    w.operation,
    w.access_pattern,
    p.tier,
    r.sustainable_iops,
    r.estimated_latency_ms,
    w.latency_target_ms,
    w.requests_per_second AS required_iops,
    r.estimated_monthly_cost,
    r.acceptable
FROM storage_workload w
JOIN tier_recommendation r
    ON r.workload_id = w.workload_id
JOIN storage_tier_profile p
    ON p.tier = r.tier;

SELECT *
FROM workload_tier_analysis
ORDER BY workload_name, estimated_monthly_cost;

-- The cheapest tier satisfying both the request-rate and latency targets
-- is selected. This is intentionally a policy query rather than a simple
-- "fastest device wins" rule.
WITH ranked AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY workload_name
            ORDER BY estimated_monthly_cost
        ) AS cost_rank
    FROM workload_tier_analysis
    WHERE acceptable
)
SELECT
    workload_name,
    tier,
    sustainable_iops,
    estimated_latency_ms,
    estimated_monthly_cost
FROM ranked
WHERE cost_rank = 1
ORDER BY workload_name;

-- Identify workloads for which no configured tier satisfies the declared
-- performance requirements.
SELECT
    w.workload_name,
    w.requests_per_second,
    w.latency_target_ms
FROM storage_workload w
WHERE NOT EXISTS (
    SELECT 1
    FROM tier_recommendation r
    WHERE r.workload_id = w.workload_id
      AND r.acceptable
);

-- Benchmark observations expose the difference between a theoretical
-- capacity model and observed performance.
INSERT INTO benchmark_run (
    workload_id,
    tier,
    queue_depth,
    measured_iops,
    measured_throughput_mib_s,
    average_latency_ms,
    p95_latency_ms,
    p99_latency_ms,
    cache_hit_rate
)
SELECT
    workload_id,
    'SSD',
    32,
    68000,
    266,
    0.74,
    1.42,
    2.80,
    0.91
FROM storage_workload
WHERE workload_name = 'Payment OLTP';

INSERT INTO benchmark_run (
    workload_id,
    tier,
    queue_depth,
    measured_iops,
    measured_throughput_mib_s,
    average_latency_ms,
    p95_latency_ms,
    p99_latency_ms,
    cache_hit_rate
)
SELECT
    workload_id,
    'HDD',
    8,
    280,
    240,
    8.8,
    15.4,
    22.7,
    0.02
FROM storage_workload
WHERE workload_name = 'Warehouse Scan';

-- Compare measured performance with declared requirements.
SELECT
    w.workload_name,
    b.tier,
    b.queue_depth,
    b.measured_iops,
    w.requests_per_second AS required_iops,
    b.p99_latency_ms,
    w.latency_target_ms,
    b.cache_hit_rate,
    CASE
        WHEN b.measured_iops >= w.requests_per_second
         AND b.p99_latency_ms <= w.latency_target_ms
        THEN 'MEETS_TARGET'
        ELSE 'VIOLATES_TARGET'
    END AS performance_status
FROM benchmark_run b
JOIN storage_workload w
    ON w.workload_id = b.workload_id
ORDER BY b.measured_at DESC;

-- Tail latency can reveal saturation that average latency hides.
SELECT
    w.workload_name,
    b.tier,
    ROUND(AVG(b.average_latency_ms), 3) AS average_latency_ms,
    ROUND(MAX(b.p95_latency_ms), 3) AS worst_p95_ms,
    ROUND(MAX(b.p99_latency_ms), 3) AS worst_p99_ms
FROM benchmark_run b
JOIN storage_workload w
    ON w.workload_id = b.workload_id
GROUP BY w.workload_name, b.tier
ORDER BY worst_p99_ms DESC;

-- Cache effectiveness analysis.
SELECT
    w.workload_name,
    cp.eviction_policy,
    cp.write_policy,
    cp.cache_capacity_gib,
    b.cache_hit_rate,
    CASE
        WHEN b.cache_hit_rate >= cp.minimum_hit_rate
        THEN 'CACHE_POLICY_SATISFIED'
        ELSE 'CACHE_POLICY_MISSED'
    END AS cache_status
FROM cache_policy cp
JOIN storage_workload w
    ON w.workload_id = cp.workload_id
LEFT JOIN LATERAL (
    SELECT cache_hit_rate
    FROM benchmark_run
    WHERE benchmark_run.workload_id = cp.workload_id
    ORDER BY measured_at DESC
    LIMIT 1
) b ON true
ORDER BY w.workload_name;

-- Transactional policy update. The change is committed only after the
-- resulting configuration satisfies the database constraints.
BEGIN;

UPDATE storage_workload
SET latency_target_ms = 3.0
WHERE workload_name = 'Payment OLTP';

SELECT populate_tier_recommendations();

COMMIT;

-- Demonstrate the updated recommendation after the transactional change.
SELECT
    workload_name,
    tier,
    estimated_latency_ms,
    estimated_monthly_cost,
    acceptable
FROM workload_tier_analysis
WHERE workload_name = 'Payment OLTP'
ORDER BY estimated_monthly_cost;

-- This query exposes the storage-performance bottleneck classification.
SELECT
    workload_name,
    tier,
    CASE
        WHEN required_iops > sustainable_iops
            THEN 'IOPS_LIMITED'
        WHEN estimated_latency_ms > latency_target_ms
            THEN 'LATENCY_LIMITED'
        WHEN access_pattern = 'SEQUENTIAL'
            THEN 'BANDWIDTH_OR_SEQUENTIAL_WORKLOAD'
        ELSE 'WITHIN_MODELED_LIMITS'
    END AS bottleneck_class
FROM workload_tier_analysis
ORDER BY workload_name, tier;
