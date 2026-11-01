DROP SCHEMA IF EXISTS scaling_lab CASCADE;
CREATE SCHEMA scaling_lab;

SET search_path TO scaling_lab, public;

-- Database scaling is represented at several layers:
-- vertical scaling changes capacity of an existing node;
-- horizontal scaling adds nodes;
-- partitioning divides logical table data;
-- sharding assigns logical partitions to independent databases/nodes.

CREATE TYPE node_status AS ENUM ('healthy', 'draining', 'unhealthy');
CREATE TYPE partition_method AS ENUM ('range', 'hash');
CREATE TYPE shard_method AS ENUM ('range', 'hash');
CREATE TYPE pull_request_state AS ENUM ('draft', 'open', 'closed', 'merged');

CREATE TABLE database_clusters (
    cluster_id       BIGSERIAL PRIMARY KEY,
    cluster_name     TEXT NOT NULL UNIQUE,
    region           TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(cluster_name)) >= 3)
);

CREATE TABLE database_nodes (
    node_id          BIGSERIAL PRIMARY KEY,
    cluster_id       BIGINT NOT NULL REFERENCES database_clusters(cluster_id)
                     ON DELETE CASCADE,
    node_name        TEXT NOT NULL,
    capacity_units   INTEGER NOT NULL,
    used_units       INTEGER NOT NULL DEFAULT 0,
    status           node_status NOT NULL DEFAULT 'healthy',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cluster_id, node_name),
    CHECK (capacity_units > 0),
    CHECK (used_units >= 0),
    CHECK (used_units <= capacity_units)
);

CREATE INDEX idx_database_nodes_cluster_status
    ON database_nodes (cluster_id, status);

CREATE TABLE scaling_events (
    event_id         BIGSERIAL PRIMARY KEY,
    cluster_id       BIGINT NOT NULL REFERENCES database_clusters(cluster_id),
    node_id          BIGINT REFERENCES database_nodes(node_id),
    event_type       TEXT NOT NULL,
    old_capacity     INTEGER,
    new_capacity     INTEGER,
    event_reason     TEXT NOT NULL,
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (event_type IN (
        'vertical_resize',
        'node_added',
        'node_drained',
        'node_failed',
        'node_recovered'
    )),
    CHECK (
        old_capacity IS NULL
        OR old_capacity > 0
    ),
    CHECK (
        new_capacity IS NULL
        OR new_capacity > 0
    )
);

CREATE TABLE partition_definitions (
    partition_id     BIGSERIAL PRIMARY KEY,
    cluster_id       BIGINT NOT NULL REFERENCES database_clusters(cluster_id)
                     ON DELETE CASCADE,
    partition_name   TEXT NOT NULL,
    method           partition_method NOT NULL,
    partition_index  INTEGER NOT NULL,
    lower_bound      BIGINT,
    upper_bound      BIGINT,
    UNIQUE (cluster_id, partition_name),
    UNIQUE (cluster_id, partition_index),
    CHECK (partition_index >= 0),
    CHECK (
        method = 'hash'
        OR (
            lower_bound IS NOT NULL
            AND upper_bound IS NOT NULL
            AND lower_bound < upper_bound
        )
    )
);

CREATE TABLE shards (
    shard_id         BIGSERIAL PRIMARY KEY,
    cluster_id       BIGINT NOT NULL REFERENCES database_clusters(cluster_id)
                     ON DELETE CASCADE,
    shard_name       TEXT NOT NULL,
    method           shard_method NOT NULL,
    node_id          BIGINT NOT NULL REFERENCES database_nodes(node_id),
    shard_index      INTEGER NOT NULL,
    active           BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (cluster_id, shard_name),
    UNIQUE (cluster_id, shard_index),
    CHECK (shard_index >= 0)
);

CREATE INDEX idx_shards_node
    ON shards (node_id);

CREATE TABLE customers (
    customer_id      BIGSERIAL PRIMARY KEY,
    customer_name    TEXT NOT NULL,
    region           TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(customer_name)) >= 2)
);

CREATE TABLE orders (
    order_id         BIGSERIAL PRIMARY KEY,
    customer_id      BIGINT NOT NULL REFERENCES customers(customer_id),
    partition_id     BIGINT NOT NULL REFERENCES partition_definitions(partition_id),
    shard_id         BIGINT NOT NULL REFERENCES shards(shard_id),
    amount           NUMERIC(14,2) NOT NULL,
    order_status     TEXT NOT NULL DEFAULT 'pending',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (amount >= 0),
    CHECK (order_status IN ('pending', 'paid', 'cancelled', 'fulfilled'))
);

CREATE INDEX idx_orders_customer
    ON orders (customer_id);

CREATE INDEX idx_orders_partition_created
    ON orders (partition_id, created_at DESC);

CREATE INDEX idx_orders_shard_created
    ON orders (shard_id, created_at DESC);

-- The scaling policy records operational limits separately from current state.
CREATE TABLE scaling_policies (
    policy_id                BIGSERIAL PRIMARY KEY,
    cluster_id               BIGINT NOT NULL UNIQUE
                             REFERENCES database_clusters(cluster_id)
                             ON DELETE CASCADE,
    vertical_max_capacity    INTEGER NOT NULL,
    horizontal_min_nodes     INTEGER NOT NULL,
    horizontal_max_nodes     INTEGER NOT NULL,
    utilization_threshold    NUMERIC(5,4) NOT NULL,
    require_healthy_nodes    BOOLEAN NOT NULL DEFAULT true,
    CHECK (vertical_max_capacity > 0),
    CHECK (horizontal_min_nodes > 0),
    CHECK (horizontal_max_nodes >= horizontal_min_nodes),
    CHECK (
        utilization_threshold > 0
        AND utilization_threshold <= 1
    )
);

-- Seed a cluster.
INSERT INTO database_clusters (cluster_name, region)
VALUES ('orders-production', 'asia-south');

INSERT INTO database_nodes (
    cluster_id,
    node_name,
    capacity_units,
    used_units,
    status
)
VALUES
    (1, 'db-primary', 200, 120, 'healthy'),
    (1, 'db-replica-01', 100, 45, 'healthy'),
    (1, 'db-replica-02', 100, 80, 'healthy'),
    (1, 'db-replica-03', 100, 100, 'draining');

INSERT INTO scaling_policies (
    cluster_id,
    vertical_max_capacity,
    horizontal_min_nodes,
    horizontal_max_nodes,
    utilization_threshold
)
VALUES
    (1, 500, 2, 12, 0.80);

-- Hash partitions are logical groups. They do not by themselves imply
-- independent physical database servers.
INSERT INTO partition_definitions (
    cluster_id,
    partition_name,
    method,
    partition_index
)
VALUES
    (1, 'orders_p0', 'hash', 0),
    (1, 'orders_p1', 'hash', 1),
    (1, 'orders_p2', 'hash', 2),
    (1, 'orders_p3', 'hash', 3);

INSERT INTO shards (
    cluster_id,
    shard_name,
    method,
    node_id,
    shard_index
)
VALUES
    (1, 'orders_s0', 'hash', 1, 0),
    (1, 'orders_s1', 'hash', 2, 1),
    (1, 'orders_s2', 'hash', 3, 2),
    (1, 'orders_s3', 'hash', 1, 3);

INSERT INTO customers (customer_name, region)
VALUES
    ('Northwind Retail', 'north'),
    ('Delta Systems', 'south'),
    ('Orion Logistics', 'east'),
    ('Vertex Services', 'west'),
    ('Apex Manufacturing', 'north'),
    ('Cedar Health', 'south'),
    ('Nimbus Telecom', 'east'),
    ('Summit Energy', 'west');

-- A deterministic hash expression keeps the demonstration reproducible.
INSERT INTO orders (
    customer_id,
    partition_id,
    shard_id,
    amount,
    order_status
)
SELECT
    c.customer_id,
    1 + mod(c.customer_id::bigint, 4),
    1 + mod(c.customer_id::bigint, 4),
    round((100 + c.customer_id * 37.25)::numeric, 2),
    CASE
        WHEN c.customer_id % 4 = 0 THEN 'fulfilled'
        WHEN c.customer_id % 3 = 0 THEN 'paid'
        ELSE 'pending'
    END
FROM customers AS c;

CREATE OR REPLACE FUNCTION validate_node_capacity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.used_units > NEW.capacity_units THEN
        RAISE EXCEPTION
            'Node % has usage % above capacity %',
            NEW.node_name,
            NEW.used_units,
            NEW.capacity_units;
    END IF;

    IF NEW.status = 'healthy' AND NEW.capacity_units <= 0 THEN
        RAISE EXCEPTION
            'Healthy node must have positive capacity';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_node_capacity
BEFORE INSERT OR UPDATE ON database_nodes
FOR EACH ROW
EXECUTE FUNCTION validate_node_capacity();

CREATE OR REPLACE FUNCTION record_node_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO scaling_events (
            cluster_id,
            node_id,
            event_type,
            new_capacity,
            event_reason
        )
        VALUES (
            NEW.cluster_id,
            NEW.node_id,
            'node_added',
            NEW.capacity_units,
            'Database node added'
        );

    ELSIF OLD.capacity_units IS DISTINCT FROM NEW.capacity_units THEN
        INSERT INTO scaling_events (
            cluster_id,
            node_id,
            event_type,
            old_capacity,
            new_capacity,
            event_reason
        )
        VALUES (
            NEW.cluster_id,
            NEW.node_id,
            'vertical_resize',
            OLD.capacity_units,
            NEW.capacity_units,
            'Node capacity changed'
        );

    ELSIF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO scaling_events (
            cluster_id,
            node_id,
            event_type,
            event_reason
        )
        VALUES (
            NEW.cluster_id,
            NEW.node_id,
            CASE
                WHEN NEW.status = 'draining' THEN 'node_drained'
                WHEN NEW.status = 'unhealthy' THEN 'node_failed'
                WHEN NEW.status = 'healthy' THEN 'node_recovered'
                ELSE 'node_failed'
            END,
            'Node status changed'
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_node_change
AFTER INSERT OR UPDATE ON database_nodes
FOR EACH ROW
EXECUTE FUNCTION record_node_change();

CREATE OR REPLACE FUNCTION choose_least_utilized_node(
    p_cluster_id BIGINT
)
RETURNS BIGINT
LANGUAGE sql
STABLE
AS $$
    SELECT node_id
    FROM database_nodes
    WHERE cluster_id = p_cluster_id
      AND status = 'healthy'
      AND used_units < capacity_units
    ORDER BY
        used_units::numeric / NULLIF(capacity_units, 0),
        node_id
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION evaluate_horizontal_scaling(
    p_cluster_id BIGINT
)
RETURNS TABLE (
    current_nodes BIGINT,
    healthy_nodes BIGINT,
    average_utilization NUMERIC,
    scale_out_required BOOLEAN
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        count(*)::bigint,
        count(*) FILTER (WHERE status = 'healthy')::bigint,
        round(
            avg(used_units::numeric / NULLIF(capacity_units, 0)),
            4
        ),
        bool_or(
            status = 'healthy'
            AND used_units::numeric / NULLIF(capacity_units, 0)
                >= (
                    SELECT utilization_threshold
                    FROM scaling_policies
                    WHERE cluster_id = p_cluster_id
                )
        )
    FROM database_nodes
    WHERE cluster_id = p_cluster_id;
$$;

CREATE OR REPLACE VIEW node_capacity_report AS
SELECT
    n.node_id,
    n.node_name,
    n.capacity_units,
    n.used_units,
    round(
        n.used_units::numeric / NULLIF(n.capacity_units, 0),
        4
    ) AS utilization,
    n.status,
    CASE
        WHEN n.status <> 'healthy' THEN 'unavailable'
        WHEN n.used_units = n.capacity_units THEN 'full'
        WHEN n.used_units::numeric / n.capacity_units
             >= p.utilization_threshold THEN 'scale_attention'
        ELSE 'available'
    END AS capacity_state
FROM database_nodes AS n
JOIN scaling_policies AS p
  ON p.cluster_id = n.cluster_id;

CREATE OR REPLACE VIEW shard_distribution_report AS
SELECT
    s.shard_id,
    s.shard_name,
    n.node_name,
    count(o.order_id) AS row_count,
    s.active
FROM shards AS s
JOIN database_nodes AS n
  ON n.node_id = s.node_id
LEFT JOIN orders AS o
  ON o.shard_id = s.shard_id
GROUP BY
    s.shard_id,
    s.shard_name,
    n.node_name,
    s.active;

-- Retrieval: identify the node that can accept another unit of workload.
SELECT choose_least_utilized_node(1) AS target_node;

-- Validation: find nodes approaching the configured utilization threshold.
SELECT *
FROM node_capacity_report
WHERE capacity_state = 'scale_attention';

-- Aggregation: inspect physical distribution.
SELECT *
FROM shard_distribution_report
ORDER BY shard_id;

-- Evaluation: decide whether horizontal scale-out pressure exists.
SELECT *
FROM evaluate_horizontal_scaling(1);

-- Reporting: compare logical partitions.
SELECT
    p.partition_name,
    count(o.order_id) AS order_count,
    coalesce(sum(o.amount), 0) AS total_value
FROM partition_definitions AS p
LEFT JOIN orders AS o
  ON o.partition_id = p.partition_id
WHERE p.cluster_id = 1
GROUP BY p.partition_id, p.partition_name
ORDER BY p.partition_id;

-- Workflow state: operational node states.
SELECT
    node_name,
    status,
    used_units,
    capacity_units
FROM database_nodes
WHERE cluster_id = 1
ORDER BY node_id;

-- Eligibility decision: a node is eligible for new traffic only when healthy
-- and below capacity.
SELECT
    node_name,
    status,
    used_units,
    capacity_units,
    (
        status = 'healthy'
        AND used_units < capacity_units
    ) AS eligible_for_new_work
FROM database_nodes
WHERE cluster_id = 1;

-- CTE: compare the current cluster with its configured policy.
WITH cluster_metrics AS (
    SELECT
        cluster_id,
        count(*) AS node_count,
        count(*) FILTER (WHERE status = 'healthy') AS healthy_count,
        avg(
            used_units::numeric / NULLIF(capacity_units, 0)
        ) AS avg_utilization
    FROM database_nodes
    WHERE cluster_id = 1
    GROUP BY cluster_id
)
SELECT
    m.cluster_id,
    m.node_count,
    m.healthy_count,
    round(m.avg_utilization, 4) AS avg_utilization,
    p.horizontal_max_nodes,
    p.utilization_threshold,
    CASE
        WHEN m.node_count >= p.horizontal_max_nodes
            THEN 'horizontal_limit_reached'
        WHEN m.avg_utilization >= p.utilization_threshold
            THEN 'consider_scale_out'
        ELSE 'within_policy'
    END AS scaling_decision
FROM cluster_metrics AS m
JOIN scaling_policies AS p
  ON p.cluster_id = m.cluster_id;

-- Transactional integrity: simulate a safe capacity increase.
BEGIN;

UPDATE database_nodes
SET capacity_units = capacity_units + 25
WHERE node_id = 3
  AND capacity_units + 25 <= (
      SELECT vertical_max_capacity
      FROM scaling_policies
      WHERE cluster_id = database_nodes.cluster_id
  );

COMMIT;

-- Failure-case query: no healthy node should be considered eligible when full.
SELECT
    node_name,
    status,
    used_units = capacity_units AS is_full,
    status = 'healthy'
        AND used_units < capacity_units AS eligible
FROM database_nodes
ORDER BY node_id;

-- Scaling-event audit trail.
SELECT
    event_id,
    event_type,
    old_capacity,
    new_capacity,
    event_reason,
    occurred_at
FROM scaling_events
ORDER BY event_id;
