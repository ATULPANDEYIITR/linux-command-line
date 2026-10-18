# File Storage: Shared File Systems, Network File Storage, and Distributed Storage

## Scope

File storage is the organization of persistent data so that applications and users can create, read, modify, delete, and share files without needing to understand the physical storage devices underneath them.

Three related models require different design decisions:

| Model | Primary abstraction | Typical access model | Main strength | Main engineering concern |
|---|---|---|---|---|
| Shared file system | A common directory and file namespace | Multiple processes or hosts use a shared filesystem | Familiar file semantics | Shared-state coordination and availability |
| Network file storage | A remote filesystem exported to clients | NFS or SMB-style mounts | Centralized access from multiple machines | Network latency and server dependency |
| Distributed storage | Data distributed across multiple storage nodes | Object, block, or distributed storage service | Replication and failure tolerance | Placement, consistency, repair, and operational complexity |

These models are related, but they are not interchangeable. A shared filesystem describes the namespace and file-access model. Network file storage describes a filesystem made available across a network. Distributed storage describes a storage architecture in which data and responsibility for storing it are distributed across multiple machines or storage components.

The implementations in this repository deliberately keep these distinctions visible.

## Core Storage Concepts

A file has both content and metadata. Content is the byte sequence being stored. Metadata can include its name, size, owner, permissions, version, timestamps, and integrity information.

A filesystem normally presents a hierarchical namespace:

`/engineering/designs/storage-architecture.md`

The path identifies a logical location rather than a physical disk address. The storage layer translates that logical request into operations on blocks, files, objects, network services, or distributed replicas.

The examples use checksums to demonstrate integrity verification. A checksum allows a storage service to compare a stored representation with an expected representation. The Python and JavaScript demonstrations use SHA-256 for the local executable model. The C++ and Java programs use lightweight standard-library hashing to remain dependency-free and explicitly identify that production cryptographic integrity checking should use a cryptographic digest implementation.

## Shared File Systems

A shared filesystem provides a namespace in which multiple processes can access files as files and directories.

The important property is not simply that several programs can read data. The important property is that they interact with a common filesystem namespace.

For example:

`/engineering/designs/storage-architecture.txt`

can be opened by multiple processes through the same logical path.

This model is particularly useful when applications depend on normal filesystem operations such as:

- directory traversal,
- file creation,
- renaming,
- modification,
- metadata inspection,
- file locking,
- permissions,
- and hierarchical paths.

The Python implementation models this with `LocalSharedFileSystem`. Its root directory is explicit, and every requested path is checked before access. The `_safe_path()` mechanism prevents a caller from escaping the storage namespace with paths such as `../../outside.txt`.

The Python implementation also writes through a temporary file and then uses `os.replace()`. This reduces the possibility that another process observes a partially written final file.

The C++ implementation represents the same conceptual model using an in-memory `SharedFilesystem`. It tracks logical capacity, file versions, ownership, and used space. Updating an existing file subtracts its previous size before calculating the new capacity requirement.

The distinction between logical namespace and physical storage is important. A shared filesystem can be backed by local disks, a storage array, or another storage service. The application still sees a filesystem abstraction.

## Network File Storage

Network file storage makes a filesystem namespace available to hosts across a network.

Common protocols include NFS and SMB. The client mounts or connects to a remote export and then uses filesystem operations against that remote namespace.

The important architectural separation is:

`Application host → network filesystem client → network → storage server → persistent storage`

The application normally does not need to know which physical disk contains a particular file.

The Python `NetworkFileStorageClient` represents this separation by placing the filesystem backend behind a client object. A client must mount the service before it can upload, download, or list files.

The JavaScript implementation uses the same idea but emphasizes asynchronous I/O. Node.js filesystem operations return promises, so storage operations can participate naturally in asynchronous application workflows.

The Java enterprise model represents a network client with `NetworkFileClient`. Two clients mount the same `SharedFilesystemService`, allowing one client to write a report while another client reads it.

This illustrates a central property of network file storage: different hosts can interact with one shared namespace without maintaining independent copies merely because the applications execute on different machines.

### Network File Storage Failure Modes

Network file storage introduces failure conditions that do not exist in exactly the same form for a local filesystem.

A client can lose network connectivity.

A remote server can become unavailable.

Network latency can make an operation much slower than a local filesystem access.

Authentication or authorization can prevent an otherwise valid filesystem operation.

Concurrent clients can modify the same file, creating coordination requirements.

Caching can also complicate freshness expectations. A client may have cached metadata or file contents while another client has already changed the remote file.

The storage system therefore has to consider availability, latency, permissions, concurrency, and cache semantics rather than treating a remote file exactly like a local disk.

## Distributed Storage

Distributed storage changes the architecture more substantially.

Instead of relying on one shared storage service as the primary persistence point, data can be distributed across several nodes.

A simplified architecture is:

`Application → distributed storage service → node A`
`                                   → node B`
`                                   → node C`

A replication factor of two means that an object is intentionally stored on two independent storage nodes.

Replication is different from merely allowing two clients to access the same file. Replication creates multiple physical or logical copies so that the system can continue operating when one storage location becomes unavailable.

The Python `DistributedObjectStore` implements this distinction directly.

Its `put()` operation selects healthy nodes and creates replicated copies. Its `get()` operation checks available replicas and verifies that their checksums agree.

The implementation also models:

- node availability,
- replication factors,
- checksum verification,
- replica corruption,
- consistency failures,
- and replica repair.

## Replication and Fault Tolerance

Replication improves availability because the failure of one node does not necessarily make the data inaccessible.

Suppose an object has replicas on:

`storage-a`
`storage-b`

If `storage-a` fails and `storage-b` remains healthy, the object can still be read.

The Python demonstration explicitly takes `storage-a` offline and successfully reads the object from the remaining replica.

Replication does not eliminate failure. It changes the failure boundary.

If every replica becomes unavailable, the object is unavailable.

If multiple replicas contain conflicting data, the system needs a consistency mechanism.

If a replica is corrupted but still reachable, simple availability checks are insufficient. Integrity verification is required to detect the problem.

The Python implementation demonstrates this by corrupting one replica and raising `StorageConsistencyError` when the copies disagree.

## Repair and Rebalancing

Distributed systems must consider what happens after a failure has been detected.

A failed node can return to service without necessarily having a current copy of every object. A corrupted replica can also remain physically present but logically unusable.

Repair reconstructs the replica from a verified copy.

The Python `repair()` operation reads verified data and rewrites unhealthy or missing replicas.

The Java implementation follows the same architectural idea through `DistributedStorageService.repair()`. The service obtains verified content and writes a new replica representation to online nodes.

A production distributed storage system can require more sophisticated mechanisms, including:

- replica placement policies,
- quorum decisions,
- background repair,
- rebalancing after node addition,
- erasure coding,
- failure domains,
- durability monitoring,
- and metadata consensus.

The examples deliberately use a small replication model so that the relationship between failure, integrity checking, and repair remains explicit.

## Storage Integrity

Availability and integrity are separate properties.

A replica can be available but incorrect.

For example, a storage node might return bytes successfully while those bytes differ from the expected object.

A checksum gives the storage service a mechanism for detecting this condition.

The Python and JavaScript implementations calculate SHA-256 for stored content. The distributed storage models compare replica checksums before accepting the data as consistent.

The SQL model stores a checksum for each logical file and each distributed replica. This allows database queries to identify replicas whose recorded checksums disagree.

A database checksum is metadata rather than proof that the underlying bytes are currently correct. A production storage system must verify the actual stored content rather than trusting only a metadata column.

## Python Implementation

The Python program contains three distinct storage abstractions.

`LocalSharedFileSystem` demonstrates a filesystem namespace rooted at an explicit directory. It implements safe path resolution, capacity accounting, atomic replacement, reading, deletion, and directory listing.

`NetworkFileStorageClient` separates client behavior from the storage server. Mount state is required before remote operations can proceed.

`DistributedObjectStore` models replicated objects rather than a single shared directory. It tracks independent nodes and their availability, validates checksums, detects inconsistent replicas, and performs repair.

The program also contains failure tests for:

- capacity exhaustion,
- missing files,
- unsafe path traversal,
- insufficient replication capacity,
- node failure,
- and corrupted distributed replicas.

The temporary-directory approach keeps the demonstration self-contained and prevents it from depending on a particular machine's permanent filesystem.

## JavaScript Implementation

The JavaScript program emphasizes asynchronous storage behavior.

Node.js filesystem operations use promises, making file storage naturally compatible with event-driven server applications.

`SharedFileSystem` uses asynchronous `fs/promises` operations and validates that resolved paths remain within the configured storage root.

`NetworkFileClient` models a remote filesystem connection while keeping the underlying server abstraction separate.

`DistributedObjectStore` represents replicated objects with independent node availability. It verifies both metadata checksums and the actual content checksum before returning a distributed object.

The asynchronous demonstration uses `Promise.all()` to issue multiple independent writes. This is useful for understanding that asynchronous JavaScript can coordinate concurrent I/O without turning storage code into synchronous blocking logic.

Concurrency does not make physical storage infinitely fast. Actual performance remains constrained by disk throughput, network bandwidth, filesystem behavior, storage-controller limits, and contention.

## C++ Case Study

The C++ program treats file storage as a storage-engine case study.

`RepositoryStorageNode` models an independent distributed node.

`DistributedStorageEngine` manages replication, node availability, verified reads, corruption detection, and repair.

The program explicitly separates node state from object state. A node can be offline while its previously stored objects still exist physically. They simply cannot participate in current operations until the node becomes available again.

The distributed engine uses a configurable replication factor. A write is rejected when the number of healthy nodes is insufficient.

A verified read collects available replicas and compares their calculated hashes. If replicas disagree, the engine raises a consistency exception rather than silently selecting potentially corrupted data.

The program also includes a storage-selection policy that distinguishes local shared filesystem use, network file storage, and distributed storage according to workload requirements.

This represents an important architecture decision: storage technology should follow workload requirements rather than being selected solely because one technology can technically store the files.

## Java Enterprise Implementation

The Java program models file storage as a small enterprise service layer.

`SharedFilesystemService` manages logical files, versions, capacity, owners, timestamps, and integrity metadata.

`NetworkFileClient` represents a client that must explicitly mount the remote service before performing remote filesystem operations.

`StorageNode` models a distributed storage member with independent online/offline state.

`DistributedStorageService` provides replication, verified reads, placement inspection, node state changes, and repair.

The Java implementation uses records for immutable metadata representations. `FileMetadata` separates descriptive file information from `StoredObject`, which contains the actual content.

The distributed service uses streams to identify healthy nodes and collect available replicas. Exceptions represent domain-level failures rather than relying only on printed status messages.

The design demonstrates why enterprise storage code benefits from explicit domain types. A node being offline, a file exceeding capacity, and replicas failing integrity checks are different failure states and therefore receive different representations.

## SQL Data Model

The PostgreSQL implementation models storage as a relational domain.

`storage_system` identifies the overall storage service and records whether it represents a shared filesystem, network file storage, or distributed storage.

`storage_node` represents physical or logical storage members.

`storage_user` represents ownership and operational identity.

`directory_entry` models the hierarchical namespace required by filesystem-oriented storage.

`stored_file` contains logical file metadata including ownership, size, version, state, and checksum.

`network_mount` records which client hosts have active NFS or SMB-style access to a storage system.

`distributed_replica` represents a specific replica of a logical file on a specific storage node.

`replication_policy` stores the required replication factor and checksum-verification policy.

These relationships deliberately separate logical file identity from physical replica placement. One logical file can therefore have multiple replica records.

## Database Constraints and Integrity

The database uses primary keys to identify storage entities and foreign keys to preserve relationships.

The file size and storage capacity fields use positive-value checks where appropriate.

A unique constraint on storage nodes prevents duplicate node names within one storage system.

A unique constraint on `(file_id, node_id)` prevents the same logical file from being recorded twice on the same storage node.

A unique constraint on filesystem names prevents duplicate entries in the same parent namespace.

Indexes target common operational queries, including:

- files by storage system and state,
- files by owner,
- active network mounts,
- replicas by file and health state,
- and replicas by node and health state.

These indexes do not make every storage query fast automatically. Their value depends on query selectivity, table size, write frequency, and the execution plans chosen by PostgreSQL.

## Database-Level Distributed Storage Analysis

The SQL queries calculate the number of healthy replicas available for a file and compare that number with the configured replication factor.

This makes a distinction between:

`replica exists`

and:

`replica is healthy and its storage node is online`

A physically recorded replica is not automatically a usable replica.

The checksum-disagreement query detects cases where multiple replicas of the same logical file report different checksum values.

The utilization query measures logical file usage against the configured storage-system capacity. In a replicated system, this is not the same as physical capacity consumption because the same logical bytes can occupy multiple replicas.

That distinction is essential when designing storage monitoring.

## Transactions

The SQL script uses a transaction when a distributed replica is marked unhealthy.

The state transition is committed only after the update succeeds.

This matters because storage metadata is operational state. If a system records half of a state change and fails before recording the rest, monitoring and repair processes can make incorrect decisions.

Database transactions provide atomicity for metadata operations, but they do not automatically make an external filesystem write transactional. Coordinating database metadata with external storage requires additional application-level protocols.

## Capacity Management

Capacity exists at several levels.

A local filesystem can enforce a physical or logical capacity limit.

A network storage server can enforce quotas or filesystem capacity.

A distributed system must consider capacity across multiple nodes, replication overhead, metadata, and sometimes erasure-coding overhead.

The Python and Java implementations demonstrate capacity checks before accepting writes.

The SQL model records logical capacity and logical file usage. For a replicated system, administrators must not interpret logical usage as physical consumption without accounting for the replication factor.

For example, a 1 GB logical object replicated three times can require approximately 3 GB of raw storage before metadata and implementation overhead are considered.

## Shared Namespace Versus Replicated Data

A shared namespace and replication solve different problems.

A shared namespace answers:

> How can multiple clients refer to the same file hierarchy?

Replication answers:

> How can data remain available when a storage location fails?

Network file storage commonly emphasizes the first question.

Distributed storage commonly emphasizes the second.

A distributed storage service can expose a filesystem-like interface, but the underlying architecture can still involve multiple replicas, nodes, placement policies, and repair mechanisms.

The interface presented to the application therefore does not necessarily reveal the storage architecture underneath it.

## Performance Considerations

Filesystem operations have costs related to metadata lookup, directory structure, storage latency, caching, synchronization, and device throughput.

Network file storage adds network round trips and server-side processing.

Distributed storage adds coordination, replication traffic, checksum processing, metadata management, and repair traffic.

Replication also increases write cost because a single logical write can produce multiple physical writes.

For a replication factor of `R`, a simple replicated write may require approximately `R` storage destinations, although real systems can pipeline or optimize these operations.

Read performance can improve when data can be served from multiple locations, but the benefit depends on placement, load balancing, locality, caching, and the consistency model.

## Failure Handling

Important failure classes include:

| Failure | Shared filesystem | Network file storage | Distributed storage |
|---|---|---|---|
| Missing file | Namespace lookup failure | Remote namespace failure | Object or metadata lookup failure |
| Storage full | Capacity rejection | Server quota or filesystem capacity | Node or cluster capacity pressure |
| Client disconnected | Local process failure | Network session failure | Service connection failure |
| Storage node failure | Depends on underlying system | Server or array availability problem | Replica placement determines survivability |
| Corrupted data | Filesystem or storage integrity mechanism | Server-side integrity mechanism | Replica verification and repair |
| Concurrent modification | File locking and application coordination | Distributed locking/cache semantics | Service-level consistency mechanisms |

The correct failure response depends on the storage model.

A failed network connection is not repaired in the same way as a corrupted distributed replica.

## Security Considerations

Filesystem security includes ownership, permissions, access-control lists, service identities, and namespace isolation.

The Python and JavaScript implementations explicitly protect filesystem roots from path traversal. A storage service that accepts user-controlled paths must not blindly concatenate those paths with a storage root.

Network storage requires authentication and authorization because remote clients can otherwise become unauthorized access paths.

Distributed storage requires additional protection for:

- node-to-node communication,
- service authentication,
- replica management,
- administrative operations,
- encryption at rest,
- encryption in transit,
- and isolation between tenants.

Checksums help detect accidental or malicious data modification but are not a complete authorization mechanism.

A checksum also does not replace encryption. Integrity and confidentiality address different security properties.

## Edge Cases and Common Design Errors

Treating a network-mounted filesystem as though it has local-disk latency can produce poor application performance.

Assuming that replication automatically means consistency can hide stale or conflicting replicas.

Counting an offline replica as healthy can make a replication policy appear satisfied when the data is not actually available.

Counting logical bytes as physical usage in a replicated system can significantly underestimate required capacity.

Trusting a stored checksum without verifying the actual bytes can allow metadata corruption to hide data corruption.

Allowing arbitrary relative paths without namespace validation can create path traversal vulnerabilities.

Writing directly to a destination file can expose partially written content to concurrent readers. Atomic replacement is often preferable when the underlying filesystem semantics support it.

Assuming that two clients have independent files merely because they run on different hosts is incorrect when both clients use the same network filesystem namespace.

## Storage Model Selection

A local or shared filesystem is appropriate when applications need normal filesystem semantics and the namespace is the important abstraction.

Network file storage is appropriate when multiple hosts need centralized access to a common filesystem hierarchy, especially when existing applications already expect POSIX-style or SMB-style file operations.

Distributed storage becomes attractive when the workload requires large-scale capacity, horizontal expansion, node-level fault tolerance, replication, object-oriented access, or geographic distribution.

The correct decision depends on access semantics, availability requirements, latency tolerance, scalability, consistency requirements, operational capabilities, and cost.

A storage system should therefore be selected by the workload's access and failure requirements rather than by capacity alone.

## Practical Relationship Between the Three Models

The three models can be viewed as progressively broader architectural abstractions.

A shared filesystem establishes a common file namespace.

Network file storage extends that namespace across hosts.

Distributed storage changes the persistence architecture so that data can be spread across multiple storage nodes and protected through replication or other distribution techniques.

The boundary is not absolute. A distributed storage platform can expose a network filesystem interface, and a network filesystem can itself be backed by redundant storage infrastructure.

The important engineering distinction is which layer provides the guarantee being discussed: filesystem semantics, network access, or distributed persistence and fault tolerance.
