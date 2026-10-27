from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
import hashlib
import re


class PullRequestState(Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class ReviewState(Enum):
    COMMENTED = "commented"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    DISMISSED = "dismissed"


class CheckState(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"


class MergeStrategy(Enum):
    MERGE_COMMIT = "merge_commit"
    SQUASH = "squash"
    REBASE = "rebase"


class DatabaseError(Exception):
    """Base exception for repository database-domain failures."""


class ValidationError(DatabaseError):
    pass


class ConstraintViolation(DatabaseError):
    pass


class MergeRejected(DatabaseError):
    pass


@dataclass(frozen=True)
class Commit:
    commit_id: str
    message: str
    author: str
    parent_ids: Tuple[str, ...] = ()


@dataclass
class Branch:
    name: str
    protected: bool = False
    commit_ids: List[str] = field(default_factory=list)

    @property
    def head(self) -> Optional[str]:
        return self.commit_ids[-1] if self.commit_ids else None


@dataclass
class ReviewComment:
    comment_id: int
    reviewer: str
    file_path: str
    line_number: int
    body: str
    resolved: bool = False


@dataclass
class Review:
    review_id: int
    reviewer: str
    state: ReviewState
    submitted_at: datetime
    comments: List[ReviewComment] = field(default_factory=list)


@dataclass
class StatusCheck:
    name: str
    state: CheckState
    details: str = ""


@dataclass
class BranchProtection:
    branch_name: str
    required_approvals: int = 2
    required_checks: Set[str] = field(default_factory=set)
    require_conversation_resolution: bool = True
    allow_direct_push: bool = False
    allow_force_push: bool = False
    allow_deletion: bool = False
    require_linear_history: bool = False
    allowed_merge_strategies: Set[MergeStrategy] = field(
        default_factory=lambda: {MergeStrategy.SQUASH, MergeStrategy.REBASE}
    )
    bypass_users: Set[str] = field(default_factory=set)


@dataclass
class PullRequest:
    number: int
    title: str
    source_branch: str
    target_branch: str
    author: str
    state: PullRequestState = PullRequestState.OPEN
    commits: List[Commit] = field(default_factory=list)
    reviews: List[Review] = field(default_factory=list)
    checks: Dict[str, StatusCheck] = field(default_factory=dict)
    comments: List[ReviewComment] = field(default_factory=list)
    merge_strategy: Optional[MergeStrategy] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_commit(self, commit: Commit) -> None:
        if self.state not in {PullRequestState.DRAFT, PullRequestState.OPEN}:
            raise ConstraintViolation("Commits cannot be added to a closed or merged pull request.")
        if not commit.message.strip():
            raise ValidationError("Commit message cannot be empty.")
        self.commits.append(commit)
        self.updated_at = datetime.now(timezone.utc)

    def submit(self) -> None:
        if self.state != PullRequestState.DRAFT:
            raise ConstraintViolation("Only a draft pull request can be submitted.")
        if not self.commits:
            raise ValidationError("A pull request must contain at least one commit.")
        self.state = PullRequestState.OPEN
        self.updated_at = datetime.now(timezone.utc)

    def close(self) -> None:
        if self.state == PullRequestState.MERGED:
            raise ConstraintViolation("A merged pull request cannot be closed.")
        self.state = PullRequestState.CLOSED
        self.updated_at = datetime.now(timezone.utc)

    def reopen(self) -> None:
        if self.state != PullRequestState.CLOSED:
            raise ConstraintViolation("Only a closed pull request can be reopened.")
        self.state = PullRequestState.OPEN
        self.updated_at = datetime.now(timezone.utc)

    def add_review(self, review: Review) -> None:
        if self.state != PullRequestState.OPEN:
            raise ConstraintViolation("Reviews can only be submitted to open pull requests.")
        if review.reviewer == self.author:
            raise ValidationError("Self-review is not eligible for approval.")
        self.reviews.append(review)
        self.updated_at = datetime.now(timezone.utc)

    def add_check(self, check: StatusCheck) -> None:
        self.checks[check.name] = check
        self.updated_at = datetime.now(timezone.utc)

    def add_comment(self, comment: ReviewComment) -> None:
        if self.state != PullRequestState.OPEN:
            raise ConstraintViolation("Comments can only be added to open pull requests.")
        if comment.line_number < 1:
            raise ValidationError("Line number must be positive.")
        self.comments.append(comment)

    def unresolved_comments(self) -> List[ReviewComment]:
        return [comment for comment in self.comments if not comment.resolved]


@dataclass
class Repository:
    name: str
    owner: str
    branches: Dict[str, Branch] = field(default_factory=dict)
    pull_requests: Dict[int, PullRequest] = field(default_factory=dict)
    protection: Dict[str, BranchProtection] = field(default_factory=dict)
    members: Set[str] = field(default_factory=set)
    next_pr_number: int = 1

    def add_branch(self, branch: Branch) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch.name):
            raise ValidationError("Invalid branch name.")
        if branch.name in self.branches:
            raise ConstraintViolation(f"Branch already exists: {branch.name}")
        self.branches[branch.name] = branch

    def create_pull_request(
        self,
        title: str,
        source_branch: str,
        target_branch: str,
        author: str,
        draft: bool = False,
    ) -> PullRequest:
        if source_branch not in self.branches or target_branch not in self.branches:
            raise ValidationError("Both source and target branches must exist.")
        if source_branch == target_branch:
            raise ValidationError("Source and target branches must differ.")
        if author not in self.members:
            raise ValidationError("Pull request author is not a repository member.")
        if not title.strip():
            raise ValidationError("Pull request title cannot be empty.")

        pr = PullRequest(
            number=self.next_pr_number,
            title=title.strip(),
            source_branch=source_branch,
            target_branch=target_branch,
            author=author,
            state=PullRequestState.DRAFT if draft else PullRequestState.OPEN,
        )
        self.pull_requests[pr.number] = pr
        self.next_pr_number += 1
        return pr

    def configure_protection(self, policy: BranchProtection) -> None:
        if policy.branch_name not in self.branches:
            raise ValidationError("Protected branch must exist.")
        if policy.required_approvals < 0:
            raise ValidationError("Required approvals cannot be negative.")
        if not policy.allowed_merge_strategies:
            raise ValidationError("At least one merge strategy must be allowed.")
        self.protection[policy.branch_name] = policy


class MergeEligibilityEngine:
    """Evaluates repository-level conditions without mutating the repository."""

    @staticmethod
    def eligible_reviewers(
        repository: Repository,
        pull_request: PullRequest,
    ) -> Set[str]:
        return repository.members - {pull_request.author}

    @staticmethod
    def valid_approvals(
        repository: Repository,
        pull_request: PullRequest,
    ) -> Set[str]:
        eligible = MergeEligibilityEngine.eligible_reviewers(repository, pull_request)

        # A later approval or requested-change review replaces the earlier
        # effective decision from the same reviewer.
        latest: Dict[str, Review] = {}
        for review in sorted(pull_request.reviews, key=lambda r: r.submitted_at):
            if review.reviewer in eligible:
                latest[review.reviewer] = review

        return {
            reviewer
            for reviewer, review in latest.items()
            if review.state == ReviewState.APPROVED
        }

    @staticmethod
    def has_blocking_review(
        repository: Repository,
        pull_request: PullRequest,
    ) -> bool:
        eligible = MergeEligibilityEngine.eligible_reviewers(repository, pull_request)
        latest: Dict[str, Review] = {}

        for review in sorted(pull_request.reviews, key=lambda r: r.submitted_at):
            if review.reviewer in eligible:
                latest[review.reviewer] = review

        return any(
            review.state == ReviewState.CHANGES_REQUESTED
            for review in latest.values()
        )

    @staticmethod
    def evaluate(
        repository: Repository,
        pull_request: PullRequest,
        strategy: MergeStrategy,
        actor: str,
    ) -> Tuple[bool, List[str]]:
        reasons: List[str] = []

        if pull_request.state != PullRequestState.OPEN:
            reasons.append("Pull request is not open.")

        target = repository.branches.get(pull_request.target_branch)
        source = repository.branches.get(pull_request.source_branch)

        if target is None or source is None:
            reasons.append("Source or target branch does not exist.")
            return False, reasons

        policy = repository.protection.get(target.name)

        if policy is None:
            if strategy not in {
                MergeStrategy.MERGE_COMMIT,
                MergeStrategy.SQUASH,
                MergeStrategy.REBASE,
            }:
                reasons.append("Unsupported merge strategy.")
            return not reasons, reasons

        if actor not in repository.members:
            reasons.append("Merge actor is not a repository member.")

        bypass = actor in policy.bypass_users

        if strategy not in policy.allowed_merge_strategies and not bypass:
            reasons.append("Selected merge strategy is prohibited.")

        if not policy.allow_direct_push and target.name == "main":
            # Direct-push restriction is relevant to direct updates. A PR merge
            # remains possible after all merge conditions are satisfied.
            pass

        approvals = MergeEligibilityEngine.valid_approvals(repository, pull_request)
        if len(approvals) < policy.required_approvals and not bypass:
            reasons.append(
                f"Required approvals: {policy.required_approvals}; "
                f"effective approvals: {len(approvals)}."
            )

        if MergeEligibilityEngine.has_blocking_review(repository, pull_request) and not bypass:
            reasons.append("At least one eligible reviewer has an effective changes-requested decision.")

        for check_name in policy.required_checks:
            check = pull_request.checks.get(check_name)
            if check is None:
                reasons.append(f"Required status check is missing: {check_name}.")
            elif check.state != CheckState.SUCCESS:
                reasons.append(
                    f"Required status check is not successful: {check_name} ({check.state.value})."
                )

        if policy.require_conversation_resolution and pull_request.unresolved_comments() and not bypass:
            reasons.append("Unresolved review conversations remain.")

        if policy.require_linear_history and strategy == MergeStrategy.MERGE_COMMIT and not bypass:
            reasons.append("Merge commits are prohibited by the linear-history policy.")

        return not reasons, reasons

    @staticmethod
    def merge(
        repository: Repository,
        pull_request: PullRequest,
        strategy: MergeStrategy,
        actor: str,
    ) -> str:
        allowed, reasons = MergeEligibilityEngine.evaluate(
            repository, pull_request, strategy, actor
        )
        if not allowed:
            raise MergeRejected("; ".join(reasons))

        target = repository.branches[pull_request.target_branch]
        source = repository.branches[pull_request.source_branch]

        if source.head is None:
            raise MergeRejected("Source branch has no commits.")

        if strategy == MergeStrategy.MERGE_COMMIT:
            merge_payload = (
                f"{target.head or 'ROOT'}:{source.head}:{pull_request.number}"
            )
            merge_id = hashlib.sha256(merge_payload.encode()).hexdigest()[:12]
            target.commit_ids.append(merge_id)
        elif strategy == MergeStrategy.SQUASH:
            payload = f"squash:{pull_request.number}:{source.head}"
            squash_id = hashlib.sha256(payload.encode()).hexdigest()[:12]
            target.commit_ids.append(squash_id)
        elif strategy == MergeStrategy.REBASE:
            target.commit_ids.extend(source.commit_ids)
        else:
            raise MergeRejected("Unsupported merge strategy.")

        pull_request.state = PullRequestState.MERGED
        pull_request.merge_strategy = strategy
        return target.head or ""


def build_repository() -> Repository:
    repository = Repository("payments-api", "platform-team")
    repository.members.update({"alice", "bob", "carol", "david", "eve"})

    repository.add_branch(Branch("main", protected=True, commit_ids=["root-001"]))
    repository.add_branch(
        Branch("feature/payment-timeout", commit_ids=["root-001", "commit-101"])
    )

    repository.configure_protection(
        BranchProtection(
            branch_name="main",
            required_approvals=2,
            required_checks={"unit-tests", "security-scan"},
            require_conversation_resolution=True,
            allow_direct_push=False,
            allow_force_push=False,
            allow_deletion=False,
            require_linear_history=True,
            allowed_merge_strategies={MergeStrategy.SQUASH, MergeStrategy.REBASE},
            bypass_users={"platform-admin"},
        )
    )
    return repository


def populate_pull_request(repository: Repository) -> PullRequest:
    pr = repository.create_pull_request(
        title="Enforce payment timeout validation",
        source_branch="feature/payment-timeout",
        target_branch="main",
        author="alice",
        draft=True,
    )

    pr.add_commit(
        Commit(
            commit_id="commit-102",
            message="Validate payment timeout configuration",
            author="alice",
            parent_ids=("commit-101",),
        )
    )
    pr.submit()

    now = datetime.now(timezone.utc)
    pr.add_review(
        Review(
            review_id=1,
            reviewer="bob",
            state=ReviewState.APPROVED,
            submitted_at=now,
        )
    )
    pr.add_review(
        Review(
            review_id=2,
            reviewer="carol",
            state=ReviewState.APPROVED,
            submitted_at=now,
        )
    )

    pr.add_check(StatusCheck("unit-tests", CheckState.SUCCESS, "248 tests passed"))
    pr.add_check(StatusCheck("security-scan", CheckState.SUCCESS, "No high severity findings"))

    comment = ReviewComment(
        comment_id=1,
        reviewer="bob",
        file_path="src/payment.py",
        line_number=42,
        body="Please document the timeout boundary.",
        resolved=False,
    )
    pr.add_comment(comment)
    comment.resolved = True

    return pr


def demonstrate_failure(repository: Repository, pr: PullRequest) -> None:
    # Introduce a failure after valid approvals to show that database-style
    # state evaluation is not equivalent to merely counting approvals.
    pr.add_check(StatusCheck("security-scan", CheckState.FAILURE, "Critical dependency issue"))

    try:
        MergeEligibilityEngine.merge(
            repository,
            pr,
            MergeStrategy.SQUASH,
            "alice",
        )
    except MergeRejected as exc:
        print("Expected merge rejection:")
        print(f"  {exc}")

    pr.add_check(StatusCheck("security-scan", CheckState.SUCCESS, "Issue remediated"))

    allowed, reasons = MergeEligibilityEngine.evaluate(
        repository,
        pr,
        MergeStrategy.SQUASH,
        "alice",
    )
    print(f"\nEligibility after remediation: {allowed}")
    if reasons:
        for reason in reasons:
            print(f"  - {reason}")


def run_assertions(repository: Repository, pr: PullRequest) -> None:
    assert pr.state == PullRequestState.OPEN
    assert len(pr.commits) == 1
    assert len(MergeEligibilityEngine.valid_approvals(repository, pr)) == 2
    assert repository.protection["main"].required_approvals == 2

    latest_check = pr.checks["security-scan"]
    assert latest_check.state == CheckState.SUCCESS

    head_before = repository.branches["main"].head
    merged_head = MergeEligibilityEngine.merge(
        repository,
        pr,
        MergeStrategy.SQUASH,
        "alice",
    )
    assert pr.state == PullRequestState.MERGED
    assert merged_head != head_before
    assert repository.branches["main"].head == merged_head


def main() -> None:
    repository = build_repository()
    pr = populate_pull_request(repository)

    print(f"Repository: {repository.name}")
    print(f"Pull Request: #{pr.number} - {pr.title}")
    print(f"State: {pr.state.value}")
    print(f"Source -> Target: {pr.source_branch} -> {pr.target_branch}")

    approvals = MergeEligibilityEngine.valid_approvals(repository, pr)
    print(f"Effective approvals: {sorted(approvals)}")
    print(f"Required checks: {sorted(repository.protection['main'].required_checks)}")

    demonstrate_failure(repository, pr)
    run_assertions(repository, pr)

    print(f"\nFinal PR state: {pr.state.value}")
    print(f"Final main branch head: {repository.branches['main'].head}")


if __name__ == "__main__":
    main()
