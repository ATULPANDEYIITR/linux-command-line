# Database Infrastructure Fundamentals

## Scope

This project models the infrastructure mechanisms that make a relational database server reliable under normal workload, failure, replication, and recovery conditions.

The five implementations use the same technical domain from different engineering perspectives:

| Area | Primary concern | Implemented mechanisms |
|---|---|---|
| Storage | How durable data is organized | Pages, records, snapshots, restore |
| Transactions | How changes become atomic | Transaction states, staged writes, commit, rollback |
| WAL | How committed changes survive crashes | Log sequence numbers, log records, replay |
| Replication | How database state is copied | Primary, replicas, queues, replay, lag |
| Availability | How service continues after failure | Health state, recovery, failover |
| Consistency | When replicas acknowledge writes | Asynchronous and synchronous replication |
| Operations | How infrastructure is monitored | Checkpoints, health reports, eligibility checks |

The central relationship is:

`Database Server → Storage → Transaction → WAL → Replication → Recovery → Availability`

A transaction represents a logical unit of work. Storage holds the resulting state. WAL records the change history needed for recovery. Replication transports committed changes to other servers. Availability depends on the health and freshness of those servers.

## Database Server Fundamentals

A database server provides the execution and persistence boundary for database operations. It normally manages client connections, transactions, memory, storage access, logging, concurrency, background maintenance, and recovery.

The implementations model two server roles:

- `PRIMARY` accepts application writes.
- `REPLICA` receives changes from a primary and normally does not accept independent application writes.

The Python, JavaScript, C++17, and Java implementations enforce this distinction in their transaction commit paths.

The PostgreSQL implementation stores the role explicitly in `database_server` and uses a partial unique index to ensure that a cluster cannot contain multiple primary servers.

A production database server contains many components that are intentionally simplified here:

`Client`
`  ↓`
`Connection / Session`
`  ↓`
`Transaction Manager`
`  ↓`
`Buffer / Storage Manager`
`  ↓`
`WAL`
`  ↓`
`Persistent Storage`

The simulation separates these responsibilities enough to show why each exists.

## Storage Engines

A storage engine determines how logical database records become persistent physical structures.

The source implementations use pages as the basic storage unit. Each page has a capacity and contains multiple records. When a page becomes full, another page is allocated.

The simplified model is:

`Database Record`
`      ↓`
`Storage Page`
`      ↓`
`Storage Engine`

The Python implementation uses `StoragePage` objects containing dictionaries.

The JavaScript implementation uses `Map` objects inside `Page` instances.

The C++ implementation stores records in STL unordered maps inside `Page` structures.

The Java implementation uses a list of maps to represent pages.

The PostgreSQL model uses the `storage_page` table with:

- page identifier
- server ownership
- page number
- capacity
- used slots
- checksum

The page model is intentionally simple. Real database engines commonly use buffer pools, page headers, tuple metadata, free-space maps, indexes, page checksums, compression, background flushing, and crash-safe page management.

### Storage lookup

The educational storage implementations perform page scans.

If there are `P` pages, a lookup can require `O(P)` page checks.

Production database systems normally avoid this cost by using indexes. An index maps search keys to physical or logical locations so that common lookups do not scan every page.

The important infrastructure distinction is:

`Logical key`
`    ↓`
`Index`
`    ↓`
`Page / Record`

rather than:

`Logical key`
`    ↓`
`Every page`
`    ↓`
`Matching record`

## Transactions

A transaction groups database operations into a logical unit.

The implementations model three transaction states:

| State | Meaning |
|---|---|
| `ACTIVE` | Operations may still be staged |
| `COMMITTED` | The transaction has successfully completed |
| `ABORTED` | The transaction has been cancelled |

The permitted state transitions are:

`ACTIVE → COMMITTED`

or

`ACTIVE → ABORTED`

A committed or aborted transaction cannot be reused.

The source implementations stage changes before applying them to storage. A storage snapshot is retained during the commit operation so that a failure can restore the previous state.

This models the atomicity requirement of transactions.

### Atomicity

Atomicity means a transaction is treated as one logical unit. Its changes should not appear partially committed.

For example, a transfer may contain:

`Debit account A`
`Credit account B`

The database should not expose a durable state in which the debit succeeds while the credit permanently fails.

The implementations model this by applying all staged writes and restoring the previous storage snapshot if an exception occurs.

A production database uses more sophisticated mechanisms, such as transaction logs, locking or multi-version concurrency control, undo information, and crash recovery.

### Isolation

The PostgreSQL model stores the declared isolation level:

- `READ COMMITTED`
- `REPEATABLE READ`
- `SERIALIZABLE`

The Java implementation represents transaction behavior as an explicit domain type and service-oriented model.

The in-memory implementations do not reproduce a complete database concurrency-control system. They focus on the infrastructure relationship between transactions, storage, and recovery.

## Write-Ahead Logging

Write-ahead logging means the database records the information needed to recover a change before relying on the modified data page as the durable representation of that change.

The simplified sequence is:

`Transaction`
`    ↓`
`Create WAL record`
`    ↓`
`Persist / retain WAL`
`    ↓`
`Apply data-page change`
`    ↓`
`Commit acknowledgement`

The implementations represent WAL records using fields such as:

- LSN
- transaction identifier
- operation
- key
- value
- timestamp or checksum

An LSN, or Log Sequence Number, provides an ordered position in the log.

For example:

`LSN 120 → update customer`
`LSN 121 → insert order`
`LSN 122 → update inventory`

Replication can use these positions to determine how far a replica has replayed.

### WAL and recovery

A crash can interrupt normal data-page processing.

Recovery can use the log to reconstruct committed changes.

The educational recovery model is:

`Stored WAL`
`    ↓`
`Select committed transactions`
`    ↓`
`Replay records in LSN order`
`    ↓`
`Rebuild database state`

The Python, JavaScript, C++17, and Java programs explicitly demonstrate this process.

Real database recovery can be substantially more sophisticated. It can combine checkpoints, redo processing, undo processing, transaction status information, page-level metadata, and durable storage guarantees.

## Checkpoints

A checkpoint records a known recovery position.

Without checkpoints, recovery may need to process a very large historical log.

The simplified model records the latest known LSN at checkpoint time:

`WAL: 100 → 101 → 102 → 103 → 104`
`                         ↑`
`                    checkpoint`

The PostgreSQL implementation stores checkpoint positions in the `checkpoint` table.

The application implementations expose a `checkpoint` operation and record the checkpoint LSN.

A checkpoint does not mean that no WAL is required after that point. It establishes a useful recovery boundary.

## Replication

Replication copies database changes from one server to another.

The model uses:

`Primary`
`   │`
`   ├── WAL record`
`   ├── WAL record`
`   └── WAL record`
`       │`
`       ├────────→ Replica A`
`       └────────→ Replica B`

A replica replays records and tracks its replay position.

The difference between the primary's latest LSN and a replica's replay LSN represents a simplified form of replication lag.

### Asynchronous replication

In asynchronous replication:

`Application`
`    ↓`
`Primary commits`
`    ↓`
`Primary acknowledges`
`    ↓`
`Replica receives later`

The primary does not need every replica to confirm the change before acknowledging the transaction.

Advantages include lower commit latency and better tolerance for slow replicas.

The main risk is lag.

If the primary fails before the change reaches a replica, the replica may not contain the most recent committed data.

### Synchronous replication

In synchronous replication:

`Application`
`    ↓`
`Primary`
`    ↓`
`Replica acknowledgement`
`    ↓`
`Commit acknowledgement`

The primary waits for configured replica acknowledgements before treating the transaction as successfully acknowledged.

Advantages include stronger protection against losing acknowledged changes during primary failure.

The trade-off is additional latency and reduced availability when required replicas are unavailable.

The Python and JavaScript implementations explicitly support asynchronous and synchronous modes.

The C++ implementation verifies a required number of acknowledgements.

The Java implementation uses a replication cluster service that checks the configured acknowledgement count.

The PostgreSQL model stores the cluster replication mode and required synchronous replica count.

## Replication Lag

Replication lag measures how far a replica trails the primary.

The simplified calculation is:

`Lag = Primary latest LSN - Replica replay LSN`

For example:

`Primary = LSN 500`
`Replica = LSN 497`
`Lag = 3`

Lag may arise from:

- network delay
- replica CPU pressure
- disk I/O pressure
- long-running queries
- replay contention
- temporary replica outage
- insufficient replication capacity

Lag is important during failover because a stale replica can cause data loss when promoted.

## Failover

Failover changes which server acts as the primary.

The basic sequence is:

`Primary failure`
`      ↓`
`Evaluate replicas`
`      ↓`
`Choose healthy and sufficiently current replica`
`      ↓`
`Promote replica`
`      ↓`
`Redirect writes`

The implementations expose explicit failover operations.

They validate that:

- the target belongs to the cluster
- the target is a replica
- the target is available

The PostgreSQL `cluster_merge_eligibility` function performs a related infrastructure policy evaluation using:

- primary availability
- online replica count
- maximum replication lag
- required replica count

The name of the PostgreSQL policy table includes `branch_protection_style` only to make a deliberate distinction from repository governance terminology. It does not represent Git branch protection. Its purpose is database operational availability enforcement.

## Availability

Availability is not the same as replication.

Replication copies state.

Availability determines whether the service can continue operating when a component fails.

A highly available database design typically combines:

`Multiple servers`
`      +`
`Replication`
`      +`
`Health monitoring`
`      +`
`Failure detection`
`      +`
`Failover`
`      +`
`Client routing`

The implementations model only the core state transitions.

They do not implement a distributed consensus protocol, automatic leader election, fencing, DNS management, connection pooling, or production-grade failure detection.

These omissions are intentional because those mechanisms introduce additional distributed-systems concerns.

## Python Implementation

The Python program is the most direct simulation of the database lifecycle.

### Main components

| Component | Responsibility |
|---|---|
| `StoragePage` | Stores records within a bounded page |
| `StorageEngine` | Allocates pages and manages records |
| `LogRecord` | Represents a WAL entry |
| `Transaction` | Tracks staged changes and transaction state |
| `DatabaseServer` | Coordinates storage, transactions, WAL, checkpoints, and recovery |
| `ReplicationCluster` | Queues and applies WAL records to replicas |

Python `dataclass` types make the infrastructure records explicit.

The `Enum` types prevent uncontrolled strings from representing critical states.

The `RLock` protects the commit section in the in-memory server model.

The program demonstrates:

- committed transactions
- rollback
- WAL generation
- checkpoint creation
- server crash
- recovery
- asynchronous replication
- synchronous replication
- replica lag
- failover
- input validation

The checksum generated for WAL records provides an integrity check before recovery replay.

## JavaScript Implementation

The JavaScript implementation uses an event-driven design.

`DatabaseServer` extends `EventEmitter` and publishes events for:

- commit
- rollback
- checkpoint
- unavailable state
- recovery

This models an operational monitoring architecture in which infrastructure components can publish state changes to observers.

JavaScript `Map` is used for:

- transaction writes
- storage records
- replica queues

The replication cluster separates the primary from replica queues.

An asynchronous health-check function demonstrates how operational monitoring can coexist with database state management without making every infrastructure operation synchronous.

The implementation also validates structured application data before accepting it.

This provides a complementary perspective to the Python program: the focus is event propagation and policy evaluation rather than classically structured transaction simulation.

## C++17 Implementation

The C++17 program treats database infrastructure as a systems-engineering problem.

The main domain types are:

- `Page`
- `StorageEngine`
- `WalRecord`
- `Transaction`
- `DatabaseServer`
- `ReplicationCluster`

STL containers are used according to their roles:

| Container | Purpose |
|---|---|
| `vector` | Ordered pages and WAL records |
| `unordered_map` | Fast record lookup within a page |
| `map` | Deterministic transaction writes and snapshots |
| `set` | Committed transaction identifiers |
| `queue` | Pending replication records |
| `optional` | Missing database values |

The implementation uses snapshot restoration for failure handling.

The replication engine maintains a queue per replica. A replica's replay LSN determines how much WAL has been applied.

The C++ implementation explicitly demonstrates the systems trade-off between:

- asynchronous replication latency
- synchronous acknowledgement
- replication lag
- crash recovery
- failover freshness

The design uses standard-library facilities only and therefore has no external runtime dependencies.

## Java 17 Implementation

The Java implementation uses enterprise-oriented domain modeling.

The principal service boundaries are:

`DatabaseServer`
`    ↓`
`Transaction`
`    ↓`
`WalRecord`

and:

`ReplicationCluster`
`    ↓`
`Replica Servers`

Java records provide immutable representations for:

- WAL records
- health status

Enums represent controlled infrastructure states.

The transaction object explicitly owns state transitions and prevents invalid reuse after commit or abort.

The replication cluster owns the policy for:

- primary writes
- replica registration
- asynchronous replication
- synchronous acknowledgement requirements
- lag calculation
- failover

The implementation also includes a `MergePolicy<T>` interface as a generic policy abstraction. The actual database workflow does not depend on it, which keeps the infrastructure model focused while demonstrating how enterprise systems can isolate policy evaluation behind typed interfaces.

The Java implementation intentionally avoids third-party frameworks so that the infrastructure behavior remains visible.

## PostgreSQL Implementation

The PostgreSQL script represents the domain relationally.

The main relationship is:

`database_cluster`
`      ↓`
`database_server`
`      ↓`
`storage_page`
`      ↓`
`application_record`

Transactions and logging are modeled separately:

`database_transaction`
`      ↓`
`wal_record`
`      ↓`
`replication_event`

Operational recovery is represented by:

`checkpoint`

The schema uses PostgreSQL-specific features including:

- schemas
- enumerated types
- identity columns
- partial unique indexes
- JSONB
- GIN indexing
- filtered aggregates
- triggers
- PL/pgSQL functions
- views
- CTEs
- transactional control
- advisory transaction locks

### Important constraints

The database enforces:

- one primary per cluster
- positive page capacity
- valid page usage
- valid transaction isolation levels
- valid transaction state transitions
- valid WAL LSNs
- replication source must be a primary
- replication target must be a replica

The `validate_transaction_transition` trigger prevents committed or aborted transactions from being moved into an invalid state.

The `validate_replication_target` trigger ensures that replication events connect a primary to a replica.

### Index design

The schema does not index every column.

Indexes are placed where they support specific access patterns:

- cluster and server state lookup
- transaction state lookup
- WAL lookup by transaction
- WAL lookup by server and LSN
- pending replication lookup
- JSONB record queries

The partial index `one_primary_per_cluster` is particularly important because it expresses a database-level invariant rather than relying on application code.

## Database Infrastructure Workflow

A typical successful write follows this conceptual sequence:

`Client request`
`      ↓`
`Begin transaction`
`      ↓`
`Validate operation`
`      ↓`
`Create WAL records`
`      ↓`
`Apply data changes`
`      ↓`
`Commit transaction`
`      ↓`
`Replicate WAL`
`      ↓`
`Replica replay`
`      ↓`
`Update replay LSN`

For synchronous replication:

`Commit`
`  ↓`
`Required replica acknowledgements`
`  ↓`
`Application acknowledgement`

For asynchronous replication:

`Commit`
`  ↓`
`Application acknowledgement`
`  ↓`
`Replica replay later`

For failure recovery:

`Server crash`
`    ↓`
`Detect unavailable state`
`    ↓`
`Read durable WAL`
`    ↓`
`Replay committed changes`
`    ↓`
`Restore service`

For failover:

`Primary unavailable`
`       ↓`
`Evaluate replicas`
`       ↓`
`Check freshness`
`       ↓`
`Promote replica`
`       ↓`
`Route future writes`

## Failure Modes

The implementations deliberately cover several failure conditions.

### Unavailable server

Operations against a crashed server fail instead of silently returning inconsistent results.

### Invalid transaction state

A committed transaction cannot be committed again, and an aborted transaction cannot be reused.

### Replica lag

Asynchronous replication permits replicas to trail the primary.

The lag is measurable rather than hidden.

### Insufficient synchronous acknowledgements

A synchronous commit can fail its acknowledgement policy if enough replicas do not confirm the target LSN.

### Invalid failover target

A replica that is not part of the cluster or is unavailable cannot be promoted.

### Corrupt WAL

The Python implementation validates WAL checksums during recovery.

A production database would use durable log records, checksums, page-level validation, recovery metadata, and carefully defined crash semantics.

## Consistency and Availability Trade-offs

Database infrastructure involves trade-offs rather than one universally correct configuration.

| Design | Consistency characteristic | Availability characteristic | Latency |
|---|---|---|---|
| Single server | Local state is authoritative | Low during server failure | Low |
| Async replicas | Replicas can lag | Better failure tolerance | Lower write latency |
| Sync replicas | Acknowledgement depends on replicas | Can degrade when required replicas fail | Higher write latency |
| Multiple replicas | More recovery choices | Higher potential availability | Replication overhead |

Replication does not automatically provide strong consistency.

A replica can be physically healthy while still being behind the primary.

Likewise, having several replicas does not automatically make failover safe. The system needs rules for selecting a sufficiently current replica and preventing conflicting primaries.

## Security Considerations

Database infrastructure contains highly sensitive persistent state.

Important controls include:

- authenticated client connections
- encrypted transport
- authenticated replication
- least-privilege database accounts
- restricted administrative permissions
- controlled failover operations
- protected WAL files
- protected database storage
- audit logging
- secret rotation
- backup encryption
- restricted network access

Administrative operations such as failover should not be available to ordinary application identities.

WAL should receive the same protection as database data because it can contain historical record values.

## Performance Considerations

The educational storage engines intentionally use page scans.

That creates a simple performance model:

`Lookup cost ≈ O(number of pages)`

Production systems improve this with indexes and memory structures.

Other performance considerations include:

| Mechanism | Performance effect |
|---|---|
| WAL | Additional write and storage activity |
| Checkpoints | Recovery improvement with checkpoint I/O cost |
| Indexes | Faster reads with write and storage overhead |
| Async replication | Lower write latency but possible lag |
| Sync replication | Stronger acknowledgement semantics with higher latency |
| Multiple replicas | Higher read and availability capacity with replication cost |
| Larger pages | Fewer page-management operations but potentially more I/O per page |

The correct configuration depends on workload, durability requirements, failure objectives, network conditions, and recovery objectives.

## Limitations of the Implementations

These programs are infrastructure learning models rather than production database engines.

They intentionally do not implement:

- real disk durability guarantees
- buffer pool management
- B-tree or LSM-tree indexes
- MVCC
- row-level locking
- deadlock detection
- distributed consensus
- automatic leader election
- fencing
- network partitions
- quorum protocols
- binary WAL formats
- physical page checksums
- point-in-time recovery
- incremental backups
- automatic failover orchestration

The PostgreSQL script relies on PostgreSQL itself for actual transaction processing, storage, WAL, locking, and recovery. Its tables represent the infrastructure concepts as an operational data model rather than replacing PostgreSQL's internal engine.

## Cross-Language Design Comparison

| Concern | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Storage | Classes and dataclasses | Maps and page objects | STL structures | Collection-based engine | Relational tables |
| Transactions | Explicit transaction objects | Event-emitting transactions | State-managed objects | Domain model | Transaction table and triggers |
| WAL | Dataclass records | Structured objects | Struct records | Immutable records | `wal_record` |
| Replication | Cluster queues | Event-driven cluster | Explicit queues | Service-oriented cluster | Relational replication events |
| Recovery | WAL replay | WAL replay | WAL replay | WAL replay | SQL operational model |
| Validation | Exceptions and assertions | Custom errors | Exceptions | Domain exceptions | Constraints and triggers |
| Monitoring | Console output | Events and async health check | Console diagnostics | Health records | Views and reporting queries |
| Availability | Server state | Evented server state | Explicit server state | Service-level state | Server-state columns |

The implementations share the same infrastructure vocabulary while using language-specific structures rather than mechanically translating one source file into another.

## Practical Infrastructure Model

A reliable database deployment can be understood through several separate questions:

1. Where is the data stored?
2. How are logical changes grouped into transactions?
3. How are changes recorded for recovery?
4. How are changes transported to other servers?
5. How much replication lag is acceptable?
6. Which server is allowed to accept writes?
7. What happens when the primary fails?
8. Which replica is safe to promote?
9. How is recovery verified?
10. Which infrastructure rules are enforced automatically?

Those questions correspond directly to the storage, transaction, WAL, replication, and availability mechanisms implemented in this project.
