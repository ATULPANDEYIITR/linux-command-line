/*
 * HTTP and HTTPS: Industry-Style Secure API Gateway Case Study
 *
 * Standard: C++17 or later
 *
 * This program models an API gateway that:
 *   - parses and validates HTTP requests,
 *   - routes requests,
 *   - authenticates bearer tokens,
 *   - validates request bodies,
 *   - applies rate limiting,
 *   - supports ETag-based conditional requests,
 *   - handles byte ranges,
 *   - constructs HTTP responses,
 *   - records security-aware request metrics,
 *   - demonstrates HTTP/HTTPS architectural distinctions,
 *   - models TLS configuration and certificate validation concepts.
 *
 * The C++ standard library does not provide a complete production HTTP/TLS
 * implementation. Therefore the program deliberately models protocol and
 * architecture behavior instead of pretending that a hand-written parser is
 * a replacement for a mature production HTTP/TLS library.
 *
 * Compile:
 *     g++ -std=c++17 -O2 -Wall -Wextra -pedantic http_https_gateway.cpp -o gateway
 *
 * Run:
 *     ./gateway
 */

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <random>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace http_learning {

using Clock = std::chrono::steady_clock;


// ============================================================================
// 1. STRING UTILITIES
// ============================================================================

std::string trim(const std::string& input) {
    const auto first = input.find_first_not_of(" \t\r\n");

    if (first == std::string::npos) {
        return "";
    }

    const auto last = input.find_last_not_of(" \t\r\n");

    return input.substr(first, last - first + 1);
}

std::string to_lower(std::string value) {
    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char character) {
            return static_cast<char>(std::tolower(character));
        }
    );

    return value;
}

bool is_token_character(char character) {
    if (std::isalnum(static_cast<unsigned char>(character))) {
        return true;
    }

    constexpr std::string_view allowed =
        "!#$%&'*+-.^_`|~";

    return allowed.find(character) != std::string_view::npos;
}

bool valid_header_name(const std::string& name) {
    if (name.empty()) {
        return false;
    }

    return std::all_of(
        name.begin(),
        name.end(),
        is_token_character
    );
}

bool valid_header_value(const std::string& value) {
    /*
     * CR and LF are forbidden here because accepting them while constructing
     * a serialized message could permit HTTP response/request splitting.
     */
    return value.find('\r') == std::string::npos
        && value.find('\n') == std::string::npos;
}


// ============================================================================
// 2. HTTP METHODS
// ============================================================================

enum class HTTPMethod {
    GET,
    HEAD,
    POST,
    PUT,
    PATCH,
    DELETE_,
    OPTIONS,
    UNKNOWN
};

std::string method_to_string(HTTPMethod method) {
    switch (method) {
        case HTTPMethod::GET:
            return "GET";
        case HTTPMethod::HEAD:
            return "HEAD";
        case HTTPMethod::POST:
            return "POST";
        case HTTPMethod::PUT:
            return "PUT";
        case HTTPMethod::PATCH:
            return "PATCH";
        case HTTPMethod::DELETE_:
            return "DELETE";
        case HTTPMethod::OPTIONS:
            return "OPTIONS";
        default:
            return "UNKNOWN";
    }
}

HTTPMethod parse_method(const std::string& method) {
    if (method == "GET") return HTTPMethod::GET;
    if (method == "HEAD") return HTTPMethod::HEAD;
    if (method == "POST") return HTTPMethod::POST;
    if (method == "PUT") return HTTPMethod::PUT;
    if (method == "PATCH") return HTTPMethod::PATCH;
    if (method == "DELETE") return HTTPMethod::DELETE_;
    if (method == "OPTIONS") return HTTPMethod::OPTIONS;

    return HTTPMethod::UNKNOWN;
}

bool is_idempotent(HTTPMethod method) {
    switch (method) {
        case HTTPMethod::GET:
        case HTTPMethod::HEAD:
        case HTTPMethod::PUT:
        case HTTPMethod::DELETE_:
        case HTTPMethod::OPTIONS:
            return true;

        default:
            return false;
    }
}


// ============================================================================
// 3. HTTP STATUS
// ============================================================================

enum class StatusClass {
    INFORMATIONAL,
    SUCCESS,
    REDIRECTION,
    CLIENT_ERROR,
    SERVER_ERROR
};

StatusClass classify_status(int status) {
    if (status < 100 || status > 599) {
        throw std::invalid_argument("HTTP status must be between 100 and 599.");
    }

    if (status < 200) return StatusClass::INFORMATIONAL;
    if (status < 300) return StatusClass::SUCCESS;
    if (status < 400) return StatusClass::REDIRECTION;
    if (status < 500) return StatusClass::CLIENT_ERROR;

    return StatusClass::SERVER_ERROR;
}

std::string reason_phrase(int status) {
    static const std::unordered_map<int, std::string> reasons = {
        {200, "OK"},
        {201, "Created"},
        {202, "Accepted"},
        {204, "No Content"},
        {206, "Partial Content"},
        {301, "Moved Permanently"},
        {302, "Found"},
        {303, "See Other"},
        {304, "Not Modified"},
        {307, "Temporary Redirect"},
        {308, "Permanent Redirect"},
        {400, "Bad Request"},
        {401, "Unauthorized"},
        {403, "Forbidden"},
        {404, "Not Found"},
        {405, "Method Not Allowed"},
        {409, "Conflict"},
        {412, "Precondition Failed"},
        {413, "Content Too Large"},
        {415, "Unsupported Media Type"},
        {429, "Too Many Requests"},
        {500, "Internal Server Error"},
        {501, "Not Implemented"},
        {502, "Bad Gateway"},
        {503, "Service Unavailable"},
        {504, "Gateway Timeout"}
    };

    const auto iterator = reasons.find(status);

    if (iterator != reasons.end()) {
        return iterator->second;
    }

    return "Unknown";
}


// ============================================================================
// 4. HTTP HEADERS
// ============================================================================

class Headers {
private:
    std::map<std::string, std::string> values;

public:
    void set(const std::string& name, const std::string& value) {
        if (!valid_header_name(name)) {
            throw std::invalid_argument("Invalid HTTP header name: " + name);
        }

        if (!valid_header_value(value)) {
            throw std::invalid_argument(
                "HTTP header value contains CR/LF."
            );
        }

        values[to_lower(name)] = value;
    }

    bool contains(const std::string& name) const {
        return values.find(to_lower(name)) != values.end();
    }

    std::optional<std::string> get(const std::string& name) const {
        const auto iterator = values.find(to_lower(name));

        if (iterator == values.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    const std::map<std::string, std::string>& all() const {
        return values;
    }
};


// ============================================================================
// 5. HTTP REQUEST
// ============================================================================

struct HTTPRequest {
    HTTPMethod method = HTTPMethod::UNKNOWN;
    std::string target;
    std::string version = "HTTP/1.1";
    Headers headers;
    std::string body;

    bool has_valid_host() const {
        return headers.contains("host");
    }
};


// ============================================================================
// 6. HTTP RESPONSE
// ============================================================================

struct HTTPResponse {
    int status = 500;
    std::string reason = "Internal Server Error";
    std::string version = "HTTP/1.1";
    Headers headers;
    std::string body;

    static HTTPResponse json(
        int status_code,
        const std::string& json_body
    ) {
        HTTPResponse response;

        response.status = status_code;
        response.reason = reason_phrase(status_code);
        response.body = json_body;

        response.headers.set(
            "Content-Type",
            "application/json; charset=utf-8"
        );

        response.headers.set(
            "Content-Length",
            std::to_string(response.body.size())
        );

        response.headers.set(
            "Cache-Control",
            "no-store"
        );

        response.headers.set(
            "X-Content-Type-Options",
            "nosniff"
        );

        return response;
    }

    std::string serialize() const {
        std::ostringstream output;

        output << version
               << ' '
               << status
               << ' '
               << reason
               << "\r\n";

        for (const auto& [name, value] : headers.all()) {
            output << name << ": " << value << "\r\n";
        }

        output << "\r\n";
        output << body;

        return output.str();
    }
};


// ============================================================================
// 7. REQUEST PARSER
// ============================================================================

class HTTPParser {
public:
    static HTTPRequest parse(const std::string& raw) {
        const std::size_t separator = raw.find("\r\n\r\n");

        if (separator == std::string::npos) {
            throw std::invalid_argument(
                "HTTP message has no header/body separator."
            );
        }

        const std::string headerBlock = raw.substr(0, separator);
        const std::string body = raw.substr(separator + 4);

        std::istringstream stream(headerBlock);
        std::string requestLine;

        if (!std::getline(stream, requestLine)) {
            throw std::invalid_argument("Missing HTTP request line.");
        }

        if (!requestLine.empty() && requestLine.back() == '\r') {
            requestLine.pop_back();
        }

        std::istringstream requestLineStream(requestLine);

        std::string methodText;
        std::string target;
        std::string version;

        requestLineStream
            >> methodText
            >> target
            >> version;

        if (methodText.empty() || target.empty() || version.empty()) {
            throw std::invalid_argument("Malformed request line.");
        }

        HTTPRequest request;

        request.method = parse_method(methodText);
        request.target = target;
        request.version = version;
        request.body = body;

        std::string headerLine;

        while (std::getline(stream, headerLine)) {
            if (!headerLine.empty() && headerLine.back() == '\r') {
                headerLine.pop_back();
            }

            if (headerLine.empty()) {
                continue;
            }

            const std::size_t colon = headerLine.find(':');

            if (colon == std::string::npos) {
                throw std::invalid_argument(
                    "Malformed HTTP header: " + headerLine
                );
            }

            const std::string name = trim(
                headerLine.substr(0, colon)
            );

            const std::string value = trim(
                headerLine.substr(colon + 1)
            );

            request.headers.set(name, value);
        }

        if (request.version == "HTTP/1.1"
            && !request.has_valid_host()) {
            throw std::invalid_argument(
                "HTTP/1.1 request requires Host header."
            );
        }

        if (const auto contentLength =
                request.headers.get("content-length")) {

            std::size_t declaredLength = 0;

            try {
                declaredLength = std::stoull(*contentLength);
            } catch (...) {
                throw std::invalid_argument(
                    "Invalid Content-Length."
                );
            }

            if (declaredLength != request.body.size()) {
                throw std::invalid_argument(
                    "Content-Length does not match body size."
                );
            }
        }

        return request;
    }
};


// ============================================================================
// 8. SECURITY TOKEN STORE
// ============================================================================

class TokenStore {
private:
    std::unordered_map<std::string, std::string> tokenToUser;

public:
    void add(const std::string& token, const std::string& username) {
        if (token.empty() || username.empty()) {
            throw std::invalid_argument(
                "Token and username cannot be empty."
            );
        }

        tokenToUser[token] = username;
    }

    std::optional<std::string> authenticate(
        const std::string& authorization
    ) const {
        constexpr std::string_view prefix = "Bearer ";

        if (authorization.size() <= prefix.size()) {
            return std::nullopt;
        }

        if (authorization.compare(
                0,
                prefix.size(),
                prefix
            ) != 0) {
            return std::nullopt;
        }

        const std::string token =
            authorization.substr(prefix.size());

        const auto iterator = tokenToUser.find(token);

        if (iterator == tokenToUser.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }
};


// ============================================================================
// 9. REQUEST RATE LIMITER
// ============================================================================

class RateLimiter {
private:
    struct ClientWindow {
        std::vector<Clock::time_point> requests;
    };

    std::unordered_map<std::string, ClientWindow> clients;

    std::size_t limit;
    std::chrono::seconds window;

public:
    RateLimiter(
        std::size_t requestLimit,
        std::chrono::seconds windowDuration
    )
        : limit(requestLimit),
          window(windowDuration) {

        if (limit == 0 || window.count() <= 0) {
            throw std::invalid_argument(
                "Rate limiter values must be positive."
            );
        }
    }

    bool allow(
        const std::string& clientId,
        Clock::time_point now = Clock::now()
    ) {
        auto& windowState = clients[clientId];

        const auto cutoff = now - window;

        windowState.requests.erase(
            std::remove_if(
                windowState.requests.begin(),
                windowState.requests.end(),
                [cutoff](const auto& timestamp) {
                    return timestamp <= cutoff;
                }
            ),
            windowState.requests.end()
        );

        if (windowState.requests.size() >= limit) {
            return false;
        }

        windowState.requests.push_back(now);
        return true;
    }
};


// ============================================================================
// 10. ETAG GENERATION
// ============================================================================

std::string pseudo_etag(const std::string& body) {
    /*
     * This is an educational deterministic hash substitute, not a
     * cryptographic implementation. Production systems should use a robust
     * cryptographic hash implementation or a version identifier as appropriate.
     */
    std::hash<std::string> hasher;

    const std::size_t digest = hasher(body);

    std::ostringstream output;

    output << '"'
           << std::hex
           << digest
           << '"';

    return output.str();
}


// ============================================================================
// 11. RANGE PROCESSING
// ============================================================================

struct ByteRange {
    std::size_t start;
    std::size_t end;
};

std::optional<ByteRange> parse_range(
    const std::string& header,
    std::size_t resourceSize
) {
    static const std::regex pattern(
        R"(bytes=(\d+)-(\d*))"
    );

    std::smatch match;

    if (!std::regex_match(header, match, pattern)) {
        return std::nullopt;
    }

    const std::size_t start =
        std::stoull(match[1].str());

    if (start >= resourceSize) {
        return std::nullopt;
    }

    std::size_t end;

    if (match[2].str().empty()) {
        end = resourceSize - 1;
    } else {
        end = std::stoull(match[2].str());
    }

    if (end < start) {
        return std::nullopt;
    }

    end = std::min(end, resourceSize - 1);

    return ByteRange{start, end};
}


// ============================================================================
// 12. TLS CONFIGURATION MODEL
// ============================================================================

struct TLSConfiguration {
    std::string minimumVersion = "TLS 1.2";
    bool certificateVerification = true;
    bool hostnameVerification = true;
    bool requireTrustedChain = true;

    void validate() const {
        if (!certificateVerification) {
            throw std::runtime_error(
                "TLS certificate verification is disabled."
            );
        }

        if (!hostnameVerification) {
            throw std::runtime_error(
                "TLS hostname verification is disabled."
            );
        }

        if (!requireTrustedChain) {
            throw std::runtime_error(
                "Trusted certificate-chain verification is disabled."
            );
        }
    }
};


// ============================================================================
// 13. SECURITY-AWARE API GATEWAY
// ============================================================================

class APIGateway {
private:
    TokenStore tokens;
    RateLimiter limiter;

    std::unordered_map<std::string, std::string> resources;

    TLSConfiguration tlsConfig;

    std::size_t maximumBodyBytes = 1'000'000;

public:
    APIGateway()
        : limiter(
            5,
            std::chrono::seconds(60)
        ) {

        tokens.add(
            "token-alice-123",
            "alice"
        );

        resources["/api/products"] =
            R"({"products":[{"id":1,"name":"Laptop"},{"id":2,"name":"Monitor"}]})";

        resources["/api/status"] =
            R"({"status":"operational"})";

        tlsConfig.validate();
    }

    HTTPResponse handle(
        const HTTPRequest& request,
        const std::string& clientId
    ) {
        /*
         * Request processing order is deliberate:
         *
         * 1. Basic protocol validation occurs before application processing.
         * 2. Rate limiting limits abusive clients.
         * 3. Authentication identifies the caller.
         * 4. Authorization determines whether the operation is permitted.
         * 5. Resource processing occurs only after those controls succeed.
         */
        if (!limiter.allow(clientId)) {
            return HTTPResponse::json(
                429,
                R"({"error":"rate_limit_exceeded"})"
            );
        }

        if (request.method == HTTPMethod::UNKNOWN) {
            return HTTPResponse::json(
                501,
                R"({"error":"method_not_implemented"})"
            );
        }

        if (request.body.size() > maximumBodyBytes) {
            return HTTPResponse::json(
                413,
                R"({"error":"request_body_too_large"})"
            );
        }

        if (request.method == HTTPMethod::POST
            || request.method == HTTPMethod::PUT
            || request.method == HTTPMethod::PATCH) {

            if (!request.headers.contains("content-type")) {
                return HTTPResponse::json(
                    415,
                    R"({"error":"content_type_required"})"
                );
            }
        }

        const bool protectedRoute =
            request.target.rfind("/api/", 0) == 0;

        std::optional<std::string> username;

        if (protectedRoute) {
            const auto authorization =
                request.headers.get("authorization");

            if (!authorization) {
                return HTTPResponse::json(
                    401,
                    R"({"error":"authentication_required"})"
                );
            }

            username = tokens.authenticate(*authorization);

            if (!username) {
                return HTTPResponse::json(
                    401,
                    R"({"error":"invalid_credentials"})"
                );
            }
        }

        if (request.method == HTTPMethod::GET
            || request.method == HTTPMethod::HEAD) {

            return handle_read(request);
        }

        if (request.method == HTTPMethod::POST) {
            return handle_create(request, username.value_or(""));
        }

        if (request.method == HTTPMethod::OPTIONS) {
            return handle_options();
        }

        if (request.method == HTTPMethod::DELETE_) {
            return HTTPResponse::json(
                403,
                R"({"error":"delete_disabled_for_demo"})"
            );
        }

        return HTTPResponse::json(
            405,
            R"({"error":"method_not_allowed"})"
        );
    }

private:
    HTTPResponse handle_read(
        const HTTPRequest& request
    ) {
        const auto iterator = resources.find(request.target);

        if (iterator == resources.end()) {
            return HTTPResponse::json(
                404,
                R"({"error":"resource_not_found"})"
            );
        }

        const std::string& representation = iterator->second;

        const std::string etag =
            pseudo_etag(representation);

        if (const auto requestETag =
                request.headers.get("if-none-match")) {

            if (*requestETag == etag) {
                HTTPResponse response;

                response.status = 304;
                response.reason = reason_phrase(304);

                response.headers.set(
                    "ETag",
                    etag
                );

                response.headers.set(
                    "Cache-Control",
                    "private, max-age=60"
                );

                return response;
            }
        }

        /*
         * Range processing demonstrates partial responses. A real production
         * implementation must also consider If-Range, multiple ranges,
         * compression, content encoding, and representation identity.
         */
        if (const auto rangeHeader =
                request.headers.get("range")) {

            const auto range =
                parse_range(
                    *rangeHeader,
                    representation.size()
                );

            if (!range) {
                return HTTPResponse::json(
                    416,
                    R"({"error":"range_not_satisfiable"})"
                );
            }

            const std::string partial =
                representation.substr(
                    range->start,
                    range->end - range->start + 1
                );

            HTTPResponse response;

            response.status = 206;
            response.reason = reason_phrase(206);
            response.body = partial;

            response.headers.set(
                "Content-Type",
                "application/json"
            );

            response.headers.set(
                "Content-Length",
                std::to_string(response.body.size())
            );

            response.headers.set(
                "Content-Range",
                "bytes "
                + std::to_string(range->start)
                + "-"
                + std::to_string(range->end)
                + "/"
                + std::to_string(representation.size())
            );

            response.headers.set(
                "ETag",
                etag
            );

            return response;
        }

        HTTPResponse response;

        response.status = 200;
        response.reason = reason_phrase(200);
        response.body = representation;

        response.headers.set(
            "Content-Type",
            "application/json"
        );

        response.headers.set(
            "Content-Length",
            std::to_string(response.body.size())
        );

        response.headers.set(
            "ETag",
            etag
        );

        response.headers.set(
            "Cache-Control",
            "private, max-age=60"
        );

        response.headers.set(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains"
        );

        /*
         * A HEAD request has the same response metadata as GET but does not
         * include the representation body.
         */
        if (request.method == HTTPMethod::HEAD) {
            response.body.clear();
        }

        return response;
    }

    HTTPResponse handle_create(
        const HTTPRequest& request,
        const std::string& username
    ) {
        if (username.empty()) {
            return HTTPResponse::json(
                401,
                R"({"error":"authentication_required"})"
            );
        }

        const auto contentType =
            request.headers.get("content-type");

        if (!contentType
            || contentType->find("application/json")
                == std::string::npos) {

            return HTTPResponse::json(
                415,
                R"({"error":"application_json_required"})"
            );
        }

        if (request.body.empty()) {
            return HTTPResponse::json(
                400,
                R"({"error":"empty_request_body"})"
            );
        }

        /*
         * A complete API would parse JSON with a mature JSON library and
         * validate a schema. The standard library does not provide JSON
         * parsing, so this case study performs a conservative structural
         * check rather than pretending to implement a full JSON parser.
         */
        const char first =
            request.body.front();

        const char last =
            request.body.back();

        if (first != '{' || last != '}') {
            return HTTPResponse::json(
                400,
                R"({"error":"expected_json_object"})"
            );
        }

        std::ostringstream responseBody;

        responseBody
            << "{"
            << "\"created\":true,"
            << "\"createdBy\":\""
            << username
            << "\","
            << "\"bytes\":"
            << request.body.size()
            << "}";

        HTTPResponse response =
            HTTPResponse::json(
                201,
                responseBody.str()
            );

        response.headers.set(
            "Location",
            "/api/resources/generated"
        );

        return response;
    }

    HTTPResponse handle_options() const {
        HTTPResponse response;

        response.status = 204;
        response.reason = reason_phrase(204);

        response.headers.set(
            "Allow",
            "GET, HEAD, POST, OPTIONS"
        );

        response.headers.set(
            "Access-Control-Allow-Methods",
            "GET, HEAD, POST, OPTIONS"
        );

        response.headers.set(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, If-None-Match, Range"
        );

        return response;
    }
};


// ============================================================================
// 14. REQUEST GENERATORS
// ============================================================================

HTTPRequest make_request(
    HTTPMethod method,
    const std::string& target,
    const std::string& token = ""
) {
    HTTPRequest request;

    request.method = method;
    request.target = target;
    request.version = "HTTP/1.1";

    request.headers.set(
        "Host",
        "api.example.test"
    );

    request.headers.set(
        "User-Agent",
        "CPP-HTTP-Learning-Gateway/1.0"
    );

    if (!token.empty()) {
        request.headers.set(
            "Authorization",
            "Bearer " + token
        );
    }

    return request;
}


// ============================================================================
// 15. TEST SCENARIOS
// ============================================================================

void print_response(
    const std::string& scenario,
    const HTTPResponse& response
) {
    std::cout
        << "\n[" << scenario << "]\n"
        << response.serialize()
        << "\n";
}

void run_gateway_case_study() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "HTTP/HTTPS API GATEWAY CASE STUDY"
        << "\n"
        << std::string(78, '=')
        << "\n";

    APIGateway gateway;

    // ------------------------------------------------------------------------
    // Scenario 1: unauthenticated protected request
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::GET,
                "/api/products"
            );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-unauthenticated"
            );

        print_response(
            "1. Missing authentication",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 2: authenticated GET
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::GET,
                "/api/products",
                "token-alice-123"
            );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-alice"
            );

        print_response(
            "2. Authenticated GET",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 3: conditional GET
    // ------------------------------------------------------------------------

    std::string etag;

    {
        HTTPRequest firstRequest =
            make_request(
                HTTPMethod::GET,
                "/api/status",
                "token-alice-123"
            );

        HTTPResponse firstResponse =
            gateway.handle(
                firstRequest,
                "client-alice-cache"
            );

        etag =
            firstResponse.headers
                .get("etag")
                .value_or("");

        print_response(
            "3A. Initial cached resource",
            firstResponse
        );
    }

    {
        HTTPRequest conditionalRequest =
            make_request(
                HTTPMethod::GET,
                "/api/status",
                "token-alice-123"
            );

        conditionalRequest.headers.set(
            "If-None-Match",
            etag
        );

        HTTPResponse response =
            gateway.handle(
                conditionalRequest,
                "client-alice-cache"
            );

        print_response(
            "3B. Conditional GET with matching ETag",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 4: POST with JSON
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::POST,
                "/api/products",
                "token-alice-123"
            );

        request.headers.set(
            "Content-Type",
            "application/json"
        );

        request.body =
            R"({"name":"Keyboard","price":2500})";

        request.headers.set(
            "Content-Length",
            std::to_string(request.body.size())
        );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-alice-write"
            );

        print_response(
            "4. Authenticated JSON creation",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 5: oversized body
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::POST,
                "/api/products",
                "token-alice-123"
            );

        request.headers.set(
            "Content-Type",
            "application/json"
        );

        request.body =
            std::string(
                1'000'001,
                'x'
            );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-large-upload"
            );

        print_response(
            "5. Oversized request body",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 6: byte range
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::GET,
                "/api/status",
                "token-alice-123"
            );

        request.headers.set(
            "Range",
            "bytes=0-9"
        );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-range"
            );

        print_response(
            "6. Partial content",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 7: OPTIONS
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::OPTIONS,
                "/api/products"
            );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-options"
            );

        print_response(
            "7. OPTIONS capability discovery",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 8: invalid Content-Type
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::POST,
                "/api/products",
                "token-alice-123"
            );

        request.headers.set(
            "Content-Type",
            "text/plain"
        );

        request.body = "not JSON";

        request.headers.set(
            "Content-Length",
            std::to_string(request.body.size())
        );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-invalid-type"
            );

        print_response(
            "8. Unsupported content type",
            response
        );
    }

    // ------------------------------------------------------------------------
    // Scenario 9: invalid bearer token
    // ------------------------------------------------------------------------

    {
        HTTPRequest request =
            make_request(
                HTTPMethod::GET,
                "/api/products",
                "invalid-token"
            );

        HTTPResponse response =
            gateway.handle(
                request,
                "client-invalid-token"
            );

        print_response(
            "9. Invalid authentication",
            response
        );
    }
}


// ============================================================================
// 16. RATE LIMITING TEST
// ============================================================================

void demonstrate_rate_limiting() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "RATE LIMITING TEST"
        << "\n"
        << std::string(78, '=')
        << "\n";

    RateLimiter limiter(
        3,
        std::chrono::seconds(60)
    );

    const auto timestamp =
        Clock::time_point{};

    for (int requestNumber = 1;
         requestNumber <= 5;
         ++requestNumber) {

        const bool allowed =
            limiter.allow(
                "192.0.2.10",
                timestamp
            );

        std::cout
            << "Request "
            << requestNumber
            << ": "
            << (allowed ? "allowed" : "429 Too Many Requests")
            << '\n';
    }
}


// ============================================================================
// 17. HTTP MESSAGE PARSING TEST
// ============================================================================

void demonstrate_parser() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "HTTP PARSER TEST"
        << "\n"
        << std::string(78, '=')
        << "\n";

    const std::string raw =
        "POST /api/products HTTP/1.1\r\n"
        "Host: api.example.test\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: 17\r\n"
        "\r\n"
        "{\"name\":\"Keyboard\"}";

    try {
        HTTPRequest request =
            HTTPParser::parse(raw);

        std::cout
            << "Method: "
            << method_to_string(request.method)
            << '\n';

        std::cout
            << "Target: "
            << request.target
            << '\n';

        std::cout
            << "Version: "
            << request.version
            << '\n';

        std::cout
            << "Body bytes: "
            << request.body.size()
            << '\n';

    } catch (const std::exception& error) {
        std::cout
            << "Parser error: "
            << error.what()
            << '\n';
    }
}


// ============================================================================
// 18. SECURITY EDGE CASES
// ============================================================================

void demonstrate_security_edge_cases() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "SECURITY EDGE CASES"
        << "\n"
        << std::string(78, '=')
        << "\n";

    // Invalid header name.
    try {
        Headers headers;

        headers.set(
            "Bad Header",
            "value"
        );

        std::cout
            << "ERROR: invalid header was accepted.\n";
    } catch (const std::exception& error) {
        std::cout
            << "Invalid header rejected: "
            << error.what()
            << '\n';
    }

    // Header injection attempt.
    try {
        Headers headers;

        headers.set(
            "X-Test",
            "safe\r\nInjected: yes"
        );

        std::cout
            << "ERROR: header injection was accepted.\n";
    } catch (const std::exception& error) {
        std::cout
            << "Header injection rejected: "
            << error.what()
            << '\n';
    }

    // Invalid Content-Length.
    try {
        const std::string raw =
            "POST / HTTP/1.1\r\n"
            "Host: example.test\r\n"
            "Content-Length: abc\r\n"
            "\r\n"
            "hello";

        HTTPParser::parse(raw);

        std::cout
            << "ERROR: invalid Content-Length was accepted.\n";
    } catch (const std::exception& error) {
        std::cout
            << "Invalid Content-Length rejected: "
            << error.what()
            << '\n';
    }
}


// ============================================================================
// 19. COMPLEXITY AND PERFORMANCE
// ============================================================================

void explain_complexity() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "PERFORMANCE AND COMPLEXITY"
        << "\n"
        << std::string(78, '=')
        << "\n";

    std::cout
        << "Header lookup: O(log n) in the std::map used here.\n"
        << "Token lookup: average O(1) using std::unordered_map.\n"
        << "Resource lookup: average O(1) using std::unordered_map.\n"
        << "Range extraction: O(k) for the selected representation bytes.\n"
        << "Rate limiter cleanup: O(r) for retained timestamps per client.\n"
        << "Request parsing: O(message size).\n";

    std::cout
        << "\nProduction servers must also account for connection pooling, "
        << "TLS handshakes, memory allocation, thread scheduling, queueing, "
        << "compression, serialization, database latency, network latency, "
        << "and backpressure.\n";
}


// ============================================================================
// 20. HTTP/HTTPS ARCHITECTURE EXPLANATION
// ============================================================================

void explain_protocol_stack() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "HTTP AND HTTPS PROTOCOL STACK"
        << "\n"
        << std::string(78, '=')
        << "\n";

    const std::vector<std::string> layers = {
        "Application: HTTP semantics",
        "Security: TLS for HTTPS",
        "Transport: TCP for HTTP/1.1 and HTTP/2; QUIC for HTTP/3",
        "Network: IP",
        "Link/physical network"
    };

    for (std::size_t i = 0; i < layers.size(); ++i) {
        std::cout
            << i + 1
            << ". "
            << layers[i]
            << '\n';
    }

    std::cout
        << "\nHTTPS is not a separate application protocol replacing HTTP "
        << "semantics. It is HTTP protected by TLS.\n";
}


// ============================================================================
// 21. TLS SECURITY MODEL
// ============================================================================

void explain_tls_model() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "TLS SECURITY MODEL"
        << "\n"
        << std::string(78, '=')
        << "\n";

    const std::vector<std::pair<std::string, std::string>> concepts = {
        {
            "Confidentiality",
            "Encrypt application traffic against passive network observation."
        },
        {
            "Integrity",
            "Detect unauthorized alteration of protected records."
        },
        {
            "Authentication",
            "Use certificates and trust validation to authenticate a server."
        },
        {
            "Key exchange",
            "Establish session secrets for symmetric protection."
        },
        {
            "Certificate chain",
            "Connect the server certificate to a trusted certificate authority."
        },
        {
            "Hostname verification",
            "Confirm the certificate identity matches the requested host."
        },
        {
            "Forward secrecy",
            "Ephemeral key exchange can protect past sessions from later key compromise."
        }
    };

    for (const auto& [name, description] : concepts) {
        std::cout
            << std::left
            << std::setw(24)
            << name
            << ": "
            << description
            << '\n';
    }
}


// ============================================================================
// 22. HTTP/1.1, HTTP/2, HTTP/3
// ============================================================================

void compare_http_versions() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "HTTP VERSION COMPARISON"
        << "\n"
        << std::string(78, '=')
        << "\n";

    struct VersionInfo {
        std::string version;
        std::string framing;
        std::string transport;
        std::string characteristic;
    };

    const std::vector<VersionInfo> versions = {
        {
            "HTTP/1.1",
            "Textual",
            "TCP",
            "Persistent connections"
        },
        {
            "HTTP/2",
            "Binary frames",
            "TCP",
            "Multiplexed streams"
        },
        {
            "HTTP/3",
            "Binary frames",
            "QUIC/UDP",
            "Multiplexed QUIC streams"
        }
    };

    for (const auto& item : versions) {
        std::cout
            << item.version
            << " | "
            << item.framing
            << " | "
            << item.transport
            << " | "
            << item.characteristic
            << '\n';
    }
}


// ============================================================================
// 23. TEST SUITE
// ============================================================================

void run_tests() {
    std::cout
        << "\n"
        << std::string(78, '=')
        << "\n"
        << "TEST SUITE"
        << "\n"
        << std::string(78, '=')
        << "\n";

    {
        const std::string raw =
            "GET /api/status HTTP/1.1\r\n"
            "Host: api.example.test\r\n"
            "\r\n";

        const HTTPRequest request =
            HTTPParser::parse(raw);

        if (request.method != HTTPMethod::GET) {
            throw std::runtime_error(
                "GET parser test failed."
            );
        }

        if (request.target != "/api/status") {
            throw std::runtime_error(
                "Target parser test failed."
            );
        }
    }

    {
        const auto range =
            parse_range(
                "bytes=2-5",
                10
            );

        if (!range
            || range->start != 2
            || range->end != 5) {

            throw std::runtime_error(
                "Range parser test failed."
            );
        }
    }

    {
        if (!is_idempotent(HTTPMethod::PUT)) {
            throw std::runtime_error(
                "PUT idempotency test failed."
            );
        }

        if (is_idempotent(HTTPMethod::POST)) {
            throw std::runtime_error(
                "POST idempotency test failed."
            );
        }
    }

    {
        Headers headers;

        headers.set(
            "Content-Type",
            "application/json"
        );

        if (!headers.contains("content-type")) {
            throw std::runtime_error(
                "Case-insensitive header lookup failed."
            );
        }
    }

    {
        TokenStore store;

        store.add(
            "secret-token",
            "alice"
        );

        const auto user =
            store.authenticate(
                "Bearer secret-token"
            );

        if (!user || *user != "alice") {
            throw std::runtime_error(
                "Token authentication test failed."
            );
        }

        if (store.authenticate("Bearer wrong")) {
            throw std::runtime_error(
                "Invalid token was accepted."
            );
        }
    }

    {
        TLSConfiguration tls;

        tls.validate();

        tls.certificateVerification = false;

        try {
            tls.validate();

            throw std::runtime_error(
                "Invalid TLS configuration was accepted."
            );
        } catch (const std::runtime_error& error) {
            const std::string message =
                error.what();

            if (message.find("certificate") == std::string::npos) {
                throw;
            }
        }
    }

    std::cout
        << "All tests passed.\n";
}


// ============================================================================
// 24. MAIN
// ============================================================================

} // namespace http_learning


int main() {
    using namespace http_learning;

    try {
        explain_protocol_stack();
        explain_tls_model();
        compare_http_versions();

        demonstrate_parser();
        demonstrate_security_edge_cases();

        run_gateway_case_study();
        demonstrate_rate_limiting();

        explain_complexity();

        run_tests();

        std::cout
            << "\n"
            << std::string(78, '=')
            << "\n"
            << "CASE STUDY COMPLETE"
            << "\n"
            << std::string(78, '=')
            << "\n";

        std::cout
            << "The program modeled a secure API gateway using HTTP semantics "
            << "and a TLS security configuration model.\n";

        std::cout
            << "A real deployment would use a mature HTTP/TLS stack, real "
            << "certificate validation, production authentication, structured "
            << "JSON parsing, observability, and hardened infrastructure.\n";

        return 0;

    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }
}
