-- PostgreSQL 14+
-- Auto-scaling simulation for an API service.
--
-- This schema separates infrastructure inventory, observed metrics,
-- scaling policies, decisions, and provisioning actions. It records a
-- simulated control plane and does not create cloud resources.

BEGIN;

DROP VIEW IF EXISTS scaling_capacity_summary;
DROP VIEW IF EXISTS scaling_recommendations;
DROP FUNCTION IF EXISTS evaluate_scaling_policy(BIGINT, TIMESTAMPTZ);
DROP TABLE IF EXISTS scaling_actions CASCADE;
DROP TABLE IF EXISTS capacity_metrics CASCADE;
DROP TABLE IF EXISTS scaling_policies CASCADE;
DROP TABLE IF EXISTS compute_instances CASCADE;
DROP TABLE IF EXISTS machine_types CASCADE;
DROP TABLE IF EXISTS scaling_groups CASCADE;

CREATE TABLE machine_types (
    machine_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    machine_name TEXT NOT NULL UNIQUE,
    cpu_cores INTEGER NOT NULL CHECK (cpu_cores > 0),
    memory_gb NUMERIC(10, 2) NOT NULL CHECK (memory_gb > 0),
    requests_per_core NUMERIC(12, 2) NOT NULL
        CHECK (requests_per_core > 0),
    hourly_cost NUMERIC(12, 4) NOT NULL CHECK (hourly_cost >= 0),
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE scaling_groups (
    scaling_group_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_name TEXT NOT NULL UNIQUE,
    service_name TEXT NOT NULL,
    environment TEXT NOT NULL
        CHECK (environment IN ('development', 'staging', 'production')),
    minimum_instances INTEGER NOT NULL CHECK (minimum_instances >= 1),
    maximum_instances INTEGER NOT NULL,
    desired_instances INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (maximum_instances >= minimum_instances),
    CHECK (
        desired_instances >= minimum_instances
        AND desired_instances <= maximum_instances
    )
);

CREATE TABLE scaling_policies (
    scaling_policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scaling_group_id BIGINT NOT NULL
        REFERENCES scaling_groups(scaling_group_id) ON DELETE CASCADE,
    policy_name TEXT NOT NULL,
    metric_name TEXT NOT NULL
        CHECK (metric_name IN ('cpu_percent', 'memory_percent', 'request_rate')),
    target_value NUMERIC(12, 2) NOT NULL CHECK (target_value > 0),
    scale_out_threshold NUMERIC(12, 2) NOT NULL,
    scale_in_threshold NUMERIC(12, 2) NOT NULL,
    scale_out_step INTEGER NOT NULL CHECK (scale_out_step > 0),
    scale_in_step INTEGER NOT NULL CHECK (scale_in_step > 0),
    cooldown_seconds INTEGER NOT NULL CHECK (cooldown_seconds >= 0),
    warmup_seconds INTEGER NOT NULL CHECK (warmup_seconds >= 0),
    evaluation_periods INTEGER NOT NULL CHECK (evaluation_periods > 0),
    maximum_change_per_evaluation INTEGER NOT NULL
        CHECK (maximum_change_per_evaluation > 0),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (scaling_group_id, policy_name),
    CHECK (scale_in_threshold >= 0),
    CHECK (scale_out_threshold > scale_in_threshold),
    CHECK (metric_name <> 'cpu_percent' OR scale_out_threshold <= 100),
    CHECK (metric_name <> 'cpu_percent' OR target_value < 100),
    CHECK (metric_name <> 'memory_percent' OR scale_out_threshold <= 100),
    CHECK (metric_name <> 'memory_percent' OR target_value <= 100)
);

CREATE TABLE compute_instances (
    instance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scaling_group_id BIGINT NOT NULL
        REFERENCES scaling_groups(scaling_group_id) ON DELETE CASCADE,
    machine_type_id BIGINT NOT NULL REFERENCES machine_types(machine_type_id),
    provider_instance_ref TEXT NOT NULL UNIQUE,
    instance_state TEXT NOT NULL
        CHECK (instance_state IN ('pending', 'ready', 'unhealthy', 'terminated')),
    launched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ready_at TIMESTAMPTZ,
    terminated_at TIMESTAMPTZ,
    availability_zone TEXT NOT NULL,
    CHECK (
        (instance_state = 'terminated' AND terminated_at IS NOT NULL)
        OR
        (instance_state <> 'terminated' AND terminated_at IS NULL)
    ),
    CHECK (ready_at IS NULL OR ready_at >= launched_at)
);

CREATE TABLE capacity_metrics (
    capacity_metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scaling_group_id BIGINT NOT NULL
        REFERENCES scaling_groups(scaling_group_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    incoming_rps NUMERIC(14, 2) NOT NULL CHECK (incoming_rps >= 0),
    cpu_percent NUMERIC(5, 2) NOT NULL
        CHECK (cpu_percent BETWEEN 0 AND 100),
    memory_percent NUMERIC(5, 2) NOT NULL
        CHECK (memory_percent BETWEEN 0 AND 100),
    ready_instances INTEGER NOT NULL CHECK (ready_instances >= 0),
    pending_instances INTEGER NOT NULL CHECK (pending_instances >= 0),
    available_capacity_rps NUMERIC(14, 2) NOT NULL
        CHECK (available_capacity_rps >= 0),
    served_rps NUMERIC(14, 2) NOT NULL CHECK (served_rps >= 0),
    rejected_rps NUMERIC(14, 2) NOT NULL CHECK (rejected_rps >= 0),
    average_latency_ms NUMERIC(14, 2) NOT NULL
        CHECK (average_latency_ms >= 0),
    estimated_hourly_cost NUMERIC(14, 4) NOT NULL
        CHECK (estimated_hourly_cost >= 0),
    CHECK (served_rps <= incoming_rps),
    CHECK (rejected_rps <= incoming_rps),
    CHECK (served_rps + rejected_rps <= incoming_rps + 0.01)
);

CREATE TABLE scaling_actions (
    scaling_action_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scaling_group_id BIGINT NOT NULL
        REFERENCES scaling_groups(scaling_group_id) ON DELETE CASCADE,
    scaling_policy_id BIGINT
        REFERENCES scaling_policies(scaling_policy_id) ON DELETE SET NULL,
    action_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_type TEXT NOT NULL
        CHECK (action_type IN (
            'scale_out', 'scale_in', 'no_change',
            'replace_instance', 'policy_rejected'
        )),
    previous_desired INTEGER NOT NULL CHECK (previous_desired >= 1),
    new_desired INTEGER NOT NULL CHECK (new_desired >= 1),
    requested_change INTEGER NOT NULL,
    applied_change INTEGER NOT NULL,
    reason TEXT NOT NULL,
    CHECK (
        (action_type = 'scale_out' AND new_desired >= previous_desired)
        OR
        (action_type = 'scale_in' AND new_desired <= previous_desired)
        OR
        action_type IN ('no_change', 'replace_instance', 'policy_rejected')
    )
);

CREATE INDEX idx_metrics_group_time
    ON capacity_metrics (scaling_group_id, observed_at DESC);

CREATE INDEX idx_metrics_cpu_time
    ON capacity_metrics (observed_at DESC, cpu_percent);

CREATE INDEX idx_instances_active
    ON compute_instances (scaling_group_id, instance_state)
    WHERE instance_state <> 'terminated';

CREATE INDEX idx_scaling_actions_group_time
    ON scaling_actions (scaling_group_id, action_time DESC);

CREATE INDEX idx_enabled_policies
    ON scaling_policies (scaling_group_id, metric_name)
    WHERE enabled;

INSERT INTO machine_types (
    machine_name, cpu_cores, memory_gb, requests_per_core, hourly_cost
) VALUES
    ('general-small', 2, 4, 120, 0.0800),
    ('general-large', 8, 16, 120, 0.3000);

INSERT INTO scaling_groups (
    group_name, service_name, environment,
    minimum_instances, maximum_instances, desired_instances
) VALUES
    ('production-api', 'payments-api', 'production', 2, 10, 2),
    ('staging-api', 'catalog-api', 'staging', 1, 6, 1);

INSERT INTO scaling_policies (
    scaling_group_id, policy_name, metric_name,
    target_value, scale_out_threshold, scale_in_threshold,
    scale_out_step, scale_in_step, cooldown_seconds,
    warmup_seconds, evaluation_periods, maximum_change_per_evaluation
)
SELECT
    scaling_group_id,
    'cpu-target-tracking',
    'cpu_percent',
    60,
    75,
    25,
    2,
    1,
    60,
    60,
    2,
    3
FROM scaling_groups
WHERE group_name = 'production-api';

INSERT INTO scaling_policies (
    scaling_group_id, policy_name, metric_name,
    target_value, scale_out_threshold, scale_in_threshold,
    scale_out_step, scale_in_step, cooldown_seconds,
    warmup_seconds, evaluation_periods, maximum_change_per_evaluation
)
SELECT
    scaling_group_id,
    'memory-pressure',
    'memory_percent',
    65,
    80,
    30,
    1,
    1,
    120,
    90,
    3,
    2
FROM scaling_groups
WHERE group_name = 'production-api';

INSERT INTO compute_instances (
    scaling_group_id, machine_type_id, provider_instance_ref,
    instance_state, launched_at, ready_at, availability_zone
)
SELECT
    g.scaling_group_id,
    m.machine_type_id,
    v.provider_ref,
    v.state,
    CURRENT_TIMESTAMP - INTERVAL '10 minutes',
    CURRENT_TIMESTAMP - INTERVAL '9 minutes',
    v.zone
FROM scaling_groups g
JOIN machine_types m ON m.machine_name = 'general-small'
CROSS JOIN (
    VALUES
        ('sim-api-001', 'ready', 'ap-south-1a'),
        ('sim-api-002', 'ready', 'ap-south-1b')
) AS v(provider_ref, state, zone)
WHERE g.group_name = 'production-api';

INSERT INTO capacity_metrics (
    scaling_group_id, observed_at, incoming_rps, cpu_percent, memory_percent,
    ready_instances, pending_instances, available_capacity_rps,
    served_rps, rejected_rps, average_latency_ms, estimated_hourly_cost
)
SELECT
    g.scaling_group_id,
    sample.observed_at,
    sample.incoming_rps,
    sample.cpu_percent,
    sample.memory_percent,
    sample.ready_instances,
    sample.pending_instances,
    sample.capacity_rps,
    LEAST(sample.incoming_rps, sample.capacity_rps),
    GREATEST(0, sample.incoming_rps - sample.capacity_rps),
    CASE
        WHEN sample.incoming_rps >= sample.capacity_rps THEN 1000
        ELSE 20 + 80 * (
            sample.incoming_rps / NULLIF(sample.capacity_rps, 0)
        ) / GREATEST(
            0.05,
            1 - sample.incoming_rps / NULLIF(sample.capacity_rps, 0)
        )
    END,
    sample.estimated_hourly_cost
FROM scaling_groups g
CROSS JOIN (
    VALUES
        (CURRENT_TIMESTAMP - INTERVAL '5 minutes',
         80::NUMERIC, 16::NUMERIC, 45::NUMERIC, 2, 0, 480::NUMERIC, 0.16::NUMERIC),
        (CURRENT_TIMESTAMP - INTERVAL '4 minutes',
         300::NUMERIC, 62.5::NUMERIC, 55::NUMERIC, 2, 0, 480::NUMERIC, 0.16::NUMERIC),
        (CURRENT_TIMESTAMP - INTERVAL '3 minutes',
         650::NUMERIC, 100::NUMERIC, 72::NUMERIC, 2, 0, 480::NUMERIC, 0.16::NUMERIC),
        (CURRENT_TIMESTAMP - INTERVAL '2 minutes',
         900::NUMERIC, 100::NUMERIC, 85::NUMERIC, 2, 2, 480::NUMERIC, 0.32::NUMERIC),
        (CURRENT_TIMESTAMP - INTERVAL '1 minute',
         500::NUMERIC, 52.1::NUMERIC, 58::NUMERIC, 4, 0, 960::NUMERIC, 0.32::NUMERIC)
) AS sample(
    observed_at, incoming_rps, cpu_percent, memory_percent,
    ready_instances, pending_instances, capacity_rps, estimated_hourly_cost
)
WHERE g.group_name = 'production-api';

CREATE VIEW scaling_capacity_summary AS
SELECT
    g.group_name,
    g.service_name,
    g.environment,
    g.minimum_instances,
    g.maximum_instances,
    g.desired_instances,
    COUNT(i.instance_id) FILTER (
        WHERE i.instance_state = 'ready'
    ) AS ready_instances,
    COUNT(i.instance_id) FILTER (
        WHERE i.instance_state = 'pending'
    ) AS pending_instances,
    COUNT(i.instance_id) FILTER (
        WHERE i.instance_state = 'unhealthy'
    ) AS unhealthy_instances,
    COALESCE(SUM(
        CASE WHEN i.instance_state = 'ready'
             THEN m.cpu_cores * m.requests_per_core
             ELSE 0
        END
    ), 0) AS ready_capacity_rps,
    COALESCE(SUM(
        CASE WHEN i.instance_state <> 'terminated'
             THEN m.hourly_cost
             ELSE 0
        END
    ), 0) AS estimated_hourly_cost
FROM scaling_groups g
LEFT JOIN compute_instances i
    ON i.scaling_group_id = g.scaling_group_id
LEFT JOIN machine_types m
    ON m.machine_type_id = i.machine_type_id
GROUP BY
    g.scaling_group_id,
    g.group_name,
    g.service_name,
    g.environment,
    g.minimum_instances,
    g.maximum_instances,
    g.desired_instances;

-- The view exposes policy decisions for application-side execution. It does
-- not directly provision resources. The latest samples must meet the
-- policy's evaluation-period requirement.
CREATE VIEW scaling_recommendations AS
WITH ranked_metrics AS (
    SELECT
        p.scaling_policy_id,
        p.scaling_group_id,
        p.policy_name,
        p.metric_name,
        p.scale_out_threshold,
        p.scale_in_threshold,
        p.scale_out_step,
        p.scale_in_step,
        p.evaluation_periods,
        p.maximum_change_per_evaluation,
        p.cooldown_seconds,
        g.minimum_instances,
        g.maximum_instances,
        g.desired_instances,
        cm.observed_at,
        CASE p.metric_name
            WHEN 'cpu_percent' THEN cm.cpu_percent
            WHEN 'memory_percent' THEN cm.memory_percent
            WHEN 'request_rate' THEN cm.incoming_rps
        END AS observed_value,
        ROW_NUMBER() OVER (
            PARTITION BY p.scaling_policy_id
            ORDER BY cm.observed_at DESC
        ) AS sample_rank
    FROM scaling_policies p
    JOIN scaling_groups g
        ON g.scaling_group_id = p.scaling_group_id
    JOIN capacity_metrics cm
        ON cm.scaling_group_id = p.scaling_group_id
    WHERE p.enabled
),
evaluated AS (
    SELECT
        scaling_policy_id,
        scaling_group_id,
        policy_name,
        metric_name,
        scale_out_threshold,
        scale_in_threshold,
        scale_out_step,
        scale_in_step,
        evaluation_periods,
        maximum_change_per_evaluation,
        minimum_instances,
        maximum_instances,
        desired_instances,
        COUNT(*) AS sample_count,
        AVG(observed_value) AS average_metric,
        MAX(observed_at) AS latest_observation
    FROM ranked_metrics
    WHERE sample_rank <= evaluation_periods
    GROUP BY
        scaling_policy_id,
        scaling_group_id,
        policy_name,
        metric_name,
        scale_out_threshold,
        scale_in_threshold,
        scale_out_step,
        scale_in_step,
        evaluation_periods,
        maximum_change_per_evaluation,
        minimum_instances,
        maximum_instances,
        desired_instances
)
SELECT
    *,
    CASE
        WHEN sample_count < evaluation_periods THEN 'insufficient_data'
        WHEN average_metric > scale_out_threshold
             AND desired_instances < maximum_instances THEN 'scale_out'
        WHEN average_metric < scale_in_threshold
             AND desired_instances > minimum_instances THEN 'scale_in'
        ELSE 'no_change'
    END AS recommended_action,
    CASE
        WHEN sample_count < evaluation_periods THEN 0
        WHEN average_metric > scale_out_threshold THEN LEAST(
            scale_out_step,
            maximum_change_per_evaluation,
            maximum_instances - desired_instances
        )
        WHEN average_metric < scale_in_threshold THEN -LEAST(
            scale_in_step,
            maximum_change_per_evaluation,
            desired_instances - minimum_instances
        )
        ELSE 0
    END AS recommended_delta
FROM evaluated;

-- A transactional decision function records a bounded recommendation.
-- The caller should additionally enforce distributed locking, idempotency,
-- cloud-provider reconciliation, and cooldown timing under concurrent workers.
CREATE FUNCTION evaluate_scaling_policy(
    p_scaling_policy_id BIGINT,
    p_now TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
RETURNS TABLE (
    policy_name TEXT,
    recommended_action TEXT,
    recommended_delta INTEGER,
    average_metric NUMERIC,
    sample_count BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_policy scaling_policies%ROWTYPE;
    v_group scaling_groups%ROWTYPE;
    v_average NUMERIC;
    v_count BIGINT;
    v_latest TIMESTAMPTZ;
    v_action TEXT := 'no_change';
    v_delta INTEGER := 0;
    v_previous INTEGER;
    v_reason TEXT;
BEGIN
    SELECT *
    INTO v_policy
    FROM scaling_policies
    WHERE scaling_policy_id = p_scaling_policy_id
      AND enabled
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Enabled scaling policy % was not found',
            p_scaling_policy_id;
    END IF;

    SELECT *
    INTO v_group
    FROM scaling_groups
    WHERE scaling_group_id = v_policy.scaling_group_id
    FOR UPDATE;

    SELECT
        AVG(metric_value),
        COUNT(*),
        MAX(observed_at)
    INTO v_average, v_count, v_latest
    FROM (
        SELECT
            cm.observed_at,
            CASE v_policy.metric_name
                WHEN 'cpu_percent' THEN cm.cpu_percent
                WHEN 'memory_percent' THEN cm.memory_percent
                WHEN 'request_rate' THEN cm.incoming_rps
            END AS metric_value
        FROM capacity_metrics cm
        WHERE cm.scaling_group_id = v_group.scaling_group_id
          AND cm.observed_at <= p_now
        ORDER BY cm.observed_at DESC
        LIMIT v_policy.evaluation_periods
    ) AS recent;

    v_previous := v_group.desired_instances;

    IF v_count < v_policy.evaluation_periods THEN
        v_reason := 'Insufficient monitoring samples';
    ELSIF v_latest < p_now - make_interval(
        secs => v_policy.cooldown_seconds
    ) THEN
        IF v_average > v_policy.scale_out_threshold
           AND v_group.desired_instances < v_group.maximum_instances THEN
            v_action := 'scale_out';
            v_delta := LEAST(
                v_policy.scale_out_step,
                v_policy.maximum_change_per_evaluation,
                v_group.maximum_instances - v_group.desired_instances
            );
            v_reason := 'Metric exceeds scale-out threshold';
        ELSIF v_average < v_policy.scale_in_threshold
           AND v_group.desired_instances > v_group.minimum_instances THEN
            v_action := 'scale_in';
            v_delta := -LEAST(
                v_policy.scale_in_step,
                v_policy.maximum_change_per_evaluation,
                v_group.desired_instances - v_group.minimum_instances
            );
            v_reason := 'Metric is below scale-in threshold';
        ELSE
            v_reason := 'Metric within thresholds or capacity bound reached';
        END IF;
    ELSE
        v_reason := 'Latest metric is inside cooldown window';
    END IF;

    IF v_action = 'scale_out' THEN
        UPDATE scaling_groups
        SET desired_instances = desired_instances + v_delta
        WHERE scaling_group_id = v_group.scaling_group_id;

    ELSIF v_action = 'scale_in' THEN
        UPDATE scaling_groups
        SET desired_instances = desired_instances + v_delta
        WHERE scaling_group_id = v_group.scaling_group_id;
    END IF;

    INSERT INTO scaling_actions (
        scaling_group_id,
        scaling_policy_id,
        action_time,
        action_type,
        previous_desired,
        new_desired,
        requested_change,
        applied_change,
        reason
    )
    SELECT
        v_group.scaling_group_id,
        v_policy.scaling_policy_id,
        p_now,
        v_action,
        v_previous,
        desired_instances,
        CASE
            WHEN v_average > v_policy.scale_out_threshold
                THEN v_policy.scale_out_step
            WHEN v_average < v_policy.scale_in_threshold
                THEN -v_policy.scale_in_step
            ELSE 0
        END,
        v_delta,
        COALESCE(v_reason, 'No scaling action required')
    FROM scaling_groups
    WHERE scaling_group_id = v_group.scaling_group_id;

    RETURN QUERY
    SELECT
        v_policy.policy_name,
        v_action,
        v_delta,
        v_average,
        v_count;
END;
$$;

-- Capacity comparison between horizontal and vertical options.
SELECT
    machine_name,
    cpu_cores,
    memory_gb,
    cpu_cores * requests_per_core AS estimated_capacity_rps,
    hourly_cost,
    CEIL(900 / (cpu_cores * requests_per_core * 0.60))::INTEGER
        AS instances_for_900_rps_at_60_percent,
    CEIL(900 / (cpu_cores * requests_per_core * 0.60)) * hourly_cost
        AS estimated_fleet_hourly_cost
FROM machine_types
WHERE enabled
ORDER BY estimated_fleet_hourly_cost;

-- Identify recent overload and saturation periods.
SELECT
    g.group_name,
    cm.observed_at,
    cm.incoming_rps,
    cm.available_capacity_rps,
    cm.cpu_percent,
    cm.memory_percent,
    cm.rejected_rps,
    cm.average_latency_ms
FROM capacity_metrics cm
JOIN scaling_groups g
    ON g.scaling_group_id = cm.scaling_group_id
WHERE cm.cpu_percent >= 75
   OR cm.rejected_rps > 0
ORDER BY cm.observed_at DESC;

-- Evaluate the production CPU policy. The function locks policy and group
-- rows, records the decision, and changes desired capacity in this transaction.
SELECT evaluate_scaling_policy(
    p.scaling_policy_id,
    CURRENT_TIMESTAMP
)
FROM scaling_policies p
JOIN scaling_groups g
    ON g.scaling_group_id = p.scaling_group_id
WHERE g.group_name = 'production-api'
  AND p.policy_name = 'cpu-target-tracking';

SELECT * FROM scaling_capacity_summary;
SELECT * FROM scaling_recommendations;
SELECT * FROM scaling_actions ORDER BY action_time DESC;

COMMIT;

-- Important production limitations:
-- The relational function records desired capacity, not provider resources.
-- Metric ingestion should be idempotent and use trusted monitoring sources.
-- Concurrent workers need a shared locking/idempotency strategy.
-- Instance termination requires draining, health checks, and availability
-- safeguards beyond a database row update.
-- CPU utilization thresholds are not universally appropriate for every service.
