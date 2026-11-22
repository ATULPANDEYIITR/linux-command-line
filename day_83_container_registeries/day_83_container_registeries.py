#!/usr/bin/env python3
"""
Container Registry Management and Image Distribution

Models:
- Container repositories and image manifests
- Immutable content digests
- Mutable and immutable tags
- Semantic versioning
- Private registry authentication and authorization
- Image push and pull operations
- Image distribution and replication
- Vulnerability and signature policy checks
- Retention and deletion policies
- Audit logging and failure handling

Run:
    python container_registry.py
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class RegistryError(Exception):
    """Base exception for registry operations."""


class AuthenticationError(RegistryError):
    pass


class AuthorizationError(RegistryError):
    pass


class ValidationError(RegistryError):
    pass


class ImageNotFoundError(RegistryError):
    pass


class ImmutableTagError(RegistryError):
    pass


class PolicyViolationError(RegistryError):
    pass


class Role(Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    PULL_ONLY = "pull_only"


class ImageStatus(Enum):
    AVAILABLE = "available"
    QUARANTINED = "quarantined"
    DELETED = "deleted"


class Operation(Enum):
    PUSH = "push"
    PULL = "pull"
    DELETE = "delete"
    MANAGE = "manage"


@dataclass(frozen=True)
class User:
    username: str
    token: str
    role: Role
    active: bool = True


@dataclass
class ImageManifest:
    repository: str
    digest: str
    content: bytes
    media_type: str
    architecture: str
    os_name: str
    created_at: datetime
    labels: dict[str, str] = field(default_factory=dict)
    status: ImageStatus = ImageStatus.AVAILABLE
    signed: bool = False
    vulnerability_count: int = 0

    @property
    def size(self) -> int:
        return len(self.content)


@dataclass
class ImageTag:
    name: str
    digest: str
    created_at: datetime
    immutable: bool = False


@dataclass
class Repository:
    name: str
    private: bool = True
    tags: dict[str, ImageTag] = field(default_factory=dict)
    manifests: dict[str, ImageManifest] = field(default_factory=dict)


@dataclass
class AuditEvent:
    timestamp: datetime
    username: str
    operation: str
    repository: str
    reference: str
    result: str


class ContainerRegistry:
    """
    In-memory registry with digest-addressed storage.

    A digest identifies image content. A tag is a human-readable
    reference that points to a digest and may change over time.
    """

    REPOSITORY_PATTERN = re.compile(
        r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$"
    )

    TAG_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")

    def __init__(
        self,
        registry_name: str,
        maximum_image_size: int = 100 * 1024 * 1024,
        require_signed_images: bool = False,
        maximum_vulnerabilities: int = 0,
    ):
        if not registry_name:
            raise ValidationError("Registry name cannot be empty.")

        if maximum_image_size <= 0:
            raise ValidationError("Maximum image size must be positive.")

        self.registry_name = registry_name
        self.maximum_image_size = maximum_image_size
        self.require_signed_images = require_signed_images
        self.maximum_vulnerabilities = maximum_vulnerabilities

        self.users: dict[str, User] = {}
        self.repositories: dict[str, Repository] = {}
        self.audit_log: list[AuditEvent] = []

    @staticmethod
    def timestamp() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def calculate_digest(content: bytes) -> str:
        return "sha256:" + hashlib.sha256(content).hexdigest()

    def register_user(
        self,
        username: str,
        role: Role,
        token: Optional[str] = None,
    ) -> User:
        if not username or username in self.users:
            raise ValidationError("Invalid or duplicate username.")

        user = User(
            username=username,
            token=token or secrets.token_urlsafe(32),
            role=role,
        )

        self.users[username] = user
        return user

    def authenticate(self, token: str) -> User:
        for user in self.users.values():
            if secrets.compare_digest(user.token, token):
                if not user.active:
                    raise AuthenticationError("Account is disabled.")
                return user

        raise AuthenticationError("Invalid registry credentials.")

    def authorize(self, user: User, operation: Operation) -> None:
        permissions = {
            Role.ADMIN: {
                Operation.PUSH,
                Operation.PULL,
                Operation.DELETE,
                Operation.MANAGE,
            },
            Role.DEVELOPER: {
                Operation.PUSH,
                Operation.PULL,
            },
            Role.PULL_ONLY: {
                Operation.PULL,
            },
        }

        if operation not in permissions[user.role]:
            raise AuthorizationError(
                f"{user.username} cannot perform {operation.value}."
            )

    def create_repository(
        self,
        token: str,
        name: str,
        private: bool = True,
    ) -> Repository:
        user = self.authenticate(token)
        self.authorize(user, Operation.MANAGE)

        if not self.REPOSITORY_PATTERN.fullmatch(name):
            raise ValidationError("Invalid repository name.")

        if name in self.repositories:
            raise ValidationError("Repository already exists.")

        repository = Repository(name=name, private=private)
        self.repositories[name] = repository

        self._audit(user, Operation.MANAGE, name, "CREATE", "SUCCESS")
        return repository

    def _get_repository(self, name: str) -> Repository:
        repository = self.repositories.get(name)

        if repository is None:
            raise ImageNotFoundError(f"Repository not found: {name}")

        return repository

    def _check_private_access(self, repository: Repository, user: User):
        if repository.private and not user.active:
            raise AuthorizationError("Inactive user cannot access private images.")

    def _audit(
        self,
        user: User,
        operation: Operation,
        repository: str,
        reference: str,
        result: str,
    ):
        self.audit_log.append(
            AuditEvent(
                timestamp=self.timestamp(),
                username=user.username,
                operation=operation.value,
                repository=repository,
                reference=reference,
                result=result,
            )
        )

    def push(
        self,
        token: str,
        repository_name: str,
        tag_name: str,
        content: bytes,
        architecture: str = "amd64",
        os_name: str = "linux",
        labels: Optional[dict[str, str]] = None,
        signed: bool = False,
        vulnerability_count: int = 0,
        immutable_tag: bool = False,
    ) -> ImageManifest:

        user = self.authenticate(token)
        self.authorize(user, Operation.PUSH)

        repository = self._get_repository(repository_name)
        self._check_private_access(repository, user)

        if not self.TAG_PATTERN.fullmatch(tag_name):
            raise ValidationError("Invalid image tag.")

        if not content:
            raise ValidationError("Image content cannot be empty.")

        if len(content) > self.maximum_image_size:
            raise ValidationError("Image exceeds registry size limit.")

        if vulnerability_count < 0:
            raise ValidationError("Invalid vulnerability count.")

        if not architecture or not os_name:
            raise ValidationError("Platform information is required.")

        if self.require_signed_images and not signed:
            raise PolicyViolationError("Image signature is required.")

        if vulnerability_count > self.maximum_vulnerabilities:
            raise PolicyViolationError(
                "Image exceeds permitted vulnerability count."
            )

        existing_tag = repository.tags.get(tag_name)

        if existing_tag and existing_tag.immutable:
            if existing_tag.digest != self.calculate_digest(content):
                raise ImmutableTagError(
                    f"Tag {tag_name} cannot be overwritten."
                )

        digest = self.calculate_digest(content)

        manifest = repository.manifests.get(digest)

        # Identical content is stored once and can have multiple tags.
        if manifest is None:
            manifest = ImageManifest(
                repository=repository_name,
                digest=digest,
                content=content,
                media_type="application/vnd.oci.image.manifest.v1+json",
                architecture=architecture,
                os_name=os_name,
                created_at=self.timestamp(),
                labels=labels or {},
                signed=signed,
                vulnerability_count=vulnerability_count,
            )
            repository.manifests[digest] = manifest

        if manifest.status != ImageStatus.AVAILABLE:
            raise PolicyViolationError("Image is not available for tagging.")

        repository.tags[tag_name] = ImageTag(
            name=tag_name,
            digest=digest,
            created_at=self.timestamp(),
            immutable=immutable_tag or (
                existing_tag.immutable if existing_tag else False
            ),
        )

        self._audit(user, Operation.PUSH, repository_name, tag_name, "SUCCESS")
        return manifest

    def pull(
        self,
        token: str,
        repository_name: str,
        reference: str,
    ) -> ImageManifest:

        user = self.authenticate(token)
        self.authorize(user, Operation.PULL)

        repository = self._get_repository(repository_name)
        self._check_private_access(repository, user)

        if reference.startswith("sha256:"):
            digest = reference
        else:
            tag = repository.tags.get(reference)

            if tag is None:
                self._audit(
                    user, Operation.PULL, repository_name, reference, "NOT_FOUND"
                )
                raise ImageNotFoundError("Image tag does not exist.")

            digest = tag.digest

        manifest = repository.manifests.get(digest)

        if manifest is None or manifest.status != ImageStatus.AVAILABLE:
            self._audit(
                user, Operation.PULL, repository_name, reference, "UNAVAILABLE"
            )
            raise ImageNotFoundError("Image digest is unavailable.")

        # Verify stored bytes against their content-addressed identifier.
        if self.calculate_digest(manifest.content) != manifest.digest:
            raise RegistryError("Image integrity verification failed.")

        self._audit(user, Operation.PULL, repository_name, reference, "SUCCESS")
        return manifest

    def delete_tag(
        self,
        token: str,
        repository_name: str,
        tag_name: str,
    ) -> None:
        user = self.authenticate(token)
        self.authorize(user, Operation.DELETE)

        repository = self._get_repository(repository_name)
        tag = repository.tags.get(tag_name)

        if tag is None:
            raise ImageNotFoundError("Tag does not exist.")

        if tag.immutable:
            raise ImmutableTagError("Immutable tags cannot be deleted.")

        del repository.tags[tag_name]

        self._audit(user, Operation.DELETE, repository_name, tag_name, "SUCCESS")

    def garbage_collect(self, token: str) -> int:
        user = self.authenticate(token)
        self.authorize(user, Operation.MANAGE)

        removed = 0

        for repository in self.repositories.values():
            referenced = {
                tag.digest for tag in repository.tags.values()
            }

            unreferenced = [
                digest
                for digest in repository.manifests
                if digest not in referenced
            ]

            for digest in unreferenced:
                del repository.manifests[digest]
                removed += 1

        self._audit(user, Operation.MANAGE, "*", "GARBAGE_COLLECTION", "SUCCESS")
        return removed

    def list_images(self, token: str, repository_name: str) -> list[dict]:
        user = self.authenticate(token)
        self.authorize(user, Operation.PULL)

        repository = self._get_repository(repository_name)
        self._check_private_access(repository, user)

        return [
            {
                "tag": tag.name,
                "digest": tag.digest,
                "immutable": tag.immutable,
                "size": repository.manifests[tag.digest].size,
            }
            for tag in repository.tags.values()
        ]

    def export_audit_report(self) -> str:
        return json.dumps(
            [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "username": event.username,
                    "operation": event.operation,
                    "repository": event.repository,
                    "reference": event.reference,
                    "result": event.result,
                }
                for event in self.audit_log
            ],
            indent=2,
        )


def demonstrate_registry():
    registry = ContainerRegistry(
        registry_name="registry.example.internal",
        maximum_image_size=10_000_000,
        require_signed_images=True,
        maximum_vulnerabilities=2,
    )

    admin = registry.register_user("registry-admin", Role.ADMIN)
    developer = registry.register_user("developer", Role.DEVELOPER)
    consumer = registry.register_user("deployment-service", Role.PULL_ONLY)

    registry.create_repository(
        admin.token,
        "production/payment-api",
        private=True,
    )

    image_v1 = b"payment-api-container-image-v1"
    image_v2 = b"payment-api-container-image-v2"

    first = registry.push(
        developer.token,
        "production/payment-api",
        "1.0.0",
        image_v1,
        signed=True,
        vulnerability_count=0,
        immutable_tag=True,
        labels={"team": "payments", "environment": "production"},
    )

    second = registry.push(
        developer.token,
        "production/payment-api",
        "1.1.0",
        image_v2,
        signed=True,
        vulnerability_count=1,
    )

    registry.push(
        developer.token,
        "production/payment-api",
        "latest",
        image_v2,
        signed=True,
        vulnerability_count=1,
    )

    pulled = registry.pull(
        consumer.token,
        "production/payment-api",
        "latest",
    )

    assert pulled.digest == second.digest
    assert first.digest != second.digest

    # A pull-only identity cannot publish an image.
    try:
        registry.push(
            consumer.token,
            "production/payment-api",
            "2.0.0",
            b"unauthorized-image",
            signed=True,
        )
    except AuthorizationError as error:
        print("Authorization test:", error)

    # Unsigned images are rejected by registry policy.
    try:
        registry.push(
            developer.token,
            "production/payment-api",
            "2.0.0",
            b"unsigned-image",
            signed=False,
        )
    except PolicyViolationError as error:
        print("Security policy test:", error)

    # Immutable tags cannot be overwritten.
    try:
        registry.push(
            developer.token,
            "production/payment-api",
            "1.0.0",
            b"different-image-content",
            signed=True,
        )
    except ImmutableTagError as error:
        print("Tag immutability test:", error)

    print("\nRegistry:", registry.registry_name)
    print("Repository images:")
    print(json.dumps(
        registry.list_images(consumer.token, "production/payment-api"),
        indent=2,
    ))

    print("\nPulled digest:", pulled.digest)
    print("Pulled image size:", pulled.size)

    print("\nAudit events:", len(registry.audit_log))

    print("\nAudit report:")
    print(registry.export_audit_report())


if __name__ == "__main__":
    demonstrate_registry()
