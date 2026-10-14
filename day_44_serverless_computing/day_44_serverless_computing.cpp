#include <algorithm>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

enum class EventType {
    HttpRequest,
    OrderCreated,
    FileUploaded,
    Timer
};

string eventTypeName(EventType type) {
    switch (type) {
        case EventType::HttpRequest:
            return "HTTP_REQUEST";
        case EventType::OrderCreated:
            return "ORDER_CREATED";
        case EventType::FileUploaded:
            return "FILE_UPLOADED";
        case EventType::Timer:
            return "TIMER";
    }

    return "UNKNOWN";
}

struct Event {
    string id;
    EventType type;
    map<string, string> payload;
};

struct Metrics {
    long long invocations = 0;
    long long failures = 0;
    double totalDurationMs = 0.0;

    double averageDurationMs() const {
        if (invocations == 0) {
            return 0.0;
        }

        return totalDurationMs / static_cast<double>(invocations);
    }
};

class ServerlessFunction {
private:
    string name_;
    int timeoutMs_;
    int memoryMb_;
    bool warm_ = false;
    Metrics metrics_;

    function<string(const Event&)> handler_;

public:
    ServerlessFunction(
        string name,
        function<string(const Event&)> handler,
        int timeoutMs = 3000,
        int memoryMb = 256
    )
        : name_(move(name)),
          timeoutMs_(timeoutMs),
          memoryMb_(memoryMb),
          handler_(move(handler)) {
        if (timeoutMs_ <= 0 || memoryMb_ <= 0) {
            throw invalid_argument("Invalid function configuration");
        }
    }

    string invoke(const Event& event) {
        const auto started = chrono::steady_clock::now();
        metrics_.invocations++;

        try {
            bool coldStart = !warm_;

            if (!warm_) {
                // The first invocation models runtime initialization overhead.
                this_thread::sleep_for(chrono::milliseconds(20));
                warm_ = true;
            }

            string result = handler_(event);

            const auto ended = chrono::steady_clock::now();
            const double elapsed =
                chrono::duration<double, milli>(ended - started).count();

            if (elapsed > timeoutMs_) {
                metrics_.failures++;
                throw runtime_error(
                    "Function exceeded configured timeout: " + name_
                );
            }

            metrics_.totalDurationMs += elapsed;

            return result + " | cold_start=" +
                   (coldStart ? "true" : "false");
        }
        catch (...) {
            metrics_.failures++;

            const auto ended = chrono::steady_clock::now();
            metrics_.totalDurationMs +=
                chrono::duration<double, milli>(ended - started).count();

            throw;
        }
    }

    const string& name() const {
        return name_;
    }

    const Metrics& metrics() const {
        return metrics_;
    }
};

class RepositoryGovernanceEngine {
private:
    struct BranchPolicy {
        int requiredApprovals;
        set<string> requiredChecks;
        bool restrictDirectPush;
        bool restrictForcePush;
        bool requireLinearHistory;
    };

    struct PullRequest {
        int number;
        string sourceBranch;
        string targetBranch;
        bool draft;
        bool mergeable;
        bool closed;
        bool approvalsStale;

        set<string> approvals;
        set<string> completedChecks;
    };

    map<string, BranchPolicy> protectedBranches_;
    map<int, PullRequest> pullRequests_;

public:
    void protectBranch(
        const string& branch,
        BranchPolicy policy
    ) {
        protectedBranches_[branch] = move(policy);
    }

    void addPullRequest(PullRequest pr) {
        if (pr.sourceBranch.empty() || pr.targetBranch.empty()) {
            throw invalid_argument("Pull Request branches cannot be empty");
        }

        if (pr.sourceBranch == pr.targetBranch) {
            throw invalid_argument(
                "Source and target branches must differ"
            );
        }

        pullRequests_[pr.number] = move(pr);
    }

    void addApproval(int number, const string& reviewer) {
        auto& pr = getPullRequest(number);

        if (pr.closed) {
            throw logic_error("Cannot approve a closed Pull Request");
        }

        if (reviewer.empty()) {
            throw invalid_argument("Reviewer identity is required");
        }

        pr.approvals.insert(reviewer);
    }

    void markApprovalStale(int number) {
        getPullRequest(number).approvalsStale = true;
    }

    void completeCheck(int number, const string& check) {
        getPullRequest(number).completedChecks.insert(check);
    }

    vector<string> mergeBlockers(int number) const {
        const auto& pr = getPullRequest(number);
        vector<string> blockers;

        if (pr.closed) {
            blockers.push_back("Pull Request is closed");
        }

        if (pr.draft) {
            blockers.push_back("Pull Request is still a draft");
        }

        if (!pr.mergeable) {
            blockers.push_back("Pull Request has unresolved conflicts");
        }

        if (pr.approvalsStale) {
            blockers.push_back("Required approvals are stale");
        }

        const auto policyIt =
            protectedBranches_.find(pr.targetBranch);

        if (policyIt == protectedBranches_.end()) {
            return blockers;
        }

        const auto& policy = policyIt->second;

        if (
            static_cast<int>(pr.approvals.size()) <
            policy.requiredApprovals
        ) {
            blockers.push_back(
                "Required approval count has not been reached"
            );
        }

        for (const auto& required : policy.requiredChecks) {
            if (!pr.completedChecks.contains(required)) {
                blockers.push_back(
                    "Required status check missing: " + required
                );
            }
        }

        return blockers;
    }

    bool canMerge(int number) const {
        return mergeBlockers(number).empty();
    }

    void printDecision(int number) const {
        const auto& pr = getPullRequest(number);

        cout << "\nPull Request #" << pr.number
             << " " << pr.sourceBranch
             << " -> " << pr.targetBranch << '\n';

        const auto blockers = mergeBlockers(number);

        if (blockers.empty()) {
            cout << "Merge eligibility: APPROVED\n";
        }
        else {
            cout << "Merge eligibility: BLOCKED\n";

            for (const auto& blocker : blockers) {
                cout << "  " << blocker << '\n';
            }
        }
    }

private:
    PullRequest& getPullRequest(int number) {
        auto it = pullRequests_.find(number);

        if (it == pullRequests_.end()) {
            throw out_of_range("Pull Request does not exist");
        }

        return it->second;
    }

    const PullRequest& getPullRequest(int number) const {
        auto it = pullRequests_.find(number);

        if (it == pullRequests_.end()) {
            throw out_of_range("Pull Request does not exist");
        }

        return it->second;
    }
};

class AutoScaler {
private:
    int minimum_;
    int maximum_;
    int targetConcurrency_;

public:
    AutoScaler(
        int minimum,
        int maximum,
        int targetConcurrency
    )
        : minimum_(minimum),
          maximum_(maximum),
          targetConcurrency_(targetConcurrency) {
        if (
            minimum < 0 ||
            maximum < minimum ||
            targetConcurrency <= 0
        ) {
            throw invalid_argument("Invalid autoscaling policy");
        }
    }

    int desiredInstances(int queuedEvents) const {
        if (queuedEvents <= 0) {
            return minimum_;
        }

        const int desired =
            (queuedEvents + targetConcurrency_ - 1) /
            targetConcurrency_;

        return min(
            maximum_,
            max(minimum_, desired)
        );
    }
};

string httpHandler(const Event& event) {
    auto method = event.payload.find("method");
    auto path = event.payload.find("path");

    if (method == event.payload.end()) {
        throw invalid_argument("HTTP method is missing");
    }

    if (path == event.payload.end() ||
        path->second.empty() ||
        path->second.front() != '/') {
        throw invalid_argument("Invalid HTTP path");
    }

    return "HTTP request accepted: " + method->second +
           " " + path->second;
}

string orderHandler(const Event& event) {
    auto customer = event.payload.find("customer");
    auto amount = event.payload.find("amount");

    if (customer == event.payload.end() ||
        amount == event.payload.end()) {
        throw invalid_argument("Incomplete order event");
    }

    return "Order accepted for customer " +
           customer->second +
           " amount=" +
           amount->second;
}

int main() {
    cout << fixed << setprecision(2);

    cout << "=== Serverless Function Execution ===\n";

    ServerlessFunction httpFunction(
        "http-api",
        httpHandler,
        3000,
        256
    );

    Event request{
        "evt-1001",
        EventType::HttpRequest,
        {
            {"method", "GET"},
            {"path", "/api/orders"}
        }
    };

    cout << httpFunction.invoke(request) << '\n';

    cout << "\n=== Event-Driven Order Processing ===\n";

    ServerlessFunction orderFunction(
        "order-processor",
        orderHandler
    );

    Event orderEvent{
        "evt-2001",
        EventType::OrderCreated,
        {
            {"customer", "customer-42"},
            {"amount", "1499.50"}
        }
    };

    cout << orderFunction.invoke(orderEvent) << '\n';

    cout << "\n=== Idempotency Registry ===\n";

    unordered_map<string, string> processedEvents;

    auto processIdempotently =
        [&](const Event& event) -> string {
            auto existing = processedEvents.find(event.id);

            if (existing != processedEvents.end()) {
                return "Duplicate event; returning cached result";
            }

            string result = orderFunction.invoke(event);
            processedEvents[event.id] = result;

            return result;
        };

    cout << processIdempotently(orderEvent) << '\n';
    cout << processIdempotently(orderEvent) << '\n';

    cout << "\n=== Repository Governance Case Study ===\n";

    RepositoryGovernanceEngine governance;

    governance.protectBranch(
        "main",
        {
            2,
            {"build", "unit-tests", "security-scan"},
            true,
            true,
            true
        }
    );

    governance.addPullRequest(
        {
            42,
            "feature/payment-validation",
            "main",
            false,
            true,
            false,
            false,
            {"alice"},
            {"build", "unit-tests"}
        }
    );

    governance.printDecision(42);

    governance.addApproval(42, "bob");
    governance.completeCheck(42, "security-scan");

    governance.printDecision(42);

    governance.markApprovalStale(42);

    governance.printDecision(42);

    cout << "\n=== Scaling Decision ===\n";

    AutoScaler scaler(0, 8, 4);

    for (int queued : {0, 1, 4, 5, 12, 25, 100}) {
        cout
            << "queued=" << queued
            << " instances="
            << scaler.desiredInstances(queued)
            << '\n';
    }

    cout << "\n=== Function Metrics ===\n";

    const auto& metrics = orderFunction.metrics();

    cout << "Function: "
         << orderFunction.name()
         << '\n';

    cout << "Invocations: "
         << metrics.invocations
         << '\n';

    cout << "Failures: "
         << metrics.failures
         << '\n';

    cout << "Average duration: "
         << metrics.averageDurationMs()
         << " ms\n";

    return 0;
}
