# Storage Virtualization

Storage virtualization separates the logical storage device presented to a consumer from the physical devices that actually provide its capacity.

The central abstraction is:

**Physical disks → Storage pool → Virtual disk → Logical volume → Logical blocks**

A consumer can address a logical block without knowing which physical disk stores it. The storage virtualization layer is responsible for capacity allocation, placement, mapping, state management, and operational policy.

This artifact treats four closely related concepts as distinct:

- **Logical volumes** define a logical block address space that applications can use.
- **Virtual disks** provide a virtual block device whose logical capacity is backed by a storage pool.
- **Block storage abstraction** hides physical placement and exposes addressable fixed-size blocks.
- **Storage pools** aggregate physical capacity into a managed resource from which virtual storage can be allocated.

The implementations deliberately approach the same storage domain from different engineering perspectives rather than translating one program line-for-line into another language.

## Core Storage Model

A physical disk has a finite capacity and a health state. Several physical disks can belong to a storage pool.

A storage pool exposes aggregate capacity:

`total capacity = sum of physical disk capacities`

Usable capacity is different from total capacity because a failed physical disk may no longer be available for new allocation.

A virtual disk is allocated from a pool. Its **logical capacity** is what the consumer sees. Its **physical allocation** is what the storage platform has actually reserved.

For thick provisioning, these values are normally equal at creation time.

For thin provisioning, logical capacity can initially be much larger than physical allocation. Physical backing grows when logical blocks receive data.

This distinction is one of the most important mechanisms demonstrated throughout the implementations.

## Block Storage Abstraction

Block storage presents storage as addressable blocks rather than as files and directories.

A logical volume has:

- a block size
- a block count
- a logical capacity
- a mapping from logical block numbers to stored data
- a state describing whether the volume is available for normal access

For a 4 KiB block size:

`logical block 0` addresses the first 4096 bytes.

`logical block 1` addresses the next 4096 bytes.

The consumer does not need to know which physical disk contains the data.

This abstraction is useful because physical placement can change independently of the logical address space. Storage systems can therefore perform allocation, migration, replication, balancing, or other physical operations without requiring the consumer to redesign its block-addressing model.

The simulations use in-memory maps for logical blocks. Production storage systems normally maintain persistent metadata and perform actual I/O against devices, storage arrays, distributed nodes, or network block protocols.

## Storage Pools

A storage pool is the capacity-management boundary in these implementations.

The Python and C++ programs use a pool containing several physical disks. The Java program uses the same conceptual structure with explicit domain classes. The SQL implementation represents the relationship with foreign keys between `storage_pool` and `physical_disk`.

A pool provides:

- total capacity
- usable capacity
- allocated capacity
- free capacity
- physical-disk health
- allocation and release operations

The pool does not expose its physical disks to the logical-volume consumer.

A placement operation can therefore return physical extents such as:

`nvme-prod-01: 40 GiB`

`nvme-prod-02: 20 GiB`

while the virtual disk continues to appear as one logical device.

The examples use a largest-free-first placement policy for clarity. This is an educational policy, not a universal production algorithm.

Real systems may consider:

- RAID stripe boundaries
- replication groups
- availability zones
- failure domains
- SSD versus HDD characteristics
- device latency
- wear level
- capacity fragmentation
- erasure-coding requirements
- data locality
- maintenance state

## Virtual Disks

A virtual disk is the intermediate block-device abstraction between a storage pool and a logical volume.

The important distinction is:

`virtual disk capacity` describes the logical address space.

`physical allocation` describes how much pool capacity has actually been committed.

The Python implementation models this distinction with `VirtualDisk`.

The Java implementation represents it as an explicit domain object containing logical capacity, provisioning type, pool identity, and physical extents.

The C++ implementation uses a `VirtualDisk` structure and treats its physical extents as part of the systems-level storage model.

The SQL implementation stores the two capacity values separately:

`logical_capacity_gib`

and

`physical_allocated_gib`

The database constraint requiring a thick disk to be fully reserved is an example of a business rule that belongs at the database integrity layer.

## Thick Provisioning

Thick provisioning reserves the requested physical capacity when the virtual disk is created.

If a 60 GiB virtual disk is created with thick provisioning, the pool immediately accounts for 60 GiB of physical allocation.

This gives predictable capacity consumption.

The Python implementation performs pool allocation during `create_virtual_disk`.

The Java and C++ implementations follow the same domain rule, but express it through their own service and domain structures.

The SQL model makes the invariant explicit through a check constraint:

`provisioning = 'thin' OR physical_allocated_gib = logical_capacity_gib`

This prevents a thick virtual disk from being represented as partially allocated.

## Thin Provisioning

Thin provisioning separates logical capacity from immediate physical reservation.

A 100 GiB thin virtual disk can initially have zero physical allocation in the model.

When the first logical blocks receive data, physical allocation grows.

The Python, JavaScript, C++, and Java implementations use a simplified 1 GiB physical allocation unit for demonstration. This is intentionally much larger than a logical block so that physical allocation changes are easy to observe.

The model illustrates the essential mechanism:

`logical capacity = address space available to the consumer`

`physical allocation = backing capacity currently committed`

Thin provisioning introduces an operational risk: logical capacity can be committed faster than physical capacity can be supplied.

A production platform therefore needs monitoring, quotas, alerts, capacity forecasting, and clear behavior when backing capacity becomes unavailable.

## Logical Volumes

A logical volume is the consumer-facing logical block-address space in the model.

The volume knows its:

- identifier
- virtual-disk relationship
- block size
- logical block count
- allocated logical blocks
- block contents

The volume does not select physical disks directly.

This separation allows the implementation to keep the logical addressing mechanism independent from the physical placement mechanism.

The Python implementation demonstrates block reads and writes with a `LogicalVolume` class.

The JavaScript implementation uses a `Map` of logical block numbers and adds asynchronous service methods to resemble an application-facing storage API.

The C++ implementation uses an ordered `std::map` to model logical block mappings and emphasizes explicit systems-level state.

The Java implementation uses a `Map<Long, BlockRecord>` and explicit domain types to represent the same logical mapping inside an enterprise-style service model.

## Python Implementation

The Python program is a complete in-memory storage virtualization engine.

Its primary domain classes are:

- `PhysicalDisk`
- `StoragePool`
- `VirtualDisk`
- `LogicalVolume`
- `Snapshot`
- `StorageVirtualizationManager`

The implementation starts at physical capacity and progressively exposes higher-level abstractions.

`StoragePool.allocate()` performs physical placement without exposing placement details to the logical volume.

`StorageVirtualizationManager.create_virtual_disk()` distinguishes thick and thin provisioning.

`LogicalVolume.write()` validates logical block boundaries and payload size before storing a block.

`read()` returns a zero-filled block when the logical block has never received data, which models the common conceptual behavior of an unwritten logical address.

The script also includes SHA-256 checksums to verify simulated block contents, snapshots, restoration, capacity failures, disk failure state, and consistency assertions.

The validation examples intentionally exercise:

- negative block numbers
- reads beyond the logical boundary
- oversized block payloads
- references to nonexistent volumes
- insufficient pool capacity

The program does not claim to be a real disk driver. It deliberately models the control-plane concepts while keeping data operations in memory.

## JavaScript Implementation

The JavaScript implementation uses a different perspective: an event-driven storage service.

`StorageService` extends Node.js `EventEmitter`.

Storage events such as block writes, snapshot creation, and snapshot restoration are emitted independently from the code that performs the operation. This models an important operational pattern in storage platforms: data-plane operations can produce audit, monitoring, and telemetry events.

The implementation also uses asynchronous methods such as `writeBlock()` and `readBlock()`.

`setImmediate()` is used to represent an asynchronous service boundary without requiring a real storage backend.

Node.js `Buffer` objects represent block payloads. The implementation copies data before storing it, preventing an external buffer reference from silently changing stored block contents.

The JavaScript version also exposes a status object containing pool, virtual-disk, and logical-volume information. This resembles the kind of state a management API could expose to an administrative interface.

The implementation demonstrates JavaScript-specific concerns such as:

- event emission
- asynchronous service boundaries
- `Map`-based block mappings
- `Buffer`-based binary data
- explicit error subclasses
- immutable configuration constants
- runtime validation

## C++ Case Study

The C++ program models a private-cloud block-storage engine.

Its architecture uses explicit domain structures:

`PhysicalDisk → StoragePool → VirtualDisk → LogicalVolume`

`BlockStorageEngine` coordinates the relationships.

The storage pool uses a map of physical disks and selects allocation candidates by available capacity. The candidate list is sorted by free capacity, producing an allocation-selection cost of approximately `O(D log D)` for `D` physical disks.

Logical block mappings use `std::map`, giving approximately `O(log B)` lookup where `B` is the number of mapped blocks.

The C++ model uses exceptions for invalid operations and explicit enums for physical-device state and provisioning mode.

The case study contains two workloads.

The transaction workload receives a thick virtual disk because predictable reserved capacity is appropriate for a stateful transactional system.

The analytics workload receives a thin virtual disk because the example emphasizes a workload whose logical address space can exceed its initial physical consumption.

The program also models snapshot creation and restoration.

The C++ implementation deliberately does not treat disk failure as automatic data recovery. A failed device changes usable capacity, but recovery requires an actual redundancy mechanism such as RAID, replication, or erasure coding.

That distinction is important because **failure detection and data recovery are different storage mechanisms**.

## Java Implementation

The Java implementation models an enterprise storage service using explicit domain objects and standard Java collections.

`PhysicalDisk` represents device capacity and health.

`StoragePool` owns the physical capacity-management rules.

`VirtualDisk` separates logical capacity from physical allocation and records physical extents.

`LogicalVolume` owns the logical block-address space.

`Snapshot` represents a point-in-time logical mapping.

`StorageService` coordinates lifecycle operations.

Java records are used for immutable value-like structures such as `PhysicalExtent` and `Snapshot`.

Enums represent constrained domain states instead of relying on arbitrary strings.

The service layer contains validation and lookup behavior, while storage entities maintain their own domain invariants.

The implementation demonstrates how enterprise-oriented design can keep storage rules explicit rather than embedding all behavior in a single procedural method.

The transaction scenario uses a thick virtual disk. The analytics scenario uses a thin virtual disk. Snapshot restoration demonstrates that the consumer-visible logical state can be reverted without exposing physical placement details.

The implementation also uses Java Streams for capacity aggregation and placement candidate selection. This makes the capacity-reporting logic concise while keeping the domain model explicit.

## SQL Data Model

The PostgreSQL schema represents the storage virtualization hierarchy relationally.

The core relationships are:

`storage_pool → physical_disk`

`storage_pool → virtual_disk`

`virtual_disk → logical_volume`

`logical_volume → logical_block`

`logical_volume → storage_snapshot`

`storage_snapshot → snapshot_block`

The physical and logical layers are therefore represented as separate tables rather than being collapsed into a single storage object.

The `physical_disk` table contains:

- physical capacity
- allocated capacity
- device state
- pool ownership

The `virtual_disk` table contains:

- logical capacity
- physical allocation
- provisioning type
- pool ownership

The `logical_volume` table contains:

- block size
- logical block count
- volume state
- virtual-disk ownership

The `logical_block` table maps a logical block number to payload and an optional physical disk.

This separation permits queries that compare logical demand with physical consumption.

## Database Integrity

The SQL implementation uses constraints for rules that should not depend entirely on application behavior.

Physical disk allocation cannot exceed physical capacity.

Physical disk allocation cannot become negative.

Virtual-disk physical allocation cannot exceed logical capacity.

A thick virtual disk must have physical allocation equal to logical capacity.

Logical block numbers cannot be negative.

Logical volumes must contain at least one logical block.

Block sizes must be positive powers of two.

Foreign keys prevent storage objects from referencing nonexistent parent objects.

The `validate_block_placement()` trigger adds a cross-table rule: a logical block cannot reference a physical disk belonging to a different storage pool from its virtual disk.

This is a useful example of a rule that requires information from several relational entities rather than a simple column-level check.

## Transactions

The SQL script includes a transactional physical-allocation operation.

The transaction:

- selects an eligible physical disk
- locks the selected row
- increments physical allocation
- increments virtual-disk physical allocation
- writes an audit record
- commits the combined operation

The transaction boundary matters because updating only one side of the capacity relationship would create inconsistent storage metadata.

A storage-control database should not represent a physical allocation as successful while the corresponding virtual-disk accounting still shows the old value.

In production, concurrency control would also need to account for multiple allocation requests arriving simultaneously.

## Snapshots

Snapshots demonstrate the distinction between current logical state and historical logical state.

The example first stores:

`transaction=TX-2026-8842;state=SETTLED`

A snapshot is created.

The live volume is then changed to:

`transaction=TX-2026-8842;state=REVERSED`

The current logical block therefore differs from the snapshot block.

The SQL model stores snapshot block contents separately for clarity.

Real snapshot implementations commonly use copy-on-write metadata and shared physical blocks rather than eagerly duplicating all data. The essential concept is that the snapshot preserves a point-in-time view while the active volume can continue to change.

## Physical Placement and Logical Addressing

The most important abstraction boundary in the artifact is between a logical block number and its physical backing.

A consumer may issue a request conceptually equivalent to:

`write(volume="lv-transactions", block=100, data=...)`

The consumer does not specify:

`disk="nvme-prod-01"`

The storage layer resolves that relationship.

This is what permits physical placement to become an implementation detail.

It also allows storage systems to perform operations such as:

- capacity balancing
- physical migration
- device replacement
- replication
- tier movement
- extent remapping

without changing the logical block address presented to the consumer.

## Capacity Accounting

Capacity must be tracked at several levels.

At the physical level:

`physical free = usable physical capacity - physical allocation`

At the virtual level:

`logical capacity = capacity visible to the consumer`

At the thin-provisioning level:

`physical allocation <= logical capacity`

These values should not be treated as interchangeable.

A thin-provisioned virtual disk can have:

`logical capacity = 180 GiB`

while:

`physical allocation = 2 GiB`

The logical address space is large even though only a small amount of physical backing has been consumed.

This creates capacity efficiency but also introduces overcommit risk.

## Failure Conditions

The implementations explicitly reject invalid operations rather than silently producing inconsistent storage state.

Examples include:

- creating duplicate storage objects
- allocating more capacity than a pool has available
- allocating from a failed disk
- accessing a block outside a logical volume
- writing data larger than the configured block size
- referring to a nonexistent pool
- referring to a nonexistent virtual disk
- referring to a nonexistent volume
- attempting to restore a nonexistent snapshot

These failures belong at different layers.

A logical block boundary error is a volume-level validation failure.

A physical capacity shortage is a pool-level resource failure.

A missing virtual disk is an object-lifecycle failure.

A failed physical disk is an infrastructure-state failure.

Keeping these failure domains distinct makes operational diagnosis clearer.

## Physical Disk Failure

A failed physical disk is removed from the pool's usable capacity calculation.

The examples deliberately retain its allocation metadata rather than pretending that failure automatically deletes the virtual storage objects.

This reflects an important architectural distinction:

**A device can fail while logical storage objects continue to exist.**

Whether their data remains available depends on the underlying redundancy design.

A storage pool using replication, RAID, or erasure coding can reconstruct or serve data despite some device failures, subject to its redundancy policy.

A simple capacity pool without redundancy cannot make such a guarantee.

Therefore, a production storage platform needs both:

- health and failure detection
- a defined data-redundancy mechanism

## Performance Considerations

Storage virtualization introduces metadata operations in addition to physical I/O.

A logical block write can conceptually require:

`logical address lookup → virtual-to-physical mapping → allocation decision → physical I/O → metadata update`

Caching and efficient metadata structures therefore matter.

The C++ case study uses `std::map` for predictable ordered lookup. The Python and JavaScript implementations use dictionaries and maps because the educational focus is on logical mapping rather than low-level I/O performance.

Production systems can require:

- extent maps rather than per-block metadata
- persistent metadata journals
- write-back or write-through caches
- asynchronous I/O queues
- batching
- locking or lock-free structures
- background reclamation
- fragmentation management
- topology-aware allocation

The correct choice depends on workload characteristics and failure requirements.

## Security Considerations

A virtual storage layer is a security boundary as well as a capacity boundary.

A production implementation must prevent one tenant or volume from addressing blocks belonging to another logical storage object.

Authorization should be evaluated before operations such as:

`create virtual disk`

`attach volume`

`read block`

`write block`

`snapshot`

`restore`

`delete`

Encryption may be implemented at the host, volume, storage-array, or device level depending on the threat model.

Audit records are also important for privileged storage operations because capacity allocation, snapshots, restoration, and physical-device state changes can have operational and security consequences.

The SQL audit table demonstrates the basic structure of recording storage operations, success state, affected resources, and timestamps.

## Debugging and Observability

A storage abstraction can hide physical placement from consumers, but operators still need visibility into the hidden layers.

Useful operational views include:

- pool total capacity
- pool usable capacity
- pool free capacity
- virtual logical capacity
- virtual physical allocation
- thin-provisioning ratio
- physical disk health
- logical blocks without backing
- snapshot age
- allocation failures
- recent storage operations

The SQL script includes queries for pool utilization, virtual-disk allocation ratios, failed-disk references, and audit history.

The JavaScript implementation emits storage events that could be connected to monitoring or logging infrastructure.

The Python, C++, and Java programs expose reports that make the logical-to-physical relationship inspectable during debugging.

## Production Design Boundaries

The programs are deliberately self-contained simulations. They model control-plane concepts without pretending to be production disk drivers or distributed storage engines.

A production implementation would need durable metadata so that a process restart does not lose the logical-to-physical mapping.

It would need crash-consistency mechanisms so that metadata and physical allocation do not diverge after an interrupted write.

It would need explicit redundancy behavior if physical failure is expected to be tolerated.

It would need concurrency control for simultaneous allocation and write requests.

It would need monitoring for thin-provisioning exhaustion.

It would need secure authorization around volume ownership and administrative operations.

It would also need a well-defined lifecycle for creation, attachment, resizing, snapshotting, migration, recovery, and deletion.

The central architectural principle remains stable even when those mechanisms become considerably more sophisticated:

**Applications operate on logical storage; virtualization manages the relationship between that logical storage and physical capacity.**
