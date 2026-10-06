#!/usr/bin/env python3
"""
Network Virtualization Laboratory

A self-contained progression from basic virtual-network concepts to a small
software-defined network and overlay-network simulator.

The program models:
- virtual network segments and isolated tenants
- virtual switches and forwarding tables
- VLAN-like logical segmentation
- SDN control-plane decisions
- VXLAN-like overlay encapsulation
- flow installation and expiration
- packet forwarding, validation, and observability

No external packages are required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from time import monotonic
from typing import Dict, List, Optional, Set, Tuple


class PacketAction(Enum):
    FORWARD = "forward"
    DROP = "drop"
    FLOOD = "flood"


@dataclass(frozen=True)
class Endpoint:
    name: str
    mac: str
    ip: IPv4Address
    segment: str
    switch: str
    port: str


@dataclass
class Packet:
    source_mac: str
    destination_mac: str
    source_ip: IPv4Address
    destination_ip: IPv4Address
    segment: str
    payload: str


@dataclass
class FlowRule:
    match_destination_mac: str
    output_port: str
    priority: int
    idle_timeout: float = 60.0
    installed_at: float = field(default_factory=monotonic)
    packet_count: int = 0

    def active(self) -> bool:
        return monotonic() - self.installed_at < self.idle_timeout


class VirtualNetwork:
    """Represents an isolated logical Layer-2/Layer-3 virtual network."""

    def __init__(self, name: str, cidr: str, network_id: int):
        self.name = name
        self.network = IPv4Network(cidr)
        self.network_id = network_id
        self.endpoints: Dict[str, Endpoint] = {}

    def add_endpoint(self, endpoint: Endpoint) -> None:
        if endpoint.ip not in self.network:
            raise ValueError(
                f"{endpoint.ip} does not belong to virtual network {self.network}"
            )
        if endpoint.name in self.endpoints:
            raise ValueError(f"Endpoint {endpoint.name} already exists")
        if any(e.mac == endpoint.mac for e in self.endpoints.values()):
            raise ValueError(f"MAC address {endpoint.mac} is already registered")
        self.endpoints[endpoint.name] = endpoint

    def contains(self, ip: IPv4Address) -> bool:
        return ip in self.network


class VirtualSwitch:
    """
    A virtual switch owns ports, learns source MAC addresses, and uses flow
    rules supplied by the SDN controller before falling back to flooding.
    """

    def __init__(self, name: str):
        self.name = name
        self.ports: Dict[str, str] = {}
        self.mac_table: Dict[str, str] = {}
        self.flow_table: List[FlowRule] = []
        self.forwarded_packets = 0
        self.dropped_packets = 0

    def connect(self, port: str, endpoint_or_link: str) -> None:
        if port in self.ports:
            raise ValueError(f"Port {port} already exists on {self.name}")
        self.ports[port] = endpoint_or_link

    def learn(self, source_mac: str, ingress_port: str) -> None:
        self.mac_table[source_mac] = ingress_port

    def install_flow(self, rule: FlowRule) -> None:
        self.flow_table.append(rule)
        self.flow_table.sort(key=lambda item: item.priority, reverse=True)

    def remove_expired_flows(self) -> None:
        self.flow_table = [rule for rule in self.flow_table if rule.active()]

    def lookup_flow(self, destination_mac: str) -> Optional[FlowRule]:
        self.remove_expired_flows()
        for rule in self.flow_table:
            if rule.match_destination_mac == destination_mac:
                return rule
        return None

    def forward(
        self, packet: Packet, ingress_port: str
    ) -> Tuple[PacketAction, Optional[str]]:
        if ingress_port not in self.ports:
            self.dropped_packets += 1
            return PacketAction.DROP, None

        self.learn(packet.source_mac, ingress_port)

        flow = self.lookup_flow(packet.destination_mac)
        if flow is not None:
            flow.packet_count += 1
            self.forwarded_packets += 1
            return PacketAction.FORWARD, flow.output_port

        learned_port = self.mac_table.get(packet.destination_mac)
        if learned_port and learned_port != ingress_port:
            self.forwarded_packets += 1
            return PacketAction.FORWARD, learned_port

        self.forwarded_packets += 1
        return PacketAction.FLOOD, None


@dataclass(frozen=True)
class OverlayFrame:
    """
    A simplified VXLAN-like frame.

    Real VXLAN places an inner Ethernet frame inside UDP/IP transport and uses
    a 24-bit VNI. This model keeps the VNI and inner packet explicit while
    omitting wire-level checksum and binary serialization details.
    """

    outer_source: str
    outer_destination: str
    vni: int
    inner_packet: Packet


class SdnController:
    """
    The controller represents the SDN control plane.

    It does not forward every packet itself. It computes a policy and
    installs forwarding rules into switches, separating control decisions from
    the data plane.
    """

    def __init__(self):
        self.registered_switches: Dict[str, VirtualSwitch] = {}
        self.segment_switches: Dict[str, Set[str]] = {}
        self.audit_log: List[str] = []

    def register_switch(self, switch: VirtualSwitch) -> None:
        self.registered_switches[switch.name] = switch

    def attach_segment(self, segment: VirtualNetwork, switch_name: str) -> None:
        if switch_name not in self.registered_switches:
            raise ValueError(f"Unknown switch {switch_name}")
        self.segment_switches.setdefault(segment.name, set()).add(switch_name)

    def install_destination_flow(
        self,
        switch_name: str,
        destination_mac: str,
        output_port: str,
        priority: int = 100,
    ) -> None:
        switch = self.registered_switches[switch_name]
        if output_port not in switch.ports:
            raise ValueError(f"Unknown output port {output_port} on {switch_name}")

        switch.install_flow(
            FlowRule(
                match_destination_mac=destination_mac,
                output_port=output_port,
                priority=priority,
            )
        )
        self.audit_log.append(
            f"Installed flow on {switch_name}: "
            f"{destination_mac} -> {output_port}"
        )

    def evaluate_policy(
        self, source: Endpoint, destination: Endpoint
    ) -> bool:
        """
        This example enforces tenant isolation.

        A production controller would generally evaluate richer policy
        objects, identity, ACLs, security groups, service chains, and
        topology state rather than only comparing segment names.
        """
        allowed = source.segment == destination.segment
        self.audit_log.append(
            f"Policy {source.name} -> {destination.name}: "
            f"{'ALLOW' if allowed else 'DENY'}"
        )
        return allowed


class OverlayNetwork:
    """Connects isolated Layer-2 segments through an overlay VNI."""

    def __init__(self, name: str):
        self.name = name
        self.vni_by_segment: Dict[str, int] = {}
        self.vtep_by_switch: Dict[str, str] = {}

    def add_segment(self, segment: VirtualNetwork, vni: int) -> None:
        if not 1 <= vni <= 16_777_215:
            raise ValueError("A VXLAN VNI must fit in 24 bits")
        if segment.name in self.vni_by_segment:
            raise ValueError(f"Segment {segment.name} already has a VNI")
        if vni in self.vni_by_segment.values():
            raise ValueError(f"VNI {vni} is already assigned")
        self.vni_by_segment[segment.name] = vni

    def add_vtep(self, switch_name: str, address: str) -> None:
        IPv4Address(address)
        self.vtep_by_switch[switch_name] = address

    def encapsulate(
        self,
        packet: Packet,
        source_switch: str,
        destination_switch: str,
    ) -> OverlayFrame:
        if packet.segment not in self.vni_by_segment:
            raise ValueError(f"No VNI configured for {packet.segment}")
        if source_switch not in self.vtep_by_switch:
            raise ValueError(f"No source VTEP for {source_switch}")
        if destination_switch not in self.vtep_by_switch:
            raise ValueError(f"No destination VTEP for {destination_switch}")

        return OverlayFrame(
            outer_source=self.vtep_by_switch[source_switch],
            outer_destination=self.vtep_by_switch[destination_switch],
            vni=self.vni_by_segment[packet.segment],
            inner_packet=packet,
        )

    def decapsulate(
        self, frame: OverlayFrame, expected_segment: str
    ) -> Packet:
        expected_vni = self.vni_by_segment.get(expected_segment)
        if expected_vni != frame.vni:
            raise PermissionError(
                "Overlay VNI does not map to the requested virtual segment"
            )
        return frame.inner_packet


def build_lab() -> Tuple[
    Dict[str, VirtualNetwork],
    Dict[str, VirtualSwitch],
    Dict[str, Endpoint],
    SdnController,
    OverlayNetwork,
]:
    tenant_a = VirtualNetwork("tenant-a", "10.10.10.0/24", 10)
    tenant_b = VirtualNetwork("tenant-b", "10.20.20.0/24", 20)

    switch_a = VirtualSwitch("vswitch-a")
    switch_b = VirtualSwitch("vswitch-b")

    switch_a.connect("p1", "web-a")
    switch_a.connect("p2", "db-a")
    switch_b.connect("p1", "web-b")
    switch_b.connect("p2", "db-b")

    endpoints = {
        "web-a": Endpoint(
            "web-a", "02:00:00:00:00:01", IPv4Address("10.10.10.10"),
            "tenant-a", "vswitch-a", "p1"
        ),
        "db-a": Endpoint(
            "db-a", "02:00:00:00:00:02", IPv4Address("10.10.10.20"),
            "tenant-a", "vswitch-a", "p2"
        ),
        "web-b": Endpoint(
            "web-b", "02:00:00:00:00:11", IPv4Address("10.20.20.10"),
            "tenant-b", "vswitch-b", "p1"
        ),
        "db-b": Endpoint(
            "db-b", "02:00:00:00:00:12", IPv4Address("10.20.20.20"),
            "tenant-b", "vswitch-b", "p2"
        ),
    }

    tenant_a.add_endpoint(endpoints["web-a"])
    tenant_a.add_endpoint(endpoints["db-a"])
    tenant_b.add_endpoint(endpoints["web-b"])
    tenant_b.add_endpoint(endpoints["db-b"])

    controller = SdnController()
    controller.register_switch(switch_a)
    controller.register_switch(switch_b)
    controller.attach_segment(tenant_a, "vswitch-a")
    controller.attach_segment(tenant_b, "vswitch-b")

    overlay = OverlayNetwork("datacenter-overlay")
    overlay.add_segment(tenant_a, 1010)
    overlay.add_segment(tenant_b, 2020)
    overlay.add_vtep("vswitch-a", "192.0.2.10")
    overlay.add_vtep("vswitch-b", "192.0.2.20")

    return (
        {"tenant-a": tenant_a, "tenant-b": tenant_b},
        {"vswitch-a": switch_a, "vswitch-b": switch_b},
        endpoints,
        controller,
        overlay,
    )


def send_packet(
    source: Endpoint,
    destination: Endpoint,
    switches: Dict[str, VirtualSwitch],
    controller: SdnController,
    payload: str,
) -> None:
    print(f"\n{source.name} -> {destination.name}")

    if not controller.evaluate_policy(source, destination):
        print("  result: DROP (tenant isolation policy)")
        return

    packet = Packet(
        source_mac=source.mac,
        destination_mac=destination.mac,
        source_ip=source.ip,
        destination_ip=destination.ip,
        segment=source.segment,
        payload=payload,
    )

    switch = switches[source.switch]
    action, output_port = switch.forward(packet, source.port)

    if action is PacketAction.FORWARD:
        print(f"  data plane: FORWARD via {source.switch}:{output_port}")
    elif action is PacketAction.FLOOD:
        print(f"  data plane: FLOOD from {source.switch}")
    else:
        print("  data plane: DROP")


def demonstrate_virtual_switches(
    endpoints: Dict[str, Endpoint],
    switches: Dict[str, VirtualSwitch],
    controller: SdnController,
) -> None:
    print("=== Virtual Switch and SDN Flow Demonstration ===")

    source = endpoints["web-a"]
    destination = endpoints["db-a"]

    send_packet(source, destination, switches, controller, "first request")
    send_packet(source, destination, switches, controller, "learned destination")

    controller.install_destination_flow(
        switch_name="vswitch-a",
        destination_mac=destination.mac,
        output_port=destination.port,
    )

    send_packet(
        source,
        destination,
        switches,
        controller,
        "controller-programmed request",
    )

    send_packet(
        endpoints["web-a"],
        endpoints["web-b"],
        switches,
        controller,
        "cross-tenant request",
    )


def demonstrate_overlay(
    endpoints: Dict[str, Endpoint],
    overlay: OverlayNetwork,
) -> None:
    print("\n=== Network Overlay Demonstration ===")

    source = endpoints["web-a"]
    destination = endpoints["db-a"]

    packet = Packet(
        source_mac=source.mac,
        destination_mac=destination.mac,
        source_ip=source.ip,
        destination_ip=destination.ip,
        segment=source.segment,
        payload="database query",
    )

    frame = overlay.encapsulate(packet, source.switch, "vswitch-b")
    print(f"inner segment: {packet.segment}")
    print(f"assigned VNI: {frame.vni}")
    print(f"outer transport: {frame.outer_source} -> {frame.outer_destination}")

    recovered = overlay.decapsulate(frame, "tenant-a")
    print(
        f"decapsulation: {recovered.source_ip} -> "
        f"{recovered.destination_ip}"
    )

    try:
        overlay.decapsulate(frame, "tenant-b")
    except PermissionError as exc:
        print(f"security check: {exc}")


def demonstrate_validation(
    networks: Dict[str, VirtualNetwork],
    endpoints: Dict[str, Endpoint],
) -> None:
    print("\n=== Virtual Network Validation ===")

    checks = [
        ("tenant-a contains 10.10.10.20",
         networks["tenant-a"].contains(IPv4Address("10.10.10.20"))),
        ("tenant-a contains 10.20.20.20",
         networks["tenant-a"].contains(IPv4Address("10.20.20.20"))),
    ]

    for label, result in checks:
        print(f"{label}: {result}")

    invalid = Endpoint(
        "invalid",
        "02:00:00:00:00:99",
        IPv4Address("10.20.20.99"),
        "tenant-a",
        "vswitch-a",
        "p9",
    )

    try:
        networks["tenant-a"].add_endpoint(invalid)
    except ValueError as exc:
        print(f"validation rejected invalid endpoint: {exc}")

    print(
        f"registered endpoints: "
        f"{', '.join(sorted(endpoints))}"
    )


def print_observability(
    switches: Dict[str, VirtualSwitch],
    controller: SdnController,
) -> None:
    print("\n=== Observability ===")

    for switch in switches.values():
        print(
            f"{switch.name}: ports={len(switch.ports)}, "
            f"MAC entries={len(switch.mac_table)}, "
            f"flows={len(switch.flow_table)}, "
            f"forwarded={switch.forwarded_packets}, "
            f"dropped={switch.dropped_packets}"
        )

    print("controller audit:")
    for event in controller.audit_log:
        print(f"  {event}")


def main() -> None:
    networks, switches, endpoints, controller, overlay = build_lab()

    demonstrate_validation(networks, endpoints)
    demonstrate_virtual_switches(endpoints, switches, controller)
    demonstrate_overlay(endpoints, overlay)
    print_observability(switches, controller)


if __name__ == "__main__":
    main()
