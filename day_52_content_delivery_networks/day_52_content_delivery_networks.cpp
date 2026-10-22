#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <list>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Content {
    std::string path;
    std::string etag;
    std::string contentType;
    std::string cacheControl;
};

struct CacheEntry {
    Content content;
    std::int64_t expiresAt;
};

class LRUCache {
private:
    struct Node {
        std::string key;
        CacheEntry entry;
    };

    std::size_t capacity_;
    std::list<Node> items_;
    std::unordered_map<std::string, std::list<Node>::iterator> index_;

public:
    explicit LRUCache(std::size_t capacity)
        : capacity_(capacity) {
        if (capacity == 0) {
            throw std::invalid_argument("Cache capacity must be positive.");
        }
    }

    std::optional<CacheEntry> get(
        const std::string& key,
        std::int64_t now
    ) {
        auto found = index_.find(key);

        if (found == index_.end()) {
            return std::nullopt;
        }

        auto iterator = found->second;
        CacheEntry result = iterator->entry;

        items_.splice(items_.begin(), items_, iterator);
        index_[key] = items_.begin();

        return result;
    }

    bool isFresh(const CacheEntry& entry, std::int64_t now) const {
        return now < entry.expiresAt;
    }

    void put(
        const std::string& key,
        const Content& content,
        std::int64_t expiresAt
    ) {
        auto found = index_.find(key);

        if (found != index_.end()) {
            found->second->entry = {content, expiresAt};
            items_.splice(items_.begin(), items_, found->second);
            index_[key] = items_.begin();
            return;
        }

        items_.push_front({key, {content, expiresAt}});
        index_[key] = items_.begin();

        if (items_.size() > capacity_) {
            auto last = std::prev(items_.end());
            index_.erase(last->key);
            items_.pop_back();
        }
    }

    bool invalidate(const std::string& key) {
        auto found = index_.find(key);

        if (found == index_.end()) {
            return false;
        }

        items_.erase(found->second);
        index_.erase(found);
        return true;
    }

    std::vector<std::string> keys() const {
        std::vector<std::string> result;

        for (const auto& item : items_) {
            result.push_back(item.key);
        }

        return result;
    }
};

class OriginServer {
private:
    std::string name_;
    std::unordered_map<std::string, Content> objects_;

public:
    explicit OriginServer(std::string name)
        : name_(std::move(name)) {}

    void publish(Content content) {
        objects_[content.path] = std::move(content);
    }

    const Content& fetch(const std::string& path) const {
        auto found = objects_.find(path);

        if (found == objects_.end()) {
            throw std::runtime_error("Origin object not found: " + path);
        }

        return found->second;
    }
};

struct BranchPolicy {
    std::size_t requiredApprovals = 2;
    bool requirePassingChecks = true;
    bool requireResolvedConversations = true;
    bool blockDirectPush = true;
    bool blockForcePush = true;
    bool requireLinearHistory = false;
};

struct Review {
    std::string reviewer;
    bool approval;
    bool stale;
    bool dismissed;
    bool eligible;
    std::vector<std::string> comments;
};

struct PullRequest {
    std::string id;
    std::string sourceBranch;
    std::string targetBranch;
    std::string state;
    std::vector<std::string> commits;
    std::vector<Review> reviews;
    std::unordered_map<std::string, bool> statusChecks;
    std::size_t unresolvedConversations = 0;
    bool draft = false;
    bool mergeable = true;
};

class MergeEligibilityEngine {
public:
    static bool allRequiredChecksPass(const PullRequest& pr) {
        if (pr.statusChecks.empty()) {
            return false;
        }

        return std::all_of(
            pr.statusChecks.begin(),
            pr.statusChecks.end(),
            [](const auto& check) {
                return check.second;
            }
        );
    }

    static std::size_t activeApprovals(const PullRequest& pr) {
        std::size_t count = 0;

        for (const Review& review : pr.reviews) {
            if (
                review.approval &&
                review.eligible &&
                !review.stale &&
                !review.dismissed
            ) {
                ++count;
            }
        }

        return count;
    }

    static bool canMerge(
        const PullRequest& pr,
        const BranchPolicy& policy,
        std::string& reason
    ) {
        if (pr.draft) {
            reason = "Draft Pull Requests cannot be merged.";
            return false;
        }

        if (pr.state != "OPEN") {
            reason = "Pull Request is not open.";
            return false;
        }

        if (pr.sourceBranch == pr.targetBranch) {
            reason = "Source and target branches must differ.";
            return false;
        }

        if (pr.commits.empty()) {
            reason = "Pull Request contains no commits.";
            return false;
        }

        if (!pr.mergeable) {
            reason = "Merge conflicts must be resolved.";
            return false;
        }

        if (policy.requirePassingChecks && !allRequiredChecksPass(pr)) {
            reason = "Required status checks are not all passing.";
            return false;
        }

        if (
            policy.requireResolvedConversations &&
            pr.unresolvedConversations > 0
        ) {
            reason = "Unresolved review conversations remain.";
            return false;
        }

        const std::size_t approvals = activeApprovals(pr);

        if (approvals < policy.requiredApprovals) {
            reason = "Required approvals are missing.";
            return false;
        }

        reason = "All branch protection conditions are satisfied.";
        return true;
    }
};

void printEligibility(
    const PullRequest& pr,
    const BranchPolicy& policy
) {
    std::string reason;
    bool eligible = MergeEligibilityEngine::canMerge(pr, policy, reason);

    std::cout
        << std::left
        << std::setw(18) << pr.id
        << std::setw(10) << (eligible ? "ELIGIBLE" : "BLOCKED")
        << reason
        << '\n';
}

int main() {
    try {
        OriginServer origin("production-origin");

        origin.publish({
            "/assets/app.js",
            "etag-app-001",
            "application/javascript",
            "public, max-age=300"
        });

        LRUCache cache(2);

        constexpr std::int64_t now = 1'000;

        cache.put(
            "/assets/app.js",
            origin.fetch("/assets/app.js"),
            now + 300
        );

        auto cached = cache.get("/assets/app.js", now);

        if (cached && cache.isFresh(*cached, now)) {
            std::cout << "Edge cache HIT: "
                      << cached->content.path << '\n';
        }

        BranchPolicy productionPolicy;
        productionPolicy.requiredApprovals = 2;
        productionPolicy.requirePassingChecks = true;
        productionPolicy.requireResolvedConversations = true;
        productionPolicy.blockDirectPush = true;
        productionPolicy.blockForcePush = true;
        productionPolicy.requireLinearHistory = true;

        PullRequest approvedPr{
            "PR-1042",
            "feature/cdn-cache-policy",
            "main",
            "OPEN",
            {"a1", "a2", "a3"},
            {
                {"reviewer-alice", true, false, false, true, {}},
                {"reviewer-bob", true, false, false, true, {}}
            },
            {
                {"unit-tests", true},
                {"integration-tests", true},
                {"security-scan", true}
            },
            0,
            false,
            true
        };

        PullRequest staleApprovalPr = approvedPr;
        staleApprovalPr.id = "PR-1043";
        staleApprovalPr.reviews[1].stale = true;

        PullRequest failedCheckPr = approvedPr;
        failedCheckPr.id = "PR-1044";
        failedCheckPr.statusChecks["security-scan"] = false;

        PullRequest conflictPr = approvedPr;
        conflictPr.id = "PR-1045";
        conflictPr.mergeable = false;

        PullRequest conversationPr = approvedPr;
        conversationPr.id = "PR-1046";
        conversationPr.unresolvedConversations = 1;

        PullRequest draftPr = approvedPr;
        draftPr.id = "PR-1047";
        draftPr.draft = true;

        std::cout << "\nMerge eligibility engine\n";
        std::cout << std::string(90, '-') << '\n';

        printEligibility(approvedPr, productionPolicy);
        printEligibility(staleApprovalPr, productionPolicy);
        printEligibility(failedCheckPr, productionPolicy);
        printEligibility(conflictPr, productionPolicy);
        printEligibility(conversationPr, productionPolicy);
        printEligibility(draftPr, productionPolicy);

        std::cout << "\nActive approvals for PR-1042: "
                  << MergeEligibilityEngine::activeApprovals(approvedPr)
                  << '\n';

        std::cout << "\nEdge cache keys before invalidation: ";
        for (const auto& key : cache.keys()) {
            std::cout << key << ' ';
        }

        std::cout << '\n';

        cache.invalidate("/assets/app.js");

        std::cout << "Edge cache keys after invalidation: ";
        for (const auto& key : cache.keys()) {
            std::cout << key << ' ';
        }

        std::cout << '\n';

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}
