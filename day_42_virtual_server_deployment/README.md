# Virtual Server Deployment and Lifecycle Management

## Technical scope

Virtual server deployment converts a requested computing configuration into an allocated, network-connected, operational machine. Lifecycle management controls what happens after that allocation, including startup, health verification, stopping, restarting, recovery, and termination.

The implementations in this repository model a cloud control plane rather than an actual hypervisor. They cover configuration validation, resource selection, network policy, deployment failures, lifecycle state transitions, inventory, operational auditing, and indicative compute costs. The cloud provider is simulated, so the examples can execute without credentials or a cloud account.

The central operational distinction is between **desired configuration**, **provider allocation**, and **observed runtime state**. A valid configuration does not guarantee successful provisioning. An allocated instance does not guarantee that its application is healthy. A successful stop request does not prove that every dependent resource has stopped billing.

## Deployment architecture

A practical deployment workflow separates the request, policy decision, provisioning operation, and runtime verification.

    Deployment request
          |
          v
    Configuration validation
          |
          v
    Environment and network policy
          |
          v
    Compute and image selection
          |
          v
    Provider allocation
          |
          v
    Boot and startup configuration
          |
          v
    Health verification
          |
          v
    Inventory and lifecycle monitoring

Each stage has a different failure mode. Validation errors should be rejected before allocation. Provider errors require operational recovery. Health-check failures require diagnosis of startup configuration, network access, application dependencies, or machine health.

### Configuration and resource selection

A server specification describes the requested machine independently of a particular runtime instance. It includes the instance name, machine image, region, compute flavor, root disk capacity, environment, network attachment, monitoring requirements, encryption policy, and ownership information.

Compute flavors represent predefined capacity profiles. The sample profiles provide two, four, and eight virtual CPUs with increasing memory and hourly compute rates. These rates are illustrative, not current provider prices.

Separating specifications from instances makes it possible to validate configuration before allocating resources and to compare requested capacity with observed infrastructure state.

### Machine images and startup configuration

A machine image establishes the operating system and initial software environment. Production deployments should use approved, maintained images with a defined patching and vulnerability-management process.

Startup configuration performs machine initialization after allocation. It may create directories, configure services, retrieve application artifacts, or register monitoring agents. A successful infrastructure API response does not prove that these actions completed successfully.

Startup scripts should be idempotent where possible. Repeated execution should not corrupt existing configuration or create duplicate services. Secrets should be obtained through an authorized secret-management mechanism rather than embedded in scripts, source control, or inventory records.

### Network attachment

A virtual machine usually receives a private address from its subnet. Public addressing is a separate decision and should not be enabled merely because a service needs outbound access.

Security groups define permitted traffic. Ingress rules should specify the required protocol, port, and source range. Production SSH access should be restricted to approved sources or replaced with managed session access.

The examples use documentation-only addresses to illustrate allocation. They do not represent reachable cloud resources.

## Lifecycle semantics

The lifecycle model uses explicit states instead of treating a virtual machine as simply running or stopped.

| State | Operational meaning |
|---|---|
| `requested` | A deployment request has been accepted for processing. |
| `provisioning` | Resource allocation or startup is in progress. |
| `running` | The machine has completed the simulated allocation or start operation. |
| `stopping` | A stop operation is being processed. |
| `stopped` | The machine is not running, but its allocation record remains. |
| `restarting` | A restart operation is in progress. |
| `failed` | A provisioning or lifecycle operation failed and requires investigation or recovery. |
| `terminated` | The machine has reached a terminal state and cannot be restarted. |

The distinction between `stopped` and `terminated` is important. A stopped machine may be restarted using retained infrastructure configuration. Termination represents the end of the machine's lifecycle and may release its addresses or other resources. Persistent disks, snapshots, static addresses, and backups may have independent lifecycles.

The transition rules prevent operations that are inconsistent with the current state. For example, restarting a stopped instance is rejected, and terminating an already terminated instance is treated as an invalid request.

### Provisioning and recovery

Provisioning is a multi-stage operation. The controller records the transition into `provisioning`, calls the provider adapter, records the allocation, and transitions to `running` only after the simulated allocation succeeds.

When allocation fails, the instance enters `failed` and the error is retained in the audit history. The failure is not silently converted into a successful deployment.

Recovery should be deliberate. A controller must determine whether the provider created resources before the failure was reported. In a real cloud system, a timeout can occur after a resource was successfully created. Blindly retrying may create duplicate instances unless the operation uses provider-supported idempotency or performs reconciliation.

### Restart behavior

Restarting a machine and replacing it are different operations. A restart normally preserves the machine identity and attached persistent storage while rebooting the operating system. Replacement creates a new instance and may change addresses, identifiers, or attached resources.

The simulations increment a boot counter to make restarts observable. They do not emulate operating-system reboot timing, graceful shutdown signals, application draining, or storage consistency.

### Audit history

Each lifecycle transition records its action, previous state, new state, actor, timestamp, and relevant details. This creates a trace of the controller's decisions and helps distinguish a user request from a provider failure or a recovery attempt.

A production audit system should use durable storage, reliable timestamps, access controls, retention rules, and protection against unauthorized modification. An in-memory event list is useful for demonstrating behavior but is not sufficient for compliance or incident investigation.

## Python implementation

The Python program builds a self-contained deployment simulator using the standard library.

`ServerSpecification` and `NetworkConfiguration` are immutable data classes. Their validation methods reject invalid names, unsupported flavors, malformed identifiers, invalid ports, and unsuitable production settings before a provider operation begins.

`LifecycleManager` owns the allowed transition graph. `DeploymentService` coordinates deployment, start, stop, restart, termination, inventory queries, and cost estimation. `SimulatedCloudProvider` isolates provider operations from lifecycle rules and supports injected failures so that error handling can be observed without external infrastructure.

The inventory serializer records instance configuration, runtime state, addresses, tags, boot count, and audit events. `save_inventory` writes JSON to a temporary file in the destination directory and then uses an atomic replacement. This reduces the risk of leaving a partially written inventory file after a process failure.

The executable test suite verifies deployment, duplicate-name rejection, invalid transitions, provider failure recording, production encryption requirements, and persisted inventory structure.

Run the demonstration with:

    python virtual_server_deployment.py

Run the tests separately with:

    python virtual_server_deployment.py --test-only

Write a simulated inventory file with:

    python virtual_server_deployment.py --inventory vm_inventory.json

The inventory persistence example writes local state; it does not provide synchronization between concurrent controllers. A real deployment system would need a shared database or another durable coordination mechanism to prevent two workers from claiming the same instance name.

## JavaScript implementation

The JavaScript file focuses on asynchronous control-plane behavior.

`DeploymentController` uses private class fields for its instance inventory, name index, idempotency records, and operation generations. `MockCloudAdapter` separates provider operations from controller policy, while `EventBus` distributes lifecycle events to listeners.

### Idempotency and duplicate requests

The deployment method requires an idempotency key. A repeated request with the same key and identical specification returns the original instance. Reusing the key for a different request is rejected.

This prevents a simple retry from allocating a second machine in the simulation. In production, idempotency records must be durable and scoped appropriately. Their lifetime, payload comparison rules, and relationship to provider request identifiers must be explicitly defined.

### Asynchronous operations

Provisioning and lifecycle methods use `async` and `await`. Provider calls can fail after an operation has entered an intermediate state, so each method records the failure and updates health information.

Operation generations illustrate a further concurrency concern: a late asynchronous response should not overwrite the result of a newer lifecycle request. A real controller also needs distributed locking or optimistic concurrency control when multiple workers can update the same resource.

The event bus isolates listener exceptions from lifecycle operations. A monitoring listener failing to process an event does not undo an allocation that has already succeeded. This separation is useful for notifications and metrics, although production event delivery should use durable messaging when loss is unacceptable.

Run with:

    node virtual_server_deployment.js

The implementation uses only Node.js built-in modules.

## C++ case study

The C++ program models a platform operations team responsible for application servers in development and production environments.

### Architecture and data structures

`ServerSpec` represents deployment intent, while `Instance` stores runtime state and audit history. `NetworkPolicy` records the subnet, security groups, ingress ports, and public-address decision. `PolicyEngine` validates configuration and exposes the allowed lifecycle transitions.

`DeploymentEngine` coordinates the workflow. An `unordered_map` indexes instances by identifier, and a second map prevents duplicate names. A simulated provider isolates resource allocation and supports injected failures.

The flavor catalogue uses an ordered map because the set of available compute profiles is small and stable. The audit log uses a vector because the program appends events and traverses them in sequence.

### Validation and failure behavior

Production machines must have encrypted root disks and monitoring enabled. Every server requires an owner, subnet, security group, supported flavor, and valid disk capacity.

Provider failures transition instances into `failed` when the transition is permitted. The controller retains the error description in the audit record and permits a deliberate recovery attempt. Terminated instances remain terminal.

The use of `std::optional` for IP addresses represents the fact that an address may not exist before allocation or after termination. This is preferable to using a fabricated address as a sentinel value.

### Complexity and operational trade-offs

Instance lookup is average-case constant time with the hash-based inventory. Name uniqueness checks are also average-case constant time. Transition validation performs a bounded lookup over a small state graph, so its cost is effectively constant.

The implementation is single-threaded. It does not provide concurrent lifecycle locking, durable inventory, network API retries, or rollback of partially completed provider operations. A production control plane would need to address these concerns independently of the in-memory state machine.

Compile and run with:

    g++ -std=c++17 -Wall -Wextra -Wpedantic virtual_server.cpp -o virtual_server
    ./virtual_server

## Java implementation

The Java program emphasizes enterprise domain modeling and explicit policy boundaries.

`ComputeFlavor`, `NetworkProfile`, `ServerSpecification`, `Allocation`, and `AuditEvent` are records. Their constructors validate or defensively copy values so that invalid network configurations and accidental mutation are less likely to pass through the service layer.

`VirtualMachine` represents mutable runtime state. The `LifecyclePolicy` class defines permitted state transitions, and `DeploymentService` coordinates provider operations and state changes. The `CloudAdapter` interface allows the lifecycle service to use a simulated provider without depending on a specific cloud SDK.

The server specification checks that its environment tag agrees with its actual environment. This prevents an inventory record from claiming that a production resource is development infrastructure merely because a tag was entered incorrectly.

The `DeploymentService` uses separate indexes for instance identifiers and names. It returns filtered inventory through streams and immutable collection views for audit access. The model uses runtime exceptions to distinguish deployment and lifecycle failures from invalid configuration.

The Java example is useful when domain invariants must remain explicit as a service grows. In a production implementation, provider operations and database transactions cannot usually be committed atomically. The service would need a durable operation record and reconciliation process to resolve cases where the provider succeeds but the database update fails.

Compile and run with Java 17:

    javac VirtualServerDeployment.java
    java VirtualServerDeployment

## PostgreSQL data model

The SQL script represents deployment state relationally and enforces basic integrity through database constraints.

| Relation | Purpose |
|---|---|
| `cloud_regions` | Identifies supported provider regions. |
| `subnets` | Associates address ranges and availability zones with regions. |
| `security_groups` | Stores network security configuration and ingress rules. |
| `machine_images` | Records operating-system images and their approval status. |
| `instance_types` | Defines compute capacity and indicative hourly rates. |
| `virtual_machines` | Stores deployment intent, resource allocation, state, and ownership. |
| `vm_security_groups` | Models the many-to-many relationship between machines and security groups. |
| `deployments` | Tracks versioned deployment attempts and outcomes. |
| `status_checks` | Stores named operational checks and their results. |
| `lifecycle_events` | Preserves transitions and operational actions. |
| `health_observations` | Stores timestamped probe results. |
| `branch_protection_policies` | Stores environment-specific virtual-machine deployment policies. |

The final relation's name is intentionally illustrative of policy protection, not Git branch protection. Its records govern server configuration requirements such as disk encryption, monitoring, image approval, private subnet placement, and maximum root disk size.

### Integrity enforcement

Primary keys identify records, foreign keys maintain relationships, unique constraints prevent duplicate instance names and idempotency keys, and check constraints reject invalid state names, disk capacities, addresses of the wrong type, and unsupported environment values.

The schema does not enforce every production policy through a single table constraint. For example, whether a machine image is approved depends on a related image record. The `deployment_readiness` view evaluates that condition together with network and environment policy.

Application-level validation and database constraints serve different purposes. Application validation can provide useful error messages before a provider operation. Database constraints protect persisted records when another client, script, or service bypasses the application.

### Lifecycle transactions

`record_lifecycle_transition` locks the selected machine row with `FOR UPDATE`, checks the transition graph, updates the state, and writes the corresponding audit event. The lock serializes competing transitions against the same row within the database transaction.

The example demonstrates a valid transition and an expected invalid transition. The helper does not execute cloud operations, and the database cannot independently guarantee that the provider's actual machine state matches the recorded state. An orchestrator must coordinate provider calls with durable operation records and reconciliation.

### Operational queries and indexes

The inventory view joins machine specifications with compute flavor information. The readiness view identifies configuration violations, and common table expressions can select the latest status check per machine.

Indexes support filtering by lifecycle state and region, retrieving recent audit events, finding recent status checks, and querying JSONB tags. The GIN index on `tags` is useful for supported JSONB containment queries; it is not automatically optimal for every JSON expression.

The cost function calculates an illustrative compute-only estimate. Actual invoices may include persistent disks, snapshots, traffic, public addresses, licenses, and provider-specific stopped-instance charges.

Run the script against a PostgreSQL database using a role authorized to create and remove the listed objects:

    psql -v ON_ERROR_STOP=1 -d deployment_lab -f virtual_server_deployment.sql

The script is designed as a repeatable lab reset and drops its named objects before rebuilding them. It should not be executed against an existing production schema without adapting the destructive setup statements.

## Deployment failures and operational controls

| Failure | Expected handling | Operational implication |
|---|---|---|
| Invalid configuration | Reject before allocation | Correct the specification or policy violation. |
| Unsupported image | Reject the request or fail readiness evaluation | Verify image provenance and approval. |
| Provider timeout | Record the failed or uncertain operation | Reconcile actual resources before retrying. |
| Startup failure | Mark deployment unhealthy or failed | Inspect startup logs, dependencies, and service readiness. |
| Network misconfiguration | Fail connectivity or health checks | Verify subnet routing and security-group rules. |
| Duplicate request | Reuse a durable idempotency record | Prevent duplicate allocations and charges. |
| Invalid state transition | Reject the operation | Reconcile the requested action with actual state. |
| Termination failure | Retain failure details and inspect provider state | Do not assume resources have been released. |

An instance state and its health status should not be treated as interchangeable. A machine may be running while its application is unhealthy, or a stopped machine may have no meaningful application health result. Infrastructure status, guest operating-system status, and application readiness should be measured separately.

## Cost, security, and production boundaries

The examples estimate compute cost from an hourly flavor rate and a selected number of hours. This is a simple planning estimate rather than billing reconciliation. Actual billing periods, rounding rules, discounts, commitments, regional pricing, storage, network transfer, and retained resources require provider-specific calculations.

Production deployment controls should include:

- **Least privilege:** grant the deployment controller only the permissions needed to allocate and manage approved resources.
- **Encryption:** enforce disk encryption and appropriate key-management policies for production data.
- **Network minimization:** avoid public addresses unless required, restrict ingress sources, and isolate administrative access.
- **Image governance:** maintain approved image versions and patching records.
- **Observability:** collect provider events, machine metrics, startup logs, and application health signals.
- **Durable state:** store lifecycle records in a shared, transactional system instead of relying on process memory.
- **Idempotent operations:** protect against duplicate resources when requests are retried.
- **Reconciliation:** periodically compare desired configuration with provider-observed state.
- **Termination safeguards:** protect retained storage and backups through explicit retention policies before deleting infrastructure.
- **Audit integrity:** restrict modification of operational records and retain sufficient evidence for incident investigation.

The simulations deliberately stop short of real cloud provisioning. Their provider adapters illustrate where a cloud SDK would be integrated, while their policy and lifecycle models show why resource allocation, runtime verification, state transitions, and durable operational records must remain distinct.
