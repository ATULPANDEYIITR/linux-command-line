-- Database Infrastructure Fundamentals
-- PostgreSQL 14+ compatible.
--
-- The schema models:
-- repositories of database infrastructure concepts rather than a generic
-- CRUD application. It distinguishes storage, transactions, WAL records,
-- replication, server availability, and operational health.

DROP SCHEMA IF EXISTS dbinfra CASCADE;
CREATE SCHEMA dbinfra;

SET search_path = dbinfra, public;

CREATE TYPE server_role AS ENUM ('PRIMARY', 'REPLICA');
CREATE TYPE server_state AS ENUM ('ONLINE', 'OFFLINE', 'RECOVERING');
CREATE TYPE transaction_state AS ENUM ('ACTIVE', 'COMMITTED', 'ABORTED');
CREATE TYPE replication_mode AS ENUM ('ASYNC', 'SYNC');
CREATE TYPE wal_operation AS ENUM ('INSERT', 'UPDATE', 'DELETE');

CREATE TABLE database_cluster (
    cluster_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_name TEXT NOT NULL UNIQUE,
    replication_mode replication_mode NOT NULL DEFAULT 'ASYNC',
    synchronous_replica_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (synchronous_replica_count >= 0)
);

CREATE TABLE database_server (
    server_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES database_cluster(cluster_id)
        ON DELETE CASCADE,
    server_name TEXT NOT NULL UNIQUE,
    role server_role NOT NULL,
    state server_state NOT NULL DEFAULT 'ONLINE',
    region TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    last_replayed_lsn BIGINT NOT NULL DEFAULT 0,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (cluster_id, server_name),
    CHECK (priority >= 0),
    CHECK (last_replayed_lsn >= 0)
);

CREATE UNIQUE INDEX one_primary_per_cluster
ON database_server(cluster_id)
WHERE role = 'PRIMARY';

CREATE INDEX idx_database_server_cluster_state
ON database_server(cluster_id, state);

CREATE TABLE storage_page (
    page_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    server_id BIGINT NOT NULL REFERENCES database_server(server_id)
        ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    page_capacity INTEGER NOT NULL DEFAULT 100,
    used_slots INTEGER NOT NULL DEFAULT 0,
    checksum TEXT,
    UNIQUE (server_id, page_number),
    CHECK (page_number >= 0),
    CHECK (page_capacity > 0),
    CHECK (used_slots >= 0),
    CHECK (used_slots <= page_capacity)
);

CREATE TABLE application_record (
    record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    server_id BIGINT NOT NULL REFERENCES database_server(server_id)
        ON DELETE CASCADE,
    page_id BIGINT REFERENCES storage_page(page_id)
        ON DELETE SET NULL,
    record_key TEXT NOT NULL,
    record_value JSONB NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (server_id, record_key),
    CHECK (version > 0)
);

CREATE INDEX idx_application_record_value
ON application_record USING GIN (record_value);

CREATE TABLE database_transaction (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    server_id BIGINT NOT NULL REFERENCES database_server(server_id),
    state transaction_state NOT NULL DEFAULT 'ACTIVE',
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    committed_at TIMESTAMPTZ,
    isolation_level TEXT NOT NULL DEFAULT 'READ COMMITTED',
    CHECK (
        isolation_level IN (
            'READ COMMITTED',
            'REPEATABLE READ',
            'SERIALIZABLE'
        )
    ),
    CHECK (
        (state = 'COMMITTED' AND committed_at IS NOT NULL)
        OR
        (state <> 'COMMITTED')
    )
);

CREATE INDEX idx_transaction_server_state
ON database_transaction(server_id, state);

CREATE TABLE wal_record (
    wal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    server_id BIGINT NOT NULL REFERENCES database_server(server_id)
        ON DELETE CASCADE,
    transaction_id BIGINT NOT NULL
        REFERENCES database_transaction(transaction_id),
    lsn BIGINT NOT NULL,
    operation wal_operation NOT NULL,
    record_key TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    checksum TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (server_id, lsn),
    CHECK (lsn > 0),
    CHECK (
        operation <> 'DELETE'
        OR new_value IS NULL
    )
);

CREATE INDEX idx_wal_transaction
ON wal_record(transaction_id);

CREATE INDEX idx_wal_server_lsn
ON wal_record(server_id, lsn);

CREATE TABLE replication_event (
    replication_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_server_id BIGINT NOT NULL REFERENCES database_server(server_id),
    target_server_id BIGINT NOT NULL REFERENCES database_server(server_id),
    wal_id BIGINT NOT NULL REFERENCES wal_record(wal_id),
    acknowledged_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,
    error_message TEXT,
    CHECK (source_server_id <> target_server_id),
    CHECK (applied_at IS NULL OR acknowledged_at IS NOT NULL)
);

CREATE INDEX idx_replication_target_pending
ON replication_event(target_server_id, applied_at)
WHERE applied_at IS NULL;

CREATE TABLE checkpoint (
    checkpoint_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    server_id BIGINT NOT NULL REFERENCES database_server(server_id)
        ON DELETE CASCADE,
    checkpoint_lsn BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (checkpoint_lsn >= 0)
);

CREATE TABLE branch_protection_style_operational_policy (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES database_cluster(cluster_id)
        ON DELETE CASCADE,
    require_online_primary BOOLEAN NOT NULL DEFAULT TRUE,
    require_replica_count INTEGER NOT NULL DEFAULT 0,
    max_replication_lag BIGINT NOT NULL DEFAULT 100,
    allow_failover BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (require_replica_count >= 0),
    CHECK (max_replication_lag >= 0)
);

COMMENT ON TABLE branch_protection_style_operational_policy IS
'Operational availability policy. The name intentionally distinguishes this '
'from application branch protection: database infrastructure has its own '
'server and replication enforcement rules.';

CREATE OR REPLACE FUNCTION validate_transaction_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'COMMITTED'
       AND NEW.state <> 'COMMITTED' THEN
        RAISE EXCEPTION
            'Committed transaction % cannot change state',
            OLD.transaction_id;
    END IF;

    IF OLD.state = 'ABORTED'
       AND NEW.state <> 'ABORTED' THEN
        RAISE EXCEPTION
            'Aborted transaction % cannot change state',
            OLD.transaction_id;
    END IF;

    IF NEW.state = 'COMMITTED'
       AND NEW.committed_at IS NULL THEN
        NEW.committed_at := clock_timestamp();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transaction_transition
BEFORE UPDATE ON database_transaction
FOR EACH ROW
EXECUTE FUNCTION validate_transaction_transition();

CREATE OR REPLACE FUNCTION validate_replication_target()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    source_role server_role;
    target_role server_role;
BEGIN
    SELECT role
    INTO source_role
    FROM database_server
    WHERE server_id = NEW.source_server_id;

    SELECT role
    INTO target_role
    FROM database_server
    WHERE server_id = NEW.target_server_id;

    IF source_role <> 'PRIMARY' THEN
        RAISE EXCEPTION
            'Replication source % is not PRIMARY',
            NEW.source_server_id;
    END IF;

    IF target_role <> 'REPLICA' THEN
        RAISE EXCEPTION
            'Replication target % is not REPLICA',
            NEW.target_server_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_replication_roles
BEFORE INSERT ON replication_event
FOR EACH ROW
EXECUTE FUNCTION validate_replication_target();

CREATE OR REPLACE FUNCTION cluster_merge_eligibility(
    p_cluster_id BIGINT
)
RETURNS TABLE (
    cluster_id BIGINT,
    primary_online BOOLEAN,
    online_replicas BIGINT,
    max_replication_lag BIGINT,
    required_replicas INTEGER,
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE SQL
AS $$
WITH policy AS (
    SELECT *
    FROM branch_protection_style_operational_policy
    WHERE cluster_id = p_cluster_id
    ORDER BY policy_id DESC
    LIMIT 1
),
primary_status AS (
    SELECT EXISTS (
        SELECT 1
        FROM database_server
        WHERE cluster_id = p_cluster_id
          AND role = 'PRIMARY'
          AND state = 'ONLINE'
    ) AS primary_online
),
replica_stats AS (
    SELECT
        count(*) FILTER (WHERE role = 'REPLICA' AND state = 'ONLINE')
            AS online_replicas,
        COALESCE(
            max(
                (
                    SELECT GREATEST(
                        0,
                        primary_server.last_replayed_lsn
                        - server.last_replayed_lsn
                    )
                    FROM database_server primary_server
                    WHERE primary_server.cluster_id = p_cluster_id
                      AND primary_server.role = 'PRIMARY'
                )
            ) FILTER (WHERE role = 'REPLICA'),
            0
        ) AS max_replication_lag
    FROM database_server server
    WHERE cluster_id = p_cluster_id
)
SELECT
    p_cluster_id,
    ps.primary_online,
    rs.online_replicas,
    rs.max_replication_lag,
    p.require_replica_count,
    (
        ps.primary_online
        AND rs.online_replicas >= p.require_replica_count
        AND rs.max_replication_lag <= p.max_replication_lag
    ) AS eligible,
    CASE
        WHEN NOT ps.primary_online
            THEN 'Primary is not online'
        WHEN rs.online_replicas < p.require_replica_count
            THEN 'Insufficient online replicas'
        WHEN rs.max_replication_lag > p.max_replication_lag
            THEN 'Replication lag exceeds policy'
        ELSE 'Cluster satisfies availability policy'
    END AS reason
FROM policy p
CROSS JOIN primary_status ps
CROSS JOIN replica_stats rs;
$$;

CREATE OR REPLACE VIEW cluster_health AS
SELECT
    c.cluster_id,
    c.cluster_name,
    c.replication_mode,
    p.server_name AS primary_server,
    p.state AS primary_state,
    count(r.server_id) FILTER (
        WHERE r.role = 'REPLICA'
          AND r.state = 'ONLINE'
    ) AS online_replicas,
    COALESCE(
        max(
            GREATEST(
                0,
                p.last_replayed_lsn - r.last_replayed_lsn
            )
        ) FILTER (WHERE r.role = 'REPLICA'),
        0
    ) AS max_replication_lag
FROM database_cluster c
LEFT JOIN database_server p
    ON p.cluster_id = c.cluster_id
   AND p.role = 'PRIMARY'
LEFT JOIN database_server r
    ON r.cluster_id = c.cluster_id
GROUP BY
    c.cluster_id,
    c.cluster_name,
    c.replication_mode,
    p.server_name,
    p.state;

CREATE OR REPLACE VIEW transaction_report AS
SELECT
    t.transaction_id,
    s.server_name,
    s.role,
    t.state,
    t.isolation_level,
    t.started_at,
    t.committed_at,
    count(w.wal_id) AS wal_records
FROM database_transaction t
JOIN database_server s
    ON s.server_id = t.server_id
LEFT JOIN wal_record w
    ON w.transaction_id = t.transaction_id
GROUP BY
    t.transaction_id,
    s.server_name,
    s.role,
    t.state,
    t.isolation_level,
    t.started_at,
    t.committed_at;

-- Sample infrastructure.
INSERT INTO database_cluster (
    cluster_name,
    replication_mode,
    synchronous_replica_count
)
VALUES
    ('orders-prod', 'ASYNC', 0),
    ('payments-prod', 'SYNC', 1);

INSERT INTO database_server (
    cluster_id,
    server_name,
    role,
    state,
    region,
    priority,
    last_replayed_lsn
)
SELECT
    c.cluster_id,
    v.server_name,
    v.role::server_role,
    v.state::server_state,
    v.region,
    v.priority,
    v.replay_lsn
FROM database_cluster c
JOIN (
    VALUES
        ('orders-prod', 'orders-primary', 'PRIMARY', 'ONLINE', 'ap-south-1', 10, 120),
        ('orders-prod', 'orders-replica-lko', 'REPLICA', 'ONLINE', 'ap-south-2', 20, 118),
        ('orders-prod', 'orders-replica-del', 'REPLICA', 'ONLINE', 'ap-south-3', 30, 120),
        ('payments-prod', 'payments-primary', 'PRIMARY', 'ONLINE', 'ap-south-1', 10, 500),
        ('payments-prod', 'payments-replica', 'REPLICA', 'ONLINE', 'ap-south-2', 20, 500)
) AS v(
    cluster_name,
    server_name,
    role,
    state,
    region,
    priority,
    replay_lsn
)
ON c.cluster_name = v.cluster_name;

INSERT INTO branch_protection_style_operational_policy (
    cluster_id,
    require_online_primary,
    require_replica_count,
    max_replication_lag,
    allow_failover
)
SELECT
    cluster_id,
    TRUE,
    CASE
        WHEN cluster_name = 'orders-prod' THEN 1
        ELSE 1
    END,
    CASE
        WHEN cluster_name = 'orders-prod' THEN 5
        ELSE 0
    END,
    TRUE
FROM database_cluster;

INSERT INTO storage_page (
    server_id,
    page_number,
    page_capacity,
    used_slots,
    checksum
)
SELECT
    server_id,
    0,
    100,
    2,
    'page-checksum-orders-000'
FROM database_server
WHERE server_name = 'orders-primary';

INSERT INTO storage_page (
    server_id,
    page_number,
    page_capacity,
    used_slots,
    checksum
)
SELECT
    server_id,
    0,
    100,
    1,
    'page-checksum-payments-000'
FROM database_server
WHERE server_name = 'payments-primary';

-- Transaction 1: committed business transaction.
INSERT INTO database_transaction (
    server_id,
    state,
    isolation_level,
    committed_at
)
SELECT
    server_id,
    'COMMITTED',
    'READ COMMITTED',
    clock_timestamp()
FROM database_server
WHERE server_name = 'orders-primary'
RETURNING transaction_id;

-- Use the latest committed transaction for sample WAL records.
INSERT INTO wal_record (
    server_id,
    transaction_id,
    lsn,
    operation,
    record_key,
    old_value,
    new_value,
    checksum
)
SELECT
    s.server_id,
    t.transaction_id,
    121,
    'INSERT',
    'order:9001',
    NULL,
    '{"customer":"C100","amount":2499,"state":"PAID"}'::jsonb,
    'sha256:sample-order-9001'
FROM database_server s
JOIN database_transaction t
    ON t.server_id = s.server_id
WHERE s.server_name = 'orders-primary'
  AND t.state = 'COMMITTED'
ORDER BY t.transaction_id DESC
LIMIT 1;

INSERT INTO application_record (
    server_id,
    page_id,
    record_key,
    record_value
)
SELECT
    s.server_id,
    p.page_id,
    'order:9001',
    '{"customer":"C100","amount":2499,"state":"PAID"}'::jsonb
FROM database_server s
JOIN storage_page p
    ON p.server_id = s.server_id
WHERE s.server_name = 'orders-primary'
  AND p.page_number = 0;

-- Transaction 2: aborted transaction, representing a failure path.
INSERT INTO database_transaction (
    server_id,
    state,
    isolation_level
)
SELECT
    server_id,
    'ABORTED',
    'SERIALIZABLE'
FROM database_server
WHERE server_name = 'orders-primary';

-- Transaction 3: committed payment operation.
INSERT INTO database_transaction (
    server_id,
    state,
    isolation_level,
    committed_at
)
SELECT
    server_id,
    'COMMITTED',
    'SERIALIZABLE',
    clock_timestamp()
FROM database_server
WHERE server_name = 'payments-primary';

INSERT INTO wal_record (
    server_id,
    transaction_id,
    lsn,
    operation,
    record_key,
    old_value,
    new_value,
    checksum
)
SELECT
    s.server_id,
    t.transaction_id,
    501,
    'UPDATE',
    'payment:P-100',
    '{"state":"AUTHORIZED"}'::jsonb,
    '{"state":"CAPTURED","amount":5000}'::jsonb,
    'sha256:sample-payment-p100'
FROM database_server s
JOIN database_transaction t
    ON t.server_id = s.server_id
WHERE s.server_name = 'payments-primary'
  AND t.state = 'COMMITTED'
ORDER BY t.transaction_id DESC
LIMIT 1;

-- Replication event demonstrating an acknowledged and applied WAL record.
INSERT INTO replication_event (
    source_server_id,
    target_server_id,
    wal_id,
    acknowledged_at,
    applied_at
)
SELECT
    source.server_id,
    target.server_id,
    w.wal_id,
    clock_timestamp(),
    clock_timestamp()
FROM database_server source
JOIN database_server target
    ON target.server_name = 'orders-replica-lko'
JOIN wal_record w
    ON w.server_id = source.server_id
WHERE source.server_name = 'orders-primary'
ORDER BY w.wal_id
LIMIT 1;

INSERT INTO checkpoint (
    server_id,
    checkpoint_lsn
)
SELECT
    server_id,
    120
FROM database_server
WHERE server_name = 'orders-primary';

-- Retrieval: database server topology.
SELECT
    c.cluster_name,
    s.server_name,
    s.role,
    s.state,
    s.region,
    s.last_replayed_lsn
FROM database_cluster c
JOIN database_server s
    ON s.cluster_id = c.cluster_id
ORDER BY c.cluster_name, s.role, s.priority;

-- Retrieval: application data.
SELECT
    s.server_name,
    a.record_key,
    a.record_value,
    a.version
FROM application_record a
JOIN database_server s
    ON s.server_id = a.server_id
ORDER BY a.record_key;

-- Aggregation: transaction state distribution.
SELECT
    s.server_name,
    t.state,
    count(*) AS transaction_count
FROM database_transaction t
JOIN database_server s
    ON s.server_id = t.server_id
GROUP BY s.server_name, t.state
ORDER BY s.server_name, t.state;

-- WAL reporting.
SELECT
    s.server_name,
    count(w.wal_id) AS wal_records,
    min(w.lsn) AS first_lsn,
    max(w.lsn) AS last_lsn
FROM database_server s
LEFT JOIN wal_record w
    ON w.server_id = s.server_id
GROUP BY s.server_name
ORDER BY s.server_name;

-- Replication reporting.
SELECT
    source.server_name AS source_server,
    target.server_name AS target_server,
    count(*) AS replication_events,
    count(*) FILTER (WHERE r.applied_at IS NOT NULL)
        AS applied_events,
    count(*) FILTER (WHERE r.applied_at IS NULL)
        AS pending_events
FROM replication_event r
JOIN database_server source
    ON source.server_id = r.source_server_id
JOIN database_server target
    ON target.server_id = r.target_server_id
GROUP BY source.server_name, target.server_name;

-- Operational health.
SELECT *
FROM cluster_health
ORDER BY cluster_name;

-- Eligibility evaluation.
SELECT *
FROM cluster_merge_eligibility(
    (SELECT cluster_id
     FROM database_cluster
     WHERE cluster_name = 'orders-prod')
);

-- CTE: identify replicas whose replay position trails their primary.
WITH primary_lsn AS (
    SELECT
        cluster_id,
        last_replayed_lsn AS primary_lsn
    FROM database_server
    WHERE role = 'PRIMARY'
),
replica_lag AS (
    SELECT
        r.server_name,
        r.cluster_id,
        GREATEST(
            0,
            p.primary_lsn - r.last_replayed_lsn
        ) AS lag
    FROM database_server r
    JOIN primary_lsn p
        ON p.cluster_id = r.cluster_id
    WHERE r.role = 'REPLICA'
)
SELECT *
FROM replica_lag
ORDER BY lag DESC;

-- Transactional integrity demonstration.
BEGIN;

SELECT pg_advisory_xact_lock(987654);

UPDATE database_server
SET last_seen_at = clock_timestamp()
WHERE server_name = 'orders-primary'
  AND state = 'ONLINE';

INSERT INTO checkpoint (
    server_id,
    checkpoint_lsn
)
SELECT server_id, last_replayed_lsn
FROM database_server
WHERE server_name = 'orders-primary';

COMMIT;

-- Enterprise-style decision report combining transaction and infrastructure state.
SELECT
    s.server_name,
    s.role,
    s.state,
    count(t.transaction_id) FILTER (
        WHERE t.state = 'COMMITTED'
    ) AS committed_transactions,
    count(t.transaction_id) FILTER (
        WHERE t.state = 'ABORTED'
    ) AS aborted_transactions,
    count(w.wal_id) AS wal_records
FROM database_server s
LEFT JOIN database_transaction t
    ON t.server_id = s.server_id
LEFT JOIN wal_record w
    ON w.server_id = s.server_id
GROUP BY s.server_name, s.role, s.state
ORDER BY s.server_name;
