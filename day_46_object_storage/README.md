# Object Storage Architecture

## Scope

Object storage is a storage model in which data is managed as independent objects rather than as blocks in a block device or records in a relational table. An object normally contains the object bytes, a unique key within its bucket or namespace, system metadata, user-defined metadata, and version information when versioning is enabled.

This artifact treats object storage as an operational system rather than as a simple file-upload abstraction. The implementations model buckets, objects, object versions, metadata, storage classes, lifecycle policies, delete markers, checksums, retention-oriented behavior, and the separation between control-plane operations and object data.

The examples use a repository of enterprise analytics, audit, and reporting objects because those workloads expose important object-storage characteristics: large immutable datasets, changing object versions, metadata-driven classification, lifecycle transitions, archival requirements, and the need to recover previous versions.

## Object Storage Model

The central relationship is:

`Bucket -> Object Key -> Object Version -> Object Data + Metadata`

A bucket provides a namespace and administrative boundary. An object key identifies an object within that namespace. The key is not necessarily a traditional filesystem path even when applications use path-like names such as `analytics/events.parquet`.

An object version represents a particular state of the object. With versioning enabled, replacing an object creates another version instead of destroying the previous version. This allows an application to retrieve an earlier state, investigate historical content, or recover from accidental overwrites.

Metadata describes the object without becoming part of its application payload. The examples distinguish content type, ownership, classification, service information, and retention information from the object bytes themselves.

## Buckets

A bucket is an administrative container for objects. The Python, JavaScript, C++, and Java implementations maintain bucket metadata separately from object records. The PostgreSQL model represents this relationship with the `buckets` and `objects` tables.

The database uses `bucket_id` as an internal identifier while enforcing a unique human-facing `bucket_name`. This avoids using a mutable textual name as the primary relational key for every child record.

The examples associate a region with each bucket. A real object-storage service may use the bucket's region to determine where data is physically or logically placed, which control-plane endpoints handle requests, and which data-residency policies apply.

A bucket is not equivalent to a directory. Object keys can contain delimiters such as `/`, but those delimiters are normally interpreted by clients as naming conventions rather than requiring an actual directory tree.

## Objects and Keys

An object key identifies an object within a bucket. Examples include:

`analytics/events.parquet`

`reports/monthly.json`

`audit/access.log`

The key is meaningful because lifecycle rules and application operations can use prefixes. A rule targeting `analytics/` can affect analytics objects without requiring every individual key to be listed.

The implementations validate empty keys and reject keys beginning with `/`. This is a deliberately small validation model. Production systems may impose additional naming restrictions depending on the object-storage service.

An object record is distinct from an object version. The object represents the logical key, while versions represent successive states associated with that key.

## Object Data and Metadata

An object can be understood as two closely related layers:

| Layer | Purpose | Example |
|---|---|---|
| Object data | Application payload | Parquet analytics dataset |
| System metadata | Storage-service attributes | Version identifier, size, storage class |
| User metadata | Application classification | `owner=data-platform` |
| Content metadata | Interpretation of bytes | `application/json` |
| Integrity metadata | Detection of unexpected modification | SHA-256 checksum |

The Python implementation calculates a SHA-256 digest for the uploaded bytes. The JavaScript implementation performs the same type of integrity calculation with Node's `crypto` module. The C++ and Java models represent checksums as object attributes, while the SQL schema validates the expected hexadecimal representation.

A checksum is useful for integrity verification, but it does not by itself establish confidentiality or authorization. Encryption, access control, transport security, and audit logging address different concerns.

## Versioning

Versioning changes the semantics of replacement and deletion.

With versioning enabled, writing a new object state creates another version. A logical object can therefore have:

`version A -> version B -> version C`

The current version is normally the most recent version that is not hidden by a delete marker.

The Python implementation exposes explicit version retrieval through `get_object(key, version_id)`. This is important because recovery often requires a specific historical state rather than merely the latest state.

The SQL schema stores versions in `object_versions`, with each version referencing the logical object through `object_id`. The index on `(object_id, created_at DESC)` supports operations that need the newest version.

Versioning also affects deletion. A versioned delete does not necessarily erase all historical data. The Python, JavaScript, and Java models represent the operation with a `DELETE_MARKER`. The logical object can become unavailable through an ordinary current-object lookup while historical versions remain available.

This distinction is important when designing recovery workflows. Removing a delete marker and permanently deleting an old version are different operations.

## Metadata Design

The relational implementation separates frequently queried object metadata from the version record:

`object_versions -> object_metadata`

The `object_metadata` table uses `(object_version_id, metadata_key)` as its primary key. This permits multiple metadata attributes while preventing duplicate keys for the same version.

Example metadata includes:

`owner = data-platform`

`classification = internal`

`service = identity`

`retention = regulated`

Metadata should be designed with a clear ownership model. System-controlled attributes such as size and storage class should not be treated as arbitrary application metadata. User metadata should also be validated when it drives retention, routing, or compliance behavior.

A metadata field that affects operational policy should have a well-defined meaning. Ambiguous metadata such as `important=true` is less useful than a policy-specific value such as `retention=regulated`.

## Lifecycle Policies

Lifecycle policies automate storage-state changes based on object age and key scope.

A lifecycle rule can combine a prefix with an age condition:

`analytics/ + age >= 30 days -> INFREQUENT_ACCESS`

Another rule can target:

`reports/ + age >= 90 days -> ARCHIVE`

The Python, JavaScript, C++, and Java implementations evaluate lifecycle policies against object age. The PostgreSQL implementation stores the rules in `lifecycle_rules` and provides `apply_lifecycle()` to perform a database-side transition.

Lifecycle management is useful because the access pattern of an object often changes over time. Recent analytics data may need frequent access, while historical reports may become rarely accessed but still need to remain available.

Transition and expiration are separate policy actions. A transition changes the storage class. Expiration removes or invalidates data according to the service's lifecycle semantics.

A production lifecycle policy must account for versioning. Expiring the current logical object does not automatically imply that every historical version should disappear. Version-aware retention rules are required when historical versions have independent retention requirements.

## Storage Classes

The examples use three conceptual storage classes:

| Storage class | Intended access pattern |
|---|---|
| `STANDARD` | Frequently accessed objects |
| `INFREQUENT_ACCESS` | Objects retained for occasional access |
| `ARCHIVE` | Long-term historical data |

These names are modeled locally and are not intended to claim that every provider uses identical pricing, retrieval latency, minimum-duration, or availability semantics.

The important architectural idea is that an object can retain its logical identity while its physical storage treatment changes. Lifecycle policy can therefore move an object between storage tiers without requiring the application to rename the object.

Storage-class selection is an operational decision involving access frequency, retrieval latency, availability requirements, retention duration, and cost.

## Control Plane and Data Plane

Object storage architecture commonly separates control-plane responsibilities from data-plane operations.

The control plane manages resources and configuration such as:

- Bucket creation and deletion
- Bucket properties
- Versioning configuration
- Lifecycle policies
- Metadata indexes
- Access policies
- Storage configuration

The data plane handles operations such as:

- Uploading object bytes
- Downloading object bytes
- Reading object metadata
- Deleting or versioning object data

The Python `ObjectStorageService` represents a simplified control plane. The actual object bytes are modeled as metadata and checksums rather than as a distributed storage implementation.

This distinction prevents a common architectural mistake: treating bucket configuration and object payload movement as the same subsystem. A production object store must coordinate metadata services with durable object storage without requiring every metadata operation to move the entire object payload.

## Python Implementation

The Python program builds an executable in-memory object-storage model.

`ObjectStorageService` owns buckets, while `Bucket` owns logical objects and lifecycle policies. `ObjectRecord` represents the logical object key and maintains a sequence of `ObjectVersion` instances.

The `put_object()` method calculates a SHA-256 checksum, creates a version identifier, records content type and metadata, and appends the new version. This demonstrates why an object replacement can be represented as a new state rather than an overwrite.

`get_object()` supports both current-object retrieval and explicit historical-version retrieval. This exposes the practical difference between a logical object and an individual version.

`delete_object()` demonstrates two different semantics. A version-specific deletion removes the selected version. A normal deletion under enabled versioning creates a delete marker.

`apply_lifecycle()` evaluates object age against prefix-based lifecycle rules. The demonstration moves reporting objects toward archival storage and audit data toward infrequent-access storage.

The script also uses a temporary filesystem object to demonstrate how application code can read bytes from a file before passing them to the object-storage abstraction. The temporary file is not treated as the persistent object store itself.

## JavaScript Implementation

The JavaScript implementation focuses on an event-oriented control-plane model.

Node.js `crypto` provides SHA-256 hashing, making checksum generation an actual runtime operation rather than a placeholder value. `Buffer` represents object data and allows byte length to be measured correctly.

The `ObjectVersion` class freezes user metadata so callers cannot accidentally mutate the metadata object after a version has been created.

Lifecycle processing is exposed through an asynchronous function, `simulateEventDrivenLifecycle()`. Lifecycle events are emitted through asynchronous scheduling using `setImmediate()`. This represents the event-driven nature of storage control operations without requiring an external message broker.

The JavaScript implementation also demonstrates `Map` for bucket and object registries. This is appropriate for direct key-based lookup of buckets and object records.

The implementation retains version history independently of the current object state. This makes explicit version retrieval and delete-marker behavior visible in the runtime model.

## C++ Repository-Style Case Study

The C++ program models an enterprise research-data object store.

`StorageControlPlane` manages buckets, while `Bucket` owns objects and lifecycle policies. `ObjectRecord` contains a vector of `ObjectVersion` objects, making version history explicit.

The case study uses analytics datasets and model artifacts because these objects commonly have large sizes, long retention periods, and changing access patterns.

The C++ implementation uses `std::map` for ordered object inventory and `std::unordered_map` for bucket lookup. Lifecycle policies are represented as typed structures rather than strings so transition targets are constrained to the `StorageClass` enumeration.

The `validateRequest()` function demonstrates a data-plane admission check that verifies the requested bucket, key, and minimum object size. This is deliberately different from simply printing an object list: the application evaluates a storage request against the state represented by the object store.

Exception-based failure handling is used for missing buckets, invalid keys, missing objects, and invalid lifecycle policies.

The program also demonstrates delete-marker semantics. A current-object lookup fails after a delete marker becomes the newest version, while the historical version records remain in the inventory.

The use of `std::optional<int>` for expiration policy demonstrates that expiration can be absent while transition behavior remains configured.

## Java Enterprise-Oriented Model

The Java program uses explicit domain types to model object-storage governance.

`Bucket`, `StoredObject`, and `ObjectVersion` represent separate domain concepts. `StorageClass`, `VersioningState`, and `ObjectState` make important states explicit instead of encoding them as arbitrary strings.

`LifecycleRule` is a record containing the policy's name, object prefix, transition duration, target storage class, and optional expiration duration. Its constructor validates the policy's basic invariants.

The `LifecycleExecutor` interface separates lifecycle evaluation from the bucket domain object. `DefaultLifecycleExecutor` provides the standard implementation. This design makes policy evaluation a distinct service responsibility rather than embedding every orchestration concern into the data model.

Java's immutable `Map.copyOf()` is used for version metadata. This prevents accidental mutation of metadata after the version has been created.

The program explicitly distinguishes current retrieval, specific-version deletion, logical deletion through a delete marker, and lifecycle transitions. These distinctions are important in enterprise systems where retention and recovery behavior must be predictable.

## SQL Data Model

The PostgreSQL implementation represents the storage hierarchy relationally:

`buckets -> objects -> object_versions -> object_metadata`

A bucket has many logical objects. An object has many versions. A version can have multiple metadata attributes.

The `buckets` table enforces unique bucket names and validates the basic bucket-name format.

The `objects` table uses a composite uniqueness constraint on `(bucket_id, object_key)`, allowing the same key to exist in different buckets while preventing duplicate logical objects inside one bucket.

The `object_versions` table stores version-specific size, checksum, content type, storage class, creation time, and state.

The `object_metadata` table allows multiple key-value attributes for each version while enforcing uniqueness of a metadata key within that version.

The `lifecycle_rules` table associates policy definitions with buckets and prefixes. Its constraints prevent incomplete transition definitions and invalid negative ages.

The `object_events` table provides an audit trail for storage operations and lifecycle changes.

## Current Version Querying

The `current_objects` view uses `ROW_NUMBER()` partitioned by `object_id` and ordered by creation time descending.

This gives the relational model a direct representation of the logical current state while retaining every historical version.

The view also exposes delete markers as state. A production implementation may apply additional semantics to determine whether a delete marker hides an object from ordinary listings.

This distinction matters because version history and current visibility are separate concepts.

## Database-Level Integrity

The SQL schema places several invariants in the database rather than relying entirely on application code.

`size_bytes >= 0` prevents negative object sizes.

The checksum constraint requires a 64-character lowercase hexadecimal value, matching the expected textual form of a SHA-256 digest.

Foreign keys prevent orphaned object versions and metadata.

The uniqueness constraint on `(bucket_id, object_key)` ensures that the logical object namespace is consistent.

The metadata primary key prevents two values from being stored under the same metadata key for one object version.

Lifecycle constraints prevent a transition rule from specifying an age without a target storage class.

These constraints are valuable because applications are not the only potential source of database writes. Multiple services, migrations, administrative jobs, and background workers may interact with storage metadata.

## Transactions

The SQL example uses a transaction around a storage-class update and its corresponding event record.

The important property is atomicity: the state change and its audit record are committed together. If the transaction fails before `COMMIT`, the database can roll both operations back.

The `FOR UPDATE` query demonstrates row-level locking before a policy-sensitive modification. This can prevent competing transactions from making conflicting updates to the same selected version.

Real object-storage systems use distributed coordination mechanisms rather than relying on a single relational transaction for the complete object-data path. The SQL transaction demonstrates governance of metadata, not the physical movement of object bytes.

## Lifecycle Processing in SQL

The `apply_lifecycle()` function searches for versions whose keys match an enabled lifecycle rule and whose age has crossed the configured threshold.

The function updates the storage class and records lifecycle-transition events.

This model highlights an important policy relationship:

`object age + object prefix + lifecycle rule -> storage state`

The policy does not need to know the application's internal representation of the object's content. It operates on storage metadata and object identity.

A production implementation needs to resolve overlapping rules explicitly. If multiple rules can apply to the same object, precedence, conflicting transitions, expiration behavior, and version-specific policies must be defined rather than left to update ordering.

## Architecture Relationships

The four central concepts interact at different layers:

| Mechanism | Primary responsibility | Relationship |
|---|---|---|
| Bucket | Namespace and administrative boundary | Contains logical objects |
| Object | Logical data identity | Identified by a key inside a bucket |
| Metadata | Object description and policy attributes | Describes a specific object or version |
| Versioning | Historical object states | Preserves successive object versions |
| Lifecycle policy | Automated storage management | Evaluates object metadata and age |
| Storage class | Storage treatment | Can change through lifecycle rules |

A lifecycle rule is not a replacement for versioning. Versioning answers the question of how historical states are retained. Lifecycle management answers the question of how object states are treated as they age.

Metadata is not the same as the object key. A key identifies an object. Metadata describes properties associated with the object or its version.

A bucket is not the same as a filesystem directory. Object keys may look hierarchical, but object storage can maintain a flat namespace internally while exposing prefix-based listing and policy operations.

## Failure Conditions and Edge Cases

An empty object is valid in the Python and JavaScript demonstrations. Object size therefore cannot be assumed to be positive merely because an object exists.

A missing object produces an explicit failure rather than returning an empty value. This avoids confusing an absent object with an object containing zero bytes.

A delete marker creates a state in which the logical object is hidden while historical versions can remain available.

Deleting a specific historical version is different from deleting the current logical object.

A bucket containing objects cannot safely be deleted in the demonstrated control-plane model. This prevents accidental removal of a namespace that still contains managed data.

Lifecycle age calculations require a consistent time basis. The examples use UTC timestamps so that policy evaluation does not depend on local machine time zones.

Overlapping lifecycle policies are another important edge case. A production policy engine must define precedence when two rules prescribe different transitions or retention periods.

## Performance Considerations

Object storage is designed around large-scale object access rather than arbitrary row-level updates inside an object.

The SQL model indexes `(object_id, created_at DESC)` because current-version queries repeatedly need the newest version for a logical object.

The object-key index supports bucket-local object lookup.

Lifecycle processing can become expensive when millions or billions of versions are evaluated. Production storage services generally use indexed metadata, partitioned background workers, event queues, or internal scheduling systems rather than scanning every object synchronously for every lifecycle evaluation.

Versioning also increases metadata volume. Retaining many versions can significantly increase storage consumption even when the current logical object has not changed frequently.

Metadata should therefore remain compact and operationally meaningful.

## Security Considerations

Object metadata can contain sensitive classification information even when the object payload is encrypted.

Checksums provide integrity information but are not an access-control mechanism. An attacker who can read an object may also be able to calculate its checksum.

Production object storage normally requires authentication, authorization, encryption in transit, encryption at rest, audit logging, and carefully scoped access policies.

Lifecycle policies can become security controls when they enforce retention or deletion requirements. Such policies must be protected against unauthorized modification.

Delete markers should not be treated as proof that data has been irreversibly destroyed. Historical versions, backups, replication targets, snapshots, or archival copies may continue to exist depending on the storage architecture.

## Common Architectural Mistakes

Treating object keys as ordinary filesystem paths can lead to incorrect assumptions about directories, rename operations, and atomicity.

Treating an overwrite as an irreversible mutation ignores the recovery semantics provided by versioning.

Using metadata as an unstructured dumping ground makes lifecycle and governance policies difficult to reason about.

Assuming that a delete operation immediately removes every historical copy can produce serious retention and compliance errors.

Running lifecycle scans synchronously in an application request path creates unnecessary latency and operational coupling. Lifecycle processing is normally better suited to asynchronous background execution.

Confusing storage classes with backups is also dangerous. A cheaper archival storage class can still be a primary copy rather than an independent backup strategy.

## Production Considerations

A production object-storage architecture must decide how object bytes are distributed, replicated, encrypted, addressed, and recovered. The examples intentionally stop at the metadata and control-plane boundary.

Large objects may require multipart or chunked upload mechanisms. The control plane must then track incomplete uploads and clean them up safely.

Durability requires redundant physical storage or equivalent fault-tolerance mechanisms. Metadata durability and object-data durability must be considered together because an object is unusable if either its bytes or the information required to locate them is lost.

Lifecycle execution should be idempotent. Re-running a transition should not corrupt an object or create an inconsistent metadata state.

Audit events should contain enough information to establish what changed, when it changed, and which object version was affected.

Version retention should be explicitly designed. Keeping every historical version indefinitely can produce unexpected cost and storage growth.

The code artifacts model these concerns at an educational system level while preserving the distinctions between logical objects, versions, metadata, lifecycle policies, and storage classes.
