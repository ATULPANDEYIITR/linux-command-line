DROP SCHEMA IF EXISTS cloud_scaling CASCADE;
CREATE SCHEMA cloud_scaling;

SET search_path = cloud_scaling, public;

CREATE TYPE instance_state AS ENUM (
    'starting',
    'healthy',
    'unhealthy',
    'draining',
    'terminated'
);

CREATE TYPE request_status AS ENUM (
    'accepted',
    'rejected',
    'completed',
    'failed'
);

CREATE TYPE scaling_action AS ENUM (
    'scale_out',
    'scale_in',
    'hold'
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(repository_name)) >= 2)
);

CREATE TABLE compute_instances (
    instance_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    instance_name TEXT NOT NULL,
    region TEXT NOT NULL,
    capacity_rps INTEGER NOT NULL,
    state instance_state NOT NULL DEFAULT 'starting',
    active_requests INTEGER NOT NULL DEFAULT 0,
    launched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    terminated_at TIMESTAMPTZ,
    UNIQUE (repository_id, instance_name),
    CHECK (capacity_rps > 0),
    CHECK (active_requests >= 0),
    CHECK (
        state <> 'terminated'
        OR terminated_at IS NOT NULL
    )
);

CREATE INDEX idx_compute_healthy_targets
    ON compute_instances(repository_id, region)
    WHERE state = 'healthy';

CREATE TABLE load_balancers (
    load_balancer_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    algorithm TEXT NOT NULL DEFAULT 'capacity_aware_round_robin',
    timeout_ms INTEGER NOT NULL DEFAULT 500,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (repository_id, name),
    CHECK (timeout_ms BETWEEN 50 AND 30000)
);

CREATE TABLE scaling_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    policy_name TEXT NOT NULL,
    min_instances INTEGER NOT NULL,
    max_instances INTEGER NOT NULL,
    scale_out_threshold NUMERIC(5,4) NOT NULL,
    scale_in_threshold NUMERIC(5,4) NOT NULL,
    cooldown_seconds INTEGER NOT NULL,
    target_utilization NUMERIC(5,4) NOT NULL DEFAULT 0.6500,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (repository_id, policy_name),
    CHECK (min_instances >= 1),
    CHECK (max_instances >= min_instances),
    CHECK (
        scale_in_threshold > 0
        AND scale_in_threshold < scale_out_threshold
        AND scale_out_threshold <= 1
    ),
    CHECK (
        target_utilization > 0
        AND target_utilization <= 1
    ),
    CHECK (cooldown_seconds >= 0)
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    current_status TEXT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repository_id, check_name),
    CHECK (
        current_status IN ('pending', 'success', 'failure')
    )
);

CREATE TABLE scaling_events (
    scaling_event_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    policy_id BIGINT NOT NULL
        REFERENCES scaling_policies(policy_id),
    action scaling_action NOT NULL,
    observed_request_rate INTEGER NOT NULL,
    observed_capacity INTEGER NOT NULL,
    observed_utilization NUMERIC(8,4) NOT NULL,
    desired_instances INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (observed_request_rate >= 0),
    CHECK (observed_capacity >= 0),
    CHECK (observed_utilization >= 0),
    CHECK (desired_instances >= 1)
);

CREATE TABLE requests (
    request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    instance_id BIGINT
        REFERENCES compute_instances(instance_id)
        ON DELETE SET NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    latency_ms INTEGER,
    status request_status NOT NULL,
    payload_bytes INTEGER NOT NULL DEFAULT 0,
    CHECK (latency_ms IS NULL OR latency_ms >= 0),
    CHECK (payload_bytes >= 0)
);

CREATE INDEX idx_requests_repository_received
    ON requests(repository_id, received_at);

CREATE INDEX idx_requests_instance
    ON requests(instance_id);

CREATE TABLE traffic_samples (
    sample_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    request_rate INTEGER NOT NULL,
    healthy_capacity INTEGER NOT NULL,
    healthy_instances INTEGER NOT NULL,
    rejected_requests INTEGER NOT NULL DEFAULT 0,
    CHECK (request_rate >= 0),
    CHECK (healthy_capacity >= 0),
    CHECK (healthy_instances >= 0),
    CHECK (rejected_requests >= 0)
);

CREATE OR REPLACE FUNCTION validate_instance_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state = 'healthy'
       AND NEW.active_requests > NEW.capacity_rps THEN
        RAISE EXCEPTION
            'Active requests (%) exceed capacity (%) for instance %',
            NEW.active_requests,
            NEW.capacity_rps,
            NEW.instance_name;
    END IF;

    IF NEW.state = 'terminated'
       AND NEW.terminated_at IS NULL THEN
        NEW.terminated_at := CURRENT_TIMESTAMP;
    END IF;

    IF NEW.state <> 'terminated' THEN
        NEW.terminated_at := NULL;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_instance_state
BEFORE INSERT OR UPDATE ON compute_instances
FOR EACH ROW
EXECUTE FUNCTION validate_instance_state();

CREATE OR REPLACE FUNCTION validate_policy()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    existing_healthy INTEGER;
BEGIN
    SELECT count(*)
    INTO existing_healthy
    FROM compute_instances
    WHERE repository_id = NEW.repository_id
      AND state IN ('healthy', 'starting');

    IF NEW.min_instances > NEW.max_instances THEN
        RAISE EXCEPTION
            'Minimum instances cannot exceed maximum instances';
    END IF;

    IF existing_healthy > NEW.max_instances THEN
        RAISE EXCEPTION
            'Policy maximum (%) is below active pool size (%)',
            NEW.max_instances,
            existing_healthy;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_policy
BEFORE INSERT OR UPDATE ON scaling_policies
FOR EACH ROW
EXECUTE FUNCTION validate_policy();

CREATE OR REPLACE FUNCTION current_capacity(
    p_repository_id BIGINT
)
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(SUM(capacity_rps), 0)::INTEGER
    FROM compute_instances
    WHERE repository_id = p_repository_id
      AND state = 'healthy';
$$;

CREATE OR REPLACE FUNCTION healthy_instance_count(
    p_repository_id BIGINT
)
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT count(*)::INTEGER
    FROM compute_instances
    WHERE repository_id = p_repository_id
      AND state = 'healthy';
$$;

CREATE OR REPLACE FUNCTION evaluate_scaling(
    p_repository_id BIGINT,
    p_request_rate INTEGER
)
RETURNS TABLE (
    action scaling_action,
    current_capacity INTEGER,
    current_instances INTEGER,
    utilization NUMERIC,
    desired_instances INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    policy_row scaling_policies%ROWTYPE;
    capacity INTEGER;
    instance_count INTEGER;
    utilization_value NUMERIC;
    desired INTEGER;
BEGIN
    IF p_request_rate < 0 THEN
        RAISE EXCEPTION 'Request rate cannot be negative';
    END IF;

    SELECT *
    INTO policy_row
    FROM scaling_policies
    WHERE repository_id = p_repository_id
      AND enabled
    ORDER BY policy_id
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No enabled scaling policy exists for repository %',
            p_repository_id;
    END IF;

    capacity := current_capacity(p_repository_id);
    instance_count := healthy_instance_count(p_repository_id);

    IF capacity = 0 THEN
        utilization_value := 999;
    ELSE
        utilization_value :=
            round(
                p_request_rate::NUMERIC / capacity,
                4
            );
    END IF;

    desired := instance_count;

    IF capacity = 0
       OR utilization_value > policy_row.scale_out_threshold THEN

        desired := LEAST(
            policy_row.max_instances,
            GREATEST(instance_count + 1, policy_row.min_instances)
        );

        RETURN QUERY
        SELECT
            'scale_out'::scaling_action,
            capacity,
            instance_count,
            utilization_value,
            desired;

        RETURN;
    END IF;

    IF utilization_value < policy_row.scale_in_threshold
       AND instance_count > policy_row.min_instances THEN

        desired := GREATEST(
            policy_row.min_instances,
            instance_count - 1
        );

        RETURN QUERY
        SELECT
            'scale_in'::scaling_action,
            capacity,
            instance_count,
            utilization_value,
            desired;

        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        'hold'::scaling_action,
        capacity,
        instance_count,
        utilization_value,
        desired;
END;
$$;

CREATE OR REPLACE VIEW repository_capacity AS
SELECT
    r.repository_id,
    r.repository_name,
    r.region,
    count(ci.instance_id) FILTER (
        WHERE ci.state = 'healthy'
    ) AS healthy_instances,
    COALESCE(
        sum(ci.capacity_rps) FILTER (
            WHERE ci.state = 'healthy'
        ),
        0
    ) AS healthy_capacity_rps,
    COALESCE(
        sum(ci.active_requests) FILTER (
            WHERE ci.state = 'healthy'
        ),
        0
    ) AS active_requests
FROM repositories r
LEFT JOIN compute_instances ci
    ON ci.repository_id = r.repository_id
GROUP BY
    r.repository_id,
    r.repository_name,
    r.region;

CREATE OR REPLACE VIEW request_health_report AS
SELECT
    r.repository_id,
    r.repository_name,
    count(req.request_id) AS total_requests,
    count(req.request_id) FILTER (
        WHERE req.status = 'completed'
    ) AS completed_requests,
    count(req.request_id) FILTER (
        WHERE req.status = 'rejected'
    ) AS rejected_requests,
    round(
        avg(req.latency_ms)
        FILTER (WHERE req.latency_ms IS NOT NULL),
        2
    ) AS average_latency_ms
FROM repositories r
LEFT JOIN requests req
    ON req.repository_id = r.repository_id
GROUP BY
    r.repository_id,
    r.repository_name;

INSERT INTO repositories (
    repository_name,
    region
)
VALUES
    ('payments-api', 'ap-south-1'),
    ('catalog-api', 'eu-west-1');

INSERT INTO load_balancers (
    repository_id,
    name,
    timeout_ms
)
SELECT
    repository_id,
    repository_name || '-alb',
    750
FROM repositories;

INSERT INTO scaling_policies (
    repository_id,
    policy_name,
    min_instances,
    max_instances,
    scale_out_threshold,
    scale_in_threshold,
    cooldown_seconds,
    target_utilization
)
SELECT
    repository_id,
    'production-default',
    2,
    6,
    0.7500,
    0.3000,
    120,
    0.6500
FROM repositories;

INSERT INTO status_checks (
    repository_id,
    check_name,
    is_required,
    current_status
)
SELECT
    repository_id,
    'application-tests',
    TRUE,
    'success'
FROM repositories;

INSERT INTO status_checks (
    repository_id,
    check_name,
    is_required,
    current_status
)
SELECT
    repository_id,
    'security-scan',
    TRUE,
    'success'
FROM repositories;

INSERT INTO compute_instances (
    repository_id,
    instance_name,
    region,
    capacity_rps,
    state,
    active_requests
)
SELECT
    repository_id,
    repository_name || '-compute-01',
    region,
    120,
    'healthy',
    15
FROM repositories;

INSERT INTO compute_instances (
    repository_id,
    instance_name,
    region,
    capacity_rps,
    state,
    active_requests
)
SELECT
    repository_id,
    repository_name || '-compute-02',
    region,
    110,
    'healthy',
    20
FROM repositories;

INSERT INTO compute_instances (
    repository_id,
    instance_name,
    region,
    capacity_rps,
    state,
    active_requests
)
SELECT
    repository_id,
    repository_name || '-compute-03',
    region,
    100,
    'unhealthy',
    0
FROM repositories
WHERE repository_name = 'payments-api';

INSERT INTO traffic_samples (
    repository_id,
    request_rate,
    healthy_capacity,
    healthy_instances,
    rejected_requests
)
SELECT
    repository_id,
    180,
    230,
    2,
    0
FROM repositories
WHERE repository_name = 'payments-api';

INSERT INTO traffic_samples (
    repository_id,
    request_rate,
    healthy_capacity,
    healthy_instances,
    rejected_requests
)
SELECT
    repository_id,
    540,
    230,
    2,
    80
FROM repositories
WHERE repository_name = 'payments-api';

INSERT INTO requests (
    repository_id,
    instance_id,
    latency_ms,
    status,
    payload_bytes
)
SELECT
    r.repository_id,
    ci.instance_id,
    82,
    'completed',
    4096
FROM repositories r
JOIN compute_instances ci
    ON ci.repository_id = r.repository_id
WHERE r.repository_name = 'payments-api'
  AND ci.instance_name LIKE '%compute-01';

INSERT INTO requests (
    repository_id,
    instance_id,
    latency_ms,
    status,
    payload_bytes
)
SELECT
    r.repository_id,
    ci.instance_id,
    115,
    'completed',
    8192
FROM repositories r
JOIN compute_instances ci
    ON ci.repository_id = r.repository_id
WHERE r.repository_name = 'payments-api'
  AND ci.instance_name LIKE '%compute-02';

INSERT INTO requests (
    repository_id,
    instance_id,
    latency_ms,
    status,
    payload_bytes
)
SELECT
    repository_id,
    NULL,
    NULL,
    'rejected',
    1024
FROM repositories
WHERE repository_name = 'payments-api';

-- Scaling evaluation for normal traffic.
SELECT *
FROM evaluate_scaling(
    (
        SELECT repository_id
        FROM repositories
        WHERE repository_name = 'payments-api'
    ),
    180
);

-- Scaling evaluation for overload.
SELECT *
FROM evaluate_scaling(
    (
        SELECT repository_id
        FROM repositories
        WHERE repository_name = 'payments-api'
    ),
    540
);

-- Capacity report demonstrates the separation between
-- configured instances and currently healthy capacity.
SELECT *
FROM repository_capacity
ORDER BY repository_id;

-- Request-level reliability report.
SELECT *
FROM request_health_report
ORDER BY repository_id;

-- Required status checks that are not passing.
SELECT
    r.repository_name,
    sc.check_name,
    sc.current_status
FROM repositories r
JOIN status_checks sc
    ON sc.repository_id = r.repository_id
WHERE sc.is_required
  AND sc.current_status <> 'success';

-- Regional capacity distribution.
SELECT
    repository_name,
    region,
    count(*) FILTER (WHERE state = 'healthy') AS healthy_instances,
    COALESCE(
        sum(capacity_rps) FILTER (WHERE state = 'healthy'),
        0
    ) AS capacity_rps
FROM repositories r
JOIN compute_instances ci
    ON ci.repository_id = r.repository_id
GROUP BY repository_name, region
ORDER BY repository_name, region;

-- Transactional scale-out example. The row lock prevents two
-- concurrent scaling decisions from both creating the same
-- capacity change.
BEGIN;

SELECT policy_id
FROM scaling_policies
WHERE repository_id = (
    SELECT repository_id
    FROM repositories
    WHERE repository_name = 'payments-api'
)
AND enabled
FOR UPDATE;

WITH decision AS (
    SELECT *
    FROM evaluate_scaling(
        (
            SELECT repository_id
            FROM repositories
            WHERE repository_name = 'payments-api'
        ),
        540
    )
)
INSERT INTO scaling_events (
    repository_id,
    policy_id,
    action,
    observed_request_rate,
    observed_capacity,
    observed_utilization,
    desired_instances
)
SELECT
    r.repository_id,
    p.policy_id,
    d.action,
    540,
    d.current_capacity,
    d.utilization,
    d.desired_instances
FROM repositories r
JOIN scaling_policies p
    ON p.repository_id = r.repository_id
CROSS JOIN decision d
WHERE r.repository_name = 'payments-api'
  AND p.enabled
LIMIT 1;

COMMIT;

-- Verify the resulting scaling event.
SELECT
    r.repository_name,
    se.action,
    se.observed_request_rate,
    se.observed_capacity,
    se.observed_utilization,
    se.desired_instances,
    se.recorded_at
FROM scaling_events se
JOIN repositories r
    ON r.repository_id = se.repository_id
ORDER BY se.recorded_at DESC;
