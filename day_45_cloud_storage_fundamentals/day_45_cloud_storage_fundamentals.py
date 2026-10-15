from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from math import ceil
from typing import Dict, List, Set, Tuple


class StorageClass(Enum):
    STANDARD = "standard"
    INFREQUENT_ACCESS = "infrequent-access"
    ARCHIVE = "archive"


@dataclass(frozen=True)
class StorageObject:
    key: str
    size_bytes: int
    content_hash: str
    storage_class: StorageClass = StorageClass.STANDARD


@dataclass
class Replica:
    region: str
    healthy: bool = True


@dataclass
class StoredObject:
    obj: StorageObject
    replicas: List[Replica] = field(default_factory=list)

    @property
    def durable_copy_count(self) -> int:
        return sum(1 for replica in self.replicas if replica.healthy)


class CloudStorageError(Exception):
    """Base exception for the storage simulation."""


class InvalidObjectError(CloudStorageError):
    pass


class ObjectNotFoundError(CloudStorageError):
    pass


class InsufficientReplicationError(CloudStorageError):
    pass


class CloudStorageBucket:
    """
    Educational cloud-object-storage model.

    Durability is modeled as the ability to retain data despite independent
    replica failures. Availability is modeled separately as the ability to
    serve a request while at least one healthy replica remains reachable.
    """

    def __init__(
        self,
        name: str,
        regions: Tuple[str, ...],
        replication_factor: int = 3,
        minimum_size_bytes: int = 1,
        maximum_object_size_bytes: int = 5 * 1024**3,
    ) -> None:
        if not name.strip():
            raise ValueError("Bucket name cannot be empty.")
        if len(regions) < 1:
            raise ValueError("At least one region is required.")
        if replication_factor < 1:
            raise ValueError("Replication factor must be positive.")
        if replication_factor > len(regions):
            raise ValueError(
                "Replication factor cannot exceed the number of regions."
            )

        self.name = name
        self.regions = regions
        self.replication_factor = replication_factor
        self.minimum_size_bytes = minimum_size_bytes
        self.maximum_object_size_bytes = maximum_object_size_bytes
        self._objects: Dict[str, StoredObject] = {}

    @staticmethod
    def _hash_content(content: bytes) -> str:
        return sha256(content).hexdigest()

    def put(
        self,
        key: str,
        content: bytes,
        storage_class: StorageClass = StorageClass.STANDARD,
    ) -> StoredObject:
        if not key.strip():
            raise InvalidObjectError("Object key cannot be empty.")
        if not isinstance(content, bytes):
            raise TypeError("Object content must be bytes.")
        if not (
            self.minimum_size_bytes
            <= len(content)
            <= self.maximum_object_size_bytes
        ):
            raise InvalidObjectError(
                f"Object size must be between {self.minimum_size_bytes} "
                f"and {self.maximum_object_size_bytes} bytes."
            )

        obj = StorageObject(
            key=key,
            size_bytes=len(content),
            content_hash=self._hash_content(content),
            storage_class=storage_class,
        )

        replicas = [
            Replica(region=region)
            for region in self.regions[: self.replication_factor]
        ]

        stored = StoredObject(obj=obj, replicas=replicas)
        self._objects[key] = stored
        return stored

    def get(self, key: str) -> StorageObject:
        stored = self._objects.get(key)
        if stored is None:
            raise ObjectNotFoundError(f"Object '{key}' does not exist.")

        if stored.durable_copy_count == 0:
            raise InsufficientReplicationError(
                f"No healthy replica is available for '{key}'."
            )

        return stored.obj

    def delete(self, key: str) -> None:
        if key not in self._objects:
            raise ObjectNotFoundError(f"Object '{key}' does not exist.")
        del self._objects[key]

    def simulate_region_failure(self, region: str) -> None:
        if region not in self.regions:
            raise ValueError(f"Unknown region: {region}")

        for stored in self._objects.values():
            for replica in stored.replicas:
                if replica.region == region:
                    replica.healthy = False

    def recover_region(self, region: str) -> None:
        if region not in self.regions:
            raise ValueError(f"Unknown region: {region}")

        for stored in self._objects.values():
            for replica in stored.replicas:
                if replica.region == region:
                    replica.healthy = True

    def replication_status(self, key: str) -> Dict[str, object]:
        stored = self._objects.get(key)
        if stored is None:
            raise ObjectNotFoundError(f"Object '{key}' does not exist.")

        healthy = [
            replica.region for replica in stored.replicas if replica.healthy
        ]
        unhealthy = [
            replica.region for replica in stored.replicas if not replica.healthy
        ]

        return {
            "key": key,
            "configured_replicas": len(stored.replicas),
            "healthy_replicas": len(healthy),
            "healthy_regions": healthy,
            "failed_regions": unhealthy,
        }

    def availability_status(self, key: str) -> str:
        stored = self._objects.get(key)
        if stored is None:
            raise ObjectNotFoundError(f"Object '{key}' does not exist.")

        healthy_count = stored.durable_copy_count

        if healthy_count == 0:
            return "UNAVAILABLE"
        if healthy_count < self.replication_factor:
            return "DEGRADED"
        return "AVAILABLE"

    def estimated_monthly_storage_cost(
        self,
        price_per_gib_month: float,
    ) -> float:
        total_bytes = sum(
            stored.obj.size_bytes
            for stored in self._objects.values()
        )

        replicated_bytes = total_bytes * self.replication_factor
        gib = replicated_bytes / (1024**3)
        return gib * price_per_gib_month

    def list_objects(self) -> List[StorageObject]:
        return [stored.obj for stored in self._objects.values()]


@dataclass
class DurabilityModel:
    annual_failure_probability_per_replica: float
    independent_replicas: int

    def estimated_annual_data_loss_probability(self) -> float:
        p = self.annual_failure_probability_per_replica
        n = self.independent_replicas

        if not 0 <= p <= 1:
            raise ValueError("Failure probability must be between 0 and 1.")
        if n < 1:
            raise ValueError("Replica count must be positive.")

        return p**n

    def estimated_nines(self) -> float:
        loss_probability = self.estimated_annual_data_loss_probability()

        if loss_probability <= 0:
            return float("inf")

        return -__import__("math").log10(loss_probability)


@dataclass
class AvailabilityModel:
    replica_availability: float
    replica_count: int

    def system_availability(self) -> float:
        a = self.replica_availability
        n = self.replica_count

        if not 0 <= a <= 1:
            raise ValueError("Availability must be between 0 and 1.")
        if n < 1:
            raise ValueError("Replica count must be positive.")

        # The system is available when at least one independent replica works.
        return 1 - (1 - a) ** n


def calculate_storage_redundancy(
    logical_size_gib: float,
    replica_count: int,
) -> float:
    if logical_size_gib < 0:
        raise ValueError("Logical size cannot be negative.")
    if replica_count < 1:
        raise ValueError("Replica count must be positive.")
    return logical_size_gib * replica_count


def demonstrate_basic_storage() -> None:
    print("\n=== Basic Object Storage ===")

    bucket = CloudStorageBucket(
        name="research-archive",
        regions=("Mumbai", "Hyderabad", "Delhi"),
        replication_factor=3,
    )

    document = bucket.put(
        "research/report.txt",
        b"Cloud storage durability and availability study.",
    )

    print("Object:", document.obj.key)
    print("Size:", document.obj.size_bytes, "bytes")
    print("SHA-256:", document.obj.content_hash)
    print("Status:", bucket.availability_status(document.obj.key))
    print("Replication:", bucket.replication_status(document.obj.key))


def demonstrate_availability_and_failure() -> None:
    print("\n=== Availability and Failure Simulation ===")

    bucket = CloudStorageBucket(
        name="production-assets",
        regions=("Mumbai", "Singapore", "Frankfurt"),
        replication_factor=3,
    )

    bucket.put("images/product-001.bin", b"product image data")

    print("Initial:", bucket.availability_status("images/product-001.bin"))

    bucket.simulate_region_failure("Mumbai")
    print(
        "After Mumbai failure:",
        bucket.availability_status("images/product-001.bin"),
    )
    print(bucket.replication_status("images/product-001.bin"))

    bucket.simulate_region_failure("Singapore")
    print(
        "After second regional failure:",
        bucket.availability_status("images/product-001.bin"),
    )

    bucket.recover_region("Mumbai")
    print(
        "After Mumbai recovery:",
        bucket.availability_status("images/product-001.bin"),
    )


def demonstrate_durability_math() -> None:
    print("\n=== Durability Modeling ===")

    model = DurabilityModel(
        annual_failure_probability_per_replica=0.001,
        independent_replicas=3,
    )

    probability = model.estimated_annual_data_loss_probability()
    nines = model.estimated_nines()

    print(f"Estimated annual data-loss probability: {probability:.12f}")
    print(f"Approximate durability scale: {nines:.2f} nines")

    availability = AvailabilityModel(
        replica_availability=0.999,
        replica_count=3,
    )

    print(
        "Independent replica availability:",
        f"{availability.system_availability():.8f}",
    )

    print(
        "Important distinction: replication can improve availability and "
        "durability, but the guarantees depend on failure independence, "
        "replica placement, repair behavior, and the provider's architecture."
    )


def demonstrate_cost_and_redundancy() -> None:
    print("\n=== Logical Storage Versus Replicated Storage ===")

    logical_size = 250.0
    replicas = 3
    physical_equivalent = calculate_storage_redundancy(
        logical_size,
        replicas,
    )

    print(f"Logical storage: {logical_size:.1f} GiB")
    print(f"Replication factor: {replicas}")
    print(f"Approximate replicated capacity: {physical_equivalent:.1f} GiB")

    bucket = CloudStorageBucket(
        name="cost-analysis",
        regions=("Mumbai", "Hyderabad", "Chennai"),
        replication_factor=3,
    )

    bucket.put("dataset.csv", b"x" * 1024 * 1024)
    print(
        "Estimated monthly storage cost:",
        f"${bucket.estimated_monthly_storage_cost(0.02):.6f}",
    )


def demonstrate_validation_and_failure() -> None:
    print("\n=== Validation and Failure Conditions ===")

    try:
        CloudStorageBucket(
            name="invalid",
            regions=("Mumbai",),
            replication_factor=2,
        )
    except ValueError as exc:
        print("Configuration rejected:", exc)

    bucket = CloudStorageBucket(
        name="validation",
        regions=("Mumbai", "Hyderabad"),
        replication_factor=2,
    )

    try:
        bucket.put("", b"invalid")
    except InvalidObjectError as exc:
        print("Object rejected:", exc)

    try:
        bucket.get("missing.txt")
    except ObjectNotFoundError as exc:
        print("Read failed:", exc)

    bucket.put("critical.txt", b"critical information")
    bucket.simulate_region_failure("Mumbai")
    bucket.simulate_region_failure("Hyderabad")

    try:
        bucket.get("critical.txt")
    except InsufficientReplicationError as exc:
        print("Availability failure:", exc)


def demonstrate_storage_design() -> None:
    print("\n=== Practical Storage Design ===")

    scenarios = {
        "active application data": {
            "storage_class": "standard",
            "priority": "low latency and high availability",
            "replication": "multi-zone or multi-region according to RTO/RPO",
        },
        "historical logs": {
            "storage_class": "infrequent-access",
            "priority": "lower cost with acceptable retrieval latency",
            "replication": "provider-managed redundancy plus lifecycle policy",
        },
        "long-term archive": {
            "storage_class": "archive",
            "priority": "low storage cost and long retention",
            "replication": "durable provider storage with explicit recovery planning",
        },
    }

    for scenario, properties in scenarios.items():
        print(f"\n{scenario}")
        for key, value in properties.items():
            print(f"  {key}: {value}")

    print(
        "\nRPO describes how much data loss is acceptable after a failure. "
        "RTO describes how quickly service must be restored. "
        "Replication alone does not define either target."
    )


def main() -> None:
    demonstrate_basic_storage()
    demonstrate_availability_and_failure()
    demonstrate_durability_math()
    demonstrate_cost_and_redundancy()
    demonstrate_validation_and_failure()
    demonstrate_storage_design()


if __name__ == "__main__":
    main()
