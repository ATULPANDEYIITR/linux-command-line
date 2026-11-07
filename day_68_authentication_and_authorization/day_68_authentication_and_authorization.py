#!/usr/bin/env python3
"""
Authentication and Authorization
Demonstrates:
- Secure password hashing with PBKDF2-HMAC-SHA256
- Password verification and account lockout
- Time-based one-time passwords (TOTP) for MFA
- HMAC-signed access tokens
- Token expiration and revocation
- OAuth 2.0 authorization-code flow with PKCE
- Role-based access control (RBAC)
- Permission and scope evaluation
- Session management and audit logging

Python 3.10+
Standard library only.

Production note:
Use Argon2id for password storage, an established OAuth/OIDC
provider, secure key management, HTTPS, and persistent storage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import urlparse


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

logger = logging.getLogger("authentication")


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PBKDF2_ITERATIONS = 600_000
TOKEN_LIFETIME = 900
SESSION_LIFETIME = 3600
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300

TOKEN_SECRET = secrets.token_bytes(32)


# ---------------------------------------------------------
# Exceptions
# ---------------------------------------------------------

class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class ValidationError(Exception):
    pass


class ExpiredTokenError(AuthenticationError):
    pass


# ---------------------------------------------------------
# Domain types
# ---------------------------------------------------------

class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    VIEWER = "viewer"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


@dataclass
class User:
    user_id: str
    username: str
    email: str
    password_salt: bytes
    password_hash: bytes
    role: Role
    mfa_secret: Optional[bytes] = None
    mfa_enabled: bool = False
    status: AccountStatus = AccountStatus.ACTIVE
    failed_attempts: int = 0
    locked_until: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str
    user_id: str
    created_at: float
    expires_at: float
    revoked: bool = False


@dataclass
class OAuthClient:
    client_id: str
    redirect_uri: str
    allowed_scopes: set[str]
    confidential: bool = False


@dataclass
class AuthorizationCode:
    code: str
    client_id: str
    user_id: str
    redirect_uri: str
    code_challenge: str
    scopes: set[str]
    expires_at: float
    consumed: bool = False


# ---------------------------------------------------------
# Password security
# ---------------------------------------------------------

class PasswordManager:

    @staticmethod
    def validate(password: str) -> None:
        if not isinstance(password, str):
            raise ValidationError("Password must be a string.")

        if len(password) < 12:
            raise ValidationError(
                "Password must contain at least 12 characters."
            )

        if len(password) > 1024:
            raise ValidationError("Password is too long.")

    @staticmethod
    def hash_password(password: str) -> tuple[bytes, bytes]:
        PasswordManager.validate(password)

        salt = secrets.token_bytes(16)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
            dklen=32
        )

        return salt, password_hash

    @staticmethod
    def verify(
        password: str,
        salt: bytes,
        expected_hash: bytes
    ) -> bool:

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
            dklen=32
        )

        return hmac.compare_digest(candidate, expected_hash)


# ---------------------------------------------------------
# Multi-factor authentication
# ---------------------------------------------------------

class TOTP:

    @staticmethod
    def generate_secret() -> bytes:
        return secrets.token_bytes(20)

    @staticmethod
    def generate(
        secret: bytes,
        timestamp: Optional[int] = None,
        interval: int = 30,
        digits: int = 6
    ) -> str:

        if not secret or interval <= 0:
            raise ValidationError("Invalid TOTP configuration.")

        timestamp = int(time.time()) if timestamp is None else timestamp
        counter = timestamp // interval

        message = counter.to_bytes(8, "big")

        digest = hmac.new(
            secret,
            message,
            hashlib.sha1
        ).digest()

        offset = digest[-1] & 0x0F

        binary = int.from_bytes(
            digest[offset:offset + 4],
            "big"
        ) & 0x7FFFFFFF

        return str(binary % (10 ** digits)).zfill(digits)

    @staticmethod
    def verify(
        secret: bytes,
        supplied_code: str,
        timestamp: Optional[int] = None,
        window: int = 1
    ) -> bool:

        if not supplied_code.isdigit() or len(supplied_code) != 6:
            return False

        now = int(time.time()) if timestamp is None else timestamp

        for offset in range(-window, window + 1):
            expected = TOTP.generate(
                secret,
                now + offset * 30
            )

            if hmac.compare_digest(expected, supplied_code):
                return True

        return False


# ---------------------------------------------------------
# Access control
# ---------------------------------------------------------

ROLE_PERMISSIONS = {
    Role.ADMIN: {
        "users.read",
        "users.create",
        "users.update",
        "users.delete",
        "reports.read",
        "reports.export",
        "settings.manage"
    },

    Role.MANAGER: {
        "users.read",
        "users.update",
        "reports.read",
        "reports.export"
    },

    Role.ANALYST: {
        "reports.read",
        "reports.export"
    },

    Role.VIEWER: {
        "reports.read"
    }
}


class AccessControl:

    @staticmethod
    def has_permission(
        role: Role,
        permission: str,
        token_scopes: Optional[set[str]] = None
    ) -> bool:

        role_permissions = ROLE_PERMISSIONS.get(role, set())

        if permission not in role_permissions:
            return False

        if token_scopes is not None:
            return permission in token_scopes

        return True

    @staticmethod
    def require_permission(
        role: Role,
        permission: str,
        token_scopes: Optional[set[str]] = None
    ) -> None:

        if not AccessControl.has_permission(
            role,
            permission,
            token_scopes
        ):
            raise AuthorizationError(
                f"Access denied: {permission}"
            )


# ---------------------------------------------------------
# Token management
# ---------------------------------------------------------

class TokenManager:

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValidationError("Signing secret must be at least 32 bytes.")

        self.secret = secret
        self.revoked_tokens: set[str] = set()

    @staticmethod
    def _encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(
            value + "=" * (-len(value) % 4)
        )

    def issue(
        self,
        user_id: str,
        scopes: set[str],
        lifetime: int = TOKEN_LIFETIME
    ) -> str:

        if lifetime <= 0 or lifetime > 86400:
            raise ValidationError("Invalid token lifetime.")

        now = int(time.time())

        header = {
            "alg": "HS256",
            "typ": "JWT"
        }

        payload = {
            "sub": user_id,
            "scope": sorted(scopes),
            "iat": now,
            "exp": now + lifetime,
            "jti": secrets.token_hex(16)
        }

        encoded_header = self._encode(
            json.dumps(header, separators=(",", ":")).encode()
        )

        encoded_payload = self._encode(
            json.dumps(payload, separators=(",", ":")).encode()
        )

        signing_input = (
            encoded_header + "." + encoded_payload
        ).encode()

        signature = hmac.new(
            self.secret,
            signing_input,
            hashlib.sha256
        ).digest()

        return (
            encoded_header
            + "."
            + encoded_payload
            + "."
            + self._encode(signature)
        )

    def verify(self, token: str) -> dict:

        try:
            if token in self.revoked_tokens:
                raise AuthenticationError("Token revoked.")

            parts = token.split(".")

            if len(parts) != 3:
                raise AuthenticationError("Malformed token.")

            header_part, payload_part, signature_part = parts

            signing_input = (
                header_part + "." + payload_part
            ).encode()

            expected_signature = hmac.new(
                self.secret,
                signing_input,
                hashlib.sha256
            ).digest()

            supplied_signature = self._decode(signature_part)

            if not hmac.compare_digest(
                expected_signature,
                supplied_signature
            ):
                raise AuthenticationError("Invalid signature.")

            header = json.loads(self._decode(header_part))
            payload = json.loads(self._decode(payload_part))

            if header.get("alg") != "HS256":
                raise AuthenticationError("Unsupported algorithm.")

            if header.get("typ") != "JWT":
                raise AuthenticationError("Invalid token type.")

            if not all(
                key in payload
                for key in ("sub", "exp", "iat", "jti", "scope")
            ):
                raise AuthenticationError("Missing token claims.")

            now = int(time.time())

            if payload["exp"] <= now:
                raise ExpiredTokenError("Token expired.")

            if payload["iat"] > now + 30:
                raise AuthenticationError("Invalid issue time.")

            if not isinstance(payload["scope"], list):
                raise AuthenticationError("Invalid scopes.")

            if not all(
                isinstance(scope, str)
                for scope in payload["scope"]
            ):
                raise AuthenticationError("Invalid scope values.")

            return payload

        except (ValueError, TypeError, KeyError, UnicodeDecodeError):
            raise AuthenticationError("Invalid token encoding.") from None

    def revoke(self, token: str) -> None:
        self.verify(token)
        self.revoked_tokens.add(token)


# ---------------------------------------------------------
# OAuth 2.0 with PKCE
# ---------------------------------------------------------

class OAuthServer:

    def __init__(self):
        self.clients: dict[str, OAuthClient] = {}
        self.authorization_codes: dict[str, AuthorizationCode] = {}

    def register_client(self, client: OAuthClient) -> None:

        parsed = urlparse(client.redirect_uri)

        if (
            not client.client_id
            or not parsed.scheme
            or not parsed.netloc
            or parsed.scheme != "https"
        ):
            raise ValidationError("Invalid OAuth client configuration.")

        if client.client_id in self.clients:
            raise ValidationError("Client already registered.")

        self.clients[client.client_id] = client

    def authorize(
        self,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        requested_scopes: set[str],
        code_challenge: str,
        state: str
    ) -> tuple[str, str]:

        client = self.clients.get(client_id)

        if client is None:
            raise AuthenticationError("Unknown OAuth client.")

        if redirect_uri != client.redirect_uri:
            raise AuthenticationError("Redirect URI mismatch.")

        if not state or len(state) < 16:
            raise ValidationError("Invalid OAuth state.")

        if not code_challenge:
            raise ValidationError("PKCE challenge required.")

        if not requested_scopes.issubset(client.allowed_scopes):
            raise AuthorizationError("Requested scopes not permitted.")

        code = secrets.token_urlsafe(32)

        self.authorization_codes[code] = AuthorizationCode(
            code=code,
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            scopes=requested_scopes.copy(),
            expires_at=time.time() + 300
        )

        return code, state

    def exchange_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        verifier: str
    ) -> tuple[str, set[str]]:

        authorization = self.authorization_codes.get(code)

        if authorization is None:
            raise AuthenticationError("Invalid authorization code.")

        if authorization.consumed:
            raise AuthenticationError("Authorization code already used.")

        if authorization.expires_at <= time.time():
            raise AuthenticationError("Authorization code expired.")

        if authorization.client_id != client_id:
            raise AuthenticationError("Client mismatch.")

        if authorization.redirect_uri != redirect_uri:
            raise AuthenticationError("Redirect mismatch.")

        if not 43 <= len(verifier) <= 128:
            raise ValidationError("Invalid PKCE verifier.")

        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()

        if not hmac.compare_digest(
            challenge,
            authorization.code_challenge
        ):
            raise AuthenticationError("PKCE verification failed.")

        # Consume before returning credentials to prevent code reuse.
        authorization.consumed = True

        return authorization.user_id, authorization.scopes.copy()


# ---------------------------------------------------------
# Authentication service
# ---------------------------------------------------------

class AuthenticationService:

    def __init__(self):
        self.users: dict[str, User] = {}
        self.username_index: dict[str, str] = {}
        self.sessions: dict[str, Session] = {}
        self.audit_log: list[dict] = []
        self.tokens = TokenManager(TOKEN_SECRET)

    def _audit(self, event: str, user_id: str, success: bool) -> None:

        self.audit_log.append({
            "event": event,
            "user_id": user_id,
            "success": success,
            "timestamp": int(time.time())
        })

    def register(
        self,
        username: str,
        email: str,
        password: str,
        role: Role
    ) -> User:

        if not username or len(username) < 3:
            raise ValidationError("Invalid username.")

        if "@" not in email:
            raise ValidationError("Invalid email address.")

        if username.lower() in self.username_index:
            raise ValidationError("Username already exists.")

        salt, password_hash = PasswordManager.hash_password(password)

        user = User(
            user_id=secrets.token_hex(12),
            username=username,
            email=email,
            password_salt=salt,
            password_hash=password_hash,
            role=role
        )

        self.users[user.user_id] = user
        self.username_index[username.lower()] = user.user_id

        self._audit("registration", user.user_id, True)

        return user

    def enable_mfa(self, user_id: str) -> str:

        user = self.users.get(user_id)

        if user is None or user.status != AccountStatus.ACTIVE:
            raise AuthenticationError("Invalid account.")

        user.mfa_secret = TOTP.generate_secret()
        user.mfa_enabled = True

        return base64.b32encode(
            user.mfa_secret
        ).decode().rstrip("=")

    def login(
        self,
        username: str,
        password: str,
        mfa_code: Optional[str] = None
    ) -> Session:

        user_id = self.username_index.get(username.lower())

        if user_id is None:
            self._audit("login", "unknown", False)
            raise AuthenticationError("Invalid credentials.")

        user = self.users[user_id]
        now = time.time()

        if user.status == AccountStatus.DISABLED:
            raise AuthenticationError("Account disabled.")

        if user.status == AccountStatus.LOCKED:

            if now < user.locked_until:
                raise AuthenticationError("Account temporarily locked.")

            user.status = AccountStatus.ACTIVE
            user.failed_attempts = 0

        password_valid = PasswordManager.verify(
            password,
            user.password_salt,
            user.password_hash
        )

        if not password_valid:
            user.failed_attempts += 1

            if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
                user.status = AccountStatus.LOCKED
                user.locked_until = now + LOCKOUT_SECONDS

            self._audit("login", user.user_id, False)

            raise AuthenticationError("Invalid credentials.")

        if user.mfa_enabled:

            if (
                not mfa_code
                or not TOTP.verify(user.mfa_secret, mfa_code)
            ):
                self._audit("mfa", user.user_id, False)
                raise AuthenticationError("MFA verification failed.")

        user.failed_attempts = 0

        session = Session(
            session_id=secrets.token_urlsafe(32),
            user_id=user.user_id,
            created_at=now,
            expires_at=now + SESSION_LIFETIME
        )

        self.sessions[session.session_id] = session

        self._audit("login", user.user_id, True)

        return session

    def validate_session(self, session_id: str) -> User:

        session = self.sessions.get(session_id)

        if (
            session is None
            or session.revoked
            or session.expires_at <= time.time()
        ):
            raise AuthenticationError("Invalid or expired session.")

        user = self.users.get(session.user_id)

        if user is None or user.status != AccountStatus.ACTIVE:
            raise AuthenticationError("Account unavailable.")

        return user

    def logout(self, session_id: str) -> None:

        session = self.sessions.get(session_id)

        if session:
            session.revoked = True
            self._audit("logout", session.user_id, True)


# ---------------------------------------------------------
# Demonstration
# ---------------------------------------------------------

def main() -> None:

    print("\n=== AUTHENTICATION AND AUTHORIZATION ===")

    service = AuthenticationService()

    admin = service.register(
        "admin_user",
        "admin@example.com",
        "Admin-Strong-Password-2026!",
        Role.ADMIN
    )

    analyst = service.register(
        "analyst_user",
        "analyst@example.com",
        "Analyst-Strong-Password-2026!",
        Role.ANALYST
    )

    # Configure MFA.
    encoded_secret = service.enable_mfa(admin.user_id)

    print("MFA configured:", bool(encoded_secret))

    # Generate a current demonstration code.
    admin_code = TOTP.generate(admin.mfa_secret)

    admin_session = service.login(
        "admin_user",
        "Admin-Strong-Password-2026!",
        admin_code
    )

    print("Admin authenticated:", True)

    authenticated_user = service.validate_session(
        admin_session.session_id
    )

    AccessControl.require_permission(
        authenticated_user.role,
        "users.delete"
    )

    print("Admin permission granted: users.delete")

    analyst_session = service.login(
        "analyst_user",
        "Analyst-Strong-Password-2026!"
    )

    analyst_user = service.validate_session(
        analyst_session.session_id
    )

    print(
        "Analyst can read reports:",
        AccessControl.has_permission(
            analyst_user.role,
            "reports.read"
        )
    )

    print(
        "Analyst can delete users:",
        AccessControl.has_permission(
            analyst_user.role,
            "users.delete"
        )
    )

    # Issue and verify a scoped access token.
    token = service.tokens.issue(
        analyst_user.user_id,
        {"reports.read"},
        lifetime=900
    )

    claims = service.tokens.verify(token)

    print("Access token subject:", claims["sub"])

    AccessControl.require_permission(
        analyst_user.role,
        "reports.read",
        set(claims["scope"])
    )

    print("Scoped token authorization: granted")

    # OAuth authorization-code flow with PKCE.
    oauth = OAuthServer()

    client = OAuthClient(
        client_id="reporting_application",
        redirect_uri="https://client.example.com/callback",
        allowed_scopes={"reports.read", "reports.export"}
    )

    oauth.register_client(client)

    verifier = secrets.token_urlsafe(48)

    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    authorization_code, state = oauth.authorize(
        client_id=client.client_id,
        user_id=analyst_user.user_id,
        redirect_uri=client.redirect_uri,
        requested_scopes={"reports.read"},
        code_challenge=challenge,
        state=secrets.token_urlsafe(24)
    )

    oauth_user, oauth_scopes = oauth.exchange_code(
        authorization_code,
        client.client_id,
        client.redirect_uri,
        verifier
    )

    print("OAuth identity:", oauth_user)
    print("OAuth scopes:", sorted(oauth_scopes))
    print("OAuth state returned:", bool(state))

    # Authorization code cannot be reused.
    try:
        oauth.exchange_code(
            authorization_code,
            client.client_id,
            client.redirect_uri,
            verifier
        )
    except AuthenticationError as error:
        print("Replay prevented:", error)

    # Token revocation.
    service.tokens.revoke(token)

    try:
        service.tokens.verify(token)
    except AuthenticationError as error:
        print("Revoked token rejected:", error)

    # Session termination.
    service.logout(admin_session.session_id)

    try:
        service.validate_session(admin_session.session_id)
    except AuthenticationError as error:
        print("Logged-out session rejected:", error)

    print("Audit events:", len(service.audit_log))

    # Basic security assertions.
    assert not AccessControl.has_permission(
        Role.VIEWER,
        "users.delete"
    )

    assert AccessControl.has_permission(
        Role.ADMIN,
        "users.delete"
    )

    assert TOTP.verify(
        analyst.mfa_secret or b"unused",
        "000000"
    ) is False

    print("\nAll demonstration checks passed.")


if __name__ == "__main__":
    main()
