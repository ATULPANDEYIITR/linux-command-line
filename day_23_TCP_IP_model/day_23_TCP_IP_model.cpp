/*
 * TCP/IP MODEL
 *
 * C++17 case study:
 * A small network-service simulation demonstrating how an application
 * request travels through the TCP/IP model.
 *
 * Layers modeled:
 *   Application
 *   Transport
 *   Internet
 *   Network Access
 *
 * The program deliberately separates conceptual protocol headers from
 * application data. It also implements routing-table lookup, IPv4
 * validation, CIDR calculations, TCP connection-state concepts,
 * application framing, validation, logging, and performance reasoning.
 */

#include <algorithm>
#include <array>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

// ============================================================================
// Utility functions
// ============================================================================

uint32_t ipv4ToInteger(const string& address) {
    stringstream stream(address);
    string part;
    array<uint32_t, 4> octets{};
    int index = 0;

    while (getline(stream, part, '.')) {
        if (index >= 4 || part.empty()) {
            throw invalid_argument("Invalid IPv4 address: " + address);
        }

        size_t consumed = 0;
        unsigned long value = stoul(part, &consumed);

        if (consumed != part.size() || value > 255) {
            throw invalid_argument("Invalid IPv4 address: " + address);
        }

        octets[index++] = static_cast<uint32_t>(value);
    }

    if (index != 4) {
        throw invalid_argument("Invalid IPv4 address: " + address);
    }

    return (octets[0] << 24) |
           (octets[1] << 16) |
           (octets[2] << 8) |
           octets[3];
}

string integerToIpv4(uint32_t value) {
    ostringstream output;

    output << ((value >> 24) & 0xFF) << "."
           << ((value >> 16) & 0xFF) << "."
           << ((value >> 8) & 0xFF) << "."
           << (value & 0xFF);

    return output.str();
}

uint32_t prefixMask(int prefixLength) {
    if (prefixLength < 0 || prefixLength > 32) {
        throw invalid_argument("IPv4 prefix length must be 0..32.");
    }

    if (prefixLength == 0) {
        return 0;
    }

    return 0xFFFFFFFFu << (32 - prefixLength);
}

void printSeparator() {
    cout << string(78, '=') << '\n';
}

// ============================================================================
// Application layer
// ============================================================================

struct HttpRequest {
    string method;
    string path;
    map<string, string> headers;
    string body;

    string serialize() const {
        ostringstream output;

        output << method << " " << path << " HTTP/1.1\n";

        for (const auto& [name, value] : headers) {
            output << name << ": " << value << '\n';
        }

        output << '\n';
        output << body;

        return output.str();
    }
};

struct HttpResponse {
    int statusCode;
    string reason;
    map<string, string> headers;
    string body;

    string serialize() const {
        ostringstream output;

        output << "HTTP/1.1 "
               << statusCode
               << " "
               << reason
               << '\n';

        for (const auto& [name, value] : headers) {
            output << name << ": " << value << '\n';
        }

        output << '\n';
        output << body;

        return output.str();
    }
};

// ============================================================================
// Transport layer
// ============================================================================

enum class TcpState {
    CLOSED,
    LISTEN,
    SYN_SENT,
    SYN_RECEIVED,
    ESTABLISHED,
    FIN_WAIT,
    CLOSE_WAIT,
};

string tcpStateName(TcpState state) {
    switch (state) {
        case TcpState::CLOSED:
            return "CLOSED";
        case TcpState::LISTEN:
            return "LISTEN";
        case TcpState::SYN_SENT:
            return "SYN-SENT";
        case TcpState::SYN_RECEIVED:
            return "SYN-RECEIVED";
        case TcpState::ESTABLISHED:
            return "ESTABLISHED";
        case TcpState::FIN_WAIT:
            return "FIN-WAIT";
        case TcpState::CLOSE_WAIT:
            return "CLOSE-WAIT";
    }

    return "UNKNOWN";
}

struct TcpSegment {
    uint32_t sequenceNumber = 0;
    uint32_t acknowledgmentNumber = 0;

    bool syn = false;
    bool ack = false;
    bool fin = false;
    bool rst = false;

    string payload;

    string describe() const {
        vector<string> flags;

        if (syn) flags.push_back("SYN");
        if (ack) flags.push_back("ACK");
        if (fin) flags.push_back("FIN");
        if (rst) flags.push_back("RST");

        string flagText;

        if (flags.empty()) {
            flagText = "-";
        } else {
            for (size_t i = 0; i < flags.size(); ++i) {
                if (i > 0) flagText += ",";
                flagText += flags[i];
            }
        }

        ostringstream output;

        output << "SEQ=" << sequenceNumber
               << " ACK=" << acknowledgmentNumber
               << " FLAGS=" << flagText
               << " PAYLOAD=" << payload.size()
               << " bytes";

        return output.str();
    }
};

class TcpConnection {
private:
    TcpState state = TcpState::CLOSED;

    uint32_t clientSequence = 1000;
    uint32_t serverSequence = 7000;

public:
    TcpState getState() const {
        return state;
    }

    vector<TcpSegment> establish() {
        vector<TcpSegment> packets;

        if (state != TcpState::CLOSED) {
            throw logic_error("TCP connection must start from CLOSED.");
        }

        state = TcpState::SYN_SENT;

        TcpSegment syn;
        syn.sequenceNumber = clientSequence;
        syn.syn = true;

        packets.push_back(syn);

        state = TcpState::SYN_RECEIVED;

        TcpSegment synAck;
        synAck.sequenceNumber = serverSequence;
        synAck.acknowledgmentNumber = clientSequence + 1;
        synAck.syn = true;
        synAck.ack = true;

        packets.push_back(synAck);

        state = TcpState::ESTABLISHED;

        TcpSegment ack;
        ack.sequenceNumber = clientSequence + 1;
        ack.acknowledgmentNumber = serverSequence + 1;
        ack.ack = true;

        packets.push_back(ack);

        return packets;
    }

    TcpSegment sendData(const string& data) {
        if (state != TcpState::ESTABLISHED) {
            throw logic_error("Data cannot be sent before TCP is established.");
        }

        TcpSegment segment;
        segment.sequenceNumber = clientSequence + 1;
        segment.acknowledgmentNumber = serverSequence + 1;
        segment.ack = true;
        segment.payload = data;

        clientSequence += static_cast<uint32_t>(data.size());

        return segment;
    }
};

// ============================================================================
// UDP model
// ============================================================================

struct UdpDatagram {
    uint16_t sourcePort;
    uint16_t destinationPort;
    string payload;

    string describe() const {
        ostringstream output;

        output << sourcePort
               << " -> "
               << destinationPort
               << ", payload="
               << payload.size()
               << " bytes";

        return output.str();
    }
};

// ============================================================================
// Internet layer
// ============================================================================

struct Ipv4Packet {
    string sourceAddress;
    string destinationAddress;
    uint8_t ttl = 64;
    uint8_t protocol = 6;
    string payload;

    string describe() const {
        ostringstream output;

        output << "IPv4 "
               << sourceAddress
               << " -> "
               << destinationAddress
               << " TTL="
               << static_cast<int>(ttl)
               << " protocol="
               << static_cast<int>(protocol)
               << " payload="
               << payload.size()
               << " bytes";

        return output.str();
    }
};

struct Route {
    string network;
    int prefixLength;
    string nextHop;
    uint32_t networkInteger;

    Route(
        string networkAddress,
        int prefix,
        string nextHopValue
    )
        : network(move(networkAddress)),
          prefixLength(prefix),
          nextHop(move(nextHopValue)),
          networkInteger(ipv4ToInteger(network)) {
        prefixMask(prefixLength);
    }

    bool matches(uint32_t destination) const {
        const uint32_t mask = prefixMask(prefixLength);

        return (destination & mask) ==
               (networkInteger & mask);
    }
};

class RoutingTable {
private:
    vector<Route> routes;

public:
    void addRoute(Route route) {
        routes.push_back(move(route));
    }

    const Route* lookup(const string& destination) const {
        const uint32_t destinationInteger =
            ipv4ToInteger(destination);

        const Route* bestMatch = nullptr;

        for (const auto& route : routes) {
            if (!route.matches(destinationInteger)) {
                continue;
            }

            if (
                bestMatch == nullptr ||
                route.prefixLength > bestMatch->prefixLength
            ) {
                bestMatch = &route;
            }
        }

        return bestMatch;
    }
};

// ============================================================================
// Network access layer
// ============================================================================

struct EthernetFrame {
    string destinationMac;
    string sourceMac;
    uint16_t etherType;
    string payload;

    string describe() const {
        ostringstream output;

        output << "Ethernet "
               << sourceMac
               << " -> "
               << destinationMac
               << " EtherType=0x"
               << hex
               << uppercase
               << setw(4)
               << setfill('0')
               << etherType
               << dec
               << " payload="
               << payload.size()
               << " bytes";

        return output.str();
    }
};

class ArpCache {
private:
    unordered_map<string, string> entries;

public:
    void insert(const string& ip, const string& mac) {
        entries[ip] = mac;
    }

    optional<string> lookup(const string& ip) const {
        auto iterator = entries.find(ip);

        if (iterator == entries.end()) {
            return nullopt;
        }

        return iterator->second;
    }
};

// ============================================================================
// Application protocol framing
// ============================================================================

class LengthPrefixedProtocol {
public:
    static string encode(const string& message) {
        if (message.size() > 0xFFFFFFFFu) {
            throw length_error("Message is too large.");
        }

        uint32_t length =
            static_cast<uint32_t>(message.size());

        string result(4, '\0');

        result[0] = static_cast<char>((length >> 24) & 0xFF);
        result[1] = static_cast<char>((length >> 16) & 0xFF);
        result[2] = static_cast<char>((length >> 8) & 0xFF);
        result[3] = static_cast<char>(length & 0xFF);

        result += message;

        return result;
    }

    static optional<pair<string, size_t>>
    decode(const string& buffer) {
        if (buffer.size() < 4) {
            return nullopt;
        }

        uint32_t length =
            (static_cast<uint32_t>(
                 static_cast<unsigned char>(buffer[0]))
             << 24) |
            (static_cast<uint32_t>(
                 static_cast<unsigned char>(buffer[1]))
             << 16) |
            (static_cast<uint32_t>(
                 static_cast<unsigned char>(buffer[2]))
             << 8) |
            static_cast<uint32_t>(
                static_cast<unsigned char>(buffer[3]));

        if (buffer.size() < 4 + length) {
            return nullopt;
        }

        return make_pair(
            buffer.substr(4, length),
            static_cast<size_t>(4 + length)
        );
    }
};

// ============================================================================
// Industry-style network service
// ============================================================================

class NetworkService {
private:
    RoutingTable routingTable;
    ArpCache arpCache;

    string serverIp = "10.20.30.10";
    string serverMac = "AA:BB:CC:DD:EE:10";

public:
    NetworkService() {
        routingTable.addRoute(
            Route("0.0.0.0", 0, "ISP")
        );

        routingTable.addRoute(
            Route("10.0.0.0", 8, "Router-A")
        );

        routingTable.addRoute(
            Route("10.20.0.0", 16, "Router-B")
        );

        routingTable.addRoute(
            Route("10.20.30.0", 24, "LOCAL-SWITCH")
        );

        arpCache.insert(
            "10.20.30.1",
            "AA:BB:CC:DD:EE:01"
        );

        arpCache.insert(
            "10.20.30.20",
            "AA:BB:CC:DD:EE:20"
        );
    }

    string processRequest(
        const string& clientIp,
        uint16_t clientPort,
        const string& path
    ) {
        if (path.empty()) {
            throw invalid_argument("HTTP path cannot be empty.");
        }

        if (clientPort == 0) {
            throw invalid_argument("Client port cannot be zero.");
        }

        // Application layer:
        HttpRequest request{
            "GET",
            path,
            {
                {"Host", serverIp},
                {"Accept", "application/json"},
            },
            "",
        };

        cout << "\nAPPLICATION LAYER\n";
        cout << request.serialize() << "\n";

        // Transport layer:
        TcpConnection connection;

        vector<TcpSegment> handshake =
            connection.establish();

        cout << "\nTRANSPORT LAYER\n";

        for (const auto& segment : handshake) {
            cout << "  "
                 << segment.describe()
                 << '\n';
        }

        TcpSegment applicationSegment =
            connection.sendData(request.serialize());

        cout << "  Data segment: "
             << applicationSegment.describe()
             << '\n';

        // Internet layer:
        Ipv4Packet packet{
            clientIp,
            serverIp,
            64,
            6,
            applicationSegment.payload,
        };

        cout << "\nINTERNET LAYER\n";
        cout << "  " << packet.describe() << '\n';

        const Route* route =
            routingTable.lookup(serverIp);

        if (route == nullptr) {
            throw runtime_error(
                "No route exists to server."
            );
        }

        cout << "  Selected route: "
             << route->network
             << "/"
             << route->prefixLength
             << " via "
             << route->nextHop
             << '\n';

        // Network access layer:
        EthernetFrame frame{
            serverMac,
            "00:11:22:33:44:55",
            0x0800,
            packet.payload,
        };

        cout << "\nNETWORK ACCESS LAYER\n";
        cout << "  " << frame.describe() << '\n';

        // The server constructs an application response.
        HttpResponse response{
            200,
            "OK",
            {
                {"Content-Type", "application/json"},
            },
            "{\"status\":\"ok\",\"message\":\"request processed\"}",
        };

        return response.serialize();
    }
};

// ============================================================================
// Failure and edge-case demonstrations
// ============================================================================

void demonstrateValidation() {
    cout << "\nVALIDATION AND EDGE CASES\n";
    printSeparator();

    const vector<string> addresses{
        "192.168.1.10",
        "10.0.0.1",
        "300.1.1.1",
        "192.168.1",
        "abc.def.ghi.jkl",
    };

    for (const auto& address : addresses) {
        try {
            const uint32_t value =
                ipv4ToInteger(address);

            cout << address
                 << " -> valid -> "
                 << value
                 << '\n';
        }
        catch (const exception& error) {
            cout << address
                 << " -> invalid -> "
                 << error.what()
                 << '\n';
        }
    }
}

void demonstrateCidrs() {
    cout << "\nCIDR CALCULATIONS\n";
    printSeparator();

    struct CidrExample {
        string address;
        int prefix;
    };

    const vector<CidrExample> examples{
        {"192.168.1.100", 24},
        {"10.20.30.40", 16},
        {"172.16.20.40", 28},
    };

    for (const auto& example : examples) {
        const uint32_t address =
            ipv4ToInteger(example.address);

        const uint32_t mask =
            prefixMask(example.prefix);

        const uint32_t network =
            address & mask;

        const uint32_t broadcast =
            network | ~mask;

        uint64_t addressCount =
            example.prefix == 32
                ? 1
                : (1ULL << (32 - example.prefix));

        cout << example.address
             << "/"
             << example.prefix
             << " -> network="
             << integerToIpv4(network)
             << ", broadcast="
             << integerToIpv4(broadcast)
             << ", addresses="
             << addressCount
             << '\n';
    }
}

void demonstrateRouting() {
    cout << "\nROUTING TABLE\n";
    printSeparator();

    RoutingTable table;

    table.addRoute(
        Route("0.0.0.0", 0, "ISP")
    );

    table.addRoute(
        Route("10.0.0.0", 8, "Router-A")
    );

    table.addRoute(
        Route("10.20.0.0", 16, "Router-B")
    );

    table.addRoute(
        Route("10.20.30.0", 24, "Router-C")
    );

    for (const string& destination : {
        "10.20.30.15",
        "10.20.99.15",
        "10.50.1.1",
        "8.8.8.8",
    }) {
        const Route* route =
            table.lookup(destination);

        if (route == nullptr) {
            cout << destination
                 << " -> no route\n";
            continue;
        }

        cout << destination
             << " -> "
             << route->network
             << "/"
             << route->prefixLength
             << " via "
             << route->nextHop
             << '\n';
    }
}

void demonstrateArp() {
    cout << "\nARP CACHE\n";
    printSeparator();

    ArpCache cache;

    cache.insert(
        "192.168.1.1",
        "AA:BB:CC:DD:EE:01"
    );

    cache.insert(
        "192.168.1.20",
        "AA:BB:CC:DD:EE:20"
    );

    for (const string& address : {
        "192.168.1.20",
        "192.168.1.99",
    }) {
        const auto result =
            cache.lookup(address);

        if (result.has_value()) {
            cout << address
                 << " -> "
                 << result.value()
                 << '\n';
        } else {
            cout << address
                 << " -> cache miss\n";
        }
    }
}

void demonstrateFraming() {
    cout << "\nAPPLICATION FRAMING\n";
    printSeparator();

    const string message =
        "TCP is a byte stream.";

    const string encoded =
        LengthPrefixedProtocol::encode(message);

    cout << "Original message size: "
         << message.size()
         << '\n';

    cout << "Encoded size: "
         << encoded.size()
         << '\n';

    const auto decoded =
        LengthPrefixedProtocol::decode(encoded);

    if (decoded.has_value()) {
        cout << "Decoded message: "
             << decoded->first
             << '\n';

        cout << "Bytes consumed: "
             << decoded->second
             << '\n';
    }

    const string incomplete =
        encoded.substr(0, 5);

    const auto incompleteResult =
        LengthPrefixedProtocol::decode(incomplete);

    cout << "Incomplete buffer decoded: "
         << boolalpha
         << incompleteResult.has_value()
         << '\n';
}

// ============================================================================
// Performance and security reasoning
// ============================================================================

void demonstrateDesignConsiderations() {
    cout << "\nDESIGN, PERFORMANCE, AND SECURITY CONSIDERATIONS\n";
    printSeparator();

    const vector<string> points{
        "TCP provides reliability but introduces connection and retransmission overhead.",
        "UDP avoids TCP connection management but does not provide TCP-style reliability.",
        "Routing lookup uses longest-prefix matching.",
        "Network services must validate addresses, ports, message sizes, and protocol fields.",
        "Timeouts are essential when waiting for external network operations.",
        "Unbounded buffers can create memory-exhaustion risks.",
        "TLS is required when confidentiality and authenticated transport are needed.",
        "Authentication and authorization are application-level security decisions.",
        "Logging should capture useful diagnostics without exposing secrets.",
        "High-concurrency servers need an explicit concurrency architecture.",
    };

    for (const auto& point : points) {
        cout << "- " << point << '\n';
    }
}

// ============================================================================
// Tests
// ============================================================================

void runTests() {
    cout << "\nSELF-TESTS\n";
    printSeparator();

    if (ipv4ToInteger("192.168.1.1") !=
        0xC0A80101u) {
        throw runtime_error("IPv4 conversion test failed.");
    }

    if (integerToIpv4(0xC0A80101u) !=
        "192.168.1.1") {
        throw runtime_error("IPv4 reverse conversion test failed.");
    }

    RoutingTable table;

    table.addRoute(
        Route("0.0.0.0", 0, "DEFAULT")
    );

    table.addRoute(
        Route("10.0.0.0", 8, "A")
    );

    table.addRoute(
        Route("10.20.0.0", 16, "B")
    );

    const Route* selected =
        table.lookup("10.20.50.1");

    if (selected == nullptr ||
        selected->nextHop != "B") {
        throw runtime_error(
            "Longest-prefix routing test failed."
        );
    }

    TcpConnection connection;

    const auto handshake =
        connection.establish();

    if (
        handshake.size() != 3 ||
        !handshake[0].syn ||
        !handshake[1].syn ||
        !handshake[1].ack ||
        !handshake[2].ack ||
        connection.getState() != TcpState::ESTABLISHED
    ) {
        throw runtime_error(
            "TCP handshake test failed."
        );
    }

    const string message = "test";

    const string encoded =
        LengthPrefixedProtocol::encode(message);

    const auto decoded =
        LengthPrefixedProtocol::decode(encoded);

    if (
        !decoded.has_value() ||
        decoded->first != message
    ) {
        throw runtime_error(
            "Application framing test failed."
        );
    }

    cout << "All tests passed.\n";
}

// ============================================================================
// Main
// ============================================================================

int main() {
    try {
        cout << "TCP/IP MODEL: INDUSTRY-STYLE NETWORK SERVICE CASE STUDY\n";
        printSeparator();

        cout
            << "The system models an HTTP-like application request "
            << "moving through all four TCP/IP layers.\n";

        demonstrateValidation();
        demonstrateCidrs();
        demonstrateRouting();
        demonstrateArp();
        demonstrateFraming();

        cout << "\nTCP CONNECTION ESTABLISHMENT\n";
        printSeparator();

        TcpConnection connection;

        cout << "Initial state: "
             << tcpStateName(connection.getState())
             << '\n';

        const auto handshake =
            connection.establish();

        for (size_t i = 0; i < handshake.size(); ++i) {
            cout << "Step "
                 << i + 1
                 << ": "
                 << handshake[i].describe()
                 << '\n';
        }

        cout << "Final state: "
             << tcpStateName(connection.getState())
             << '\n';

        cout << "\nFULL NETWORK SERVICE\n";
        printSeparator();

        NetworkService service;

        const string response =
            service.processRequest(
                "192.168.1.20",
                53000,
                "/api/status"
            );

        cout << "\nAPPLICATION RESPONSE\n";
        cout << response << '\n';

        demonstrateDesignConsiderations();
        runTests();

        cout << "\nCASE STUDY COMPLETE\n";
    }
    catch (const exception& error) {
        cerr << "Fatal error: "
             << error.what()
             << '\n';

        return 1;
    }

    return 0;
}
