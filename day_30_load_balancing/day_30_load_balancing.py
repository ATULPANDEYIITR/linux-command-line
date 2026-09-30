#!/usr/bin/env python3
"""
Load Balancing: Layer 4, Layer 7, health checks, traffic distribution,
and high availability.

This self-contained program models a small production-style load-balancing
environment without requiring external packages.

It demonstrates:

- Layer 4 load balancing based on transport-level connection metadata.
- Layer 7 load balancing based on HTTP request attributes.
- Active health checks and recovery.
- Round-robin, weighted, least-connections, and consistent-hash routing.
- Connection accounting and request routing.
- Session affinity at the application layer.
- Backend draining during deployment.
- High availability with an active/standby load-balancer pair.
- Failure detection and recovery.
- Metrics useful for debugging and operations.

The simulation intentionally models load-balancer decisions rather than
opening real network sockets. That keeps the example deterministic and
executable on a standard Python installation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import random
import time
from collections import Counter, defaultdict, deque
from typing import Callable, Iterable, Optional


class Layer(str, Enum):
    L4 = "Layer 4"
    L7 = "Layer 7"


class BackendState(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"


class Algorithm(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    CONSISTENT_HASH = "consistent_hash"


@dataclass
class L4Connection:
    """
    Transport-level connection metadata.

    An L4 load balancer normally works with information such as source and
    destination IP addresses, ports, and transport protocol. It does not need
    to understand an HTTP path such as /api/orders.
    """

    connection_id: str
    source_ip: str
    source_port: int
    destination_ip: str
    destination_port: int
    protocol: str = "TCP"


@dataclass
class HttpRequest:
    """
    Application-level request metadata.

    L7 routing can inspect HTTP-specific information such as host, method,
    path, headers, and cookies. The load balancer can therefore implement
    content-aware routing rules.
    """

    request_id: str
    client_ip: str
    host: str
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)


@dataclass
class Backend:
    name: str
    ip: str
    port: int
    weight: int = 1
    state: BackendState = BackendState.HEALTHY
    active_connections: int = 0
    requests_served: int = 0
    total_latency_ms: float = 0.0
    region: str = "primary"
    version: str = "v1"
    fail_health_checks: bool = False
    failure_probability: float = 0.0

    @property
    def average_latency_ms(self) -> float:
        if self.requests_served == 0:
            return 0.0
        return self.total_latency_ms / self.requests_served

    @property
    def accepting_new_traffic(self) -> bool:
        return self.state == BackendState.HEALTHY


@dataclass
class HealthCheckResult:
    backend: str
    healthy: bool
    latency_ms: float
    reason: str


@dataclass
class HealthChecker:
    interval_seconds: float = 5.0
    timeout_seconds: float = 2.0
    failure_threshold: int = 2
    recovery_threshold: int = 2
    consecutive_failures: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    consecutive_successes: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def probe(self, backend: Backend) -> HealthCheckResult:
        """
        Simulate an active TCP/HTTP-style health probe.

        A real system might perform:
          TCP: connect to backend.port
          HTTP: GET /healthz and validate the response
          HTTPS: complete TLS plus HTTP validation

        The simulation uses backend.fail_health_checks to produce deterministic
        failures.
        """
        if backend.fail_health_checks:
            latency = self.timeout_seconds * 1000
            return HealthCheckResult(
                backend=backend.name,
                healthy=False,
                latency_ms=latency,
                reason="health endpoint failed or timed out",
            )

        latency = 5.0 + (hash(backend.name) % 15)
        return HealthCheckResult(
            backend=backend.name,
            healthy=True,
            latency_ms=float(latency),
            reason="health check passed",
        )

    def apply(self, backend: Backend, result: HealthCheckResult) -> None:
        """
        Apply threshold-based health-state transitions.

        Thresholds prevent one transient probe failure from immediately
        removing a backend from service.
        """
        if result.healthy:
            self.consecutive_failures[backend.name] = 0
            self.consecutive_successes[backend.name] += 1

            if (
                backend.state == BackendState.UNHEALTHY
                and self.consecutive_successes[backend.name] >= self.recovery_threshold
            ):
                backend.state = BackendState.HEALTHY
        else:
            self.consecutive_successes[backend.name] = 0
            self.consecutive_failures[backend.name] += 1

            if self.consecutive_failures[backend.name] >= self.failure_threshold:
                backend.state = BackendState.UNHEALTHY


class BackendPool:
    """Maintains a collection of candidate backend servers."""

    def __init__(self, backends: Iterable[Backend]):
        self.backends = list(backends)
        if not self.backends:
            raise ValueError("A backend pool must contain at least one backend.")

    def healthy_backends(self) -> list[Backend]:
        return [b for b in self.backends if b.accepting_new_traffic]

    def find(self, name: str) -> Backend:
        for backend in self.backends:
            if backend.name == name:
                return backend
        raise KeyError(f"Unknown backend: {name}")

    def start_draining(self, name: str) -> None:
        """
        Draining stops new connections while allowing existing connections to
        finish. This is useful during deployments and controlled maintenance.
        """
        backend = self.find(name)
        if backend.state == BackendState.HEALTHY:
            backend.state = BackendState.DRAINING

    def recover(self, name: str) -> None:
        backend = self.find(name)
        backend.state = BackendState.HEALTHY


class Layer4LoadBalancer:
    """
    Simplified Layer 4 load balancer.

    The routing decision deliberately ignores HTTP path and host information.
    It chooses a backend using transport-level connection characteristics and
    then associates the connection with that backend.
    """

    def __init__(
        self,
        pool: BackendPool,
        algorithm: Algorithm = Algorithm.ROUND_ROBIN,
    ):
        if algorithm not in {
            Algorithm.ROUND_ROBIN,
            Algorithm.WEIGHTED_ROUND_ROBIN,
            Algorithm.LEAST_CONNECTIONS,
            Algorithm.CONSISTENT_HASH,
        }:
            raise ValueError("Unsupported Layer 4 algorithm.")

        self.pool = pool
        self.algorithm = algorithm
        self._round_robin_index = 0
        self.connection_table: dict[str, str] = {}

    def _round_robin(self, candidates: list[Backend]) -> Backend:
        backend = candidates[self._round_robin_index % len(candidates)]
        self._round_robin_index += 1
        return backend

    def _weighted_round_robin(self, candidates: list[Backend]) -> Backend:
        expanded: list[Backend] = []
        for backend in candidates:
            if backend.weight <= 0:
                raise ValueError(f"Invalid weight for {backend.name}.")
            expanded.extend([backend] * backend.weight)

        backend = expanded[self._round_robin_index % len(expanded)]
        self._round_robin_index += 1
        return backend

    @staticmethod
    def _least_connections(candidates: list[Backend]) -> Backend:
        return min(candidates, key=lambda backend: backend.active_connections)

    def _consistent_hash(
        self,
        candidates: list[Backend],
        connection: L4Connection,
    ) -> Backend:
        """
        Hash source address and port to provide stable routing.

        Consistent hashing reduces remapping when the backend membership
        changes, although production implementations usually use a hash ring
        with virtual nodes rather than this compact selection model.
        """
        key = f"{connection.source_ip}:{connection.source_port}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        position = int(digest, 16) % len(candidates)
        return candidates[position]

    def select_backend(self, connection: L4Connection) -> Backend:
        if connection.connection_id in self.connection_table:
            backend_name = self.connection_table[connection.connection_id]
            return self.pool.find(backend_name)

        candidates = self.pool.healthy_backends()
        if not candidates:
            raise RuntimeError("No healthy backend is available.")

        if self.algorithm == Algorithm.ROUND_ROBIN:
            backend = self._round_robin(candidates)
        elif self.algorithm == Algorithm.WEIGHTED_ROUND_ROBIN:
            backend = self._weighted_round_robin(candidates)
        elif self.algorithm == Algorithm.LEAST_CONNECTIONS:
            backend = self._least_connections(candidates)
        else:
            backend = self._consistent_hash(candidates, connection)

        self.connection_table[connection.connection_id] = backend.name
        backend.active_connections += 1
        return backend

    def close_connection(self, connection_id: str) -> None:
        """
        Remove the connection mapping and release one backend connection.

        Production load balancers must carefully handle duplicate close events
        and connection timeouts. This implementation makes close idempotent.
        """
        backend_name = self.connection_table.pop(connection_id, None)
        if backend_name is None:
            return

        backend = self.pool.find(backend_name)
        backend.active_connections = max(0, backend.active_connections - 1)


class Layer7LoadBalancer:
    """
    HTTP-aware load balancer.

    Routing rules are intentionally different from L4 routing because L7 can
    inspect host/path/method and application cookies.
    """

    def __init__(self, pool: BackendPool):
        self.pool = pool
        self.round_robin_index = 0
        self.session_table: dict[str, str] = {}
        self.metrics = Counter()

    def _round_robin(self, candidates: list[Backend]) -> Backend:
        backend = candidates[self.round_robin_index % len(candidates)]
        self.round_robin_index += 1
        return backend

    def select_backend(self, request: HttpRequest) -> Backend:
        candidates = self.pool.healthy_backends()
        if not candidates:
            raise RuntimeError("HTTP request rejected: no healthy backend.")

        # Application-aware routing: administrative endpoints are isolated
        # from ordinary API traffic.
        if request.path.startswith("/admin"):
            admin_candidates = [
                b for b in candidates if b.version == "admin"
            ]
            if admin_candidates:
                return self._round_robin(admin_candidates)

        # Static content can be routed to nodes optimized for that workload.
        if request.path.startswith("/static/"):
            static_candidates = [
                b for b in candidates if b.region == "edge"
            ]
            if static_candidates:
                return self._round_robin(static_candidates)

        # Cookie-based affinity is an application-level routing decision.
        session_id = request.cookies.get("session_id")
        if session_id and session_id in self.session_table:
            session_backend = self.pool.find(self.session_table[session_id])
            if session_backend.accepting_new_traffic:
                self.metrics["sticky_session_hit"] += 1
                return session_backend

        backend = self._round_robin(candidates)

        if session_id:
            self.session_table[session_id] = backend.name
            self.metrics["sticky_session_assignment"] += 1

        return backend

    def handle_request(
        self,
        request: HttpRequest,
        latency_ms: Optional[float] = None,
        rng: Optional[random.Random] = None,
    ) -> Backend:
        backend = self.select_backend(request)

        # A request cannot be routed to a backend that is not accepting
        # traffic. The state can change between selection and execution in
        # real systems, so retry/failover logic is normally needed as well.
        if not backend.accepting_new_traffic:
            self.metrics["routing_race_failure"] += 1
            raise RuntimeError(f"Backend {backend.name} stopped accepting traffic.")

        random_source = rng or random.Random()
        if random_source.random() < backend.failure_probability:
            self.metrics["upstream_failure"] += 1
            raise ConnectionError(f"Backend {backend.name} failed during request.")

        simulated_latency = (
            latency_ms if latency_ms is not None else 10.0 + random_source.random() * 20
        )
        backend.requests_served += 1
        backend.total_latency_ms += simulated_latency
        self.metrics["requests"] += 1
        return backend


class HighAvailabilityLoadBalancer:
    """
    Active/standby load-balancer pair.

    The model assumes an external mechanism can detect failure of the active
    load balancer. Failover changes which instance is authoritative.
    """

    def __init__(
        self,
        primary_name: str = "lb-primary",
        standby_name: str = "lb-standby",
    ):
        self.primary_name = primary_name
        self.standby_name = standby_name
        self.active_name = primary_name
        self.failover_events = 0

    def fail_active_node(self) -> None:
        if self.active_name == self.primary_name:
            self.active_name = self.standby_name
        else:
            self.active_name = self.primary_name
        self.failover_events += 1

    @property
    def active(self) -> str:
        return self.active_name


@dataclass
class RoutingDecision:
    client: str
    protocol: str
    target: str
    reason: str


class LoadBalancingLab:
    """Runs coherent demonstrations instead of unrelated language examples."""

    def __init__(self):
        self.rng = random.Random(42)
        self.backends = BackendPool(
            [
                Backend(
                    name="api-a",
                    ip="10.0.1.10",
                    port=8080,
                    weight=3,
                    region="primary",
                    version="v1",
                ),
                Backend(
                    name="api-b",
                    ip="10.0.1.11",
                    port=8080,
                    weight=2,
                    region="primary",
                    version="v1",
                ),
                Backend(
                    name="api-c",
                    ip="10.0.2.10",
                    port=8080,
                    weight=1,
                    region="secondary",
                    version="v1",
                ),
                Backend(
                    name="static-edge",
                    ip="10.0.9.10",
                    port=8080,
                    weight=1,
                    region="edge",
                    version="v1",
                ),
                Backend(
                    name="admin-a",
                    ip="10.0.8.10",
                    port=8080,
                    weight=1,
                    region="primary",
                    version="admin",
                ),
            ]
        )
        self.health_checker = HealthChecker(
            failure_threshold=2,
            recovery_threshold=2,
        )

    @staticmethod
    def heading(title: str) -> None:
        print("\n" + "=" * 78)
        print(title)
        print("=" * 78)

    def demonstrate_health_checks(self) -> None:
        self.heading("ACTIVE HEALTH CHECKS")

        for backend in self.backends.backends:
            result = self.health_checker.probe(backend)
            self.health_checker.apply(backend, result)
            print(
                f"{backend.name:14} "
                f"healthy={str(result.healthy):5} "
                f"state={backend.state.value:10} "
                f"reason={result.reason}"
            )

        target = self.backends.find("api-b")
        target.fail_health_checks = True

        print("\nSimulating repeated failure of api-b:")
        for probe_number in range(1, 4):
            result = self.health_checker.probe(target)
            self.health_checker.apply(target, result)
            print(
                f"probe={probe_number} failures="
                f"{self.health_checker.consecutive_failures[target.name]} "
                f"state={target.state.value}"
            )

        target.fail_health_checks = False

        print("\nSimulating recovery of api-b:")
        for probe_number in range(1, 3):
            result = self.health_checker.probe(target)
            self.health_checker.apply(target, result)
            print(
                f"probe={probe_number} successes="
                f"{self.health_checker.consecutive_successes[target.name]} "
                f"state={target.state.value}"
            )

    def demonstrate_l4(self) -> None:
        self.heading("LAYER 4 LOAD BALANCING")

        lb = Layer4LoadBalancer(
            self.backends,
            algorithm=Algorithm.WEIGHTED_ROUND_ROBIN,
        )

        decisions: list[RoutingDecision] = []

        for index in range(8):
            connection = L4Connection(
                connection_id=f"tcp-{index}",
                source_ip=f"192.168.1.{100 + index}",
                source_port=40000 + index,
                destination_ip="203.0.113.20",
                destination_port=443,
            )
            backend = lb.select_backend(connection)
            decisions.append(
                RoutingDecision(
                    client=connection.source_ip,
                    protocol=connection.protocol,
                    target=backend.name,
                    reason="weighted transport-level selection",
                )
            )

        for decision in decisions:
            print(
                f"{decision.client:16} -> "
                f"{decision.target:14} ({decision.reason})"
            )

        print("\nClosing half of the connections:")
        for connection_id in list(lb.connection_table)[:4]:
            lb.close_connection(connection_id)

        for backend in self.backends.backends:
            print(
                f"{backend.name:14} active_connections="
                f"{backend.active_connections}"
            )

    def demonstrate_l7(self) -> None:
        self.heading("LAYER 7 HTTP LOAD BALANCING")

        lb = Layer7LoadBalancer(self.backends)

        requests = [
            HttpRequest(
                request_id="r-001",
                client_ip="198.51.100.10",
                host="api.example.internal",
                method="GET",
                path="/orders",
            ),
            HttpRequest(
                request_id="r-002",
                client_ip="198.51.100.11",
                host="api.example.internal",
                method="GET",
                path="/static/logo.svg",
            ),
            HttpRequest(
                request_id="r-003",
                client_ip="198.51.100.12",
                host="admin.example.internal",
                method="GET",
                path="/admin/users",
            ),
            HttpRequest(
                request_id="r-004",
                client_ip="198.51.100.13",
                host="api.example.internal",
                method="POST",
                path="/orders",
                cookies={"session_id": "customer-42"},
            ),
            HttpRequest(
                request_id="r-005",
                client_ip="198.51.100.13",
                host="api.example.internal",
                method="GET",
                path="/orders/123",
                cookies={"session_id": "customer-42"},
            ),
        ]

        for request in requests:
            backend = lb.handle_request(request, rng=self.rng)
            print(
                f"{request.method:4} {request.path:20} "
                f"session={request.cookies.get('session_id', '-'):12} "
                f"-> {backend.name}"
            )

        print("\nL7 routing metrics:")
        for name, value in sorted(lb.metrics.items()):
            print(f"{name:26} {value}")

    def demonstrate_least_connections(self) -> None:
        self.heading("LEAST-CONNECTIONS DISTRIBUTION")

        pool = BackendPool(
            [
                Backend("worker-a", "10.1.0.1", 8080, active_connections=5),
                Backend("worker-b", "10.1.0.2", 8080, active_connections=1),
                Backend("worker-c", "10.1.0.3", 8080, active_connections=3),
            ]
        )

        lb = Layer4LoadBalancer(pool, Algorithm.LEAST_CONNECTIONS)

        for index in range(6):
            connection = L4Connection(
                connection_id=f"least-{index}",
                source_ip="192.0.2.1",
                source_port=50000 + index,
                destination_ip="203.0.113.50",
                destination_port=443,
            )
            backend = lb.select_backend(connection)
            print(
                f"connection={connection.connection_id} "
                f"selected={backend.name} "
                f"new_count={backend.active_connections}"
            )

    def demonstrate_consistent_hashing(self) -> None:
        self.heading("CONSISTENT-HASH-STYLE CLIENT AFFINITY")

        pool = BackendPool(
            [
                Backend("cache-a", "10.2.0.1", 8080),
                Backend("cache-b", "10.2.0.2", 8080),
                Backend("cache-c", "10.2.0.3", 8080),
            ]
        )
        lb = Layer4LoadBalancer(pool, Algorithm.CONSISTENT_HASH)

        for client_ip in [
            "192.0.2.10",
            "192.0.2.11",
            "192.0.2.12",
            "192.0.2.13",
        ]:
            connection = L4Connection(
                connection_id=f"hash-{client_ip}",
                source_ip=client_ip,
                source_port=42000,
                destination_ip="203.0.113.60",
                destination_port=443,
            )
            backend = lb.select_backend(connection)
            print(f"{client_ip:16} -> {backend.name}")

    def demonstrate_draining(self) -> None:
        self.heading("BACKEND DRAINING")

        backend = self.backends.find("api-c")
        backend.active_connections = 4

        print(
            f"Before maintenance: {backend.name} state={backend.state.value} "
            f"active={backend.active_connections}"
        )

        self.backends.start_draining(backend.name)

        print(
            f"During maintenance: {backend.name} state={backend.state.value} "
            f"accepting_new_traffic={backend.accepting_new_traffic}"
        )

        # Existing connections can finish independently of the new-traffic
        # decision. A production implementation may wait for a connection
        # drain timeout before terminating the process.
        while backend.active_connections > 0:
            backend.active_connections -= 1

        print(
            f"After drain: {backend.name} state={backend.state.value} "
            f"active={backend.active_connections}"
        )

        backend.state = BackendState.HEALTHY

    def demonstrate_failure_during_request(self) -> None:
        self.heading("UPSTREAM FAILURE DURING REQUEST PROCESSING")

        pool = BackendPool(
            [
                Backend(
                    "unstable-a",
                    "10.3.0.1",
                    8080,
                    failure_probability=0.35,
                ),
                Backend(
                    "stable-b",
                    "10.3.0.2",
                    8080,
                    failure_probability=0.0,
                ),
            ]
        )
        lb = Layer7LoadBalancer(pool)
        successes = Counter()
        failures = 0

        for index in range(20):
            request = HttpRequest(
                request_id=f"failure-test-{index}",
                client_ip="198.51.100.30",
                host="api.example.internal",
                method="GET",
                path="/health-aware-operation",
            )

            try:
                backend = lb.handle_request(request, rng=self.rng)
                successes[backend.name] += 1
            except ConnectionError:
                failures += 1

        print(f"successful_requests={sum(successes.values())}")
        print(f"upstream_failures={failures}")
        for backend_name, count in successes.items():
            print(f"{backend_name:14} successful={count}")

        print(
            "\nA production design may retry idempotent requests on another "
            "healthy backend, but blind retries can duplicate non-idempotent "
            "operations such as POST requests."
        )

    def demonstrate_high_availability(self) -> None:
        self.heading("HIGH AVAILABILITY")

        ha = HighAvailabilityLoadBalancer()

        print(f"Initial active load balancer: {ha.active}")
        ha.fail_active_node()
        print(f"After failure detection:       {ha.active}")
        ha.fail_active_node()
        print(f"After recovery/failback:       {ha.active}")
        print(f"Failover events:               {ha.failover_events}")

        print(
            "\nHigh availability requires more than two processes. The design "
            "also needs failure detection, a shared or replicated configuration, "
            "a stable service address such as a virtual IP or DNS mechanism, "
            "and protection against split-brain ownership."
        )

    def demonstrate_validation(self) -> None:
        self.heading("CONFIGURATION VALIDATION AND FAILURE CONDITIONS")

        invalid_backend = Backend(
            name="invalid",
            ip="10.4.0.1",
            port=8080,
            weight=0,
        )

        try:
            Layer4LoadBalancer(
                BackendPool([invalid_backend]),
                Algorithm.WEIGHTED_ROUND_ROBIN,
            ).select_backend(
                L4Connection(
                    connection_id="invalid-weight",
                    source_ip="192.0.2.99",
                    source_port=50000,
                    destination_ip="203.0.113.99",
                    destination_port=443,
                )
            )
        except ValueError as exc:
            print(f"Rejected invalid configuration: {exc}")

        empty_pool = BackendPool(
            [
                Backend(
                    "offline",
                    "10.4.0.2",
                    8080,
                    state=BackendState.UNHEALTHY,
                )
            ]
        )

        try:
            Layer4LoadBalancer(empty_pool).select_backend(
                L4Connection(
                    connection_id="no-backend",
                    source_ip="192.0.2.100",
                    source_port=50001,
                    destination_ip="203.0.113.99",
                    destination_port=443,
                )
            )
        except RuntimeError as exc:
            print(f"Traffic rejected safely: {exc}")

    def print_backend_report(self) -> None:
        self.heading("BACKEND OPERATIONS REPORT")

        for backend in self.backends.backends:
            print(
                f"{backend.name:14} "
                f"state={backend.state.value:10} "
                f"weight={backend.weight:<2} "
                f"connections={backend.active_connections:<2} "
                f"requests={backend.requests_served:<3} "
                f"avg_latency={backend.average_latency_ms:6.2f} ms"
            )

    def run(self) -> None:
        self.heading("LOAD BALANCING LAB")
        print(
            "A deterministic simulation of L4/L7 routing, health checks, "
            "traffic distribution, and high availability."
        )

        self.demonstrate_health_checks()
        self.demonstrate_l4()
        self.demonstrate_l7()
        self.demonstrate_least_connections()
        self.demonstrate_consistent_hashing()
        self.demonstrate_draining()
        self.demonstrate_failure_during_request()
        self.demonstrate_high_availability()
        self.demonstrate_validation()
        self.print_backend_report()


def run_small_self_tests() -> None:
    """Validate important routing invariants without external test packages."""

    pool = BackendPool(
        [
            Backend("a", "10.0.0.1", 8080),
            Backend("b", "10.0.0.2", 8080),
        ]
    )

    lb = Layer4LoadBalancer(pool, Algorithm.ROUND_ROBIN)

    first = lb.select_backend(
        L4Connection("test-1", "192.0.2.1", 40001, "203.0.113.1", 443)
    )
    second = lb.select_backend(
        L4Connection("test-2", "192.0.2.2", 40002, "203.0.113.1", 443)
    )

    assert first.name != second.name
    assert first.active_connections == 1
    assert second.active_connections == 1

    lb.close_connection("test-1")
    assert first.active_connections == 0

    pool.find("b").state = BackendState.UNHEALTHY
    third = lb.select_backend(
        L4Connection("test-3", "192.0.2.3", 40003, "203.0.113.1", 443)
    )
    assert third.name == "a"

    checker = HealthChecker(failure_threshold=1, recovery_threshold=1)
    backend = pool.find("b")
    backend.fail_health_checks = True
    result = checker.probe(backend)
    checker.apply(backend, result)
    assert backend.state == BackendState.UNHEALTHY

    backend.fail_health_checks = False
    result = checker.probe(backend)
    checker.apply(backend, result)
    assert backend.state == BackendState.HEALTHY


if __name__ == "__main__":
    run_small_self_tests()
    LoadBalancingLab().run()
