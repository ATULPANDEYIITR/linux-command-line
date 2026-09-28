# HTTP and HTTPS

## 1. Topic Introduction

HTTP, or Hypertext Transfer Protocol, is an application-layer protocol used to exchange information between clients and servers. A web browser, mobile application, command-line client, or backend service can act as an HTTP client. A web server, API server, reverse proxy, CDN, or gateway can receive HTTP requests and produce HTTP responses.

HTTPS means HTTP carried through Transport Layer Security, usually abbreviated TLS. HTTP defines application-level concepts such as methods, status codes, headers, requests, responses, cookies, caching, and content negotiation. TLS protects the connection carrying those HTTP messages.

The central distinction is:

- HTTP defines how application messages are structured and interpreted.
- TLS provides cryptographic protection for communication.
- HTTPS combines HTTP semantics with TLS protection.

The three implementations in this study use different perspectives:

- Python focuses on protocol mechanics, message construction and parsing, caching, cookies, ranges, TLS inspection, and local servers.
- JavaScript focuses on modern web application communication, Fetch, asynchronous programming, browser-origin behavior, CORS, Node.js HTTP/HTTPS APIs, and request lifecycle handling.
- C++ presents an industry-style API gateway that combines parsing, authentication, authorization, rate limiting, caching validators, range handling, request validation, and TLS configuration concepts.

---

## 2. Fundamental Terminology

### Client

A client initiates communication.

Examples include:

- Web browser
- Mobile application
- JavaScript application
- Python API client
- Command-line HTTP client
- Another backend service

### Server

A server receives requests and produces responses.

Examples include:

- Web server
- REST API
- Reverse proxy
- Load balancer
- CDN
- Application gateway

### Resource

A resource is an identifiable piece of information or application capability. Examples include:

- `/users/42`
- `/api/products`
- `/images/logo.png`
- `/api/orders/123`

### Request

A request is sent by a client to a server. An HTTP request can contain:

1. Request method
2. Request target
3. HTTP version
4. Headers
5. Optional body

### Response

A response is sent by a server to a client. It contains:

1. HTTP version
2. Status code
3. Reason phrase in HTTP/1.x representations
4. Headers
5. Optional body

### Header

Headers carry metadata.

Examples:

- `Host`
- `Accept`
- `Content-Type`
- `Content-Length`
- `Authorization`
- `Cookie`
- `Cache-Control`
- `ETag`
- `Location`
- `Range`
- `User-Agent`

### Body

The body carries representation or request data.

Common examples include:

- HTML
- JSON
- XML
- Plain text
- Images
- Audio
- Video
- Binary files
- Form data

---

## 3. URL Structure

A URL such as:

`https://api.example.com:8443/users/42?sort=name&active=true#profile`

contains several components.

| Component | Example |
|---|---|
| Scheme | `https` |
| Host | `api.example.com` |
| Port | `8443` |
| Path | `/users/42` |
| Query | `sort=name&active=true` |
| Fragment | `profile` |

The Python implementation uses `urllib.parse.urlsplit()` to expose these components.

The JavaScript implementation uses the standard `URL` class and `URLSearchParams`.

A fragment has an important distinction: it is generally interpreted by the user agent and is not included in the HTTP request target sent to the server.

---

## 4. HTTP Methods

The main methods demonstrated are:

| Method | Typical purpose |
|---|---|
| GET | Retrieve a representation |
| HEAD | Retrieve metadata without the response body |
| POST | Submit data or trigger a server-side operation |
| PUT | Create or replace a representation |
| PATCH | Partially modify a representation |
| DELETE | Request deletion |
| OPTIONS | Discover supported communication options |
| CONNECT | Establish a tunnel |

### Safe methods

A safe method is defined in terms of its intended semantics as read-only from the client's perspective.

GET and HEAD are examples.

Safe does not mean that processing the request can never consume server resources. A GET request can cause logging, metrics, cache activity, or other internal work.

### Idempotent methods

An operation is idempotent when multiple identical requests have the same intended server-side effect as a single request.

GET, HEAD, PUT, DELETE, and OPTIONS have idempotent semantics.

POST is not generally idempotent.

PATCH depends on the operation.

Idempotency is important for retry systems. A client should not blindly retry every failed request because repeating an operation can produce duplicate side effects.

An application can also implement an idempotency-key mechanism for operations that need safe retry semantics. The server must implement the semantics; the existence of an idempotency key alone does not make a request idempotent.

---

## 5. HTTP Request Structure

A simplified HTTP/1.1 request has the conceptual form:

`METHOD target HTTP/version`

followed by headers, a blank line, and an optional body.

For example:

`GET /api/users?page=2 HTTP/1.1`

followed by headers such as:

`Host: example.com`

`Accept: application/json`

The Python program creates this structure through the `HTTPRequest` class.

The C++ program represents it through the `HTTPRequest` structure and `HTTPParser`.

The JavaScript implementation demonstrates the equivalent structure using strings and the `Headers` API.

HTTP/2 and HTTP/3 use binary framing rather than transmitting HTTP/1.1's textual representation directly. Their application semantics still include methods, headers, status codes, and bodies.

---

## 6. HTTP Response Structure

A response includes a status code and optional body.

Typical examples:

`HTTP/1.1 200 OK`

`HTTP/1.1 404 Not Found`

`HTTP/1.1 500 Internal Server Error`

Important response categories are:

| Category | Meaning |
|---|---|
| 1xx | Informational |
| 2xx | Successful |
| 3xx | Redirection |
| 4xx | Client error |
| 5xx | Server error |

### Important status codes

| Code | Meaning |
|---:|---|
| 200 | OK |
| 201 | Created |
| 202 | Accepted |
| 204 | No Content |
| 206 | Partial Content |
| 301 | Moved Permanently |
| 302 | Found |
| 303 | See Other |
| 304 | Not Modified |
| 307 | Temporary Redirect |
| 308 | Permanent Redirect |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 405 | Method Not Allowed |
| 409 | Conflict |
| 412 | Precondition Failed |
| 413 | Content Too Large |
| 415 | Unsupported Media Type |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
| 502 | Bad Gateway |
| 503 | Service Unavailable |
| 504 | Gateway Timeout |

A 401 response generally indicates that authentication is required or that supplied authentication credentials were not accepted. A 403 response indicates that the server understood the request but is refusing the operation.

---

## 7. Content Types

`Content-Type` describes the media type of the message body.

Examples include:

- `application/json`
- `text/html`
- `text/plain`
- `application/pdf`
- `image/png`

For JSON APIs, a common value is:

`application/json`

Character encoding can also be specified for applicable media types, such as:

`text/html; charset=utf-8`

The Python implementation uses `json.dumps()` and explicit UTF-8 encoding.

The JavaScript implementation uses `JSON.stringify()` and `JSON.parse()`.

The C++ gateway requires JSON content for its demonstrated POST operation and performs a conservative structural check because the C++ standard library does not include a JSON parser.

---

## 8. Content-Length

`Content-Length` describes the size of the message body in bytes when used for HTTP message framing.

The Python implementation validates that a Content-Length value consists of decimal digits.

The C++ parser compares a declared Content-Length against the actual body size.

The JavaScript Node.js server uses byte lengths when constructing responses.

Byte length matters because character count and byte count can differ for UTF-8 text. For example, a Unicode character may require multiple UTF-8 bytes.

---

## 9. Transfer Encoding and Chunked Messages

HTTP/1.1 can use chunked transfer encoding when a sender does not need to know the complete body length before transmission.

The Python implementation contains:

- `encode_chunked()`
- `decode_chunked()`

The encoded representation consists of chunks containing:

1. Chunk size in hexadecimal
2. CRLF
3. Chunk data
4. CRLF

A zero-length final chunk marks the end.

Chunked encoding is distinct from content compression. Compression changes representation size or encoding, while chunked transfer encoding concerns HTTP/1.1 message framing.

---

## 10. HTTP Range Requests

A client can request only part of a representation using a Range header.

Example:

`Range: bytes=5-10`

A successful partial response commonly uses:

`206 Partial Content`

with a `Content-Range` header.

The Python implementation provides `apply_byte_range()`.

The JavaScript implementation provides `applyByteRange()`.

The C++ gateway supports a single byte range.

Range requests are useful for:

- Large downloads
- Resumable downloads
- Media seeking
- Partial file retrieval
- Bandwidth optimization

Production implementations need to handle more cases, including unsatisfiable ranges, multiple ranges, conditional range requests, compression, and representation identity.

---

## 11. URL Encoding

Reserved URL characters may need percent encoding.

The Python implementation demonstrates:

- `urllib.parse.quote()`
- `urllib.parse.unquote()`
- `urllib.parse.urlencode()`

The JavaScript implementation uses `URLSearchParams`.

For example, spaces and special characters can be represented safely within a query string through appropriate encoding.

URL encoding is not encryption.

---

## 12. Cookies

Cookies allow servers and clients to maintain state across HTTP requests.

A server can send:

`Set-Cookie: session_id=abc123; Path=/; Secure; HttpOnly; SameSite=Lax`

The client may later send:

`Cookie: session_id=abc123`

### Important cookie attributes

#### Secure

A Secure cookie is intended to be sent only over secure connections.

#### HttpOnly

HttpOnly prevents browser JavaScript from reading the cookie through `document.cookie`.

This helps reduce the ability of injected client-side scripts to directly access session cookies.

#### SameSite

SameSite controls when browsers attach cookies in cross-site contexts. Values include:

- `Strict`
- `Lax`
- `None`

`SameSite=None` has additional requirements in modern browsers, including Secure.

#### Path

Restricts the URL paths for which a cookie is sent.

#### Domain

Controls the domain scope under the cookie rules.

The Python implementation provides a deliberately simplified cookie jar for educational purposes.

The JavaScript implementation demonstrates cookie parsing and explains why HttpOnly cannot be created through ordinary browser JavaScript.

A production cookie implementation should rely on a mature browser or server framework rather than the simplified educational classes in these files.

---

## 13. HTTP Authentication

HTTP applications can use several authentication mechanisms.

Examples include:

- Basic authentication
- Bearer tokens
- Session cookies
- Mutual TLS
- Signed requests
- Application-specific authentication protocols

### Basic authentication

Basic authentication represents credentials using Base64.

Base64 is encoding, not encryption.

Therefore:

`Authorization: Basic ...`

must normally be transported through HTTPS when credentials require protection in transit.

The Python and JavaScript implementations demonstrate Base64 encoding without implying that it provides cryptographic protection.

---

## 14. Bearer Tokens

The C++ case study uses a simplified bearer-token store.

A request can contain:

`Authorization: Bearer token-alice-123`

The gateway looks up the token and associates it with a user.

A real authentication system must address:

- Token generation
- Token storage
- Token expiration
- Revocation
- Audience
- Issuer
- Scope
- Key management
- Leakage prevention
- Logging
- Rotation
- Authorization

Tokens should not be exposed unnecessarily in URLs because URLs can appear in logs, browser history, monitoring systems, and other infrastructure.

---

## 15. Origins and the Same-Origin Policy

A browser origin consists of:

- Scheme
- Host
- Port

For example:

`https://app.example.com`

and

`https://api.example.com`

are different origins because their hosts differ.

Also:

`http://example.com`

and

`https://example.com`

are different origins because their schemes differ.

The JavaScript implementation compares origins with the `URL.origin` property.

The same-origin policy is an important browser security mechanism. It restricts many forms of cross-origin interaction unless an appropriate browser mechanism permits them.

---

## 16. CORS

CORS means Cross-Origin Resource Sharing.

Servers can provide response headers such as:

`Access-Control-Allow-Origin`

`Access-Control-Allow-Methods`

`Access-Control-Allow-Headers`

`Access-Control-Allow-Credentials`

CORS is particularly important for browser-based JavaScript applications.

A server-to-server Node.js request is not automatically subject to browser same-origin enforcement.

CORS configuration must be explicit. Arbitrarily reflecting an incoming Origin value can create security problems, particularly when credentials are involved.

CORS is not an authentication system.

CORS does not make an insecure API secure.

It controls browser cross-origin behavior.

---

## 17. Fetch API

The JavaScript implementation uses the Fetch API.

A basic operation has the conceptual structure:

`fetch(url, options)`

Fetch returns a Promise.

A response contains:

- `status`
- `statusText`
- `headers`
- `body`
- `ok`

An important behavior is that ordinary HTTP error statuses such as 404 and 500 do not automatically cause Fetch's Promise to reject.

Application code therefore needs to check:

`response.ok`

or inspect:

`response.status`

Network-level failures and aborted requests are handled differently.

---

## 18. Asynchronous JavaScript

HTTP operations are inherently suitable for asynchronous programming.

The JavaScript implementation uses:

- Promises
- `async`
- `await`
- `AbortController`
- Event listeners in Node.js

Asynchronous programming prevents an application from unnecessarily blocking while waiting for network I/O.

A production application should also consider:

- Timeouts
- Cancellation
- Retries
- Backoff
- Concurrency limits
- Connection reuse
- Error classification

---

## 19. Timeouts

A request without an appropriate timeout can wait indefinitely or consume resources for too long.

The JavaScript implementation uses `AbortController` to cancel a Fetch operation.

The Python examples configure socket or HTTP connection timeouts.

The Node.js examples configure request-related timeout settings.

Timeouts should be selected according to the actual operation. A very short timeout can cause unnecessary failures, while an excessively long timeout can exhaust resources.

---

## 20. Retries

Retries can recover from temporary failures.

The JavaScript implementation provides `retryOperation()` with exponential backoff and jitter.

The Python implementation provides `RetryPolicy`.

The C++ case study discusses the same design principle.

Retries should not be applied blindly.

Consider:

- Is the failure temporary?
- Is the request idempotent?
- Can the operation produce duplicate side effects?
- Does the server support idempotency keys?
- Is the failure caused by invalid input?
- Is the service overloaded?
- Is retrying likely to increase the overload?

A retry system should distinguish transient failures from permanent failures.

---

## 21. HTTP Caching

Caching can reduce:

- Network traffic
- Server workload
- Latency
- Repeated computation

Important cache-related headers include:

- `Cache-Control`
- `ETag`
- `Last-Modified`
- `Expires`
- `If-None-Match`
- `If-Modified-Since`
- `Vary`

The Python implementation contains an `HTTPCache`.

The JavaScript implementation contains `SimpleCache`.

The C++ gateway implements ETag-style conditional requests.

---

## 22. ETags

An ETag identifies a particular representation.

Example:

`ETag: "abc123"`

A client can send:

`If-None-Match: "abc123"`

If the server determines that the representation has not changed, it can return:

`304 Not Modified`

without retransmitting the representation.

The Python implementation creates an ETag from SHA-256.

The JavaScript implementation creates an ETag from a SHA-256 digest.

The C++ implementation uses `std::hash` as an educational deterministic identifier. That implementation is intentionally not presented as a cryptographic hash.

Production ETags should use a suitable representation version or robust digest mechanism according to application requirements.

---

## 23. Cache-Control

Examples include:

`Cache-Control: no-store`

and:

`Cache-Control: private, max-age=60`

`no-store` indicates that the response should not be stored by caches according to the directive.

`private` indicates that a response is intended for a private cache rather than a shared cache.

`max-age` specifies a freshness lifetime in seconds.

Caching sensitive responses requires careful consideration of:

- User identity
- Authorization
- Shared caches
- Response variation
- Personal data
- Invalidation
- Cache poisoning

---

## 24. Redirects

Important redirect statuses include:

- 301
- 302
- 303
- 307
- 308

307 and 308 are particularly significant because their semantics preserve the request method.

Redirect handling is security-sensitive.

A client should consider:

- Destination validation
- Cross-origin transitions
- Credential forwarding
- Sensitive headers
- Authentication state
- Redirect loops

The JavaScript Fetch implementation allows applications to control redirect behavior through appropriate options.

---

## 25. HTTP Headers and Security

Headers are an important part of application behavior.

The JavaScript implementation demonstrates header construction and validation.

The C++ implementation rejects:

- Invalid header names
- CR/LF in header values

This prevents a class of HTTP message construction problems related to header injection.

Production applications should rely on mature HTTP libraries for complete parsing and serialization because HTTP message grammar and framing have many subtle cases.

---

## 26. Request Smuggling and Message Framing

HTTP request smuggling can occur when intermediaries disagree about where an HTTP request begins or ends.

Potentially dangerous interactions can involve:

- Content-Length
- Transfer-Encoding
- Proxies
- Reverse proxies
- Load balancers
- Origin servers
- Multiple HTTP implementations

The key architectural principle is that every component involved in parsing an HTTP message must interpret framing consistently.

The Python program demonstrates basic Content-Length validation.

The C++ parser validates the body length against Content-Length.

These are educational examples, not complete request-smuggling defenses.

Production systems should use hardened HTTP implementations and carefully test proxy and origin-server combinations.

---

## 27. HTTP/1.1

HTTP/1.1 commonly uses a textual representation for messages.

It supports:

- Persistent connections
- Request methods
- Headers
- Chunked transfer encoding
- Range requests
- Conditional requests
- Caching
- Host-based virtual hosting

The Python program implements simplified HTTP/1.x serialization and parsing.

The C++ program also models HTTP/1.1 request and response structures.

---

## 28. HTTP/2

HTTP/2 uses binary framing.

Important characteristics include:

- Multiplexed streams
- Header compression
- Binary frames
- Stream identifiers
- Concurrent request/response streams over a connection

HTTP/2 changes transport efficiency and framing but retains fundamental HTTP concepts such as methods, status codes, headers, and representations.

---

## 29. HTTP/3

HTTP/3 uses QUIC rather than TCP.

QUIC is built on UDP and provides transport features needed for reliable multiplexed communication.

HTTP/3 can reduce some transport-level head-of-line blocking effects compared with TCP-based multiplexing.

The Python, JavaScript, and C++ implementations explain HTTP/3 conceptually rather than implementing QUIC.

Implementing HTTP/3 and TLS 1.3 from scratch would not be appropriate for a standalone educational standard-library program.

---

## 30. TLS Fundamentals

TLS provides several important properties.

### Confidentiality

Encryption prevents passive network observers from reading protected application traffic.

### Integrity

Authenticated cryptographic protection allows detection of unauthorized modification.

### Authentication

Certificates allow a client to authenticate the server's identity when certificate validation succeeds.

### Key exchange

The TLS handshake establishes cryptographic material used for the protected session.

### Forward secrecy

Modern ephemeral key-exchange mechanisms can provide protection against certain forms of retrospective decryption after compromise of long-term credentials.

---

## 31. Certificates

A TLS certificate binds an identity to a public key through a digital signature.

A certificate can contain:

- Subject
- Subject Alternative Name
- Public key
- Validity period
- Issuer
- Key usage information
- Extended key usage
- Signature

Modern hostname validation relies primarily on the Subject Alternative Name extension.

A certificate chain can contain:

1. Server certificate
2. Intermediate CA certificates
3. Trusted root CA

The client validates the chain according to its trust configuration.

---

## 32. Certificate Authorities

A Certificate Authority, or CA, signs certificates or intermediate certificates according to its trust model.

The browser or operating system maintains a trust store containing trusted roots.

A valid TLS connection normally requires more than simply having a certificate. The client needs to validate:

- Certificate chain
- Validity period
- Hostname
- Appropriate key usage
- Signature relationships
- Trust configuration
- Other applicable certificate constraints

---

## 33. Hostname Verification

A certificate for:

`api.example.com`

should not automatically be considered valid for:

`malicious.example.net`

Hostname verification is a fundamental part of server authentication.

The Python implementation demonstrates hostname matching with `ssl.match_hostname()`.

The Python HTTPS client uses `ssl.create_default_context()`, which enables ordinary certificate validation and hostname checking.

The JavaScript Node.js HTTPS client defaults to certificate verification through the Node.js TLS stack.

---

## 34. TLS Version and Configuration

Modern deployments should use contemporary TLS configurations supported by their infrastructure and clients.

The Python program displays the default TLS context configuration.

The Node.js HTTPS server explicitly sets a minimum TLS version of TLS 1.2 in the example.

The C++ program models:

- Minimum TLS version
- Certificate verification
- Hostname verification
- Trusted-chain verification

The C++ standard library itself does not provide a complete TLS implementation, so these fields model the security requirements rather than performing TLS negotiation.

---

## 35. Why HTTPS Matters

Without TLS, HTTP traffic can be observed or modified by network components that can intercept the communication path.

HTTPS protects the connection against common passive and active network threats when TLS is correctly configured and the endpoint itself is trustworthy.

HTTPS does not protect against every application vulnerability.

For example, HTTPS does not automatically prevent:

- SQL injection
- Broken authorization
- Cross-site scripting
- Unsafe deserialization
- Weak passwords
- Business-logic flaws
- Server-side request forgery
- Vulnerable dependencies
- Compromised endpoints

TLS protects communication. Application security remains the responsibility of the complete system.

---

## 36. HTTP vs HTTPS

| Property | HTTP | HTTPS |
|---|---|---|
| Application semantics | HTTP | HTTP |
| Encryption | Not provided by HTTP | TLS provides protected transport |
| Integrity protection | Not provided cryptographically by HTTP | Provided by TLS |
| Server authentication | Not provided by HTTP itself | Normally provided through TLS certificates |
| Common port | 80 | 443 |
| Certificate management | Not required by HTTP | Required for ordinary authenticated TLS deployment |
| Browser security context | Less protected | Secure context for applicable browser capabilities |

HTTPS is therefore best understood as protected HTTP communication rather than a completely unrelated protocol.

---

## 37. Python Implementation

The Python file is organized as a standalone study program.

### Protocol structures

The `HTTPRequest` class models:

- Method
- Target
- Version
- Headers
- Body

The `HTTPResponse` class models corresponding response fields.

### Parsing

`parse_http_request()` demonstrates how an HTTP/1.x message can be separated into headers and body.

The parser checks the request line and header syntax.

### Cookies

`SimpleCookieJar` demonstrates basic cookie storage and Set-Cookie parsing.

It is intentionally simplified and should not be treated as a complete browser cookie implementation.

### Caching

`HTTPCache` stores representations with generated ETags and timestamps.

### Range requests

`apply_byte_range()` demonstrates partial byte retrieval.

### Chunked encoding

`encode_chunked()` and `decode_chunked()` demonstrate HTTP/1.1 chunked transfer framing.

### TLS

The Python program uses the standard `ssl` module.

`inspect_certificate()` retrieves and displays information about a remote TLS certificate.

`demonstrate_ssl_context_configuration()` shows the properties of a secure default context.

### HTTP and HTTPS clients

The program uses:

- `http.client.HTTPConnection`
- `http.client.HTTPSConnection`

This demonstrates that the application-level request structure remains similar while HTTPS adds TLS protection.

### Local server

`LearningHTTPHandler` demonstrates a small HTTP API.

It supports:

- GET `/`
- GET `/health`
- POST request processing
- Content-Length validation
- Request-size limits
- JSON responses
- Security headers

---

## 38. JavaScript Implementation

The JavaScript implementation emphasizes application and browser behavior.

### URL

The `URL` class exposes:

- `protocol`
- `hostname`
- `port`
- `pathname`
- `search`
- `hash`
- `origin`

`URLSearchParams` handles query parameters.

### Fetch

`fetchExample()` demonstrates asynchronous HTTP communication.

It explicitly checks `response.ok`, which is important because a 404 or 500 response is still a valid HTTP response from Fetch's perspective.

### POST JSON

`postJSON()` demonstrates:

- POST
- JSON serialization
- Content-Type
- Accept
- Response validation

### Timeout

`fetchWithTimeout()` uses `AbortController`.

### Retry

`retryOperation()` uses asynchronous exponential backoff with jitter.

### Cookies

The program explains the distinction between browser-controlled HttpOnly cookies and JavaScript-accessible cookies.

### CORS

The implementation shows representative CORS headers and explains the browser security model.

### Node.js server

`createLearningHTTPServer()` creates a real Node.js HTTP server.

It demonstrates:

- Request routing
- JSON responses
- Request body collection
- Request-size limits
- Error handling
- Timeout settings
- Security headers

### Node.js HTTPS server

`createLearningHTTPSServer()` reads a certificate and private key and creates a TLS-protected Node.js server.

The implementation intentionally does not generate a certificate automatically.

---

## 39. C++ API Gateway Case Study

The C++ program models an API gateway rather than merely printing isolated protocol syntax.

The system receives HTTP requests and processes them through multiple controls.

### Major components

The case study contains:

- `Headers`
- `HTTPRequest`
- `HTTPResponse`
- `HTTPParser`
- `TokenStore`
- `RateLimiter`
- `APIGateway`
- TLS configuration model
- ETag generation
- Range processing

### Request-processing architecture

The gateway follows this general sequence:

1. Receive request.
2. Apply rate limiting.
3. Validate the HTTP method.
4. Enforce body-size limits.
5. Validate Content-Type for applicable operations.
6. Authenticate protected requests.
7. Route the operation.
8. Generate a response.
9. Attach appropriate response metadata.

This ordering demonstrates why security checks should happen before expensive application processing.

---

## 40. C++ Authentication

The `TokenStore` maps bearer tokens to users.

The example token:

`token-alice-123`

maps to:

`alice`

The implementation is deliberately simplified.

A production authentication service would need stronger protections for:

- Token storage
- Token lifecycle
- Expiration
- Revocation
- Secret management
- Key rotation
- Scope
- Audience
- Issuer
- Audit logging

---

## 41. C++ Rate Limiting

`RateLimiter` uses a fixed-window model.

The demonstration allows a fixed number of requests from a client within a time window.

Once the limit is reached, the gateway returns:

`429 Too Many Requests`

Rate limiting protects infrastructure from uncontrolled request volume but has design trade-offs.

Possible production approaches include:

- Fixed windows
- Sliding windows
- Token buckets
- Leaky buckets
- Distributed rate limits
- Per-user limits
- Per-IP limits
- Endpoint-specific limits

Distributed systems may need shared state so multiple gateway instances apply consistent limits.

---

## 42. C++ Conditional Requests

The C++ gateway generates an ETag for a resource.

A client can send:

`If-None-Match`

If the ETag matches, the gateway returns:

`304 Not Modified`

This demonstrates how conditional requests can reduce response transfer.

---

## 43. C++ Range Handling

The gateway parses:

`Range: bytes=0-9`

and can return:

`206 Partial Content`

with:

`Content-Range`

The implementation supports a single range for educational clarity.

A production implementation would need to address more complete HTTP range semantics.

---

## 44. C++ Request Validation

The gateway limits request body size.

The demonstration uses a maximum of:

`1,000,000` bytes.

Oversized requests produce:

`413 Content Too Large`

The program also checks Content-Type for POST, PUT, and PATCH operations.

This demonstrates a basic principle:

> Input should be constrained before expensive processing.

Request-size validation helps protect memory and CPU resources.

---

## 45. HTTP Error Handling

HTTP errors should be represented with appropriate status codes.

Examples:

- Invalid syntax → 400
- Missing authentication → 401
- Insufficient permission → 403
- Missing resource → 404
- Unsupported method → 405
- Unsupported media type → 415
- Request too large → 413
- Rate limit exceeded → 429
- Server failure → 500
- Upstream failure → 502
- Temporary service unavailability → 503

Applications should avoid returning `200 OK` for every condition because clients, caches, monitoring systems, and other infrastructure rely on meaningful status semantics.

---

## 46. Edge Cases

Important HTTP edge cases include:

### Empty body

Some requests legitimately have no body.

### Missing Content-Length

A server must understand how the body is framed rather than assuming one particular mechanism.

### Invalid Content-Length

Malformed framing should be rejected.

### Conflicting framing

Components must consistently interpret request framing.

### Invalid headers

Header names and values require validation.

### Oversized body

Servers should enforce request-size limits.

### Invalid ranges

A range beyond the representation can produce an unsatisfiable range response.

### Missing authentication

Protected resources should reject unauthenticated requests.

### Invalid authentication

Invalid credentials should not be treated as an authenticated identity.

### Redirects

Redirect destinations can cross security boundaries.

### Cache variation

A cached response can be incorrect if cache keys do not reflect relevant request dimensions.

---

## 47. Common Mistakes

### Mistake 1: Treating HTTPS as encryption only

HTTPS provides more than confidentiality. TLS also provides integrity protection and server authentication when validation succeeds.

### Mistake 2: Treating Base64 as encryption

Base64 can be reversed easily.

### Mistake 3: Disabling certificate verification

Disabling verification can allow a client to connect without authenticating the server.

### Mistake 4: Ignoring response status

A response body alone does not determine whether an operation succeeded.

### Mistake 5: Retrying every request

Retries can duplicate side effects.

### Mistake 6: Putting secrets in URLs

URLs can be logged or retained by multiple components.

### Mistake 7: Assuming CORS is authentication

CORS is a browser cross-origin mechanism, not an authorization system.

### Mistake 8: Assuming cookies are automatically safe

Cookie security depends on attributes, browser behavior, application design, and session management.

### Mistake 9: Writing a complete HTTP parser casually

HTTP parsing has subtle framing and interoperability issues. Production systems should use mature implementations.

### Mistake 10: Trusting client-side authorization

A browser interface can hide a button, but the server must enforce authorization.

---

## 48. Security Considerations

A secure HTTP/HTTPS application should consider:

- TLS certificate validation
- Hostname verification
- Strong TLS configuration
- Secure cookies
- Authentication
- Authorization
- Input validation
- Request-size limits
- Rate limiting
- Timeout configuration
- Safe redirects
- Security headers
- Logging without secrets
- Dependency security
- Error handling
- Request framing
- Cache isolation
- CSRF protections where applicable
- Content Security Policy where applicable
- Secure handling of tokens
- Secret rotation
- Monitoring and alerting

TLS should be treated as one security layer rather than the complete security architecture.

---

## 49. Security Headers Demonstrated

The implementations demonstrate several security-related headers.

### Strict-Transport-Security

HSTS tells compatible browsers to use HTTPS for a specified policy period.

### Content-Security-Policy

CSP can restrict which content sources a browser may load or execute.

### X-Content-Type-Options

`nosniff` helps prevent MIME-type sniffing behavior in applicable browser contexts.

### Referrer-Policy

Controls the amount of referrer information transmitted.

### Permissions-Policy

Can restrict selected browser capabilities.

These headers must be configured according to the application's actual requirements.

---

## 50. Reverse Proxies and Load Balancers

A production HTTP request may travel through:

1. Browser
2. DNS
3. CDN
4. Reverse proxy
5. Load balancer
6. Application server
7. Database or downstream service

TLS can terminate at several architectural points.

For example:

`Client → HTTPS → Load Balancer → HTTP/HTTPS → Application`

or:

`Client → HTTPS → CDN → HTTPS → Load Balancer → HTTPS → Application`

Security design must establish:

- Where TLS terminates
- Whether internal traffic is encrypted
- Which component validates the original client
- Which headers can be trusted
- Where authentication occurs
- Where authorization occurs
- How client IP information is forwarded
- How certificates are managed

Forwarded headers are security-sensitive because applications should not automatically trust arbitrary client-supplied values.

---

## 51. Performance Considerations

HTTP performance depends on multiple factors.

Important variables include:

- DNS resolution
- Network latency
- TCP connection establishment
- TLS handshake
- Connection reuse
- HTTP version
- Request size
- Response size
- Compression
- Server computation
- Database latency
- Queueing
- Congestion
- Client processing

### Connection reuse

Reusing connections can avoid repeated connection setup.

### HTTP/2

Multiplexing allows multiple streams over one connection.

### HTTP/3

QUIC provides multiplexed streams over a UDP-based transport.

### Compression

Compression can reduce transfer size but consumes CPU and can introduce security or performance considerations depending on the content.

### Caching

Caching can reduce repeated transfers and computation.

---

## 52. Complexity Considerations

The C++ implementation uses:

- `std::map` for headers
- `std::unordered_map` for resources and tokens
- `std::vector` for rate-limit timestamps
- Regular expressions for simple range parsing

Approximate complexity:

| Operation | Complexity |
|---|---|
| Header lookup | O(log n) |
| Token lookup | Average O(1) |
| Resource lookup | Average O(1) |
| Request parsing | O(message size) |
| Range extraction | O(selected bytes) |
| Rate-limit cleanup | O(retained timestamps) |

Real network-server performance is affected by many additional factors, including allocation, serialization, I/O scheduling, connection management, TLS processing, and downstream service latency.

---

## 53. Production Considerations

The educational implementations intentionally avoid pretending to be complete production frameworks.

Production HTTP/HTTPS systems need:

- Mature HTTP parsing
- Complete TLS implementation
- Certificate lifecycle management
- Robust authentication
- Authorization
- Structured logging
- Metrics
- Distributed tracing
- Connection pooling
- Request limits
- Timeouts
- Graceful shutdown
- Backpressure
- Memory controls
- Dependency management
- Configuration management
- Secret management
- Security testing
- Load testing
- Failure recovery

The C++ standard library alone is not a complete HTTP/TLS stack.

The simplified C++ TLS model demonstrates required security properties rather than implementing TLS itself.

---

## 54. Implementation Differences

### Python

Python is effective for demonstrating protocol concepts because its standard library provides:

- URL parsing
- HTTP clients
- HTTP servers
- TLS support
- JSON
- Hashing
- Socket functionality

Its concise syntax also makes protocol experiments easy to read.

### JavaScript

JavaScript is especially relevant to web communication because it directly interacts with browser networking APIs.

The implementation demonstrates:

- Fetch
- Promises
- async/await
- AbortController
- URL
- Headers
- Browser origins
- CORS
- Node.js HTTP
- Node.js HTTPS
- Node.js TLS

### C++

C++ is useful for modeling systems where performance, explicit data structures, memory behavior, concurrency architecture, and systems integration matter.

The case study therefore focuses on an API gateway architecture rather than browser-specific APIs.

---

## 55. Practical Applications

HTTP and HTTPS are foundational to:

- REST APIs
- Web applications
- Mobile APIs
- Microservices
- Cloud services
- CDN delivery
- Reverse proxies
- Authentication services
- Payment APIs
- Software update systems
- IoT communication
- Monitoring APIs
- Webhooks
- Developer platforms
- Enterprise integration
- Service-to-service communication

HTTPS is particularly important whenever confidentiality, integrity, or authenticated server communication is required.

---

## 56. Important Distinctions

### HTTP vs HTTPS

HTTP defines application communication. HTTPS protects HTTP with TLS.

### Authentication vs Authorization

Authentication answers:

"Who is this client?"

Authorization answers:

"What is this authenticated client allowed to do?"

### Encoding vs Encryption

Encoding changes representation.

Encryption uses cryptography to protect information.

Base64 is encoding.

TLS uses cryptographic protection.

### Cache validation vs authentication

ETags determine whether a representation changed.

Authentication determines identity.

They solve different problems.

### CORS vs authorization

CORS controls browser cross-origin behavior.

Authorization controls what a client is allowed to do.

### TLS vs application security

TLS protects communication.

Application security protects the system's logic, data, identity, authorization, and inputs.

---

## 57. Testing Demonstrated

All three implementations contain executable testing concepts.

The Python program uses assertions for:

- Request serialization
- Request parsing
- Chunked encoding
- Range handling
- Origin comparison
- Cookie behavior
- Cache behavior
- Rate limiting

The JavaScript program uses Node's `assert/strict`.

The C++ program implements a dedicated test suite for:

- HTTP parsing
- Range parsing
- Method semantics
- Header lookup
- Authentication
- TLS configuration
- Invalid input handling

Testing protocol code is important because small parsing differences can create interoperability or security problems.

---

## 58. Debugging HTTP Communication

When debugging an HTTP problem, inspect:

1. URL
2. HTTP method
3. Request target
4. Request headers
5. Request body
6. Status code
7. Response headers
8. Response body
9. Redirect behavior
10. Cookies
11. Cache state
12. Authentication
13. TLS certificate
14. TLS hostname
15. Proxy or load-balancer behavior
16. Server logs
17. Client logs
18. Timing and timeout information

For HTTPS problems, distinguish certificate validation failures from application-level HTTP failures.

A successful TLS handshake does not imply that the application returned a successful HTTP response.

---

## 59. Learning Through the Three Programs

The Python implementation establishes the protocol foundation.

The JavaScript implementation demonstrates how those concepts appear in modern application development and browser environments.

The C++ case study combines the concepts into a gateway architecture where multiple concerns interact:

- Protocol parsing
- Security
- Authentication
- Rate limiting
- Caching
- Conditional requests
- Range handling
- Validation
- Error responses
- TLS configuration
- Performance considerations

Together, the implementations demonstrate HTTP and HTTPS as both communication protocols and components of a larger distributed-system architecture.
