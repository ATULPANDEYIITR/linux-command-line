DROP SCHEMA IF EXISTS serverless_demo CASCADE;
CREATE SCHEMA serverless_demo;
SET search_path TO serverless_demo;

CREATE TYPE function_runtime AS ENUM (
    'python',
    'javascript',
    'java',
    'cpp'
);

CREATE TYPE trigger_type AS ENUM (
    'http',
    'event',
    'schedule'
);

CREATE TYPE invocation_status AS ENUM (
    'success',
    'failure',
    'timeout'
);

CREATE TYPE event_status AS ENUM (
    'published',
    'processing',
    'processed',
    'failed'
);

CREATE TABLE serverless_functions (
    function_id BIGSERIAL PRIMARY KEY,
    function_name TEXT NOT NULL UNIQUE,
    runtime function_runtime NOT NULL,
    trigger trigger_type NOT NULL,
    memory_mb INTEGER NOT NULL DEFAULT 256,
    timeout_ms INTEGER NOT NULL DEFAULT 3000,
    minimum_instances INTEGER NOT NULL DEFAULT 0,
    maximum_instances INTEGER NOT NULL DEFAULT 10,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (memory_mb > 0),
    CHECK (timeout_ms > 0),
    CHECK (minimum_instances >= 0),
    CHECK (maximum_instances >= minimum_instances)
);

CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload JSONB NOT NULL,
    status event_status NOT NULL DEFAULT 'published',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ
);

CREATE TABLE function_subscriptions (
    function_id BIGINT NOT NULL
        REFERENCES serverless_functions(function_id)
        ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    PRIMARY KEY (function_id, event_type)
);

CREATE TABLE invocations (
    invocation_id BIGSERIAL PRIMARY KEY,
    function_id BIGINT NOT NULL
        REFERENCES serverless_functions(function_id),
    event_id UUID NOT NULL
        REFERENCES events(event_id),
    status invocation_status NOT NULL,
    duration_ms NUMERIC(12,3) NOT NULL,
    cold_start BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    invoked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (duration_ms >= 0),
    CHECK (
        status = 'success'
        OR error_message IS NOT NULL
    )
);

CREATE TABLE processed_events (
    function_id BIGINT NOT NULL
        REFERENCES serverless_functions(function_id)
        ON DELETE CASCADE,
    event_id UUID NOT NULL
        REFERENCES events(event_id)
        ON DELETE CASCADE,
    result JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (function_id, event_id)
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    owner_name TEXT NOT NULL
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, branch_name)
);

CREATE TABLE pull_requests (
    pull_request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    source_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    target_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    title TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open',
    draft BOOLEAN NOT NULL DEFAULT TRUE,
    mergeable BOOLEAN NOT NULL DEFAULT TRUE,
    approvals_stale BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    merged_at TIMESTAMPTZ,
    CHECK (source_branch_id <> target_branch_id),
    CHECK (state IN ('open', 'closed', 'merged'))
);

CREATE TABLE reviewers (
    reviewer_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE review_requests (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES reviewers(reviewer_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pull_request_id, reviewer_id)
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES reviewers(reviewer_id),
    review_state TEXT NOT NULL,
    body TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dismissed_at TIMESTAMPTZ,
    CHECK (
        review_state IN (
            'commented',
            'changes_requested',
            'approved',
            'dismissed'
        )
    )
);

CREATE TABLE review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES reviews(review_id)
        ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    comment_body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (line_number > 0)
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    commit_hash CHAR(40) NOT NULL UNIQUE,
    parent_hash CHAR(40),
    authored_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    state TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name),
    CHECK (state IN ('pending', 'passed', 'failed'))
);

CREATE TABLE branch_protection_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE
        REFERENCES branches(branch_id)
        ON DELETE CASCADE,
    required_approvals INTEGER NOT NULL DEFAULT 0,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT FALSE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    restrict_direct_push BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_force_push BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_deletion BOOLEAN NOT NULL DEFAULT TRUE,
    allow_administrator_bypass BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (required_approvals >= 0)
);

CREATE TABLE required_status_checks (
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policies(policy_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    PRIMARY KEY (policy_id, check_name)
);

CREATE INDEX idx_events_type_status
    ON events(event_type, status);

CREATE INDEX idx_invocations_function_time
    ON invocations(function_id, invoked_at DESC);

CREATE INDEX idx_pull_requests_target_state
    ON pull_requests(target_branch_id, state);

CREATE INDEX idx_reviews_pull_request_state
    ON reviews(pull_request_id, review_state);

CREATE INDEX idx_status_checks_pr_state
    ON status_checks(pull_request_id, state);

INSERT INTO serverless_functions (
    function_name,
    runtime,
    trigger,
    memory_mb,
    timeout_ms,
    minimum_instances,
    maximum_instances
)
VALUES
(
    'order-processor',
    'python',
    'event',
    512,
    3000,
    0,
    20
),
(
    'http-api',
    'javascript',
    'http',
    256,
    2000,
    0,
    50
),
(
    'file-processor',
    'java',
    'event',
    1024,
    10000,
    0,
    15
);

INSERT INTO events (
    event_id,
    event_type,
    source,
    payload
)
VALUES
(
    '00000000-0000-0000-0000-000000000101',
    'order.created',
    'checkout-service',
    '{"customer_id":"customer-42","amount":1499.50}'
),
(
    '00000000-0000-0000-0000-000000000102',
    'file.uploaded',
    'object-storage',
    '{"filename":"inspection-report.pdf","size_bytes":1500000}'
);

INSERT INTO function_subscriptions (
    function_id,
    event_type
)
SELECT function_id, 'order.created'
FROM serverless_functions
WHERE function_name = 'order-processor';

INSERT INTO function_subscriptions (
    function_id,
    event_type
)
SELECT function_id, 'file.uploaded'
FROM serverless_functions
WHERE function_name = 'file-processor';

INSERT INTO invocations (
    function_id,
    event_id,
    status,
    duration_ms,
    cold_start
)
SELECT
    f.function_id,
    '00000000-0000-0000-0000-000000000101',
    'success',
    43.712,
    TRUE
FROM serverless_functions f
WHERE f.function_name = 'order-processor';

INSERT INTO invocations (
    function_id,
    event_id,
    status,
    duration_ms,
    cold_start
)
SELECT
    f.function_id,
    '00000000-0000-0000-0000-000000000102',
    'success',
    71.331,
    FALSE
FROM serverless_functions f
WHERE f.function_name = 'file-processor';

INSERT INTO processed_events (
    function_id,
    event_id,
    result
)
SELECT
    f.function_id,
    '00000000-0000-0000-0000-000000000101',
    '{"status":"accepted","order_id":"ord-1001"}'
FROM serverless_functions f
WHERE f.function_name = 'order-processor'
ON CONFLICT (function_id, event_id) DO NOTHING;

INSERT INTO repositories (
    repository_name,
    owner_name
)
VALUES
(
    'payment-platform',
    'platform-engineering'
);

INSERT INTO branches (
    repository_id,
    branch_name,
    protected
)
SELECT repository_id, 'main', TRUE
FROM repositories
WHERE repository_name = 'payment-platform';

INSERT INTO branches (
    repository_id,
    branch_name,
    protected
)
SELECT repository_id, 'feature/payment-validation', FALSE
FROM repositories
WHERE repository_name = 'payment-platform';

INSERT INTO pull_requests (
    repository_id,
    source_branch_id,
    target_branch_id,
    title,
    state,
    draft,
    mergeable
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    'Validate payment amount before authorization',
    'open',
    FALSE,
    TRUE
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/payment-validation'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'payment-platform';

INSERT INTO reviewers (username)
VALUES
('alice'),
('bob'),
('carol');

INSERT INTO review_requests (
    pull_request_id,
    reviewer_id
)
SELECT
    pr.pull_request_id,
    rv.reviewer_id
FROM pull_requests pr
JOIN reviewers rv
    ON rv.username IN ('alice', 'bob');

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    review_state,
    body
)
SELECT
    pr.pull_request_id,
    rv.reviewer_id,
    'approved',
    'Validation logic meets the service contract.'
FROM pull_requests pr
JOIN reviewers rv
    ON rv.username = 'alice';

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    review_state,
    body
)
SELECT
    pr.pull_request_id,
    rv.reviewer_id,
    'approved',
    'Error handling and boundary checks are acceptable.'
FROM pull_requests pr
JOIN reviewers rv
    ON rv.username = 'bob';

INSERT INTO review_comments (
    review_id,
    file_path,
    line_number,
    comment_body,
    resolved
)
SELECT
    review_id,
    'src/payment/validator.py',
    47,
    'Validate the currency code before applying amount limits.',
    TRUE
FROM reviews
WHERE review_state = 'approved'
  AND reviewer_id = (
      SELECT reviewer_id
      FROM reviewers
      WHERE username = 'alice'
  );

INSERT INTO commits (
    pull_request_id,
    commit_hash,
    parent_hash
)
SELECT
    pull_request_id,
    '1111111111111111111111111111111111111111',
    NULL
FROM pull_requests;

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    state,
    completed_at
)
SELECT
    pull_request_id,
    'build',
    'passed',
    CURRENT_TIMESTAMP
FROM pull_requests;

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    state,
    completed_at
)
SELECT
    pull_request_id,
    'unit-tests',
    'passed',
    CURRENT_TIMESTAMP
FROM pull_requests;

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    state,
    completed_at
)
SELECT
    pull_request_id,
    'security-scan',
    'passed',
    CURRENT_TIMESTAMP
FROM pull_requests;

INSERT INTO branch_protection_policies (
    branch_id,
    required_approvals,
    require_conversation_resolution,
    require_linear_history,
    restrict_direct_push,
    restrict_force_push,
    restrict_deletion,
    allow_administrator_bypass
)
SELECT
    branch_id,
    2,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    FALSE
FROM branches
WHERE branch_name = 'main';

INSERT INTO required_status_checks (
    policy_id,
    check_name
)
SELECT
    policy_id,
    check_name
FROM branch_protection_policies,
    (
        VALUES
            ('build'),
            ('unit-tests'),
            ('security-scan')
    ) AS checks(check_name);

CREATE VIEW function_observability AS
SELECT
    f.function_name,
    f.runtime,
    COUNT(i.invocation_id) AS invocation_count,
    COUNT(*) FILTER (
        WHERE i.status = 'failure'
    ) AS failure_count,
    ROUND(
        AVG(i.duration_ms),
        3
    ) AS average_duration_ms,
    COUNT(*) FILTER (
        WHERE i.cold_start
    ) AS cold_start_count
FROM serverless_functions f
LEFT JOIN invocations i
    ON i.function_id = f.function_id
GROUP BY
    f.function_id,
    f.function_name,
    f.runtime;

CREATE VIEW pull_request_merge_evaluation AS
WITH approval_counts AS (
    SELECT
        pr.pull_request_id,
        COUNT(DISTINCT r.reviewer_id)
            FILTER (
                WHERE r.review_state = 'approved'
                  AND r.dismissed_at IS NULL
            ) AS approvals
    FROM pull_requests pr
    LEFT JOIN reviews r
        ON r.pull_request_id = pr.pull_request_id
    GROUP BY pr.pull_request_id
),
required_checks AS (
    SELECT
        p.policy_id,
        p.branch_id,
        COUNT(rsc.check_name) AS required_count
    FROM branch_protection_policies p
    LEFT JOIN required_status_checks rsc
        ON rsc.policy_id = p.policy_id
    GROUP BY p.policy_id, p.branch_id
),
passed_checks AS (
    SELECT
        pr.pull_request_id,
        COUNT(rsc.check_name) AS passed_required_count
    FROM pull_requests pr
    JOIN branch_protection_policies p
        ON p.branch_id = pr.target_branch_id
    JOIN required_status_checks rsc
        ON rsc.policy_id = p.policy_id
    JOIN status_checks sc
        ON sc.pull_request_id = pr.pull_request_id
       AND sc.check_name = rsc.check_name
       AND sc.state = 'passed'
    GROUP BY pr.pull_request_id
)
SELECT
    pr.pull_request_id,
    pr.title,
    pr.state,
    pr.draft,
    pr.mergeable,
    pr.approvals_stale,
    ac.approvals,
    p.required_approvals,
    COALESCE(pc.passed_required_count, 0)
        AS passed_required_checks,
    rc.required_count,
    (
        pr.state = 'open'
        AND NOT pr.draft
        AND pr.mergeable
        AND NOT pr.approvals_stale
        AND ac.approvals >= p.required_approvals
        AND COALESCE(pc.passed_required_count, 0)
            = rc.required_count
    ) AS merge_eligible
FROM pull_requests pr
JOIN branches b
    ON b.branch_id = pr.target_branch_id
JOIN branch_protection_policies p
    ON p.branch_id = b.branch_id
JOIN approval_counts ac
    ON ac.pull_request_id = pr.pull_request_id
JOIN required_checks rc
    ON rc.branch_id = b.branch_id
LEFT JOIN passed_checks pc
    ON pc.pull_request_id = pr.pull_request_id;

SELECT *
FROM function_observability
ORDER BY function_name;

SELECT
    event_type,
    status,
    COUNT(*) AS event_count
FROM events
GROUP BY event_type, status
ORDER BY event_type, status;

SELECT
    pull_request_id,
    title,
    approvals,
    required_approvals,
    passed_required_checks,
    required_count,
    merge_eligible
FROM pull_request_merge_evaluation;

SELECT
    pr.pull_request_id,
    pr.title,
    rv.username AS reviewer,
    r.review_state,
    r.dismissed_at
FROM pull_requests pr
JOIN reviews r
    ON r.pull_request_id = pr.pull_request_id
JOIN reviewers rv
    ON rv.reviewer_id = r.reviewer_id
ORDER BY pr.pull_request_id, rv.username;

SELECT
    f.function_name,
    COUNT(i.invocation_id) AS invocations,
    ROUND(
        AVG(i.duration_ms),
        2
    ) AS avg_duration_ms,
    MAX(i.duration_ms) AS max_duration_ms
FROM serverless_functions f
LEFT JOIN invocations i
    ON i.function_id = f.function_id
GROUP BY f.function_name
ORDER BY avg_duration_ms DESC;

BEGIN;

INSERT INTO events (
    event_id,
    event_type,
    source,
    payload
)
VALUES (
    '00000000-0000-0000-0000-000000000103',
    'order.created',
    'checkout-service',
    '{"customer_id":"customer-99","amount":725.00}'
);

INSERT INTO processed_events (
    function_id,
    event_id,
    result
)
SELECT
    f.function_id,
    '00000000-0000-0000-0000-000000000103',
    '{"status":"accepted"}'
FROM serverless_functions f
WHERE f.function_name = 'order-processor'
ON CONFLICT (function_id, event_id)
DO NOTHING;

UPDATE events
SET
    status = 'processed',
    processed_at = CURRENT_TIMESTAMP
WHERE event_id =
    '00000000-0000-0000-0000-000000000103';

COMMIT;

SELECT
    event_id,
    event_type,
    status,
    processed_at
FROM events
WHERE event_id =
    '00000000-0000-0000-0000-000000000103';

-- The primary key on processed_events makes duplicate processing
-- detectable at the database layer. ON CONFLICT prevents a second
-- result from replacing the first result for the same function/event pair.
