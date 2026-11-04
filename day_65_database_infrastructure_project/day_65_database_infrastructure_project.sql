-- ============================================================================
-- HIGH AVAILABILITY DATABASE INFRASTRUCTURE
-- PostgreSQL 15+
--
-- Models:
--   1. Database clusters and physical database nodes
--   2. Primary and read-replica topology
--   3. Transaction positions and replication lag
--   4. Backup inventory, retention and verification
--   5. Cache performance and invalidation events
--   6. Infrastructure monitoring and alerts
--   7. Failover and recovery operations
--   8. Availability and disaster-recovery reporting
--
-- IMPORTANT:
-- This script models infrastructure control-plane metadata.
-- It does not configure PostgreSQL streaming replication, install
-- a connection pooler, provision servers, or execute physical backups.
-- Those operations require external infrastructure orchestration.
-- ============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS infrastructure;

SET search_path TO infrastructure, public;

-- ============================================================================
-- 1. DOMAIN TYPES
-- ============================================================================

CREATE TYPE node_role AS ENUM (
    'primary',
    'replica'
);

CREATE TYPE node_state AS ENUM (
    'healthy',
    'degraded',
    'failed',
    'recovering',
    'maintenance'
);

CREATE TYPE backup_type AS ENUM (
    'full',
    'incremental',
    'wal'
);

CREATE TYPE backup_state AS ENUM (
    'pending',
    'running',
    'verified',
    'failed',
    'expired'
);

CREATE TYPE alert_severity AS ENUM (
    'info',
    'warning',
    'critical'
);

CREATE TYPE failover_state AS ENUM (
    'initiated',
    'completed',
    'failed',
    'rolled_back'
);

CREATE TYPE maintenance_state AS ENUM (
    'scheduled',
    'in_progress',
    'completed',
    'cancelled'
);

-- ============================================================================
-- 2. INFRASTRUCTURE POLICY
-- ============================================================================

CREATE TABLE infrastructure_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name VARCHAR(100) NOT NULL UNIQUE,

    maximum_replication_lag_seconds INTEGER NOT NULL DEFAULT 5
        CHECK (maximum_replication_lag_seconds >= 0),

    minimum_healthy_replicas INTEGER NOT NULL DEFAULT 1
        CHECK (minimum_healthy_replicas >= 0),

    maximum_connections INTEGER NOT NULL DEFAULT 100
        CHECK (maximum_connections > 0),

    maximum_cpu_percent NUMERIC(5,2) NOT NULL DEFAULT 85
        CHECK (maximum_cpu_percent BETWEEN 1 AND 100),

    maximum_memory_percent NUMERIC(5,2) NOT NULL DEFAULT 90
        CHECK (maximum_memory_percent BETWEEN 1 AND 100),

    cache_ttl_seconds INTEGER NOT NULL DEFAULT 60
        CHECK (cache_ttl_seconds > 0),

    backup_interval_minutes INTEGER NOT NULL DEFAULT 60
        CHECK (backup_interval_minutes > 0),

    backup_retention_days INTEGER NOT NULL DEFAULT 30
        CHECK (backup_retention_days > 0),

    recovery_point_objective_seconds INTEGER NOT NULL DEFAULT 300
        CHECK (recovery_point_objective_seconds >= 0),

    recovery_time_objective_seconds INTEGER NOT NULL DEFAULT 120
        CHECK (recovery_time_objective_seconds >= 0),

    enforce_cross_zone_replication BOOLEAN NOT NULL DEFAULT TRUE,
    automatic_failover_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO infrastructure_policies (
    policy_name,
    maximum_replication_lag_seconds,
    minimum_healthy_replicas,
    maximum_connections,
    maximum_cpu_percent,
    maximum_memory_percent,
    cache_ttl_seconds,
    backup_interval_minutes,
    backup_retention_days,
    recovery_point_objective_seconds,
    recovery_time_objective_seconds
)
VALUES (
    'production-ha-policy',
    5,
    1,
    200,
    85,
    90,
    60,
    60,
    30,
    300,
    120
);

-- ============================================================================
-- 3. CLUSTERS
-- ============================================================================

CREATE TABLE database_clusters (
    cluster_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_name VARCHAR(120) NOT NULL UNIQUE,
    database_engine VARCHAR(50) NOT NULL DEFAULT 'PostgreSQL',
    engine_version VARCHAR(30) NOT NULL,

    environment VARCHAR(20) NOT NULL
        CHECK (environment IN ('development', 'staging', 'production')),

    policy_id BIGINT NOT NULL
        REFERENCES infrastructure_policies(policy_id),

    cluster_state VARCHAR(20) NOT NULL DEFAULT 'healthy'
        CHECK (cluster_state IN (
            'healthy', 'degraded', 'failed', 'maintenance'
        )),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO database_clusters (
    cluster_name,
    engine_version,
    environment,
    policy_id
)
SELECT
    'production-cluster',
    '18',
    'production',
    policy_id
FROM infrastructure_policies
WHERE policy_name = 'production-ha-policy';

-- ============================================================================
-- 4. DATABASE NODES
-- ============================================================================

CREATE TABLE database_nodes (
    node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id)
        ON DELETE CASCADE,

    node_name VARCHAR(100) NOT NULL,
    hostname INET NOT NULL,

    region VARCHAR(80) NOT NULL,
    availability_zone VARCHAR(80) NOT NULL,

    role node_role NOT NULL,
    state node_state NOT NULL DEFAULT 'healthy',

    transaction_position BIGINT NOT NULL DEFAULT 0
        CHECK (transaction_position >= 0),

    replication_lag_seconds INTEGER NOT NULL DEFAULT 0
        CHECK (replication_lag_seconds >= 0),

    active_connections INTEGER NOT NULL DEFAULT 0
        CHECK (active_connections >= 0),

    cpu_percent NUMERIC(5,2) NOT NULL DEFAULT 10
        CHECK (cpu_percent BETWEEN 0 AND 100),

    memory_percent NUMERIC(5,2) NOT NULL DEFAULT 30
        CHECK (memory_percent BETWEEN 0 AND 100),

    last_heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (cluster_id, node_name),
    UNIQUE (cluster_id, hostname)
);

CREATE INDEX idx_nodes_cluster_role_state
ON database_nodes(cluster_id, role, state);

CREATE INDEX idx_nodes_replication_lag
ON database_nodes(cluster_id, replication_lag_seconds)
WHERE role = 'replica' AND state = 'healthy';

CREATE INDEX idx_nodes_heartbeat
ON database_nodes(last_heartbeat_at);

-- Ensure a cluster has no more than one primary.
CREATE UNIQUE INDEX uq_one_primary_per_cluster
ON database_nodes(cluster_id)
WHERE role = 'primary';

-- Sample topology: one primary and two replicas across zones.
INSERT INTO database_nodes (
    cluster_id,
    node_name,
    hostname,
    region,
    availability_zone,
    role,
    transaction_position
)
SELECT
    cluster_id,
    'db-primary-01',
    '10.0.1.10'::inet,
    'ap-south-1',
    'zone-a',
    'primary',
    1000
FROM database_clusters
WHERE cluster_name = 'production-cluster';

INSERT INTO database_nodes (
    cluster_id,
    node_name,
    hostname,
    region,
    availability_zone,
    role,
    transaction_position,
    replication_lag_seconds
)
SELECT
    cluster_id,
    'db-replica-01',
    '10.0.1.11'::inet,
    'ap-south-1',
    'zone-b',
    'replica',
    998,
    2
FROM database_clusters
WHERE cluster_name = 'production-cluster';

INSERT INTO database_nodes (
    cluster_id,
    node_name,
    hostname,
    region,
    availability_zone,
    role,
    transaction_position,
    replication_lag_seconds
)
SELECT
    cluster_id,
    'db-replica-02',
    '10.0.2.10'::inet,
    'ap-south-2',
    'zone-c',
    'replica',
    995,
    5
FROM database_clusters
WHERE cluster_name = 'production-cluster';

-- ============================================================================
-- 5. TRANSACTION AND REPLICATION HISTORY
-- ============================================================================

CREATE TABLE replication_events (
    replication_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    source_node_id BIGINT NOT NULL
        REFERENCES database_nodes(node_id),

    replica_node_id BIGINT NOT NULL
        REFERENCES database_nodes(node_id),

    source_position BIGINT NOT NULL
        CHECK (source_position >= 0),

    applied_position BIGINT NOT NULL
        CHECK (applied_position >= 0),

    lag_seconds INTEGER NOT NULL
        CHECK (lag_seconds >= 0),

    successful BOOLEAN NOT NULL DEFAULT TRUE,

    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (source_node_id <> replica_node_id),
    CHECK (applied_position <= source_position)
);

CREATE INDEX idx_replication_events_cluster_time
ON replication_events(cluster_id, observed_at DESC);

CREATE INDEX idx_replication_events_replica_time
ON replication_events(replica_node_id, observed_at DESC);

INSERT INTO replication_events (
    cluster_id,
    source_node_id,
    replica_node_id,
    source_position,
    applied_position,
    lag_seconds,
    successful
)
SELECT
    p.cluster_id,
    p.node_id,
    r.node_id,
    p.transaction_position,
    r.transaction_position,
    r.replication_lag_seconds,
    TRUE
FROM database_nodes p
JOIN database_nodes r
    ON r.cluster_id = p.cluster_id
WHERE p.role = 'primary'
AND r.role = 'replica';

-- ============================================================================
-- 6. BACKUP INVENTORY
-- ============================================================================

CREATE TABLE backups (
    backup_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    source_node_id BIGINT NOT NULL
        REFERENCES database_nodes(node_id),

    backup_name VARCHAR(150) NOT NULL,
    backup_type backup_type NOT NULL,

    state backup_state NOT NULL DEFAULT 'pending',

    parent_backup_id BIGINT
        REFERENCES backups(backup_id),

    transaction_position BIGINT NOT NULL
        CHECK (transaction_position >= 0),

    storage_uri TEXT NOT NULL,

    checksum_algorithm VARCHAR(20) NOT NULL DEFAULT 'SHA256'
        CHECK (checksum_algorithm IN ('SHA256', 'SHA512')),

    checksum VARCHAR(128),

    size_bytes BIGINT NOT NULL DEFAULT 0
        CHECK (size_bytes >= 0),

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    verified_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (cluster_id, backup_name),

    CHECK (
        (backup_type = 'incremental' AND parent_backup_id IS NOT NULL)
        OR
        (backup_type <> 'incremental' AND parent_backup_id IS NULL)
    ),

    CHECK (
        completed_at IS NULL
        OR started_at IS NULL
        OR completed_at >= started_at
    ),

    CHECK (
        verified_at IS NULL
        OR completed_at IS NOT NULL
    )
);

CREATE INDEX idx_backups_cluster_created
ON backups(cluster_id, created_at DESC);

CREATE INDEX idx_backups_verified
ON backups(cluster_id, created_at DESC)
WHERE state = 'verified';

CREATE INDEX idx_backups_expiration
ON backups(expires_at)
WHERE state = 'verified';

-- Ensure incremental backup parents are verified full backups
-- belonging to the same cluster.
CREATE OR REPLACE FUNCTION validate_backup_parent()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent backups%ROWTYPE;
BEGIN
    IF NEW.backup_type = 'incremental' THEN
        SELECT *
        INTO parent
        FROM backups
        WHERE backup_id = NEW.parent_backup_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Parent backup does not exist';
        END IF;

        IF parent.cluster_id <> NEW.cluster_id THEN
            RAISE EXCEPTION 'Parent belongs to another cluster';
        END IF;

        IF parent.backup_type <> 'full'
           OR parent.state <> 'verified' THEN
            RAISE EXCEPTION
                'Incremental backup requires a verified full backup';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_backup_parent
BEFORE INSERT OR UPDATE OF backup_type, parent_backup_id, cluster_id
ON backups
FOR EACH ROW
EXECUTE FUNCTION validate_backup_parent();

-- Backup lifecycle integrity.
CREATE OR REPLACE FUNCTION validate_backup_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'verified'
       AND NEW.state NOT IN ('verified', 'expired') THEN
        RAISE EXCEPTION 'Verified backup cannot return to execution';
    END IF;

    IF NEW.state = 'verified' THEN
        IF NEW.checksum IS NULL
           OR NEW.completed_at IS NULL
           OR NEW.verified_at IS NULL THEN
            RAISE EXCEPTION
                'Verified backup requires checksum and completion timestamps';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_backup_transition
BEFORE UPDATE ON backups
FOR EACH ROW
EXECUTE FUNCTION validate_backup_transition();

-- ============================================================================
-- 7. BACKUP SAMPLE DATA
-- ============================================================================

INSERT INTO backups (
    cluster_id,
    source_node_id,
    backup_name,
    backup_type,
    state,
    transaction_position,
    storage_uri,
    checksum,
    size_bytes,
    started_at,
    completed_at,
    verified_at,
    expires_at
)
SELECT
    c.cluster_id,
    n.node_id,
    'production-full-001',
    'full',
    'verified',
    n.transaction_position,
    's3://example-backups/production/full-001',
    repeat('a', 64),
    104857600,
    NOW() - INTERVAL '30 minutes',
    NOW() - INTERVAL '20 minutes',
    NOW() - INTERVAL '19 minutes',
    NOW() + INTERVAL '30 days'
FROM database_clusters c
JOIN database_nodes n
    ON n.cluster_id = c.cluster_id
WHERE c.cluster_name = 'production-cluster'
AND n.role = 'primary';

INSERT INTO backups (
    cluster_id,
    source_node_id,
    backup_name,
    backup_type,
    state,
    parent_backup_id,
    transaction_position,
    storage_uri,
    checksum,
    size_bytes,
    started_at,
    completed_at,
    verified_at,
    expires_at
)
SELECT
    b.cluster_id,
    b.source_node_id,
    'production-incremental-001',
    'incremental',
    'verified',
    b.backup_id,
    b.transaction_position,
    's3://example-backups/production/incremental-001',
    repeat('b', 64),
    5242880,
    NOW() - INTERVAL '10 minutes',
    NOW() - INTERVAL '8 minutes',
    NOW() - INTERVAL '7 minutes',
    NOW() + INTERVAL '30 days'
FROM backups b
WHERE b.backup_name = 'production-full-001';

-- ============================================================================
-- 8. BACKUP RESTORE TESTS
-- ============================================================================

CREATE TABLE restore_tests (
    restore_test_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    backup_id BIGINT NOT NULL REFERENCES backups(backup_id),

    target_environment VARCHAR(30) NOT NULL,

    state VARCHAR(20) NOT NULL
        CHECK (state IN ('pending', 'running', 'passed', 'failed')),

    restored_position BIGINT,
    duration_seconds NUMERIC(12,3),

    tested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    notes TEXT,

    CHECK (
        duration_seconds IS NULL OR duration_seconds >= 0
    )
);

CREATE INDEX idx_restore_tests_backup
ON restore_tests(backup_id, tested_at DESC);

INSERT INTO restore_tests (
    backup_id,
    target_environment,
    state,
    restored_position,
    duration_seconds,
    notes
)
SELECT
    backup_id,
    'isolated-recovery',
    'passed',
    transaction_position,
    42.5,
    'Checksum verification and isolated restoration completed'
FROM backups
WHERE backup_name = 'production-full-001';

-- ============================================================================
-- 9. CACHE OBSERVABILITY
-- ============================================================================

CREATE TABLE cache_metrics (
    cache_metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    cache_name VARCHAR(100) NOT NULL,

    hits BIGINT NOT NULL DEFAULT 0 CHECK (hits >= 0),
    misses BIGINT NOT NULL DEFAULT 0 CHECK (misses >= 0),

    evictions BIGINT NOT NULL DEFAULT 0 CHECK (evictions >= 0),

    invalidations BIGINT NOT NULL DEFAULT 0
        CHECK (invalidations >= 0),

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cache_metrics_cluster_time
ON cache_metrics(cluster_id, recorded_at DESC);

INSERT INTO cache_metrics (
    cluster_id,
    cache_name,
    hits,
    misses,
    evictions,
    invalidations
)
SELECT
    cluster_id,
    'application-cache',
    8500,
    1500,
    100,
    250
FROM database_clusters
WHERE cluster_name = 'production-cluster';

CREATE TABLE cache_invalidation_events (
    invalidation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    cache_key_hash VARCHAR(128) NOT NULL,

    invalidation_reason VARCHAR(50) NOT NULL
        CHECK (invalidation_reason IN (
            'write',
            'ttl_expiration',
            'manual',
            'failover',
            'security'
        )),

    invalidated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cache_invalidations_cluster_time
ON cache_invalidation_events(cluster_id, invalidated_at DESC);

-- ============================================================================
-- 10. MONITORING METRICS AND ALERTS
-- ============================================================================

CREATE TABLE monitoring_metrics (
    metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    node_id BIGINT
        REFERENCES database_nodes(node_id),

    metric_name VARCHAR(100) NOT NULL,

    metric_value NUMERIC(18,4) NOT NULL,

    metric_unit VARCHAR(30) NOT NULL,

    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_monitoring_cluster_metric_time
ON monitoring_metrics(
    cluster_id,
    metric_name,
    collected_at DESC
);

CREATE INDEX idx_monitoring_node_time
ON monitoring_metrics(node_id, collected_at DESC);

CREATE TABLE infrastructure_alerts (
    alert_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    node_id BIGINT
        REFERENCES database_nodes(node_id),

    alert_type VARCHAR(100) NOT NULL,

    severity alert_severity NOT NULL,

    description TEXT NOT NULL,

    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,

    resolved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_unresolved
ON infrastructure_alerts(cluster_id, severity, created_at DESC)
WHERE resolved_at IS NULL;

INSERT INTO monitoring_metrics (
    cluster_id,
    node_id,
    metric_name,
    metric_value,
    metric_unit
)
SELECT
    cluster_id,
    node_id,
    'cpu_percent',
    cpu_percent,
    'percent'
FROM database_nodes;

INSERT INTO monitoring_metrics (
    cluster_id,
    node_id,
    metric_name,
    metric_value,
    metric_unit
)
SELECT
    cluster_id,
    node_id,
    'replication_lag',
    replication_lag_seconds,
    'seconds'
FROM database_nodes
WHERE role = 'replica';

-- ============================================================================
-- 11. FAILOVER HISTORY
-- ============================================================================

CREATE TABLE failover_events (
    failover_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    previous_primary_id BIGINT NOT NULL
        REFERENCES database_nodes(node_id),

    promoted_node_id BIGINT NOT NULL
        REFERENCES database_nodes(node_id),

    state failover_state NOT NULL DEFAULT 'initiated',

    previous_position BIGINT NOT NULL
        CHECK (previous_position >= 0),

    promoted_position BIGINT NOT NULL
        CHECK (promoted_position >= 0),

    data_loss_transactions BIGINT NOT NULL DEFAULT 0
        CHECK (data_loss_transactions >= 0),

    initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    failure_reason TEXT,

    CHECK (previous_primary_id <> promoted_node_id),

    CHECK (
        completed_at IS NULL OR completed_at >= initiated_at
    )
);

CREATE INDEX idx_failover_cluster_time
ON failover_events(cluster_id, initiated_at DESC);

-- ============================================================================
-- 12. NODE HEALTH VALIDATION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_node_health()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    policy infrastructure_policies%ROWTYPE;
BEGIN
    SELECT p.*
    INTO policy
    FROM infrastructure_policies p
    JOIN database_clusters c
        ON c.policy_id = p.policy_id
    WHERE c.cluster_id = NEW.cluster_id;

    IF NEW.role = 'replica'
       AND NEW.replication_lag_seconds >
           policy.maximum_replication_lag_seconds
       AND NEW.state = 'healthy' THEN

        NEW.state := 'degraded';
    END IF;

    IF NEW.active_connections > policy.maximum_connections THEN
        RAISE EXCEPTION
            'Connection count exceeds cluster policy';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_node_health
BEFORE INSERT OR UPDATE OF
    role,
    state,
    replication_lag_seconds,
    active_connections
ON database_nodes
FOR EACH ROW
EXECUTE FUNCTION validate_node_health();

-- ============================================================================
-- 13. TRANSACTIONAL FAILOVER PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE promote_replica(
    p_cluster_id BIGINT,
    p_replica_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    old_primary database_nodes%ROWTYPE;
    candidate database_nodes%ROWTYPE;
    current_policy infrastructure_policies%ROWTYPE;
    event_id BIGINT;
BEGIN
    -- Serialize failover operations for one cluster.
    PERFORM pg_advisory_xact_lock(p_cluster_id);

    SELECT p.*
    INTO current_policy
    FROM infrastructure_policies p
    JOIN database_clusters c
        ON c.policy_id = p.policy_id
    WHERE c.cluster_id = p_cluster_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cluster policy not found';
    END IF;

    IF NOT current_policy.automatic_failover_enabled THEN
        RAISE EXCEPTION 'Automatic failover is disabled';
    END IF;

    SELECT *
    INTO old_primary
    FROM database_nodes
    WHERE cluster_id = p_cluster_id
      AND role = 'primary'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No primary found';
    END IF;

    SELECT *
    INTO candidate
    FROM database_nodes
    WHERE node_id = p_replica_id
      AND cluster_id = p_cluster_id
      AND role = 'replica'
      AND state = 'healthy'
      AND replication_lag_seconds <=
          current_policy.maximum_replication_lag_seconds
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Candidate is not an eligible healthy replica';
    END IF;

    -- The previous primary must stop being writable before promotion.
    UPDATE database_nodes
    SET role = 'replica',
        state = 'failed'
    WHERE node_id = old_primary.node_id;

    UPDATE database_nodes
    SET role = 'primary',
        replication_lag_seconds = 0
    WHERE node_id = candidate.node_id;

    INSERT INTO failover_events (
        cluster_id,
        previous_primary_id,
        promoted_node_id,
        state,
        previous_position,
        promoted_position,
        data_loss_transactions,
        completed_at
    )
    VALUES (
        p_cluster_id,
        old_primary.node_id,
        candidate.node_id,
        'completed',
        old_primary.transaction_position,
        candidate.transaction_position,
        GREATEST(
            0,
            old_primary.transaction_position -
            candidate.transaction_position
        ),
        NOW()
    )
    RETURNING failover_id INTO event_id;

    -- Cached application values must be invalidated after promotion.
    INSERT INTO cache_invalidation_events (
        cluster_id,
        cache_key_hash,
        invalidation_reason
    )
    VALUES (
        p_cluster_id,
        'ALL',
        'failover'
    );

    UPDATE database_clusters
    SET cluster_state = 'healthy'
    WHERE cluster_id = p_cluster_id;

    RAISE NOTICE
        'Failover event % completed: node % promoted',
        event_id,
        candidate.node_name;
END;
$$;

-- ============================================================================
-- 14. RECOVERY PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE rejoin_failed_node(
    p_node_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    target database_nodes%ROWTYPE;
    leader database_nodes%ROWTYPE;
BEGIN
    SELECT *
    INTO target
    FROM database_nodes
    WHERE node_id = p_node_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Recovery node not found';
    END IF;

    SELECT *
    INTO leader
    FROM database_nodes
    WHERE cluster_id = target.cluster_id
      AND role = 'primary'
      AND state = 'healthy'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No healthy primary available for recovery';
    END IF;

    IF target.node_id = leader.node_id THEN
        RAISE EXCEPTION 'Cannot recover the active primary';
    END IF;

    UPDATE database_nodes
    SET state = 'recovering',
        role = 'replica'
    WHERE node_id = target.node_id;

    -- This metadata model represents a completed resynchronization.
    -- Production recovery must use a consistent base backup and WAL replay.
    UPDATE database_nodes
    SET transaction_position = leader.transaction_position,
        replication_lag_seconds = 0,
        state = 'healthy',
        last_heartbeat_at = NOW()
    WHERE node_id = target.node_id;
END;
$$;

-- ============================================================================
-- 15. REPLICATION MONITORING PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE record_replication_metrics(
    p_cluster_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    primary_record database_nodes%ROWTYPE;
    replica_record database_nodes%ROWTYPE;
BEGIN
    SELECT *
    INTO primary_record
    FROM database_nodes
    WHERE cluster_id = p_cluster_id
      AND role = 'primary'
      AND state = 'healthy';

    IF NOT FOUND THEN
        INSERT INTO infrastructure_alerts (
            cluster_id,
            alert_type,
            severity,
            description
        )
        VALUES (
            p_cluster_id,
            'PRIMARY_UNAVAILABLE',
            'critical',
            'No healthy primary was found during monitoring'
        );

        RETURN;
    END IF;

    FOR replica_record IN
        SELECT *
        FROM database_nodes
        WHERE cluster_id = p_cluster_id
          AND role = 'replica'
    LOOP
        INSERT INTO replication_events (
            cluster_id,
            source_node_id,
            replica_node_id,
            source_position,
            applied_position,
            lag_seconds,
            successful
        )
        VALUES (
            p_cluster_id,
            primary_record.node_id,
            replica_record.node_id,
            primary_record.transaction_position,
            replica_record.transaction_position,
            replica_record.replication_lag_seconds,
            replica_record.state = 'healthy'
        );

        INSERT INTO monitoring_metrics (
            cluster_id,
            node_id,
            metric_name,
            metric_value,
            metric_unit
        )
        VALUES (
            p_cluster_id,
            replica_record.node_id,
            'replication_lag',
            replica_record.replication_lag_seconds,
            'seconds'
        );
    END LOOP;
END;
$$;

-- ============================================================================
-- 16. AVAILABILITY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW cluster_availability AS
SELECT
    c.cluster_id,
    c.cluster_name,
    c.environment,
    c.cluster_state,

    COUNT(n.node_id) AS total_nodes,

    COUNT(n.node_id) FILTER (
        WHERE n.state = 'healthy'
    ) AS healthy_nodes,

    COUNT(n.node_id) FILTER (
        WHERE n.role = 'primary'
          AND n.state = 'healthy'
    ) AS healthy_primaries,

    COUNT(n.node_id) FILTER (
        WHERE n.role = 'replica'
          AND n.state = 'healthy'
          AND n.replication_lag_seconds <=
              p.maximum_replication_lag_seconds
    ) AS healthy_replicas,

    p.minimum_healthy_replicas,

    (
        COUNT(n.node_id) FILTER (
            WHERE n.role = 'primary'
              AND n.state = 'healthy'
        ) = 1
    ) AS write_available,

    (
        COUNT(n.node_id) FILTER (
            WHERE n.role = 'primary'
              AND n.state = 'healthy'
        ) = 1
        OR
        COUNT(n.node_id) FILTER (
            WHERE n.role = 'replica'
              AND n.state = 'healthy'
              AND n.replication_lag_seconds <=
                  p.maximum_replication_lag_seconds
        ) > 0
    ) AS read_available,

    (
        COUNT(n.node_id) FILTER (
            WHERE n.role = 'replica'
              AND n.state = 'healthy'
              AND n.replication_lag_seconds <=
                  p.maximum_replication_lag_seconds
        ) >= p.minimum_healthy_replicas
    ) AS replica_policy_satisfied

FROM database_clusters c
JOIN infrastructure_policies p
    ON p.policy_id = c.policy_id
LEFT JOIN database_nodes n
    ON n.cluster_id = c.cluster_id
GROUP BY
    c.cluster_id,
    c.cluster_name,
    c.environment,
    c.cluster_state,
    p.minimum_healthy_replicas,
    p.maximum_replication_lag_seconds;

-- ============================================================================
-- 17. BACKUP RECOVERY-POINT REPORT
-- ============================================================================

CREATE OR REPLACE VIEW backup_recovery_report AS
SELECT
    c.cluster_id,
    c.cluster_name,

    MAX(b.completed_at) FILTER (
        WHERE b.state = 'verified'
          AND b.backup_type = 'full'
    ) AS latest_verified_full_backup,

    MAX(b.completed_at) FILTER (
        WHERE b.state = 'verified'
    ) AS latest_verified_backup,

    COUNT(b.backup_id) FILTER (
        WHERE b.state = 'verified'
    ) AS verified_backup_count,

    COUNT(b.backup_id) FILTER (
        WHERE b.state = 'failed'
    ) AS failed_backup_count,

    MAX(b.transaction_position) FILTER (
        WHERE b.state = 'verified'
    ) AS latest_verified_position,

    EXTRACT(
        EPOCH FROM (
            NOW() - MAX(b.completed_at) FILTER (
                WHERE b.state = 'verified'
            )
        )
    )::BIGINT AS seconds_since_last_verified_backup,

    p.recovery_point_objective_seconds,

    (
        MAX(b.completed_at) FILTER (
            WHERE b.state = 'verified'
        ) >= NOW() -
            make_interval(
                secs => p.recovery_point_objective_seconds
            )
    ) AS recovery_point_objective_met

FROM database_clusters c
JOIN infrastructure_policies p
    ON p.policy_id = c.policy_id
LEFT JOIN backups b
    ON b.cluster_id = c.cluster_id
GROUP BY
    c.cluster_id,
    c.cluster_name,
    p.recovery_point_objective_seconds;

-- ============================================================================
-- 18. CACHE PERFORMANCE REPORT
-- ============================================================================

CREATE OR REPLACE VIEW cache_performance_report AS
SELECT
    c.cluster_id,
    c.cluster_name,
    m.cache_name,

    SUM(m.hits) AS total_hits,
    SUM(m.misses) AS total_misses,

    SUM(m.evictions) AS total_evictions,
    SUM(m.invalidations) AS total_invalidations,

    ROUND(
        100.0 * SUM(m.hits) /
        NULLIF(SUM(m.hits) + SUM(m.misses), 0),
        2
    ) AS cache_hit_percentage

FROM database_clusters c
JOIN cache_metrics m
    ON m.cluster_id = c.cluster_id
GROUP BY
    c.cluster_id,
    c.cluster_name,
    m.cache_name;

-- ============================================================================
-- 19. MONITORING ALERT EVALUATION
-- ============================================================================

CREATE OR REPLACE FUNCTION evaluate_node_metrics()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    node_record database_nodes%ROWTYPE;
    policy infrastructure_policies%ROWTYPE;
    alert_count INTEGER := 0;
    current_severity alert_severity;
    current_description TEXT;
BEGIN
    FOR node_record IN
        SELECT n.*
        FROM database_nodes n
    LOOP
        SELECT p.*
        INTO policy
        FROM infrastructure_policies p
        JOIN database_clusters c
            ON c.policy_id = p.policy_id
        WHERE c.cluster_id = node_record.cluster_id;

        IF node_record.state = 'failed' THEN
            current_severity := 'critical';
            current_description := 'Database node has failed';

        ELSIF node_record.cpu_percent >= policy.maximum_cpu_percent THEN
            current_severity := 'warning';
            current_description := 'CPU threshold exceeded';

        ELSIF node_record.memory_percent >=
              policy.maximum_memory_percent THEN
            current_severity := 'warning';
            current_description := 'Memory threshold exceeded';

        ELSIF node_record.role = 'replica'
          AND node_record.replication_lag_seconds >
              policy.maximum_replication_lag_seconds THEN
            current_severity := 'warning';
            current_description := 'Replication lag threshold exceeded';

        ELSIF node_record.last_heartbeat_at <
              NOW() - INTERVAL '30 seconds' THEN
            current_severity := 'critical';
            current_description := 'Node heartbeat is stale';

        ELSE
            CONTINUE;
        END IF;

        INSERT INTO infrastructure_alerts (
            cluster_id,
            node_id,
            alert_type,
            severity,
            description
        )
        VALUES (
            node_record.cluster_id,
            node_record.node_id,
            'NODE_HEALTH',
            current_severity,
            current_description
        );

        alert_count := alert_count + 1;
    END LOOP;

    RETURN alert_count;
END;
$$;

-- ============================================================================
-- 20. MAINTENANCE WINDOWS
-- ============================================================================

CREATE TABLE maintenance_windows (
    maintenance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cluster_id BIGINT NOT NULL
        REFERENCES database_clusters(cluster_id),

    node_id BIGINT
        REFERENCES database_nodes(node_id),

    maintenance_reason TEXT NOT NULL,

    state maintenance_state NOT NULL DEFAULT 'scheduled',

    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (ends_at > starts_at)
);

CREATE INDEX idx_maintenance_schedule
ON maintenance_windows(cluster_id, starts_at, ends_at);

-- ============================================================================
-- 21. TRANSACTIONAL SAMPLE WORKFLOW
-- ============================================================================

-- Record a new write position and update replica lag.
BEGIN;

UPDATE database_nodes
SET transaction_position = transaction_position + 25
WHERE cluster_id = (
    SELECT cluster_id
    FROM database_clusters
    WHERE cluster_name = 'production-cluster'
)
AND role = 'primary'
AND state = 'healthy';

UPDATE database_nodes
SET replication_lag_seconds = replication_lag_seconds + 3
WHERE cluster_id = (
    SELECT cluster_id
    FROM database_clusters
    WHERE cluster_name = 'production-cluster'
)
AND role = 'replica'
AND state = 'healthy';

COMMIT;

-- Simulate replica synchronization.
UPDATE database_nodes r
SET transaction_position = p.transaction_position,
    replication_lag_seconds = 0,
    state = 'healthy'
FROM database_nodes p
WHERE r.cluster_id = p.cluster_id
AND p.cluster_id = (
    SELECT cluster_id
    FROM database_clusters
    WHERE cluster_name = 'production-cluster'
)
AND p.role = 'primary'
AND r.role = 'replica'
AND r.node_name = 'db-replica-01';

-- ============================================================================
-- 22. REPORTING AND EVALUATION QUERIES
-- ============================================================================

-- A. Cluster availability.
SELECT *
FROM cluster_availability
ORDER BY cluster_name;

-- B. Node topology and current health.
SELECT
    c.cluster_name,
    n.node_name,
    n.hostname,
    n.region,
    n.availability_zone,
    n.role,
    n.state,
    n.transaction_position,
    n.replication_lag_seconds,
    n.active_connections
FROM database_nodes n
JOIN database_clusters c
    ON c.cluster_id = n.cluster_id
ORDER BY
    c.cluster_name,
    n.role,
    n.node_name;

-- C. Replication lag evaluation.
SELECT
    n.node_name,
    n.replication_lag_seconds,
    p.maximum_replication_lag_seconds,
    CASE
        WHEN n.state <> 'healthy' THEN 'UNAVAILABLE'
        WHEN n.replication_lag_seconds <=
             p.maximum_replication_lag_seconds THEN 'ELIGIBLE'
        ELSE 'LAGGING'
    END AS replica_eligibility
FROM database_nodes n
JOIN database_clusters c
    ON c.cluster_id = n.cluster_id
JOIN infrastructure_policies p
    ON p.policy_id = c.policy_id
WHERE n.role = 'replica';

-- D. Backup inventory and restore validation.
SELECT
    b.backup_name,
    b.backup_type,
    b.state,
    b.transaction_position,
    b.checksum,
    b.size_bytes,
    b.created_at,
    rt.state AS restore_test_state,
    rt.duration_seconds
FROM backups b
LEFT JOIN restore_tests rt
    ON rt.backup_id = b.backup_id
ORDER BY b.created_at DESC;

-- E. Backup recovery-point evaluation.
SELECT *
FROM backup_recovery_report;

-- F. Cache hit ratio.
SELECT *
FROM cache_performance_report;

-- G. Unresolved infrastructure alerts.
SELECT
    a.alert_id,
    c.cluster_name,
    n.node_name,
    a.alert_type,
    a.severity,
    a.description,
    a.created_at
FROM infrastructure_alerts a
JOIN database_clusters c
    ON c.cluster_id = a.cluster_id
LEFT JOIN database_nodes n
    ON n.node_id = a.node_id
WHERE a.resolved_at IS NULL
ORDER BY
    CASE a.severity
        WHEN 'critical' THEN 1
        WHEN 'warning' THEN 2
        ELSE 3
    END,
    a.created_at DESC;

-- H. Historical replication performance.
WITH replication_summary AS (
    SELECT
        replica_node_id,
        AVG(lag_seconds) AS average_lag,
        MAX(lag_seconds) AS maximum_lag,
        COUNT(*) AS observations,
        COUNT(*) FILTER (
            WHERE successful
        ) AS successful_observations
    FROM replication_events
    GROUP BY replica_node_id
)
SELECT
    n.node_name,
    ROUND(rs.average_lag, 2) AS average_lag_seconds,
    rs.maximum_lag,
    rs.observations,
    rs.successful_observations
FROM replication_summary rs
JOIN database_nodes n
    ON n.node_id = rs.replica_node_id;

-- I. Connection utilization.
SELECT
    node_name,
    active_connections,
    p.maximum_connections,
    ROUND(
        100.0 * active_connections /
        p.maximum_connections,
        2
    ) AS utilization_percentage
FROM database_nodes n
JOIN database_clusters c
    ON c.cluster_id = n.cluster_id
JOIN infrastructure_policies p
    ON p.policy_id = c.policy_id;

-- J. Failover performance and data-loss reporting.
SELECT
    c.cluster_name,
    f.previous_primary_id,
    f.promoted_node_id,
    f.state,
    f.previous_position,
    f.promoted_position,
    f.data_loss_transactions,
    EXTRACT(
        EPOCH FROM (f.completed_at - f.initiated_at)
    ) AS failover_duration_seconds
FROM failover_events f
JOIN database_clusters c
    ON c.cluster_id = f.cluster_id
ORDER BY f.initiated_at DESC;

-- K. Eligible failover candidates.
SELECT
    n.node_id,
    n.node_name,
    n.transaction_position,
    n.replication_lag_seconds,
    n.availability_zone
FROM database_nodes n
JOIN database_clusters c
    ON c.cluster_id = n.cluster_id
JOIN infrastructure_policies p
    ON p.policy_id = c.policy_id
WHERE n.role = 'replica'
AND n.state = 'healthy'
AND n.replication_lag_seconds <=
    p.maximum_replication_lag_seconds
ORDER BY
    n.transaction_position DESC,
    n.active_connections ASC;

-- L. Execute monitoring evaluation.
SELECT evaluate_node_metrics() AS generated_alerts;

-- ============================================================================
-- 23. FAILOVER DEMONSTRATION
-- ============================================================================
--
-- Run the following transaction to promote replica db-replica-01.
-- The transaction locks the cluster and node records, prevents duplicate
-- primary assignment through the unique partial index, records failover
-- metadata and invalidates cached application data.
--
-- This is a control-plane demonstration. A production deployment must
-- fence the old primary and coordinate actual replication promotion.
--
-- ============================================================================

-- Uncomment to execute:
--
-- BEGIN;
--
-- CALL promote_replica(
--     (
--         SELECT cluster_id
--         FROM database_clusters
--         WHERE cluster_name = 'production-cluster'
--     ),
--     (
--         SELECT node_id
--         FROM database_nodes
--         WHERE node_name = 'db-replica-01'
--     )
-- );
--
-- COMMIT;

-- ============================================================================
-- 24. RECOVERY DEMONSTRATION
-- ============================================================================
--
-- After failover, the old primary must be rebuilt or resynchronized.
-- It must never rejoin as an independent writable primary.
--
-- Uncomment after a successful failover:
--
-- CALL rejoin_failed_node(
--     (
--         SELECT node_id
--         FROM database_nodes
--         WHERE node_name = 'db-primary-01'
--     )
-- );
--
-- ============================================================================

-- ============================================================================
-- 25. BACKUP RETENTION EVALUATION
-- ============================================================================

WITH backup_dependencies AS (
    SELECT
        parent_backup_id,
        COUNT(*) AS dependent_backups
    FROM backups
    WHERE parent_backup_id IS NOT NULL
      AND state = 'verified'
    GROUP BY parent_backup_id
)
SELECT
    b.backup_id,
    b.backup_name,
    b.backup_type,
    b.state,
    b.expires_at,
    COALESCE(d.dependent_backups, 0) AS dependent_backups,
    CASE
        WHEN b.state <> 'verified' THEN 'NOT_RETAINABLE'
        WHEN b.expires_at <= NOW()
         AND COALESCE(d.dependent_backups, 0) = 0
            THEN 'ELIGIBLE_FOR_EXPIRATION'
        WHEN b.expires_at <= NOW()
            THEN 'RETAIN_FOR_DEPENDENCIES'
        ELSE 'WITHIN_RETENTION'
    END AS retention_decision
FROM backups b
LEFT JOIN backup_dependencies d
    ON d.parent_backup_id = b.backup_id
ORDER BY b.created_at;

-- ============================================================================
-- 26. INFRASTRUCTURE SUMMARY
-- ============================================================================

CREATE OR REPLACE VIEW infrastructure_summary AS
SELECT
    a.cluster_id,
    a.cluster_name,
    a.total_nodes,
    a.healthy_nodes,
    a.healthy_primaries,
    a.healthy_replicas,
    a.write_available,
    a.read_available,
    a.replica_policy_satisfied,
    COALESCE(cr.cache_hit_percentage, 0) AS cache_hit_percentage,
    COALESCE(br.verified_backup_count, 0) AS verified_backups,
    br.seconds_since_last_verified_backup,
    br.recovery_point_objective_met
FROM cluster_availability a
LEFT JOIN cache_performance_report cr
    ON cr.cluster_id = a.cluster_id
LEFT JOIN backup_recovery_report br
    ON br.cluster_id = a.cluster_id;

SELECT *
FROM infrastructure_summary;

COMMIT;

-- ============================================================================
-- END OF DATABASE INFRASTRUCTURE SCRIPT
-- ============================================================================
