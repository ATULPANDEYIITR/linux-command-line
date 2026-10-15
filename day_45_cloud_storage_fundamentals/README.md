# Cloud Storage Fundamentals

## Scope

Cloud object storage is designed around a separation between the data a customer logically stores and the physical mechanisms used by the storage platform to keep that data available and durable.

The implementations in this project focus on four closely related storage properties:

- **Durability** describes the probability that stored data remains intact over the storage service's stated durability period.
- **Availability** describes whether the service can successfully provide access to stored data when requested.
- **Redundancy** describes the existence of additional copies, fragments, or independent failure-domain resources that reduce the effect of individual failures.
- **Replication** is one specific redundancy mechanism in which data is maintained across multiple storage locations or storage resources.

These properties interact, but they are not interchangeable. Three replicas do not automatically mean three times the durability, and a durable object can still be temporarily unavailable.

## Object Storage Model

The Python, JavaScript, C++, and Java implementations use an object-storage model rather than a traditional block-device model.

An object consists of an application-visible key, content or logical size, metadata, and a storage class. The physical implementation is represented by replicas distributed across regions.

A simplified relationship is:

`logical object -> storage service -> failure-domain replicas`

The logical object can remain one object from the application's perspective even when the underlying service maintains multiple copies or other redundant representations.

The SQL implementation represents this relationship through `buckets`, `objects`, `replicas`, and `replica_health`.

## Durability

Durability concerns long-term preservation of data.

If a storage system has independent replica failure probability `p` and requires all `n` replicas to be lost before the object is lost, a simplified model for simultaneous loss is:

`P(data loss) = p^n`

For example, if the individual annual failure probability were hypothetically `0.001` and three failures were independent:

`0.001^3 = 0.000000001`

This is an educational model, not a provider SLA calculation. Real cloud storage systems use mechanisms such as multiple failure domains, erasure coding, integrity verification, background repair, metadata protection, and operational recovery processes.

The Python, JavaScript, C++, and Java programs expose this simplified probability calculation so the effect of replica count can be observed directly.

## Availability

Availability is concerned with successful access during an operational interval.

For independent replicas with availability `a`, a simplified model for at least one available replica is:

`P(system available) = 1 - (1 - a)^n`

With three independent replicas, the probability that all three are simultaneously unavailable becomes much smaller than the probability that one individual replica is unavailable.

The important operational distinction is that a storage system can be:

- **Available** when enough healthy replicas can serve requests.
- **Degraded** when some redundancy has been lost but at least one healthy replica remains.
- **Unavailable** when no usable replica remains.

The simulations intentionally expose the degraded state. This matters because a system that continues serving data after one failure may still have increased risk until repair restores its redundancy.

## Redundancy and Replication

Redundancy is the broader design principle of maintaining alternative resources.

Replication is one implementation of that principle.

For example, an object replicated across Mumbai, Singapore, and Frankfurt has multiple geographic locations represented in the demonstrations. If Mumbai becomes unavailable, the other replicas can continue serving the object.

The location of replicas is important. Three copies within one failure domain do not provide the same protection against a failure that affects the entire domain.

Redundancy can also be implemented through techniques other than literal full copies, including erasure coding. The implementations use explicit replicas because that representation makes the relationship between failures and availability clear.

## Failure Domains

A failure domain is a set of resources that can be affected by a common failure.

Examples include:

- A storage node.
- A rack or host group.
- An availability zone.
- A geographic region.
- A network segment.
- A control-plane dependency.

Replication is most useful when replicas are sufficiently independent. Placing three replicas in the same failure domain can leave all three vulnerable to one common event.

The Python simulation models regions directly. The C++ case study uses three regional locations for market-data snapshots. The Java model represents regions as part of the storage service domain. The SQL model records replica-to-region relationships explicitly.

## Python Implementation

The Python program provides the most direct simulation-oriented representation.

`CloudStorageBucket` maintains objects and their replicas. `StorageObject` records the logical object properties, while `Replica` represents an independently modeled copy associated with a region.

The `put()` method validates the object key and content size before creating the configured replicas. This demonstrates the distinction between logical insertion and the storage service's internal redundancy.

`simulate_region_failure()` marks replicas in a region unhealthy without deleting the logical object. This is important because a regional failure does not necessarily mean data loss. The object's availability depends on whether healthy replicas remain.

`availability_status()` explicitly distinguishes `AVAILABLE`, `DEGRADED`, and `UNAVAILABLE`.

The Python program also contains separate `DurabilityModel` and `AvailabilityModel` classes. This prevents the two concepts from being collapsed into one metric.

The validation examples demonstrate configuration errors, missing objects, invalid object keys, and complete loss of healthy replicas.

The cost calculation shows another important storage distinction: logical capacity and replicated physical capacity are not necessarily equal. If one logical GiB is represented by three complete replicas, the simplified physical equivalent is approximately three GiB before provider-specific compression, erasure coding, metadata overhead, or other implementation details.

## JavaScript Implementation

The JavaScript implementation uses Node.js event-driven behavior to model storage events.

`ObjectStore` extends `EventEmitter`. Storage operations emit events such as `objectStored`, `regionFailure`, `regionRecovered`, and `objectRead`.

This provides a useful perspective for operational systems because storage failures often generate events that monitoring, alerting, repair, and orchestration components consume asynchronously.

The `healthCheck()` method is asynchronous. It uses a short asynchronous delay to represent an external or network-bound health operation. The result reports the number of healthy replicas and the resulting availability state.

The implementation uses Node's `crypto` module to calculate a SHA-256 content hash. The hash demonstrates how integrity metadata can be associated with stored content. A cryptographic hash is not itself a replication mechanism, but integrity verification is important to reliable storage systems.

`StorageGovernancePolicy` evaluates minimum replication and multi-region requirements separately from the storage engine. This demonstrates the distinction between storage behavior and organizational policy.

## C++ Case Study

The C++ implementation models a financial analytics repository that stores daily market-data snapshots.

`RepositoryStorage` maintains objects and explicit regional replicas. The case study is deliberately more system-oriented than the Python simulation.

The storage service tracks:

- Logical object size.
- Storage class.
- Replica regions.
- Replica health.
- Logical capacity.
- Replicated capacity.
- Regional failure.
- Regional recovery.
- Availability state.

The `failRegion()` operation changes the health of replicas belonging to the selected region. The object remains present while the surviving replicas determine whether it is still available.

`physicalCapacityBytes()` demonstrates the capacity consequence of full replication. The logical dataset size is multiplied by the number of replicas in the simplified model.

`StoragePolicy` represents a governance layer that checks minimum replication and multi-region requirements. This separates technical storage state from the policy that determines whether that configuration is acceptable.

The program also uses exception handling for invalid configurations, unknown regions, invalid object keys, and invalid object sizes.

The C++ implementation intentionally notes that its mathematical durability model is simplified. A real cloud platform may use erasure coding and distributed repair rather than maintaining a complete independent copy of every object.

## Java Implementation

The Java implementation uses an enterprise-oriented domain model.

`StorageObject`, `Replica`, and `ProtectionPolicy` are records representing immutable domain values where appropriate.

`StoredObject` owns the replica state for an object and exposes domain operations such as region failure, region recovery, healthy-replica counting, and availability evaluation.

`StorageService` acts as the application service responsible for storing and retrieving objects, validating regions, evaluating policies, and handling availability.

The `ReplicaState` enum distinguishes `HEALTHY`, `FAILED`, and `REPAIRING`. Representing these as explicit states is more precise than using arbitrary strings because invalid state names are prevented by the type system.

`AvailabilityState` separates the service-level availability result from individual replica health.

`ProtectionPolicy` represents requirements such as minimum replicas, multi-region placement, and encryption. `StoragePolicyResult` returns the compliance state together with specific violations.

The Java program also uses `ConcurrentHashMap` for the object registry. This reflects the fact that storage-service metadata can be accessed by concurrent operations in an enterprise service, although a production implementation would require a much broader concurrency and consistency design.

## SQL Data Model

The PostgreSQL schema models storage governance as relational data.

The principal entities are:

| Entity | Purpose |
|---|---|
| `regions` | Defines geographic storage locations and whether they are active. |
| `buckets` | Represents logical storage containers and their replication configuration. |
| `branch_protection` | Stores storage governance requirements such as minimum healthy replicas and encryption requirements. |
| `replicas` | Associates buckets with regions and records replica state. |
| `objects` | Stores object-level metadata such as size, key, hash, and storage class. |
| `replica_health` | Records integrity verification for an object replica. |
| `reviewers` | Provides operational identities for review-related storage governance records. |
| `reviews` | Records storage review decisions and comments. |
| `status_checks` | Represents machine-evaluated storage checks. |
| `storage_events` | Provides an operational event history. |

The database uses foreign keys to prevent references to nonexistent buckets, regions, objects, or replicas.

`CHECK` constraints restrict replica state and storage class values. This places basic integrity rules inside the database instead of requiring every application to implement them independently.

The `replicas` table has a unique constraint on `(bucket_id, region_id)`, preventing duplicate regional replica records for the same bucket.

Indexes are created around common operational access patterns, including replica health by bucket, replica verification by object, object storage class, and recent storage events.

## Database-Level Availability Evaluation

The `object_storage_health` view calculates the current state of each object from relational data.

It counts configured replicas and healthy replicas and derives:

- `AVAILABLE` when all configured replicas are healthy.
- `DEGRADED` when at least one replica remains healthy but the configured replica count is not fully healthy.
- `UNAVAILABLE` when no healthy replica remains.

This is different from simply storing an availability string on the object. The view derives the state from the underlying replica records, reducing the chance that an application-maintained status field becomes stale.

The same view also exposes the number of distinct replica regions. This permits queries to distinguish replication count from geographic diversity.

## Integrity and Checksums

The SQL schema stores a SHA-256 value for each object.

The JavaScript implementation calculates SHA-256 directly using Node's cryptographic library. The Python program also calculates SHA-256 using the standard library.

A checksum can detect unintended content changes when the stored content is later verified against the expected digest.

A checksum does not guarantee durability. It answers a different question:

`Does the retrieved content match the expected content?`

Durability asks:

`Does the storage system preserve the content over the relevant failure period?`

Availability asks:

`Can the application retrieve the content when it needs it?`

These questions must not be treated as equivalent.

## Storage Classes

The examples distinguish:

- `standard` for frequently accessed operational data.
- `infrequent-access` for data accessed less often where lower storage cost can justify different retrieval characteristics.
- `archive` for long-retention information where access frequency is low.

A storage class is a service-level storage choice, not a synonym for durability.

An archive class may be designed for high durability while still imposing longer retrieval times or different operational constraints.

The Python, JavaScript, C++, Java, and SQL implementations use storage classes only where they contribute to the storage model rather than turning them into a generic enumeration exercise.

## Replication Factor and Capacity

If an application stores 250 GiB and the simplified design uses three full replicas:

`logical capacity = 250 GiB`

`replicated capacity = 250 × 3 = 750 GiB`

Actual cloud billing cannot be inferred from this equation alone. Providers may use erasure coding, compression, metadata overhead, minimum billing units, storage-class pricing, replication policies, and other mechanisms.

The calculation is useful for understanding why redundancy has a resource cost.

## Degraded State and Repair

A failed replica should not automatically be interpreted as data loss.

Consider an object with three healthy replicas:

`Mumbai + Singapore + Frankfurt`

If Mumbai fails:

`failed Mumbai + healthy Singapore + healthy Frankfurt`

The object can remain available while its redundancy is degraded.

A mature storage service would normally initiate repair or reconstruction so the system does not remain permanently exposed to the reduced redundancy level.

This is one reason durability depends on more than the number of initial copies. Repair speed, detection, monitoring, integrity verification, and failure-domain design all influence long-term resilience.

## Durability Versus Availability

The distinction can be expressed through failure scenarios.

A regional network outage can make a replica inaccessible without destroying the stored data. This can reduce availability without immediately reducing the long-term durability of the object.

A catastrophic event that destroys all surviving copies can affect durability.

A temporary service-control problem can affect availability even when the underlying data remains intact.

Consequently, a storage architecture should not evaluate both properties using one number.

## Redundancy Versus Replication

Replication is a concrete mechanism. Redundancy is the broader architectural objective.

Full replication creates complete copies.

Other redundancy mechanisms can distribute encoded fragments across failure domains. Erasure coding can provide resilience with less raw storage overhead than maintaining complete copies, but it introduces reconstruction and coding complexity.

The examples intentionally use explicit replicas because the relationship between failure and recovery is easier to observe.

## Availability, RTO, and RPO

Availability is related to but distinct from recovery objectives.

**RTO**, or Recovery Time Objective, specifies how quickly service should be restored after a disruptive event.

**RPO**, or Recovery Point Objective, specifies the maximum acceptable amount of data loss measured in time.

For example, an application could require:

`RTO <= 15 minutes`

and

`RPO <= 5 minutes`

Replication may help meet these objectives, but replication alone does not guarantee them.

Synchronous and asynchronous replication have different trade-offs. Synchronous approaches can provide stronger write durability across failure domains but can increase write latency and depend on network conditions. Asynchronous approaches can reduce write latency while leaving a window in which the newest data may not yet exist at another location.

## Common Failure Modes

### Single-region redundancy

Multiple replicas placed in one failure domain may all become inaccessible during a common regional event.

### Insufficient replica repair

A system that continues operating after one failure but does not repair the missing redundancy becomes progressively more exposed to subsequent failures.

### Treating availability as durability

A temporarily unavailable object is not necessarily lost.

### Treating replication count as a complete durability guarantee

Three copies provide a simplified redundancy model, but actual durability depends on placement, implementation, repair, correlated failures, and provider architecture.

### Ignoring integrity verification

A replica can exist while its content is corrupted. Storage systems therefore need integrity verification mechanisms in addition to redundancy.

### Assuming a backup is the same as a replica

A replica is generally part of the storage service's operational redundancy mechanism. A backup is intended to provide a recoverable historical or independent copy. A deletion or corruption event can propagate to replicas, so independent backup strategy may still be necessary.

## Performance Considerations

Replication introduces additional work.

Writes may need to reach multiple storage locations or be encoded into multiple fragments. Cross-region replication can introduce network latency and bandwidth consumption.

Reads can potentially benefit from geographic proximity because a service may select an accessible replica near the requester.

Health checking and repair also consume resources. A storage platform must balance rapid failure detection against the cost of monitoring very large numbers of objects and replicas.

Indexes in the SQL implementation are targeted at operational queries rather than added indiscriminately. Indexes improve lookup performance but consume storage and impose write-maintenance overhead.

## Security Considerations

Cloud storage reliability does not replace security controls.

Encryption protects confidentiality but does not by itself provide durability.

Access control determines who can read, write, delete, or configure storage.

Versioning can reduce the effect of accidental overwrites or deletions, but it can also increase retained storage volume.

Audit events help identify changes to storage configuration and object operations.

The SQL model stores encryption policy requirements alongside storage governance because the decision to permit an object should consider both resilience and security requirements.

## Production Design Considerations

A production cloud storage architecture should define the failure domains that matter to the application rather than selecting a replica count in isolation.

The design should establish:

- The acceptable durability requirement for each data category.
- The availability requirement for operational reads and writes.
- The geographic or zonal failure domains that require independence.
- The RPO and RTO required by the application.
- The repair behavior after a replica failure.
- The integrity verification mechanism.
- The retention and deletion model.
- The backup strategy for accidental deletion or logical corruption.
- The encryption and access-control requirements.
- The monitoring and alerting thresholds for degraded redundancy.

The implementations in this project intentionally simplify provider internals while keeping these architectural distinctions visible.

## Relationship Between the Six Deliverables

The Python implementation emphasizes executable simulation and validation. It makes replica failure and availability states easy to observe.

The JavaScript implementation emphasizes event-driven storage operations and asynchronous health checks. Its event emitter model is useful for understanding how operational systems can react to storage failures.

The C++ implementation treats storage as a technical case study for a market-data platform. It focuses on capacity calculations, regional failure, policy evaluation, and explicit resource management.

The Java implementation models storage as an enterprise domain. Explicit records, enums, policy objects, and service methods make storage states and governance rules part of the domain model.

The SQL implementation moves the storage model into the database. Constraints, relationships, indexes, views, transactions, and queries show how storage integrity and operational state can be enforced and evaluated at the relational layer.

Together, these implementations demonstrate the same storage fundamentals from different technical perspectives without treating durability, availability, redundancy, and replication as interchangeable concepts.
