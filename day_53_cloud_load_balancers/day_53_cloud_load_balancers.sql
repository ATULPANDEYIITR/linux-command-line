DROP SCHEMA IF EXISTS cloud_lb_demo CASCADE;
CREATE SCHEMA cloud_lb_demo;
SET search_path TO cloud_lb_demo;

-- PostgreSQL-specific relational model for a Layer-7 cloud load balancer.
-- The database distinguishes:
--   routing workflow -> pull-style request routing
--   code/review-like evaluation -> health and policy evaluation
--   approval-like decisions -> target eligibility decisions
--   protection/governance -> protected listener and backend rules

CREATE TYPE protocol_type AS ENUM ('HTTP', 'HTTPS');

CREATE TYPE target_state AS ENUM (
    'healthy',
    'unhealthy',
    'draining',
    'disabled'
);

CREATE TYPE routing_algorithm AS ENUM (
    'round_robin',
    'weighted',
    'least_connections'
);

CREATE TYPE check_result AS ENUM (
    'success',
    'failure',
    'timeout'
);

CREATE TYPE merge_policy_state AS ENUM (
    'eligible',
    'blocked'
);

CREATE TABLE load_balancers (
    load_balancer_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    certificate_hostname TEXT NOT NULL,
    certificate_id TEXT NOT NULL UNIQUE,
    minimum_tls_version TEXT NOT NULL
        CHECK (minimum_tls_version IN ('TLSv1.2', 'TLSv1.3')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE listeners (
    listener_id BIGSERIAL PRIMARY KEY,
    load_balancer_id BIGINT NOT NULL
        REFERENCES load_balancers(load_balancer_id)
        ON DELETE CASCADE,
    protocol protocol_type NOT NULL,
    port INTEGER NOT NULL
        CHECK (port BETWEEN 1 AND 65535),
    tls_termination BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (load_balancer_id, protocol, port)
);

CREATE TABLE target_groups (
    target_group_id BIGSERIAL PRIMARY KEY,
    load_balancer_id BIGINT NOT NULL
        REFERENCES load_balancers(load_balancer_id)
        ON DELETE CASCADE,
    name TEXT NOT NULL,
    routing_algorithm routing_algorithm NOT NULL,
    health_path TEXT NOT NULL DEFAULT '/health'
        CHECK (health_path LIKE '/%'),
    health_interval_seconds INTEGER NOT NULL DEFAULT 10
        CHECK (health_interval_seconds > 0),
    health_timeout_seconds INTEGER NOT NULL DEFAULT 2
        CHECK (
            health_timeout_seconds > 0
            AND health_timeout_seconds <= health_interval_seconds
        ),
    healthy_threshold INTEGER NOT NULL DEFAULT 2
        CHECK (healthy_threshold >= 1),
    unhealthy_threshold INTEGER NOT NULL DEFAULT 2
        CHECK (unhealthy_threshold >= 1),
    sticky_sessions BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (load_balancer_id, name)
);

CREATE TABLE backend_targets (
    target_id BIGSERIAL PRIMARY KEY,
    target_group_id BIGINT NOT NULL
        REFERENCES target_groups(target_group_id)
        ON DELETE CASCADE,
    target_name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL
        CHECK (port BETWEEN 1 AND 65535),
    weight INTEGER NOT NULL DEFAULT 1
        CHECK (weight > 0),
    state target_state NOT NULL DEFAULT 'healthy',
    simulated_health BOOLEAN NOT NULL DEFAULT TRUE,
    active_connections INTEGER NOT NULL DEFAULT 0
        CHECK (active_connections >= 0),
    total_requests BIGINT NOT NULL DEFAULT 0
        CHECK (total_requests >= 0),
    failed_requests BIGINT NOT NULL DEFAULT 0
        CHECK (failed_requests >= 0),
    UNIQUE (target_group_id, target_name),
    UNIQUE (target_group_id, host, port)
);

CREATE TABLE health_checks (
    health_check_id BIGSERIAL PRIMARY KEY,
    target_id BIGINT NOT NULL
        REFERENCES backend_targets(target_id)
        ON DELETE CASCADE,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    result check_result NOT NULL,
    response_time_ms INTEGER
        CHECK (response_time_ms IS NULL OR response_time_ms >= 0),
    status_code INTEGER
        CHECK (
            status_code IS NULL
            OR status_code BETWEEN 100 AND 599
        ),
    error_message TEXT
);

CREATE TABLE requests (
    request_id BIGSERIAL PRIMARY KEY,
    request_token TEXT NOT NULL UNIQUE,
    listener_id BIGINT NOT NULL
        REFERENCES listeners(listener_id),
    client_ip INET NOT NULL,
    host TEXT NOT NULL,
    request_path TEXT NOT NULL
        CHECK (request_path LIKE '/%'),
    protocol protocol_type NOT NULL,
    session_id TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE routing_events (
    routing_event_id BIGSERIAL PRIMARY KEY,
    request_id BIGINT NOT NULL
        REFERENCES requests(request_id)
        ON DELETE CASCADE,
    target_id BIGINT
        REFERENCES backend_targets(target_id),
    status_code INTEGER NOT NULL
        CHECK (status_code BETWEEN 100 AND 599),
    tls_terminated BOOLEAN NOT NULL,
    latency_ms INTEGER
        CHECK (latency_ms IS NULL OR latency_ms >= 0),
    failure_reason TEXT,
    routed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE branch_protection_like_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    target_group_id BIGINT NOT NULL UNIQUE
        REFERENCES target_groups(target_group_id)
        ON DELETE CASCADE,
    require_healthy_target BOOLEAN NOT NULL DEFAULT TRUE,
    require_tls_for_external_clients BOOLEAN NOT NULL DEFAULT TRUE,
    allow_direct_backend_access BOOLEAN NOT NULL DEFAULT FALSE,
    require_all_status_checks BOOLEAN NOT NULL DEFAULT TRUE,
    administrator_bypass BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE required_status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_like_policies(policy_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    UNIQUE (policy_id, check_name)
);

CREATE TABLE status_check_results (
    result_id BIGSERIAL PRIMARY KEY,
    status_check_id BIGINT NOT NULL
        REFERENCES required_status_checks(status_check_id)
        ON DELETE CASCADE,
    target_id BIGINT
        REFERENCES backend_targets(target_id)
        ON DELETE CASCADE,
    passed BOOLEAN NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- These indexes support common operational queries without indexing
-- every column indiscriminately.
CREATE INDEX idx_backend_targets_group_state
    ON backend_targets(target_group_id, state);

CREATE INDEX idx_health_checks_target_time
    ON health_checks(target_id, checked_at DESC);

CREATE INDEX idx_routing_events_time
    ON routing_events(routed_at DESC);

CREATE INDEX idx_requests_session
    ON requests(session_id)
    WHERE session_id IS NOT NULL;

INSERT INTO load_balancers (
    name,
    certificate_hostname,
    certificate_id,
    minimum_tls_version
)
VALUES (
    'production-api-lb',
    'api.example.com',
    'cert-prod-2026',
    'TLSv1.2'
);

INSERT INTO listeners (
    load_balancer_id,
    protocol,
    port,
    tls_termination
)
SELECT
    load_balancer_id,
    'HTTPS',
    443,
    TRUE
FROM load_balancers
WHERE name = 'production-api-lb';

INSERT INTO listeners (
    load_balancer_id,
    protocol,
    port,
    tls_termination
)
SELECT
    load_balancer_id,
    'HTTP',
    80,
    FALSE
FROM load_balancers
WHERE name = 'production-api-lb';

INSERT INTO target_groups (
    load_balancer_id,
    name,
    routing_algorithm,
    health_path,
    health_interval_seconds,
    health_timeout_seconds,
    healthy_threshold,
    unhealthy_threshold,
    sticky_sessions
)
SELECT
    load_balancer_id,
    'api-production',
    'weighted',
    '/health',
    10,
    2,
    2,
    2,
    TRUE
FROM load_balancers
WHERE name = 'production-api-lb';

INSERT INTO backend_targets (
    target_group_id,
    target_name,
    host,
    port,
    weight,
    state,
    simulated_health
)
SELECT
    target_group_id,
    target_name,
    host,
    8080,
    weight,
    'healthy',
    TRUE
FROM target_groups
CROSS JOIN (
    VALUES
        ('api-a', '10.20.0.10', 5),
        ('api-b', '10.20.0.11', 3),
        ('api-c', '10.20.0.12', 2)
) AS seed(target_name, host, weight)
WHERE target_groups.name = 'api-production';

INSERT INTO branch_protection_like_policies (
    target_group_id,
    require_healthy_target,
    require_tls_for_external_clients,
    allow_direct_backend_access,
    require_all_status_checks,
    administrator_bypass
)
SELECT
    target_group_id,
    TRUE,
    TRUE,
    FALSE,
    TRUE,
    FALSE
FROM target_groups
WHERE name = 'api-production';

INSERT INTO required_status_checks (
    policy_id,
    check_name
)
SELECT
    policy_id,
    check_name
FROM branch_protection_like_policies
CROSS JOIN (
    VALUES
        ('all-backends-healthy'),
        ('tls-policy-valid'),
        ('listener-config-valid')
) AS checks(check_name);

-- Health-check results establish the evidence used by routing eligibility.
INSERT INTO health_checks (
    target_id,
    result,
    response_time_ms,
    status_code
)
SELECT
    target_id,
    'success',
    CASE target_name
        WHEN 'api-a' THEN 14
        WHEN 'api-b' THEN 22
        ELSE 31
    END,
    200
FROM backend_targets
WHERE target_group_id = (
    SELECT target_group_id
    FROM target_groups
    WHERE name = 'api-production'
);

INSERT INTO health_checks (
    target_id,
    result,
    response_time_ms,
    status_code
)
SELECT
    target_id,
    'success',
    15,
    200
FROM backend_targets
WHERE target_name = 'api-a';

INSERT INTO health_checks (
    target_id,
    result,
    response_time_ms,
    status_code
)
SELECT
    target_id,
    'failure',
    2500,
    503
FROM backend_targets
WHERE target_name = 'api-b';

-- Update operational state from health evidence.
UPDATE backend_targets AS target
SET state = 'unhealthy'
WHERE target.target_name = 'api-b';

-- Required status-check results represent policy gates.
INSERT INTO status_check_results (
    status_check_id,
    target_id,
    passed
)
SELECT
    status_check_id,
    target.target_id,
    CASE
        WHEN checks.check_name = 'all-backends-healthy'
            THEN target.state = 'healthy'
        WHEN checks.check_name = 'tls-policy-valid'
            THEN lb.minimum_tls_version IN ('TLSv1.2', 'TLSv1.3')
        WHEN checks.check_name = 'listener-config-valid'
            THEN listener.port = 443
        ELSE FALSE
    END
FROM required_status_checks checks
JOIN branch_protection_like_policies policy
    ON policy.policy_id = checks.policy_id
JOIN target_groups tg
    ON tg.target_group_id = policy.target_group_id
JOIN load_balancers lb
    ON lb.load_balancer_id = tg.load_balancer_id
JOIN backend_targets target
    ON target.target_group_id = tg.target_group_id
CROSS JOIN LATERAL (
    SELECT port
    FROM listeners
    WHERE load_balancer_id = lb.load_balancer_id
      AND protocol = 'HTTPS'
      AND tls_termination = TRUE
    LIMIT 1
) listener;

-- Function evaluates whether a target is currently eligible for traffic.
CREATE OR REPLACE FUNCTION target_is_eligible(
    p_target_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT
        t.state = 'healthy'
        AND t.simulated_health
        AND EXISTS (
            SELECT 1
            FROM target_groups tg
            JOIN branch_protection_like_policies policy
                ON policy.target_group_id = tg.target_group_id
            WHERE tg.target_group_id = t.target_group_id
              AND policy.require_healthy_target
        )
    FROM backend_targets t
    WHERE t.target_id = p_target_id;
$$;

-- Function evaluates target-group merge/routing eligibility as a governance
-- decision. The CTEs keep health, TLS, and status-check rules distinct.
CREATE OR REPLACE FUNCTION target_group_eligibility(
    p_target_group_id BIGINT
)
RETURNS TABLE (
    target_group_id BIGINT,
    healthy_target_count BIGINT,
    required_checks BIGINT,
    passed_checks BIGINT,
    eligibility merge_policy_state,
    reason TEXT
)
LANGUAGE SQL
STABLE
AS $$
    WITH healthy AS (
        SELECT COUNT(*) AS count
        FROM backend_targets
        WHERE target_group_id = p_target_group_id
          AND state = 'healthy'
          AND simulated_health
    ),
    required_checks AS (
        SELECT COUNT(*) AS count
        FROM required_status_checks rsc
        JOIN branch_protection_like_policies p
            ON p.policy_id = rsc.policy_id
        WHERE p.target_group_id = p_target_group_id
    ),
    passed_checks AS (
        SELECT COUNT(*) AS count
        FROM status_check_results scr
        JOIN required_status_checks rsc
            ON rsc.status_check_id = scr.status_check_id
        JOIN branch_protection_like_policies p
            ON p.policy_id = rsc.policy_id
        WHERE p.target_group_id = p_target_group_id
          AND scr.passed
    )
    SELECT
        p_target_group_id,
        healthy.count,
        required_checks.count,
        passed_checks.count,
        CASE
            WHEN healthy.count > 0
             AND required_checks.count = passed_checks.count
            THEN 'eligible'::merge_policy_state
            ELSE 'blocked'::merge_policy_state
        END,
        CASE
            WHEN healthy.count = 0
                THEN 'No healthy backend target'
            WHEN required_checks.count <> passed_checks.count
                THEN 'Required status checks are not all passing'
            ELSE 'Routing policy conditions satisfied'
        END
    FROM healthy, required_checks, passed_checks;
$$;

-- Trigger prevents negative connection counts and request counters from
-- being introduced by application bugs or administrative updates.
CREATE OR REPLACE FUNCTION validate_backend_counters()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.active_connections < 0 THEN
        RAISE EXCEPTION
            'active_connections cannot be negative';
    END IF;

    IF NEW.total_requests < 0 OR NEW.failed_requests < 0 THEN
        RAISE EXCEPTION
            'request counters cannot be negative';
    END IF;

    IF NEW.failed_requests > NEW.total_requests THEN
        RAISE EXCEPTION
            'failed_requests cannot exceed total_requests';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_backend_counters
BEFORE INSERT OR UPDATE
ON backend_targets
FOR EACH ROW
EXECUTE FUNCTION validate_backend_counters();

-- A request-routing function performs validation and records the routing
-- decision in one transaction.
CREATE OR REPLACE FUNCTION route_request(
    p_request_token TEXT,
    p_listener_id BIGINT,
    p_client_ip INET,
    p_host TEXT,
    p_path TEXT,
    p_protocol protocol_type,
    p_session_id TEXT,
    p_target_id BIGINT,
    p_status_code INTEGER,
    p_latency_ms INTEGER,
    p_failure_reason TEXT DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_request_id BIGINT;
    v_tls_terminated BOOLEAN;
BEGIN
    IF p_request_token IS NULL OR btrim(p_request_token) = '' THEN
        RAISE EXCEPTION 'Request token is required';
    END IF;

    IF p_path IS NULL OR p_path NOT LIKE '/%' THEN
        RAISE EXCEPTION 'Request path must begin with /';
    END IF;

    IF p_status_code < 100 OR p_status_code > 599 THEN
        RAISE EXCEPTION 'Invalid HTTP status code';
    END IF;

    IF p_latency_ms IS NOT NULL AND p_latency_ms < 0 THEN
        RAISE EXCEPTION 'Latency cannot be negative';
    END IF;

    v_tls_terminated := p_protocol = 'HTTPS';

    INSERT INTO requests (
        request_token,
        listener_id,
        client_ip,
        host,
        request_path,
        protocol,
        session_id
    )
    VALUES (
        p_request_token,
        p_listener_id,
        p_client_ip,
        p_host,
        p_path,
        p_protocol,
        p_session_id
    )
    RETURNING request_id INTO v_request_id;

    INSERT INTO routing_events (
        request_id,
        target_id,
        status_code,
        tls_terminated,
        latency_ms,
        failure_reason
    )
    VALUES (
        v_request_id,
        p_target_id,
        p_status_code,
        v_tls_terminated,
        p_latency_ms,
        p_failure_reason
    );

    IF p_target_id IS NOT NULL THEN
        UPDATE backend_targets
        SET
            total_requests = total_requests + 1,
            failed_requests =
                failed_requests
                + CASE WHEN p_status_code >= 500 THEN 1 ELSE 0 END
        WHERE target_id = p_target_id;
    END IF;

    RETURN v_request_id;
END;
$$;

-- Transactional example: route a successful HTTPS request and update the
-- target counters atomically.
BEGIN;

SELECT route_request(
    'req-1001',
    (
        SELECT listener_id
        FROM listeners
        WHERE protocol = 'HTTPS'
        LIMIT 1
    ),
    '192.0.2.50',
    'api.example.com',
    '/orders',
    'HTTPS',
    'session-100',
    (
        SELECT target_id
        FROM backend_targets
        WHERE target_name = 'api-a'
    ),
    200,
    18,
    NULL
);

COMMIT;

-- Failed routing attempt caused by an unhealthy target. It is retained as
-- an operational event for diagnosis rather than silently discarded.
BEGIN;

SELECT route_request(
    'req-1002',
    (
        SELECT listener_id
        FROM listeners
        WHERE protocol = 'HTTPS'
        LIMIT 1
    ),
    '192.0.2.51',
    'api.example.com',
    '/orders',
    'HTTPS',
    'session-101',
    (
        SELECT target_id
        FROM backend_targets
        WHERE target_name = 'api-b'
    ),
    502,
    2500,
    'Backend health check failed'
);

COMMIT;

-- Current backend health report.
SELECT
    target_name,
    host,
    port,
    state,
    weight,
    active_connections,
    total_requests,
    failed_requests,
    ROUND(
        100.0
        * (total_requests - failed_requests)
        / NULLIF(total_requests, 0),
        2
    ) AS success_rate_percent
FROM backend_targets
ORDER BY target_name;

-- Health history identifies targets with recent failures.
SELECT
    t.target_name,
    hc.checked_at,
    hc.result,
    hc.response_time_ms,
    hc.status_code,
    hc.error_message
FROM health_checks hc
JOIN backend_targets t
    ON t.target_id = hc.target_id
ORDER BY hc.checked_at DESC, t.target_name;

-- CTE-based operational report separates request volume from failures.
WITH traffic AS (
    SELECT
        target_id,
        COUNT(*) AS request_count,
        COUNT(*) FILTER (WHERE status_code < 400) AS success_count,
        COUNT(*) FILTER (WHERE status_code >= 500) AS server_error_count,
        AVG(latency_ms) AS average_latency_ms
    FROM routing_events
    GROUP BY target_id
)
SELECT
    t.target_name,
    COALESCE(traffic.request_count, 0) AS request_count,
    COALESCE(traffic.success_count, 0) AS success_count,
    COALESCE(traffic.server_error_count, 0) AS server_error_count,
    ROUND(COALESCE(traffic.average_latency_ms, 0), 2)
        AS average_latency_ms
FROM backend_targets t
LEFT JOIN traffic
    ON traffic.target_id = t.target_id
ORDER BY t.target_name;

-- TLS termination report verifies that HTTPS listeners terminate TLS.
SELECT
    lb.name AS load_balancer,
    l.protocol,
    l.port,
    l.tls_termination,
    lb.minimum_tls_version,
    lb.certificate_hostname
FROM listeners l
JOIN load_balancers lb
    ON lb.load_balancer_id = l.load_balancer_id
WHERE l.protocol = 'HTTPS';

-- Policy evaluation reports whether the target group is eligible to serve
-- traffic under the modeled governance conditions.
SELECT *
FROM target_group_eligibility(
    (
        SELECT target_group_id
        FROM target_groups
        WHERE name = 'api-production'
    )
);

-- Detect unhealthy targets that still receive traffic.
SELECT
    t.target_name,
    t.state,
    COUNT(re.routing_event_id) AS routed_events
FROM backend_targets t
LEFT JOIN routing_events re
    ON re.target_id = t.target_id
WHERE t.state <> 'healthy'
GROUP BY t.target_name, t.state
HAVING COUNT(re.routing_event_id) > 0;

-- Session affinity report shows which backend currently handled each
-- session, useful when diagnosing uneven distribution.
SELECT
    r.session_id,
    t.target_name,
    COUNT(*) AS request_count
FROM requests r
JOIN routing_events re
    ON re.request_id = r.request_id
JOIN backend_targets t
    ON t.target_id = re.target_id
WHERE r.session_id IS NOT NULL
GROUP BY r.session_id, t.target_name
ORDER BY r.session_id, request_count DESC;
