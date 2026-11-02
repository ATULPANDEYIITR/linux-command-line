DROP SCHEMA IF EXISTS cache_lab CASCADE;

CREATE SCHEMA cache_lab;

SET search_path TO cache_lab;

CREATE TYPE cache_backend AS ENUM (
    'local',
    'distributed'
);

CREATE TYPE cache_entry_state AS ENUM (
    'fresh',
    'stale',
    'evicted',
    'invalidated'
);

CREATE TYPE invalidation_reason AS ENUM (
    'ttl_expiration',
    'data_mutation',
    'explicit_purge',
    'tag_purge',
    'policy_change'
);

CREATE TYPE cache_event_type AS ENUM (
    'hit',
    'miss',
    'set',
    'stale',
    'eviction',
    'invalidation'
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(repository_name)) >= 2)
);

CREATE TABLE cache_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    policy_name TEXT NOT NULL UNIQUE,
    backend cache_backend NOT NULL,
    max_entries INTEGER NOT NULL,
    default_ttl_seconds INTEGER NOT NULL,
    stale_while_revalidate_seconds INTEGER NOT NULL DEFAULT 0,
    max_value_bytes INTEGER NOT NULL DEFAULT 1048576,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (max_entries > 0),
    CHECK (default_ttl_seconds > 0),
    CHECK (stale_while_revalidate_seconds >= 0),
    CHECK (max_value_bytes > 0)
);

CREATE TABLE products (
    product_id BIGSERIAL PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    inventory INTEGER NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(sku)) >= 2),
    CHECK (length(trim(product_name)) >= 2),
    CHECK (price >= 0),
    CHECK (inventory >= 0),
    CHECK (version > 0)
);

CREATE TABLE cache_namespaces (
    namespace_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    policy_id BIGINT NOT NULL
        REFERENCES cache_policies(policy_id),
    namespace_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, namespace_name),
    CHECK (length(trim(namespace_name)) >= 2)
);

CREATE TABLE cache_entries (
    cache_entry_id BIGSERIAL PRIMARY KEY,
    namespace_id BIGINT NOT NULL
        REFERENCES cache_namespaces(namespace_id)
        ON DELETE CASCADE,
    cache_key TEXT NOT NULL,
    value_json JSONB NOT NULL,
    version BIGINT NOT NULL,
    state cache_entry_state NOT NULL DEFAULT 'fresh',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    stale_until TIMESTAMPTZ,
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    access_count BIGINT NOT NULL DEFAULT 0,
    byte_size INTEGER NOT NULL DEFAULT 0,
    UNIQUE (namespace_id, cache_key),
    CHECK (length(trim(cache_key)) > 0),
    CHECK (version > 0),
    CHECK (byte_size >= 0),
    CHECK (access_count >= 0),
    CHECK (stale_until IS NULL OR stale_until >= expires_at)
);

CREATE TABLE cache_tags (
    cache_entry_id BIGINT NOT NULL
        REFERENCES cache_entries(cache_entry_id)
        ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (cache_entry_id, tag),
    CHECK (length(trim(tag)) > 0)
);

CREATE TABLE cache_events (
    event_id BIGSERIAL PRIMARY KEY,
    cache_entry_id BIGINT
        REFERENCES cache_entries(cache_entry_id)
        ON DELETE SET NULL,
    namespace_id BIGINT
        REFERENCES cache_namespaces(namespace_id)
        ON DELETE CASCADE,
    cache_key TEXT NOT NULL,
    event_type cache_event_type NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE invalidation_log (
    invalidation_id BIGSERIAL PRIMARY KEY,
    namespace_id BIGINT NOT NULL
        REFERENCES cache_namespaces(namespace_id)
        ON DELETE CASCADE,
    cache_key TEXT NOT NULL,
    reason invalidation_reason NOT NULL,
    invalidated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cache_entries_expiration
    ON cache_entries (expires_at);

CREATE INDEX idx_cache_entries_last_accessed
    ON cache_entries (namespace_id, last_accessed_at);

CREATE INDEX idx_cache_entries_state
    ON cache_entries (namespace_id, state);

CREATE INDEX idx_cache_tags_tag
    ON cache_tags (tag);

CREATE INDEX idx_cache_events_namespace_time
    ON cache_events (namespace_id, event_time DESC);

CREATE INDEX idx_products_updated_at
    ON products (updated_at);

CREATE OR REPLACE FUNCTION set_product_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    NEW.version := OLD.version + 1;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_product_version
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION set_product_updated_at();

CREATE OR REPLACE FUNCTION calculate_json_size()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.byte_size := pg_column_size(NEW.value_json);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cache_entry_size
BEFORE INSERT OR UPDATE OF value_json ON cache_entries
FOR EACH ROW
EXECUTE FUNCTION calculate_json_size();

CREATE OR REPLACE FUNCTION log_cache_set()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO cache_events (
        cache_entry_id,
        namespace_id,
        cache_key,
        event_type,
        details
    )
    VALUES (
        NEW.cache_entry_id,
        NEW.namespace_id,
        NEW.cache_key,
        'set',
        jsonb_build_object(
            'version', NEW.version,
            'expires_at', NEW.expires_at
        )
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cache_set_event
AFTER INSERT OR UPDATE ON cache_entries
FOR EACH ROW
EXECUTE FUNCTION log_cache_set();

CREATE OR REPLACE FUNCTION cache_product_json(p_product_id BIGINT)
RETURNS JSONB
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_build_object(
        'product_id', product_id,
        'sku', sku,
        'product_name', product_name,
        'price', price,
        'inventory', inventory,
        'version', version,
        'updated_at', updated_at
    )
    FROM products
    WHERE product_id = p_product_id;
$$;

CREATE OR REPLACE FUNCTION put_cache_entry(
    p_namespace_id BIGINT,
    p_cache_key TEXT,
    p_value JSONB,
    p_version BIGINT,
    p_ttl_seconds INTEGER,
    p_stale_seconds INTEGER DEFAULT 0
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_entry_id BIGINT;
    v_policy_max_bytes INTEGER;
    v_size INTEGER;
BEGIN
    IF p_namespace_id IS NULL
       OR p_cache_key IS NULL
       OR length(trim(p_cache_key)) = 0 THEN
        RAISE EXCEPTION 'namespace and non-empty cache key are required';
    END IF;

    IF p_ttl_seconds <= 0 THEN
        RAISE EXCEPTION 'ttl must be positive';
    END IF;

    IF p_stale_seconds < 0 THEN
        RAISE EXCEPTION 'stale window cannot be negative';
    END IF;

    SELECT p.max_value_bytes
    INTO v_policy_max_bytes
    FROM cache_namespaces n
    JOIN cache_policies p
      ON p.policy_id = n.policy_id
    WHERE n.namespace_id = p_namespace_id
      AND p.enabled;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'cache namespace is missing or disabled';
    END IF;

    v_size := pg_column_size(p_value);

    IF v_size > v_policy_max_bytes THEN
        RAISE EXCEPTION
            'cache value exceeds configured size limit: % > % bytes',
            v_size,
            v_policy_max_bytes;
    END IF;

    INSERT INTO cache_entries (
        namespace_id,
        cache_key,
        value_json,
        version,
        state,
        expires_at,
        stale_until,
        last_accessed_at,
        access_count
    )
    VALUES (
        p_namespace_id,
        p_cache_key,
        p_value,
        p_version,
        'fresh',
        now() + make_interval(secs => p_ttl_seconds),
        CASE
            WHEN p_stale_seconds > 0
            THEN now()
                + make_interval(
                    secs => p_ttl_seconds + p_stale_seconds
                )
            ELSE NULL
        END,
        now(),
        0
    )
    ON CONFLICT (namespace_id, cache_key)
    DO UPDATE SET
        value_json = EXCLUDED.value_json,
        version = EXCLUDED.version,
        state = 'fresh',
        created_at = now(),
        expires_at = EXCLUDED.expires_at,
        stale_until = EXCLUDED.stale_until,
        last_accessed_at = now()
    RETURNING cache_entry_id
    INTO v_entry_id;

    RETURN v_entry_id;
END;
$$;

CREATE OR REPLACE FUNCTION read_cache_entry(
    p_namespace_id BIGINT,
    p_cache_key TEXT
)
RETURNS TABLE (
    cache_entry_id BIGINT,
    value_json JSONB,
    version BIGINT,
    state cache_entry_state
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE cache_entries
    SET
        state = CASE
            WHEN now() >= expires_at
                 AND stale_until IS NOT NULL
                 AND now() < stale_until
            THEN 'stale'
            WHEN now() >= expires_at
            THEN 'stale'
            ELSE 'fresh'
        END,
        last_accessed_at = now(),
        access_count = access_count + 1
    WHERE namespace_id = p_namespace_id
      AND cache_key = p_cache_key;

    RETURN QUERY
    SELECT
        e.cache_entry_id,
        e.value_json,
        e.version,
        e.state
    FROM cache_entries e
    WHERE e.namespace_id = p_namespace_id
      AND e.cache_key = p_cache_key
      AND (
          now() < e.expires_at
          OR (
              e.stale_until IS NOT NULL
              AND now() < e.stale_until
          )
      );
END;
$$;

CREATE OR REPLACE FUNCTION invalidate_cache_key(
    p_namespace_id BIGINT,
    p_cache_key TEXT,
    p_reason invalidation_reason
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE cache_entries
    SET state = 'invalidated'
    WHERE namespace_id = p_namespace_id
      AND cache_key = p_cache_key
      AND state <> 'invalidated';

    GET DIAGNOSTICS v_updated = ROW_COUNT;

    INSERT INTO invalidation_log (
        namespace_id,
        cache_key,
        reason
    )
    VALUES (
        p_namespace_id,
        p_cache_key,
        p_reason
    );

    IF v_updated > 0 THEN
        INSERT INTO cache_events (
            namespace_id,
            cache_key,
            event_type,
            details
        )
        VALUES (
            p_namespace_id,
            p_cache_key,
            'invalidation',
            jsonb_build_object(
                'reason', p_reason::text
            )
        );
    END IF;

    RETURN v_updated > 0;
END;
$$;

CREATE OR REPLACE FUNCTION invalidate_by_tag(
    p_namespace_id BIGINT,
    p_tag TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    WITH affected AS (
        UPDATE cache_entries e
        SET state = 'invalidated'
        FROM cache_tags t
        WHERE t.cache_entry_id = e.cache_entry_id
          AND e.namespace_id = p_namespace_id
          AND t.tag = p_tag
          AND e.state <> 'invalidated'
        RETURNING e.cache_entry_id, e.cache_key
    ),
    logged AS (
        INSERT INTO invalidation_log (
            namespace_id,
            cache_key,
            reason
        )
        SELECT
            p_namespace_id,
            cache_key,
            'tag_purge'
        FROM affected
        RETURNING 1
    )
    SELECT count(*)
    INTO v_count
    FROM logged;

    RETURN v_count;
END;
$$;

CREATE OR REPLACE FUNCTION evict_lru(
    p_namespace_id BIGINT,
    p_limit INTEGER
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    IF p_limit <= 0 THEN
        RETURN 0;
    END IF;

    WITH victims AS (
        SELECT cache_entry_id, cache_key
        FROM cache_entries
        WHERE namespace_id = p_namespace_id
          AND state IN ('fresh', 'stale')
        ORDER BY last_accessed_at ASC
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    ),
    marked AS (
        UPDATE cache_entries e
        SET state = 'evicted'
        FROM victims v
        WHERE e.cache_entry_id = v.cache_entry_id
        RETURNING e.cache_entry_id, e.cache_key
    )
    INSERT INTO cache_events (
        cache_entry_id,
        namespace_id,
        cache_key,
        event_type,
        details
    )
    SELECT
        cache_entry_id,
        p_namespace_id,
        cache_key,
        'eviction',
        jsonb_build_object('policy', 'LRU')
    FROM marked;

    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN v_count;
END;
$$;

INSERT INTO repositories (repository_name)
VALUES ('inventory-platform');

INSERT INTO cache_policies (
    policy_name,
    backend,
    max_entries,
    default_ttl_seconds,
    stale_while_revalidate_seconds,
    max_value_bytes
)
VALUES
(
    'product-local-l1',
    'local',
    1000,
    30,
    10,
    262144
),
(
    'product-distributed-l2',
    'distributed',
    10000,
    300,
    60,
    1048576
);

INSERT INTO products (
    sku,
    product_name,
    price,
    inventory
)
VALUES
('EDGE-001', 'Edge Router', 249.99, 18),
('GATE-002', 'Secure Gateway', 499.00, 7),
('TEL-003', 'Telemetry Node', 129.50, 31);

INSERT INTO cache_namespaces (
    repository_id,
    policy_id,
    namespace_name
)
SELECT
    r.repository_id,
    p.policy_id,
    x.namespace_name
FROM repositories r
CROSS JOIN (
    VALUES
        ('product-l1', 'product-local-l1'),
        ('product-l2', 'product-distributed-l2')
) AS x(namespace_name, policy_name)
JOIN cache_policies p
  ON p.policy_name = x.policy_name
WHERE r.repository_name = 'inventory-platform';

INSERT INTO cache_entries (
    namespace_id,
    cache_key,
    value_json,
    version,
    state,
    expires_at,
    stale_until,
    last_accessed_at,
    access_count
)
SELECT
    n.namespace_id,
    'product:' || p.product_id,
    cache_product_json(p.product_id),
    p.version,
    'fresh',
    now() + interval '30 seconds',
    now() + interval '40 seconds',
    now(),
    0
FROM cache_namespaces n
JOIN products p
  ON p.product_id IS NOT NULL
WHERE n.namespace_name = 'product-l1';

INSERT INTO cache_entries (
    namespace_id,
    cache_key,
    value_json,
    version,
    state,
    expires_at,
    stale_until
)
SELECT
    n.namespace_id,
    'product:' || p.product_id,
    cache_product_json(p.product_id),
    p.version,
    'fresh',
    now() + interval '5 minutes',
    now() + interval '6 minutes'
FROM cache_namespaces n
JOIN products p
  ON p.product_id IS NOT NULL
WHERE n.namespace_name = 'product-l2';

INSERT INTO cache_tags (cache_entry_id, tag)
SELECT cache_entry_id, 'product'
FROM cache_entries;

INSERT INTO cache_tags (cache_entry_id, tag)
SELECT cache_entry_id, cache_key
FROM cache_entries;

-- Retrieval: only fresh values are accepted as normal cache hits.
SELECT
    n.namespace_name,
    e.cache_key,
    e.version,
    e.state,
    e.value_json
FROM cache_entries e
JOIN cache_namespaces n
  ON n.namespace_id = e.namespace_id
WHERE e.state = 'fresh'
ORDER BY n.namespace_name, e.cache_key;

-- Validation: identify entries whose cached version no longer matches
-- the authoritative product version.
SELECT
    e.cache_key,
    e.version AS cached_version,
    p.version AS source_version,
    CASE
        WHEN e.version = p.version THEN 'valid'
        ELSE 'stale_version'
    END AS validation_result
FROM cache_entries e
JOIN products p
  ON ('product:' || p.product_id) = e.cache_key
WHERE e.state <> 'invalidated';

-- Aggregation: operational cache metrics.
SELECT
    n.namespace_name,
    count(*) AS entries,
    count(*) FILTER (WHERE e.state = 'fresh') AS fresh_entries,
    count(*) FILTER (WHERE e.state = 'stale') AS stale_entries,
    avg(e.access_count) AS average_access_count,
    sum(e.byte_size) AS total_cached_bytes
FROM cache_entries e
JOIN cache_namespaces n
  ON n.namespace_id = e.namespace_id
GROUP BY n.namespace_name
ORDER BY n.namespace_name;

-- Evaluation: calculate whether a cache entry is eligible for serving.
SELECT
    e.cache_key,
    e.state,
    e.expires_at,
    e.stale_until,
    CASE
        WHEN e.state = 'fresh'
             AND now() < e.expires_at
        THEN 'serve_fresh'
        WHEN e.state = 'stale'
             AND e.stale_until IS NOT NULL
             AND now() < e.stale_until
        THEN 'serve_stale_refresh'
        ELSE 'do_not_serve'
    END AS eligibility
FROM cache_entries e
ORDER BY e.cache_key;

-- Transactional mutation: change authoritative state and invalidate the
-- corresponding distributed cache entry in the same transaction.
BEGIN;

UPDATE products
SET price = 279.99
WHERE sku = 'EDGE-001';

SELECT invalidate_cache_key(
    (
        SELECT namespace_id
        FROM cache_namespaces
        WHERE namespace_name = 'product-l2'
    ),
    'product:' || (
        SELECT product_id
        FROM products
        WHERE sku = 'EDGE-001'
    ),
    'data_mutation'
);

COMMIT;

-- Workflow state after mutation.
SELECT
    n.namespace_name,
    e.cache_key,
    e.state,
    e.version,
    e.created_at,
    e.expires_at
FROM cache_entries e
JOIN cache_namespaces n
  ON n.namespace_id = e.namespace_id
WHERE e.cache_key = (
    'product:' || (
        SELECT product_id
        FROM products
        WHERE sku = 'EDGE-001'
    )
)
ORDER BY n.namespace_name;

-- Failure case: negative price is rejected by the database constraint.
DO $$
BEGIN
    BEGIN
        UPDATE products
        SET price = -1
        WHERE sku = 'GATE-002';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'expected constraint failure: negative price rejected';
    END;
END;
$$;

-- Explicit tag-based invalidation.
SELECT invalidate_by_tag(
    (
        SELECT namespace_id
        FROM cache_namespaces
        WHERE namespace_name = 'product-l1'
    ),
    'product'
);

-- Demonstrate LRU eviction under controlled pressure.
SELECT evict_lru(
    (
        SELECT namespace_id
        FROM cache_namespaces
        WHERE namespace_name = 'product-l2'
    ),
    1
);

-- Final reporting view.
CREATE OR REPLACE VIEW cache_operational_report AS
SELECT
    n.namespace_name,
    p.policy_name,
    p.backend,
    p.max_entries,
    p.default_ttl_seconds,
    count(e.cache_entry_id) AS stored_entries,
    count(e.cache_entry_id)
        FILTER (WHERE e.state = 'fresh') AS fresh_entries,
    count(e.cache_entry_id)
        FILTER (WHERE e.state = 'stale') AS stale_entries,
    count(e.cache_entry_id)
        FILTER (WHERE e.state = 'invalidated') AS invalidated_entries,
    coalesce(sum(e.byte_size), 0) AS total_bytes,
    coalesce(sum(e.access_count), 0) AS total_accesses
FROM cache_namespaces n
JOIN cache_policies p
  ON p.policy_id = n.policy_id
LEFT JOIN cache_entries e
  ON e.namespace_id = n.namespace_id
GROUP BY
    n.namespace_name,
    p.policy_name,
    p.backend,
    p.max_entries,
    p.default_ttl_seconds;

SELECT *
FROM cache_operational_report
ORDER BY namespace_name;

-- Event audit: useful for diagnosing miss storms, evictions, and invalidation
-- behavior without storing sensitive payloads in the event table.
SELECT
    event_type,
    count(*) AS event_count
FROM cache_events
GROUP BY event_type
ORDER BY event_type;

-- Invalidation audit.
SELECT
    reason,
    count(*) AS invalidation_count
FROM invalidation_log
GROUP BY reason
ORDER BY reason;
