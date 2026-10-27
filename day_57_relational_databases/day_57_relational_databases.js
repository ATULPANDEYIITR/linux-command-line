"use strict";

const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");

const PR_STATE = Object.freeze({
  DRAFT: "draft",
  OPEN: "open",
  CLOSED: "closed",
  MERGED: "merged",
});

const REVIEW_STATE = Object.freeze({
  COMMENTED: "commented",
  APPROVED: "approved",
  CHANGES_REQUESTED: "changes_requested",
  DISMISSED: "dismissed",
});

const CHECK_STATE = Object.freeze({
  PENDING: "pending",
  SUCCESS: "success",
  FAILURE: "failure",
});

const MERGE_STRATEGY = Object.freeze({
  MERGE_COMMIT: "merge_commit",
  SQUASH: "squash",
  REBASE: "rebase",
});

class ValidationError extends Error {}
class ConstraintError extends Error {}
class MergeRejectedError extends Error {}

function assertString(value, field) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new ValidationError(`${field} must be a non-empty string`);
  }
}

function cloneSet(values) {
  return new Set(values);
}

class Branch {
  constructor(name, commits = [], protectedBranch = false) {
    assertString(name, "Branch name");
    if (!/^[A-Za-z0-9._/-]+$/.test(name)) {
      throw new ValidationError(`Invalid branch name: ${name}`);
    }
    this.name = name;
    this.commits = [...commits];
    this.protected = protectedBranch;
  }

  get head() {
    return this.commits.at(-1) ?? null;
  }
}

class Review {
  constructor(id, reviewer, state, submittedAt = new Date()) {
    if (!Number.isInteger(id) || id <= 0) {
      throw new ValidationError("Review id must be positive");
    }
    assertString(reviewer, "Reviewer");
    if (!Object.values(REVIEW_STATE).includes(state)) {
      throw new ValidationError(`Invalid review state: ${state}`);
    }
    this.id = id;
    this.reviewer = reviewer;
    this.state = state;
    this.submittedAt = submittedAt;
  }
}

class ReviewComment {
  constructor(id, reviewer, filePath, lineNumber, body) {
    if (!Number.isInteger(lineNumber) || lineNumber < 1) {
      throw new ValidationError("Line number must be positive");
    }
    assertString(filePath, "File path");
    assertString(body, "Comment body");
    this.id = id;
    this.reviewer = reviewer;
    this.filePath = filePath;
    this.lineNumber = lineNumber;
    this.body = body;
    this.resolved = false;
  }
}

class PullRequest extends EventEmitter {
  constructor(number, title, source, target, author, draft = false) {
    super();
    if (!Number.isInteger(number) || number <= 0) {
      throw new ValidationError("Pull request number must be positive");
    }
    assertString(title, "Pull request title");
    assertString(source, "Source branch");
    assertString(target, "Target branch");
    assertString(author, "Author");

    if (source === target) {
      throw new ValidationError("Source and target branches must differ");
    }

    this.number = number;
    this.title = title.trim();
    this.source = source;
    this.target = target;
    this.author = author;
    this.state = draft ? PR_STATE.DRAFT : PR_STATE.OPEN;
    this.commits = [];
    this.reviews = [];
    this.comments = [];
    this.checks = new Map();
    this.mergeStrategy = null;
  }

  addCommit(commitId, message) {
    assertString(commitId, "Commit id");
    assertString(message, "Commit message");

    if (![PR_STATE.DRAFT, PR_STATE.OPEN].includes(this.state)) {
      throw new ConstraintError("Commits cannot be added after closure");
    }

    this.commits.push({ id: commitId, message });
    this.emit("commit-added", { pr: this.number, commitId });
  }

  submit() {
    if (this.state !== PR_STATE.DRAFT) {
      throw new ConstraintError("Only draft pull requests can be submitted");
    }
    if (this.commits.length === 0) {
      throw new ValidationError("Cannot submit an empty pull request");
    }
    this.state = PR_STATE.OPEN;
    this.emit("submitted", { pr: this.number });
  }

  addReview(review) {
    if (this.state !== PR_STATE.OPEN) {
      throw new ConstraintError("Reviews require an open pull request");
    }
    if (review.reviewer === this.author) {
      throw new ValidationError("Self-approval is not permitted");
    }
    this.reviews.push(review);
    this.emit("review-submitted", review);
  }

  addComment(comment) {
    if (this.state !== PR_STATE.OPEN) {
      throw new ConstraintError("Comments require an open pull request");
    }
    this.comments.push(comment);
    this.emit("comment-added", comment);
  }

  resolveComment(commentId) {
    const comment = this.comments.find((item) => item.id === commentId);
    if (!comment) {
      throw new ValidationError(`Unknown comment: ${commentId}`);
    }
    comment.resolved = true;
    this.emit("conversation-resolved", { pr: this.number, commentId });
  }

  setCheck(name, state, details = "") {
    assertString(name, "Check name");
    if (!Object.values(CHECK_STATE).includes(state)) {
      throw new ValidationError(`Invalid check state: ${state}`);
    }
    this.checks.set(name, { name, state, details });
    this.emit("status-updated", { pr: this.number, name, state });
  }

  close() {
    if (this.state === PR_STATE.MERGED) {
      throw new ConstraintError("Merged pull requests cannot be closed");
    }
    this.state = PR_STATE.CLOSED;
    this.emit("closed", { pr: this.number });
  }

  reopen() {
    if (this.state !== PR_STATE.CLOSED) {
      throw new ConstraintError("Only closed pull requests can be reopened");
    }
    this.state = PR_STATE.OPEN;
    this.emit("reopened", { pr: this.number });
  }

  unresolvedComments() {
    return this.comments.filter((comment) => !comment.resolved);
  }
}

class BranchPolicy {
  constructor({
    branch,
    requiredApprovals,
    requiredChecks,
    requireResolvedConversations,
    requireLinearHistory,
    allowedStrategies,
    bypassUsers,
  }) {
    this.branch = branch;
    this.requiredApprovals = requiredApprovals;
    this.requiredChecks = cloneSet(requiredChecks);
    this.requireResolvedConversations = requireResolvedConversations;
    this.requireLinearHistory = requireLinearHistory;
    this.allowedStrategies = cloneSet(allowedStrategies);
    this.bypassUsers = cloneSet(bypassUsers);

    if (!Number.isInteger(requiredApprovals) || requiredApprovals < 0) {
      throw new ValidationError("Approval requirement must be non-negative");
    }
  }
}

class Repository extends EventEmitter {
  constructor(name) {
    super();
    assertString(name, "Repository name");
    this.name = name;
    this.branches = new Map();
    this.members = new Set();
    this.policies = new Map();
    this.pullRequests = new Map();
    this.nextPrNumber = 1;
  }

  addMember(username) {
    assertString(username, "Username");
    this.members.add(username);
  }

  addBranch(branch) {
    if (this.branches.has(branch.name)) {
      throw new ConstraintError(`Duplicate branch: ${branch.name}`);
    }
    this.branches.set(branch.name, branch);
  }

  protectBranch(policy) {
    if (!this.branches.has(policy.branch)) {
      throw new ValidationError("Protected branch must exist");
    }
    this.policies.set(policy.branch, policy);
  }

  createPullRequest(title, source, target, author, draft = false) {
    if (!this.branches.has(source) || !this.branches.has(target)) {
      throw new ValidationError("Both branches must exist");
    }
    if (!this.members.has(author)) {
      throw new ValidationError("Author is not a repository member");
    }

    const pr = new PullRequest(
      this.nextPrNumber++,
      title,
      source,
      target,
      author,
      draft
    );

    this.pullRequests.set(pr.number, pr);
    this.emit("pull-request-created", pr);
    return pr;
  }
}

function effectiveReviews(repository, pr) {
  const latest = new Map();

  [...pr.reviews]
    .sort((a, b) => a.submittedAt - b.submittedAt)
    .forEach((review) => {
      if (repository.members.has(review.reviewer) && review.reviewer !== pr.author) {
        latest.set(review.reviewer, review);
      }
    });

  return latest;
}

function evaluateMerge(repository, pr, strategy, actor) {
  const reasons = [];
  const policy = repository.policies.get(pr.target);

  if (pr.state !== PR_STATE.OPEN) {
    reasons.push("Pull request is not open");
  }

  if (!repository.members.has(actor)) {
    reasons.push("Merge actor is not a repository member");
  }

  if (!policy) {
    return { eligible: reasons.length === 0, reasons };
  }

  const bypass = policy.bypassUsers.has(actor);
  const latest = effectiveReviews(repository, pr);

  const approvals = [...latest.values()].filter(
    (review) => review.state === REVIEW_STATE.APPROVED
  );

  const blockingReview = [...latest.values()].some(
    (review) => review.state === REVIEW_STATE.CHANGES_REQUESTED
  );

  if (!bypass && approvals.length < policy.requiredApprovals) {
    reasons.push(
      `Need ${policy.requiredApprovals} approvals; found ${approvals.length}`
    );
  }

  if (!bypass && blockingReview) {
    reasons.push("An effective changes-requested review blocks merging");
  }

  if (!bypass && !policy.allowedStrategies.has(strategy)) {
    reasons.push(`Merge strategy ${strategy} is not permitted`);
  }

  for (const required of policy.requiredChecks) {
    const check = pr.checks.get(required);
    if (!check || check.state !== CHECK_STATE.SUCCESS) {
      reasons.push(`Required check failed or is missing: ${required}`);
    }
  }

  if (
    !bypass &&
    policy.requireResolvedConversations &&
    pr.unresolvedComments().length > 0
  ) {
    reasons.push("Unresolved review conversations remain");
  }

  if (
    !bypass &&
    policy.requireLinearHistory &&
    strategy === MERGE_STRATEGY.MERGE_COMMIT
  ) {
    reasons.push("Linear history prohibits merge commits");
  }

  return { eligible: reasons.length === 0, reasons };
}

function performMerge(repository, pr, strategy, actor) {
  const decision = evaluateMerge(repository, pr, strategy, actor);

  if (!decision.eligible) {
    throw new MergeRejectedError(decision.reasons.join("; "));
  }

  const target = repository.branches.get(pr.target);
  const source = repository.branches.get(pr.source);

  if (!source.head) {
    throw new MergeRejectedError("Source branch has no commits");
  }

  let newHead;

  if (strategy === MERGE_STRATEGY.SQUASH) {
    newHead = crypto
      .createHash("sha256")
      .update(`squash:${pr.number}:${source.head}`)
      .digest("hex")
      .slice(0, 12);
    target.commits.push(newHead);
  } else if (strategy === MERGE_STRATEGY.REBASE) {
    target.commits.push(...source.commits);
    newHead = target.head;
  } else if (strategy === MERGE_STRATEGY.MERGE_COMMIT) {
    newHead = crypto
      .createHash("sha256")
      .update(`merge:${target.head}:${source.head}:${pr.number}`)
      .digest("hex")
      .slice(0, 12);
    target.commits.push(newHead);
  } else {
    throw new MergeRejectedError(`Unsupported strategy: ${strategy}`);
  }

  pr.state = PR_STATE.MERGED;
  pr.mergeStrategy = strategy;
  repository.emit("merged", {
    pullRequest: pr.number,
    strategy,
    commit: newHead,
  });

  return newHead;
}

async function runChecks(pr) {
  const checks = [
    ["unit-tests", 30, CHECK_STATE.SUCCESS, "248 tests passed"],
    ["security-scan", 45, CHECK_STATE.SUCCESS, "No high severity findings"],
    ["schema-validation", 20, CHECK_STATE.SUCCESS, "Migration is valid"],
  ];

  await Promise.all(
    checks.map(
      ([name, delay, state, details]) =>
        new Promise((resolve) => {
          setTimeout(() => {
            pr.setCheck(name, state, details);
            resolve(name);
          }, delay);
        })
    )
  );
}

async function main() {
  const repository = new Repository("payments-api");

  for (const user of ["alice", "bob", "carol", "david"]) {
    repository.addMember(user);
  }

  repository.addBranch(new Branch("main", ["root-001"], true));
  repository.addBranch(
    new Branch("feature/payment-timeout", ["root-001", "commit-101"])
  );

  repository.protectBranch(
    new BranchPolicy({
      branch: "main",
      requiredApprovals: 2,
      requiredChecks: new Set(["unit-tests", "security-scan", "schema-validation"]),
      requireResolvedConversations: true,
      requireLinearHistory: true,
      allowedStrategies: new Set([MERGE_STRATEGY.SQUASH, MERGE_STRATEGY.REBASE]),
      bypassUsers: new Set(["platform-admin"]),
    })
  );

  repository.on("pull-request-created", (pr) =>
    console.log(`PR #${pr.number} created: ${pr.title}`)
  );
  repository.on("review-submitted", (review) =>
    console.log(`Review ${review.id}: ${review.state}`)
  );
  repository.on("merged", (event) =>
    console.log(`Merged PR #${event.pullRequest} using ${event.strategy}`)
  );

  const pr = repository.createPullRequest(
    "Enforce payment timeout validation",
    "feature/payment-timeout",
    "main",
    "alice",
    true
  );

  pr.addCommit("commit-102", "Validate payment timeout configuration");
  pr.submit();

  pr.addReview(
    new Review(1, "bob", REVIEW_STATE.APPROVED)
  );
  pr.addReview(
    new Review(2, "carol", REVIEW_STATE.APPROVED)
  );

  const comment = new ReviewComment(
    1,
    "bob",
    "src/payment.js",
    42,
    "Document the timeout boundary."
  );
  pr.addComment(comment);

  console.log("\nBefore conversation resolution:");
  console.log(evaluateMerge(repository, pr, MERGE_STRATEGY.SQUASH, "alice"));

  pr.resolveComment(1);

  await runChecks(pr);

  const decision = evaluateMerge(
    repository,
    pr,
    MERGE_STRATEGY.SQUASH,
    "alice"
  );

  console.log("\nAfter checks and resolution:");
  console.log(decision);

  const mergedCommit = performMerge(
    repository,
    pr,
    MERGE_STRATEGY.SQUASH,
    "alice"
  );

  console.log("\nFinal state:");
  console.log({
    pullRequest: pr.number,
    state: pr.state,
    mergeStrategy: pr.mergeStrategy,
    mainHead: repository.branches.get("main").head,
    mergedCommit,
  });
}

main().catch((error) => {
  console.error(`Execution failed: ${error.message}`);
  process.exitCode = 1;
});
