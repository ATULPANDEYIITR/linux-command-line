/*
===============================================================================
DOCKER FUNDAMENTALS
PostgreSQL Container and Image Management Database
===============================================================================

PostgreSQL 15+

Domain:
- Docker architecture
- Registries
- Repositories
- Image manifests
- Image layers
- Container deployments
- Container lifecycle
- Port mappings
- Volumes
- Environment configuration
- Resource policies
- Deployment eligibility
- Audit history
- Operational reporting

The database represents a Docker management and learning environment.
It does not replace the Docker daemon or perform actual container execution.

Execution:
    psql -U postgres -d postgres -f docker_fundamentals.sql
===============================================================================
*/

BEGIN;

-- ============================================================================
-- 1. SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS docker_lab;

SET search_path TO docker_lab, public;

-- ============================================================================
-- 2. ENUMERATIONS
-- ============================================================================

CREATE TYPE image_origin AS ENUM (
    'built',
    'registry',
    'local'
);

CREATE TYPE container_state AS ENUM (
    'created',
    'running',
    'paused',
    'restarting',
    'exited',
    'dead'
);

CREATE TYPE registry_visibility AS ENUM (
    'public',
    'private',
    'internal'
);

CREATE TYPE deployment_result AS ENUM (
    'pending',
    'eligible',
    'rejected',
    'deployed',
    'failed',
    'removed'
);

CREATE TYPE audit_action AS ENUM (
    'image_built',
    'image_pulled',
    'image_pushed',
    'container_created',
    'container_started',
    'container_paused',
    'container_unpaused',
    'container_stopped',
    'container_restarted',
    'container_removed',
    'deployment_rejected'
);

-- ============================================================================
-- 3. USERS
-- ============================================================================

CREATE TABLE docker_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    username VARCHAR(80) NOT NULL UNIQUE,

    email VARCHAR(255) NOT NULL UNIQUE,

    role_name VARCHAR(40) NOT NULL
        CHECK (
            role_name IN (
                'administrator',
                'developer',
                'operator',
                'auditor'
            )
        ),

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 4. REGISTRIES
-- ============================================================================

CREATE TABLE registries (
    registry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    hostname VARCHAR(255) NOT NULL UNIQUE,

    provider VARCHAR(80) NOT NULL,

    visibility registry_visibility NOT NULL DEFAULT 'private',

    tls_required BOOLEAN NOT NULL DEFAULT TRUE,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (hostname !~ '[[:space:]]')
);

CREATE TABLE registry_memberships (
    registry_id BIGINT NOT NULL
        REFERENCES registries(registry_id)
        ON DELETE CASCADE,

    user_id BIGINT NOT NULL
        REFERENCES docker_users(user_id)
        ON DELETE CASCADE,

    can_pull BOOLEAN NOT NULL DEFAULT TRUE,

    can_push BOOLEAN NOT NULL DEFAULT FALSE,

    authenticated_at TIMESTAMPTZ,

    PRIMARY KEY (registry_id, user_id)
);

-- ============================================================================
-- 5. IMAGE REPOSITORIES
-- ============================================================================

CREATE TABLE image_repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_id BIGINT
        REFERENCES registries(registry_id)
        ON DELETE SET NULL,

    repository_name VARCHAR(255) NOT NULL,

    owner_id BIGINT NOT NULL
        REFERENCES docker_users(user_id),

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (registry_id, repository_name),

    CHECK (
        repository_name ~
        '^[a-z0-9]+([._-][a-z0-9]+)*(\/[a-z0-9]+([._-][a-z0-9]+)*)*$'
    )
);

-- ============================================================================
-- 6. IMAGE MANIFESTS
-- ============================================================================

CREATE TABLE images (
    image_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES image_repositories(repository_id),

    tag VARCHAR(128) NOT NULL,

    digest CHAR(64) NOT NULL UNIQUE,

    origin image_origin NOT NULL,

    total_size_mb NUMERIC(12,2) NOT NULL
        CHECK (total_size_mb >= 0),

    architecture VARCHAR(40) NOT NULL DEFAULT 'amd64',

    operating_system VARCHAR(40) NOT NULL DEFAULT 'linux',

    created_by BIGINT NOT NULL
        REFERENCES docker_users(user_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (repository_id, tag),

    CHECK (tag ~ '^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$'),

    CHECK (digest ~ '^[a-f0-9]{64}$')
);

-- ============================================================================
-- 7. IMAGE LAYERS
-- ============================================================================

CREATE TABLE image_layers (
    layer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES images(image_id)
        ON DELETE CASCADE,

    layer_order INTEGER NOT NULL
        CHECK (layer_order >= 0),

    digest CHAR(64) NOT NULL,

    instruction TEXT NOT NULL,

    size_mb NUMERIC(12,2) NOT NULL
        CHECK (size_mb >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (image_id, layer_order),

    UNIQUE (image_id, digest),

    CHECK (digest ~ '^[a-f0-9]{64}$')
);

-- ============================================================================
-- 8. IMAGE DISTRIBUTION EVENTS
-- ============================================================================

CREATE TABLE image_distribution_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_id BIGINT NOT NULL
        REFERENCES images(image_id),

    registry_id BIGINT NOT NULL
        REFERENCES registries(registry_id),

    user_id BIGINT NOT NULL
        REFERENCES docker_users(user_id),

    operation VARCHAR(10) NOT NULL
        CHECK (operation IN ('push', 'pull')),

    succeeded BOOLEAN NOT NULL,

    error_message TEXT,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        succeeded = TRUE
        OR error_message IS NOT NULL
    )
);

-- ============================================================================
-- 9. RESOURCE POLICIES
-- ============================================================================

CREATE TABLE resource_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(100) NOT NULL UNIQUE,

    maximum_cpu NUMERIC(8,2) NOT NULL
        CHECK (maximum_cpu > 0),

    maximum_memory_mb INTEGER NOT NULL
        CHECK (maximum_memory_mb >= 6),

    maximum_ports INTEGER NOT NULL
        CHECK (maximum_ports >= 1),

    privileged_containers_allowed BOOLEAN NOT NULL DEFAULT FALSE,

    host_network_allowed BOOLEAN NOT NULL DEFAULT FALSE,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 10. CONTAINER DEPLOYMENTS
-- ============================================================================

CREATE TABLE containers (
    container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    container_name VARCHAR(128) NOT NULL UNIQUE,

    image_id BIGINT NOT NULL
        REFERENCES images(image_id),

    owner_id BIGINT NOT NULL
        REFERENCES docker_users(user_id),

    policy_id BIGINT NOT NULL
        REFERENCES resource_policies(policy_id),

    state container_state NOT NULL DEFAULT 'created',

    deployment_status deployment_result NOT NULL DEFAULT 'pending',

    cpu_limit NUMERIC(8,2) NOT NULL
        CHECK (cpu_limit > 0),

    memory_limit_mb INTEGER NOT NULL
        CHECK (memory_limit_mb >= 6),

    privileged BOOLEAN NOT NULL DEFAULT FALSE,

    host_network BOOLEAN NOT NULL DEFAULT FALSE,

    restart_count INTEGER NOT NULL DEFAULT 0
        CHECK (restart_count >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    started_at TIMESTAMPTZ,

    stopped_at TIMESTAMPTZ,

    removed_at TIMESTAMPTZ
);

-- ============================================================================
-- 11. PORT MAPPINGS
-- ============================================================================

CREATE TABLE container_ports (
    port_mapping_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES containers(container_id)
        ON DELETE CASCADE,

    host_port INTEGER NOT NULL
        CHECK (host_port BETWEEN 1 AND 65535),

    container_port INTEGER NOT NULL
        CHECK (container_port BETWEEN 1 AND 65535),

    protocol VARCHAR(10) NOT NULL DEFAULT 'tcp'
        CHECK (protocol IN ('tcp', 'udp')),

    UNIQUE (container_id, host_port, protocol)
);

-- A host port cannot be allocated to two active containers.
CREATE UNIQUE INDEX uq_active_host_port
ON container_ports(host_port, protocol)
WHERE container_id IN (
    SELECT container_id
    FROM containers
    WHERE deployment_status = 'deployed'
);

-- ============================================================================
-- 12. VOLUME MAPPINGS
-- ============================================================================

CREATE TABLE container_volumes (
    volume_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES containers(container_id)
        ON DELETE CASCADE,

    host_path TEXT NOT NULL,

    container_path TEXT NOT NULL,

    read_only BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (container_id, container_path),

    CHECK (left(container_path, 1) = '/'),

    CHECK (left(host_path, 1) = '/')
);

-- ============================================================================
-- 13. ENVIRONMENT VARIABLES
-- ============================================================================

CREATE TABLE container_environment (
    environment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES containers(container_id)
        ON DELETE CASCADE,

    variable_name VARCHAR(128) NOT NULL,

    variable_value TEXT NOT NULL,

    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (container_id, variable_name),

    CHECK (
        variable_name ~ '^[A-Za-z_][A-Za-z0-9_]*$'
    )
);

-- Sensitive values should be encrypted or supplied through a
-- dedicated secret-management system in production.

-- ============================================================================
-- 14. CONTAINER AUDIT
-- ============================================================================

CREATE TABLE container_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT
        REFERENCES containers(container_id)
        ON DELETE SET NULL,

    user_id BIGINT
        REFERENCES docker_users(user_id)
        ON DELETE SET NULL,

    action audit_action NOT NULL,

    previous_state container_state,

    new_state container_state,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 15. DEPLOYMENT VALIDATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_container_deployment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    policy_record resource_policies%ROWTYPE;
    actual_ports INTEGER;
BEGIN
    SELECT *
    INTO policy_record
    FROM resource_policies
    WHERE policy_id = NEW.policy_id
      AND active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource policy is missing or inactive';
    END IF;

    IF NEW.cpu_limit > policy_record.maximum_cpu THEN
        RAISE EXCEPTION
            'CPU limit % exceeds policy maximum %',
            NEW.cpu_limit,
            policy_record.maximum_cpu;
    END IF;

    IF NEW.memory_limit_mb > policy_record.maximum_memory_mb THEN
        RAISE EXCEPTION
            'Memory limit % exceeds policy maximum %',
            NEW.memory_limit_mb,
            policy_record.maximum_memory_mb;
    END IF;

    IF NEW.privileged
       AND NOT policy_record.privileged_containers_allowed THEN
        RAISE EXCEPTION 'Privileged containers are prohibited';
    END IF;

    IF NEW.host_network
       AND NOT policy_record.host_network_allowed THEN
        RAISE EXCEPTION 'Host networking is prohibited';
    END IF;

    SELECT COUNT(*)
    INTO actual_ports
    FROM container_ports
    WHERE container_id = NEW.container_id;

    IF actual_ports > policy_record.maximum_ports THEN
        RAISE EXCEPTION 'Maximum port mapping count exceeded';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_deployment
BEFORE INSERT OR UPDATE OF
    policy_id,
    cpu_limit,
    memory_limit_mb,
    privileged,
    host_network
ON containers
FOR EACH ROW
EXECUTE FUNCTION validate_container_deployment();

-- ============================================================================
-- 16. LAYER TOTAL VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_image_layer_total()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_image BIGINT;
    expected_size NUMERIC(12,2);
    actual_size NUMERIC(12,2);
BEGIN
    target_image := COALESCE(NEW.image_id, OLD.image_id);

    SELECT total_size_mb
    INTO expected_size
    FROM images
    WHERE image_id = target_image;

    SELECT COALESCE(SUM(size_mb), 0)
    INTO actual_size
    FROM image_layers
    WHERE image_id = target_image;

    IF expected_size IS NOT NULL
       AND actual_size > expected_size THEN
        RAISE EXCEPTION
            'Layer total % MB exceeds manifest size % MB',
            actual_size,
            expected_size;
    END IF;

    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_validate_image_layer_total
AFTER INSERT OR UPDATE OR DELETE
ON image_layers
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION validate_image_layer_total();

-- ============================================================================
-- 17. STATE TRANSITION VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_container_state_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = NEW.state THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.state = 'created' AND NEW.state = 'running')
        OR
        (OLD.state = 'running' AND NEW.state IN ('paused', 'exited'))
        OR
        (OLD.state = 'paused' AND NEW.state IN ('running', 'exited'))
        OR
        (OLD.state = 'exited' AND NEW.state IN ('running', 'dead'))
        OR
        (OLD.state = 'created' AND NEW.state = 'dead')
        OR
        (OLD.state = 'restarting' AND NEW.state = 'running')
        OR
        (OLD.state = 'running' AND NEW.state = 'restarting')
        OR
        (OLD.state = 'paused' AND NEW.state = 'restarting')
    ) THEN
        RAISE EXCEPTION
            'Invalid container transition: % -> %',
            OLD.state,
            NEW.state;
    END IF;

    IF NEW.state = 'running' AND OLD.state <> 'running' THEN
        NEW.started_at := CURRENT_TIMESTAMP;
        NEW.stopped_at := NULL;
    END IF;

    IF NEW.state = 'exited' THEN
        NEW.stopped_at := CURRENT_TIMESTAMP;
    END IF;

    IF NEW.state = 'dead' THEN
        NEW.removed_at := CURRENT_TIMESTAMP;
        NEW.deployment_status := 'removed';
    END IF;

    IF NEW.state = 'restarting' THEN
        NEW.restart_count := OLD.restart_count + 1;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_state
BEFORE UPDATE OF state
ON containers
FOR EACH ROW
EXECUTE FUNCTION validate_container_state_transition();

-- ============================================================================
-- 18. AUTOMATIC AUDIT TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION record_container_state_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    action_value audit_action;
BEGIN
    IF OLD.state = NEW.state THEN
        RETURN NEW;
    END IF;

    action_value := CASE NEW.state
        WHEN 'running' THEN
            CASE OLD.state
                WHEN 'restarting' THEN 'container_restarted'::audit_action
                ELSE 'container_started'::audit_action
            END
        WHEN 'paused' THEN 'container_paused'::audit_action
        WHEN 'exited' THEN 'container_stopped'::audit_action
        WHEN 'dead' THEN 'container_removed'::audit_action
        ELSE 'container_created'::audit_action
    END;

    INSERT INTO container_audit (
        container_id,
        user_id,
        action,
        previous_state,
        new_state,
        details
    )
    VALUES (
        NEW.container_id,
        NEW.owner_id,
        action_value,
        OLD.state,
        NEW.state,
        jsonb_build_object(
            'container_name', NEW.container_name,
            'image_id', NEW.image_id
        )
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_container_state_change
AFTER UPDATE OF state
ON containers
FOR EACH ROW
EXECUTE FUNCTION record_container_state_change();

-- ============================================================================
-- 19. IMAGE INVENTORY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_image_inventory AS
SELECT
    i.image_id,
    r.repository_name,
    i.tag,
    i.digest,
    i.origin,
    i.architecture,
    i.operating_system,
    i.total_size_mb,
    COUNT(l.layer_id) AS layer_count,
    COALESCE(SUM(l.size_mb), 0) AS layer_size_mb,
    i.created_at
FROM images i
JOIN image_repositories r
    ON r.repository_id = i.repository_id
LEFT JOIN image_layers l
    ON l.image_id = i.image_id
GROUP BY
    i.image_id,
    r.repository_name,
    i.tag,
    i.digest,
    i.origin,
    i.architecture,
    i.operating_system,
    i.total_size_mb,
    i.created_at;

-- ============================================================================
-- 20. CONTAINER INVENTORY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_container_inventory AS
SELECT
    c.container_id,
    c.container_name,
    r.repository_name,
    i.tag AS image_tag,
    c.state,
    c.deployment_status,
    c.cpu_limit,
    c.memory_limit_mb,
    c.restart_count,
    u.username AS owner,
    p.policy_name,
    c.created_at,
    c.started_at,
    c.stopped_at
FROM containers c
JOIN images i
    ON i.image_id = c.image_id
JOIN image_repositories r
    ON r.repository_id = i.repository_id
JOIN docker_users u
    ON u.user_id = c.owner_id
JOIN resource_policies p
    ON p.policy_id = c.policy_id;

-- ============================================================================
-- 21. DEPLOYMENT ELIGIBILITY FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION evaluate_container_eligibility(
    p_container_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    c containers%ROWTYPE;
    p resource_policies%ROWTYPE;
    port_count INTEGER;
BEGIN
    SELECT *
    INTO c
    FROM containers
    WHERE container_id = p_container_id;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Container not found'::TEXT;
        RETURN;
    END IF;

    SELECT *
    INTO p
    FROM resource_policies
    WHERE policy_id = c.policy_id
      AND active = TRUE;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Policy inactive or missing'::TEXT;
        RETURN;
    END IF;

    SELECT COUNT(*)::INTEGER
    INTO port_count
    FROM container_ports
    WHERE container_id = p_container_id;

    IF c.cpu_limit > p.maximum_cpu THEN
        RETURN QUERY
        SELECT FALSE, 'CPU policy violation'::TEXT;
        RETURN;
    END IF;

    IF c.memory_limit_mb > p.maximum_memory_mb THEN
        RETURN QUERY
        SELECT FALSE, 'Memory policy violation'::TEXT;
        RETURN;
    END IF;

    IF port_count > p.maximum_ports THEN
        RETURN QUERY
        SELECT FALSE, 'Port policy violation'::TEXT;
        RETURN;
    END IF;

    IF c.privileged AND NOT p.privileged_containers_allowed THEN
        RETURN QUERY
        SELECT FALSE, 'Privileged mode prohibited'::TEXT;
        RETURN;
    END IF;

    IF c.host_network AND NOT p.host_network_allowed THEN
        RETURN QUERY
        SELECT FALSE, 'Host networking prohibited'::TEXT;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT TRUE, 'Deployment policy satisfied'::TEXT;
END;
$$;

-- ============================================================================
-- 22. DEPLOYMENT PROCESSING PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE process_container_deployment(
    p_container_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    evaluation RECORD;
BEGIN
    SELECT *
    INTO evaluation
    FROM evaluate_container_eligibility(p_container_id);

    IF evaluation.eligible THEN

        UPDATE containers
        SET deployment_status = 'eligible'
        WHERE container_id = p_container_id
          AND deployment_status = 'pending';

    ELSE

        UPDATE containers
        SET deployment_status = 'rejected'
        WHERE container_id = p_container_id
          AND deployment_status = 'pending';

        INSERT INTO container_audit (
            container_id,
            action,
            details
        )
        VALUES (
            p_container_id,
            'deployment_rejected',
            jsonb_build_object(
                'reason', evaluation.reason
            )
        );

    END IF;
END;
$$;

-- ============================================================================
-- 23. PERFORMANCE INDEXES
-- ============================================================================

CREATE INDEX idx_images_repository
ON images(repository_id);

CREATE INDEX idx_layers_image_order
ON image_layers(image_id, layer_order);

CREATE INDEX idx_containers_state
ON containers(state);

CREATE INDEX idx_containers_owner
ON containers(owner_id);

CREATE INDEX idx_containers_image
ON containers(image_id);

CREATE INDEX idx_containers_deployment
ON containers(deployment_status);

CREATE INDEX idx_audit_container_time
ON container_audit(container_id, occurred_at DESC);

CREATE INDEX idx_distribution_image_time
ON image_distribution_events(image_id, occurred_at DESC);

CREATE INDEX idx_container_environment_name
ON container_environment(variable_name);

-- ============================================================================
-- 24. SAMPLE DATA
-- ============================================================================

INSERT INTO docker_users (
    username,
    email,
    role_name
)
VALUES
    ('admin', 'admin@example.com', 'administrator'),
    ('developer1', 'developer1@example.com', 'developer'),
    ('operator1', 'operator1@example.com', 'operator'),
    ('auditor1', 'auditor1@example.com', 'auditor');

INSERT INTO registries (
    hostname,
    provider,
    visibility,
    tls_required
)
VALUES
    ('registry.example.com', 'Private Registry', 'private', TRUE),
    ('docker.io', 'Docker Hub', 'public', TRUE);

INSERT INTO registry_memberships (
    registry_id,
    user_id,
    can_pull,
    can_push,
    authenticated_at
)
SELECT
    r.registry_id,
    u.user_id,
    TRUE,
    u.role_name IN ('administrator', 'developer'),
    CURRENT_TIMESTAMP
FROM registries r
CROSS JOIN docker_users u
WHERE r.hostname = 'registry.example.com'
  AND u.username IN ('admin', 'developer1', 'operator1');

INSERT INTO image_repositories (
    registry_id,
    repository_name,
    owner_id,
    description
)
SELECT
    r.registry_id,
    'training/web-api',
    u.user_id,
    'Docker fundamentals web API image'
FROM registries r
CROSS JOIN docker_users u
WHERE r.hostname = 'registry.example.com'
  AND u.username = 'developer1';

INSERT INTO image_repositories (
    registry_id,
    repository_name,
    owner_id,
    description
)
SELECT
    r.registry_id,
    'training/worker',
    u.user_id,
    'Background worker image'
FROM registries r
CROSS JOIN docker_users u
WHERE r.hostname = 'registry.example.com'
  AND u.username = 'developer1';

INSERT INTO images (
    repository_id,
    tag,
    digest,
    origin,
    total_size_mb,
    architecture,
    operating_system,
    created_by
)
SELECT
    repository_id,
    '1.0.0',
    repeat('a', 64),
    'built',
    67.00,
    'amd64',
    'linux',
    (SELECT user_id FROM docker_users WHERE username = 'developer1')
FROM image_repositories
WHERE repository_name = 'training/web-api';

INSERT INTO images (
    repository_id,
    tag,
    digest,
    origin,
    total_size_mb,
    architecture,
    operating_system,
    created_by
)
SELECT
    repository_id,
    '2.0.0',
    repeat('b', 64),
    'registry',
    88.00,
    'amd64',
    'linux',
    (SELECT user_id FROM docker_users WHERE username = 'developer1')
FROM image_repositories
WHERE repository_name = 'training/web-api';

INSERT INTO images (
    repository_id,
    tag,
    digest,
    origin,
    total_size_mb,
    architecture,
    operating_system,
    created_by
)
SELECT
    repository_id,
    '1.0.0',
    repeat('c', 64),
    'built',
    50.00,
    'amd64',
    'linux',
    (SELECT user_id FROM docker_users WHERE username = 'developer1')
FROM image_repositories
WHERE repository_name = 'training/worker';

INSERT INTO image_layers (
    image_id,
    layer_order,
    digest,
    instruction,
    size_mb
)
SELECT
    image_id,
    layer_order,
    digest,
    instruction,
    size_mb
FROM (
    VALUES
        (repeat('a', 64), 0, repeat('1', 64), 'FROM python:3.13-slim', 45.00),
        (repeat('a', 64), 1, repeat('2', 64), 'Install application dependencies', 18.00),
        (repeat('a', 64), 2, repeat('3', 64), 'COPY application files', 4.00),
        (repeat('b', 64), 0, repeat('4', 64), 'FROM python:3.13-slim', 45.00),
        (repeat('b', 64), 1, repeat('5', 64), 'Install upgraded dependencies', 25.00),
        (repeat('b', 64), 2, repeat('6', 64), 'COPY application files', 18.00),
        (repeat('c', 64), 0, repeat('7', 64), 'FROM alpine:3.21', 20.00),
        (repeat('c', 64), 1, repeat('8', 64), 'Install worker runtime', 20.00),
        (repeat('c', 64), 2, repeat('9', 64), 'COPY worker application', 10.00)
) AS sample (
    image_digest,
    layer_order,
    digest,
    instruction,
    size_mb
)
JOIN images i
    ON i.digest = sample.image_digest;

INSERT INTO resource_policies (
    policy_name,
    maximum_cpu,
    maximum_memory_mb,
    maximum_ports,
    privileged_containers_allowed,
    host_network_allowed
)
VALUES
    ('development', 2.00, 2048, 10, FALSE, FALSE),
    ('production', 4.00, 8192, 20, FALSE, FALSE),
    ('restricted', 1.00, 512, 2, FALSE, FALSE);

-- ============================================================================
-- 25. CONTAINER RECORDS
-- ============================================================================

INSERT INTO containers (
    container_name,
    image_id,
    owner_id,
    policy_id,
    state,
    deployment_status,
    cpu_limit,
    memory_limit_mb
)
SELECT
    'web-api-dev',
    i.image_id,
    u.user_id,
    p.policy_id,
    'created',
    'pending',
    1.00,
    512
FROM images i
JOIN image_repositories r
    ON r.repository_id = i.repository_id
JOIN docker_users u
    ON u.username = 'developer1'
JOIN resource_policies p
    ON p.policy_name = 'development'
WHERE r.repository_name = 'training/web-api'
  AND i.tag = '1.0.0';

INSERT INTO containers (
    container_name,
    image_id,
    owner_id,
    policy_id,
    state,
    deployment_status,
    cpu_limit,
    memory_limit_mb
)
SELECT
    'web-api-prod',
    i.image_id,
    u.user_id,
    p.policy_id,
    'created',
    'pending',
    2.00,
    2048
FROM images i
JOIN image_repositories r
    ON r.repository_id = i.repository_id
JOIN docker_users u
    ON u.username = 'operator1'
JOIN resource_policies p
    ON p.policy_name = 'production'
WHERE r.repository_name = 'training/web-api'
  AND i.tag = '2.0.0';

INSERT INTO containers (
    container_name,
    image_id,
    owner_id,
    policy_id,
    state,
    deployment_status,
    cpu_limit,
    memory_limit_mb
)
SELECT
    'worker-restricted',
    i.image_id,
    u.user_id,
    p.policy_id,
    'created',
    'pending',
    0.50,
    256
FROM images i
JOIN image_repositories r
    ON r.repository_id = i.repository_id
JOIN docker_users u
    ON u.username = 'developer1'
JOIN resource_policies p
    ON p.policy_name = 'restricted'
WHERE r.repository_name = 'training/worker'
  AND i.tag = '1.0.0';

-- ============================================================================
-- 26. PORT MAPPINGS
-- ============================================================================

INSERT INTO container_ports (
    container_id,
    host_port,
    container_port,
    protocol
)
SELECT
    c.container_id,
    8080,
    8000,
    'tcp'
FROM containers c
WHERE c.container_name = 'web-api-dev';

INSERT INTO container_ports (
    container_id,
    host_port,
    container_port,
    protocol
)
SELECT
    c.container_id,
    8443,
    443,
    'tcp'
FROM containers c
WHERE c.container_name = 'web-api-prod';

INSERT INTO container_ports (
    container_id,
    host_port,
    container_port,
    protocol
)
SELECT
    c.container_id,
    9090,
    9090,
    'tcp'
FROM containers c
WHERE c.container_name = 'worker-restricted';

-- ============================================================================
-- 27. VOLUMES
-- ============================================================================

INSERT INTO container_volumes (
    container_id,
    host_path,
    container_path,
    read_only
)
SELECT
    c.container_id,
    '/srv/web-api/data',
    '/app/data',
    FALSE
FROM containers c
WHERE c.container_name = 'web-api-dev';

INSERT INTO container_volumes (
    container_id,
    host_path,
    container_path,
    read_only
)
SELECT
    c.container_id,
    '/srv/web-api/config',
    '/app/config',
    TRUE
FROM containers c
WHERE c.container_name = 'web-api-prod';

-- ============================================================================
-- 28. ENVIRONMENT VARIABLES
-- ============================================================================

INSERT INTO container_environment (
    container_id,
    variable_name,
    variable_value,
    is_sensitive
)
SELECT
    c.container_id,
    'APP_ENV',
    'development',
    FALSE
FROM containers c
WHERE c.container_name = 'web-api-dev';

INSERT INTO container_environment (
    container_id,
    variable_name,
    variable_value,
    is_sensitive
)
SELECT
    c.container_id,
    'DATABASE_URL',
    '[encrypted-secret-reference]',
    TRUE
FROM containers c
WHERE c.container_name = 'web-api-prod';

INSERT INTO container_environment (
    container_id,
    variable_name,
    variable_value,
    is_sensitive
)
SELECT
    c.container_id,
    'LOG_LEVEL',
    'info',
    FALSE
FROM containers c
WHERE c.container_name = 'worker-restricted';

-- ============================================================================
-- 29. IMAGE DISTRIBUTION EXAMPLES
-- ============================================================================

INSERT INTO image_distribution_events (
    image_id,
    registry_id,
    user_id,
    operation,
    succeeded,
    error_message
)
SELECT
    i.image_id,
    r.registry_id,
    u.user_id,
    'push',
    TRUE,
    NULL
FROM images i
JOIN image_repositories ir
    ON ir.repository_id = i.repository_id
JOIN registries r
    ON r.registry_id = ir.registry_id
JOIN docker_users u
    ON u.username = 'developer1'
WHERE i.tag = '1.0.0'
  AND ir.repository_name = 'training/web-api';

INSERT INTO image_distribution_events (
    image_id,
    registry_id,
    user_id,
    operation,
    succeeded,
    error_message
)
SELECT
    i.image_id,
    r.registry_id,
    u.user_id,
    'push',
    FALSE,
    'Registry authentication failed'
FROM images i
JOIN image_repositories ir
    ON ir.repository_id = i.repository_id
JOIN registries r
    ON r.registry_id = ir.registry_id
JOIN docker_users u
    ON u.username = 'developer1'
WHERE i.tag = '2.0.0'
  AND ir.repository_name = 'training/web-api';

-- ============================================================================
-- 30. PROCESS DEPLOYMENT ELIGIBILITY
-- ============================================================================

DO $$
DECLARE
    target RECORD;
BEGIN
    FOR target IN
        SELECT container_id
        FROM containers
        ORDER BY container_id
    LOOP
        CALL process_container_deployment(target.container_id);
    END LOOP;
END;
$$;

-- ============================================================================
-- 31. INITIAL CONTAINER LIFECYCLE
-- ============================================================================

UPDATE containers
SET state = 'running',
    deployment_status = 'deployed'
WHERE container_name = 'web-api-dev'
  AND deployment_status = 'eligible';

UPDATE containers
SET state = 'running',
    deployment_status = 'deployed'
WHERE container_name = 'web-api-prod'
  AND deployment_status = 'eligible';

UPDATE containers
SET state = 'running',
    deployment_status = 'deployed'
WHERE container_name = 'worker-restricted'
  AND deployment_status = 'eligible';

-- ============================================================================
-- 32. ADDITIONAL AUDIT EXAMPLES
-- ============================================================================

INSERT INTO container_audit (
    container_id,
    user_id,
    action,
    details
)
SELECT
    c.container_id,
    u.user_id,
    'image_built',
    jsonb_build_object(
        'image_tag', i.tag,
        'image_origin', i.origin
    )
FROM containers c
JOIN images i
    ON i.image_id = c.image_id
JOIN docker_users u
    ON u.username = 'developer1'
WHERE c.container_name = 'web-api-dev';

-- ============================================================================
-- 33. RETRIEVAL QUERIES
-- ============================================================================

-- Image manifests and layer counts.

SELECT *
FROM v_image_inventory
ORDER BY repository_name, tag;

-- Containers and their deployment status.

SELECT *
FROM v_container_inventory
ORDER BY container_name;

-- Detailed image layers.

SELECT
    r.repository_name,
    i.tag,
    l.layer_order,
    l.instruction,
    l.size_mb,
    l.digest
FROM image_layers l
JOIN images i
    ON i.image_id = l.image_id
JOIN image_repositories r
    ON r.repository_id = i.repository_id
ORDER BY
    r.repository_name,
    i.tag,
    l.layer_order;

-- ============================================================================
-- 34. VALIDATION QUERIES
-- ============================================================================

-- Compare image manifest size and layer size.

SELECT
    i.image_id,
    i.total_size_mb,
    COALESCE(SUM(l.size_mb), 0) AS calculated_size_mb,
    i.total_size_mb - COALESCE(SUM(l.size_mb), 0)
        AS remaining_size_mb
FROM images i
LEFT JOIN image_layers l
    ON l.image_id = i.image_id
GROUP BY i.image_id, i.total_size_mb;

-- Check containers that exceed their resource policies.

SELECT
    c.container_name,
    c.cpu_limit,
    p.maximum_cpu,
    c.memory_limit_mb,
    p.maximum_memory_mb
FROM containers c
JOIN resource_policies p
    ON p.policy_id = c.policy_id
WHERE c.cpu_limit > p.maximum_cpu
   OR c.memory_limit_mb > p.maximum_memory_mb;

-- Inspect deployment eligibility.

SELECT
    c.container_name,
    e.eligible,
    e.reason
FROM containers c
CROSS JOIN LATERAL
    evaluate_container_eligibility(c.container_id) e
ORDER BY c.container_name;

-- ============================================================================
-- 35. AGGREGATION AND REPORTING
-- ============================================================================

-- Image count and total storage by repository.

SELECT
    r.repository_name,
    COUNT(i.image_id) AS image_count,
    COALESCE(SUM(i.total_size_mb), 0) AS total_storage_mb,
    COALESCE(AVG(i.total_size_mb), 0) AS average_image_size_mb
FROM image_repositories r
LEFT JOIN images i
    ON i.repository_id = r.repository_id
GROUP BY r.repository_name
ORDER BY total_storage_mb DESC;

-- Container distribution by state.

SELECT
    state,
    COUNT(*) AS container_count,
    SUM(memory_limit_mb) AS allocated_memory_mb,
    SUM(cpu_limit) AS allocated_cpu
FROM containers
GROUP BY state
ORDER BY container_count DESC;

-- Image push and pull success rates.

SELECT
    operation,
    COUNT(*) AS total_operations,
    COUNT(*) FILTER (WHERE succeeded) AS successful_operations,
    COUNT(*) FILTER (WHERE NOT succeeded) AS failed_operations,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE succeeded)
        / NULLIF(COUNT(*), 0),
        2
    ) AS success_percentage
FROM image_distribution_events
GROUP BY operation;

-- ============================================================================
-- 36. WORKFLOW REPORTING
-- ============================================================================

-- Container-to-image-to-registry relationship.

SELECT
    c.container_name,
    r.repository_name,
    i.tag,
    i.origin,
    c.state,
    c.deployment_status,
    reg.hostname
FROM containers c
JOIN images i
    ON i.image_id = c.image_id
JOIN image_repositories r
    ON r.repository_id = i.repository_id
LEFT JOIN registries reg
    ON reg.registry_id = r.registry_id
ORDER BY c.container_name;

-- Container port and volume configuration.

SELECT
    c.container_name,
    cp.host_port,
    cp.container_port,
    cp.protocol,
    cv.host_path,
    cv.container_path,
    cv.read_only
FROM containers c
LEFT JOIN container_ports cp
    ON cp.container_id = c.container_id
LEFT JOIN container_volumes cv
    ON cv.container_id = c.container_id
ORDER BY c.container_name;

-- ============================================================================
-- 37. COMMON TABLE EXPRESSION
-- ============================================================================

WITH image_usage AS (
    SELECT
        i.image_id,
        r.repository_name,
        i.tag,
        COUNT(c.container_id) AS deployment_count
    FROM images i
    JOIN image_repositories r
        ON r.repository_id = i.repository_id
    LEFT JOIN containers c
        ON c.image_id = i.image_id
    GROUP BY
        i.image_id,
        r.repository_name,
        i.tag
)
SELECT
    repository_name,
    tag,
    deployment_count,
    CASE
        WHEN deployment_count = 0 THEN 'unused'
        WHEN deployment_count = 1 THEN 'single deployment'
        ELSE 'multiple deployments'
    END AS usage_category
FROM image_usage
ORDER BY deployment_count DESC;

-- ============================================================================
-- 38. TRANSACTIONAL STATE MANAGEMENT
-- ============================================================================

-- Demonstrates a safe pause operation with transaction handling.
-- The operation can be rolled back without leaving partial state.

BEGIN;

UPDATE containers
SET state = 'paused'
WHERE container_name = 'web-api-dev'
  AND state = 'running';

COMMIT;

-- Resume the container.

BEGIN;

UPDATE containers
SET state = 'running'
WHERE container_name = 'web-api-dev'
  AND state = 'paused';

COMMIT;

-- ============================================================================
-- 39. FAILURE SCENARIOS
-- ============================================================================

-- The following statements intentionally demonstrate validation failures.
-- They are executed inside PL/pgSQL exception blocks so that the complete
-- script continues successfully.

DO $$
BEGIN
    BEGIN
        INSERT INTO container_ports (
            container_id,
            host_port,
            container_port
        )
        SELECT
            container_id,
            70000,
            80
        FROM containers
        WHERE container_name = 'web-api-dev';

    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE
                'Expected invalid port failure: %',
                SQLERRM;
    END;

    BEGIN
        INSERT INTO containers (
            container_name,
            image_id,
            owner_id,
            policy_id,
            cpu_limit,
            memory_limit_mb,
            privileged
        )
        SELECT
            'unauthorized-privileged',
            i.image_id,
            u.user_id,
            p.policy_id,
            1,
            512,
            TRUE
        FROM images i
        JOIN image_repositories r
            ON r.repository_id = i.repository_id
        JOIN docker_users u
            ON u.username = 'developer1'
        JOIN resource_policies p
            ON p.policy_name = 'restricted'
        WHERE r.repository_name = 'training/web-api'
        LIMIT 1;

    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE
                'Expected privileged deployment failure: %',
                SQLERRM;
    END;
END;
$$;

-- ============================================================================
-- 40. AUDIT REPORT
-- ============================================================================

SELECT
    a.audit_id,
    c.container_name,
    u.username,
    a.action,
    a.previous_state,
    a.new_state,
    a.details,
    a.occurred_at
FROM container_audit a
LEFT JOIN containers c
    ON c.container_id = a.container_id
LEFT JOIN docker_users u
    ON u.user_id = a.user_id
ORDER BY a.occurred_at DESC;

-- ============================================================================
-- 41. REGISTRY SECURITY REPORT
-- ============================================================================

SELECT
    r.hostname,
    r.visibility,
    r.tls_required,
    u.username,
    m.can_pull,
    m.can_push,
    m.authenticated_at
FROM registry_memberships m
JOIN registries r
    ON r.registry_id = m.registry_id
JOIN docker_users u
    ON u.user_id = m.user_id
ORDER BY r.hostname, u.username;

-- ============================================================================
-- 42. DEPLOYMENT CAPACITY REPORT
-- ============================================================================

SELECT
    p.policy_name,
    p.maximum_cpu,
    COALESCE(SUM(c.cpu_limit), 0) AS allocated_cpu,
    p.maximum_memory_mb,
    COALESCE(SUM(c.memory_limit_mb), 0) AS allocated_memory_mb,
    COUNT(c.container_id) AS container_count
FROM resource_policies p
LEFT JOIN containers c
    ON c.policy_id = p.policy_id
   AND c.deployment_status = 'deployed'
GROUP BY
    p.policy_id,
    p.policy_name,
    p.maximum_cpu,
    p.maximum_memory_mb
ORDER BY p.policy_name;

-- ============================================================================
-- 43. DATABASE COMPLETION
-- ============================================================================

COMMIT;

-- Final verification.

SELECT 'Docker fundamentals database initialized successfully'
    AS execution_status;

RESET search_path;
