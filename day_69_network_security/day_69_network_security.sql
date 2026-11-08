-- ============================================================
-- NETWORK SECURITY MANAGEMENT SYSTEM
-- PostgreSQL 14+
--
-- Models:
-- 1. Network infrastructure and subnets
-- 2. Firewalls and firewall rules
-- 3. Security groups
-- 4. Network ACLs
-- 5. Stateless and stateful traffic controls
-- 6. Network packets and traffic decisions
-- 7. Connection tracking
-- 8. Security audit records
-- 9. Policy validation and reporting
--
-- Important:
-- This is a policy simulation and audit database.
-- It does not install or enforce operating-system firewall rules.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS network_security;

SET search_path TO network_security, public;

-- ============================================================
-- 1. ENUMERATIONS
-- ============================================================

CREATE TYPE network_protocol AS ENUM (
    'TCP',
    'UDP',
    'ICMP',
    'ANY'
);

CREATE TYPE traffic_direction AS ENUM (
    'INBOUND',
    'OUTBOUND'
);

CREATE TYPE traffic_action AS ENUM (
    'ALLOW',
    'DENY'
);

CREATE TYPE security_layer AS ENUM (
    'FIREWALL',
    'SECURITY_GROUP',
    'NETWORK_ACL'
);

CREATE TYPE decision_reason AS ENUM (
    'RULE_MATCH',
    'DEFAULT_DENY',
    'STATEFUL_RETURN',
    'INVALID_PACKET'
);

CREATE TYPE connection_status AS ENUM (
    'ESTABLISHED',
    'CLOSED',
    'EXPIRED'
);

-- ============================================================
-- 2. NETWORK INFRASTRUCTURE
-- ============================================================

CREATE TABLE network_zones (
    zone_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zone_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    environment VARCHAR(30) NOT NULL
        CHECK (
            environment IN (
                'DEVELOPMENT',
                'TESTING',
                'STAGING',
                'PRODUCTION'
            )
        ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE network_subnets (
    subnet_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zone_id BIGINT NOT NULL
        REFERENCES network_zones(zone_id),
    subnet_name VARCHAR(100) NOT NULL,
    cidr_block CIDR NOT NULL,
    address_family SMALLINT NOT NULL DEFAULT 4
        CHECK (address_family IN (4, 6)),
    description TEXT,

    UNIQUE (zone_id, subnet_name),

    CHECK (
        family(cidr_block) = address_family
    )
);

CREATE INDEX idx_subnets_zone
ON network_subnets(zone_id);

-- ============================================================
-- 3. FIREWALLS
-- ============================================================

CREATE TABLE firewalls (
    firewall_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    firewall_name VARCHAR(120) NOT NULL UNIQUE,
    zone_id BIGINT REFERENCES network_zones(zone_id),
    stateful BOOLEAN NOT NULL DEFAULT TRUE,
    default_action traffic_action NOT NULL DEFAULT 'DENY',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 4. SECURITY GROUPS
-- ============================================================

CREATE TABLE security_groups (
    security_group_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_name VARCHAR(120) NOT NULL UNIQUE,
    zone_id BIGINT REFERENCES network_zones(zone_id),
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE security_group_subnets (
    security_group_id BIGINT NOT NULL
        REFERENCES security_groups(security_group_id)
        ON DELETE CASCADE,
    subnet_id BIGINT NOT NULL
        REFERENCES network_subnets(subnet_id)
        ON DELETE CASCADE,

    PRIMARY KEY (security_group_id, subnet_id)
);

-- ============================================================
-- 5. NETWORK ACCESS CONTROL LISTS
-- ============================================================

CREATE TABLE network_acls (
    acl_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    acl_name VARCHAR(120) NOT NULL UNIQUE,
    zone_id BIGINT REFERENCES network_zones(zone_id),
    stateful BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (stateful = FALSE),
    default_action traffic_action NOT NULL DEFAULT 'DENY',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE network_acl_subnets (
    acl_id BIGINT NOT NULL
        REFERENCES network_acls(acl_id)
        ON DELETE CASCADE,
    subnet_id BIGINT NOT NULL
        REFERENCES network_subnets(subnet_id)
        ON DELETE CASCADE,

    PRIMARY KEY (acl_id, subnet_id)
);

-- ============================================================
-- 6. CENTRALIZED SECURITY RULES
-- ============================================================

CREATE TABLE security_rules (
    rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    layer security_layer NOT NULL,

    firewall_id BIGINT REFERENCES firewalls(firewall_id),
    security_group_id BIGINT
        REFERENCES security_groups(security_group_id),
    acl_id BIGINT REFERENCES network_acls(acl_id),

    rule_number INTEGER NOT NULL
        CHECK (rule_number >= 0),

    rule_name VARCHAR(150) NOT NULL,

    source_cidr CIDR NOT NULL,
    destination_cidr CIDR NOT NULL,

    protocol network_protocol NOT NULL,

    direction traffic_direction NOT NULL,

    action traffic_action NOT NULL,

    port_start INTEGER NOT NULL DEFAULT 0,
    port_end INTEGER NOT NULL DEFAULT 65535,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (port_start BETWEEN 0 AND 65535),
    CHECK (port_end BETWEEN 0 AND 65535),
    CHECK (port_start <= port_end),

    CHECK (
        family(source_cidr) = family(destination_cidr)
    ),

    CHECK (
        protocol <> 'ICMP'
        OR (port_start = 0 AND port_end = 65535)
    ),

    CHECK (
        (layer = 'FIREWALL'
            AND firewall_id IS NOT NULL
            AND security_group_id IS NULL
            AND acl_id IS NULL)
        OR
        (layer = 'SECURITY_GROUP'
            AND firewall_id IS NULL
            AND security_group_id IS NOT NULL
            AND acl_id IS NULL)
        OR
        (layer = 'NETWORK_ACL'
            AND firewall_id IS NULL
            AND security_group_id IS NULL
            AND acl_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_firewall_rule_number
ON security_rules(firewall_id, rule_number)
WHERE firewall_id IS NOT NULL;

CREATE UNIQUE INDEX uq_security_group_rule_number
ON security_rules(security_group_id, rule_number)
WHERE security_group_id IS NOT NULL;

CREATE UNIQUE INDEX uq_acl_rule_number
ON security_rules(acl_id, rule_number)
WHERE acl_id IS NOT NULL;

CREATE INDEX idx_rules_firewall_enabled
ON security_rules(firewall_id, rule_number)
WHERE enabled = TRUE;

CREATE INDEX idx_rules_group_enabled
ON security_rules(security_group_id, rule_number)
WHERE enabled = TRUE;

CREATE INDEX idx_rules_acl_enabled
ON security_rules(acl_id, rule_number)
WHERE enabled = TRUE;

CREATE INDEX idx_rules_source_cidr
ON security_rules USING GIST(source_cidr inet_ops);

CREATE INDEX idx_rules_destination_cidr
ON security_rules USING GIST(destination_cidr inet_ops);

-- ============================================================
-- 7. PACKET EVENTS
-- ============================================================

CREATE TABLE packet_events (
    packet_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source_ip INET NOT NULL,
    destination_ip INET NOT NULL,

    source_port INTEGER NOT NULL DEFAULT 0,
    destination_port INTEGER NOT NULL DEFAULT 0,

    protocol network_protocol NOT NULL,

    direction traffic_direction NOT NULL,

    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (family(source_ip) = family(destination_ip)),
    CHECK (source_port BETWEEN 0 AND 65535),
    CHECK (destination_port BETWEEN 0 AND 65535),

    CHECK (
        protocol <> 'ICMP'
        OR (source_port = 0 AND destination_port = 0)
    )
);

CREATE INDEX idx_packet_events_received
ON packet_events(received_at DESC);

CREATE INDEX idx_packet_events_source
ON packet_events(source_ip);

CREATE INDEX idx_packet_events_destination
ON packet_events(destination_ip);

-- ============================================================
-- 8. CONNECTION TRACKING
-- ============================================================

CREATE TABLE tracked_connections (
    connection_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source_ip INET NOT NULL,
    destination_ip INET NOT NULL,

    source_port INTEGER NOT NULL,
    destination_port INTEGER NOT NULL,

    protocol network_protocol NOT NULL
        CHECK (protocol IN ('TCP', 'UDP')),

    status connection_status NOT NULL DEFAULT 'ESTABLISHED',

    established_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    CHECK (source_port BETWEEN 1 AND 65535),
    CHECK (destination_port BETWEEN 1 AND 65535),
    CHECK (expires_at > established_at)
);

CREATE INDEX idx_active_connections
ON tracked_connections(
    source_ip,
    destination_ip,
    source_port,
    destination_port,
    protocol
)
WHERE status = 'ESTABLISHED';

CREATE INDEX idx_connection_expiration
ON tracked_connections(expires_at)
WHERE status = 'ESTABLISHED';

-- ============================================================
-- 9. SECURITY DECISION AUDIT
-- ============================================================

CREATE TABLE security_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    packet_id BIGINT NOT NULL
        REFERENCES packet_events(packet_id),

    layer security_layer NOT NULL,

    rule_id BIGINT REFERENCES security_rules(rule_id),

    action traffic_action NOT NULL,

    reason decision_reason NOT NULL,

    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    details TEXT
);

CREATE INDEX idx_audit_time
ON security_audit(evaluated_at DESC);

CREATE INDEX idx_audit_action
ON security_audit(action, evaluated_at DESC);

CREATE INDEX idx_audit_layer
ON security_audit(layer, action);

-- ============================================================
-- 10. VALIDATE RULE OWNERSHIP
-- ============================================================

CREATE OR REPLACE FUNCTION validate_security_rule_owner()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.layer = 'FIREWALL' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM firewalls
            WHERE firewall_id = NEW.firewall_id
              AND enabled = TRUE
        ) THEN
            RAISE EXCEPTION
                'Firewall does not exist or is disabled';
        END IF;

    ELSIF NEW.layer = 'SECURITY_GROUP' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM security_groups
            WHERE security_group_id = NEW.security_group_id
              AND enabled = TRUE
        ) THEN
            RAISE EXCEPTION
                'Security group does not exist or is disabled';
        END IF;

    ELSIF NEW.layer = 'NETWORK_ACL' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM network_acls
            WHERE acl_id = NEW.acl_id
              AND enabled = TRUE
        ) THEN
            RAISE EXCEPTION
                'Network ACL does not exist or is disabled';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_security_rule_owner
BEFORE INSERT OR UPDATE ON security_rules
FOR EACH ROW
EXECUTE FUNCTION validate_security_rule_owner();

-- ============================================================
-- 11. RULE MATCHING FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION find_matching_rule(
    p_layer security_layer,
    p_owner_id BIGINT,
    p_source_ip INET,
    p_destination_ip INET,
    p_source_port INTEGER,
    p_destination_port INTEGER,
    p_protocol network_protocol,
    p_direction traffic_direction
)
RETURNS TABLE (
    matched_rule_id BIGINT,
    matched_action traffic_action,
    matched_rule_name VARCHAR(150)
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        r.rule_id,
        r.action,
        r.rule_name
    FROM security_rules r
    WHERE r.layer = p_layer
      AND r.enabled = TRUE

      AND CASE p_layer
          WHEN 'FIREWALL' THEN r.firewall_id = p_owner_id
          WHEN 'SECURITY_GROUP' THEN
              r.security_group_id = p_owner_id
          WHEN 'NETWORK_ACL' THEN r.acl_id = p_owner_id
          ELSE FALSE
      END

      AND p_source_ip <<= r.source_cidr
      AND p_destination_ip <<= r.destination_cidr

      AND (
          r.protocol = 'ANY'
          OR r.protocol = p_protocol
      )

      AND r.direction = p_direction

      AND (
          p_protocol = 'ICMP'
          OR p_destination_port BETWEEN
             r.port_start AND r.port_end
      )

    ORDER BY r.rule_number ASC

    LIMIT 1;
$$;

-- ============================================================
-- 12. SECURITY EVALUATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_traffic(
    p_layer security_layer,
    p_owner_id BIGINT,
    p_source_ip INET,
    p_destination_ip INET,
    p_source_port INTEGER,
    p_destination_port INTEGER,
    p_protocol network_protocol,
    p_direction traffic_direction
)
RETURNS TABLE (
    allowed BOOLEAN,
    decision traffic_action,
    reason decision_reason,
    matched_rule BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_rule RECORD;
    v_default traffic_action;
    v_stateful BOOLEAN;
    v_return_exists BOOLEAN;
BEGIN
    IF family(p_source_ip) <> family(p_destination_ip) THEN
        RAISE EXCEPTION 'Source and destination IP families differ';
    END IF;

    IF p_source_port NOT BETWEEN 0 AND 65535
       OR p_destination_port NOT BETWEEN 0 AND 65535 THEN
        RAISE EXCEPTION 'Invalid transport port';
    END IF;

    IF p_protocol = 'ICMP'
       AND (p_source_port <> 0 OR p_destination_port <> 0) THEN
        RAISE EXCEPTION 'ICMP cannot contain transport ports';
    END IF;

    -- Determine the policy's default action and state behavior.
    IF p_layer = 'FIREWALL' THEN

        SELECT default_action, stateful
        INTO v_default, v_stateful
        FROM firewalls
        WHERE firewall_id = p_owner_id
          AND enabled = TRUE;

    ELSIF p_layer = 'SECURITY_GROUP' THEN

        SELECT 'DENY'::traffic_action, TRUE
        INTO v_default, v_stateful
        FROM security_groups
        WHERE security_group_id = p_owner_id
          AND enabled = TRUE;

    ELSIF p_layer = 'NETWORK_ACL' THEN

        SELECT default_action, FALSE
        INTO v_default, v_stateful
        FROM network_acls
        WHERE acl_id = p_owner_id
          AND enabled = TRUE;

    ELSE
        RAISE EXCEPTION 'Unsupported security layer';
    END IF;

    IF v_default IS NULL THEN
        RAISE EXCEPTION 'Security policy is unavailable';
    END IF;

    -- Stateful return traffic is permitted when an established
    -- connection exists in the reverse direction.
    IF v_stateful
       AND p_direction = 'OUTBOUND'
       AND p_protocol IN ('TCP', 'UDP') THEN

        SELECT EXISTS (
            SELECT 1
            FROM tracked_connections c
            WHERE c.source_ip = p_destination_ip
              AND c.destination_ip = p_source_ip
              AND c.source_port = p_destination_port
              AND c.destination_port = p_source_port
              AND c.protocol = p_protocol
              AND c.status = 'ESTABLISHED'
              AND c.expires_at > NOW()
        )
        INTO v_return_exists;

        IF v_return_exists THEN
            RETURN QUERY SELECT
                TRUE,
                'ALLOW'::traffic_action,
                'STATEFUL_RETURN'::decision_reason,
                NULL::BIGINT;

            RETURN;
        END IF;
    END IF;

    SELECT *
    INTO v_rule
    FROM find_matching_rule(
        p_layer,
        p_owner_id,
        p_source_ip,
        p_destination_ip,
        p_source_port,
        p_destination_port,
        p_protocol,
        p_direction
    );

    IF FOUND THEN
        RETURN QUERY SELECT
            v_rule.matched_action = 'ALLOW',
            v_rule.matched_action,
            'RULE_MATCH'::decision_reason,
            v_rule.matched_rule_id;

        RETURN;
    END IF;

    RETURN QUERY SELECT
        v_default = 'ALLOW',
        v_default,
        'DEFAULT_DENY'::decision_reason,
        NULL::BIGINT;
END;
$$;

-- ============================================================
-- 13. CONNECTION ESTABLISHMENT PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE establish_connection(
    p_source_ip INET,
    p_destination_ip INET,
    p_source_port INTEGER,
    p_destination_port INTEGER,
    p_protocol network_protocol,
    p_lifetime_seconds INTEGER DEFAULT 3600
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_protocol NOT IN ('TCP', 'UDP') THEN
        RAISE EXCEPTION
            'Connection tracking supports TCP and UDP only';
    END IF;

    IF p_source_port NOT BETWEEN 1 AND 65535
       OR p_destination_port NOT BETWEEN 1 AND 65535 THEN
        RAISE EXCEPTION 'Invalid connection ports';
    END IF;

    IF p_lifetime_seconds <= 0
       OR p_lifetime_seconds > 86400 THEN
        RAISE EXCEPTION 'Connection lifetime must be 1-86400 seconds';
    END IF;

    INSERT INTO tracked_connections (
        source_ip,
        destination_ip,
        source_port,
        destination_port,
        protocol,
        status,
        expires_at
    )
    VALUES (
        p_source_ip,
        p_destination_ip,
        p_source_port,
        p_destination_port,
        p_protocol,
        'ESTABLISHED',
        NOW() + make_interval(secs => p_lifetime_seconds)
    );
END;
$$;

-- ============================================================
-- 14. CONNECTION EXPIRATION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE expire_connections()
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE tracked_connections
    SET status = 'EXPIRED'
    WHERE status = 'ESTABLISHED'
      AND expires_at <= NOW();
END;
$$;

-- ============================================================
-- 15. SAMPLE INFRASTRUCTURE
-- ============================================================

INSERT INTO network_zones (
    zone_name,
    description,
    environment
)
VALUES
    ('PRODUCTION-WEB', 'Public-facing web application zone', 'PRODUCTION'),
    ('PRODUCTION-APP', 'Application processing zone', 'PRODUCTION'),
    ('PRODUCTION-DATA', 'Restricted database zone', 'PRODUCTION'),
    ('DEVELOPMENT', 'Development environment', 'DEVELOPMENT');

INSERT INTO network_subnets (
    zone_id,
    subnet_name,
    cidr_block,
    address_family
)
SELECT
    zone_id,
    'WEB-SUBNET',
    '172.16.1.0/24',
    4
FROM network_zones
WHERE zone_name = 'PRODUCTION-WEB';

INSERT INTO network_subnets (
    zone_id,
    subnet_name,
    cidr_block,
    address_family
)
SELECT
    zone_id,
    'APP-SUBNET',
    '172.16.2.0/24',
    4
FROM network_zones
WHERE zone_name = 'PRODUCTION-APP';

INSERT INTO network_subnets (
    zone_id,
    subnet_name,
    cidr_block,
    address_family
)
SELECT
    zone_id,
    'DATA-SUBNET',
    '172.16.3.0/24',
    4
FROM network_zones
WHERE zone_name = 'PRODUCTION-DATA';

-- ============================================================
-- 16. SAMPLE SECURITY CONTROLS
-- ============================================================

INSERT INTO firewalls (
    firewall_name,
    zone_id,
    stateful,
    default_action
)
SELECT
    'PRODUCTION-FIREWALL',
    zone_id,
    TRUE,
    'DENY'
FROM network_zones
WHERE zone_name = 'PRODUCTION-WEB';

INSERT INTO security_groups (
    group_name,
    zone_id,
    description
)
SELECT
    'WEB-SECURITY-GROUP',
    zone_id,
    'Permit authorized HTTPS access'
FROM network_zones
WHERE zone_name = 'PRODUCTION-WEB';

INSERT INTO network_acls (
    acl_name,
    zone_id,
    default_action
)
SELECT
    'PRODUCTION-NACL',
    zone_id,
    'DENY'
FROM network_zones
WHERE zone_name = 'PRODUCTION-WEB';

-- Associate subnet with security group and ACL.

INSERT INTO security_group_subnets (
    security_group_id,
    subnet_id
)
SELECT sg.security_group_id, s.subnet_id
FROM security_groups sg
JOIN network_subnets s
    ON s.subnet_name = 'WEB-SUBNET';

INSERT INTO network_acl_subnets (
    acl_id,
    subnet_id
)
SELECT a.acl_id, s.subnet_id
FROM network_acls a
JOIN network_subnets s
    ON s.subnet_name = 'WEB-SUBNET';

-- ============================================================
-- 17. FIREWALL RULES
-- ============================================================

INSERT INTO security_rules (
    layer,
    firewall_id,
    rule_number,
    rule_name,
    source_cidr,
    destination_cidr,
    protocol,
    direction,
    action,
    port_start,
    port_end
)
SELECT
    'FIREWALL',
    firewall_id,
    100,
    'ALLOW-INTERNAL-HTTPS',
    '10.0.0.0/8',
    '172.16.0.0/12',
    'TCP',
    'INBOUND',
    'ALLOW',
    443,
    443
FROM firewalls
WHERE firewall_name = 'PRODUCTION-FIREWALL';

INSERT INTO security_rules (
    layer,
    firewall_id,
    rule_number,
    rule_name,
    source_cidr,
    destination_cidr,
    protocol,
    direction,
    action,
    port_start,
    port_end
)
SELECT
    'FIREWALL',
    firewall_id,
    200,
    'BLOCK-HTTP',
    '0.0.0.0/0',
    '172.16.0.0/12',
    'TCP',
    'INBOUND',
    'DENY',
    80,
    80
FROM firewalls
WHERE firewall_name = 'PRODUCTION-FIREWALL';

-- ============================================================
-- 18. SECURITY GROUP RULES
-- ============================================================

INSERT INTO security_rules (
    layer,
    security_group_id,
    rule_number,
    rule_name,
    source_cidr,
    destination_cidr,
    protocol,
    direction,
    action,
    port_start,
    port_end
)
SELECT
    'SECURITY_GROUP',
    security_group_id,
    100,
    'ALLOW-APPLICATION-HTTPS',
    '10.0.0.0/8',
    '172.16.0.0/12',
    'TCP',
    'INBOUND',
    'ALLOW',
    443,
    443
FROM security_groups
WHERE group_name = 'WEB-SECURITY-GROUP';

-- ============================================================
-- 19. NETWORK ACL RULES
-- ============================================================

INSERT INTO security_rules (
    layer,
    acl_id,
    rule_number,
    rule_name,
    source_cidr,
    destination_cidr,
    protocol,
    direction,
    action,
    port_start,
    port_end
)
SELECT
    'NETWORK_ACL',
    acl_id,
    100,
    'ALLOW-INBOUND-HTTPS',
    '10.0.0.0/8',
    '172.16.0.0/12',
    'TCP',
    'INBOUND',
    'ALLOW',
    443,
    443
FROM network_acls
WHERE acl_name = 'PRODUCTION-NACL';

INSERT INTO security_rules (
    layer,
    acl_id,
    rule_number,
    rule_name,
    source_cidr,
    destination_cidr,
    protocol,
    direction,
    action,
    port_start,
    port_end
)
SELECT
    'NETWORK_ACL',
    acl_id,
    200,
    'ALLOW-OUTBOUND-EPHEMERAL',
    '172.16.0.0/12',
    '10.0.0.0/8',
    'TCP',
    'OUTBOUND',
    'ALLOW',
    1024,
    65535
FROM network_acls
WHERE acl_name = 'PRODUCTION-NACL';

-- ============================================================
-- 20. PACKET EVENT EXAMPLES
-- ============================================================

INSERT INTO packet_events (
    source_ip,
    destination_ip,
    source_port,
    destination_port,
    protocol,
    direction
)
VALUES
    (
        '10.1.1.10',
        '172.16.1.20',
        51000,
        443,
        'TCP',
        'INBOUND'
    ),
    (
        '203.0.113.25',
        '172.16.1.20',
        51001,
        80,
        'TCP',
        'INBOUND'
    ),
    (
        '10.1.1.10',
        '172.16.1.20',
        51002,
        22,
        'TCP',
        'INBOUND'
    ),
    (
        '10.1.1.10',
        '172.16.1.20',
        51003,
        53,
        'UDP',
        'INBOUND'
    );

-- ============================================================
-- 21. RETRIEVAL AND POLICY EVALUATION
-- ============================================================

-- Retrieve all firewall rules in evaluation order.

SELECT
    rule_id,
    rule_name,
    source_cidr,
    destination_cidr,
    protocol,
    direction,
    action,
    rule_number
FROM security_rules
WHERE layer = 'FIREWALL'
ORDER BY rule_number;

-- Evaluate the first packet against the firewall.

SELECT *
FROM evaluate_traffic(
    'FIREWALL',
    (
        SELECT firewall_id
        FROM firewalls
        WHERE firewall_name = 'PRODUCTION-FIREWALL'
    ),
    '10.1.1.10',
    '172.16.1.20',
    51000,
    443,
    'TCP',
    'INBOUND'
);

-- Evaluate an HTTP packet.

SELECT *
FROM evaluate_traffic(
    'FIREWALL',
    (
        SELECT firewall_id
        FROM firewalls
        WHERE firewall_name = 'PRODUCTION-FIREWALL'
    ),
    '203.0.113.25',
    '172.16.1.20',
    51001,
    80,
    'TCP',
    'INBOUND'
);

-- Evaluate unauthorized SSH traffic.

SELECT *
FROM evaluate_traffic(
    'FIREWALL',
    (
        SELECT firewall_id
        FROM firewalls
        WHERE firewall_name = 'PRODUCTION-FIREWALL'
    ),
    '10.1.1.10',
    '172.16.1.20',
    51002,
    22,
    'TCP',
    'INBOUND'
);

-- ============================================================
-- 22. MULTI-LAYER TRAFFIC EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_network_stack(
    p_source_ip INET,
    p_destination_ip INET,
    p_source_port INTEGER,
    p_destination_port INTEGER,
    p_protocol network_protocol,
    p_direction traffic_direction
)
RETURNS TABLE (
    firewall_allowed BOOLEAN,
    security_group_allowed BOOLEAN,
    acl_allowed BOOLEAN,
    final_allowed BOOLEAN
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_firewall BOOLEAN;
    v_group BOOLEAN := TRUE;
    v_acl BOOLEAN;
    v_firewall_id BIGINT;
    v_group_id BIGINT;
    v_acl_id BIGINT;
BEGIN
    SELECT firewall_id
    INTO v_firewall_id
    FROM firewalls
    WHERE firewall_name = 'PRODUCTION-FIREWALL'
      AND enabled = TRUE;

    SELECT security_group_id
    INTO v_group_id
    FROM security_groups
    WHERE group_name = 'WEB-SECURITY-GROUP'
      AND enabled = TRUE;

    SELECT acl_id
    INTO v_acl_id
    FROM network_acls
    WHERE acl_name = 'PRODUCTION-NACL'
      AND enabled = TRUE;

    SELECT allowed INTO v_firewall
    FROM evaluate_traffic(
        'FIREWALL',
        v_firewall_id,
        p_source_ip,
        p_destination_ip,
        p_source_port,
        p_destination_port,
        p_protocol,
        p_direction
    );

    IF p_direction = 'INBOUND' THEN
        SELECT allowed INTO v_group
        FROM evaluate_traffic(
            'SECURITY_GROUP',
            v_group_id,
            p_source_ip,
            p_destination_ip,
            p_source_port,
            p_destination_port,
            p_protocol,
            p_direction
        );
    END IF;

    SELECT allowed INTO v_acl
    FROM evaluate_traffic(
        'NETWORK_ACL',
        v_acl_id,
        p_source_ip,
        p_destination_ip,
        p_source_port,
        p_destination_port,
        p_protocol,
        p_direction
    );

    RETURN QUERY SELECT
        v_firewall,
        v_group,
        v_acl,
        v_firewall AND v_group AND v_acl;
END;
$$;

SELECT *
FROM evaluate_network_stack(
    '10.1.1.10',
    '172.16.1.20',
    51000,
    443,
    'TCP',
    'INBOUND'
);

-- ============================================================
-- 23. AUDIT INSERTION
-- ============================================================

INSERT INTO security_audit (
    packet_id,
    layer,
    rule_id,
    action,
    reason,
    details
)
SELECT
    p.packet_id,
    'FIREWALL',
    r.rule_id,
    COALESCE(r.action, f.default_action),
    CASE
        WHEN r.rule_id IS NULL THEN 'DEFAULT_DENY'
        ELSE 'RULE_MATCH'
    END,
    COALESCE(r.rule_name, 'No matching firewall rule')
FROM packet_events p
CROSS JOIN firewalls f
LEFT JOIN LATERAL (
    SELECT rule_id, action, rule_name
    FROM security_rules sr
    WHERE sr.firewall_id = f.firewall_id
      AND sr.enabled = TRUE
      AND sr.direction = p.direction
      AND p.source_ip <<= sr.source_cidr
      AND p.destination_ip <<= sr.destination_cidr
      AND (
          sr.protocol = 'ANY'
          OR sr.protocol = p.protocol
      )
      AND (
          p.protocol = 'ICMP'
          OR p.destination_port BETWEEN
             sr.port_start AND sr.port_end
      )
    ORDER BY sr.rule_number
    LIMIT 1
) r ON TRUE
WHERE f.firewall_name = 'PRODUCTION-FIREWALL';

-- ============================================================
-- 24. REPORTING VIEWS
-- ============================================================

CREATE OR REPLACE VIEW firewall_rule_inventory AS
SELECT
    sr.rule_id,
    sr.rule_name,
    sr.layer,
    f.firewall_name,
    sg.group_name,
    acl.acl_name,
    sr.source_cidr,
    sr.destination_cidr,
    sr.protocol,
    sr.direction,
    sr.action,
    sr.rule_number,
    sr.enabled
FROM security_rules sr
LEFT JOIN firewalls f
    ON f.firewall_id = sr.firewall_id
LEFT JOIN security_groups sg
    ON sg.security_group_id = sr.security_group_id
LEFT JOIN network_acls acl
    ON acl.acl_id = sr.acl_id;

CREATE OR REPLACE VIEW security_traffic_summary AS
SELECT
    DATE_TRUNC('hour', p.received_at) AS traffic_hour,
    p.protocol,
    p.direction,
    COUNT(*) AS total_packets,
    COUNT(*) FILTER (
        WHERE a.action = 'ALLOW'
    ) AS allowed_packets,
    COUNT(*) FILTER (
        WHERE a.action = 'DENY'
    ) AS denied_packets
FROM packet_events p
LEFT JOIN security_audit a
    ON a.packet_id = p.packet_id
GROUP BY
    DATE_TRUNC('hour', p.received_at),
    p.protocol,
    p.direction;

-- ============================================================
-- 25. AGGREGATION AND SECURITY REPORTING
-- ============================================================

SELECT
    layer,
    action,
    reason,
    COUNT(*) AS total_decisions
FROM security_audit
GROUP BY layer, action, reason
ORDER BY layer, action;

SELECT
    source_ip,
    destination_ip,
    protocol,
    COUNT(*) AS packet_count
FROM packet_events
GROUP BY source_ip, destination_ip, protocol
ORDER BY packet_count DESC;

SELECT *
FROM firewall_rule_inventory
ORDER BY layer, rule_number;

SELECT *
FROM security_traffic_summary;

-- ============================================================
-- 26. VALIDATION QUERIES
-- ============================================================

-- Detect broad source ranges.

SELECT
    rule_id,
    rule_name,
    source_cidr,
    destination_cidr
FROM security_rules
WHERE source_cidr IN (
    '0.0.0.0/0'::CIDR,
    '::/0'::CIDR
);

-- Detect disabled security rules.

SELECT *
FROM security_rules
WHERE enabled = FALSE;

-- Detect overly broad port ranges.

SELECT
    rule_id,
    rule_name,
    port_start,
    port_end
FROM security_rules
WHERE port_start = 0
  AND port_end = 65535
  AND protocol <> 'ICMP';

-- ============================================================
-- 27. TRANSACTIONAL POLICY CHANGE
-- ============================================================

-- Example: adding a restricted database access rule.
-- The change is atomic.

BEGIN;

INSERT INTO security_rules (
    layer,
    firewall_id,
    rule_number,
    rule_name,
    source_cidr,
    destination_cidr,
    protocol,
    direction,
    action,
    port_start,
    port_end
)
SELECT
    'FIREWALL',
    firewall_id,
    300,
    'ALLOW-APP-TO-DATABASE',
    '172.16.2.0/24',
    '172.16.3.0/24',
    'TCP',
    'OUTBOUND',
    'ALLOW',
    5432,
    5432
FROM firewalls
WHERE firewall_name = 'PRODUCTION-FIREWALL';

COMMIT;

-- ============================================================
-- 28. EXPIRED CONNECTION REPORT
-- ============================================================

SELECT
    connection_id,
    source_ip,
    destination_ip,
    protocol,
    status,
    established_at,
    expires_at
FROM tracked_connections
WHERE expires_at <= NOW();

-- ============================================================
-- 29. SECURITY SUMMARY
-- ============================================================

SELECT
    (SELECT COUNT(*) FROM firewalls) AS firewall_count,
    (SELECT COUNT(*) FROM security_groups) AS security_group_count,
    (SELECT COUNT(*) FROM network_acls) AS network_acl_count,
    (SELECT COUNT(*) FROM security_rules) AS rule_count,
    (SELECT COUNT(*) FROM packet_events) AS packet_count,
    (SELECT COUNT(*) FROM security_audit) AS audit_count;

COMMIT;
