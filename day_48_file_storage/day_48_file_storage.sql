-- PostgreSQL-compatible file-storage model.
-- The schema separates a shared filesystem namespace from network access
-- sessions and distributed replicas. This prevents concepts such as
-- "mounted access" and "physical replica placement" from being represented
-- as the same database fact.

DROP SCHEMA IF EXISTS file_storage_lab CASCADE;
CREATE SCHEMA file_storage_lab;

SET search_path TO file_storage_lab;

CREATE TYPE storage_kind AS ENUM (
    'SHARED_FILESYSTEM',
    'NETWORK_FILE_STORAGE',
    'DISTRIBUTED_STORAGE'
);

CREATE TYPE node_state AS ENUM (
    'ONLINE',
    'OFFLINE',
    'DEGRADED'
);

CREATE TYPE file_state AS ENUM (
    'ACTIVE',
    'DELETED',
    'QUARANTINED'
);

CREATE TABLE storage_system (
    storage_system_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    system_name TEXT NOT NULL UNIQUE,
    storage_kind storage_kind NOT NULL,
    capacity_bytes BIGINT NOT NULL CHECK (capacity_bytes > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE storage_node (
    node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    storage_system_id BIGINT NOT NULL
        REFERENCES storage_system(storage_system_id)
        ON DELETE CASCADE,
    node_name TEXT NOT NULL,
    state node_state NOT NULL DEFAULT 'ONLINE',
    capacity_bytes BIGINT NOT NULL CHECK (capacity_bytes > 0),
    UNIQUE (storage_system_id, node_name)
);

CREATE TABLE storage_user (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    role_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE directory_entry (
    entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    storage_system_id BIGINT NOT NULL
        REFERENCES storage_system(storage_system_id)
        ON DELETE CASCADE,
    parent_entry_id BIGINT
        REFERENCES directory_entry(entry_id)
        ON DELETE CASCADE,
    entry_name TEXT NOT NULL,
    UNIQUE (storage_system_id, parent_entry_id, entry_name)
);

CREATE TABLE stored_file (
    file_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    storage_system_id BIGINT NOT NULL
        REFERENCES storage_system(storage_system_id)
        ON DELETE CASCADE,
    parent_entry_id BIGINT
        REFERENCES directory_entry(entry_id)
        ON DELETE RESTRICT,
    file_name TEXT NOT NULL,
    owner_user_id BIGINT NOT NULL
        REFERENCES storage_user(user_id),
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    checksum_sha256 CHAR(64) NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    state file_state NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        storage_system_id,
        parent_entry_id,
        file_name
    )
);

CREATE TABLE network_mount (
    mount_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    storage_system_id BIGINT NOT NULL
        REFERENCES storage_system(storage_system_id)
        ON DELETE CASCADE,
    user_id BIGINT NOT NULL
        REFERENCES storage_user(user_id),
    client_hostname TEXT NOT NULL,
    protocol TEXT NOT NULL CHECK (
        protocol IN ('NFS', 'SMB')
    ),
    mount_path TEXT NOT NULL,
    mounted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE distributed_replica (
    replica_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id BIGINT NOT NULL
        REFERENCES stored_file(file_id)
        ON DELETE CASCADE,
    node_id BIGINT NOT NULL
        REFERENCES storage_node(node_id)
        ON DELETE RESTRICT,
    replica_version INTEGER NOT NULL CHECK (replica_version > 0),
    checksum_sha256 CHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    is_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    last_verified_at TIMESTAMPTZ,
    UNIQUE (file_id, node_id)
);

CREATE TABLE replication_policy (
    storage_system_id BIGINT PRIMARY KEY
        REFERENCES storage_system(storage_system_id)
        ON DELETE CASCADE,
    replication_factor INTEGER NOT NULL CHECK (replication_factor > 0),
    require_distinct_nodes BOOLEAN NOT NULL DEFAULT TRUE,
    checksum_verification BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_stored_file_system_state
    ON stored_file(storage_system_id, state);

CREATE INDEX idx_stored_file_owner
    ON stored_file(owner_user_id);

CREATE INDEX idx_network_mount_active
    ON network_mount(storage_system_id, active);

CREATE INDEX idx_replica_file_health
    ON distributed_replica(file_id, is_healthy);

CREATE INDEX idx_replica_node_state
    ON distributed_replica(node_id, is_healthy);

INSERT INTO storage_system (
    system_name,
    storage_kind,
    capacity_bytes
)
VALUES
    ('engineering-share', 'SHARED_FILESYSTEM', 50000000000),
    ('corporate-nas', 'NETWORK_FILE_STORAGE', 500000000000),
    ('analytics-object-store', 'DISTRIBUTED_STORAGE', 5000000000000);

INSERT INTO storage_user (username, role_name)
VALUES
    ('alice', 'engineer'),
    ('bob', 'analyst'),
    ('storage-admin', 'storage-admin'),
    ('analytics-service', 'service');

INSERT INTO storage_node (
    storage_system_id,
    node_name,
    state,
    capacity_bytes
)
SELECT
    storage_system_id,
    node_name,
    node_state,
    2000000000000
FROM storage_system
JOIN (
    VALUES
        ('analytics-object-store', 'object-node-a', 'ONLINE'::node_state),
        ('analytics-object-store', 'object-node-b', 'ONLINE'::node_state),
        ('analytics-object-store', 'object-node-c', 'DEGRADED'::node_state)
) AS nodes(system_name, node_name, node_state)
ON storage_system.system_name = nodes.system_name;

INSERT INTO replication_policy (
    storage_system_id,
    replication_factor,
    require_distinct_nodes,
    checksum_verification
)
SELECT
    storage_system_id,
    2,
    TRUE,
    TRUE
FROM storage_system
WHERE system_name = 'analytics-object-store';

INSERT INTO directory_entry (
    storage_system_id,
    parent_entry_id,
    entry_name
)
SELECT
    storage_system_id,
    NULL,
    'reports'
FROM storage_system
WHERE system_name = 'corporate-nas';

INSERT INTO directory_entry (
    storage_system_id,
    parent_entry_id,
    entry_name
)
SELECT
    storage_system_id,
    NULL,
    'datasets'
FROM storage_system
WHERE system_name = 'analytics-object-store';

INSERT INTO stored_file (
    storage_system_id,
    parent_entry_id,
    file_name,
    owner_user_id,
    size_bytes,
    checksum_sha256,
    version_number
)
SELECT
    s.storage_system_id,
    d.entry_id,
    'monthly-revenue.csv',
    u.user_id,
    42,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    3
FROM storage_system s
JOIN directory_entry d
    ON d.storage_system_id = s.storage_system_id
JOIN storage_user u
    ON u.username = 'bob'
WHERE s.system_name = 'corporate-nas'
  AND d.entry_name = 'reports';

INSERT INTO network_mount (
    storage_system_id,
    user_id,
    client_hostname,
    protocol,
    mount_path
)
SELECT
    s.storage_system_id,
    u.user_id,
    'finance-workstation-01',
    'NFS',
    '/mnt/corporate-reports'
FROM storage_system s
JOIN storage_user u
    ON u.username = 'bob'
WHERE s.system_name = 'corporate-nas';

INSERT INTO stored_file (
    storage_system_id,
    parent_entry_id,
    file_name,
    owner_user_id,
    size_bytes,
    checksum_sha256,
    version_number
)
SELECT
    s.storage_system_id,
    d.entry_id,
    'customer-events-2026-10.json',
    u.user_id,
    4096,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    1
FROM storage_system s
JOIN directory_entry d
    ON d.storage_system_id = s.storage_system_id
JOIN storage_user u
    ON u.username = 'analytics-service'
WHERE s.system_name = 'analytics-object-store'
  AND d.entry_name = 'datasets';

INSERT INTO distributed_replica (
    file_id,
    node_id,
    replica_version,
    checksum_sha256,
    size_bytes,
    is_healthy,
    last_verified_at
)
SELECT
    f.file_id,
    n.node_id,
    1,
    f.checksum_sha256,
    f.size_bytes,
    TRUE,
    CURRENT_TIMESTAMP
FROM stored_file f
JOIN storage_system s
    ON s.storage_system_id = f.storage_system_id
JOIN storage_node n
    ON n.storage_system_id = s.storage_system_id
WHERE f.file_name = 'customer-events-2026-10.json'
  AND n.node_name IN ('object-node-a', 'object-node-b');

-- Files currently reachable through active network mounts.
SELECT
    s.system_name,
    nm.client_hostname,
    nm.protocol,
    nm.mount_path,
    f.file_name,
    f.version_number
FROM network_mount nm
JOIN storage_system s
    ON s.storage_system_id = nm.storage_system_id
JOIN stored_file f
    ON f.storage_system_id = s.storage_system_id
WHERE nm.active = TRUE
  AND f.state = 'ACTIVE'
ORDER BY s.system_name, f.file_name;

-- Distributed files whose healthy replica count is below policy.
WITH replica_counts AS (
    SELECT
        f.file_id,
        f.file_name,
        f.storage_system_id,
        COUNT(*) FILTER (
            WHERE r.is_healthy = TRUE
              AND n.state = 'ONLINE'
        ) AS healthy_replicas
    FROM stored_file f
    LEFT JOIN distributed_replica r
        ON r.file_id = f.file_id
    LEFT JOIN storage_node n
        ON n.node_id = r.node_id
    GROUP BY
        f.file_id,
        f.file_name,
        f.storage_system_id
)
SELECT
    rc.file_name,
    rc.healthy_replicas,
    rp.replication_factor,
    rc.healthy_replicas >= rp.replication_factor AS satisfies_policy
FROM replica_counts rc
JOIN replication_policy rp
    ON rp.storage_system_id = rc.storage_system_id;

-- Detect replica checksum disagreements for a file.
SELECT
    f.file_name,
    COUNT(DISTINCT r.checksum_sha256) AS distinct_replica_checksums
FROM stored_file f
JOIN distributed_replica r
    ON r.file_id = f.file_id
GROUP BY f.file_id, f.file_name
HAVING COUNT(DISTINCT r.checksum_sha256) > 1;

-- Storage utilization at the logical file layer.
SELECT
    s.system_name,
    s.storage_kind,
    s.capacity_bytes,
    COALESCE(SUM(f.size_bytes), 0) AS logical_bytes_used,
    ROUND(
        COALESCE(SUM(f.size_bytes), 0)::numeric
        / s.capacity_bytes * 100,
        2
    ) AS logical_utilization_percent
FROM storage_system s
LEFT JOIN stored_file f
    ON f.storage_system_id = s.storage_system_id
   AND f.state = 'ACTIVE'
GROUP BY
    s.storage_system_id,
    s.system_name,
    s.storage_kind,
    s.capacity_bytes
ORDER BY logical_utilization_percent DESC;

-- Show files that currently have replicas on degraded or offline nodes.
SELECT
    f.file_name,
    n.node_name,
    n.state,
    r.is_healthy
FROM distributed_replica r
JOIN stored_file f
    ON f.file_id = r.file_id
JOIN storage_node n
    ON n.node_id = r.node_id
WHERE n.state <> 'ONLINE'
   OR r.is_healthy = FALSE;

-- Transactional example: mark a failed replica unhealthy while preserving
-- a consistent database state. The application should only commit after
-- recording the failure event successfully.
BEGIN;

UPDATE distributed_replica
SET
    is_healthy = FALSE,
    last_verified_at = CURRENT_TIMESTAMP
WHERE file_id = (
    SELECT file_id
    FROM stored_file
    WHERE file_name = 'customer-events-2026-10.json'
)
AND node_id = (
    SELECT node_id
    FROM storage_node
    WHERE node_name = 'object-node-b'
);

COMMIT;

-- Verify that the failed replica is no longer counted as healthy.
SELECT
    f.file_name,
    COUNT(*) FILTER (
        WHERE r.is_healthy
          AND n.state = 'ONLINE'
    ) AS healthy_replicas
FROM stored_file f
JOIN distributed_replica r
    ON r.file_id = f.file_id
JOIN storage_node n
    ON n.node_id = r.node_id
WHERE f.file_name = 'customer-events-2026-10.json'
GROUP BY f.file_name;

-- Database-level rejection example:
-- This statement intentionally violates the positive-size constraint.
-- It is left commented so the complete script remains executable.
--
-- INSERT INTO stored_file (
--     storage_system_id,
--     file_name,
--     owner_user_id,
--     size_bytes,
--     checksum_sha256,
--     version_number
-- )
-- SELECT
--     storage_system_id,
--     'invalid.bin',
--     (SELECT user_id FROM storage_user WHERE username = 'alice'),
--     -10,
--     repeat('c', 64),
--     1
-- FROM storage_system
-- WHERE system_name = 'engineering-share';
