/*
 * IP Addressing Case Study
 *
 * Modern C++17
 *
 * Scenario:
 *     A medium-sized organization receives the IPv4 block 10.40.0.0/22
 *     for internal use. The network team must allocate address space for
 *     several departments, maintain DHCP-style leases, classify addresses,
 *     perform subnet membership checks, summarize routes, and model a
 *     simplified NAT/PAT boundary.
 *
 * The program also demonstrates IPv6 representation and prefix planning.
 *
 * No external libraries are required.
 */

#include <algorithm>
#include <array>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

using IPv4Integer = std::uint32_t;
using IPv6Integer = unsigned __int128;

// -----------------------------------------------------------------------------
// Utility functions
// -----------------------------------------------------------------------------

void printTitle(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}

std::vector<std::string> split(const std::string& text, char delimiter) {
    std::vector<std::string> parts;
    std::stringstream stream(text);
    std::string part;

    while (std::getline(stream, part, delimiter)) {
        parts.push_back(part);
    }

    return parts;
}

// -----------------------------------------------------------------------------
// IPv4 representation
// -----------------------------------------------------------------------------

class IPv4Address {
private:
    IPv4Integer value_;

public:
    explicit IPv4Address(IPv4Integer value = 0)
        : value_(value) {}

    static IPv4Address parse(const std::string& text) {
        const auto parts = split(text, '.');

        if (parts.size() != 4) {
            throw std::invalid_argument(
                "IPv4 address must contain exactly four octets."
            );
        }

        IPv4Integer value = 0;

        for (const auto& part : parts) {
            if (part.empty()) {
                throw std::invalid_argument("Empty IPv4 octet.");
            }

            std::size_t position = 0;
            unsigned long number = std::stoul(part, &position);

            if (position != part.size() || number > 255) {
                throw std::invalid_argument(
                    "IPv4 octet must be an integer from 0 through 255."
                );
            }

            value = (value << 8) | static_cast<IPv4Integer>(number);
        }

        return IPv4Address(value);
    }

    IPv4Integer value() const {
        return value_;
    }

    std::string toString() const {
        std::ostringstream output;

        output
            << ((value_ >> 24) & 0xff) << "."
            << ((value_ >> 16) & 0xff) << "."
            << ((value_ >> 8) & 0xff) << "."
            << (value_ & 0xff);

        return output.str();
    }

    std::string toBinary() const {
        std::string result;
        result.reserve(32);

        for (int bit = 31; bit >= 0; --bit) {
            result += ((value_ >> bit) & 1U) ? '1' : '0';

            if (bit == 24 || bit == 16 || bit == 8) {
                result += '.';
            }
        }

        return result;
    }

    bool operator<(const IPv4Address& other) const {
        return value_ < other.value_;
    }

    bool operator==(const IPv4Address& other) const {
        return value_ == other.value_;
    }
};

// -----------------------------------------------------------------------------
// IPv4 network
// -----------------------------------------------------------------------------

class IPv4Network {
private:
    IPv4Address networkAddress_;
    std::uint8_t prefixLength_;

public:
    IPv4Network(
        const IPv4Address& address,
        std::uint8_t prefixLength
    )
        : prefixLength_(prefixLength) {
        if (prefixLength > 32) {
            throw std::invalid_argument("IPv4 prefix must be between 0 and 32.");
        }

        IPv4Integer mask = 0;

        if (prefixLength != 0) {
            mask = 0xffffffffU << (32 - prefixLength);
        }

        networkAddress_ = IPv4Address(address.value() & mask);
    }

    static IPv4Network parse(const std::string& cidr) {
        const auto parts = split(cidr, '/');

        if (parts.size() != 2) {
            throw std::invalid_argument("CIDR must contain an address and prefix.");
        }

        IPv4Address address = IPv4Address::parse(parts[0]);

        std::size_t position = 0;
        unsigned long prefix = std::stoul(parts[1], &position);

        if (position != parts[1].size() || prefix > 32) {
            throw std::invalid_argument("Invalid IPv4 prefix.");
        }

        return IPv4Network(address, static_cast<std::uint8_t>(prefix));
    }

    std::uint8_t prefixLength() const {
        return prefixLength_;
    }

    IPv4Address networkAddress() const {
        return networkAddress_;
    }

    IPv4Integer mask() const {
        if (prefixLength_ == 0) {
            return 0;
        }

        return 0xffffffffU << (32 - prefixLength_);
    }

    IPv4Address broadcastAddress() const {
        const IPv4Integer hostMask = ~mask();
        return IPv4Address(networkAddress_.value() | hostMask);
    }

    std::uint64_t totalAddresses() const {
        return std::uint64_t{1} << (32 - prefixLength_);
    }

    std::uint64_t conventionalUsableHosts() const {
        if (prefixLength_ <= 30) {
            return totalAddresses() - 2;
        }

        if (prefixLength_ == 31) {
            return 2;
        }

        return 1;
    }

    bool contains(const IPv4Address& address) const {
        return (address.value() & mask()) == networkAddress_.value();
    }

    std::string toString() const {
        return networkAddress_.toString() +
               "/" +
               std::to_string(prefixLength_);
    }
};

// -----------------------------------------------------------------------------
// IPv4 classification
// -----------------------------------------------------------------------------

bool inRange(
    const IPv4Address& address,
    const IPv4Network& network
) {
    return network.contains(address);
}

std::vector<std::string> classifyIPv4(const IPv4Address& address) {
    std::vector<std::string> labels;

    const std::vector<std::pair<std::string, IPv4Network>> ranges = {
        {"private RFC 1918", IPv4Network::parse("10.0.0.0/8")},
        {"private RFC 1918", IPv4Network::parse("172.16.0.0/12")},
        {"private RFC 1918", IPv4Network::parse("192.168.0.0/16")},
        {"loopback", IPv4Network::parse("127.0.0.0/8")},
        {"link-local", IPv4Network::parse("169.254.0.0/16")},
        {"multicast", IPv4Network::parse("224.0.0.0/4")},
        {"shared address space", IPv4Network::parse("100.64.0.0/10")},
        {"documentation", IPv4Network::parse("192.0.2.0/24")},
        {"documentation", IPv4Network::parse("198.51.100.0/24")},
        {"documentation", IPv4Network::parse("203.0.113.0/24")}
    };

    for (const auto& [label, network] : ranges) {
        if (network.contains(address)) {
            labels.push_back(label);
        }
    }

    if (labels.empty()) {
        labels.push_back("ordinary IPv4 address");
    }

    return labels;
}

// -----------------------------------------------------------------------------
// Address allocation request
// -----------------------------------------------------------------------------

struct AllocationRequest {
    std::string name;
    std::uint32_t hostsRequired;
};

struct Allocation {
    std::string name;
    IPv4Network network;
    std::uint32_t hostsRequired;
};

// -----------------------------------------------------------------------------
// VLSM planning
// -----------------------------------------------------------------------------

std::uint8_t prefixForHosts(std::uint32_t hostsRequired) {
    if (hostsRequired == 0) {
        throw std::invalid_argument("Host requirement must be positive.");
    }

    for (int prefix = 30; prefix >= 0; --prefix) {
        std::uint64_t total =
            std::uint64_t{1} << (32 - prefix);

        std::uint64_t usable = total - 2;

        if (usable >= hostsRequired) {
            return static_cast<std::uint8_t>(prefix);
        }
    }

    throw std::runtime_error("Host requirement exceeds IPv4 capacity.");
}

std::vector<Allocation> allocateVLSM(
    const IPv4Network& baseNetwork,
    std::vector<AllocationRequest> requests
) {
    std::sort(
        requests.begin(),
        requests.end(),
        [](const AllocationRequest& a, const AllocationRequest& b) {
            return a.hostsRequired > b.hostsRequired;
        }
    );

    IPv4Integer cursor = baseNetwork.networkAddress().value();
    const IPv4Integer baseEnd = baseNetwork.broadcastAddress().value();

    std::vector<Allocation> result;

    for (const auto& request : requests) {
        const std::uint8_t prefix = prefixForHosts(request.hostsRequired);

        const IPv4Integer blockSize =
            static_cast<IPv4Integer>(
                std::uint64_t{1} << (32 - prefix)
            );

        const IPv4Integer remainder = cursor % blockSize;

        if (remainder != 0) {
            cursor += blockSize - remainder;
        }

        if (cursor > std::numeric_limits<IPv4Integer>::max() - blockSize + 1) {
            throw std::runtime_error("IPv4 address arithmetic overflow.");
        }

        const IPv4Integer broadcast =
            cursor + blockSize - 1;

        if (broadcast > baseEnd) {
            throw std::runtime_error(
                "Base network does not contain enough space."
            );
        }

        result.push_back({
            request.name,
            IPv4Network(
                IPv4Address(cursor),
                prefix
            ),
            request.hostsRequired
        });

        cursor = broadcast + 1;
    }

    return result;
}

// -----------------------------------------------------------------------------
// DHCP-style lease management
// -----------------------------------------------------------------------------

struct DHCPLease {
    std::string clientId;
    IPv4Address address;
    std::uint64_t expirationTime;
};

class DHCPPool {
private:
    IPv4Network network_;
    std::vector<IPv4Address> availableAddresses_;
    std::map<std::string, DHCPLease> leases_;

public:
    DHCPPool(
        const IPv4Network& network,
        IPv4Address first,
        IPv4Address last
    )
        : network_(network) {
        if (!network_.contains(first) || !network_.contains(last)) {
            throw std::invalid_argument(
                "DHCP range must be inside the configured network."
            );
        }

        if (first.value() > last.value()) {
            throw std::invalid_argument(
                "DHCP first address must not exceed last address."
            );
        }

        for (
            IPv4Integer value = first.value();
            value <= last.value();
            ++value
        ) {
            availableAddresses_.emplace_back(value);

            if (value == std::numeric_limits<IPv4Integer>::max()) {
                break;
            }
        }
    }

    DHCPLease request(
        const std::string& clientId,
        std::uint64_t currentTime,
        std::uint64_t duration
    ) {
        auto existing = leases_.find(clientId);

        if (existing != leases_.end()) {
            existing->second.expirationTime =
                currentTime + duration;

            return existing->second;
        }

        std::set<IPv4Integer> used;

        for (const auto& [id, lease] : leases_) {
            used.insert(lease.address.value());
        }

        for (const auto& address : availableAddresses_) {
            if (!used.contains(address.value())) {
                DHCPLease lease{
                    clientId,
                    address,
                    currentTime + duration
                };

                leases_[clientId] = lease;
                return lease;
            }
        }

        throw std::runtime_error("DHCP pool exhausted.");
    }

    void release(const std::string& clientId) {
        leases_.erase(clientId);
    }

    void expire(std::uint64_t currentTime) {
        for (auto iterator = leases_.begin();
             iterator != leases_.end();) {

            if (iterator->second.expirationTime <= currentTime) {
                iterator = leases_.erase(iterator);
            } else {
                ++iterator;
            }
        }
    }

    std::size_t activeLeases() const {
        return leases_.size();
    }
};

// -----------------------------------------------------------------------------
// NAT/PAT
// -----------------------------------------------------------------------------

struct NATTranslation {
    IPv4Address privateAddress;
    std::uint16_t privatePort;

    IPv4Address publicAddress;
    std::uint16_t publicPort;

    IPv4Address destinationAddress;
    std::uint16_t destinationPort;
};

class NATTable {
private:
    IPv4Address publicAddress_;
    std::uint16_t nextPort_ = 40000;

    std::vector<NATTranslation> translations_;

public:
    explicit NATTable(const IPv4Address& publicAddress)
        : publicAddress_(publicAddress) {}

    NATTranslation createTranslation(
        const IPv4Address& privateAddress,
        std::uint16_t privatePort,
        const IPv4Address& destinationAddress,
        std::uint16_t destinationPort
    ) {
        const auto labels = classifyIPv4(privateAddress);

        bool isPrivate = std::find(
            labels.begin(),
            labels.end(),
            "private RFC 1918"
        ) != labels.end();

        if (!isPrivate) {
            throw std::invalid_argument(
                "This NAT example expects an RFC 1918 private source."
            );
        }

        if (privatePort == 0 || destinationPort == 0) {
            throw std::invalid_argument("TCP/UDP ports must be non-zero.");
        }

        if (nextPort_ == 65535) {
            throw std::runtime_error(
                "Simplified NAT translation port space exhausted."
            );
        }

        NATTranslation translation{
            privateAddress,
            privatePort,
            publicAddress_,
            nextPort_++,
            destinationAddress,
            destinationPort
        };

        translations_.push_back(translation);
        return translation;
    }

    std::size_t size() const {
        return translations_.size();
    }
};

// -----------------------------------------------------------------------------
// IPv6 representation
// -----------------------------------------------------------------------------

class IPv6Address {
private:
    std::array<std::uint16_t, 8> groups_{};

public:
    IPv6Address() = default;

    explicit IPv6Address(
        const std::array<std::uint16_t, 8>& groups
    )
        : groups_(groups) {}

    static IPv6Address parse(const std::string& text) {
        if (text.empty()) {
            throw std::invalid_argument("IPv6 address cannot be empty.");
        }

        const auto compressionPosition = text.find("::");

        if (
            compressionPosition != std::string::npos &&
            text.find("::", compressionPosition + 2) != std::string::npos
        ) {
            throw std::invalid_argument(
                "IPv6 compression may appear only once."
            );
        }

        std::vector<std::string> groups;

        if (compressionPosition != std::string::npos) {
            const std::string left =
                text.substr(0, compressionPosition);

            const std::string right =
                text.substr(compressionPosition + 2);

            std::vector<std::string> leftGroups =
                left.empty() ? std::vector<std::string>{}
                             : split(left, ':');

            std::vector<std::string> rightGroups =
                right.empty() ? std::vector<std::string>{}
                              : split(right, ':');

            if (
                leftGroups.size() + rightGroups.size() >= 8
            ) {
                throw std::invalid_argument(
                    "IPv6 :: must replace at least one group."
                );
            }

            groups = leftGroups;

            const std::size_t missing =
                8 - leftGroups.size() - rightGroups.size();

            for (std::size_t i = 0; i < missing; ++i) {
                groups.push_back("0");
            }

            groups.insert(
                groups.end(),
                rightGroups.begin(),
                rightGroups.end()
            );
        } else {
            groups = split(text, ':');

            if (groups.size() != 8) {
                throw std::invalid_argument(
                    "Uncompressed IPv6 requires eight groups."
                );
            }
        }

        if (groups.size() != 8) {
            throw std::invalid_argument(
                "IPv6 address must contain eight logical groups."
            );
        }

        std::array<std::uint16_t, 8> values{};

        for (std::size_t i = 0; i < 8; ++i) {
            const auto& group = groups[i];

            if (group.empty() || group.size() > 4) {
                throw std::invalid_argument(
                    "IPv6 group must contain 1 to 4 hexadecimal digits."
                );
            }

            unsigned long value = 0;

            for (char character : group) {
                value <<= 4;

                if (character >= '0' && character <= '9') {
                    value += character - '0';
                } else if (character >= 'a' && character <= 'f') {
                    value += character - 'a' + 10;
                } else if (character >= 'A' && character <= 'F') {
                    value += character - 'A' + 10;
                } else {
                    throw std::invalid_argument(
                        "Invalid hexadecimal character in IPv6 address."
                    );
                }
            }

            if (value > 0xffff) {
                throw std::invalid_argument(
                    "IPv6 group exceeds 16 bits."
                );
            }

            values[i] = static_cast<std::uint16_t>(value);
        }

        return IPv6Address(values);
    }

    const std::array<std::uint16_t, 8>& groups() const {
        return groups_;
    }

    bool isLoopback() const {
        for (std::size_t i = 0; i < 7; ++i) {
            if (groups_[i] != 0) {
                return false;
            }
        }

        return groups_[7] == 1;
    }

    bool isUnspecified() const {
        for (auto group : groups_) {
            if (group != 0) {
                return false;
            }
        }

        return true;
    }

    bool isLinkLocal() const {
        return (groups_[0] & 0xffc0) == 0xfe80;
    }

    bool isMulticast() const {
        return (groups_[0] & 0xff00) == 0xff00;
    }

    bool isUniqueLocal() const {
        return (groups_[0] & 0xfe00) == 0xfc00;
    }

    std::string toString() const {
        std::size_t bestStart = 8;
        std::size_t bestLength = 0;

        std::size_t currentStart = 8;
        std::size_t currentLength = 0;

        for (std::size_t i = 0; i <= 8; ++i) {
            const bool zero =
                i < 8 && groups_[i] == 0;

            if (zero) {
                if (currentStart == 8) {
                    currentStart = i;
                    currentLength = 1;
                } else {
                    ++currentLength;
                }
            } else {
                if (
                    currentLength >= 2 &&
                    currentLength > bestLength
                ) {
                    bestStart = currentStart;
                    bestLength = currentLength;
                }

                currentStart = 8;
                currentLength = 0;
            }
        }

        std::ostringstream output;

        for (std::size_t i = 0; i < 8;) {
            if (i == bestStart) {
                if (i == 0) {
                    output << "::";
                } else {
                    output << ':';
                    output << ':';
                }

                i += bestLength;

                if (i == 8) {
                    break;
                }

                continue;
            }

            if (i != 0 && i != bestStart + bestLength) {
                output << ':';
            }

            output << std::hex
                   << std::nouppercase
                   << groups_[i]
                   << std::dec;

            ++i;
        }

        return output.str();
    }
};

// -----------------------------------------------------------------------------
// IPv6 subnet planning
// -----------------------------------------------------------------------------

std::uint64_t ipv6SubnetCount(
    std::uint8_t parentPrefix,
    std::uint8_t childPrefix
) {
    if (
        parentPrefix > 128 ||
        childPrefix > 128 ||
        childPrefix < parentPrefix
    ) {
        throw std::invalid_argument("Invalid IPv6 prefix relationship.");
    }

    const unsigned difference =
        childPrefix - parentPrefix;

    if (difference >= 64) {
        return std::numeric_limits<std::uint64_t>::max();
    }

    return std::uint64_t{1} << difference;
}

// -----------------------------------------------------------------------------
// Case-study reporting
// -----------------------------------------------------------------------------

void printAllocation(const Allocation& allocation) {
    const auto& network = allocation.network;

    std::cout
        << std::left
        << std::setw(26)
        << allocation.name
        << std::setw(20)
        << network.toString()
        << "requested="
        << std::setw(4)
        << allocation.hostsRequired
        << "usable="
        << network.conventionalUsableHosts()
        << "\n";
}

// -----------------------------------------------------------------------------
// Case study
// -----------------------------------------------------------------------------

void runEnterpriseCaseStudy() {
    printTitle("1. ENTERPRISE NETWORK ADDRESSING CASE STUDY");

    /*
     * The organization receives 10.40.0.0/22.
     *
     * A /22 contains:
     *
     *     2^(32 - 22) = 1024 addresses
     *
     * Because this is RFC 1918 private space, it is appropriate for internal
     * network design. It is not itself a public Internet destination prefix.
     */
    const IPv4Network baseNetwork =
        IPv4Network::parse("10.40.0.0/22");

    std::cout << "Base allocation: "
              << baseNetwork.toString()
              << "\n";

    std::cout << "Network address: "
              << baseNetwork.networkAddress().toString()
              << "\n";

    std::cout << "Broadcast address: "
              << baseNetwork.broadcastAddress().toString()
              << "\n";

    std::cout << "Total addresses: "
              << baseNetwork.totalAddresses()
              << "\n";

    std::cout << "Conventional usable hosts: "
              << baseNetwork.conventionalUsableHosts()
              << "\n";

    const std::vector<AllocationRequest> departments = {
        {"Engineering", 180},
        {"Production", 90},
        {"Finance", 35},
        {"Security", 18},
        {"Infrastructure", 6}
    };

    std::cout << "\nVLSM allocation:\n";

    const auto allocations =
        allocateVLSM(baseNetwork, departments);

    for (const auto& allocation : allocations) {
        printAllocation(allocation);
    }

    /*
     * Verify that each allocated subnet is inside the base network and that
     * the allocation process produced non-overlapping ranges.
     */
    std::cout << "\nAllocation validation:\n";

    for (std::size_t i = 0; i < allocations.size(); ++i) {
        const auto& current = allocations[i];

        if (
            !baseNetwork.contains(current.network.networkAddress()) ||
            !baseNetwork.contains(current.network.broadcastAddress())
        ) {
            throw std::runtime_error(
                "Allocation escaped the base network."
            );
        }

        if (i > 0) {
            const auto& previous = allocations[i - 1];

            if (
                previous.network.broadcastAddress().value() >=
                current.network.networkAddress().value()
            ) {
                throw std::runtime_error(
                    "VLSM allocations overlap."
                );
            }
        }

        std::cout
            << "  "
            << current.name
            << ": valid, contained, non-overlapping\n";
    }
}

// -----------------------------------------------------------------------------
// Address classification case study
// -----------------------------------------------------------------------------

void runClassificationCaseStudy() {
    printTitle("2. ADDRESS CLASSIFICATION");

    const std::vector<std::string> addresses = {
        "10.40.0.1",
        "172.16.10.20",
        "192.168.50.10",
        "8.8.8.8",
        "127.0.0.1",
        "169.254.20.10",
        "224.0.0.1",
        "100.64.10.5",
        "203.0.113.10"
    };

    for (const auto& text : addresses) {
        const auto address = IPv4Address::parse(text);
        const auto labels = classifyIPv4(address);

        std::cout
            << std::left
            << std::setw(17)
            << address.toString()
            << " -> ";

        for (std::size_t i = 0; i < labels.size(); ++i) {
            if (i != 0) {
                std::cout << ", ";
            }

            std::cout << labels[i];
        }

        std::cout << "\n";
    }
}

// -----------------------------------------------------------------------------
// DHCP case study
// -----------------------------------------------------------------------------

void runDHCPCaseStudy() {
    printTitle("3. DHCP ADDRESS MANAGEMENT");

    const IPv4Network network =
        IPv4Network::parse("10.40.3.0/24");

    DHCPPool pool(
        network,
        IPv4Address::parse("10.40.3.50"),
        IPv4Address::parse("10.40.3.54")
    );

    const std::vector<std::string> clients = {
        "engineering-laptop-01",
        "engineering-laptop-02",
        "printer-01"
    };

    for (const auto& client : clients) {
        const auto lease =
            pool.request(client, 1000, 3600);

        std::cout
            << std::left
            << std::setw(28)
            << client
            << " -> "
            << lease.address.toString()
            << " expires="
            << lease.expirationTime
            << "\n";
    }

    pool.release("engineering-laptop-02");

    const auto replacement =
        pool.request("phone-01", 1100, 3600);

    std::cout
        << std::left
        << std::setw(28)
        << "phone-01"
        << " -> "
        << replacement.address.toString()
        << "\n";

    std::cout
        << "Active leases: "
        << pool.activeLeases()
        << "\n";

    pool.expire(5000);

    std::cout
        << "Active leases after expiration: "
        << pool.activeLeases()
        << "\n";
}

// -----------------------------------------------------------------------------
// NAT case study
// -----------------------------------------------------------------------------

void runNATCaseStudy() {
    printTitle("4. NAT/PAT BORDER CASE STUDY");

    const IPv4Address publicAddress =
        IPv4Address::parse("203.0.113.10");

    NATTable nat(publicAddress);

    struct Connection {
        std::string name;
        std::string privateIp;
        std::uint16_t privatePort;
        std::string destinationIp;
        std::uint16_t destinationPort;
    };

    const std::vector<Connection> connections = {
        {
            "Laptop A",
            "10.40.0.10",
            51515,
            "198.51.100.40",
            443
        },
        {
            "Laptop B",
            "10.40.0.11",
            51516,
            "198.51.100.40",
            443
        },
        {
            "Server Admin",
            "10.40.1.20",
            53000,
            "198.51.100.50",
            22
        }
    };

    for (const auto& connection : connections) {
        const auto translation =
            nat.createTranslation(
                IPv4Address::parse(connection.privateIp),
                connection.privatePort,
                IPv4Address::parse(connection.destinationIp),
                connection.destinationPort
            );

        std::cout
            << std::left
            << std::setw(15)
            << connection.name
            << " "
            << translation.privateAddress.toString()
            << ":"
            << translation.privatePort
            << " -> "
            << translation.publicAddress.toString()
            << ":"
            << translation.publicPort
            << "\n";
    }

    std::cout
        << "NAT translations: "
        << nat.size()
        << "\n";
}

// -----------------------------------------------------------------------------
// IPv6 case study
// -----------------------------------------------------------------------------

void runIPv6CaseStudy() {
    printTitle("5. IPV6 ADDRESSING CASE STUDY");

    const std::vector<std::string> examples = {
        "2001:db8:abcd::1",
        "::1",
        "::",
        "fe80::10",
        "fd12:3456:789a::20",
        "ff02::1"
    };

    for (const auto& text : examples) {
        const auto address =
            IPv6Address::parse(text);

        std::cout
            << std::left
            << std::setw(30)
            << text
            << " -> "
            << std::setw(25)
            << address.toString();

        if (address.isLoopback()) {
            std::cout << " loopback";
        }

        if (address.isUnspecified()) {
            std::cout << " unspecified";
        }

        if (address.isLinkLocal()) {
            std::cout << " link-local";
        }

        if (address.isUniqueLocal()) {
            std::cout << " unique-local";
        }

        if (address.isMulticast()) {
            std::cout << " multicast";
        }

        std::cout << "\n";
    }

    const std::uint64_t numberOfSubnets =
        ipv6SubnetCount(48, 64);

    std::cout
        << "\nIPv6 /48 to /64 subnet count: "
        << numberOfSubnets
        << "\n";

    std::cout
        << "This equals 2^(64-48) = 65,536 /64 networks.\n";
}

// -----------------------------------------------------------------------------
// Route summarization
// -----------------------------------------------------------------------------

IPv4Network summarizeAddresses(
    const std::vector<IPv4Address>& addresses
) {
    if (addresses.empty()) {
        throw std::invalid_argument(
            "At least one address is required."
        );
    }

    IPv4Integer minimum = addresses.front().value();
    IPv4Integer maximum = addresses.front().value();

    for (const auto& address : addresses) {
        minimum = std::min(minimum, address.value());
        maximum = std::max(maximum, address.value());
    }

    IPv4Integer difference = minimum ^ maximum;

    std::uint8_t prefix = 32;

    if (difference != 0) {
        std::uint8_t differingBits = 0;

        while (difference != 0) {
            ++differingBits;
            difference >>= 1;
        }

        prefix = static_cast<std::uint8_t>(32 - differingBits);
    }

    return IPv4Network(
        IPv4Address(minimum),
        prefix
    );
}

void runSummarizationCaseStudy() {
    printTitle("6. ROUTE SUMMARIZATION");

    const std::vector<IPv4Network> networks = {
        IPv4Network::parse("10.40.8.0/24"),
        IPv4Network::parse("10.40.9.0/24"),
        IPv4Network::parse("10.40.10.0/24"),
        IPv4Network::parse("10.40.11.0/24")
    };

    std::vector<IPv4Address> networkAddresses;

    for (const auto& network : networks) {
        std::cout << "  " << network.toString() << "\n";
        networkAddresses.push_back(network.networkAddress());
    }

    const auto summary =
        summarizeAddresses(networkAddresses);

    std::cout
        << "Covering summary: "
        << summary.toString()
        << "\n";

    std::cout
        << "\nA summary reduces routing-table entries when the address ranges"
        << "\nare contiguous and policy permits aggregation.\n";
}

// -----------------------------------------------------------------------------
// Edge cases and failure conditions
// -----------------------------------------------------------------------------

void runEdgeCases() {
    printTitle("7. EDGE CASES AND FAILURE CONDITIONS");

    const std::vector<std::string> invalidIPv4 = {
        "192.168.1.999",
        "192.168.1",
        "192.168.1.a",
        "10.0.0.256"
    };

    for (const auto& text : invalidIPv4) {
        try {
            auto address = IPv4Address::parse(text);
            std::cout
                << "Unexpectedly accepted: "
                << address.toString()
                << "\n";
        } catch (const std::exception& error) {
            std::cout
                << "Rejected IPv4 "
                << text
                << ": "
                << error.what()
                << "\n";
        }
    }

    const std::vector<std::string> invalidIPv6 = {
        "2001:db8:::1",
        "2001:db8:1:2:3:4:5",
        "2001:db8:1:2:3:4:5:6:7",
        "2001:db8:zzzz::1"
    };

    for (const auto& text : invalidIPv6) {
        try {
            auto address = IPv6Address::parse(text);
            std::cout
                << "Unexpectedly accepted: "
                << address.toString()
                << "\n";
        } catch (const std::exception& error) {
            std::cout
                << "Rejected IPv6 "
                << text
                << ": "
                << error.what()
                << "\n";
        }
    }

    try {
        const auto network =
            IPv4Network::parse("192.168.1.0/26");

        const auto address =
            IPv4Address::parse("192.168.2.10");

        std::cout
            << "\nMembership test: "
            << address.toString()
            << " is "
            << (network.contains(address) ? "inside" : "outside")
            << " "
            << network.toString()
            << "\n";
    } catch (const std::exception& error) {
        std::cout << "Unexpected error: "
                  << error.what()
                  << "\n";
    }
}

// -----------------------------------------------------------------------------
// Security and design considerations
// -----------------------------------------------------------------------------

void printSecurityConsiderations() {
    printTitle("8. SECURITY AND PRODUCTION DESIGN");

    const std::vector<std::string> points = {
        "Private addressing is not an authentication mechanism.",
        "NAT does not replace firewall policy.",
        "IPv4 and IPv6 must both be considered in security controls.",
        "Network segmentation should reflect trust boundaries and application needs.",
        "Address validation is necessary before using addresses in policy decisions.",
        "Dynamic addresses require suitable logging and asset-management practices.",
        "Documentation ranges should be used in examples rather than real public hosts.",
        "Routing summaries must not accidentally include unauthorized address space.",
        "Infrastructure addressing should allow for growth and operational requirements.",
        "Monitoring should detect unexpected assignments, routes, and source addresses."
    };

    for (std::size_t index = 0; index < points.size(); ++index) {
        std::cout
            << std::setw(2)
            << index + 1
            << ". "
            << points[index]
            << "\n";
    }
}

// -----------------------------------------------------------------------------
// Complexity discussion
// -----------------------------------------------------------------------------

void printComplexityDiscussion() {
    printTitle("9. ALGORITHMIC AND PERFORMANCE CONSIDERATIONS");

    std::cout
        << "IPv4 membership: O(1)\n"
        << "IPv4 bit-mask calculation: O(1)\n"
        << "Prefix capacity calculation: O(1)\n"
        << "VLSM request sorting: O(n log n)\n"
        << "VLSM sequential allocation after sorting: O(n)\n"
        << "DHCP lease lookup in this implementation: O(log n)\n"
        << "DHCP free-address scan: O(m), where m is pool size\n"
        << "Route summarization: O(n)\n"
        << "IPv6 parsing: O(1) for the fixed eight-group representation\n";

    std::cout
        << "\nThe case study favors clear standard-library data structures over"
        << "\nnetwork-server complexity. A production address-management system"
        << "\nwould also require persistence, concurrency control, auditing,"
        << "\nlease synchronization, failure recovery, and protocol compliance.\n";
}

// -----------------------------------------------------------------------------
// Self-tests
// -----------------------------------------------------------------------------

void runSelfTests() {
    printTitle("10. SELF-TESTS");

    {
        const auto address =
            IPv4Address::parse("192.168.10.25");

        if (address.toString() != "192.168.10.25") {
            throw std::runtime_error("IPv4 round-trip test failed.");
        }

        if (
            address.toBinary() !=
            "11000000.10101000.00001010.00011001"
        ) {
            throw std::runtime_error("IPv4 binary test failed.");
        }
    }

    {
        const auto network =
            IPv4Network::parse("192.168.1.0/24");

        if (
            network.broadcastAddress().toString() !=
            "192.168.1.255"
        ) {
            throw std::runtime_error(
                "IPv4 broadcast test failed."
            );
        }

        if (
            !network.contains(
                IPv4Address::parse("192.168.1.100")
            )
        ) {
            throw std::runtime_error(
                "IPv4 membership test failed."
            );
        }

        if (
            network.contains(
                IPv4Address::parse("192.168.2.100")
            )
        ) {
            throw std::runtime_error(
                "IPv4 non-membership test failed."
            );
        }
    }

    {
        const auto loopback =
            IPv6Address::parse("::1");

        if (!loopback.isLoopback()) {
            throw std::runtime_error(
                "IPv6 loopback test failed."
            );
        }

        const auto linkLocal =
            IPv6Address::parse("fe80::1");

        if (!linkLocal.isLinkLocal()) {
            throw std::runtime_error(
                "IPv6 link-local test failed."
            );
        }

        const auto multicast =
            IPv6Address::parse("ff02::1");

        if (!multicast.isMulticast()) {
            throw std::runtime_error(
                "IPv6 multicast test failed."
            );
        }
    }

    {
        const auto network =
            IPv4Network::parse("10.0.0.0/24");

        const auto requests = std::vector<AllocationRequest>{
            {"A", 100},
            {"B", 50},
            {"C", 20}
        };

        const auto allocations =
            allocateVLSM(network, requests);

        if (allocations.size() != 3) {
            throw std::runtime_error(
                "VLSM allocation count test failed."
            );
        }
    }

    std::cout << "All C++ self-tests passed.\n";
}

// -----------------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------------

int main() {
    try {
        printTitle("IP ADDRESSING INDUSTRY-STYLE CASE STUDY");

        std::cout
            << "Scenario: internal enterprise IPv4 allocation combined with"
            << "\nDHCP-style management, NAT/PAT, IPv6 planning, and routing.\n";

        runEnterpriseCaseStudy();
        runClassificationCaseStudy();
        runDHCPCaseStudy();
        runNATCaseStudy();
        runIPv6CaseStudy();
        runSummarizationCaseStudy();
        runEdgeCases();
        printSecurityConsiderations();
        printComplexityDiscussion();
        runSelfTests();

        printTitle("END OF CASE STUDY");

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
