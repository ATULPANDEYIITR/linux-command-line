#!/usr/bin/env python3
"""
Kubernetes Deployments and ReplicaSets Simulation

Models:
- Declarative deployment specifications
- Desired and observed replica counts
- ReplicaSet ownership and lifecycle
- Pod creation and termination
- Rolling updates
- MaxSurge and MaxUnavailable
- Readiness and availability
- Deployment revision history
- Rollback operations
- Scaling and reconciliation
- Failure handling and validation

Python 3.10+
Uses only the Python standard library.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("kubernetes-simulator")


class DeploymentError(Exception):
    pass


class ValidationError(DeploymentError):
    pass


class RevisionNotFoundError(DeploymentError):
    pass


class PodPhase(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    TERMINATING = "Terminating"
    TERMINATED = "Terminated"
    FAILED = "Failed"


class DeploymentPhase(str, Enum):
    PROGRESSING = "Progressing"
    AVAILABLE = "Available"
    DEGRADED = "Degraded"
    FAILED = "Failed"


class ReplicaSetPhase(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


@dataclass(frozen=True)
class ContainerSpec:
    name: str
    image: str
    port: int = 8080
    cpu_request: str = "100m"
    memory_request: str = "128Mi"

    def __post_init__(self):
        if not self.name.strip():
            raise ValidationError("Container name cannot be empty")

        if not self.image.strip():
            raise ValidationError("Container image cannot be empty")

        if not 1 <= self.port <= 65535:
            raise ValidationError("Invalid container port")


@dataclass(frozen=True)
class DeploymentSpec:
    name: str
    namespace: str
    replicas: int
    container: ContainerSpec
    max_surge: int = 1
    max_unavailable: int = 0
    min_ready_seconds: int = 0
    revision_history_limit: int = 5

    def __post_init__(self):
        if not self.name or not self.namespace:
            raise ValidationError(
                "Deployment name and namespace are required"
            )

        if self.replicas < 0:
            raise ValidationError("Replicas cannot be negative")

        if self.max_surge < 0 or self.max_unavailable < 0:
            raise ValidationError("Rolling update values cannot be negative")

        if self.max_surge == 0 and self.max_unavailable == 0:
            raise ValidationError(
                "At least one of max_surge or max_unavailable must be positive"
            )

        if self.min_ready_seconds < 0:
            raise ValidationError("min_ready_seconds cannot be negative")

        if self.revision_history_limit < 0:
            raise ValidationError("Revision history limit cannot be negative")


@dataclass
class Pod:
    pod_id: str
    name: str
    image: str
    replica_set_id: str
    phase: PodPhase = PodPhase.PENDING
    ready: bool = False
    ready_since: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def start(self):
        if self.phase != PodPhase.PENDING:
            raise DeploymentError("Only pending pods can start")

        self.phase = PodPhase.RUNNING

    def mark_ready(self):
        if self.phase != PodPhase.RUNNING:
            raise DeploymentError("Only running pods can become ready")

        self.ready = True
        self.ready_since = time.time()

    def mark_unready(self):
        self.ready = False
        self.ready_since = None

    def terminate(self):
        if self.phase in (PodPhase.TERMINATED, PodPhase.FAILED):
            return

        self.ready = False
        self.phase = PodPhase.TERMINATING

    def finish_termination(self):
        if self.phase != PodPhase.TERMINATING:
            raise DeploymentError("Pod is not terminating")

        self.phase = PodPhase.TERMINATED


@dataclass
class ReplicaSet:
    replica_set_id: str
    name: str
    deployment_name: str
    revision: int
    image: str
    desired_replicas: int = 0
    pods: dict[str, Pod] = field(default_factory=dict)
    phase: ReplicaSetPhase = ReplicaSetPhase.ACTIVE

    @property
    def active_pods(self) -> list[Pod]:
        return [
            pod for pod in self.pods.values()
            if pod.phase not in (
                PodPhase.TERMINATED,
                PodPhase.FAILED
            )
        ]

    @property
    def ready_replicas(self) -> int:
        return sum(
            pod.ready and pod.phase == PodPhase.RUNNING
            for pod in self.pods.values()
        )

    @property
    def available_replicas(self) -> int:
        return self.ready_replicas


@dataclass
class DeploymentStatus:
    desired_replicas: int
    updated_replicas: int = 0
    ready_replicas: int = 0
    available_replicas: int = 0
    unavailable_replicas: int = 0
    observed_generation: int = 1
    phase: DeploymentPhase = DeploymentPhase.PROGRESSING


class DeploymentController:

    def __init__(self, spec: DeploymentSpec):
        self.spec = spec
        self.generation = 1
        self.revision = 1

        self.replica_sets: dict[str, ReplicaSet] = {}
        self.revision_history: dict[int, dict] = {}

        self.status = DeploymentStatus(
            desired_replicas=spec.replicas
        )

        self._create_replica_set(spec.container.image)
        self.reconcile()

    def _new_replica_set(self, image: str) -> ReplicaSet:
        identifier = str(uuid.uuid4())[:8]

        return ReplicaSet(
            replica_set_id=identifier,
            name=f"{self.spec.name}-{identifier}",
            deployment_name=self.spec.name,
            revision=self.revision,
            image=image
        )

    def _create_replica_set(self, image: str) -> ReplicaSet:
        replica_set = self._new_replica_set(image)

        self.replica_sets[replica_set.replica_set_id] = replica_set

        self.revision_history[self.revision] = {
            "revision": self.revision,
            "image": image,
            "replica_set_id": replica_set.replica_set_id
        }

        return replica_set

    @property
    def active_replica_sets(self) -> list[ReplicaSet]:
        return [
            rs for rs in self.replica_sets.values()
            if rs.phase == ReplicaSetPhase.ACTIVE
        ]

    @property
    def current_replica_set(self) -> ReplicaSet:
        candidates = [
            rs for rs in self.active_replica_sets
            if rs.image == self.spec.container.image
        ]

        if not candidates:
            raise DeploymentError("No active ReplicaSet for current image")

        return max(candidates, key=lambda rs: rs.revision)

    def _create_pod(self, replica_set: ReplicaSet) -> Pod:
        identifier = str(uuid.uuid4())[:8]

        pod = Pod(
            pod_id=identifier,
            name=f"{replica_set.name}-pod-{identifier}",
            image=replica_set.image,
            replica_set_id=replica_set.replica_set_id
        )

        replica_set.pods[pod.pod_id] = pod

        logger.info(
            "Created pod %s using image %s",
            pod.name,
            pod.image
        )

        return pod

    def _remove_pod(self, pod: Pod):
        pod.terminate()
        pod.finish_termination()

    def _sync_replica_set(
        self,
        replica_set: ReplicaSet,
        desired: int
    ):
        replica_set.desired_replicas = desired

        active = replica_set.active_pods

        while len(active) < desired:
            pod = self._create_pod(replica_set)
            pod.start()
            active.append(pod)

        while len(active) > desired:
            pod = active.pop()
            self._remove_pod(pod)

    def reconcile(self):
        """
        Reconciliation compares desired state with observed state.
        This method is safe to execute repeatedly.
        """

        active_sets = self.active_replica_sets

        if not active_sets:
            self._create_replica_set(self.spec.container.image)
            active_sets = self.active_replica_sets

        for replica_set in active_sets:
            target = (
                self.spec.replicas
                if replica_set.image == self.spec.container.image
                else 0
            )

            self._sync_replica_set(replica_set, target)

        self._update_status()

    def _update_status(self):
        active_sets = self.active_replica_sets

        active_pods = [
            pod
            for rs in active_sets
            for pod in rs.active_pods
        ]

        ready = sum(
            pod.ready and pod.phase == PodPhase.RUNNING
            for pod in active_pods
        )

        updated = sum(
            pod.image == self.spec.container.image
            for pod in active_pods
        )

        available = sum(
            pod.ready
            and pod.phase == PodPhase.RUNNING
            and (
                self.spec.min_ready_seconds == 0
                or (
                    pod.ready_since is not None
                    and time.time() - pod.ready_since
                    >= self.spec.min_ready_seconds
                )
            )
            for pod in active_pods
        )

        desired = self.spec.replicas

        self.status = DeploymentStatus(
            desired_replicas=desired,
            updated_replicas=updated,
            ready_replicas=ready,
            available_replicas=available,
            unavailable_replicas=max(0, desired - available),
            observed_generation=self.generation,
            phase=(
                DeploymentPhase.AVAILABLE
                if available >= desired
                else DeploymentPhase.PROGRESSING
            )
        )

    def mark_pod_ready(self, pod_id: str):
        for replica_set in self.replica_sets.values():
            if pod_id in replica_set.pods:
                replica_set.pods[pod_id].mark_ready()
                self._update_status()
                return

        raise DeploymentError(f"Unknown pod: {pod_id}")

    def mark_pod_unready(self, pod_id: str):
        for replica_set in self.replica_sets.values():
            if pod_id in replica_set.pods:
                replica_set.pods[pod_id].mark_unready()
                self._update_status()
                return

        raise DeploymentError(f"Unknown pod: {pod_id}")

    def scale(self, replicas: int):
        if replicas < 0:
            raise ValidationError("Replica count cannot be negative")

        self.spec = DeploymentSpec(
            name=self.spec.name,
            namespace=self.spec.namespace,
            replicas=replicas,
            container=self.spec.container,
            max_surge=self.spec.max_surge,
            max_unavailable=self.spec.max_unavailable,
            min_ready_seconds=self.spec.min_ready_seconds,
            revision_history_limit=self.spec.revision_history_limit
        )

        self.generation += 1
        self.reconcile()

    def update_image(self, new_image: str):
        if not new_image.strip():
            raise ValidationError("Image cannot be empty")

        if new_image == self.spec.container.image:
            logger.info("Image is unchanged")
            return

        old_spec = self.spec

        try:
            self.spec = DeploymentSpec(
                name=old_spec.name,
                namespace=old_spec.namespace,
                replicas=old_spec.replicas,
                container=ContainerSpec(
                    name=old_spec.container.name,
                    image=new_image,
                    port=old_spec.container.port,
                    cpu_request=old_spec.container.cpu_request,
                    memory_request=old_spec.container.memory_request
                ),
                max_surge=old_spec.max_surge,
                max_unavailable=old_spec.max_unavailable,
                min_ready_seconds=old_spec.min_ready_seconds,
                revision_history_limit=old_spec.revision_history_limit
            )

            self.revision += 1
            self.generation += 1

            for rs in self.active_replica_sets:
                rs.phase = ReplicaSetPhase.INACTIVE

            self._create_replica_set(new_image)
            self.reconcile()

            logger.info(
                "Deployment updated to revision %d",
                self.revision
            )

        except Exception:
            self.spec = old_spec
            raise

    def rolling_update_step(self):
        """
        Simulates one bounded rolling-update operation.

        max_surge controls temporary capacity above desired replicas.
        max_unavailable controls how many replicas may be unavailable.
        """

        desired = self.spec.replicas

        old_sets = [
            rs for rs in self.active_replica_sets
            if rs.image != self.spec.container.image
        ]

        new_sets = [
            rs for rs in self.active_replica_sets
            if rs.image == self.spec.container.image
        ]

        if not new_sets:
            raise DeploymentError("No target ReplicaSet exists")

        new_rs = max(new_sets, key=lambda rs: rs.revision)

        all_active = [
            pod
            for rs in self.active_replica_sets
            for pod in rs.active_pods
        ]

        total = len(all_active)

        ready = sum(
            pod.ready and pod.phase == PodPhase.RUNNING
            for pod in all_active
        )

        old_pods = [
            pod
            for rs in old_sets
            for pod in rs.active_pods
        ]

        new_pods = new_rs.active_pods

        max_total = desired + self.spec.max_surge
        min_available = max(
            0,
            desired - self.spec.max_unavailable
        )

        # Add replacement capacity before removing old pods.
        if len(new_pods) < desired and total < max_total:
            pod = self._create_pod(new_rs)
            pod.start()
            self._update_status()
            return f"Created {pod.name}"

        # Remove old pods only when the availability budget permits.
        if old_pods and ready > min_available:
            pod = old_pods[0]
            self._remove_pod(pod)
            self._update_status()
            return f"Terminated {pod.name}"

        if not old_pods and len(new_pods) >= desired:
            for rs in old_sets:
                rs.phase = ReplicaSetPhase.INACTIVE

            self._update_status()
            return "Rolling update completed"

        return "Waiting for readiness or capacity"

    def run_rolling_update(self, max_steps: int = 100):
        if max_steps <= 0:
            raise ValidationError("max_steps must be positive")

        history = []

        for _ in range(max_steps):
            result = self.rolling_update_step()
            history.append(result)

            if result == "Rolling update completed":
                return history

        raise DeploymentError(
            "Rolling update did not complete within the step limit"
        )

    def rollback(self, target_revision: int):
        if target_revision not in self.revision_history:
            raise RevisionNotFoundError(
                f"Revision {target_revision} does not exist"
            )

        target = self.revision_history[target_revision]
        target_image = target["image"]

        if target_image == self.spec.container.image:
            logger.info("Deployment already uses requested image")
            return

        self.update_image(target_image)

        logger.info(
            "Rollback created revision %d using image %s",
            self.revision,
            target_image
        )

    def cleanup_history(self):
        limit = self.spec.revision_history_limit

        if limit == 0:
            keep = {self.revision}
        else:
            revisions = sorted(self.revision_history)
            keep = set(revisions[-limit:])

        for revision in list(self.revision_history):
            if revision not in keep:
                del self.revision_history[revision]

        for rs_id, rs in list(self.replica_sets.items()):
            if (
                rs.phase == ReplicaSetPhase.INACTIVE
                and rs.revision not in self.revision_history
            ):
                del self.replica_sets[rs_id]

    def report(self) -> dict:
        self._update_status()

        return {
            "deployment": self.spec.name,
            "namespace": self.spec.namespace,
            "generation": self.generation,
            "revision": self.revision,
            "image": self.spec.container.image,
            "status": asdict(self.status),
            "replica_sets": [
                {
                    "name": rs.name,
                    "revision": rs.revision,
                    "image": rs.image,
                    "desired": rs.desired_replicas,
                    "active": len(rs.active_pods),
                    "ready": rs.ready_replicas,
                    "phase": rs.phase.value
                }
                for rs in self.replica_sets.values()
            ],
            "history": list(self.revision_history.values())
        }


def demonstrate():
    spec = DeploymentSpec(
        name="inventory-api",
        namespace="production",
        replicas=3,
        container=ContainerSpec(
            name="inventory",
            image="inventory-api:v1.0.0",
            port=8080
        ),
        max_surge=1,
        max_unavailable=0
    )

    deployment = DeploymentController(spec)

    # Initial pods become ready.
    for rs in deployment.active_replica_sets:
        for pod in rs.active_pods:
            deployment.mark_pod_ready(pod.pod_id)

    print("\nINITIAL DEPLOYMENT")
    print(json.dumps(deployment.report(), indent=2))

    # Update the application image.
    deployment.update_image("inventory-api:v2.0.0")

    print("\nROLLING UPDATE")
    for result in deployment.run_rolling_update():
        print(result)

        # Simulate successful application readiness.
        for rs in deployment.active_replica_sets:
            if rs.image == deployment.spec.container.image:
                for pod in rs.active_pods:
                    if not pod.ready:
                        deployment.mark_pod_ready(pod.pod_id)

    print("\nUPDATED DEPLOYMENT")
    print(json.dumps(deployment.report(), indent=2))

    # Roll back to the first revision.
    deployment.rollback(1)

    for rs in deployment.active_replica_sets:
        if rs.image == deployment.spec.container.image:
            for pod in rs.active_pods:
                if not pod.ready:
                    deployment.mark_pod_ready(pod.pod_id)

    print("\nROLLBACK")
    print(json.dumps(deployment.report(), indent=2))

    deployment.scale(5)

    print("\nSCALED DEPLOYMENT")
    print(json.dumps(deployment.report(), indent=2))

    deployment.cleanup_history()


if __name__ == "__main__":
    try:
        demonstrate()
    except (DeploymentError, ValidationError) as exc:
        logger.exception("Deployment operation failed: %s", exc)
        raise SystemExit(1)
