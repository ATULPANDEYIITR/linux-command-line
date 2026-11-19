-- ============================================================
-- DOCKER NETWORKING MANAGEMENT AND GOVERNANCE DATABASE
-- PostgreSQL 15+
--
-- Models:
-- 1. Docker hosts and repositories
-- 2. Bridge, host, and none networking modes
-- 3. Networks, subnets, gateways, and memberships
-- 4. Containers and container IP assignments
-- 5. Port publishing and protocol validation
-- 6. Network-scoped service discovery
-- 7. Network isolation and connectivity policies
-- 8. Network events and audit records
-- 9. Connectivity evaluation and reporting
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS docker_networking;

SET search_path TO docker_networking, public;

-- ------------------------------------------------------------
-- ENUMERATED DOMAIN TYPES
-- ------------------------------------------------------------

CREATE TYPE network_mode AS ENUM (
    'bridge',
    'host',
    'none'
);

CREATE TYPE network_driver AS ENUM (
    'bridge',
    'host',
    'overlay',
    'macvlan',
    'ipvlan',
    'none'
);

CREATE TYPE container_state AS ENUM (
    'created',
    'running',
    'stopped',
    'paused',
    'removed'
);

CREATE TYPE network_protocol AS ENUM (
    'tcp',
    'udp',
    'sctp'
);

CREATE TYPE network_event_type AS ENUM (
    'network_created',
    'network_deleted',
    'container_created',
    'container_started',
    'container_stopped',
    'container_connected',
    'container_disconnected',
    'port_published',
    'port_removed',
    'connectivity_allowed',
    'connectivity_denied',
    'policy_changed'
);

-- ------------------------------------------------------------
-- DOCKER HOSTS
-- ------------------------------------------------------------

CREATE TABLE docker_hosts (
    host_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    hostname VARCHAR(150) NOT NULL UNIQUE,

    operating_system VARCHAR(100) NOT NULL,

    docker_version VARCHAR(50) NOT NULL,

    management_address INET NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- NETWORK DEFINITIONS
-- ------------------------------------------------------------

CREATE TABLE networks (
    network_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    host_id BIGINT NOT NULL REFERENCES docker_hosts(host_id),

    network_name VARCHAR(100) NOT NULL,

    driver network_driver NOT NULL DEFAULT 'bridge',

    subnet CIDR,

    gateway INET,

    internal BOOLEAN NOT NULL DEFAULT FALSE,

    attachable BOOLEAN NOT NULL DEFAULT TRUE,

    enable_ipv6 BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (host_id, network_name),

    CHECK (
        subnet IS NULL
        OR family(subnet) = 4
    ),

    CHECK (
        gateway IS NULL
        OR family(gateway) = 4
    ),

    CHECK (
        gateway IS NULL
        OR subnet IS NULL
        OR gateway <<= subnet
    ),

    CHECK (
        driver = 'bridge'
        OR subnet IS NULL
        OR driver IN ('overlay', 'macvlan', 'ipvlan')
    )
);

CREATE INDEX idx_network_host_driver
    ON networks(host_id, driver);

CREATE INDEX idx_network_internal
    ON networks(internal);

-- ------------------------------------------------------------
-- CONTAINERS
-- ------------------------------------------------------------

CREATE TABLE containers (
    container_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    host_id BIGINT NOT NULL REFERENCES docker_hosts(host_id),

    container_name VARCHAR(100) NOT NULL,

    image_name VARCHAR(255) NOT NULL,

    mode network_mode NOT NULL DEFAULT 'bridge',

    state container_state NOT NULL DEFAULT 'created',

    started_at TIMESTAMPTZ,

    stopped_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (host_id, container_name),

    CHECK (
        started_at IS NULL
        OR stopped_at IS NULL
        OR stopped_at >= started_at
    )
);

CREATE INDEX idx_containers_host_state
    ON containers(host_id, state);

CREATE INDEX idx_containers_mode
    ON containers(mode);

-- ------------------------------------------------------------
-- NETWORK MEMBERSHIP
-- ------------------------------------------------------------

CREATE TABLE network_memberships (
    membership_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    network_id BIGINT NOT NULL REFERENCES networks(network_id),

    container_id BIGINT NOT NULL REFERENCES containers(container_id),

    ipv4_address INET,

    ipv6_address INET,

    aliases TEXT[] NOT NULL DEFAULT '{}',

    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    disconnected_at TIMESTAMPTZ,

    UNIQUE (network_id, container_id),

    CHECK (
        ipv4_address IS NULL
        OR family(ipv4_address) = 4
    ),

    CHECK (
        ipv6_address IS NULL
        OR family(ipv6_address) = 6
    ),

    CHECK (
        disconnected_at IS NULL
        OR disconnected_at >= connected_at
    )
);

CREATE UNIQUE INDEX uq_network_ipv4
    ON network_memberships(network_id, ipv4_address)
    WHERE ipv4_address IS NOT NULL
      AND disconnected_at IS NULL;

CREATE INDEX idx_membership_container
    ON network_memberships(container_id);

CREATE INDEX idx_membership_network_active
    ON network_memberships(network_id)
    WHERE disconnected_at IS NULL;

-- ------------------------------------------------------------
-- CONTAINER EXPOSED PORTS
-- ------------------------------------------------------------

CREATE TABLE exposed_ports (
    exposed_port_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    container_id BIGINT NOT NULL REFERENCES containers(container_id),

    container_port INTEGER NOT NULL
        CHECK (container_port BETWEEN 1 AND 65535),

    protocol network_protocol NOT NULL DEFAULT 'tcp',

    description VARCHAR(255),

    UNIQUE (container_id, container_port, protocol)
);

CREATE INDEX idx_exposed_container_port
    ON exposed_ports(container_id, container_port);

-- ------------------------------------------------------------
-- PUBLISHED HOST PORTS
-- ------------------------------------------------------------

CREATE TABLE published_ports (
    published_port_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    host_id BIGINT NOT NULL REFERENCES docker_hosts(host_id),

    container_id BIGINT NOT NULL REFERENCES containers(container_id),

    host_ip INET NOT NULL DEFAULT '0.0.0.0',

    host_port INTEGER NOT NULL
        CHECK (host_port BETWEEN 1 AND 65535),

    container_port INTEGER NOT NULL
        CHECK (container_port BETWEEN 1 AND 65535),

    protocol network_protocol NOT NULL DEFAULT 'tcp',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        host_id,
        host_ip,
        host_port,
        protocol
    )
);

CREATE INDEX idx_published_container
    ON published_ports(container_id);

CREATE INDEX idx_published_host_port
    ON published_ports(host_id, host_port);

-- ------------------------------------------------------------
-- NETWORK GOVERNANCE POLICIES
-- ------------------------------------------------------------

CREATE TABLE network_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    network_id BIGINT NOT NULL REFERENCES networks(network_id),

    policy_name VARCHAR(120) NOT NULL,

    allow_outbound BOOLEAN NOT NULL DEFAULT TRUE,

    allow_inbound BOOLEAN NOT NULL DEFAULT TRUE,

    allow_inter_network BOOLEAN NOT NULL DEFAULT FALSE,

    allow_host_access BOOLEAN NOT NULL DEFAULT FALSE,

    allow_external_access BOOLEAN NOT NULL DEFAULT FALSE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (network_id, policy_name)
);

CREATE INDEX idx_policy_enabled
    ON network_policies(network_id, enabled);

-- ------------------------------------------------------------
-- CONNECTIVITY DECISIONS
-- ------------------------------------------------------------

CREATE TABLE connectivity_decisions (
    decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source_container_id BIGINT NOT NULL
        REFERENCES containers(container_id),

    target_container_id BIGINT NOT NULL
        REFERENCES containers(container_id),

    destination_port INTEGER NOT NULL
        CHECK (destination_port BETWEEN 1 AND 65535),

    protocol network_protocol NOT NULL DEFAULT 'tcp',

    decision VARCHAR(10) NOT NULL
        CHECK (decision IN ('allow', 'deny')),

    reason TEXT NOT NULL,

    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_connectivity_source_time
    ON connectivity_decisions(
        source_container_id,
        evaluated_at DESC
    );

CREATE INDEX idx_connectivity_target
    ON connectivity_decisions(target_container_id, decision);

-- ------------------------------------------------------------
-- NETWORK EVENTS
-- ------------------------------------------------------------

CREATE TABLE network_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    host_id BIGINT REFERENCES docker_hosts(host_id),

    network_id BIGINT REFERENCES networks(network_id),

    container_id BIGINT REFERENCES containers(container_id),

    event_type network_event_type NOT NULL,

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_network_events_time
    ON network_events(occurred_at DESC);

CREATE INDEX idx_network_events_type
    ON network_events(event_type, occurred_at DESC);

CREATE INDEX idx_network_events_details
    ON network_events USING GIN(event_details);

-- ------------------------------------------------------------
-- FUNCTION: VALIDATE CONTAINER NETWORK MEMBERSHIP
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_network_membership()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_mode network_mode;
    v_state container_state;
    v_driver network_driver;
    v_network_subnet CIDR;
    v_network_host BIGINT;
    v_container_host BIGINT;
BEGIN
    SELECT mode, state, host_id
    INTO v_mode, v_state, v_container_host
    FROM containers
    WHERE container_id = NEW.container_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Container does not exist.';
    END IF;

    SELECT driver, subnet, host_id
    INTO v_driver, v_network_subnet, v_network_host
    FROM networks
    WHERE network_id = NEW.network_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Network does not exist.';
    END IF;

    IF v_mode <> 'bridge' THEN
        RAISE EXCEPTION
            'Host and none containers cannot join bridge memberships.';
    END IF;

    IF v_state = 'removed' THEN
        RAISE EXCEPTION 'Removed containers cannot join networks.';
    END IF;

    IF v_driver <> 'bridge' THEN
        RAISE EXCEPTION
            'This membership model supports bridge networks only.';
    END IF;

    IF v_container_host <> v_network_host THEN
        RAISE EXCEPTION
            'Container and bridge network must belong to the same host.';
    END IF;

    IF NEW.ipv4_address IS NOT NULL THEN
        IF v_network_subnet IS NULL THEN
            RAISE EXCEPTION 'Network has no IPv4 subnet.';
        END IF;

        IF NOT (NEW.ipv4_address <<= v_network_subnet) THEN
            RAISE EXCEPTION
                'Container IP is outside the network subnet.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_network_membership
BEFORE INSERT OR UPDATE
ON network_memberships
FOR EACH ROW
EXECUTE FUNCTION validate_network_membership();

-- ------------------------------------------------------------
-- FUNCTION: VALIDATE PORT PUBLISHING
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_published_port()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_mode network_mode;
    v_state container_state;
    v_host BIGINT;
    v_exposed BOOLEAN;
BEGIN
    SELECT mode, state, host_id
    INTO v_mode, v_state, v_host
    FROM containers
    WHERE container_id = NEW.container_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Container not found.';
    END IF;

    IF v_mode <> 'bridge' THEN
        RAISE EXCEPTION
            'Port publishing is not permitted for host or none mode.';
    END IF;

    IF v_state <> 'running' THEN
        RAISE EXCEPTION
            'Ports can only be published for running containers.';
    END IF;

    IF v_host <> NEW.host_id THEN
        RAISE EXCEPTION
            'Container and published host do not match.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM exposed_ports
        WHERE container_id = NEW.container_id
          AND container_port = NEW.container_port
          AND protocol = NEW.protocol
    )
    INTO v_exposed;

    IF NOT v_exposed THEN
        RAISE EXCEPTION
            'Destination port must exist in exposed_ports.';
    END IF;

    -- Wildcard address conflicts with every specific host address.
    IF EXISTS (
        SELECT 1
        FROM published_ports p
        WHERE p.host_id = NEW.host_id
          AND p.protocol = NEW.protocol
          AND p.host_port = NEW.host_port
          AND p.published_port_id
              <> COALESCE(NEW.published_port_id, -1)
          AND (
              p.host_ip = '0.0.0.0'::INET
              OR NEW.host_ip = '0.0.0.0'::INET
              OR p.host_ip = NEW.host_ip
          )
    ) THEN
        RAISE EXCEPTION 'Host port binding conflict.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_published_port
BEFORE INSERT OR UPDATE
ON published_ports
FOR EACH ROW
EXECUTE FUNCTION validate_published_port();

-- ------------------------------------------------------------
-- FUNCTION: RECORD NETWORK EVENTS
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION record_container_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO network_events (
            host_id,
            container_id,
            event_type,
            event_details
        )
        VALUES (
            NEW.host_id,
            NEW.container_id,
            'container_created',
            jsonb_build_object(
                'name', NEW.container_name,
                'mode', NEW.mode,
                'state', NEW.state
            )
        );

    ELSIF NEW.state IS DISTINCT FROM OLD.state THEN
        INSERT INTO network_events (
            host_id,
            container_id,
            event_type,
            event_details
        )
        VALUES (
            NEW.host_id,
            NEW.container_id,
            CASE
                WHEN NEW.state = 'running'
                    THEN 'container_started'::network_event_type
                WHEN NEW.state = 'stopped'
                    THEN 'container_stopped'::network_event_type
                ELSE 'container_created'::network_event_type
            END,
            jsonb_build_object(
                'previous_state', OLD.state,
                'new_state', NEW.state
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_container_event
AFTER INSERT OR UPDATE OF state
ON containers
FOR EACH ROW
EXECUTE FUNCTION record_container_event();

-- ------------------------------------------------------------
-- FUNCTION: EVALUATE BRIDGE CONNECTIVITY
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION evaluate_connectivity(
    p_source BIGINT,
    p_target BIGINT,
    p_port INTEGER,
    p_protocol network_protocol DEFAULT 'tcp'
)
RETURNS TABLE (
    allowed BOOLEAN,
    decision_reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source containers%ROWTYPE;
    v_target containers%ROWTYPE;
    v_shared BOOLEAN;
    v_exposed BOOLEAN;
    v_source_internal BOOLEAN;
    v_target_internal BOOLEAN;
BEGIN
    IF p_port < 1 OR p_port > 65535 THEN
        RAISE EXCEPTION 'Invalid destination port.';
    END IF;

    SELECT *
    INTO v_source
    FROM containers
    WHERE container_id = p_source;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source container not found.';
    END IF;

    SELECT *
    INTO v_target
    FROM containers
    WHERE container_id = p_target;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Target container not found.';
    END IF;

    IF v_source.state <> 'running'
       OR v_target.state <> 'running' THEN

        RETURN QUERY
        SELECT FALSE, 'One or both containers are not running.';
        RETURN;
    END IF;

    IF p_source = p_target THEN
        RETURN QUERY
        SELECT TRUE, 'Same container.';
        RETURN;
    END IF;

    IF v_source.mode = 'none'
       OR v_target.mode = 'none' THEN

        RETURN QUERY
        SELECT FALSE, 'None networking prevents communication.';
        RETURN;
    END IF;

    IF v_source.mode = 'host'
       AND v_target.mode = 'host' THEN

        RETURN QUERY
        SELECT TRUE, 'Shared host network namespace.';
        RETURN;
    END IF;

    IF v_source.mode <> 'bridge'
       OR v_target.mode <> 'bridge' THEN

        RETURN QUERY
        SELECT FALSE, 'No supported bridge communication path.';
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM network_memberships sm
        JOIN network_memberships tm
          ON tm.network_id = sm.network_id
        JOIN networks n
          ON n.network_id = sm.network_id
        WHERE sm.container_id = p_source
          AND tm.container_id = p_target
          AND sm.disconnected_at IS NULL
          AND tm.disconnected_at IS NULL
          AND n.driver = 'bridge'
    )
    INTO v_shared;

    SELECT EXISTS (
        SELECT 1
        FROM exposed_ports
        WHERE container_id = p_target
          AND container_port = p_port
          AND protocol = p_protocol
    )
    INTO v_exposed;

    IF v_shared AND v_exposed THEN
        RETURN QUERY
        SELECT TRUE, 'Shared bridge network and exposed port.';
    ELSE
        RETURN QUERY
        SELECT FALSE,
            CASE
                WHEN NOT v_shared
                    THEN 'Network isolation: no shared bridge network.'
                ELSE 'Destination port is not exposed.'
            END;
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- FUNCTION: RECORD CONNECTIVITY DECISION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION record_connectivity_decision(
    p_source BIGINT,
    p_target BIGINT,
    p_port INTEGER,
    p_protocol network_protocol DEFAULT 'tcp'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_allowed BOOLEAN;
    v_reason TEXT;
    v_decision_id BIGINT;
BEGIN
    SELECT allowed, decision_reason
    INTO v_allowed, v_reason
    FROM evaluate_connectivity(
        p_source,
        p_target,
        p_port,
        p_protocol
    );

    INSERT INTO connectivity_decisions (
        source_container_id,
        target_container_id,
        destination_port,
        protocol,
        decision,
        reason
    )
    VALUES (
        p_source,
        p_target,
        p_port,
        p_protocol,
        CASE WHEN v_allowed THEN 'allow' ELSE 'deny' END,
        v_reason
    )
    RETURNING decision_id INTO v_decision_id;

    INSERT INTO network_events (
        container_id,
        event_type,
        event_details
    )
    VALUES (
        p_source,
        CASE
            WHEN v_allowed
                THEN 'connectivity_allowed'::network_event_type
            ELSE 'connectivity_denied'::network_event_type
        END,
        jsonb_build_object(
            'target_container_id', p_target,
            'port', p_port,
            'protocol', p_protocol,
            'reason', v_reason
        )
    );

    RETURN v_decision_id;
END;
$$;

-- ------------------------------------------------------------
-- VIEW: ACTIVE NETWORK TOPOLOGY
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW active_network_topology AS
SELECT
    h.hostname,
    n.network_name,
    n.driver,
    n.subnet,
    n.gateway,
    n.internal,
    c.container_name,
    c.image_name,
    c.mode,
    c.state,
    m.ipv4_address,
    m.ipv6_address,
    m.aliases
FROM networks n
JOIN docker_hosts h
    ON h.host_id = n.host_id
JOIN network_memberships m
    ON m.network_id = n.network_id
JOIN containers c
    ON c.container_id = m.container_id
WHERE m.disconnected_at IS NULL
  AND c.state <> 'removed';

-- ------------------------------------------------------------
-- VIEW: PORT PUBLISHING INVENTORY
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW published_port_inventory AS
SELECT
    h.hostname,
    c.container_name,
    p.host_ip,
    p.host_port,
    p.container_port,
    p.protocol,
    c.state
FROM published_ports p
JOIN docker_hosts h
    ON h.host_id = p.host_id
JOIN containers c
    ON c.container_id = p.container_id;

-- ------------------------------------------------------------
-- VIEW: NETWORK CONNECTIVITY REPORT
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW connectivity_report AS
SELECT
    decision,
    protocol,
    COUNT(*) AS total_decisions,
    COUNT(DISTINCT source_container_id) AS source_containers,
    COUNT(DISTINCT target_container_id) AS destination_containers,
    MAX(evaluated_at) AS last_evaluation
FROM connectivity_decisions
GROUP BY decision, protocol;

-- ------------------------------------------------------------
-- SAMPLE DATA
-- ------------------------------------------------------------

INSERT INTO docker_hosts (
    hostname,
    operating_system,
    docker_version,
    management_address
)
VALUES
(
    'docker-node-01',
    'Ubuntu 24.04',
    '28.0.0',
    '192.168.1.10'
),
(
    'docker-node-02',
    'Ubuntu 24.04',
    '28.0.0',
    '192.168.1.11'
);

INSERT INTO networks (
    host_id,
    network_name,
    driver,
    subnet,
    gateway,
    internal
)
SELECT
    host_id,
    'frontend-net',
    'bridge',
    '172.20.0.0/24',
    '172.20.0.1',
    FALSE
FROM docker_hosts
WHERE hostname = 'docker-node-01';

INSERT INTO networks (
    host_id,
    network_name,
    driver,
    subnet,
    gateway,
    internal
)
SELECT
    host_id,
    'backend-net',
    'bridge',
    '172.21.0.0/24',
    '172.21.0.1',
    TRUE
FROM docker_hosts
WHERE hostname = 'docker-node-01';

INSERT INTO networks (
    host_id,
    network_name,
    driver,
    subnet,
    gateway,
    internal
)
SELECT
    host_id,
    'isolated-test-net',
    'bridge',
    '172.22.0.0/24',
    '172.22.0.1',
    TRUE
FROM docker_hosts
WHERE hostname = 'docker-node-01';

INSERT INTO containers (
    host_id,
    container_name,
    image_name,
    mode,
    state,
    started_at
)
SELECT
    host_id,
    'frontend',
    'nginx:stable',
    'bridge',
    'running',
    NOW()
FROM docker_hosts
WHERE hostname = 'docker-node-01';

INSERT INTO containers (
    host_id,
    container_name,
    image_name,
    mode,
    state,
    started_at
)
SELECT
    host_id,
    'api',
    'python:3.13-slim',
    'bridge',
    'running',
    NOW()
FROM docker_hosts
WHERE hostname = 'docker-node-01';

INSERT INTO containers (
    host_id,
    container_name,
    image_name,
    mode,
    state,
    started_at
)
SELECT
    host_id,
    'database',
    'postgres:18',
    'bridge',
    'running',
    NOW()
FROM docker_hosts
WHERE hostname = 'docker-node-01';

INSERT INTO containers (
    host_id,
    container_name,
    image_name,
    mode,
    state,
    started_at
)
SELECT
    host_id,
    'host-monitor',
    'monitor:latest',
    'host',
    'running',
    NOW()
FROM docker_hosts
WHERE hostname = 'docker-node-01';

INSERT INTO containers (
    host_id,
    container_name,
    image_name,
    mode,
    state,
    started_at
)
SELECT
    host_id,
    'isolated-worker',
    'python:3.13-slim',
    'bridge',
    'running',
    NOW()
FROM docker_hosts
WHERE hostname = 'docker-node-01';

-- Frontend belongs to frontend-net.
INSERT INTO network_memberships (
    network_id,
    container_id,
    ipv4_address,
    aliases
)
SELECT
    n.network_id,
    c.container_id,
    '172.20.0.10',
    ARRAY['web', 'frontend-service']
FROM networks n
JOIN containers c
    ON c.container_name = 'frontend'
WHERE n.network_name = 'frontend-net';

-- API belongs to frontend-net and backend-net.
INSERT INTO network_memberships (
    network_id,
    container_id,
    ipv4_address,
    aliases
)
SELECT
    n.network_id,
    c.container_id,
    '172.20.0.11',
    ARRAY['api-service']
FROM networks n
JOIN containers c
    ON c.container_name = 'api'
WHERE n.network_name = 'frontend-net';

INSERT INTO network_memberships (
    network_id,
    container_id,
    ipv4_address,
    aliases
)
SELECT
    n.network_id,
    c.container_id,
    '172.21.0.10',
    ARRAY['api-backend']
FROM networks n
JOIN containers c
    ON c.container_name = 'api'
WHERE n.network_name = 'backend-net';

-- Database belongs only to backend-net.
INSERT INTO network_memberships (
    network_id,
    container_id,
    ipv4_address,
    aliases
)
SELECT
    n.network_id,
    c.container_id,
    '172.21.0.11',
    ARRAY['database', 'postgres']
FROM networks n
JOIN containers c
    ON c.container_name = 'database'
WHERE n.network_name = 'backend-net';

-- Isolated worker has its own network.
INSERT INTO network_memberships (
    network_id,
    container_id,
    ipv4_address
)
SELECT
    n.network_id,
    c.container_id,
    '172.22.0.10'
FROM networks n
JOIN containers c
    ON c.container_name = 'isolated-worker'
WHERE n.network_name = 'isolated-test-net';

-- Host-mode containers have no bridge membership.

INSERT INTO exposed_ports (
    container_id,
    container_port,
    protocol,
    description
)
SELECT container_id, 80, 'tcp', 'HTTP frontend'
FROM containers
WHERE container_name = 'frontend';

INSERT INTO exposed_ports (
    container_id,
    container_port,
    protocol,
    description
)
SELECT container_id, 8000, 'tcp', 'API endpoint'
FROM containers
WHERE container_name = 'api';

INSERT INTO exposed_ports (
    container_id,
    container_port,
    protocol,
    description
)
SELECT container_id, 5432, 'tcp', 'PostgreSQL database'
FROM containers
WHERE container_name = 'database';

INSERT INTO exposed_ports (
    container_id,
    container_port,
    protocol,
    description
)
SELECT container_id, 9090, 'tcp', 'Host monitoring'
FROM containers
WHERE container_name = 'host-monitor';

-- ------------------------------------------------------------
-- PORT PUBLISHING
-- ------------------------------------------------------------

INSERT INTO published_ports (
    host_id,
    container_id,
    host_ip,
    host_port,
    container_port,
    protocol
)
SELECT
    h.host_id,
    c.container_id,
    '127.0.0.1',
    8080,
    80,
    'tcp'
FROM docker_hosts h
JOIN containers c
    ON c.host_id = h.host_id
WHERE h.hostname = 'docker-node-01'
  AND c.container_name = 'frontend';

-- ------------------------------------------------------------
-- NETWORK POLICY CONFIGURATION
-- ------------------------------------------------------------

INSERT INTO network_policies (
    network_id,
    policy_name,
    allow_outbound,
    allow_inbound,
    allow_inter_network,
    allow_host_access,
    allow_external_access
)
SELECT
    network_id,
    'frontend-default',
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    TRUE
FROM networks
WHERE network_name = 'frontend-net';

INSERT INTO network_policies (
    network_id,
    policy_name,
    allow_outbound,
    allow_inbound,
    allow_inter_network,
    allow_host_access,
    allow_external_access
)
SELECT
    network_id,
    'backend-restricted',
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    FALSE
FROM networks
WHERE network_name = 'backend-net';

INSERT INTO network_policies (
    network_id,
    policy_name,
    allow_outbound,
    allow_inbound,
    allow_inter_network,
    allow_host_access,
    allow_external_access
)
SELECT
    network_id,
    'isolated-default',
    FALSE,
    FALSE,
    FALSE,
    FALSE,
    FALSE
FROM networks
WHERE network_name = 'isolated-test-net';

-- ------------------------------------------------------------
-- TRANSACTIONAL CONNECTIVITY EVALUATION
-- ------------------------------------------------------------

DO $$
DECLARE
    v_frontend BIGINT;
    v_api BIGINT;
    v_database BIGINT;
    v_worker BIGINT;
BEGIN
    SELECT container_id INTO STRICT v_frontend
    FROM containers
    WHERE container_name = 'frontend';

    SELECT container_id INTO STRICT v_api
    FROM containers
    WHERE container_name = 'api';

    SELECT container_id INTO STRICT v_database
    FROM containers
    WHERE container_name = 'database';

    SELECT container_id INTO STRICT v_worker
    FROM containers
    WHERE container_name = 'isolated-worker';

    -- Frontend -> API: shared frontend network.
    PERFORM record_connectivity_decision(
        v_frontend,
        v_api,
        8000,
        'tcp'
    );

    -- API -> Database: shared backend network.
    PERFORM record_connectivity_decision(
        v_api,
        v_database,
        5432,
        'tcp'
    );

    -- Frontend -> Database: no shared network.
    PERFORM record_connectivity_decision(
        v_frontend,
        v_database,
        5432,
        'tcp'
    );

    -- API -> Isolated worker: no shared network.
    PERFORM record_connectivity_decision(
        v_api,
        v_worker,
        8000,
        'tcp'
    );
END;
$$;

COMMIT;

-- ============================================================
-- OPERATIONAL QUERIES
-- ============================================================

-- 1. Retrieve complete active topology.
SELECT *
FROM active_network_topology
ORDER BY network_name, container_name;

-- 2. Retrieve all networks and their configurations.
SELECT
    hostname,
    network_name,
    driver,
    subnet,
    gateway,
    internal
FROM networks n
JOIN docker_hosts h USING (host_id)
ORDER BY hostname, network_name;

-- 3. Retrieve network memberships.
SELECT
    n.network_name,
    c.container_name,
    m.ipv4_address,
    m.aliases,
    m.connected_at
FROM network_memberships m
JOIN networks n USING (network_id)
JOIN containers c USING (container_id)
WHERE m.disconnected_at IS NULL
ORDER BY n.network_name, c.container_name;

-- 4. Retrieve published ports.
SELECT *
FROM published_port_inventory
ORDER BY hostname, host_port;

-- 5. Retrieve exposed ports.
SELECT
    c.container_name,
    e.container_port,
    e.protocol,
    e.description
FROM exposed_ports e
JOIN containers c USING (container_id)
ORDER BY c.container_name, e.container_port;

-- 6. Aggregate container counts by network mode.
SELECT
    mode,
    state,
    COUNT(*) AS container_count
FROM containers
GROUP BY mode, state
ORDER BY mode, state;

-- 7. Aggregate membership by network.
SELECT
    n.network_name,
    COUNT(m.membership_id) FILTER (
        WHERE m.disconnected_at IS NULL
    ) AS active_members
FROM networks n
LEFT JOIN network_memberships m USING (network_id)
GROUP BY n.network_id, n.network_name
ORDER BY active_members DESC;

-- 8. Evaluate individual connectivity without recording it.
SELECT *
FROM evaluate_connectivity(
    (SELECT container_id FROM containers
     WHERE container_name = 'frontend'),
    (SELECT container_id FROM containers
     WHERE container_name = 'api'),
    8000,
    'tcp'
);

-- 9. Evaluate frontend-to-database isolation.
SELECT *
FROM evaluate_connectivity(
    (SELECT container_id FROM containers
     WHERE container_name = 'frontend'),
    (SELECT container_id FROM containers
     WHERE container_name = 'database'),
    5432,
    'tcp'
);

-- 10. Review historical connectivity decisions.
SELECT
    s.container_name AS source,
    t.container_name AS destination,
    d.destination_port,
    d.protocol,
    d.decision,
    d.reason,
    d.evaluated_at
FROM connectivity_decisions d
JOIN containers s
    ON s.container_id = d.source_container_id
JOIN containers t
    ON t.container_id = d.target_container_id
ORDER BY d.evaluated_at DESC;

-- 11. Aggregate connectivity results.
SELECT *
FROM connectivity_report;

-- 12. Inspect denied connectivity attempts.
SELECT
    s.container_name AS source,
    t.container_name AS destination,
    d.destination_port,
    d.reason,
    d.evaluated_at
FROM connectivity_decisions d
JOIN containers s
    ON s.container_id = d.source_container_id
JOIN containers t
    ON t.container_id = d.target_container_id
WHERE d.decision = 'deny'
ORDER BY d.evaluated_at DESC;

-- 13. Inspect network event history.
SELECT
    event_id,
    event_type,
    event_details,
    occurred_at
FROM network_events
ORDER BY occurred_at DESC;

-- 14. Inspect active network policies.
SELECT
    n.network_name,
    p.policy_name,
    p.allow_outbound,
    p.allow_inbound,
    p.allow_inter_network,
    p.allow_host_access,
    p.allow_external_access
FROM network_policies p
JOIN networks n USING (network_id)
WHERE p.enabled = TRUE;

-- 15. Identify containers without active bridge membership.
SELECT
    c.container_name,
    c.mode,
    c.state
FROM containers c
WHERE c.mode = 'bridge'
  AND c.state <> 'removed'
  AND NOT EXISTS (
      SELECT 1
      FROM network_memberships m
      WHERE m.container_id = c.container_id
        AND m.disconnected_at IS NULL
  );

-- 16. Identify internal networks and external port exposure.
SELECT
    n.network_name,
    n.internal,
    c.container_name,
    p.host_ip,
    p.host_port,
    p.container_port
FROM networks n
JOIN network_memberships m USING (network_id)
JOIN containers c USING (container_id)
LEFT JOIN published_ports p
    ON p.container_id = c.container_id
WHERE n.internal = TRUE
  AND m.disconnected_at IS NULL;

-- 17. Identify port conflicts by host and protocol.
SELECT
    host_id,
    host_port,
    protocol,
    COUNT(*) AS mapping_count
FROM published_ports
GROUP BY host_id, host_port, protocol
HAVING COUNT(*) > 1;

-- 18. Retrieve service discovery aliases.
SELECT
    n.network_name,
    unnest(m.aliases) AS service_alias,
    c.container_name,
    m.ipv4_address
FROM network_memberships m
JOIN networks n USING (network_id)
JOIN containers c USING (container_id)
WHERE m.disconnected_at IS NULL;

-- 19. Inspect network event counts by category.
SELECT
    event_type,
    COUNT(*) AS event_count,
    MAX(occurred_at) AS latest_event
FROM network_events
GROUP BY event_type
ORDER BY event_count DESC;

-- 20. Calculate successful connectivity percentage.
SELECT
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (
        WHERE decision = 'allow'
    ) AS allowed_requests,
    COUNT(*) FILTER (
        WHERE decision = 'deny'
    ) AS denied_requests,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE decision = 'allow'
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS allowed_percentage
FROM connectivity_decisions;

-- ============================================================
-- ADDITIONAL TRANSACTION EXAMPLE
-- Demonstrates atomic network disconnection.
-- Execute separately when the disconnection is required.
-- ============================================================

-- BEGIN;
--
-- UPDATE network_memberships
-- SET disconnected_at = NOW()
-- WHERE container_id = (
--     SELECT container_id
--     FROM containers
--     WHERE container_name = 'api'
-- )
-- AND network_id = (
--     SELECT network_id
--     FROM networks
--     WHERE network_name = 'frontend-net'
-- )
-- AND disconnected_at IS NULL;
--
-- COMMIT;
--
-- ============================================================
-- END OF DOCKER NETWORKING DATABASE
-- ============================================================
