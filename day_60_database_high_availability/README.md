# Database High Availability: Clustering, Failover, and Redundancy

## 1. System Scope

Database high availability (HA) is the ability of a database service to continue accepting operations when an instance, host, storage component, network path, or availability zone becomes unavailable.

A highly available system is not defined simply by the number of database servers. It depends on independent failure domains, replication behavior, failure detection, safe writer selection, and controlled recovery.

The implementations in this project model a three-node database cluster distributed across three availability zones. One node serves as the primary, while two nodes maintain replicas. The cluster uses majority quorum, synchronous acknowledgements for committed writes, asynchronous replication for a non-acknowledging replica, and fencing before primary promotion.

The central operational requirements are:

- Maintain an unambiguous write authority.
- Preserve committed data during a primary failure.
- Avoid promotion when quorum is unavailable.
- Avoid promotion of a replica that has not received committed writes.
- Distribute nodes across independent failure domains.
- Record state transitions for diagnosis and audit.
- Reintroduce recovered nodes as replicas rather than allowing competing writers.

This project models the HA control plane. It does not configure physical database replication, provision servers, establish network policies, or perform infrastructure-level fencing.

## 2. Core Architecture

### 2.1 Cluster topology

The example cluster contains three voters:

| Node | Availability zone | Initial role | Replication behavior |
|---|---|---|---|
| `db-a` | `zone-a` | Primary | Accepts writes |
| `db-b` | `zone-b` | Replica | Synchronous acknowledgement |
| `db-c` | `zone-c` | Replica | Asynchronous replication |

A failure in one availability zone should not automatically cause the whole database service to become unavailable. Distributing replicas across zones reduces the risk that a single zone-level incident removes every database copy.

Zone placement is useful only when the zones have sufficiently independent power, networking, compute, storage, and operational dependencies. Multiple instances in the same failure domain do not provide the same protection as independent zones.

### 2.2 Architecture flow

    Client application
          |
          v
    Database service endpoint
          |
          v
    Primary database: db-a
          |
          +--------------------+
          |                    |
          v                    v
    Replica: db-b        Replica: db-c
    zone-b               zone-c
    synchronous          asynchronous
          |
          v
    Cluster control plane
          |
          +--> Health monitoring
          +--> Quorum evaluation
          +--> Replication validation
          +--> Primary fencing
          +--> Replica promotion
          +--> Recovery and audit

The service endpoint is separate from database membership. A real deployment also needs a mechanism to direct client connections to the current primary after promotion.

## 3. Clustering

Clustering groups multiple database instances into one logical service. The cluster maintains shared policies and a consistent view of which instance is authorized to accept writes.

The project distinguishes three responsibilities:

| Responsibility | Purpose |
|---|---|
| Membership | Defines which database nodes belong to the cluster |
| Replication | Maintains copies of database changes |
| Coordination | Determines which node may become the primary |

Clustering does not necessarily imply that every node can accept writes. In a primary-replica design, only the current primary is the write authority. Replicas provide redundancy, read capacity where permitted, and promotion candidates during failure.

The Python, C++, and Java implementations model membership through node collections. JavaScript uses a `Map` to maintain node identity and support event-driven state changes. PostgreSQL stores membership in `cluster_nodes` and associates each node with a cluster and an availability zone.

## 4. Quorum and Split-Brain Prevention

### 4.1 Majority quorum

Quorum is the minimum number of participating voters required to authorize a cluster operation.

For an odd number of voters:

\[
Q = \left\lfloor\frac{N}{2}\right\rfloor + 1
\]

For three voters:

\[
Q = \left\lfloor\frac{3}{2}\right\rfloor + 1 = 2
\]

Two available voters establish a majority. One available voter does not.

Majority voting prevents two isolated groups from independently satisfying the same majority rule in a fixed voter configuration. It does not, by itself, prevent an old primary from continuing to accept writes after losing contact with the cluster.

### 4.2 Fencing

Fencing prevents a former primary from continuing to act as a writer after a new primary has been selected.

The model uses an explicit fenced state. A fenced node:

- Cannot count as a live voter.
- Cannot qualify as a promotion candidate.
- Cannot retain the primary role.
- Must be rebuilt or safely reintroduced before serving as a replica.

The old primary is fenced before the candidate is promoted. The cluster term increases after promotion, giving the new writer generation a distinct identity.

The implementations represent fencing as a state-management operation. In an actual deployment, fencing must be enforced outside the application process through a reliable mechanism such as infrastructure isolation, power control, storage fencing, or another environment-appropriate control. Merely changing an in-memory flag does not fence a real database server.

### 4.3 Why quorum loss blocks promotion

An unavailable primary does not automatically justify promoting any available replica. The cluster must first establish that a majority of voters remain available.

The implementations reject promotion when fewer than two voters remain in the three-node configuration. This protects against an unsafe writer transition during a network partition or widespread infrastructure failure.

## 5. Replication and Redundancy

Replication maintains database copies on separate instances. Replication mode determines how changes are acknowledged and when the primary considers a write committed.

### 5.1 Synchronous replication

With synchronous replication, the primary waits for the required replica acknowledgement before confirming a commit under the configured commit policy.

The model requires the primary and at least one replica to acknowledge a committed write. With three voters, that represents a majority of two.

The benefit is a stronger recovery-point guarantee for acknowledged writes. A surviving acknowledged replica can contain the complete committed write position.

The trade-off is reduced write availability when the required acknowledgements cannot be obtained. A strict synchronous policy may reject writes even when the primary itself remains operational.

### 5.2 Asynchronous replication

Asynchronous replication allows the primary to proceed without waiting for every replica.

This reduces write latency and can allow a slower replica to catch up later. It also creates a period in which a replica may not contain recent committed changes.

In the example, `db-b` acknowledges writes synchronously and `db-c` is allowed to lag. The simulator updates `db-c`'s lag indicator when it misses acknowledgements.

A low lag measurement does not establish that a replica has applied every committed transaction. The failover policy therefore checks both the replication index and the measured lag.

### 5.3 Replication position

The project uses a monotonically increasing commit index to represent the progress of committed database changes.

The following values have separate meanings:

| Field | Meaning |
|---|---|
| `commitIndex` | Highest committed cluster position |
| `appliedIndex` | Highest position applied by a node |
| `lagMs` | Approximate replication delay |
| `term` | Cluster writer generation |

Under the zero-data-loss promotion policy, a candidate must satisfy:

\[
\text{appliedIndex} \geq \text{commitIndex}
\]

and:

\[
\text{lagMs} \leq \text{maximumLagMs}
\]

The index condition is the decisive test for the model's committed-write guarantee. The lag threshold is a separate operational constraint.

These values are abstractions. Real database systems use transaction logs, write-ahead logs, replication positions, replay locations, acknowledgements, and system-specific commit semantics.

## 6. Automatic Failover

Automatic failover transfers write authority from an unavailable primary to a suitable replica.

The project uses the following sequence:

    Primary failure detected
             |
             v
    Evaluate live voters
             |
             v
    Verify majority quorum
             |
             v
    Verify live availability zones
             |
             v
    Find a caught-up replica
             |
             v
    Apply replication lag policy
             |
             v
    Fence former primary
             |
             v
    Promote selected replica
             |
             v
    Increment cluster term
             |
             v
    Record failover event

### 6.1 Candidate selection

The candidate must:

- Be a configured voter.
- Be reachable and healthy.
- Have replica role.
- Not be fenced.
- Have an applied index at least equal to the commit index.
- Satisfy the configured replication-lag threshold.

When multiple candidates qualify, the implementations prefer the highest applied index, then the lowest numerical priority, then the node identifier as a deterministic tie-breaker.

### 6.2 Failure conditions

The system rejects promotion when:

- The existing primary is still healthy.
- Majority quorum is unavailable.
- Too few independent zones remain.
- No replica has all committed writes.
- The candidate exceeds the configured lag limit.

Failure to promote is an intentional safety outcome. An unavailable database is undesirable, but promoting an incomplete or conflicting writer can cause data loss or split-brain behavior.

### 6.3 Recovery after failover

A recovered former primary is not automatically allowed to become the primary again.

The recovery workflow changes it to a replica, removes its fenced status after the recovery step, and synchronizes it to the current commit index. The current primary remains the write authority.

This avoids a second-writer condition and separates recovery from failover.

## 7. Availability, Durability, and Recovery Metrics

High availability, durability, and disaster recovery are related but different properties.

| Concept | Meaning |
|---|---|
| Availability | Ability to access the database service |
| Durability | Ability to retain committed data |
| Redundancy | Availability of independent copies or components |
| Replication | Transfer of changes between database instances |
| Failover | Transfer of service authority to another instance |
| Recovery | Restoration of a failed or lagging instance |
| Quorum | Minimum participating voter count for an authorized operation |
| Fencing | Prevention of an obsolete writer from accepting operations |

Two operational metrics are especially important.

**Recovery Point Objective (RPO)** is the maximum acceptable amount of data loss measured over time or committed work. A zero-data-loss promotion policy requires the candidate to contain every committed write represented by the cluster's commit index.

**Recovery Time Objective (RTO)** is the target time for restoring service after an interruption. This project does not calculate a production RTO. A real RTO includes detection time, decision time, fencing, promotion, connection routing, application reconnection, and validation.

Replication is not a substitute for backup. Replication can copy accidental deletion, corruption, or malicious changes to other nodes. Independent backups and tested restoration procedures are still necessary.

## 8. Python Implementation

The Python implementation provides a domain-oriented cluster simulator using standard-library components.

### Mechanisms

| Mechanism | Purpose |
|---|---|
| `Enum` | Represents node roles and operational states |
| `dataclass` | Defines nodes, policies, and decision records |
| `RLock` | Serializes operations and allows safe nested evaluation |
| `dict` | Provides direct node lookup |
| `list` | Stores audit events and candidate collections |
| `set` | Calculates independent live-zone count |
| Exceptions | Distinguish quorum and promotion failures |

`HACluster.commit_write()` validates the primary and quorum before advancing the commit index. It updates the primary and the required synchronous replicas while allowing other replicas to lag.

`evaluate_failover()` is an evaluation operation rather than a mutation. It returns a decision containing the candidate, live voter count, zone count, and reason.

`failover()` applies the transition only after a successful evaluation. It fences the old primary, promotes the candidate, and increments the term.

`rejoin_as_replica()` synchronizes a recovered instance to the current committed position.

The executable scenario verifies a successful promotion and a separate quorum-loss rejection.

## 9. JavaScript Implementation

The JavaScript implementation focuses on event-driven orchestration and asynchronous health checks.

### Mechanisms

| Mechanism | Purpose |
|---|---|
| `EventEmitter` | Publishes cluster and primary-change events |
| `Map` | Maintains database instances by identifier |
| `Set` | Calculates distinct live availability zones |
| `Promise.allSettled()` | Collects independent health probe outcomes |
| `AsyncLock` | Serializes concurrent cluster mutations |
| `Object.freeze()` | Protects configuration and event records |
| `Buffer.byteLength()` | Validates UTF-8 payload size |

Health probes run concurrently. Their results are subsequently applied under the cluster lock, avoiding uncoordinated changes to shared cluster state.

The `clusterEvent` event exposes operational transitions. The `primaryChanged` event communicates a change in write authority to other components.

`commitWrite()` and `failover()` both use the asynchronous lock. This prevents a write operation and primary promotion from independently modifying the same cluster state.

The demonstration uses an asynchronous probe to simulate primary failure, then verifies promotion and recovery. A second cluster demonstrates a rejected promotion when quorum is unavailable.

The program uses Node.js built-in modules only.

## 10. C++17 Implementation

The C++ implementation treats HA as a synchronized state machine with explicit data structures and controlled operations.

### Mechanisms

| Mechanism | Purpose |
|---|---|
| `struct` | Holds node, policy, and decision data |
| `enum class` | Defines strongly typed roles and node states |
| `std::map` | Stores nodes with deterministic identifier ordering |
| `std::vector` | Holds voters, candidates, and audit entries |
| `std::set` | Counts independent live zones |
| `std::optional` | Represents an absent failover candidate |
| `std::sort` | Applies deterministic candidate ordering |
| `std::mutex` | Serializes cluster operations |
| Exceptions | Report invalid transitions and unsafe operations |

`HACluster` owns the cluster state and exposes controlled operations rather than permitting callers to modify internal node state directly.

The write path calculates quorum and the number of required replica acknowledgements before advancing the commit index.

The candidate evaluator checks every operational and replication condition. Promotion is performed only after the decision is eligible.

The `std::optional` candidate field makes the absence of a safe candidate explicit. The program also includes a quorum-loss scenario to verify rejection behavior.

The implementation has no external dependencies and compiles with C++17.

## 11. Java 17 Implementation

The Java implementation presents the cluster as an enterprise domain aggregate with explicit policy and transition types.

### Domain components

| Component | Responsibility |
|---|---|
| `Node` | Owns mutable node state |
| `HaPolicy` | Defines immutable cluster requirements |
| `NodeSnapshot` | Exposes a stable view for health checks |
| `HealthMonitor` | Executes concurrent health probes |
| `ProbeResult` | Represents a health-check outcome |
| `FailoverDecision` | Returns immutable eligibility results |
| `HaCluster` | Protects cluster invariants and transitions |

The `HaPolicy` record validates its configuration at construction. Invalid voter counts, acknowledgement requirements, lag limits, and zone requirements are rejected before the cluster starts.

The health monitor uses an `ExecutorService` and `CompletableFuture` to execute probes concurrently. Probe results are applied by the cluster aggregate through a serialized operation.

`HaCluster` uses `ReentrantLock` to protect writes, health-state updates, failover, and recovery.

The candidate selection uses Java streams and comparator chaining to produce deterministic ordering. An immutable `FailoverDecision` separates policy evaluation from the action that changes cluster roles.

The Java program uses Java 17 language and standard-library features without third-party dependencies.

## 12. PostgreSQL Implementation

The SQL file provides a relational representation of the HA control plane and its workflow.

### 12.1 Relational model

| Table | Purpose |
|---|---|
| `ha_clusters` | Stores cluster policy, term, commit index, and current primary |
| `cluster_nodes` | Stores node membership, roles, zones, and replication positions |
| `replication_links` | Describes directed replication relationships |
| `health_checks` | Stores time-stamped health observations |
| `committed_writes` | Records committed write positions and payloads |
| `failover_events` | Audits primary transitions and promotion reasons |

The schema uses primary keys, foreign keys, unique constraints, check constraints, partial indexes, and a trigger to enforce node-state consistency.

The composite foreign keys on replication relationships ensure that source and target nodes belong to the same cluster.

The partial unique index prevents multiple unfenced primary records within a cluster.

### 12.2 Transactional write procedure

`record_quorum_write()`:

1. Locks the cluster row.
2. Confirms that the configured primary is operational.
3. Calculates the required majority.
4. Counts live voters and available replicas.
5. Locks the selected synchronous acknowledgement set.
6. Updates the primary and acknowledged replica positions.
7. Records the committed write.
8. Advances the cluster commit index.

A failure during the transaction causes its changes to roll back. This prevents the commit index from advancing without the corresponding write record and acknowledgement state.

### 12.3 Failover evaluation

`evaluate_failover()` returns an eligibility decision without modifying cluster state.

It checks primary availability, majority quorum, independent live zones, candidate replication position, and lag policy.

`perform_failover()` obtains a cluster row lock, reevaluates eligibility, updates replication topology, fences the former primary, promotes the candidate, increments the cluster term, and records an audit event.

`rejoin_as_replica()` synchronizes a recovered node with the active commit index and creates a replication relationship from the current primary.

### 12.4 Reporting and queries

The script includes:

- `cluster_health` for quorum, zones, replica count, and maximum live lag.
- `replication_status` for source-target relationships and replication positions.
- Validation queries comparing applied indexes with the cluster commit index.
- Aggregation by availability zone.
- Failover eligibility evaluation.
- Committed-write history.
- Primary-promotion history.
- Latest health-check observations.

The sample scenario creates a three-zone cluster, records two writes, marks the primary down, executes failover, and returns the former primary as a replica. A final exception-handling block verifies that writes are rejected when the cluster cannot use its configured primary.

The database script represents control-plane records and transitions. It does not enable physical WAL streaming, configure PostgreSQL standby servers, or provide actual server fencing.

## 13. Failure Scenarios and Expected Behavior

| Scenario | Expected behavior |
|---|---|
| Primary fails; two replicas remain live | Evaluate quorum and candidate safety before promotion |
| Primary fails; one voter remains | Reject promotion because majority quorum is unavailable |
| Candidate has not applied the latest commit | Reject candidate under zero-data-loss policy |
| Candidate exceeds maximum lag | Reject candidate under the configured lag policy |
| Live nodes are concentrated in too few zones | Reject promotion when zone-diversity policy is not met |
| Former primary recovers | Fence or rebuild it and rejoin it as a replica |
| Two failover requests arrive concurrently | Serialize mutations and reevaluate eligibility before promotion |
| Write arrives while primary is unavailable | Reject the write |
| Asynchronous replica falls behind | Retain its lag state and prevent unsafe promotion |

## 14. Performance and Operational Considerations

### Quorum size

A majority quorum increases coordination requirements as voter count grows. Larger clusters can provide more failure tolerance, but they also increase communication overhead and the complexity of membership management.

The examples use three voters because this makes majority behavior explicit while providing one-node failure tolerance.

### Replication latency

Synchronous acknowledgements contribute to write latency. Network distance, storage performance, transaction-log flushing, and replica load influence acknowledgement time.

Cross-zone synchronous replication can improve durability but may increase latency. The replication mode should reflect the required RPO and acceptable write latency.

### Health checks

Health checks should use meaningful failure signals and appropriate timeouts. An overly aggressive timeout can interpret a temporary network delay as a node failure.

A production control plane should distinguish a failed database process from a network partition, a slow storage system, a failed health endpoint, and a complete zone outage.

### Candidate selection

Candidate selection should consider more than a node's response to a health check. Replication progress, database recovery state, failure domain, fencing status, and the configured recovery-point objective must also be considered.

### Connection routing

A successful promotion does not automatically redirect application traffic. A production architecture needs a stable service endpoint or connection-routing mechanism that identifies the current primary and handles stale connections.

### Monitoring

Useful operational measurements include:

- Current primary and cluster term.
- Live voter count and quorum status.
- Live availability-zone count.
- Replication lag and applied log position.
- Health-check response times.
- Failover duration.
- Promotion failures and rejected candidates.
- Replica recovery duration.
- Backup completion and restore-test results.

## 15. Security and Reliability Boundaries

HA coordination is part of the database security and reliability boundary.

Production implementations should apply:

- Authentication and authorization for cluster-control operations.
- Encryption for database connections and replication traffic.
- Least-privilege identities for health checks and orchestration.
- Auditable changes to cluster membership and promotion policy.
- Protection against unauthorized fencing or promotion requests.
- Secure storage and rotation of credentials.
- Independent backup retention and restoration controls.
- Validation of network partitions and recovery procedures.
- Monitoring of unusual role changes and repeated promotion attempts.

The in-memory implementations use a simulated fenced state. The PostgreSQL implementation uses database transactions and relational constraints for its modeled state. Neither is a substitute for infrastructure-level isolation or a production consensus and orchestration mechanism.

## 16. Design Limitations

The project intentionally uses a simplified fixed three-voter topology.

It does not implement:

- Physical PostgreSQL streaming replication.
- Database transaction-log parsing or WAL replay.
- Dynamic voter membership or reconfiguration.
- A distributed consensus protocol.
- Network-level fencing.
- Real health-check network calls.
- Application connection pool invalidation.
- Storage replication.
- Backup scheduling or restoration.
- Live failover timing and production RTO measurements.
- Cross-region disaster recovery.

The commit index represents a logical committed-write position. It is not a replacement for the database's native transaction identifier or log sequence number.

A production deployment must coordinate database-native replication and commit semantics with the control plane's quorum, fencing, recovery, and traffic-routing behavior.

## 17. Execution Environment

| Deliverable | Runtime |
|---|---|
| Python | Python 3.10 or later |
| JavaScript | Node.js 18 or later |
| C++17 | Compiler with C++17 support |
| Java | Java 17 or later |
| PostgreSQL | PostgreSQL 14 or later |

The Python, JavaScript, C++17, and Java programs use standard-library facilities only. The SQL script creates its own `ha_lab` schema and sample cluster data.
