#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * Kubernetes Cluster Governance and Resource Scheduling Engine
 *
 * C++17 implementation of:
 * - Cluster architecture
 * - Control-plane and worker nodes
 * - Pod scheduling
 * - Resource requests and capacity
 * - Deployment reconciliation
 * - Service endpoint selection
 * - Node failure and recovery
 * - Rolling replacement
 * - Cluster health evaluation
 *
 * No external dependencies.
 */

namespace kube {

// ============================================================
// EXCEPTIONS
// ============================================================

class KubernetesException : public std::runtime_error {
public:
    explicit KubernetesException(const std::string& message)
        : std::runtime_error(message) {}
};

class ValidationException : public KubernetesException {
public:
    using KubernetesException::KubernetesException;
};

class SchedulingException : public KubernetesException {
public:
    using KubernetesException::KubernetesException;
};

class ResourceNotFoundException : public KubernetesException {
public:
    using KubernetesException::KubernetesException;
};


// ============================================================
// ENUMERATIONS
// ============================================================

enum class NodeRole {
    ControlPlane,
    Worker
};

enum class NodeStatus {
    Ready,
    NotReady
};

enum class PodStatus {
    Pending,
    Running,
    Failed,
    Terminating
};

enum class ServiceType {
    ClusterIP,
    NodePort,
    LoadBalancer
};

std::string toString(NodeRole role) {
    return role == NodeRole::Worker
        ? "Worker"
        : "ControlPlane";
}

std::string toString(NodeStatus status) {
    return status == NodeStatus::Ready
        ? "Ready"
        : "NotReady";
}

std::string toString(PodStatus status) {
    switch (status) {
        case PodStatus::Pending: return "Pending";
        case PodStatus::Running: return "Running";
        case PodStatus::Failed: return "Failed";
        case PodStatus::Terminating: return "Terminating";
    }

    return "Unknown";
}


// ============================================================
// RESOURCE MODEL
// ============================================================

struct Resources {
    int cpuMillicores;
    int memoryMB;

    Resources(int cpu, int memory)
        : cpuMillicores(cpu), memoryMB(memory) {

        if (cpu <= 0 || memory <= 0) {
            throw ValidationException(
                "CPU and memory requests must be positive."
            );
        }
    }
};


// ============================================================
// CONTAINER
// ============================================================

struct Container {
    std::string name;
    std::string image;
    Resources resources;
    bool ready = true;
    int restartCount = 0;

    Container(
        std::string containerName,
        std::string containerImage,
        Resources requirements
    )
        : name(std::move(containerName)),
          image(std::move(containerImage)),
          resources(requirements) {

        if (name.empty() || image.empty()) {
            throw ValidationException(
                "Container name and image are required."
            );
        }
    }
};


// ============================================================
// POD
// ============================================================

struct Pod {
    std::string id;
    std::string name;
    std::string namespaceName;
    std::string nodeName;

    std::map<std::string, std::string> labels;
    std::vector<Container> containers;

    PodStatus status = PodStatus::Pending;
    bool ready = false;

    Resources requirements() const {
        int cpu = 0;
        int memory = 0;

        for (const auto& container : containers) {
            cpu += container.resources.cpuMillicores;
            memory += container.resources.memoryMB;
        }

        return Resources(cpu, memory);
    }

    bool matches(
        const std::map<std::string, std::string>& selector
    ) const {

        return std::all_of(
            selector.begin(),
            selector.end(),
            [&](const auto& entry) {
                auto it = labels.find(entry.first);

                return it != labels.end()
                    && it->second == entry.second;
            }
        );
    }
};


// ============================================================
// NODE
// ============================================================

class Node {

private:
    Resources capacity_;
    int allocatedCPU_ = 0;
    int allocatedMemory_ = 0;

    std::set<std::string> podIds_;

public:
    std::string name;
    NodeRole role;
    NodeStatus status = NodeStatus::Ready;

    Node(
        std::string nodeName,
        NodeRole nodeRole,
        Resources capacity
    )
        : capacity_(capacity),
          name(std::move(nodeName)),
          role(nodeRole) {

        if (name.empty()) {
            throw ValidationException("Node name is required.");
        }
    }

    bool canSchedule(const Resources& resources) const {

        return role == NodeRole::Worker
            && status == NodeStatus::Ready
            && allocatedCPU_ + resources.cpuMillicores
                <= capacity_.cpuMillicores
            && allocatedMemory_ + resources.memoryMB
                <= capacity_.memoryMB;
    }

    void allocate(const Pod& pod) {

        Resources resources = pod.requirements();

        if (!canSchedule(resources)) {
            throw SchedulingException(
                "Insufficient resources on node " + name
            );
        }

        if (podIds_.count(pod.id)) {
            throw ValidationException(
                "Pod already allocated on node."
            );
        }

        allocatedCPU_ += resources.cpuMillicores;
        allocatedMemory_ += resources.memoryMB;

        podIds_.insert(pod.id);
    }

    void release(const Pod& pod) {

        if (!podIds_.count(pod.id)) {
            return;
        }

        Resources resources = pod.requirements();

        allocatedCPU_ -= resources.cpuMillicores;
        allocatedMemory_ -= resources.memoryMB;

        podIds_.erase(pod.id);

        if (allocatedCPU_ < 0 || allocatedMemory_ < 0) {
            throw KubernetesException(
                "Node resource accounting is inconsistent."
            );
        }
    }

    int availableCPU() const {
        return capacity_.cpuMillicores - allocatedCPU_;
    }

    int availableMemory() const {
        return capacity_.memoryMB - allocatedMemory_;
    }

    int allocatedCPU() const {
        return allocatedCPU_;
    }

    int allocatedMemory() const {
        return allocatedMemory_;
    }

    std::size_t podCount() const {
        return podIds_.size();
    }

    const std::set<std::string>& podIds() const {
        return podIds_;
    }

    const Resources& capacity() const {
        return capacity_;
    }
};


// ============================================================
// DEPLOYMENT
// ============================================================

struct Deployment {
    std::string name;
    std::string image;

    int desiredReplicas;
    int generation = 1;

    Resources resources;

    std::map<std::string, std::string> labels;
    std::vector<std::string> podIds;

    Deployment(
        std::string deploymentName,
        std::string containerImage,
        int replicas,
        Resources requirements,
        std::map<std::string, std::string> podLabels
    )
        : name(std::move(deploymentName)),
          image(std::move(containerImage)),
          desiredReplicas(replicas),
          resources(requirements),
          labels(std::move(podLabels)) {

        if (name.empty() || image.empty()) {
            throw ValidationException(
                "Deployment name and image are required."
            );
        }

        if (replicas < 0) {
            throw ValidationException(
                "Replica count cannot be negative."
            );
        }

        if (labels.empty()) {
            throw ValidationException(
                "Deployment labels are required."
            );
        }
    }
};


// ============================================================
// SERVICE
// ============================================================

struct Service {
    std::string name;
    std::map<std::string, std::string> selector;

    int port;
    int targetPort;

    std::string clusterIP;

    Service(
        std::string serviceName,
        std::map<std::string, std::string> serviceSelector,
        int servicePort,
        int containerPort
    )
        : name(std::move(serviceName)),
          selector(std::move(serviceSelector)),
          port(servicePort),
          targetPort(containerPort) {

        if (name.empty() || selector.empty()) {
            throw ValidationException(
                "Service name and selector are required."
            );
        }

        if (
            port < 1 || port > 65535 ||
            targetPort < 1 || targetPort > 65535
        ) {
            throw ValidationException(
                "Invalid Service port."
            );
        }
    }
};


// ============================================================
// SCHEDULER
// ============================================================

class Scheduler {

public:

    Node& schedule(
        const Pod& pod,
        std::map<std::string, Node>& nodes
    ) {

        std::vector<Node*> candidates;

        for (auto& [name, node] : nodes) {
            if (node.canSchedule(pod.requirements())) {
                candidates.push_back(&node);
            }
        }

        if (candidates.empty()) {
            throw SchedulingException(
                "No suitable node for Pod " + pod.name
            );
        }

        Resources requested = pod.requirements();

        // Best-fit scheduling reduces the amount of fragmented capacity.
        auto selected = std::min_element(
            candidates.begin(),
            candidates.end(),
            [&](Node* a, Node* b) {
                return a->availableCPU()
                    - requested.cpuMillicores
                    <
                    b->availableCPU()
                    - requested.cpuMillicores;
            }
        );

        (*selected)->allocate(pod);

        return **selected;
    }
};


// ============================================================
// CLUSTER
// ============================================================

class KubernetesCluster {

private:

    std::map<std::string, Node> nodes_;
    std::map<std::string, Pod> pods_;
    std::map<std::string, Deployment> deployments_;
    std::map<std::string, Service> services_;

    Scheduler scheduler_;

    unsigned long long nextPodId_ = 1;

    std::string createPodId() {
        return "pod-" + std::to_string(nextPodId_++);
    }

    int activeReplicaCount(const Deployment& deployment) const {

        int count = 0;

        for (const auto& id : deployment.podIds) {
            auto it = pods_.find(id);

            if (
                it != pods_.end() &&
                (
                    it->second.status == PodStatus::Running ||
                    it->second.status == PodStatus::Pending
                )
            ) {
                count++;
            }
        }

        return count;
    }

public:

    std::string name;

    explicit KubernetesCluster(std::string clusterName)
        : name(std::move(clusterName)) {

        if (name.empty()) {
            throw ValidationException(
                "Cluster name cannot be empty."
            );
        }
    }

    void addNode(Node node) {

        if (nodes_.count(node.name)) {
            throw ValidationException(
                "Duplicate node: " + node.name
            );
        }

        std::string nodeName = node.name;

        nodes_.emplace(
            nodeName,
            std::move(node)
        );

        std::cout << "Node registered: "
                  << nodeName << '\n';
    }

    void createPod(Pod pod) {

        pod.id = createPodId();

        std::string id = pod.id;
        std::string podName = pod.name;

        auto [it, inserted] = pods_.emplace(
            id,
            std::move(pod)
        );

        if (!inserted) {
            throw ValidationException(
                "Duplicate Pod identifier."
            );
        }

        try {

            Node& node = scheduler_.schedule(
                it->second,
                nodes_
            );

            it->second.nodeName = node.name;
            it->second.status = PodStatus::Running;
            it->second.ready = true;

            std::cout
                << "Scheduled " << podName
                << " on " << node.name << '\n';

        } catch (const SchedulingException& error) {

            it->second.status = PodStatus::Pending;
            it->second.ready = false;

            std::cout
                << "Pending: " << podName
                << " | " << error.what() << '\n';
        }
    }

    void deletePod(const std::string& id) {

        auto it = pods_.find(id);

        if (it == pods_.end()) {
            throw ResourceNotFoundException(
                "Pod not found: " + id
            );
        }

        Pod& pod = it->second;

        pod.status = PodStatus::Terminating;

        if (!pod.nodeName.empty()) {
            nodes_.at(pod.nodeName).release(pod);
        }

        pods_.erase(it);
    }

    void reconcile(const std::string& name) {

        auto it = deployments_.find(name);

        if (it == deployments_.end()) {
            throw ResourceNotFoundException(
                "Deployment not found: " + name
            );
        }

        Deployment& deployment = it->second;

        while (
            activeReplicaCount(deployment)
            < deployment.desiredReplicas
        ) {

            Pod pod;

            pod.name =
                deployment.name + "-"
                + std::to_string(nextPodId_);

            pod.namespaceName = "default";
            pod.labels = deployment.labels;

            pod.containers.emplace_back(
                "application",
                deployment.image,
                deployment.resources
            );

            createPod(std::move(pod));

            const auto& created = pods_.rbegin()->second;

            deployment.podIds.push_back(created.id);
        }

        while (
            activeReplicaCount(deployment)
            > deployment.desiredReplicas
        ) {

            auto id = deployment.podIds.back();

            deletePod(id);

            deployment.podIds.pop_back();
        }
    }

    void createDeployment(Deployment deployment) {

        std::string deploymentName = deployment.name;

        if (deployments_.count(deploymentName)) {
            throw ValidationException(
                "Deployment already exists."
            );
        }

        deployments_.emplace(
            deploymentName,
            std::move(deployment)
        );

        reconcile(deploymentName);
    }

    void scaleDeployment(
        const std::string& name,
        int replicas
    ) {

        if (replicas < 0) {
            throw ValidationException(
                "Replica count cannot be negative."
            );
        }

        auto it = deployments_.find(name);

        if (it == deployments_.end()) {
            throw ResourceNotFoundException(
                "Deployment not found."
            );
        }

        it->second.desiredReplicas = replicas;
        it->second.generation++;

        reconcile(name);
    }

    void createService(Service service) {

        if (services_.count(service.name)) {
            throw ValidationException(
                "Service already exists."
            );
        }

        service.clusterIP =
            "10.96.0." + std::to_string(services_.size() + 10);

        services_.emplace(
            service.name,
            std::move(service)
        );
    }

    std::vector<std::string> endpoints(
        const std::string& serviceName
    ) const {

        auto serviceIt = services_.find(serviceName);

        if (serviceIt == services_.end()) {
            throw ResourceNotFoundException(
                "Service not found."
            );
        }

        std::vector<std::string> result;

        for (const auto& [id, pod] : pods_) {

            if (
                pod.status == PodStatus::Running &&
                pod.ready &&
                pod.matches(serviceIt->second.selector)
            ) {
                result.push_back(pod.name);
            }
        }

        return result;
    }

    void failNode(const std::string& name) {

        auto nodeIt = nodes_.find(name);

        if (nodeIt == nodes_.end()) {
            throw ResourceNotFoundException(
                "Node not found."
            );
        }

        Node& node = nodeIt->second;

        node.status = NodeStatus::NotReady;

        std::vector<std::string> affected(
            node.podIds().begin(),
            node.podIds().end()
        );

        for (const auto& id : affected) {

            auto podIt = pods_.find(id);

            if (podIt == pods_.end()) {
                continue;
            }

            node.release(podIt->second);

            podIt->second.status = PodStatus::Failed;
            podIt->second.ready = false;
            podIt->second.nodeName.clear();
        }

        std::cout
            << "Node failed: " << name
            << ", affected Pods: " << affected.size()
            << '\n';

        for (const auto& [deploymentName, deployment]
             : deployments_) {

            // Reconciliation creates replacements for failed replicas.
            reconcile(deploymentName);
        }
    }

    void recoverNode(const std::string& name) {

        auto it = nodes_.find(name);

        if (it == nodes_.end()) {
            throw ResourceNotFoundException(
                "Node not found."
            );
        }

        it->second.status = NodeStatus::Ready;

        for (auto& [id, pod] : pods_) {

            if (pod.status != PodStatus::Pending) {
                continue;
            }

            try {

                Node& selected = scheduler_.schedule(
                    pod,
                    nodes_
                );

                pod.nodeName = selected.name;
                pod.status = PodStatus::Running;
                pod.ready = true;

            } catch (const SchedulingException&) {
                // Pod remains pending until capacity is available.
            }
        }
    }

    void rollingUpdate(
        const std::string& name,
        const std::string& newImage
    ) {

        if (newImage.empty()) {
            throw ValidationException(
                "Container image cannot be empty."
            );
        }

        auto it = deployments_.find(name);

        if (it == deployments_.end()) {
            throw ResourceNotFoundException(
                "Deployment not found."
            );
        }

        Deployment& deployment = it->second;

        const std::string oldImage = deployment.image;
        const int originalGeneration = deployment.generation;

        const std::vector<std::string> oldIds =
            deployment.podIds;

        std::vector<std::string> replacementIds;

        try {

            deployment.image = newImage;
            deployment.generation++;

            // Create replacement Pods first.
            for (int i = 0; i < deployment.desiredReplicas; i++) {

                Pod pod;

                pod.name = name + "-updated-" + std::to_string(i + 1);
                pod.namespaceName = "default";
                pod.labels = deployment.labels;

                pod.containers.emplace_back(
                    "application",
                    newImage,
                    deployment.resources
                );

                createPod(std::move(pod));

                const std::string id = pods_.rbegin()->first;

                if (pods_.at(id).status != PodStatus::Running) {
                    throw SchedulingException(
                        "Replacement Pod could not be scheduled."
                    );
                }

                replacementIds.push_back(id);
            }

            // Remove old replicas only after replacements are ready.
            for (const auto& id : oldIds) {
                deletePod(id);
            }

            deployment.podIds = replacementIds;

        } catch (...) {

            for (const auto& id : replacementIds) {
                if (pods_.count(id)) {
                    deletePod(id);
                }
            }

            deployment.image = oldImage;
            deployment.generation = originalGeneration;
            deployment.podIds = oldIds;

            throw;
        }
    }

    void report() const {

        std::cout << "\nCLUSTER: " << name << '\n';

        std::cout << "\nNODES\n";

        for (const auto& [name, node] : nodes_) {

            std::cout
                << std::left << std::setw(15) << name
                << " | " << std::setw(12)
                << toString(node.role)
                << " | " << std::setw(10)
                << toString(node.status)
                << " | CPU: " << node.allocatedCPU()
                << "/" << node.capacity().cpuMillicores
                << " | Memory: " << node.allocatedMemory()
                << "/" << node.capacity().memoryMB
                << " MB | Pods: " << node.podCount()
                << '\n';
        }

        std::cout << "\nPODS\n";

        std::map<PodStatus, int> counts;

        for (const auto& [id, pod] : pods_) {
            counts[pod.status]++;
        }

        for (const auto& [status, count] : counts) {
            std::cout
                << toString(status)
                << ": " << count << '\n';
        }

        std::cout << "\nDEPLOYMENTS\n";

        for (const auto& [name, deployment] : deployments_) {
            std::cout
                << name
                << " | Desired: " << deployment.desiredReplicas
                << " | Observed: "
                << activeReplicaCount(deployment)
                << " | Image: " << deployment.image
                << " | Generation: " << deployment.generation
                << '\n';
        }

        std::cout << "\nSERVICES\n";

        for (const auto& [name, service] : services_) {
            std::cout
                << name
                << " | ClusterIP: " << service.clusterIP
                << " | Port: " << service.port
                << " | Endpoints: "
                << endpoints(name).size()
                << '\n';
        }
    }

    void validateInvariants() const {

        for (const auto& [name, node] : nodes_) {

            if (
                node.allocatedCPU() < 0 ||
                node.allocatedMemory() < 0 ||
                node.allocatedCPU() > node.capacity().cpuMillicores ||
                node.allocatedMemory() > node.capacity().memoryMB
            ) {
                throw KubernetesException(
                    "Resource invariant violated on " + name
                );
            }
        }

        for (const auto& [id, pod] : pods_) {

            if (
                pod.status == PodStatus::Running &&
                pod.nodeName.empty()
            ) {
                throw KubernetesException(
                    "Running Pod has no assigned node."
                );
            }

            if (
                pod.status == PodStatus::Running &&
                !nodes_.count(pod.nodeName)
            ) {
                throw KubernetesException(
                    "Pod references a missing node."
                );
            }
        }
    }
};

} // namespace kube


// ============================================================
// MAIN
// ============================================================

int main() {

    try {

        using namespace kube;

        KubernetesCluster cluster("production-cluster");

        cluster.addNode(
            Node(
                "master-01",
                NodeRole::ControlPlane,
                Resources(8000, 16384)
            )
        );

        cluster.addNode(
            Node(
                "worker-01",
                NodeRole::Worker,
                Resources(4000, 8192)
            )
        );

        cluster.addNode(
            Node(
                "worker-02",
                NodeRole::Worker,
                Resources(4000, 8192)
            )
        );

        cluster.addNode(
            Node(
                "worker-03",
                NodeRole::Worker,
                Resources(2000, 4096)
            )
        );

        Deployment deployment(
            "payment-api",
            "payment-api:1.0",
            3,
            Resources(500, 512),
            {
                {"app", "payment"},
                {"environment", "production"}
            }
        );

        cluster.createDeployment(std::move(deployment));

        Service service(
            "payment-service",
            {{"app", "payment"}},
            80,
            8080
        );

        cluster.createService(std::move(service));

        cluster.report();

        std::cout << "\nSERVICE ENDPOINTS\n";

        for (const auto& endpoint :
             cluster.endpoints("payment-service")) {

            std::cout << endpoint << '\n';
        }

        std::cout << "\nSCALING DEPLOYMENT TO FIVE REPLICAS\n";

        cluster.scaleDeployment("payment-api", 5);

        cluster.report();

        std::cout << "\nROLLING UPDATE\n";

        cluster.rollingUpdate(
            "payment-api",
            "payment-api:2.0"
        );

        cluster.report();

        std::cout << "\nSIMULATING WORKER FAILURE\n";

        cluster.failNode("worker-01");

        cluster.validateInvariants();
        cluster.report();

        std::cout << "\nRECOVERING WORKER\n";

        cluster.recoverNode("worker-01");

        cluster.validateInvariants();
        cluster.report();

        std::cout
            << "\nAll cluster invariants validated.\n";

    } catch (const std::exception& error) {

        std::cerr
            << "Kubernetes simulation error: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
