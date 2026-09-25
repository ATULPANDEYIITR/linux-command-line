/*
 * IPv4 Subnetting and CIDR
 *
 * C++17 industry-style case study:
 * Enterprise Network Address Planning and Routing Validation System
 *
 * The program models a network planning tool that:
 *   1. Represents IPv4 addresses as 32-bit unsigned integers.
 *   2. Converts between dotted-decimal and integer notation.
 *   3. Calculates CIDR network boundaries.
 *   4. Allocates VLSM subnets based on department requirements.
 *   5. Detects overlapping networks.
 *   6. Performs longest-prefix-match routing.
 *   7. Generates route summaries.
 *   8. Validates important edge cases.
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic subnetting.cpp -o subnetting
 *
 * Run:
 *   ./subnetting
 */

#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

class IPv4Address {
private:
    std::uint32_t value_;

public:
    IPv4Address() : value_(0) {}

    explicit IPv4Address(std::uint32_t value) : value_(value) {}

    explicit IPv4Address(const std::string& text) {
        value_ = parse(text);
    }

    static std::uint32_t parse(const std::string& text) {
        std::stringstream stream(text);
        std::string part;
        std::vector<unsigned int> octets;

        while (std::getline(stream, part, '.')) {
            if (part.empty()) {
                throw std::invalid_argument("Empty IPv4 octet.");
            }

            std::size_t processed = 0;
            unsigned long value;

            try {
                value = std::stoul(part, &processed);
            } catch (...) {
                throw std::invalid_argument("Invalid IPv4 octet: " + part);
            }

            if (processed != part.size() || value > 255) {
                throw std::invalid_argument("IPv4 octet out of range: " + part);
            }

            octets.push_back(static_cast<unsigned int>(value));
        }

        if (octets.size() != 4) {
            throw std::invalid_argument("IPv4 address must contain four octets.");
        }

        return (static_cast<std::uint32_t>(octets[0]) << 24U) |
               (static_cast<std::uint32_t>(octets[1]) << 16U) |
               (static_cast<std::uint32_t>(octets[2]) << 8U) |
               static_cast<std::uint32_t>(octets[3]);
    }

    std::uint32_t value() const {
        return value_;
    }

    std::string toString() const {
        std::ostringstream output;

        output
            << ((value_ >> 24U) & 0xFFU) << "."
            << ((value_ >> 16U) & 0xFFU) << "."
            << ((value_ >> 8U) & 0xFFU) << "."
            << (value_ & 0xFFU);

        return output.str();
    }

    std::string toBinary() const {
        std::string result;

        for (int octet = 3; octet >= 0; --octet) {
            std::uint32_t value = (value_ >> (octet * 8)) & 0xFFU;

            for (int bit = 7; bit >= 0; --bit) {
                result += ((value >> bit) & 1U) ? '1' : '0';
            }

            if (octet != 0) {
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
// CIDR NETWORK
// -----------------------------------------------------------------------------

class IPv4Network {
private:
    IPv4Address network_;
    std::uint8_t prefix_;

public:
    IPv4Network(const IPv4Address& address, std::uint8_t prefix)
        : prefix_(prefix) {

        if (prefix > 32) {
            throw std::invalid_argument("CIDR prefix must be between 0 and 32.");
        }

        const std::uint32_t mask = subnetMask(prefix);
        network_ = IPv4Address(address.value() & mask);
    }

    IPv4Network(const std::string& cidr) {
        const std::size_t slash = cidr.find('/');

        if (slash == std::string::npos) {
            throw std::invalid_argument("CIDR must contain '/'.");
        }

        const std::string addressText = cidr.substr(0, slash);
        const std::string prefixText = cidr.substr(slash + 1);

        if (prefixText.empty()) {
            throw std::invalid_argument("CIDR prefix is missing.");
        }

        std::size_t processed = 0;
        unsigned long parsedPrefix;

        try {
            parsedPrefix = std::stoul(prefixText, &processed);
        } catch (...) {
            throw std::invalid_argument("Invalid CIDR prefix.");
        }

        if (processed != prefixText.size() || parsedPrefix > 32) {
            throw std::invalid_argument("CIDR prefix must be between 0 and 32.");
        }

        prefix_ = static_cast<std::uint8_t>(parsedPrefix);

        const IPv4Address address(addressText);
        network_ = IPv4Address(address.value() & subnetMask(prefix_));
    }

    static std::uint32_t subnetMask(std::uint8_t prefix) {
        if (prefix == 0) {
            return 0U;
        }

        if (prefix == 32) {
            return 0xFFFFFFFFU;
        }

        return 0xFFFFFFFFU << (32U - prefix);
    }

    static std::uint32_t wildcardMask(std::uint8_t prefix) {
        return ~subnetMask(prefix);
    }

    std::uint8_t prefix() const {
        return prefix_;
    }

    IPv4Address networkAddress() const {
        return network_;
    }

    IPv4Address broadcastAddress() const {
        return IPv4Address(
            network_.value() | wildcardMask(prefix_)
        );
    }

    std::uint64_t totalAddresses() const {
        return 1ULL << (32U - prefix_);
    }

    std::uint64_t traditionalUsableHosts() const {
        if (prefix_ >= 31) {
            return 0;
        }

        return totalAddresses() - 2;
    }

    std::uint64_t operationalUsableHosts() const {
        if (prefix_ == 31) {
            return 2;
        }

        if (prefix_ == 32) {
            return 1;
        }

        return traditionalUsableHosts();
    }

    bool contains(const IPv4Address& address) const {
        const std::uint32_t mask = subnetMask(prefix_);

        return (address.value() & mask) == network_.value();
    }

    bool overlaps(const IPv4Network& other) const {
        return network_.value() <= other.broadcastAddress().value() &&
               other.network_.value() <= broadcastAddress().value();
    }

    std::string toString() const {
        return networkAddress().toString() + "/" +
               std::to_string(prefix_);
    }

    IPv4Network child(std::uint64_t index, std::uint8_t childPrefix) const {
        if (childPrefix < prefix_) {
            throw std::invalid_argument(
                "Child prefix cannot be shorter than parent prefix."
            );
        }

        if (childPrefix > 32) {
            throw std::invalid_argument(
                "Child prefix cannot exceed 32."
            );
        }

        const std::uint64_t childSize = 1ULL << (32U - childPrefix);
        const std::uint64_t childCount = 1ULL << (childPrefix - prefix_);

        if (index >= childCount) {
            throw std::out_of_range("Child subnet index exceeds parent.");
        }

        const std::uint64_t value =
            static_cast<std::uint64_t>(network_.value()) +
            index * childSize;

        if (value > std::numeric_limits<std::uint32_t>::max()) {
            throw std::overflow_error("Subnet address overflow.");
        }

        return IPv4Network(
            IPv4Address(static_cast<std::uint32_t>(value)),
            childPrefix
        );
    }
};


// -----------------------------------------------------------------------------
// SUBNET REQUIREMENTS
// -----------------------------------------------------------------------------

struct DepartmentRequirement {
    std::string name;
    std::string purpose;
    std::uint64_t hostsRequired;
};

struct Allocation {
    std::string name;
    std::string purpose;
    std::uint64_t hostsRequired;
    IPv4Network network;
};


// -----------------------------------------------------------------------------
// PREFIX SELECTION
// -----------------------------------------------------------------------------

std::uint8_t minimumPrefixForHosts(std::uint64_t requiredHosts) {
    if (requiredHosts == 0) {
        throw std::invalid_argument(
            "Host requirement must be greater than zero."
        );
    }

    for (int prefix = 30; prefix >= 0; --prefix) {
        IPv4Network candidate(
            IPv4Address(0),
            static_cast<std::uint8_t>(prefix)
        );

        if (candidate.traditionalUsableHosts() >= requiredHosts) {
            return static_cast<std::uint8_t>(prefix);
        }
    }

    throw std::runtime_error(
        "No conventional IPv4 subnet can satisfy the requirement."
    );
}


// -----------------------------------------------------------------------------
// VLSM ALLOCATOR
// -----------------------------------------------------------------------------

class VLSMAllocator {
private:
    IPv4Network parent_;

public:
    explicit VLSMAllocator(const IPv4Network& parent)
        : parent_(parent) {}

    std::vector<Allocation> allocate(
        std::vector<DepartmentRequirement> requirements
    ) const {
        // Larger requirements are allocated first. This reduces fragmentation
        // because large blocks have stricter alignment requirements.
        std::sort(
            requirements.begin(),
            requirements.end(),
            [](const DepartmentRequirement& first,
               const DepartmentRequirement& second) {
                return first.hostsRequired > second.hostsRequired;
            }
        );

        std::vector<Allocation> allocations;

        std::uint64_t current =
            static_cast<std::uint64_t>(parent_.networkAddress().value());

        const std::uint64_t parentEnd =
            static_cast<std::uint64_t>(parent_.broadcastAddress().value());

        for (const auto& requirement : requirements) {
            const std::uint8_t prefix =
                minimumPrefixForHosts(requirement.hostsRequired);

            const std::uint64_t blockSize =
                1ULL << (32U - prefix);

            // A subnet must begin on a boundary corresponding to its size.
            const std::uint64_t remainder = current % blockSize;

            if (remainder != 0) {
                current += blockSize - remainder;
            }

            if (current > parentEnd ||
                blockSize - 1 > parentEnd - current) {
                throw std::runtime_error(
                    "Address space exhausted while allocating " +
                    requirement.name
                );
            }

            IPv4Network network(
                IPv4Address(static_cast<std::uint32_t>(current)),
                prefix
            );

            if (!parent_.contains(network.networkAddress()) ||
                network.broadcastAddress().value() > parentEnd) {
                throw std::runtime_error(
                    "Allocated subnet is outside the parent network."
                );
            }

            allocations.push_back({
                requirement.name,
                requirement.purpose,
                requirement.hostsRequired,
                network
            });

            current += blockSize;
        }

        return allocations;
    }
};


// -----------------------------------------------------------------------------
// ROUTING
// -----------------------------------------------------------------------------

class RoutingTable {
private:
    std::vector<IPv4Network> routes_;

public:
    void addRoute(const IPv4Network& network) {
        routes_.push_back(network);
    }

    const IPv4Network* longestPrefixMatch(
        const IPv4Address& destination
    ) const {
        const IPv4Network* best = nullptr;

        for (const auto& route : routes_) {
            if (!route.contains(destination)) {
                continue;
            }

            if (best == nullptr ||
                route.prefix() > best->prefix()) {
                best = &route;
            }
        }

        return best;
    }

    void print() const {
        for (const auto& route : routes_) {
            std::cout << "  " << route.toString() << "\n";
        }
    }
};


// -----------------------------------------------------------------------------
// ROUTE SUMMARIZATION
// -----------------------------------------------------------------------------

unsigned commonPrefixLength(
    std::uint32_t first,
    std::uint32_t second
) {
    std::uint32_t difference = first ^ second;

    if (difference == 0) {
        return 32;
    }

    unsigned count = 0;

    while (difference != 0) {
        difference >>= 1U;
        ++count;
    }

    return 32U - count;
}

std::vector<IPv4Network> summarizeRange(
    const IPv4Address& firstAddress,
    const IPv4Address& lastAddress
) {
    std::uint64_t start = firstAddress.value();
    const std::uint64_t end = lastAddress.value();

    if (start > end) {
        throw std::invalid_argument(
            "First address must not exceed last address."
        );
    }

    std::vector<IPv4Network> result;

    while (start <= end) {
        std::uint8_t selectedPrefix = 32;

        for (int prefix = 0; prefix <= 32; ++prefix) {
            const std::uint64_t blockSize =
                1ULL << (32U - prefix);

            const bool aligned = (start % blockSize) == 0;
            const std::uint64_t blockEnd = start + blockSize - 1;

            if (aligned && blockEnd <= end) {
                selectedPrefix = static_cast<std::uint8_t>(prefix);
                break;
            }
        }

        result.emplace_back(
            IPv4Address(static_cast<std::uint32_t>(start)),
            selectedPrefix
        );

        start += 1ULL << (32U - selectedPrefix);
    }

    return result;
}


// -----------------------------------------------------------------------------
// REPORTING
// -----------------------------------------------------------------------------

void printSubnetDetails(const IPv4Network& network) {
    std::cout << "\nCIDR:             " << network.toString();
    std::cout << "\nNetwork address:  "
              << network.networkAddress().toString();
    std::cout << "\nBroadcast:        "
              << network.broadcastAddress().toString();
    std::cout << "\nSubnet mask:      "
              << IPv4Address(
                     IPv4Network::subnetMask(network.prefix())
                 ).toString();
    std::cout << "\nWildcard mask:    "
              << IPv4Address(
                     IPv4Network::wildcardMask(network.prefix())
                 ).toString();
    std::cout << "\nTotal addresses:  "
              << network.totalAddresses();
    std::cout << "\nTraditional hosts:"
              << network.traditionalUsableHosts();
    std::cout << "\nOperational hosts:"
              << network.operationalUsableHosts();
    std::cout << "\nBinary network:   "
              << network.networkAddress().toBinary()
              << "\n";
}


// -----------------------------------------------------------------------------
// CASE STUDY
// -----------------------------------------------------------------------------

void runEnterpriseCaseStudy() {
    std::cout << "\n";
    std::cout << std::string(78, '=') << "\n";
    std::cout << "ENTERPRISE IPv4 NETWORK PLANNING CASE STUDY\n";
    std::cout << std::string(78, '=') << "\n";

    /*
     * Scenario:
     *
     * An organization receives 10.20.0.0/20 and needs separate networks
     * for engineering, finance, HR, operations, security, and infrastructure.
     *
     * VLSM is used because each group has a different host requirement.
     */
    IPv4Network parent("10.20.0.0/20");

    std::cout << "\nParent allocation:\n";
    printSubnetDetails(parent);

    std::vector<DepartmentRequirement> requirements = {
        {"Engineering", "Application development", 400},
        {"Operations", "Operations systems", 180},
        {"Finance", "Financial systems", 80},
        {"HR", "Human resources", 40},
        {"Security", "Security infrastructure", 20},
        {"Network", "Network management", 6}
    };

    VLSMAllocator allocator(parent);
    std::vector<Allocation> allocations =
        allocator.allocate(requirements);

    std::cout << "\nVLSM allocation:\n";
    std::cout
        << std::left
        << std::setw(16) << "Department"
        << std::setw(27) << "Purpose"
        << std::setw(20) << "CIDR"
        << std::setw(12) << "Required"
        << "Usable\n";

    std::cout << std::string(90, '-') << "\n";

    for (const auto& allocation : allocations) {
        std::cout
            << std::left
            << std::setw(16) << allocation.name
            << std::setw(27) << allocation.purpose
            << std::setw(20) << allocation.network.toString()
            << std::setw(12) << allocation.hostsRequired
            << allocation.network.operationalUsableHosts()
            << "\n";
    }

    // -------------------------------------------------------------------------
    // Overlap validation
    // -------------------------------------------------------------------------

    std::cout << "\nAllocation overlap validation:\n";

    bool overlapFound = false;

    for (std::size_t i = 0; i < allocations.size(); ++i) {
        for (std::size_t j = i + 1; j < allocations.size(); ++j) {
            if (allocations[i].network.overlaps(
                    allocations[j].network)) {

                overlapFound = true;

                std::cout
                    << "  OVERLAP: "
                    << allocations[i].network.toString()
                    << " <-> "
                    << allocations[j].network.toString()
                    << "\n";
            }
        }
    }

    if (!overlapFound) {
        std::cout << "  No overlapping allocated networks.\n";
    }

    // -------------------------------------------------------------------------
    // Routing case study
    // -------------------------------------------------------------------------

    std::cout << "\nRouting table:\n";

    RoutingTable routingTable;

    routingTable.addRoute(IPv4Network("0.0.0.0/0"));
    routingTable.addRoute(IPv4Network("10.0.0.0/8"));
    routingTable.addRoute(IPv4Network("10.20.0.0/20"));

    for (const auto& allocation : allocations) {
        routingTable.addRoute(allocation.network);
    }

    routingTable.print();

    std::vector<std::string> destinations = {
        "10.20.0.10",
        "10.20.1.200",
        "10.20.5.10",
        "10.20.15.250",
        "10.50.1.1",
        "8.8.8.8"
    };

    std::cout << "\nLongest-prefix routing decisions:\n";

    for (const auto& destinationText : destinations) {
        IPv4Address destination(destinationText);

        const IPv4Network* selected =
            routingTable.longestPrefixMatch(destination);

        std::cout
            << "  "
            << destination.toString()
            << " -> ";

        if (selected == nullptr) {
            std::cout << "NO ROUTE";
        } else {
            std::cout << selected->toString();
        }

        std::cout << "\n";
    }
}


// -----------------------------------------------------------------------------
// EDUCATIONAL EXAMPLES
// -----------------------------------------------------------------------------

void demonstrateFundamentals() {
    std::cout << "\n";
    std::cout << std::string(78, '=') << "\n";
    std::cout << "FUNDAMENTAL SUBNET CALCULATIONS\n";
    std::cout << std::string(78, '=') << "\n";

    std::vector<std::string> examples = {
        "192.168.1.0/24",
        "192.168.1.64/26",
        "172.16.0.0/20",
        "10.0.0.0/8",
        "192.168.1.0/30",
        "192.168.1.0/31",
        "192.168.1.10/32"
    };

    for (const auto& example : examples) {
        printSubnetDetails(IPv4Network(example));
    }
}

void demonstrateEqualSubnetting() {
    std::cout << "\n";
    std::cout << std::string(78, '=') << "\n";
    std::cout << "EQUAL-SIZE SUBNETTING\n";
    std::cout << std::string(78, '=') << "\n";

    IPv4Network parent("192.168.10.0/24");

    std::uint8_t childPrefix = 26;

    const std::uint64_t childCount =
        1ULL << (childPrefix - parent.prefix());

    std::cout
        << parent.toString()
        << " split into /"
        << static_cast<unsigned>(childPrefix)
        << " creates "
        << childCount
        << " equal-size subnets.\n";

    for (std::uint64_t index = 0; index < childCount; ++index) {
        std::cout
            << "  "
            << parent.child(index, childPrefix).toString()
            << "\n";
    }
}

void demonstrateSummarization() {
    std::cout << "\n";
    std::cout << std::string(78, '=') << "\n";
    std::cout << "ROUTE SUMMARIZATION\n";
    std::cout << std::string(78, '=') << "\n";

    auto summaries = summarizeRange(
        IPv4Address("192.168.0.0"),
        IPv4Address("192.168.3.255")
    );

    std::cout << "Summary for 192.168.0.0-192.168.3.255:\n";

    for (const auto& summary : summaries) {
        std::cout << "  " << summary.toString() << "\n";
    }
}

void demonstrateInvalidInput() {
    std::cout << "\n";
    std::cout << std::string(78, '=') << "\n";
    std::cout << "VALIDATION AND FAILURE CONDITIONS\n";
    std::cout << std::string(78, '=') << "\n";

    std::vector<std::string> invalid = {
        "192.168.1.256/24",
        "192.168.1.0/33",
        "192.168.1/24",
        "abc.def.1.2/24",
        "192.168.1.0"
    };

    for (const auto& value : invalid) {
        try {
            IPv4Network network(value);
            std::cout
                << value
                << " -> accepted as "
                << network.toString()
                << "\n";
        } catch (const std::exception& error) {
            std::cout
                << value
                << " -> rejected: "
                << error.what()
                << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// MAIN
// -----------------------------------------------------------------------------

int main() {
    try {
        demonstrateFundamentals();
        demonstrateEqualSubnetting();
        demonstrateSummarization();
        demonstrateInvalidInput();
        runEnterpriseCaseStudy();

        std::cout << "\n";
        std::cout << std::string(78, '=') << "\n";
        std::cout << "IMPLEMENTATION CONSIDERATIONS\n";
        std::cout << std::string(78, '=') << "\n";

        std::cout
            << "1. IPv4 addresses are naturally represented as 32-bit values.\n"
            << "2. Network calculation uses bitwise AND with the subnet mask.\n"
            << "3. Broadcast calculation ORs the network with the wildcard mask.\n"
            << "4. VLSM allocates different prefix lengths to different needs.\n"
            << "5. Longest-prefix match selects the most specific matching route.\n"
            << "6. Overlap validation prevents conflicting address allocations.\n"
            << "7. /31 and /32 require special handling because traditional\n"
            << "   network/broadcast host rules do not apply in the same way.\n"
            << "8. Pairwise overlap checking is O(N^2) for N networks.\n"
            << "9. A production router uses optimized lookup structures rather\n"
            << "   than repeatedly scanning every route.\n"
            << "10. Subnetting provides address organization, not complete security.\n";

    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }

    return 0;
}
