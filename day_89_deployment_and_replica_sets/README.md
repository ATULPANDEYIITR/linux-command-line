# Kubernetes Deployments and ReplicaSets

## 1. Deployment and ReplicaSet Architecture

Kubernetes Deployments provide declarative management of stateless application workloads. They maintain the desired state of an application and coordinate changes to the underlying ReplicaSets.

A Deployment does not directly manage individual application Pods. It manages ReplicaSets, which manage Pods.

The resource relationship is:

Deployment
  |
  +-- ReplicaSet: Revision 1
  |      |
  |      +-- Pod 1
  |      +-- Pod 2
  |      +-- Pod 3
  |
  +-- ReplicaSet: Revision 2
         |
         +-- Pod 4
         +-- Pod 5
         +-- Pod 6

The Deployment controller manages ReplicaSets. The ReplicaSet controller ensures that the appropriate number of Pods exist. Other Kubernetes control-plane components handle scheduling, node placement, and workload execution.

The implementations in this repository simulate the resource relationships, reconciliation process, scaling, rolling updates, readiness, revision history, and rollback operations.

## 2. Declarative Deployment Model

A declarative configuration describes the required application state rather than providing a sequence of individual Pod creation commands.

A Deployment specification typically defines:

| Field | Purpose |
|---|---|
| `replicas` | Desired number of application Pods |
| `selector` | Identifies Pods belonging to the Deployment |
| `template` | Defines the Pod specification |
| `strategy` | Determines how application versions are replaced |
| `minReadySeconds` | Minimum readiness duration before a Pod is considered available |
| `revisionHistoryLimit` | Number of old ReplicaSet revisions retained |
| `progressDeadlineSeconds` | Maximum time allowed for rollout progress |

A representative configuration has the following structure:

- Deployment name: `orders-api`
- Namespace: `production`
- Desired replicas: 3
- Container image: `orders-api:1.0.0`
- Container port: 8080
- Update strategy: RollingUpdate
- Maximum surge: 1
- Maximum unavailable: 0

The desired replica count is not necessarily the number of Pods currently running. It is the target against which the controllers continuously evaluate observed state.

### Desired state and observed state

These concepts must remain distinct.

| Desired state | Observed state |
|---|---|
| Three replicas requested | Two Pods currently running |
| Image version 2.0 requested | Some Pods still use version 1.0 |
| All Pods should become available | One Pod has failed readiness |
| Deployment should use a particular specification | Controllers have not yet completed reconciliation |

The reconciliation process attempts to reduce the difference between desired and observed state.

## 3. ReplicaSets

A ReplicaSet maintains a stable number of matching Pods.

Its main responsibilities are:

- Identify Pods through label selectors.
- Maintain the configured replica count.
- Create replacement Pods when existing Pods disappear.
- Remove excess Pods when the desired count decreases.
- Maintain the relationship between a workload controller and its Pods.

A ReplicaSet does not independently implement application-version rollout policies. Deployment controllers coordinate multiple ReplicaSets to perform controlled application updates.

### ReplicaSet lifecycle

A typical lifecycle is:

1. The Deployment creates a ReplicaSet.
2. The ReplicaSet creates the required Pods.
3. The Pods are scheduled and started.
4. Readiness probes determine whether the application can receive traffic.
5. The ReplicaSet maintains the desired number of matching Pods.
6. During an update, the Deployment creates another ReplicaSet.
7. The previous ReplicaSet is gradually scaled down.
8. Old ReplicaSets may remain available for rollback.

### Desired and ready replicas

The following quantities represent different states:

| Quantity | Meaning |
|---|---|
| Desired replicas | Number specified by the Deployment |
| Current replicas | Existing non-terminated Pods |
| Ready replicas | Running Pods passing readiness |
| Available replicas | Ready Pods satisfying the availability duration |
| Updated replicas | Pods using the current Deployment Pod template |

For example:

| Metric | Value |
|---|---:|
| Desired | 3 |
| Current | 3 |
| Ready | 2 |
| Available | 2 |
| Updated | 3 |

This Deployment has three current Pods, but only two are ready and available.

A matching replica count does not establish application health.

## 4. Reconciliation and Controllers

Kubernetes controllers use reconciliation rather than relying exclusively on individual commands.

A reconciliation loop follows this conceptual process:

Observe current state
    |
Read desired specification
    |
Calculate differences
    |
Create or remove resources
    |
Update status
    |
Repeat

For a Deployment requesting three replicas:

- If two Pods exist, the ReplicaSet controller creates another.
- If four Pods exist, it removes an excess Pod.
- If a Pod fails, the ReplicaSet controller attempts to replace it.
- If the Deployment template changes, the Deployment controller creates or updates ReplicaSets.

Reconciliation is continuous. A single controller operation does not guarantee that every resource immediately reaches its target state.

The Python, JavaScript, C++, and Java programs implement explicit reconciliation operations. The PostgreSQL implementation uses a stored procedure to compare desired and observed replica counts.

### Idempotency

An idempotent reconciliation operation can execute repeatedly without introducing unnecessary resources once the target state has been reached.

For example, reconciling a Deployment that already has three active Pods should not create a fourth Pod.

This property is important because Kubernetes controllers repeatedly process resource changes and may retry operations after failures.

## 5. Rolling Updates

A rolling update replaces application versions gradually rather than terminating every existing Pod simultaneously.

Suppose an application currently runs:

- Three Pods using `orders-api:1.0.0`.
- Three desired replicas.
- One maximum additional Pod.
- Zero maximum unavailable replicas.

The target version is `orders-api:2.0.0`.

A simplified rollout proceeds as follows:

| Stage | Old version | New version | Total |
|---|---:|---:|---:|
| Initial | 3 | 0 | 3 |
| New Pod created | 3 | 1 | 4 |
| New Pod becomes ready | 3 | 1 | 4 |
| Old Pod terminated | 2 | 1 | 3 |
| Second replacement | 2 | 2 | 4 |
| Second replacement ready | 2 | 2 | 4 |
| Second old Pod terminated | 1 | 2 | 3 |
| Final replacement ready | 1 | 3 | 4 |
| Last old Pod terminated | 0 | 3 | 3 |

The actual Kubernetes rollout is asynchronous and may perform multiple controller operations between observations.

### Rolling update parameters

| Parameter | Function |
|---|---|
| `maxSurge` | Maximum additional Pods permitted above the desired replica count |
| `maxUnavailable` | Maximum number of unavailable replicas permitted during an update |

These parameters can be specified as integers or percentages in Kubernetes.

For three desired replicas:

- `maxSurge: 1` permits up to four Pods.
- `maxUnavailable: 0` requires the desired availability level to be maintained during replacement.

A rollout must account for readiness, scheduling capacity, resource availability, and application startup time.

### Important distinctions

Creating a new Pod does not mean that it is ready.

A running Pod does not necessarily mean that it is available.

A Deployment can temporarily have more Pods than its desired replica count because of the surge allowance.

A rollout may pause when the new application version cannot become ready.

The C++ and Java implementations model the rollout as bounded operations. The Python and JavaScript implementations also expose individual rollout steps.

## 6. Readiness and Availability

Readiness determines whether a Pod is suitable for receiving application traffic.

A readiness probe can evaluate:

- HTTP endpoint responses.
- TCP connection availability.
- An executable health-check command.

A failed readiness probe removes the Pod from normal Service traffic without necessarily terminating its container.

Readiness and liveness serve different purposes:

| Mechanism | Purpose |
|---|---|
| Readiness probe | Determines whether the application can receive traffic |
| Liveness probe | Determines whether the container should be restarted |
| Startup probe | Determines whether the application has completed startup |

`minReadySeconds` defines the minimum period for which a Pod must remain ready before it counts as available for Deployment progress.

This prevents a newly ready Pod from immediately being treated as a stable replacement.

The simulations represent readiness through explicit state transitions. They do not implement real HTTP, TCP, or executable probes.

## 7. Deployment Strategies

Kubernetes supports two principal Deployment update strategies.

### RollingUpdate

RollingUpdate gradually replaces existing Pods.

Characteristics:

- Supports controlled replacement.
- Uses `maxSurge` and `maxUnavailable`.
- Allows old and new application versions to coexist temporarily.
- Maintains availability according to the configured rollout policy.

This strategy is appropriate when the application can tolerate temporary coexistence of different versions.

### Recreate

Recreate terminates existing Pods before creating replacement Pods.

Characteristics:

- Avoids simultaneous operation of old and new versions.
- May cause application downtime.
- Does not provide the same gradual replacement behavior as RollingUpdate.

It can be appropriate when different application versions cannot safely run simultaneously.

The PostgreSQL schema records both strategies, while the rollout simulation concentrates on RollingUpdate.

## 8. Deployment Revisions

A Deployment revision represents a version of its Pod template.

A new revision is generally created when the Pod template changes.

Examples include:

- Changing the container image.
- Changing container commands.
- Modifying environment variables.
- Updating Pod resource requests.
- Changing volumes or other Pod template settings.

Changing only the replica count does not normally create a new Deployment revision.

The implementations use revision numbers and image identifiers to demonstrate historical states.

A simplified history is:

| Revision | Image |
|---|---|
| 1 | `orders-api:1.0.0` |
| 2 | `orders-api:2.0.0` |
| 3 | `orders-api:3.0.0` |
| 4 | `orders-api:1.0.0` |

Revision 4 represents a rollback to the original image, not a return to revision number 1.

In Kubernetes, `revisionHistoryLimit` controls how many old ReplicaSets are retained for rollback purposes.

Deleting an old ReplicaSet can remove the ability to roll back to its revision.

## 9. Rollbacks

A rollback restores a previous Deployment Pod template.

A typical rollback workflow is:

1. Identify an earlier revision.
2. Inspect its configuration.
3. Select the target revision.
4. Restore the previous Pod template.
5. Create a new rollout revision.
6. Replace the current Pods according to the update strategy.
7. Verify application readiness and availability.

A rollback does not necessarily restore the complete state of the application.

For example, it does not automatically reverse:

- Database schema migrations.
- External service changes.
- Persistent volume modifications.
- Configuration changes stored outside the Pod template.
- Changes to independently managed resources.

A rollback must therefore be evaluated against application compatibility and external dependencies.

The four source implementations model rollback through the restoration of an earlier container image.

The PostgreSQL procedure creates a new revision using the selected historical image.

## 10. Scaling

Scaling changes the desired replica count.

For example:

- Existing desired replicas: 3.
- New desired replicas: 5.

The ReplicaSet controller creates two additional Pods.

Scaling down from five to two causes excess Pods to be terminated.

Scaling is separate from application-version updates. A replica-count change does not inherently require a new Pod template revision.

In a production cluster, Horizontal Pod Autoscaling can adjust replica counts based on resource utilization or other configured metrics.

The implementations provide explicit scaling methods and reconcile the corresponding ReplicaSet state.

## 11. Failure Conditions

Deployment operations may encounter several failure scenarios.

| Failure | Effect |
|---|---|
| Invalid image | New application version cannot be started |
| Image pull failure | Pod cannot obtain its container image |
| Scheduling failure | Pod remains pending |
| Readiness failure | Pod does not become available |
| Insufficient node capacity | Additional Pods cannot be scheduled |
| Application crash | Container may restart or become unhealthy |
| Insufficient surge capacity | Replacement operations may wait |
| Insufficient availability | Old Pods cannot safely be removed under the policy |
| Missing historical revision | Requested rollback cannot proceed |

A production Deployment can also report progress deadline failures.

`progressDeadlineSeconds` controls when a Deployment is considered to have failed to make sufficient progress. The setting does not automatically perform a rollback.

The simulations represent basic failure validation and waiting conditions. They do not reproduce the full Kubernetes scheduling, networking, image-pull, or container-runtime subsystems.

## 12. Python Implementation

The Python implementation uses dataclasses and enumerations to model Kubernetes resource objects.

### Main components

| Component | Responsibility |
|---|---|
| `ContainerSpec` | Defines the application container |
| `DeploymentSpec` | Stores declarative Deployment configuration |
| `Pod` | Models an individual application instance |
| `ReplicaSet` | Maintains Pod ownership and replica counts |
| `DeploymentStatus` | Represents observed Deployment state |
| `DeploymentController` | Coordinates reconciliation and rollout operations |

### Important mechanisms

- Dataclasses represent resource specifications and observed status.
- Enumerations restrict valid lifecycle states.
- Dictionaries provide indexed resource storage.
- UUIDs distinguish simulated resources.
- Exceptions reject invalid transitions.
- Reconciliation synchronizes desired and observed state.
- Revision history enables rollback.
- Logging provides operational diagnostics.
- JSON reporting exposes the current resource state.

### Execution

Run the script using Python 3.10 or later.

The demonstration creates an initial Deployment, marks Pods ready, updates the container image, executes a rolling update, performs a rollback, and scales the Deployment.

No third-party Python packages are required.

## 13. JavaScript Implementation

The JavaScript implementation emphasizes event-driven controller behavior.

### Main components

| Component | Responsibility |
|---|---|
| `Pod` | Models Pod lifecycle and readiness |
| `ReplicaSet` | Tracks Pods using a Map |
| `Deployment` | Coordinates the desired state |
| `EventEmitter` | Publishes resource lifecycle events |
| `validateConfig()` | Validates Deployment configuration |
| `rollingUpdateStep()` | Performs one rollout operation |
| `saveReport()` | Persists a JSON status report |

The event-driven design publishes events when:

- A ReplicaSet is created.
- A Pod is created.
- A Pod becomes ready.
- A Pod terminates.
- A Deployment changes.
- A rollout operation executes.

`Map` provides resource lookup, while `EventEmitter` separates state transitions from monitoring and reporting.

The asynchronous rollout method uses Promises and Node.js scheduling to represent controller operations.

### Execution

Run using Node.js 18 or later.

No npm dependencies are required.

The optional report-writing operation uses Node.js filesystem permissions to restrict access to the generated file.

## 14. C++17 Implementation

The C++ implementation emphasizes explicit state management and resource ownership.

### Main components

| Component | Responsibility |
|---|---|
| `DeploymentPolicy` | Validates replica and rollout parameters |
| `Pod` | Enforces lifecycle transitions |
| `ReplicaSet` | Owns Pod objects |
| `Revision` | Stores historical image information |
| `DeploymentController` | Implements reconciliation and rollout |

The implementation uses:

- `enum class` for strongly typed lifecycle states.
- `unique_ptr` for exclusive resource ownership.
- `map` for deterministic resource indexing.
- STL algorithms for counting and filtering.
- References for controlled access to managed objects.
- Exceptions for invalid operations.

Exclusive ownership prevents accidental copying of managed Pod objects.

The rollout algorithm explicitly calculates:

- Total active replicas.
- Ready replicas.
- Old-version replicas.
- New-version replicas.
- Maximum permitted capacity.
- Minimum required availability.

This approach demonstrates how deployment policies can be represented in a strongly typed resource-management system.

### Compilation

Requires a C++17-compatible compiler.

The program uses no external libraries.

## 15. Java 17 Implementation

The Java implementation uses an enterprise-oriented service architecture.

### Main components

| Component | Responsibility |
|---|---|
| `ContainerDefinition` | Immutable container configuration |
| `DeploymentPolicy` | Immutable rollout policy |
| `Pod` | Stateful application instance |
| `ReplicaSet` | Pod ownership and replica management |
| `Revision` | Historical Deployment specification |
| `DeploymentStatus` | Immutable status representation |
| `DeploymentService` | Deployment management operations |

Java records represent immutable configuration and status values.

The service layer separates resource operations from configuration definitions.

Synchronized methods provide basic protection against concurrent modification of the in-memory simulation.

The implementation validates resource identity, image names, replica counts, and rolling-update parameters.

Its rollout service evaluates availability constraints before terminating existing Pods.

The implementation is a single-process simulation, not a distributed Kubernetes controller.

### Compilation and execution

The class is named `DeploymentGovernance`.

Compile using Java 17 and execute the resulting class.

No third-party dependencies are required.

## 16. PostgreSQL Implementation

The PostgreSQL implementation models the deployment lifecycle using relational tables, integrity constraints, indexes, functions, procedures, triggers, and reporting views.

### Database relationships

| Table | Purpose |
|---|---|
| `namespaces` | Namespace definitions |
| `deployments` | Desired Deployment specifications |
| `deployment_revisions` | Historical Deployment templates |
| `replica_sets` | ReplicaSet ownership and revision |
| `pods` | Individual application instances |
| `rollout_operations` | Recorded rollout operations |
| `reconciliation_events` | Desired versus observed state |

### Integrity mechanisms

Primary keys identify resources.

Foreign keys enforce ownership relationships.

Unique constraints prevent duplicate Deployment names within a namespace and duplicate revisions within a Deployment.

Check constraints reject invalid replica counts, ports, and rollout policies.

Triggers validate specifications and update Deployment generations.

Indexes support queries involving namespace, Deployment, ReplicaSet, Pod state, and revision history.

### Stored functions and procedures

| Function or procedure | Purpose |
|---|---|
| `validate_deployment_spec()` | Validates Deployment configuration |
| `update_deployment_generation()` | Tracks specification changes |
| `create_deployment_revision()` | Stores Deployment revisions |
| `create_replica_set()` | Creates ReplicaSets |
| `create_pod()` | Creates simulated Pods |
| `set_pod_readiness()` | Updates readiness state |
| `terminate_pod()` | Terminates an active Pod |
| `reconcile_deployment()` | Synchronizes replica counts |
| `refresh_deployment_status()` | Recalculates observed status |
| `update_deployment_image()` | Creates an image-update revision |
| `rollback_deployment()` | Restores a previous image |
| `rolling_update_step()` | Executes one rollout operation |

### Reporting views

`deployment_overview` provides a consolidated Deployment and Pod status.

`rollout_eligibility` evaluates replica availability against the configured unavailability allowance.

The reporting queries identify:

- Replica-count mismatches.
- Unready Pods.
- Obsolete container images.
- Revision history.
- Rollout activity.
- Namespace-level replica utilization.

### Transaction handling

The SQL script runs inside a transaction.

The savepoint and exception-handling demonstration illustrates how invalid replica updates are rejected without aborting the complete database workflow.

The schema is a learning-oriented relational simulation. It does not implement the complete Kubernetes API server, scheduler, admission controllers, or distributed controller-runtime behavior.

## 17. Deployment State Transitions

The implementations use explicit lifecycle transitions.

### Pod lifecycle

Pending
  |
  v
Running
  |
  +----> Ready
  |        |
  |        v
  |     Unready
  |
  v
Terminating
  |
  v
Terminated

A failed Pod can enter the Failed state.

### Deployment lifecycle

Progressing
    |
    +----> Available
    |
    +----> Degraded
    |
    +----> Failed

The simulated state transitions are simplified. Actual Kubernetes status conditions include more detailed reasons and condition types.

### ReplicaSet lifecycle

Active
  |
  v
Scaled down
  |
  v
Inactive
  |
  v
Retained for rollback or removed

An inactive ReplicaSet may remain in the cluster with zero desired replicas.

## 18. Performance Considerations

Controller efficiency depends on resource counts, lookup operations, reconciliation frequency, and API-server activity.

The implementations demonstrate several performance-oriented choices.

| Implementation | Design choice |
|---|---|
| Python | Dictionaries provide efficient resource lookup |
| JavaScript | Maps provide indexed resource storage |
| C++17 | Ordered maps and unique ownership provide predictable resource management |
| Java 17 | HashMaps provide average constant-time lookup |
| PostgreSQL | Composite indexes support common resource queries |

For a system with \(N\) Pods:

- Counting all Pods requires \(O(N)\) work.
- Filtering Pods by image requires \(O(N)\) work without an appropriate index.
- Indexed resource lookup is generally more efficient than repeated full collection scans.
- A complete report requires work proportional to the number of resources being reported.

Production controllers should also consider API request limits, event processing, retry backoff, concurrent reconciliations, and watch-based resource observation.

## 19. Security Considerations

Deployment configuration affects the security of the application execution environment.

Important controls include:

- Use trusted container registries.
- Prefer immutable image digests for reproducible deployments.
- Apply Kubernetes RBAC to restrict Deployment modifications.
- Avoid embedding credentials in container images.
- Store sensitive configuration in appropriately protected Secrets.
- Apply least-privilege service accounts.
- Define CPU and memory requests and limits.
- Apply network policies where required.
- Use image vulnerability scanning.
- Restrict privileged containers.
- Audit Deployment and ReplicaSet modifications.
- Protect access to deployment reports and audit data.

An image tag alone does not guarantee immutable image content. An image digest provides a more precise reference to the intended image.

A rollback should also be checked for security vulnerabilities. Restoring an older application version can restore previously corrected security weaknesses.

## 20. Important Differences Between the Simulation and Kubernetes

| Capability | Simulations | Kubernetes |
|---|---|---|
| Declarative configuration | Implemented | Implemented |
| ReplicaSet ownership | Implemented | Implemented |
| Reconciliation | Simplified | Distributed control loops |
| Pod scheduling | Simulated | Scheduler-managed |
| Container execution | Simulated | Container runtime |
| Readiness | Manually controlled | Probe-driven |
| Liveness | Not fully implemented | Probe-driven |
| Rolling updates | Step-based simulation | Controller-managed |
| Rollback | Image-based revision model | Pod-template revision restoration |
| Service traffic routing | Not implemented | Service and endpoint mechanisms |
| Persistent storage | Not implemented | Volume and storage subsystems |
| Horizontal autoscaling | Manual scaling | HPA integration supported |
| Admission control | Not implemented | Admission controllers |
| RBAC | Not implemented | Kubernetes authorization |

The simulations intentionally focus on Deployment and ReplicaSet control behavior instead of recreating the entire Kubernetes platform.

## 21. Practical Deployment Workflow

A typical application release follows this sequence:

1. Define the Deployment specification.
2. Apply the desired configuration.
3. Allow the Deployment controller to create the ReplicaSet.
4. Allow the ReplicaSet controller to create Pods.
5. Verify Pod scheduling and startup.
6. Check readiness and availability.
7. Observe the rollout status.
8. Investigate failed or unavailable Pods.
9. Confirm that the desired image is running.
10. Retain sufficient revision history for recovery.

A release should not be considered successful solely because the requested number of Pods exists. The application must also satisfy its readiness, availability, and operational requirements.
