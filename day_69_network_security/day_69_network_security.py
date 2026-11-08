#!/usr/bin/env python3
"""
Network Security: Firewalls, Security Groups, Network ACLs, and Traffic Filtering.

Demonstrates:
- Packet filtering and firewall rules
- Stateful and stateless traffic inspection
- Security groups
- Network ACLs
- CIDR and IP address validation
- Port and protocol restrictions
- Rule priority and default-deny behavior
- Connection tracking
- Security event logging
- JSON policy persistence
- Automated security tests

Python 3.10+
Uses only the Python standard library.
"""

from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)

logger = logging.getLogger("network-security")


# ---------------------------------------------------------
# Domain Types
# ---------------------------------------------------------

class Protocol(str, Enum):
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    ANY = "ANY"


class Direction(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class Action(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class DecisionReason(str, Enum):
    RULE_MATCH = "RULE_MATCH"
    DEFAULT_DENY = "DEFAULT_DENY"
    INVALID_PACKET = "INVALID_PACKET"
    STATEFUL_RETURN = "STATEFUL_RETURN"


# ---------------------------------------------------------
# Packet Model
# ---------------------------------------------------------

@dataclass(frozen=True)
class Packet:
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    protocol: Protocol
    direction: Direction

    def validate(self) -> None:
        ipaddress.ip_address(self.source_ip)
        ipaddress.ip_address(self.destination_ip)

        if not isinstance(self.protocol, Protocol):
            raise ValueError("Unsupported protocol")

        if not isinstance(self.direction, Direction):
            raise ValueError("Unsupported direction")

        if not 0 <= self.source_port <= 65535:
            raise ValueError("Invalid source port")

        if not 0 <= self.destination_port <= 65535:
            raise ValueError("Invalid destination port")

        if self.protocol == Protocol.ICMP:
            if self.source_port != 0 or self.destination_port != 0:
                raise ValueError("ICMP packets must use zero ports")


# ---------------------------------------------------------
# Firewall Rule
# ---------------------------------------------------------

@dataclass(frozen=True)
class FirewallRule:
    rule_id: str
    name: str
    source_cidr: str
    destination_cidr: str
    protocol: Protocol
    direction: Direction
    action: Action
    priority: int
    port_start: int = 0
    port_end: int = 65535
    enabled: bool = True

    def __post_init__(self) -> None:
        ipaddress.ip_network(self.source_cidr, strict=False)
        ipaddress.ip_network(self.destination_cidr, strict=False)

        if not self.rule_id.strip():
            raise ValueError("Rule ID cannot be empty")

        if self.priority < 0:
            raise ValueError("Priority cannot be negative")

        if not 0 <= self.port_start <= self.port_end <= 65535:
            raise ValueError("Invalid port range")

        if self.protocol == Protocol.ICMP:
            if self.port_start != 0 or self.port_end != 65535:
                raise ValueError("ICMP rules do not use port ranges")

    def matches(self, packet: Packet) -> bool:
        if not self.enabled:
            return False

        if self.direction != packet.direction:
            return False

        if self.protocol not in (Protocol.ANY, packet.protocol):
            return False

        source = ipaddress.ip_address(packet.source_ip)
        destination = ipaddress.ip_address(packet.destination_ip)

        if source.version != ipaddress.ip_network(
            self.source_cidr, strict=False
        ).version:
            return False

        if destination.version != ipaddress.ip_network(
            self.destination_cidr, strict=False
        ).version:
            return False

        if source not in ipaddress.ip_network(
            self.source_cidr, strict=False
        ):
            return False

        if destination not in ipaddress.ip_network(
            self.destination_cidr, strict=False
        ):
            return False

        if packet.protocol == Protocol.ICMP:
            return True

        return self.port_start <= packet.destination_port <= self.port_end


# ---------------------------------------------------------
# Security Decision
# ---------------------------------------------------------

@dataclass
class SecurityDecision:
    allowed: bool
    action: Action
    reason: DecisionReason
    matched_rule: Optional[str]
    message: str


# ---------------------------------------------------------
# Connection Tracking
# ---------------------------------------------------------

class ConnectionTracker:
    """
    Tracks established TCP/UDP flows.

    A production implementation must additionally handle:
    connection expiration, TCP state transitions, resource
    limits, spoofing protection, and concurrent access.
    """

    def __init__(self):
        self.connections: set[tuple] = set()

    @staticmethod
    def connection_key(packet: Packet) -> tuple:
        return (
            packet.source_ip,
            packet.source_port,
            packet.destination_ip,
            packet.destination_port,
            packet.protocol
        )

    @staticmethod
    def reverse_key(packet: Packet) -> tuple:
        return (
            packet.destination_ip,
            packet.destination_port,
            packet.source_ip,
            packet.source_port,
            packet.protocol
        )

    def establish(self, packet: Packet) -> None:
        if packet.protocol in (Protocol.TCP, Protocol.UDP):
            self.connections.add(self.connection_key(packet))

    def is_established(self, packet: Packet) -> bool:
        return self.reverse_key(packet) in self.connections

    def close(self, packet: Packet) -> None:
        self.connections.discard(self.connection_key(packet))


# ---------------------------------------------------------
# Stateful Firewall
# ---------------------------------------------------------

class StatefulFirewall:

    def __init__(self, rules: list[FirewallRule]):
        self.rules = sorted(rules, key=lambda rule: rule.priority)
        self.connections = ConnectionTracker()
        self.audit_log: list[SecurityDecision] = []

    def evaluate(self, packet: Packet) -> SecurityDecision:
        try:
            packet.validate()
        except (ValueError, TypeError) as exc:
            return self._record(SecurityDecision(
                False,
                Action.DENY,
                DecisionReason.INVALID_PACKET,
                None,
                str(exc)
            ))

        # Return traffic for an established connection is permitted.
        if self.connections.is_established(packet):
            return self._record(SecurityDecision(
                True,
                Action.ALLOW,
                DecisionReason.STATEFUL_RETURN,
                None,
                "Established connection return traffic"
            ))

        for rule in self.rules:
            if rule.matches(packet):
                allowed = rule.action == Action.ALLOW

                if allowed:
                    self.connections.establish(packet)

                return self._record(SecurityDecision(
                    allowed,
                    rule.action,
                    DecisionReason.RULE_MATCH,
                    rule.rule_id,
                    rule.name
                ))

        return self._record(SecurityDecision(
            False,
            Action.DENY,
            DecisionReason.DEFAULT_DENY,
            None,
            "No matching firewall rule"
        ))

    def _record(self, decision: SecurityDecision) -> SecurityDecision:
        self.audit_log.append(decision)

        logger.info(
            "Decision=%s Reason=%s Rule=%s",
            decision.action.value,
            decision.reason.value,
            decision.matched_rule
        )

        return decision


# ---------------------------------------------------------
# Security Group
# ---------------------------------------------------------

class SecurityGroup:
    """
    Security groups are stateful virtual network controls.

    This simplified model implements inbound allow rules.
    Unmatched inbound traffic is denied.
    """

    def __init__(self, group_id: str, inbound_rules: list[FirewallRule]):
        self.group_id = group_id
        self.firewall = StatefulFirewall(inbound_rules)

    def evaluate_inbound(self, packet: Packet) -> SecurityDecision:
        if packet.direction != Direction.INBOUND:
            raise ValueError("Security group expects inbound traffic")

        return self.firewall.evaluate(packet)


# ---------------------------------------------------------
# Network ACL
# ---------------------------------------------------------

class NetworkACL:
    """
    Network ACLs are stateless.

    Inbound and outbound traffic must be explicitly permitted.
    Rules are processed by ascending rule number.
    """

    def __init__(self, acl_id: str, rules: list[FirewallRule]):
        self.acl_id = acl_id
        self.rules = sorted(rules, key=lambda rule: rule.priority)

    def evaluate(self, packet: Packet) -> SecurityDecision:
        packet.validate()

        for rule in self.rules:
            if rule.matches(packet):
                return SecurityDecision(
                    rule.action == Action.ALLOW,
                    rule.action,
                    DecisionReason.RULE_MATCH,
                    rule.rule_id,
                    rule.name
                )

        return SecurityDecision(
            False,
            Action.DENY,
            DecisionReason.DEFAULT_DENY,
            None,
            "Network ACL default deny"
        )


# ---------------------------------------------------------
# Combined Network Security Architecture
# ---------------------------------------------------------

class NetworkSecurityEngine:

    def __init__(
        self,
        firewall: StatefulFirewall,
        security_group: SecurityGroup,
        network_acl: NetworkACL
    ):
        self.firewall = firewall
        self.security_group = security_group
        self.network_acl = network_acl

    def inspect(self, packet: Packet) -> dict:
        try:
            packet.validate()

            # Each security layer independently evaluates traffic.
            firewall_result = self.firewall.evaluate(packet)

            if not firewall_result.allowed:
                return self._result("FIREWALL", firewall_result)

            if packet.direction == Direction.INBOUND:
                sg_result = self.security_group.evaluate_inbound(packet)

                if not sg_result.allowed:
                    return self._result("SECURITY_GROUP", sg_result)

            acl_result = self.network_acl.evaluate(packet)

            if not acl_result.allowed:
                return self._result("NETWORK_ACL", acl_result)

            return {
                "allowed": True,
                "blocked_by": None,
                "message": "Traffic passed all applicable security controls"
            }

        except (ValueError, TypeError) as exc:
            return {
                "allowed": False,
                "blocked_by": "VALIDATION",
                "message": str(exc)
            }

    @staticmethod
    def _result(layer: str, decision: SecurityDecision) -> dict:
        return {
            "allowed": False,
            "blocked_by": layer,
            "reason": decision.reason.value,
            "rule_id": decision.matched_rule,
            "message": decision.message
        }


# ---------------------------------------------------------
# Policy Persistence
# ---------------------------------------------------------

def save_rules(
    rules: list[FirewallRule],
    filename: str = "firewall_rules.json"
) -> None:
    data = []

    for rule in rules:
        item = asdict(rule)
        item["protocol"] = rule.protocol.value
        item["direction"] = rule.direction.value
        item["action"] = rule.action.value
        data.append(item)

    Path(filename).write_text(
        json.dumps(data, indent=4),
        encoding="utf-8"
    )


def load_rules(
    filename: str = "firewall_rules.json"
) -> list[FirewallRule]:
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {filename}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("Policy file must contain a JSON array")

    return [
        FirewallRule(
            **{
                **item,
                "protocol": Protocol(item["protocol"]),
                "direction": Direction(item["direction"]),
                "action": Action(item["action"])
            }
        )
        for item in data
    ]


# ---------------------------------------------------------
# Security Reporting
# ---------------------------------------------------------

def generate_report(decisions: list[SecurityDecision]) -> dict:
    return {
        "total_packets": len(decisions),
        "allowed": sum(d.allowed for d in decisions),
        "denied": sum(not d.allowed for d in decisions),
        "default_denials": sum(
            d.reason == DecisionReason.DEFAULT_DENY
            for d in decisions
        ),
        "invalid_packets": sum(
            d.reason == DecisionReason.INVALID_PACKET
            for d in decisions
        )
    }


# ---------------------------------------------------------
# Demonstration
# ---------------------------------------------------------

def main() -> None:

    firewall_rules = [
        FirewallRule(
            "FW001", "Allow internal HTTPS",
            "10.0.0.0/8", "172.16.0.0/12",
            Protocol.TCP, Direction.INBOUND,
            Action.ALLOW, 100, 443, 443
        ),
        FirewallRule(
            "FW002", "Block insecure HTTP",
            "0.0.0.0/0", "172.16.0.0/12",
            Protocol.TCP, Direction.INBOUND,
            Action.DENY, 200, 80, 80
        ),
        FirewallRule(
            "FW003", "Allow internal DNS",
            "10.0.0.0/8", "172.16.0.0/12",
            Protocol.UDP, Direction.INBOUND,
            Action.ALLOW, 300, 53, 53
        )
    ]

    sg_rules = [
        FirewallRule(
            "SG001", "Application HTTPS",
            "10.0.0.0/8", "172.16.0.0/12",
            Protocol.TCP, Direction.INBOUND,
            Action.ALLOW, 100, 443, 443
        )
    ]

    acl_rules = [
        FirewallRule(
            "ACL001", "Inbound HTTPS",
            "10.0.0.0/8", "172.16.0.0/12",
            Protocol.TCP, Direction.INBOUND,
            Action.ALLOW, 100, 443, 443
        ),
        FirewallRule(
            "ACL002", "Outbound HTTPS response",
            "172.16.0.0/12", "10.0.0.0/8",
            Protocol.TCP, Direction.OUTBOUND,
            Action.ALLOW, 100, 1024, 65535
        ),
        FirewallRule(
            "ACL003", "Inbound DNS",
            "10.0.0.0/8", "172.16.0.0/12",
            Protocol.UDP, Direction.INBOUND,
            Action.ALLOW, 200, 53, 53
        )
    ]

    firewall = StatefulFirewall(firewall_rules)
    security_group = SecurityGroup("SG-WEB", sg_rules)
    network_acl = NetworkACL("ACL-PRODUCTION", acl_rules)

    engine = NetworkSecurityEngine(
        firewall,
        security_group,
        network_acl
    )

    packets = [
        Packet(
            "10.1.1.10", "172.16.1.20",
            51000, 443, Protocol.TCP, Direction.INBOUND
        ),
        Packet(
            "203.0.113.25", "172.16.1.20",
            51001, 80, Protocol.TCP, Direction.INBOUND
        ),
        Packet(
            "10.1.1.10", "172.16.1.20",
            51002, 22, Protocol.TCP, Direction.INBOUND
        ),
        Packet(
            "10.1.1.10", "172.16.1.20",
            51003, 53, Protocol.UDP, Direction.INBOUND
        )
    ]

    print("\nNETWORK SECURITY EVALUATION")
    print("=" * 65)

    for index, packet in enumerate(packets, start=1):
        result = engine.inspect(packet)

        print(
            f"\nPacket {index}: "
            f"{packet.source_ip} -> {packet.destination_ip}"
        )
        print(f"Protocol: {packet.protocol.value}")
        print(f"Decision: {'ALLOW' if result['allowed'] else 'DENY'}")
        print(f"Details: {result['message']}")

    # Demonstrate stateful return traffic.
    response = Packet(
        "172.16.1.20", "10.1.1.10",
        443, 51000, Protocol.TCP, Direction.OUTBOUND
    )

    print("\nSTATEFUL CONNECTION TEST")
    print(engine.inspect(response))

    # Demonstrate stateless ACL return-traffic filtering.
    print("\nSTATELESS NETWORK ACL TEST")
    print(network_acl.evaluate(response))

    # Invalid packet test.
    invalid_packet = Packet(
        "999.999.999.999", "172.16.1.20",
        50000, 443, Protocol.TCP, Direction.INBOUND
    )

    print("\nINVALID PACKET TEST")
    print(engine.inspect(invalid_packet))

    print("\nSECURITY REPORT")
    print(json.dumps(
        generate_report(firewall.audit_log),
        indent=4
    ))

    # Automated assertions.
    assert engine.inspect(packets[0])["allowed"]
    assert not engine.inspect(packets[1])["allowed"]
    assert not engine.inspect(packets[2])["allowed"]
    assert engine.inspect(packets[3])["allowed"]

    assert firewall.connections.is_established(response)
    assert network_acl.evaluate(response).allowed

    print("\nAll network security assertions passed.")


if __name__ == "__main__":
    main()
