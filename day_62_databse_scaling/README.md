# Database Scaling: Vertical Scaling, Horizontal Scaling, Partitioning, and Sharding

## Scope

This learning artifact models database scaling as four related but distinct mechanisms:

| Mechanism | Primary purpose | Main change |
|---|---|---|
| Vertical scaling | Increase the capacity of an existing database server | More resources on one node |
| Horizontal scaling | Increase aggregate service capacity | More database nodes |
| Partitioning | Organize a logical dataset into smaller sections | Rows are divided into partitions |
| Sharding | Distribute data across independently managed database units | Partitions are placed across shards |

The implementations use a common order-processing domain. Customers generate orders, orders belong to logical partitions, partitions are distributed through shard placement, and database nodes provide the physical capacity used by the system.

A useful conceptual separation is:

`Database -> Logical Partitions -> Shard Placement -> Database Nodes`

Vertical scaling changes the capacity of a node.

Horizontal scaling changes the number of nodes.

Partitioning changes how data is organized inside a logical database structure.

Sharding changes where those logical data groups are physically served.

These mechanisms can be combined. A sharded system can still use partitioning, and each shard can itself use vertical scaling or horizontal replication.

## Vertical Scaling

Vertical scaling, also called scale-up, increases the resources assigned to an existing database server.

Typical resources include:

- CPU
- memory
- storage capacity
- storage I/O capability
- network throughput

The Python implementation represents a database node with `capacity` and `used` values. `VerticalScaler.resize()` changes the capacity of the same node while preserving its identity and workload.

The Java implementation uses `DatabaseNode.resize()` and explicitly rejects a new capacity below the currently active workload. This models an important operational invariant: a capacity change must not make the existing workload mathematically invalid.

The PostgreSQL implementation stores capacity in `database_nodes.capacity_units`. A trigger prevents `used_units` from exceeding `capacity_units`, while `scaling_events` records capacity changes for operational auditing.

### Advantages

Vertical scaling is attractive when:

- the database architecture is still centralized;
- the workload can be handled by one sufficiently large server;
- operational simplicity is important;
- the database engine benefits strongly from larger memory or faster storage;
- application changes must be minimized.

### Limitations

A single machine has a physical and economic ceiling. Increasing resources can also produce a larger failure domain because a substantial amount of workload remains dependent on one server.

A resize can require infrastructure changes, planned maintenance, workload migration, or a restart depending on the resource being changed and the database platform.

## Horizontal Scaling

Horizontal scaling, or scale-out, adds additional database nodes.

The central difference from vertical scaling is that capacity grows by adding independent machines or service instances rather than making one machine larger.

The Python `Cluster` distributes workload across nodes and rejects requests when no healthy node has available capacity.

The Java implementation adds an explicit `NodeState` model:

- `HEALTHY` accepts new workload.
- `DRAINING` is being removed from active routing.
- `UNHEALTHY` cannot receive new workload.

This distinction is important operationally. Planned removal and unexpected failure are not identical conditions.

The JavaScript implementation uses an event-driven `ScalingController`. Events such as `nodeAdded`, `nodeResized`, and `requestRouted` expose changes in cluster state without coupling the routing logic to a particular monitoring implementation.

## Horizontal Scaling and Data Distribution

Adding database nodes does not automatically solve data placement.

A scale-out architecture must answer two separate questions:

1. Which node should receive workload?
2. Which node owns or serves a particular piece of data?

The first is a capacity-routing problem.

The second is a data-distribution problem.

Sharding addresses the second problem.

Replication can address availability and read scaling, but replication and sharding should not be treated as the same mechanism. Replication normally creates additional copies of data, while sharding divides ownership or serving responsibility across data ranges or hash buckets.

## Partitioning

Partitioning divides a logical table into smaller data sections.

For example, an order table containing billions of rows could be divided according to:

- customer identifier;
- order date;
- geographic region;
- tenant identifier;
- hash bucket.

The partitioning strategy should match important query patterns and data lifecycle operations.

### Range Partitioning

Range partitioning assigns rows to intervals.

A conceptual layout might be:

`customer_id 0-999 -> partition 0`

`customer_id 1000-1999 -> partition 1`

`customer_id 2000-2999 -> partition 2`

Range partitioning can be effective when queries frequently specify a bounded range that aligns with the partition key.

It can also simplify retention operations when old ranges can be detached or removed as complete partitions.

A poor range key can create skew. If most new records fall into the newest range, that partition can become disproportionately busy.

### Hash Partitioning

Hash partitioning applies a deterministic hash to a partition key.

Conceptually:

`hash(customer_id) mod N -> partition`

Hashing normally distributes values more evenly than simple ranges when the key has suitable cardinality.

Its trade-off is query locality. A query that needs a contiguous range of customer identifiers may have to touch many hash partitions.

The Python, Java, C++, and PostgreSQL implementations all demonstrate hash-based placement while retaining explicit support for range-based policies where appropriate.

## Sharding

Sharding distributes data across independently managed database units.

A simplified model is:

`Customer ID -> Shard Function -> Shard -> Database Node`

The shard function must be deterministic. Given the same routing key, the system must consistently identify the same shard unless a deliberate rebalancing operation changes the mapping.

The Python `ShardedStore` provides `insert()`, `get()`, and `rebalance()` operations. The Java `ShardRepository` stores each shard as an independent map and performs point lookups using the customer identifier.

The C++ implementation uses `unordered_map` for shard-local storage, giving a practical in-memory representation of independently managed data buckets.

The PostgreSQL model separates `partition_definitions` from `shards` and `database_nodes`. This makes the conceptual relationship explicit rather than collapsing all three concepts into one table.

## Shard Keys

A shard key determines where a record belongs.

A strong shard key generally has:

- sufficient cardinality;
- reasonably balanced distribution;
- frequent presence in point-lookups;
- stable values;
- low probability of producing a hot shard.

A weak shard key can produce severe skew.

For example, if nearly all current traffic uses one tenant identifier, hashing that tenant identifier can still produce a hot shard because every request for that tenant maps to the same location.

Changing a shard key later can be expensive because existing records may need to be redistributed and application routing must remain consistent during migration.

## Rebalancing

Adding shards changes the placement problem.

With a simple modulo scheme:

`shard = hash(key) mod N`

changing `N` can move a large percentage of records.

For example:

`hash(key) mod 4`

and

`hash(key) mod 8`

produce different placements for many keys.

The Python implementation explicitly demonstrates this by creating a replacement store with a larger shard count and reinserting every order. This is intentionally simple and makes the data-movement cost visible.

Production systems commonly use more sophisticated placement techniques, such as consistent hashing, virtual nodes, explicit shard maps, or controlled migration workflows.

Rebalancing must preserve:

- data correctness;
- routing correctness;
- availability;
- transaction consistency where required;
- acceptable migration load;
- observability;
- rollback or recovery capability.

## Hot Partitions and Hot Shards

Scaling problems are not always caused by insufficient total capacity.

A system may have adequate aggregate capacity while one partition or shard is overloaded.

For example:

`Shard 0 -> 10% of rows -> 10% of traffic`

`Shard 1 -> 15% of rows -> 15% of traffic`

`Shard 2 -> 20% of rows -> 20% of traffic`

`Shard 3 -> 55% of traffic`

The fourth shard can become the bottleneck even if the cluster has substantial unused capacity elsewhere.

This is why monitoring should measure distribution, not just total database utilization.

Useful measurements include:

- requests per shard;
- storage per shard;
- CPU per node;
- memory utilization;
- I/O latency;
- queue depth;
- query latency;
- partition size;
- replication lag where replication is used;
- failed routing attempts.

## Python Implementation

The Python program models scaling through several cooperating classes.

`Node` stores capacity, usage, health, and utilization.

`Cluster` manages multiple nodes and performs workload routing.

`VerticalScaler` changes the capacity of one existing node.

`HorizontalScaler` adds or removes database nodes.

`Partitioner` maps orders to logical partitions using either hash or range placement.

`ShardedStore` maps orders to physical shards and supports point lookup and scale-out redistribution.

`generate_orders()` produces deterministic test data so the distribution can be inspected repeatedly.

Assertions verify important invariants:

- all orders remain stored after redistribution;
- point lookup returns the expected record;
- vertical capacity changes are applied correctly;
- the cluster retains its expected node count.

The implementation also models an unhealthy node. New work is rejected from unhealthy nodes rather than silently routing requests to unavailable capacity.

## JavaScript Implementation

The JavaScript implementation emphasizes event-driven behavior.

`DatabaseNode` represents an independently routable database server.

`ScalingController` maintains a `Map` of nodes and selects the least-utilized healthy node with available capacity.

The controller emits events when nodes are added, resized, or assigned work. This reflects a common Node.js architecture in which routing, telemetry, monitoring, and operational handlers can react to state changes without embedding all behavior in one function.

`Partitioner` handles logical partition placement.

`ShardRouter` determines physical shard placement.

`ShardedRepository` stores records by shard and performs customer-key-based point lookup.

`processBatch()` uses promises to represent concurrent request submission. The routing decision remains synchronous so capacity validation happens before a request is accepted.

The implementation uses Node.js standard-library modules only:

- `crypto` for deterministic hashing;
- `events` for event-driven state reporting.

No external npm package is required.

## C++17 Implementation

The C++ implementation treats scaling as a resource-management problem.

`DatabaseNode` contains explicit resource state and calculates utilization.

`RepositoryGovernance` manages nodes and chooses a healthy node with available capacity. It uses STL algorithms such as `find_if`, `min_element`, and `accumulate`.

`Partitioner` separates logical partition selection from physical shard placement.

`ShardMap` uses `unordered_map` inside each shard, giving average constant-time lookup behavior under normal hash-table assumptions.

The C++ implementation uses deterministic integer mixing for hash placement rather than relying on implementation-specific string hashing.

Exceptions are used for invalid states such as:

- zero capacity;
- duplicate nodes;
- unknown nodes;
- capacity below active workload;
- no healthy node with available capacity;
- duplicate orders;
- missing point-lookup results.

The program also verifies a row-count invariant after sharding:

`sum(rows in all shards) = total generated orders`

This is a basic but useful check when implementing redistribution logic.

## Java 17 Implementation

The Java implementation uses explicit enterprise-style domain modeling.

`DatabaseNode` represents node capacity and operational state.

`Cluster` provides workload routing.

`PartitionPolicy` separates logical partitioning rules from physical storage.

`ShardRepository` manages shard-local data.

`ScalingPolicy` defines a policy interface, while `UtilizationPolicy` implements a concrete utilization threshold. This keeps policy evaluation separate from the operation that performs routing.

Java records provide immutable domain values for `Order`.

The `NodeState` enum distinguishes healthy, draining, and unhealthy states. That distinction supports operational workflows in which a node can be removed from new traffic before it is physically decommissioned.

Streams are used for:

- node selection;
- partition aggregation;
- shard distribution reporting.

The implementation demonstrates a key enterprise design principle: domain rules should be explicit enough to validate independently from infrastructure actions.

## PostgreSQL Implementation

The PostgreSQL script models the scaling architecture relationally.

### Core tables

`database_clusters` identifies logical database clusters.

`database_nodes` stores physical node capacity, workload, and health state.

`scaling_events` provides an operational history of node changes.

`partition_definitions` represents logical partitioning.

`shards` represents physical shard placement.

`customers` and `orders` provide the business workload.

`scaling_policies` stores cluster-specific capacity and utilization rules.

### Constraints

The schema uses:

- primary keys;
- foreign keys;
- unique constraints;
- check constraints;
- enum types;
- indexes.

The node table prevents invalid states such as negative usage or usage above capacity.

The order table requires a valid customer, partition, and shard.

### Triggers

`validate_node_capacity()` provides database-level enforcement of node capacity.

`record_node_change()` creates audit records when nodes are added, resized, drained, failed, or recovered.

This is important because application validation alone cannot guarantee that every writer respects an operational invariant.

### Functions

`choose_least_utilized_node()` identifies a healthy node with available capacity.

`evaluate_horizontal_scaling()` calculates cluster-level utilization and determines whether scale-out pressure exists.

### Views

`node_capacity_report` classifies nodes as:

- `available`;
- `scale_attention`;
- `full`;
- `unavailable`.

`shard_distribution_report` exposes the number of orders assigned to each shard and its database node.

These views provide operational reporting without requiring every query to reconstruct the same calculations.

## Scaling Decision Workflow

A practical scaling workflow can be represented as:

`Monitor`

`  -> Measure utilization`

`  -> Detect capacity pressure`

`  -> Determine whether pressure is local or global`

`  -> Check policy limits`

`  -> Choose vertical or horizontal action`

`  -> Evaluate data distribution`

`  -> Rebalance partitions or shards when necessary`

`  -> Validate workload`

`  -> Continue monitoring`

The distinction between local and global pressure matters.

If one database node is overloaded while other nodes are underutilized, better routing or data redistribution may be more appropriate than adding capacity everywhere.

If every node is near its capacity threshold, horizontal scaling may be more appropriate.

If the entire database fits comfortably on one machine but requires more memory or faster storage, vertical scaling can be operationally simpler.

## Query Routing and Data Routing

Workload routing and data routing should not be conflated.

Workload routing asks:

`Which healthy database node should process this request?`

Data routing asks:

`Which partition or shard contains this record?`

A system can route requests to a healthy node while still routing a specific customer to the correct shard.

For a point lookup, the sequence can be:

`customer_id`

`-> shard-key calculation`

`-> shard`

`-> database node`

`-> record lookup`

This is why the source implementations keep cluster routing and shard routing as separate components.

## Failure Handling

Scaling systems must distinguish capacity exhaustion from node failure.

Capacity exhaustion means a node is healthy but cannot accept more work.

Node failure means the node should not receive new work regardless of unused nominal capacity.

Planned draining is another state. A draining node may still contain active workload but should not receive new requests.

The implementations therefore avoid treating a simple boolean capacity check as a complete operational model.

Failure handling should also consider:

- retries;
- idempotency;
- transaction boundaries;
- partial failures;
- stale routing information;
- migration state;
- recovery;
- observability.

Retries are particularly important for write operations because an automatically retried request can create duplicate effects unless the operation is idempotent.

## Performance Considerations

Vertical scaling can improve performance without introducing cross-node coordination, but hardware limits remain.

Horizontal scaling increases aggregate capacity but introduces coordination and routing complexity.

Partitioning can improve query performance when the database can eliminate irrelevant partitions. This is commonly called partition pruning.

Sharding can reduce the amount of data a single database must serve, but cross-shard queries can become significantly more expensive.

A point query such as:

`WHERE customer_id = ?`

can be efficient when `customer_id` is the shard key.

A query such as:

`GROUP BY region`

may require work across many shards unless the architecture provides a specialized aggregation strategy.

Therefore, a scaling design should begin with workload characteristics rather than simply selecting the largest number of nodes.

## Security Considerations

Scaling does not remove normal database security requirements.

Important controls include:

- least-privilege database accounts;
- encrypted connections;
- authentication between application and database nodes;
- controlled administrative access;
- credential rotation;
- audit logging;
- protection of customer identifiers;
- secure backup storage;
- network segmentation;
- restricted cross-shard access.

Operational logs should not expose passwords, connection strings, authentication tokens, or other secrets.

Shard placement metadata can also be operationally sensitive because it reveals infrastructure topology.

## Data Consistency Considerations

Partitioning within one logical database can often preserve transactional behavior more easily than cross-database sharding.

Sharding can make transactions spanning multiple shards substantially more complex.

For example:

`Customer A -> Shard 1`

`Customer B -> Shard 4`

A transaction updating both customers may require coordination across two independent data stores.

Designs should therefore prefer operations that remain within one shard when possible.

A good shard key can reduce cross-shard transactions by keeping related data together.

## Edge Cases

The implementations explicitly address several edge cases:

| Edge case | Handling |
|---|---|
| Duplicate node | Rejected |
| Zero capacity | Rejected |
| Capacity below current usage | Rejected |
| Unhealthy node | Excluded from new routing |
| Full node | Cannot accept new workload |
| Duplicate order | Rejected |
| Invalid customer ID | Rejected |
| Empty cluster capacity | Routing fails explicitly |
| Shard redistribution | Rows are reassigned |
| Missing point lookup | Detected as an invariant failure |
| Data-loss during distribution | Checked using row-count invariants |

These checks are intentionally close to the affected domain objects so invalid states do not silently propagate.

## Relationship Between the Four Concepts

The four concepts solve different problems:

| Question | Mechanism |
|---|---|
| Can one database server handle more workload? | Vertical scaling |
| Can the system use more independent database capacity? | Horizontal scaling |
| Can a large logical table be divided into manageable data groups? | Partitioning |
| Can data ownership be distributed across independent databases? | Sharding |

They can be combined in one architecture:

`Application`

`    |`

`    v`

`Routing Layer`

`    |`

`    +-------------------+`

`    |                   |`

`    v                   v`

`Shard 0             Shard 1`

`    |                   |`

`Partitions          Partitions`

`    |                   |`

`Nodes               Nodes`

`    |                   |`

`Vertical capacity   Vertical capacity`

This layered view prevents a common design error: assuming that adding database servers automatically solves every database scaling problem.

## Practical Design Trade-offs

A scaling decision should consider:

- workload type;
- read/write ratio;
- data volume;
- request volume;
- query patterns;
- transaction boundaries;
- availability requirements;
- acceptable latency;
- operational complexity;
- infrastructure limits;
- data distribution;
- failure recovery.

Vertical scaling is usually simpler but has a hardware ceiling.

Horizontal scaling provides more aggregate capacity but requires routing and operational coordination.

Partitioning can improve manageability and query pruning but requires a suitable partition key.

Sharding can distribute very large datasets but introduces routing, migration, cross-shard query, and consistency concerns.

The appropriate architecture is therefore determined by workload characteristics rather than by scale alone.
