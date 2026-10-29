# Database Replication: Primary-Replica Architecture, Synchronization, and Failover

## Scope

This learning artifact models database replication as a distributed data-management workflow. The implementations distinguish four related but separate concerns:

| Area | Meaning |
|---|---|
| Primary | The authoritative node that accepts writes under normal operation |
| Replica | A secondary node that receives and applies replicated changes |
| Synchronous replication | A write acknowledgement depends on configured synchronous replica durability |
| Asynchronous replication | A replica can apply changes after the primary has accepted the write |
| Replication lag | The difference between the primary's latest durable position and a replica's applied position |
| Failover | Promotion of an eligible replica when the primary becomes unavailable |

The central relationship is:

Primary write → WAL/change position → replication transport → replica apply → durability or read eligibility → failover decision

The model intentionally distinguishes a logical replication-management model from the internal implementation of a database engine. The PostgreSQL script records replication state and WAL-like positions; it does not replace PostgreSQL's server-level WAL sender, receiver, storage, or recovery processes.

## Primary-Replica Architecture

A primary-replica topology separates write authority from replicated read or recovery capacity.

Plain-text topology:

    Application
        |
        v
    Primary
        |
        +--------------------+
        |                    |
        v                    v
    Sync Replica        Async Replica
        |                    |
    low durability       possible lag
    acknowledgement      eventual apply

The primary maintains the authoritative write sequence. Every accepted change receives an ordered position. Replicas consume those changes and advance their applied position.

The Python implementation uses `WalEntry` objects and a `ReplicationCluster` to model this sequence. The JavaScript implementation uses immutable transaction objects and `Map` collections. The C++ program represents the WAL using STL vectors and explicitly controls node state. Java models the domain with records, service classes, policies, and concurrent collections. PostgreSQL stores replication positions and receipts relationally.

A primary is not simply another replica with a different name. It owns the normal write path. Promotion changes the authority model and therefore requires explicit state transition handling.

## Replication Positions

The examples use monotonically increasing WAL positions to make replication state observable.

If the primary is at position 105 and a replica has applied position 101:

    replication lag = 105 - 101 = 4

A replica at position 105 has caught up with the primary's represented workload.

The position is useful for:

- measuring lag
- determining whether a replica is sufficiently current for a read
- selecting a candidate during failover
- verifying synchronous durability
- detecting degraded replication
- identifying recovery gaps

A position alone does not guarantee every property of a real database system. Actual durability also depends on storage, WAL flushing, transaction semantics, configuration, and failure boundaries.

## Synchronous Replication

Synchronous replication places a replica acknowledgement requirement on the write path.

The Python model writes a WAL entry, sends it to replicas, and applies the entry on synchronous replicas before considering the write acknowledged.

The C++ implementation makes this decision explicit through `writeAcknowledged`. A write is acknowledged only when every configured synchronous replica has applied the relevant position.

The Java implementation isolates this rule in `SynchronousDurabilityPolicy`. This separates domain policy from the mechanics of storing and applying transactions.

Conceptually:

    Client
      |
      | write
      v
    Primary
      |
      | replicate
      v
    Synchronous Replica
      |
      | applied
      v
    acknowledgement
      |
      v
    Client

The major benefit is a smaller exposure window for acknowledged data when the primary fails. The trade-off is that write latency and availability can depend on synchronous replica health and network conditions.

A synchronous configuration therefore requires careful consideration of:

- replica availability
- network latency
- acknowledgement semantics
- storage durability
- quorum or required-replica configuration
- behavior when synchronous replicas become unavailable

## Asynchronous Replication

Asynchronous replication separates primary write acknowledgement from replica application.

The primary can accept a transaction while the replica still has pending work.

The Python implementation represents pending entries with a list and advances the asynchronous replica through `async_tick`.

The JavaScript implementation uses an asynchronous method, `processAsyncReplication`, and a timer-backed Promise to represent delayed application.

The C++ program exposes an explicit replication-processing batch. The Java service provides `processAsync`.

The model therefore makes the consistency distinction visible:

    Primary position:       105
    Async replica position: 101
    Lag:                      4

An asynchronous replica may be useful for:

- read scaling
- reporting workloads
- geographically distant replicas
- disaster recovery
- workloads where write latency is more important than immediate replica visibility

The cost is potential stale data.

## Read Consistency and Stale Replicas

A replica should not automatically be treated as current.

The implementations support a minimum required replication position. A read can require the selected replica to have reached a specified position.

For example:

    required position = 105
    replica position  = 101

The read is rejected because the replica cannot prove that it has applied the required state.

This pattern is useful when an application needs read-after-write behavior while still using a replica.

The Python and C++ implementations explicitly raise or report lag failures. JavaScript reports a replication error. Java exposes the rule through the service's read operation.

A production system may use stronger consistency mechanisms depending on the database and workload, but the principle remains important: replica availability and replica freshness are separate properties.

## Failover

Failover changes which node has write authority.

Normal state:

    primary-01  -> writable
    sync-01     -> replica
    async-01    -> replica

After primary failure:

    primary-01  -> failed
    sync-01     -> candidate
    async-01    -> candidate

After promotion:

    sync-01     -> writable primary
    async-01    -> replica
    primary-01  -> failed or recovery candidate

Promotion must not be treated as merely changing a string field. The promoted node must have an appropriate data position, must be available, and must become the unique active authority.

The Python model copies the promoted replica's state into the new primary state. The C++ program performs the same state transition using explicit node objects. Java's `ReplicationService` uses a synchronized promotion operation and copies the candidate snapshot into the primary state. PostgreSQL performs the transition transactionally by changing node roles and recording a failover event.

## Failover Candidate Selection

A good failover candidate should be evaluated using operational state rather than name or static priority alone.

The examples consider:

- node availability
- replication mode
- applied position
- node health
- current primary position
- configured replication policy

A synchronous replica that has reached the latest primary position is generally a stronger candidate than a lagging asynchronous replica for a controlled promotion.

The PostgreSQL failover query selects the most advanced healthy synchronous replica. The C++ and application-language models explicitly reject unavailable replicas.

Real deployments may include additional candidate attributes such as geographic placement, storage health, connection reachability, recovery state, promotion priority, and fencing status.

## Split-Brain Risk

Failover introduces a critical distributed-systems problem: two nodes must not simultaneously believe they are authoritative writable primaries.

A safe promotion procedure therefore needs an authority transition rather than simply starting writes on a replica.

Important controls include:

- detecting primary failure reliably
- preventing the old primary from accepting writes
- fencing or isolating the old primary where necessary
- selecting one promotion candidate
- recording the failover event
- redirecting clients to the new primary
- rebuilding or rejoining the old primary safely

The examples model the old primary as failed before promotion. This is a logical simulation of fencing, not a substitute for infrastructure-level fencing.

## Recovery and Rejoining

A failed primary cannot safely reappear as an independent writable primary with old state.

The Python implementation illustrates the principle in `reconnect_old_primary`: the old primary is treated as a replica candidate after failover rather than immediately reclaiming write authority.

A production recovery process may require:

1. isolating the old primary
2. determining its last valid position
3. reconciling missing changes
4. rebuilding or resynchronizing it
5. verifying replication health
6. adding it back as a replica
7. only promoting it later through a controlled procedure

This prevents divergent histories from being accepted as one authoritative database state.

## Python Implementation

The Python program models replication behavior directly with dataclasses and enumerations.

`WalEntry` represents an ordered change. `Replica` maintains its applied position, local data, and pending queue. `ReplicationCluster` owns the primary state, WAL sequence, replicas, reads, writes, lag calculation, and failover operations.

Important mechanisms include:

- synchronous application before write acknowledgement
- asynchronous application through explicit ticks
- minimum-position reads
- stale-replica rejection
- primary failure
- replica promotion
- validation of keys and values
- explicit replication exceptions
- final status inspection

The use of dictionaries provides constant-time average lookup for the simulated key-value state. Pending replication is represented as an ordered list, which is appropriate for the small deterministic learning model but would not be a replacement for a production WAL queue.

## JavaScript Implementation

The JavaScript implementation focuses on event-driven replication behavior.

`ReplicationCluster` extends `EventEmitter`. It emits events for writes, replication activity, failures, and promotions.

JavaScript-specific mechanisms include:

- `Map` for node and database state
- `Set`-like collection behavior through map traversal
- immutable transaction records with `Object.freeze`
- asynchronous replication through Promises
- event-driven state notifications
- explicit input validation
- bounded key and value sizes
- asynchronous batch processing

The event model separates state changes from observers. A monitoring component could subscribe to write, failure, and promotion events without modifying the replication engine itself.

## C++17 Implementation

The C++ program presents replication as a deterministic systems-engineering case study.

`ReplicationCluster` manages the primary, WAL records, replica nodes, and promotion operations. `ReplicaNode` contains its replication mode, role, health state, applied position, pending queue, and local data.

C++17 features include:

- strongly typed enumerations
- STL `map` and `vector`
- `std::optional` for missing values
- explicit exception handling
- value-oriented WAL records
- bounded input validation
- deterministic batch application
- explicit state transitions

The program uses ordered containers and sequential WAL application to make correctness visible. A production database would require substantially more sophisticated concurrency, storage, locking, crash recovery, and network mechanisms.

## Java 17 Implementation

The Java implementation emphasizes enterprise domain modeling.

The `WalEntry` record represents immutable transaction metadata. `ReplicaNode` represents a replication participant. `ApprovalPolicy` defines a policy abstraction, and `SynchronousDurabilityPolicy` evaluates whether a synchronous replica has reached the required position.

`ReplicationService` coordinates:

- primary writes
- WAL creation
- synchronous durability
- asynchronous application
- replica reads
- primary failure
- promotion
- status reporting

The service methods explicitly distinguish normal write processing from failover.

Java's `ConcurrentHashMap` is used for shared key-value state, while synchronized methods protect critical transitions involving WAL sequencing and promotion.

The policy abstraction is intentionally separate from the storage model. This makes it possible to introduce alternative durability policies without embedding all rules directly into the replication service.

## PostgreSQL Implementation

The PostgreSQL script creates a `replication_lab` schema and models operational replication metadata.

Key tables include:

| Table | Purpose |
|---|---|
| `repository` | Logical database or application ownership boundary |
| `database_node` | Primary and replica identity, role, health, mode, and position |
| `replication_transaction` | Ordered WAL-like transaction metadata |
| `replication_receipt` | Records replica application of transactions |
| `branch` | Example protected application branch metadata |
| `replication_policy` | Required synchronous replicas and maximum asynchronous lag |
| `failover_event` | Auditable record of primary replacement |

The `database_node` table uses an enumerated role, replication mode, and state. Constraints prevent an ordinary replica from omitting its replication mode and prevent a primary from declaring itself a synchronous or asynchronous replica.

The partial unique index `one_active_primary_per_repository` prevents more than one non-failed primary from being active for the same repository in the represented model.

The `calculate_replication_lag` function computes the difference between the latest transaction position and a node's current position.

The `record_replication_apply` function advances replica state and creates an application receipt. The transactional section demonstrates how a new replication transaction and synchronous receipt can be committed together.

The failover transaction marks the old primary as failed, promotes the most advanced healthy synchronous replica, and records the event.

## Database-Level Integrity

The relational model demonstrates rules that are better enforced by the database than by application convention alone.

Examples include:

- primary keys for entity identity
- foreign keys for relationship integrity
- unique repository and node names
- enumerated state values
- non-negative replication positions
- unique WAL positions per repository
- unique replication receipts
- one active primary per repository
- role and replication-mode validation

This reduces the probability that independent application processes create contradictory metadata.

Database constraints should still be paired with operational controls. A relational metadata model cannot itself fence an unreachable database server.

## Failure Modes

The implementations explicitly model several failure conditions.

| Failure | Represented response |
|---|---|
| Primary unavailable | New writes are rejected |
| Replica unavailable | Replica reads and promotion are rejected |
| Replica lagging | Freshness-constrained reads are rejected |
| Invalid write key | Validation error |
| Excessive value size | Validation error |
| Unknown promotion target | Promotion failure |
| Failed replica promotion | Promotion failure |
| Missing synchronous durability | Write acknowledgement failure |
| Primary failure | Failover process begins |
| Divergent old primary | Old primary is not immediately restored as authority |

A real deployment would also need to handle network partitions, storage failure, corrupted WAL, clock differences, process crashes, connection exhaustion, replication slots, authentication, TLS, monitoring, backup recovery, and operational fencing.

## Performance Considerations

Replication adds work to the write and recovery path.

Synchronous replication can increase write latency because the primary waits for the configured durability condition.

Asynchronous replication reduces write-path dependency on replicas but can increase read staleness and recovery-point exposure.

The application-language simulations use in-memory maps for state lookup. Their average key lookup is approximately O(1), while ordered WAL application is O(n) for a batch of `n` sequential entries.

The PostgreSQL model uses indexes for identity and repository-specific lookup. The partial primary index is particularly important because primary uniqueness is a high-value integrity rule and should not depend only on application code.

Large production replication systems require careful consideration of:

- WAL generation rate
- network bandwidth
- replica apply throughput
- storage I/O
- queue depth
- checkpoint behavior
- replication lag
- read workload distribution
- failover time
- recovery time objective
- recovery point objective

## Security Considerations

Replication traffic can contain sensitive application data. A production design should protect:

- database credentials
- replication authentication
- network connections
- WAL transport
- administrative promotion operations
- failover credentials
- monitoring endpoints
- backup and recovery artifacts

Least privilege is important. A replication account should have only the permissions required for replication operations.

Failover should be an authenticated and auditable administrative operation. Automated promotion should have explicit safeguards against simultaneous promotion by independent controllers.

Input validation in the Python, JavaScript, C++, and Java programs demonstrates a basic application boundary. The PostgreSQL constraints provide a second layer of protection against invalid internal state.

## Educational Distinctions

The four central concepts should not be collapsed into one mechanism.

| Concept | Primary question |
|---|---|
| Primary-replica architecture | Which node normally accepts writes, and which nodes receive copies? |
| Synchronous replication | What replica durability condition must be satisfied before acknowledgement? |
| Asynchronous replication | Can the primary acknowledge before a replica has applied the change? |
| Failover | Which eligible replica becomes the new write authority after primary failure? |

They form a workflow:

    Write
      |
      v
    Primary
      |
      +---- synchronous durability ----> acknowledgement
      |
      +---- asynchronous transport ----> eventual replica state
      |
      v
    Failure detection
      |
      v
    Candidate evaluation
      |
      v
    Promotion
      |
      v
    New primary

The separation is essential. Replication mode determines how changes are propagated and acknowledged. Failover determines how authority changes after failure. Replica freshness determines whether a replica can safely serve a consistency-sensitive read.

## Practical Limitations

These implementations are educational models rather than database engines.

They do not implement:

- physical disk persistence
- crash-safe WAL flushing
- actual network replication
- PostgreSQL streaming replication
- replication slots
- timeline history
- quorum consensus
- distributed locking
- fencing hardware
- automatic DNS or service discovery
- connection pool redirection
- point-in-time recovery
- encrypted replication channels

The PostgreSQL script intentionally models replication metadata instead of attempting to reproduce PostgreSQL server internals using SQL tables.

The most important transferable principle is that replication state must be observable, validated, and governed. A replica is useful only when its freshness, health, and role are known, and a failover is safe only when authority is transferred without allowing conflicting writers.
