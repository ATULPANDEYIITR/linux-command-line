from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from random import Random
from typing import Dict, List, Optional


class InstanceState(Enum):
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"
    TERMINATED = "terminated"


class ScalingAction(Enum):
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    HOLD = "hold"


@dataclass
class Instance:
    instance_id: str
    capacity_rps: int
    state: InstanceState = InstanceState.STARTING
    active_requests: int = 0
    consecutive_failures: int = 0

    def available_capacity(self) -> int:
        if self.state != InstanceState.HEALTHY:
            return 0
        return max(0, self.capacity_rps - self.active_requests)


@dataclass(frozen=True)
class ScalingPolicy:
    target_utilization: float = 0.65
    scale_out_threshold: float = 0.75
    scale_in_threshold: float = 0.30
    min_instances: int = 2
    max_instances: int = 8
    cooldown_ticks: int = 2


@dataclass
class LoadBalancer:
    name: str
    request_timeout_ms: int = 500
    health_check_interval: int = 1
    _cursor: int = 0

    def healthy_instances(self, instances: List[Instance]) -> List[Instance]:
        return [i for i in instances if i.state == InstanceState.HEALTHY]

    def distribute(self, requests: int, instances: List[Instance]) -> Dict[str, int]:
        healthy = self.healthy_instances(instances)
        allocation = {i.instance_id: 0 for i in instances}

        if not healthy:
            raise RuntimeError("No healthy compute instances are available")

        remaining = requests
        start = self._cursor % len(healthy)

        while remaining > 0:
            made_progress = False
            for offset in range(len(healthy)):
                instance = healthy[(start + offset) % len(healthy)]
                capacity = instance.available_capacity()
                if capacity <= 0:
                    continue

                assigned = min(capacity, remaining)
                allocation[instance.instance_id] += assigned
                instance.active_requests += assigned
                remaining -= assigned
                made_progress = True

                if remaining == 0:
                    break

            if not made_progress:
                break

        self._cursor = (start + 1) % len(healthy)
        return allocation


@dataclass
class AutoScaler:
    policy: ScalingPolicy
    cooldown_remaining: int = 0

    def evaluate(self, request_rate: int, total_capacity: int) -> ScalingAction:
        if total_capacity <= 0:
            return ScalingAction.SCALE_OUT

        utilization = request_rate / total_capacity

        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return ScalingAction.HOLD

        if utilization > self.policy.scale_out_threshold:
            return ScalingAction.SCALE_OUT

        if utilization < self.policy.scale_in_threshold:
            return ScalingAction.SCALE_IN

        return ScalingAction.HOLD

    def apply_cooldown(self) -> None:
        self.cooldown_remaining = self.policy.cooldown_ticks


@dataclass
class CloudScalingArchitecture:
    scaling_policy: ScalingPolicy
    random: Random = field(default_factory=lambda: Random(42))
    instances: List[Instance] = field(default_factory=list)
    load_balancer: LoadBalancer = field(
        default_factory=lambda: LoadBalancer("public-alb")
    )
    autoscaler: AutoScaler = field(init=False)
    next_instance_number: int = 1

    def __post_init__(self) -> None:
        self.autoscaler = AutoScaler(self.scaling_policy)
        self._validate_policy()
        self.scale_to(self.scaling_policy.min_instances)

    def _validate_policy(self) -> None:
        p = self.scaling_policy
        if not 0 < p.scale_in_threshold < p.scale_out_threshold:
            raise ValueError("Scaling thresholds must be ordered and positive")
        if p.min_instances < 1:
            raise ValueError("At least one instance is required")
        if p.max_instances < p.min_instances:
            raise ValueError("Maximum instances cannot be below minimum instances")
        if not 0 < p.target_utilization <= 1:
            raise ValueError("Target utilization must be between 0 and 1")

    def _new_instance(self) -> Instance:
        instance = Instance(
            instance_id=f"compute-{self.next_instance_number:02d}",
            capacity_rps=self.random.randint(90, 120),
        )
        self.next_instance_number += 1
        return instance

    def launch_pending_instances(self) -> None:
        for instance in self.instances:
            if instance.state == InstanceState.STARTING:
                instance.state = InstanceState.HEALTHY

    def scale_to(self, desired: int) -> None:
        desired = max(
            self.scaling_policy.min_instances,
            min(self.scaling_policy.max_instances, desired),
        )

        active = [
            i for i in self.instances
            if i.state != InstanceState.TERMINATED
        ]

        if len(active) < desired:
            for _ in range(desired - len(active)):
                self.instances.append(self._new_instance())
            self.launch_pending_instances()
            return

        if len(active) > desired:
            removable = [
                i for i in active
                if i.state == InstanceState.HEALTHY and i.active_requests == 0
            ]
            for instance in removable[: len(active) - desired]:
                instance.state = InstanceState.TERMINATED

    def current_instances(self) -> List[Instance]:
        return [i for i in self.instances if i.state != InstanceState.TERMINATED]

    def total_capacity(self) -> int:
        return sum(
            i.capacity_rps
            for i in self.current_instances()
            if i.state == InstanceState.HEALTHY
        )

    def healthy_capacity(self) -> int:
        return sum(
            i.capacity_rps
            for i in self.current_instances()
            if i.state == InstanceState.HEALTHY
        )

    def simulate_health_failure(self, instance_id: str) -> None:
        for instance in self.instances:
            if instance.instance_id == instance_id:
                instance.state = InstanceState.UNHEALTHY
                return
        raise KeyError(f"Unknown instance: {instance_id}")

    def recover_unhealthy_instances(self) -> None:
        for instance in self.instances:
            if instance.state == InstanceState.UNHEALTHY:
                instance.consecutive_failures = 0
                instance.state = InstanceState.HEALTHY

    def process_tick(self, request_rate: int) -> Dict[str, object]:
        if request_rate < 0:
            raise ValueError("Request rate cannot be negative")

        for instance in self.current_instances():
            instance.active_requests = 0

        capacity_before = self.healthy_capacity()
        action = self.autoscaler.evaluate(request_rate, capacity_before)

        if action == ScalingAction.SCALE_OUT:
            current = len(self.current_instances())
            self.scale_to(current + 1)
            self.autoscaler.apply_cooldown()
        elif action == ScalingAction.SCALE_IN:
            current = len(self.current_instances())
            self.scale_to(current - 1)
            self.autoscaler.apply_cooldown()

        allocation = self.load_balancer.distribute(
            request_rate, self.current_instances()
        )

        served = sum(allocation.values())
        rejected = request_rate - served

        # Requests are assumed short-lived for this simulation.
        for instance in self.current_instances():
            instance.active_requests = 0

        return {
            "request_rate": request_rate,
            "action": action.value,
            "instances": len(self.current_instances()),
            "healthy_instances": len(
                self.load_balancer.healthy_instances(self.current_instances())
            ),
            "capacity_rps": self.healthy_capacity(),
            "served": served,
            "rejected": rejected,
            "allocation": allocation,
        }


def run_simulation() -> None:
    architecture = CloudScalingArchitecture(
        ScalingPolicy(
            target_utilization=0.65,
            scale_out_threshold=0.75,
            scale_in_threshold=0.30,
            min_instances=2,
            max_instances=6,
            cooldown_ticks=2,
        )
    )

    traffic_pattern = [80, 130, 170, 230, 410, 520, 610, 280, 150, 70, 90]

    print("Cloud Scaling Architecture Simulation")
    print("=" * 72)

    for tick, request_rate in enumerate(traffic_pattern, start=1):
        if tick == 6:
            healthy = architecture.load_balancer.healthy_instances(
                architecture.current_instances()
            )
            if healthy:
                architecture.simulate_health_failure(healthy[0].instance_id)

        result = architecture.process_tick(request_rate)

        print(
            f"Tick {tick:02d} | "
            f"requests={result['request_rate']:3d} | "
            f"action={result['action']:9s} | "
            f"instances={result['instances']} | "
            f"healthy={result['healthy_instances']} | "
            f"capacity={result['capacity_rps']:3d} | "
            f"served={result['served']:3d} | "
            f"rejected={result['rejected']:3d}"
        )

        if tick == 7:
            architecture.recover_unhealthy_instances()

    print("\nFinal instance state:")
    for instance in architecture.current_instances():
        print(
            f"{instance.instance_id}: "
            f"capacity={instance.capacity_rps} rps, "
            f"state={instance.state.value}"
        )


def run_assertions() -> None:
    architecture = CloudScalingArchitecture(
        ScalingPolicy(min_instances=2, max_instances=4)
    )

    assert len(architecture.current_instances()) == 2
    assert architecture.healthy_capacity() > 0

    result = architecture.process_tick(10)
    assert result["served"] == 10
    assert result["rejected"] == 0

    try:
        architecture.process_tick(-1)
    except ValueError:
        pass
    else:
        raise AssertionError("Negative traffic should fail validation")

    architecture.simulate_health_failure("compute-01")
    assert (
        architecture.current_instances()[0].state == InstanceState.UNHEALTHY
    )


if __name__ == "__main__":
    run_assertions()
    run_simulation()
