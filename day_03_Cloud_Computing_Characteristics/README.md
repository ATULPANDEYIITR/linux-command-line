# Cloud Computing Characteristics

## Overview

Cloud computing is a model for delivering computing resources and services over a network, usually the Internet. Instead of purchasing, installing, configuring, and maintaining physical infrastructure yourself, organizations can consume computing capabilities as services from cloud providers.

The five essential characteristics of cloud computing are:

1. **On-demand self-service**
2. **Broad network access**
3. **Resource pooling**
4. **Rapid elasticity**
5. **Measured service**

These characteristics explain what makes cloud computing different from traditional IT infrastructure.

---

## 1. On-demand self-service

On-demand self-service means that a cloud consumer can provision computing resources automatically without requiring direct human interaction with the cloud service provider.

In traditional IT, obtaining a new server may require:

- Submitting a request
- Getting approval
- Purchasing hardware
- Installing hardware
- Installing an operating system
- Configuring networking
- Configuring security
- Deploying the application

Cloud computing automates much of this process.

The traditional process can look like:

User → IT Department → Approval → Procurement → Hardware → Installation → Configuration → Application

The cloud process can look like:

User → Cloud Console/API/CLI → Authentication → Authorization → Cloud Control Plane → Resource Provisioning

Cloud users can typically request resources through:

- Web consoles
- APIs
- Command-line interfaces
- SDKs
- Infrastructure-as-Code tools

For example, a developer may request:

- 4 vCPU
- 16 GB RAM
- Linux operating system
- A specific region
- A particular storage configuration

The cloud platform handles the underlying provisioning process.

### Key idea

On-demand self-service means:

> The consumer can obtain computing capabilities when needed without requiring manual intervention from the cloud provider.

---

## 2. Broad network access

Broad network access means that cloud capabilities are available over a network through standard mechanisms and can be accessed by different types of client devices.

Examples include:

- Laptops
- Desktop computers
- Smartphones
- Tablets
- Web applications
- Mobile applications
- APIs
- IoT devices
- Command-line tools

A simplified model is:

User Devices → Network → Cloud Services

Cloud services commonly use technologies such as:

- TCP/IP
- DNS
- HTTP
- HTTPS
- TLS
- REST APIs
- SDKs
- VPNs
- Private networking

Broad network access does not mean that every cloud resource is publicly accessible.

A secure architecture may look like:

Internet → Firewall → Load Balancer → Application → Private Database

The database may be accessible only from the application network and not directly from the public Internet.

### Key idea

Broad network access means:

> Cloud capabilities can be accessed through networks using standardized mechanisms and from a wide range of client platforms.

---

## 3. Resource pooling

Resource pooling means that cloud providers maintain shared pools of computing resources that can be dynamically assigned and reassigned to different customers.

Resources can include:

- CPU
- RAM
- Storage
- Network bandwidth
- GPUs
- Specialized accelerators

Instead of permanently dedicating an entire physical server to one customer, a cloud provider can use shared infrastructure to serve many customers.

Conceptually:

Cloud Infrastructure

→ CPU Pool

→ Memory Pool

→ Storage Pool

→ Network Pool

→ GPU Pool

These resources are dynamically allocated according to workload requirements.

### Example

Suppose a provider has:

- 10,000 CPU cores
- 50 TB RAM
- 10 PB storage

Different customers can consume portions of this shared infrastructure.

When one customer releases resources, those resources can potentially be allocated to another customer.

### Key idea

Resource pooling allows cloud providers to:

- Improve infrastructure utilization
- Dynamically allocate resources
- Serve multiple customers
- Reduce unused capacity
- Manage large-scale infrastructure efficiently

---

## 4. Multi-tenancy

Multi-tenancy is closely associated with resource pooling.

Multi-tenancy means that multiple customers can use shared underlying infrastructure while maintaining logical isolation between their environments.

A simplified example is:

Physical Server → Hypervisor → VM-A, VM-B, VM-C

VM-A → Customer A

VM-B → Customer B

VM-C → Customer C

Although the infrastructure is shared, customers should not be able to access each other's resources or data.

Isolation can be implemented through:

- Virtual machines
- Hypervisors
- Containers
- Network segmentation
- Identity and access management
- Encryption
- Storage isolation
- Security policies

### Important distinction

Resource pooling describes the sharing and dynamic allocation of infrastructure.

Multi-tenancy describes how multiple customers can use shared infrastructure while maintaining logical separation.

---

## 5. Virtualization and abstraction

Virtualization is one of the important technologies that can support cloud computing.

Suppose a physical server contains:

- 32 CPU cores
- 128 GB RAM

A hypervisor can divide this physical infrastructure into multiple virtual machines.

Conceptually:

Physical Server

→ Hypervisor

→ VM 1

→ VM 2

→ VM 3

→ VM 4

Each virtual machine can receive a portion of the physical resources.

The customer does not necessarily need to know which physical server is running the workload.

The customer may simply request:

- 4 vCPU
- 16 GB RAM
- Linux

The cloud provider manages:

- Physical servers
- Data centers
- Power
- Cooling
- Physical networking
- Hardware failures
- Hypervisors
- Capacity
- Resource scheduling

This is called abstraction.

### Virtualization vs cloud computing

Virtualization and cloud computing are not the same thing.

**Virtualization** is a technology that abstracts physical resources into virtual resources.

**Cloud computing** is a broader service delivery model involving characteristics such as:

- Self-service
- Network access
- Resource pooling
- Elasticity
- Measurement

Therefore:

> Virtualization can enable cloud computing, but virtualization alone does not constitute cloud computing.

---

## 6. Dynamic resource allocation

Resource pooling allows cloud platforms to allocate resources dynamically.

For example:

Customer A → 8 CPU

Customer B → 16 CPU

Customer C → 4 CPU

If Customer B releases its resources, those resources can potentially become available to other workloads.

Dynamic resource allocation helps cloud providers optimize infrastructure utilization.

---

## 7. Rapid elasticity

Rapid elasticity means that cloud capabilities can be rapidly provisioned and released according to workload demand.

Consider an online shopping platform.

Normal traffic:

1,000 requests per minute

During a flash sale:

100,000 requests per minute

After the sale:

2,000 requests per minute

A fixed infrastructure might use:

10 servers

During the flash sale, 10 servers may not be sufficient.

An elastic cloud architecture could behave like:

Normal traffic → 10 servers

Peak traffic → 100 servers

After peak → 12 servers

The infrastructure dynamically adjusts to demand.

### Key idea

Rapid elasticity allows organizations to:

- Increase capacity when demand increases
- Decrease capacity when demand decreases
- Avoid excessive manual provisioning
- Respond quickly to workload changes

---

## 8. Scalability vs elasticity

Scalability and elasticity are related but different concepts.

### Scalability

Scalability is the ability of a system to handle increasing workload by adding capacity.

### Elasticity

Elasticity is the ability to dynamically add and remove capacity according to changing workload.

For example:

10 servers → 100 servers

demonstrates scaling.

But:

10 → 100 → 20 → 50 → 10

according to workload demand demonstrates elasticity.

### Simple distinction

> Scalability is about the ability to handle growth. Elasticity is about dynamically adapting capacity to changing demand.

---

## 9. Vertical scaling

Vertical scaling means increasing or decreasing the capacity of an existing machine.

Example:

Before:

2 CPU  
8 GB RAM

After:

8 CPU  
32 GB RAM

This is also called scaling up.

### Advantages

- Simple concept
- Can improve single-node performance
- Useful for some stateful workloads
- May require fewer application instances

### Disadvantages

- Physical hardware limits exist
- Larger machines can become expensive
- May require restart or downtime depending on the platform
- Can create a single point of failure

---

## 10. Horizontal scaling

Horizontal scaling means adding or removing multiple instances.

Example:

Before:

Server 1

After:

Server 1  
Server 2  
Server 3  
Server 4

This is also called scaling out.

### Advantages

- Large scaling potential
- Better fault tolerance
- Works well with load balancing
- Supports distributed architectures
- Allows independent instance replacement

### Disadvantages

- More architectural complexity
- Distributed state becomes challenging
- Network communication increases
- Data consistency can become complicated

---

## 11. Autoscaling

Autoscaling is the automated process of increasing or decreasing infrastructure capacity according to workload conditions.

A simplified architecture is:

Application → Monitoring → Metrics → Autoscaler → Resource Change

Metrics may include:

- CPU utilization
- Memory utilization
- Requests per second
- Request latency
- Queue length
- Database connections
- Custom application metrics
- Scheduled events
- Predictive demand

A simple policy might be:

CPU > 70% → Scale up

CPU < 30% → Scale down

Real cloud autoscaling systems are much more sophisticated than this simple rule.

---

## 12. Autoscaling cooldown and hysteresis

A poorly designed autoscaler can continuously scale up and down.

For example:

Traffic increases → Scale up → Load decreases → Scale down → Load increases → Scale up

This can create instability.

Cloud systems can use:

- Cooldown periods
- Stabilization windows
- Hysteresis
- Minimum instance limits
- Maximum instance limits
- Predictive scaling

For example:

Scale up when CPU > 70%

Scale down when CPU < 30%

The gap between the two thresholds reduces unnecessary oscillation.

---

## 13. Measured service

Measured service means that cloud systems automatically measure and monitor resource consumption.

Resources that can be measured include:

- Compute time
- Storage
- Network traffic
- API requests
- Database operations
- Function invocations
- GPU usage
- Memory usage

A simplified usage record could be:

Compute = 100 hours

Storage = 500 GB

Network = 2 TB

API requests = 10 million

Measurement provides visibility into how resources are being consumed.

---

## 14. Metering vs billing

Metering and billing are related but different.

### Metering

Metering answers:

> How much did the customer consume?

### Billing

Billing answers:

> How much should the customer pay according to the applicable pricing model?

Example:

Usage = 100 compute hours

Price = $0.05 per hour

Cost = $5.00

Cloud pricing can use many different models, including:

- Per-second pricing
- Per-minute pricing
- Per-hour pricing
- Per-request pricing
- Storage-based pricing
- Data-transfer pricing
- Reserved commitments
- Subscription pricing
- Tiered pricing
- Free tiers

---

## 15. Pay-as-you-go

Measured service supports a utility-like approach to computing.

An electricity analogy is useful.

Electricity:

Consume electricity → Meter usage → Calculate bill

Cloud:

Consume computing resources → Measure usage → Apply pricing → Calculate cost

Cloud computing therefore allows organizations to consume resources without necessarily purchasing all underlying infrastructure themselves.

The exact billing model depends on the specific cloud service.

---

## 16. Resource utilization

Measured service allows organizations to analyze infrastructure utilization.

Suppose:

Capacity = 100 units

Actual usage = 20 units

Utilization:

20 / 100 = 20%

Low utilization can indicate:

- Oversized resources
- Idle infrastructure
- Poor workload placement
- Inefficient architecture

This can lead to rightsizing and cost optimization.

---

## 17. Rightsizing

Rightsizing means selecting resource configurations that appropriately match workload requirements.

For example:

Provisioned:

16 CPU  
64 GB RAM

Actual requirement:

4 CPU  
16 GB RAM

The workload may be overprovisioned.

Measured usage can help identify this mismatch.

Rightsizing can potentially reduce:

- Infrastructure waste
- Cloud spending
- Resource contention
- Unnecessary capacity

---

## 18. Resource quotas

Cloud environments can use quotas to limit resource consumption.

Example:

Customer A → Maximum 100 VMs

Customer B → Maximum 50 VMs

Quotas can be applied to:

- Compute instances
- CPUs
- Storage
- GPUs
- API requests
- Network resources

Organizations can also use:

- Budgets
- Spending limits
- Resource policies
- Governance rules

---

## 19. Cloud control plane

The cloud control plane manages cloud infrastructure and resources.

Conceptually:

Control Plane

→ Compute

→ Storage

→ Networking

→ Identity

→ Security

→ Scaling

The control plane can manage:

- Provisioning
- Deletion
- Configuration
- Authentication
- Authorization
- Scheduling
- Scaling
- Monitoring
- Resource lifecycle

---

## 20. Control plane vs data plane

The control plane and data plane have different responsibilities.

### Control plane

The control plane answers:

> What should exist and how should it be configured?

Examples:

- Create a virtual machine
- Delete a database
- Configure a network
- Change a scaling policy
- Modify access permissions

### Data plane

The data plane handles actual application workloads.

Examples:

- Processing application requests
- Database queries
- Network traffic
- Application execution

A simplified model is:

Control Plane → Manages infrastructure

Data Plane → Executes workload

---

## 21. Scheduling

Cloud providers require schedulers to determine where workloads should run.

Suppose:

Host A → 20 CPU available

Host B → 10 CPU available

Host C → 50 CPU available

A customer requests:

15 CPU

The scheduler selects a suitable host.

Scheduling decisions may consider:

- CPU
- Memory
- Storage
- Network
- GPU availability
- Region
- Availability zone
- Hardware type
- Affinity
- Anti-affinity
- Capacity
- Cost
- Fault domains

---

## 22. Load balancing

Horizontal elasticity generally works together with load balancing.

Example:

Clients → Load Balancer → Server 1  
                                → Server 2  
                                → Server 3

When demand increases:

Clients → Load Balancer → Server 1  
                                → Server 2  
                                → Server 3  
                                → Server 4  
                                → Server 5

The load balancer distributes requests among instances.

This allows application capacity to grow while distributing traffic across multiple servers.

---

## 23. Elasticity and queues

Some applications should scale based on queue length rather than CPU utilization.

Example:

Users → API → Message Queue → Workers

If the queue becomes too large:

Queue length increases → Autoscaler → More workers

This architecture is useful for asynchronous workloads such as:

- Image processing
- Video processing
- Data processing
- Email processing
- Background jobs

---

## 24. Backpressure

Backpressure occurs when an upstream component produces work faster than a downstream component can process it.

Example:

Producer = 10,000 jobs/sec

Consumer = 2,000 jobs/sec

The queue will grow.

Possible solutions include:

- Autoscaling
- Rate limiting
- Queues
- Retry policies
- Dead-letter queues
- Load shedding
- Backpressure mechanisms

This demonstrates that elasticity must be designed across the complete application architecture.

---

## 25. Serverless computing

Serverless computing provides a high level of infrastructure abstraction.

A developer can deploy a function while the cloud platform handles much of the underlying infrastructure.

Conceptually:

Request → Function → Execution

During low demand:

Few or no active executions

During high demand:

Many concurrent executions

Serverless computing strongly demonstrates:

- On-demand self-service
- Rapid elasticity
- Measured service

---

## 26. Containers

Containers provide application isolation and portability.

A simplified architecture is:

Host Operating System → Container Runtime → Container 1, Container 2, Container 3

Container orchestration platforms can automate:

- Deployment
- Scheduling
- Scaling
- Service discovery
- Networking
- Health checks
- Rolling updates
- Application recovery

Containers are frequently used in cloud-native architectures.

---

## 27. Cloud-native architecture

Cloud-native architecture attempts to take advantage of cloud capabilities instead of simply moving traditional applications into the cloud.

Common cloud-native principles include:

- Automation
- APIs
- Horizontal scaling
- Elasticity
- Containers
- Microservices
- Infrastructure as Code
- Observability
- Continuous delivery
- Resilience
- Automated recovery

---

## 28. Infrastructure as Code

Infrastructure as Code, commonly abbreviated as IaC, means defining infrastructure using machine-readable configuration.

Instead of manually creating:

- Virtual machines
- Networks
- Databases
- Load balancers
- Storage

the desired infrastructure can be described through configuration.

Conceptually:

IaC Configuration → IaC Tool → Cloud APIs → Infrastructure

Benefits include:

- Repeatability
- Automation
- Version control
- Auditing
- Faster deployment
- Reduced configuration drift
- Easier recovery
- Consistent environments

---

## 29. Observability

Measured service depends heavily on observability.

The three commonly discussed pillars of observability are:

### Metrics

Examples:

CPU = 72%

Memory = 65%

Requests/sec = 10,000

### Logs

Logs record application and infrastructure events.

Examples:

- Errors
- Warnings
- Authentication events
- Deployment events
- Application activity

### Traces

Distributed tracing shows how a request travels through different services.

Example:

User Request → API Gateway → Service A → Service B → Database

Observability helps engineers understand:

- Performance
- Failures
- Latency
- Resource consumption
- Capacity
- Dependencies
- Application behavior

---

## 30. Security and broad network access

Broad network access creates important security requirements.

Cloud environments commonly use:

- Identity and Access Management
- Authentication
- Authorization
- Multi-factor authentication
- Encryption
- Firewalls
- Security groups
- Network ACLs
- Private networks
- VPNs
- Secrets management
- Logging
- Monitoring

A secure architecture can look like:

User → Identity Provider → Authentication → Authorization → API Gateway → Application → Private Database

Broad network access and strong security are compatible when appropriate controls are implemented.

---

## 31. IAM and least privilege

IAM stands for Identity and Access Management.

IAM answers questions such as:

- Who are you?
- What are you allowed to do?
- Which resources can you access?

For example:

Developer:

- Read application logs
- Deploy applications
- Cannot delete production databases

Database administrator:

- Manage databases
- Manage database permissions
- Cannot necessarily modify all infrastructure

This follows the principle of least privilege.

The principle is:

> Give users and applications only the permissions they actually need.

---

## 32. Cloud service models

The five characteristics describe cloud computing broadly, while cloud services can be delivered at different abstraction levels.

The classic service models are:

- IaaS
- PaaS
- SaaS

### IaaS

Infrastructure as a Service provides infrastructure resources such as virtual machines, storage, and networking.

The customer typically manages more of the software stack, including:

- Operating system
- Runtime
- Application
- Configuration

The provider manages more of:

- Physical hardware
- Data centers
- Physical networking
- Virtualization

### PaaS

Platform as a Service provides a managed application platform.

The provider manages more infrastructure and runtime components.

The developer can focus primarily on:

- Application code
- Data
- Configuration

### SaaS

Software as a Service provides a finished application.

The customer primarily consumes the application rather than managing the underlying infrastructure.

Examples include categories such as:

- Email
- CRM
- Collaboration software
- Productivity applications

---

## 33. Virtualization vs cloud computing

Virtualization is not the same thing as cloud computing.

Virtualization:

> Abstraction of physical infrastructure into virtual resources.

Cloud computing:

> A broader computing service model involving self-service, network access, resource pooling, elasticity, and measured service.

A company can use virtualization internally without providing cloud computing.

Therefore:

> Virtualization is an important enabling technology, but cloud computing is a broader operational and service delivery model.

---

## 34. Traditional IT vs cloud computing

Traditional IT may look like:

Purchase Hardware → Install Hardware → Configure Infrastructure → Fixed Capacity → Manual Scaling

Cloud computing may look like:

API/Console → Automated Provisioning → Resource Pool → Dynamic Capacity → Autoscaling → Measured Usage

Traditional infrastructure generally requires more upfront planning and physical capacity management.

Cloud infrastructure emphasizes:

- Automation
- Abstraction
- Self-service
- Dynamic allocation
- Elasticity
- Measurement

---

## 35. CAPEX vs OPEX

Traditional infrastructure often involves significant capital expenditure, or CAPEX.

Examples include:

- Servers
- Storage hardware
- Networking equipment
- Data centers
- Power infrastructure
- Cooling infrastructure

Cloud consumption often shifts spending toward operational expenditure, or OPEX, depending on the service and accounting context.

The conceptual difference is:

Traditional IT:

Purchase infrastructure first → Use infrastructure

Cloud:

Consume infrastructure as a service → Pay according to the applicable commercial model

---

## 36. Cloud bursting

Cloud bursting occurs when an organization normally operates workloads on private infrastructure but temporarily uses public cloud resources during periods of high demand.

Normal workload:

Private Data Center

Peak workload:

Private Data Center + Public Cloud

Cloud bursting can provide temporary capacity without permanently purchasing infrastructure for peak demand.

---

## 37. Hybrid cloud

Hybrid cloud combines different infrastructure environments.

Example:

On-Premises Infrastructure → Secure Network → Public Cloud

Organizations may use hybrid cloud for:

- Legacy systems
- Regulatory requirements
- Data locality
- Disaster recovery
- Gradual migration
- Temporary capacity
- Specialized workloads

---

## 38. Multi-cloud

Multi-cloud means using services from multiple cloud providers.

For example:

Cloud Provider A → Compute

Cloud Provider B → Analytics

Cloud Provider C → Specialized AI

Potential benefits include:

- Provider diversification
- Access to specialized services
- Geographic flexibility
- Reduced dependence on one provider

Potential disadvantages include:

- Operational complexity
- Different APIs
- Different security models
- Different pricing systems
- Increased skills requirements
- More complicated governance

---

## 39. Fault tolerance and availability

The five cloud characteristics do not automatically guarantee high availability or fault tolerance.

Cloud applications can still fail because of:

- Application bugs
- Network failures
- Database failures
- Dependency failures
- Configuration errors
- Regional outages
- Capacity problems

High availability may require distributing workloads across multiple fault domains.

Example:

Region → Availability Zone A  
        → Availability Zone B  
        → Availability Zone C

This can improve resilience against certain infrastructure failures.

---

## 40. Idempotency

Cloud automation and distributed systems frequently require idempotent operations.

An operation is idempotent when repeating the operation does not cause unintended additional effects.

For example:

Client sends provisioning request → Network timeout → Client retries

If the operation is designed to be idempotent, the retry should not accidentally create duplicate resources.

Idempotency is important for:

- Cloud APIs
- Infrastructure provisioning
- Distributed systems
- Payment systems
- Message processing
- Automated workflows

---

## 41. Event-driven cloud architecture

Cloud platforms frequently support event-driven architectures.

Example:

File Uploaded → Event → Function → Processing → Database/Storage

Events can trigger processing automatically.

Benefits include:

- Automation
- On-demand execution
- Elasticity
- Decoupling
- Asynchronous processing

---

## 42. FinOps and measured service

FinOps is the practice of managing cloud economics through collaboration between engineering, finance, and business teams.

Measured service provides the usage information required for cloud cost management.

Organizations can ask:

- Which application consumes the most resources?
- Which team has the highest cloud cost?
- Which resources are idle?
- Which instances are oversized?
- Where is network spending increasing?
- Which workloads should be optimized?

Therefore, measured service is both a technical and business capability.

---

## 43. Sustainability

Resource pooling and improved infrastructure utilization can potentially reduce resource waste.

For example:

Dedicated infrastructure → 20% utilization

Shared infrastructure → Higher aggregate utilization

Actual environmental impact depends on many factors, including:

- Data center efficiency
- Energy sources
- Hardware efficiency
- Workload characteristics
- Network consumption
- Storage requirements
- Utilization

Measured service can help organizations understand resource consumption and identify opportunities for efficiency.

---

## 44. The five characteristics working together

The five characteristics should not be viewed as completely independent.

They form a connected cloud operating model:

User → On-demand Self-service → Cloud API → Broad Network Access → Cloud Control Plane → Resource Pooling → Shared Infrastructure → Rapid Elasticity → Dynamic Capacity → Measured Service → Usage, Monitoring, and Billing

This creates a powerful computing model.

The core chain is:

Self-service + Network access + Resource pooling + Elasticity + Measurement

---

## 45. Practical e-commerce example

Imagine an online shopping platform.

Normal traffic:

10 application servers

Flash sale:

100 application servers

After the sale:

15 application servers

The five characteristics appear as follows.

### On-demand self-service

Infrastructure is provisioned automatically through APIs or automation.

### Broad network access

Customers access the application through:

- Web browsers
- Mobile applications
- APIs

### Resource pooling

Underlying infrastructure is shared and dynamically allocated.

### Rapid elasticity

Application capacity grows during the flash sale and decreases after demand falls.

### Measured service

The organization measures:

- Compute
- Storage
- Network
- Database usage
- API requests

---

## 46. Cloud automation feedback loop

A mature cloud system can operate as a feedback loop:

Workload → Metrics → Monitoring → Decision → Automation → Resource Change → New Workload Behavior → Metrics

This creates a continuous cycle:

Observe → Measure → Decide → Act → Observe Again

Autoscaling is a common example of this control-loop concept.

---

## 47. Common misconceptions

### Misconception 1: Cloud is just someone else's computer

This is an oversimplification.

Cloud computing involves:

- Automation
- Self-service
- Network access
- Resource pooling
- Elasticity
- Measurement
- Abstraction
- Orchestration
- Security

### Misconception 2: Cloud means unlimited resources

False.

Cloud providers still have:

- Physical capacity
- Service limits
- Regional limits
- Quotas
- Hardware constraints

### Misconception 3: Cloud automatically scales every application

False.

Elasticity must be deliberately designed and configured.

Applications may require:

- Autoscaling
- Load balancing
- Queues
- Stateless architecture
- Database scaling

### Misconception 4: Broad network access means everything is public

False.

Cloud resources can be protected through:

- Firewalls
- IAM
- Private networking
- VPNs
- Encryption
- Access policies

### Misconception 5: Cloud is always cheaper

False.

Cloud can become expensive because of:

- Idle resources
- Overprovisioning
- Excessive data transfer
- Unused storage
- Poor architecture
- Uncontrolled resource creation

---

## 48. Important distinctions

| Concept | Meaning |
|---|---|
| Scalability | Ability to handle increased workload |
| Elasticity | Ability to dynamically add and remove capacity |
| Metering | Measuring resource consumption |
| Billing | Applying pricing rules to measured usage |
| Virtualization | Abstracting physical resources into virtual resources |
| Resource pooling | Sharing and dynamically allocating infrastructure |
| Multi-tenancy | Multiple customers sharing infrastructure with logical isolation |
| Self-service | Customer can provision resources without provider intervention |
| Broad network access | Cloud capabilities are accessible through networks |
| Autoscaling | Automated adjustment of capacity |

---

## 49. Interview-ready definitions

### On-demand self-service

The ability of a cloud consumer to automatically provision computing capabilities without requiring direct human interaction with the cloud provider.

### Broad network access

Cloud capabilities are available over a network through standard mechanisms and can be accessed by a wide range of client platforms.

### Resource pooling

Provider computing resources are pooled to serve multiple consumers, with resources dynamically assigned and reassigned according to demand.

### Rapid elasticity

Cloud capabilities can be rapidly provisioned and released to scale according to workload demand.

### Measured service

Cloud systems automatically measure, monitor, and report resource consumption, providing visibility for optimization and, where applicable, usage-based charging.

---

## 50. Five-characteristic memory model

A simple way to remember the five characteristics is:

**ASK → ACCESS → SHARE → SCALE → MEASURE**

### ASK

On-demand self-service

### ACCESS

Broad network access

### SHARE

Resource pooling

### SCALE

Rapid elasticity

### MEASURE

Measured service

The complete idea is:

> I can request computing resources myself, access them through networks, consume resources from a shared pool, dynamically increase or decrease capacity, and measure what I consume.

---

## 51. Complete conceptual cloud architecture

A modern cloud-native application may look like:

Users  
↓  
DNS / CDN  
↓  
Load Balancer  
↓  
API Gateway  
↓  
Service A / Service B / Service C  
↓  
Message Queue  
↓  
Workers  
↓  
Database  
↓  
Object Storage

Supporting infrastructure may include:

- Identity
- Security
- Monitoring
- Logging
- Tracing
- Autoscaling
- Billing
- Governance
- Infrastructure as Code
- Networking

The five characteristics operate throughout this architecture.

---

## 52. Mapping characteristics to technologies

| Cloud characteristic | Related technologies and concepts |
|---|---|
| On-demand self-service | APIs, CLI, SDKs, cloud consoles, Infrastructure as Code |
| Broad network access | Internet, HTTPS, APIs, VPNs, private networking |
| Resource pooling | Virtualization, containers, multi-tenancy, schedulers |
| Rapid elasticity | Autoscaling, load balancing, serverless, orchestration |
| Measured service | Metrics, monitoring, metering, billing, FinOps |

---

## 53. What I learned

By studying cloud computing characteristics, I learned that cloud computing is much more than simply running applications on remote servers. It is a complete model for delivering computing capabilities through automation, abstraction, shared infrastructure, network access, dynamic scaling, and measurement.

I learned that **on-demand self-service** allows users and applications to provision cloud resources automatically without depending on manual intervention from the cloud provider.

I learned that **broad network access** makes cloud services available through standardized network mechanisms to different types of clients such as laptops, smartphones, applications, APIs, and IoT devices.

I learned that **resource pooling** allows cloud providers to maintain shared pools of compute, memory, storage, networking, GPUs, and other infrastructure resources.

I learned that **multi-tenancy** allows multiple customers to use shared infrastructure while maintaining logical isolation and security.

I learned that **virtualization** provides an abstraction layer between physical infrastructure and virtual resources.

I learned the difference between **virtualization and cloud computing** and understood that virtualization is an enabling technology rather than a complete definition of cloud computing.

I learned that **rapid elasticity** allows cloud environments to dynamically increase and decrease capacity according to workload demand.

I learned the difference between **scalability and elasticity**. Scalability is the ability to handle increasing workload, while elasticity emphasizes dynamically adding and removing capacity.

I learned about **vertical scaling**, where the capacity of an existing machine is increased, and **horizontal scaling**, where additional instances are added.

I learned how **autoscaling** can use CPU, memory, request rate, latency, queue length, and application-specific metrics to determine when resources should be added or removed.

I learned that **load balancing** distributes traffic across multiple instances and commonly works together with horizontal scaling.

I learned that **measured service** enables cloud platforms to measure resources such as compute time, storage, network traffic, API requests, database operations, and GPU usage.

I learned the difference between **metering and billing**. Metering measures consumption, while billing applies pricing rules to measured consumption.

I learned how the **pay-as-you-go** model provides a utility-like approach to consuming computing resources.

I learned that cloud does not automatically mean lower cost. Idle resources, overprovisioning, excessive storage, network traffic, and inefficient architecture can produce significant expenses.

I learned about **rightsizing**, which means selecting resource configurations that appropriately match workload requirements.

I learned about **resource quotas** and how organizations can limit resource consumption.

I learned about the **cloud control plane** and its role in provisioning, configuration, scheduling, scaling, security, and resource lifecycle management.

I learned the difference between the **control plane and data plane**.

I learned how **scheduling** determines where workloads should run based on resource availability and placement constraints.

I learned how **queues and workers** can support elastic architectures for asynchronous workloads.

I learned about **backpressure**, which occurs when upstream components produce work faster than downstream components can process it.

I learned that cloud security requires controls such as IAM, authentication, authorization, encryption, firewalls, private networking, VPNs, secrets management, and least-privilege access.

I learned about **IaaS, PaaS, and SaaS** as different levels of cloud service abstraction.

I learned that **serverless computing** provides a high level of infrastructure abstraction and can demonstrate on-demand execution, rapid elasticity, and measured service.

I learned that **containers** provide application isolation and portability and are widely used in cloud-native systems.

I learned about **cloud-native architecture**, which emphasizes automation, APIs, containers, microservices, elasticity, observability, Infrastructure as Code, and resilience.

I learned about **Infrastructure as Code**, which allows infrastructure to be described using machine-readable configuration and managed through automation and version control.

I learned about **observability**, including metrics, logs, and traces, and how these capabilities support monitoring, troubleshooting, scaling, and cost optimization.

I learned about **hybrid cloud**, **multi-cloud**, and **cloud bursting** architectures.

I learned about **idempotency** and why it is important for cloud APIs and distributed systems.

I learned about **event-driven architectures**, where events can trigger cloud functions and other processing automatically.

I learned about **FinOps** and how measured service provides the usage information required for cloud cost management.

I learned that cloud resource pooling and efficient utilization can potentially contribute to infrastructure efficiency and sustainability.

I learned that the five characteristics do not automatically guarantee security, availability, reliability, resilience, or low cost. These qualities must be deliberately designed and managed.

---

## 54. Final takeaway

The five essential characteristics of cloud computing are:

1. **On-demand self-service**
2. **Broad network access**
3. **Resource pooling**
4. **Rapid elasticity**
5. **Measured service**

They can be remembered as:

**ASK → ACCESS → SHARE → SCALE → MEASURE**

Together, they create a computing model where users can:

1. Request resources themselves
2. Access resources through networks
3. Consume resources from shared infrastructure
4. Scale capacity dynamically
5. Measure and optimize consumption

The most important takeaway is:

> Cloud computing is not simply about moving servers from an organization's building to a provider's data center. Its real value comes from combining self-service, network accessibility, pooled resources, elasticity, automation, abstraction, and measurement into a unified computing model.

These five characteristics form the conceptual foundation for understanding:

- Cloud infrastructure
- Cloud-native applications
- Virtualization
- Containers
- Serverless computing
- Autoscaling
- Load balancing
- Infrastructure as Code
- Observability
- Distributed systems
- FinOps
- Cloud security
- Hybrid cloud
- Multi-cloud
- Modern cloud architecture

## Final mental model

```text
ON-DEMAND SELF-SERVICE
          |
          v
BROAD NETWORK ACCESS
          |
          v
RESOURCE POOLING
          |
          v
RAPID ELASTICITY
          |
          v
MEASURED SERVICE
