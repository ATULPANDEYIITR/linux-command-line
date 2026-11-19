#!/usr/bin/env python3
"""
Docker Networking: Bridge Networks, Host Networking, Communication,
Port Publishing, DNS Resolution, and Network Isolation.

Self-contained Docker networking simulator using Python standard library.
The simulator models network behavior without requiring a Docker daemon.
"""

from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("docker-networking")


class NetworkMode(Enum):
    BRIDGE = "bridge"
    HOST = "host"
    NONE = "none"


class NetworkError(Exception):
    """Base exception for network simulation errors."""


class NetworkNotFoundError(NetworkError):
    pass


class ContainerNotFoundError(NetworkError):
    pass


class ConnectivityError(NetworkError):
    pass


class PortConflictError(NetworkError):
    pass


@dataclass
class Network:
    name: str
    subnet: str
    gateway: Optional[str] = None
    internal: bool = False
    members: set[str] = field(default_factory=set)

    def __post_init__(self):
        network = ipaddress.ip_network(self.subnet, strict=True)

        if network.version != 4:
            raise ValueError("Only IPv4 networks are supported.")

        if network.prefixlen > 29:
            raise ValueError("Subnet must provide sufficient host addresses.")

        if self.gateway is None:
            self.gateway = str(next(network.hosts()))

        gateway = ipaddress.ip_address(self.gateway)

        if gateway not in network or gateway == network.network_address:
            raise ValueError("Gateway must belong to the subnet.")

        self._network = network

    def contains(self, address: str) -> bool:
        return ipaddress.ip_address(address) in self._network

    def allocate_ip(self) -> str:
        occupied = set()

        for address in self._network.hosts():
            occupied.add(str(address))

        for candidate in self._network.hosts():
            value = str(candidate)

            if value == self.gateway:
                continue

            used = False

            for container_ip in occupied:
                if container_ip == value:
                    used = True
                    break

            if not used:
                return value

        raise NetworkError(f"No available addresses in {self.name}.")


@dataclass
class Container:
    container_id: str
    name: str
    image: str
    mode: NetworkMode = NetworkMode.BRIDGE
    ips: dict[str, str] = field(default_factory=dict)
    exposed_ports: set[int] = field(default_factory=set)
    running: bool = True

    def __post_init__(self):
        if not self.container_id or not self.name:
            raise ValueError("Container ID and name are required.")

        if not self.image:
            raise ValueError("Container image is required.")

    @property
    def primary_ip(self) -> Optional[str]:
        return next(iter(self.ips.values()), None)


@dataclass(frozen=True)
class PortMapping:
    host_ip: str
    host_port: int
    container_name: str
    container_port: int
    protocol: str = "tcp"


class DockerNetworkSimulator:
    """
    Models:
    - User-defined bridge networks.
    - Container IP allocation.
    - Container-to-container connectivity.
    - Network-scoped DNS.
    - Host networking.
    - Port publishing.
    - Internal network isolation.
    - Container lifecycle.
    """

    def __init__(self):
        self.networks: dict[str, Network] = {}
        self.containers: dict[str, Container] = {}
        self.port_mappings: dict[tuple, PortMapping] = {}
        self.events: list[dict] = []

    def _event(self, action: str, **details):
        event = {
            "action": action,
            **details
        }
        self.events.append(event)
        logger.info("%s", event)

    def create_network(
        self,
        name: str,
        subnet: str,
        internal: bool = False,
        gateway: Optional[str] = None
    ) -> Network:

        if name in self.networks:
            raise NetworkError(f"Network already exists: {name}")

        network = Network(
            name=name,
            subnet=subnet,
            gateway=gateway,
            internal=internal
        )

        for existing in self.networks.values():
            if network._network.overlaps(existing._network):
                raise NetworkError(
                    f"Subnet overlaps with network {existing.name}."
                )

        self.networks[name] = network

        self._event(
            "network_created",
            name=name,
            subnet=subnet,
            internal=internal
        )

        return network

    def create_container(
        self,
        container_id: str,
        name: str,
        image: str,
        network_name: Optional[str] = None,
        mode: NetworkMode = NetworkMode.BRIDGE,
        exposed_ports: Optional[set[int]] = None
    ) -> Container:

        if name in self.containers:
            raise NetworkError(f"Container already exists: {name}")

        if mode == NetworkMode.HOST and network_name is not None:
            raise NetworkError(
                "Host networking cannot be combined with a bridge network."
            )

        if mode == NetworkMode.NONE and network_name is not None:
            raise NetworkError(
                "None networking cannot be combined with a bridge network."
            )

        container = Container(
            container_id=container_id,
            name=name,
            image=image,
            mode=mode,
            exposed_ports=exposed_ports or set()
        )

        for port in container.exposed_ports:
            self._validate_port(port)

        if mode == NetworkMode.BRIDGE:
            if network_name is None:
                raise NetworkError(
                    "Bridge containers require a network."
                )

            network = self.get_network(network_name)
            address = self._allocate_ip(network)

            container.ips[network_name] = address
            network.members.add(name)

        self.containers[name] = container

        self._event(
            "container_created",
            name=name,
            mode=mode.value,
            ips=container.ips
        )

        return container

    @staticmethod
    def _validate_port(port: int):
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"Invalid TCP/UDP port: {port}")

    def _allocate_ip(self, network: Network) -> str:
        used = {
            address
            for container in self.containers.values()
            for address in container.ips.values()
        }

        for address in network._network.hosts():
            value = str(address)

            if value != network.gateway and value not in used:
                return value

        raise NetworkError("Network address pool exhausted.")

    def get_network(self, name: str) -> Network:
        if name not in self.networks:
            raise NetworkNotFoundError(name)

        return self.networks[name]

    def get_container(self, name: str) -> Container:
        if name not in self.containers:
            raise ContainerNotFoundError(name)

        container = self.containers[name]

        if not container.running:
            raise ConnectivityError(f"{name} is not running.")

        return container

    def connect_container(
        self,
        container_name: str,
        network_name: str
    ) -> str:

        container = self.get_container(container_name)
        network = self.get_network(network_name)

        if container.mode != NetworkMode.BRIDGE:
            raise NetworkError(
                "Only bridge-mode containers can join user-defined networks."
            )

        if network_name in container.ips:
            raise NetworkError("Container is already connected.")

        address = self._allocate_ip(network)

        container.ips[network_name] = address
        network.members.add(container_name)

        self._event(
            "container_connected",
            container=container_name,
            network=network_name,
            ip=address
        )

        return address

    def disconnect_container(
        self,
        container_name: str,
        network_name: str
    ):
        container = self.get_container(container_name)
        network = self.get_network(network_name)

        if network_name not in container.ips:
            raise NetworkError("Container is not connected.")

        del container.ips[network_name]
        network.members.discard(container_name)

        self._event(
            "container_disconnected",
            container=container_name,
            network=network_name
        )

    def resolve_dns(
        self,
        source_name: str,
        target_name: str,
        network_name: str
    ) -> str:

        source = self.get_container(source_name)
        target = self.get_container(target_name)
        network = self.get_network(network_name)

        if source.mode != NetworkMode.BRIDGE:
            raise ConnectivityError(
                "DNS resolution requires a bridge-network participant."
            )

        if (
            network_name not in source.ips
            or network_name not in target.ips
        ):
            raise ConnectivityError(
                "Containers do not share the requested network."
            )

        if target_name not in network.members:
            raise ConnectivityError("DNS record not available.")

        address = target.ips[network_name]

        self._event(
            "dns_resolved",
            source=source_name,
            target=target_name,
            address=address
        )

        return address

    def can_communicate(
        self,
        source_name: str,
        target_name: str,
        port: int
    ) -> bool:

        self._validate_port(port)

        source = self.get_container(source_name)
        target = self.get_container(target_name)

        if source_name == target_name:
            return True

        if (
            source.mode == NetworkMode.NONE
            or target.mode == NetworkMode.NONE
        ):
            return False

        if (
            source.mode == NetworkMode.HOST
            and target.mode == NetworkMode.HOST
        ):
            return True

        if source.mode == NetworkMode.HOST:
            return False

        if target.mode == NetworkMode.HOST:
            return False

        shared_networks = set(source.ips) & set(target.ips)

        for network_name in shared_networks:
            network = self.get_network(network_name)

            if (
                source_name in network.members
                and target_name in network.members
            ):
                return port in target.exposed_ports

        return False

    def publish_port(
        self,
        container_name: str,
        host_port: int,
        container_port: int,
        host_ip: str = "0.0.0.0",
        protocol: str = "tcp"
    ) -> PortMapping:

        container = self.get_container(container_name)

        self._validate_port(host_port)
        self._validate_port(container_port)

        if protocol not in {"tcp", "udp"}:
            raise ValueError("Protocol must be tcp or udp.")

        if container.mode == NetworkMode.NONE:
            raise NetworkError("Cannot publish ports for none-mode container.")

        if container.mode == NetworkMode.HOST:
            raise NetworkError(
                "Port publishing is not used with host networking."
            )

        if container_port not in container.exposed_ports:
            raise NetworkError(
                "Container port must be declared as exposed."
            )

        try:
            ipaddress.ip_address(host_ip)
        except ValueError as exc:
            raise ValueError("Invalid host IP address.") from exc

        key = (host_ip, host_port, protocol)

        wildcard_key = ("0.0.0.0", host_port, protocol)
        specific_conflict = (
            host_ip != "0.0.0.0"
            and wildcard_key in self.port_mappings
        )

        wildcard_conflict = (
            host_ip == "0.0.0.0"
            and any(
                existing_port == host_port
                and existing_protocol == protocol
                for existing_ip, existing_port, existing_protocol
                in self.port_mappings
            )
        )

        if (
            key in self.port_mappings
            or specific_conflict
            or wildcard_conflict
        ):
            raise PortConflictError(
                f"Host port already allocated: {host_port}/{protocol}"
            )

        mapping = PortMapping(
            host_ip=host_ip,
            host_port=host_port,
            container_name=container_name,
            container_port=container_port,
            protocol=protocol
        )

        self.port_mappings[key] = mapping

        self._event(
            "port_published",
            container=container_name,
            host_port=host_port,
            container_port=container_port,
            protocol=protocol
        )

        return mapping

    def remove_port_mapping(
        self,
        host_ip: str,
        host_port: int,
        protocol: str = "tcp"
    ):
        key = (host_ip, host_port, protocol)

        if key not in self.port_mappings:
            raise NetworkError("Port mapping does not exist.")

        del self.port_mappings[key]

    def external_access(
        self,
        host_port: int,
        container_port: int,
        protocol: str = "tcp"
    ) -> bool:

        self._validate_port(host_port)
        self._validate_port(container_port)

        if protocol not in {"tcp", "udp"}:
            raise ValueError("Unsupported protocol.")

        for mapping in self.port_mappings.values():
            if (
                mapping.host_port == host_port
                and mapping.container_port == container_port
                and mapping.protocol == protocol
            ):
                target = self.get_container(mapping.container_name)

                return (
                    target.running
                    and mapping.container_port in target.exposed_ports
                )

        return False

    def inspect(self, container_name: str) -> dict:
        container = self.get_container(container_name)

        return {
            "name": container.name,
            "image": container.image,
            "mode": container.mode.value,
            "running": container.running,
            "networks": container.ips.copy(),
            "exposed_ports": sorted(container.exposed_ports)
        }

    def stop_container(self, container_name: str):
        container = self.get_container(container_name)
        container.running = False

        for network_name in list(container.ips):
            self.networks[network_name].members.discard(container_name)

        self._event("container_stopped", container=container_name)

    def start_container(self, container_name: str):
        container = self.containers.get(container_name)

        if container is None:
            raise ContainerNotFoundError(container_name)

        if container.running:
            raise NetworkError("Container is already running.")

        for network_name in container.ips:
            self.networks[network_name].members.add(container_name)

        container.running = True

        self._event("container_started", container=container_name)

    def network_report(self) -> dict:
        return {
            name: {
                "subnet": network.subnet,
                "gateway": network.gateway,
                "internal": network.internal,
                "members": sorted(network.members)
            }
            for name, network in self.networks.items()
        }


def run_demonstration():
    simulator = DockerNetworkSimulator()

    # Separate frontend and backend network segments.
    simulator.create_network(
        "frontend-net",
        "172.20.0.0/24"
    )

    simulator.create_network(
        "backend-net",
        "172.21.0.0/24",
        internal=True
    )

    # Frontend has access only to the frontend network.
    simulator.create_container(
        "c001",
        "frontend",
        "nginx:stable",
        "frontend-net",
        exposed_ports={80}
    )

    # API joins both networks to communicate with both tiers.
    simulator.create_container(
        "c002",
        "api",
        "python:3.13-slim",
        "frontend-net",
        exposed_ports={8000}
    )

    simulator.connect_container("api", "backend-net")

    # Database is isolated on the backend network.
    simulator.create_container(
        "c003",
        "database",
        "postgres:18",
        "backend-net",
        exposed_ports={5432}
    )

    # Host-mode container shares the host network namespace.
    simulator.create_container(
        "c004",
        "host-monitor",
        "monitor:latest",
        mode=NetworkMode.HOST
    )

    print("\nNETWORK REPORT")
    print(json.dumps(simulator.network_report(), indent=2))

    print("\nCONTAINER INSPECTION")
    print(json.dumps(simulator.inspect("api"), indent=2))

    print("\nDNS RESOLUTION")

    database_ip = simulator.resolve_dns(
        "api",
        "database",
        "backend-net"
    )

    print(f"database -> {database_ip}")

    print("\nCONNECTIVITY TESTS")

    assert simulator.can_communicate(
        "frontend", "api", 8000
    )

    assert simulator.can_communicate(
        "api", "database", 5432
    )

    assert not simulator.can_communicate(
        "frontend", "database", 5432
    )

    print("Frontend -> API: allowed")
    print("API -> Database: allowed")
    print("Frontend -> Database: denied")

    print("\nPORT PUBLISHING")

    simulator.publish_port(
        "frontend",
        host_port=8080,
        container_port=80,
        host_ip="127.0.0.1"
    )

    assert simulator.external_access(8080, 80)
    print("127.0.0.1:8080 -> frontend:80")

    print("\nISOLATION TESTS")

    try:
        simulator.resolve_dns(
            "frontend",
            "database",
            "backend-net"
        )
    except ConnectivityError as error:
        print(f"Expected isolation: {error}")

    try:
        simulator.publish_port(
            "database",
            8080,
            5432
        )
    except PortConflictError:
        print("Port conflict detected.")

    print("\nFINAL EVENTS")
    print(f"Recorded events: {len(simulator.events)}")

    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run_demonstration()
