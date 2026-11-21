/*
===============================================================================
DOCKER COMPOSE: RELATIONAL DEPLOYMENT AND CONFIGURATION MANAGEMENT
===============================================================================

PostgreSQL 15+

Models:
1. Projects
2. Networks and volumes
3. Service definitions
4. Environment configuration
5. Port mappings
6. Service dependencies
7. Deployment executions
8. Runtime service instances
9. Health-check results
10. Restart policies
11. Deployment events
12. Deployment eligibility

The database records declarative configuration and deployment observations.
It does not create or operate actual Docker containers.
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS compose_platform;

SET search_path TO compose_platform, public;

-- ============================================================================
-- ENUMERATIONS
-- ============================================================================

CREATE TYPE service_state AS ENUM (
    'created',
    'starting',
    'running',
    'healthy',
    'unhealthy',
    'failed',
    'stopped'
);

CREATE TYPE dependency_condition AS ENUM (
    'service_started',
    'service_healthy',
    'service_completed_successfully'
);

CREATE TYPE restart_policy AS ENUM (
    'no',
    'always',
    'on-failure',
    'unless-stopped'
);

CREATE TYPE deployment_state AS ENUM (
    'pending',
    'deploying',
    'running',
    'failed',
    'stopped'
);

CREATE TYPE health_result AS ENUM (
    'starting',
    'healthy',
    'unhealthy'
);

CREATE TYPE event_severity AS ENUM (
    'info',
    'warning',
    'error'
);

-- ============================================================================
-- PROJECTS
-- ============================================================================

CREATE TABLE projects (
    project_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_name VARCHAR(120) NOT NULL UNIQUE,
    compose_version VARCHAR(20) NOT NULL DEFAULT '3.9',
    description TEXT,
    environment_name VARCHAR(40) NOT NULL DEFAULT 'development',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_project_name
        CHECK (project_name ~ '^[a-zA-Z0-9][a-zA-Z0-9_-]*$'),

    CONSTRAINT valid_environment
        CHECK (
            environment_name IN (
                'development',
                'testing',
                'staging',
                'production'
            )
        )
);

-- ============================================================================
-- NETWORKS
-- ============================================================================

CREATE TABLE networks (
    network_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id BIGINT NOT NULL
        REFERENCES projects(project_id) ON DELETE CASCADE,

    network_name VARCHAR(100) NOT NULL,
    driver VARCHAR(30) NOT NULL DEFAULT 'bridge',
    internal BOOLEAN NOT NULL DEFAULT FALSE,
    external BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE(project_id, network_name),

    CONSTRAINT valid_network_driver
        CHECK (driver IN ('bridge', 'overlay', 'host', 'macvlan'))
);

-- ============================================================================
-- VOLUMES
-- ============================================================================

CREATE TABLE volumes (
    volume_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id BIGINT NOT NULL
        REFERENCES projects(project_id) ON DELETE CASCADE,

    volume_name VARCHAR(100) NOT NULL,
    driver VARCHAR(30) NOT NULL DEFAULT 'local',
    external BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE(project_id, volume_name)
);

-- ============================================================================
-- SERVICES
-- ============================================================================

CREATE TABLE services (
    service_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL
        REFERENCES projects(project_id) ON DELETE CASCADE,

    service_name VARCHAR(100) NOT NULL,
    image VARCHAR(255) NOT NULL,
    image_tag VARCHAR(100) NOT NULL DEFAULT 'latest',

    command TEXT,
    entrypoint TEXT,

    restart restart_policy NOT NULL DEFAULT 'no',

    replicas INTEGER NOT NULL DEFAULT 1,

    healthcheck_command TEXT,
    healthcheck_interval_seconds INTEGER NOT NULL DEFAULT 10,
    healthcheck_timeout_seconds INTEGER NOT NULL DEFAULT 5,
    healthcheck_retries INTEGER NOT NULL DEFAULT 3,
    healthcheck_start_period_seconds INTEGER NOT NULL DEFAULT 0,

    cpu_limit NUMERIC(8,3),
    memory_limit_mb INTEGER,

    read_only_root_filesystem BOOLEAN NOT NULL DEFAULT FALSE,
    privileged BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(project_id, service_name),

    CONSTRAINT valid_service_name
        CHECK (service_name ~ '^[a-zA-Z0-9][a-zA-Z0-9_.-]*$'),

    CONSTRAINT valid_image
        CHECK (length(trim(image)) > 0),

    CONSTRAINT positive_replicas
        CHECK (replicas > 0),

    CONSTRAINT valid_healthcheck
        CHECK (
            healthcheck_interval_seconds > 0
            AND healthcheck_timeout_seconds > 0
            AND healthcheck_retries > 0
            AND healthcheck_start_period_seconds >= 0
        ),

    CONSTRAINT valid_resource_limits
        CHECK (
            (cpu_limit IS NULL OR cpu_limit > 0)
            AND
            (memory_limit_mb IS NULL OR memory_limit_mb > 0)
        )
);

CREATE INDEX idx_services_project
    ON services(project_id, service_name);

-- ============================================================================
-- ENVIRONMENT VARIABLES
-- ============================================================================

CREATE TABLE service_environment (
    environment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_id BIGINT NOT NULL
        REFERENCES services(service_id) ON DELETE CASCADE,

    variable_name VARCHAR(128) NOT NULL,

    variable_value TEXT,
    required BOOLEAN NOT NULL DEFAULT FALSE,

    is_secret BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE(service_id, variable_name),

    CONSTRAINT valid_variable_name
        CHECK (variable_name ~ '^[A-Za-z_][A-Za-z0-9_]*$'),

    CONSTRAINT required_value_present
        CHECK (NOT required OR variable_value IS NOT NULL)
);

-- Secret values should be represented by secret-manager references
-- in production rather than stored as plaintext.

-- ============================================================================
-- PORT MAPPINGS
-- ============================================================================

CREATE TABLE service_ports (
    port_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_id BIGINT NOT NULL
        REFERENCES services(service_id) ON DELETE CASCADE,

    host_port INTEGER NOT NULL,
    container_port INTEGER NOT NULL,

    protocol VARCHAR(3) NOT NULL DEFAULT 'tcp',

    UNIQUE(service_id, host_port, protocol),

    CONSTRAINT valid_host_port
        CHECK (host_port BETWEEN 1 AND 65535),

    CONSTRAINT valid_container_port
        CHECK (container_port BETWEEN 1 AND 65535),

    CONSTRAINT valid_port_protocol
        CHECK (protocol IN ('tcp', 'udp'))
);

-- ============================================================================
-- SERVICE NETWORK MEMBERSHIP
-- ============================================================================

CREATE TABLE service_networks (
    service_id BIGINT NOT NULL
        REFERENCES services(service_id) ON DELETE CASCADE,

    network_id BIGINT NOT NULL
        REFERENCES networks(network_id) ON DELETE CASCADE,

    PRIMARY KEY(service_id, network_id)
);

-- ============================================================================
-- SERVICE VOLUME MOUNTS
-- ============================================================================

CREATE TABLE service_volumes (
    mount_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_id BIGINT NOT NULL
        REFERENCES services(service_id) ON DELETE CASCADE,

    volume_id BIGINT NOT NULL
        REFERENCES volumes(volume_id) ON DELETE CASCADE,

    container_path TEXT NOT NULL,
    read_only BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE(service_id, container_path),

    CONSTRAINT valid_container_path
        CHECK (
            left(container_path, 1) = '/'
            AND position('/../' IN container_path) = 0
        )
);

-- ============================================================================
-- DEPENDENCIES
-- ============================================================================

CREATE TABLE service_dependencies (
    dependency_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_id BIGINT NOT NULL
        REFERENCES services(service_id) ON DELETE CASCADE,

    depends_on_service_id BIGINT NOT NULL
        REFERENCES services(service_id) ON DELETE CASCADE,

    condition dependency_condition NOT NULL DEFAULT 'service_started',

    UNIQUE(service_id, depends_on_service_id),

    CONSTRAINT no_self_dependency
        CHECK (service_id <> depends_on_service_id)
);

CREATE INDEX idx_dependencies_target
    ON service_dependencies(depends_on_service_id);

-- ============================================================================
-- DEPLOYMENTS
-- ============================================================================

CREATE TABLE deployments (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL
        REFERENCES projects(project_id),

    deployment_number INTEGER NOT NULL,

    state deployment_state NOT NULL DEFAULT 'pending',

    configuration_version VARCHAR(80) NOT NULL,

    initiated_by VARCHAR(120) NOT NULL,

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(project_id, deployment_number),

    CONSTRAINT valid_deployment_times
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        )
);

CREATE INDEX idx_deployments_project_state
    ON deployments(project_id, state, created_at DESC);

-- ============================================================================
-- RUNTIME SERVICE INSTANCES
-- ============================================================================

CREATE TABLE service_instances (
    instance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id) ON DELETE CASCADE,

    service_id BIGINT NOT NULL
        REFERENCES services(service_id),

    replica_number INTEGER NOT NULL DEFAULT 1,

    state service_state NOT NULL DEFAULT 'created',

    container_identifier VARCHAR(128),

    restart_count INTEGER NOT NULL DEFAULT 0,

    last_error TEXT,

    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,

    UNIQUE(deployment_id, service_id, replica_number),

    CONSTRAINT valid_replica_number
        CHECK (replica_number > 0),

    CONSTRAINT valid_restart_count
        CHECK (restart_count >= 0)
);

CREATE INDEX idx_instances_deployment_state
    ON service_instances(deployment_id, state);

CREATE INDEX idx_instances_service
    ON service_instances(service_id, state);

-- ============================================================================
-- HEALTH CHECK HISTORY
-- ============================================================================

CREATE TABLE health_checks (
    health_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    instance_id BIGINT NOT NULL
        REFERENCES service_instances(instance_id) ON DELETE CASCADE,

    result health_result NOT NULL,

    response_time_ms INTEGER,

    output TEXT,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_response_time
        CHECK (response_time_ms IS NULL OR response_time_ms >= 0)
);

CREATE INDEX idx_health_checks_instance_time
    ON health_checks(instance_id, checked_at DESC);

-- ============================================================================
-- DEPLOYMENT EVENTS
-- ============================================================================

CREATE TABLE deployment_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id) ON DELETE CASCADE,

    service_id BIGINT
        REFERENCES services(service_id) ON DELETE SET NULL,

    severity event_severity NOT NULL DEFAULT 'info',

    event_type VARCHAR(100) NOT NULL,

    message TEXT NOT NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_deployment_time
    ON deployment_events(deployment_id, occurred_at DESC);

-- ============================================================================
-- CONFIGURATION VALIDATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_project_configuration(
    p_project_id BIGINT
)
RETURNS TABLE (
    validation_code TEXT,
    validation_message TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM projects
        WHERE project_id = p_project_id
    ) THEN
        RETURN QUERY
        SELECT
            'PROJECT_NOT_FOUND'::TEXT,
            'Project does not exist'::TEXT;

        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM services
        WHERE project_id = p_project_id
    ) THEN
        RETURN QUERY
        SELECT
            'NO_SERVICES'::TEXT,
            'Project contains no services'::TEXT;
    END IF;

    -- Detect dependencies that cross project boundaries.
    RETURN QUERY
    SELECT
        'CROSS_PROJECT_DEPENDENCY'::TEXT,
        ('Service ' || s.service_name ||
         ' references a service outside its project')::TEXT
    FROM service_dependencies d
    JOIN services s
        ON s.service_id = d.service_id
    JOIN services target
        ON target.service_id = d.depends_on_service_id
    WHERE s.project_id = p_project_id
      AND target.project_id <> p_project_id;

    -- Check for missing required environment values.
    RETURN QUERY
    SELECT
        'MISSING_ENVIRONMENT'::TEXT,
        ('Missing environment variable ' ||
         e.variable_name || ' for ' || s.service_name)::TEXT
    FROM services s
    JOIN service_environment e
        ON e.service_id = s.service_id
    WHERE s.project_id = p_project_id
      AND e.required = TRUE
      AND e.variable_value IS NULL;

    -- Detect services attached to no networks.
    RETURN QUERY
    SELECT
        'NO_NETWORK'::TEXT,
        ('Service ' || s.service_name ||
         ' has no declared network membership')::TEXT
    FROM services s
    WHERE s.project_id = p_project_id
      AND NOT EXISTS (
          SELECT 1
          FROM service_networks sn
          WHERE sn.service_id = s.service_id
      );
END;
$$;

-- ============================================================================
-- DEPENDENCY CYCLE DETECTION
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_dependency_cycles(
    p_project_id BIGINT
)
RETURNS TABLE (
    service_name TEXT,
    has_cycle BOOLEAN
)
LANGUAGE sql
STABLE
AS $$
    WITH RECURSIVE dependency_paths AS (
        SELECT
            d.service_id AS origin,
            d.depends_on_service_id AS current_node,
            ARRAY[
                d.service_id,
                d.depends_on_service_id
            ]::BIGINT[] AS path,
            d.service_id = d.depends_on_service_id AS cycle
        FROM service_dependencies d
        JOIN services s
            ON s.service_id = d.service_id
        WHERE s.project_id = p_project_id

        UNION ALL

        SELECT
            p.origin,
            d.depends_on_service_id,
            p.path || d.depends_on_service_id,
            d.depends_on_service_id = ANY(p.path)
        FROM dependency_paths p
        JOIN service_dependencies d
            ON d.service_id = p.current_node
        JOIN services target
            ON target.service_id = d.depends_on_service_id
        WHERE p.cycle = FALSE
          AND target.project_id = p_project_id
          AND cardinality(p.path) <= 100
    )
    SELECT
        s.service_name::TEXT,
        EXISTS (
            SELECT 1
            FROM dependency_paths p
            WHERE p.origin = s.service_id
              AND p.cycle = TRUE
        )
    FROM services s
    WHERE s.project_id = p_project_id;
$$;

-- ============================================================================
-- DEPLOYMENT ELIGIBILITY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW deployment_eligibility AS
SELECT
    p.project_id,
    p.project_name,
    COUNT(DISTINCT s.service_id) AS service_count,

    COUNT(DISTINCT s.service_id)
        FILTER (WHERE s.privileged = TRUE) AS privileged_services,

    COUNT(DISTINCT s.service_id)
        FILTER (WHERE s.healthcheck_command IS NOT NULL)
        AS healthchecked_services,

    COUNT(DISTINCT s.service_id)
        FILTER (WHERE s.read_only_root_filesystem = TRUE)
        AS read_only_services,

    COUNT(DISTINCT s.service_id)
        FILTER (
            WHERE s.restart = 'no'
        ) AS services_without_restart,

    NOT EXISTS (
        SELECT 1
        FROM detect_dependency_cycles(p.project_id) c
        WHERE c.has_cycle = TRUE
    ) AS dependency_graph_valid

FROM projects p
LEFT JOIN services s
    ON s.project_id = p.project_id
GROUP BY p.project_id, p.project_name;

-- ============================================================================
-- DEPLOYMENT EVALUATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION evaluate_deployment(
    p_deployment_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    issue_count BIGINT,
    message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_project_id BIGINT;
    v_issues BIGINT := 0;
BEGIN
    SELECT project_id
    INTO v_project_id
    FROM deployments
    WHERE deployment_id = p_deployment_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Deployment % does not exist',
            p_deployment_id;
    END IF;

    SELECT COUNT(*)
    INTO v_issues
    FROM validate_project_configuration(v_project_id);

    SELECT v_issues + COUNT(*)
    INTO v_issues
    FROM detect_dependency_cycles(v_project_id)
    WHERE has_cycle = TRUE;

    RETURN QUERY
    SELECT
        v_issues = 0,
        v_issues,
        CASE
            WHEN v_issues = 0
                THEN 'Configuration eligible for deployment'
            ELSE
                'Configuration contains validation failures'
        END;
END;
$$;

-- ============================================================================
-- DEPLOYMENT START FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION start_deployment(
    p_project_id BIGINT,
    p_initiated_by TEXT,
    p_configuration_version TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_deployment_id BIGINT;
    v_next_number INTEGER;
    v_evaluation RECORD;
BEGIN
    IF p_initiated_by IS NULL OR
       length(trim(p_initiated_by)) = 0 THEN
        RAISE EXCEPTION 'Initiator is required';
    END IF;

    PERFORM 1
    FROM projects
    WHERE project_id = p_project_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Project does not exist';
    END IF;

    SELECT COALESCE(MAX(deployment_number), 0) + 1
    INTO v_next_number
    FROM deployments
    WHERE project_id = p_project_id;

    INSERT INTO deployments (
        project_id,
        deployment_number,
        state,
        configuration_version,
        initiated_by,
        started_at
    )
    VALUES (
        p_project_id,
        v_next_number,
        'deploying',
        p_configuration_version,
        p_initiated_by,
        CURRENT_TIMESTAMP
    )
    RETURNING deployment_id
    INTO v_deployment_id;

    SELECT *
    INTO v_evaluation
    FROM evaluate_deployment(v_deployment_id);

    IF NOT v_evaluation.eligible THEN
        UPDATE deployments
        SET
            state = 'failed',
            completed_at = CURRENT_TIMESTAMP,
            error_message = v_evaluation.message
        WHERE deployment_id = v_deployment_id;

        INSERT INTO deployment_events (
            deployment_id,
            severity,
            event_type,
            message
        )
        VALUES (
            v_deployment_id,
            'error',
            'configuration_rejected',
            v_evaluation.message
        );

        RETURN v_deployment_id;
    END IF;

    -- Create one runtime record for every configured replica.
    INSERT INTO service_instances (
        deployment_id,
        service_id,
        replica_number,
        state
    )
    SELECT
        v_deployment_id,
        s.service_id,
        replica.replica_number,
        'created'
    FROM services s
    CROSS JOIN LATERAL
        generate_series(1, s.replicas) AS replica(replica_number)
    WHERE s.project_id = p_project_id;

    INSERT INTO deployment_events (
        deployment_id,
        severity,
        event_type,
        message
    )
    VALUES (
        v_deployment_id,
        'info',
        'deployment_accepted',
        'Configuration passed database validation'
    );

    RETURN v_deployment_id;
END;
$$;

-- ============================================================================
-- INSTANCE STATE TRANSITION VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION enforce_instance_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = NEW.state THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.state = 'created'
            AND NEW.state IN ('starting', 'stopped'))
        OR
        (OLD.state = 'starting'
            AND NEW.state IN (
                'running', 'healthy', 'failed', 'stopped'
            ))
        OR
        (OLD.state = 'running'
            AND NEW.state IN (
                'unhealthy', 'failed', 'stopped', 'starting'
            ))
        OR
        (OLD.state = 'healthy'
            AND NEW.state IN (
                'unhealthy', 'failed', 'stopped', 'starting'
            ))
        OR
        (OLD.state = 'unhealthy'
            AND NEW.state IN (
                'failed', 'starting', 'stopped'
            ))
        OR
        (OLD.state = 'failed'
            AND NEW.state IN ('starting', 'stopped'))
        OR
        (OLD.state = 'stopped'
            AND NEW.state = 'starting')
    ) THEN
        RAISE EXCEPTION
            'Invalid service state transition: % -> %',
            OLD.state,
            NEW.state;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_instance_transition
BEFORE UPDATE OF state
ON service_instances
FOR EACH ROW
EXECUTE FUNCTION enforce_instance_transition();

-- ============================================================================
-- DEPLOYMENT STATUS RECONCILIATION
-- ============================================================================

CREATE OR REPLACE FUNCTION reconcile_deployment(
    p_deployment_id BIGINT
)
RETURNS deployment_state
LANGUAGE plpgsql
AS $$
DECLARE
    v_total BIGINT;
    v_running BIGINT;
    v_failed BIGINT;
    v_result deployment_state;
BEGIN
    SELECT
        COUNT(*),
        COUNT(*) FILTER (
            WHERE state IN ('running', 'healthy')
        ),
        COUNT(*) FILTER (
            WHERE state = 'failed'
        )
    INTO v_total, v_running, v_failed
    FROM service_instances
    WHERE deployment_id = p_deployment_id;

    IF NOT EXISTS (
        SELECT 1
        FROM deployments
        WHERE deployment_id = p_deployment_id
    ) THEN
        RAISE EXCEPTION 'Unknown deployment';
    END IF;

    IF v_failed > 0 THEN
        v_result := 'failed';

    ELSIF v_total > 0 AND v_running = v_total THEN
        v_result := 'running';

    ELSE
        v_result := 'deploying';
    END IF;

    UPDATE deployments
    SET
        state = v_result,
        completed_at = CASE
            WHEN v_result IN ('running', 'failed')
                THEN CURRENT_TIMESTAMP
            ELSE NULL
        END
    WHERE deployment_id = p_deployment_id;

    RETURN v_result;
END;
$$;

-- ============================================================================
-- REPORTING VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW project_service_inventory AS
SELECT
    p.project_name,
    s.service_name,
    s.image,
    s.image_tag,
    s.replicas,
    s.restart,
    s.healthcheck_command,
    s.cpu_limit,
    s.memory_limit_mb,
    s.privileged,
    s.read_only_root_filesystem
FROM projects p
JOIN services s
    ON s.project_id = p.project_id;

CREATE OR REPLACE VIEW deployment_service_status AS
SELECT
    d.deployment_id,
    p.project_name,
    d.deployment_number,
    d.state AS deployment_state,
    s.service_name,
    i.replica_number,
    i.state AS service_state,
    i.restart_count,
    i.last_error
FROM deployments d
JOIN projects p
    ON p.project_id = d.project_id
JOIN service_instances i
    ON i.deployment_id = d.deployment_id
JOIN services s
    ON s.service_id = i.service_id;

CREATE OR REPLACE VIEW latest_health_status AS
SELECT DISTINCT ON (i.instance_id)
    i.instance_id,
    s.service_name,
    h.result,
    h.response_time_ms,
    h.checked_at
FROM service_instances i
JOIN services s
    ON s.service_id = i.service_id
JOIN health_checks h
    ON h.instance_id = i.instance_id
ORDER BY i.instance_id, h.checked_at DESC;

-- ============================================================================
-- SAMPLE PROJECT
-- ============================================================================

INSERT INTO projects (
    project_name,
    compose_version,
    description,
    environment_name
)
VALUES (
    'inventory-platform',
    '3.9',
    'Multi-container inventory application',
    'development'
);

INSERT INTO networks (
    project_id,
    network_name,
    driver,
    internal
)
SELECT project_id, 'frontend', 'bridge', FALSE
FROM projects
WHERE project_name = 'inventory-platform';

INSERT INTO networks (
    project_id,
    network_name,
    driver,
    internal
)
SELECT project_id, 'backend', 'bridge', TRUE
FROM projects
WHERE project_name = 'inventory-platform';

INSERT INTO volumes (
    project_id,
    volume_name,
    driver
)
SELECT project_id, 'database-data', 'local'
FROM projects
WHERE project_name = 'inventory-platform';

-- ============================================================================
-- SAMPLE SERVICES
-- ============================================================================

INSERT INTO services (
    project_id,
    service_name,
    image,
    image_tag,
    restart,
    healthcheck_command,
    healthcheck_interval_seconds,
    healthcheck_retries,
    replicas,
    memory_limit_mb,
    read_only_root_filesystem
)
SELECT
    project_id,
    'database',
    'postgres',
    '18',
    'unless-stopped',
    'pg_isready',
    10,
    3,
    1,
    1024,
    FALSE
FROM projects
WHERE project_name = 'inventory-platform';

INSERT INTO services (
    project_id,
    service_name,
    image,
    image_tag,
    restart,
    healthcheck_command,
    replicas,
    memory_limit_mb
)
SELECT
    project_id,
    'cache',
    'redis',
    '8',
    'always',
    'redis-cli ping',
    1,
    256
FROM projects
WHERE project_name = 'inventory-platform';

INSERT INTO services (
    project_id,
    service_name,
    image,
    image_tag,
    restart,
    healthcheck_command,
    replicas,
    memory_limit_mb
)
SELECT
    project_id,
    'api',
    'inventory-api',
    '1.0',
    'on-failure',
    'curl -f localhost:8000/health',
    2,
    1024
FROM projects
WHERE project_name = 'inventory-platform';

INSERT INTO services (
    project_id,
    service_name,
    image,
    image_tag,
    restart,
    replicas,
    memory_limit_mb
)
SELECT
    project_id,
    'web',
    'inventory-web',
    '1.0',
    'unless-stopped',
    2,
    512
FROM projects
WHERE project_name = 'inventory-platform';

-- ============================================================================
-- ENVIRONMENT CONFIGURATION
-- ============================================================================

INSERT INTO service_environment (
    service_id,
    variable_name,
    variable_value,
    required,
    is_secret
)
SELECT
    service_id,
    'POSTGRES_DB',
    'inventory',
    TRUE,
    FALSE
FROM services
WHERE service_name = 'database';

INSERT INTO service_environment (
    service_id,
    variable_name,
    variable_value,
    required,
    is_secret
)
SELECT
    service_id,
    'POSTGRES_PASSWORD',
    'development-only-secret',
    TRUE,
    TRUE
FROM services
WHERE service_name = 'database';

INSERT INTO service_environment (
    service_id,
    variable_name,
    variable_value,
    required
)
SELECT
    service_id,
    'DATABASE_HOST',
    'database',
    TRUE
FROM services
WHERE service_name = 'api';

INSERT INTO service_environment (
    service_id,
    variable_name,
    variable_value,
    required
)
SELECT
    service_id,
    'CACHE_HOST',
    'cache',
    TRUE
FROM services
WHERE service_name = 'api';

-- ============================================================================
-- PORT CONFIGURATION
-- ============================================================================

INSERT INTO service_ports (
    service_id,
    host_port,
    container_port,
    protocol
)
SELECT service_id, 8000, 8000, 'tcp'
FROM services
WHERE service_name = 'api';

INSERT INTO service_ports (
    service_id,
    host_port,
    container_port,
    protocol
)
SELECT service_id, 8080, 80, 'tcp'
FROM services
WHERE service_name = 'web';

-- ============================================================================
-- NETWORK MEMBERSHIP
-- ============================================================================

INSERT INTO service_networks (
    service_id,
    network_id
)
SELECT s.service_id, n.network_id
FROM services s
JOIN projects p
    ON p.project_id = s.project_id
JOIN networks n
    ON n.project_id = p.project_id
WHERE p.project_name = 'inventory-platform'
  AND (
      (s.service_name IN ('database', 'cache', 'api')
       AND n.network_name = 'backend')
      OR
      (s.service_name IN ('api', 'web')
       AND n.network_name = 'frontend')
  );

-- ============================================================================
-- VOLUME MOUNT
-- ============================================================================

INSERT INTO service_volumes (
    service_id,
    volume_id,
    container_path,
    read_only
)
SELECT
    s.service_id,
    v.volume_id,
    '/var/lib/postgresql/data',
    FALSE
FROM services s
JOIN volumes v
    ON v.project_id = s.project_id
WHERE s.service_name = 'database'
  AND v.volume_name = 'database-data';

-- ============================================================================
-- SERVICE DEPENDENCIES
-- ============================================================================

INSERT INTO service_dependencies (
    service_id,
    depends_on_service_id,
    condition
)
SELECT
    dependent.service_id,
    dependency.service_id,
    'service_healthy'
FROM services dependent
JOIN services dependency
    ON dependency.project_id = dependent.project_id
WHERE
    (dependent.service_name = 'api'
     AND dependency.service_name IN ('database', 'cache'))
    OR
    (dependent.service_name = 'web'
     AND dependency.service_name = 'api');

-- ============================================================================
-- CONFIGURATION VALIDATION
-- ============================================================================

SELECT *
FROM validate_project_configuration(
    (
        SELECT project_id
        FROM projects
        WHERE project_name = 'inventory-platform'
    )
);

SELECT *
FROM detect_dependency_cycles(
    (
        SELECT project_id
        FROM projects
        WHERE project_name = 'inventory-platform'
    )
);

SELECT *
FROM deployment_eligibility;

-- ============================================================================
-- CREATE A DEPLOYMENT
-- ============================================================================

DO $$
DECLARE
    v_deployment_id BIGINT;
    v_project_id BIGINT;
BEGIN
    SELECT project_id
    INTO v_project_id
    FROM projects
    WHERE project_name = 'inventory-platform';

    v_deployment_id := start_deployment(
        v_project_id,
        'deployment-operator',
        'configuration-v1'
    );

    RAISE NOTICE 'Created deployment ID: %', v_deployment_id;
END;
$$;

-- ============================================================================
-- SIMULATE SUCCESSFUL STARTUP
-- ============================================================================

UPDATE service_instances
SET state = 'starting'
WHERE deployment_id = (
    SELECT MAX(deployment_id)
    FROM deployments
)
AND state = 'created';

-- Database health check.
UPDATE service_instances i
SET state = 'healthy',
    started_at = CURRENT_TIMESTAMP
FROM services s
WHERE i.service_id = s.service_id
  AND s.service_name = 'database'
  AND i.deployment_id = (
      SELECT MAX(deployment_id) FROM deployments
  );

-- Cache health check.
UPDATE service_instances i
SET state = 'healthy',
    started_at = CURRENT_TIMESTAMP
FROM services s
WHERE i.service_id = s.service_id
  AND s.service_name = 'cache'
  AND i.deployment_id = (
      SELECT MAX(deployment_id) FROM deployments
  );

-- API startup.
UPDATE service_instances i
SET state = 'healthy',
    started_at = CURRENT_TIMESTAMP
FROM services s
WHERE i.service_id = s.service_id
  AND s.service_name = 'api'
  AND i.deployment_id = (
      SELECT MAX(deployment_id) FROM deployments
  );

-- Web startup.
UPDATE service_instances i
SET state = 'running',
    started_at = CURRENT_TIMESTAMP
FROM services s
WHERE i.service_id = s.service_id
  AND s.service_name = 'web'
  AND i.deployment_id = (
      SELECT MAX(deployment_id) FROM deployments
  );

-- ============================================================================
-- HEALTH CHECK OBSERVATIONS
-- ============================================================================

INSERT INTO health_checks (
    instance_id,
    result,
    response_time_ms,
    output
)
SELECT
    i.instance_id,
    'healthy',
    8,
    'Health check successful'
FROM service_instances i
JOIN services s
    ON s.service_id = i.service_id
WHERE i.deployment_id = (
    SELECT MAX(deployment_id) FROM deployments
)
AND s.service_name IN ('database', 'cache', 'api');

-- ============================================================================
-- RECONCILE DEPLOYMENT
-- ============================================================================

SELECT reconcile_deployment(
    (SELECT MAX(deployment_id) FROM deployments)
);

-- ============================================================================
-- SAMPLE FAILURE SCENARIO
-- ============================================================================

INSERT INTO deployment_events (
    deployment_id,
    service_id,
    severity,
    event_type,
    message
)
SELECT
    d.deployment_id,
    s.service_id,
    'warning',
    'health_warning',
    'Simulated temporary cache latency'
FROM deployments d
JOIN services s
    ON s.project_id = d.project_id
WHERE d.deployment_id = (
    SELECT MAX(deployment_id) FROM deployments
)
AND s.service_name = 'cache';

-- ============================================================================
-- RETRIEVAL QUERIES
-- ============================================================================

-- 1. Retrieve every service and its configuration.

SELECT *
FROM project_service_inventory
WHERE project_name = 'inventory-platform'
ORDER BY service_name;

-- 2. Retrieve service dependency relationships.

SELECT
    source.service_name AS service,
    target.service_name AS dependency,
    d.condition
FROM service_dependencies d
JOIN services source
    ON source.service_id = d.service_id
JOIN services target
    ON target.service_id = d.depends_on_service_id
ORDER BY source.service_name, target.service_name;

-- 3. Retrieve deployment history.

SELECT
    p.project_name,
    d.deployment_number,
    d.state,
    d.configuration_version,
    d.initiated_by,
    d.started_at,
    d.completed_at
FROM deployments d
JOIN projects p
    ON p.project_id = d.project_id
ORDER BY d.created_at DESC;

-- 4. Retrieve running and failed instances.

SELECT *
FROM deployment_service_status
WHERE service_state IN ('running', 'healthy', 'failed')
ORDER BY deployment_id, service_name;

-- ============================================================================
-- AGGREGATION AND REPORTING
-- ============================================================================

-- 5. Count services by runtime state.

SELECT
    service_state,
    COUNT(*) AS instance_count
FROM deployment_service_status
GROUP BY service_state
ORDER BY instance_count DESC;

-- 6. Calculate restart activity.

SELECT
    s.service_name,
    SUM(i.restart_count) AS total_restarts,
    COUNT(*) AS instance_count
FROM service_instances i
JOIN services s
    ON s.service_id = i.service_id
GROUP BY s.service_name
ORDER BY total_restarts DESC;

-- 7. Find latest health-check results.

SELECT *
FROM latest_health_status
ORDER BY checked_at DESC;

-- 8. Measure health-check latency.

SELECT
    s.service_name,
    COUNT(*) AS check_count,
    AVG(h.response_time_ms) AS average_latency_ms,
    MAX(h.response_time_ms) AS maximum_latency_ms
FROM health_checks h
JOIN service_instances i
    ON i.instance_id = h.instance_id
JOIN services s
    ON s.service_id = i.service_id
GROUP BY s.service_name;

-- ============================================================================
-- ELIGIBILITY AND VALIDATION REPORTING
-- ============================================================================

-- 9. Identify privileged services.

SELECT
    service_name,
    image,
    privileged
FROM project_service_inventory
WHERE privileged = TRUE;

-- 10. Identify services lacking health checks.

SELECT
    service_name,
    image
FROM project_service_inventory
WHERE healthcheck_command IS NULL;

-- 11. Evaluate the latest deployment.

SELECT *
FROM evaluate_deployment(
    (SELECT MAX(deployment_id) FROM deployments)
);

-- 12. Identify projects with invalid dependency graphs.

SELECT
    p.project_name,
    c.service_name,
    c.has_cycle
FROM projects p
CROSS JOIN LATERAL
    detect_dependency_cycles(p.project_id) c
WHERE c.has_cycle = TRUE;

-- ============================================================================
-- FAILURE HANDLING EXAMPLE
-- ============================================================================

-- The following transaction demonstrates rollback if an invalid
-- state transition is attempted.

DO $$
DECLARE
    v_instance_id BIGINT;
BEGIN
    SELECT instance_id
    INTO v_instance_id
    FROM service_instances
    WHERE deployment_id = (
        SELECT MAX(deployment_id) FROM deployments
    )
    LIMIT 1;

    IF v_instance_id IS NOT NULL THEN
        BEGIN
            UPDATE service_instances
            SET state = 'created'
            WHERE instance_id = v_instance_id;

        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE
                    'Invalid transition rejected: %',
                    SQLERRM;
        END;
    END IF;
END;
$$;

-- ============================================================================
-- FINAL DEPLOYMENT REPORT
-- ============================================================================

SELECT
    d.deployment_id,
    p.project_name,
    d.state AS deployment_state,
    COUNT(i.instance_id) AS total_instances,
    COUNT(i.instance_id)
        FILTER (
            WHERE i.state = 'healthy'
        ) AS healthy_instances,
    COUNT(i.instance_id)
        FILTER (
            WHERE i.state = 'failed'
        ) AS failed_instances
FROM deployments d
JOIN projects p
    ON p.project_id = d.project_id
LEFT JOIN service_instances i
    ON i.deployment_id = d.deployment_id
GROUP BY
    d.deployment_id,
    p.project_name,
    d.state
ORDER BY d.deployment_id DESC;

COMMIT;
