/*
 * OSI Model: Industry-Style C++ Case Study
 *
 * Scenario:
 * A simplified enterprise branch network sends an HTTPS request from a
 * workstation to a remote application server.
 *
 * The implementation models:
 *   Layer 1 - Physical transmission
 *   Layer 2 - Ethernet framing and MAC addressing
 *   Layer 3 - IPv4 addressing and routing
 *   Layer 4 - TCP transport and ports
 *   Layer 5 - Session state
 *   Layer 6 - Data representation
 *   Layer 7 - HTTP application data
 *
 * Standard: C++17
 *
 * Compile:
 *   g++ -std=c++17 -O2 osi_case_study.cpp -o osi_case_study
 */

#include <algorithm>
#include <array>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Byte = std::uint8_t;


// ============================================================
// Utility Functions
// ============================================================

std::string toHex(std::uint32_t value, int width) {
    std::ostringstream output;
    output << std::hex << std::uppercase
           << std::setw(width) << std::setfill('0')
           << value;
    return output.str();
}


std::vector<std::string> split(const std::string& value, char delimiter) {
    std::vector<std::string> parts;
    std::stringstream stream(value);
    std::string part;

    while (std::getline(stream, part, delimiter)) {
        parts.push_back(part);
    }

    return parts;
}


// ============================================================
// Layer 1: Physical
// ============================================================

class PhysicalMedium {
public:
    explicit PhysicalMedium(std::size_t capacityBits)
        : capacityBits_(capacityBits) {}

    bool transmit(const std::vector<Byte>& data) const {
        const std::size_t bits = data.size() * 8;

        std::cout
            << "[Layer 1] Transmitting "
            << bits
            << " bits over the physical medium.\n";

        if (bits > capacityBits_) {
            std::cout
                << "[Layer 1] Warning: simulated transmission unit "
                << "capacity exceeded.\n";
            return false;
        }

        return true;
    }

private:
    std::size_t capacityBits_;
};


// ============================================================
// Layer 2: MAC Address
// ============================================================

class MacAddress {
public:
    explicit MacAddress(const std::string& text) {
        parse(text);
    }

    std::string toString() const {
        std::ostringstream output;

        for (std::size_t index = 0; index < bytes_.size(); ++index) {
            if (index > 0) {
                output << ':';
            }

            output << std::hex << std::uppercase
                   << std::setw(2) << std::setfill('0')
                   << static_cast<int>(bytes_[index]);
        }

        return output.str();
    }

private:
    std::array<Byte, 6> bytes_{};

    static int hexValue(char character) {
        if (character >= '0' && character <= '9') {
            return character - '0';
        }

        if (character >= 'a' && character <= 'f') {
            return character - 'a' + 10;
        }

        if (character >= 'A' && character <= 'F') {
            return character - 'A' + 10;
        }

        return -1;
    }

    void parse(std::string text) {
        std::replace(text.begin(), text.end(), '-', ':');

        const auto parts = split(text, ':');

        if (parts.size() != 6) {
            throw std::invalid_argument("MAC address must contain six octets.");
        }

        for (std::size_t index = 0; index < 6; ++index) {
            if (parts[index].size() != 2) {
                throw std::invalid_argument("Invalid MAC octet.");
            }

            const int high = hexValue(parts[index][0]);
            const int low = hexValue(parts[index][1]);

            if (high < 0 || low < 0) {
                throw std::invalid_argument("Invalid hexadecimal MAC address.");
            }

            bytes_[index] = static_cast<Byte>((high << 4) | low);
        }
    }
};


// ============================================================
// Layer 2: Ethernet Frame
// ============================================================

class EthernetFrame {
public:
    EthernetFrame(
        MacAddress destination,
        MacAddress source,
        std::uint16_t etherType,
        std::vector<Byte> payload
    )
        : destination_(std::move(destination)),
          source_(std::move(source)),
          etherType_(etherType),
          payload_(std::move(payload)) {}

    const std::vector<Byte>& payload() const {
        return payload_;
    }

    void printSummary() const {
        std::cout
            << "[Layer 2] Ethernet frame: "
            << source_.toString()
            << " -> "
            << destination_.toString()
            << ", EtherType=0x"
            << toHex(etherType_, 4)
            << ", payload="
            << payload_.size()
            << " bytes\n";
    }

private:
    MacAddress destination_;
    MacAddress source_;
    std::uint16_t etherType_;
    std::vector<Byte> payload_;
};


// ============================================================
// Layer 3: IPv4 Address
// ============================================================

class IPv4Address {
public:
    explicit IPv4Address(const std::string& text) {
        parse(text);
    }

    std::uint32_t value() const {
        return value_;
    }

    std::string toString() const {
        return std::to_string((value_ >> 24) & 0xFF) + "." +
               std::to_string((value_ >> 16) & 0xFF) + "." +
               std::to_string((value_ >> 8) & 0xFF) + "." +
               std::to_string(value_ & 0xFF);
    }

private:
    std::uint32_t value_{};

    void parse(const std::string& text) {
        const auto parts = split(text, '.');

        if (parts.size() != 4) {
            throw std::invalid_argument("IPv4 address must contain four octets.");
        }

        value_ = 0;

        for (const auto& part : parts) {
            if (part.empty()) {
                throw std::invalid_argument("Empty IPv4 octet.");
            }

            std::size_t position = 0;
            unsigned long number = std::stoul(part, &position);

            if (position != part.size() || number > 255) {
                throw std::invalid_argument("Invalid IPv4 octet.");
            }

            value_ = (value_ << 8) | static_cast<std::uint32_t>(number);
        }
    }
};


// ============================================================
// Layer 3: Routing
// ============================================================

struct Route {
    IPv4Address network;
    int prefixLength;
    std::string nextHop;
    std::string interfaceName;
    int metric;

    std::uint32_t mask() const {
        if (prefixLength == 0) {
            return 0;
        }

        return 0xFFFFFFFFu << (32 - prefixLength);
    }

    bool contains(const IPv4Address& address) const {
        return (address.value() & mask()) ==
               (network.value() & mask());
    }
};


class RoutingTable {
public:
    void addRoute(Route route) {
        if (route.prefixLength < 0 || route.prefixLength > 32) {
            throw std::invalid_argument("Invalid prefix length.");
        }

        routes_.push_back(std::move(route));
    }

    std::optional<Route> lookup(const IPv4Address& destination) const {
        std::optional<Route> selected;

        for (const auto& route : routes_) {
            if (!route.contains(destination)) {
                continue;
            }

            if (!selected.has_value() ||
                route.prefixLength > selected->prefixLength ||
                (
                    route.prefixLength == selected->prefixLength &&
                    route.metric < selected->metric
                )) {
                selected = route;
            }
        }

        return selected;
    }

    void display() const {
        std::cout << "\nRouting table:\n";

        for (const auto& route : routes_) {
            std::cout
                << "  "
                << route.network.toString()
                << "/"
                << route.prefixLength
                << " -> "
                << route.nextHop
                << " via "
                << route.interfaceName
                << " metric="
                << route.metric
                << '\n';
        }
    }

private:
    std::vector<Route> routes_;
};


// ============================================================
// Layer 4: TCP
// ============================================================

enum TcpFlag : std::uint16_t {
    FIN = 0x001,
    SYN = 0x002,
    RST = 0x004,
    PSH = 0x008,
    ACK = 0x010
};


class TcpSegment {
public:
    TcpSegment(
        std::uint16_t sourcePort,
        std::uint16_t destinationPort,
        std::uint32_t sequenceNumber,
        std::uint32_t acknowledgmentNumber,
        std::uint16_t flags,
        std::vector<Byte> payload
    )
        : sourcePort_(sourcePort),
          destinationPort_(destinationPort),
          sequenceNumber_(sequenceNumber),
          acknowledgmentNumber_(acknowledgmentNumber),
          flags_(flags),
          payload_(std::move(payload)) {

        if (sourcePort_ == 0 || destinationPort_ == 0) {
            throw std::invalid_argument("TCP port zero is not valid here.");
        }
    }

    void printSummary() const {
        std::cout
            << "[Layer 4] TCP "
            << sourcePort_
            << " -> "
            << destinationPort_
            << ", seq="
            << sequenceNumber_
            << ", ack="
            << acknowledgmentNumber_
            << ", flags="
            << flagText()
            << ", payload="
            << payload_.size()
            << " bytes\n";
    }

    const std::vector<Byte>& payload() const {
        return payload_;
    }

    std::uint16_t destinationPort() const {
        return destinationPort_;
    }

private:
    std::uint16_t sourcePort_;
    std::uint16_t destinationPort_;
    std::uint32_t sequenceNumber_;
    std::uint32_t acknowledgmentNumber_;
    std::uint16_t flags_;
    std::vector<Byte> payload_;

    std::string flagText() const {
        std::vector<std::string> names;

        if (flags_ & SYN) names.push_back("SYN");
        if (flags_ & ACK) names.push_back("ACK");
        if (flags_ & PSH) names.push_back("PSH");
        if (flags_ & FIN) names.push_back("FIN");
        if (flags_ & RST) names.push_back("RST");

        if (names.empty()) {
            return "NONE";
        }

        std::ostringstream output;

        for (std::size_t index = 0; index < names.size(); ++index) {
            if (index > 0) {
                output << ",";
            }

            output << names[index];
        }

        return output.str();
    }
};


// ============================================================
// Layer 4: UDP
// ============================================================

class UdpDatagram {
public:
    UdpDatagram(
        std::uint16_t sourcePort,
        std::uint16_t destinationPort,
        std::vector<Byte> payload
    )
        : sourcePort_(sourcePort),
          destinationPort_(destinationPort),
          payload_(std::move(payload)) {

        if (sourcePort_ == 0 || destinationPort_ == 0) {
            throw std::invalid_argument("UDP ports must be non-zero here.");
        }
    }

    std::size_t length() const {
        return 8 + payload_.size();
    }

    void printSummary() const {
        std::cout
            << "[Layer 4] UDP "
            << sourcePort_
            << " -> "
            << destinationPort_
            << ", length="
            << length()
            << " bytes\n";
    }

private:
    std::uint16_t sourcePort_;
    std::uint16_t destinationPort_;
    std::vector<Byte> payload_;
};


// ============================================================
// Layer 5: Session
// ============================================================

enum class SessionState {
    Closed,
    Opening,
    Established,
    Closing
};


class Session {
public:
    void open() {
        if (state_ != SessionState::Closed) {
            throw std::logic_error("Session is not closed.");
        }

        state_ = SessionState::Opening;
        std::cout << "[Layer 5] Session opening.\n";

        state_ = SessionState::Established;
        std::cout << "[Layer 5] Session established.\n";
    }

    void close() {
        if (state_ != SessionState::Established) {
            throw std::logic_error("Only an established session can close.");
        }

        state_ = SessionState::Closing;
        std::cout << "[Layer 5] Session closing.\n";

        state_ = SessionState::Closed;
        std::cout << "[Layer 5] Session closed.\n";
    }

    bool established() const {
        return state_ == SessionState::Established;
    }

private:
    SessionState state_ = SessionState::Closed;
};


// ============================================================
// Layer 6: Presentation
// ============================================================

class PresentationCodec {
public:
    static std::vector<Byte> encodeText(const std::string& text) {
        // ASCII/UTF-8-compatible text is represented directly as bytes
        // for this educational case study.
        return std::vector<Byte>(text.begin(), text.end());
    }

    static std::string decodeText(const std::vector<Byte>& data) {
        return std::string(data.begin(), data.end());
    }

    static std::string serializeJsonStatus(
        int status,
        const std::string& message
    ) {
        return
            "{\"status\":" +
            std::to_string(status) +
            ",\"message\":\"" +
            message +
            "\"}";
    }
};


// ============================================================
// Layer 7: Application
// ============================================================

class HttpApplication {
public:
    static std::string buildRequest(
        const std::string& host,
        const std::string& path
    ) {
        if (host.empty()) {
            throw std::invalid_argument("HTTP Host cannot be empty.");
        }

        if (path.empty() || path.front() != '/') {
            throw std::invalid_argument("HTTP path must begin with '/'.");
        }

        return
            "GET " + path + " HTTP/1.1\r\n"
            "Host: " + host + "\r\n"
            "Accept: */*\r\n"
            "Connection: close\r\n"
            "\r\n";
    }

    static void receive(const std::string& request) {
        const auto lines = split(request, '\n');

        std::cout
            << "[Layer 7] Application received: "
            << (lines.empty() ? "<empty>" : lines.front())
            << '\n';
    }
};


// ============================================================
// Enterprise Branch Network
// ============================================================

class EnterpriseNetwork {
public:
    EnterpriseNetwork()
        : medium_(12000),
          workstationMac_("AA:BB:CC:DD:EE:01"),
          gatewayMac_("00:11:22:33:44:01"),
          serverMac_("00:11:22:33:44:99"),
          workstationIp_("192.168.10.50"),
          gatewayIp_("192.168.10.1"),
          serverIp_("10.20.5.10") {

        routingTable_.addRoute({
            IPv4Address("192.168.10.0"),
            24,
            "direct",
            "eth0",
            1
        });

        routingTable_.addRoute({
            IPv4Address("10.20.0.0"),
            16,
            "10.20.0.1",
            "eth1",
            10
        });

        routingTable_.addRoute({
            IPv4Address("0.0.0.0"),
            0,
            "192.168.10.1",
            "eth0",
            100
        });
    }

    void runHttpsRequest() {
        std::cout
            << "\n"
            << "============================================================\n"
            << "ENTERPRISE HTTPS REQUEST CASE STUDY\n"
            << "============================================================\n";

        const std::string httpRequest =
            HttpApplication::buildRequest(
                "application.example",
                "/api/status"
            );

        // Layer 6 transforms application text into a byte representation.
        const std::vector<Byte> encodedApplicationData =
            PresentationCodec::encodeText(httpRequest);

        std::cout
            << "[Layer 6] Encoded application data: "
            << encodedApplicationData.size()
            << " bytes\n";

        // Layer 5 establishes the logical application session.
        Session session;
        session.open();

        if (!session.established()) {
            throw std::runtime_error("Session establishment failed.");
        }

        // Layer 4 places application data into a TCP segment.
        TcpSegment tcpSegment(
            53000,
            443,
            1000,
            5000,
            PSH | ACK,
            encodedApplicationData
        );

        tcpSegment.printSummary();

        // Layer 3 creates an IPv4 packet.
        IPv4Address destination(serverIp_);

        const auto route = routingTable_.lookup(destination);

        if (!route.has_value()) {
            throw std::runtime_error("No route to destination.");
        }

        std::cout
            << "[Layer 3] Route selected: "
            << route->network.toString()
            << "/"
            << route->prefixLength
            << " via "
            << route->nextHop
            << '\n';

        std::vector<Byte> networkPayload = tcpSegment.payload();

        // A complete IPv4 packet normally includes an IP header.
        // Here the payload is represented explicitly while the
        // architecture focuses on the layer transition.
        std::cout
            << "[Layer 3] "
            << workstationIp_.toString()
            << " -> "
            << destination.toString()
            << ", TTL=64, protocol=TCP\n";

        // Layer 2 wraps the network payload inside an Ethernet frame.
        EthernetFrame frame(
            gatewayMac_,
            workstationMac_,
            0x0800,
            networkPayload
        );

        frame.printSummary();

        // Layer 1 transmits the serialized representation.
        if (!medium_.transmit(frame.payload())) {
            throw std::runtime_error("Physical transmission failed.");
        }

        std::cout
            << "[Layer 1] Transmission successful.\n";

        // The remote side now processes the layers in reverse.
        receiveAtServer(frame, tcpSegment, session);

        session.close();
    }

private:
    PhysicalMedium medium_;

    MacAddress workstationMac_;
    MacAddress gatewayMac_;
    MacAddress serverMac_;

    IPv4Address workstationIp_;
    IPv4Address gatewayIp_;
    IPv4Address serverIp_;

    RoutingTable routingTable_;

    void receiveAtServer(
        const EthernetFrame& frame,
        const TcpSegment& tcpSegment,
        const Session& session
    ) {
        std::cout
            << "\n"
            << "------------------------------------------------------------\n"
            << "REMOTE RECEIVE PATH\n"
            << "------------------------------------------------------------\n";

        // Layer 2 validation.
        frame.printSummary();

        // Layer 4 validation.
        if (!session.established()) {
            throw std::runtime_error(
                "Transport data received without an established session."
            );
        }

        std::cout
            << "[Layer 4] Destination TCP port "
            << tcpSegment.destinationPort()
            << " corresponds to HTTPS.\n";

        // Layer 6 representation conversion.
        const std::string request =
            PresentationCodec::decodeText(tcpSegment.payload());

        // Layer 7 application handling.
        HttpApplication::receive(request);

        const std::string response =
            PresentationCodec::serializeJsonStatus(
                200,
                "network path operational"
            );

        std::cout
            << "[Layer 7] Response: "
            << response
            << '\n';
    }
};


// ============================================================
// Diagnostics
// ============================================================

void demonstrateTcpHandshake() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "TCP THREE-WAY HANDSHAKE\n"
        << "============================================================\n";

    std::cout << "1. Client -> Server: SYN\n";
    std::cout << "2. Server -> Client: SYN-ACK\n";
    std::cout << "3. Client -> Server: ACK\n";
    std::cout << "4. Connection state: ESTABLISHED\n";
}


void demonstrateMtu() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "MTU ANALYSIS\n"
        << "============================================================\n";

    constexpr std::size_t mtu = 1500;
    constexpr std::size_t ipv4Header = 20;
    constexpr std::size_t tcpHeader = 20;

    const std::size_t tcpPayload =
        mtu - ipv4Header - tcpHeader;

    std::cout
        << "MTU: "
        << mtu
        << " bytes\n";

    std::cout
        << "Approximate TCP payload capacity: "
        << tcpPayload
        << " bytes\n";

    std::cout
        << "TCP segmentation and IP fragmentation are distinct mechanisms.\n";
}


void demonstrateLayerTroubleshooting() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "OSI TROUBLESHOOTING MODEL\n"
        << "============================================================\n";

    const std::map<int, std::string> examples = {
        {1, "No link: cable, transceiver, interface, power"},
        {2, "Wrong VLAN, MAC learning, switching loop"},
        {3, "IP address, gateway, route, subnet"},
        {4, "Port filtering, TCP state, firewall"},
        {5, "Session timeout or invalid session state"},
        {6, "Encoding, TLS, certificate, representation"},
        {7, "DNS, HTTP, authentication, application configuration"},
    };

    for (const auto& [layer, problem] : examples) {
        std::cout
            << "Layer "
            << layer
            << ": "
            << problem
            << '\n';
    }
}


void demonstrateComplexity() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "ALGORITHMIC AND PERFORMANCE CONSIDERATIONS\n"
        << "============================================================\n";

    std::cout
        << "Simple routing-table lookup in this case study is O(R), "
        << "where R is the number of routes.\n";

    std::cout
        << "Real routers use optimized forwarding structures to "
        << "avoid scanning every route for each packet.\n";

    std::cout
        << "Packet processing cost includes parsing, validation, "
        << "memory access, copying, checksums, and queueing.\n";

    std::cout
        << "C++ provides deterministic resource management and "
        << "low-level control useful for high-performance networking.\n";
}


// ============================================================
// Edge Cases
// ============================================================

void demonstrateEdgeCases() {
    std::cout
        << "\n"
        << "============================================================\n"
        << "EDGE CASES\n"
        << "============================================================\n";

    try {
        IPv4Address invalid("999.1.1.1");
        (void)invalid;
    } catch (const std::exception& error) {
        std::cout
            << "Invalid IP rejected: "
            << error.what()
            << '\n';
    }

    try {
        MacAddress invalid("AA:BB:CC");
        (void)invalid;
    } catch (const std::exception& error) {
        std::cout
            << "Invalid MAC rejected: "
            << error.what()
            << '\n';
    }

    try {
        TcpSegment invalid(
            0,
            443,
            1,
            1,
            SYN,
            {}
        );
        invalid.printSummary();
    } catch (const std::exception& error) {
        std::cout
            << "Invalid TCP port rejected: "
            << error.what()
            << '\n';
    }
}


// ============================================================
// Main
// ============================================================

int main() {
    try {
        std::cout
            << "============================================================\n"
            << "OSI MODEL C++ CASE STUDY\n"
            << "============================================================\n";

        std::cout
            << "\n"
            << "Layer 7: Application      HTTP\n"
            << "Layer 6: Presentation     UTF-8 / JSON / TLS concepts\n"
            << "Layer 5: Session          Session lifecycle\n"
            << "Layer 4: Transport        TCP / UDP\n"
            << "Layer 3: Network          IPv4 / Routing\n"
            << "Layer 2: Data Link        Ethernet / MAC\n"
            << "Layer 1: Physical         Signals / Bits\n";

        demonstrateTcpHandshake();
        demonstrateMtu();
        demonstrateLayerTroubleshooting();
        demonstrateComplexity();
        demonstrateEdgeCases();

        EnterpriseNetwork enterpriseNetwork;
        enterpriseNetwork.runHttpsRequest();

        std::cout
            << "\n"
            << "============================================================\n"
            << "CASE STUDY COMPLETED\n"
            << "============================================================\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }
}
