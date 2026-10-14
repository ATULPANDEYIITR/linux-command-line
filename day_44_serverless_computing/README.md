# Serverless Computing: Functions, Events, Scaling, and Architecture

## Scope

Serverless computing is an execution model in which the application developer deploys code without directly managing the underlying server fleet. The platform is responsible for provisioning execution environments, starting runtimes, routing invocations, scaling capacity, and retiring unused execution environments.

The central abstraction is the function. A function is normally a small unit of application logic invoked by an HTTP request, an event, or a schedule. Serverless architecture extends that function model into a distributed system composed of independently deployable event consumers and managed services.

The six artifacts in this collection approach the subject from different technical perspectives:

- The Python program builds an executable simulation of function invocation, event routing, retries, idempotency, scaling, timeouts, metrics, and a simple cost model.
- The JavaScript program uses asynchronous JavaScript and event-driven execution to model HTTP functions, event fan-out, retries, idempotency, autoscaling, and observability.
- The C++ program focuses on a technical case study in which a serverless platform is combined with a repository-governance engine, showing how event processing, policy evaluation, scaling, and operational state can coexist.
- The Java program models serverless execution as an enterprise domain with explicit event types, asynchronous function execution, immutable event records, idempotency storage, and policy-driven state evaluation.
- The PostgreSQL script models functions, events, subscriptions, invocations, processed-event records, repositories, Pull Requests, reviews, status checks, and branch protection as relational data with integrity constraints and operational queries.
- The README connects these implementations to the architectural mechanisms that distinguish serverless systems from conventional long-running server applications.

## Serverless Execution Model

A conventional server application commonly owns a continuously running process. The process may listen on a port, maintain worker threads, hold connections, and remain available even when there is little traffic.

A serverless function changes the operational boundary. The developer supplies a function and configuration such as memory, timeout, runtime, and trigger. The platform determines when execution environments are created and how many concurrent environments are needed.

A simplified execution path is:

`event source -> platform routing -> function environment -> handler -> response or side effect`

For an HTTP invocation, the event may contain an HTTP method, path, headers, query parameters, and request body.

For an event trigger, the function may receive a record describing an object-storage upload, a queue message, an order, a database change, or another domain event.

For scheduled execution, the platform generates an invocation according to a schedule rather than waiting for an external HTTP request.

The application should not assume that one execution environment remains alive indefinitely. Runtime reuse can occur, but reuse is an optimization controlled by the platform rather than a durable application guarantee.

## Functions and Invocation Lifecycle

A useful conceptual lifecycle is:

`created -> initialized -> invoked -> completed -> reused or retired`

Initialization can involve loading application modules, establishing configuration, preparing connection pools, and constructing framework objects. The first request handled by a newly initialized environment can therefore have different latency from later requests.

The Python implementation models this distinction through the `warm` state in `ServerlessFunction`. The first invocation incurs an artificial initialization delay and reports a cold start.

The JavaScript implementation uses the same architectural distinction but represents execution with asynchronous Promises. The `ServerlessFunction` class records invocation count, failures, total duration, memory configuration, and timeout configuration.

The Java implementation uses an executor to represent asynchronous platform-managed execution. An `Event` is immutable through a Java record, while the function handler is represented by the `EventHandler` functional interface.

These implementations deliberately model the application-level behavior rather than attempting to reproduce a specific cloud provider's internal scheduler.

## HTTP-Triggered Functions

HTTP-triggered serverless functions behave like request handlers.

A request such as:

`GET /api/orders`

can be transformed into an event containing:

`method = GET`

and:

`path = /api/orders`

The handler validates the request and produces a response object.

The Python implementation uses `validate_http_request`. It rejects unsupported HTTP methods and malformed paths.

The JavaScript implementation performs equivalent validation while returning an object containing `statusCode`, method, path, and response data.

The Java implementation expresses the same domain through a typed `Event`, but its handler returns `Map<String, Object>` because the example is intended to remain dependency-free.

Important production concerns include authentication, authorization, request validation, payload limits, timeout configuration, observability, structured error responses, and protection against abusive traffic.

A serverless HTTP function does not eliminate these concerns. It changes who manages the execution infrastructure.

## Event-Driven Execution

Event-driven serverless architecture separates event producers from event consumers.

An order service can publish:

`order.created`

without directly calling every downstream operation.

Separate functions can subscribe to the event:

`order.created -> order processor`

`order.created -> inventory check`

`order.created -> notification`

This creates a fan-out architecture. The producer does not need to contain all downstream business logic.

The Python `EventBus` maintains subscriptions by `EventType` and invokes subscribed functions concurrently using `asyncio`.

The JavaScript `EventBus` stores subscribers in a `Map` and uses `Promise.allSettled()` so one failed consumer does not automatically hide the outcome of other consumers.

The Java `EventRouter` uses an `EnumMap<EventType, List<ServerlessFunction>>` and asynchronous `CompletableFuture` execution.

These differences are important. The three programs implement the same architectural idea with language-specific concurrency and data-structure choices rather than copying one source file into another language.

## Event Contracts

An event should have a stable contract.

The Python `Event` contains:

- an event identifier
- an event type
- a payload dictionary
- a creation timestamp

The JavaScript event uses a generated UUID and freezes the outer event object. The payload is cloned before being stored so accidental mutation of the original input does not alter the event object.

The Java record makes the Java event immutable at the record level and uses `Map.copyOf()` for the payload.

The SQL implementation stores event payloads in PostgreSQL `JSONB`. This allows structured event data while preserving relational metadata such as event type, source, status, and timestamps.

Event contracts become especially important when producers and consumers are deployed independently. A producer changing field names or semantics can break consumers even when both applications remain individually healthy.

## Statelessness

Serverless functions should generally treat each invocation as independent.

A function should not assume that:

- the same execution environment will receive the next request;
- local memory contains the previous request's state;
- a temporary file will exist during another invocation;
- an in-memory counter represents the complete global invocation count;
- an open network connection will remain usable indefinitely.

Durable state belongs in an external service such as a relational database, object store, cache, queue, or other managed persistence system.

The example idempotency stores demonstrate an important distinction. In-memory dictionaries and maps are useful for illustrating the mechanism, but they are not durable distributed state. A production implementation would normally use a shared durable store.

## Idempotency

Event delivery can be repeated.

A function may successfully process an event but fail before acknowledging completion. The event infrastructure may then deliver the same event again.

If the operation creates an order, charges an account, sends a notification, or modifies a database record, duplicate execution can produce incorrect results.

The Python `IdempotencyStore` maps an event ID to its first result.

The JavaScript `IdempotencyStore` uses a `Map` for the same application-level demonstration.

The PostgreSQL `processed_events` table uses:

`PRIMARY KEY (function_id, event_id)`

to enforce uniqueness at the database layer.

The SQL transaction uses `ON CONFLICT (function_id, event_id) DO NOTHING`, which makes duplicate processing observable without replacing the original result.

The important production principle is that idempotency should be enforced at a durable boundary when duplicate execution can cause externally visible effects.

## Retries and Failure Handling

Distributed systems experience transient failures.

A downstream service may be temporarily unavailable. A network connection can fail. A dependency may return a timeout. A platform invocation can fail before completion.

The Python `RetryPolicy` uses exponential backoff. Its delays increase after successive failures.

The JavaScript `RetryPolicy` applies the same strategy using asynchronous delays.

Retries must not be applied blindly. Retrying a non-idempotent operation can create duplicate side effects.

A safe retry design usually combines:

- an operation that is idempotent or protected by an idempotency key;
- a bounded retry count;
- exponential backoff;
- appropriate timeout values;
- failure classification;
- logging and metrics;
- a final failure path such as a dead-letter mechanism where the event infrastructure supports one.

A retry does not make an unavailable dependency healthy. It only gives transient failures another opportunity to recover.

## Timeouts

Serverless functions are bounded executions.

The Python `ServerlessFunction` uses `asyncio.wait_for()` to enforce its timeout.

The JavaScript implementation races the handler against a timer.

The Java implementation measures execution duration and compares it with the configured timeout.

Timeouts protect the platform and downstream resources from indefinitely executing work.

A timeout that is too short can terminate legitimate work. A timeout that is too long can increase resource consumption and delay failure detection.

Timeout design should therefore reflect the actual operation being performed rather than using one arbitrary value for every function.

## Cold Starts

A cold start occurs when an execution environment must be initialized before handling an invocation.

Initialization can include:

- starting a runtime;
- loading application code;
- importing modules;
- creating framework objects;
- establishing configuration;
- preparing connections or clients.

A warm invocation can reuse an existing environment.

Cold-start behavior is affected by runtime characteristics, package size, initialization work, configuration, traffic patterns, and platform implementation.

The examples intentionally use small artificial delays. They do not claim to reproduce the performance characteristics of any particular cloud provider.

The architectural lesson is that application code should minimize unnecessary initialization work, especially for latency-sensitive functions.

## Scaling

Serverless platforms can create additional execution capacity as invocation demand increases.

A conceptual relationship is:

`required capacity ≈ incoming work / useful concurrency per execution environment`

The Python `AutoScaler`, JavaScript `AutoScaler`, and Java scaling demonstration make this relationship explicit.

The model assumes a target concurrency of four and limits capacity between zero and eight instances.

For a queue depth of 25:

`ceil(25 / 4) = 7`

so the model requests seven execution environments.

This is an educational scaling model rather than a provider-specific autoscaling algorithm. Real platforms consider additional factors such as concurrency limits, available capacity, request duration, queue age, traffic patterns, quotas, and platform-specific scaling policies.

## Scale-to-Zero

A distinctive property of many serverless platforms is the ability to reduce active execution capacity substantially when demand falls.

The example autoscaling model permits a minimum instance count of zero.

This can reduce idle compute consumption, but it can also make the next request pay initialization latency.

Scale-to-zero is therefore a trade-off between idle capacity and startup latency rather than a universal performance advantage.

Applications requiring consistently low latency may use minimum warm capacity where the platform supports it.

## Concurrency

Concurrency determines how much work can be processed simultaneously.

Higher concurrency can improve throughput, but the correct value depends on workload characteristics.

CPU-heavy operations, memory-heavy processing, blocking network calls, database connections, and external API limits all influence useful concurrency.

Unbounded concurrency can overload downstream systems even when the serverless platform itself can accept more requests.

A robust architecture treats downstream capacity as part of the scaling design.

For example:

`serverless concurrency -> database connection pool -> database capacity`

If the function layer scales to hundreds of simultaneous executions while the database can safely handle only a small number of concurrent connections, the database becomes the bottleneck.

## Memory and Compute Allocation

The examples store memory configuration alongside each function.

Memory is not merely a storage limit. In many serverless platforms, compute capacity is related to the configured memory tier.

A function performing image processing, machine learning inference, compression, or large JSON transformations may need a different resource profile from a lightweight API validation function.

The correct configuration is therefore workload-specific.

The SQL `serverless_functions` table enforces positive memory and timeout values and stores minimum and maximum scaling limits.

## Observability

Serverless systems require strong observability because execution environments are ephemeral.

Useful metrics include:

- invocation count;
- failure count;
- duration;
- timeout count;
- cold-start count;
- concurrency;
- event processing delay;
- retry count;
- downstream error rate.

The Python implementation writes a JSON metrics snapshot.

The JavaScript implementation displays a metrics table.

The SQL script creates `function_observability`, which aggregates invocation count, failures, average duration, and cold starts.

Observability data should be correlated with an invocation or event identifier so a request can be traced across multiple functions.

## Serverless Architecture

A larger architecture can be represented as:

`Client`

`-> API Gateway / HTTP trigger`

`-> Request Function`

`-> Event or Queue`

`-> Domain Functions`

`-> Database / Object Storage / External Services`

The key architectural distinction is that the function is not the entire system. Serverless applications are usually compositions of managed infrastructure and short-lived compute.

For example, a file-processing workflow can be:

`object uploaded`

`-> storage event`

`-> validation function`

`-> metadata database`

`-> processing function`

`-> completion event`

This is different from a single web server that continuously watches a filesystem.

## Python Implementation

The Python program uses `asyncio` because event-driven serverless workloads often spend significant time waiting for I/O.

`ServerlessFunction` encapsulates function configuration, execution metrics, timeout behavior, and warm-state simulation.

`EventBus` separates event producers from event consumers.

`RetryPolicy` demonstrates bounded exponential backoff.

`IdempotencyStore` demonstrates duplicate-event detection.

`AutoScaler` models the relationship between queued work and desired execution capacity.

`write_observability_snapshot()` demonstrates how function metrics can be serialized for later analysis.

The program also validates HTTP requests, processes object-storage metadata, creates order results, simulates transient inventory failures, and demonstrates timeout handling.

The implementation uses only the Python standard library.

## JavaScript Implementation

The JavaScript program emphasizes asynchronous execution and event-driven behavior.

`ServerlessFunction` uses Promises and records execution metrics.

`EventBus` stores event subscriptions in a `Map`. `Promise.allSettled()` is important because independent consumers should have independent outcomes.

`RetryPolicy` implements asynchronous exponential backoff.

`IdempotencyStore` shows duplicate event handling.

`AutoScaler` models desired execution capacity.

The implementation also uses Node.js's `crypto.randomUUID()` to generate event identifiers and avoids unnecessary npm dependencies.

The JavaScript-specific value comes from its natural asynchronous programming model rather than from simply translating Python statements.

## C++ Case Study

The C++ program uses a repository-governance scenario to demonstrate how serverless-style execution can be integrated with a policy engine.

`ServerlessFunction` models function configuration, cold initialization, invocation timing, memory configuration, and timeout enforcement.

`RepositoryGovernanceEngine` evaluates Pull Requests against protected-branch conditions.

The governance model keeps these concepts distinct:

- a Pull Request proposes a changeset;
- approvals represent reviewer decisions;
- status checks represent automated validation;
- branch protection defines repository-level merge requirements;
- merge eligibility is the result of evaluating those conditions.

A Pull Request can therefore have two approvals and still be blocked if a required security check has not passed.

It can also satisfy the required checks and approvals but become blocked after approvals are marked stale.

This demonstrates a general event-driven policy pattern: an event can cause state changes, while a policy engine evaluates whether the resulting state satisfies the conditions for a protected operation.

The C++ implementation uses standard containers such as `map`, `set`, and `unordered_map`. The governance engine performs set membership checks for approvals and required status checks.

## Java Enterprise Model

The Java program models serverless execution using explicit domain types.

`Event` is a record, which makes the event structure concise and immutable.

`EventType` provides a closed vocabulary for supported event categories.

`ServerlessFunction` encapsulates asynchronous execution and metrics.

`EventRouter` uses an `EnumMap` because event types are represented by an enum and therefore have a bounded key space.

`IdempotencyStore` demonstrates durable-state semantics conceptually while using an in-memory concurrent map for a self-contained program.

The repository-governance portion uses `PullRequestState` to make lifecycle state explicit.

`BranchProtectionPolicy` captures merge conditions as data rather than scattering them through unrelated conditional statements.

`MergeEligibilityService` evaluates whether a Pull Request satisfies the policy.

This design is useful for enterprise applications because policy rules can be tested independently from transport and execution infrastructure.

## PostgreSQL Data Model

The SQL implementation treats serverless execution as a relational operational domain.

`serverless_functions` stores runtime configuration.

`events` stores event identity, type, source, payload, and processing status.

`function_subscriptions` maps event types to consumers.

`invocations` records execution outcomes and durations.

`processed_events` provides database-level idempotency.

The repository portion provides a separate but related governance domain.

`repositories` and `branches` define repository structure.

`pull_requests` records proposed changes.

`reviewers`, `review_requests`, and `reviews` model review participation and review decisions.

`review_comments` stores file-level review discussions.

`commits` records changesets associated with Pull Requests.

`status_checks` represents automated validation.

`branch_protection_policies` stores repository-level rules.

`required_status_checks` specifies which automated checks are mandatory.

This separation prevents Pull Requests, reviews, approvals, and branch protection from being treated as the same concept.

## Pull Requests, Code Review, Approvals, and Branch Protection

A Pull Request is the workflow object representing a proposed change from a source branch to a target branch.

Code Review evaluates the proposed change. Reviewers can comment on specific files and lines, identify problems, request changes, or approve the work.

An approval is a specific review decision. It is not equivalent to the existence of a Pull Request or the existence of a reviewer assignment.

Branch Protection is a repository policy layer. It can require approvals, require status checks, restrict direct pushes, restrict force pushes, restrict deletion, require conversation resolution, or require linear history.

The relationship is therefore:

`Pull Request -> Code Review -> Approval`

while:

`Branch Protection -> merge eligibility constraints`

The merge decision combines these conditions.

A Pull Request can exist without an approval.

A review can exist without approval.

An approval can exist but become stale.

A protected branch can require multiple approvals and specific status checks before merge eligibility is reached.

This separation is critical in repository-governance systems.

## Status Checks

Automated status checks are independent signals about the proposed change.

Typical checks can validate:

`build`

`unit-tests`

`security-scan`

The SQL model records each check with `pending`, `passed`, or `failed` state.

The merge-evaluation view compares completed checks with the required checks configured by branch protection.

This prevents a simple approval count from being treated as sufficient evidence for merge readiness.

## Review State and Approval Semantics

The review model distinguishes:

`commented`

`changes_requested`

`approved`

`dismissed`

A reviewer assignment identifies who is expected to review.

A review identifies what decision that reviewer submitted.

An approval can later become invalid because the underlying Pull Request changes or because repository policy dismisses stale approvals.

The SQL schema represents dismissal with `dismissed_at`.

The C++ model uses `approvalsStale`.

The Java model uses `approvalsStale` as explicit domain state.

These representations demonstrate the same policy distinction from different implementation perspectives.

## Branch Protection Enforcement

The SQL `branch_protection_policies` table contains:

- required approval count;
- conversation-resolution requirement;
- linear-history requirement;
- direct-push restriction;
- force-push restriction;
- deletion restriction;
- administrator bypass policy.

These are governance rules, not Pull Request content.

The distinction matters because branch protection can apply to every change targeting a protected branch.

A protected `main` branch may reject direct pushes even when no Pull Request exists. A Pull Request can be open while still being ineligible for merge because the branch policy has not been satisfied.

## Security Considerations

Serverless systems expand the number of boundaries that need protection.

Important controls include:

- validating untrusted event payloads;
- authenticating HTTP requests;
- authorizing sensitive operations;
- using least-privilege execution identities;
- restricting access to databases and object storage;
- protecting secrets;
- validating object-storage event metadata;
- preventing replay attacks where applicable;
- using idempotency keys for side-effecting operations;
- limiting concurrency against downstream services;
- monitoring unusual invocation patterns.

Event payloads should be treated as untrusted input.

The presence of a trusted event transport does not automatically make the data inside the event trustworthy.

## Failure Modes

Common failure patterns include:

### Duplicate delivery

A function processes an event successfully, but the acknowledgement path fails. The event is delivered again.

The response is durable idempotency.

### Downstream outage

A function depends on a database or external API that is temporarily unavailable.

The response may involve bounded retries, exponential backoff, circuit-breaking behavior, queue buffering, or delayed processing.

### Timeout

A function exceeds its execution limit.

The response is to investigate workload size, dependency latency, concurrency, and timeout configuration rather than simply increasing the timeout indefinitely.

### Cold-start latency

A low-traffic function receives a request after its previous execution environment has been retired.

The response may involve reducing initialization work or maintaining a small amount of warm capacity when the workload requires predictable latency.

### Downstream saturation

Serverless scaling can create more concurrent function executions than a database or external service can safely handle.

The response is capacity-aware concurrency control rather than unrestricted scaling.

## Performance Considerations

Serverless performance should be evaluated at the complete request path rather than only at function execution time.

For an event-driven application:

`event ingestion + scheduling + cold start + function execution + downstream calls + persistence`

determines end-to-end latency.

For a database-backed function, connection management is particularly important. Creating a new database connection for every invocation can become expensive when the platform scales rapidly.

Caching can reduce repeated work, but cache contents must be treated as optional because execution environments may disappear.

Function package size also affects initialization behavior.

## Cost Considerations

Serverless billing commonly depends on combinations of invocation count, execution duration, resource allocation, and related managed services.

The Python example demonstrates a simplified calculation using invocation count and GB-seconds.

This model is intentionally generic because actual prices differ by provider, region, runtime, architecture, resource configuration, networking, and additional services.

A useful cost model is:

`total cost = request charges + compute charges + dependent service charges`

A low function execution cost does not imply a low application cost if the architecture performs excessive database operations, network transfers, queue operations, or storage operations.

## Database Integrity

The PostgreSQL implementation uses database constraints for rules that belong at the persistence layer.

Examples include:

`PRIMARY KEY` for unique identities.

`FOREIGN KEY` for relationships.

`CHECK` constraints for valid numeric ranges and states.

`UNIQUE` constraints for function names, branch names, commit hashes, and required checks.

The `processed_events` primary key prevents the same function from storing multiple processing results for the same event.

This is stronger than relying only on application code because concurrent application instances can otherwise race.

## Transactions

The final SQL transaction inserts an event, records its processing result, and changes its event status.

The transaction establishes an atomic boundary for those database changes.

If an operation requires several related records to remain consistent, transaction boundaries should be selected around the complete state transition rather than around arbitrary individual statements.

A transaction does not make external side effects automatically atomic. For example, a database transaction cannot automatically roll back an email already delivered by an external provider.

This is one reason event-driven systems often use explicit workflow state, idempotency, and reliable event publication patterns.

## Architecture Boundaries

A mature serverless design separates:

`trigger`

from:

`function logic`

from:

`durable state`

from:

`event transport`

from:

`policy`

from:

`observability`

The code examples intentionally keep these boundaries visible.

The function should process the event.

The event bus or event infrastructure should deliver the event.

The database should maintain durable state.

The policy layer should evaluate domain rules.

Observability should record what happened.

Combining all of these responsibilities into one function creates a system that becomes difficult to test, scale, and operate.

## Common Design Mistakes

### Treating a function as a miniature server

A function should not assume a permanent process lifetime or local durable state.

### Ignoring duplicate delivery

At-least-once event delivery can create duplicate side effects without idempotency.

### Retrying everything

Retries can amplify outages and duplicate non-idempotent operations.

### Scaling without downstream limits

Function concurrency can overwhelm databases and external services.

### Treating approvals as permanent

Repository policies may dismiss approvals after relevant changes.

### Treating branch protection as code review

Review quality and repository enforcement are different mechanisms.

### Putting every operation into one function

Large functions reduce the architectural advantages of independent scaling and deployment.

### Using excessive synchronous dependencies

A serverless function that waits on many sequential services can have poor latency and high execution cost.

## Practical Architectural Distinctions

A function is an execution unit.

An event is a message describing something that happened.

An event trigger connects an event source to a function.

A Pull Request is a repository workflow object.

A review is a reviewer decision about a proposed change.

An approval is a positive review state.

Branch protection is a repository governance policy.

A status check is an automated validation signal.

Merge eligibility is the resulting decision after relevant conditions have been evaluated.

These concepts interact, but they should remain separate in both architecture and data modeling.

## Production Considerations

Production serverless systems need clear ownership of:

- function deployment;
- configuration;
- permissions;
- secrets;
- event contracts;
- retries;
- dead-letter handling;
- idempotency;
- observability;
- quotas;
- concurrency;
- database capacity;
- dependency timeouts;
- incident response.

The platform manages infrastructure, but serverless does not remove operational engineering. It changes the layer at which that engineering occurs.

The strongest design treats serverless functions as components inside a distributed system rather than as isolated pieces of code.
