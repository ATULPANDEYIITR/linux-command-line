/*
 * Linux Networking Technical Case Study
 *
 * Scenario:
 *     A Linux-based service gateway hosts an internal telemetry service.
 *     The gateway must validate IPv4 configuration, choose appropriate
 *     routes, expose a TCP service, send UDP telemetry, perform DNS-style
 *     endpoint validation, and provide structured troubleshooting output.
 *
 * The implementation demonstrates:
 *
 *     - IPv4 parsing and validation
 *     - CIDR subnet calculations
 *     - Longest-prefix route selection
 *     - Route metrics
 *     - TCP server/client communication
 *     - UDP telemetry
 *     - Connection timeouts
 *     - Input validation
 *     - Error handling
 *     - Concurrent worker threads
 *     - Performance measurements
 *     - Modular class design
 *     - Security-oriented service binding
 *
 * Compile:
 *     g++ -std=c++17 -O2 -Wall -Wextra -pedantic linux_networking_case_study.cpp -o network_case
 *
 * Run:
 *     ./network_case
 */

#include <algorithm>
#include <arpa/inet.h>
#include <atomic>
#include <chrono>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <netdb.h>
#include <netinet/in.h>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>


// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

void printSection(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}

std::string errnoMessage(const std::string& operation) {
    return operation + ": " + std::strerror(errno);
}


// ---------------------------------------------------------------------------
// IPv4 address representation
// ---------------------------------------------------------------------------

class IPv4Address {
private:
    uint32_t value_;

public:
    explicit IPv4Address(uint32_t value = 0)
        : value_(value) {}

    static IPv4Address parse(const std::string& text) {
        in_addr address{};

        if (inet_pton(AF_INET, text.c_str(), &address) != 1) {
            throw std::invalid_argument("Invalid IPv4 address: " + text);
        }

        return IPv4Address(ntohl(address.s_addr));
    }

    uint32_t value() const {
        return value_;
    }

    bool operator==(const IPv4Address& other) const {
        return value_ == other.value_;
    }

    std::string toString() const {
        in_addr address{};
        address.s_addr = htonl(value_);

        char buffer[INET_ADDRSTRLEN]{};

        if (inet_ntop(
                AF_INET,
                &address,
                buffer,
                sizeof(buffer)) == nullptr) {
            throw std::runtime_error("Unable to format IPv4 address.");
        }

        return std::string(buffer);
    }
};


// ---------------------------------------------------------------------------
// CIDR network
// ---------------------------------------------------------------------------

class IPv4Network {
private:
    IPv4Address network_;
    uint8_t prefixLength_;
    uint32_t mask_;

public:
    IPv4Network(IPv4Address address, uint8_t prefixLength)
        : prefixLength_(prefixLength), mask_(0) {

        if (prefixLength > 32) {
            throw std::invalid_argument("IPv4 prefix must be between 0 and 32.");
        }

        if (prefixLength == 0) {
            mask_ = 0;
        } else {
            mask_ = 0xffffffffu << (32 - prefixLength);
        }

        network_ = IPv4Address(address.value() & mask_);
    }

    static IPv4Network parse(const std::string& cidr) {
        const auto slash = cidr.find('/');

        if (slash == std::string::npos) {
            throw std::invalid_argument(
                "CIDR must contain '/': " + cidr
            );
        }

        const std::string addressText = cidr.substr(0, slash);
        const std::string prefixText = cidr.substr(slash + 1);

        size_t consumed = 0;
        unsigned long prefix = std::stoul(prefixText, &consumed);

        if (consumed != prefixText.size() || prefix > 32) {
            throw std::invalid_argument(
                "Invalid CIDR prefix: " + prefixText
            );
        }

        return IPv4Network(
            IPv4Address::parse(addressText),
            static_cast<uint8_t>(prefix)
        );
    }

    bool contains(const IPv4Address& address) const {
        return (address.value() & mask_) == network_.value();
    }

    uint8_t prefixLength() const {
        return prefixLength_;
    }

    std::string toString() const {
        return network_.toString() +
               "/" +
               std::to_string(prefixLength_);
    }
};


// ---------------------------------------------------------------------------
// Routing model
// ---------------------------------------------------------------------------

struct Route {
    IPv4Network network;
    std::string gateway;
    std::string interfaceName;
    int metric;

    bool matches(const IPv4Address& destination) const {
        return network.contains(destination);
    }
};


class RoutingTable {
private:
    std::vector<Route> routes_;

public:
    void addRoute(const Route& route) {
        routes_.push_back(route);
    }

    std::optional<Route> lookup(const IPv4Address& destination) const {
        std::vector<Route> candidates;

        for (const auto& route : routes_) {
            if (route.matches(destination)) {
                candidates.push_back(route);
            }
        }

        if (candidates.empty()) {
            return std::nullopt;
        }

        // Longest-prefix match is the primary selection criterion.
        // Metric resolves otherwise equivalent prefixes in this model.
        std::sort(
            candidates.begin(),
            candidates.end(),
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

        return candidates.front();
    }

    void print() const {
        std::cout << std::left
                  << std::setw(20) << "Destination"
                  << std::setw(18) << "Gateway"
                  << std::setw(12) << "Interface"
                  << "Metric\n";

        for (const auto& route : routes_) {
            std::cout << std::left
                      << std::setw(20) << route.network.toString()
                      << std::setw(18) << route.gateway
                      << std::setw(12) << route.interfaceName
                      << route.metric
                      << "\n";
        }
    }
};


// ---------------------------------------------------------------------------
// Configuration validation
// ---------------------------------------------------------------------------

struct InterfaceConfiguration {
    std::string name;
    IPv4Address address;
    IPv4Network network;
};


class ConfigurationValidator {
public:
    static bool addressBelongsToNetwork(
        const IPv4Address& address,
        const IPv4Network& network) {

        return network.contains(address);
    }

    static void validate(const InterfaceConfiguration& configuration) {
        if (!addressBelongsToNetwork(
                configuration.address,
                configuration.network)) {

            throw std::invalid_argument(
                "Interface address " +
                configuration.address.toString() +
                " is outside " +
                configuration.network.toString()
            );
        }
    }
};


// ---------------------------------------------------------------------------
// RAII file descriptor
// ---------------------------------------------------------------------------

class FileDescriptor {
private:
    int descriptor_;

public:
    explicit FileDescriptor(int descriptor = -1)
        : descriptor_(descriptor) {}

    ~FileDescriptor() {
        close();
    }

    FileDescriptor(const FileDescriptor&) = delete;
    FileDescriptor& operator=(const FileDescriptor&) = delete;

    FileDescriptor(FileDescriptor&& other) noexcept
        : descriptor_(other.descriptor_) {
        other.descriptor_ = -1;
    }

    FileDescriptor& operator=(FileDescriptor&& other) noexcept {
        if (this != &other) {
            close();
            descriptor_ = other.descriptor_;
            other.descriptor_ = -1;
        }

        return *this;
    }

    int get() const {
        return descriptor_;
    }

    bool valid() const {
        return descriptor_ >= 0;
    }

    int release() {
        const int value = descriptor_;
        descriptor_ = -1;
        return value;
    }

    void close() {
        if (descriptor_ >= 0) {
            ::close(descriptor_);
            descriptor_ = -1;
        }
    }
};


// ---------------------------------------------------------------------------
// TCP service
// ---------------------------------------------------------------------------

class TcpEchoServer {
private:
    FileDescriptor serverSocket_;
    uint16_t port_;

public:
    TcpEchoServer()
        : serverSocket_(), port_(0) {}

    void start() {
        int descriptor = socket(AF_INET, SOCK_STREAM, 0);

        if (descriptor < 0) {
            throw std::runtime_error(errnoMessage("socket"));
        }

        serverSocket_ = FileDescriptor(descriptor);

        int reuse = 1;

        if (setsockopt(
                serverSocket_.get(),
                SOL_SOCKET,
                SO_REUSEADDR,
                &reuse,
                sizeof(reuse)) < 0) {

            throw std::runtime_error(errnoMessage("setsockopt"));
        }

        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_port = htons(0);

        // Binding to loopback is deliberate. A production service should
        // bind to the smallest interface scope required by its architecture.
        if (inet_pton(
                AF_INET,
                "127.0.0.1",
                &address.sin_addr) != 1) {

            throw std::runtime_error("Unable to create loopback address.");
        }

        if (bind(
                serverSocket_.get(),
                reinterpret_cast<sockaddr*>(&address),
                sizeof(address)) < 0) {

            throw std::runtime_error(errnoMessage("bind"));
        }

        if (listen(serverSocket_.get(), 16) < 0) {
            throw std::runtime_error(errnoMessage("listen"));
        }

        sockaddr_in boundAddress{};
        socklen_t length = sizeof(boundAddress);

        if (getsockname(
                serverSocket_.get(),
                reinterpret_cast<sockaddr*>(&boundAddress),
                &length) < 0) {

            throw std::runtime_error(errnoMessage("getsockname"));
        }

        port_ = ntohs(boundAddress.sin_port);
    }

    uint16_t port() const {
        return port_;
    }

    void serveOnce() {
        sockaddr_in clientAddress{};
        socklen_t clientLength = sizeof(clientAddress);

        FileDescriptor clientSocket(
            accept(
                serverSocket_.get(),
                reinterpret_cast<sockaddr*>(&clientAddress),
                &clientLength
            )
        );

        if (!clientSocket.valid()) {
            throw std::runtime_error(errnoMessage("accept"));
        }

        char buffer[4096]{};

        const ssize_t received = recv(
            clientSocket.get(),
            buffer,
            sizeof(buffer),
            0
        );

        if (received < 0) {
            throw std::runtime_error(errnoMessage("recv"));
        }

        const std::string response =
            "ACK:" +
            std::string(buffer, static_cast<size_t>(received));

        size_t sentTotal = 0;

        // send() can legally send fewer bytes than requested, so production
        // TCP code must account for partial writes.
        while (sentTotal < response.size()) {
            const ssize_t sent = send(
                clientSocket.get(),
                response.data() + sentTotal,
                response.size() - sentTotal,
                0
            );

            if (sent < 0) {
                throw std::runtime_error(errnoMessage("send"));
            }

            if (sent == 0) {
                break;
            }

            sentTotal += static_cast<size_t>(sent);
        }
    }
};


// ---------------------------------------------------------------------------
// TCP client
// ---------------------------------------------------------------------------

class TcpClient {
public:
    static std::string request(
        const std::string& host,
        uint16_t port,
        const std::string& message) {

        FileDescriptor socketDescriptor(
            socket(AF_INET, SOCK_STREAM, 0)
        );

        if (!socketDescriptor.valid()) {
            throw std::runtime_error(errnoMessage("socket"));
        }

        timeval timeout{};
        timeout.tv_sec = 2;
        timeout.tv_usec = 0;

        if (setsockopt(
                socketDescriptor.get(),
                SOL_SOCKET,
                SO_RCVTIMEO,
                &timeout,
                sizeof(timeout)) < 0) {

            throw std::runtime_error(errnoMessage("SO_RCVTIMEO"));
        }

        if (setsockopt(
                socketDescriptor.get(),
                SOL_SOCKET,
                SO_SNDTIMEO,
                &timeout,
                sizeof(timeout)) < 0) {

            throw std::runtime_error(errnoMessage("SO_SNDTIMEO"));
        }

        sockaddr_in serverAddress{};
        serverAddress.sin_family = AF_INET;
        serverAddress.sin_port = htons(port);

        // The case study uses IPv4 loopback. getaddrinfo() is normally
        // preferable when a real application must support hostnames and
        // IPv6 in addition to IPv4.
        if (inet_pton(
                AF_INET,
                host.c_str(),
                &serverAddress.sin_addr) != 1) {

            throw std::invalid_argument(
                "This case-study client expects a numeric IPv4 address."
            );
        }

        if (connect(
                socketDescriptor.get(),
                reinterpret_cast<sockaddr*>(&serverAddress),
                sizeof(serverAddress)) < 0) {

            throw std::runtime_error(errnoMessage("connect"));
        }

        size_t sentTotal = 0;

        while (sentTotal < message.size()) {
            const ssize_t sent = send(
                socketDescriptor.get(),
                message.data() + sentTotal,
                message.size() - sentTotal,
                0
            );

            if (sent < 0) {
                throw std::runtime_error(errnoMessage("send"));
            }

            if (sent == 0) {
                throw std::runtime_error("TCP connection made no progress.");
            }

            sentTotal += static_cast<size_t>(sent);
        }

        std::string response;
        char buffer[4096]{};

        const ssize_t received = recv(
            socketDescriptor.get(),
            buffer,
            sizeof(buffer),
            0
        );

        if (received < 0) {
            throw std::runtime_error(errnoMessage("recv"));
        }

        response.assign(
            buffer,
            static_cast<size_t>(received)
        );

        return response;
    }
};


// ---------------------------------------------------------------------------
// UDP telemetry sender
// ---------------------------------------------------------------------------

class UdpTelemetrySender {
public:
    static void sendMessage(
        const std::string& destination,
        uint16_t port,
        const std::string& message) {

        FileDescriptor socketDescriptor(
            socket(AF_INET, SOCK_DGRAM, 0)
        );

        if (!socketDescriptor.valid()) {
            throw std::runtime_error(errnoMessage("UDP socket"));
        }

        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_port = htons(port);

        if (inet_pton(
                AF_INET,
                destination.c_str(),
                &address.sin_addr) != 1) {

            throw std::invalid_argument(
                "Invalid UDP destination address."
            );
        }

        const ssize_t sent = sendto(
            socketDescriptor.get(),
            message.data(),
            message.size(),
            0,
            reinterpret_cast<sockaddr*>(&address),
            sizeof(address)
        );

        if (sent < 0) {
            throw std::runtime_error(errnoMessage("sendto"));
        }

        if (static_cast<size_t>(sent) != message.size()) {
            throw std::runtime_error(
                "UDP datagram was not sent completely."
            );
        }
    }
};


// ---------------------------------------------------------------------------
// DNS-style hostname lookup
// ---------------------------------------------------------------------------

std::vector<std::string> resolveHostname(
    const std::string& hostname) {

    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    addrinfo* results = nullptr;

    const int status = getaddrinfo(
        hostname.c_str(),
        nullptr,
        &hints,
        &results
    );

    if (status != 0) {
        throw std::runtime_error(
            "getaddrinfo(" +
            hostname +
            "): " +
            gai_strerror(status)
        );
    }

    std::vector<std::string> addresses;

    for (
        addrinfo* current = results;
        current != nullptr;
        current = current->ai_next) {

        char addressBuffer[INET6_ADDRSTRLEN]{};

        if (current->ai_family == AF_INET) {
            auto* ipv4 =
                reinterpret_cast<sockaddr_in*>(current->ai_addr);

            if (inet_ntop(
                    AF_INET,
                    &ipv4->sin_addr,
                    addressBuffer,
                    sizeof(addressBuffer))) {

                addresses.emplace_back(addressBuffer);
            }
        } else if (current->ai_family == AF_INET6) {
            auto* ipv6 =
                reinterpret_cast<sockaddr_in6*>(current->ai_addr);

            if (inet_ntop(
                    AF_INET6,
                    &ipv6->sin6_addr,
                    addressBuffer,
                    sizeof(addressBuffer))) {

                addresses.emplace_back(addressBuffer);
            }
        }
    }

    freeaddrinfo(results);

    std::sort(addresses.begin(), addresses.end());
    addresses.erase(
        std::unique(addresses.begin(), addresses.end()),
        addresses.end()
    );

    return addresses;
}


// ---------------------------------------------------------------------------
// TCP port test
// ---------------------------------------------------------------------------

struct PortTestResult {
    bool reachable;
    std::string state;
    double milliseconds;
};


PortTestResult testTcpPort(
    const std::string& host,
    uint16_t port) {

    const auto started =
        std::chrono::steady_clock::now();

    FileDescriptor socketDescriptor(
        socket(AF_INET, SOCK_STREAM, 0)
    );

    if (!socketDescriptor.valid()) {
        const auto ended =
            std::chrono::steady_clock::now();

        const double milliseconds =
            std::chrono::duration<double, std::milli>(
                ended - started
            ).count();

        return {
            false,
            errnoMessage("socket"),
            milliseconds
        };
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port);

    if (inet_pton(
            AF_INET,
            host.c_str(),
            &address.sin_addr) != 1) {

        const auto ended =
            std::chrono::steady_clock::now();

        const double milliseconds =
            std::chrono::duration<double, std::milli>(
                ended - started
            ).count();

        return {
            false,
            "invalid IPv4 address",
            milliseconds
        };
    }

    if (connect(
            socketDescriptor.get(),
            reinterpret_cast<sockaddr*>(&address),
            sizeof(address)) < 0) {

        const auto ended =
            std::chrono::steady_clock::now();

        const double milliseconds =
            std::chrono::duration<double, std::milli>(
                ended - started
            ).count();

        return {
            false,
            std::strerror(errno),
            milliseconds
        };
    }

    const auto ended =
        std::chrono::steady_clock::now();

    const double milliseconds =
        std::chrono::duration<double, std::milli>(
            ended - started
        ).count();

    return {
        true,
        "open",
        milliseconds
    };
}


// ---------------------------------------------------------------------------
// Telemetry packet model
// ---------------------------------------------------------------------------

struct TelemetryPacket {
    uint64_t sequence;
    double temperature;
    double packetLossPercent;
};


class TelemetryAnalyzer {
public:
    static double averageTemperature(
        const std::vector<TelemetryPacket>& packets) {

        if (packets.empty()) {
            throw std::invalid_argument(
                "Cannot calculate average of empty telemetry."
            );
        }

        double total = 0.0;

        for (const auto& packet : packets) {
            total += packet.temperature;
        }

        return total / packets.size();
    }

    static double averageLoss(
        const std::vector<TelemetryPacket>& packets) {

        if (packets.empty()) {
            throw std::invalid_argument(
                "Cannot calculate loss of empty telemetry."
            );
        }

        double total = 0.0;

        for (const auto& packet : packets) {
            total += packet.packetLossPercent;
        }

        return total / packets.size();
    }
};


// ---------------------------------------------------------------------------
// Concurrent monitoring simulation
// ---------------------------------------------------------------------------

class ConcurrentMonitor {
private:
    std::mutex mutex_;
    std::vector<TelemetryPacket> packets_;
    std::atomic<bool> running_{true};

public:
    void collect(int workerId, int count) {
        for (int index = 0; index < count && running_; ++index) {
            TelemetryPacket packet{
                static_cast<uint64_t>(
                    workerId * 1000 + index
                ),
                20.0 +
                    static_cast<double>(
                        (workerId * 7 + index) % 15
                    ),
                static_cast<double>(
                    (workerId + index) % 3
                )
            };

            {
                std::lock_guard<std::mutex> lock(mutex_);
                packets_.push_back(packet);
            }

            std::this_thread::sleep_for(
                std::chrono::milliseconds(5)
            );
        }
    }

    void stop() {
        running_ = false;
    }

    std::vector<TelemetryPacket> snapshot() {
        std::lock_guard<std::mutex> lock(mutex_);
        return packets_;
    }
};


// ---------------------------------------------------------------------------
// Main case study
// ---------------------------------------------------------------------------

int main() {
    try {
        printSection("LINUX NETWORKING TECHNICAL CASE STUDY");

        std::cout
            << "Scenario: secure local gateway with routing, TCP service,\n"
            << "UDP telemetry, DNS resolution, and diagnostics.\n";

        // -------------------------------------------------------------------
        // Stage 1: Interface configuration
        // -------------------------------------------------------------------

        printSection("1. INTERFACE CONFIGURATION");

        InterfaceConfiguration configuration{
            "lo",
            IPv4Address::parse("127.0.0.1"),
            IPv4Network::parse("127.0.0.0/8")
        };

        ConfigurationValidator::validate(configuration);

        std::cout
            << "Interface: " << configuration.name << "\n"
            << "Address:   " << configuration.address.toString() << "\n"
            << "Network:   " << configuration.network.toString() << "\n"
            << "Validation: PASS\n";


        // -------------------------------------------------------------------
        // Stage 2: Route table
        // -------------------------------------------------------------------

        printSection("2. ROUTING TABLE");

        RoutingTable routingTable;

        routingTable.addRoute({
            IPv4Network::parse("0.0.0.0/0"),
            "192.168.1.1",
            "eth0",
            100
        });

        routingTable.addRoute({
            IPv4Network::parse("192.168.1.0/24"),
            "direct",
            "eth0",
            100
        });

        routingTable.addRoute({
            IPv4Network::parse("192.168.1.128/25"),
            "direct",
            "eth0",
            50
        });

        routingTable.addRoute({
            IPv4Network::parse("10.0.0.0/8"),
            "192.168.1.254",
            "eth0",
            200
        });

        routingTable.print();

        std::vector<std::string> destinations{
            "192.168.1.25",
            "192.168.1.200",
            "10.20.30.40",
            "8.8.8.8"
        };

        std::cout << "\nRoute decisions:\n";

        for (const auto& destinationText : destinations) {
            const auto destination =
                IPv4Address::parse(destinationText);

            const auto route =
                routingTable.lookup(destination);

            if (!route) {
                std::cout
                    << destinationText
                    << " -> NO ROUTE\n";
                continue;
            }

            std::cout
                << destinationText
                << " -> "
                << route->network.toString()
                << " via "
                << route->gateway
                << " dev "
                << route->interfaceName
                << " metric "
                << route->metric
                << "\n";
        }


        // -------------------------------------------------------------------
        // Stage 3: IPv4 edge cases
        // -------------------------------------------------------------------

        printSection("3. ADDRESSING EDGE CASES");

        const std::vector<std::string> testAddresses{
            "0.0.0.0",
            "127.0.0.1",
            "192.168.1.255",
            "255.255.255.255"
        };

        for (const auto& text : testAddresses) {
            try {
                const auto address = IPv4Address::parse(text);

                std::cout
                    << text
                    << " -> parsed as "
                    << address.toString()
                    << "\n";
            } catch (const std::exception& error) {
                std::cout
                    << text
                    << " -> ERROR: "
                    << error.what()
                    << "\n";
            }
        }


        // -------------------------------------------------------------------
        // Stage 4: TCP service
        // -------------------------------------------------------------------

        printSection("4. TCP SERVICE");

        TcpEchoServer tcpServer;
        tcpServer.start();

        std::cout
            << "TCP server listening on 127.0.0.1:"
            << tcpServer.port()
            << "\n";

        std::thread tcpWorker(
            [&tcpServer]() {
                try {
                    tcpServer.serveOnce();
                } catch (const std::exception& error) {
                    std::cerr
                        << "TCP worker error: "
                        << error.what()
                        << "\n";
                }
            }
        );

        std::this_thread::sleep_for(
            std::chrono::milliseconds(50)
        );

        const auto tcpStarted =
            std::chrono::steady_clock::now();

        const std::string response =
            TcpClient::request(
                "127.0.0.1",
                tcpServer.port(),
                "telemetry-request"
            );

        const auto tcpEnded =
            std::chrono::steady_clock::now();

        const double tcpMilliseconds =
            std::chrono::duration<double, std::milli>(
                tcpEnded - tcpStarted
            ).count();

        tcpWorker.join();

        std::cout
            << "Server response: "
            << response
            << "\n"
            << "Round-trip time: "
            << std::fixed
            << std::setprecision(3)
            << tcpMilliseconds
            << " ms\n";


        // -------------------------------------------------------------------
        // Stage 5: UDP telemetry
        // -------------------------------------------------------------------

        printSection("5. UDP TELEMETRY");

        // UDP does not establish a TCP-style connection. This demonstration
        // sends a datagram and reports the send result. A production telemetry
        // protocol may add sequence numbers, acknowledgements, timestamps,
        // authentication, integrity protection, and retransmission logic.
        UdpTelemetrySender::sendMessage(
            "127.0.0.1",
            9999,
            "temperature=24.5"
        );

        std::cout
            << "UDP telemetry datagram sent to 127.0.0.1:9999.\n"
            << "No delivery guarantee is inferred from successful sendto().\n";


        // -------------------------------------------------------------------
        // Stage 6: DNS
        // -------------------------------------------------------------------

        printSection("6. DNS RESOLUTION");

        const std::string hostname = "example.com";

        const auto dnsStarted =
            std::chrono::steady_clock::now();

        const auto addresses =
            resolveHostname(hostname);

        const auto dnsEnded =
            std::chrono::steady_clock::now();

        const double dnsMilliseconds =
            std::chrono::duration<double, std::milli>(
                dnsEnded - dnsStarted
            ).count();

        std::cout
            << hostname
            << " resolved to:\n";

        for (const auto& address : addresses) {
            std::cout
                << "  "
                << address
                << "\n";
        }

        std::cout
            << "Resolution time: "
            << std::fixed
            << std::setprecision(3)
            << dnsMilliseconds
            << " ms\n";


        // -------------------------------------------------------------------
        // Stage 7: Port diagnostics
        // -------------------------------------------------------------------

        printSection("7. TCP PORT DIAGNOSTICS");

        // DNS resolution above demonstrates name-to-address translation.
        // For a focused port test, use a known numeric address.
        const auto localPortResult =
            testTcpPort(
                "127.0.0.1",
                tcpServer.port()
            );

        std::cout
            << "127.0.0.1:"
            << tcpServer.port()
            << " -> "
            << localPortResult.state
            << " in "
            << localPortResult.milliseconds
            << " ms\n";


        // -------------------------------------------------------------------
        // Stage 8: Telemetry analytics
        // -------------------------------------------------------------------

        printSection("8. TELEMETRY ANALYSIS");

        std::vector<TelemetryPacket> telemetry{
            {1, 22.1, 0.0},
            {2, 22.7, 0.5},
            {3, 23.0, 0.0},
            {4, 23.4, 1.0},
            {5, 23.8, 0.5}
        };

        std::cout
            << "Average temperature: "
            << TelemetryAnalyzer::averageTemperature(telemetry)
            << "\n";

        std::cout
            << "Average packet loss: "
            << TelemetryAnalyzer::averageLoss(telemetry)
            << "%\n";


        // -------------------------------------------------------------------
        // Stage 9: Concurrent collectors
        // -------------------------------------------------------------------

        printSection("9. CONCURRENT NETWORK MONITORING");

        ConcurrentMonitor monitor;

        std::thread collectorOne(
            [&monitor]() {
                monitor.collect(1, 10);
            }
        );

        std::thread collectorTwo(
            [&monitor]() {
                monitor.collect(2, 10);
            }
        );

        collectorOne.join();
        collectorTwo.join();

        const auto snapshot = monitor.snapshot();

        std::cout
            << "Collected packets: "
            << snapshot.size()
            << "\n";

        std::cout
            << "Average temperature: "
            << TelemetryAnalyzer::averageTemperature(snapshot)
            << "\n";

        std::cout
            << "Average packet loss: "
            << TelemetryAnalyzer::averageLoss(snapshot)
            << "%\n";


        // -------------------------------------------------------------------
        // Stage 10: Failure conditions
        // -------------------------------------------------------------------

        printSection("10. FAILURE CONDITION TESTS");

        try {
            IPv4Address::parse("300.1.1.1");
        } catch (const std::exception& error) {
            std::cout
                << "Invalid IPv4 test: "
                << error.what()
                << "\n";
        }

        try {
            IPv4Network::parse("192.168.1.0/40");
        } catch (const std::exception& error) {
            std::cout
                << "Invalid CIDR test: "
                << error.what()
                << "\n";
        }

        try {
            InterfaceConfiguration invalid{
                "eth-test",
                IPv4Address::parse("10.0.0.10"),
                IPv4Network::parse("192.168.1.0/24")
            };

            ConfigurationValidator::validate(invalid);
        } catch (const std::exception& error) {
            std::cout
                << "Subnet validation test: "
                << error.what()
                << "\n";
        }


        // -------------------------------------------------------------------
        // Stage 11: Architecture and operational reasoning
        // -------------------------------------------------------------------

        printSection("11. SYSTEM DESIGN CONSIDERATIONS");

        std::cout
            << "Interface layer: validates local adapter/address state.\n"
            << "Routing layer: selects a route using longest-prefix matching.\n"
            << "Transport layer: TCP provides reliable streams; UDP provides datagrams.\n"
            << "Naming layer: getaddrinfo integrates hostname resolution.\n"
            << "Application layer: telemetry is processed into operational metrics.\n"
            << "Concurrency: independent collectors can execute in parallel.\n"
            << "Resource safety: RAII closes sockets on scope exit.\n"
            << "Security: TCP service binds to loopback rather than all interfaces.\n";


        // -------------------------------------------------------------------
        // Stage 12: Complexity
        // -------------------------------------------------------------------

        printSection("12. COMPLEXITY CONSIDERATIONS");

        std::cout
            << "Route lookup in this educational table: O(R log R) because\n"
            << "matching routes are sorted for every lookup. A production\n"
            << "routing implementation uses specialized kernel structures.\n\n"

            << "Telemetry average: O(N) time and O(1) additional arithmetic state.\n\n"

            << "Interface configuration validation: O(1).\n\n"

            << "Concurrent collection: O(N) total work across all packets,\n"
            << "with mutex contention depending on the number of workers.\n";


        // -------------------------------------------------------------------
        // Stage 13: Production considerations
        // -------------------------------------------------------------------

        printSection("13. PRODUCTION CONSIDERATIONS");

        std::cout
            << "A production gateway should also address:\n"
            << "  - TLS and certificate validation for encrypted services.\n"
            << "  - Authentication and authorization.\n"
            << "  - Firewall and ACL policy.\n"
            << "  - IPv6 support where required.\n"
            << "  - Structured logging and metrics.\n"
            << "  - Graceful shutdown and signal handling.\n"
            << "  - Backpressure and bounded queues.\n"
            << "  - Connection limits and resource exhaustion protection.\n"
            << "  - DNS failure and cache behavior.\n"
            << "  - Monitoring for packet loss, latency, jitter, and errors.\n"
            << "  - Packet capture during authorized investigations.\n"
            << "  - Network namespace and container isolation where appropriate.\n";


        // -------------------------------------------------------------------
        // Final result
        // -------------------------------------------------------------------

        printSection("14. CASE STUDY COMPLETE");

        std::cout
            << "The case study successfully demonstrated a layered Linux\n"
            << "networking model: addressing, routing, transport, naming,\n"
            << "application traffic, concurrency, diagnostics, and security.\n";

        return 0;

    } catch (const std::exception& error) {
        std::cerr
            << "\nFatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
