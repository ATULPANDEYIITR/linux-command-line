#!/usr/bin/env python3
"""
Key Management Lifecycle Simulator

Demonstrates:
- Encryption key generation and lifecycle management
- Key versioning and rotation
- Envelope encryption
- HMAC-based authenticated educational encryption
- Secrets management
- Access control and audit logging
- Simulated HSM-backed key protection
- Key revocation and expiration
- Automated lifecycle validation

Security note:
The standard-library encryption construction is educational only.
Production systems should use vetted AES-256-GCM or ChaCha20-Poly1305
implementations and a managed KMS or HSM.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

LOGGER = logging.getLogger("key_management")


class KeyErrorBase(Exception):
    pass


class KeyNotFoundError(KeyErrorBase):
    pass


class KeyAccessDenied(KeyErrorBase):
    pass


class InvalidKeyState(KeyErrorBase):
    pass


class KeyPurpose(Enum):
    ENCRYPTION = "encryption"
    SIGNING = "signing"
    HMAC = "hmac"
    KEY_ENCRYPTION = "key_encryption"


class KeyStatus(Enum):
    ACTIVE = "active"
    ROTATED = "rotated"
    DISABLED = "disabled"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Role(Enum):
    ADMIN = "admin"
    CRYPTO_OPERATOR = "crypto_operator"
    APPLICATION = "application"
    AUDITOR = "auditor"


@dataclass
class Principal:
    principal_id: str
    role: Role


@dataclass
class KeyVersion:
    key_id: str
    version: int
    purpose: KeyPurpose
    algorithm: str
    material: bytes = field(repr=False)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: Optional[datetime] = None
    status: KeyStatus = KeyStatus.ACTIVE
    hardware_protected: bool = False
    parent_key_id: Optional[str] = None

    def metadata(self) -> dict:
        return {
            "key_id": self.key_id,
            "version": self.version,
            "purpose": self.purpose.value,
            "algorithm": self.algorithm,
            "created_at": self.created_at.isoformat(),
            "expires_at": (
                self.expires_at.isoformat()
                if self.expires_at else None
            ),
            "status": self.status.value,
            "hardware_protected": self.hardware_protected
        }


class AuditLog:
    def __init__(self):
        self.events = []

    def record(self, actor, action, key_id, outcome, details=""):
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "key_id": key_id,
            "outcome": outcome,
            "details": details
        }
        self.events.append(event)
        LOGGER.info(
            "%s | %s | %s | %s",
            actor, action, key_id, outcome
        )


class SimulatedHSM:
    """
    Models an HSM boundary.

    In a real HSM, private key material remains inside the
    hardware security boundary and operations are performed
    through authenticated cryptographic interfaces.
    """

    def generate_key(self, size=32):
        if size not in (16, 24, 32):
            raise ValueError("Unsupported key size")
        return secrets.token_bytes(size)

    def protect(self, material):
        if not material:
            raise ValueError("Empty key material")
        return hashlib.sha256(
            b"educational-hsm-boundary" + material
        ).hexdigest()


class KeyManager:
    def __init__(self, hsm=None, rotation_days=90):
        self.hsm = hsm or SimulatedHSM()
        self.rotation_days = rotation_days
        self.keys: dict[str, list[KeyVersion]] = {}
        self.audit = AuditLog()

    @staticmethod
    def _authorize(principal, allowed):
        if principal.role not in allowed:
            raise KeyAccessDenied(
                f"{principal.principal_id} lacks permission"
            )

    def create_key(
        self,
        principal: Principal,
        purpose: KeyPurpose,
        hardware_protected=True
    ) -> KeyVersion:

        self._authorize(
            principal,
            {Role.ADMIN, Role.CRYPTO_OPERATOR}
        )

        key_id = secrets.token_hex(12)
        material = self.hsm.generate_key(32)

        version = KeyVersion(
            key_id=key_id,
            version=1,
            purpose=purpose,
            algorithm="HMAC-SHA256-STREAM-DEMO",
            material=material,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.rotation_days),
            hardware_protected=hardware_protected
        )

        self.keys[key_id] = [version]

        self.audit.record(
            principal.principal_id,
            "CREATE",
            key_id,
            "SUCCESS"
        )

        return version

    def get_active_key(self, key_id):
        versions = self.keys.get(key_id)

        if not versions:
            raise KeyNotFoundError(key_id)

        key = versions[-1]

        if key.status != KeyStatus.ACTIVE:
            raise InvalidKeyState("Key is not active")

        if key.expires_at and datetime.now(
            timezone.utc
        ) >= key.expires_at:
            key.status = KeyStatus.EXPIRED
            raise InvalidKeyState("Key has expired")

        return key

    def rotate_key(self, principal, key_id):
        self._authorize(
            principal,
            {Role.ADMIN, Role.CRYPTO_OPERATOR}
        )

        current = self.get_active_key(key_id)

        current.status = KeyStatus.ROTATED

        new_version = KeyVersion(
            key_id=key_id,
            version=current.version + 1,
            purpose=current.purpose,
            algorithm=current.algorithm,
            material=self.hsm.generate_key(32),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.rotation_days),
            hardware_protected=current.hardware_protected
        )

        self.keys[key_id].append(new_version)

        self.audit.record(
            principal.principal_id,
            "ROTATE",
            key_id,
            "SUCCESS",
            f"Version {new_version.version}"
        )

        return new_version

    def revoke_key(self, principal, key_id):
        self._authorize(
            principal,
            {Role.ADMIN}
        )

        versions = self.keys.get(key_id)

        if not versions:
            raise KeyNotFoundError(key_id)

        for version in versions:
            version.status = KeyStatus.REVOKED

        self.audit.record(
            principal.principal_id,
            "REVOKE",
            key_id,
            "SUCCESS"
        )

    def disable_key(self, principal, key_id):
        self._authorize(
            principal,
            {Role.ADMIN, Role.CRYPTO_OPERATOR}
        )

        key = self.get_active_key(key_id)
        key.status = KeyStatus.DISABLED

        self.audit.record(
            principal.principal_id,
            "DISABLE",
            key_id,
            "SUCCESS"
        )

    def list_metadata(self):
        return [
            version.metadata()
            for versions in self.keys.values()
            for version in versions
        ]

    def export_audit(self, filename):
        """
        Stores audit metadata, not encryption key material.
        Restrict filesystem permissions in production.
        """
        path = Path(filename)
        path.write_text(
            json.dumps(self.audit.events, indent=2),
            encoding="utf-8"
        )


class EducationalEnvelopeCipher:
    """
    Educational authenticated encryption construction.

    This is NOT a production cryptographic primitive.

    It derives a keystream using HMAC-SHA256 and authenticates
    ciphertext using a separate derived authentication key.

    Production systems must use a standardized AEAD cipher.
    """

    @staticmethod
    def _derive(master_key, label):
        return hmac.new(
            master_key,
            label,
            hashlib.sha256
        ).digest()

    @staticmethod
    def _stream(key, nonce, length):
        output = bytearray()
        counter = 0

        while len(output) < length:
            block = hmac.new(
                key,
                nonce + counter.to_bytes(8, "big"),
                hashlib.sha256
            ).digest()

            output.extend(block)
            counter += 1

        return bytes(output[:length])

    @classmethod
    def encrypt(cls, plaintext, key):
        if len(key) != 32:
            raise ValueError("Expected a 256-bit key")

        nonce = secrets.token_bytes(16)

        encryption_key = cls._derive(
            key, b"encryption"
        )

        authentication_key = cls._derive(
            key, b"authentication"
        )

        stream = cls._stream(
            encryption_key,
            nonce,
            len(plaintext)
        )

        ciphertext = bytes(
            a ^ b for a, b in zip(plaintext, stream)
        )

        tag = hmac.new(
            authentication_key,
            nonce + ciphertext,
            hashlib.sha256
        ).digest()

        return {
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(
                ciphertext
            ).decode(),
            "tag": base64.b64encode(tag).decode()
        }

    @classmethod
    def decrypt(cls, envelope, key):
        nonce = base64.b64decode(
            envelope["nonce"],
            validate=True
        )

        ciphertext = base64.b64decode(
            envelope["ciphertext"],
            validate=True
        )

        supplied_tag = base64.b64decode(
            envelope["tag"],
            validate=True
        )

        authentication_key = cls._derive(
            key, b"authentication"
        )

        expected_tag = hmac.new(
            authentication_key,
            nonce + ciphertext,
            hashlib.sha256
        ).digest()

        if not hmac.compare_digest(
            supplied_tag, expected_tag
        ):
            raise ValueError(
                "Authentication failed: data modified"
            )

        encryption_key = cls._derive(
            key, b"encryption"
        )

        stream = cls._stream(
            encryption_key,
            nonce,
            len(ciphertext)
        )

        return bytes(
            a ^ b for a, b in zip(ciphertext, stream)
        )


class SecretsVault:
    """
    Stores encrypted application secrets.

    Only ciphertext and key references are retained.
    """

    def __init__(self, manager):
        self.manager = manager
        self.secrets = {}

    def store(self, principal, name, plaintext, key_id):
        if principal.role != Role.APPLICATION:
            raise KeyAccessDenied(
                "Application role required"
            )

        if not name or len(name) > 128:
            raise ValueError("Invalid secret name")

        if name in self.secrets:
            raise ValueError("Secret already exists")

        key = self.manager.get_active_key(key_id)

        envelope = EducationalEnvelopeCipher.encrypt(
            plaintext.encode("utf-8"),
            key.material
        )

        self.secrets[name] = {
            "key_id": key_id,
            "version": key.version,
            "envelope": envelope
        }

    def retrieve(self, principal, name):
        if principal.role not in {
            Role.APPLICATION,
            Role.ADMIN
        }:
            raise KeyAccessDenied(
                "Secret retrieval denied"
            )

        record = self.secrets.get(name)

        if record is None:
            raise KeyNotFoundError(name)

        versions = self.manager.keys[
            record["key_id"]
        ]

        matching = next(
            (
                item for item in versions
                if item.version == record["version"]
            ),
            None
        )

        if matching is None:
            raise KeyNotFoundError(
                "Encryption key version unavailable"
            )

        if matching.status == KeyStatus.REVOKED:
            raise InvalidKeyState(
                "Secret uses a revoked key"
            )

        plaintext = EducationalEnvelopeCipher.decrypt(
            record["envelope"],
            matching.material
        )

        return plaintext.decode("utf-8")

    def reencrypt(self, principal, name):
        if principal.role not in {
            Role.ADMIN,
            Role.CRYPTO_OPERATOR
        }:
            raise KeyAccessDenied(
                "Re-encryption denied"
            )

        record = self.secrets.get(name)

        if record is None:
            raise KeyNotFoundError(name)

        old_key = next(
            item for item in self.manager.keys[
                record["key_id"]
            ]
            if item.version == record["version"]
        )

        plaintext = EducationalEnvelopeCipher.decrypt(
            record["envelope"],
            old_key.material
        )

        new_key = self.manager.get_active_key(
            record["key_id"]
        )

        record["envelope"] = (
            EducationalEnvelopeCipher.encrypt(
                plaintext,
                new_key.material
            )
        )

        record["version"] = new_key.version

        self.manager.audit.record(
            principal.principal_id,
            "REENCRYPT",
            record["key_id"],
            "SUCCESS",
            name
        )


def demonstrate():
    admin = Principal("security-admin", Role.ADMIN)
    operator = Principal(
        "crypto-operator", Role.CRYPTO_OPERATOR
    )
    application = Principal(
        "payment-service", Role.APPLICATION
    )

    manager = KeyManager(rotation_days=90)
    vault = SecretsVault(manager)

    # Generate a dedicated key-encryption key.
    key = manager.create_key(
        operator,
        KeyPurpose.KEY_ENCRYPTION
    )

    print("\n1. Initial key")
    print(json.dumps(key.metadata(), indent=2))

    # Store an application secret.
    vault.store(
        application,
        "database-password",
        "Example-Database-Secret-2026",
        key.key_id
    )

    print("\n2. Retrieve secret")
    print(vault.retrieve(
        application,
        "database-password"
    ))

    # Rotate the key while preserving old key versions.
    manager.rotate_key(operator, key.key_id)

    print("\n3. Key versions")
    print(json.dumps(
        manager.list_metadata(),
        indent=2
    ))

    # Re-encrypt data using the new active version.
    vault.reencrypt(
        operator,
        "database-password"
    )

    print("\n4. Retrieve after re-encryption")
    print(vault.retrieve(
        application,
        "database-password"
    ))

    # Tampering detection.
    envelope = vault.secrets[
        "database-password"
    ]["envelope"].copy()

    envelope["ciphertext"] = base64.b64encode(
        b"tampered"
    ).decode()

    try:
        EducationalEnvelopeCipher.decrypt(
            envelope,
            manager.get_active_key(
                key.key_id
            ).material
        )
    except ValueError as exc:
        print("\n5. Tampering detected:", exc)

    # Unauthorized access.
    try:
        vault.retrieve(
            Principal("unauthorized-user", Role.AUDITOR),
            "database-password"
        )
    except KeyAccessDenied as exc:
        print("\n6. Access denied:", exc)

    # Key revocation.
    manager.revoke_key(admin, key.key_id)

    try:
        manager.get_active_key(key.key_id)
    except InvalidKeyState as exc:
        print("\n7. Revocation enforced:", exc)

    print("\n8. Audit records")
    for event in manager.audit.events:
        print(
            event["action"],
            event["key_id"],
            event["outcome"]
        )

    # Fundamental integrity assertions.
    assert len(manager.keys[key.key_id]) == 2
    assert all(
        version.status == KeyStatus.REVOKED
        for version in manager.keys[key.key_id]
    )

    LOGGER.info("All demonstration checks completed")


if __name__ == "__main__":
    demonstrate()
