/*
 * Routing and NAT
 *
 * C++17 case study:
 * A small enterprise network with:
 *   - clients
 *   - an edge router
 *   - a core router
 *   - routing tables
 *   - longest-prefix matching
 *   - default gateway behavior
 *   - packet forwarding
 *   - TTL
 *   - NAT/PAT
 *   - stateful firewall behavior
 *   - neighbor resolution
 *   - route metrics
 *   - troubleshooting
 *
 * Build:
 *   g++ -std=c++17 -O2 routing_nat.cpp -o routing_nat
 *
 * This program is a simulation. It does not transmit real network packets.
 */

#include <algorithm>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using IPv4 = std::uint32_t;


// ============================================================================
// 1. IPv4 ADDRESS IMPLEMENTATION
// ============================================================================

class IPv4Address {
private:
    IPv4 value_;

public:
    explicit IPv4Address(IPv4 value = 0)
        : value_(value) {}

    explicit IPv4Address(const std::string& text) {
        std::stringstream stream(text);

        unsigned int a, b, c, d;
        char dot1, dot2, dot3;

        if (
            !(stream >> a >> dot1 >> b >> dot2 >> c >> dot3 >> d) ||
            dot1 != '.' ||
            dot2 != '.' ||
            dot3 != '.' ||
            a > 255 ||
            b > 255 ||
            c > 255 ||
            d > 255
        ) {
            throw std::invalid_argument(
                "Invalid IPv4 address: " + text
            );
        }

        value_ =
            (static_cast<IPv4>(a) << 24) |
            (static_cast<IPv4>(b) << 16) |
            (static_cast<IPv4>(c) << 8) |
            static_cast<IPv4>(d);
    }

    IPv4 value() const {
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

    bool operator==(const IPv4Address& other) const {
        return value_ == other.value_;
    }

    bool operator!=(const IPv4Address& other) const {
        return !(*this == other);
    }

    bool operator<(const IPv4Address& other) const {
        return value_ < other.value_;
    }
};


std::ostream& operator<<(
    std::ostream& output,
    const IPv4Address& address
) {
    output << address.toString();
    return output;
}


// ============================================================================
// 2. NETWORK PREFIX
// ============================================================================

class IPv4Network {
private:
    IPv4 network_;
    unsigned int prefixLength_;

    static IPv4 maskForPrefix(unsigned int prefixLength) {
        if (prefixLength > 32) {
            throw std::invalid_argument(
                "Prefix length must be between 0 and 32"
            );
        }

        if (prefixLength == 0) {
            return 0;
        }

        return 0xFFFFFFFFu << (32 - prefixLength);
    }

public:
    IPv4Network(
        const IPv4Address& address,
        unsigned int prefixLength
    )
        : prefixLength_(prefixLength) {

        IPv4 mask = maskForPrefix(prefixLength);

        network_ =
            address.value() & mask;
    }

    static IPv4Network fromCIDR(
        const std::string& cidr
    ) {
        const std::size_t slash = cidr.find('/');

        if (slash == std::string::npos) {
            throw std::invalid_argument(
                "CIDR notation requires '/'"
            );
        }

        const std::string address =
            cidr.substr(0, slash);

        const std::string prefix =
            cidr.substr(slash + 1);

        unsigned long parsedPrefix =
            std::stoul(prefix);

        return IPv4Network(
            IPv4Address(address),
            static_cast<unsigned int>(parsedPrefix)
        );
    }

    bool contains(
        const IPv4Address& address
    ) const {
        IPv4 mask = maskForPrefix(prefixLength_);

        return (
            address.value() & mask
        ) == network_;
    }

    unsigned int prefixLength() const {
        return prefixLength_;
    }

    IPv4Address networkAddress() const {
        return IPv4Address(network_);
    }

    std::string toString() const {
        return networkAddress().toString()
            + "/"
            + std::to_string(prefixLength_);
    }
};


// ============================================================================
// 3. PACKET
// ============================================================================

struct Packet {
    IPv4Address source;
    IPv4Address destination;

    std::string protocol = "TCP";

    std::optional<unsigned int> sourcePort;
    std::optional<unsigned int> destinationPort;

    unsigned int ttl = 64;
    std::size_t payloadBytes = 100;

    std::vector<std::string> path;

    std::string describe() const {
        std::ostringstream output;

        output
            << source;

        if (sourcePort && destinationPort) {
            output
                << ":"
                << *sourcePort
                << " -> :"
                << *destinationPort;
        }

        output
            << " -> "
            << destination
            << " "
            << protocol
            << " TTL="
            << ttl;

        return output.str();
    }
};


// ============================================================================
// 4. ROUTE
// ============================================================================

struct Route {
    IPv4Network destination;
    std::optional<IPv4Address> nextHop;
    std::string interfaceName;

    int metric = 1;
    int administrativeDistance = 0;

    std::string source = "connected";

    bool matches(
        const IPv4Address& address
    ) const {
        return destination.contains(address);
    }
};


// ============================================================================
// 5. ROUTING TABLE
// ============================================================================

class RoutingTable {
private:
    std::vector<Route> routes_;

public:
    void addRoute(const Route& route) {
        routes_.push_back(route);
    }

    std::optional<Route> lookup(
        const IPv4Address& destination
    ) const {
        std::vector<Route> matches;

        for (const auto& route : routes_) {
            if (route.matches(destination)) {
                matches.push_back(route);
            }
        }

        if (matches.empty()) {
            return std::nullopt;
        }

        // Longest-prefix matching:
        // the most specific destination network wins.
        std::sort(
            matches.begin(),
            matches.end(),
            [](const Route& left, const Route& right) {
                if (
                    left.destination.prefixLength() !=
                    right.destination.prefixLength()
                ) {
                    return
                        left.destination.prefixLength() >
                        right.destination.prefixLength();
                }

                if (
                    left.administrativeDistance !=
                    right.administrativeDistance
                ) {
                    return
                        left.administrativeDistance <
                        right.administrativeDistance;
                }

                return left.metric < right.metric;
            }
        );

        return matches.front();
    }

    void display() const {
        std::cout
            << std::left
            << std::setw(20) << "Destination"
            << std::setw(18) << "Next Hop"
            << std::setw(14) << "Interface"
            << std::setw(8) << "Metric"
            << std::setw(8) << "AD"
            << "Source\n";

        std::cout
            << std::string(78, '-')
            << "\n";

        for (const auto& route : routes_) {
            std::string nextHop =
                route.nextHop
                    ? route.nextHop->toString()
                    : "direct";

            std::cout
                << std::left
                << std::setw(20)
                << route.destination.toString()
                << std::setw(18)
                << nextHop
                << std::setw(14)
                << route.interfaceName
                << std::setw(8)
                << route.metric
                << std::setw(8)
                << route.administrativeDistance
                << route.source
                << "\n";
        }
    }
};


// ============================================================================
// 6. ROUTER
// ============================================================================

class Router {
protected:
    std::string name_;

    std::map<
        std::string,
        IPv4Address
    > interfaces_;

    RoutingTable routingTable_;

public:
    explicit Router(std::string name)
        : name_(std::move(name)) {}

    virtual ~Router() = default;

    const std::string& name() const {
        return name_;
    }

    void addInterface(
        const std::string& interfaceName,
        const IPv4Address& address,
        unsigned int prefixLength
    ) {
        interfaces_[interfaceName] = address;

        IPv4Network network(
            address,
            prefixLength
        );

        // Directly connected networks do not need another
        // router as their next hop.
        routingTable_.addRoute({
            network,
            std::nullopt,
            interfaceName,
            0,
            0,
            "connected"
        });
    }

    void addStaticRoute(
        const IPv4Network& destination,
        const IPv4Address& nextHop,
        const std::string& interfaceName,
        int metric = 1
    ) {
        routingTable_.addRoute({
            destination,
            nextHop,
            interfaceName,
            metric,
            1,
            "static"
        });
    }

    void addDefaultRoute(
        const IPv4Address& nextHop,
        const std::string& interfaceName,
        int metric = 1
    ) {
        addStaticRoute(
            IPv4Network(
                IPv4Address("0.0.0.0"),
                0
            ),
            nextHop,
            interfaceName,
            metric
        );
    }

    std::optional<Route> forward(
        Packet& packet
    ) {
        packet.path.push_back(name_);

        if (packet.ttl <= 1) {
            throw std::runtime_error(
                name_ + ": TTL expired"
            );
        }

        --packet.ttl;

        return routingTable_.lookup(
            packet.destination
        );
    }

    void showInterfaces() const {
        std::cout
            << "\nInterfaces for "
            << name_
            << ":\n";

        for (const auto& [name, address] : interfaces_) {
            std::cout
                << "  "
                << std::left
                << std::setw(14)
                << name
                << address
                << "\n";
        }
    }

    void showRoutingTable() const {
        routingTable_.display();
    }
};


// ============================================================================
// 7. NAT/PAT
// ============================================================================

struct NatKey {
    IPv4Address privateIp;
    unsigned int privatePort;
    IPv4Address remoteIp;
    unsigned int remotePort;
    std::string protocol;

    bool operator<(const NatKey& other) const {
        return std::tie(
            privateIp,
            privatePort,
            remoteIp,
            remotePort,
            protocol
        ) <
        std::tie(
            other.privateIp,
            other.privatePort,
            other.remoteIp,
            other.remotePort,
            other.protocol
        );
    }
};


struct NatTranslation {
    IPv4Address privateIp;
    unsigned int privatePort;

    IPv4Address publicIp;
    unsigned int publicPort;

    IPv4Address remoteIp;
    unsigned int remotePort;

    std::string protocol;
};


class NatTable {
private:
    IPv4Address publicIp_;
    unsigned int nextPort_;

    std::map<NatKey, NatTranslation> outbound_;

    std::map<
        std::tuple<IPv4Address, unsigned int, std::string>,
        NatTranslation
    > inbound_;

    unsigned int allocatePort() {
        for (unsigned int attempts = 0;
             attempts < 20000;
             ++attempts) {

            unsigned int candidate = nextPort_++;

            if (nextPort_ > 60000) {
                nextPort_ = 40000;
            }

            bool occupied = false;

            for (const auto& [key, translation] : outbound_) {
                if (
                    translation.publicPort ==
                    candidate
                ) {
                    occupied = true;
                    break;
                }
            }

            if (!occupied) {
                return candidate;
            }
        }

        throw std::runtime_error(
            "NAT port pool exhausted"
        );
    }

public:
    explicit NatTable(
        IPv4Address publicIp,
        unsigned int firstPort = 40000
    )
        : publicIp_(publicIp),
          nextPort_(firstPort) {}

    NatTranslation translateOutbound(
        const IPv4Address& privateIp,
        unsigned int privatePort,
        const IPv4Address& remoteIp,
        unsigned int remotePort,
        const std::string& protocol
    ) {
        NatKey key{
            privateIp,
            privatePort,
            remoteIp,
            remotePort,
            protocol
        };

        auto existing = outbound_.find(key);

        if (existing != outbound_.end()) {
            return existing->second;
        }

        unsigned int publicPort =
            allocatePort();

        NatTranslation translation{
            privateIp,
            privatePort,
            publicIp_,
            publicPort,
            remoteIp,
            remotePort,
            protocol
        };

        outbound_[key] = translation;

        inbound_[
            std::make_tuple(
                publicIp_,
                publicPort,
                protocol
            )
        ] = translation;

        return translation;
    }

    std::optional<NatTranslation> translateInbound(
        unsigned int publicPort,
        const IPv4Address& destinationIp,
        const std::string& protocol
    ) const {
        auto key = std::make_tuple(
            destinationIp,
            publicPort,
            protocol
        );

        auto found = inbound_.find(key);

        if (found == inbound_.end()) {
            return std::nullopt;
        }

        return found->second;
    }

    void display() const {
        std::cout
            << std::left
            << std::setw(26)
            << "Private"
            << std::setw(26)
            << "Public"
            << std::setw(26)
            << "Remote"
            << "Protocol\n";

        std::cout
            << std::string(88, '-')
            << "\n";

        for (const auto& [key, translation] : outbound_) {
            std::string privateEndpoint =
                translation.privateIp.toString()
                + ":"
                + std::to_string(
                    translation.privatePort
                );

            std::string publicEndpoint =
                translation.publicIp.toString()
                + ":"
                + std::to_string(
                    translation.publicPort
                );

            std::string remoteEndpoint =
                translation.remoteIp.toString()
                + ":"
                + std::to_string(
                    translation.remotePort
                );

            std::cout
                << std::left
                << std::setw(26)
                << privateEndpoint
                << std::setw(26)
                << publicEndpoint
                << std::setw(26)
                << remoteEndpoint
                << translation.protocol
                << "\n";
        }
    }
};


// ============================================================================
// 8. STATEFUL FIREWALL
// ============================================================================

struct Connection {
    IPv4Address sourceIp;
    unsigned int sourcePort;

    IPv4Address destinationIp;
    unsigned int destinationPort;

    std::string protocol;
};


class StatefulFirewall {
private:
    struct ConnectionComparator {
        bool operator()(
            const Connection& left,
            const Connection& right
        ) const {
            return std::tie(
                left.sourceIp,
                left.sourcePort,
                left.destinationIp,
                left.destinationPort,
                left.protocol
            ) <
            std::tie(
                right.sourceIp,
                right.sourcePort,
                right.destinationIp,
                right.destinationPort,
                right.protocol
            );
        }
    };

    std::set<Connection, ConnectionComparator> connections_;

public:
    bool allowOutbound(
        const Connection& connection
    ) {
        connections_.insert(connection);
        return true;
    }

    bool allowInbound(
        const Connection& inbound
    ) const {
        Connection reverse{
            inbound.destinationIp,
            inbound.destinationPort,
            inbound.sourceIp,
            inbound.sourcePort,
            inbound.protocol
        };

        return connections_.find(reverse)
            != connections_.end();
    }
};


// ============================================================================
// 9. NEIGHBOR CACHE
// ============================================================================

class NeighborCache {
private:
    std::map<
        IPv4Address,
        std::string
    > entries_;

public:
    void learn(
        const IPv4Address& address,
        const std::string& mac
    ) {
        entries_[address] = mac;
    }

    std::optional<std::string> resolve(
        const IPv4Address& address
    ) const {
        auto found = entries_.find(address);

        if (found == entries_.end()) {
            return std::nullopt;
        }

        return found->second;
    }
};


// ============================================================================
// 10. ENTERPRISE NETWORK
// ============================================================================

class EnterpriseNetwork {
private:
    Router edge_;
    Router core_;

    NatTable nat_;

    StatefulFirewall firewall_;

    NeighborCache neighbors_;

public:
    EnterpriseNetwork()
        : edge_("EDGE"),
          core_("CORE"),
          nat_(IPv4Address("198.51.100.10")) {

        configure();
    }

    void configure() {
        // User LAN.
        edge_.addInterface(
            "LAN",
            IPv4Address("192.168.50.1"),
            24
        );

        // Router-to-router transit network.
        edge_.addInterface(
            "TRANSIT",
            IPv4Address("10.0.0.1"),
            30
        );

        core_.addInterface(
            "TRANSIT",
            IPv4Address("10.0.0.2"),
            30
        );

        core_.addInterface(
            "WAN",
            IPv4Address("198.51.100.1"),
            30
        );

        // The edge router sends unknown destinations toward CORE.
        edge_.addDefaultRoute(
            IPv4Address("10.0.0.2"),
            "TRANSIT"
        );

        // CORE knows how to return traffic to the user LAN.
        core_.addStaticRoute(
            IPv4Network::fromCIDR(
                "192.168.50.0/24"
            ),
            IPv4Address("10.0.0.1"),
            "TRANSIT"
        );

        // Simulated ARP cache.
        neighbors_.learn(
            IPv4Address("10.0.0.2"),
            "02:00:00:00:00:02"
        );

        neighbors_.learn(
            IPv4Address("10.0.0.1"),
            "02:00:00:00:00:01"
        );
    }

    void sendToInternet(
        const IPv4Address& sourceIp,
        unsigned int sourcePort,
        const IPv4Address& destinationIp,
        unsigned int destinationPort
    ) {
        Packet packet{
            sourceIp,
            destinationIp,
            "TCP",
            sourcePort,
            destinationPort,
            64,
            100,
            {}
        };

        std::cout
            << "\nClient creates:\n  "
            << packet.describe()
            << "\n";

        // Step 1: EDGE performs a route lookup.
        auto edgeRoute =
            edge_.forward(packet);

        if (!edgeRoute) {
            throw std::runtime_error(
                "EDGE: no route to destination"
            );
        }

        std::cout
            << "EDGE forwards through "
            << edgeRoute->interfaceName
            << ", next-hop="
            << (
                edgeRoute->nextHop
                    ? edgeRoute->nextHop->toString()
                    : destinationIp.toString()
            )
            << ", TTL="
            << packet.ttl
            << "\n";

        // Step 2: CORE performs another route lookup.
        auto coreRoute =
            core_.forward(packet);

        if (!coreRoute) {
            throw std::runtime_error(
                "CORE: no route to destination"
            );
        }

        std::cout
            << "CORE forwards through "
            << coreRoute->interfaceName
            << ", next-hop="
            << (
                coreRoute->nextHop
                    ? coreRoute->nextHop->toString()
                    : destinationIp.toString()
            )
            << ", TTL="
            << packet.ttl
            << "\n";

        // Step 3: Stateful firewall creates outbound state.
        Connection connection{
            sourceIp,
            sourcePort,
            destinationIp,
            destinationPort,
            "TCP"
        };

        if (!firewall_.allowOutbound(connection)) {
            throw std::runtime_error(
                "Firewall denied outbound traffic"
            );
        }

        // Step 4: NAT/PAT rewrites the source endpoint.
        NatTranslation translation =
            nat_.translateOutbound(
                sourceIp,
                sourcePort,
                destinationIp,
                destinationPort,
                "TCP"
            );

        std::cout
            << "NAT translation:\n  "
            << translation.privateIp
            << ":"
            << translation.privatePort
            << " -> "
            << translation.publicIp
            << ":"
            << translation.publicPort
            << "\n";

        // Step 5: The remote Internet server sees the public endpoint.
        std::cout
            << "Remote server sees source "
            << translation.publicIp
            << ":"
            << translation.publicPort
            << "\n";

        // Step 6: Return packet is matched against NAT state.
        auto reverse =
            nat_.translateInbound(
                translation.publicPort,
                translation.publicIp,
                "TCP"
            );

        if (!reverse) {
            throw std::runtime_error(
                "Return packet has no NAT state"
            );
        }

        std::cout
            << "NAT restores destination to "
            << reverse->privateIp
            << ":"
            << reverse->privatePort
            << "\n";

        // Step 7: Stateful firewall recognizes the return flow.
        Connection returnConnection{
            reverse->remoteIp,
            reverse->remotePort,
            reverse->privateIp,
            reverse->privatePort,
            reverse->protocol
        };

        bool allowed =
            firewall_.allowInbound(
                returnConnection
            );

        std::cout
            << "Stateful firewall return decision: "
            << std::boolalpha
            << allowed
            << "\n";
    }

    void showRoutingTables() const {
        std::cout
            << "\nEDGE routing table:\n";

        edge_.showRoutingTable();

        std::cout
            << "\nCORE routing table:\n";

        core_.showRoutingTable();
    }

    void showNeighborResolution() const {
        std::cout
            << "\nNeighbor resolution:\n";

        auto result =
            neighbors_.resolve(
                IPv4Address("10.0.0.2")
            );

        if (result) {
            std::cout
                << "10.0.0.2 -> "
                << *result
                << "\n";
        } else {
            std::cout
                << "10.0.0.2 -> unresolved\n";
        }
    }

    void showNatTable() const {
        std::cout
            << "\nNAT table:\n";

        nat_.display();
    }
};


// ============================================================================
// 11. ROUTING LOOP CASE STUDY
// ============================================================================

void demonstrateRoutingLoop() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "ROUTING LOOP AND TTL\n"
        << std::string(78, '=')
        << "\n";

    Router routerA("R-A");
    Router routerB("R-B");

    routerA.addInterface(
        "LINK",
        IPv4Address("10.0.0.1"),
        24
    );

    routerB.addInterface(
        "LINK",
        IPv4Address("10.0.0.2"),
        24
    );

    routerA.addStaticRoute(
        IPv4Network::fromCIDR("172.16.0.0/16"),
        IPv4Address("10.0.0.2"),
        "LINK"
    );

    routerB.addStaticRoute(
        IPv4Network::fromCIDR("172.16.0.0/16"),
        IPv4Address("10.0.0.1"),
        "LINK"
    );

    Packet packet{
        IPv4Address("192.168.1.10"),
        IPv4Address("172.16.10.10"),
        "ICMP",
        std::nullopt,
        std::nullopt,
        5,
        64,
        {}
    };

    for (int hop = 0; hop < 10; ++hop) {
        Router& current =
            (hop % 2 == 0)
                ? routerA
                : routerB;

        try {
            auto route =
                current.forward(packet);

            std::cout
                << current.name()
                << ": TTL="
                << packet.ttl;

            if (route) {
                std::cout
                    << ", next-hop="
                    << (
                        route->nextHop
                            ? route->nextHop->toString()
                            : "direct"
                    );
            }

            std::cout
                << "\n";
        }
        catch (const std::exception& error) {
            std::cout
                << current.name()
                << ": "
                << error.what()
                << "\n";
            break;
        }
    }
}


// ============================================================================
// 12. ROUTE AGGREGATION
// ============================================================================

void demonstrateRouteAggregation() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "ROUTE AGGREGATION\n"
        << std::string(78, '=')
        << "\n";

    std::vector<std::string> specificRoutes{
        "10.10.0.0/24",
        "10.10.1.0/24",
        "10.10.2.0/24",
        "10.10.3.0/24"
    };

    for (const auto& route : specificRoutes) {
        std::cout
            << "  "
            << route
            << "\n";
    }

    std::cout
        << "Aggregate representation: 10.10.0.0/22\n";

    std::cout
        << "Aggregation can reduce routing-table entries when the "
           "address allocation is contiguous and aligned correctly.\n";
}


// ============================================================================
// 13. ROUTING VERSUS SWITCHING
// ============================================================================

void compareRoutingAndSwitching() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "ROUTING VERSUS SWITCHING\n"
        << std::string(78, '=')
        << "\n";

    std::cout
        << std::left
        << std::setw(24) << "Concept"
        << std::setw(28) << "Routing"
        << "Switching\n";

    std::cout
        << std::string(78, '-')
        << "\n";

    std::cout
        << std::setw(24) << "Address"
        << std::setw(28) << "IP"
        << "MAC\n";

    std::cout
        << std::setw(24) << "Primary structure"
        << std::setw(28) << "Routing table"
        << "MAC address table\n";

    std::cout
        << std::setw(24) << "Main decision"
        << std::setw(28) << "Destination network"
        << "Destination MAC\n";

    std::cout
        << std::setw(24) << "Typical role"
        << std::setw(28) << "Connect networks"
        << "Connect local Ethernet hosts\n";
}


// ============================================================================
// 14. TESTING
// ============================================================================

void require(
    bool condition,
    const std::string& message
) {
    if (!condition) {
        throw std::runtime_error(
            "Test failed: " + message
        );
    }
}


void testIPv4Conversion() {
    IPv4Address address("192.168.1.10");

    require(
        address.toString() == "192.168.1.10",
        "IPv4 conversion"
    );
}


void testNetworkMembership() {
    IPv4Network network =
        IPv4Network::fromCIDR(
            "192.168.1.0/24"
        );

    require(
        network.contains(
            IPv4Address("192.168.1.50")
        ),
        "address should belong to network"
    );

    require(
        !network.contains(
            IPv4Address("192.168.2.50")
        ),
        "address should not belong to network"
    );
}


void testLongestPrefix() {
    RoutingTable table;

    table.addRoute({
        IPv4Network::fromCIDR("0.0.0.0/0"),
        IPv4Address("192.168.1.1"),
        "WAN",
        100,
        1,
        "static"
    });

    table.addRoute({
        IPv4Network::fromCIDR("10.0.0.0/8"),
        IPv4Address("192.168.1.2"),
        "CORE",
        20,
        1,
        "static"
    });

    table.addRoute({
        IPv4Network::fromCIDR("10.20.0.0/16"),
        IPv4Address("192.168.1.3"),
        "CORE",
        10,
        1,
        "static"
    });

    auto route =
        table.lookup(
            IPv4Address("10.20.30.40")
        );

    require(
        route.has_value(),
        "route should exist"
    );

    require(
        route->destination.toString()
            == "10.20.0.0/16",
        "longest prefix must win"
    );
}


void testNatRoundTrip() {
    NatTable nat(
        IPv4Address("203.0.113.10")
    );

    NatTranslation translation =
        nat.translateOutbound(
            IPv4Address("192.168.1.10"),
            50000,
            IPv4Address("93.184.216.34"),
            443,
            "TCP"
        );

    auto reverse =
        nat.translateInbound(
            translation.publicPort,
            translation.publicIp,
            "TCP"
        );

    require(
        reverse.has_value(),
        "NAT reverse translation must exist"
    );

    require(
        reverse->privateIp
            == IPv4Address("192.168.1.10"),
        "NAT must restore private address"
    );

    require(
        reverse->privatePort == 50000,
        "NAT must restore private port"
    );
}


void testTtlExpiration() {
    Router router("TEST");

    router.addInterface(
        "LAN",
        IPv4Address("10.0.0.1"),
        24
    );

    Packet packet{
        IPv4Address("10.0.0.10"),
        IPv4Address("8.8.8.8"),
        "ICMP",
        std::nullopt,
        std::nullopt,
        1,
        64,
        {}
    };

    bool expired = false;

    try {
        router.forward(packet);
    }
    catch (const std::exception& error) {
        expired =
            std::string(error.what())
                .find("TTL expired")
                != std::string::npos;
    }

    require(
        expired,
        "TTL expiration must be detected"
    );
}


void runTests() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "AUTOMATED TESTS\n"
        << std::string(78, '=')
        << "\n";

    struct Test {
        std::string name;
        void (*function)();
    };

    std::vector<Test> tests{
        {"IPv4 conversion", testIPv4Conversion},
        {"Network membership", testNetworkMembership},
        {"Longest-prefix matching", testLongestPrefix},
        {"NAT round trip", testNatRoundTrip},
        {"TTL expiration", testTtlExpiration}
    };

    std::size_t passed = 0;

    for (const auto& test : tests) {
        try {
            test.function();
            std::cout
                << "PASS  "
                << test.name
                << "\n";
            ++passed;
        }
        catch (const std::exception& error) {
            std::cout
                << "FAIL  "
                << test.name
                << ": "
                << error.what()
                << "\n";
        }
    }

    std::cout
        << "\n"
        << passed
        << "/"
        << tests.size()
        << " tests passed.\n";
}


// ============================================================================
// 15. MAIN
// ============================================================================

int main() {
    try {
        std::cout
            << std::string(78, '=')
            << "\n"
            << "ROUTING AND NAT: C++ ENTERPRISE NETWORK CASE STUDY\n"
            << std::string(78, '=')
            << "\n";

        EnterpriseNetwork network;

        network.showRoutingTables();

        network.showNeighborResolution();

        network.sendToInternet(
            IPv4Address("192.168.50.25"),
            51500,
            IPv4Address("93.184.216.34"),
            443
        );

        network.showNatTable();

        demonstrateRoutingLoop();
        demonstrateRouteAggregation();
        compareRoutingAndSwitching();
        runTests();

        std::cout
            << "\n"
            << std::string(78, '=')
            << "\n"
            << "CASE STUDY COMPLETE\n"
            << std::string(78, '=')
            << "\n";
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }

    return 0;
}
