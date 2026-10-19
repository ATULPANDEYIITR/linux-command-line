"""
Storage Performance Laboratory

A self-contained study of storage performance through:
- IOPS
- throughput
- latency
- caching
- storage tiers
- workload characterization
- queue depth
- batching
- cache policies
- tier placement
- performance measurement
- optimization trade-offs

The program uses only the Python standard library and simulates storage rather
than requiring access to a real disk. This makes the examples deterministic
and safe to execute on a development machine.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum
import math
import random
import statistics
import time
from typing import Iterable


BYTES_PER_MIB = 1024 * 1024
BYTES_PER_GIB = 1024 * BYTES_PER_MIB


class Operation(Enum):
    READ = "read"
    WRITE = "write"


class StorageTier(Enum):
    NVME = "NVMe"
    SSD = "SSD"
    HDD = "HDD"
    ARCHIVE = "Archive"


@dataclass(frozen=True)
class StorageProfile:
    name: str
    iops_limit: float
    throughput_mib_s: float
    base_latency_ms: float
    latency_jitter_ms: float
    capacity_gib: float
    cost_per_gib_month: float


TIER_PROFILES = {
    StorageTier.NVME: StorageProfile(
        "NVMe", 900_000, 7_000, 0.08, 0.04, 2_000, 0.12
    ),
    StorageTier.SSD: StorageProfile(
        "SSD", 120_000, 1_200, 0.45, 0.20, 8_000, 0.07
    ),
    StorageTier.HDD: StorageProfile(
        "HDD", 300, 250, 8.0, 3.0, 20_000, 0.025
    ),
    StorageTier.ARCHIVE: StorageProfile(
        "Archive", 50, 100, 80.0, 20.0, 100_000, 0.008
    ),
}


@dataclass
class OperationRecord:
    operation: Operation
    size_bytes: int
    latency_ms: float
    cache_hit: bool = False
    tier: StorageTier = StorageTier.SSD

    @property
    def duration_seconds(self) -> float:
        return self.latency_ms / 1000.0


@dataclass
class PerformanceMetrics:
    operations: int = 0
    bytes_processed: int = 0
    total_latency_ms: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0

    def record(self, operation: OperationRecord) -> None:
        self.operations += 1
        self.bytes_processed += operation.size_bytes
        self.total_latency_ms += operation.latency_ms
        self.latencies_ms.append(operation.latency_ms)
        if operation.cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / self.operations if self.operations else 0.0

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        if not 0 < p <= 100:
            raise ValueError("Percentile must be between 0 and 100.")
        values = sorted(self.latencies_ms)
        position = (len(values) - 1) * p / 100
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return values[lower]
        weight = position - lower
        return values[lower] * (1 - weight) + values[upper] * weight

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total else 0.0


@dataclass
class WorkloadRequest:
    operation: Operation
    offset_bytes: int
    size_bytes: int


def human_bytes(value: float) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.2f} {unit}"
        amount /= 1024
    return f"{amount:.2f} TiB"


def calculate_iops(operations: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        raise ValueError("Elapsed time must be positive.")
    return operations / elapsed_seconds


def calculate_throughput(bytes_processed: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        raise ValueError("Elapsed time must be positive.")
    return bytes_processed / BYTES_PER_MIB / elapsed_seconds


def bandwidth_limited_iops(
    throughput_mib_s: float, io_size_bytes: int
) -> float:
    if io_size_bytes <= 0:
        raise ValueError("I/O size must be positive.")
    return throughput_mib_s * BYTES_PER_MIB / io_size_bytes


def demonstrate_basic_metrics() -> None:
    print("\n=== Fundamental Storage Metrics ===")

    operations = 120_000
    elapsed = 2.0
    block_size = 4096

    iops = calculate_iops(operations, elapsed)
    throughput = calculate_throughput(operations * block_size, elapsed)

    print(f"Operations: {operations:,}")
    print(f"Elapsed time: {elapsed:.2f} s")
    print(f"Block size: {block_size:,} bytes")
    print(f"IOPS: {iops:,.0f}")
    print(f"Throughput: {throughput:,.2f} MiB/s")

    print("\nThe same device can show very different IOPS and throughput")
    print("depending on request size. Small random requests emphasize IOPS;")
    print("large sequential requests emphasize bandwidth.")


def demonstrate_latency_and_iops_relationship() -> None:
    print("\n=== Latency and Theoretical IOPS ===")

    latencies_ms = [0.1, 0.5, 1.0, 5.0, 10.0]
    queue_depth = 1

    for latency in latencies_ms:
        theoretical_iops = queue_depth / (latency / 1000)
        print(
            f"Latency {latency:5.1f} ms -> "
            f"QD={queue_depth} theoretical IOPS: {theoretical_iops:,.0f}"
        )

    print(
        "\nAt queue depth one, latency strongly limits the number of operations "
        "that can complete per second."
    )

    for qd in (1, 4, 16, 64):
        iops = qd / (1.0 / 1000)
        print(f"1 ms latency, QD={qd:2d} -> {iops:,.0f} theoretical IOPS")


class LRUCache:
    """Byte-aware LRU cache for storage blocks."""

    def __init__(self, capacity_bytes: int):
        if capacity_bytes <= 0:
            raise ValueError("Cache capacity must be positive.")
        self.capacity_bytes = capacity_bytes
        self.entries: OrderedDict[int, bytes] = OrderedDict()
        self.current_bytes = 0

    def get(self, key: int) -> bytes | None:
        value = self.entries.get(key)
        if value is None:
            return None
        self.entries.move_to_end(key)
        return value

    def put(self, key: int, value: bytes) -> None:
        value_size = len(value)

        if value_size > self.capacity_bytes:
            return

        old = self.entries.pop(key, None)
        if old is not None:
            self.current_bytes -= len(old)

        while self.current_bytes + value_size > self.capacity_bytes:
            _, evicted = self.entries.popitem(last=False)
            self.current_bytes -= len(evicted)

        self.entries[key] = value
        self.current_bytes += value_size

    def __len__(self) -> int:
        return len(self.entries)


class SimulatedStorage:
    """
    Simulates a storage tier.

    Latency contains a fixed component plus random jitter. Throughput and IOPS
    limits are modeled independently because a storage system can be limited by
    either request rate or bandwidth.
    """

    def __init__(
        self,
        tier: StorageTier,
        seed: int = 42,
        cache_capacity_bytes: int = 0,
    ):
        self.tier = tier
        self.profile = TIER_PROFILES[tier]
        self.random = random.Random(seed)
        self.cache = (
            LRUCache(cache_capacity_bytes)
            if cache_capacity_bytes > 0
            else None
        )

    def _latency(self, size_bytes: int) -> float:
        if size_bytes <= 0:
            raise ValueError("I/O size must be positive.")

        bandwidth_ms = (
            size_bytes / BYTES_PER_MIB
        ) / self.profile.throughput_mib_s * 1000

        iops_ms = 1000 / self.profile.iops_limit

        return (
            self.profile.base_latency_ms
            + max(bandwidth_ms, iops_ms)
            + self.random.uniform(0, self.profile.latency_jitter_ms)
        )

    def read(self, block_id: int, size_bytes: int) -> OperationRecord:
        if self.cache is not None:
            cached = self.cache.get(block_id)
            if cached is not None:
                return OperationRecord(
                    Operation.READ,
                    size_bytes,
                    0.03,
                    cache_hit=True,
                    tier=self.tier,
                )

        latency = self._latency(size_bytes)

        if self.cache is not None:
            self.cache.put(block_id, bytes(size_bytes))

        return OperationRecord(
            Operation.READ,
            size_bytes,
            latency,
            cache_hit=False,
            tier=self.tier,
        )

    def write(self, block_id: int, size_bytes: int) -> OperationRecord:
        latency = self._latency(size_bytes)

        if self.cache is not None:
            self.cache.put(block_id, bytes(size_bytes))

        return OperationRecord(
            Operation.WRITE,
            size_bytes,
            latency,
            cache_hit=False,
            tier=self.tier,
        )


def run_workload(
    storage: SimulatedStorage,
    requests: Iterable[WorkloadRequest],
) -> PerformanceMetrics:
    metrics = PerformanceMetrics()

    for request in requests:
        block_id = request.offset_bytes // max(request.size_bytes, 1)

        if request.operation is Operation.READ:
            result = storage.read(block_id, request.size_bytes)
        else:
            result = storage.write(block_id, request.size_bytes)

        metrics.record(result)

    return metrics


def print_metrics(name: str, metrics: PerformanceMetrics) -> None:
    print(f"\n{name}")
    print(f"Operations:       {metrics.operations:,}")
    print(f"Data processed:   {human_bytes(metrics.bytes_processed)}")
    print(f"Average latency:  {metrics.average_latency_ms:.3f} ms")
    print(f"P50 latency:      {metrics.percentile(50):.3f} ms")
    print(f"P95 latency:      {metrics.percentile(95):.3f} ms")
    print(f"P99 latency:      {metrics.percentile(99):.3f} ms")
    print(f"Cache hit rate:   {metrics.cache_hit_rate * 100:.2f}%")


def build_random_workload(
    count: int,
    size_bytes: int,
    read_ratio: float,
    address_space_bytes: int,
    seed: int = 42,
) -> list[WorkloadRequest]:
    if count <= 0:
        raise ValueError("Workload count must be positive.")
    if not 0 <= read_ratio <= 1:
        raise ValueError("Read ratio must be between 0 and 1.")
    if address_space_bytes < size_bytes:
        raise ValueError("Address space must fit at least one request.")

    rng = random.Random(seed)
    max_offset = address_space_bytes - size_bytes
    return [
        WorkloadRequest(
            Operation.READ if rng.random() < read_ratio else Operation.WRITE,
            rng.randrange(0, max_offset + 1, size_bytes),
            size_bytes,
        )
        for _ in range(count)
    ]


def build_hotset_workload(
    count: int,
    size_bytes: int,
    hot_blocks: int,
    address_space_bytes: int,
    seed: int = 7,
) -> list[WorkloadRequest]:
    if hot_blocks <= 0:
        raise ValueError("Hot-set size must be positive.")

    rng = random.Random(seed)
    max_block = address_space_bytes // size_bytes
    if hot_blocks > max_block:
        raise ValueError("Hot-set exceeds address space.")

    requests = []
    for _ in range(count):
        block = rng.randrange(hot_blocks)
        requests.append(
            WorkloadRequest(
                Operation.READ,
                block * size_bytes,
                size_bytes,
            )
        )
    return requests


def compare_storage_tiers() -> None:
    print("\n=== Storage Tier Comparison ===")

    requests = build_random_workload(
        count=2_000,
        size_bytes=4096,
        read_ratio=0.9,
        address_space_bytes=BYTES_PER_GIB,
    )

    for tier in StorageTier:
        storage = SimulatedStorage(tier)
        metrics = run_workload(storage, requests)
        print_metrics(tier.value, metrics)

    print("\nTier selection is a workload decision:")
    print("NVMe is suited to latency-sensitive, high-IOPS workloads.")
    print("SSD provides strong general-purpose random I/O performance.")
    print("HDD is economical for larger sequential workloads.")
    print("Archive storage favors capacity and cost over interactive latency.")


def demonstrate_cache_effect() -> None:
    print("\n=== Caching Effect ===")

    workload = build_hotset_workload(
        count=5_000,
        size_bytes=4096,
        hot_blocks=128,
        address_space_bytes=BYTES_PER_GIB,
    )

    uncached = run_workload(
        SimulatedStorage(StorageTier.SSD, cache_capacity_bytes=0),
        workload,
    )

    cached = run_workload(
        SimulatedStorage(
            StorageTier.SSD,
            cache_capacity_bytes=128 * 4096,
        ),
        workload,
    )

    print_metrics("SSD without cache", uncached)
    print_metrics("SSD with 512 KiB LRU cache", cached)

    print(
        "\nCaching reduces storage requests when the workload has temporal "
        "or spatial locality. A cache miss still pays the underlying tier cost."
    )


def demonstrate_sequential_vs_random() -> None:
    print("\n=== Sequential Versus Random Access ===")

    size = 128 * 1024
    sequential = [
        WorkloadRequest(Operation.READ, i * size, size)
        for i in range(500)
    ]

    random_requests = build_random_workload(
        count=500,
        size_bytes=size,
        read_ratio=1.0,
        address_space_bytes=BYTES_GIB,
        seed=99,
    )

    for name, workload in (
        ("Sequential 128 KiB reads", sequential),
        ("Random 128 KiB reads", random_requests),
    ):
        metrics = run_workload(
            SimulatedStorage(StorageTier.HDD),
            workload,
        )
        print_metrics(name, metrics)


def estimate_service_time(
    profile: StorageProfile,
    requests: int,
    request_size: int,
    queue_depth: int,
) -> float:
    if requests <= 0 or request_size <= 0 or queue_depth <= 0:
        raise ValueError("All workload parameters must be positive.")

    iops_bound = profile.iops_limit
    throughput_bound = (
        profile.throughput_mib_s
        * BYTES_PER_MIB
        / request_size
    )
    sustainable_iops = min(iops_bound, throughput_bound)
    effective_iops = min(sustainable_iops * queue_depth, sustainable_iops)

    return requests / effective_iops


def demonstrate_io_size_and_queue_depth() -> None:
    print("\n=== I/O Size and Queue Depth ===")

    profile = TIER_PROFILES[StorageTier.NVME]

    for io_size in (4096, 64 * 1024, 1024 * 1024):
        bandwidth_bound = bandwidth_limited_iops(
            profile.throughput_mib_s, io_size
        )
        effective = min(profile.iops_limit, bandwidth_bound)

        print(
            f"I/O size {human_bytes(io_size):>10}: "
            f"bandwidth-limited IOPS={bandwidth_bound:>10,.0f}, "
            f"effective limit={effective:>10,.0f}"
        )

    print(
        "\nQueue depth can expose parallelism in the device, but increasing "
        "queue depth indefinitely does not guarantee better application "
        "latency. Saturation commonly raises tail latency."
    )


class StorageTierManager:
    """Places objects into tiers using access frequency and age."""

    def __init__(self):
        self.objects: dict[str, dict] = {}

    def register(
        self,
        object_id: str,
        size_bytes: int,
        accesses_per_day: float,
        age_days: int,
    ) -> None:
        if not object_id.strip():
            raise ValueError("Object ID cannot be empty.")
        if size_bytes <= 0:
            raise ValueError("Object size must be positive.")
        if accesses_per_day < 0 or age_days < 0:
            raise ValueError("Access frequency and age cannot be negative.")

        self.objects[object_id] = {
            "size_bytes": size_bytes,
            "accesses_per_day": accesses_per_day,
            "age_days": age_days,
        }

    def recommend(self, object_id: str) -> StorageTier:
        item = self.objects[object_id]
        frequency = item["accesses_per_day"]
        age = item["age_days"]

        if frequency >= 100:
            return StorageTier.NVME
        if frequency >= 10 or age < 30:
            return StorageTier.SSD
        if age < 365:
            return StorageTier.HDD
        return StorageTier.ARCHIVE


def demonstrate_tiering() -> None:
    print("\n=== Storage Tiering Policy ===")

    manager = StorageTierManager()

    manager.register("checkout-cache", 2 * BYTES_PER_GIB, 500, 2)
    manager.register("customer-database", 200 * BYTES_PER_GIB, 40, 15)
    manager.register("monthly-reports", 50 * BYTES_PER_GIB, 2, 180)
    manager.register("audit-archive", 500 * BYTES_PER_GIB, 0.1, 900)

    for object_id in manager.objects:
        print(f"{object_id:20s} -> {manager.recommend(object_id).value}")

    print(
        "\nTiering should consider access frequency, latency requirements, "
        "data age, capacity, recovery requirements, and cost rather than "
        "using storage speed as the only criterion."
    )


def estimate_monthly_storage_cost(
    tier: StorageTier,
    capacity_gib: float,
) -> float:
    if capacity_gib < 0:
        raise ValueError("Capacity cannot be negative.")
    return capacity_gib * TIER_PROFILES[tier].cost_per_gib_month


def demonstrate_cost_performance_tradeoff() -> None:
    print("\n=== Cost and Performance Trade-off ===")

    capacity = 1_000

    for tier in StorageTier:
        profile = TIER_PROFILES[tier]
        cost = estimate_monthly_storage_cost(tier, capacity)
        print(
            f"{tier.value:8s}: "
            f"${cost:8.2f}/month for {capacity:,} GiB, "
            f"{profile.iops_limit:,.0f} IOPS, "
            f"{profile.throughput_mib_s:,.0f} MiB/s"
        )


def benchmark_cpu_overhead() -> None:
    print("\n=== Measurement Technique ===")

    start = time.perf_counter()
    checksum = 0

    for value in range(500_000):
        checksum ^= value

    elapsed = time.perf_counter() - start
    print(f"Measured computation interval: {elapsed * 1000:.3f} ms")
    print(f"Checksum prevents the loop result from being unused: {checksum}")

    print(
        "\nReal storage benchmarks should separate application overhead, "
        "filesystem overhead, device latency, cache effects, warm-up, and "
        "measurement overhead. A single average can hide P99 latency spikes."
    )


def demonstrate_percentiles() -> None:
    print("\n=== Tail Latency ===")

    metrics = PerformanceMetrics()

    rng = random.Random(123)
    for _ in range(1_000):
        latency = rng.gauss(0.5, 0.08)
        if rng.random() < 0.01:
            latency += rng.uniform(10, 40)

        metrics.record(
            OperationRecord(
                Operation.READ,
                4096,
                max(0.05, latency),
                tier=StorageTier.SSD,
            )
        )

    print(f"Average: {metrics.average_latency_ms:.3f} ms")
    print(f"P50:     {metrics.percentile(50):.3f} ms")
    print(f"P95:     {metrics.percentile(95):.3f} ms")
    print(f"P99:     {metrics.percentile(99):.3f} ms")

    print(
        "\nTail latency matters for interactive and distributed systems because "
        "a small number of slow storage operations can delay complete requests."
    )


def validate_workload(request: WorkloadRequest, capacity_bytes: int) -> None:
    if request.size_bytes <= 0:
        raise ValueError("Request size must be positive.")
    if request.offset_bytes < 0:
        raise ValueError("Offset cannot be negative.")
    if request.offset_bytes + request.size_bytes > capacity_bytes:
        raise ValueError("Request exceeds storage capacity.")


def demonstrate_validation() -> None:
    print("\n=== Validation and Failure Conditions ===")

    capacity = 10 * BYTES_PER_MIB

    invalid_requests = [
        WorkloadRequest(Operation.READ, -1, 4096),
        WorkloadRequest(Operation.WRITE, 0, 0),
        WorkloadRequest(Operation.READ, 9 * BYTES_PER_MIB, 2 * BYTES_PER_MIB),
    ]

    for request in invalid_requests:
        try:
            validate_workload(request, capacity)
        except ValueError as exc:
            print(f"Rejected request: {exc}")


def explain_optimization_strategy() -> None:
    print("\n=== Practical Optimization Decisions ===")

    strategies = {
        "Reduce latency": "Use faster media, shorter I/O paths, and locality-aware caching.",
        "Increase IOPS": "Use sufficient parallelism and smaller requests when workload semantics permit.",
        "Increase throughput": "Use larger sequential requests and a device with adequate bandwidth.",
        "Control tail latency": "Avoid uncontrolled queue growth and monitor P95/P99/P99.9.",
        "Improve cache efficiency": "Keep frequently reused data in a cache sized for the actual working set.",
        "Control cost": "Move cold data to cheaper tiers without violating access or recovery requirements.",
        "Avoid false gains": "Benchmark with realistic queue depth, read/write ratio, request size, and warm/cold cache states.",
    }

    for goal, approach in strategies.items():
        print(f"{goal}: {approach}")


def main() -> None:
    print("Storage Performance Laboratory")
    print("==============================")

    demonstrate_basic_metrics()
    demonstrate_latency_and_iops_relationship()
    compare_storage_tiers()
    demonstrate_cache_effect()
    demonstrate_sequential_vs_random()
    demonstrate_io_size_and_queue_depth()
    demonstrate_tiering()
    demonstrate_cost_performance_tradeoff()
    demonstrate_percentiles()
    demonstrate_validation()
    benchmark_cpu_overhead()
    explain_optimization_strategy()

    print("\n=== Storage Performance Model ===")
    print(
        "Performance is constrained by the narrowest relevant resource: "
        "latency, IOPS capacity, bandwidth, queueing, cache effectiveness, "
        "or the selected storage tier."
    )


if __name__ == "__main__":
    main()
