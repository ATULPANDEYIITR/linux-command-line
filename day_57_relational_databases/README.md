# Relational Database Architecture: Repository Governance Workflow

## Scope

This project models relational database architecture through executable implementations covering schemas, tables, keys, normalization, indexes, constraints, transactions, and ACID-oriented state management.

The examples use repository development as the application domain:

`Repository → Branch → Commit → Pull Request → Review → Conversation → Status Check → Branch Protection → Merge Eligibility → Merge`

The repository workflow provides realistic relationships and state transitions while the central technical subject remains relational database design.

## Architectural Model

The relational model separates entities that have different ownership, cardinality, lifecycle, and integrity requirements.

| Entity | Relational responsibility |
|---|---|
| Repository | Top-level ownership boundary |
| Repository Member | Repository-level identity and role |
| Branch | Named repository state |
| Commit | Immutable change record |
| Branch Commit | Many-to-many-style branch history association |
| Pull Request | Proposed change between branches |
| Pull Request Commit | Changeset association |
| Review | Reviewer decision |
| Review Comment | Discussion attached to a review and pull request |
| Status Check | Automated validation result |
| Branch Protection Policy | Repository governance rules |
| Required Status Check | Policy-to-check relationship |
| Allowed Merge Strategy | Policy-to-strategy relationship |
| Policy Bypass User | Controlled governance exception |
| Merge | Final merge event |

The model deliberately distinguishes proposed work from evaluation and enforcement.

A Pull Request identifies a proposed change.

Code Review records human evaluation and discussion.

Approvals represent effective review decisions.

Branch Protection stores repository-level enforcement rules.

Merge Eligibility is derived from those independent states.

## Relational Design Principles

### Tables and keys

Every major entity has a primary key. Relationships use foreign keys rather than duplicating descriptive information.

`repository.repository_id` identifies a repository.

`branch.repository_id` associates branches with their repository.

`pull_request.source_branch_id` and `pull_request.target_branch_id` represent the two branch roles involved in a proposed change.

The compound uniqueness rule on `(repository_id, pull_request_number)` allows pull request numbers to restart naturally for different repositories while remaining unique within each repository.

### Many-to-many relationships

Several relationships are represented explicitly through association tables.

`branch_commit` associates branches with commits while preserving a branch-specific position.

`pull_request_commit` associates proposed changes with commits and preserves changeset order.

`required_status_check` associates a branch-protection policy with multiple required checks.

`allowed_merge_strategy` associates a policy with permitted merge strategies.

`policy_bypass_user` records narrowly scoped governance exceptions.

These structures avoid comma-separated lists and preserve first-normal-form storage.

## Normalization

The design separates attributes according to their functional dependencies.

A repository name is stored once in `repository`.

A branch references its repository rather than storing repository metadata repeatedly.

A review references its Pull Request and stores the reviewer decision independently from review comments.

A status check is separate from a review because automated checks and human evaluations have different semantics.

Branch protection is separate from Pull Request state because protection is a repository policy, not a property of one proposed change.

This separation reduces update anomalies and makes constraints enforceable at the appropriate relation.

## Pull Requests

A Pull Request is represented by `pull_request`.

Its principal relationships are:

`repository → pull_request`

`source branch → pull_request`

`target branch → pull_request`

`author → pull_request`

`pull_request → commits`

The lifecycle is represented by the `pr_state` enumeration:

`draft → open → closed`

or:

`draft → open → merged`

A draft Pull Request may contain commits without being eligible for merge. Submission changes it to `open`.

Closing a Pull Request prevents further workflow actions that require an open state. A merged Pull Request becomes an immutable historical workflow event at the application level.

The source and target branches are explicitly distinct. This prevents meaningless self-targeting Pull Requests.

## Code Review

Code Review is represented by the `review` and `review_comment` relations.

A review has an explicit state:

| Review state | Meaning |
|---|---|
| `commented` | Reviewer provided feedback without an approval decision |
| `approved` | Reviewer accepted the current change state |
| `changes_requested` | Reviewer identified blocking changes |
| `dismissed` | Previous review decision is no longer active |

Review comments represent discussion content separately from the review decision.

This distinction is important because a discussion comment is not automatically an approval or rejection.

A comment contains a file path and line number so that feedback can be attached to a concrete source location.

The `resolved` field represents whether the conversation has been addressed. Branch protection can require all such conversations to be resolved before merging.

The Python implementation uses mutable domain objects for direct workflow simulation. Java uses immutable records for value-oriented objects such as reviews and comments. JavaScript uses event emission so review and conversation changes can trigger other application behavior.

## Approvals

Approval is not modeled as an independent duplicated table.

Instead, approval is a semantic interpretation of the latest effective review from an eligible reviewer.

The database query uses:

`DISTINCT ON (pull_request_id, reviewer_username)`

ordered by submission time to identify the latest review from each reviewer.

The effective approval count therefore does not simply count every historical approval.

For example, if a reviewer first approves and later requests changes, the later decision supersedes the earlier approval.

This avoids the common data-model error of treating historical approval rows as simultaneously active decisions.

Self-approval is rejected by validation logic.

Reviewer membership is also checked so an arbitrary username cannot create a valid governance decision.

## Branch Protection

Branch Protection is modeled independently from review activity.

A `branch_protection_policy` describes enforcement conditions for a protected branch.

The policy can require:

- A minimum number of approvals
- Successful named status checks
- Resolved conversations
- Linear history
- Restricted merge strategies
- Restricted direct updates
- Restricted force pushes
- Restricted branch deletion

The policy is attached to a branch through a unique foreign key relationship.

This means one branch has at most one active protection policy in this model.

Policy exceptions are represented explicitly through `policy_bypass_user`.

A bypass is therefore an identifiable authorization rule rather than an undocumented application shortcut.

## Status Checks

Status checks are independent from human reviews.

A status check has a name, state, and details.

The supported states are:

`pending`

`success`

`failure`

Required checks are stored in `required_status_check`.

This allows different protected branches to require different automated validations.

For the example repository, the protected `main` branch requires:

| Check | Purpose |
|---|---|
| `unit-tests` | Automated functional verification |
| `security-scan` | Security-oriented validation |
| `schema-validation` | Database or migration validation |

A Pull Request is not eligible merely because its human reviews are approved. All required automated checks must also satisfy the branch policy.

## Merge Eligibility

Merge eligibility is derived rather than stored as an uncontrolled boolean.

The database view `merge_eligibility_report` combines:

- Pull Request state
- Effective approvals
- Required approvals
- Blocking review decisions
- Unresolved conversations
- Required status checks
- Successful status checks
- Branch protection

The Python, C++, and Java implementations use equivalent service-layer evaluation.

The JavaScript implementation exposes the same decision process through an event-driven domain model.

The general decision relationship is:

`Merge Eligibility = PR State + Effective Reviews + Required Checks + Conversation State + Branch Policy`

An approval alone is therefore insufficient.

## Transactions

The PostgreSQL implementation uses a transaction around conversation resolution and eligibility inspection.

The `merge_pull_request` function performs the final merge operation with a row lock on the Pull Request.

The function validates:

1. Pull Request existence
2. Pull Request state
3. Merge actor membership
4. Merge strategy
5. Required approvals
6. Blocking review decisions
7. Conversation resolution
8. Required status checks
9. Bypass authorization

Only after these validations does it insert a merge record and transition the Pull Request to `merged`.

This keeps the final workflow transition atomic.

## Constraints and Triggers

Relational constraints handle rules that can be represented directly by the schema.

Examples include:

- Primary keys
- Foreign keys
- Unique constraints
- Non-null requirements
- Positive line numbers
- Valid state values
- Non-negative approval requirements
- Non-empty names and messages

Triggers enforce rules that require cross-row inspection.

The review membership trigger verifies that the reviewer belongs to the repository associated with the Pull Request.

It also prevents the Pull Request author from using a review to satisfy approval requirements.

The review-comment trigger validates repository membership for discussion authors.

The branch trigger prevents an entity from simultaneously being represented as protected and deleted.

## Index Design

Indexes are placed on access paths used by workflow evaluation.

`idx_pull_request_target_state` supports queries that locate Pull Requests by protected target branch and state.

`idx_review_pr_reviewer_time` supports retrieval of review history by Pull Request and reviewer.

`idx_status_check_pr_state` supports status evaluation.

`idx_review_comment_pr_unresolved` is a partial index because merge eligibility frequently needs unresolved comments rather than all historical comments.

Indexes are not added indiscriminately because every additional index increases write cost and storage requirements.

## Python Implementation

The Python program is a self-contained domain simulation.

Its primary structures are:

- `Repository`
- `Branch`
- `Commit`
- `PullRequest`
- `Review`
- `ReviewComment`
- `StatusCheck`
- `BranchProtection`
- `MergeEligibilityEngine`

Python dataclasses provide explicit domain records.

Enums constrain workflow states and merge strategies.

The `MergeEligibilityEngine` evaluates policies without mutating state. The separate `merge` operation performs the state transition only after eligibility succeeds.

The example deliberately creates a failed security check, demonstrates rejection, repairs the state, and then performs a successful squash merge.

Assertions verify important postconditions.

## JavaScript Implementation

The JavaScript implementation uses Node.js standard-library facilities.

`Map` stores checks, branches, policies, and repository state.

`Set` models repository membership, required checks, merge strategies, and bypass users.

`EventEmitter` represents workflow events such as:

- Pull Request creation
- Commit addition
- Review submission
- Comment creation
- Conversation resolution
- Status updates
- Merge completion

Status checks are processed asynchronously with Promises to represent independent automated validations.

This provides a different engineering model from the synchronous Python implementation while preserving the same relational concepts.

## C++17 Implementation

The C++ program implements repository governance as a strongly typed merge engine.

Enums represent workflow states.

STL containers represent:

- Repository membership
- Branch maps
- Review collections
- Status checks
- Policy sets

`MergeEligibilityEngine` separates evaluation from mutation.

The `MergeDecision` structure returns both eligibility and concrete rejection reasons.

The implementation demonstrates how explicit ownership and value semantics can be used for a governance engine without external libraries.

The program rejects an unresolved conversation before accepting the final squash merge.

## Java 17 Implementation

The Java implementation emphasizes enterprise domain modeling.

Records represent immutable value objects such as:

- `Commit`
- `Review`
- `ReviewComment`
- `StatusCheck`
- `BranchProtectionPolicy`
- `MergeDecision`

Mutable aggregate behavior remains inside `Repository`, `Branch`, and `PullRequest`.

`MergeEligibilityService` acts as the application-level policy evaluator.

Java Streams are used for effective-review selection, approval counting, and blocking-review detection.

The design separates policy data from policy evaluation, allowing the same branch-protection rules to be evaluated without embedding governance conditions inside individual entity classes.

## Security Considerations

Repository governance data represents authorization-sensitive state.

Important controls include:

- Reviewer membership validation
- Author self-approval prevention
- Explicit bypass users
- Protected branch policies
- Direct-update restrictions
- Force-push restrictions
- Required automated checks
- Transactional merge validation
- Immutable historical merge records

The database should be deployed with appropriate PostgreSQL roles and least-privilege permissions.

Application-level authorization should not be treated as a replacement for database constraints where database enforcement is practical.

Bypass accounts should be tightly controlled because bypassing branch protection effectively bypasses multiple repository governance requirements.

## Failure Conditions

The implementations explicitly handle cases such as:

- Missing branches
- Invalid branch names
- Empty commit messages
- Empty Pull Requests
- Self-approval
- Non-member reviewers
- Unresolved conversations
- Missing required checks
- Failed required checks
- Insufficient approvals
- Blocking review decisions
- Prohibited merge strategies
- Non-linear merge strategies under linear-history policy
- Closed Pull Requests
- Merged Pull Requests receiving new commits
- Missing source commits

These cases illustrate why relational integrity and workflow policy should be treated as separate but cooperating layers.

## Performance Characteristics

The primary performance-sensitive operations are review lookup, status-check evaluation, unresolved-conversation detection, and Pull Request lookup by target branch.

The database indexes support these access paths.

Effective-review calculation is proportional to the number of review records associated with a Pull Request.

Status-check validation is proportional to the number of required checks for the applicable branch policy.

Repository-level Pull Request lookup is indexed rather than requiring a full table scan.

The application implementations use hash-based collections where membership or keyed lookup is required, producing expected constant-time lookup for those operations.

## Relationship Between the Four Workflow Areas

The four areas have different responsibilities.

`Pull Request`

Defines the proposed change and its source and target branches.

`Code Review`

Records technical evaluation, comments, discussions, and review states.

`Approvals`

Represents the effective approval decisions derived from eligible reviewer reviews.

`Branch Protection`

Defines repository-level conditions that must be satisfied before a protected branch can accept a merge.

The resulting workflow is:

`Pull Request`
`      ↓`
`Code Review`
`      ↓`
`Effective Approvals`
`      ↓`
`Status Checks + Conversation State`
`      ↓`
`Branch Protection`
`      ↓`
`Merge Eligibility`
`      ↓`
`Merge`

These layers overlap operationally but are not interchangeable.

## Practical Relational Workflow

A typical transaction proceeds as follows:

1. A repository owns the source and target branches.
2. Developers create commits.
3. A Pull Request references the source and target branches.
4. Reviewers submit decisions.
5. Review comments create conversations.
6. Automated systems create status-check results.
7. Branch protection defines the required conditions.
8. The database derives effective review decisions.
9. Merge eligibility evaluates all required conditions.
10. A successful merge records the final merge event.

The relational architecture keeps each stage independently queryable and enforceable.

## File Responsibilities

| File | Primary implementation |
|---|---|
| Python | Repository workflow simulation and merge-eligibility engine |
| JavaScript | Event-driven workflow and asynchronous status processing |
| C++17 | Strongly typed repository governance and merge engine |
| Java 17 | Enterprise domain model and policy service |
| PostgreSQL | Normalized relational schema, constraints, triggers, views, queries, and transactional merge function |
| README.md | Architecture and implementation specification |

## Data Integrity Model

The core integrity hierarchy is:

`Repository`
`  ├── Members`
`  ├── Branches`
`  │     └── Commits`
`  ├── Pull Requests`
`  │     ├── Commits`
`  │     ├── Reviews`
`  │     │     └── Comments`
`  │     └── Status Checks`
`  └── Branch Protection`
`        ├── Required Checks`
`        ├── Merge Strategies`
`        └── Bypass Users`

This structure keeps repository identity, source history, proposed changes, human decisions, automated validation, and enforcement policies as distinct relational concerns.

## Limitations

The model intentionally represents repository governance rather than implementing a complete distributed version-control system.

Commit ancestry is represented relationally through branch and Pull Request associations rather than a full commit graph algorithm.

Merge conflict detection is represented as a governance prerequisite rather than performing a complete three-way source merge.

Authentication, network transport, repository hosting, object storage, and distributed locking across independent services are outside the scope of these implementations.

The PostgreSQL transaction provides database-level atomicity for the modeled merge operation, while production deployments would also require appropriate application authorization and operational controls.
