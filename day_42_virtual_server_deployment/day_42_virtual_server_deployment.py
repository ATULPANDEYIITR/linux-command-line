#!/usr/bin/env python3
"""Virtual server deployment and instance lifecycle management.

This standard-library-only lab models virtual machines, deployment validation,
cloud-init configuration, health checks, lifecycle transitions, cost estimation,
inventory persistence, and operational failure recovery.

Run:
    python virtual_server_deployment.py
    python virtual_server_deployment.py --inventory vm_inventory.json

The program simulates cloud operations locally. It does not create real cloud
resources or store cloud credentials.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import tempfile
import unittest
import uuid

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("virtual-server-deployment")


def utc_now() -> str:
    """Return a timezone-aware timestamp suitable for audit records."""
    return datetime.now(timezone.utc).isoformat()


class DeploymentError(Exception):
    """Base exception for deployment and lifecycle failures."""


class ValidationError(DeploymentError):
    """Raised when a requested server configuration is invalid."""


class StateTransitionError(DeploymentError):
    """Raised when an operation is incompatible with the current state."""


class ProviderError(DeploymentError):
    """Raised when a simulated infrastructure operation fails."""


class InstanceState(str, Enum):
    REQUESTED = "requested"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    RESTARTING = "restarting"
    TERMINATED = "terminated"
    FAILED = "failed"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True)
class InstanceType:
    """Compute capacity and indicative hourly price."""

    name: str
    vcpus: int
    memory_gib: float
    hourly_rate: float


INSTANCE_TYPES = {
    "small": InstanceType("small", 2, 4.0, 0.05),
    "medium": InstanceType("medium", 4, 16.0, 0.12),
    "large": InstanceType("large", 8, 32.0, 0.24),
}


@dataclass(frozen=True)
class NetworkConfiguration:
    subnet_id: str
    security_group_ids: tuple[str, ...]
    public_ip: bool = False
    allowed_ingress_ports: tuple[int, ...] = (22, 443)

    def validate(self, environment: Environment) -> None:
        if not re.fullmatch(r"subnet-[a-zA-Z0-9-]{3,40}", self.subnet_id):
            raise ValidationError("Invalid subnet identifier.")

        if not self.security_group_ids:
            raise ValidationError("At least one security group is required.")

        for group_id in self.security_group_ids:
            if not re.fullmatch(r"sg-[a-zA-Z0-9-]{3,40}", group_id):
                raise ValidationError(f"Invalid security group identifier: {group_id}")

        for port in self.allowed_ingress_ports:
            if not 1 <= port <= 65535:
                raise ValidationError(f"Invalid ingress port: {port}")

        if len(set(self.allowed_ingress_ports)) != len(self.allowed_ingress_ports):
            raise ValidationError("Ingress ports must not contain duplicates.")

        if environment == Environment.PRODUCTION and 22 in self.allowed_ingress_ports:
            logger.warning(
                "Production SSH ingress is configured. Restrict its source "
                "CIDRs and prefer managed session access."
            )


@dataclass(frozen=True)
class ServerSpecification:
    name: str
    instance_type: str
    image_id: str
    region: str
    environment: Environment
    network: NetworkConfiguration
    root_disk_gib: int = 30
    encrypted_disk: bool = True
    monitoring_enabled: bool = True
    startup_script: str = ""

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", self.name):
            raise ValidationError(
                "Server name must be 2-40 characters, lowercase, and "
                "contain only letters, digits, and internal hyphens."
            )

        if self.instance_type not in INSTANCE_TYPES:
            raise ValidationError(f"Unsupported instance type: {self.instance_type}")

        if not re.fullmatch(r"(?:img|ami)-[a-zA-Z0-9-]{3,40}", self.image_id):
            raise ValidationError("Image identifier must use an img- or ami- prefix.")

        if not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d+", self.region):
            raise ValidationError(f"Invalid region format: {self.region}")

        if not 8 <= self.root_disk_gib <= 16384:
            raise ValidationError("Root disk must be between 8 and 16384 GiB.")

        if self.environment == Environment.PRODUCTION:
            if not self.encrypted_disk:
                raise ValidationError("Production root disks must be encrypted.")
            if not self.monitoring_enabled:
                raise ValidationError("Production monitoring must be enabled.")

        if len(self.startup_script.encode("utf-8")) > 16_384:
            raise ValidationError("Startup script exceeds the 16 KiB lab limit.")

        self.network.validate(self.environment)


@dataclass
class AuditEvent:
    timestamp: str
    action: str
    previous_state: str
    new_state: str
    actor: str
    details: str = ""


@dataclass
class VirtualMachine:
    specification: ServerSpecification
    instance_id: str = field(
        default_factory=lambda: "vm-" + uuid.uuid4().hex[:12]
    )
    state: InstanceState = InstanceState.REQUESTED
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    private_ip: str | None = None
    public_ip: str | None = None
    health_status: str = "unknown"
    boot_count: int = 0
    audit_log: list[AuditEvent] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)

    def record_transition(
        self,
        action: str,
        new_state: InstanceState,
        actor: str,
        details: str = "",
    ) -> None:
        previous = self.state
        self.state = new_state
        self.updated_at = utc_now()
        self.audit_log.append(
            AuditEvent(
                timestamp=self.updated_at,
                action=action,
                previous_state=previous.value,
                new_state=new_state.value,
                actor=actor,
                details=details,
            )
        )


class LifecycleManager:
    """Enforce allowed lifecycle transitions independently of provider APIs."""

    ALLOWED_TRANSITIONS = {
        InstanceState.REQUESTED: {InstanceState.PROVISIONING, InstanceState.FAILED},
        InstanceState.PROVISIONING: {InstanceState.RUNNING, InstanceState.FAILED},
        InstanceState.RUNNING: {
            InstanceState.STOPPING,
            InstanceState.RESTARTING,
            InstanceState.TERMINATED,
            InstanceState.FAILED,
        },
        InstanceState.STOPPING: {InstanceState.STOPPED, InstanceState.FAILED},
        InstanceState.STOPPED: {
            InstanceState.PROVISIONING,
            InstanceState.TERMINATED,
            InstanceState.FAILED,
        },
        InstanceState.RESTARTING: {InstanceState.RUNNING, InstanceState.FAILED},
        InstanceState.FAILED: {
            InstanceState.PROVISIONING,
            InstanceState.TERMINATED,
        },
        InstanceState.TERMINATED: set(),
    }

    @classmethod
    def transition(
        cls,
        vm: VirtualMachine,
        target: InstanceState,
        action: str,
        actor: str = "deployment-controller",
        details: str = "",
    ) -> None:
        if target not in cls.ALLOWED_TRANSITIONS[vm.state]:
            raise StateTransitionError(
                f"Cannot transition {vm.instance_id} from "
                f"{vm.state.value} to {target.value}."
            )
        vm.record_transition(action, target, actor, details)


class SimulatedCloudProvider:
    """Deterministic provider simulator with injectable failures."""

    def __init__(self) -> None:
        self.fail_next_operation: str | None = None
        self.next_private_ip = 10

    def _maybe_fail(self, operation: str) -> None:
        if self.fail_next_operation == operation:
            self.fail_next_operation = None
            raise ProviderError(f"Simulated provider failure during {operation}.")

    def create_instance(self, vm: VirtualMachine) -> None:
        self._maybe_fail("create")
        vm.private_ip = f"10.20.0.{self.next_private_ip}"
        self.next_private_ip += 1
        vm.public_ip = (
            f"198.51.100.{self.next_private_ip}"
            if vm.specification.network.public_ip
            else None
        )
        vm.boot_count += 1

    def start_instance(self, vm: VirtualMachine) -> None:
        self._maybe_fail("start")
        if vm.private_ip is None:
            vm.private_ip = f"10.20.0.{self.next_private_ip}"
            self.next_private_ip += 1
        vm.boot_count += 1

    def stop_instance(self, vm: VirtualMachine) -> None:
        self._maybe_fail("stop")

    def restart_instance(self, vm: VirtualMachine) -> None:
        self._maybe_fail("restart")
        vm.boot_count += 1

    def terminate_instance(self, vm: VirtualMachine) -> None:
        self._maybe_fail("terminate")


class DeploymentService:
    """Coordinate validation, provider calls, transitions, and recovery."""

    def __init__(self, provider: SimulatedCloudProvider | None = None) -> None:
        self.provider = provider or SimulatedCloudProvider()
        self.inventory: dict[str, VirtualMachine] = {}
        self.names: dict[str, str] = {}

    def deploy(self, specification: ServerSpecification) -> VirtualMachine:
        specification.validate()

        if specification.name in self.names:
            raise ValidationError(
                f"An instance named {specification.name!r} already exists."
            )

        vm = VirtualMachine(specification=specification)
        self.inventory[vm.instance_id] = vm
        self.names[specification.name] = vm.instance_id

        LifecycleManager.transition(vm, InstanceState.PROVISIONING, "create")

        try:
            self.provider.create_instance(vm)
            LifecycleManager.transition(
                vm,
                InstanceState.RUNNING,
                "create",
                details="Provider accepted configuration and assigned addresses.",
            )
            vm.health_status = "healthy"
            return vm
        except ProviderError as exc:
            LifecycleManager.transition(
                vm, InstanceState.FAILED, "create", details=str(exc)
            )
            vm.health_status = "unhealthy"
            raise

    def get(self, instance_id: str) -> VirtualMachine:
        try:
            return self.inventory[instance_id]
        except KeyError as exc:
            raise DeploymentError(f"Unknown instance: {instance_id}") from exc

    def stop(self, instance_id: str) -> VirtualMachine:
        vm = self.get(instance_id)
        if vm.state != InstanceState.RUNNING:
            raise StateTransitionError("Only running instances can be stopped.")

        LifecycleManager.transition(vm, InstanceState.STOPPING, "stop")
        try:
            self.provider.stop_instance(vm)
            LifecycleManager.transition(vm, InstanceState.STOPPED, "stop")
            vm.health_status = "not-running"
            return vm
        except ProviderError as exc:
            LifecycleManager.transition(
                vm, InstanceState.FAILED, "stop", details=str(exc)
            )
            vm.health_status = "unhealthy"
            raise

    def start(self, instance_id: str) -> VirtualMachine:
        vm = self.get(instance_id)
        if vm.state not in {InstanceState.STOPPED, InstanceState.FAILED}:
            raise StateTransitionError("Only stopped or failed instances can start.")

        LifecycleManager.transition(vm, InstanceState.PROVISIONING, "start")
        try:
            self.provider.start_instance(vm)
            LifecycleManager.transition(vm, InstanceState.RUNNING, "start")
            vm.health_status = "healthy"
            return vm
        except ProviderError as exc:
            LifecycleManager.transition(
                vm, InstanceState.FAILED, "start", details=str(exc)
            )
            vm.health_status = "unhealthy"
            raise

    def restart(self, instance_id: str) -> VirtualMachine:
        vm = self.get(instance_id)
        if vm.state != InstanceState.RUNNING:
            raise StateTransitionError("Only running instances can be restarted.")

        LifecycleManager.transition(vm, InstanceState.RESTARTING, "restart")
        try:
            self.provider.restart_instance(vm)
            LifecycleManager.transition(vm, InstanceState.RUNNING, "restart")
            vm.health_status = "healthy"
            return vm
        except ProviderError as exc:
            LifecycleManager.transition(
                vm, InstanceState.FAILED, "restart", details=str(exc)
            )
            vm.health_status = "unhealthy"
            raise

    def terminate(self, instance_id: str) -> VirtualMachine:
        vm = self.get(instance_id)
        if vm.state == InstanceState.TERMINATED:
            raise StateTransitionError("Instance is already terminated.")

        try:
            self.provider.terminate_instance(vm)
        except ProviderError as exc:
            if vm.state != InstanceState.FAILED:
                LifecycleManager.transition(
                    vm, InstanceState.FAILED, "terminate", details=str(exc)
                )
            raise

        LifecycleManager.transition(vm, InstanceState.TERMINATED, "terminate")
        vm.health_status = "terminated"
        vm.public_ip = None
        vm.private_ip = None
        return vm

    def list_instances(
        self, state: InstanceState | None = None
    ) -> list[VirtualMachine]:
        values = list(self.inventory.values())
        if state is not None:
            values = [vm for vm in values if vm.state == state]
        return sorted(values, key=lambda vm: vm.created_at)

    def estimate_monthly_compute_cost(
        self,
        instance_id: str,
        hours_per_month: float = 730.0,
    ) -> float:
        if not math.isfinite(hours_per_month) or not 0 <= hours_per_month <= 744:
            raise ValidationError("Monthly billable hours must be between 0 and 744.")

        vm = self.get(instance_id)
        rate = INSTANCE_TYPES[vm.specification.instance_type].hourly_rate

        # This is a compute-only estimate; disk, network, IP, and licensing
        # charges are excluded and stopped-instance billing varies by provider.
        billable_hours = 0.0 if vm.state == InstanceState.TERMINATED else hours_per_month
        return round(rate * billable_hours, 2)

    def save_inventory(self, path: Path) -> None:
        """Atomically persist inventory to avoid partially written JSON files."""
        payload = {
            "schema_version": 1,
            "saved_at": utc_now(),
            "instances": [self._serialize_vm(vm) for vm in self.inventory.values()],
        }
        path.parent.mkdir(parents=True, exist_ok=True)

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent, text=True
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _serialize_vm(vm: VirtualMachine) -> dict[str, Any]:
        spec = vm.specification
        return {
            "instance_id": vm.instance_id,
            "name": spec.name,
            "instance_type": spec.instance_type,
            "image_id": spec.image_id,
            "region": spec.region,
            "environment": spec.environment.value,
            "network": {
                "subnet_id": spec.network.subnet_id,
                "security_group_ids": list(spec.network.security_group_ids),
                "public_ip": spec.network.public_ip,
                "allowed_ingress_ports": list(
                    spec.network.allowed_ingress_ports
                ),
            },
            "root_disk_gib": spec.root_disk_gib,
            "encrypted_disk": spec.encrypted_disk,
            "monitoring_enabled": spec.monitoring_enabled,
            "state": vm.state.value,
            "created_at": vm.created_at,
            "updated_at": vm.updated_at,
            "private_ip": vm.private_ip,
            "public_ip": vm.public_ip,
            "health_status": vm.health_status,
            "boot_count": vm.boot_count,
            "tags": vm.tags,
            "audit_log": [asdict(event) for event in vm.audit_log],
        }


def build_specification(
    name: str,
    environment: Environment = Environment.DEVELOPMENT,
    instance_type: str = "small",
    public_ip: bool = False,
) -> ServerSpecification:
    return ServerSpecification(
        name=name,
        instance_type=instance_type,
        image_id="img-linux2026",
        region="ap-south-1",
        environment=environment,
        network=NetworkConfiguration(
            subnet_id="subnet-prod001",
            security_group_ids=("sg-app001",),
            public_ip=public_ip,
            allowed_ingress_ports=(443,),
        ),
        root_disk_gib=40,
        encrypted_disk=True,
        monitoring_enabled=True,
        startup_script=(
            "#!/bin/sh\n"
            "set -eu\n"
            "mkdir -p /var/lib/example-service\n"
            "printf '%s\\n' 'deployment-initialized' "
            "> /var/lib/example-service/status\n"
        ),
    )


class DeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = SimulatedCloudProvider()
        self.service = DeploymentService(self.provider)

    def test_deploy_and_stop(self) -> None:
        vm = self.service.deploy(build_specification("test-api"))
        self.assertEqual(vm.state, InstanceState.RUNNING)
        self.service.stop(vm.instance_id)
        self.assertEqual(vm.state, InstanceState.STOPPED)

    def test_duplicate_names_are_rejected(self) -> None:
        self.service.deploy(build_specification("test-api"))
        with self.assertRaises(ValidationError):
            self.service.deploy(build_specification("test-api"))

    def test_invalid_transition_is_rejected(self) -> None:
        vm = self.service.deploy(build_specification("test-api"))
        self.service.terminate(vm.instance_id)
        with self.assertRaises(StateTransitionError):
            self.service.start(vm.instance_id)

    def test_provider_failure_records_failed_state(self) -> None:
        self.provider.fail_next_operation = "create"
        with self.assertRaises(ProviderError):
            self.service.deploy(build_specification("test-api"))
        vm = next(iter(self.service.inventory.values()))
        self.assertEqual(vm.state, InstanceState.FAILED)

    def test_production_encryption_is_required(self) -> None:
        spec = build_specification("secure-api", Environment.PRODUCTION)
        invalid = ServerSpecification(
            name=spec.name,
            instance_type=spec.instance_type,
            image_id=spec.image_id,
            region=spec.region,
            environment=spec.environment,
            network=spec.network,
            encrypted_disk=False,
            monitoring_enabled=True,
        )
        with self.assertRaises(ValidationError):
            invalid.validate()

    def test_inventory_round_trip_structure(self) -> None:
        vm = self.service.deploy(build_specification("persist-api"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            self.service.save_inventory(path)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["instances"][0]["instance_id"], vm.instance_id)
            self.assertEqual(saved["instances"][0]["state"], "running")


def run_demonstration() -> None:
    print("\nVirtual server deployment lab")
    print("=" * 42)

    service = DeploymentService()

    development = service.deploy(
        build_specification("catalog-api", Environment.DEVELOPMENT, "medium")
    )
    production = service.deploy(
        build_specification("payments-api", Environment.PRODUCTION, "large")
    )

    production.tags = {
        "team": "payments",
        "managed-by": "deployment-controller",
        "environment": "production",
    }

    for vm in service.list_instances():
        spec = vm.specification
        print(
            f"{spec.name:16} {vm.instance_id:16} "
            f"state={vm.state.value:12} "
            f"type={spec.instance_type:6} "
            f"private_ip={vm.private_ip:12} "
            f"public_ip={vm.public_ip or 'none':15} "
            f"monthly_compute_estimate="
            f"${service.estimate_monthly_compute_cost(vm.instance_id):.2f}"
        )

    service.stop(development.instance_id)
    service.start(development.instance_id)
    service.restart(production.instance_id)

    print("\nLifecycle audit for payments-api")
    for event in production.audit_log:
        print(
            f"{event.timestamp} {event.action:10} "
            f"{event.previous_state:12} -> {event.new_state:12} "
            f"{event.details}"
        )

    with tempfile.TemporaryDirectory() as directory:
        inventory_path = Path(directory) / "inventory.json"
        service.save_inventory(inventory_path)
        print(f"\nInventory persisted: {inventory_path.name}")
        print(f"Serialized bytes: {inventory_path.stat().st_size}")

    print("\nExecuting validation and lifecycle tests")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        help="Write the final simulated inventory to this JSON path.",
    )
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Run tests without the demonstration.",
    )
    args = parser.parse_args()

    if not args.test_only:
        run_demonstration()

    if args.inventory:
        service = DeploymentService()
        vm = service.deploy(build_specification("inventory-example"))
        service.save_inventory(args.inventory)
        print(
            f"Saved {vm.instance_id} to "
            f"{args.inventory.resolve()}"
        )


if __name__ == "__main__":
    main()
