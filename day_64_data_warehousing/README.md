# Data Warehousing

## 1. Purpose and scope

Data warehousing is the practice of collecting, integrating, storing and organizing data for analysis and reporting. A data warehouse separates analytical workloads from the operational systems that record daily business activity.

This project implements a retail sales data pipeline across five programming and database environments. Each implementation demonstrates a distinct engineering approach to extracting operational data, transforming records, loading analytical structures and producing aggregate reports.

The central workflow is:

Operational systems
        |
        v
Change capture and extraction
        |
        v
Staging and validation
        |
        v
Transformation and dimension lookup
        |
        v
Fact and dimension loading
        |
        v
Analytical queries and reports

The example uses customers, products, dates and sales. Sales are the measurable business events. Customer, product and date attributes provide the context needed to analyze those events.

## 2. OLTP and OLAP

OLTP and OLAP are different workload categories. They have different design objectives and should not be treated as interchangeable database configurations.

| Characteristic | OLTP | OLAP |
|---|---|---|
| Primary purpose | Record operational transactions | Analyze business activity |
| Typical operations | Insert, update and selective retrieval | Aggregation, filtering and historical analysis |
| Data scope | Current operational records | Integrated current and historical data |
| Query pattern | Frequent and relatively selective | Often scans and groups many records |
| Data model | Commonly normalized | Commonly dimensional or analytical |
| Consistency requirement | Strong transaction consistency | Governed load and reporting consistency |
| Example | Registering a customer purchase | Comparing monthly sales by region |

An operational sales system needs to record an individual transaction quickly and preserve transactional integrity. An analytical system needs to combine large numbers of sales with customer, product and date attributes.

The project separates these responsibilities. The Python source database and JavaScript source store represent operational data. Their warehouse structures are designed for analytical reads. The PostgreSQL implementation makes staging, dimensions and facts separate database objects.

A warehouse does not automatically replace an OLTP database. Operational systems remain responsible for transaction processing, while the warehouse supports reporting and analysis.

## 3. Analytical databases and dimensional modeling

An analytical database is structured to support queries that examine business activity across multiple dimensions. A common design is the dimensional model.

### 3.1 Fact tables

A fact table stores measurable events or observations.

The `fact_sales` table in the PostgreSQL implementation contains:

| Field | Meaning |
|---|---|
| `source_system` | Operational system that produced the record |
| `source_sale_id` | Business identifier assigned by the source |
| `customer_sk` | Warehouse customer key |
| `product_sk` | Warehouse product key |
| `date_key` | Warehouse date key |
| `quantity` | Number of units sold |
| `unit_price_cents` | Unit price in minor currency units |
| `gross_cents` | Quantity multiplied by unit price |

The grain of this fact table is one source sales transaction. Grain means the precise business event represented by one fact row.

Defining grain before creating a fact table prevents inconsistent levels of detail. A fact table containing one row per sales transaction should not silently mix transaction-level records with monthly summary records.

The implementations use integer minor currency units, such as cents or paise, to avoid common floating-point rounding errors in financial calculations.

### 3.2 Dimension tables

Dimension tables describe the entities and contexts associated with facts.

| Dimension | Example attributes | Analytical use |
|---|---|---|
| Customer | Customer identifier, name, region | Compare purchasing activity by geography |
| Product | Product identifier, name, category | Compare products and product categories |
| Date | Date, year, quarter, month, day | Analyze trends over time |

The fact table stores warehouse dimension keys. Reports join those keys to dimension tables to retrieve descriptive attributes.

### 3.3 Business keys and surrogate keys

A business key identifies an entity in the operational domain. For example, `C001` identifies a customer in the source system.

A surrogate key is an internal warehouse identifier. The PostgreSQL implementation uses `customer_sk` and `product_sk` as surrogate keys.

Separating the two is useful when source identifiers change, when several source systems use different identifiers, and when historical dimension versions must coexist.

### 3.4 Star schema

The PostgreSQL structure uses a star-schema arrangement:

        dim_customer
              |
              |
dim_date -- fact_sales -- dim_product

The fact table is at the center. Dimension tables contain descriptive attributes and connect to the fact table through foreign keys.

A star schema makes common analytical queries easier to understand. It also gives query planners useful join and index structures. It can contain more duplicated descriptive data than a highly normalized operational schema, which is an intentional tradeoff for analytical use.

## 4. ETL pipelines

ETL means Extract, Transform and Load. It is a controlled process for moving data from source systems into an analytical destination.

### 4.1 Extract

Extraction retrieves source data or source changes.

The Python and PostgreSQL implementations use change sequences or batch records to identify work that has not yet been processed. The JavaScript implementation publishes source changes as events and reads them in batches.

Extraction may use:

- Full extraction, which reads the entire available source dataset.
- Incremental extraction, which reads records changed since a known point.
- Change Data Capture (CDC), which captures inserts, updates and deletes from a source system or its transaction log.
- Event-based extraction, which receives changes as events are published.

Full extraction is straightforward but can be expensive for large datasets. Incremental extraction reduces repeated work, but requires reliable change identification and recovery handling.

A timestamp watermark can be used to track progress. Timestamp-only watermarks require care because multiple records can share a timestamp. A stable sequence number or a composite cursor can make incremental extraction more reliable.

### 4.2 Transform

Transformation converts operational records into a form suitable for analytics.

The implementations apply the following transformations:

- Validate record identifiers.
- Reject invalid quantities and prices.
- Verify that customer and product keys resolve.
- Exclude cancelled or incomplete transactions.
- Validate dates.
- Calculate gross sales amounts.
- Associate facts with dimension records.
- Record rejected data for investigation.

Transformation is not only a formatting step. It enforces business definitions and quality rules. For example, a transaction with a negative quantity should not enter a standard sales fact table unless the organization has explicitly modeled returns or reversals.

### 4.3 Load

Loading writes validated and transformed records into warehouse tables.

The project demonstrates:
- Loading dimension records before dependent facts.
- Using foreign keys to prevent invalid dimension references.
- Preventing duplicate fact records with source business identifiers.
- Updating an existing fact when a newer source version is available.
- Maintaining a load watermark.
- Recording rejected records separately.
- Committing related warehouse changes as a transaction.

A successful ETL run should leave both its data changes and its progress marker in a consistent state. Advancing a watermark before the corresponding data is safely committed can cause records to be skipped after a failure.

## 5. ETL and ELT

ETL and ELT differ in where transformation takes place.

| Aspect | ETL | ELT |
|---|---|---|
| Sequence | Extract, transform, load | Extract, load, transform |
| Transformation location | Before loading into the target | Inside the target platform |
| Typical use | Controlled transformation before analytical storage | Large-scale platforms with substantial in-database processing |
| Raw data retention | May retain selected source or staging data | Often retains raw source data in the target |
| Main tradeoff | More control before loading | More flexibility after ingestion |

The PostgreSQL implementation uses staging tables before inserting validated facts. It performs transformation and validation inside PostgreSQL through a stored procedure. This demonstrates a database-oriented ETL workflow and also illustrates how ELT-style processing can use the analytical database's own execution engine.

The distinction is about where and when transformation occurs, not simply which database product is used.

## 6. Staging and data quality

A staging area holds extracted source records before they enter final analytical structures.

Its purpose is to separate ingestion from publication. Source data can be inspected, validated, reconciled and rejected without immediately affecting analytical reports.

The PostgreSQL script uses `dw_demo.stg_sales` as its staging table. It deliberately permits records that violate analytical business rules. This allows invalid source records to be captured and investigated instead of silently disappearing during ingestion.

The `dw_demo.etl_reject` table records the staging row, batch, reason code, explanation and rejection time.

Typical validation categories include:

| Category | Example rule |
|---|---|
| Completeness | Required source identifiers must be present |
| Validity | Sale dates must be valid dates |
| Range | Quantity must be positive |
| Referential integrity | Customer and product keys must exist |
| Consistency | Sale status must permit fact loading |
| Uniqueness | A source transaction must not create duplicate facts |
| Arithmetic safety | Calculated amounts must not exceed supported numeric ranges |

A rejected record should retain enough context to identify its source, understand why it failed and determine whether it can be corrected.

Quarantine is different from deletion. It preserves evidence of source quality problems and supports investigation and controlled reprocessing.

## 7. Slowly Changing Dimensions

Dimension attributes can change over time. A customer may move from one region to another, or a product may be assigned to a different category.

A warehouse must decide whether reports should show the latest attribute value or preserve the historical value that applied when a fact occurred.

### 7.1 SCD Type 1

Slowly Changing Dimension Type 1 overwrites an existing dimension attribute.

For example, a customer's region is replaced with the latest region. Historical facts joined to that customer will then appear under the updated region.

Type 1 is appropriate when historical changes do not need to be preserved for reporting.

The Python and JavaScript examples use simplified Type 1 dimension updates.

### 7.2 SCD Type 2

Slowly Changing Dimension Type 2 retains multiple dimension versions.

The customer table includes:

- A stable customer business key.
- A warehouse surrogate key.
- `valid_from` and `valid_to` dates.
- An `is_current` indicator.

For customer `C001`, the PostgreSQL and Java implementations retain two historical records:

| Customer | Region | Valid from | Valid to | Current |
|---|---|---|---|---|
| C001 | North | 2025-01-01 | 2026-01-01 | No |
| C001 | East | 2026-01-01 | 9999-12-31 | Yes |

The customer version selected for a fact must cover the fact's business date.

The effective-date condition is:

`valid_from <= sale_date AND sale_date < valid_to`

The exclusive upper boundary avoids ambiguity when one version ends on the same date that the next begins.

The Java implementation checks for overlapping customer validity intervals. The PostgreSQL script includes a timeline validation query that identifies overlaps and gaps.

Type 2 preserves historical context, but introduces more complex dimension lookup and maintenance requirements.

## 8. Incremental loading, idempotency and recovery

Incremental loading processes only new or changed source records. It reduces repeated extraction and transformation work.

A warehouse pipeline needs a reliable way to identify the last committed source change.

The Python implementation uses an append-only change sequence. The warehouse stores the latest committed sequence in `etl_state`.

The JavaScript implementation tracks the last processed source sequence in the analytical store.

The PostgreSQL implementation groups staged records into batches and maintains batch status and counts.

Idempotency means that repeating an operation produces the same intended result without creating unintended duplicates.

The project uses source identifiers as deduplication keys:
- Python uses `source_sale_id` as the fact primary key.
- JavaScript stores facts in a `Map` keyed by sale identifier.
- C++17 maintains a set of loaded sale identifiers.
- Java uses a map keyed by sale identifier and compares source versions.
- PostgreSQL enforces a unique constraint on `(source_system, source_sale_id)`.

The source version or change timestamp determines whether an incoming record is newer than an existing fact.

A production implementation also needs an explicit policy for source deletions, corrections, reversals and late-arriving records. Deleting a source record should not automatically delete historical warehouse information without a defined business rule.

## 9. OLAP operations and analytical reporting

OLAP queries examine data from different analytical perspectives.

Common operations include:

| Operation | Meaning | Example |
|---|---|---|
| Roll-up | Aggregate to a higher level | Daily sales to monthly sales |
| Drill-down | Move to a more detailed level | Annual sales to quarterly sales |
| Slice | Filter on one dimension | Sales for one year |
| Dice | Filter on multiple dimensions | Electronics sales in selected regions |
| Pivot | Rotate dimensions in a report | Regions as columns and months as rows |

The implementations demonstrate analytical aggregation by customer region and product.

A query that groups sales by region performs several operations:
1. Read the sales fact records.
2. Join customer dimension keys to their descriptive records.
3. Group facts by region.
4. Calculate transaction count, units and revenue.
5. Order the resulting groups by revenue.

The PostgreSQL script also performs monthly reporting with CTEs and window functions. `RANK()` identifies regional revenue positions within each year and month.

These analytical queries differ from selective operational lookups. They commonly scan more records, join dimensions and calculate aggregates.

## 10. Data infrastructure and performance

A data warehouse is part of a wider data infrastructure. Its operation depends on ingestion, processing, storage, governance, monitoring and reporting components.

### 10.1 Source systems

Operational systems are authoritative for their own transactions. They may include application databases, point-of-sale systems, customer management platforms and external feeds.

A warehouse should preserve source-system identity and source transaction identifiers to support lineage and reconciliation.

### 10.2 Ingestion and change capture

Ingestion transports source records into staging or raw storage.

Batch ingestion groups records for periodic processing. Streaming or event-based ingestion processes changes as they arrive.

The appropriate choice depends on:
- Required reporting freshness.
- Source-system capabilities.
- Data volume.
- Network and compute capacity.
- Recovery and replay requirements.

The JavaScript example demonstrates event-driven ingestion. The Python and PostgreSQL implementations demonstrate batch-oriented processing.

### 10.3 Storage layouts

Row-oriented storage is generally useful when applications frequently retrieve or modify complete records.

Column-oriented storage is useful for analytical workloads that scan a small subset of columns across many records.

The C++17 program models a columnar fact store using separate vectors for individual attributes. This structure-of-arrays design reduces the need to access unrelated attributes during a narrow analytical scan.

The implementation is an in-memory demonstration, not a complete compressed columnar database. Real columnar systems add compression, encoding, partitioning, parallel scans and durable storage.

### 10.4 Indexing

Indexes reduce the amount of data that must be scanned for suitable query patterns.

The PostgreSQL implementation creates indexes for:
- Fact table date filtering.
- Customer and date lookups.
- Product and date lookups.
- Staging batch retrieval.
- Customer region filtering.
- Product category filtering.

Indexes are not free. They consume storage and increase write and maintenance costs. An index should correspond to actual query patterns and be evaluated with query plans and representative data volumes.

### 10.5 Partitioning

Large fact tables are often partitioned by date or another useful key.

Date partitioning can:
- Reduce the amount of data scanned for time-bounded reports.
- Simplify retention and archival operations.
- Support parallel loading of independent partitions.
- Allow maintenance of older data separately.

The examples use date keys and date-oriented indexes but do not implement physical table partitioning. Partitioning becomes valuable when table size, query patterns and retention requirements justify its operational cost.

### 10.6 Performance considerations

Analytical performance depends on several factors:

- Appropriate fact-table grain.
- Selective filtering and well-designed joins.
- Suitable indexes and partition boundaries.
- Statistics that allow the query planner to estimate row counts.
- Efficient data types and storage representations.
- Batch size and parallelism.
- Data skew and cardinality.
- Memory available for joins, sorting and aggregation.

The C++ implementation uses hash-based duplicate detection and ordered aggregation. Its duplicate checks are typically constant time on average. The analytical report processes the fact vectors in linear time relative to the number of facts, apart from map operations.

The Java and JavaScript implementations use maps for dimension lookup and fact identity. Average lookup is constant time, subject to hash distribution and memory limits.

## 11. Implementation architecture

The five source implementations share one business domain but use different execution models.

### 11.1 Python: transactional SQLite ETL

The Python script separates an operational source database from an analytical warehouse database.

`OperationalSource` owns source customers, products and the append-only sales change log.

`AnalyticalWarehouse` owns the dimensional model, fact table, ETL state and quarantine table.

`load_batch()`:
- Reads the committed sequence watermark.
- Extracts new source events.
- Loads or refreshes dimensions.
- Validates sales records.
- Resolves warehouse dimension keys.
- Inserts or updates fact records.
- Quarantines invalid records.
- Advances the watermark within the same database transaction.

The fact table uses `source_sale_id` as its primary key. A newer `source_change_seq` updates an earlier fact version. A repeated event cannot create a duplicate fact.

The report methods aggregate sales by region and product. Assertions verify initial loading, correction handling and an empty incremental batch.

The use of separate in-memory SQLite connections keeps the example self-contained. A production deployment would use durable databases, operational monitoring, connection management and an explicit cross-system recovery strategy.

### 11.2 JavaScript: event-driven warehouse pipeline

The JavaScript implementation uses Node.js standard-library capabilities.

`SourceStore` is an event emitter. It publishes validated source events and provides an asynchronous generator for incremental batches.

`WarehousePipeline` consumes those batches and emits operational events such as:
- `source.received`
- `batch.loaded`
- `batch.failed`
- `pipeline.completed`

The analytical store uses `Map` objects for dimensions, facts and quarantined records.

The pipeline creates a staged snapshot of warehouse state before processing. It replaces committed state only after the batch satisfies the configured reject-ratio policy.

The implementation also:
- Rejects invalid numeric values.
- Protects calculations from unsafe JavaScript integer precision.
- Validates calendar dates.
- Deduplicates by source sale identifier.
- Uses source sequence numbers to detect newer events.
- Processes batches asynchronously.
- Prevents concurrent calls to the same pipeline instance.

This is an in-memory model. A production event-processing service would require durable checkpoints, distributed failure handling, persistent storage, explicit event replay rules and backpressure controls.

### 11.3 C++17: columnar fact storage

The C++17 implementation focuses on compact analytical storage and batch integrity.

`SaleEvent` represents incoming operational data. `Customer` and `Product` represent dimensions. `ColumnarFacts` stores each fact attribute in a separate vector.

The `WarehouseEngine`:
- Validates source identifiers and dates.
- Resolves customer and product dimension keys.
- Checks arithmetic overflow.
- Rejects duplicate source identifiers.
- Quarantines invalid events.
- Commits a staged batch.
- Aggregates revenue and units by region and product.

The separate vectors form a structure-of-arrays design. It allows an analytical operation to access only required attributes instead of loading complete row objects.

The implementation uses copy-on-write state for batch-level atomicity. This is straightforward for a small demonstration but copies the existing fact vectors and duplicate set. That cost can become substantial for large datasets. Production systems would use durable transactional storage, append-oriented segments, versioned files or another storage strategy designed for large fact volumes.

The correction example is insert-only and uses a new sale identifier. The other implementations demonstrate source-version-based correction of an existing business sale.

### 11.4 Java 17: enterprise ETL and governance

The Java implementation uses records, interfaces, collections, futures and explicit service classes.

Its main domain types include:
- `CustomerVersion`
- `Product`
- `Sale`
- `Fact`
- `Snapshot`
- `LoadMetrics`
- `LoadAudit`

`OperationalSource` separates source extraction from pipeline logic. Three extraction operations run concurrently using `CompletableFuture`.

`JobTracker` controls permitted state transitions:

CREATED
   |
   v
EXTRACTING
   |
   v
VALIDATING
   |
   v
LOADING
   |
   v
SUCCEEDED

An error moves the job to `FAILED`.

The warehouse maintains customer dimension history using SCD Type 2 validity intervals. It resolves the appropriate customer version using the sale date.

`QualityPolicy` determines whether a batch meets its maximum permitted rejection ratio and minimum loaded-record requirement.

`AccessPolicy` distinguishes ETL execution privileges from analytical reporting privileges. Only a principal with the appropriate role can execute a pipeline or read reports.

The warehouse constructs staged collection copies and commits them only after validation and policy evaluation. This provides a clear transactional model for an in-memory demonstration. Large enterprise deployments would normally use database transactions or durable storage rather than copying all warehouse state.

### 11.5 PostgreSQL: relational warehouse and controlled ETL

The PostgreSQL script implements a relational dimensional warehouse.

The `dw_demo` schema contains:
- `etl_batch` for pipeline execution state and metrics.
- `stg_sales` for source records.
- `etl_reject` for failed quality checks.
- `dim_customer` for SCD Type 2 customer versions.
- `dim_product` for product attributes.
- `dim_date` for calendar attributes.
- `fact_sales` for measured sales events.
- `publication_policy` for batch quality limits.

`process_sales_batch()` applies validation, dimension lookup, rejection handling and fact loading.

The fact table has a unique constraint on source system and source sale identifier. Its `ON CONFLICT` logic updates an existing fact only when the incoming source change timestamp is newer.

The generated `gross_cents` column derives gross value from quantity and unit price. The database enforces quantity, price and referential integrity through constraints.

A trigger validates ETL batch state transitions. The batch procedure changes the state from `PENDING` to `RUNNING` and then to either `SUCCEEDED` or an error state if an operation is handled accordingly by the calling transaction.

The publication eligibility view evaluates batch completion, loaded-record count and rejection ratio against the active quality policy.

The reporting views expose enriched facts and monthly regional revenue without repeating dimension joins in each report.

## 12. Batch state, transactions and failure handling

A production ETL pipeline needs explicit state management.

A typical batch state model is:

PENDING
   |
   v
RUNNING
   |
   +----> SUCCEEDED
   |
   +----> FAILED

A batch should not be marked successful merely because extraction completed. Its data changes must pass validation, loading and publication checks.

Transactions help ensure that related database operations succeed or fail together.

The PostgreSQL procedure is invoked inside an explicit transaction. A failure that raises an exception aborts that transaction unless the caller handles it through an appropriate transaction or exception strategy. The batch's prior committed state remains available for investigation.

The Python implementation commits fact changes and its sequence watermark together. The JavaScript and Java implementations use staged collection copies before replacing committed state.

A real pipeline should record:
- Batch identifier and source system.
- Extraction start and completion times.
- Number of source records.
- Number of inserted or updated records.
- Number of skipped records.
- Number of rejected records.
- Error details.
- Last committed watermark.
- Pipeline and transformation version.

These details support troubleshooting, operational monitoring and reconciliation.

## 13. Data governance, security and lineage

Data governance defines how data is owned, accessed, validated, retained and used.

Important controls include:

- **Access control:** Restrict access according to user responsibilities.
- **Least privilege:** Grant only the database and application permissions needed for a task.
- **Lineage:** Preserve source identity, source record keys and load history.
- **Data quality:** Apply documented rules and report violations.
- **Auditability:** Record execution status, timestamps and processing metrics.
- **Privacy:** Restrict access to personal information and apply appropriate retention rules.
- **Encryption:** Protect data in transit and at rest.
- **Credential management:** Use managed secrets rather than embedding credentials in application code.
- **Recovery:** Test backup, replay and restoration procedures.

The Java example uses role-based access checks to separate ETL execution from report access. The PostgreSQL example records source systems and batch metadata.

These are demonstration-level controls. A production system also needs database roles, grants, row-level security where suitable, authentication integration, encrypted connections, centralized auditing and managed credential storage.

Source identifiers and timestamps are useful lineage attributes, but they do not replace complete lineage metadata. A governed production pipeline should also identify transformation versions and source-to-target mappings.

## 14. Failure scenarios and design responses

| Failure scenario | Risk | Appropriate response |
|---|---|---|
| Source unavailable | Extraction cannot complete | Retain the last committed watermark and retry according to policy |
| Duplicate source event | Duplicate fact values | Enforce a stable source business key |
| Invalid quantity | Incorrect sales measure | Quarantine and record the validation reason |
| Unknown customer | Fact cannot resolve its dimension | Reject, or apply a documented unknown-member policy |
| Late-arriving dimension | Valid fact arrives before its dimension | Defer or use an explicit inferred-member process |
| Customer attribute changes | Historical reports may be distorted | Select the appropriate SCD strategy |
| Partial load failure | Inconsistent fact and watermark state | Use transactional loading |
| Source correction | Previously loaded fact becomes outdated | Use source versions or change timestamps |
| Arithmetic overflow | Incorrect monetary measure | Validate numeric ranges before calculating |
| Duplicate batch execution | Repeated work or duplicate facts | Enforce batch identity and idempotent fact keys |
| Excessive rejection rate | Unreliable analytical publication | Apply a quality gate |
| Unauthorized report access | Exposure of restricted data | Enforce role and database permissions |

The correct response depends on the business meaning of the data. For example, an unknown customer may be a temporary ingestion delay, a source defect or a legitimate anonymous transaction. A pipeline should not silently assign an arbitrary customer key without a defined policy.

## 15. Limitations of the implementations

These implementations focus on foundational warehouse engineering mechanisms. They do not form a distributed production data platform.

| Implementation | Demonstrated | Not implemented |
|---|---|---|
| Python | SQLite source and warehouse, incremental change sequence, transactional load, quarantine, reporting | Distributed extraction, durable external orchestration, physical partitions |
| JavaScript | Event-based ingestion, asynchronous batching, state staging, event reporting | Persistent event broker, distributed consumers, durable checkpoint storage |
| C++17 | Columnar in-memory facts, batch staging, duplicate detection, analytical aggregation | Compression, disk-based segments, parallel query execution |
| Java 17 | Enterprise domain types, parallel extraction, job states, SCD Type 2, quality and access policies | Distributed job scheduling, database-backed transactions, enterprise identity integration |
| PostgreSQL | Star schema, SCD Type 2, staging, stored procedure, constraints, indexes, views and batch eligibility | Distributed ingestion, physical partitioning, production role provisioning, external orchestration |

The examples also use a small retail dataset. Real warehouses may combine several source systems with different identifiers, currencies, calendars, data definitions and update semantics.

A larger implementation must address source reconciliation, late-arriving facts, deletion handling, schema evolution, privacy rules, distributed execution, workload isolation, retention and disaster recovery.

## 16. Technical terms

| Term | Definition |
|---|---|
| Data warehouse | An integrated data store designed primarily for analysis and reporting |
| Analytical database | A database optimized for analytical queries |
| OLTP | Online Transaction Processing, focused on operational transactions |
| OLAP | Online Analytical Processing, focused on multidimensional analysis |
| ETL | Extract, Transform and Load |
| ELT | Extract, Load and Transform |
| Staging area | Temporary or intermediate storage for extracted source data |
| CDC | Change Data Capture, the collection of changes made in a source system |
| Fact table | A table containing measurable business events |
| Dimension table | A table containing descriptive attributes used to analyze facts |
| Grain | The exact level of detail represented by one fact row |
| Business key | An identifier defined by the operational business domain |
| Surrogate key | A warehouse-generated identifier |
| Star schema | A dimensional layout with a fact table connected to dimensions |
| SCD | Slowly Changing Dimension, a strategy for handling dimension changes |
| Watermark | A stored position used to identify previously processed source changes |
| Idempotency | Repeating an operation without producing unintended duplicate effects |
| Data lineage | Information about the origin and transformation of data |
| Data quality | The degree to which data meets defined validity and usability rules |
| Quarantine | Isolated storage for records that fail processing rules |
| Columnar storage | A layout in which values from the same attribute are stored together |
| Partitioning | Dividing a large table or dataset into manageable subsets |
| Surrogate date key | A warehouse key representing a calendar date |
| Reconciliation | Comparing source and warehouse records or totals |
| Late-arriving data | Source data received after its expected processing window |

## 17. Practical interpretation

The implementations illustrate why a data warehouse is more than a second database containing copied operational records.

A useful warehouse needs a defined fact grain, stable dimensions, reliable source identification, validation rules, incremental processing and consistent analytical definitions.

ETL controls how source data enters the analytical environment. Dimensional modeling defines how business events can be analyzed. OLAP queries provide aggregation and exploration. Data infrastructure supplies the storage, execution, security and operational controls required to keep the system dependable.

The engineering decisions are connected: a source change strategy affects idempotency; dimension history affects fact lookups; fact grain affects reporting accuracy; indexing and storage layout affect query performance; and transaction boundaries affect recovery after failure.
