-- ============================================================
-- KUBERNETES CONTROL PLANE
-- PostgreSQL 15+
--
-- Relational model for:
--   1. Clusters and repositories of cluster resources
--   2. Control plane components
--   3. Nodes and capacity
--   4. Namespaces
--   5. Pods and containers
--   6. Deployments and reconciliation
--   7. Scheduling and resource allocation
--   8. Component heartbeats
--   9. Leader election
--  10. Control plane events
--  11. Operational policies
--  12. Health evaluation and audit
--
-- The schema is an operational learning model.
-- It is not a replacement for Kubernetes etcd.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS k8s_control;

SET search_path TO k8s_control, public;

-- ============================================================
-- 1. ENUMERATIONS
-- ============================================================

CREATE TYPE component_type AS ENUM (
    'API_SERVER',
    'SCHEDULER',
    'CONTROLLER_MANAGER',
    'ETCD',
    'CLOUD_CONTROLLER_MANAGER',
    'KUBELET',
    'KUBE_PROXY'
);

CREATE TYPE component_status AS ENUM (
    'HEALTHY',
    'DEGRADED',
    'UNAVAILABLE',
    'UNKNOWN'
);

CREATE TYPE node_status AS ENUM (
    'READY',
    'NOT_READY',
    'UNKNOWN'
);

CREATE TYPE pod_phase AS ENUM (
    'PENDING',
    'RUNNING',
    'FAILED',
    'SUCCEEDED'
);

CREATE TYPE deployment_status AS ENUM (
    'ACTIVE',
    'PROGRESSING',
    'DEGRADED',
    'FAILED',
    'COMPLETED'
);

CREATE TYPE scheduling_status AS ENUM (
    'PENDING',
    'SCHEDULED',
    'UNSCHEDULABLE',
    'CANCELLED'
);

CREATE TYPE event_type AS ENUM (
    'NORMAL',
    'WARNING',
    'ERROR'
);

CREATE TYPE operation_status AS ENUM (
    'ACCEPTED',
    'REJECTED',
    'COMPLETED',
    'FAILED'
);

-- ============================================================
-- 2. CLUSTERS
-- ============================================================

CREATE TABLE clusters (
    cluster_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_name VARCHAR(100) NOT NULL UNIQUE,

    kubernetes_version VARCHAR(30) NOT NULL,

    environment VARCHAR(30) NOT NULL,

    region VARCHAR(100) NOT NULL,

    control_plane_endpoint TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT valid_environment CHECK (
        environment IN (
            'development',
            'testing',
            'staging',
            'production'
        )
    )
);

-- ============================================================
-- 3. NAMESPACES
-- ============================================================

CREATE TABLE namespaces (
    namespace_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL REFERENCES clusters(cluster_id),

    namespace_name VARCHAR(63) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    UNIQUE (cluster_id, namespace_name),

    CHECK (status IN ('ACTIVE', 'TERMINATING', 'TERMINATED'))
);

-- ============================================================
-- 4. CONTROL PLANE COMPONENTS
-- ============================================================

CREATE TABLE control_plane_components (
    component_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL REFERENCES clusters(cluster_id),

    component_name VARCHAR(100) NOT NULL,

    component_type component_type NOT NULL,

    version VARCHAR(30) NOT NULL,

    status component_status NOT NULL DEFAULT 'UNKNOWN',

    endpoint TEXT,

    last_heartbeat TIMESTAMPTZ,

    started_at TIMESTAMPTZ,

    UNIQUE (cluster_id, component_name)
);

CREATE INDEX idx_components_cluster_status
    ON control_plane_components(cluster_id, status);

CREATE INDEX idx_components_heartbeat
    ON control_plane_components(last_heartbeat);

-- ============================================================
-- 5. WORKER AND CONTROL PLANE NODES
-- ============================================================

CREATE TABLE nodes (
    node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL REFERENCES clusters(cluster_id),

    node_name VARCHAR(253) NOT NULL,

    node_role VARCHAR(30) NOT NULL,

    status node_status NOT NULL DEFAULT 'UNKNOWN',

    cpu_capacity INTEGER NOT NULL,

    memory_capacity_mb INTEGER NOT NULL,

    cpu_allocated INTEGER NOT NULL DEFAULT 0,

    memory_allocated_mb INTEGER NOT NULL DEFAULT 0,

    kubelet_version VARCHAR(30) NOT NULL,

    last_heartbeat TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (cluster_id, node_name),

    CHECK (cpu_capacity > 0),

    CHECK (memory_capacity_mb > 0),

    CHECK (cpu_allocated >= 0),

    CHECK (memory_allocated_mb >= 0),

    CHECK (cpu_allocated <= cpu_capacity),

    CHECK (memory_allocated_mb <= memory_capacity),

    CHECK (
        node_role IN (
            'CONTROL_PLANE',
            'WORKER'
        )
    )
);

CREATE INDEX idx_nodes_cluster_status
    ON nodes(cluster_id, status);

CREATE INDEX idx_nodes_available_capacity
    ON nodes(
        cluster_id,
        status,
        cpu_capacity,
        memory_capacity_mb
    );

-- ============================================================
-- 6. DEPLOYMENTS
-- ============================================================

CREATE TABLE deployments (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL REFERENCES namespaces(namespace_id),

    deployment_name VARCHAR(253) NOT NULL,

    container_image TEXT NOT NULL,

    desired_replicas INTEGER NOT NULL,

    observed_replicas INTEGER NOT NULL DEFAULT 0,

    ready_replicas INTEGER NOT NULL DEFAULT 0,

    cpu_request INTEGER NOT NULL,

    memory_request_mb INTEGER NOT NULL,

    status deployment_status NOT NULL DEFAULT 'PROGRESSING',

    generation BIGINT NOT NULL DEFAULT 1,

    observed_generation BIGINT NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (namespace_id, deployment_name),

    CHECK (desired_replicas >= 0),

    CHECK (observed_replicas >= 0),

    CHECK (ready_replicas >= 0),

    CHECK (cpu_request > 0),

    CHECK (memory_request_mb > 0),

    CHECK (ready_replicas <= observed_replicas)
);

CREATE INDEX idx_deployments_namespace_status
    ON deployments(namespace_id, status);

-- ============================================================
-- 7. PODS
-- ============================================================

CREATE TABLE pods (
    pod_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL REFERENCES namespaces(namespace_id),

    deployment_id BIGINT REFERENCES deployments(deployment_id),

    pod_name VARCHAR(253) NOT NULL,

    uid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    phase pod_phase NOT NULL DEFAULT 'PENDING',

    assigned_node_id BIGINT REFERENCES nodes(node_id),

    restart_count INTEGER NOT NULL DEFAULT 0,

    resource_version BIGINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (namespace_id, pod_name),

    CHECK (restart_count >= 0),

    CHECK (resource_version > 0)
);

CREATE INDEX idx_pods_namespace_phase
    ON pods(namespace_id, phase);

CREATE INDEX idx_pods_node_phase
    ON pods(assigned_node_id, phase);

CREATE INDEX idx_pods_deployment
    ON pods(deployment_id);

-- ============================================================
-- 8. CONTAINER SPECIFICATIONS
-- ============================================================

CREATE TABLE containers (
    container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_id BIGINT NOT NULL REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    container_name VARCHAR(100) NOT NULL,

    image TEXT NOT NULL,

    cpu_request INTEGER NOT NULL,

    memory_request_mb INTEGER NOT NULL,

    UNIQUE (pod_id, container_name),

    CHECK (cpu_request > 0),

    CHECK (memory_request_mb > 0)
);

CREATE INDEX idx_containers_pod
    ON containers(pod_id);

-- ============================================================
-- 9. SCHEDULING ATTEMPTS
-- ============================================================

CREATE TABLE scheduling_attempts (
    attempt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_id BIGINT NOT NULL REFERENCES pods(pod_id),

    selected_node_id BIGINT REFERENCES nodes(node_id),

    attempt_number INTEGER NOT NULL,

    status scheduling_status NOT NULL DEFAULT 'PENDING',

    reason TEXT,

    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (pod_id, attempt_number),

    CHECK (attempt_number > 0),

    CHECK (
        (status = 'SCHEDULED' AND selected_node_id IS NOT NULL)
        OR
        (status <> 'SCHEDULED')
    )
);

CREATE INDEX idx_scheduling_status_time
    ON scheduling_attempts(status, attempted_at DESC);

-- ============================================================
-- 10. COMPONENT HEARTBEATS
-- ============================================================

CREATE TABLE component_heartbeats (
    heartbeat_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    component_id BIGINT NOT NULL
        REFERENCES control_plane_components(component_id),

    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    response_time_ms INTEGER,

    successful BOOLEAN NOT NULL,

    message TEXT,

    CHECK (
        response_time_ms IS NULL
        OR response_time_ms >= 0
    )
);

CREATE INDEX idx_heartbeats_component_time
    ON component_heartbeats(component_id, received_at DESC);

-- ============================================================
-- 11. CONTROL PLANE POLICIES
-- ============================================================

CREATE TABLE control_plane_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL REFERENCES clusters(cluster_id),

    policy_name VARCHAR(100) NOT NULL,

    require_api_server BOOLEAN NOT NULL DEFAULT TRUE,

    require_scheduler BOOLEAN NOT NULL DEFAULT TRUE,

    require_controller_manager BOOLEAN NOT NULL DEFAULT TRUE,

    require_etcd BOOLEAN NOT NULL DEFAULT TRUE,

    reject_degraded_components BOOLEAN NOT NULL DEFAULT TRUE,

    minimum_ready_nodes INTEGER NOT NULL DEFAULT 1,

    maximum_heartbeat_age_seconds INTEGER NOT NULL DEFAULT 30,

    allow_degraded_operation BOOLEAN NOT NULL DEFAULT FALSE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (cluster_id, policy_name),

    CHECK (minimum_ready_nodes >= 0),

    CHECK (maximum_heartbeat_age_seconds > 0)
);

-- ============================================================
-- 12. LEASES AND LEADER ELECTION
-- ============================================================

CREATE TABLE control_plane_leases (
    lease_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL REFERENCES clusters(cluster_id),

    lease_name VARCHAR(100) NOT NULL,

    holder_identity VARCHAR(253),

    acquired_at TIMESTAMPTZ,

    renewed_at TIMESTAMPTZ,

    lease_duration_seconds INTEGER NOT NULL,

    resource_version BIGINT NOT NULL DEFAULT 1,

    UNIQUE (cluster_id, lease_name),

    CHECK (lease_duration_seconds > 0),

    CHECK (resource_version > 0)
);

CREATE INDEX idx_leases_expiry
    ON control_plane_leases(renewed_at);

-- ============================================================
-- 13. CONTROL PLANE EVENTS
-- ============================================================

CREATE TABLE control_plane_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL REFERENCES clusters(cluster_id),

    component_id BIGINT REFERENCES control_plane_components(component_id),

    pod_id BIGINT REFERENCES pods(pod_id),

    event_type event_type NOT NULL,

    reason VARCHAR(100) NOT NULL,

    message TEXT NOT NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_cluster_time
    ON control_plane_events(cluster_id, occurred_at DESC);

CREATE INDEX idx_events_type_time
    ON control_plane_events(event_type, occurred_at DESC);

-- ============================================================
-- 14. CONTROL PLANE AUDIT
-- ============================================================

CREATE TABLE operation_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL REFERENCES clusters(cluster_id),

    actor VARCHAR(253) NOT NULL,

    operation VARCHAR(50) NOT NULL,

    resource_type VARCHAR(100) NOT NULL,

    resource_identifier VARCHAR(253) NOT NULL,

    status operation_status NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_cluster_time
    ON operation_audit(cluster_id, occurred_at DESC);

CREATE INDEX idx_audit_resource
    ON operation_audit(resource_type, resource_identifier);

-- ============================================================
-- 15. RESOURCE VERSION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION increment_pod_resource_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.resource_version := OLD.resource_version + 1;
    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_pod_resource_version
BEFORE UPDATE ON pods
FOR EACH ROW
EXECUTE FUNCTION increment_pod_resource_version();

-- ============================================================
-- 16. DEPLOYMENT VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_deployment_replicas()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.ready_replicas > NEW.observed_replicas THEN
        RAISE EXCEPTION
            'Ready replicas cannot exceed observed replicas';
    END IF;

    IF NEW.observed_replicas > NEW.desired_replicas THEN
        RAISE EXCEPTION
            'Observed replicas exceed desired replicas';
    END IF;

    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_deployment
BEFORE INSERT OR UPDATE ON deployments
FOR EACH ROW
EXECUTE FUNCTION validate_deployment_replicas();

-- ============================================================
-- 17. POD RESOURCE CALCULATION
-- ============================================================

CREATE OR REPLACE FUNCTION get_pod_resource_requirements(
    p_pod_id BIGINT
)
RETURNS TABLE (
    total_cpu INTEGER,
    total_memory_mb INTEGER
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        COALESCE(SUM(cpu_request), 0)::INTEGER,
        COALESCE(SUM(memory_request_mb), 0)::INTEGER
    FROM containers
    WHERE pod_id = p_pod_id;
$$;

-- ============================================================
-- 18. NODE FEASIBILITY
-- ============================================================

CREATE OR REPLACE FUNCTION node_can_schedule_pod(
    p_pod_id BIGINT,
    p_node_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_cpu INTEGER;
    v_memory INTEGER;
    v_node RECORD;
BEGIN
    SELECT *
    INTO v_node
    FROM nodes
    WHERE node_id = p_node_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_node.status <> 'READY' THEN
        RETURN FALSE;
    END IF;

    SELECT total_cpu, total_memory_mb
    INTO v_cpu, v_memory
    FROM get_pod_resource_requirements(p_pod_id);

    RETURN (
        v_node.cpu_capacity - v_node.cpu_allocated >= v_cpu
        AND
        v_node.memory_capacity_mb -
            v_node.memory_allocated_mb >= v_memory
    );
END;
$$;

-- ============================================================
-- 19. ATOMIC POD SCHEDULING PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE schedule_pod(
    p_pod_id BIGINT,
    p_node_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cpu INTEGER;
    v_memory INTEGER;
    v_namespace BIGINT;
    v_phase pod_phase;
BEGIN
    -- Lock the pod to prevent concurrent scheduling attempts.
    SELECT namespace_id, phase
    INTO v_namespace, v_phase
    FROM pods
    WHERE pod_id = p_pod_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pod does not exist';
    END IF;

    IF v_phase <> 'PENDING' THEN
        RAISE EXCEPTION 'Only pending pods can be scheduled';
    END IF;

    SELECT total_cpu, total_memory_mb
    INTO v_cpu, v_memory
    FROM get_pod_resource_requirements(p_pod_id);

    -- Lock the selected node before checking and allocating capacity.
    PERFORM 1
    FROM nodes
    WHERE node_id = p_node_id
      AND status = 'READY'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Node is unavailable';
    END IF;

    IF NOT node_can_schedule_pod(p_pod_id, p_node_id) THEN
        RAISE EXCEPTION 'Insufficient node resources';
    END IF;

    UPDATE nodes
    SET cpu_allocated = cpu_allocated + v_cpu,
        memory_allocated_mb = memory_allocated_mb + v_memory
    WHERE node_id = p_node_id;

    UPDATE pods
    SET assigned_node_id = p_node_id,
        phase = 'RUNNING'
    WHERE pod_id = p_pod_id;

    INSERT INTO scheduling_attempts (
        pod_id,
        selected_node_id,
        attempt_number,
        status,
        reason
    )
    VALUES (
        p_pod_id,
        p_node_id,
        COALESCE(
            (
                SELECT MAX(attempt_number) + 1
                FROM scheduling_attempts
                WHERE pod_id = p_pod_id
            ),
            1
        ),
        'SCHEDULED',
        'Node selected and resources allocated'
    );

    INSERT INTO operation_audit (
        cluster_id,
        actor,
        operation,
        resource_type,
        resource_identifier,
        status,
        details
    )
    SELECT
        n.cluster_id,
        'kube-scheduler',
        'SCHEDULE',
        'Pod',
        p_pod_id::TEXT,
        'COMPLETED',
        jsonb_build_object(
            'node_id', p_node_id,
            'cpu', v_cpu,
            'memory_mb', v_memory
        )
    FROM nodes n
    WHERE n.node_id = p_node_id;

EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$;

-- ============================================================
-- 20. DEPLOYMENT RECONCILIATION REPORT
-- ============================================================

CREATE OR REPLACE FUNCTION reconcile_deployment(
    p_deployment_id BIGINT
)
RETURNS TABLE (
    deployment_name VARCHAR,
    desired INTEGER,
    observed INTEGER,
    ready INTEGER,
    missing INTEGER
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        d.deployment_name,
        d.desired_replicas,
        COUNT(p.pod_id)::INTEGER,
        COUNT(p.pod_id) FILTER (
            WHERE p.phase = 'RUNNING'
        )::INTEGER,
        GREATEST(
            d.desired_replicas - COUNT(p.pod_id)::INTEGER,
            0
        )
    FROM deployments d
    LEFT JOIN pods p
        ON p.deployment_id = d.deployment_id
    WHERE d.deployment_id = p_deployment_id
    GROUP BY
        d.deployment_id,
        d.deployment_name,
        d.desired_replicas;
$$;

-- ============================================================
-- 21. CONTROL PLANE HEALTH EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_control_plane(
    p_cluster_id BIGINT
)
RETURNS TABLE (
    component_name VARCHAR,
    component_status component_status,
    heartbeat_age_seconds NUMERIC,
    evaluation TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        c.component_name,
        c.status,
        CASE
            WHEN c.last_heartbeat IS NULL THEN NULL
            ELSE ROUND(
                EXTRACT(
                    EPOCH FROM NOW() - c.last_heartbeat
                )::NUMERIC,
                2
            )
        END,
        CASE
            WHEN c.last_heartbeat IS NULL THEN 'NO_HEARTBEAT'
            WHEN c.status = 'UNAVAILABLE' THEN 'UNAVAILABLE'
            WHEN c.status = 'DEGRADED' THEN 'DEGRADED'
            ELSE 'REGISTERED'
        END
    FROM control_plane_components c
    WHERE c.cluster_id = p_cluster_id
    ORDER BY c.component_type;
$$;

-- ============================================================
-- 22. POLICY ELIGIBILITY EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_cluster_policy(
    p_cluster_id BIGINT
)
RETURNS TABLE (
    policy_name VARCHAR,
    eligible BOOLEAN,
    violations TEXT[]
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    p RECORD;
    v_ready_nodes INTEGER;
    v_violations TEXT[];
    v_unavailable BIGINT;
    v_degraded BIGINT;
BEGIN
    FOR p IN
        SELECT *
        FROM control_plane_policies
        WHERE cluster_id = p_cluster_id
          AND enabled = TRUE
    LOOP
        v_violations := ARRAY[]::TEXT[];

        SELECT COUNT(*)::INTEGER
        INTO v_ready_nodes
        FROM nodes
        WHERE cluster_id = p_cluster_id
          AND status = 'READY';

        IF v_ready_nodes < p.minimum_ready_nodes THEN
            v_violations := array_append(
                v_violations,
                'INSUFFICIENT_READY_NODES'
            );
        END IF;

        SELECT COUNT(*)
        INTO v_unavailable
        FROM control_plane_components c
        WHERE c.cluster_id = p_cluster_id
          AND (
              (
                  p.require_api_server
                  AND c.component_type = 'API_SERVER'
              )
              OR (
                  p.require_scheduler
                  AND c.component_type = 'SCHEDULER'
              )
              OR (
                  p.require_controller_manager
                  AND c.component_type = 'CONTROLLER_MANAGER'
              )
              OR (
                  p.require_etcd
                  AND c.component_type = 'ETCD'
              )
          )
          AND (
              c.status = 'UNAVAILABLE'
              OR c.last_heartbeat IS NULL
              OR c.last_heartbeat <
                 NOW() - make_interval(
                     secs => p.maximum_heartbeat_age_seconds
                 )
          );

        IF v_unavailable > 0 THEN
            v_violations := array_append(
                v_violations,
                'REQUIRED_COMPONENT_UNAVAILABLE'
            );
        END IF;

        IF p.reject_degraded_components THEN
            SELECT COUNT(*)
            INTO v_degraded
            FROM control_plane_components c
            WHERE c.cluster_id = p_cluster_id
              AND c.status = 'DEGRADED';

            IF v_degraded > 0 THEN
                v_violations := array_append(
                    v_violations,
                    'DEGRADED_COMPONENT_PRESENT'
                );
            END IF;
        END IF;

        policy_name := p.policy_name;
        eligible := cardinality(v_violations) = 0;
        violations := v_violations;

        RETURN NEXT;
    END LOOP;
END;
$$;

-- ============================================================
-- 23. LEASE RENEWAL
-- ============================================================

CREATE OR REPLACE PROCEDURE renew_control_plane_lease(
    p_lease_id BIGINT,
    p_holder VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_lease RECORD;
BEGIN
    SELECT *
    INTO v_lease
    FROM control_plane_leases
    WHERE lease_id = p_lease_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Lease not found';
    END IF;

    IF v_lease.holder_identity IS NOT NULL
       AND v_lease.holder_identity <> p_holder
       AND v_lease.renewed_at IS NOT NULL
       AND v_lease.renewed_at >
           NOW() - make_interval(
               secs => v_lease.lease_duration_seconds
           )
    THEN
        RAISE EXCEPTION 'Lease is held by another identity';
    END IF;

    UPDATE control_plane_leases
    SET holder_identity = p_holder,
        acquired_at = COALESCE(acquired_at, NOW()),
        renewed_at = NOW(),
        resource_version = resource_version + 1
    WHERE lease_id = p_lease_id;
END;
$$;

-- ============================================================
-- 24. CONTROL PLANE REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW cluster_control_plane_summary AS
SELECT
    cl.cluster_id,
    cl.cluster_name,
    cl.kubernetes_version,

    COUNT(DISTINCT c.component_id) AS component_count,

    COUNT(DISTINCT c.component_id) FILTER (
        WHERE c.status = 'HEALTHY'
    ) AS healthy_components,

    COUNT(DISTINCT c.component_id) FILTER (
        WHERE c.status = 'UNAVAILABLE'
    ) AS unavailable_components,

    COUNT(DISTINCT n.node_id) AS node_count,

    COUNT(DISTINCT n.node_id) FILTER (
        WHERE n.status = 'READY'
    ) AS ready_nodes,

    COUNT(DISTINCT p.pod_id) AS pod_count,

    COUNT(DISTINCT p.pod_id) FILTER (
        WHERE p.phase = 'RUNNING'
    ) AS running_pods,

    COUNT(DISTINCT p.pod_id) FILTER (
        WHERE p.phase = 'PENDING'
    ) AS pending_pods

FROM clusters cl

LEFT JOIN control_plane_components c
    ON c.cluster_id = cl.cluster_id

LEFT JOIN nodes n
    ON n.cluster_id = cl.cluster_id

LEFT JOIN namespaces ns
    ON ns.cluster_id = cl.cluster_id

LEFT JOIN pods p
    ON p.namespace_id = ns.namespace_id

GROUP BY
    cl.cluster_id,
    cl.cluster_name,
    cl.kubernetes_version;

-- ============================================================
-- 25. SAMPLE CLUSTER
-- ============================================================

INSERT INTO clusters (
    cluster_name,
    kubernetes_version,
    environment,
    region,
    control_plane_endpoint
)
VALUES
(
    'production-cluster',
    'v1.32.0',
    'production',
    'ap-south-1',
    'https://api.production.example.internal'
),
(
    'staging-cluster',
    'v1.32.0',
    'staging',
    'ap-south-1',
    'https://api.staging.example.internal'
);

INSERT INTO namespaces (
    cluster_id,
    namespace_name
)
SELECT cluster_id, 'production'
FROM clusters
WHERE cluster_name = 'production-cluster';

INSERT INTO namespaces (
    cluster_id,
    namespace_name
)
SELECT cluster_id, 'monitoring'
FROM clusters
WHERE cluster_name = 'production-cluster';

-- ============================================================
-- 26. COMPONENT REGISTRATION
-- ============================================================

INSERT INTO control_plane_components (
    cluster_id,
    component_name,
    component_type,
    version,
    status,
    endpoint,
    started_at,
    last_heartbeat
)
SELECT
    cluster_id,
    component_name,
    component_type,
    'v1.32.0',
    'HEALTHY',
    endpoint,
    NOW() - INTERVAL '2 days',
    NOW()
FROM clusters
CROSS JOIN (
    VALUES
        (
            'kube-apiserver',
            'API_SERVER'::component_type,
            'https://api.example.internal'
        ),
        (
            'kube-scheduler',
            'SCHEDULER'::component_type,
            NULL
        ),
        (
            'kube-controller-manager',
            'CONTROLLER_MANAGER'::component_type,
            NULL
        ),
        (
            'etcd',
            'ETCD'::component_type,
            NULL
        )
) AS component_data(
    component_name,
    component_type,
    endpoint
)
WHERE cluster_name = 'production-cluster';

-- Simulated degraded scheduler in staging.
INSERT INTO control_plane_components (
    cluster_id,
    component_name,
    component_type,
    version,
    status,
    last_heartbeat
)
SELECT
    cluster_id,
    'kube-scheduler',
    'SCHEDULER',
    'v1.32.0',
    'DEGRADED',
    NOW()
FROM clusters
WHERE cluster_name = 'staging-cluster';

-- ============================================================
-- 27. NODE REGISTRATION
-- ============================================================

INSERT INTO nodes (
    cluster_id,
    node_name,
    node_role,
    status,
    cpu_capacity,
    memory_capacity_mb,
    kubelet_version,
    last_heartbeat
)
SELECT
    cluster_id,
    node_name,
    'WORKER',
    status,
    cpu_capacity,
    memory_capacity,
    'v1.32.0',
    NOW()
FROM clusters
CROSS JOIN (
    VALUES
        (
            'worker-01',
            'READY'::node_status,
            8,
            8192
        ),
        (
            'worker-02',
            'READY'::node_status,
            4,
            4096
        ),
        (
            'worker-03',
            'NOT_READY'::node_status,
            8,
            16384
        )
) AS node_data(
    node_name,
    status,
    cpu_capacity,
    memory_capacity
)
WHERE cluster_name = 'production-cluster';

-- ============================================================
-- 28. OPERATIONAL POLICIES
-- ============================================================

INSERT INTO control_plane_policies (
    cluster_id,
    policy_name,
    require_api_server,
    require_scheduler,
    require_controller_manager,
    require_etcd,
    reject_degraded_components,
    minimum_ready_nodes,
    maximum_heartbeat_age_seconds
)
SELECT
    cluster_id,
    'production-availability-policy',
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    2,
    30
FROM clusters
WHERE cluster_name = 'production-cluster';

INSERT INTO control_plane_policies (
    cluster_id,
    policy_name,
    require_api_server,
    require_scheduler,
    require_controller_manager,
    require_etcd,
    reject_degraded_components,
    minimum_ready_nodes,
    maximum_heartbeat_age_seconds,
    allow_degraded_operation
)
SELECT
    cluster_id,
    'staging-policy',
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    FALSE,
    0,
    60,
    TRUE
FROM clusters
WHERE cluster_name = 'staging-cluster';

-- ============================================================
-- 29. DEPLOYMENT AND POD SAMPLE DATA
-- ============================================================

INSERT INTO deployments (
    namespace_id,
    deployment_name,
    container_image,
    desired_replicas,
    observed_replicas,
    ready_replicas,
    cpu_request,
    memory_request_mb,
    status,
    generation,
    observed_generation
)
SELECT
    ns.namespace_id,
    'web',
    'nginx:1.27',
    3,
    2,
    2,
    1,
    256,
    'DEGRADED',
    3,
    2
FROM namespaces ns
JOIN clusters cl
    ON cl.cluster_id = ns.cluster_id
WHERE cl.cluster_name = 'production-cluster'
  AND ns.namespace_name = 'production';

INSERT INTO pods (
    namespace_id,
    deployment_id,
    pod_name,
    phase,
    assigned_node_id
)
SELECT
    d.namespace_id,
    d.deployment_id,
    pod_data.pod_name,
    pod_data.phase,
    n.node_id
FROM deployments d
JOIN namespaces ns
    ON ns.namespace_id = d.namespace_id
JOIN clusters cl
    ON cl.cluster_id = ns.cluster_id
CROSS JOIN (
    VALUES
        ('web-0', 'RUNNING'::pod_phase, 'worker-01'),
        ('web-1', 'RUNNING'::pod_phase, 'worker-02'),
        ('web-2', 'PENDING'::pod_phase, NULL::VARCHAR)
) AS pod_data(pod_name, phase, node_name)
LEFT JOIN nodes n
    ON n.cluster_id = cl.cluster_id
   AND n.node_name = pod_data.node_name
WHERE d.deployment_name = 'web'
  AND cl.cluster_name = 'production-cluster';

INSERT INTO containers (
    pod_id,
    container_name,
    image,
    cpu_request,
    memory_request_mb
)
SELECT
    pod_id,
    'application',
    'nginx:1.27',
    1,
    256
FROM pods
WHERE pod_name IN ('web-0', 'web-1', 'web-2');

-- ============================================================
-- 30. INITIAL RESOURCE ALLOCATION
-- ============================================================

UPDATE nodes n
SET cpu_allocated = allocation.cpu,
    memory_allocated_mb = allocation.memory
FROM (
    SELECT
        p.assigned_node_id,
        SUM(c.cpu_request)::INTEGER AS cpu,
        SUM(c.memory_request_mb)::INTEGER AS memory
    FROM pods p
    JOIN containers c
        ON c.pod_id = p.pod_id
    WHERE p.phase = 'RUNNING'
    GROUP BY p.assigned_node_id
) allocation
WHERE n.node_id = allocation.assigned_node_id;

-- ============================================================
-- 31. HEARTBEAT SAMPLE DATA
-- ============================================================

INSERT INTO component_heartbeats (
    component_id,
    received_at,
    response_time_ms,
    successful,
    message
)
SELECT
    component_id,
    NOW(),
    12,
    TRUE,
    'Health check successful'
FROM control_plane_components
WHERE status = 'HEALTHY';

INSERT INTO component_heartbeats (
    component_id,
    received_at,
    response_time_ms,
    successful,
    message
)
SELECT
    component_id,
    NOW() - INTERVAL '5 minutes',
    2500,
    FALSE,
    'Intermittent scheduling latency'
FROM control_plane_components
WHERE component_name = 'kube-scheduler'
  AND cluster_id = (
      SELECT cluster_id
      FROM clusters
      WHERE cluster_name = 'staging-cluster'
  );

-- ============================================================
-- 32. LEADER ELECTION SAMPLE
-- ============================================================

INSERT INTO control_plane_leases (
    cluster_id,
    lease_name,
    holder_identity,
    acquired_at,
    renewed_at,
    lease_duration_seconds
)
SELECT
    cluster_id,
    'kube-controller-manager',
    'controller-manager-01',
    NOW() - INTERVAL '5 minutes',
    NOW(),
    15
FROM clusters
WHERE cluster_name = 'production-cluster';

-- ============================================================
-- 33. OPERATIONAL EVENTS
-- ============================================================

INSERT INTO control_plane_events (
    cluster_id,
    component_id,
    event_type,
    reason,
    message
)
SELECT
    c.cluster_id,
    c.component_id,
    'NORMAL',
    'ComponentStarted',
    'Control plane component registered'
FROM control_plane_components c
WHERE c.cluster_id = (
    SELECT cluster_id
    FROM clusters
    WHERE cluster_name = 'production-cluster'
);

INSERT INTO control_plane_events (
    cluster_id,
    event_type,
    reason,
    message
)
SELECT
    cluster_id,
    'WARNING',
    'NodeNotReady',
    'worker-03 is not reporting a ready condition'
FROM clusters
WHERE cluster_name = 'production-cluster';

-- ============================================================
-- 34. AUDIT SAMPLE
-- ============================================================

INSERT INTO operation_audit (
    cluster_id,
    actor,
    operation,
    resource_type,
    resource_identifier,
    status,
    details
)
SELECT
    cluster_id,
    'deployment-controller',
    'RECONCILE',
    'Deployment',
    'web',
    'COMPLETED',
    jsonb_build_object(
        'desired', 3,
        'observed', 2,
        'ready', 2
    )
FROM clusters
WHERE cluster_name = 'production-cluster';

-- ============================================================
-- 35. RETRIEVAL QUERIES
-- ============================================================

-- Retrieve control plane components.
SELECT
    cluster_name,
    component_name,
    component_type,
    version,
    status,
    last_heartbeat
FROM clusters cl
JOIN control_plane_components c
    ON c.cluster_id = cl.cluster_id
ORDER BY cluster_name, component_type;

-- Retrieve pods and their assigned nodes.
SELECT
    ns.namespace_name,
    p.pod_name,
    p.phase,
    n.node_name,
    p.resource_version
FROM pods p
JOIN namespaces ns
    ON ns.namespace_id = p.namespace_id
LEFT JOIN nodes n
    ON n.node_id = p.assigned_node_id
ORDER BY ns.namespace_name, p.pod_name;

-- ============================================================
-- 36. VALIDATION QUERIES
-- ============================================================

-- Pods without a node assignment.
SELECT
    pod_id,
    pod_name,
    phase
FROM pods
WHERE phase = 'RUNNING'
  AND assigned_node_id IS NULL;

-- Node resource utilization.
SELECT
    node_name,
    cpu_allocated,
    cpu_capacity,
    ROUND(
        100.0 * cpu_allocated / cpu_capacity,
        2
    ) AS cpu_utilization_percent,
    memory_allocated_mb,
    memory_capacity_mb,
    ROUND(
        100.0 * memory_allocated_mb / memory_capacity_mb,
        2
    ) AS memory_utilization_percent
FROM nodes
ORDER BY node_name;

-- Deployment generation drift.
SELECT
    deployment_name,
    generation,
    observed_generation,
    desired_replicas,
    observed_replicas
FROM deployments
WHERE generation <> observed_generation;

-- ============================================================
-- 37. AGGREGATION QUERIES
-- ============================================================

-- Pod distribution by phase.
SELECT
    ns.namespace_name,
    p.phase,
    COUNT(*) AS pod_count
FROM pods p
JOIN namespaces ns
    ON ns.namespace_id = p.namespace_id
GROUP BY ns.namespace_name, p.phase
ORDER BY ns.namespace_name, p.phase;

-- Component availability by cluster.
SELECT
    cl.cluster_name,
    COUNT(*) AS total_components,
    COUNT(*) FILTER (
        WHERE c.status = 'HEALTHY'
    ) AS healthy,
    COUNT(*) FILTER (
        WHERE c.status = 'DEGRADED'
    ) AS degraded,
    COUNT(*) FILTER (
        WHERE c.status = 'UNAVAILABLE'
    ) AS unavailable
FROM clusters cl
LEFT JOIN control_plane_components c
    ON c.cluster_id = cl.cluster_id
GROUP BY cl.cluster_name;

-- ============================================================
-- 38. CTE: RESOURCE UTILIZATION
-- ============================================================

WITH node_usage AS (
    SELECT
        n.node_id,
        n.node_name,
        n.cpu_capacity,
        n.cpu_allocated,
        n.memory_capacity_mb,
        n.memory_allocated_mb
    FROM nodes n
),
usage_percentages AS (
    SELECT
        node_name,
        ROUND(
            100.0 * cpu_allocated / cpu_capacity,
            2
        ) AS cpu_percent,
        ROUND(
            100.0 * memory_allocated_mb /
                memory_capacity_mb,
            2
        ) AS memory_percent
    FROM node_usage
)
SELECT
    node_name,
    cpu_percent,
    memory_percent,
    CASE
        WHEN cpu_percent >= 90 OR memory_percent >= 90
            THEN 'HIGH'
        WHEN cpu_percent >= 70 OR memory_percent >= 70
            THEN 'MODERATE'
        ELSE 'NORMAL'
    END AS capacity_condition
FROM usage_percentages
ORDER BY cpu_percent DESC;

-- ============================================================
-- 39. DEPLOYMENT RECONCILIATION
-- ============================================================

SELECT *
FROM reconcile_deployment(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'web'
        LIMIT 1
    )
);

-- ============================================================
-- 40. COMPONENT HEALTH EVALUATION
-- ============================================================

SELECT
    cl.cluster_name,
    evaluation.component_name,
    evaluation.component_status,
    evaluation.heartbeat_age_seconds,
    evaluation.evaluation
FROM clusters cl
CROSS JOIN LATERAL evaluate_control_plane(cl.cluster_id)
    AS evaluation
ORDER BY cl.cluster_name, evaluation.component_name;

-- ============================================================
-- 41. CONTROL PLANE GOVERNANCE
-- ============================================================

SELECT
    cl.cluster_name,
    policy.policy_name,
    policy.eligible,
    policy.violations
FROM clusters cl
CROSS JOIN LATERAL evaluate_cluster_policy(cl.cluster_id)
    AS policy
ORDER BY cl.cluster_name, policy.policy_name;

-- ============================================================
-- 42. EVENT REPORT
-- ============================================================

SELECT
    cl.cluster_name,
    e.event_type,
    e.reason,
    e.message,
    e.occurred_at
FROM control_plane_events e
JOIN clusters cl
    ON cl.cluster_id = e.cluster_id
ORDER BY e.occurred_at DESC;

-- ============================================================
-- 43. TRANSACTIONAL SCHEDULING EXAMPLE
-- ============================================================

-- The following transaction demonstrates atomic scheduling.
-- It selects a pending pod and a feasible worker.
-- Row locks protect resource accounting.
--
-- The procedure raises an exception if allocation is unsafe.

DO $$
DECLARE
    v_pod_id BIGINT;
    v_node_id BIGINT;
BEGIN
    SELECT p.pod_id
    INTO v_pod_id
    FROM pods p
    WHERE p.phase = 'PENDING'
      AND p.pod_name = 'web-2'
    FOR UPDATE;

    IF v_pod_id IS NULL THEN
        RAISE NOTICE 'No pending web-2 pod';
    ELSE
        SELECT n.node_id
        INTO v_node_id
        FROM nodes n
        WHERE n.status = 'READY'
          AND node_can_schedule_pod(v_pod_id, n.node_id)
        ORDER BY
            (n.cpu_capacity - n.cpu_allocated),
            n.node_name
        LIMIT 1
        FOR UPDATE;

        IF v_node_id IS NULL THEN
            INSERT INTO scheduling_attempts (
                pod_id,
                attempt_number,
                status,
                reason
            )
            VALUES (
                v_pod_id,
                COALESCE(
                    (
                        SELECT MAX(attempt_number) + 1
                        FROM scheduling_attempts
                        WHERE pod_id = v_pod_id
                    ),
                    1
                ),
                'UNSCHEDULABLE',
                'No ready node has sufficient capacity'
            );

            RAISE NOTICE 'Pod is unschedulable';
        ELSE
            CALL schedule_pod(v_pod_id, v_node_id);

            RAISE NOTICE 'Pod scheduled successfully';
        END IF;
    END IF;
END;
$$;

-- ============================================================
-- 44. FAILURE SCENARIO: CONTROL PLANE COMPONENT OUTAGE
-- ============================================================

-- Simulate an etcd outage.
UPDATE control_plane_components
SET status = 'UNAVAILABLE',
    last_heartbeat = NOW() - INTERVAL '10 minutes'
WHERE component_name = 'etcd'
  AND cluster_id = (
      SELECT cluster_id
      FROM clusters
      WHERE cluster_name = 'production-cluster'
  );

INSERT INTO control_plane_events (
    cluster_id,
    component_id,
    event_type,
    reason,
    message
)
SELECT
    cluster_id,
    component_id,
    'ERROR',
    'EtcdUnavailable',
    'Persistent control plane storage is unavailable'
FROM control_plane_components
WHERE component_name = 'etcd'
  AND cluster_id = (
      SELECT cluster_id
      FROM clusters
      WHERE cluster_name = 'production-cluster'
  );

-- Confirm policy rejection.
SELECT
    policy_name,
    eligible,
    violations
FROM evaluate_cluster_policy(
    (
        SELECT cluster_id
        FROM clusters
        WHERE cluster_name = 'production-cluster'
    )
);

-- ============================================================
-- 45. FAILURE RECOVERY
-- ============================================================

UPDATE control_plane_components
SET status = 'HEALTHY',
    last_heartbeat = NOW()
WHERE component_name = 'etcd'
  AND cluster_id = (
      SELECT cluster_id
      FROM clusters
      WHERE cluster_name = 'production-cluster'
  );

INSERT INTO component_heartbeats (
    component_id,
    received_at,
    response_time_ms,
    successful,
    message
)
SELECT
    component_id,
    NOW(),
    15,
    TRUE,
    'Etcd service recovered'
FROM control_plane_components
WHERE component_name = 'etcd'
  AND cluster_id = (
      SELECT cluster_id
      FROM clusters
      WHERE cluster_name = 'production-cluster'
  );

-- ============================================================
-- 46. FINAL REPORT
-- ============================================================

SELECT *
FROM cluster_control_plane_summary
ORDER BY cluster_name;

SELECT
    n.node_name,
    n.status,
    n.cpu_allocated,
    n.cpu_capacity,
    n.memory_allocated_mb,
    n.memory_capacity_mb
FROM nodes n
ORDER BY n.node_name;

SELECT
    operation,
    resource_type,
    status,
    COUNT(*) AS operations
FROM operation_audit
GROUP BY operation, resource_type, status
ORDER BY operation, resource_type;

COMMIT;
