# Data Center Physical Infrastructure

This learning artifact models the physical systems that make a data center operational: racks, servers, electrical distribution, cooling, UPS systems, generators, redundancy, environmental conditions, and physical failure scenarios.

The implementations deliberately distinguish physical capacity from operational state. A rack can have free rack units but insufficient electrical capacity. A facility can have enough total cooling capacity but lose its N+1 property when a cooling unit fails. A server can consume modest power while still becoming unavailable if it has only one electrical connection.

The central relationship is:

**IT equipment → electrical consumption → heat generation → cooling requirement**

That relationship is surrounded by physical resilience mechanisms:

**utility power → UPS → distribution → rack feeds → server power supplies**

and, for longer interruptions:

**generator → electrical distribution → UPS and facility loads**

The six deliverables use different technical perspectives rather than reproducing one implementation in six languages.

---

## Physical infrastructure model

A data center is a physical system with several tightly coupled capacity dimensions.

### Racks

A rack provides mechanical space measured in rack units, commonly written as `U`. The reference implementations use 42U racks.

Rack capacity is not simply a matter of available physical space. An installation decision also has to consider:

- electrical capacity on the rack feeds;
- power-feed redundancy;
- server dimensions;
- thermal density;
- cable routing and service access;
- equipment maintenance requirements;
- future capacity reservations.

A rack with 10U free space can still be unsuitable for a new server if its remaining electrical or cooling budget is insufficient.

The Python, C++, JavaScript, and Java implementations therefore maintain rack-unit usage independently from electrical load.

### Servers

Servers are modeled with:

- an asset identifier;
- a hostname or descriptive name;
- rack-unit consumption;
- electrical consumption in watts;
- power redundancy characteristics;
- an operational state.

Electrical consumption is converted from watts to kilowatts for facility calculations.

A dual-power server has two modeled electrical paths. A single-corded device has only one. This distinction becomes important during a power-feed failure.

### Power feeds

The examples use A and B rack power feeds.

A dual-corded server divides its modeled load between the two feeds. If one feed fails, the server remains available through the surviving path.

A single-corded server does not receive this protection. When its only modeled feed fails, the equipment is marked offline.

This is a simplified operational model. Real electrical engineering requires consideration of circuit topology, breaker coordination, phase balancing, voltage, current, power factor, distribution equipment, automatic transfer systems, and the actual behavior of server power supplies.

---

## Cooling and heat generation

Electrical power consumed by IT equipment is ultimately released as heat inside the facility.

The implementations therefore treat the active IT electrical load as the modeled thermal load:

`heat load in kW ≈ IT electrical load in kW`

This is intentionally simplified. Real thermal engineering also considers airflow patterns, environmental conditions, equipment efficiency, containment strategy, chilled-water conditions, economization, liquid cooling, and other facility characteristics.

The Python implementation exposes this relationship through `total_heat_kw()` and cooling-capacity validation.

The JavaScript implementation calculates the same relationship through `totalITLoadKw` and `coolingCapacityKw`.

The C++ and Java implementations use the same physical principle while emphasizing strongly typed infrastructure models.

The SQL implementation computes the thermal load from the relational server inventory rather than storing an independent heat value that could become inconsistent with server power consumption.

---

## Cooling redundancy

Cooling capacity is not equivalent to cooling resilience.

Suppose a facility has three cooling units, each rated at 8 kW, and the IT heat load is 10 kW.

Total installed capacity is:

`8 + 8 + 8 = 24 kW`

If one unit fails:

`8 + 8 = 16 kW`

The facility still has enough capacity to remove 10 kW of heat. This is an example of N+1 behavior for the modeled load.

The important calculation is therefore not just:

`total cooling capacity >= current heat load`

but also:

`capacity after loss of one required unit >= current heat load`

The implementations explicitly test this condition.

The SQL implementation uses a window calculation to identify the largest online cooling unit and evaluates remaining capacity after its hypothetical loss.

---

## Environmental operating limits

Cooling infrastructure ultimately supports an environmental operating range.

The examples use:

- a modeled normal ambient temperature of 22°C;
- a modeled upper limit of 27°C.

These values are educational simulation parameters rather than universal engineering specifications.

The code demonstrates the operational consequence of a temperature excursion. A facility can have installed cooling capacity but still raise an environmental alarm when measured temperature exceeds the configured threshold.

This distinction matters because capacity calculations describe available infrastructure while environmental monitoring describes actual operating conditions.

---

## Power resilience

A resilient data center does not rely on a single electrical component.

The physical power chain can contain several layers:

- utility service;
- switchgear;
- generators;
- UPS systems;
- distribution equipment;
- rack-level power distribution;
- server power supplies.

The Python model represents UPS and generator capacity separately from rack feeds.

The Java, C++, and JavaScript implementations concentrate on rack-level survivability while retaining facility-level power concepts.

The SQL schema stores UPS and generator capacity as separate entities because their operational roles are different.

A generator provides longer-duration power continuity during a utility interruption. A UPS provides short-duration conditioned power and bridges the time required for generator systems to start and stabilize. The exact architecture depends on facility engineering design.

---

## Redundancy models

The term redundancy describes how much infrastructure remains available after component failure.

### N

An N design provides exactly the capacity required for the intended load.

If the required cooling capacity is 16 kW and installed capacity is exactly 16 kW, losing one cooling unit can cause insufficient capacity.

N provides capacity but no component-failure margin.

### N+1

N+1 adds one additional capacity unit beyond the requirement.

For a 10 kW modeled load, three 5 kW cooling units provide 15 kW installed capacity. If one fails, 10 kW remains.

The important property is survivability after one relevant component failure, not merely the amount of installed capacity.

### 2N

2N generally means two independent systems, each capable of supporting the required load.

The rack power examples use a simplified form of independent A/B electrical paths for dual-corded servers. A complete 2N facility design requires much more than two database rows or two labels. The physical electrical architecture must actually provide independence.

---

## Python implementation

The Python program is a self-contained infrastructure simulator.

Its domain model contains:

- `Server` for IT equipment characteristics;
- `PowerSystem` for capacity and electrical load;
- `CoolingSystem` for thermal-removal capacity;
- `Rack` for mechanical space and rack-level power paths;
- `DataCenter` for facility-level aggregation and resilience checks.

The `Rack.install_server()` method performs two different placement calculations.

For a dual-powered server, half of the modeled electrical load is placed on each rack feed. This lets the simulator test what happens when one feed disappears.

For a single-powered server, the entire modeled load is attached to one feed. Such a server can become unavailable during a feed failure.

The Python implementation also validates rack-unit capacity. An attempted 50U server cannot be placed in a 42U rack, producing a controlled validation failure rather than silently creating an impossible physical configuration.

### Cooling evaluation

`validate_cooling()` compares heat load with available cooling capacity and also checks the modeled ambient temperature.

`validate_n_plus_one_cooling()` removes the largest online cooling unit from the capacity calculation and checks whether the remaining units can still handle the IT heat load.

This is more meaningful than checking only total installed capacity.

### Failure simulation

`demonstrate_power_failure()` disables a rack feed and reports which single-corded servers become unavailable.

Dual-powered servers remain online because their second electrical path is still available.

`demonstrate_cooling_failure()` disables a cooling unit and evaluates both immediate cooling sufficiency and N+1 status.

### Capacity planning

The Python program also projects a 25% IT-load increase. This demonstrates why capacity planning must consider future growth rather than only the present load.

The projection is deliberately simple. Real facility planning would include electrical diversity, equipment utilization profiles, cooling efficiency, infrastructure losses, construction constraints, and commissioning margins.

---

## JavaScript implementation

The JavaScript implementation takes an event-driven perspective.

`DataCenter` extends Node.js `EventEmitter`. Infrastructure failures are emitted as events rather than handled exclusively through a synchronous sequence of method calls.

This reflects an important property of physical infrastructure monitoring systems: environmental sensors, electrical monitoring equipment, building-management systems, and facility alerts produce events asynchronously.

The implementation defines event types for:

- power-feed failure;
- cooling failure;
- temperature alerts.

The `fail()` method emits an infrastructure failure event. Registered handlers then determine the operational response.

### Rack behavior

The JavaScript `Rack` class manages rack-unit capacity and feed-level electrical load.

It also rejects installation of dual-powered equipment when one of the required feeds is already offline.

This models a practical operational constraint: installation procedures can have stricter requirements than normal steady-state operation.

### Asynchronous monitoring

`runMonitoringCycle()` uses a Promise-based delay to represent asynchronous monitoring.

No third-party package is required.

The monitoring cycle reads current heat load, cooling capacity, cooling margin, and temperature status and produces an operational decision.

This is intentionally different from the Python implementation. Python focuses on an object-oriented physical simulation, while JavaScript emphasizes event-driven facility behavior.

---

## C++ case study

The C++ program models an enterprise data center as a strongly typed physical infrastructure system.

Its principal domain types are:

- `Server`;
- `PowerPath`;
- `Rack`;
- `CoolingUnit`;
- `DataCenter`.

The `Rack` class encapsulates physical capacity and electrical-feed state.

A server cannot be installed if its rack-unit requirement exceeds available rack space.

A dual-powered server requires capacity on both A and B feeds.

The model treats a feed failure as a physical event that can affect only equipment lacking electrical redundancy.

### Algorithmic behavior

Rack occupancy is calculated by traversing installed equipment and summing rack units for equipment that remains online.

Electrical load is calculated independently from physical rack occupancy.

This distinction prevents an important modeling error: physical capacity and electrical capacity are different resources.

N+1 cooling is calculated by collecting the capacities of online cooling units, identifying the largest unit, subtracting it from total capacity, and comparing the remaining capacity against the active IT load.

For `n` cooling units, this is an O(n) calculation.

### Failure handling

The C++ implementation uses exceptions for invalid infrastructure operations.

Examples include:

- unknown rack identifiers;
- invalid rack dimensions;
- insufficient rack space;
- insufficient electrical capacity;
- unknown cooling units;
- invalid environmental temperature input.

The main program catches `std::exception`, providing a single boundary for operational errors.

### Engineering trade-off

The model deliberately does not pretend to be an electrical engineering simulator.

It does not calculate:

- voltage drop;
- breaker coordination;
- short-circuit current;
- phase imbalance;
- harmonics;
- power factor;
- generator transient response;
- chilled-water hydraulics.

Those calculations require engineering data that cannot be inferred from a simple rack inventory.

The purpose of the case study is to model physical capacity and resilience decisions without creating false precision.

---

## Java implementation

The Java implementation emphasizes enterprise domain modeling.

`ServerSpec` is a record representing immutable equipment characteristics.

This is appropriate because a server's physical specification should not be changed accidentally as part of an operational state transition.

`InstalledServer` separates immutable equipment characteristics from mutable operating state.

A server can be:

- `ONLINE`;
- `OFFLINE`;
- `MAINTENANCE`.

This prevents the physical specification from being mixed with its current operational condition.

### Explicit state management

`InstalledServer.changeState()` applies a state-transition rule.

The implementation rejects a transition directly from `OFFLINE` to `MAINTENANCE`.

The rule is intentionally explicit because physical operations often have state-dependent procedures. An offline server may need to be restored or formally decommissioned before being placed into a maintenance workflow.

The exact state machine for a production facility would normally be more detailed.

### Infrastructure evaluation service

`InfrastructureEvaluationService` separates facility evaluation from facility storage.

Its `Evaluation` record captures:

- cooling sufficiency;
- N+1 cooling status;
- temperature safety;
- current IT load;
- current cooling capacity.

This allows the application to evaluate infrastructure state without putting every reporting rule inside the physical asset classes.

### Java-specific design

The Java implementation uses:

- records for immutable configuration and evaluation results;
- enums for constrained physical states;
- collections for racks and cooling assets;
- streams for aggregate capacity calculations;
- explicit exceptions for invalid operations;
- domain classes for operational state.

This gives the model a structure appropriate for a larger enterprise facilities-management application.

---

## SQL relational model

The PostgreSQL script models physical infrastructure as relational data.

The central hierarchy is:

`facility → row_location → rack → server`

Electrical relationships are represented separately:

`rack → power_feed → server_power_connection → server`

Cooling is modeled at the facility level:

`facility → cooling_unit`

Power resilience assets are also separate:

`facility → ups_system`

and:

`facility → generator`

Operational failures are captured by:

`facility → infrastructure_incident`

This separation is important because a rack, a power feed, a cooling unit, and a generator have different lifecycles and constraints.

---

## Database constraints

The SQL schema uses constraints to prevent physically nonsensical records.

Examples include:

- rack capacity must be positive;
- server rack-unit consumption must be positive;
- server electrical consumption must be positive;
- power-feed capacity must be positive;
- reserved electrical capacity must remain below total capacity;
- cooling capacity must be positive;
- duplicate rack codes are rejected within a row;
- duplicate server asset tags are rejected;
- power-feed sides are unique per rack.

The database therefore provides a second line of defense beyond application validation.

---

## Electrical connection modeling

`server_power_connection` is intentionally separate from `server`.

A server may have one or two physical power connections.

A dual-powered server should have two independent connections. The SQL audit query identifies cases where the recorded number of connections does not match the declared redundancy model.

This is an example of a relational integrity problem that is different from a simple server inventory problem.

The server record says what the equipment requires.

The connection table says how it is physically connected.

Those are related but distinct facts.

---

## SQL cooling calculations

The SQL script calculates IT heat load from online servers.

It does not store a duplicate heat-load column on every server because such duplication could become inconsistent with the authoritative electrical-consumption value.

The cooling query aggregates online cooling-unit capacity and compares it with online IT load.

The N+1 query goes further by identifying the largest active cooling unit and evaluating capacity after its loss.

This makes the database useful for operational reporting rather than merely storing an equipment list.

---

## Transactions and physical incidents

The SQL script uses transactions when simulating infrastructure failures.

The power-feed failure transaction:

- marks the A feed offline;
- records an infrastructure incident;
- marks affected single-corded equipment offline.

These operations are committed together.

If a database error occurs before commit, the transaction can be rolled back rather than leaving the infrastructure inventory in a partially updated state.

The cooling failure transaction similarly changes the cooling-unit state and records an incident.

This matters because an operational event should not produce contradictory inventory records such as a failed component without an incident record or an incident record claiming a failure that the asset inventory does not show.

---

## Physical infrastructure failure modes

### Rack capacity failure

A server may physically exceed the available rack units.

This is detected during placement rather than after installation.

A physical rack cannot accept more equipment simply because the database has no row-level restriction on the number of servers. Rack occupancy must be derived from the dimensions of installed equipment.

### Electrical capacity failure

A rack may have physical space but insufficient electrical capacity.

This is why rack-unit planning and power planning are separate calculations.

A high-density server can fit mechanically while exceeding a circuit or PDU capacity.

### Single power-path failure

A single-corded device can become unavailable after loss of its only feed.

A dual-corded device can remain online if its two connections truly terminate on independent power paths.

The model demonstrates the operational difference without claiming that two connectors alone establish full facility-level independence.

### Cooling-unit failure

A cooling-unit failure may be harmless, manageable, or critical depending on remaining capacity.

The correct evaluation is based on:

`remaining cooling capacity >= active heat load`

not simply:

`one cooling unit failed`

### Temperature excursion

Measured environmental conditions provide another operational signal.

A facility may have nominal cooling capacity while actual temperature rises because of airflow problems, control faults, sensor conditions, or local thermal concentration.

This is why physical monitoring cannot be reduced to static asset inventories.

---

## Capacity planning

A data center has multiple independent capacity dimensions.

| Capacity dimension | What it measures | Typical failure when underestimated |
| --- | --- | --- |
| Rack units | Physical mounting space | Equipment cannot be installed |
| Electrical capacity | Available power | Circuit, PDU, UPS, or distribution overload |
| Cooling capacity | Heat-removal capability | Temperature rise |
| UPS capacity | Short-duration conditioned power | Insufficient ride-through capacity |
| Generator capacity | Longer-duration backup power | Backup system cannot support required load |
| Power-path redundancy | Ability to survive feed failure | Single component failure causes equipment outage |

Capacity planning must evaluate these dimensions together.

Adding racks without increasing electrical capacity creates a power bottleneck.

Adding electrical capacity without adequate cooling creates a thermal bottleneck.

Adding cooling without adequate generator capacity can leave environmental infrastructure unavailable during a prolonged power event.

---

## PUE and facility efficiency

Power Usage Effectiveness is commonly expressed as:

`PUE = Total Facility Power / IT Equipment Power`

A PUE of 1.0 would mean every unit of facility power is consumed directly by IT equipment.

Real facilities have non-IT loads such as:

- cooling;
- pumps;
- fans;
- lighting;
- power-distribution losses;
- control systems.

The Python simulator provides a deliberately simplified PUE calculation.

It should not be interpreted as an engineering-grade facility efficiency measurement because the model does not contain complete facility power metering.

For actual PUE measurement, facility-level and IT-level energy measurements need defined measurement boundaries and appropriate instrumentation.

---

## Redundancy versus capacity

Capacity and redundancy should not be treated as synonyms.

A facility can have a large amount of capacity but poor fault tolerance.

For example, two cooling units rated at 20 kW each provide 40 kW of total capacity. If the active IT heat load is 15 kW, the total capacity appears generous.

If one unit fails, 20 kW remains, so the system is still resilient for a 15 kW load.

By contrast, two 10 kW units supporting a 15 kW load provide 20 kW total but only 10 kW after one failure. The facility has capacity before failure but not N+1 resilience.

The failure-state calculation is therefore central to redundancy analysis.

---

## Physical independence

Redundancy labels can be misleading if supposedly independent components share a physical dependency.

Two power feeds may still share:

- the same upstream switchgear;
- the same distribution path;
- the same generator;
- the same cable route;
- the same maintenance dependency.

Two cooling systems may share a common chilled-water source.

Two generators may share fuel infrastructure.

Two UPS systems may share a common upstream failure point.

The code examples simplify these relationships so that the core capacity and failure concepts remain understandable. A production design must model common-mode failures separately.

---

## Security and physical access

Physical infrastructure also has a security boundary.

Relevant controls include:

- restricted data-hall access;
- controlled rack access;
- visitor logging;
- equipment asset identification;
- camera coverage;
- environmental monitoring;
- alarm escalation;
- separation of facilities and IT operational responsibilities;
- controlled maintenance procedures.

The examples focus primarily on capacity and resilience rather than access-control implementation.

Physical security is nevertheless important because unauthorized access to power, networking, or server hardware can bypass software security controls.

---

## Monitoring and operational response

A useful facility monitoring system should distinguish between measurement, state, and response.

A sensor may report a temperature.

The monitoring system converts that measurement into a state such as normal, warning, or critical.

An operational workflow then determines the response.

The JavaScript implementation demonstrates this event-oriented approach through `EventEmitter`.

The relational model demonstrates another part of the workflow by recording incidents separately from physical component inventory.

This separation allows historical analysis of failures without destroying the current state of the infrastructure asset.

---

## Important modeling limitations

These implementations are educational physical-infrastructure models rather than facility-engineering design tools.

They simplify several areas.

Electrical calculations do not include voltage, current, phase balancing, power factor, breaker curves, short-circuit behavior, harmonic distortion, or detailed transfer-switch behavior.

Cooling calculations do not model airflow, containment, chilled-water systems, refrigerant circuits, humidity, supply/return temperatures, or localized rack hotspots.

Generator calculations do not model fuel consumption, start sequence, transient load response, or generator synchronization.

Rack placement does not model cable management, floor loading, seismic requirements, service clearances, or equipment-specific mounting restrictions.

These omissions are intentional. Adding unsupported engineering assumptions would create a false impression of physical accuracy.

---

## Common infrastructure mistakes

### Treating rack space as the only capacity metric

A rack can have empty U-space while its power distribution is already near its operating limit.

Mechanical capacity, electrical capacity, and thermal capacity must be checked together.

### Counting total cooling capacity without checking failure capacity

Installed cooling capacity does not demonstrate N+1 resilience.

The relevant question is whether remaining cooling capacity can handle the required load after the defined failure.

### Assuming dual power supplies automatically create 2N resilience

Two server power supplies provide equipment-level electrical redundancy only if their upstream paths are actually independent.

The independence of the complete electrical path matters.

### Ignoring single-corded infrastructure

Management devices, appliances, monitoring equipment, and older systems may have only one power connection.

A facility can therefore have redundant rack feeds while still containing individual single-path failure points.

### Storing derived physical values as uncontrolled duplicate data

The SQL model derives IT heat load from server electrical consumption.

Storing both values independently would allow them to drift apart.

Derived values should normally be calculated from authoritative measurements or maintained through controlled mechanisms.

---

## Production-oriented considerations

A real physical infrastructure management platform would normally need stronger asset identity, historical telemetry, maintenance records, calibration information, facility diagrams, electrical topology, environmental sensor data, alarm policies, role-based access, audit history, and change-management controls.

Capacity should also be tracked over time rather than only as a current snapshot.

Historical trends can reveal:

- increasing rack density;
- shrinking electrical margin;
- recurring thermal excursions;
- cooling-unit utilization;
- UPS loading;
- generator runtime;
- failure frequency.

The data model in the SQL implementation provides a foundation for such operational records while keeping physical equipment, capacity, and incidents distinct.

---

## Relationship between the six implementations

| Deliverable | Primary technical perspective |
| --- | --- |
| Python | Object-oriented physical infrastructure simulator and capacity analysis |
| JavaScript | Event-driven facility monitoring and failure processing |
| C++ | Strongly typed infrastructure capacity and failure case study |
| Java | Enterprise domain model with explicit state and evaluation services |
| SQL | Relational representation, integrity constraints, operational queries, and transactions |
| README | Technical interpretation of the physical infrastructure models |

The implementations intentionally reach the same physical conclusions through different mechanisms.

A rack has mechanical capacity.

A server has electrical demand.

Electrical demand creates thermal load.

Cooling must remove that thermal load.

Power redundancy determines which equipment survives an electrical-path failure.

Cooling redundancy determines whether thermal capacity survives a cooling-unit failure.

UPS and generator capacity support continuity at the facility power layer.

These relationships form the core physical-infrastructure model demonstrated across the deliverables.
