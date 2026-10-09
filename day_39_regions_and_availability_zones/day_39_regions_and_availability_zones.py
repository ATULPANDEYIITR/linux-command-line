#!/usr/bin/env python3
"""Model geographic regions, availability zones, and resilient cloud deployments.

Uses only the Python standard library. The simulation distinguishes regional
failures from zone failures and evaluates placement, capacity, quorum, latency,
and recovery requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Iterable


class FailureScope(str, Enum):
    ZONE = "zone"
    REGION = "region"


class DeploymentError(ValueError):
    """Raised when a deployment configuration violates an explicit rule."""


@dataclass(frozen=True)
class Region:
    name: str
    latitude: float
    longitude: float
    data_residency_group: str
    zones: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DeploymentError("Region name cannot be empty.")
        if not -90 <= self.latitude <= 90:
            raise DeploymentError("Latitude must be between -90 and 90.")
        if not -180 <= self.longitude <= 180:
            raise DeploymentError("Longitude must be between -180 and 180.")
        if len(set(self.zones)) != len(self.zones) or not self.zones:
            raise DeploymentError("A region requires distinct availability zones.")


@dataclass
class AvailabilityZone:
    name: str
    region_name: str
    capacity_units: int
    latency_ms: float
    healthy: bool = True
    used_capacity: int = 0

    def __post_init__(self) -> None:
        if self.capacity_units < 0 or self.latency_ms < 0:
            raise DeploymentError("Capacity and latency cannot be negative.")

    @property
    def available_capacity(self) -> int:
        return max(0, self.capacity_units - self.used_capacity)

    def can_allocate(self, units: int) -> bool:
        return self.healthy and units <= self.available_capacity

    def allocate(self, units: int) -> None:
        if units <= 0:
            raise DeploymentError("Allocation must be positive.")
        if not self.can_allocate(units):
            raise DeploymentError(f"Insufficient healthy capacity in {self.name}.")
        self.used_capacity += units

    def release(self, units: int) -> None:
        if units <= 0 or units > self.used_capacity:
            raise DeploymentError("Invalid capacity release.")
        self.used_capacity -= units


@dataclass(frozen=True)
class Workload:
    name: str
    required_units: int
    minimum_zones: int
    maximum_latency_ms: float
    residency_group: str
    critical: bool = True

    def __post_init__(self) -> None:
        if self.required_units <= 0:
            raise DeploymentError("Workload capacity must be positive.")
        if self.minimum_zones < 1:
            raise DeploymentError("At least one zone is required.")
        if self.maximum_latency_ms < 0:
            raise DeploymentError("Latency limit cannot be negative.")


@dataclass
class Placement:
    workload_name: str
    allocations: dict[str, int] = field(default_factory=dict)

    @property
    def total_units(self) -> int:
        return sum(self.allocations.values())


class CloudEnvironment:
    def __init__(self, regions: Iterable[Region],
                 zones: Iterable[AvailabilityZone]) -> None:
        self.regions = {region.name: region for region in regions}
        self.zones = {zone.name: zone for zone in zones}

        if not self.regions or not self.zones:
            raise DeploymentError("At least one region and zone are required.")

        for zone in self.zones.values():
            region = self.regions.get(zone.region_name)
            if region is None or zone.name not in region.zones:
                raise DeploymentError(
                    f"Zone {zone.name} has an inconsistent region relationship."
                )

    def eligible_zones(self, workload: Workload,
                       region_names: Iterable[str]) -> list[AvailabilityZone]:
        allowed_regions = set(region_names)
        return sorted(
            (
                zone for zone in self.zones.values()
                if zone.region_name in allowed_regions
                and zone.healthy
                and self.regions[zone.region_name].data_residency_group
                == workload.residency_group
                and zone.latency_ms <= workload.maximum_latency_ms
            ),
            key=lambda zone: (
                zone.latency_ms,
                -zone.available_capacity,
                zone.name,
            ),
        )

    def deploy(self, workload: Workload,
               region_names: Iterable[str]) -> Placement:
        """Spread replicas across zones using a capacity-aware greedy policy.

        Production schedulers may need global optimization when workloads share
        capacity or when latency and cost constraints interact.
        """
        candidates = self.eligible_zones(workload, region_names)

        if len(candidates) < workload.minimum_zones:
            raise DeploymentError(
                f"{workload.name}: only {len(candidates)} eligible zones; "
                f"{workload.minimum_zones} required."
            )

        # Assign a replica to each required zone before adding extra capacity.
        # This prevents a single low-latency zone from absorbing all replicas.
        remaining = workload.required_units
        selected = candidates[:workload.minimum_zones]
        allocation = {zone.name: 0 for zone in selected}

        for zone in selected:
            if remaining > 0 and zone.available_capacity > 0:
                allocation[zone.name] += 1
                remaining -= 1

        # Fill the remaining capacity with the lowest-latency eligible zones.
        # Zones selected for initial spreading remain available for more units.
        for zone in candidates:
            if remaining <= 0:
                break
            already_selected = allocation.get(zone.name, 0)
            usable = min(
                remaining,
                zone.available_capacity - already_selected,
            )
            if usable > 0:
                allocation[zone.name] = already_selected + usable
                remaining -= usable

        if remaining > 0:
            raise DeploymentError(
                f"{workload.name}: insufficient aggregate eligible capacity; "
                f"{remaining} units remain unplaced."
            )

        for zone_name, units in allocation.items():
            if units:
                self.zones[zone_name].allocate(units)

        return Placement(workload.name, allocation)

    def fail_zone(self, zone_name: str) -> None:
        self.zones[zone_name].healthy = False

    def recover_zone(self, zone_name: str) -> None:
        self.zones[zone_name].healthy = True

    def fail_region(self, region_name: str) -> None:
        if region_name not in self.regions:
            raise DeploymentError(f"Unknown region: {region_name}")
        for zone in self.zones.values():
            if zone.region_name == region_name:
                zone.healthy = False

    def recover_region(self, region_name: str) -> None:
        if region_name not in self.regions:
            raise DeploymentError(f"Unknown region: {region_name}")
        for zone in self.zones.values():
            if zone.region_name == region_name:
                zone.healthy = True

    def surviving_capacity(self, placement: Placement) -> int:
        return sum(
            units for zone_name, units in placement.allocations.items()
            if self.zones[zone_name].healthy
        )

    def available_zone_count(self, placement: Placement) -> int:
        return sum(
            1 for zone_name, units in placement.allocations.items()
            if units > 0 and self.zones[zone_name].healthy
        )

    def report(self) -> None:
        for region_name in sorted(self.regions):
            print(f"Region: {region_name}")
            for zone in sorted(
                (z for z in self.zones.values()
                 if z.region_name == region_name),
                key=lambda item: item.name,
            ):
                status = "healthy" if zone.healthy else "FAILED"
                print(
                    f"  {zone.name}: {status}, "
                    f"capacity={zone.available_capacity}/"
                    f"{zone.capacity_units}, latency={zone.latency_ms:.1f} ms"
                )


def haversine_km(lat1: float, lon1: float,
                 lat2: float, lon2: float) -> float:
    """Estimate geographic distance between two latitude/longitude points."""
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 6371.0 * 2 * asin(sqrt(min(1.0, a)))


@dataclass(frozen=True)
class RecoveryObjective:
    recovery_time_objective_minutes: int
    recovery_point_objective_minutes: int

    def __post_init__(self) -> None:
        if self.recovery_time_objective_minutes < 0:
            raise DeploymentError("RTO cannot be negative.")
        if self.recovery_point_objective_minutes < 0:
            raise DeploymentError("RPO cannot be negative.")


@dataclass(frozen=True)
class RecoveryPlan:
    objective: RecoveryObjective
    detection_minutes: int
    failover_minutes: int
    replication_lag_minutes: int
    tested: bool

    def assess(self) -> list[str]:
        findings: list[str] = []
        actual_rto = self.detection_minutes + self.failover_minutes
        if actual_rto > self.objective.recovery_time_objective_minutes:
            findings.append(
                f"RTO violation: {actual_rto} minutes exceeds "
                f"{self.objective.recovery_time_objective_minutes} minutes."
            )
        if self.replication_lag_minutes > (
            self.objective.recovery_point_objective_minutes
        ):
            findings.append(
                f"RPO violation: replication lag is "
                f"{self.replication_lag_minutes} minutes."
            )
        if not self.tested:
            findings.append("Recovery plan has not been tested.")
        return findings


def build_environment() -> CloudEnvironment:
    regions = [
        Region(
            "asia-south", 19.0760, 72.8777, "india",
            ("as-1a", "as-1b", "as-1c"),
        ),
        Region(
            "asia-southeast", 1.3521, 103.8198, "apac",
            ("ase-1a", "ase-1b", "ase-1c"),
        ),
    ]
    zones = [
        AvailabilityZone("as-1a", "asia-south", 8, 12),
        AvailabilityZone("as-1b", "asia-south", 8, 15),
        AvailabilityZone("as-1c", "asia-south", 8, 18),
        AvailabilityZone("ase-1a", "asia-southeast", 10, 48),
        AvailabilityZone("ase-1b", "asia-southeast", 10, 52),
        AvailabilityZone("ase-1c", "asia-southeast", 10, 55),
    ]
    return CloudEnvironment(regions, zones)


def main() -> None:
    environment = build_environment()

    payment_api = Workload(
        name="payment-api",
        required_units=9,
        minimum_zones=3,
        maximum_latency_ms=30,
        residency_group="india",
        critical=True,
    )
    placement = environment.deploy(payment_api, ["asia-south"])

    print("Initial placement")
    print(placement.allocations)
    print(f"Allocated units: {placement.total_units}")
    print()

    print("Zone outage")
    environment.fail_zone("as-1b")
    print(f"Surviving units: {environment.surviving_capacity(placement)}")
    print(f"Surviving zones: {environment.available_zone_count(placement)}")
    print(
        "Capacity preserved:",
        environment.surviving_capacity(placement) >= payment_api.required_units,
    )
    environment.recover_zone("as-1b")
    print()

    print("Regional disaster")
    environment.fail_region("asia-south")
    print(f"Surviving units: {environment.surviving_capacity(placement)}")
    print("A second region is required for regional disaster recovery.")
    environment.recover_region("asia-south")
    print()

    print("Geographic distance")
    distance = haversine_km(19.0760, 72.8777, 1.3521, 103.8198)
    print(f"Approximate Mumbai-to-Singapore distance: {distance:.0f} km")
    print()

    print("Recovery objective assessment")
    recovery = RecoveryPlan(
        objective=RecoveryObjective(15, 5),
        detection_minutes=3,
        failover_minutes=8,
        replication_lag_minutes=2,
        tested=True,
    )
    findings = recovery.assess()
    print("Recovery plan meets configured objectives." if not findings else findings)
    print()

    print("Capacity and placement validation")
    try:
        environment.deploy(
            Workload("restricted-workload", 4, 2, 10, "india"),
            ["asia-southeast"],
        )
    except DeploymentError as error:
        print(f"Deployment rejected: {error}")

    print()
    environment.report()


if __name__ == "__main__":
    main()
