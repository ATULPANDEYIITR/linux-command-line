# Geographic Infrastructure: Regions, Availability Zones, and Fault Isolation

## Scope

Geographic infrastructure design determines where applications, compute capacity, databases, and replicated data operate. Its primary objective is to maintain acceptable service availability when infrastructure components fail, while respecting latency, capacity, data residency, and recovery requirements.

A **region** is a geographically distinct cloud infrastructure location. An **availability zone** is an isolated infrastructure failure domain within a region. Multiple zones can protect against certain localized failures, while deployment across regions can protect against a wider class of disasters.

Neither construct guarantees availability by itself. Resilience depends on application architecture, placement, replication, traffic routing, capacity reserves, failure detection, and tested recovery procedures.

The implementations in this repository use a simulated infrastructure inventory. Their region names, capacities, latencies, and recovery measurements are illustrative configuration values rather than claims about live cloud-provider infrastructure.

## Regions and availability zones are different failure domains

### Geographic regions

A region establishes a broad deployment boundary. Regions may differ in geographic distance, available services, network connectivity, pricing, regulatory requirements, and disaster exposure.

Regional placement influences:

- **Latency:** A geographically distant region generally introduces additional network propagation delay. Actual application latency also depends on routing, congestion, processing time, and service dependencies.
- **Data residency:** Workloads may be restricted to particular countries, jurisdictions, or approved geographic locations.
- **Disaster recovery:** A region can serve as a recovery destination when the primary region becomes unavailable.
- **Capacity planning:** A recovery region must have enough available resources to accept the workloads expected to fail over.
- **Operational complexity:** Cross-region replication, failover, consistency, and traffic management require additional controls.

A region is not automatically independent of every other region. Regions can share external dependencies, identity services, control planes, network providers, or operational procedures. Effective disaster recovery requires identifying these dependencies instead of assuming that geographic separation alone removes every common failure mode.

### Availability zones

Availability zones are designed to isolate failures within a region. Depending on the provider, an individual zone may represent one or more physically separate data centers with independent power, cooling, and networking characteristics.

Deploying application replicas across zones can reduce the impact of a localized outage. For example, a payment API with nine capacity units might distribute three units to each of three zones.

If one zone fails, six units remain. That deployment survives the failure only if six units satisfy the actual demand or if the architecture can add or move capacity quickly enough.

A replica count and a capacity requirement are different concepts. Three zones do not automatically imply that the application can tolerate one zone failure at full traffic. Capacity must be sized for the surviving failure domain.

### Failure-domain hierarchy

The following hierarchy illustrates the intended relationship:

- **Instance or process:** A process crash may be handled by a supervisor or replacement instance.
- **Availability zone:** A localized infrastructure failure requires surviving replicas in other zones.
- **Region:** A regional outage requires a viable deployment and data-recovery strategy outside the affected region.
- **Shared dependency:** A common identity provider, DNS service, external API, or deployment control plane can undermine geographic redundancy if it remains a single point of failure.

The larger the failure domain, the more likely recovery involves network routing, replicated state, and coordinated operational decisions rather than simply restarting an instance.

## Geographic placement is a constrained scheduling problem

A placement decision must satisfy multiple conditions simultaneously. A zone may have sufficient capacity but violate residency rules. Another zone may meet residency requirements but exceed the workload's latency limit. A third may satisfy both but lack enough free capacity.

The Python, JavaScript, C++, and Java implementations represent these decisions through a workload's required capacity, minimum zone count, maximum latency, and residency group.

The scheduler filters candidate zones before allocating resources. It then spreads an initial allocation across the required number of zones and distributes remaining capacity across eligible candidates.

This is a practical heuristic rather than a globally optimal scheduling algorithm. It is deterministic for a fixed inventory and ordering, which makes demonstrations and tests reproducible.

### Placement invariants

A valid placement should preserve these invariants:

- Every allocated zone belongs to an allowed region.
- The region satisfies the workload's residency requirements.
- The zone is healthy and meets the workload's latency threshold.
- Allocated capacity does not exceed the zone's configured capacity.
- The deployment spans at least the required number of eligible zones.
- The total allocation meets the workload's required capacity.
- Failed or unavailable zones are excluded from the usable-capacity calculation.

These conditions should be checked when scheduling and monitored after deployment. An initially valid placement can become insufficient after failures or changes in workload demand.

### Capacity and fault tolerance

Let \(C_i\) denote the capacity allocated to zone \(i\), and let \(H_i\) equal one when the zone is healthy and zero otherwise.

The surviving capacity is:

\[
C_{\text{surviving}} = \sum_i H_i C_i
\]

A workload requiring \(D\) units retains sufficient configured capacity only when:

\[
C_{\text{surviving}} \ge D
\]

This equation assumes that allocated units accurately represent usable application capacity. Real systems must also account for CPU and memory pressure, connection limits, database throughput, request distribution, dependency bottlenecks, and autoscaling delays.

The Python simulation uses this calculation to distinguish a healthy inventory from a deployment that can satisfy its capacity requirement after a failure.

## Python implementation: capacity-aware placement

The Python script defines immutable `Region` and `Workload` configurations alongside mutable `AvailabilityZone` objects. The environment validates the region-to-zone relationship when constructing its inventory.

The scheduler selects eligible zones by latency and remaining capacity. It reserves capacity only after it has constructed and validated a complete placement plan.

The implementation also includes:

- `DeploymentError` for invalid configurations and impossible placements.
- `fail_zone()` and `recover_zone()` for localized failure simulation.
- `fail_region()` and `recover_region()` for regional failure simulation.
- `surviving_capacity()` and `available_zone_count()` for post-failure evaluation.
- `haversine_km()` for approximate great-circle distance calculations.
- `RecoveryObjective` and `RecoveryPlan` for recovery-time and recovery-point assessment.

The distance calculation illustrates the relationship between geographic separation and potential network latency. It must not be treated as a latency estimator: physical distance does not reveal the actual network route or its performance.

The placement algorithm is intentionally simple. Its initial spreading step gives the selected zones a minimum allocation, while the capacity-aware filling step uses the remaining available capacity. A production scheduler would typically account for concurrent scheduling, resource dimensions, affinity constraints, cost, service dependencies, and placement changes during execution.

## JavaScript implementation: event-driven infrastructure health

The JavaScript implementation uses Node.js's `EventEmitter` to represent infrastructure events. Zone and region failures are applied through event handlers, making state transitions separate from the code that produces events.

`GeographicScheduler` maintains region and zone inventories, evaluates candidate placement, and reports surviving capacity. Its `emitOnce()` method uses event identifiers to demonstrate deduplication when the same event is delivered more than once.

This distinction matters in distributed monitoring systems. Events can be retried after timeouts or delivered repeatedly. A consumer should not blindly repeat side effects when it receives a duplicate notification.

The simulation keeps its deduplication set in memory, so it does not survive process restarts and is not a durable distributed idempotency mechanism. A production implementation would persist processed event identifiers or use a durable event-processing mechanism.

The implementation also separates zone health from region health. A failed region makes its zones unavailable, while recovery restores their configured health in the simplified model. Real recovery procedures should not mark every zone healthy automatically without checking infrastructure readiness and application dependencies.

The included assertions validate expected simulation behavior. They do not constitute a full reliability test suite for a distributed cloud deployment.

## C++ case study: deterministic placement and fault simulation

The C++ program models a payment workload distributed across zones in India West. Its `GovernanceEngine` stores regions and zones in ordered maps, and each region maintains the identifiers of its zones.

The placement engine performs candidate filtering, deterministic sorting, initial zone spreading, and capacity allocation. It constructs the plan before committing reservations, avoiding partial updates when ordinary validation fails.

The `Evaluation` structure reports both surviving units and surviving zones. These measurements answer different operational questions:

- Surviving units indicate whether the configured capacity requirement remains satisfied.
- Surviving zones indicate how much of the original geographic distribution remains available.

The case study simulates a single-zone failure followed by a regional outage. The second failure removes the entire primary region from the workload's usable capacity. A recovery region is useful only when the workload can actually be placed there and its data and dependencies are available.

The example also demonstrates a residency rejection by attempting to deploy an India-restricted workload in Singapore.

The C++ implementation is an in-memory simulation, not a concurrent production scheduler. It does not provide durable state, distributed locking, automatic traffic routing, or database replication. A real implementation would need coordination to prevent simultaneous schedulers from allocating the same remaining capacity.

## Java implementation: explicit domain modeling

The Java program represents infrastructure using `Region`, `Zone`, `Workload`, and `InfrastructureService` domain types.

The `Health` and `Residency` enums constrain state and residency values to explicitly supported categories. The `RecoveryObjective` and `RecoveryMeasurement` records model recovery requirements separately from observed recovery behavior.

The infrastructure service validates region membership, workload residency, latency limits, zone health, and capacity before committing placement. If reservation fails after an earlier reservation succeeds, the implementation releases the earlier reservations.

The workload exposes an immutable copy of its placement map rather than returning its internal mutable collection. This prevents callers from silently changing placement records without passing through the service's validation logic.

Java streams filter and sort candidate zones, while the domain classes keep capacity reservations close to the resources they govern. This separation improves clarity but does not eliminate concurrency hazards. The example assumes that placement operations are not executed concurrently by competing schedulers.

The service also models zone and regional failures separately. Recovery-objective evaluation is independent of placement, emphasizing that operational recovery targets are not the same as resource-allocation rules.

## SQL implementation: relational inventory and integrity enforcement

The PostgreSQL script represents infrastructure as related tables rather than nested application objects.

| Table | Purpose |
|---|---|
| `geographic_region` | Geographic identity, residency group, location, and regional health |
| `availability_zone` | Region membership, capacity, latency, and zone health |
| `workload` | Required capacity, minimum zone spread, latency limit, and residency requirement |
| `workload_region_allowlist` | Explicit region eligibility for each workload |
| `placement` | Allocated capacity for each workload-zone pair |
| `replication_link` | Cross-region replication mode, status, and lag |
| `recovery_objective` | RTO, RPO, detection time, failover time, and test status |
| `infrastructure_event` | Recorded failure or recovery events with unique event keys |

Primary keys and foreign keys enforce entity identity and referential integrity. Unique constraints prevent duplicate region codes, zone codes, and workload-region allowlist entries. Check constraints reject negative capacity, invalid coordinates, and impossible recovery measurements.

The `validate_placement()` trigger verifies that the target zone and region are healthy, the latency limit is respected, the region satisfies residency requirements, the region appears in the workload allowlist, and the allocation fits the zone's capacity.

The placement trigger locks the selected zone row during validation. That lock helps serialize capacity changes for that zone, but a complete concurrent scheduling transaction must also coordinate any global workload requirements, such as minimum zone spread and aggregate allocation across several zones. A transaction-scoped advisory lock is demonstrated for the sample placement operation.

The `infrastructure_event` table gives each event a unique key. Its trigger applies regional events to all zones in that region and applies zone-specific events to the selected zone. This demonstrates relationally managed state changes and duplicate-event protection.

The script includes queries for:

- Allocated and unallocated capacity by zone.
- Workloads whose placement falls below required capacity or healthy zone spread.
- Regional recovery candidates and their measured recovery objectives.
- Surviving capacity after a zone outage.
- The number of healthy regions hosting each workload.

The script's integrity trigger applies to placement writes, not every possible change that could invalidate a placement. For example, changing a zone's health or capacity can make an existing placement unsuitable. Production systems should enforce health transitions through controlled transactions and use explicit monitoring queries to detect existing violations.

The regional recovery query estimates RPO from replication lag and evaluates RTO using detection and failover durations. These calculations are useful screening checks, but they do not prove recoverability. Replication mode, data consistency, recovery procedures, DNS behavior, and dependent services must be validated through recovery exercises.

## RTO and RPO: distinct recovery objectives

The Recovery Time Objective (RTO) specifies the maximum acceptable time to restore a service after a disruptive event.

The Recovery Point Objective (RPO) specifies the maximum acceptable amount of data loss, commonly expressed as a time interval before the incident.

The sample calculations are:

\[
RTO_{\text{observed}} =
T_{\text{detection}} + T_{\text{failover}}
\]

A recovery plan satisfies its configured RTO when the observed or estimated restoration time does not exceed the target.

RPO assessment is different. A configured replication lag provides an estimate of the potential recovery point, but actual data loss depends on acknowledged writes, replication semantics, consistency guarantees, and the precise failure sequence.

Synchronous replication can reduce the risk of losing acknowledged writes but may increase write latency and introduce cross-region availability trade-offs. Asynchronous replication can reduce latency but may leave recent writes unavailable after an abrupt primary-region failure.

Neither approach is universally preferable. The appropriate choice depends on the business consequences of data loss, acceptable latency, transaction semantics, and recovery requirements.

## Failure scenarios and operational interpretation

### Single-zone failure

A localized zone outage removes the affected zone from usable capacity. Other zones may continue serving traffic if application replicas, data access, routing, and dependencies remain functional.

A resilient deployment must have enough surviving capacity and must avoid dependencies that exist only in the failed zone.

### Regional failure

A regional outage can affect every zone in that region. Deploying three zones within one region does not provide three independent regional recovery destinations.

Cross-region recovery requires more than a second copy of application code. It can require replicated databases, compatible secrets and identity configuration, network connectivity, traffic-routing changes, recovery automation, and reserved capacity.

### Capacity exhaustion during failover

A recovery region may be healthy yet unable to accept the full workload because its resources are already occupied by other services.

Capacity planning should model correlated failures. If several workloads normally share a recovery region, they may all request additional capacity at the same time.

### Residency and latency conflicts

A distant region can have available resources and still be unsuitable because of residency restrictions or latency requirements. The sample schedulers reject ineligible regions before allocating capacity.

Real deployments may need separate rules for personal data, encryption keys, backup copies, disaster-recovery replicas, and administrative access. A broad geographic label alone does not establish regulatory compliance.

### Recovery and failback

Restoring the original region is not equivalent to safely returning production traffic to it. Failback may require verifying data consistency, reconciling writes, restoring capacity, and changing traffic gradually.

A safe recovery procedure defines when a region becomes eligible, how application health is verified, and which system has authority to change routing or placement.

## Limitations of the simulations

The four programs share a common educational model but have different implementation concerns.

- The Python script emphasizes configuration validation, geographic calculations, capacity allocation, and recovery objectives.
- The JavaScript program emphasizes event-driven state changes and in-process event deduplication.
- The C++ program emphasizes deterministic scheduling, explicit capacity calculations, and failure evaluation.
- The Java program emphasizes domain types, immutable views of placement, validation boundaries, and rollback of failed reservations.
- The SQL script emphasizes relational integrity, durable event records, placement validation, and operational queries.

None of the in-memory programs simulates real network partitions, database consensus, traffic-routing convergence, service discovery, or actual cloud-provider failure behavior. Their health transitions are simplified and immediate.

The SQL model is a relational demonstration, not a complete orchestration platform. Its triggers do not automatically provision servers, copy data, redirect clients, or restore application state.

## Production design considerations

A production geographic architecture should be designed around explicit failure assumptions and measurable recovery requirements.

- **Define failure boundaries:** Document which failures must be tolerated, including process, instance, zone, region, and shared-dependency failures.
- **Size surviving capacity:** Verify that remaining resources can serve peak demand after the required failure scenarios.
- **Separate health from capacity:** A healthy zone may be overloaded, and a zone with free capacity may be unreachable from the application.
- **Protect state:** Specify replication guarantees, transaction consistency, backup retention, and recovery-point verification.
- **Automate safely:** Make failover operations idempotent, observable, and protected against conflicting concurrent actions.
- **Measure recovery:** Track detection time, routing convergence, restoration time, replication lag, and the success of recovery exercises.
- **Test correlated failures:** Simulate the loss of multiple zones, a full region, and dependencies shared by nominally separate deployments.
- **Control placement changes:** Validate residency, latency, capacity, and policy constraints whenever a workload is moved or scaled.
- **Verify failback:** Treat return to the primary region as a separate operational workflow with data-consistency checks and controlled traffic migration.

Geographic resilience is an end-to-end property. Regions and availability zones provide the physical and logical boundaries around which recovery can be designed, but the resulting reliability depends on whether applications, data, capacity, routing, and operational procedures continue to function across those boundaries.
