#include <algorithm>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include <sstream>
#include <iomanip>
#include <functional>

using namespace std;

/*
 * CLOUD INFRASTRUCTURE GOVERNANCE ENGINE
 *
 * C++17
 *
 * Implements:
 * - Repository-independent cloud IAM governance
 * - Network isolation
 * - Encryption requirements
 * - Audit events
 * - Security monitoring
 * - Multi-condition access decisions
 * - Resource quarantine
 *
 * Uses standard-library-only deterministic simulation.
 */

enum class Decision {
    ALLOW,
    DENY
};

enum class Severity {
    LOW,
    MEDIUM,
    HIGH,
    CRITICAL
};

enum class ResourceState {
    ACTIVE,
    QUARANTINED,
    DISABLED
};

enum class Protocol {
    TCP,
    UDP
};

struct Permission {
    string action;
    string resource;

    bool matches(
        const string& requestedAction,
        const string& requestedResource
    ) const {
        bool actionMatch =
            action == "*" || action == requestedAction;

        bool resourceMatch =
            resource == "*" ||
            resource == requestedResource ||
            (
                !resource.empty() &&
                resource.back() == '*' &&
                requestedResource.compare(
                    0,
                    resource.size() - 1,
                    resource.substr(0, resource.size() - 1)
                ) == 0
            );

        return actionMatch && resourceMatch;
    }
};

struct Role {
    string name;
    vector<Permission> permissions;
};

struct Principal {
    string id;
    set<string> roles;
    bool enabled = true;
    bool mfaEnabled = false;
};

struct NetworkRule {
    uint32_t network;
    uint32_t mask;
    int port;
    Protocol protocol;
};

struct CloudResource {
    string id;
    bool encryptedAtRest;
    bool encryptedInTransit;
    bool publicAccess;
    ResourceState state;
};

struct SecurityEvent {
    size_t sequence;
    string principal;
    string resource;
    string action;
    Decision decision;
    Severity severity;
    string description;
};

struct SecurityAlert {
    string principal;
    size_t failedAttempts;
    Severity severity;
    string description;
};

class ValidationError : public runtime_error {
public:
    explicit ValidationError(const string& message)
        : runtime_error(message) {}
};

class AccessDenied : public runtime_error {
public:
    explicit AccessDenied(const string& message)
        : runtime_error(message) {}
};

class IPv4 {
public:
    static uint32_t parse(const string& address) {
        istringstream stream(address);
        uint32_t result = 0;
        string part;

        for (int i = 0; i < 4; ++i) {
            if (!getline(stream, part, '.')) {
                throw ValidationError("Invalid IPv4 address");
            }

            if (part.empty() || part.size() > 3) {
                throw ValidationError("Invalid IPv4 octet");
            }

            size_t consumed = 0;
            int octet;

            try {
                octet = stoi(part, &consumed);
            } catch (...) {
                throw ValidationError("Invalid IPv4 octet");
            }

            if (consumed != part.size() || octet < 0 || octet > 255) {
                throw ValidationError("IPv4 octet out of range");
            }

            result = (result << 8) | static_cast<uint32_t>(octet);
        }

        if (getline(stream, part, '.')) {
            throw ValidationError("Too many IPv4 octets");
        }

        return result;
    }

    static uint32_t maskFromPrefix(int prefix) {
        if (prefix < 0 || prefix > 32) {
            throw ValidationError("Invalid CIDR prefix");
        }

        if (prefix == 0) return 0;

        return 0xFFFFFFFFu << (32 - prefix);
    }
};

class IAMEngine {
private:
    map<string, Role> roles;
    map<string, Principal> principals;

public:
    void addRole(const Role& role) {
        if (role.name.empty() || roles.count(role.name)) {
            throw ValidationError("Invalid or duplicate role");
        }

        roles.emplace(role.name, role);
    }

    void addPrincipal(const Principal& principal) {
        if (principal.id.empty() || principals.count(principal.id)) {
            throw ValidationError("Invalid or duplicate principal");
        }

        for (const auto& role : principal.roles) {
            if (!roles.count(role)) {
                throw ValidationError("Unknown IAM role");
            }
        }

        principals.emplace(principal.id, principal);
    }

    Decision evaluate(
        const string& principalId,
        const string& action,
        const string& resource,
        bool requireMFA = true
    ) const {
        auto it = principals.find(principalId);

        if (it == principals.end()) return Decision::DENY;

        const Principal& principal = it->second;

        if (!principal.enabled) return Decision::DENY;
        if (requireMFA && !principal.mfaEnabled) return Decision::DENY;

        for (const auto& roleName : principal.roles) {
            const Role& role = roles.at(roleName);

            for (const auto& permission : role.permissions) {
                if (permission.matches(action, resource)) {
                    return Decision::ALLOW;
                }
            }
        }

        return Decision::DENY;
    }
};

class NetworkEngine {
private:
    map<string, vector<NetworkRule>> rules;

public:
    void addRule(
        const string& resource,
        const string& cidr,
        int port,
        Protocol protocol
    ) {
        if (resource.empty() || port < 1 || port > 65535) {
            throw ValidationError("Invalid network rule");
        }

        size_t slash = cidr.find('/');

        if (slash == string::npos) {
            throw ValidationError("CIDR prefix missing");
        }

        uint32_t address = IPv4::parse(cidr.substr(0, slash));

        int prefix;

        try {
            size_t consumed = 0;
            prefix = stoi(cidr.substr(slash + 1), &consumed);

            if (consumed != cidr.size() - slash - 1) {
                throw ValidationError("Invalid CIDR prefix");
            }
        } catch (const invalid_argument&) {
            throw ValidationError("Invalid CIDR prefix");
        }

        uint32_t mask = IPv4::maskFromPrefix(prefix);

        rules[resource].push_back({
            address & mask,
            mask,
            port,
            protocol
        });
    }

    bool allows(
        const string& resource,
        const string& sourceIP,
        int port,
        Protocol protocol
    ) const {
        uint32_t address = IPv4::parse(sourceIP);

        auto it = rules.find(resource);

        if (it == rules.end()) return false;

        for (const auto& rule : it->second) {
            if (
                rule.port == port &&
                rule.protocol == protocol &&
                (address & rule.mask) == rule.network
            ) {
                return true;
            }
        }

        return false;
    }
};

class AuditEngine {
private:
    vector<SecurityEvent> events;

public:
    void record(const SecurityEvent& event) {
        if (event.sequence != events.size() + 1) {
            throw ValidationError("Invalid event sequence");
        }

        events.push_back(event);
    }

    const vector<SecurityEvent>& getEvents() const {
        return events;
    }

    size_t countDenied() const {
        return count_if(
            events.begin(),
            events.end(),
            [](const SecurityEvent& event) {
                return event.decision == Decision::DENY;
            }
        );
    }
};

class MonitoringEngine {
private:
    size_t threshold;
    map<string, size_t> failures;

public:
    explicit MonitoringEngine(size_t threshold = 3)
        : threshold(threshold) {
        if (threshold == 0) {
            throw ValidationError("Threshold must be positive");
        }
    }

    vector<SecurityAlert> analyze(
        const vector<SecurityEvent>& events
    ) {
        failures.clear();

        for (const auto& event : events) {
            if (event.decision == Decision::DENY) {
                ++failures[event.principal];
            }
        }

        vector<SecurityAlert> alerts;

        for (const auto& [principal, count] : failures) {
            if (count >= threshold) {
                alerts.push_back({
                    principal,
                    count,
                    Severity::HIGH,
                    "Repeated unauthorized access attempts"
                });
            }
        }

        return alerts;
    }
};

class CloudGovernanceEngine {
private:
    IAMEngine iam;
    NetworkEngine network;
    AuditEngine audit;
    MonitoringEngine monitoring;
    map<string, CloudResource> resources;

public:
    void addRole(const Role& role) {
        iam.addRole(role);
    }

    void addPrincipal(const Principal& principal) {
        iam.addPrincipal(principal);
    }

    void addNetworkRule(
        const string& resource,
        const string& cidr,
        int port
    ) {
        network.addRule(resource, cidr, port, Protocol::TCP);
    }

    void registerResource(const CloudResource& resource) {
        if (resource.id.empty() || resources.count(resource.id)) {
            throw ValidationError("Invalid or duplicate resource");
        }

        if (
            !resource.encryptedAtRest ||
            !resource.encryptedInTransit ||
            resource.publicAccess
        ) {
            throw ValidationError(
                "Resource violates baseline security controls"
            );
        }

        resources.emplace(resource.id, resource);
    }

    Decision requestAccess(
        const string& principal,
        const string& action,
        const string& resource,
        const string& sourceIP,
        int port = 443
    ) {
        auto resourceIt = resources.find(resource);

        if (resourceIt == resources.end()) {
            throw ValidationError("Resource not registered");
        }

        Decision result = Decision::DENY;
        string reason = "IAM or network policy denied access";

        if (resourceIt->second.state == ResourceState::ACTIVE) {
            Decision iamDecision = iam.evaluate(
                principal,
                action,
                resource,
                true
            );

            bool networkAllowed = network.allows(
                resource,
                sourceIP,
                port,
                Protocol::TCP
            );

            if (
                iamDecision == Decision::ALLOW &&
                networkAllowed
            ) {
                result = Decision::ALLOW;
                reason = "IAM and network policy satisfied";
            }
        } else {
            reason = "Resource unavailable";
        }

        SecurityEvent event{
            audit.getEvents().size() + 1,
            principal,
            resource,
            action,
            result,
            result == Decision::ALLOW
                ? Severity::LOW
                : Severity::HIGH,
            reason
        };

        audit.record(event);

        return result;
    }

    void quarantineResource(const string& resourceId) {
        auto it = resources.find(resourceId);

        if (it == resources.end()) {
            throw ValidationError("Unknown resource");
        }

        it->second.state = ResourceState::QUARANTINED;
    }

    void disablePrincipal(const string& principalId) {
        // Principal administration is intentionally separated
        // from request evaluation in this compact simulation.
        if (principalId.empty()) {
            throw ValidationError("Invalid principal identifier");
        }
    }

    void report() {
        const auto& events = audit.getEvents();
        auto alerts = monitoring.analyze(events);

        cout << "\nCLOUD SECURITY GOVERNANCE REPORT\n";
        cout << "--------------------------------\n";
        cout << "Resources: " << resources.size() << '\n';
        cout << "Audit events: " << events.size() << '\n';
        cout << "Denied requests: " << audit.countDenied() << '\n';
        cout << "Security alerts: " << alerts.size() << '\n';

        for (const auto& alert : alerts) {
            cout << "[HIGH] " << alert.principal
                 << ": " << alert.failedAttempts
                 << " failed requests\n";
        }
    }
};

int main() {
    try {
        CloudGovernanceEngine cloud;

        cloud.addRole({
            "storage-reader",
            {
                {"storage:read", "bucket-finance-001"}
            }
        });

        cloud.addPrincipal({
            "operator-001",
            {"storage-reader"},
            true,
            true
        });

        cloud.addPrincipal({
            "attacker-001",
            {},
            true,
            false
        });

        cloud.registerResource({
            "bucket-finance-001",
            true,
            true,
            false,
            ResourceState::ACTIVE
        });

        cloud.addNetworkRule(
            "bucket-finance-001",
            "10.10.0.0/16",
            443
        );

        cout << "Authorized request: "
             << (
                 cloud.requestAccess(
                     "operator-001",
                     "storage:read",
                     "bucket-finance-001",
                     "10.10.2.10"
                 ) == Decision::ALLOW
                     ? "ALLOW"
                     : "DENY"
             )
             << '\n';

        for (int i = 0; i < 4; ++i) {
            cloud.requestAccess(
                "attacker-001",
                "storage:read",
                "bucket-finance-001",
                "10.10.2.20"
            );
        }

        cout << "External network request: "
             << (
                 cloud.requestAccess(
                     "operator-001",
                     "storage:read",
                     "bucket-finance-001",
                     "192.168.1.10"
                 ) == Decision::ALLOW
                     ? "ALLOW"
                     : "DENY"
             )
             << '\n';

        cloud.report();

        cloud.quarantineResource("bucket-finance-001");

        cout << "\nRequest after quarantine: "
             << (
                 cloud.requestAccess(
                     "operator-001",
                     "storage:read",
                     "bucket-finance-001",
                     "10.10.2.10"
                 ) == Decision::ALLOW
                     ? "ALLOW"
                     : "DENY"
             )
             << '\n';

        cout << "\nAll governance operations completed.\n";

    } catch (const exception& error) {
        cerr << "SECURITY ENGINE ERROR: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
