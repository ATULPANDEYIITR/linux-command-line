# Introduction to Virtualization

## Scope

This project models the foundational ideas behind server virtualization:

- physical servers and their finite hardware resources
- virtual machines as isolated software-defined computing environments
- resource abstraction between guest operating systems and physical hardware
- hypervisor-controlled allocation and scheduling
- VM lifecycle management
- resource utilization and consolidation
- CPU overcommitment and contention
- capacity validation and failure handling
- practical benefits and trade-offs of virtualization

The three implementations deliberately use different perspectives. Python provides a readable resource-management simulation, JavaScript emphasizes event-driven lifecycle management, and C++ models a more structured private-cloud governance and placement engine.

---

## Physical Servers

A physical server is the actual machine containing resources such as CPU cores, RAM, storage devices, network interfaces, firmware, buses, and other hardware components.

The physical server is the ultimate capacity boundary. Virtualization can divide or multiplex resources, but it cannot create additional physical CPU execution capacity, memory chips, storage bandwidth, or network throughput merely by defining more virtual machines.

The Python implementation represents a physical server with `PhysicalServer`. Its capacity includes CPU cores, memory in GiB, storage in GiB, and network capacity in Gbps.

The JavaScript implementation uses the `PhysicalServer` class for the same architectural boundary but connects it to an event-driven VM management layer.

The C++ implementation places a `PhysicalHost` inside a `VirtualizationCluster`. This makes the physical host an explicit infrastructure object whose capacity is consulted before virtual machines are created.

---

## Virtual Machines

A virtual machine is a software-defined computer environment presented to a guest operating system.

A VM normally has virtual resources such as:

- virtual CPUs
- virtual memory
- virtual storage
- virtual network interfaces

The guest operating system treats these resources as its available machine environment. The VM does not normally own the underlying physical CPU cores or memory modules.

The virtualization layer is responsible for mapping guest-visible operations onto physical resources.

For example, the Python program creates a VM with `ResourceRequest(4, 16, 120, 2.0)`. The guest is modeled as having four virtual CPU cores, 16 GiB of memory, 120 GiB of storage, and a 2 Gbps virtual network allocation. Those values describe the VM's virtual resource contract, not four permanently dedicated physical CPU cores.

---

## Resource Abstraction

Resource abstraction is one of the central mechanisms of virtualization.

Without virtualization, an operating system interacts much more directly with physical hardware. With virtualization, the guest sees a virtual hardware environment while the hypervisor controls how that environment maps onto the physical machine.

The abstraction can be represented as:

    Physical CPU / Memory / Storage / Network
                       |
                       v
                  Hypervisor
                       |
          +------------+------------+
          |            |            |
          v            v            v
        VM Web       VM DB       VM Analytics
          |            |            |
          v            v            v
      Guest OS      Guest OS      Guest OS

This separation provides flexibility. A VM configuration can describe a virtual CPU allocation without requiring that a particular physical CPU core permanently belong to that VM.

The abstraction also creates an additional management layer. Performance, availability, security, and capacity depend partly on how effectively that layer maps virtual demands to physical resources.

---

## Hypervisor Role

The hypervisor is the virtualization layer responsible for managing virtual machines and mediating access to physical resources.

The exact implementation differs between hypervisor technologies, but the conceptual responsibilities represented in this project include:

- creating VM resource definitions
- validating resource requests
- maintaining VM lifecycle state
- allocating physical capacity
- scheduling CPU demand
- maintaining isolation boundaries
- presenting virtual hardware to guests
- managing contention between workloads

The Python `Hypervisor` class keeps a collection of VMs and calculates both configured allocation and current workload consumption.

The JavaScript `Hypervisor` class performs resource validation and uses `EventEmitter` to make VM lifecycle events observable by management software.

The C++ `VirtualizationCluster` acts as a governance layer around physical hosts and VMs. It evaluates projected resource allocations before accepting a VM.

---

## Allocation Versus Actual Usage

A key virtualization distinction is the difference between **configured virtual capacity** and **current workload consumption**.

A VM may be configured with 8 virtual CPUs while its workload may currently need only a fraction of that processing capacity.

The Python program therefore maintains both:

- VM allocation, representing configured virtual resources
- VM utilization, representing current workload demand

The `actual_usage()` method converts utilization percentages into approximate current consumption.

This distinction matters because consolidation decisions based only on configured allocations can produce a different picture from decisions based on measured workload behavior.

For example, a host may have 20 virtual CPUs assigned to VMs while only a smaller amount of CPU execution is being demanded at a particular moment.

Memory requires additional care because memory pressure can become a hard constraint much sooner than CPU demand in many workloads.

---

## Virtual Machine Lifecycle

A VM is not simply either present or absent. It has an operational lifecycle.

The Python and JavaScript implementations model:

`stopped -> running -> paused -> running -> stopped`

The lifecycle rules prevent invalid transitions.

For example, a stopped VM cannot be resumed directly from the paused state because it has not entered that state. A running VM can be paused, while a paused VM can be resumed.

The C++ case study uses the same conceptual lifecycle through the `VMState` enumeration and methods such as `start()`, `pause()`, `resume()`, and `stop()`.

These state transitions demonstrate an important virtualization management principle: control-plane operations should validate the current state before changing it.

---

## CPU Virtualization and Overcommitment

CPU virtualization allows virtual CPUs to share physical CPU execution capacity.

A physical host may have 16 physical cores while the combined VM configuration may specify more than 16 virtual CPUs.

This is called **CPU overcommitment**.

The Python demonstration deliberately creates an environment with 18 virtual CPU cores assigned to a 16-core host. The simulation allows this because CPU execution can be scheduled over time.

The C++ case study goes further by modeling a proportional scheduler. When requested CPU demand exceeds physical capacity, the scheduler scales the requested execution shares so that their sum remains within the available physical CPU capacity.

This is a simplified model. Real hypervisors account for substantially more factors, including scheduling fairness, priorities, processor topology, virtualization hardware support, interrupt processing, affinity, and workload behavior.

CPU overcommitment is therefore a capacity-planning decision rather than a method for manufacturing physical CPU capacity.

---

## Memory as a Capacity Boundary

Memory is handled more conservatively in these implementations.

The Python `Hypervisor` requires aggregate VM memory allocation to remain within physical memory.

The JavaScript implementation also rejects projected memory allocations that exceed the host's physical memory.

The C++ case study treats memory as a hard placement constraint.

Real virtualization platforms can implement more sophisticated memory-management techniques, but memory pressure has important consequences because actively running workloads require usable physical memory or an appropriate backing mechanism.

A host with excessive memory overcommitment can experience degradation or failure when multiple workloads demand their configured memory simultaneously.

---

## Storage and Network Abstraction

Virtualization also abstracts storage and network resources.

A VM can be assigned a virtual disk even though the underlying data ultimately resides on physical storage resources.

Likewise, a guest operating system can interact with a virtual network interface while the physical traffic eventually traverses the host's network hardware and virtualization stack.

The Python and JavaScript resource models therefore include storage and network capacity alongside CPU and memory.

These resources have different performance characteristics. Storage capacity alone does not describe storage performance. IOPS, latency, throughput, queue depth, caching, and contention can become important in real environments.

Similarly, a virtual network allocation does not eliminate physical network bottlenecks. Multiple VMs can compete for the same physical network interface or upstream network path.

---

## VM Isolation

Virtual machines provide separate guest environments even though they share physical infrastructure.

In the Python implementation, `tenant-a` and `tenant-b` receive independent VM identities and resource allocations.

The conceptual isolation boundary is:

    Physical Host
        |
        +-- Hypervisor
             |
             +-- VM A
             |
             +-- VM B

A process running inside VM A is not normally given direct access to VM B's guest memory simply because both VMs are hosted on the same physical machine.

The hypervisor is therefore part of the security boundary.

Isolation should not be interpreted as absolute protection against every failure. Hypervisor vulnerabilities, device emulation bugs, insecure management interfaces, incorrect configuration, shared-resource side channels, and compromised host infrastructure can affect the security model.

---

## Python Implementation

The Python program is a resource-management simulation designed to expose virtualization mechanics through executable objects and state changes.

### Physical resource model

`PhysicalServer` defines the finite physical capacity of a host. Validation in its constructor prevents nonsensical resources such as zero CPU cores or negative memory.

### VM resource model

`ResourceRequest` represents the virtual resource allocation assigned to a VM.

`VirtualMachine` combines that allocation with:

- operating-system identity
- lifecycle state
- CPU utilization
- memory utilization
- storage utilization
- network utilization

The `actual_usage()` method separates workload consumption from configured VM capacity.

### Hypervisor model

`Hypervisor` stores VMs and validates resource requests against the host.

Its `allocated_resources()` method answers:

> How much virtual capacity has been configured?

Its `actual_host_usage()` method answers:

> How much resource consumption is currently produced by running workloads?

This distinction makes the simulation useful for understanding why virtualization capacity planning cannot rely on a single resource number.

### Failure behavior

The program explicitly rejects VM requests that exceed physical memory, storage, or network capacity. It also rejects invalid resource values and invalid lifecycle transitions.

The CPU policy is configurable through `allow_cpu_overcommit`.

### Advanced scheduling

`CpuScheduler` provides a simplified proportional allocation model. If total demand exceeds physical CPU capacity, each workload receives a proportional share.

The implementation is intentionally simpler than a production hypervisor scheduler while preserving the fundamental resource-multiplexing idea.

---

## JavaScript Implementation

The JavaScript program uses Node.js-specific event-driven behavior to represent virtualization management.

### Event-driven VM management

`VirtualMachine` extends Node.js `EventEmitter`.

VM lifecycle operations emit events such as `started`, `stopped`, `paused`, and `resumed`.

The `Hypervisor` listens to these VM events and re-emits management-level events such as `vmStarted` and `vmCreated`.

This models an important control-plane pattern: monitoring or orchestration software can react to lifecycle changes rather than continuously polling every VM.

### Resource validation

The JavaScript hypervisor validates projected allocations before creating a VM.

The projected allocation is calculated as existing virtual allocation plus the new VM's requested resources.

Memory, storage, and network are treated as hard capacity boundaries. CPU overcommitment is permitted by policy.

### Current usage

The JavaScript VM maintains utilization percentages separately from configured virtual resources.

`currentUsage()` calculates approximate active consumption only when the VM is running.

This lets the host report distinguish configured capacity from current workload activity.

### Scheduling

`proportionalCpuSchedule()` models CPU contention using a proportional scaling factor.

When total CPU demand exceeds physical capacity, each workload's scheduled share is reduced proportionally.

The function demonstrates resource contention without pretending to reproduce the scheduling algorithms of a real hypervisor.

---

## C++ Private-Cloud Case Study

The C++ implementation represents a small private-cloud environment in which a virtualization cluster governs VM placement on physical hosts.

The architecture is intentionally different from the Python object model.

### Physical host

`PhysicalHost` encapsulates the physical capacity boundary.

The cluster can therefore reason about whether a proposed VM allocation fits within the host's available resources.

### Cluster governance

`VirtualizationCluster` maintains physical hosts and their VM inventories.

Before a VM is accepted, the cluster computes the projected allocation and applies policy.

The C++ implementation permits CPU overcommitment on the case-study host while keeping memory, storage, and network within hard capacity limits.

### VM data structure

Each VM contains:

- a name
- a guest operating system
- virtual resource allocation
- lifecycle state
- workload utilization

The VM calculates current usage from its allocation and utilization values.

### Placement logic

VM creation evaluates:

    existing allocation + requested allocation

against:

    physical host capacity

CPU is evaluated according to the host's overcommit policy. Memory, storage, and network are checked directly against physical capacity.

This separates a resource policy decision from the physical capacity itself.

### CPU scheduler

`ProportionalCpuScheduler` receives CPU demand from several VMs.

The case study gives:

- `web-production` a demand of 2 cores
- `database-production` a demand of 7 cores
- `analytics` a demand of 6 cores

The combined demand is greater than the host's 16 physical cores, so the scheduler scales the shares.

This illustrates why overcommitment can work during ordinary operation while still requiring careful capacity planning for simultaneous peaks.

---

## Consolidation

Server consolidation is one of the principal operational reasons for virtualization.

Consider three workloads that would otherwise require separate physical servers. A virtualized environment can place those workloads into separate VMs on a shared host when the combined resource requirements fit the host's capacity and the workload behavior is compatible with the platform.

The important relationship is:

    Multiple workloads
            |
            v
    Virtual machines
            |
            v
    Shared physical resource pool

Consolidation can reduce unused capacity when workloads have different utilization patterns.

It does not eliminate the need for capacity planning. A consolidated host can become a larger failure domain because several workloads may depend on the same physical machine.

---

## Benefits and Trade-offs

### Hardware utilization

Virtualization can improve utilization by allowing several workloads to share physical capacity.

A dedicated physical server may spend much of its CPU capacity idle while another server experiences a peak. Virtualization allows the resource pool to be shared rather than statically divided by machine ownership.

### Isolation

Separate VMs provide distinct guest operating-system environments.

This can be useful when applications require different operating systems, software stacks, administrative boundaries, or controlled resource allocations.

### Hardware abstraction

Guest operating systems can operate against virtual hardware interfaces instead of being tightly coupled to a particular physical server configuration.

This can simplify workload movement and infrastructure management.

### Operational flexibility

VMs can be created, started, stopped, paused, resumed, backed up, replicated, resized, migrated, or restored depending on the capabilities of the virtualization platform.

### Failure-domain trade-off

Consolidation creates shared dependencies.

If many critical VMs run on one physical host, failure of that host can affect all of them. High-availability designs therefore distribute workloads across hosts and account for host failures during capacity planning.

---

## Resource Contention

Virtualization changes the question from:

> Which physical server owns this workload?

to:

> How should this workload share the physical resource pool with other workloads?

CPU contention is illustrated explicitly in the C++ scheduler.

Storage and network contention require different measurements. Two VMs may each have reasonable configured storage capacity while still competing for the same physical storage throughput.

Likewise, several VMs can have virtual network interfaces while sharing a physical network interface and upstream network infrastructure.

Resource capacity should therefore be considered across both quantity and performance.

---

## Common Failure Conditions

The implementations deliberately demonstrate failures that a virtualization control plane should detect.

### Invalid resource requests

A VM requesting zero or negative resources is rejected.

Such validation prevents malformed configurations from entering the resource-management system.

### Physical memory exhaustion

A VM requiring more memory than the physical host can provide is rejected in the simulations.

### Storage exhaustion

A VM whose requested storage exceeds the host's modeled storage capacity is rejected.

### Network capacity exhaustion

A network allocation exceeding the host's modeled network capacity is rejected.

### Invalid lifecycle transitions

Operations such as resuming a stopped VM are rejected because the requested state transition does not match the VM's current state.

### CPU overcommitment

CPU overcommitment is not automatically treated as an error. It is represented as a policy decision because CPU virtualization can multiplex execution over time.

The important distinction is that an accepted CPU allocation does not guarantee that every VM can simultaneously consume its entire configured virtual CPU capacity.

---

## Performance Considerations

Virtualization introduces overhead and contention mechanisms that do not exist in exactly the same form on a dedicated physical workload.

Important dimensions include:

| Resource | Virtualization concern |
|---|---|
| CPU | Scheduling overhead, contention, overcommitment, CPU topology |
| Memory | Physical capacity, memory pressure, allocation policy |
| Storage | IOPS, latency, throughput, queues, shared devices |
| Network | Interface bandwidth, packet processing, shared links |
| Host | Aggregate contention and failure-domain size |

A VM configuration should therefore not be interpreted as a complete performance guarantee.

A four-vCPU VM does not automatically receive the same performance characteristics as a physical server with four dedicated physical cores.

---

## Security Considerations

Virtualization creates a layered security architecture.

The major boundaries include:

    Guest application
          |
    Guest operating system
          |
    Virtual hardware
          |
    Hypervisor
          |
    Physical hardware
          |
    Management infrastructure

The hypervisor and its management plane are security-sensitive components.

Practical controls include strong administrative access control, network segmentation, timely security updates, restricted management interfaces, audit logging, secure VM images, controlled device exposure, and monitoring of host-level activity.

Isolation also needs to be evaluated in the context of shared resources. A VM is logically separated from other VMs, but the physical host remains shared infrastructure.

---

## Production Capacity Planning

A production virtualization environment should account for more than average utilization.

Capacity planning should consider:

- peak CPU demand rather than only average CPU demand
- memory requirements during simultaneous workload peaks
- storage latency and throughput rather than capacity alone
- network throughput and burst behavior
- host failure scenarios
- maintenance windows
- workload growth
- VM placement constraints
- licensing restrictions
- backup and recovery requirements
- monitoring and alerting

A host that is technically capable of running its current VMs may still be unsuitable if losing that host would leave the remaining infrastructure unable to absorb the workloads.

---

## Important Distinctions

### Physical server versus virtual machine

A physical server is an actual hardware platform. A VM is a software-defined computing environment whose resources are presented through the virtualization layer.

### Virtual resource versus physical resource

A virtual CPU is a guest-visible execution resource. A physical CPU core is actual hardware execution capacity. Multiple virtual CPUs may compete for physical CPU resources.

### Allocation versus utilization

Allocation describes what has been configured for a VM. Utilization describes what the workload is currently consuming.

### Isolation versus independence

VM isolation separates guest environments, but the VMs remain dependent on shared physical infrastructure and the hypervisor.

### Consolidation versus unlimited scaling

Consolidation improves resource pooling. It does not remove physical limits.

### Overcommitment versus additional hardware

Overcommitment permits more virtual capacity to be configured than can be simultaneously executed. It does not create additional physical resources.

---

## Practical Workflow

A simplified virtualization management workflow can be represented as:

    Physical host discovered
             |
             v
    Capacity inventory created
             |
             v
    VM resource request received
             |
             v
    Allocation policy evaluated
             |
       +-----+-----+
       |           |
     reject      accept
                   |
                   v
              VM created
                   |
                   v
              VM started
                   |
                   v
          Workload consumes resources
                   |
                   v
       Monitoring measures utilization
                   |
                   v
        Capacity policy is reevaluated

This workflow connects the core concepts: physical infrastructure supplies the finite resource pool, the hypervisor abstracts it into virtual resources, VMs consume those resources, and management software continuously evaluates capacity and workload behavior.

---

## Limitations of the Simulation

The implementations intentionally model the architectural concepts rather than reproducing a commercial hypervisor.

They do not implement actual hardware virtualization instructions, page-table virtualization, virtual machine monitor memory translation, device emulation, live migration protocols, distributed storage, NUMA scheduling, virtual switches, snapshots, copy-on-write disks, or production high-availability algorithms.

The CPU schedulers are simplified mathematical demonstrations. A production scheduler has substantially more state and policy.

The storage and network values represent capacity rather than complete performance models.

These limitations are important because a conceptual resource allocator should not be confused with a complete virtualization platform.

---

## Code Execution

The Python program can be executed directly with a Python 3 interpreter.

The JavaScript implementation is designed for Node.js because it uses Node's built-in `events` module and `EventEmitter`.

The C++ program targets C++17 and uses only the standard library.

The C++ build command is:

    g++ -std=c++17 -O2 -Wall -Wextra -pedantic virtualization.cpp -o virtualization

The resulting executable runs the private-cloud case study, validation scenarios, VM lifecycle demonstration, CPU scheduling model, and architectural explanation.
