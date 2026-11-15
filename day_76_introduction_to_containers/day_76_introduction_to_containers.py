#!/usr/bin/env python3
"""
Introduction to Containers
A self-contained containerization and application-packaging simulator.

Demonstrates:
- Container images and immutable layers
- Image registries and content digests
- Container creation, startup, stopping and removal
- Process, filesystem and network isolation concepts
- CPU and memory resource limits
- Environment configuration and port mappings
- Health checks and restart policies
- Security validation and image vulnerability metadata
- Container orchestration and application deployment

This is an educational simulator. It does not create operating-system
namespaces, cgroups, network interfaces or real containers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("container-platform")


class ContainerError(Exception):
    """Base exception for container operations."""


class ValidationError(ContainerError):
    """Invalid container configuration."""


class StateError(ContainerError):
    """Invalid container state transition."""


class SecurityError(ContainerError):
    """Security policy violation."""


class ContainerState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    REMOVED = "removed"


class RestartPolicy(Enum):
    NO = "no"
    ON_FAILURE = "on-failure"
    ALWAYS = "always"


class HealthStatus(Enum):
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class ImageLayer:
    instruction: str
    content: str

    @property
    def digest(self) -> str:
        payload = f"{self.instruction}:{self.content}"
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ContainerImage:
    name: str
    tag: str
    layers: tuple[ImageLayer, ...]
    entrypoint: tuple[str, ...]
    exposed_ports: tuple[int, ...] = ()
    user: str = "app"
    vulnerabilities: int = 0

    def __post_init__(self):
        if not self.name or not self.tag:
            raise ValidationError("Image name and tag are required.")

        if not self.layers:
            raise ValidationError("An image must contain at least one layer.")

        if not self.entrypoint:
            raise ValidationError("Image entrypoint cannot be empty.")

        if self.vulnerabilities < 0:
            raise ValidationError("Vulnerability count cannot be negative.")

        if any(not 1 <= port <= 65535 for port in self.exposed_ports):
            raise ValidationError("Invalid exposed port.")

    @property
    def reference(self) -> str:
        return f"{self.name}:{self.tag}"

    @property
    def digest(self) -> str:
        content = "|".join(layer.digest for layer in self.layers)
        return hashlib.sha256(content.encode()).hexdigest()

    @property
    def size_bytes(self) -> int:
        return sum(len(layer.content.encode()) for layer in self.layers)


@dataclass
class ResourceLimits:
    cpu_cores: float = 1.0
    memory_mb: int = 256
    pids_limit: int = 100

    def validate(self):
        if not 0 < self.cpu_cores <= 64:
            raise ValidationError("CPU allocation must be between 0 and 64.")

        if not 16 <= self.memory_mb <= 262144:
            raise ValidationError("Memory must be between 16 MB and 256 GB.")

        if not 1 <= self.pids_limit <= 32768:
            raise ValidationError("Invalid process limit.")


@dataclass
class ContainerConfig:
    environment: dict[str, str] = field(default_factory=dict)
    port_mappings: dict[int, int] = field(default_factory=dict)
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    restart_policy: RestartPolicy = RestartPolicy.NO
    read_only_rootfs: bool = True
    privileged: bool = False
    run_as_root: bool = False

    def validate(self, image: ContainerImage):
        self.resources.validate()

        if self.privileged:
            raise SecurityError("Privileged containers are prohibited.")

        if self.run_as_root:
            raise SecurityError("Root execution is prohibited by policy.")

        for key, value in self.environment.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValidationError(f"Invalid environment variable: {key}")

            if not isinstance(value, str):
                raise ValidationError("Environment values must be strings.")

            if len(value) > 4096:
                raise ValidationError("Environment value exceeds size limit.")

        for container_port, host_port in self.port_mappings.items():
            if container_port not in image.exposed_ports:
                raise ValidationError(
                    f"Container port {container_port} is not exposed by image."
                )

            if not 1 <= host_port <= 65535:
                raise ValidationError("Invalid host port.")

        if len(set(self.port_mappings.values())) != len(self.port_mappings):
            raise ValidationError("Duplicate host port mappings.")


@dataclass
class Container:
    image: ContainerImage
    config: ContainerConfig
    container_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: ContainerState = ContainerState.CREATED
    health: HealthStatus = HealthStatus.STARTING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    restart_count: int = 0
    logs: list[str] = field(default_factory=list)

    def log(self, message: str):
        self.logs.append(message)
        logger.info("[%s] %s", self.container_id, message)

    def start(self):
        if self.state not in (
            ContainerState.CREATED,
            ContainerState.STOPPED,
        ):
            raise StateError(f"Cannot start container in {self.state.value} state.")

        self.state = ContainerState.RUNNING
        self.started_at = time.time()
        self.stopped_at = None
        self.health = HealthStatus.STARTING
        self.log(f"Started image {self.image.reference}")

    def mark_healthy(self):
        if self.state != ContainerState.RUNNING:
            raise StateError("Only running containers can become healthy.")

        self.health = HealthStatus.HEALTHY
        self.log("Health check passed.")

    def mark_unhealthy(self):
        if self.state != ContainerState.RUNNING:
            raise StateError("Only running containers can become unhealthy.")

        self.health = HealthStatus.UNHEALTHY
        self.log("Health check failed.")

    def stop(self):
        if self.state != ContainerState.RUNNING:
            raise StateError("Only running containers can be stopped.")

        self.state = ContainerState.STOPPED
        self.stopped_at = time.time()
        self.log("Container stopped.")

    def fail(self, reason: str):
        if self.state != ContainerState.RUNNING:
            raise StateError("Only running containers can fail.")

        self.state = ContainerState.FAILED
        self.health = HealthStatus.UNHEALTHY
        self.stopped_at = time.time()
        self.log(f"Container failed: {reason}")

    def remove(self):
        if self.state == ContainerState.RUNNING:
            raise StateError("Stop a container before removing it.")

        if self.state == ContainerState.REMOVED:
            raise StateError("Container is already removed.")

        self.state = ContainerState.REMOVED
        self.log("Container removed.")


class ImageRegistry:
    """Local image registry with immutable digest verification."""

    def __init__(self):
        self.images: dict[str, ContainerImage] = {}

    def push(self, image: ContainerImage):
        self.images[image.reference] = image
        logger.info("Pushed %s (%s)", image.reference, image.digest[:16])

    def pull(self, reference: str) -> ContainerImage:
        image = self.images.get(reference)

        if image is None:
            raise ContainerError(f"Image not found: {reference}")

        if hashlib.sha256(
            "|".join(layer.digest for layer in image.layers).encode()
        ).hexdigest() != image.digest:
            raise SecurityError("Image digest verification failed.")

        return image


class ContainerRuntime:
    """Manages container lifecycle and resource allocation."""

    def __init__(self, total_memory_mb: int = 4096, total_cpu: float = 8.0):
        self.containers: dict[str, Container] = {}
        self.total_memory_mb = total_memory_mb
        self.total_cpu = total_cpu

    def _allocated_resources(self):
        active = [
            c for c in self.containers.values()
            if c.state == ContainerState.RUNNING
        ]

        memory = sum(c.config.resources.memory_mb for c in active)
        cpu = sum(c.config.resources.cpu_cores for c in active)

        return memory, cpu

    def create(
        self,
        image: ContainerImage,
        config: ContainerConfig,
    ) -> Container:
        config.validate(image)

        memory, cpu = self._allocated_resources()

        if memory + config.resources.memory_mb > self.total_memory_mb:
            raise ContainerError("Insufficient available memory.")

        if cpu + config.resources.cpu_cores > self.total_cpu:
            raise ContainerError("Insufficient available CPU allocation.")

        container = Container(image=image, config=config)
        self.containers[container.container_id] = container

        logger.info("Created container %s", container.container_id)
        return container

    def start(self, container_id: str):
        container = self.get(container_id)

        memory, cpu = self._allocated_resources()

        if container.state != ContainerState.RUNNING:
            if memory + container.config.resources.memory_mb > self.total_memory_mb:
                raise ContainerError("Insufficient memory to start.")

            if cpu + container.config.resources.cpu_cores > self.total_cpu:
                raise ContainerError("Insufficient CPU to start.")

        container.start()

    def get(self, container_id: str) -> Container:
        container = self.containers.get(container_id)

        if container is None or container.state == ContainerState.REMOVED:
            raise ContainerError("Container does not exist.")

        return container

    def restart_failed(self, container_id: str):
        container = self.get(container_id)

        if container.state != ContainerState.FAILED:
            raise StateError("Restart policy applies to failed containers.")

        policy = container.config.restart_policy

        if policy == RestartPolicy.NO:
            return False

        if policy == RestartPolicy.ON_FAILURE and container.restart_count >= 3:
            container.log("Restart limit reached.")
            return False

        container.restart_count += 1
        container.state = ContainerState.STOPPED
        container.start()

        return True

    def list_containers(self):
        return [
            {
                "id": c.container_id,
                "image": c.image.reference,
                "state": c.state.value,
                "health": c.health.value,
                "restarts": c.restart_count,
            }
            for c in self.containers.values()
            if c.state != ContainerState.REMOVED
        ]

    def export_state(self, filename: str):
        """Export operational metadata, never environment secrets."""

        data = self.list_containers()
        Path(filename).write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )


def build_application_image() -> ContainerImage:
    """Build a layered application image."""

    return ContainerImage(
        name="inventory-api",
        tag="1.0.0",
        layers=(
            ImageLayer("FROM", "python:3.13-slim"),
            ImageLayer("WORKDIR", "/app"),
            ImageLayer("COPY", "requirements.txt"),
            ImageLayer("RUN", "pip install --no-cache-dir"),
            ImageLayer("COPY", "application.py"),
        ),
        entrypoint=("python", "application.py"),
        exposed_ports=(8000,),
        user="app",
        vulnerabilities=0,
    )


def demonstrate_containerization():
    print("\n=== CONTAINERIZATION SIMULATOR ===")

    registry = ImageRegistry()
    runtime = ContainerRuntime(
        total_memory_mb=4096,
        total_cpu=8.0,
    )

    image = build_application_image()
    registry.push(image)

    pulled_image = registry.pull("inventory-api:1.0.0")

    print("\nImage information")
    print("Reference:", pulled_image.reference)
    print("Digest:", pulled_image.digest)
    print("Size:", pulled_image.size_bytes, "bytes")
    print("Layers:", len(pulled_image.layers))

    config = ContainerConfig(
        environment={
            "APP_ENV": "production",
            "LOG_LEVEL": "INFO",
        },
        port_mappings={
            8000: 8080,
        },
        resources=ResourceLimits(
            cpu_cores=1.5,
            memory_mb=512,
            pids_limit=100,
        ),
        restart_policy=RestartPolicy.ON_FAILURE,
        read_only_rootfs=True,
    )

    container = runtime.create(pulled_image, config)

    runtime.start(container.container_id)
    container.mark_healthy()

    print("\nRunning containers")
    print(json.dumps(runtime.list_containers(), indent=2))

    # Demonstrate resource isolation through independent allocation limits.
    print("\nResource allocation")
    print("CPU:", container.config.resources.cpu_cores)
    print("Memory:", container.config.resources.memory_mb, "MB")
    print("Process limit:", container.config.resources.pids_limit)

    # Demonstrate failure and restart behavior.
    container.fail("Simulated application process failure")

    restarted = runtime.restart_failed(container.container_id)
    print("\nRestart performed:", restarted)

    container.mark_healthy()

    # Demonstrate isolation policy enforcement.
    try:
        insecure_config = ContainerConfig(
            privileged=True,
            run_as_root=True,
        )
        runtime.create(pulled_image, insecure_config)
    except SecurityError as exc:
        print("\nSecurity policy rejected configuration:", exc)

    # Demonstrate validation failure.
    try:
        invalid_config = ContainerConfig(
            port_mappings={9000: 8080},
        )
        invalid_config.validate(pulled_image)
    except ValidationError as exc:
        print("Configuration rejected:", exc)

    # Demonstrate invalid lifecycle operation.
    try:
        container.start()
    except StateError as exc:
        print("Invalid lifecycle operation:", exc)

    runtime.export_state("container-state.json")
    print("\nOperational metadata exported to container-state.json")

    container.stop()
    container.remove()

    print("\nFinal container state:", container.state.value)


def run_tests():
    image = build_application_image()

    assert image.reference == "inventory-api:1.0.0"
    assert len(image.layers) == 5
    assert len(image.digest) == 64

    runtime = ContainerRuntime(1024, 4.0)

    config = ContainerConfig(
        resources=ResourceLimits(1.0, 128, 50),
    )

    container = runtime.create(image, config)
    runtime.start(container.container_id)

    assert container.state == ContainerState.RUNNING

    container.stop()
    container.remove()

    assert container.state == ContainerState.REMOVED

    try:
        container.start()
        raise AssertionError("Removed container should not restart.")
    except StateError:
        pass

    print("\nAll tests passed.")


if __name__ == "__main__":
    demonstrate_containerization()
    run_tests()
