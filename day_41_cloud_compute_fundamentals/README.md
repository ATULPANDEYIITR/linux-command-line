# Cloud Compute Fundamentals

## Technical scope

Cloud compute provides on-demand processing capacity through virtual machines and related compute services. A cloud instance is a provisioned compute environment with a defined resource configuration, operating-system environment, network interfaces, and lifecycle.

This project examines the relationship between instance sizing, virtual CPUs, memory, instance families, host capacity, provisioning, lifecycle management, and compute cost. It implements a small compute control plane in Python and JavaScript, models host allocation as a C++ case study, represents enterprise resource policies in Java, and uses PostgreSQL to maintain a relational inventory of compute resources.

The examples use fictional instance types and prices. Their purpose is to explain compute architecture and capacity planning, not to reproduce the catalog or billing rules of a specific cloud provider.

## Cloud instances and virtualization

A cloud instance is a logical compute resource made available to a workload. A virtual machine typically runs on a hypervisor, which manages access to physical processors, memory, storage, and networking. The cloud control plane handles requests and resource allocation, while the data plane and underlying virtualization infrastructure provide execution and connectivity.

The distinction between a logical instance and its physical host matters because users usually select a virtual resource configuration rather than a specific processor or memory module. A provider maps the requested configuration to available infrastructure while respecting compatibility and capacity constraints.

A useful compute model contains three separate entities:

- **Instance type:** The catalog specification describing vCPUs, memory, architecture, network capability, family, and price.
- **Physical host:** The underlying machine with finite processor and memory capacity.
- **Compute instance:** A provisioned resource that refers to an instance type and, while running, consumes capacity on an eligible host.

Separating these entities prevents a common modeling error: treating the number of vCPUs in an instance type as if it were the number of physical processor cores dedicated exclusively to that instance.

## Virtual CPUs and processor capacity

A virtual CPU, or vCPU, represents a unit of processor capacity exposed to a virtual machine. Its physical implementation depends on the provider and infrastructure. A vCPU may correspond to a hardware thread or another provider-defined allocation of processor time.

The number of vCPUs is an important sizing parameter, but it does not independently determine application performance. Two instances with the same vCPU count can differ in processor generation, sustained performance, CPU scheduling, memory bandwidth, network throughput, and virtualization overhead.

CPU sizing should be based on workload behavior:

- Web services and application servers often benefit from enough vCPUs to handle concurrent requests without excessive scheduling delay.
- Batch processing and parallel numerical workloads can benefit from compute-optimized instances when their algorithms use multiple cores effectively.
- Databases may require a balance of processor capacity, memory, storage performance, and network throughput.
- Low-utilization development services may fit smaller or burstable configurations when their latency and sustained CPU requirements permit it.

CPU utilization alone is not sufficient for sizing. A service can show moderate average utilization and still suffer from short CPU saturation periods. Monitoring should include peak utilization, request latency, queue depth, throttling, and workload concurrency.

## Memory sizing and memory-to-vCPU ratio

Memory is commonly measured in GiB. It holds active application data, database buffers, caches, operating-system structures, and runtime state.

The memory-to-vCPU ratio is calculated as:

\[
\text{Memory ratio} =
\frac{\text{Memory in GiB}}{\text{vCPU count}}
\]

For a four-vCPU instance with 32 GiB of memory, the ratio is 8 GiB per vCPU. This ratio is useful for comparing instance configurations, but it is not a direct measure of performance.

Memory-intensive workloads include in-memory databases, analytical processing, large caches, and applications that maintain substantial working sets. Insufficient memory can cause garbage-collection pressure, swapping, cache eviction, or out-of-memory termination.

The appropriate size depends on the working set and its growth, not only on the average memory consumption observed during a short test. Capacity planning should leave sufficient headroom for traffic peaks, deployment overlap, operating-system requirements, and background jobs.

## Instance families

Instance families group compute configurations according to their intended resource balance. The precise characteristics and availability of families vary between providers.

| Family | Primary design objective | Representative workload |
|---|---|---|
| General-purpose | Balanced processor and memory resources | APIs, application servers, small databases |
| Compute-optimized | Higher processor capacity relative to memory | Batch computation, parallel processing, CPU-heavy services |
| Memory-optimized | Larger memory capacity relative to processor count | In-memory analytics, large caches, memory-heavy databases |
| Burstable | Economical baseline CPU capacity with permitted bursts | Development environments, low-average-utilization services |
| Accelerated | Specialized hardware such as GPUs | Parallel numerical workloads, graphics processing, supported machine-learning workloads |

A family designation is a starting point, not a guarantee that a workload will perform well. Storage throughput, network capacity, processor generation, accelerator availability, and application compatibility also matter.

### Burstable capacity

Burstable instances require special consideration because average CPU usage can hide sustained demand. Some providers implement a baseline CPU entitlement and a credit mechanism. When an instance uses less than its baseline, it may accumulate credits; sustained use above the baseline consumes them.

The exact credit rules are provider-specific. A burstable instance that performs well during a short test may slow down during a long-running computation after its available burst capacity is exhausted.

The JavaScript catalog and the other examples represent burstable configurations as a family. They do not attempt to simulate a particular provider's credit algorithm.

### Accelerated compute

Accelerated instances expose specialized hardware in addition to conventional processor and memory resources. The presence of an accelerator does not mean that every application becomes faster. The application must use compatible software and APIs, and its workload must benefit from the accelerator.

The Python and SQL catalogs include an accelerated family to show how a catalog can represent a distinct configuration category. They do not emulate GPU execution or estimate accelerator utilization.

## Compute provisioning architecture

Provisioning transforms a resource request into an allocated, usable instance.

A typical control-plane workflow includes:

- Validating requested vCPU count, memory, architecture, family constraints, and spending limits.
- Selecting an instance type from the catalog.
- Finding an eligible host with enough compatible free resources.
- Reserving capacity and creating the instance record.
- Completing the transition to a running state after allocation succeeds.
- Reporting failure when no eligible configuration or host can satisfy the request.

The examples implement a simplified version of this workflow. Their host schedulers use deterministic placement strategies and in-memory data structures. Real providers must account for additional constraints such as processor topology, storage placement, availability zones, capacity reservations, quotas, security boundaries, and concurrent provisioning requests.

### Resource accounting

For a physical host:

\[
\text{Free vCPUs} =
\text{Total vCPUs} - \text{Reserved vCPUs}
\]

\[
\text{Free memory} =
\text{Total memory} - \text{Reserved memory}
\]

An instance can fit only if the host satisfies both resource constraints and the architecture requirement.

The model does not overcommit vCPUs or memory. Production virtualization systems may support overcommitment under controlled conditions, but overcommitment introduces contention and failure risks. It must not be confused with the existence of unused capacity at the logical instance level.

### Lifecycle states

The implementations model requested, provisioning, running, stopped, terminated, and failed states. State transitions are explicitly checked so that a terminated instance cannot accidentally return to a running state.

Stopping an instance releases its simulated host reservation. Restarting requires the scheduler to find capacity again. Consequently, a previously running instance may fail to restart if other workloads have consumed the available resources.

This model treats a stopped instance's configuration as persistent while its host reservation is released. It does not model operating-system boot, image creation, attached volumes, public IP changes, or application health checks.

A running state indicates successful allocation in the simulation. In a production environment, service readiness must be checked separately through health probes, networking checks, and application-level monitoring.

## Python implementation

The Python script uses `dataclass` objects and enumerations to represent instance specifications, physical hosts, compute instances, families, and lifecycle states.

The `InstanceType` class validates resource specifications and exposes a memory-to-vCPU ratio. The `PhysicalHost` class tracks reservations and calculates available CPU and memory. Its `can_fit()` method enforces architecture and capacity compatibility before allocation.

The `ComputeCloud` class combines the catalog, hosts, and instance registry. Its provisioning method records the request, enters the provisioning state, searches eligible hosts, reserves capacity, and transitions to running. Failed placement is recorded as a failed instance rather than silently producing a running instance without an allocation.

The separate `choose_instance_type()` function selects the lowest-cost configuration satisfying minimum CPU and memory requirements, an optional family preference, and an optional price limit. This illustrates the difference between selecting a suitable catalog configuration and finding an available physical host.

The cost estimator calculates period, monthly, and annual compute-only projections. It intentionally excludes storage, network charges, taxes, discounts, and other provider-specific billing rules.

The final demonstrations cover inventory reporting, capacity inspection, stopping and restarting, termination, invalid type requests, and illegal state transitions.

## JavaScript implementation

The JavaScript program uses Node.js and `EventEmitter` to model an observable compute control plane.

The `InstanceCatalog` encapsulates its type registry with a private field and validates entries before insertion. Returned specifications are frozen to prevent accidental mutation of catalog records. Selection filters configurations by resources, family, and budget before sorting candidates by price and resource size.

The `Host` class uses a reservation map to account for each allocation. Resource totals are derived from that map rather than maintained as independent mutable counters, reducing the chance that two counters become inconsistent.

The `ComputeControlPlane` emits state-change events during provisioning, startup, shutdown, failure, and termination. Such events can support audit logs, metrics, and downstream orchestration in a larger system.

Asynchronous boundaries and an optional `AbortSignal` illustrate how a control-plane operation can be cancelled before allocation. The implementation is still a single-process demonstration. It does not provide distributed locking, durable event delivery, retries with idempotency keys, or cross-process reservation guarantees.

The JavaScript cost estimator validates numeric inputs and rejects invalid instance counts. Its scope is intentionally limited to the compute rate and number of billed hours.

## C++ case study: Host allocation and capacity placement

The C++ program presents a repository-independent compute infrastructure scenario in which a control-plane engine must place workloads on physical hosts while respecting processor architecture, vCPU capacity, memory capacity, and cost limits.

The `InstanceType` structure represents immutable-style catalog specifications, while `ComputeRequest` captures the minimum requirements of a database workload. The `Host` class maintains a set of active allocation identifiers alongside its resource counters. Reservation and release operations validate allocation identity to prevent duplicate accounting or releasing an unknown allocation.

The `GovernanceEngine` owns the catalog, host inventory, and instance registry. Its selection algorithm chooses a compatible instance type by price and then vCPU count. Its placement algorithm sorts eligible hosts according to available memory and CPU capacity before attempting allocation.

This example distinguishes two optimization problems. Instance selection chooses a configuration from a catalog; placement chooses an available host for the selected configuration. A low-cost instance type is not sufficient if no compatible host can accommodate it.

The lifecycle implementation rejects invalid state transitions. A failed placement records a failed instance, and host release operations verify that the allocation exists. The final scenario tests a database request, a compute-heavy analytics workload, cost calculation, restart, termination, and an unknown instance type.

The implementation uses C++17 standard-library containers and exceptions. The placement algorithm sorts the host list, giving a sorting cost of \(O(H \log H)\) for \(H\) hosts, followed by at most \(O(H)\) placement checks. A production scheduler would need additional data structures, concurrency controls, and resource dimensions for larger inventories.

## Java implementation: Enterprise compute policies

The Java program represents compute provisioning as an enterprise service with explicit resource policy, catalog, host, instance, and lifecycle abstractions.

The `InstanceType` record validates the basic catalog specification. The `ComputePolicy` record defines minimum vCPUs, minimum memory, a maximum hourly rate, permitted instance families, and permitted architectures. Its `permits()` method centralizes policy evaluation rather than scattering resource checks across service methods.

`PhysicalHost` calculates resource consumption from its reservation map. `ComputeInstance` contains an explicit state-transition table, preventing illegal transitions such as moving directly from requested to terminated.

`ComputeService` selects the lowest-cost permitted configuration and searches eligible hosts for sufficient capacity. Its reporting method shows the workload, selected configuration, resource allocation, lifecycle state, and assigned host.

The cost estimator uses `BigDecimal` rather than binary floating-point arithmetic for monetary calculations. This provides predictable decimal arithmetic for the simplified billing model, although real billing must also follow the provider's rounding, metering, discount, and currency rules.

Immutable records and copied collections reduce accidental modification of policies and catalog specifications. The service itself is not thread-safe. A production deployment would require synchronized or transactional allocation, durable state, authorization, auditing, and recovery after partial failures.

## PostgreSQL data model

The SQL script models compute inventory and provisioning as related relational entities.

| Table | Responsibility |
|---|---|
| `instance_types` | Defines family, architecture, vCPU count, memory, network capacity, and hourly rate |
| `physical_hosts` | Stores physical capacity, architecture, and host availability |
| `provisioning_requests` | Captures resource requirements, budget limits, and request processing status |
| `compute_instances` | Stores provisioned instance identity, type, workload, lifecycle state, and tags |
| `resource_allocations` | Associates a running instance with its current host reservation |
| `compute_cost_records` | Stores usage intervals and computes the recorded charge |

Primary keys establish row identity. Foreign keys link instances to catalog specifications and requests, and allocations to instances and hosts. Unique constraints prevent duplicate type names, instance names, request assignments, and active allocation records for an instance.

Check constraints enforce positive CPU and memory values, valid families and architectures, non-negative rates, allowed lifecycle values, and valid cost intervals. The JSONB tag column requires an object and has a GIN index to support tag-oriented queries.

The catalog-selection query joins each request with types satisfying its minimum resources, family, architecture, and budget. A window function ranks compatible configurations by price and resource size. The insertion then creates instances from the best-ranked candidates for the database and API workloads.

The capacity view aggregates reservations per host. The inventory view joins the instance, type, allocation, and host tables to provide a consolidated operational view. Cost projections calculate eight-hour, monthly, and annual estimates from catalog rates, while the cost records store an explicit usage interval and billed-hour quantity.

### Database integrity and concurrent allocation

Relational constraints prevent many invalid records, but they do not by themselves enforce every cross-table resource invariant. For example, a simple foreign key cannot guarantee that the total vCPU and memory reservations on a host remain within capacity.

The SQL script uses a transaction when stopping the API instance and deleting its allocation. This prevents the lifecycle update and resource release from being committed as separate operations.

The placement query is deliberately a simplified demonstration. Under concurrent provisioning, two transactions could inspect the same free capacity and both attempt reservations. A production implementation should use a serialized allocation service or a carefully designed transaction with row locks and retry handling. It should also enforce architecture compatibility, host capacity, and the requirement that allocations belong only to running instances through controlled procedures, triggers, or equivalent transactional enforcement.

## Cost and capacity planning

Compute cost is commonly modeled as:

\[
\text{Compute cost} =
\text{Hourly rate} \times \text{Billed hours} \times \text{Instance count}
\]

For three instances priced at \$0.16 per hour and running for eight billed hours, the simplified compute charge is \$3.84.

The monthly estimate in the examples uses 730 hours as a planning convention. The annual estimate uses 8,760 hours. These figures are projections rather than exact billing promises.

Instance sizing should balance application performance and cost. Selecting a larger instance than necessary wastes resources, while selecting a configuration that is too small can increase latency, retries, queue depth, and operational instability.

Capacity planning should evaluate both the total available resources and their distribution across eligible hosts. A cluster can have sufficient aggregate free memory and CPU capacity but still fail to place a workload if no individual host has enough compatible capacity.

A basic concurrent-workload estimate is:

\[
\text{Concurrent workloads} =
\left\lfloor
\frac{\text{Total vCPUs} \times \text{Target utilization}}
{\text{Average vCPUs per workload}}
\right\rfloor
\]

This estimate assumes a sufficiently uniform workload and does not account for memory limits, CPU scheduling, burst behavior, uneven demand, or redundancy requirements. It is a planning approximation rather than a placement guarantee.

## Important limitations and operational considerations

The implementations use simplified catalogs, host inventories, and rates. They do not represent every cloud-specific resource dimension or billing rule.

Production provisioning should account for the following operational concerns:

- **Availability:** A host-level placement decision does not provide fault tolerance. Critical workloads require appropriate distribution across failure domains.
- **Architecture compatibility:** An instance type must match the host architecture and the workload's operating-system image and compiled dependencies.
- **Resource contention:** vCPU count does not guarantee exclusive physical cores or constant processor performance.
- **Memory pressure:** Host free memory and instance memory limits must be monitored alongside application-level memory usage.
- **Networking:** Network bandwidth, packet-processing limits, and traffic costs can constrain a workload even when CPU and memory are sufficient.
- **Persistent data:** Stopping or terminating compute capacity must be separated from storage-retention and data-deletion policies.
- **Security:** Provisioning must validate workload identity, permissions, network access, image provenance, and resource ownership.
- **Observability:** Lifecycle events should be correlated with allocation records, health checks, resource metrics, and billing records.
- **Concurrency:** Resource allocation must remain correct when multiple requests compete for the same host capacity.
- **Cost control:** Budgets, quotas, tags, idle-instance detection, and usage reporting should be applied without assuming that a catalog price captures the complete bill.

These concerns determine whether a compute configuration that appears suitable in a catalog will remain reliable, secure, and economical when deployed in a real environment.
