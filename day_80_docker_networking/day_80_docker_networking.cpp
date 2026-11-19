#include <algorithm>
#include <cstdint>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

using namespace std;

enum class NetworkMode {
    BRIDGE,
    HOST,
    NONE
};

enum class MergeDecision {
    ALLOW,
    DENY
};

struct IPv4 {
    uint32_t value;

    static IPv4 parse(const string& address) {
        stringstream stream(address);
        string part;
        uint32_t result = 0;
        int count = 0;

        while (getline(stream, part, '.')) {
            if (part.empty() || part.size() > 3) {
                throw invalid_argument("Invalid IPv4 address.");
            }

            int octet;

            try {
                size_t position = 0;
                octet = stoi(part, &position);

                if (position != part.size()) {
                    throw invalid_argument("Invalid octet.");
                }
            } catch (...) {
                throw invalid_argument("Invalid IPv4 octet.");
            }

            if (octet < 0 || octet > 255) {
                throw invalid_argument("IPv4 octet out of range.");
            }

            result = (result << 8) | static_cast<uint32_t>(octet);
            count++;
        }

        if (count != 4) {
            throw invalid_argument("IPv4 requires four octets.");
        }

        return {result};
    }

    string toString() const {
        return to_string((value >> 24) & 255) + "." +
               to_string((value >> 16) & 255) + "." +
               to_string((value >> 8) & 255) + "." +
               to_string(value & 255);
    }
};

struct Network {
    string name;
    uint32_t networkAddress;
    uint32_t broadcastAddress;
    uint32_t gateway;
    bool internal;

    set<string> members;
    map<string, IPv4> addresses;

    Network(
        string networkName,
        const string& subnet,
        bool isInternal
    ) : name(move(networkName)), internal(isInternal) {

        size_t separator = subnet.find('/');

        if (separator == string::npos) {
            throw invalid_argument("CIDR notation required.");
        }

        IPv4 base = IPv4::parse(subnet.substr(0, separator));
        int prefix = stoi(subnet.substr(separator + 1));

        if (prefix < 16 || prefix > 29) {
            throw invalid_argument("Unsupported subnet prefix.");
        }

        uint32_t mask = 0xFFFFFFFFu << (32 - prefix);

        networkAddress = base.value & mask;
        broadcastAddress = networkAddress | ~mask;

        gateway = networkAddress + 1;
    }

    bool contains(uint32_t address) const {
        return address >= networkAddress &&
               address <= broadcastAddress;
    }

    IPv4 allocate() const {
        for (
            uint32_t current = networkAddress + 1;
            current < broadcastAddress;
            current++
        ) {
            if (current == gateway) {
                continue;
            }

            bool occupied = false;

            for (const auto& [name, address] : addresses) {
                if (address.value == current) {
                    occupied = true;
                    break;
                }
            }

            if (!occupied) {
                return {current};
            }
        }

        throw runtime_error("Network address pool exhausted.");
    }

    void attach(const string& container) {
        if (members.count(container)) {
            throw runtime_error("Container already connected.");
        }

        IPv4 address = allocate();

        members.insert(container);
        addresses[container] = address;
    }

    void detach(const string& container) {
        if (!members.count(container)) {
            throw runtime_error("Container is not connected.");
        }

        members.erase(container);
        addresses.erase(container);
    }
};

struct Container {
    string id;
    string name;
    string image;
    NetworkMode mode;

    bool running = true;

    set<int> exposedPorts;
    map<string, IPv4> networks;

    Container(
        string containerId,
        string containerName,
        string containerImage,
        NetworkMode networkMode,
        set<int> ports
    ) :
        id(move(containerId)),
        name(move(containerName)),
        image(move(containerImage)),
        mode(networkMode),
        exposedPorts(move(ports)) {

        if (id.empty() || name.empty() || image.empty()) {
            throw invalid_argument("Container fields are required.");
        }

        for (int port : exposedPorts) {
            validatePort(port);
        }
    }

    static void validatePort(int port) {
        if (port < 1 || port > 65535) {
            throw invalid_argument("Invalid network port.");
        }
    }
};

struct PortMapping {
    string container;
    string hostIP;
    int hostPort;
    int containerPort;
    string protocol;
};

struct Decision {
    MergeDecision result;
    string reason;
};

class DockerGovernanceEngine {
private:
    map<string, Network> networks;
    map<string, Container> containers;
    vector<PortMapping> mappings;

    Container& getContainer(const string& name) {
        auto it = containers.find(name);

        if (it == containers.end()) {
            throw runtime_error("Container not found: " + name);
        }

        if (!it->second.running) {
            throw runtime_error("Container is stopped: " + name);
        }

        return it->second;
    }

    Network& getNetwork(const string& name) {
        auto it = networks.find(name);

        if (it == networks.end()) {
            throw runtime_error("Network not found: " + name);
        }

        return it->second;
    }

public:
    void createNetwork(
        const string& name,
        const string& subnet,
        bool internal = false
    ) {
        if (networks.count(name)) {
            throw runtime_error("Duplicate network name.");
        }

        Network candidate(name, subnet, internal);

        for (const auto& [existingName, existing] : networks) {
            bool overlap =
                candidate.networkAddress <= existing.broadcastAddress &&
                existing.networkAddress <= candidate.broadcastAddress;

            if (overlap) {
                throw runtime_error("Overlapping network subnets.");
            }
        }

        networks.emplace(name, move(candidate));

        cout << "Network created: " << name << "\n";
    }

    void createContainer(
        const string& id,
        const string& name,
        const string& image,
        NetworkMode mode,
        const string& networkName,
        const set<int>& ports
    ) {
        if (containers.count(name)) {
            throw runtime_error("Duplicate container name.");
        }

        if (
            mode == NetworkMode::BRIDGE &&
            networkName.empty()
        ) {
            throw invalid_argument("Bridge network is required.");
        }

        if (
            mode != NetworkMode::BRIDGE &&
            !networkName.empty()
        ) {
            throw invalid_argument(
                "Host and none modes cannot join bridge networks."
            );
        }

        Container container(id, name, image, mode, ports);

        if (mode == NetworkMode::BRIDGE) {
            Network& network = getNetwork(networkName);

            network.attach(name);

            container.networks[networkName] =
                network.addresses.at(name);
        }

        containers.emplace(name, move(container));

        cout << "Container created: " << name << "\n";
    }

    void connectContainer(
        const string& containerName,
        const string& networkName
    ) {
        Container& container = getContainer(containerName);
        Network& network = getNetwork(networkName);

        if (container.mode != NetworkMode::BRIDGE) {
            throw runtime_error("Container cannot join bridge network.");
        }

        network.attach(containerName);

        container.networks[networkName] =
            network.addresses.at(containerName);

        cout << containerName << " connected to "
             << networkName << "\n";
    }

    void disconnectContainer(
        const string& containerName,
        const string& networkName
    ) {
        Container& container = getContainer(containerName);
        Network& network = getNetwork(networkName);

        network.detach(containerName);
        container.networks.erase(networkName);
    }

    string resolveDNS(
        const string& sourceName,
        const string& targetName,
        const string& networkName
    ) {
        Container& source = getContainer(sourceName);
        Container& target = getContainer(targetName);
        Network& network = getNetwork(networkName);

        if (
            !source.networks.count(networkName) ||
            !target.networks.count(networkName)
        ) {
            throw runtime_error("DNS resolution denied.");
        }

        if (!network.members.count(targetName)) {
            throw runtime_error("DNS record unavailable.");
        }

        return target.networks.at(networkName).toString();
    }

    Decision evaluateConnection(
        const string& sourceName,
        const string& targetName,
        int port
    ) {
        Container& source = getContainer(sourceName);
        Container& target = getContainer(targetName);

        Container::validatePort(port);

        if (sourceName == targetName) {
            return {MergeDecision::ALLOW, "Same container."};
        }

        if (
            source.mode == NetworkMode::NONE ||
            target.mode == NetworkMode::NONE
        ) {
            return {MergeDecision::DENY, "None network mode."};
        }

        if (
            source.mode == NetworkMode::HOST &&
            target.mode == NetworkMode::HOST
        ) {
            return {
                MergeDecision::ALLOW,
                "Shared host network namespace."
            };
        }

        if (
            source.mode != NetworkMode::BRIDGE ||
            target.mode != NetworkMode::BRIDGE
        ) {
            return {
                MergeDecision::DENY,
                "No supported bridge communication path."
            };
        }

        for (const auto& [networkName, sourceIP] : source.networks) {
            if (
                target.networks.count(networkName) &&
                target.exposedPorts.count(port)
            ) {
                return {
                    MergeDecision::ALLOW,
                    "Shared bridge network: " + networkName
                };
            }
        }

        return {
            MergeDecision::DENY,
            "No shared network or permitted destination port."
        };
    }

    void publishPort(
        const string& containerName,
        const string& hostIP,
        int hostPort,
        int containerPort,
        const string& protocol = "tcp"
    ) {
        Container& container = getContainer(containerName);

        Container::validatePort(hostPort);
        Container::validatePort(containerPort);

        if (container.mode != NetworkMode::BRIDGE) {
            throw runtime_error("Publishing requires bridge mode.");
        }

        IPv4::parse(hostIP);

        if (!container.exposedPorts.count(containerPort)) {
            throw runtime_error("Container port is not exposed.");
        }

        if (protocol != "tcp" && protocol != "udp") {
            throw invalid_argument("Invalid protocol.");
        }

        for (const auto& mapping : mappings) {
            bool addressConflict =
                mapping.hostIP == "0.0.0.0" ||
                hostIP == "0.0.0.0" ||
                mapping.hostIP == hostIP;

            if (
                addressConflict &&
                mapping.hostPort == hostPort &&
                mapping.protocol == protocol
            ) {
                throw runtime_error("Host port conflict.");
            }
        }

        mappings.push_back({
            containerName,
            hostIP,
            hostPort,
            containerPort,
            protocol
        });

        cout << "Published " << hostIP << ":" << hostPort
             << " -> " << containerName << ":"
             << containerPort << "\n";
    }

    bool externalAccess(
        int hostPort,
        int containerPort,
        const string& protocol = "tcp"
    ) {
        Container::validatePort(hostPort);
        Container::validatePort(containerPort);

        for (const auto& mapping : mappings) {
            auto it = containers.find(mapping.container);

            if (
                it != containers.end() &&
                it->second.running &&
                mapping.hostPort == hostPort &&
                mapping.containerPort == containerPort &&
                mapping.protocol == protocol
            ) {
                return true;
            }
        }

        return false;
    }

    void stopContainer(const string& name) {
        Container& container = getContainer(name);

        container.running = false;

        for (auto& [networkName, network] : networks) {
            if (network.members.count(name)) {
                network.detach(name);
            }
        }

        mappings.erase(
            remove_if(
                mappings.begin(),
                mappings.end(),
                [&](const PortMapping& mapping) {
                    return mapping.container == name;
                }
            ),
            mappings.end()
        );

        cout << "Stopped: " << name << "\n";
    }

    void printTopology() const {
        cout << "\nNETWORK TOPOLOGY\n";

        for (const auto& [name, network] : networks) {
            cout << "\n" << name
                 << " | internal=" << boolalpha
                 << network.internal << "\n";

            for (const auto& member : network.members) {
                cout << "  " << member << " -> "
                     << network.addresses.at(member).toString()
                     << "\n";
            }
        }

        cout << "\nCONTAINERS\n";

        for (const auto& [name, container] : containers) {
            cout << name
                 << " | running=" << boolalpha
                 << container.running << "\n";
        }
    }
};

int main() {
    try {
        DockerGovernanceEngine engine;

        engine.createNetwork(
            "frontend-net",
            "172.20.0.0/24"
        );

        engine.createNetwork(
            "backend-net",
            "172.21.0.0/24",
            true
        );

        engine.createContainer(
            "c001",
            "frontend",
            "nginx:stable",
            NetworkMode::BRIDGE,
            "frontend-net",
            {80}
        );

        engine.createContainer(
            "c002",
            "api",
            "python:3.13-slim",
            NetworkMode::BRIDGE,
            "frontend-net",
            {8000}
        );

        engine.connectContainer("api", "backend-net");

        engine.createContainer(
            "c003",
            "database",
            "postgres:18",
            NetworkMode::BRIDGE,
            "backend-net",
            {5432}
        );

        engine.createContainer(
            "c004",
            "host-monitor",
            "monitor:latest",
            NetworkMode::HOST,
            "",
            {9090}
        );

        cout << "\nSERVICE DISCOVERY\n";

        cout << "Database IP: "
             << engine.resolveDNS(
                 "api",
                 "database",
                 "backend-net"
             ) << "\n";

        cout << "\nCONNECTIVITY POLICY\n";

        vector<tuple<string, string, int>> tests = {
            {"frontend", "api", 8000},
            {"api", "database", 5432},
            {"frontend", "database", 5432}
        };

        for (const auto& [source, target, port] : tests) {
            Decision decision = engine.evaluateConnection(
                source,
                target,
                port
            );

            cout << source << " -> " << target
                 << ":" << port << " = "
                 << (
                     decision.result == MergeDecision::ALLOW
                     ? "ALLOWED"
                     : "DENIED"
                 )
                 << " | " << decision.reason << "\n";
        }

        engine.publishPort(
            "frontend",
            "127.0.0.1",
            8080,
            80
        );

        cout << "\nExternal access: "
             << boolalpha
             << engine.externalAccess(8080, 80)
             << "\n";

        engine.printTopology();

        // Isolation must be enforced even when both services
        // are operational and their destination ports are exposed.
        if (
            engine.evaluateConnection(
                "frontend", "database", 5432
            ).result != MergeDecision::DENY
        ) {
            throw runtime_error("Isolation validation failed.");
        }

        if (
            engine.evaluateConnection(
                "api", "database", 5432
            ).result != MergeDecision::ALLOW
        ) {
            throw runtime_error("Backend connectivity failed.");
        }

        cout << "\nALL NETWORK TESTS PASSED\n";

    } catch (const exception& error) {
        cerr << "ERROR: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
