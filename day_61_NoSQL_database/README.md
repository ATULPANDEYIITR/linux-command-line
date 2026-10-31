# NoSQL Database Architectures

## Scope

This project models four distinct NoSQL database architectures through the same distributed-application domain:

- Key-value databases for direct lookup and session state.
- Document databases for flexible, nested product records.
- Wide-column databases for sparse, partition-oriented telemetry.
- Graph databases for relationship traversal and dependency analysis.

The five implementations deliberately use different engineering perspectives. Python provides an executable simulation of the four storage patterns. JavaScript models event-driven processing and asynchronous telemetry ingestion. C++17 builds a compact architecture case study with explicit containers and graph traversal. Java 17 models an enterprise service layer with domain records, repository abstractions, policies, and state transitions. PostgreSQL provides a relational representation of the same access patterns using JSONB, sparse cells, graph edges, constraints, triggers, recursive CTEs, and transactional operations.

## Architectural Relationship

NoSQL is not one storage model. The appropriate design depends on access patterns, data shape, distribution requirements, consistency expectations, and relationship complexity.

A useful distinction is:

    Workload
       |
       +-- Direct key lookup ----------> Key-value
       |
       +-- Flexible nested records ----> Document
       |
       +-- Partitioned sparse rows ----> Wide-column
       |
       +-- Relationship traversal ----> Graph

The four models can coexist in one platform. They solve different problems rather than representing interchangeable names for the same structure.

## Key-Value Databases

A key-value database associates a unique key with an opaque value.

The primary operation is conceptually:

    key -> value

This model is effective when the application already knows the identifier required to retrieve data. Common workloads include sessions, authentication tokens, counters, feature flags, cache entries, and short-lived application state.

The Python implementation uses a dictionary for constant-average direct lookup and a separate expiration structure for TTL handling. Expired entries are removed when accessed. Invalid keys and non-positive TTL values are rejected.

The JavaScript implementation uses Map rather than a plain object. This provides explicit key-value semantics and avoids accidental collisions with object properties. Change events are emitted when entries are written or deleted, making the model suitable for event-driven applications.

The C++ implementation uses unordered_map and steady_clock. The monotonic clock is important for TTL measurement because elapsed-duration calculations should not depend on changes to the system wall clock.

The Java implementation wraps key-value entries in an immutable record containing the value and optional expiration timestamp. The repository validates expiration before storing an entry and removes expired entries during retrieval.

The PostgreSQL implementation represents the same pattern with a primary key and JSONB value. An index on expiration values supports maintenance-oriented queries for entries with TTL information.

### Key-value design characteristics

| Property | Key-value model |
|---|---|
| Primary access | Exact key lookup |
| Data shape | Opaque or application-defined |
| Typical latency goal | Very low |
| Query model | Usually limited |
| Relationships | Not the primary abstraction |
| Typical workload | Sessions, cache, counters, tokens |
| Main design concern | Key design and access pattern |

A key-value model becomes less appropriate when applications frequently need arbitrary filtering across the value or multi-hop relationship traversal.

## Document Databases

A document database stores records as self-contained documents. JSON-like structures are common because nested objects and arrays can be represented naturally.

The project models product catalog data as documents containing:

- identity
- product name
- category
- price
- tags
- inventory
- variable attributes

The important distinction from the key-value model is that document structure has meaning to the database and application. Fields can be indexed or queried without requiring the application to understand the entire value as an opaque object.

The Python DocumentStore validates document identifiers, prevents duplicate identifiers, performs predicate-based searches, and supports partial updates.

The JavaScript implementation uses a Map as the collection index and structuredClone to prevent callers from unintentionally sharing mutable document references. This is relevant when application code modifies nested objects after insertion.

The C++ case study represents product documents as a typed Product structure. This provides stronger compile-time validation for a defined catalog shape rather than attempting to reproduce arbitrary JSON.

The Java implementation uses a Product record with constructor validation and immutable tag lists. A repository interface separates the domain object from the storage abstraction.

The PostgreSQL representation uses JSONB. Required fields such as name, category, and price are checked at the database boundary, while GIN indexes support JSON-oriented access. A separate category expression index supports a common filtering path.

### Document update semantics

A document may evolve without every record having exactly the same optional fields.

For example, a product may initially contain:

    name
    category
    price

A later version may contain:

    name
    category
    price
    attributes
        region
        firmware_version

This flexibility is useful for heterogeneous records, but it shifts some validation responsibility toward application and database rules. The PostgreSQL trigger increments a document version whenever the JSON document changes.

## Wide-Column Databases

Wide-column databases organize data around partition or row keys and sparse columns or column families.

The important design principle is that the schema is shaped around known query paths rather than around a universally normalized relational representation.

The telemetry model uses:

    row key       column family       column
    device-001    telemetry           timestamp
    device-002    telemetry           timestamp

Different rows can contain different columns. This is useful for high-volume telemetry where records are naturally partitioned by device, customer, region, time bucket, or another distribution key.

The Python implementation stores row keys, families, and sparse column dictionaries directly. The JavaScript implementation uses nested Maps and performs asynchronous telemetry ingestion. The C++ implementation uses nested unordered_map containers and focuses on efficient in-memory writes and family scans.

The Java implementation separates the repository from the domain service and uses nested maps to represent row, family, and column levels.

The PostgreSQL implementation represents each sparse cell as a row containing a row key, column family, column name, optional numeric value, optional text value, and observation timestamp.

### Wide-column considerations

Partition design is critical. A poorly selected partition key can create oversized partitions or concentrate traffic on a small number of nodes.

A time-series system also needs to consider:

- time bucketing
- retention
- write distribution
- hot partitions
- query windows
- replication
- compaction behavior
- acceptable consistency

The project does not pretend that a relational table with sparse cells has the same physical behavior as a distributed wide-column engine. It represents the logical access pattern so that the architectural difference remains visible.

## Graph Databases

Graph databases model entities as nodes and relationships as edges.

The project uses service dependencies:

    api
      |
    calls
      v
    orders
      |
      +------ calls ------> payments
      |
    calls
      v
    inventory
      |
    reads
      v
    inventory-db

The important operation is relationship traversal rather than simple record retrieval.

The Python, JavaScript, C++, and Java implementations use adjacency structures. The graph traversal algorithms perform breadth-first search to find a shortest unweighted dependency path.

For example:

    api -> orders -> inventory -> inventory-db

The visited set prevents cycles from causing infinite traversal. This is important because production dependency graphs can contain circular relationships.

The PostgreSQL implementation stores nodes and directed edges separately. Recursive CTEs then traverse the graph while maintaining the path and rejecting nodes already present in that path.

### Graph-specific characteristics

| Property | Graph model |
|---|---|
| Primary entities | Nodes |
| Relationships | Edges |
| Main operation | Traversal |
| Typical queries | Paths, neighbors, dependencies |
| Main risk | Unbounded traversal |
| Important control | Depth and cycle handling |

Graph databases are useful when relationships are first-class data. They are not automatically superior for ordinary attribute filtering or direct key lookup.

## Distinguishing the Four Architectures

| Workload | Key-value | Document | Wide-column | Graph |
|---|---:|---:|---:|---:|
| Exact session lookup | Strong fit | Possible | Possible | Poor fit |
| Flexible product records | Limited | Strong fit | Possible | Poor fit |
| Massive telemetry streams | Possible | Possible | Strong fit | Poor fit |
| Multi-hop dependencies | Poor fit | Limited | Poor fit | Strong fit |
| Nested attributes | Application-managed | Native concept | Limited | Node properties |
| Relationship traversal | Weak | Application-managed | Weak | Native concept |

The selection should begin with the dominant access pattern rather than with the database product name.

## Python Implementation

The Python file defines four explicit storage classes:

- KeyValueStore
- DocumentStore
- WideColumnStore
- GraphStore

The key-value store supports TTL expiration. The document store uses deep serialization to prevent external mutation of stored structures. The wide-column store models sparse families and columns. The graph store performs breadth-first shortest-path traversal.

A separate architecture-selection function maps workload characteristics to a database model.

Assertions cover:

- successful session retrieval
- document filtering
- telemetry scanning
- graph traversal
- duplicate-document rejection
- missing-key handling

The program is self-contained and uses only Python standard-library modules.

## JavaScript Implementation

The JavaScript implementation uses Node.js standard-library capabilities.

Key design choices include:

- Map for explicit key-value storage.
- EventEmitter for key-value change notifications.
- structuredClone for defensive document copies.
- async generators for telemetry events.
- asynchronous iteration for ingestion.
- Map-based adjacency structures for graph relationships.

The telemetry path is intentionally asynchronous. This models a stream-processing boundary without requiring an external message broker.

Validation errors and missing-resource errors use separate exception classes so callers can distinguish invalid input from absent data.

## C++17 Implementation

The C++ program presents a strongly typed case study.

The storage components use:

- unordered_map for direct and sparse lookup
- unordered_set for graph membership and visited tracking
- vector for product tags and graph paths
- deque for breadth-first traversal
- optional for paths that may not exist
- steady_clock for TTL expiration

The Product structure gives the document case a typed representation. The graph engine performs breadth-first search and returns an optional path.

C++ makes memory ownership and data-structure selection explicit. This is useful when evaluating performance-sensitive systems where allocation behavior and container characteristics affect throughput.

## Java 17 Implementation

The Java implementation models an enterprise-oriented service boundary.

The domain includes:

- Product records
- repository interfaces
- key-value storage
- wide-column storage
- dependency graphs
- architecture policy selection
- workflow state transitions

The Product record performs constructor validation and creates an immutable copy of its tag collection.

The ArchitecturePolicy object evaluates workload characteristics and assigns a database model. The WorkflowService explicitly controls state transitions and rejects invalid transitions.

The graph implementation uses records for graph edges and immutable path values returned from traversal.

This structure separates domain behavior from storage mechanics and makes validation and state management explicit.

## PostgreSQL Implementation

The SQL file represents all four NoSQL patterns in one executable PostgreSQL schema.

The relational model includes:

- architecture decisions
- key-value entries
- JSONB documents
- sparse wide-column cells
- graph nodes
- graph edges
- ingestion workflows

Constraints enforce basic data validity. JSONB indexes support document-oriented queries. Graph indexes support source and target relationship access.

The workflow trigger rejects invalid transitions after terminal states. The document trigger increments document versions when JSON content changes.

The script demonstrates:

- exact key retrieval
- JSONB filtering
- JSON structure validation
- telemetry aggregation
- graph relationship retrieval
- recursive graph traversal
- architecture reporting
- workflow reporting
- document eligibility evaluation
- transactional document modification
- rejected state transitions

## Data and State Boundaries

The implementations separate several concepts that are often incorrectly combined.

    Data shape
        |
        +--> Key-value value
        +--> Document fields
        +--> Wide-column cells
        +--> Graph nodes and edges

    Access pattern
        |
        +--> Direct lookup
        +--> Attribute query
        +--> Partition scan
        +--> Relationship traversal

    Operational state
        |
        +--> Valid
        +--> Missing
        +--> Expired
        +--> Failed
        +--> Completed

A database architecture describes storage and access behavior. It does not by itself define every application workflow or validation rule.

## Validation and Failure Handling

The implementations reject several classes of invalid operations.

Key-value validation includes empty or excessively long keys, invalid TTL values, and missing entries.

Document validation includes missing identifiers, duplicate identifiers, negative prices, and invalid document structures.

Wide-column validation requires row keys, families, and columns.

Graph validation requires existing endpoints and rejects duplicate nodes. Traversal uses visited-state tracking to avoid cycles.

The Java workflow service adds explicit state validation so a completed or failed workflow cannot silently return to an earlier state.

The PostgreSQL schema moves critical checks into the database where appropriate. This prevents application code from being the only enforcement layer.

## Performance Considerations

Key-value operations are designed around direct lookup. Hash-based structures provide expected constant-time lookup, insertion, and deletion.

Document queries can become expensive when arbitrary predicates require scanning every document. Indexing frequently queried fields reduces this cost.

Wide-column systems are designed around predictable partition access. Scanning every partition is generally less desirable than querying a known partition and bounded time range.

Graph breadth-first traversal has a cost proportional to the visited portion of the graph. In the in-memory implementations, adjacency access is efficient, but path construction can consume additional memory.

The PostgreSQL recursive graph query includes a depth limit and cycle check. These controls prevent an accidental query from traversing an unbounded graph.

## Security Considerations

NoSQL architecture does not remove the need for security controls.

Production systems should protect:

- credentials and connection strings
- session values
- sensitive document fields
- telemetry
- graph relationship data
- administrative operations

The examples do not embed credentials or connect to external databases. This keeps the files executable without requiring secrets.

For real deployments, access should be based on least privilege. Applications should receive only the database operations and data access they require.

Document and JSON data should be validated before being trusted by application logic. Graph relationships should also be treated as data subject to authorization because a dependency or ownership relationship can itself be sensitive.

TTL handling is useful for reducing the lifetime of temporary values, but expiration is not a substitute for access control or secure deletion requirements.

## Consistency and Data Modeling

The choice of NoSQL architecture affects how consistency is approached.

Key-value systems commonly favor simple, predictable operations around individual keys.

Document systems make a related object convenient to store as one record, reducing the need for joins but potentially duplicating information.

Wide-column systems favor data layouts optimized for distributed access patterns. Denormalization is often deliberate.

Graph systems keep relationships explicit, making traversal efficient while introducing graph-specific concerns such as cycle detection and traversal limits.

The central design decision is not whether a database is relational or non-relational. The important question is whether its storage model matches the application's dominant reads, writes, relationships, and scaling behavior.

## Practical Domain Flow

The four architectures can form a single distributed platform:

    Application
        |
        +--> Session service --------> Key-value store
        |
        +--> Catalog service --------> Document store
        |
        +--> Telemetry service ------> Wide-column store
        |
        +--> Dependency service -----> Graph store

Each component has a different reason for its storage choice.

The session service benefits from direct key lookup and expiration. The catalog service benefits from nested and evolving records. The telemetry service benefits from partition-oriented sparse writes. The dependency service benefits from explicit relationship traversal.

This separation prevents the common design error of forcing every workload into one storage model simply because the same application owns all four datasets.

## Limitations

The in-memory Python, JavaScript, C++17, and Java 17 implementations model logical behavior rather than distributed storage-engine internals. They do not reproduce replication protocols, consensus, sharding, compaction, distributed transactions, network partitions, or production failure recovery.

The PostgreSQL implementation demonstrates relational representations of NoSQL-oriented access patterns. PostgreSQL JSONB, sparse tables, and recursive CTEs provide useful modeling mechanisms, but they do not reproduce the physical scalability characteristics of specialized NoSQL engines.

The examples therefore focus on architecture, data modeling, access patterns, validation, traversal, and workflow behavior rather than claiming equivalence between storage technologies.

## File Responsibilities

| File | Primary perspective | Main implementation |
|---|---|---|
| Python | Executable architecture simulation | Four in-memory NoSQL models |
| JavaScript | Event-driven processing | Events, async telemetry, Maps |
| C++17 | Systems-oriented case study | STL containers and graph engine |
| Java 17 | Enterprise domain model | Records, repositories, policies, state transitions |
| PostgreSQL | Persistent relational representation | JSONB, sparse cells, graph tables, triggers, CTEs |

The five implementations share the same architectural distinctions while intentionally using language-specific data structures and design techniques.
