# Storage Performance

## Scope

Storage performance is the study of how quickly a storage system can accept, process, and complete I/O requests. The important dimensions are not interchangeable.

**IOPS** measures completed I/O operations per second. It is especially important for small random requests such as database pages, metadata operations, and transactional workloads.

**Throughput** measures the amount of data transferred per second, normally expressed as MB/s or MiB/s. It becomes especially important when requests are large and sequential, such as analytics scans, backups, media processing, and bulk data movement.

**Latency** measures the time required for an individual operation to complete. Average latency is useful, but P95 and P99 latency are often more representative of user-facing performance because storage systems can experience occasional queueing and service-time spikes.

**Caching** attempts to serve frequently reused data from a faster memory layer rather than repeatedly accessing the underlying storage device.

**Storage tiers** place workloads or data on different media according to latency, IOPS, throughput, capacity, durability, access frequency, and cost requirements.

The relationship among these mechanisms is central to performance engineering:

`request size × IOPS ≈ throughput`

This is an approximation rather than a universal device guarantee. A real system can be limited by controller capacity, protocol overhead, filesystem behavior, queueing, CPU consumption, cache behavior, or device saturation before a theoretical limit is reached.

## Core Performance Model

### IOPS

IOPS represents request rate rather than data rate.

A device completing 100,000 4 KiB operations per second transfers approximately:

`100,000 × 4 KiB ≈ 390.6 MiB/s`

The same 100,000 IOPS with 1 MiB requests would imply a much larger data rate and could exceed the device's bandwidth capability.

The Python implementation calculates IOPS directly from operation count and elapsed time. The JavaScript implementation exposes the relationship through `bandwidthLimitedIOPS()`, while the C++ and SQL implementations use the same relationship when evaluating whether a tier can satisfy a workload.

IOPS should therefore be interpreted together with request size and access pattern.

### Throughput

Throughput is a measure of sustained data transfer.

Large sequential operations can achieve high throughput while generating relatively few I/O operations. A storage system that is excellent at sequential throughput may still perform poorly for highly random small-block workloads.

The implementations distinguish these workload shapes rather than treating peak bandwidth as a universal storage-performance measure.

The C++ case study explicitly classifies a warehouse scan as sequential and an OLTP database as random. This distinction affects which performance constraint matters most.

### Latency

Latency is the time between submitting an operation and completing it.

The examples model latency as a combination of a base service time and a component influenced by I/O size and device bandwidth. The simplified model is intentionally not presented as a physical-device benchmark. Real hardware contains additional effects such as controller scheduling, firmware behavior, protocol queues, filesystem overhead, cache state, garbage collection, thermal conditions, and contention.

Latency must be evaluated at the tail as well as at the average.

A workload with a 0.5 ms average latency and occasional 50 ms operations can behave very differently from a workload whose latency remains close to 0.5 ms.

The Python program calculates P50, P95, and P99 latency. The SQL model also stores P95 and P99 benchmark measurements and enforces that P95 cannot be lower than the average and P99 cannot be lower than P95.

## Queue Depth and Saturation

Queue depth describes how many I/O requests can be outstanding.

A queue depth of one exposes little device parallelism. Increasing queue depth can allow a storage device to keep internal resources busy and can increase observed IOPS.

The relationship is not unlimited.

Once the storage system reaches a bottleneck, additional outstanding requests generally produce more queueing rather than proportionally higher useful work. Tail latency can therefore increase while throughput approaches a plateau.

The JavaScript implementation models this behavior with asynchronous workers. `runConcurrentWorkload()` maintains a configurable number of outstanding requests, making queue depth an explicit part of the experiment.

The C++ policy model treats sustainable IOPS as a capacity boundary. The SQL schema stores queue depth with benchmark observations so that measurements can be compared under different concurrency conditions.

## Caching

Caching changes the path through which data is served.

A cache hit avoids an access to the slower storage layer. A cache miss must retrieve the object or block from the underlying tier and may then place the result into the cache.

The Python implementation contains a byte-aware LRU cache. It tracks the total memory occupied by cached values and evicts the least recently used entries when capacity is exhausted.

The JavaScript implementation uses JavaScript's `Map` insertion order to implement an LRU structure. This demonstrates a language-specific approach to maintaining recency without introducing an external package.

The Java program models an enterprise cache policy separately from storage-tier selection. This separation is important because caching is not itself a replacement for appropriate persistent storage.

Caching is most effective when the workload has locality. A frequently reused working set can produce a high hit rate. A uniformly random workload over a much larger address space can produce a poor hit rate even when the cache is large in absolute terms.

Caching also introduces design concerns:

- A high hit rate does not automatically mean that the system has adequate durability or persistence.
- Cached data can become stale when the underlying data changes.
- Write-back caching can improve write performance but requires careful durability and recovery handling.
- Write-through caching provides a simpler durability relationship but can increase write latency.
- An oversized cache can consume memory needed by the application itself.
- Cache invalidation and eviction policy directly influence effective performance.

The SQL model stores cache capacity, eviction policy, write policy, and minimum acceptable hit rate so these decisions can be evaluated independently of storage tier selection.

## Storage Tiers

The implementations use four conceptual tiers:

| Tier | Performance characteristic | Appropriate workload pattern |
|---|---|---|
| NVMe | Very high IOPS, high bandwidth, low latency | Latency-sensitive databases and demanding random I/O |
| SSD | Strong general-purpose random and sequential performance | Enterprise application storage and mixed workloads |
| HDD | Lower IOPS with economical capacity | Bulk sequential workloads and less latency-sensitive data |
| Archive | Very low interactive performance with low storage cost | Long-term, infrequently accessed data |

These are modeled values for educational experimentation, not specifications for a particular commercial device.

Tier selection should not simply select the fastest medium. The appropriate decision depends on whether the workload is IOPS-bound, bandwidth-bound, latency-sensitive, capacity-heavy, or cost-sensitive.

## Python Implementation

The Python program builds a complete storage-performance simulation around `StorageProfile`, `StorageTier`, `OperationRecord`, and `PerformanceMetrics`.

`calculate_iops()` and `calculate_throughput()` establish the fundamental metrics. `bandwidth_limited_iops()` demonstrates why request size changes the relationship between IOPS and throughput.

`SimulatedStorage` models a storage tier and generates latency from its configured characteristics. Reads and writes become `OperationRecord` instances that can be aggregated into percentile and cache statistics.

The Python `LRUCache` is byte-aware rather than merely entry-count based. This matters because a cache containing ten 4 KiB blocks consumes very different memory from one containing ten 1 MiB objects.

The workload generators distinguish random access from hot-set access. The hot-set experiment demonstrates temporal locality and shows how a cache can change effective latency and backend request volume.

`StorageTierManager` provides a simple policy layer that considers access frequency and object age. Frequently accessed data is assigned to faster tiers, while older and less frequently accessed data can move toward economical capacity tiers.

Validation functions reject negative offsets, zero-sized I/O, and requests extending beyond storage capacity. This reflects an important performance-engineering principle: invalid workload definitions should be detected before benchmark results are interpreted.

## JavaScript Implementation

The JavaScript program focuses on asynchronous storage behavior.

`StorageDevice` extends `EventTarget`, allowing completion events to be emitted when asynchronous operations finish. This models the event-driven nature of Node.js rather than translating the Python simulation directly.

`setTimeout()` represents asynchronous completion. It is not intended to be a physical storage simulator. Its purpose is to demonstrate that an application can keep its event loop available while I/O work is pending.

`runConcurrentWorkload()` creates a configurable worker pool. The worker count represents queue depth and provides a concrete way to examine the effect of concurrency.

`PerformanceCollector` records operations and computes throughput, observed IOPS, average latency, P95, P99, and cache hit rate.

The JavaScript LRU cache uses `Map` insertion order. This is a useful JavaScript-specific implementation because `Map` preserves insertion order, allowing recently accessed keys to be moved to the end.

The program also evaluates storage tiers against a workload containing request size, request rate, and latency target. This separates workload requirements from device capabilities.

## C++ Case Study

The C++ program models a storage-performance planning engine for an enterprise data platform.

`TierProfile` describes the performance and cost characteristics of each storage tier. `StorageRequest` represents workload requirements rather than device properties.

`evaluateRequest()` calculates the bandwidth-limited IOPS for a requested I/O size and combines it with the tier's maximum IOPS. The lower of those limits becomes the modeled sustainable IOPS.

This distinction matters because a device may advertise a very high IOPS value while large requests become bandwidth-limited.

`WorkloadPlanner` stores workloads in an ordered map and selects the least expensive tier that satisfies the declared IOPS and latency requirements. This creates a realistic policy decision instead of simply choosing the fastest device.

The case study covers:

- An OLTP database using small random reads.
- A warehouse scan using large sequential reads.
- A nightly backup using large sequential writes.
- A compliance archive where cost and capacity dominate interactive performance.

The cache experiment uses an LRU structure and a deliberately small hot set. Comparing a cache capable of storing 32 blocks with one capable of storing the complete 256-block working set demonstrates how working-set size affects cache hit rate.

The C++ implementation also measures CPU work with `std::chrono`. This is intentionally separate from storage timing because benchmark programs can accidentally measure their own processing overhead rather than the storage subsystem.

## Java Enterprise Model

The Java program uses explicit domain types to represent an enterprise storage-performance policy.

`StorageTier` and `AccessPattern` are enums because the permitted states are known and should not be represented as arbitrary strings.

`TierProfile` is an immutable record containing device capabilities. `Workload` is another immutable record containing application requirements.

`PerformancePolicy` owns the evaluation rules. It calculates sustainable IOPS from both device IOPS capacity and bandwidth. It then evaluates whether the workload's IOPS and latency requirements can be satisfied.

The policy selects the least expensive acceptable tier. This represents a practical enterprise requirement: performance must meet a service objective without automatically selecting the most expensive storage.

`StorageService` separates cache behavior from policy evaluation. The `CachePolicy` uses an access-ordered `LinkedHashMap` to implement LRU behavior.

The Java design therefore separates:

`Workload requirements → Tier capability evaluation → Policy decision → Cache behavior`

This separation makes policy changes easier to reason about than embedding all rules inside application-level conditionals.

Validation is implemented through constructor checks and exceptions. Invalid request sizes, negative capacity values, missing workload names, and invalid performance targets are rejected at the domain boundary.

## SQL Data Model

The PostgreSQL implementation treats storage performance as relational operational data.

`storage_tier_profile` stores capabilities and costs for each tier.

`storage_workload` stores application requirements such as request size, request rate, latency target, capacity, operation type, and access pattern.

`benchmark_run` records observed performance. It contains measured IOPS, measured throughput, average latency, P95 latency, P99 latency, queue depth, and cache hit rate.

`cache_policy` stores cache capacity and explicit eviction and write policies.

`tier_recommendation` stores the result of comparing a workload with each available tier.

The foreign keys ensure that workload and tier references cannot point to nonexistent entities. `CHECK` constraints prevent invalid values such as zero-sized requests, negative latency, negative capacity, or cache hit rates outside the range from zero to one.

Indexes are applied to workload access patterns, requested IOPS, and benchmark lookup paths because these are natural filtering dimensions for performance analysis.

The `estimate_sustainable_iops()` function applies the relationship between throughput and request size at the database layer.

The `workload_tier_analysis` view exposes the resulting policy data in a query-friendly form. A common table expression with `row_number()` identifies the cheapest acceptable tier for each workload.

The benchmark queries demonstrate an important distinction between modeled capacity and measured behavior. A device can satisfy a theoretical requirement while an actual benchmark reveals higher tail latency or lower effective IOPS.

## Performance Bottlenecks

Storage performance problems should be classified by the limiting resource rather than by a generic statement that storage is slow.

An **IOPS-bound** workload reaches the maximum useful request rate before exhausting available bandwidth. Small random database operations commonly behave this way.

A **bandwidth-bound** workload reaches the device's data-transfer limit. Large sequential reads and writes are common examples.

A **latency-bound** workload has a strict response-time requirement that the selected tier cannot satisfy even when its aggregate throughput is adequate.

A **cache-bound** workload is sensitive to working-set locality and cache capacity. Poor cache locality can cause repeated backend requests.

A **queueing-bound** workload has enough outstanding requests to saturate the device, making additional concurrency primarily increase waiting time.

The SQL script produces a bottleneck classification based on these relationships.

## Benchmarking Considerations

A useful storage benchmark must control the variables that affect the result.

Request size changes the IOPS-to-throughput relationship. Sequential and random access produce different device behavior. Read/write ratio changes controller and media workload. Queue depth changes concurrency and can alter both throughput and tail latency.

Cache state must also be controlled. A warm-cache benchmark can report dramatically better results than a cold-cache benchmark without any change to the persistent storage device.

The benchmark must record percentiles instead of only an average. P99 latency is particularly useful when storage operations participate in user-facing requests or distributed transactions.

Benchmark results should also distinguish theoretical device specifications from measured application performance. Filesystem overhead, protocol overhead, CPU work, application scheduling, and contention can all affect observed values.

## Performance Optimization

Optimization should begin by identifying the actual bottleneck.

For an IOPS-bound workload, reducing unnecessary small operations, improving locality, batching where semantics permit, or moving the workload to higher-IOPS storage can help.

For a bandwidth-bound workload, larger sequential requests, reduced unnecessary copying, and a tier with sufficient sustained throughput are more relevant.

For latency-sensitive workloads, reducing queueing and selecting low-latency media can be more valuable than increasing peak bandwidth.

For cache-sensitive workloads, the working-set size and access distribution should be measured before increasing cache capacity. A larger cache is useful only when it captures reusable data.

Queue depth should be increased only until useful device parallelism is exposed. Beyond saturation, excessive concurrency can produce higher tail latency without proportional throughput gains.

Tiering can reduce cost by keeping frequently accessed data on fast storage and moving cold data to economical capacity tiers.

## Edge Cases and Failure Conditions

A storage-performance model must reject invalid workload definitions.

Zero-sized I/O has no meaningful performance interpretation.

Negative offsets are invalid for ordinary storage addressing.

Requests that extend beyond a defined capacity must be rejected.

A latency percentile cannot be calculated from an empty sample.

A cache object larger than the cache capacity cannot be retained by a byte-capacity LRU implementation.

A workload that exceeds every tier's sustainable IOPS or latency target has no valid tier assignment. The correct response is to expose the policy conflict rather than silently selecting a tier that violates the requirement.

A cache hit rate near 100% does not prove that the underlying storage tier is appropriate because the workload may be relying almost entirely on volatile memory.

## Common Performance Mistakes

Peak throughput should not be treated as equivalent to random IOPS performance.

Average latency should not be treated as a substitute for P95 or P99 latency.

Increasing queue depth should not be assumed to increase performance indefinitely.

A cache hit should not be treated as evidence that persistent storage has become faster.

A benchmark should not compare different request sizes and describe the results as though they represent the same workload.

Cold-cache and warm-cache results should not be mixed without identifying the cache state.

Storage tier selection should not be based only on price per GiB or only on peak performance.

A theoretical specification should not be presented as an application-level performance guarantee.

## Production Considerations

Production storage monitoring should correlate IOPS, throughput, latency percentiles, queue depth, cache hit rate, capacity utilization, and workload type.

Capacity monitoring is important because a storage system can remain fast while approaching a capacity threshold that changes operational risk or future expansion cost.

Performance monitoring should preserve enough workload context to distinguish a sudden increase in I/O demand from a device-level regression.

For latency-sensitive applications, P95, P99, and sometimes P99.9 are more useful than averages when determining whether storage meets service objectives.

Tiering policies should also account for data lifecycle and operational requirements. Moving data to a slower tier may reduce cost while creating unacceptable recovery or access delays if the lifecycle policy is poorly designed.

The central engineering relationship is therefore not simply "faster storage is better." A useful design connects workload behavior, I/O size, IOPS, throughput, latency, cache locality, queue depth, storage tier, capacity, and cost into one measurable performance model.
