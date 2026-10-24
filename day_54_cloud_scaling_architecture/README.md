# Cloud Scaling Architecture

## Scope

This artifact models a distributed cloud application whose compute capacity changes with demand. The architecture separates four responsibilities:

- **Load balancing** distributes incoming requests across healthy compute instances.
- **Auto scaling** changes the number of compute instances according to measured demand and capacity.
- **Distributed compute** provides parallel request-processing capacity across multiple instances.
- **Health management** prevents unhealthy instances from receiving new traffic.

The five implementations use the same domain concepts while taking different engineering approaches.

| Component | Responsibility |
|---|---|
| Client traffic | Produces variable request demand |
| Load balancer | Selects healthy compute targets |
| Compute pool | Provides distributed processing capacity |
| Health checks | Determine whether a target can receive traffic |
| Auto scaler | Compares demand with available capacity |
| Scaling policy | Defines minimum, maximum, and utilization thresholds |
| Cooldown | Prevents rapid oscillation between scaling actions |
| Capacity model | Represents requests per second handled by each instance |
| Monitoring data | Records traffic, capacity, latency, and rejected requests |

## Architecture Model

The logical flow is:

    Clients
       |
       v
    Load Balancer
       |
       +-------------------+
       |         |         |
       v         v         v
    Compute   Compute   Compute
    Node A    Node B    Node C
       |         |         |
       +---------+---------+
                 |
                 v
          Health Evaluation
                 |
                 v
            Auto Scaler
                 |
        +--------+--------+
        |                 |
    Scale Out         Scale In
        |                 |
        v                 v
    Add Capacity      Remove Idle Capacity

The load balancer operates on the current healthy pool. The auto scaler operates on aggregate demand and available capacity. These are separate responsibilities.

## Scaling Fundamentals

A compute instance has a finite request-processing capacity.

If an instance can process 120 requests per second, two healthy instances provide approximately 240 requests per second of modeled capacity. The simulation does not claim that real systems scale perfectly linearly because actual capacity depends on CPU, memory, I/O, network limits, application behavior, and request complexity.

A basic utilization measure is:

`utilization = request_rate / healthy_capacity`

For example, 180 requests per second against 240 requests per second of healthy capacity produces a modeled utilization of `0.75`.

The scaling policy in the implementations uses:

| Policy | Example value |
|---|---:|
| Minimum instances | 2 |
| Maximum instances | 6 |
| Scale-out threshold | 75% |
| Scale-in threshold | 30% |
| Target utilization | 65% |
| Cooldown | 2 simulation ticks or configured time |

The scale-out and scale-in thresholds are intentionally different. This hysteresis reduces repeated scale-out and scale-in decisions when demand fluctuates around a single threshold.

## Load Balancing

The load balancer is responsible for request distribution, not capacity creation.

The implementations maintain a set of healthy targets and allocate requests among targets with remaining capacity.

An unhealthy instance contributes zero routable capacity.

This creates an important separation:

| Concern | Load balancer | Auto scaler |
|---|---|---|
| Detect usable target | Yes | Indirectly |
| Route request | Yes | No |
| Add compute | No | Yes |
| Remove compute | No | Yes |
| Apply request capacity | Yes | Uses it for decisions |
| Enforce health isolation | Yes | No |

A production load balancer can use algorithms such as round robin, weighted routing, least connections, or latency-aware routing. The implementations use a capacity-aware round-robin model so that a target cannot receive requests beyond its modeled capacity.

## Distributed Compute

Distributed compute means request processing is spread across independent execution units.

The compute pool is represented as:

    Instance 01: 120 RPS
    Instance 02: 110 RPS
    Instance 03: 100 RPS
                 |
                 v
       Aggregate healthy capacity

The aggregate capacity is calculated only from healthy instances.

An unhealthy instance can remain part of the infrastructure inventory while contributing no available request capacity.

This distinction matters because infrastructure existence and serving eligibility are different states.

## Instance Lifecycle

Instances move through explicit states:

`starting -> healthy -> draining -> terminated`

A failure can move an instance to:

`healthy -> unhealthy`

Recovery can move it back:

`unhealthy -> healthy`

The implementations use a simplified activation model in which starting instances become healthy during the simulation. A production platform would normally include image provisioning, application startup, readiness checks, registration with the load balancer, and graceful connection draining.

The lifecycle state prevents a terminated or unhealthy instance from accidentally becoming a routing target.

## Auto Scaling

Auto scaling evaluates the relationship between incoming demand and currently available capacity.

The decision model is:

    Demand
      |
      v
    Compare with healthy capacity
      |
      +---- utilization > scale-out threshold ----> Scale Out
      |
      +---- utilization < scale-in threshold ------> Scale In
      |
      +---- otherwise ------------------------------> Hold

The implementations enforce minimum and maximum capacity.

This prevents two important failures:

- Scaling out without an upper bound can create uncontrolled infrastructure growth.
- Scaling in below the minimum capacity can remove the redundancy required for normal service operation.

## Cooldown Behavior

A scaling cooldown temporarily suppresses additional scaling decisions after a change.

Without cooldown behavior, a rapidly changing workload could produce:

    Scale Out
       |
    Scale In
       |
    Scale Out
       |
    Scale In

This oscillation creates unnecessary infrastructure churn.

The examples therefore record a cooldown period after scaling decisions. The Python, JavaScript, and Java implementations represent cooldown in memory. The PostgreSQL model records scaling events so that an external control plane can persist and analyze those decisions.

A production implementation would normally combine cooldowns with multiple signals, stabilization windows, predictive capacity planning, and minimum healthy capacity.

## Python Implementation

The Python program models the architecture as an executable simulation.

### Domain types

`InstanceState` represents compute lifecycle and health states.

`ScalingAction` represents `scale_out`, `scale_in`, and `hold`.

`Instance` stores:

- instance identity
- request capacity
- lifecycle state
- active requests
- failure information

`ScalingPolicy` is a dataclass containing scaling limits and thresholds.

### Load balancing

`LoadBalancer.distribute()` identifies healthy instances and assigns traffic using capacity-aware round robin.

The method returns:

- allocation by instance
- served requests
- implicitly rejected requests when total capacity is insufficient

The implementation refuses to route requests when no healthy instance exists.

### Auto scaling

`AutoScaler.evaluate()` compares request rate with total healthy capacity.

The result is one of three actions:

- `SCALE_OUT`
- `SCALE_IN`
- `HOLD`

The cooldown counter prevents immediate repeated scaling decisions.

### Failure simulation

The simulation deliberately marks an instance unhealthy during the traffic sequence.

The load balancer then excludes that instance.

The architecture subsequently restores the instance to healthy state, demonstrating that failure handling and scaling are separate mechanisms.

### Validation

The Python program validates:

- scaling threshold ordering
- minimum and maximum instance limits
- target utilization
- negative traffic
- unknown instance identifiers
- absence of healthy targets

Assertions verify normal request processing and health isolation.

## JavaScript Implementation

The JavaScript implementation uses an event-oriented Node.js-compatible design.

### JavaScript-specific model

`Map` is used for per-instance routing allocation.

`Promise` and `async` behavior are used in the simulation loop to model asynchronous infrastructure activity.

Classes isolate:

- instances
- load balancing
- auto scaling
- architecture orchestration

The program uses immutable frozen objects for the state enumerations.

### Event-oriented processing

`runEventDrivenSimulation()` processes changing traffic asynchronously.

The short asynchronous delay represents the fact that real infrastructure operations are not instantaneous. Real cloud systems would have substantially longer provisioning and readiness intervals.

### Error handling

`ValidationError` distinguishes invalid input from operational failures.

The architecture handles a load-balancer failure by returning rejected traffic when no healthy target is available.

This makes failure observable rather than silently discarding the condition.

## C++17 Implementation

The C++ implementation treats the system as a governance and capacity engine.

### Data structures

The program uses:

- `struct` for compact domain records
- `enum class` for strongly typed states
- `std::vector` for the compute pool
- `std::map` for deterministic request allocations
- STL algorithms for filtering and counting
- exceptions for invalid state and input

`Instance` owns its capacity and active request state.

`LoadBalancer` operates on references to instances rather than copying the compute pool.

### Capacity routing

The load balancer repeatedly distributes traffic while available target capacity remains.

If every healthy target reaches capacity, the remaining requests become rejected.

This explicitly models overload instead of allowing request demand to exceed the declared infrastructure capacity.

### Scaling engine

`AutoScaler` owns policy evaluation and cooldown state.

`GovernanceEngine` owns the compute pool and applies the scaling decision.

This separation allows the scaling policy to remain independent from the mechanics of instance creation and termination.

### Failure handling

An unhealthy instance is retained in the infrastructure collection but excluded from capacity calculations.

This represents a common production distinction:

`registered resource != serving resource`

The C++ implementation also validates unknown instance identifiers and negative traffic.

## Java 17 Implementation

The Java implementation uses explicit enterprise-style domain modeling.

### Records

`ScalingPolicy`, `RoutingResult`, and `ScalingDecision` are Java records.

Records provide compact immutable data structures for policy and decision results.

### Service boundaries

The implementation separates:

- `AutoScalingService`
- `RequestRouter`
- `ComputeService`
- `RepositoryStylePolicy`

The service structure makes the responsibilities explicit rather than placing all behavior in a single class.

### State transitions

`Instance` exposes controlled state changes through methods instead of allowing arbitrary public mutation.

`ComputeService` determines when instances can be created or terminated.

The scaling service determines what action should be considered.

The routing service determines where requests can be placed.

### Stream-based queries

Java streams are used for operations such as:

- finding healthy instances
- counting active instances
- calculating healthy capacity
- selecting removable instances

The implementation still uses explicit loops where mutation and capacity allocation make a loop easier to reason about.

### Enterprise policy separation

`RepositoryStylePolicy` demonstrates a governance boundary around scale-in and scale-out limits.

Although the example is intentionally compact, the same boundary can hold additional enterprise rules such as:

- regional capacity requirements
- maintenance windows
- reserved capacity limits
- deployment freeze periods
- availability-zone constraints
- cost controls

## PostgreSQL Implementation

The PostgreSQL script models the infrastructure as relational operational data.

### Core tables

The main entities are:

| Table | Purpose |
|---|---|
| `repositories` | Logical applications using the infrastructure |
| `compute_instances` | Distributed compute resources |
| `load_balancers` | Request distribution configuration |
| `scaling_policies` | Scaling thresholds and capacity limits |
| `status_checks` | Operational readiness signals |
| `scaling_events` | Persistent scaling decisions |
| `requests` | Request-level processing results |
| `traffic_samples` | Historical traffic and capacity measurements |

The relational model allows infrastructure state to be queried independently of application execution.

### Constraints

The database enforces important rules using:

- primary keys
- foreign keys
- unique constraints
- check constraints
- enumerated state types
- triggers

For example, an instance cannot have more active requests than its declared capacity while it is healthy.

The policy table prevents a scale-in threshold from being equal to or above the scale-out threshold.

### Indexing

The partial index on healthy compute instances focuses on the operational query that selects routing targets.

The request indexes support queries by repository, time, and compute instance.

The indexes are intentionally narrow rather than indexing every column.

### Stored scaling evaluation

`evaluate_scaling()` calculates:

- current healthy capacity
- current healthy instance count
- utilization
- scaling action
- desired instance count

The function does not create infrastructure itself.

That separation is deliberate. A relational database can determine desired state, while a control plane or orchestration system can reconcile that desired state with actual infrastructure.

### Views

`repository_capacity` provides an operational capacity view.

`request_health_report` aggregates:

- total requests
- completed requests
- rejected requests
- average latency

These views separate reporting logic from application queries.

### Transactional scaling event

The transaction locks the applicable scaling policy before recording a scaling event.

This demonstrates a basic concurrency-control pattern:

    Begin transaction
          |
          v
    Lock scaling policy
          |
          v
    Evaluate current capacity
          |
          v
    Record scaling decision
          |
          v
        Commit

A production control plane would normally use stronger reconciliation logic around infrastructure APIs, idempotency keys, leases, and distributed coordination.

## Failure Scenarios

The artifacts deliberately cover several failure modes.

| Failure | Expected behavior |
|---|---|
| Negative request rate | Validation failure |
| No healthy instances | Requests are rejected |
| Unhealthy compute node | Node removed from routing |
| Traffic above capacity | Excess requests rejected |
| Scaling beyond maximum | Maximum limit enforced |
| Scaling below minimum | Minimum limit enforced |
| Invalid thresholds | Policy validation failure |
| Terminated instance | Cannot act as a serving target |
| Rapid traffic changes | Cooldown reduces scaling oscillation |

These failures represent different layers. Input validation, health management, capacity exhaustion, and scaling policy enforcement should not be collapsed into one mechanism.

## Security Considerations

A real cloud scaling system must protect both the data plane and the control plane.

Important controls include:

- authenticate infrastructure-management requests
- authorize scaling operations by role
- protect load-balancer configuration
- restrict instance-management APIs
- encrypt traffic between clients and load balancers
- use encrypted transport between services where appropriate
- avoid storing credentials in application source code
- use short-lived credentials for infrastructure APIs
- audit scaling actions
- protect monitoring and operational data
- validate externally supplied traffic and configuration values
- restrict administrative bypass operations
- prevent unauthorized modification of minimum and maximum capacity

The PostgreSQL design also uses foreign keys and database constraints to prevent invalid infrastructure relationships.

## Performance Considerations

The in-memory routing implementations scan healthy instances and distribute requests across them.

For `n` healthy instances, one routing pass is approximately `O(n)` and repeated capacity exhaustion can require multiple passes. For typical small or moderate target pools this is straightforward.

The database capacity calculation uses indexed and filtered access patterns. The partial healthy-target index is useful because routing and health analysis generally care about serving instances rather than terminated resources.

At large scale, production systems would normally avoid using a relational database as the hot-path request router. The database is more appropriate for configuration, policy, state persistence, reporting, and control-plane coordination.

## Availability and Scaling Trade-offs

Adding instances improves horizontal capacity, but scaling is not free.

| Decision | Benefit | Cost or risk |
|---|---|---|
| More instances | Higher throughput | Higher infrastructure cost |
| Larger instances | Higher per-node capacity | Larger failure impact |
| Higher scale-out threshold | Fewer scaling events | Greater overload risk |
| Lower scale-out threshold | More capacity headroom | Higher cost |
| Lower minimum | Lower idle cost | Less redundancy |
| Higher minimum | Better failure tolerance | Higher baseline cost |
| Longer cooldown | Less oscillation | Slower reaction |
| Shorter cooldown | Faster response | More scaling churn |

A sound architecture chooses these values from workload behavior rather than treating them as universal constants.

## Health Checks and Readiness

A health check should answer whether an instance is safe to receive traffic, not merely whether its operating system responds.

A realistic readiness sequence can be:

    Instance starts
         |
         v
    Process running
         |
         v
    Dependencies reachable
         |
         v
    Application ready
         |
         v
    Health check passes
         |
         v
    Register with load balancer

A failed readiness check should prevent traffic from reaching the instance.

For termination:

    Stop new traffic
         |
         v
    Drain existing requests
         |
         v
    Confirm idle
         |
         v
    Terminate

The simplified simulations use immediate lifecycle transitions where a production system would need asynchronous draining.

## Statelessness and Distributed Sessions

Horizontal scaling works most naturally when application instances are stateless.

A stateless service can send consecutive requests from the same client to different instances:

    Request 1 -> Instance A
    Request 2 -> Instance C
    Request 3 -> Instance B

Persistent application state should normally live in shared systems such as databases, caches, object storage, or dedicated state services rather than local instance memory.

If local session state is unavoidable, session affinity can reduce routing flexibility but introduces additional failure and rebalancing concerns.

## Multi-Region Scaling

The examples include region fields because distributed systems often require more than one failure domain.

A multi-region architecture can be represented as:

    Global Traffic Layer
       |
       +--------------------+
       |                    |
       v                    v
    Region A             Region B
       |                    |
    LB + Pool            LB + Pool
       |                    |
    Compute Nodes        Compute Nodes

Regional routing can consider:

- latency
- regional health
- capacity
- regulatory requirements
- data residency
- cost
- disaster-recovery objectives

Global routing and regional load balancing remain separate control layers.

## Database Versus Control Plane

The PostgreSQL implementation intentionally models desired infrastructure state without pretending that SQL itself is the compute orchestration system.

A practical control-plane workflow is:

    Metrics
       |
       v
    Policy Evaluation
       |
       v
    Desired Capacity
       |
       v
    Infrastructure API
       |
       v
    Instance Provisioning
       |
       v
    Health Checks
       |
       v
    Load Balancer Registration

The database can persist the observed and desired state. A reconciliation service can compare desired state with actual infrastructure and make idempotent changes.

## Practical Architecture Boundaries

The complete design can be divided into four major planes:

| Plane | Main responsibility |
|---|---|
| Data plane | Process and route application requests |
| Health plane | Determine which resources can serve |
| Control plane | Evaluate scaling policy and reconcile capacity |
| Observability plane | Record metrics, events, failures, and latency |

Keeping these boundaries clear prevents a common architectural mistake: putting routing, scaling, monitoring, and infrastructure provisioning into one tightly coupled component.

## Implementation Comparison

| Language | Primary perspective | Key mechanism |
|---|---|---|
| Python | Simulation and experimentation | Dataclasses, enums, assertions |
| JavaScript | Event-driven model | Maps, classes, async processing |
| C++17 | Capacity and governance engine | STL, strong enums, explicit ownership |
| Java 17 | Enterprise domain model | Records, services, streams, policies |
| PostgreSQL | Persistent control-plane model | Constraints, triggers, functions, views, transactions |

Each implementation represents the same infrastructure concepts without requiring identical source structure.

The common architectural relationship is:

`traffic -> load balancing -> distributed compute -> health observation -> scaling decision -> capacity change`

The important distinction is that request routing consumes current capacity, while auto scaling changes future capacity. Health state determines which capacity is usable, and policy determines when capacity should change.
