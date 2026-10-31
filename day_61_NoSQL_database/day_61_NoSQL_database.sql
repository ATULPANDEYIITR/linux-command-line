DROP SCHEMA IF EXISTS nosql_lab CASCADE;
CREATE SCHEMA nosql_lab;

SET search_path TO nosql_lab, public;

-- PostgreSQL is relational, so each NoSQL architecture is represented
-- according to its characteristic access pattern rather than pretending
-- that all four models have identical storage semantics.

CREATE TYPE database_model AS ENUM (
    'key-value',
    'document',
    'wide-column',
    'graph'
);

CREATE TYPE repository_status AS ENUM (
    'active',
    'archived'
);

CREATE TYPE document_status AS ENUM (
    'active',
    'inactive'
);

CREATE TYPE workflow_status AS ENUM (
    'created',
    'active',
    'completed',
    'failed'
);

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    status repository_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE architecture_decisions (
    decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    workload_name TEXT NOT NULL,
    selected_model database_model NOT NULL,
    rationale TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, workload_name)
);

-- Key-value model: one key identifies one value.
CREATE TABLE kv_entries (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    expires_at TIMESTAMPTZ,
    CHECK (length(key) BETWEEN 1 AND 256),
    CHECK (
        expires_at IS NULL
        OR expires_at > TIMESTAMPTZ '2000-01-01 00:00:00+00'
    )
);

CREATE INDEX kv_entries_expiry_idx
    ON kv_entries (expires_at)
    WHERE expires_at IS NOT NULL;

-- Document model: flexible JSONB attributes coexist with indexed
-- fields used frequently by the application.
CREATE TABLE product_documents (
    document_id TEXT PRIMARY KEY,
    document JSONB NOT NULL,
    status document_status NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(document) = 'object'),
    CHECK (document ? 'name'),
    CHECK (document ? 'category'),
    CHECK (
        jsonb_typeof(document->'price') = 'number'
        AND (document->>'price')::NUMERIC >= 0
    )
);

CREATE INDEX product_documents_category_idx
    ON product_documents ((document->>'category'));

CREATE INDEX product_documents_tags_gin_idx
    ON product_documents
    USING GIN ((document->'tags'));

CREATE INDEX product_documents_jsonb_idx
    ON product_documents
    USING GIN (document);

-- Wide-column model: a row key, column family, and sparse columns.
CREATE TABLE wide_column_cells (
    row_key TEXT NOT NULL,
    column_family TEXT NOT NULL,
    column_name TEXT NOT NULL,
    numeric_value DOUBLE PRECISION,
    text_value TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (row_key, column_family, column_name),
    CHECK (
        numeric_value IS NOT NULL
        OR text_value IS NOT NULL
    ),
    CHECK (
        NOT (
            numeric_value IS NOT NULL
            AND text_value IS NOT NULL
        )
    )
);

CREATE INDEX wide_column_family_time_idx
    ON wide_column_cells (column_family, observed_at DESC);

-- Graph model: vertices and directed edges.
CREATE TABLE graph_nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::JSONB,
    CHECK (jsonb_typeof(properties) = 'object')
);

CREATE TABLE graph_edges (
    edge_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_node TEXT NOT NULL
        REFERENCES graph_nodes(node_id)
        ON DELETE CASCADE,
    relation TEXT NOT NULL,
    target_node TEXT NOT NULL
        REFERENCES graph_nodes(node_id)
        ON DELETE CASCADE,
    properties JSONB NOT NULL DEFAULT '{}'::JSONB,
    UNIQUE (source_node, relation, target_node),
    CHECK (source_node <> target_node),
    CHECK (jsonb_typeof(properties) = 'object')
);

CREATE INDEX graph_edges_source_idx
    ON graph_edges (source_node, relation);

CREATE INDEX graph_edges_target_idx
    ON graph_edges (target_node, relation);

-- Explicit workflow state demonstrates how an application can preserve
-- state transitions independently from its selected NoSQL model.
CREATE TABLE ingestion_workflows (
    workflow_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workload_name TEXT NOT NULL,
    model database_model NOT NULL,
    state workflow_status NOT NULL DEFAULT 'created',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failure_reason TEXT,
    CHECK (
        completed_at IS NULL
        OR started_at IS NOT NULL
    ),
    CHECK (
        state <> 'completed'
        OR completed_at IS NOT NULL
    ),
    CHECK (
        state <> 'failed'
        OR failure_reason IS NOT NULL
    )
);

CREATE OR REPLACE FUNCTION validate_workflow_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'completed'
       AND NEW.state <> 'completed' THEN
        RAISE EXCEPTION
            'Completed workflow % cannot transition to %',
            OLD.workflow_id,
            NEW.state;
    END IF;

    IF OLD.state = 'failed'
       AND NEW.state <> 'failed' THEN
        RAISE EXCEPTION
            'Failed workflow % cannot transition to %',
            OLD.workflow_id,
            NEW.state;
    END IF;

    IF NEW.state = 'active' AND NEW.started_at IS NULL THEN
        NEW.started_at := now();
    END IF;

    IF NEW.state = 'completed' AND NEW.completed_at IS NULL THEN
        NEW.completed_at := now();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER workflow_state_guard
BEFORE UPDATE ON ingestion_workflows
FOR EACH ROW
EXECUTE FUNCTION validate_workflow_state();

CREATE OR REPLACE FUNCTION validate_document_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.document IS DISTINCT FROM OLD.document THEN
        NEW.version := OLD.version + 1;
        NEW.updated_at := now();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER document_version_guard
BEFORE UPDATE ON product_documents
FOR EACH ROW
EXECUTE FUNCTION validate_document_version();

INSERT INTO repositories (repository_name)
VALUES
    ('distributed-catalog'),
    ('telemetry-platform');

INSERT INTO architecture_decisions (
    repository_id,
    workload_name,
    selected_model,
    rationale
)
SELECT
    repository_id,
    'user sessions',
    'key-value',
    'Direct lookup by stable key with low-latency access'
FROM repositories
WHERE repository_name = 'distributed-catalog';

INSERT INTO architecture_decisions (
    repository_id,
    workload_name,
    selected_model,
    rationale
)
SELECT
    repository_id,
    'product catalog',
    'document',
    'Flexible attributes and nested product metadata'
FROM repositories
WHERE repository_name = 'distributed-catalog';

INSERT INTO architecture_decisions (
    repository_id,
    workload_name,
    selected_model,
    rationale
)
SELECT
    repository_id,
    'device telemetry',
    'wide-column',
    'Partition-oriented sparse time-series measurements'
FROM repositories
WHERE repository_name = 'telemetry-platform';

INSERT INTO architecture_decisions (
    repository_id,
    workload_name,
    selected_model,
    rationale
)
SELECT
    repository_id,
    'service dependencies',
    'graph',
    'Relationship traversal between services and data stores'
FROM repositories
WHERE repository_name = 'telemetry-platform';

INSERT INTO kv_entries (key, value, expires_at)
VALUES
(
    'session:user-1001',
    '{"user_id":"user-1001","role":"analyst"}',
    now() + interval '1 hour'
),
(
    'counter:catalog-views',
    '1250',
    NULL
);

INSERT INTO product_documents (
    document_id,
    document
)
VALUES
(
    'p100',
    '{
        "name": "Edge Gateway",
        "category": "networking",
        "price": 149.50,
        "tags": ["iot", "gateway", "edge"],
        "inventory": {"available": 42},
        "attributes": {
            "region": "asia-south",
            "active": true
        }
    }'::JSONB
),
(
    'p200',
    '{
        "name": "Graph Sensor",
        "category": "telemetry",
        "price": 89.00,
        "tags": ["sensor", "graph"],
        "inventory": {"available": 18},
        "attributes": {
            "region": "asia-south",
            "active": true
        }
    }'::JSONB
);

INSERT INTO wide_column_cells (
    row_key,
    column_family,
    column_name,
    numeric_value,
    observed_at
)
VALUES
(
    'device-001',
    'telemetry',
    '2026-10-31T12:00:00Z',
    44.1,
    '2026-10-31T12:00:00Z'
),
(
    'device-001',
    'telemetry',
    '2026-10-31T12:05:00Z',
    45.2,
    '2026-10-31T12:05:00Z'
),
(
    'device-002',
    'telemetry',
    '2026-10-31T12:00:00Z',
    38.5,
    '2026-10-31T12:00:00Z'
);

INSERT INTO graph_nodes (node_id, node_type, properties)
VALUES
('api', 'service', '{"team":"platform"}'),
('orders', 'service', '{"team":"commerce"}'),
('inventory', 'service', '{"team":"supply"}'),
('payments', 'service', '{"team":"finance"}'),
('inventory-db', 'database', '{"engine":"wide-column"}');

INSERT INTO graph_edges (
    source_node,
    relation,
    target_node
)
VALUES
('api', 'calls', 'orders'),
('orders', 'calls', 'inventory'),
('orders', 'calls', 'payments'),
('inventory', 'reads', 'inventory-db');

INSERT INTO ingestion_workflows (
    workload_name,
    model,
    state
)
VALUES
('product catalog ingestion', 'document', 'created'),
('device telemetry ingestion', 'wide-column', 'created'),
('dependency indexing', 'graph', 'created');

-- Transactional update: product metadata and its version change together.
BEGIN;

UPDATE product_documents
SET document = jsonb_set(
    document,
    '{attributes,firmware_version}',
    '"2.1"'::JSONB,
    true
)
WHERE document_id = 'p100';

COMMIT;

-- Retrieval: key-value entries that have not expired.
SELECT
    key,
    value,
    expires_at
FROM kv_entries
WHERE expires_at IS NULL
   OR expires_at > now()
ORDER BY key;

-- Document filtering using nested JSON fields.
SELECT
    document_id,
    document->>'name' AS product_name,
    (document->>'price')::NUMERIC AS price
FROM product_documents
WHERE status = 'active'
  AND (document->>'price')::NUMERIC >= 100
ORDER BY price DESC;

-- Document validation query.
SELECT
    document_id,
    document->>'name' AS product_name,
    CASE
        WHEN jsonb_typeof(document->'tags') = 'array'
        THEN 'valid'
        ELSE 'invalid'
    END AS tag_structure
FROM product_documents;

-- Wide-column aggregation.
SELECT
    row_key,
    COUNT(*) AS measurement_count,
    ROUND(AVG(numeric_value)::NUMERIC, 2) AS average_value,
    MAX(observed_at) AS latest_observation
FROM wide_column_cells
WHERE column_family = 'telemetry'
GROUP BY row_key
ORDER BY row_key;

-- Graph relationship retrieval.
SELECT
    source_node,
    relation,
    target_node
FROM graph_edges
WHERE source_node = 'orders'
ORDER BY relation, target_node;

-- Recursive graph traversal from the API service.
WITH RECURSIVE dependency_path AS (
    SELECT
        source_node AS node_id,
        ARRAY[source_node] AS path,
        0 AS depth
    FROM graph_edges
    WHERE source_node = 'api'

    UNION ALL

    SELECT
        edge.target_node,
        dependency_path.path || edge.target_node,
        dependency_path.depth + 1
    FROM dependency_path
    JOIN graph_edges edge
      ON edge.source_node = dependency_path.node_id
    WHERE dependency_path.depth < 10
      AND NOT edge.target_node = ANY(dependency_path.path)
)
SELECT
    path,
    depth
FROM dependency_path
ORDER BY depth, path;

-- Architecture evaluation report.
SELECT
    selected_model,
    COUNT(*) AS workload_count,
    STRING_AGG(workload_name, ', ' ORDER BY workload_name) AS workloads
FROM architecture_decisions
GROUP BY selected_model
ORDER BY selected_model;

-- Workflow state report.
SELECT
    workload_name,
    model,
    state,
    started_at,
    completed_at,
    failure_reason
FROM ingestion_workflows
ORDER BY workflow_id;

-- Eligibility-style evaluation for a flexible document workload.
WITH document_quality AS (
    SELECT
        document_id,
        document ? 'name' AS has_name,
        document ? 'category' AS has_category,
        jsonb_typeof(document->'tags') = 'array' AS valid_tags,
        jsonb_typeof(document->'price') = 'number'
            AND (document->>'price')::NUMERIC >= 0 AS valid_price
    FROM product_documents
)
SELECT
    document_id,
    has_name,
    has_category,
    valid_tags,
    valid_price,
    (
        has_name
        AND has_category
        AND valid_tags
        AND valid_price
    ) AS eligible
FROM document_quality
ORDER BY document_id;

-- Demonstrate a failed transition without changing the committed state.
DO $$
DECLARE
    workflow_id_value BIGINT;
BEGIN
    SELECT workflow_id
    INTO workflow_id_value
    FROM ingestion_workflows
    WHERE workload_name = 'product catalog ingestion';

    UPDATE ingestion_workflows
    SET state = 'active'
    WHERE workflow_id = workflow_id_value;

    UPDATE ingestion_workflows
    SET state = 'completed'
    WHERE workflow_id = workflow_id_value;

    BEGIN
        UPDATE ingestion_workflows
        SET state = 'active'
        WHERE workflow_id = workflow_id_value;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE
                'Expected invalid workflow transition rejected: %',
                SQLERRM;
    END;
END;
$$;
