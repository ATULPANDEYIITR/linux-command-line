/*
 * TCP AND UDP: C++ INDUSTRY-STYLE CASE STUDY
 * ===========================================
 *
 * Scenario:
 * ---------
 * A telemetry gateway receives status updates from distributed devices.
 *
 * The system needs two communication modes:
 *
 * 1. TCP:
 *    Used for reliable configuration transfer and commands.
 *
 * 2. UDP:
 *    Used for lightweight telemetry where low overhead and datagram
 *    boundaries are useful.
 *
 * The program demonstrates:
 *
 * - IPv4 sockets
 * - TCP server/client behavior
 * - UDP server/client behavior
 * - application-level TCP framing
 * - UDP packet validation
 * - sequence numbers
 * - duplicate detection
 * - timeout concepts
 * - input validation
 * - checksums
 * - statistics
 * - error handling
 * - RAII socket management
 * - complexity and architectural trade-offs
 *
 * Platform:
 * ----------
 * POSIX/Linux/macOS socket API.
 *
 * Compile:
 * ----------
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic tcp_udp_case_study.cpp -o tcp_udp_case_study
 *
 * Run:
 * ----------
 * ./tcp_udp_case_study
 *
 * This program uses loopback networking only.
 */

#include <arpa/inet.h>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <netinet/in.h>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>
#include <sys/socket.h>


// ============================================================================
// 1. GENERAL UTILITIES
// ============================================================================

namespace netstudy {

constexpr uint16_t TCP_PORT = 0;
constexpr uint16_t UDP_PORT = 0;

constexpr std::size_t MAX_FRAME_SIZE = 1024 * 1024;
constexpr std::size_t MAX_UDP_PAYLOAD = 1200;

void printSection(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}

void checkSystemCall(int result, const std::string& operation) {
    if (result < 0) {
        throw std::runtime_error(
            operation + " failed: " + std::strerror(errno)
        );
    }
}


// ============================================================================
// 2. RAII SOCKET WRAPPER
// ============================================================================

class Socket {
private:
    int fd_;

public:
    Socket() : fd_(-1) {}

    explicit Socket(int fd) : fd_(fd) {}

    Socket(const Socket&) = delete;
    Socket& operator=(const Socket&) = delete;

    Socket(Socket&& other) noexcept : fd_(other.fd_) {
        other.fd_ = -1;
    }

    Socket& operator=(Socket&& other) noexcept {
        if (this != &other) {
            close();
            fd_ = other.fd_;
            other.fd_ = -1;
        }

        return *this;
    }

    ~Socket() {
        close();
    }

    int get() const {
        return fd_;
    }

    bool valid() const {
        return fd_ >= 0;
    }

    void reset(int fd = -1) {
        close();
        fd_ = fd;
    }

    void close() {
        if (fd_ >= 0) {
            ::close(fd_);
            fd_ = -1;
        }
    }

    void setReceiveTimeout(int milliseconds) {
        timeval timeout{};
        timeout.tv_sec = milliseconds / 1000;
        timeout.tv_usec = (milliseconds % 1000) * 1000;

        if (setsockopt(
                fd_,
                SOL_SOCKET,
                SO_RCVTIMEO,
                &timeout,
                sizeof(timeout)
            ) < 0) {
            throw std::runtime_error(
                "setsockopt(SO_RCVTIMEO) failed: " +
                std::string(std::strerror(errno))
            );
        }
    }
};


// ============================================================================
// 3. TCP FRAMING
// ============================================================================

/*
 * TCP gives applications a byte stream.
 *
 * Therefore an application protocol needs a way to identify where one
 * message ends and another begins.
 *
 * This case study uses:
 *
 *     [4-byte network-order length][payload]
 *
 * Network byte order is big-endian.
 */

uint32_t readUint32Network(const std::vector<uint8_t>& data, std::size_t offset) {
    if (offset + 4 > data.size()) {
        throw std::runtime_error("Insufficient bytes for uint32");
    }

    uint32_t value = 0;

    value |= static_cast<uint32_t>(data[offset]) << 24;
    value |= static_cast<uint32_t>(data[offset + 1]) << 16;
    value |= static_cast<uint32_t>(data[offset + 2]) << 8;
    value |= static_cast<uint32_t>(data[offset + 3]);

    return value;
}

void appendUint32Network(
    std::vector<uint8_t>& output,
    uint32_t value
) {
    output.push_back(static_cast<uint8_t>((value >> 24) & 0xFF));
    output.push_back(static_cast<uint8_t>((value >> 16) & 0xFF));
    output.push_back(static_cast<uint8_t>((value >> 8) & 0xFF));
    output.push_back(static_cast<uint8_t>(value & 0xFF));
}

std::vector<uint8_t> encodeFrame(const std::string& message) {
    if (message.size() > MAX_FRAME_SIZE) {
        throw std::invalid_argument("TCP message exceeds maximum size");
    }

    std::vector<uint8_t> result;
    result.reserve(4 + message.size());

    appendUint32Network(
        result,
        static_cast<uint32_t>(message.size())
    );

    result.insert(
        result.end(),
        message.begin(),
        message.end()
    );

    return result;
}

class FrameDecoder {
private:
    std::vector<uint8_t> buffer_;

public:
    std::vector<std::string> feed(
        const uint8_t* data,
        std::size_t length
    ) {
        if (data == nullptr && length != 0) {
            throw std::invalid_argument("Null data pointer");
        }

        buffer_.insert(
            buffer_.end(),
            data,
            data + length
        );

        std::vector<std::string> messages;

        while (buffer_.size() >= 4) {
            const uint32_t payloadLength =
                readUint32Network(buffer_, 0);

            if (payloadLength > MAX_FRAME_SIZE) {
                throw std::runtime_error(
                    "TCP frame exceeds configured maximum"
                );
            }

            const std::size_t totalLength =
                4 + static_cast<std::size_t>(payloadLength);

            if (buffer_.size() < totalLength) {
                break;
            }

            std::string message(
                buffer_.begin() + 4,
                buffer_.begin() + totalLength
            );

            messages.push_back(std::move(message));

            buffer_.erase(
                buffer_.begin(),
                buffer_.begin() + static_cast<std::ptrdiff_t>(totalLength)
            );
        }

        return messages;
    }

    std::size_t bufferedBytes() const {
        return buffer_.size();
    }
};


// ============================================================================
// 4. RELIABLE SEND
// ============================================================================

void sendAll(
    int socketFd,
    const uint8_t* data,
    std::size_t length
) {
    std::size_t sent = 0;

    while (sent < length) {
        const ssize_t result = ::send(
            socketFd,
            data + sent,
            length - sent,
            0
        );

        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }

            throw std::runtime_error(
                "send failed: " + std::string(std::strerror(errno))
            );
        }

        if (result == 0) {
            throw std::runtime_error(
                "send returned zero before completion"
            );
        }

        sent += static_cast<std::size_t>(result);
    }
}

std::string receiveTcpFrame(int socketFd) {
    std::vector<uint8_t> header(4);

    std::size_t received = 0;

    while (received < 4) {
        const ssize_t result = ::recv(
            socketFd,
            header.data() + received,
            4 - received,
            0
        );

        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }

            throw std::runtime_error(
                "recv header failed: " +
                std::string(std::strerror(errno))
            );
        }

        if (result == 0) {
            throw std::runtime_error(
                "Peer closed TCP connection before frame header"
            );
        }

        received += static_cast<std::size_t>(result);
    }

    const uint32_t payloadLength =
        readUint32Network(header, 0);

    if (payloadLength > MAX_FRAME_SIZE) {
        throw std::runtime_error(
            "Received TCP frame is too large"
        );
    }

    std::vector<uint8_t> payload(payloadLength);

    received = 0;

    while (received < payload.size()) {
        const ssize_t result = ::recv(
            socketFd,
            payload.data() + received,
            payload.size() - received,
            0
        );

        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }

            throw std::runtime_error(
                "recv payload failed: " +
                std::string(std::strerror(errno))
            );
        }

        if (result == 0) {
            throw std::runtime_error(
                "Peer closed TCP connection during frame"
            );
        }

        received += static_cast<std::size_t>(result);
    }

    return std::string(payload.begin(), payload.end());
}


// ============================================================================
// 5. TELEMETRY MESSAGE MODEL
// ============================================================================

struct TelemetryMessage {
    uint32_t deviceId;
    uint32_t sequence;
    int32_t temperatureCelsiusTimes100;
    uint32_t batteryMillivolts;
    uint64_t timestampSeconds;
};

std::string telemetryToText(const TelemetryMessage& telemetry) {
    std::ostringstream output;

    output
        << "device=" << telemetry.deviceId
        << ", sequence=" << telemetry.sequence
        << ", temperature="
        << std::fixed
        << std::setprecision(2)
        << telemetry.temperatureCelsiusTimes100 / 100.0
        << " C"
        << ", battery="
        << telemetry.batteryMillivolts
        << " mV"
        << ", timestamp="
        << telemetry.timestampSeconds;

    return output.str();
}


// ============================================================================
// 6. CHECKSUM
// ============================================================================

/*
 * This is a small educational checksum, not a replacement for a
 * cryptographic integrity mechanism.
 *
 * Production security protocols should use authenticated encryption or
 * another standardized integrity mechanism.
 */

uint32_t fnv1a(const std::vector<uint8_t>& data) {
    uint32_t hash = 2166136261u;

    for (uint8_t byte : data) {
        hash ^= byte;
        hash *= 16777619u;
    }

    return hash;
}


// ============================================================================
// 7. UDP TELEMETRY PACKET
// ============================================================================

std::vector<uint8_t> encodeTelemetry(
    const TelemetryMessage& telemetry
) {
    /*
     * Wire layout:
     *
     * magic       2 bytes
     * version     1 byte
     * device ID   4 bytes
     * sequence    4 bytes
     * temperature 4 bytes
     * battery     4 bytes
     * timestamp   8 bytes
     * checksum    4 bytes
     *
     * The structure is manually serialized so the program does not depend
     * on compiler-specific struct padding or native endianness.
     */

    std::vector<uint8_t> packet;

    packet.push_back('T');
    packet.push_back('M');
    packet.push_back(1);

    appendUint32Network(packet, telemetry.deviceId);
    appendUint32Network(packet, telemetry.sequence);

    appendUint32Network(
        packet,
        static_cast<uint32_t>(
            telemetry.temperatureCelsiusTimes100
        )
    );

    appendUint32Network(packet, telemetry.batteryMillivolts);

    const uint64_t timestamp = telemetry.timestampSeconds;

    for (int shift = 56; shift >= 0; shift -= 8) {
        packet.push_back(
            static_cast<uint8_t>((timestamp >> shift) & 0xFF)
        );
    }

    const uint32_t checksum = fnv1a(packet);

    appendUint32Network(packet, checksum);

    if (packet.size() > MAX_UDP_PAYLOAD) {
        throw std::runtime_error("UDP telemetry packet too large");
    }

    return packet;
}

TelemetryMessage decodeTelemetry(
    const uint8_t* data,
    std::size_t length
) {
    constexpr std::size_t BASE_SIZE = 3 + 4 + 4 + 4 + 4 + 8;
    constexpr std::size_t TOTAL_SIZE = BASE_SIZE + 4;

    if (data == nullptr || length != TOTAL_SIZE) {
        throw std::runtime_error(
            "Invalid telemetry packet size"
        );
    }

    if (data[0] != 'T' || data[1] != 'M') {
        throw std::runtime_error(
            "Invalid telemetry magic"
        );
    }

    if (data[2] != 1) {
        throw std::runtime_error(
            "Unsupported telemetry protocol version"
        );
    }

    std::vector<uint8_t> withoutChecksum(
        data,
        data + BASE_SIZE
    );

    const uint32_t expectedChecksum =
        fnv1a(withoutChecksum);

    const uint32_t receivedChecksum =
        readUint32Network(
            std::vector<uint8_t>(data, data + length),
            BASE_SIZE
        );

    if (expectedChecksum != receivedChecksum) {
        throw std::runtime_error(
            "Telemetry checksum mismatch"
        );
    }

    std::vector<uint8_t> bytes(
        data,
        data + length
    );

    TelemetryMessage telemetry{};

    telemetry.deviceId =
        readUint32Network(bytes, 3);

    telemetry.sequence =
        readUint32Network(bytes, 7);

    telemetry.temperatureCelsiusTimes100 =
        static_cast<int32_t>(
            readUint32Network(bytes, 11)
        );

    telemetry.batteryMillivolts =
        readUint32Network(bytes, 15);

    uint64_t timestamp = 0;

    for (std::size_t index = 19; index < 27; ++index) {
        timestamp =
            (timestamp << 8) |
            static_cast<uint64_t>(bytes[index]);
    }

    telemetry.timestampSeconds = timestamp;

    return telemetry;
}


// ============================================================================
// 8. TELEMETRY VALIDATION
// ============================================================================

void validateTelemetry(
    const TelemetryMessage& telemetry
) {
    if (telemetry.deviceId == 0) {
        throw std::invalid_argument(
            "Device ID cannot be zero"
        );
    }

    if (telemetry.batteryMillivolts > 10000) {
        throw std::invalid_argument(
            "Battery voltage is outside configured range"
        );
    }

    const double temperature =
        telemetry.temperatureCelsiusTimes100 / 100.0;

    if (temperature < -100.0 || temperature > 150.0) {
        throw std::invalid_argument(
            "Temperature is outside configured range"
        );
    }
}


// ============================================================================
// 9. TCP CONFIGURATION SERVER
// ============================================================================

class TcpConfigurationServer {
private:
    Socket serverSocket_;

public:
    uint16_t start() {
        serverSocket_.reset(
            ::socket(AF_INET, SOCK_STREAM, 0)
        );

        if (!serverSocket_.valid()) {
            throw std::runtime_error(
                "Unable to create TCP socket"
            );
        }

        int reuse = 1;

        if (setsockopt(
                serverSocket_.get(),
                SOL_SOCKET,
                SO_REUSEADDR,
                &reuse,
                sizeof(reuse)
            ) < 0) {
            throw std::runtime_error(
                "Unable to configure SO_REUSEADDR"
            );
        }

        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        address.sin_port = htons(TCP_PORT);

        checkSystemCall(
            ::bind(
                serverSocket_.get(),
                reinterpret_cast<sockaddr*>(&address),
                sizeof(address)
            ),
            "TCP bind"
        );

        checkSystemCall(
            ::listen(serverSocket_.get(), 8),
            "TCP listen"
        );

        socklen_t length = sizeof(address);

        checkSystemCall(
            ::getsockname(
                serverSocket_.get(),
                reinterpret_cast<sockaddr*>(&address),
                &length
            ),
            "getsockname"
        );

        return ntohs(address.sin_port);
    }

    void serveOneClient() {
        sockaddr_in clientAddress{};
        socklen_t clientLength = sizeof(clientAddress);

        int clientFd = ::accept(
            serverSocket_.get(),
            reinterpret_cast<sockaddr*>(&clientAddress),
            &clientLength
        );

        if (clientFd < 0) {
            throw std::runtime_error(
                "TCP accept failed: " +
                std::string(std::strerror(errno))
            );
        }

        Socket client(clientFd);

        std::string request =
            receiveTcpFrame(client.get());

        std::cout
            << "TCP server received command: "
            << request
            << "\n";

        const std::string response =
            "CONFIGURATION ACCEPTED: " + request;

        const std::vector<uint8_t> frame =
            encodeFrame(response);

        sendAll(
            client.get(),
            frame.data(),
            frame.size()
        );
    }
};


// ============================================================================
// 10. TCP CONFIGURATION CLIENT
// ============================================================================

std::string runTcpClient(
    uint16_t port,
    const std::string& command
) {
    Socket socket(
        ::socket(AF_INET, SOCK_STREAM, 0)
    );

    if (!socket.valid()) {
        throw std::runtime_error(
            "Unable to create TCP client socket"
        );
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    checkSystemCall(
        ::connect(
            socket.get(),
            reinterpret_cast<sockaddr*>(&address),
            sizeof(address)
        ),
        "TCP connect"
    );

    const std::vector<uint8_t> frame =
        encodeFrame(command);

    sendAll(
        socket.get(),
        frame.data(),
        frame.size()
    );

    return receiveTcpFrame(socket.get());
}


// ============================================================================
// 11. UDP TELEMETRY SERVER
// ============================================================================

class UdpTelemetryServer {
private:
    Socket socket_;
    std::set<uint32_t> seenSequences_;

public:
    uint16_t start() {
        socket_.reset(
            ::socket(AF_INET, SOCK_DGRAM, 0)
        );

        if (!socket_.valid()) {
            throw std::runtime_error(
                "Unable to create UDP socket"
            );
        }

        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        address.sin_port = htons(UDP_PORT);

        checkSystemCall(
            ::bind(
                socket_.get(),
                reinterpret_cast<sockaddr*>(&address),
                sizeof(address)
            ),
            "UDP bind"
        );

        socklen_t length = sizeof(address);

        checkSystemCall(
            ::getsockname(
                socket_.get(),
                reinterpret_cast<sockaddr*>(&address),
                &length
            ),
            "UDP getsockname"
        );

        return ntohs(address.sin_port);
    }

    void receiveOne() {
        std::array<uint8_t, MAX_UDP_PAYLOAD> buffer{};

        sockaddr_in sender{};
        socklen_t senderLength = sizeof(sender);

        const ssize_t received = ::recvfrom(
            socket_.get(),
            buffer.data(),
            buffer.size(),
            0,
            reinterpret_cast<sockaddr*>(&sender),
            &senderLength
        );

        if (received < 0) {
            throw std::runtime_error(
                "UDP recvfrom failed: " +
                std::string(std::strerror(errno))
            );
        }

        try {
            TelemetryMessage telemetry =
                decodeTelemetry(
                    buffer.data(),
                    static_cast<std::size_t>(received)
                );

            validateTelemetry(telemetry);

            if (seenSequences_.contains(telemetry.sequence)) {
                std::cout
                    << "UDP duplicate sequence "
                    << telemetry.sequence
                    << " ignored.\n";

                return;
            }

            seenSequences_.insert(telemetry.sequence);

            std::cout
                << "UDP telemetry accepted: "
                << telemetryToText(telemetry)
                << "\n";

        } catch (const std::exception& error) {
            std::cerr
                << "Rejected UDP packet: "
                << error.what()
                << "\n";
        }
    }
};


// ============================================================================
// 12. UDP TELEMETRY CLIENT
// ============================================================================

void sendTelemetry(
    uint16_t port,
    const TelemetryMessage& telemetry
) {
    validateTelemetry(telemetry);

    const std::vector<uint8_t> packet =
        encodeTelemetry(telemetry);

    Socket socket(
        ::socket(AF_INET, SOCK_DGRAM, 0)
    );

    if (!socket.valid()) {
        throw std::runtime_error(
            "Unable to create UDP client socket"
        );
    }

    sockaddr_in destination{};
    destination.sin_family = AF_INET;
    destination.sin_port = htons(port);
    destination.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    const ssize_t sent = ::sendto(
        socket.get(),
        packet.data(),
        packet.size(),
        0,
        reinterpret_cast<sockaddr*>(&destination),
        sizeof(destination)
    );

    if (sent < 0) {
        throw std::runtime_error(
            "UDP sendto failed: " +
            std::string(std::strerror(errno))
        );
    }

    if (static_cast<std::size_t>(sent) != packet.size()) {
        throw std::runtime_error(
            "Unexpected partial UDP datagram send"
        );
    }
}


// ============================================================================
// 13. TCP STREAM CASE STUDY
// ============================================================================

void runTcpCaseStudy() {
    printSection("TCP CASE STUDY: RELIABLE DEVICE CONFIGURATION");

    TcpConfigurationServer server;

    const uint16_t port = server.start();

    std::exception_ptr serverError;

    std::thread serverThread(
        [&]() {
            try {
                server.serveOneClient();
            } catch (...) {
                serverError = std::current_exception();
            }
        }
    );

    // Give the server thread time to enter accept().
    std::this_thread::sleep_for(
        std::chrono::milliseconds(20)
    );

    const std::string response =
        runTcpClient(
            port,
            "SET REPORT_INTERVAL=30"
        );

    serverThread.join();

    if (serverError) {
        std::rethrow_exception(serverError);
    }

    std::cout
        << "TCP client received: "
        << response
        << "\n";
}


// ============================================================================
// 14. UDP TELEMETRY CASE STUDY
// ============================================================================

void runUdpCaseStudy() {
    printSection("UDP CASE STUDY: LOW-OVERHEAD TELEMETRY");

    UdpTelemetryServer server;

    const uint16_t port = server.start();

    std::thread serverThread(
        [&]() {
            server.receiveOne();
            server.receiveOne();
        }
    );

    std::this_thread::sleep_for(
        std::chrono::milliseconds(20)
    );

    const auto now =
        static_cast<uint64_t>(
            std::chrono::duration_cast<
                std::chrono::seconds
            >(
                std::chrono::system_clock::now().time_since_epoch()
            ).count()
        );

    TelemetryMessage first{
        101,
        1,
        2350,
        3750,
        now
    };

    TelemetryMessage duplicate{
        101,
        1,
        2350,
        3750,
        now
    };

    sendTelemetry(port, first);
    sendTelemetry(port, duplicate);

    serverThread.join();
}


// ============================================================================
// 15. EDGE CASE DEMONSTRATIONS
// ============================================================================

void runEdgeCaseTests() {
    printSection("EDGE CASES AND FAILURE CONDITIONS");

    // Oversized TCP message.
    try {
        std::string oversized(
            MAX_FRAME_SIZE + 1,
            'A'
        );

        encodeFrame(oversized);

        throw std::runtime_error(
            "Oversized TCP message was not rejected"
        );

    } catch (const std::invalid_argument& error) {
        std::cout
            << "Correctly rejected oversized TCP message: "
            << error.what()
            << "\n";
    }

    // Invalid telemetry device ID.
    try {
        TelemetryMessage invalid{
            0,
            10,
            2000,
            3700,
            100
        };

        validateTelemetry(invalid);

        throw std::runtime_error(
            "Invalid device ID was not rejected"
        );

    } catch (const std::invalid_argument& error) {
        std::cout
            << "Correctly rejected invalid telemetry: "
            << error.what()
            << "\n";
    }

    // Invalid checksum.
    try {
        TelemetryMessage valid{
            101,
            55,
            2200,
            3800,
            100
        };

        auto packet = encodeTelemetry(valid);

        packet[5] ^= 0xFF;

        decodeTelemetry(
            packet.data(),
            packet.size()
        );

        throw std::runtime_error(
            "Checksum corruption was not detected"
        );

    } catch (const std::runtime_error& error) {
        std::cout
            << "Correctly detected corrupted packet: "
            << error.what()
            << "\n";
    }
}


// ============================================================================
// 16. COMPLEXITY ANALYSIS
// ============================================================================

void printComplexityAnalysis() {
    printSection("ALGORITHMIC AND PERFORMANCE CONSIDERATIONS");

    std::cout << R"(
TCP framing:
    Encoding one message is O(n), where n is payload size.
    Receiving one framed message is O(n) for copying/processing payload.

UDP telemetry:
    Packet serialization is O(n).
    Packet validation is O(n).
    Duplicate lookup uses std::set, approximately O(log k), where k is
    the number of remembered sequence numbers.

For a high-throughput production system, an unordered_set may provide
average O(1) lookup, although it has different memory and collision
characteristics.

TCP:
    Reliable ordered delivery reduces application complexity but can cause
    head-of-line blocking at the byte-stream level.

UDP:
    Individual datagrams avoid TCP's stream semantics, but reliability,
    ordering, congestion control, and duplicate handling may need to be
    designed at another protocol layer.

The correct architecture depends on application semantics rather than
transport overhead alone.
)";
}


// ============================================================================
// 17. SECURITY ANALYSIS
// ============================================================================

void printSecurityAnalysis() {
    printSection("SECURITY CONSIDERATIONS");

    std::cout << R"(
This case study includes validation and a non-cryptographic checksum for
educational purposes.

The checksum is NOT authentication.

A production system should consider:

    - TLS for TCP-based protocols where appropriate.
    - Authenticated encryption for UDP-based protocols.
    - Authentication of devices.
    - Authorization of configuration commands.
    - Replay protection.
    - Rate limiting.
    - Maximum message and packet sizes.
    - Resource quotas.
    - Strict parser validation.
    - Secure key management.
    - Monitoring and audit logging.

A transport protocol does not automatically make an application secure.

TCP:
    Reliable delivery does not mean confidentiality or authentication.

UDP:
    Low overhead does not mean that security must be omitted.

QUIC demonstrates how sophisticated transport behavior can be constructed
over UDP while incorporating security and reliability mechanisms.
)";
}


// ============================================================================
// 18. ARCHITECTURAL COMPARISON
// ============================================================================

void printArchitectureComparison() {
    printSection("ARCHITECTURAL COMPARISON");

    struct Row {
        std::string property;
        std::string tcp;
        std::string udp;
    };

    const std::vector<Row> rows = {
        {
            "Communication model",
            "Connection-oriented",
            "Connectionless"
        },
        {
            "Application abstraction",
            "Ordered byte stream",
            "Independent datagrams"
        },
        {
            "Reliability",
            "Built in",
            "Application/protocol dependent"
        },
        {
            "Ordering",
            "Built in",
            "Not guaranteed"
        },
        {
            "Message boundaries",
            "Must be framed by application",
            "Datagram boundary preserved"
        },
        {
            "Flow control",
            "TCP provides it",
            "UDP does not"
        },
        {
            "Congestion control",
            "TCP provides mechanisms",
            "Not provided by basic UDP"
        },
        {
            "Typical examples",
            "HTTP, SSH, databases",
            "DNS, telemetry, real-time systems"
        }
    };

    for (const auto& row : rows) {
        std::cout
            << std::left
            << std::setw(25)
            << row.property
            << " | "
            << std::setw(35)
            << row.tcp
            << " | "
            << row.udp
            << "\n";
    }
}


// ============================================================================
// 19. MAIN
// ============================================================================

} // namespace netstudy


int main() {
    using namespace netstudy;

    try {
        printSection("TCP AND UDP INDUSTRY-STYLE C++ CASE STUDY");

        std::cout << R"(
Scenario:

A telemetry gateway receives two categories of traffic from distributed
devices.

1. Configuration commands:
   Reliability and ordered delivery are required, so TCP is used.

2. Telemetry:
   Small periodic updates benefit from datagram semantics. UDP is used,
   with explicit validation and duplicate detection at the application
   layer.

The implementation uses loopback sockets, making the demonstration local
and deterministic enough for study purposes.
)";

        runTcpCaseStudy();
        runUdpCaseStudy();
        runEdgeCaseTests();
        printComplexityAnalysis();
        printSecurityAnalysis();
        printArchitectureComparison();

        printSection("CASE STUDY COMPLETE");

        std::cout << R"(
Important transport distinction:

TCP:
    Connection-oriented and reliable ordered byte stream.

UDP:
    Connectionless datagrams without TCP's built-in reliability and
    ordering mechanisms.

The appropriate choice depends on the communication requirements of the
application.
)";

        return 0;

    } catch (const std::exception& error) {
        std::cerr
            << "\nFatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
