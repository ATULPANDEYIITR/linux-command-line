#!/usr/bin/env python3
"""
Docker Container Lifecycle and Management
==========================================
Demonstrates:
- Container creation, execution, inspection, stopping and removal
- Docker image management
- Environment variables
- Container networking
- Persistent volumes and bind mounts
- Container logs and health checks
- Resource limits
- Docker CLI automation using subprocess
- Validation, error handling and security controls

Requirements:
- Python 3.10+
- Docker Engine or Docker Desktop
- Docker CLI available in PATH

Run:
    python docker_container_manager.py
    python docker_container_manager.py --demo
    python docker_container_manager.py --list
    python docker_container_manager.py --cleanup
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("docker-manager")


class DockerError(Exception):
    """Base exception for Docker management failures."""


class DockerUnavailableError(DockerError):
    """Docker CLI or daemon is unavailable."""


class ContainerNotFoundError(DockerError):
    """Requested container does not exist."""


class ValidationError(DockerError):
    """Invalid container configuration."""


class ContainerState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"
    REMOVING = "removing"


@dataclass(frozen=True)
class PortMapping:
    container_port: int
    host_port: int
    protocol: str = "tcp"

    def validate(self) -> None:
        if not 1 <= self.container_port <= 65535:
            raise ValidationError("Invalid container port.")

        if not 1 <= self.host_port <= 65535:
            raise ValidationError("Invalid host port.")

        if self.protocol not in {"tcp", "udp"}:
            raise ValidationError("Protocol must be tcp or udp.")


@dataclass
class ContainerConfig:
    name: str
    image: str
    command: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    ports: list[PortMapping] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    network: str | None = None
    memory: str | None = None
    cpu_limit: float | None = None
    restart_policy: str = "no"
    detach: bool = True
    auto_remove: bool = False

    def validate(self) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", self.name):
            raise ValidationError("Invalid container name.")

        if not self.image or self.image.startswith("-"):
            raise ValidationError("Invalid image reference.")

        if self.restart_policy not in {
            "no", "always", "unless-stopped", "on-failure"
        }:
            raise ValidationError("Unsupported restart policy.")

        if self.cpu_limit is not None and self.cpu_limit <= 0:
            raise ValidationError("CPU limit must be positive.")

        for key, value in self.environment.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValidationError(f"Invalid environment key: {key}")

            if "\x00" in value:
                raise ValidationError("Environment values cannot contain NUL.")

        for port in self.ports:
            port.validate()

        if len({p.host_port for p in self.ports}) != len(self.ports):
            raise ValidationError("Duplicate host ports.")

        for volume in self.volumes:
            if not volume or "\x00" in volume:
                raise ValidationError("Invalid volume specification.")


class DockerClient:
    """Safe wrapper around the Docker CLI."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.executable = shutil.which("docker")

        if self.executable is None:
            raise DockerUnavailableError(
                "Docker CLI was not found in PATH."
            )

        self._check_daemon()

    def execute(
        self,
        arguments: list[str],
        timeout: int | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not arguments:
            raise ValidationError("Docker command cannot be empty.")

        if any("\x00" in argument for argument in arguments):
            raise ValidationError("Invalid command argument.")

        command = [self.executable, *arguments]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerError("Docker command timed out.") from exc
        except OSError as exc:
            raise DockerUnavailableError(str(exc)) from exc

        if check and result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise DockerError(
                f"Docker command failed ({result.returncode}): {message}"
            )

        return result

    def _check_daemon(self) -> None:
        result = self.execute(
            ["info", "--format", "{{.ServerVersion}}"],
            timeout=self.timeout,
            check=False,
        )

        if result.returncode != 0:
            raise DockerUnavailableError(
                "Docker daemon is not responding. Start Docker Desktop "
                "or the Docker service."
            )

        logger.info("Docker Engine version: %s", result.stdout.strip())

    def version(self) -> dict[str, Any]:
        result = self.execute(["version", "--format", "{{json .}}"])
        return json.loads(result.stdout)

    def pull_image(self, image: str) -> None:
        if not image or image.startswith("-"):
            raise ValidationError("Invalid image name.")

        logger.info("Pulling image: %s", image)
        self.execute(["pull", image], timeout=300)

    def image_exists(self, image: str) -> bool:
        result = self.execute(
            ["image", "inspect", image],
            check=False,
        )
        return result.returncode == 0

    def create_container(self, config: ContainerConfig) -> str:
        config.validate()

        arguments = [
            "create",
            "--name", config.name,
            "--restart", config.restart_policy,
        ]

        if config.memory:
            arguments.extend(["--memory", config.memory])

        if config.cpu_limit is not None:
            arguments.extend(["--cpus", str(config.cpu_limit)])

        for mapping in config.ports:
            arguments.extend([
                "-p",
                f"{mapping.host_port}:{mapping.container_port}/{mapping.protocol}",
            ])

        for key, value in config.environment.items():
            arguments.extend(["-e", f"{key}={value}"])

        for volume in config.volumes:
            arguments.extend(["-v", volume])

        if config.network:
            arguments.extend(["--network", config.network])

        arguments.append(config.image)
        arguments.extend(config.command)

        result = self.execute(arguments)
        container_id = result.stdout.strip()

        logger.info(
            "Created container %s: %s",
            config.name,
            container_id[:12],
        )

        return container_id

    def run_container(self, config: ContainerConfig) -> str:
        config.validate()

        arguments = [
            "run",
            "--name", config.name,
            "--restart", config.restart_policy,
        ]

        if config.detach:
            arguments.append("-d")

        if config.auto_remove:
            arguments.append("--rm")

        if config.memory:
            arguments.extend(["--memory", config.memory])

        if config.cpu_limit is not None:
            arguments.extend(["--cpus", str(config.cpu_limit)])

        for mapping in config.ports:
            arguments.extend([
                "-p",
                f"{mapping.host_port}:{mapping.container_port}/{mapping.protocol}",
            ])

        for key, value in config.environment.items():
            arguments.extend(["-e", f"{key}={value}"])

        for volume in config.volumes:
            arguments.extend(["-v", volume])

        if config.network:
            arguments.extend(["--network", config.network])

        arguments.append(config.image)
        arguments.extend(config.command)

        result = self.execute(arguments, timeout=120)

        container_id = result.stdout.strip()

        logger.info(
            "Started container %s: %s",
            config.name,
            container_id[:12],
        )

        return container_id

    def start(self, name: str) -> None:
        self.execute(["start", name])
        logger.info("Started %s", name)

    def stop(self, name: str, timeout: int = 10) -> None:
        self.execute(["stop", "--time", str(timeout), name])
        logger.info("Stopped %s", name)

    def restart(self, name: str) -> None:
        self.execute(["restart", name])
        logger.info("Restarted %s", name)

    def pause(self, name: str) -> None:
        self.execute(["pause", name])

    def unpause(self, name: str) -> None:
        self.execute(["unpause", name])

    def remove(self, name: str, force: bool = False) -> None:
        arguments = ["rm"]

        if force:
            arguments.append("-f")

        arguments.append(name)
        self.execute(arguments)

        logger.info("Removed container %s", name)

    def inspect(self, name: str) -> dict[str, Any]:
        result = self.execute(["inspect", name])
        data = json.loads(result.stdout)

        if not data:
            raise ContainerNotFoundError(name)

        return data[0]

    def list_containers(self, all_containers: bool = True) -> list[dict]:
        arguments = ["ps", "--format", "{{json .}}"]

        if all_containers:
            arguments.append("-a")

        result = self.execute(arguments)

        containers = []

        for line in result.stdout.splitlines():
            if line.strip():
                containers.append(json.loads(line))

        return containers

    def logs(self, name: str, tail: int = 100) -> str:
        if not 1 <= tail <= 10000:
            raise ValidationError("Log tail must be between 1 and 10000.")

        result = self.execute([
            "logs",
            "--tail",
            str(tail),
            name,
        ])

        return result.stdout + result.stderr

    def create_network(self, name: str, driver: str = "bridge") -> None:
        if driver not in {"bridge", "overlay", "macvlan"}:
            raise ValidationError("Unsupported network driver.")

        self.execute(["network", "create", "--driver", driver, name])

    def inspect_network(self, name: str) -> dict:
        result = self.execute(["network", "inspect", name])
        return json.loads(result.stdout)[0]

    def create_volume(self, name: str) -> None:
        self.execute(["volume", "create", name])

    def inspect_volume(self, name: str) -> dict:
        result = self.execute(["volume", "inspect", name])
        return json.loads(result.stdout)[0]

    def health_status(self, name: str) -> str:
        data = self.inspect(name)

        return data.get("State", {}).get(
            "Health", {}
        ).get("Status", "not-configured")

    def container_environment(self, name: str) -> list[str]:
        data = self.inspect(name)

        # Environment values may contain secrets. Avoid logging them.
        return data.get("Config", {}).get("Env", [])

    def container_stats(self, name: str) -> dict:
        result = self.execute([
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            name,
        ])

        return json.loads(result.stdout)


class ContainerManager:
    """High-level operational workflow."""

    def __init__(self, client: DockerClient):
        self.client = client

    def deploy_web_container(self) -> str:
        image = "nginx:alpine"

        if not self.client.image_exists(image):
            self.client.pull_image(image)

        config = ContainerConfig(
            name="learning-nginx",
            image=image,
            ports=[
                PortMapping(
                    container_port=80,
                    host_port=8088,
                )
            ],
            environment={
                "APP_ENV": "development",
                "APP_PORT": "80",
            },
            memory="128m",
            cpu_limit=0.5,
            restart_policy="unless-stopped",
        )

        existing = self.client.execute(
            ["inspect", config.name],
            check=False,
        )

        if existing.returncode == 0:
            raise ValidationError(
                f"Container {config.name} already exists. "
                "Inspect or remove it before deploying again."
            )

        return self.client.run_container(config)

    def print_inventory(self) -> None:
        containers = self.client.list_containers()

        print("\nDOCKER CONTAINER INVENTORY")
        print("-" * 90)

        if not containers:
            print("No containers found.")
            return

        for container in containers:
            print(
                f"Name: {container.get('Names')}\n"
                f"ID: {container.get('ID')}\n"
                f"Image: {container.get('Image')}\n"
                f"Status: {container.get('Status')}\n"
                f"Ports: {container.get('Ports')}\n"
            )

    def demonstrate_lifecycle(self) -> None:
        name = "learning-nginx"

        self.deploy_web_container()

        print("\nContainer created and started.")

        details = self.client.inspect(name)

        print("Container ID:", details["Id"][:12])
        print("Image:", details["Config"]["Image"])
        print("State:", details["State"]["Status"])

        print("\nPausing container...")
        self.client.pause(name)

        print("Unpausing container...")
        self.client.unpause(name)

        print("\nRestarting container...")
        self.client.restart(name)

        print("\nContainer statistics:")
        print(json.dumps(
            self.client.container_stats(name),
            indent=2,
        ))

        print("\nContainer logs:")
        print(self.client.logs(name, tail=10))

        print("\nStopping container...")
        self.client.stop(name)

        print("Container lifecycle demonstration completed.")

    def cleanup_demo(self) -> None:
        result = self.client.execute(
            ["inspect", "learning-nginx"],
            check=False,
        )

        if result.returncode == 0:
            self.client.remove("learning-nginx", force=True)
        else:
            print("Demo container does not exist.")


def validate_environment_security() -> None:
    """Check common environment-variable handling risks."""

    dangerous_names = {
        "DOCKER_HOST",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    }

    for key in dangerous_names:
        if key in os.environ:
            logger.warning(
                "Docker connection variable %s is configured.",
                key,
            )

    if os.name != "nt":
        docker_socket = Path("/var/run/docker.sock")

        if docker_socket.exists():
            logger.info("Docker socket detected.")

            if os.access(docker_socket, os.W_OK):
                logger.warning(
                    "Current process can write to the Docker socket. "
                    "This is a highly privileged capability."
                )


def run_assertions() -> None:
    """Test configuration validation without contacting Docker."""

    config = ContainerConfig(
        name="test-container",
        image="nginx:alpine",
        environment={"APP_ENV": "test"},
        ports=[PortMapping(80, 8080)],
    )

    config.validate()

    invalid = ContainerConfig(
        name="invalid container",
        image="nginx:alpine",
    )

    try:
        invalid.validate()
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid container name was accepted.")

    try:
        PortMapping(70000, 8080).validate()
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid port was accepted.")

    print("Configuration validation tests passed.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Docker container lifecycle management."
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a complete Nginx container lifecycle demonstration.",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all containers.",
    )

    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove the demonstration container.",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run local validation tests.",
    )

    args = parser.parse_args()

    if args.test:
        run_assertions()
        return 0

    try:
        validate_environment_security()

        client = DockerClient()
        manager = ContainerManager(client)

        if args.list:
            manager.print_inventory()
        elif args.cleanup:
            manager.cleanup_demo()
        elif args.demo:
            manager.demonstrate_lifecycle()
        else:
            print("Docker Engine:", client.execute(
                ["version", "--format", "{{.Server.Version}}"]
            ).stdout.strip())

            manager.print_inventory()

            print(
                "\nUse --demo, --list, --cleanup or --test "
                "to perform an operation."
            )

    except DockerUnavailableError as exc:
        logger.error("Docker unavailable: %s", exc)
        return 2

    except ValidationError as exc:
        logger.error("Validation error: %s", exc)
        return 3

    except DockerError as exc:
        logger.error("Docker operation failed: %s", exc)
        return 4

    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
