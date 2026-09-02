"""
HISTORY OF COMPUTING INFRASTRUCTURE
===================================

A structured, self-contained educational program covering:

1. Foundations of computing infrastructure
2. Early computing and mainframes
3. Batch processing and time-sharing
4. Terminals and centralized computing
5. Minicomputers
6. Personal computers and the rise of local computing
7. Local area networks
8. Client-server architecture
9. Enterprise computing
10. Data centers
11. Storage and networking infrastructure
12. Virtualization
13. Distributed computing
14. Clusters
15. High-performance computing
16. Grid computing
17. Service-oriented architecture
18. Web-scale infrastructure
19. Infrastructure automation
20. Utility computing
21. Cloud computing
22. IaaS, PaaS, SaaS
23. Public, private, hybrid and multi-cloud
24. Containers
25. Microservices
26. Infrastructure as Code
27. Software-defined infrastructure
28. Scalability and elasticity
29. Availability and fault tolerance
30. Modern cloud-native infrastructure
31. Historical comparisons and conceptual exercises

The program intentionally uses plain Python data structures and functions.
It does not require external libraries.

The objective is not to simulate an actual data center. The objective is to
represent the major architectural ideas so that the historical transition
from centralized computing to cloud infrastructure can be understood
through executable examples.

Run with:

    python computing_infrastructure_history.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import random


# ============================================================================
# SECTION 1: BASIC CONCEPTS
# ============================================================================

def section(title: str) -> None:
    """Print a major section heading."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def subsection(title: str) -> None:
    """Print a subsection heading."""
    print("\n" + "-" * 80)
    print(title)
    print("-" * 80)


def explain(text: str) -> None:
    """Print explanatory text."""
    print(text)


section("1. WHAT IS COMPUTING INFRASTRUCTURE?")

explain("""
Computing infrastructure is the collection of physical and logical resources
required to run computing workloads.

The physical side includes:

- processors
- memory
- storage devices
- networking equipment
- power systems
- cooling systems
- servers
- racks
- buildings
- backup systems

The logical side includes:

- operating systems
- virtualization
- databases
- middleware
- networking software
- distributed systems
- applications
- management systems
- monitoring systems
- orchestration systems

Computing infrastructure has changed repeatedly because organizations have
continually tried to answer several fundamental questions:

1. Where should computation happen?
2. Where should data be stored?
3. Who should control the hardware?
4. How should users access computing resources?
5. How should systems scale?
6. How should failures be handled?
7. How can expensive hardware be used efficiently?

The history of computing infrastructure is therefore largely a history of
changing the location, ownership, abstraction, and distribution of computing
resources.
""")


# ============================================================================
# SECTION 2: CENTRALIZED COMPUTING
# ============================================================================

section("2. EARLY COMPUTING AND CENTRALIZED ARCHITECTURE")

explain("""
Early electronic computers were enormous machines occupying large physical
spaces. Computing resources were scarce, expensive, and centrally managed.

This naturally produced a centralized architecture.

In a centralized architecture:

    Users
      |
      v
+-------------------+
| Central Computer  |
| CPU               |
| Memory            |
| Storage           |
+-------------------+

The central computer performed most or all computation.

Users did not normally own powerful computing machines. Instead, they accessed
a central system.

This model established one of the most important architectural patterns in
computing:

    many users -> shared computing resource

The idea of sharing a powerful computing system did not disappear with the
development of personal computers. It returned in different forms through
servers, virtualization, and eventually cloud computing.
""")


# ============================================================================
# SECTION 3: MAINFRAMES
# ============================================================================

section("3. MAINFRAME COMPUTING")

explain("""
Mainframes became an important form of enterprise computing.

A mainframe was designed for centralized processing, large transaction
volumes, reliability, and support for many simultaneous users or applications.

Mainframes were particularly important for:

- banking
- government
- insurance
- airlines
- large enterprises
- scientific and business data processing

A mainframe environment often followed this conceptual model:

              +----------------+
              |    Mainframe   |
              |----------------|
              | CPU            |
              | Memory         |
              | Storage        |
              | OS             |
              +-------+--------+
                      |
          +-----------+-----------+
          |           |           |
       Terminal    Terminal    Terminal
          |           |           |
        User        User        User

The terminal was primarily an access device.

The important distinction is:

    Terminal != full independent computer

A traditional terminal could provide input and output while computation
occurred on the central system.

This architecture made sense when computing resources were extremely expensive.

Instead of purchasing a powerful computer for every employee, an organization
could purchase one large system and allow many users to share it.
""")


# ============================================================================
# SECTION 4: BATCH PROCESSING
# ============================================================================

section("4. BATCH PROCESSING")

explain("""
One early operating model was batch processing.

In batch processing, jobs were collected and processed with limited direct
interaction during execution.

Conceptually:

    Input data
        |
        v
    Job queue
        |
        v
    Computer
        |
        v
    Output

A batch job might involve:

- reading a large dataset
- processing records
- performing calculations
- generating reports
- producing output files

The important property was that computation was organized around jobs rather
than continuous interactive sessions.

Batch processing remains relevant today.

Examples include:

- payroll processing
- backups
- ETL pipelines
- large data transformations
- financial settlement
- scheduled reports
- machine learning training jobs
""")


# ============================================================================
# SECTION 5: TIME-SHARING
# ============================================================================

section("5. TIME-SHARING")

explain("""
Time-sharing changed the relationship between users and centralized
computers.

Instead of allowing one job to occupy the machine for an extended period,
the operating system could rapidly switch between users and processes.

Conceptually:

    User A ----\
    User B -----+--> Central CPU
    User C ----/
    User D ----/

The CPU appears to serve users simultaneously because it switches between
tasks very quickly.

A simplified sequence might look like:

    A A A B B C C A A D D B B C C

This is not necessarily true parallel execution. It is controlled sharing of
processing time.

Time-sharing introduced an important infrastructure concept:

    resource multiplexing

Multiple users can share the same underlying resource.

This idea later became extremely important in virtualization and cloud
computing.
""")


# ============================================================================
# SECTION 6: TERMINALS
# ============================================================================

section("6. TERMINALS AND CENTRALIZED ACCESS")

explain("""
Terminals allowed users to interact with centralized computing systems.

A simple terminal model can be represented as:

    keyboard -> central system
    central system -> display

The terminal itself did relatively little computation.

This created a separation between:

    access device
    central computing system

This distinction is historically important because modern cloud computing also
separates the user's device from the infrastructure performing the computation.

A modern laptop may only act as a client to:

- cloud storage
- remote databases
- web applications
- cloud development environments
- hosted AI systems
- remote virtual machines

The hardware is different, but the architectural principle of remote
computation remains recognizable.
""")


# ============================================================================
# SECTION 7: MINICOMPUTERS
# ============================================================================

section("7. MINICOMPUTERS")

explain("""
Minicomputers emerged as smaller and comparatively less expensive systems
than large mainframes.

They were useful for:

- universities
- laboratories
- manufacturing
- engineering
- departments within organizations

They contributed to decentralization.

Instead of:

    entire organization
            |
        mainframe

an organization could begin to have:

    organization
       / | \
      /  |  \
   Dept Dept Dept
    |    |    |
  Computer Computer Computer

This introduced a recurring infrastructure trade-off:

    centralization
        vs.
    decentralization

Centralization simplifies control and resource sharing.

Decentralization can improve local autonomy and reduce dependence on one
central machine.

This tension continues to exist in modern systems.
""")


# ============================================================================
# SECTION 8: PERSONAL COMPUTERS
# ============================================================================

section("8. PERSONAL COMPUTERS")

explain("""
The personal computer changed computing infrastructure dramatically.

Instead of relying completely on a centralized machine, an individual could
own a computer containing:

- CPU
- RAM
- disk
- operating system
- applications
- local files

The architecture shifted toward:

    User
      |
      v
+-------------------+
| Personal Computer |
| CPU               |
| Memory            |
| Storage           |
| Applications      |
+-------------------+

Computing moved closer to the user.

This is an example of decentralization.

The personal computer did not eliminate centralized infrastructure. Instead,
both models began to coexist.
""")


# ============================================================================
# SECTION 9: NETWORKING
# ============================================================================

section("9. NETWORKS CONNECT COMPUTERS")

explain("""
Once computers could communicate over networks, infrastructure became less
dependent on individual machines.

A network allows computing resources to communicate.

    Computer A -----\
    Computer B ------+---- Network ---- Server
    Computer C -----/
    Computer D -----/

Important networking concepts include:

- packets
- addresses
- routing
- switching
- protocols
- bandwidth
- latency
- reliability

Infrastructure evolution cannot be understood without networking.

A computer that cannot communicate effectively with other systems has limited
ability to participate in a distributed environment.

Networking transformed computing from isolated machines into connected
systems.
""")


# ============================================================================
# SECTION 10: LAN
# ============================================================================

section("10. LOCAL AREA NETWORKS")

explain("""
A Local Area Network connects computers within a limited geographical area.

Examples include:

- office networks
- university networks
- laboratory networks
- data center networks

A basic LAN might look like:

        +---------+
        | Switch  |
        +----+----+
             |
      +------+------+
      |      |      |
      PC     PC    Server

The switch provides connectivity between devices.

Once organizations had reliable networks, it became practical to separate
users from the machines that performed particular services.
""")


# ============================================================================
# SECTION 11: CLIENT-SERVER
# ============================================================================

section("11. CLIENT-SERVER ARCHITECTURE")

explain("""
Client-server architecture became a major step away from purely centralized
mainframe interaction.

A client requests a service.

A server provides that service.

    Client
       |
       | Request
       v
    Server
       |
       | Response
       v
    Client

Examples:

- web browser -> web server
- application -> database server
- email client -> mail server
- desktop application -> application server

The client and server can be different computers.

This allows infrastructure to specialize.

Instead of one machine doing everything, different servers can perform
different functions.
""")


# ============================================================================
# SECTION 12: TWO-TIER AND THREE-TIER
# ============================================================================

section("12. TWO-TIER AND THREE-TIER ARCHITECTURES")

explain("""
A two-tier architecture separates the client from the server.

    Client
       |
       v
    Database Server

A three-tier architecture adds an application layer.

    Client
       |
       v
 Presentation Layer
       |
       v
 Application Layer
       |
       v
 Database Layer

This separation improves organization and allows different components to be
scaled or maintained independently.

For example:

    100 clients
        |
        v
    5 application servers
        |
        v
    2 database servers

The infrastructure is no longer a single computer. It is a collection of
specialized machines cooperating through a network.
""")


# ============================================================================
# SECTION 13: ENTERPRISE INFRASTRUCTURE
# ============================================================================

section("13. ENTERPRISE COMPUTING")

explain("""
As organizations became increasingly dependent on information systems,
infrastructure expanded.

A large enterprise environment could contain:

- application servers
- database servers
- file servers
- email systems
- authentication systems
- backup servers
- network switches
- routers
- storage systems
- monitoring systems

A simplified architecture:

             Users
               |
          Network
               |
        Load Balancer
          /       \
     Server       Server
        \          /
         \        /
        Database Cluster
               |
            Storage

The infrastructure became a system of systems.

Managing this environment required:

- system administrators
- network administrators
- database administrators
- security teams
- operations teams
- backup administrators

This operational complexity became one of the forces that eventually
encouraged virtualization and cloud computing.
""")


# ============================================================================
# SECTION 14: DATA CENTERS
# ============================================================================

section("14. DATA CENTERS")

explain("""
A data center is a facility designed to host computing infrastructure.

A data center is not simply a room containing computers.

It requires supporting infrastructure such as:

- electricity
- backup power
- generators
- cooling
- fire protection
- physical security
- network connectivity
- racks
- cabling
- monitoring

A simplified physical model:

    Data Center
    --------------------------------
    | Rack | Rack | Rack | Rack   |
    | Rack | Rack | Rack | Rack   |
    | Rack | Rack | Rack | Rack   |
    --------------------------------
        |      |      |
      Network Power Cooling
""")


# ============================================================================
# SECTION 15: RACK SERVERS
# ============================================================================

section("15. SERVER HARDWARE AND RACKS")

@dataclass
class Server:
    name: str
    cpu_cores: int
    memory_gb: int
    storage_gb: int
    power_watts: int


servers = [
    Server("server-01", 16, 64, 2000, 500),
    Server("server-02", 32, 128, 4000, 650),
    Server("server-03", 64, 256, 8000, 900),
]

for server in servers:
    print(
        f"{server.name}: "
        f"{server.cpu_cores} CPU cores, "
        f"{server.memory_gb} GB RAM, "
        f"{server.storage_gb} GB storage, "
        f"{server.power_watts} W"
    )

explain("""
Modern data centers organize servers into racks.

A rack provides:

- physical organization
- power distribution
- network connectivity
- cooling airflow
- cable management

A data center therefore combines computing resources with facility
engineering.

This is important because infrastructure performance is not determined only
by CPU speed.

A server also depends on:

- power
- temperature
- network bandwidth
- storage performance
- cooling
- physical reliability
""")


# ============================================================================
# SECTION 16: STORAGE
# ============================================================================

section("16. STORAGE INFRASTRUCTURE")

explain("""
Storage evolved from local disks attached to individual machines toward
shared storage systems.

Important storage categories include:

    Local storage
        |
        +-- HDD
        +-- SSD
        +-- NVMe

    Shared storage
        |
        +-- NAS
        +-- SAN

    Distributed storage
        |
        +-- replicated storage
        +-- object storage
        +-- distributed file systems

Local storage is physically associated with a particular machine.

Shared storage allows multiple machines to access common data.

Distributed storage can spread data across multiple machines.
""")


# ============================================================================
# SECTION 17: RAID
# ============================================================================

section("17. RAID AND STORAGE RELIABILITY")

explain("""
RAID stands for Redundant Array of Independent Disks.

RAID techniques use multiple disks to improve:

- redundancy
- performance
- capacity

Different RAID levels use different strategies.

RAID 0:
    Striping without redundancy.

RAID 1:
    Mirroring.

RAID 5:
    Striping with distributed parity.

RAID 6:
    Striping with additional parity.

RAID 10:
    Combination of mirroring and striping.

The important infrastructure principle is:

    redundancy can reduce the effect of hardware failure

But RAID is not the same as backup.

A redundant disk array protects against certain hardware failures.

A backup provides another copy that can be used after:

- accidental deletion
- corruption
- ransomware
- operational mistakes
- catastrophic failures
""")


# ============================================================================
# SECTION 18: NETWORK STORAGE
# ============================================================================

section("18. NAS AND SAN")

explain("""
NAS means Network Attached Storage.

Users or servers access files over a network.

SAN means Storage Area Network.

A SAN provides specialized block-level storage connectivity.

The historical movement is important:

    local disk
       |
       v
    shared storage
       |
       v
 distributed storage

As infrastructure grew, data stopped being tied to a single server.

This made it easier to move workloads between machines.
""")


# ============================================================================
# SECTION 19: VIRTUALIZATION
# ============================================================================

section("19. VIRTUALIZATION")

explain("""
Virtualization is one of the most important transitions in infrastructure
history.

Without virtualization:

    Physical Server
       |
       +-- Application A
       +-- Application B
       +-- Application C

Applications compete for the same operating system and hardware environment.

With virtualization:

             Physical Server
                    |
              Hypervisor
          /        |        \
         /         |         \
       VM1        VM2        VM3
        |          |          |
       OS         OS         OS
        |          |          |
      Apps       Apps       Apps

A virtual machine behaves like an independent computer even though it shares
physical hardware with other virtual machines.
""")


# ============================================================================
# SECTION 20: HYPERVISORS
# ============================================================================

section("20. HYPERVISORS")

explain("""
A hypervisor manages virtual machines.

Two broad categories are commonly discussed.

Type 1:
    Runs directly on physical hardware.

    Hardware
       |
    Hypervisor
      / | \
    VM VM VM

Type 2:
    Runs on top of a host operating system.

    Hardware
       |
    Host OS
       |
    Hypervisor
      / | \
    VM VM VM

Type 1 virtualization is particularly important in server infrastructure
because it allows physical servers to host many independent virtual machines.
""")


# ============================================================================
# SECTION 21: RESOURCE UTILIZATION
# ============================================================================

section("21. WHY VIRTUALIZATION MATTERS")

def utilization(used: float, capacity: float) -> float:
    if capacity <= 0:
        return 0.0
    return used / capacity


physical_servers = 10
average_utilization_without_virtualization = 0.15
total_capacity = physical_servers
used_capacity = total_capacity * average_utilization_without_virtualization

print("Physical servers:", physical_servers)
print("Approximate utilization:", average_utilization_without_virtualization * 100, "%")
print("Used capacity:", used_capacity, "server-equivalents")

explain("""
A traditional server may be purchased for a workload that uses only a small
fraction of its CPU and memory capacity.

Virtualization allows several workloads to share the same physical machine.

For example:

    Physical Server
       |
       +-- VM A = 20%
       +-- VM B = 15%
       +-- VM C = 25%
       +-- VM D = 10%

The physical server can be used more efficiently.

Virtualization therefore provides:

- better hardware utilization
- workload isolation
- easier provisioning
- faster deployment
- migration capabilities
- flexible resource allocation
- improved infrastructure consolidation

Virtualization is an abstraction layer.

The user interacts with a virtual machine rather than directly managing the
physical server.
""")


# ============================================================================
# SECTION 22: SERVER CONSOLIDATION
# ============================================================================

section("22. SERVER CONSOLIDATION")

explain("""
Before virtualization, an organization might have:

    Application A -> Server A
    Application B -> Server B
    Application C -> Server C
    Application D -> Server D

After virtualization:

                Physical Server
                     |
             +-------+-------+
             |       |       |
            VM-A    VM-B    VM-C

Server consolidation reduces:

- hardware count
- physical space
- power consumption
- cooling requirements
- hardware management overhead

The principle is simple:

    fewer physical machines
    + better utilization
    = more efficient infrastructure
""")


# ============================================================================
# SECTION 23: LIVE MIGRATION
# ============================================================================

section("23. VIRTUAL MACHINE MIGRATION")

explain("""
Virtual machines can often be moved between physical hosts.

Conceptually:

       Host A                    Host B
    +----------+              +----------+
    | VM       | ------------>| VM       |
    +----------+              +----------+

Migration can support:

- hardware maintenance
- load balancing
- capacity management
- failure avoidance

This abstraction is historically important.

If software is no longer tightly tied to a physical server, infrastructure
can become more flexible.
""")


# ============================================================================
# SECTION 24: DISTRIBUTED COMPUTING
# ============================================================================

section("24. DISTRIBUTED COMPUTING")

explain("""
Distributed computing uses multiple computers to perform work as part of a
larger system.

Instead of:

    One powerful computer

the system may use:

    Computer A
        |
    Computer B
        |
    Computer C
        |
    Computer D

The machines communicate over a network.

A distributed system therefore introduces problems that do not exist in the
same way on a single machine.

Examples include:

- network latency
- partial failure
- message loss
- clock differences
- inconsistent data
- coordination
- replication
- leader election
- distributed transactions

The major conceptual change is:

    hardware failure becomes expected rather than exceptional
""")


# ============================================================================
# SECTION 25: PARALLELISM
# ============================================================================

section("25. PARALLEL COMPUTING")

explain("""
Parallel computing divides work into pieces that can execute simultaneously.

Suppose a task contains 1,000 independent operations.

A sequential approach might process:

    1 -> 2 -> 3 -> ... -> 1000

A parallel approach could divide the work:

    Worker 1 -> 1..250
    Worker 2 -> 251..500
    Worker 3 -> 501..750
    Worker 4 -> 751..1000

The theoretical speedup is limited by:

- communication
- synchronization
- sequential portions
- uneven workloads
- hardware limitations

This is why simply adding more computers does not automatically produce
linear performance improvement.
""")


# ============================================================================
# SECTION 26: AMDAHL'S LAW
# ============================================================================

section("26. AMDAHL'S LAW")

def amdahl_speedup(parallel_fraction: float, processors: int) -> float:
    """
    Amdahl's Law:

        Speedup = 1 / ((1 - P) + P/N)

    P = fraction of work that can be parallelized
    N = number of processors
    """
    if processors <= 0:
        raise ValueError("Processors must be positive.")

    return 1 / ((1 - parallel_fraction) +
                parallel_fraction / processors)


parallel_fraction = 0.90

for processors in [1, 2, 4, 8, 16, 32]:
    speedup = amdahl_speedup(parallel_fraction, processors)
    print(f"{processors:2d} processors -> theoretical speedup: {speedup:.2f}x")

explain("""
Amdahl's Law demonstrates an important limitation of parallel computing.

If 90% of a workload can be parallelized, the remaining 10% is sequential.

Even with an enormous number of processors, the sequential part limits the
maximum speedup.

The maximum theoretical speedup in this example is approximately:

    1 / 0.10 = 10x

This principle matters when designing distributed infrastructure because
adding machines does not remove algorithmic bottlenecks.
""")


# ============================================================================
# SECTION 27: CLUSTERS
# ============================================================================

section("27. CLUSTER COMPUTING")

explain("""
A cluster is a collection of computers working together.

A simplified cluster:

             Cluster
     ---------------------
     | Node | Node | Node |
     ---------------------
         \      |      /
          \     |     /
             Network

Clusters can be used for:

- high availability
- load balancing
- high-performance computing
- distributed databases
- large-scale data processing

A cluster may be homogeneous or heterogeneous.

The nodes may have:

- identical hardware
- different hardware
- different roles
""")


# ============================================================================
# SECTION 28: HIGH AVAILABILITY
# ============================================================================

section("28. HIGH AVAILABILITY")

@dataclass
class Service:
    name: str
    replicas: int
    failure_probability_per_replica: float


def probability_all_replicas_fail(
    replicas: int,
    failure_probability: float
) -> float:
    return failure_probability ** replicas


service = Service(
    name="web-service",
    replicas=3,
    failure_probability_per_replica=0.01
)

failure_probability = probability_all_replicas_fail(
    service.replicas,
    service.failure_probability_per_replica
)

print(
    f"Probability that all {service.replicas} replicas fail: "
    f"{failure_probability:.8f}"
)

explain("""
Replication can improve availability.

If one server hosts a service:

    Service -> Server A

then failure of Server A can make the service unavailable.

With replication:

    Service
     / | \
    A  B  C

the service may remain available if one machine fails.

This is a central principle in modern infrastructure:

    eliminate single points of failure

But replication introduces additional challenges:

- consistency
- synchronization
- failover
- data duplication
- network partitions
""")


# ============================================================================
# SECTION 29: LOAD BALANCING
# ============================================================================

section("29. LOAD BALANCING")

explain("""
A load balancer distributes incoming requests across multiple servers.

    Clients
       |
       v
+--------------+
| Load Balancer|
+------+-------+
       |
   +---+---+
   |   |   |
  S1  S2  S3

Instead of every request going to one server, requests can be distributed.

Common strategies include:

- round robin
- weighted round robin
- least connections
- least response time
- hash-based routing

Load balancing allows infrastructure to scale horizontally.
""")


def round_robin_servers(
    requests: int,
    server_names: List[str]
) -> Dict[str, int]:

    if not server_names:
        raise ValueError("At least one server is required.")

    distribution = {server: 0 for server in server_names}

    for request_number in range(requests):
        server = server_names[request_number % len(server_names)]
        distribution[server] += 1

    return distribution


distribution = round_robin_servers(
    20,
    ["server-A", "server-B", "server-C"]
)

print("Round-robin request distribution:", distribution)


# ============================================================================
# SECTION 30: HORIZONTAL AND VERTICAL SCALING
# ============================================================================

section("30. SCALING INFRASTRUCTURE")

explain("""
Vertical scaling means increasing the resources of an existing machine.

    Small Server
        |
        v
    Bigger Server

Examples:

- more CPU
- more RAM
- faster storage

Horizontal scaling means adding more machines.

    Server
       |
    Server + Server
       |
    Server + Server + Server

Vertical scaling is often simpler initially.

Horizontal scaling can provide greater capacity and resilience but introduces
distributed-systems complexity.

Modern large-scale systems frequently use horizontal scaling.
""")


# ============================================================================
# SECTION 31: WEB INFRASTRUCTURE
# ============================================================================

section("31. THE RISE OF WEB INFRASTRUCTURE")

explain("""
The growth of the World Wide Web created enormous demand for server
infrastructure.

A simple web request looks like:

    Browser
       |
       | HTTP request
       v
    Web Server
       |
       v
    Application
       |
       v
    Database

As traffic increased, organizations added:

- additional web servers
- caching
- load balancers
- database replicas
- content delivery networks
- distributed storage

Infrastructure became increasingly distributed.
""")


# ============================================================================
# SECTION 32: CACHING
# ============================================================================

section("32. CACHING")

explain("""
A cache stores frequently used information closer to where it is needed.

Without caching:

    Client -> Application -> Database

With caching:

    Client -> Application -> Cache
                              |
                              v
                           Database

If the requested information is already in the cache, the system can avoid
accessing the database.

Caching can reduce:

- latency
- database load
- network traffic
- computation

But caching introduces a difficult problem:

    stale data

A cached value may not immediately reflect the latest source data.
""")


# ============================================================================
# SECTION 33: CONTENT DELIVERY
# ============================================================================

section("33. CONTENT DELIVERY NETWORKS")

explain("""
A Content Delivery Network distributes content across geographically
distributed locations.

Instead of:

    User in India ----\
    User in Europe ----+--> One origin server
    User in USA ------/

a CDN can place content closer to users.

    User -> Nearby Edge Location
                    |
                    v
                  Origin

This reduces latency for static or cacheable content.

The infrastructure principle is:

    move computation or data closer to the consumer
""")


# ============================================================================
# SECTION 34: DISTRIBUTED DATABASES
# ============================================================================

section("34. DISTRIBUTED DATA")

explain("""
As infrastructure became distributed, databases also had to support multiple
machines.

Important techniques include:

- replication
- partitioning
- sharding
- distributed transactions
- consensus
- quorum-based operations

Replication means keeping copies of data.

Partitioning means dividing data into sections.

For example:

    Customers A-H -> Node 1
    Customers I-P -> Node 2
    Customers Q-Z -> Node 3

This allows datasets to exceed the capacity of a single machine.
""")


# ============================================================================
# SECTION 35: SHARDING
# ============================================================================

section("35. SHARDING")

def shard_user(user_id: int, number_of_shards: int) -> int:
    if number_of_shards <= 0:
        raise ValueError("Number of shards must be positive.")

    return user_id % number_of_shards


number_of_shards = 4

for user_id in range(1, 13):
    shard = shard_user(user_id, number_of_shards)
    print(f"User {user_id:2d} -> shard {shard}")

explain("""
Sharding distributes records across multiple machines.

A simple hash or modulo strategy can determine where a record belongs.

Real systems use more sophisticated approaches because naive modulo
partitioning can make scaling difficult.

Changing from four shards to five shards can cause many records to map to
different locations.

This is one reason distributed infrastructure requires careful architecture.
""")


# ============================================================================
# SECTION 36: GRID COMPUTING
# ============================================================================

section("36. GRID COMPUTING")

explain("""
Grid computing connects computing resources that may belong to different
administrative domains.

The goal is to combine distributed resources for large workloads.

Grid computing was especially important in:

- scientific research
- academic computing
- simulations
- large-scale calculations

The concept contributed to a broader understanding that computing capacity
could be assembled from multiple networked systems.
""")


# ============================================================================
# SECTION 37: SERVICE-ORIENTED ARCHITECTURE
# ============================================================================

section("37. SERVICE-ORIENTED ARCHITECTURE")

explain("""
Service-oriented architecture separates application functionality into
services.

For example:

    Order Service
    Payment Service
    Inventory Service
    Customer Service

Each service provides defined functionality.

The broader infrastructure movement was:

    monolithic application
            |
            v
      separate services
            |
            v
   distributed application

This created flexibility but also increased operational complexity.
""")


# ============================================================================
# SECTION 38: INFRASTRUCTURE COMPLEXITY
# ============================================================================

section("38. WHY INFRASTRUCTURE BECAME HARD TO MANAGE")

explain("""
As organizations accumulated servers and applications, infrastructure
management became increasingly complex.

Imagine an organization with:

    5,000 servers
    2,000 applications
    50 databases
    hundreds of network devices

Manual management becomes difficult.

Typical tasks include:

- provisioning servers
- installing operating systems
- configuring networks
- applying patches
- managing storage
- creating backups
- monitoring systems
- replacing failed hardware
- controlling access

This created demand for automation.
""")


# ============================================================================
# SECTION 39: AUTOMATION
# ============================================================================

section("39. INFRASTRUCTURE AUTOMATION")

explain("""
Infrastructure automation means using software to perform infrastructure
operations.

Instead of:

    Human -> manually configure server

the process becomes:

    Configuration -> Automation System -> Server

Automation improves:

- consistency
- repeatability
- speed
- auditability

The infrastructure itself begins to be managed through software.
""")


@dataclass
class Machine:
    name: str
    operating_system: str
    cpu: int
    memory: int
    status: str = "stopped"


def provision_machine(
    name: str,
    operating_system: str,
    cpu: int,
    memory: int
) -> Machine:

    return Machine(
        name=name,
        operating_system=operating_system,
        cpu=cpu,
        memory=memory,
        status="running"
    )


machine = provision_machine(
    "application-server-01",
    "Linux",
    8,
    32
)

print(machine)


# ============================================================================
# SECTION 40: UTILITY COMPUTING
# ============================================================================

section("40. UTILITY COMPUTING")

explain("""
Utility computing introduced a powerful economic and architectural idea:

    computing resources can be consumed as a service

The analogy is electricity.

A customer does not normally construct a power plant to operate a computer.

The customer consumes electricity and pays according to an applicable
pricing model.

Utility computing applies a similar idea to computing:

    infrastructure provider
            |
            v
       computing capacity
            |
            v
          customer

This concept helped prepare the ground for cloud computing.
""")


# ============================================================================
# SECTION 41: CLOUD COMPUTING
# ============================================================================

section("41. THE TRANSITION TO CLOUD COMPUTING")

explain("""
Cloud computing builds on several earlier technologies:

    Mainframes
       |
    Time-sharing
       |
    Networking
       |
    Client-server
       |
    Data centers
       |
    Virtualization
       |
    Distributed systems
       |
    Automation
       |
    Utility computing
       |
    Cloud computing

Cloud computing did not appear from nowhere.

It represents the convergence of many earlier infrastructure ideas.

The major change is the delivery model.

Traditional infrastructure often required an organization to:

    purchase hardware
        |
        v
    install hardware
        |
        v
    configure hardware
        |
        v
    operate hardware

Cloud infrastructure allows users to request computing resources through
software interfaces.

    User
      |
      v
    API / Console
      |
      v
    Cloud Platform
      |
      v
    Compute / Storage / Network
""")


# ============================================================================
# SECTION 42: CLOUD CHARACTERISTICS
# ============================================================================

section("42. IMPORTANT CLOUD CHARACTERISTICS")

explain("""
Cloud computing is generally associated with several characteristics.

On-demand access:
    Resources can be requested when needed.

Resource pooling:
    Provider infrastructure is shared across many customers.

Elasticity:
    Resources can expand or contract according to demand.

Measured usage:
    Consumption can be monitored and billed.

Network access:
    Resources are available through networks.

These characteristics transform infrastructure from a physical asset into a
service-oriented resource.
""")


# ============================================================================
# SECTION 43: INFRASTRUCTURE AS A SERVICE
# ============================================================================

section("43. INFRASTRUCTURE AS A SERVICE")

explain("""
Infrastructure as a Service, or IaaS, provides fundamental infrastructure
resources.

Typical resources include:

- virtual machines
- virtual networks
- storage
- IP addresses
- firewalls
- load balancers

Conceptually:

    Customer
       |
       v
    IaaS API
       |
    +--+-----------+
    |              |
   VM            Storage
    |
 Network

The customer manages much of the operating environment.

The provider manages the underlying physical infrastructure.
""")


# ============================================================================
# SECTION 44: PLATFORM AS A SERVICE
# ============================================================================

section("44. PLATFORM AS A SERVICE")

explain("""
Platform as a Service, or PaaS, abstracts more infrastructure away from the
application developer.

Instead of managing:

- physical servers
- virtual machines
- operating systems
- runtime configuration

the developer focuses more directly on the application.

Conceptually:

    Developer
        |
        v
      PaaS
        |
        v
  Managed Runtime
        |
        v
   Infrastructure

PaaS therefore represents a higher level of abstraction than IaaS.
""")


# ============================================================================
# SECTION 45: SOFTWARE AS A SERVICE
# ============================================================================

section("45. SOFTWARE AS A SERVICE")

explain("""
Software as a Service, or SaaS, provides complete software applications over
a network.

The customer generally does not manage the underlying:

- servers
- operating systems
- storage infrastructure
- application runtime

The customer mainly uses the application.

Examples of the conceptual hierarchy:

    SaaS
      |
    Application

    PaaS
      |
    Application Platform

    IaaS
      |
    Virtual Infrastructure

The higher the abstraction, the less physical infrastructure the customer
needs to manage directly.
""")


# ============================================================================
# SECTION 46: RESPONSIBILITY MODEL
# ============================================================================

section("46. SHARED RESPONSIBILITY")

explain("""
Cloud infrastructure does not mean that the provider is responsible for
everything.

Responsibilities are divided between provider and customer.

A simplified model:

    Physical hardware
        -> Provider

    Data center
        -> Provider

    Virtualization platform
        -> Usually provider

    Operating system
        -> Depends on service model

    Application
        -> Customer

    Data
        -> Customer responsibility

    Identity and access configuration
        -> Customer responsibility

The exact boundary depends on the service being used.
""")


# ============================================================================
# SECTION 47: PUBLIC, PRIVATE, HYBRID
# ============================================================================

section("47. CLOUD DEPLOYMENT MODELS")

explain("""
Public cloud:

    Provider-owned infrastructure
             |
          Customers

Private cloud:

    Organization-owned or dedicated
             |
        Internal users

Hybrid cloud:

    Private environment
           |
         Bridge
           |
    Public cloud

Multi-cloud:

    Cloud A
       \
        +---- Organization
       /
    Cloud B

These models reflect different requirements around:

- control
- cost
- compliance
- performance
- portability
- operational complexity
""")


# ============================================================================
# SECTION 48: MULTI-TENANCY
# ============================================================================

section("48. MULTI-TENANCY")

explain("""
Cloud platforms commonly serve multiple customers using shared physical
infrastructure.

Conceptually:

        Physical Infrastructure
              |
      +-------+-------+
      |       |       |
   Tenant A Tenant B Tenant C

Isolation is required so that one tenant cannot improperly access another
tenant's resources.

Virtualization, identity controls, networking, storage isolation, and
encryption can all contribute to tenant separation.

Multi-tenancy is one of the reasons cloud providers can achieve large-scale
resource utilization.
""")


# ============================================================================
# SECTION 49: CONTAINERS
# ============================================================================

section("49. CONTAINERS")

explain("""
Containers provide operating-system-level isolation for applications.

A simplified model:

        Host Operating System
                 |
        Container Runtime
        /        |        \
    App A      App B      App C

Unlike traditional virtual machines, containers commonly share the host
kernel.

Conceptually:

Virtual machines:

    Hardware
       |
    Hypervisor
     /  |  \
   VM  VM  VM
   OS  OS  OS

Containers:

    Hardware
       |
    Host OS
       |
 Container Runtime
   /     |     \
 App    App    App

Containers are generally lighter than full virtual machines because they do
not normally require a complete guest operating system for each application.
""")


# ============================================================================
# SECTION 50: CONTAINERIZATION
# ============================================================================

section("50. WHY CONTAINERS MATTER")

explain("""
Containers help package applications with their dependencies.

A conceptual application package might contain:

    Application
    Libraries
    Runtime dependencies
    Configuration

This reduces the classic problem:

    "It works on my machine."

The application environment becomes more reproducible.

Containers also support:

- fast deployment
- process isolation
- portability
- application packaging
- scaling
- automated deployment
""")


# ============================================================================
# SECTION 51: ORCHESTRATION
# ============================================================================

section("51. CONTAINER ORCHESTRATION")

explain("""
Running one container is relatively simple.

Running thousands of containers is an infrastructure problem.

An orchestration system can manage:

- scheduling
- service discovery
- scaling
- health checks
- rolling deployments
- networking
- recovery

Conceptually:

                Orchestrator
                 /    |    \
                /     |     \
           Node A   Node B   Node C
            /  \      |      /  \
          App  App   App    App  App

The infrastructure becomes programmable.
""")


# ============================================================================
# SECTION 52: MICROSERVICES
# ============================================================================

section("52. MICROSERVICES")

explain("""
Microservices architecture decomposes an application into smaller services.

Example:

    E-commerce System
       |
       +-- User Service
       +-- Product Service
       +-- Order Service
       +-- Payment Service
       +-- Notification Service

Each service can potentially be deployed and scaled independently.

This can improve organizational and deployment flexibility.

But it also creates more distributed-system problems:

- network failures
- service discovery
- distributed tracing
- authentication
- data consistency
- monitoring
- deployment coordination
""")


# ============================================================================
# SECTION 53: INFRASTRUCTURE AS CODE
# ============================================================================

section("53. INFRASTRUCTURE AS CODE")

explain("""
Infrastructure as Code means representing infrastructure configuration using
machine-readable definitions.

Instead of:

    Engineer manually creates server

the process becomes:

    Configuration file
            |
            v
    Infrastructure tool
            |
            v
    Resources created

Benefits include:

- repeatability
- version control
- reviewability
- automation
- consistency
- reproducibility

Infrastructure becomes something that can be treated similarly to software
source code.
""")


@dataclass
class InfrastructureDefinition:
    name: str
    cpu: int
    memory: int
    replicas: int
    network: str


infrastructure = InfrastructureDefinition(
    name="web-application",
    cpu=4,
    memory=16,
    replicas=3,
    network="private-network"
)

print("Infrastructure definition:")
print(infrastructure)


# ============================================================================
# SECTION 54: SOFTWARE-DEFINED INFRASTRUCTURE
# ============================================================================

section("54. SOFTWARE-DEFINED INFRASTRUCTURE")

explain("""
Traditional infrastructure depends heavily on manually configured physical
components.

Software-defined infrastructure abstracts physical resources and exposes
them through software.

Examples of programmable resources include:

- virtual networks
- virtual machines
- storage volumes
- security policies
- load balancers

This leads to an important historical transition:

    hardware-defined infrastructure
                |
                v
    software-controlled infrastructure

Cloud computing depends heavily on this abstraction.
""")


# ============================================================================
# SECTION 55: API-DRIVEN INFRASTRUCTURE
# ============================================================================

section("55. API-DRIVEN COMPUTING")

explain("""
Modern infrastructure is frequently controlled through APIs.

A simplified sequence:

    Application
        |
        | API request
        v
    Infrastructure Platform
        |
        v
    Resource created

For example, a system might request:

    Create virtual machine
    Create storage volume
    Create network
    Attach storage
    Configure firewall

The physical infrastructure is hidden behind an abstraction layer.
""")


# ============================================================================
# SECTION 56: ELASTICITY
# ============================================================================

section("56. ELASTICITY")

explain("""
Elasticity means that resources can change according to demand.

Suppose traffic changes:

    Low traffic
        |
        v
      2 servers

    High traffic
        |
        v
     20 servers

    Traffic decreases
        |
        v
      3 servers

The ability to dynamically change capacity is one of the major differences
between traditional fixed infrastructure and modern cloud environments.
""")


def required_servers(
    requests_per_second: int,
    capacity_per_server: int
) -> int:

    if capacity_per_server <= 0:
        raise ValueError("Capacity must be positive.")

    return math.ceil(requests_per_second / capacity_per_server)


for traffic in [100, 500, 1000, 2500, 5000]:
    servers_needed = required_servers(traffic, 500)
    print(
        f"{traffic:4d} requests/sec -> "
        f"{servers_needed} servers"
    )


# ============================================================================
# SECTION 57: AUTOSCALING
# ============================================================================

section("57. AUTOSCALING")

explain("""
Autoscaling automatically changes resource capacity according to predefined
conditions.

For example:

    CPU > 70%
        |
        v
    Add server

    CPU < 30%
        |
        v
    Remove server

Autoscaling combines:

- monitoring
- policy
- provisioning
- scheduling
- resource management

This is one of the clearest examples of infrastructure becoming software
controlled.
""")


# ============================================================================
# SECTION 58: AVAILABILITY
# ============================================================================

section("58. AVAILABILITY AND DOWNTIME")

def availability_percentage(
    total_minutes: float,
    downtime_minutes: float
) -> float:

    if total_minutes <= 0:
        raise ValueError("Total time must be positive.")

    return (
        (total_minutes - downtime_minutes)
        / total_minutes
    ) * 100


days_in_year = 365
minutes_in_year = days_in_year * 24 * 60

for downtime in [525.6, 52.56, 5.256]:
    availability = availability_percentage(
        minutes_in_year,
        downtime
    )

    print(
        f"{downtime:.3f} minutes downtime/year "
        f"-> {availability:.5f}% availability"
    )

explain("""
Availability is commonly expressed as the percentage of time a service is
operational.

The basic formula is:

    Availability =
        (Total Time - Downtime) / Total Time

High availability requires more than good hardware.

It may require:

- redundancy
- failover
- monitoring
- backups
- geographically distributed systems
- reliable networking
- automated recovery
""")


# ============================================================================
# SECTION 59: FAULT TOLERANCE
# ============================================================================

section("59. FAULT TOLERANCE")

explain("""
Fault tolerance means designing a system so that certain failures do not
cause unacceptable service interruption.

Possible failure domains include:

    Process
      |
    Server
      |
    Rack
      |
    Power source
      |
    Network switch
      |
    Data center
      |
    Region

A robust infrastructure design considers which failure it is expected to
survive.

Redundancy at one level does not necessarily protect against failures at
another level.
""")


# ============================================================================
# SECTION 60: DISASTER RECOVERY
# ============================================================================

section("60. DISASTER RECOVERY")

explain("""
Disaster recovery concerns restoring systems after major disruption.

Potential events include:

- data center failure
- natural disaster
- major network failure
- destructive software incident
- storage failure
- operational error

Important concepts include:

RPO:
    Recovery Point Objective

RTO:
    Recovery Time Objective

RPO asks:

    How much data loss can be tolerated?

RTO asks:

    How quickly must the service be restored?

These concepts influence:

- backup frequency
- replication
- geographic redundancy
- recovery architecture
""")


# ============================================================================
# SECTION 61: DATA CENTER TO CLOUD
# ============================================================================

section("61. THE INFRASTRUCTURE EVOLUTION")

explain("""
The historical progression can be represented as:

    Mainframe
       |
       v
    Time-sharing
       |
       v
    Minicomputer
       |
       v
    Personal Computer
       |
       v
    Local Networks
       |
       v
    Client-Server
       |
       v
    Enterprise Data Centers
       |
       v
    Virtualization
       |
       v
    Distributed Computing
       |
       v
    Web-Scale Infrastructure
       |
       v
    Infrastructure Automation
       |
       v
    Cloud Computing
       |
       v
    Containers and Cloud-Native Systems

Each stage did not completely replace the previous one.

Mainframes still exist.

Data centers still exist.

Virtual machines still exist.

Client-server architecture still exists.

Cloud infrastructure itself is implemented using physical data centers.

The important change is the abstraction and delivery model.
""")


# ============================================================================
# SECTION 62: PHYSICAL TO LOGICAL ABSTRACTION
# ============================================================================

section("62. THE RISE OF ABSTRACTION")

explain("""
One of the deepest themes in computing infrastructure history is abstraction.

Early computing:

    User -> Physical Machine

Later:

    User -> Operating System -> Hardware

Virtualized:

    User -> Virtual Machine -> Hypervisor -> Hardware

Cloud:

    User -> API -> Virtual Resource -> Physical Infrastructure

Containerized:

    User -> Container -> Host OS -> Hardware

The user increasingly interacts with logical resources rather than physical
machines.

This abstraction enables infrastructure to be:

- programmable
- portable
- scalable
- automated
- reusable
""")


# ============================================================================
# SECTION 63: RESOURCE POOLING
# ============================================================================

section("63. RESOURCE POOLING")

explain("""
Resource pooling means combining infrastructure into a shared pool.

Instead of assigning one physical server permanently to one workload:

    Server A -> Application A
    Server B -> Application B

a resource pool may contain:

    Server A
    Server B
    Server C
    Server D

Workloads can be placed where capacity is available.

This is a major principle behind:

- virtualization clusters
- cloud platforms
- distributed storage
- container clusters
""")


# ============================================================================
# SECTION 64: SCHEDULING
# ============================================================================

section("64. RESOURCE SCHEDULING")

@dataclass
class Workload:
    name: str
    cpu_required: int
    memory_required: int


@dataclass
class Host:
    name: str
    cpu_capacity: int
    memory_capacity: int
    workloads: List[Workload] = field(default_factory=list)

    @property
    def cpu_used(self) -> int:
        return sum(w.cpu_required for w in self.workloads)

    @property
    def memory_used(self) -> int:
        return sum(w.memory_required for w in self.workloads)

    def can_host(self, workload: Workload) -> bool:
        return (
            self.cpu_used + workload.cpu_required
            <= self.cpu_capacity
            and
            self.memory_used + workload.memory_required
            <= self.memory_capacity
        )

    def add_workload(self, workload: Workload) -> bool:
        if self.can_host(workload):
            self.workloads.append(workload)
            return True
        return False


hosts = [
    Host("host-1", 16, 64),
    Host("host-2", 16, 64),
]

workloads = [
    Workload("web-1", 4, 16),
    Workload("web-2", 4, 16),
    Workload("database-1", 8, 32),
    Workload("worker-1", 4, 8),
]

for workload in workloads:
    placed = False

    for host in hosts:
        if host.add_workload(workload):
            print(f"{workload.name} placed on {host.name}")
            placed = True
            break

    if not placed:
        print(f"{workload.name} could not be placed")


# ============================================================================
# SECTION 65: CAPACITY PLANNING
# ============================================================================

section("65. CAPACITY PLANNING")

explain("""
Capacity planning attempts to answer:

    How much infrastructure will be required?

Factors include:

- expected traffic
- CPU requirements
- memory requirements
- storage growth
- network bandwidth
- redundancy requirements
- peak demand
- future growth

Traditional infrastructure often required capacity to be purchased before
demand arrived.

This creates a problem.

If demand is underestimated:

    insufficient capacity

If demand is overestimated:

    unused capacity

Cloud elasticity attempts to reduce this mismatch.
""")


# ============================================================================
# SECTION 66: OVERPROVISIONING
# ============================================================================

section("66. OVERPROVISIONING")

explain("""
Organizations traditionally overprovisioned infrastructure to handle peak
demand.

Suppose average traffic is:

    1,000 requests/sec

but peak traffic is:

    10,000 requests/sec

A fixed infrastructure design might need to support 10,000 requests/sec even
when most of the day requires much less.

This means resources remain unused during normal periods.

Virtualization and cloud elasticity provide ways to improve utilization.
""")


# ============================================================================
# SECTION 67: ECONOMICS OF INFRASTRUCTURE
# ============================================================================

section("67. CAPITAL EXPENDITURE AND OPERATING EXPENDITURE")

explain("""
Traditional infrastructure often requires significant capital expenditure.

Examples:

- servers
- storage
- networking
- buildings
- cooling
- power systems

This is commonly associated with CapEx.

Cloud services shift much of the spending toward operational consumption,
commonly associated with OpEx.

The economic difference can be simplified as:

Traditional:

    Buy hardware
        |
    Own capacity
        |
    Operate capacity

Cloud:

    Request capacity
        |
    Consume capacity
        |
    Pay according to service model

This is not merely an accounting distinction. It changes how organizations
plan and acquire computing resources.
""")


# ============================================================================
# SECTION 68: MULTIPLEXING AND SHARING
# ============================================================================

section("68. THE RECURRING IDEA OF SHARED COMPUTING")

explain("""
Several historical technologies appear different but implement a related
idea.

Mainframe time-sharing:

    many users -> one large machine

Virtualization:

    many VMs -> one physical server

Cloud:

    many customers -> shared provider infrastructure

Containerization:

    many isolated workloads -> shared operating system

The recurring principle is:

    share expensive infrastructure while maintaining useful isolation

This principle is central to the economics of modern computing.
""")


# ============================================================================
# SECTION 69: ISOLATION
# ============================================================================

section("69. COMPUTING ISOLATION")

explain("""
Isolation allows workloads to share hardware without behaving as if they are
one unrestricted process.

Isolation can occur at multiple levels:

    Process isolation
    Container isolation
    Virtual machine isolation
    Network isolation
    Storage isolation
    Identity isolation

The stronger the isolation requirement, the more infrastructure and
performance considerations may be involved.

Cloud platforms depend heavily on effective isolation.
""")


# ============================================================================
# SECTION 70: LATENCY
# ============================================================================

section("70. LATENCY AS AN INFRASTRUCTURE CONSTRAINT")

explain("""
Latency is the time required for an operation or communication to complete.

In centralized systems:

    User
      |
      v
    Central system

In distributed systems:

    User
      |
      v
    Service A
      |
      v
    Service B
      |
      v
    Database
      |
      v
    Service C

Each network interaction can introduce latency.

As systems become more distributed, architecture must consider:

- network distance
- serialization
- routing
- congestion
- processing time
- storage latency

Distributed computing provides scalability and resilience but makes
communication more complicated.
""")


# ============================================================================
# SECTION 71: CONSISTENCY
# ============================================================================

section("71. CONSISTENCY IN DISTRIBUTED SYSTEMS")

explain("""
When data exists on multiple machines, the copies may not immediately agree.

Example:

    Database A -> balance = 100
    Database B -> balance = 100

A transaction changes one copy:

    Database A -> balance = 50
    Database B -> balance = 100

The system now needs mechanisms to propagate the change.

Distributed systems therefore deal with concepts such as:

- strong consistency
- eventual consistency
- replication
- consensus
- quorum
- conflict resolution

The historical movement toward distributed infrastructure therefore created
new theoretical and engineering problems.
""")


# ============================================================================
# SECTION 72: CAPACITY VS RELIABILITY
# ============================================================================

section("72. SCALABILITY, AVAILABILITY, AND CONSISTENCY")

explain("""
Modern infrastructure often balances several goals.

Scalability:
    Can the system handle more workload?

Availability:
    Does the system remain operational?

Consistency:
    Do distributed copies of data behave according to required guarantees?

Performance:
    How quickly does the system respond?

Cost:
    How much infrastructure is required?

Security:
    Can resources and data be protected?

These goals can conflict.

For example, adding replicas may improve availability but can increase
synchronization and operational complexity.
""")


# ============================================================================
# SECTION 73: CLOUD-NATIVE INFRASTRUCTURE
# ============================================================================

section("73. CLOUD-NATIVE INFRASTRUCTURE")

explain("""
Cloud-native systems generally take advantage of:

- containers
- orchestration
- APIs
- automation
- immutable infrastructure
- microservices
- observability
- continuous delivery
- elastic scaling

The important idea is not simply "running software in a cloud."

Cloud-native architecture designs software and infrastructure around
automation, distribution, resilience, and dynamic resource management.
""")


# ============================================================================
# SECTION 74: IMMUTABLE INFRASTRUCTURE
# ============================================================================

section("74. IMMUTABLE INFRASTRUCTURE")

explain("""
In mutable infrastructure, an existing server is repeatedly changed.

Example:

    Server
      |
    update
      |
    update
      |
    update

Over time, manual changes can make systems difficult to reproduce.

Immutable infrastructure uses replacement rather than repeated modification.

Conceptually:

    Old server
        |
        X

    New server
        |
        v
    New configuration

This makes infrastructure states easier to reproduce and reason about.
""")


# ============================================================================
# SECTION 75: OBSERVABILITY
# ============================================================================

section("75. OBSERVABILITY")

explain("""
Modern distributed infrastructure requires visibility into system behavior.

Important sources include:

Metrics:
    numerical measurements

Logs:
    event records

Traces:
    request paths across distributed services

For example:

    User Request
        |
        v
    Service A
        |
        v
    Service B
        |
        v
    Database

Tracing can help identify where time is being spent.

Monitoring infrastructure is therefore a necessary part of operating
distributed systems.
""")


# ============================================================================
# SECTION 76: SECURITY EVOLUTION
# ============================================================================

section("76. INFRASTRUCTURE SECURITY")

explain("""
Security requirements evolved alongside infrastructure.

Traditional physical infrastructure emphasized:

- physical access
- perimeter security
- network controls
- server hardening

Distributed and cloud infrastructure adds:

- identity and access management
- API security
- encryption
- secrets management
- workload isolation
- network segmentation
- continuous monitoring
- configuration security

The security boundary is no longer simply the physical data center.
""")


# ============================================================================
# SECTION 77: NETWORK VIRTUALIZATION
# ============================================================================

section("77. NETWORK VIRTUALIZATION")

explain("""
Traditional networks rely heavily on physical devices.

Modern infrastructure can create logical networks using software.

Conceptually:

    Physical Network
          |
          v
    Virtual Network
       /       \
    Subnet A  Subnet B

Virtual networks can provide:

- segmentation
- routing
- isolation
- virtual firewalls
- software-defined connectivity

This follows the same historical pattern as server virtualization:

    physical resource
          |
          v
    logical abstraction
          |
          v
    programmable control
""")


# ============================================================================
# SECTION 78: STORAGE VIRTUALIZATION
# ============================================================================

section("78. STORAGE VIRTUALIZATION")

explain("""
Storage virtualization separates logical storage from the exact physical
devices holding the data.

A user might see:

    volume-001

without knowing whether its data resides on:

    disk A
    disk B
    disk C
    replicated storage
    distributed storage

This abstraction makes storage easier to allocate and manage.
""")


# ============================================================================
# SECTION 79: COMPUTE, NETWORK, STORAGE
# ============================================================================

section("79. THE THREE CORE INFRASTRUCTURE DOMAINS")

explain("""
Most infrastructure can be understood through three fundamental domains.

Compute:
    CPU and memory used to execute programs.

Storage:
    systems used to retain data.

Network:
    systems used to connect computing resources.

A cloud platform essentially turns these physical domains into programmable
services.

    Compute -> Virtual machines / containers
    Storage -> Volumes / object storage
    Network -> Virtual networks / load balancers
""")


# ============================================================================
# SECTION 80: A COMPLETE HISTORICAL ARCHITECTURE
# ============================================================================

section("80. FROM MAINFRAME TO CLOUD")

explain("""
Consider the evolution of an organization's computing environment.

STAGE 1: MAINFRAME

    Users
      |
    Terminals
      |
    Mainframe


STAGE 2: CLIENT-SERVER

    Clients
     / | \
    /  |  \
   Server Farm
       |
    Database


STAGE 3: DATA CENTER

    Users
      |
    Network
      |
    Load Balancer
     /       \
   Server   Server
      \      /
       Database
          |
        Storage


STAGE 4: VIRTUALIZED DATA CENTER

    Physical Hosts
        |
    Hypervisors
     /   |   \
   VM   VM   VM
    |    |    |
 Services and Applications


STAGE 5: DISTRIBUTED INFRASTRUCTURE

    Node A ---- Node B
      |           |
      +----+------+
           |
         Node C


STAGE 6: CLOUD

    User
      |
    API
      |
    Cloud Control Plane
      |
    +----+----+--------+
    |         |        |
  Compute   Storage  Network
    |
  Virtualized Resources


STAGE 7: CLOUD-NATIVE

    User
      |
    Application
      |
    Services
      |
    Containers
      |
    Orchestrator
      |
    Virtual Infrastructure
      |
    Physical Data Centers

The physical infrastructure has not disappeared.

It has become increasingly abstracted, automated, pooled, and programmable.
""")


# ============================================================================
# SECTION 81: CONTROL PLANE AND DATA PLANE
# ============================================================================

section("81. CONTROL PLANE AND DATA PLANE")

explain("""
Modern infrastructure often separates control from execution.

Control plane:

    decides what should happen

Data plane:

    performs the actual work

Example:

    Control Plane
         |
         | Create server
         v
    Infrastructure
         |
         v
    Running workload

In a cloud platform, APIs and management systems form part of the control
plane, while compute, networking, and storage resources form the execution
environment.

This distinction becomes increasingly important as infrastructure becomes
programmable.
""")


# ============================================================================
# SECTION 82: RESOURCE ABSTRACTION LEVELS
# ============================================================================

section("82. LEVELS OF INFRASTRUCTURE ABSTRACTION")

abstraction_levels = [
    "Physical hardware",
    "Operating system",
    "Virtual machine",
    "Container",
    "Managed platform",
    "Application service",
]

for level, name in enumerate(abstraction_levels, start=1):
    print(f"{level}. {name}")

explain("""
Moving upward generally means:

    less direct infrastructure control
    more abstraction
    easier consumption

Moving downward generally means:

    more control
    more responsibility
    more infrastructure detail

The trade-off is not simply better versus worse.

A database administrator may need detailed control.

An application developer may prefer a managed service.

An infrastructure architect chooses the abstraction level according to the
requirements of the workload.
""")


# ============================================================================
# SECTION 83: MONOLITH TO DISTRIBUTED SYSTEM
# ============================================================================

section("83. APPLICATION ARCHITECTURE EVOLUTION")

explain("""
A simplified historical application progression is:

    Monolithic application
            |
            v
      Client-server
            |
            v
    Multi-tier application
            |
            v
     Service-oriented
            |
            v
      Microservices
            |
            v
    Cloud-native services

Each step introduces more separation.

Separation can provide:

- independent scaling
- independent deployment
- organizational boundaries
- technology flexibility

But separation also introduces:

- network calls
- service dependencies
- distributed failures
- monitoring requirements
- operational complexity
""")


# ============================================================================
# SECTION 84: SERVERLESS
# ============================================================================

section("84. SERVERLESS COMPUTING")

explain("""
Serverless computing is another abstraction layer.

The user provides application logic while the platform manages much of the
underlying server infrastructure.

Conceptually:

    Developer
        |
      Function
        |
    Serverless Platform
        |
    Infrastructure

The term does not mean servers literally disappear.

Servers still execute the workload.

The difference is that the customer does not directly manage those servers.
""")


# ============================================================================
# SECTION 85: EVENT-DRIVEN INFRASTRUCTURE
# ============================================================================

section("85. EVENT-DRIVEN SYSTEMS")

explain("""
Modern distributed systems often use events.

Example:

    User places order
          |
          v
      Order Event
       /       \
      /         \
Inventory     Payment
   |              |
   v              v
Update          Process

This reduces direct coupling between components.

But it introduces questions around:

- event ordering
- duplicate messages
- retries
- delivery guarantees
- idempotency
- eventual consistency
""")


# ============================================================================
# SECTION 86: INFRASTRUCTURE FAILURE SIMULATION
# ============================================================================

section("86. SIMPLE FAILURE SIMULATION")

def simulate_failures(
    servers: List[str],
    failure_probability: float
) -> Tuple[List[str], List[str]]:

    failed = []
    healthy = []

    for server in servers:
        if random.random() < failure_probability:
            failed.append(server)
        else:
            healthy.append(server)

    return healthy, failed


random.seed(42)

server_names = [
    "server-1",
    "server-2",
    "server-3",
    "server-4",
    "server-5",
]

healthy, failed = simulate_failures(
    server_names,
    0.20
)

print("Healthy servers:", healthy)
print("Failed servers:", failed)

explain("""
Distributed infrastructure assumes that components can fail.

The system must therefore distinguish between:

    failure of a component

and:

    failure of the entire service

A service with multiple replicas may continue operating even when individual
components fail.

This is one of the fundamental reasons for distributed redundancy.
""")


# ============================================================================
# SECTION 87: FAILURE DOMAINS
# ============================================================================

section("87. FAILURE DOMAINS")

failure_domains = {
    "process": "Application process stops",
    "server": "Physical or virtual server fails",
    "rack": "Rack-level infrastructure fails",
    "zone": "Availability zone or facility segment fails",
    "region": "Geographic region becomes unavailable",
}

for domain, description in failure_domains.items():
    print(f"{domain:10s}: {description}")

explain("""
A system designed to survive server failure is not automatically designed to
survive a complete data center failure.

Resilience must be designed at the appropriate failure domain.
""")


# ============================================================================
# SECTION 88: MONOLITHIC DATA CENTER VS CLOUD
# ============================================================================

section("88. TRADITIONAL DATA CENTER VS CLOUD INFRASTRUCTURE")

comparison = {
    "Hardware ownership": (
        "Organization commonly owns or leases hardware",
        "Provider commonly owns underlying hardware"
    ),
    "Provisioning": (
        "Often slower and hardware-dependent",
        "Usually software/API-driven"
    ),
    "Capacity": (
        "Often fixed or planned in advance",
        "Can be dynamically adjusted"
    ),
    "Resource abstraction": (
        "Lower abstraction",
        "Higher abstraction"
    ),
    "Scaling": (
        "Requires infrastructure planning",
        "Can often be automated"
    ),
    "Operations": (
        "Organization manages physical environment",
        "Provider manages underlying facility"
    ),
}

for topic, values in comparison.items():
    print(f"\n{topic}")
    print("  Traditional:", values[0])
    print("  Cloud:      ", values[1])


# ============================================================================
# SECTION 89: HISTORICAL CAUSE AND EFFECT
# ============================================================================

section("89. CAUSE AND EFFECT IN INFRASTRUCTURE EVOLUTION")

explain("""
The evolution can be understood through recurring problems and solutions.

PROBLEM:
Computers are expensive.

RESPONSE:
Share centralized computers.

PROBLEM:
Users need interactive access.

RESPONSE:
Time-sharing and terminals.

PROBLEM:
Organizations need local computing.

RESPONSE:
Minicomputers and personal computers.

PROBLEM:
Computers need to communicate.

RESPONSE:
Networking and LANs.

PROBLEM:
Applications need centralized services.

RESPONSE:
Client-server architecture.

PROBLEM:
Organizations accumulate large amounts of infrastructure.

RESPONSE:
Data centers.

PROBLEM:
Physical servers are underutilized.

RESPONSE:
Virtualization.

PROBLEM:
Applications require greater scale and resilience.

RESPONSE:
Clusters and distributed computing.

PROBLEM:
Infrastructure becomes difficult to manage manually.

RESPONSE:
Automation and APIs.

PROBLEM:
Organizations need flexible computing capacity.

RESPONSE:
Utility computing and cloud computing.

PROBLEM:
Applications need rapid, automated deployment.

RESPONSE:
Containers, orchestration, Infrastructure as Code, and cloud-native
architecture.
""")


# ============================================================================
# SECTION 90: KEY DISTINCTIONS
# ============================================================================

section("90. IMPORTANT CONCEPTUAL DISTINCTIONS")

distinctions = [
    ("Mainframe", "Large centralized computing system"),
    ("Client", "System requesting a service"),
    ("Server", "System providing a service"),
    ("Data center", "Facility hosting computing infrastructure"),
    ("Virtual machine", "Software-defined computer running on shared hardware"),
    ("Hypervisor", "Software layer managing virtual machines"),
    ("Cluster", "Group of computers working together"),
    ("Distributed system", "System whose components execute across networked machines"),
    ("Cloud", "Service-oriented delivery of pooled computing resources"),
    ("Container", "Isolated application environment sharing a host kernel"),
    ("Elasticity", "Ability to dynamically change resource capacity"),
    ("Scalability", "Ability to handle increasing workload"),
    ("Availability", "Ability to remain operational"),
    ("Redundancy", "Multiple components providing protection against failure"),
    ("Automation", "Software-controlled infrastructure management"),
    ("Infrastructure as Code", "Infrastructure represented through declarative or programmable definitions"),
]

for concept, definition in distinctions:
    print(f"{concept:28s} -> {definition}")


# ============================================================================
# SECTION 91: SIMPLE INFRASTRUCTURE DESIGN
# ============================================================================

section("91. BUILDING A MODERN WEB INFRASTRUCTURE")

explain("""
Suppose an organization operates a web application.

A basic infrastructure might contain:

                    Internet
                       |
                       v
                 Load Balancer
                    /     \
                   /       \
             Web Server   Web Server
                   \       /
                    \     /
                  Application
                       |
                       v
                    Database
                       |
                       v
                    Storage

To make the architecture more resilient:

                    Internet
                       |
                       v
                 Load Balancer
                    /     \
                   /       \
              Server A   Server B
                  |          |
                  +----+-----+
                       |
                  Database
                   /     \
                  /       \
              Replica   Replica
                       |
                    Storage

Then virtualization may be introduced:

    Physical Host
        |
    Hypervisor
      /  |  \
    VM  VM  VM

Then cloud infrastructure may provide the same logical resources through
software APIs.

The architecture becomes increasingly independent of specific physical
machines.
""")


# ============================================================================
# SECTION 92: INFRASTRUCTURE LAYERS
# ============================================================================

section("92. COMPLETE INFRASTRUCTURE STACK")

explain("""
A modern application can be viewed as a stack.

Layer 1:
    Physical facilities

Layer 2:
    Servers, storage, networking

Layer 3:
    Virtualization

Layer 4:
    Operating systems

Layer 5:
    Containers and runtimes

Layer 6:
    Application platforms

Layer 7:
    Application services

Layer 8:
    User-facing applications

A failure at a lower layer can affect many layers above it.

For example:

    Power failure
        |
        v
    Physical servers stop
        |
        v
    Virtual machines stop
        |
        v
    Applications stop
        |
        v
    Users cannot access services
""")


# ============================================================================
# SECTION 93: COMPUTE AS A SERVICE
# ============================================================================

section("93. COMPUTE AS A SERVICE")

def monthly_compute_cost(
    hourly_rate: float,
    hours: int = 730
) -> float:

    return hourly_rate * hours


hourly_rate = 0.10
monthly_cost = monthly_compute_cost(hourly_rate)

print(f"At ${hourly_rate:.2f}/hour:")
print(f"Approximate 730-hour monthly cost: ${monthly_cost:.2f}")

explain("""
Cloud infrastructure often allows compute to be treated as a metered service.

The exact pricing model varies by provider and service.

The infrastructure principle is:

    resource capacity
          |
          v
    measurable consumption
          |
          v
        cost

This allows infrastructure consumption to become more closely associated
with actual resource usage.
""")


# ============================================================================
# SECTION 94: ELASTIC CAPACITY
# ============================================================================

section("94. FIXED CAPACITY VS ELASTIC CAPACITY")

fixed_capacity = {
    "minimum_servers": 10,
    "maximum_servers": 10,
}

elastic_capacity = {
    "minimum_servers": 2,
    "maximum_servers": 50,
}

print("Fixed capacity:", fixed_capacity)
print("Elastic capacity:", elastic_capacity)

explain("""
Fixed infrastructure maintains a predetermined capacity.

Elastic infrastructure can change capacity.

The advantage of elasticity is not simply lower cost.

It can also provide:

- faster response to demand
- improved resilience
- automated scaling
- more flexible capacity planning

The trade-off is increased system complexity.
""")


# ============================================================================
# SECTION 95: THE CONTROL LOOP
# ============================================================================

section("95. AUTOMATED INFRASTRUCTURE CONTROL LOOP")

explain("""
Modern infrastructure often operates as a feedback loop.

    Observe
       |
       v
    Measure
       |
       v
    Compare with policy
       |
       v
    Decide
       |
       v
    Act
       |
       v
    Observe again

For example:

    CPU usage = 85%
          |
          v
    Scaling policy triggered
          |
          v
    Create additional instance
          |
          v
    Traffic redistributed

This is an important shift from manual infrastructure administration toward
automated systems management.
""")


# ============================================================================
# SECTION 96: INFRASTRUCTURE AS SOFTWARE
# ============================================================================

section("96. INFRASTRUCTURE BECOMES PROGRAMMABLE")

explain("""
The deepest transformation in modern infrastructure is that infrastructure
itself can be manipulated through software.

Historically:

    Hardware
       |
    Human operator
       |
    Manual configuration

Modern:

    Software
       |
    API
       |
    Control plane
       |
    Infrastructure

The infrastructure can now be:

- created programmatically
- destroyed programmatically
- scaled programmatically
- monitored programmatically
- configured programmatically
- tested programmatically

This is one of the foundations of modern cloud operations.
""")


# ============================================================================
# SECTION 97: HISTORICAL TIMELINE
# ============================================================================

section("97. CONCEPTUAL HISTORICAL TIMELINE")

timeline = [
    ("Early electronic computing", "Centralized, expensive computing resources"),
    ("Mainframe era", "Large centralized enterprise systems"),
    ("Batch processing", "Jobs processed in organized batches"),
    ("Time-sharing", "Multiple users share computing time"),
    ("Minicomputers", "Smaller departmental systems"),
    ("Personal computers", "Computing moves closer to individuals"),
    ("Local networks", "Computers become interconnected"),
    ("Client-server", "Services are distributed between clients and servers"),
    ("Enterprise data centers", "Large-scale centralized infrastructure facilities"),
    ("Virtualization", "Physical resources become pooled and abstracted"),
    ("Clusters", "Multiple machines operate together"),
    ("Distributed computing", "Applications and data spread across machines"),
    ("Web-scale systems", "Infrastructure expands to serve large internet workloads"),
    ("Automation", "Infrastructure management becomes software-driven"),
    ("Utility computing", "Computing capacity becomes consumable as a service"),
    ("Cloud computing", "Elastic infrastructure delivered through network services"),
    ("Containers", "Application environments become lightweight and portable"),
    ("Cloud-native systems", "Automation, orchestration, APIs and distributed services"),
]

for period, development in timeline:
    print(f"{period:28s} -> {development}")


# ============================================================================
# SECTION 98: FINAL CONCEPT MAP
# ============================================================================

section("98. COMPUTING INFRASTRUCTURE CONCEPT MAP")

explain("""
                         COMPUTING INFRASTRUCTURE
                                  |
          +-----------------------+------------------------+
          |                       |                        |
        Compute                 Storage                  Network
          |                       |                        |
       Servers                  Disks                   Switches
          |                    Storage Systems             |
    Virtual Machines              |                     Routing
          |                  Distributed Storage           |
      Containers                  |                    Virtual Networks
          |                       |                        |
    Orchestration              Replication              Connectivity
          |                       |                        |
          +-----------------------+------------------------+
                                  |
                           Distributed Systems
                                  |
                           Resource Pooling
                                  |
                            Virtualization
                                  |
                              Automation
                                  |
                                APIs
                                  |
                              Cloud
                                  |
                 +----------------+----------------+
                 |                |                |
                IaaS             PaaS             SaaS
                 |
             Containers
                 |
          Cloud-Native Systems

The major historical pattern is:

    CENTRALIZATION
          ->
    DECENTRALIZATION
          ->
    NETWORKING
          ->
    DISTRIBUTION
          ->
    VIRTUALIZATION
          ->
    AUTOMATION
          ->
    ELASTIC SERVICE DELIVERY

The physical computer never disappeared.

The important change was the layer at which users interact with computing
resources.

Modern users increasingly interact with:

    services
    APIs
    virtual machines
    containers
    managed platforms

rather than directly with:

    CPUs
    disks
    physical servers
    network cables

That abstraction is one of the defining characteristics of modern computing
infrastructure.
""")


# ============================================================================
# SECTION 99: KNOWLEDGE CHECKS
# ============================================================================

section("99. KNOWLEDGE CHECKS")

questions = [
    (
        "1",
        "Why were mainframes well suited to early enterprise computing?",
        "Because computing resources were expensive and centralized systems "
        "allowed many users and workloads to share powerful hardware."
    ),
    (
        "2",
        "What problem did time-sharing address?",
        "It allowed multiple users to interact with a central computer by "
        "sharing CPU time."
    ),
    (
        "3",
        "What is the central idea of client-server architecture?",
        "Clients request services and servers provide them."
    ),
    (
        "4",
        "Why did data centers become important?",
        "Organizations needed controlled facilities for large collections of "
        "servers, storage, networking, power and cooling infrastructure."
    ),
    (
        "5",
        "Why is virtualization important?",
        "It allows multiple isolated virtual workloads to share physical hardware."
    ),
    (
        "6",
        "What is distributed computing?",
        "A computing model in which multiple networked machines cooperate to "
        "perform work."
    ),
    (
        "7",
        "Why is networking fundamental to distributed systems?",
        "Because distributed components need to communicate across networks."
    ),
    (
        "8",
        "What is elasticity?",
        "The ability to increase or decrease resource capacity according to demand."
    ),
    (
        "9",
        "What does IaaS provide?",
        "Fundamental infrastructure resources such as virtual machines, storage "
        "and networking."
    ),
    (
        "10",
        "Why are containers useful?",
        "They package applications and dependencies into isolated, portable "
        "execution environments."
    ),
]

for number, question, answer in questions:
    print(f"\nQuestion {number}: {question}")
    print(f"Answer: {answer}")


# ============================================================================
# SECTION 100: PRACTICAL ARCHITECTURE EXERCISE
# ============================================================================

section("100. PRACTICAL ARCHITECTURE EXERCISE")

explain("""
Consider an online banking system.

The system must support:

- millions of customers
- account access
- transactions
- authentication
- high availability
- secure communication
- database storage
- backups

A conceptual architecture could be:

                    Customers
                        |
                        v
                   Internet
                        |
                        v
                Load Balancer
                  /       \
                 /         \
          Application A   Application B
                 \         /
                  \       /
                 Service Layer
                 /    |     \
                /     |      \
        Account   Transaction  Auth
        Service     Service    Service
                \     |      /
                 \    |     /
                 Database Cluster
                    /     \
                   /       \
             Primary       Replica
                   |
                   v
                Backups

The physical implementation may involve:

    Data centers
        |
    Physical servers
        |
    Hypervisors
        |
    Virtual machines
        |
    Containers
        |
    Applications

The customer does not need to know which physical CPU executes a particular
transaction.

That is the result of infrastructure abstraction.

The system can be understood simultaneously at several levels:

Business level:
    Banking service

Application level:
    Account and transaction services

Platform level:
    Runtime and orchestration

Infrastructure level:
    Compute, storage and networking

Physical level:
    Servers, disks, switches, power and cooling

The history of computing infrastructure is largely the history of building
and managing these layers more efficiently.
""")


# ============================================================================
# SECTION 101: FINAL HISTORICAL MODEL
# ============================================================================

section("101. HISTORICAL MODEL OF COMPUTING INFRASTRUCTURE")

explain("""
The evolution can finally be expressed through six major transformations.

TRANSFORMATION 1:
FROM SCARCE COMPUTERS TO SHARED COMPUTERS

    Mainframes
    Time-sharing
    Terminals

TRANSFORMATION 2:
FROM CENTRALIZED COMPUTING TO CONNECTED COMPUTING

    Personal computers
    LANs
    Client-server architecture

TRANSFORMATION 3:
FROM INDIVIDUAL SERVERS TO DATA CENTER INFRASTRUCTURE

    Server farms
    Storage systems
    Network infrastructure
    Power and cooling
    Data centers

TRANSFORMATION 4:
FROM PHYSICAL SERVERS TO ABSTRACT RESOURCES

    Virtual machines
    Hypervisors
    Resource pools
    Virtual networks
    Virtual storage

TRANSFORMATION 5:
FROM INDIVIDUAL MACHINES TO DISTRIBUTED SYSTEMS

    Clusters
    Replication
    Distributed databases
    Load balancing
    Geographic distribution

TRANSFORMATION 6:
FROM MANAGED HARDWARE TO PROGRAMMABLE SERVICES

    Automation
    APIs
    Infrastructure as Code
    Elasticity
    Containers
    Cloud platforms
    Cloud-native systems

The result is a layered infrastructure model in which physical hardware is
still essential but is increasingly hidden behind software abstractions.

The modern cloud therefore represents not the disappearance of physical
infrastructure, but the transformation of physical infrastructure into a
programmable, pooled, automated and service-oriented computing environment.
""")


print("\n" + "=" * 80)
print("END OF COMPUTING INFRASTRUCTURE HISTORY PROGRAM")
print("=" * 80)
