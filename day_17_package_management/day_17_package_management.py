#!/usr/bin/env python3
"""
Package Management: A Practical Study from Beginner to Advanced

This standalone program teaches package-management concepts through executable
examples. It models repositories, packages, semantic versions, dependencies,
installation, upgrades, downgrades, removals, dependency resolution, lock
files, virtual environments, integrity verification, conflicts, repositories,
and transaction-style package operations.

The program intentionally uses only Python's standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Dict, Iterable, List, Optional, Set, Tuple
import copy
import re


# ============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# ============================================================================

def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def explain_basic_terminology() -> None:
    print_section("1. Package-management fundamentals")

    terms = {
        "Package": "A distributable unit containing software and metadata.",
        "Package manager": "Software that installs, updates, removes, and resolves packages.",
        "Repository": "A source from which packages and metadata can be obtained.",
        "Dependency": "Another package required by a package.",
        "Version": "An identifier describing a particular release of software.",
        "Manifest": "Metadata declaring package identity, version, dependencies, and related information.",
        "Lock file": "A file recording exact dependency versions selected for reproducible installation.",
        "Artifact": "The concrete downloadable package archive or binary.",
        "Registry": "A service that indexes package names, versions, and metadata.",
        "Virtual environment": "An isolated environment containing a separate package set.",
        "Transitive dependency": "A dependency required indirectly through another dependency.",
        "Conflict": "A situation where required package constraints cannot be satisfied together.",
        "Upgrade": "Moving to a newer compatible or requested version.",
        "Downgrade": "Moving to an older version.",
        "Uninstall": "Removing a package and, where safe, its unused dependencies.",
        "Integrity": "Confidence that an artifact has not been modified unexpectedly.",
    }

    for name, definition in terms.items():
        print(f"{name:24} {definition}")


# ============================================================================
# 2. SEMANTIC VERSIONING
# ============================================================================

@dataclass(frozen=True, order=True)
class Version:
    """
    A small semantic-version representation.

    Semantic versioning normally has MAJOR.MINOR.PATCH components:
      1.2.3

    MAJOR: incompatible API changes.
    MINOR: backward-compatible functionality.
    PATCH: backward-compatible bug fixes.

    Real package ecosystems also support prereleases, build metadata, epochs,
    local versions, or ecosystem-specific version schemes. This teaching
    implementation deliberately focuses on numeric MAJOR.MINOR.PATCH versions.
    """

    major: int
    minor: int
    patch: int

    VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

    @classmethod
    def parse(cls, text: str) -> "Version":
        match = cls.VERSION_PATTERN.fullmatch(text.strip())
        if not match:
            raise ValueError(f"Invalid semantic version: {text!r}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def demonstrate_versions() -> None:
    print_section("2. Versions and version comparison")

    versions = [
        Version.parse("1.0.0"),
        Version.parse("1.2.0"),
        Version.parse("1.2.5"),
        Version.parse("2.0.0"),
    ]

    for version in versions:
        print(version)

    print("1.2.5 > 1.2.0:", Version.parse("1.2.5") > Version.parse("1.2.0"))
    print("2.0.0 > 1.9.9:", Version.parse("2.0.0") > Version.parse("1.9.9"))

    print("\nVersioning rule of thumb:")
    print("  PATCH -> bug fixes")
    print("  MINOR -> compatible features")
    print("  MAJOR -> potentially incompatible changes")


# ============================================================================
# 3. VERSION CONSTRAINTS
# ============================================================================

@dataclass(frozen=True)
class VersionConstraint:
    """
    Represents a small but useful subset of dependency constraints.

    Supported forms:
      *
      ==1.2.3
      >=1.2.0
      >1.2.0
      <=1.5.0
      <2.0.0
      ^1.2.3
      ^0.2.3
      ~1.2.3

    ^1.2.3 generally means >=1.2.3 and <2.0.0.
    ^0.2.3 generally means >=0.2.3 and <0.3.0.
    ~1.2.3 generally means >=1.2.3 and <1.3.0.

    Different ecosystems define constraint syntax differently. A package
    manager must therefore implement the rules of its own ecosystem.
    """

    expression: str

    def matches(self, version: Version) -> bool:
        expression = self.expression.strip()

        if expression in ("", "*"):
            return True

        if expression.startswith("^"):
            base = Version.parse(expression[1:])
            if base.major > 0:
                upper = Version(base.major + 1, 0, 0)
            elif base.minor > 0:
                upper = Version(0, base.minor + 1, 0)
            else:
                upper = Version(0, 0, base.patch + 1)
            return version >= base and version < upper

        if expression.startswith("~"):
            base = Version.parse(expression[1:])
            upper = Version(base.major, base.minor + 1, 0)
            return version >= base and version < upper

        operators = [">=", "<=", "==", ">", "<"]
        for operator in operators:
            if expression.startswith(operator):
                target = Version.parse(expression[len(operator):])
                return {
                    ">=": version >= target,
                    "<=": version <= target,
                    "==": version == target,
                    ">": version > target,
                    "<": version < target,
                }[operator]

        # A plain version is treated as an exact requirement in this model.
        return version == Version.parse(expression)


def demonstrate_constraints() -> None:
    print_section("3. Dependency version constraints")

    candidates = [
        Version.parse("1.1.0"),
        Version.parse("1.2.0"),
        Version.parse("1.2.5"),
        Version.parse("1.9.0"),
        Version.parse("2.0.0"),
    ]

    constraints = ["^1.2.0", "~1.2.0", ">=1.2.0", "<2.0.0", "==1.2.5"]

    for expression in constraints:
        accepted = [
            str(version)
            for version in candidates
            if VersionConstraint(expression).matches(version)
        ]
        print(f"{expression:10} -> {accepted}")


# ============================================================================
# 4. PACKAGE DATA MODEL
# ============================================================================

@dataclass(frozen=True)
class Dependency:
    name: str
    constraint: VersionConstraint


@dataclass
class Package:
    name: str
    version: Version
    dependencies: List[Dependency] = field(default_factory=list)
    description: str = ""
    size_kb: int = 0
    platform: str = "any"
    checksum: str = ""

    def artifact_bytes(self) -> bytes:
        """
        Generate deterministic pseudo-artifact content.

        A real package manager hashes the actual downloaded archive or package
        file. Here we use deterministic bytes to demonstrate integrity checks.
        """
        dependency_text = ",".join(
            f"{dependency.name}:{dependency.constraint.expression}"
            for dependency in self.dependencies
        )
        return (
            f"{self.name}|{self.version}|{dependency_text}|{self.platform}"
        ).encode()

    def calculate_checksum(self) -> str:
        return sha256(self.artifact_bytes()).hexdigest()

    def with_checksum(self) -> "Package":
        clone = copy.deepcopy(self)
        clone.checksum = clone.calculate_checksum()
        return clone


# ============================================================================
# 5. REPOSITORY
# ============================================================================

class Repository:
    """A simplified package repository containing multiple package versions."""

    def __init__(self, name: str, trusted: bool = True):
        self.name = name
        self.trusted = trusted
        self._packages: Dict[str, List[Package]] = {}

    def publish(self, package: Package) -> None:
        package = package.with_checksum()
        versions = self._packages.setdefault(package.name, [])

        # A repository should not normally contain duplicate name/version
        # records. Replacing it here keeps the example deterministic.
        versions[:] = [
            existing
            for existing in versions
            if existing.version != package.version
        ]
        versions.append(package)
        versions.sort(key=lambda item: item.version)

    def available_versions(self, name: str) -> List[Version]:
        return [
            package.version
            for package in self._packages.get(name, [])
        ]

    def candidates(
        self,
        name: str,
        constraint: VersionConstraint,
    ) -> List[Package]:
        return [
            package
            for package in self._packages.get(name, [])
            if constraint.matches(package.version)
        ]

    def latest_matching(
        self,
        name: str,
        constraint: VersionConstraint,
    ) -> Optional[Package]:
        candidates = self.candidates(name, constraint)
        return max(candidates, key=lambda package: package.version) if candidates else None

    def get_exact(self, name: str, version: Version) -> Optional[Package]:
        for package in self._packages.get(name, []):
            if package.version == version:
                return package
        return None


# ============================================================================
# 6. DEPENDENCY RESOLUTION
# ============================================================================

class DependencyResolutionError(Exception):
    """Raised when package requirements cannot be satisfied."""


@dataclass
class Requirement:
    name: str
    constraint: VersionConstraint
    requested_by: str


class DependencyResolver:
    """
    A backtracking dependency resolver.

    The algorithm:
      1. Select a requirement.
      2. Find repository candidates satisfying its constraint.
      3. Prefer newer versions.
      4. Tentatively select one.
      5. Add its dependencies to the requirement set.
      6. Backtrack if a conflict occurs.

    Real-world package managers use more sophisticated SAT solvers,
    PubGrub-like algorithms, constraint solvers, priority rules, lock files,
    platform markers, optional dependencies, and repository policies.
    """

    def __init__(self, repositories: List[Repository]):
        self.repositories = repositories

    def _candidates(
        self,
        name: str,
        constraint: VersionConstraint,
    ) -> List[Package]:
        candidates: List[Package] = []

        for repository in self.repositories:
            if not repository.trusted:
                continue
            candidates.extend(repository.candidates(name, constraint))

        # Newest candidates are considered first.
        candidates.sort(key=lambda package: package.version, reverse=True)

        # Remove duplicate name/version combinations from multiple repositories.
        unique: Dict[Tuple[str, Version], Package] = {}
        for package in candidates:
            unique[(package.name, package.version)] = package

        return list(unique.values())

    def resolve(
        self,
        root_name: str,
        root_constraint: VersionConstraint,
    ) -> Dict[str, Package]:
        requirements = [
            Requirement(root_name, root_constraint, "root")
        ]
        selected: Dict[str, Package] = {}
        return self._search(requirements, selected)

    def _search(
        self,
        requirements: List[Requirement],
        selected: Dict[str, Package],
    ) -> Dict[str, Package]:
        if not requirements:
            return selected

        requirement = requirements[0]
        remaining = requirements[1:]

        already_selected = selected.get(requirement.name)
        if already_selected:
            if requirement.constraint.matches(already_selected.version):
                return self._search(remaining, selected)
            raise DependencyResolutionError(
                f"Conflict: {requirement.requested_by} requires "
                f"{requirement.name} {requirement.constraint.expression}, "
                f"but {already_selected.version} was selected."
            )

        candidates = self._candidates(
            requirement.name,
            requirement.constraint,
        )

        if not candidates:
            raise DependencyResolutionError(
                f"No available version satisfies "
                f"{requirement.name} {requirement.constraint.expression} "
                f"required by {requirement.requested_by}."
            )

        for candidate in candidates:
            next_selected = dict(selected)
            next_selected[candidate.name] = candidate

            next_requirements = list(remaining)
            next_requirements.extend(
                Requirement(
                    dependency.name,
                    dependency.constraint,
                    candidate.name,
                )
                for dependency in candidate.dependencies
            )

            try:
                return self._search(next_requirements, next_selected)
            except DependencyResolutionError:
                # Backtracking is important when the newest candidate creates
                # a conflict but an older candidate can satisfy all constraints.
                continue

        raise DependencyResolutionError(
            f"Could not resolve {requirement.name} "
            f"{requirement.constraint.expression}."
        )


def demonstrate_resolution(repository: Repository) -> None:
    print_section("4. Dependency resolution")

    resolver = DependencyResolver([repository])

    try:
        resolved = resolver.resolve(
            "analytics-app",
            VersionConstraint("==1.0.0"),
        )

        print("Resolved dependency graph:")
        for name, package in sorted(resolved.items()):
            print(f"  {name}=={package.version}")

    except DependencyResolutionError as error:
        print("Resolution failed:", error)


# ============================================================================
# 7. PACKAGE MANAGER STATE
# ============================================================================

@dataclass
class LockRecord:
    name: str
    version: Version
    checksum: str


class PackageManager:
    """
    A transaction-oriented package manager simulation.

    Installed packages are kept separately from repository metadata.
    A lock dictionary records exact versions and checksums.

    Production package managers also maintain caches, database state,
    configuration files, file ownership records, signatures, dependency
    graphs, triggers, scripts, rollback information, and platform-specific
    metadata.
    """

    def __init__(self, repositories: List[Repository]):
        self.repositories = repositories
        self.installed: Dict[str, Package] = {}
        self.lock: Dict[str, LockRecord] = {}
        self.history: List[str] = []

    def _resolver(self) -> DependencyResolver:
        return DependencyResolver(self.repositories)

    def install(
        self,
        name: str,
        constraint: str = "*",
        update_lock: bool = True,
    ) -> None:
        print(f"\nInstalling {name} {constraint}")

        before = copy.deepcopy(self.installed)

        try:
            resolved = self._resolver().resolve(
                name,
                VersionConstraint(constraint),
            )

            # Validate every artifact before modifying installed state.
            for package in resolved.values():
                if package.calculate_checksum() != package.checksum:
                    raise ValueError(
                        f"Integrity check failed for {package.name} "
                        f"{package.version}"
                    )

            self.installed.update(resolved)

            if update_lock:
                for package in resolved.values():
                    self.lock[package.name] = LockRecord(
                        package.name,
                        package.version,
                        package.checksum,
                    )

            self.history.append(
                f"install {name} {constraint}"
            )

            for package in sorted(
                resolved.values(),
                key=lambda item: item.name,
            ):
                print(f"  selected {package.name}=={package.version}")

        except Exception:
            # A failed installation should not leave a partially modified
            # package database.
            self.installed = before
            raise

    def remove(self, name: str) -> None:
        print(f"\nRemoving {name}")

        if name not in self.installed:
            print("  package is not installed")
            return

        dependents = [
            package.name
            for package in self.installed.values()
            if any(
                dependency.name == name
                for dependency in package.dependencies
            )
            and package.name != name
        ]

        if dependents:
            raise RuntimeError(
                f"Cannot safely remove {name}; required by "
                + ", ".join(sorted(dependents))
            )

        del self.installed[name]
        self.lock.pop(name, None)
        self.history.append(f"remove {name}")
        print(f"  removed {name}")

    def upgrade_all(self) -> None:
        print("\nChecking for upgrades")

        changes = []

        for name, installed_package in list(self.installed.items()):
            candidate_versions: List[Package] = []

            for repository in self.repositories:
                candidate_versions.extend(
                    repository.candidates(
                        name,
                        VersionConstraint("*"),
                    )
                )

            if not candidate_versions:
                continue

            newest = max(
                candidate_versions,
                key=lambda package: package.version,
            )

            if newest.version > installed_package.version:
                changes.append((name, installed_package, newest))

        for name, old, new in changes:
            print(f"  {name}: {old.version} -> {new.version}")

            # A production upgrade would re-resolve the complete dependency
            # graph instead of blindly replacing a single package.
            self.installed[name] = new
            self.lock[name] = LockRecord(
                new.name,
                new.version,
                new.checksum,
            )

        if not changes:
            print("  all installed packages are current")

        self.history.append("upgrade-all")

    def show_installed(self) -> None:
        print("\nInstalled packages:")
        if not self.installed:
            print("  none")
            return

        for package in sorted(
            self.installed.values(),
            key=lambda item: item.name,
        ):
            print(
                f"  {package.name}=={package.version} "
                f"({package.size_kb} KB)"
            )

    def show_lock(self) -> None:
        print("\nLock file:")
        for record in sorted(
            self.lock.values(),
            key=lambda item: item.name,
        ):
            print(
                f"  {record.name}=={record.version} "
                f"sha256:{record.checksum[:16]}..."
            )

    def verify_integrity(self) -> bool:
        print("\nVerifying installed artifacts")
        valid = True

        for package in self.installed.values():
            expected = package.checksum
            actual = package.calculate_checksum()

            if expected == actual:
                print(f"  OK   {package.name}=={package.version}")
            else:
                print(f"  FAIL {package.name}=={package.version}")
                valid = False

        return valid

    def install_from_lock(self) -> None:
        """
        Reproduce exact package versions from the lock state.

        This is distinct from resolving fresh compatible versions.
        """
        print("\nReinstalling from lock file")

        restored: Dict[str, Package] = {}

        for record in self.lock.values():
            package = None

            for repository in self.repositories:
                package = repository.get_exact(
                    record.name,
                    record.version,
                )
                if package:
                    break

            if package is None:
                raise RuntimeError(
                    f"Locked package {record.name}=={record.version} "
                    "is unavailable."
                )

            if package.checksum != record.checksum:
                raise RuntimeError(
                    f"Checksum mismatch for locked package "
                    f"{record.name}=={record.version}"
                )

            restored[package.name] = package

        self.installed = restored
        self.history.append("install-from-lock")

    def history_log(self) -> None:
        print("\nTransaction history:")
        for index, action in enumerate(self.history, start=1):
            print(f"  {index:02d}. {action}")


# ============================================================================
# 8. BUILDING A SAMPLE REPOSITORY
# ============================================================================

def create_sample_repository() -> Repository:
    repository = Repository("example-central", trusted=True)

    repository.publish(
        Package(
            name="http-core",
            version=Version.parse("1.0.0"),
            description="Basic HTTP primitives",
            size_kb=180,
        )
    )
    repository.publish(
        Package(
            name="http-core",
            version=Version.parse("1.1.0"),
            description="HTTP primitives with connection pooling",
            size_kb=220,
        )
    )
    repository.publish(
        Package(
            name="http-core",
            version=Version.parse("2.0.0"),
            description="HTTP core with redesigned API",
            size_kb=300,
        )
    )

    repository.publish(
        Package(
            name="parser",
            version=Version.parse("1.0.0"),
            dependencies=[
                Dependency(
                    "http-core",
                    VersionConstraint("^1.0.0"),
                )
            ],
            description="Configuration parser",
            size_kb=90,
        )
    )
    repository.publish(
        Package(
            name="parser",
            version=Version.parse("1.1.0"),
            dependencies=[
                Dependency(
                    "http-core",
                    VersionConstraint("^1.0.0"),
                )
            ],
            description="Improved configuration parser",
            size_kb=110,
        )
    )

    repository.publish(
        Package(
            name="database-driver",
            version=Version.parse("3.0.0"),
            dependencies=[
                Dependency(
                    "http-core",
                    VersionConstraint(">=1.1.0"),
                )
            ],
            description="Database connectivity driver",
            size_kb=750,
        )
    )

    repository.publish(
        Package(
            name="analytics-app",
            version=Version.parse("1.0.0"),
            dependencies=[
                Dependency(
                    "parser",
                    VersionConstraint("^1.0.0"),
                ),
                Dependency(
                    "database-driver",
                    VersionConstraint("==3.0.0"),
                ),
            ],
            description="Application using parser and database driver",
            size_kb=1200,
        )
    )

    repository.publish(
        Package(
            name="analytics-app",
            version=Version.parse("1.1.0"),
            dependencies=[
                Dependency(
                    "parser",
                    VersionConstraint("^1.1.0"),
                ),
                Dependency(
                    "database-driver",
                    VersionConstraint("==3.0.0"),
                ),
            ],
            description="Updated analytics application",
            size_kb=1300,
        )
    )

    return repository


# ============================================================================
# 9. DEPENDENCY GRAPH
# ============================================================================

def build_dependency_graph(packages: Iterable[Package]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {}

    for package in packages:
        graph[package.name] = {
            dependency.name
            for dependency in package.dependencies
        }

    return graph


def print_dependency_graph(packages: Iterable[Package]) -> None:
    print_section("5. Dependency graph")

    graph = build_dependency_graph(packages)

    for package_name in sorted(graph):
        dependencies = sorted(graph[package_name])
        if dependencies:
            print(f"{package_name} -> {', '.join(dependencies)}")
        else:
            print(f"{package_name} -> no dependencies")


def detect_cycle(graph: Dict[str, Set[str]]) -> bool:
    """
    Depth-first cycle detection.

    A dependency cycle such as:
      A -> B -> C -> A

    can make ordinary dependency installation impossible unless the ecosystem
    has special mechanisms for cyclic packages.
    """
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False

        visiting.add(node)

        for dependency in graph.get(node, set()):
            if visit(dependency):
                return True

        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


# ============================================================================
# 10. CONFLICT DEMONSTRATION
# ============================================================================

def demonstrate_conflict() -> None:
    print_section("6. Dependency conflicts")

    repository = Repository("conflict-demo")

    repository.publish(
        Package(
            name="core",
            version=Version.parse("1.5.0"),
        )
    )
    repository.publish(
        Package(
            name="core",
            version=Version.parse("2.0.0"),
        )
    )

    repository.publish(
        Package(
            name="legacy-tool",
            version=Version.parse("1.0.0"),
            dependencies=[
                Dependency(
                    "core",
                    VersionConstraint("<2.0.0"),
                )
            ],
        )
    )

    repository.publish(
        Package(
            name="modern-tool",
            version=Version.parse("1.0.0"),
            dependencies=[
                Dependency(
                    "core",
                    VersionConstraint(">=2.0.0"),
                )
            ],
        )
    )

    # A root application requires both incompatible constraints.
    repository.publish(
        Package(
            name="conflicting-app",
            version=Version.parse("1.0.0"),
            dependencies=[
                Dependency(
                    "legacy-tool",
                    VersionConstraint("==1.0.0"),
                ),
                Dependency(
                    "modern-tool",
                    VersionConstraint("==1.0.0"),
                ),
            ],
        )
    )

    try:
        DependencyResolver([repository]).resolve(
            "conflicting-app",
            VersionConstraint("==1.0.0"),
        )
    except DependencyResolutionError as error:
        print("Expected resolution failure:")
        print(" ", error)


# ============================================================================
# 11. OPTIONAL DEPENDENCIES, DEV DEPENDENCIES, AND RUNTIME CONCEPTS
# ============================================================================

@dataclass
class ExtendedPackageMetadata:
    """
    Illustrative metadata model showing categories used by many ecosystems.

    These categories are represented as data only; the resolver above handles
    ordinary runtime dependencies.
    """

    runtime_dependencies: List[Dependency] = field(default_factory=list)
    development_dependencies: List[Dependency] = field(default_factory=list)
    optional_dependencies: List[Dependency] = field(default_factory=list)
    platform_requirements: List[str] = field(default_factory=list)


def demonstrate_dependency_categories() -> None:
    print_section("7. Dependency categories")

    metadata = ExtendedPackageMetadata(
        runtime_dependencies=[
            Dependency("http-core", VersionConstraint("^1.0.0"))
        ],
        development_dependencies=[
            Dependency("test-runner", VersionConstraint("^2.0.0"))
        ],
        optional_dependencies=[
            Dependency("accelerator", VersionConstraint("^1.0.0"))
        ],
        platform_requirements=["python>=3.11", "linux-or-windows"],
    )

    print("Runtime dependencies:")
    for dependency in metadata.runtime_dependencies:
        print(f"  {dependency.name} {dependency.constraint.expression}")

    print("Development dependencies:")
    for dependency in metadata.development_dependencies:
        print(f"  {dependency.name} {dependency.constraint.expression}")

    print("Optional dependencies:")
    for dependency in metadata.optional_dependencies:
        print(f"  {dependency.name} {dependency.constraint.expression}")

    print("Platform requirements:")
    for requirement in metadata.platform_requirements:
        print(f"  {requirement}")


# ============================================================================
# 12. REPOSITORIES AND TRUST
# ============================================================================

def demonstrate_repository_trust() -> None:
    print_section("8. Repositories, integrity, and trust")

    trusted_repository = Repository("trusted", trusted=True)
    untrusted_repository = Repository("untrusted", trusted=False)

    trusted_package = Package(
        name="secure-library",
        version=Version.parse("1.0.0"),
    ).with_checksum()

    untrusted_package = Package(
        name="secure-library",
        version=Version.parse("9.9.9"),
    ).with_checksum()

    trusted_repository.publish(trusted_package)
    untrusted_repository.publish(untrusted_package)

    resolver = DependencyResolver(
        [untrusted_repository, trusted_repository]
    )

    resolved = resolver.resolve(
        "secure-library",
        VersionConstraint("*"),
    )

    selected = resolved["secure-library"]

    print("Trusted repositories are preferred in this model.")
    print(f"Selected version: {selected.version}")
    print("Selected package checksum:", selected.checksum)

    print("\nSecurity principles:")
    print("  - Prefer trusted repositories.")
    print("  - Verify checksums or signatures.")
    print("  - Protect repository credentials.")
    print("  - Review package provenance.")
    print("  - Avoid blindly executing package installation scripts.")
    print("  - Pin critical production dependencies when appropriate.")


# ============================================================================
# 13. LOCK FILES AND REPRODUCIBILITY
# ============================================================================

def demonstrate_lock_file(manager: PackageManager) -> None:
    print_section("9. Lock files and reproducible installation")

    manager.show_lock()

    print(
        "\nA version constraint such as ^1.0.0 can allow several versions."
    )
    print(
        "A lock file converts the chosen dependency graph into exact versions."
    )

    original = dict(manager.installed)

    manager.installed.clear()
    print("\nEnvironment cleared.")
    manager.show_installed()

    manager.install_from_lock()
    print("\nEnvironment restored from lock state.")
    manager.show_installed()

    assert set(original) == set(manager.installed)


# ============================================================================
# 14. PACKAGE CACHING
# ============================================================================

class PackageCache:
    """
    Simplified local artifact cache.

    Caching reduces repeated downloads and can improve installation speed.
    Caches must still be treated carefully because stale or corrupted artifacts
    can cause failures.
    """

    def __init__(self):
        self._items: Dict[Tuple[str, Version], Package] = {}

    def put(self, package: Package) -> None:
        self._items[(package.name, package.version)] = package

    def get(self, name: str, version: Version) -> Optional[Package]:
        return self._items.get((name, version))

    def has(self, name: str, version: Version) -> bool:
        return (name, version) in self._items


def demonstrate_cache(repository: Repository) -> None:
    print_section("10. Package caching")

    cache = PackageCache()

    package = repository.get_exact(
        "http-core",
        Version.parse("1.1.0"),
    )

    assert package is not None

    print("Cache before:", cache.has(package.name, package.version))
    cache.put(package)
    print("Cache after :", cache.has(package.name, package.version))

    cached = cache.get(package.name, package.version)
    print("Cached artifact checksum:", cached.checksum if cached else "missing")


# ============================================================================
# 15. ENVIRONMENT ISOLATION
# ============================================================================

class Environment:
    """
    Represents an isolated software environment.

    Isolation prevents unrelated applications from forcing the same package
    version into a single global installation. Python virtual environments,
    Node project directories, containers, language-specific environments, and
    OS package databases use different mechanisms to achieve related goals.
    """

    def __init__(self, name: str):
        self.name = name
        self.packages: Dict[str, Package] = {}

    def install(self, package: Package) -> None:
        self.packages[package.name] = package

    def show(self) -> None:
        print(f"{self.name}:")
        for package in sorted(
            self.packages.values(),
            key=lambda item: item.name,
        ):
            print(f"  {package.name}=={package.version}")


def demonstrate_isolation(repository: Repository) -> None:
    print_section("11. Environment isolation")

    development = Environment("development")
    production = Environment("production")

    development_package = repository.get_exact(
        "http-core",
        Version.parse("1.1.0"),
    )
    production_package = repository.get_exact(
        "http-core",
        Version.parse("1.0.0"),
    )

    assert development_package is not None
    assert production_package is not None

    development.install(development_package)
    production.install(production_package)

    development.show()
    production.show()

    print(
        "\nThe two environments can intentionally use different versions "
        "without overwriting one another."
    )


# ============================================================================
# 16. UPDATE STRATEGIES
# ============================================================================

def compare_update_strategies() -> None:
    print_section("12. Update strategies")

    strategies = {
        "Exact pin": "Install exactly one version, such as 1.2.3.",
        "Minimum constraint": "Allow versions at or above a specified version.",
        "Compatible constraint": "Allow versions within a compatibility range.",
        "Latest": "Always choose the newest available version.",
        "Locked": "Use versions recorded in a lock file.",
        "Scheduled update": "Review and apply dependency updates periodically.",
    }

    for strategy, meaning in strategies.items():
        print(f"{strategy:20} {meaning}")

    print("\nTrade-offs:")
    print("  More flexibility -> potentially newer fixes, but less reproducibility.")
    print("  More pinning     -> stronger reproducibility, but more update work.")
    print("  Automated updates -> reduced maintenance, but require strong testing.")


# ============================================================================
# 17. EDGE CASES
# ============================================================================

def demonstrate_edge_cases(repository: Repository) -> None:
    print_section("13. Edge cases")

    cases = [
        ("missing-package", "1.0.0"),
        ("http-core", "invalid"),
        ("http-core", "2.0.0"),
    ]

    for name, constraint in cases:
        try:
            if name == "http-core" and constraint == "invalid":
                # Parsing a malformed version constraint reaches Version.parse.
                VersionConstraint("==" + constraint).matches(
                    Version.parse("1.0.0")
                )
            else:
                result = DependencyResolver([repository]).resolve(
                    name,
                    VersionConstraint(constraint),
                )
                print(
                    f"{name} {constraint}: "
                    + ", ".join(
                        f"{key}=={value.version}"
                        for key, value in result.items()
                    )
                )
        except (DependencyResolutionError, ValueError) as error:
            print(f"{name} {constraint}: handled error -> {error}")


# ============================================================================
# 18. TRANSACTION SAFETY
# ============================================================================

def demonstrate_transaction_safety(manager: PackageManager) -> None:
    print_section("14. Transaction safety")

    before = {
        name: package.version
        for name, package in manager.installed.items()
    }

    try:
        manager.install(
            "package-that-does-not-exist",
            "==1.0.0",
        )
    except Exception as error:
        print("Installation failed:", error)

    after = {
        name: package.version
        for name, package in manager.installed.items()
    }

    print("State unchanged after failure:", before == after)

    print(
        "\nAtomicity is important because a half-completed package operation "
        "can leave an application unusable."
    )


# ============================================================================
# 19. PERFORMANCE CONSIDERATIONS
# ============================================================================

def explain_performance() -> None:
    print_section("15. Performance considerations")

    observations = [
        "Repository metadata should be indexed rather than scanned repeatedly.",
        "Local caches avoid repeated artifact downloads.",
        "Dependency graphs should avoid unnecessary repeated traversal.",
        "Lock files reduce repeated dependency-resolution work.",
        "Parallel downloads can improve installation time when dependencies are independent.",
        "Large dependency graphs increase resolver search space.",
        "Backtracking can become expensive when many constraints interact.",
        "Checksum verification adds CPU and I/O cost but protects integrity.",
    ]

    for observation in observations:
        print("-", observation)


# ============================================================================
# 20. SECURITY CONSIDERATIONS
# ============================================================================

def explain_security() -> None:
    print_section("16. Security considerations")

    controls = [
        "Use trusted repositories and authenticated package sources.",
        "Verify cryptographic hashes or signatures.",
        "Keep package managers and repository clients patched.",
        "Audit direct and transitive dependencies.",
        "Remove unused dependencies to reduce attack surface.",
        "Avoid running package installation as an unnecessary privileged user.",
        "Review installation scripts because packages can execute code.",
        "Protect private repository credentials and tokens.",
        "Use lock files for reproducible production deployments.",
        "Monitor dependencies for known vulnerabilities.",
        "Treat compromised dependencies as a supply-chain incident.",
    ]

    for control in controls:
        print("-", control)


# ============================================================================
# 21. COMPARISON OF COMMON ECOSYSTEMS
# ============================================================================

def compare_ecosystems() -> None:
    print_section("17. Common package-management ecosystems")

    ecosystems = [
        ("Python", "pip", "PyPI", "pyproject.toml, requirements files, lock tools"),
        ("JavaScript", "npm", "npm registry", "package.json, package-lock.json"),
        ("Java", "Maven", "Maven repositories", "pom.xml"),
        ("C/C++", "Conan/vcpkg", "Configured registries/ports", "Manifest files"),
        ("Rust", "Cargo", "crates.io", "Cargo.toml, Cargo.lock"),
        ("Go", "Go modules", "Module proxy", "go.mod, go.sum"),
        ("Debian/Ubuntu", "APT", "APT repositories", "dpkg database + APT metadata"),
        ("Fedora/RHEL", "DNF", "RPM repositories", "RPM database + repository metadata"),
    ]

    print(
        f"{'Ecosystem':15} {'Manager':18} {'Repository':25} {'Metadata'}"
    )
    print("-" * 95)

    for row in ecosystems:
        print(f"{row[0]:15} {row[1]:18} {row[2]:25} {row[3]}")


# ============================================================================
# 22. PRACTICAL COMMAND CONCEPTS
# ============================================================================

def explain_common_commands() -> None:
    print_section("18. Typical package-manager operations")

    commands = {
        "install": "Acquire a package and resolve/install its dependencies.",
        "remove": "Remove a package while preserving packages still required.",
        "update": "Refresh package metadata from repositories.",
        "upgrade": "Move installed packages toward newer available versions.",
        "search": "Find packages by name or metadata.",
        "show/info": "Display package metadata and dependencies.",
        "list": "Display installed or available packages.",
        "freeze/lock": "Record exact versions for reproducibility.",
        "verify/check": "Validate package files, metadata, or integrity.",
        "clean": "Remove cached artifacts or obsolete metadata.",
    }

    for operation, description in commands.items():
        print(f"{operation:15} {description}")


# ============================================================================
# 23. TESTS
# ============================================================================

def run_assertion_tests(repository: Repository) -> None:
    print_section("19. Built-in verification tests")

    assert Version.parse("1.2.3") < Version.parse("2.0.0")
    assert VersionConstraint("^1.2.0").matches(Version.parse("1.9.9"))
    assert not VersionConstraint("^1.2.0").matches(Version.parse("2.0.0"))
    assert VersionConstraint("~1.2.0").matches(Version.parse("1.2.9"))
    assert not VersionConstraint("~1.2.0").matches(Version.parse("1.3.0"))

    resolved = DependencyResolver([repository]).resolve(
        "analytics-app",
        VersionConstraint("==1.0.0"),
    )

    assert "analytics-app" in resolved
    assert "parser" in resolved
    assert "database-driver" in resolved
    assert "http-core" in resolved

    graph = build_dependency_graph(resolved.values())
    assert not detect_cycle(graph)

    print("All assertions passed.")


# ============================================================================
# 24. FULL DEMONSTRATION
# ============================================================================

def main() -> None:
    print_section("PACKAGE MANAGEMENT STUDY PROGRAM")
    print(
        "This program demonstrates package-management mechanisms using "
        "a self-contained simulation."
    )

    explain_basic_terminology()
    demonstrate_versions()
    demonstrate_constraints()

    repository = create_sample_repository()

    print_section("Repository contents")
    for package_name in sorted(
        {
            package.name
            for versions in repository._packages.values()
            for package in versions
        }
    ):
        versions = repository.available_versions(package_name)
        print(
            f"{package_name:20} "
            + ", ".join(str(version) for version in versions)
        )

    demonstrate_resolution(repository)

    manager = PackageManager([repository])

    try:
        manager.install("analytics-app", "==1.0.0")
    except Exception as error:
        print("Unexpected installation error:", error)

    manager.show_installed()
    print_dependency_graph(manager.installed.values())

    manager.verify_integrity()
    demonstrate_lock_file(manager)

    manager.upgrade_all()
    manager.show_installed()
    manager.show_lock()

    demonstrate_cache(repository)
    demonstrate_isolation(repository)
    demonstrate_dependency_categories()
    demonstrate_repository_trust()
    demonstrate_conflict()
    demonstrate_edge_cases(repository)
    demonstrate_transaction_safety(manager)

    compare_update_strategies()
    explain_performance()
    explain_security()
    compare_ecosystems()
    explain_common_commands()
    run_assertion_tests(repository)

    manager.history_log()

    print_section("End of executable study")
    print(
        "The central model is: repository -> metadata -> dependency "
        "resolution -> artifact verification -> transaction -> installed "
        "environment -> lock state."
    )


if __name__ == "__main__":
    main()
