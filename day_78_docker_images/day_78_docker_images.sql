/*
===============================================================================
DOCKER IMAGES: RELATIONAL BUILD AND IMAGE GOVERNANCE SYSTEM
===============================================================================

PostgreSQL 14+

Models:
- Registries
- Repositories
- Base images
- Image layers
- Layer dependencies
- Dockerfiles
- Build contexts
- Build executions
- Build stages
- Image manifests
- Image tags
- Image vulnerabilities
- Build policies
- Optimization findings
- Build cache
- Artifact promotion

The schema separates:
1. Dockerfile source instructions.
2. Build execution records.
3. Immutable layer artifacts.
4. Final image manifests.
5. Repository and registry governance.

Run as a database role with permission to create schemas and functions.
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS docker_platform;

SET search_path TO docker_platform, public;

-- ============================================================================
-- 1. ENUM TYPES
-- ============================================================================

CREATE TYPE instruction_type AS ENUM (
    'FROM',
    'WORKDIR',
    'COPY',
    'ADD',
    'RUN',
    'ENV',
    'ARG',
    'USER',
    'EXPOSE',
    'LABEL',
    'CMD',
    'ENTRYPOINT'
);

CREATE TYPE build_status AS ENUM (
    'PENDING',
    'QUEUED',
    'RUNNING',
    'SUCCEEDED',
    'FAILED',
    'CANCELLED'
);

CREATE TYPE finding_severity AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE policy_status AS ENUM (
    'ACTIVE',
    'INACTIVE'
);

CREATE TYPE promotion_status AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'COMPLETED'
);

-- ============================================================================
-- 2. REGISTRIES
-- ============================================================================

CREATE TABLE registries (
    registry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_name VARCHAR(150) NOT NULL UNIQUE,

    registry_url TEXT NOT NULL UNIQUE,

    registry_type VARCHAR(30) NOT NULL
        CHECK (
            registry_type IN (
                'PRIVATE',
                'PUBLIC',
                'CLOUD',
                'SELF_HOSTED'
            )
        ),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 3. REPOSITORIES
-- ============================================================================

CREATE TABLE image_repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    registry_id BIGINT NOT NULL
        REFERENCES registries(registry_id),

    repository_name VARCHAR(255) NOT NULL,

    owner_name VARCHAR(150) NOT NULL,

    description TEXT,

    visibility VARCHAR(20) NOT NULL DEFAULT 'PRIVATE'
        CHECK (
            visibility IN ('PUBLIC', 'PRIVATE', 'INTERNAL')
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (registry_id, repository_name)
);

CREATE INDEX idx_repositories_owner
ON image_repositories(owner_name);

-- ============================================================================
-- 4. BASE IMAGES
-- ============================================================================

CREATE TABLE base_images (
    base_image_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT
        REFERENCES image_repositories(repository_id),

    image_name VARCHAR(255) NOT NULL,

    image_tag VARCHAR(150) NOT NULL,

    image_digest VARCHAR(255),

    architecture VARCHAR(50) NOT NULL DEFAULT 'linux/amd64',

    operating_system VARCHAR(100),

    image_size_bytes BIGINT NOT NULL
        CHECK (image_size_bytes >= 0),

    is_trusted BOOLEAN NOT NULL DEFAULT FALSE,

    is_deprecated BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (image_name, image_tag, architecture)
);

CREATE INDEX idx_base_images_trust
ON base_images(is_trusted, is_deprecated);

-- ============================================================================
-- 5. DOCKERFILE DEFINITIONS
-- ============================================================================

CREATE TABLE dockerfiles (
    dockerfile_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES image_repositories(repository_id),

    dockerfile_name VARCHAR(255) NOT NULL DEFAULT 'Dockerfile',

    dockerfile_content TEXT NOT NULL,

    content_digest VARCHAR(255) NOT NULL,

    version_number INTEGER NOT NULL DEFAULT 1
        CHECK (version_number > 0),

    build_context_digest VARCHAR(255),

    dockerignore_content TEXT,

    created_by VARCHAR(150) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (
        repository_id,
        dockerfile_name,
        version_number
    )
);

CREATE INDEX idx_dockerfiles_digest
ON dockerfiles(content_digest);

-- ============================================================================
-- 6. DOCKERFILE INSTRUCTIONS
-- ============================================================================

CREATE TABLE dockerfile_instructions (
    instruction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    dockerfile_id BIGINT NOT NULL
        REFERENCES dockerfiles(dockerfile_id)
        ON DELETE CASCADE,

    line_number INTEGER NOT NULL
        CHECK (line_number > 0),

    instruction instruction_type NOT NULL,

    arguments TEXT NOT NULL,

    instruction_digest VARCHAR(255),

    UNIQUE (dockerfile_id, line_number)
);

CREATE INDEX idx_instructions_dockerfile
ON dockerfile_instructions(
    dockerfile_id,
    line_number
);

CREATE INDEX idx_instructions_type
ON dockerfile_instructions(instruction);

-- ============================================================================
-- 7. BUILD EXECUTIONS
-- ============================================================================

CREATE TABLE image_builds (
    build_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    dockerfile_id BIGINT NOT NULL
        REFERENCES dockerfiles(dockerfile_id),

    build_number INTEGER NOT NULL
        CHECK (build_number > 0),

    build_status build_status NOT NULL DEFAULT 'PENDING',

    builder_name VARCHAR(150) NOT NULL,

    build_platform VARCHAR(100) NOT NULL DEFAULT 'linux/amd64',

    cache_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    duration_ms BIGINT
        CHECK (duration_ms IS NULL OR duration_ms >= 0),

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (dockerfile_id, build_number),

    CHECK (
        completed_at IS NULL
        OR started_at IS NULL
        OR completed_at >= started_at
    ),

    CHECK (
        build_status NOT IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
        OR completed_at IS NOT NULL
    )
);

CREATE INDEX idx_build_status_created
ON image_builds(build_status, created_at DESC);

CREATE INDEX idx_build_dockerfile
ON image_builds(dockerfile_id, build_number DESC);

-- ============================================================================
-- 8. BUILD STAGES
-- ============================================================================

CREATE TABLE build_stages (
    stage_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    build_id BIGINT NOT NULL
        REFERENCES image_builds(build_id)
        ON DELETE CASCADE,

    stage_name VARCHAR(100) NOT NULL,

    stage_order INTEGER NOT NULL
        CHECK (stage_order > 0),

    base_image_id BIGINT
        REFERENCES base_images(base_image_id),

    is_final_stage BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (build_id, stage_name),

    UNIQUE (build_id, stage_order)
);

CREATE INDEX idx_build_stages_build
ON build_stages(build_id, stage_order);

-- ============================================================================
-- 9. IMMUTABLE IMAGE LAYERS
-- ============================================================================

CREATE TABLE image_layers (
    layer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    layer_digest VARCHAR(255) NOT NULL UNIQUE,

    instruction_digest VARCHAR(255) NOT NULL,

    layer_size_bytes BIGINT NOT NULL
        CHECK (layer_size_bytes >= 0),

    compression_format VARCHAR(30) NOT NULL DEFAULT 'gzip'
        CHECK (
            compression_format IN (
                'gzip',
                'zstd',
                'none'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_image_layers_instruction
ON image_layers(instruction_digest);

CREATE INDEX idx_image_layers_size
ON image_layers(layer_size_bytes DESC);

-- ============================================================================
-- 10. LAYER DEPENDENCIES
-- ============================================================================

CREATE TABLE layer_dependencies (
    dependency_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    parent_layer_id BIGINT NOT NULL
        REFERENCES image_layers(layer_id),

    child_layer_id BIGINT NOT NULL
        REFERENCES image_layers(layer_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (parent_layer_id <> child_layer_id),

    UNIQUE (parent_layer_id, child_layer_id)
);

CREATE INDEX idx_layer_dependencies_parent
ON layer_dependencies(parent_layer_id);

CREATE INDEX idx_layer_dependencies_child
ON layer_dependencies(child_layer_id);

-- ============================================================================
-- 11. BUILD LAYER EXECUTION RECORDS
-- ============================================================================

CREATE TABLE build_layer_results (
    build_layer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    build_id BIGINT NOT NULL
        REFERENCES image_builds(build_id)
        ON DELETE CASCADE,

    stage_id BIGINT
        REFERENCES build_stages(stage_id),

    instruction_id BIGINT
        REFERENCES dockerfile_instructions(instruction_id),

    layer_id BIGINT NOT NULL
        REFERENCES image_layers(layer_id),

    layer_order INTEGER NOT NULL
        CHECK (layer_order > 0),

    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,

    execution_duration_ms BIGINT
        CHECK (
            execution_duration_ms IS NULL
            OR execution_duration_ms >= 0
        ),

    UNIQUE (build_id, stage_id, layer_order)
);

CREATE INDEX idx_build_layer_results_build
ON build_layer_results(build_id, layer_order);

CREATE INDEX idx_build_layer_cache
ON build_layer_results(cache_hit);

-- ============================================================================
-- 12. IMAGE MANIFESTS
-- ============================================================================

CREATE TABLE image_manifests (
    manifest_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    build_id BIGINT NOT NULL UNIQUE
        REFERENCES image_builds(build_id),

    repository_id BIGINT NOT NULL
        REFERENCES image_repositories(repository_id),

    manifest_digest VARCHAR(255) NOT NULL UNIQUE,

    image_size_bytes BIGINT NOT NULL
        CHECK (image_size_bytes >= 0),

    architecture VARCHAR(50) NOT NULL,

    operating_system VARCHAR(100) NOT NULL DEFAULT 'linux',

    layer_count INTEGER NOT NULL
        CHECK (layer_count >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_manifest_repository_created
ON image_manifests(repository_id, created_at DESC);

CREATE INDEX idx_manifest_size
ON image_manifests(image_size_bytes DESC);

-- ============================================================================
-- 13. IMAGE TAGS
-- ============================================================================

CREATE TABLE image_tags (
    tag_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    manifest_id BIGINT NOT NULL
        REFERENCES image_manifests(manifest_id),

    repository_id BIGINT NOT NULL
        REFERENCES image_repositories(repository_id),

    tag_name VARCHAR(150) NOT NULL,

    is_production BOOLEAN NOT NULL DEFAULT FALSE,

    is_mutable BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (repository_id, tag_name)
);

CREATE INDEX idx_image_tags_production
ON image_tags(repository_id, is_production);

-- ============================================================================
-- 14. SECURITY SCANNING
-- ============================================================================

CREATE TABLE image_vulnerabilities (
    vulnerability_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    manifest_id BIGINT NOT NULL
        REFERENCES image_manifests(manifest_id)
        ON DELETE CASCADE,

    vulnerability_code VARCHAR(100) NOT NULL,

    package_name VARCHAR(255) NOT NULL,

    installed_version VARCHAR(100),

    fixed_version VARCHAR(100),

    severity finding_severity NOT NULL,

    description TEXT,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (
        manifest_id,
        vulnerability_code,
        package_name
    )
);

CREATE INDEX idx_vulnerabilities_severity
ON image_vulnerabilities(
    severity,
    is_resolved
);

CREATE INDEX idx_vulnerabilities_manifest
ON image_vulnerabilities(manifest_id);

-- ============================================================================
-- 15. IMAGE OPTIMIZATION FINDINGS
-- ============================================================================

CREATE TABLE optimization_findings (
    finding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    build_id BIGINT NOT NULL
        REFERENCES image_builds(build_id)
        ON DELETE CASCADE,

    finding_code VARCHAR(100) NOT NULL,

    severity finding_severity NOT NULL,

    description TEXT NOT NULL,

    recommendation TEXT NOT NULL,

    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_optimization_findings
ON optimization_findings(
    build_id,
    severity,
    is_resolved
);

-- ============================================================================
-- 16. BUILD POLICIES
-- ============================================================================

CREATE TABLE image_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(150) NOT NULL UNIQUE,

    maximum_size_bytes BIGINT
        CHECK (
            maximum_size_bytes IS NULL
            OR maximum_size_bytes > 0
        ),

    maximum_layers INTEGER
        CHECK (
            maximum_layers IS NULL
            OR maximum_layers > 0
        ),

    require_non_root BOOLEAN NOT NULL DEFAULT TRUE,

    require_pinned_base BOOLEAN NOT NULL DEFAULT TRUE,

    require_vulnerability_scan BOOLEAN NOT NULL DEFAULT TRUE,

    maximum_critical_vulnerabilities INTEGER NOT NULL DEFAULT 0
        CHECK (maximum_critical_vulnerabilities >= 0),

    policy_status policy_status NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 17. BUILD POLICY ASSIGNMENTS
-- ============================================================================

CREATE TABLE repository_policy_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    repository_id BIGINT NOT NULL
        REFERENCES image_repositories(repository_id),

    policy_id BIGINT NOT NULL
        REFERENCES image_policies(policy_id),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (repository_id, policy_id)
);

-- ============================================================================
-- 18. BUILD POLICY EVALUATIONS
-- ============================================================================

CREATE TABLE policy_evaluations (
    evaluation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    build_id BIGINT NOT NULL
        REFERENCES image_builds(build_id),

    policy_id BIGINT NOT NULL
        REFERENCES image_policies(policy_id),

    is_eligible BOOLEAN NOT NULL,

    failed_rules JSONB NOT NULL DEFAULT '[]'::jsonb,

    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (build_id, policy_id),

    CHECK (jsonb_typeof(failed_rules) = 'array')
);

CREATE INDEX idx_policy_evaluations_result
ON policy_evaluations(is_eligible, evaluated_at DESC);

-- ============================================================================
-- 19. ARTIFACT PROMOTION
-- ============================================================================

CREATE TABLE image_promotions (
    promotion_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    manifest_id BIGINT NOT NULL
        REFERENCES image_manifests(manifest_id),

    source_environment VARCHAR(50) NOT NULL,

    target_environment VARCHAR(50) NOT NULL,

    requested_by VARCHAR(150) NOT NULL,

    approved_by VARCHAR(150),

    promotion_status promotion_status NOT NULL DEFAULT 'PENDING',

    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ,

    CHECK (source_environment <> target_environment),

    CHECK (
        promotion_status <> 'COMPLETED'
        OR (
            approved_by IS NOT NULL
            AND completed_at IS NOT NULL
        )
    )
);

CREATE INDEX idx_promotions_status
ON image_promotions(promotion_status, requested_at DESC);

-- ============================================================================
-- 20. BUILD STATUS TRANSITION TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_build_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.build_status = NEW.build_status THEN
        RETURN NEW;
    END IF;

    IF OLD.build_status = 'PENDING'
       AND NEW.build_status NOT IN ('QUEUED', 'RUNNING', 'CANCELLED') THEN

        RAISE EXCEPTION
            'Invalid build transition: PENDING -> %',
            NEW.build_status;
    END IF;

    IF OLD.build_status = 'QUEUED'
       AND NEW.build_status NOT IN ('RUNNING', 'CANCELLED', 'FAILED') THEN

        RAISE EXCEPTION
            'Invalid build transition: QUEUED -> %',
            NEW.build_status;
    END IF;

    IF OLD.build_status = 'RUNNING'
       AND NEW.build_status NOT IN ('SUCCEEDED', 'FAILED', 'CANCELLED') THEN

        RAISE EXCEPTION
            'Invalid build transition: RUNNING -> %',
            NEW.build_status;
    END IF;

    IF OLD.build_status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') THEN
        RAISE EXCEPTION
            'Terminal build states cannot be changed.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_build_transition
BEFORE UPDATE OF build_status
ON image_builds
FOR EACH ROW
EXECUTE FUNCTION validate_build_transition();

-- ============================================================================
-- 21. BUILD TIMESTAMP MANAGEMENT
-- ============================================================================

CREATE OR REPLACE FUNCTION manage_build_timestamps()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.build_status = 'RUNNING'
       AND NEW.started_at IS NULL THEN

        NEW.started_at := CURRENT_TIMESTAMP;
    END IF;

    IF NEW.build_status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') THEN

        IF NEW.started_at IS NULL THEN
            RAISE EXCEPTION
                'A build must have a start timestamp before completion.';
        END IF;

        NEW.completed_at := CURRENT_TIMESTAMP;

        NEW.duration_ms := GREATEST(
            0,
            (
                EXTRACT(
                    EPOCH FROM (
                        NEW.completed_at - NEW.started_at
                    )
                ) * 1000
            )::BIGINT
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_manage_build_timestamps
BEFORE UPDATE OF build_status
ON image_builds
FOR EACH ROW
EXECUTE FUNCTION manage_build_timestamps();

-- ============================================================================
-- 22. LAYER IMMUTABILITY
-- ============================================================================

CREATE OR REPLACE FUNCTION prevent_layer_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Image layers are immutable. Create a new layer instead.';
END;
$$;

CREATE TRIGGER trg_prevent_layer_update
BEFORE UPDATE OR DELETE
ON image_layers
FOR EACH ROW
EXECUTE FUNCTION prevent_layer_mutation();

-- ============================================================================
-- 23. BUILD VALIDATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_dockerfile(
    p_dockerfile_id BIGINT
)
RETURNS TABLE (
    check_name TEXT,
    is_valid BOOLEAN,
    details TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_instruction_count INTEGER;
    v_first_instruction instruction_type;
    v_user_count INTEGER;
BEGIN

    SELECT COUNT(*)
    INTO v_instruction_count
    FROM dockerfile_instructions
    WHERE dockerfile_id = p_dockerfile_id;

    check_name := 'INSTRUCTION_COUNT';
    is_valid := v_instruction_count > 0;
    details := 'Number of instructions: '
               || v_instruction_count::TEXT;

    RETURN NEXT;

    SELECT instruction
    INTO v_first_instruction
    FROM dockerfile_instructions
    WHERE dockerfile_id = p_dockerfile_id
    ORDER BY line_number
    LIMIT 1;

    check_name := 'FIRST_INSTRUCTION_FROM';
    is_valid := v_first_instruction = 'FROM';
    details := 'The first instruction must be FROM.';

    RETURN NEXT;

    SELECT COUNT(*)
    INTO v_user_count
    FROM dockerfile_instructions
    WHERE dockerfile_id = p_dockerfile_id
      AND instruction = 'USER'
      AND LOWER(arguments) NOT IN ('root', '0');

    check_name := 'NON_ROOT_USER';
    is_valid := v_user_count > 0;
    details := 'At least one non-root USER instruction is expected.';

    RETURN NEXT;

    check_name := 'BASE_IMAGE_DECLARED';
    is_valid := EXISTS (
        SELECT 1
        FROM dockerfile_instructions
        WHERE dockerfile_id = p_dockerfile_id
          AND instruction = 'FROM'
    );

    details := 'A base image must be declared.';

    RETURN NEXT;

END;
$$;

-- ============================================================================
-- 24. BUILD CACHE STATISTICS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_build_cache_statistics AS
SELECT
    build_id,

    COUNT(*) AS total_layers,

    COUNT(*) FILTER (
        WHERE cache_hit
    ) AS cached_layers,

    COUNT(*) FILTER (
        WHERE NOT cache_hit
    ) AS newly_created_layers,

    ROUND(
        100.0 * COUNT(*) FILTER (WHERE cache_hit)
        / NULLIF(COUNT(*), 0),
        2
    ) AS cache_hit_percentage

FROM build_layer_results
GROUP BY build_id;

-- ============================================================================
-- 25. IMAGE SIZE REPORT VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_image_size_report AS
SELECT
    m.manifest_id,

    r.repository_name,

    m.manifest_digest,

    m.image_size_bytes,

    ROUND(
        m.image_size_bytes / 1048576.0,
        2
    ) AS image_size_mb,

    m.layer_count,

    m.architecture,

    m.created_at

FROM image_manifests m

JOIN image_repositories r
    ON r.repository_id = m.repository_id;

-- ============================================================================
-- 26. VULNERABILITY REPORT VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_vulnerability_report AS
SELECT
    m.manifest_id,

    r.repository_name,

    v.vulnerability_code,

    v.package_name,

    v.installed_version,

    v.fixed_version,

    v.severity,

    v.is_resolved

FROM image_vulnerabilities v

JOIN image_manifests m
    ON m.manifest_id = v.manifest_id

JOIN image_repositories r
    ON r.repository_id = m.repository_id;

-- ============================================================================
-- 27. IMAGE POLICY EVALUATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION evaluate_image_policy(
    p_manifest_id BIGINT,
    p_policy_id BIGINT
)
RETURNS TABLE (
    is_eligible BOOLEAN,
    failed_rules JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_manifest image_manifests%ROWTYPE;
    v_policy image_policies%ROWTYPE;

    v_non_root BOOLEAN;
    v_pinned BOOLEAN;
    v_critical_count INTEGER;
    v_failed JSONB := '[]'::jsonb;
BEGIN

    SELECT *
    INTO v_manifest
    FROM image_manifests
    WHERE manifest_id = p_manifest_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Manifest % does not exist.',
            p_manifest_id;
    END IF;

    SELECT *
    INTO v_policy
    FROM image_policies
    WHERE policy_id = p_policy_id
      AND policy_status = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active policy % does not exist.',
            p_policy_id;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM dockerfile_instructions di
        JOIN image_builds b
            ON b.dockerfile_id = di.dockerfile_id
        WHERE b.build_id = v_manifest.build_id
          AND di.instruction = 'USER'
          AND LOWER(di.arguments) NOT IN ('root', '0')
    )
    INTO v_non_root;

    IF v_policy.require_non_root AND NOT v_non_root THEN
        v_failed := v_failed || jsonb_build_array(
            jsonb_build_object(
                'rule', 'NON_ROOT_USER',
                'severity', 'HIGH'
            )
        );
    END IF;

    SELECT NOT EXISTS (
        SELECT 1
        FROM dockerfile_instructions di
        JOIN image_builds b
            ON b.dockerfile_id = di.dockerfile_id
        WHERE b.build_id = v_manifest.build_id
          AND di.instruction = 'FROM'
          AND di.arguments ~ '(^|[[:space:]])[^[:space:]]+:latest'
    )
    INTO v_pinned;

    IF v_policy.require_pinned_base AND NOT v_pinned THEN
        v_failed := v_failed || jsonb_build_array(
            jsonb_build_object(
                'rule', 'PINNED_BASE_IMAGE',
                'severity', 'MEDIUM'
            )
        );
    END IF;

    IF v_policy.maximum_size_bytes IS NOT NULL
       AND v_manifest.image_size_bytes > v_policy.maximum_size_bytes THEN

        v_failed := v_failed || jsonb_build_array(
            jsonb_build_object(
                'rule', 'MAXIMUM_IMAGE_SIZE',
                'actual_bytes', v_manifest.image_size_bytes,
                'maximum_bytes', v_policy.maximum_size_bytes
            )
        );
    END IF;

    IF v_policy.maximum_layers IS NOT NULL
       AND v_manifest.layer_count > v_policy.maximum_layers THEN

        v_failed := v_failed || jsonb_build_array(
            jsonb_build_object(
                'rule', 'MAXIMUM_LAYERS',
                'actual', v_manifest.layer_count,
                'maximum', v_policy.maximum_layers
            )
        );
    END IF;

    SELECT COUNT(*)
    INTO v_critical_count
    FROM image_vulnerabilities
    WHERE manifest_id = p_manifest_id
      AND severity = 'CRITICAL'
      AND NOT is_resolved;

    IF v_critical_count >
       v_policy.maximum_critical_vulnerabilities THEN

        v_failed := v_failed || jsonb_build_array(
            jsonb_build_object(
                'rule', 'CRITICAL_VULNERABILITIES',
                'actual', v_critical_count,
                'maximum',
                v_policy.maximum_critical_vulnerabilities
            )
        );
    END IF;

    is_eligible := jsonb_array_length(v_failed) = 0;
    failed_rules := v_failed;

    RETURN NEXT;

END;
$$;

-- ============================================================================
-- 28. PROMOTION APPROVAL FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION approve_image_promotion(
    p_promotion_id BIGINT,
    p_approver VARCHAR(150)
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_status promotion_status;
BEGIN

    IF p_approver IS NULL OR LENGTH(TRIM(p_approver)) = 0 THEN
        RAISE EXCEPTION
            'Approver identity is required.';
    END IF;

    SELECT promotion_status
    INTO v_status
    FROM image_promotions
    WHERE promotion_id = p_promotion_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Promotion does not exist.';
    END IF;

    IF v_status <> 'PENDING' THEN
        RAISE EXCEPTION
            'Only pending promotions can be approved.';
    END IF;

    UPDATE image_promotions
    SET
        promotion_status = 'APPROVED',
        approved_by = p_approver
    WHERE promotion_id = p_promotion_id;

END;
$$;

-- ============================================================================
-- 29. SAMPLE REGISTRIES
-- ============================================================================

INSERT INTO registries (
    registry_name,
    registry_url,
    registry_type
)
VALUES
(
    'Internal Registry',
    'https://registry.internal.example',
    'PRIVATE'
),
(
    'Public Registry',
    'https://registry.public.example',
    'PUBLIC'
);

-- ============================================================================
-- 30. SAMPLE REPOSITORIES
-- ============================================================================

INSERT INTO image_repositories (
    registry_id,
    repository_name,
    owner_name,
    description,
    visibility
)
SELECT
    registry_id,
    'enterprise-api',
    'platform-engineering',
    'Enterprise API container images',
    'PRIVATE'
FROM registries
WHERE registry_name = 'Internal Registry';

INSERT INTO image_repositories (
    registry_id,
    repository_name,
    owner_name,
    description,
    visibility
)
SELECT
    registry_id,
    'base-images',
    'platform-engineering',
    'Approved base image collection',
    'INTERNAL'
FROM registries
WHERE registry_name = 'Internal Registry';

-- ============================================================================
-- 31. SAMPLE BASE IMAGES
-- ============================================================================

INSERT INTO base_images (
    repository_id,
    image_name,
    image_tag,
    image_digest,
    architecture,
    operating_system,
    image_size_bytes,
    is_trusted
)
SELECT
    repository_id,
    'python',
    '3.13-slim',
    'sha256:python313approved',
    'linux/amd64',
    'Debian',
    45 * 1048576,
    TRUE
FROM image_repositories
WHERE repository_name = 'base-images';

INSERT INTO base_images (
    repository_id,
    image_name,
    image_tag,
    image_digest,
    architecture,
    operating_system,
    image_size_bytes,
    is_trusted
)
SELECT
    repository_id,
    'alpine',
    '3.21',
    'sha256:alpine321approved',
    'linux/amd64',
    'Alpine Linux',
    8 * 1048576,
    TRUE
FROM image_repositories
WHERE repository_name = 'base-images';

-- ============================================================================
-- 32. SAMPLE DOCKERFILE
-- ============================================================================

INSERT INTO dockerfiles (
    repository_id,
    dockerfile_name,
    dockerfile_content,
    content_digest,
    version_number,
    build_context_digest,
    created_by
)
SELECT
    repository_id,
    'Dockerfile',
    E'FROM python:3.13-slim\n'
    || E'WORKDIR /app\n'
    || E'COPY requirements.txt .\n'
    || E'RUN pip install -r requirements.txt\n'
    || E'COPY app.py .\n'
    || E'ENV APP_ENV=production\n'
    || E'EXPOSE 8000\n'
    || E'USER 10001\n'
    || E'CMD python app.py',
    'sha256:dockerfile001',
    1,
    'sha256:context001',
    'platform-engineering'
FROM image_repositories
WHERE repository_name = 'enterprise-api';

-- ============================================================================
-- 33. SAMPLE INSTRUCTIONS
-- ============================================================================

INSERT INTO dockerfile_instructions (
    dockerfile_id,
    line_number,
    instruction,
    arguments
)
SELECT
    dockerfile_id,
    sample.line_number,
    sample.instruction,
    sample.arguments
FROM dockerfiles d
CROSS JOIN (
    VALUES
        (1, 'FROM'::instruction_type, 'python:3.13-slim'),
        (2, 'WORKDIR'::instruction_type, '/app'),
        (3, 'COPY'::instruction_type, 'requirements.txt .'),
        (4, 'RUN'::instruction_type, 'pip install -r requirements.txt'),
        (5, 'COPY'::instruction_type, 'app.py .'),
        (6, 'ENV'::instruction_type, 'APP_ENV=production'),
        (7, 'EXPOSE'::instruction_type, '8000'),
        (8, 'USER'::instruction_type, '10001'),
        (9, 'CMD'::instruction_type, 'python app.py')
) AS sample(line_number, instruction, arguments)
WHERE d.content_digest = 'sha256:dockerfile001';

-- ============================================================================
-- 34. SAMPLE BUILD
-- ============================================================================

INSERT INTO image_builds (
    dockerfile_id,
    build_number,
    build_status,
    builder_name,
    build_platform,
    cache_enabled
)
SELECT
    dockerfile_id,
    1,
    'PENDING',
    'build-agent-01',
    'linux/amd64',
    TRUE
FROM dockerfiles
WHERE content_digest = 'sha256:dockerfile001';

-- ============================================================================
-- 35. BUILD LIFECYCLE
-- ============================================================================

UPDATE image_builds
SET build_status = 'QUEUED'
WHERE build_number = 1
  AND build_status = 'PENDING';

UPDATE image_builds
SET build_status = 'RUNNING'
WHERE build_number = 1
  AND build_status = 'QUEUED';

-- ============================================================================
-- 36. SAMPLE BUILD STAGE
-- ============================================================================

INSERT INTO build_stages (
    build_id,
    stage_name,
    stage_order,
    base_image_id,
    is_final_stage
)
SELECT
    b.build_id,
    'runtime',
    1,
    bi.base_image_id,
    TRUE
FROM image_builds b
JOIN dockerfiles d
    ON d.dockerfile_id = b.dockerfile_id
JOIN base_images bi
    ON bi.image_name = 'python'
   AND bi.image_tag = '3.13-slim'
WHERE d.content_digest = 'sha256:dockerfile001';

-- ============================================================================
-- 37. SAMPLE IMAGE LAYERS
-- ============================================================================

INSERT INTO image_layers (
    layer_digest,
    instruction_digest,
    layer_size_bytes,
    compression_format
)
VALUES
(
    'sha256:layer001',
    'sha256:instruction001',
    45 * 1048576,
    'gzip'
),
(
    'sha256:layer002',
    'sha256:instruction002',
    0,
    'gzip'
),
(
    'sha256:layer003',
    'sha256:instruction003',
    1024,
    'gzip'
),
(
    'sha256:layer004',
    'sha256:instruction004',
    15 * 1048576,
    'gzip'
),
(
    'sha256:layer005',
    'sha256:instruction005',
    2048,
    'gzip'
),
(
    'sha256:layer006',
    'sha256:instruction006',
    0,
    'gzip'
),
(
    'sha256:layer007',
    'sha256:instruction007',
    0,
    'gzip'
),
(
    'sha256:layer008',
    'sha256:instruction008',
    0,
    'gzip'
),
(
    'sha256:layer009',
    'sha256:instruction009',
    0,
    'gzip'
);

-- ============================================================================
-- 38. LAYER DEPENDENCY CHAIN
-- ============================================================================

INSERT INTO layer_dependencies (
    parent_layer_id,
    child_layer_id
)
SELECT
    parent.layer_id,
    child.layer_id
FROM image_layers parent
JOIN image_layers child
    ON child.layer_digest = CASE parent.layer_digest
        WHEN 'sha256:layer001' THEN 'sha256:layer002'
        WHEN 'sha256:layer002' THEN 'sha256:layer003'
        WHEN 'sha256:layer003' THEN 'sha256:layer004'
        WHEN 'sha256:layer004' THEN 'sha256:layer005'
        WHEN 'sha256:layer005' THEN 'sha256:layer006'
        WHEN 'sha256:layer006' THEN 'sha256:layer007'
        WHEN 'sha256:layer007' THEN 'sha256:layer008'
        WHEN 'sha256:layer008' THEN 'sha256:layer009'
    END
WHERE parent.layer_digest IN (
    'sha256:layer001',
    'sha256:layer002',
    'sha256:layer003',
    'sha256:layer004',
    'sha256:layer005',
    'sha256:layer006',
    'sha256:layer007',
    'sha256:layer008'
);

-- ============================================================================
-- 39. ASSIGN LAYERS TO BUILD
-- ============================================================================

INSERT INTO build_layer_results (
    build_id,
    stage_id,
    instruction_id,
    layer_id,
    layer_order,
    cache_hit,
    execution_duration_ms
)
SELECT
    b.build_id,
    s.stage_id,
    di.instruction_id,
    l.layer_id,
    di.line_number,
    di.line_number IN (1, 2, 6, 7, 8, 9),
    20 + di.line_number * 10
FROM image_builds b
JOIN dockerfiles d
    ON d.dockerfile_id = b.dockerfile_id
JOIN build_stages s
    ON s.build_id = b.build_id
JOIN dockerfile_instructions di
    ON di.dockerfile_id = d.dockerfile_id
JOIN image_layers l
    ON l.layer_digest = (
        'sha256:layer'
        || LPAD(di.line_number::TEXT, 3, '0')
    )
WHERE d.content_digest = 'sha256:dockerfile001';

-- ============================================================================
-- 40. COMPLETE BUILD
-- ============================================================================

UPDATE image_builds
SET build_status = 'SUCCEEDED'
WHERE build_number = 1
  AND build_status = 'RUNNING';

-- ============================================================================
-- 41. IMAGE MANIFEST
-- ============================================================================

INSERT INTO image_manifests (
    build_id,
    repository_id,
    manifest_digest,
    image_size_bytes,
    architecture,
    operating_system,
    layer_count
)
SELECT
    b.build_id,
    d.repository_id,
    'sha256:manifest001',
    SUM(l.layer_size_bytes),
    'linux/amd64',
    'linux',
    COUNT(l.layer_id)
FROM image_builds b
JOIN dockerfiles d
    ON d.dockerfile_id = b.dockerfile_id
JOIN build_layer_results bl
    ON bl.build_id = b.build_id
JOIN image_layers l
    ON l.layer_id = bl.layer_id
WHERE d.content_digest = 'sha256:dockerfile001'
GROUP BY
    b.build_id,
    d.repository_id;

-- ============================================================================
-- 42. IMAGE TAG
-- ============================================================================

INSERT INTO image_tags (
    manifest_id,
    repository_id,
    tag_name,
    is_production,
    is_mutable
)
SELECT
    m.manifest_id,
    m.repository_id,
    '1.0.0',
    FALSE,
    TRUE
FROM image_manifests m
WHERE m.manifest_digest = 'sha256:manifest001';

-- ============================================================================
-- 43. SECURITY POLICY
-- ============================================================================

INSERT INTO image_policies (
    policy_name,
    maximum_size_bytes,
    maximum_layers,
    require_non_root,
    require_pinned_base,
    require_vulnerability_scan,
    maximum_critical_vulnerabilities
)
VALUES
(
    'Production Image Policy',
    150 * 1048576,
    15,
    TRUE,
    TRUE,
    TRUE,
    0
),
(
    'Development Image Policy',
    500 * 1048576,
    30,
    FALSE,
    FALSE,
    FALSE,
    5
);

INSERT INTO repository_policy_assignments (
    repository_id,
    policy_id
)
SELECT
    r.repository_id,
    p.policy_id
FROM image_repositories r
CROSS JOIN image_policies p
WHERE r.repository_name = 'enterprise-api'
  AND p.policy_name = 'Production Image Policy';

-- ============================================================================
-- 44. SAMPLE VULNERABILITY
-- ============================================================================

INSERT INTO image_vulnerabilities (
    manifest_id,
    vulnerability_code,
    package_name,
    installed_version,
    fixed_version,
    severity,
    description
)
SELECT
    manifest_id,
    'CVE-DEMO-2026-001',
    'example-system-library',
    '1.0.0',
    '1.0.1',
    'MEDIUM',
    'Demonstration vulnerability record.'
FROM image_manifests
WHERE manifest_digest = 'sha256:manifest001';

-- ============================================================================
-- 45. OPTIMIZATION FINDINGS
-- ============================================================================

INSERT INTO optimization_findings (
    build_id,
    finding_code,
    severity,
    description,
    recommendation
)
SELECT
    build_id,
    'DEPENDENCY_LAYER_ORDER',
    'LOW',
    'Dependency installation occurs before application source copying.',
    'This ordering improves dependency-layer cache reuse.'
FROM image_builds
WHERE build_number = 1;

-- ============================================================================
-- 46. POLICY EVALUATION
-- ============================================================================

INSERT INTO policy_evaluations (
    build_id,
    policy_id,
    is_eligible,
    failed_rules
)
SELECT
    m.build_id,
    p.policy_id,
    result.is_eligible,
    result.failed_rules
FROM image_manifests m
JOIN repository_policy_assignments assignment
    ON assignment.repository_id = m.repository_id
JOIN image_policies p
    ON p.policy_id = assignment.policy_id
CROSS JOIN LATERAL evaluate_image_policy(
    m.manifest_id,
    p.policy_id
) result
WHERE m.manifest_digest = 'sha256:manifest001';

-- ============================================================================
-- 47. SAMPLE PROMOTION REQUEST
-- ============================================================================

INSERT INTO image_promotions (
    manifest_id,
    source_environment,
    target_environment,
    requested_by,
    promotion_status
)
SELECT
    manifest_id,
    'STAGING',
    'PRODUCTION',
    'release-engineer',
    'PENDING'
FROM image_manifests
WHERE manifest_digest = 'sha256:manifest001';

-- ============================================================================
-- 48. RETRIEVAL: DOCKERFILE INSTRUCTIONS
-- ============================================================================

SELECT
    d.dockerfile_name,
    d.version_number,
    di.line_number,
    di.instruction,
    di.arguments
FROM dockerfiles d
JOIN dockerfile_instructions di
    ON di.dockerfile_id = d.dockerfile_id
WHERE d.content_digest = 'sha256:dockerfile001'
ORDER BY di.line_number;

-- ============================================================================
-- 49. VALIDATION: DOCKERFILE QUALITY
-- ============================================================================

SELECT *
FROM validate_dockerfile(
    (
        SELECT dockerfile_id
        FROM dockerfiles
        WHERE content_digest = 'sha256:dockerfile001'
    )
);

-- ============================================================================
-- 50. AGGREGATION: LAYER SIZE DISTRIBUTION
-- ============================================================================

SELECT
    compression_format,
    COUNT(*) AS layer_count,
    SUM(layer_size_bytes) AS total_bytes,
    ROUND(
        SUM(layer_size_bytes) / 1048576.0,
        2
    ) AS total_megabytes,
    AVG(layer_size_bytes) AS average_layer_size
FROM image_layers
GROUP BY compression_format
ORDER BY total_bytes DESC;

-- ============================================================================
-- 51. REPORTING: IMAGE SIZE
-- ============================================================================

SELECT *
FROM v_image_size_report
ORDER BY image_size_bytes DESC;

-- ============================================================================
-- 52. REPORTING: BUILD CACHE EFFICIENCY
-- ============================================================================

SELECT
    b.build_id,
    b.build_number,
    b.build_status,
    COALESCE(c.total_layers, 0) AS total_layers,
    COALESCE(c.cached_layers, 0) AS cached_layers,
    COALESCE(c.newly_created_layers, 0) AS new_layers,
    COALESCE(c.cache_hit_percentage, 0) AS cache_hit_percentage
FROM image_builds b
LEFT JOIN v_build_cache_statistics c
    ON c.build_id = b.build_id
ORDER BY b.created_at DESC;

-- ============================================================================
-- 53. EVALUATION: POLICY ELIGIBILITY
-- ============================================================================

SELECT
    r.repository_name,
    m.manifest_digest,
    p.policy_name,
    e.is_eligible,
    e.failed_rules
FROM policy_evaluations e
JOIN image_builds b
    ON b.build_id = e.build_id
JOIN image_manifests m
    ON m.build_id = b.build_id
JOIN image_repositories r
    ON r.repository_id = m.repository_id
JOIN image_policies p
    ON p.policy_id = e.policy_id;

-- ============================================================================
-- 54. SECURITY: VULNERABILITY REPORT
-- ============================================================================

SELECT
    repository_name,
    vulnerability_code,
    package_name,
    severity,
    is_resolved
FROM v_vulnerability_report
ORDER BY
    CASE severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;

-- ============================================================================
-- 55. WORKFLOW: APPROVE IMAGE PROMOTION
-- ============================================================================

DO $$
DECLARE
    v_promotion_id BIGINT;
BEGIN

    SELECT promotion_id
    INTO v_promotion_id
    FROM image_promotions
    WHERE promotion_status = 'PENDING'
    ORDER BY requested_at
    LIMIT 1;

    IF v_promotion_id IS NOT NULL THEN

        PERFORM approve_image_promotion(
            v_promotion_id,
            'release-manager'
        );

    END IF;

END;
$$;

-- ============================================================================
-- 56. REPORTING: LAYER REUSE
-- ============================================================================

SELECT
    l.layer_digest,
    l.layer_size_bytes,
    COUNT(DISTINCT bl.build_id) AS build_usage_count,
    COUNT(*) FILTER (
        WHERE bl.cache_hit
    ) AS cache_reuse_count
FROM image_layers l
JOIN build_layer_results bl
    ON bl.layer_id = l.layer_id
GROUP BY
    l.layer_id,
    l.layer_digest,
    l.layer_size_bytes
ORDER BY build_usage_count DESC, l.layer_size_bytes DESC;

-- ============================================================================
-- 57. MULTI-STAGE BUILD INFORMATION
-- ============================================================================

SELECT
    b.build_id,
    s.stage_name,
    s.stage_order,
    bi.image_name AS base_image,
    bi.image_tag AS base_tag,
    s.is_final_stage
FROM build_stages s
JOIN image_builds b
    ON b.build_id = s.build_id
LEFT JOIN base_images bi
    ON bi.base_image_id = s.base_image_id
ORDER BY b.build_id, s.stage_order;

-- ============================================================================
-- 58. FAILED BUILDS
-- ============================================================================

SELECT
    build_id,
    build_number,
    builder_name,
    error_message,
    started_at,
    completed_at
FROM image_builds
WHERE build_status = 'FAILED'
ORDER BY created_at DESC;

-- ============================================================================
-- 59. OPTIMIZATION FINDINGS
-- ============================================================================

SELECT
    b.build_number,
    f.finding_code,
    f.severity,
    f.description,
    f.recommendation,
    f.is_resolved
FROM optimization_findings f
JOIN image_builds b
    ON b.build_id = f.build_id
ORDER BY f.detected_at DESC;

-- ============================================================================
-- 60. REGISTRY REPOSITORY INVENTORY
-- ============================================================================

SELECT
    registry.registry_name,
    repository.repository_name,
    repository.owner_name,
    COUNT(DISTINCT manifest.manifest_id) AS image_count,
    COALESCE(
        SUM(manifest.image_size_bytes),
        0
    ) AS total_image_bytes
FROM registries registry
JOIN image_repositories repository
    ON repository.registry_id = registry.registry_id
LEFT JOIN image_manifests manifest
    ON manifest.repository_id = repository.repository_id
GROUP BY
    registry.registry_id,
    registry.registry_name,
    repository.repository_id,
    repository.repository_name,
    repository.owner_name
ORDER BY registry.registry_name, repository.repository_name;

-- ============================================================================
-- 61. TRANSACTIONAL PROMOTION COMPLETION EXAMPLE
-- ============================================================================

BEGIN;

UPDATE image_promotions
SET
    promotion_status = 'COMPLETED',
    completed_at = CURRENT_TIMESTAMP
WHERE promotion_status = 'APPROVED'
  AND approved_by IS NOT NULL
  AND promotion_id = (
      SELECT promotion_id
      FROM image_promotions
      WHERE promotion_status = 'APPROVED'
      ORDER BY requested_at
      LIMIT 1
      FOR UPDATE
  );

COMMIT;

-- ============================================================================
-- 62. FINAL BUILD INVENTORY
-- ============================================================================

SELECT
    r.repository_name,
    b.build_number,
    b.build_status,
    m.manifest_digest,
    ROUND(m.image_size_bytes / 1048576.0, 2) AS size_mb,
    m.layer_count,
    b.duration_ms
FROM image_builds b
JOIN dockerfiles d
    ON d.dockerfile_id = b.dockerfile_id
JOIN image_repositories r
    ON r.repository_id = d.repository_id
LEFT JOIN image_manifests m
    ON m.build_id = b.build_id
ORDER BY b.created_at DESC;

COMMIT;
