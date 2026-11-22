-- ============================================================
-- CONTAINER REGISTRY MANAGEMENT AND IMAGE DISTRIBUTION
-- PostgreSQL 15+
--
-- Models:
--   1. Registry instances
--   2. Users and registry permissions
--   3. Image repositories
--   4. Content-addressed image manifests
--   5. Image tags and versioning
--   6. Image publication and distribution
--   7. Vulnerability and signature policies
--   8. Repository access control
--   9. Image audit events
--  10. Garbage collection and merge-independent release rules
--
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS container_registry;

SET search_path TO container_registry, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE registry_role AS ENUM (
    'admin',
    'publisher',
    'consumer'
);

CREATE TYPE image_status AS ENUM (
    'available',
    'quarantined',
    'deleted'
);

CREATE TYPE distribution_status AS ENUM (
    'pending',
    'delivered',
    'failed'
);

CREATE TYPE audit_operation AS ENUM (
    'create_repository',
    'push',
    'pull',
    'delete_tag',
    'policy_update',
    'distribute',
    'garbage_collect'
);

-- ============================================================
-- 2. REGISTRY INSTANCES
-- ============================================================

CREATE TABLE registries (
    registry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_name VARCHAR(150) NOT NULL UNIQUE,

    endpoint TEXT NOT NULL UNIQUE,

    private_registry BOOLEAN NOT NULL DEFAULT TRUE,

    maximum_image_size BIGINT NOT NULL DEFAULT 104857600,

    maximum_vulnerabilities INTEGER NOT NULL DEFAULT 0,

    require_signed_images BOOLEAN NOT NULL DEFAULT TRUE,

    allow_immutable_tags BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT positive_image_size
        CHECK (maximum_image_size > 0),

    CONSTRAINT nonnegative_vulnerability_limit
        CHECK (maximum_vulnerabilities >= 0)
);

-- ============================================================
-- 3. USERS AND ACCESS CONTROL
-- ============================================================

CREATE TABLE registry_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    username VARCHAR(100) NOT NULL UNIQUE,

    -- Store a secure credential hash, never plaintext credentials.
    credential_hash TEXT NOT NULL,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE registry_permissions (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_id BIGINT NOT NULL
        REFERENCES registries(registry_id),

    user_id BIGINT NOT NULL
        REFERENCES registry_users(user_id),

    role registry_role NOT NULL,

    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (registry_id, user_id)
);

CREATE INDEX idx_registry_permissions_user
    ON registry_permissions(user_id, registry_id);

-- ============================================================
-- 4. IMAGE REPOSITORIES
-- ============================================================

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_id BIGINT NOT NULL
        REFERENCES registries(registry_id),

    repository_name VARCHAR(255) NOT NULL,

    description TEXT,

    private_repository BOOLEAN NOT NULL DEFAULT TRUE,

    created_by BIGINT NOT NULL
        REFERENCES registry_users(user_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (registry_id, repository_name),

    CHECK (
        repository_name ~
        '^[a-z0-9]+([._-][a-z0-9]+)*(/[a-z0-9]+([._-][a-z0-9]+)*)*$'
    )
);

CREATE INDEX idx_repositories_registry
    ON repositories(registry_id);

-- ============================================================
-- 5. IMAGE MANIFESTS
-- ============================================================

CREATE TABLE image_manifests (
    manifest_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id),

    digest VARCHAR(71) NOT NULL,

    media_type TEXT NOT NULL,

    image_size BIGINT NOT NULL,

    architecture VARCHAR(30) NOT NULL,

    operating_system VARCHAR(30) NOT NULL,

    content_location TEXT,

    signed BOOLEAN NOT NULL DEFAULT FALSE,

    vulnerability_count INTEGER NOT NULL DEFAULT 0,

    status image_status NOT NULL DEFAULT 'available',

    created_by BIGINT NOT NULL
        REFERENCES registry_users(user_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (repository_id, digest),

    CHECK (digest ~ '^sha256:[a-f0-9]{64}$'),

    CHECK (image_size > 0),

    CHECK (vulnerability_count >= 0)
);

CREATE INDEX idx_manifests_digest
    ON image_manifests(digest);

CREATE INDEX idx_manifests_repository_status
    ON image_manifests(repository_id, status);

CREATE INDEX idx_manifests_created_at
    ON image_manifests(created_at);

-- ============================================================
-- 6. IMAGE TAGS AND VERSIONING
-- ============================================================

CREATE TABLE image_tags (
    tag_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT NOT NULL,

    manifest_id BIGINT NOT NULL,

    tag_name VARCHAR(128) NOT NULL,

    immutable BOOLEAN NOT NULL DEFAULT FALSE,

    created_by BIGINT NOT NULL
        REFERENCES registry_users(user_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (repository_id, manifest_id)
        REFERENCES image_manifests(repository_id, manifest_id),

    UNIQUE (repository_id, tag_name),

    CHECK (
        tag_name ~ '^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$'
    )
);

CREATE INDEX idx_image_tags_manifest
    ON image_tags(manifest_id);

CREATE INDEX idx_image_tags_repository
    ON image_tags(repository_id, tag_name);

-- ============================================================
-- 7. IMAGE SIGNATURE ATTESTATIONS
-- ============================================================

CREATE TABLE image_signatures (
    signature_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    manifest_id BIGINT NOT NULL
        REFERENCES image_manifests(manifest_id),

    signer_identity TEXT NOT NULL,

    signature_algorithm VARCHAR(50) NOT NULL,

    signature_value TEXT NOT NULL,

    verified BOOLEAN NOT NULL DEFAULT FALSE,

    signed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (manifest_id, signer_identity)
);

-- ============================================================
-- 8. IMAGE VULNERABILITY SCANS
-- ============================================================

CREATE TABLE vulnerability_scans (
    scan_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    manifest_id BIGINT NOT NULL
        REFERENCES image_manifests(manifest_id),

    scanner_name VARCHAR(100) NOT NULL,

    critical_count INTEGER NOT NULL DEFAULT 0,

    high_count INTEGER NOT NULL DEFAULT 0,

    medium_count INTEGER NOT NULL DEFAULT 0,

    low_count INTEGER NOT NULL DEFAULT 0,

    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    scan_passed BOOLEAN NOT NULL DEFAULT FALSE,

    CHECK (
        critical_count >= 0
        AND high_count >= 0
        AND medium_count >= 0
        AND low_count >= 0
    )
);

CREATE INDEX idx_vulnerability_scans_manifest
    ON vulnerability_scans(manifest_id, scanned_at DESC);

-- ============================================================
-- 9. DISTRIBUTION DESTINATIONS
-- ============================================================

CREATE TABLE distribution_targets (
    target_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_id BIGINT NOT NULL
        REFERENCES registries(registry_id),

    target_name VARCHAR(150) NOT NULL,

    endpoint TEXT NOT NULL,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (registry_id, target_name)
);

CREATE TABLE image_distributions (
    distribution_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    manifest_id BIGINT NOT NULL
        REFERENCES image_manifests(manifest_id),

    target_id BIGINT NOT NULL
        REFERENCES distribution_targets(target_id),

    initiated_by BIGINT NOT NULL
        REFERENCES registry_users(user_id),

    status distribution_status NOT NULL DEFAULT 'pending',

    retry_count INTEGER NOT NULL DEFAULT 0,

    error_message TEXT,

    initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    UNIQUE (manifest_id, target_id),

    CHECK (retry_count >= 0)
);

CREATE INDEX idx_distributions_status
    ON image_distributions(status, initiated_at);

-- ============================================================
-- 10. REGISTRY AUDIT LOG
-- ============================================================

CREATE TABLE registry_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_id BIGINT NOT NULL
        REFERENCES registries(registry_id),

    user_id BIGINT
        REFERENCES registry_users(user_id),

    operation audit_operation NOT NULL,

    repository_id BIGINT
        REFERENCES repositories(repository_id),

    reference TEXT,

    result VARCHAR(30) NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_registry_audit_time
    ON registry_audit(registry_id, occurred_at DESC);

CREATE INDEX idx_registry_audit_user
    ON registry_audit(user_id, occurred_at DESC);

-- ============================================================
-- 11. ACCESS CONTROL FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION has_registry_permission(
    p_registry_id BIGINT,
    p_user_id BIGINT,
    p_required_role registry_role
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM registry_permissions rp
        JOIN registry_users u
            ON u.user_id = rp.user_id
        WHERE rp.registry_id = p_registry_id
          AND rp.user_id = p_user_id
          AND u.active = TRUE
          AND (
              rp.role = 'admin'
              OR rp.role = p_required_role
              OR (
                  p_required_role = 'consumer'
                  AND rp.role = 'publisher'
              )
          )
    );
$$;

-- ============================================================
-- 12. TAG IMMUTABILITY TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_immutable_tag()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.immutable THEN

        IF NEW.manifest_id <> OLD.manifest_id THEN
            RAISE EXCEPTION
                'Immutable tag % cannot point to another manifest.',
                OLD.tag_name;
        END IF;

        IF NOT NEW.immutable THEN
            RAISE EXCEPTION
                'Immutable tag % cannot be made mutable.',
                OLD.tag_name;
        END IF;

    END IF;

    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_immutable_tag
BEFORE UPDATE ON image_tags
FOR EACH ROW
EXECUTE FUNCTION enforce_immutable_tag();

CREATE OR REPLACE FUNCTION prevent_immutable_tag_deletion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.immutable THEN
        RAISE EXCEPTION
            'Immutable tag % cannot be deleted.',
            OLD.tag_name;
    END IF;

    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_prevent_immutable_tag_deletion
BEFORE DELETE ON image_tags
FOR EACH ROW
EXECUTE FUNCTION prevent_immutable_tag_deletion();

-- ============================================================
-- 13. IMAGE POLICY EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_image_policy(
    p_manifest_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_registry_id BIGINT;
    v_registry registries%ROWTYPE;
    v_manifest image_manifests%ROWTYPE;
    v_verified_signature BOOLEAN;
    v_scan_passed BOOLEAN;
BEGIN
    SELECT
        r.registry_id,
        r.maximum_image_size,
        r.maximum_vulnerabilities,
        r.require_signed_images
    INTO
        v_registry_id,
        v_registry.maximum_image_size,
        v_registry.maximum_vulnerabilities,
        v_registry.require_signed_images
    FROM image_manifests m
    JOIN repositories repo
        ON repo.repository_id = m.repository_id
    JOIN registries r
        ON r.registry_id = repo.registry_id
    WHERE m.manifest_id = p_manifest_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Manifest % does not exist.', p_manifest_id;
    END IF;

    SELECT *
    INTO v_manifest
    FROM image_manifests
    WHERE manifest_id = p_manifest_id;

    IF v_manifest.status <> 'available' THEN
        RETURN FALSE;
    END IF;

    IF v_manifest.image_size > v_registry.maximum_image_size THEN
        RETURN FALSE;
    END IF;

    IF v_manifest.vulnerability_count >
       v_registry.maximum_vulnerabilities THEN
        RETURN FALSE;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM image_signatures
        WHERE manifest_id = p_manifest_id
          AND verified = TRUE
    )
    INTO v_verified_signature;

    IF v_registry.require_signed_images
       AND NOT v_verified_signature THEN
        RETURN FALSE;
    END IF;

    -- Require a successful security scan.
    SELECT EXISTS (
        SELECT 1
        FROM vulnerability_scans
        WHERE manifest_id = p_manifest_id
          AND scan_passed = TRUE
    )
    INTO v_scan_passed;

    IF NOT v_scan_passed THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;

-- ============================================================
-- 14. IMAGE PUBLICATION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE publish_image(
    p_registry_id BIGINT,
    p_user_id BIGINT,
    p_repository_name VARCHAR(255),
    p_tag_name VARCHAR(128),
    p_digest VARCHAR(71),
    p_media_type TEXT,
    p_image_size BIGINT,
    p_architecture VARCHAR(30),
    p_os VARCHAR(30),
    p_signed BOOLEAN,
    p_vulnerability_count INTEGER,
    p_immutable BOOLEAN DEFAULT FALSE
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_repository_id BIGINT;
    v_manifest_id BIGINT;
    v_existing_tag image_tags%ROWTYPE;
    v_tag_exists BOOLEAN;
    v_registry registries%ROWTYPE;
BEGIN
    IF NOT has_registry_permission(
        p_registry_id,
        p_user_id,
        'publisher'
    ) THEN
        RAISE EXCEPTION 'User cannot publish images.';
    END IF;

    IF p_digest !~ '^sha256:[a-f0-9]{64}$' THEN
        RAISE EXCEPTION 'Invalid SHA-256 digest format.';
    END IF;

    IF p_tag_name !~ '^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$' THEN
        RAISE EXCEPTION 'Invalid image tag.';
    END IF;

    IF p_image_size <= 0 OR p_vulnerability_count < 0 THEN
        RAISE EXCEPTION 'Invalid image metadata.';
    END IF;

    SELECT *
    INTO v_registry
    FROM registries
    WHERE registry_id = p_registry_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Registry does not exist.';
    END IF;

    IF p_image_size > v_registry.maximum_image_size THEN
        RAISE EXCEPTION 'Image exceeds registry size limit.';
    END IF;

    IF v_registry.require_signed_images AND NOT p_signed THEN
        RAISE EXCEPTION 'Signed image is required.';
    END IF;

    IF p_vulnerability_count >
       v_registry.maximum_vulnerabilities THEN
        RAISE EXCEPTION 'Vulnerability threshold exceeded.';
    END IF;

    SELECT repository_id
    INTO v_repository_id
    FROM repositories
    WHERE registry_id = p_registry_id
      AND repository_name = p_repository_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Repository does not exist.';
    END IF;

    SELECT *
    INTO v_existing_tag
    FROM image_tags
    WHERE repository_id = v_repository_id
      AND tag_name = p_tag_name
    FOR UPDATE;

    v_tag_exists := FOUND;

    IF v_tag_exists AND v_existing_tag.immutable THEN

        IF v_existing_tag.manifest_id NOT IN (
            SELECT manifest_id
            FROM image_manifests
            WHERE repository_id = v_repository_id
              AND digest = p_digest
        ) THEN
            RAISE EXCEPTION
                'Cannot overwrite immutable tag %.',
                p_tag_name;
        END IF;

    END IF;

    INSERT INTO image_manifests (
        repository_id,
        digest,
        media_type,
        image_size,
        architecture,
        operating_system,
        signed,
        vulnerability_count,
        created_by
    )
    VALUES (
        v_repository_id,
        p_digest,
        p_media_type,
        p_image_size,
        p_architecture,
        p_os,
        p_signed,
        p_vulnerability_count,
        p_user_id
    )
    ON CONFLICT (repository_id, digest)
    DO NOTHING;

    SELECT manifest_id
    INTO v_manifest_id
    FROM image_manifests
    WHERE repository_id = v_repository_id
      AND digest = p_digest;

    IF EXISTS (
        SELECT 1
        FROM image_manifests
        WHERE manifest_id = v_manifest_id
          AND status <> 'available'
    ) THEN
        RAISE EXCEPTION 'Manifest is unavailable.';
    END IF;

    IF v_tag_exists THEN

        UPDATE image_tags
        SET manifest_id = v_manifest_id,
            immutable = immutable OR p_immutable,
            created_by = p_user_id
        WHERE tag_id = v_existing_tag.tag_id;

    ELSE

        INSERT INTO image_tags (
            repository_id,
            manifest_id,
            tag_name,
            immutable,
            created_by
        )
        VALUES (
            v_repository_id,
            v_manifest_id,
            p_tag_name,
            p_immutable,
            p_user_id
        );

    END IF;

    INSERT INTO registry_audit (
        registry_id,
        user_id,
        operation,
        repository_id,
        reference,
        result,
        details
    )
    VALUES (
        p_registry_id,
        p_user_id,
        'push',
        v_repository_id,
        p_tag_name,
        'SUCCESS',
        jsonb_build_object(
            'digest', p_digest,
            'size', p_image_size
        )
    );
END;
$$;

-- ============================================================
-- 15. IMAGE DISTRIBUTION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE queue_image_distribution(
    p_user_id BIGINT,
    p_manifest_id BIGINT,
    p_target_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_registry_id BIGINT;
BEGIN
    SELECT repo.registry_id
    INTO v_registry_id
    FROM image_manifests m
    JOIN repositories repo
        ON repo.repository_id = m.repository_id
    WHERE m.manifest_id = p_manifest_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Manifest not found.';
    END IF;

    IF NOT has_registry_permission(
        v_registry_id,
        p_user_id,
        'consumer'
    ) THEN
        RAISE EXCEPTION 'User cannot distribute images.';
    END IF;

    IF NOT evaluate_image_policy(p_manifest_id) THEN
        RAISE EXCEPTION 'Image failed registry distribution policy.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM distribution_targets
        WHERE target_id = p_target_id
          AND registry_id = v_registry_id
          AND active = TRUE
    ) THEN
        RAISE EXCEPTION 'Distribution target is unavailable.';
    END IF;

    INSERT INTO image_distributions (
        manifest_id,
        target_id,
        initiated_by
    )
    VALUES (
        p_manifest_id,
        p_target_id,
        p_user_id
    )
    ON CONFLICT (manifest_id, target_id)
    DO NOTHING;

    INSERT INTO registry_audit (
        registry_id,
        user_id,
        operation,
        reference,
        result,
        details
    )
    VALUES (
        v_registry_id,
        p_user_id,
        'distribute',
        p_manifest_id::TEXT,
        'QUEUED',
        jsonb_build_object(
            'target_id', p_target_id
        )
    );
END;
$$;

-- ============================================================
-- 16. DISTRIBUTION FAILURE AND RETRY MANAGEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION update_distribution_result(
    p_distribution_id BIGINT,
    p_success BOOLEAN,
    p_error TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE image_distributions
    SET status = CASE
            WHEN p_success THEN 'delivered'::distribution_status
            ELSE 'failed'::distribution_status
        END,
        retry_count = CASE
            WHEN p_success THEN retry_count
            ELSE retry_count + 1
        END,
        error_message = CASE
            WHEN p_success THEN NULL
            ELSE p_error
        END,
        completed_at = NOW()
    WHERE distribution_id = p_distribution_id
      AND status <> 'delivered';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Distribution not found or already delivered.';
    END IF;
END;
$$;

-- ============================================================
-- 17. TAG AND MANIFEST RETRIEVAL VIEW
-- ============================================================

CREATE OR REPLACE VIEW repository_image_inventory AS
SELECT
    r.registry_id,
    reg.registry_name,
    r.repository_id,
    r.repository_name,
    t.tag_name,
    t.immutable,
    m.manifest_id,
    m.digest,
    m.media_type,
    m.image_size,
    m.architecture,
    m.operating_system,
    m.signed,
    m.vulnerability_count,
    m.status,
    t.updated_at
FROM repositories r
JOIN registries reg
    ON reg.registry_id = r.registry_id
LEFT JOIN image_tags t
    ON t.repository_id = r.repository_id
LEFT JOIN image_manifests m
    ON m.manifest_id = t.manifest_id;

-- ============================================================
-- 18. REGISTRY SECURITY REPORT
-- ============================================================

CREATE OR REPLACE VIEW image_security_report AS
SELECT
    reg.registry_name,
    repo.repository_name,
    m.digest,
    m.signed,
    m.vulnerability_count,
    m.status,
    COALESCE(scan.critical_count, 0) AS critical_vulnerabilities,
    COALESCE(scan.high_count, 0) AS high_vulnerabilities,
    COALESCE(signature.verified, FALSE) AS signature_verified,
    COALESCE(scan.scan_passed, FALSE) AS scan_passed
FROM image_manifests m
JOIN repositories repo
    ON repo.repository_id = m.repository_id
JOIN registries reg
    ON reg.registry_id = repo.registry_id
LEFT JOIN LATERAL (
    SELECT
        critical_count,
        high_count,
        scan_passed
    FROM vulnerability_scans
    WHERE manifest_id = m.manifest_id
    ORDER BY scanned_at DESC
    LIMIT 1
) scan ON TRUE
LEFT JOIN LATERAL (
    SELECT BOOL_OR(verified) AS verified
    FROM image_signatures
    WHERE manifest_id = m.manifest_id
) signature ON TRUE;

-- ============================================================
-- 19. DISTRIBUTION REPORT
-- ============================================================

CREATE OR REPLACE VIEW distribution_report AS
SELECT
    reg.registry_name,
    repo.repository_name,
    m.digest,
    target.target_name,
    d.status,
    d.retry_count,
    d.error_message,
    d.initiated_at,
    d.completed_at
FROM image_distributions d
JOIN image_manifests m
    ON m.manifest_id = d.manifest_id
JOIN repositories repo
    ON repo.repository_id = m.repository_id
JOIN registries reg
    ON reg.registry_id = repo.registry_id
JOIN distribution_targets target
    ON target.target_id = d.target_id;

-- ============================================================
-- 20. GARBAGE COLLECTION CANDIDATE QUERY
-- ============================================================

CREATE OR REPLACE VIEW unreferenced_manifests AS
SELECT
    m.manifest_id,
    m.repository_id,
    m.digest,
    m.image_size,
    m.created_at
FROM image_manifests m
WHERE NOT EXISTS (
    SELECT 1
    FROM image_tags t
    WHERE t.manifest_id = m.manifest_id
);

-- ============================================================
-- 21. SAMPLE REGISTRY DATA
-- ============================================================

INSERT INTO registries (
    registry_name,
    endpoint,
    private_registry,
    maximum_image_size,
    maximum_vulnerabilities,
    require_signed_images
)
VALUES
(
    'enterprise-registry',
    'https://registry.example.internal',
    TRUE,
    104857600,
    1,
    TRUE
),
(
    'public-registry',
    'https://public.example.internal',
    FALSE,
    52428800,
    5,
    FALSE
);

INSERT INTO registry_users (
    username,
    credential_hash
)
VALUES
('registry-admin', 'sha256$admin-credential-hash'),
('build-service', 'sha256$publisher-credential-hash'),
('deployment-service', 'sha256$consumer-credential-hash'),
('auditor', 'sha256$auditor-credential-hash');

INSERT INTO registry_permissions (
    registry_id,
    user_id,
    role
)
SELECT
    r.registry_id,
    u.user_id,
    permissions.role::registry_role
FROM (
    VALUES
        ('enterprise-registry', 'registry-admin', 'admin'),
        ('enterprise-registry', 'build-service', 'publisher'),
        ('enterprise-registry', 'deployment-service', 'consumer'),
        ('enterprise-registry', 'auditor', 'consumer'),
        ('public-registry', 'registry-admin', 'admin'),
        ('public-registry', 'build-service', 'publisher'),
        ('public-registry', 'deployment-service', 'consumer')
) AS permissions(registry_name, username, role)
JOIN registries r
    ON r.registry_name = permissions.registry_name
JOIN registry_users u
    ON u.username = permissions.username;

INSERT INTO repositories (
    registry_id,
    repository_name,
    description,
    private_repository,
    created_by
)
SELECT
    r.registry_id,
    'production/payment-api',
    'Payment processing container images',
    TRUE,
    u.user_id
FROM registries r
CROSS JOIN registry_users u
WHERE r.registry_name = 'enterprise-registry'
  AND u.username = 'registry-admin';

INSERT INTO repositories (
    registry_id,
    repository_name,
    description,
    private_repository,
    created_by
)
SELECT
    r.registry_id,
    'development/analytics-api',
    'Analytics service development images',
    TRUE,
    u.user_id
FROM registries r
CROSS JOIN registry_users u
WHERE r.registry_name = 'enterprise-registry'
  AND u.username = 'registry-admin';

-- ============================================================
-- 22. SAMPLE IMAGE MANIFESTS
-- ============================================================

INSERT INTO image_manifests (
    repository_id,
    digest,
    media_type,
    image_size,
    architecture,
    operating_system,
    signed,
    vulnerability_count,
    created_by
)
SELECT
    r.repository_id,
    'sha256:' || repeat('a', 64),
    'application/vnd.oci.image.manifest.v1+json',
    12500000,
    'amd64',
    'linux',
    TRUE,
    0,
    u.user_id
FROM repositories r
CROSS JOIN registry_users u
WHERE r.repository_name = 'production/payment-api'
  AND u.username = 'build-service';

INSERT INTO image_manifests (
    repository_id,
    digest,
    media_type,
    image_size,
    architecture,
    operating_system,
    signed,
    vulnerability_count,
    created_by
)
SELECT
    r.repository_id,
    'sha256:' || repeat('b', 64),
    'application/vnd.oci.image.manifest.v1+json',
    15000000,
    'amd64',
    'linux',
    TRUE,
    1,
    u.user_id
FROM repositories r
CROSS JOIN registry_users u
WHERE r.repository_name = 'production/payment-api'
  AND u.username = 'build-service';

-- An unsigned manifest represents a deliberately rejected release candidate.
INSERT INTO image_manifests (
    repository_id,
    digest,
    media_type,
    image_size,
    architecture,
    operating_system,
    signed,
    vulnerability_count,
    created_by
)
SELECT
    r.repository_id,
    'sha256:' || repeat('c', 64),
    'application/vnd.oci.image.manifest.v1+json',
    8000000,
    'amd64',
    'linux',
    FALSE,
    4,
    u.user_id
FROM repositories r
CROSS JOIN registry_users u
WHERE r.repository_name = 'production/payment-api'
  AND u.username = 'build-service';

-- ============================================================
-- 23. SAMPLE TAGS
-- ============================================================

INSERT INTO image_tags (
    repository_id,
    manifest_id,
    tag_name,
    immutable,
    created_by
)
SELECT
    r.repository_id,
    m.manifest_id,
    '1.0.0',
    TRUE,
    u.user_id
FROM repositories r
JOIN image_manifests m
    ON m.repository_id = r.repository_id
JOIN registry_users u
    ON u.username = 'build-service'
WHERE r.repository_name = 'production/payment-api'
  AND m.digest = 'sha256:' || repeat('a', 64);

INSERT INTO image_tags (
    repository_id,
    manifest_id,
    tag_name,
    immutable,
    created_by
)
SELECT
    r.repository_id,
    m.manifest_id,
    'latest',
    FALSE,
    u.user_id
FROM repositories r
JOIN image_manifests m
    ON m.repository_id = r.repository_id
JOIN registry_users u
    ON u.username = 'build-service'
WHERE r.repository_name = 'production/payment-api'
  AND m.digest = 'sha256:' || repeat('b', 64);

-- ============================================================
-- 24. SAMPLE SIGNATURES
-- ============================================================

INSERT INTO image_signatures (
    manifest_id,
    signer_identity,
    signature_algorithm,
    signature_value,
    verified
)
SELECT
    manifest_id,
    'build-system@example.internal',
    'ECDSA-P256',
    'sample-signature-attestation',
    TRUE
FROM image_manifests
WHERE digest = 'sha256:' || repeat('a', 64);

INSERT INTO image_signatures (
    manifest_id,
    signer_identity,
    signature_algorithm,
    signature_value,
    verified
)
SELECT
    manifest_id,
    'build-system@example.internal',
    'ECDSA-P256',
    'sample-signature-attestation-v2',
    TRUE
FROM image_manifests
WHERE digest = 'sha256:' || repeat('b', 64);

-- ============================================================
-- 25. SAMPLE VULNERABILITY SCANS
-- ============================================================

INSERT INTO vulnerability_scans (
    manifest_id,
    scanner_name,
    critical_count,
    high_count,
    medium_count,
    low_count,
    scan_passed
)
SELECT
    manifest_id,
    'enterprise-image-scanner',
    0,
    0,
    0,
    0,
    TRUE
FROM image_manifests
WHERE digest = 'sha256:' || repeat('a', 64);

INSERT INTO vulnerability_scans (
    manifest_id,
    scanner_name,
    critical_count,
    high_count,
    medium_count,
    low_count,
    scan_passed
)
SELECT
    manifest_id,
    'enterprise-image-scanner',
    0,
    1,
    2,
    1,
    TRUE
FROM image_manifests
WHERE digest = 'sha256:' || repeat('b', 64);

-- ============================================================
-- 26. SAMPLE DISTRIBUTION TARGETS
-- ============================================================

INSERT INTO distribution_targets (
    registry_id,
    target_name,
    endpoint
)
SELECT
    registry_id,
    'production-kubernetes',
    'https://cluster.example.internal'
FROM registries
WHERE registry_name = 'enterprise-registry';

INSERT INTO distribution_targets (
    registry_id,
    target_name,
    endpoint
)
SELECT
    registry_id,
    'staging-kubernetes',
    'https://staging.example.internal'
FROM registries
WHERE registry_name = 'enterprise-registry';

COMMIT;

-- ============================================================
-- 27. RETRIEVAL QUERIES
-- ============================================================

-- List repository images and tags.
SELECT *
FROM repository_image_inventory
ORDER BY repository_name, tag_name;

-- Retrieve an image by its immutable digest.
SELECT
    repository_name,
    digest,
    architecture,
    operating_system,
    image_size
FROM repository_image_inventory
WHERE digest = 'sha256:' || repeat('a', 64);

-- ============================================================
-- 28. VERSIONING AND TAG REPORTING
-- ============================================================

SELECT
    repository_name,
    tag_name,
    digest,
    immutable,
    updated_at
FROM repository_image_inventory
WHERE tag_name IS NOT NULL
ORDER BY repository_name, updated_at DESC;

-- Semantic version tags should be compared as versions by an
-- application or a dedicated semantic-version extension.
-- Lexicographical ordering is not semantic version ordering.

-- ============================================================
-- 29. IMAGE SECURITY EVALUATION
-- ============================================================

SELECT
    registry_name,
    repository_name,
    digest,
    signed,
    vulnerability_count,
    signature_verified,
    scan_passed,
    (
        signed
        AND signature_verified
        AND scan_passed
        AND critical_vulnerabilities = 0
    ) AS basic_security_eligible
FROM image_security_report;

-- Full registry policy evaluation for each manifest.
SELECT
    manifest_id,
    digest,
    evaluate_image_policy(manifest_id) AS eligible
FROM image_manifests;

-- ============================================================
-- 30. ACCESS CONTROL VALIDATION
-- ============================================================

SELECT
    u.username,
    rp.role,
    has_registry_permission(
        rp.registry_id,
        u.user_id,
        'publisher'
    ) AS can_publish,
    has_registry_permission(
        rp.registry_id,
        u.user_id,
        'consumer'
    ) AS can_consume
FROM registry_permissions rp
JOIN registry_users u
    ON u.user_id = rp.user_id
ORDER BY u.username;

-- ============================================================
-- 31. AGGREGATION AND STORAGE REPORT
-- ============================================================

SELECT
    r.repository_name,
    COUNT(DISTINCT m.manifest_id) AS manifest_count,
    COUNT(DISTINCT t.tag_id) AS tag_count,
    COALESCE(SUM(m.image_size), 0) AS stored_manifest_bytes,
    COALESCE(AVG(m.image_size), 0)::NUMERIC(15,2)
        AS average_image_size
FROM repositories r
LEFT JOIN image_manifests m
    ON m.repository_id = r.repository_id
LEFT JOIN image_tags t
    ON t.manifest_id = m.manifest_id
GROUP BY r.repository_id, r.repository_name
ORDER BY r.repository_name;

-- ============================================================
-- 32. DISTRIBUTION ELIGIBILITY
-- ============================================================

SELECT
    m.manifest_id,
    m.digest,
    target.target_name,
    target.active,
    m.status,
    evaluate_image_policy(m.manifest_id) AS policy_eligible
FROM image_manifests m
JOIN repositories r
    ON r.repository_id = m.repository_id
JOIN distribution_targets target
    ON target.registry_id = r.registry_id
ORDER BY target.target_name;

-- ============================================================
-- 33. DISTRIBUTION WORKFLOW
-- ============================================================

-- Queue an eligible image for production distribution.
-- Execute as an authorized database application role.

DO $$
DECLARE
    v_user_id BIGINT;
    v_manifest_id BIGINT;
    v_target_id BIGINT;
BEGIN
    SELECT user_id
    INTO v_user_id
    FROM registry_users
    WHERE username = 'deployment-service';

    SELECT m.manifest_id
    INTO v_manifest_id
    FROM image_manifests m
    JOIN repositories r
        ON r.repository_id = m.repository_id
    WHERE r.repository_name = 'production/payment-api'
      AND m.digest = 'sha256:' || repeat('a', 64);

    SELECT target_id
    INTO v_target_id
    FROM distribution_targets
    WHERE target_name = 'production-kubernetes';

    CALL queue_image_distribution(
        v_user_id,
        v_manifest_id,
        v_target_id
    );
END;
$$;

-- ============================================================
-- 34. PROCESS DISTRIBUTION RESULTS
-- ============================================================

-- Mark the first pending distribution as successfully delivered.
DO $$
DECLARE
    v_distribution_id BIGINT;
BEGIN
    SELECT distribution_id
    INTO v_distribution_id
    FROM image_distributions
    WHERE status = 'pending'
    ORDER BY initiated_at
    LIMIT 1;

    IF FOUND THEN
        PERFORM update_distribution_result(
            v_distribution_id,
            TRUE,
            NULL
        );
    END IF;
END;
$$;

SELECT *
FROM distribution_report
ORDER BY initiated_at DESC;

-- ============================================================
-- 35. FAILURE AND RETRY REPORT
-- ============================================================

SELECT
    distribution_id,
    target_id,
    status,
    retry_count,
    error_message
FROM image_distributions
WHERE status = 'failed'
   OR retry_count > 0
ORDER BY initiated_at DESC;

-- ============================================================
-- 36. AUDIT REPORT
-- ============================================================

SELECT
    a.audit_id,
    u.username,
    a.operation,
    r.repository_name,
    a.reference,
    a.result,
    a.details,
    a.occurred_at
FROM registry_audit a
LEFT JOIN registry_users u
    ON u.user_id = a.user_id
LEFT JOIN repositories r
    ON r.repository_id = a.repository_id
ORDER BY a.occurred_at DESC;

-- ============================================================
-- 37. GARBAGE COLLECTION CANDIDATES
-- ============================================================

SELECT
    manifest_id,
    repository_id,
    digest,
    image_size,
    created_at
FROM unreferenced_manifests
ORDER BY created_at;

-- ============================================================
-- 38. SAFE GARBAGE COLLECTION
-- ============================================================

-- Only delete manifests that have no tags or active distributions.
-- Production systems should also check retention windows, active
-- pulls, replication state and external references.

BEGIN;

WITH removable AS (
    SELECT m.manifest_id
    FROM image_manifests m
    WHERE NOT EXISTS (
        SELECT 1
        FROM image_tags t
        WHERE t.manifest_id = m.manifest_id
    )
    AND NOT EXISTS (
        SELECT 1
        FROM image_distributions d
        WHERE d.manifest_id = m.manifest_id
          AND d.status = 'pending'
    )
    FOR UPDATE
)
DELETE FROM image_manifests m
USING removable x
WHERE m.manifest_id = x.manifest_id;

COMMIT;

-- ============================================================
-- 39. FINAL REGISTRY HEALTH REPORT
-- ============================================================

SELECT
    reg.registry_name,
    COUNT(DISTINCT repo.repository_id) AS repository_count,
    COUNT(DISTINCT m.manifest_id) AS manifest_count,
    COUNT(DISTINCT t.tag_id) AS tag_count,
    COUNT(DISTINCT CASE
        WHEN m.status = 'quarantined'
        THEN m.manifest_id
    END) AS quarantined_images,
    COUNT(DISTINCT CASE
        WHEN m.signed = FALSE
        THEN m.manifest_id
    END) AS unsigned_images
FROM registries reg
LEFT JOIN repositories repo
    ON repo.registry_id = reg.registry_id
LEFT JOIN image_manifests m
    ON m.repository_id = repo.repository_id
LEFT JOIN image_tags t
    ON t.manifest_id = m.manifest_id
GROUP BY reg.registry_id, reg.registry_name
ORDER BY reg.registry_name;
