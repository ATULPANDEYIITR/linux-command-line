-- ============================================================
-- DOCKER MULTI-SERVICE APPLICATION
-- PostgreSQL 17
--
-- Database:
--   appdb
--
-- Services:
--   frontend
--   backend
--   database
--
-- Features:
--   Relational application storage
--   Service registry
--   Container lifecycle
--   Networks
--   Persistent volumes
--   Health monitoring
--   Deployment events
--   Dependency validation
--   Deployment reporting
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS docker_app;

SET search_path TO docker_app, public;

-- ------------------------------------------------------------
-- ENUM TYPES
-- ------------------------------------------------------------

CREATE TYPE service_type AS ENUM (
    'frontend',
    'backend',
    'database',
    'cache',
    'worker'
);

CREATE TYPE container_status AS ENUM (
    'created',
    'starting',
    'running',
    'healthy',
    'unhealthy',
    'stopped',
    'failed'
);

CREATE TYPE network_scope AS ENUM (
    'public',
    'internal',
    'isolated'
);

CREATE TYPE health_status AS ENUM (
    'pass',
    'fail',
    'unknown'
);

CREATE TYPE deployment_status AS ENUM (
    'pending',
    'running',
    'successful',
    'failed',
    'rolled_back'
);

-- ------------------------------------------------------------
-- APPLICATION SERVICES
-- ------------------------------------------------------------

CREATE TABLE services (
    service_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_name VARCHAR(63) NOT NULL UNIQUE,

    service_kind service_type NOT NULL,

    container_port INTEGER NOT NULL,

    network network_scope NOT NULL,

    persistent_storage_required BOOLEAN
        NOT NULL DEFAULT FALSE,

    health_check_required BOOLEAN
        NOT NULL DEFAULT TRUE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_service_name
        CHECK (
            service_name ~ '^[a-z][a-z0-9-]{0,62}$'
        ),

    CONSTRAINT valid_container_port
        CHECK (
            container_port BETWEEN 1 AND 65535
        ),

    CONSTRAINT database_network_security
        CHECK (
            service_kind <> 'database'
            OR network <> 'public'
        )
);

CREATE INDEX idx_services_kind
ON services(service_kind);

CREATE INDEX idx_services_enabled
ON services(enabled);

-- ------------------------------------------------------------
-- SERVICE DEPENDENCIES
-- ------------------------------------------------------------

CREATE TABLE service_dependencies (
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,

    depends_on_service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE RESTRICT,

    dependency_required BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (
        service_id,
        depends_on_service_id
    ),

    CHECK (service_id <> depends_on_service_id)
);

CREATE INDEX idx_dependencies_target
ON service_dependencies(depends_on_service_id);

-- ------------------------------------------------------------
-- NETWORKS
-- ------------------------------------------------------------

CREATE TABLE networks (
    network_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    network_name VARCHAR(100) NOT NULL UNIQUE,

    network_driver VARCHAR(30) NOT NULL DEFAULT 'bridge',

    scope network_scope NOT NULL,

    internal_only BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (network_driver IN ('bridge', 'overlay'))
);

CREATE TABLE service_networks (
    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE CASCADE,

    network_id BIGINT NOT NULL
        REFERENCES networks(network_id)
        ON DELETE CASCADE,

    PRIMARY KEY (service_id, network_id)
);

CREATE INDEX idx_service_networks_network
ON service_networks(network_id);

-- ------------------------------------------------------------
-- CONTAINER INSTANCES
-- ------------------------------------------------------------

CREATE TABLE containers (
    container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE RESTRICT,

    container_name VARCHAR(100) NOT NULL UNIQUE,

    image_name VARCHAR(255) NOT NULL,

    image_tag VARCHAR(100) NOT NULL,

    status container_status NOT NULL DEFAULT 'created',

    restart_count INTEGER NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ,

    stopped_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (restart_count >= 0),

    CHECK (
        image_name !~ '^[[:space:]]*$'
    )
);

CREATE INDEX idx_containers_service_status
ON containers(service_id, status);

CREATE INDEX idx_containers_created
ON containers(created_at DESC);

-- ------------------------------------------------------------
-- PERSISTENT VOLUMES
-- ------------------------------------------------------------

CREATE TABLE volumes (
    volume_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    volume_name VARCHAR(100) NOT NULL UNIQUE,

    volume_driver VARCHAR(50) NOT NULL DEFAULT 'local',

    persistent BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE container_volumes (
    container_id BIGINT NOT NULL
        REFERENCES containers(container_id)
        ON DELETE CASCADE,

    volume_id BIGINT NOT NULL
        REFERENCES volumes(volume_id)
        ON DELETE RESTRICT,

    mount_path VARCHAR(255) NOT NULL,

    read_only BOOLEAN NOT NULL DEFAULT FALSE,

    PRIMARY KEY (container_id, volume_id, mount_path),

    CHECK (mount_path LIKE '/%')
);

CREATE INDEX idx_container_volumes_volume
ON container_volumes(volume_id);

-- ------------------------------------------------------------
-- PORT MAPPINGS
-- ------------------------------------------------------------

CREATE TABLE port_mappings (
    mapping_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES containers(container_id)
        ON DELETE CASCADE,

    host_port INTEGER NOT NULL,

    container_port INTEGER NOT NULL,

    protocol VARCHAR(10) NOT NULL DEFAULT 'tcp',

    CHECK (host_port BETWEEN 1 AND 65535),

    CHECK (container_port BETWEEN 1 AND 65535),

    CHECK (protocol IN ('tcp', 'udp')),

    UNIQUE(host_port, protocol)
);

CREATE INDEX idx_port_mappings_container
ON port_mappings(container_id);

-- ------------------------------------------------------------
-- HEALTH CHECK HISTORY
-- ------------------------------------------------------------

CREATE TABLE health_checks (
    health_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES containers(container_id)
        ON DELETE CASCADE,

    check_name VARCHAR(100) NOT NULL,

    status health_status NOT NULL,

    response_time_ms INTEGER,

    details TEXT,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        response_time_ms IS NULL
        OR response_time_ms >= 0
    )
);

CREATE INDEX idx_health_container_time
ON health_checks(container_id, checked_at DESC);

CREATE INDEX idx_health_status
ON health_checks(status);

-- ------------------------------------------------------------
-- DEPLOYMENTS
-- ------------------------------------------------------------

CREATE TABLE deployments (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_name VARCHAR(150) NOT NULL,

    environment VARCHAR(30) NOT NULL,

    status deployment_status NOT NULL DEFAULT 'pending',

    initiated_by VARCHAR(100) NOT NULL,

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        environment IN (
            'development',
            'testing',
            'staging',
            'production'
        )
    ),

    CHECK (
        completed_at IS NULL
        OR started_at IS NULL
        OR completed_at >= started_at
    )
);

CREATE INDEX idx_deployments_status
ON deployments(status, created_at DESC);

CREATE TABLE deployment_services (
    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id)
        ON DELETE CASCADE,

    service_id BIGINT NOT NULL
        REFERENCES services(service_id)
        ON DELETE RESTRICT,

    deployment_status deployment_status NOT NULL DEFAULT 'pending',

    error_message TEXT,

    PRIMARY KEY (deployment_id, service_id)
);

-- ------------------------------------------------------------
-- DEPLOYMENT EVENTS
-- ------------------------------------------------------------

CREATE TABLE deployment_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id)
        ON DELETE CASCADE,

    service_id BIGINT
        REFERENCES services(service_id)
        ON DELETE SET NULL,

    event_type VARCHAR(50) NOT NULL,

    event_message TEXT NOT NULL,

    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_deployment
ON deployment_events(deployment_id, event_time DESC);

-- ------------------------------------------------------------
-- TRIGGER: RECORD SERVICE CREATION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION record_container_creation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO deployment_events (
        deployment_id,
        service_id,
        event_type,
        event_message
    )
    SELECT
        d.deployment_id,
        NEW.service_id,
        'container_created',
        'Container registered: ' || NEW.container_name
    FROM deployments d
    WHERE d.status = 'running'
    ORDER BY d.created_at DESC
    LIMIT 1;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_container_creation
AFTER INSERT ON containers
FOR EACH ROW
EXECUTE FUNCTION record_container_creation();

-- ------------------------------------------------------------
-- TRIGGER: PREVENT INVALID CONTAINER STATE TRANSITIONS
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_container_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.status = 'created'
            AND NEW.status IN ('starting', 'stopped'))

        OR

        (OLD.status = 'starting'
            AND NEW.status IN ('running', 'failed', 'stopped'))

        OR

        (OLD.status = 'running'
            AND NEW.status IN ('healthy', 'unhealthy', 'failed', 'stopped'))

        OR

        (OLD.status = 'healthy'
            AND NEW.status IN ('unhealthy', 'stopped'))

        OR

        (OLD.status = 'unhealthy'
            AND NEW.status IN ('healthy', 'failed', 'stopped'))

        OR

        (OLD.status = 'failed'
            AND NEW.status IN ('starting', 'stopped'))

        OR

        (OLD.status = 'stopped'
            AND NEW.status = 'starting')
    ) THEN
        RAISE EXCEPTION
            'Invalid container state transition: % -> %',
            OLD.status,
            NEW.status;
    END IF;

    IF NEW.status = 'starting'
       AND OLD.status IN ('created', 'failed', 'stopped') THEN

        NEW.started_at = NOW();
        NEW.stopped_at = NULL;
    END IF;

    IF NEW.status = 'stopped' THEN
        NEW.stopped_at = NOW();
    END IF;

    IF NEW.status = 'starting'
       AND OLD.status = 'failed' THEN

        NEW.restart_count = OLD.restart_count + 1;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_transition
BEFORE UPDATE OF status ON containers
FOR EACH ROW
EXECUTE FUNCTION validate_container_transition();

-- ------------------------------------------------------------
-- TRIGGER: PROTECT PERSISTENT VOLUME ATTACHMENTS
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_volume_attachment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    is_persistent BOOLEAN;
BEGIN
    SELECT persistent
    INTO is_persistent
    FROM volumes
    WHERE volume_id = NEW.volume_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Volume does not exist.';
    END IF;

    IF NOT is_persistent THEN
        RAISE EXCEPTION
            'Database storage must use a persistent volume.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_volume_attachment
BEFORE INSERT OR UPDATE ON container_volumes
FOR EACH ROW
EXECUTE FUNCTION validate_volume_attachment();

-- ------------------------------------------------------------
-- FUNCTION: CHECK SERVICE DEPENDENCIES
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION dependencies_healthy(
    p_service_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT NOT EXISTS (
        SELECT 1
        FROM service_dependencies dependency
        JOIN services dependent_service
          ON dependent_service.service_id =
             dependency.depends_on_service_id
        LEFT JOIN containers c
          ON c.service_id = dependent_service.service_id
         AND c.status = 'healthy'
        WHERE dependency.service_id = p_service_id
          AND dependency.dependency_required = TRUE
          AND c.container_id IS NULL
    );
$$;

-- ------------------------------------------------------------
-- FUNCTION: CHECK DATABASE STORAGE
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION database_storage_ready(
    p_service_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT
        NOT EXISTS (
            SELECT 1
            FROM services s
            WHERE s.service_id = p_service_id
              AND s.service_kind = 'database'
        )
        OR EXISTS (
            SELECT 1
            FROM containers c
            JOIN container_volumes cv
              ON cv.container_id = c.container_id
            JOIN volumes v
              ON v.volume_id = cv.volume_id
            WHERE c.service_id = p_service_id
              AND v.persistent = TRUE
              AND cv.mount_path =
                  '/var/lib/postgresql/data'
        );
$$;

-- ------------------------------------------------------------
-- FUNCTION: DETERMINE DEPLOYMENT ELIGIBILITY
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION deployment_eligible(
    p_service_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT
        EXISTS (
            SELECT 1
            FROM services
            WHERE service_id = p_service_id
              AND enabled = TRUE
        )
        AND dependencies_healthy(p_service_id)
        AND database_storage_ready(p_service_id)
        AND NOT EXISTS (
            SELECT 1
            FROM services s
            WHERE s.service_id = p_service_id
              AND s.health_check_required = TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM containers c
                  WHERE c.service_id = s.service_id
                    AND c.status IN ('created', 'starting', 'running', 'healthy')
              )
        );
$$;

-- ------------------------------------------------------------
-- PROCEDURE: REGISTER DEPLOYMENT
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE register_deployment(
    p_name VARCHAR(150),
    p_environment VARCHAR(30),
    p_initiated_by VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
DECLARE
    new_deployment_id BIGINT;
BEGIN
    INSERT INTO deployments (
        deployment_name,
        environment,
        status,
        initiated_by,
        started_at
    )
    VALUES (
        p_name,
        p_environment,
        'running',
        p_initiated_by,
        NOW()
    )
    RETURNING deployment_id INTO new_deployment_id;

    INSERT INTO deployment_services (
        deployment_id,
        service_id,
        deployment_status
    )
    SELECT
        new_deployment_id,
        service_id,
        'pending'
    FROM services
    WHERE enabled = TRUE;

    INSERT INTO deployment_events (
        deployment_id,
        event_type,
        event_message
    )
    VALUES (
        new_deployment_id,
        'deployment_started',
        'Deployment registered.'
    );
END;
$$;

-- ------------------------------------------------------------
-- VIEW: CURRENT SERVICE STATUS
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW service_runtime_report AS
SELECT
    s.service_id,
    s.service_name,
    s.service_kind,
    s.container_port,
    s.network,
    c.container_name,
    c.image_name,
    c.image_tag,
    c.status,
    c.restart_count,
    latest_health.status AS health_status,
    latest_health.checked_at AS last_health_check
FROM services s
LEFT JOIN containers c
    ON c.service_id = s.service_id
LEFT JOIN LATERAL (
    SELECT h.status, h.checked_at
    FROM health_checks h
    WHERE h.container_id = c.container_id
    ORDER BY h.checked_at DESC
    LIMIT 1
) latest_health ON TRUE;

-- ------------------------------------------------------------
-- SAMPLE DATA
-- ------------------------------------------------------------

INSERT INTO services (
    service_name,
    service_kind,
    container_port,
    network,
    persistent_storage_required,
    health_check_required
)
VALUES
    ('database', 'database', 5432, 'internal', TRUE, TRUE),
    ('backend', 'backend', 8000, 'internal', FALSE, TRUE),
    ('frontend', 'frontend', 3000, 'public', FALSE, TRUE),
    ('worker', 'worker', 9000, 'internal', FALSE, TRUE);

INSERT INTO service_dependencies (
    service_id,
    depends_on_service_id
)
SELECT child.service_id, parent.service_id
FROM (
    VALUES
        ('backend', 'database'),
        ('frontend', 'backend'),
        ('worker', 'backend')
) AS relations(child_name, parent_name)
JOIN services child
    ON child.service_name = relations.child_name
JOIN services parent
    ON parent.service_name = relations.parent_name;

INSERT INTO networks (
    network_name,
    network_driver,
    scope,
    internal_only
)
VALUES
    ('public_network', 'bridge', 'public', FALSE),
    ('internal_network', 'bridge', 'internal', TRUE);

INSERT INTO service_networks (
    service_id,
    network_id
)
SELECT s.service_id, n.network_id
FROM (
    VALUES
        ('frontend', 'public_network'),
        ('frontend', 'internal_network'),
        ('backend', 'internal_network'),
        ('database', 'internal_network'),
        ('worker', 'internal_network')
) AS assignment(service_name, network_name)
JOIN services s
    ON s.service_name = assignment.service_name
JOIN networks n
    ON n.network_name = assignment.network_name;

INSERT INTO volumes (
    volume_name,
    volume_driver,
    persistent
)
VALUES ('postgres_data', 'local', TRUE);

INSERT INTO deployments (
    deployment_name,
    environment,
    status,
    initiated_by,
    started_at
)
VALUES (
    'initial-development-deployment',
    'development',
    'running',
    'system_admin',
    NOW()
);

INSERT INTO containers (
    service_id,
    container_name,
    image_name,
    image_tag,
    status
)
SELECT
    service_id,
    'docker-' || service_name,
    CASE service_kind
        WHEN 'database' THEN 'postgres'
        WHEN 'backend' THEN 'python-backend'
        WHEN 'frontend' THEN 'node-frontend'
        ELSE 'worker-image'
    END,
    CASE service_kind
        WHEN 'database' THEN '17-alpine'
        ELSE '1.0'
    END,
    'created'
FROM services
WHERE enabled = TRUE;

INSERT INTO container_volumes (
    container_id,
    volume_id,
    mount_path
)
SELECT
    c.container_id,
    v.volume_id,
    '/var/lib/postgresql/data'
FROM containers c
JOIN services s
    ON s.service_id = c.service_id
JOIN volumes v
    ON v.volume_name = 'postgres_data'
WHERE s.service_name = 'database';

INSERT INTO port_mappings (
    container_id,
    host_port,
    container_port
)
SELECT
    c.container_id,
    s.container_port,
    s.container_port
FROM containers c
JOIN services s
    ON s.service_id = c.service_id
WHERE s.service_name IN ('frontend', 'backend');

INSERT INTO deployment_services (
    deployment_id,
    service_id,
    deployment_status
)
SELECT
    d.deployment_id,
    s.service_id,
    'pending'
FROM deployments d
CROSS JOIN services s
WHERE d.deployment_name =
    'initial-development-deployment';

-- ------------------------------------------------------------
-- TRANSACTIONAL CONTAINER STARTUP
-- ------------------------------------------------------------

DO $$
DECLARE
    service_record RECORD;
    current_container BIGINT;
BEGIN
    -- Start in dependency order: database, backend, frontend.
    FOR service_record IN
        WITH RECURSIVE dependency_tree AS (
            SELECT
                s.service_id,
                s.service_name,
                0 AS depth
            FROM services s
            WHERE NOT EXISTS (
                SELECT 1
                FROM service_dependencies sd
                WHERE sd.service_id = s.service_id
            )

            UNION ALL

            SELECT
                child.service_id,
                child.service_name,
                parent.depth + 1
            FROM dependency_tree parent
            JOIN service_dependencies sd
                ON sd.depends_on_service_id = parent.service_id
            JOIN services child
                ON child.service_id = sd.service_id
        )
        SELECT DISTINCT ON (service_id)
            service_id,
            service_name,
            depth
        FROM dependency_tree
        ORDER BY service_id, depth
    LOOP
        IF NOT dependencies_healthy(service_record.service_id) THEN
            RAISE NOTICE
                'Dependencies not healthy for %',
                service_record.service_name;
        END IF;

        SELECT container_id
        INTO current_container
        FROM containers
        WHERE service_id = service_record.service_id
        ORDER BY container_id DESC
        LIMIT 1;

        IF current_container IS NOT NULL THEN
            UPDATE containers
            SET status = 'starting'
            WHERE container_id = current_container;

            UPDATE containers
            SET status = 'running'
            WHERE container_id = current_container;

            UPDATE containers
            SET status = 'healthy'
            WHERE container_id = current_container;

            INSERT INTO health_checks (
                container_id,
                check_name,
                status,
                response_time_ms,
                details
            )
            VALUES (
                current_container,
                'startup-health-check',
                'pass',
                12,
                'Demonstration health check'
            );
        END IF;
    END LOOP;
END;
$$;

-- ------------------------------------------------------------
-- DEPLOYMENT ELIGIBILITY REPORT
-- ------------------------------------------------------------

SELECT
    service_name,
    service_kind,
    deployment_eligible(service_id) AS eligible
FROM services
ORDER BY service_id;

-- ------------------------------------------------------------
-- SERVICE DEPENDENCY REPORT
-- ------------------------------------------------------------

SELECT
    child.service_name AS service,
    parent.service_name AS depends_on,
    sd.dependency_required
FROM service_dependencies sd
JOIN services child
    ON child.service_id = sd.service_id
JOIN services parent
    ON parent.service_id = sd.depends_on_service_id
ORDER BY child.service_name;

-- ------------------------------------------------------------
-- CONTAINER RETRIEVAL
-- ------------------------------------------------------------

SELECT
    container_name,
    image_name,
    image_tag,
    status,
    restart_count,
    started_at
FROM containers
ORDER BY container_id;

-- ------------------------------------------------------------
-- HEALTH AGGREGATION
-- ------------------------------------------------------------

SELECT
    s.service_name,
    COUNT(h.health_check_id) AS total_checks,
    COUNT(*) FILTER (
        WHERE h.status = 'pass'
    ) AS successful_checks,
    COUNT(*) FILTER (
        WHERE h.status = 'fail'
    ) AS failed_checks,
    ROUND(
        AVG(h.response_time_ms)::NUMERIC,
        2
    ) AS average_response_ms
FROM services s
JOIN containers c
    ON c.service_id = s.service_id
LEFT JOIN health_checks h
    ON h.container_id = c.container_id
GROUP BY s.service_name
ORDER BY s.service_name;

-- ------------------------------------------------------------
-- PERSISTENT STORAGE REPORT
-- ------------------------------------------------------------

SELECT
    c.container_name,
    v.volume_name,
    cv.mount_path,
    v.persistent,
    cv.read_only
FROM container_volumes cv
JOIN containers c
    ON c.container_id = cv.container_id
JOIN volumes v
    ON v.volume_id = cv.volume_id;

-- ------------------------------------------------------------
-- NETWORK ISOLATION REPORT
-- ------------------------------------------------------------

SELECT
    s.service_name,
    n.network_name,
    n.scope,
    n.internal_only
FROM service_networks sn
JOIN services s
    ON s.service_id = sn.service_id
JOIN networks n
    ON n.network_id = sn.network_id
ORDER BY s.service_name, n.network_name;

-- ------------------------------------------------------------
-- DEPLOYMENT COMPLETION
-- ------------------------------------------------------------

UPDATE deployments
SET
    status = 'successful',
    completed_at = NOW()
WHERE deployment_name =
    'initial-development-deployment'
AND NOT EXISTS (
    SELECT 1
    FROM deployment_services ds
    WHERE ds.deployment_id = deployments.deployment_id
      AND ds.deployment_status IN ('failed', 'rolled_back')
);

COMMIT;

-- ------------------------------------------------------------
-- OPERATIONAL QUERIES
-- ------------------------------------------------------------

-- 1. Current application services.
SELECT *
FROM service_runtime_report
ORDER BY service_name;

-- 2. Containers that require attention.
SELECT
    container_name,
    status,
    restart_count
FROM containers
WHERE status IN ('unhealthy', 'failed');

-- 3. Latest health check per container.
SELECT DISTINCT ON (container_id)
    container_id,
    status,
    response_time_ms,
    checked_at
FROM health_checks
ORDER BY container_id, checked_at DESC;

-- 4. Failed deployment events.
SELECT
    d.deployment_name,
    e.event_type,
    e.event_message,
    e.event_time
FROM deployment_events e
JOIN deployments d
    ON d.deployment_id = e.deployment_id
WHERE e.event_type ILIKE '%fail%'
ORDER BY e.event_time DESC;

-- 5. Storage usage and attachment counts.
SELECT
    v.volume_name,
    v.persistent,
    COUNT(cv.container_id) AS attached_containers
FROM volumes v
LEFT JOIN container_volumes cv
    ON cv.volume_id = v.volume_id
GROUP BY v.volume_id, v.volume_name, v.persistent;
