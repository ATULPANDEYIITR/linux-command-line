-- PostgreSQL 15+ compatible data-center physical infrastructure model.
--
-- The schema represents physical capacity and operational relationships:
-- facilities contain racks; racks contain servers; servers consume power;
-- racks have redundant power feeds; cooling units remove heat; UPS systems
-- and generators provide facility power resilience; incidents record failures.
--
-- The database deliberately keeps physical infrastructure concerns separate
-- from application workloads.

DROP SCHEMA IF EXISTS data_center CASCADE;
CREATE SCHEMA data_center;

SET search_path TO data_center;

CREATE TYPE equipment_state AS ENUM (
    'online',
    'offline',
    'maintenance'
);

CREATE TYPE power_feed_side AS ENUM (
    'A',
    'B'
);

CREATE TYPE redundancy_model AS ENUM (
    'none',
    'N',
    'N+1',
    '2N'
);

CREATE TYPE incident_type AS ENUM (
    'power_feed_failure',
    'cooling_failure',
    'ups_failure',
    'generator_failure',
    'temperature_excursion'
);

CREATE TABLE facility (
    facility_id       BIGSERIAL PRIMARY KEY,
    facility_code     TEXT NOT NULL UNIQUE,
    facility_name     TEXT NOT NULL,
    location          TEXT NOT NULL,
    design_redundancy redundancy_model NOT NULL,
    ambient_temp_c    NUMERIC(5,2) NOT NULL DEFAULT 22.00,
    maximum_temp_c    NUMERIC(5,2) NOT NULL DEFAULT 27.00,
    CHECK (ambient_temp_c >= -50 AND ambient_temp_c <= 80),
    CHECK (maximum_temp_c > 0)
);

CREATE TABLE row_location (
    row_id       BIGSERIAL PRIMARY KEY,
    facility_id  BIGINT NOT NULL REFERENCES facility(facility_id)
                 ON DELETE CASCADE,
    row_code     TEXT NOT NULL,
    UNIQUE (facility_id, row_code)
);

CREATE TABLE rack (
    rack_id          BIGSERIAL PRIMARY KEY,
    row_id           BIGINT NOT NULL REFERENCES row_location(row_id)
                     ON DELETE CASCADE,
    rack_code        TEXT NOT NULL,
    total_rack_units INTEGER NOT NULL DEFAULT 42,
    CHECK (total_rack_units > 0),
    UNIQUE (row_id, rack_code)
);

CREATE TABLE power_feed (
    power_feed_id BIGSERIAL PRIMARY KEY,
    rack_id       BIGINT NOT NULL REFERENCES rack(rack_id)
                  ON DELETE CASCADE,
    feed_side     power_feed_side NOT NULL,
    capacity_kw   NUMERIC(10,2) NOT NULL,
    reserved_kw   NUMERIC(10,2) NOT NULL DEFAULT 0,
    online        BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (capacity_kw > 0),
    CHECK (reserved_kw >= 0),
    CHECK (reserved_kw < capacity_kw),
    UNIQUE (rack_id, feed_side)
);

CREATE TABLE server (
    server_id        BIGSERIAL PRIMARY KEY,
    rack_id          BIGINT NOT NULL REFERENCES rack(rack_id)
                     ON DELETE RESTRICT,
    asset_tag        TEXT NOT NULL UNIQUE,
    hostname         TEXT NOT NULL UNIQUE,
    rack_units       INTEGER NOT NULL,
    power_watts      NUMERIC(10,2) NOT NULL,
    dual_power       BOOLEAN NOT NULL,
    state            equipment_state NOT NULL DEFAULT 'online',
    installed_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (rack_units > 0),
    CHECK (power_watts > 0)
);

CREATE TABLE server_power_connection (
    connection_id BIGSERIAL PRIMARY KEY,
    server_id     BIGINT NOT NULL REFERENCES server(server_id)
                  ON DELETE CASCADE,
    power_feed_id BIGINT NOT NULL REFERENCES power_feed(power_feed_id)
                  ON DELETE RESTRICT,
    connected_watts NUMERIC(10,2) NOT NULL,
    CHECK (connected_watts > 0),
    UNIQUE (server_id, power_feed_id)
);

CREATE TABLE cooling_unit (
    cooling_unit_id BIGSERIAL PRIMARY KEY,
    facility_id     BIGINT NOT NULL REFERENCES facility(facility_id)
                    ON DELETE CASCADE,
    unit_code       TEXT NOT NULL,
    cooling_type    TEXT NOT NULL,
    capacity_kw     NUMERIC(10,2) NOT NULL,
    online          BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (facility_id, unit_code),
    CHECK (capacity_kw > 0)
);

CREATE TABLE ups_system (
    ups_id        BIGSERIAL PRIMARY KEY,
    facility_id   BIGINT NOT NULL REFERENCES facility(facility_id)
                  ON DELETE CASCADE,
    system_code   TEXT NOT NULL,
    capacity_kw   NUMERIC(10,2) NOT NULL,
    reserved_kw   NUMERIC(10,2) NOT NULL DEFAULT 0,
    online        BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (facility_id, system_code),
    CHECK (capacity_kw > 0),
    CHECK (reserved_kw >= 0),
    CHECK (reserved_kw < capacity_kw)
);

CREATE TABLE generator (
    generator_id  BIGSERIAL PRIMARY KEY,
    facility_id   BIGINT NOT NULL REFERENCES facility(facility_id)
                  ON DELETE CASCADE,
    generator_code TEXT NOT NULL,
    capacity_kw   NUMERIC(10,2) NOT NULL,
    online        BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (facility_id, generator_code),
    CHECK (capacity_kw > 0)
);

CREATE TABLE infrastructure_incident (
    incident_id     BIGSERIAL PRIMARY KEY,
    facility_id     BIGINT NOT NULL REFERENCES facility(facility_id)
                    ON DELETE CASCADE,
    incident_type   incident_type NOT NULL,
    component_name  TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMPTZ,
    severity        TEXT NOT NULL,
    description     TEXT NOT NULL,
    CHECK (severity IN ('warning', 'critical')),
    CHECK (resolved_at IS NULL OR resolved_at >= started_at)
);

CREATE INDEX idx_rack_row
    ON rack(row_id);

CREATE INDEX idx_server_rack_state
    ON server(rack_id, state);

CREATE INDEX idx_power_connection_feed
    ON server_power_connection(power_feed_id);

CREATE INDEX idx_cooling_facility_online
    ON cooling_unit(facility_id, online);

CREATE INDEX idx_incident_open
    ON infrastructure_incident(facility_id, started_at)
    WHERE resolved_at IS NULL;

INSERT INTO facility (
    facility_code,
    facility_name,
    location,
    design_redundancy
)
VALUES (
    'DC-LKO-01',
    'Regional Enterprise Data Center',
    'Lucknow',
    'N+1'
);

INSERT INTO row_location (facility_id, row_code)
SELECT facility_id, 'ROW-A'
FROM facility
WHERE facility_code = 'DC-LKO-01';

INSERT INTO rack (
    row_id,
    rack_code,
    total_rack_units
)
SELECT row_id, rack_code, 42
FROM row_location
CROSS JOIN (
    VALUES ('R01'), ('R02'), ('R03')
) AS racks(rack_code)
WHERE row_code = 'ROW-A';

INSERT INTO power_feed (
    rack_id,
    feed_side,
    capacity_kw,
    reserved_kw
)
SELECT
    rack_id,
    feed_side,
    10.00,
    1.00
FROM rack
CROSS JOIN (
    VALUES ('A'::power_feed_side), ('B'::power_feed_side)
) AS feeds(feed_side);

INSERT INTO server (
    rack_id,
    asset_tag,
    hostname,
    rack_units,
    power_watts,
    dual_power
)
SELECT
    r.rack_id,
    v.asset_tag,
    v.hostname,
    v.rack_units,
    v.power_watts,
    v.dual_power
FROM rack r
JOIN (
    VALUES
        ('ASSET-001', 'virt-01', 2, 900.00, TRUE, 'R01'),
        ('ASSET-002', 'db-01',   2, 750.00, TRUE, 'R01'),
        ('ASSET-003', 'fac-01',  1, 250.00, FALSE, 'R01'),
        ('ASSET-004', 'store-01',2, 700.00, TRUE, 'R02'),
        ('ASSET-005', 'compute-01',4,1400.00,TRUE,'R03')
) AS v(asset_tag, hostname, rack_units, power_watts, dual_power, rack_code)
ON r.rack_code = v.rack_code;

-- Dual-corded servers receive half their modeled load on each feed.
-- The single-corded facilities gateway is deliberately connected only to A.
INSERT INTO server_power_connection (
    server_id,
    power_feed_id,
    connected_watts
)
SELECT
    s.server_id,
    pf.power_feed_id,
    CASE
        WHEN s.dual_power THEN s.power_watts / 2
        ELSE s.power_watts
    END
FROM server s
JOIN rack r
    ON r.rack_id = s.rack_id
JOIN power_feed pf
    ON pf.rack_id = r.rack_id
WHERE
    (
        s.dual_power = TRUE
        AND pf.feed_side IN ('A', 'B')
    )
    OR (
        s.dual_power = FALSE
        AND pf.feed_side = 'A'
    );

INSERT INTO cooling_unit (
    facility_id,
    unit_code,
    cooling_type,
    capacity_kw
)
SELECT facility_id, unit_code, 'CRAC', capacity_kw
FROM facility
CROSS JOIN (
    VALUES
        ('CRAC-01', 8.00),
        ('CRAC-02', 8.00),
        ('CRAC-03', 8.00)
) AS units(unit_code, capacity_kw)
WHERE facility_code = 'DC-LKO-01';

INSERT INTO ups_system (
    facility_id,
    system_code,
    capacity_kw,
    reserved_kw
)
SELECT facility_id, system_code, capacity_kw, 20.00
FROM facility
CROSS JOIN (
    VALUES
        ('UPS-A', 120.00),
        ('UPS-B', 120.00)
) AS systems(system_code, capacity_kw)
WHERE facility_code = 'DC-LKO-01';

INSERT INTO generator (
    facility_id,
    generator_code,
    capacity_kw
)
SELECT facility_id, generator_code, capacity_kw
FROM facility
CROSS JOIN (
    VALUES
        ('GEN-A', 250.00),
        ('GEN-B', 250.00)
) AS systems(generator_code, capacity_kw)
WHERE facility_code = 'DC-LKO-01';

-- Physical rack occupancy.
SELECT
    r.rack_code,
    r.total_rack_units,
    COALESCE(SUM(
        CASE
            WHEN s.state <> 'offline' THEN s.rack_units
            ELSE 0
        END
    ), 0) AS used_u,
    r.total_rack_units - COALESCE(SUM(
        CASE
            WHEN s.state <> 'offline' THEN s.rack_units
            ELSE 0
        END
    ), 0) AS free_u
FROM rack r
LEFT JOIN server s
    ON s.rack_id = r.rack_id
GROUP BY r.rack_id, r.rack_code, r.total_rack_units
ORDER BY r.rack_code;

-- Electrical load by rack and feed.
SELECT
    r.rack_code,
    pf.feed_side,
    pf.capacity_kw,
    pf.reserved_kw,
    COALESCE(SUM(spc.connected_watts) / 1000.0, 0) AS connected_kw,
    pf.capacity_kw - pf.reserved_kw
        - COALESCE(SUM(spc.connected_watts) / 1000.0, 0) AS remaining_kw,
    pf.online
FROM rack r
JOIN power_feed pf
    ON pf.rack_id = r.rack_id
LEFT JOIN server_power_connection spc
    ON spc.power_feed_id = pf.power_feed_id
GROUP BY
    r.rack_id,
    r.rack_code,
    pf.power_feed_id,
    pf.feed_side,
    pf.capacity_kw,
    pf.reserved_kw,
    pf.online
ORDER BY r.rack_code, pf.feed_side;

-- IT heat load is represented by server electrical consumption.
WITH rack_heat AS (
    SELECT
        r.rack_id,
        r.rack_code,
        COALESCE(SUM(
            CASE
                WHEN s.state = 'online' THEN s.power_watts
                ELSE 0
            END
        ) / 1000.0, 0) AS heat_kw
    FROM rack r
    LEFT JOIN server s
        ON s.rack_id = r.rack_id
    GROUP BY r.rack_id, r.rack_code
)
SELECT *
FROM rack_heat
ORDER BY rack_code;

-- Facility cooling balance.
WITH it_load AS (
    SELECT
        f.facility_id,
        f.facility_code,
        COALESCE(SUM(
            CASE
                WHEN s.state = 'online' THEN s.power_watts
                ELSE 0
            END
        ) / 1000.0, 0) AS it_load_kw
    FROM facility f
    LEFT JOIN row_location rl
        ON rl.facility_id = f.facility_id
    LEFT JOIN rack r
        ON r.row_id = rl.row_id
    LEFT JOIN server s
        ON s.rack_id = r.rack_id
    GROUP BY f.facility_id, f.facility_code
),
cooling AS (
    SELECT
        facility_id,
        COALESCE(SUM(capacity_kw)
            FILTER (WHERE online), 0) AS cooling_kw
    FROM cooling_unit
    GROUP BY facility_id
)
SELECT
    i.facility_code,
    i.it_load_kw,
    COALESCE(c.cooling_kw, 0) AS cooling_kw,
    COALESCE(c.cooling_kw, 0) - i.it_load_kw AS cooling_margin_kw,
    COALESCE(c.cooling_kw, 0) >= i.it_load_kw AS cooling_sufficient
FROM it_load i
LEFT JOIN cooling c
    ON c.facility_id = i.facility_id;

-- N+1 cooling test:
-- If the largest currently-online cooling unit fails, remaining capacity
-- must still cover the active IT heat load.
WITH active_cooling AS (
    SELECT
        facility_id,
        cooling_unit_id,
        capacity_kw,
        MAX(capacity_kw) OVER (
            PARTITION BY facility_id
        ) AS largest_unit_kw
    FROM cooling_unit
    WHERE online
),
cooling_capacity AS (
    SELECT
        facility_id,
        SUM(capacity_kw) AS total_capacity_kw,
        MAX(largest_unit_kw) AS largest_unit_kw
    FROM active_cooling
    GROUP BY facility_id
),
it_load AS (
    SELECT
        f.facility_id,
        COALESCE(SUM(
            CASE
                WHEN s.state = 'online' THEN s.power_watts
                ELSE 0
            END
        ) / 1000.0, 0) AS it_load_kw
    FROM facility f
    LEFT JOIN row_location rl
        ON rl.facility_id = f.facility_id
    LEFT JOIN rack r
        ON r.row_id = rl.row_id
    LEFT JOIN server s
        ON s.rack_id = r.rack_id
    GROUP BY f.facility_id
)
SELECT
    i.facility_id,
    i.it_load_kw,
    c.total_capacity_kw,
    c.largest_unit_kw,
    c.total_capacity_kw - c.largest_unit_kw
        AS capacity_after_largest_failure_kw,
    c.total_capacity_kw - c.largest_unit_kw >= i.it_load_kw
        AS n_plus_one_pass
FROM it_load i
JOIN cooling_capacity c
    ON c.facility_id = i.facility_id;

-- Identify servers that lack electrical redundancy.
SELECT
    s.asset_tag,
    s.hostname,
    s.dual_power,
    COUNT(spc.connection_id) AS power_connections
FROM server s
LEFT JOIN server_power_connection spc
    ON spc.server_id = s.server_id
GROUP BY s.server_id
HAVING
    (s.dual_power AND COUNT(spc.connection_id) < 2)
    OR
    (NOT s.dual_power AND COUNT(spc.connection_id) <> 1);

-- A power-feed failure transaction:
-- This models an operational incident and changes both infrastructure state
-- and affected single-corded equipment in one atomic transaction.
BEGIN;

UPDATE power_feed
SET online = FALSE
WHERE rack_id = (
    SELECT r.rack_id
    FROM rack r
    WHERE r.rack_code = 'R01'
)
AND feed_side = 'A';

INSERT INTO infrastructure_incident (
    facility_id,
    incident_type,
    component_name,
    severity,
    description
)
SELECT
    facility_id,
    'power_feed_failure',
    'R01-A',
    'critical',
    'Rack R01 feed A is unavailable.'
FROM facility
WHERE facility_code = 'DC-LKO-01';

UPDATE server s
SET state = 'offline'
WHERE s.rack_id = (
    SELECT rack_id
    FROM rack
    WHERE rack_code = 'R01'
)
AND s.dual_power = FALSE
AND EXISTS (
    SELECT 1
    FROM server_power_connection spc
    JOIN power_feed pf
        ON pf.power_feed_id = spc.power_feed_id
    WHERE spc.server_id = s.server_id
      AND pf.feed_side = 'A'
);

COMMIT;

-- Verify the affected rack after the failure.
SELECT
    r.rack_code,
    s.asset_tag,
    s.hostname,
    s.state,
    s.dual_power
FROM rack r
JOIN server s
    ON s.rack_id = r.rack_id
WHERE r.rack_code = 'R01'
ORDER BY s.asset_tag;

-- Restore the feed and close the corresponding incident.
BEGIN;

UPDATE power_feed
SET online = TRUE
WHERE rack_id = (
    SELECT rack_id
    FROM rack
    WHERE rack_code = 'R01'
)
AND feed_side = 'A';

UPDATE server s
SET state = 'online'
WHERE s.rack_id = (
    SELECT rack_id
    FROM rack
    WHERE rack_code = 'R01'
)
AND s.asset_tag = 'ASSET-003';

UPDATE infrastructure_incident
SET resolved_at = CURRENT_TIMESTAMP
WHERE component_name = 'R01-A'
  AND incident_type = 'power_feed_failure'
  AND resolved_at IS NULL;

COMMIT;

-- Cooling failure simulation.
BEGIN;

UPDATE cooling_unit
SET online = FALSE
WHERE unit_code = 'CRAC-01'
  AND facility_id = (
      SELECT facility_id
      FROM facility
      WHERE facility_code = 'DC-LKO-01'
  );

INSERT INTO infrastructure_incident (
    facility_id,
    incident_type,
    component_name,
    severity,
    description
)
SELECT
    facility_id,
    'cooling_failure',
    'CRAC-01',
    'warning',
    'Cooling unit CRAC-01 is offline; N+1 capacity must be reevaluated.'
FROM facility
WHERE facility_code = 'DC-LKO-01';

COMMIT;

-- The cooling query exposes whether remaining units can support the heat load.
WITH heat AS (
    SELECT
        f.facility_id,
        COALESCE(SUM(
            CASE
                WHEN s.state = 'online' THEN s.power_watts
                ELSE 0
            END
        ) / 1000.0, 0) AS heat_kw
    FROM facility f
    LEFT JOIN row_location rl
        ON rl.facility_id = f.facility_id
    LEFT JOIN rack r
        ON r.row_id = rl.row_id
    LEFT JOIN server s
        ON s.rack_id = r.rack_id
    GROUP BY f.facility_id
),
available_cooling AS (
    SELECT
        facility_id,
        COALESCE(SUM(capacity_kw)
            FILTER (WHERE online), 0) AS available_kw
    FROM cooling_unit
    GROUP BY facility_id
)
SELECT
    h.facility_id,
    h.heat_kw,
    c.available_kw,
    c.available_kw - h.heat_kw AS margin_kw,
    c.available_kw >= h.heat_kw AS cooling_ok
FROM heat h
JOIN available_cooling c
    ON c.facility_id = h.facility_id;

-- Restore cooling and resolve the incident.
BEGIN;

UPDATE cooling_unit
SET online = TRUE
WHERE unit_code = 'CRAC-01'
  AND facility_id = (
      SELECT facility_id
      FROM facility
      WHERE facility_code = 'DC-LKO-01'
  );

UPDATE infrastructure_incident
SET resolved_at = CURRENT_TIMESTAMP
WHERE component_name = 'CRAC-01'
  AND incident_type = 'cooling_failure'
  AND resolved_at IS NULL;

COMMIT;

-- UPS and generator resilience snapshot.
SELECT
    f.facility_code,
    u.system_code AS ups_system,
    u.capacity_kw,
    u.reserved_kw,
    u.capacity_kw - u.reserved_kw AS usable_kw,
    u.online
FROM facility f
JOIN ups_system u
    ON u.facility_id = f.facility_id
ORDER BY u.system_code;

SELECT
    f.facility_code,
    g.generator_code,
    g.capacity_kw,
    g.online
FROM facility f
JOIN generator g
    ON g.facility_id = f.facility_id
ORDER BY g.generator_code;

-- Open incidents are operationally important because a facility can appear
-- physically capable while still having an unresolved component failure.
SELECT
    f.facility_code,
    i.incident_type,
    i.component_name,
    i.severity,
    i.started_at,
    i.description
FROM infrastructure_incident i
JOIN facility f
    ON f.facility_id = i.facility_id
WHERE i.resolved_at IS NULL
ORDER BY
    CASE i.severity
        WHEN 'critical' THEN 1
        ELSE 2
    END,
    i.started_at;
