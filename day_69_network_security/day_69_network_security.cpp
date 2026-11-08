#include <algorithm>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Network Security and Traffic Filtering Engine
 *
 * C++17 implementation of:
 * - IPv4 and CIDR matching
 * - Firewall rules
 * - Stateful connection tracking
 * - Security groups
 * - Stateless network ACLs
 * - Priority-based filtering
 * - Default-deny policies
 * - Multi-layer traffic inspection
 * - Security audit reporting
 *
 * Compile:
 * g++ -std=c++17 -Wall -Wextra -pedantic network_security.cpp -o network_security
 */

namespace network_security {

// -------------------------------------------------------
// Enumerations
// -------------------------------------------------------

enum class Protocol {
    TCP,
    UDP,
    ICMP,
    ANY
};

enum class Direction {
    INBOUND,
    OUTBOUND
};

enum class Action {
    ALLOW,
    DENY
};

// -------------------------------------------------------
// String Conversion
// -------------------------------------------------------

std::string toString(Protocol value) {
    switch (value) {
        case Protocol::TCP: return "TCP";
        case Protocol::UDP: return "UDP";
        case Protocol::ICMP: return "ICMP";
        case Protocol::ANY: return "ANY";
    }

    throw std::invalid_argument("Unknown protocol");
}

std::string toString(Action value) {
    return value == Action::ALLOW ? "ALLOW" : "DENY";
}

// -------------------------------------------------------
// IPv4 Address
// -------------------------------------------------------

class IPv4Address {
private:
    uint32_t value_;

public:
    explicit IPv4Address(const std::string& address) {
        std::istringstream input(address);
        std::string segment;

        uint32_t result = 0;
        int count = 0;

        while (std::getline(input, segment, '.')) {
            if (segment.empty() || segment.size() > 3) {
                throw std::invalid_argument("Invalid IPv4 address");
            }

            if (!std::all_of(
                segment.begin(), segment.end(),
                [](unsigned char c) { return c >= '0' && c <= '9'; }
            )) {
                throw std::invalid_argument("Invalid IPv4 octet");
            }

            int octet = std::stoi(segment);

            if (octet < 0 || octet > 255) {
                throw std::invalid_argument("IPv4 octet out of range");
            }

            result = (result << 8) | static_cast<uint32_t>(octet);
            ++count;
        }

        if (count != 4) {
            throw std::invalid_argument("IPv4 requires four octets");
        }

        value_ = result;
    }

    uint32_t value() const {
        return value_;
    }

    std::string toString() const {
        std::ostringstream output;

        output
            << ((value_ >> 24) & 255) << "."
            << ((value_ >> 16) & 255) << "."
            << ((value_ >> 8) & 255) << "."
            << (value_ & 255);

        return output.str();
    }
};

// -------------------------------------------------------
// CIDR Network
// -------------------------------------------------------

class CIDR {
private:
    uint32_t network_;
    uint32_t mask_;

public:
    explicit CIDR(const std::string& notation) {
        const auto separator = notation.find('/');

        if (separator == std::string::npos) {
            throw std::invalid_argument("CIDR prefix is required");
        }

        IPv4Address address(notation.substr(0, separator));

        int prefix = std::stoi(notation.substr(separator + 1));

        if (prefix < 0 || prefix > 32) {
            throw std::invalid_argument("CIDR prefix must be 0-32");
        }

        mask_ = prefix == 0
            ? 0
            : (0xFFFFFFFFu << (32 - prefix));

        network_ = address.value() & mask_;
    }

    bool contains(const IPv4Address& address) const {
        return (address.value() & mask_) == network_;
    }
};

// -------------------------------------------------------
// Network Packet
// -------------------------------------------------------

struct Packet {
    IPv4Address source;
    IPv4Address destination;
    uint16_t sourcePort;
    uint16_t destinationPort;
    Protocol protocol;
    Direction direction;

    Packet(
        const std::string& sourceIP,
        const std::string& destinationIP,
        int sourcePortValue,
        int destinationPortValue,
        Protocol protocolValue,
        Direction directionValue
    )
        : source(sourceIP),
          destination(destinationIP),
          sourcePort(validatePort(sourcePortValue)),
          destinationPort(validatePort(destinationPortValue)),
          protocol(protocolValue),
          direction(directionValue) {

        if (protocol == Protocol::ICMP &&
            (sourcePort != 0 || destinationPort != 0)) {
            throw std::invalid_argument(
                "ICMP packets cannot contain TCP/UDP ports"
            );
        }
    }

private:
    static uint16_t validatePort(int port) {
        if (port < 0 || port > 65535) {
            throw std::invalid_argument("Invalid network port");
        }

        return static_cast<uint16_t>(port);
    }
};

// -------------------------------------------------------
// Firewall Rule
// -------------------------------------------------------

struct FirewallRule {
    std::string id;
    std::string name;
    CIDR sourceNetwork;
    CIDR destinationNetwork;
    Protocol protocol;
    Direction direction;
    Action action;
    int priority;
    uint16_t portStart;
    uint16_t portEnd;
    bool enabled;

    FirewallRule(
        std::string ruleID,
        std::string ruleName,
        std::string sourceCIDR,
        std::string destinationCIDR,
        Protocol protocolValue,
        Direction directionValue,
        Action actionValue,
        int priorityValue,
        int startPort,
        int endPort,
        bool enabledValue = true
    )
        : id(std::move(ruleID)),
          name(std::move(ruleName)),
          sourceNetwork(sourceCIDR),
          destinationNetwork(destinationCIDR),
          protocol(protocolValue),
          direction(directionValue),
          action(actionValue),
          priority(priorityValue),
          portStart(validatePort(startPort)),
          portEnd(validatePort(endPort)),
          enabled(enabledValue) {

        if (id.empty() || name.empty()) {
            throw std::invalid_argument("Rule ID and name are required");
        }

        if (priority < 0) {
            throw std::invalid_argument("Priority cannot be negative");
        }

        if (portStart > portEnd) {
            throw std::invalid_argument("Invalid port range");
        }

        if (protocol == Protocol::ICMP &&
            (portStart != 0 || portEnd != 65535)) {
            throw std::invalid_argument("ICMP rules cannot restrict ports");
        }
    }

    bool matches(const Packet& packet) const {
        if (!enabled || direction != packet.direction) {
            return false;
        }

        if (protocol != Protocol::ANY &&
            protocol != packet.protocol) {
            return false;
        }

        if (!sourceNetwork.contains(packet.source) ||
            !destinationNetwork.contains(packet.destination)) {
            return false;
        }

        if (packet.protocol == Protocol::ICMP) {
            return true;
        }

        return packet.destinationPort >= portStart &&
               packet.destinationPort <= portEnd;
    }

private:
    static uint16_t validatePort(int port) {
        if (port < 0 || port > 65535) {
            throw std::invalid_argument("Invalid rule port");
        }

        return static_cast<uint16_t>(port);
    }
};

// -------------------------------------------------------
// Security Decision
// -------------------------------------------------------

struct Decision {
    bool allowed;
    std::string layer;
    std::string reason;
    std::string ruleID;
};

// -------------------------------------------------------
// Connection Tracking
// -------------------------------------------------------

struct Connection {
    uint32_t sourceIP;
    uint32_t destinationIP;
    uint16_t sourcePort;
    uint16_t destinationPort;
    Protocol protocol;

    bool operator<(const Connection& other) const {
        return std::tie(
            sourceIP,
            destinationIP,
            sourcePort,
            destinationPort,
            protocol
        ) < std::tie(
            other.sourceIP,
            other.destinationIP,
            other.sourcePort,
            other.destinationPort,
            other.protocol
        );
    }
};

class ConnectionTracker {
private:
    std::set<Connection> connections_;

    static Connection makeKey(
        const IPv4Address& source,
        const IPv4Address& destination,
        uint16_t sourcePort,
        uint16_t destinationPort,
        Protocol protocol
    ) {
        return {
            source.value(),
            destination.value(),
            sourcePort,
            destinationPort,
            protocol
        };
    }

public:
    void establish(const Packet& packet) {
        if (packet.protocol == Protocol::ICMP ||
            packet.protocol == Protocol::ANY) {
            return;
        }

        connections_.insert(makeKey(
            packet.source,
            packet.destination,
            packet.sourcePort,
            packet.destinationPort,
            packet.protocol
        ));
    }

    bool isReturnTraffic(const Packet& packet) const {
        return connections_.count(makeKey(
            packet.destination,
            packet.source,
            packet.destinationPort,
            packet.sourcePort,
            packet.protocol
        )) > 0;
    }

    void close(const Packet& packet) {
        connections_.erase(makeKey(
            packet.source,
            packet.destination,
            packet.sourcePort,
            packet.destinationPort,
            packet.protocol
        ));
    }

    size_t size() const {
        return connections_.size();
    }
};

// -------------------------------------------------------
// Policy Evaluator
// -------------------------------------------------------

class PolicyEvaluator {
private:
    std::vector<FirewallRule> rules_;
    bool stateful_;
    ConnectionTracker tracker_;

public:
    PolicyEvaluator(
        std::vector<FirewallRule> rules,
        bool stateful
    )
        : rules_(std::move(rules)),
          stateful_(stateful) {

        validateRules();

        std::sort(
            rules_.begin(),
            rules_.end(),
            [](const FirewallRule& a, const FirewallRule& b) {
                return a.priority < b.priority;
            }
        );
    }

    Decision evaluate(const Packet& packet) {
        if (stateful_ && tracker_.isReturnTraffic(packet)) {
            return {
                true,
                "STATEFUL",
                "ESTABLISHED_RETURN_TRAFFIC",
                ""
            };
        }

        for (const auto& rule : rules_) {
            if (!rule.matches(packet)) {
                continue;
            }

            bool allowed = rule.action == Action::ALLOW;

            if (allowed && stateful_) {
                tracker_.establish(packet);
            }

            return {
                allowed,
                "POLICY",
                "RULE_MATCH",
                rule.id
            };
        }

        return {
            false,
            "POLICY",
            "DEFAULT_DENY",
            ""
        };
    }

    size_t activeConnections() const {
        return tracker_.size();
    }

    void replaceRules(std::vector<FirewallRule> rules) {
        auto previous = std::move(rules_);

        rules_ = std::move(rules);

        try {
            validateRules();

            std::sort(
                rules_.begin(),
                rules_.end(),
                [](const FirewallRule& a, const FirewallRule& b) {
                    return a.priority < b.priority;
                }
            );
        } catch (...) {
            rules_ = std::move(previous);
            throw;
        }
    }

private:
    void validateRules() const {
        std::set<std::string> identifiers;

        for (const auto& rule : rules_) {
            if (!identifiers.insert(rule.id).second) {
                throw std::invalid_argument("Duplicate firewall rule ID");
            }
        }
    }
};

// -------------------------------------------------------
// Security Group
// -------------------------------------------------------

class SecurityGroup {
private:
    std::string id_;
    PolicyEvaluator evaluator_;

public:
    SecurityGroup(
        std::string id,
        std::vector<FirewallRule> rules
    )
        : id_(std::move(id)),
          evaluator_(std::move(rules), true) {}

    Decision inspect(const Packet& packet) {
        if (packet.direction != Direction::INBOUND) {
            throw std::invalid_argument(
                "Security group expects inbound traffic"
            );
        }

        return evaluator_.evaluate(packet);
    }
};

// -------------------------------------------------------
// Network ACL
// -------------------------------------------------------

class NetworkACL {
private:
    std::string id_;
    PolicyEvaluator evaluator_;

public:
    NetworkACL(
        std::string id,
        std::vector<FirewallRule> rules
    )
        : id_(std::move(id)),
          evaluator_(std::move(rules), false) {}

    Decision inspect(const Packet& packet) {
        return evaluator_.evaluate(packet);
    }
};

// -------------------------------------------------------
// Firewall
// -------------------------------------------------------

class Firewall {
private:
    PolicyEvaluator evaluator_;

public:
    explicit Firewall(std::vector<FirewallRule> rules)
        : evaluator_(std::move(rules), true) {}

    Decision inspect(const Packet& packet) {
        return evaluator_.evaluate(packet);
    }
};

// -------------------------------------------------------
// Network Security Gateway
// -------------------------------------------------------

class NetworkSecurityGateway {
private:
    Firewall firewall_;
    SecurityGroup securityGroup_;
    NetworkACL acl_;

    std::vector<Decision> audit_;

public:
    NetworkSecurityGateway(
        std::vector<FirewallRule> firewallRules,
        std::vector<FirewallRule> securityGroupRules,
        std::vector<FirewallRule> aclRules
    )
        : firewall_(std::move(firewallRules)),
          securityGroup_("WEB-SG", std::move(securityGroupRules)),
          acl_("PRODUCTION-ACL", std::move(aclRules)) {}

    Decision inspect(const Packet& packet) {
        Decision result = firewall_.inspect(packet);

        if (!result.allowed) {
            result.layer = "FIREWALL";
            audit_.push_back(result);
            return result;
        }

        if (packet.direction == Direction::INBOUND) {
            result = securityGroup_.inspect(packet);

            if (!result.allowed) {
                result.layer = "SECURITY_GROUP";
                audit_.push_back(result);
                return result;
            }
        }

        result = acl_.inspect(packet);

        if (!result.allowed) {
            result.layer = "NETWORK_ACL";
            audit_.push_back(result);
            return result;
        }

        result = {
            true,
            "ALL_LAYERS",
            "TRAFFIC_ALLOWED",
            ""
        };

        audit_.push_back(result);
        return result;
    }

    void report() const {
        size_t allowed = 0;
        size_t denied = 0;

        std::map<std::string, size_t> blockedBy;

        for (const auto& decision : audit_) {
            if (decision.allowed) {
                ++allowed;
            } else {
                ++denied;
                ++blockedBy[decision.layer];
            }
        }

        std::cout << "\nSECURITY AUDIT REPORT\n";
        std::cout << "Total: " << audit_.size() << "\n";
        std::cout << "Allowed: " << allowed << "\n";
        std::cout << "Denied: " << denied << "\n";

        for (const auto& item : blockedBy) {
            std::cout << item.first
                      << ": " << item.second << "\n";
        }
    }
};

// -------------------------------------------------------
// Application
// -------------------------------------------------------

void printDecision(
    const Packet& packet,
    const Decision& decision
) {
    std::cout
        << packet.source.toString()
        << " -> "
        << packet.destination.toString()
        << " | "
        << toString(packet.protocol)
        << " | "
        << toString(decision.allowed ? Action::ALLOW : Action::DENY)
        << " | "
        << decision.layer
        << " | "
        << decision.reason
        << " | Rule: "
        << (decision.ruleID.empty() ? "NONE" : decision.ruleID)
        << "\n";
}

} // namespace network_security

int main() {
    using namespace network_security;

    try {
        std::vector<FirewallRule> firewallRules = {
            {
                "FW001", "Internal HTTPS",
                "10.0.0.0/8", "172.16.0.0/12",
                Protocol::TCP, Direction::INBOUND,
                Action::ALLOW, 100, 443, 443
            },
            {
                "FW002", "Block HTTP",
                "0.0.0.0/0", "172.16.0.0/12",
                Protocol::TCP, Direction::INBOUND,
                Action::DENY, 200, 80, 80
            }
        };

        std::vector<FirewallRule> securityGroupRules = {
            {
                "SG001", "Application HTTPS",
                "10.0.0.0/8", "172.16.0.0/12",
                Protocol::TCP, Direction::INBOUND,
                Action::ALLOW, 100, 443, 443
            }
        };

        std::vector<FirewallRule> aclRules = {
            {
                "ACL001", "Inbound HTTPS",
                "10.0.0.0/8", "172.16.0.0/12",
                Protocol::TCP, Direction::INBOUND,
                Action::ALLOW, 100, 443, 443
            },
            {
                "ACL002", "Outbound HTTPS response",
                "172.16.0.0/12", "10.0.0.0/8",
                Protocol::TCP, Direction::OUTBOUND,
                Action::ALLOW, 100, 1024, 65535
            },
            {
                "ACL003", "Inbound DNS",
                "10.0.0.0/8", "172.16.0.0/12",
                Protocol::UDP, Direction::INBOUND,
                Action::ALLOW, 200, 53, 53
            }
        };

        NetworkSecurityGateway gateway(
            firewallRules,
            securityGroupRules,
            aclRules
        );

        std::vector<Packet> traffic;

        traffic.emplace_back(
            "10.1.1.10", "172.16.1.20",
            51000, 443, Protocol::TCP, Direction::INBOUND
        );

        traffic.emplace_back(
            "203.0.113.25", "172.16.1.20",
            51001, 80, Protocol::TCP, Direction::INBOUND
        );

        traffic.emplace_back(
            "10.1.1.10", "172.16.1.20",
            51002, 22, Protocol::TCP, Direction::INBOUND
        );

        traffic.emplace_back(
            "10.1.1.10", "172.16.1.20",
            51003, 53, Protocol::UDP, Direction::INBOUND
        );

        std::cout << "NETWORK SECURITY ENGINE\n\n";

        for (const auto& packet : traffic) {
            Decision decision = gateway.inspect(packet);
            printDecision(packet, decision);
        }

        Packet response(
            "172.16.1.20", "10.1.1.10",
            443, 51000, Protocol::TCP, Direction::OUTBOUND
        );

        std::cout << "\nSTATEFUL FIREWALL RETURN TEST\n";
        Decision returnDecision = gateway.inspect(response);
        printDecision(response, returnDecision);

        gateway.report();

        // Edge-case and security assertions.
        assert(gateway.inspect(traffic[0]).allowed);
        assert(!gateway.inspect(traffic[1]).allowed);
        assert(!gateway.inspect(traffic[2]).allowed);
        assert(gateway.inspect(traffic[3]).allowed);

        // Validate invalid addresses.
        bool rejected = false;

        try {
            IPv4Address invalid("300.1.1.1");
        } catch (const std::invalid_argument&) {
            rejected = true;
        }

        assert(rejected);

        // Validate CIDR boundaries.
        CIDR privateNetwork("10.0.0.0/8");

        assert(privateNetwork.contains(
            IPv4Address("10.255.255.254")
        ));

        assert(!privateNetwork.contains(
            IPv4Address("11.0.0.1")
        ));

        std::cout << "\nAll C++17 security tests passed.\n";

    } catch (const std::exception& error) {
        std::cerr
            << "Security engine error: "
            << error.what()
            << "\n";

        return 1;
    }

    return 0;
}
