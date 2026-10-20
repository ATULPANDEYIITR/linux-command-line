# Data Backup: Full Backups, Incremental Backups, Snapshots, Retention, and Automation

## Scope

This artifact models a production-oriented backup workflow around five closely related concerns:

- Full backups
- Incremental backups
- Storage snapshots
- Retention policies
- Automated backup execution and verification

The implementations deliberately treat these as different mechanisms.

A **full backup** captures the complete selected dataset at a recovery point.

An **incremental backup** captures changes since a specified parent backup. A restore therefore depends on the full backup plus the required incremental chain.

A **snapshot** represents a point-in-time storage view. The source implementations model it as an immutable copy because standard Python, JavaScript, C++17, and Java 17 do not provide a portable storage-level snapshot API. Real copy-on-write snapshots are normally implemented by the storage platform.

A **retention policy** determines which recovery points remain eligible for storage and which can expire.

**Backup automation** schedules or executes these operations, validates their output, and detects failed or corrupted recovery points.

## Recovery Model

The central relationship is:

    Source data
        |
        +--> Full backup --------------------+
        |                                     |
        +--> Incremental 1 --> Incremental 2 --> Incremental 3
                                              |
                                              v
                                      Restore chain

The full backup is the root recovery point. Each incremental backup depends on its parent.

If a full backup contains:

    A B C D

and the next backup records:

    B' E

the logical recovery state becomes:

    A B' C D E

An incremental backup is therefore smaller than a full backup when the change set is small, but it introduces dependency management.

## Full Backups

A full backup copies every selected file.

The Python implementation calculates a SHA-256 fingerprint for every file before copying it. The manifest records:

| Field | Purpose |
|---|---|
| Relative path | Identifies the backed-up object |
| Size | Detects truncation or unexpected size changes |
| Modification timestamp | Provides source metadata |
| SHA-256 | Provides content-integrity verification |

The Java implementation uses the same cryptographic hash family through `MessageDigest`. The C++ implementation intentionally uses a lightweight standard-library checksum and comments on the production trade-off: a real deployment should use a vetted cryptographic hashing implementation rather than a non-cryptographic checksum.

Full backups provide a simple restore root, but they consume more storage and generally require more I/O than incremental backups.

## Incremental Backups

Incremental backups compare the current source inventory with a parent inventory.

A file is copied when:

- It did not exist in the parent.
- Its size changed.
- Its modification metadata changed.
- Its content fingerprint changed.

The Python model stores only changed files in an incremental manifest. The JavaScript implementation uses a `Map` to compare inventories asynchronously. The C++ implementation uses ordered maps to create deterministic inventories. The Java model represents fingerprints as immutable records.

The important distinction is that an incremental backup does not independently represent the complete dataset.

A restore requires:

    Full
      +
    Incremental 1
      +
    Incremental 2
      +
      ...
      +
    Latest incremental

A damaged or missing member of this chain can prevent reconstruction of the desired recovery point.

## Snapshots

A snapshot is a storage-level point-in-time representation rather than a conventional file-by-file backup.

Typical storage systems implement snapshots using copy-on-write metadata:

    Original blocks
         |
    Snapshot metadata
         |
    Only changed blocks require additional storage

This can make snapshots fast and space-efficient when the underlying storage supports them.

The source implementations use immutable copies to provide a portable conceptual model. This is intentionally different from claiming that a normal filesystem copy has the same atomicity, space efficiency, or crash-consistency properties as a storage snapshot.

A production snapshot system must account for:

- Application consistency
- Database write ordering
- Snapshot atomicity
- Snapshot deletion dependencies
- Storage capacity
- Snapshot availability during infrastructure failure

Snapshots should not automatically be considered an independent disaster-recovery copy. If the snapshot and primary data reside on the same failed storage system, both may be unavailable.

## Backup Integrity

Creating a backup does not prove that the backup can be restored.

The implementations therefore separate creation from verification.

The verification workflow checks:

    Backup exists
         |
         v
    Expected files exist
         |
         v
    File sizes match
         |
         v
    Checksums match
         |
         v
    Backup accepted as verified

The Python example intentionally modifies an incremental backup after creation. Verification detects the resulting checksum mismatch.

This illustrates an important operational property: integrity verification must inspect the stored backup rather than trusting the result of the copy operation.

## Python Implementation

The Python file provides a self-contained backup simulation using only the standard library.

`FileFingerprint` provides immutable file metadata. `BackupManifest` records the logical recovery information. `BackupStore` implements full and incremental backup creation and verification.

Temporary directories are used before a backup becomes visible under its final identifier:

    Temporary backup
           |
           +-- Copy data
           |
           +-- Write manifest
           |
           v
    Atomic rename
           |
           v
    Completed backup

This reduces the risk that an interrupted copy is mistaken for a completed backup.

The Python implementation also validates relative paths before reading stored backup files. This protects verification logic from malicious or corrupted manifest paths containing directory traversal components.

`RetentionPolicy` separates retention decisions from storage operations. The example evaluates old backups without automatically deleting them, which is safer than combining policy calculation and destructive deletion in a single operation.

## JavaScript Implementation

The JavaScript file models backup automation as an asynchronous Node.js process.

Filesystem operations use the promise-based `fs` API. Directory traversal is asynchronous, and checksum calculation occurs as part of the inventory workflow.

The `BackupRepository` class handles:

- Repository initialization
- Full backup creation
- Incremental change detection
- Integrity verification
- Restore-chain validation

The JavaScript implementation also includes an explicit `restoreChain` operation. It verifies every backup before copying files into a target directory.

The restore process rejects chains that do not begin with a full backup. It also validates parent relationships through the backup manifests.

`RetentionPolicy` demonstrates policy evaluation independently of the physical deletion mechanism. This separation is useful for scheduled automation because a system can first report candidates for expiration and only later perform an authorized deletion.

Node.js asynchronous filesystem operations are appropriate for an automation process that may handle many filesystem operations without blocking the event loop on every individual operation.

## C++ Implementation

The C++17 program treats backup management as a repository engine.

Its domain types distinguish:

- `BackupType`
- `FileRecord`
- `Backup`
- `ReviewResult`
- `RetentionPolicy`

The engine creates complete and incremental backups, verifies stored content, and validates incremental dependency chains.

The C++ implementation uses `std::filesystem` for recursive traversal and filesystem operations. `std::map` provides deterministic file inventories and makes comparison between backup generations straightforward.

Temporary directories are used during creation. If copying fails, the temporary directory is removed instead of leaving an apparently completed backup.

The `mergeEligible` operation demonstrates an important recovery constraint: every incremental must point to the immediately preceding member of the chain, and every member must pass verification.

The checksum implementation is intentionally marked as a limitation. Its purpose is to keep the program dependency-free while demonstrating integrity comparison. A production backup engine should use a cryptographic hash implementation such as SHA-256 from a vetted cryptographic library.

## Java Enterprise Model

The Java implementation uses explicit domain types to represent enterprise backup behavior.

`BackupType` separates full, incremental, and snapshot semantics.

`BackupState` distinguishes creation from successful verification and failed verification.

`FileFingerprint` is a Java record, providing an immutable representation of file metadata.

`BackupPolicy` centralizes operational requirements:

| Policy | Meaning |
|---|---|
| `retentionDays` | Maximum ordinary retention period |
| `requireVerification` | Requires integrity validation |
| `maximumIncrementalChain` | Limits restore-chain depth |

`BackupValidator` is an interface so validation behavior can be separated from backup creation.

`FileBackupValidator` performs path, existence, size, and SHA-256 checks.

This design prevents backup creation and backup validation from becoming a single inseparable operation. That distinction matters in enterprise systems where creation, verification, retention, monitoring, and restoration may be executed by separate services.

The Java implementation also models failure explicitly through `BackupException` rather than silently returning invalid state.

## PostgreSQL Model

The PostgreSQL script represents backup metadata as relational data.

The principal entities are:

    repositories
        |
        +---- backup_policies
        |
        +---- backups
                 |
                 +---- backup_files
                 |
                 +---- backup_jobs
                 |
                 +---- retention_events

`repositories` identifies protected data sources.

`backup_policies` defines operational requirements such as:

- Full-backup interval
- Incremental interval
- Retention period
- Maximum incremental chain
- Verification requirement

`backups` records recovery points and their relationships. The self-referencing `parent_backup_id` column represents incremental dependencies.

`backup_files` records individual files and their checksums. The database rejects unsafe relative paths containing `..`.

`backup_jobs` represents automation state separately from the backup object itself. This allows a scheduler to distinguish a queued or failed job from the recovery point eventually produced.

`retention_events` records policy decisions rather than silently deleting historical information.

## Database Integrity Rules

Several rules are enforced by PostgreSQL rather than relying solely on application code.

Examples include:

    Full backup -> no parent
    Incremental/snapshot -> parent relationship permitted
    size_bytes >= 0
    checksum -> exactly 64 hexadecimal characters
    relative path -> cannot contain traversal components
    retention_days > 0
    maximum_incremental_chain > 0
    verified backup -> verified_at must exist

This is important because backup metadata may be written by more than one application or automation process. Database constraints provide a second layer of protection against invalid state.

## Recursive Restore Chains

The SQL script uses a recursive CTE to traverse backup dependencies.

The conceptual query is:

    Full backup
         |
    Incremental
         |
    Incremental
         |
    Incremental

The recursive query calculates the depth of every member relative to its full backup.

This supports operational checks such as detecting chains that exceed a configured maximum length.

Long incremental chains can reduce restore efficiency because recovery requires applying more dependent recovery points. Limiting chain length therefore represents a trade-off between backup storage efficiency and restoration complexity.

## Retention Policies

Retention is not simply a deletion rule.

A useful policy distinguishes:

    Recent recovery point
            |
            v
           KEEP
            |
    Older recovery point
            |
            v
      Evaluate policy
            |
       +----+----+
       |         |
      KEEP     EXPIRE

The SQL model records retention decisions in `retention_events` before changing backup state.

The example uses a transaction:

    BEGIN
      Identify candidates
      Record expiration decision
      Update backup state
    COMMIT

If a database failure occurs before commit, the policy decision and state change do not become partially committed.

Physical deletion from object storage is intentionally outside this metadata transaction. Database state and external storage are separate systems, so a production implementation needs a reconciliation process to safely coordinate them.

## Automation

Backup automation normally follows a workflow similar to:

    Scheduler
        |
        v
    Load repository policy
        |
        v
    Determine required backup type
        |
        +--> Full
        |
        +--> Incremental
        |
        +--> Snapshot
        |
        v
    Create recovery point
        |
        v
    Verify integrity
        |
        +---- failure ----> Alert / retry
        |
        v
    Record successful backup
        |
        v
    Evaluate retention

Automation should not treat a successful process exit as proof of recoverability.

Useful operational states include:

- Queued
- Running
- Succeeded
- Failed
- Verified
- Expired

The SQL `backup_jobs` table provides explicit job state, while the source implementations model verification independently.

## Failure Conditions

Important backup failures include:

| Failure | Consequence | Appropriate control |
|---|---|---|
| Source disappears | Backup cannot complete | Validate source before execution |
| Disk fills | Partial backup | Temporary staging and capacity monitoring |
| File changes during copy | Inconsistent recovery point | Application-consistent snapshots or coordinated backup |
| Corrupted stored file | Restore may fail | Checksum verification |
| Missing incremental | Chain cannot reconstruct state | Dependency validation |
| Excessive incremental chain | Slow restore | Maximum chain policy |
| Premature deletion | Recovery point lost | Retention policy and protected deletion |
| Same-storage failure | Primary and backup lost together | Separate storage or disaster-recovery site |
| Malicious path metadata | Unauthorized file access | Relative-path validation |
| Silent backup failure | False recovery confidence | Job state, alerts, and verification |

## Performance Considerations

For a dataset containing `n` files, an inventory-based incremental backup performs approximately `O(n)` metadata comparisons. If checksums are recalculated for every file, the amount of data read can approach the total dataset size.

Full backups normally require:

    I/O ≈ total selected dataset

Incremental backups normally require:

    I/O ≈ changed data + metadata scanning

The practical advantage of incremental backups increases as the percentage of changed data decreases.

Hash calculation is CPU- and I/O-intensive. A production implementation can reduce unnecessary work by using filesystem metadata to identify candidates before recalculating content hashes, while still retaining cryptographic verification for the final stored copy.

## Security Considerations

Backup storage should be treated as sensitive infrastructure.

Backups may contain credentials, personal information, database contents, configuration secrets, and application source data.

A production system should therefore consider:

- Encryption in transit
- Encryption at rest
- Restricted backup credentials
- Separate backup identities
- Immutable or write-protected recovery points
- Audit logging
- Deletion authorization
- Integrity verification
- Protection against ransomware
- Separation between production credentials and backup credentials

A backup repository that is writable by the same compromised credentials used by the production application can be destroyed along with the primary data.

## Backup Versus Snapshot

| Property | Full Backup | Incremental Backup | Snapshot |
|---|---|---|---|
| Complete independent copy | Yes | No | Usually logical point-in-time view |
| Storage efficiency | Lower | Higher | Often high with copy-on-write |
| Restore dependency | Low | Chain dependent | Storage-platform dependent |
| Typical creation speed | Slower | Faster | Very fast |
| Cross-system disaster recovery | Suitable | Suitable | Not necessarily |
| Storage implementation | Files/objects | Files/objects | Storage subsystem |
| Primary concern | Storage and I/O | Chain management | Storage availability and consistency |

A snapshot is not automatically a replacement for an off-system backup.

## Operational Recovery

A robust backup design should define recovery objectives as well as backup mechanics.

**Recovery Point Objective (RPO)** describes how much recent data the organization can afford to lose.

**Recovery Time Objective (RTO)** describes how quickly the service must be restored.

For example, a policy using hourly incrementals can provide a much smaller potential data-loss window than a daily backup schedule, but it also creates more backup objects and potentially more metadata and restore-chain management.

Backup frequency, retention, storage cost, verification frequency, and restore complexity must therefore be designed together.

## Educational Focus

The five implementations deliberately use different technical perspectives:

| File | Primary perspective |
|---|---|
| Python | Filesystem backup simulation, manifests, hashing, retention |
| JavaScript | Asynchronous Node.js backup automation and restore validation |
| C++17 | Repository-oriented backup and dependency engine |
| Java 17 | Enterprise domain model, policies, validation, and explicit states |
| PostgreSQL | Relational backup metadata, dependency chains, jobs, and retention transactions |

The shared concepts are consistent across the implementations, while their structures remain appropriate to their respective runtimes and programming models.
