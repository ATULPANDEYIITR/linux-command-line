# Binary Search on Answer

Binary Search on Answer is an optimization technique in which binary search is performed over a range of possible result values rather than over positions in a sorted collection.

The central requirement is a monotonic feasibility predicate.

For a minimization problem, the candidate values normally behave like:

`false false false false true true true`

The first `true` value is the optimal answer.

For a maximization problem, the pattern is normally:

`true true true true false false false`

The last `true` value is the optimal answer.

The five implementations use the same mathematical idea from different engineering perspectives. They are deliberately not translations of one another.

## Relationship between the four optimization concepts

The core technique can be expressed as:

    candidate answer
          |
          v
     feasibility test
          |
       +--+--+
       |     |
     false  true
       |     |
    discard  keep candidate
    right    search left
             for minimum

The important separation is between the **answer space** and the **feasibility space**.

A normal binary search asks whether a target exists in an ordered collection. Binary Search on Answer asks whether a proposed numerical answer satisfies a set of constraints.

A solution usually has four parts:

- Establish the smallest possible answer.
- Establish the largest possible answer.
- Write a feasibility test for one candidate.
- Binary-search for the boundary where feasibility changes.

## Minimum and maximum forms

The Python implementation provides both boundary patterns.

`binary_search_first_true` searches for the smallest feasible answer. It is appropriate for problems such as:

- minimum shipping capacity
- minimum eating speed
- minimum largest partition sum
- minimum worker processing capacity

`binary_search_last_true` searches for the largest feasible answer. It is appropriate for problems such as:

- maximum minimum distance
- maximum achievable minimum allocation

The midpoint is calculated as `low + (high - low) // 2`. This avoids the classic integer-overflow form `low + high` in implementations where the numeric type has bounded range.

## Python implementation

The Python program models several standard allocation and optimization problems.

### Package shipping

`minimum_ship_capacity` receives ordered package weights and a delivery-day limit.

The lower bound is the heaviest package because no capacity smaller than that can transport it.

The upper bound is the total weight because one day can theoretically carry everything.

For each candidate capacity, the feasibility function greedily fills the current day until the next package would exceed the capacity. A new day is then started.

The predicate is monotonic:

    small capacity -> too many days -> infeasible
    large capacity  -> enough capacity -> feasible

The algorithm therefore finds the first feasible capacity.

If there are `n` packages and the numerical answer range is `R`, the complexity is approximately `O(n log R)`.

### Eating speed

`minimum_eating_speed` demonstrates a different feasibility calculation.

For a speed `k`, a pile of size `p` requires:

`ceil(p / k)`

hours.

The total required time is compared with the available hours. Increasing the speed cannot increase the required time, so feasibility is monotonic.

The implementation exits early when the accumulated hours already exceed the limit. This avoids unnecessary work for obviously infeasible candidates.

### Aggressive placement

`aggressive_cows_max_distance` demonstrates the opposite boundary search.

The candidate is a minimum distance between placed objects. A greedy placement procedure determines whether at least the requested number of objects can be placed while respecting that distance.

If distance `d` is feasible, every smaller distance is also feasible.

The search therefore finds the **last feasible distance**.

Sorting the positions costs `O(n log n)`. Each feasibility check is `O(n)`, producing `O(n log n + n log R)` total complexity.

### Partitioning

`minimum_partition_largest_sum` splits an ordered collection into a bounded number of contiguous groups.

The candidate answer is the largest permitted group sum.

The lower bound is the largest individual value. The upper bound is the total sum.

The feasibility test counts how many groups are necessary when no group may exceed the candidate limit.

This pattern appears in workload allocation, contiguous data partitioning, storage assignment, and scheduling problems.

### Maximum minimum allocation

`maximum_minimum_allocation` illustrates the dual optimization direction. Instead of minimizing the maximum load, it searches for the largest minimum allocation that remains feasible.

This distinction matters because the binary-search boundary changes:

- minimize a value: search for first `true`
- maximize a value: search for last `true`

## JavaScript implementation

The JavaScript file uses the same answer-space principle while emphasizing runtime-friendly validation and an event-oriented domain class.

`RepositoryCapacityPlanner` models an ordered workload assigned to a fixed number of workers. It demonstrates that the feasibility predicate can be encapsulated as a domain operation instead of being tied to a standalone algorithm.

The implementation uses `Number.isSafeInteger` because JavaScript's `Number` type cannot exactly represent every integer above `Number.MAX_SAFE_INTEGER`.

The JavaScript code also separates:

- validation failures through `ValidationError`
- generic binary-search mechanics
- problem-specific feasibility predicates
- domain-level processing capacity

This separation makes the boundary-search algorithm reusable without making the feasibility rule generic or opaque.

## C++ implementation

The C++ program uses templates to make the binary-search boundary operation independent of the predicate type.

`first_true` and `last_true` accept callable predicates and operate on `int64_t` answer ranges.

The technical case study introduces a repository governance engine alongside allocation problems. The governance model checks conditions such as:

- source branch synchronization
- conflict resolution
- required approvals
- successful status checks
- unresolved conversations
- protected-branch requirements

These conditions are represented as an eligibility predicate. A candidate state either satisfies the governance rule or does not.

The program also demonstrates why binary search should not be applied merely because values are numeric. A valid answer-space search requires monotonicity. If increasing the candidate can arbitrarily switch between feasible and infeasible states, binary search is not valid.

The C++ implementation uses `std::vector`, `std::sort`, lambdas, templates, exceptions, assertions, and fixed-width integer types. No third-party libraries are required.

## Java implementation

The Java implementation uses explicit domain modeling rather than translating the procedural Python structure.

`ReviewPolicy` is an immutable record representing repository-level review requirements.

`PullRequest` is another immutable record representing the state that must be evaluated.

`ReviewState` makes the workflow state explicit:

- `DRAFT`
- `OPEN`
- `CHANGES_REQUESTED`
- `APPROVED`
- `MERGED`
- `CLOSED`

`MergeEligibilityService` evaluates whether the current Pull Request state satisfies the configured policy.

This separates **review policy** from **Pull Request state** and from **merge-eligibility behavior**.

The same source also contains allocation algorithms because Binary Search on Answer is the primary technical topic. The repository governance model provides an enterprise-oriented example of a feasibility service, while the allocation functions demonstrate numerical answer-space searching directly.

Java's `LongPredicate` is used for the monotonic feasibility function. Records provide compact immutable domain objects, while collections and streams support validation and bound calculation.

## PostgreSQL implementation

The PostgreSQL script models answer-space searching together with repository governance.

The relational model contains:

- `allocation_problem`
- `workload_item`
- `allocation_policy`
- `repository_workflow`
- `branch_protection`

`workload_item` stores ordered numerical workloads. The `(problem_id, sequence_no)` unique constraint preserves one logical position per problem.

`can_allocate` is the database implementation of the monotonic feasibility predicate.

`minimum_feasible_capacity` performs the binary search inside PL/pgSQL. It calculates the answer bounds from the stored workload and repeatedly evaluates `can_allocate`.

This demonstrates an important database principle: the database can enforce and evaluate domain rules rather than merely storing the values required by an external application.

The repository workflow model is deliberately separate from numerical allocation.

`repository_workflow` represents the state of a proposed change, including:

- source and target branches
- branch synchronization
- conflict resolution
- approvals
- successful status checks
- unresolved conversations

`branch_protection` represents repository-level merge requirements. Its policy is evaluated by `validate_branch_governance`.

The distinction is:

| Concept | Responsibility |
|---|---|
| Pull Request workflow | Represents the proposed change and its lifecycle state |
| Code review | Evaluates the quality and correctness of proposed changes |
| Approval | Records a review decision that satisfies an approval requirement |
| Branch protection | Enforces repository-level conditions before merging |

The SQL view `merge_eligibility` exposes the resulting policy decision without duplicating the underlying rules.

The transaction examples demonstrate that policy state can be changed atomically. The successful transaction updates status-check progress and validates the resulting state before committing. The second transaction creates an unresolved-conversation failure and explicitly rolls the invalid state back.

## Pull Requests

A Pull Request provides the workflow for proposing changes from a source branch toward a target branch.

A typical lifecycle is:

    source branch
         |
         v
    draft Pull Request
         |
         v
    ready for review
         |
         +---- commits change
         |
         +---- conversations occur
         |
         +---- status checks run
         |
         +---- reviewers evaluate
         |
         v
    merge eligibility
         |
         +---- merge
         |
         +---- close
         |
         +---- reopen when repository workflow permits

The source branch contains the proposed changes. The target branch is the branch into which those changes would eventually be integrated.

The changeset is composed of commits. A new commit can modify the changeset after review and can invalidate conditions that previously appeared satisfied.

A Draft Pull Request communicates that the proposal is not yet ready for final review. Moving it into a reviewable state changes workflow status but does not itself establish approval or merge eligibility.

Base-branch synchronization is important when the target branch has advanced after the Pull Request was opened. Depending on repository policy, the source branch may need to be updated before merging.

Merge conflicts are different from review failures. A conflict means Git cannot safely combine the relevant histories without additional resolution. A review request or approval does not resolve a conflict.

A Pull Request can be closed without being merged and can, where repository workflow permits, be reopened later. These are lifecycle operations rather than approval decisions.

## Code Review

Code Review evaluates the proposed implementation.

Review activity can contain inline comments tied to specific changed lines. Discussions may identify correctness defects, security concerns, maintainability issues, missing tests, or unclear behavior.

Review states communicate reviewer decisions. A review can approve a changeset, request changes, or provide a neutral comment-only assessment depending on the platform's review model.

A reviewer should evaluate the actual scope of the change rather than turning an unrelated Pull Request into a broad refactoring exercise.

Useful review criteria include:

| Criterion | Question |
|---|---|
| Correctness | Does the change produce the intended behavior? |
| Regression risk | Can existing behavior break? |
| Security | Does the change introduce an exploitable condition? |
| Data integrity | Can invalid or inconsistent state be created? |
| Tests | Are important behavioral paths covered? |
| Maintainability | Is the implementation understandable and supportable? |
| Scope | Does the change remain focused on its stated purpose? |

A review discussion should be resolved only after the underlying concern has been addressed or explicitly accepted according to the project's review process.

A common failure mode is treating the existence of a review as equivalent to approval. Review activity and approval are related but distinct.

## Approvals

An approval is a review decision that can satisfy a repository policy requiring reviewer approval.

Approval eligibility depends on repository rules and reviewer identity. A repository may restrict who can provide an effective approval, such as requiring designated reviewers or preventing a contributor from satisfying a required independent-review condition.

An approval is not necessarily permanent.

A new commit can make an earlier approval stale when the changed code materially alters what was reviewed. A repository policy may dismiss or invalidate the approval when the Pull Request changes.

This produces an important distinction:

    review exists
         |
         v
    review is approved
         |
         v
    approval is eligible
         |
         v
    approval satisfies current policy

Only the final condition contributes to merge eligibility.

The Java `ReviewPolicy` and `MergeEligibilityService` explicitly model this distinction by storing approval requirements separately from the Pull Request's current approval count.

## Branch Protection

Branch Protection is a repository governance mechanism.

It determines which conditions must be satisfied before a protected branch can accept a merge.

Typical conditions include:

- required approvals
- required status checks
- conversation resolution
- source-branch synchronization
- restrictions on direct pushes
- restrictions on force pushes
- restrictions on branch deletion
- permitted merge strategies
- linear-history requirements where configured
- administrator behavior
- explicitly permitted bypass mechanisms

Branch protection should not be confused with code review.

Code Review answers whether reviewers consider the change acceptable. Branch Protection answers whether the repository's configured governance rules allow the change to be merged.

The relationship can be expressed as:

    Pull Request
         |
         | proposes a changeset
         v
    Code Review
         |
         | produces review decisions
         v
    Approvals
         |
         | contributes approval evidence
         v
    Branch Protection
         |
         | evaluates repository policy
         v
    Merge eligibility

Required status checks are independent evidence. An approval cannot substitute for a failed build, failed test, failed security scan, or other required check.

Likewise, a successful status check cannot substitute for a required reviewer approval.

## Merge eligibility as a predicate

The implementations repeatedly use the same logical structure:

    candidate answer/state
            |
            v
        predicate
            |
        +---+---+
        |       |
      false    true
        |       |
      reject  retain

For numerical optimization, the candidate is a capacity, speed, distance, or allocation value.

For repository governance, the candidate is a Pull Request state evaluated against policy.

The mathematical binary-search optimization requires a monotonic numerical predicate. Repository merge eligibility itself is not automatically a binary-search-on-answer problem because repository state can change in multiple directions when commits, reviews, checks, and policy settings change.

That distinction prevents an incorrect use of binary search merely because a system contains boolean conditions.

## Bound selection

Good bounds reduce the number of feasibility evaluations.

For shipping capacity:

`lower bound = maximum item`

`upper bound = total workload`

For partitioning:

`lower bound = maximum element`

`upper bound = total sum`

For minimum eating speed:

`lower bound = 1`

`upper bound = maximum pile`

For minimum distance:

`lower bound = 0`

`upper bound = maximum position - minimum position`

The lower bound must not exclude the correct answer. The upper bound must contain at least one feasible answer for a solvable problem.

Incorrect bounds can make a perfectly correct binary-search loop return an invalid result.

## Edge cases and failure conditions

The implementations explicitly reject invalid collections, empty workloads, non-positive values, invalid group counts, invalid worker counts, and impossible domain configurations.

Important algorithmic edge cases include:

- one workload item
- one available group
- number of groups equal to number of items
- a candidate capacity smaller than one item
- duplicate positions
- very large integer values
- insufficient available time
- unresolved governance conditions
- unsynchronized source branches
- unresolved conflicts
- insufficient approvals
- insufficient successful checks

The feasibility function should also short-circuit when failure is already certain. This improves performance without changing the result.

## Performance

If the answer range contains `R` possible integer values and one feasibility test costs `O(n)`, binary search requires approximately `O(log R)` feasibility evaluations.

The resulting complexity is:

`O(n log R)`

For problems requiring an initial sort, such as maximum minimum distance placement, the total complexity becomes:

`O(n log n + n log R)`

Memory usage is generally `O(1)` beyond the input representation when the feasibility test scans the data without constructing auxiliary structures.

The practical performance benefit becomes substantial when the answer range is large. A linear scan over every candidate may require billions of feasibility evaluations, while binary search requires only logarithmically many candidate evaluations.

## Security and production considerations

Numerical implementations must use integer types large enough for the expected sums. The C++ and Java implementations use 64-bit integer values. The JavaScript implementation validates safe integers because JavaScript `Number` cannot exactly represent every arbitrary-size integer.

Input validation is part of the algorithm rather than an optional presentation concern. Invalid values can break monotonicity or make the problem definition meaningless.

For production allocation systems, overflow-safe arithmetic, bounded inputs, time limits, cancellation, and explicit handling of impossible instances are important.

For repository governance systems, authorization must be enforced separately from a simple boolean eligibility calculation. A caller should not be able to change approval counts, reviewer identity, branch-protection rules, or status-check results merely by invoking an eligibility function.

Database constraints provide another layer of protection. The PostgreSQL model uses primary keys, foreign keys, uniqueness rules, check constraints, indexes, transactions, and server-side functions to keep persisted state consistent.

## Implementation comparison

| Implementation | Main perspective | Binary-search mechanism | Distinctive mechanism |
|---|---|---|---|
| Python | Algorithmic modeling | First/last feasible answer | Dataclasses, validation, callable predicates |
| JavaScript | Interactive/domain-oriented processing | First/last feasible answer | Runtime validation, class-based workload planner |
| C++17 | Governance and algorithm engine | Generic predicate templates | `int64_t`, lambdas, templates, assertions |
| Java 17 | Enterprise domain model | `LongPredicate` boundary search | Records, enums, immutable policy objects, services |
| PostgreSQL | Persistent workflow and policy evaluation | PL/pgSQL answer-space search | Relational constraints, functions, views, CTEs, transactions |

The implementations therefore share one algorithmic principle without collapsing the distinct roles of allocation algorithms, Pull Request workflows, code review, approvals, and branch governance into a single concept.
