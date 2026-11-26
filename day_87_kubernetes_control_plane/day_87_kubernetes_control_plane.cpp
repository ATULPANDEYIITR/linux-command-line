#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

// ============================================================
// 1. DOMAIN ENUMERATIONS
// ============================================================

enum class PodPhase {
    Pending,
    Running,
    Failed,
    Succeeded
};

enum class NodeStatus {
    Ready,
    NotReady,
    Unknown
};

enum class ComponentStatus {
    Healthy,
    Degraded,
    Unavailable
};

enum class CheckStatus {
    Pending,
    Passing,
    Failing
};

enum class OperationStatus {
    Accepted,
    Rejected,
    Completed
};

string toString(PodPhase phase) {
    switch (phase) {
        case PodPhase::Pending: return "Pending";
        case PodPhase::Running: return "Running";
        case PodPhase::Failed: return "Failed";
        case PodPhase::Succeeded: return "Succeeded";
    }

    throw logic_error("Unknown pod phase");
}

string toString(NodeStatus status) {
    switch (status) {
        case NodeStatus::Ready: return "Ready";
        case NodeStatus::NotReady: return "NotReady";
        case NodeStatus::Unknown: return "Unknown";
    }

    throw logic_error("Unknown node status");
}

string toString(ComponentStatus status) {
    switch (status) {
        case ComponentStatus::Healthy: return "Healthy";
        case ComponentStatus::Degraded: return "Degraded";
        case ComponentStatus::Unavailable: return "Unavailable";
    }

    throw logic_error("Unknown component status");
}

// ============================================================
// 2. DOMAIN STRUCTURES
// ============================================================

struct Container {
    string name;
    string image;
    int cpuRequest;
    int memoryRequest;

    void validate() const {
        if (name.empty() || image.empty()) {
            throw invalid_argument(
                "Container name and image are required"
            );
        }

        if (cpuRequest <= 0 || memoryRequest <= 0) {
            throw invalid_argument(
                "Container resource requests must be positive"
            );
        }
    }
};

struct Pod {
    string name;
    string namespaceName;
    string uid;
    vector<Container> containers;
    PodPhase phase = PodPhase::Pending;
    optional<string> assignedNode;
    int restartCount = 0;

    int cpuRequest() const {
        return accumulate(
            containers.begin(),
            containers.end(),
            0,
            [](int total, const Container& container) {
                return total + container.cpuRequest;
            }
        );
    }

    int memoryRequest() const {
        return accumulate(
            containers.begin(),
            containers.end(),
            0,
            [](int total, const Container& container) {
                return total + container.memoryRequest;
            }
        );
    }

    void validate() const {
        if (name.empty() || namespaceName.empty()) {
            throw invalid_argument("Invalid pod metadata");
        }

        if (containers.empty()) {
            throw invalid_argument("Pod must contain a container");
        }

        set<string> names;

        for (const auto& container : containers) {
            container.validate();

            if (!names.insert(container.name).second) {
                throw invalid_argument("Duplicate container name");
            }
        }

        if (cpuRequest() <= 0 || memoryRequest() <= 0) {
            throw invalid_argument("Invalid aggregate resources");
        }
    }
};

struct Node {
    string name;
    int cpuCapacity;
    int memoryCapacity;
    int cpuAllocated = 0;
    int memoryAllocated = 0;
    NodeStatus status = NodeStatus::Ready;

    int availableCPU() const {
        return cpuCapacity - cpuAllocated;
    }

    int availableMemory() const {
        return memoryCapacity - memoryAllocated;
    }

    bool canHost(const Pod& pod) const {
        return status == NodeStatus::Ready &&
               availableCPU() >= pod.cpuRequest() &&
               availableMemory() >= pod.memoryRequest();
    }

    void allocate(const Pod& pod) {
        if (!canHost(pod)) {
            throw runtime_error("Node cannot accommodate pod");
        }

        cpuAllocated += pod.cpuRequest();
        memoryAllocated += pod.memoryRequest();
    }

    void release(const Pod& pod) {
        if (cpuAllocated < pod.cpuRequest() ||
            memoryAllocated < pod.memoryRequest()) {
            throw logic_error("Invalid node resource accounting");
        }

        cpuAllocated -= pod.cpuRequest();
        memoryAllocated -= pod.memoryRequest();
    }

    void validate() const {
        if (name.empty() ||
            cpuCapacity <= 0 ||
            memoryCapacity <= 0 ||
            cpuAllocated < 0 ||
            memoryAllocated < 0 ||
            cpuAllocated > cpuCapacity ||
            memoryAllocated > memoryCapacity) {
            throw invalid_argument("Invalid node configuration");
        }
    }
};

struct StatusCheck {
    string name;
    CheckStatus status;
    string message;
};

struct ControlPlaneComponent {
    string name;
    string version;
    ComponentStatus status;
    long long lastHeartbeat;
};

struct ClusterEvent {
    long long timestamp;
    string resource;
    string type;
    string message;
};

struct SchedulingResult {
    string pod;
    string node;
    bool successful;
    string reason;
};

// ============================================================
// 3. VERSIONED STATE STORE
// ============================================================

class VersionedStore {
private:
    struct Entry {
        string value;
        unsigned long long revision;
    };

    unordered_map<string, Entry> records;
    unsigned long long globalRevision = 0;

public:
    unsigned long long revision() const {
        return globalRevision;
    }

    unsigned long long put(
        const string& key,
        const string& value,
        optional<unsigned long long> expected = nullopt
    ) {
        if (key.empty() || key.front() != '/') {
            throw invalid_argument("Invalid storage key");
        }

        auto iterator = records.find(key);

        unsigned long long actual =
            iterator == records.end() ? 0 : iterator->second.revision;

        if (expected.has_value() && expected.value() != actual) {
            throw runtime_error("Optimistic concurrency conflict");
        }

        unsigned long long nextRevision = ++globalRevision;

        records[key] = {
            value,
            nextRevision
        };

        return nextRevision;
    }

    pair<string, unsigned long long> get(
        const string& key
    ) const {
        auto iterator = records.find(key);

        if (iterator == records.end()) {
            throw out_of_range("Resource not found");
        }

        return {
            iterator->second.value,
            iterator->second.revision
        };
    }

    bool exists(const string& key) const {
        return records.find(key) != records.end();
    }

    void erase(const string& key) {
        if (records.erase(key) == 0) {
            throw out_of_range("Resource not found");
        }

        ++globalRevision;
    }

    vector<pair<string, string>> list(
        const string& prefix
    ) const {
        vector<pair<string, string>> result;

        for (const auto& [key, entry] : records) {
            if (key.compare(0, prefix.size(), prefix) == 0) {
                result.emplace_back(key, entry.value);
            }
        }

        sort(result.begin(), result.end());

        return result;
    }
};

// ============================================================
// 4. API SERVER
// ============================================================

class APIServer {
private:
    VersionedStore& store;
    vector<ClusterEvent> events;

    string podKey(const Pod& pod) const {
        return "/registry/pods/" +
               pod.namespaceName + "/" + pod.name;
    }

public:
    explicit APIServer(VersionedStore& storage)
        : store(storage) {}

    void createPod(const Pod& pod) {
        pod.validate();

        string key = podKey(pod);

        if (store.exists(key)) {
            throw runtime_error("Pod already exists");
        }

        store.put(key, pod.uid);

        events.push_back({
            currentTime(),
            pod.name,
            "Created",
            "Pod accepted by API server"
        });
    }

    void updatePod(const Pod& pod) {
        pod.validate();

        string key = podKey(pod);

        auto current = store.get(key);

        store.put(
            key,
            pod.uid + ":" + toString(pod.phase),
            current.second
        );

        events.push_back({
            currentTime(),
            pod.name,
            "Updated",
            "Pod state persisted"
        });
    }

    bool exists(const Pod& pod) const {
        return store.exists(podKey(pod));
    }

    vector<ClusterEvent> getEvents() const {
        return events;
    }

    static long long currentTime() {
        return chrono::duration_cast<chrono::milliseconds>(
            chrono::system_clock::now().time_since_epoch()
        ).count();
    }
};

// ============================================================
// 5. SCHEDULING ENGINE
// ============================================================

class SchedulingEngine {
private:
    vector<Node>& nodes;
    APIServer& apiServer;

    int calculateScore(const Node& node, const Pod& pod) const {
        // Lower remaining CPU after placement receives a higher
        // best-fit preference.
        int remainingCPU = node.availableCPU() - pod.cpuRequest();
        int remainingMemory =
            node.availableMemory() - pod.memoryRequest();

        return remainingCPU * 1000 + remainingMemory;
    }

public:
    SchedulingEngine(
        vector<Node>& clusterNodes,
        APIServer& api
    ) : nodes(clusterNodes), apiServer(api) {}

    SchedulingResult schedule(Pod& pod) {
        if (pod.phase != PodPhase::Pending) {
            return {
                pod.name,
                "",
                false,
                "Pod is not pending"
            };
        }

        vector<size_t> feasible;

        for (size_t i = 0; i < nodes.size(); ++i) {
            if (nodes[i].canHost(pod)) {
                feasible.push_back(i);
            }
        }

        if (feasible.empty()) {
            return {
                pod.name,
                "",
                false,
                "No feasible node"
            };
        }

        auto best = min_element(
            feasible.begin(),
            feasible.end(),
            [&](size_t a, size_t b) {
                int scoreA = calculateScore(nodes[a], pod);
                int scoreB = calculateScore(nodes[b], pod);

                if (scoreA != scoreB) {
                    return scoreA < scoreB;
                }

                return nodes[a].name < nodes[b].name;
            }
        );

        Node& selected = nodes[*best];

        selected.allocate(pod);
        pod.assignedNode = selected.name;
        pod.phase = PodPhase::Running;

        try {
            apiServer.updatePod(pod);
        } catch (...) {
            selected.release(pod);
            pod.assignedNode.reset();
            pod.phase = PodPhase::Pending;
            throw;
        }

        return {
            pod.name,
            selected.name,
            true,
            "Pod successfully scheduled"
        };
    }
};

// ============================================================
// 6. CONTROLLER RECONCILIATION
// ============================================================

struct Deployment {
    string name;
    string namespaceName;
    string image;
    int desiredReplicas;
    int cpuRequest;
    int memoryRequest;

    void validate() const {
        if (name.empty() ||
            namespaceName.empty() ||
            image.empty() ||
            desiredReplicas < 0 ||
            cpuRequest <= 0 ||
            memoryRequest <= 0) {
            throw invalid_argument("Invalid deployment specification");
        }
    }
};

class DeploymentController {
private:
    APIServer& apiServer;
    int sequence = 0;

public:
    explicit DeploymentController(APIServer& api)
        : apiServer(api) {}

    vector<Pod> reconcile(
        const Deployment& deployment,
        const vector<Pod>& observed
    ) {
        deployment.validate();

        vector<Pod> managed;

        for (const auto& pod : observed) {
            if (pod.namespaceName == deployment.namespaceName &&
                pod.name.compare(
                    0,
                    deployment.name.size() + 1,
                    deployment.name + "-"
                ) == 0) {
                managed.push_back(pod);
            }
        }

        while (static_cast<int>(managed.size()) <
               deployment.desiredReplicas) {

            Pod pod;

            pod.name = deployment.name + "-" +
                       to_string(sequence++);

            pod.namespaceName = deployment.namespaceName;
            pod.uid = "pod-" + to_string(sequence);

            pod.containers.push_back({
                "application",
                deployment.image,
                deployment.cpuRequest,
                deployment.memoryRequest
            });

            pod.validate();
            apiServer.createPod(pod);

            managed.push_back(pod);
        }

        return managed;
    }
};

// ============================================================
// 7. REPOSITORY-LIKE CONTROL PLANE POLICY ENGINE
// ============================================================

struct ControlPlanePolicy {
    bool requireAPIServerAvailable = true;
    bool requireSchedulerAvailable = true;
    bool requireEtcdAvailable = true;
    bool requireControllerAvailable = true;
    bool requireNodeReady = true;
    bool allowDegradedOperation = false;
    int minimumReadyNodes = 1;
};

struct EvaluationResult {
    bool accepted;
    vector<string> violations;
};

class GovernanceEngine {
private:
    ControlPlanePolicy policy;

public:
    explicit GovernanceEngine(ControlPlanePolicy p)
        : policy(p) {}

    EvaluationResult evaluate(
        const vector<ControlPlaneComponent>& components,
        const vector<Node>& nodes
    ) const {
        EvaluationResult result{true, {}};

        map<string, ComponentStatus> statusByName;

        for (const auto& component : components) {
            statusByName[component.name] = component.status;
        }

        const vector<pair<string, bool>> requirements = {
            {"kube-apiserver", policy.requireAPIServerAvailable},
            {"kube-scheduler", policy.requireSchedulerAvailable},
            {"kube-controller-manager", policy.requireControllerAvailable},
            {"etcd", policy.requireEtcdAvailable}
        };

        for (const auto& [name, required] : requirements) {
            if (!required) {
                continue;
            }

            auto it = statusByName.find(name);

            if (it == statusByName.end()) {
                result.violations.push_back(
                    "Missing control plane component: " + name
                );
                continue;
            }

            if (it->second == ComponentStatus::Unavailable) {
                result.violations.push_back(
                    "Unavailable component: " + name
                );
            } else if (
                it->second == ComponentStatus::Degraded &&
                !policy.allowDegradedOperation
            ) {
                result.violations.push_back(
                    "Degraded component: " + name
                );
            }
        }

        int readyNodes = static_cast<int>(
            count_if(
                nodes.begin(),
                nodes.end(),
                [](const Node& node) {
                    return node.status == NodeStatus::Ready;
                }
            )
        );

        if (readyNodes < policy.minimumReadyNodes) {
            result.violations.push_back(
                "Insufficient ready worker nodes"
            );
        }

        if (policy.requireNodeReady) {
            for (const auto& node : nodes) {
                if (node.status == NodeStatus::NotReady) {
                    result.violations.push_back(
                        "Node is not ready: " + node.name
                    );
                }
            }
        }

        result.accepted = result.violations.empty();

        return result;
    }
};

// ============================================================
// 8. CLUSTER MONITOR
// ============================================================

class ClusterMonitor {
private:
    vector<ControlPlaneComponent> components;

public:
    void registerComponent(const string& name, const string& version) {
        auto it = find_if(
            components.begin(),
            components.end(),
            [&](const ControlPlaneComponent& component) {
                return component.name == name;
            }
        );

        if (it != components.end()) {
            throw runtime_error("Component already registered");
        }

        components.push_back({
            name,
            version,
            ComponentStatus::Healthy,
            APIServer::currentTime()
        });
    }

    void heartbeat(const string& name) {
        auto it = find_if(
            components.begin(),
            components.end(),
            [&](const ControlPlaneComponent& component) {
                return component.name == name;
            }
        );

        if (it == components.end()) {
            throw out_of_range("Component not found");
        }

        it->lastHeartbeat = APIServer::currentTime();
        it->status = ComponentStatus::Healthy;
    }

    void markUnavailable(const string& name) {
        auto it = find_if(
            components.begin(),
            components.end(),
            [&](const ControlPlaneComponent& component) {
                return component.name == name;
            }
        );

        if (it == components.end()) {
            throw out_of_range("Component not found");
        }

        it->status = ComponentStatus::Unavailable;
    }

    const vector<ControlPlaneComponent>& getComponents() const {
        return components;
    }
};

// ============================================================
// 9. LEADER ELECTION
// ============================================================

class LeaderElection {
private:
    string holder;
    long long renewedAt = 0;
    long long leaseDuration;

public:
    explicit LeaderElection(long long duration = 15000)
        : leaseDuration(duration) {
        if (duration <= 0) {
            throw invalid_argument("Invalid lease duration");
        }
    }

    bool acquire(const string& candidate) {
        if (candidate.empty()) {
            throw invalid_argument("Candidate identity required");
        }

        long long now = APIServer::currentTime();

        bool expired = holder.empty() ||
                       now - renewedAt >= leaseDuration;

        if (expired || holder == candidate) {
            holder = candidate;
            renewedAt = now;
            return true;
        }

        return false;
    }

    bool isLeader(const string& candidate) const {
        return holder == candidate &&
               APIServer::currentTime() - renewedAt < leaseDuration;
    }
};

// ============================================================
// 10. EXECUTABLE CONTROL PLANE SCENARIO
// ============================================================

void printEvaluation(const EvaluationResult& result) {
    cout << "Governance result: "
         << (result.accepted ? "ACCEPTED" : "REJECTED")
         << '\n';

    for (const auto& violation : result.violations) {
        cout << "  - " << violation << '\n';
    }
}

int main() {
    try {
        VersionedStore etcd;
        APIServer apiServer(etcd);

        vector<Node> nodes = {
            {"worker-01", 8, 2048},
            {"worker-02", 4, 1024},
            {"worker-03", 8, 4096}
        };

        for (const auto& node : nodes) {
            node.validate();
        }

        ClusterMonitor monitor;

        monitor.registerComponent("kube-apiserver", "v1.32.0");
        monitor.registerComponent("kube-scheduler", "v1.32.0");
        monitor.registerComponent(
            "kube-controller-manager",
            "v1.32.0"
        );
        monitor.registerComponent("etcd", "3.5.17");

        LeaderElection election(15000);

        if (!election.acquire("controller-01")) {
            throw runtime_error("Leader election failed");
        }

        if (!election.isLeader("controller-01")) {
            throw runtime_error("Leadership verification failed");
        }

        Deployment deployment{
            "web",
            "production",
            "nginx:1.27",
            3,
            1,
            256
        };

        DeploymentController controller(apiServer);

        vector<Pod> observed;

        vector<Pod> desired = controller.reconcile(
            deployment,
            observed
        );

        SchedulingEngine scheduler(nodes, apiServer);

        vector<SchedulingResult> schedulingResults;

        for (auto& pod : desired) {
            schedulingResults.push_back(
                scheduler.schedule(pod)
            );
        }

        cout << "\nSCHEDULING RESULTS\n";

        for (const auto& result : schedulingResults) {
            cout << result.pod << " -> ";

            if (result.successful) {
                cout << result.node;
            } else {
                cout << result.reason;
            }

            cout << '\n';
        }

        ControlPlanePolicy policy;

        policy.minimumReadyNodes = 2;
        policy.allowDegradedOperation = false;

        GovernanceEngine governance(policy);

        cout << "\nINITIAL GOVERNANCE EVALUATION\n";

        auto initial = governance.evaluate(
            monitor.getComponents(),
            nodes
        );

        printEvaluation(initial);

        if (!initial.accepted) {
            throw runtime_error("Healthy cluster rejected");
        }

        // Simulate an etcd outage.
        monitor.markUnavailable("etcd");

        cout << "\nFAILURE SCENARIO: ETCD UNAVAILABLE\n";

        auto failed = governance.evaluate(
            monitor.getComponents(),
            nodes
        );

        printEvaluation(failed);

        if (failed.accepted) {
            throw runtime_error("Etcd failure was not detected");
        }

        // Simulate recovery.
        monitor.heartbeat("etcd");

        cout << "\nRECOVERY SCENARIO\n";

        auto recovered = governance.evaluate(
            monitor.getComponents(),
            nodes
        );

        printEvaluation(recovered);

        if (!recovered.accepted) {
            throw runtime_error("Cluster recovery failed");
        }

        // Test unschedulable pod.
        Pod oversized{
            "oversized",
            "production",
            "pod-oversized",
            {
                {"application", "large-image", 100, 100000}
            }
        };

        auto rejected = scheduler.schedule(oversized);

        cout << "\nUNSCHEDULABLE POD\n";
        cout << rejected.reason << '\n';

        if (rejected.successful) {
            throw runtime_error("Oversized pod was scheduled");
        }

        cout << "\nETCD REVISION: "
             << etcd.revision() << '\n';

        cout << "\nALL CONTROL PLANE TESTS PASSED\n";

        return 0;

    } catch (const exception& error) {
        cerr << "CONTROL PLANE ERROR: "
             << error.what() << '\n';

        return 1;
    }
}
