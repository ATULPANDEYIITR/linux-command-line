-- ============================================================
-- KUBERNETES CLUSTER MANAGEMENT AND ORCHESTRATION
-- PostgreSQL 15+
--
-- Models:
--   Clusters
--   Control-plane and worker nodes
--   Namespaces
--   Containers
--   Pods
--   Deployments
--   Replica management
--   Services and endpoints
--   Resource allocation
--   Scheduling
--   Node health
--   Rolling updates
--   Cluster events
--   Operational reporting
--
-- Execute using psql.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS kubernetes;

SET search_path TO kubernetes, public;

-- ============================================================
-- 1. ENUMERATED TYPES
-- ============================================================

CREATE TYPE node_role AS ENUM (
    'control-plane',
    'worker'
);

CREATE TYPE node_status AS ENUM (
    'Ready',
    'NotReady',
    'SchedulingDisabled'
);

CREATE TYPE pod_status AS ENUM (
    'Pending',
    'Running',
    'Failed',
    'Succeeded',
    'Terminating'
);

CREATE TYPE service_type AS ENUM (
    'ClusterIP',
    'NodePort',
    'LoadBalancer'
);

CREATE TYPE deployment_status AS ENUM (
    'Active',
    'Degraded',
    'Scaling',
    'Paused'
);

CREATE TYPE container_status AS ENUM (
    'Waiting',
    'Running',
    'Terminated'
);

CREATE TYPE event_severity AS ENUM (
    'Normal',
    'Warning',
    'Critical'
);

-- ============================================================
-- 2. CLUSTERS
-- ============================================================

CREATE TABLE clusters (
    cluster_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_name VARCHAR(100) NOT NULL UNIQUE,

    environment VARCHAR(30) NOT NULL,

    kubernetes_version VARCHAR(30) NOT NULL,

    api_endpoint VARCHAR(255),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_environment
        CHECK (
            environment IN (
                'development',
                'testing',
                'staging',
                'production'
            )
        ),

    CONSTRAINT valid_cluster_name
        CHECK (
            cluster_name ~ '^[a-z0-9][a-z0-9-]*$'
        )
);

-- ============================================================
-- 3. NAMESPACES
-- ============================================================

CREATE TABLE namespaces (
    namespace_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES clusters(cluster_id),

    namespace_name VARCHAR(63) NOT NULL,

    purpose TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(cluster_id, namespace_name),

    CONSTRAINT valid_namespace_name
        CHECK (
            namespace_name ~ '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        )
);

-- ============================================================
-- 4. NODES
-- ============================================================

CREATE TABLE nodes (
    node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES clusters(cluster_id),

    node_name VARCHAR(100) NOT NULL,

    role node_role NOT NULL,

    status node_status NOT NULL DEFAULT 'Ready',

    cpu_capacity_millicores INTEGER NOT NULL,

    memory_capacity_mb INTEGER NOT NULL,

    cpu_allocated_millicores INTEGER NOT NULL DEFAULT 0,

    memory_allocated_mb INTEGER NOT NULL DEFAULT 0,

    kubelet_version VARCHAR(30),

    internal_ip INET,

    last_heartbeat TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(cluster_id, node_name),

    CONSTRAINT positive_node_capacity
        CHECK (
            cpu_capacity_millicores > 0
            AND memory_capacity_mb > 0
        ),

    CONSTRAINT valid_node_allocation
        CHECK (
            cpu_allocated_millicores >= 0
            AND memory_allocated_mb >= 0
            AND cpu_allocated_millicores
                <= cpu_capacity_millicores
            AND memory_allocated_mb
                <= memory_capacity_mb
        )
);

CREATE INDEX idx_nodes_cluster_status
    ON nodes(cluster_id, status);

CREATE INDEX idx_nodes_worker_ready
    ON nodes(cluster_id, node_name)
    WHERE role = 'worker' AND status = 'Ready';

-- ============================================================
-- 5. DEPLOYMENTS
-- ============================================================

CREATE TABLE deployments (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL
        REFERENCES namespaces(namespace_id),

    deployment_name VARCHAR(100) NOT NULL,

    container_image VARCHAR(255) NOT NULL,

    desired_replicas INTEGER NOT NULL DEFAULT 1,

    generation INTEGER NOT NULL DEFAULT 1,

    available_generation INTEGER NOT NULL DEFAULT 0,

    status deployment_status NOT NULL DEFAULT 'Scaling',

    strategy VARCHAR(30) NOT NULL DEFAULT 'RollingUpdate',

    max_surge INTEGER NOT NULL DEFAULT 1,

    max_unavailable INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(namespace_id, deployment_name),

    CONSTRAINT valid_replica_count
        CHECK (desired_replicas >= 0),

    CONSTRAINT valid_generation
        CHECK (
            generation > 0
            AND available_generation >= 0
        ),

    CONSTRAINT valid_strategy
        CHECK (
            strategy IN ('RollingUpdate', 'Recreate')
        ),

    CONSTRAINT valid_rollout_limits
        CHECK (
            max_surge >= 0
            AND max_unavailable >= 0
        )
);

-- ============================================================
-- 6. DEPLOYMENT LABELS
-- ============================================================

CREATE TABLE deployment_labels (
    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id)
        ON DELETE CASCADE,

    label_key VARCHAR(63) NOT NULL,

    label_value VARCHAR(253) NOT NULL,

    PRIMARY KEY(deployment_id, label_key)
);

-- ============================================================
-- 7. PODS
-- ============================================================

CREATE TABLE pods (
    pod_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL
        REFERENCES namespaces(namespace_id),

    deployment_id BIGINT
        REFERENCES deployments(deployment_id)
        ON DELETE SET NULL,

    node_id BIGINT
        REFERENCES nodes(node_id)
        ON DELETE SET NULL,

    pod_name VARCHAR(100) NOT NULL,

    status pod_status NOT NULL DEFAULT 'Pending',

    cpu_request_millicores INTEGER NOT NULL,

    memory_request_mb INTEGER NOT NULL,

    restart_count INTEGER NOT NULL DEFAULT 0,

    ready BOOLEAN NOT NULL DEFAULT FALSE,

    creation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    started_at TIMESTAMPTZ,

    terminated_at TIMESTAMPTZ,

    UNIQUE(namespace_id, pod_name),

    CONSTRAINT valid_pod_resources
        CHECK (
            cpu_request_millicores > 0
            AND memory_request_mb > 0
        ),

    CONSTRAINT valid_restart_count
        CHECK (restart_count >= 0),

    CONSTRAINT running_pod_has_node
        CHECK (
            status <> 'Running'
            OR node_id IS NOT NULL
        ),

    CONSTRAINT valid_readiness
        CHECK (
            NOT ready
            OR status = 'Running'
        )
);

CREATE INDEX idx_pods_node_status
    ON pods(node_id, status);

CREATE INDEX idx_pods_deployment_status
    ON pods(deployment_id, status);

CREATE INDEX idx_pods_namespace
    ON pods(namespace_id, pod_name);

CREATE INDEX idx_pods_ready
    ON pods(namespace_id, ready)
    WHERE status = 'Running' AND ready = TRUE;

-- ============================================================
-- 8. POD LABELS
-- ============================================================

CREATE TABLE pod_labels (
    pod_id BIGINT NOT NULL
        REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    label_key VARCHAR(63) NOT NULL,

    label_value VARCHAR(253) NOT NULL,

    PRIMARY KEY(pod_id, label_key)
);

CREATE INDEX idx_pod_labels_selector
    ON pod_labels(label_key, label_value, pod_id);

-- ============================================================
-- 9. CONTAINERS
-- ============================================================

CREATE TABLE containers (
    container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_id BIGINT NOT NULL
        REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    container_name VARCHAR(100) NOT NULL,

    image VARCHAR(255) NOT NULL,

    cpu_request_millicores INTEGER NOT NULL,

    memory_request_mb INTEGER NOT NULL,

    status container_status NOT NULL DEFAULT 'Waiting',

    restart_count INTEGER NOT NULL DEFAULT 0,

    UNIQUE(pod_id, container_name),

    CHECK (
        cpu_request_millicores > 0
        AND memory_request_mb > 0
    ),

    CHECK (restart_count >= 0)
);

-- ============================================================
-- 10. SERVICES
-- ============================================================

CREATE TABLE services (
    service_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL
        REFERENCES namespaces(namespace_id),

    service_name VARCHAR(100) NOT NULL,

    service_type service_type NOT NULL DEFAULT 'ClusterIP',

    cluster_ip INET,

    port INTEGER NOT NULL,

    target_port INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(namespace_id, service_name),

    CHECK (port BETWEEN 1 AND 65535),

    CHECK (target_port BETWEEN 1 AND 65535)
);

-- ============================================================
-- 11. SERVICE SELECTORS
-- ============================================================

CREATE TABLE service_selectors (
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,

    label_key VARCHAR(63) NOT NULL,

    label_value VARCHAR(253) NOT NULL,

    PRIMARY KEY(service_id, label_key)
);

CREATE INDEX idx_service_selectors
    ON service_selectors(label_key, label_value, service_id);

-- ============================================================
-- 12. STATUS CHECKS
-- ============================================================

CREATE TABLE pod_status_checks (
    check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pod_id BIGINT NOT NULL
        REFERENCES pods(pod_id)
        ON DELETE CASCADE,

    check_name VARCHAR(100) NOT NULL,

    check_type VARCHAR(20) NOT NULL,

    successful BOOLEAN NOT NULL,

    response_time_ms INTEGER,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_check_type
        CHECK (
            check_type IN (
                'readiness',
                'liveness',
                'startup'
            )
        ),

    CHECK (
        response_time_ms IS NULL
        OR response_time_ms >= 0
    )
);

CREATE INDEX idx_pod_checks_recent
    ON pod_status_checks(pod_id, checked_at DESC);

-- ============================================================
-- 13. CLUSTER EVENTS
-- ============================================================

CREATE TABLE cluster_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES clusters(cluster_id),

    node_id BIGINT
        REFERENCES nodes(node_id)
        ON DELETE SET NULL,

    pod_id BIGINT
        REFERENCES pods(pod_id)
        ON DELETE SET NULL,

    deployment_id BIGINT
        REFERENCES deployments(deployment_id)
        ON DELETE SET NULL,

    event_type VARCHAR(100) NOT NULL,

    severity event_severity NOT NULL DEFAULT 'Normal',

    message TEXT NOT NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cluster_events_recent
    ON cluster_events(cluster_id, occurred_at DESC);

CREATE INDEX idx_cluster_events_severity
    ON cluster_events(cluster_id, severity, occurred_at DESC);

-- ============================================================
-- 14. RESOURCE ALLOCATION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION allocate_pod_resources()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    selected_node nodes%ROWTYPE;
BEGIN

    IF NEW.node_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Lock the selected node to prevent concurrent over-allocation.
    SELECT *
    INTO selected_node
    FROM nodes
    WHERE node_id = NEW.node_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Selected node does not exist.';
    END IF;

    IF selected_node.role <> 'worker' THEN
        RAISE EXCEPTION 'Pods cannot be scheduled on control-plane nodes.';
    END IF;

    IF selected_node.status <> 'Ready' THEN
        RAISE EXCEPTION 'Node is not ready for scheduling.';
    END IF;

    IF
        selected_node.cpu_allocated_millicores
            + NEW.cpu_request_millicores
            > selected_node.cpu_capacity_millicores
        OR
        selected_node.memory_allocated_mb
            + NEW.memory_request_mb
            > selected_node.memory_capacity_mb
    THEN
        RAISE EXCEPTION 'Insufficient node resources.';
    END IF;

    UPDATE nodes
    SET
        cpu_allocated_millicores =
            cpu_allocated_millicores
            + NEW.cpu_request_millicores,

        memory_allocated_mb =
            memory_allocated_mb
            + NEW.memory_request_mb

    WHERE node_id = NEW.node_id;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION release_pod_resources()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    IF OLD.node_id IS NOT NULL THEN

        UPDATE nodes
        SET
            cpu_allocated_millicores =
                cpu_allocated_millicores
                - OLD.cpu_request_millicores,

            memory_allocated_mb =
                memory_allocated_mb
                - OLD.memory_request_mb

        WHERE node_id = OLD.node_id;

    END IF;

    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_allocate_pod_resources
BEFORE INSERT ON pods
FOR EACH ROW
EXECUTE FUNCTION allocate_pod_resources();

CREATE TRIGGER trg_release_pod_resources
AFTER DELETE ON pods
FOR EACH ROW
EXECUTE FUNCTION release_pod_resources();

-- ============================================================
-- 15. POD NODE ASSIGNMENT UPDATE
-- ============================================================

CREATE OR REPLACE FUNCTION manage_pod_node_assignment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    selected_node nodes%ROWTYPE;
BEGIN

    IF OLD.node_id IS NOT DISTINCT FROM NEW.node_id
       AND OLD.cpu_request_millicores =
           NEW.cpu_request_millicores
       AND OLD.memory_request_mb =
           NEW.memory_request_mb
    THEN
        RETURN NEW;
    END IF;

    -- Release the old allocation first.
    IF OLD.node_id IS NOT NULL THEN

        UPDATE nodes
        SET
            cpu_allocated_millicores =
                cpu_allocated_millicores
                - OLD.cpu_request_millicores,

            memory_allocated_mb =
                memory_allocated_mb
                - OLD.memory_request_mb

        WHERE node_id = OLD.node_id;

    END IF;

    IF NEW.node_id IS NOT NULL THEN

        SELECT *
        INTO selected_node
        FROM nodes
        WHERE node_id = NEW.node_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Target node does not exist.';
        END IF;

        IF selected_node.role <> 'worker'
           OR selected_node.status <> 'Ready'
        THEN
            RAISE EXCEPTION 'Target node is not schedulable.';
        END IF;

        IF
            selected_node.cpu_allocated_millicores
                + NEW.cpu_request_millicores
                > selected_node.cpu_capacity_millicores
            OR
            selected_node.memory_allocated_mb
                + NEW.memory_request_mb
                > selected_node.memory_capacity_mb
        THEN
            RAISE EXCEPTION 'Insufficient target node capacity.';
        END IF;

        UPDATE nodes
        SET
            cpu_allocated_millicores =
                cpu_allocated_millicores
                + NEW.cpu_request_millicores,

            memory_allocated_mb =
                memory_allocated_mb
                + NEW.memory_request_mb

        WHERE node_id = NEW.node_id;

    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_manage_pod_node_assignment
BEFORE UPDATE OF
    node_id,
    cpu_request_millicores,
    memory_request_mb
ON pods
FOR EACH ROW
EXECUTE FUNCTION manage_pod_node_assignment();

-- ============================================================
-- 16. DEPLOYMENT RECONCILIATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION reconcile_deployment(
    p_deployment_id BIGINT
)
RETURNS TABLE (
    deployment_name VARCHAR,
    desired_replicas INTEGER,
    current_replicas BIGINT,
    ready_replicas BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN

    IF NOT EXISTS (
        SELECT 1
        FROM deployments
        WHERE deployment_id = p_deployment_id
    ) THEN
        RAISE EXCEPTION 'Deployment not found: %',
            p_deployment_id;
    END IF;

    UPDATE deployments d
    SET
        status = CASE
            WHEN stats.ready_replicas = d.desired_replicas
                THEN 'Active'::deployment_status
            WHEN stats.ready_replicas = 0
                THEN 'Degraded'::deployment_status
            ELSE 'Scaling'::deployment_status
        END,

        available_generation = CASE
            WHEN stats.ready_replicas = d.desired_replicas
                THEN d.generation
            ELSE d.available_generation
        END,

        updated_at = NOW()

    FROM (
        SELECT
            deployment_id,

            COUNT(*) FILTER (
                WHERE status IN ('Running', 'Pending')
            ) AS current_replicas,

            COUNT(*) FILTER (
                WHERE status = 'Running' AND ready = TRUE
            ) AS ready_replicas

        FROM pods
        WHERE deployment_id = p_deployment_id
        GROUP BY deployment_id
    ) stats

    WHERE d.deployment_id = stats.deployment_id;

    UPDATE deployments d
    SET
        status = CASE
            WHEN d.desired_replicas = 0
                THEN 'Active'::deployment_status
            ELSE 'Degraded'::deployment_status
        END

    WHERE d.deployment_id = p_deployment_id
      AND NOT EXISTS (
          SELECT 1
          FROM pods p
          WHERE p.deployment_id = d.deployment_id
            AND p.status IN ('Running', 'Pending')
      );

    RETURN QUERY
    SELECT
        d.deployment_name,
        d.desired_replicas,
        COUNT(p.pod_id),
        COUNT(p.pod_id) FILTER (
            WHERE p.status = 'Running' AND p.ready
        )

    FROM deployments d
    LEFT JOIN pods p
        ON p.deployment_id = d.deployment_id
       AND p.status IN ('Running', 'Pending')

    WHERE d.deployment_id = p_deployment_id

    GROUP BY d.deployment_id;
END;
$$;

-- ============================================================
-- 17. SERVICE ENDPOINT VIEW
-- ============================================================

CREATE VIEW service_endpoints AS

SELECT
    s.service_id,
    s.service_name,
    s.namespace_id,
    s.cluster_ip,
    s.port,
    s.target_port,

    p.pod_id,
    p.pod_name,
    n.node_name

FROM services s

JOIN service_selectors ss
    ON ss.service_id = s.service_id

JOIN pod_labels pl
    ON pl.label_key = ss.label_key
   AND pl.label_value = ss.label_value

JOIN pods p
    ON p.pod_id = pl.pod_id

JOIN nodes n
    ON n.node_id = p.node_id

WHERE p.status = 'Running'
  AND p.ready = TRUE

GROUP BY
    s.service_id,
    s.service_name,
    s.namespace_id,
    s.cluster_ip,
    s.port,
    s.target_port,
    p.pod_id,
    p.pod_name,
    n.node_name

HAVING COUNT(DISTINCT ss.label_key) = (
    SELECT COUNT(*)
    FROM service_selectors required
    WHERE required.service_id = s.service_id
);

-- ============================================================
-- 18. NODE RESOURCE UTILIZATION VIEW
-- ============================================================

CREATE VIEW node_resource_utilization AS

SELECT
    n.node_id,
    c.cluster_name,
    n.node_name,
    n.role,
    n.status,

    n.cpu_capacity_millicores,
    n.cpu_allocated_millicores,

    ROUND(
        100.0 * n.cpu_allocated_millicores
        / NULLIF(n.cpu_capacity_millicores, 0),
        2
    ) AS cpu_utilization_percent,

    n.memory_capacity_mb,
    n.memory_allocated_mb,

    ROUND(
        100.0 * n.memory_allocated_mb
        / NULLIF(n.memory_capacity_mb, 0),
        2
    ) AS memory_utilization_percent

FROM nodes n

JOIN clusters c
    ON c.cluster_id = n.cluster_id;

-- ============================================================
-- 19. DEPLOYMENT HEALTH VIEW
-- ============================================================

CREATE VIEW deployment_health AS

SELECT
    d.deployment_id,
    d.deployment_name,
    ns.namespace_name,

    d.desired_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.status IN ('Running', 'Pending')
    ) AS observed_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.status = 'Running'
          AND p.ready = TRUE
    ) AS ready_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.status = 'Pending'
    ) AS pending_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.status = 'Failed'
    ) AS failed_replicas,

    d.status,
    d.generation,
    d.available_generation

FROM deployments d

JOIN namespaces ns
    ON ns.namespace_id = d.namespace_id

LEFT JOIN pods p
    ON p.deployment_id = d.deployment_id

GROUP BY
    d.deployment_id,
    d.deployment_name,
    ns.namespace_name,
    d.desired_replicas,
    d.status,
    d.generation,
    d.available_generation;

-- ============================================================
-- 20. SAMPLE DATA
-- ============================================================

INSERT INTO clusters (
    cluster_name,
    environment,
    kubernetes_version,
    api_endpoint
)
VALUES
(
    'production-cluster',
    'production',
    '1.32.0',
    'https://10.0.0.1:6443'
),
(
    'development-cluster',
    'development',
    '1.32.0',
    'https://10.0.1.1:6443'
);

INSERT INTO namespaces (
    cluster_id,
    namespace_name,
    purpose
)
SELECT
    cluster_id,
    'production',
    'Production application workloads'
FROM clusters
WHERE cluster_name = 'production-cluster';

INSERT INTO namespaces (
    cluster_id,
    namespace_name,
    purpose
)
SELECT
    cluster_id,
    'development',
    'Development and testing workloads'
FROM clusters
WHERE cluster_name = 'development-cluster';

INSERT INTO nodes (
    cluster_id,
    node_name,
    role,
    status,
    cpu_capacity_millicores,
    memory_capacity_mb,
    kubelet_version,
    internal_ip
)
SELECT
    cluster_id,
    'master-01',
    'control-plane',
    'Ready',
    8000,
    16384,
    '1.32.0',
    '10.0.0.10'
FROM clusters
WHERE cluster_name = 'production-cluster';

INSERT INTO nodes (
    cluster_id,
    node_name,
    role,
    status,
    cpu_capacity_millicores,
    memory_capacity_mb,
    kubelet_version,
    internal_ip
)
SELECT
    cluster_id,
    data.node_name,
    'worker',
    data.status,
    data.cpu,
    data.memory,
    '1.32.0',
    data.ip::INET

FROM clusters c

CROSS JOIN (
    VALUES
        (
            'worker-01',
            'Ready'::node_status,
            4000,
            8192,
            '10.0.0.11'
        ),
        (
            'worker-02',
            'Ready'::node_status,
            4000,
            8192,
            '10.0.0.12'
        ),
        (
            'worker-03',
            'NotReady'::node_status,
            2000,
            4096,
            '10.0.0.13'
        )
) AS data(
    node_name,
    status,
    cpu,
    memory,
    ip
)

WHERE c.cluster_name = 'production-cluster';

INSERT INTO deployments (
    namespace_id,
    deployment_name,
    container_image,
    desired_replicas,
    generation,
    status
)
SELECT
    namespace_id,
    'inventory-api',
    'inventory-api:1.0.0',
    3,
    1,
    'Scaling'
FROM namespaces
WHERE namespace_name = 'production';

INSERT INTO deployment_labels (
    deployment_id,
    label_key,
    label_value
)
SELECT
    deployment_id,
    'app',
    'inventory'
FROM deployments
WHERE deployment_name = 'inventory-api';

INSERT INTO deployment_labels (
    deployment_id,
    label_key,
    label_value
)
SELECT
    deployment_id,
    'environment',
    'production'
FROM deployments
WHERE deployment_name = 'inventory-api';

-- ============================================================
-- 21. CREATE SCHEDULED PODS
-- ============================================================

INSERT INTO pods (
    namespace_id,
    deployment_id,
    node_id,
    pod_name,
    status,
    cpu_request_millicores,
    memory_request_mb,
    ready,
    started_at
)

SELECT
    ns.namespace_id,
    d.deployment_id,
    n.node_id,
    pod_data.pod_name,
    'Running',
    500,
    512,
    TRUE,
    NOW()

FROM namespaces ns

JOIN deployments d
    ON d.namespace_id = ns.namespace_id

JOIN nodes n
    ON n.cluster_id = (
        SELECT cluster_id
        FROM clusters
        WHERE cluster_name = 'production-cluster'
    )

CROSS JOIN (
    VALUES
        ('inventory-api-1', 'worker-01'),
        ('inventory-api-2', 'worker-01'),
        ('inventory-api-3', 'worker-02')
) AS pod_data(pod_name, node_name)

WHERE ns.namespace_name = 'production'
  AND d.deployment_name = 'inventory-api'
  AND n.node_name = pod_data.node_name;

-- ============================================================
-- 22. POD LABELS
-- ============================================================

INSERT INTO pod_labels (
    pod_id,
    label_key,
    label_value
)
SELECT
    p.pod_id,
    label_data.label_key,
    label_data.label_value

FROM pods p

JOIN deployments d
    ON d.deployment_id = p.deployment_id

CROSS JOIN (
    VALUES
        ('app', 'inventory'),
        ('environment', 'production')
) AS label_data(label_key, label_value)

WHERE d.deployment_name = 'inventory-api';

-- ============================================================
-- 23. CONTAINER RECORDS
-- ============================================================

INSERT INTO containers (
    pod_id,
    container_name,
    image,
    cpu_request_millicores,
    memory_request_mb,
    status
)

SELECT
    p.pod_id,
    'application',
    d.container_image,
    500,
    512,
    'Running'

FROM pods p

JOIN deployments d
    ON d.deployment_id = p.deployment_id

WHERE d.deployment_name = 'inventory-api';

-- ============================================================
-- 24. SERVICE AND SELECTOR
-- ============================================================

INSERT INTO services (
    namespace_id,
    service_name,
    service_type,
    cluster_ip,
    port,
    target_port
)

SELECT
    namespace_id,
    'inventory-service',
    'ClusterIP',
    '10.96.0.20',
    80,
    8080

FROM namespaces

WHERE namespace_name = 'production';

INSERT INTO service_selectors (
    service_id,
    label_key,
    label_value
)

SELECT
    service_id,
    'app',
    'inventory'

FROM services

WHERE service_name = 'inventory-service';

INSERT INTO service_selectors (
    service_id,
    label_key,
    label_value
)

SELECT
    service_id,
    'environment',
    'production'

FROM services

WHERE service_name = 'inventory-service';

-- ============================================================
-- 25. HEALTH CHECK DATA
-- ============================================================

INSERT INTO pod_status_checks (
    pod_id,
    check_name,
    check_type,
    successful,
    response_time_ms
)

SELECT
    pod_id,
    'http-readiness',
    'readiness',
    TRUE,
    18

FROM pods;

INSERT INTO pod_status_checks (
    pod_id,
    check_name,
    check_type,
    successful,
    response_time_ms
)

SELECT
    pod_id,
    'container-liveness',
    'liveness',
    TRUE,
    5

FROM pods;

-- ============================================================
-- 26. SAMPLE CLUSTER EVENTS
-- ============================================================

INSERT INTO cluster_events (
    cluster_id,
    node_id,
    event_type,
    severity,
    message
)

SELECT
    c.cluster_id,
    n.node_id,
    'NodeNotReady',
    'Warning',
    'Worker node is not responding to health monitoring.'

FROM clusters c

JOIN nodes n
    ON n.cluster_id = c.cluster_id

WHERE c.cluster_name = 'production-cluster'
  AND n.node_name = 'worker-03';

INSERT INTO cluster_events (
    cluster_id,
    event_type,
    severity,
    message
)

SELECT
    cluster_id,
    'DeploymentCreated',
    'Normal',
    'Inventory API deployment registered.'

FROM clusters

WHERE cluster_name = 'production-cluster';

-- ============================================================
-- 27. RETRIEVAL QUERIES
-- ============================================================

-- Cluster inventory.
SELECT
    cluster_name,
    environment,
    kubernetes_version,
    api_endpoint
FROM clusters
ORDER BY cluster_name;

-- Node inventory.
SELECT
    cluster_name,
    node_name,
    role,
    status,
    cpu_capacity_millicores,
    memory_capacity_mb
FROM nodes
JOIN clusters USING (cluster_id)
ORDER BY cluster_name, node_name;

-- Pod inventory.
SELECT
    p.pod_name,
    ns.namespace_name,
    n.node_name,
    p.status,
    p.ready,
    p.cpu_request_millicores,
    p.memory_request_mb
FROM pods p
JOIN namespaces ns USING (namespace_id)
LEFT JOIN nodes n USING (node_id)
ORDER BY p.pod_name;

-- ============================================================
-- 28. RESOURCE UTILIZATION REPORT
-- ============================================================

SELECT *
FROM node_resource_utilization
ORDER BY cpu_utilization_percent DESC;

-- ============================================================
-- 29. DEPLOYMENT HEALTH REPORT
-- ============================================================

SELECT *
FROM deployment_health
ORDER BY deployment_name;

-- ============================================================
-- 30. SERVICE DISCOVERY
-- ============================================================

SELECT
    service_name,
    cluster_ip,
    pod_name,
    node_name,
    port,
    target_port

FROM service_endpoints

ORDER BY service_name, pod_name;

-- ============================================================
-- 31. SCHEDULING ELIGIBILITY
-- ============================================================

-- Identify nodes capable of accepting a 500m CPU / 512MB Pod.
SELECT
    node_name,
    status,
    cpu_capacity_millicores
        - cpu_allocated_millicores AS available_cpu,

    memory_capacity_mb
        - memory_allocated_mb AS available_memory

FROM nodes

WHERE role = 'worker'
  AND status = 'Ready'
  AND cpu_capacity_millicores
        - cpu_allocated_millicores >= 500
  AND memory_capacity_mb
        - memory_allocated_mb >= 512;

-- ============================================================
-- 32. POD HEALTH EVALUATION
-- ============================================================

SELECT
    p.pod_name,

    COUNT(*) FILTER (
        WHERE checks.check_type = 'readiness'
          AND checks.successful
    ) AS successful_readiness_checks,

    COUNT(*) FILTER (
        WHERE checks.check_type = 'liveness'
          AND checks.successful
    ) AS successful_liveness_checks,

    AVG(checks.response_time_ms) AS average_response_ms

FROM pods p

LEFT JOIN pod_status_checks checks
    ON checks.pod_id = p.pod_id

GROUP BY p.pod_id, p.pod_name

ORDER BY p.pod_name;

-- ============================================================
-- 33. AGGREGATION: PODS PER NODE
-- ============================================================

SELECT
    n.node_name,
    n.status,
    COUNT(p.pod_id) AS total_pods,

    COUNT(p.pod_id) FILTER (
        WHERE p.status = 'Running'
    ) AS running_pods,

    COUNT(p.pod_id) FILTER (
        WHERE p.status = 'Pending'
    ) AS pending_pods,

    COUNT(p.pod_id) FILTER (
        WHERE p.status = 'Failed'
    ) AS failed_pods

FROM nodes n

LEFT JOIN pods p
    ON p.node_id = n.node_id

GROUP BY n.node_id, n.node_name, n.status

ORDER BY n.node_name;

-- ============================================================
-- 34. CTE: CLUSTER CAPACITY
-- ============================================================

WITH capacity AS (

    SELECT
        cluster_id,

        SUM(cpu_capacity_millicores) AS total_cpu,

        SUM(cpu_allocated_millicores) AS used_cpu,

        SUM(memory_capacity_mb) AS total_memory,

        SUM(memory_allocated_mb) AS used_memory

    FROM nodes

    GROUP BY cluster_id

)

SELECT
    c.cluster_name,
    capacity.total_cpu,
    capacity.used_cpu,
    capacity.total_cpu - capacity.used_cpu
        AS available_cpu,

    capacity.total_memory,
    capacity.used_memory,
    capacity.total_memory - capacity.used_memory
        AS available_memory

FROM capacity

JOIN clusters c USING (cluster_id);

-- ============================================================
-- 35. DEPLOYMENT RECONCILIATION
-- ============================================================

SELECT *
FROM reconcile_deployment(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'inventory-api'
    )
);

-- ============================================================
-- 36. TRANSACTION: SAFE POD CREATION
-- ============================================================

-- The node allocation trigger locks the node row and verifies
-- capacity before accepting the new Pod.

SAVEPOINT before_additional_pod;

DO $$
DECLARE
    v_namespace_id BIGINT;
    v_deployment_id BIGINT;
    v_node_id BIGINT;
BEGIN

    SELECT namespace_id
    INTO v_namespace_id
    FROM namespaces
    WHERE namespace_name = 'production';

    SELECT deployment_id
    INTO v_deployment_id
    FROM deployments
    WHERE deployment_name = 'inventory-api';

    SELECT node_id
    INTO v_node_id
    FROM nodes
    WHERE node_name = 'worker-02';

    INSERT INTO pods (
        namespace_id,
        deployment_id,
        node_id,
        pod_name,
        status,
        cpu_request_millicores,
        memory_request_mb,
        ready
    )
    VALUES (
        v_namespace_id,
        v_deployment_id,
        v_node_id,
        'inventory-api-4',
        'Running',
        500,
        512,
        TRUE
    );

END;
$$;

-- Demonstrate rollback of the optional additional Pod.
ROLLBACK TO SAVEPOINT before_additional_pod;

-- ============================================================
-- 37. FAILED SCHEDULING ATTEMPT
-- ============================================================

-- This block deliberately attempts an invalid allocation.
-- The exception is caught, so the remaining SQL script executes.

DO $$
DECLARE
    v_namespace_id BIGINT;
    v_deployment_id BIGINT;
    v_node_id BIGINT;
BEGIN

    SELECT namespace_id
    INTO v_namespace_id
    FROM namespaces
    WHERE namespace_name = 'production';

    SELECT deployment_id
    INTO v_deployment_id
    FROM deployments
    WHERE deployment_name = 'inventory-api';

    SELECT node_id
    INTO v_node_id
    FROM nodes
    WHERE node_name = 'worker-01';

    BEGIN

        INSERT INTO pods (
            namespace_id,
            deployment_id,
            node_id,
            pod_name,
            status,
            cpu_request_millicores,
            memory_request_mb,
            ready
        )
        VALUES (
            v_namespace_id,
            v_deployment_id,
            v_node_id,
            'invalid-large-pod',
            'Running',
            100000,
            100000,
            TRUE
        );

    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE
                'Scheduling correctly rejected: %',
                SQLERRM;
    END;

END;
$$;

-- ============================================================
-- 38. NODE FAILURE SIMULATION
-- ============================================================

UPDATE nodes
SET
    status = 'NotReady',
    last_heartbeat = NOW() - INTERVAL '10 minutes'

WHERE node_name = 'worker-02';

-- Mark affected Pods as failed and release their resource
-- allocations through the node assignment update trigger.

UPDATE pods
SET
    node_id = NULL,
    status = 'Failed',
    ready = FALSE,
    terminated_at = NOW()

WHERE node_id = (
    SELECT node_id
    FROM nodes
    WHERE node_name = 'worker-02'
);

-- Reconcile deployment state after node failure.
SELECT *
FROM reconcile_deployment(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'inventory-api'
    )
);

-- ============================================================
-- 39. RECOVER NODE
-- ============================================================

UPDATE nodes
SET
    status = 'Ready',
    last_heartbeat = NOW()

WHERE node_name = 'worker-02';

-- ============================================================
-- 40. OPERATIONAL EVENT REPORT
-- ============================================================

SELECT
    c.cluster_name,
    e.event_type,
    e.severity,
    e.message,
    e.occurred_at

FROM cluster_events e

JOIN clusters c
    ON c.cluster_id = e.cluster_id

ORDER BY e.occurred_at DESC;

-- ============================================================
-- 41. FAILED POD REPORT
-- ============================================================

SELECT
    p.pod_name,
    p.status,
    p.restart_count,
    d.deployment_name,
    ns.namespace_name

FROM pods p

LEFT JOIN deployments d
    ON d.deployment_id = p.deployment_id

JOIN namespaces ns
    ON ns.namespace_id = p.namespace_id

WHERE p.status = 'Failed'

ORDER BY p.creation_timestamp DESC;

-- ============================================================
-- 42. SECURITY AND DATABASE GOVERNANCE
-- ============================================================

-- Create a restricted operational role if it does not exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'kubernetes_readonly'
    ) THEN
        CREATE ROLE kubernetes_readonly;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kubernetes
TO kubernetes_readonly;

GRANT SELECT ON ALL TABLES IN SCHEMA kubernetes
TO kubernetes_readonly;

ALTER DEFAULT PRIVILEGES
IN SCHEMA kubernetes
GRANT SELECT ON TABLES
TO kubernetes_readonly;

-- Read-only access does not grant permission to modify
-- cluster state, Pod assignments or resource allocations.

-- ============================================================
-- 43. FINAL INTEGRITY REPORT
-- ============================================================

SELECT
    'NODE_CAPACITY' AS validation,
    COUNT(*) AS checked_records,
    COUNT(*) FILTER (
        WHERE cpu_allocated_millicores
                <= cpu_capacity_millicores
          AND memory_allocated_mb
                <= memory_capacity_mb
    ) AS valid_records

FROM nodes

UNION ALL

SELECT
    'RUNNING_POD_ASSIGNMENT',
    COUNT(*),
    COUNT(*) FILTER (
        WHERE node_id IS NOT NULL
    )

FROM pods

WHERE status = 'Running';

-- Persist the demonstration cluster state.
COMMIT;
