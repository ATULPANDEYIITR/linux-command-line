# Network Security and Traffic Filtering

## 1. Technical Scope

This module implements a network security policy management system using five programming and database technologies.

The central objective is to determine whether network traffic should be allowed or denied by evaluating multiple security controls.

The implementations cover four distinct security mechanisms:

| Mechanism | Primary responsibility | Traffic behavior |
|---|---|---|
| Firewall | Controls traffic using network filtering rules | Stateful or stateless, depending on configuration |
| Security Group | Controls traffic associated with virtual network resources | Stateful |
| Network ACL | Controls traffic entering and leaving a subnet | Stateless |
| Traffic Filtering | Evaluates packet attributes against security policies | Depends on the filtering mechanism |

The examples use an enterprise network containing web, application, and database subnets.

## 2. Network Security Architecture

The simulated environment uses the following address ranges:

| Network | CIDR | Purpose |
|---|---|---|
| Internal network | `10.0.0.0/8` | Trusted internal systems |
| Web network | `172.16.1.0/24` | Public-facing applications |
| Application network | `172.16.2.0/24` | Backend processing |
| Database network | `172.16.3.0/24` | Restricted database services |

The traffic inspection architecture is:

    Incoming Network Traffic
              |
              v
        Packet Validation
              |
              v
          Firewall
              |
              v
        Security Group
              |
              v
         Network ACL
              |
              v
       Traffic Decision
              |
        +-----+-----+
        |           |
       ALLOW       DENY
        |           |
        v           v
    Application   Audit Log

The security group is evaluated for inbound traffic in the implementations. Network ACL evaluation considers the direction of traffic.

A packet must pass every applicable security control to be accepted.

## 3. Firewall Fundamentals

A firewall monitors network traffic and applies predefined security rules.

A firewall rule specifies the conditions under which traffic is accepted or rejected.

The principal attributes are:

| Attribute | Description |
|---|---|
| Rule ID | Unique identifier |
| Source CIDR | Permitted or restricted source network |
| Destination CIDR | Target network |
| Protocol | TCP, UDP, ICMP, or ANY |
| Direction | Inbound or outbound |
| Port range | Applicable destination ports |
| Action | ALLOW or DENY |
| Priority | Rule evaluation order |
| Enabled | Determines whether the rule is active |

### Rule evaluation

The implementations process rules in ascending priority order.

For example:

| Priority | Source | Destination | Protocol | Port | Action |
|---|---|---|---|---|---|
| 100 | `10.0.0.0/8` | `172.16.0.0/12` | TCP | 443 | ALLOW |
| 200 | `0.0.0.0/0` | `172.16.0.0/12` | TCP | 80 | DENY |

A packet matching an applicable rule receives that rule's decision.

If no rule matches, the simulated policy uses default-deny behavior.

### Stateful and stateless firewalls

A stateful firewall maintains connection information.

When an authorized connection is established, the firewall records its identifying information. Return traffic matching the reverse connection can then be accepted without requiring a separate matching outbound rule.

A stateless firewall evaluates each packet independently. Both directions require appropriate rules.

Stateful inspection is useful for tracking established application communications. Stateless inspection provides explicit control over individual packet directions.

## 4. IP Addresses and CIDR

CIDR means Classless Inter-Domain Routing.

It represents a network using an IP address and prefix length.

For example:

`192.168.1.0/24`

The prefix `/24` identifies the first 24 bits as the network portion.

The implementations support IPv4 address validation and CIDR matching.

The C++ and Java implementations convert IPv4 addresses into unsigned 32-bit numerical representations.

The JavaScript implementation uses unsigned bitwise operations.

The Python implementation uses the standard-library `ipaddress` module.

The PostgreSQL implementation uses native `INET` and `CIDR` data types.

Important edge cases include:

- Invalid IPv4 octets.
- Missing CIDR prefixes.
- Prefix lengths outside the permitted range.
- Different IP address families.
- Network boundary addresses.
- Invalid packet addresses.

The JavaScript, C++, and Java demonstrations focus on IPv4. Python and PostgreSQL use capabilities that also support IPv6, although the sample policies primarily demonstrate IPv4.

## 5. Security Groups

A security group is a virtual network security control associated with resources such as virtual machines, application instances, or network interfaces.

Security groups are stateful.

Their primary characteristics are:

- Rules define permitted traffic.
- Unmatched traffic is denied in the demonstrated model.
- Return traffic for established connections is automatically permitted.
- Rules are associated with a particular group.
- Multiple security groups may apply to a resource in real cloud environments.

### Example

An application server requires HTTPS access.

| Source | Destination | Protocol | Port | Decision |
|---|---|---|---|---|
| Internal network | Application server | TCP | 443 | ALLOW |
| Internal network | Application server | TCP | 22 | DENY |
| Internal network | Application server | TCP | 80 | DENY |

The security group permits HTTPS while rejecting unauthorized SSH and HTTP access.

The implementations demonstrate inbound security group evaluation and stateful return traffic.

Cloud providers differ in rule composition and attachment behavior. The simplified examples use an independent policy evaluator for each security group.

## 6. Network Access Control Lists

A Network Access Control List, or Network ACL, applies security rules at the subnet level.

Unlike security groups, network ACLs are stateless.

This means that inbound and outbound traffic must be evaluated independently.

For example, an inbound HTTPS connection may use:

| Attribute | Value |
|---|---|
| Source IP | `10.1.1.10` |
| Destination IP | `172.16.1.20` |
| Source port | 51000 |
| Destination port | 443 |
| Protocol | TCP |

The return packet reverses the address and port relationships:

| Attribute | Value |
|---|---|
| Source IP | `172.16.1.20` |
| Destination IP | `10.1.1.10` |
| Source port | 443 |
| Destination port | 51000 |
| Protocol | TCP |

The inbound and outbound rules must both permit the corresponding traffic.

### Ephemeral ports

Client applications commonly use temporary source ports.

A network ACL may therefore need outbound rules permitting the appropriate ephemeral destination port range for return traffic.

The example uses ports `1024-65535` to illustrate this requirement. Actual production ranges should be restricted to the applicable operating-system and network requirements.

### Key distinction

| Characteristic | Security Group | Network ACL |
|---|---|---|
| Operating level | Resource or network interface | Subnet |
| Stateful | Yes | No |
| Return traffic | Automatically tracked | Requires explicit rules |
| Rule behavior | Allow-based in the demonstrated model | Allow and deny |
| Rule priority | Provider-dependent | Commonly ordered by rule number |
| Default behavior | Deny unmatched traffic | Configurable default behavior |

The PostgreSQL schema explicitly enforces the stateless property of network ACL records.

## 7. Traffic Filtering Workflow

Each packet contains:

- Source IP address.
- Destination IP address.
- Source port.
- Destination port.
- Protocol.
- Direction.

The filtering process follows these operations:

1. Validate the packet.
2. Validate its IP addresses.
3. Validate transport ports.
4. Determine whether an established connection exists.
5. Evaluate enabled rules in priority order.
6. Identify the first matching rule.
7. Apply its action.
8. Apply default-deny behavior when no rule matches.
9. Record the decision.

### Matching conditions

A rule matches when:

- The direction is correct.
- The source address belongs to the source CIDR.
- The destination address belongs to the destination CIDR.
- The protocol matches.
- The destination port belongs to the configured range.

ICMP does not use TCP or UDP transport ports. The implementations therefore treat ICMP separately.

### Default deny

Default deny is a security principle in which traffic is rejected unless an explicit policy permits it.

This reduces exposure caused by missing or incomplete security rules.

A default-deny policy is particularly important for administrative services, databases, and internal application interfaces.

## 8. Python Implementation

The Python implementation models a complete network security evaluation workflow.

### Important components

| Component | Responsibility |
|---|---|
| `Packet` | Represents and validates network traffic |
| `FirewallRule` | Defines matching conditions |
| `ConnectionTracker` | Tracks established connections |
| `StatefulFirewall` | Evaluates firewall policies |
| `SecurityGroup` | Evaluates inbound resource-level rules |
| `NetworkACL` | Evaluates stateless subnet-level rules |
| `NetworkSecurityEngine` | Coordinates security layers |
| `SecurityDecision` | Represents a filtering result |

### Technical decisions

Python's `ipaddress` module provides reliable IP and CIDR operations.

Dataclasses provide structured domain objects.

Enums restrict protocols, directions, actions, and decision reasons to defined values.

The connection tracker uses a set for connection lookup.

The audit mechanism maintains security decisions for reporting.

JSON persistence demonstrates how firewall policies can be exported and restored.

### Complexity

For `n` configured rules, a straightforward rule evaluation requires up to O(n) comparisons.

Sorting rules requires O(n log n).

Connection lookup through a hash set has average O(1) complexity.

The demonstration intentionally favors readable policy evaluation over specialized high-throughput packet processing.

## 9. JavaScript Implementation

The JavaScript implementation uses an event-driven architecture.

### Important components

- `CIDR`: IPv4 network matching.
- `Packet`: Immutable packet representation.
- `FirewallRule`: Traffic policy.
- `ConnectionTable`: Stateful connection storage.
- `PolicyEvaluator`: Rule evaluation.
- `SecurityGroup`: Resource-level filtering.
- `NetworkACL`: Stateless subnet filtering.
- `Firewall`: Stateful firewall filtering.
- `NetworkSecurityGateway`: Multi-layer evaluation.

### Event-driven monitoring

The gateway extends Node.js `EventEmitter`.

Each security decision generates a `security-event` event.

This separates traffic evaluation from monitoring.

An event listener can collect information about:

- Allowed connections.
- Rejected connections.
- The security layer responsible for blocking traffic.
- Matched rules.
- Traffic sources and destinations.

### Asynchronous processing

The traffic-processing function uses asynchronous execution and isolates packet validation errors.

A malformed packet does not prevent subsequent packets from being evaluated.

The implementation uses Node.js filesystem functionality to persist audit information.

### Performance considerations

The implementation uses:

- `Map` for connection tracking.
- `Set` for duplicate rule detection.
- Sorted arrays for ordered policy evaluation.
- EventEmitter for event notifications.

The IPv4 CIDR implementation uses unsigned 32-bit arithmetic.

It is intentionally restricted to IPv4 because JavaScript bitwise operators operate on 32-bit integers.

## 10. C++17 Implementation

The C++ implementation emphasizes domain modeling and deterministic policy evaluation.

### Important components

| Component | Purpose |
|---|---|
| `IPv4Address` | Converts and validates IPv4 addresses |
| `CIDR` | Performs network membership checks |
| `Packet` | Models network traffic |
| `FirewallRule` | Stores filtering conditions |
| `ConnectionTracker` | Maintains established connections |
| `PolicyEvaluator` | Applies ordered rules |
| `Firewall` | Implements stateful firewall behavior |
| `SecurityGroup` | Implements resource-level filtering |
| `NetworkACL` | Implements stateless filtering |
| `NetworkSecurityGateway` | Coordinates the security controls |

### Data structures

The implementation uses:

- `vector` for configured firewall rules.
- `set` for connection tracking.
- `map` for audit aggregation.
- `struct` for packet, rule, connection, and decision records.

The connection structure defines ordering so it can be stored in an ordered set.

Connection lookup therefore has O(log c) complexity, where `c` represents the number of tracked connections.

Rule evaluation has O(n) complexity after initial sorting.

### Error handling

Invalid network addresses, CIDR prefixes, ports, and duplicate rule identifiers produce exceptions.

The gateway distinguishes decisions made by the firewall, security group, and network ACL.

## 11. Java 17 Implementation

The Java implementation represents an enterprise-oriented network security service.

It separates domain objects, policy interfaces, infrastructure controls, and service-level orchestration.

### Domain model

The principal types are:

- `IPv4Address`
- `Cidr`
- `Packet`
- `FirewallRule`
- `ConnectionKey`
- `Decision`
- `AuditEvent`

Records provide immutable representations of packets, rules, connection keys, and audit events.

### Policy abstraction

The `TrafficPolicy` interface defines a common traffic evaluation contract.

`AbstractPolicy` implements shared functionality for rule validation, ordering, and connection tracking.

The concrete policy classes implement their own behavior:

- `Firewall`
- `SecurityGroup`
- `NetworkACL`

This structure prevents the network security service from depending on the internal implementation of every policy.

### Service layer

`NetworkSecurityService` coordinates the filtering sequence.

It performs firewall evaluation first, followed by inbound security group evaluation where applicable, and finally network ACL evaluation.

Audit events record the outcome and the responsible security layer.

### Java collections

| Collection | Application |
|---|---|
| `List` | Rules and audit records |
| `Set` | Duplicate rule detection |
| `Map` | Connection tracking |
| `TreeMap` | Ordered reporting |

The implementation uses Java streams for reporting and immutable collection results for audit retrieval.

## 12. PostgreSQL Implementation

The PostgreSQL implementation models network security as a relational policy-management system.

### Database structure

The principal entities are:

| Table | Purpose |
|---|---|
| `network_zones` | Represents logical network environments |
| `network_subnets` | Stores subnet definitions |
| `firewalls` | Stores firewall configurations |
| `security_groups` | Stores resource-level security groups |
| `network_acls` | Stores subnet-level ACL configurations |
| `security_rules` | Stores filtering rules |
| `packet_events` | Stores observed packet information |
| `tracked_connections` | Stores established connections |
| `security_audit` | Stores filtering decisions |

### Relationships

    Network Zones
         |
         +---- Network Subnets
         |          |
         |          +---- Security Group Associations
         |          |
         |          +---- Network ACL Associations
         |
         +---- Firewalls
                    |
                    +---- Security Rules

    Security Groups
         |
         +---- Security Rules

    Network ACLs
         |
         +---- Security Rules

    Packet Events
         |
         +---- Security Audit

### Constraints

The database applies:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- CIDR address-family validation.
- Protocol restrictions.
- Port-range validation.
- Rule ownership validation.

The `security_rules` table uses a check constraint to ensure that each rule belongs to exactly one applicable security layer.

Partial unique indexes enforce unique rule numbers within individual policy owners.

### PostgreSQL network types

The implementation uses:

- `INET` for individual IP addresses.
- `CIDR` for network ranges.
- `family()` to validate address families.
- `<<=` to check whether an IP address belongs to a network.

GiST indexes support network-oriented lookups.

### Functions and procedures

`find_matching_rule()` identifies the first applicable rule.

`evaluate_traffic()` evaluates a packet against a security policy.

`evaluate_network_stack()` coordinates the firewall, security group, and network ACL evaluations.

`establish_connection()` registers an authorized TCP or UDP connection.

`expire_connections()` updates connections whose expiration time has passed.

### Transactions

The database demonstrates transactional policy modification.

A database transaction ensures that a policy change is committed atomically or rolled back when an error occurs.

### Reporting

The implementation includes queries for:

- Firewall inventory.
- Traffic summaries.
- Allowed and denied packets.
- Broad network permissions.
- Disabled rules.
- Active connections.
- Expired connections.
- Security decisions by layer.

## 13. Security Policy Evaluation Examples

The following scenarios represent the expected behavior of the demonstrated configuration.

| Scenario | Protocol | Destination port | Expected result |
|---|---|---:|---|
| Internal HTTPS | TCP | 443 | ALLOW |
| External HTTP | TCP | 80 | DENY |
| Unauthorized SSH | TCP | 22 | DENY |
| Internal DNS | UDP | 53 | ALLOW |
| Unmatched traffic | TCP | 9000 | DENY |
| Established HTTPS return | TCP | Ephemeral | Stateful controls permit return traffic |

The actual result depends on all applicable security layers.

For example, allowing HTTPS through a firewall does not automatically permit the connection through a security group or network ACL.

Each control must independently authorize the traffic according to its own behavior.

## 14. Security Design Considerations

### Least privilege

Only necessary sources, destinations, protocols, and ports should be permitted.

An application that requires HTTPS should not automatically receive SSH or database access.

### Avoid broad permissions

Rules using `0.0.0.0/0` permit traffic from every IPv4 address within their matching conditions.

Such rules should be carefully reviewed, particularly for administrative and database services.

### Separate application tiers

Web, application, and database systems should use distinct network boundaries.

A web server should not receive unrestricted access to internal database networks.

### Connection tracking

Connection tracking should include:

- Connection expiration.
- Resource limits.
- TCP state validation.
- Connection cleanup.
- Protection against spoofed packets.
- Concurrency controls.

The demonstrations implement basic connection identification and reverse-flow matching. They do not implement a complete TCP state machine.

### Auditability

Security audit records should preserve:

- Timestamp.
- Source and destination addresses.
- Protocol.
- Security layer.
- Matched rule.
- Final action.
- Reason for the decision.

Production audit storage should have restricted access, retention controls, and integrity protection.

### Policy change management

Security rules should be validated before deployment.

Changes should be reviewed for:

- Unintended exposure.
- Conflicting priorities.
- Duplicate identifiers.
- Broad CIDR ranges.
- Unnecessary port access.
- Missing return-traffic permissions.
- Incorrect subnet associations.

## 15. Limitations and Production Boundaries

These implementations are educational policy engines, not production packet-processing firewalls.

They do not directly inspect or modify operating-system network interfaces.

The demonstrations have the following limitations:

| Area | Demonstrated behavior | Production requirement |
|---|---|---|
| IP matching | IPv4 CIDR evaluation | Full IPv4 and IPv6 policy support |
| Stateful tracking | Reverse-flow lookup | Full protocol state and timeout management |
| Firewall | Ordered policy matching | Kernel or network-device enforcement |
| Security groups | Inbound stateful filtering | Provider-specific attachment and rule semantics |
| Network ACL | Stateless directional evaluation | Explicit provider-compatible rule behavior |
| Traffic processing | Sequential evaluation | High-throughput concurrent packet processing |
| Logging | Local audit records | Centralized protected audit infrastructure |
| Policy storage | In-memory or relational storage | Versioning, approvals, backups, and deployment controls |

The PostgreSQL implementation is a policy simulation. Its functions and tables do not automatically synchronize rules with cloud networking services or operating-system firewalls.

The JavaScript implementation's IPv4 bitwise CIDR operations are not an IPv6 implementation.

The C++ and Java examples use IPv4 representations.

## 16. Execution Requirements

| Deliverable | Runtime | External dependencies |
|---|---|---|
| Python | Python 3.10+ | None |
| JavaScript | Node.js 18+ | None |
| C++17 | C++17 compiler | None |
| Java | Java 17 | None |
| PostgreSQL | PostgreSQL 14+ | None |

The five implementations are independently executable or deployable in their respective environments.

The PostgreSQL script creates a dedicated schema named `network_security`.

The Python and JavaScript examples generate local audit or policy files when executed.

## 17. Key Technical Distinctions

The four principal concepts must remain separate:

| Concept | Main question answered |
|---|---|
| Firewall | Should this packet pass the firewall policy? |
| Security Group | Is this resource authorized to receive the traffic? |
| Network ACL | Is this traffic permitted at the subnet boundary? |
| Traffic Filtering | Which packet attributes and rules determine the final decision? |

The central design principle is that network security is achieved through coordinated controls rather than reliance on a single firewall rule.

A well-designed network policy combines restricted access, explicit traffic direction, connection-state management, subnet isolation, validation, and auditable decisions.
