-- PostgreSQL 15+ virtual server deployment and lifecycle management lab.
-- The schema models control-plane intent, provider allocation, policy
-- enforcement, lifecycle history, health observations, and cost estimation.
-- No cloud resources are created by this database script.

BEGIN;

DROP VIEW IF EXISTS instance_inventory;
DROP VIEW IF EXISTS deployment_readiness;
DROP FUNCTION IF EXISTS record_lifecycle_transition(BIGINT, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS estimate_monthly_compute_cost(BIGINT, NUMERIC);
DROP TABLE IF EXISTS health_observations CASCADE;
DROP TABLE IF EXISTS lifecycle_events CASCADE;
DROP TABLE IF EXISTS status_checks CASCADE;
DROP TABLE IF EXISTS deployments CASCADE;
DROP TABLE IF EXISTS instance_types CASCADE;
DROP TABLE IF EXISTS machine_images CASCADE;
DROP TABLE IF EXISTS security_groups CASCADE;
DROP TABLE IF EXISTS subnets CASCADE;
DROP TABLE IF EXISTS virtual_machines CASCADE;
DROP TABLE IF EXISTS branch_protection_policies CASCADE;
DROP TABLE IF EXISTS cloud_regions CASCADE;

CREATE TABLE cloud_regions (
    region_code TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    region_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (provider_name, region_name),
    CHECK (region_code ~ '^[a-z]{2}(-[a-z0-9]+)+-[0-9]+$')
);

CREATE TABLE subnets (
    subnet_id TEXT PRIMARY KEY,
    region_code TEXT NOT NULL REFERENCES cloud_regions(region_code),
    cidr_block CIDR NOT NULL,
    availability_zone TEXT NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (region_code, cidr_block),
    CHECK (subnet_id ~ '^subnet-[A-Za-z0-9-]{3,40}$')
);

CREATE TABLE security_groups (
    security_group_id TEXT PRIMARY KEY,
    region_code TEXT NOT NULL REFERENCES cloud_regions(region_code),
    group_name TEXT NOT NULL,
    description TEXT NOT NULL,
    ingress_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (region_code, group_name),
    CHECK (security_group_id ~ '^sg-[A-Za-z0-9-]{3,40}$'),
    CHECK (jsonb_typeof(ingress_rules) = 'array')
);

CREATE TABLE machine_images (
    image_id TEXT PRIMARY KEY,
    operating_system TEXT NOT NULL,
    image_version TEXT NOT NULL,
    architecture TEXT NOT NULL DEFAULT 'x86_64',
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (image_id ~ '^(img|ami)-[A-Za-z0-9-]{3,40}$'),
    CHECK (architecture IN ('x86_64', 'arm64'))
);

CREATE TABLE instance_types (
    instance_type TEXT PRIMARY KEY,
    vcpus INTEGER NOT NULL,
    memory_gib NUMERIC(8,2) NOT NULL,
    hourly_compute_rate NUMERIC(12,6) NOT NULL,
    CHECK (vcpus > 0),
    CHECK (memory_gib > 0),
    CHECK (hourly_compute_rate >= 0)
);

CREATE TABLE virtual_machines (
    vm_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_name TEXT NOT NULL UNIQUE,
    environment TEXT NOT NULL,
    region_code TEXT NOT NULL REFERENCES cloud_regions(region_code),
    subnet_id TEXT NOT NULL REFERENCES subnets(subnet_id),
    image_id TEXT NOT NULL REFERENCES machine_images(image_id),
    instance_type TEXT NOT NULL REFERENCES instance_types(instance_type),
    root_disk_gib INTEGER NOT NULL DEFAULT 30,
    encrypted_disk BOOLEAN NOT NULL DEFAULT TRUE,
    monitoring_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    public_ip_requested BOOLEAN NOT NULL DEFAULT FALSE,
    private_ip INET,
    public_ip INET,
    state TEXT NOT NULL DEFAULT 'requested',
    health_status TEXT NOT NULL DEFAULT 'unknown',
    owner TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    terminated_at TIMESTAMPTZ,
    tags JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (instance_name ~ '^[a-z][a-z0-9-]{1,39}$'),
    CHECK (environment IN ('development', 'staging', 'production')),
    CHECK (root_disk_gib BETWEEN 8 AND 16384),
    CHECK (state IN (
        'requested', 'provisioning', 'running', 'stopping',
        'stopped', 'restarting', 'terminated', 'failed'
    )),
    CHECK (health_status IN (
        'unknown', 'healthy', 'unhealthy', 'not-running', 'terminated'
    )),
    CHECK (jsonb_typeof(tags) = 'object'),
    CHECK (owner <> ''),
    CHECK (terminated_at IS NULL OR state = 'terminated'),
    CHECK (public_ip_requested OR public_ip IS NULL)
);

CREATE TABLE vm_security_groups (
    vm_id BIGINT NOT NULL REFERENCES virtual_machines(vm_id) ON DELETE CASCADE,
    security_group_id TEXT NOT NULL REFERENCES security_groups(security_group_id),
    PRIMARY KEY (vm_id, security_group_id)
);

CREATE TABLE deployments (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vm_id BIGINT NOT NULL REFERENCES virtual_machines(vm_id),
    deployment_version TEXT NOT NULL,
    startup_script_sha256 TEXT,
    requested_by TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    outcome TEXT NOT NULL DEFAULT 'pending',
    failure_reason TEXT,
    UNIQUE (vm_id, deployment_version),
    CHECK (outcome IN ('pending', 'succeeded', 'failed', 'rolled_back')),
    CHECK (completed_at IS NULL OR completed_at >= requested_at)
);

CREATE TABLE status_checks (
    check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vm_id BIGINT NOT NULL REFERENCES virtual_machines(vm_id),
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms INTEGER,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (status IN ('pending', 'passed', 'failed', 'unknown')),
    CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CHECK (jsonb_typeof(details) = 'object')
);

CREATE TABLE lifecycle_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vm_id BIGINT NOT NULL REFERENCES virtual_machines(vm_id),
    action TEXT NOT NULL,
    previous_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (action IN (
        'create', 'start', 'stop', 'restart', 'terminate',
        'health-check', 'provider-failure', 'configuration-update'
    )),
    CHECK (jsonb_typeof(details) = 'object')
);

CREATE TABLE health_observations (
    observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vm_id BIGINT NOT NULL REFERENCES virtual_machines(vm_id),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    probe_name TEXT NOT NULL,
    is_healthy BOOLEAN NOT NULL,
    latency_ms INTEGER,
    diagnostic TEXT,
    CHECK (latency_ms IS NULL OR latency_ms >= 0)
);

-- The name is retained to illustrate a cloud-policy distinction: these
-- controls govern virtual-machine deployments, not source-code branches.
CREATE TABLE branch_protection_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name TEXT NOT NULL UNIQUE,
    environment TEXT NOT NULL,
    require_encrypted_disk BOOLEAN NOT NULL DEFAULT TRUE,
    require_monitoring BOOLEAN NOT NULL DEFAULT TRUE,
    require_approved_image BOOLEAN NOT NULL DEFAULT TRUE,
    require_private_subnet BOOLEAN NOT NULL DEFAULT TRUE,
    maximum_root_disk_gib INTEGER NOT NULL DEFAULT 512,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (environment IN ('development', 'staging', 'production')),
    CHECK (maximum_root_disk_gib BETWEEN 8 AND 16384)
);

CREATE INDEX idx_vms_state_region
    ON virtual_machines (state, region_code);

CREATE INDEX idx_vms_owner_environment
    ON virtual_machines (owner, environment);

CREATE INDEX idx_lifecycle_vm_time
    ON lifecycle_events (vm_id, event_time DESC);

CREATE INDEX idx_checks_vm_latest
    ON status_checks (vm_id, checked_at DESC);

CREATE INDEX idx_health_vm_latest
    ON health_observations (vm_id, observed_at DESC);

CREATE INDEX idx_vm_tags_gin
    ON virtual_machines USING GIN (tags);

INSERT INTO cloud_regions (region_code, provider_name, region_name)
VALUES
    ('ap-south-1', 'ExampleCloud', 'Asia South'),
    ('eu-west-1', 'ExampleCloud', 'Europe West');

INSERT INTO subnets (
    subnet_id, region_code, cidr_block, availability_zone, is_public
)
VALUES
    ('subnet-app001', 'ap-south-1', '10.60.1.0/24', 'ap-south-1a', FALSE),
    ('subnet-web001', 'ap-south-1', '10.60.2.0/24', 'ap-south-1b', TRUE),
    ('subnet-eu001', 'eu-west-1', '10.70.1.0/24', 'eu-west-1a', FALSE);

INSERT INTO security_groups (
    security_group_id, region_code, group_name, description, ingress_rules
)
VALUES
    (
        'sg-app001', 'ap-south-1', 'application-private',
        'HTTPS ingress from approved upstream services',
        '[{"protocol":"tcp","port":443,"source":"10.60.0.0/16"}]'::jsonb
    ),
    (
        'sg-web001', 'ap-south-1', 'web-public',
        'Public HTTPS ingress',
        '[{"protocol":"tcp","port":443,"source":"0.0.0.0/0"}]'::jsonb
    ),
    (
        'sg-eu001', 'eu-west-1', 'application-eu',
        'Private European application ingress',
        '[{"protocol":"tcp","port":443,"source":"10.70.0.0/16"}]'::jsonb
    );

INSERT INTO machine_images (
    image_id, operating_system, image_version, architecture, approved
)
VALUES
    ('img-linux2026', 'Linux', '2026.10', 'x86_64', TRUE),
    ('img-unreviewed', 'Linux', '2026.09-custom', 'x86_64', FALSE),
    ('ami-eulinux2026', 'Linux', '2026.10', 'arm64', TRUE);

INSERT INTO instance_types (
    instance_type, vcpus, memory_gib, hourly_compute_rate
)
VALUES
    ('small', 2, 4, 0.050000),
    ('medium', 4, 16, 0.120000),
    ('large', 8, 32, 0.240000);

INSERT INTO branch_protection_policies (
    policy_name, environment, require_encrypted_disk, require_monitoring,
    require_approved_image, require_private_subnet, maximum_root_disk_gib
)
VALUES
    ('Development baseline', 'development', FALSE, TRUE, FALSE, FALSE, 512),
    ('Production baseline', 'production', TRUE, TRUE, TRUE, TRUE, 512),
    ('Staging baseline', 'staging', TRUE, TRUE, TRUE, TRUE, 256);

INSERT INTO virtual_machines (
    instance_name, environment, region_code, subnet_id, image_id,
    instance_type, root_disk_gib, encrypted_disk, monitoring_enabled,
    public_ip_requested, private_ip, public_ip, state, health_status,
    owner, idempotency_key, tags
)
VALUES
    (
        'catalog-api', 'development', 'ap-south-1', 'subnet-app001',
        'img-linux2026', 'medium', 40, TRUE, TRUE, FALSE,
        '10.60.1.10', NULL, 'running', 'healthy',
        'platform-team', 'deploy-catalog-20261012',
        '{"service":"catalog","team":"platform","environment":"development"}'
    ),
    (
        'payments-api', 'production', 'ap-south-1', 'subnet-app001',
        'img-linux2026', 'large', 80, TRUE, TRUE, FALSE,
        '10.60.1.20', NULL, 'running', 'healthy',
        'payments-team', 'deploy-payments-20261012',
        '{"service":"payments","team":"payments","environment":"production"}'
    ),
    (
        'staging-worker', 'staging', 'eu-west-1', 'subnet-eu001',
        'ami-eulinux2026', 'small', 30, TRUE, TRUE, FALSE,
        '10.70.1.15', NULL, 'stopped', 'not-running',
        'platform-team', 'deploy-staging-20261012',
        '{"service":"worker","team":"platform","environment":"staging"}'
    ),
    (
        'legacy-worker', 'development', 'ap-south-1', 'subnet-web001',
        'img-unreviewed', 'small', 20, TRUE, FALSE, TRUE,
        '10.60.2.15', '198.51.100.15', 'failed', 'unhealthy',
        'migration-team', 'deploy-legacy-20261012',
        '{"service":"legacy-worker","team":"migration","environment":"development"}'
    );

INSERT INTO vm_security_groups (vm_id, security_group_id)
SELECT vm.vm_id,
       CASE WHEN vm.instance_name = 'legacy-worker'
            THEN 'sg-web001'
            WHEN vm.region_code = 'eu-west-1'
            THEN 'sg-eu001'
            ELSE 'sg-app001'
       END
FROM virtual_machines AS vm;

INSERT INTO deployments (
    vm_id, deployment_version, startup_script_sha256, requested_by,
    completed_at, outcome, failure_reason
)
SELECT vm_id,
       '2026.10.12',
       md5(instance_name || ':startup-script'),
       owner,
       CASE WHEN state = 'failed' THEN NULL ELSE now() END,
       CASE WHEN state = 'failed' THEN 'failed' ELSE 'succeeded' END,
       CASE WHEN state = 'failed'
            THEN 'Startup health verification failed'
            ELSE NULL
       END
FROM virtual_machines;

INSERT INTO status_checks (vm_id, check_name, status, duration_ms, details)
SELECT vm_id, 'cloud-init', 'passed', 420,
       '{"phase":"configuration","source":"simulated-provider"}'::jsonb
FROM virtual_machines
WHERE state = 'running';

INSERT INTO status_checks (vm_id, check_name, status, duration_ms, details)
SELECT vm_id, 'application-health', 'failed', 5000,
       '{"reason":"service did not become ready"}'::jsonb
FROM virtual_machines
WHERE state = 'failed';

INSERT INTO lifecycle_events (
    vm_id, action, previous_state, new_state, actor, details
)
SELECT vm_id,
       'create',
       'requested',
       CASE WHEN state = 'failed' THEN 'failed' ELSE 'running' END,
       owner,
       jsonb_build_object(
           'region', region_code,
           'instance_type', instance_type
       )
FROM virtual_machines;

INSERT INTO lifecycle_events (
    vm_id, action, previous_state, new_state, actor, details
)
SELECT vm_id,
       'provider-failure',
       'provisioning',
       'failed',
       owner,
       '{"reason":"health check timeout"}'::jsonb
FROM virtual_machines
WHERE state = 'failed';

INSERT INTO health_observations (
    vm_id, probe_name, is_healthy, latency_ms, diagnostic
)
SELECT vm_id,
       'application-http',
       state = 'running',
       CASE WHEN state = 'running' THEN 42 ELSE 5000 END,
       CASE WHEN state = 'running'
            THEN 'HTTP readiness probe succeeded'
            ELSE 'Readiness probe timed out'
       END
FROM virtual_machines;

-- Return the current inventory with compute characteristics.
CREATE VIEW instance_inventory AS
SELECT
    vm.vm_id,
    vm.instance_name,
    vm.environment,
    vm.region_code,
    vm.state,
    vm.health_status,
    vm.private_ip,
    vm.public_ip,
    vm.owner,
    flavor.vcpus,
    flavor.memory_gib,
    flavor.hourly_compute_rate,
    vm.root_disk_gib,
    vm.encrypted_disk,
    vm.monitoring_enabled,
    vm.created_at,
    vm.updated_at
FROM virtual_machines AS vm
JOIN instance_types AS flavor USING (instance_type);

-- Evaluate environment-specific deployment readiness. A policy violation is
-- reported explicitly rather than silently modifying an existing server.
CREATE VIEW deployment_readiness AS
SELECT
    vm.vm_id,
    vm.instance_name,
    vm.environment,
    policy.policy_name,
    (
        (NOT policy.require_encrypted_disk OR vm.encrypted_disk)
        AND
        (NOT policy.require_monitoring OR vm.monitoring_enabled)
        AND
        (NOT policy.require_approved_image OR image.approved)
        AND
        (NOT policy.require_private_subnet OR NOT subnet.is_public)
        AND
        vm.root_disk_gib <= policy.maximum_root_disk_gib
    ) AS policy_compliant,
    image.approved AS image_approved,
    subnet.is_public AS subnet_is_public
FROM virtual_machines AS vm
JOIN branch_protection_policies AS policy
  ON policy.environment = vm.environment AND policy.active
JOIN machine_images AS image USING (image_id)
JOIN subnets AS subnet USING (subnet_id);

-- This helper records a lifecycle transition and refuses illegal transitions.
-- It deliberately does not invoke a cloud provider; an orchestrator must
-- perform the provider operation and update the database transactionally.
CREATE FUNCTION record_lifecycle_transition(
    p_vm_id BIGINT,
    p_target_state TEXT,
    p_action TEXT,
    p_actor TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_state TEXT;
    transition_allowed BOOLEAN := FALSE;
BEGIN
    SELECT state
      INTO current_state
      FROM virtual_machines
     WHERE vm_id = p_vm_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown virtual machine ID %', p_vm_id;
    END IF;

    CASE current_state
        WHEN 'requested' THEN
            transition_allowed :=
                p_target_state IN ('provisioning', 'failed');
        WHEN 'provisioning' THEN
            transition_allowed :=
                p_target_state IN ('running', 'failed');
        WHEN 'running' THEN
            transition_allowed :=
                p_target_state IN ('stopping', 'restarting', 'terminated', 'failed');
        WHEN 'stopping' THEN
            transition_allowed :=
                p_target_state IN ('stopped', 'failed');
        WHEN 'stopped' THEN
            transition_allowed :=
                p_target_state IN ('provisioning', 'terminated', 'failed');
        WHEN 'restarting' THEN
            transition_allowed :=
                p_target_state IN ('running', 'failed');
        WHEN 'failed' THEN
            transition_allowed :=
                p_target_state IN ('provisioning', 'terminated');
        WHEN 'terminated' THEN
            transition_allowed := FALSE;
        ELSE
            transition_allowed := FALSE;
    END CASE;

    IF NOT transition_allowed THEN
        RAISE EXCEPTION 'Illegal lifecycle transition: % -> %',
            current_state, p_target_state;
    END IF;

    UPDATE virtual_machines
       SET state = p_target_state,
           updated_at = now(),
           terminated_at = CASE
               WHEN p_target_state = 'terminated' THEN now()
               ELSE NULL
           END,
           health_status = CASE
               WHEN p_target_state = 'running' THEN 'healthy'
               WHEN p_target_state = 'stopped' THEN 'not-running'
               WHEN p_target_state = 'terminated' THEN 'terminated'
               WHEN p_target_state = 'failed' THEN 'unhealthy'
               ELSE health_status
           END,
           private_ip = CASE
               WHEN p_target_state = 'terminated' THEN NULL
               ELSE private_ip
           END,
           public_ip = CASE
               WHEN p_target_state = 'terminated' THEN NULL
               ELSE public_ip
           END
     WHERE vm_id = p_vm_id;

    INSERT INTO lifecycle_events (
        vm_id, action, previous_state, new_state, actor, details
    )
    VALUES (
        p_vm_id,
        p_action,
        current_state,
        p_target_state,
        p_actor,
        jsonb_build_object('recorded_by', 'database-function')
    );
END;
$$;

CREATE FUNCTION estimate_monthly_compute_cost(
    p_vm_id BIGINT,
    p_billable_hours NUMERIC DEFAULT 730
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    rate NUMERIC;
    current_state TEXT;
BEGIN
    IF p_billable_hours < 0 OR p_billable_hours > 744 THEN
        RAISE EXCEPTION 'Billable hours must be between 0 and 744';
    END IF;

    SELECT flavor.hourly_compute_rate, vm.state
      INTO rate, current_state
      FROM virtual_machines AS vm
      JOIN instance_types AS flavor USING (instance_type)
     WHERE vm.vm_id = p_vm_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown virtual machine ID %', p_vm_id;
    END IF;

    IF current_state = 'terminated' THEN
        RETURN 0;
    END IF;

    -- Compute-only illustration. Provider billing for stopped instances,
    -- storage, network traffic, and public addresses can differ.
    RETURN round(rate * p_billable_hours, 2);
END;
$$;

-- Inventory and state distribution.
SELECT * FROM instance_inventory ORDER BY vm_id;

SELECT
    environment,
    state,
    count(*) AS instance_count,
    sum(root_disk_gib) AS provisioned_root_disk_gib
FROM virtual_machines
GROUP BY environment, state
ORDER BY environment, state;

-- Find machines violating the active environment policy.
SELECT *
FROM deployment_readiness
WHERE NOT policy_compliant
ORDER BY environment, instance_name;

-- Find running instances with failed latest application checks.
WITH latest_check AS (
    SELECT DISTINCT ON (vm_id)
        vm_id, check_name, status, checked_at, details
    FROM status_checks
    WHERE check_name = 'application-health'
    ORDER BY vm_id, checked_at DESC
)
SELECT vm.instance_name, vm.state, check.status, check.checked_at, check.details
FROM virtual_machines AS vm
JOIN latest_check AS check USING (vm_id)
WHERE vm.state = 'running' AND check.status <> 'passed';

-- Cost estimate grouped by environment. It does not claim to be a final bill.
SELECT
    environment,
    sum(estimate_monthly_compute_cost(vm_id, 730)) AS estimated_compute_cost
FROM virtual_machines
GROUP BY environment
ORDER BY environment;

-- Demonstrate a valid stop transition with an atomic audit record.
-- The selected development VM begins in the running state.
BEGIN;
SELECT record_lifecycle_transition(
    (SELECT vm_id FROM virtual_machines WHERE instance_name = 'catalog-api'),
    'stopping',
    'stop',
    'operations-demo'
);
SELECT record_lifecycle_transition(
    (SELECT vm_id FROM virtual_machines WHERE instance_name = 'catalog-api'),
    'stopped',
    'stop',
    'operations-demo'
);
COMMIT;

-- Demonstrate transaction rollback for an invalid state transition. The
-- exception aborts this transaction; the savepoint allows the script to
-- continue after the expected rejection.
BEGIN;
SAVEPOINT invalid_transition_demo;
DO $$
BEGIN
    BEGIN
        PERFORM record_lifecycle_transition(
            (SELECT vm_id FROM virtual_machines
             WHERE instance_name = 'catalog-api'),
            'running',
            'start',
            'operations-demo'
        );
        RAISE EXCEPTION 'Expected invalid transition was not rejected';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Invalid transition rejected: %', SQLERRM;
    END;
END;
$$;
ROLLBACK TO SAVEPOINT invalid_transition_demo;
COMMIT;

-- Database constraints reject unencrypted production instances even when an
-- application-level policy check is accidentally omitted. The nested block
-- catches the expected constraint violation without aborting the script.
DO $$
BEGIN
    BEGIN
        INSERT INTO virtual_machines (
            instance_name, environment, region_code, subnet_id, image_id,
            instance_type, root_disk_gib, encrypted_disk, monitoring_enabled,
            state, owner, idempotency_key
        )
        VALUES (
            'invalid-prod', 'production', 'ap-south-1', 'subnet-app001',
            'img-linux2026', 'small', 20, FALSE, TRUE,
            'requested', 'platform-team', 'invalid-production-key'
        );

        RAISE EXCEPTION 'Expected production policy validation to reject the row';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Constraint rejected invalid production configuration';
    END;
END;
$$;

-- Lifecycle and operational audit history.
SELECT
    vm.instance_name,
    event.event_time,
    event.action,
    event.previous_state,
    event.new_state,
    event.actor,
    event.details
FROM lifecycle_events AS event
JOIN virtual_machines AS vm USING (vm_id)
ORDER BY event.event_time, event.event_id;

COMMIT;
