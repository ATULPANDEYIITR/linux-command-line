# Network Virtualization: Virtual Networks, Virtual Switches, SDN, and Overlays

## Scope

Network virtualization separates logical network behavior from the physical network infrastructure that carries packets. A virtual network can provide an isolated Layer-2 or Layer-3 environment without requiring a dedicated physical network for every tenant or application.

This laboratory treats four closely related mechanisms as distinct technical areas:

- **Virtual networks** define logical connectivity domains, address spaces, segmentation, and tenant isolation.
- **Virtual switches** implement virtualized data-plane forwarding, including port attachment, MAC learning, forwarding tables, and flow rules.
- **Software-defined networking (SDN)** separates network control decisions from packet forwarding so a controller can program forwarding behavior and apply centralized policy.
- **Network overlays** encapsulate logical network traffic inside an underlay transport, allowing virtual networks to span physical hosts, racks, or data-center locations without requiring the physical topology to reproduce the logical topology.

The six deliverables use the same general subject but deliberately approach it from different technical perspectives.

## Fundamental Network Virtualization Model

A traditional physical network associates a physical interface, switch port, broadcast domain, and often a physical device with network connectivity. Virtualization introduces logical objects that can be mapped onto shared physical infrastructure.

A useful abstraction is:

`endpoint -> virtual port -> virtual switch -> logical network -> underlay`

The logical network can be identified by an identifier such as a VLAN ID or VXLAN VNI. The physical infrastructure does not necessarily need to understand every logical endpoint. It can transport traffic between virtualization endpoints while the virtual network layer preserves logical segmentation.

The distinction between logical and physical topology is important. A tenant may see two machines as members of the same logical network even when those machines are connected to different physical hosts and different physical switches.

Virtualization therefore provides isolation and abstraction, while the physical underlay provides transport capacity and reachability.

## Virtual Networks

A virtual network is the logical connectivity domain in which endpoints are associated with a particular network identity and addressing policy.

The Python implementation represents a virtual network with `VirtualNetwork`. Each network has:

- a name
- a CIDR address space
- a logical network identifier
- endpoint membership

The implementation validates that an endpoint address belongs to the virtual network's CIDR. It also prevents duplicate endpoint names and MAC addresses.

The two example networks are `tenant-a` and `tenant-b`. Their address spaces are deliberately separate:

- `tenant-a`: `10.10.10.0/24`
- `tenant-b`: `10.20.20.0/24`

This models tenant isolation without requiring a separate physical switch for each tenant.

The Java program represents the same concept with the immutable `VirtualNetwork` record. Java's record syntax is useful here because the network definition is primarily configuration and identity data rather than mutable runtime state.

The SQL implementation treats virtual networks as first-class database entities. The `virtual_network` table stores the CIDR, VNI, segment type, and unique network identity. PostgreSQL's `CIDR` type represents the address range directly rather than storing a network as unvalidated text.

The SQL constraint `CHECK (vni BETWEEN 1 AND 16777215)` is specifically relevant to VXLAN-style 24-bit VNIs. The database therefore rejects an invalid identifier instead of depending solely on an application validation routine.

## Virtual Network Isolation

Isolation is not simply a property of having different names. A real system must enforce whether traffic is permitted between logical networks.

The examples use explicit tenant policy:

`tenant-a -> tenant-a = ALLOW`

`tenant-b -> tenant-b = ALLOW`

`tenant-a -> tenant-b = DENY`

`tenant-b -> tenant-a = DENY`

The Python `SdnController.evaluate_policy()` method performs this policy decision before forwarding. The C++ case study uses `TenantPolicy` to maintain explicit source-VNI and destination-VNI decisions. The Java implementation uses `PolicyEngine`, which stores `Decision.ALLOW` or `Decision.DENY`.

This separation matters because forwarding and authorization are different responsibilities. A virtual switch can know where a MAC address resides without necessarily being authorized to forward traffic between two isolated tenants.

## Virtual Switches

A virtual switch is a software implementation of switching behavior. It connects virtual or physical interfaces and makes forwarding decisions for frames.

The Python `VirtualSwitch` maintains:

- virtual ports
- a MAC learning table
- an SDN flow table
- forwarding and drop counters

When a packet enters the switch, the source MAC is learned against the ingress port. If the destination is known, the switch can forward directly. If the destination is unknown, the model produces an unknown-unicast flood.

The important distinction is between **MAC learning** and **controller-programmed flows**.

MAC learning discovers forwarding information from observed traffic. A controller-programmed flow is an explicit data-plane instruction produced by control-plane policy.

The JavaScript implementation makes this distinction observable through `macTable` and `flowTable`. The `forward()` method first checks a programmed flow and then falls back to the learned MAC table.

The C++ program uses `unordered_map` for MAC learning and a vector of `FlowRule` objects sorted by priority. This emphasizes the data structures used by a forwarding implementation rather than simply printing a conceptual switch diagram.

## Virtual Switch Forwarding Behavior

A simplified forwarding sequence is:

`receive frame -> validate ingress -> learn source -> lookup flow -> lookup MAC -> forward or flood`

The Python implementation returns one of:

- `FORWARD`
- `DROP`
- `FLOOD`

A packet is dropped when the ingress port is invalid. A known destination produces a forwarding decision. An unknown destination produces flooding.

A production virtual switch has substantially more state and processing. It may perform VLAN classification, VLAN translation, ACL evaluation, QoS classification, tunnel processing, connection tracking, multicast handling, and hardware offload decisions.

The laboratory intentionally keeps the forwarding model focused on virtualization concepts rather than reproducing an entire production switching stack.

## Software-Defined Networking

SDN introduces a separation between the **control plane** and the **data plane**.

The data plane is responsible for processing packets according to installed forwarding state. The control plane determines what forwarding state should exist.

The Python `SdnController` registers virtual switches and installs `FlowRule` objects. The controller does not directly simulate every packet. Instead, it programs the switch and lets the switch apply the resulting rule.

This distinction is central to SDN.

A conceptual flow is:

`policy -> controller decision -> flow installation -> virtual switch forwarding`

This is different from simply placing all network logic inside a switch.

The C++ implementation makes this separation explicit through `SdnController` and `VirtualSwitch`. The controller owns switch registration and policy while the switch owns forwarding state.

The Java implementation uses the same architectural separation but models the controller as an enterprise service containing network inventory, policy evaluation, flow programming, and audit events.

## Control Plane and Data Plane

The control plane answers questions such as:

- Which path should traffic use?
- Is a source network allowed to communicate with a destination network?
- Which output port should a destination MAC use?
- Should a new flow be installed?
- Is a virtual switch available?
- Is an overlay endpoint healthy?

The data plane answers a narrower runtime question:

`Given this packet and the forwarding state currently installed, what should happen to the packet?`

Separating these responsibilities provides central control while avoiding the need for the controller to process every data packet.

A failure in the control plane and a failure in the data plane also have different consequences. A switch may continue forwarding existing flows during a temporary controller outage, depending on the architecture and the expiration behavior of its forwarding state.

The examples model flow state and expiration because programmed forwarding entries are operational state, not permanent truth.

## SDN Flow Rules

A flow rule can be viewed as a match/action relationship.

The simplified model uses:

`destination MAC -> output port`

Real OpenFlow-style systems can match on substantially more information, including ingress port, Ethernet fields, VLAN information, IP addresses, transport protocols, and other metadata.

The Python `FlowRule` also contains:

- priority
- idle timeout
- installation timestamp
- packet count

Priority matters when multiple rules can match the same traffic. Timeout matters because stale forwarding state can produce incorrect or inefficient behavior after topology or endpoint changes.

The SQL `flow_rule` table stores similar state relationally and indexes the fields needed for forwarding lookup.

## SDN Policy Versus Forwarding

Policy and forwarding should not be conflated.

For example, a switch can have a valid flow for the MAC address of `web-b`, but an isolation policy can still prohibit `web-a` from reaching the `tenant-b` network.

The examples therefore perform policy evaluation separately from forwarding lookup.

This distinction becomes particularly important in larger systems where security groups, network ACLs, service insertion, routing policy, identity, and segmentation all affect whether a packet should be forwarded.

## Network Overlays

An overlay creates a logical network on top of an underlay.

The underlay provides physical or routed IP connectivity between tunnel endpoints. The overlay provides logical network semantics above that transport.

A simplified model is:

`inner Ethernet frame -> encapsulation -> underlay packet -> decapsulation -> inner frame`

VXLAN is a common data-center overlay technology. VXLAN uses a 24-bit VXLAN Network Identifier, or VNI, to distinguish logical Layer-2 segments.

The examples use VNIs such as `1010` and `2020` to represent tenant segments.

The VNI is not an IP subnet. It is a logical segment identifier. The IP address of the VTEP belongs to the underlay-facing transport side, while the inner packet retains the logical tenant information.

## VTEPs

A VXLAN Tunnel Endpoint, or VTEP, performs encapsulation and decapsulation.

The Python `OverlayNetwork` maps switches to VTEP addresses and maps virtual networks to VNIs.

The resulting `OverlayFrame` contains:

- outer source VTEP
- outer destination VTEP
- VNI
- inner packet

This intentionally separates the outer transport identity from the inner tenant identity.

The JavaScript implementation represents the same relationship using an object with `outer`, `vni`, and `inner` properties. Its asynchronous controller checks model the fact that real overlay deployment also depends on operational conditions such as underlay reachability and VTEP availability.

The Java `OverlayService` uses an immutable `OverlayFrame` record. This prevents accidental modification of an encapsulated frame's identity after creation.

## Overlay Isolation

A VNI must be validated during decapsulation.

The implementations deliberately attempt an invalid operation by trying to decapsulate a tenant-A frame as tenant B.

The Python implementation raises `PermissionError`.

The C++ implementation throws an exception from `OverlayNetwork::decapsulate()`.

The Java implementation throws `SecurityException`.

The JavaScript implementation throws an ordinary `Error` with a VNI mismatch message.

The common architectural principle is more important than the language-specific exception type: the receiving tunnel endpoint must not blindly accept an overlay frame as belonging to an arbitrary logical network.

## Underlay and Overlay Relationship

The underlay and overlay solve different problems.

The **underlay** supplies transport reachability between tunnel endpoints. It is concerned with physical links, routed IP addresses, routing, MTU, failures, and transport availability.

The **overlay** supplies logical network identity and tenant segmentation. It is concerned with VNIs, tunnel endpoints, encapsulation, decapsulation, and mapping logical networks onto tunnel infrastructure.

An overlay cannot compensate for an unreachable underlay. Conversely, an operational underlay does not automatically establish correct tenant isolation if the overlay mappings or policies are wrong.

This is why the JavaScript implementation runs status checks for underlay reachability, VTEP health, and VNI consistency before declaring the overlay deployment ready.

## Python Implementation

The Python program is a progressively executable network virtualization simulator.

`VirtualNetwork` models logical network membership and CIDR validation. `VirtualSwitch` models virtual ports, MAC learning, flow rules, forwarding, flooding, and counters.

`SdnController` models the SDN control plane. It registers switches, associates switches with virtual segments, evaluates tenant policy, and installs destination-specific flows.

`OverlayNetwork` models VTEP and VNI relationships and creates an `OverlayFrame` containing the outer transport identity and inner packet.

The program also exposes operational state through counters and an audit log. This is important because a network virtualization implementation is not only a forwarding mechanism; it needs observability to diagnose incorrect flows, unexpected drops, and policy decisions.

The validation examples demonstrate an endpoint outside the configured virtual network being rejected. The forwarding examples demonstrate the transition from unknown destination flooding to learned forwarding and finally controller-programmed forwarding.

## JavaScript Implementation

The JavaScript implementation emphasizes event-driven control behavior.

`SdnController` extends Node.js `EventEmitter`. Flow installation and status-check completion produce events, allowing the controller to expose operational changes without coupling every component directly to the controller's internal implementation.

The asynchronous `runStatusChecks()` method uses Promises and `await` to model sequential controller-side operational checks.

The JavaScript model also uses `Map` for switch and network registries. This is appropriate for keyed lookup of dynamic infrastructure objects.

The implementation intentionally differs from the Python program by treating controller operations as event-producing asynchronous operations rather than presenting the network primarily as a synchronous simulator.

## C++ Case Study

The C++ program models a repository-independent network virtualization control system with two tenant networks.

Its central classes are `VirtualSwitch`, `TenantPolicy`, `SdnController`, `OverlayNetwork`, and `GovernanceEngine`.

`VirtualSwitch` uses an `unordered_map` for learned MAC state and a priority-sorted collection of flow rules. The forwarding method demonstrates the data-plane sequence of source learning followed by destination resolution.

`TenantPolicy` uses a map keyed by a source-VNI and destination-VNI pair. An absent rule is treated as denied, producing a fail-closed policy model.

`SdnController` owns references to registered switches and performs explicit flow installation. The controller therefore represents the control plane while the switch represents the data plane.

`OverlayNetwork` provides VNI registration, VTEP registration, encapsulation, and VNI validation during decapsulation.

The case study also includes deployment status checks. This reflects an operational reality: network programming should not be considered complete merely because a desired configuration exists. Reachability and endpoint health can determine whether an overlay deployment is actually usable.

The implementation is C++17-compatible and uses standard containers, exceptions, `optional`, and algorithms without third-party libraries.

## Java Implementation

The Java implementation takes an enterprise domain-model approach.

The `VirtualNetwork`, `Endpoint`, `FlowKey`, `FlowRule`, `StatusCheck`, and `OverlayFrame` records provide immutable value-oriented representations for configuration and events.

`VirtualSwitch` owns mutable runtime state because forwarding tables and device state naturally change during operation.

`PolicyEngine` represents explicit network policy decisions, while `SdnController` acts as a service that manages infrastructure registration, authorization, flow installation, and audit events.

`DeploymentGate` uses Java Streams to evaluate whether all operational checks have passed. This is a deliberately different role from the network policy engine: the deployment gate determines whether the configured environment is operationally ready, whereas policy determines whether a traffic relationship is permitted.

The use of enums for `SegmentType`, `DeviceState`, `Decision`, and `FlowState` prevents important domain states from being represented as arbitrary strings.

The Java implementation therefore demonstrates how network virtualization concepts can be represented in an enterprise-oriented domain model rather than as a collection of procedural forwarding functions.

## SQL Data Model

The PostgreSQL implementation treats network virtualization as a relational system.

`virtual_network` stores logical network identity, CIDR addressing, VNI, and segment type.

`virtual_switch` stores virtual-switch inventory and operational state.

`switch_port` associates ports with switches and distinguishes endpoint, uplink, and VTEP roles.

`endpoint` associates MAC and IP addresses with logical networks and virtual switch ports.

`vtep` stores tunnel endpoint addresses.

`overlay_mapping` maps logical networks to VNIs.

`sdn_policy` stores source-network and destination-network policy decisions.

`flow_rule` stores controller-programmed data-plane forwarding state.

`mac_learning` models learned MAC-to-port state.

`control_event` provides an operational audit trail.

Foreign keys prevent orphaned relationships. Unique constraints prevent duplicate network identifiers, VNIs, MAC addresses, IP addresses, switch names, and port names within a switch.

The database indexes reflect actual lookup patterns. The flow index supports lookup by switch, network, destination MAC, state, and priority. The policy index supports source/destination policy evaluation.

## Database-Level Integrity

The SQL model demonstrates an important distinction between application validation and database integrity.

An application can check whether a VNI is valid before inserting it, but the database constraint provides a second enforcement boundary. A different application, administrative script, or future service cannot silently insert a VNI outside the allowed range.

Similarly, foreign keys ensure that a flow cannot refer to a nonexistent switch, network, or output port.

The `flow_rule` constraints require an installed flow to have an installation timestamp. Expiration is also constrained to occur after installation when both timestamps exist.

These constraints make invalid states harder to persist.

## Transactions and Operational State

The SQL script includes a transaction that increments the packet count for an installed flow and records the forwarding event.

The transaction groups the operational state change and its audit event.

Without a transaction, a system could theoretically update a flow counter while failing to record the corresponding event, producing inconsistent operational evidence.

Production systems often need stronger event and state consistency guarantees than a simple simulator. Transaction boundaries should therefore be selected around meaningful state transitions rather than arbitrary groups of statements.

## Edge Cases

Unknown destinations are important in virtual switching because MAC learning is not instantaneous. A switch may need to flood unknown unicast traffic until it learns the destination.

A stale flow is another failure condition. A previously correct destination can move to another port, host, or virtual switch. Flow expiration and reprogramming mechanisms prevent old forwarding state from remaining valid indefinitely.

A failed virtual switch should not accept new forwarding operations. The Java implementation models this through `DeviceState`.

A missing VTEP prevents correct overlay encapsulation. The overlay implementations explicitly validate VTEP availability.

A VNI mismatch during decapsulation represents a segmentation error. The examples reject such traffic instead of treating the inner frame as automatically trustworthy.

An unknown SDN policy is treated conservatively in the C++ policy engine. This is a fail-closed approach that is preferable for tenant isolation when accidental cross-network communication would be more damaging than an unintended denial.

## Performance Considerations

Virtualization introduces additional state and processing.

A virtual switch must maintain forwarding state and perform lookups at packet rate. Hash-based MAC tables provide average constant-time lookup behavior in typical implementations, although actual performance depends on collision behavior, memory locality, and implementation details.

Priority-based flow matching can become expensive if many rules are scanned sequentially. Production forwarding engines therefore use optimized classification structures and often offload selected paths to hardware or specialized data-plane implementations.

Overlay encapsulation adds headers and therefore reduces the amount of available payload for a fixed physical MTU. Systems using overlays must account for tunnel overhead and avoid fragmentation problems through appropriate MTU configuration and path validation.

Centralized SDN control can simplify policy management but creates control-plane scaling and availability requirements. Large systems distribute controllers or use clustered control-plane architectures rather than depending on a single process.

## Security Considerations

Tenant isolation should be enforced at multiple layers where appropriate.

VNI assignment must be controlled because an incorrect mapping can associate a packet with the wrong logical network.

VTEP authorization matters because an unauthorized tunnel endpoint should not automatically gain access to every overlay segment.

Flow installation should be authenticated and authorized. A compromised control-plane identity capable of installing arbitrary forwarding rules can bypass intended segmentation.

Control-plane APIs should use authentication, authorization, transport protection, input validation, and audit logging.

MAC learning should also be treated as security-sensitive state. Unexpected MAC movement, excessive learning events, and MAC spoofing can indicate attacks or faulty virtual infrastructure.

The examples do not implement cryptographic authentication or production-grade tunnel security. They focus on the network virtualization mechanisms themselves while explicitly validating logical network identity.

## Common Implementation Mistakes

Treating a virtual network as merely an IP subnet misses the Layer-2 and logical-segmentation aspects of virtualization.

Treating a virtual switch as only a software version of a physical switch misses its relationship with virtual interfaces, hypervisors, overlays, security policy, and software-controlled forwarding.

Treating SDN as synonymous with a controller is also inaccurate. SDN is fundamentally about the separation and programmability of control and data-plane behavior. A controller is one architectural mechanism for implementing that separation.

Treating a VNI as an IP address creates confusion between overlay segmentation and underlay transport.

Treating overlay encapsulation as encryption is a security mistake. Encapsulation provides transport and logical segmentation semantics. It does not automatically provide confidentiality or authentication.

Treating policy approval and forwarding state as the same thing can create dangerous authorization gaps. A forwarding rule says what the data plane can do; a policy determines what it should be allowed to do.

## Architecture Relationship

The four areas fit together without being interchangeable:

`Virtual Network`
defines logical connectivity and segmentation.

`Virtual Switch`
implements local virtual data-plane forwarding.

`SDN`
provides programmable control and policy over forwarding behavior.

`Overlay`
extends logical network connectivity across an underlay by encapsulating traffic.

A typical data-center flow can therefore be understood as:

`application endpoint`
→ `virtual network membership`
→ `virtual switch`
→ `SDN-controlled forwarding state`
→ `overlay encapsulation`
→ `underlay transport`
→ `remote VTEP`
→ `overlay decapsulation`
→ `remote virtual switch`
→ `destination endpoint`

Each stage has a different responsibility. Keeping those responsibilities distinct is essential for designing, debugging, and securing network virtualization systems.

## Debugging Model

A useful troubleshooting sequence is to determine which layer is failing.

If an endpoint cannot communicate with another endpoint on the same logical segment, inspect endpoint membership, virtual port attachment, MAC learning, virtual-switch state, and flow programming.

If same-segment forwarding works but cross-segment traffic is denied, inspect policy rather than the switch's MAC table.

If local virtualization works but remote hosts cannot communicate, inspect VTEP registration, VNI mapping, underlay reachability, and overlay MTU behavior.

If the controller has the correct policy but forwarding does not change, inspect controller-to-switch communication and the installed flow state.

If a previously working path stops functioning, inspect stale flows, endpoint movement, VTEP state, and control-plane events.

The Python audit output, JavaScript events, C++ controller log, Java controller audit, and SQL `control_event` table all provide different mechanisms for observing these transitions.

## Production Considerations

A production implementation would need substantially richer state than this laboratory model.

A virtual switch would need stronger handling for VLANs, routing, ACLs, QoS, multicast, port security, interface lifecycle, link state, and hardware or kernel acceleration where available.

An SDN controller would need topology discovery, controller clustering, state reconciliation, northbound APIs, southbound protocols, authentication, authorization, rollback behavior, idempotent configuration, and failure recovery.

An overlay system would need robust VTEP discovery, endpoint learning, tunnel lifecycle management, MTU management, multicast or control-plane alternatives where applicable, and operational telemetry.

A production network virtualization platform must also distinguish desired configuration from observed state. The desired state might say that a VNI should exist and a flow should be installed, while observed state might show that the switch is unavailable or that the VTEP cannot reach its peer.

The laboratory implementations intentionally make this distinction visible through controller policy, switch state, flow state, overlay mappings, status checks, and database constraints.
