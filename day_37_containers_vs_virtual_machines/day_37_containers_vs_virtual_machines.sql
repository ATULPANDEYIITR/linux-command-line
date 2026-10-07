-- Containers vs Virtual Machines
--
-- PostgreSQL-compatible relational model for evaluating workload placement.
--
-- The schema deliberately separates:
--   workload requirements
--   runtime technologies
--   host capacity
--   deployment estimates
--   portability requirements
--   security requirements
--   and placement decisions.
--
-- The database enforces data integrity through primary keys, foreign keys,
-- CHECK constraints, UNIQUE constraints, and indexes.
--
-- Numerical values are illustrative architectural assumptions rather than
-- universal performance benchmarks.

DROP SCHEMA IF EXISTS container_vm_lab CASCADE;

CREATE SCHEMA container_vm_lab;

SET search_path TO container_vm_lab;

CREATE TYPE deployment_type AS ENUM (
    'CONTAINER',
    'VIRTUAL_MACHINE'
);

CREATE TYPE workload_type AS ENUM (
    'MICROSERVICE',
    'DATABASE',
    'LEGACY_APPLICATION',
    'BATCH_PROCESS'
);

CREATE TYPE decision_status AS ENUM (
    'APPROVED',
    'REJECTED'
);

CREATE TABLE hosts (
    host_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    host_name TEXT NOT NULL UNIQUE,
    host_os TEXT NOT NULL,
    kernel_version TEXT NOT NULL,
    cpu_cores NUMERIC(8,2) NOT NULL CHECK (cpu_cores > 0),
    memory_gib NUMERIC(10,2) NOT NULL CHECK (memory_gib > 0),
    storage_gib NUMERIC(12,2) NOT NULL CHECK (storage_gib > 0),
    CHECK (length(trim(host_name)) > 0)
);

CREATE TABLE runtime_profiles (
    runtime_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    runtime_type deployment_type NOT NULL UNIQUE,
    runtime_name TEXT NOT NULL UNIQUE,
    shares_host_kernel BOOLEAN NOT NULL,
    has_guest_kernel BOOLEAN NOT NULL,
    has_virtual_hardware_boundary BOOLEAN NOT NULL,
    isolation_score NUMERIC(4,3) NOT NULL
        CHECK (isolation_score BETWEEN 0 AND 1),
    memory_overhead_mib NUMERIC(10,2) NOT NULL
        CHECK (memory_overhead_mib >= 0),
    cpu_overhead_percent NUMERIC(6,2) NOT NULL
        CHECK (cpu_overhead_percent >= 0),
    startup_seconds NUMERIC(10,2) NOT NULL
        CHECK (startup_seconds >= 0),
    storage_overhead_gib NUMERIC(10,2) NOT NULL
        CHECK (storage_overhead_gib >= 0),
    requires_compatible_host_kernel BOOLEAN NOT NULL
);

CREATE TABLE workloads (
    workload_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_name TEXT NOT NULL UNIQUE,
    workload_type workload_type NOT NULL,
    requested_cpu_cores NUMERIC(8,2) NOT NULL
        CHECK (requested_cpu_cores > 0),
    requested_memory_gib NUMERIC(10,2) NOT NULL
        CHECK (requested_memory_gib > 0),
    requested_storage_gib NUMERIC(12,2) NOT NULL
        CHECK (requested_storage_gib > 0),
    requires_strong_isolation BOOLEAN NOT NULL DEFAULT FALSE,
    requires_specific_guest_os BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (length(trim(workload_name)) > 0)
);

CREATE TABLE runtime_host_compatibility (
    runtime_id BIGINT NOT NULL
        REFERENCES runtime_profiles(runtime_id)
        ON DELETE CASCADE,
    host_id BIGINT NOT NULL
        REFERENCES hosts(host_id)
        ON DELETE CASCADE,
    compatible BOOLEAN NOT NULL,
    compatibility_reason TEXT NOT NULL,
    PRIMARY KEY (runtime_id, host_id)
);

CREATE TABLE placement_rules (
    rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_name TEXT NOT NULL UNIQUE,
    rule_type TEXT NOT NULL,
    description TEXT NOT NULL,
    CHECK (length(trim(rule_name)) > 0),
    CHECK (length(trim(description)) > 0)
);

CREATE TABLE workload_placement_policies (
    workload_id BIGINT NOT NULL
        REFERENCES workloads(workload_id)
        ON DELETE CASCADE,
    rule_id BIGINT NOT NULL
        REFERENCES placement_rules(rule_id)
        ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (workload_id, rule_id)
);

CREATE TABLE deployment_estimates (
    estimate_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_id BIGINT NOT NULL
        REFERENCES workloads(workload_id)
        ON DELETE CASCADE,
    runtime_id BIGINT NOT NULL
        REFERENCES runtime_profiles(runtime_id)
        ON DELETE RESTRICT,
    host_id BIGINT NOT NULL
        REFERENCES hosts(host_id)
        ON DELETE RESTRICT,
    instance_count INTEGER NOT NULL CHECK (instance_count > 0),
    estimated_cpu_cores NUMERIC(12,2) NOT NULL
        CHECK (estimated_cpu_cores >= 0),
    estimated_memory_gib NUMERIC(12,2) NOT NULL
        CHECK (estimated_memory_gib >= 0),
    estimated_storage_gib NUMERIC(12,2) NOT NULL
        CHECK (estimated_storage_gib >= 0),
    memory_utilization_percent NUMERIC(8,2) NOT NULL,
    cpu_utilization_percent NUMERIC(8,2) NOT NULL,
    storage_utilization_percent NUMERIC(8,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE placement_decisions (
    decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_id BIGINT NOT NULL
        REFERENCES workloads(workload_id)
        ON DELETE CASCADE,
    runtime_id BIGINT NOT NULL
        REFERENCES runtime_profiles(runtime_id)
        ON DELETE RESTRICT,
    host_id BIGINT NOT NULL
        REFERENCES hosts(host_id)
        ON DELETE RESTRICT,
    estimate_id BIGINT
        REFERENCES deployment_estimates(estimate_id)
        ON DELETE SET NULL,
    status decision_status NOT NULL,
    decision_reason TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workloads_type
    ON workloads(workload_type);

CREATE INDEX idx_estimates_workload
    ON deployment_estimates(workload_id);

CREATE INDEX idx_estimates_runtime
    ON deployment_estimates(runtime_id);

CREATE INDEX idx_decisions_status
    ON placement_decisions(status);

CREATE INDEX idx_compatibility_host
    ON runtime_host_compatibility(host_id);

INSERT INTO hosts (
    host_name,
    host_os,
    kernel_version,
    cpu_cores,
    memory_gib,
    storage_gib
)
VALUES
    (
        'linux-production-01',
        'Linux',
        '6.12',
        16,
        64,
        500
    ),
    (
        'windows-virtualization-01',
        'Windows Server',
        '2025',
        32,
        128,
        1000
    ),
    (
        'linux-high-memory-01',
        'Linux',
        '6.8',
        32,
        128,
        1000
    );

INSERT INTO runtime_profiles (
    runtime_type,
    runtime_name,
    shares_host_kernel,
    has_guest_kernel,
    has_virtual_hardware_boundary,
    isolation_score,
    memory_overhead_mib,
    cpu_overhead_percent,
    startup_seconds,
    storage_overhead_gib,
    requires_compatible_host_kernel
)
VALUES
    (
        'CONTAINER',
        'Container',
        TRUE,
        FALSE,
        FALSE,
        0.720,
        80,
        2.00,
        0.80,
        0.15,
        TRUE
    ),
    (
        'VIRTUAL_MACHINE',
        'Virtual Machine',
        FALSE,
        TRUE,
        TRUE,
        0.960,
        900,
        7.00,
        25.00,
        8.00,
        FALSE
    );

INSERT INTO workloads (
    workload_name,
    workload_type,
    requested_cpu_cores,
    requested_memory_gib,
    requested_storage_gib,
    requires_strong_isolation,
    requires_specific_guest_os
)
VALUES
    (
        'Payment API',
        'MICROSERVICE',
        0.25,
        1,
        0.20,
        FALSE,
        FALSE
    ),
    (
        'Transactional Database',
        'DATABASE',
        2,
        8,
        20,
        TRUE,
        FALSE
    ),
    (
        'Legacy ERP Connector',
        'LEGACY_APPLICATION',
        1.5,
        4,
        8,
        TRUE,
        TRUE
    ),
    (
        'Nightly Analytics Batch',
        'BATCH_PROCESS',
        2,
        6,
        15,
        FALSE,
        FALSE
    );

INSERT INTO runtime_host_compatibility (
    runtime_id,
    host_id,
    compatible,
    compatibility_reason
)
SELECT
    runtime.runtime_id,
    host.host_id,
    CASE
        WHEN runtime.runtime_type = 'VIRTUAL_MACHINE'
            THEN TRUE
        WHEN runtime.runtime_type = 'CONTAINER'
             AND host.host_os = 'Linux'
            THEN TRUE
        ELSE FALSE
    END,
    CASE
        WHEN runtime.runtime_type = 'VIRTUAL_MACHINE'
            THEN 'Guest kernel and OS are carried by the VM.'
        WHEN runtime.runtime_type = 'CONTAINER'
             AND host.host_os = 'Linux'
            THEN 'Host provides compatible Linux kernel facilities.'
        ELSE
            'The simplified model does not treat this host as providing '
            || 'the required container kernel environment.'
    END
FROM runtime_profiles runtime
CROSS JOIN hosts host;

INSERT INTO placement_rules (
    rule_name,
    rule_type,
    description
)
VALUES
    (
        'strong-isolation',
        'ISOLATION',
        'Workloads requiring strong isolation must use a runtime with isolation score at least 0.90.'
    ),
    (
        'guest-os',
        'GUEST_OS',
        'Workloads requiring a specific guest operating system must use a VM.'
    ),
    (
        'host-compatibility',
        'COMPATIBILITY',
        'The selected runtime must be compatible with the target host.'
    ),
    (
        'resource-capacity',
        'CAPACITY',
        'Estimated resource usage must not exceed host capacity.'
    );

INSERT INTO workload_placement_policies (
    workload_id,
    rule_id
)
SELECT
    workload.workload_id,
    rule.rule_id
FROM workloads workload
CROSS JOIN placement_rules rule;

-- The following CTE calculates the same resource model used by the
-- application examples:
--
-- application memory + runtime memory overhead
-- application CPU * (1 + runtime CPU overhead)
-- application storage + runtime storage overhead
--
-- It demonstrates SQL-specific relational calculation rather than simply
-- storing precomputed values.

WITH candidate AS (
    SELECT
        w.workload_id,
        w.workload_name,
        r.runtime_id,
        r.runtime_name,
        h.host_id,
        h.host_name,
        30 AS instance_count,
        (
            30 * (
                w.requested_memory_gib
                + r.memory_overhead_mib / 1024.0
            )
        ) AS estimated_memory_gib,
        (
            30 * w.requested_cpu_cores
            * (1 + r.cpu_overhead_percent / 100.0)
        ) AS estimated_cpu_cores,
        (
            30 * (
                w.requested_storage_gib
                + r.storage_overhead_gib
            )
        ) AS estimated_storage_gib,
        h.memory_gib,
        h.cpu_cores,
        h.storage_gib
    FROM workloads w
    CROSS JOIN runtime_profiles r
    JOIN hosts h
        ON h.host_name = 'linux-production-01'
)
SELECT
    workload_name,
    runtime_name,
    host_name,
    estimated_memory_gib,
    estimated_cpu_cores,
    estimated_storage_gib,
    ROUND(
        estimated_memory_gib / memory_gib * 100,
        2
    ) AS memory_utilization_percent,
    ROUND(
        estimated_cpu_cores / cpu_cores * 100,
        2
    ) AS cpu_utilization_percent,
    ROUND(
        estimated_storage_gib / storage_gib * 100,
        2
    ) AS storage_utilization_percent
FROM candidate
ORDER BY workload_name, runtime_name;

-- Portability query: the relational model makes the kernel dependency
-- explicit instead of treating an application image as universally portable.

SELECT
    r.runtime_name,
    COUNT(*) FILTER (WHERE c.compatible) AS compatible_hosts,
    COUNT(*) AS evaluated_hosts,
    ROUND(
        COUNT(*) FILTER (WHERE c.compatible) * 100.0
        / COUNT(*),
        2
    ) AS compatibility_percent
FROM runtime_profiles r
JOIN runtime_host_compatibility c
    ON c.runtime_id = r.runtime_id
GROUP BY r.runtime_id, r.runtime_name
ORDER BY compatibility_percent DESC;

-- Isolation comparison keeps the kernel boundary distinct from general
-- resource efficiency.

SELECT
    runtime_name,
    shares_host_kernel,
    has_guest_kernel,
    has_virtual_hardware_boundary,
    isolation_score,
    memory_overhead_mib,
    cpu_overhead_percent,
    startup_seconds
FROM runtime_profiles
ORDER BY isolation_score DESC;

-- Store a representative estimate for later policy evaluation.

INSERT INTO deployment_estimates (
    workload_id,
    runtime_id,
    host_id,
    instance_count,
    estimated_cpu_cores,
    estimated_memory_gib,
    estimated_storage_gib,
    memory_utilization_percent,
    cpu_utilization_percent,
    storage_utilization_percent
)
SELECT
    w.workload_id,
    r.runtime_id,
    h.host_id,
    30,
    30 * w.requested_cpu_cores
        * (1 + r.cpu_overhead_percent / 100.0),
    30 * (
        w.requested_memory_gib
        + r.memory_overhead_mib / 1024.0
    ),
    30 * (
        w.requested_storage_gib
        + r.storage_overhead_gib
    ),
    30 * (
        w.requested_memory_gib
        + r.memory_overhead_mib / 1024.0
    ) / h.memory_gib * 100,
    30 * w.requested_cpu_cores
        * (1 + r.cpu_overhead_percent / 100.0)
        / h.cpu_cores * 100,
    30 * (
        w.requested_storage_gib
        + r.storage_overhead_gib
    ) / h.storage_gib * 100
FROM workloads w
JOIN runtime_profiles r
    ON r.runtime_type = 'CONTAINER'
JOIN hosts h
    ON h.host_name = 'linux-production-01'
WHERE w.workload_name = 'Payment API';

-- Transactional decision recording:
-- the database records the estimate and the resulting governance decision
-- together, preventing an application from reporting a decision without
-- preserving the underlying resource calculation.

BEGIN;

WITH latest_estimate AS (
    SELECT
        estimate_id,
        workload_id,
        runtime_id,
        host_id
    FROM deployment_estimates
    WHERE workload_id = (
        SELECT workload_id
        FROM workloads
        WHERE workload_name = 'Payment API'
    )
    ORDER BY created_at DESC
    LIMIT 1
)
INSERT INTO placement_decisions (
    workload_id,
    runtime_id,
    host_id,
    estimate_id,
    status,
    decision_reason
)
SELECT
    e.workload_id,
    e.runtime_id,
    e.host_id,
    e.estimate_id,
    CASE
        WHEN e.memory_utilization_percent <= 100
         AND e.cpu_utilization_percent <= 100
         AND e.storage_utilization_percent <= 100
        THEN 'APPROVED'
        ELSE 'REJECTED'
    END,
    CASE
        WHEN e.memory_utilization_percent <= 100
         AND e.cpu_utilization_percent <= 100
         AND e.storage_utilization_percent <= 100
        THEN 'Resource estimate fits the selected host.'
        ELSE 'Resource estimate exceeds host capacity.'
    END
FROM latest_estimate e;

COMMIT;

-- Policy query for strong-isolation workloads.
-- A container may be efficient but is rejected by this policy because the
-- modeled isolation boundary does not meet the selected threshold.

SELECT
    w.workload_name,
    r.runtime_name,
    CASE
        WHEN w.requires_strong_isolation
             AND r.isolation_score < 0.90
            THEN 'REJECTED'
        WHEN w.requires_specific_guest_os
             AND r.runtime_type <> 'VIRTUAL_MACHINE'
            THEN 'REJECTED'
        ELSE 'ELIGIBLE'
    END AS policy_result
FROM workloads w
CROSS JOIN runtime_profiles r
ORDER BY w.workload_name, r.runtime_name;

-- Demonstrate how resource efficiency changes with instance count.

WITH counts AS (
    SELECT generate_series(1, 50) AS instance_count
),
microservice AS (
    SELECT
        w.requested_cpu_cores,
        w.requested_memory_gib,
        w.requested_storage_gib
    FROM workloads w
    WHERE w.workload_name = 'Payment API'
)
SELECT
    c.instance_count,
    ROUND(
        c.instance_count * (
            m.requested_memory_gib
            + r.memory_overhead_mib / 1024.0
        ),
        2
    ) AS container_memory_gib,
    ROUND(
        c.instance_count * (
            m.requested_memory_gib
            + vm.memory_overhead_mib / 1024.0
        ),
        2
    ) AS vm_memory_gib
FROM counts c
CROSS JOIN microservice m
JOIN runtime_profiles r
    ON r.runtime_type = 'CONTAINER'
JOIN runtime_profiles vm
    ON vm.runtime_type = 'VIRTUAL_MACHINE'
ORDER BY c.instance_count;

-- The following constraint demonstrates a database-level invariant.
-- A negative isolation score cannot be inserted.
--
-- Example invalid operation:
-- INSERT INTO runtime_profiles (
--     runtime_type,
--     runtime_name,
--     shares_host_kernel,
--     has_guest_kernel,
--     has_virtual_hardware_boundary,
--     isolation_score,
--     memory_overhead_mib,
--     cpu_overhead_percent,
--     startup_seconds,
--     storage_overhead_gib,
--     requires_compatible_host_kernel
-- )
-- VALUES (
--     'CONTAINER',
--     'Invalid Runtime',
--     TRUE,
--     FALSE,
--     FALSE,
--     1.50,
--     80,
--     2,
--     1,
--     0.15,
--     TRUE
-- );
--
-- PostgreSQL rejects the row because isolation_score is constrained to
-- the interval [0, 1].

-- Final governance view:
-- This view separates the four major comparison dimensions:
-- isolation, performance/resource cost, portability, and startup behavior.

CREATE VIEW runtime_comparison AS
SELECT
    runtime_name,
    runtime_type,
    CASE
        WHEN shares_host_kernel
            THEN 'Shared host kernel'
        ELSE 'Independent guest kernel'
    END AS kernel_model,
    isolation_score,
    memory_overhead_mib,
    cpu_overhead_percent,
    storage_overhead_gib,
    startup_seconds,
    CASE
        WHEN requires_compatible_host_kernel
            THEN 'Requires compatible host kernel environment'
        ELSE 'Carries guest kernel'
    END AS portability_model
FROM runtime_profiles;

SELECT *
FROM runtime_comparison
ORDER BY isolation_score DESC;
