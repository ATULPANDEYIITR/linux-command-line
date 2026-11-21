#!/usr/bin/env python3
"""
Docker Compose: Declarative Multi-Container Application Orchestration

Demonstrates:
- Service configuration and validation
- Environment variable interpolation
- Dependency graphs and startup ordering
- Health checks and readiness conditions
- Networks, ports, volumes, and restart policies
- Deployment lifecycle simulation
- Failure handling and service recovery
- Configuration inspection and deployment reporting

Requires Python 3.10+.
Uses only the Python standard library.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ComposeError(Exception):
    """Base exception for Compose-related errors."""


class ConfigurationError(ComposeError):
    pass


class DependencyError(ComposeError):
    pass


class DeploymentError(ComposeError):
    pass


class ServiceState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"
    FAILED = "failed"


class RestartPolicy(str, Enum):
    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    UNLESS_STOPPED = "unless-stopped"


class DependencyCondition(str, Enum):
    STARTED = "service_started"
    HEALTHY = "service_healthy"
    COMPLETED = "service_completed_successfully"


@dataclass(frozen=True)
class PortMapping:
    host: int
    container: int
    protocol: str = "tcp"

    def validate(self) -> None:
        if not 1 <= self.host <= 65535:
            raise ConfigurationError("Invalid host port")
        if not 1 <= self.container <= 65535:
            raise ConfigurationError("Invalid container port")
        if self.protocol not in {"tcp", "udp"}:
            raise ConfigurationError("Unsupported port protocol")


@dataclass(frozen=True)
class VolumeMount:
    source: str
    target: str
    read_only: bool = False

    def validate(self) -> None:
        if not self.source or not self.target.startswith("/"):
            raise ConfigurationError("Invalid volume mount")
        if ".." in self.target.split("/"):
            raise ConfigurationError("Unsafe volume target")


@dataclass
class Dependency:
    service: str
    condition: DependencyCondition = DependencyCondition.STARTED


@dataclass
class HealthCheck:
    command: str
    interval_seconds: int = 10
    retries: int = 3
    start_period_seconds: int = 0

    def validate(self) -> None:
        if not self.command.strip():
            raise ConfigurationError("Health-check command is required")
        if self.interval_seconds < 1 or self.retries < 1:
            raise ConfigurationError("Invalid health-check configuration")


@dataclass
class ServiceConfig:
    name: str
    image: str
    command: str = ""
    environment: dict[str, str] = field(default_factory=dict)
    ports: list[PortMapping] = field(default_factory=list)
    volumes: list[VolumeMount] = field(default_factory=list)
    networks: set[str] = field(default_factory=set)
    depends_on: list[Dependency] = field(default_factory=list)
    healthcheck: HealthCheck | None = None
    restart: RestartPolicy = RestartPolicy.NO
    replicas: int = 1
    profiles: set[str] = field(default_factory=set)

    def validate(self) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", self.name):
            raise ConfigurationError(f"Invalid service name: {self.name}")

        if not self.image or not self.image.strip():
            raise ConfigurationError(f"{self.name}: image is required")

        if self.replicas < 1:
            raise ConfigurationError(f"{self.name}: replicas must be positive")

        for port in self.ports:
            port.validate()

        for volume in self.volumes:
            volume.validate()

        if self.healthcheck:
            self.healthcheck.validate()


@dataclass
class ServiceRuntime:
    config: ServiceConfig
    state: ServiceState = ServiceState.CREATED
    attempts: int = 0
    error: str | None = None
    started_at: float | None = None
    healthy_at: float | None = None


class EnvironmentResolver:
    """Resolve ${NAME} and ${NAME:-default} expressions."""

    PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

    @classmethod
    def resolve(
        cls,
        value: str,
        environment: dict[str, str],
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)

            if name in environment:
                return environment[name]

            if default is not None:
                return default

            raise ConfigurationError(
                f"Required environment variable is missing: {name}"
            )

        return cls.PATTERN.sub(replace, value)


class ComposeProject:
    def __init__(
        self,
        name: str,
        services: list[ServiceConfig],
        networks: set[str],
        environment: dict[str, str] | None = None,
    ):
        self.name = name
        self.networks = networks
        self.environment = dict(os.environ if environment is None else environment)
        self.services = {s.name: ServiceRuntime(s) for s in services}
        self.events: list[dict[str, Any]] = []
        self.validate()

    def log(self, service: str, event: str, detail: str = "") -> None:
        self.events.append({
            "time": round(time.time(), 3),
            "service": service,
            "event": event,
            "detail": detail,
        })

    def validate(self) -> None:
        if not self.name:
            raise ConfigurationError("Project name is required")

        if len(self.services) == 0:
            raise ConfigurationError("Project must contain services")

        occupied_ports: set[tuple[int, str]] = set()

        for name, runtime in self.services.items():
            runtime.config.validate()

            for dependency in runtime.config.depends_on:
                if dependency.service not in self.services:
                    raise DependencyError(
                        f"{name} depends on unknown service "
                        f"{dependency.service}"
                    )

                if dependency.service == name:
                    raise DependencyError(f"{name} cannot depend on itself")

            unknown_networks = runtime.config.networks - self.networks
            if unknown_networks:
                raise ConfigurationError(
                    f"{name} references unknown networks: {unknown_networks}"
                )

            for port in runtime.config.ports:
                key = (port.host, port.protocol)
                if key in occupied_ports:
                    raise ConfigurationError(
                        f"Host port conflict: {port.host}/{port.protocol}"
                    )
                occupied_ports.add(key)

            runtime.config.environment = {
                key: EnvironmentResolver.resolve(value, self.environment)
                for key, value in runtime.config.environment.items()
            }

        self.startup_order()

    def startup_order(self) -> list[str]:
        """
        Topological sorting using Kahn's algorithm.

        Complexity: O(V + E), where V is services and E is
        dependency relationships.
        """
        indegree = {name: 0 for name in self.services}
        dependents: dict[str, list[str]] = defaultdict(list)

        for name, runtime in self.services.items():
            for dependency in runtime.config.depends_on:
                indegree[name] += 1
                dependents[dependency.service].append(name)

        queue = deque(
            name for name, degree in indegree.items() if degree == 0
        )

        result = []

        while queue:
            name = queue.popleft()
            result.append(name)

            for dependent in dependents[name]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.services):
            raise DependencyError("Circular service dependency detected")

        return result

    def dependency_satisfied(self, dependency: Dependency) -> bool:
        runtime = self.services[dependency.service]

        if dependency.condition == DependencyCondition.STARTED:
            return runtime.state in {
                ServiceState.RUNNING,
                ServiceState.HEALTHY,
            }

        if dependency.condition == DependencyCondition.HEALTHY:
            return runtime.state == ServiceState.HEALTHY

        if dependency.condition == DependencyCondition.COMPLETED:
            return runtime.state == ServiceState.STOPPED

        return False

    def start_service(self, name: str) -> None:
        runtime = self.services[name]
        config = runtime.config

        if runtime.state in {ServiceState.RUNNING, ServiceState.HEALTHY}:
            return

        for dependency in config.depends_on:
            if not self.dependency_satisfied(dependency):
                raise DeploymentError(
                    f"{name} cannot start: dependency "
                    f"{dependency.service} has not satisfied "
                    f"{dependency.condition.value}"
                )

        runtime.state = ServiceState.STARTING
        runtime.attempts += 1
        self.log(name, "starting", config.image)

        # A real implementation would invoke the Docker Engine API.
        runtime.started_at = time.time()

        if config.healthcheck:
            runtime.state = ServiceState.HEALTHY
            runtime.healthy_at = time.time()
            self.log(name, "healthy", "Health check passed")
        else:
            runtime.state = ServiceState.RUNNING
            self.log(name, "running", "Container started")

    def up(self) -> None:
        self.log(self.name, "deployment_started")

        for name in self.startup_order():
            try:
                self.start_service(name)
            except ComposeError as exc:
                self.services[name].state = ServiceState.FAILED
                self.services[name].error = str(exc)
                self.log(name, "failed", str(exc))
                raise

        self.log(self.name, "deployment_completed")

    def stop_service(self, name: str) -> None:
        if name not in self.services:
            raise DeploymentError(f"Unknown service: {name}")

        runtime = self.services[name]

        if runtime.state == ServiceState.STOPPED:
            return

        runtime.state = ServiceState.STOPPED
        self.log(name, "stopped")

    def down(self) -> None:
        for name in reversed(self.startup_order()):
            self.stop_service(name)

        self.log(self.name, "deployment_stopped")

    def simulate_failure(self, name: str, reason: str) -> bool:
        if name not in self.services:
            raise DeploymentError(f"Unknown service: {name}")

        runtime = self.services[name]
        runtime.state = ServiceState.FAILED
        runtime.error = reason
        self.log(name, "failed", reason)

        policy = runtime.config.restart

        if policy in {
            RestartPolicy.ALWAYS,
            RestartPolicy.UNLESS_STOPPED,
            RestartPolicy.ON_FAILURE,
        }:
            runtime.state = ServiceState.STARTING
            runtime.attempts += 1
            runtime.error = None

            if runtime.config.healthcheck:
                runtime.state = ServiceState.HEALTHY
            else:
                runtime.state = ServiceState.RUNNING

            self.log(name, "restarted", policy.value)
            return True

        return False

    def status(self) -> dict[str, str]:
        return {
            name: runtime.state.value
            for name, runtime in self.services.items()
        }

    def deployment_report(self) -> dict[str, Any]:
        return {
            "project": self.name,
            "status": self.status(),
            "startup_order": self.startup_order(),
            "services": {
                name: {
                    "image": runtime.config.image,
                    "state": runtime.state.value,
                    "attempts": runtime.attempts,
                    "error": runtime.error,
                }
                for name, runtime in self.services.items()
            },
            "events": self.events,
        }


def build_example_project() -> ComposeProject:
    services = [
        ServiceConfig(
            name="database",
            image="postgres:18",
            environment={
                "POSTGRES_DB": "${DB_NAME:-application}",
                "POSTGRES_USER": "${DB_USER:-app}",
                "POSTGRES_PASSWORD": "${DB_PASSWORD:-local-only}",
            },
            volumes=[
                VolumeMount("database-data", "/var/lib/postgresql/data")
            ],
            networks={"backend"},
            healthcheck=HealthCheck(
                "pg_isready -U app -d application"
            ),
            restart=RestartPolicy.UNLESS_STOPPED,
        ),
        ServiceConfig(
            name="cache",
            image="redis:8",
            networks={"backend"},
            healthcheck=HealthCheck("redis-cli ping"),
            restart=RestartPolicy.ALWAYS,
        ),
        ServiceConfig(
            name="api",
            image="example/api:1.0",
            command="python app.py",
            environment={
                "DATABASE_HOST": "database",
                "CACHE_HOST": "cache",
            },
            ports=[PortMapping(8000, 8000)],
            networks={"frontend", "backend"},
            depends_on=[
                Dependency("database", DependencyCondition.HEALTHY),
                Dependency("cache", DependencyCondition.HEALTHY),
            ],
            restart=RestartPolicy.ON_FAILURE,
            healthcheck=HealthCheck("curl -f http://localhost:8000/health"),
        ),
        ServiceConfig(
            name="web",
            image="example/web:1.0",
            ports=[PortMapping(8080, 80)],
            networks={"frontend"},
            depends_on=[
                Dependency("api", DependencyCondition.HEALTHY)
            ],
            restart=RestartPolicy.UNLESS_STOPPED,
        ),
    ]

    return ComposeProject(
        name="inventory-platform",
        services=services,
        networks={"frontend", "backend"},
        environment={
            "DB_NAME": "inventory",
            "DB_USER": "inventory_user",
            "DB_PASSWORD": "development-secret",
        },
    )


def test_project() -> None:
    project = build_example_project()

    assert project.startup_order() == [
        "database", "cache", "api", "web"
    ]

    project.up()

    assert project.status()["database"] == "healthy"
    assert project.status()["api"] == "healthy"
    assert project.status()["web"] == "running"

    restarted = project.simulate_failure(
        "api", "Simulated database connection interruption"
    )

    assert restarted
    assert project.status()["api"] == "healthy"

    project.down()
    assert all(
        state == "stopped"
        for state in project.status().values()
    )

    try:
        ComposeProject(
            "invalid",
            [
                ServiceConfig(
                    "first", "image:first",
                    depends_on=[Dependency("second")]
                ),
                ServiceConfig(
                    "second", "image:second",
                    depends_on=[Dependency("first")]
                ),
            ],
            set(),
        )
    except DependencyError:
        pass
    else:
        raise AssertionError("Circular dependency was not detected")

    try:
        PortMapping(80000, 80).validate()
    except ConfigurationError:
        pass
    else:
        raise AssertionError("Invalid port was accepted")


def main() -> None:
    test_project()

    project = build_example_project()
    project.up()

    project.simulate_failure("cache", "Simulated cache failure")

    print(json.dumps(
        project.deployment_report(),
        indent=2,
        default=str,
    ))

    project.down()


if __name__ == "__main__":
    main()
