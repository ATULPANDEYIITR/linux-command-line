/*
 * DNS: Domain Names, Resolution, Records, Recursive Resolvers, and Caching
 *
 * C++17 industry-style case study:
 * A miniature DNS infrastructure and recursive resolver for a simulated
 * enterprise domain.
 *
 * Build:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic dns_case_study.cpp -o dns_case_study
 *
 * The program is intentionally self-contained and uses only the C++ standard
 * library. It models DNS concepts without requiring a network connection.
 */

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

// ============================================================================
// 1. BASIC ENUMERATIONS
// ============================================================================

enum class RecordType {
    A,
    AAAA,
    CNAME,
    MX,
    NS,
    TXT,
    SOA,
    PTR
};

string toString(RecordType type) {
    switch (type) {
        case RecordType::A: return "A";
        case RecordType::AAAA: return "AAAA";
        case RecordType::CNAME: return "CNAME";
        case RecordType::MX: return "MX";
        case RecordType::NS: return "NS";
        case RecordType::TXT: return "TXT";
        case RecordType::SOA: return "SOA";
        case RecordType::PTR: return "PTR";
    }

    return "UNKNOWN";
}


// ============================================================================
// 2. UTILITY FUNCTIONS
// ============================================================================

string normalizeName(string name) {
    transform(
        name.begin(),
        name.end(),
        name.begin(),
        [](unsigned char character) {
            return static_cast<char>(tolower(character));
        }
    );

    while (!name.empty() && name.back() == '.') {
        name.pop_back();
    }

    if (name.empty()) {
        return ".";
    }

    return name + ".";
}

vector<string> splitDomainName(const string& name) {
    string normalized = normalizeName(name);

    if (normalized == ".") {
        return {};
    }

    normalized.pop_back();

    vector<string> labels;
    string label;

    stringstream stream(normalized);

    while (getline(stream, label, '.')) {
        labels.push_back(label);
    }

    return labels;
}

bool isSubdomainOrEqual(
    const string& name,
    const string& parent
) {
    const string child = normalizeName(name);
    const string ancestor = normalizeName(parent);

    if (child == ancestor) {
        return true;
    }

    if (child.size() <= ancestor.size()) {
        return false;
    }

    const string suffix =
        child.substr(
            child.size() - ancestor.size()
        );

    if (suffix != ancestor) {
        return false;
    }

    return child[child.size() - ancestor.size() - 1] == '.';
}

bool validDomainName(const string& name) {
    const string normalized = normalizeName(name);

    if (normalized == ".") {
        return false;
    }

    if (normalized.size() - 1 > 253) {
        return false;
    }

    const vector<string> labels =
        splitDomainName(normalized);

    for (const string& label : labels) {
        if (label.empty() || label.size() > 63) {
            return false;
        }

        if (
            label.front() == '-' ||
            label.back() == '-'
        ) {
            return false;
        }
    }

    return true;
}


// ============================================================================
// 3. DNS RECORD
// ============================================================================

struct DNSRecord {
    string name;
    RecordType type;
    string value;
    uint32_t ttl;
    optional<int> priority;

    DNSRecord(
        string recordName,
        RecordType recordType,
        string recordValue,
        uint32_t recordTTL = 300,
        optional<int> recordPriority = nullopt
    )
        : name(normalizeName(move(recordName))),
          type(recordType),
          value(move(recordValue)),
          ttl(recordTTL),
          priority(recordPriority) {}

    string toString() const {
        ostringstream output;

        output
            << name
            << " "
            << ttl
            << " IN "
            << ::toString(type)
            << " "
            << value;

        if (priority.has_value()) {
            output
                << " priority="
                << *priority;
        }

        return output.str();
    }
};

void validateRecord(const DNSRecord& record) {
    if (record.name.empty()) {
        throw invalid_argument(
            "DNS record name cannot be empty"
        );
    }

    if (record.type == RecordType::A) {
        int dots = 0;

        for (char character : record.value) {
            if (character == '.') {
                dots++;
            } else if (!isdigit(
                           static_cast<unsigned char>(character)
                       )) {
                throw invalid_argument(
                    "Invalid IPv4 address: " +
                    record.value
                );
            }
        }

        if (dots != 3) {
            throw invalid_argument(
                "Invalid IPv4 address: " +
                record.value
            );
        }

        stringstream stream(record.value);
        string part;

        while (getline(stream, part, '.')) {
            if (part.empty()) {
                throw invalid_argument(
                    "Invalid IPv4 address: " +
                    record.value
                );
            }

            int value = stoi(part);

            if (value < 0 || value > 255) {
                throw invalid_argument(
                    "Invalid IPv4 address: " +
                    record.value
                );
            }
        }
    }

    if (record.type == RecordType::MX) {
        if (
            !record.priority.has_value() ||
            *record.priority < 0
        ) {
            throw invalid_argument(
                "MX records require non-negative priority"
            );
        }
    }

    if (
        record.type == RecordType::CNAME ||
        record.type == RecordType::MX ||
        record.type == RecordType::NS ||
        record.type == RecordType::PTR
    ) {
        if (record.value.empty()) {
            throw invalid_argument(
                "Target value cannot be empty"
            );
        }
    }
}


// ============================================================================
// 4. DNS ZONE
// ============================================================================

class DNSZone {
private:
    string origin;

    map<
        pair<string, RecordType>,
        vector<DNSRecord>
    > records;

public:
    explicit DNSZone(string zoneOrigin)
        : origin(normalizeName(move(zoneOrigin))) {}

    const string& getOrigin() const {
        return origin;
    }

    void addRecord(const DNSRecord& record) {
        if (
            !isSubdomainOrEqual(
                record.name,
                origin
            )
        ) {
            throw invalid_argument(
                "Record lies outside zone " +
                origin
            );
        }

        validateRecord(record);

        records[
            {normalizeName(record.name), record.type}
        ].push_back(record);
    }

    vector<DNSRecord> query(
        const string& name,
        RecordType type
    ) const {
        const auto key =
            make_pair(
                normalizeName(name),
                type
            );

        auto iterator = records.find(key);

        if (iterator == records.end()) {
            return {};
        }

        return iterator->second;
    }

    bool hasName(const string& name) const {
        const string normalized =
            normalizeName(name);

        for (const auto& [key, values] : records) {
            if (key.first == normalized) {
                return true;
            }
        }

        return false;
    }
};


// ============================================================================
// 5. DNS RESPONSE
// ============================================================================

struct DNSResponse {
    vector<DNSRecord> answer;
    vector<DNSRecord> authority;
    vector<DNSRecord> additional;
    bool authoritative = false;
    bool fromCache = false;
    string error;

    bool success() const {
        return error.empty();
    }
};


// ============================================================================
// 6. AUTHORITATIVE SERVER
// ============================================================================

class AuthoritativeServer {
private:
    string serverName;
    vector<shared_ptr<DNSZone>> zones;

public:
    AuthoritativeServer(
        string name,
        vector<shared_ptr<DNSZone>> serverZones
    )
        : serverName(normalizeName(move(name))),
          zones(move(serverZones)) {}

    const string& getName() const {
        return serverName;
    }

    DNSResponse query(
        const string& name,
        RecordType type
    ) const {
        shared_ptr<DNSZone> bestZone;

        for (const auto& zone : zones) {
            if (
                isSubdomainOrEqual(
                    name,
                    zone->getOrigin()
                )
            ) {
                if (
                    !bestZone ||
                    zone->getOrigin().size() >
                    bestZone->getOrigin().size()
                ) {
                    bestZone = zone;
                }
            }
        }

        if (!bestZone) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "REFUSED"
            };
        }

        const auto answer =
            bestZone->query(name, type);

        if (!answer.empty()) {
            return DNSResponse{
                answer,
                {},
                {},
                true,
                false,
                ""
            };
        }

        if (bestZone->hasName(name)) {
            return DNSResponse{
                {},
                {},
                {},
                true,
                false,
                "NOERROR/NODATA"
            };
        }

        return DNSResponse{
            {},
            {},
            {},
            true,
            false,
            "NXDOMAIN"
        };
    }
};


// ============================================================================
// 7. DELEGATION
// ============================================================================

struct Delegation {
    string zoneName;
    vector<string> nameServers;

    Delegation(
        string zone,
        vector<string> servers
    )
        : zoneName(normalizeName(move(zone))) {
        for (auto& server : servers) {
            nameServers.push_back(
                normalizeName(move(server))
            );
        }
    }
};


// ============================================================================
// 8. ROOT SERVER
// ============================================================================

class RootServer {
private:
    map<string, Delegation> delegations;

public:
    explicit RootServer(
        vector<Delegation> rootDelegations
    ) {
        for (auto& delegation : rootDelegations) {
            delegations.emplace(
                delegation.zoneName,
                move(delegation)
            );
        }
    }

    DNSResponse query(
        const string& name
    ) const {
        const auto labels =
            splitDomainName(name);

        if (labels.empty()) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "INVALID_NAME"
            };
        }

        const string tld =
            normalizeName(labels.back());

        auto iterator =
            delegations.find(tld);

        if (iterator == delegations.end()) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "NXDOMAIN"
            };
        }

        vector<DNSRecord> authority;

        for (
            const string& server :
            iterator->second.nameServers
        ) {
            authority.emplace_back(
                tld,
                RecordType::NS,
                server,
                86400
            );
        }

        return DNSResponse{
            {},
            authority,
            {},
            true,
            false,
            ""
        };
    }
};


// ============================================================================
// 9. TLD SERVER
// ============================================================================

class TLDServer {
private:
    string tld;
    map<string, Delegation> delegations;

public:
    TLDServer(
        string tldName,
        vector<Delegation> tldDelegations
    )
        : tld(normalizeName(move(tldName))) {
        for (auto& delegation : tldDelegations) {
            delegations.emplace(
                delegation.zoneName,
                move(delegation)
            );
        }
    }

    DNSResponse query(
        const string& name
    ) const {
        const auto labels =
            splitDomainName(name);

        if (labels.size() < 2) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "INVALID_NAME"
            };
        }

        const string domain =
            normalizeName(
                labels[labels.size() - 2] +
                "." +
                labels[labels.size() - 1]
            );

        auto iterator =
            delegations.find(domain);

        if (iterator == delegations.end()) {
            return DNSResponse{
                {},
                {},
                {},
                true,
                false,
                "NXDOMAIN"
            };
        }

        vector<DNSRecord> authority;

        for (
            const string& server :
            iterator->second.nameServers
        ) {
            authority.emplace_back(
                domain,
                RecordType::NS,
                server,
                172800
            );
        }

        return DNSResponse{
            {},
            authority,
            {},
            true,
            false,
            ""
        };
    }
};


// ============================================================================
// 10. DNS CACHE
// ============================================================================

struct CacheEntry {
    vector<DNSRecord> records;
    chrono::steady_clock::time_point expiresAt;
    bool negative = false;
};

class DNSCache {
private:
    map<pair<string, RecordType>, CacheEntry> entries;

public:
    optional<CacheEntry> get(
        const string& name,
        RecordType type
    ) {
        const auto key =
            make_pair(
                normalizeName(name),
                type
            );

        auto iterator = entries.find(key);

        if (iterator == entries.end()) {
            return nullopt;
        }

        const auto now =
            chrono::steady_clock::now();

        if (now >= iterator->second.expiresAt) {
            entries.erase(iterator);
            return nullopt;
        }

        return iterator->second;
    }

    void put(
        const string& name,
        RecordType type,
        const vector<DNSRecord>& records,
        uint32_t ttl,
        bool negative = false
    ) {
        if (ttl == 0) {
            return;
        }

        const auto expiration =
            chrono::steady_clock::now() +
            chrono::seconds(ttl);

        entries[
            {
                normalizeName(name),
                type
            }
        ] = CacheEntry{
            records,
            expiration,
            negative
        };
    }

    void clear() {
        entries.clear();
    }

    size_t size() const {
        return entries.size();
    }
};


// ============================================================================
// 11. RECURSIVE RESOLVER
// ============================================================================

class RecursiveResolver {
private:
    RootServer rootServer;

    map<string, shared_ptr<TLDServer>> tldServers;

    map<
        string,
        shared_ptr<AuthoritativeServer>
    > authoritativeServers;

    DNSCache cache;

    vector<string> trace;

    size_t queryCount = 0;

    DNSResponse resolveInternal(
        const string& name,
        RecordType type,
        int maxCnameDepth,
        set<string>& visited
    ) {
        auto cached =
            cache.get(name, type);

        if (cached.has_value()) {
            trace.push_back(
                "CACHE HIT: " +
                normalizeName(name) +
                " " +
                toString(type)
            );

            DNSResponse response;
            response.answer =
                cached->records;
            response.fromCache = true;

            if (cached->negative) {
                response.error = "NXDOMAIN";
            }

            return response;
        }

        trace.push_back(
            "CACHE MISS: " +
            normalizeName(name) +
            " " +
            toString(type)
        );

        DNSResponse rootResponse =
            rootServer.query(name);

        trace.push_back(
            "ROOT: locate TLD delegation"
        );

        if (!rootResponse.success()) {
            return rootResponse;
        }

        const auto labels =
            splitDomainName(name);

        const string tld =
            normalizeName(labels.back());

        auto tldIterator =
            tldServers.find(tld);

        if (tldIterator == tldServers.end()) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "TLD_SERVER_UNAVAILABLE"
            };
        }

        DNSResponse tldResponse =
            tldIterator->second->query(name);

        trace.push_back(
            "TLD: locate authoritative server"
        );

        if (!tldResponse.success()) {
            return tldResponse;
        }

        if (tldResponse.authority.empty()) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "TLD_NO_DELEGATION"
            };
        }

        const string authorityName =
            normalizeName(
                tldResponse.authority.front().value
            );

        auto authorityIterator =
            authoritativeServers.find(
                authorityName
            );

        if (
            authorityIterator ==
            authoritativeServers.end()
        ) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "AUTHORITATIVE_SERVER_UNAVAILABLE"
            };
        }

        trace.push_back(
            "AUTHORITATIVE: query " +
            authorityName
        );

        DNSResponse response =
            authorityIterator->second->query(
                name,
                type
            );

        if (!response.answer.empty()) {
            uint32_t minimumTTL =
                numeric_limits<uint32_t>::max();

            for (const auto& record :
                 response.answer) {
                minimumTTL =
                    min(minimumTTL, record.ttl);
            }

            cache.put(
                name,
                type,
                response.answer,
                minimumTTL
            );

            return response;
        }

        // CNAME processing demonstrates an important DNS behavior:
        // the canonical name must be resolved for the requested type.
        if (type != RecordType::CNAME) {
            DNSResponse cnameResponse =
                authorityIterator->second->query(
                    name,
                    RecordType::CNAME
                );

            if (!cnameResponse.answer.empty()) {
                const string target =
                    normalizeName(
                        cnameResponse.answer.front().value
                    );

                trace.push_back(
                    "CNAME: " +
                    normalizeName(name) +
                    " -> " +
                    target
                );

                if (visited.count(name) > 0) {
                    return DNSResponse{
                        {},
                        {},
                        {},
                        false,
                        false,
                        "CNAME_LOOP"
                    };
                }

                if (
                    static_cast<int>(visited.size()) >=
                    maxCnameDepth
                ) {
                    return DNSResponse{
                        {},
                        {},
                        {},
                        false,
                        false,
                        "CNAME_CHAIN_TOO_LONG"
                    };
                }

                visited.insert(
                    normalizeName(name)
                );

                DNSResponse targetResponse =
                    resolveInternal(
                        target,
                        type,
                        maxCnameDepth,
                        visited
                    );

                if (!targetResponse.answer.empty()) {
                    targetResponse.authority =
                        cnameResponse.answer;

                    return targetResponse;
                }

                return targetResponse;
            }
        }

        // Negative caching reduces repeated work for nonexistent names.
        // Production implementations use standards-defined negative TTL
        // behavior rather than blindly using an arbitrary value.
        if (response.error == "NXDOMAIN") {
            cache.put(
                name,
                type,
                {},
                30,
                true
            );
        }

        return response;
    }

public:
    RecursiveResolver(
        RootServer root,
        map<string, shared_ptr<TLDServer>> tlds,
        map<
            string,
            shared_ptr<AuthoritativeServer>
        > authorities
    )
        : rootServer(move(root)),
          tldServers(move(tlds)),
          authoritativeServers(move(authorities)) {}

    DNSResponse resolve(
        const string& name,
        RecordType type = RecordType::A,
        int maxCnameDepth = 8
    ) {
        queryCount++;
        trace.clear();

        const string normalized =
            normalizeName(name);

        if (!validDomainName(normalized)) {
            return DNSResponse{
                {},
                {},
                {},
                false,
                false,
                "INVALID_DOMAIN_NAME"
            };
        }

        set<string> visited;

        return resolveInternal(
            normalized,
            type,
            maxCnameDepth,
            visited
        );
    }

    const vector<string>& getTrace() const {
        return trace;
    }

    size_t getQueryCount() const {
        return queryCount;
    }

    size_t cacheSize() const {
        return cache.size();
    }
};


// ============================================================================
// 12. ENTERPRISE CASE STUDY
// ============================================================================

struct EnterpriseDNS {
    shared_ptr<DNSZone> zone;
    shared_ptr<AuthoritativeServer> authoritative;
    shared_ptr<TLDServer> tld;
    unique_ptr<RecursiveResolver> resolver;
};

EnterpriseDNS buildEnterpriseDNS() {
    auto zone =
        make_shared<DNSZone>(
            "corp.example."
        );

    // Main application endpoint.
    zone->addRecord(
        DNSRecord(
            "corp.example.",
            RecordType.A,
            "192.0.2.10",
            300
        )
    );

    // Public web service is an alias.
    zone->addRecord(
        DNSRecord(
            "www.corp.example.",
            RecordType.CNAME,
            "corp.example.",
            120
        )
    );

    // API has both IPv4 and IPv6.
    zone->addRecord(
        DNSRecord(
            "api.corp.example.",
            RecordType.A,
            "192.0.2.20",
            60
        )
    );

    zone->addRecord(
        DNSRecord(
            "api.corp.example.",
            RecordType.AAAA,
            "2001:db8::20",
            60
        )
    );

    // Mail infrastructure.
    zone->addRecord(
        DNSRecord(
            "mail.corp.example.",
            RecordType.A,
            "192.0.2.30",
            300
        )
    );

    zone->addRecord(
        DNSRecord(
            "corp.example.",
            RecordType.MX,
            "mail.corp.example.",
            3600,
            10
        )
    );

    // Authoritative delegation information.
    zone->addRecord(
        DNSRecord(
            "corp.example.",
            RecordType.NS,
            "ns1.corp.example.",
            86400
        )
    );

    // A TXT record can be used for verification and policy data.
    zone->addRecord(
        DNSRecord(
            "corp.example.",
            RecordType.TXT,
            "service-verification=demo-value",
            3600
        )
    );

    auto authoritative =
        make_shared<AuthoritativeServer>(
            "ns1.corp.example.",
            vector<shared_ptr<DNSZone>>{zone}
        );

    RootServer root({
        Delegation(
            ".example.",
            {"a.example-tld.example."}
        )
    });

    auto tld =
        make_shared<TLDServer>(
            ".example.",
            vector<Delegation>{
                Delegation(
                    "corp.example.",
                    {"ns1.corp.example."}
                )
            }
        );

    auto resolver =
        make_unique<RecursiveResolver>(
            move(root),
            map<string, shared_ptr<TLDServer>>{
                {".example.", tld}
            },
            map<
                string,
                shared_ptr<AuthoritativeServer>
            >{
                {"ns1.corp.example.", authoritative}
            }
        );

    return EnterpriseDNS{
        zone,
        authoritative,
        tld,
        move(resolver)
    };
}


// ============================================================================
// 13. QUERY DISPLAY
// ============================================================================

void printResponse(
    const string& queryName,
    RecordType type,
    const DNSResponse& response,
    const vector<string>& trace
) {
    cout << "\nQuery: "
         << normalizeName(queryName)
         << " "
         << toString(type)
         << "\n";

    cout << "Trace:\n";

    for (const string& event : trace) {
        cout << "  " << event << "\n";
    }

    if (!response.answer.empty()) {
        cout << "Answer:\n";

        for (const auto& record :
             response.answer) {
            cout << "  "
                 << record.toString()
                 << "\n";
        }
    } else {
        cout << "Status: "
             << response.error
             << "\n";
    }

    cout << "Cache hit: "
         << boolalpha
         << response.fromCache
         << "\n";
}


// ============================================================================
// 14. REVERSE DNS
// ============================================================================

string reverseIPv4Name(const string& address) {
    vector<int> octets;
    stringstream stream(address);
    string part;

    while (getline(stream, part, '.')) {
        if (part.empty()) {
            throw invalid_argument(
                "Invalid IPv4 address"
            );
        }

        int value = stoi(part);

        if (value < 0 || value > 255) {
            throw invalid_argument(
                "Invalid IPv4 address"
            );
        }

        octets.push_back(value);
    }

    if (octets.size() != 4) {
        throw invalid_argument(
            "IPv4 address requires four octets"
        );
    }

    ostringstream output;

    output
        << octets[3] << "."
        << octets[2] << "."
        << octets[1] << "."
        << octets[0]
        << ".in-addr.arpa.";

    return output.str();
}


// ============================================================================
// 15. CNAME LOOP CASE STUDY
// ============================================================================

void demonstrateCNAMELoop() {
    cout << "\n"
         << string(78, '=')
         << "\nCNAME LOOP FAILURE CASE\n"
         << string(78, '=')
         << "\n";

    auto zone =
        make_shared<DNSZone>(
            "loop.example."
        );

    zone->addRecord(
        DNSRecord(
            "a.loop.example.",
            RecordType::CNAME,
            "b.loop.example.",
            60
        )
    );

    zone->addRecord(
        DNSRecord(
            "b.loop.example.",
            RecordType::CNAME,
            "a.loop.example.",
            60
        )
    );

    auto authoritative =
        make_shared<AuthoritativeServer>(
            "ns.loop.example.",
            vector<shared_ptr<DNSZone>>{zone}
        );

    RootServer root({
        Delegation(
            ".example.",
            {"a.example-tld.example."}
        )
    });

    auto tld =
        make_shared<TLDServer>(
            ".example.",
            vector<Delegation>{
                Delegation(
                    "loop.example.",
                    {"ns.loop.example."}
                )
            }
        );

    RecursiveResolver resolver(
        move(root),
        {
            {".example.", tld}
        },
        {
            {"ns.loop.example.", authoritative}
        }
    );

    DNSResponse response =
        resolver.resolve(
            "a.loop.example.",
            RecordType::A
        );

    for (const string& event :
         resolver.getTrace()) {
        cout << "  "
             << event
             << "\n";
    }

    cout << "Result: "
         << response.error
         << "\n";
}


// ============================================================================
// 16. TESTS
// ============================================================================

void runTests() {
    cout << "\n"
         << string(78, '=')
         << "\nAUTOMATED TESTS\n"
         << string(78, '=')
         << "\n";

    EnterpriseDNS infrastructure =
        buildEnterpriseDNS();

    DNSResponse response =
        infrastructure.resolver->resolve(
            "api.corp.example.",
            RecordType::A
        );

    assert(response.success());
    assert(!response.answer.empty());
    assert(
        response.answer.front().value ==
        "192.0.2.20"
    );

    response =
        infrastructure.resolver->resolve(
            "api.corp.example.",
            RecordType::AAAA
        );

    assert(response.success());
    assert(
        response.answer.front().value ==
        "2001:db8::20"
    );

    response =
        infrastructure.resolver->resolve(
            "www.corp.example.",
            RecordType::A
        );

    assert(response.success());
    assert(
        response.answer.front().value ==
        "192.0.2.10"
    );

    response =
        infrastructure.resolver->resolve(
            "missing.corp.example.",
            RecordType::A
        );

    assert(
        response.error == "NXDOMAIN"
    );

    response =
        infrastructure.resolver->resolve(
            "api.corp.example.",
            RecordType::A
        );

    assert(response.fromCache);

    assert(
        reverseIPv4Name("192.0.2.10") ==
        "10.2.0.192.in-addr.arpa."
    );

    try {
        DNSRecord invalid(
            "bad.corp.example.",
            RecordType::A,
            "999.1.1.1"
        );

        validateRecord(invalid);

        assert(false);
    } catch (const invalid_argument&) {
        // Expected validation failure.
    }

    assert(
        validDomainName(
            "api.corp.example."
        )
    );

    assert(
        !validDomainName(
            "bad..corp.example."
        )
    );

    cout << "All tests passed.\n";
}


// ============================================================================
// 17. PERFORMANCE DISCUSSION
// ============================================================================

void demonstratePerformance() {
    cout << "\n"
         << string(78, '=')
         << "\nPERFORMANCE AND DESIGN CONSIDERATIONS\n"
         << string(78, '=')
         << "\n";

    // A cold lookup can require multiple network exchanges.
    const double rootRTT = 25.0;
    const double tldRTT = 20.0;
    const double authorityRTT = 30.0;

    const double coldLookup =
        rootRTT +
        tldRTT +
        authorityRTT;

    cout << fixed
         << setprecision(1)
         << "Illustrative cold-cache sequential cost: "
         << coldLookup
         << " ms\n";

    cout << "Illustrative cache-hit path: one local cache lookup.\n";

    cout << "\nImportant performance variables:\n";

    const vector<string> factors{
        "Cache hit ratio",
        "TTL configuration",
        "Network latency",
        "Packet loss",
        "Retry behavior",
        "Authoritative-server latency",
        "Resolver CPU and memory load",
        "DNSSEC validation",
        "Transport protocol",
        "Negative caching"
    };

    for (const auto& factor : factors) {
        cout << "  - "
             << factor
             << "\n";
    }
}


// ============================================================================
// 18. SECURITY DESIGN
// ============================================================================

void demonstrateSecurity() {
    cout << "\n"
         << string(78, '=')
         << "\nDNS SECURITY DESIGN\n"
         << string(78, '=')
         << "\n";

    const vector<pair<string, string>> topics{
        {
            "DNSSEC",
            "Authenticates DNS data with cryptographic signatures."
        },
        {
            "Cache poisoning",
            "Attempts to place forged DNS information into caches."
        },
        {
            "DNS over TLS",
            "Encrypts DNS transport with TLS."
        },
        {
            "DNS over HTTPS",
            "Carries DNS queries through HTTPS."
        },
        {
            "Open resolver exposure",
            "Can permit unauthorized use and amplification abuse."
        },
        {
            "Split-horizon DNS",
            "Can provide different answers to different networks."
        }
    };

    for (const auto& [name, explanation] :
         topics) {
        cout << name
             << ": "
             << explanation
             << "\n";
    }
}


// ============================================================================
// 19. ENTERPRISE QUERY WORKFLOW
// ============================================================================

void runEnterpriseScenario() {
    cout << "\n"
         << string(78, '=')
         << "\nENTERPRISE DNS CASE STUDY\n"
         << string(78, '=')
         << "\n";

    EnterpriseDNS infrastructure =
        buildEnterpriseDNS();

    struct Query {
        string name;
        RecordType type;
    };

    const vector<Query> queries{
        {"corp.example.", RecordType::A},
        {"www.corp.example.", RecordType::A},
        {"api.corp.example.", RecordType::A},
        {"api.corp.example.", RecordType::AAAA},
        {"corp.example.", RecordType::MX},
        {"corp.example.", RecordType::TXT},
        {"unknown.corp.example.", RecordType::A}
    };

    for (const auto& query : queries) {
        DNSResponse response =
            infrastructure.resolver->resolve(
                query.name,
                query.type
            );

        printResponse(
            query.name,
            query.type,
            response,
            infrastructure.resolver->getTrace()
        );
    }

    cout << "\nResolver query count: "
         << infrastructure.resolver->getQueryCount()
         << "\n";

    cout << "Cached keys: "
         << infrastructure.resolver->cacheSize()
         << "\n";
}


// ============================================================================
// 20. MAIN
// ============================================================================

int main() {
    try {
        cout << "DNS INDUSTRY-STYLE CASE STUDY\n";
        cout << "C++17 self-contained DNS simulation\n";

        runEnterpriseScenario();
        demonstrateCNAMELoop();
        demonstratePerformance();
        demonstrateSecurity();

        cout << "\n"
             << string(78, '=')
             << "\nREVERSE DNS EXAMPLE\n"
             << string(78, '=')
             << "\n";

        cout
            << "192.0.2.10 -> "
            << reverseIPv4Name("192.0.2.10")
            << "\n";

        runTests();

        cout << "\nProgram completed successfully.\n";
    } catch (const exception& exception) {
        cerr
            << "Fatal error: "
            << exception.what()
            << "\n";

        return 1;
    }

    return 0;
}
