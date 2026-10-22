import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

public class CdnGovernanceCaseStudy {

    enum ReviewState {
        PENDING,
        APPROVED,
        CHANGES_REQUESTED,
        COMMENTED,
        DISMISSED
    }

    enum PullRequestState {
        DRAFT,
        OPEN,
        MERGED,
        CLOSED
    }

    enum CheckState {
        PASSING,
        FAILING,
        PENDING
    }

    record ContentObject(
        String path,
        String etag,
        String contentType,
        int maxAgeSeconds,
        boolean privateContent
    ) {
        ContentObject {
            Objects.requireNonNull(path);
            Objects.requireNonNull(etag);
            Objects.requireNonNull(contentType);

            if (!path.startsWith("/")) {
                throw new IllegalArgumentException(
                    "Content path must start with /."
                );
            }

            if (maxAgeSeconds < 0) {
                throw new IllegalArgumentException(
                    "maxAgeSeconds cannot be negative."
                );
            }
        }

        boolean cacheable() {
            return !privateContent && maxAgeSeconds > 0;
        }
    }

    static final class EdgeCache {
        private final int capacity;

        private final LinkedHashMap<String, CacheEntry> entries =
            new LinkedHashMap<>(16, 0.75f, true);

        EdgeCache(int capacity) {
            if (capacity <= 0) {
                throw new IllegalArgumentException(
                    "Cache capacity must be positive."
                );
            }

            this.capacity = capacity;
        }

        Optional<ContentObject> get(
            String path,
            Instant now
        ) {
            CacheEntry entry = entries.get(path);

            if (entry == null) {
                return Optional.empty();
            }

            if (now.isBefore(entry.expiresAt())) {
                return Optional.of(entry.content());
            }

            entries.remove(path);
            return Optional.empty();
        }

        void put(
            ContentObject content,
            Instant now
        ) {
            if (!content.cacheable()) {
                return;
            }

            entries.put(
                content.path(),
                new CacheEntry(
                    content,
                    now.plusSeconds(content.maxAgeSeconds())
                )
            );

            while (entries.size() > capacity) {
                String oldest = entries.keySet().iterator().next();
                entries.remove(oldest);
            }
        }

        boolean invalidate(String path) {
            return entries.remove(path) != null;
        }

        Set<String> paths() {
            return Collections.unmodifiableSet(entries.keySet());
        }
    }

    record CacheEntry(
        ContentObject content,
        Instant expiresAt
    ) {}

    record Reviewer(
        String username,
        boolean eligible
    ) {}

    record Review(
        Reviewer reviewer,
        ReviewState state,
        List<String> comments,
        boolean stale
    ) {
        Review {
            comments = List.copyOf(comments);
        }

        boolean activeApproval() {
            return reviewer.eligible()
                && state == ReviewState.APPROVED
                && !stale;
        }
    }

    record BranchProtectionPolicy(
        String branch,
        int requiredApprovals,
        Set<String> requiredChecks,
        boolean requireResolvedConversations,
        boolean preventDirectPush,
        boolean preventForcePush,
        boolean requireLinearHistory
    ) {
        BranchProtectionPolicy {
            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                    "Required approvals cannot be negative."
                );
            }

            requiredChecks = Set.copyOf(requiredChecks);
        }
    }

    static final class PullRequest {
        private final String id;
        private final String sourceBranch;
        private final String targetBranch;
        private PullRequestState state;
        private final List<String> commits;
        private final List<Review> reviews;
        private final EnumMap<String, CheckState> checks;
        private int unresolvedConversations;
        private boolean mergeConflict;

        PullRequest(
            String id,
            String sourceBranch,
            String targetBranch
        ) {
            if (sourceBranch.equals(targetBranch)) {
                throw new IllegalArgumentException(
                    "Source and target branches must differ."
                );
            }

            this.id = Objects.requireNonNull(id);
            this.sourceBranch = Objects.requireNonNull(sourceBranch);
            this.targetBranch = Objects.requireNonNull(targetBranch);
            this.state = PullRequestState.OPEN;
            this.commits = new ArrayList<>();
            this.reviews = new ArrayList<>();
            this.checks = new EnumMap<>(String.class);
        }

        void addCommit(String commitId) {
            if (state != PullRequestState.OPEN) {
                throw new IllegalStateException(
                    "Commits can only be added to an open Pull Request."
                );
            }

            commits.add(Objects.requireNonNull(commitId));
        }

        void addReview(Review review) {
            reviews.add(Objects.requireNonNull(review));
        }

        void setCheck(String name, CheckState state) {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Check name cannot be blank."
                );
            }

            checks.put(name, Objects.requireNonNull(state));
        }

        void setUnresolvedConversations(int count) {
            if (count < 0) {
                throw new IllegalArgumentException(
                    "Conversation count cannot be negative."
                );
            }

            unresolvedConversations = count;
        }

        void setMergeConflict(boolean mergeConflict) {
            this.mergeConflict = mergeConflict;
        }

        void markDraft() {
            if (state == PullRequestState.OPEN) {
                state = PullRequestState.DRAFT;
            }
        }

        void reopen() {
            if (state == PullRequestState.CLOSED) {
                state = PullRequestState.OPEN;
            }
        }

        PullRequestState state() {
            return state;
        }

        String id() {
            return id;
        }

        String targetBranch() {
            return targetBranch;
        }

        List<Review> reviews() {
            return Collections.unmodifiableList(reviews);
        }

        Map<String, CheckState> checks() {
            return Collections.unmodifiableMap(checks);
        }

        int unresolvedConversations() {
            return unresolvedConversations;
        }

        boolean hasCommits() {
            return !commits.isEmpty();
        }

        boolean hasConflict() {
            return mergeConflict;
        }
    }

    static final class MergeEligibilityService {

        static List<String> evaluate(
            PullRequest pr,
            BranchProtectionPolicy policy
        ) {
            List<String> failures = new ArrayList<>();

            if (pr.state() != PullRequestState.OPEN) {
                failures.add("Pull Request must be open.");
            }

            if (!pr.hasCommits()) {
                failures.add("Pull Request must contain at least one commit.");
            }

            if (pr.hasConflict()) {
                failures.add("Merge conflicts must be resolved.");
            }

            for (String required : policy.requiredChecks()) {
                CheckState state = pr.checks().get(required);

                if (state != CheckState.PASSING) {
                    failures.add(
                        "Required check is not passing: " + required
                    );
                }
            }

            long approvals = pr.reviews()
                .stream()
                .filter(Review::activeApproval)
                .count();

            if (approvals < policy.requiredApprovals()) {
                failures.add(
                    "Approval requirement not satisfied: "
                    + approvals
                    + "/"
                    + policy.requiredApprovals()
                );
            }

            if (
                policy.requireResolvedConversations()
                && pr.unresolvedConversations() > 0
            ) {
                failures.add(
                    "Unresolved conversations: "
                    + pr.unresolvedConversations()
                );
            }

            return List.copyOf(failures);
        }
    }

    static final class OriginRepository {
        private final Map<String, ContentObject> objects = new HashMap<>();

        void publish(ContentObject content) {
            objects.put(content.path(), content);
        }

        ContentObject get(String path) {
            ContentObject content = objects.get(path);

            if (content == null) {
                throw new IllegalArgumentException(
                    "Origin content not found: " + path
                );
            }

            return content;
        }
    }

    public static void main(String[] args) {
        OriginRepository origin = new OriginRepository();

        origin.publish(
            new ContentObject(
                "/assets/app.js",
                "etag-app-001",
                "application/javascript",
                300,
                false
            )
        );

        origin.publish(
            new ContentObject(
                "/account/profile.json",
                "etag-private-001",
                "application/json",
                0,
                true
            )
        );

        EdgeCache edgeCache = new EdgeCache(2);
        Instant now = Instant.now();

        ContentObject app = origin.get("/assets/app.js");

        edgeCache.put(app, now);

        System.out.println(
            "First edge lookup: "
            + edgeCache.get("/assets/app.js", now).isPresent()
        );

        System.out.println(
            "Private object cacheable: "
            + origin.get("/account/profile.json").cacheable()
        );

        BranchProtectionPolicy policy =
            new BranchProtectionPolicy(
                "main",
                2,
                Set.of("unit-tests", "security-scan"),
                true,
                true,
                true,
                true
            );

        PullRequest pullRequest =
            new PullRequest(
                "PR-2007",
                "feature/edge-routing",
                "main"
            );

        pullRequest.addCommit("commit-a");
        pullRequest.addCommit("commit-b");

        Reviewer alice = new Reviewer("alice", true);
        Reviewer bob = new Reviewer("bob", true);

        pullRequest.addReview(
            new Review(
                alice,
                ReviewState.APPROVED,
                List.of("Caching headers are explicit."),
                false
            )
        );

        pullRequest.addReview(
            new Review(
                bob,
                ReviewState.APPROVED,
                List.of("Origin fallback is handled."),
                false
            )
        );

        pullRequest.setCheck("unit-tests", CheckState.PASSING);
        pullRequest.setCheck("security-scan", CheckState.PASSING);
        pullRequest.setUnresolvedConversations(0);
        pullRequest.setMergeConflict(false);

        List<String> failures =
            MergeEligibilityService.evaluate(
                pullRequest,
                policy
            );

        System.out.println("\nMerge eligibility for " + pullRequest.id());

        if (failures.isEmpty()) {
            System.out.println("ELIGIBLE: branch protection conditions pass.");
        } else {
            failures.forEach(failure ->
                System.out.println("BLOCKED: " + failure)
            );
        }

        Review staleApproval =
            new Review(
                alice,
                ReviewState.APPROVED,
                List.of(),
                true
            );

        PullRequest staleApprovalPr =
            new PullRequest(
                "PR-2008",
                "feature/stale-approval",
                "main"
            );

        staleApprovalPr.addCommit("commit-c");
        staleApprovalPr.addReview(staleApproval);
        staleApprovalPr.addReview(
            new Review(
                bob,
                ReviewState.APPROVED,
                List.of(),
                false
            )
        );
        staleApprovalPr.setCheck("unit-tests", CheckState.PASSING);
        staleApprovalPr.setCheck("security-scan", CheckState.PASSING);

        failures =
            MergeEligibilityService.evaluate(
                staleApprovalPr,
                policy
            );

        System.out.println(
            "\nStale approval scenario: "
            + (failures.isEmpty() ? "ELIGIBLE" : "BLOCKED")
        );

        failures.forEach(failure ->
            System.out.println("BLOCKED: " + failure)
        );

        System.out.println(
            "\nEdge cache paths before purge: "
            + edgeCache.paths()
        );

        edgeCache.invalidate("/assets/app.js");

        System.out.println(
            "Edge cache paths after purge: "
            + edgeCache.paths()
        );
    }
}
