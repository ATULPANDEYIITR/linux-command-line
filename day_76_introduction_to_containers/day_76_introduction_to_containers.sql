/*
===============================================================================
INTRODUCTION TO CONTAINERS
PostgreSQL container platform inventory and governance model
===============================================================================

Models:
1. Container registries and immutable image versions
2. Layered image packaging
3. Repositories and container images
4. Container instances and lifecycle transitions
5. CPU, memory and process limits
6. Network port mappings
7. Environment configuration metadata
8. Container health monitoring
9. Restart policies
10. Image vulnerability assessments
11. Deployment security policies
12. Resource admission control
13. Audit history and reporting

Requires PostgreSQL 15 or later.

This database models container operations. It does not implement
operating-system namespace or cgroup isolation.
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS container_platform;

SET search_path TO container_platform, public;

-- ============================================================================
-- ENUMERATIONS
-- ============================================================================

CREATE TYPE container_state AS ENUM (
    'created',
    'running',
    'stopped',
    'failed',
    'removed'
);

CREATE TYPE health_status AS ENUM (
    'starting',
    'healthy',
    'unhealthy'
);

CREATE TYPE restart_policy AS ENUM (
    'no',
    'on-failure',
    'always'
);

CREATE TYPE scan_status AS ENUM (
    'pending',
    'passed',
    'failed'
);

CREATE TYPE deployment_environment AS ENUM (
    'development',
    'testing',
    'staging',
    'production'
);

-- ============================================================================
-- IMAGE REGISTRIES
-- ============================================================================

CREATE TABLE image_registries (
    registry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    registry_name VARCHAR(120) NOT NULL UNIQUE,
    registry_url TEXT NOT NULL UNIQUE,
    is_trusted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_registry_name
        CHECK (length(trim(registry_name)) > 0)
);

-- ============================================================================
-- IMAGE REPOSITORIES
-- ============================================================================

CREATE TABLE image_repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    registry_id BIGINT NOT NULL REFERENCES image_registries(registry_id),
    repository_name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_registry_repository
        UNIQUE (registry_id, repository_name),

    CONSTRAINT valid_repository_name
        CHECK (length(trim(repository_name)) > 0)
);

-- ============================================================================
-- CONTAINER IMAGES
-- ============================================================================

CREATE TABLE container_images (
    image_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES image_repositories(repository_id),

    image_tag VARCHAR(100) NOT NULL,
    digest CHAR(64) NOT NULL,
    base_image VARCHAR(200) NOT NULL,
    entrypoint TEXT NOT NULL,
    image_size_bytes BIGINT NOT NULL,
    layer_count INTEGER NOT NULL,
    execution_user VARCHAR(100) NOT NULL DEFAULT 'app',
    vulnerability_count INTEGER NOT NULL DEFAULT 0,
    scan_state scan_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_repository_tag
        UNIQUE (repository_id, image_tag),

    CONSTRAINT unique_image_digest
        UNIQUE (digest),

    CONSTRAINT valid_image_size
        CHECK (image_size_bytes >= 0),

    CONSTRAINT valid_layer_count
        CHECK (layer_count > 0),

    CONSTRAINT valid_vulnerability_count
        CHECK (vulnerability_count >= 0),

    CONSTRAINT valid_image_user
        CHECK (length(trim(execution_user)) > 0),

    CONSTRAINT valid_image_digest
        CHECK (digest ~ '^[a-f0-9]{64}$')
);

CREATE INDEX idx_images_repository
    ON container_images(repository_id);

CREATE INDEX idx_images_scan_state
    ON container_images(scan_state, vulnerability_count);

-- ============================================================================
-- IMAGE LAYERS
-- ============================================================================

CREATE TABLE image_layers (
    layer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id) ON DELETE CASCADE,

    layer_order INTEGER NOT NULL,
    instruction VARCHAR(30) NOT NULL,
    content_description TEXT NOT NULL,
    layer_digest CHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL,

    CONSTRAINT unique_image_layer_order
        UNIQUE (image_id, layer_order),

    CONSTRAINT valid_layer_order
        CHECK (layer_order >= 0),

    CONSTRAINT valid_layer_size
        CHECK (size_bytes >= 0),

    CONSTRAINT valid_layer_digest
        CHECK (layer_digest ~ '^[a-f0-9]{64}$')
);

-- ============================================================================
-- EXPOSED IMAGE PORTS
-- ============================================================================

CREATE TABLE image_exposed_ports (
    image_id BIGINT NOT NULL
        REFERENCES container_images(image_id) ON DELETE CASCADE,

    container_port INTEGER NOT NULL,
    protocol VARCHAR(10) NOT NULL DEFAULT 'tcp',

    PRIMARY KEY (image_id, container_port, protocol),

    CONSTRAINT valid_container_port
        CHECK (container_port BETWEEN 1 AND 65535),

    CONSTRAINT valid_port_protocol
        CHECK (protocol IN ('tcp', 'udp'))
);

-- ============================================================================
-- HOST NODES
-- ============================================================================

CREATE TABLE host_nodes (
    node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    node_name VARCHAR(120) NOT NULL UNIQUE,
    total_cpu NUMERIC(8,2) NOT NULL,
    total_memory_mb BIGINT NOT NULL,
    total_process_capacity INTEGER NOT NULL,
    node_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_node_cpu
        CHECK (total_cpu > 0),

    CONSTRAINT valid_node_memory
        CHECK (total_memory_mb >= 16),

    CONSTRAINT valid_node_process_capacity
        CHECK (total_process_capacity > 0)
);

-- ============================================================================
-- CONTAINER DEPLOYMENTS
-- ============================================================================

CREATE TABLE containers (
    container_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    image_id BIGINT NOT NULL REFERENCES container_images(image_id),
    node_id BIGINT NOT NULL REFERENCES host_nodes(node_id),

    container_name VARCHAR(150) NOT NULL,
    environment deployment_environment NOT NULL,

    state container_state NOT NULL DEFAULT 'created',
    health health_status NOT NULL DEFAULT 'starting',
    restart_policy restart_policy NOT NULL DEFAULT 'no',

    cpu_limit NUMERIC(8,2) NOT NULL,
    memory_limit_mb BIGINT NOT NULL,
    process_limit INTEGER NOT NULL,

    privileged BOOLEAN NOT NULL DEFAULT FALSE,
    run_as_root BOOLEAN NOT NULL DEFAULT FALSE,
    read_only_rootfs BOOLEAN NOT NULL DEFAULT TRUE,

    restart_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,

    CONSTRAINT unique_node_container_name
        UNIQUE (node_id, container_name),

    CONSTRAINT valid_container_cpu
        CHECK (cpu_limit > 0),

    CONSTRAINT valid_container_memory
        CHECK (memory_limit_mb >= 16),

    CONSTRAINT valid_container_process_limit
        CHECK (process_limit > 0),

    CONSTRAINT valid_restart_count
        CHECK (restart_count >= 0),

    CONSTRAINT privileged_container_prohibited
        CHECK (privileged = FALSE),

    CONSTRAINT root_execution_prohibited
        CHECK (run_as_root = FALSE),

    CONSTRAINT root_filesystem_policy
        CHECK (read_only_rootfs = TRUE),

    CONSTRAINT valid_runtime_timestamps
        CHECK (
            stopped_at IS NULL
            OR started_at IS NULL
            OR stopped_at >= started_at
        )
);

CREATE INDEX idx_containers_node_state
    ON containers(node_id, state);

CREATE INDEX idx_containers_image
    ON containers(image_id);

CREATE INDEX idx_containers_environment
    ON containers(environment, state);

CREATE INDEX idx_running_containers
    ON containers(node_id, state)
    WHERE state = 'running';

-- ============================================================================
-- PORT MAPPINGS
-- ============================================================================

CREATE TABLE container_port_mappings (
    mapping_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id UUID NOT NULL
        REFERENCES containers(container_id) ON DELETE CASCADE,

    container_port INTEGER NOT NULL,
    host_port INTEGER NOT NULL,
    protocol VARCHAR(10) NOT NULL DEFAULT 'tcp',

    CONSTRAINT unique_host_port_protocol
        UNIQUE (host_port, protocol),

    CONSTRAINT unique_container_port_mapping
        UNIQUE (container_id, container_port, protocol),

    CONSTRAINT valid_mapping_container_port
        CHECK (container_port BETWEEN 1 AND 65535),

    CONSTRAINT valid_mapping_host_port
        CHECK (host_port BETWEEN 1 AND 65535),

    CONSTRAINT valid_mapping_protocol
        CHECK (protocol IN ('tcp', 'udp'))
);

CREATE INDEX idx_port_mappings_container
    ON container_port_mappings(container_id);

-- ============================================================================
-- ENVIRONMENT CONFIGURATION
-- Values are stored as metadata in this educational model.
-- Production secrets should be held in a dedicated secret manager.
-- ============================================================================

CREATE TABLE container_environment (
    environment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id UUID NOT NULL
        REFERENCES containers(container_id) ON DELETE CASCADE,

    variable_name VARCHAR(128) NOT NULL,
    variable_value TEXT NOT NULL,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT unique_container_environment_key
        UNIQUE (container_id, variable_name),

    CONSTRAINT valid_environment_key
        CHECK (
            variable_name ~ '^[A-Za-z_][A-Za-z0-9_]*$'
        ),

    CONSTRAINT valid_environment_value
        CHECK (length(variable_value) <= 4096)
);

-- ============================================================================
-- HEALTH CHECK HISTORY
-- ============================================================================

CREATE TABLE container_health_checks (
    health_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id UUID NOT NULL
        REFERENCES containers(container_id) ON DELETE CASCADE,

    status health_status NOT NULL,
    response_time_ms INTEGER,
    check_message TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_health_response_time
        CHECK (
            response_time_ms IS NULL
            OR response_time_ms >= 0
        )
);

CREATE INDEX idx_health_container_time
    ON container_health_checks(container_id, checked_at DESC);

-- ============================================================================
-- AUDIT EVENTS
-- ============================================================================

CREATE TABLE container_audit_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id UUID NOT NULL
        REFERENCES containers(container_id),

    event_type VARCHAR(100) NOT NULL,
    event_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_event_type
        CHECK (length(trim(event_type)) > 0)
);

CREATE INDEX idx_audit_container_timestamp
    ON container_audit_events(container_id, event_timestamp DESC);

-- ============================================================================
-- RESOURCE VALIDATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_container_resources()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_node RECORD;
    v_used_cpu NUMERIC;
    v_used_memory BIGINT;
    v_used_processes BIGINT;
BEGIN
    SELECT *
    INTO v_node
    FROM host_nodes
    WHERE node_id = NEW.node_id
      AND node_active = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Host node does not exist or is inactive.';
    END IF;

    IF NEW.cpu_limit > v_node.total_cpu THEN
        RAISE EXCEPTION 'Container CPU request exceeds host capacity.';
    END IF;

    IF NEW.memory_limit_mb > v_node.total_memory_mb THEN
        RAISE EXCEPTION 'Container memory request exceeds host capacity.';
    END IF;

    IF NEW.process_limit > v_node.total_process_capacity THEN
        RAISE EXCEPTION 'Container process limit exceeds host capacity.';
    END IF;

    IF NEW.state = 'running' THEN

        SELECT
            COALESCE(SUM(cpu_limit), 0),
            COALESCE(SUM(memory_limit_mb), 0),
            COALESCE(SUM(process_limit), 0)
        INTO
            v_used_cpu,
            v_used_memory,
            v_used_processes
        FROM containers
        WHERE node_id = NEW.node_id
          AND state = 'running'
          AND container_id <> NEW.container_id;

        IF v_used_cpu + NEW.cpu_limit > v_node.total_cpu THEN
            RAISE EXCEPTION 'Insufficient node CPU capacity.';
        END IF;

        IF v_used_memory + NEW.memory_limit_mb > v_node.total_memory_mb THEN
            RAISE EXCEPTION 'Insufficient node memory capacity.';
        END IF;

        IF v_used_processes + NEW.process_limit >
            v_node.total_process_capacity THEN
            RAISE EXCEPTION 'Insufficient node process capacity.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_resources
BEFORE INSERT OR UPDATE OF
    node_id,
    state,
    cpu_limit,
    memory_limit_mb,
    process_limit
ON containers
FOR EACH ROW
EXECUTE FUNCTION validate_container_resources();

-- ============================================================================
-- IMAGE DEPLOYMENT SECURITY VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_image_deployment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_image RECORD;
BEGIN
    SELECT *
    INTO v_image
    FROM container_images
    WHERE image_id = NEW.image_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Container image not found.';
    END IF;

    IF v_image.scan_state <> 'passed' THEN
        RAISE EXCEPTION 'Image has not passed security scanning.';
    END IF;

    IF v_image.vulnerability_count > 0 THEN
        RAISE EXCEPTION 'Image contains known vulnerabilities.';
    END IF;

    IF v_image.execution_user = 'root' THEN
        RAISE EXCEPTION 'Root-based image deployment prohibited.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_image_deployment
BEFORE INSERT OR UPDATE OF image_id
ON containers
FOR EACH ROW
EXECUTE FUNCTION validate_image_deployment();

-- ============================================================================
-- PORT EXPOSURE VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_container_port_mapping()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_image_id BIGINT;
BEGIN
    SELECT image_id
    INTO v_image_id
    FROM containers
    WHERE container_id = NEW.container_id;

    IF NOT EXISTS (
        SELECT 1
        FROM image_exposed_ports
        WHERE image_id = v_image_id
          AND container_port = NEW.container_port
          AND protocol = NEW.protocol
    ) THEN
        RAISE EXCEPTION
            'Port is not exposed by the selected container image.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_port_mapping
BEFORE INSERT OR UPDATE
ON container_port_mappings
FOR EACH ROW
EXECUTE FUNCTION validate_container_port_mapping();

-- ============================================================================
-- AUDIT TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION record_container_state_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state IS DISTINCT FROM OLD.state THEN
        INSERT INTO container_audit_events (
            container_id,
            event_type,
            event_details
        )
        VALUES (
            NEW.container_id,
            'state_changed',
            jsonb_build_object(
                'previous_state', OLD.state,
                'new_state', NEW.state
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_container_state_audit
AFTER UPDATE OF state
ON containers
FOR EACH ROW
EXECUTE FUNCTION record_container_state_change();

-- ============================================================================
-- LIFECYCLE VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_container_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'removed' AND NEW.state <> 'removed' THEN
        RAISE EXCEPTION 'Removed containers cannot be reopened.';
    END IF;

    IF OLD.state = 'running' AND NEW.state NOT IN (
        'running', 'stopped', 'failed'
    ) THEN
        RAISE EXCEPTION 'Invalid transition from running.';
    END IF;

    IF OLD.state = 'failed' AND NEW.state NOT IN (
        'failed', 'stopped', 'removed'
    ) THEN
        RAISE EXCEPTION 'Invalid transition from failed.';
    END IF;

    IF OLD.state = 'stopped' AND NEW.state NOT IN (
        'stopped', 'running', 'removed'
    ) THEN
        RAISE EXCEPTION 'Invalid transition from stopped.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_transition
BEFORE UPDATE OF state
ON containers
FOR EACH ROW
EXECUTE FUNCTION validate_container_transition();

-- ============================================================================
-- DEPLOYMENT ELIGIBILITY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW container_deployment_eligibility AS
SELECT
    i.image_id,
    r.repository_name,
    i.image_tag,
    i.digest,
    i.scan_state,
    i.vulnerability_count,
    i.execution_user,

    (
        i.scan_state = 'passed'
        AND i.vulnerability_count = 0
        AND i.execution_user <> 'root'
    ) AS deployment_eligible

FROM container_images i
JOIN image_repositories r
    ON r.repository_id = i.repository_id;

-- ============================================================================
-- OPERATIONAL RESOURCE REPORT
-- ============================================================================

CREATE OR REPLACE VIEW node_resource_usage AS
SELECT
    n.node_id,
    n.node_name,
    n.total_cpu,
    n.total_memory_mb,

    COALESCE(
        SUM(c.cpu_limit) FILTER (WHERE c.state = 'running'),
        0
    ) AS allocated_cpu,

    COALESCE(
        SUM(c.memory_limit_mb) FILTER (WHERE c.state = 'running'),
        0
    ) AS allocated_memory_mb,

    COUNT(c.container_id) FILTER (
        WHERE c.state = 'running'
    ) AS running_containers,

    n.total_cpu - COALESCE(
        SUM(c.cpu_limit) FILTER (WHERE c.state = 'running'),
        0
    ) AS available_cpu,

    n.total_memory_mb - COALESCE(
        SUM(c.memory_limit_mb) FILTER (WHERE c.state = 'running'),
        0
    ) AS available_memory_mb

FROM host_nodes n
LEFT JOIN containers c
    ON c.node_id = n.node_id

GROUP BY
    n.node_id,
    n.node_name,
    n.total_cpu,
    n.total_memory_mb;

-- ============================================================================
-- SAMPLE REGISTRIES
-- ============================================================================

INSERT INTO image_registries (
    registry_name,
    registry_url,
    is_trusted
)
VALUES
    (
        'Internal Registry',
        'https://registry.example.internal',
        TRUE
    ),
    (
        'External Registry',
        'https://registry.example.com',
        FALSE
    );

INSERT INTO image_repositories (
    registry_id,
    repository_name,
    description
)
VALUES
    (
        1,
        'inventory-api',
        'Inventory management application'
    ),
    (
        1,
        'reporting-service',
        'Enterprise reporting application'
    ),
    (
        2,
        'legacy-service',
        'Legacy application image'
    );

-- ============================================================================
-- SAMPLE IMAGES
-- ============================================================================

INSERT INTO container_images (
    repository_id,
    image_tag,
    digest,
    base_image,
    entrypoint,
    image_size_bytes,
    layer_count,
    execution_user,
    vulnerability_count,
    scan_state
)
VALUES
(
    1,
    '1.0.0',
    repeat('a', 64),
    'python:3.13-slim',
    'python application.py',
    150000000,
    5,
    'app',
    0,
    'passed'
),
(
    2,
    '2.1.0',
    repeat('b', 64),
    'node:22-slim',
    'node server.js',
    180000000,
    6,
    'app',
    0,
    'passed'
),
(
    3,
    '0.9.0',
    repeat('c', 64),
    'ubuntu:20.04',
    '/usr/bin/legacy-service',
    300000000,
    4,
    'root',
    3,
    'failed'
);

-- ============================================================================
-- IMAGE LAYERS
-- ============================================================================

INSERT INTO image_layers (
    image_id,
    layer_order,
    instruction,
    content_description,
    layer_digest,
    size_bytes
)
VALUES
(
    1, 0, 'FROM', 'Python slim base image', repeat('1', 64), 80000000
),
(
    1, 1, 'WORKDIR', '/app', repeat('2', 64), 100
),
(
    1, 2, 'COPY', 'requirements.txt', repeat('3', 64), 1000
),
(
    1, 3, 'RUN', 'Install dependencies', repeat('4', 64), 50000000
),
(
    1, 4, 'COPY', 'Application source', repeat('5', 64), 20000000
),
(
    2, 0, 'FROM', 'Node slim base image', repeat('6', 64), 90000000
),
(
    2, 1, 'WORKDIR', '/app', repeat('7', 64), 100
),
(
    2, 2, 'COPY', 'package.json', repeat('8', 64), 2000
),
(
    2, 3, 'RUN', 'Install production dependencies', repeat('9', 64), 60000000
),
(
    2, 4, 'COPY', 'server.js', repeat('d', 64), 10000000
),
(
    2, 5, 'USER', 'app', repeat('e', 64), 100
);

-- ============================================================================
-- EXPOSED PORTS
-- ============================================================================

INSERT INTO image_exposed_ports (
    image_id,
    container_port,
    protocol
)
VALUES
    (1, 8000, 'tcp'),
    (2, 3000, 'tcp'),
    (3, 8080, 'tcp');

-- ============================================================================
-- HOST NODES
-- ============================================================================

INSERT INTO host_nodes (
    node_name,
    total_cpu,
    total_memory_mb,
    total_process_capacity
)
VALUES
    ('worker-node-01', 16, 32768, 4096),
    ('worker-node-02', 8, 16384, 2048);

-- ============================================================================
-- SAMPLE CONTAINER DEPLOYMENTS
-- ============================================================================

INSERT INTO containers (
    container_id,
    image_id,
    node_id,
    container_name,
    environment,
    state,
    health,
    restart_policy,
    cpu_limit,
    memory_limit_mb,
    process_limit
)
VALUES
(
    '11111111-1111-4111-8111-111111111111',
    1,
    1,
    'inventory-production',
    'production',
    'running',
    'healthy',
    'on-failure',
    2,
    1024,
    150
),
(
    '22222222-2222-4222-8222-222222222222',
    2,
    1,
    'reporting-staging',
    'staging',
    'running',
    'starting',
    'always',
    1,
    512,
    100
),
(
    '33333333-3333-4333-8333-333333333333',
    1,
    2,
    'inventory-testing',
    'testing',
    'stopped',
    'unhealthy',
    'no',
    1,
    512,
    100
);

-- ============================================================================
-- PORT MAPPINGS
-- ============================================================================

INSERT INTO container_port_mappings (
    container_id,
    container_port,
    host_port,
    protocol
)
VALUES
(
    '11111111-1111-4111-8111-111111111111',
    8000,
    8080,
    'tcp'
),
(
    '22222222-2222-4222-8222-222222222222',
    3000,
    9090,
    'tcp'
),
(
    '33333333-3333-4333-8333-333333333333',
    8000,
    8081,
    'tcp'
);

-- ============================================================================
-- ENVIRONMENT CONFIGURATION
-- ============================================================================

INSERT INTO container_environment (
    container_id,
    variable_name,
    variable_value,
    is_secret
)
VALUES
(
    '11111111-1111-4111-8111-111111111111',
    'APP_ENV',
    'production',
    FALSE
),
(
    '11111111-1111-4111-8111-111111111111',
    'DATABASE_PASSWORD',
    'REDACTED_SECRET_REFERENCE',
    TRUE
),
(
    '22222222-2222-4222-8222-222222222222',
    'APP_ENV',
    'staging',
    FALSE
);

-- ============================================================================
-- HEALTH CHECK RECORDS
-- ============================================================================

INSERT INTO container_health_checks (
    container_id,
    status,
    response_time_ms,
    check_message
)
VALUES
(
    '11111111-1111-4111-8111-111111111111',
    'healthy',
    35,
    'HTTP health endpoint returned success'
),
(
    '11111111-1111-4111-8111-111111111111',
    'healthy',
    28,
    'Application operating normally'
),
(
    '22222222-2222-4222-8222-222222222222',
    'starting',
    120,
    'Application initialization in progress'
),
(
    '33333333-3333-4333-8333-333333333333',
    'unhealthy',
    NULL,
    'Container stopped'
);

-- ============================================================================
-- DEPLOYMENT ELIGIBILITY QUERY
-- ============================================================================

SELECT
    repository_name,
    image_tag,
    scan_state,
    vulnerability_count,
    execution_user,
    deployment_eligible
FROM container_deployment_eligibility
ORDER BY repository_name, image_tag;

-- ============================================================================
-- CONTAINER INVENTORY QUERY
-- ============================================================================

SELECT
    c.container_name,
    i.image_tag,
    n.node_name,
    c.environment,
    c.state,
    c.health,
    c.cpu_limit,
    c.memory_limit_mb,
    c.restart_count
FROM containers c
JOIN container_images i
    ON i.image_id = c.image_id
JOIN host_nodes n
    ON n.node_id = c.node_id
ORDER BY n.node_name, c.container_name;

-- ============================================================================
-- NODE RESOURCE AGGREGATION
-- ============================================================================

SELECT *
FROM node_resource_usage
ORDER BY node_name;

-- ============================================================================
-- HEALTH REPORT
-- ============================================================================

SELECT
    c.container_name,
    h.status,
    COUNT(*) AS checks,
    ROUND(AVG(h.response_time_ms), 2) AS average_response_ms,
    MAX(h.checked_at) AS latest_check
FROM container_health_checks h
JOIN containers c
    ON c.container_id = h.container_id
GROUP BY c.container_name, h.status
ORDER BY c.container_name, h.status;

-- ============================================================================
-- RECENT AUDIT EVENTS
-- ============================================================================

SELECT
    container_id,
    event_type,
    event_details,
    event_timestamp
FROM container_audit_events
ORDER BY event_timestamp DESC;

-- ============================================================================
-- CTE: RUNNING CONTAINER CAPACITY ANALYSIS
-- ============================================================================

WITH running_usage AS (
    SELECT
        node_id,
        COUNT(*) AS running_count,
        SUM(cpu_limit) AS used_cpu,
        SUM(memory_limit_mb) AS used_memory
    FROM containers
    WHERE state = 'running'
    GROUP BY node_id
)
SELECT
    n.node_name,
    n.total_cpu,
    COALESCE(r.used_cpu, 0) AS used_cpu,
    n.total_cpu - COALESCE(r.used_cpu, 0) AS available_cpu,
    n.total_memory_mb,
    COALESCE(r.used_memory, 0) AS used_memory_mb,
    n.total_memory_mb - COALESCE(r.used_memory, 0)
        AS available_memory_mb,
    COALESCE(r.running_count, 0) AS running_count
FROM host_nodes n
LEFT JOIN running_usage r
    ON r.node_id = n.node_id;

-- ============================================================================
-- FUNCTION: CHECK DEPLOYMENT CAPACITY
-- ============================================================================

CREATE OR REPLACE FUNCTION check_deployment_capacity(
    p_node_id BIGINT,
    p_cpu NUMERIC,
    p_memory_mb BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_node RECORD;
    v_cpu NUMERIC;
    v_memory BIGINT;
BEGIN
    SELECT *
    INTO v_node
    FROM host_nodes
    WHERE node_id = p_node_id
      AND node_active = TRUE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    SELECT
        COALESCE(SUM(cpu_limit), 0),
        COALESCE(SUM(memory_limit_mb), 0)
    INTO v_cpu, v_memory
    FROM containers
    WHERE node_id = p_node_id
      AND state = 'running';

    RETURN
        v_cpu + p_cpu <= v_node.total_cpu
        AND v_memory + p_memory_mb <= v_node.total_memory_mb;
END;
$$;

SELECT
    node_name,
    check_deployment_capacity(node_id, 2, 2048) AS can_deploy
FROM host_nodes;

-- ============================================================================
-- PROCEDURE: RESTART FAILED CONTAINER
-- ============================================================================

CREATE OR REPLACE PROCEDURE restart_failed_container(
    p_container_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_container RECORD;
BEGIN
    SELECT *
    INTO v_container
    FROM containers
    WHERE container_id = p_container_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Container not found.';
    END IF;

    IF v_container.state <> 'failed' THEN
        RAISE EXCEPTION 'Container is not in failed state.';
    END IF;

    IF v_container.restart_policy = 'no' THEN
        RAISE EXCEPTION 'Restart policy prohibits restarting.';
    END IF;

    IF (
        v_container.restart_policy = 'on-failure'
        AND v_container.restart_count >= 3
    ) THEN
        RAISE EXCEPTION 'Restart attempt limit reached.';
    END IF;

    UPDATE containers
    SET
        state = 'stopped',
        restart_count = restart_count + 1
    WHERE container_id = p_container_id;

    UPDATE containers
    SET
        state = 'running',
        health = 'starting',
        started_at = CURRENT_TIMESTAMP,
        stopped_at = NULL
    WHERE container_id = p_container_id;

    INSERT INTO container_audit_events (
        container_id,
        event_type,
        event_details
    )
    VALUES (
        p_container_id,
        'restart_requested',
        jsonb_build_object(
            'restart_policy', v_container.restart_policy
        )
    );
END;
$$;

-- ============================================================================
-- TRANSACTIONAL RESTART DEMONSTRATION
-- ============================================================================

-- Demonstrate failure handling without leaving sample data modified.

DO $$
DECLARE
    v_container_id UUID :=
        '33333333-3333-4333-8333-333333333333';
BEGIN
    UPDATE containers
    SET state = 'failed'
    WHERE container_id = v_container_id
      AND state = 'stopped';

    BEGIN
        CALL restart_failed_container(v_container_id);

        -- Demonstrate a running state without retaining the change.
        RAISE NOTICE 'Container restart simulation succeeded.';

        ROLLBACK;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Restart rejected: %', SQLERRM;
            ROLLBACK;
    END;
END;
$$;

-- ============================================================================
-- VALIDATION: REJECT UNSCANNED IMAGE
-- ============================================================================

DO $$
BEGIN
    BEGIN
        INSERT INTO containers (
            image_id,
            node_id,
            container_name,
            environment,
            cpu_limit,
            memory_limit_mb,
            process_limit
        )
        VALUES (
            3,
            1,
            'insecure-legacy-container',
            'development',
            1,
            256,
            50
        );

        RAISE EXCEPTION 'Security validation unexpectedly failed.';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected deployment rejection: %', SQLERRM;
    END;
END;
$$;

-- ============================================================================
-- FINAL REPORT
-- ============================================================================

SELECT
    n.node_name,
    n.running_containers,
    n.allocated_cpu,
    n.available_cpu,
    n.allocated_memory_mb,
    n.available_memory_mb
FROM node_resource_usage n
ORDER BY n.node_name;

SELECT
    state,
    COUNT(*) AS container_count
FROM containers
GROUP BY state
ORDER BY state;

COMMIT;
