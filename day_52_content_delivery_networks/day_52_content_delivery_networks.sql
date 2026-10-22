DROP SCHEMA IF EXISTS cdn_governance CASCADE;
CREATE SCHEMA cdn_governance;
SET search_path = cdn_governance, public;

-- A CDN is represented as origin infrastructure plus geographically
-- distributed edge locations. Repository governance is kept separate
-- from delivery data so each concern has explicit relational boundaries.

CREATE TYPE pr_state AS ENUM (
    'DRAFT',
    'OPEN',
    'CLOSED',
    'MERGED'
);

CREATE TYPE review_state AS ENUM (
    'PENDING',
    'COMMENTED',
    'CHANGES_REQUESTED',
    'APPROVED',
    'DISMISSED'
);

CREATE TYPE check_state AS ENUM (
    'PENDING',
    'PASSING',
    'FAILING'
);

CREATE TYPE merge_strategy AS ENUM (
    'MERGE_COMMIT',
    'SQUASH',
    'REBASE'
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    default_branch TEXT NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name),
    CHECK (name <> ''),
    CHECK (default_branch <> '')
);

CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (username <> '')
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, branch_name),
    CHECK (branch_name <> '')
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    sha TEXT NOT NULL,
    author_id BIGINT NOT NULL
        REFERENCES users(user_id),
    committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    message TEXT NOT NULL,
    UNIQUE (repository_id, sha),
    CHECK (length(sha) >= 7),
    CHECK (message <> '')
);

CREATE TABLE pull_requests (
    pull_request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    source_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    target_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    author_id BIGINT NOT NULL
        REFERENCES users(user_id),
    title TEXT NOT NULL,
    state pr_state NOT NULL DEFAULT 'OPEN',
    is_draft BOOLEAN NOT NULL DEFAULT FALSE,
    mergeable BOOLEAN NOT NULL DEFAULT TRUE,
    unresolved_conversations INTEGER NOT NULL DEFAULT 0,
    merge_strategy merge_strategy,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    merged_at TIMESTAMPTZ,
    CHECK (source_branch_id <> target_branch_id),
    CHECK (unresolved_conversations >= 0),
    CHECK (
        (state = 'DRAFT' AND is_draft)
        OR state <> 'DRAFT'
    )
);

CREATE TABLE pull_request_commits (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    commit_id BIGINT NOT NULL
        REFERENCES commits(commit_id) ON DELETE RESTRICT,
    sequence_number INTEGER NOT NULL,
    PRIMARY KEY (pull_request_id, commit_id),
    UNIQUE (pull_request_id, sequence_number),
    CHECK (sequence_number > 0)
);

CREATE TABLE reviewers (
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id) ON DELETE CASCADE,
    eligible BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (repository_id, user_id)
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES users(user_id),
    state review_state NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stale BOOLEAN NOT NULL DEFAULT FALSE,
    dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (pull_request_id, reviewer_id, submitted_at)
);

CREATE TABLE review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES reviews(review_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (line_number > 0),
    CHECK (body <> '')
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    state check_state NOT NULL DEFAULT 'PENDING',
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name)
);

CREATE TABLE branch_protection_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id) ON DELETE CASCADE,
    required_approvals INTEGER NOT NULL DEFAULT 1,
    require_passing_checks BOOLEAN NOT NULL DEFAULT TRUE,
    require_resolved_conversations BOOLEAN NOT NULL DEFAULT TRUE,
    allow_direct_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_force_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_branch_deletion BOOLEAN NOT NULL DEFAULT FALSE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    allow_administrator_bypass BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, branch_id),
    CHECK (required_approvals >= 0)
);

CREATE TABLE required_status_checks (
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policies(policy_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    PRIMARY KEY (policy_id, check_name),
    CHECK (check_name <> '')
);

CREATE TABLE edge_locations (
    edge_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    city TEXT NOT NULL,
    latency_to_origin_ms INTEGER NOT NULL,
    capacity_objects INTEGER NOT NULL,
    CHECK (latency_to_origin_ms >= 0),
    CHECK (capacity_objects > 0)
);

CREATE TABLE origin_objects (
    object_id BIGSERIAL PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL,
    etag TEXT NOT NULL,
    cache_control TEXT NOT NULL,
    object_size_bytes BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (path LIKE '/%'),
    CHECK (object_size_bytes >= 0)
);

CREATE TABLE edge_cache_entries (
    edge_id BIGINT NOT NULL
        REFERENCES edge_locations(edge_id) ON DELETE CASCADE,
    object_id BIGINT NOT NULL
        REFERENCES origin_objects(object_id) ON DELETE CASCADE,
    cached_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (edge_id, object_id),
    CHECK (expires_at > cached_at),
    CHECK (hit_count >= 0)
);

CREATE INDEX idx_pr_repository_target
    ON pull_requests(repository_id, target_branch_id, state);

CREATE INDEX idx_reviews_pr_state
    ON reviews(pull_request_id, state, stale, dismissed);

CREATE INDEX idx_status_checks_pr_state
    ON status_checks(pull_request_id, state);

CREATE INDEX idx_cache_expiration
    ON edge_cache_entries(expires_at);

INSERT INTO repositories (name, default_branch)
VALUES ('edge-platform', 'main');

INSERT INTO users (username)
VALUES
    ('maya'),
    ('liam'),
    ('noah'),
    ('sophia'),
    ('olivia');

INSERT INTO branches (repository_id, branch_name, protected)
SELECT repository_id, branch_name, protected
FROM (
    SELECT r.repository_id, 'main' AS branch_name, TRUE AS protected
    FROM repositories r
    WHERE r.name = 'edge-platform'
    UNION ALL
    SELECT r.repository_id, 'feature/cache-policy', FALSE
    FROM repositories r
    WHERE r.name = 'edge-platform'
    UNION ALL
    SELECT r.repository_id, 'feature/stale-approval', FALSE
    FROM repositories r
    WHERE r.name = 'edge-platform'
) AS b;

INSERT INTO commits (
    repository_id,
    sha,
    author_id,
    message
)
SELECT
    r.repository_id,
    'abcdef1234567890',
    u.user_id,
    'Define cache-control policy'
FROM repositories r
JOIN users u ON u.username = 'maya'
WHERE r.name = 'edge-platform';

INSERT INTO commits (
    repository_id,
    sha,
    author_id,
    message
)
SELECT
    r.repository_id,
    '1234567890abcdef',
    u.user_id,
    'Add edge cache invalidation'
FROM repositories r
JOIN users u ON u.username = 'maya'
WHERE r.name = 'edge-platform';

INSERT INTO pull_requests (
    repository_id,
    source_branch_id,
    target_branch_id,
    author_id,
    title,
    state,
    is_draft,
    mergeable,
    unresolved_conversations
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    author.user_id,
    'Introduce CDN cache policy',
    'OPEN',
    FALSE,
    TRUE,
    0
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/cache-policy'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
JOIN users author ON author.username = 'maya'
WHERE r.name = 'edge-platform';

INSERT INTO pull_request_commits (
    pull_request_id,
    commit_id,
    sequence_number
)
SELECT
    pr.pull_request_id,
    c.commit_id,
    1
FROM pull_requests pr
JOIN commits c
    ON c.sha = 'abcdef1234567890'
WHERE pr.title = 'Introduce CDN cache policy';

INSERT INTO pull_request_commits (
    pull_request_id,
    commit_id,
    sequence_number
)
SELECT
    pr.pull_request_id,
    c.commit_id,
    2
FROM pull_requests pr
JOIN commits c
    ON c.sha = '1234567890abcdef'
WHERE pr.title = 'Introduce CDN cache policy';

INSERT INTO reviewers (repository_id, user_id, eligible)
SELECT r.repository_id, u.user_id, TRUE
FROM repositories r
CROSS JOIN users u
WHERE r.name = 'edge-platform'
  AND u.username IN ('liam', 'noah', 'sophia');

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    state,
    stale,
    dismissed
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'APPROVED',
    FALSE,
    FALSE
FROM pull_requests pr
JOIN users u ON u.username IN ('liam', 'noah')
WHERE pr.title = 'Introduce CDN cache policy';

INSERT INTO review_comments (
    review_id,
    file_path,
    line_number,
    body,
    resolved
)
SELECT
    review_id,
    'cdn/cache_policy.py',
    42,
    'Cache-Control must prevent shared caching of private objects.',
    TRUE
FROM reviews
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE title = 'Introduce CDN cache policy'
)
LIMIT 1;

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    state
)
SELECT
    pr.pull_request_id,
    check_name,
    'PASSING'
FROM pull_requests pr
CROSS JOIN (
    VALUES ('unit-tests'), ('integration-tests'), ('security-scan')
) AS checks(check_name)
WHERE pr.title = 'Introduce CDN cache policy';

INSERT INTO branch_protection_policies (
    repository_id,
    branch_id,
    required_approvals,
    require_passing_checks,
    require_resolved_conversations,
    allow_direct_push,
    allow_force_push,
    allow_branch_deletion,
    require_linear_history,
    allow_administrator_bypass
)
SELECT
    r.repository_id,
    b.branch_id,
    2,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    FALSE,
    TRUE,
    FALSE
FROM repositories r
JOIN branches b
    ON b.repository_id = r.repository_id
   AND b.branch_name = 'main'
WHERE r.name = 'edge-platform';

INSERT INTO required_status_checks (policy_id, check_name)
SELECT policy_id, check_name
FROM branch_protection_policies
CROSS JOIN (
    VALUES ('unit-tests'), ('integration-tests'), ('security-scan')
) AS checks(check_name);

INSERT INTO edge_locations (
    name,
    region,
    city,
    latency_to_origin_ms,
    capacity_objects
)
VALUES
    ('edge-delhi', 'asia', 'Delhi', 180, 10000),
    ('edge-frankfurt', 'europe', 'Frankfurt', 120, 10000),
    ('edge-virginia', 'north-america', 'Virginia', 20, 10000);

INSERT INTO origin_objects (
    path,
    content_type,
    etag,
    cache_control,
    object_size_bytes
)
VALUES
    (
        '/index.html',
        'text/html',
        'etag-index-001',
        'public, max-age=60',
        4200
    ),
    (
        '/assets/app.js',
        'application/javascript',
        'etag-app-001',
        'public, max-age=300',
        183000
    ),
    (
        '/account/profile.json',
        'application/json',
        'etag-profile-001',
        'private, no-store',
        900
    );

INSERT INTO edge_cache_entries (
    edge_id,
    object_id,
    cached_at,
    expires_at
)
SELECT
    e.edge_id,
    o.object_id,
    now(),
    now() + INTERVAL '300 seconds'
FROM edge_locations e
JOIN origin_objects o
    ON o.path = '/assets/app.js'
WHERE e.name IN ('edge-delhi', 'edge-frankfurt');

CREATE OR REPLACE FUNCTION validate_shared_cache_entry()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    object_cache_control TEXT;
BEGIN
    SELECT cache_control
    INTO object_cache_control
    FROM origin_objects
    WHERE object_id = NEW.object_id;

    IF lower(object_cache_control) LIKE '%no-store%'
       OR lower(object_cache_control) LIKE '%private%' THEN
        RAISE EXCEPTION
            'Private or no-store object % cannot be stored in shared edge cache',
            NEW.object_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_shared_cache_entry
BEFORE INSERT OR UPDATE ON edge_cache_entries
FOR EACH ROW
EXECUTE FUNCTION validate_shared_cache_entry();

CREATE OR REPLACE FUNCTION merge_eligibility(
    requested_pr BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT,
    active_approvals BIGINT,
    required_approvals INTEGER,
    failing_checks BIGINT,
    unresolved_conversations INTEGER
)
LANGUAGE sql
AS $$
WITH pr AS (
    SELECT
        p.*,
        bp.required_approvals,
        bp.require_passing_checks,
        bp.require_resolved_conversations,
        bp.policy_id
    FROM pull_requests p
    JOIN branch_protection_policies bp
      ON bp.repository_id = p.repository_id
     AND bp.branch_id = p.target_branch_id
    WHERE p.pull_request_id = requested_pr
),
approvals AS (
    SELECT
        r.pull_request_id,
        count(*) FILTER (
            WHERE r.state = 'APPROVED'
              AND r.stale = FALSE
              AND r.dismissed = FALSE
              AND COALESCE(rv.eligible, FALSE) = TRUE
        ) AS active_approvals
    FROM reviews r
    JOIN pull_requests p
      ON p.pull_request_id = r.pull_request_id
    LEFT JOIN reviewers rv
      ON rv.repository_id = p.repository_id
     AND rv.user_id = r.reviewer_id
    WHERE r.pull_request_id = requested_pr
    GROUP BY r.pull_request_id
),
required_checks AS (
    SELECT
        COUNT(*) AS total_required,
        COUNT(*) FILTER (
            WHERE sc.state = 'PASSING'
        ) AS passing_required
    FROM pr
    JOIN required_status_checks rsc
      ON rsc.policy_id = pr.policy_id
    LEFT JOIN status_checks sc
      ON sc.pull_request_id = pr.pull_request_id
     AND sc.check_name = rsc.check_name
),
evaluation AS (
    SELECT
        pr.*,
        COALESCE(a.active_approvals, 0) AS active_approvals,
        COALESCE(rc.total_required, 0) AS total_required,
        COALESCE(rc.passing_required, 0) AS passing_required
    FROM pr
    LEFT JOIN approvals a
      ON a.pull_request_id = pr.pull_request_id
    CROSS JOIN required_checks rc
)
SELECT
    (
        state = 'OPEN'
        AND is_draft = FALSE
        AND mergeable = TRUE
        AND active_approvals >= required_approvals
        AND (
            NOT require_passing_checks
            OR (
                total_required > 0
                AND passing_required = total_required
            )
        )
        AND (
            NOT require_resolved_conversations
            OR unresolved_conversations = 0
        )
    ) AS eligible,
    CASE
        WHEN state <> 'OPEN'
            THEN 'Pull Request is not open'
        WHEN is_draft
            THEN 'Draft Pull Request cannot be merged'
        WHEN NOT mergeable
            THEN 'Merge conflict must be resolved'
        WHEN active_approvals < required_approvals
            THEN 'Required approvals are missing'
        WHEN require_passing_checks
             AND (
                 total_required = 0
                 OR passing_required <> total_required
             )
            THEN 'Required status checks are not passing'
        WHEN require_resolved_conversations
             AND unresolved_conversations > 0
            THEN 'Review conversations remain unresolved'
        ELSE 'All merge conditions satisfied'
    END AS reason,
    active_approvals,
    required_approvals,
    total_required - passing_required AS failing_checks,
    unresolved_conversations
FROM evaluation;
$$;

CREATE VIEW active_review_approvals AS
SELECT
    pr.pull_request_id,
    pr.title,
    count(*) AS approval_count
FROM pull_requests pr
JOIN reviews r
  ON r.pull_request_id = pr.pull_request_id
JOIN reviewers rv
  ON rv.repository_id = pr.repository_id
 AND rv.user_id = r.reviewer_id
WHERE r.state = 'APPROVED'
  AND r.stale = FALSE
  AND r.dismissed = FALSE
  AND rv.eligible = TRUE
GROUP BY pr.pull_request_id, pr.title;

CREATE VIEW edge_cache_report AS
SELECT
    e.name AS edge_location,
    e.region,
    o.path,
    o.etag,
    c.cached_at,
    c.expires_at,
    c.hit_count,
    CASE
        WHEN c.expires_at > now() THEN 'FRESH'
        ELSE 'EXPIRED'
    END AS cache_state
FROM edge_cache_entries c
JOIN edge_locations e ON e.edge_id = c.edge_id
JOIN origin_objects o ON o.object_id = c.object_id;

-- Pull Request merge evaluation.
SELECT *
FROM merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Introduce CDN cache policy'
    )
);

-- Review and approval reporting.
SELECT *
FROM active_review_approvals;

-- Cache placement and freshness reporting.
SELECT *
FROM edge_cache_report
ORDER BY edge_location, path;

-- Identify objects that must never be shared through edge caches.
SELECT
    path,
    cache_control,
    CASE
        WHEN lower(cache_control) LIKE '%private%'
          OR lower(cache_control) LIKE '%no-store%'
        THEN 'DO NOT CACHE'
        ELSE 'CACHEABLE'
    END AS caching_policy
FROM origin_objects
ORDER BY path;

-- Demonstrate transactional cache invalidation.
BEGIN;

DELETE FROM edge_cache_entries
WHERE object_id = (
    SELECT object_id
    FROM origin_objects
    WHERE path = '/assets/app.js'
);

COMMIT;

-- Confirm the invalidation.
SELECT *
FROM edge_cache_report
ORDER BY edge_location, path;

-- A failed insertion demonstrates database-level cache safety.
-- It is intentionally wrapped in a savepoint so the rest of the script
-- remains executable after PostgreSQL rejects the protected object.
BEGIN;

SAVEPOINT protected_object_test;

INSERT INTO edge_cache_entries (
    edge_id,
    object_id,
    cached_at,
    expires_at
)
SELECT
    e.edge_id,
    o.object_id,
    now(),
    now() + INTERVAL '60 seconds'
FROM edge_locations e
JOIN origin_objects o
  ON o.path = '/account/profile.json'
WHERE e.name = 'edge-delhi';

ROLLBACK TO SAVEPOINT protected_object_test;
COMMIT;

-- Latency comparison illustrates the purpose of edge caching:
-- a cache hit avoids the modeled origin round trip.
SELECT
    e.name,
    e.region,
    e.latency_to_origin_ms,
    CASE
        WHEN c.object_id IS NOT NULL
         AND c.expires_at > now()
        THEN 'EDGE HIT'
        ELSE 'ORIGIN FETCH'
    END AS delivery_path
FROM edge_locations e
LEFT JOIN edge_cache_entries c
  ON c.edge_id = e.edge_id
ORDER BY e.region, e.name;
