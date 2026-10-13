# Auto Scaling: Capacity Management and Automated Infrastructure Expansion

## Scope

Auto scaling adjusts computing capacity in response to changes in workload demand. The objective is to maintain an acceptable level of service while controlling infrastructure cost.

This repository models a web API experiencing ordinary traffic, sudden demand increases, sustained peak load, and a return to low demand. Its five implementations cover different parts of the problem:

- **Python** implements a stateful simulation with traffic generation, scaling decisions, warmup delays, health failures, cost estimates, and JSON reporting.
- **JavaScript** models an event-driven controller using asynchronous metric collection and event notifications.
- **C++** presents a capacity-management engine with explicit resource states, bounded scaling actions, failure recovery, and vertical sizing comparisons.
- **Java** represents an enterprise-oriented scaling service with immutable policy definitions, domain types, event delivery, and a recorded action history.
- **PostgreSQL** stores resource inventory, policy definitions, time-series observations, scaling decisions, and capacity summaries.

All five implementations simulate resource management. They do not provision real infrastructure.

## Core Concepts

### Horizontal scaling

Horizontal scaling changes the number of compute instances running a service.

Scale-out adds instances when demand exceeds the capacity that existing instances can serve. Scale-in removes excess instances when demand remains low enough to satisfy the service's capacity requirements.

For a fleet of identical instances, the approximate total request capacity is:

\[
C = N \times C_i
\]

where:

- \(C\) is the fleet's theoretical request capacity.
- \(N\) is the number of ready, healthy instances.
- \(C_i\) is the capacity of one instance.

If an instance can sustain 240 requests per second, four ready instances provide an estimated capacity of 960 requests per second. This estimate assumes the load balancer distributes traffic effectively and the application scales across instances without a major shared bottleneck.

The desired instance count is not necessarily the same as the ready instance count. New instances can take time to initialize, and failed instances may remain recorded until the controller processes their removal.

### Vertical scaling

Vertical scaling changes the resources assigned to an individual instance. Increasing CPU cores or memory can allow a larger instance to handle more traffic without increasing the number of instances.

A simplified fleet-sizing equation is:

\[
N = \left\lceil \frac{D}{C_i U_t} \right\rceil
\]

where \(D\) is demand and \(U_t\) is the target utilization expressed as a fraction.

At 900 requests per second and a 60% target utilization:

| Instance type | Cores | Capacity per instance | Hourly cost | Required instances | Fleet hourly cost |
|---|---:|---:|---:|---:|---:|
| general-small | 2 | 240 requests/s | $0.08 | 7 | $0.56 |
| general-large | 8 | 960 requests/s | $0.30 | 2 | $0.60 |

These illustrative rates show that fewer large instances do not automatically produce lower cost. Actual selection must account for workload behavior, memory requirements, availability, network limits, and the application's ability to use available CPU resources.

Vertical scaling may also require a restart or replacement, and every instance type has a maximum size. Horizontal scaling is often preferable when workloads can be distributed across independent instances.

### Automated infrastructure expansion

Automated scaling connects monitoring, policy evaluation, desired-capacity updates, and infrastructure reconciliation.

A typical control loop is:

1. Collect service and infrastructure metrics.
2. Evaluate recent measurements against a scaling policy.
3. Determine whether capacity should increase, decrease, or remain unchanged.
4. Update desired capacity within configured limits.
5. Provision or terminate resources through an infrastructure provider.
6. Wait for health checks and initialization to complete.
7. Verify that actual capacity matches the desired state.

The implementations simulate these operations. A production controller would integrate with a cloud provider or orchestrator and reconcile actual resources against the recorded desired state.

## Scaling Policies

### Threshold-based policies

A threshold policy uses explicit boundaries to trigger capacity changes.

The examples use CPU utilization above 75% as a scale-out signal and CPU utilization below 25% as a scale-in signal. Values between these boundaries produce no change.

Separate scale-out and scale-in thresholds create a buffer between opposite decisions. This helps reduce oscillation when a metric moves around a single threshold.

CPU is not always a reliable measure of application demand. A service limited by database connections, network throughput, memory pressure, or an external API may require a different metric.

### Target tracking

Target tracking attempts to maintain a metric near a desired value, such as 60% CPU utilization.

A simplified capacity estimate is:

\[
N_{\text{desired}} =
\left\lceil \frac{D}{C_i U_t} \right\rceil
\]

A real target-tracking controller also considers current capacity, scaling constraints, metric availability, and provider-specific behavior. The example policies use bounded step changes instead of continuously replacing the fleet with the calculated value.

### Evaluation periods

A single high measurement may be caused by a short burst, a delayed metric, or measurement noise. Evaluation periods require multiple observations before acting.

The Python and C++ controllers keep a bounded CPU history. JavaScript uses an event-driven metric window. Java uses a deque to hold the recent measurements. PostgreSQL selects recent observations with ordering and limiting.

The number and duration of evaluation periods determine how quickly the controller responds. Longer windows can reduce unnecessary scaling but may increase the time before capacity expands.

### Cooldowns and warmup

A cooldown limits how frequently a controller performs successive scaling actions. Warmup represents the time required for a new instance to become ready.

These delays serve different purposes:

- **Cooldown** limits repeated decisions.
- **Warmup** delays the contribution of a new instance to serving capacity.

An instance in the pending state increases desired capacity but does not increase available request capacity. Treating pending resources as immediately ready would make the controller underestimate overload risk.

Cooldown implementations vary between cloud providers and policy types. Some systems use instance warmup, estimated capacity contribution, or different rules for scale-in and scale-out rather than a single timer.

## Horizontal and Vertical Scaling Trade-offs

| Concern | Horizontal scaling | Vertical scaling |
|---|---|---|
| Capacity change | Adds or removes instances | Changes instance size |
| Main constraint | Fleet limits and application distribution | Largest supported instance size |
| Availability | Multiple instances can tolerate individual failures | A larger single instance may remain a single point of failure |
| Startup behavior | New instances need initialization and health checks | Resizing may require replacement or restart |
| Cost model | More instances increase aggregate cost | Larger instance types have higher individual costs |
| Application requirements | Shared state and session handling need care | Application must benefit from additional CPU or memory |

Neither approach is universally better. Services can combine both methods by selecting an appropriate instance type and adjusting the fleet size.

## Python Implementation

The Python program centers on the `AutoScalingGroup` class. It maintains instance states, desired capacity, metric history, and a scaling-event log.

### Instance lifecycle

Each `Instance` has an identifier, machine type, health status, and readiness time. Instances created by `scale_out()` enter the pending state when a warmup delay is configured. `advance_time()` promotes healthy instances to ready when their readiness time arrives.

The `ready_instances` property excludes pending and unhealthy resources. The capacity calculation therefore reflects the resources available to serve requests rather than the desired fleet size.

### Policy evaluation

`observe()` validates incoming traffic, estimates CPU utilization, calculates served and rejected requests, and records a `Metrics` object.

`evaluate_policy()` evaluates the bounded CPU history. It waits until enough observations exist, checks the cooldown, and then compares average CPU utilization with the scale-out and scale-in thresholds.

Scale-out and scale-in enforce the configured minimum, maximum, and per-evaluation change limit. The simulator also includes a health-failure operation, a recovery path, a vertical-sizing comparison, and assertions that exercise important boundaries.

### Reporting

The simulation prints a capacity table and the actions recorded by the controller. It writes `autoscaling_report.json`, which contains the policy, machine type, events, and sampled metrics.

The report uses simulated time for scaling decisions and a wall-clock timestamp for report creation. Its estimated resource-hour calculation is illustrative because it samples cost at fixed intervals rather than integrating every infrastructure billing event.

## JavaScript Implementation

The JavaScript file emphasizes event-driven execution and asynchronous metric processing.

### Event-based monitoring

`CapacityPool` extends Node.js `EventEmitter`. It publishes events when instances are created, become ready, are removed, or become unhealthy. The controller also emits a `scaling-action` event when desired capacity changes.

This separates the decision logic from logging and other observers. A production implementation could use the same separation to feed audit records, notifications, or monitoring systems.

### Asynchronous collection

`collectMetrics()` is asynchronous and validates incoming measurements before recording them. Its asynchronous boundary illustrates how metric collection can fit into a controller that performs network operations.

`runLoadTest()` advances simulated time, collects metrics, evaluates policy, and records the resulting action for each traffic sample.

### Capacity reconciliation

The pool bounds every requested capacity change by the minimum, maximum, and per-evaluation limit. Scale-in prefers pending instances so that a reduction does not unnecessarily remove ready capacity.

The example uses in-memory state. A real controller needs persistent desired state, idempotency keys, locking or another concurrency strategy, bounded retries, and provider-side operation tracking. Without these controls, concurrent workers may issue duplicate or conflicting infrastructure operations.

## C++ Case Study

The C++ program models a service handling release-day traffic with a bounded repository of compute instances.

### Architecture and state model

`MachineType` describes resource capacity and hourly cost. `GovernancePolicy` validates the minimum and maximum fleet sizes, scaling steps, timing settings, and utilization thresholds.

`GovernanceEngine` owns the instance inventory, recent CPU samples, metric history, and audit events. The instance state enum distinguishes pending, ready, and unhealthy resources.

This explicit state model prevents the engine from counting an unhealthy or initializing instance as ready capacity.

### Algorithms and failure handling

The controller calculates ready capacity by multiplying the number of ready instances by the capacity of one machine. It then calculates served and rejected request rates.

Policy evaluation uses a bounded vector of recent CPU measurements. Scale-out adds pending instances; scale-in removes pending instances first. Both operations enforce the fleet limits.

The failure-recovery case marks an instance unhealthy, removes failed inventory records, and requests replacement capacity within the configured maximum.

The vector-based implementation is suitable for a small simulation. A high-frequency controller handling a very large inventory would generally benefit from indexed instance lookup and more efficient metric-window structures.

### Capacity and performance considerations

The latency estimate rises as utilization approaches saturation. This is an illustrative queueing-pressure model, not a prediction of production latency percentiles.

Real services should measure latency distributions, queue depth, concurrency, error rates, and dependency performance. Average CPU alone can conceal a severe bottleneck in a database or downstream service.

The C++ example also demonstrates why scale-out decisions should consider warmup delays. A burst that exceeds ready capacity can cause rejected traffic before newly requested instances become available.

## Java Implementation

The Java program uses explicit domain types to separate resource state, policy configuration, metric observations, and scaling decisions.

### Domain model

`MachineType`, `ScalingPolicy`, `Sample`, and `ScalingEvent` are records. Records provide compact immutable data structures for configuration and audit information.

`ComputeInstance` owns its mutable lifecycle state and exposes methods for health failure, recovery, and readiness transitions. This keeps lifecycle changes within the resource model instead of distributing arbitrary state mutations across the service.

### Scaling service

`ScalingService` maintains an inventory, a bounded CPU window, sampled metrics, and an audit history. Its `evaluatePolicy()` method distinguishes insufficient data, cooldown periods, scale-out decisions, scale-in decisions, and stable conditions.

The `DomainEventBus` separates the production of scaling events from their observers. The service uses defensive copies when exposing its metric and audit collections.

The model deliberately keeps provider-specific operations outside the domain layer. A production adapter would translate a scaling decision into provider API calls, record operation identifiers, handle timeouts, and reconcile asynchronous results.

### Failure states

The Java model exposes unhealthy and recovery transitions separately. Recovery moves an instance to pending until its readiness time arrives.

The sample program demonstrates a health failure and requests additional capacity. A production recovery controller must also ensure that failed resources do not consume desired capacity indefinitely and that replacements respect quota, availability-zone distribution, and minimum healthy capacity.

## PostgreSQL Data Model

The SQL implementation represents scaling as a relational workflow rather than as an in-memory controller.

### Infrastructure inventory

`machine_types` stores the CPU, memory, estimated request capacity, and cost of each instance type.

`scaling_groups` stores service identity, environment, and desired capacity limits. Its constraints prevent a group from declaring desired capacity below its minimum or above its maximum.

`compute_instances` represents individual resources, including their state, availability zone, launch time, and readiness time. Its checks ensure terminated instances have a termination timestamp and active instances do not.

### Policies and observations

`scaling_policies` stores metric selection, thresholds, action sizes, cooldown, warmup, evaluation periods, and maximum changes.

`capacity_metrics` stores observations for request rate, CPU, memory, ready and pending counts, capacity, rejected traffic, latency, and estimated cost.

`scaling_actions` records the previous and new desired capacity, requested and applied changes, the policy responsible for the decision, and the reason for the action.

These tables distinguish configuration, observed facts, and decisions. That separation is important for auditing why the controller expanded or reduced capacity.

### Views and queries

`scaling_capacity_summary` aggregates instance inventory by group and reports ready capacity, pending capacity counts, unhealthy instances, and estimated cost.

`scaling_recommendations` ranks recent observations within each enabled policy and calculates a bounded recommendation. It is useful for inspection, but the view does not independently execute infrastructure operations.

The index on `(scaling_group_id, observed_at DESC)` supports recent-metric queries for a particular group. The partial index on active instances avoids indexing terminated resources for queries that focus on current inventory.

### Transactional policy evaluation

`evaluate_scaling_policy()` locks the policy and group records, retrieves recent metric observations, calculates the average, evaluates thresholds, updates desired capacity, and records an action.

The function demonstrates database-level transaction boundaries and row locking. It is not a complete distributed controller. Concurrent provisioning workers need idempotency, provider operation tracking, and a defined retry strategy. The latest metric timestamp is also not a substitute for a durable record of the last successful scaling action.

The database stores desired state and simulation data. Updating `scaling_groups.desired_instances` does not create or terminate a real cloud resource.

## Automated Expansion and Production Readiness

A reliable auto-scaling system must manage more than a threshold and an instance count.

### Startup delays and spare capacity

The time required to detect demand, make a decision, provision a machine, initialize the application, and pass health checks can be longer than a sudden traffic spike.

Predictive scaling, scheduled capacity, queue buffering, load shedding, and reserved headroom can reduce this risk. The appropriate combination depends on how quickly demand changes and how much latency the service can tolerate.

### Scaling signals

A CPU-based policy works best when CPU consumption closely tracks demand. Other services may need request concurrency, queue depth, memory utilization, or a service-specific saturation metric.

A robust policy uses reliable telemetry, bounded evaluation windows, explicit handling of missing data, and thresholds appropriate to the service's behavior.

### Cost and availability

Cost comparisons should include instance pricing, minimum fleet size, data transfer, storage, load balancing, and any provider-specific charges. The examples include only an illustrative instance-hour rate.

Scale-in must account for active connections, in-flight requests, disruption budgets, and failure-domain distribution. Removing capacity solely because CPU is low can cause an outage if the remaining fleet lacks redundancy.

### Security and operational controls

Infrastructure permissions should be limited to the actions the controller requires. Metric ingestion must be authenticated and protected against corrupted or stale measurements. Scaling decisions should produce audit records that identify the policy, observations, previous state, new state, and reason.

Production systems also need alarms for failed provisioning, capacity quotas, missing metrics, repeated scaling oscillation, and situations where demand remains above available capacity despite reaching the configured maximum.

## Common Failure Modes

- **Scale-out too late:** Evaluation windows and startup delays allow demand to exceed capacity before new instances become ready.
- **Excessive scale-in:** Low average utilization hides a traffic burst or removes too much redundancy.
- **Scaling oscillation:** Closely spaced thresholds and noisy metrics trigger repeated opposite actions.
- **False capacity estimates:** The model assumes each instance contributes its full theoretical capacity, even when shared dependencies limit throughput.
- **Stale measurements:** Delayed or missing metrics produce decisions based on an outdated workload.
- **Unbounded retries:** Repeated provisioning requests can create duplicate resources or overload the control plane.
- **Incorrect failure accounting:** Unhealthy instances remain counted as available capacity, or failed resources are never replaced.
- **Cost underestimation:** Pending instances and non-compute charges are omitted from the cost model.

The central design requirement is to keep observed demand, available capacity, desired capacity, policy decisions, and actual infrastructure state distinct. Auto scaling becomes dependable when these states are reconciled through measured feedback, bounded actions, and explicit failure handling.
