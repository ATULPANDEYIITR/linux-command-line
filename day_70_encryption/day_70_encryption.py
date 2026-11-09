#!/usr/bin/env python3
"""
Encryption Engineering Laboratory

Demonstrates:
- Encryption at rest using AES-256-GCM.
- Encryption in transit using TLS configuration validation.
- Symmetric encryption and authenticated decryption.
- RSA public-key cryptography.
- Hybrid encryption using AES-GCM and RSA-OAEP.
- Key lifecycle management and rotation.
- Tamper detection, input validation, and failure handling.

Dependency:
    python -m pip install cryptography

Run:
    python encryption_lab.py
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import unittest

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("encryption_lab")


class EncryptionError(Exception):
    """Base exception for encryption operations."""


class ValidationError(EncryptionError):
    """Raised when cryptographic input is invalid."""


class DecryptionError(EncryptionError):
    """Raised when authentication or decryption fails."""


class KeyStatus(Enum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"


class EncryptionMode(Enum):
    AT_REST = "at_rest"
    IN_TRANSIT = "in_transit"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class EncryptedPayload:
    algorithm: str
    key_id: str
    nonce: str
    ciphertext: str
    created_at: str
    mode: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "EncryptedPayload":
        try:
            data = json.loads(value)
            return cls(**data)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValidationError("Invalid encrypted payload format") from exc


@dataclass
class ManagedKey:
    key_id: str
    material: bytes
    status: KeyStatus
    created_at: datetime


class KeyManager:
    """Manages encryption keys and their lifecycle."""

    def __init__(self) -> None:
        self._keys: dict[str, ManagedKey] = {}
        self._active_key_id: str | None = None

    def generate_key(self, key_id: str) -> ManagedKey:
        if not key_id or len(key_id) > 100:
            raise ValidationError("Invalid key identifier")

        if key_id in self._keys:
            raise ValidationError("Key identifier already exists")

        key = ManagedKey(
            key_id=key_id,
            material=AESGCM.generate_key(bit_length=256),
            status=KeyStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
        )

        self._keys[key_id] = key
        self._active_key_id = key_id

        logger.info("Generated encryption key: %s", key_id)
        return key

    def get_key(self, key_id: str) -> ManagedKey:
        key = self._keys.get(key_id)

        if key is None:
            raise ValidationError("Unknown key identifier")

        if key.status == KeyStatus.REVOKED:
            raise ValidationError("Key has been revoked")

        return key

    def active_key(self) -> ManagedKey:
        if self._active_key_id is None:
            raise ValidationError("No active encryption key")

        return self.get_key(self._active_key_id)

    def rotate(self, new_key_id: str) -> ManagedKey:
        previous = self.active_key()
        previous.status = KeyStatus.ROTATED

        return self.generate_key(new_key_id)

    def revoke(self, key_id: str) -> None:
        key = self.get_key(key_id)
        key.status = KeyStatus.REVOKED

        if self._active_key_id == key_id:
            self._active_key_id = None

        logger.warning("Key revoked: %s", key_id)


class SymmetricEncryption:
    """AES-256-GCM authenticated encryption."""

    ALGORITHM = "AES-256-GCM"

    def __init__(self, manager: KeyManager) -> None:
        self.manager = manager

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: bytes = b"",
    ) -> EncryptedPayload:

        if not isinstance(plaintext, bytes):
            raise ValidationError("Plaintext must be bytes")

        if len(plaintext) > 10_000_000:
            raise ValidationError("Plaintext exceeds size limit")

        if not isinstance(associated_data, bytes):
            raise ValidationError("Associated data must be bytes")

        key = self.manager.active_key()
        nonce = os.urandom(12)

        ciphertext = AESGCM(key.material).encrypt(
            nonce,
            plaintext,
            associated_data,
        )

        return EncryptedPayload(
            algorithm=self.ALGORITHM,
            key_id=key.key_id,
            nonce=base64.b64encode(nonce).decode("ascii"),
            ciphertext=base64.b64encode(ciphertext).decode("ascii"),
            created_at=datetime.now(timezone.utc).isoformat(),
            mode=EncryptionMode.AT_REST.value,
        )

    def decrypt(
        self,
        payload: EncryptedPayload,
        associated_data: bytes = b"",
    ) -> bytes:

        if payload.algorithm != self.ALGORITHM:
            raise ValidationError("Unsupported encryption algorithm")

        try:
            nonce = base64.b64decode(payload.nonce, validate=True)
            ciphertext = base64.b64decode(
                payload.ciphertext,
                validate=True,
            )

            if len(nonce) != 12:
                raise ValidationError("Invalid AES-GCM nonce")

            if len(ciphertext) < 16:
                raise ValidationError("Invalid authentication tag")

            key = self.manager.get_key(payload.key_id)

            return AESGCM(key.material).decrypt(
                nonce,
                ciphertext,
                associated_data,
            )

        except InvalidTag as exc:
            raise DecryptionError(
                "Authentication failed: data may have been modified"
            ) from exc
        except (ValueError, TypeError) as exc:
            raise DecryptionError("Invalid encrypted data") from exc


class HybridEncryption:
    """
    Encrypts data with AES-GCM and protects the AES key
    using RSA-OAEP with SHA-256.
    """

    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=3072,
        )
        self.public_key = self.private_key.public_key()

    def encrypt(self, plaintext: bytes) -> dict[str, str]:
        if not isinstance(plaintext, bytes):
            raise ValidationError("Plaintext must be bytes")

        if len(plaintext) > 10_000_000:
            raise ValidationError("Plaintext exceeds size limit")

        data_key = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)

        ciphertext = AESGCM(data_key).encrypt(
            nonce,
            plaintext,
            b"hybrid-encryption-v1",
        )

        encrypted_key = self.public_key.encrypt(
            data_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return {
            "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
            "encrypted_key": base64.b64encode(
                encrypted_key
            ).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(
                ciphertext
            ).decode("ascii"),
        }

    def decrypt(self, envelope: dict[str, str]) -> bytes:
        try:
            if envelope.get("algorithm") != (
                "AES-256-GCM+RSA-OAEP-SHA256"
            ):
                raise ValidationError("Unsupported hybrid algorithm")

            encrypted_key = base64.b64decode(
                envelope["encrypted_key"],
                validate=True,
            )
            nonce = base64.b64decode(
                envelope["nonce"],
                validate=True,
            )
            ciphertext = base64.b64decode(
                envelope["ciphertext"],
                validate=True,
            )

            if len(nonce) != 12 or len(ciphertext) < 16:
                raise ValidationError("Invalid hybrid envelope")

            data_key = self.private_key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            return AESGCM(data_key).decrypt(
                nonce,
                ciphertext,
                b"hybrid-encryption-v1",
            )

        except InvalidTag as exc:
            raise DecryptionError("Hybrid authentication failed") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise DecryptionError("Invalid hybrid envelope") from exc


class TLSConfiguration:
    """Validates minimum TLS transport security requirements."""

    MINIMUM_VERSION = "TLSv1.2"

    @staticmethod
    def validate(version: str, certificate_verified: bool) -> bool:
        supported = {"TLSv1.2", "TLSv1.3"}

        if version not in supported:
            raise ValidationError("Unsupported or insecure TLS version")

        if not certificate_verified:
            raise ValidationError("TLS certificate verification failed")

        return True


class SecureFileStore:
    """Stores authenticated encrypted files."""

    def __init__(self, encryption: SymmetricEncryption) -> None:
        self.encryption = encryption

    def save(self, path: Path, plaintext: bytes) -> None:
        payload = self.encryption.encrypt(
            plaintext,
            associated_data=str(path.name).encode(),
        )

        # Restrictive permissions are applied when creating the file.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        descriptor = os.open(path, flags, 0o600)

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                file.write(payload.to_json())
        except Exception:
            raise

    def load(self, path: Path) -> bytes:
        try:
            if path.is_symlink():
                raise ValidationError("Symbolic links are not permitted")

            if not path.is_file():
                raise ValidationError("Encrypted file does not exist")

            if path.stat().st_size > 15_000_000:
                raise ValidationError("Encrypted file exceeds size limit")

            payload = EncryptedPayload.from_json(
                path.read_text(encoding="utf-8")
            )

            return self.encryption.decrypt(
                payload,
                associated_data=path.name.encode(),
            )

        except OSError as exc:
            raise EncryptionError("File operation failed") from exc


def derive_subkey(
    master_key: bytes,
    context: bytes,
) -> bytes:
    """Derives a context-specific key using HKDF-SHA256."""

    if len(master_key) < 32:
        raise ValidationError("Master key must contain at least 32 bytes")

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=context,
    ).derive(master_key)


class EncryptionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.manager = KeyManager()
        self.manager.generate_key("key-001")
        self.encryption = SymmetricEncryption(self.manager)

    def test_symmetric_round_trip(self) -> None:
        original = b"Confidential enterprise information"

        payload = self.encryption.encrypt(original)
        self.assertEqual(self.encryption.decrypt(payload), original)

    def test_associated_data(self) -> None:
        payload = self.encryption.encrypt(
            b"Account record",
            b"account-100",
        )

        self.assertEqual(
            self.encryption.decrypt(payload, b"account-100"),
            b"Account record",
        )

        with self.assertRaises(DecryptionError):
            self.encryption.decrypt(payload, b"account-200")

    def test_tamper_detection(self) -> None:
        payload = self.encryption.encrypt(b"Sensitive data")

        modified = EncryptedPayload(
            **{
                **payload.__dict__,
                "ciphertext": base64.b64encode(
                    b"tampered-data" * 3
                ).decode(),
            }
        )

        with self.assertRaises(DecryptionError):
            self.encryption.decrypt(modified)

    def test_key_rotation(self) -> None:
        old_payload = self.encryption.encrypt(b"Old record")

        self.manager.rotate("key-002")

        new_payload = self.encryption.encrypt(b"New record")

        self.assertEqual(
            self.encryption.decrypt(old_payload),
            b"Old record",
        )
        self.assertEqual(
            self.encryption.decrypt(new_payload),
            b"New record",
        )

    def test_hybrid_encryption(self) -> None:
        hybrid = HybridEncryption()
        original = b"Hybrid encrypted document"

        envelope = hybrid.encrypt(original)

        self.assertEqual(
            hybrid.decrypt(envelope),
            original,
        )

    def test_tls_validation(self) -> None:
        self.assertTrue(
            TLSConfiguration.validate("TLSv1.3", True)
        )

        with self.assertRaises(ValidationError):
            TLSConfiguration.validate("TLSv1.1", True)

    def test_subkey_derivation(self) -> None:
        master = os.urandom(32)

        first = derive_subkey(master, b"database")
        second = derive_subkey(master, b"file-storage")

        self.assertEqual(len(first), 32)
        self.assertNotEqual(first, second)

    def test_secure_file_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.enc"
            store = SecureFileStore(self.encryption)

            store.save(path, b"Encrypted file contents")

            self.assertEqual(
                store.load(path),
                b"Encrypted file contents",
            )


def main() -> None:
    print("\nENCRYPTION ENGINEERING LABORATORY")
    print("=" * 48)

    manager = KeyManager()
    manager.generate_key("production-key-001")

    symmetric = SymmetricEncryption(manager)

    original = b"Confidential financial transaction"

    payload = symmetric.encrypt(
        original,
        associated_data=b"transaction-1001",
    )

    recovered = symmetric.decrypt(
        payload,
        associated_data=b"transaction-1001",
    )

    print("\n1. Symmetric Encryption")
    print("Algorithm:", payload.algorithm)
    print("Encrypted payload length:", len(payload.ciphertext))
    print("Recovered:", recovered.decode())

    hybrid = HybridEncryption()
    envelope = hybrid.encrypt(original)

    print("\n2. Public-Key and Hybrid Encryption")
    print("Algorithm:", envelope["algorithm"])
    print("Recovered:", hybrid.decrypt(envelope).decode())

    print("\n3. Encryption at Rest")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "financial.enc"
        store = SecureFileStore(symmetric)

        store.save(path, original)
        print("Encrypted file created:", path.name)
        print("Recovered:", store.load(path).decode())

    print("\n4. Encryption in Transit")
    print(
        "TLS configuration valid:",
        TLSConfiguration.validate("TLSv1.3", True),
    )

    print("\n5. Key Rotation")
    manager.rotate("production-key-002")
    print("New active key:", manager.active_key().key_id)

    print("\n6. Context-Specific Key Derivation")
    derived = derive_subkey(
        manager.active_key().material,
        b"application/database",
    )
    print("Derived key length:", len(derived), "bytes")

    print("\n7. Automated Tests")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        EncryptionTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)

    print("\nAll encryption demonstrations completed successfully.")


if __name__ == "__main__":
    main()
