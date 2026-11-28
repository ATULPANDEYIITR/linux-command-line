-- ============================================================
-- Kubernetes Deployments and ReplicaSets
-- PostgreSQL 15+
--
-- Relational simulation of:
--   Deployments
--   Declarative specifications
--   ReplicaSets
--   Pods
--   Revisions
--   Rolling updates
--   Readiness
--   Rollbacks
--   Deployment status
--   Reconciliation
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS orchestration;

SET search_path TO orchestration, public;

-- ------------------------------------------------------------
-- ENUM TYPES
-- ------------------------------------------------------------

CREATE TYPE deployment_phase AS ENUM (
    'Progressing',
    'Available',
    'Degraded',
    'Failed'
);

CREATE TYPE replica_set_phase AS ENUM (
    'Active',
    'Inactive'
);

CREATE TYPE pod_phase AS ENUM (
    'Pending',
    'Running',
    'Terminating',
    'Terminated',
    'Failed'
);

CREATE TYPE rollout_strategy AS ENUM (
    'RollingUpdate',
    'Recreate'
);

CREATE TYPE rollout_operation AS ENUM (
    'Create',
    'Terminate',
    'Wait',
    'Completed',
    'Failed'
);

-- ------------------------------------------------------------
-- NAMESPACES
-- ------------------------------------------------------------

CREATE TABLE namespaces (
    namespace_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    namespace_name VARCHAR(63) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_namespace_name
        CHECK (
            namespace_name ~
            '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        )
);

-- ------------------------------------------------------------
-- DEPLOYMENTS
-- ------------------------------------------------------------

CREATE TABLE deployments (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    namespace_id BIGINT NOT NULL
        REFERENCES namespaces(namespace_id),

    deployment_name VARCHAR(63) NOT NULL,

    desired_replicas INTEGER NOT NULL DEFAULT 1,

    container_name VARCHAR(63) NOT NULL,

    container_image VARCHAR(255) NOT NULL,

    container_port INTEGER NOT NULL DEFAULT 8080,

    strategy rollout_strategy NOT NULL DEFAULT 'RollingUpdate',

    max_surge INTEGER NOT NULL DEFAULT 1,

    max_unavailable INTEGER NOT NULL DEFAULT 0,

    min_ready_seconds INTEGER NOT NULL DEFAULT 0,

    revision_history_limit INTEGER NOT NULL DEFAULT 5,

    generation INTEGER NOT NULL DEFAULT 1,

    current_revision INTEGER NOT NULL DEFAULT 1,

    phase deployment_phase NOT NULL DEFAULT 'Progressing',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_deployment
        UNIQUE(namespace_id, deployment_name),

    CONSTRAINT valid_deployment_name
        CHECK (
            deployment_name ~
            '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        ),

    CONSTRAINT valid_desired_replicas
        CHECK (desired_replicas >= 0),

    CONSTRAINT valid_container_port
        CHECK (container_port BETWEEN 1 AND 65535),

    CONSTRAINT valid_rolling_update
        CHECK (
            max_surge >= 0
            AND max_unavailable >= 0
            AND (
                max_surge > 0
                OR max_unavailable > 0
            )
        ),

    CONSTRAINT valid_min_ready_seconds
        CHECK (min_ready_seconds >= 0),

    CONSTRAINT valid_history_limit
        CHECK (revision_history_limit >= 0),

    CONSTRAINT valid_generation
        CHECK (generation >= 1),

    CONSTRAINT valid_revision
        CHECK (current_revision >= 1),

    CONSTRAINT valid_image
        CHECK (length(trim(container_image)) > 0)
);

CREATE INDEX idx_deployments_namespace
    ON deployments(namespace_id);

CREATE INDEX idx_deployments_phase
    ON deployments(phase);

-- ------------------------------------------------------------
-- DEPLOYMENT REVISION HISTORY
-- ------------------------------------------------------------

CREATE TABLE deployment_revisions (
    revision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id)
        ON DELETE CASCADE,

    revision_number INTEGER NOT NULL,

    container_image VARCHAR(255) NOT NULL,

    desired_replicas INTEGER NOT NULL,

    container_port INTEGER NOT NULL,

    max_surge INTEGER NOT NULL,

    max_unavailable INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(deployment_id, revision_number),

    CHECK (revision_number > 0),

    CHECK (desired_replicas >= 0),

    CHECK (container_port BETWEEN 1 AND 65535),

    CHECK (
        max_surge >= 0
        AND max_unavailable >= 0
    )
);

CREATE INDEX idx_revision_history
    ON deployment_revisions(
        deployment_id,
        revision_number DESC
    );

-- ------------------------------------------------------------
-- REPLICASETS
-- ------------------------------------------------------------

CREATE TABLE replica_sets (
    replica_set_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id)
        ON DELETE CASCADE,

    revision_number INTEGER NOT NULL,

    replica_set_name VARCHAR(100) NOT NULL UNIQUE,

    container_image VARCHAR(255) NOT NULL,

    desired_replicas INTEGER NOT NULL DEFAULT 0,

    phase replica_set_phase NOT NULL DEFAULT 'Active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_deployment_revision
        UNIQUE(deployment_id, revision_number),

    CONSTRAINT valid_replica_set_replicas
        CHECK (desired_replicas >= 0)
);

CREATE INDEX idx_replica_sets_deployment
    ON replica_sets(deployment_id, phase);

CREATE INDEX idx_replica_sets_revision
    ON replica_sets(deployment_id, revision_number DESC);

-- ------------------------------------------------------------
-- PODS
-- ------------------------------------------------------------

CREATE TABLE pods (
    pod_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    replica_set_id BIGINT NOT NULL
        REFERENCES replica_sets(replica_set_id)
        ON DELETE CASCADE,

    pod_name VARCHAR(120) NOT NULL UNIQUE,

    container_image VARCHAR(255) NOT NULL,

    phase pod_phase NOT NULL DEFAULT 'Pending',

    ready BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    started_at TIMESTAMPTZ,

    ready_since TIMESTAMPTZ,

    terminated_at TIMESTAMPTZ,

    CONSTRAINT valid_pod_readiness
        CHECK (
            NOT ready
            OR phase = 'Running'
        ),

    CONSTRAINT valid_ready_timestamp
        CHECK (
            ready_since IS NULL
            OR ready = TRUE
        )
);

CREATE INDEX idx_pods_replica_set
    ON pods(replica_set_id, phase);

CREATE INDEX idx_pods_ready
    ON pods(ready, phase);

CREATE INDEX idx_pods_image
    ON pods(container_image);

-- ------------------------------------------------------------
-- ROLLOUT OPERATIONS
-- ------------------------------------------------------------

CREATE TABLE rollout_operations (
    operation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id)
        ON DELETE CASCADE,

    revision_number INTEGER NOT NULL,

    operation rollout_operation NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rollout_operations
    ON rollout_operations(
        deployment_id,
        created_at DESC
    );

-- ------------------------------------------------------------
-- RECONCILIATION AUDIT
-- ------------------------------------------------------------

CREATE TABLE reconciliation_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    deployment_id BIGINT NOT NULL
        REFERENCES deployments(deployment_id)
        ON DELETE CASCADE,

    desired_replicas INTEGER NOT NULL,

    observed_replicas INTEGER NOT NULL,

    difference INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reconciliation_events
    ON reconciliation_events(
        deployment_id,
        created_at DESC
    );

-- ------------------------------------------------------------
-- VALIDATION FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_deployment_spec()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.container_image IS NULL
       OR length(trim(NEW.container_image)) = 0 THEN
        RAISE EXCEPTION 'Container image cannot be empty';
    END IF;

    IF NEW.desired_replicas < 0 THEN
        RAISE EXCEPTION 'Invalid desired replica count';
    END IF;

    IF NEW.max_surge = 0 AND NEW.max_unavailable = 0 THEN
        RAISE EXCEPTION
            'max_surge and max_unavailable cannot both be zero';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF NEW.deployment_id <> OLD.deployment_id THEN
            RAISE EXCEPTION 'Deployment identity cannot change';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_deployment
BEFORE INSERT OR UPDATE ON deployments
FOR EACH ROW
EXECUTE FUNCTION validate_deployment_spec();

-- ------------------------------------------------------------
-- GENERATION MANAGEMENT
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_deployment_generation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.desired_replicas,
        NEW.container_image,
        NEW.container_port,
        NEW.max_surge,
        NEW.max_unavailable,
        NEW.strategy,
        NEW.min_ready_seconds
    ) IS DISTINCT FROM ROW(
        OLD.desired_replicas,
        OLD.container_image,
        OLD.container_port,
        OLD.max_surge,
        OLD.max_unavailable,
        OLD.strategy,
        OLD.min_ready_seconds
    ) THEN

        NEW.generation := OLD.generation + 1;
        NEW.updated_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_deployment_generation
BEFORE UPDATE ON deployments
FOR EACH ROW
EXECUTE FUNCTION update_deployment_generation();

-- ------------------------------------------------------------
-- REVISION SNAPSHOT FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION create_deployment_revision()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO deployment_revisions (
        deployment_id,
        revision_number,
        container_image,
        desired_replicas,
        container_port,
        max_surge,
        max_unavailable
    )
    VALUES (
        NEW.deployment_id,
        NEW.current_revision,
        NEW.container_image,
        NEW.desired_replicas,
        NEW.container_port,
        NEW.max_surge,
        NEW.max_unavailable
    )
    ON CONFLICT (deployment_id, revision_number)
    DO UPDATE SET
        container_image = EXCLUDED.container_image,
        desired_replicas = EXCLUDED.desired_replicas,
        container_port = EXCLUDED.container_port,
        max_surge = EXCLUDED.max_surge,
        max_unavailable = EXCLUDED.max_unavailable;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_create_initial_revision
AFTER INSERT ON deployments
FOR EACH ROW
EXECUTE FUNCTION create_deployment_revision();

-- ------------------------------------------------------------
-- REPLICASET CREATION FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION create_replica_set(
    p_deployment_id BIGINT,
    p_revision INTEGER,
    p_image VARCHAR,
    p_desired INTEGER
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_replica_set_id BIGINT;
    v_name VARCHAR(100);
BEGIN
    IF p_desired < 0 THEN
        RAISE EXCEPTION 'Desired replicas cannot be negative';
    END IF;

    IF p_image IS NULL OR length(trim(p_image)) = 0 THEN
        RAISE EXCEPTION 'Image is required';
    END IF;

    v_name := 'rs-' || p_deployment_id || '-' || p_revision;

    INSERT INTO replica_sets (
        deployment_id,
        revision_number,
        replica_set_name,
        container_image,
        desired_replicas
    )
    VALUES (
        p_deployment_id,
        p_revision,
        v_name,
        p_image,
        p_desired
    )
    RETURNING replica_set_id INTO v_replica_set_id;

    RETURN v_replica_set_id;
END;
$$;

-- ------------------------------------------------------------
-- POD CREATION FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION create_pod(
    p_replica_set_id BIGINT,
    p_image VARCHAR
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_pod_id BIGINT;
    v_pod_name VARCHAR(120);
BEGIN
    IF p_image IS NULL OR length(trim(p_image)) = 0 THEN
        RAISE EXCEPTION 'Pod image is required';
    END IF;

    v_pod_name :=
        'pod-' || p_replica_set_id || '-' ||
        substr(md5(random()::text || clock_timestamp()::text), 1, 12);

    INSERT INTO pods (
        replica_set_id,
        pod_name,
        container_image
    )
    VALUES (
        p_replica_set_id,
        v_pod_name,
        p_image
    )
    RETURNING pod_id INTO v_pod_id;

    UPDATE pods
    SET
        phase = 'Running',
        started_at = CURRENT_TIMESTAMP
    WHERE pod_id = v_pod_id;

    RETURN v_pod_id;
END;
$$;

-- ------------------------------------------------------------
-- POD READINESS FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_pod_readiness(
    p_pod_id BIGINT,
    p_ready BOOLEAN
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_phase pod_phase;
BEGIN
    SELECT phase
    INTO v_phase
    FROM pods
    WHERE pod_id = p_pod_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pod % does not exist', p_pod_id;
    END IF;

    IF v_phase <> 'Running' THEN
        RAISE EXCEPTION 'Only running pods can change readiness';
    END IF;

    UPDATE pods
    SET
        ready = p_ready,
        ready_since = CASE
            WHEN p_ready THEN CURRENT_TIMESTAMP
            ELSE NULL
        END
    WHERE pod_id = p_pod_id;
END;
$$;

-- ------------------------------------------------------------
-- POD TERMINATION FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION terminate_pod(
    p_pod_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE pods
    SET
        phase = 'Terminated',
        ready = FALSE,
        ready_since = NULL,
        terminated_at = CURRENT_TIMESTAMP
    WHERE pod_id = p_pod_id
      AND phase NOT IN ('Terminated', 'Failed');

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active pod % does not exist', p_pod_id;
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- RECONCILIATION PROCEDURE
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE reconcile_deployment(
    p_deployment_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_desired INTEGER;
    v_observed INTEGER;
    v_revision INTEGER;
    v_image VARCHAR(255);

    v_rs RECORD;
    v_difference INTEGER;
    v_pod_id BIGINT;
BEGIN
    SELECT
        desired_replicas,
        current_revision,
        container_image
    INTO
        v_desired,
        v_revision,
        v_image
    FROM deployments
    WHERE deployment_id = p_deployment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Deployment % not found', p_deployment_id;
    END IF;

    -- The active ReplicaSet for the current image receives
    -- the desired replica count. Old ReplicaSets scale to zero.
    IF NOT EXISTS (
        SELECT 1
        FROM replica_sets
        WHERE deployment_id = p_deployment_id
          AND revision_number = v_revision
    ) THEN
        PERFORM create_replica_set(
            p_deployment_id,
            v_revision,
            v_image,
            v_desired
        );
    END IF;

    UPDATE replica_sets
    SET
        desired_replicas = CASE
            WHEN revision_number = v_revision THEN v_desired
            ELSE 0
        END,
        phase = CASE
            WHEN revision_number = v_revision THEN 'Active'
            ELSE 'Inactive'
        END
    WHERE deployment_id = p_deployment_id;

    FOR v_rs IN
        SELECT
            replica_set_id,
            container_image,
            desired_replicas
        FROM replica_sets
        WHERE deployment_id = p_deployment_id
        ORDER BY revision_number
    LOOP

        SELECT COUNT(*)
        INTO v_observed
        FROM pods
        WHERE replica_set_id = v_rs.replica_set_id
          AND phase NOT IN ('Terminated', 'Failed');

        v_difference := v_rs.desired_replicas - v_observed;

        IF v_difference > 0 THEN
            FOR i IN 1..v_difference LOOP
                PERFORM create_pod(
                    v_rs.replica_set_id,
                    v_rs.container_image
                );
            END LOOP;

        ELSIF v_difference < 0 THEN
            FOR v_pod_id IN
                SELECT pod_id
                FROM pods
                WHERE replica_set_id = v_rs.replica_set_id
                  AND phase NOT IN ('Terminated', 'Failed')
                ORDER BY created_at DESC
                LIMIT abs(v_difference)
            LOOP
                PERFORM terminate_pod(v_pod_id);
            END LOOP;
        END IF;

        INSERT INTO reconciliation_events (
            deployment_id,
            desired_replicas,
            observed_replicas,
            difference
        )
        SELECT
            p_deployment_id,
            v_rs.desired_replicas,
            COUNT(*)::INTEGER,
            v_rs.desired_replicas - COUNT(*)::INTEGER
        FROM pods
        WHERE replica_set_id = v_rs.replica_set_id
          AND phase NOT IN ('Terminated', 'Failed');

    END LOOP;

    CALL refresh_deployment_status(p_deployment_id);
END;
$$;

-- ------------------------------------------------------------
-- DEPLOYMENT STATUS PROCEDURE
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE refresh_deployment_status(
    p_deployment_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_desired INTEGER;
    v_ready INTEGER;
    v_available INTEGER;
    v_updated INTEGER;
    v_min_ready INTEGER;
    v_image VARCHAR(255);
BEGIN
    SELECT
        desired_replicas,
        min_ready_seconds,
        container_image
    INTO
        v_desired,
        v_min_ready,
        v_image
    FROM deployments
    WHERE deployment_id = p_deployment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Deployment not found';
    END IF;

    SELECT
        COUNT(*) FILTER (
            WHERE p.ready AND p.phase = 'Running'
        )::INTEGER,

        COUNT(*) FILTER (
            WHERE p.ready
              AND p.phase = 'Running'
              AND p.ready_since <=
                  CURRENT_TIMESTAMP -
                  make_interval(secs => v_min_ready)
        )::INTEGER,

        COUNT(*) FILTER (
            WHERE p.container_image = v_image
              AND p.phase NOT IN ('Terminated', 'Failed')
        )::INTEGER

    INTO
        v_ready,
        v_available,
        v_updated

    FROM pods p
    JOIN replica_sets rs
      ON rs.replica_set_id = p.replica_set_id

    WHERE rs.deployment_id = p_deployment_id
      AND rs.phase = 'Active'
      AND p.phase NOT IN ('Terminated', 'Failed');

    UPDATE deployments
    SET phase = CASE
        WHEN v_available >= v_desired THEN 'Available'
        WHEN v_ready > 0 THEN 'Progressing'
        ELSE 'Degraded'
    END
    WHERE deployment_id = p_deployment_id;
END;
$$;

-- ------------------------------------------------------------
-- IMAGE UPDATE PROCEDURE
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE update_deployment_image(
    p_deployment_id BIGINT,
    p_new_image VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_old_image VARCHAR(255);
    v_new_revision INTEGER;
BEGIN
    IF p_new_image IS NULL OR length(trim(p_new_image)) = 0 THEN
        RAISE EXCEPTION 'New image cannot be empty';
    END IF;

    SELECT container_image, current_revision + 1
    INTO v_old_image, v_new_revision
    FROM deployments
    WHERE deployment_id = p_deployment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Deployment not found';
    END IF;

    IF v_old_image = p_new_image THEN
        RAISE NOTICE 'Image unchanged';
        RETURN;
    END IF;

    UPDATE deployments
    SET
        container_image = p_new_image,
        current_revision = v_new_revision,
        generation = generation + 1,
        phase = 'Progressing'
    WHERE deployment_id = p_deployment_id;

    INSERT INTO deployment_revisions (
        deployment_id,
        revision_number,
        container_image,
        desired_replicas,
        container_port,
        max_surge,
        max_unavailable
    )
    SELECT
        deployment_id,
        current_revision,
        container_image,
        desired_replicas,
        container_port,
        max_surge,
        max_unavailable
    FROM deployments
    WHERE deployment_id = p_deployment_id;

    PERFORM create_replica_set(
        p_deployment_id,
        v_new_revision,
        p_new_image,
        0
    );

    INSERT INTO rollout_operations (
        deployment_id,
        revision_number,
        operation,
        details
    )
    VALUES (
        p_deployment_id,
        v_new_revision,
        'Create',
        jsonb_build_object(
            'old_image', v_old_image,
            'new_image', p_new_image
        )
    );
END;
$$;

-- ------------------------------------------------------------
-- ROLLBACK PROCEDURE
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE rollback_deployment(
    p_deployment_id BIGINT,
    p_target_revision INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_image VARCHAR(255);
BEGIN
    SELECT container_image
    INTO v_image
    FROM deployment_revisions
    WHERE deployment_id = p_deployment_id
      AND revision_number = p_target_revision;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Revision % does not exist for deployment %',
            p_target_revision,
            p_deployment_id;
    END IF;

    -- A rollback is a new revision containing an older specification.
    CALL update_deployment_image(
        p_deployment_id,
        v_image
    );

    INSERT INTO rollout_operations (
        deployment_id,
        revision_number,
        operation,
        details
    )
    SELECT
        deployment_id,
        current_revision,
        'Create',
        jsonb_build_object(
            'rollback_target', p_target_revision,
            'restored_image', v_image
        )
    FROM deployments
    WHERE deployment_id = p_deployment_id;
END;
$$;

-- ------------------------------------------------------------
-- ROLLING UPDATE STEP
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION rolling_update_step(
    p_deployment_id BIGINT
)
RETURNS rollout_operation
LANGUAGE plpgsql
AS $$
DECLARE
    v_desired INTEGER;
    v_surge INTEGER;
    v_unavailable INTEGER;
    v_current_image VARCHAR(255);

    v_total INTEGER;
    v_ready INTEGER;
    v_old INTEGER;
    v_new INTEGER;

    v_minimum_available INTEGER;
    v_maximum_total INTEGER;

    v_target_rs BIGINT;
    v_pod_id BIGINT;
    v_result rollout_operation;
BEGIN
    SELECT
        desired_replicas,
        max_surge,
        max_unavailable,
        container_image
    INTO
        v_desired,
        v_surge,
        v_unavailable,
        v_current_image
    FROM deployments
    WHERE deployment_id = p_deployment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Deployment not found';
    END IF;

    SELECT replica_set_id
    INTO v_target_rs
    FROM replica_sets
    WHERE deployment_id = p_deployment_id
      AND container_image = v_current_image
      AND phase = 'Active'
    ORDER BY revision_number DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Target ReplicaSet does not exist';
    END IF;

    SELECT
        COUNT(*)::INTEGER,
        COUNT(*) FILTER (
            WHERE p.ready AND p.phase = 'Running'
        )::INTEGER
    INTO v_total, v_ready
    FROM pods p
    JOIN replica_sets rs
      ON rs.replica_set_id = p.replica_set_id
    WHERE rs.deployment_id = p_deployment_id
      AND rs.phase = 'Active'
      AND p.phase NOT IN ('Terminated', 'Failed');

    SELECT COUNT(*)::INTEGER
    INTO v_old
    FROM pods p
    JOIN replica_sets rs
      ON rs.replica_set_id = p.replica_set_id
    WHERE rs.deployment_id = p_deployment_id
      AND rs.phase = 'Active'
      AND rs.container_image <> v_current_image
      AND p.phase NOT IN ('Terminated', 'Failed');

    SELECT COUNT(*)::INTEGER
    INTO v_new
    FROM pods
    WHERE replica_set_id = v_target_rs
      AND phase NOT IN ('Terminated', 'Failed');

    v_minimum_available := GREATEST(
        0,
        v_desired - v_unavailable
    );

    v_maximum_total := v_desired + v_surge;

    IF v_new < v_desired AND v_total < v_maximum_total THEN

        PERFORM create_pod(
            v_target_rs,
            v_current_image
        );

        v_result := 'Create';

    ELSIF v_old > 0 AND v_ready > v_minimum_available THEN

        SELECT p.pod_id
        INTO v_pod_id
        FROM pods p
        JOIN replica_sets rs
          ON rs.replica_set_id = p.replica_set_id
        WHERE rs.deployment_id = p_deployment_id
          AND rs.phase = 'Active'
          AND rs.container_image <> v_current_image
          AND p.phase NOT IN ('Terminated', 'Failed')
        ORDER BY p.created_at
        LIMIT 1;

        PERFORM terminate_pod(v_pod_id);

        v_result := 'Terminate';

    ELSIF v_old = 0 AND v_new >= v_desired THEN

        v_result := 'Completed';

    ELSE
        v_result := 'Wait';
    END IF;

    INSERT INTO rollout_operations (
        deployment_id,
        revision_number,
        operation,
        details
    )
    SELECT
        deployment_id,
        current_revision,
        v_result,
        jsonb_build_object(
            'total_replicas', v_total,
            'ready_replicas', v_ready,
            'old_replicas', v_old,
            'new_replicas', v_new,
            'max_total', v_maximum_total,
            'minimum_available', v_minimum_available
        )
    FROM deployments
    WHERE deployment_id = p_deployment_id;

    CALL refresh_deployment_status(p_deployment_id);

    RETURN v_result;
END;
$$;

-- ------------------------------------------------------------
-- REPORTING VIEW
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW deployment_overview AS
SELECT
    d.deployment_id,
    n.namespace_name,
    d.deployment_name,
    d.container_image,
    d.desired_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.phase NOT IN ('Terminated', 'Failed')
    ) AS active_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.ready AND p.phase = 'Running'
    ) AS ready_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.container_image = d.container_image
          AND p.phase NOT IN ('Terminated', 'Failed')
    ) AS updated_replicas,

    d.current_revision,
    d.generation,
    d.phase

FROM deployments d

JOIN namespaces n
  ON n.namespace_id = d.namespace_id

LEFT JOIN replica_sets rs
  ON rs.deployment_id = d.deployment_id
 AND rs.phase = 'Active'

LEFT JOIN pods p
  ON p.replica_set_id = rs.replica_set_id

GROUP BY
    d.deployment_id,
    n.namespace_name,
    d.deployment_name,
    d.container_image,
    d.desired_replicas,
    d.current_revision,
    d.generation,
    d.phase;

-- ------------------------------------------------------------
-- ROLLOUT ELIGIBILITY VIEW
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW rollout_eligibility AS
SELECT
    d.deployment_id,
    d.deployment_name,
    d.current_revision,

    d.desired_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.phase NOT IN ('Terminated', 'Failed')
    ) AS active_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.ready AND p.phase = 'Running'
    ) AS ready_replicas,

    COUNT(p.pod_id) FILTER (
        WHERE p.container_image = d.container_image
          AND p.phase NOT IN ('Terminated', 'Failed')
    ) AS updated_replicas,

    CASE
        WHEN COUNT(p.pod_id) FILTER (
            WHERE p.ready AND p.phase = 'Running'
        ) >=
        GREATEST(0, d.desired_replicas - d.max_unavailable)
        THEN TRUE
        ELSE FALSE
    END AS minimum_availability_satisfied

FROM deployments d

LEFT JOIN replica_sets rs
  ON rs.deployment_id = d.deployment_id
 AND rs.phase = 'Active'

LEFT JOIN pods p
  ON p.replica_set_id = rs.replica_set_id

GROUP BY
    d.deployment_id,
    d.deployment_name,
    d.current_revision,
    d.desired_replicas,
    d.max_unavailable;

-- ============================================================
-- SAMPLE DATA
-- ============================================================

INSERT INTO namespaces(namespace_name)
VALUES
    ('production'),
    ('staging'),
    ('development');

INSERT INTO deployments (
    namespace_id,
    deployment_name,
    desired_replicas,
    container_name,
    container_image,
    container_port,
    strategy,
    max_surge,
    max_unavailable,
    min_ready_seconds,
    revision_history_limit
)
SELECT
    namespace_id,
    'orders-api',
    3,
    'orders',
    'orders-api:1.0.0',
    8080,
    'RollingUpdate',
    1,
    0,
    0,
    5
FROM namespaces
WHERE namespace_name = 'production';

INSERT INTO deployments (
    namespace_id,
    deployment_name,
    desired_replicas,
    container_name,
    container_image,
    container_port,
    strategy,
    max_surge,
    max_unavailable
)
SELECT
    namespace_id,
    'catalog-api',
    2,
    'catalog',
    'catalog-api:1.0.0',
    8081,
    'RollingUpdate',
    1,
    0
FROM namespaces
WHERE namespace_name = 'staging';

-- ------------------------------------------------------------
-- INITIAL REPLICASETS AND PODS
-- ------------------------------------------------------------

DO $$
DECLARE
    v_deployment RECORD;
    v_rs BIGINT;
    v_pod BIGINT;
BEGIN
    FOR v_deployment IN
        SELECT *
        FROM deployments
    LOOP
        v_rs := create_replica_set(
            v_deployment.deployment_id,
            v_deployment.current_revision,
            v_deployment.container_image,
            v_deployment.desired_replicas
        );

        FOR i IN 1..v_deployment.desired_replicas LOOP
            v_pod := create_pod(
                v_rs,
                v_deployment.container_image
            );

            PERFORM set_pod_readiness(v_pod, TRUE);
        END LOOP;
    END LOOP;
END;
$$;

-- ============================================================
-- DEMONSTRATION: INITIAL STATUS
-- ============================================================

SELECT *
FROM deployment_overview
ORDER BY deployment_id;

SELECT *
FROM rollout_eligibility
ORDER BY deployment_id;

-- ============================================================
-- DEMONSTRATION: IMAGE UPDATE
-- ============================================================

CALL update_deployment_image(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'orders-api'
    ),
    'orders-api:2.0.0'
);

-- The new ReplicaSet is initially scaled to zero.
-- Reconciliation creates its desired replicas.

CALL reconcile_deployment(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'orders-api'
    )
);

-- New pods must pass readiness before old pods are removed.

UPDATE pods p
SET
    ready = TRUE,
    ready_since = CURRENT_TIMESTAMP
FROM replica_sets rs
JOIN deployments d
  ON d.deployment_id = rs.deployment_id
WHERE p.replica_set_id = rs.replica_set_id
  AND rs.deployment_id = d.deployment_id
  AND rs.container_image = d.container_image
  AND d.deployment_name = 'orders-api'
  AND p.phase = 'Running';

-- Perform one rolling-update operation.

SELECT rolling_update_step(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'orders-api'
    )
);

SELECT *
FROM deployment_overview
WHERE deployment_name = 'orders-api';

-- ============================================================
-- DEMONSTRATION: ROLLBACK
-- ============================================================

CALL rollback_deployment(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'orders-api'
    ),
    1
);

CALL reconcile_deployment(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'orders-api'
    )
);

-- ============================================================
-- DEMONSTRATION: SCALING
-- ============================================================

UPDATE deployments
SET desired_replicas = 5
WHERE deployment_name = 'orders-api';

CALL reconcile_deployment(
    (
        SELECT deployment_id
        FROM deployments
        WHERE deployment_name = 'orders-api'
    )
);

-- ============================================================
-- RETRIEVAL QUERIES
-- ============================================================

-- Deployment and ReplicaSet relationships.

SELECT
    d.deployment_name,
    rs.replica_set_name,
    rs.revision_number,
    rs.container_image,
    rs.desired_replicas,
    rs.phase
FROM deployments d
JOIN replica_sets rs
  ON rs.deployment_id = d.deployment_id
ORDER BY
    d.deployment_name,
    rs.revision_number;

-- Pod-level details.

SELECT
    d.deployment_name,
    rs.replica_set_name,
    p.pod_name,
    p.container_image,
    p.phase,
    p.ready,
    p.created_at
FROM deployments d
JOIN replica_sets rs
  ON rs.deployment_id = d.deployment_id
JOIN pods p
  ON p.replica_set_id = rs.replica_set_id
ORDER BY d.deployment_name, p.created_at;

-- ============================================================
-- VALIDATION QUERIES
-- ============================================================

-- Identify deployments where observed replicas differ
-- from the desired count.

SELECT
    deployment_name,
    desired_replicas,
    active_replicas,
    ready_replicas,
    desired_replicas - active_replicas AS replica_difference
FROM deployment_overview
WHERE active_replicas <> desired_replicas;

-- Identify unready running pods.

SELECT
    p.pod_name,
    rs.replica_set_name,
    rs.container_image
FROM pods p
JOIN replica_sets rs
  ON rs.replica_set_id = p.replica_set_id
WHERE p.phase = 'Running'
  AND p.ready = FALSE;

-- Detect pods running an obsolete image.

SELECT
    p.pod_name,
    p.container_image AS pod_image,
    d.container_image AS desired_image
FROM pods p
JOIN replica_sets rs
  ON rs.replica_set_id = p.replica_set_id
JOIN deployments d
  ON d.deployment_id = rs.deployment_id
WHERE p.container_image <> d.container_image
  AND p.phase NOT IN ('Terminated', 'Failed');

-- ============================================================
-- AGGREGATION AND REPORTING
-- ============================================================

-- Active replicas grouped by namespace.

SELECT
    namespace_name,
    COUNT(DISTINCT deployment_id) AS deployments,
    SUM(active_replicas) AS active_pods,
    SUM(ready_replicas) AS ready_pods
FROM deployment_overview
GROUP BY namespace_name;

-- Deployment revision history.

SELECT
    d.deployment_name,
    r.revision_number,
    r.container_image,
    r.desired_replicas,
    r.created_at
FROM deployment_revisions r
JOIN deployments d
  ON d.deployment_id = r.deployment_id
ORDER BY
    d.deployment_name,
    r.revision_number;

-- Rollout operation audit.

SELECT
    d.deployment_name,
    o.revision_number,
    o.operation,
    o.details,
    o.created_at
FROM rollout_operations o
JOIN deployments d
  ON d.deployment_id = o.deployment_id
ORDER BY o.created_at DESC;

-- ============================================================
-- COMMON TABLE EXPRESSION: REPLICA CAPACITY
-- ============================================================

WITH replica_capacity AS (
    SELECT
        d.deployment_id,
        d.deployment_name,
        d.desired_replicas,
        COUNT(p.pod_id) FILTER (
            WHERE p.phase NOT IN ('Terminated', 'Failed')
        ) AS active_replicas,
        COUNT(p.pod_id) FILTER (
            WHERE p.ready AND p.phase = 'Running'
        ) AS ready_replicas
    FROM deployments d
    LEFT JOIN replica_sets rs
      ON rs.deployment_id = d.deployment_id
     AND rs.phase = 'Active'
    LEFT JOIN pods p
      ON p.replica_set_id = rs.replica_set_id
    GROUP BY
        d.deployment_id,
        d.deployment_name,
        d.desired_replicas
)
SELECT
    *,
    GREATEST(
        0,
        desired_replicas - ready_replicas
    ) AS unavailable_replicas
FROM replica_capacity;

-- ============================================================
-- ELIGIBILITY DETERMINATION
-- ============================================================

SELECT
    deployment_name,
    desired_replicas,
    active_replicas,
    ready_replicas,
    updated_replicas,
    minimum_availability_satisfied,
    CASE
        WHEN minimum_availability_satisfied
        THEN 'Availability budget satisfied'
        ELSE 'Availability budget violated'
    END AS rollout_decision
FROM rollout_eligibility;

-- ============================================================
-- HISTORY CLEANUP
-- Retain the configured number of recent revisions.
-- ============================================================

DELETE FROM deployment_revisions r
USING deployments d
WHERE r.deployment_id = d.deployment_id
  AND r.revision_number NOT IN (
      SELECT retained.revision_number
      FROM deployment_revisions retained
      WHERE retained.deployment_id = d.deployment_id
      ORDER BY retained.revision_number DESC
      LIMIT GREATEST(
          1,
          d.revision_history_limit
      )
  );

-- ============================================================
-- FAILURE CASE: TRANSACTION ROLLBACK
-- ============================================================

SAVEPOINT before_invalid_change;

-- This statement is rejected by the CHECK constraint.
-- It is isolated in a savepoint so the rest of the script
-- remains executable.

DO $$
BEGIN
    BEGIN
        UPDATE deployments
        SET desired_replicas = -1
        WHERE deployment_name = 'orders-api';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE
                'Invalid replica update rejected: %',
                SQLERRM;
    END;
END;
$$;

-- ============================================================
-- FINAL REPORT
-- ============================================================

SELECT *
FROM deployment_overview
ORDER BY deployment_id;

SELECT *
FROM reconciliation_events
ORDER BY created_at DESC;

SELECT *
FROM deployment_revisions
ORDER BY deployment_id, revision_number;

COMMIT;
