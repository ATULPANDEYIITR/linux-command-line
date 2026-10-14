from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


class EventType(str, Enum):
    HTTP_REQUEST = "http_request"
    FILE_UPLOADED = "file_uploaded"
    ORDER_CREATED = "order_created"
    TIMER = "timer"


@dataclass
class Event:
    event_type: EventType
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class FunctionMetrics:
    invocations: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0

    @property
    def average_duration_ms(self) -> float:
        if self.invocations == 0:
            return 0.0
        return self.total_duration_ms / self.invocations


class FunctionTimeout(Exception):
    pass


class FunctionExecutionError(Exception):
    pass


class ServerlessFunction:
    """
    A local model of a serverless function.

    A real provider creates an isolated execution environment, invokes the
    function, records metrics, and may retain the environment for reuse.
    This class models the application-level portion of that lifecycle.
    """

    def __init__(
        self,
        name: str,
        handler: Callable[[Event], Awaitable[Dict[str, Any]]],
        timeout_seconds: float = 3.0,
        memory_mb: int = 256,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if memory_mb <= 0:
            raise ValueError("memory_mb must be positive")

        self.name = name
        self.handler = handler
        self.timeout_seconds = timeout_seconds
        self.memory_mb = memory_mb
        self.metrics = FunctionMetrics()
        self._warm = False

    async def invoke(self, event: Event) -> Dict[str, Any]:
        started = time.perf_counter()
        self.metrics.invocations += 1

        try:
            if not self._warm:
                # Cold starts add initialization work before the handler runs.
                await asyncio.sleep(0.03)
                self._warm = True

            result = await asyncio.wait_for(
                self.handler(event),
                timeout=self.timeout_seconds,
            )
            return {
                "function": self.name,
                "event_id": event.event_id,
                "result": result,
                "cold_start": self.metrics.invocations == 1,
            }

        except asyncio.TimeoutError as exc:
            self.metrics.failures += 1
            raise FunctionTimeout(
                f"{self.name} exceeded {self.timeout_seconds}s timeout"
            ) from exc
        except Exception as exc:
            self.metrics.failures += 1
            raise FunctionExecutionError(
                f"{self.name} failed: {exc}"
            ) from exc
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            self.metrics.total_duration_ms += duration_ms


class EventBus:
    """
    Minimal event-driven dispatcher.

    Event producers publish events without knowing which functions consume
    them. This loose coupling is a central serverless architecture pattern.
    """

    def __init__(self) -> None:
        self.subscriptions: Dict[
            EventType, List[ServerlessFunction]
        ] = {}

    def subscribe(
        self,
        event_type: EventType,
        function: ServerlessFunction,
    ) -> None:
        self.subscriptions.setdefault(event_type, []).append(function)

    async def publish(self, event: Event) -> List[Dict[str, Any]]:
        functions = self.subscriptions.get(event.event_type, [])
        if not functions:
            logging.warning("No consumers for %s", event.event_type.value)
            return []

        tasks = [
            asyncio.create_task(function.invoke(event))
            for function in functions
        ]

        results: List[Dict[str, Any]] = []
        for task in asyncio.as_completed(tasks):
            try:
                results.append(await task)
            except FunctionExecutionError as exc:
                logging.error("%s", exc)
            except FunctionTimeout as exc:
                logging.error("%s", exc)

        return results


class AutoScaler:
    """
    Simple concurrency-based scaling simulation.

    Real serverless platforms hide infrastructure management and scale
    execution environments according to incoming workload. This model makes
    the decision visible for learning purposes.
    """

    def __init__(
        self,
        minimum_instances: int = 0,
        maximum_instances: int = 10,
        target_concurrency: int = 2,
    ) -> None:
        if not 0 <= minimum_instances <= maximum_instances:
            raise ValueError("Invalid instance range")
        if target_concurrency <= 0:
            raise ValueError("target_concurrency must be positive")

        self.minimum_instances = minimum_instances
        self.maximum_instances = maximum_instances
        self.target_concurrency = target_concurrency

    def desired_instances(self, queued_events: int) -> int:
        if queued_events <= 0:
            return self.minimum_instances

        desired = (
            queued_events + self.target_concurrency - 1
        ) // self.target_concurrency

        return min(
            self.maximum_instances,
            max(self.minimum_instances, desired),
        )


class RetryPolicy:
    def __init__(
        self,
        attempts: int = 3,
        base_delay_seconds: float = 0.05,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.attempts = attempts
        self.base_delay_seconds = base_delay_seconds

    async def execute(
        self,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        last_error: Optional[Exception] = None

        for attempt in range(self.attempts):
            try:
                return await operation()
            except Exception as exc:
                last_error = exc

                if attempt == self.attempts - 1:
                    break

                # Exponential backoff avoids immediately hammering a failing
                # downstream service.
                delay = self.base_delay_seconds * (2**attempt)
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error


class IdempotencyStore:
    """
    Stores processed event IDs.

    Event-driven systems can deliver a message more than once. Idempotency
    makes repeated delivery safe when the operation should happen once.
    """

    def __init__(self) -> None:
        self._processed: Dict[str, Any] = {}

    def contains(self, event_id: str) -> bool:
        return event_id in self._processed

    def get(self, event_id: str) -> Any:
        return self._processed[event_id]

    def save(self, event_id: str, result: Any) -> None:
        self._processed[event_id] = result


async def validate_http_request(event: Event) -> Dict[str, Any]:
    payload = event.payload

    method = payload.get("method")
    path = payload.get("path")

    if method not in {"GET", "POST", "PUT", "DELETE"}:
        raise ValueError("Unsupported HTTP method")

    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Invalid HTTP path")

    return {
        "status": 200,
        "message": "Request accepted by serverless function",
        "method": method,
        "path": path,
    }


async def process_uploaded_file(event: Event) -> Dict[str, Any]:
    payload = event.payload
    filename = payload.get("filename")
    size_bytes = payload.get("size_bytes", 0)

    if not filename:
        raise ValueError("filename is required")

    if size_bytes < 0:
        raise ValueError("size_bytes cannot be negative")

    # The event contains metadata rather than the entire file. Production
    # systems commonly store the object in object storage and pass a reference.
    return {
        "filename": filename,
        "size_bytes": size_bytes,
        "classification": (
            "large-file" if size_bytes > 10_000_000 else "normal-file"
        ),
    }


async def create_order(event: Event) -> Dict[str, Any]:
    payload = event.payload
    amount = payload.get("amount")
    customer_id = payload.get("customer_id")

    if not customer_id:
        raise ValueError("customer_id is required")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("amount must be positive")

    await asyncio.sleep(0.01)

    return {
        "order_id": f"ord-{uuid.uuid4().hex[:10]}",
        "customer_id": customer_id,
        "amount": round(float(amount), 2),
        "status": "accepted",
    }


async def flaky_inventory_check(event: Event) -> Dict[str, Any]:
    # The randomness simulates a transient downstream failure.
    if random.random() < 0.35:
        raise ConnectionError("Inventory service temporarily unavailable")

    return {
        "sku": event.payload.get("sku", "UNKNOWN"),
        "available": True,
    }


async def demonstrate_basic_functions() -> None:
    print("\n=== Basic Function Invocation ===")

    function = ServerlessFunction(
        name="http-validator",
        handler=validate_http_request,
    )

    event = Event(
        event_type=EventType.HTTP_REQUEST,
        payload={
            "method": "GET",
            "path": "/api/orders",
        },
    )

    result = await function.invoke(event)
    print(json.dumps(result, indent=2))


async def demonstrate_event_driven_architecture() -> None:
    print("\n=== Event-Driven Architecture ===")

    bus = EventBus()

    order_function = ServerlessFunction(
        name="order-processor",
        handler=create_order,
    )

    inventory_function = ServerlessFunction(
        name="inventory-check",
        handler=flaky_inventory_check,
    )

    bus.subscribe(EventType.ORDER_CREATED, order_function)
    bus.subscribe(EventType.ORDER_CREATED, inventory_function)

    event = Event(
        event_type=EventType.ORDER_CREATED,
        payload={
            "customer_id": "customer-42",
            "amount": 1499.50,
            "sku": "LAPTOP-001",
        },
    )

    retry_policy = RetryPolicy(attempts=4)

    async def process_inventory() -> Dict[str, Any]:
        return await inventory_function.invoke(event)

    results = await bus.publish(event)

    try:
        inventory_result = await retry_policy.execute(process_inventory)
        results.append(inventory_result)
    except Exception as exc:
        logging.error("Inventory remained unavailable: %s", exc)

    for result in results:
        print(json.dumps(result, indent=2))


async def demonstrate_idempotency() -> None:
    print("\n=== Idempotent Event Processing ===")

    store = IdempotencyStore()
    function = ServerlessFunction(
        name="file-processor",
        handler=process_uploaded_file,
    )

    event = Event(
        event_type=EventType.FILE_UPLOADED,
        payload={
            "filename": "inspection-report.pdf",
            "size_bytes": 1_500_000,
        },
    )

    async def process_once() -> Any:
        if store.contains(event.event_id):
            return {
                "status": "duplicate",
                "cached_result": store.get(event.event_id),
            }

        result = await function.invoke(event)
        store.save(event.event_id, result)
        return result

    first = await process_once()
    second = await process_once()

    print("First delivery:")
    print(json.dumps(first, indent=2))
    print("Repeated delivery:")
    print(json.dumps(second, indent=2))


def demonstrate_scaling() -> None:
    print("\n=== Scaling Model ===")

    scaler = AutoScaler(
        minimum_instances=0,
        maximum_instances=8,
        target_concurrency=4,
    )

    for queued_events in [0, 1, 4, 5, 12, 25, 100]:
        instances = scaler.desired_instances(queued_events)
        print(
            f"queued_events={queued_events:3d} "
            f"desired_instances={instances}"
        )


async def demonstrate_failure_and_timeout() -> None:
    print("\n=== Failure and Timeout Handling ===")

    async def slow_handler(event: Event) -> Dict[str, Any]:
        await asyncio.sleep(0.2)
        return {"status": "completed"}

    slow_function = ServerlessFunction(
        name="short-timeout-function",
        handler=slow_handler,
        timeout_seconds=0.05,
    )

    event = Event(
        event_type=EventType.TIMER,
        payload={"source": "scheduler"},
    )

    try:
        await slow_function.invoke(event)
    except FunctionTimeout as exc:
        print(f"Handled timeout: {exc}")


def demonstrate_cost_model() -> None:
    print("\n=== Approximate Serverless Cost Model ===")

    invocations = 2_000_000
    request_price_per_million = 0.20
    compute_gb_seconds = 12_500
    compute_price_per_gb_second = 0.0000166667

    request_cost = (
        invocations / 1_000_000
    ) * request_price_per_million

    compute_cost = (
        compute_gb_seconds * compute_price_per_gb_second
    )

    total = request_cost + compute_cost

    print(f"Invocations: {invocations:,}")
    print(f"Request cost model: ${request_cost:.4f}")
    print(f"Compute cost model: ${compute_cost:.4f}")
    print(f"Approximate total: ${total:.4f}")

    # This is intentionally a generic educational model. Actual provider
    # pricing varies by platform, region, architecture, memory, duration,
    # networking, and other services.


def write_observability_snapshot(
    functions: List[ServerlessFunction],
    output_path: str = "serverless_metrics.json",
) -> None:
    snapshot = {}

    for function in functions:
        snapshot[function.name] = {
            "invocations": function.metrics.invocations,
            "failures": function.metrics.failures,
            "average_duration_ms": round(
                function.metrics.average_duration_ms,
                3,
            ),
            "memory_mb": function.memory_mb,
            "timeout_seconds": function.timeout_seconds,
        }

    Path(output_path).write_text(
        json.dumps(snapshot, indent=2),
        encoding="utf-8",
    )

    print(f"\nMetrics written to {output_path}")


async def main() -> None:
    random.seed(7)

    await demonstrate_basic_functions()
    await demonstrate_event_driven_architecture()
    await demonstrate_idempotency()
    demonstrate_scaling()
    await demonstrate_failure_and_timeout()
    demonstrate_cost_model()

    metric_function = ServerlessFunction(
        name="metrics-demo",
        handler=validate_http_request,
    )

    await metric_function.invoke(
        Event(
            event_type=EventType.HTTP_REQUEST,
            payload={"method": "GET", "path": "/health"},
        )
    )

    write_observability_snapshot([metric_function])


if __name__ == "__main__":
    asyncio.run(main())
