# Scalable Compute and Storage Architecture

## Architecture Overview

This project models a service that runs on virtual servers, distributes incoming requests across healthy instances, stores application data in versioned object storage, creates recoverable backups, and evaluates whether its infrastructure satisfies operational policies.

The design separates request processing from persistent data. Compute instances can become unavailable without requiring application objects to be stored on those instances. Object versions preserve earlier content, while backup manifests identify the data and versions captured at a particular point in time.

### Logical architecture

    Clients
       |
       v
    Load Balancer
       |
       +-------------------+-------------------+
       |                   |                   |
       v                   v                   v
    Virtual Server A    Virtual Server B    Virtual Server C
    Availability Zone A Availability Zone B Availability Zone C
       |                   |                   |
       +-------------------+-------------------+
                           |
                           v
                    Object Storage
                           |
                 +---------+---------+
                 |                   |
                 v                   v
            Object Versions     Backup Snapshots
                                     |
                                     v
                              Recovery Validation

    Architecture Policy
       |
       +-- Compute availability
       +-- Zone diversity
       +-- Storage limits
       +-- Backup availability

The architecture separates six responsibilities:

- **Compute:** Executes application requests and provides processing capacity.
- **Load balancing:** Selects an eligible instance for each incoming request.
- **Object storage:** Retains named objects independently of application servers.
- **Versioning:** Preserves historical object content and supports recovery from accidental changes.
- **Backups:** Capture a consistent logical snapshot of active objects and their version metadata.
- **Policy evaluation:** Checks whether the infrastructure meets its configured availability and recovery requirements.

A simulated backup is not equivalent to a production disaster-recovery system. A real deployment must store backup data outside the failure domain of the primary storage system.

## Compute Architecture

### Virtual servers and capacity

A virtual server is a software-defined compute environment with allocated processing, memory, networking, and operating-system resources. Applications can run on multiple virtual servers to increase capacity and reduce dependence on a single machine.

Each simulated compute instance has:

| Property | Purpose |
|---|---|
| Instance ID | Uniquely identifies a virtual server |
| Availability zone | Identifies its infrastructure failure domain |
| State | Indicates whether the instance is eligible to receive requests |
| Capacity | Defines the maximum number of concurrent simulated requests |
| Active requests | Tracks currently reserved capacity |

The implementations use three principal instance states:

- `running`: The instance can receive requests if capacity remains.
- `stopped`: The instance is not eligible for new requests.
- `unhealthy`: Health evaluation has excluded the instance from routing.

Capacity is a simplified model. The example uses a request-count limit rather than actual CPU utilization, memory consumption, network throughput, or requests per second. Production capacity planning must use measured workload behavior and appropriate resource metrics.

### Availability zones

An availability zone represents an infrastructure failure domain within a cloud region. Deploying compute instances across multiple zones reduces dependence on a single zone.

Zone diversity does not guarantee availability by itself. Instances also need suitable network connectivity, sufficient remaining capacity, health monitoring, and dependencies that can tolerate a zone failure.

The policy evaluator checks whether the number of zones containing running instances meets the configured minimum.

## Load Balancing

A load balancer distributes incoming requests across eligible application instances.

The implementations use least normalized utilization. For each eligible instance, the routing score is:

`active_requests / capacity`

The instance with the lowest score is selected. Ties are resolved using the instance identifier to produce predictable results.

An instance is eligible only when:

- Its state is `running`.
- Its active-request count is below its configured capacity.

If every instance is stopped, unhealthy, or at capacity, the router reports a capacity failure rather than assigning the request to an unavailable server.

### Request lifecycle

    Incoming request
          |
          v
    Identify eligible instances
          |
          v
    Select lowest utilization
          |
          v
    Reserve capacity
          |
          v
    Read required object
          |
          v
    Return response
          |
          v
    Release capacity

Capacity reservation and release are distinct operations. A request handler must release its reservation even if reading data or processing the request fails.

Python uses `try/finally`, JavaScript uses `try/finally` in an asynchronous handler, C++ explicitly releases capacity in its demonstration workflow, and Java uses `try/finally` around the request operation.

The C++ demonstration is sequential. Its data structures do not provide thread-safe routing. The JavaScript model uses Node.js event-driven processing, and the Java model uses asynchronous tasks with `CompletableFuture`. The Python and SQL examples use their respective synchronization and database mechanisms.

A production implementation should account for request timeouts, cancellation, retries, connection draining, health-check intervals, and failure recovery. It should also distinguish an in-flight request from a connection that has been successfully completed.

## Object Storage and Versioning

Object storage retains data as named objects rather than requiring application servers to manage a shared local filesystem. Objects can represent configuration files, reports, images, exports, and other application data.

The model associates each object with:

- A relative object key.
- A version number.
- The stored content.
- A content checksum.
- A lifecycle state.
- Creation metadata.

For example, `config/service.json` identifies a configuration object. Updating the object creates a new version instead of overwriting its historical content.

### Object version lifecycle

    Create object
         |
         v
    Version 1: revision 1
         |
         v
    Update object
         |
         v
    Version 2: revision 2
         |
         +------> Read version 1
         |
         +------> Read current version

The examples preserve historical content to illustrate recovery from accidental updates. Deletion makes the current object unavailable through ordinary reads while preserving the modeled historical record.

Object versioning and backups solve different problems. Versioning preserves earlier revisions within an object store. A backup captures a collection of object contents and versions at a defined point in time. If the primary storage system is lost, historical versions stored only within that system may also be lost.

### Object-key validation

Object keys are logical identifiers, not trusted filesystem paths. The implementations reject unsafe relative paths, including parent-directory traversal patterns.

The examples also enforce maximum object sizes. The Python, JavaScript, C++, and Java implementations validate input in application code. PostgreSQL enforces key, size, and checksum rules through table constraints and triggers.

These checks reduce accidental misuse, but object-key validation alone does not provide authorization. A production storage service must also authenticate callers and enforce access policies for individual buckets, objects, and operations.

## Backup Design

A backup captures a logical snapshot of active object versions.

The snapshot contains a manifest mapping each object key to its captured version and the corresponding object data. A checksum protects the manifest representation used by the example implementations.

### Backup lifecycle

    Active object versions
             |
             v
       Create snapshot
             |
             v
       Record manifest
             |
             v
       Verify integrity
             |
             v
       Mark completed
             |
             v
       Restore into replacement state
             |
             v
       Validate recovered objects

The examples reject incomplete backups and validate manifest consistency before restoration. They build replacement state before publishing it, reducing the risk of exposing a partially restored collection of objects.

The checksum implementations are deliberately different:

| Implementation | Integrity mechanism |
|---|---|
| Python | SHA-256 over a deterministic manifest and object data representation |
| JavaScript | SHA-256 over canonicalized JSON containing the manifest and encoded data |
| C++17 | FNV-1a as a lightweight demonstration checksum |
| Java 17 | SHA-256 over sorted manifest entries and encoded content |
| PostgreSQL | SHA-256 through the `pgcrypto` extension |

FNV-1a is not cryptographically secure and must not be treated as protection against intentional tampering. Even a cryptographic hash does not prove who created a backup. Production backup systems should protect backup metadata and content with appropriate access controls, independent storage, encryption, and authenticated integrity mechanisms.

The SQL example records backup items and validates each item's content checksum. It stores a manifest digest for reporting. The example does not implement a complete SQL restore procedure that recalculates the manifest digest, replaces live objects, and verifies the restored state as a single recovery workflow.

### Recovery objectives

Two operational measurements guide backup design:

- **Recovery Point Objective (RPO):** The maximum acceptable amount of data loss measured in time.
- **Recovery Time Objective (RTO):** The target time required to restore service after an incident.

A backup's existence does not prove either objective can be met. Backup frequency, storage throughput, object volume, restore duration, dependencies, and recovery testing all affect actual recovery capability.

## Python Implementation

The Python script provides an executable in-memory simulation using standard-library data structures.

### Domain model

- `ComputeInstance` represents a validated virtual server.
- `StoredObject` represents a versioned object with a SHA-256 checksum.
- `Backup` records the backup manifest, captured bytes, and integrity checksum.
- `ObjectStorage` manages object versions, logical deletion, snapshots, and restoration.
- `LoadBalancer` performs least-normalized-utilization routing.
- `ArchitecturePolicy` evaluates zone diversity, running capacity, and completed backups.

The dataclasses provide explicit domain records, while enums constrain lifecycle states. Dictionaries hold object histories and instance state.

The object store uses a reentrant lock around mutations and snapshot operations. The load balancer uses a lock around instance selection and capacity reservation. These mechanisms protect individual operations in this simulation, although they do not make the entire architecture a distributed, transactionally consistent system.

### Executable workflow

The `demonstrate()` function creates application configuration and report objects, creates a backup, validates the architecture, routes requests, changes an object version, hides a deleted object, restores the backup, and simulates an unhealthy compute instance.

It also tests unsafe object keys and an empty compute pool. Assertions verify historical-version preservation and restored object contents.

The diagnostic report is written into a temporary directory, which is automatically removed after the example completes.

The simulator keeps object data in memory. It does not provide durable storage, cross-process synchronization, a network endpoint, or real cloud-provider APIs.

## JavaScript Implementation

The JavaScript file uses Node.js standard-library modules to model an event-driven architecture.

### Event-driven operations

`ObjectStore` and `ComputePool` extend `EventEmitter`. They publish events for object storage, object deletion, backup restoration, request routing, health changes, and capacity exhaustion.

Event listeners can observe these changes without embedding every reporting operation inside the underlying storage or routing methods.

The store uses private class fields and `Map` collections to manage version histories. Buffer copies reduce the risk of callers accidentally mutating the bytes retained by the store.

### Asynchronous request processing

The request handler acquires compute capacity, reads an object, and releases the reservation in a `finally` block. The main function uses `Promise.all` to execute multiple request handlers concurrently.

The load balancer's acquisition and release methods perform synchronous in-memory updates. This works for the single-threaded Node.js execution model used here, but it does not coordinate capacity across multiple processes or hosts.

The backup service also demonstrates asynchronous file handling through `node:fs/promises`. It creates a restricted-permission temporary report file and removes its temporary directory after use.

The object store and compute pool are in-memory models. The backup report contains metadata, not a durable copy of the complete object payloads. A production backup service must write actual backup data to an independent durable destination.

## C++17 Implementation

The C++ program emphasizes explicit state, typed structures, and controlled mutation through classes.

### Engineering choices

`ComputeInstance` validates its configuration and calculates utilization. `ObjectStore` manages historical object versions, rejects unsafe keys, and builds a replacement collection before restoration. `LoadBalancer` owns the compute instances and performs deterministic least-utilization selection.

The `GovernancePolicy` evaluates running capacity, zone diversity, and backup availability.

The example uses `std::map` for deterministic key ordering and `std::vector` for version history. It returns copied object records for reads rather than exposing internal storage containers.

### Integrity and complexity

The example uses FNV-1a as a compact demonstration checksum. It is not suitable for security-sensitive backup verification.

With \(n\) compute instances, selecting an instance scans the collection and takes \(O(n)\) time. With \(v\) versions of an object, historical lookup is \(O(v)\) in this implementation. Snapshot creation is linear in the number of stored objects, excluding the cost of processing their contents.

The demonstration uses sequential request handling. A production multithreaded router would need synchronization around selection and reservation, along with careful handling of request cancellation and exceptions.

## Java 17 Implementation

The Java program models the architecture with immutable records, explicit domain types, policy interfaces, and service classes.

### Domain types and validation

Java records represent compute instances, stored objects, backups, and policy results. Record constructors validate important invariants, and helper methods return updated instances rather than directly modifying record fields.

`ObjectStore` owns mutable version histories behind synchronized methods. `LoadBalancer` uses synchronized capacity operations to prevent concurrent callers from reserving the same available capacity without accounting for earlier reservations.

The storage implementation encodes bytes in Base64 for immutable backup records. SHA-256 checksums provide content-integrity checks, and restoration validates the manifest before replacing live state.

### Policy composition

`ArchitectureRule` defines a policy contract. `ZoneDiversityRule` evaluates the availability-zone requirement, while `BackupRule` checks for a completed backup.

`GovernanceService` evaluates all configured rules and collects their violations into an immutable `PolicyResult`. This separates policy definitions from the service that applies them.

The main method demonstrates asynchronous request processing with `CompletableFuture`, historical object reads, deletion, backup restoration, health changes, and failure handling.

The asynchronous service uses the common fork-join pool. This is sufficient for the local demonstration, but a production service should use a deliberately configured executor, bounded queues, timeouts, and an explicit overload policy.

## PostgreSQL Implementation

The SQL script models the architecture as relational data with database-enforced integrity rules and transactional operations.

### Relational structure

| Table | Responsibility |
|---|---|
| `repositories` | Defines the application environment and region |
| `availability_zones` | Identifies the zone failure domains |
| `compute_instances` | Stores instance health and capacity |
| `storage_buckets` | Defines object-storage limits and versioning configuration |
| `stored_objects` | Holds each object's current content and state |
| `object_versions` | Preserves historical content revisions |
| `backups` | Records backup state, completion time, and manifest digest |
| `backup_items` | Stores the objects captured by a backup |
| `load_balancer_requests` | Records request routing outcomes |
| `architecture_policies` | Stores infrastructure requirements |
| `policy_evaluations` | Persists eligibility decisions and violations |

Primary keys uniquely identify records. Foreign keys enforce relationships between repositories, zones, instances, buckets, objects, backups, and requests. Check constraints enforce basic state and capacity rules.

### Triggers and functions

`validate_object_content()` verifies object size and SHA-256 integrity before object content is inserted or changed.

`validate_version_content()` performs corresponding checks for historical versions.

`record_object_version()` creates historical records when objects are inserted or updated and synchronizes the latest version's state when it is deleted.

`reserve_compute_instance()` selects an eligible instance using normalized utilization and row-level locking. `FOR UPDATE SKIP LOCKED` prevents a concurrent reservation from waiting on an already locked candidate; if all eligible candidates are locked, the operation can report temporary capacity exhaustion even when another transaction is about to release capacity.

`release_compute_instance()` decrements active requests only when an instance has a reservation to release.

`create_bucket_backup()` captures active objects, creates backup items, calculates a deterministic manifest digest, and marks the backup completed within the transaction.

`evaluate_architecture()` checks zone diversity, running capacity, backup availability, and object-size policy. It persists the evaluation and its violations as JSONB.

### Reporting and integrity

The views provide current active objects and compute capacity by zone. Reporting queries aggregate request outcomes, inspect backup metadata, retrieve policy violations, and validate stored backup-item checksums.

The script uses `pgcrypto` for SHA-256 and UUID generation. Creating this extension requires the necessary database permissions.

The script starts by dropping and recreating its dedicated schema. It is intended for a disposable learning database, not a database containing existing application data.

### Transactional limitations

The SQL example reserves and releases capacity within one short transaction to demonstrate relational integrity. Real request processing lasts beyond a database transaction. A production design should avoid holding database locks for the duration of an external request and should use a carefully defined reservation lifecycle with expiration, completion, and failure recovery.

Similarly, the SQL backup function snapshots rows transactionally within PostgreSQL. It does not upload data to independent object storage, coordinate snapshots across separate databases, or implement off-site disaster recovery.

## Operational Constraints and Failure Modes

| Failure condition | Expected behavior | Production consideration |
|---|---|---|
| No healthy compute instances | Request routing fails | Alert, retry selectively, and restore capacity |
| All instances at capacity | New requests are rejected | Apply admission control and queue limits |
| Object key is unsafe | Write is rejected | Enforce authorization separately |
| Object exceeds size limit | Write is rejected | Define upload limits and multipart behavior |
| Historical object is missing | Read fails | Check retention and backup recovery options |
| Backup is incomplete | Restore is rejected | Alert and retry backup creation |
| Backup checksum differs | Integrity verification fails | Isolate the backup and investigate corruption |
| Availability-zone diversity is insufficient | Policy evaluation reports a violation | Restore redundancy or adjust capacity placement |
| Compute reservation cannot be released | Capacity accounting may become inaccurate | Use idempotent release operations and expiring leases |
| Primary storage is unavailable | Object reads may fail | Recover from independent durable backups |

## Security and Production Boundaries

The examples are simulations, not production cloud infrastructure. They do not provision actual virtual servers, configure a managed load balancer, or connect to a cloud object-storage service.

A production implementation should include:

- Strong identity and authorization for compute administration, object reads, writes, deletes, and backup restoration.
- Encryption in transit and at rest, with managed key rotation.
- Independent backup storage, retention policies, restore testing, and protection against unauthorized deletion.
- Centralized logs, health metrics, request latency measurements, capacity alerts, and backup-failure alerts.
- Explicit resource quotas and upload limits.
- Idempotent request handling, bounded retries, timeouts, and controlled overload behavior.
- Network isolation and restricted administrative access.
- Monitoring for zone failures and dependencies that can become single points of failure.

The main architectural principle is separation of responsibilities: compute serves requests, load balancing selects available capacity, object storage retains data, backups provide a recovery mechanism, and policy evaluation makes infrastructure requirements explicit.
