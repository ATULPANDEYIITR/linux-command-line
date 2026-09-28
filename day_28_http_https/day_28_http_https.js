"use strict";

/*
 * HTTP and HTTPS: practical JavaScript study program.
 *
 * This file complements the Python implementation by focusing on JavaScript
 * networking APIs, URL handling, browser concepts, asynchronous requests,
 * Fetch API behavior, headers, JSON, AbortController, caching concepts,
 * cookies, redirects, security boundaries, and Node.js HTTPS/TLS concepts.
 *
 * Browser examples are represented as functions that can run in a browser.
 * Node.js examples use only built-in modules.
 *
 * Suggested execution:
 *     node http_https_learning.js
 *
 * No external npm packages are required.
 */

const http = require("node:http");
const https = require("node:https");
const crypto = require("node:crypto");
const url = require("node:url");
const fs = require("node:fs");
const path = require("node:path");


// ============================================================================
// 1. FUNDAMENTAL HTTP TERMINOLOGY
// ============================================================================

const HTTP_METHODS = Object.freeze({
    GET: "Retrieve a representation.",
    HEAD: "Retrieve headers without a response body.",
    POST: "Submit data or request a server-side action.",
    PUT: "Create or replace a representation.",
    PATCH: "Partially modify a representation.",
    DELETE: "Request deletion of a resource.",
    OPTIONS: "Discover communication options.",
    CONNECT: "Establish a tunnel, often through a proxy."
});

const STATUS_CODES = Object.freeze({
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    206: "Partial Content",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    412: "Precondition Failed",
    413: "Content Too Large",
    415: "Unsupported Media Type",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout"
});

function printSection(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function printSubsection(title) {
    console.log(`\n--- ${title} ---`);
}


// ============================================================================
// 2. URL API
// ============================================================================

function demonstrateURLAPI() {
    printSection("2. URL AND URLSEARCHPARAMS");

    const resourceURL = new URL(
        "https://api.example.com:8443/users/42?active=true&page=2#profile"
    );

    console.log("href:", resourceURL.href);
    console.log("protocol:", resourceURL.protocol);
    console.log("hostname:", resourceURL.hostname);
    console.log("port:", resourceURL.port);
    console.log("pathname:", resourceURL.pathname);
    console.log("search:", resourceURL.search);
    console.log("hash:", resourceURL.hash);

    const parameters = new URLSearchParams(resourceURL.search);

    console.log("active:", parameters.get("active"));
    console.log("page:", parameters.get("page"));

    parameters.set("sort", "name");
    resourceURL.search = parameters.toString();

    console.log("Updated URL:", resourceURL.href);

    /*
     * URL fragments are normally handled by the user agent and are not part
     * of the HTTP request target sent to the server.
     */
}


// ============================================================================
// 3. RAW HTTP MESSAGE STRUCTURE
// ============================================================================

function buildHTTPMessage() {
    printSection("3. HTTP REQUEST MESSAGE STRUCTURE");

    const requestLine = "GET /api/users?page=2 HTTP/1.1";

    const headers = {
        Host: "example.com",
        Accept: "application/json",
        "User-Agent": "HTTP-Learning-JavaScript/1.0",
        Connection: "close"
    };

    const headerText = Object.entries(headers)
        .map(([name, value]) => `${name}: ${value}`)
        .join("\r\n");

    const rawMessage = `${requestLine}\r\n${headerText}\r\n\r\n`;

    console.log(rawMessage);

    /*
     * HTTP/1.x uses a request line followed by headers, a blank line, and
     * optionally a message body. HTTP/2 and HTTP/3 use binary framing rather
     * than this textual wire representation, although the conceptual HTTP
     * fields remain.
     */
}


// ============================================================================
// 4. JSON REQUEST/RESPONSE
// ============================================================================

function demonstrateJSON() {
    printSection("4. JSON OVER HTTP");

    const user = {
        username: "atul",
        active: true,
        roles: ["reader", "developer"]
    };

    const requestBody = JSON.stringify(user);

    console.log("Serialized JSON:", requestBody);
    console.log("Content-Type: application/json");
    console.log("Body byte length:", Buffer.byteLength(requestBody, "utf8"));

    const parsedResponse = JSON.parse(
        '{"id":42,"username":"atul","active":true}'
    );

    console.log("Parsed response:", parsedResponse);
}


// ============================================================================
// 5. HEADERS
// ============================================================================

function demonstrateHeaders() {
    printSection("5. JAVASCRIPT HEADERS API");

    const headers = new Headers();

    headers.set("Accept", "application/json");
    headers.set("X-Request-ID", crypto.randomUUID());

    console.log("Accept:", headers.get("accept"));
    console.log("Request ID:", headers.get("x-request-id"));

    console.log("Header entries:");

    for (const [name, value] of headers.entries()) {
        console.log(`${name}: ${value}`);
    }

    /*
     * Header names are case-insensitive according to HTTP semantics.
     * The Headers API normalizes access accordingly.
     */
}


// ============================================================================
// 6. STATUS HANDLING
// ============================================================================

function classifyStatus(statusCode) {
    if (!Number.isInteger(statusCode) || statusCode < 100 || statusCode > 599) {
        throw new RangeError("HTTP status code must be between 100 and 599.");
    }

    if (statusCode >= 100 && statusCode < 200) return "informational";
    if (statusCode >= 200 && statusCode < 300) return "successful";
    if (statusCode >= 300 && statusCode < 400) return "redirection";
    if (statusCode >= 400 && statusCode < 500) return "client-error";
    return "server-error";
}

function demonstrateStatusHandling() {
    printSection("6. STATUS CODE HANDLING");

    for (const code of [200, 201, 301, 304, 400, 401, 404, 429, 500, 503]) {
        console.log(
            `${code}: ${STATUS_CODES[code] ?? "Known HTTP status"} -> ${classifyStatus(code)}`
        );
    }

    /*
     * Fetch resolves its Promise for ordinary HTTP error statuses such as
     * 404 and 500. It rejects mainly for failures such as network errors,
     * malformed URLs, or an aborted operation. Therefore production code
     * should explicitly inspect response.ok or response.status.
     */
}


// ============================================================================
// 7. ASYNCHRONOUS FETCH
// ============================================================================

async function fetchExample(urlString) {
    printSubsection(`Fetching ${urlString}`);

    try {
        const response = await fetch(urlString, {
            method: "GET",
            headers: {
                "Accept": "application/json, text/plain;q=0.9, */*;q=0.8"
            }
        });

        console.log("HTTP status:", response.status);
        console.log("HTTP status text:", response.statusText);
        console.log("Content-Type:", response.headers.get("content-type"));

        if (!response.ok) {
            throw new Error(`HTTP request failed with ${response.status}`);
        }

        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
            return await response.json();
        }

        return await response.text();
    } catch (error) {
        console.error("Fetch error:", error.message);
        throw error;
    }
}


// ============================================================================
// 8. POST REQUEST
// ============================================================================

async function postJSON(urlString, payload) {
    const response = await fetch(urlString, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const responseText = await response.text().catch(() => "");
        throw new Error(
            `POST failed: ${response.status} ${response.statusText}; ${responseText}`
        );
    }

    const contentType = response.headers.get("content-type") || "";

    return contentType.includes("application/json")
        ? response.json()
        : response.text();
}


// ============================================================================
// 9. ABORTCONTROLLER AND TIMEOUTS
// ============================================================================

async function fetchWithTimeout(urlString, timeoutMilliseconds = 5000) {
    const controller = new AbortController();

    const timeoutId = setTimeout(
        () => controller.abort(),
        timeoutMilliseconds
    );

    try {
        const response = await fetch(urlString, {
            signal: controller.signal,
            headers: {
                "Accept": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return await response.text();
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error(
                `Request exceeded ${timeoutMilliseconds} ms timeout.`
            );
        }

        throw error;
    } finally {
        clearTimeout(timeoutId);
    }
}


// ============================================================================
// 10. RETRY WITH EXPONENTIAL BACKOFF
// ============================================================================

function delay(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function retryOperation(
    operation,
    {
        maxAttempts = 3,
        baseDelay = 200,
        maxDelay = 2000
    } = {}
) {
    if (maxAttempts < 1) {
        throw new RangeError("maxAttempts must be at least one.");
    }

    let lastError;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            return await operation(attempt);
        } catch (error) {
            lastError = error;

            if (attempt === maxAttempts) {
                break;
            }

            /*
             * Exponential backoff reduces repeated load during temporary
             * failures. Random jitter is commonly added in distributed systems
             * so many clients do not retry simultaneously.
             */
            const exponentialDelay = Math.min(
                baseDelay * (2 ** (attempt - 1)),
                maxDelay
            );

            const jitter = Math.random() * exponentialDelay * 0.25;

            await delay(exponentialDelay + jitter);
        }
    }

    throw lastError;
}


// ============================================================================
// 11. IDEMPOTENCY
// ============================================================================

function demonstrateIdempotency() {
    printSection("11. METHOD SAFETY AND IDEMPOTENCY");

    const properties = {
        GET: ["safe", "idempotent"],
        HEAD: ["safe", "idempotent"],
        OPTIONS: ["safe", "idempotent"],
        PUT: ["not safe", "idempotent"],
        DELETE: ["not safe", "idempotent"],
        POST: ["not safe", "not generally idempotent"],
        PATCH: ["not safe", "depends on operation"]
    };

    for (const [method, [safety, idempotency]] of Object.entries(properties)) {
        console.log(
            `${method.padEnd(8)} | ${safety.padEnd(25)} | ${idempotency}`
        );
    }

    /*
     * A POST can sometimes be made effectively retry-safe through an
     * application-level idempotency key. The server must actually implement
     * the required semantics; merely sending a header does not guarantee it.
     */
}


// ============================================================================
// 12. COOKIES
// ============================================================================

function parseCookieHeader(headerValue) {
    const cookies = {};

    if (!headerValue) {
        return cookies;
    }

    for (const part of headerValue.split(";")) {
        const separatorIndex = part.indexOf("=");

        if (separatorIndex === -1) {
            continue;
        }

        const name = part.slice(0, separatorIndex).trim();
        const value = part.slice(separatorIndex + 1).trim();

        if (name) {
            cookies[name] = value;
        }
    }

    return cookies;
}

function demonstrateCookies() {
    printSection("12. COOKIES");

    const requestCookieHeader = "session_id=abc123; theme=dark";

    console.log(parseCookieHeader(requestCookieHeader));

    console.log(
        "Example Set-Cookie:",
        "session_id=abc123; Path=/; Secure; HttpOnly; SameSite=Lax"
    );

    /*
     * In a browser, HttpOnly cookies cannot be read through document.cookie.
     * A server can still receive them automatically when cookie rules permit.
     *
     * JavaScript cannot normally set the HttpOnly attribute itself because
     * HttpOnly is specifically a server-controlled restriction.
     */
}


// ============================================================================
// 13. BROWSER ORIGIN
// ============================================================================

function getOrigin(urlString) {
    return new URL(urlString).origin;
}

function demonstrateOrigin() {
    printSection("13. ORIGIN AND SAME-ORIGIN POLICY");

    const first = "https://app.example.com/dashboard";
    const second = "https://api.example.com/users";
    const third = "https://app.example.com/settings";
    const fourth = "http://app.example.com/settings";

    console.log("A:", getOrigin(first));
    console.log("B:", getOrigin(second));
    console.log("C:", getOrigin(third));
    console.log("D:", getOrigin(fourth));

    console.log("A === B:", getOrigin(first) === getOrigin(second));
    console.log("A === C:", getOrigin(first) === getOrigin(third));
    console.log("A === D:", getOrigin(first) === getOrigin(fourth));

    /*
     * Same-origin comparison includes scheme, hostname, and port.
     * app.example.com and api.example.com are different origins even though
     * they share the same parent domain.
     */
}


// ============================================================================
// 14. CORS CONCEPT
// ============================================================================

function explainCORSHeaders() {
    printSection("14. CORS");

    const hypotheticalResponseHeaders = {
        "Access-Control-Allow-Origin": "https://app.example.com",
        "Access-Control-Allow-Methods": "GET, POST",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Credentials": "true"
    };

    for (const [name, value] of Object.entries(hypotheticalResponseHeaders)) {
        console.log(`${name}: ${value}`);
    }

    /*
     * CORS is primarily a browser-enforced mechanism. A server-to-server
     * request made by Node.js is not automatically restricted by the browser's
     * same-origin policy.
     *
     * Credentials and wildcard origins have important compatibility and
     * security constraints. Servers should explicitly configure allowed
     * origins rather than reflecting arbitrary Origin values.
     */
}


// ============================================================================
// 15. CONTENT NEGOTIATION
// ============================================================================

function demonstrateContentNegotiation() {
    printSection("15. CONTENT NEGOTIATION");

    const acceptedTypes = [
        "application/json",
        "text/html;q=0.8",
        "*/*;q=0.5"
    ];

    console.log("Accept header:", acceptedTypes.join(", "));

    console.log(
        "A server may choose a representation according to Accept, "
        "Accept-Language, Accept-Encoding, and other request metadata."
    );

    console.log(
        "Response metadata may include Content-Type and Vary to describe "
        "the selected representation and relevant cache dimensions."
    );
}


// ============================================================================
// 16. CACHING
// ============================================================================

class SimpleCache {
    constructor() {
        this.entries = new Map();
    }

    store(urlString, body, maxAgeSeconds) {
        const etag = `"${crypto
            .createHash("sha256")
            .update(body)
            .digest("hex")
            .slice(0, 16)}"`;

        const entry = {
            url: urlString,
            body,
            etag,
            storedAt: Date.now(),
            maxAgeSeconds
        };

        this.entries.set(urlString, entry);

        return entry;
    }

    isFresh(entry) {
        const ageMilliseconds = Date.now() - entry.storedAt;

        return ageMilliseconds < entry.maxAgeSeconds * 1000;
    }
}

function demonstrateCaching() {
    printSection("16. HTTP CACHING");

    const cache = new SimpleCache();

    const body = JSON.stringify({
        version: 1,
        message: "cacheable representation"
    });

    const entry = cache.store(
        "https://example.com/data",
        body,
        60
    );

    console.log("ETag:", entry.etag);
    console.log("Fresh:", cache.isFresh(entry));

    console.log(
        "Conditional request header:",
        `If-None-Match: ${entry.etag}`
    );

    console.log(
        "If the representation is unchanged, a server can return 304 Not Modified."
    );
}


// ============================================================================
// 17. RANGE REQUEST CONCEPT
// ============================================================================

function applyByteRange(buffer, start, end) {
    if (!Number.isInteger(start) || start < 0) {
        throw new RangeError("start must be a non-negative integer.");
    }

    if (end !== undefined && (!Number.isInteger(end) || end < start)) {
        throw new RangeError("end must be an integer >= start.");
    }

    if (start >= buffer.length) {
        throw new RangeError("Requested range is outside the resource.");
    }

    const inclusiveEnd = end === undefined
        ? buffer.length - 1
        : Math.min(end, buffer.length - 1);

    return buffer.subarray(start, inclusiveEnd + 1);
}

function demonstrateRanges() {
    printSection("17. BYTE RANGE REQUESTS");

    const resource = Buffer.from("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
    const result = applyByteRange(resource, 5, 10);

    console.log("Resource:", resource.toString());
    console.log("Range bytes=5-10:", result.toString());
}


// ============================================================================
// 18. BASIC AUTHORIZATION HEADER
// ============================================================================

function createBasicAuthorization(username, password) {
    const credentials = `${username}:${password}`;

    return `Basic ${Buffer
        .from(credentials, "utf8")
        .toString("base64")}`;
}

function demonstrateAuthentication() {
    printSection("18. HTTP AUTHENTICATION");

    const authorization = createBasicAuthorization(
        "alice",
        "example-password"
    );

    console.log("Authorization:", authorization);

    console.log(
        "Base64 is encoding rather than encryption. Basic authentication "
        + "requires TLS when credentials must be protected in transit."
    );

    console.log(
        "Bearer tokens, sessions, mutual TLS, and signed requests represent "
        + "other authentication mechanisms with different security properties."
    );
}


// ============================================================================
// 19. SECURITY HEADERS
// ============================================================================

function demonstrateSecurityHeaders() {
    printSection("19. SECURITY-RELEVANT RESPONSE HEADERS");

    const headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=()"
    };

    for (const [name, value] of Object.entries(headers)) {
        console.log(`${name}: ${value}`);
    }

    console.log(
        "\nSecurity headers are application-dependent. A policy should be "
        + "tested against the actual resources and browser features required."
    );
}


// ============================================================================
// 20. URL AND HEADER SECURITY
// ============================================================================

function demonstrateSensitiveDataHandling() {
    printSection("20. SENSITIVE DATA HANDLING");

    const unsafeURL = new URL("https://example.com/reset");

    /*
     * Avoid placing passwords, long-lived access tokens, or other secrets in
     * query strings. URLs can appear in logs, browser history, analytics,
     * monitoring systems, proxies, and referrer-related metadata.
     */
    unsafeURL.searchParams.set("user", "alice");

    console.log("Non-secret query example:", unsafeURL.href);

    console.log(
        "Credentials should normally be transported through an appropriate "
        + "authenticated mechanism and protected by HTTPS."
    );
}


// ============================================================================
// 21. NODE.JS HTTP SERVER
// ============================================================================

function createLearningHTTPServer(port = 8080) {
    const server = http.createServer((request, response) => {
        const requestURL = new URL(
            request.url,
            `http://${request.headers.host || "localhost"}`
        );

        /*
         * Security headers are sent before end() or writeHead() completes the
         * response. Content-Length is used here because the response body is
         * already known.
         */
        response.setHeader("Content-Type", "application/json; charset=utf-8");
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("X-Content-Type-Options", "nosniff");

        if (requestURL.pathname === "/health" && request.method === "GET") {
            const body = JSON.stringify({
                status: "healthy",
                protocol: "HTTP"
            });

            response.writeHead(200, {
                "Content-Length": Buffer.byteLength(body)
            });

            response.end(body);
            return;
        }

        if (requestURL.pathname === "/api/echo" && request.method === "POST") {
            let receivedBytes = 0;
            const chunks = [];

            request.on("data", chunk => {
                receivedBytes += chunk.length;

                /*
                 * Enforce a maximum request body size. Production systems
                 * should use streaming and application-specific validation
                 * rather than buffering arbitrarily large requests.
                 */
                if (receivedBytes > 1_000_000) {
                    response.writeHead(413);
                    response.end(
                        JSON.stringify({ error: "request body too large" })
                    );
                    request.destroy();
                    return;
                }

                chunks.push(chunk);
            });

            request.on("end", () => {
                const body = Buffer.concat(chunks);

                const result = JSON.stringify({
                    receivedBytes: body.length,
                    sha256: crypto
                        .createHash("sha256")
                        .update(body)
                        .digest("hex")
                });

                response.writeHead(200, {
                    "Content-Length": Buffer.byteLength(result)
                });

                response.end(result);
            });

            request.on("error", error => {
                if (!response.headersSent) {
                    response.writeHead(400);
                    response.end(
                        JSON.stringify({
                            error: "request stream failure",
                            message: error.message
                        })
                    );
                }
            });

            return;
        }

        const notFound = JSON.stringify({
            error: "not_found",
            method: request.method,
            path: requestURL.pathname
        });

        response.writeHead(404, {
            "Content-Length": Buffer.byteLength(notFound)
        });

        response.end(notFound);
    });

    server.requestTimeout = 10_000;
    server.headersTimeout = 10_000;
    server.keepAliveTimeout = 5_000;

    server.listen(port, "127.0.0.1", () => {
        console.log(`HTTP server listening on http://127.0.0.1:${port}`);
    });

    return server;
}


// ============================================================================
// 22. NODE.JS HTTPS SERVER
// ============================================================================

function createLearningHTTPSServer(
    port = 8443,
    certificateFile = "server.crt",
    keyFile = "server.key"
) {
    printSection("22. NODE.JS HTTPS SERVER");

    /*
     * Development certificate creation is intentionally left to an
     * administrator's certificate tooling. The certificate must include the
     * hostname clients use, such as localhost.
     */
    if (!fs.existsSync(certificateFile)) {
        console.error(`Certificate not found: ${certificateFile}`);
        return null;
    }

    if (!fs.existsSync(keyFile)) {
        console.error(`Private key not found: ${keyFile}`);
        return null;
    }

    const tlsOptions = {
        cert: fs.readFileSync(path.resolve(certificateFile)),
        key: fs.readFileSync(path.resolve(keyFile)),
        minVersion: "TLSv1.2"
    };

    const server = https.createServer(
        tlsOptions,
        (request, response) => {
            response.setHeader(
                "Content-Type",
                "application/json; charset=utf-8"
            );
            response.setHeader("Cache-Control", "no-store");
            response.setHeader("X-Content-Type-Options", "nosniff");

            const body = JSON.stringify({
                service: "Node.js HTTPS learning server",
                protocol: "HTTPS",
                method: request.method,
                path: request.url
            });

            response.writeHead(200, {
                "Content-Length": Buffer.byteLength(body)
            });

            response.end(body);
        }
    );

    server.requestTimeout = 10_000;
    server.headersTimeout = 10_000;

    server.listen(port, "127.0.0.1", () => {
        console.log(`HTTPS server listening on https://127.0.0.1:${port}`);
    });

    return server;
}


// ============================================================================
// 23. NODE.JS HTTPS CLIENT
// ============================================================================

function httpsRequestExample(hostname = "example.com") {
    printSection("23. NODE.JS HTTPS CLIENT");

    return new Promise((resolve, reject) => {
        const request = https.request(
            {
                hostname,
                port: 443,
                path: "/",
                method: "GET",
                timeout: 8000,
                headers: {
                    "User-Agent": "HTTP-Learning-Node/1.0",
                    Accept: "text/html"
                }
            },
            response => {
                console.log("Status:", response.statusCode);
                console.log("Content-Type:", response.headers["content-type"]);

                const chunks = [];

                response.on("data", chunk => {
                    chunks.push(chunk);
                });

                response.on("end", () => {
                    const body = Buffer.concat(chunks);

                    console.log("Received bytes:", body.length);
                    console.log("First bytes:", body.subarray(0, 200).toString());

                    resolve(body);
                });
            }
        );

        request.on("timeout", () => {
            request.destroy(new Error("HTTPS request timed out."));
        });

        request.on("error", reject);

        request.end();
    });
}


// ============================================================================
// 24. TLS CONNECTION INSPECTION
// ============================================================================

function inspectRemoteTLS(hostname = "example.com") {
    printSection(`24. TLS INSPECTION: ${hostname}`);

    return new Promise((resolve, reject) => {
        const socket = tlsConnect(hostname);

        socket.on("secureConnect", () => {
            console.log("Authorized:", socket.authorized);
            console.log("Authorization error:", socket.authorizationError);
            console.log("Protocol:", socket.getProtocol());
            console.log("Cipher:", socket.getCipher());

            const certificate = socket.getPeerCertificate();

            console.log("Certificate subject:", certificate.subject);
            console.log("Certificate issuer:", certificate.issuer);
            console.log("Certificate valid from:", certificate.valid_from);
            console.log("Certificate valid to:", certificate.valid_to);

            socket.end();
            resolve(certificate);
        });

        socket.on("error", reject);
    });
}

function tlsConnect(hostname) {
    const tls = require("node:tls");

    return tls.connect({
        host: hostname,
        port: 443,
        servername: hostname,
        rejectUnauthorized: true,
        timeout: 8000
    });
}


// ============================================================================
// 25. HTTPS VS HTTP CONCEPTUAL COMPARISON
// ============================================================================

function compareHTTPAndHTTPS() {
    printSection("25. HTTP VS HTTPS");

    const comparison = [
        ["Application semantics", "HTTP", "HTTP over TLS"],
        ["Confidentiality", "Not provided by HTTP itself", "Provided by TLS when correctly configured"],
        ["Integrity", "Not cryptographically guaranteed", "Provided by authenticated TLS records"],
        ["Server authentication", "Not provided by HTTP itself", "Normally provided by certificate validation"],
        ["Typical ports", "80", "443"],
        ["Browser security", "Restricted depending on context", "Required for many modern web capabilities"],
        ["Deployment", "Plain transport", "TLS configuration and certificate management required"]
    ];

    for (const [aspect, httpValue, httpsValue] of comparison) {
        console.log(`\n${aspect}`);
        console.log(`  HTTP : ${httpValue}`);
        console.log(`  HTTPS: ${httpsValue}`);
    }

    console.log(
        "\nHTTPS does not change GET, POST, status codes, JSON, cookies, or "
        + "HTTP application semantics. TLS protects the transport connection "
        + "over which those HTTP messages travel."
    );
}


// ============================================================================
// 26. PROXY CONCEPTS
// ============================================================================

function explainProxyArchitecture() {
    printSection("26. PROXIES, LOAD BALANCERS, AND TLS TERMINATION");

    const architecture = [
        "Browser/client",
        "DNS",
        "CDN or reverse proxy",
        "Load balancer",
        "Application server",
        "Database or downstream service"
    ];

    architecture.forEach((component, index) => {
        console.log(`${index + 1}. ${component}`);
    });

    console.log(
        "\nTLS can terminate at a CDN, reverse proxy, or load balancer. "
        + "If traffic is re-encrypted toward the application server, there may "
        + "be multiple independently protected connections."
    );

    console.log(
        "\nThe security design must define which component authenticates the "
        + "client, which component validates forwarded headers, and where "
        + "authorization decisions are made."
    );
}


// ============================================================================
// 27. REQUEST PARSING AND HEADER INJECTION AWARENESS
// ============================================================================

function validateHeaderName(name) {
    /*
     * HTTP field names use the token grammar. Rejecting control characters
     * and whitespace is important when constructing raw HTTP messages.
     */
    if (!/^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/.test(name)) {
        throw new Error(`Invalid HTTP header name: ${name}`);
    }

    return name;
}

function validateHeaderValue(value) {
    /*
     * CR and LF must not be accepted as ordinary header-value characters when
     * constructing an HTTP message. This prevents header-injection problems.
     */
    if (/[\r\n]/.test(value)) {
        throw new Error("Header value contains forbidden CR/LF characters.");
    }

    return value;
}

function demonstrateHeaderValidation() {
    printSection("27. HEADER VALIDATION");

    console.log(validateHeaderName("Content-Type"));
    console.log(validateHeaderValue("application/json"));

    try {
        validateHeaderValue("safe\r\nInjected: true");
    } catch (error) {
        console.log("Rejected malicious header value:", error.message);
    }

    try {
        validateHeaderName("Bad Header");
    } catch (error) {
        console.log("Rejected invalid header name:", error.message);
    }
}


// ============================================================================
// 28. REQUEST SIZE LIMIT
// ============================================================================

function collectRequestBody(request, maxBytes = 1_000_000) {
    return new Promise((resolve, reject) => {
        let totalBytes = 0;
        const chunks = [];

        request.on("data", chunk => {
            totalBytes += chunk.length;

            if (totalBytes > maxBytes) {
                reject(
                    new Error(
                        `Request body exceeds ${maxBytes} byte limit.`
                    )
                );

                request.destroy();
                return;
            }

            chunks.push(chunk);
        });

        request.on("end", () => {
            resolve(Buffer.concat(chunks));
        });

        request.on("error", reject);
    });
}


// ============================================================================
// 29. SIMPLE RATE LIMITER
// ============================================================================

class FixedWindowRateLimiter {
    constructor(limit, windowMilliseconds) {
        if (limit <= 0 || windowMilliseconds <= 0) {
            throw new RangeError("Rate limit parameters must be positive.");
        }

        this.limit = limit;
        this.windowMilliseconds = windowMilliseconds;
        this.requests = new Map();
    }

    allow(clientId, now = Date.now()) {
        const existing = this.requests.get(clientId) || [];

        const cutoff = now - this.windowMilliseconds;

        const recent = existing.filter(timestamp => timestamp > cutoff);

        if (recent.length >= this.limit) {
            this.requests.set(clientId, recent);
            return false;
        }

        recent.push(now);
        this.requests.set(clientId, recent);

        return true;
    }
}

function demonstrateRateLimiting() {
    printSection("29. RATE LIMITING");

    const limiter = new FixedWindowRateLimiter(3, 60_000);

    for (let requestNumber = 1; requestNumber <= 5; requestNumber++) {
        console.log(
            `Request ${requestNumber}:`,
            limiter.allow("client-A", 1000)
                ? "allowed"
                : "429 Too Many Requests"
        );
    }
}


// ============================================================================
// 30. HASH-BASED ETAG
// ============================================================================

function generateETag(body) {
    return `"${crypto
        .createHash("sha256")
        .update(body)
        .digest("hex")
        .slice(0, 16)}"`;
}

function demonstrateETag() {
    printSection("30. ETAG");

    const body = Buffer.from("Version 1 of a resource");
    const etag = generateETag(body);

    console.log("Generated ETag:", etag);
    console.log(`If-None-Match: ${etag}`);

    console.log(
        "A server can compare the request validator with the current "
        + "representation and return 304 when appropriate."
    );
}


// ============================================================================
// 31. TESTS
// ============================================================================

function runAssertions() {
    printSection("31. BUILT-IN ASSERTIONS");

    const assert = require("node:assert/strict");

    assert.equal(classifyStatus(200), "successful");
    assert.equal(classifyStatus(404), "client-error");
    assert.equal(classifyStatus(503), "server-error");

    assert.equal(
        getOrigin("https://example.com/a"),
        "https://example.com"
    );

    assert.notEqual(
        getOrigin("http://example.com/a"),
        getOrigin("https://example.com/a")
    );

    const buffer = Buffer.from("abcdef");

    assert.equal(
        applyByteRange(buffer, 1, 3).toString(),
        "bcd"
    );

    assert.equal(
        parseCookieHeader("a=1; b=2").b,
        "2"
    );

    assert.match(
        generateETag(Buffer.from("test")),
        /^"[a-f0-9]+"/
    );

    const limiter = new FixedWindowRateLimiter(2, 1000);

    assert.equal(limiter.allow("client", 1000), true);
    assert.equal(limiter.allow("client", 1000), true);
    assert.equal(limiter.allow("client", 1000), false);

    try {
        validateHeaderName("Bad Header");
        assert.fail("Invalid header name should throw.");
    } catch (error) {
        assert.match(error.message, /Invalid HTTP header name/);
    }

    console.log("All assertions passed.");
}


// ============================================================================
// 32. PRACTICAL HTTPS REQUEST FLOW
// ============================================================================

function explainHTTPSFlow() {
    printSection("32. REAL-WORLD HTTPS FLOW");

    const steps = [
        "1. JavaScript/browser code creates a URL and prepares an HTTP request.",
        "2. DNS resolves the destination hostname.",
        "3. The client establishes the transport connection.",
        "4. TLS negotiates cryptographic parameters and authenticates the server certificate.",
        "5. HTTP request headers and optional body are sent through the protected channel.",
        "6. A CDN, proxy, or load balancer may route the request.",
        "7. The application authenticates and authorizes the operation.",
        "8. The server returns status, headers, and an optional representation.",
        "9. The client processes caching, cookies, redirects, and response data.",
        "10. Application code handles successful and unsuccessful outcomes."
    ];

    for (const step of steps) {
        console.log(step);
    }
}


// ============================================================================
// 33. BROWSER-ONLY DEMONSTRATION
// ============================================================================

async function browserFetchDemonstration() {
    if (typeof window === "undefined" || typeof document === "undefined") {
        console.log(
            "Browser demonstration skipped because this runtime is not a browser."
        );
        return;
    }

    printSection("33. BROWSER FETCH DEMONSTRATION");

    try {
        const response = await fetch("/api/health", {
            method: "GET",
            credentials: "same-origin",
            headers: {
                Accept: "application/json"
            }
        });

        console.log("Status:", response.status);
        console.log("Response:", await response.text());
    } catch (error) {
        console.error("Browser fetch failed:", error);
    }
}


// ============================================================================
// 34. MAIN STUDY PROGRAM
// ============================================================================

async function main() {
    printSection("HTTP AND HTTPS JAVASCRIPT STUDY PROGRAM");

    console.log(
        "This executable file demonstrates web communication concepts using "
        + "JavaScript and Node.js built-in APIs."
    );

    demonstrateURLAPI();
    buildHTTPMessage();
    demonstrateJSON();
    demonstrateHeaders();
    demonstrateStatusHandling();
    demonstrateIdempotency();
    demonstrateCookies();
    demonstrateOrigin();
    explainCORSHeaders();
    demonstrateContentNegotiation();
    demonstrateCaching();
    demonstrateRanges();
    demonstrateAuthentication();
    demonstrateSecurityHeaders();
    demonstrateSensitiveDataHandling();
    demonstrateHeaderValidation();
    demonstrateRateLimiting();
    demonstrateETag();
    compareHTTPAndHTTPS();
    explainProxyArchitecture();
    runAssertions();
    explainHTTPSFlow();

    await browserFetchDemonstration();

    printSection("OPTIONAL NETWORK OPERATIONS");

    console.log("Examples available in this file:");
    console.log("  await fetchExample('https://example.com/')");
    console.log("  await fetchWithTimeout('https://example.com/', 5000)");
    console.log("  await httpsRequestExample('example.com')");
    console.log("  await inspectRemoteTLS('example.com')");
    console.log("  createLearningHTTPServer(8080)");
    console.log("  createLearningHTTPSServer(8443)");

    console.log(
        "\nNetwork examples are not automatically executed so the core study "
        + "program remains usable in offline environments."
    );
}


if (require.main === module) {
    main().catch(error => {
        console.error("Program failed:", error);
        process.exitCode = 1;
    });
}


// ============================================================================
// 35. EXPORTS FOR TESTING OR REUSE
// ============================================================================

module.exports = {
    HTTP_METHODS,
    STATUS_CODES,
    classifyStatus,
    generateETag,
    parseCookieHeader,
    applyByteRange,
    validateHeaderName,
    validateHeaderValue,
    FixedWindowRateLimiter,
    SimpleCache,
    createBasicAuthorization,
    createLearningHTTPServer,
    createLearningHTTPSServer,
    fetchExample,
    fetchWithTimeout,
    postJSON,
    retryOperation
};
