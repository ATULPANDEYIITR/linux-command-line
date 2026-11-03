-- ============================================================================
-- DATA WAREHOUSING: POSTGRESQL ETL AND ANALYTICAL MODEL
-- ============================================================================
--
-- Demonstrates:
--   1. Operational source staging and change-batch tracking.
--   2. A dimensional star schema.
--   3. SCD Type 2 customer history.
--   4. ETL validation, quarantine and idempotent fact loading.
--   5. Transactional workflow processing.
--   6. OLAP reporting and batch eligibility evaluation.
--
-- Execute with PostgreSQL 15 or later.
-- This script creates an isolated schema named dw_demo.
-- It does not drop existing schemas or tables.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS dw_demo;

-- ============================================================================
-- 1. ETL CONTROL AND SOURCE STAGING
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_demo.etl_batch (
    batch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_code TEXT NOT NULL UNIQUE,
    source_system TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')),
    extracted_count INTEGER NOT NULL DEFAULT 0
        CHECK (extracted_count >= 0),
    loaded_count INTEGER NOT NULL DEFAULT 0
        CHECK (loaded_count >= 0),
    rejected_count INTEGER NOT NULL DEFAULT 0
        CHECK (rejected_count >= 0),
    skipped_count INTEGER NOT NULL DEFAULT 0
        CHECK (skipped_count >= 0),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        completed_at IS NULL
        OR started_at IS NULL
        OR completed_at >= started_at
    )
);

CREATE TABLE IF NOT EXISTS dw_demo.stg_sales (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id BIGINT NOT NULL
        REFERENCES dw_demo.etl_batch(batch_id),
    source_system TEXT NOT NULL,
    source_sale_id TEXT NOT NULL,
    customer_bk TEXT NOT NULL,
    product_bk TEXT NOT NULL,
    sale_date DATE NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price_cents BIGINT NOT NULL,
    sale_status TEXT NOT NULL,
    source_changed_at TIMESTAMPTZ NOT NULL,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (batch_id, source_system, source_sale_id)
);

CREATE INDEX IF NOT EXISTS idx_stg_sales_batch
    ON dw_demo.stg_sales(batch_id, staging_id);

CREATE INDEX IF NOT EXISTS idx_stg_sales_business_key
    ON dw_demo.stg_sales(source_system, source_sale_id);

CREATE TABLE IF NOT EXISTS dw_demo.etl_reject (
    reject_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    staging_id BIGINT NOT NULL UNIQUE
        REFERENCES dw_demo.stg_sales(staging_id),
    batch_id BIGINT NOT NULL
        REFERENCES dw_demo.etl_batch(batch_id),
    reason_code TEXT NOT NULL,
    reason_detail TEXT NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(reason_code)) > 0),
    CHECK (length(trim(reason_detail)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_etl_reject_batch
    ON dw_demo.etl_reject(batch_id, rejected_at);

-- ============================================================================
-- 2. DIMENSION TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_demo.dim_customer (
    customer_sk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_bk TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    region TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (valid_from < valid_to),
    UNIQUE (customer_bk, valid_from)
);

-- The business key may have many historical rows but only one current row.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_customer_current
    ON dw_demo.dim_customer(customer_bk)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_dim_customer_region
    ON dw_demo.dim_customer(region);

CREATE TABLE IF NOT EXISTS dw_demo.dim_product (
    product_sk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_bk TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_product_category
    ON dw_demo.dim_product(category, product_name);

CREATE TABLE IF NOT EXISTS dw_demo.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    calendar_year INTEGER NOT NULL,
    calendar_quarter INTEGER NOT NULL
        CHECK (calendar_quarter BETWEEN 1 AND 4),
    calendar_month INTEGER NOT NULL
        CHECK (calendar_month BETWEEN 1 AND 12),
    day_of_month INTEGER NOT NULL
        CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week INTEGER NOT NULL
        CHECK (day_of_week BETWEEN 1 AND 7)
);

-- ============================================================================
-- 3. FACT TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_demo.fact_sales (
    sales_sk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_sale_id TEXT NOT NULL,
    source_change_at TIMESTAMPTZ NOT NULL,
    customer_sk BIGINT NOT NULL
        REFERENCES dw_demo.dim_customer(customer_sk),
    product_sk BIGINT NOT NULL
        REFERENCES dw_demo.dim_product(product_sk),
    date_key INTEGER NOT NULL
        REFERENCES dw_demo.dim_date(date_key),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents BIGINT NOT NULL CHECK (unit_price_cents >= 0),
    gross_cents BIGINT GENERATED ALWAYS AS
        (quantity::BIGINT * unit_price_cents) STORED,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, source_sale_id)
);

-- Fact-table indexes support common star-schema filtering and joins.
CREATE INDEX IF NOT EXISTS idx_fact_sales_date
    ON dw_demo.fact_sales(date_key);

CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_date
    ON dw_demo.fact_sales(customer_sk, date_key);

CREATE INDEX IF NOT EXISTS idx_fact_sales_product_date
    ON dw_demo.fact_sales(product_sk, date_key);

-- ============================================================================
-- 4. BATCH PUBLICATION POLICY
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_demo.publication_policy (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name TEXT NOT NULL UNIQUE,
    maximum_reject_ratio NUMERIC(5, 4) NOT NULL
        CHECK (maximum_reject_ratio BETWEEN 0 AND 1),
    minimum_loaded_rows INTEGER NOT NULL DEFAULT 1
        CHECK (minimum_loaded_rows >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO dw_demo.publication_policy(
    policy_name,
    maximum_reject_ratio,
    minimum_loaded_rows,
    active
)
VALUES ('standard_sales_quality', 0.3000, 1, TRUE)
ON CONFLICT (policy_name) DO UPDATE SET
    maximum_reject_ratio = EXCLUDED.maximum_reject_ratio,
    minimum_loaded_rows = EXCLUDED.minimum_loaded_rows,
    active = EXCLUDED.active;

-- ============================================================================
-- 5. DIMENSION AND SAMPLE DATA
-- ============================================================================

INSERT INTO dw_demo.dim_customer(
    customer_bk, customer_name, region,
    valid_from, valid_to, is_current
)
VALUES
    (
        'C001', 'Asha Mehta', 'North',
        DATE '2025-01-01', DATE '2026-01-01', FALSE
    ),
    (
        'C001', 'Asha Mehta', 'East',
        DATE '2026-01-01', DATE '9999-12-31', TRUE
    ),
    (
        'C002', 'Rohan Singh', 'South',
        DATE '2025-01-01', DATE '9999-12-31', TRUE
    ),
    (
        'C003', 'Mira Das', 'West',
        DATE '2025-01-01', DATE '9999-12-31', TRUE
    )
ON CONFLICT (customer_bk, valid_from) DO UPDATE SET
    customer_name = EXCLUDED.customer_name,
    region = EXCLUDED.region,
    valid_to = EXCLUDED.valid_to,
    is_current = EXCLUDED.is_current;

INSERT INTO dw_demo.dim_product(
    product_bk, product_name, category, active
)
VALUES
    ('P100', 'Laptop', 'Electronics', TRUE),
    ('P200', 'Monitor', 'Electronics', TRUE),
    ('P300', 'Office Chair', 'Furniture', TRUE)
ON CONFLICT (product_bk) DO UPDATE SET
    product_name = EXCLUDED.product_name,
    category = EXCLUDED.category,
    active = EXCLUDED.active;

-- A date dimension is generated once and reused by every fact load.
INSERT INTO dw_demo.dim_date(
    date_key,
    full_date,
    calendar_year,
    calendar_quarter,
    calendar_month,
    day_of_month,
    day_of_week
)
SELECT
    TO_CHAR(d::DATE, 'YYYYMMDD')::INTEGER,
    d::DATE,
    EXTRACT(YEAR FROM d)::INTEGER,
    EXTRACT(QUARTER FROM d)::INTEGER,
    EXTRACT(MONTH FROM d)::INTEGER,
    EXTRACT(DAY FROM d)::INTEGER,
    EXTRACT(ISODOW FROM d)::INTEGER
FROM GENERATE_SERIES(
    DATE '2025-01-01',
    DATE '2027-12-31',
    INTERVAL '1 day'
) AS d
ON CONFLICT (date_key) DO NOTHING;

-- ============================================================================
-- 6. SAMPLE SOURCE BATCH
-- ============================================================================

DO $$
DECLARE
    v_batch_id BIGINT;
BEGIN
    INSERT INTO dw_demo.etl_batch(
        batch_code,
        source_system,
        status
    )
    VALUES (
        'RETAIL-2026-10-INITIAL',
        'RETAIL_OLTP',
        'PENDING'
    )
    ON CONFLICT (batch_code) DO NOTHING;

    SELECT batch_id
    INTO v_batch_id
    FROM dw_demo.etl_batch
    WHERE batch_code = 'RETAIL-2026-10-INITIAL';

    INSERT INTO dw_demo.stg_sales(
        batch_id,
        source_system,
        source_sale_id,
        customer_bk,
        product_bk,
        sale_date,
        quantity,
        unit_price_cents,
        sale_status,
        source_changed_at
    )
    VALUES
        (
            v_batch_id, 'RETAIL_OLTP', 'S1001',
            'C001', 'P100', DATE '2025-11-01',
            2, 75000, 'COMPLETED',
            TIMESTAMPTZ '2025-11-01 10:00:00+05:30'
        ),
        (
            v_batch_id, 'RETAIL_OLTP', 'S1002',
            'C001', 'P200', DATE '2026-02-14',
            1, 22000, 'COMPLETED',
            TIMESTAMPTZ '2026-02-14 11:00:00+05:30'
        ),
        (
            v_batch_id, 'RETAIL_OLTP', 'S1003',
            'C002', 'P100', DATE '2026-02-15',
            3, 75000, 'COMPLETED',
            TIMESTAMPTZ '2026-02-15 12:00:00+05:30'
        ),
        (
            v_batch_id, 'RETAIL_OLTP', 'S1004',
            'C003', 'P300', DATE '2026-02-16',
            2, 12000, 'COMPLETED',
            TIMESTAMPTZ '2026-02-16 13:00:00+05:30'
        ),
        (
            v_batch_id, 'RETAIL_OLTP', 'S1005',
            'C001', 'P200', DATE '2026-02-17',
            -1, 22000, 'COMPLETED',
            TIMESTAMPTZ '2026-02-17 14:00:00+05:30'
        ),
        (
            v_batch_id, 'RETAIL_OLTP', 'S1006',
            'C003', 'P999', DATE '2026-02-18',
            1, 15000, 'COMPLETED',
            TIMESTAMPTZ '2026-02-18 15:00:00+05:30'
        ),
        (
            v_batch_id, 'RETAIL_OLTP', 'S1007',
            'C002', 'P100', DATE '2026-02-19',
            1, 75000, 'CANCELLED',
            TIMESTAMPTZ '2026-02-19 16:00:00+05:30'
        )
    ON CONFLICT (batch_id, source_system, source_sale_id) DO NOTHING;
END;
$$;

-- ============================================================================
-- 7. BATCH STATE VALIDATION TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION dw_demo.validate_batch_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = NEW.status THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'PENDING' AND NEW.status = 'RUNNING' THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'RUNNING'
       AND NEW.status IN ('SUCCEEDED', 'FAILED') THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'Invalid ETL batch transition: % -> %',
        OLD.status,
        NEW.status;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_batch_transition
    ON dw_demo.etl_batch;

CREATE TRIGGER trg_validate_batch_transition
BEFORE UPDATE OF status
ON dw_demo.etl_batch
FOR EACH ROW
EXECUTE FUNCTION dw_demo.validate_batch_transition();

-- ============================================================================
-- 8. ETL BATCH PROCESSING PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE dw_demo.process_sales_batch(
    p_batch_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_batch_status TEXT;
    v_policy dw_demo.publication_policy%ROWTYPE;
    v_record RECORD;
    v_customer_sk BIGINT;
    v_product_sk BIGINT;
    v_date_key INTEGER;
    v_loaded INTEGER := 0;
    v_rejected INTEGER := 0;
    v_skipped INTEGER := 0;
    v_extracted INTEGER := 0;
    v_reason_code TEXT;
    v_reason_detail TEXT;
    v_rows INTEGER;
    v_reject_ratio NUMERIC;
BEGIN
    SELECT status
    INTO v_batch_status
    FROM dw_demo.etl_batch
    WHERE batch_id = p_batch_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown ETL batch ID: %', p_batch_id;
    END IF;

    IF v_batch_status <> 'PENDING' THEN
        RAISE EXCEPTION
            'Batch % is not eligible for processing; state is %',
            p_batch_id,
            v_batch_status;
    END IF;

    SELECT *
    INTO v_policy
    FROM dw_demo.publication_policy
    WHERE policy_name = 'standard_sales_quality'
      AND active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No active publication policy is configured';
    END IF;

    UPDATE dw_demo.etl_batch
    SET status = 'RUNNING',
        started_at = CURRENT_TIMESTAMP
    WHERE batch_id = p_batch_id;

    SELECT COUNT(*)::INTEGER
    INTO v_extracted
    FROM dw_demo.stg_sales
    WHERE batch_id = p_batch_id;

    FOR v_record IN
        SELECT *
        FROM dw_demo.stg_sales
        WHERE batch_id = p_batch_id
        ORDER BY staging_id
    LOOP
        v_reason_code := NULL;
        v_reason_detail := NULL;

        -- Incomplete business transactions are not loaded as sales facts.
        IF v_record.sale_status <> 'COMPLETED' THEN
            v_skipped := v_skipped + 1;
            CONTINUE;
        END IF;

        IF v_record.quantity <= 0 THEN
            v_reason_code := 'INVALID_QUANTITY';
            v_reason_detail := 'Quantity must be greater than zero';

        ELSIF v_record.unit_price_cents < 0 THEN
            v_reason_code := 'INVALID_PRICE';
            v_reason_detail := 'Unit price cannot be negative';

        ELSIF v_record.unit_price_cents > 0
          AND v_record.quantity::BIGINT >
              9223372036854775807 / v_record.unit_price_cents THEN
            v_reason_code := 'AMOUNT_OVERFLOW';
            v_reason_detail := 'Gross amount exceeds BIGINT range';
        END IF;

        IF v_reason_code IS NOT NULL THEN
            INSERT INTO dw_demo.etl_reject(
                staging_id,
                batch_id,
                reason_code,
                reason_detail
            )
            VALUES (
                v_record.staging_id,
                p_batch_id,
                v_reason_code,
                v_reason_detail
            )
            ON CONFLICT (staging_id) DO UPDATE SET
                reason_code = EXCLUDED.reason_code,
                reason_detail = EXCLUDED.reason_detail,
                rejected_at = CURRENT_TIMESTAMP;

            v_rejected := v_rejected + 1;
            CONTINUE;
        END IF;

        -- Resolve the correct SCD Type 2 customer version as of sale_date.
        SELECT customer_sk
        INTO v_customer_sk
        FROM dw_demo.dim_customer
        WHERE customer_bk = v_record.customer_bk
          AND valid_from <= v_record.sale_date
          AND v_record.sale_date < valid_to
        ORDER BY valid_from DESC
        LIMIT 1;

        IF v_customer_sk IS NULL THEN
            v_reason_code := 'UNKNOWN_CUSTOMER_VERSION';
            v_reason_detail :=
                'No customer dimension version covers the sale date';
        END IF;

        SELECT product_sk
        INTO v_product_sk
        FROM dw_demo.dim_product
        WHERE product_bk = v_record.product_bk
          AND active = TRUE;

        IF v_product_sk IS NULL AND v_reason_code IS NULL THEN
            v_reason_code := 'UNKNOWN_PRODUCT';
            v_reason_detail := 'Product does not exist or is inactive';
        END IF;

        SELECT TO_CHAR(v_record.sale_date, 'YYYYMMDD')::INTEGER
        INTO v_date_key;

        IF v_reason_code IS NULL
           AND NOT EXISTS (
               SELECT 1
               FROM dw_demo.dim_date
               WHERE date_key = v_date_key
                 AND full_date = v_record.sale_date
           ) THEN
            v_reason_code := 'UNKNOWN_DATE';
            v_reason_detail := 'Sale date is absent from date dimension';
        END IF;

        IF v_reason_code IS NOT NULL THEN
            INSERT INTO dw_demo.etl_reject(
                staging_id,
                batch_id,
                reason_code,
                reason_detail
            )
            VALUES (
                v_record.staging_id,
                p_batch_id,
                v_reason_code,
                v_reason_detail
            )
            ON CONFLICT (staging_id) DO UPDATE SET
                reason_code = EXCLUDED.reason_code,
                reason_detail = EXCLUDED.reason_detail,
                rejected_at = CURRENT_TIMESTAMP;

            v_rejected := v_rejected + 1;
            CONTINUE;
        END IF;

        -- The unique source key makes retries safe. A source event with a
        -- newer change timestamp can correct an earlier version of a fact.
        INSERT INTO dw_demo.fact_sales(
            source_system,
            source_sale_id,
            source_change_at,
            customer_sk,
            product_sk,
            date_key,
            quantity,
            unit_price_cents
        )
        VALUES (
            v_record.source_system,
            v_record.source_sale_id,
            v_record.source_changed_at,
            v_customer_sk,
            v_product_sk,
            v_date_key,
            v_record.quantity,
            v_record.unit_price_cents
        )
        ON CONFLICT (source_system, source_sale_id) DO UPDATE SET
            source_change_at = EXCLUDED.source_change_at,
            customer_sk = EXCLUDED.customer_sk,
            product_sk = EXCLUDED.product_sk,
            date_key = EXCLUDED.date_key,
            quantity = EXCLUDED.quantity,
            unit_price_cents = EXCLUDED.unit_price_cents
        WHERE EXCLUDED.source_change_at >
              dw_demo.fact_sales.source_change_at;

        GET DIAGNOSTICS v_rows = ROW_COUNT;

        IF v_rows = 1 THEN
            v_loaded := v_loaded + 1;
        ELSE
            v_skipped := v_skipped + 1;
        END IF;
    END LOOP;

    v_reject_ratio := CASE
        WHEN v_extracted = 0 THEN 0
        ELSE v_rejected::NUMERIC / v_extracted
    END;

    IF v_reject_ratio > v_policy.maximum_reject_ratio THEN
        RAISE EXCEPTION
            'Batch quality gate failed: reject ratio % exceeds limit %',
            v_reject_ratio,
            v_policy.maximum_reject_ratio;
    END IF;

    IF v_loaded < v_policy.minimum_loaded_rows THEN
        RAISE EXCEPTION
            'Batch does not meet minimum loaded row requirement';
    END IF;

    UPDATE dw_demo.etl_batch
    SET status = 'SUCCEEDED',
        extracted_count = v_extracted,
        loaded_count = v_loaded,
        rejected_count = v_rejected,
        skipped_count = v_skipped,
        completed_at = CURRENT_TIMESTAMP
    WHERE batch_id = p_batch_id;
END;
$$;

-- ============================================================================
-- 9. TRANSACTIONAL EXECUTION
-- ============================================================================

BEGIN;

CALL dw_demo.process_sales_batch(
    (
        SELECT batch_id
        FROM dw_demo.etl_batch
        WHERE batch_code = 'RETAIL-2026-10-INITIAL'
    )
);

COMMIT;

-- ============================================================================
-- 10. IDEMPOTENCY TEST BATCH
-- ============================================================================

DO $$
DECLARE
    v_batch_id BIGINT;
BEGIN
    INSERT INTO dw_demo.etl_batch(
        batch_code,
        source_system,
        status
    )
    VALUES (
        'RETAIL-2026-10-RETRY',
        'RETAIL_OLTP',
        'PENDING'
    )
    ON CONFLICT (batch_code) DO NOTHING;

    SELECT batch_id
    INTO v_batch_id
    FROM dw_demo.etl_batch
    WHERE batch_code = 'RETAIL-2026-10-RETRY';

    INSERT INTO dw_demo.stg_sales(
        batch_id,
        source_system,
        source_sale_id,
        customer_bk,
        product_bk,
        sale_date,
        quantity,
        unit_price_cents,
        sale_status,
        source_changed_at
    )
    VALUES (
        v_batch_id,
        'RETAIL_OLTP',
        'S1001',
        'C001',
        'P100',
        DATE '2025-11-01',
        2,
        75000,
        'COMPLETED',
        TIMESTAMPTZ '2025-11-01 10:00:00+05:30'
    )
    ON CONFLICT (batch_id, source_system, source_sale_id) DO NOTHING;
END;
$$;

BEGIN;

CALL dw_demo.process_sales_batch(
    (
        SELECT batch_id
        FROM dw_demo.etl_batch
        WHERE batch_code = 'RETAIL-2026-10-RETRY'
    )
);

COMMIT;

-- ============================================================================
-- 11. REPORTING VIEW
-- ============================================================================

CREATE OR REPLACE VIEW dw_demo.v_sales_enriched AS
SELECT
    f.sales_sk,
    f.source_system,
    f.source_sale_id,
    d.full_date,
    d.calendar_year,
    d.calendar_quarter,
    d.calendar_month,
    c.customer_bk,
    c.customer_name,
    c.region,
    p.product_bk,
    p.product_name,
    p.category,
    f.quantity,
    f.unit_price_cents,
    f.gross_cents
FROM dw_demo.fact_sales AS f
JOIN dw_demo.dim_customer AS c
    ON c.customer_sk = f.customer_sk
JOIN dw_demo.dim_product AS p
    ON p.product_sk = f.product_sk
JOIN dw_demo.dim_date AS d
    ON d.date_key = f.date_key;

CREATE OR REPLACE VIEW dw_demo.v_revenue_by_region_month AS
SELECT
    calendar_year,
    calendar_month,
    region,
    COUNT(*) AS transaction_count,
    SUM(quantity) AS units_sold,
    SUM(gross_cents) AS revenue_cents
FROM dw_demo.v_sales_enriched
GROUP BY
    calendar_year,
    calendar_month,
    region;

-- ============================================================================
-- 12. ELIGIBILITY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW dw_demo.v_batch_eligibility AS
SELECT
    b.batch_id,
    b.batch_code,
    b.status,
    b.extracted_count,
    b.loaded_count,
    b.rejected_count,
    b.skipped_count,
    COALESCE(
        b.rejected_count::NUMERIC /
        NULLIF(b.extracted_count, 0),
        0
    ) AS reject_ratio,
    p.maximum_reject_ratio,
    p.minimum_loaded_rows,
    (
        b.status = 'SUCCEEDED'
        AND b.loaded_count >= p.minimum_loaded_rows
        AND COALESCE(
            b.rejected_count::NUMERIC /
            NULLIF(b.extracted_count, 0),
            0
        ) <= p.maximum_reject_ratio
    ) AS is_eligible_for_publication
FROM dw_demo.etl_batch AS b
CROSS JOIN dw_demo.publication_policy AS p
WHERE p.active = TRUE;

-- ============================================================================
-- 13. RETRIEVAL AND VALIDATION QUERIES
-- ============================================================================

-- Operational staging records for a selected batch.
SELECT
    staging_id,
    source_sale_id,
    customer_bk,
    product_bk,
    sale_date,
    quantity,
    unit_price_cents,
    sale_status
FROM dw_demo.stg_sales
WHERE batch_id = (
    SELECT batch_id
    FROM dw_demo.etl_batch
    WHERE batch_code = 'RETAIL-2026-10-INITIAL'
)
ORDER BY staging_id;

-- Quality failures and their recorded reasons.
SELECT
    r.batch_id,
    s.source_sale_id,
    r.reason_code,
    r.reason_detail,
    r.rejected_at
FROM dw_demo.etl_reject AS r
JOIN dw_demo.stg_sales AS s
    ON s.staging_id = r.staging_id
ORDER BY r.reject_id;

-- Detect missing or overlapping customer validity intervals.
WITH ordered_versions AS (
    SELECT
        customer_bk,
        valid_from,
        valid_to,
        LAG(valid_to) OVER (
            PARTITION BY customer_bk
            ORDER BY valid_from
        ) AS previous_valid_to
    FROM dw_demo.dim_customer
)
SELECT
    customer_bk,
    valid_from,
    valid_to,
    previous_valid_to,
    CASE
        WHEN previous_valid_to IS NULL THEN 'FIRST_VERSION'
        WHEN valid_from < previous_valid_to THEN 'OVERLAP'
        WHEN valid_from > previous_valid_to THEN 'GAP'
        ELSE 'CONTIGUOUS'
    END AS timeline_status
FROM ordered_versions
ORDER BY customer_bk, valid_from;

-- ============================================================================
-- 14. OLAP AGGREGATION AND EVALUATION QUERIES
-- ============================================================================

-- Revenue by region and product.
SELECT
    region,
    product_name,
    SUM(quantity) AS units_sold,
    COUNT(*) AS transaction_count,
    SUM(gross_cents) AS revenue_cents
FROM dw_demo.v_sales_enriched
GROUP BY region, product_name
ORDER BY revenue_cents DESC;

-- Monthly analytical report using a CTE.
WITH monthly_sales AS (
    SELECT
        calendar_year,
        calendar_month,
        region,
        SUM(gross_cents) AS revenue_cents,
        SUM(quantity) AS units_sold
    FROM dw_demo.v_sales_enriched
    GROUP BY calendar_year, calendar_month, region
),
ranked_regions AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY calendar_year, calendar_month
            ORDER BY revenue_cents DESC
        ) AS regional_revenue_rank
    FROM monthly_sales
)
SELECT
    calendar_year,
    calendar_month,
    region,
    units_sold,
    revenue_cents,
    regional_revenue_rank
FROM ranked_regions
ORDER BY calendar_year, calendar_month, regional_revenue_rank;

-- Evaluate batch processing and publication eligibility.
SELECT *
FROM dw_demo.v_batch_eligibility
ORDER BY batch_id;

-- Operational-to-warehouse reconciliation by batch.
SELECT
    b.batch_code,
    b.extracted_count,
    b.loaded_count,
    b.rejected_count,
    b.skipped_count,
    COUNT(DISTINCT f.source_sale_id) AS matching_fact_count
FROM dw_demo.etl_batch AS b
LEFT JOIN dw_demo.stg_sales AS s
    ON s.batch_id = b.batch_id
LEFT JOIN dw_demo.fact_sales AS f
    ON f.source_system = s.source_system
   AND f.source_sale_id = s.source_sale_id
GROUP BY
    b.batch_id,
    b.batch_code,
    b.extracted_count,
    b.loaded_count,
    b.rejected_count,
    b.skipped_count
ORDER BY b.batch_id;

-- Retrieve the most recent successful load for each source system.
SELECT DISTINCT ON (source_system)
    source_system,
    batch_code,
    completed_at,
    loaded_count,
    rejected_count
FROM dw_demo.etl_batch
WHERE status = 'SUCCEEDED'
ORDER BY source_system, completed_at DESC;

-- ============================================================================
-- 15. POINT-LOOKUP AND AGGREGATE QUERY COMPARISON
-- ============================================================================

-- A selective fact lookup. In a production design, an operational database
-- would serve frequently changing transaction records.
SELECT
    source_sale_id,
    quantity,
    unit_price_cents,
    gross_cents
FROM dw_demo.fact_sales
WHERE source_system = 'RETAIL_OLTP'
  AND source_sale_id = 'S1001';

-- An analytical query reads and groups many facts across dimensions.
SELECT
    p.category,
    d.calendar_year,
    SUM(f.quantity) AS units,
    SUM(f.gross_cents) AS revenue_cents
FROM dw_demo.fact_sales AS f
JOIN dw_demo.dim_product AS p
    ON p.product_sk = f.product_sk
JOIN dw_demo.dim_date AS d
    ON d.date_key = f.date_key
GROUP BY p.category, d.calendar_year
ORDER BY d.calendar_year, p.category;

-- ============================================================================
-- END OF SCRIPT
-- ============================================================================
