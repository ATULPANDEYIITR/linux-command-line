#!/usr/bin/env python3
"""
Kubernetes Control Plane Simulator

Models:
- API server request processing and validation
- etcd-style persistent state and resource versions
- Scheduler node selection and pod placement
- Controllers and reconciliation loops
- Node and component health
- Control plane operations and failure handling
- Leader election and operational monitoring

Requires Python 3.10+.
Uses only the Python standard library.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
import uuid

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("kubernetes-control-plane")


# ============================================================
# 1. DOMAIN TYPES
# ============================================================

class PodPhase(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    FAILED = "Failed"
    SUCCEEDED = "Succeeded"


class NodeCondition(str, Enum):
    READY = "Ready"
    NOT_READY = "NotReady"
    UNKNOWN = "Unknown"


class ComponentStatus(str, Enum):
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNAVAILABLE = "Unavailable"


class OperationType(str, Enum):
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"
    SCHEDULE = "Schedule"
    RECONCILE = "Reconcile"


class ControlPlaneError(Exception):
    """Base exception for control plane operations."""


class ValidationError(ControlPlaneError):
    pass


class NotFoundError(ControlPlaneError):
    pass


class ConflictError(ControlPlaneError):
    pass


class SchedulingError(ControlPlaneError):
    pass


@dataclass
class ResourceMetadata:
    name: str
    namespace: str = "default"
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_version: int = 0
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name or len(self.name) > 253:
            raise ValidationError("Invalid resource name")

        if not self.namespace or len(self.namespace) > 63:
            raise ValidationError("Invalid namespace")

        for key, value in self.labels.items():
            if not key or not isinstance(value, str):
                raise ValidationError("Invalid label")


@dataclass
class Container:
    name: str
    image: str
    cpu_request: int = 1
    memory_request: int = 128

    def validate(self) -> None:
        if not self.name or not self.image:
            raise ValidationError("Container name and image are required")

        if self.cpu_request <= 0 or self.memory_request <= 0:
            raise ValidationError("Resource requests must be positive")


@dataclass
class Pod:
    metadata: ResourceMetadata
    containers: list[Container]
    phase: PodPhase = PodPhase.PENDING
    node_name: Optional[str] = None
    restart_count: int = 0

    def validate(self) -> None:
        self.metadata.validate()

        if not self.containers:
            raise ValidationError("A pod requires at least one container")

        names = set()

        for container in self.containers:
            container.validate()

            if container.name in names:
                raise ValidationError("Duplicate container name")

            names.add(container.name)

    @property
    def cpu_request(self) -> int:
        return sum(c.cpu_request for c in self.containers)

    @property
    def memory_request(self) -> int:
        return sum(c.memory_request for c in self.containers)


@dataclass
class Node:
    name: str
    cpu_capacity: int
    memory_capacity: int
    condition: NodeCondition = NodeCondition.READY
    cpu_allocated: int = 0
    memory_allocated: int = 0
    labels: dict[str, str] = field(default_factory=dict)

    def available_cpu(self) -> int:
        return self.cpu_capacity - self.cpu_allocated

    def available_memory(self) -> int:
        return self.memory_capacity - self.memory_allocated

    def can_host(self, pod: Pod) -> bool:
        return (
            self.condition == NodeCondition.READY
            and self.available_cpu() >= pod.cpu_request
            and self.available_memory() >= pod.memory_request
        )

    def allocate(self, pod: Pod) -> None:
        if not self.can_host(pod):
            raise SchedulingError(f"Node {self.name} cannot host pod")

        self.cpu_allocated += pod.cpu_request
        self.memory_allocated += pod.memory_request

    def release(self, pod: Pod) -> None:
        self.cpu_allocated -= pod.cpu_request
        self.memory_allocated -= pod.memory_request

        if self.cpu_allocated < 0 or self.memory_allocated < 0:
            raise ConflictError("Resource allocation accounting is invalid")


@dataclass
class ControlPlaneComponent:
    name: str
    status: ComponentStatus
    version: str
    last_heartbeat: float = field(default_factory=time.time)


@dataclass
class Event:
    event_id: str
    timestamp: float
    resource_name: str
    event_type: str
    message: str


@dataclass
class AuditRecord:
    timestamp: float
    operation: str
    resource: str
    actor: str
    result: str


# ============================================================
# 2. ETCD-STYLE PERSISTENT STATE
# ============================================================

class EtcdStore:
    """
    Thread-safe in-memory model of etcd.

    Real etcd provides a distributed, durable key-value store,
    revisions, transactions, leases, watches and consensus.

    This simulator models revisions and optimistic concurrency.
    It does not implement distributed consensus or disk durability.
    """

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._revision = 0
        self._lock = threading.RLock()

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def put(
        self,
        key: str,
        value: Any,
        expected_revision: Optional[int] = None
    ) -> int:

        with self._lock:
            current = self._data.get(key)

            if expected_revision is not None:
                actual = current["revision"] if current else 0

                if actual != expected_revision:
                    raise ConflictError(
                        f"Revision conflict for {key}: "
                        f"expected {expected_revision}, got {actual}"
                    )

            self._revision += 1

            self._data[key] = {
                "value": copy.deepcopy(value),
                "revision": self._revision
            }

            return self._revision

    def get(self, key: str) -> Any:
        with self._lock:
            if key not in self._data:
                raise NotFoundError(f"Key not found: {key}")

            return copy.deepcopy(self._data[key]["value"])

    def get_with_revision(self, key: str) -> tuple[Any, int]:
        with self._lock:
            if key not in self._data:
                raise NotFoundError(f"Key not found: {key}")

            entry = self._data[key]

            return (
                copy.deepcopy(entry["value"]),
                entry["revision"]
            )

    def delete(self, key: str) -> None:
        with self._lock:
            if key not in self._data:
                raise NotFoundError(f"Key not found: {key}")

            del self._data[key]
            self._revision += 1

    def list_prefix(self, prefix: str) -> list[Any]:
        with self._lock:
            return [
                copy.deepcopy(entry["value"])
                for key, entry in self._data.items()
                if key.startswith(prefix)
            ]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                key: copy.deepcopy(entry["value"])
                for key, entry in self._data.items()
            }


# ============================================================
# 3. API SERVER
# ============================================================

class APIServer:
    """
    Central API interface for validating and persisting resources.

    The real Kubernetes API server also performs authentication,
    authorization, admission, conversion, defaulting and
    API discovery.
    """

    def __init__(self, store: EtcdStore):
        self.store = store
        self.audit_log: list[AuditRecord] = []
        self._lock = threading.RLock()

    @staticmethod
    def pod_key(namespace: str, name: str) -> str:
        return f"/registry/pods/{namespace}/{name}"

    @staticmethod
    def node_key(name: str) -> str:
        return f"/registry/nodes/{name}"

    def _audit(
        self,
        operation: str,
        resource: str,
        actor: str,
        result: str
    ) -> None:

        self.audit_log.append(
            AuditRecord(
                timestamp=time.time(),
                operation=operation,
                resource=resource,
                actor=actor,
                result=result
            )
        )

    def create_pod(
        self,
        pod: Pod,
        actor: str = "system"
    ) -> Pod:

        with self._lock:
            try:
                pod.validate()

                key = self.pod_key(
                    pod.metadata.namespace,
                    pod.metadata.name
                )

                if key in self.store.snapshot():
                    raise ConflictError("Pod already exists")

                pod.metadata.resource_version = self.store.put(
                    key,
                    asdict(pod)
                )

                self._audit("CREATE", key, actor, "SUCCESS")

                return copy.deepcopy(pod)

            except Exception:
                self._audit(
                    "CREATE",
                    pod.metadata.name,
                    actor,
                    "FAILED"
                )
                raise

    def get_pod(self, namespace: str, name: str) -> Pod:
        data = self.store.get(self.pod_key(namespace, name))
        return self._deserialize_pod(data)

    def update_pod(self, pod: Pod, actor: str = "system") -> Pod:
        with self._lock:
            key = self.pod_key(
                pod.metadata.namespace,
                pod.metadata.name
            )

            try:
                pod.validate()

                _, current_revision = self.store.get_with_revision(key)

                revision = self.store.put(
                    key,
                    asdict(pod),
                    expected_revision=current_revision
                )

                pod.metadata.resource_version = revision

                self._audit("UPDATE", key, actor, "SUCCESS")

                return copy.deepcopy(pod)

            except Exception:
                self._audit("UPDATE", key, actor, "FAILED")
                raise

    def delete_pod(
        self,
        namespace: str,
        name: str,
        actor: str = "system"
    ) -> None:

        key = self.pod_key(namespace, name)

        try:
            self.store.delete(key)
            self._audit("DELETE", key, actor, "SUCCESS")
        except Exception:
            self._audit("DELETE", key, actor, "FAILED")
            raise

    def register_node(self, node: Node) -> None:
        if node.cpu_capacity <= 0 or node.memory_capacity <= 0:
            raise ValidationError("Invalid node capacity")

        if node.name in [n["name"] for n in self.store.list_prefix(
            "/registry/nodes/"
        )]:
            raise ConflictError("Node already registered")

        self.store.put(self.node_key(node.name), asdict(node))

    def _deserialize_pod(self, data: dict[str, Any]) -> Pod:
        metadata = ResourceMetadata(**data["metadata"])

        containers = [
            Container(**container)
            for container in data["containers"]
        ]

        return Pod(
            metadata=metadata,
            containers=containers,
            phase=PodPhase(data["phase"]),
            node_name=data["node_name"],
            restart_count=data["restart_count"]
        )


# ============================================================
# 4. SCHEDULER
# ============================================================

class Scheduler:
    """
    Selects a feasible node and binds a pending pod.

    Scheduling is a two-stage conceptual operation:
    1. Filtering: identify feasible nodes.
    2. Scoring: rank feasible nodes.

    Kubernetes scheduling includes additional plugins,
    topology constraints, affinity, taints and tolerations.
    """

    def __init__(self, api_server: APIServer):
        self.api_server = api_server

    def schedule(
        self,
        pod: Pod,
        nodes: list[Node]
    ) -> str:

        if pod.phase != PodPhase.PENDING:
            raise SchedulingError("Only pending pods can be scheduled")

        feasible = [
            node for node in nodes
            if node.can_host(pod)
        ]

        if not feasible:
            raise SchedulingError(
                f"No feasible node for pod {pod.metadata.name}"
            )

        # Best-fit scoring reduces fragmentation by favoring
        # nodes with the smallest remaining CPU capacity.
        feasible.sort(
            key=lambda node: (
                node.available_cpu() - pod.cpu_request,
                node.available_memory() - pod.memory_request,
                node.name
            )
        )

        selected = feasible[0]

        selected.allocate(pod)

        pod.node_name = selected.name
        pod.phase = PodPhase.RUNNING

        try:
            self.api_server.update_pod(pod, actor="scheduler")
        except Exception:
            selected.release(pod)
            raise

        logger.info(
            "Scheduled pod %s on node %s",
            pod.metadata.name,
            selected.name
        )

        return selected.name


# ============================================================
# 5. CONTROLLER AND RECONCILIATION
# ============================================================

@dataclass
class Deployment:
    name: str
    namespace: str
    desired_replicas: int
    image: str
    cpu_request: int = 1
    memory_request: int = 128

    def validate(self) -> None:
        if not self.name or not self.image:
            raise ValidationError("Deployment name and image required")

        if self.desired_replicas < 0:
            raise ValidationError("Replica count cannot be negative")


class DeploymentController:
    """
    Reconciliation compares desired state with observed state.

    It creates missing pods and does not assume that an API
    request immediately produces a running workload.
    """

    def __init__(self, api_server: APIServer):
        self.api_server = api_server

    def reconcile(self, deployment: Deployment) -> int:
        deployment.validate()

        prefix = (
            f"/registry/pods/{deployment.namespace}/"
            f"{deployment.name}-"
        )

        existing = self.api_server.store.list_prefix(prefix)

        current = len(existing)
        created = 0

        while current < deployment.desired_replicas:
            pod = Pod(
                metadata=ResourceMetadata(
                    name=f"{deployment.name}-{current}",
                    namespace=deployment.namespace,
                    labels={
                        "app": deployment.name,
                        "managed-by": "deployment-controller"
                    }
                ),
                containers=[
                    Container(
                        name="application",
                        image=deployment.image,
                        cpu_request=deployment.cpu_request,
                        memory_request=deployment.memory_request
                    )
                ]
            )

            self.api_server.create_pod(
                pod,
                actor="deployment-controller"
            )

            current += 1
            created += 1

        return created


# ============================================================
# 6. CONTROL PLANE OPERATIONS
# ============================================================

class ControlPlaneMonitor:
    def __init__(self):
        self.components: dict[str, ControlPlaneComponent] = {}
        self.events: list[Event] = []

    def register(self, component: ControlPlaneComponent) -> None:
        if component.name in self.components:
            raise ConflictError("Component already registered")

        self.components[component.name] = component

    def heartbeat(self, component_name: str) -> None:
        if component_name not in self.components:
            raise NotFoundError("Component not found")

        component = self.components[component_name]
        component.last_heartbeat = time.time()
        component.status = ComponentStatus.HEALTHY

    def evaluate(self, timeout_seconds: float = 30) -> dict[str, str]:
        if timeout_seconds <= 0:
            raise ValidationError("Heartbeat timeout must be positive")

        now = time.time()
        results = {}

        for name, component in self.components.items():
            if now - component.last_heartbeat > timeout_seconds:
                component.status = ComponentStatus.UNAVAILABLE

            results[name] = component.status.value

        return results

    def record_event(
        self,
        resource: str,
        event_type: str,
        message: str
    ) -> None:

        self.events.append(
            Event(
                event_id=str(uuid.uuid4()),
                timestamp=time.time(),
                resource_name=resource,
                event_type=event_type,
                message=message
            )
        )


class LeaderElection:
    """
    Simplified lease-based leader election model.

    This is an in-process simulation, not a distributed lease
    implementation. Real Kubernetes deployments use Lease
    objects and coordination mechanisms.
    """

    def __init__(self, lease_duration: float = 15):
        if lease_duration <= 0:
            raise ValidationError("Lease duration must be positive")

        self.lease_duration = lease_duration
        self.holder: Optional[str] = None
        self.renewed_at = 0.0
        self._lock = threading.Lock()

    def acquire(self, candidate: str) -> bool:
        if not candidate:
            raise ValidationError("Candidate identity is required")

        with self._lock:
            now = time.time()

            expired = (
                self.holder is None
                or now - self.renewed_at >= self.lease_duration
            )

            if expired or self.holder == candidate:
                self.holder = candidate
                self.renewed_at = now
                return True

            return False

    def is_leader(self, candidate: str) -> bool:
        with self._lock:
            return (
                self.holder == candidate
                and time.time() - self.renewed_at < self.lease_duration
            )


# ============================================================
# 7. CLUSTER SIMULATION
# ============================================================

class KubernetesControlPlane:
    def __init__(self):
        self.etcd = EtcdStore()
        self.api_server = APIServer(self.etcd)
        self.scheduler = Scheduler(self.api_server)
        self.deployment_controller = DeploymentController(
            self.api_server
        )
        self.monitor = ControlPlaneMonitor()
        self.leader_election = LeaderElection()

        self.nodes: list[Node] = []

    def add_node(self, node: Node) -> None:
        self.api_server.register_node(node)
        self.nodes.append(node)

    def submit_deployment(self, deployment: Deployment) -> list[Pod]:
        self.deployment_controller.reconcile(deployment)

        prefix = (
            f"/registry/pods/{deployment.namespace}/"
            f"{deployment.name}-"
        )

        stored = self.etcd.list_prefix(prefix)

        return [
            self.api_server._deserialize_pod(item)
            for item in stored
        ]

    def schedule_pending_pods(self) -> dict[str, str]:
        results = {}

        for data in self.etcd.list_prefix("/registry/pods/"):
            pod = self.api_server._deserialize_pod(data)

            if pod.phase != PodPhase.PENDING:
                continue

            try:
                results[pod.metadata.name] = self.scheduler.schedule(
                    pod,
                    self.nodes
                )
            except SchedulingError as error:
                results[pod.metadata.name] = str(error)

        return results

    def cluster_report(self) -> dict[str, Any]:
        pods = self.etcd.list_prefix("/registry/pods/")

        return {
            "etcd_revision": self.etcd.revision,
            "nodes": [
                {
                    "name": node.name,
                    "condition": node.condition.value,
                    "cpu_available": node.available_cpu(),
                    "memory_available": node.available_memory()
                }
                for node in self.nodes
            ],
            "pods": {
                phase.value: sum(
                    1 for pod in pods
                    if pod["phase"] == phase.value
                )
                for phase in PodPhase
            },
            "components": self.monitor.evaluate(),
            "audit_records": len(self.api_server.audit_log)
        }


# ============================================================
# 8. EXECUTABLE TESTS AND EXAMPLE
# ============================================================

def run_tests() -> None:
    cluster = KubernetesControlPlane()

    cluster.add_node(
        Node("worker-01", 8, 2048)
    )

    cluster.add_node(
        Node("worker-02", 4, 1024)
    )

    cluster.monitor.register(
        ControlPlaneComponent(
            "kube-apiserver",
            ComponentStatus.HEALTHY,
            "v1.32.0"
        )
    )

    cluster.monitor.register(
        ControlPlaneComponent(
            "kube-scheduler",
            ComponentStatus.HEALTHY,
            "v1.32.0"
        )
    )

    cluster.monitor.register(
        ControlPlaneComponent(
            "kube-controller-manager",
            ComponentStatus.HEALTHY,
            "v1.32.0"
        )
    )

    cluster.monitor.register(
        ControlPlaneComponent(
            "etcd",
            ComponentStatus.HEALTHY,
            "3.5.17"
        )
    )

    assert cluster.leader_election.acquire("controller-01")
    assert cluster.leader_election.is_leader("controller-01")

    deployment = Deployment(
        name="web",
        namespace="production",
        desired_replicas=3,
        image="nginx:1.27",
        cpu_request=1,
        memory_request=256
    )

    pods = cluster.submit_deployment(deployment)

    assert len(pods) == 3
    assert all(p.phase == PodPhase.PENDING for p in pods)

    scheduling_results = cluster.schedule_pending_pods()

    assert len(scheduling_results) == 3

    running_pods = cluster.etcd.list_prefix(
        "/registry/pods/production/web-"
    )

    assert all(
        pod["phase"] == PodPhase.RUNNING.value
        for pod in running_pods
    )

    # Validation failure: zero CPU request.
    try:
        invalid = Pod(
            metadata=ResourceMetadata(name="invalid"),
            containers=[
                Container("app", "nginx:1.27", 0, 128)
            ]
        )
        cluster.api_server.create_pod(invalid)
        raise AssertionError("Invalid pod was accepted")
    except ValidationError:
        pass

    # Concurrency failure: stale resource revision.
    pod_data, revision = cluster.etcd.get_with_revision(
        "/registry/pods/production/web-0"
    )

    cluster.etcd.put(
        "/registry/pods/production/web-0",
        pod_data
    )

    try:
        cluster.etcd.put(
            "/registry/pods/production/web-0",
            pod_data,
            expected_revision=revision
        )
        raise AssertionError("Stale update was accepted")
    except ConflictError:
        pass

    # Scheduling failure when no nodes are feasible.
    oversized = Pod(
        metadata=ResourceMetadata(name="oversized"),
        containers=[
            Container("app", "large-image", 100, 100000)
        ]
    )

    try:
        cluster.scheduler.schedule(oversized, cluster.nodes)
        raise AssertionError("Unschedulable pod was accepted")
    except SchedulingError:
        pass

    print("\nKUBERNETES CONTROL PLANE REPORT")

    print(
        json.dumps(
            cluster.cluster_report(),
            indent=4
        )
    )

    print("\nSCHEDULING RESULTS")

    print(json.dumps(scheduling_results, indent=4))

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run_tests()
