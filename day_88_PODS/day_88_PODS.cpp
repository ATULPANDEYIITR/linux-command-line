#include <algorithm>
#include <cassert>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * KUBERNETES POD SCHEDULING AND GOVERNANCE ENGINE
 *
 * C++17
 *
 * Implements:
 * - Pod and container domain models
 * - Resource requests and limits
 * - Node capacity management
 * - Resource-aware scheduling
 * - Init container execution
 * - Pod lifecycle transitions
 * - Readiness evaluation
 * - Restart policies
 * - Deployment replica reconciliation
 * - Rolling workload updates
 * - Cluster reporting
 *
 * This is an educational control-plane simulation.
 * It does not communicate with a Kubernetes cluster.
 */

namespace kube {

// ============================================================
// 1. ENUMERATIONS
// ============================================================

enum class PodPhase {
    Pending,
    Running,
    Succeeded,
    Failed,
    Unknown
};

enum class ContainerState {
    Waiting,
    Running,
    Terminated
};

enum class RestartPolicy {
    Always,
    OnFailure,
    Never
};

enum class WorkloadType {
    Deployment,
    Job,
    DaemonSet,
    StatefulSet
};

std::string toString(PodPhase phase) {
    switch (phase) {
        case PodPhase::Pending: return "Pending";
        case PodPhase::Running: return "Running";
        case PodPhase::Succeeded: return "Succeeded";
        case PodPhase::Failed: return "Failed";
        case PodPhase::Unknown: return "Unknown";
    }

    return "Unknown";
}

std::string toString(ContainerState state) {
    switch (state) {
        case ContainerState::Waiting: return "Waiting";
        case ContainerState::Running: return "Running";
        case ContainerState::Terminated: return "Terminated";
    }

    return "Unknown";
}

// ============================================================
// 2. RESOURCE REQUIREMENTS
// ============================================================

struct Resources {
    double cpuRequest = 0.1;
    double cpuLimit = 0.5;
    int memoryRequest = 128;
    int memoryLimit = 512;

    void validate() const {
        if (
            !std::isfinite(cpuRequest) ||
            !std::isfinite(cpuLimit) ||
            cpuRequest < 0 ||
            cpuLimit <= 0 ||
            cpuRequest > cpuLimit
        ) {
            throw std::invalid_argument(
                "Invalid CPU request or limit."
            );
        }

        if (
            memoryRequest < 0 ||
            memoryLimit <= 0 ||
            memoryRequest > memoryLimit
        ) {
            throw std::invalid_argument(
                "Invalid memory request or limit."
            );
        }
    }
};

// ============================================================
// 3. CONTAINER
// ============================================================

class Container {
private:
    std::string name_;
    std::string image_;
    Resources resources_;

    ContainerState state_ = ContainerState::Waiting;
    bool ready_ = false;
    int restartCount_ = 0;
    int exitCode_ = 0;

public:
    Container(
        std::string name,
        std::string image,
        Resources resources = {}
    )
        : name_(std::move(name)),
          image_(std::move(image)),
          resources_(resources) {

        if (name_.empty() || image_.empty()) {
            throw std::invalid_argument(
                "Container name and image are required."
            );
        }

        resources_.validate();
    }

    void start() {
        if (state_ == ContainerState::Running) {
            throw std::logic_error(
                "Container is already running."
            );
        }

        state_ = ContainerState::Running;
        ready_ = false;
    }

    void markReady() {
        if (state_ != ContainerState::Running) {
            throw std::logic_error(
                "Container must be running."
            );
        }

        ready_ = true;
    }

    void terminate(int exitCode) {
        if (state_ != ContainerState::Running) {
            throw std::logic_error(
                "Container is not running."
            );
        }

        state_ = ContainerState::Terminated;
        exitCode_ = exitCode;
        ready_ = false;
    }

    void restart() {
        ++restartCount_;
        state_ = ContainerState::Waiting;
        ready_ = false;
        exitCode_ = 0;
    }

    const std::string& name() const {
        return name_;
    }

    const std::string& image() const {
        return image_;
    }

    const Resources& resources() const {
        return resources_;
    }

    ContainerState state() const {
        return state_;
    }

    bool ready() const {
        return ready_;
    }

    int restartCount() const {
        return restartCount_;
    }

    int exitCode() const {
        return exitCode_;
    }
};

// ============================================================
// 4. NODE RESOURCE ALLOCATION
// ============================================================

struct ResourceRequest {
    double cpu = 0;
    int memory = 0;
};

class Node {
private:
    std::string name_;
    double cpuCapacity_;
    int memoryCapacity_;

    std::unordered_map<std::string, ResourceRequest> allocations_;

public:
    Node(
        std::string name,
        double cpuCapacity,
        int memoryCapacity
    )
        : name_(std::move(name)),
          cpuCapacity_(cpuCapacity),
          memoryCapacity_(memoryCapacity) {

        if (
            name_.empty() ||
            !std::isfinite(cpuCapacity_) ||
            cpuCapacity_ <= 0 ||
            memoryCapacity_ <= 0
        ) {
            throw std::invalid_argument(
                "Invalid node configuration."
            );
        }
    }

    ResourceRequest allocated() const {
        ResourceRequest total;

        for (const auto& [id, request] : allocations_) {
            total.cpu += request.cpu;
            total.memory += request.memory;
        }

        return total;
    }

    bool canFit(const ResourceRequest& request) const {
        const auto current = allocated();

        return (
            current.cpu + request.cpu <= cpuCapacity_ + 1e-9 &&
            current.memory + request.memory <= memoryCapacity_
        );
    }

    bool reserve(
        const std::string& podId,
        const ResourceRequest& request
    ) {
        if (allocations_.count(podId)) {
            throw std::logic_error(
                "Pod already has an allocation."
            );
        }

        if (!canFit(request)) {
            return false;
        }

        allocations_.emplace(podId, request);
        return true;
    }

    void release(const std::string& podId) {
        allocations_.erase(podId);
    }

    const std::string& name() const {
        return name_;
    }

    double cpuCapacity() const {
        return cpuCapacity_;
    }

    int memoryCapacity() const {
        return memoryCapacity_;
    }
};

// ============================================================
// 5. POD DOMAIN MODEL
// ============================================================

class Pod {
private:
    std::string id_;
    std::string name_;
    std::string namespace_;

    std::vector<Container> containers_;
    std::vector<Container> initContainers_;

    RestartPolicy restartPolicy_;
    PodPhase phase_ = PodPhase::Pending;

    std::string nodeName_;

    bool scheduled_ = false;
    bool initialized_ = false;
    bool containersReady_ = false;
    bool ready_ = false;

    std::vector<std::string> events_;

public:
    Pod(
        std::string id,
        std::string name,
        std::string namespaceName,
        std::vector<Container> containers,
        std::vector<Container> initContainers = {},
        RestartPolicy restartPolicy = RestartPolicy::Always
    )
        : id_(std::move(id)),
          name_(std::move(name)),
          namespace_(std::move(namespaceName)),
          containers_(std::move(containers)),
          initContainers_(std::move(initContainers)),
          restartPolicy_(restartPolicy) {

        if (
            id_.empty() ||
            name_.empty() ||
            namespace_.empty() ||
            containers_.empty()
        ) {
            throw std::invalid_argument(
                "Invalid Pod configuration."
            );
        }

        std::set<std::string> names;

        for (const auto& container : containers_) {
            if (!names.insert(container.name()).second) {
                throw std::invalid_argument(
                    "Duplicate container name."
                );
            }
        }

        for (const auto& container : initContainers_) {
            if (!names.insert(container.name()).second) {
                throw std::invalid_argument(
                    "Duplicate init container name."
                );
            }
        }

        initialized_ = initContainers_.empty();
        record("Pod created.");
    }

    ResourceRequest schedulingRequest() const {
        ResourceRequest application;
        ResourceRequest initialization;

        for (const auto& container : containers_) {
            application.cpu += container.resources().cpuRequest;
            application.memory +=
                container.resources().memoryRequest;
        }

        for (const auto& container : initContainers_) {
            initialization.cpu = std::max(
                initialization.cpu,
                container.resources().cpuRequest
            );

            initialization.memory = std::max(
                initialization.memory,
                container.resources().memoryRequest
            );
        }

        return {
            std::max(application.cpu, initialization.cpu),
            std::max(application.memory, initialization.memory)
        };
    }

    void record(const std::string& event) {
        events_.push_back(event);
    }

    void assignNode(const std::string& nodeName) {
        if (scheduled_) {
            throw std::logic_error(
                "Pod is already scheduled."
            );
        }

        nodeName_ = nodeName;
        scheduled_ = true;
        record("Pod scheduled on " + nodeName);
    }

    void initialize() {
        if (!scheduled_) {
            throw std::logic_error(
                "Pod must be scheduled first."
            );
        }

        if (phase_ != PodPhase::Pending) {
            throw std::logic_error(
                "Invalid initialization state."
            );
        }

        for (auto& container : initContainers_) {
            container.start();
            container.markReady();
            container.terminate(0);

            record(
                "Init container completed: " + container.name()
            );
        }

        initialized_ = true;
    }

    void start() {
        if (!scheduled_ || !initialized_) {
            throw std::logic_error(
                "Pod prerequisites are incomplete."
            );
        }

        if (phase_ != PodPhase::Pending) {
            throw std::logic_error(
                "Pod cannot start in its current phase."
            );
        }

        for (auto& container : containers_) {
            container.start();
        }

        phase_ = PodPhase::Running;
        record("Application containers started.");
    }

    void evaluateReadiness() {
        containersReady_ = (
            phase_ == PodPhase::Running &&
            std::all_of(
                containers_.begin(),
                containers_.end(),
                [](const Container& container) {
                    return (
                        container.state() == ContainerState::Running &&
                        container.ready()
                    );
                }
            )
        );

        ready_ = containersReady_;
    }

    void readinessProbe(bool successful) {
        if (phase_ != PodPhase::Running) {
            throw std::logic_error(
                "Readiness probes require a running Pod."
            );
        }

        for (auto& container : containers_) {
            if (container.state() == ContainerState::Running) {
                if (successful) {
                    container.markReady();
                }
            }
        }

        if (!successful) {
            // A failed readiness probe removes the Pod from ready endpoints.
            // It does not automatically restart the container.
            ready_ = false;
            containersReady_ = false;
        } else {
            evaluateReadiness();
        }

        record(
            successful
                ? "Readiness probe succeeded."
                : "Readiness probe failed."
        );
    }

    void containerFailure(
        const std::string& containerName,
        int exitCode
    ) {
        auto iterator = std::find_if(
            containers_.begin(),
            containers_.end(),
            [&](const Container& container) {
                return container.name() == containerName;
            }
        );

        if (iterator == containers_.end()) {
            throw std::invalid_argument(
                "Unknown application container."
            );
        }

        iterator->terminate(exitCode);

        const bool shouldRestart = (
            restartPolicy_ == RestartPolicy::Always ||
            (
                restartPolicy_ == RestartPolicy::OnFailure &&
                exitCode != 0
            )
        );

        if (shouldRestart) {
            iterator->restart();
            iterator->start();

            record(
                "Container restarted: " + containerName
            );
        } else {
            const bool allTerminated = std::all_of(
                containers_.begin(),
                containers_.end(),
                [](const Container& container) {
                    return container.state() ==
                        ContainerState::Terminated;
                }
            );

            if (allTerminated) {
                const bool successful = std::all_of(
                    containers_.begin(),
                    containers_.end(),
                    [](const Container& container) {
                        return container.exitCode() == 0;
                    }
                );

                phase_ = successful
                    ? PodPhase::Succeeded
                    : PodPhase::Failed;
            }
        }

        evaluateReadiness();
        record("Container failure processed.");
    }

    void complete(int exitCode = 0) {
        if (phase_ != PodPhase::Running) {
            throw std::logic_error(
                "Only running Pods can complete."
            );
        }

        for (auto& container : containers_) {
            if (container.state() == ContainerState::Running) {
                container.terminate(exitCode);
            }
        }

        phase_ = exitCode == 0
            ? PodPhase::Succeeded
            : PodPhase::Failed;

        ready_ = false;
        containersReady_ = false;

        record("Pod completed.");
    }

    const std::string& id() const {
        return id_;
    }

    const std::string& name() const {
        return name_;
    }

    const std::string& nodeName() const {
        return nodeName_;
    }

    PodPhase phase() const {
        return phase_;
    }

    bool ready() const {
        return ready_;
    }

    const std::vector<Container>& containers() const {
        return containers_;
    }

    std::vector<Container>& containers() {
        return containers_;
    }

    const std::vector<std::string>& events() const {
        return events_;
    }

    void print() const {
        std::cout
            << "\nPod: " << name_
            << "\nNamespace: " << namespace_
            << "\nPhase: " << toString(phase_)
            << "\nNode: " << nodeName_
            << "\nReady: " << std::boolalpha << ready_
            << "\nContainers:\n";

        for (const auto& container : containers_) {
            std::cout
                << "  " << container.name()
                << " | " << container.image()
                << " | " << toString(container.state())
                << " | Restarts: " << container.restartCount()
                << '\n';
        }
    }
};

// ============================================================
// 6. SCHEDULER
// ============================================================

class Scheduler {
private:
    std::vector<Node*> nodes_;

public:
    explicit Scheduler(std::vector<Node*> nodes)
        : nodes_(std::move(nodes)) {

        if (nodes_.empty()) {
            throw std::invalid_argument(
                "Scheduler requires worker nodes."
            );
        }
    }

    std::string schedule(Pod& pod) {
        const auto request = pod.schedulingRequest();

        std::vector<Node*> candidates;

        for (Node* node : nodes_) {
            if (node->canFit(request)) {
                candidates.push_back(node);
            }
        }

        std::sort(
            candidates.begin(),
            candidates.end(),
            [&](Node* a, Node* b) {
                const auto left = a->allocated();
                const auto right = b->allocated();

                const double scoreA =
                    a->cpuCapacity() - left.cpu - request.cpu;

                const double scoreB =
                    b->cpuCapacity() - right.cpu - request.cpu;

                return scoreA < scoreB;
            }
        );

        for (Node* node : candidates) {
            if (node->reserve(pod.id(), request)) {
                pod.assignNode(node->name());
                return node->name();
            }
        }

        throw std::runtime_error(
            "No node has sufficient available resources."
        );
    }

    void release(Pod& pod) {
        for (Node* node : nodes_) {
            node->release(pod.id());
        }
    }
};

// ============================================================
// 7. DEPLOYMENT RECONCILIATION
// ============================================================

class Deployment {
private:
    std::string name_;
    std::string namespace_;
    std::string image_;
    int desiredReplicas_;

    std::vector<Pod> pods_;
    int generation_ = 1;

    int nextId_ = 1;

    Pod createPod() {
        const std::string id =
            name_ + "-" + std::to_string(nextId_);

        const std::string podName =
            name_ + "-" + std::to_string(nextId_++);

        return Pod(
            id,
            podName,
            namespace_,
            {
                Container(
                    "application",
                    image_
                )
            }
        );
    }

public:
    Deployment(
        std::string name,
        std::string namespaceName,
        std::string image,
        int replicas
    )
        : name_(std::move(name)),
          namespace_(std::move(namespaceName)),
          image_(std::move(image)),
          desiredReplicas_(replicas) {

        if (
            name_.empty() ||
            namespace_.empty() ||
            image_.empty() ||
            replicas < 0
        ) {
            throw std::invalid_argument(
                "Invalid Deployment configuration."
            );
        }
    }

    void reconcile() {
        while (
            static_cast<int>(pods_.size()) < desiredReplicas_
        ) {
            pods_.push_back(createPod());
        }

        while (
            static_cast<int>(pods_.size()) > desiredReplicas_
        ) {
            pods_.pop_back();
        }
    }

    void rollingUpdate(
        const std::string& newImage,
        Scheduler& scheduler
    ) {
        if (newImage.empty()) {
            throw std::invalid_argument(
                "Image reference is required."
            );
        }

        ++generation_;

        std::vector<Pod> replacements;

        // Replacement Pods are validated before old replicas are removed.
        for (int i = 0; i < desiredReplicas_; ++i) {
            const std::string id =
                name_ + "-update-" + std::to_string(nextId_);

            const std::string podName =
                name_ + "-update-" + std::to_string(nextId_++);

            replacements.emplace_back(
                id,
                podName,
                namespace_,
                {
                    Container("application", newImage)
                }
            );
        }

        std::vector<Pod*> scheduled;

        try {
            for (auto& pod : replacements) {
                scheduler.schedule(pod);
                scheduled.push_back(&pod);

                pod.initialize();
                pod.start();
                pod.readinessProbe(true);

                if (!pod.ready()) {
                    throw std::runtime_error(
                        "Replacement Pod is not ready."
                    );
                }
            }
        } catch (...) {
            for (Pod* pod : scheduled) {
                scheduler.release(*pod);
            }

            throw;
        }

        for (auto& oldPod : pods_) {
            scheduler.release(oldPod);
        }

        pods_ = std::move(replacements);
        image_ = newImage;
    }

    void setReplicas(int replicas) {
        if (replicas < 0) {
            throw std::invalid_argument(
                "Replicas cannot be negative."
            );
        }

        desiredReplicas_ = replicas;
        ++generation_;
    }

    void printStatus() const {
        const int ready = static_cast<int>(
            std::count_if(
                pods_.begin(),
                pods_.end(),
                [](const Pod& pod) {
                    return pod.ready();
                }
            )
        );

        std::cout
            << "\nDeployment: " << name_
            << "\nImage: " << image_
            << "\nDesired replicas: " << desiredReplicas_
            << "\nActual replicas: " << pods_.size()
            << "\nReady replicas: " << ready
            << "\nGeneration: " << generation_
            << '\n';
    }

    std::vector<Pod>& pods() {
        return pods_;
    }

    const std::vector<Pod>& pods() const {
        return pods_;
    }
};

// ============================================================
// 8. CLUSTER REPORTING
// ============================================================

struct ClusterMetrics {
    int total = 0;
    int pending = 0;
    int running = 0;
    int succeeded = 0;
    int failed = 0;
    int ready = 0;
    int restarts = 0;
};

ClusterMetrics calculateMetrics(
    const std::vector<Pod*>& pods
) {
    ClusterMetrics metrics;
    metrics.total = static_cast<int>(pods.size());

    for (Pod* pod : pods) {
        switch (pod->phase()) {
            case PodPhase::Pending:
                ++metrics.pending;
                break;
            case PodPhase::Running:
                ++metrics.running;
                break;
            case PodPhase::Succeeded:
                ++metrics.succeeded;
                break;
            case PodPhase::Failed:
                ++metrics.failed;
                break;
            default:
                break;
        }

        if (pod->ready()) {
            ++metrics.ready;
        }

        for (const auto& container : pod->containers()) {
            metrics.restarts += container.restartCount();
        }
    }

    return metrics;
}

void printMetrics(const ClusterMetrics& metrics) {
    std::cout
        << "\nCLUSTER REPORT"
        << "\nTotal: " << metrics.total
        << "\nPending: " << metrics.pending
        << "\nRunning: " << metrics.running
        << "\nSucceeded: " << metrics.succeeded
        << "\nFailed: " << metrics.failed
        << "\nReady: " << metrics.ready
        << "\nRestarts: " << metrics.restarts
        << '\n';
}

// ============================================================
// 9. EXECUTABLE DEMONSTRATION
// ============================================================

} // namespace kube

int main() {
    using namespace kube;

    try {
        std::cout
            << "KUBERNETES POD GOVERNANCE ENGINE\n"
            << "================================\n";

        // Worker node capacities are expressed in CPU cores and MiB.
        Node worker1("worker-01", 8.0, 16384);
        Node worker2("worker-02", 4.0, 8192);

        Scheduler scheduler({&worker1, &worker2});

        Resources apiResources{
            0.5,
            1.0,
            256,
            512
        };

        Pod apiPod(
            "pod-001",
            "api-pod",
            "production",
            {
                Container(
                    "api",
                    "python:3.13-slim",
                    apiResources
                ),
                Container(
                    "metrics",
                    "busybox:1.36"
                )
            },
            {
                Container(
                    "database-init",
                    "busybox:1.36"
                )
            },
            RestartPolicy::Always
        );

        std::cout << "\n1. Resource-aware scheduling\n";

        std::cout
            << "Assigned node: "
            << scheduler.schedule(apiPod)
            << '\n';

        std::cout << "\n2. Initialization\n";
        apiPod.initialize();

        std::cout << "\n3. Starting application containers\n";
        apiPod.start();

        std::cout << "\n4. Readiness probe\n";
        apiPod.readinessProbe(true);

        assert(apiPod.ready());

        apiPod.print();

        std::cout << "\n5. Container failure simulation\n";

        apiPod.containerFailure("api", 1);

        std::cout
            << "Restart count: "
            << apiPod.containers()[0].restartCount()
            << '\n';

        std::cout << "\n6. Deployment creation\n";

        Deployment deployment(
            "frontend",
            "production",
            "nginx:1.27",
            3
        );

        deployment.reconcile();
        deployment.printStatus();

        std::cout << "\n7. Scheduling deployment replicas\n";

        for (auto& pod : deployment.pods()) {
            scheduler.schedule(pod);
            pod.initialize();
            pod.start();
            pod.readinessProbe(true);
        }

        deployment.printStatus();

        std::cout << "\n8. Rolling update\n";

        deployment.rollingUpdate(
            "nginx:1.28",
            scheduler
        );

        deployment.printStatus();

        std::cout << "\n9. Resource allocation\n";

        for (const Node* node : {&worker1, &worker2}) {
            const auto used = node->allocated();

            std::cout
                << node->name()
                << " CPU: " << used.cpu
                << " Memory: " << used.memory << " MiB\n";
        }

        std::cout << "\n10. Cluster metrics\n";

        std::vector<Pod*> allPods = {&apiPod};

        for (auto& pod : deployment.pods()) {
            allPods.push_back(&pod);
        }

        printMetrics(calculateMetrics(allPods));

        std::cout << "\n11. Edge-case validation\n";

        bool rejected = false;

        try {
            Resources invalid{
                2.0,
                1.0,
                256,
                512
            };

            invalid.validate();
        } catch (const std::invalid_argument&) {
            rejected = true;
        }

        assert(rejected);

        rejected = false;

        try {
            Node invalidNode("invalid", -2.0, 1024);
        } catch (const std::invalid_argument&) {
            rejected = true;
        }

        assert(rejected);

        std::cout << "Invalid resource configurations rejected.\n";

        std::cout << "\nAll demonstrations completed successfully.\n";

    } catch (const std::exception& error) {
        std::cerr
            << "Execution error: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
