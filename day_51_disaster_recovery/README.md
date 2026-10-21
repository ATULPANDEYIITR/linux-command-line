# Disaster Recovery: RPO, RTO, Backup Recovery, Pilot Light, Warm Standby, and Multi-Region Recovery

## Scope

This project models disaster recovery as an operational decision system rather than as a collection of backup commands.

The central relationship is:

`Business Service -> Recovery Objective -> Recovery Tier -> Recovery Assets -> Health Validation -> Failover Decision`

The implementation distinguishes two independent recovery objectives:

| Objective | Meaning | Operational question |
|---|---|---|
| RPO | Recovery Point Objective | How much recent data can be lost? |
| RTO | Recovery Time Objective | How long can the service remain unavailable? |

RPO is expressed as a maximum acceptable data age. RTO is expressed as a maximum acceptable recovery duration.

A backup that is three hours old can be perfectly valid as a backup while still violating a five-minute RPO. Likewise, a service can have a current backup but fail a five-minute RTO if restoring and validating that backup takes an hour.

## Recovery tiers

The project models four recovery approaches.

| Tier | Primary mechanism | Typical recovery speed | Main trade-off |
|---|---|---:|---|
| Backup restore | Rebuild from stored backup | Slowest | Lowest operating cost, highest recovery time |
| Pilot light | Keep essential infrastructure and configuration ready | Faster | Application capacity still needs expansion |
| Warm standby | Keep a functioning secondary environment with reduced capacity | Fast | Higher operating cost |
| Multi-region | Operate service across multiple active regions | Fastest | Highest architectural and operational complexity |

The numerical recovery durations used by the simulations are policy estimates rather than universal industry values:

- Backup restore: 90 minutes
- Pilot light: 30 minutes
- Warm standby: 10 minutes
- Multi-region: 2 minutes

A real organization would derive these values from measured recovery exercises.

## Relationship between recovery mechanisms

Backup and replication solve different problems.

A backup provides a recoverable historical state. Replication reduces the time needed to obtain a current state but does not automatically replace backups. Replication can copy corruption, accidental deletion, or application-level errors into another environment.

A recovery architecture therefore commonly combines:

`Production Data -> Replication -> Secondary Environment`

and

`Production Data -> Verified Backup -> Independent Storage`

The secondary environment handles rapid availability. The backup provides an independent recovery point.

## Python implementation

The Python program provides a repository-independent recovery simulation using explicit domain classes.

`RecoveryObjective` validates RPO and RTO values. `Backup` records creation time, storage location, size, and a SHA-256 checksum. `Service` owns recovery objectives, recovery tier, data, backup history, and configured recovery regions.

`RecoveryManager` coordinates:

- region registration
- service registration
- data writes
- backup creation
- backup-age calculation
- regional failure
- failover evaluation
- recovery audit

The `recover()` method does not treat the existence of a secondary region as sufficient. It checks the recovery tier, configured target, target availability, backup availability, RPO, and RTO.

The audit mechanism separately identifies operational weaknesses such as stale backups and insufficient available regions.

The script also demonstrates expected failure conditions:

- attempting recovery without a backup
- using a stale backup
- recovering into an unavailable region
- configuring multi-region service without enough available regions

The backup checksum demonstrates an integrity-control mechanism. In production, checksum validation would be combined with encryption, immutable retention, access control, monitoring, and restore testing.

## JavaScript implementation

The JavaScript implementation uses an event-driven design.

`RecoveryController` extends Node.js `EventEmitter`. Region failures and successful failovers produce events rather than requiring every component to poll the controller synchronously.

The service model stores recovery data in a `Map`, while `Backup` uses Node's standard `crypto` module to calculate a SHA-256 representation of the backup payload.

The asynchronous `waitForHealthCheck()` function represents the type of external health signal that a real recovery orchestrator would consume. The example deliberately keeps the delay deterministic so that the program remains self-contained.

The JavaScript policy evaluator separates:

- target configuration
- target availability
- primary failure
- backup availability
- RPO compliance
- RTO compliance
- recovery-tier support

This prevents a configured secondary region from being treated as automatically usable.

The program also demonstrates capacity failure. A region can be configured as a recovery target while still being unsuitable because its capacity is zero.

## C++ implementation

The C++ program treats disaster recovery as a governance engine.

`PullRequestRecoveryRecord` is deliberately named to emphasize that recovery execution can be subject to controlled operational approval and validation workflows. The engine evaluates:

- failed primary region
- target-region availability
- configured recovery region
- verified backup availability
- RPO
- RTO
- status checks
- eligible approvals

The recovery decision is represented by `Evaluation`. Its `eligible()` method requires every mandatory condition to pass.

This creates a fail-closed recovery policy:

`Any mandatory condition fails -> Recovery rejected`

rather than:

`Some conditions pass -> Attempt recovery anyway`

The program uses C++17 containers such as `std::map`, `std::set`, and `std::vector`. It uses `std::optional`-compatible domain design and exceptions for invalid configuration and failed policy evaluation.

The implementation also demonstrates why a recovery target cannot be selected solely from configuration. A configured region with failed capacity is still unavailable.

## Java implementation

The Java implementation uses explicit enterprise-style domain types.

The main domain objects are:

- `RecoveryObjective`
- `Region`
- `RecoveryService`
- `Backup`
- `StatusCheck`
- `Approval`
- `RecoveryPolicy`
- `RecoveryEvaluation`
- `RecoveryServiceManager`

Enums represent bounded operational states such as recovery tier, region state, and service state.

Java records are used for immutable value objects such as `RecoveryObjective`, `StatusCheck`, `Backup`, `Approval`, and `RecoveryEvaluation`.

The service lifecycle is explicit:

`HEALTHY -> RECOVERING -> RECOVERED`

The region lifecycle is separate:

`PRIMARY -> FAILED`

and:

`SECONDARY -> PRIMARY`

This separation is important because service state and infrastructure-region state describe different things.

`RecoveryPolicy` owns recovery-time estimates and approval requirements. `RecoveryServiceManager` performs the state transition only after policy evaluation succeeds.

The Java example also treats reviewer eligibility and approval state separately. An approval from an ineligible reviewer cannot satisfy the recovery approval requirement.

## PostgreSQL implementation

The PostgreSQL model represents disaster recovery as relational operational data.

Core entities include:

| Table | Purpose |
|---|---|
| `repositories` | Owning engineering repositories and teams |
| `regions` | Region state and capacity |
| `services` | Recovery objectives and recovery tier |
| `service_regions` | Configured recovery locations |
| `backups` | Backup lifecycle, verification, checksum, and storage region |
| `review_policies` | Required approval and review controls |
| `reviewers` | Eligible operational reviewers |
| `service_approvals` | Recovery approval decisions |
| `status_checks` | Automated recovery readiness checks |
| `recovery_events` | Historical failover operations |

The database enforces important invariants with primary keys, foreign keys, uniqueness constraints, check constraints, and enumerated types.

For example:

- RPO cannot be negative.
- RTO must be positive.
- Region capacity must remain between 0 and 100.
- A completed backup requires verification.
- A service must reference an existing primary region.
- A service cannot use an unknown recovery region.

### Recovery evaluation query

`evaluate_recovery()` centralizes the database-side recovery decision.

It checks:

`Primary failed`

AND

`Target available`

AND

`Target configured`

AND

`Verified backup exists`

AND

`Backup age <= RPO`

AND

`Estimated recovery time <= RTO`

AND

`Required approvals exist`

AND

`All status checks pass`

Only when all conditions are satisfied is `recovery_eligible` true.

This allows reporting and operational automation to use the same database policy rather than independently reconstructing recovery rules in application code.

### Transactional failover

`execute_recovery()` performs the state transition inside a transaction.

The primary region is locked through the service row, the complete recovery policy is evaluated, and only then are the service and region states changed.

The intended state transition is:

`Primary Region: PRIMARY -> FAILED`

`Recovery Region: SECONDARY -> PRIMARY`

`Service: HEALTHY -> RECOVERING -> RECOVERED`

The recovery event is recorded after the transition.

A production implementation would normally combine this transactional model with distributed coordination, infrastructure orchestration, health verification, idempotency controls, audit logging, and external incident management.

## Backup recovery

Backup recovery is the most dependent on stored recovery artifacts.

A typical sequence is:

`Failure`
→ `Identify latest verified backup`
→ `Provision recovery environment`
→ `Restore backup`
→ `Validate integrity`
→ `Run application checks`
→ `Rebuild dependent services`
→ `Route traffic`
→ `Validate service`

The key limitation is that backup age and restore duration directly affect RPO and RTO.

The project therefore refuses recovery when the latest verified backup is outside the declared RPO.

A backup should not be considered recoverable merely because a backup row exists. Verification status is part of the recovery decision.

## Pilot light

A pilot-light architecture keeps the minimum infrastructure required to accelerate recovery.

Typical retained components may include:

- network configuration
- infrastructure definitions
- identity configuration
- database replication or essential data synchronization
- container or virtual-machine images
- deployment configuration
- monitoring configuration

Application capacity is normally expanded during an incident.

The advantage is lower cost than maintaining a full secondary production environment. The disadvantage is that scaling and validation still occur during recovery.

## Warm standby

Warm standby keeps a secondary environment partially or substantially operational.

The secondary environment may have:

- synchronized data
- running application instances
- preconfigured networking
- deployed application versions
- monitoring
- reduced compute capacity

Failover therefore involves less provisioning than backup restore or pilot light.

The Python and Java examples use warm standby for a service with a five-minute RPO and fifteen-minute RTO. The modeled ten-minute recovery estimate is acceptable against that RTO.

## Multi-region recovery

Multi-region recovery distributes service capability across independent geographic regions.

The strongest form of the model requires:

- more than one configured region
- more than one available region
- current data synchronization
- healthy traffic routing
- automated health detection
- tested failover
- independent operational access

The project intentionally does not assume that a second region guarantees recovery. A configured region with zero capacity or a failed state cannot satisfy the recovery target.

Multi-region architectures also introduce additional failure modes:

- cross-region replication lag
- split-brain behavior
- inconsistent writes
- DNS or routing failures
- regional dependency failures
- credential or control-plane outages
- correlated infrastructure failures

## RPO versus backup frequency

If a service requires a five-minute RPO, a backup schedule that runs every hour cannot guarantee the requirement.

The distinction is:

`Backup frequency -> potential recovery-point age`

`RPO -> maximum acceptable recovery-point age`

If backup creation occurs every five minutes but verification takes ten minutes, the effective recovery process may still fail a five-minute RPO depending on when the verified backup becomes usable.

Replication can reduce recovery-point lag, but replication itself must be monitored and tested.

## RTO versus recovery tier

RTO should influence architecture selection.

A service with a four-hour RTO may reasonably use backup restore if restore tests consistently complete within that window.

A service with a five-minute RTO generally requires a much more prepared environment.

A simplified relationship is:

| Requirement | Plausible architecture |
|---|---|
| Hours of downtime acceptable | Backup restore |
| Tens of minutes | Pilot light |
| Minutes | Warm standby |
| Very low interruption | Multi-region |

These are architectural tendencies rather than universal thresholds.

## Failure conditions modeled by the project

The implementations intentionally reject recovery under invalid conditions.

### Stale recovery point

The latest verified backup is older than the declared RPO.

Result:

`RPO condition = false`

### Excessive recovery duration

The selected recovery tier has an estimated recovery duration greater than the service RTO.

Result:

`RTO condition = false`

### Unavailable target

The configured secondary region is failed or has no capacity.

Result:

`target_available = false`

### Missing backup

Backup-restore recovery cannot proceed without a usable backup.

Result:

`backup_available = false`

### Failed status check

A failed integrity, replication, or security validation blocks recovery.

Result:

`status_checks_met = false`

### Insufficient approvals

A recovery policy can require independent operational approval before failover.

Only active, eligible, non-stale, non-dismissed approvals count.

Result:

`approvals_met = false`

## Security considerations

Disaster recovery expands the security boundary because recovery infrastructure, backup storage, replication channels, and emergency credentials all become critical assets.

Important controls include:

- encryption at rest for backup storage
- encryption in transit for replication
- separate backup credentials
- least-privilege recovery roles
- immutable or protected backup retention
- independent administrative access
- audit logging
- restore integrity validation
- credential rotation
- monitoring of recovery-region access
- protection against unauthorized failover

Recovery credentials should not depend exclusively on infrastructure that may be unavailable during the disaster.

Backups should also be protected against destructive access by the same identity that controls production systems.

## Performance and operational trade-offs

Recovery architecture involves cost, latency, and complexity.

| Architecture | Cost | Recovery speed | Operational complexity |
|---|---|---|---|
| Backup restore | Lower | Lower | Moderate |
| Pilot light | Moderate | Moderate | High |
| Warm standby | Higher | High | High |
| Multi-region | Highest | Very high | Very high |

The cheapest architecture is not automatically appropriate. The correct design is determined by the business impact of downtime and data loss.

A service with low transaction volume and relaxed RTO/RPO may not justify multi-region operation.

A payment system with strict availability and data-loss requirements may justify the additional infrastructure and operational complexity.

## Recovery testing

A disaster recovery plan is incomplete until recovery has been tested.

Useful tests include:

- restore a known backup into an isolated environment
- measure actual restore duration
- calculate actual recovery-point age
- simulate primary-region failure
- validate secondary-region capacity
- verify traffic switching
- test dependency recovery
- verify monitoring after failover
- test return-to-primary procedures
- record actual RPO and RTO measurements

The measured values should replace assumptions in recovery policies.

A useful operational loop is:

`Plan -> Test -> Measure -> Correct -> Test Again`

## Architecture boundary

The project models the decision and governance layer. It does not attempt to control a real cloud provider.

A production recovery platform would connect these policy decisions to infrastructure automation, traffic management, databases, object storage, monitoring systems, secrets management, incident management, and audit systems.

The key architectural separation remains:

`Recovery Objective`
determines what must be achieved.

`Recovery Tier`
describes the preparedness required to achieve it.

`Backup / Replication`
provides recoverable data.

`Health Checks`
determine whether recovery components are usable.

`Policy Evaluation`
determines whether recovery conditions are satisfied.

`Failover`
changes service routing and operational state.
