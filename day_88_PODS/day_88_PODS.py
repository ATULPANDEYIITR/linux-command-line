#!/usr/bin/env python3
"""
POD MANAGEMENT AND KUBERNETES WORKLOAD DEPLOYMENT

A self-contained Kubernetes Pod lifecycle simulator covering:
- Containers versus Pods
- Pod specifications and manifests
- Container states and restart policies
- Pod lifecycle and readiness
- Init containers and application containers
- Resource requests and limits
- Scheduling and node capacity
- Liveness, readiness, and startup probes
- Deployment replicas and rolling updates
- Failure handling and event history
- Workload validation and operational reporting

Python 3.10+
No external dependencies.
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
    format="%(levelname)s: %(message)s"
)

logger = logging.getLogger("pod-manager")


# ============================================================
# 1. DOMAIN ENUMERATIONS
# ============================================================

class PodPhase(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ContainerState(str, Enum):
    WAITING = "Waiting"
    RUNNING = "Running"
    TERMINATED = "Terminated"


class RestartPolicy(str, Enum):
    ALWAYS = "Always"
    ON_FAILURE = "OnFailure"
    NEVER = "Never"


class WorkloadType(str, Enum):
    DEPLOYMENT = "Deployment"
    JOB = "Job"
    DAEMONSET = "DaemonSet"
    STATEFULSET = "StatefulSet"


# ============================================================
# 2. RESOURCE MODEL
# ============================================================

@dataclass(frozen=True)
class ResourceRequirements:
    cpu_request: float = 0.1
    memory_request_mb: int = 128
    cpu_limit: float = 0.5
    memory_limit_mb: int = 512

    def __post_init__(self):
        if self.cpu_request < 0 or self.cpu_limit <= 0:
            raise ValueError("CPU values must be non-negative.")

        if self.memory_request_mb < 0 or self.memory_limit_mb <= 0:
            raise ValueError("Memory values must be non-negative.")

        if self.cpu_request > self.cpu_limit:
            raise ValueError("CPU request cannot exceed CPU limit.")

        if self.memory_request_mb > self.memory_limit_mb:
            raise ValueError("Memory request cannot exceed memory limit.")


@dataclass(frozen=True)
class Probe:
    path: str
    initial_delay_seconds: int = 0
    period_seconds: int = 10
    failure_threshold: int = 3

    def __post_init__(self):
        if not self.path.startswith("/"):
            raise ValueError("Probe path must begin with '/'.")

        if self.initial_delay_seconds < 0:
            raise ValueError("Initial delay cannot be negative.")

        if self.period_seconds <= 0 or self.failure_threshold <= 0:
            raise ValueError("Probe intervals and thresholds must be positive.")


# ============================================================
# 3. CONTAINER MODEL
# ============================================================

@dataclass
class Container:
    name: str
    image: str
    resources: ResourceRequirements = field(
        default_factory=ResourceRequirements
    )
    environment: dict[str, str] = field(default_factory=dict)
    state: ContainerState = ContainerState.WAITING
    restart_count: int = 0
    exit_code: Optional[int] = None
    ready: bool = False
    logs: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Container name is required.")

        if not self.image or any(
            character.isspace() for character in self.image
        ):
            raise ValueError("A valid container image is required.")

    def start(self):
        if self.state == ContainerState.RUNNING:
            raise RuntimeError(f"{self.name} is already running.")

        self.state = ContainerState.RUNNING
        self.exit_code = None
        self.ready = False
        self.logs.append("Container started.")

    def mark_ready(self):
        if self.state != ContainerState.RUNNING:
            raise RuntimeError("Only running containers can become ready.")

        self.ready = True
        self.logs.append("Container passed readiness check.")

    def terminate(self, exit_code: int):
        if self.state != ContainerState.RUNNING:
            raise RuntimeError("Container is not running.")

        self.state = ContainerState.TERMINATED
        self.exit_code = exit_code
        self.ready = False
        self.logs.append(f"Container terminated with exit code {exit_code}.")

    def restart(self):
        self.restart_count += 1
        self.state = ContainerState.WAITING
        self.ready = False
        self.exit_code = None
        self.logs.append("Container restart requested.")


# ============================================================
# 4. NODE AND SCHEDULER
# ============================================================

@dataclass
class Node:
    name: str
    cpu_capacity: float
    memory_capacity_mb: int
    labels: dict[str, str] = field(default_factory=dict)
    scheduled_pods: set[str] = field(default_factory=set)

    def __post_init__(self):
        if self.cpu_capacity <= 0 or self.memory_capacity_mb <= 0:
            raise ValueError("Node capacity must be positive.")

    def available_resources(self, pod_requests):
        return (
            self.cpu_capacity - pod_requests[0],
            self.memory_capacity_mb - pod_requests[1]
        )


class Scheduler:
    """Schedules Pods using aggregate container resource requests."""

    def __init__(self, nodes: list[Node]):
        if not nodes:
            raise ValueError("At least one node is required.")

        self.nodes = {node.name: node for node in nodes}

    def schedule(self, pod: "Pod") -> str:
        if pod.node_name:
            raise RuntimeError("Pod has already been scheduled.")

        cpu = sum(c.resources.cpu_request for c in pod.containers)
        memory = sum(
            c.resources.memory_request_mb for c in pod.containers
        )

        candidates = []

        for node in self.nodes.values():
            available_cpu, available_memory = node.available_resources(
                pod.aggregate_node_requests()
            )

            if available_cpu >= cpu and available_memory >= memory:
                candidates.append((node, available_cpu, available_memory))

        if not candidates:
            raise RuntimeError(
                f"Insufficient cluster capacity for Pod {pod.name}."
            )

        # Best-fit placement reduces unnecessary fragmentation.
        node, _, _ = min(
            candidates,
            key=lambda item: (
                item[1] - cpu,
                item[2] - memory
            )
        )

        pod.node_name = node.name
        node.scheduled_pods.add(pod.uid)

        return node.name


# ============================================================
# 5. POD MODEL
# ============================================================

@dataclass
class Pod:
    name: str
    namespace: str
    containers: list[Container]
    init_containers: list[Container] = field(default_factory=list)
    restart_policy: RestartPolicy = RestartPolicy.ALWAYS
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    readiness_probe: Optional[Probe] = None
    liveness_probe: Optional[Probe] = None

    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: PodPhase = PodPhase.PENDING
    node_name: Optional[str] = None
    creation_time: float = field(default_factory=time.time)
    conditions: dict[str, bool] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.name or not self.namespace:
            raise ValueError("Pod name and namespace are required.")

        if not self.containers:
            raise ValueError("A Pod must contain at least one application container.")

        all_containers = self.containers + self.init_containers
        names = [container.name for container in all_containers]

        if len(names) != len(set(names)):
            raise ValueError("Container names must be unique within a Pod.")

        self.conditions = {
            "PodScheduled": False,
            "Initialized": not bool(self.init_containers),
            "ContainersReady": False,
            "Ready": False
        }

    def aggregate_node_requests(self):
        """Init containers run sequentially; their requests are not summed."""

        app_cpu = sum(
            c.resources.cpu_request for c in self.containers
        )
        app_memory = sum(
            c.resources.memory_request_mb for c in self.containers
        )

        init_cpu = max(
            (c.resources.cpu_request for c in self.init_containers),
            default=0
        )
        init_memory = max(
            (c.resources.memory_request_mb for c in self.init_containers),
            default=0
        )

        return (
            max(app_cpu, init_cpu),
            max(app_memory, init_memory)
        )

    def record(self, message: str):
        self.events.append(message)
        logger.info("[%s] %s", self.name, message)

    def initialize(self):
        if not self.node_name:
            raise RuntimeError("Pod must be scheduled before initialization.")

        if self.phase != PodPhase.PENDING:
            raise RuntimeError("Only pending Pods can be initialized.")

        self.conditions["PodScheduled"] = True
        self.record(f"Scheduled on node {self.node_name}.")

        if not self.init_containers:
            self.conditions["Initialized"] = True
            return

        for container in self.init_containers:
            container.start()
            container.mark_ready()
            container.terminate(0)
            self.record(f"Init container {container.name} completed.")

        self.conditions["Initialized"] = True

    def start(self):
        if not self.conditions["Initialized"]:
            raise RuntimeError("Init containers have not completed.")

        if not self.conditions["PodScheduled"]:
            raise RuntimeError("Pod has not been scheduled.")

        if self.phase not in (PodPhase.PENDING, PodPhase.RUNNING):
            raise RuntimeError("Pod cannot start in its current phase.")

        for container in self.containers:
            if container.state == ContainerState.WAITING:
                container.start()

        self.phase = PodPhase.RUNNING
        self.record("Application containers started.")

    def evaluate_readiness(self):
        if self.phase != PodPhase.RUNNING:
            self.conditions["Ready"] = False
            return False

        ready = all(
            container.state == ContainerState.RUNNING
            and container.ready
            for container in self.containers
        )

        self.conditions["ContainersReady"] = ready
        self.conditions["Ready"] = ready

        return ready

    def simulate_readiness_probe(self, successful: bool):
        if not self.readiness_probe:
            raise RuntimeError("No readiness probe is configured.")

        if self.phase != PodPhase.RUNNING:
            raise RuntimeError("Pod is not running.")

        if successful:
            for container in self.containers:
                if container.state == ContainerState.RUNNING:
                    container.mark_ready()
        else:
            for container in self.containers:
                container.ready = False
                container.logs.append("Readiness probe failed.")

        self.evaluate_readiness()

    def simulate_container_failure(
        self,
        container_name: str,
        exit_code: int
    ):
        container = next(
            (
                c for c in self.containers
                if c.name == container_name
            ),
            None
        )

        if container is None:
            raise ValueError(f"Unknown container: {container_name}")

        container.terminate(exit_code)
        self.record(
            f"Container {container_name} exited with code {exit_code}."
        )

        should_restart = (
            self.restart_policy == RestartPolicy.ALWAYS
            or (
                self.restart_policy == RestartPolicy.ON_FAILURE
                and exit_code != 0
            )
        )

        if should_restart:
            container.restart()
            container.start()
            self.record(f"Container {container_name} restarted.")
            self.phase = PodPhase.RUNNING
        elif all(
            c.state == ContainerState.TERMINATED
            for c in self.containers
        ):
            if all(c.exit_code == 0 for c in self.containers):
                self.phase = PodPhase.SUCCEEDED
            else:
                self.phase = PodPhase.FAILED

        self.evaluate_readiness()

    def complete(self, exit_code: int = 0):
        if self.phase != PodPhase.RUNNING:
            raise RuntimeError("Only running Pods can complete.")

        for container in self.containers:
            if container.state == ContainerState.RUNNING:
                container.terminate(exit_code)

        if exit_code == 0:
            self.phase = PodPhase.SUCCEEDED
        else:
            self.phase = PodPhase.FAILED

        self.conditions["Ready"] = False
        self.conditions["ContainersReady"] = False
        self.record(f"Pod completed with exit code {exit_code}.")

    def to_dict(self):
        return {
            "name": self.name,
            "namespace": self.namespace,
            "uid": self.uid,
            "phase": self.phase.value,
            "node": self.node_name,
            "restart_policy": self.restart_policy.value,
            "conditions": self.conditions,
            "containers": [
                {
                    "name": c.name,
                    "image": c.image,
                    "state": c.state.value,
                    "ready": c.ready,
                    "restart_count": c.restart_count
                }
                for c in self.containers
            ],
            "events": self.events
        }


# ============================================================
# 6. WORKLOAD DEPLOYMENT
# ============================================================

@dataclass
class Deployment:
    name: str
    namespace: str
    replicas: int
    image: str
    labels: dict[str, str]
    pods: list[Pod] = field(default_factory=list)
    generation: int = 1
    observed_generation: int = 0

    def __post_init__(self):
        if self.replicas < 0:
            raise ValueError("Replica count cannot be negative.")

        if not self.name or not self.image:
            raise ValueError("Deployment name and image are required.")

    def reconcile(self):
        """Create missing replicas or remove excess replicas."""

        active = [
            pod for pod in self.pods
            if pod.phase not in (PodPhase.FAILED, PodPhase.SUCCEEDED)
        ]

        while len(active) < self.replicas:
            pod = Pod(
                name=f"{self.name}-{uuid.uuid4().hex[:6]}",
                namespace=self.namespace,
                containers=[
                    Container(
                        name="application",
                        image=self.image
                    )
                ],
                labels=self.labels.copy()
            )
            self.pods.append(pod)
            active.append(pod)

        while len(active) > self.replicas:
            pod = active.pop()
            self.pods.remove(pod)

        self.observed_generation = self.generation

    def rolling_update(self, new_image: str, max_surge: int = 1):
        if not new_image:
            raise ValueError("New image is required.")

        if max_surge < 0:
            raise ValueError("max_surge cannot be negative.")

        self.image = new_image
        self.generation += 1

        for index, pod in enumerate(self.pods):
            pod.name = f"{self.name}-updated-{index + 1}"
            pod.containers = [
                Container(
                    name="application",
                    image=new_image
                )
            ]
            pod.phase = PodPhase.PENDING
            pod.node_name = None
            pod.conditions = {
                "PodScheduled": False,
                "Initialized": True,
                "ContainersReady": False,
                "Ready": False
            }
            pod.events.append("Deployment rolling update applied.")

        self.reconcile()


# ============================================================
# 7. MANIFEST VALIDATION
# ============================================================

def validate_pod_manifest(manifest: dict) -> list[str]:
    errors = []

    if manifest.get("apiVersion") != "v1":
        errors.append("Pod apiVersion must be v1.")

    if manifest.get("kind") != "Pod":
        errors.append("Manifest kind must be Pod.")

    metadata = manifest.get("metadata", {})
    spec = manifest.get("spec", {})

    if not metadata.get("name"):
        errors.append("metadata.name is required.")

    containers = spec.get("containers", [])

    if not containers:
        errors.append("spec.containers must contain at least one container.")

    names = set()

    for container in containers:
        name = container.get("name")
        image = container.get("image")

        if not name:
            errors.append("Every container requires a name.")
        elif name in names:
            errors.append(f"Duplicate container name: {name}")
        else:
            names.add(name)

        if not image:
            errors.append(f"Container {name} requires an image.")

        resources = container.get("resources", {})
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})

        if "cpu" in requests and "cpu" in limits:
            if requests["cpu"] > limits["cpu"]:
                errors.append(f"CPU request exceeds limit for {name}.")

    return errors


# ============================================================
# 8. OPERATIONAL REPORTING
# ============================================================

def cluster_report(pods: list[Pod]) -> dict:
    report = {
        "total": len(pods),
        "pending": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "ready": 0,
        "restarts": 0
    }

    for pod in pods:
        report[pod.phase.value.lower()] += 1

        if pod.evaluate_readiness():
            report["ready"] += 1

        report["restarts"] += sum(
            c.restart_count for c in pod.containers
        )

    return report


# ============================================================
# 9. EXECUTABLE DEMONSTRATION
# ============================================================

def main():
    print("\nKUBERNETES POD MANAGEMENT SIMULATOR")
    print("=" * 55)

    node = Node(
        name="worker-node-01",
        cpu_capacity=8.0,
        memory_capacity_mb=16384,
        labels={"zone": "central", "type": "worker"}
    )

    scheduler = Scheduler([node])

    web_container = Container(
        name="web",
        image="nginx:1.27",
        resources=ResourceRequirements(
            cpu_request=0.5,
            memory_request_mb=256,
            cpu_limit=1.0,
            memory_limit_mb=512
        )
    )

    sidecar = Container(
        name="metrics",
        image="prom/node-exporter:v1.8.2",
        resources=ResourceRequirements(
            cpu_request=0.1,
            memory_request_mb=64,
            cpu_limit=0.2,
            memory_limit_mb=128
        )
    )

    init_container = Container(
        name="initialize",
        image="busybox:1.36"
    )

    pod = Pod(
        name="web-pod-01",
        namespace="production",
        containers=[web_container, sidecar],
        init_containers=[init_container],
        restart_policy=RestartPolicy.ALWAYS,
        labels={
            "app": "web",
            "environment": "production"
        },
        readiness_probe=Probe(
            path="/health",
            initial_delay_seconds=5,
            period_seconds=10
        )
    )

    print("\n1. Scheduling Pod")

    assigned_node = scheduler.schedule(pod)
    print("Assigned node:", assigned_node)

    print("\n2. Executing initialization")
    pod.initialize()

    print("\n3. Starting application containers")
    pod.start()

    print("\n4. Readiness evaluation")
    pod.simulate_readiness_probe(successful=True)
    print("Pod ready:", pod.conditions["Ready"])

    print("\n5. Simulating container failure")
    pod.simulate_container_failure("web", exit_code=1)

    print("Restart count:", web_container.restart_count)
    print("Container state:", web_container.state.value)

    print("\n6. Validating Pod manifest")

    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "web-pod-02",
            "namespace": "production"
        },
        "spec": {
            "containers": [
                {
                    "name": "web",
                    "image": "nginx:1.27",
                    "resources": {
                        "requests": {"cpu": 0.5},
                        "limits": {"cpu": 1.0}
                    }
                }
            ]
        }
    }

    errors = validate_pod_manifest(manifest)
    print("Manifest valid:", not errors)
    print("Validation errors:", errors)

    print("\n7. Creating Deployment")

    deployment = Deployment(
        name="frontend",
        namespace="production",
        replicas=3,
        image="nginx:1.27",
        labels={"app": "frontend"}
    )

    deployment.reconcile()

    print("Desired replicas:", deployment.replicas)
    print("Actual replicas:", len(deployment.pods))

    print("\n8. Performing rolling update")

    deployment.rolling_update(
        new_image="nginx:1.28",
        max_surge=1
    )

    print("Deployment image:", deployment.image)
    print("Deployment generation:", deployment.generation)

    print("\n9. Cluster report")

    all_pods = [pod] + deployment.pods

    print(
        json.dumps(
            cluster_report(all_pods),
            indent=4
        )
    )

    print("\n10. Detailed Pod information")

    print(
        json.dumps(
            pod.to_dict(),
            indent=4
        )
    )

    # Edge-case validation.
    try:
        Container(
            name="invalid",
            image="nginx",
            resources=ResourceRequirements(
                cpu_request=2.0,
                cpu_limit=1.0
            )
        )
    except ValueError as error:
        print("\nExpected validation failure:", error)

    print("\nSimulation completed successfully.")


if __name__ == "__main__":
    main()
