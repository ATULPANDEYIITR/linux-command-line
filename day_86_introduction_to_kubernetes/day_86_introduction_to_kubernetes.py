#!/usr/bin/env python3
"""
Kubernetes Fundamentals and Container Orchestration Simulator

Demonstrates:
- Container orchestration
- Kubernetes cluster architecture
- Control plane and worker nodes
- API server, scheduler, controller manager and etcd
- Pods, containers, deployments and replicas
- Services and service discovery
- Resource requests and limits
- Pod scheduling and node capacity
- Health checks and self-healing
- Rolling updates and scaling
- Cluster validation and operational reporting

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import json
import logging
import random
import uuid

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)

logger = logging.getLogger("kubernetes-simulator")


# ============================================================
# ENUMERATIONS
# ============================================================

class NodeRole(Enum):
    CONTROL_PLANE = "control-plane"
    WORKER = "worker"


class NodeStatus(Enum):
    READY = "Ready"
    NOT_READY = "NotReady"


class PodStatus(Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    FAILED = "Failed"
    SUCCEEDED = "Succeeded"
    TERMINATING = "Terminating"


class DeploymentStatus(Enum):
    ACTIVE = "Active"
    DEGRADED = "Degraded"
    COMPLETED = "Completed"


class ServiceType(Enum):
    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"


# ============================================================
# EXCEPTIONS
# ============================================================

class KubernetesError(Exception):
    """Base exception for cluster operations."""


class ValidationError(KubernetesError):
    pass


class SchedulingError(KubernetesError):
    pass


class ResourceExhaustionError(KubernetesError):
    pass


class ResourceNotFoundError(KubernetesError):
    pass


# ============================================================
# RESOURCE MODEL
# ============================================================

@dataclass(frozen=True)
class ResourceRequirements:
    cpu_millicores: int
    memory_mb: int

    def __post_init__(self):
        if self.cpu_millicores <= 0:
            raise ValidationError("CPU request must be positive.")

        if self.memory_mb <= 0:
            raise ValidationError("Memory request must be positive.")


@dataclass
class Container:
    name: str
    image: str
    resources: ResourceRequirements
    ready: bool = True
    restart_count: int = 0

    def __post_init__(self):
        if not self.name.strip():
            raise ValidationError("Container name cannot be empty.")

        if not self.image.strip():
            raise ValidationError("Container image cannot be empty.")

        if ":" not in self.image and "@sha256:" not in self.image:
            logger.warning(
                "Image %s has no explicit version or digest.",
                self.image
            )


# ============================================================
# NODE MODEL
# ============================================================

@dataclass
class Node:
    name: str
    role: NodeRole
    capacity: ResourceRequirements
    status: NodeStatus = NodeStatus.READY
    allocated_cpu: int = 0
    allocated_memory: int = 0
    pod_ids: set[str] = field(default_factory=set)

    def available_resources(self) -> ResourceRequirements:
        return ResourceRequirements(
            cpu_millicores=self.capacity.cpu_millicores
            - self.allocated_cpu,
            memory_mb=self.capacity.memory_mb
            - self.allocated_memory
        )

    def can_schedule(self, requirements: ResourceRequirements) -> bool:
        if self.role != NodeRole.WORKER:
            return False

        if self.status != NodeStatus.READY:
            return False

        return (
            self.allocated_cpu + requirements.cpu_millicores
            <= self.capacity.cpu_millicores
            and
            self.allocated_memory + requirements.memory_mb
            <= self.capacity.memory_mb
        )

    def allocate(self, pod_id: str, requirements: ResourceRequirements):
        if not self.can_schedule(requirements):
            raise ResourceExhaustionError(
                f"Insufficient resources on node {self.name}"
            )

        self.allocated_cpu += requirements.cpu_millicores
        self.allocated_memory += requirements.memory_mb
        self.pod_ids.add(pod_id)

    def release(self, pod_id: str, requirements: ResourceRequirements):
        if pod_id not in self.pod_ids:
            return

        self.allocated_cpu -= requirements.cpu_millicores
        self.allocated_memory -= requirements.memory_mb
        self.pod_ids.remove(pod_id)

        if self.allocated_cpu < 0 or self.allocated_memory < 0:
            raise KubernetesError("Node resource accounting is inconsistent.")


# ============================================================
# POD MODEL
# ============================================================

@dataclass
class Pod:
    name: str
    containers: list[Container]
    labels: dict[str, str]
    namespace: str = "default"
    pod_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: PodStatus = PodStatus.PENDING
    node_name: Optional[str] = None
    restart_count: int = 0

    def __post_init__(self):
        if not self.name.strip():
            raise ValidationError("Pod name cannot be empty.")

        if not self.containers:
            raise ValidationError("A Pod must contain at least one container.")

        if not self.namespace.strip():
            raise ValidationError("Namespace cannot be empty.")

    @property
    def resource_requirements(self) -> ResourceRequirements:
        # A Pod's scheduling request is the sum of its regular containers.
        return ResourceRequirements(
            cpu_millicores=sum(
                c.resources.cpu_millicores for c in self.containers
            ),
            memory_mb=sum(
                c.resources.memory_mb for c in self.containers
            )
        )

    @property
    def is_ready(self) -> bool:
        return (
            self.status == PodStatus.RUNNING
            and all(container.ready for container in self.containers)
        )


# ============================================================
# DEPLOYMENT MODEL
# ============================================================

@dataclass
class Deployment:
    name: str
    image: str
    replicas: int
    template_labels: dict[str, str]
    resources: ResourceRequirements
    pods: list[str] = field(default_factory=list)
    generation: int = 1
    available_generation: int = 0

    def __post_init__(self):
        if not self.name.strip():
            raise ValidationError("Deployment name cannot be empty.")

        if self.replicas < 0:
            raise ValidationError("Replica count cannot be negative.")

        if not self.template_labels:
            raise ValidationError("Deployment requires labels.")


# ============================================================
# SERVICE MODEL
# ============================================================

@dataclass
class Service:
    name: str
    selector: dict[str, str]
    service_type: ServiceType = ServiceType.CLUSTER_IP
    port: int = 80
    target_port: int = 8080
    cluster_ip: Optional[str] = None

    def __post_init__(self):
        if not self.name.strip():
            raise ValidationError("Service name cannot be empty.")

        if not self.selector:
            raise ValidationError("Service selector cannot be empty.")

        if not (1 <= self.port <= 65535):
            raise ValidationError("Invalid service port.")

        if not (1 <= self.target_port <= 65535):
            raise ValidationError("Invalid target port.")


# ============================================================
# API SERVER
# ============================================================

class APIServer:
    """
    Simplified Kubernetes API server.

    Validates requests and coordinates access to cluster state.
    """

    def __init__(self):
        self.objects: dict[str, object] = {}

    def register(self, resource_type: str, name: str, obj: object):
        key = f"{resource_type}/{name}"

        if key in self.objects:
            raise ValidationError(f"Resource already exists: {key}")

        self.objects[key] = obj
        logger.info("API Server registered %s", key)

    def get(self, resource_type: str, name: str):
        key = f"{resource_type}/{name}"

        if key not in self.objects:
            raise ResourceNotFoundError(key)

        return self.objects[key]

    def delete(self, resource_type: str, name: str):
        key = f"{resource_type}/{name}"

        if key not in self.objects:
            raise ResourceNotFoundError(key)

        return self.objects.pop(key)


# ============================================================
# ETCD SIMULATION
# ============================================================

class Etcd:
    """
    Simplified persistent key-value state store.

    Real etcd provides a distributed, consistent storage system.
    """

    def __init__(self):
        self.store: dict[str, dict] = {}
        self.revision = 0

    def put(self, key: str, value: dict):
        self.revision += 1

        self.store[key] = {
            "revision": self.revision,
            "value": value
        }

    def get(self, key: str) -> Optional[dict]:
        return self.store.get(key)

    def delete(self, key: str):
        self.revision += 1
        self.store.pop(key, None)


# ============================================================
# SCHEDULER
# ============================================================

class Scheduler:
    """
    Assigns pending Pods to suitable worker nodes.

    Scheduling uses a best-fit resource strategy.
    """

    def schedule(self, pod: Pod, nodes: list[Node]) -> Node:
        candidates = [
            node for node in nodes
            if node.can_schedule(pod.resource_requirements)
        ]

        if not candidates:
            raise SchedulingError(
                f"No suitable worker node for Pod {pod.name}"
            )

        requirements = pod.resource_requirements

        # Prefer nodes with the smallest remaining CPU capacity.
        selected = min(
            candidates,
            key=lambda node: (
                node.capacity.cpu_millicores
                - node.allocated_cpu
                - requirements.cpu_millicores
            )
        )

        selected.allocate(pod.pod_id, requirements)

        pod.node_name = selected.name
        pod.status = PodStatus.RUNNING

        logger.info(
            "Scheduled Pod %s on node %s",
            pod.name,
            selected.name
        )

        return selected


# ============================================================
# CONTROLLER MANAGER
# ============================================================

class ControllerManager:
    """
    Reconciles actual cluster state with desired state.

    A Deployment requests a number of replicas. The controller
    creates or removes Pods to match that requirement.
    """

    def __init__(self, cluster: "KubernetesCluster"):
        self.cluster = cluster

    def reconcile(self, deployment: Deployment):
        active_pods = [
            self.cluster.pods[pod_id]
            for pod_id in deployment.pods
            if pod_id in self.cluster.pods
            and self.cluster.pods[pod_id].status
            in (PodStatus.RUNNING, PodStatus.PENDING)
        ]

        while len(active_pods) < deployment.replicas:
            number = len(deployment.pods) + 1

            pod = Pod(
                name=f"{deployment.name}-pod-{number}",
                containers=[
                    Container(
                        name="application",
                        image=deployment.image,
                        resources=deployment.resources
                    )
                ],
                labels=deployment.template_labels.copy()
            )

            self.cluster.create_pod(pod)
            deployment.pods.append(pod.pod_id)
            active_pods.append(pod)

        while len(active_pods) > deployment.replicas:
            pod = active_pods.pop()

            self.cluster.delete_pod(pod.pod_id)
            deployment.pods.remove(pod.pod_id)

        deployment.available_generation = deployment.generation

        return self.cluster.deployment_status(deployment)


# ============================================================
# KUBERNETES CLUSTER
# ============================================================

class KubernetesCluster:

    def __init__(self, name: str):
        if not name.strip():
            raise ValidationError("Cluster name cannot be empty.")

        self.name = name
        self.api_server = APIServer()
        self.etcd = Etcd()
        self.scheduler = Scheduler()

        self.nodes: dict[str, Node] = {}
        self.pods: dict[str, Pod] = {}
        self.deployments: dict[str, Deployment] = {}
        self.services: dict[str, Service] = {}

        self.controller_manager = ControllerManager(self)

    def add_node(self, node: Node):
        if node.name in self.nodes:
            raise ValidationError("Duplicate node name.")

        self.nodes[node.name] = node

        self.etcd.put(
            f"nodes/{node.name}",
            {
                "role": node.role.value,
                "status": node.status.value
            }
        )

        logger.info("Node added: %s", node.name)

    def create_pod(self, pod: Pod):
        self.api_server.register("pod", pod.name, pod)
        self.pods[pod.pod_id] = pod

        self.etcd.put(
            f"pods/{pod.pod_id}",
            {
                "name": pod.name,
                "namespace": pod.namespace,
                "status": pod.status.value
            }
        )

        try:
            self.scheduler.schedule(pod, list(self.nodes.values()))

        except SchedulingError:
            pod.status = PodStatus.PENDING

            logger.warning(
                "Pod %s remains pending.",
                pod.name
            )

    def delete_pod(self, pod_id: str):
        pod = self.pods.get(pod_id)

        if pod is None:
            raise ResourceNotFoundError(pod_id)

        pod.status = PodStatus.TERMINATING

        if pod.node_name:
            node = self.nodes[pod.node_name]

            node.release(
                pod.pod_id,
                pod.resource_requirements
            )

        self.api_server.delete("pod", pod.name)
        self.etcd.delete(f"pods/{pod_id}")

        del self.pods[pod_id]

    def create_deployment(self, deployment: Deployment):
        if deployment.name in self.deployments:
            raise ValidationError("Deployment already exists.")

        self.deployments[deployment.name] = deployment

        self.etcd.put(
            f"deployments/{deployment.name}",
            {
                "replicas": deployment.replicas,
                "generation": deployment.generation
            }
        )

        self.controller_manager.reconcile(deployment)

    def scale_deployment(self, name: str, replicas: int):
        if replicas < 0:
            raise ValidationError("Replicas cannot be negative.")

        deployment = self.deployments.get(name)

        if deployment is None:
            raise ResourceNotFoundError(name)

        deployment.replicas = replicas
        deployment.generation += 1

        self.etcd.put(
            f"deployments/{name}",
            {
                "replicas": replicas,
                "generation": deployment.generation
            }
        )

        return self.controller_manager.reconcile(deployment)

    def create_service(self, service: Service):
        if service.name in self.services:
            raise ValidationError("Service already exists.")

        service.cluster_ip = (
            f"10.96.0.{len(self.services) + 10}"
        )

        self.services[service.name] = service

        self.etcd.put(
            f"services/{service.name}",
            {
                "type": service.service_type.value,
                "cluster_ip": service.cluster_ip,
                "port": service.port
            }
        )

    def service_endpoints(self, service_name: str) -> list[str]:
        service = self.services.get(service_name)

        if service is None:
            raise ResourceNotFoundError(service_name)

        endpoints = []

        for pod in self.pods.values():
            if pod.status != PodStatus.RUNNING or not pod.is_ready:
                continue

            if all(
                pod.labels.get(key) == value
                for key, value in service.selector.items()
            ):
                endpoints.append(pod.pod_id)

        return endpoints

    def deployment_status(self, deployment: Deployment):
        active = sum(
            1 for pod_id in deployment.pods
            if pod_id in self.pods
            and self.pods[pod_id].is_ready
        )

        if active == deployment.replicas:
            return DeploymentStatus.ACTIVE

        if active == 0:
            return DeploymentStatus.DEGRADED

        return DeploymentStatus.DEGRADED

    def simulate_node_failure(self, node_name: str):
        node = self.nodes.get(node_name)

        if node is None:
            raise ResourceNotFoundError(node_name)

        node.status = NodeStatus.NOT_READY

        affected_pods = [
            pod for pod in self.pods.values()
            if pod.node_name == node_name
        ]

        for pod in affected_pods:
            node.release(
                pod.pod_id,
                pod.resource_requirements
            )

            pod.node_name = None
            pod.status = PodStatus.FAILED

        logger.warning(
            "Node %s failed. %d Pods affected.",
            node_name,
            len(affected_pods)
        )

        # Deployments replace failed Pods during reconciliation.
        for deployment in self.deployments.values():
            self.controller_manager.reconcile(deployment)

    def recover_node(self, node_name: str):
        node = self.nodes.get(node_name)

        if node is None:
            raise ResourceNotFoundError(node_name)

        node.status = NodeStatus.READY

        logger.info("Node %s recovered.", node_name)

        for pod in self.pods.values():
            if pod.status == PodStatus.PENDING:
                try:
                    self.scheduler.schedule(
                        pod,
                        list(self.nodes.values())
                    )
                except SchedulingError:
                    continue

    def cluster_report(self) -> dict:
        return {
            "cluster": self.name,
            "nodes": {
                name: {
                    "role": node.role.value,
                    "status": node.status.value,
                    "cpu_allocated": node.allocated_cpu,
                    "cpu_capacity": node.capacity.cpu_millicores,
                    "memory_allocated": node.allocated_memory,
                    "memory_capacity": node.capacity.memory_mb,
                    "pods": len(node.pod_ids)
                }
                for name, node in self.nodes.items()
            },
            "pod_status": {
                status.value: sum(
                    pod.status == status for pod in self.pods.values()
                )
                for status in PodStatus
            },
            "deployments": {
                name: {
                    "desired_replicas": deployment.replicas,
                    "status": self.deployment_status(deployment).value
                }
                for name, deployment in self.deployments.items()
            },
            "services": {
                name: {
                    "cluster_ip": service.cluster_ip,
                    "endpoints": len(self.service_endpoints(name))
                }
                for name, service in self.services.items()
            },
            "etcd_revision": self.etcd.revision
        }


# ============================================================
# EXECUTABLE DEMONSTRATION
# ============================================================

def main():

    cluster = KubernetesCluster("production-cluster")

    # Control-plane node manages cluster operations.
    cluster.add_node(
        Node(
            name="master-01",
            role=NodeRole.CONTROL_PLANE,
            capacity=ResourceRequirements(8000, 16384)
        )
    )

    # Worker nodes execute application Pods.
    cluster.add_node(
        Node(
            name="worker-01",
            role=NodeRole.WORKER,
            capacity=ResourceRequirements(4000, 8192)
        )
    )

    cluster.add_node(
        Node(
            name="worker-02",
            role=NodeRole.WORKER,
            capacity=ResourceRequirements(4000, 8192)
        )
    )

    cluster.add_node(
        Node(
            name="worker-03",
            role=NodeRole.WORKER,
            capacity=ResourceRequirements(2000, 4096)
        )
    )

    deployment = Deployment(
        name="web-application",
        image="nginx:1.27",
        replicas=3,
        template_labels={
            "app": "web",
            "environment": "production"
        },
        resources=ResourceRequirements(
            cpu_millicores=500,
            memory_mb=512
        )
    )

    cluster.create_deployment(deployment)

    service = Service(
        name="web-service",
        selector={"app": "web"},
        service_type=ServiceType.CLUSTER_IP,
        port=80,
        target_port=8080
    )

    cluster.create_service(service)

    print("\nINITIAL CLUSTER REPORT")
    print(json.dumps(cluster.cluster_report(), indent=2))

    print("\nSERVICE ENDPOINTS")
    print(cluster.service_endpoints("web-service"))

    print("\nSCALING DEPLOYMENT TO FIVE REPLICAS")
    cluster.scale_deployment("web-application", 5)

    print(json.dumps(cluster.cluster_report(), indent=2))

    print("\nSIMULATING NODE FAILURE")
    cluster.simulate_node_failure("worker-01")

    print(json.dumps(cluster.cluster_report(), indent=2))

    print("\nRECOVERING NODE")
    cluster.recover_node("worker-01")

    print(json.dumps(cluster.cluster_report(), indent=2))

    # Validate basic resource accounting.
    for node in cluster.nodes.values():
        assert node.allocated_cpu >= 0
        assert node.allocated_memory >= 0
        assert node.allocated_cpu <= node.capacity.cpu_millicores
        assert node.allocated_memory <= node.capacity.memory_mb

    print("\nAll cluster accounting assertions passed.")


if __name__ == "__main__":
    main()
