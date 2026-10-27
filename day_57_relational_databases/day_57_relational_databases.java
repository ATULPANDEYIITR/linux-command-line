import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class RepositoryGovernanceApp {

    enum PullRequestState {
        DRAFT, OPEN, CLOSED, MERGED
    }

    enum ReviewState {
        COMMENTED, APPROVED, CHANGES_REQUESTED, DISMISSED
    }

    enum CheckState {
        PENDING, SUCCESS, FAILURE
    }

    enum MergeStrategy {
        MERGE_COMMIT, SQUASH, REBASE
    }

    static class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class PolicyException extends RuntimeException {
        PolicyException(String message) {
            super(message);
        }
    }

    static class MergeRejectedException extends RuntimeException {
        MergeRejectedException(String message) {
            super(message);
        }
    }

    record Commit(
        String id,
        String message,
        String author,
        List<String> parents
    ) {
        Commit {
            requireText(id, "Commit id");
            requireText(message, "Commit message");
            requireText(author, "Commit author");
            parents = List.copyOf(parents);
        }
    }

    record StatusCheck(
        String name,
        CheckState state,
        String details
    ) {
        StatusCheck {
            requireText(name, "Status check name");
            Objects.requireNonNull(state, "Status check state");
            details = details == null ? "" : details;
        }
    }

    record ReviewComment(
        int id,
        String reviewer,
        String file,
        int line,
        String body,
        boolean resolved
    ) {
        ReviewComment {
            if (id <= 0 || line <= 0) {
                throw new ValidationException("Comment id and line must be positive.");
            }
            requireText(reviewer, "Reviewer");
            requireText(file, "File");
            requireText(body, "Comment body");
        }

        ReviewComment resolve() {
            return new ReviewComment(id, reviewer, file, line, body, true);
        }
    }

    record Review(
        int id,
        String reviewer,
        ReviewState state,
        Instant submittedAt
    ) {
        Review {
            if (id <= 0) {
                throw new ValidationException("Review id must be positive.");
            }
            requireText(reviewer, "Reviewer");
            Objects.requireNonNull(state, "Review state");
            Objects.requireNonNull(submittedAt, "Review timestamp");
        }
    }

    record BranchProtectionPolicy(
        String branch,
        int requiredApprovals,
        Set<String> requiredChecks,
        boolean requireResolvedConversations,
        boolean requireLinearHistory,
        Set<MergeStrategy> allowedStrategies,
        Set<String> bypassUsers
    ) {
        BranchProtectionPolicy {
            requireText(branch, "Protected branch");

            if (requiredApprovals < 0) {
                throw new ValidationException(
                    "Required approvals cannot be negative."
                );
            }

            requiredChecks = Set.copyOf(requiredChecks);
            allowedStrategies = Set.copyOf(allowedStrategies);
            bypassUsers = Set.copyOf(bypassUsers);

            if (allowedStrategies.isEmpty()) {
                throw new ValidationException(
                    "At least one merge strategy is required."
                );
            }
        }
    }

    static final class Branch {
        private final String name;
        private final boolean protectedBranch;
        private final List<String> commits = new ArrayList<>();

        Branch(String name, boolean protectedBranch, List<String> initialCommits) {
            requireText(name, "Branch name");
            this.name = name;
            this.protectedBranch = protectedBranch;
            this.commits.addAll(initialCommits);
        }

        String name() {
            return name;
        }

        boolean protectedBranch() {
            return protectedBranch;
        }

        String head() {
            if (commits.isEmpty()) {
                return null;
            }
            return commits.get(commits.size() - 1);
        }

        List<String> commits() {
            return Collections.unmodifiableList(commits);
        }

        void appendCommit(String commit) {
            requireText(commit, "Commit id");
            commits.add(commit);
        }

        void appendCommits(List<String> newCommits) {
            newCommits.forEach(this::appendCommit);
        }
    }

    static final class PullRequest {
        private final int number;
        private final String title;
        private final String sourceBranch;
        private final String targetBranch;
        private final String author;
        private PullRequestState state;
        private final List<Commit> commits = new ArrayList<>();
        private final List<Review> reviews = new ArrayList<>();
        private final List<ReviewComment> comments = new ArrayList<>();
        private final Map<String, StatusCheck> checks = new HashMap<>();

        PullRequest(
            int number,
            String title,
            String sourceBranch,
            String targetBranch,
            String author,
            boolean draft
        ) {
            if (number <= 0) {
                throw new ValidationException("Pull request number must be positive.");
            }

            requireText(title, "Pull request title");
            requireText(sourceBranch, "Source branch");
            requireText(targetBranch, "Target branch");
            requireText(author, "Author");

            if (sourceBranch.equals(targetBranch)) {
                throw new ValidationException(
                    "Source and target branches must differ."
                );
            }

            this.number = number;
            this.title = title;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.author = author;
            this.state = draft
                ? PullRequestState.DRAFT
                : PullRequestState.OPEN;
        }

        int number() {
            return number;
        }

        String title() {
            return title;
        }

        String sourceBranch() {
            return sourceBranch;
        }

        String targetBranch() {
            return targetBranch;
        }

        String author() {
            return author;
        }

        PullRequestState state() {
            return state;
        }

        List<Commit> commits() {
            return Collections.unmodifiableList(commits);
        }

        List<Review> reviews() {
            return Collections.unmodifiableList(reviews);
        }

        List<ReviewComment> comments() {
            return Collections.unmodifiableList(comments);
        }

        Map<String, StatusCheck> checks() {
            return Collections.unmodifiableMap(checks);
        }

        void addCommit(Commit commit) {
            if (state != PullRequestState.DRAFT &&
                state != PullRequestState.OPEN) {
                throw new PolicyException(
                    "Commits cannot be added after closure."
                );
            }
            commits.add(commit);
        }

        void submit() {
            if (state != PullRequestState.DRAFT) {
                throw new PolicyException(
                    "Only draft pull requests can be submitted."
                );
            }
            if (commits.isEmpty()) {
                throw new ValidationException(
                    "A pull request needs at least one commit."
                );
            }
            state = PullRequestState.OPEN;
        }

        void addReview(Review review) {
            if (state != PullRequestState.OPEN) {
                throw new PolicyException(
                    "Reviews require an open pull request."
                );
            }
            if (review.reviewer().equals(author)) {
                throw new ValidationException(
                    "Self-approval is not permitted."
                );
            }
            reviews.add(review);
        }

        void addComment(ReviewComment comment) {
            if (state != PullRequestState.OPEN) {
                throw new PolicyException(
                    "Comments require an open pull request."
                );
            }
            comments.add(comment);
        }

        void resolveComment(int commentId) {
            for (int i = 0; i < comments.size(); i++) {
                if (comments.get(i).id() == commentId) {
                    comments.set(i, comments.get(i).resolve());
                    return;
                }
            }
            throw new ValidationException(
                "Review comment does not exist: " + commentId
            );
        }

        void setCheck(StatusCheck check) {
            checks.put(check.name(), check);
        }

        boolean hasUnresolvedConversations() {
            return comments.stream().anyMatch(
                comment -> !comment.resolved()
            );
        }

        void markMerged() {
            if (state != PullRequestState.OPEN) {
                throw new PolicyException(
                    "Only open pull requests can be merged."
                );
            }
            state = PullRequestState.MERGED;
        }
    }

    static final class Repository {
        private final String name;
        private final Set<String> members = new HashSet<>();
        private final Map<String, Branch> branches = new HashMap<>();
        private final Map<String, BranchProtectionPolicy> policies =
            new HashMap<>();
        private final Map<Integer, PullRequest> pullRequests =
            new HashMap<>();
        private int nextPullRequest = 1;

        Repository(String name) {
            requireText(name, "Repository name");
            this.name = name;
        }

        String name() {
            return name;
        }

        void addMember(String member) {
            requireText(member, "Member");
            members.add(member);
        }

        boolean isMember(String member) {
            return members.contains(member);
        }

        void addBranch(Branch branch) {
            if (branches.containsKey(branch.name())) {
                throw new PolicyException(
                    "Branch already exists: " + branch.name()
                );
            }
            branches.put(branch.name(), branch);
        }

        Branch branch(String name) {
            Branch branch = branches.get(name);
            if (branch == null) {
                throw new ValidationException(
                    "Branch does not exist: " + name
                );
            }
            return branch;
        }

        void protect(BranchProtectionPolicy policy) {
            if (!branches.containsKey(policy.branch())) {
                throw new ValidationException(
                    "Protected branch does not exist."
                );
            }
            policies.put(policy.branch(), policy);
        }

        BranchProtectionPolicy policy(String branch) {
            return policies.get(branch);
        }

        PullRequest createPullRequest(
            String title,
            String source,
            String target,
            String author,
            boolean draft
        ) {
            if (!branches.containsKey(source) ||
                !branches.containsKey(target)) {
                throw new ValidationException(
                    "Source and target branches must exist."
                );
            }

            if (!members.contains(author)) {
                throw new ValidationException(
                    "Author is not a repository member."
                );
            }

            PullRequest pullRequest = new PullRequest(
                nextPullRequest++,
                title,
                source,
                target,
                author,
                draft
            );

            pullRequests.put(pullRequest.number(), pullRequest);
            return pullRequest;
        }
    }

    record MergeDecision(
        boolean eligible,
        int effectiveApprovals,
        List<String> reasons
    ) {}

    static final class MergeEligibilityService {

        MergeDecision evaluate(
            Repository repository,
            PullRequest pullRequest,
            MergeStrategy strategy,
            String actor
        ) {
            List<String> reasons = new ArrayList<>();

            if (pullRequest.state() != PullRequestState.OPEN) {
                reasons.add("Pull request is not open.");
            }

            if (!repository.isMember(actor)) {
                reasons.add("Merge actor is not a repository member.");
            }

            BranchProtectionPolicy policy =
                repository.policy(pullRequest.targetBranch());

            if (policy == null) {
                return new MergeDecision(
                    reasons.isEmpty(),
                    0,
                    List.copyOf(reasons)
                );
            }

            boolean bypass = policy.bypassUsers().contains(actor);

            if (!bypass &&
                !policy.allowedStrategies().contains(strategy)) {
                reasons.add("Merge strategy is not permitted.");
            }

            Map<String, Review> latestReviews = new HashMap<>();

            pullRequest.reviews().stream()
                .filter(review ->
                    repository.isMember(review.reviewer()) &&
                    !review.reviewer().equals(pullRequest.author())
                )
                .sorted(java.util.Comparator.comparing(Review::submittedAt))
                .forEach(review ->
                    latestReviews.put(review.reviewer(), review)
                );

            int approvals = (int) latestReviews.values().stream()
                .filter(review -> review.state() == ReviewState.APPROVED)
                .count();

            if (!bypass && approvals < policy.requiredApprovals()) {
                reasons.add(
                    "Required approvals: " + policy.requiredApprovals() +
                    ", effective approvals: " + approvals
                );
            }

            boolean blockingReview = latestReviews.values().stream()
                .anyMatch(review ->
                    review.state() == ReviewState.CHANGES_REQUESTED
                );

            if (!bypass && blockingReview) {
                reasons.add(
                    "An effective changes-requested review blocks merging."
                );
            }

            for (String requiredCheck : policy.requiredChecks()) {
                StatusCheck check =
                    pullRequest.checks().get(requiredCheck);

                if (check == null ||
                    check.state() != CheckState.SUCCESS) {
                    reasons.add(
                        "Required check is missing or unsuccessful: " +
                        requiredCheck
                    );
                }
            }

            if (!bypass &&
                policy.requireResolvedConversations() &&
                pullRequest.hasUnresolvedConversations()) {
                reasons.add(
                    "Unresolved review conversations remain."
                );
            }

            if (!bypass &&
                policy.requireLinearHistory() &&
                strategy == MergeStrategy.MERGE_COMMIT) {
                reasons.add(
                    "Linear-history policy rejects merge commits."
                );
            }

            return new MergeDecision(
                reasons.isEmpty(),
                approvals,
                List.copyOf(reasons)
            );
        }

        String merge(
            Repository repository,
            PullRequest pullRequest,
            MergeStrategy strategy,
            String actor
        ) {
            MergeDecision decision =
                evaluate(repository, pullRequest, strategy, actor);

            if (!decision.eligible()) {
                throw new MergeRejectedException(
                    String.join("; ", decision.reasons())
                );
            }

            Branch target = repository.branch(
                pullRequest.targetBranch()
            );
            Branch source = repository.branch(
                pullRequest.sourceBranch()
            );

            if (source.head() == null) {
                throw new MergeRejectedException(
                    "Source branch has no commits."
                );
            }

            String newHead;

            switch (strategy) {
                case SQUASH -> {
                    newHead =
                        "squash-" +
                        pullRequest.number() +
                        "-" +
                        source.head();
                    target.appendCommit(newHead);
                }
                case REBASE -> {
                    target.appendCommits(source.commits());
                    newHead = target.head();
                }
                case MERGE_COMMIT -> {
                    newHead =
                        "merge-" +
                        pullRequest.number() +
                        "-" +
                        source.head();
                    target.appendCommit(newHead);
                }
                default -> throw new MergeRejectedException(
                    "Unsupported merge strategy."
                );
            }

            pullRequest.markMerged();
            return newHead;
        }
    }

    static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new ValidationException(
                field + " must be non-empty."
            );
        }
    }

    public static void main(String[] args) {
        try {
            Repository repository = new Repository("payments-api");

            repository.addMember("alice");
            repository.addMember("bob");
            repository.addMember("carol");
            repository.addMember("david");

            repository.addBranch(
                new Branch(
                    "main",
                    true,
                    List.of("root-001")
                )
            );

            repository.addBranch(
                new Branch(
                    "feature/payment-timeout",
                    false,
                    List.of("root-001", "commit-101")
                )
            );

            repository.protect(
                new BranchProtectionPolicy(
                    "main",
                    2,
                    Set.of("unit-tests", "security-scan"),
                    true,
                    true,
                    EnumSet.of(
                        MergeStrategy.SQUASH,
                        MergeStrategy.REBASE
                    ),
                    Set.of("platform-admin")
                )
            );

            PullRequest pullRequest =
                repository.createPullRequest(
                    "Enforce payment timeout validation",
                    "feature/payment-timeout",
                    "main",
                    "alice",
                    true
                );

            pullRequest.addCommit(
                new Commit(
                    "commit-102",
                    "Validate payment timeout configuration",
                    "alice",
                    List.of("commit-101")
                )
            );

            pullRequest.submit();

            pullRequest.addReview(
                new Review(
                    1,
                    "bob",
                    ReviewState.APPROVED,
                    Instant.now()
                )
            );

            pullRequest.addReview(
                new Review(
                    2,
                    "carol",
                    ReviewState.APPROVED,
                    Instant.now()
                )
            );

            pullRequest.addComment(
                new ReviewComment(
                    1,
                    "bob",
                    "src/payment-service.java",
                    42,
                    "Document the timeout boundary.",
                    false
                )
            );

            pullRequest.setCheck(
                new StatusCheck(
                    "unit-tests",
                    CheckState.SUCCESS,
                    "248 tests passed"
                )
            );

            pullRequest.setCheck(
                new StatusCheck(
                    "security-scan",
                    CheckState.SUCCESS,
                    "No high severity findings"
                )
            );

            MergeEligibilityService service =
                new MergeEligibilityService();

            MergeDecision blocked =
                service.evaluate(
                    repository,
                    pullRequest,
                    MergeStrategy.SQUASH,
                    "alice"
                );

            System.out.println(
                "Before resolution: " + blocked.eligible()
            );

            blocked.reasons().forEach(
                reason -> System.out.println("  - " + reason)
            );

            pullRequest.resolveComment(1);

            MergeDecision eligible =
                service.evaluate(
                    repository,
                    pullRequest,
                    MergeStrategy.SQUASH,
                    "alice"
                );

            System.out.println(
                "\nAfter resolution: " + eligible.eligible()
            );
            System.out.println(
                "Effective approvals: " +
                eligible.effectiveApprovals()
            );

            String newHead =
                service.merge(
                    repository,
                    pullRequest,
                    MergeStrategy.SQUASH,
                    "alice"
                );

            System.out.println(
                "\nRepository: " + repository.name()
            );
            System.out.println(
                "PR state: " + pullRequest.state()
            );
            System.out.println(
                "main head: " + newHead
            );

        } catch (RuntimeException error) {
            System.err.println(
                "Execution failed: " + error.getMessage()
            );
            System.exit(1);
        }
    }
}
