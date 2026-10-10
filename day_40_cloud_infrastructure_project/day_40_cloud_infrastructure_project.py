"""
Cloud Infrastructure Project
A self-contained simulation of a basic virtual cloud infrastructure containing:
compute, networking, storage, and security components.

The implementation models common cloud concepts without requiring an external
cloud provider SDK. It is intentionally provider-neutral so the infrastructure
rules can be studied and tested locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from ipaddress import IPv4Network, IPv4Address
from pathlib import Path
from typing import Dict, List, Optional, Set
import hashlib
import json
import secrets
import tempfile


class InstanceState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    TERMINATED = "terminated"


class StorageType(str, Enum):
    OBJECT = "object"
    BLOCK = "block"


class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    CONNECT = "connect"


@dataclass(frozen=True)
class SecurityRule:
    protocol: str
    port: Optional[int]
    source: str
    action: str = "allow"

    def matches(self, protocol: str, port: Optional[int], source_ip: str) -> bool:
        if self.protocol != protocol and self.protocol != "all":
            return False

        if self.port is not None and port != self.port:
            return False

        if self.source == "0.0.0.0/0":
            source_matches = True
        else:
            source_matches = IPv4Address(source_ip) in IPv4Network(
                self.source, strict=False
            )

        return source_matches


@dataclass
class SecurityGroup:
    name: str
    inbound_rules: List[SecurityRule] = field(default_factory=list)
    outbound_rules: List[SecurityRule] = field(default_factory=list)

    def allows_inbound(
        self, protocol: str, port: Optional[int], source_ip: str
    ) -> bool:
        return any(
            rule.action == "allow"
            and rule.matches(protocol, port, source_ip)
            for rule in self.inbound_rules
        )

    def allows_outbound(
        self, protocol: str, port: Optional[int], destination_ip: str
    ) -> bool:
        return any(
            rule.action == "allow"
            and rule.matches(protocol, port, destination_ip)
            for rule in self.outbound_rules
        )


@dataclass
class Subnet:
    name: str
    cidr: str
    public: bool

    def contains(self, ip: str) -> bool:
        return IPv4Address(ip) in IPv4Network(self.cidr)


@dataclass
class VirtualNetwork:
    name: str
    cidr: str
    subnets: Dict[str, Subnet] = field(default_factory=dict)

    def add_subnet(self, subnet: Subnet) -> None:
        network = IPv4Network(self.cidr)
        candidate = IPv4Network(subnet.cidr)

        if not candidate.subnet_of(network):
            raise ValueError(
                f"Subnet {candidate} is outside virtual network {network}"
            )

        if any(
            candidate.overlaps(IPv4Network(existing.cidr))
            for existing in self.subnets.values()
        ):
            raise ValueError(f"Subnet {candidate} overlaps an existing subnet")

        self.subnets[subnet.name] = subnet

    def find_subnet(self, name: str) -> Subnet:
        try:
            return self.subnets[name]
        except KeyError:
            raise ValueError(f"Unknown subnet: {name}") from None


@dataclass
class ObjectRecord:
    key: str
    content: bytes
    checksum: str
    encrypted: bool


@dataclass
class StorageBucket:
    name: str
    encryption_required: bool = True
    objects: Dict[str, ObjectRecord] = field(default_factory=dict)

    def put(self, key: str, content: bytes, encrypted: bool = True) -> None:
        if not key.strip():
            raise ValueError("Object key cannot be empty")

        if self.encryption_required and not encrypted:
            raise PermissionError(
                "Bucket policy requires encryption for every object"
            )

        checksum = hashlib.sha256(content).hexdigest()
        self.objects[key] = ObjectRecord(
            key=key,
            content=content,
            checksum=checksum,
            encrypted=encrypted,
        )

    def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(f"Object does not exist: {key}")
        return self.objects[key].content

    def delete(self, key: str) -> None:
        if key not in self.objects:
            raise FileNotFoundError(f"Object does not exist: {key}")
        del self.objects[key]


@dataclass
class BlockVolume:
    name: str
    size_gb: int
    attached_instance: Optional[str] = None
    encrypted: bool = True

    def attach(self, instance_id: str) -> None:
        if self.attached_instance is not None:
            raise RuntimeError("Volume is already attached")
        self.attached_instance = instance_id

    def detach(self) -> None:
        self.attached_instance = None


@dataclass
class ComputeInstance:
    instance_id: str
    name: str
    subnet_name: str
    private_ip: str
    security_group: str
    state: InstanceState = InstanceState.STOPPED
    public_ip: Optional[str] = None
    volumes: Set[str] = field(default_factory=set)

    def start(self) -> None:
        if self.state == InstanceState.TERMINATED:
            raise RuntimeError("A terminated instance cannot be restarted")
        self.state = InstanceState.RUNNING

    def stop(self) -> None:
        if self.state == InstanceState.TERMINATED:
            raise RuntimeError("A terminated instance is already unavailable")
        self.state = InstanceState.STOPPED

    def terminate(self) -> None:
        self.state = InstanceState.TERMINATED


@dataclass
class IAMUser:
    username: str
    roles: Set[str] = field(default_factory=set)


class CloudInfrastructure:
    """
    Provider-neutral control plane.

    The class separates resource creation from resource policy evaluation.
    Real cloud platforms perform similar functions through APIs and control
    planes, although their implementations are distributed and substantially
    more sophisticated.
    """

    def __init__(self) -> None:
        self.networks: Dict[str, VirtualNetwork] = {}
        self.security_groups: Dict[str, SecurityGroup] = {}
        self.instances: Dict[str, ComputeInstance] = {}
        self.buckets: Dict[str, StorageBucket] = {}
        self.volumes: Dict[str, BlockVolume] = {}
        self.users: Dict[str, IAMUser] = {}

    def create_network(self, name: str, cidr: str) -> VirtualNetwork:
        if name in self.networks:
            raise ValueError(f"Network already exists: {name}")

        network = VirtualNetwork(name=name, cidr=cidr)
        self.networks[name] = network
        return network

    def create_security_group(
        self,
        name: str,
        inbound: List[SecurityRule],
        outbound: List[SecurityRule],
    ) -> SecurityGroup:
        if name in self.security_groups:
            raise ValueError(f"Security group already exists: {name}")

        group = SecurityGroup(
            name=name,
            inbound_rules=inbound,
            outbound_rules=outbound,
        )
        self.security_groups[name] = group
        return group

    def launch_instance(
        self,
        instance_id: str,
        name: str,
        subnet_name: str,
        private_ip: str,
        security_group: str,
    ) -> ComputeInstance:
        if instance_id in self.instances:
            raise ValueError(f"Instance already exists: {instance_id}")

        subnet = next(
            (
                subnet
                for network in self.networks.values()
                for subnet in network.subnets.values()
                if subnet.name == subnet_name
            ),
            None,
        )

        if subnet is None:
            raise ValueError(f"Unknown subnet: {subnet_name}")

        if not subnet.contains(private_ip):
            raise ValueError(
                f"Private IP {private_ip} does not belong to subnet {subnet.cidr}"
            )

        if security_group not in self.security_groups:
            raise ValueError(f"Unknown security group: {security_group}")

        if any(
            instance.private_ip == private_ip
            and instance.state != InstanceState.TERMINATED
            for instance in self.instances.values()
        ):
            raise ValueError(f"Private IP already assigned: {private_ip}")

        instance = ComputeInstance(
            instance_id=instance_id,
            name=name,
            subnet_name=subnet_name,
            private_ip=private_ip,
            security_group=security_group,
        )

        self.instances[instance_id] = instance
        return instance

    def create_bucket(self, name: str) -> StorageBucket:
        if name in self.buckets:
            raise ValueError(f"Bucket already exists: {name}")

        bucket = StorageBucket(name=name)
        self.buckets[name] = bucket
        return bucket

    def create_volume(
        self,
        name: str,
        size_gb: int,
        encrypted: bool = True,
    ) -> BlockVolume:
        if name in self.volumes:
            raise ValueError(f"Volume already exists: {name}")

        if size_gb <= 0:
            raise ValueError("Volume size must be positive")

        volume = BlockVolume(
            name=name,
            size_gb=size_gb,
            encrypted=encrypted,
        )
        self.volumes[name] = volume
        return volume

    def attach_volume(self, volume_name: str, instance_id: str) -> None:
        volume = self.volumes[volume_name]
        instance = self.instances[instance_id]

        if instance.state == InstanceState.TERMINATED:
            raise RuntimeError("Cannot attach storage to terminated instance")

        volume.attach(instance_id)
        instance.volumes.add(volume_name)

    def create_user(self, username: str, roles: Set[str]) -> IAMUser:
        if username in self.users:
            raise ValueError(f"User already exists: {username}")

        user = IAMUser(username=username, roles=set(roles))
        self.users[username] = user
        return user

    def authorize(
        self,
        username: str,
        resource_type: str,
        action: Action,
    ) -> bool:
        user = self.users.get(username)
        if user is None:
            return False

        role_permissions = {
            "administrator": {
                "compute",
                "network",
                "storage",
                "security",
            },
            "developer": {
                "compute",
                "storage",
            },
            "network-admin": {
                "network",
                "security",
            },
            "auditor": {
                "storage-read",
            },
        }

        for role in user.roles:
            permissions = role_permissions.get(role, set())

            if resource_type in permissions:
                return True

            if (
                resource_type == "storage"
                and action == Action.READ
                and "storage-read" in permissions
            ):
                return True

        return False

    def can_connect(
        self,
        source_instance_id: str,
        destination_instance_id: str,
        protocol: str,
        port: int,
    ) -> bool:
        source = self.instances[source_instance_id]
        destination = self.instances[destination_instance_id]

        if (
            source.state != InstanceState.RUNNING
            or destination.state != InstanceState.RUNNING
        ):
            return False

        group = self.security_groups[destination.security_group]

        return group.allows_inbound(
            protocol=protocol,
            port=port,
            source_ip=source.private_ip,
        )

    def infrastructure_report(self) -> dict:
        return {
            "networks": {
                name: {
                    "cidr": network.cidr,
                    "subnets": {
                        subnet.name: {
                            "cidr": subnet.cidr,
                            "public": subnet.public,
                        }
                        for subnet in network.subnets.values()
                    },
                }
                for name, network in self.networks.items()
            },
            "compute": {
                instance_id: {
                    "name": instance.name,
                    "private_ip": instance.private_ip,
                    "state": instance.state.value,
                    "security_group": instance.security_group,
                    "volumes": sorted(instance.volumes),
                }
                for instance_id, instance in self.instances.items()
            },
            "storage": {
                name: {
                    "objects": len(bucket.objects),
                    "encryption_required": bucket.encryption_required,
                }
                for name, bucket in self.buckets.items()
            },
            "volumes": {
                name: {
                    "size_gb": volume.size_gb,
                    "encrypted": volume.encrypted,
                    "attached_instance": volume.attached_instance,
                }
                for name, volume in self.volumes.items()
            },
        }


def demonstrate_networking(cloud: CloudInfrastructure) -> None:
    network = cloud.create_network("production-vpc", "10.0.0.0/16")

    network.add_subnet(
        Subnet(
            name="public-web",
            cidr="10.0.1.0/24",
            public=True,
        )
    )

    network.add_subnet(
        Subnet(
            name="private-app",
            cidr="10.0.10.0/24",
            public=False,
        )
    )

    network.add_subnet(
        Subnet(
            name="private-data",
            cidr="10.0.20.0/24",
            public=False,
        )
    )

    print("Network CIDR:", network.cidr)
    for subnet in network.subnets.values():
        print(
            f"  {subnet.name}: {subnet.cidr}, "
            f"{'public' if subnet.public else 'private'}"
        )


def demonstrate_security(cloud: CloudInfrastructure) -> None:
    cloud.create_security_group(
        "web-sg",
        inbound=[
            SecurityRule("tcp", 443, "0.0.0.0/0"),
            SecurityRule("tcp", 22, "10.0.10.0/24"),
        ],
        outbound=[
            SecurityRule("tcp", 443, "0.0.0.0/0"),
        ],
    )

    cloud.create_security_group(
        "database-sg",
        inbound=[
            SecurityRule("tcp", 5432, "10.0.10.0/24"),
        ],
        outbound=[
            SecurityRule("all", None, "10.0.0.0/16"),
        ],
    )

    cloud.create_user(
        "platform-admin",
        {"administrator"},
    )

    cloud.create_user(
        "application-developer",
        {"developer"},
    )

    cloud.create_user(
        "security-operator",
        {"network-admin"},
    )

    print(
        "Developer can manage compute:",
        cloud.authorize(
            "application-developer",
            "compute",
            Action.CONNECT,
        ),
    )

    print(
        "Developer can manage network:",
        cloud.authorize(
            "application-developer",
            "network",
            Action.CONNECT,
        ),
    )


def demonstrate_compute(cloud: CloudInfrastructure) -> None:
    web = cloud.launch_instance(
        instance_id="web-01",
        name="web-server",
        subnet_name="public-web",
        private_ip="10.0.1.10",
        security_group="web-sg",
    )

    app = cloud.launch_instance(
        instance_id="app-01",
        name="application-server",
        subnet_name="private-app",
        private_ip="10.0.10.10",
        security_group="web-sg",
    )

    database = cloud.launch_instance(
        instance_id="db-01",
        name="postgres-server",
        subnet_name="private-data",
        private_ip="10.0.20.10",
        security_group="database-sg",
    )

    for instance in (web, app, database):
        instance.start()

    print(
        f"Running instances: "
        f"{sum(i.state == InstanceState.RUNNING for i in cloud.instances.values())}"
    )

    print(
        "Application can reach database on PostgreSQL:",
        cloud.can_connect("app-01", "db-01", "tcp", 5432),
    )

    print(
        "Web server can reach database on PostgreSQL:",
        cloud.can_connect("web-01", "db-01", "tcp", 5432),
    )


def demonstrate_storage(cloud: CloudInfrastructure) -> None:
    bucket = cloud.create_bucket("production-artifacts")
    volume = cloud.create_volume(
        "database-volume",
        size_gb=100,
        encrypted=True,
    )

    cloud.attach_volume("database-volume", "db-01")

    bucket.put(
        "config/production.json",
        b'{"environment":"production","region":"ap-south-1"}',
        encrypted=True,
    )

    retrieved = bucket.get("config/production.json")

    print("Stored object checksum:", bucket.objects["config/production.json"].checksum)
    print("Retrieved object:", retrieved.decode("utf-8"))
    print("Database volume attached to:", volume.attached_instance)

    try:
        bucket.put(
            "secrets/plaintext.txt",
            b"unsafe-secret",
            encrypted=False,
        )
    except PermissionError as exc:
        print("Storage policy blocked write:", exc)


def demonstrate_edge_cases(cloud: CloudInfrastructure) -> None:
    print("\nEdge-case validation:")

    try:
        cloud.networks["production-vpc"].add_subnet(
            Subnet(
                name="overlapping-subnet",
                cidr="10.0.10.128/25",
                public=False,
            )
        )
    except ValueError as exc:
        print("Overlap prevented:", exc)

    try:
        cloud.launch_instance(
            instance_id="invalid-ip",
            name="invalid",
            subnet_name="private-app",
            private_ip="10.0.99.10",
            security_group="web-sg",
        )
    except ValueError as exc:
        print("Invalid IP prevented:", exc)

    try:
        cloud.volumes["database-volume"].attach("web-01")
    except RuntimeError as exc:
        print("Double attachment prevented:", exc)

    try:
        cloud.instances["web-01"].terminate()
        cloud.instances["web-01"].start()
    except RuntimeError as exc:
        print("Invalid lifecycle transition prevented:", exc)


def demonstrate_export(cloud: CloudInfrastructure) -> None:
    report = cloud.infrastructure_report()

    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "infrastructure-report.json"

        path.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print("\nInfrastructure report written to:", path)
        print(path.read_text(encoding="utf-8"))


def main() -> None:
    print("=== Virtual Cloud Infrastructure Simulation ===\n")

    cloud = CloudInfrastructure()

    demonstrate_networking(cloud)
    print()

    demonstrate_security(cloud)
    print()

    demonstrate_compute(cloud)
    print()

    demonstrate_storage(cloud)

    demonstrate_edge_cases(cloud)
    demonstrate_export(cloud)


if __name__ == "__main__":
    main()
