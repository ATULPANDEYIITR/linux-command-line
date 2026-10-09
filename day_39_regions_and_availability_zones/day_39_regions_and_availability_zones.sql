-- PostgreSQL 15+ geographic infrastructure and resilience model.
-- Run in a dedicated database. The script creates its own schema.

BEGIN;

CREATE SCHEMA IF NOT EXISTS geo_resilience;
SET search_path TO geo_resilience, public;

CREATE TYPE health_state AS ENUM ('healthy', 'failed', 'maintenance');
CREATE TYPE failure_scope AS ENUM ('zone', 'region');
CREATE TYPE replication_mode AS ENUM ('synchronous', 'asynchronous');

CREATE TABLE geographic_region (
    region_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region_code        TEXT NOT NULL UNIQUE,
    display_name       TEXT NOT NULL,
    country_code       CHAR(2) NOT NULL,
    residency_group    TEXT NOT NULL,
    latitude           NUMERIC(8,5) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude          NUMERIC(8,5) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    state              health_state NOT NULL DEFAULT 'healthy',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (region_code ~ '^[a-z][a-z0-9-]{1,30}$')
);

CREATE TABLE availability_zone (
    zone_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region_id          BIGINT NOT NULL REFERENCES geographic_region(region_id),
    zone_code          TEXT NOT NULL UNIQUE,
    capacity_units     INTEGER NOT NULL CHECK (capacity_units >= 0),
    latency_ms         NUMERIC(9,3) NOT NULL CHECK (latency_ms >= 0),
    state              health_state NOT NULL DEFAULT 'healthy',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (region_id, zone_code)
);

CREATE INDEX availability_zone_region_state_idx
    ON availability_zone(region_id, state);

CREATE TABLE workload (
    workload_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_code      TEXT NOT NULL UNIQUE,
    required_units     INTEGER NOT NULL CHECK (required_units > 0),
    minimum_zones      INTEGER NOT NULL CHECK (minimum_zones > 0),
    maximum_latency_ms NUMERIC(9,3) NOT NULL CHECK (maximum_latency_ms >= 0),
    residency_group    TEXT NOT NULL,
    critical           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE workload_region_allowlist (
    workload_id        BIGINT NOT NULL REFERENCES workload(workload_id) ON DELETE CASCADE,
    region_id          BIGINT NOT NULL REFERENCES geographic_region(region_id),
    PRIMARY KEY (workload_id, region_id)
);

CREATE TABLE placement (
    placement_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_id        BIGINT NOT NULL REFERENCES workload(workload_id),
    zone_id            BIGINT NOT NULL REFERENCES availability_zone(zone_id),
    allocated_units    INTEGER NOT NULL CHECK (allocated_units > 0),
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    placed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workload_id, zone_id)
);

CREATE INDEX placement_workload_active_idx
    ON placement(workload_id, active);

CREATE TABLE replication_link (
    replication_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_region_id   BIGINT NOT NULL REFERENCES geographic_region(region_id),
    target_region_id   BIGINT NOT NULL REFERENCES geographic_region(region_id),
    mode               replication_mode NOT NULL,
    lag_seconds        INTEGER NOT NULL DEFAULT 0 CHECK (lag_seconds >= 0),
    enabled            BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (source_region_id <> target_region_id),
    UNIQUE (source_region_id, target_region_id)
);

CREATE TABLE recovery_objective (
    workload_id        BIGINT PRIMARY KEY REFERENCES workload(workload_id) ON DELETE CASCADE,
    rto_minutes        INTEGER NOT NULL CHECK (rto_minutes >= 0),
    rpo_minutes        INTEGER NOT NULL CHECK (rpo_minutes >= 0),
    detection_minutes  INTEGER NOT NULL CHECK (detection_minutes >= 0),
    failover_minutes   INTEGER NOT NULL CHECK (failover_minutes >= 0),
    tested             BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE infrastructure_event (
    event_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_key          TEXT NOT NULL UNIQUE,
    scope              failure_scope NOT NULL,
    region_id          BIGINT NOT NULL REFERENCES geographic_region(region_id),
    zone_id            BIGINT REFERENCES availability_zone(zone_id),
    resulting_state    health_state NOT NULL,
    occurred_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    details            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (
        (scope = 'region' AND zone_id IS NULL)
        OR (scope = 'zone' AND zone_id IS NOT NULL)
    )
);

-- The trigger prevents a placement from violating capacity, region allowlists,
-- latency limits, or residency rules at insertion time.
-- A concurrent scheduler should additionally serialize placement changes
-- using row locks or an advisory lock for each scheduling operation.
CREATE OR REPLACE FUNCTION validate_placement()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = geo_resilience, public
AS $$
DECLARE
    v_workload workload%ROWTYPE;
    v_zone availability_zone%ROWTYPE;
    v_region geographic_region%ROWTYPE;
    v_used INTEGER;
    v_allowed BOOLEAN;
BEGIN
    SELECT * INTO STRICT v_workload
    FROM workload
    WHERE workload_id = NEW.workload_id;

    SELECT * INTO STRICT v_zone
    FROM availability_zone
    WHERE zone_id = NEW.zone_id
    FOR UPDATE;

    SELECT * INTO STRICT v_region
    FROM geographic_region
    WHERE region_id = v_zone.region_id;

    IF v_zone.state <> 'healthy' OR v_region.state <> 'healthy' THEN
        RAISE EXCEPTION 'Cannot place workload in an unhealthy zone or region';
    END IF;

    IF v_zone.latency_ms > v_workload.maximum_latency_ms THEN
        RAISE EXCEPTION 'Zone latency exceeds workload limit';
    END IF;

    IF v_region.residency_group <> v_workload.residency_group THEN
        RAISE EXCEPTION 'Region violates workload residency requirements';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM workload_region_allowlist a
        WHERE a.workload_id = NEW.workload_id
          AND a.region_id = v_zone.region_id
    ) INTO v_allowed;

    IF NOT v_allowed THEN
        RAISE EXCEPTION 'Region is not in the workload allowlist';
    END IF;

    SELECT COALESCE(SUM(p.allocated_units), 0)::INTEGER
    INTO v_used
    FROM placement p
    WHERE p.zone_id = NEW.zone_id
      AND p.active
      AND (TG_OP <> 'UPDATE' OR p.placement_id <> NEW.placement_id);

    IF v_used + NEW.allocated_units > v_zone.capacity_units THEN
        RAISE EXCEPTION 'Zone capacity would be exceeded';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER placement_integrity_trigger
BEFORE INSERT OR UPDATE OF workload_id, zone_id, allocated_units, active
ON placement
FOR EACH ROW
EXECUTE FUNCTION validate_placement();

-- A unique event key makes retries idempotent at the event-storage layer.
CREATE OR REPLACE FUNCTION apply_infrastructure_event()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = geo_resilience, public
AS $$
BEGIN
    IF NEW.scope = 'region' THEN
        UPDATE geographic_region
        SET state = NEW.resulting_state
        WHERE region_id = NEW.region_id;

        UPDATE availability_zone
        SET state = NEW.resulting_state
        WHERE region_id = NEW.region_id;
    ELSE
        IF NOT EXISTS (
            SELECT 1 FROM availability_zone
            WHERE zone_id = NEW.zone_id
              AND region_id = NEW.region_id
        ) THEN
            RAISE EXCEPTION 'Zone does not belong to the event region';
        END IF;

        UPDATE availability_zone
        SET state = NEW.resulting_state
        WHERE zone_id = NEW.zone_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER infrastructure_event_state_trigger
AFTER INSERT ON infrastructure_event
FOR EACH ROW
EXECUTE FUNCTION apply_infrastructure_event();

INSERT INTO geographic_region
    (region_code, display_name, country_code, residency_group, latitude, longitude)
VALUES
    ('india-west', 'India West', 'IN', 'india', 19.07600, 72.87770),
    ('india-south', 'India South', 'IN', 'india', 12.97160, 77.59460),
    ('singapore', 'Singapore', 'SG', 'apac', 1.35210, 103.81980);

INSERT INTO availability_zone
    (region_id, zone_code, capacity_units, latency_ms)
SELECT r.region_id, v.zone_code, v.capacity_units, v.latency_ms
FROM (
    VALUES
        ('india-west', 'west-a', 8, 10.0),
        ('india-west', 'west-b', 8, 13.0),
        ('india-west', 'west-c', 8, 16.0),
        ('india-south', 'south-a', 10, 22.0),
        ('india-south', 'south-b', 10, 25.0),
        ('india-south', 'south-c', 10, 27.0),
        ('singapore', 'sg-a', 12, 55.0),
        ('singapore', 'sg-b', 12, 58.0)
) AS v(region_code, zone_code, capacity_units, latency_ms)
JOIN geographic_region r USING (region_code);

INSERT INTO workload
    (workload_code, required_units, minimum_zones, maximum_latency_ms, residency_group)
VALUES
    ('payment-api', 9, 3, 30, 'india'),
    ('restricted-ledger', 4, 2, 20, 'india'),
    ('analytics-batch', 6, 2, 70, 'apac');

INSERT INTO workload_region_allowlist (workload_id, region_id)
SELECT w.workload_id, r.region_id
FROM workload w
JOIN geographic_region r
  ON (w.workload_code IN ('payment-api', 'restricted-ledger')
      AND r.region_code IN ('india-west', 'india-south'))
  OR (w.workload_code = 'analytics-batch'
      AND r.region_code IN ('singapore'));

INSERT INTO recovery_objective
    (workload_id, rto_minutes, rpo_minutes, detection_minutes,
     failover_minutes, tested)
SELECT workload_id, 15, 5, 3, 8, TRUE
FROM workload
WHERE workload_code = 'payment-api';

INSERT INTO replication_link
    (source_region_id, target_region_id, mode, lag_seconds)
SELECT source.region_id, target.region_id, 'asynchronous', 90
FROM geographic_region source
JOIN geographic_region target ON target.region_code = 'india-south'
WHERE source.region_code = 'india-west';

-- Allocate nine units across three independent zones.
BEGIN;

SELECT pg_advisory_xact_lock(42001);

INSERT INTO placement (workload_id, zone_id, allocated_units)
SELECT w.workload_id, z.zone_id, v.units
FROM (
    VALUES ('west-a', 3), ('west-b', 3), ('west-c', 3)
) AS v(zone_code, units)
JOIN availability_zone z USING (zone_code)
JOIN workload w ON w.workload_code = 'payment-api';

COMMIT;

-- Aggregate active capacity by region, including zones with no placement.
SELECT
    r.region_code,
    z.zone_code,
    z.state AS zone_state,
    z.capacity_units,
    COALESCE(SUM(p.allocated_units) FILTER (WHERE p.active), 0) AS allocated_units,
    z.capacity_units -
        COALESCE(SUM(p.allocated_units) FILTER (WHERE p.active), 0) AS unallocated_units
FROM geographic_region r
JOIN availability_zone z USING (region_id)
LEFT JOIN placement p USING (zone_id)
GROUP BY r.region_code, z.zone_code, z.state, z.capacity_units
ORDER BY r.region_code, z.zone_code;

-- Identify workloads with insufficient replica distribution.
SELECT
    w.workload_code,
    w.required_units,
    w.minimum_zones,
    COALESCE(SUM(p.allocated_units) FILTER (WHERE p.active), 0) AS allocated_units,
    COUNT(DISTINCT p.zone_id) FILTER (
        WHERE p.active AND z.state = 'healthy' AND r.state = 'healthy'
    ) AS healthy_zones
FROM workload w
LEFT JOIN placement p USING (workload_id)
LEFT JOIN availability_zone z USING (zone_id)
LEFT JOIN geographic_region r USING (region_id)
GROUP BY w.workload_id
HAVING COALESCE(SUM(p.allocated_units) FILTER (WHERE p.active), 0) < w.required_units
    OR COUNT(DISTINCT p.zone_id) FILTER (
        WHERE p.active AND z.state = 'healthy' AND r.state = 'healthy'
    ) < w.minimum_zones;

-- Regional recovery feasibility requires an enabled replication destination.
SELECT
    w.workload_code,
    source.region_code AS source_region,
    target.region_code AS recovery_region,
    link.mode,
    link.lag_seconds,
    objective.rto_minutes,
    objective.rpo_minutes,
    objective.detection_minutes + objective.failover_minutes AS estimated_rto_minutes,
    CEIL(link.lag_seconds / 60.0)::INTEGER AS estimated_rpo_minutes,
    objective.detection_minutes + objective.failover_minutes
        <= objective.rto_minutes AS rto_satisfied,
    CEIL(link.lag_seconds / 60.0)::INTEGER
        <= objective.rpo_minutes AS rpo_satisfied
FROM recovery_objective objective
JOIN workload w USING (workload_id)
JOIN replication_link link ON link.enabled
JOIN geographic_region source ON source.region_id = link.source_region_id
JOIN geographic_region target ON target.region_id = link.target_region_id
JOIN workload_region_allowlist allowed
    ON allowed.workload_id = w.workload_id
   AND allowed.region_id = target.region_id
WHERE source.region_code = 'india-west';

-- Record a zone outage. Repeated event_key insertion is rejected by the unique
-- constraint; callers should use INSERT ... ON CONFLICT DO NOTHING for retries.
INSERT INTO infrastructure_event
    (event_key, scope, region_id, zone_id, resulting_state, details)
SELECT
    'demo-zone-outage-west-b',
    'zone',
    r.region_id,
    z.zone_id,
    'failed',
    '{"cause":"simulated zone power failure"}'::jsonb
FROM geographic_region r
JOIN availability_zone z USING (region_id)
WHERE r.region_code = 'india-west'
  AND z.zone_code = 'west-b';

-- Capacity and health after the simulated outage.
SELECT
    w.workload_code,
    COALESCE(SUM(p.allocated_units) FILTER (
        WHERE p.active AND z.state = 'healthy' AND r.state = 'healthy'
    ), 0) AS surviving_units,
    COUNT(DISTINCT p.zone_id) FILTER (
        WHERE p.active AND z.state = 'healthy' AND r.state = 'healthy'
    ) AS surviving_zones,
    w.required_units,
    w.minimum_zones
FROM workload w
LEFT JOIN placement p USING (workload_id)
LEFT JOIN availability_zone z USING (zone_id)
LEFT JOIN geographic_region r USING (region_id)
GROUP BY w.workload_id;

-- The constraints reject a residency violation. The statement is isolated in a
-- savepoint so the rest of the script can execute after the expected error.
SAVEPOINT before_invalid_placement;

-- This insert intentionally fails because the payment workload does not permit
-- placement in Singapore. Run it separately when demonstrating the error:
-- INSERT INTO placement (workload_id, zone_id, allocated_units)
-- SELECT w.workload_id, z.zone_id, 1
-- FROM workload w CROSS JOIN availability_zone z
-- WHERE w.workload_code = 'payment-api' AND z.zone_code = 'sg-a';

RELEASE SAVEPOINT before_invalid_placement;

-- A healthy zone is not sufficient evidence of regional resilience.
-- Count independent regions hosting active replicas for each workload.
SELECT
    w.workload_code,
    COUNT(DISTINCT z.region_id) FILTER (
        WHERE p.active AND z.state = 'healthy' AND r.state = 'healthy'
    ) AS healthy_regions
FROM workload w
LEFT JOIN placement p USING (workload_id)
LEFT JOIN availability_zone z USING (zone_id)
LEFT JOIN geographic_region r USING (region_id)
GROUP BY w.workload_id
ORDER BY w.workload_code;

COMMIT;
