# Load Balancing: Layer 4, Layer 7, Health Checks, Traffic Distribution, and High Availability

## Topic Scope

Load balancing distributes client traffic across multiple backend servers so that one backend does not become a single point of overload or failure.

This implementation set treats four closely related concerns as distinct engineering mechanisms:

- **Layer 4 load balancing** makes decisions using transport-level information such as connections, IP addresses, ports, and protocols.
- **Layer 7 load balancing** understands application protocols such as HTTP and can route using hosts, paths, methods, headers, cookies, or other request attributes.
- **Health checks** determine whether a backend should remain eligible for new traffic.
- **Traffic distribution and high availability** determine how eligible capacity is used and how the service behaves when infrastructure fails.

The three implementations model these mechanisms from different technical perspectives. Python provides a broad executable simulation, JavaScript emphasizes asynchronous and event-driven behavior, and C++ presents a strongly typed infrastructure case study.

---

## Core Load-Balancing Model

A basic load-balancing system contains a client population, one or more load-balancer instances, a backend pool, health-monitoring logic, and an algorithm that selects a backend.

A simplified request path is:

    Client
       |
       v
    Load Balancer
       |
       +---- health eligibility
       |
       +---- routing algorithm
       |
       +---- backend selection
       |
       +---- Backend A
       +---- Backend B
       +---- Backend C

The important distinction is that a routing algorithm should normally select from the **eligible** backend set rather than from every configured backend.

If a backend is configured but unhealthy, routing traffic to it defeats the purpose of health monitoring. Likewise, a backend in a controlled draining state should normally stop receiving new traffic while existing work is allowed to finish.

A useful abstraction is:

    eligible_backends =
        configured_backends
        - unhealthy_backends
        - draining_backends

The exact behavior depends on the load-balancing product and configuration, but this model captures the central relationship demonstrated by the implementations.

---

## Layer 4 Load Balancing

Layer 4 operates around the transport layer, commonly TCP or UDP.

An L4 load balancer can reason about information such as:

- source IP address;
- source port;
- destination IP address;
- destination port;
- transport protocol;
- connection or flow identity.

It does not need to parse an HTTP request to decide where a TCP connection should go.

For example:

    Client 192.0.2.20:41000
             |
             | TCP
             v
       203.0.113.10:443
             |
       +-----+-----+
       |     |     |
       v     v     v
     API-A API-B API-C

A TCP connection selected for API-B should continue to API-B for the lifetime of that connection. The Python, JavaScript, and C++ implementations therefore maintain explicit connection mappings.

### L4 connection affinity

The Python `Layer4LoadBalancer` stores a `connection_table`. Once a connection identifier has been associated with a backend, subsequent lookups return that backend instead of running the selection algorithm again.

The JavaScript `Layer4Router` uses a `Map` for the same conceptual purpose.

The C++ case study separates this transport-level `connectionMap` from application-level HTTP sessions. This distinction matters because a transport connection and an application session are not necessarily the same thing.

### L4 strengths and limitations

L4 can be efficient because it does not need to understand the full application protocol. It is useful for TCP services, TLS pass-through designs, and protocols that an HTTP-aware proxy cannot or should not interpret.

The trade-off is reduced application awareness. An L4 device generally cannot make decisions such as:

    /static/* -> edge servers
    /admin/*  -> administrative servers
    /api/*    -> API servers

Those decisions require understanding application-layer information.

---

## Layer 7 Load Balancing

Layer 7 operates with application-level information.

For HTTP, an L7 load balancer can inspect:

- HTTP method;
- hostname;
- URL path;
- request headers;
- cookies;
- query parameters;
- application metadata, depending on implementation.

This allows traffic policies to reflect application architecture.

For example:

    GET /static/app.js
        -> edge backend

    GET /admin/users
        -> administrative backend

    GET /orders/123
        -> API backend

The JavaScript implementation makes this distinction particularly explicit in `Layer7Router.route()`.

The Python implementation similarly routes `/static/` requests toward edge-oriented nodes and `/admin` requests toward administrative nodes.

The C++ case study implements the same architectural distinction with typed `HttpRequest` and `Backend` structures.

L7 routing introduces additional processing and operational complexity because the load balancer must understand and often terminate or proxy an application protocol. TLS termination, HTTP parsing, header manipulation, cookie processing, request buffering, and connection reuse can all affect resource usage.

---

## L4 and L7 Are Not Interchangeable

The distinction is architectural rather than merely terminological.

| Property | Layer 4 | Layer 7 |
|---|---|---|
| Primary information | Transport flow | Application request |
| Typical protocols | TCP, UDP | HTTP, HTTPS and other application protocols |
| Understands URL path | No | Yes |
| Can route by HTTP host | No | Yes |
| Connection affinity | Natural | Possible, but separate from application session affinity |
| Application cookie awareness | No | Yes |
| Processing visibility | Lower | Higher |
| Typical routing granularity | Connection or flow | Request |
| Application-aware routing | Limited | Strong |

An L4 decision may assign an entire TCP flow to one backend. An L7 proxy can potentially make independent decisions for individual HTTP requests.

This difference becomes important with HTTP keep-alive, HTTP/2, HTTP/3, long-lived connections, and application session state.

---

## Traffic-Distribution Algorithms

The implementations demonstrate several algorithms because no single algorithm is appropriate for every workload.

### Round robin

Round robin rotates through eligible backends:

    A -> B -> C -> A -> B -> C

It is simple and predictable when backend capacities are similar.

The weakness is that equal request counts do not necessarily mean equal work. A request for a lightweight health endpoint may consume far fewer resources than a complex report-generation request.

### Weighted round robin

Weighted routing assigns a relative capacity weight to each backend.

For weights:

    A = 3
    B = 2
    C = 1

A simplified expanded sequence is:

    A A A B B C

The Python and C++ implementations use this model to show how a larger backend can receive a larger share of new traffic.

Weights should represent a meaningful capacity difference rather than being arbitrary numbers. Incorrect weights can concentrate traffic on an already constrained server.

### Least connections

Least-connections routing chooses the eligible backend with the smallest active connection count.

This is useful when connection duration varies substantially.

The C++ implementation uses active connection count as the primary comparison and backend name as a deterministic tie-breaker.

The limitation is that connection count is only a proxy for load. Ten idle connections may consume less capacity than one CPU-intensive request.

### Consistent-hash-style routing

Hashing a client or flow key can produce stable routing:

    hash(client_key) -> backend position

The Python and JavaScript implementations demonstrate this mechanism.

A production consistent-hashing implementation commonly uses a hash ring and virtual nodes. The simplified examples use deterministic hash selection to make the routing principle visible without introducing a large hashing infrastructure.

Hashing can support affinity while reducing arbitrary movement of clients when backend membership changes. It does not automatically solve overload, health failure, or session-state problems.

---

## Health Checks

Health checking determines whether a backend is suitable for new traffic.

A health check can operate at different levels.

A transport-level check might verify that a TCP connection can be established.

An application-level check might request an endpoint such as:

    GET /healthz

and validate the response.

A stronger application health endpoint can verify dependencies such as a database, cache, or message broker, but making every dependency part of the readiness decision can also make the service unnecessarily fragile.

The correct health signal should represent whether the backend is actually capable of serving the traffic that the load balancer intends to send.

### Failure thresholds

The implementations use consecutive-failure thresholds.

Suppose the failure threshold is two:

    probe 1: failure -> remain healthy
    probe 2: failure -> mark unhealthy

This avoids immediately removing a backend because of one transient network event.

The recovery process uses a separate recovery threshold:

    recovery probe 1: success -> remain unhealthy
    recovery probe 2: success -> return to healthy

The separation between failure and recovery thresholds reduces state flapping.

### Health states

The examples use three primary states:

    healthy
    unhealthy
    draining

These states have different meanings.

**Healthy** means the backend is eligible for new traffic.

**Unhealthy** means the backend should be excluded from normal new-traffic selection.

**Draining** means the backend is intentionally being removed from new traffic while existing connections or requests can finish.

Draining is not the same as a health failure. A backend can be perfectly healthy while being drained for deployment or maintenance.

---

## Graceful Draining

A production deployment should avoid abruptly terminating a backend that still owns active connections.

A simplified sequence is:

    healthy
       |
       v
    draining
       |
       +---- reject new traffic
       |
       +---- allow existing traffic to finish
       |
       v
    stopped

The Python `demonstrate_draining()` method explicitly sets active connections and reduces them to zero before returning the backend to service.

The JavaScript `demonstrateDraining()` method uses the same concept while relying on the `acceptingTraffic` property to exclude the backend from normal routing.

The C++ implementation treats draining as a distinct enum state and therefore makes the state transition explicit in the type model.

Real infrastructure usually adds a drain timeout. Without a timeout, one indefinitely open connection can prevent an instance from being safely removed.

---

## Session Affinity

Session affinity is an application-level concern and should not be confused with transport connection affinity.

A user might have:

    Browser
       |
       +---- TCP connection 1
       +---- TCP connection 2
       +---- TCP connection 3

while all requests carry:

    session_id = customer-42

An L7 load balancer can inspect that cookie and route the requests consistently to the same backend.

The examples maintain a `sessionMap` or `session_table` for this purpose.

The implementation also checks whether the sticky backend is still healthy. If it has failed, the affinity entry is discarded so that the request can move to another healthy backend.

This illustrates an important operational limitation of sticky sessions: affinity can reduce the effectiveness of traffic distribution and can make a particular backend more important than the others.

Applications designed for horizontal scaling generally benefit from externalized session state or stateless request processing.

---

## Failure During Request Processing

Health checks are not a guarantee that every subsequent request will succeed.

A backend can pass a health check and fail milliseconds later.

There are therefore at least two distinct failure windows:

    health check
         |
         v
    backend appears healthy
         |
         v
    request arrives
         |
         v
    backend fails

The JavaScript `RetryController` demonstrates one response to this problem.

Retries are not universally safe.

A failed `GET` can usually be retried because it is intended to be idempotent.

A failed `POST` may have reached the application even if the client did not receive the response. Automatically replaying it can create duplicate operations.

The JavaScript implementation therefore allows retry attempts for a set of idempotent methods and restricts non-idempotent operations to a single attempt.

Production retry policies also need backoff, retry budgets, timeout coordination, and protection against retry storms.

---

## High Availability

A load balancer itself must not become the single point of failure.

A basic high-availability arrangement can use:

    Client
       |
       v
    Stable service address
       |
       +--------+
       |        |
       v        v
    LB-A      LB-B
    active    standby
       |
       v
    Backend pool

If LB-A fails, traffic must be directed to LB-B.

The Python implementation models this with `HighAvailabilityLoadBalancer`.

The JavaScript implementation uses an event-emitting `HighAvailabilityPair`.

The C++ case study uses `HighAvailabilityPair` with an explicit generation or epoch value.

### Failover requirements

A useful high-availability design requires more than having two load-balancer processes.

Important mechanisms include:

- failure detection;
- a stable service address;
- replicated or shared configuration;
- controlled ownership of the active role;
- prevention of split-brain;
- synchronized health information where required;
- predictable recovery and failback behavior.

The stable address might be implemented using a virtual IP, DNS-based mechanisms, anycast, or infrastructure-specific service discovery.

The correct mechanism depends on the deployment environment.

### Split-brain

A particularly dangerous failure occurs when both load balancers believe they are active.

For example:

    LB-A -> believes it owns active role
    LB-B -> believes it owns active role

If both advertise or receive the same traffic, stateful behavior and network ownership can become inconsistent.

High-availability designs therefore need an explicit mechanism for determining ownership and preventing simultaneous active control.

---

## Availability Zones

High availability should also consider failure domains.

Suppose three backends exist:

    API-A -> zone-a
    API-B -> zone-b
    API-C -> zone-b

If zone-b fails, both API-B and API-C disappear simultaneously.

The C++ `AvailabilityPolicy` therefore evaluates both healthy backend count and the number of healthy zones.

This illustrates why simply counting servers can produce a misleading availability model. Three instances in the same failure domain do not provide the same resilience as instances distributed across independent zones.

---

## Python Implementation

The Python program is a self-contained simulation named `LoadBalancingLab`.

Its major components are intentionally separated by responsibility.

`Backend` stores operational state, weights, connection counts, request counts, latency measurements, zone information, and simulated failures.

`BackendPool` manages backend membership and the distinction between configured and eligible nodes.

`HealthChecker` implements active probes and threshold-based state transitions.

`Layer4LoadBalancer` demonstrates transport-level routing using round robin, weighted round robin, least connections, and consistent-hash-style selection.

`Layer7LoadBalancer` demonstrates HTTP-aware path routing and session affinity.

`HighAvailabilityLoadBalancer` models active/standby failover.

The program also contains assertions in `run_small_self_tests()` so that basic routing and health-state invariants are checked before the larger simulation executes.

The executable behavior includes health failure and recovery, connection accounting, path-aware HTTP routing, weighted traffic, consistent hashing, draining, upstream failure, high availability, and invalid configuration handling.

Run it with:

    python load_balancing.py

No third-party package is required.

---

## JavaScript Implementation

The JavaScript implementation is designed around asynchronous and event-driven behavior.

`AsyncHealthChecker` extends `EventEmitter` and performs asynchronous probes with a timeout race. This makes the health-monitoring mechanism closer to the event-driven execution model common in Node.js services.

`Layer4Router` uses `Map` for connection ownership and supports several transport-oriented algorithms.

`Layer7Router` emits routing events and stores application session affinity independently from L4 connection mappings.

`RetryController` demonstrates an important application-level failure decision: retrying an idempotent operation is materially different from replaying a potentially non-idempotent mutation.

`TrafficPolicy` evaluates the current backend pool against minimum capacity and zone-diversity requirements.

`HighAvailabilityPair` models active/standby state transitions through events.

Run it with:

    node load_balancing.js

The file uses only Node.js built-in modules.

---

## C++ Case Study

The C++ program models an infrastructure environment in which an HTTP service is deployed across availability zones.

The central `Backend` structure contains:

- network address and port;
- traffic weight;
- availability zone;
- service role;
- health state;
- active connections;
- request counts;
- failure counts;
- latency measurements.

`BackendPool` enforces configuration invariants and exposes healthy backends without exposing unhealthy or draining nodes to normal selection.

`HealthMonitor` implements consecutive failure and recovery thresholds.

`LoadBalancer` combines two distinct routing perspectives. Its L4 methods maintain a connection table, while its L7 methods use HTTP path and session information.

The L7 scenario separates administrative requests and static assets from normal API traffic.

The C++ implementation also demonstrates least-connections routing and weighted distribution, followed by graceful draining.

`AvailabilityPolicy` evaluates the number of healthy backends and the number of healthy zones. This turns high availability into an explicit policy rather than treating it as an informal property.

`HighAvailabilityPair` models active/standby load-balancer ownership and increments an epoch whenever a failover occurs.

Compile with:

    g++ -std=c++17 -O2 -Wall -Wextra -pedantic load_balancing.cpp -o load_balancing

Run with:

    ./load_balancing

On Windows with MinGW, the resulting executable can be run as:

    load_balancing.exe

---

## Routing Decision and Health Decision Are Different

A useful design distinction is:

    Health subsystem
          |
          v
    Which backends are eligible?
          |
          v
    Routing subsystem
          |
          v
    Which eligible backend receives traffic?

The health subsystem should not choose traffic distribution.

The routing algorithm should not decide that an unhealthy backend is healthy merely because its algorithm would otherwise select it.

This separation is visible throughout the implementations.

For example, `healthyBackends()` filters the candidate set first. Only after that filtering does the routing algorithm select a target.

This architecture makes both components easier to reason about and test.

---

## Edge Cases

### No healthy backends

If every backend is unhealthy or draining, normal traffic cannot be safely routed.

The implementations raise or report a routing failure rather than silently selecting an unavailable backend.

A production service must decide what the client receives in this situation, such as a gateway error, a controlled overload response, or another service-specific fallback.

### One healthy backend

A load balancer can continue operating with one healthy backend, but capacity and failure tolerance are reduced.

A health check can therefore report that traffic is technically routable while an availability policy may still reject the configuration because redundancy requirements are no longer satisfied.

### Backend failure after selection

A backend can fail after being selected. Health checks cannot eliminate this race completely.

Request timeouts, connection failures, circuit breakers, and carefully designed retries are used to handle this class of failure.

### Draining backend

A draining backend may still have active connections but must not receive new traffic.

Treating draining as equivalent to unhealthy loses the operational distinction between planned maintenance and unexpected failure.

### Unequal backend capacity

Equal round-robin distribution can overload a smaller backend when servers have different capacities.

Weighted algorithms can account for known capacity differences, although weights become stale if actual resource capacity changes.

### Long-lived connections

Least-connections routing can behave differently when connections have very different lifetimes.

Long-lived WebSocket or streaming connections can occupy a backend for much longer than ordinary HTTP requests.

### Sticky-session failure

If the backend holding a session fails, a strict affinity implementation may cause requests to fail repeatedly.

The examples explicitly allow a failed affinity target to be discarded so the request can be routed to another healthy backend.

---

## Performance Considerations

Load balancing adds work to the request path.

An L4 device can often make a routing decision without parsing the application payload.

An L7 proxy generally performs more processing because it must understand application-layer information. TLS termination can add cryptographic CPU work, and HTTP parsing adds memory and CPU overhead.

The selection algorithms also have different computational characteristics.

A simple round-robin decision is effectively constant time for an indexed backend collection.

Least-connections selection requires examining eligible backends and is therefore proportional to the number of candidates in the straightforward implementation.

The simplified weighted round-robin implementation expands weights into a temporary selection sequence. Production implementations normally use more efficient weighted scheduling algorithms when the number or magnitude of weights becomes large.

The simplified consistent-hash examples use direct hashing rather than a full virtual-node ring. A production hash ring can reduce remapping during membership changes but requires additional data structures and careful handling of node weights.

Metrics collection can also become expensive if every request creates high-cardinality labels. Operational identifiers such as raw request IDs should generally not become unbounded metric dimensions.

---

## Health-Check Design Considerations

A health endpoint should answer the question:

> Should this backend receive the traffic represented by this load-balancer pool?

A process-level health check such as "the process exists" may be too weak.

An overly deep health check that requires every dependency to be available can also be too strict.

A useful design separates concepts such as:

- liveness: the process is alive;
- readiness: the process is prepared to receive traffic;
- dependency health: a required external service is available;
- overload state: the process is alive but should receive less or no new traffic.

The load-balancer integration generally benefits from readiness-style semantics because the relevant decision concerns new traffic.

Health-check intervals, timeouts, failure thresholds, recovery thresholds, and probe concurrency should be chosen with care. Aggressive probing can create unnecessary load, while slow detection can allow a failing backend to receive traffic for too long.

---

## Security Considerations

Load balancers sit on an important trust boundary and therefore require security controls.

For L7 HTTP systems, request parsing must reject malformed or ambiguous input consistently. Differences between a front-end proxy and a backend HTTP parser can create request-smuggling vulnerabilities if they disagree about request boundaries.

TLS configuration should use appropriate protocol versions and certificate validation. When TLS is terminated at the load balancer, the internal connection to the backend must also be protected when the network is not fully trusted.

Client IP forwarding requires careful treatment. Headers such as `X-Forwarded-For` should not automatically be trusted when they originate directly from untrusted clients.

Health-check endpoints should expose only the information needed for health decisions. Detailed diagnostic output can reveal infrastructure details unnecessarily.

Administrative routes should not rely only on the fact that the request reached an administrative backend. Authentication and authorization remain application security responsibilities.

Load balancers should also enforce appropriate connection, request, header, and body-size limits to reduce resource-exhaustion risks.

---

## Debugging and Observability

A useful load-balancing system should make routing decisions observable.

The examples record information such as:

- selected backend;
- active connections;
- request count;
- failed request count;
- average latency;
- health state;
- failover generation;
- routing metrics.

A production system commonly needs metrics for:

    requests per second
    active connections
    backend response latency
    upstream error rate
    health-check failures
    backend state changes
    connection establishment failures
    TLS handshake failures
    retry count
    queue depth
    dropped or rejected requests
    failover events

Logs should make it possible to answer questions such as:

    Which backend received this request?

    Was the backend healthy when selected?

    Was the request retried?

    Did the backend fail before or after receiving the request?

    Was the target draining?

    Which load-balancer instance was active?

Distributed tracing can connect the load-balancer request span to the backend service span, making upstream latency and failure location easier to identify.

---

## Common Design Mistakes

### Treating health as binary and permanent

A backend can transition repeatedly between healthy and unhealthy states. Thresholds and recovery logic are needed to avoid reacting to every transient failure.

### Routing to draining nodes

A deployment operation can unintentionally continue sending new requests to a node that should be removed from service.

Draining must therefore be represented explicitly rather than inferred from a generic operational comment.

### Confusing connection affinity with session affinity

A TCP connection belongs to a transport flow. An application session can span many transport connections.

The implementations maintain separate maps to demonstrate this distinction.

### Retrying every failed request

A retry is not automatically safe. Replaying a mutation can produce duplicate side effects.

Retry behavior should account for HTTP method semantics, idempotency keys, timeouts, and application behavior.

### Assuming two load balancers automatically provide high availability

Two independent instances can still fail together, lose configuration synchronization, or both believe they are active.

Failover ownership and state coordination are essential.

### Counting servers instead of failure domains

Several servers in one availability zone do not provide the same resilience as servers distributed across independent zones.

High-availability policy should account for meaningful failure domains.

### Using equal weights for unequal hardware

Round robin assumes approximately comparable capacity. If one backend has substantially different CPU, memory, network, or application capacity, an equal distribution may be inappropriate.

---

## Production Architecture Considerations

A larger deployment can separate responsibilities into several layers:

    Internet / Client Network
              |
              v
       Edge / L4 Load Balancer
              |
              v
       L7 HTTP Proxy Tier
              |
       +------+------+
       |      |      |
       v      v      v
      API    API    API
       |      |      |
       +------+------+
              |
       Shared application
          dependencies

The exact architecture depends on whether TLS should terminate at the edge, whether L4 pass-through is required, whether an L7 proxy is needed, and whether services are independently discoverable.

Backend registration should also be treated as dynamic infrastructure state. Instances can be created, removed, upgraded, or moved between zones.

Configuration changes should therefore be validated before being applied. An invalid backend address, duplicate backend identity, impossible weight, missing health endpoint, or empty service pool should not silently enter production.

---

## Relationship Between the Four Core Areas

The mechanisms fit together in a pipeline rather than replacing one another.

**Layer 4 load balancing** determines where transport flows go.

**Layer 7 load balancing** can make application-aware routing decisions for protocols it understands.

**Health checks** determine which backends are eligible to receive new work.

**Traffic-distribution algorithms** decide how eligible capacity is shared.

**High availability** protects the load-balancing layer itself and considers whether sufficient backend capacity remains across failure domains.

A simplified relationship is:

    Health checks
          |
          v
    Eligible backends
          |
          +----------------------+
          |                      |
          v                      v
    L4 flow routing        L7 request routing
          |                      |
          +----------+-----------+
                     |
                     v
              Backend service

High availability surrounds this routing path by ensuring that the load-balancing control point and the backend fleet can continue serving traffic when individual infrastructure components fail.

The implementations use different languages and architectural styles, but they preserve this separation of responsibilities so that transport routing, application routing, health state, traffic distribution, and availability policy remain distinguishable engineering mechanisms.
