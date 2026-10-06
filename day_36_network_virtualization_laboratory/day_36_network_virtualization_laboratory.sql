-- PostgreSQL-compatible Network Virtualization Laboratory
--
-- The schema separates:
--   virtual networks: logical tenant/network segments
--   virtual switches: data-plane forwarding devices
--   SDN control: flow rules and policy decisions
--   overlays: VTEPs and VNI mappings
--
-- The database intentionally enforces important invariants with constraints
-- rather than relying only on application-level validation.

DROP SCHEMA IF EXISTS network_virtualization CASCADE;

CREATE SCHEMA network_virtualization;

SET search_path TO network_virtualization;

CREATE TYPE segment_type AS ENUM (
    'TENANT',
    'MANAGEMENT',
    'TRANSIT'
);

CREATE TYPE switch_state AS ENUM (
    'ACTIVE',
    'MAINTENANCE',
    'FAILED'
);

CREATE TYPE endpoint_state AS ENUM (
    'ACTIVE',
    'DISABLED'
);

CREATE TYPE flow_state AS ENUM (
    'PENDING',
    'INSTALLED',
    'EXPIRED'
);

CREATE TYPE policy_action AS ENUM (
    'ALLOW',
    'DENY'
);

CREATE TABLE virtual_network (
    network_id BIGSERIAL PRIMARY KEY,
    network_name TEXT NOT NULL UNIQUE,
    cidr_block CIDR NOT NULL,
    vni INTEGER NOT NULL UNIQUE,
    segment_type segment_type NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (vni BETWEEN 1 AND 16777215)
);

CREATE TABLE virtual_switch (
    switch_id BIGSERIAL PRIMARY KEY,
    switch_name TEXT NOT NULL UNIQUE,
    management_ip INET NOT NULL UNIQUE,
    state switch_state NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE switch_port (
    port_id BIGSERIAL PRIMARY KEY,
    switch_id BIGINT NOT NULL REFERENCES virtual_switch(switch_id)
        ON DELETE CASCADE,
    port_name TEXT NOT NULL,
    port_role TEXT NOT NULL CHECK (
        port_role IN ('ENDPOINT', 'UPLINK', 'VTEP')
    ),
    UNIQUE (switch_id, port_name)
);

CREATE TABLE endpoint (
    endpoint_id BIGSERIAL PRIMARY KEY,
    endpoint_name TEXT NOT NULL UNIQUE,
    mac_address MACADDR NOT NULL UNIQUE,
    ip_address INET NOT NULL UNIQUE,
    network_id BIGINT NOT NULL REFERENCES virtual_network(network_id),
    switch_port_id BIGINT NOT NULL REFERENCES switch_port(port_id),
    state endpoint_state NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE vtep (
    vtep_id BIGSERIAL PRIMARY KEY,
    switch_id BIGINT NOT NULL UNIQUE REFERENCES virtual_switch(switch_id)
        ON DELETE CASCADE,
    vtep_ip INET NOT NULL UNIQUE
);

CREATE TABLE overlay_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    network_id BIGINT NOT NULL UNIQUE
        REFERENCES virtual_network(network_id)
        ON DELETE CASCADE,
    vni INTEGER NOT NULL UNIQUE,
    CHECK (vni BETWEEN 1 AND 16777215)
);

CREATE TABLE sdn_policy (
    policy_id BIGSERIAL PRIMARY KEY,
    source_network_id BIGINT NOT NULL
        REFERENCES virtual_network(network_id),
    destination_network_id BIGINT NOT NULL
        REFERENCES virtual_network(network_id),
    action policy_action NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    description TEXT NOT NULL,
    UNIQUE (
        source_network_id,
        destination_network_id,
        priority
    ),
    CHECK (priority > 0)
);

CREATE TABLE flow_rule (
    flow_id BIGSERIAL PRIMARY KEY,
    switch_id BIGINT NOT NULL REFERENCES virtual_switch(switch_id)
        ON DELETE CASCADE,
    network_id BIGINT NOT NULL REFERENCES virtual_network(network_id),
    destination_mac MACADDR NOT NULL,
    output_port_id BIGINT NOT NULL REFERENCES switch_port(port_id),
    priority INTEGER NOT NULL DEFAULT 100,
    state flow_state NOT NULL DEFAULT 'PENDING',
    packet_count BIGINT NOT NULL DEFAULT 0,
    installed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    CHECK (priority > 0),
    CHECK (packet_count >= 0),
    CHECK (
        (state = 'INSTALLED' AND installed_at IS NOT NULL)
        OR state <> 'INSTALLED'
    ),
    CHECK (
        expires_at IS NULL OR installed_at IS NULL
        OR expires_at > installed_at
    )
);

CREATE TABLE mac_learning (
    switch_id BIGINT NOT NULL REFERENCES virtual_switch(switch_id)
        ON DELETE CASCADE,
    mac_address MACADDR NOT NULL,
    port_id BIGINT NOT NULL REFERENCES switch_port(port_id),
    learned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (switch_id, mac_address)
);

CREATE TABLE control_event (
    event_id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    switch_id BIGINT REFERENCES virtual_switch(switch_id),
    network_id BIGINT REFERENCES virtual_network(network_id),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_endpoint_network
    ON endpoint(network_id);

CREATE INDEX idx_flow_lookup
    ON flow_rule(
        switch_id,
        network_id,
        destination_mac,
        state,
        priority DESC
    );

CREATE INDEX idx_mac_learning_lookup
    ON mac_learning(switch_id, mac_address);

CREATE INDEX idx_policy_evaluation
    ON sdn_policy(
        source_network_id,
        destination_network_id,
        priority DESC
    );

CREATE INDEX idx_control_event_time
    ON control_event(created_at DESC);

INSERT INTO virtual_network (
    network_name,
    cidr_block,
    vni,
    segment_type
)
VALUES
    ('tenant-a', '10.10.10.0/24', 1010, 'TENANT'),
    ('tenant-b', '10.20.20.0/24', 2020, 'TENANT'),
    ('management', '10.99.0.0/24', 9900, 'MANAGEMENT');

INSERT INTO virtual_switch (
    switch_name,
    management_ip
)
VALUES
    ('vswitch-a', '192.0.2.10'),
    ('vswitch-b', '192.0.2.20');

INSERT INTO switch_port (
    switch_id,
    port_name,
    port_role
)
SELECT switch_id, 'p1', 'ENDPOINT'
FROM virtual_switch
WHERE switch_name = 'vswitch-a';

INSERT INTO switch_port (
    switch_id,
    port_name,
    port_role
)
SELECT switch_id, 'p2', 'ENDPOINT'
FROM virtual_switch
WHERE switch_name = 'vswitch-a';

INSERT INTO switch_port (
    switch_id,
    port_name,
    port_role
)
SELECT switch_id, 'p1', 'ENDPOINT'
FROM virtual_switch
WHERE switch_name = 'vswitch-b';

INSERT INTO switch_port (
    switch_id,
    port_name,
    port_role
)
SELECT switch_id, 'p2', 'ENDPOINT'
FROM virtual_switch
WHERE switch_name = 'vswitch-b';

INSERT INTO switch_port (
    switch_id,
    port_name,
    port_role
)
SELECT switch_id, 'vtep0', 'VTEP'
FROM virtual_switch
WHERE switch_name IN ('vswitch-a', 'vswitch-b');

INSERT INTO vtep (
    switch_id,
    vtep_ip
)
SELECT switch_id, management_ip
FROM virtual_switch;

INSERT INTO overlay_mapping (
    network_id,
    vni
)
SELECT network_id, vni
FROM virtual_network
WHERE segment_type = 'TENANT';

INSERT INTO endpoint (
    endpoint_name,
    mac_address,
    ip_address,
    network_id,
    switch_port_id
)
SELECT
    'web-a',
    '02:00:00:00:00:01',
    '10.10.10.10',
    n.network_id,
    p.port_id
FROM virtual_network n
JOIN virtual_switch s
    ON s.switch_name = 'vswitch-a'
JOIN switch_port p
    ON p.switch_id = s.switch_id
   AND p.port_name = 'p1'
WHERE n.network_name = 'tenant-a';

INSERT INTO endpoint (
    endpoint_name,
    mac_address,
    ip_address,
    network_id,
    switch_port_id
)
SELECT
    'db-a',
    '02:00:00:00:00:02',
    '10.10.10.20',
    n.network_id,
    p.port_id
FROM virtual_network n
JOIN virtual_switch s
    ON s.switch_name = 'vswitch-a'
JOIN switch_port p
    ON p.switch_id = s.switch_id
   AND p.port_name = 'p2'
WHERE n.network_name = 'tenant-a';

INSERT INTO endpoint (
    endpoint_name,
    mac_address,
    ip_address,
    network_id,
    switch_port_id
)
SELECT
    'web-b',
    '02:00:00:00:00:11',
    '10.20.20.10',
    n.network_id,
    p.port_id
FROM virtual_network n
JOIN virtual_switch s
    ON s.switch_name = 'vswitch-b'
JOIN switch_port p
    ON p.switch_id = s.switch_id
   AND p.port_name = 'p1'
WHERE n.network_name = 'tenant-b';

INSERT INTO endpoint (
    endpoint_name,
    mac_address,
    ip_address,
    network_id,
    switch_port_id
)
SELECT
    'db-b',
    '02:00:00:00:00:12',
    '10.20.20.20',
    n.network_id,
    p.port_id
FROM virtual_network n
JOIN virtual_switch s
    ON s.switch_name = 'vswitch-b'
JOIN switch_port p
    ON p.switch_id = s.switch_id
   AND p.port_name = 'p2'
WHERE n.network_name = 'tenant-b';

-- Same-tenant traffic is explicitly allowed.
INSERT INTO sdn_policy (
    source_network_id,
    destination_network_id,
    action,
    priority,
    description
)
SELECT
    a.network_id,
    a.network_id,
    'ALLOW',
    100,
    'Permit traffic within tenant-a'
FROM virtual_network a
WHERE a.network_name = 'tenant-a';

INSERT INTO sdn_policy (
    source_network_id,
    destination_network_id,
    action,
    priority,
    description
)
SELECT
    b.network_id,
    b.network_id,
    'ALLOW',
    100,
    'Permit traffic within tenant-b'
FROM virtual_network b
WHERE b.network_name = 'tenant-b';

-- Cross-tenant traffic is denied by policy.
INSERT INTO sdn_policy (
    source_network_id,
    destination_network_id,
    action,
    priority,
    description
)
SELECT
    a.network_id,
    b.network_id,
    'DENY',
    200,
    'Prevent tenant-a from directly reaching tenant-b'
FROM virtual_network a
CROSS JOIN virtual_network b
WHERE a.network_name = 'tenant-a'
  AND b.network_name = 'tenant-b';

INSERT INTO sdn_policy (
    source_network_id,
    destination_network_id,
    action,
    priority,
    description
)
SELECT
    b.network_id,
    a.network_id,
    'DENY',
    200,
    'Prevent tenant-b from directly reaching tenant-a'
FROM virtual_network a
CROSS JOIN virtual_network b
WHERE a.network_name = 'tenant-a'
  AND b.network_name = 'tenant-b';

-- Simulate MAC learning in the virtual switch.
INSERT INTO mac_learning (
    switch_id,
    mac_address,
    port_id
)
SELECT
    s.switch_id,
    e.mac_address,
    e.switch_port_id
FROM endpoint e
JOIN switch_port p
    ON p.port_id = e.switch_port_id
JOIN virtual_switch s
    ON s.switch_id = p.switch_id
WHERE e.endpoint_name IN ('web-a', 'db-a');

-- Controller-programmed destination flow.
INSERT INTO flow_rule (
    switch_id,
    network_id,
    destination_mac,
    output_port_id,
    priority,
    state,
    packet_count,
    installed_at,
    expires_at
)
SELECT
    s.switch_id,
    n.network_id,
    e.mac_address,
    e.switch_port_id,
    200,
    'INSTALLED',
    0,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP + INTERVAL '10 minutes'
FROM endpoint e
JOIN virtual_network n
    ON n.network_id = e.network_id
JOIN switch_port p
    ON p.port_id = e.switch_port_id
JOIN virtual_switch s
    ON s.switch_id = p.switch_id
WHERE e.endpoint_name = 'db-a';

INSERT INTO control_event (
    event_type,
    switch_id,
    network_id,
    message
)
SELECT
    'FLOW_INSTALLED',
    s.switch_id,
    n.network_id,
    'Controller installed db-a destination flow'
FROM virtual_switch s
JOIN virtual_network n
    ON n.network_name = 'tenant-a'
WHERE s.switch_name = 'vswitch-a';

-- View: virtual network inventory and endpoint density.
CREATE VIEW virtual_network_inventory AS
SELECT
    n.network_name,
    n.cidr_block,
    n.vni,
    n.segment_type,
    COUNT(e.endpoint_id) AS endpoint_count
FROM virtual_network n
LEFT JOIN endpoint e
    ON e.network_id = n.network_id
GROUP BY
    n.network_id,
    n.network_name,
    n.cidr_block,
    n.vni,
    n.segment_type;

-- View: installed data-plane flows.
CREATE VIEW active_flow_inventory AS
SELECT
    s.switch_name,
    n.network_name,
    f.destination_mac,
    p.port_name AS output_port,
    f.priority,
    f.packet_count,
    f.installed_at,
    f.expires_at
FROM flow_rule f
JOIN virtual_switch s
    ON s.switch_id = f.switch_id
JOIN virtual_network n
    ON n.network_id = f.network_id
JOIN switch_port p
    ON p.port_id = f.output_port_id
WHERE f.state = 'INSTALLED'
  AND (f.expires_at IS NULL OR f.expires_at > CURRENT_TIMESTAMP);

-- View: overlay VTEP/VNI mapping.
CREATE VIEW overlay_inventory AS
SELECT
    n.network_name,
    n.vni,
    s.switch_name,
    v.vtep_ip
FROM overlay_mapping m
JOIN virtual_network n
    ON n.network_id = m.network_id
JOIN vtep v
    ON v.vtep_id IS NOT NULL
JOIN virtual_switch s
    ON s.switch_id = v.switch_id;

-- Evaluate a source/destination pair using the highest-priority policy.
WITH candidate_policy AS (
    SELECT
        p.policy_id,
        p.action,
        p.priority,
        ROW_NUMBER() OVER (
            ORDER BY p.priority DESC, p.policy_id DESC
        ) AS policy_rank
    FROM sdn_policy p
    JOIN virtual_network source_network
        ON source_network.network_id = p.source_network_id
    JOIN virtual_network destination_network
        ON destination_network.network_id =
           p.destination_network_id
    WHERE source_network.network_name = 'tenant-a'
      AND destination_network.network_name = 'tenant-b'
)
SELECT
    action,
    priority
FROM candidate_policy
WHERE policy_rank = 1;

-- Query the actual virtual-switch path for db-a.
SELECT
    s.switch_name,
    f.destination_mac,
    p.port_name AS output_port,
    f.priority,
    f.state
FROM flow_rule f
JOIN virtual_switch s
    ON s.switch_id = f.switch_id
JOIN switch_port p
    ON p.port_id = f.output_port_id
JOIN endpoint e
    ON e.mac_address = f.destination_mac
WHERE e.endpoint_name = 'db-a';

-- Find active endpoints and their logical network.
SELECT
    e.endpoint_name,
    e.mac_address,
    e.ip_address,
    n.network_name,
    n.vni,
    s.switch_name,
    p.port_name
FROM endpoint e
JOIN virtual_network n
    ON n.network_id = e.network_id
JOIN switch_port p
    ON p.port_id = e.switch_port_id
JOIN virtual_switch s
    ON s.switch_id = p.switch_id
WHERE e.state = 'ACTIVE'
ORDER BY n.network_name, e.endpoint_name;

-- Demonstrate transactional flow-counter maintenance.
BEGIN;

UPDATE flow_rule
SET packet_count = packet_count + 1
WHERE destination_mac = '02:00:00:00:00:02'
  AND state = 'INSTALLED'
  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP);

INSERT INTO control_event (
    event_type,
    switch_id,
    network_id,
    message
)
SELECT
    'PACKET_FORWARDED',
    f.switch_id,
    f.network_id,
    'Database request forwarded through programmed flow'
FROM flow_rule f
WHERE f.destination_mac = '02:00:00:00:00:02'
  AND f.state = 'INSTALLED';

COMMIT;

-- Detect expired flows that should no longer participate in forwarding.
SELECT
    s.switch_name,
    f.destination_mac,
    f.expires_at
FROM flow_rule f
JOIN virtual_switch s
    ON s.switch_id = f.switch_id
WHERE f.state = 'INSTALLED'
  AND f.expires_at < CURRENT_TIMESTAMP;

-- PostgreSQL constraint demonstration:
-- the following statement would fail because 16,777,216 is outside the
-- 24-bit VNI range. It is intentionally left commented so the complete
-- laboratory script remains executable.
--
-- INSERT INTO virtual_network (
--     network_name, cidr_block, vni, segment_type
-- ) VALUES (
--     'invalid-vni-network', '10.50.0.0/24', 16777216, 'TENANT'
-- );

-- Detect potentially unsafe endpoint placement where an endpoint's network
-- and switch port do not correspond to the expected operational topology.
SELECT
    e.endpoint_name,
    n.network_name,
    s.switch_name,
    p.port_name
FROM endpoint e
JOIN virtual_network n
    ON n.network_id = e.network_id
JOIN switch_port p
    ON p.port_id = e.switch_port_id
JOIN virtual_switch s
    ON s.switch_id = p.switch_id
WHERE p.port_role <> 'ENDPOINT';

-- Operational event stream.
SELECT
    created_at,
    event_type,
    message
FROM control_event
ORDER BY created_at DESC;
