#!/usr/bin/env python3
"""
Docker Fundamentals: Architecture, Images, Containers, Registries and Commands.

A self-contained Docker learning laboratory featuring:
- Docker architecture and component modeling
- Image layers and immutable image references
- Container lifecycle and state transitions
- Registry authentication and image distribution
- Port and volume configuration
- Resource constraints
- Docker CLI integration
- JSON inventory persistence
- Validation, error handling and automated tests

Requires Python 3.10+.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("docker_fundamentals")


# ============================================================
# 1. DOMAIN ENUMERATIONS
# ============================================================

class ContainerState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"


class ImageSource(str, Enum):
    LOCAL = "local"
    REGISTRY = "registry"
    BUILT = "built"


class DockerComponent(str, Enum):
    CLIENT = "docker_cli"
    DAEMON = "dockerd"
    CONTAINERD = "containerd"
    RUNTIME = "runc"
    REGISTRY = "registry"
    BUILD_ENGINE = "buildkit"


# ============================================================
# 2. VALIDATION UTILITIES
# ============================================================

def validate_name(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")

    if len(value) > 128:
        raise ValueError(f"{field_name} exceeds 128 characters")

    return value.strip()


def validate_image_reference(reference: str) -> str:
    reference = validate_name(reference, "Image reference")

    pattern = (
        r"^(?:[a-zA-Z0-9.-]+(?::\d+)?/)?"
        r"[a-z0-9]+(?:[._-][a-z0-9]+)*"
        r"(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*"
        r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?"
        r"(?:@sha256:[a-fA-F0-9]{64})?$"
    )

    if not re.fullmatch(pattern, reference):
        raise ValueError(f"Invalid image reference: {reference}")

    return reference


def validate_port(port: int) -> None:
    if not isinstance(port, int) or isinstance(port, bool):
        raise ValueError("Port must be an integer")

    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")


# ============================================================
# 3. DOCKER ARCHITECTURE
# ============================================================

@dataclass(frozen=True)
class ArchitectureComponent:
    name: DockerComponent
    responsibility: str


class DockerArchitecture:
    COMPONENTS = [
        ArchitectureComponent(
            DockerComponent.CLIENT,
            "Accepts user commands and communicates with the Docker API."
        ),
        ArchitectureComponent(
            DockerComponent.DAEMON,
            "Manages images, containers, networks and volumes."
        ),
        ArchitectureComponent(
            DockerComponent.CONTAINERD,
            "Manages container lifecycle and runtime operations."
        ),
        ArchitectureComponent(
            DockerComponent.RUNTIME,
            "Creates and starts containers using operating-system isolation."
        ),
        ArchitectureComponent(
            DockerComponent.REGISTRY,
            "Stores and distributes container images."
        ),
        ArchitectureComponent(
            DockerComponent.BUILD_ENGINE,
            "Builds images from Dockerfiles and build contexts."
        )
    ]

    @classmethod
    def display(cls) -> None:
        print("\nDOCKER ARCHITECTURE")

        for component in cls.COMPONENTS:
            print(f"\n{component.name.value}")
            print(f"  {component.responsibility}")

        print("\nTypical command flow:")
        print("Docker CLI -> Docker API -> dockerd")
        print("dockerd -> containerd -> runc")
        print("Image operations -> Registry / BuildKit")


# ============================================================
# 4. IMAGE MODEL
# ============================================================

@dataclass
class ImageLayer:
    layer_id: str
    instruction: str
    size_mb: float

    def __post_init__(self) -> None:
        validate_name(self.layer_id, "Layer ID")

        if self.size_mb < 0:
            raise ValueError("Layer size cannot be negative")


@dataclass
class DockerImage:
    repository: str
    tag: str
    layers: list[ImageLayer]
    source: ImageSource = ImageSource.LOCAL
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        validate_image_reference(f"{self.repository}:{self.tag}")

        if not self.layers:
            raise ValueError("An image must contain at least one layer")

        identifiers = [layer.layer_id for layer in self.layers]

        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate image layer identifiers")

    @property
    def reference(self) -> str:
        return f"{self.repository}:{self.tag}"

    @property
    def size_mb(self) -> float:
        return round(sum(layer.size_mb for layer in self.layers), 2)

    @property
    def layer_count(self) -> int:
        return len(self.layers)


class ImageStore:
    def __init__(self) -> None:
        self.images: dict[str, DockerImage] = {}

    def add(self, image: DockerImage) -> None:
        self.images[image.reference] = image

    def get(self, reference: str) -> DockerImage:
        try:
            return self.images[reference]
        except KeyError as exc:
            raise LookupError(
                f"Image not found locally: {reference}"
            ) from exc

    def remove(self, reference: str) -> None:
        if reference not in self.images:
            raise LookupError(f"Image not found: {reference}")

        del self.images[reference]

    def list_images(self) -> list[DockerImage]:
        return sorted(
            self.images.values(),
            key=lambda image: image.reference
        )


# ============================================================
# 5. REGISTRY MODEL
# ============================================================

@dataclass
class Registry:
    hostname: str
    images: dict[str, DockerImage] = field(default_factory=dict)
    authenticated_users: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        validate_name(self.hostname, "Registry hostname")

    def login(self, username: str) -> None:
        self.authenticated_users.add(
            validate_name(username, "Username")
        )

    def push(
        self,
        image: DockerImage,
        username: str
    ) -> str:
        if username not in self.authenticated_users:
            raise PermissionError("Registry authentication required")

        remote_reference = (
            f"{self.hostname}/{image.reference}"
        )

        self.images[remote_reference] = image
        return remote_reference

    def pull(self, reference: str) -> DockerImage:
        if reference not in self.images:
            raise LookupError(
                f"Image does not exist in registry: {reference}"
            )

        return self.images[reference]


# ============================================================
# 6. CONTAINER MODEL
# ============================================================

@dataclass
class Container:
    container_id: str
    name: str
    image: DockerImage
    environment: dict[str, str] = field(default_factory=dict)
    ports: dict[int, int] = field(default_factory=dict)
    volumes: dict[str, str] = field(default_factory=dict)
    state: ContainerState = ContainerState.CREATED
    cpu_limit: float = 1.0
    memory_limit_mb: int = 512
    restart_count: int = 0

    def __post_init__(self) -> None:
        validate_name(self.name, "Container name")

        if self.cpu_limit <= 0:
            raise ValueError("CPU limit must be positive")

        if self.memory_limit_mb < 6:
            raise ValueError("Memory limit must be at least 6 MB")

        for host, container in self.ports.items():
            validate_port(host)
            validate_port(container)

        for key, value in self.environment.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError(f"Invalid environment variable: {key}")

            if "\x00" in value:
                raise ValueError("Environment values cannot contain NUL")

    def start(self) -> None:
        if self.state not in {
            ContainerState.CREATED,
            ContainerState.EXITED
        }:
            raise RuntimeError(
                f"Cannot start container in state {self.state.value}"
            )

        self.state = ContainerState.RUNNING

    def pause(self) -> None:
        if self.state != ContainerState.RUNNING:
            raise RuntimeError("Only running containers can be paused")

        self.state = ContainerState.PAUSED

    def unpause(self) -> None:
        if self.state != ContainerState.PAUSED:
            raise RuntimeError("Container is not paused")

        self.state = ContainerState.RUNNING

    def stop(self) -> None:
        if self.state not in {
            ContainerState.RUNNING,
            ContainerState.PAUSED
        }:
            raise RuntimeError("Container cannot be stopped")

        self.state = ContainerState.EXITED

    def restart(self) -> None:
        if self.state == ContainerState.DEAD:
            raise RuntimeError("Dead containers cannot be restarted")

        self.restart_count += 1
        self.state = ContainerState.RUNNING

    def remove(self, force: bool = False) -> None:
        if self.state == ContainerState.RUNNING and not force:
            raise RuntimeError(
                "Running container requires force removal or stopping"
            )

        self.state = ContainerState.DEAD


# ============================================================
# 7. DOCKER ENGINE SIMULATOR
# ============================================================

class DockerEngine:
    def __init__(self) -> None:
        self.image_store = ImageStore()
        self.containers: dict[str, Container] = {}
        self.container_names: set[str] = set()

    def pull_image(self, registry: Registry, reference: str) -> DockerImage:
        image = registry.pull(reference)
        self.image_store.add(image)
        return image

    def create_container(
        self,
        name: str,
        image_reference: str,
        **configuration: Any
    ) -> Container:
        name = validate_name(name, "Container name")

        if name in self.container_names:
            raise ValueError(f"Container name already exists: {name}")

        image = self.image_store.get(image_reference)

        container = Container(
            container_id=f"ctr-{len(self.containers) + 1:04d}",
            name=name,
            image=image,
            **configuration
        )

        self.containers[container.container_id] = container
        self.container_names.add(name)

        return container

    def get_container(self, name: str) -> Container:
        for container in self.containers.values():
            if container.name == name:
                return container

        raise LookupError(f"Container not found: {name}")

    def remove_container(
        self,
        name: str,
        force: bool = False
    ) -> None:
        container = self.get_container(name)
        container.remove(force)

        del self.containers[container.container_id]
        self.container_names.remove(name)

    def list_containers(
        self,
        include_stopped: bool = True
    ) -> list[Container]:
        return [
            container
            for container in self.containers.values()
            if include_stopped
            or container.state == ContainerState.RUNNING
        ]

    def inspect(self, name: str) -> dict[str, Any]:
        container = self.get_container(name)

        return {
            "id": container.container_id,
            "name": container.name,
            "image": container.image.reference,
            "state": container.state.value,
            "ports": container.ports,
            "volumes": container.volumes,
            "cpu_limit": container.cpu_limit,
            "memory_limit_mb": container.memory_limit_mb,
            "restart_count": container.restart_count
        }


# ============================================================
# 8. DOCKER CLI INTEGRATION
# ============================================================

class DockerCLI:
    def __init__(self, executable: str = "docker") -> None:
        self.executable = executable

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def execute(
        self,
        arguments: list[str],
        timeout: int = 15
    ) -> str:
        if not self.available():
            raise EnvironmentError("Docker CLI is not installed")

        if not arguments:
            raise ValueError("A Docker command is required")

        if any(not isinstance(arg, str) for arg in arguments):
            raise ValueError("All command arguments must be strings")

        try:
            result = subprocess.run(
                [self.executable, *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("Docker command timed out") from exc

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or f"Docker exited with code {result.returncode}"
            )

        return result.stdout.strip()

    def version(self) -> str:
        return self.execute(["version", "--format", "{{.Client.Version}}"])

    def list_containers(self) -> str:
        return self.execute(["ps", "-a"])

    def list_images(self) -> str:
        return self.execute(["images"])

    def daemon_information(self) -> str:
        return self.execute(["info", "--format", "{{.ServerVersion}}"])


# ============================================================
# 9. INVENTORY PERSISTENCE
# ============================================================

class InventoryStorage:
    @staticmethod
    def save(engine: DockerEngine, path: Path) -> None:
        data = {
            "images": [
                {
                    "reference": image.reference,
                    "size_mb": image.size_mb,
                    "layer_count": image.layer_count
                }
                for image in engine.image_store.list_images()
            ],
            "containers": [
                engine.inspect(container.name)
                for container in engine.containers.values()
            ]
        }

        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    @staticmethod
    def load(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(path)

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid inventory format")

        if not isinstance(data.get("images"), list):
            raise ValueError("Invalid image inventory")

        if not isinstance(data.get("containers"), list):
            raise ValueError("Invalid container inventory")

        return data


# ============================================================
# 10. PRACTICAL WORKFLOW
# ============================================================

def create_demo_environment() -> DockerEngine:
    engine = DockerEngine()

    image = DockerImage(
        repository="nginx",
        tag="1.27",
        source=ImageSource.REGISTRY,
        layers=[
            ImageLayer("layer-001", "Base operating system", 28.5),
            ImageLayer("layer-002", "Install Nginx", 12.4),
            ImageLayer("layer-003", "Application configuration", 2.1)
        ]
    )

    engine.image_store.add(image)

    container = engine.create_container(
        "web-server",
        "nginx:1.27",
        environment={
            "APP_ENV": "development",
            "LOG_LEVEL": "info"
        },
        ports={8080: 80},
        volumes={"/host/site": "/usr/share/nginx/html"},
        cpu_limit=1.5,
        memory_limit_mb=512
    )

    container.start()

    return engine


def demonstrate_workflow() -> None:
    DockerArchitecture.display()

    engine = create_demo_environment()

    print("\nLOCAL IMAGES")

    for image in engine.image_store.list_images():
        print(
            f"{image.reference} | "
            f"{image.layer_count} layers | "
            f"{image.size_mb} MB"
        )

    print("\nCONTAINER INVENTORY")

    for container in engine.list_containers():
        print(
            container.name,
            container.state.value,
            container.image.reference
        )

    container = engine.get_container("web-server")

    print("\nCONTAINER INSPECTION")
    print(json.dumps(engine.inspect("web-server"), indent=2))

    container.pause()
    print("\nAfter pause:", container.state.value)

    container.unpause()
    print("After unpause:", container.state.value)

    container.stop()
    print("After stop:", container.state.value)

    container.start()
    print("After start:", container.state.value)

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "docker-inventory.json"

        InventoryStorage.save(engine, path)
        inventory = InventoryStorage.load(path)

        print("\nPERSISTED INVENTORY")
        print(json.dumps(inventory, indent=2))


# ============================================================
# 11. REGISTRY DEMONSTRATION
# ============================================================

def demonstrate_registry() -> None:
    registry = Registry("registry.example.com")

    image = DockerImage(
        repository="training/web-app",
        tag="1.0.0",
        source=ImageSource.BUILT,
        layers=[
            ImageLayer("base", "FROM python:3.13-slim", 45),
            ImageLayer("dependencies", "Install dependencies", 18),
            ImageLayer("application", "COPY application files", 4)
        ]
    )

    registry.login("developer")

    remote = registry.push(image, "developer")
    print("\nPUSHED IMAGE:", remote)

    downloaded = registry.pull(remote)
    print("PULLED IMAGE:", downloaded.reference)

    try:
        registry.push(image, "unauthorized-user")
    except PermissionError as error:
        print("EXPECTED SECURITY FAILURE:", error)


# ============================================================
# 12. AUTOMATED TESTS
# ============================================================

def run_tests() -> None:
    engine = create_demo_environment()

    container = engine.get_container("web-server")

    assert container.state == ContainerState.RUNNING

    container.pause()
    assert container.state == ContainerState.PAUSED

    container.unpause()
    assert container.state == ContainerState.RUNNING

    container.stop()
    assert container.state == ContainerState.EXITED

    container.start()
    assert container.state == ContainerState.RUNNING

    try:
        container.pause()
        container.pause()
        raise AssertionError("Expected invalid state transition")
    except RuntimeError:
        pass

    try:
        validate_port(70000)
        raise AssertionError("Expected invalid port")
    except ValueError:
        pass

    registry = Registry("registry.example.com")

    try:
        registry.push(
            engine.image_store.get("nginx:1.27"),
            "unauthorized"
        )
        raise AssertionError("Expected authentication failure")
    except PermissionError:
        pass

    try:
        engine.create_container("web-server", "nginx:1.27")
        raise AssertionError("Expected duplicate container name")
    except ValueError:
        pass

    print("\nAll automated tests passed.")


# ============================================================
# 13. REAL DOCKER ENVIRONMENT INSPECTION
# ============================================================

def inspect_real_docker() -> None:
    cli = DockerCLI()

    if not cli.available():
        print("\nDocker CLI not found.")
        print("Install Docker Desktop or Docker Engine.")
        return

    print("\nDOCKER CLIENT VERSION")

    try:
        print(cli.version())

        print("\nDOCKER SERVER VERSION")
        print(cli.daemon_information())

        print("\nLOCAL IMAGES")
        print(cli.list_images())

        print("\nCONTAINERS")
        print(cli.list_containers())

    except (RuntimeError, TimeoutError, EnvironmentError) as error:
        logger.error("Docker inspection failed: %s", error)


# ============================================================
# 14. ENTRY POINT
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Docker Fundamentals Learning Laboratory"
    )

    parser.add_argument(
        "--real",
        action="store_true",
        help="Inspect the installed Docker environment"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Execute automated tests"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the simulated Docker workflow"
    )

    arguments = parser.parse_args()

    if arguments.real:
        inspect_real_docker()

    if arguments.demo or not (
        arguments.real or arguments.test
    ):
        demonstrate_workflow()
        demonstrate_registry()

    if arguments.test:
        run_tests()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, LookupError) as error:
        logger.error("Execution failed: %s", error)
        sys.exit(1)
