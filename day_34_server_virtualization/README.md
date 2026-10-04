# Server Virtualization: Physical Resource Sharing Among Virtual Environments

## Topic Scope

Server virtualization is the technique of presenting multiple isolated virtual computing environments from a shared physical server. A physical machine may contain processors, memory, storage devices, and network interfaces whose capacity is managed by a virtualization layer and exposed to multiple virtual machines.

The central engineering problem is not simply creating several VMs. The important problem is managing the relationship between **physical capacity**, **virtual allocation**, and **runtime demand**.

A useful model is:

**Physical server → virtualization layer → virtual hardware → guest operating systems → applications**

A physical server may have 16 CPU cores, 64 GiB of RAM, 1 TiB of storage, and a 10 Gbps network interface. Instead of dedicating the entire server to one operating system, a virtualization platform can allocate portions of these resources to several VMs.

For example, a host might provision:

| VM | Virtual CPU | RAM | Storage | Network |
|---|---:|---:|---:|---:|
| Web service | 4 | 8 GiB | 100 GiB | 1 Gbps |
| Database | 6 | 24 GiB | 300 GiB | 2.5 Gbps |
| Analytics | 4 | 16 GiB | 250 GiB | 1.5 Gbps |

The allocations describe virtual resources presented to the guests. They do not necessarily mean that every VM is continuously consuming the maximum amount of physical hardware.

## Physical Hardware and Virtual Resources

A virtualization host has finite physical resources.

### CPU

Physical processors provide execution capacity. A hypervisor schedules virtual CPUs onto physical CPU execution resources.

The Python implementation represents CPU capacity using the `cpu` field of `ResourceVector`. The JavaScript implementation uses the same concept but combines it with event-driven workload management. The C++ case study uses CPU demand to demonstrate contention and priority-weighted allocation.

CPU allocation and CPU demand are distinct.

A VM configured with four vCPUs might spend most of its time using only one or two CPU units. When several VMs simultaneously become busy, their aggregate demand can approach or exceed the host's physical CPU capacity.

This is one reason virtualization can achieve higher hardware utilization than static one-application-per-server deployments.

### Memory

Memory is more restrictive than CPU because active guest memory must be backed by usable physical memory or by mechanisms that reclaim, compress, swap, or otherwise manage memory pressure.

The examples therefore track memory separately from CPU. A placement policy may allow some CPU overcommit while applying a stricter memory ratio.

The Python `ControlledOvercommitPolicy` permits CPU and memory overcommit within explicit limits. It deliberately treats storage and network capacity separately instead of assuming that all resources can be overcommitted in the same way.

### Storage

Storage provides persistent capacity for virtual disks and guest data.

The examples treat storage primarily as an allocation constraint rather than an instantaneous execution resource. A VM can have a 300 GiB virtual disk while using only part of that space.

Real virtualization environments introduce additional storage mechanisms such as thin provisioning, snapshots, copy-on-write structures, storage pools, replication, caching, and shared storage. These mechanisms can change the relationship between virtual disk size and physical storage consumption.

### Network

A physical network interface has finite throughput. Virtual network interfaces allow individual VMs to communicate through the host's networking layer.

The simulations keep network allocation bounded by physical capacity in the overcommit policy. This demonstrates that different resources can require different governance rules.

A policy suitable for CPU sharing does not automatically make sense for network bandwidth.

## The Hypervisor's Role

The virtualization layer, commonly called a **hypervisor**, controls access to physical hardware and presents virtual hardware to guests.

Two broad architectural categories are commonly discussed:

- **Type 1 hypervisors** run directly on physical hardware and are commonly used in server and data-center environments.
- **Type 2 hypervisors** run above a conventional host operating system and are commonly used for desktop virtualization and development.

The programs in this repository do not implement a real hypervisor. They model management decisions that occur around virtualization: resource accounting, VM lifecycle, placement, contention, and migration.

A real hypervisor must handle substantially more mechanisms, including CPU scheduling, memory translation, interrupt handling, virtual devices, I/O isolation, hardware-assisted virtualization, device drivers, virtual networking, storage paths, and security boundaries.

## Resource Isolation

The purpose of virtualizing a server is not merely to divide its resources numerically. VMs need controlled access to shared hardware.

A guest normally sees virtual CPU, virtual memory, virtual disks, and virtual network devices rather than direct ownership of the physical machine.

Isolation has several dimensions:

- CPU scheduling prevents one guest from simply executing arbitrary workloads on every physical CPU without hypervisor control.
- Memory virtualization prevents one VM from directly addressing another VM's guest memory.
- Virtual storage separates guest-visible disks from the underlying physical storage representation.
- Virtual networking provides virtual interfaces and controlled paths to other VMs, the host, and external networks.
- Device virtualization or passthrough determines how guests interact with physical devices.

The resource models in the three implementations focus primarily on capacity and scheduling rather than implementing hardware-level isolation.

## Allocation Versus Demand

A critical distinction in server virtualization is the difference between what a VM is **configured to have** and what its workload **currently needs**.

The Python `VirtualMachine` class stores configured resources in `resources` and runtime workload values in `cpu_demand`, `memory_demand_gib`, and `network_demand_mbps`.

The Python `PhysicalHost` then calculates:

- `configured_allocation()`
- `running_demand()`
- allocation utilization
- demand utilization
- configured overcommit
- current workload overload

This makes it possible to model a host where configured VM capacity exceeds physical hardware while current demand remains within physical limits.

That distinction is central to understanding virtualization density.

## Overcommitment

**Overcommitment** occurs when the total virtual resources configured across VMs exceed the corresponding physical resource capacity.

For example, a host with eight physical CPU units might provision four VMs with four vCPUs each:

**Configured virtual CPU = 16 vCPU**

**Physical CPU = 8 CPU units**

The virtual allocation is therefore 2:1 relative to physical CPU capacity.

This can be useful when workloads are bursty and rarely consume their full allocation simultaneously. It can also become dangerous when many workloads become busy at the same time.

The Python implementation makes this distinction explicit through `is_overcommitted()` and `is_currently_overloaded()`.

These are different conditions:

- A host can be configured for overcommit without being overloaded at a particular moment.
- A host can become overloaded when runtime demand exceeds physical capacity.
- Persistent overload can cause latency, reduced throughput, queue growth, and poor application performance.

## Conservative Allocation

A conservative policy reserves enough physical capacity for the configured VM resources.

The Python `ConservativePolicy` rejects a placement when the projected allocation does not fit within physical capacity.

This model favors predictability.

It is appropriate conceptually when the operator wants strong resource guarantees and has limited tolerance for contention.

The JavaScript `ReservedCapacityPolicy` provides the same policy concept in a JavaScript-specific management model.

## Controlled Overcommit

The Python and JavaScript implementations also demonstrate controlled overcommitment.

The Python policy uses:

- a maximum CPU overcommit ratio
- a maximum memory overcommit ratio
- physical storage limits
- physical network limits

The JavaScript `BurstablePolicy` implements the same type of policy but places it inside an event-driven virtualization management service.

The important design decision is that overcommit is **policy-controlled**, not an unlimited permission to create VMs.

A production system would normally consider additional information such as historical workload patterns, reservations, limits, NUMA topology, host health, workload criticality, availability requirements, and cluster-wide capacity.

## CPU Contention

CPU contention occurs when the active workload demand from VMs exceeds available physical execution capacity.

Suppose a host has eight physical CPU units and three running VMs request:

- VM A: 5 CPU units
- VM B: 4 CPU units
- VM C: 3 CPU units

Total demand is 12 CPU units against 8 physical units.

The hypervisor must schedule access to the available CPU capacity.

The Python `distribute_cpu_fair_share()` function demonstrates a simplified priority-weighted scheduler. The C++ `calculateCPUShare()` function implements the same conceptual problem from a systems-programming perspective.

The model gives higher-priority workloads a larger share when total demand exceeds physical capacity.

Real hypervisors use substantially more sophisticated mechanisms. They may consider CPU shares, reservations, limits, CPU affinity, processor topology, scheduling classes, NUMA locality, virtualization overhead, and hardware scheduling support.

## Memory Pressure

Memory contention is especially important because active memory pages must ultimately be supported by physical memory or a memory-management mechanism.

A system may use mechanisms such as:

- guest ballooning
- host swapping
- memory compression
- page sharing where supported
- dynamic memory allocation
- memory reservations
- memory limits

These mechanisms have different performance and isolation implications.

The simulations deliberately stop short of implementing guest memory paging. They use memory as a capacity dimension so that placement policies can reason about physical versus virtual capacity.

This keeps the educational model focused on resource division rather than pretending that a simple counter represents the complete behavior of a production memory-management subsystem.

## VM Lifecycle

A VM is not always running.

The implementations model lifecycle states such as:

- stopped
- running
- paused

The Python implementation provides `start()`, `stop()`, `pause()`, and `resume()` methods.

The JavaScript implementation adds event emission when lifecycle changes occur.

This matters because runtime demand depends on state. A stopped VM may still occupy configured capacity in the management model while contributing no active CPU or network workload.

A paused VM similarly does not contribute active execution demand in these simulations.

Real hypervisors can have additional lifecycle states and operations, including creation, cloning, suspension, migration, reboot, deletion, and recovery.

## Pulling the Resource Model Together

A useful mental model is:

**Physical capacity → VM allocation → runtime demand → contention → scheduling decision**

The physical capacity represents what the server actually owns.

The VM allocation represents what the virtualization platform exposes or promises to the guest.

Runtime demand represents what the guest workload is attempting to consume.

If aggregate demand remains below physical capacity, the host may satisfy all active workloads without significant resource contention.

If demand exceeds physical capacity, the hypervisor must schedule, throttle, delay, reclaim, or otherwise manage access to the constrained resource.

## Python Implementation

The Python program is a complete resource-management simulator.

### Resource representation

`ResourceVector` represents CPU, memory, storage, and network capacity in one object. Arithmetic operations allow the host to add VM allocations and calculate remaining capacity.

The `fits_within()` method checks whether an allocation can physically fit.

The `utilization_against()` method calculates resource utilization ratios independently for each resource.

### VM model

`VirtualMachine` stores both configured resources and runtime workload demand.

Its lifecycle methods demonstrate why a virtualization management system must distinguish between:

- resource provisioning
- VM state
- active workload demand
- persistent storage usage

The snapshot mechanism records snapshot metadata without attempting to implement a real copy-on-write storage system.

### Physical host

`PhysicalHost` maintains the collection of VMs and exposes separate calculations for configured allocation and runtime demand.

This separation is one of the most important concepts in the program.

A host can report:

- physical capacity
- configured allocation
- active demand
- allocation utilization
- demand utilization
- overcommit state
- current overload state

### Placement

`ClusterScheduler` chooses among multiple hosts.

It evaluates whether each host satisfies the active policy and then calculates a multi-resource placement score.

The score considers CPU, memory, storage, and network rather than blindly filling CPU capacity.

This demonstrates why real resource placement is a multi-dimensional scheduling problem.

### Workload simulation

`simulate_workload()` changes VM demand across several cycles.

The resulting output illustrates that a VM's configured resources are not equivalent to continuous consumption.

The simulation uses a deterministic random seed so that the same workload pattern can be reproduced while debugging or studying the code.

### Migration

`can_live_migrate()` checks whether the destination host can accommodate a running VM.

`migrate_vm()` then performs an accounting-level transfer between hosts.

This is not a real live migration implementation. A real system would transfer guest memory state, track memory changes while the VM continues running, coordinate device state, maintain networking, and eventually switch execution to the destination.

## JavaScript Implementation

The JavaScript program approaches virtualization as an event-driven management system.

### Event-driven VM lifecycle

`VirtualMachine` extends Node.js `EventEmitter`.

When a VM starts, pauses, resumes, or stops, it emits a `stateChanged` event.

This models an important management-plane pattern: resource changes can trigger other services without embedding every consumer directly inside the VM object.

For example, a production management system could use lifecycle events to trigger:

- monitoring updates
- audit records
- capacity recalculation
- alert evaluation
- orchestration workflows

### Host resource events

`PhysicalHost` listens to VM events and emits higher-level events such as `vmStateChanged`, `vmAdded`, and `vmRemoved`.

This creates a layered event flow:

**VM event → host event → management event**

The JavaScript implementation therefore demonstrates a different architectural perspective from the Python implementation.

### Asynchronous monitoring

`monitorOnce()` is asynchronous and `simulateChangingWorkload()` uses promises and timed execution.

This reflects how a Node.js management service could periodically collect telemetry from hypervisor APIs or monitoring agents.

The program does not claim to access actual hardware. The asynchronous behavior demonstrates the structure of an event-driven management plane.

### Placement policy

`ReservedCapacityPolicy` models strict reservation.

`BurstablePolicy` permits bounded CPU and memory overcommit while keeping storage and network bounded.

The policies are represented as separate classes so that the management system can change governance rules without rewriting host resource accounting.

## C++ Case Study

The C++ program models a private-cloud cluster containing heterogeneous physical servers.

The scenario contains:

- an orders database
- an analytics workload
- a web service
- a development VM

The VMs have different priorities and resource allocations.

### Physical server model

`PhysicalServer` owns a collection of `VirtualMachine` objects and calculates both configured allocation and active demand.

The server is therefore the physical resource boundary.

### Policy abstraction

`PlacementPolicy` is an abstract interface.

`ReservedCapacityPolicy` requires the complete configured allocation to fit.

`ControlledOvercommitPolicy` allows CPU and memory overcommit according to explicit ratios but prevents storage and network overcommit.

This design separates governance rules from the physical server implementation.

### Cluster scheduling

`ClusterScheduler` evaluates all eligible servers and selects the one with the best multi-resource placement score.

This represents a simplified form of VM placement.

Real cloud schedulers may use much richer information, including:

- CPU and memory reservations
- NUMA topology
- host affinity
- anti-affinity
- hardware capabilities
- availability zones
- storage locality
- network locality
- maintenance state
- historical resource consumption

### CPU scheduling

`calculateCPUShare()` detects CPU contention and distributes available CPU using VM priority.

Its computational complexity is O(V), where V is the number of VMs on the host.

The algorithm is deliberately simplified. A real hypervisor scheduler is not merely a proportional arithmetic function.

### Migration

The case study checks whether the destination can accept a running VM before performing a simplified migration.

Real live migration is considerably more complex.

A production implementation must account for guest memory transfer, memory dirtying rates, virtual device state, virtual network continuity, storage accessibility, CPU compatibility, and the final switchover.

The C++ program therefore uses migration as a resource-capacity case study rather than pretending to implement a real hypervisor migration protocol.

## Resource Fragmentation

A host may have enough total capacity for a VM but still be difficult to use efficiently because capacity is distributed unevenly across resource dimensions.

For example, a host might have:

- substantial free CPU
- very little free memory
- substantial storage
- substantial network capacity

A CPU-only scheduler might incorrectly conclude that the host is ideal.

The Python and C++ placement algorithms therefore calculate multi-resource scores.

This demonstrates a central scheduling principle: **capacity is multidimensional**.

## Overcommit Risk

Overcommitment is useful only when the workload profile supports it.

A development environment with irregular CPU demand may be a good candidate for CPU overcommit.

A memory-heavy workload with consistently high utilization can make memory overcommit risky.

A production system should therefore distinguish between resource classes and workload characteristics rather than applying one universal overcommit ratio.

The risk increases when:

- many VMs become busy simultaneously
- workload peaks are correlated
- physical headroom becomes small
- memory pressure causes reclamation
- storage latency increases
- network demand reaches interface capacity
- reservations and limits are poorly configured

## Common Failure Conditions

The implementations explicitly handle several failure cases.

### Duplicate VM names

A host rejects a VM when another VM with the same name already exists.

This prevents ambiguous resource ownership in the simulation.

### Negative resource quantities

Resource validation rejects negative CPU, memory, storage, or network values.

Negative physical capacity has no meaningful interpretation.

### Excessive allocation

A conservative policy rejects an allocation that exceeds physical capacity.

An overcommit policy may accept it only when the configured ratios remain within policy.

### Invalid lifecycle transitions

A stopped VM cannot be paused.

A paused VM must be resumed through the appropriate lifecycle operation.

These rules prevent the simulated state machine from entering invalid states.

### Migration failure

A migration is rejected when the destination cannot satisfy the applicable placement policy.

The important operational rule is that capacity must be evaluated before changing the source or destination state.

## Performance Considerations

Resource accounting generally scales with the number of VMs being evaluated.

The basic host allocation calculation is O(V), where V is the number of VMs on a host.

The placement scheduler evaluates multiple hosts, making a simple placement operation approximately O(H × V), where H is the number of candidate hosts.

Large-scale virtualization platforms cannot rely only on repeated full scans. They can maintain indexes, cached capacity summaries, telemetry streams, placement metadata, and cluster-level scheduling structures.

Runtime monitoring also requires careful sampling strategy. Very frequent telemetry collection increases management overhead, while infrequent collection can hide short resource spikes.

## Security and Isolation Considerations

Resource division does not automatically guarantee complete security isolation.

A production virtualization platform must defend against:

- unauthorized VM access
- hypervisor vulnerabilities
- malicious guest workloads
- virtual network misconfiguration
- insecure management interfaces
- improper storage permissions
- exposed management credentials
- unsafe device passthrough
- resource-exhaustion attacks

The hypervisor is a particularly sensitive trust boundary because compromise of the virtualization layer can potentially affect multiple guest environments.

Resource quotas also have a security relevance. Without appropriate limits, one tenant may intentionally or accidentally consume excessive shared resources and degrade service for other tenants.

## Production Considerations

A production virtualization platform needs substantially more than the resource counters shown in these programs.

Important operational components include:

| Area | Production concern |
|---|---|
| CPU | Scheduling, reservations, limits, topology, NUMA, affinity |
| Memory | Reservations, reclamation, ballooning, swapping, NUMA locality |
| Storage | Thin provisioning, IOPS, latency, snapshots, replication, failure recovery |
| Network | Virtual switches, VLANs, overlays, bandwidth controls, packet processing |
| Availability | Host failure detection, restart policies, clustering, redundancy |
| Migration | Destination compatibility, memory transfer, storage, network continuity |
| Monitoring | Capacity trends, latency, saturation, alerts, historical telemetry |
| Security | Hypervisor hardening, isolation, access control, secure management |
| Governance | Resource quotas, tenant policies, reservations, workload classification |

The simulator intentionally focuses on the relationship between physical resources and virtual environments rather than implementing these production subsystems.

## Key Technical Distinctions

### Physical capacity versus virtual allocation

Physical capacity is what the server actually provides.

Virtual allocation is what the virtualization platform configures for VMs.

Virtual allocation may exceed physical capacity when overcommit is permitted.

### Allocation versus demand

Allocation describes provisioned virtual capacity.

Demand describes current workload consumption.

A VM can have a large allocation while using relatively little physical capacity.

### Overcommit versus overload

Overcommit is a configuration relationship between virtual allocation and physical capacity.

Overload is a runtime condition in which active demand exceeds available physical capacity.

Overcommit does not necessarily mean that the host is currently overloaded.

### VM isolation versus resource scheduling

Isolation prevents one guest from directly controlling another guest's environment.

Scheduling determines how shared physical resources are distributed when multiple guests need them.

These are related but different responsibilities.

### Placement versus migration

Placement determines where a VM should run when it is introduced into the cluster.

Migration changes the physical host on which an existing VM runs.

Both operations require resource-capacity reasoning, but migration also has continuity and compatibility constraints.

## Practical Architectural Model

The three implementations collectively model a simplified virtualization control plane:

**Physical servers**

→ provide finite CPU, memory, storage, and network capacity

**Placement policies**

→ decide whether a VM can consume capacity on a host

**Virtual machines**

→ represent isolated virtual environments with configured resources

**Workload demand**

→ represents actual resource consumption

**Schedulers**

→ decide how shared capacity is distributed

**Monitoring**

→ observes resource pressure and state changes

**Migration**

→ moves workloads when another host can safely accommodate them

This relationship is the core of server virtualization resource management.

## Limitations of the Simulation

The programs are intentionally educational models rather than hypervisor implementations.

They do not implement:

- hardware virtualization instructions
- guest page-table translation
- actual virtual CPUs
- real memory isolation
- virtual disk I/O
- copy-on-write snapshots
- virtual switches
- physical NIC drivers
- live memory migration
- NUMA-aware scheduling
- real-time hypervisor telemetry
- hardware failure recovery

The models instead make the resource-sharing problem explicit and executable.

The most important abstraction is the separation of **physical capacity**, **virtual allocation**, and **runtime demand**. Once those concepts are separated, scheduling, overcommitment, contention, and migration can be reasoned about systematically.
