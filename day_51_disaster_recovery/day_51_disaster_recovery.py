#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import copy
import hashlib
import json
import time


class RecoveryTier(Enum):
    BACKUP_RESTORE = "backup_restore"
    PILOT_LIGHT = "pilot_light"
    WARM_STANDBY = "warm_standby"
    MULTI_REGION = "multi_region"


class RegionState(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FAILED = "failed"


@dataclass(frozen=True)
class RecoveryObjective:
    rpo_minutes: int
    rto_minutes: int

    def validate(self) -> None:
        if self.rpo_minutes < 0:
            raise ValueError("RPO cannot be negative")
        if self.rto_minutes <= 0:
            raise ValueError("RTO must be greater than zero")


@dataclass
class Backup:
    backup_id: str
    created_at: float
    size_mb: int
    checksum: str
    location: str
    complete: bool = True

    @classmethod
    def create(cls, backup_id: str, data: bytes, location: str) -> "Backup":
        return cls(
            backup_id=backup_id,
            created_at=time.time(),
            size_mb=max(1, len(data) // 1024 // 1024),
            checksum=hashlib.sha256(data).hexdigest(),
            location=location,
        )


@dataclass
class Service:
    name: str
    objective: RecoveryObjective
    tier: RecoveryTier
    data: Dict[str, str] = field(default_factory=dict)
    last_backup_at: Optional[float] = None
    running_regions: List[str] = field(default_factory=list)

    def validate(self) -> None:
        self.objective.validate()
        if not self.name.strip():
            raise ValueError("Service name cannot be empty")
        if not self.running_regions:
            raise ValueError(f"{self.name} has no recovery region")


@dataclass
class Region:
    name: str
    state: RegionState = RegionState.SECONDARY
    capacity_percent: int = 100

    def validate(self) -> None:
        if not 0 <= self.capacity_percent <= 100:
            raise ValueError("Capacity must be between 0 and 100")


class RecoveryManager:
    def __init__(self) -> None:
        self.regions: Dict[str, Region] = {}
        self.services: Dict[str, Service] = {}
        self.backups: Dict[str, List[Backup]] = {}

    def add_region(self, region: Region) -> None:
        region.validate()
        if region.name in self.regions:
            raise ValueError(f"Region already exists: {region.name}")
        self.regions[region.name] = region

    def register_service(self, service: Service) -> None:
        service.validate()

        missing = [
            region for region in service.running_regions
            if region not in self.regions
        ]
        if missing:
            raise ValueError(f"Unknown recovery regions: {missing}")

        self.services[service.name] = service
        self.backups.setdefault(service.name, [])

    def create_backup(self, service_name: str) -> Backup:
        service = self._service(service_name)

        serialized = json.dumps(
            service.data,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        backup_id = f"{service_name}-backup-{len(self.backups[service_name]) + 1}"
        backup = Backup.create(
            backup_id=backup_id,
            data=serialized,
            location="object-storage-secondary",
        )

        self.backups[service_name].append(backup)
        service.last_backup_at = backup.created_at
        return backup

    def record_write(self, service_name: str, key: str, value: str) -> None:
        service = self._service(service_name)
        if not key:
            raise ValueError("Data key cannot be empty")
        service.data[key] = value

    def latest_backup(self, service_name: str) -> Optional[Backup]:
        backups = self.backups.get(service_name, [])
        return backups[-1] if backups else None

    def calculate_data_loss_minutes(
        self,
        service_name: str,
        failure_time: Optional[float] = None,
    ) -> Optional[float]:
        backup = self.latest_backup(service_name)
        if backup is None:
            return None

        failure_time = failure_time or time.time()
        return max(0.0, (failure_time - backup.created_at) / 60)

    def fail_region(self, region_name: str) -> None:
        region = self._region(region_name)
        region.state = RegionState.FAILED

    def recover(
        self,
        service_name: str,
        failed_region: str,
        available_recovery_region: str,
    ) -> Dict[str, object]:
        service = self._service(service_name)
        failed = self._region(failed_region)
        target = self._region(available_recovery_region)

        if failed.state != RegionState.FAILED:
            raise RuntimeError(f"Region {failed_region} is not failed")

        if target.state == RegionState.FAILED:
            raise RuntimeError(f"Recovery target {target.name} is unavailable")

        if target.capacity_percent <= 0:
            raise RuntimeError(f"Recovery target {target.name} has no capacity")

        backup = self.latest_backup(service_name)

        if service.tier == RecoveryTier.BACKUP_RESTORE and backup is None:
            raise RuntimeError("Backup restore is impossible without a backup")

        if service.tier in {
            RecoveryTier.PILOT_LIGHT,
            RecoveryTier.WARM_STANDBY,
            RecoveryTier.MULTI_REGION,
        } and target.name not in service.running_regions:
            raise RuntimeError(
                f"{target.name} is not configured for service {service_name}"
            )

        estimated_minutes = {
            RecoveryTier.BACKUP_RESTORE: 90,
            RecoveryTier.PILOT_LIGHT: 30,
            RecoveryTier.WARM_STANDBY: 10,
            RecoveryTier.MULTI_REGION: 2,
        }[service.tier]

        meets_rto = estimated_minutes <= service.objective.rto_minutes
        estimated_rpo = self.calculate_data_loss_minutes(service_name)

        meets_rpo = (
            estimated_rpo is not None
            and estimated_rpo <= service.objective.rpo_minutes
        )

        if not meets_rto or not meets_rpo:
            raise RuntimeError(
                f"Recovery objectives violated: "
                f"RPO={estimated_rpo}, target={service.objective.rpo_minutes}; "
                f"RTO={estimated_minutes}, target={service.objective.rto_minutes}"
            )

        target.state = RegionState.PRIMARY
        failed.state = RegionState.FAILED

        return {
            "service": service.name,
            "tier": service.tier.value,
            "recovery_region": target.name,
            "estimated_rpo_minutes": round(estimated_rpo or 0, 2),
            "estimated_rto_minutes": estimated_minutes,
            "rpo_met": meets_rpo,
            "rto_met": meets_rto,
        }

    def audit(self) -> List[str]:
        findings: List[str] = []

        for service in self.services.values():
            latest = self.latest_backup(service.name)

            if latest is None:
                findings.append(f"{service.name}: no backup exists")
                continue

            if not latest.complete:
                findings.append(f"{service.name}: latest backup is incomplete")

            age_minutes = (time.time() - latest.created_at) / 60

            if age_minutes > service.objective.rpo_minutes:
                findings.append(
                    f"{service.name}: backup age exceeds RPO "
                    f"({age_minutes:.1f} > {service.objective.rpo_minutes} minutes)"
                )

            if service.tier == RecoveryTier.MULTI_REGION:
                available = [
                    self.regions[r]
                    for r in service.running_regions
                    if self.regions[r].state != RegionState.FAILED
                ]
                if len(available) < 2:
                    findings.append(
                        f"{service.name}: multi-region service lacks "
                        "two available regions"
                    )

        return findings

    def _service(self, name: str) -> Service:
        if name not in self.services:
            raise KeyError(f"Unknown service: {name}")
        return self.services[name]

    def _region(self, name: str) -> Region:
        if name not in self.regions:
            raise KeyError(f"Unknown region: {name}")
        return self.regions[name]


def simulate_failover(manager: RecoveryManager) -> None:
    service = manager.services["payments"]

    # Make the backup timestamp recent enough to satisfy the five-minute RPO.
    backup = manager.create_backup(service.name)
    backup.created_at = time.time() - 60
    service.last_backup_at = backup.created_at

    manager.fail_region("ap-south-1")

    result = manager.recover(
        service_name="payments",
        failed_region="ap-south-1",
        available_recovery_region="ap-southeast-1",
    )

    print("Recovery result:")
    print(json.dumps(result, indent=2))

    print("\nAudit findings:")
    findings = manager.audit()
    if findings:
        for finding in findings:
            print("-", finding)
    else:
        print("- No recovery-policy findings")


def demonstrate_failed_recovery(manager: RecoveryManager) -> None:
    service = manager.services["analytics"]

    # A stale backup intentionally demonstrates an RPO failure.
    backup = manager.create_backup(service.name)
    backup.created_at = time.time() - 180
    service.last_backup_at = backup.created_at

    manager.fail_region("eu-west-1")

    try:
        manager.recover(
            service_name="analytics",
            failed_region="eu-west-1",
            available_recovery_region="eu-central-1",
        )
    except RuntimeError as exc:
        print("\nExpected recovery rejection:")
        print(exc)


def main() -> None:
    manager = RecoveryManager()

    manager.add_region(Region("ap-south-1", RegionState.PRIMARY))
    manager.add_region(Region("ap-southeast-1", RegionState.SECONDARY))
    manager.add_region(Region("eu-west-1", RegionState.PRIMARY))
    manager.add_region(Region("eu-central-1", RegionState.SECONDARY))

    manager.register_service(
        Service(
            name="payments",
            objective=RecoveryObjective(rpo_minutes=5, rto_minutes=15),
            tier=RecoveryTier.WARM_STANDBY,
            data={"transaction-1001": "approved"},
            running_regions=["ap-south-1", "ap-southeast-1"],
        )
    )

    manager.register_service(
        Service(
            name="analytics",
            objective=RecoveryObjective(rpo_minutes=30, rto_minutes=60),
            tier=RecoveryTier.BACKUP_RESTORE,
            data={"report-2026-10-21": "complete"},
            running_regions=["eu-west-1", "eu-central-1"],
        )
    )

    manager.register_service(
        Service(
            name="catalog",
            objective=RecoveryObjective(rpo_minutes=1, rto_minutes=5),
            tier=RecoveryTier.MULTI_REGION,
            data={"sku-100": "active"},
            running_regions=["ap-south-1", "ap-southeast-1"],
        )
    )

    manager.record_write("payments", "transaction-1002", "pending")
    simulate_failover(manager)

    # Reset the region for the independent failure demonstration.
    manager.regions["eu-west-1"].state = RegionState.PRIMARY
    manager.regions["eu-central-1"].state = RegionState.SECONDARY

    demonstrate_failed_recovery(manager)

    # Demonstrate that a failed or missing recovery target is rejected.
    manager.regions["eu-central-1"].state = RegionState.FAILED
    try:
        manager.recover(
            "analytics",
            "eu-west-1",
            "eu-central-1",
        )
    except RuntimeError as exc:
        print("\nExpected unavailable-target rejection:")
        print(exc)


if __name__ == "__main__":
    main()
