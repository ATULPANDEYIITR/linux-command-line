# Cloud architecture fundamentals

## Topic introduction

Cloud architecture is the structured design of computing resources and services that work together to deliver an application or business capability.

A cloud application is rarely just a server. A production system commonly contains several interconnected layers:

- Users and clients
- DNS and global traffic routing
- CDN and edge services
- Load balancers
- Compute resources
- Application services
- Databases
- Caches
- Object storage
- Message queues
- Event systems
- Identity and access management
- Security controls
- Monitoring and observability
- Backup and disaster recovery
- Deployment infrastructure
- Cost and governance controls

The Python study script models these concepts progressively. The implementations are intentionally provider-neutral so that the architectural principles remain understandable without depending on a specific cloud platform.

---

## What cloud computing means

Cloud computing is the delivery of computing capabilities through a network using infrastructure and services that can generally be provisioned, managed, and scaled without owning and operating all of the underlying physical hardware.

Typical cloud capabilities include:

- Compute
- Networking
- Storage
- Databases
- Messaging
- Identity
- Security
- Monitoring
- Analytics
- Application platforms

The architectural objective is not simply to move an existing application onto a cloud provider. A cloud architecture should use appropriate properties of distributed infrastructure such as elasticity, redundancy, managed services, automation, and geographic distribution.

---

## Cloud service models

The script introduces four commonly discussed service models.

### Infrastructure as a Service

Infrastructure as a Service, or IaaS, provides fundamental infrastructure such as virtual machines, networking, and storage.

The customer generally has significant responsibility for:

- Operating systems
- Application software
- Network configuration
- Identity configuration
- Data
- Security configuration

IaaS provides substantial control but also creates substantial operational responsibility.

### Platform as a Service

Platform as a Service, or PaaS, abstracts more infrastructure and operating-system management.

The customer generally focuses more heavily on:

- Application code
- Configuration
- Data
- Application-level security

The platform provider manages more of the underlying infrastructure.

### Software as a Service

Software as a Service, or SaaS, delivers a complete application to customers.

The provider generally manages most of the technical stack.

The customer still has responsibilities such as:

- Account security
- Identity management
- Data governance
- Access configuration
- Appropriate application usage

### Function as a Service

Function as a Service, or FaaS, provides event-driven execution of individual functions.

The developer supplies function code while the platform manages much of the underlying execution infrastructure.

FaaS is particularly useful for event-driven workloads but may introduce limitations involving execution duration, startup latency, state management, and platform-specific behavior.

---

## Cloud deployment models

The script distinguishes several deployment models.

### Public cloud

Infrastructure is operated by a cloud provider and shared across customers through logical isolation.

### Private cloud

Infrastructure is dedicated to a single organization, although the implementation can vary substantially.

### Hybrid cloud

Hybrid architecture combines private infrastructure with public-cloud resources.

### Multi-cloud

Multi-cloud architecture uses services from multiple cloud providers.

Multi-cloud can provide organizational or technical benefits, but it also increases operational complexity, skills requirements, integration work, and governance overhead.

---

## Shared responsibility

Cloud security follows a shared-responsibility concept.

The provider is responsible for aspects such as physical facilities and underlying infrastructure. The customer remains responsible for many configuration, identity, application, and data controls.

The exact boundary changes with the service model.

For example, an IaaS customer normally has more operating-system responsibility than a SaaS customer.

The important architectural lesson is that using a managed cloud service does not eliminate security responsibility. It changes where the responsibility boundary lies.

---

## Regions and availability zones

A region represents a geographic cloud location.

An availability zone is an isolated infrastructure location within a region.

A simplified architecture is:

    Region
      |
      +-- Zone A
      +-- Zone B
      +-- Zone C

Deploying a critical workload in one zone creates exposure to a zone-level failure.

Deploying across multiple zones can reduce this risk.

Multi-region architecture provides stronger geographic resilience but introduces additional complexity involving:

- Data replication
- Traffic routing
- Failover
- Cross-region latency
- Data-transfer costs
- Consistency
- Disaster recovery

Geographic redundancy should be driven by business requirements rather than treated as an automatic requirement for every application.

---

## Compute architecture

Compute resources execute application logic.

The script demonstrates three broad compute approaches.

### Virtual machines

A virtual machine provides an operating-system environment with allocated CPU, memory, storage, and networking.

Virtual machines provide significant control but require management of more infrastructure components.

### Containers

Containers package applications with their dependencies while sharing an underlying operating-system kernel.

Container architecture makes application deployment more portable and allows workloads to be managed by orchestration platforms.

### Serverless functions

Serverless functions are short-lived execution units invoked by events or requests.

Typical characteristics include:

- Automatic scaling
- Event-driven execution
- Usage-based billing
- Reduced infrastructure management
- Stateless execution patterns

Potential constraints include:

- Cold starts
- Execution limits
- Platform-specific behavior
- Debugging complexity
- Dependency and networking considerations

Serverless does not mean that servers do not exist. It means that infrastructure management is largely abstracted from the application developer.

---

## Vertical and horizontal scaling

Scaling describes how a system handles increasing workload.

### Vertical scaling

Vertical scaling increases the capacity of an existing resource.

For example:

    4 CPU
        ->
    8 CPU

It is conceptually simple but eventually encounters physical or service limits.

### Horizontal scaling

Horizontal scaling adds more instances.

For example:

    1 application instance
        ->
    3 application instances

Horizontal scaling is particularly effective for stateless services.

### Elasticity

Elasticity is the ability to automatically adjust capacity as workload changes.

An autoscaling system can increase capacity during traffic spikes and reduce capacity when demand decreases.

Scaling must be considered across the complete dependency chain. Adding application servers does not solve a database bottleneck if the database remains the limiting component.

---

## Stateless and stateful applications

A stateless application does not depend on local process memory for durable user state between requests.

This makes horizontal scaling easier.

A stateful application keeps important state inside a particular process or machine.

A cloud architecture often moves shared state into services such as:

- Databases
- Distributed caches
- Object storage
- Message systems

This allows application instances to remain relatively interchangeable.

---

## Networking fundamentals

Networking is the communication layer connecting users, applications, services, databases, and external systems.

Important concepts include:

- IP addresses
- Subnets
- Routing
- Routers
- Firewalls
- NAT
- Load balancers
- DNS
- Private networks
- Public networks

The Python script demonstrates IPv4 conversion and basic subnet comparison.

A subnet provides a logical division of an IP network.

Network segmentation is important because not every component should communicate with every other component.

---

## Public and private subnets

A common cloud architecture separates public-facing and private resources.

A simplified design is:

    Internet
       |
       v
    Public Load Balancer
       |
       v
    Private Application Tier
       |
       v
    Private Database

A database generally does not need direct public internet access simply because an application needs to connect to it.

Private network placement reduces exposure, although private placement alone does not constitute complete security.

Security groups, firewalls, IAM, encryption, authentication, and application controls remain necessary.

---

## Load balancing

A load balancer distributes traffic among multiple targets.

Common algorithms include:

- Round robin
- Weighted routing
- Least connections
- Hash-based routing

Health checks are essential because a load balancer should avoid sending traffic to unhealthy targets.

The Python implementation demonstrates round-robin routing and removal of an unhealthy backend from the effective target pool.

Load balancing contributes to:

- Availability
- Horizontal scaling
- Traffic distribution
- Failure isolation
- Deployment strategies

---

## DNS

DNS translates names into network destinations.

Common record types include:

- A
- AAAA
- CNAME
- MX
- TXT

TTL determines how long a DNS response can be cached.

DNS architecture becomes particularly important in systems involving:

- Multiple regions
- Global traffic routing
- Failover
- CDN services
- Domain verification
- Service discovery

DNS caching also means that configuration changes may not become visible everywhere immediately.

---

## Storage architecture

Cloud storage is commonly discussed in three broad categories.

### Block storage

Block storage provides virtual disk-like storage.

It is commonly attached to compute resources and is appropriate for operating-system disks and workloads requiring block-level access.

### File storage

File storage provides filesystem semantics and can be shared across multiple compute resources.

### Object storage

Object storage stores objects identified by keys.

It is commonly used for:

- Images
- Videos
- Documents
- Backups
- Logs
- Static assets
- Data-lake files

Object storage should not automatically be treated as a normal filesystem. Its access model and consistency behavior depend on the service.

---

## Durability and availability

Durability and availability are distinct properties.

Durability asks whether data is likely to survive storage failures.

Availability asks whether the service can be accessed when required.

A system can have highly durable data while temporarily being unable to serve that data.

Conversely, a highly available service can still have poor data protection if its storage architecture is inadequate.

Architectural requirements should explicitly define both.

---

## Database architecture

Database selection should be based on workload requirements.

Relational databases are commonly appropriate when applications need:

- Structured schemas
- Relationships
- Transactions
- Constraints
- Complex queries

NoSQL databases cover several models, including:

- Key-value
- Document
- Wide-column
- Graph

Important database design considerations include:

- Query patterns
- Transaction requirements
- Consistency
- Replication
- Partitioning
- Indexing
- Backup
- Recovery
- Connection management
- Capacity

The database should be selected after understanding how the application reads and writes data.

---

## Database indexing

An index creates an additional access path to data.

Indexes can greatly improve read performance for suitable query patterns.

Indexes also have costs:

- Storage consumption
- Additional write work
- Maintenance
- Memory consumption
- Possible poor effectiveness for low-selectivity fields

Indexes should be designed around actual queries rather than added indiscriminately.

---

## Database replication

Replication maintains multiple copies of data.

A primary-replica model commonly uses:

    Primary
      |
      +-- Replica A
      +-- Replica B

Replication can improve:

- Read scalability
- Availability
- Disaster recovery

It can also introduce:

- Replica lag
- Consistency challenges
- Replication failures
- Additional operational complexity

Synchronous replication generally provides stronger coordination at the cost of latency and availability trade-offs.

Asynchronous replication can reduce write latency but allows replicas to temporarily contain older data.

---

## Caching

A cache stores frequently accessed information closer to the application or user.

Caching can reduce:

- Database load
- Network latency
- Repeated computation
- Origin traffic

Important caching concepts include:

- Cache hit
- Cache miss
- TTL
- Eviction
- Invalidation
- Stale data
- Cache-aside
- Write-through
- Write-back

Cache invalidation is one of the most difficult aspects of caching because cached information can become outdated when the underlying source changes.

---

## Cache-aside pattern

The cache-aside pattern follows this general process:

    1. Check cache.
    2. If found, return cached value.
    3. If absent, query the database.
    4. Store the result in cache.
    5. Return the result.

This approach is relatively simple and widely applicable.

Its primary challenge is maintaining acceptable freshness.

A cache should not be used where stale data would violate an important business or safety requirement unless the consistency model explicitly supports it.

---

## Content delivery networks

A CDN distributes content through edge locations.

A simplified request path is:

    User
      |
      v
    Edge location
      |
      +-- Cache hit -> response
      |
      +-- Cache miss -> origin

CDNs are particularly useful for:

- Images
- JavaScript
- CSS
- Videos
- Static pages
- Downloadable assets

They can reduce latency for geographically distributed users and decrease load on origin infrastructure.

---

## API gateways

An API gateway provides a controlled entry point to application APIs.

Common gateway responsibilities include:

- Authentication
- Authorization
- Rate limiting
- Request routing
- TLS termination
- Request transformation
- Logging
- Metrics
- API versioning

A gateway should not automatically become the location for all business logic. Excessive logic at the gateway can create a tightly coupled central component.

---

## Queues and asynchronous processing

Message queues decouple producers from consumers.

Synchronous processing may look like:

    Client
      |
      v
    API
      |
      v
    Worker
      |
      v
    Database
      |
      v
    Response

Asynchronous processing can look like:

    Client
      |
      v
    API
      |
      v
    Queue
      |
      v
    Worker
      |
      v
    Database

Asynchronous architecture is useful for long-running or non-critical immediate work.

Benefits include:

- Decoupling
- Traffic smoothing
- Independent scaling
- Retry support
- Better handling of workload spikes

Trade-offs include:

- Eventual consistency
- Duplicate messages
- Ordering problems
- Queue monitoring
- Retry management

---

## Retries and exponential backoff

Retries can help recover from transient failures such as:

- Network timeouts
- Temporary service failures
- Rate limits
- Short-lived overload

Retries should be bounded.

Uncontrolled retries can create a retry storm in which many clients repeatedly call an already overloaded dependency.

Exponential backoff increases the delay between attempts.

Jitter introduces randomness so that many clients do not retry at exactly the same time.

A robust retry policy should consider:

- Maximum attempts
- Maximum total delay
- Backoff
- Jitter
- Error classification
- Idempotency

---

## Dead-letter queues

Messages that repeatedly fail processing can be moved to a dead-letter queue.

A dead-letter queue provides a location for:

- Investigation
- Manual recovery
- Reprocessing
- Monitoring

It should not become a permanent dumping ground. Persistent dead-letter messages generally indicate an application, data, dependency, or schema problem.

---

## Idempotency

An operation is idempotent when repeating the same operation produces the same intended final state.

For example:

    Set status = ACTIVE

can be repeated without changing the final state after the first successful operation.

An operation such as:

    Add ₹100

is not naturally idempotent because repeating it creates another financial effect.

Idempotency keys are especially important for:

- Payments
- Order creation
- Resource provisioning
- External API operations

The Python script demonstrates an idempotency-key-based order service.

---

## Event-driven architecture

An event represents something that happened.

Examples include:

- OrderCreated
- PaymentCompleted
- UserRegistered
- FileUploaded

A producer publishes an event and multiple consumers can react to it.

Example:

    Order Service
         |
         v
    OrderCreated
       / | \
      /  |  \
     v   v   v
    Billing
    Shipping
    Analytics

Event-driven architecture reduces direct coupling but introduces asynchronous behavior and eventual consistency.

Consumers should generally be designed to tolerate:

- Duplicate events
- Delayed events
- Out-of-order events
- Consumer failures

---

## Monolithic architecture

A monolith packages multiple capabilities into one deployable application.

Advantages include:

- Simple deployment
- Lower operational complexity
- Straightforward local development
- Easier in-process communication
- Easier transactional boundaries

Disadvantages can include:

- Larger deployment units
- Coarse-grained scaling
- Strong internal coupling
- Larger blast radius for some failures

A well-designed monolith can be an effective architecture.

---

## Microservices architecture

Microservices divide an application into independently deployable services.

A service should generally have a clear business responsibility.

For example:

    User Service
    Order Service
    Payment Service
    Inventory Service

Potential benefits include:

- Independent deployment
- Independent scaling
- Clear ownership boundaries
- Failure isolation in selected cases

Potential costs include:

- Network failures
- Distributed tracing
- Data consistency
- Service discovery
- Deployment coordination
- Increased monitoring requirements
- More operational overhead

Microservices should be justified by requirements such as organizational boundaries, independent scaling, independent deployment, or domain separation.

They should not be introduced merely because they are popular.

---

## Service discovery

Cloud workloads can change addresses as instances are created, removed, or replaced.

Service discovery provides a logical mapping such as:

    payment-service
          |
          +-- instance A
          +-- instance B
          +-- instance C

Consumers use the service identity rather than relying on permanently hard-coded machine addresses.

Service discovery is useful in dynamic container and distributed environments.

---

## Containers and orchestration

Containers package applications and their dependencies.

An orchestrator manages many containers and may provide:

- Scheduling
- Restarting failed workloads
- Service discovery
- Scaling
- Health checks
- Rolling deployments
- Resource constraints

A simplified model is:

    Cluster
       |
       +-- Node
       |    +-- Workload
       |    +-- Workload
       |
       +-- Node
            +-- Workload
            +-- Workload

The Python script models nodes, workloads, CPU requests, memory requests, and scheduling.

A production orchestrator also has substantially more functionality, including networking, security policies, storage integration, workload controllers, and rollout mechanisms.

---

## Serverless architecture

Serverless abstracts much of the infrastructure management from application developers.

Typical characteristics include:

- Event-driven execution
- Automatic scaling
- Short-lived processes
- Usage-based billing
- Managed infrastructure

Serverless is not automatically cheaper or faster.

Architects must consider:

- Invocation frequency
- Execution duration
- Startup latency
- Dependency size
- Network access
- Observability
- Vendor-specific limits
- State management

---

## Identity and access management

Identity and Access Management, or IAM, controls who or what can access resources.

Authentication asks:

    Who are you?

Authorization asks:

    What are you allowed to do?

A permission can be represented conceptually as:

    Principal + Resource + Action

For example:

    order-service
    orders
    read

The Python script demonstrates permissions, principals, and role-based access control.

---

## Least privilege

Least privilege means granting only the permissions required to perform a task.

A service that only reads orders should not automatically have permission to:

- Delete orders
- Modify infrastructure
- Access unrelated databases
- Change identity policies

Least privilege reduces the potential impact of compromised identities.

Permissions should be reviewed periodically because requirements and application architecture change over time.

---

## Role-based access control

RBAC assigns permissions to roles.

For example:

    Analyst
        -> Read reports

    Developer
        -> Deploy development applications

    Administrator
        -> Infrastructure administration

Users receive roles rather than individual permissions.

RBAC simplifies administration but can become difficult to manage when roles become too broad or too numerous.

---

## Encryption

Encryption transforms data into a form that requires an appropriate key to recover.

Two important states are:

### Encryption at rest

Protects stored data such as:

- Database storage
- Object storage
- Disk volumes
- Backups

### Encryption in transit

Protects information moving between systems, commonly through TLS.

The script also distinguishes hashing and encoding from encryption.

Hashing is designed as a one-way transformation.

Base64 is an encoding mechanism, not a security mechanism.

---

## Secrets management

Secrets include:

- Passwords
- API keys
- Database credentials
- Private keys
- Tokens

Secrets should not normally be embedded directly in source code or committed to version control.

A production architecture should use a dedicated secret-management mechanism with:

- Access controls
- Encryption
- Auditing
- Rotation
- Limited retrieval permissions

Secret exposure is often caused by operational mistakes rather than sophisticated attacks, so secure defaults and automated controls are important.

---

## Zero-trust architecture

Zero trust rejects the assumption that network location alone establishes trust.

Core ideas include:

- Verify identity
- Apply least privilege
- Validate access requests
- Segment resources
- Monitor activity
- Assume compromise is possible

Traditional perimeter thinking may treat internal networks as trusted.

A zero-trust model treats access as something that must be explicitly justified and controlled.

---

## Network segmentation

Segmentation separates application tiers and limits communication.

A typical model is:

    Internet
       |
       v
    Web tier
       |
       v
    Application tier
       |
       v
    Database tier

The database may allow connections only from the application tier.

Segmentation reduces attack surface and limits lateral movement after a compromise.

---

## High availability

High availability attempts to reduce service interruption.

Common mechanisms include:

- Multiple instances
- Multiple availability zones
- Health checks
- Automatic failover
- Replication
- Load balancing
- Redundant dependencies

Availability must be considered end-to-end.

Three healthy application servers do not eliminate a single database failure point if all three depend on one database instance.

---

## Availability mathematics

Availability is commonly represented as:

    Availability = Uptime / Total Time

Downtime is:

    Downtime = 1 - Availability

Illustrative monthly downtime for a 30-day month is approximately:

| Availability | Approximate downtime |
|---|---:|
| 99.0% | 7.2 hours |
| 99.9% | 43.2 minutes |
| 99.99% | 4.32 minutes |
| 99.999% | 0.432 minutes |

Actual service-level agreements can use different measurement periods, exclusions, and definitions.

---

## SLI, SLO, and SLA

### SLI

A Service Level Indicator is a measured quantity.

For example:

    Successful requests / Total requests

### SLO

A Service Level Objective is a target.

For example:

    99.9% successful requests

### SLA

A Service Level Agreement is a formal commitment, often involving contractual consequences.

These terms should not be treated as interchangeable.

---

## Error budgets

An error budget represents the amount of unreliability permitted by an SLO.

For a 99.9% availability target:

    Error budget = 1 - 0.999
                 = 0.001
                 = 0.1%

Error budgets provide a way to balance reliability and delivery speed.

If a service is consuming its error budget rapidly, engineering decisions may need to prioritize reliability work.

---

## Disaster recovery

Disaster recovery addresses major disruptions.

Important concepts include:

### Recovery Time Objective

RTO specifies the maximum acceptable recovery time.

Example:

    RTO = 60 minutes

### Recovery Point Objective

RPO specifies the maximum acceptable amount of data loss measured in time.

Example:

    RPO = 15 minutes

A system with an RPO of 15 minutes needs an appropriate data-protection strategy capable of meeting that requirement.

---

## Disaster recovery strategies

Common approaches include:

### Backup and restore

The system is rebuilt or restored from backups.

This is generally less expensive but may have longer recovery times.

### Pilot light

A minimal version of critical infrastructure is maintained and expanded during recovery.

### Warm standby

A partially or fully functioning secondary environment is maintained and can be scaled during failover.

### Hot standby

A secondary environment is maintained at substantial capacity and can become active quickly.

### Active-active

Multiple environments actively serve traffic.

Recovery speed generally increases as redundancy and operational cost increase, although the exact relationship depends on architecture.

---

## Backup architecture

A backup strategy should define:

- Frequency
- Retention
- Encryption
- Geographic separation
- Access control
- Immutability
- Restore procedures
- Restore testing

A backup that has never been restored successfully should not be treated as proven recoverability.

The commonly known 3-2-1 approach calls for three copies, two different storage types or media, and one off-site copy.

Modern architectures may add immutable and logically isolated backup copies to protect against destructive attacks and accidental deletion.

---

## Observability

Observability provides insight into system behavior.

Three common pillars are:

### Logs

Logs record events.

Useful structured fields include:

- Timestamp
- Service
- Request ID
- Operation
- Status
- Duration
- Error information

Sensitive information should not be unnecessarily logged.

### Metrics

Metrics are numerical measurements.

Examples:

- Request rate
- Error rate
- CPU utilization
- Memory utilization
- Queue depth
- Database connections
- Latency

### Traces

Distributed traces follow requests across multiple services.

A trace may contain spans for:

    API Gateway
    Order Service
    Database
    Payment Service

A trace ID connects the spans.

Tracing is particularly useful when latency is distributed across multiple services.

---

## Structured logging

Structured logs represent information as fields rather than relying entirely on free-form text.

A conceptual record might contain:

    timestamp
    level
    service
    message
    request_id
    operation
    duration_ms

Structured logs make filtering, searching, aggregation, and automated analysis easier.

Logs should avoid exposing:

- Passwords
- Authentication tokens
- Private keys
- Payment credentials
- Unnecessary personal information

---

## Performance architecture

Performance involves several different dimensions.

### Latency

Time required to complete an operation.

### Throughput

Amount of work completed per unit of time.

### Concurrency

Number of operations being processed simultaneously.

### Saturation

How close a resource is to its capacity.

Common performance techniques include:

- Caching
- Indexing
- Query optimization
- Connection pooling
- Batching
- Compression
- Asynchronous processing
- Horizontal scaling
- CDN usage

Optimization should begin with measurement and bottleneck identification rather than assumptions.

---

## Percentiles and tail latency

Average latency can hide slow requests.

For example, most requests might complete quickly while a small number take several seconds.

Percentiles provide a better view of tail behavior.

Common measurements include:

- P50
- P90
- P95
- P99

P95 latency means that approximately 95% of measured requests are at or below that latency value under the defined measurement methodology.

Tail latency is particularly important in distributed systems because a slow dependency can affect end-to-end user experience.

---

## Connection pooling

Database connections have setup and resource costs.

Connection pooling maintains reusable connections.

Benefits include:

- Lower connection setup overhead
- Controlled database connection counts
- Better resource utilization

A pool that is too small causes application requests to wait.

A pool that is too large can overwhelm the database.

Pool sizing must therefore consider:

- Application concurrency
- Database capacity
- Query duration
- Number of application instances
- Connection limits

---

## CAP theorem

CAP theorem concerns distributed systems under network partition.

The three properties are:

- Consistency
- Availability
- Partition tolerance

Under a network partition, a distributed system cannot guarantee both full consistency and full availability simultaneously according to the formal CAP model.

Partition tolerance is generally considered necessary for distributed systems operating over networks because partitions can occur.

CAP should not be confused with ACID database transactions.

---

## Consistency models

Different systems can offer different consistency guarantees.

### Strong consistency

Reads observe the latest successful write according to the system's consistency contract.

### Eventual consistency

Replicas may temporarily differ but converge when updates stop and the system functions normally.

### Read-after-write consistency

A client can observe its own recent write.

### Causal consistency

Causally related operations maintain their causal ordering.

The appropriate consistency model depends on the application.

A social feed may tolerate some eventual consistency.

A financial transaction may require much stronger consistency guarantees.

---

## Timeouts

Every distributed dependency should generally have an explicit timeout.

Without timeouts, an application can wait indefinitely for a dependency.

A request may pass through:

    Client
      |
      v
    Gateway
      |
      v
    Service
      |
      v
    Database

Timeout budgets should be coordinated across these layers.

A downstream timeout longer than the entire upstream request budget may provide little practical value.

---

## Circuit breaker pattern

A circuit breaker protects a system from repeatedly calling an unhealthy dependency.

Typical states are:

### Closed

Requests are allowed.

### Open

Requests are blocked temporarily.

### Half-open

A limited number of requests are used to determine whether the dependency has recovered.

Circuit breakers help reduce cascading failures.

---

## Bulkhead pattern

The bulkhead pattern isolates resource pools.

For example:

    Payment workers
    Email workers
    Reporting workers

If reporting consumes all available resources, payment processing can remain protected if it has a separate pool.

The goal is to reduce the blast radius of overload or failure.

---

## Rate limiting

Rate limiting controls how much traffic a client or workload can generate.

Common algorithms include:

- Fixed window
- Sliding window
- Token bucket
- Leaky bucket

Rate limiting protects:

- APIs
- Databases
- Authentication endpoints
- Expensive operations
- Shared infrastructure

The token-bucket example demonstrates capacity and token refill behavior.

Rate limiting can also provide fairness among clients.

---

## Backpressure

Backpressure occurs when producers generate work faster than consumers can process it.

For example:

    Producer = 1000 messages/sec
    Consumer = 500 messages/sec

The queue grows by approximately:

    500 messages/sec

If this continues, the queue can eventually exhaust available resources or create unacceptable processing delays.

Possible responses include:

- Scaling consumers
- Rate limiting producers
- Batching
- Dropping non-critical work
- Increasing processing capacity
- Admission control

---

## Admission control

Admission control prevents a system from accepting more work than it can safely process.

Instead of allowing unlimited requests to consume resources, the system can reject or defer work.

Typical responses include:

- HTTP 429 for rate limiting
- HTTP 503 for temporary service unavailability

Controlled rejection is often safer than allowing the system to exhaust memory, connections, threads, or other finite resources.

---

## Fault tolerance

Fault tolerance allows a system to continue operating despite failures.

Techniques include:

- Redundancy
- Replication
- Failover
- Retries
- Circuit breakers
- Bulkheads
- Queues
- Graceful degradation

Graceful degradation means that optional functionality can fail without bringing down the core business operation.

For example, if a recommendation service is unavailable, an e-commerce checkout may still operate without recommendations.

---

## Infrastructure as Code

Infrastructure as Code represents infrastructure configuration in a repeatable form.

Infrastructure resources can include:

- Networks
- Subnets
- Security groups
- Databases
- Compute resources
- Load balancers
- Storage

Important benefits include:

- Repeatability
- Version control
- Review
- Automation
- Consistency
- Reproducibility

Infrastructure configuration should be treated as an engineering artifact.

Secrets should not be embedded directly into infrastructure definitions.

---

## Immutable infrastructure

Immutable infrastructure treats deployed infrastructure as replaceable.

Instead of manually modifying an existing server:

    Existing server
        |
        v
    Manual changes

a new version is built and deployed:

    New artifact
        |
        v
    New instances
        |
        v
    Validation
        |
        v
    Old instances removed

This reduces configuration drift and improves reproducibility.

---

## Deployment strategies

### Blue-green deployment

Two environments exist:

    Blue = current version
    Green = new version

Traffic is switched after the new environment is validated.

A major benefit is relatively simple rollback.

The primary cost is temporarily operating two environments.

### Canary deployment

Only a small percentage of traffic is sent to the new version initially.

Example:

    95% -> old version
     5% -> new version

If the new version remains healthy, traffic can gradually increase.

Canary deployment reduces blast radius but requires good observability and traffic control.

### Rolling deployment

Instances are replaced gradually.

For four instances:

    3 old + 1 new
    2 old + 2 new
    1 old + 3 new
    0 old + 4 new

The deployment must preserve sufficient healthy capacity throughout the process.

---

## Database migrations and deployments

Application deployments can fail when database schema changes are incompatible with old or new application versions.

An expand-and-contract strategy helps:

### Expand

Add new schema elements while preserving compatibility with the old application.

### Migrate

Deploy the new application and migrate data where required.

### Contract

Remove obsolete schema elements after old application versions are no longer active.

This pattern is particularly useful for rolling and canary deployments.

---

## Multi-region architecture

Multi-region systems deploy workloads in geographically separate regions.

### Active-passive

One region handles traffic while another is prepared for recovery.

### Active-active

Multiple regions actively serve users.

Active-active can improve resilience and global latency but makes data synchronization and consistency more difficult.

Architects must consider:

- Routing
- Replication
- Failover
- Data residency
- Cross-region traffic
- Operational complexity
- Cost

---

## Cost architecture

Cloud cost commonly comes from:

- Compute
- Databases
- Storage
- Network transfer
- Requests
- Data processing
- Logging
- Monitoring

Cost optimization techniques include:

- Right-sizing
- Autoscaling
- Removing unused resources
- Storage lifecycle management
- Efficient data transfer
- Capacity commitments where appropriate
- Resource tagging
- Cost allocation
- Architecture optimization

The cheapest individual service is not necessarily the lowest-total-cost architecture.

Operational complexity, engineering time, outages, and performance limitations can all create indirect costs.

---

## Cost-performance-reliability trade-offs

Architecture is a multi-dimensional optimization problem.

Typical trade-offs include:

| Decision | Potential benefit | Potential cost |
|---|---|---|
| Multi-zone deployment | Higher availability | Higher infrastructure cost |
| Multi-region deployment | Geographic resilience | Higher complexity and cost |
| Caching | Lower latency | Staleness and invalidation complexity |
| Microservices | Independent scaling | Distributed-system complexity |
| Serverless | Reduced infrastructure management | Runtime constraints and platform coupling |
| Strong consistency | Easier correctness for some workloads | Latency or availability trade-offs |
| More replicas | Better redundancy | More resource consumption |

Good architecture makes these trade-offs explicit.

---

## Cloud-native application principles

Cloud-native applications commonly benefit from:

- Externalized configuration
- Explicit dependencies
- Stateless processes
- Disposable instances
- Health checks
- Graceful shutdown
- Automated deployment
- Environment consistency
- Horizontal scaling
- Centralized observability

The purpose is to make applications suitable for dynamic infrastructure where instances can be replaced, moved, scaled, or terminated.

---

## Health checks

Health checks allow infrastructure to determine whether a workload should receive traffic.

Two important concepts are:

### Liveness

Determines whether the process is alive.

### Readiness

Determines whether the process is prepared to receive traffic.

An application can be alive but not ready.

For example:

    Process running
    Database unavailable

The process may technically be alive, but routing traffic to it may produce failures.

---

## Graceful shutdown

Cloud workloads can be terminated during:

- Scaling
- Deployment
- Failure recovery
- Maintenance

Graceful shutdown should allow an application to:

- Stop accepting new work
- Finish appropriate in-progress work
- Close connections
- Flush important state
- Release resources

Applications should not assume that a process will run indefinitely.

---

## Partitioning and sharding

Partitioning divides data into smaller logical pieces.

Sharding distributes those partitions across multiple nodes.

A shard key might be:

- Customer ID
- Tenant ID
- Account ID
- Geographic region

A good shard key should:

- Distribute load reasonably evenly
- Match important access patterns
- Avoid hot partitions
- Support the application's query model

Changing a shard key later can be difficult, so it should be selected carefully.

---

## Consistent hashing

Consistent hashing is commonly useful in distributed caches and routing systems.

The purpose is to reduce the number of keys that need to move when nodes are added or removed.

A hash ring can conceptually be represented as:

    0 -------------------------------------- MAX
       |        |          |          |
     Node A   Node B      Node C      Node D

A key is mapped to a position and associated with a node according to the ring's routing rules.

The Python implementation provides a simplified demonstration of this concept.

---

## Message ordering

Distributed messaging systems can provide different ordering guarantees.

Possible guarantees include:

- No ordering
- Ordering within a partition
- Ordering per key
- Global ordering

Global ordering can limit scalability.

A common design is to preserve ordering for events associated with the same business entity while allowing unrelated entities to process independently.

---

## Message delivery semantics

Three common conceptual delivery models are:

### At-most-once

A message may be lost but is not intentionally retried.

### At-least-once

A message may be delivered more than once.

### Exactly-once

The system provides guarantees intended to make the resulting effect occur once under its defined model.

At-least-once delivery is common because it is practical and resilient.

Consumers should therefore often be idempotent.

---

## Distributed transactions and the Saga pattern

Distributed transactions across independent services are difficult because each service controls its own local state.

The Saga pattern divides a business transaction into local transactions.

Example:

    Create order
        |
        v
    Reserve inventory
        |
        v
    Charge payment
        |
        v
    Confirm order

If payment fails:

    Release inventory
        |
        v
    Cancel order

The compensating action is a business operation that counteracts the earlier operation.

A compensation is not necessarily equivalent to a database rollback.

---

## CQRS

CQRS stands for Command Query Responsibility Segregation.

It separates:

- Commands that modify state
- Queries that read state

This can be useful when read and write workloads have substantially different requirements.

CQRS does not inherently require two databases.

A simple implementation can maintain a shared state model while exposing separate command and query responsibilities.

More advanced implementations may use separate read models.

---

## Event sourcing

Event sourcing stores state changes as an append-only sequence of events.

Instead of storing only:

    balance = 900

the system may store events such as:

    AccountOpened
    Deposited 1000
    Withdrawn 100

The current state can be reconstructed by replaying the events.

Potential benefits include:

- Audit history
- Historical reconstruction
- Event-driven integration

Potential challenges include:

- Event schema evolution
- Large event histories
- Replay time
- Storage growth
- Operational complexity

Event sourcing should be adopted only when its benefits justify its complexity.

---

## Data lakes and warehouses

A data lake commonly stores large volumes of raw or semi-structured information.

A data warehouse is generally optimized for structured analytical queries.

A simplified analytical architecture is:

    Applications
        |
        v
    Data Lake
        |
        v
    Transformation
        |
        v
    Data Warehouse
        |
        v
    Analytics

The boundary between these systems can vary depending on the platform and organizational architecture.

---

## Data governance

Cloud architecture must address the complete data lifecycle.

Important concerns include:

- Data ownership
- Classification
- Access control
- Encryption
- Retention
- Deletion
- Backup
- Auditability
- Data residency
- Regulatory requirements

Possible classification levels include:

- Public
- Internal
- Confidential
- Restricted

More sensitive data generally requires stronger controls.

---

## Multi-tenancy

Multi-tenancy means a single application serves multiple customers or tenants.

Common models include:

### Shared database and shared tables

All tenants use the same tables with tenant identifiers.

Advantages include efficiency.

The main risk is cross-tenant data leakage caused by incorrect authorization or filtering.

### Shared database and separate schemas

Tenants receive separate schemas.

This provides stronger logical separation but increases management complexity.

### Separate database per tenant

Each tenant has a separate database.

This can provide stronger isolation but increases operational overhead.

### Separate infrastructure per tenant

Each tenant receives dedicated infrastructure.

This provides strong isolation but can be expensive and operationally complex.

---

## Tenant isolation

Tenant identifiers must be treated as security boundaries.

A query such as:

    SELECT records WHERE tenant_id = current_tenant

must not rely solely on user-provided values.

Authorization must establish which tenant the authenticated identity is allowed to access.

Cross-tenant access is a serious security concern in multi-tenant systems.

---

## API versioning

APIs evolve over time.

Common approaches include:

- URL versioning
- Header-based versioning
- Query-parameter versioning

Important concerns include:

- Backward compatibility
- Deprecation
- Migration
- Client support
- Documentation
- Contract testing

Versioning should be combined with a clear compatibility policy.

---

## Threat modeling

Threat modeling identifies how a system could be attacked or misused.

Important questions include:

- What assets require protection?
- Who are the actors?
- Where are trust boundaries?
- What could go wrong?
- What controls reduce risk?

The script introduces the STRIDE categories:

- Spoofing
- Tampering
- Repudiation
- Information disclosure
- Denial of service
- Elevation of privilege

Threat modeling should be performed during architecture design rather than only after implementation.

---

## Input validation

Cloud APIs receive untrusted input.

Validation should address:

- Type
- Length
- Range
- Schema
- Format
- Allowed values

For example, an order quantity can be constrained to a valid integer range.

Input validation should be combined with other security mechanisms such as:

- Authentication
- Authorization
- Parameterized database queries
- Output encoding
- Rate limiting

Validation alone is not a complete security solution.

---

## Secure defaults

Secure-by-default configuration reduces accidental exposure.

Examples include:

- Private databases by default
- Private object storage by default
- Encryption enabled by default
- Audit logging enabled
- Least-privilege access
- Restricted administrative interfaces

Security should not depend entirely on every individual engineer remembering every configuration requirement manually.

Automation and safe defaults reduce human error.

---

## Graceful degradation

Graceful degradation allows critical functionality to continue when optional dependencies fail.

For example:

    Recommendation service unavailable
            |
            v
    Hide recommendations
            |
            v
    Continue checkout

This differs from simply ignoring failures.

The system should explicitly identify which capabilities are critical and which can be temporarily unavailable.

---

## Production architecture

A production system should have explicit answers for:

### Architecture

- What are the major components?
- What are their dependencies?
- What are the failure domains?
- Where are the single points of failure?

### Security

- Who can access each resource?
- Are secrets protected?
- Is encryption enabled?
- Is the network segmented?
- Are security events logged?

### Reliability

- What happens when an instance fails?
- What happens when an availability zone fails?
- What happens when a database fails?
- What happens when a dependency becomes slow?

### Operations

- Are logs available?
- Are metrics available?
- Are traces available?
- Are alerts meaningful?
- Can engineers diagnose failures?

### Deployment

- Can changes be deployed safely?
- Can the previous version be restored?
- Are database migrations compatible?

### Performance

- What is the expected workload?
- What are latency objectives?
- What is the bottleneck?
- How does the system behave during spikes?

### Cost

- What are the major cost drivers?
- Which resources can scale down?
- Are unused resources removed?
- Is spending visible to the appropriate owners?

### Recovery

- What is the RTO?
- What is the RPO?
- Have backups been restored?
- Has failover been tested?

---

## Failure injection

Architecture should be tested against failures rather than relying solely on diagrams and assumptions.

Useful scenarios include:

- Instance termination
- Availability-zone failure
- Region failure
- Database unavailability
- Network latency
- Network partition
- Queue backlog
- Dependency timeout
- Expired credentials
- Invalid configuration
- Storage exhaustion

Failure testing validates whether redundancy and recovery mechanisms actually work.

---

## Testing cloud architecture

Different testing layers answer different questions.

### Unit testing

Tests individual functions and components.

### Integration testing

Tests communication between components.

### Contract testing

Checks that service interfaces remain compatible.

### Load testing

Tests expected and peak workloads.

### Stress testing

Pushes a system beyond normal capacity to understand its behavior.

### Resilience testing

Introduces controlled failures to validate recovery behavior.

### Security testing

Tests authentication, authorization, configuration, and security controls.

### Disaster recovery testing

Validates the ability to restore applications and data.

A production architecture requires more than unit tests.

---

## Architecture decision records

Architecture Decision Records document important technical choices.

A useful ADR contains:

- Decision title
- Context
- Decision
- Alternatives
- Consequences

For example, an architecture may choose asynchronous image processing because image processing is long-running and should not block an HTTP request.

The decision should also document the resulting trade-offs, such as the need for job tracking and eventual completion.

ADR documentation preserves architectural reasoning, not merely the final technology choice.

---

## Reference three-tier architecture

A common cloud web architecture is:

    Users
      |
      v
    DNS
      |
      v
    CDN / Load Balancer
      |
      v
    Application Tier
      |
      +----> Cache
      |
      +----> Queue
      |
      +----> Database
      |
      +----> Object Storage

Supporting capabilities include:

    IAM
    Encryption
    Secrets
    Monitoring
    Logging
    Tracing
    Backup
    Disaster Recovery
    Infrastructure as Code
    Deployment automation

The exact components depend on the application.

---

## Highly available web architecture

A resilient architecture may distribute application resources across availability zones:

    Internet
       |
       v
    DNS / CDN
       |
       v
    Load Balancer
       |
       +----------------+
       |                |
       v                v
    Zone A            Zone B
       |                |
    App A1            App B1
    App A2            App B2
       |                |
       +-------+--------+
               |
             Cache
               |
               v
          Multi-zone DB
               |
               v
          Object Storage
               |
               v
            Backups

The design reduces dependence on a single application instance or zone.

It does not automatically eliminate every single point of failure. Each dependency must be examined independently.

---

## Architecture design process

A systematic architecture process can follow these stages:

1. Define business requirements.
2. Define functional requirements.
3. Define non-functional requirements.
4. Identify users and workloads.
5. Estimate traffic and data volume.
6. Identify security requirements.
7. Define availability requirements.
8. Define RTO and RPO.
9. Select an architecture style.
10. Design networking.
11. Design compute.
12. Design storage and databases.
13. Design application communication.
14. Design security controls.
15. Design observability.
16. Design deployment and rollback.
17. Model failure scenarios.
18. Estimate cost.
19. Document major decisions.
20. Test the architecture.

This process prevents technology selection from becoming the starting point before the actual requirements are understood.

---

## Requirements-to-architecture mapping

Non-functional requirements directly influence architecture.

| Requirement | Architectural implication |
|---|---|
| High availability | Redundancy and failure-domain distribution |
| Low latency | Caching, optimized queries, edge delivery |
| High traffic growth | Horizontal scaling and elasticity |
| Low RTO | Standby or redundant recovery infrastructure |
| Low RPO | Frequent backups or replication |
| Strong security | IAM, segmentation, encryption, auditing |
| High auditability | Structured logs and immutable records |
| Low operating cost | Right-sizing, autoscaling, lifecycle policies |
| Global users | CDN and potentially multi-region architecture |

Architecture should therefore be traceable back to requirements.

---

## Security considerations

Security should be designed as a set of layers.

A useful conceptual model is:

    Identity
       |
    Network
       |
    Application
       |
    Data
       |
    Monitoring

Important controls include:

- Strong authentication
- Least privilege
- Role-based access
- Private networking
- Encryption
- Secret management
- Input validation
- Rate limiting
- Network segmentation
- Audit logging
- Security monitoring
- Backup protection

Security should assume that individual components can eventually be compromised.

---

## Performance considerations

Performance architecture should consider the complete request path:

    Client
      |
      v
    Edge
      |
      v
    Gateway
      |
      v
    Application
      |
      +----> Cache
      |
      +----> Database
      |
      +----> External service

Latency can accumulate across these layers.

A database query that takes 100 ms may appear acceptable in isolation but become problematic if a request performs several sequential calls.

Parallelism, caching, batching, asynchronous processing, query optimization, and efficient network paths can reduce end-to-end latency.

---

## Reliability considerations

Reliability requires explicit handling of partial failure.

In distributed systems, one component can fail while others continue operating.

Examples include:

- Application healthy, database unavailable
- Gateway healthy, application unavailable
- Queue healthy, workers unavailable
- Primary database healthy, replica unhealthy
- Region A unavailable, Region B healthy

Architectures should define what happens in each important failure state.

---

## Cost considerations

Cloud architecture should model cost before production.

Major questions include:

- What resources are always running?
- What scales with traffic?
- What is the expected peak?
- What data is stored?
- How much data crosses regions?
- How much logging is generated?
- Which managed services incur request-based costs?
- Which resources can be shut down outside working hours?

Cost optimization should not compromise requirements such as security, reliability, or regulatory compliance.

---

## Implementation considerations

The Python script uses standard-library implementations to demonstrate architectural mechanisms.

These implementations are educational models rather than replacements for production cloud services.

For example:

- The load balancer is a simplified routing simulation.
- The object store is an in-memory representation.
- The cache is a basic TTL cache.
- The queue is an in-memory message queue.
- The service registry is a simple dictionary-based registry.
- The circuit breaker is a conceptual implementation.
- The scheduler models basic resource placement.

Real cloud platforms provide significantly more sophisticated implementations involving distributed state, fault tolerance, persistence, security, monitoring, and operational controls.

---

## Common mistakes

### Exposing databases publicly

A database usually does not need direct internet exposure.

### Hard-coding secrets

Credentials should not be committed to application source code.

### Treating retries as harmless

Retries can amplify outages and duplicate side effects.

### Deploying critical services in one zone

Zone failure can become service failure.

### Creating unnecessary microservices

Distributed architecture adds significant operational complexity.

### Ignoring observability

A system that cannot be diagnosed quickly is difficult to operate reliably.

### Ignoring database bottlenecks

Adding application servers does not automatically increase database capacity.

### Trusting backups without restore testing

Backup existence does not prove recoverability.

### Ignoring cost

Cloud architecture can become expensive through unused resources, network transfer, excessive logging, or inefficient workloads.

### Assuming private means secure

Private network placement is only one layer of security.

---

## Important distinctions

### Scalability versus elasticity

Scalability is the ability to handle increasing workload.

Elasticity emphasizes automatic adjustment of capacity based on demand.

### Availability versus durability

Availability concerns accessibility.

Durability concerns preservation of data.

### Authentication versus authorization

Authentication identifies the principal.

Authorization determines permitted actions.

### Encryption versus hashing

Encryption is reversible with the appropriate key.

Hashing is designed as a one-way transformation.

### Queue versus event

A queue commonly distributes work among consumers.

An event commonly represents something that happened and can be observed by multiple consumers.

### Backup versus replication

Replication provides additional live copies.

Backup provides recoverable historical copies.

Replication alone should not be assumed to protect against accidental deletion or destructive corruption.

### Monolith versus microservices

A monolith uses a larger deployable unit.

Microservices use independently deployable services.

Neither is universally superior.

### Vertical versus horizontal scaling

Vertical scaling increases the capacity of a resource.

Horizontal scaling adds resources.

---

## Edge cases

Important cloud architecture edge cases include:

- No healthy application instances
- Complete availability-zone loss
- Regional outage
- Duplicate messages
- Out-of-order events
- Delayed messages
- Stale cache data
- Database replica lag
- Network partitions
- Expired credentials
- DNS propagation and caching
- Sudden traffic spikes
- Slow dependencies
- Queue backlogs
- Memory exhaustion
- Connection exhaustion
- Disk exhaustion
- Incompatible deployments
- Partial transaction completion
- Cross-tenant authorization errors

These cases matter because distributed systems commonly fail partially rather than completely.

---

## Architectural trade-offs

There is rarely one architecture that simultaneously maximizes every desirable property.

For example:

    More redundancy
        -> higher availability
        -> higher cost

    Stronger consistency
        -> simpler correctness for some workloads
        -> possible latency or availability trade-offs

    More microservices
        -> independent scaling and deployment
        -> more distributed-system complexity

    More caching
        -> lower latency
        -> greater invalidation complexity

    Multi-region
        -> geographic resilience
        -> higher operational and data-consistency complexity

Good architecture is therefore the process of selecting acceptable trade-offs according to business requirements.

---

## End-to-end architecture perspective

The most important concept in cloud architecture is that individual components cannot be evaluated completely in isolation.

A production request may travel through:

    User
      |
      v
    DNS
      |
      v
    CDN / WAF
      |
      v
    Load Balancer
      |
      v
    Application
      |
      +------> Cache
      |
      +------> Database
      |
      +------> Queue
                   |
                   v
                 Worker
                   |
                   v
              Object Storage

Across all these components, supporting systems provide:

    Identity
    Authorization
    Encryption
    Secrets
    Monitoring
    Logging
    Tracing
    Alerting
    Backup
    Disaster Recovery
    Infrastructure Automation
    Cost Management
    Governance

A cloud architecture is therefore a system of interacting capabilities, dependencies, failure domains, security boundaries, and operational processes.

The Python script demonstrates these relationships through progressively more advanced models, from basic compute and networking through distributed systems, resilience, security, observability, deployment, disaster recovery, cost, and production-readiness considerations.
