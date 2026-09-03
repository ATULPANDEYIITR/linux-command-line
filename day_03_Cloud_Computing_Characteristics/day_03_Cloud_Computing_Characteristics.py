"""
===============================================================================
CLOUD COMPUTING CHARACTERISTICS
===============================================================================

Topic:
    NIST's Five Essential Characteristics of Cloud Computing

Characteristics:
    1. On-demand self-service
    2. Broad network access
    3. Resource pooling
    4. Rapid elasticity
    5. Measured service

This script explains the topic from beginner to advanced level.

IMPORTANT:
    This is an educational simulation. It does NOT create real cloud
    infrastructure. The classes and functions model how cloud concepts work.

===============================================================================
LEARNING OBJECTIVES
===============================================================================

After studying this script, you should understand:

1. What cloud computing means.
2. Why cloud computing is different from traditional IT infrastructure.
3. The five essential characteristics of cloud computing.
4. On-demand self-service.
5. Broad network access.
6. Resource pooling.
7. Multi-tenancy.
8. Virtualization and abstraction.
9. Rapid elasticity.
10. Horizontal and vertical scaling.
11. Measured service.
12. Pay-as-you-go economics.
13. Metering and monitoring.
14. Service-level concepts.
15. Capacity management.
16. Autoscaling.
17. Load balancing.
18. Resource allocation.
19. Cloud efficiency.
20. How the five characteristics work together.
21. Practical examples using Python.
22. Advanced cloud architecture concepts.
23. Common misconceptions.
24. Interview questions and answers.

===============================================================================
PART 1: WHAT IS CLOUD COMPUTING?
===============================================================================

Cloud computing is a model for delivering computing resources over a network,
usually the Internet.

Instead of purchasing and maintaining physical servers yourself, you can
obtain computing resources from a cloud provider.

Typical cloud resources include:

    - Virtual machines
    - Containers
    - Storage
    - Databases
    - Networks
    - Load balancers
    - AI/ML services
    - Monitoring systems
    - Security services
    - Serverless functions

Examples of cloud providers include:

    - Amazon Web Services (AWS)
    - Microsoft Azure
    - Google Cloud
    - Oracle Cloud
    - IBM Cloud

A simplified traditional IT model:

    Company
       |
       +---- Physical Server
       |
       +---- Storage
       |
       +---- Network
       |
       +---- Data Center
       |
       +---- Electricity
       |
       +---- Cooling
       |
       +---- Hardware Maintenance

A simplified cloud model:

    User
      |
      v
    Cloud API / Console
      |
      v
    Cloud Provider
      |
      +---- Compute
      +---- Storage
      +---- Database
      +---- Networking
      +---- Security
      +---- Monitoring

The cloud hides much of the physical infrastructure from the customer.

The customer usually cares about:

    "How much compute do I need?"

rather than:

    "Which physical server should I purchase?"

===============================================================================
PART 2: WHY DO WE NEED CLOUD COMPUTING?
===============================================================================

Traditional infrastructure has several problems.

Suppose a company expects 1,000 users.

It purchases enough hardware for 1,000 users.

Later, the application becomes popular and suddenly receives 100,000 users.

The company may not have enough infrastructure.

This creates:

    Capacity Problem
          |
          v
    Application slows down
          |
          v
    Users experience failures

The opposite problem also occurs.

Suppose the company purchases infrastructure for 100,000 users but normally
has only 1,000 users.

Most infrastructure remains unused.

That creates:

    Overprovisioning
          |
          v
    Idle resources
          |
          v
    Wasted capital

Cloud computing attempts to solve these problems through characteristics such
as resource pooling, rapid elasticity, and measured service.

===============================================================================
PART 3: THE FIVE ESSENTIAL CHARACTERISTICS
===============================================================================

A cloud environment is commonly described through five essential
characteristics:

    1. On-demand self-service
    2. Broad network access
    3. Resource pooling
    4. Rapid elasticity
    5. Measured service

A useful mental model is:

             CLOUD COMPUTING
                    |
       +------------+------------+
       |            |            |
       v            v            v
   Resources     Network      Economics
       |            |            |
       v            v            v
   Pooling      Access       Measured
       |
       v
   Elasticity
       |
       v
   Self-Service

===============================================================================
PART 4: CHARACTERISTIC #1
ON-DEMAND SELF-SERVICE
===============================================================================

Definition:

On-demand self-service means that a customer can provision computing
resources automatically without requiring direct human interaction with the
cloud provider.

In simple language:

    "I need a server."
    |
    v
    I request it through an API/console.
    |
    v
    Cloud provisions it automatically.

Traditional infrastructure might look like:

    Developer
       |
       v
    Submit request
       |
       v
    IT administrator
       |
       v
    Procurement
       |
       v
    Hardware purchase
       |
       v
    Installation
       |
       v
    Configuration
       |
       v
    Server available

Cloud:

    Developer
       |
       v
    API / Console
       |
       v
    Automated provisioning
       |
       v
    Resource available

This can reduce provisioning time dramatically.

===============================================================================
ON-DEMAND SELF-SERVICE EXAMPLE
===============================================================================
"""

class CloudResource:
    """Represents a generic cloud resource."""

    def __init__(self, resource_id, resource_type, cpu, memory):
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.cpu = cpu
        self.memory = memory
        self.status = "PROVISIONED"

    def __repr__(self):
        return (
            f"CloudResource("
            f"id={self.resource_id}, "
            f"type={self.resource_type}, "
            f"cpu={self.cpu}, "
            f"memory={self.memory}, "
            f"status={self.status})"
        )


class CloudProvider:
    """Simple simulation of a cloud provider."""

    def __init__(self):
        self.resources = {}

    def provision_resource(self, resource_type, cpu, memory):
        resource_id = f"resource-{len(self.resources) + 1}"

        resource = CloudResource(
            resource_id=resource_id,
            resource_type=resource_type,
            cpu=cpu,
            memory=memory
        )

        self.resources[resource_id] = resource

        return resource

    def terminate_resource(self, resource_id):
        if resource_id in self.resources:
            self.resources[resource_id].status = "TERMINATED"

    def list_resources(self):
        return list(self.resources.values())


provider = CloudProvider()

server = provider.provision_resource(
    resource_type="virtual-machine",
    cpu=4,
    memory="16GB"
)

print("\nON-DEMAND SELF-SERVICE")
print(server)

"""
The important concept is not the Python class itself.

The important concept is:

    Customer
       |
       v
    API request
       |
       v
    Automated provisioning
       |
       v
    Resource

Real cloud providers implement this using APIs, orchestration systems,
identity management, infrastructure-as-code, and control planes.

Examples of provisioning interfaces include:

    - Web console
    - REST API
    - CLI
    - SDK
    - Infrastructure-as-Code

===============================================================================
PART 5: API-DRIVEN SELF-SERVICE
===============================================================================

Modern cloud platforms are heavily API-driven.

A user might conceptually make a request such as:

    POST /instances

with parameters:

    CPU = 4
    Memory = 16 GB
    Image = Linux
    Region = selected-region

The cloud control plane receives the request.

A simplified architecture:

    User
      |
      v
    API
      |
      v
    Authentication
      |
      v
    Authorization
      |
      v
    Cloud Control Plane
      |
      v
    Scheduler
      |
      v
    Resource Pool
      |
      v
    Compute Instance

Important distinction:

    CONTROL PLANE
        |
        +-- Creates
        +-- Deletes
        +-- Configures
        +-- Scales
        +-- Manages

    DATA PLANE
        |
        +-- Handles actual application traffic
        +-- Performs application work

===============================================================================
PART 6: CHARACTERISTIC #2
BROAD NETWORK ACCESS
===============================================================================

Broad network access means cloud capabilities are available over a network
through standard mechanisms and can be accessed by a wide variety of client
devices.

Examples:

    Laptop
    Desktop
    Smartphone
    Tablet
    IoT device
    Application
    CLI
    API client

Conceptually:

                CLOUD
                  |
        +---------+---------+
        |         |         |
        v         v         v
      Laptop   Smartphone   API
        |
        v
      Browser

The important idea is network accessibility.

Cloud resources are not usually restricted to a single physical machine in
a local office.

===============================================================================
BROAD NETWORK ACCESS EXAMPLE
===============================================================================
"""

import requests


def demonstrate_api_access():
    """
    Demonstrates the general concept of network/API access.

    This example intentionally does not call a real cloud provider.
    """

    cloud_endpoint = "https://cloud.example.com/api/resources"

    request_information = {
        "method": "GET",
        "endpoint": cloud_endpoint,
        "client": "Python application"
    }

    return request_information


print("\nBROAD NETWORK ACCESS")
print(demonstrate_api_access())

"""
A real cloud SDK may perform authenticated API calls.

The flow could be:

    Python Application
          |
          v
    Internet / Private Network
          |
          v
    Cloud API Endpoint
          |
          v
    Authentication
          |
          v
    Cloud Service

===============================================================================
IMPORTANT NETWORK CONCEPTS
===============================================================================

Broad network access depends on several technologies:

    - TCP/IP
    - DNS
    - HTTP/HTTPS
    - TLS
    - REST APIs
    - SDKs
    - VPNs
    - Private networks
    - Firewalls
    - Load balancers
    - Identity and access management

Cloud services can be exposed through:

    Public endpoints
    Private endpoints
    Internal service networks
    VPN connections
    Dedicated network connections

===============================================================================
PART 7: NETWORK ACCESSIBILITY DOES NOT MEAN "PUBLICLY OPEN"
===============================================================================

This is a common misconception.

Broad network access does NOT mean:

    "Everyone on the Internet can access everything."

Security controls can restrict access.

For example:

    Internet
       |
       v
    Firewall
       |
       v
    Load Balancer
       |
       v
    Application
       |
       v
    Private Database

The database may not be directly accessible from the public Internet.

===============================================================================
PART 8: CHARACTERISTIC #3
RESOURCE POOLING
===============================================================================

Resource pooling means the cloud provider pools computing resources to serve
multiple customers using a multi-tenant model.

Physical resources can include:

    - CPU
    - RAM
    - Storage
    - Network bandwidth
    - GPU
    - Specialized accelerators

Instead of dedicating one physical server to one customer, a provider may
allocate resources dynamically.

Conceptually:

                 PHYSICAL INFRASTRUCTURE
                         |
            +------------+------------+
            |            |            |
            v            v            v
          CPU          RAM         Storage
            |            |            |
            +------------+------------+
                         |
                         v
                   RESOURCE POOL
                  /      |       \
                 /       |        \
                v        v         v
             Tenant A  Tenant B  Tenant C

===============================================================================
MULTI-TENANCY
===============================================================================

Multi-tenancy means multiple customers can use shared underlying
infrastructure while logically remaining isolated.

For example:

    Physical Server
          |
    +-----+-----+-----+
    |           |     |
    v           v     v
  VM A        VM B   VM C
 Tenant A    Tenant B Tenant C

The tenants should not be able to access each other's data.

Isolation can be implemented through technologies such as:

    - Virtual machines
    - Containers
    - Hypervisors
    - Network segmentation
    - Access control
    - Encryption
    - Storage isolation

===============================================================================
PART 9: VIRTUALIZATION
===============================================================================

Virtualization is one of the technologies that helps providers pool
infrastructure.

Imagine a physical server:

    32 CPU cores
    128 GB RAM

A hypervisor can divide the physical machine into multiple virtual machines.

Example:

    Physical Server
    32 CPU cores
    128 GB RAM

          |
          v

    +--------------------+
    | Hypervisor         |
    +--------------------+
       |       |       |
       v       v       v
      VM1     VM2     VM3

Each VM may receive a portion of the resources.

This creates abstraction.

The customer interacts with:

    "My virtual machine"

rather than:

    "Physical server #48192"

===============================================================================
PART 10: ABSTRACTION
===============================================================================

Abstraction hides unnecessary implementation details.

For example, a customer may request:

    4 vCPU
    16 GB RAM
    Linux

The customer may not know which physical machine will host the workload.

This abstraction allows cloud providers to optimize infrastructure.

The provider can move workloads, schedule workloads, allocate resources,
replace hardware, and manage infrastructure without requiring the customer
to understand every physical detail.

===============================================================================
PART 11: RESOURCE ALLOCATION SIMULATION
===============================================================================
"""

class ResourcePool:
    """Simulates a shared cloud resource pool."""

    def __init__(self, total_cpu, total_memory):
        self.total_cpu = total_cpu
        self.total_memory = total_memory

        self.available_cpu = total_cpu
        self.available_memory = total_memory

        self.allocations = {}

    def allocate(self, tenant, cpu, memory):
        if cpu > self.available_cpu:
            raise RuntimeError("Insufficient CPU resources.")

        if memory > self.available_memory:
            raise RuntimeError("Insufficient memory resources.")

        self.available_cpu -= cpu
        self.available_memory -= memory

        self.allocations[tenant] = {
            "cpu": cpu,
            "memory": memory
        }

    def release(self, tenant):
        if tenant not in self.allocations:
            return

        allocation = self.allocations.pop(tenant)

        self.available_cpu += allocation["cpu"]
        self.available_memory += allocation["memory"]

    def utilization(self):
        cpu_used = self.total_cpu - self.available_cpu
        memory_used = self.total_memory - self.available_memory

        return {
            "cpu_utilization": cpu_used / self.total_cpu,
            "memory_utilization": memory_used / self.total_memory
        }


pool = ResourcePool(
    total_cpu=64,
    total_memory=256
)

pool.allocate(
    tenant="customer-A",
    cpu=8,
    memory=32
)

pool.allocate(
    tenant="customer-B",
    cpu=16,
    memory=64
)

print("\nRESOURCE POOLING")
print(pool.allocations)
print(pool.utilization())

"""
===============================================================================
PART 12: RESOURCE POOLING AND LOCATION INDEPENDENCE
===============================================================================

A cloud customer often does not control the exact physical location of a
resource.

The provider may have:

    Region
       |
       +-- Availability Zone A
       +-- Availability Zone B
       +-- Availability Zone C

Inside each availability zone:

       Data Center
            |
       +----+----+
       |         |
       v         v
    Server     Server
       |
       v
    Resource Pool

The customer may select a region or availability zone while the provider
handles physical infrastructure.

===============================================================================
PART 13: CHARACTERISTIC #4
RAPID ELASTICITY
===============================================================================

Rapid elasticity means resources can be provisioned and released rapidly,
often automatically, according to demand.

This is one of the most important characteristics of cloud computing.

Consider an e-commerce website.

Normal traffic:

    1,000 requests/minute

During a major sale:

    100,000 requests/minute

After the sale:

    2,000 requests/minute

Static infrastructure:

    10 servers
    ------------------------------
    Normal:      enough
    Sale:        insufficient
    After sale:  mostly idle

Elastic infrastructure:

    Normal:
        10 servers

    Sale:
        100 servers

    After sale:
        12 servers

The system adjusts capacity according to demand.

===============================================================================
SCALING
===============================================================================

There are two major forms of scaling.

1. Vertical scaling
2. Horizontal scaling

===============================================================================
VERTICAL SCALING
===============================================================================

Vertical scaling means increasing or decreasing the capacity of an existing
machine.

Example:

    2 CPU
    8 GB RAM

becomes:

    8 CPU
    32 GB RAM

Conceptually:

        SMALL VM
           |
           | scale up
           v
        LARGE VM

Advantages:

    - Simple concept
    - Sometimes easier for stateful applications
    - Can improve single-node performance

Disadvantages:

    - Physical limits exist
    - May require restart
    - Can create a single point of failure
    - Eventually becomes expensive

===============================================================================
HORIZONTAL SCALING
===============================================================================

Horizontal scaling means adding or removing instances.

Example:

    Server 1

becomes:

    Server 1
    Server 2
    Server 3
    Server 4

Advantages:

    - Better fault tolerance
    - Large scale
    - Works well with distributed architectures
    - Supports load balancing

Disadvantages:

    - Application architecture becomes more complex
    - State management becomes important
    - Distributed systems introduce additional failure modes

===============================================================================
ELASTICITY VS SCALABILITY
===============================================================================

These concepts are related but not identical.

SCALABILITY:

    Ability of a system to handle increased workload by adding capacity.

ELASTICITY:

    Ability to dynamically add and remove capacity according to changing
    workload.

Example:

    A system can scale from 10 servers to 100 servers.

That demonstrates scalability.

If it automatically goes:

    10 -> 100 -> 20 -> 50 -> 10

according to demand, that demonstrates elasticity.

===============================================================================
PART 14: AUTOSCALING
===============================================================================

Autoscaling is the automated adjustment of infrastructure capacity.

A simplified autoscaling system:

                     APPLICATION
                          |
                          v
                     MONITORING
                          |
                          v
                    CPU / Requests
                          |
                          v
                     AUTOSCALER
                     /        \
                    /          \
                   v            v
              Scale Up      Scale Down

Example policy:

    IF CPU > 70%
        increase instances

    IF CPU < 30%
        decrease instances

===============================================================================
AUTOSCALER SIMULATION
===============================================================================
"""

class AutoScaler:
    """Simple autoscaling simulation."""

    def __init__(
        self,
        minimum_instances=1,
        maximum_instances=10,
        scale_up_threshold=70,
        scale_down_threshold=30
    ):
        self.minimum_instances = minimum_instances
        self.maximum_instances = maximum_instances
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.instances = minimum_instances

    def evaluate(self, cpu_usage):
        if cpu_usage > self.scale_up_threshold:
            self.instances = min(
                self.instances + 1,
                self.maximum_instances
            )

        elif cpu_usage < self.scale_down_threshold:
            self.instances = max(
                self.instances - 1,
                self.minimum_instances
            )

        return self.instances


autoscaler = AutoScaler(
    minimum_instances=2,
    maximum_instances=8
)

cpu_samples = [
    20,
    25,
    75,
    80,
    90,
    85,
    40,
    20
]

print("\nRAPID ELASTICITY / AUTOSCALING")

for cpu in cpu_samples:
    instances = autoscaler.evaluate(cpu)

    print(
        f"CPU Usage: {cpu}% | "
        f"Instances: {instances}"
    )

"""
===============================================================================
PART 15: WHY AUTOSCALING IS MORE COMPLEX IN REAL SYSTEMS
===============================================================================

Real autoscaling systems may consider:

    - CPU utilization
    - Memory utilization
    - Request count
    - Requests per second
    - Queue length
    - Latency
    - Custom business metrics
    - Scheduled events
    - Predictive demand
    - Cost constraints

Example:

    IF average request latency > 500 ms
        scale up

    IF queue length > 1000
        scale up

    IF utilization < 20%
        scale down

Cloud systems may use multiple signals.

===============================================================================
PART 16: COOL-DOWN PERIODS
===============================================================================

A naive autoscaler can oscillate.

Example:

    Scale up
       |
       v
    Load decreases
       |
       v
    Scale down
       |
       v
    Load increases
       |
       v
    Scale up again

This is called oscillation or thrashing.

Cloud systems can use:

    - Cooldown periods
    - Stabilization windows
    - Hysteresis
    - Predictive scaling
    - Minimum/maximum instance limits

===============================================================================
HYSTERESIS
===============================================================================

Instead of:

    Scale up above 70%
    Scale down below 70%

use:

    Scale up above 70%
    Scale down below 30%

This creates a gap.

That gap reduces rapid switching.

===============================================================================
PART 17: CHARACTERISTIC #5
MEASURED SERVICE
===============================================================================

Measured service means cloud systems automatically control and optimize
resource usage by measuring usage.

The provider can monitor resources such as:

    - CPU time
    - Memory
    - Storage
    - Network traffic
    - Number of requests
    - Database operations
    - Function invocations
    - GPU usage

The user can be charged according to usage depending on the service model.

This creates a utility-style computing model.

Traditional model:

    Buy hardware
       |
       v
    Own capacity
       |
       v
    Pay upfront

Cloud model:

    Consume resources
       |
       v
    Measure usage
       |
       v
    Pay according to pricing model

===============================================================================
PART 18: METERING
===============================================================================

Metering means measuring resource consumption.

Example:

    CPU usage:
        100 hours

    Storage:
        500 GB-month

    Network:
        2 TB

    API calls:
        10 million

A simplified metering system can be modeled with Python.

===============================================================================
METERING SIMULATION
===============================================================================
"""

class UsageMeter:
    """Tracks cloud resource usage."""

    def __init__(self):
        self.usage = {
            "compute_hours": 0,
            "storage_gb": 0,
            "network_gb": 0,
            "api_requests": 0
        }

    def record_compute(self, hours):
        self.usage["compute_hours"] += hours

    def record_storage(self, gb):
        self.usage["storage_gb"] += gb

    def record_network(self, gb):
        self.usage["network_gb"] += gb

    def record_api_requests(self, count):
        self.usage["api_requests"] += count

    def report(self):
        return self.usage.copy()


meter = UsageMeter()

meter.record_compute(120)
meter.record_storage(500)
meter.record_network(200)
meter.record_api_requests(1_000_000)

print("\nMEASURED SERVICE")
print(meter.report())

"""
===============================================================================
PART 19: BILLING
===============================================================================

Measured service and billing are related but not identical.

MEASUREMENT:

    How much resource was consumed?

BILLING:

    How much should the customer pay based on the pricing model?

Example:

    Usage:
        100 compute hours

    Price:
        $0.05 per compute hour

    Cost:
        $5.00

===============================================================================
BILLING SIMULATION
===============================================================================
"""

class CloudBill:
    """Simple cloud billing calculator."""

    def __init__(
        self,
        compute_price_per_hour,
        storage_price_per_gb,
        network_price_per_gb
    ):
        self.compute_price_per_hour = compute_price_per_hour
        self.storage_price_per_gb = storage_price_per_gb
        self.network_price_per_gb = network_price_per_gb

    def calculate(
        self,
        compute_hours,
        storage_gb,
        network_gb
    ):
        compute_cost = (
            compute_hours *
            self.compute_price_per_hour
        )

        storage_cost = (
            storage_gb *
            self.storage_price_per_gb
        )

        network_cost = (
            network_gb *
            self.network_price_per_gb
        )

        total = (
            compute_cost +
            storage_cost +
            network_cost
        )

        return {
            "compute_cost": compute_cost,
            "storage_cost": storage_cost,
            "network_cost": network_cost,
            "total_cost": total
        }


bill = CloudBill(
    compute_price_per_hour=0.05,
    storage_price_per_gb=0.02,
    network_price_per_gb=0.01
)

cost = bill.calculate(
    compute_hours=100,
    storage_gb=500,
    network_gb=100
)

print("\nCLOUD BILLING SIMULATION")
print(cost)

"""
===============================================================================
PART 20: PAY-AS-YOU-GO
===============================================================================

Pay-as-you-go means customers can pay according to their consumption under
the relevant pricing model.

This is similar to utilities.

Electricity:

    Consume electricity
         |
         v
    Meter consumption
         |
         v
    Calculate bill

Cloud:

    Consume compute
         |
         v
    Measure consumption
         |
         v
    Calculate bill

This does NOT mean every cloud service is billed purely per second or per
request. Pricing models differ significantly.

Cloud pricing may involve:

    - Per-second pricing
    - Per-minute pricing
    - Per-hour pricing
    - Per-request pricing
    - Storage capacity
    - Data transfer
    - Reserved commitments
    - Savings plans
    - Subscription pricing
    - Tiered pricing
    - Free tiers

===============================================================================
PART 21: RESOURCE UTILIZATION
===============================================================================

Measured service allows organizations to understand utilization.

For example:

    Server capacity:
        100 units

    Actual utilization:
        20 units

Utilization:

        20 / 100 = 20%

If infrastructure remains at low utilization, the organization may investigate
rightsizing or architecture changes.

===============================================================================
UTILIZATION CALCULATOR
===============================================================================
"""

def calculate_utilization(used, capacity):
    if capacity <= 0:
        raise ValueError("Capacity must be greater than zero.")

    return used / capacity


print("\nRESOURCE UTILIZATION")

utilization = calculate_utilization(
    used=40,
    capacity=100
)

print(f"Utilization: {utilization:.0%}")

"""
===============================================================================
PART 22: HOW THE FIVE CHARACTERISTICS WORK TOGETHER
===============================================================================

The five characteristics should not be viewed as isolated concepts.

They form a connected cloud operating model.

Example:

    User
      |
      | 1. On-demand self-service
      v
    Cloud API
      |
      | 2. Broad network access
      v
    Cloud control plane
      |
      | 3. Resource pooling
      v
    Shared infrastructure
      |
      | 4. Rapid elasticity
      v
    Dynamic capacity
      |
      | 5. Measured service
      v
    Usage + monitoring + billing

This creates a powerful model:

    SELF-SERVICE
        +
    NETWORK ACCESS
        +
    RESOURCE POOLING
        +
    ELASTICITY
        +
    MEASUREMENT
        =
    CLOUD COMPUTING MODEL

===============================================================================
PART 23: COMPLETE CLOUD SIMULATION
===============================================================================
"""

class CloudEnvironment:
    """
    Combines the five cloud characteristics into one simplified simulation.
    """

    def __init__(self, total_cpu, total_memory):
        self.pool = ResourcePool(
            total_cpu=total_cpu,
            total_memory=total_memory
        )

        self.meter = UsageMeter()

        self.resources = {}

    # -------------------------------------------------------------------------
    # 1. ON-DEMAND SELF-SERVICE
    # -------------------------------------------------------------------------
    def request_resource(self, customer, cpu, memory):
        resource_id = (
            f"{customer}-"
            f"{len(self.resources) + 1}"
        )

        self.pool.allocate(
            tenant=resource_id,
            cpu=cpu,
            memory=memory
        )

        self.resources[resource_id] = {
            "customer": customer,
            "cpu": cpu,
            "memory": memory,
            "status": "RUNNING"
        }

        return resource_id

    # -------------------------------------------------------------------------
    # 2. RESOURCE RELEASE
    # -------------------------------------------------------------------------
    def release_resource(self, resource_id):
        if resource_id not in self.resources:
            return

        self.pool.release(resource_id)

        self.resources[resource_id]["status"] = "TERMINATED"

    # -------------------------------------------------------------------------
    # 3. MEASURED SERVICE
    # -------------------------------------------------------------------------
    def record_usage(
        self,
        compute_hours=0,
        storage_gb=0,
        network_gb=0,
        api_requests=0
    ):
        self.meter.record_compute(compute_hours)
        self.meter.record_storage(storage_gb)
        self.meter.record_network(network_gb)
        self.meter.record_api_requests(api_requests)

    def status(self):
        return {
            "resources": self.resources,
            "pool_utilization": self.pool.utilization(),
            "usage": self.meter.report()
        }


cloud = CloudEnvironment(
    total_cpu=100,
    total_memory=512
)

resource_a = cloud.request_resource(
    customer="customer-A",
    cpu=10,
    memory=64
)

resource_b = cloud.request_resource(
    customer="customer-B",
    cpu=20,
    memory=128
)

cloud.record_usage(
    compute_hours=200,
    storage_gb=1000,
    network_gb=500,
    api_requests=2_000_000
)

print("\nCOMPLETE CLOUD SIMULATION")

for key, value in cloud.status().items():
    print(f"{key}: {value}")

"""
===============================================================================
PART 24: CLOUD CONTROL PLANE
===============================================================================

A cloud provider generally needs a control plane to manage resources.

Conceptually:

                       CONTROL PLANE
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
       Compute            Storage           Network
          |                  |                  |
          v                  v                  v
      Instances           Volumes           Networks

The control plane may manage:

    - Provisioning
    - Scheduling
    - Authentication
    - Authorization
    - Configuration
    - Scaling
    - Monitoring
    - Resource lifecycle

===============================================================================
PART 25: CLOUD DATA PLANE
===============================================================================

The data plane handles actual workload execution.

Example:

    User request
         |
         v
    Load balancer
         |
         v
    Application servers
         |
         v
    Database

The application traffic itself is part of the workload/data plane.

A useful distinction:

    Control plane:
        "What should exist?"

    Data plane:
        "What is actually processing traffic?"

===============================================================================
PART 26: SCHEDULING
===============================================================================

When many customers request resources, the provider needs a scheduler.

Suppose the provider has:

    Host A:
        20 CPU available

    Host B:
        10 CPU available

    Host C:
        50 CPU available

A customer requests:

    15 CPU

The scheduler selects an appropriate host.

Simplified:

    Request
       |
       v
    Scheduler
       |
       +---- Host A
       |
       +---- Host B
       |
       +---- Host C
              |
              v
           Selected

Scheduling can consider:

    - CPU
    - Memory
    - Storage
    - Network
    - Availability zone
    - Affinity
    - Anti-affinity
    - Hardware type
    - GPU availability
    - Cost
    - Fault domains

===============================================================================
PART 27: LOAD BALANCING
===============================================================================

Horizontal elasticity usually requires load balancing.

Suppose:

    Client
       |
       v
    Load Balancer
      / | \
     /  |  \
    v   v   v
   S1  S2  S3

The load balancer distributes requests among servers.

If demand increases:

    Client
       |
       v
    Load Balancer
    / | | | \
   v  v v v  v
  S1 S2 S3 S4 S5

The autoscaler can create more instances.

===============================================================================
PART 28: ELASTICITY + LOAD BALANCING
===============================================================================

These concepts often work together.

    Incoming traffic
          |
          v
    Load balancer
          |
          v
    Application instances
          |
          v
    Monitoring
          |
          v
    Autoscaler
          |
          v
    New instances
          |
          v
    Load balancer
          |
          v
    More capacity

This is a fundamental cloud architecture pattern.

===============================================================================
PART 29: RESOURCE POOLING AND MULTI-TENANCY
===============================================================================

Suppose three customers use one provider.

    Physical Infrastructure
            |
       +----+----+
       |         |
       v         v
    Compute    Storage
       |
    +--+--+--+
    |  |  |  |
    v  v  v  v
   A   B  C  D

Customers share infrastructure while logical boundaries remain enforced.

Important requirements include:

    Isolation
    Security
    Fairness
    Resource limits
    Quotas
    Monitoring

===============================================================================
PART 30: RESOURCE QUOTAS
===============================================================================

Cloud providers and organizations can define quotas.

Example:

    Customer A:
        Maximum 100 VMs

    Customer B:
        Maximum 50 VMs

Quotas prevent unrestricted resource consumption.

===============================================================================
QUOTA SIMULATION
===============================================================================
"""

class ResourceQuota:
    """Limits how many resources a tenant can allocate."""

    def __init__(self, maximum_resources):
        self.maximum_resources = maximum_resources
        self.current_resources = 0

    def allocate(self):
        if self.current_resources >= self.maximum_resources:
            raise RuntimeError("Resource quota exceeded.")

        self.current_resources += 1

    def release(self):
        if self.current_resources > 0:
            self.current_resources -= 1


quota = ResourceQuota(maximum_resources=3)

print("\nRESOURCE QUOTA")

for _ in range(3):
    quota.allocate()

print(
    f"Current resources: "
    f"{quota.current_resources}"
)

"""
===============================================================================
PART 31: SECURITY AND BROAD NETWORK ACCESS
===============================================================================

Because cloud services are accessible through networks, security becomes
extremely important.

Common controls include:

    - Identity and Access Management
    - Authentication
    - Authorization
    - MFA
    - Encryption
    - Firewalls
    - Security groups
    - Network ACLs
    - Private networking
    - Secrets management
    - Logging
    - Monitoring

A secure architecture may look like:

    User
      |
      v
    Identity Provider
      |
      v
    Authentication
      |
      v
    Authorization
      |
      v
    API Gateway
      |
      v
    Application
      |
      v
    Private Database

===============================================================================
PART 32: IAM
===============================================================================

IAM stands for Identity and Access Management.

IAM answers questions such as:

    Who are you?

    What are you allowed to do?

Example:

    Developer
        |
        +-- Read application logs
        +-- Deploy application
        +-- Cannot delete production database

    Database administrator
        |
        +-- Manage databases
        +-- Cannot modify identity policies

This follows the principle of least privilege.

===============================================================================
PART 33: SERVICE MODELS
===============================================================================

The five characteristics apply to cloud computing broadly, but cloud
services can be delivered at different abstraction levels.

Three classic service models are:

    IaaS
    PaaS
    SaaS

===============================================================================
IaaS
===============================================================================

Infrastructure as a Service.

The customer manages more of the software stack.

Example:

    Cloud VM

Customer typically manages:

    - Operating system
    - Application
    - Runtime
    - Configuration

Provider manages:

    - Physical hardware
    - Data center
    - Networking infrastructure
    - Virtualization layer

===============================================================================
PaaS
===============================================================================

Platform as a Service.

The provider manages more infrastructure and runtime components.

Developer focuses primarily on:

    Application code
    Data
    Configuration

The platform handles more operational complexity.

===============================================================================
SAAS
===============================================================================

Software as a Service.

The customer primarily consumes the finished application.

Examples conceptually include:

    Email
    CRM
    Collaboration software
    Online document systems

The customer generally does not manage the underlying servers.

===============================================================================
PART 34: SERVERLESS AND CLOUD CHARACTERISTICS
===============================================================================

Serverless computing is another abstraction model.

A developer might deploy:

    function()

and the platform handles:

    - Infrastructure
    - Capacity
    - Scaling
    - Server management

Serverless strongly demonstrates:

    On-demand self-service
    Rapid elasticity
    Measured service

For example:

    1 request
        |
        v
    Function invocation

    1,000,000 requests
        |
        v
    Function scales automatically

The developer does not manually provision 1,000,000 servers.

===============================================================================
PART 35: CONTAINERS
===============================================================================

Containers provide another form of application isolation.

Conceptually:

    Host Operating System
          |
       Container Runtime
          |
       +--+--+--+
       |  |  |  |
       v  v  v  v
      C1 C2 C3 C4

Containers are lightweight compared with traditional VMs because they can
share the host operating system kernel.

Container orchestration platforms can automate:

    - Deployment
    - Scaling
    - Scheduling
    - Service discovery
    - Networking
    - Health checks

===============================================================================
PART 36: CLOUD-NATIVE ARCHITECTURE
===============================================================================

Cloud-native architecture attempts to exploit cloud capabilities rather than
simply moving traditional applications into the cloud.

Typical characteristics include:

    - Automation
    - Elasticity
    - Horizontal scaling
    - Containers
    - Microservices
    - APIs
    - Infrastructure as Code
    - Observability
    - Continuous delivery
    - Resilience

===============================================================================
PART 37: INFRASTRUCTURE AS CODE
===============================================================================

Infrastructure as Code, or IaC, means defining infrastructure using
machine-readable configuration.

Instead of manually creating:

    VM
    Network
    Database

you describe the desired infrastructure declaratively.

Conceptually:

    Configuration
         |
         v
    IaC tool
         |
         v
    Cloud API
         |
         v
    Infrastructure

Benefits:

    - Repeatability
    - Automation
    - Version control
    - Auditing
    - Faster deployment
    - Reduced configuration drift

===============================================================================
PART 38: OBSERVABILITY
===============================================================================

Measured service depends heavily on observability.

Three common pillars:

    1. Metrics
    2. Logs
    3. Traces

METRICS:

    CPU = 72%
    Memory = 65%
    Requests/sec = 10,000

LOGS:

    Application events

TRACES:

    Request journey through distributed services

Example:

    User Request
        |
        v
    API Gateway
        |
        v
    Service A
        |
        v
    Service B
        |
        v
    Database

Distributed tracing can help determine where latency occurs.

===============================================================================
PART 39: SERVICE LEVEL OBJECTIVES
===============================================================================

Cloud systems often use Service Level Objectives (SLOs).

Example:

    Availability target:
        99.9%

    Latency target:
        95% of requests < 200 ms

Elasticity and resource management can help meet these objectives.

But elasticity does not guarantee availability by itself.

A highly elastic system can still fail because of:

    - Bad application code
    - Database bottlenecks
    - Network failure
    - Dependency failure
    - Configuration errors
    - Regional outage

===============================================================================
PART 40: FAULT TOLERANCE
===============================================================================

Cloud architectures often distribute resources across fault domains.

Conceptually:

               REGION
                  |
        +---------+---------+
        |         |         |
        v         v         v
       AZ-A      AZ-B      AZ-C
        |         |         |
       VM        VM        VM

If one availability zone fails, workloads in other zones may continue.

This is related to:

    - High availability
    - Fault tolerance
    - Disaster recovery
    - Resilience

These concepts are not themselves one of the five essential characteristics,
but they are important when implementing cloud systems.

===============================================================================
PART 41: COST OPTIMIZATION
===============================================================================

Measured service creates visibility into costs.

A simplified cost model:

    Total Cost
        =
    Compute Cost
        +
    Storage Cost
        +
    Network Cost
        +
    Database Cost
        +
    Other Services

Organizations can use measured usage to identify:

    - Idle instances
    - Oversized instances
    - Excessive storage
    - Unexpected network traffic
    - Unused resources

===============================================================================
PART 42: RIGHTSIZING
===============================================================================

Rightsizing means selecting an appropriate resource size.

Example:

    Provisioned:
        16 CPU
        64 GB RAM

    Actual requirement:
        4 CPU
        16 GB RAM

The resource may be oversized.

Measured service helps reveal this mismatch.

===============================================================================
PART 43: CLOUD BURSTING
===============================================================================

Cloud bursting occurs when an organization normally runs workloads on private
infrastructure but temporarily uses public cloud capacity during demand
spikes.

Example:

    Normal:
        Private data center

    Peak demand:
        Private data center
              +
        Public cloud

This can provide temporary elasticity.

===============================================================================
PART 44: HYBRID CLOUD
===============================================================================

Hybrid cloud combines different infrastructure environments.

Example:

    On-premises
         |
         |
      Network
         |
         v
    Public Cloud

Organizations may use hybrid architectures for:

    - Regulatory requirements
    - Legacy applications
    - Data locality
    - Disaster recovery
    - Capacity expansion

===============================================================================
PART 45: MULTI-CLOUD
===============================================================================

Multi-cloud means using services from multiple cloud providers.

Example:

    Provider A:
        Compute

    Provider B:
        Analytics

    Provider C:
        Specialized AI

Potential benefits:

    - Provider diversification
    - Access to specialized services
    - Geographic flexibility

Potential disadvantages:

    - Operational complexity
    - Different APIs
    - Different security models
    - Different pricing systems
    - Skills requirements

===============================================================================
PART 46: CLOUD ELASTICITY AND QUEUES
===============================================================================

Not every system should immediately add application servers.

Sometimes workload is placed into a queue.

Example:

    Users
      |
      v
    API
      |
      v
    Queue
      |
      +---- Worker 1
      +---- Worker 2
      +---- Worker 3

If queue length increases:

    Queue length
         |
         v
    Autoscaler
         |
         v
    More workers

This can be more stable than scaling directly from CPU utilization.

===============================================================================
PART 47: BACKPRESSURE
===============================================================================

Backpressure occurs when downstream systems cannot process work as quickly
as upstream systems produce it.

Example:

    Producer:
        10,000 jobs/sec

    Consumer:
        2,000 jobs/sec

The queue grows.

A cloud-native architecture may use:

    Queue
    Rate limiting
    Autoscaling
    Retry policies
    Dead-letter queues

This illustrates why elasticity must be designed across the entire system.

===============================================================================
PART 48: RESOURCE GOVERNANCE
===============================================================================

Cloud resource pooling creates the need for governance.

Organizations may establish:

    - Quotas
    - Budgets
    - Policies
    - Tags
    - Resource naming standards
    - Access policies
    - Encryption requirements
    - Network restrictions

Example:

    Production resources
        |
        +-- Must be encrypted
        +-- Must have backups
        +-- Must have owner tag
        +-- Must have monitoring

===============================================================================
PART 49: CLOUD AUTOMATION LOOP
===============================================================================

A mature cloud platform can operate as a feedback system.

    Workload
       |
       v
    Metrics
       |
       v
    Monitoring
       |
       v
    Decision
       |
       v
    Automation
       |
       v
    Resource Change
       |
       v
    New Workload Behavior
       |
       +----------------------+
                              |
                              v
                           Metrics

This resembles a control loop.

The cloud continuously observes resource conditions and can respond
automatically.

===============================================================================
PART 50: ADVANCED ELASTICITY MODEL
===============================================================================
"""

class AdvancedAutoScaler:
    """
    More realistic autoscaler simulation.

    Uses:
        - minimum instances
        - maximum instances
        - scale-up threshold
        - scale-down threshold
        - cooldown
    """

    def __init__(
        self,
        minimum_instances=2,
        maximum_instances=20,
        scale_up_threshold=70,
        scale_down_threshold=30,
        cooldown_period=2
    ):
        self.minimum_instances = minimum_instances
        self.maximum_instances = maximum_instances

        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold

        self.cooldown_period = cooldown_period
        self.cooldown_remaining = 0

        self.instances = minimum_instances

    def evaluate(self, cpu_usage):
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return self.instances

        if cpu_usage > self.scale_up_threshold:
            self.instances = min(
                self.instances + 1,
                self.maximum_instances
            )

            self.cooldown_remaining = self.cooldown_period

        elif cpu_usage < self.scale_down_threshold:
            self.instances = max(
                self.instances - 1,
                self.minimum_instances
            )

            self.cooldown_remaining = self.cooldown_period

        return self.instances


advanced_autoscaler = AdvancedAutoScaler()

print("\nADVANCED AUTOSCALING")

traffic_pattern = [
    20,
    25,
    75,
    80,
    85,
    90,
    40,
    25,
    20,
    15
]

for cpu in traffic_pattern:
    instances = advanced_autoscaler.evaluate(cpu)

    print(
        f"CPU={cpu:>3}% | "
        f"Instances={instances}"
    )

"""
===============================================================================
PART 51: FIVE CHARACTERISTICS IN ONE PRACTICAL EXAMPLE
===============================================================================

Imagine an online shopping platform.

NORMAL TRAFFIC:

    10 application servers

FLASH SALE:

    100 application servers

AFTER SALE:

    15 application servers

Now map the five characteristics.

1. ON-DEMAND SELF-SERVICE

    Infrastructure can be provisioned programmatically.

2. BROAD NETWORK ACCESS

    Customers access the application over networks through browsers,
    mobile applications, and APIs.

3. RESOURCE POOLING

    Provider infrastructure is shared among multiple customers.

4. RAPID ELASTICITY

    Application capacity grows and shrinks according to demand.

5. MEASURED SERVICE

    Compute, storage, networking, and other usage can be measured.

===============================================================================
PART 52: COMMON MISCONCEPTIONS
===============================================================================

MISCONCEPTION #1:

    "Cloud means someone else's computer."

This is an oversimplification.

Cloud computing is an operational and service delivery model involving
automation, abstraction, resource pooling, network access, elasticity, and
measurement.

-------------------------------------------------------------------------------

MISCONCEPTION #2:

    "Cloud automatically means unlimited resources."

False.

Cloud resources are finite.

Providers have:

    - Capacity limits
    - Quotas
    - Regional constraints
    - Service limits
    - Hardware availability

-------------------------------------------------------------------------------

MISCONCEPTION #3:

    "Cloud automatically scales everything."

False.

Elasticity must be configured and designed.

An application may need:

    - Autoscaling
    - Load balancing
    - Stateless design
    - Queue-based architecture
    - Database scaling

-------------------------------------------------------------------------------

MISCONCEPTION #4:

    "Broad network access means everything is public."

False.

Private networking and access controls can restrict resources.

-------------------------------------------------------------------------------

MISCONCEPTION #5:

    "Measured service always means cheap."

False.

Cloud can become expensive if resources are poorly managed.

Examples:

    - Idle servers
    - Excessive storage
    - Large data transfers
    - Unused databases
    - Overprovisioning

-------------------------------------------------------------------------------

MISCONCEPTION #6:

    "Virtual machines are the same as cloud computing."

False.

Virtualization is an enabling technology.

Cloud computing is a broader service delivery model.

===============================================================================
PART 53: TRADITIONAL IT VS CLOUD
===============================================================================

Traditional IT:

    Hardware
        |
        v
    Manual provisioning
        |
        v
    Fixed capacity
        |
        v
    Low flexibility
        |
        v
    Capital expenditure

Cloud:

    API / Console
        |
        v
    Automated provisioning
        |
        v
    Shared resource pool
        |
        v
    Elastic capacity
        |
        v
    Metered consumption

===============================================================================
PART 54: CAPEX VS OPEX
===============================================================================

Traditional infrastructure often involves significant capital expenditure
(CAPEX).

Examples:

    - Servers
    - Storage systems
    - Networking equipment
    - Data center construction

Cloud consumption often shifts more spending toward operational expenditure
(OPEX), though the exact accounting treatment depends on circumstances.

The important conceptual difference is:

    Traditional:
        Purchase infrastructure first.

    Cloud:
        Consume infrastructure as a service.

===============================================================================
PART 55: CLOUD CHARACTERISTICS AND DISTRIBUTED SYSTEMS
===============================================================================

Cloud computing often involves distributed systems.

A distributed application may contain:

    Service A
       |
       v
    Service B
       |
       v
    Service C
       |
       v
    Database

Each component can potentially scale independently.

For example:

    API:
        20 instances

    Worker:
        50 instances

    Database:
        3 nodes

This creates flexibility but also introduces complexity.

Distributed systems must deal with:

    - Network failures
    - Partial failures
    - Latency
    - Consistency
    - Synchronization
    - Retries
    - Duplicate requests
    - Service discovery

===============================================================================
PART 56: IDEMPOTENCY
===============================================================================

Cloud APIs and distributed systems often need idempotent operations.

An operation is idempotent if repeating it produces the same intended result.

For example:

    Create resource with unique request ID.

If the client retries because of a network timeout, the cloud system should
avoid accidentally creating duplicate resources when the operation is meant
to be idempotent.

This becomes especially important in automated provisioning.

===============================================================================
PART 57: EVENT-DRIVEN CLOUD ARCHITECTURE
===============================================================================

Cloud platforms frequently support event-driven architectures.

Example:

    Event
      |
      v
    Message Queue
      |
      v
    Function
      |
      v
    Database

Events can trigger resources automatically.

For example:

    File uploaded
        |
        v
    Event
        |
        v
    Processing function
        |
        v
    Output generated

This demonstrates on-demand execution and elasticity.

===============================================================================
PART 58: SERVERLESS ELASTICITY
===============================================================================

Consider a serverless function.

At 10 requests:

    Function instances:
        1

At 10,000 requests:

    Function instances:
        many

At 0 requests:

    Active execution:
        0

This is an extreme example of elastic resource allocation.

The exact scaling behavior depends on the cloud service.

===============================================================================
PART 59: FINOPS
===============================================================================

FinOps is the practice of managing cloud economics through collaboration
between engineering, finance, and business teams.

Measured service provides the data required for FinOps.

Typical FinOps questions:

    Which team consumed the most resources?

    Which applications are expensive?

    Which resources are idle?

    Are workloads properly sized?

    Can workloads be scheduled differently?

    Are committed pricing options appropriate?

Cloud measurement therefore becomes a business capability, not just a
technical capability.

===============================================================================
PART 60: SUSTAINABILITY
===============================================================================

Cloud resource pooling and efficient utilization can potentially improve
infrastructure utilization.

For example:

    Dedicated servers:
        20% utilization

    Shared infrastructure:
        Provider can aggregate workloads

Higher utilization can reduce wasted capacity, though actual environmental
impact depends on data center efficiency, workload characteristics,
hardware, networking, and energy sources.

Measured service can help organizations monitor resource consumption.

===============================================================================
PART 61: ADVANCED CLOUD ARCHITECTURE
===============================================================================

A modern cloud application may look like:

                       USERS
                         |
                         v
                   DNS / CDN
                         |
                         v
                  Load Balancer
                         |
                         v
                 API Gateway
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          Service A   Service B   Service C
             |           |           |
             +-----------+-----------+
                         |
                  Message Queue
                         |
                         v
                      Workers
                         |
                         v
                      Database
                         |
                         v
                    Object Storage

Supporting systems:

    Identity
    Monitoring
    Logging
    Tracing
    Autoscaling
    Security
    Billing
    Governance
    Infrastructure as Code

The five cloud characteristics operate across this architecture.

===============================================================================
PART 62: MAPPING THE FIVE CHARACTERISTICS TO THE ARCHITECTURE
===============================================================================

ON-DEMAND SELF-SERVICE:

    APIs
    IaC
    CLI
    Cloud console
    Automation

BROAD NETWORK ACCESS:

    Internet
    Private networks
    APIs
    Mobile clients
    Web clients

RESOURCE POOLING:

    Shared compute
    Shared storage
    Shared networking
    Multi-tenancy

RAPID ELASTICITY:

    Autoscaling
    Serverless
    Dynamic workers
    Horizontal scaling

MEASURED SERVICE:

    Metrics
    Usage records
    Billing
    Cost allocation
    Monitoring

===============================================================================
PART 63: INTERVIEW-LEVEL DEFINITIONS
===============================================================================

ON-DEMAND SELF-SERVICE:

    The ability of a cloud consumer to provision computing capabilities
    automatically without requiring human interaction with the provider.

BROAD NETWORK ACCESS:

    Cloud capabilities are available over a network through standard
    mechanisms and can be accessed by diverse client platforms.

RESOURCE POOLING:

    Provider computing resources are pooled to serve multiple consumers,
    with resources dynamically assigned and reassigned according to demand.

RAPID ELASTICITY:

    Capabilities can be rapidly provisioned and released to scale with
    demand, often appearing virtually unlimited to consumers.

MEASURED SERVICE:

    Cloud systems automatically measure, control, and report resource
    consumption to provide transparency and support optimization and
    appropriate charging.

===============================================================================
PART 64: IMPORTANT DISTINCTIONS
===============================================================================

SCALABILITY vs ELASTICITY:

    Scalability:
        Ability to handle growth.

    Elasticity:
        Dynamic adjustment to changing demand.

METERING vs BILLING:

    Metering:
        Measuring usage.

    Billing:
        Converting usage and pricing rules into charges.

VIRTUALIZATION vs CLOUD:

    Virtualization:
        Technology for abstracting physical resources.

    Cloud:
        Service delivery model with broader characteristics.

MULTI-TENANCY vs RESOURCE POOLING:

    Resource pooling:
        Infrastructure is shared and dynamically allocated.

    Multi-tenancy:
        Multiple customers use shared infrastructure with logical isolation.

PUBLIC CLOUD vs BROAD NETWORK ACCESS:

    Public cloud:
        A deployment model.

    Broad network access:
        An essential characteristic.

===============================================================================
PART 65: KNOWLEDGE CHECK
===============================================================================
"""

questions = [
    {
        "question": "Which characteristic allows customers to provision resources themselves?",
        "answer": "On-demand self-service"
    },
    {
        "question": "Which characteristic describes access through networks and standard mechanisms?",
        "answer": "Broad network access"
    },
    {
        "question": "Which characteristic describes shared infrastructure?",
        "answer": "Resource pooling"
    },
    {
        "question": "Which characteristic allows capacity to dynamically grow and shrink?",
        "answer": "Rapid elasticity"
    },
    {
        "question": "Which characteristic involves measuring resource consumption?",
        "answer": "Measured service"
    }
]

print("\nKNOWLEDGE CHECK")

for index, item in enumerate(questions, start=1):
    print(f"{index}. {item['question']}")
    print(f"   Answer: {item['answer']}")

"""
===============================================================================
PART 66: SCENARIO-BASED QUESTIONS
===============================================================================

SCENARIO 1:

A developer logs into a cloud console and creates a virtual machine without
calling the provider's support team.

Characteristic:

    On-demand self-service

-------------------------------------------------------------------------------

SCENARIO 2:

A mobile application, laptop browser, and backend API all access a cloud
service through network interfaces.

Characteristic:

    Broad network access

-------------------------------------------------------------------------------

SCENARIO 3:

Thousands of customers use infrastructure managed by one cloud provider.

Characteristic:

    Resource pooling

-------------------------------------------------------------------------------

SCENARIO 4:

An application automatically increases from 5 instances to 50 instances
during a traffic spike.

Characteristic:

    Rapid elasticity

-------------------------------------------------------------------------------

SCENARIO 5:

A company tracks compute hours, storage usage, and network consumption.

Characteristic:

    Measured service

===============================================================================
PART 67: ADVANCED INTERVIEW QUESTIONS
===============================================================================

Q1. Why is resource pooling important?

Answer:

Resource pooling allows cloud providers to efficiently share infrastructure
among many customers. Dynamic allocation allows capacity to be assigned where
it is needed.

-------------------------------------------------------------------------------

Q2. What makes elasticity different from traditional scaling?

Answer:

Traditional scaling may involve manually adding infrastructure. Elasticity
emphasizes rapid, dynamic provisioning and release according to changing
demand.

-------------------------------------------------------------------------------

Q3. Why is measured service important?

Answer:

It provides visibility into resource consumption, enables monitoring and
optimization, and can support usage-based pricing and cost allocation.

-------------------------------------------------------------------------------

Q4. Does virtualization equal cloud computing?

Answer:

No. Virtualization is a technology that abstracts physical resources.
Cloud computing is a broader service model characterized by self-service,
network access, resource pooling, elasticity, and measurement.

-------------------------------------------------------------------------------

Q5. Is cloud computing always cheaper?

Answer:

No. Cloud can reduce infrastructure management overhead and improve
utilization, but poorly designed workloads can become expensive.

-------------------------------------------------------------------------------

Q6. Why is broad network access important?

Answer:

It allows users and applications to consume cloud capabilities from diverse
client platforms through standardized network mechanisms.

-------------------------------------------------------------------------------

Q7. What technologies support rapid elasticity?

Answer:

Examples include:

    - Autoscaling
    - Load balancing
    - Containers
    - Serverless platforms
    - Infrastructure as Code
    - Monitoring
    - Orchestration systems

-------------------------------------------------------------------------------

Q8. What is multi-tenancy?

Answer:

It is an architecture in which multiple customers share underlying
infrastructure while logical isolation and security boundaries are maintained.

===============================================================================
PART 68: FINAL MENTAL MODEL
===============================================================================

Remember the five characteristics using this sequence:

    ASK
     |
     v
    ACCESS
     |
     v
    SHARE
     |
     v
    SCALE
     |
     v
    MEASURE

Meaning:

    ASK
        On-demand self-service

    ACCESS
        Broad network access

    SHARE
        Resource pooling

    SCALE
        Rapid elasticity

    MEASURE
        Measured service

A complete cloud experience can therefore be understood as:

    "I can request resources myself,
     access them through networks,
     consume resources from a shared pool,
     increase or decrease capacity rapidly,
     and measure what I consume."

===============================================================================
PART 69: FINAL SUMMARY
===============================================================================

The five essential characteristics of cloud computing are fundamental to
understanding why cloud computing differs from traditional infrastructure.

1. ON-DEMAND SELF-SERVICE

   Users can provision resources automatically when needed.

2. BROAD NETWORK ACCESS

   Cloud capabilities are accessible through networks using standard
   mechanisms and diverse client platforms.

3. RESOURCE POOLING

   Providers maintain shared pools of infrastructure and dynamically assign
   resources to multiple customers.

4. RAPID ELASTICITY

   Capacity can rapidly increase or decrease according to workload demand.

5. MEASURED SERVICE

   Resource consumption is measured, monitored, and reported.

Together, these characteristics enable a utility-like computing model.

The deeper cloud architecture built around these characteristics includes:

    APIs
    Automation
    Virtualization
    Containers
    Resource schedulers
    Load balancers
    Autoscaling
    Monitoring
    Metering
    Billing
    IAM
    Networking
    Infrastructure as Code
    Observability
    Governance
    FinOps
    Resilience

The most important conceptual chain is:

    SELF-SERVICE
          |
          v
    REQUEST RESOURCES
          |
          v
    RESOURCE POOL
          |
          v
    DYNAMIC ALLOCATION
          |
          v
    ELASTIC SCALING
          |
          v
    MEASUREMENT
          |
          v
    OPTIMIZATION

This chain explains a large portion of modern cloud architecture.

===============================================================================
END OF CLOUD COMPUTING CHARACTERISTICS GUIDE
===============================================================================
"""
