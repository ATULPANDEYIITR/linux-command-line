-- ============================================================
-- KUBERNETES POD MANAGEMENT AND WORKLOAD DEPLOYMENT
-- PostgreSQL 15+
--
-- Domain coverage:
-- 1. Clusters and worker nodes
-- 2. Namespaces
-- 3. Container specifications
-- 4. Pod specifications and lifecycle
-- 5. Init containers and application containers
-- 6. Resource requests and limits
-- 7. Scheduling and node allocations
-- 8. Deployments and replicas
-- 9. ReplicaSet-like ownership
-- 10. Readiness and liveness probes
-- 11. Pod conditions and events
-- 12. Restart policies
-- 13. Rolling updates
-- 14. Operational reporting
--
-- This schema models workload-management records.
-- It does not replace the Kubernetes API server,
-- scheduler, controller manager, or etcd.
-- ============================================================


-- ============================================================
-- 1. SCHEMA
-- ============================================================

DROP SCHEMA IF EXISTS pod_management CASCADE;

CREATE SCHEMA pod_management;

SET search_path TO pod_management, public;


-- ============================================================
-- 2. ENUM TYPES
-- ============================================================

CREATE TYPE pod_phase AS ENUM (
    'Pending',
    'Running',
    'Succeeded',
    'Failed',
    'Unknown'
);

CREATE TYPE container_state AS ENUM (
    'Waiting',
    'Running',
    'Terminated'
);

CREATE TYPE restart_policy AS ENUM (
    'Always',
    'OnFailure',
    'Never'
);

CREATE TYPE workload_type AS ENUM (
    'Deployment',
    'Job',
    'DaemonSet',
    'StatefulSet'
);

CREATE TYPE container_role AS ENUM (
    'Application',
    'Init'
);

CREATE TYPE condition_status AS ENUM (
    'True',
    'False',
    'Unknown'
);

CREATE TYPE event_type AS ENUM (
    'Normal',
    'Warning'
);

CREATE TYPE rollout_status AS ENUM (
    'Pending',
    'Progressing',
    'Completed',
    'Failed',
    'RolledBack'
);


-- ============================================================
-- 3. CLUSTER AND NODE MANAGEMENT
-- ============================================================

CREATE TABLE clusters (
    cluster_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_name VARCHAR(100) NOT NULL UNIQUE,

    environment VARCHAR(30) NOT NULL,

    api_endpoint TEXT NOT NULL,

    kubernetes_version VARCHAR(30) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'Active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_cluster_status
        CHECK (status IN ('Active', 'Inactive', 'Maintenance'))
);


CREATE TABLE worker_nodes (
    node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES clusters(cluster_id),

    node_name VARCHAR(100) NOT NULL,

    cpu_capacity NUMERIC(10,3) NOT NULL,

    memory_capacity_mib BIGINT NOT NULL,

    cpu_allocatable NUMERIC(10,3) NOT NULL,

    memory_allocatable_mib BIGINT NOT NULL,

    node_ready BOOLEAN NOT NULL DEFAULT TRUE,

    labels JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_node_per_cluster
        UNIQUE (cluster_id, node_name),

    CONSTRAINT valid_node_resources
        CHECK (
            cpu_capacity > 0
            AND memory_capacity_mib > 0
            AND cpu_allocatable >= 0
            AND memory_allocatable_mib >= 0
            AND cpu_allocatable <= cpu_capacity
            AND memory_allocatable_mib <= memory_capacity_mib
        )
);


-- ============================================================
-- 4. NAMESPACES
-- ============================================================

CREATE TABLE namespaces (
    namespace_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES clusters(cluster_id),

    namespace_name VARCHAR(63) NOT NULL,

    environment VARCHAR(30) NOT NULL,

    resource_quota_cpu NUMERIC(10,3),

    resource_quota_memory_mib BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_namespace
        UNIQUE (cluster_id, namespace_name),

    CONSTRAINT valid_namespace_quota
        CHECK (
            (resource_quota_cpu IS NULL OR resource_quota_cpu > 0)
            AND
            (resource_quota_memory_mib IS NULL
                OR resource_quota_memory_mib > 0)
        )
);


-- ============================================================
-- 5. WORKLOAD CONTROLLERS
-- ============================================================

CREATE TABLE workloads (
    workload_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL
        REFERENCES namespaces(namespace_id),

    workload_name VARCHAR(120) NOT NULL,

    workload_kind workload_type NOT NULL,

    desired_replicas INTEGER NOT NULL DEFAULT 1,

    current_generation INTEGER NOT NULL DEFAULT 1,

    observed_generation INTEGER NOT NULL DEFAULT 0,

    selector JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_workload_name
        UNIQUE (namespace_id, workload_name),

    CONSTRAINT valid_replica_count
        CHECK (desired_replicas >= 0),

    CONSTRAINT valid_generation
        CHECK (
            current_generation > 0
            AND observed_generation >= 0
        )
);


-- ============================================================
-- 6. CONTAINER SPECIFICATIONS
-- ============================================================

CREATE TABLE container_specs (
    container_spec_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    workload_id BIGINT NOT NULL
        REFERENCES workloads(workload_id)
        ON DELETE CASCADE,

    container_name VARCHAR(100) NOT NULL,

    container_image TEXT NOT NULL,

    image_pull_policy VARCHAR(20) NOT NULL DEFAULT 'IfNotPresent',

    role container_role NOT NULL DEFAULT 'Application',

    cpu_request NUMERIC(10,3) NOT NULL DEFAULT 0.1,

    cpu_limit NUMERIC(10,3) NOT NULL DEFAULT 0.5,

    memory_request_mib BIGINT NOT NULL DEFAULT 128,

    memory_limit_mib BIGINT NOT NULL DEFAULT 512,

    environment JSONB NOT NULL DEFAULT '{}'::JSONB,

    execution_order INTEGER NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_container_spec
        UNIQUE (workload_id, container_name),

    CONSTRAINT valid_container_image
        CHECK (
            LENGTH(TRIM(container_image)) > 0
            AND container_image !~ '[[:space:]]'
        ),

    CONSTRAINT valid_pull_policy
        CHECK (
            image_pull_policy IN (
                'Always',
                'IfNotPresent',
                'Never'
            )
        ),

    CONSTRAINT valid_container_resources
        CHECK (
            cpu_request >= 0
            AND cpu_limit > 0
            AND cpu_request <= cpu_limit
            AND memory_request_mib >= 0
            AND memory_limit_mib > 0
            AND memory_request_mib <= memory_limit_mib
        ),

    CONSTRAINT valid_execution_order
        CHECK (execution_order > 0)
);


-- ============================================================
-- 7. PODS
-- ============================================================

CREATE TABLE pods (
    pod_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL
        REFERENCES namespaces(namespace_id),

    workload_id BIGINT
        REFERENCES workloads(workload_id)
        ON DELETE SET NULL,

    node_id BIGINT
        REFERENCES worker_nodes(node_id)
        ON DELETE SET NULL,

    pod_name VARCHAR(120) NOT NULL,

    uid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    phase pod_phase NOT NULL DEFAULT 'Pending',

    restart_policy restart_policy NOT NULL DEFAULT 'Always',

    labels JSONB NOT NULL DEFAULT '{}'::JSONB,

    annotations JSONB NOT NULL DEFAULT '{}'::JSONB,

    creation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    start_timestamp TIMESTAMPTZ,

    completion_timestamp TIMESTAMPTZ,

    deletion_timestamp TIMESTAMPTZ,

    CONSTRAINT unique_pod_name
        UNIQUE (namespace_id, pod_name),

    CONSTRAINT valid_pod_completion
        CHECK (
            completion_timestamp IS NULL
            OR start_timestamp IS NOT NULL
        )
);


CREATE INDEX idx_pods_namespace_phase
    ON pods(namespace_id, phase);


CREATE INDEX idx_pods_node_phase
    ON pods(node_id, phase);


CREATE INDEX idx_pods_workload
    ON pods(workload_id);


CREATE INDEX idx_pods_labels
    ON pods USING GIN(labels);


-- ============================================================
-- 8. POD CONTAINERS
-- ============================================================

CREATE TABLE pod_containers (
    pod_container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_id BIGINT NOT NULL
        REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    container_spec_id BIGINT
        REFERENCES container_specs(container_spec_id)
        ON DELETE SET NULL,

    container_name VARCHAR(100) NOT NULL,

    container_image TEXT NOT NULL,

    role container_role NOT NULL DEFAULT 'Application',

    state container_state NOT NULL DEFAULT 'Waiting',

    ready BOOLEAN NOT NULL DEFAULT FALSE,

    restart_count INTEGER NOT NULL DEFAULT 0,

    exit_code INTEGER,

    started_at TIMESTAMPTZ,

    terminated_at TIMESTAMPTZ,

    CONSTRAINT unique_container_per_pod
        UNIQUE (pod_id, container_name),

    CONSTRAINT valid_restart_count
        CHECK (restart_count >= 0)
);


CREATE INDEX idx_pod_containers_state
    ON pod_containers(pod_id, state);


-- ============================================================
-- 9. POD CONDITIONS
-- ============================================================

CREATE TABLE pod_conditions (
    condition_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_id BIGINT NOT NULL
        REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    condition_type VARCHAR(50) NOT NULL,

    status condition_status NOT NULL,

    reason VARCHAR(120),

    message TEXT,

    last_transition_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_pod_condition
        UNIQUE (pod_id, condition_type),

    CONSTRAINT valid_condition_type
        CHECK (
            condition_type IN (
                'PodScheduled',
                'Initialized',
                'ContainersReady',
                'Ready'
            )
        )
);


-- ============================================================
-- 10. PROBES
-- ============================================================

CREATE TABLE container_probes (
    probe_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_container_id BIGINT NOT NULL
        REFERENCES pod_containers(pod_container_id)
        ON DELETE CASCADE,

    probe_type VARCHAR(20) NOT NULL,

    http_path TEXT,

    initial_delay_seconds INTEGER NOT NULL DEFAULT 0,

    period_seconds INTEGER NOT NULL DEFAULT 10,

    timeout_seconds INTEGER NOT NULL DEFAULT 1,

    failure_threshold INTEGER NOT NULL DEFAULT 3,

    last_success BOOLEAN,

    last_execution TIMESTAMPTZ,

    CONSTRAINT unique_probe_per_type
        UNIQUE (pod_container_id, probe_type),

    CONSTRAINT valid_probe_type
        CHECK (
            probe_type IN (
                'Startup',
                'Readiness',
                'Liveness'
            )
        ),

    CONSTRAINT valid_probe_configuration
        CHECK (
            initial_delay_seconds >= 0
            AND period_seconds > 0
            AND timeout_seconds > 0
            AND failure_threshold > 0
        ),

    CONSTRAINT valid_http_path
        CHECK (
            http_path IS NULL
            OR http_path LIKE '/%'
        )
);


-- ============================================================
-- 11. POD EVENTS
-- ============================================================

CREATE TABLE pod_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_id BIGINT NOT NULL
        REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    event_type event_type NOT NULL,

    reason VARCHAR(120) NOT NULL,

    message TEXT NOT NULL,

    occurrence_count INTEGER NOT NULL DEFAULT 1,

    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_event_count
        CHECK (occurrence_count > 0)
);


CREATE INDEX idx_pod_events_timestamp
    ON pod_events(pod_id, event_timestamp DESC);


-- ============================================================
-- 12. NODE ALLOCATIONS
-- ============================================================

CREATE TABLE node_allocations (
    allocation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    node_id BIGINT NOT NULL
        REFERENCES worker_nodes(node_id),

    pod_id BIGINT NOT NULL
        REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    cpu_reserved NUMERIC(10,3) NOT NULL,

    memory_reserved_mib BIGINT NOT NULL,

    allocated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    released_at TIMESTAMPTZ,

    CONSTRAINT valid_allocation
        CHECK (
            cpu_reserved >= 0
            AND memory_reserved_mib >= 0
        ),

    CONSTRAINT unique_active_pod_allocation
        UNIQUE (pod_id)
);


CREATE INDEX idx_node_allocations_active
    ON node_allocations(node_id)
    WHERE released_at IS NULL;


-- ============================================================
-- 13. ROLLING UPDATE RECORDS
-- ============================================================

CREATE TABLE rollout_history (
    rollout_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    workload_id BIGINT NOT NULL
        REFERENCES workloads(workload_id)
        ON DELETE CASCADE,

    previous_generation INTEGER NOT NULL,

    new_generation INTEGER NOT NULL,

    previous_image TEXT,

    new_image TEXT NOT NULL,

    rollout_status rollout_status NOT NULL DEFAULT 'Pending',

    desired_replicas INTEGER NOT NULL,

    updated_replicas INTEGER NOT NULL DEFAULT 0,

    available_replicas INTEGER NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    CONSTRAINT valid_rollout_generation
        CHECK (new_generation > previous_generation),

    CONSTRAINT valid_rollout_counts
        CHECK (
            desired_replicas >= 0
            AND updated_replicas >= 0
            AND available_replicas >= 0
        )
);


-- ============================================================
-- 14. AUTOMATIC TIMESTAMP MANAGEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION update_modified_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_workload_updated_at
BEFORE UPDATE ON workloads
FOR EACH ROW
EXECUTE FUNCTION update_modified_timestamp();


-- ============================================================
-- 15. RESOURCE REQUEST AGGREGATION
-- ============================================================

CREATE OR REPLACE FUNCTION calculate_workload_resources(
    p_workload_id BIGINT
)
RETURNS TABLE (
    requested_cpu NUMERIC,
    requested_memory_mib BIGINT
)
LANGUAGE SQL
STABLE
AS $$
    WITH application_resources AS (
        SELECT
            COALESCE(SUM(cpu_request), 0) AS cpu,
            COALESCE(SUM(memory_request_mib), 0) AS memory
        FROM container_specs
        WHERE workload_id = p_workload_id
          AND role = 'Application'
    ),
    init_resources AS (
        SELECT
            COALESCE(MAX(cpu_request), 0) AS cpu,
            COALESCE(MAX(memory_request_mib), 0) AS memory
        FROM container_specs
        WHERE workload_id = p_workload_id
          AND role = 'Init'
    )
    SELECT
        GREATEST(a.cpu, i.cpu),
        GREATEST(a.memory, i.memory)
    FROM application_resources a
    CROSS JOIN init_resources i;
$$;


-- ============================================================
-- 16. NODE SCHEDULING VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_node_capacity(
    p_node_id BIGINT,
    p_cpu NUMERIC,
    p_memory BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_cpu_capacity NUMERIC;
    v_memory_capacity BIGINT;
    v_allocated_cpu NUMERIC;
    v_allocated_memory BIGINT;
BEGIN
    SELECT
        cpu_allocatable,
        memory_allocatable_mib
    INTO
        v_cpu_capacity,
        v_memory_capacity
    FROM worker_nodes
    WHERE node_id = p_node_id
      AND node_ready = TRUE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    SELECT
        COALESCE(SUM(cpu_reserved), 0),
        COALESCE(SUM(memory_reserved_mib), 0)
    INTO
        v_allocated_cpu,
        v_allocated_memory
    FROM node_allocations
    WHERE node_id = p_node_id
      AND released_at IS NULL;

    RETURN (
        v_allocated_cpu + p_cpu <= v_cpu_capacity
        AND
        v_allocated_memory + p_memory <= v_memory_capacity
    );
END;
$$;


-- ============================================================
-- 17. POD SCHEDULING PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE schedule_pod(
    p_pod_id BIGINT,
    p_node_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_workload_id BIGINT;
    v_cpu NUMERIC;
    v_memory BIGINT;
    v_namespace_cluster BIGINT;
    v_node_cluster BIGINT;
BEGIN
    SELECT
        p.workload_id,
        n.cluster_id
    INTO
        v_workload_id,
        v_namespace_cluster
    FROM pods p
    JOIN namespaces n
      ON n.namespace_id = p.namespace_id
    WHERE p.pod_id = p_pod_id
      AND p.phase = 'Pending'
      AND p.node_id IS NULL
    FOR UPDATE OF p;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Pod does not exist or is not schedulable';
    END IF;

    SELECT cluster_id
    INTO v_node_cluster
    FROM worker_nodes
    WHERE node_id = p_node_id
      AND node_ready = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Worker node does not exist or is not ready';
    END IF;

    IF v_namespace_cluster <> v_node_cluster THEN
        RAISE EXCEPTION
            'Pod and node belong to different clusters';
    END IF;

    IF v_workload_id IS NULL THEN
        RAISE EXCEPTION
            'Pod must belong to a workload for this procedure';
    END IF;

    SELECT requested_cpu, requested_memory_mib
    INTO v_cpu, v_memory
    FROM calculate_workload_resources(v_workload_id);

    IF NOT validate_node_capacity(
        p_node_id,
        v_cpu,
        v_memory
    ) THEN
        RAISE EXCEPTION
            'Insufficient node resources';
    END IF;

    INSERT INTO node_allocations (
        node_id,
        pod_id,
        cpu_reserved,
        memory_reserved_mib
    )
    VALUES (
        p_node_id,
        p_pod_id,
        v_cpu,
        v_memory
    );

    UPDATE pods
    SET node_id = p_node_id
    WHERE pod_id = p_pod_id;

    INSERT INTO pod_conditions (
        pod_id,
        condition_type,
        status,
        reason,
        message
    )
    VALUES (
        p_pod_id,
        'PodScheduled',
        'True',
        'Scheduled',
        'Pod assigned to a worker node'
    )
    ON CONFLICT (pod_id, condition_type)
    DO UPDATE SET
        status = 'True',
        reason = 'Scheduled',
        message = 'Pod assigned to a worker node',
        last_transition_time = NOW();

    INSERT INTO pod_events (
        pod_id,
        event_type,
        reason,
        message
    )
    VALUES (
        p_pod_id,
        'Normal',
        'Scheduled',
        'Pod successfully assigned to worker node'
    );
END;
$$;


-- ============================================================
-- 18. POD READINESS EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_pod_readiness(
    p_pod_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_total INTEGER;
    v_ready INTEGER;
    v_running BOOLEAN;
    v_result BOOLEAN;
BEGIN
    SELECT phase = 'Running'
    INTO v_running
    FROM pods
    WHERE pod_id = p_pod_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pod does not exist';
    END IF;

    SELECT
        COUNT(*)::INTEGER,
        COUNT(*) FILTER (
            WHERE state = 'Running'
              AND ready = TRUE
        )::INTEGER
    INTO v_total, v_ready
    FROM pod_containers
    WHERE pod_id = p_pod_id
      AND role = 'Application';

    v_result := (
        v_running
        AND v_total > 0
        AND v_total = v_ready
    );

    INSERT INTO pod_conditions (
        pod_id,
        condition_type,
        status,
        reason,
        message
    )
    VALUES (
        p_pod_id,
        'ContainersReady',
        CASE WHEN v_result THEN 'True' ELSE 'False' END,
        'ContainerReadinessEvaluation',
        'Application container readiness evaluated'
    )
    ON CONFLICT (pod_id, condition_type)
    DO UPDATE SET
        status = EXCLUDED.status,
        reason = EXCLUDED.reason,
        message = EXCLUDED.message,
        last_transition_time = NOW();

    INSERT INTO pod_conditions (
        pod_id,
        condition_type,
        status,
        reason,
        message
    )
    VALUES (
        p_pod_id,
        'Ready',
        CASE WHEN v_result THEN 'True' ELSE 'False' END,
        'PodReadinessEvaluation',
        'Pod readiness evaluated'
    )
    ON CONFLICT (pod_id, condition_type)
    DO UPDATE SET
        status = EXCLUDED.status,
        reason = EXCLUDED.reason,
        message = EXCLUDED.message,
        last_transition_time = NOW();

    RETURN v_result;
END;
$$;


-- ============================================================
-- 19. CONTAINER RESTART PROCESSING
-- ============================================================

CREATE OR REPLACE PROCEDURE process_container_exit(
    p_pod_container_id BIGINT,
    p_exit_code INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_pod_id BIGINT;
    v_policy restart_policy;
    v_state container_state;
    v_should_restart BOOLEAN;
BEGIN
    SELECT
        pc.pod_id,
        pc.state,
        p.restart_policy
    INTO
        v_pod_id,
        v_state,
        v_policy
    FROM pod_containers pc
    JOIN pods p
      ON p.pod_id = pc.pod_id
    WHERE pc.pod_container_id = p_pod_container_id
    FOR UPDATE OF pc;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Container does not exist';
    END IF;

    IF v_state <> 'Running' THEN
        RAISE EXCEPTION 'Container is not running';
    END IF;

    UPDATE pod_containers
    SET
        state = 'Terminated',
        ready = FALSE,
        exit_code = p_exit_code,
        terminated_at = NOW()
    WHERE pod_container_id = p_pod_container_id;

    v_should_restart := (
        v_policy = 'Always'
        OR (
            v_policy = 'OnFailure'
            AND p_exit_code <> 0
        )
    );

    IF v_should_restart THEN
        UPDATE pod_containers
        SET
            state = 'Waiting',
            restart_count = restart_count + 1,
            exit_code = NULL,
            terminated_at = NULL
        WHERE pod_container_id = p_pod_container_id;

        INSERT INTO pod_events (
            pod_id,
            event_type,
            reason,
            message
        )
        VALUES (
            v_pod_id,
            'Warning',
            'ContainerRestart',
            'Container restart scheduled after termination'
        );
    ELSE
        INSERT INTO pod_events (
            pod_id,
            event_type,
            reason,
            message
        )
        VALUES (
            v_pod_id,
            'Normal',
            'ContainerTerminated',
            'Container terminated without restart'
        );
    END IF;

    PERFORM evaluate_pod_readiness(v_pod_id);
END;
$$;


-- ============================================================
-- 20. POD LIFECYCLE REPORTING VIEW
-- ============================================================

CREATE OR REPLACE VIEW pod_lifecycle_report AS
SELECT
    p.pod_id,
    p.pod_name,
    n.namespace_name,
    p.phase,
    p.restart_policy,
    w.workload_name,
    wn.node_name,

    COUNT(pc.pod_container_id) AS container_count,

    COUNT(pc.pod_container_id) FILTER (
        WHERE pc.role = 'Application'
    ) AS application_container_count,

    COUNT(pc.pod_container_id) FILTER (
        WHERE pc.state = 'Running'
    ) AS running_container_count,

    COUNT(pc.pod_container_id) FILTER (
        WHERE pc.ready = TRUE
    ) AS ready_container_count,

    COALESCE(SUM(pc.restart_count), 0) AS total_restarts,

    EXISTS (
        SELECT 1
        FROM pod_conditions condition
        WHERE condition.pod_id = p.pod_id
          AND condition.condition_type = 'Ready'
          AND condition.status = 'True'
    ) AS pod_ready,

    p.creation_timestamp

FROM pods p

JOIN namespaces n
  ON n.namespace_id = p.namespace_id

LEFT JOIN workloads w
  ON w.workload_id = p.workload_id

LEFT JOIN worker_nodes wn
  ON wn.node_id = p.node_id

LEFT JOIN pod_containers pc
  ON pc.pod_id = p.pod_id

GROUP BY
    p.pod_id,
    n.namespace_name,
    w.workload_name,
    wn.node_name;


-- ============================================================
-- 21. DEPLOYMENT STATUS VIEW
-- ============================================================

CREATE OR REPLACE VIEW deployment_status_report AS
SELECT
    w.workload_id,
    w.workload_name,
    n.namespace_name,
    w.workload_kind,
    w.desired_replicas,
    w.current_generation,
    w.observed_generation,

    COUNT(p.pod_id) FILTER (
        WHERE p.phase NOT IN ('Failed', 'Succeeded')
    ) AS active_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.phase = 'Running'
    ) AS running_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM pod_conditions pc
            WHERE pc.pod_id = p.pod_id
              AND pc.condition_type = 'Ready'
              AND pc.status = 'True'
        )
    ) AS ready_replicas,

    CASE
        WHEN COUNT(p.pod_id) FILTER (
            WHERE p.phase NOT IN ('Failed', 'Succeeded')
        ) = w.desired_replicas
        AND COUNT(p.pod_id) FILTER (
            WHERE EXISTS (
                SELECT 1
                FROM pod_conditions pc
                WHERE pc.pod_id = p.pod_id
                  AND pc.condition_type = 'Ready'
                  AND pc.status = 'True'
            )
        ) = w.desired_replicas
        THEN 'Available'
        ELSE 'Reconciling'
    END AS deployment_status

FROM workloads w

JOIN namespaces n
  ON n.namespace_id = w.namespace_id

LEFT JOIN pods p
  ON p.workload_id = w.workload_id

WHERE w.workload_kind = 'Deployment'

GROUP BY
    w.workload_id,
    n.namespace_name;


-- ============================================================
-- 22. SAMPLE CLUSTER DATA
-- ============================================================

INSERT INTO clusters (
    cluster_name,
    environment,
    api_endpoint,
    kubernetes_version
)
VALUES
(
    'production-cluster',
    'Production',
    'https://kubernetes.example.internal',
    '1.31'
),
(
    'staging-cluster',
    'Staging',
    'https://staging.example.internal',
    '1.31'
);


INSERT INTO worker_nodes (
    cluster_id,
    node_name,
    cpu_capacity,
    memory_capacity_mib,
    cpu_allocatable,
    memory_allocatable_mib,
    labels
)
SELECT
    cluster_id,
    'worker-01',
    8.0,
    16384,
    7.5,
    15360,
    '{"zone":"central","role":"worker"}'::JSONB
FROM clusters
WHERE cluster_name = 'production-cluster';


INSERT INTO worker_nodes (
    cluster_id,
    node_name,
    cpu_capacity,
    memory_capacity_mib,
    cpu_allocatable,
    memory_allocatable_mib,
    labels
)
SELECT
    cluster_id,
    'worker-02',
    4.0,
    8192,
    3.5,
    7168,
    '{"zone":"central","role":"worker"}'::JSONB
FROM clusters
WHERE cluster_name = 'production-cluster';


INSERT INTO worker_nodes (
    cluster_id,
    node_name,
    cpu_capacity,
    memory_capacity_mib,
    cpu_allocatable,
    memory_allocatable_mib
)
SELECT
    cluster_id,
    'staging-worker-01',
    4.0,
    8192,
    3.5,
    7168
FROM clusters
WHERE cluster_name = 'staging-cluster';


-- ============================================================
-- 23. SAMPLE NAMESPACES
-- ============================================================

INSERT INTO namespaces (
    cluster_id,
    namespace_name,
    environment,
    resource_quota_cpu,
    resource_quota_memory_mib
)
SELECT
    cluster_id,
    'production',
    'Production',
    12.0,
    24576
FROM clusters
WHERE cluster_name = 'production-cluster';


INSERT INTO namespaces (
    cluster_id,
    namespace_name,
    environment,
    resource_quota_cpu,
    resource_quota_memory_mib
)
SELECT
    cluster_id,
    'staging',
    'Staging',
    6.0,
    12288
FROM clusters
WHERE cluster_name = 'staging-cluster';


-- ============================================================
-- 24. SAMPLE WORKLOADS
-- ============================================================

INSERT INTO workloads (
    namespace_id,
    workload_name,
    workload_kind,
    desired_replicas,
    current_generation,
    observed_generation,
    selector
)
SELECT
    namespace_id,
    'frontend',
    'Deployment',
    3,
    1,
    1,
    '{"app":"frontend"}'::JSONB
FROM namespaces
WHERE namespace_name = 'production';


INSERT INTO workloads (
    namespace_id,
    workload_name,
    workload_kind,
    desired_replicas,
    current_generation,
    observed_generation,
    selector
)
SELECT
    namespace_id,
    'background-worker',
    'Deployment',
    2,
    1,
    1,
    '{"app":"background-worker"}'::JSONB
FROM namespaces
WHERE namespace_name = 'production';


INSERT INTO workloads (
    namespace_id,
    workload_name,
    workload_kind,
    desired_replicas,
    current_generation,
    observed_generation,
    selector
)
SELECT
    namespace_id,
    'data-processing',
    'Job',
    1,
    1,
    1,
    '{"job":"data-processing"}'::JSONB
FROM namespaces
WHERE namespace_name = 'production';


-- ============================================================
-- 25. SAMPLE CONTAINER SPECIFICATIONS
-- ============================================================

INSERT INTO container_specs (
    workload_id,
    container_name,
    container_image,
    role,
    cpu_request,
    cpu_limit,
    memory_request_mib,
    memory_limit_mib,
    environment,
    execution_order
)
SELECT
    workload_id,
    'web',
    'nginx:1.27',
    'Application',
    0.5,
    1.0,
    256,
    512,
    '{"APP_ENV":"production"}'::JSONB,
    1
FROM workloads
WHERE workload_name = 'frontend';


INSERT INTO container_specs (
    workload_id,
    container_name,
    container_image,
    role,
    cpu_request,
    cpu_limit,
    memory_request_mib,
    memory_limit_mib,
    execution_order
)
SELECT
    workload_id,
    'metrics',
    'busybox:1.36',
    'Application',
    0.1,
    0.2,
    64,
    128,
    2
FROM workloads
WHERE workload_name = 'frontend';


INSERT INTO container_specs (
    workload_id,
    container_name,
    container_image,
    role,
    cpu_request,
    cpu_limit,
    memory_request_mib,
    memory_limit_mib,
    execution_order
)
SELECT
    workload_id,
    'initialize',
    'busybox:1.36',
    'Init',
    0.2,
    0.5,
    128,
    256,
    1
FROM workloads
WHERE workload_name = 'frontend';


INSERT INTO container_specs (
    workload_id,
    container_name,
    container_image,
    role,
    cpu_request,
    cpu_limit,
    memory_request_mib,
    memory_limit_mib
)
SELECT
    workload_id,
    'processor',
    'python:3.13-slim',
    'Application',
    1.0,
    2.0,
    512,
    1024
FROM workloads
WHERE workload_name = 'background-worker';


-- ============================================================
-- 26. SAMPLE PODS
-- ============================================================

INSERT INTO pods (
    namespace_id,
    workload_id,
    pod_name,
    phase,
    restart_policy,
    labels
)
SELECT
    n.namespace_id,
    w.workload_id,
    'frontend-pod-01',
    'Running',
    'Always',
    '{"app":"frontend","version":"v1"}'::JSONB
FROM namespaces n
JOIN workloads w
  ON w.namespace_id = n.namespace_id
WHERE n.namespace_name = 'production'
  AND w.workload_name = 'frontend';


INSERT INTO pods (
    namespace_id,
    workload_id,
    pod_name,
    phase,
    restart_policy,
    labels
)
SELECT
    n.namespace_id,
    w.workload_id,
    'frontend-pod-02',
    'Running',
    'Always',
    '{"app":"frontend","version":"v1"}'::JSONB
FROM namespaces n
JOIN workloads w
  ON w.namespace_id = n.namespace_id
WHERE n.namespace_name = 'production'
  AND w.workload_name = 'frontend';


INSERT INTO pods (
    namespace_id,
    workload_id,
    pod_name,
    phase,
    restart_policy,
    labels
)
SELECT
    n.namespace_id,
    w.workload_id,
    'frontend-pod-03',
    'Pending',
    'Always',
    '{"app":"frontend","version":"v1"}'::JSONB
FROM namespaces n
JOIN workloads w
  ON w.namespace_id = n.namespace_id
WHERE n.namespace_name = 'production'
  AND w.workload_name = 'frontend';


INSERT INTO pods (
    namespace_id,
    workload_id,
    pod_name,
    phase,
    restart_policy,
    labels
)
SELECT
    n.namespace_id,
    w.workload_id,
    'worker-pod-01',
    'Running',
    'Always',
    '{"app":"background-worker"}'::JSONB
FROM namespaces n
JOIN workloads w
  ON w.namespace_id = n.namespace_id
WHERE n.namespace_name = 'production'
  AND w.workload_name = 'background-worker';


INSERT INTO pods (
    namespace_id,
    workload_id,
    pod_name,
    phase,
    restart_policy,
    labels
)
SELECT
    n.namespace_id,
    w.workload_id,
    'worker-pod-02',
    'Failed',
    'OnFailure',
    '{"app":"background-worker"}'::JSONB
FROM namespaces n
JOIN workloads w
  ON w.namespace_id = n.namespace_id
WHERE n.namespace_name = 'production'
  AND w.workload_name = 'background-worker';


-- ============================================================
-- 27. ASSIGN NODES TO EXISTING PODS
-- ============================================================

UPDATE pods p
SET node_id = wn.node_id
FROM namespaces n,
     worker_nodes wn
WHERE p.namespace_id = n.namespace_id
  AND wn.cluster_id = n.cluster_id
  AND (
      (p.pod_name = 'frontend-pod-01'
       AND wn.node_name = 'worker-01')
      OR
      (p.pod_name = 'frontend-pod-02'
       AND wn.node_name = 'worker-02')
      OR
      (p.pod_name = 'worker-pod-01'
       AND wn.node_name = 'worker-01')
  );


-- ============================================================
-- 28. POD CONTAINER INSTANCES
-- ============================================================

INSERT INTO pod_containers (
    pod_id,
    container_spec_id,
    container_name,
    container_image,
    role,
    state,
    ready,
    restart_count
)
SELECT
    p.pod_id,
    cs.container_spec_id,
    cs.container_name,
    cs.container_image,
    cs.role,
    CASE
        WHEN p.phase = 'Running'
             AND cs.role = 'Application'
        THEN 'Running'::container_state
        WHEN cs.role = 'Init'
        THEN 'Terminated'::container_state
        ELSE 'Waiting'::container_state
    END,
    (
        p.phase = 'Running'
        AND cs.role = 'Application'
    ),
    0
FROM pods p
JOIN workloads w
  ON w.workload_id = p.workload_id
JOIN container_specs cs
  ON cs.workload_id = w.workload_id
WHERE p.pod_name IN (
    'frontend-pod-01',
    'frontend-pod-02',
    'frontend-pod-03'
);


INSERT INTO pod_containers (
    pod_id,
    container_spec_id,
    container_name,
    container_image,
    role,
    state,
    ready,
    restart_count,
    exit_code
)
SELECT
    p.pod_id,
    cs.container_spec_id,
    cs.container_name,
    cs.container_image,
    cs.role,
    CASE
        WHEN p.phase = 'Running'
        THEN 'Running'::container_state
        ELSE 'Terminated'::container_state
    END,
    p.phase = 'Running',
    CASE
        WHEN p.phase = 'Failed' THEN 3
        ELSE 0
    END,
    CASE
        WHEN p.phase = 'Failed' THEN 137
        ELSE NULL
    END
FROM pods p
JOIN workloads w
  ON w.workload_id = p.workload_id
JOIN container_specs cs
  ON cs.workload_id = w.workload_id
WHERE p.pod_name IN (
    'worker-pod-01',
    'worker-pod-02'
);


-- ============================================================
-- 29. SAMPLE POD CONDITIONS
-- ============================================================

INSERT INTO pod_conditions (
    pod_id,
    condition_type,
    status,
    reason,
    message
)
SELECT
    pod_id,
    condition_type,
    CASE
        WHEN phase = 'Running'
        THEN 'True'::condition_status
        ELSE 'False'::condition_status
    END,
    'InitialCondition',
    'Initial sample condition'
FROM pods
CROSS JOIN (
    VALUES
        ('PodScheduled'),
        ('Initialized'),
        ('ContainersReady'),
        ('Ready')
) AS conditions(condition_type);


-- ============================================================
-- 30. SAMPLE PROBES
-- ============================================================

INSERT INTO container_probes (
    pod_container_id,
    probe_type,
    http_path,
    initial_delay_seconds,
    period_seconds,
    timeout_seconds,
    failure_threshold,
    last_success
)
SELECT
    pod_container_id,
    'Readiness',
    '/health',
    5,
    10,
    2,
    3,
    TRUE
FROM pod_containers
WHERE container_name = 'web'
  AND state = 'Running';


INSERT INTO container_probes (
    pod_container_id,
    probe_type,
    http_path,
    initial_delay_seconds,
    period_seconds,
    timeout_seconds,
    failure_threshold,
    last_success
)
SELECT
    pod_container_id,
    'Liveness',
    '/live',
    15,
    15,
    3,
    3,
    TRUE
FROM pod_containers
WHERE container_name = 'web'
  AND state = 'Running';


-- ============================================================
-- 31. SAMPLE EVENTS
-- ============================================================

INSERT INTO pod_events (
    pod_id,
    event_type,
    reason,
    message
)
SELECT
    pod_id,
    'Normal',
    'Scheduled',
    'Pod successfully assigned to worker node'
FROM pods
WHERE phase = 'Running';


INSERT INTO pod_events (
    pod_id,
    event_type,
    reason,
    message
)
SELECT
    pod_id,
    'Warning',
    'BackOff',
    'Container experienced repeated failures'
FROM pods
WHERE phase = 'Failed';


-- ============================================================
-- 32. SAMPLE ACTIVE NODE ALLOCATIONS
-- ============================================================

INSERT INTO node_allocations (
    node_id,
    pod_id,
    cpu_reserved,
    memory_reserved_mib
)
SELECT
    p.node_id,
    p.pod_id,
    r.requested_cpu,
    r.requested_memory_mib
FROM pods p
CROSS JOIN LATERAL
    calculate_workload_resources(p.workload_id) r
WHERE p.node_id IS NOT NULL;


-- ============================================================
-- 33. SAMPLE ROLLOUT HISTORY
-- ============================================================

INSERT INTO rollout_history (
    workload_id,
    previous_generation,
    new_generation,
    previous_image,
    new_image,
    rollout_status,
    desired_replicas,
    updated_replicas,
    available_replicas
)
SELECT
    workload_id,
    1,
    2,
    'nginx:1.26',
    'nginx:1.27',
    'Completed',
    3,
    3,
    2
FROM workloads
WHERE workload_name = 'frontend';


-- ============================================================
-- 34. QUERY: RETRIEVE PODS
-- ============================================================

SELECT
    pod_name,
    namespace_name,
    phase,
    node_name,
    pod_ready,
    total_restarts
FROM pod_lifecycle_report
ORDER BY creation_timestamp DESC;


-- ============================================================
-- 35. QUERY: CONTAINER STATE DISTRIBUTION
-- ============================================================

SELECT
    state,
    COUNT(*) AS container_count,
    COUNT(*) FILTER (
        WHERE ready = TRUE
    ) AS ready_count,
    SUM(restart_count) AS total_restarts
FROM pod_containers
GROUP BY state
ORDER BY state;


-- ============================================================
-- 36. QUERY: RESOURCE AGGREGATION
-- ============================================================

SELECT
    w.workload_name,
    r.requested_cpu,
    r.requested_memory_mib
FROM workloads w
CROSS JOIN LATERAL
    calculate_workload_resources(w.workload_id) r
ORDER BY w.workload_name;


-- ============================================================
-- 37. QUERY: NODE RESOURCE UTILIZATION
-- ============================================================

SELECT
    wn.node_name,
    wn.cpu_allocatable,
    COALESCE(SUM(na.cpu_reserved), 0) AS reserved_cpu,
    wn.memory_allocatable_mib,
    COALESCE(SUM(na.memory_reserved_mib), 0)
        AS reserved_memory_mib,

    ROUND(
        100.0 * COALESCE(SUM(na.cpu_reserved), 0)
        / NULLIF(wn.cpu_allocatable, 0),
        2
    ) AS cpu_utilization_percent,

    ROUND(
        100.0 * COALESCE(SUM(na.memory_reserved_mib), 0)
        / NULLIF(wn.memory_allocatable_mib, 0),
        2
    ) AS memory_utilization_percent

FROM worker_nodes wn

LEFT JOIN node_allocations na
    ON na.node_id = wn.node_id
   AND na.released_at IS NULL

GROUP BY
    wn.node_id,
    wn.node_name,
    wn.cpu_allocatable,
    wn.memory_allocatable_mib;


-- ============================================================
-- 38. QUERY: DEPLOYMENT RECONCILIATION
-- ============================================================

SELECT
    workload_name,
    namespace_name,
    desired_replicas,
    active_replicas,
    running_replicas,
    ready_replicas,
    deployment_status
FROM deployment_status_report
ORDER BY workload_name;


-- ============================================================
-- 39. QUERY: FAILURE INVESTIGATION
-- ============================================================

SELECT
    p.pod_name,
    pc.container_name,
    pc.state,
    pc.exit_code,
    pc.restart_count,
    pe.reason,
    pe.message,
    pe.event_timestamp

FROM pods p

JOIN pod_containers pc
    ON pc.pod_id = p.pod_id

LEFT JOIN pod_events pe
    ON pe.pod_id = p.pod_id

WHERE p.phase = 'Failed'
   OR pc.restart_count > 0

ORDER BY pe.event_timestamp DESC NULLS LAST;


-- ============================================================
-- 40. QUERY: UNREADY PODS
-- ============================================================

SELECT
    p.pod_id,
    p.pod_name,
    p.phase,
    c.status,
    c.reason,
    c.message
FROM pods p
LEFT JOIN pod_conditions c
    ON c.pod_id = p.pod_id
   AND c.condition_type = 'Ready'
WHERE c.status IS DISTINCT FROM 'True'
ORDER BY p.pod_name;


-- ============================================================
-- 41. QUERY: WORKLOAD ELIGIBILITY
-- ============================================================

WITH workload_resources AS (
    SELECT
        w.workload_id,
        w.workload_name,
        n.cluster_id,
        w.desired_replicas,
        r.requested_cpu,
        r.requested_memory_mib
    FROM workloads w
    JOIN namespaces n
        ON n.namespace_id = w.namespace_id
    CROSS JOIN LATERAL
        calculate_workload_resources(w.workload_id) r
),
node_capacity AS (
    SELECT
        cluster_id,
        SUM(cpu_allocatable) AS total_cpu,
        SUM(memory_allocatable_mib) AS total_memory
    FROM worker_nodes
    WHERE node_ready = TRUE
    GROUP BY cluster_id
)
SELECT
    wr.workload_name,
    wr.desired_replicas,
    wr.requested_cpu,
    wr.requested_memory_mib,

    CASE
        WHEN nc.total_cpu >=
             wr.requested_cpu * wr.desired_replicas
         AND nc.total_memory >=
             wr.requested_memory_mib * wr.desired_replicas
        THEN 'Potentially Schedulable'
        ELSE 'Insufficient Aggregate Capacity'
    END AS eligibility

FROM workload_resources wr

JOIN node_capacity nc
    ON nc.cluster_id = wr.cluster_id;


-- ============================================================
-- 42. TRANSACTION: CREATE AND SCHEDULE A POD
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_namespace_id BIGINT;
    v_workload_id BIGINT;
    v_pod_id BIGINT;
    v_node_id BIGINT;
BEGIN
    SELECT namespace_id
    INTO v_namespace_id
    FROM namespaces
    WHERE namespace_name = 'production'
    LIMIT 1;

    SELECT workload_id
    INTO v_workload_id
    FROM workloads
    WHERE workload_name = 'frontend'
      AND namespace_id = v_namespace_id;

    SELECT node_id
    INTO v_node_id
    FROM worker_nodes
    WHERE node_name = 'worker-01'
    LIMIT 1;

    INSERT INTO pods (
        namespace_id,
        workload_id,
        pod_name,
        phase,
        restart_policy,
        labels
    )
    VALUES (
        v_namespace_id,
        v_workload_id,
        'frontend-pod-transaction',
        'Pending',
        'Always',
        '{"app":"frontend","version":"transaction"}'::JSONB
    )
    RETURNING pod_id INTO v_pod_id;

    INSERT INTO pod_containers (
        pod_id,
        container_spec_id,
        container_name,
        container_image,
        role,
        state
    )
    SELECT
        v_pod_id,
        container_spec_id,
        container_name,
        container_image,
        role,
        'Waiting'
    FROM container_specs
    WHERE workload_id = v_workload_id;

    CALL schedule_pod(v_pod_id, v_node_id);

    RAISE NOTICE
        'Created and scheduled Pod with ID %',
        v_pod_id;
END;
$$;

COMMIT;


-- ============================================================
-- 43. TRANSACTION: SIMULATE FAILED SCHEDULING
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_pod_id BIGINT;
    v_node_id BIGINT;
BEGIN
    SELECT pod_id
    INTO v_pod_id
    FROM pods
    WHERE pod_name = 'frontend-pod-03';

    SELECT node_id
    INTO v_node_id
    FROM worker_nodes
    WHERE node_name = 'worker-02'
    LIMIT 1;

    IF v_pod_id IS NOT NULL AND v_node_id IS NOT NULL THEN
        IF NOT validate_node_capacity(
            v_node_id,
            1000,
            1000000
        ) THEN
            RAISE NOTICE
                'Scheduling rejected: insufficient node capacity';
        ELSE
            CALL schedule_pod(v_pod_id, v_node_id);
        END IF;
    END IF;
END;
$$;

COMMIT;


-- ============================================================
-- 44. TRANSACTION: SIMULATE A CONTAINER FAILURE
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_container_id BIGINT;
BEGIN
    SELECT pc.pod_container_id
    INTO v_container_id
    FROM pod_containers pc
    JOIN pods p
      ON p.pod_id = pc.pod_id
    WHERE p.pod_name = 'frontend-pod-01'
      AND pc.container_name = 'web'
      AND pc.state = 'Running'
    LIMIT 1;

    IF v_container_id IS NOT NULL THEN
        CALL process_container_exit(
            v_container_id,
            1
        );
    END IF;
END;
$$;

COMMIT;


-- ============================================================
-- 45. QUERY: RESTART AND FAILURE ANALYTICS
-- ============================================================

SELECT
    n.namespace_name,
    w.workload_name,
    COUNT(DISTINCT p.pod_id) AS pod_count,
    SUM(pc.restart_count) AS restart_count,
    COUNT(*) FILTER (
        WHERE pc.state = 'Terminated'
    ) AS terminated_containers

FROM pods p

JOIN namespaces n
    ON n.namespace_id = p.namespace_id

LEFT JOIN workloads w
    ON w.workload_id = p.workload_id

JOIN pod_containers pc
    ON pc.pod_id = p.pod_id

GROUP BY
    n.namespace_name,
    w.workload_name

ORDER BY restart_count DESC;


-- ============================================================
-- 46. QUERY: ROLLOUT HISTORY
-- ============================================================

SELECT
    w.workload_name,
    rh.previous_generation,
    rh.new_generation,
    rh.previous_image,
    rh.new_image,
    rh.rollout_status,
    rh.desired_replicas,
    rh.updated_replicas,
    rh.available_replicas,
    rh.started_at,
    rh.completed_at
FROM rollout_history rh
JOIN workloads w
    ON w.workload_id = rh.workload_id
ORDER BY rh.started_at DESC;


-- ============================================================
-- 47. QUERY: POD EVENT TIMELINE
-- ============================================================

SELECT
    p.pod_name,
    pe.event_type,
    pe.reason,
    pe.message,
    pe.occurrence_count,
    pe.event_timestamp
FROM pod_events pe
JOIN pods p
    ON p.pod_id = pe.pod_id
ORDER BY
    p.pod_name,
    pe.event_timestamp;


-- ============================================================
-- 48. QUERY: PROBE HEALTH
-- ============================================================

SELECT
    p.pod_name,
    pc.container_name,
    cp.probe_type,
    cp.http_path,
    cp.period_seconds,
    cp.failure_threshold,
    cp.last_success,
    cp.last_execution
FROM container_probes cp
JOIN pod_containers pc
    ON pc.pod_container_id = cp.pod_container_id
JOIN pods p
    ON p.pod_id = pc.pod_id
ORDER BY
    p.pod_name,
    cp.probe_type;


-- ============================================================
-- 49. QUERY: RESOURCE PRESSURE
-- ============================================================

WITH allocations AS (
    SELECT
        node_id,
        SUM(cpu_reserved) AS reserved_cpu,
        SUM(memory_reserved_mib) AS reserved_memory
    FROM node_allocations
    WHERE released_at IS NULL
    GROUP BY node_id
)
SELECT
    wn.node_name,
    wn.node_ready,
    wn.cpu_allocatable,
    COALESCE(a.reserved_cpu, 0) AS reserved_cpu,
    wn.memory_allocatable_mib,
    COALESCE(a.reserved_memory, 0) AS reserved_memory,

    (
        wn.cpu_allocatable - COALESCE(a.reserved_cpu, 0)
    ) AS available_cpu,

    (
        wn.memory_allocatable_mib -
        COALESCE(a.reserved_memory, 0)
    ) AS available_memory_mib

FROM worker_nodes wn

LEFT JOIN allocations a
    ON a.node_id = wn.node_id

ORDER BY wn.node_name;


-- ============================================================
-- 50. QUERY: WORKLOAD CONTAINER INVENTORY
-- ============================================================

SELECT
    w.workload_name,
    cs.container_name,
    cs.container_image,
    cs.role,
    cs.cpu_request,
    cs.cpu_limit,
    cs.memory_request_mib,
    cs.memory_limit_mib,
    cs.image_pull_policy
FROM container_specs cs
JOIN workloads w
    ON w.workload_id = cs.workload_id
ORDER BY
    w.workload_name,
    cs.role,
    cs.execution_order;


-- ============================================================
-- 51. FINAL OPERATIONAL REPORT
-- ============================================================

SELECT
    'PODS' AS report_section,
    COUNT(*)::TEXT AS record_count
FROM pods

UNION ALL

SELECT
    'RUNNING PODS',
    COUNT(*)::TEXT
FROM pods
WHERE phase = 'Running'

UNION ALL

SELECT
    'FAILED PODS',
    COUNT(*)::TEXT
FROM pods
WHERE phase = 'Failed'

UNION ALL

SELECT
    'CONTAINERS',
    COUNT(*)::TEXT
FROM pod_containers

UNION ALL

SELECT
    'RESTARTED CONTAINERS',
    COUNT(*)::TEXT
FROM pod_containers
WHERE restart_count > 0

UNION ALL

SELECT
    'ACTIVE NODE ALLOCATIONS',
    COUNT(*)::TEXT
FROM node_allocations
WHERE released_at IS NULL;

-- End of executable Pod Management schema and workflow.
