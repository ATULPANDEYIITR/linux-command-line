/*
 * Cloud Infrastructure Governance Engine
 *
 * C++17 case study:
 * A private cloud platform operates a three-tier application. The governance
 * engine validates whether compute workloads can communicate with each other,
 * whether storage is attached safely, and whether a workload satisfies the
 * platform's network security policy.
 *
 * The program emphasizes strongly typed domain objects, deterministic policy
 * evaluation, unordered containers, validation, and explicit failure states.
 */

#include <algorithm>
#include <exception>
#include <iomanip>
#include <iostream>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

enum class InstanceState {
    Stopped,
    Running,
    Terminated
};

enum class Protocol {
    TCP,
    UDP,
    All
};

enum class RuleAction {
    Allow,
    Deny
};

struct SecurityRule {
    Protocol protocol;
    int port;
    std::string sourceSubnet;
    RuleAction action;

    bool matches(Protocol requestedProtocol,
                 int requestedPort,
                 const std::string& sourceIp) const {
        bool protocolMatch =
            protocol == Protocol::All ||
            protocol == requestedProtocol;

        bool portMatch =
            port == -1 ||
            port == requestedPort;

        // This simplified case study represents CIDR matching through the
        // subnet prefix stored by the policy. Production systems should use
        // binary CIDR calculations rather than string-prefix checks.
        bool sourceMatch =
            sourceSubnet == "0.0.0.0/0" ||
            sourceIp.rfind(
                sourceSubnet.substr(0, sourceSubnet.find_last_of('.') + 1),
                0
            ) == 0;

        return protocolMatch && portMatch && sourceMatch;
    }
};

class SecurityGroup {
private:
    std::string name_;
    std::vector<SecurityRule> inbound_;

public:
    explicit SecurityGroup(std::string name)
        : name_(std::move(name)) {}

    void addInboundRule(const SecurityRule& rule) {
        inbound_.push_back(rule);
    }

    bool allowsInbound(Protocol protocol,
                       int port,
                       const std::string& sourceIp) const {
        bool matched = false;

        for (const auto& rule : inbound_) {
            if (rule.matches(protocol, port, sourceIp)) {
                matched = true;

                // Explicit deny wins when both allow and deny rules match.
                if (rule.action == RuleAction::Deny) {
                    return false;
                }
            }
        }

        return matched;
    }

    const std::string& name() const {
        return name_;
    }
};

class VirtualNetwork {
private:
    std::string name_;
    std::string cidr_;
    std::set<std::string> subnets_;

public:
    VirtualNetwork(std::string name, std::string cidr)
        : name_(std::move(name)), cidr_(std::move(cidr)) {}

    void addSubnet(const std::string& subnet) {
        if (subnets_.contains(subnet)) {
            throw std::invalid_argument(
                "Duplicate subnet: " + subnet
            );
        }

        subnets_.insert(subnet);
    }

    const std::string& name() const {
        return name_;
    }

    const std::string& cidr() const {
        return cidr_;
    }

    const std::set<std::string>& subnets() const {
        return subnets_;
    }
};

class ComputeInstance {
private:
    std::string id_;
    std::string hostname_;
    std::string subnet_;
    std::string privateIp_;
    std::string securityGroup_;
    InstanceState state_;
    std::set<std::string> volumes_;

public:
    ComputeInstance(std::string id,
                    std::string hostname,
                    std::string subnet,
                    std::string privateIp,
                    std::string securityGroup)
        : id_(std::move(id)),
          hostname_(std::move(hostname)),
          subnet_(std::move(subnet)),
          privateIp_(std::move(privateIp)),
          securityGroup_(std::move(securityGroup)),
          state_(InstanceState::Stopped) {}

    void start() {
        if (state_ == InstanceState::Terminated) {
            throw std::logic_error(
                "Terminated instance cannot start"
            );
        }

        state_ = InstanceState::Running;
    }

    void terminate() {
        state_ = InstanceState::Terminated;
    }

    void attachVolume(const std::string& volumeName) {
        if (state_ == InstanceState::Terminated) {
            throw std::logic_error(
                "Cannot attach storage to terminated instance"
            );
        }

        volumes_.insert(volumeName);
    }

    InstanceState state() const {
        return state_;
    }

    const std::string& id() const {
        return id_;
    }

    const std::string& privateIp() const {
        return privateIp_;
    }

    const std::string& securityGroup() const {
        return securityGroup_;
    }

    const std::set<std::string>& volumes() const {
        return volumes_;
    }
};

class BlockVolume {
private:
    std::string name_;
    std::size_t sizeGb_;
    bool encrypted_;
    std::optional<std::string> attachedInstance_;

public:
    BlockVolume(std::string name,
                std::size_t sizeGb,
                bool encrypted)
        : name_(std::move(name)),
          sizeGb_(sizeGb),
          encrypted_(encrypted) {
        if (sizeGb == 0) {
            throw std::invalid_argument(
                "Volume size must be greater than zero"
            );
        }
    }

    void attach(const std::string& instanceId) {
        if (attachedInstance_.has_value()) {
            throw std::logic_error(
                "Volume is already attached"
            );
        }

        attachedInstance_ = instanceId;
    }

    const std::string& name() const {
        return name_;
    }

    bool encrypted() const {
        return encrypted_;
    }
};

class GovernanceEngine {
private:
    std::unordered_map<std::string, VirtualNetwork> networks_;
    std::unordered_map<std::string, SecurityGroup> groups_;
    std::unordered_map<std::string, ComputeInstance> instances_;
    std::unordered_map<std::string, BlockVolume> volumes_;

public:
    void addNetwork(VirtualNetwork network) {
        const auto key = network.name();

        if (networks_.contains(key)) {
            throw std::invalid_argument(
                "Network already exists: " + key
            );
        }

        networks_.emplace(key, std::move(network));
    }

    void addSecurityGroup(SecurityGroup group) {
        const auto key = group.name();

        if (groups_.contains(key)) {
            throw std::invalid_argument(
                "Security group already exists: " + key
            );
        }

        groups_.emplace(key, std::move(group));
    }

    void addInstance(ComputeInstance instance) {
        const auto key = instance.id();

        if (instances_.contains(key)) {
            throw std::invalid_argument(
                "Instance already exists: " + key
            );
        }

        instances_.emplace(key, std::move(instance));
    }

    void addVolume(BlockVolume volume) {
        const auto key = volume.name();

        if (volumes_.contains(key)) {
            throw std::invalid_argument(
                "Volume already exists: " + key
            );
        }

        volumes_.emplace(key, std::move(volume));
    }

    ComputeInstance& instance(const std::string& id) {
        auto it = instances_.find(id);

        if (it == instances_.end()) {
            throw std::out_of_range(
                "Unknown instance: " + id
            );
        }

        return it->second;
    }

    BlockVolume& volume(const std::string& name) {
        auto it = volumes_.find(name);

        if (it == volumes_.end()) {
            throw std::out_of_range(
                "Unknown volume: " + name
            );
        }

        return it->second;
    }

    bool canCommunicate(const std::string& sourceId,
                        const std::string& destinationId,
                        Protocol protocol,
                        int port) const {
        auto sourceIt = instances_.find(sourceId);
        auto destinationIt = instances_.find(destinationId);

        if (sourceIt == instances_.end() ||
            destinationIt == instances_.end()) {
            throw std::out_of_range(
                "Communication endpoint does not exist"
            );
        }

        const auto& source = sourceIt->second;
        const auto& destination = destinationIt->second;

        if (source.state() != InstanceState::Running ||
            destination.state() != InstanceState::Running) {
            return false;
        }

        auto groupIt =
            groups_.find(destination.securityGroup());

        if (groupIt == groups_.end()) {
            throw std::logic_error(
                "Destination security group is missing"
            );
        }

        return groupIt->second.allowsInbound(
            protocol,
            port,
            source.privateIp()
        );
    }

    void attachVolume(const std::string& volumeName,
                      const std::string& instanceId) {
        auto& volumeRef = volume(volumeName);
        auto& instanceRef = instance(instanceId);

        if (!volumeRef.encrypted()) {
            throw std::security_error(
                "Unencrypted block storage is prohibited"
            );
        }

        volumeRef.attach(instanceId);
        instanceRef.attachVolume(volumeName);
    }

    void printReport() const {
        std::cout << "\nInfrastructure report\n";
        std::cout << "Networks: " << networks_.size() << '\n';
        std::cout << "Security groups: " << groups_.size() << '\n';
        std::cout << "Compute instances: " << instances_.size() << '\n';
        std::cout << "Block volumes: " << volumes_.size() << '\n';

        for (const auto& [id, instance] : instances_) {
            std::cout
                << "  " << id
                << " IP=" << instance.privateIp()
                << " volumes=" << instance.volumes().size()
                << '\n';
        }
    }
};

int main() {
    try {
        GovernanceEngine cloud;

        VirtualNetwork productionVpc(
            "production-vpc",
            "10.0.0.0/16"
        );

        productionVpc.addSubnet("10.0.1.0/24");
        productionVpc.addSubnet("10.0.10.0/24");
        productionVpc.addSubnet("10.0.20.0/24");

        cloud.addNetwork(std::move(productionVpc));

        SecurityGroup webSecurity("web-sg");

        webSecurity.addInboundRule({
            Protocol::TCP,
            443,
            "0.0.0.0/0",
            RuleAction::Allow
        });

        webSecurity.addInboundRule({
            Protocol::TCP,
            22,
            "10.0.10.0/24",
            RuleAction::Allow
        });

        cloud.addSecurityGroup(std::move(webSecurity));

        SecurityGroup databaseSecurity("database-sg");

        databaseSecurity.addInboundRule({
            Protocol::TCP,
            5432,
            "10.0.10.0/24",
            RuleAction::Allow
        });

        cloud.addSecurityGroup(std::move(databaseSecurity));

        cloud.addInstance(
            ComputeInstance(
                "web-01",
                "web-server",
                "10.0.1.0/24",
                "10.0.1.10",
                "web-sg"
            )
        );

        cloud.addInstance(
            ComputeInstance(
                "app-01",
                "application-server",
                "10.0.10.0/24",
                "10.0.10.10",
                "web-sg"
            )
        );

        cloud.addInstance(
            ComputeInstance(
                "db-01",
                "database-server",
                "10.0.20.0/24",
                "10.0.20.10",
                "database-sg"
            )
        );

        cloud.instance("web-01").start();
        cloud.instance("app-01").start();
        cloud.instance("db-01").start();

        cloud.addVolume(
            BlockVolume(
                "database-data",
                100,
                true
            )
        );

        cloud.attachVolume(
            "database-data",
            "db-01"
        );

        bool applicationToDatabase =
            cloud.canCommunicate(
                "app-01",
                "db-01",
                Protocol::TCP,
                5432
            );

        bool webToDatabase =
            cloud.canCommunicate(
                "web-01",
                "db-01",
                Protocol::TCP,
                5432
            );

        std::cout
            << "Application -> database: "
            << std::boolalpha
            << applicationToDatabase
            << '\n';

        std::cout
            << "Web -> database: "
            << std::boolalpha
            << webToDatabase
            << '\n';

        try {
            cloud.instance("db-01").terminate();
            cloud.instance("db-01").start();
        } catch (const std::exception& error) {
            std::cout
                << "Lifecycle validation: "
                << error.what()
                << '\n';
        }

        cloud.printReport();

    } catch (const std::exception& error) {
        std::cerr
            << "Infrastructure operation failed: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
