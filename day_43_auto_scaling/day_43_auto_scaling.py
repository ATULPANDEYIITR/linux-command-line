#!/usr/bin/env python3
"""
Auto Scaling: horizontal scaling, vertical scaling, scaling policies, and
automated infrastructure expansion.

Executable with Python 3.10+ and the standard library.

The simulator models a web service receiving variable traffic. It compares
horizontal and vertical scaling, evaluates metric-based policies, accounts
for startup delays, applies cooldowns, simulates instance failures, and
estimates infrastructure costs. It does not provision real cloud resources.
"""

from __future__ import annotations

import json
import logging
import math
import random
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
LOGGER = logging.getLogger("autoscaling")


class ScalingDirection(str, Enum):
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NONE = "none"


class ScalingMode(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(frozen=True)
class InstanceType:
    name: str
    cpu_cores: int
    memory_gb: float
    hourly_cost: float
    requests_per_second_per_core: float = 120.0

    def __post_init__(self) -> None:
        if self.cpu_cores <= 0:
            raise ValueError("CPU cores must be positive.")
        if self.memory_gb <= 0 or self.hourly_cost < 0:
            raise ValueError("Memory must be positive and cost non-negative.")
        if self.requests_per_second_per_core <= 0:
            raise ValueError("Request capacity per core must be positive.")

    @property
    def capacity_rps(self) -> float:
        return self.cpu_cores * self.requests_per_second_per_core


@dataclass
class Instance:
    instance_id: str
    instance_type: InstanceType
    state: str = "pending"
    ready_at: int = 0
    healthy: bool = True
    consecutive_low_load: int = 0

    @property
    def capacity_rps(self) -> float:
        return self.instance_type.capacity_rps


@dataclass(frozen=True)
class ScalingPolicy:
    name: str
    target_cpu_percent: float = 60.0
    scale_out_threshold: float = 75.0
    scale_in_threshold: float = 25.0
    scale_out_step: int = 1
    scale_in_step: int = 1
    cooldown_seconds: int = 120
    evaluation_periods: int = 2
    minimum_instances: int = 2
    maximum_instances: int = 10
    instance_warmup_seconds: int = 60
    maximum_scale_change: int = 3

    def __post_init__(self) -> None:
        if not 0 < self.scale_in_threshold < self.scale_out_threshold <= 100:
            raise ValueError("Scaling thresholds must be ordered within 0-100.")
        if self.scale_out_step < 1 or self.scale_in_step < 1:
            raise ValueError("Scaling steps must be positive.")
        if self.minimum_instances < 1:
            raise ValueError("At least one instance is required.")
        if self.maximum_instances < self.minimum_instances:
            raise ValueError("Maximum instances cannot be below minimum.")
        if self.cooldown_seconds < 0 or self.instance_warmup_seconds < 0:
            raise ValueError("Cooldown and warmup cannot be negative.")
        if self.evaluation_periods < 1 or self.maximum_scale_change < 1:
            raise ValueError("Evaluation periods and scale-change limit must be positive.")


@dataclass
class Metrics:
    timestamp: int
    incoming_rps: float
    available_capacity_rps: float
    cpu_percent: float
    memory_percent: float
    desired_instances: int
    ready_instances: int
    pending_instances: int
    served_rps: float
    rejected_rps: float
    estimated_hourly_cost: float
    average_latency_ms: float


@dataclass
class ScalingEvent:
    timestamp: int
    direction: str
    previous_desired: int
    new_desired: int
    reason: str


@dataclass
class AutoScalingGroup:
    instance_type: InstanceType
    policy: ScalingPolicy
    current_time: int = 0
    desired_instances: int = 2
    instances: list[Instance] = field(default_factory=list)
    next_instance_number: int = 1
    last_scaling_time: int = -10**9
    events: list[ScalingEvent] = field(default_factory=list)
    history: list[Metrics] = field(default_factory=list)
    cpu_history: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        self.desired_instances = min(
            self.policy.maximum_instances,
            max(self.policy.minimum_instances, self.desired_instances),
        )
        self.cpu_history = deque(maxlen=self.policy.evaluation_periods)

        # Initial capacity is available immediately.
        for _ in range(self.desired_instances):
            self.instances.append(
                Instance(
                    instance_id=f"web-{self.next_instance_number:03d}",
                    instance_type=self.instance_type,
                    state="ready",
                )
            )
            self.next_instance_number += 1

    @property
    def ready_instances(self) -> list[Instance]:
        return [
            instance
            for instance in self.instances
            if instance.state == "ready" and instance.healthy
        ]

    @property
    def pending_instances(self) -> list[Instance]:
        return [i for i in self.instances if i.state == "pending"]

    @property
    def available_capacity_rps(self) -> float:
        return sum(i.capacity_rps for i in self.ready_instances)

    @property
    def estimated_hourly_cost(self) -> float:
        # Pending resources may already incur cloud charges.
        return sum(
            i.instance_type.hourly_cost
            for i in self.instances
            if i.healthy
        )

    def _new_instance(self, ready_at: int) -> Instance:
        instance = Instance(
            instance_id=f"web-{self.next_instance_number:03d}",
            instance_type=self.instance_type,
            state="pending" if ready_at > self.current_time else "ready",
            ready_at=ready_at,
        )
        self.next_instance_number += 1
        return instance

    def advance_time(self, seconds: int) -> None:
        if seconds < 0:
            raise ValueError("Time cannot move backwards.")
        self.current_time += seconds
        for instance in self.instances:
            if (
                instance.state == "pending"
                and instance.ready_at <= self.current_time
                and instance.healthy
            ):
                instance.state = "ready"
                LOGGER.info("Instance %s is ready.", instance.instance_id)

    def set_instance_health(self, instance_id: str, healthy: bool) -> None:
        instance = next(
            (item for item in self.instances if item.instance_id == instance_id),
            None,
        )
        if instance is None:
            raise ValueError(f"Unknown instance: {instance_id}")
        instance.healthy = healthy
        if not healthy:
            instance.state = "unhealthy"
        elif instance.state == "unhealthy":
            instance.state = "pending"
            instance.ready_at = self.current_time + self.policy.instance_warmup_seconds

    def _record_event(
        self,
        direction: ScalingDirection,
        previous: int,
        reason: str,
    ) -> None:
        self.events.append(
            ScalingEvent(
                timestamp=self.current_time,
                direction=direction.value,
                previous_desired=previous,
                new_desired=self.desired_instances,
                reason=reason,
            )
        )

    def scale_out(self, count: int, reason: str) -> int:
        previous = self.desired_instances
        permitted = min(
            count,
            self.policy.maximum_instances - self.desired_instances,
            self.policy.maximum_scale_change,
        )
        if permitted <= 0:
            return 0

        self.desired_instances += permitted
        for _ in range(permitted):
            self.instances.append(
                self._new_instance(
                    self.current_time + self.policy.instance_warmup_seconds
                )
            )

        self.last_scaling_time = self.current_time
        self._record_event(ScalingDirection.SCALE_OUT, previous, reason)
        LOGGER.info(
            "Scale out: desired capacity %d -> %d (%s).",
            previous,
            self.desired_instances,
            reason,
        )
        return permitted

    def scale_in(self, count: int, reason: str) -> int:
        previous = self.desired_instances
        permitted = min(
            count,
            self.desired_instances - self.policy.minimum_instances,
            self.policy.maximum_scale_change,
        )
        if permitted <= 0:
            return 0

        # Remove pending instances first, then healthy ready instances.
        # A production platform must also respect connection draining and
        # minimum healthy capacity during instance termination.
        candidates = sorted(
            [
                i for i in self.instances
                if i.healthy and i.state in {"pending", "ready"}
            ],
            key=lambda i: (i.state != "pending", i.instance_id),
        )
        removed = candidates[:permitted]
        if not removed:
            return 0

        removed_ids = {item.instance_id for item in removed}
        self.instances = [
            item for item in self.instances if item.instance_id not in removed_ids
        ]
        self.desired_instances -= len(removed)
        self.last_scaling_time = self.current_time
        self._record_event(ScalingDirection.SCALE_IN, previous, reason)
        LOGGER.info(
            "Scale in: desired capacity %d -> %d (%s).",
            previous,
            self.desired_instances,
            reason,
        )
        return len(removed)

    def observe(
        self,
        incoming_rps: float,
        memory_demand_gb_per_instance: float = 1.0,
    ) -> Metrics:
        if not math.isfinite(incoming_rps) or incoming_rps < 0:
            raise ValueError("Incoming request rate must be finite and non-negative.")
        if not math.isfinite(memory_demand_gb_per_instance) or memory_demand_gb_per_instance < 0:
            raise ValueError("Memory demand must be finite and non-negative.")

        capacity = self.available_capacity_rps
        served = min(incoming_rps, capacity)
        rejected = max(0.0, incoming_rps - served)
        cpu = min(100.0, 100.0 * incoming_rps / capacity) if capacity else 100.0

        ready = self.ready_instances
        total_memory = sum(i.instance_type.memory_gb for i in ready)
        memory_needed = len(ready) * memory_demand_gb_per_instance
        memory = min(100.0, 100.0 * memory_needed / total_memory) if total_memory else 100.0

        # This simplified latency model represents queueing pressure. Real
        # latency requires request traces and an explicit queueing model.
        if capacity <= 0 or rejected > 0:
            latency = 1000.0 + rejected * 10.0
        else:
            utilization = incoming_rps / max(capacity, 1e-9)
            latency = 20.0 + 80.0 * utilization / max(0.05, 1.0 - utilization)

        metrics = Metrics(
            timestamp=self.current_time,
            incoming_rps=incoming_rps,
            available_capacity_rps=capacity,
            cpu_percent=round(cpu, 2),
            memory_percent=round(memory, 2),
            desired_instances=self.desired_instances,
            ready_instances=len(ready),
            pending_instances=len(self.pending_instances),
            served_rps=round(served, 2),
            rejected_rps=round(rejected, 2),
            estimated_hourly_cost=round(self.estimated_hourly_cost, 4),
            average_latency_ms=round(min(latency, 60000.0), 2),
        )
        self.history.append(metrics)
        self.cpu_history.append(cpu)
        return metrics

    def evaluate_policy(self) -> ScalingDirection:
        if len(self.cpu_history) < self.policy.evaluation_periods:
            return ScalingDirection.NONE

        average_cpu = statistics.fmean(self.cpu_history)
        elapsed = self.current_time - self.last_scaling_time
        if elapsed < self.policy.cooldown_seconds:
            return ScalingDirection.NONE

        if average_cpu > self.policy.scale_out_threshold:
            self.scale_out(
                self.policy.scale_out_step,
                f"Average CPU {average_cpu:.1f}% exceeds "
                f"{self.policy.scale_out_threshold:.1f}%",
            )
            return ScalingDirection.SCALE_OUT

        if average_cpu < self.policy.scale_in_threshold:
            self.scale_in(
                self.policy.scale_in_step,
                f"Average CPU {average_cpu:.1f}% is below "
                f"{self.policy.scale_in_threshold:.1f}%",
            )
            return ScalingDirection.SCALE_IN

        return ScalingDirection.NONE


@dataclass(frozen=True)
class VerticalCapacity:
    instance_type: InstanceType

    def evaluate_replacement(
        self,
        incoming_rps: float,
        utilization_target: float = 0.60,
    ) -> int:
        if incoming_rps < 0 or not 0 < utilization_target < 1:
            raise ValueError("Invalid traffic or utilization target.")
        return math.ceil(
            incoming_rps / (self.instance_type.capacity_rps * utilization_target)
        )


def simulate_traffic(
    group: AutoScalingGroup,
    traffic: Iterable[float],
    interval_seconds: int = 30,
) -> list[Metrics]:
    if interval_seconds <= 0:
        raise ValueError("Interval must be positive.")

    results: list[Metrics] = []
    for incoming_rps in traffic:
        group.advance_time(interval_seconds)
        metrics = group.observe(incoming_rps)
        results.append(metrics)
        group.evaluate_policy()
    return results


def traffic_profile() -> list[float]:
    """A realistic ramp, peak, and quiet period in requests per second."""
    return (
        [80.0] * 4
        + [250.0] * 5
        + [650.0] * 6
        + [1100.0] * 4
        + [400.0] * 5
        + [70.0] * 8
    )


def print_metrics_table(metrics: list[Metrics]) -> None:
    print(
        "\nTime(s)  Incoming  Capacity  CPU%   Ready  Pending  Rejected  "
        "Latency(ms)  Cost($/h)"
    )
    print("-" * 88)
    for row in metrics:
        print(
            f"{row.timestamp:7d}  {row.incoming_rps:8.1f}  "
            f"{row.available_capacity_rps:8.1f}  {row.cpu_percent:5.1f}  "
            f"{row.ready_instances:5d}  {row.pending_instances:7d}  "
            f"{row.rejected_rps:8.1f}  {row.average_latency_ms:11.1f}  "
            f"{row.estimated_hourly_cost:9.2f}"
        )


def write_report(group: AutoScalingGroup, output_path: str = "autoscaling_report.json") -> None:
    report = {
        "generated_at_epoch": int(time.time()),
        "policy": asdict(group.policy),
        "instance_type": asdict(group.instance_type),
        "events": [asdict(event) for event in group.events],
        "metrics": [asdict(row) for row in group.history],
        "estimated_total_instance_hours": (
            sum(row.estimated_hourly_cost for row in group.history) / 120.0
        ),
    }
    Path(output_path).write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )


def run_self_tests() -> None:
    small = InstanceType("small", 2, 4, 0.08)
    policy = ScalingPolicy(
        name="test-policy",
        minimum_instances=2,
        maximum_instances=5,
        instance_warmup_seconds=30,
        cooldown_seconds=0,
        evaluation_periods=2,
    )
    group = AutoScalingGroup(small, policy)

    assert len(group.ready_instances) == 2
    assert group.available_capacity_rps == 480.0

    metric = group.observe(600.0)
    assert metric.rejected_rps == 120.0
    assert metric.cpu_percent == 100.0

    group.scale_out(1, "test capacity expansion")
    assert group.desired_instances == 3
    assert len(group.pending_instances) == 1

    group.advance_time(30)
    assert len(group.ready_instances) == 3

    group.scale_in(10, "test minimum protection")
    assert group.desired_instances == policy.minimum_instances

    try:
        group.observe(-1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("Negative traffic must be rejected.")

    print("Self-tests passed.")


def main() -> None:
    run_self_tests()

    small = InstanceType(
        name="general-small",
        cpu_cores=2,
        memory_gb=4.0,
        hourly_cost=0.08,
    )
    large = InstanceType(
        name="general-large",
        cpu_cores=8,
        memory_gb=16.0,
        hourly_cost=0.30,
    )

    print("\nHorizontal scaling")
    policy = ScalingPolicy(
        name="web-tier-target-tracking",
        target_cpu_percent=60.0,
        scale_out_threshold=75.0,
        scale_in_threshold=25.0,
        scale_out_step=2,
        scale_in_step=1,
        cooldown_seconds=60,
        evaluation_periods=2,
        minimum_instances=2,
        maximum_instances=10,
        instance_warmup_seconds=60,
        maximum_scale_change=3,
    )
    group = AutoScalingGroup(small, policy, desired_instances=2)
    metrics = simulate_traffic(group, traffic_profile(), interval_seconds=30)
    print_metrics_table(metrics)

    print("\nScaling events")
    for event in group.events:
        print(
            f"t={event.timestamp:4d}s {event.direction:9s} "
            f"{event.previous_desired} -> {event.new_desired}: {event.reason}"
        )

    print("\nVertical scaling comparison")
    demand = 900.0
    small_capacity = VerticalCapacity(small)
    large_capacity = VerticalCapacity(large)
    small_count = small_capacity.evaluate_replacement(demand)
    large_count = large_capacity.evaluate_replacement(demand)
    print(
        f"At {demand:.0f} requests/s and 60% target utilization, "
        f"small instances required: {small_count}; "
        f"large instances required: {large_count}."
    )
    print(
        f"Small fleet hourly cost: ${small_count * small.hourly_cost:.2f}; "
        f"large fleet hourly cost: ${large_count * large.hourly_cost:.2f}."
    )

    print("\nFailure and recovery")
    if group.ready_instances:
        failed = group.ready_instances[0]
        group.set_instance_health(failed.instance_id, False)
        print(f"Marked {failed.instance_id} unhealthy.")
        failure_metric = group.observe(500.0)
        print(
            f"Capacity after failure: {failure_metric.available_capacity_rps:.0f} "
            f"requests/s; rejected: {failure_metric.rejected_rps:.0f}."
        )
        group.scale_out(1, "replace failed capacity")
        group.advance_time(policy.instance_warmup_seconds)
        print(
            f"Healthy ready instances after recovery: {len(group.ready_instances)}."
        )

    write_report(group)
    print("\nReport written to autoscaling_report.json.")


if __name__ == "__main__":
    main()
