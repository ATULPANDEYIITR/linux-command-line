#include <algorithm>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

enum class PullRequestState {
    Draft,
    Open,
    Closed,
    Merged
};

enum class ReviewState {
    Commented,
    Approved,
    ChangesRequested,
    Dismissed
};

enum class CheckState {
    Pending,
    Success,
    Failure
};

enum class MergeStrategy {
    MergeCommit,
    Squash,
    Rebase
};

std::string to_string(PullRequestState state) {
    switch (state) {
        case PullRequestState::Draft: return "draft";
        case PullRequestState::Open: return "open";
        case PullRequestState::Closed: return "closed";
        case PullRequestState::Merged: return "merged";
    }
    return "unknown";
}

std::string to_string(ReviewState state) {
    switch (state) {
        case ReviewState::Commented: return "commented";
        case ReviewState::Approved: return "approved";
        case ReviewState::ChangesRequested: return "changes_requested";
        case ReviewState::Dismissed: return "dismissed";
    }
    return "unknown";
}

std::string to_string(MergeStrategy strategy) {
    switch (strategy) {
        case MergeStrategy::MergeCommit: return "merge_commit";
        case MergeStrategy::Squash: return "squash";
        case MergeStrategy::Rebase: return "rebase";
    }
    return "unknown";
}

class ValidationError : public std::runtime_error {
public:
    explicit ValidationError(const std::string& message)
        : std::runtime_error(message) {}
};

class ConstraintViolation : public std::runtime_error {
public:
    explicit ConstraintViolation(const std::string& message)
        : std::runtime_error(message) {}
};

class MergeRejected : public std::runtime_error {
public:
    explicit MergeRejected(const std::string& message)
        : std::runtime_error(message) {}
};

struct Commit {
    std::string id;
    std::string message;
    std::string author;
    std::vector<std::string> parents;
};

struct ReviewComment {
    int id{};
    std::string reviewer;
    std::string file;
    int line{};
    std::string body;
    bool resolved{false};
};

struct Review {
    int id{};
    std::string reviewer;
    ReviewState state{};
    std::chrono::system_clock::time_point submittedAt;
};

struct StatusCheck {
    std::string name;
    CheckState state{};
    std::string details;
};

struct Branch {
    std::string name;
    bool protectedBranch{false};
    std::vector<std::string> commits;

    const std::string* head() const {
        if (commits.empty()) {
            return nullptr;
        }
        return &commits.back();
    }
};

struct BranchProtection {
    std::string branch;
    std::size_t requiredApprovals{0};
    std::set<std::string> requiredChecks;
    bool requireResolvedConversations{true};
    bool requireLinearHistory{false};
    std::set<MergeStrategy> allowedStrategies;
    std::set<std::string> bypassUsers;
};

class PullRequest {
private:
    int number_;
    std::string title_;
    std::string source_;
    std::string target_;
    std::string author_;
    PullRequestState state_;
    std::vector<Commit> commits_;
    std::vector<Review> reviews_;
    std::vector<ReviewComment> comments_;
    std::map<std::string, StatusCheck> checks_;
    MergeStrategy mergeStrategy_{MergeStrategy::Squash};

public:
    PullRequest(
        int number,
        std::string title,
        std::string source,
        std::string target,
        std::string author,
        PullRequestState state
    )
        : number_(number),
          title_(std::move(title)),
          source_(std::move(source)),
          target_(std::move(target)),
          author_(std::move(author)),
          state_(state) {

        if (number_ <= 0 || title_.empty() || source_.empty() ||
            target_.empty() || author_.empty()) {
            throw ValidationError("Invalid pull request fields.");
        }

        if (source_ == target_) {
            throw ValidationError("Source and target branches must differ.");
        }
    }

    int number() const { return number_; }
    const std::string& title() const { return title_; }
    const std::string& source() const { return source_; }
    const std::string& target() const { return target_; }
    const std::string& author() const { return author_; }
    PullRequestState state() const { return state_; }

    const std::vector<Commit>& commits() const { return commits_; }
    const std::vector<Review>& reviews() const { return reviews_; }
    const std::vector<ReviewComment>& comments() const { return comments_; }
    const std::map<std::string, StatusCheck>& checks() const { return checks_; }

    void addCommit(Commit commit) {
        if (state_ != PullRequestState::Draft &&
            state_ != PullRequestState::Open) {
            throw ConstraintViolation("Cannot add commits after closure.");
        }
        if (commit.id.empty() || commit.message.empty()) {
            throw ValidationError("Commit id and message are required.");
        }
        commits_.push_back(std::move(commit));
    }

    void submit() {
        if (state_ != PullRequestState::Draft) {
            throw ConstraintViolation("Only drafts can be submitted.");
        }
        if (commits_.empty()) {
            throw ValidationError("A pull request needs at least one commit.");
        }
        state_ = PullRequestState::Open;
    }

    void addReview(Review review) {
        if (state_ != PullRequestState::Open) {
            throw ConstraintViolation("Reviews require an open pull request.");
        }
        if (review.reviewer == author_) {
            throw ValidationError("Self-review cannot satisfy approval.");
        }
        reviews_.push_back(std::move(review));
    }

    void addComment(ReviewComment comment) {
        if (state_ != PullRequestState::Open) {
            throw ConstraintViolation("Comments require an open pull request.");
        }
        if (comment.line <= 0 || comment.body.empty()) {
            throw ValidationError("Invalid review comment.");
        }
        comments_.push_back(std::move(comment));
    }

    void resolveComment(int commentId) {
        auto it = std::find_if(
            comments_.begin(),
            comments_.end(),
            [commentId](const ReviewComment& comment) {
                return comment.id == commentId;
            }
        );

        if (it == comments_.end()) {
            throw ValidationError("Review comment not found.");
        }

        it->resolved = true;
    }

    void setCheck(StatusCheck check) {
        if (check.name.empty()) {
            throw ValidationError("Status check name cannot be empty.");
        }
        checks_[check.name] = std::move(check);
    }

    bool hasUnresolvedComments() const {
        return std::any_of(
            comments_.begin(),
            comments_.end(),
            [](const ReviewComment& comment) {
                return !comment.resolved;
            }
        );
    }

    void markMerged(MergeStrategy strategy) {
        if (state_ != PullRequestState::Open) {
            throw ConstraintViolation("Only open pull requests can be merged.");
        }
        mergeStrategy_ = strategy;
        state_ = PullRequestState::Merged;
    }
};

class Repository {
private:
    std::string name_;
    std::unordered_set<std::string> members_;
    std::map<std::string, Branch> branches_;
    std::map<std::string, BranchProtection> protections_;
    std::map<int, PullRequest> pullRequests_;
    int nextPullRequest_{1};

public:
    explicit Repository(std::string name)
        : name_(std::move(name)) {}

    const std::string& name() const {
        return name_;
    }

    void addMember(const std::string& member) {
        if (member.empty()) {
            throw ValidationError("Member name cannot be empty.");
        }
        members_.insert(member);
    }

    bool isMember(const std::string& member) const {
        return members_.contains(member);
    }

    void addBranch(Branch branch) {
        if (branch.name.empty()) {
            throw ValidationError("Branch name cannot be empty.");
        }
        if (branches_.contains(branch.name)) {
            throw ConstraintViolation("Duplicate branch: " + branch.name);
        }
        branches_.emplace(branch.name, std::move(branch));
    }

    Branch& branch(const std::string& name) {
        auto it = branches_.find(name);
        if (it == branches_.end()) {
            throw ValidationError("Branch does not exist: " + name);
        }
        return it->second;
    }

    const Branch& branch(const std::string& name) const {
        auto it = branches_.find(name);
        if (it == branches_.end()) {
            throw ValidationError("Branch does not exist: " + name);
        }
        return it->second;
    }

    void protectBranch(BranchProtection protection) {
        if (!branches_.contains(protection.branch)) {
            throw ValidationError("Protected branch does not exist.");
        }
        if (protection.allowedStrategies.empty()) {
            throw ValidationError("At least one merge strategy is required.");
        }
        protections_[protection.branch] = std::move(protection);
    }

    const BranchProtection* protectionFor(const std::string& branch) const {
        auto it = protections_.find(branch);
        if (it == protections_.end()) {
            return nullptr;
        }
        return &it->second;
    }

    PullRequest& createPullRequest(
        const std::string& title,
        const std::string& source,
        const std::string& target,
        const std::string& author,
        bool draft
    ) {
        if (!branches_.contains(source) || !branches_.contains(target)) {
            throw ValidationError("Source and target branches must exist.");
        }
        if (!isMember(author)) {
            throw ValidationError("Author is not a repository member.");
        }

        auto [it, inserted] = pullRequests_.try_emplace(
            nextPullRequest_,
            nextPullRequest_,
            title,
            source,
            target,
            author,
            draft ? PullRequestState::Draft : PullRequestState::Open
        );

        if (!inserted) {
            throw ConstraintViolation("Pull request number collision.");
        }

        ++nextPullRequest_;
        return it->second;
    }
};

struct MergeDecision {
    bool eligible{false};
    std::vector<std::string> reasons;
    std::size_t effectiveApprovals{0};
};

class MergeEligibilityEngine {
public:
    static MergeDecision evaluate(
        const Repository& repository,
        const PullRequest& pr,
        MergeStrategy strategy,
        const std::string& actor
    ) {
        MergeDecision decision;

        if (pr.state() != PullRequestState::Open) {
            decision.reasons.push_back("Pull request is not open.");
        }

        if (!repository.isMember(actor)) {
            decision.reasons.push_back("Merge actor is not a repository member.");
        }

        const BranchProtection* policy =
            repository.protectionFor(pr.target());

        if (policy == nullptr) {
            decision.eligible = decision.reasons.empty();
            return decision;
        }

        const bool bypass = policy->bypassUsers.contains(actor);

        if (!bypass && !policy->allowedStrategies.contains(strategy)) {
            decision.reasons.push_back("Merge strategy is prohibited.");
        }

        std::unordered_map<std::string, Review> latestReviews;

        for (const auto& review : pr.reviews()) {
            if (review.reviewer != pr.author() &&
                repository.isMember(review.reviewer)) {
                latestReviews[review.reviewer] = review;
            }
        }

        for (const auto& [reviewer, review] : latestReviews) {
            if (review.state == ReviewState::Approved) {
                ++decision.effectiveApprovals;
            }
        }

        if (!bypass &&
            decision.effectiveApprovals < policy->requiredApprovals) {
            decision.reasons.push_back(
                "Required approvals: " +
                std::to_string(policy->requiredApprovals) +
                ", effective approvals: " +
                std::to_string(decision.effectiveApprovals)
            );
        }

        const bool blockingReview = std::any_of(
            latestReviews.begin(),
            latestReviews.end(),
            [](const auto& pair) {
                return pair.second.state == ReviewState::ChangesRequested;
            }
        );

        if (!bypass && blockingReview) {
            decision.reasons.push_back(
                "An effective changes-requested review blocks merging."
            );
        }

        for (const auto& required : policy->requiredChecks) {
            auto check = pr.checks().find(required);

            if (check == pr.checks().end() ||
                check->second.state != CheckState::Success) {
                decision.reasons.push_back(
                    "Required status check is missing or unsuccessful: " +
                    required
                );
            }
        }

        if (!bypass &&
            policy->requireResolvedConversations &&
            pr.hasUnresolvedComments()) {
            decision.reasons.push_back(
                "Unresolved review conversations remain."
            );
        }

        if (!bypass &&
            policy->requireLinearHistory &&
            strategy == MergeStrategy::MergeCommit) {
            decision.reasons.push_back(
                "Linear-history policy rejects merge commits."
            );
        }

        decision.eligible = decision.reasons.empty();
        return decision;
    }

    static std::string merge(
        Repository& repository,
        PullRequest& pr,
        MergeStrategy strategy,
        const std::string& actor
    ) {
        MergeDecision decision =
            evaluate(repository, pr, strategy, actor);

        if (!decision.eligible) {
            std::string message;
            for (const auto& reason : decision.reasons) {
                if (!message.empty()) {
                    message += "; ";
                }
                message += reason;
            }
            throw MergeRejected(message);
        }

        Branch& target = repository.branch(pr.target());
        const Branch& source = repository.branch(pr.source());

        if (source.commits.empty()) {
            throw MergeRejected("Source branch has no commits.");
        }

        std::string newHead;

        if (strategy == MergeStrategy::Squash) {
            newHead = "squash-" + std::to_string(pr.number()) + "-" +
                      source.commits.back();
            target.commits.push_back(newHead);
        } else if (strategy == MergeStrategy::Rebase) {
            target.commits.insert(
                target.commits.end(),
                source.commits.begin(),
                source.commits.end()
            );
            newHead = target.commits.back();
        } else if (strategy == MergeStrategy::MergeCommit) {
            newHead = "merge-" + std::to_string(pr.number()) + "-" +
                      source.commits.back();
            target.commits.push_back(newHead);
        }

        pr.markMerged(strategy);
        return newHead;
    }
};

std::chrono::system_clock::time_point now() {
    return std::chrono::system_clock::now();
}

int main() {
    try {
        Repository repository("payments-api");

        for (const std::string& member :
             {"alice", "bob", "carol", "david"}) {
            repository.addMember(member);
        }

        repository.addBranch(
            Branch{"main", true, {"root-001"}}
        );

        repository.addBranch(
            Branch{
                "feature/payment-timeout",
                false,
                {"root-001", "commit-101"}
            }
        );

        repository.protectBranch(
            BranchProtection{
                "main",
                2,
                {"unit-tests", "security-scan"},
                true,
                true,
                {MergeStrategy::Squash, MergeStrategy::Rebase},
                {"platform-admin"}
            }
        );

        PullRequest& pr = repository.createPullRequest(
            "Enforce payment timeout validation",
            "feature/payment-timeout",
            "main",
            "alice",
            true
        );

        pr.addCommit(
            Commit{
                "commit-102",
                "Validate payment timeout configuration",
                "alice",
                {"commit-101"}
            }
        );

        pr.submit();

        pr.addReview(
            Review{1, "bob", ReviewState::Approved, now()}
        );

        pr.addReview(
            Review{2, "carol", ReviewState::Approved, now()}
        );

        pr.addComment(
            ReviewComment{
                1,
                "bob",
                "src/payment.cpp",
                42,
                "Document the timeout boundary.",
                false
            }
        );

        pr.setCheck(
            StatusCheck{
                "unit-tests",
                CheckState::Success,
                "248 tests passed"
            }
        );

        pr.setCheck(
            StatusCheck{
                "security-scan",
                CheckState::Success,
                "No high severity findings"
            }
        );

        MergeDecision beforeResolution =
            MergeEligibilityEngine::evaluate(
                repository,
                pr,
                MergeStrategy::Squash,
                "alice"
            );

        std::cout << "Before conversation resolution: "
                  << std::boolalpha
                  << beforeResolution.eligible << "\n";

        for (const auto& reason : beforeResolution.reasons) {
            std::cout << "  - " << reason << "\n";
        }

        pr.resolveComment(1);

        MergeDecision finalDecision =
            MergeEligibilityEngine::evaluate(
                repository,
                pr,
                MergeStrategy::Squash,
                "alice"
            );

        std::cout << "\nAfter resolution: "
                  << finalDecision.eligible << "\n";
        std::cout << "Effective approvals: "
                  << finalDecision.effectiveApprovals << "\n";

        const std::string mergedHead =
            MergeEligibilityEngine::merge(
                repository,
                pr,
                MergeStrategy::Squash,
                "alice"
            );

        std::cout << "\nPull request state: "
                  << to_string(pr.state()) << "\n";
        std::cout << "Merge strategy: "
                  << to_string(MergeStrategy::Squash) << "\n";
        std::cout << "New main head: "
                  << mergedHead << "\n";

        if (pr.state() != PullRequestState::Merged) {
            throw std::logic_error("Postcondition failed.");
        }

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Execution failed: "
                  << error.what() << "\n";
        return 1;
    }
}
