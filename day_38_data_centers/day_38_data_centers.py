#!/usr/bin/env python3
"""
Data Center Physical Infrastructure Simulator

Demonstrates:
- Rack organization and rack-unit capacity
- Server placement and power draw
- Power distribution and redundant feeds
- Cooling load and thermal headroom
- UPS/generator capacity
- N+1 redundancy
- Environmental monitoring
- Failure scenarios
- Maintenance and operational validation
- Capacity planning

The model intentionally focuses on physical data-center infrastructure rather
than application-level software infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class PowerFeed(str, Enum):
    A = "A"
    B = "B"


class EquipmentState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class CoolingMode(str, Enum):
    AIR = "air"
    LIQUID = "liquid"


@dataclass(frozen=True)
class Server:
    server_id: str
    name: str
    rack_units: int
    watts: int
    dual_power: bool
    cooling_mode: CoolingMode = CoolingMode.AIR

    @property
    def heat_kw(self) -> float:
        # Almost all electrical power consumed by IT equipment eventually
        # becomes heat that the cooling system must remove.
        return self.watts / 1000.0


@dataclass
class PowerSystem:
    name: str
    capacity_kw: float
    reserved_kw: float = 0.0
    active_load_kw: float = 0.0
    online: bool = True

    @property
    def usable_kw(self) -> float:
        return max(0.0, self.capacity_kw - self.reserved_kw)

    @property
    def utilization(self) -> float:
        if self.usable_kw == 0:
            return 1.0
        return self.active_load_kw / self.usable_kw

    def can_accept(self, additional_kw: float) -> bool:
        return self.online and self.active_load_kw + additional_kw <= self.usable_kw

    def add_load(self, load_kw: float) -> None:
        if not self.can_accept(load_kw):
            raise ValueError(
                f"{self.name} cannot accept {load_kw:.2f} kW; "
                f"available capacity is {self.usable_kw - self.active_load_kw:.2f} kW"
            )
        self.active_load_kw += load_kw

    def remove_load(self, load_kw: float) -> None:
        self.active_load_kw = max(0.0, self.active_load_kw - load_kw)


@dataclass
class CoolingSystem:
    name: str
    capacity_kw: float
    online: bool = True

    def available_capacity(self) -> float:
        return self.capacity_kw if self.online else 0.0


@dataclass
class ServerInstallation:
    server: Server
    feed_a: Optional[str]
    feed_b: Optional[str]
    state: EquipmentState = EquipmentState.ONLINE

    @property
    def is_redundant(self) -> bool:
        return self.server.dual_power and self.feed_a is not None and self.feed_b is not None


@dataclass
class Rack:
    rack_id: str
    location: str
    total_u: int = 42
    power_a: PowerSystem = field(
        default_factory=lambda: PowerSystem("Rack A feed", 10.0, 1.0)
    )
    power_b: PowerSystem = field(
        default_factory=lambda: PowerSystem("Rack B feed", 10.0, 1.0)
    )
    servers: List[ServerInstallation] = field(default_factory=list)

    def used_u(self) -> int:
        return sum(
            installation.server.rack_units
            for installation in self.servers
            if installation.state != EquipmentState.OFFLINE
        )

    def free_u(self) -> int:
        return self.total_u - self.used_u()

    def power_load_kw(self) -> float:
        return sum(
            installation.server.watts / 1000.0
            for installation in self.servers
            if installation.state != EquipmentState.OFFLINE
        )

    def install_server(self, server: Server) -> None:
        if server.rack_units <= 0:
            raise ValueError("Rack-unit size must be positive.")

        if server.rack_units > self.free_u():
            raise ValueError(
                f"{self.rack_id} has only {self.free_u()}U available; "
                f"{server.name} requires {server.rack_units}U."
            )

        load_kw = server.watts / 1000.0

        if server.dual_power:
            # A dual-corded server is modeled with independent A/B feeds.
            # Each feed receives half of the nominal load in this simplified model.
            per_feed = load_kw / 2.0
            if not self.power_a.can_accept(per_feed):
                raise ValueError(f"Insufficient capacity on {self.rack_id} feed A.")
            if not self.power_b.can_accept(per_feed):
                raise ValueError(f"Insufficient capacity on {self.rack_id} feed B.")

            self.power_a.add_load(per_feed)
            self.power_b.add_load(per_feed)

            installation = ServerInstallation(
                server=server,
                feed_a=self.power_a.name,
                feed_b=self.power_b.name,
            )
        else:
            # A single-corded device cannot tolerate loss of its only feed.
            if not self.power_a.can_accept(load_kw):
                raise ValueError(
                    f"Insufficient capacity on {self.rack_id} feed A for single-corded server."
                )
            self.power_a.add_load(load_kw)

            installation = ServerInstallation(
                server=server,
                feed_a=self.power_a.name,
                feed_b=None,
            )

        self.servers.append(installation)

    def remove_server(self, server_id: str) -> None:
        for installation in self.servers:
            if installation.server.server_id == server_id:
                load_kw = installation.server.watts / 1000.0

                if installation.is_redundant:
                    half = load_kw / 2.0
                    self.power_a.remove_load(half)
                    self.power_b.remove_load(half)
                elif installation.feed_a == self.power_a.name:
                    self.power_a.remove_load(load_kw)
                elif installation.feed_a == self.power_b.name:
                    self.power_b.remove_load(load_kw)

                self.servers.remove(installation)
                return

        raise KeyError(f"Server {server_id} is not installed in {self.rack_id}.")

    def fail_feed(self, feed: PowerFeed) -> List[str]:
        affected: List[str] = []
        power_system = self.power_a if feed == PowerFeed.A else self.power_b
        power_system.online = False

        for installation in self.servers:
            if installation.state == EquipmentState.OFFLINE:
                continue

            uses_failed_feed = (
                installation.feed_a == power_system.name
                or installation.feed_b == power_system.name
            )

            if uses_failed_feed and not installation.is_redundant:
                installation.state = EquipmentState.OFFLINE
                affected.append(installation.server.server_id)

        return affected

    def restore_feed(self, feed: PowerFeed) -> None:
        power_system = self.power_a if feed == PowerFeed.A else self.power_b
        power_system.online = True

        for installation in self.servers:
            if installation.state == EquipmentState.OFFLINE:
                # A real facility would determine whether the device automatically
                # recovers, needs a power-cycle, or needs technician intervention.
                installation.state = EquipmentState.ONLINE


@dataclass
class DataCenter:
    name: str
    racks: Dict[str, Rack]
    cooling_systems: List[CoolingSystem]
    ups_systems: List[PowerSystem]
    generators: List[PowerSystem]
    ambient_temperature_c: float = 22.0
    recommended_max_temperature_c: float = 27.0

    def total_it_load_kw(self) -> float:
        return sum(rack.power_load_kw() for rack in self.racks.values())

    def total_heat_kw(self) -> float:
        return self.total_it_load_kw()

    def total_cooling_capacity_kw(self) -> float:
        return sum(
            system.available_capacity() for system in self.cooling_systems
        )

    def active_cooling_count(self) -> int:
        return sum(system.online for system in self.cooling_systems)

    def power_usage_effectiveness(self) -> Optional[float]:
        it_load = self.total_it_load_kw()
        if it_load <= 0:
            return None

        # PUE = total facility power / IT equipment power.
        # The simulator treats cooling and other facility overhead as a simple
        # modeled overhead rather than a complete electrical engineering model.
        facility_load = it_load + max(0.0, self.total_cooling_capacity_kw() * 0.12)
        return facility_load / it_load

    def validate_cooling(self) -> Tuple[bool, str]:
        heat = self.total_heat_kw()
        capacity = self.total_cooling_capacity_kw()

        if capacity < heat:
            return (
                False,
                f"Cooling shortfall: {heat:.2f} kW heat load vs "
                f"{capacity:.2f} kW available cooling.",
            )

        if self.ambient_temperature_c > self.recommended_max_temperature_c:
            return (
                False,
                f"Ambient temperature {self.ambient_temperature_c:.1f}°C "
                f"exceeds {self.recommended_max_temperature_c:.1f}°C.",
            )

        return True, "Cooling capacity and modeled temperature are within limits."

    def validate_n_plus_one_cooling(self) -> Tuple[bool, str]:
        online = [system for system in self.cooling_systems if system.online]
        if len(online) < 2:
            return False, "N+1 cooling cannot be demonstrated with fewer than two units."

        total = sum(system.capacity_kw for system in online)
        largest = max(system.capacity_kw for system in online)
        heat = self.total_heat_kw()

        if total - largest >= heat:
            return True, "N+1 cooling capacity is available."
        return False, (
            f"N+1 cooling capacity is insufficient: after losing the largest "
            f"unit, {total - largest:.2f} kW remains for {heat:.2f} kW load."
        )

    def validate_rack_power_redundancy(self) -> List[str]:
        findings = []

        for rack in self.racks.values():
            if not rack.power_a.online or not rack.power_b.online:
                findings.append(
                    f"{rack.rack_id}: one power path is unavailable."
                )

            for installation in rack.servers:
                if installation.server.dual_power and not installation.is_redundant:
                    findings.append(
                        f"{rack.rack_id}/{installation.server.server_id}: "
                        "dual-power server lacks two independent connections."
                    )

        return findings

    def facility_report(self) -> str:
        lines = [
            f"Data center: {self.name}",
            f"IT load: {self.total_it_load_kw():.2f} kW",
            f"Heat load: {self.total_heat_kw():.2f} kW",
            f"Cooling capacity: {self.total_cooling_capacity_kw():.2f} kW",
            f"Online cooling units: {self.active_cooling_count()}",
            f"Modeled PUE: {self.power_usage_effectiveness():.2f}",
            "",
            "Rack utilization:",
        ]

        for rack in self.racks.values():
            lines.append(
                f"  {rack.rack_id} ({rack.location}): "
                f"{rack.used_u()}/{rack.total_u}U, "
                f"A={rack.power_a.active_load_kw:.2f} kW, "
                f"B={rack.power_b.active_load_kw:.2f} kW"
            )

        return "\n".join(lines)


def build_reference_data_center() -> DataCenter:
    racks = {
        "RACK-A01": Rack("RACK-A01", "Row A / Position 01"),
        "RACK-A02": Rack("RACK-A02", "Row A / Position 02"),
        "RACK-B01": Rack("RACK-B01", "Row B / Position 01"),
    }

    cooling = [
        CoolingSystem("CRAC-01", 12.0),
        CoolingSystem("CRAC-02", 12.0),
        CoolingSystem("CRAC-03", 12.0),
    ]

    ups = [
        PowerSystem("UPS-A", 120.0, 20.0),
        PowerSystem("UPS-B", 120.0, 20.0),
    ]

    generators = [
        PowerSystem("GEN-A", 250.0, 30.0),
        PowerSystem("GEN-B", 250.0, 30.0),
    ]

    return DataCenter(
        name="Reference Enterprise Facility",
        racks=racks,
        cooling_systems=cooling,
        ups_systems=ups,
        generators=generators,
    )


def install_reference_servers(dc: DataCenter) -> None:
    servers = [
        Server("SRV-001", "Database host", 2, 850, True),
        Server("SRV-002", "Virtualization host", 2, 1100, True),
        Server("SRV-003", "Storage controller", 2, 700, True),
        Server("SRV-004", "Network management server", 1, 300, True),
        Server("SRV-005", "Backup appliance", 4, 1400, True),
        Server("SRV-006", "Monitoring appliance", 1, 250, False),
    ]

    dc.racks["RACK-A01"].install_server(servers[0])
    dc.racks["RACK-A01"].install_server(servers[1])
    dc.racks["RACK-A02"].install_server(servers[2])
    dc.racks["RACK-A02"].install_server(servers[3])
    dc.racks["RACK-B01"].install_server(servers[4])
    dc.racks["RACK-B01"].install_server(servers[5])


def demonstrate_rack_capacity(dc: DataCenter) -> None:
    print("\nRACK CAPACITY")
    for rack in dc.racks.values():
        print(
            f"{rack.rack_id}: {rack.used_u()}U used, "
            f"{rack.free_u()}U free"
        )

    oversized = Server("SRV-EDGE", "Oversized appliance", 50, 1000, True)

    try:
        dc.racks["RACK-A01"].install_server(oversized)
    except ValueError as exc:
        print(f"Rejected placement: {exc}")


def demonstrate_environment(dc: DataCenter) -> None:
    print("\nENVIRONMENT")
    valid, message = dc.validate_cooling()
    print(f"Cooling validation: {'PASS' if valid else 'FAIL'} - {message}")

    valid, message = dc.validate_n_plus_one_cooling()
    print(f"N+1 validation: {'PASS' if valid else 'FAIL'} - {message}")

    dc.ambient_temperature_c = 29.0
    valid, message = dc.validate_cooling()
    print(f"High-temperature validation: {'PASS' if valid else 'FAIL'} - {message}")

    dc.ambient_temperature_c = 22.0


def demonstrate_power_failure(dc: DataCenter) -> None:
    print("\nPOWER FAILURE SCENARIO")

    rack = dc.racks["RACK-A01"]

    print("Before failure:")
    for installation in rack.servers:
        print(
            f"  {installation.server.server_id}: "
            f"{installation.state.value}, "
            f"dual_power={installation.server.dual_power}"
        )

    affected = rack.fail_feed(PowerFeed.A)

    print(f"Failed feed A. Directly affected servers: {affected}")

    for installation in rack.servers:
        print(
            f"  {installation.server.server_id}: "
            f"{installation.state.value}"
        )

    rack.restore_feed(PowerFeed.A)
    print("Feed A restored.")

    for installation in rack.servers:
        print(
            f"  {installation.server.server_id}: "
            f"{installation.state.value}"
        )


def demonstrate_cooling_failure(dc: DataCenter) -> None:
    print("\nCOOLING FAILURE SCENARIO")

    cooling_unit = dc.cooling_systems[0]
    cooling_unit.online = False

    valid, message = dc.validate_cooling()
    print(f"After {cooling_unit.name} failure: {'PASS' if valid else 'FAIL'} - {message}")

    valid, message = dc.validate_n_plus_one_cooling()
    print(f"N+1 after failure: {'PASS' if valid else 'FAIL'} - {message}")

    cooling_unit.online = True


def demonstrate_redundancy_findings(dc: DataCenter) -> None:
    print("\nREDUNDANCY AUDIT")

    findings = dc.validate_rack_power_redundancy()

    if not findings:
        print("No rack power redundancy findings.")
    else:
        for finding in findings:
            print(finding)


def demonstrate_generator_and_ups_capacity(dc: DataCenter) -> None:
    print("\nPOWER RESILIENCE CAPACITY")

    it_load = dc.total_it_load_kw()

    for system in dc.ups_systems:
        print(
            f"{system.name}: usable={system.usable_kw:.1f} kW, "
            f"IT load reference={it_load:.2f} kW"
        )

    for system in dc.generators:
        print(
            f"{system.name}: usable={system.usable_kw:.1f} kW, "
            f"capacity margin={system.usable_kw - it_load:.2f} kW"
        )

    # Generator sizing must account for more than today's IT load in a real
    # design. Starting currents, cooling, UPS losses, lighting, and future
    # growth are among the loads that require engineering analysis.
    if all(system.usable_kw >= it_load for system in dc.generators):
        print("Current modeled IT load fits within each generator's usable capacity.")
    else:
        print("Generator capacity is insufficient for the modeled IT load.")


def demonstrate_validation_failure() -> None:
    print("\nVALIDATION FAILURE EXAMPLE")

    rack = Rack(
        "RACK-OVERLOAD",
        "Row C / Position 01",
        power_a=PowerSystem("Overload A", 5.0, 0.0),
        power_b=PowerSystem("Overload B", 5.0, 0.0),
    )

    high_power_server = Server(
        "SRV-HIGH",
        "High-density compute node",
        4,
        11000,
        True,
    )

    try:
        rack.install_server(high_power_server)
    except ValueError as exc:
        print(f"Power placement correctly rejected: {exc}")


def demonstrate_capacity_growth(dc: DataCenter) -> None:
    print("\nCAPACITY GROWTH ANALYSIS")

    current = dc.total_it_load_kw()
    planned_growth_percent = 25.0
    projected = current * (1.0 + planned_growth_percent / 100.0)

    cooling_capacity = dc.total_cooling_capacity_kw()
    print(f"Current IT load: {current:.2f} kW")
    print(f"Projected IT load after {planned_growth_percent:.0f}% growth: {projected:.2f} kW")
    print(f"Installed cooling capacity: {cooling_capacity:.2f} kW")

    if projected <= cooling_capacity:
        print("Cooling has sufficient modeled capacity for the projection.")
    else:
        print("Cooling expansion would be required for the projection.")


def main() -> None:
    dc = build_reference_data_center()
    install_reference_servers(dc)

    print("DATA CENTER PHYSICAL INFRASTRUCTURE SIMULATOR")
    print("=" * 52)
    print(dc.facility_report())

    demonstrate_rack_capacity(dc)
    demonstrate_environment(dc)
    demonstrate_power_failure(dc)
    demonstrate_cooling_failure(dc)
    demonstrate_redundancy_findings(dc)
    demonstrate_generator_and_ups_capacity(dc)
    demonstrate_validation_failure()
    demonstrate_capacity_growth(dc)

    print("\nFINAL FACILITY REPORT")
    print("=" * 52)
    print(dc.facility_report())


if __name__ == "__main__":
    main()
