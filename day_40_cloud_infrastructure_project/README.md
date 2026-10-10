# Cloud Infrastructure Project

## Scope

This project models a basic virtual cloud infrastructure as a provider-neutral system containing compute, networking, storage, and security components.

The implementations do not attempt to reproduce a particular public-cloud provider API. Instead, they model the underlying infrastructure relationships that appear across platforms:

- A virtual network provides an address space.
- Subnets divide that address space into public and private network segments.
- Compute instances consume subnet addresses and attach to security policies.
- Security groups control permitted network flows.
- Block storage provides persistent storage for compute workloads.
- Object storage provides independently addressable objects.
- IAM-style roles determine which users can administer infrastructure resources.
- Infrastructure events provide an operational audit trail.

The five executable implementations approach the same infrastructure problem from different technical perspectives. Python emphasizes an executable control-plane simulation, JavaScript emphasizes event-driven infrastructure operations, C++ implements a typed governance engine, Java models an enterprise domain with explicit abstractions, and PostgreSQL represents the infrastructure as a relational system with database-level integrity.

## Infrastructure Model

The logical architecture is:

    Internet
        |
        v
    Public Web Subnet
        |
        v
    Web Compute
        |
        v
    Private Application Subnet
        |
        v
    Application Compute
        |
        v
    Private Database Subnet
        |
        v
    Database Compute
        |
        +------> Encrypted Block Storage

    Application and platform services
        |
        +------> Encrypted Object Storage

The important architectural boundary is between public and private resources. The public subnet contains externally reachable workloads, while application and database workloads are placed in private address ranges. Network policy determines whether traffic is allowed between these layers.

## Networking

The virtual network is represented by `10.0.0.0/16` in the implementations. It is divided into separate subnets:

| Subnet | CIDR | Purpose | Exposure |
|---|---|---|---|
| `public-web` | `10.0.1.0/24` | Web-facing compute | Public |
| `private-app` | `10.0.10.0/24` | Application workloads | Private |
| `private-database` | `10.0.20.0/24` | Database workloads | Private |

Subnetting is important because a single large network does not by itself express application trust boundaries. The subnet structure gives the security model meaningful network locations to evaluate.

The database subnet accepts database traffic from the application subnet. The public web workload does not receive the same database access merely because both workloads belong to the same virtual network.

The SQL implementation uses PostgreSQL `CIDR` and `INET` types rather than storing network addresses as arbitrary strings. This allows PostgreSQL network operators such as `<<` to perform actual subnet membership checks.

## Compute

Compute resources are modeled as stateful workloads. An instance can be stopped, running, or terminated.

The lifecycle rule is intentionally restrictive:

    STOPPED -> RUNNING
    RUNNING -> STOPPED
    RUNNING -> TERMINATED
    STOPPED -> TERMINATED

A terminated instance cannot be restarted.

The Python implementation represents this using `InstanceState` and explicit lifecycle methods. The Java implementation encapsulates state transitions inside `ComputeInstance`. The C++ program uses an enum and rejects invalid lifecycle operations with exceptions.

The JavaScript version adds an event-driven behavior. Starting an instance emits an `instance.started` event, allowing another part of the program to react without being directly coupled to the state-changing method.

The SQL implementation represents lifecycle state with a PostgreSQL enum and performs instance startup inside a transaction-aware stored function.

## Security Groups

Security groups are represented as collections of inbound or outbound network rules.

A representative database rule is:

    TCP
    Port 5432
    Source 10.0.10.0/24
    Action allow

This means PostgreSQL traffic is accepted when the source belongs to the application subnet.

The important distinction is that a security group is attached to a workload rather than being a generic statement that a port is safe. The destination instance's security policy is evaluated against the source address and requested protocol and port.

The web security group permits HTTPS traffic on port 443 from the public network and permits SSH only from the private application subnet.

This creates a more meaningful policy than simply opening all ports.

## Security Policy Evaluation

The basic network authorization flow is:

    source instance
          |
          v
    source private IP
          |
          v
    destination instance
          |
          v
    destination security group
          |
          v
    matching protocol + port + source network
          |
          v
    allow or deny

The Python `can_connect` method performs this evaluation directly.

The JavaScript implementation uses an event-driven control plane but retains the same security boundary.

The C++ governance engine separates security policy from compute state and uses `SecurityGroup::allowsInbound()` as the policy evaluation point.

The Java implementation treats the security group as a domain object with `NetworkRule` records. This keeps network authorization rules separate from infrastructure lifecycle behavior.

The SQL implementation stores individual rules relationally and uses PostgreSQL network operators when evaluating whether a source address belongs to a permitted CIDR.

## Compute and Network Relationship

An instance cannot be considered independently from its network configuration.

Each compute resource has:

- a subnet
- a private IP address
- a security group
- a lifecycle state
- compute capacity
- optional persistent storage

The Python implementation validates that an assigned private address belongs to the selected subnet.

The SQL schema uses foreign keys between compute instances and subnets and creates a partial unique index so an active private IP cannot be assigned to multiple non-terminated instances.

That database constraint is important because application-level validation alone is vulnerable to concurrent requests. Two provisioning operations could independently check an address and both attempt to allocate it. A database uniqueness rule provides a stronger final integrity boundary.

## Storage

The project distinguishes object storage from block storage.

### Block Storage

Block storage is attached to a compute instance and is modeled with a size and attachment relationship.

The database workload receives a 100 GB encrypted block volume named `database-data`.

The attachment relationship is separate from the storage resource itself. This reflects the fact that persistent storage can have an independent lifecycle from the compute instance.

The implementations prevent a volume from being attached twice and require encryption for block storage.

### Object Storage

Object storage is represented by a bucket containing objects addressed by keys.

The Python implementation stores object bytes in memory and calculates a SHA-256 checksum.

The JavaScript implementation performs the same conceptual operation using Node.js `crypto`, but uses it as part of an event-driven Node application.

The SQL implementation stores object metadata including a checksum, encryption state, object size, and bucket relationship.

The object bucket policy can require encryption. The PostgreSQL trigger prevents an unencrypted object from being inserted when the bucket requires encryption.

This is an example of placing an invariant at the database layer instead of relying exclusively on application logic.

## IAM and Authorization

Network authorization and administrative authorization are different concerns.

A security group determines whether network traffic is allowed.

IAM determines whether a human or service identity is allowed to administer a resource.

The project models roles such as:

| Role | Representative permissions |
|---|---|
| Administrator | Compute, network, storage, security |
| Developer | Compute, storage |
| Network administrator | Network, security |
| Auditor | Storage read |

The Python implementation uses role-to-permission sets.

The Java implementation represents permissions as an enum and associates them with an immutable identity model.

The SQL implementation normalizes users, roles, permissions, user-role relationships, and role-permission relationships into separate tables.

This distinction prevents a common architectural mistake: treating network access and administrative access as if they were the same policy.

## Python Implementation

The Python program is a provider-neutral infrastructure control-plane simulation.

Its `CloudInfrastructure` class owns virtual networks, security groups, compute instances, buckets, block volumes, and users.

`VirtualNetwork` validates subnet placement and prevents overlapping subnets.

`ComputeInstance` models lifecycle state transitions and attached volumes.

`StorageBucket` demonstrates object creation, retrieval, deletion, encryption enforcement, and SHA-256 checksums.

`SecurityGroup` performs network rule matching.

`authorize()` models role-based infrastructure permissions.

The script also intentionally exercises failure conditions. It attempts to create an overlapping subnet, assign an invalid private address, attach an already attached volume, restart a terminated instance, and store an unencrypted object in an encrypted bucket.

Those failures are not decorative examples. They demonstrate where infrastructure systems need explicit validation rather than assuming every API request is valid.

## JavaScript Implementation

The JavaScript implementation uses Node.js and emphasizes event-driven infrastructure behavior.

`CloudControlPlane` extends `EventEmitter`. Starting a compute instance produces an `instance.started` event, while storage attachment produces a `volume.attached` event.

This is useful for infrastructure automation because provisioning systems frequently react to state changes. For example, a production platform could use a state transition to trigger monitoring registration, inventory updates, configuration management, or audit logging.

The program also uses asynchronous execution through `async` functions and `await`. The small `wait()` function represents asynchronous provisioning boundaries without requiring an external cloud API.

Node's built-in `crypto` module provides SHA-256 checksums for object data, avoiding an unnecessary third-party dependency.

The JavaScript implementation therefore adds an event-oriented perspective instead of merely translating the Python object model.

## C++ Case Study

The C++ program implements a typed infrastructure governance engine.

`GovernanceEngine` owns networks, security groups, instances, and volumes using standard-library containers.

The security model is represented by `SecurityRule` and `SecurityGroup`.

The compute model is represented by `ComputeInstance`, which owns lifecycle state and its attached volume names.

The storage model is represented by `BlockVolume`.

The case study focuses on deterministic governance decisions:

    Is the source instance running?
    Is the destination instance running?
    Does the destination security group exist?
    Does an inbound rule match protocol?
    Does it match the destination port?
    Does the source IP belong to the allowed network?

Only when those conditions are satisfied is communication allowed.

The C++ implementation also demonstrates an explicit policy decision where a deny rule takes precedence after a matching rule is found. This is a useful model for infrastructure policy engines because rule ordering and conflict behavior must be defined rather than left ambiguous.

The implementation uses `std::unordered_map` for resource lookup and `std::set` for unique subnet and volume associations. Most resource lookups are expected to be approximately O(1) average time, while ordered set operations are O(log n).

The program is compiled as C++17 and requires no external library.

## Java Implementation

The Java implementation presents the infrastructure as an enterprise domain model.

Java enums represent controlled states and permissions. Records represent immutable network-rule configuration.

`ComputeInstance` owns lifecycle transitions and rejects invalid state changes.

`BlockVolume` protects its attachment relationship and refuses unencrypted storage.

`Identity` represents administrative capabilities independently from infrastructure resources.

`CloudPolicy` provides explicit authorization decisions such as whether an identity may manage compute, manage networks, or read storage.

The separation is important because enterprise infrastructure platforms typically have multiple policy layers. A developer may be permitted to restart compute instances while lacking permission to change network security. An auditor may inspect storage without being allowed to modify it.

The implementation uses standard Java collections and exceptions and requires Java 17 or later.

## SQL Data Model

The PostgreSQL schema models infrastructure as related persistent entities.

The principal relationships are:

    cloud_user
        |
        +--- user_role --- role --- role_permission --- permission

    virtual_network
        |
        +--- subnet
                |
                +--- compute_instance
                         |
                         +--- volume_attachment --- storage_resource

    security_group
        |
        +--- security_rule

    object_bucket
        |
        +--- object_record

The foreign keys enforce relationships that should never become orphaned.

The `virtual_network` table stores network CIDRs using PostgreSQL's `CIDR` type.

The `compute_instance` table uses `INET` for private addresses.

The partial unique index on active private addresses prevents an address from being reused by multiple active instances.

## Database-Level Enforcement

Some infrastructure rules belong at the database boundary.

The encrypted block-storage trigger rejects a block volume with encryption disabled.

The object-storage trigger reads the bucket's encryption policy and rejects plaintext objects when encryption is mandatory.

The `start_instance()` function locks the selected instance row before evaluating and changing its lifecycle state. This prevents a simple read-then-write sequence from becoming inconsistent when multiple operations interact with the same resource.

Transactions are used around the compute startup operations so the lifecycle changes and corresponding audit records participate in the same database transaction.

This illustrates an important infrastructure principle: application validation is useful, but critical invariants should also be enforced by the persistence layer when the database owns the authoritative state.

## Auditability

Infrastructure operations can have operational and security consequences, so the SQL implementation contains an `infrastructure_event` table.

Events record:

- event type
- actor
- affected instance
- descriptive message
- timestamp

This permits operational queries such as identifying who started an instance or examining recent infrastructure changes.

The same conceptual requirement appears in the other implementations through explicit methods and state transitions, although the SQL version provides durable relational audit records.

## Failure Conditions

The implementations intentionally address common infrastructure failure conditions.

An instance cannot restart after termination because termination represents an irreversible lifecycle state in this model.

A block volume cannot be attached twice.

An encrypted bucket rejects plaintext objects.

A private IP cannot be allocated outside its subnet.

An active private IP cannot be shared between compute resources in the PostgreSQL model.

A subnet cannot overlap another subnet in the Python model.

Database access from the public web tier is rejected because the database security group only permits port 5432 from the application subnet.

A developer does not automatically receive network-administration permissions.

These rules demonstrate that infrastructure design is primarily about controlling valid state and valid relationships, not simply creating resources.

## Security Considerations

The example intentionally uses private network segments for application and database workloads.

The database port is not opened to the public network.

SSH access is narrower than HTTPS access.

Block storage is encrypted.

Object storage can require encryption.

Administrative permissions are separated by role.

Infrastructure operations are represented as auditable events.

A real cloud platform would require stronger controls than this educational model. Production systems should use provider-managed identity, short-lived credentials, secrets management, encryption key management, centralized audit logging, network segmentation, least-privilege policies, vulnerability management, monitoring, and formal change controls.

The source code should not be interpreted as a complete production security boundary.

## Performance Considerations

The in-memory Python, JavaScript, C++, and Java implementations use maps or dictionaries for direct resource lookup.

For small infrastructure models this is sufficient. Large control planes require more careful handling of concurrency, indexing, caching, distributed state, retries, idempotency, rate limits, and eventual consistency.

The SQL implementation adds indexes to commonly queried relationships such as:

- subnet membership
- compute state
- security-group rules
- object buckets
- infrastructure event timestamps

Indexes improve lookup performance but introduce write overhead and consume storage. They should therefore correspond to actual query patterns rather than being added indiscriminately.

## Production Design Boundaries

The project is a local model rather than a real cloud provider implementation.

A production infrastructure platform would need to handle resource reconciliation, concurrent provisioning requests, retries, idempotency keys, distributed locks or transactional state management, asynchronous operations, quotas, resource tagging, monitoring, secrets, key management, backups, disaster recovery, high availability, API authentication, authorization policies, and audit retention.

The important architectural lesson is that compute, networking, storage, and security cannot be designed as isolated modules. They form a dependency graph.

A compute instance depends on a subnet and security policy. Storage depends on an attachment relationship. Network access depends on both endpoint state and security rules. Administrative operations depend on identity permissions. Persistent infrastructure state requires integrity guarantees and auditability.

The implementations therefore treat infrastructure as a governed system of resources and relationships rather than as a collection of unrelated virtual machines.
