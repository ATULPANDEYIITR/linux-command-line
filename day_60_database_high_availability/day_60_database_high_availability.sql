/*
 * Database high-availability control-plane schema and executable scenario.
 *
 * PostgreSQL 14 or later.
 *
 * This script models:
 * - Database clusters and fixed voter membership
 * - Multi-zone database nodes
 * - Synchronous and asynchronous replication links
 * - Committed write positions
 * - Health-check observations
 * - Majority quorum enforcement
 * - Safe failover eligibility
 * - Fencing and primary promotion
 * - Replica recovery
 * - Auditable failover events
 *
 * This is a control-plane model, not a physical replication configuration.
 * It does not start PostgreSQL standby servers, stream WAL, or fence real
 * infrastructure. Those operations require a separate deployment and
 * orchestration layer.
 */

DROP SCHEMA IF EXISTS ha_lab CASCADE;
CREATE SCHEMA ha_lab;
SET search_path = ha_lab, public;

CREATE TYPE node_role AS ENUM ('primary', 'replica');
CREATE TYPE node_state AS ENUM ('healthy', 'suspect', 'down', 'fenced');
CREATE TYPE replication_mode AS ENUM ('synchronous', 'asynchronous');
CREATE TYPE rpo_mode AS ENUM ('zero_data_loss', 'bounded_lag');
CREATE TYPE health_result AS ENUM ('healthy', 'degraded', 'failed');

CREATE TABLE ha_clusters (
    cluster_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_name TEXT NOT NULL UNIQUE,
    expected_voters INTEGER NOT NULL DEFAULT 3,
    synchronous_replica_acks INTEGER NOT NULL DEFAULT 1,
    maximum_lag_ms BIGINT NOT NULL DEFAULT 500,
    minimum_live_zones INTEGER NOT NULL DEFAULT 2,
    recovery_point_mode rpo_mode NOT NULL DEFAULT 'zero_data_loss',
    current_primary_node_id BIGINT,
    commit_index BIGINT NOT NULL DEFAULT 0,
    term BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_expected_voters
        CHECK (expected_voters >= 3 AND expected_voters % 2 = 1),

    CONSTRAINT ck_sync_ack_count
        CHECK (
            synchronous_replica_acks >= 1
            AND synchronous_replica_acks < expected_voters
        ),

    CONSTRAINT ck_maximum_lag
        CHECK (maximum_lag_ms >= 0),

    CONSTRAINT ck_minimum_live_zones
        CHECK (minimum_live_zones >= 1 AND minimum_live_zones <= expected_voters),

    CONSTRAINT ck_commit_index
        CHECK (commit_index >= 0),

    CONSTRAINT ck_cluster_term
        CHECK (term >= 1)
);

CREATE TABLE cluster_nodes (
    node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES ha_clusters(cluster_id) ON DELETE CASCADE,
    node_name TEXT NOT NULL,
    availability_zone TEXT NOT NULL,
    role node_role NOT NULL,
    state node_state NOT NULL DEFAULT 'healthy',
    voter BOOLEAN NOT NULL DEFAULT TRUE,
    reachable BOOLEAN NOT NULL DEFAULT TRUE,
    fenced BOOLEAN NOT NULL DEFAULT FALSE,
    applied_index BIGINT NOT NULL DEFAULT 0,
    lag_ms BIGINT NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 100,
    last_heartbeat_at TIMESTAMPTZ,

    CONSTRAINT uq_cluster_node_name UNIQUE (cluster_id, node_name),
    CONSTRAINT uq_cluster_node_reference UNIQUE (cluster_id, node_id),

    CONSTRAINT ck_node_applied_index CHECK (applied_index >= 0),
    CONSTRAINT ck_node_lag CHECK (lag_ms >= 0),
    CONSTRAINT ck_node_priority CHECK (priority >= 0),

    CONSTRAINT ck_fenced_node
        CHECK (NOT fenced OR role = 'replica'),

    CONSTRAINT ck_fenced_state
        CHECK (
            state <> 'fenced'
            OR (fenced AND NOT reachable AND role = 'replica')
        ),

    CONSTRAINT ck_down_node
        CHECK (state <> 'down' OR NOT reachable),

    CONSTRAINT ck_healthy_node
        CHECK (state <> 'healthy' OR (reachable AND NOT fenced))
);

-- Prevent two unfenced primaries in the same cluster.
CREATE UNIQUE INDEX uq_one_unfenced_primary
    ON cluster_nodes(cluster_id)
    WHERE role = 'primary' AND NOT fenced;

CREATE INDEX ix_live_cluster_voters
    ON cluster_nodes(cluster_id, voter, state, reachable);

CREATE INDEX ix_replica_promotion_candidates
    ON cluster_nodes(cluster_id, applied_index DESC, priority)
    WHERE role = 'replica' AND state = 'healthy' AND NOT fenced;

ALTER TABLE ha_clusters
    ADD CONSTRAINT fk_current_primary
    FOREIGN KEY (cluster_id, current_primary_node_id)
    REFERENCES cluster_nodes(cluster_id, node_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE replication_links (
    link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES ha_clusters(cluster_id) ON DELETE CASCADE,
    source_node_id BIGINT NOT NULL,
    target_node_id BIGINT NOT NULL,
    mode replication_mode NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_replication_path
        UNIQUE (cluster_id, source_node_id, target_node_id),

    CONSTRAINT ck_replication_direction
        CHECK (source_node_id <> target_node_id),

    CONSTRAINT fk_link_source
        FOREIGN KEY (cluster_id, source_node_id)
        REFERENCES cluster_nodes(cluster_id, node_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_link_target
        FOREIGN KEY (cluster_id, target_node_id)
        REFERENCES cluster_nodes(cluster_id, node_id)
        ON DELETE CASCADE
);

CREATE INDEX ix_replication_targets
    ON replication_links(cluster_id, target_node_id)
    WHERE enabled;

CREATE TABLE health_checks (
    health_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id BIGINT NOT NULL,
    node_id BIGINT NOT NULL,
    result health_result NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    latency_ms INTEGER,
    diagnostic TEXT,

    CONSTRAINT ck_health_latency
        CHECK (latency_ms IS NULL OR latency_ms >= 0),

    CONSTRAINT fk_health_node
        FOREIGN KEY (cluster_id, node_id)
        REFERENCES cluster_nodes(cluster_id, node_id)
        ON DELETE CASCADE
);

CREATE INDEX ix_latest_node_health
    ON health_checks(cluster_id, node_id, observed_at DESC);

CREATE TABLE committed_writes (
    write_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES ha_clusters(cluster_id) ON DELETE CASCADE,
    write_index BIGINT NOT NULL,
    payload JSONB NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_cluster_write_index UNIQUE (cluster_id, write_index),
    CONSTRAINT ck_write_index CHECK (write_index > 0)
);

CREATE TABLE failover_events (
    failover_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES ha_clusters(cluster_id) ON DELETE CASCADE,
    previous_primary_node_id BIGINT,
    promoted_node_id BIGINT NOT NULL,
    previous_term BIGINT NOT NULL,
    new_term BIGINT NOT NULL,
    commit_index_at_promotion BIGINT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_failover_term CHECK (new_term = previous_term + 1),
    CONSTRAINT ck_failover_commit_index CHECK (commit_index_at_promotion >= 0),

    CONSTRAINT fk_old_primary
        FOREIGN KEY (previous_primary_node_id)
        REFERENCES cluster_nodes(node_id),

    CONSTRAINT fk_promoted_node
        FOREIGN KEY (promoted_node_id)
        REFERENCES cluster_nodes(node_id)
);

CREATE INDEX ix_cluster_failover_history
    ON failover_events(cluster_id, occurred_at DESC);

-- Enforce operational invariants even when nodes are changed outside procedures.
CREATE OR REPLACE FUNCTION enforce_node_operational_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state = 'fenced' THEN
        NEW.fenced := TRUE;
        NEW.reachable := FALSE;
        NEW.role := 'replica';
    END IF;

    IF NEW.fenced AND NEW.role = 'primary' THEN
        RAISE EXCEPTION 'A fenced node cannot hold the primary role';
    END IF;

    IF NEW.state = 'down' AND NEW.reachable THEN
        RAISE EXCEPTION 'A down node cannot be reachable';
    END IF;

    IF NEW.state = 'healthy' AND (NOT NEW.reachable OR NEW.fenced) THEN
        RAISE EXCEPTION 'A healthy node must be reachable and unfenced';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_node_operational_state
BEFORE INSERT OR UPDATE ON cluster_nodes
FOR EACH ROW
EXECUTE FUNCTION enforce_node_operational_state();


/*
 * Transactional write path.
 *
 * The cluster row is locked to serialize commits against failover.
 * A write is accepted only when the primary is healthy and the configured
 * synchronous acknowledgement count can establish a majority.
 *
 * Selected synchronous replicas receive the committed index in the same
 * transaction. Other healthy replicas are allowed to lag.
 */
CREATE OR REPLACE FUNCTION record_quorum_write(
    p_cluster_id BIGINT,
    p_payload JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_cluster ha_clusters%ROWTYPE;
    v_primary cluster_nodes%ROWTYPE;
    v_live_voters INTEGER;
    v_required_voters INTEGER;
    v_required_replica_acks INTEGER;
    v_available_replicas INTEGER;
    v_new_index BIGINT;
    v_updated_replicas INTEGER;
BEGIN
    IF p_payload IS NULL THEN
        RAISE EXCEPTION 'Write payload cannot be NULL';
    END IF;

    SELECT *
    INTO v_cluster
    FROM ha_clusters
    WHERE cluster_id = p_cluster_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown cluster %', p_cluster_id;
    END IF;

    SELECT *
    INTO v_primary
    FROM cluster_nodes
    WHERE cluster_id = p_cluster_id
      AND node_id = v_cluster.current_primary_node_id
    FOR UPDATE;

    IF NOT FOUND
       OR v_primary.role <> 'primary'
       OR v_primary.state <> 'healthy'
       OR NOT v_primary.reachable
       OR v_primary.fenced THEN
        RAISE EXCEPTION 'Current primary is not operational';
    END IF;

    v_required_voters := (v_cluster.expected_voters / 2) + 1;

    SELECT COUNT(*)
    INTO v_live_voters
    FROM cluster_nodes
    WHERE cluster_id = p_cluster_id
      AND voter
      AND reachable
      AND state = 'healthy'
      AND NOT fenced;

    IF v_live_voters < v_required_voters THEN
        RAISE EXCEPTION
            'Write rejected: quorum requires %, but only % voters are live',
            v_required_voters,
            v_live_voters;
    END IF;

    v_required_replica_acks := GREATEST(
        v_cluster.synchronous_replica_acks,
        v_required_voters - 1
    );

    SELECT COUNT(*)
    INTO v_available_replicas
    FROM cluster_nodes
    WHERE cluster_id = p_cluster_id
      AND node_id <> v_cluster.current_primary_node_id
      AND role = 'replica'
      AND voter
      AND reachable
      AND state = 'healthy'
      AND NOT fenced;

    IF v_available_replicas < v_required_replica_acks THEN
        RAISE EXCEPTION
            'Write rejected: required % replica acknowledgements, available %',
            v_required_replica_acks,
            v_available_replicas;
    END IF;

    v_new_index := v_cluster.commit_index + 1;

    -- A deterministic priority order makes acknowledgement selection repeatable.
    WITH selected_replicas AS (
        SELECT node_id
        FROM cluster_nodes
        WHERE cluster_id = p_cluster_id
          AND node_id <> v_cluster.current_primary_node_id
          AND role = 'replica'
          AND voter
          AND reachable
          AND state = 'healthy'
          AND NOT fenced
        ORDER BY priority, node_id
        LIMIT v_required_replica_acks
        FOR UPDATE
    )
    UPDATE cluster_nodes AS target
    SET applied_index = v_new_index,
        lag_ms = 0,
        last_heartbeat_at = CURRENT_TIMESTAMP
    FROM selected_replicas AS selected
    WHERE target.node_id = selected.node_id;

    GET DIAGNOSTICS v_updated_replicas = ROW_COUNT;

    IF v_updated_replicas < v_required_replica_acks THEN
        RAISE EXCEPTION 'Synchronous acknowledgement set changed during commit';
    END IF;

    UPDATE cluster_nodes
    SET applied_index = v_new_index,
        lag_ms = 0,
        last_heartbeat_at = CURRENT_TIMESTAMP
    WHERE node_id = v_cluster.current_primary_node_id;

    -- Remaining asynchronous replicas are not falsely reported as caught up.
    UPDATE cluster_nodes
    SET lag_ms = lag_ms + 100
    WHERE cluster_id = p_cluster_id
      AND node_id <> v_cluster.current_primary_node_id
      AND role = 'replica'
      AND voter
      AND reachable
      AND state = 'healthy'
      AND NOT fenced
      AND applied_index < v_new_index;

    UPDATE ha_clusters
    SET commit_index = v_new_index
    WHERE cluster_id = p_cluster_id;

    INSERT INTO committed_writes (
        cluster_id,
        write_index,
        payload
    )
    VALUES (
        p_cluster_id,
        v_new_index,
        p_payload
    );

    RETURN v_new_index;
END;
$$;


/*
 * Pure eligibility evaluation.
 *
 * The function does not alter node roles, cluster terms, or fencing state.
 * It returns one row explaining whether promotion is currently safe.
 */
CREATE OR REPLACE FUNCTION evaluate_failover(
    p_cluster_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    candidate_node_id BIGINT,
    live_voters INTEGER,
    live_zones INTEGER,
    reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cluster ha_clusters%ROWTYPE;
    v_required_voters INTEGER;
    v_live_voters INTEGER;
    v_live_zones INTEGER;
    v_primary_healthy BOOLEAN;
    v_candidate_node_id BIGINT;
BEGIN
    SELECT *
    INTO v_cluster
    FROM ha_clusters
    WHERE cluster_id = p_cluster_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown cluster %', p_cluster_id;
    END IF;

    v_required_voters := (v_cluster.expected_voters / 2) + 1;

    SELECT
        COUNT(*),
        COUNT(DISTINCT availability_zone)
    INTO
        v_live_voters,
        v_live_zones
    FROM cluster_nodes
    WHERE cluster_id = p_cluster_id
      AND voter
      AND reachable
      AND state = 'healthy'
      AND NOT fenced;

    SELECT EXISTS (
        SELECT 1
        FROM cluster_nodes
        WHERE cluster_id = p_cluster_id
          AND node_id = v_cluster.current_primary_node_id
          AND role = 'primary'
          AND state = 'healthy'
          AND reachable
          AND NOT fenced
    )
    INTO v_primary_healthy;

    SELECT node_id
    INTO v_candidate_node_id
    FROM cluster_nodes
    WHERE cluster_id = p_cluster_id
      AND node_id <> v_cluster.current_primary_node_id
      AND role = 'replica'
      AND voter
      AND reachable
      AND state = 'healthy'
      AND NOT fenced
      AND applied_index >= v_cluster.commit_index
      AND lag_ms <= v_cluster.maximum_lag_ms
    ORDER BY applied_index DESC, priority, node_id
    LIMIT 1;

    IF v_primary_healthy THEN
        RETURN QUERY
        SELECT
            FALSE,
            NULL::BIGINT,
            v_live_voters,
            v_live_zones,
            'Current primary is healthy'::TEXT;
        RETURN;
    END IF;

    IF v_live_voters < v_required_voters THEN
        RETURN QUERY
        SELECT
            FALSE,
            NULL::BIGINT,
            v_live_voters,
            v_live_zones,
            'Majority quorum is unavailable'::TEXT;
        RETURN;
    END IF;

    IF v_live_zones < v_cluster.minimum_live_zones THEN
        RETURN QUERY
        SELECT
            FALSE,
            NULL::BIGINT,
            v_live_voters,
            v_live_zones,
            'Insufficient live availability zones'::TEXT;
        RETURN;
    END IF;

    IF v_candidate_node_id IS NULL THEN
        RETURN QUERY
        SELECT
            FALSE,
            NULL::BIGINT,
            v_live_voters,
            v_live_zones,
            'No fully caught-up replica satisfies the lag policy'::TEXT;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        TRUE,
        v_candidate_node_id,
        v_live_voters,
        v_live_zones,
        'Quorum and replication safety conditions are satisfied'::TEXT;
END;
$$;


/*
 * Atomic promotion workflow.
 *
 * The cluster row lock serializes concurrent failover requests and write
 * transactions. The former primary is fenced before the new primary is
 * assigned. A term increment distinguishes the new writer generation.
 */
CREATE OR REPLACE PROCEDURE perform_failover(
    p_cluster_id BIGINT,
    p_reason TEXT DEFAULT 'automatic health-check failover'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cluster ha_clusters%ROWTYPE;
    v_decision RECORD;
    v_old_primary BIGINT;
    v_new_term BIGINT;
BEGIN
    SELECT *
    INTO v_cluster
    FROM ha_clusters
    WHERE cluster_id = p_cluster_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown cluster %', p_cluster_id;
    END IF;

    SELECT *
    INTO v_decision
    FROM evaluate_failover(p_cluster_id);

    IF NOT v_decision.eligible OR v_decision.candidate_node_id IS NULL THEN
        RAISE EXCEPTION 'Failover rejected: %', v_decision.reason
            USING ERRCODE = '55000';
    END IF;

    v_old_primary := v_cluster.current_primary_node_id;
    v_new_term := v_cluster.term + 1;

    PERFORM 1
    FROM cluster_nodes
    WHERE cluster_id = p_cluster_id
      AND node_id = v_decision.candidate_node_id
    FOR UPDATE;

    -- Remove the candidate's old upstream link before changing topology.
    DELETE FROM replication_links
    WHERE cluster_id = p_cluster_id
      AND target_node_id = v_decision.candidate_node_id;

    -- Existing links from the former primary are redirected to the promoted node.
    UPDATE replication_links
    SET source_node_id = v_decision.candidate_node_id
    WHERE cluster_id = p_cluster_id
      AND source_node_id = v_old_primary
      AND target_node_id <> v_decision.candidate_node_id;

    -- Fencing makes the former primary ineligible to serve writes.
    UPDATE cluster_nodes
    SET role = 'replica',
        state = 'fenced',
        fenced = TRUE,
        reachable = FALSE
    WHERE cluster_id = p_cluster_id
      AND node_id = v_old_primary;

    UPDATE cluster_nodes
    SET role = 'primary',
        state = 'healthy',
        fenced = FALSE,
        reachable = TRUE,
        last_heartbeat_at = CURRENT_TIMESTAMP
    WHERE cluster_id = p_cluster_id
      AND node_id = v_decision.candidate_node_id;

    UPDATE ha_clusters
    SET current_primary_node_id = v_decision.candidate_node_id,
        term = v_new_term
    WHERE cluster_id = p_cluster_id;

    INSERT INTO failover_events (
        cluster_id,
        previous_primary_node_id,
        promoted_node_id,
        previous_term,
        new_term,
        commit_index_at_promotion,
        reason
    )
    VALUES (
        p_cluster_id,
        v_old_primary,
        v_decision.candidate_node_id,
        v_cluster.term,
        v_new_term,
        v_cluster.commit_index,
        COALESCE(NULLIF(p_reason, ''), 'automatic failover')
    );
END;
$$;


/*
 * Recovery workflow.
 *
 * A previous primary is not simply switched back on. It is reintroduced as
 * a replica and synchronized to the current committed index.
 */
CREATE OR REPLACE PROCEDURE rejoin_as_replica(
    p_cluster_id BIGINT,
    p_node_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cluster ha_clusters%ROWTYPE;
    v_node cluster_nodes%ROWTYPE;
BEGIN
    SELECT *
    INTO v_cluster
    FROM ha_clusters
    WHERE cluster_id = p_cluster_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown cluster %', p_cluster_id;
    END IF;

    SELECT *
    INTO v_node
    FROM cluster_nodes
    WHERE cluster_id = p_cluster_id
      AND node_id = p_node_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown node % in cluster %', p_node_id, p_cluster_id;
    END IF;

    IF p_node_id = v_cluster.current_primary_node_id THEN
        RAISE EXCEPTION 'The active primary cannot rejoin as a replica';
    END IF;

    UPDATE cluster_nodes
    SET role = 'replica',
        state = 'healthy',
        fenced = FALSE,
        reachable = TRUE,
        applied_index = v_cluster.commit_index,
        lag_ms = 0,
        last_heartbeat_at = CURRENT_TIMESTAMP
    WHERE cluster_id = p_cluster_id
      AND node_id = p_node_id;

    -- Rebuild the upstream replication relationship.
    INSERT INTO replication_links (
        cluster_id,
        source_node_id,
        target_node_id,
        mode,
        enabled
    )
    VALUES (
        p_cluster_id,
        v_cluster.current_primary_node_id,
        p_node_id,
        'asynchronous',
        TRUE
    )
    ON CONFLICT (cluster_id, source_node_id, target_node_id)
    DO UPDATE SET enabled = TRUE;
END;
$$;


/*
 * Operational reporting views.
 */

CREATE OR REPLACE VIEW cluster_health AS
SELECT
    c.cluster_id,
    c.cluster_name,
    c.current_primary_node_id,
    primary_node.node_name AS primary_name,
    c.term,
    c.commit_index,
    c.recovery_point_mode,
    (c.expected_voters / 2) + 1 AS quorum_required,
    COUNT(n.node_id) FILTER (
        WHERE n.voter
          AND n.reachable
          AND n.state = 'healthy'
          AND NOT n.fenced
    ) AS live_voters,
    COUNT(DISTINCT n.availability_zone) FILTER (
        WHERE n.voter
          AND n.reachable
          AND n.state = 'healthy'
          AND NOT n.fenced
    ) AS live_zones,
    COUNT(n.node_id) FILTER (
        WHERE n.role = 'replica'
          AND n.state = 'healthy'
          AND n.reachable
          AND NOT n.fenced
    ) AS healthy_replicas,
    MAX(n.lag_ms) FILTER (
        WHERE n.role = 'replica'
          AND n.state = 'healthy'
          AND n.reachable
          AND NOT n.fenced
    ) AS maximum_live_replica_lag_ms
FROM ha_clusters AS c
LEFT JOIN cluster_nodes AS n
    ON n.cluster_id = c.cluster_id
LEFT JOIN cluster_nodes AS primary_node
    ON primary_node.cluster_id = c.cluster_id
   AND primary_node.node_id = c.current_primary_node_id
GROUP BY
    c.cluster_id,
    c.cluster_name,
    c.current_primary_node_id,
    primary_node.node_name,
    c.term,
    c.commit_index,
    c.recovery_point_mode,
    c.expected_voters;

CREATE OR REPLACE VIEW replication_status AS
SELECT
    link.cluster_id,
    source.node_name AS source_node,
    source.availability_zone AS source_zone,
    target.node_name AS target_node,
    target.availability_zone AS target_zone,
    link.mode,
    link.enabled,
    source.applied_index AS source_applied_index,
    target.applied_index AS target_applied_index,
    GREATEST(source.applied_index - target.applied_index, 0) AS index_gap,
    target.lag_ms
FROM replication_links AS link
JOIN cluster_nodes AS source
    ON source.cluster_id = link.cluster_id
   AND source.node_id = link.source_node_id
JOIN cluster_nodes AS target
    ON target.cluster_id = link.cluster_id
   AND target.node_id = link.target_node_id;


/*
 * Sample production-like topology.
 *
 * Three voters are distributed over three independent zones.
 * db-b acknowledges writes synchronously. db-c represents an asynchronous
 * replica that may lag. The cluster requires two live zones for failover.
 */
DO $$
DECLARE
    v_cluster_id BIGINT;
    v_db_a BIGINT;
    v_db_b BIGINT;
    v_db_c BIGINT;
BEGIN
    INSERT INTO ha_clusters (
        cluster_name,
        expected_voters,
        synchronous_replica_acks,
        maximum_lag_ms,
        minimum_live_zones,
        recovery_point_mode
    )
    VALUES (
        'orders-production',
        3,
        1,
        500,
        2,
        'zero_data_loss'
    )
    RETURNING cluster_id INTO v_cluster_id;

    INSERT INTO cluster_nodes (
        cluster_id,
        node_name,
        availability_zone,
        role,
        priority,
        applied_index,
        last_heartbeat_at
    )
    VALUES (
        v_cluster_id,
        'db-a',
        'zone-a',
        'primary',
        0,
        0,
        CURRENT_TIMESTAMP
    )
    RETURNING node_id INTO v_db_a;

    INSERT INTO cluster_nodes (
        cluster_id,
        node_name,
        availability_zone,
        role,
        priority,
        applied_index,
        last_heartbeat_at
    )
    VALUES (
        v_cluster_id,
        'db-b',
        'zone-b',
        'replica',
        1,
        0,
        CURRENT_TIMESTAMP
    )
    RETURNING node_id INTO v_db_b;

    INSERT INTO cluster_nodes (
        cluster_id,
        node_name,
        availability_zone,
        role,
        priority,
        applied_index,
        last_heartbeat_at
    )
    VALUES (
        v_cluster_id,
        'db-c',
        'zone-c',
        'replica',
        2,
        0,
        CURRENT_TIMESTAMP
    )
    RETURNING node_id INTO v_db_c;

    UPDATE ha_clusters
    SET current_primary_node_id = v_db_a
    WHERE cluster_id = v_cluster_id;

    INSERT INTO replication_links (
        cluster_id,
        source_node_id,
        target_node_id,
        mode
    )
    VALUES
        (v_cluster_id, v_db_a, v_db_b, 'synchronous'),
        (v_cluster_id, v_db_a, v_db_c, 'asynchronous');

    INSERT INTO health_checks (
        cluster_id,
        node_id,
        result,
        latency_ms,
        diagnostic
    )
    VALUES
        (v_cluster_id, v_db_a, 'healthy', 4, 'Primary heartbeat received'),
        (v_cluster_id, v_db_b, 'healthy', 6, 'Synchronous replica available'),
        (v_cluster_id, v_db_c, 'healthy', 12, 'Asynchronous replica available');

    -- Both writes are acknowledged by db-a and db-b.
    -- db-c is allowed to remain behind.
    PERFORM record_quorum_write(
        v_cluster_id,
        '{"order_id": "ORD-1001", "operation": "insert"}'::JSONB
    );

    PERFORM record_quorum_write(
        v_cluster_id,
        '{"order_id": "ORD-1002", "operation": "update"}'::JSONB
    );

    -- The primary fails. Two voters remain reachable across two zones.
    UPDATE cluster_nodes
    SET state = 'down',
        reachable = FALSE
    WHERE cluster_id = v_cluster_id
      AND node_id = v_db_a;

    INSERT INTO health_checks (
        cluster_id,
        node_id,
        result,
        diagnostic
    )
    VALUES (
        v_cluster_id,
        v_db_a,
        'failed',
        'Heartbeat timeout; primary marked unavailable'
    );

    -- db-b has every committed write; db-c does not.
    -- Promotion is safe because db-b has the committed index.
    CALL perform_failover(
        v_cluster_id,
        'Primary heartbeat timeout in zone-a'
    );

    -- The former primary must return as a replica, not as a second writer.
    CALL rejoin_as_replica(v_cluster_id, v_db_a);
END;
$$;


/*
 * Retrieval: cluster state, current writer, quorum, and zone distribution.
 */
SELECT *
FROM cluster_health
ORDER BY cluster_id;

/*
 * Retrieval: current replication topology and replica positions.
 */
SELECT *
FROM replication_status
ORDER BY cluster_id, target_node;

/*
 * Validation: compare each live node's applied index with the commit index.
 * A node behind the commit index is not eligible under zero-data-loss policy.
 */
SELECT
    c.cluster_name,
    n.node_name,
    n.role,
    n.state,
    n.applied_index,
    c.commit_index,
    n.lag_ms,
    CASE
        WHEN n.applied_index >= c.commit_index
         AND n.lag_ms <= c.maximum_lag_ms
         AND n.state = 'healthy'
         AND n.reachable
         AND NOT n.fenced
        THEN TRUE
        ELSE FALSE
    END AS replication_eligible
FROM ha_clusters AS c
JOIN cluster_nodes AS n
    ON n.cluster_id = c.cluster_id
ORDER BY c.cluster_name, n.node_name;

/*
 * Aggregation: replica count and maximum observed lag by availability zone.
 */
SELECT
    c.cluster_name,
    n.availability_zone,
    COUNT(*) AS node_count,
    COUNT(*) FILTER (WHERE n.state = 'healthy' AND n.reachable) AS live_nodes,
    MAX(n.lag_ms) AS maximum_replica_lag_ms
FROM ha_clusters AS c
JOIN cluster_nodes AS n
    ON n.cluster_id = c.cluster_id
GROUP BY c.cluster_name, n.availability_zone
ORDER BY c.cluster_name, n.availability_zone;

/*
 * Evaluation: expose the decision without changing cluster state.
 */
SELECT
    c.cluster_name,
    decision.eligible,
    decision.candidate_node_id,
    decision.live_voters,
    decision.live_zones,
    decision.reason
FROM ha_clusters AS c
CROSS JOIN LATERAL evaluate_failover(c.cluster_id) AS decision;

/*
 * Workflow reporting: inspect committed writes and promotion history.
 */
SELECT
    c.cluster_name,
    w.write_index,
    w.payload,
    w.committed_at
FROM committed_writes AS w
JOIN ha_clusters AS c
    ON c.cluster_id = w.cluster_id
ORDER BY c.cluster_name, w.write_index;

SELECT
    c.cluster_name,
    old_node.node_name AS previous_primary,
    new_node.node_name AS promoted_primary,
    event.previous_term,
    event.new_term,
    event.commit_index_at_promotion,
    event.reason,
    event.occurred_at
FROM failover_events AS event
JOIN ha_clusters AS c
    ON c.cluster_id = event.cluster_id
LEFT JOIN cluster_nodes AS old_node
    ON old_node.node_id = event.previous_primary_node_id
JOIN cluster_nodes AS new_node
    ON new_node.node_id = event.promoted_node_id
ORDER BY event.occurred_at DESC;

/*
 * Health reporting: latest observation for each node.
 */
SELECT DISTINCT ON (c.cluster_name, n.node_name)
    c.cluster_name,
    n.node_name,
    h.result,
    h.latency_ms,
    h.diagnostic,
    h.observed_at
FROM health_checks AS h
JOIN cluster_nodes AS n
    ON n.cluster_id = h.cluster_id
   AND n.node_id = h.node_id
JOIN ha_clusters AS c
    ON c.cluster_id = h.cluster_id
ORDER BY c.cluster_name, n.node_name, h.observed_at DESC;

/*
 * Transactional failure demonstration.
 *
 * This subtransaction intentionally attempts a write after the primary has
 * been fenced and verifies that the operation is rejected. The exception is
 * caught so the complete script remains executable.
 */
DO $$
DECLARE
    v_cluster_id BIGINT;
BEGIN
    SELECT cluster_id
    INTO v_cluster_id
    FROM ha_clusters
    WHERE cluster_name = 'orders-production';

    BEGIN
        PERFORM record_quorum_write(
            v_cluster_id,
            '{"order_id": "ORD-FAIL", "operation": "invalid-write"}'::JSONB
        );
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected write rejection: %', SQLERRM;
    END;
END;
$$;
