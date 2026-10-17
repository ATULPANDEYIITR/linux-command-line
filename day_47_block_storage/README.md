# Block Storage: Volumes, Disks, Snapshots, Performance, and Compute Attachment

## Scope

Block storage provides persistent block-addressable storage that can be presented to a compute system as a disk or volume. The central architectural distinction is between the compute resource that consumes storage and the persistent volume that owns the data.

This repository models that relationship across five implementation perspectives:

- Python provides an executable storage control-plane simulation with disks, compute instances, attachment rules, snapshots, capacity validation, performance calculations, and a temporary file-backed persistence demonstration.
- JavaScript models asynchronous storage operations and lifecycle events, emphasizing the remote and event-driven nature of cloud storage APIs.
- C++ implements a repository-style storage governance engine using explicit domain structures, strong state handling, attachment validation, snapshot lineage, and performance profiles.
- Java models an enterprise storage service using domain classes, enums, immutable records, interfaces, policies, validation, exceptions, and explicit volume state transitions.
- PostgreSQL represents the storage domain relationally, including compute instances, volumes, attachments, snapshots, performance profiles, integrity constraints, indexes, transactions, and operational queries.

The implementations intentionally use different perspectives rather than translating one program into another language.

## Block Storage Model

A block-storage volume exposes storage as addressable blocks. The operating system or storage consumer can create a filesystem, database data files, swap space, or another block-oriented structure on top of the volume.

The basic dependency is:

`Compute instance -> block device -> volume -> physical or distributed storage`

The compute instance provides processing. The volume provides persistence. Attaching a volume establishes the relationship between those resources, but attachment does not imply that the volume's lifetime is identical to the compute instance's lifetime.

This separation is important for replacement, scaling, disaster recovery, database maintenance, and workload migration.

A persistent volume can normally remain available after the original compute instance has been terminated or detached. The exact behavior depends on the storage platform and its deletion policy.

## Volumes and Disks

A volume is the logical storage object presented to a compute system. A disk is often used as an equivalent operational term, although specific platforms may distinguish between virtual disks, physical devices, logical volumes, and storage resources.

The implementations represent a volume with properties such as:

| Property | Meaning |
| --- | --- |
| Capacity | Maximum logical storage available |
| Used space | Data currently represented as occupied |
| Media class | HDD, SSD, or NVMe-style performance tier |
| Availability zone | Placement or attachment locality |
| Attachment | Current relationship with compute |
| State | Available or attached |
| Encryption | Whether stored data is protected at rest |
| Snapshots | Point-in-time recovery references |

Capacity is different from performance. A 2 TiB volume can have very different latency and I/O behavior depending on the storage class and its provisioned performance characteristics.

## HDD, SSD, and NVMe Characteristics

The examples use three simplified storage profiles.

| Storage class | Approximate latency model | Example throughput | Typical role |
| --- | ---: | ---: | --- |
| HDD | 8 ms | 180 MB/s | Large sequential or archival workloads |
| SSD | 0.8 ms | 550 MB/s | General application workloads |
| NVMe | 0.15 ms | 3500 MB/s | Latency-sensitive and high-I/O workloads |

These values are illustrative engineering profiles, not universal hardware specifications. Actual cloud performance depends on the provider, volume type, provisioned IOPS, throughput limits, queue depth, workload pattern, instance limits, network architecture, and other controls.

Latency and throughput describe different characteristics.

Latency measures the delay associated with an I/O operation. Throughput measures how much data can be transferred over time. IOPS measures the number of I/O operations completed per second.

A workload performing many small random database operations may be constrained by latency and IOPS. A workload moving large sequential backup files may be constrained more strongly by throughput.

## Compute Attachment

The Python, C++, and Java implementations explicitly separate compute instances from persistent volumes.

An attachment establishes a relationship such as:

`db-prod-01 -> db-data`

The volume remains a separate object. Detaching it removes the compute relationship without deleting the volume.

The examples enforce a simplified single-attachment rule. This is deliberate because multi-attach storage requires additional coordination. If several machines write to the same block device without a cluster-aware filesystem or another coordination mechanism, independent filesystem metadata can become corrupted.

Attachment locality is also modeled. The examples reject a volume-to-instance attachment when their availability zones do not match.

Real platforms differ in their zone, region, network, multi-attach, and replication semantics, so locality rules must always be verified against the specific storage service.

## Python Implementation

The Python program defines `Disk`, `ComputeInstance`, `Snapshot`, and `BlockStorageSystem` objects.

`Disk.write()` validates capacity before changing the used-space value. This demonstrates why storage operations need explicit resource accounting rather than allowing arbitrary state changes.

`ComputeInstance.attach()` checks zone compatibility and rejects a disk that is already attached. The resulting attachment is stored in both the compute object and the disk object.

`BlockStorageSystem.create_snapshot()` creates a snapshot with a parent reference. The parent relationship demonstrates a snapshot lineage rather than treating every snapshot as an unrelated object.

The program also calculates logical block counts for a 4 KiB block size and estimates transfer time from data size and throughput. These calculations illustrate why storage capacity, block size, IOPS, throughput, and latency must not be treated as interchangeable measurements.

The temporary file-backed example uses a real file to demonstrate persistence across separate open operations. It calculates SHA-256 checksums before and after additional data is written, showing a concrete persistence boundary without requiring an external storage service.

Failure handling covers negative capacity, cross-zone attachment, duplicate resources, invalid writes, capacity exhaustion, and restoration into an undersized target.

## JavaScript Implementation

The JavaScript program models storage as an asynchronous service.

`Volume`, `ComputeNode`, and `BlockStorageController` represent separate resources. The controller performs resource lookup and attachment coordination while the volume retains its persistent state.

The `asynchronousSnapshotOperation()` function uses a Promise to model a remote storage operation. A cloud storage API is not equivalent to local memory access: creating a snapshot, cloning a volume, restoring data, or changing attachment state can involve control-plane operations that complete asynchronously.

The JavaScript implementation also uses a `Map` for resource lookup and explicit error handling through `StorageError`.

The performance model uses an object keyed by media type. This makes the storage-class distinction explicit rather than embedding unrelated conditional logic throughout the program.

## C++ Governance Case Study

The C++ program models a storage governance service for a database, analytics workload, and archive workload.

Its central objects are `Disk`, `ComputeInstance`, `Snapshot`, and `RepositoryStorageGovernance`.

The storage service keeps disks independent from compute instances. `std::optional` represents the fact that a disk may have no current attachment. A populated optional value identifies the compute instance currently using the disk.

The `Disk::write()` method enforces capacity before mutating state. This keeps a basic storage invariant inside the domain object.

The snapshot representation contains:

- snapshot identity
- source disk
- logical data size
- changed-block count
- optional parent snapshot

This allows the program to represent snapshot lineage directly.

The performance model uses a `switch` over `DiskType` and returns a `PerformanceProfile` containing latency, throughput, and baseline IOPS.

The case study also demonstrates a capacity failure and a conflicting attachment. These are operationally different failures: one concerns resource exhaustion, while the other concerns lifecycle and ownership.

## Java Enterprise Model

The Java program treats block storage as an enterprise domain.

`BlockVolume` owns storage state and exposes controlled operations for writes, attachment, detachment, and snapshot creation.

`ComputeInstance` represents the compute side of the relationship. The instance stores attachment modes while the volume stores its current attachment state.

`VolumeState` makes the principal lifecycle states explicit:

`AVAILABLE -> ATTACHED -> AVAILABLE`

A volume is not destroyed when it returns to `AVAILABLE`.

The `Snapshot` record provides an immutable representation of snapshot metadata. The `PerformanceProfile` record similarly represents a measured or configured performance profile without exposing mutable implementation state.

The `StoragePolicy` interface demonstrates policy-oriented design. `ProductionDatabasePolicy` expresses a specific workload rule: a production database volume must have sufficient capacity and NVMe-class media.

This separation is useful because storage policy should not be scattered across every service method. A policy object can make a workload requirement explicit and testable.

The Java implementation also demonstrates exception-driven failure handling for duplicate resources, invalid capacity, cross-zone attachment, conflicting attachment, and unsafe writes.

## PostgreSQL Data Model

The SQL model uses the `block_storage_lab` schema and PostgreSQL enumerated types.

The major relationships are:

`compute_instance 1 -> many volume_attachment`

`volume 1 -> many volume_attachment`

`volume 1 -> many storage_snapshot`

`storage_snapshot 1 -> many child snapshots`

The `volume` table stores capacity, utilization, media type, availability zone, state, and encryption status.

The `volume_attachment` table records the relationship between a volume and compute instance. An active attachment is represented by a row with a null `detached_at`.

A partial unique index named `one_active_attachment_per_volume` prevents more than one active attachment for the same volume in this simplified model while retaining historical attachment records.

The `storage_snapshot` table stores parent-child lineage. `parent_snapshot_id` references the same table, allowing a snapshot chain to be reconstructed with a recursive common table expression.

## Database Integrity

The SQL model places basic storage invariants at the database layer.

The volume capacity constraint requires a positive capacity:

`capacity_gib > 0`

The used-space constraint prevents negative usage and prevents usage from exceeding capacity:

`used_gib >= 0 AND used_gib <= capacity_gib`

The snapshot changed-block constraint prevents negative block counts.

Foreign keys prevent attachments from referencing nonexistent compute instances or volumes.

These constraints reduce the amount of invalid state that application code can create accidentally.

Cross-table rules such as zone compatibility require more than a simple row-level check. The SQL script therefore provides a validation query that identifies cross-zone violations. A production implementation would normally enforce such a rule through transactional application logic or an appropriate database trigger.

## Snapshot Semantics

A snapshot represents the state of a volume at a point in time.

The examples store both the logical volume size and the number of changed blocks. These concepts should not be confused.

A logical snapshot can represent a large volume even when the physical storage consumed by an incremental snapshot is much smaller. The exact snapshot accounting model depends on the storage implementation.

The snapshot chain in the examples is:

`db-before-maintenance -> db-after-maintenance`

The recursive SQL query reconstructs this relationship from the self-referencing `parent_snapshot_id`.

Snapshots are useful for rollback, backup workflows, development environments, migration procedures, and disaster recovery. They should not automatically be assumed to be equivalent to application-consistent backups. A database may need coordination, flushing, quiescing, or application-level backup mechanisms to guarantee recoverability to a desired point.

## Performance Considerations

Storage performance should be evaluated against the workload rather than against capacity alone.

A database performing many small random operations can expose latency and IOPS limits even when total data transfer is low.

A backup workload can consume high throughput while issuing comparatively large sequential operations.

Queue depth also matters. A storage device with low individual operation latency can exhibit different effective behavior when many operations are outstanding.

The compute instance itself can impose storage limits. A high-performance volume cannot necessarily deliver its theoretical maximum if the attached compute platform has a lower I/O or network limit.

The Python program's `calculate_iops()` and transfer-time functions intentionally keep the mathematics simple so the relationship between measurements remains visible.

## Snapshot and Recovery Risks

Snapshots must be treated as recovery mechanisms with explicit operational assumptions.

A crash-consistent snapshot captures storage state as seen at a particular point without necessarily representing a clean application transaction boundary.

For databases, recovery procedures may require transaction logs, write-ahead logs, database-native backup facilities, or application quiescence.

Snapshot retention also consumes storage resources and can create operational cost. A production policy should define retention periods, deletion behavior, recovery objectives, and protection against accidental deletion.

## Security

Block-storage security has several layers.

Encryption at rest protects stored data if the underlying storage media or service infrastructure is exposed. The SQL model therefore records an `encrypted` attribute.

Attachment authorization controls which compute identities may access a volume.

Least privilege should prevent an application that only needs read access from receiving unnecessary write access.

Snapshot access is also security-sensitive. A snapshot can contain the complete logical contents of the source volume. Granting snapshot creation or export permissions can therefore provide access to sensitive data even when direct volume access is restricted.

Credentials and encryption keys should not be embedded in source code. Production systems should use the platform's identity and key-management mechanisms.

## Failure Conditions

Several failures are distinct and should not be collapsed into a generic storage error.

A capacity failure means the volume cannot accept more data.

An attachment failure means the requested compute-to-volume relationship violates lifecycle, locality, or ownership rules.

A snapshot failure concerns point-in-time protection rather than normal I/O capacity.

A performance failure can occur when workload demand exceeds provisioned IOPS, throughput, queue, or compute-side limits even though the volume still has substantial free capacity.

A recovery failure can occur when a snapshot exists but is not sufficient to reconstruct an application-consistent state.

Keeping these failure classes separate improves monitoring and incident diagnosis.

## Common Design Mistakes

Treating a volume as if it were temporary instance-local storage defeats the main persistence property of block storage.

Assuming that more capacity automatically means more performance is incorrect. Capacity and performance are separate dimensions.

Assuming that every snapshot is an application-consistent backup can produce recovery failures.

Ignoring availability-zone or attachment constraints can make a theoretically valid volume unusable by a particular compute resource.

Allowing unrestricted concurrent attachment can cause filesystem corruption when the workload does not support shared block access.

Failing to monitor free capacity can turn a normal write into an application outage.

Using throughput alone to diagnose database storage performance can hide a latency or IOPS bottleneck.

## Production Architecture

A production block-storage service generally separates several concerns:

`Control plane -> volume lifecycle and policy`

`Data plane -> actual block I/O`

`Compute layer -> attachment and device presentation`

`Snapshot layer -> point-in-time protection`

`Monitoring -> capacity, latency, IOPS, throughput, errors`

`Security layer -> identity, authorization, encryption, key management`

The educational implementations compress these concerns into small executable models, but preserve the important boundaries between them.

A useful operational invariant is that destroying or replacing compute should not accidentally destroy persistent application data unless an explicit storage lifecycle policy says so.

## Practical Relationship Between the Concepts

Volumes provide the persistent storage object.

Disks describe how that storage is presented to a compute environment.

Snapshots capture recoverable point-in-time representations.

Performance characteristics determine whether the storage can satisfy a workload's latency, throughput, and IOPS requirements.

Compute attachment connects persistent storage to a machine capable of consuming it.

These mechanisms are related but not interchangeable. Increasing capacity does not necessarily increase IOPS. Creating a snapshot does not automatically create an application-consistent backup. Detaching a volume does not inherently erase its data. Attaching a volume does not guarantee that the workload can achieve the volume's theoretical performance.

The implementation set models these distinctions directly through state, validation, relationships, performance profiles, snapshot lineage, and database constraints.
