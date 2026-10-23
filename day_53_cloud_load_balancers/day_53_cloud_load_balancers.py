#!/usr/bin/env python3
"""
Cloud Load Balancer Simulator

Models:
- Backend target groups
- Health checks
- Weighted and least-connections traffic routing
- TLS/SSL termination
- Connection lifecycle
- Backend failure and recovery
- Sticky sessions
- Administrative validation
- Access logging
- Basic operational metrics

The implementation uses only Python's standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import ipaddress
import random
import ssl
import time
from typing import Dict, Iterable, List, Optional, Tuple


class Protocol(str, Enum):
    HTTP = "HTTP"
    HTTPS = "HTTPS"


class TargetState(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"


class LoadBalancingAlgorithm(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONNECTIONS = "least_connections"


@dataclass
class HealthCheckConfig:
    path: str = "/health"
    interval_seconds: float = 5.0
    timeout_seconds: float = 2.0
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("Health-check path must start with '/'")
        if self.interval_seconds <= 0 or self.timeout_seconds <= 0:
            raise ValueError("Health-check timing values must be positive")
        if self.healthy_threshold < 1 or self.unhealthy_threshold < 1:
            raise ValueError("Health-check thresholds must be positive")


@dataclass
class Target:
    target_id: str
    host: str
    port: int
    weight: int = 1
    state: TargetState = TargetState.HEALTHY
    response_latency_ms: float = 20.0
    simulated_health: bool = True
    active_connections: int = 0
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0

    def __post_init__(self) -> None:
        try:
            ipaddress.ip_address(self.host)
        except ValueError:
            if not self.host or any(ch.isspace() for ch in self.host):
                raise ValueError(f"Invalid target host: {self.host}")

        if not 1 <= self.port <= 65535:
            raise ValueError(f"Invalid target port: {self.port}")
        if self.weight < 1:
            raise ValueError("Target weight must be at least 1")
        if self.response_latency_ms < 0:
            raise ValueError("Latency cannot be negative")

    def check_health(self, config: HealthCheckConfig) -> bool:
        """Simulate an application health endpoint response."""
        if self.state == TargetState.DRAINING:
            return False

        if self.simulated_health:
            self.consecutive_successes += 1
            self.consecutive_failures = 0

            if self.consecutive_successes >= config.healthy_threshold:
                self.state = TargetState.HEALTHY
            return True

        self.consecutive_failures += 1
        self.consecutive_successes = 0

        if self.consecutive_failures >= config.unhealthy_threshold:
            self.state = TargetState.UNHEALTHY
        return False

    @property
    def available(self) -> bool:
        return self.state == TargetState.HEALTHY


@dataclass
class TargetGroup:
    name: str
    targets: Dict[str, Target] = field(default_factory=dict)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.WEIGHTED

    def register(self, target: Target) -> None:
        if target.target_id in self.targets:
            raise ValueError(f"Target already registered: {target.target_id}")
        self.targets[target.target_id] = target

    def deregister(self, target_id: str, drain: bool = True) -> None:
        target = self.targets.get(target_id)
        if target is None:
            raise KeyError(f"Unknown target: {target_id}")

        if drain and target.active_connections:
            target.state = TargetState.DRAINING
        else:
            del self.targets[target_id]

    def run_health_checks(self) -> None:
        for target in self.targets.values():
            target.check_health(self.health_check)

    def healthy_targets(self) -> List[Target]:
        return [target for target in self.targets.values() if target.available]

    def choose_target(self, request_key: Optional[str] = None) -> Target:
        candidates = self.healthy_targets()

        if not candidates:
            raise RuntimeError(f"Target group '{self.name}' has no healthy targets")

        if self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return min(
                candidates,
                key=lambda target: (
                    target.active_connections,
                    target.response_latency_ms,
                    target.target_id,
                ),
            )

        if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            # Deterministic selection makes simulations reproducible.
            key = request_key or str(time.monotonic_ns())
            index = int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(candidates)
            return candidates[index]

        total_weight = sum(target.weight for target in candidates)
        if total_weight <= 0:
            raise RuntimeError("No positive target weights are configured")

        key = request_key or str(time.monotonic_ns())
        digest = hashlib.sha256(key.encode()).digest()
        point = int.from_bytes(digest[:8], "big") % total_weight

        current = 0
        for target in candidates:
            current += target.weight
            if point < current:
                return target

        return candidates[-1]


@dataclass
class TLSCertificate:
    hostname: str
    certificate_id: str
    minimum_tls_version: str = "TLSv1.2"

    def validate(self) -> None:
        if not self.hostname or "." not in self.hostname:
            raise ValueError("Certificate hostname must be a valid DNS name")
        if not self.certificate_id:
            raise ValueError("Certificate identifier cannot be empty")
        if self.minimum_tls_version not in {"TLSv1.2", "TLSv1.3"}:
            raise ValueError("Only TLS 1.2 and TLS 1.3 are permitted")


@dataclass
class Request:
    request_id: str
    client_ip: str
    protocol: Protocol
    host: str
    path: str
    session_id: Optional[str] = None

    def validate(self) -> None:
        try:
            ipaddress.ip_address(self.client_ip)
        except ValueError as exc:
            raise ValueError("Invalid client IP") from exc

        if not self.host or not self.path.startswith("/"):
            raise ValueError("Request host and path are invalid")


@dataclass
class Response:
    request_id: str
    status_code: int
    target_id: Optional[str]
    tls_terminated: bool
    message: str


@dataclass
class AccessLogEntry:
    request_id: str
    client_ip: str
    host: str
    path: str
    target_id: Optional[str]
    status_code: int
    latency_ms: float
    tls_terminated: bool


class CloudLoadBalancer:
    """
    A simplified Layer-7 load balancer.

    TLS is terminated at the load balancer. Backend traffic is represented
    as HTTP in this simulation, but production deployments should normally
    use encrypted backend transport when traffic crosses an untrusted network.
    """

    def __init__(
        self,
        name: str,
        certificate: TLSCertificate,
        algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.WEIGHTED,
        sticky_sessions: bool = True,
    ) -> None:
        if not name.strip():
            raise ValueError("Load-balancer name cannot be empty")

        certificate.validate()
        self.name = name
        self.certificate = certificate
        self.algorithm = algorithm
        self.sticky_sessions = sticky_sessions
        self.target_groups: Dict[str, TargetGroup] = {}
        self.session_map: Dict[str, str] = {}
        self.logs: List[AccessLogEntry] = []

    def add_target_group(self, group: TargetGroup) -> None:
        if group.name in self.target_groups:
            raise ValueError(f"Duplicate target group: {group.name}")

        group.algorithm = self.algorithm
        self.target_groups[group.name] = group

    def synchronize_health(self) -> None:
        for group in self.target_groups.values():
            group.run_health_checks()

    def terminate_tls(self, request: Request) -> None:
        request.validate()

        if request.protocol != Protocol.HTTPS:
            return

        if request.host != self.certificate.hostname:
            raise ssl.SSLError(
                f"TLS certificate does not match requested host '{request.host}'"
            )

        # ssl.SSLContext models the protocol policy even though this simulator
        # does not open a network socket.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = (
            ssl.TLSVersion.TLSv1_3
            if self.certificate.minimum_tls_version == "TLSv1.3"
            else ssl.TLSVersion.TLSv1_2
        )
        del context

    def route(
        self,
        request: Request,
        target_group_name: str,
    ) -> Response:
        request.validate()

        if target_group_name not in self.target_groups:
            return Response(
                request.request_id,
                503,
                None,
                False,
                "Unknown target group",
            )

        group = self.target_groups[target_group_name]

        try:
            self.terminate_tls(request)
        except (ssl.SSLError, ValueError) as exc:
            return Response(
                request.request_id,
                421,
                None,
                False,
                f"TLS validation failed: {exc}",
            )

        target: Optional[Target] = None

        # Sticky sessions are useful for stateful applications, but they can
        # reduce balancing quality and complicate failover.
        if self.sticky_sessions and request.session_id:
            mapped_id = self.session_map.get(request.session_id)
            if mapped_id:
                mapped = group.targets.get(mapped_id)
                if mapped and mapped.available:
                    target = mapped

        if target is None:
            try:
                target = group.choose_target(request.session_id or request.request_id)
            except RuntimeError as exc:
                return Response(
                    request.request_id,
                    503,
                    None,
                    request.protocol == Protocol.HTTPS,
                    str(exc),
                )

            if self.sticky_sessions and request.session_id:
                self.session_map[request.session_id] = target.target_id

        target.active_connections += 1
        target.total_requests += 1

        # A deterministic failure model keeps the demonstration reproducible.
        failure = (
            not target.simulated_health
            or target.state != TargetState.HEALTHY
        )

        latency = target.response_latency_ms

        try:
            if failure:
                target.failed_requests += 1
                status = 502
                message = "Backend target unavailable"
            else:
                status = 200
                message = f"Request served by {target.target_id}"
        finally:
            target.active_connections -= 1

        self.logs.append(
            AccessLogEntry(
                request_id=request.request_id,
                client_ip=request.client_ip,
                host=request.host,
                path=request.path,
                target_id=target.target_id,
                status_code=status,
                latency_ms=latency,
                tls_terminated=request.protocol == Protocol.HTTPS,
            )
        )

        return Response(
            request.request_id,
            status,
            target.target_id,
            request.protocol == Protocol.HTTPS,
            message,
        )

    def metrics(self) -> Dict[str, float]:
        total = len(self.logs)
        successful = sum(1 for entry in self.logs if entry.status_code < 400)
        failed = total - successful

        return {
            "requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate_percent": (successful / total * 100) if total else 0.0,
            "average_latency_ms": (
                sum(entry.latency_ms for entry in self.logs) / total
                if total
                else 0.0
            ),
        }


def print_target_group_state(group: TargetGroup) -> None:
    print(f"\nTarget group: {group.name}")
    for target in group.targets.values():
        print(
            f"  {target.target_id}: "
            f"state={target.state.value}, "
            f"weight={target.weight}, "
            f"requests={target.total_requests}, "
            f"failures={target.failed_requests}"
        )


def main() -> None:
    certificate = TLSCertificate(
        hostname="api.example.internal",
        certificate_id="cert-prod-2026",
        minimum_tls_version="TLSv1.2",
    )

    load_balancer = CloudLoadBalancer(
        name="production-api-lb",
        certificate=certificate,
        algorithm=LoadBalancingAlgorithm.WEIGHTED,
        sticky_sessions=True,
    )

    primary = TargetGroup(
        name="api-v1",
        health_check=HealthCheckConfig(
            path="/health",
            interval_seconds=5,
            timeout_seconds=2,
            healthy_threshold=2,
            unhealthy_threshold=2,
        ),
    )

    primary.register(
        Target(
            target_id="api-a",
            host="10.20.1.10",
            port=8080,
            weight=3,
            response_latency_ms=18,
        )
    )
    primary.register(
        Target(
            target_id="api-b",
            host="10.20.1.11",
            port=8080,
            weight=2,
            response_latency_ms=25,
        )
    )
    primary.register(
        Target(
            target_id="api-c",
            host="10.20.1.12",
            port=8080,
            weight=1,
            response_latency_ms=31,
        )
    )

    load_balancer.add_target_group(primary)

    # Health checks must succeed before routing decisions are trusted.
    load_balancer.synchronize_health()
    load_balancer.synchronize_health()

    requests = [
        Request(
            request_id=f"req-{i}",
            client_ip=f"192.0.2.{10 + i}",
            protocol=Protocol.HTTPS,
            host="api.example.internal",
            path="/orders",
            session_id=f"session-{i % 3}",
        )
        for i in range(1, 10)
    ]

    print("Initial traffic distribution")
    for request in requests:
        response = load_balancer.route(request, "api-v1")
        print(
            f"{response.request_id}: "
            f"status={response.status_code}, "
            f"target={response.target_id}, "
            f"{response.message}"
        )

    print_target_group_state(primary)

    # Simulate a failed backend. Health checks eventually remove it from
    # routing while other targets remain available.
    primary.targets["api-b"].simulated_health = False
    load_balancer.synchronize_health()
    load_balancer.synchronize_health()

    print("\nAfter api-b fails health checks")
    for i in range(10, 15):
        request = Request(
            request_id=f"req-{i}",
            client_ip=f"198.51.100.{i}",
            protocol=Protocol.HTTPS,
            host="api.example.internal",
            path="/orders",
            session_id=f"new-session-{i}",
        )
        response = load_balancer.route(request, "api-v1")
        print(
            f"{response.request_id}: "
            f"status={response.status_code}, target={response.target_id}"
        )

    print_target_group_state(primary)

    # Recovery requires successful health checks before the target becomes
    # eligible again.
    primary.targets["api-b"].simulated_health = True
    load_balancer.synchronize_health()
    load_balancer.synchronize_health()

    print("\nAfter api-b recovers")
    recovery_request = Request(
        request_id="recovery-1",
        client_ip="203.0.113.20",
        protocol=Protocol.HTTPS,
        host="api.example.internal",
        path="/health-dependent-operation",
        session_id="recovery-session",
    )
    print(load_balancer.route(recovery_request, "api-v1"))

    # Demonstrate certificate hostname rejection.
    invalid_host_request = Request(
        request_id="tls-error-1",
        client_ip="203.0.113.21",
        protocol=Protocol.HTTPS,
        host="malicious.example.net",
        path="/orders",
    )
    print("\nInvalid TLS hostname:")
    print(load_balancer.route(invalid_host_request, "api-v1"))

    print("\nMetrics:")
    for key, value in load_balancer.metrics().items():
        print(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")


if __name__ == "__main__":
    main()
