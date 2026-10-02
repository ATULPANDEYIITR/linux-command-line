# Hypervisors: Type 1, Type 2, and Virtual Machine Management

## Topic Scope

A hypervisor is the virtualization layer responsible for presenting virtualized computing resources to guest operating systems. It allows multiple virtual machines (VMs) to share a physical computer while maintaining controlled boundaries around CPU execution, memory, storage, and networking.

The two major architectural categories are **Type 1** and **Type 2** hypervisors.

A Type 1 hypervisor runs directly on physical hardware and provides virtualization services without requiring a conventional host operating system underneath it. A Type 2 hypervisor runs above a host operating system as software, with the host operating system remaining part of the path between the virtualization software and physical hardware.

The three implementations in this project approach the subject from different perspectives:

- The Python program provides a broad virtualization simulator with explicit VM resources, lifecycle transitions, snapshots, networking, CPU scheduling, and memory-overcommitment behavior.
- The JavaScript program models a management plane using event-driven architecture and asynchronous management operations.
- The C++ program presents a coherent infrastructure case study in which a Type 1 hypervisor manages production-style workloads and enforces resource constraints.

None of the programs creates a real virtual machine. They model the control and resource-management behavior that a real virtualization platform must implement.

## Hypervisor Architecture

The basic Type 1 architecture can be represented as:

    Physical hardware
           |
       Hypervisor
        /   |   \
      VM    VM    VM

The hypervisor has direct responsibility for managing physical resources and exposing virtual resources to guest operating systems.

The Type 2 architecture can be represented as:

    Physical hardware
           |
       Host OS
           |
    Type 2 hypervisor
        /       \
      VM         VM

The host operating system remains active and provides services used by the virtualization application. This architecture is common for desktop development, testing, laboratories, and workstation virtualization.

The architectural distinction is important because the location of the virtualization layer changes the execution path, management model, dependency structure, and operational environment.

## Type 1 Hypervisors

A Type 1 hypervisor, also called a bare-metal hypervisor, operates directly on the physical machine.

Its responsibilities can include:

- scheduling virtual CPUs onto physical CPU execution resources;
- maintaining isolation between guest memory regions;
- exposing virtual storage devices;
- providing virtual network interfaces;
- controlling access to physical devices;
- maintaining VM lifecycle state;
- exposing management interfaces;
- enforcing resource allocation policies.

Examples of products and technologies commonly associated with Type 1 virtualization include VMware ESXi, Xen, and Hyper-V's hypervisor architecture. Their internal implementations differ, so the architectural category should not be interpreted as meaning that every Type 1 product works identically.

Modern processors provide hardware virtualization capabilities that make efficient VM execution practical. The hypervisor can use processor privilege mechanisms and virtualization extensions so that guest operating systems can execute many instructions directly while privileged operations remain controlled by the virtualization layer.

The Python `Type1Hypervisor` class models this architecture by associating a hypervisor directly with `HostResources`. The C++ case study also constructs a `Hypervisor` using `HypervisorType::Type1`, representing the physical server as the foundation of the virtualization environment.

## Type 2 Hypervisors

A Type 2 hypervisor runs on top of a host operating system.

The host operating system manages the physical computer while the hypervisor application requests resources and services from that operating system. Guest operating systems execute inside VMs managed by the Type 2 layer.

This arrangement is useful for environments where virtualization is primarily a software application on a workstation. Developers can run Linux VMs on a Windows or macOS host without replacing the host operating system with a dedicated bare-metal virtualization platform.

The additional host operating-system layer can affect resource management and the execution path. The hypervisor is not the only privileged software layer controlling the physical machine.

The Python implementation represents this distinction with `Type2Hypervisor`, which includes a `host_os` attribute. The program therefore distinguishes the architectural location of the hypervisor rather than treating Type 1 and Type 2 as merely different names for the same object.

The JavaScript implementation uses the same architectural distinction through `HypervisorType.TYPE_1` and `HypervisorType.TYPE_2` while concentrating on management events rather than duplicating the Python resource model.

## Virtual Machines

A virtual machine is a software-defined computing environment containing virtual hardware presented to a guest operating system.

A VM normally has virtual resources such as:

- virtual CPUs;
- virtual memory;
- virtual disks;
- virtual network interfaces;
- firmware or boot configuration;
- virtual controllers;
- device interfaces exposed by the virtualization platform.

A guest operating system interacts with virtual hardware rather than directly managing every physical device.

For example, a guest may see a virtual disk exposed through a virtual storage controller. The hypervisor or its storage subsystem translates the guest's virtual I/O operations into operations against an underlying storage resource.

The Python `VirtualMachine` class models this relationship by keeping CPU, memory, disks, NICs, state, and snapshots together. The C++ implementation uses a similar object model but places it inside a larger infrastructure-management scenario.

## VM Creation

Creating a VM involves more than allocating a name.

A management system must validate the requested resources and establish the virtual hardware configuration.

The Python simulator requires:

- a unique VM name;
- a positive virtual CPU count;
- at least 128 MB of configured memory;
- positive virtual storage;
- a guest operating system identifier.

The hypervisor then creates a virtual disk and a virtual network interface. The VM receives a unique identifier and is inserted into the hypervisor's VM inventory.

The JavaScript implementation follows a similar management sequence but introduces an event-driven control plane. A successful `createVM()` operation emits a `vmCreated` event, allowing an audit or automation component to react without embedding audit logic inside the VM itself.

The C++ case study creates production-style workloads such as `web-frontend`, `database-primary`, and `monitoring`. These are deliberately treated as infrastructure workloads rather than generic programming examples.

## Resource Allocation

The physical server has finite resources.

If a host has 16 CPU cores, a policy that prevents CPU overcommitment cannot allocate 20 vCPUs across active VMs.

The Python implementation checks this relationship using `allocated_cpu` and `resources.cpu_cores`.

Memory is handled separately because memory virtualization has different characteristics from CPU scheduling. The simulator can operate with strict memory allocation or explicitly allow memory overcommitment.

Storage is also accounted for independently. A VM's configured virtual disk capacity contributes to the host's allocated storage even when a thin-provisioned virtual disk has not yet consumed its complete physical backing capacity.

These distinctions are important because configured capacity, committed capacity, and physically consumed capacity are not necessarily the same thing.

## Virtual CPU Scheduling

A vCPU is a virtual execution resource. It does not automatically represent a permanently dedicated physical CPU core.

A hypervisor schedules vCPUs onto physical execution resources. The scheduler must deal with workloads that may simultaneously request more execution capacity than is available.

The Python `schedule_cpu()` method provides a simplified round-robin-style accounting model. It does not reproduce a production scheduler, but it demonstrates the fundamental relationship between vCPUs and physical CPU resources.

The C++ case study calls `scheduleCPU()` repeatedly and records simulated CPU execution time for the web and database workloads.

Real systems may consider:

- CPU affinity;
- scheduling priority;
- physical CPU topology;
- simultaneous multithreading;
- NUMA locality;
- interrupt activity;
- VM workload characteristics;
- CPU reservations and limits;
- virtualization overhead.

The simplified models intentionally avoid claiming that a few lines of scheduling logic reproduce a production hypervisor scheduler.

## Memory Virtualization

Memory virtualization creates a mapping between addresses used by the guest and physical memory available on the host.

A guest operating system maintains its own view of memory. The virtualization platform must ultimately ensure that guest memory accesses are translated and isolated from memory belonging to other guests and the hypervisor.

Modern systems can use hardware-supported second-level address translation mechanisms. The exact mechanism depends on processor architecture and platform implementation.

Memory overcommitment introduces another layer of complexity. If VMs collectively request more memory than the host physically possesses, the platform requires a mechanism for managing the difference.

Possible techniques include:

- memory ballooning;
- page sharing;
- memory compression;
- host swapping;
- dynamic reclamation;
- workload-specific memory limits.

The Python and JavaScript programs explicitly demonstrate an `allowMemoryOvercommit` policy. The programs also report memory pressure so that the distinction between requested memory and physical capacity remains visible.

Overcommitment can improve utilization, but excessive memory pressure can cause significant performance degradation.

## Virtual Storage

The virtual disk is the guest-visible storage device.

The backing storage can be represented by files, logical volumes, block devices, network storage, or other storage abstractions depending on the virtualization platform.

The Python `VirtualDisk` class tracks:

- capacity;
- current usage;
- storage path;
- virtual bus;
- thin-provisioning behavior.

The JavaScript implementation uses a similar disk abstraction but emphasizes runtime validation and management errors.

The C++ case study attaches a virtual disk to each production workload and exercises storage writes. A write that would exceed virtual capacity is rejected instead of silently corrupting state.

Virtual storage also introduces operational concerns such as I/O latency, throughput, queue depth, durability, snapshot behavior, and backing-storage capacity.

## Virtual Networking

A VM normally receives a virtual network interface rather than a physical network card.

The virtualization platform can connect that interface to different networking models.

The implementations model:

- NAT;
- bridged networking;
- host-only networking.

NAT allows guest traffic to be translated through a host-side networking boundary. Bridged networking places the VM's virtual interface into a network environment that behaves more directly like a separate machine on the physical network. Host-only networking provides a more isolated communication model intended for host-to-guest or controlled local communication.

The Python simulator creates a virtual NIC with a generated MAC address and demonstrates disconnecting and reconnecting it.

A production virtual network may contain virtual switches, VLANs, software-defined network controls, firewall policies, routing, port groups, security groups, and traffic monitoring.

## VM Lifecycle

VM management is stateful.

The Python and JavaScript implementations model these states:

    CREATED
       |
       v
    RUNNING <----> PAUSED
       |
       v
    STOPPED
       |
       v
    DESTROYED

A created VM can be started. A running VM can be paused or shut down. A paused VM can resume. A destroyed VM cannot be started again.

Lifecycle validation prevents invalid transitions.

For example, attempting to start a destroyed VM raises an error. Attempting to pause a VM that is not running is also rejected.

This state validation is important because management APIs must prevent contradictory operations from reaching lower-level virtualization components.

The JavaScript implementation makes lifecycle changes observable through `EventEmitter`. A `stateChanged` event records the previous and new state, which resembles the event-driven nature of real infrastructure-management systems.

## Snapshots

A VM snapshot captures a point-in-time representation of selected VM state.

The Python implementation records:

- VM state;
- virtual CPU count;
- configured memory;
- disk usage.

The JavaScript implementation stores the same kind of metadata using JavaScript objects and `Map` structures.

The C++ case study creates a snapshot of the database VM before maintenance and restores it after a simulated maintenance operation.

A snapshot should not automatically be interpreted as a complete backup. Real snapshot implementations have different semantics depending on the virtualization platform and storage architecture. They may use copy-on-write storage structures and can consume substantial backing storage as data changes.

Snapshot consistency also depends on whether guest filesystem or application state is coordinated. A crash-consistent snapshot is not automatically equivalent to an application-consistent backup.

## Python Implementation

The Python implementation is designed as a broad simulator.

Its major components are:

### `HostResources`

This class represents physical CPU, memory, and storage capacity. Validation prevents a hypervisor from being constructed with nonsensical negative or zero capacities.

### `VirtualDisk`

This object models virtual storage capacity and usage. The `write()` operation validates capacity before changing disk state.

### `VirtualNIC`

This object represents a virtual network interface and its connection state.

### `VirtualMachine`

This class owns VM resources and lifecycle state. It implements startup, pause, resume, shutdown, destruction, snapshot creation, snapshot restoration, disk attachment, and network-interface attachment.

### `Hypervisor`

This is the central resource manager. It maintains the VM inventory, calculates resource allocation, validates new VM requests, and simulates CPU scheduling.

### `Type1Hypervisor` and `Type2Hypervisor`

These subclasses make the architectural distinction explicit. The Type 2 implementation records a host operating system, while the Type 1 implementation models a direct hardware virtualization layer.

The script also demonstrates memory overcommitment, resource pressure, failure conditions, virtual networking, and security-boundary considerations.

## JavaScript Implementation

The JavaScript program takes a complementary approach.

Its central design is event-driven.

`Hypervisor` extends Node.js `EventEmitter`. VM creation emits `vmCreated`, lifecycle changes emit `stateChanged`, destruction emits `vmDestroyed`, and CPU scheduling emits `cpuScheduled`.

This design separates the core VM management operation from listeners that may perform logging, monitoring, auditing, or automation.

The `ManagementController` introduces asynchronous operations through `async` functions. Its `provisionVM()`, `startVM()`, and `shutdownVM()` methods model the management-plane pattern in which an API request may trigger asynchronous infrastructure work.

The JavaScript implementation also demonstrates:

- `Map` for VM and snapshot inventories;
- `crypto.randomUUID()` for management identifiers;
- cryptographic hashing for deterministic simulated MAC generation;
- nullish coalescing for configuration defaults;
- asynchronous Promise-based management operations;
- event-driven audit logging;
- explicit lifecycle validation;
- memory-overcommitment;
- virtual disk failure handling.

The use of `EventEmitter` is particularly relevant to infrastructure systems because operational state changes frequently need to feed independent logging and monitoring components.

## C++ Infrastructure Case Study

The C++ implementation models a private infrastructure server called `Compute-01`.

The server has:

- 16 physical CPU cores;
- 32 GB of memory;
- 1 TB of storage.

The platform provisions three workloads:

    web-frontend
    database-primary
    monitoring

The web workload receives 2 vCPUs, 4 GB of memory, and 40 GB of storage.

The database workload receives 4 vCPUs, 8 GB of memory, and 120 GB of storage.

The monitoring workload receives 2 vCPUs, 2 GB of memory, and 30 GB of storage.

Each VM receives a virtual disk and a virtual NIC.

The case study then exercises lifecycle management, storage activity, CPU scheduling, snapshots, resource validation, failure handling, and restoration.

The C++ implementation uses `std::unordered_map` for the hypervisor VM inventory. This provides efficient average-case lookup by VM identifier.

`std::vector` stores VM-owned virtual disks and network interfaces because each VM can have multiple devices.

`std::map` stores snapshots because snapshot identifiers are used as explicit lookup keys and deterministic iteration is useful for this small management model.

Exceptions represent management failures such as insufficient resources, invalid lifecycle transitions, invalid storage operations, and unknown VM identifiers.

## Resource Validation and Failure Handling

Resource validation should occur before provisioning changes the VM inventory.

The programs reject requests when:

- CPU capacity would be exceeded;
- memory capacity would be exceeded when overcommitment is disabled;
- storage capacity would be exceeded;
- VM memory is below the configured minimum;
- storage write capacity would be exceeded;
- a duplicate VM name is requested;
- a lifecycle operation is incompatible with the current VM state;
- a destroyed VM is modified.

This ordering matters. A management system should avoid partially provisioning a VM and then discovering that the remaining resources are unavailable.

Production systems may also require transactional behavior across multiple resources. For example, storage creation, network attachment, metadata registration, and VM startup may need coordinated rollback when one operation fails.

## Isolation

One of the primary purposes of virtualization is controlled isolation.

A hypervisor must prevent one guest from arbitrarily accessing another guest's memory or privileged execution context.

Isolation involves more than assigning different VM identifiers.

A production virtualization stack can rely on:

- CPU privilege and virtualization mechanisms;
- hardware-assisted memory translation;
- isolation of virtual devices;
- controlled access to physical devices;
- virtual network segmentation;
- management-plane authorization;
- hypervisor patching;
- secure configuration of management interfaces.

Virtual device emulation can itself create security risk because a complex device implementation processes input originating from guest environments.

A VM should therefore be treated as a security boundary that requires continuous maintenance rather than as an automatic guarantee of perfect isolation.

## Type 1 and Type 2 Comparison

| Characteristic | Type 1 | Type 2 |
|---|---|---|
| Primary execution layer | Directly on physical hardware | Above a host operating system |
| Host OS underneath virtualization layer | Not required in the conventional architecture | Required |
| Typical environment | Servers, infrastructure, data centers | Desktops, development, laboratories |
| Hardware control | Hypervisor has direct responsibility | Host OS remains involved |
| Management focus | Infrastructure-scale resource management | Application-oriented virtualization |
| Example use | Consolidated server workloads | Developer VM on a workstation |
| Main architectural distinction | Hardware is beneath the hypervisor | Host OS is beneath the hypervisor |

The distinction describes architecture, not a universal performance ranking. Actual performance depends on hardware support, workload, configuration, device paths, storage, networking, scheduling, and the particular virtualization implementation.

## Virtualization Versus Emulation

Virtualization and emulation are related but different concepts.

Virtualization generally allows a guest environment to execute against an abstraction of hardware that corresponds closely enough to the underlying architecture for efficient execution.

Emulation can reproduce a different processor or hardware architecture in software. This can provide compatibility with hardware architectures that do not match the host processor but usually introduces a different performance profile.

The implementations in this project focus on virtualization management and do not attempt to emulate CPU instructions.

## CPU Virtualization Considerations

A virtual CPU is an abstraction.

When several VMs have active vCPUs, the virtualization platform must decide when each vCPU receives physical execution time.

Important production considerations include:

- physical CPU topology;
- scheduling fairness;
- VM CPU limits;
- reservations;
- affinity;
- NUMA placement;
- interrupt handling;
- workload burst behavior;
- virtualization overhead.

The sample schedulers deliberately simplify these issues. Their purpose is to make resource accounting visible rather than to reproduce production scheduling algorithms.

## Memory Overcommitment

Strict allocation ensures that configured VM memory does not exceed host memory.

For example, a host with 8 GB of RAM cannot strictly allocate 6 GB to one VM and another 4 GB to a second VM.

Overcommitment changes this rule.

A virtualization platform may permit a combined virtual allocation larger than physical memory if it expects workloads not to consume their entire configured memory simultaneously or if it has mechanisms to reclaim memory.

The Python and JavaScript examples explicitly enable this behavior and show memory pressure.

The important operational distinction is:

    configured VM memory
              !=
    actively consumed physical memory

A platform that permits overcommitment without sufficient reclamation capacity can experience severe memory pressure.

## Storage Provisioning Models

The Python simulator marks its default disks as thin-provisioned.

A thin-provisioned virtual disk can expose a large logical capacity while consuming physical storage progressively as data is written.

A thick or fully allocated disk reserves more backing capacity up front.

Thin provisioning improves storage utilization but introduces an operational requirement: the underlying storage system must be monitored. If many thin-provisioned disks grow simultaneously, physical capacity can become exhausted even though each VM individually appears to have sufficient logical capacity.

Snapshots can add another layer of storage consumption because changed blocks may need to be preserved relative to the snapshot state.

## Virtual Networking Models

The examples use NAT as the default virtual networking mode.

The available conceptual modes are:

| Mode | Behavior |
|---|---|
| NAT | Guest traffic is translated through the virtualization host's networking path |
| Bridged | Guest networking is connected more directly to an external network |
| Host-only | Guest communication is restricted to a controlled host-side network |

A production environment can build considerably more complex virtual networks using virtual switches, VLANs, routing, firewalling, software-defined networking, and network policy.

A virtual NIC therefore represents an interface endpoint, not merely a data structure containing a MAC address.

## Common Management Mistakes

### Treating a VM as only a process

A VM has virtual CPU, memory, storage, networking, firmware, and lifecycle state. Stopping a process does not provide the same semantics as shutting down a guest operating system.

### Confusing snapshots with backups

Snapshots depend on the underlying virtualization and storage implementation. They should not automatically be treated as an independent disaster-recovery copy.

### Ignoring host capacity

Creating VMs without resource accounting can cause CPU contention, memory exhaustion, or storage exhaustion.

### Assuming virtual capacity equals physical consumption

Thin-provisioned storage and memory overcommitment demonstrate why configured capacity and physical consumption must be monitored separately.

### Treating isolation as automatic

Virtualization provides an isolation architecture, but secure isolation depends on the hypervisor, hardware, virtual devices, configuration, updates, and management controls.

### Allowing invalid lifecycle transitions

Management APIs should explicitly validate state transitions. A destroyed VM should not silently return to a running state.

## Performance Considerations

Virtualization introduces management and execution overhead.

CPU virtualization can be highly efficient with hardware support, but scheduling still matters when many vCPUs compete for physical CPUs.

Memory virtualization introduces address-translation work and can be affected by memory locality and host pressure.

Storage performance depends heavily on the backing device, virtualization layer, caching, queueing, filesystem or block-storage implementation, and workload pattern.

Network performance depends on the virtual NIC, virtual switch, host networking stack, physical interface, and network configuration.

The Python and C++ programs expose resource accounting so that these relationships can be reasoned about explicitly.

## Production Considerations

A production hypervisor platform requires more than VM creation.

Important operational controls include:

- authenticated management access;
- role-based authorization;
- secure management networks;
- hypervisor patching;
- hardware compatibility validation;
- capacity monitoring;
- VM inventory management;
- storage health monitoring;
- network isolation;
- logging and auditing;
- backup and recovery procedures;
- controlled lifecycle operations;
- resource reservations and limits;
- alerting for host resource pressure.

The JavaScript audit controller demonstrates the architectural idea of separating infrastructure state changes from audit processing.

The Python implementation demonstrates validation and resource accounting.

The C++ case study demonstrates how these controls can be composed into a coherent infrastructure-management engine.

## Security Considerations

The hypervisor occupies a privileged position because it mediates access to physical resources.

Security concerns therefore include:

- vulnerabilities in the hypervisor itself;
- vulnerable virtual-device implementations;
- unauthorized management access;
- insecure VM images;
- weak isolation configuration;
- exposed management interfaces;
- improper storage permissions;
- untrusted guest workloads;
- insufficient logging.

Management interfaces deserve particular attention. A secure VM isolation boundary can still be undermined if an unauthorized user can create, modify, attach devices to, or destroy VMs.

The example programs model authorization-adjacent validation and isolation concepts but do not implement a production authentication or authorization system.

## Debugging the Simulations

When a VM operation fails, the most useful diagnostic sequence is to inspect:

- current VM state;
- requested resource amounts;
- currently allocated resources;
- host capacity;
- virtual disk capacity;
- attached virtual devices;
- lifecycle transition being attempted.

The Python program reports explicit validation failures. The JavaScript program propagates management errors through rejected operations and catches them at the top-level execution boundary. The C++ program uses exceptions to preserve failure information while preventing invalid state transitions from being silently accepted.

These patterns make the simulated management plane easier to reason about than a system that silently ignores invalid requests.

## Limitations of the Implementations

These programs are educational management models, not actual hypervisors.

They do not:

- execute guest CPU instructions;
- configure Intel VT-x or AMD-V;
- manipulate page tables;
- implement real second-level address translation;
- control physical PCI devices;
- implement real virtual switches;
- boot guest operating systems;
- create real virtual disk files;
- provide real snapshot consistency;
- implement production CPU scheduling;
- provide real VM migration;
- provide live memory migration;
- implement production-grade authentication.

The abstractions are intentionally focused on the relationship between hypervisor architecture, VM resources, lifecycle management, and infrastructure control.

## Relationship Between the Three Implementations

The implementations share the same virtualization concepts but deliberately emphasize different engineering perspectives.

The Python program is the broadest simulator. It makes resource accounting, VM lifecycle, snapshots, virtual disks, networking, CPU scheduling, and memory overcommitment explicit in one executable model.

The JavaScript program emphasizes an infrastructure control plane. Its `EventEmitter` architecture shows how VM state changes can become observable events, while its asynchronous controller resembles management APIs that perform operations outside the immediate call stack.

The C++ program focuses on a coherent infrastructure case study. It models a physical server, production-style workloads, resource allocation, device attachment, scheduling, snapshots, capacity failures, and restoration as one management system.

Together, these perspectives show that virtualization is not simply the act of "running a VM." A hypervisor must continuously translate physical capacity into controlled virtual resources while maintaining lifecycle correctness, isolation, and predictable resource management.
