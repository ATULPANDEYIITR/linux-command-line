/*
 * Introduction to Computer Networking
 *
 * Industry-style C++ case study:
 * A small enterprise network simulator models clients, switches, routers,
 * packets, routing tables, firewall decisions, services, and packet delivery.
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic networking_case_study.cpp -o networking
 *
 * Run:
 *   ./networking
 *
 * The program uses only the C++ standard library.
 */

#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

// ============================================================================
// 1. BASIC NETWORK ADDRESS REPRESENTATION
// ============================================================================

class IPv4Address {
private:
    uint32_t value_;

public:
    explicit IPv4Address(uint32_t value) : value_(value) {}

    static IPv4Address parse(const string& text) {
        stringstream stream(text);
        string part;
        vector<int> octets;

        while (getline(stream, part, '.')) {
            if (part.empty()) {
                throw invalid_argument("Invalid IPv4 address: " + text);
            }

            int value = stoi(part);

            if (value < 0 || value > 255) {
                throw invalid_argument("IPv4 octet out of range");
            }

            octets.push_back(value);
        }

        if (octets.size() != 4) {
            throw invalid_argument("IPv4 address requires four octets");
        }

        uint32_t result =
            (static_cast<uint32_t>(octets[0]) << 24) |
            (static_cast<uint32_t>(octets[1]) << 16) |
            (static_cast<uint32_t>(octets[2]) << 8) |
            static_cast<uint32_t>(octets[3]);

        return IPv4Address(result);
    }

    uint32_t value() const {
        return value_;
    }

    string toString() const {
        ostringstream output;

        output << ((value_ >> 24) & 255) << "."
               << ((value_ >> 16) & 255) << "."
               << ((value_ >> 8) & 255) << "."
               << (value_ & 255);

        return output.str();
    }

    bool operator==(const IPv4Address& other) const {
        return value_ == other.value_;
    }
};

// ============================================================================
// 2. CIDR NETWORK
// ============================================================================

class IPv4Network {
private:
    IPv4Address networkAddress_;
    int prefixLength_;

    static uint32_t prefixMask(int prefixLength) {
        if (prefixLength < 0 || prefixLength > 32) {
            throw invalid_argument("Prefix length must be 0..32");
        }

        if (prefixLength == 0) {
            return 0;
        }

        return 0xFFFFFFFFu << (32 - prefixLength);
    }

public:
    IPv4Network(const IPv4Address& address, int prefixLength)
        : prefixLength_(prefixLength) {
        uint32_t mask = prefixMask(prefixLength);
        uint32_t network = address.value() & mask;
        networkAddress_ = IPv4Address(network);
    }

    bool contains(const IPv4Address& address) const {
        uint32_t mask = prefixMask(prefixLength_);
        return (address.value() & mask) ==
               (networkAddress_.value() & mask);
    }

    int prefixLength() const {
        return prefixLength_;
    }

    IPv4Address networkAddress() const {
        return networkAddress_;
    }

    string toString() const {
        return networkAddress_.toString() + "/" +
               to_string(prefixLength_);
    }
};

// ============================================================================
// 3. PACKET MODEL
// ============================================================================

struct Packet {
    int id;
    IPv4Address source;
    IPv4Address destination;
    int sourcePort;
    int destinationPort;
    string protocol;
    string payload;
    vector<string> hops;
    int ttl;

    Packet(
        int packetId,
        IPv4Address sourceAddress,
        IPv4Address destinationAddress,
        int sourcePortNumber,
        int destinationPortNumber,
        string transportProtocol,
        string data
    )
        : id(packetId),
          source(sourceAddress),
          destination(destinationAddress),
          sourcePort(sourcePortNumber),
          destinationPort(destinationPortNumber),
          protocol(move(transportProtocol)),
          payload(move(data)),
          ttl(16) {}

    void addHop(const string& device) {
        hops.push_back(device);
    }

    bool decrementTTL() {
        if (ttl <= 0) {
            return false;
        }

        --ttl;
        return ttl > 0;
    }

    void print() const {
        cout << "Packet #" << id
             << " " << source.toString()
             << ":" << sourcePort
             << " -> "
             << destination.toString()
             << ":" << destinationPort
             << " protocol=" << protocol
             << " payload=\"" << payload << "\"\n";

        cout << "  TTL: " << ttl << "\n";
        cout << "  Hops: ";

        for (size_t i = 0; i < hops.size(); ++i) {
            if (i > 0) {
                cout << " -> ";
            }

            cout << hops[i];
        }

        cout << "\n";
    }
};

// ============================================================================
// 4. FIREWALL
// ============================================================================

enum class FirewallAction {
    Allow,
    Deny
};

struct FirewallRule {
    string protocol;
    int destinationPort;
    FirewallAction action;
};

class Firewall {
private:
    vector<FirewallRule> rules_;

public:
    void addRule(
        string protocol,
        int destinationPort,
        FirewallAction action
    ) {
        rules_.push_back(
            {move(protocol), destinationPort, action}
        );
    }

    FirewallAction evaluate(
        const string& protocol,
        int destinationPort
    ) const {
        for (const auto& rule : rules_) {
            if (
                rule.protocol == protocol &&
                rule.destinationPort == destinationPort
            ) {
                return rule.action;
            }
        }

        // Default deny demonstrates a restrictive security posture.
        return FirewallAction::Deny;
    }
};

// ============================================================================
// 5. SERVICES
// ============================================================================

class NetworkService {
private:
    string serviceName_;
    int port_;

public:
    NetworkService(string name, int port)
        : serviceName_(move(name)), port_(port) {}

    int port() const {
        return port_;
    }

    const string& name() const {
        return serviceName_;
    }

    string handle(const string& request) const {
        if (serviceName_ == "HTTPS") {
            if (request == "GET /") {
                return "HTTP/1.1 200 OK | enterprise portal";
            }

            return "HTTP/1.1 404 Not Found";
        }

        if (serviceName_ == "DNS") {
            return "DNS response for " + request;
        }

        if (serviceName_ == "SSH") {
            return "SSH service available";
        }

        return "Service response";
    }
};

// ============================================================================
// 6. HOST
// ============================================================================

class Host {
private:
    string name_;
    IPv4Address address_;
    Firewall firewall_;
    map<int, NetworkService> services_;

public:
    Host(string name, IPv4Address address)
        : name_(move(name)), address_(address) {}

    const string& name() const {
        return name_;
    }

    IPv4Address address() const {
        return address_;
    }

    void addFirewallRule(
        string protocol,
        int destinationPort,
        FirewallAction action
    ) {
        firewall_.addRule(
            move(protocol),
            destinationPort,
            action
        );
    }

    void addService(const NetworkService& service) {
        services_.emplace(service.port(), service);
    }

    optional<string> receive(Packet& packet) {
        if (
            firewall_.evaluate(
                packet.protocol,
                packet.destinationPort
            ) == FirewallAction::Deny
        ) {
            return nullopt;
        }

        auto service = services_.find(packet.destinationPort);

        if (service == services_.end()) {
            return nullopt;
        }

        packet.addHop(name_);

        return service->second.handle(packet.payload);
    }
};

// ============================================================================
// 7. ROUTING TABLE
// ============================================================================

struct Route {
    IPv4Network network;
    string nextHop;
    int metric;
};

class Router {
private:
    string name_;
    vector<Route> routes_;

public:
    explicit Router(string name)
        : name_(move(name)) {}

    const string& name() const {
        return name_;
    }

    void addRoute(
        const IPv4Network& network,
        string nextHop,
        int metric
    ) {
        routes_.push_back(
            {network, move(nextHop), metric}
        );
    }

    optional<Route> lookup(const IPv4Address& destination) const {
        vector<Route> matches;

        for (const auto& route : routes_) {
            if (route.network.contains(destination)) {
                matches.push_back(route);
            }
        }

        if (matches.empty()) {
            return nullopt;
        }

        // Longest-prefix matching chooses the most specific route.
        sort(
            matches.begin(),
            matches.end(),
            [](const Route& left, const Route& right) {
                if (
                    left.network.prefixLength() !=
                    right.network.prefixLength()
                ) {
                    return left.network.prefixLength() >
                           right.network.prefixLength();
                }

                return left.metric < right.metric;
            }
        );

        return matches.front();
    }

    void printRoutes() const {
        cout << "Routing table for " << name_ << ":\n";

        for (const auto& route : routes_) {
            cout << "  "
                 << left << setw(18)
                 << route.network.toString()
                 << " -> "
                 << setw(10)
                 << route.nextHop
                 << " metric="
                 << route.metric
                 << "\n";
        }
    }
};

// ============================================================================
// 8. ETHERNET SWITCH
// ============================================================================

class EthernetSwitch {
private:
    unordered_map<string, string> macTable_;

public:
    string receive(
        const string& sourceMac,
        const string& destinationMac,
        const string& ingressPort
    ) {
        // Learning occurs from the source MAC address.
        macTable_[sourceMac] = ingressPort;

        auto destination = macTable_.find(destinationMac);

        if (destination == macTable_.end()) {
            return "FLOOD";
        }

        return "FORWARD -> " + destination->second;
    }

    void printTable() const {
        cout << "Switch MAC table:\n";

        for (const auto& [mac, port] : macTable_) {
            cout << "  " << mac << " -> " << port << "\n";
        }
    }
};

// ============================================================================
// 9. NETWORK TOPOLOGY
// ============================================================================

class EnterpriseNetwork {
private:
    EthernetSwitch accessSwitch_;
    Router edgeRouter_;
    Host webServer_;
    Host dnsServer_;

public:
    EnterpriseNetwork()
        : edgeRouter_("EDGE-R1"),
          webServer_(
              "WEB-01",
              IPv4Address::parse("10.20.30.10")
          ),
          dnsServer_(
              "DNS-01",
              IPv4Address::parse("10.20.30.53")
          ) {
        configure();
    }

    void configure() {
        IPv4Network localNetwork(
            IPv4Address::parse("10.20.30.0"),
            24
        );

        IPv4Network enterpriseNetwork(
            IPv4Address::parse("10.20.0.0"),
            16
        );

        IPv4Network defaultNetwork(
            IPv4Address::parse("0.0.0.0"),
            0
        );

        edgeRouter_.addRoute(
            localNetwork,
            "LOCAL",
            1
        );

        edgeRouter_.addRoute(
            enterpriseNetwork,
            "INTERNAL",
            10
        );

        edgeRouter_.addRoute(
            defaultNetwork,
            "ISP",
            100
        );

        webServer_.addFirewallRule(
            "TCP",
            443,
            FirewallAction::Allow
        );

        webServer_.addFirewallRule(
            "TCP",
            22,
            FirewallAction::Allow
        );

        webServer_.addService(
            NetworkService("HTTPS", 443)
        );

        webServer_.addService(
            NetworkService("SSH", 22)
        );

        dnsServer_.addFirewallRule(
            "UDP",
            53,
            FirewallAction::Allow
        );

        dnsServer_.addService(
            NetworkService("DNS", 53)
        );
    }

    void showInfrastructure() const {
        cout << "\nInfrastructure:\n";
        cout << "  Access switch: Layer-2 forwarding device\n";
        cout << "  " << edgeRouter_.name()
             << ": Layer-3 routing device\n";
        cout << "  " << webServer_.name()
             << ": HTTPS application server\n";
        cout << "  " << dnsServer_.name()
             << ": DNS application server\n";

        edgeRouter_.printRoutes();
    }

    void demonstrateSwitchLearning() {
        cout << "\nSwitch learning demonstration:\n";

        cout
            << "Frame 1: "
            << accessSwitch_.receive(
                "AA:AA:AA:AA:AA:01",
                "BB:BB:BB:BB:BB:02",
                "port1"
            )
            << "\n";

        cout
            << "Frame 2: "
            << accessSwitch_.receive(
                "BB:BB:BB:BB:BB:02",
                "AA:AA:AA:AA:AA:01",
                "port2"
            )
            << "\n";

        cout
            << "Frame 3: "
            << accessSwitch_.receive(
                "AA:AA:AA:AA:AA:01",
                "BB:BB:BB:BB:BB:02",
                "port1"
            )
            << "\n";

        accessSwitch_.printTable();
    }

    void sendWebRequest() {
        cout << "\nWeb request case study:\n";

        Packet packet(
            1001,
            IPv4Address::parse("10.20.30.25"),
            webServer_.address(),
            51500,
            443,
            "TCP",
            "GET /"
        );

        packet.addHop("CLIENT-01");

        auto route = edgeRouter_.lookup(packet.destination);

        if (!route) {
            cout << "No route to destination.\n";
            return;
        }

        cout << "Router selected route "
             << route->network.toString()
             << " via "
             << route->nextHop
             << ".\n";

        packet.addHop(edgeRouter_.name());

        if (!packet.decrementTTL()) {
            cout << "Packet expired during routing.\n";
            return;
        }

        auto response = webServer_.receive(packet);

        if (!response) {
            cout << "Firewall denied request or service unavailable.\n";
            packet.print();
            return;
        }

        cout << "Server response: "
             << *response
             << "\n";

        packet.print();
    }

    void sendBlockedRequest() {
        cout << "\nFirewall failure case:\n";

        Packet packet(
            1002,
            IPv4Address::parse("10.20.30.25"),
            webServer_.address(),
            51501,
            23,
            "TCP",
            "UNAUTHORIZED"
        );

        packet.addHop("CLIENT-01");
        packet.addHop(edgeRouter_.name());

        auto response = webServer_.receive(packet);

        if (!response) {
            cout
                << "Request denied because TCP/23 is not allowed.\n";
        }
    }

    void demonstrateDnsRequest() {
        cout << "\nDNS request case:\n";

        Packet packet(
            1003,
            IPv4Address::parse("10.20.30.25"),
            dnsServer_.address(),
            52000,
            53,
            "UDP",
            "example.internal"
        );

        packet.addHop("CLIENT-01");
        packet.addHop(edgeRouter_.name());

        auto response = dnsServer_.receive(packet);

        if (response) {
            cout << *response << "\n";
        } else {
            cout << "DNS request failed.\n";
        }
    }
};

// ============================================================================
// 10. PERFORMANCE MODEL
// ============================================================================

class NetworkLink {
private:
    double bandwidthMbps_;
    double latencyMs_;

public:
    NetworkLink(double bandwidthMbps, double latencyMs)
        : bandwidthMbps_(bandwidthMbps),
          latencyMs_(latencyMs) {
        if (bandwidthMbps <= 0 || latencyMs < 0) {
            throw invalid_argument("Invalid network link");
        }
    }

    double transmissionTimeMs(size_t bytes) const {
        double megabits =
            static_cast<double>(bytes) * 8.0 / 1'000'000.0;

        return (megabits / bandwidthMbps_) * 1000.0;
    }

    double totalApproximateTimeMs(size_t bytes) const {
        return latencyMs_ + transmissionTimeMs(bytes);
    }
};

// ============================================================================
// 11. APPLICATION MESSAGE VALIDATION
// ============================================================================

class ApplicationProtocol {
public:
    static string buildRequest(
        const string& method,
        const string& path
    ) {
        if (method.empty()) {
            throw invalid_argument("HTTP method cannot be empty");
        }

        if (path.empty() || path.front() != '/') {
            throw invalid_argument("Path must begin with '/'");
        }

        if (path.find('\r') != string::npos ||
            path.find('\n') != string::npos) {
            throw invalid_argument("Path contains forbidden characters");
        }

        return method + " " + path + " HTTP/1.1";
    }
};

// ============================================================================
// 12. TESTING
// ============================================================================

void runTests() {
    cout << "\n" << string(78, '=') << "\n";
    cout << "SELF-TESTS\n";
    cout << string(78, '=') << "\n";

    auto address = IPv4Address::parse("192.168.1.10");

    if (address.toString() != "192.168.1.10") {
        throw runtime_error("IPv4 conversion test failed");
    }

    IPv4Network subnet(
        IPv4Address::parse("192.168.1.0"),
        24
    );

    if (!subnet.contains(
        IPv4Address::parse("192.168.1.25")
    )) {
        throw runtime_error("Subnet membership test failed");
    }

    if (subnet.contains(
        IPv4Address::parse("192.168.2.25")
    )) {
        throw runtime_error("Subnet exclusion test failed");
    }

    Router router("TEST-R1");

    router.addRoute(
        IPv4Network(
            IPv4Address::parse("0.0.0.0"),
            0
        ),
        "DEFAULT",
        100
    );

    router.addRoute(
        IPv4Network(
            IPv4Address::parse("10.0.0.0"),
            8
        ),
        "INTERNAL",
        10
    );

    auto route = router.lookup(
        IPv4Address::parse("10.20.30.40")
    );

    if (!route || route->nextHop != "INTERNAL") {
        throw runtime_error("Routing test failed");
    }

    NetworkLink link(100.0, 20.0);

    if (link.transmissionTimeMs(1500) <= 0) {
        throw runtime_error("Performance calculation failed");
    }

    string request =
        ApplicationProtocol::buildRequest(
            "GET",
            "/"
        );

    if (request != "GET / HTTP/1.1") {
        throw runtime_error("Protocol formatting test failed");
    }

    cout << "All tests passed.\n";
}

// ============================================================================
// 13. COMPLEXITY DISCUSSION
// ============================================================================

void printComplexityNotes() {
    cout << "\n" << string(78, '=') << "\n";
    cout << "COMPLEXITY AND DESIGN NOTES\n";
    cout << string(78, '=') << "\n";

    cout << "Routing lookup:\n";
    cout << "  This educational router scans all routes and sorts matches.\n";
    cout << "  A production router uses optimized forwarding structures.\n\n";

    cout << "Switch MAC lookup:\n";
    cout << "  unordered_map provides expected O(1) lookup.\n\n";

    cout << "Service lookup:\n";
    cout << "  std::map provides O(log n) lookup by port.\n\n";

    cout << "Packet forwarding:\n";
    cout << "  Real forwarding devices optimize the data plane for very high rates.\n";
}

// ============================================================================
// 14. MAIN CASE STUDY
// ============================================================================

int main() {
    try {
        cout << string(78, '=') << "\n";
        cout << "INTRODUCTION TO COMPUTER NETWORKING\n";
        cout << "C++ ENTERPRISE NETWORK CASE STUDY\n";
        cout << string(78, '=') << "\n";

        cout << "\nScenario:\n";
        cout << "A client accesses an HTTPS service inside an enterprise network.\n";
        cout << "The network contains a Layer-2 switch, a Layer-3 router,\n";
        cout << "an HTTPS server, and a DNS server.\n";

        EnterpriseNetwork network;

        network.showInfrastructure();
        network.demonstrateSwitchLearning();
        network.sendWebRequest();
        network.sendBlockedRequest();
        network.demonstrateDnsRequest();

        NetworkLink link(
            1000.0,
            12.0
        );

        cout << "\nPerformance calculation:\n";
        cout << "A 1500-byte payload over a 1 Gbps link has an approximate\n";
        cout << "serialization time of "
             << fixed
             << setprecision(4)
             << link.transmissionTimeMs(1500)
             << " ms.\n";

        cout << "Including modeled propagation/queue latency: "
             << link.totalApproximateTimeMs(1500)
             << " ms.\n";

        runTests();
        printComplexityNotes();

        cout << "\nSecurity design considerations:\n";
        cout << "  - Default-deny firewall behavior limits unintended exposure.\n";
        cout << "  - Application input is validated before processing.\n";
        cout << "  - Packet TTL limits indefinite forwarding loops.\n";
        cout << "  - Production systems require authenticated and encrypted communication.\n";
        cout << "  - Logs should avoid credentials and sensitive payloads.\n";

        cout << "\nFailure conditions represented by this case study:\n";
        cout << "  - Invalid IPv4 address\n";
        cout << "  - Missing route\n";
        cout << "  - Expired TTL\n";
        cout << "  - Firewall denial\n";
        cout << "  - Unknown service port\n";
        cout << "  - Invalid application request\n";

        cout << "\n" << string(78, '=') << "\n";
        cout << "END OF C++ NETWORKING CASE STUDY\n";
        cout << string(78, '=') << "\n";

        return 0;
    } catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << "\n";
        return 1;
    }
}
