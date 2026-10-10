-- PostgreSQL 15+ compatible cloud infrastructure model.
--
-- The schema represents a small virtual cloud platform with:
-- virtual networks, subnets, security groups, compute instances,
-- block volumes, object buckets, IAM users, roles, reviews of security
-- policies, status checks, and an auditable infrastructure event stream.
--
-- The database is responsible for enforcing relationships and important
-- invariants instead of leaving every rule to application code.

DROP SCHEMA IF EXISTS cloud_infrastructure CASCADE;

CREATE SCHEMA cloud_infrastructure;

SET search_path TO cloud_infrastructure;

CREATE TYPE instance_state AS ENUM (
    'stopped',
    'running',
    'terminated'
);

CREATE TYPE subnet_type AS ENUM (
    'public',
    'private'
);

CREATE TYPE protocol_type AS ENUM (
    'tcp',
    'udp',
    'all'
);

CREATE TYPE rule_action AS ENUM (
    'allow',
    'deny'
);

CREATE TYPE storage_class AS ENUM (
    'object',
    'block'
);

CREATE TYPE event_type AS ENUM (
    'network_created',
    'subnet_created',
    'instance_created',
    'instance_started',
    'instance_stopped',
    'instance_terminated',
    'volume_attached',
    'object_uploaded',
    'security_rule_created',
    'policy_denied'
);

CREATE TABLE cloud_user (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE role (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE
);

CREATE TABLE permission (
    permission_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permission_name TEXT NOT NULL UNIQUE
);

CREATE TABLE user_role (
    user_id BIGINT NOT NULL REFERENCES cloud_user(user_id)
        ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES role(role_id)
        ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE role_permission (
    role_id BIGINT NOT NULL REFERENCES role(role_id)
        ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permission(permission_id)
        ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE virtual_network (
    network_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    network_name TEXT NOT NULL UNIQUE,
    cidr CIDR NOT NULL,
    created_by BIGINT NOT NULL REFERENCES cloud_user(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subnet (
    subnet_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    network_id BIGINT NOT NULL REFERENCES virtual_network(network_id)
        ON DELETE CASCADE,
    subnet_name TEXT NOT NULL,
    cidr CIDR NOT NULL,
    subnet_type subnet_type NOT NULL,
    UNIQUE (network_id, subnet_name)
);

CREATE INDEX idx_subnet_network
    ON subnet(network_id);

CREATE TABLE security_group (
    security_group_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE security_rule (
    rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    security_group_id BIGINT NOT NULL
        REFERENCES security_group(security_group_id)
        ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (
        direction IN ('inbound', 'outbound')
    ),
    protocol protocol_type NOT NULL,
    port_start INTEGER,
    port_end INTEGER,
    source_cidr CIDR,
    action rule_action NOT NULL,
    CONSTRAINT valid_port_range CHECK (
        (port_start IS NULL AND port_end IS NULL)
        OR
        (
            port_start BETWEEN 1 AND 65535
            AND port_end BETWEEN 1 AND 65535
            AND port_start <= port_end
        )
    )
);

CREATE INDEX idx_security_rule_group_direction
    ON security_rule(security_group_id, direction);

CREATE TABLE compute_instance (
    instance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_name TEXT NOT NULL UNIQUE,
    subnet_id BIGINT NOT NULL REFERENCES subnet(subnet_id),
    security_group_id BIGINT NOT NULL
        REFERENCES security_group(security_group_id),
    private_ip INET NOT NULL,
    public_ip INET,
    state instance_state NOT NULL DEFAULT 'stopped',
    vcpu INTEGER NOT NULL CHECK (vcpu > 0),
    memory_gb NUMERIC(8,2) NOT NULL CHECK (memory_gb > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_active_private_ip
    ON compute_instance(private_ip)
    WHERE state <> 'terminated';

CREATE INDEX idx_compute_subnet
    ON compute_instance(subnet_id);

CREATE INDEX idx_compute_state
    ON compute_instance(state);

CREATE TABLE storage_resource (
    storage_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    storage_name TEXT NOT NULL UNIQUE,
    storage_class storage_class NOT NULL,
    encrypted BOOLEAN NOT NULL DEFAULT TRUE,
    size_gb NUMERIC(12,2),
    CHECK (
        (
            storage_class = 'block'
            AND size_gb IS NOT NULL
            AND size_gb > 0
        )
        OR
        (
            storage_class = 'object'
            AND size_gb IS NULL
        )
    )
);

CREATE TABLE volume_attachment (
    storage_id BIGINT PRIMARY KEY
        REFERENCES storage_resource(storage_id)
        ON DELETE CASCADE,
    instance_id BIGINT NOT NULL
        REFERENCES compute_instance(instance_id)
        ON DELETE CASCADE,
    attached_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_instance_volume_attachment
    ON volume_attachment(storage_id, instance_id);

CREATE TABLE object_bucket (
    bucket_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_name TEXT NOT NULL UNIQUE,
    encryption_required BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE object_record (
    object_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_id BIGINT NOT NULL REFERENCES object_bucket(bucket_id)
        ON DELETE CASCADE,
    object_key TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    encrypted BOOLEAN NOT NULL DEFAULT TRUE,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (bucket_id, object_key)
);

CREATE INDEX idx_object_bucket
    ON object_record(bucket_id);

CREATE TABLE infrastructure_event (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type event_type NOT NULL,
    actor_user_id BIGINT REFERENCES cloud_user(user_id),
    instance_id BIGINT REFERENCES compute_instance(instance_id),
    event_message TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_infrastructure_event_time
    ON infrastructure_event(occurred_at DESC);

CREATE OR REPLACE FUNCTION enforce_encrypted_block_storage()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.storage_class = 'block' AND NEW.encrypted = FALSE THEN
        RAISE EXCEPTION
            'Block storage must be encrypted';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_encrypted_block_storage
BEFORE INSERT OR UPDATE ON storage_resource
FOR EACH ROW
EXECUTE FUNCTION enforce_encrypted_block_storage();

CREATE OR REPLACE FUNCTION enforce_object_encryption()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    required_encryption BOOLEAN;
BEGIN
    SELECT encryption_required
    INTO required_encryption
    FROM object_bucket
    WHERE bucket_id = NEW.bucket_id;

    IF required_encryption AND NEW.encrypted = FALSE THEN
        RAISE EXCEPTION
            'Bucket policy requires encrypted objects';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_object_encryption
BEFORE INSERT OR UPDATE ON object_record
FOR EACH ROW
EXECUTE FUNCTION enforce_object_encryption();

CREATE OR REPLACE FUNCTION start_instance(
    target_instance_id BIGINT,
    actor BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_state instance_state;
BEGIN
    SELECT state
    INTO current_state
    FROM compute_instance
    WHERE instance_id = target_instance_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Instance % does not exist',
            target_instance_id;
    END IF;

    IF current_state = 'terminated' THEN
        RAISE EXCEPTION
            'Terminated instances cannot be started';
    END IF;

    UPDATE compute_instance
    SET state = 'running'
    WHERE instance_id = target_instance_id;

    INSERT INTO infrastructure_event (
        event_type,
        actor_user_id,
        instance_id,
        event_message
    )
    VALUES (
        'instance_started',
        actor,
        target_instance_id,
        'Compute instance entered running state'
    );
END;
$$;

INSERT INTO cloud_user (username)
VALUES
    ('platform-admin'),
    ('application-developer'),
    ('security-auditor');

INSERT INTO role (role_name)
VALUES
    ('administrator'),
    ('developer'),
    ('network-admin'),
    ('auditor');

INSERT INTO permission (permission_name)
VALUES
    ('compute'),
    ('network'),
    ('storage'),
    ('security'),
    ('storage-read');

INSERT INTO user_role (user_id, role_id)
SELECT u.user_id, r.role_id
FROM cloud_user u
JOIN role r
    ON r.role_name =
        CASE u.username
            WHEN 'platform-admin' THEN 'administrator'
            WHEN 'application-developer' THEN 'developer'
            WHEN 'security-auditor' THEN 'auditor'
        END;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
JOIN permission p
    ON (
        (r.role_name = 'administrator')
        OR
        (r.role_name = 'developer' AND p.permission_name IN (
            'compute',
            'storage'
        ))
        OR
        (r.role_name = 'network-admin' AND p.permission_name IN (
            'network',
            'security'
        ))
        OR
        (r.role_name = 'auditor' AND p.permission_name = 'storage-read')
    );

INSERT INTO virtual_network (
    network_name,
    cidr,
    created_by
)
SELECT
    'production-vpc',
    '10.0.0.0/16',
    user_id
FROM cloud_user
WHERE username = 'platform-admin';

INSERT INTO subnet (
    network_id,
    subnet_name,
    cidr,
    subnet_type
)
SELECT
    network_id,
    data.subnet_name,
    data.cidr::CIDR,
    data.subnet_type::subnet_type
FROM virtual_network,
(
    VALUES
        ('public-web', '10.0.1.0/24', 'public'),
        ('private-app', '10.0.10.0/24', 'private'),
        ('private-database', '10.0.20.0/24', 'private')
) AS data(subnet_name, cidr, subnet_type);

INSERT INTO security_group (
    group_name,
    description
)
VALUES
    (
        'web-sg',
        'Public web access with restricted administration'
    ),
    (
        'database-sg',
        'Database access from application subnet only'
    );

INSERT INTO security_rule (
    security_group_id,
    direction,
    protocol,
    port_start,
    port_end,
    source_cidr,
    action
)
SELECT
    security_group_id,
    'inbound',
    'tcp',
    443,
    443,
    '0.0.0.0/0',
    'allow'
FROM security_group
WHERE group_name = 'web-sg';

INSERT INTO security_rule (
    security_group_id,
    direction,
    protocol,
    port_start,
    port_end,
    source_cidr,
    action
)
SELECT
    security_group_id,
    'inbound',
    'tcp',
    22,
    22,
    '10.0.10.0/24',
    'allow'
FROM security_group
WHERE group_name = 'web-sg';

INSERT INTO security_rule (
    security_group_id,
    direction,
    protocol,
    port_start,
    port_end,
    source_cidr,
    action
)
SELECT
    security_group_id,
    'inbound',
    'tcp',
    5432,
    5432,
    '10.0.10.0/24',
    'allow'
FROM security_group
WHERE group_name = 'database-sg';

INSERT INTO compute_instance (
    instance_name,
    subnet_id,
    security_group_id,
    private_ip,
    vcpu,
    memory_gb
)
SELECT
    'web-01',
    s.subnet_id,
    sg.security_group_id,
    '10.0.1.10',
    2,
    4
FROM subnet s
JOIN security_group sg
    ON sg.group_name = 'web-sg'
WHERE s.subnet_name = 'public-web';

INSERT INTO compute_instance (
    instance_name,
    subnet_id,
    security_group_id,
    private_ip,
    vcpu,
    memory_gb
)
SELECT
    'app-01',
    s.subnet_id,
    sg.security_group_id,
    '10.0.10.10',
    4,
    8
FROM subnet s
JOIN security_group sg
    ON sg.group_name = 'web-sg'
WHERE s.subnet_name = 'private-app';

INSERT INTO compute_instance (
    instance_name,
    subnet_id,
    security_group_id,
    private_ip,
    vcpu,
    memory_gb
)
SELECT
    'db-01',
    s.subnet_id,
    sg.security_group_id,
    '10.0.20.10',
    4,
    16
FROM subnet s
JOIN security_group sg
    ON sg.group_name = 'database-sg'
WHERE s.subnet_name = 'private-database';

INSERT INTO storage_resource (
    storage_name,
    storage_class,
    encrypted,
    size_gb
)
VALUES (
    'database-data',
    'block',
    TRUE,
    100
);

INSERT INTO volume_attachment (
    storage_id,
    instance_id
)
SELECT
    sr.storage_id,
    ci.instance_id
FROM storage_resource sr
CROSS JOIN compute_instance ci
WHERE sr.storage_name = 'database-data'
  AND ci.instance_name = 'db-01';

INSERT INTO object_bucket (
    bucket_name,
    encryption_required
)
VALUES (
    'production-artifacts',
    TRUE
);

INSERT INTO object_record (
    bucket_id,
    object_key,
    checksum_sha256,
    encrypted,
    size_bytes
)
SELECT
    bucket_id,
    'config/application.json',
    '8f434346648f6b96df89dda901c517fb068ff2e8c5b7a6f4f4d7d6b6e7f8a9b0',
    TRUE,
    128
FROM object_bucket
WHERE bucket_name = 'production-artifacts';

BEGIN;

SELECT start_instance(
    ci.instance_id,
    u.user_id
)
FROM compute_instance ci
CROSS JOIN cloud_user u
WHERE ci.instance_name = 'web-01'
  AND u.username = 'platform-admin';

SELECT start_instance(
    ci.instance_id,
    u.user_id
)
FROM compute_instance ci
CROSS JOIN cloud_user u
WHERE ci.instance_name = 'app-01'
  AND u.username = 'platform-admin';

SELECT start_instance(
    ci.instance_id,
    u.user_id
)
FROM compute_instance ci
CROSS JOIN cloud_user u
WHERE ci.instance_name = 'db-01'
  AND u.username = 'platform-admin';

COMMIT;

-- Resource inventory.
SELECT
    ci.instance_name,
    ci.private_ip,
    ci.state,
    s.subnet_name,
    s.subnet_type,
    sg.group_name
FROM compute_instance ci
JOIN subnet s
    ON s.subnet_id = ci.subnet_id
JOIN security_group sg
    ON sg.security_group_id = ci.security_group_id
ORDER BY ci.instance_name;

-- Show the network segmentation.
SELECT
    vn.network_name,
    vn.cidr AS network_cidr,
    s.subnet_name,
    s.cidr AS subnet_cidr,
    s.subnet_type
FROM virtual_network vn
JOIN subnet s
    ON s.network_id = vn.network_id
ORDER BY s.subnet_name;

-- Evaluate the database's inbound policy against application traffic.
SELECT
    source.instance_name AS source_instance,
    destination.instance_name AS destination_instance,
    sr.protocol,
    sr.port_start,
    sr.source_cidr,
    sr.action
FROM compute_instance source
JOIN compute_instance destination
    ON destination.instance_name = 'db-01'
JOIN security_rule sr
    ON sr.security_group_id = destination.security_group_id
WHERE source.instance_name = 'app-01'
  AND sr.direction = 'inbound'
  AND source.private_ip << sr.source_cidr
  AND sr.protocol = 'tcp'
  AND 5432 BETWEEN sr.port_start AND sr.port_end;

-- Verify encrypted storage attachments.
SELECT
    sr.storage_name,
    sr.storage_class,
    sr.encrypted,
    ci.instance_name
FROM storage_resource sr
JOIN volume_attachment va
    ON va.storage_id = sr.storage_id
JOIN compute_instance ci
    ON ci.instance_id = va.instance_id;

-- Audit infrastructure state changes.
SELECT
    ie.event_type,
    cu.username AS actor,
    ci.instance_name,
    ie.event_message,
    ie.occurred_at
FROM infrastructure_event ie
LEFT JOIN cloud_user cu
    ON cu.user_id = ie.actor_user_id
LEFT JOIN compute_instance ci
    ON ci.instance_id = ie.instance_id
ORDER BY ie.occurred_at DESC;

-- Test the database constraint by attempting an invalid unencrypted volume.
-- This statement is intentionally commented because executing it must fail.
-- INSERT INTO storage_resource (
--     storage_name,
--     storage_class,
--     encrypted,
--     size_gb
-- )
-- VALUES ('unsafe-volume', 'block', FALSE, 50);

-- Test the object encryption policy in the same way.
-- INSERT INTO object_record (
--     bucket_id,
--     object_key,
--     checksum_sha256,
--     encrypted,
--     size_bytes
-- )
-- SELECT
--     bucket_id,
--     'unsafe/plaintext.txt',
--     'invalid-example',
--     FALSE,
--     20
-- FROM object_bucket
-- WHERE bucket_name = 'production-artifacts';

-- Permission analysis: identify the capabilities granted to each user.
SELECT
    u.username,
    r.role_name,
    p.permission_name
FROM cloud_user u
JOIN user_role ur
    ON ur.user_id = u.user_id
JOIN role r
    ON r.role_id = ur.role_id
JOIN role_permission rp
    ON rp.role_id = r.role_id
JOIN permission p
    ON p.permission_id = rp.permission_id
ORDER BY u.username, r.role_name, p.permission_name;

-- A useful operational view combines compute, network, and security state.
CREATE OR REPLACE VIEW infrastructure_inventory AS
SELECT
    ci.instance_name,
    ci.state,
    ci.private_ip,
    vn.network_name,
    s.subnet_name,
    s.subnet_type,
    sg.group_name,
    ci.vcpu,
    ci.memory_gb
FROM compute_instance ci
JOIN subnet s
    ON s.subnet_id = ci.subnet_id
JOIN virtual_network vn
    ON vn.network_id = s.network_id
JOIN security_group sg
    ON sg.security_group_id = ci.security_group_id;

SELECT *
FROM infrastructure_inventory
ORDER BY instance_name;
