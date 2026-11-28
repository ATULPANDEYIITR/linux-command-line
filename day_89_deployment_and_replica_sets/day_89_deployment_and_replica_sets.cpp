#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class PodState {
    Pending,
    Running,
    Terminating,
    Terminated,
    Failed
};

enum class RolloutState {
    Progressing,
    Available,
    Degraded
};

enum class ReplicaSetState {
    Active,
    Inactive
};

string toString(PodState state) {
    switch (state) {
        case PodState::Pending: return "Pending";
        case PodState::Running: return "Running";
        case PodState::Terminating: return "Terminating";
        case PodState::Terminated: return "Terminated";
        case PodState::Failed: return "Failed";
    }

    return "Unknown";
}

struct DeploymentPolicy {
    int replicas = 3;
    int maxSurge = 1;
    int maxUnavailable = 0;
    int revisionHistoryLimit = 5;

    void validate() const {
        if (replicas < 0) {
            throw invalid_argument("Replicas cannot be negative");
        }

        if (maxSurge < 0 || maxUnavailable < 0) {
            throw invalid_argument("Invalid rolling update policy");
        }

        if (maxSurge == 0 && maxUnavailable == 0) {
            throw invalid_argument(
                "At least one rollout allowance must be positive"
            );
        }

        if (revisionHistoryLimit < 0) {
            throw invalid_argument("Invalid revision history limit");
        }
    }
};

class Pod {
private:
    string id_;
    string image_;
    string replicaSetId_;
    PodState state_;
    bool ready_;

public:
    Pod(
        string id,
        string image,
        string replicaSetId
    )
        : id_(move(id)),
          image_(move(image)),
          replicaSetId_(move(replicaSetId)),
          state_(PodState::Pending),
          ready_(false) {}

    void start() {
        if (state_ != PodState::Pending) {
            throw logic_error("Invalid pod start transition");
        }

        state_ = PodState::Running;
    }

    void markReady() {
        if (state_ != PodState::Running) {
            throw logic_error("Pod must be running before readiness");
        }

        ready_ = true;
    }

    void markUnready() {
        ready_ = false;
    }

    void terminate() {
        if (
            state_ == PodState::Terminated ||
            state_ == PodState::Failed
        ) {
            return;
        }

        ready_ = false;
        state_ = PodState::Terminating;
        state_ = PodState::Terminated;
    }

    bool isActive() const {
        return state_ != PodState::Terminated &&
               state_ != PodState::Failed;
    }

    bool isReady() const {
        return ready_ && state_ == PodState::Running;
    }

    const string& id() const {
        return id_;
    }

    const string& image() const {
        return image_;
    }

    PodState state() const {
        return state_;
    }
};

class ReplicaSet {
private:
    string id_;
    string name_;
    string image_;
    int revision_;
    int desiredReplicas_;
    ReplicaSetState state_;
    map<string, unique_ptr<Pod>> pods_;

public:
    ReplicaSet(
        string id,
        string deploymentName,
        string image,
        int revision
    )
        : id_(move(id)),
          name_(deploymentName + "-" + id_),
          image_(move(image)),
          revision_(revision),
          desiredReplicas_(0),
          state_(ReplicaSetState::Active) {}

    void addPod(unique_ptr<Pod> pod) {
        string id = pod->id();

        if (!pods_.emplace(id, move(pod)).second) {
            throw logic_error("Duplicate pod identifier");
        }
    }

    int activeCount() const {
        return count_if(
            pods_.begin(),
            pods_.end(),
            [](const auto& entry) {
                return entry.second->isActive();
            }
        );
    }

    int readyCount() const {
        return count_if(
            pods_.begin(),
            pods_.end(),
            [](const auto& entry) {
                return entry.second->isReady();
            }
        );
    }

    vector<Pod*> activePods() {
        vector<Pod*> result;

        for (auto& [id, pod] : pods_) {
            if (pod->isActive()) {
                result.push_back(pod.get());
            }
        }

        return result;
    }

    void setDesired(int desired) {
        if (desired < 0) {
            throw invalid_argument("Desired replicas cannot be negative");
        }

        desiredReplicas_ = desired;
    }

    void setInactive() {
        state_ = ReplicaSetState::Inactive;
    }

    bool active() const {
        return state_ == ReplicaSetState::Active;
    }

    int revision() const {
        return revision_;
    }

    int desired() const {
        return desiredReplicas_;
    }

    const string& image() const {
        return image_;
    }

    const string& id() const {
        return id_;
    }

    const string& name() const {
        return name_;
    }
};

struct Revision {
    int number;
    string image;
    string replicaSetId;
};

class DeploymentController {
private:
    string name_;
    string namespace_;
    string image_;

    DeploymentPolicy policy_;

    int revision_;
    int generation_;
    int nextId_;

    map<string, unique_ptr<ReplicaSet>> replicaSets_;
    map<int, Revision> history_;

    string generateId() {
        return "resource-" + to_string(nextId_++);
    }

    ReplicaSet& createReplicaSet(const string& image) {
        string id = generateId();

        auto replicaSet = make_unique<ReplicaSet>(
            id,
            name_,
            image,
            revision_
        );

        ReplicaSet& reference = *replicaSet;

        replicaSets_.emplace(id, move(replicaSet));

        history_[revision_] = {
            revision_,
            image,
            id
        };

        return reference;
    }

    vector<ReplicaSet*> activeSets() {
        vector<ReplicaSet*> result;

        for (auto& [id, rs] : replicaSets_) {
            if (rs->active()) {
                result.push_back(rs.get());
            }
        }

        return result;
    }

    ReplicaSet* currentSet() {
        ReplicaSet* result = nullptr;

        for (ReplicaSet* rs : activeSets()) {
            if (rs->image() == image_) {
                if (
                    result == nullptr ||
                    rs->revision() > result->revision()
                ) {
                    result = rs;
                }
            }
        }

        return result;
    }

    void createPod(ReplicaSet& rs) {
        string id = generateId();

        auto pod = make_unique<Pod>(
            id,
            rs.image(),
            rs.id()
        );

        pod->start();
        rs.addPod(move(pod));
    }

    void removePod(Pod& pod) {
        pod.terminate();
    }

    void sync(ReplicaSet& rs, int desired) {
        rs.setDesired(desired);

        auto pods = rs.activePods();

        while (static_cast<int>(pods.size()) < desired) {
            createPod(rs);
            pods = rs.activePods();
        }

        while (static_cast<int>(pods.size()) > desired) {
            removePod(*pods.back());
            pods.pop_back();
        }
    }

public:
    DeploymentController(
        string name,
        string namespaceName,
        string image,
        DeploymentPolicy policy
    )
        : name_(move(name)),
          namespace_(move(namespaceName)),
          image_(move(image)),
          policy_(policy),
          revision_(1),
          generation_(1),
          nextId_(1) {

        if (name_.empty() || namespace_.empty() || image_.empty()) {
            throw invalid_argument("Deployment fields are required");
        }

        policy_.validate();

        createReplicaSet(image_);
        reconcile();
    }

    void reconcile() {
        /*
         * The controller does not directly store a desired pod count
         * inside the cluster. It continuously compares desired and
         * observed state and corrects differences.
         */

        if (activeSets().empty()) {
            createReplicaSet(image_);
        }

        for (ReplicaSet* rs : activeSets()) {
            int desired = rs->image() == image_
                ? policy_.replicas
                : 0;

            sync(*rs, desired);
        }
    }

    void markReady(const string& podId) {
        for (auto& [id, rs] : replicaSets_) {
            for (Pod* pod : rs->activePods()) {
                if (pod->id() == podId) {
                    pod->markReady();
                    return;
                }
            }
        }

        throw out_of_range("Pod not found");
    }

    void markAllCurrentReady() {
        ReplicaSet* rs = currentSet();

        if (rs == nullptr) {
            throw logic_error("Current ReplicaSet does not exist");
        }

        for (Pod* pod : rs->activePods()) {
            if (!pod->isReady()) {
                pod->markReady();
            }
        }
    }

    void scale(int replicas) {
        if (replicas < 0) {
            throw invalid_argument("Invalid replica count");
        }

        policy_.replicas = replicas;
        generation_++;

        reconcile();
    }

    void updateImage(const string& newImage) {
        if (newImage.empty()) {
            throw invalid_argument("Image cannot be empty");
        }

        if (newImage == image_) {
            return;
        }

        image_ = newImage;
        revision_++;
        generation_++;

        for (ReplicaSet* rs : activeSets()) {
            rs->setInactive();
        }

        createReplicaSet(image_);
        reconcile();
    }

    string rollingUpdateStep() {
        int desired = policy_.replicas;

        vector<ReplicaSet*> oldSets;
        vector<ReplicaSet*> newSets;

        for (ReplicaSet* rs : activeSets()) {
            if (rs->image() == image_) {
                newSets.push_back(rs);
            } else {
                oldSets.push_back(rs);
            }
        }

        if (newSets.empty()) {
            throw logic_error("Target ReplicaSet not found");
        }

        ReplicaSet* target = newSets.front();

        int total = 0;
        int ready = 0;

        for (ReplicaSet* rs : activeSets()) {
            total += rs->activeCount();
            ready += rs->readyCount();
        }

        int oldCount = 0;

        for (ReplicaSet* rs : oldSets) {
            oldCount += rs->activeCount();
        }

        int newCount = target->activeCount();

        int maxTotal = desired + policy_.maxSurge;

        int minimumAvailable = max(
            0,
            desired - policy_.maxUnavailable
        );

        if (newCount < desired && total < maxTotal) {
            createPod(*target);
            return "CREATED";
        }

        if (oldCount > 0 && ready > minimumAvailable) {
            for (ReplicaSet* rs : oldSets) {
                auto pods = rs->activePods();

                if (!pods.empty()) {
                    removePod(*pods.front());
                    return "TERMINATED";
                }
            }
        }

        if (oldCount == 0 && newCount >= desired) {
            for (ReplicaSet* rs : oldSets) {
                rs->setInactive();
            }

            return "COMPLETED";
        }

        return "WAITING";
    }

    void rollingUpdate(int maximumSteps = 100) {
        if (maximumSteps <= 0) {
            throw invalid_argument("Maximum steps must be positive");
        }

        for (int i = 0; i < maximumSteps; ++i) {
            string result = rollingUpdateStep();

            cout << "Rollout operation: " << result << '\n';

            if (result == "COMPLETED") {
                return;
            }

            if (result == "WAITING") {
                return;
            }

            // Simulate readiness probes succeeding for new pods.
            markAllCurrentReady();
        }

        throw runtime_error("Rolling update exceeded step limit");
    }

    void rollback(int targetRevision) {
        auto it = history_.find(targetRevision);

        if (it == history_.end()) {
            throw out_of_range("Revision does not exist");
        }

        if (it->second.image == image_) {
            return;
        }

        // A rollback is a new revision pointing to an older image.
        updateImage(it->second.image);
    }

    void pruneHistory() {
        vector<int> revisions;

        for (const auto& [number, revision] : history_) {
            revisions.push_back(number);
        }

        int limit = policy_.revisionHistoryLimit;

        while (
            limit == 0
                ? revisions.size() > 0
                : static_cast<int>(revisions.size()) > limit
        ) {
            if (limit == 0 && revisions.back() == revision_) {
                break;
            }

            int oldest = revisions.front();

            if (oldest == revision_) {
                break;
            }

            history_.erase(oldest);
            revisions.erase(revisions.begin());
        }
    }

    void report() {
        int total = 0;
        int ready = 0;
        int updated = 0;

        cout << "\nDEPLOYMENT: " << name_ << '\n';
        cout << "NAMESPACE: " << namespace_ << '\n';
        cout << "IMAGE: " << image_ << '\n';
        cout << "GENERATION: " << generation_ << '\n';
        cout << "REVISION: " << revision_ << '\n';

        cout << "\nREPLICASETS\n";

        for (const auto& [id, rs] : replicaSets_) {
            if (!rs->active()) {
                continue;
            }

            cout << "Name: " << rs->name()
                 << " | Image: " << rs->image()
                 << " | Desired: " << rs->desired()
                 << " | Active: " << rs->activeCount()
                 << " | Ready: " << rs->readyCount()
                 << '\n';

            total += rs->activeCount();
            ready += rs->readyCount();

            if (rs->image() == image_) {
                updated += rs->activeCount();
            }
        }

        cout << "\nSTATUS\n";
        cout << "Desired replicas: " << policy_.replicas << '\n';
        cout << "Total active: " << total << '\n';
        cout << "Updated replicas: " << updated << '\n';
        cout << "Ready replicas: " << ready << '\n';
        cout << "Unavailable: "
             << max(0, policy_.replicas - ready) << '\n';

        cout << "Phase: "
             << (
                 ready >= policy_.replicas
                     ? "Available"
                     : "Progressing"
             )
             << '\n';

        cout << "\nREVISION HISTORY\n";

        for (const auto& [number, revision] : history_) {
            cout << number << " -> " << revision.image << '\n';
        }
    }
};

int main() {
    try {
        DeploymentPolicy policy;
        policy.replicas = 3;
        policy.maxSurge = 1;
        policy.maxUnavailable = 0;
        policy.revisionHistoryLimit = 5;

        DeploymentController deployment(
            "orders-api",
            "production",
            "orders-api:v1.0.0",
            policy
        );

        cout << "INITIAL DEPLOYMENT\n";

        deployment.markAllCurrentReady();
        deployment.report();

        cout << "\nSTARTING ROLLING UPDATE\n";

        deployment.updateImage("orders-api:v2.0.0");
        deployment.rollingUpdate();

        deployment.report();

        cout << "\nROLLBACK TO REVISION 1\n";

        deployment.rollback(1);
        deployment.markAllCurrentReady();
        deployment.report();

        cout << "\nSCALING TO FIVE REPLICAS\n";

        deployment.scale(5);
        deployment.markAllCurrentReady();
        deployment.report();

        deployment.pruneHistory();

    } catch (const exception& error) {
        cerr << "CONTROLLER ERROR: "
             << error.what()
             << '\n';

        return 1;
    }

    return 0;
}
