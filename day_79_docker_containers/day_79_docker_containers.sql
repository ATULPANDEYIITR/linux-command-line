-- ============================================================
-- DOCKER CONTAINER MANAGEMENT AND OPERATIONS DATABASE
-- PostgreSQL 15+
--
-- Covers:
--   Docker hosts
--   Images
--   Containers
--   Lifecycle transitions
--   Environment variables
--   Networks
--   Network attachments
--   Persistent volumes
--   Volume mounts
--   Port mappings
--   Resource allocations
--   Health checks
--   Deployment policies
--   Deployment eligibility
--   Operational reporting
--
-- Execute:
--   psql -U postgres -d postgres -f docker_management.sql
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS docker_ops;

SET search_path TO docker_ops, public;

-- ------------------------------------------------------------
-- ENUMERATED DOMAIN TYPES
-- ------------------------------------------------------------

CREATE TYPE container_state AS ENUM (
    'created',
    'running',
    'paused',
    'restarting',
    'exited',
    'dead'
);

CREATE TYPE network_driver AS ENUM (
    'bridge',
    'host',
    'overlay',
    'macvlan',
    'none'
);

CREATE TYPE restart_policy AS ENUM (
    'no',
    'always',
    'unless-stopped',
    'on-failure'
);

CREATE TYPE health_status AS ENUM (
    'starting',
    'healthy',
    'unhealthy',
    'not-configured'
);

CREATE TYPE volume_type AS ENUM (
    'named',
    'bind',
    'anonymous'
);

CREATE TYPE deployment_status AS ENUM (
    'pending',
    'approved',
    'rejected',
    'deployed',
    'failed',
    'rolled-back'
);

-- ------------------------------------------------------------
-- DOCKER HOSTS
-- ------------------------------------------------------------

CREATE TABLE docker_hosts (
    host_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    host_name VARCHAR(150) NOT NULL UNIQUE,

    engine_version VARCHAR(50) NOT NULL,

    operating_system VARCHAR(100) NOT NULL,

    architecture VARCHAR(50) NOT NULL,

    total_cpu_cores NUMERIC(8,2) NOT NULL
        CHECK (total_cpu_cores > 0),

    total_memory_bytes BIGINT NOT NULL
        CHECK (total_memory_bytes > 0),

    available BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (length(trim(host_name)) > 0)
);

-- ------------------------------------------------------------
-- DOCKER IMAGES
-- ------------------------------------------------------------

CREATE TABLE docker_images (
    image_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    image_name VARCHAR(255) NOT NULL,

    image_tag VARCHAR(128) NOT NULL DEFAULT 'latest',

    digest VARCHAR(255),

    image_size_bytes BIGINT NOT NULL
        CHECK (image_size_bytes >= 0),

    architecture VARCHAR(50) NOT NULL,

    is_trusted BOOLEAN NOT NULL DEFAULT FALSE,

    pulled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (image_name, image_tag),

    CHECK (length(trim(image_name)) > 0)
);

-- ------------------------------------------------------------
-- NETWORKS
-- ------------------------------------------------------------

CREATE TABLE docker_networks (
    network_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    host_id BIGINT NOT NULL
        REFERENCES docker_hosts(host_id),

    network_name VARCHAR(150) NOT NULL,

    driver network_driver NOT NULL DEFAULT 'bridge',

    subnet CIDR,

    gateway INET,

    internal BOOLEAN NOT NULL DEFAULT FALSE,

    attachable BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (host_id, network_name)
);

CREATE INDEX idx_network_host
ON docker_networks(host_id);

-- ------------------------------------------------------------
-- PERSISTENT VOLUMES
-- ------------------------------------------------------------

CREATE TABLE docker_volumes (
    volume_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    host_id BIGINT NOT NULL
        REFERENCES docker_hosts(host_id),

    volume_name VARCHAR(255) NOT NULL,

    volume_kind volume_type NOT NULL,

    driver VARCHAR(100) NOT NULL DEFAULT 'local',

    mountpoint TEXT,

    size_bytes BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (host_id, volume_name),

    CHECK (size_bytes IS NULL OR size_bytes >= 0)
);

CREATE INDEX idx_volume_host
ON docker_volumes(host_id);

-- ------------------------------------------------------------
-- CONTAINERS
-- ------------------------------------------------------------

CREATE TABLE docker_containers (
    container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    external_id VARCHAR(128) NOT NULL UNIQUE,

    host_id BIGINT NOT NULL
        REFERENCES docker_hosts(host_id),

    image_id BIGINT NOT NULL
        REFERENCES docker_images(image_id),

    container_name VARCHAR(128) NOT NULL,

    state container_state NOT NULL DEFAULT 'created',

    restart_policy restart_policy NOT NULL DEFAULT 'no',

    cpu_limit NUMERIC(8,3) NOT NULL DEFAULT 0.5
        CHECK (cpu_limit > 0),

    memory_limit_bytes BIGINT NOT NULL
        CHECK (memory_limit_bytes >= 16777216),

    privileged BOOLEAN NOT NULL DEFAULT FALSE,

    read_only_root BOOLEAN NOT NULL DEFAULT TRUE,

    auto_remove BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    started_at TIMESTAMPTZ,

    stopped_at TIMESTAMPTZ,

    UNIQUE (host_id, container_name),

    CHECK (length(trim(container_name)) > 0),

    CHECK (
        started_at IS NULL OR started_at >= created_at
    )
);

CREATE INDEX idx_container_host_state
ON docker_containers(host_id, state);

CREATE INDEX idx_container_image
ON docker_containers(image_id);

CREATE INDEX idx_container_created
ON docker_containers(created_at DESC);

CREATE INDEX idx_running_containers
ON docker_containers(host_id, container_name)
WHERE state = 'running';

-- ------------------------------------------------------------
-- ENVIRONMENT VARIABLES
--
-- Values are stored separately to avoid exposing them in
-- general container inventory queries.
--
-- Production secrets should be stored in a dedicated secret
-- manager rather than ordinary application configuration.
-- ------------------------------------------------------------

CREATE TABLE container_environment (
    environment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES docker_containers(container_id)
        ON DELETE CASCADE,

    variable_name VARCHAR(128) NOT NULL,

    variable_value TEXT NOT NULL,

    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (container_id, variable_name),

    CHECK (
        variable_name ~ '^[A-Za-z_][A-Za-z0-9_]*$'
    ),

    CHECK (position(chr(0) IN variable_value) = 0)
);

CREATE INDEX idx_environment_container
ON container_environment(container_id);

-- ------------------------------------------------------------
-- PORT MAPPINGS
-- ------------------------------------------------------------

CREATE TABLE container_ports (
    port_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES docker_containers(container_id)
        ON DELETE CASCADE,

    host_ip INET NOT NULL DEFAULT '0.0.0.0',

    host_port INTEGER NOT NULL
        CHECK (host_port BETWEEN 1 AND 65535),

    container_port INTEGER NOT NULL
        CHECK (container_port BETWEEN 1 AND 65535),

    protocol VARCHAR(4) NOT NULL DEFAULT 'tcp'
        CHECK (protocol IN ('tcp', 'udp')),

    UNIQUE (
        container_id,
        host_ip,
        host_port,
        protocol
    )
);

CREATE INDEX idx_container_ports
ON container_ports(host_port, protocol);

-- ------------------------------------------------------------
-- NETWORK ATTACHMENTS
-- ------------------------------------------------------------

CREATE TABLE container_network_attachments (
    attachment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES docker_containers(container_id)
        ON DELETE CASCADE,

    network_id BIGINT NOT NULL
        REFERENCES docker_networks(network_id)
        ON DELETE CASCADE,

    ipv4_address INET,

    aliases TEXT[] NOT NULL DEFAULT '{}',

    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (container_id, network_id)
);

CREATE INDEX idx_attachment_network
ON container_network_attachments(network_id);

-- ------------------------------------------------------------
-- VOLUME MOUNTS
-- ------------------------------------------------------------

CREATE TABLE container_volume_mounts (
    mount_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES docker_containers(container_id)
        ON DELETE CASCADE,

    volume_id BIGINT NOT NULL
        REFERENCES docker_volumes(volume_id),

    destination TEXT NOT NULL,

    read_only BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (container_id, destination),

    CHECK (destination LIKE '/%'),

    CHECK (destination NOT LIKE '%/../%')
);

CREATE INDEX idx_volume_mount_container
ON container_volume_mounts(container_id);

-- ------------------------------------------------------------
-- HEALTH CHECK HISTORY
-- ------------------------------------------------------------

CREATE TABLE container_health_checks (
    health_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES docker_containers(container_id)
        ON DELETE CASCADE,

    status health_status NOT NULL,

    exit_code INTEGER,

    output TEXT,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    response_time_ms INTEGER
        CHECK (
            response_time_ms IS NULL OR response_time_ms >= 0
        )
);

CREATE INDEX idx_health_latest
ON container_health_checks(
    container_id,
    checked_at DESC
);

-- ------------------------------------------------------------
-- LIFECYCLE EVENTS
-- ------------------------------------------------------------

CREATE TABLE container_lifecycle_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES docker_containers(container_id)
        ON DELETE CASCADE,

    previous_state container_state,

    new_state container_state NOT NULL,

    event_reason TEXT,

    actor VARCHAR(150) NOT NULL,

    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lifecycle_history
ON container_lifecycle_events(
    container_id,
    event_time DESC
);

-- ------------------------------------------------------------
-- DEPLOYMENT POLICIES
-- ------------------------------------------------------------

CREATE TABLE deployment_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(150) NOT NULL UNIQUE,

    allow_privileged BOOLEAN NOT NULL DEFAULT FALSE,

    require_read_only_root BOOLEAN NOT NULL DEFAULT TRUE,

    require_trusted_image BOOLEAN NOT NULL DEFAULT TRUE,

    require_healthy_container BOOLEAN NOT NULL DEFAULT TRUE,

    max_cpu NUMERIC(8,3) NOT NULL
        CHECK (max_cpu > 0),

    max_memory_bytes BIGINT NOT NULL
        CHECK (max_memory_bytes > 0),

    max_published_ports INTEGER NOT NULL DEFAULT 10
        CHECK (max_published_ports >= 0),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE deployment_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL
        REFERENCES docker_containers(container_id),

    policy_id BIGINT NOT NULL
        REFERENCES deployment_policies(policy_id),

    requested_by VARCHAR(150) NOT NULL,

    status deployment_status NOT NULL DEFAULT 'pending',

    decision_reason TEXT,

    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    decided_at TIMESTAMPTZ
);

CREATE INDEX idx_deployment_status
ON deployment_requests(status, requested_at DESC);

-- ------------------------------------------------------------
-- STATE TRANSITION VALIDATION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_container_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    allowed BOOLEAN := FALSE;
BEGIN
    IF NEW.state = OLD.state THEN
        RETURN NEW;
    END IF;

    CASE OLD.state
        WHEN 'created' THEN
            allowed := NEW.state IN ('running', 'exited', 'dead');

        WHEN 'running' THEN
            allowed := NEW.state IN (
                'paused', 'restarting', 'exited', 'dead'
            );

        WHEN 'paused' THEN
            allowed := NEW.state IN ('running', 'exited', 'dead');

        WHEN 'restarting' THEN
            allowed := NEW.state IN ('running', 'exited', 'dead');

        WHEN 'exited' THEN
            allowed := NEW.state IN ('running', 'dead');

        WHEN 'dead' THEN
            allowed := FALSE;
    END CASE;

    IF NOT allowed THEN
        RAISE EXCEPTION
            'Invalid container transition: % -> %',
            OLD.state,
            NEW.state;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_container_transition
BEFORE UPDATE OF state
ON docker_containers
FOR EACH ROW
EXECUTE FUNCTION validate_container_transition();

-- ------------------------------------------------------------
-- LIFECYCLE AUDIT TRIGGER
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION record_container_lifecycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state IS DISTINCT FROM NEW.state THEN

        INSERT INTO container_lifecycle_events (
            container_id,
            previous_state,
            new_state,
            event_reason,
            actor
        )
        VALUES (
            NEW.container_id,
            OLD.state,
            NEW.state,
            'Container state updated',
            current_user
        );

        IF NEW.state = 'running' THEN
            NEW.started_at := NOW();
            NEW.stopped_at := NULL;

        ELSIF NEW.state IN ('exited', 'dead') THEN
            NEW.stopped_at := NOW();
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_container_lifecycle
BEFORE UPDATE OF state
ON docker_containers
FOR EACH ROW
EXECUTE FUNCTION record_container_lifecycle();

-- ------------------------------------------------------------
-- ENVIRONMENT VARIABLE UPSERT FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_container_environment(
    p_container_id BIGINT,
    p_name VARCHAR,
    p_value TEXT,
    p_sensitive BOOLEAN DEFAULT FALSE
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    result_id BIGINT;
BEGIN
    IF p_name !~ '^[A-Za-z_][A-Za-z0-9_]*$' THEN
        RAISE EXCEPTION 'Invalid environment variable name.';
    END IF;

    INSERT INTO container_environment (
        container_id,
        variable_name,
        variable_value,
        is_sensitive
    )
    VALUES (
        p_container_id,
        p_name,
        p_value,
        p_sensitive
    )
    ON CONFLICT (container_id, variable_name)
    DO UPDATE SET
        variable_value = EXCLUDED.variable_value,
        is_sensitive = EXCLUDED.is_sensitive
    RETURNING environment_id INTO result_id;

    RETURN result_id;
END;
$$;

-- ------------------------------------------------------------
-- LATEST HEALTH STATUS FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION latest_health_status(
    p_container_id BIGINT
)
RETURNS health_status
LANGUAGE sql
STABLE
AS $$
    SELECT status
    FROM container_health_checks
    WHERE container_id = p_container_id
    ORDER BY checked_at DESC, health_check_id DESC
    LIMIT 1;
$$;

-- ------------------------------------------------------------
-- DEPLOYMENT ELIGIBILITY FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION evaluate_deployment(
    p_request_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reasons TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    request_record RECORD;
    errors TEXT[] := ARRAY[]::TEXT[];
    published_ports INTEGER;
    current_health health_status;
BEGIN
    SELECT
        dr.request_id,
        dr.status,
        c.state,
        c.cpu_limit,
        c.memory_limit_bytes,
        c.privileged,
        c.read_only_root,
        i.is_trusted,
        p.allow_privileged,
        p.require_read_only_root,
        p.require_trusted_image,
        p.require_healthy_container,
        p.max_cpu,
        p.max_memory_bytes,
        p.max_published_ports,
        c.container_id
    INTO request_record
    FROM deployment_requests dr
    JOIN docker_containers c
        ON c.container_id = dr.container_id
    JOIN docker_images i
        ON i.image_id = c.image_id
    JOIN deployment_policies p
        ON p.policy_id = dr.policy_id
    WHERE dr.request_id = p_request_id
      AND p.enabled = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Deployment request or active policy not found: %',
            p_request_id;
    END IF;

    IF request_record.state <> 'running' THEN
        errors := array_append(
            errors,
            'Container is not running'
        );
    END IF;

    IF request_record.privileged
       AND NOT request_record.allow_privileged THEN
        errors := array_append(
            errors,
            'Privileged mode prohibited'
        );
    END IF;

    IF request_record.read_only_root = FALSE
       AND request_record.require_read_only_root THEN
        errors := array_append(
            errors,
            'Read-only root filesystem required'
        );
    END IF;

    IF request_record.cpu_limit > request_record.max_cpu THEN
        errors := array_append(
            errors,
            'CPU allocation exceeds policy'
        );
    END IF;

    IF request_record.memory_limit_bytes >
       request_record.max_memory_bytes THEN
        errors := array_append(
            errors,
            'Memory allocation exceeds policy'
        );
    END IF;

    IF request_record.require_trusted_image
       AND NOT request_record.is_trusted THEN
        errors := array_append(
            errors,
            'Image is not trusted'
        );
    END IF;

    SELECT COUNT(*)::INTEGER
    INTO published_ports
    FROM container_ports
    WHERE container_id = request_record.container_id;

    IF published_ports > request_record.max_published_ports THEN
        errors := array_append(
            errors,
            'Published port limit exceeded'
        );
    END IF;

    IF request_record.require_healthy_container THEN

        current_health := latest_health_status(
            request_record.container_id
        );

        IF current_health IS DISTINCT FROM 'healthy'::health_status THEN
            errors := array_append(
                errors,
                'Container does not have a healthy status'
            );
        END IF;
    END IF;

    eligible := cardinality(errors) = 0;

    reasons := CASE
        WHEN eligible THEN 'All deployment policies satisfied'
        ELSE array_to_string(errors, '; ')
    END;

    RETURN NEXT;
END;
$$;

-- ------------------------------------------------------------
-- DEPLOYMENT PROCESSING PROCEDURE
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE process_deployment(
    p_request_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    decision RECORD;
BEGIN
    SELECT *
    INTO decision
    FROM evaluate_deployment(p_request_id);

    UPDATE deployment_requests
    SET
        status = CASE
            WHEN decision.eligible
                THEN 'approved'::deployment_status
            ELSE 'rejected'::deployment_status
        END,
        decision_reason = decision.reasons,
        decided_at = NOW()
    WHERE request_id = p_request_id
      AND status = 'pending';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Only pending deployment requests can be processed.';
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- OPERATIONAL VIEWS
-- ------------------------------------------------------------

CREATE VIEW container_inventory AS
SELECT
    c.container_id,
    c.external_id,
    h.host_name,
    c.container_name,
    i.image_name,
    i.image_tag,
    c.state,
    c.cpu_limit,
    ROUND(c.memory_limit_bytes / 1048576.0, 2)
        AS memory_limit_mb,
    c.restart_policy,
    c.created_at,
    c.started_at,
    c.stopped_at
FROM docker_containers c
JOIN docker_hosts h
    ON h.host_id = c.host_id
JOIN docker_images i
    ON i.image_id = c.image_id;

CREATE VIEW container_network_inventory AS
SELECT
    c.container_name,
    n.network_name,
    n.driver,
    a.ipv4_address,
    a.connected_at
FROM container_network_attachments a
JOIN docker_containers c
    ON c.container_id = a.container_id
JOIN docker_networks n
    ON n.network_id = a.network_id;

CREATE VIEW container_health_inventory AS
SELECT DISTINCT ON (c.container_id)
    c.container_id,
    c.container_name,
    h.status,
    h.response_time_ms,
    h.checked_at
FROM docker_containers c
JOIN container_health_checks h
    ON h.container_id = c.container_id
ORDER BY
    c.container_id,
    h.checked_at DESC,
    h.health_check_id DESC;

CREATE VIEW host_resource_inventory AS
SELECT
    h.host_id,
    h.host_name,
    h.total_cpu_cores,
    COALESCE(SUM(
        CASE WHEN c.state = 'running'
            THEN c.cpu_limit
            ELSE 0
        END
    ), 0) AS allocated_cpu,
    h.total_memory_bytes,
    COALESCE(SUM(
        CASE WHEN c.state = 'running'
            THEN c.memory_limit_bytes
            ELSE 0
        END
    ), 0) AS allocated_memory
FROM docker_hosts h
LEFT JOIN docker_containers c
    ON c.host_id = h.host_id
GROUP BY
    h.host_id,
    h.host_name,
    h.total_cpu_cores,
    h.total_memory_bytes;

-- ------------------------------------------------------------
-- SAMPLE HOSTS
-- ------------------------------------------------------------

INSERT INTO docker_hosts (
    host_name,
    engine_version,
    operating_system,
    architecture,
    total_cpu_cores,
    total_memory_bytes
)
VALUES
(
    'docker-production-01',
    '28.0.0',
    'Linux',
    'x86_64',
    16,
    34359738368
),
(
    'docker-development-01',
    '28.0.0',
    'Windows',
    'x86_64',
    8,
    17179869184
);

-- ------------------------------------------------------------
-- SAMPLE IMAGES
-- ------------------------------------------------------------

INSERT INTO docker_images (
    image_name,
    image_tag,
    digest,
    image_size_bytes,
    architecture,
    is_trusted
)
VALUES
(
    'nginx',
    'alpine',
    'sha256:111111111111',
    50000000,
    'amd64',
    TRUE
),
(
    'postgres',
    '16-alpine',
    'sha256:222222222222',
    250000000,
    'amd64',
    TRUE
),
(
    'unverified/application',
    'latest',
    'sha256:333333333333',
    120000000,
    'amd64',
    FALSE
);

-- ------------------------------------------------------------
-- SAMPLE NETWORKS
-- ------------------------------------------------------------

INSERT INTO docker_networks (
    host_id,
    network_name,
    driver,
    subnet,
    gateway,
    internal
)
SELECT
    host_id,
    'application-network',
    'bridge',
    '172.25.0.0/16',
    '172.25.0.1',
    FALSE
FROM docker_hosts
WHERE host_name = 'docker-production-01';

INSERT INTO docker_networks (
    host_id,
    network_name,
    driver,
    subnet,
    gateway,
    internal
)
SELECT
    host_id,
    'database-network',
    'bridge',
    '172.26.0.0/16',
    '172.26.0.1',
    TRUE
FROM docker_hosts
WHERE host_name = 'docker-production-01';

-- ------------------------------------------------------------
-- SAMPLE VOLUMES
-- ------------------------------------------------------------

INSERT INTO docker_volumes (
    host_id,
    volume_name,
    volume_kind,
    driver,
    mountpoint
)
SELECT
    host_id,
    'nginx-data',
    'named',
    'local',
    '/var/lib/docker/volumes/nginx-data/_data'
FROM docker_hosts
WHERE host_name = 'docker-production-01';

INSERT INTO docker_volumes (
    host_id,
    volume_name,
    volume_kind,
    driver,
    mountpoint
)
SELECT
    host_id,
    'postgres-data',
    'named',
    'local',
    '/var/lib/docker/volumes/postgres-data/_data'
FROM docker_hosts
WHERE host_name = 'docker-production-01';

-- ------------------------------------------------------------
-- SAMPLE CONTAINERS
-- ------------------------------------------------------------

INSERT INTO docker_containers (
    external_id,
    host_id,
    image_id,
    container_name,
    state,
    restart_policy,
    cpu_limit,
    memory_limit_bytes,
    privileged,
    read_only_root
)
SELECT
    'aabbcc001122',
    h.host_id,
    i.image_id,
    'web-nginx',
    'running',
    'unless-stopped',
    0.5,
    134217728,
    FALSE,
    TRUE
FROM docker_hosts h
CROSS JOIN docker_images i
WHERE h.host_name = 'docker-production-01'
  AND i.image_name = 'nginx'
  AND i.image_tag = 'alpine';

INSERT INTO docker_containers (
    external_id,
    host_id,
    image_id,
    container_name,
    state,
    restart_policy,
    cpu_limit,
    memory_limit_bytes,
    privileged,
    read_only_root
)
SELECT
    'ddeeff003344',
    h.host_id,
    i.image_id,
    'database-postgres',
    'running',
    'unless-stopped',
    1.0,
    536870912,
    FALSE,
    FALSE
FROM docker_hosts h
CROSS JOIN docker_images i
WHERE h.host_name = 'docker-production-01'
  AND i.image_name = 'postgres'
  AND i.image_tag = '16-alpine';

INSERT INTO docker_containers (
    external_id,
    host_id,
    image_id,
    container_name,
    state,
    restart_policy,
    cpu_limit,
    memory_limit_bytes,
    privileged,
    read_only_root
)
SELECT
    '112233445566',
    h.host_id,
    i.image_id,
    'unverified-app',
    'exited',
    'no',
    0.5,
    134217728,
    TRUE,
    FALSE
FROM docker_hosts h
CROSS JOIN docker_images i
WHERE h.host_name = 'docker-production-01'
  AND i.image_name = 'unverified/application';

-- ------------------------------------------------------------
-- ENVIRONMENT CONFIGURATION
-- ------------------------------------------------------------

SELECT set_container_environment(
    c.container_id,
    'APP_ENV',
    'production',
    FALSE
)
FROM docker_containers c
WHERE c.container_name = 'web-nginx';

SELECT set_container_environment(
    c.container_id,
    'APP_PORT',
    '80',
    FALSE
)
FROM docker_containers c
WHERE c.container_name = 'web-nginx';

SELECT set_container_environment(
    c.container_id,
    'POSTGRES_DB',
    'application_db',
    FALSE
)
FROM docker_containers c
WHERE c.container_name = 'database-postgres';

SELECT set_container_environment(
    c.container_id,
    'POSTGRES_PASSWORD',
    'REDACTED-DEMO-SECRET',
    TRUE
)
FROM docker_containers c
WHERE c.container_name = 'database-postgres';

-- ------------------------------------------------------------
-- SAMPLE PORT MAPPINGS
-- ------------------------------------------------------------

INSERT INTO container_ports (
    container_id,
    host_ip,
    host_port,
    container_port,
    protocol
)
SELECT
    container_id,
    '127.0.0.1',
    8080,
    80,
    'tcp'
FROM docker_containers
WHERE container_name = 'web-nginx';

INSERT INTO container_ports (
    container_id,
    host_ip,
    host_port,
    container_port,
    protocol
)
SELECT
    container_id,
    '127.0.0.1',
    5433,
    5432,
    'tcp'
FROM docker_containers
WHERE container_name = 'database-postgres';

-- ------------------------------------------------------------
-- NETWORK ATTACHMENTS
-- ------------------------------------------------------------

INSERT INTO container_network_attachments (
    container_id,
    network_id,
    ipv4_address,
    aliases
)
SELECT
    c.container_id,
    n.network_id,
    '172.25.0.10',
    ARRAY['web', 'frontend']
FROM docker_containers c
JOIN docker_networks n
    ON n.network_name = 'application-network'
JOIN docker_hosts h
    ON h.host_id = n.host_id
WHERE c.container_name = 'web-nginx'
  AND h.host_name = 'docker-production-01';

INSERT INTO container_network_attachments (
    container_id,
    network_id,
    ipv4_address,
    aliases
)
SELECT
    c.container_id,
    n.network_id,
    '172.26.0.10',
    ARRAY['database', 'postgres']
FROM docker_containers c
JOIN docker_networks n
    ON n.network_name = 'database-network'
JOIN docker_hosts h
    ON h.host_id = n.host_id
WHERE c.container_name = 'database-postgres'
  AND h.host_name = 'docker-production-01';

-- ------------------------------------------------------------
-- VOLUME ATTACHMENTS
-- ------------------------------------------------------------

INSERT INTO container_volume_mounts (
    container_id,
    volume_id,
    destination,
    read_only
)
SELECT
    c.container_id,
    v.volume_id,
    '/usr/share/nginx/html',
    TRUE
FROM docker_containers c
JOIN docker_volumes v
    ON v.volume_name = 'nginx-data'
WHERE c.container_name = 'web-nginx';

INSERT INTO container_volume_mounts (
    container_id,
    volume_id,
    destination,
    read_only
)
SELECT
    c.container_id,
    v.volume_id,
    '/var/lib/postgresql/data',
    FALSE
FROM docker_containers c
JOIN docker_volumes v
    ON v.volume_name = 'postgres-data'
WHERE c.container_name = 'database-postgres';

-- ------------------------------------------------------------
-- HEALTH CHECK HISTORY
-- ------------------------------------------------------------

INSERT INTO container_health_checks (
    container_id,
    status,
    exit_code,
    output,
    response_time_ms
)
SELECT
    container_id,
    'healthy',
    0,
    'HTTP endpoint responded successfully.',
    12
FROM docker_containers
WHERE container_name = 'web-nginx';

INSERT INTO container_health_checks (
    container_id,
    status,
    exit_code,
    output,
    response_time_ms
)
SELECT
    container_id,
    'healthy',
    0,
    'Database connection successful.',
    24
FROM docker_containers
WHERE container_name = 'database-postgres';

INSERT INTO container_health_checks (
    container_id,
    status,
    exit_code,
    output,
    response_time_ms
)
SELECT
    container_id,
    'unhealthy',
    1,
    'Container failed its startup health check.',
    0
FROM docker_containers
WHERE container_name = 'unverified-app';

-- ------------------------------------------------------------
-- DEPLOYMENT POLICIES
-- ------------------------------------------------------------

INSERT INTO deployment_policies (
    policy_name,
    allow_privileged,
    require_read_only_root,
    require_trusted_image,
    require_healthy_container,
    max_cpu,
    max_memory_bytes,
    max_published_ports
)
VALUES
(
    'production-standard',
    FALSE,
    TRUE,
    TRUE,
    TRUE,
    4.0,
    2147483648,
    10
),
(
    'development-standard',
    FALSE,
    FALSE,
    FALSE,
    FALSE,
    8.0,
    4294967296,
    20
);

-- ------------------------------------------------------------
-- DEPLOYMENT REQUESTS
-- ------------------------------------------------------------

INSERT INTO deployment_requests (
    container_id,
    policy_id,
    requested_by,
    status
)
SELECT
    c.container_id,
    p.policy_id,
    'platform-admin',
    'pending'
FROM docker_containers c
CROSS JOIN deployment_policies p
WHERE c.container_name = 'web-nginx'
  AND p.policy_name = 'production-standard';

INSERT INTO deployment_requests (
    container_id,
    policy_id,
    requested_by,
    status
)
SELECT
    c.container_id,
    p.policy_id,
    'application-team',
    'pending'
FROM docker_containers c
CROSS JOIN deployment_policies p
WHERE c.container_name = 'unverified-app'
  AND p.policy_name = 'production-standard';

-- ------------------------------------------------------------
-- PROCESS DEPLOYMENT REQUESTS
-- ------------------------------------------------------------

CALL process_deployment(
    (
        SELECT request_id
        FROM deployment_requests
        WHERE requested_by = 'platform-admin'
    )
);

CALL process_deployment(
    (
        SELECT request_id
        FROM deployment_requests
        WHERE requested_by = 'application-team'
    )
);

-- ------------------------------------------------------------
-- OPERATIONAL RETRIEVAL
-- ------------------------------------------------------------

-- Complete container inventory.
SELECT *
FROM container_inventory
ORDER BY host_name, container_name;

-- Running containers only.
SELECT *
FROM container_inventory
WHERE state = 'running';

-- Container configuration without exposing sensitive values.
SELECT
    c.container_name,
    e.variable_name,
    CASE
        WHEN e.is_sensitive THEN '[REDACTED]'
        ELSE e.variable_value
    END AS displayed_value,
    e.is_sensitive
FROM docker_containers c
JOIN container_environment e
    ON e.container_id = c.container_id
ORDER BY c.container_name, e.variable_name;

-- Network topology.
SELECT *
FROM container_network_inventory
ORDER BY network_name, container_name;

-- Volume utilization and attachment count.
SELECT
    v.volume_name,
    v.volume_kind,
    COUNT(m.mount_id) AS mount_count,
    STRING_AGG(c.container_name, ', ') AS attached_containers
FROM docker_volumes v
LEFT JOIN container_volume_mounts m
    ON m.volume_id = v.volume_id
LEFT JOIN docker_containers c
    ON c.container_id = m.container_id
GROUP BY
    v.volume_id,
    v.volume_name,
    v.volume_kind;

-- Latest health results.
SELECT *
FROM container_health_inventory
ORDER BY container_name;

-- Host resource allocation.
SELECT
    host_name,
    total_cpu_cores,
    allocated_cpu,
    ROUND(
        allocated_cpu / NULLIF(total_cpu_cores, 0) * 100,
        2
    ) AS cpu_allocation_percentage,
    ROUND(total_memory_bytes / 1048576.0, 2)
        AS total_memory_mb,
    ROUND(allocated_memory / 1048576.0, 2)
        AS allocated_memory_mb
FROM host_resource_inventory;

-- Lifecycle event history.
SELECT
    c.container_name,
    e.previous_state,
    e.new_state,
    e.event_reason,
    e.actor,
    e.event_time
FROM container_lifecycle_events e
JOIN docker_containers c
    ON c.container_id = e.container_id
ORDER BY e.event_time DESC;

-- Deployment decisions.
SELECT
    dr.request_id,
    c.container_name,
    p.policy_name,
    dr.requested_by,
    dr.status,
    dr.decision_reason,
    dr.decided_at
FROM deployment_requests dr
JOIN docker_containers c
    ON c.container_id = dr.container_id
JOIN deployment_policies p
    ON p.policy_id = dr.policy_id
ORDER BY dr.request_id;

-- ------------------------------------------------------------
-- AGGREGATION AND OPERATIONAL REPORTING
-- ------------------------------------------------------------

-- Container counts by state.
SELECT
    state,
    COUNT(*) AS container_count
FROM docker_containers
GROUP BY state
ORDER BY state;

-- Image usage.
SELECT
    i.image_name,
    i.image_tag,
    COUNT(c.container_id) AS container_count
FROM docker_images i
LEFT JOIN docker_containers c
    ON c.image_id = i.image_id
GROUP BY i.image_id, i.image_name, i.image_tag
ORDER BY container_count DESC;

-- Deployment approval statistics.
SELECT
    status,
    COUNT(*) AS request_count
FROM deployment_requests
GROUP BY status
ORDER BY status;

-- Containers without an assigned network.
SELECT
    c.container_name
FROM docker_containers c
WHERE NOT EXISTS (
    SELECT 1
    FROM container_network_attachments a
    WHERE a.container_id = c.container_id
);

-- Containers exceeding host CPU allocation.
WITH allocation AS (
    SELECT
        h.host_id,
        h.host_name,
        h.total_cpu_cores,
        SUM(
            CASE WHEN c.state = 'running'
                THEN c.cpu_limit
                ELSE 0
            END
        ) AS allocated_cpu
    FROM docker_hosts h
    LEFT JOIN docker_containers c
        ON c.host_id = h.host_id
    GROUP BY
        h.host_id,
        h.host_name,
        h.total_cpu_cores
)
SELECT *
FROM allocation
WHERE allocated_cpu > total_cpu_cores;

-- ------------------------------------------------------------
-- TRANSACTIONAL LIFECYCLE DEMONSTRATION
-- ------------------------------------------------------------

-- This transaction changes a container's state and records
-- the transition through the lifecycle trigger.

BEGIN;

UPDATE docker_containers
SET state = 'exited'
WHERE container_name = 'web-nginx'
  AND state = 'running';

COMMIT;

-- Restarting an exited container.
BEGIN;

UPDATE docker_containers
SET state = 'running'
WHERE container_name = 'web-nginx'
  AND state = 'exited';

COMMIT;

-- ------------------------------------------------------------
-- CTE: DEPLOYMENT READINESS REPORT
-- ------------------------------------------------------------

WITH latest_health AS (
    SELECT DISTINCT ON (container_id)
        container_id,
        status,
        checked_at
    FROM container_health_checks
    ORDER BY
        container_id,
        checked_at DESC,
        health_check_id DESC
),
port_counts AS (
    SELECT
        container_id,
        COUNT(*) AS published_ports
    FROM container_ports
    GROUP BY container_id
)
SELECT
    c.container_name,
    c.state,
    COALESCE(h.status, 'not-configured') AS health,
    COALESCE(p.published_ports, 0) AS published_ports,
    CASE
        WHEN c.state <> 'running'
            THEN 'NOT_RUNNING'
        WHEN h.status IS DISTINCT FROM 'healthy'
            THEN 'HEALTH_CHECK_REQUIRED'
        ELSE 'READY'
    END AS readiness
FROM docker_containers c
LEFT JOIN latest_health h
    ON h.container_id = c.container_id
LEFT JOIN port_counts p
    ON p.container_id = c.container_id
ORDER BY c.container_name;

-- ------------------------------------------------------------
-- DATABASE MAINTENANCE AND SECURITY NOTES
-- ------------------------------------------------------------

-- Sensitive environment variables should not be exposed
-- through general-purpose application roles.
--
-- Production deployments should:
-- 1. Use dedicated PostgreSQL roles.
-- 2. Restrict direct access to environment tables.
-- 3. Use external secret-management systems.
-- 4. Encrypt database connections.
-- 5. Retain lifecycle audit events.
-- 6. Apply retention policies to health-check history.
-- 7. Validate actual Docker Engine state independently.
--
-- Example role-level access restriction:
--
-- REVOKE ALL ON container_environment FROM PUBLIC;
-- REVOKE ALL ON deployment_requests FROM PUBLIC;
--
-- A dedicated application role should receive only the
-- minimum SELECT or EXECUTE permissions required.

COMMIT;
