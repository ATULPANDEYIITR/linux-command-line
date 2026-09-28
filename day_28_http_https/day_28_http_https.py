#!/usr/bin/env python3
"""
HTTP and HTTPS: comprehensive standalone study program.

This program teaches HTTP and HTTPS from beginner concepts through advanced
topics using executable Python examples. It implements a small HTTP message
parser, URL handling, HTTP request/response construction, cookie handling,
caching concepts, redirects, content negotiation, authentication examples,
TLS/certificate inspection, and a local HTTPS server/client demonstration.

The standard library is intentionally used wherever possible so the file can
be studied and executed without third-party packages.

Run:
    python http_https_learning.py

Optional local HTTPS demonstration:
    python http_https_learning.py --server

The HTTPS server demonstration requires a certificate and private key named
server.crt and server.key in the current directory. The program explains how
to generate development certificates through comments, but does not generate
or distribute certificates automatically.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import http.server
import ipaddress
import json
import mimetypes
import os
import re
import socket
import ssl
import threading
import time
import urllib.parse
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# ============================================================================
# 1. FUNDAMENTAL HTTP TERMINOLOGY
# ============================================================================

HTTP_TERMINOLOGY = {
    "HTTP": (
        "Hypertext Transfer Protocol, an application-layer protocol used to "
        "exchange requests and responses between clients and servers."
    ),
    "HTTPS": (
        "HTTP carried through a TLS-protected connection. TLS provides "
        "encryption, integrity protection, and server authentication."
    ),
    "client": "The party that initiates a request, such as a browser or API client.",
    "server": "The party that receives requests and sends responses.",
    "request": "A message sent by a client asking a server to perform an operation.",
    "response": "A message sent by a server describing the result of a request.",
    "resource": "A server-side representation identified by a URI.",
    "URI": "A uniform resource identifier.",
    "URL": "A URI that provides a retrieval-oriented location.",
    "header": "Metadata carried in an HTTP message.",
    "body": "Optional message content such as JSON, HTML, an image, or form data.",
    "status code": "A three-digit code describing the general result of a request.",
    "TLS": (
        "Transport Layer Security, a cryptographic protocol that protects "
        "network communication."
    ),
    "certificate": (
        "A digitally signed credential binding an identity, such as a DNS "
        "name, to a public key."
    ),
    "CA": "Certificate Authority, an entity whose trusted signatures establish certificate trust.",
    "cookie": (
        "Small state information sent by a server and later returned by a "
        "client according to cookie rules."
    ),
}

HTTP_METHODS = {
    "GET": "Retrieve a representation.",
    "HEAD": "Retrieve response metadata without the response content.",
    "POST": "Submit data, often causing creation or another server-side action.",
    "PUT": "Create or completely replace a representation at a target URI.",
    "PATCH": "Apply a partial modification.",
    "DELETE": "Request deletion of a target resource.",
    "OPTIONS": "Ask which communication options are supported.",
    "TRACE": "Diagnostic method that can reflect a request; commonly disabled.",
    "CONNECT": "Establish a tunnel, commonly used with HTTP proxies.",
}

STATUS_CATEGORIES = {
    1: "Informational",
    2: "Successful",
    3: "Redirection",
    4: "Client error",
    5: "Server error",
}


def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_subsection(title: str) -> None:
    print(f"\n--- {title} ---")


def explain_terminology() -> None:
    print_section("1. HTTP AND HTTPS TERMINOLOGY")

    for term, definition in HTTP_TERMINOLOGY.items():
        print(f"{term:12}: {definition}")

    print_subsection("HTTP methods")
    for method, meaning in HTTP_METHODS.items():
        print(f"{method:9}: {meaning}")

    print_subsection("Status-code classes")
    for category, meaning in STATUS_CATEGORIES.items():
        print(f"{category}xx: {meaning}")


# ============================================================================
# 2. URL / URI STRUCTURE
# ============================================================================

def demonstrate_url_structure() -> None:
    print_section("2. URL STRUCTURE")

    url = (
        "https://api.example.com:8443/users/42"
        "?sort=name&active=true#profile"
    )

    parsed = urllib.parse.urlsplit(url)

    print(f"Original URL : {url}")
    print(f"Scheme       : {parsed.scheme}")
    print(f"Netloc       : {parsed.netloc}")
    print(f"Hostname     : {parsed.hostname}")
    print(f"Port         : {parsed.port}")
    print(f"Path         : {parsed.path}")
    print(f"Query        : {parsed.query}")
    print(f"Fragment     : {parsed.fragment}")

    query_parameters = urllib.parse.parse_qs(parsed.query)
    print(f"Parsed query : {query_parameters}")

    rebuilt = urllib.parse.urlunsplit(parsed)
    print(f"Rebuilt URL  : {rebuilt}")

    # Fragments are client-side identifiers and are normally not transmitted
    # as part of the HTTP request-target sent to the server.
    request_target = urllib.parse.urlunsplit(
        ("", "", parsed.path, parsed.query, "")
    )
    print(f"HTTP target  : {request_target}")


# ============================================================================
# 3. HTTP REQUEST MESSAGE
# ============================================================================

@dataclass
class HTTPRequest:
    method: str
    target: str
    version: str = "HTTP/1.1"
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def serialize(self) -> bytes:
        """Convert the structured request into an HTTP/1.x byte message."""
        normalized = {key.lower(): value for key, value in self.headers.items()}

        if "host" not in normalized:
            raise ValueError("HTTP/1.1 requests require a Host header.")

        if self.body and "content-length" not in normalized:
            normalized["content-length"] = str(len(self.body))

        lines = [f"{self.method} {self.target} {self.version}"]
        lines.extend(f"{key}: {value}" for key, value in normalized.items())

        return ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1") + self.body


def demonstrate_http_request() -> None:
    print_section("3. BUILDING AN HTTP REQUEST")

    request = HTTPRequest(
        method="GET",
        target="/products?page=2",
        headers={
            "Host": "example.com",
            "User-Agent": "HTTP-Learning-Client/1.0",
            "Accept": "application/json",
            "Connection": "close",
        },
    )

    raw = request.serialize()

    print(raw.decode("iso-8859-1"))

    # POST requests commonly carry a body. Content-Type describes its format,
    # while Content-Length describes the byte length of that body.
    payload = json.dumps({"username": "atul", "active": True}).encode()

    post_request = HTTPRequest(
        method="POST",
        target="/api/users",
        headers={
            "Host": "example.com",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        body=payload,
    )

    print("POST request:")
    print(post_request.serialize().decode("iso-8859-1"))


# ============================================================================
# 4. HTTP RESPONSE MESSAGE
# ============================================================================

@dataclass
class HTTPResponse:
    status_code: int
    reason: str
    version: str = "HTTP/1.1"
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def serialize(self) -> bytes:
        normalized = {key.lower(): value for key, value in self.headers.items()}

        if self.body and "content-length" not in normalized:
            normalized["content-length"] = str(len(self.body))

        lines = [f"{self.version} {self.status_code} {self.reason}"]
        lines.extend(f"{key}: {value}" for key, value in normalized.items())

        return ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1") + self.body


def demonstrate_http_response() -> None:
    print_section("4. BUILDING AN HTTP RESPONSE")

    body = json.dumps(
        {
            "message": "Resource retrieved successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    response = HTTPResponse(
        status_code=200,
        reason="OK",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        body=body,
    )

    print(response.serialize().decode("utf-8"))


# ============================================================================
# 5. REQUEST/RESPONSE PARSING
# ============================================================================

def parse_http_headers(raw_headers: str) -> Dict[str, str]:
    """Parse basic HTTP header lines into a case-insensitive-style mapping."""
    result: Dict[str, str] = {}

    for line in raw_headers.split("\r\n"):
        if not line:
            continue

        if ":" not in line:
            raise ValueError(f"Malformed header line: {line!r}")

        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()

        if not re.fullmatch(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+", name):
            raise ValueError(f"Invalid header name: {name!r}")

        result[name.lower()] = value

    return result


def parse_http_request(raw: bytes) -> HTTPRequest:
    header_part, separator, body = raw.partition(b"\r\n\r\n")

    if not separator:
        raise ValueError("HTTP message has no header/body separator.")

    lines = header_part.decode("iso-8859-1").split("\r\n")

    if not lines:
        raise ValueError("Empty HTTP request.")

    request_line = lines[0].split(" ")

    if len(request_line) != 3:
        raise ValueError("Malformed request line.")

    method, target, version = request_line

    headers = parse_http_headers("\r\n".join(lines[1:]))

    return HTTPRequest(method, target, version, headers, body)


def demonstrate_parsing() -> None:
    print_section("5. PARSING AN HTTP REQUEST")

    raw_request = (
        b"GET /hello?name=Atul HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Accept: text/plain\r\n"
        b"User-Agent: LearningClient/1.0\r\n"
        b"\r\n"
    )

    request = parse_http_request(raw_request)

    print(f"Method : {request.method}")
    print(f"Target : {request.target}")
    print(f"Version: {request.version}")
    print(f"Headers: {request.headers}")
    print(f"Body   : {request.body!r}")


# ============================================================================
# 6. STATUS CODES
# ============================================================================

def explain_status_codes() -> None:
    print_section("6. IMPORTANT HTTP STATUS CODES")

    statuses = {
        100: "Continue",
        101: "Switching Protocols",
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
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }

    for code, reason in statuses.items():
        print(f"{code}: {reason}")


# ============================================================================
# 7. IDEMPOTENCY AND SAFETY
# ============================================================================

def demonstrate_method_properties() -> None:
    print_section("7. METHOD SAFETY AND IDEMPOTENCY")

    properties = {
        "GET": ("safe", "idempotent"),
        "HEAD": ("safe", "idempotent"),
        "OPTIONS": ("safe", "idempotent"),
        "PUT": ("not safe", "idempotent"),
        "DELETE": ("not safe", "idempotent"),
        "POST": ("not safe", "not generally idempotent"),
        "PATCH": ("not safe", "depends on the operation"),
        "CONNECT": ("not safe", "not generally idempotent"),
        "TRACE": ("safe in protocol semantics", "idempotent"),
    }

    for method, (safety, idempotency) in properties.items():
        print(f"{method:8} | {safety:24} | {idempotency}")

    print(
        "\nIdempotency describes the intended effect of repeating the same "
        "request, not whether the request is transmitted only once."
    )


# ============================================================================
# 8. CONTENT TYPES AND ENCODING
# ============================================================================

def demonstrate_content_types() -> None:
    print_section("8. CONTENT TYPES AND ENCODING")

    examples = [
        ("HTML", "<h1>Hello</h1>", "text/html; charset=utf-8"),
        ("JSON", {"name": "Atul", "active": True}, "application/json"),
        ("Plain text", "Hello HTTP", "text/plain; charset=utf-8"),
    ]

    for name, value, content_type in examples:
        if isinstance(value, str):
            encoded = value.encode("utf-8")
        else:
            encoded = json.dumps(value).encode("utf-8")

        print(f"{name:12} | {content_type:30} | {len(encoded)} bytes")

    filename = "report.pdf"
    guessed_type, _ = mimetypes.guess_type(filename)
    print(f"\nMIME type guessed for {filename}: {guessed_type}")


# ============================================================================
# 9. URL ENCODING
# ============================================================================

def demonstrate_url_encoding() -> None:
    print_section("9. URL ENCODING")

    original = "HTTP & HTTPS: secure web communication?"
    encoded = urllib.parse.quote(original)
    decoded = urllib.parse.unquote(encoded)

    print(f"Original: {original}")
    print(f"Encoded : {encoded}")
    print(f"Decoded : {decoded}")

    parameters = {
        "query": "network security",
        "page": "2",
        "filter": "active users",
    }

    query = urllib.parse.urlencode(parameters)
    print(f"Query string: {query}")


# ============================================================================
# 10. COOKIES
# ============================================================================

@dataclass
class Cookie:
    name: str
    value: str
    attributes: Dict[str, str | bool] = field(default_factory=dict)

    def set_cookie_header(self) -> str:
        parts = [f"{self.name}={self.value}"]

        for name, value in self.attributes.items():
            if value is True:
                parts.append(name)
            else:
                parts.append(f"{name}={value}")

        return "; ".join(parts)


class SimpleCookieJar:
    """Small educational cookie jar.

    Real browsers implement substantially more rules, including domain,
    path, expiry, SameSite, Secure, partitioning, and public-suffix handling.
    """

    def __init__(self) -> None:
        self.cookies: Dict[str, Cookie] = {}

    def receive_set_cookie(self, header: str) -> None:
        parts = [part.strip() for part in header.split(";")]

        if not parts or "=" not in parts[0]:
            raise ValueError("Invalid Set-Cookie header.")

        name, value = parts[0].split("=", 1)

        attributes: Dict[str, str | bool] = {}

        for part in parts[1:]:
            if "=" in part:
                attr_name, attr_value = part.split("=", 1)
                attributes[attr_name.strip()] = attr_value.strip()
            else:
                attributes[part] = True

        self.cookies[name] = Cookie(name, value, attributes)

    def cookie_header(self) -> str:
        return "; ".join(
            f"{cookie.name}={cookie.value}"
            for cookie in self.cookies.values()
        )


def demonstrate_cookies() -> None:
    print_section("10. COOKIES")

    jar = SimpleCookieJar()

    jar.receive_set_cookie(
        "session_id=abc123; Path=/; HttpOnly; Secure; SameSite=Lax"
    )

    jar.receive_set_cookie(
        "theme=dark; Path=/"
    )

    print(f"Stored cookies: {list(jar.cookies)}")
    print(f"Request Cookie header: {jar.cookie_header()}")

    print(
        "\nHttpOnly is intended to prevent JavaScript from reading the cookie "
        "through document.cookie. Secure tells compatible clients to send "
        "the cookie only over secure connections."
    )


# ============================================================================
# 11. HTTP CACHING AND CONDITIONAL REQUESTS
# ============================================================================

@dataclass
class CacheEntry:
    url: str
    body: bytes
    etag: str
    stored_at: float

    def fresh_for(self, seconds: int) -> bool:
        return time.time() - self.stored_at < seconds


class HTTPCache:
    def __init__(self) -> None:
        self.entries: Dict[str, CacheEntry] = {}

    def store(self, url: str, body: bytes) -> CacheEntry:
        etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'

        entry = CacheEntry(
            url=url,
            body=body,
            etag=etag,
            stored_at=time.time(),
        )

        self.entries[url] = entry
        return entry

    def get(self, url: str) -> Optional[CacheEntry]:
        return self.entries.get(url)


def demonstrate_caching() -> None:
    print_section("11. HTTP CACHING")

    cache = HTTPCache()

    first_body = b'{"version":1,"message":"hello"}'
    entry = cache.store("https://example.com/data", first_body)

    print(f"ETag generated: {entry.etag}")
    print(f"Fresh for 60 seconds? {entry.fresh_for(60)}")

    client_etag = entry.etag
    server_etag = entry.etag

    if client_etag == server_etag:
        print("Conditional request result: 304 Not Modified")
        print("The client can reuse its cached representation.")

    print(
        "\nCommon cache controls include Cache-Control, ETag, Last-Modified, "
        "Expires, If-None-Match, and If-Modified-Since."
    )


# ============================================================================
# 12. ETAG AND LAST-MODIFIED
# ============================================================================

def demonstrate_validators() -> None:
    print_section("12. RESOURCE VALIDATORS")

    body = b"Important resource representation"
    etag = '"' + hashlib.sha256(body).hexdigest() + '"'

    last_modified = formatdate(time.time(), usegmt=True)

    print(f"ETag          : {etag}")
    print(f"Last-Modified : {last_modified}")

    print("\nA conditional request might contain:")
    print(f"If-None-Match: {etag}")
    print(f"If-Modified-Since: {last_modified}")

    print(
        "\nA matching validator can allow a server to return 304 instead of "
        "transmitting the representation again."
    )


# ============================================================================
# 13. REDIRECTS
# ============================================================================

def demonstrate_redirects() -> None:
    print_section("13. REDIRECTS")

    redirect_codes = {
        301: "Permanent redirect",
        302: "Temporary redirect",
        303: "See another resource, commonly after POST",
        307: "Temporary redirect preserving method semantics",
        308: "Permanent redirect preserving method semantics",
    }

    for code, explanation in redirect_codes.items():
        print(f"{code}: {explanation}")

    print(
        "\nA security-sensitive client should validate redirect destinations "
        "and avoid blindly forwarding credentials to a different origin."
    )


# ============================================================================
# 14. AUTHENTICATION BASICS
# ============================================================================

def basic_auth_header(username: str, password: str) -> str:
    credentials = f"{username}:{password}".encode("utf-8")
    encoded = base64.b64encode(credentials).decode("ascii")
    return f"Basic {encoded}"


def demonstrate_authentication() -> None:
    print_section("14. HTTP AUTHENTICATION")

    header = basic_auth_header("alice", "example-password")
    print(f"Authorization header: {header}")

    print(
        "\nBase64 is encoding, not encryption. Basic authentication therefore "
        "must normally be protected by TLS so credentials are not exposed "
        "to network observers."
    )

    print(
        "\nOther authentication approaches include bearer tokens, mutual TLS, "
        "signed requests, cookies-backed sessions, and application-specific "
        "authentication protocols."
    )


# ============================================================================
# 15. ORIGIN AND CORS CONCEPTS
# ============================================================================

def origin_from_url(url: str) -> Tuple[str, str, Optional[int]]:
    parsed = urllib.parse.urlsplit(url)

    if not parsed.scheme or not parsed.hostname:
        raise ValueError("URL must contain scheme and host.")

    default_port = {"http": 80, "https": 443}.get(parsed.scheme)

    return (
        parsed.scheme,
        parsed.hostname.lower(),
        parsed.port or default_port,
    )


def same_origin(url_a: str, url_b: str) -> bool:
    return origin_from_url(url_a) == origin_from_url(url_b)


def demonstrate_origin_security() -> None:
    print_section("15. ORIGINS AND CORS")

    first = "https://app.example.com/dashboard"
    second = "https://api.example.com/users"
    third = "https://app.example.com/settings"

    print(f"Origin A: {origin_from_url(first)}")
    print(f"Origin B: {origin_from_url(second)}")
    print(f"Same origin A/B: {same_origin(first, second)}")
    print(f"Same origin A/C: {same_origin(first, third)}")

    print(
        "\nAn origin is defined by scheme, host, and port. The browser's same-"
        "origin policy restricts many cross-origin operations. CORS provides "
        "a controlled mechanism for servers to declare which cross-origin "
        "browser requests are permitted."
    )


# ============================================================================
# 16. HTTP HEADER VALIDATION AND REQUEST-SMUGGLING AWARENESS
# ============================================================================

def validate_content_length(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("Content-Length must contain decimal digits.")

    length = int(value)

    if length < 0:
        raise ValueError("Content-Length cannot be negative.")

    return length


def demonstrate_message_framing() -> None:
    print_section("16. MESSAGE FRAMING AND SECURITY")

    examples = ["0", "42", "1024"]

    for value in examples:
        print(f"Content-Length {value!r} -> {validate_content_length(value)} bytes")

    print(
        "\nHTTP message framing is security-sensitive. Different components "
        "such as proxies and origin servers must agree on where a request "
        "ends. Ambiguous Content-Length and Transfer-Encoding handling has "
        "historically contributed to request-smuggling vulnerabilities."
    )

    print(
        "\nProduction systems should use mature, well-tested HTTP stacks "
        "rather than implementing a complete parser from scratch."
    )


# ============================================================================
# 17. CHUNKED TRANSFER ENCODING
# ============================================================================

def encode_chunked(body: bytes, chunk_size: int = 8) -> bytes:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    output = bytearray()

    for start in range(0, len(body), chunk_size):
        chunk = body[start:start + chunk_size]
        output.extend(f"{len(chunk):X}\r\n".encode("ascii"))
        output.extend(chunk)
        output.extend(b"\r\n")

    output.extend(b"0\r\n\r\n")
    return bytes(output)


def decode_chunked(encoded: bytes) -> bytes:
    position = 0
    output = bytearray()

    while True:
        line_end = encoded.find(b"\r\n", position)

        if line_end == -1:
            raise ValueError("Incomplete chunk-size line.")

        size_text = encoded[position:line_end]

        try:
            size = int(size_text.split(b";", 1)[0], 16)
        except ValueError as exc:
            raise ValueError("Invalid chunk size.") from exc

        position = line_end + 2

        if size == 0:
            if encoded[position:position + 2] != b"\r\n":
                raise ValueError("Invalid final chunk.")
            return bytes(output)

        if position + size + 2 > len(encoded):
            raise ValueError("Incomplete chunk.")

        output.extend(encoded[position:position + size])
        position += size

        if encoded[position:position + 2] != b"\r\n":
            raise ValueError("Missing chunk terminator.")

        position += 2


def demonstrate_chunked_encoding() -> None:
    print_section("17. CHUNKED TRANSFER ENCODING")

    body = b"Streaming HTTP content without knowing the final size first."

    encoded = encode_chunked(body, chunk_size=10)
    decoded = decode_chunked(encoded)

    print(f"Original: {body!r}")
    print(f"Encoded : {encoded!r}")
    print(f"Decoded : {decoded!r}")
    print(f"Round trip successful: {body == decoded}")


# ============================================================================
# 18. RANGE REQUESTS
# ============================================================================

def apply_byte_range(data: bytes, range_header: str) -> bytes:
    match = re.fullmatch(r"bytes=(\d+)-(\d*)", range_header.strip())

    if not match:
        raise ValueError("Only a single byte range is supported.")

    start = int(match.group(1))
    end_text = match.group(2)

    if start >= len(data):
        raise ValueError("Range is unsatisfiable.")

    end = len(data) - 1 if not end_text else int(end_text)

    if end < start:
        raise ValueError("Range end precedes range start.")

    return data[start:min(end + 1, len(data))]


def demonstrate_ranges() -> None:
    print_section("18. RANGE REQUESTS")

    document = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    fragment = apply_byte_range(document, "bytes=5-10")

    print(f"Resource : {document.decode()}")
    print(f"Range   : bytes=5-10")
    print(f"Result  : {fragment.decode()}")

    print(
        "\nRange requests support partial transfer, which is useful for "
        "large files, media seeking, resumable downloads, and bandwidth "
        "optimization."
    )


# ============================================================================
# 19. HTTP CONNECTIONS
# ============================================================================

def demonstrate_connection_behavior() -> None:
    print_section("19. CONNECTION MANAGEMENT")

    print("HTTP/1.0: connections were commonly short-lived by default.")
    print("HTTP/1.1: persistent connections became the normal behavior.")
    print("HTTP/2  : multiplexes streams over a connection.")
    print("HTTP/3  : uses QUIC over UDP and provides HTTP semantics over QUIC.")

    print(
        "\nConnection reuse reduces setup overhead. HTTP/2 multiplexing allows "
        "multiple request/response streams to share a connection. HTTP/3 "
        "changes the transport layer to QUIC while retaining HTTP concepts."
    )


# ============================================================================
# 20. HTTP/2 AND HTTP/3 CONCEPTS
# ============================================================================

def explain_modern_http() -> None:
    print_section("20. HTTP/2 AND HTTP/3 CONCEPTS")

    comparison = [
        ("HTTP/1.1", "Textual message format", "TCP", "Persistent connections"),
        ("HTTP/2", "Binary framing", "TCP", "Multiplexed streams"),
        ("HTTP/3", "Binary framing", "QUIC/UDP", "Multiplexed QUIC streams"),
    ]

    print(f"{'Version':10} | {'Framing':20} | {'Transport':12} | Feature")
    print("-" * 78)

    for row in comparison:
        print(f"{row[0]:10} | {row[1]:20} | {row[2]:12} | {row[3]}")

    print(
        "\nHTTP/2 and HTTP/3 are not simply 'encrypted HTTP/1.1'. They define "
        "different framing and transport interactions while preserving the "
        "core request/response semantics of HTTP."
    )


# ============================================================================
# 21. TLS CONCEPTS
# ============================================================================

def explain_tls() -> None:
    print_section("21. TLS FUNDAMENTALS")

    concepts = {
        "Confidentiality": "Encryption prevents passive observers from reading protected application data.",
        "Integrity": "Authenticated cryptography detects unauthorized modification.",
        "Authentication": "Certificates allow clients to authenticate the server identity.",
        "Key exchange": "Client and server establish shared cryptographic secrets.",
        "Handshake": "The protocol negotiates parameters and establishes protected session keys.",
        "Certificate chain": "A server certificate can chain through intermediates to a trusted root.",
        "Hostname verification": "The certificate identity must match the requested hostname.",
        "Forward secrecy": "Ephemeral key exchange can prevent later compromise of a long-term key from exposing old sessions.",
    }

    for name, description in concepts.items():
        print(f"{name:22}: {description}")

    print(
        "\nTLS does not make an application automatically secure. Application "
        "authorization, input validation, secure cookie configuration, "
        "dependency management, and correct protocol usage remain necessary."
    )


# ============================================================================
# 22. CERTIFICATE INSPECTION
# ============================================================================

def inspect_certificate(hostname: str, port: int = 443) -> None:
    print_section(f"22. TLS CERTIFICATE INSPECTION: {hostname}:{port}")

    context = ssl.create_default_context()

    try:
        with socket.create_connection((hostname, port), timeout=8) as raw_socket:
            with context.wrap_socket(
                raw_socket,
                server_hostname=hostname,
            ) as tls_socket:
                certificate = tls_socket.getpeercert()

                print(f"TLS version : {tls_socket.version()}")
                print(f"Cipher      : {tls_socket.cipher()}")

                subject = certificate.get("subject", ())
                issuer = certificate.get("issuer", ())
                san = certificate.get("subjectAltName", ())

                print(f"Subject     : {subject}")
                print(f"Issuer      : {issuer}")
                print(f"Subject Alt : {san[:10]}")

                not_before = certificate.get("notBefore")
                not_after = certificate.get("notAfter")

                print(f"Valid from  : {not_before}")
                print(f"Valid until : {not_after}")

    except (OSError, ssl.SSLError) as exc:
        print(f"Certificate inspection failed: {exc}")


# ============================================================================
# 23. TLS CERTIFICATE NAME MATCHING
# ============================================================================

def demonstrate_hostname_matching() -> None:
    print_section("23. CERTIFICATE HOSTNAME MATCHING")

    examples = [
        ("api.example.com", "*.example.com"),
        ("example.com", "*.example.com"),
        ("a.b.example.com", "*.example.com"),
    ]

    for hostname, pattern in examples:
        try:
            ssl.match_hostname(
                {
                    "subjectAltName": (
                        ("DNS", pattern),
                    )
                },
                hostname,
            )
            result = "match"
        except ssl.CertificateError:
            result = "no match"

        print(f"{hostname:25} vs {pattern:20} -> {result}")

    print(
        "\nModern certificate validation primarily relies on the Subject "
        "Alternative Name extension. Wildcard matching has defined scope and "
        "does not mean an arbitrary number of DNS labels."
    )


# ============================================================================
# 24. SECURE VS INSECURE CONTEXTS
# ============================================================================

def demonstrate_ssl_context_configuration() -> None:
    print_section("24. SECURE TLS CLIENT CONFIGURATION")

    context = ssl.create_default_context()

    print(f"Protocol context: {context.protocol}")
    print(f"Minimum TLS version: {context.minimum_version}")
    print(f"Certificate verification: {context.verify_mode}")
    print(f"Hostname checking: {context.check_hostname}")

    print(
        "\ncreate_default_context() enables certificate validation and hostname "
        "checking appropriate for ordinary secure client connections."
    )

    print(
        "\nAvoid disabling certificate verification merely to make a failing "
        "connection work. A disabled verification policy removes an important "
        "part of TLS server authentication."
    )


# ============================================================================
# 25. LOCAL HTTP SERVER
# ============================================================================

class LearningHTTPHandler(http.server.BaseHTTPRequestHandler):
    server_version = "HTTP-Learning-Server/1.0"

    def _send_json(self, status: int, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)

        if parsed.path == "/":
            self._send_json(
                200,
                {
                    "service": "HTTP learning server",
                    "method": "GET",
                    "path": parsed.path,
                    "query": urllib.parse.parse_qs(parsed.query),
                },
            )
            return

        if parsed.path == "/health":
            self._send_json(200, {"status": "healthy"})
            return

        self._send_json(
            404,
            {
                "error": "not_found",
                "path": parsed.path,
            },
        )

    def do_POST(self) -> None:
        content_length_text = self.headers.get("Content-Length")

        if content_length_text is None:
            self._send_json(411, {"error": "Content-Length required"})
            return

        try:
            content_length = validate_content_length(content_length_text)
        except ValueError:
            self._send_json(400, {"error": "invalid Content-Length"})
            return

        if content_length > 1_000_000:
            self._send_json(413, {"error": "request body too large"})
            return

        body = self.rfile.read(content_length)

        self._send_json(
            200,
            {
                "received_bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            },
        )

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"[HTTP SERVER] {format_string % args}")


def start_http_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = http.server.ThreadingHTTPServer(
        (host, port),
        LearningHTTPHandler,
    )

    print(f"HTTP server listening on http://{host}:{port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping HTTP server.")
    finally:
        server.server_close()


# ============================================================================
# 26. HTTP CLIENT USING STANDARD LIBRARY
# ============================================================================

def demonstrate_http_client() -> None:
    print_section("26. PYTHON HTTP CLIENT")

    connection = http.client.HTTPConnection(
        "example.com",
        timeout=8,
    )

    try:
        connection.request(
            "GET",
            "/",
            headers={
                "User-Agent": "HTTP-Learning-Client/1.0",
                "Accept": "text/html",
            },
        )

        response = connection.getresponse()

        print(f"Status : {response.status} {response.reason}")
        print(f"Type   : {response.getheader('Content-Type')}")
        print(f"Length : {response.getheader('Content-Length')}")

        body = response.read(500)
        print(f"First bytes:\n{body[:500]!r}")

    except OSError as exc:
        print(f"HTTP request failed: {exc}")
    finally:
        connection.close()


def demonstrate_https_client() -> None:
    print_section("27. PYTHON HTTPS CLIENT")

    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(
        "example.com",
        443,
        context=context,
        timeout=8,
    )

    try:
        connection.request(
            "GET",
            "/",
            headers={
                "User-Agent": "HTTPS-Learning-Client/1.0",
                "Accept": "text/html",
            },
        )

        response = connection.getresponse()

        print(f"Status : {response.status} {response.reason}")
        print(f"Server : {response.getheader('Server')}")
        print(f"Type   : {response.getheader('Content-Type')}")

        body = response.read(500)
        print(f"First bytes:\n{body[:500]!r}")

    except (OSError, ssl.SSLError) as exc:
        print(f"HTTPS request failed: {exc}")
    finally:
        connection.close()


# ============================================================================
# 28. HTTPS LOCAL SERVER
# ============================================================================

class LearningHTTPSServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


def start_https_server(
    host: str = "127.0.0.1",
    port: int = 8443,
    certificate_file: str = "server.crt",
    key_file: str = "server.key",
) -> None:
    print_section("28. LOCAL HTTPS SERVER")

    if not Path(certificate_file).exists():
        print(f"Certificate not found: {certificate_file}")
        print(
            "For development only, create a certificate and key with a trusted "
            "local certificate tool or OpenSSL. The certificate must contain "
            "the hostname used by the client, such as localhost."
        )
        return

    if not Path(key_file).exists():
        print(f"Private key not found: {key_file}")
        return

    server = LearningHTTPSServer(
        (host, port),
        LearningHTTPHandler,
    )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        certfile=certificate_file,
        keyfile=key_file,
    )

    server.socket = context.wrap_socket(
        server.socket,
        server_side=True,
    )

    print(f"HTTPS server listening on https://{host}:{port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping HTTPS server.")
    finally:
        server.server_close()


# ============================================================================
# 29. TIMEOUT AND RETRY DESIGN
# ============================================================================

class RetryPolicy:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.2,
        max_delay: float = 2.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one.")

        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    def delay_for(self, attempt: int) -> float:
        # Exponential backoff limits repeated pressure on an unavailable
        # service. Production systems often add jitter as well.
        delay = self.base_delay * (2 ** max(0, attempt - 1))
        return min(delay, self.max_delay)


def demonstrate_retry_policy() -> None:
    print_section("29. TIMEOUTS AND RETRIES")

    policy = RetryPolicy()

    for attempt in range(1, 5):
        print(f"Attempt {attempt}: delay={policy.delay_for(attempt):.2f}s")

    print(
        "\nNot every HTTP failure should be retried. Retrying a non-idempotent "
        "operation can duplicate side effects unless the application has an "
        "appropriate idempotency mechanism."
    )


# ============================================================================
# 30. RATE LIMITING
# ============================================================================

class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate-limit parameters must be positive.")

        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def allow(self, client_id: str, now: Optional[float] = None) -> bool:
        current = time.time() if now is None else now

        cutoff = current - self.window_seconds

        recent = [
            timestamp
            for timestamp in self.requests[client_id]
            if timestamp > cutoff
        ]

        self.requests[client_id] = recent

        if len(recent) >= self.limit:
            return False

        recent.append(current)
        return True


def demonstrate_rate_limiting() -> None:
    print_section("30. RATE LIMITING")

    limiter = FixedWindowRateLimiter(limit=3, window_seconds=60)

    for request_number in range(1, 6):
        allowed = limiter.allow("client-A", now=1000)
        print(f"Request {request_number}: {'allowed' if allowed else '429 Too Many Requests'}")


# ============================================================================
# 31. SECURE HTTP SERVER DESIGN CHECKLIST
# ============================================================================

def demonstrate_security_checklist() -> None:
    print_section("31. HTTP/HTTPS SECURITY CHECKLIST")

    checklist = [
        "Use HTTPS for sensitive traffic.",
        "Validate TLS certificates and hostnames.",
        "Do not disable TLS verification to bypass certificate errors.",
        "Use secure cookie attributes such as Secure, HttpOnly, and appropriate SameSite.",
        "Validate and constrain request sizes.",
        "Validate Content-Type and actual input structure.",
        "Apply authorization on the server, not only in browser code.",
        "Protect against injection by using context-appropriate escaping and parameterization.",
        "Avoid exposing secrets in URLs because URLs may appear in logs and other metadata.",
        "Use security headers appropriate to the application.",
        "Apply rate limits where abuse is possible.",
        "Set connection, read, and total operation timeouts.",
        "Treat redirects as security-sensitive.",
        "Keep HTTP parsing in mature libraries when building production software.",
        "Log security-relevant events without logging passwords or tokens.",
    ]

    for number, item in enumerate(checklist, start=1):
        print(f"{number:2}. {item}")


# ============================================================================
# 32. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    print_section("32. EDGE CASES AND FAILURE CONDITIONS")

    cases = [
        "",
        "https://example.com",
        "https://example.com:443/path",
        "https://example.com/search?q=a%20b",
        "http://localhost:8080/",
        "https://[::1]/",
    ]

    for value in cases:
        try:
            parsed = urllib.parse.urlsplit(value)

            if not parsed.scheme or not parsed.hostname:
                raise ValueError("Missing scheme or hostname.")

            print(
                f"{value!r:40} -> "
                f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 'default'}"
            )

        except (ValueError, IndexError) as exc:
            print(f"{value!r:40} -> ERROR: {exc}")

    malformed_headers = [
        "Good-Header: value\r\nAnother: value",
        "MissingColon",
        "Bad Header: value",
    ]

    for raw in malformed_headers:
        try:
            print(f"Headers {raw!r} -> {parse_http_headers(raw)}")
        except ValueError as exc:
            print(f"Headers {raw!r} -> ERROR: {exc}")


# ============================================================================
# 33. PERFORMANCE COMPARISON
# ============================================================================

def benchmark_hashing() -> None:
    print_section("33. PERFORMANCE CONSIDERATIONS")

    payload = os.urandom(1_000_000)

    start = time.perf_counter()
    digest = hashlib.sha256(payload).hexdigest()
    elapsed = time.perf_counter() - start

    print(f"SHA-256 digest: {digest}")
    print(f"Hashing 1 MB took approximately {elapsed:.6f} seconds.")

    print(
        "\nNetwork performance depends on latency, connection reuse, DNS, "
        "TLS handshakes, server processing, payload size, compression, "
        "congestion, HTTP version, and infrastructure."
    )

    print(
        "\nMicrobenchmarks vary by hardware and workload. A single local "
        "timing measurement should not be treated as a production capacity "
        "estimate."
    )


# ============================================================================
# 34. TESTING
# ============================================================================

def run_assertions() -> None:
    print_section("34. BUILT-IN TESTS")

    request = HTTPRequest(
        "GET",
        "/",
        headers={"Host": "example.com"},
    )

    raw = request.serialize()
    assert raw.startswith(b"GET / HTTP/1.1\r\n")

    parsed = parse_http_request(raw)
    assert parsed.method == "GET"
    assert parsed.target == "/"
    assert parsed.headers["host"] == "example.com"

    body = b"hello world"
    chunked = encode_chunked(body, 4)
    assert decode_chunked(chunked) == body

    assert apply_byte_range(b"abcdef", "bytes=1-3") == b"bcd"

    assert same_origin(
        "https://example.com/a",
        "https://example.com/b",
    )

    assert not same_origin(
        "http://example.com/a",
        "https://example.com/a",
    )

    assert validate_content_length("42") == 42

    try:
        validate_content_length("-1")
    except ValueError:
        pass
    else:
        raise AssertionError("Negative Content-Length should fail.")

    cookie_jar = SimpleCookieJar()
    cookie_jar.receive_set_cookie("session=xyz; Secure; HttpOnly")
    assert "session=xyz" in cookie_jar.cookie_header()

    cache = HTTPCache()
    entry = cache.store("https://example.com", b"cache me")
    assert entry.etag.startswith('"')
    assert cache.get("https://example.com") is entry

    limiter = FixedWindowRateLimiter(2, 60)
    assert limiter.allow("x", 100)
    assert limiter.allow("x", 100)
    assert not limiter.allow("x", 100)

    print("All educational assertions passed.")


# ============================================================================
# 35. REAL-WORLD REQUEST FLOW
# ============================================================================

def explain_real_world_flow() -> None:
    print_section("35. REAL-WORLD HTTPS REQUEST FLOW")

    steps = [
        "1. The application obtains a URL such as https://api.example.com/data.",
        "2. DNS resolution maps the hostname to one or more IP addresses.",
        "3. The client establishes the appropriate transport connection.",
        "4. For HTTPS, TLS negotiation establishes an authenticated protected channel.",
        "5. The client sends an HTTP request over that protected channel.",
        "6. A load balancer, proxy, CDN, or origin server may process the request.",
        "7. The application validates authentication, authorization, input, and request state.",
        "8. The server constructs an HTTP response with status, headers, and optional body.",
        "9. TLS protects the response while it travels back to the client.",
        "10. The client interprets status, headers, caching rules, cookies, and body.",
    ]

    for step in steps:
        print(step)

    print(
        "\nA production request can cross many components. Correct security "
        "requires understanding which component terminates TLS, which component "
        "sets security headers, where authentication occurs, and which component "
        "is authoritative for authorization."
    )


# ============================================================================
# 36. COMMAND-LINE ENTRY POINT
# ============================================================================

def run_learning_program() -> None:
    explain_terminology()
    demonstrate_url_structure()
    demonstrate_http_request()
    demonstrate_http_response()
    demonstrate_parsing()
    explain_status_codes()
    demonstrate_method_properties()
    demonstrate_content_types()
    demonstrate_url_encoding()
    demonstrate_cookies()
    demonstrate_caching()
    demonstrate_validators()
    demonstrate_redirects()
    demonstrate_authentication()
    demonstrate_origin_security()
    demonstrate_message_framing()
    demonstrate_chunked_encoding()
    demonstrate_ranges()
    demonstrate_connection_behavior()
    explain_modern_http()
    explain_tls()
    demonstrate_hostname_matching()
    demonstrate_ssl_context_configuration()
    demonstrate_retry_policy()
    demonstrate_rate_limiting()
    demonstrate_security_checklist()
    demonstrate_edge_cases()
    benchmark_hashing()
    run_assertions()
    explain_real_world_flow()

    print_section("OPTIONAL NETWORK DEMONSTRATIONS")
    print(
        "The following functions perform real network operations and are not "
        "called automatically so that the study script remains deterministic."
    )
    print("Call demonstrate_http_client() for a real HTTP request.")
    print("Call demonstrate_https_client() for a real HTTPS request.")
    print("Call inspect_certificate('example.com') to inspect a TLS certificate.")
    print("Call start_http_server() to launch the local HTTP server.")
    print("Call start_https_server() after providing server.crt/server.key.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Comprehensive HTTP and HTTPS learning program."
    )

    parser.add_argument(
        "--server",
        action="store_true",
        help="Start the local HTTP learning server.",
    )

    parser.add_argument(
        "--https-server",
        action="store_true",
        help="Start the local HTTPS learning server.",
    )

    parser.add_argument(
        "--inspect",
        metavar="HOST",
        help="Inspect the TLS certificate of a remote HTTPS host.",
    )

    args = parser.parse_args()

    if args.server:
        start_http_server()
        return

    if args.https_server:
        start_https_server()
        return

    if args.inspect:
        inspect_certificate(args.inspect)
        return

    run_learning_program()


if __name__ == "__main__":
    main()
