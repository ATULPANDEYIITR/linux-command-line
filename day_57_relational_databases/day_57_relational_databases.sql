DROP SCHEMA IF EXISTS repository_governance CASCADE;
CREATE SCHEMA repository_governance;

SET search_path TO repository_governance, public;

-- The relational model separates proposed changes, review decisions,
-- approval state, automated checks, and repository-level enforcement.

CREATE TYPE repository_governance.pr_state AS ENUM (
    'draft',
    'open',
    'closed',
    'merged'
);

CREATE TYPE repository_governance.review_state AS ENUM (
    'commented',
    'approved',
    'changes_requested',
    'dismissed'
);

CREATE TYPE repository_governance.check_state AS ENUM (
    'pending',
    'success',
    'failure'
);

CREATE TYPE repository_governance.merge_strategy AS ENUM (
    'merge_commit',
    'squash',
    'rebase'
);

CREATE TABLE repository (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_name TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (owner_name, repository_name),
    CHECK (length(trim(owner_name)) > 0),
    CHECK (length(trim(repository_name)) > 0)
);

CREATE TABLE repository_member (
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    role_name TEXT NOT NULL DEFAULT 'developer',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (repository_id, username),
    CHECK (role_name IN ('developer', 'maintainer', 'administrator'))
);

CREATE TABLE branch (
    branch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    UNIQUE (repository_id, branch_name),
    CHECK (length(trim(branch_name)) > 0)
);

CREATE TABLE commit (
    commit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    commit_hash TEXT NOT NULL,
    author_username TEXT NOT NULL,
    message TEXT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repository_id, commit_hash),
    FOREIGN KEY (repository_id, author_username)
        REFERENCES repository_member(repository_id, username),
    CHECK (length(trim(commit_hash)) >= 7),
    CHECK (length(trim(message)) > 0)
);

CREATE TABLE branch_commit (
    branch_id BIGINT NOT NULL
        REFERENCES branch(branch_id) ON DELETE CASCADE,
    commit_id BIGINT NOT NULL
        REFERENCES commit(commit_id) ON DELETE RESTRICT,
    position_no BIGINT NOT NULL,
    PRIMARY KEY (branch_id, commit_id),
    UNIQUE (branch_id, position_no),
    CHECK (position_no > 0)
);

CREATE TABLE pull_request (
    pull_request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repository(repository_id) ON DELETE CASCADE,
    pull_request_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    source_branch_id BIGINT NOT NULL
        REFERENCES branch(branch_id) ON DELETE RESTRICT,
    target_branch_id BIGINT NOT NULL
        REFERENCES branch(branch_id) ON DELETE RESTRICT,
    author_username TEXT NOT NULL,
    state pr_state NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    merged_at TIMESTAMPTZ,
    UNIQUE (repository_id, pull_request_number),
    FOREIGN KEY (repository_id, author_username)
        REFERENCES repository_member(repository_id, username),
    CHECK (length(trim(title)) > 0),
    CHECK (source_branch_id <> target_branch_id),
    CHECK (
        (state = 'merged' AND merged_at IS NOT NULL)
        OR state <> 'merged'
    )
);

CREATE TABLE pull_request_commit (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id) ON DELETE CASCADE,
    commit_id BIGINT NOT NULL
        REFERENCES commit(commit_id) ON DELETE RESTRICT,
    sequence_no INTEGER NOT NULL,
    PRIMARY KEY (pull_request_id, commit_id),
    UNIQUE (pull_request_id, sequence_no),
    CHECK (sequence_no > 0)
);

CREATE TABLE review (
    review_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id) ON DELETE CASCADE,
    reviewer_username TEXT NOT NULL,
    review_state review_state NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dismissed_at TIMESTAMPTZ,
    FOREIGN KEY (
        (SELECT repository_id
         FROM pull_request p
         WHERE p.pull_request_id = pull_request_id),
        reviewer_username
    ) REFERENCES repository_member(repository_id, username)
    DEFERRABLE INITIALLY DEFERRED
);

-- PostgreSQL does not permit a subquery in a foreign-key column definition.
-- The repository membership relationship is therefore enforced by the trigger
-- below, while the pull request relationship remains a normal foreign key.

CREATE TABLE review_comment (
    comment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    review_id BIGINT
        REFERENCES review(review_id) ON DELETE CASCADE,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id) ON DELETE CASCADE,
    reviewer_username TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    CHECK (line_number > 0),
    CHECK (length(trim(file_path)) > 0),
    CHECK (length(trim(body)) > 0),
    CHECK (
        (resolved = TRUE AND resolved_at IS NOT NULL)
        OR resolved = FALSE
    )
);

CREATE TABLE status_check (
    status_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_request(pull_request_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    check_state check_state NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name),
    CHECK (length(trim(check_name)) > 0)
);

CREATE TABLE branch_protection_policy (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE
        REFERENCES branch(branch_id) ON DELETE CASCADE,
    required_approvals INTEGER NOT NULL DEFAULT 0,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT TRUE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    allow_direct_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_force_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_branch_deletion BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (required_approvals >= 0)
);

CREATE TABLE required_status_check (
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policy(policy_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    PRIMARY KEY (policy_id, check_name),
    CHECK (length(trim(check_name)) > 0)
);

CREATE TABLE allowed_merge_strategy (
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policy(policy_id) ON DELETE CASCADE,
    strategy merge_strategy NOT NULL,
    PRIMARY KEY (policy_id, strategy)
);

CREATE TABLE policy_bypass_user (
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policy(policy_id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    PRIMARY KEY (policy_id, username)
);

CREATE TABLE merge (
    merge_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL UNIQUE
        REFERENCES pull_request(pull_request_id) ON DELETE RESTRICT,
    merged_by TEXT NOT NULL,
    strategy merge_strategy NOT NULL,
    resulting_commit_hash TEXT NOT NULL,
    merged_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_branch_repository
    ON branch(repository_id);

CREATE INDEX idx_commit_repository_author
    ON commit(repository_id, author_username);

CREATE INDEX idx_pull_request_target_state
    ON pull_request(target_branch_id, state);

CREATE INDEX idx_review_pr_reviewer_time
    ON review(pull_request_id, reviewer_username, submitted_at DESC);

CREATE INDEX idx_status_check_pr_state
    ON status_check(pull_request_id, check_state);

CREATE INDEX idx_review_comment_pr_unresolved
    ON review_comment(pull_request_id)
    WHERE resolved = FALSE;

CREATE OR REPLACE FUNCTION validate_pull_request_membership()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    pr_repository_id BIGINT;
BEGIN
    SELECT repository_id
      INTO pr_repository_id
      FROM pull_request
     WHERE pull_request_id = NEW.pull_request_id;

    IF NOT EXISTS (
        SELECT 1
          FROM repository_member
         WHERE repository_id = pr_repository_id
           AND username = NEW.reviewer_username
    ) THEN
        RAISE EXCEPTION
            'Reviewer % is not a member of repository %',
            NEW.reviewer_username,
            pr_repository_id;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pull_request
         WHERE pull_request_id = NEW.pull_request_id
           AND author_username = NEW.reviewer_username
    ) THEN
        RAISE EXCEPTION
            'Pull request authors cannot approve their own changes';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_review_membership
BEFORE INSERT OR UPDATE ON review
FOR EACH ROW
EXECUTE FUNCTION validate_pull_request_membership();

CREATE OR REPLACE FUNCTION validate_review_comment_membership()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    pr_repository_id BIGINT;
BEGIN
    SELECT repository_id
      INTO pr_repository_id
      FROM pull_request
     WHERE pull_request_id = NEW.pull_request_id;

    IF NOT EXISTS (
        SELECT 1
          FROM repository_member
         WHERE repository_id = pr_repository_id
           AND username = NEW.reviewer_username
    ) THEN
        RAISE EXCEPTION
            'Comment author % is not a repository member',
            NEW.reviewer_username;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_review_comment_membership
BEFORE INSERT OR UPDATE ON review_comment
FOR EACH ROW
EXECUTE FUNCTION validate_review_comment_membership();

CREATE OR REPLACE FUNCTION validate_protected_branch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.protected = TRUE
       AND NEW.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'A protected branch cannot be marked deleted';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_branch_protection
BEFORE INSERT OR UPDATE ON branch
FOR EACH ROW
EXECUTE FUNCTION validate_protected_branch();

CREATE OR REPLACE FUNCTION refresh_pull_request_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_pull_request_timestamp
BEFORE UPDATE ON pull_request
FOR EACH ROW
EXECUTE FUNCTION refresh_pull_request_timestamp();

CREATE OR REPLACE FUNCTION merge_pull_request(
    p_pull_request_id BIGINT,
    p_actor TEXT,
    p_strategy merge_strategy
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_pr pull_request%ROWTYPE;
    v_policy branch_protection_policy%ROWTYPE;
    v_approvals INTEGER;
    v_unresolved INTEGER;
    v_required_checks INTEGER;
    v_successful_checks INTEGER;
    v_result_hash TEXT;
    v_is_bypass BOOLEAN;
BEGIN
    SELECT *
      INTO v_pr
      FROM pull_request
     WHERE pull_request_id = p_pull_request_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pull request % does not exist', p_pull_request_id;
    END IF;

    IF v_pr.state <> 'open' THEN
        RAISE EXCEPTION 'Pull request % is not open', p_pull_request_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM repository_member
         WHERE repository_id = v_pr.repository_id
           AND username = p_actor
    ) THEN
        RAISE EXCEPTION 'Merge actor % is not a repository member', p_actor;
    END IF;

    SELECT bp.*
      INTO v_policy
      FROM branch_protection_policy bp
     WHERE bp.branch_id = v_pr.target_branch_id;

    v_is_bypass := EXISTS (
        SELECT 1
          FROM policy_bypass_user pbu
         WHERE pbu.policy_id = v_policy.policy_id
           AND pbu.username = p_actor
    );

    IF NOT v_is_bypass THEN
        IF NOT EXISTS (
            SELECT 1
              FROM allowed_merge_strategy ams
             WHERE ams.policy_id = v_policy.policy_id
               AND ams.strategy = p_strategy
        ) THEN
            RAISE EXCEPTION 'Merge strategy % is prohibited',
                p_strategy;
        END IF;

        IF v_policy.require_linear_history
           AND p_strategy = 'merge_commit' THEN
            RAISE EXCEPTION 'Linear history prohibits merge commits';
        END IF;
    END IF;

    WITH latest AS (
        SELECT DISTINCT ON (r.reviewer_username)
               r.reviewer_username,
               r.review_state
          FROM review r
         WHERE r.pull_request_id = v_pr.pull_request_id
         ORDER BY r.reviewer_username, r.submitted_at DESC, r.review_id DESC
    )
    SELECT count(*)
      INTO v_approvals
      FROM latest
     WHERE review_state = 'approved';

    IF NOT v_is_bypass
       AND v_approvals < v_policy.required_approvals THEN
        RAISE EXCEPTION
            'Required approvals %, effective approvals %',
            v_policy.required_approvals,
            v_approvals;
    END IF;

    IF NOT v_is_bypass
       AND EXISTS (
           WITH latest AS (
               SELECT DISTINCT ON (r.reviewer_username)
                      r.reviewer_username,
                      r.review_state
                 FROM review r
                WHERE r.pull_request_id = v_pr.pull_request_id
                ORDER BY r.reviewer_username,
                         r.submitted_at DESC,
                         r.review_id DESC
           )
           SELECT 1
             FROM latest
            WHERE review_state = 'changes_requested'
       ) THEN
        RAISE EXCEPTION 'An effective changes-requested review blocks merge';
    END IF;

    SELECT count(*)
      INTO v_unresolved
      FROM review_comment
     WHERE pull_request_id = v_pr.pull_request_id
       AND resolved = FALSE;

    IF NOT v_is_bypass
       AND v_policy.require_conversation_resolution
       AND v_unresolved > 0 THEN
        RAISE EXCEPTION 'Unresolved review conversations remain';
    END IF;

    SELECT count(*)
      INTO v_required_checks
      FROM required_status_check
     WHERE policy_id = v_policy.policy_id;

    SELECT count(*)
      INTO v_successful_checks
      FROM required_status_check rsc
      JOIN status_check sc
        ON sc.pull_request_id = v_pr.pull_request_id
       AND sc.check_name = rsc.check_name
     WHERE rsc.policy_id = v_policy.policy_id
       AND sc.check_state = 'success';

    IF NOT v_is_bypass
       AND v_successful_checks <> v_required_checks THEN
        RAISE EXCEPTION
            'Required status checks are incomplete: % of % successful',
            v_successful_checks,
            v_required_checks;
    END IF;

    v_result_hash :=
        encode(
            digest(
                v_pr.repository_id::TEXT || ':' ||
                v_pr.pull_request_id::TEXT || ':' ||
                p_strategy::TEXT || ':' ||
                clock_timestamp()::TEXT,
                'sha256'
            ),
            'hex'
        );

    INSERT INTO merge (
        pull_request_id,
        merged_by,
        strategy,
        resulting_commit_hash
    )
    VALUES (
        v_pr.pull_request_id,
        p_actor,
        p_strategy,
        v_result_hash
    );

    UPDATE pull_request
       SET state = 'merged',
           merged_at = CURRENT_TIMESTAMP
     WHERE pull_request_id = v_pr.pull_request_id;

    RETURN v_result_hash;
END;
$$;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO repository (
    owner_name,
    repository_name
)
VALUES (
    'platform-team',
    'payments-api'
);

INSERT INTO repository_member (
    repository_id,
    username,
    role_name
)
SELECT repository_id, username, role_name
FROM repository
CROSS JOIN (
    VALUES
        ('alice', 'developer'),
        ('bob', 'developer'),
        ('carol', 'maintainer'),
        ('david', 'maintainer'),
        ('platform-admin', 'administrator')
) AS members(username, role_name);

INSERT INTO branch (
    repository_id,
    branch_name,
    protected
)
SELECT repository_id, 'main', TRUE
FROM repository
UNION ALL
SELECT repository_id, 'feature/payment-timeout', FALSE
FROM repository;

INSERT INTO commit (
    repository_id,
    commit_hash,
    author_username,
    message
)
SELECT r.repository_id, x.commit_hash, x.author_username, x.message
FROM repository r
CROSS JOIN (
    VALUES
        ('root001abc', 'carol', 'Initial repository state'),
        ('commit101abc', 'alice', 'Introduce payment timeout configuration'),
        ('commit102abc', 'alice', 'Validate payment timeout configuration')
) AS x(commit_hash, author_username, message);

INSERT INTO branch_commit (
    branch_id,
    commit_id,
    position_no
)
SELECT b.branch_id, c.commit_id,
       CASE c.commit_hash
           WHEN 'root001abc' THEN 1
           WHEN 'commit101abc' THEN 2
           ELSE 3
       END
FROM branch b
JOIN commit c
  ON c.repository_id = b.repository_id
WHERE
    (b.branch_name = 'main' AND c.commit_hash = 'root001abc')
 OR (b.branch_name = 'feature/payment-timeout'
     AND c.commit_hash IN ('root001abc', 'commit101abc'));

INSERT INTO pull_request (
    repository_id,
    pull_request_number,
    title,
    source_branch_id,
    target_branch_id,
    author_username,
    state
)
SELECT
    r.repository_id,
    1,
    'Enforce payment timeout validation',
    source.branch_id,
    target.branch_id,
    'alice',
    'open'
FROM repository r
JOIN branch source
  ON source.repository_id = r.repository_id
 AND source.branch_name = 'feature/payment-timeout'
JOIN branch target
  ON target.repository_id = r.repository_id
 AND target.branch_name = 'main';

INSERT INTO pull_request_commit (
    pull_request_id,
    commit_id,
    sequence_no
)
SELECT pr.pull_request_id, c.commit_id, 1
FROM pull_request pr
JOIN commit c
  ON c.repository_id = pr.repository_id
WHERE pr.pull_request_number = 1
  AND c.commit_hash = 'commit102abc';

INSERT INTO branch_protection_policy (
    branch_id,
    required_approvals,
    require_conversation_resolution,
    require_linear_history,
    allow_direct_push,
    allow_force_push,
    allow_branch_deletion
)
SELECT
    branch_id,
    2,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    FALSE
FROM branch
WHERE branch_name = 'main';

INSERT INTO required_status_check (
    policy_id,
    check_name
)
SELECT policy_id, check_name
FROM branch_protection_policy
CROSS JOIN (
    VALUES
        ('unit-tests'),
        ('security-scan'),
        ('schema-validation')
) AS checks(check_name);

INSERT INTO allowed_merge_strategy (
    policy_id,
    strategy
)
SELECT policy_id, strategy::merge_strategy
FROM branch_protection_policy
CROSS JOIN (
    VALUES
        ('squash'),
        ('rebase')
) AS strategies(strategy);

INSERT INTO policy_bypass_user (
    policy_id,
    username
)
SELECT bp.policy_id, 'platform-admin'
FROM branch_protection_policy bp
JOIN branch b ON b.branch_id = bp.branch_id;

INSERT INTO review (
    pull_request_id,
    reviewer_username,
    review_state
)
SELECT pull_request_id, reviewer, review_state::review_state
FROM pull_request
CROSS JOIN (
    VALUES
        ('bob', 'approved'),
        ('carol', 'approved')
) AS reviews(reviewer, review_state)
WHERE pull_request_number = 1;

INSERT INTO review_comment (
    review_id,
    pull_request_id,
    reviewer_username,
    file_path,
    line_number,
    body
)
SELECT
    r.review_id,
    r.pull_request_id,
    r.reviewer_username,
    'src/payment_service.py',
    42,
    'Document the timeout boundary.'
FROM review r
WHERE r.pull_request_id = (
    SELECT pull_request_id
    FROM pull_request
    WHERE pull_request_number = 1
)
AND r.reviewer_username = 'bob';

INSERT INTO status_check (
    pull_request_id,
    check_name,
    check_state,
    details,
    completed_at
)
SELECT
    pull_request_id,
    check_name,
    'success',
    details,
    CURRENT_TIMESTAMP
FROM pull_request
CROSS JOIN (
    VALUES
        ('unit-tests', '248 tests passed'),
        ('security-scan', 'No high severity findings'),
        ('schema-validation', 'Migration is valid')
) AS checks(check_name, details)
WHERE pull_request_number = 1;

CREATE OR REPLACE VIEW merge_eligibility_report AS
WITH latest_reviews AS (
    SELECT DISTINCT ON (r.pull_request_id, r.reviewer_username)
           r.pull_request_id,
           r.reviewer_username,
           r.review_state,
           r.submitted_at
      FROM review r
     ORDER BY r.pull_request_id,
              r.reviewer_username,
              r.submitted_at DESC,
              r.review_id DESC
),
approval_counts AS (
    SELECT
        pull_request_id,
        count(*) FILTER (
            WHERE review_state = 'approved'
        ) AS effective_approvals,
        count(*) FILTER (
            WHERE review_state = 'changes_requested'
        ) AS blocking_reviews
    FROM latest_reviews
    GROUP BY pull_request_id
),
unresolved AS (
    SELECT
        pull_request_id,
        count(*) AS unresolved_comments
    FROM review_comment
    WHERE resolved = FALSE
    GROUP BY pull_request_id
),
required_checks AS (
    SELECT
        pr.pull_request_id,
        count(rsc.check_name) AS required_count,
        count(sc.check_name) FILTER (
            WHERE sc.check_state = 'success'
        ) AS successful_count
    FROM pull_request pr
    JOIN branch_protection_policy bp
      ON bp.branch_id = pr.target_branch_id
    LEFT JOIN required_status_check rsc
      ON rsc.policy_id = bp.policy_id
    LEFT JOIN status_check sc
      ON sc.pull_request_id = pr.pull_request_id
     AND sc.check_name = rsc.check_name
    GROUP BY pr.pull_request_id
)
SELECT
    pr.pull_request_id,
    r.repository_name,
    pr.pull_request_number,
    pr.title,
    pr.state,
    source.branch_name AS source_branch,
    target.branch_name AS target_branch,
    pr.author_username,
    COALESCE(ac.effective_approvals, 0) AS effective_approvals,
    bp.required_approvals,
    COALESCE(ac.blocking_reviews, 0) AS blocking_reviews,
    COALESCE(u.unresolved_comments, 0) AS unresolved_comments,
    COALESCE(rc.required_count, 0) AS required_checks,
    COALESCE(rc.successful_count, 0) AS successful_checks,
    CASE
        WHEN pr.state <> 'open'
            THEN FALSE
        WHEN COALESCE(ac.effective_approvals, 0)
             < bp.required_approvals
            THEN FALSE
        WHEN COALESCE(ac.blocking_reviews, 0) > 0
            THEN FALSE
        WHEN bp.require_conversation_resolution
             AND COALESCE(u.unresolved_comments, 0) > 0
            THEN FALSE
        WHEN COALESCE(rc.successful_count, 0)
             <> COALESCE(rc.required_count, 0)
            THEN FALSE
        ELSE TRUE
    END AS eligible_without_bypass
FROM pull_request pr
JOIN repository r
  ON r.repository_id = pr.repository_id
JOIN branch source
  ON source.branch_id = pr.source_branch_id
JOIN branch target
  ON target.branch_id = pr.target_branch_id
JOIN branch_protection_policy bp
  ON bp.branch_id = pr.target_branch_id
LEFT JOIN approval_counts ac
  ON ac.pull_request_id = pr.pull_request_id
LEFT JOIN unresolved u
  ON u.pull_request_id = pr.pull_request_id
LEFT JOIN required_checks rc
  ON rc.pull_request_id = pr.pull_request_id;

-- Retrieval of repository structure.
SELECT
    r.repository_name,
    b.branch_name,
    b.protected
FROM repository r
JOIN branch b
  ON b.repository_id = r.repository_id
ORDER BY b.branch_name;

-- Pull request, review, and automated-check state.
SELECT
    *
FROM merge_eligibility_report
ORDER BY pull_request_number;

-- Review quality: latest effective decision for every reviewer.
WITH ranked_reviews AS (
    SELECT
        r.*,
        row_number() OVER (
            PARTITION BY pull_request_id, reviewer_username
            ORDER BY submitted_at DESC, review_id DESC
        ) AS reviewer_version
    FROM review r
)
SELECT
    pull_request_id,
    reviewer_username,
    review_state,
    submitted_at
FROM ranked_reviews
WHERE reviewer_version = 1
ORDER BY pull_request_id, reviewer_username;

-- Demonstrate an atomic resolution followed by eligibility evaluation.
BEGIN;

UPDATE review_comment
SET resolved = TRUE,
    resolved_at = CURRENT_TIMESTAMP
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM pull_request
    WHERE pull_request_number = 1
)
AND resolved = FALSE;

SELECT
    pull_request_number,
    title,
    effective_approvals,
    required_approvals,
    unresolved_comments,
    successful_checks,
    required_checks,
    eligible_without_bypass
FROM merge_eligibility_report
WHERE pull_request_number = 1;

COMMIT;

-- The merge function locks the PR, validates relational state, and records
-- the merge atomically. This call succeeds because approvals, checks, and
-- conversation state have all been satisfied.
SELECT merge_pull_request(
    (
        SELECT pull_request_id
        FROM pull_request
        WHERE pull_request_number = 1
    ),
    'alice',
    'squash'
);

-- Final workflow state.
SELECT
    pr.pull_request_number,
    pr.state,
    m.merged_by,
    m.strategy,
    m.resulting_commit_hash,
    m.merged_at
FROM pull_request pr
LEFT JOIN merge m
  ON m.pull_request_id = pr.pull_request_id
ORDER BY pr.pull_request_number;

-- Aggregation by repository and workflow state.
SELECT
    r.repository_name,
    pr.state,
    count(*) AS pull_request_count
FROM repository r
JOIN pull_request pr
  ON pr.repository_id = r.repository_id
GROUP BY r.repository_name, pr.state
ORDER BY r.repository_name, pr.state;
