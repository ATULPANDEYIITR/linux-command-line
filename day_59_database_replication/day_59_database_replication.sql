DROP SCHEMA IF EXISTS replication_lab CASCADE;
CREATE SCHEMA replication_lab;

SET search_path = replication_lab, public;

-- The schema represents logical replication metadata and state.
-- It does not pretend to implement PostgreSQL's physical WAL transport.
-- Actual physical replication is performed by PostgreSQL server processes;
-- this relational model records the governance and operational state around it.

CREATE TYPE node_role AS ENUM ('primary', 'replica', 'offline');
CREATE TYPE replication_mode AS ENUM ('synchronous', 'asynchronous');
CREATE TYPE node_state AS ENUM ('healthy', 'degraded', 'failed');
CREATE TYPE pr_status AS ENUM ('draft', 'open', 'merged', 'closed');

CREATE TABLE repository (
    repository_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    owner_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(name)) > 0)
);

CREATE TABLE database_node (
    node_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    node_name TEXT NOT NULL,
    role node_role NOT NULL,
    replication_mode replication_mode,
    state node_state NOT NULL DEFAULT 'healthy',
    current_lsn BIGINT NOT NULL DEFAULT 0,
    last_heartbeat_at TIMESTAMPTZ,
    UNIQUE (repository_id, node_name),
    CHECK (current_lsn >= 0),
    CHECK (
        (role = 'primary' AND replication_mode IS NULL)
        OR
        (role = 'replica' AND replication_mode IS NOT NULL)
        OR
        role = 'offline'
    )
);

CREATE UNIQUE INDEX one_active_primary_per_repository
ON database_node(repository_id)
WHERE role = 'primary' AND state <> 'failed';

CREATE TABLE replication_transaction (
    transaction_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    wal_position BIGINT NOT NULL,
    object_key TEXT NOT NULL,
    object_value TEXT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, wal_position),
    CHECK (wal_position > 0),
    CHECK (length(trim(object_key)) > 0)
);

CREATE TABLE replication_receipt (
    receipt_id BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL
        REFERENCES replication_transaction(transaction_id)
        ON DELETE CASCADE,
    node_id BIGINT NOT NULL
        REFERENCES database_node(node_id) ON DELETE CASCADE,
    applied_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'applied', 'failed')
    ),
    UNIQUE (transaction_id, node_id)
);

CREATE TABLE branch (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    head_lsn BIGINT NOT NULL DEFAULT 0,
    protected BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (repository_id, branch_name),
    CHECK (length(trim(branch_name)) > 0),
    CHECK (head_lsn >= 0)
);

CREATE TABLE failover_event (
    failover_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    old_primary_node_id BIGINT
        REFERENCES database_node(node_id),
    new_primary_node_id BIGINT
        REFERENCES database_node(node_id),
    reason TEXT NOT NULL,
    old_lsn BIGINT NOT NULL,
    new_lsn BIGINT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (old_lsn >= 0),
    CHECK (new_lsn >= 0),
    CHECK (new_lsn <= old_lsn OR old_lsn = 0)
);

CREATE TABLE replication_policy (
    policy_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL UNIQUE
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    required_sync_replicas INTEGER NOT NULL DEFAULT 1,
    max_async_lag BIGINT NOT NULL DEFAULT 5,
    allow_failover BOOLEAN NOT NULL DEFAULT true,
    CHECK (required_sync_replicas >= 0),
    CHECK (max_async_lag >= 0)
);

CREATE OR REPLACE FUNCTION validate_primary_node()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.role = 'primary' AND NEW.replication_mode IS NOT NULL THEN
        RAISE EXCEPTION
            'A primary cannot have a replica replication mode';
    END IF;

    IF NEW.role = 'replica' AND NEW.replication_mode IS NULL THEN
        RAISE EXCEPTION
            'A replica must declare a replication mode';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_primary_node
BEFORE INSERT OR UPDATE ON database_node
FOR EACH ROW
EXECUTE FUNCTION validate_primary_node();

CREATE OR REPLACE FUNCTION calculate_replication_lag(
    p_repository_id BIGINT,
    p_node_id BIGINT
)
RETURNS BIGINT
LANGUAGE sql
STABLE
AS $$
    SELECT GREATEST(
        COALESCE(
            (
                SELECT max(wal_position)
                FROM replication_transaction
                WHERE repository_id = p_repository_id
            ),
            0
        )
        -
        COALESCE(
            (
                SELECT current_lsn
                FROM database_node
                WHERE node_id = p_node_id
            ),
            0
        ),
        0
    );
$$;

CREATE OR REPLACE FUNCTION record_replication_apply(
    p_transaction_id BIGINT,
    p_node_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_position BIGINT;
BEGIN
    SELECT wal_position
    INTO v_position
    FROM replication_transaction
    WHERE transaction_id = p_transaction_id;

    IF v_position IS NULL THEN
        RAISE EXCEPTION 'Unknown replication transaction %',
            p_transaction_id;
    END IF;

    UPDATE database_node
    SET current_lsn = GREATEST(current_lsn, v_position),
        last_heartbeat_at = now(),
        state = 'healthy'
    WHERE node_id = p_node_id
      AND role = 'replica';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Node % is not an available replica', p_node_id;
    END IF;

    INSERT INTO replication_receipt (
        transaction_id,
        node_id,
        applied_at,
        status
    )
    VALUES (
        p_transaction_id,
        p_node_id,
        now(),
        'applied'
    )
    ON CONFLICT (transaction_id, node_id)
    DO UPDATE SET
        applied_at = EXCLUDED.applied_at,
        status = EXCLUDED.status;
END;
$$;

-- Sample repository and policy.
INSERT INTO repository (name, owner_name)
VALUES ('payments-core', 'platform-engineering');

INSERT INTO replication_policy (
    repository_id,
    required_sync_replicas,
    max_async_lag,
    allow_failover
)
SELECT repository_id, 1, 3, true
FROM repository
WHERE name = 'payments-core';

-- Primary and replicas.
INSERT INTO database_node (
    repository_id,
    node_name,
    role,
    replication_mode,
    state,
    current_lsn,
    last_heartbeat_at
)
SELECT
    repository_id,
    'db-primary-01',
    'primary',
    NULL,
    'healthy',
    105,
    now()
FROM repository
WHERE name = 'payments-core';

INSERT INTO database_node (
    repository_id,
    node_name,
    role,
    replication_mode,
    state,
    current_lsn,
    last_heartbeat_at
)
SELECT
    repository_id,
    'db-replica-sync-01',
    'replica',
    'synchronous',
    'healthy',
    105,
    now()
FROM repository
WHERE name = 'payments-core';

INSERT INTO database_node (
    repository_id,
    node_name,
    role,
    replication_mode,
    state,
    current_lsn,
    last_heartbeat_at
)
SELECT
    repository_id,
    'db-replica-async-01',
    'replica',
    'asynchronous',
    'healthy',
    101,
    now()
FROM repository
WHERE name = 'payments-core';

INSERT INTO branch (
    repository_id,
    branch_name,
    head_lsn,
    protected
)
SELECT repository_id, 'main', 105, true
FROM repository
WHERE name = 'payments-core';

-- Replication transactions representing WAL positions.
INSERT INTO replication_transaction (
    repository_id,
    wal_position,
    object_key,
    object_value
)
SELECT repository_id, 101, 'customer:1001', 'active'
FROM repository
WHERE name = 'payments-core';

INSERT INTO replication_transaction (
    repository_id,
    wal_position,
    object_key,
    object_value
)
SELECT repository_id, 102, 'invoice:9001', 'paid'
FROM repository
WHERE name = 'payments-core';

INSERT INTO replication_transaction (
    repository_id,
    wal_position,
    object_key,
    object_value
)
SELECT repository_id, 103, 'invoice:9002', 'pending'
FROM repository
WHERE name = 'payments-core';

INSERT INTO replication_transaction (
    repository_id,
    wal_position,
    object_key,
    object_value
)
SELECT repository_id, 104, 'customer:1002', 'active'
FROM repository
WHERE name = 'payments-core';

INSERT INTO replication_transaction (
    repository_id,
    wal_position,
    object_key,
    object_value
)
SELECT repository_id, 105, 'invoice:9003', 'paid'
FROM repository
WHERE name = 'payments-core';

-- Mark the synchronous replica as fully caught up.
INSERT INTO replication_receipt (
    transaction_id,
    node_id,
    applied_at,
    status
)
SELECT
    t.transaction_id,
    n.node_id,
    now(),
    'applied'
FROM replication_transaction t
JOIN repository r
    ON r.repository_id = t.repository_id
JOIN database_node n
    ON n.repository_id = r.repository_id
WHERE r.name = 'payments-core'
  AND n.node_name = 'db-replica-sync-01';

-- The asynchronous replica intentionally has lag.
INSERT INTO replication_receipt (
    transaction_id,
    node_id,
    applied_at,
    status
)
SELECT
    t.transaction_id,
    n.node_id,
    now(),
    'applied'
FROM replication_transaction t
JOIN repository r
    ON r.repository_id = t.repository_id
JOIN database_node n
    ON n.repository_id = r.repository_id
WHERE r.name = 'payments-core'
  AND n.node_name = 'db-replica-async-01'
  AND t.wal_position <= 101;

-- Transactional application of a new WAL event.
BEGIN;

INSERT INTO replication_transaction (
    repository_id,
    wal_position,
    object_key,
    object_value
)
SELECT repository_id, 106, 'invoice:9004', 'paid'
FROM repository
WHERE name = 'payments-core';

-- Synchronous receipt is required before the transaction is committed.
INSERT INTO replication_receipt (
    transaction_id,
    node_id,
    applied_at,
    status
)
SELECT
    t.transaction_id,
    n.node_id,
    now(),
    'applied'
FROM replication_transaction t
JOIN repository r
    ON r.repository_id = t.repository_id
JOIN database_node n
    ON n.repository_id = r.repository_id
WHERE r.name = 'payments-core'
  AND t.wal_position = 106
  AND n.node_name = 'db-replica-sync-01';

UPDATE database_node
SET current_lsn = 106,
    last_heartbeat_at = now()
WHERE node_name = 'db-primary-01'
  AND repository_id = (
      SELECT repository_id
      FROM repository
      WHERE name = 'payments-core'
  );

COMMIT;

-- Current node health and lag.
SELECT
    n.node_name,
    n.role,
    n.replication_mode,
    n.state,
    n.current_lsn,
    calculate_replication_lag(n.repository_id, n.node_id) AS lag
FROM database_node n
JOIN repository r
    ON r.repository_id = n.repository_id
WHERE r.name = 'payments-core'
ORDER BY n.node_name;

-- Identify replicas that violate the asynchronous lag policy.
SELECT
    n.node_name,
    n.replication_mode,
    calculate_replication_lag(n.repository_id, n.node_id) AS lag,
    p.max_async_lag
FROM database_node n
JOIN replication_policy p
    ON p.repository_id = n.repository_id
WHERE n.replication_mode = 'asynchronous'
  AND calculate_replication_lag(n.repository_id, n.node_id)
      > p.max_async_lag;

-- Count synchronous replicas that satisfy the current WAL position.
WITH primary_position AS (
    SELECT
        repository_id,
        current_lsn
    FROM database_node
    WHERE role = 'primary'
      AND state <> 'failed'
)
SELECT
    r.name AS repository,
    pp.current_lsn AS primary_lsn,
    count(n.node_id) AS eligible_sync_replicas,
    p.required_sync_replicas,
    (
        count(n.node_id) >= p.required_sync_replicas
    ) AS synchronous_requirement_met
FROM primary_position pp
JOIN repository r
    ON r.repository_id = pp.repository_id
JOIN replication_policy p
    ON p.repository_id = r.repository_id
LEFT JOIN database_node n
    ON n.repository_id = pp.repository_id
   AND n.role = 'replica'
   AND n.replication_mode = 'synchronous'
   AND n.state = 'healthy'
   AND n.current_lsn >= pp.current_lsn
GROUP BY
    r.name,
    pp.current_lsn,
    p.required_sync_replicas;

-- Transactional failover:
-- select the most advanced healthy synchronous replica,
-- demote the old primary, promote the selected replica,
-- and record the event atomically.
BEGIN;

WITH candidate AS (
    SELECT node_id, repository_id, current_lsn
    FROM database_node
    WHERE role = 'replica'
      AND replication_mode = 'synchronous'
      AND state = 'healthy'
    ORDER BY current_lsn DESC
    LIMIT 1
),
old_primary AS (
    SELECT node_id, repository_id, current_lsn
    FROM database_node
    WHERE role = 'primary'
      AND state <> 'failed'
    LIMIT 1
)
UPDATE database_node n
SET role = 'offline',
    state = 'failed'
FROM old_primary op
WHERE n.node_id = op.node_id;

WITH candidate AS (
    SELECT node_id, repository_id, current_lsn
    FROM database_node
    WHERE role = 'replica'
      AND replication_mode = 'synchronous'
      AND state = 'healthy'
    ORDER BY current_lsn DESC
    LIMIT 1
)
UPDATE database_node n
SET role = 'primary',
    replication_mode = NULL,
    state = 'healthy'
FROM candidate c
WHERE n.node_id = c.node_id;

INSERT INTO failover_event (
    repository_id,
    old_primary_node_id,
    new_primary_node_id,
    reason,
    old_lsn,
    new_lsn
)
SELECT
    oldp.repository_id,
    oldp.node_id,
    newp.node_id,
    'Primary failure with synchronous replica promotion',
    oldp.current_lsn,
    newp.current_lsn
FROM (
    SELECT
        node_id,
        repository_id,
        current_lsn
    FROM database_node
    WHERE state = 'failed'
      AND role = 'offline'
    ORDER BY node_id DESC
    LIMIT 1
) oldp
JOIN (
    SELECT
        node_id,
        repository_id,
        current_lsn
    FROM database_node
    WHERE role = 'primary'
    ORDER BY node_id DESC
    LIMIT 1
) newp
ON newp.repository_id = oldp.repository_id;

COMMIT;

-- Final primary and replica state after failover.
SELECT
    r.name AS repository,
    n.node_name,
    n.role,
    n.replication_mode,
    n.state,
    n.current_lsn
FROM repository r
JOIN database_node n
    ON n.repository_id = r.repository_id
WHERE r.name = 'payments-core'
ORDER BY n.node_name;
