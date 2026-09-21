#!/usr/bin/env python3
"""
Linux Administration Project
============================

A comprehensive, self-contained learning and simulation program for Linux
server administration.

The program teaches and demonstrates:

- Linux administration terminology
- Users and groups
- User account configuration
- Password policy concepts
- SSH access concepts
- SSH key authentication
- File ownership and permissions
- Symbolic and numeric permissions
- Special permissions
- Package management concepts
- Services and service states
- Processes and signals
- Environment variables
- Shell commands
- Automated scripts
- Scheduled jobs
- Logging and auditing concepts
- Configuration validation
- Backups
- Monitoring
- Security hardening
- Least privilege
- Idempotent administration
- Failure handling
- A practical server administration simulation

The program intentionally uses a simulation layer for potentially destructive
operations such as creating operating-system users, changing permissions, or
starting services. This makes the file safe to run on ordinary computers while
still demonstrating the mechanisms and commands used on a real Linux server.

On an actual Linux server, administrators commonly use commands such as:

    useradd
    usermod
    passwd
    groupadd
    id
    groups
    ssh
    ssh-keygen
    chmod
    chown
    chgrp
    ls
    apt
    dnf
    yum
    systemctl
    journalctl
    ps
    top
    kill
    crontab
    find
    tar
    df
    du

The simulation prints the corresponding commands without executing privileged
changes.

Run:

    python3 linux_administration_project.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


# ---------------------------------------------------------------------------
# Basic terminology
# ---------------------------------------------------------------------------

"""
Linux administration is the practice of installing, configuring, securing,
monitoring, maintaining, and troubleshooting Linux systems.

A Linux server normally contains several important layers:

    Hardware
        |
    Kernel
        |
    Processes and services
        |
    Filesystems
        |
    Users and groups
        |
    Applications
        |
    Network services
        |
    Administrative automation

A system administrator must understand both the individual components and
their relationships.

Examples:

    A user may belong to a group.
    A group may own a directory.
    A directory may contain application files.
    An application may run as a system user.
    The application may be managed by systemd.
    SSH may provide remote administrative access.
    Logs may record authentication and service events.
"""


class PackageManager(Enum):
    """Common Linux package manager families."""

    APT = "apt"
    DNF = "dnf"
    YUM = "yum"
    PACMAN = "pacman"
    ZYPPER = "zypper"


class ServiceState(Enum):
    """Simplified service states."""

    STOPPED = "stopped"
    RUNNING = "running"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AuthenticationMethod(Enum):
    """Common SSH authentication mechanisms."""

    PASSWORD = "password"
    PUBLIC_KEY = "public-key"
    BOTH = "password-and-public-key"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def section(title: str) -> None:
    """Print a readable section heading."""

    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    """Print a smaller heading."""

    print()
    print("-" * 78)
    print(title)
    print("-" * 78)


def explain(label: str, value: object) -> None:
    """Print a labeled explanation."""

    print(f"{label}: {value}")


def run_command(
    command: Sequence[str],
    *,
    timeout: int = 10,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """
    Execute a read-only or explicitly requested command.

    This helper is intentionally available for harmless inspection commands.
    It does not automatically run privileged administrative commands.
    """

    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def command_text(command: Sequence[str]) -> str:
    """Convert a command list into shell-readable text."""

    return " ".join(shlex.quote(part) for part in command)


def is_valid_linux_username(username: str) -> bool:
    """
    Validate a conventional Linux username.

    Many distributions use restrictions around username characters and length.
    Exact policy can differ, so this function deliberately represents a
    conservative administrative policy rather than claiming to be universal.
    """

    return bool(re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username))


def is_valid_group_name(group: str) -> bool:
    """Validate a conventional Linux group name."""

    return bool(re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", group))


def hash_for_demo(value: str) -> str:
    """
    Produce a SHA-256 digest for demonstrations involving configuration
    fingerprints.

    This is NOT a password-storage recommendation. Linux password storage
    should use the operating system's password management facilities and
    modern password-hashing schemes.
    """

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# User and group management
# ---------------------------------------------------------------------------


@dataclass
class LinuxUser:
    """Represent the important attributes of a Linux account."""

    username: str
    uid: int
    primary_group: str
    supplementary_groups: Set[str] = field(default_factory=set)
    home_directory: str = ""
    shell: str = "/bin/bash"
    locked: bool = False
    ssh_authorized_keys: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.home_directory:
            self.home_directory = f"/home/{self.username}"

    @property
    def all_groups(self) -> Set[str]:
        """Return primary and supplementary group membership."""

        return {self.primary_group, *self.supplementary_groups}


class UserManager:
    """Safe in-memory simulation of Linux user and group administration."""

    def __init__(self) -> None:
        self.users: Dict[str, LinuxUser] = {}
        self.groups: Dict[str, Set[str]] = {}
        self.next_uid = 1000

        # Typical administrative/system accounts are represented separately.
        self.add_group("root")
        self.add_user(
            "root",
            primary_group="root",
            uid=0,
            home_directory="/root",
            shell="/bin/bash",
        )

    def add_group(self, group: str) -> None:
        """Create a group in the simulation."""

        if not is_valid_group_name(group):
            raise ValueError(f"Invalid group name: {group}")

        if group in self.groups:
            raise ValueError(f"Group already exists: {group}")

        self.groups[group] = set()

    def add_user(
        self,
        username: str,
        *,
        primary_group: Optional[str] = None,
        uid: Optional[int] = None,
        home_directory: Optional[str] = None,
        shell: str = "/bin/bash",
    ) -> LinuxUser:
        """Create a simulated user account."""

        if not is_valid_linux_username(username):
            raise ValueError(f"Invalid Linux username: {username}")

        if username in self.users:
            raise ValueError(f"User already exists: {username}")

        if primary_group is None:
            primary_group = username

        if primary_group not in self.groups:
            self.add_group(primary_group)

        assigned_uid = self.next_uid if uid is None else uid

        if uid is None:
            self.next_uid += 1
        else:
            self.next_uid = max(self.next_uid, uid + 1)

        user = LinuxUser(
            username=username,
            uid=assigned_uid,
            primary_group=primary_group,
            home_directory=home_directory or f"/home/{username}",
            shell=shell,
        )

        self.users[username] = user
        self.groups[primary_group].add(username)

        return user

    def add_user_to_group(self, username: str, group: str) -> None:
        """Add an existing user to an existing group."""

        if username not in self.users:
            raise KeyError(f"Unknown user: {username}")

        if group not in self.groups:
            raise KeyError(f"Unknown group: {group}")

        self.users[username].supplementary_groups.add(group)
        self.groups[group].add(username)

    def lock_user(self, username: str) -> None:
        """Lock an account in the simulation."""

        self.users[username].locked = True

    def unlock_user(self, username: str) -> None:
        """Unlock an account in the simulation."""

        self.users[username].locked = False

    def describe_user(self, username: str) -> None:
        """Display account information similar to id/groups output."""

        user = self.users[username]

        print(f"Username: {user.username}")
        print(f"UID: {user.uid}")
        print(f"Primary group: {user.primary_group}")
        print(f"Groups: {', '.join(sorted(user.all_groups))}")
        print(f"Home: {user.home_directory}")
        print(f"Shell: {user.shell}")
        print(f"Locked: {user.locked}")

    def show_commands(self, username: str) -> None:
        """Show the real Linux commands corresponding to the simulation."""

        user = self.users[username]

        print(command_text([
            "sudo",
            "useradd",
            "-m",
            "-s",
            user.shell,
            user.username,
        ]))

        print(command_text([
            "sudo",
            "usermod",
            "-aG",
            *sorted(user.supplementary_groups),
            user.username,
        ]) if user.supplementary_groups else "No supplementary groups required.")


def demonstrate_users_and_groups() -> UserManager:
    """Teach users, groups, UID/GID concepts, and account administration."""

    section("1. Users, groups, UIDs, GIDs, and account administration")

    manager = UserManager()

    manager.add_group("developers")
    manager.add_group("operations")
    manager.add_group("auditors")

    alice = manager.add_user("alice", primary_group="developers")
    bob = manager.add_user("bob", primary_group="developers")
    admin = manager.add_user("serveradmin", primary_group="operations")

    manager.add_user_to_group("alice", "operations")
    manager.add_user_to_group("bob", "auditors")
    manager.add_user_to_group("serveradmin", "auditors")

    print("A Linux account normally has:")
    print("  - a username")
    print("  - a numeric UID")
    print("  - a primary group")
    print("  - optional supplementary groups")
    print("  - a home directory")
    print("  - a login shell")
    print("  - authentication information")
    print()

    print("Example account:")
    manager.describe_user(alice.username)

    print()
    print("Equivalent administrative commands on a real Linux system:")
    manager.show_commands(alice.username)

    print()
    print("Important distinctions:")
    print("  UID identifies the user numerically.")
    print("  GID identifies a group numerically.")
    print("  Primary group is the account's default group.")
    print("  Supplementary groups provide additional access.")
    print("  root traditionally has UID 0 and unrestricted administrative power.")

    manager.lock_user("bob")
    print()
    print(f"Bob locked: {manager.users['bob'].locked}")

    manager.unlock_user("bob")
    print(f"Bob unlocked: {manager.users['bob'].locked}")

    return manager


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


@dataclass
class PermissionSet:
    """Represent read, write, and execute permissions."""

    read: bool = False
    write: bool = False
    execute: bool = False

    def numeric(self) -> int:
        """Convert rwx permissions into a numeric value."""

        return (
            (4 if self.read else 0)
            + (2 if self.write else 0)
            + (1 if self.execute else 0)
        )

    def symbolic(self) -> str:
        """Convert permissions to rwx form."""

        return (
            ("r" if self.read else "-")
            + ("w" if self.write else "-")
            + ("x" if self.execute else "-")
        )


@dataclass
class FilePermissions:
    """Represent the permission model of a file."""

    owner: str
    group: str
    owner_permissions: PermissionSet
    group_permissions: PermissionSet
    other_permissions: PermissionSet
    is_directory: bool = False
    setuid: bool = False
    setgid: bool = False
    sticky: bool = False

    def mode(self) -> int:
        """Return the traditional numeric mode representation."""

        special = (
            (4 if self.setuid else 0) * 1000
            + (2 if self.setgid else 0) * 1000
            + (1 if self.sticky else 0) * 1000
        )

        return (
            special
            + self.owner_permissions.numeric() * 100
            + self.group_permissions.numeric() * 10
            + self.other_permissions.numeric()
        )

    def symbolic(self) -> str:
        """Return a familiar ls-style permission string."""

        prefix = "d" if self.is_directory else "-"

        owner = self.owner_permissions.symbolic()
        group = self.group_permissions.symbolic()
        other = self.other_permissions.symbolic()

        if self.setuid:
            owner = owner[:2] + ("s" if self.owner_permissions.execute else "S")

        if self.setgid:
            group = group[:2] + ("s" if self.group_permissions.execute else "S")

        if self.sticky:
            other = other[:2] + ("t" if self.other_permissions.execute else "T")

        return prefix + owner + group + other


def permission_examples() -> None:
    """Demonstrate Linux rwx permissions and common modes."""

    section("2. Linux file ownership and permissions")

    examples = [
        (
            "Private file",
            FilePermissions(
                owner="alice",
                group="developers",
                owner_permissions=PermissionSet(True, True, False),
                group_permissions=PermissionSet(False, False, False),
                other_permissions=PermissionSet(False, False, False),
            ),
        ),
        (
            "Shared executable",
            FilePermissions(
                owner="alice",
                group="developers",
                owner_permissions=PermissionSet(True, True, True),
                group_permissions=PermissionSet(True, False, True),
                other_permissions=PermissionSet(True, False, True),
            ),
        ),
        (
            "Private directory",
            FilePermissions(
                owner="alice",
                group="developers",
                owner_permissions=PermissionSet(True, True, True),
                group_permissions=PermissionSet(False, False, False),
                other_permissions=PermissionSet(False, False, False),
                is_directory=True,
            ),
        ),
    ]

    for label, permissions in examples:
        print(f"{label}:")
        print(f"  symbolic = {permissions.symbolic()}")
        print(f"  numeric  = {permissions.mode():04d}")
        print()

    print("Permission values:")
    print("  read    = 4")
    print("  write   = 2")
    print("  execute = 1")
    print()
    print("Therefore:")
    print("  7 = rwx")
    print("  6 = rw-")
    print("  5 = r-x")
    print("  4 = r--")
    print("  0 = ---")

    print()
    print("Common commands:")
    print("  chmod 640 report.txt")
    print("  chmod u+x script.sh")
    print("  chown alice:developers report.txt")
    print("  chgrp developers report.txt")
    print("  ls -l report.txt")

    print()
    print("Directory permissions have an important difference:")
    print("  read    allows listing directory entries")
    print("  write   allows creating/removing entries when execute permits access")
    print("  execute allows traversing/accessing objects in the directory")

    print()
    print("Special permissions:")
    print("  setuid  - executable can run with file owner's effective identity")
    print("  setgid  - executable or directory receives group-related behavior")
    print("  sticky  - commonly restricts deletion within shared directories")

    print()
    print("Security principle:")
    print("Do not solve access problems by blindly using chmod 777.")
    print("Grant the minimum permissions required by the workload.")


# ---------------------------------------------------------------------------
# Permission evaluator
# ---------------------------------------------------------------------------


def effective_permission(
    permissions: FilePermissions,
    username: str,
    groups: Iterable[str],
) -> PermissionSet:
    """
    Determine which permission class applies to a user.

    The simplified order is:

        owner
        group
        other

    Real Linux permission checking has additional details involving ACLs,
    capabilities, root behavior, mount options, and filesystem semantics.
    """

    group_set = set(groups)

    if username == permissions.owner:
        return permissions.owner_permissions

    if permissions.group in group_set:
        return permissions.group_permissions

    return permissions.other_permissions


def permission_check_demo(manager: UserManager) -> None:
    """Demonstrate permission evaluation."""

    section("3. Permission checking and least privilege")

    project_file = FilePermissions(
        owner="alice",
        group="developers",
        owner_permissions=PermissionSet(True, True, True),
        group_permissions=PermissionSet(True, True, True),
        other_permissions=PermissionSet(False, False, False),
    )

    for username in ["alice", "bob", "serveradmin", "root"]:
        user = manager.users[username]
        permission = effective_permission(
            project_file,
            username,
            user.all_groups,
        )

        print(
            f"{username:12} -> {permission.symbolic()} "
            f"(numeric {permission.numeric()})"
        )

    print()
    print("This demonstrates why groups are useful:")
    print("A file can be shared with a defined operational team without")
    print("granting the same access to every account on the machine.")


# ---------------------------------------------------------------------------
# SSH
# ---------------------------------------------------------------------------


@dataclass
class SSHConfiguration:
    """Represent important SSH server settings."""

    port: int = 22
    permit_root_login: str = "prohibit-password"
    password_authentication: bool = False
    pubkey_authentication: bool = True
    max_auth_tries: int = 3
    allow_users: Set[str] = field(default_factory=set)
    allow_groups: Set[str] = field(default_factory=set)
    idle_timeout_seconds: int = 900

    def validate(self) -> List[str]:
        """Return configuration problems."""

        errors: List[str] = []

        if not 1 <= self.port <= 65535:
            errors.append("SSH port must be between 1 and 65535.")

        if self.max_auth_tries < 1:
            errors.append("MaxAuthTries must be positive.")

        if self.idle_timeout_seconds < 0:
            errors.append("Idle timeout cannot be negative.")

        if self.password_authentication and not self.pubkey_authentication:
            errors.append(
                "Password-only authentication requires stronger compensating controls."
            )

        if self.permit_root_login == "yes":
            errors.append(
                "Direct root SSH login increases the remote administrative attack surface."
            )

        return errors

    def show(self) -> None:
        """Display representative sshd configuration."""

        settings = {
            "Port": self.port,
            "PermitRootLogin": self.permit_root_login,
            "PasswordAuthentication": "yes" if self.password_authentication else "no",
            "PubkeyAuthentication": "yes" if self.pubkey_authentication else "no",
            "MaxAuthTries": self.max_auth_tries,
            "ClientAliveInterval": self.idle_timeout_seconds,
        }

        for key, value in settings.items():
            print(f"{key} {value}")

        if self.allow_users:
            print("AllowUsers " + " ".join(sorted(self.allow_users)))

        if self.allow_groups:
            print("AllowGroups " + " ".join(sorted(self.allow_groups)))


def demonstrate_ssh(manager: UserManager) -> None:
    """Demonstrate SSH concepts and secure configuration."""

    section("4. SSH remote administration")

    print("SSH provides encrypted remote administration.")
    print()
    print("Typical key-authentication flow:")
    print("  1. Generate a key pair.")
    print("  2. Keep the private key secret.")
    print("  3. Install the public key in ~/.ssh/authorized_keys.")
    print("  4. The client proves possession of the private key.")
    print("  5. The server grants access if policy permits.")

    print()
    print("Example key generation command:")
    print("  ssh-keygen -t ed25519 -C 'administrator@example.com'")

    print()
    print("Example public-key installation:")
    print("  ssh-copy-id alice@server.example.com")

    configuration = SSHConfiguration(
        port=22,
        permit_root_login="prohibit-password",
        password_authentication=False,
        pubkey_authentication=True,
        max_auth_tries=3,
        allow_users={"serveradmin", "alice"},
    )

    print()
    print("Representative sshd configuration:")
    configuration.show()

    errors = configuration.validate()

    print()
    if errors:
        print("Configuration validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("SSH configuration validation: PASS")

    manager.users["alice"].ssh_authorized_keys.append(
        "ssh-ed25519 AAAAEXAMPLEKEY alice@example"
    )

    print()
    print("Alice authorized keys:")
    for key in manager.users["alice"].ssh_authorized_keys:
        print(f"  {key}")

    print()
    print("SSH security practices:")
    print("  - Prefer modern public-key authentication.")
    print("  - Protect private keys.")
    print("  - Restrict administrative accounts.")
    print("  - Avoid direct root login when operationally unnecessary.")
    print("  - Review authentication logs.")
    print("  - Keep OpenSSH patched.")
    print("  - Restrict network exposure with firewall policy.")
    print("  - Use a bastion or VPN when appropriate.")


# ---------------------------------------------------------------------------
# Package management
# ---------------------------------------------------------------------------


@dataclass
class Package:
    """Represent a package in a simulated package database."""

    name: str
    version: str
    installed: bool = False


class PackageManagerSimulator:
    """Teach package installation and repository concepts."""

    def __init__(self, manager: PackageManager) -> None:
        self.manager = manager
        self.packages: Dict[str, Package] = {
            "openssh-server": Package("openssh-server", "9.x"),
            "curl": Package("curl", "8.x"),
            "git": Package("git", "2.x"),
            "python3": Package("python3", "3.x"),
            "nginx": Package("nginx", "1.x"),
        }

    def command(self, action: str, package: str = "") -> List[str]:
        """Generate a package-manager command."""

        if self.manager == PackageManager.APT:
            if action == "update":
                return ["sudo", "apt", "update"]
            if action == "upgrade":
                return ["sudo", "apt", "upgrade"]
            if action == "install":
                return ["sudo", "apt", "install", "-y", package]
            if action == "remove":
                return ["sudo", "apt", "remove", "-y", package]

        if self.manager == PackageManager.DNF:
            if action == "update":
                return ["sudo", "dnf", "makecache"]
            if action == "upgrade":
                return ["sudo", "dnf", "upgrade"]
            if action == "install":
                return ["sudo", "dnf", "install", "-y", package]
            if action == "remove":
                return ["sudo", "dnf", "remove", "-y", package]

        raise ValueError(f"Unsupported simulated package action: {action}")

    def install(self, package: str) -> None:
        """Mark a package installed."""

        if package not in self.packages:
            raise KeyError(f"Package not found in simulation: {package}")

        self.packages[package].installed = True

    def show_state(self) -> None:
        """Display package database state."""

        for package in self.packages.values():
            status = "installed" if package.installed else "not installed"
            print(f"{package.name:20} {package.version:5} {status}")


def demonstrate_packages() -> PackageManagerSimulator:
    """Demonstrate package management."""

    section("5. Package management")

    simulator = PackageManagerSimulator(PackageManager.APT)

    print("Package managers resolve, install, update, and remove software.")
    print("Examples include apt on Debian/Ubuntu and dnf on Fedora/RHEL-family systems.")

    print()
    print("Update repository metadata:")
    print(" ", command_text(simulator.command("update")))

    print("Install Nginx:")
    print(" ", command_text(simulator.command("install", "nginx")))

    simulator.install("nginx")

    print()
    print("Simulated package database:")
    simulator.show_state()

    print()
    print("Important package-management concepts:")
    print("  Repository: source of signed package metadata and packages.")
    print("  Package: distributable software unit.")
    print("  Dependency: software required by another package.")
    print("  Version: specific release of a package.")
    print("  Update: newer package release.")
    print("  Upgrade: process of moving installed software to newer versions.")
    print("  Remove: uninstalling software while respecting dependency rules.")

    print()
    print("Operational practice:")
    print("Keep production package updates controlled, tested, logged, and recoverable.")

    return simulator


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


@dataclass
class Service:
    """Represent a system service."""

    name: str
    state: ServiceState = ServiceState.STOPPED
    enabled_at_boot: bool = False
    description: str = ""

    def start(self) -> None:
        """Start the simulated service."""

        if self.state == ServiceState.FAILED:
            raise RuntimeError(f"Cannot start failed service without recovery: {self.name}")

        self.state = ServiceState.RUNNING

    def stop(self) -> None:
        """Stop the service."""

        self.state = ServiceState.STOPPED

    def restart(self) -> None:
        """Restart the service."""

        self.stop()
        self.start()

    def enable(self) -> None:
        """Enable service startup."""

        self.enabled_at_boot = True

    def disable(self) -> None:
        """Disable service startup."""

        self.enabled_at_boot = False


class ServiceManager:
    """Simulation of basic systemd service operations."""

    def __init__(self) -> None:
        self.services: Dict[str, Service] = {}

    def register(self, service: Service) -> None:
        """Register a service."""

        self.services[service.name] = service

    def status(self, name: str) -> Service:
        """Return service status."""

        return self.services[name]

    def show_systemctl_examples(self, name: str) -> None:
        """Print representative systemctl commands."""

        for action in ["status", "start", "stop", "restart", "enable", "disable"]:
            print(f"  systemctl {action} {name}")


def demonstrate_services() -> ServiceManager:
    """Demonstrate systemd-style service management."""

    section("6. Services and systemd")

    manager = ServiceManager()

    manager.register(Service(
        name="ssh",
        description="OpenSSH server",
    ))

    manager.register(Service(
        name="nginx",
        description="Web server",
    ))

    manager.register(Service(
        name="cron",
        description="Job scheduler",
    ))

    ssh_service = manager.status("ssh")
    ssh_service.start()
    ssh_service.enable()

    nginx_service = manager.status("nginx")
    nginx_service.start()
    nginx_service.enable()

    for service in manager.services.values():
        print(
            f"{service.name:8} "
            f"state={service.state.value:8} "
            f"enabled={service.enabled_at_boot}"
        )

    print()
    print("Typical systemctl commands for nginx:")
    manager.show_systemctl_examples("nginx")

    print()
    print("systemd responsibilities commonly include:")
    print("  - starting services")
    print("  - stopping services")
    print("  - restarting services")
    print("  - supervising services")
    print("  - enabling boot-time startup")
    print("  - dependency management")
    print("  - collecting service state and logs")

    return manager


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------


def demonstrate_processes() -> None:
    """Demonstrate process inspection safely."""

    section("7. Processes and signals")

    print("A process is a running instance of a program.")
    print("Important concepts include PID, PPID, process state, CPU usage, and memory usage.")

    print()
    print("Common commands:")
    print("  ps aux")
    print("  ps -ef")
    print("  top")
    print("  htop")
    print("  pgrep nginx")
    print("  kill PID")
    print("  kill -TERM PID")
    print("  kill -KILL PID")

    print()
    print("Signal distinction:")
    print("  SIGTERM asks a process to terminate cleanly.")
    print("  SIGKILL terminates immediately and cannot be handled by the target.")
    print("Therefore SIGTERM should generally be preferred when possible.")

    if shutil.which("ps"):
        result = run_command(["ps", "-eo", "pid,ppid,comm"], timeout=5)
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            print()
            print("A small sample of the current process table:")
            for line in lines[:8]:
                print(f"  {line}")


# ---------------------------------------------------------------------------
# Filesystem and storage
# ---------------------------------------------------------------------------


def demonstrate_filesystem_commands() -> None:
    """Demonstrate filesystem administration commands."""

    section("8. Filesystems, storage, and disk usage")

    print("Linux presents storage through a hierarchical filesystem.")
    print("The root filesystem is represented by /.")

    print()
    print("Important paths:")
    paths = {
        "/etc": "system and application configuration",
        "/var": "variable data such as logs and service data",
        "/home": "regular users' home directories",
        "/root": "root user's home directory",
        "/tmp": "temporary files",
        "/usr": "user-space programs and libraries",
        "/opt": "optional application software",
        "/dev": "device nodes",
        "/proc": "process and kernel information interface",
        "/sys": "kernel and device information interface",
    }

    for path, description in paths.items():
        print(f"  {path:8} -> {description}")

    print()
    print("Useful commands:")
    print("  df -h        filesystem capacity")
    print("  du -sh DIR   directory usage")
    print("  lsblk        block devices")
    print("  mount        mounted filesystems")
    print("  find         search filesystem objects")

    print()
    print("Storage failure conditions to monitor:")
    print("  - nearly full filesystem")
    print("  - inode exhaustion")
    print("  - read-only remount")
    print("  - failing disks")
    print("  - runaway logs")
    print("  - uncontrolled temporary files")


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------


def demonstrate_environment() -> None:
    """Teach environment variables and PATH."""

    section("9. Environment variables and PATH")

    print("Environment variables provide process configuration.")
    print()
    print("Examples:")
    for variable in ["HOME", "PATH", "SHELL", "USER"]:
        value = os.environ.get(variable, "<not defined>")
        print(f"  {variable}={value}")

    print()
    print("PATH is a colon-separated list of directories used to locate executables.")
    print("A safer administration pattern is to use explicit executable paths in")
    print("critical automation when ambiguity could cause a security problem.")

    print()
    print("Python can read an environment variable with:")
    print("  os.environ.get('VARIABLE_NAME')")


# ---------------------------------------------------------------------------
# Shell scripting concepts
# ---------------------------------------------------------------------------


class ShellScriptBuilder:
    """Build a safe shell script as text rather than executing it."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.lines: List[str] = [
            "#!/usr/bin/env bash",
            "set -Eeuo pipefail",
            "",
            f"# Automated administration script: {name}",
        ]

    def add(self, line: str) -> None:
        """Append a shell line."""

        self.lines.append(line)

    def text(self) -> str:
        """Return the complete script."""

        return "\n".join(self.lines) + "\n"


def demonstrate_shell_automation() -> str:
    """Create a production-style shell automation example."""

    section("10. Shell automation")

    script = ShellScriptBuilder("server_health_check")

    script.add('LOG_FILE="/var/log/server-health-check.log"')
    script.add('timestamp="$(date -Is)"')
    script.add('echo "[$timestamp] health check started" >> "$LOG_FILE"')
    script.add("")
    script.add('if systemctl is-active --quiet ssh; then')
    script.add('    echo "[$timestamp] ssh: OK" >> "$LOG_FILE"')
    script.add("else")
    script.add('    echo "[$timestamp] ssh: FAILED" >> "$LOG_FILE"')
    script.add("    exit 1")
    script.add("fi")
    script.add("")
    script.add('disk_usage="$(df -P / | awk \'NR==2 {gsub("%","",$5); print $5}\')"')
    script.add('if [ "$disk_usage" -ge 90 ]; then')
    script.add('    echo "[$timestamp] disk usage critical: ${disk_usage}%" >> "$LOG_FILE"')
    script.add("    exit 2")
    script.add("fi")
    script.add("")
    script.add('echo "[$timestamp] health check completed" >> "$LOG_FILE"')

    text = script.text()

    print(text)

    print("Important shell scripting practices:")
    print("  set -e stops after many command failures.")
    print("  set -u detects unset variables.")
    print("  set -o pipefail detects failures within pipelines.")
    print("  Quote variables to avoid word-splitting and globbing problems.")
    print("  Validate external input before using it in commands.")
    print("  Use absolute paths where command resolution must be controlled.")

    return text


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


@dataclass
class ScheduledJob:
    """Represent a cron-style scheduled job."""

    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str
    command: str
    owner: str = "root"

    def expression(self) -> str:
        """Return a cron entry."""

        return (
            f"{self.minute} {self.hour} {self.day_of_month} "
            f"{self.month} {self.day_of_week} {self.command}"
        )


def demonstrate_scheduling() -> None:
    """Demonstrate cron scheduling."""

    section("11. Scheduling automated administration")

    jobs = [
        ScheduledJob(
            minute="0",
            hour="2",
            day_of_month="*",
            month="*",
            day_of_week="*",
            command="/usr/local/sbin/server-backup",
        ),
        ScheduledJob(
            minute="*/15",
            hour="*",
            day_of_month="*",
            month="*",
            day_of_week="*",
            command="/usr/local/sbin/server-health-check",
        ),
    ]

    for job in jobs:
        print(f"{job.owner}: {job.expression()}")

    print()
    print("Cron fields:")
    print("  minute hour day-of-month month day-of-week command")

    print()
    print("Automation should be:")
    print("  - idempotent where possible")
    print("  - observable through logs")
    print("  - safe when run repeatedly")
    print("  - explicit about failure")
    print("  - protected from unauthorized modification")


# ---------------------------------------------------------------------------
# Logging and auditing
# ---------------------------------------------------------------------------


@dataclass
class LogEvent:
    """Represent a security or operations log event."""

    timestamp: datetime
    service: str
    severity: str
    message: str


class AuditLog:
    """Simple in-memory audit log."""

    def __init__(self) -> None:
        self.events: List[LogEvent] = []

    def record(self, service: str, severity: str, message: str) -> None:
        """Record an event."""

        self.events.append(
            LogEvent(
                timestamp=datetime.now(timezone.utc),
                service=service,
                severity=severity,
                message=message,
            )
        )

    def show(self, severity: Optional[str] = None) -> None:
        """Display audit events."""

        for event in self.events:
            if severity and event.severity != severity:
                continue

            print(
                f"{event.timestamp.isoformat()} "
                f"{event.service:<10} "
                f"{event.severity:<8} "
                f"{event.message}"
            )


def demonstrate_logging() -> AuditLog:
    """Demonstrate operational logging."""

    section("12. Logging and auditing")

    audit = AuditLog()

    audit.record("sshd", "INFO", "Accepted public key for alice")
    audit.record("sshd", "WARN", "Repeated authentication failure")
    audit.record("nginx", "INFO", "Worker started")
    audit.record("systemd", "INFO", "nginx.service entered running state")
    audit.record("backup", "ERROR", "Backup destination unavailable")

    audit.show()

    print()
    print("Typical Linux logging tools:")
    print("  journalctl")
    print("  /var/log/")
    print("  logger")
    print("  systemd-journald")

    print()
    print("A useful operational log should answer:")
    print("  What happened?")
    print("  When did it happen?")
    print("  Which component produced the event?")
    print("  What severity does it have?")
    print("  What identity or process was involved?")
    print("  Can the event be correlated with another event?")

    return audit


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


class BackupManager:
    """Safe local backup demonstration using a temporary directory."""

    def __init__(self, source: Path, destination: Path) -> None:
        self.source = source
        self.destination = destination

    def create_backup(self) -> Path:
        """Create a timestamped backup copy."""

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.destination / f"backup-{timestamp}"

        target.mkdir(parents=True, exist_ok=False)

        for source_file in self.source.rglob("*"):
            relative = source_file.relative_to(self.source)
            destination_file = target / relative

            if source_file.is_dir():
                destination_file.mkdir(parents=True, exist_ok=True)
            else:
                destination_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, destination_file)

        return target


def demonstrate_backup() -> None:
    """Demonstrate a small safe backup operation."""

    section("13. Backups and recovery")

    with tempfile.TemporaryDirectory(prefix="linux-admin-demo-") as temporary_directory:
        root = Path(temporary_directory)
        source = root / "application"
        destination = root / "backups"

        source.mkdir()
        destination.mkdir()

        (source / "config.txt").write_text(
            "application_port=8080\n"
            "environment=production\n",
            encoding="utf-8",
        )

        (source / "data.txt").write_text(
            "important application data\n",
            encoding="utf-8",
        )

        backup = BackupManager(source, destination)
        backup_path = backup.create_backup()

        print(f"Source directory: {source}")
        print(f"Backup directory: {backup_path}")

        files = sorted(
            str(path.relative_to(backup_path))
            for path in backup_path.rglob("*")
            if path.is_file()
        )

        print("Backed-up files:")
        for filename in files:
            print(f"  {filename}")

    print()
    print("A backup strategy should consider:")
    print("  - what must be backed up")
    print("  - backup frequency")
    print("  - retention")
    print("  - encryption")
    print("  - off-host storage")
    print("  - restoration testing")
    print("  - recovery time objective (RTO)")
    print("  - recovery point objective (RPO)")


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


@dataclass
class ServerConfiguration:
    """Represent a simplified server security configuration."""

    hostname: str
    ssh: SSHConfiguration
    firewall_enabled: bool
    automatic_security_updates: bool
    unnecessary_services: Set[str]
    admin_users: Set[str]

    def validate(self, user_manager: UserManager) -> List[str]:
        """Validate server configuration."""

        errors: List[str] = []

        errors.extend(self.ssh.validate())

        if not self.hostname:
            errors.append("Hostname must not be empty.")

        if not self.firewall_enabled:
            errors.append("Firewall is not enabled.")

        if not self.automatic_security_updates:
            errors.append("Automatic security update policy is disabled.")

        if self.unnecessary_services:
            errors.append(
                "Unnecessary services are enabled: "
                + ", ".join(sorted(self.unnecessary_services))
            )

        for username in self.admin_users:
            if username not in user_manager.users:
                errors.append(f"Administrative user does not exist: {username}")

        if "root" in self.ssh.allow_users:
            errors.append("SSH policy explicitly permits direct root access.")

        return errors


def demonstrate_security_validation(manager: UserManager) -> ServerConfiguration:
    """Demonstrate security hardening and validation."""

    section("14. Server security validation")

    configuration = ServerConfiguration(
        hostname="app-server-01",
        ssh=SSHConfiguration(
            password_authentication=False,
            pubkey_authentication=True,
            permit_root_login="prohibit-password",
            allow_users={"serveradmin"},
        ),
        firewall_enabled=True,
        automatic_security_updates=True,
        unnecessary_services=set(),
        admin_users={"serveradmin"},
    )

    problems = configuration.validate(manager)

    if problems:
        print("Security validation: FAIL")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("Security validation: PASS")

    print()
    print("Hardening areas:")
    print("  Account security")
    print("  SSH configuration")
    print("  Network exposure")
    print("  Firewall rules")
    print("  Package patching")
    print("  Service minimization")
    print("  File permissions")
    print("  Logging and auditing")
    print("  Backups")
    print("  Monitoring")
    print("  Secrets management")

    return configuration


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


class DesiredState:
    """Simple desired-state representation."""

    def __init__(self) -> None:
        self.users: Dict[str, Set[str]] = {}
        self.services_enabled: Set[str] = set()
        self.packages: Set[str] = set()

    def add_user(self, username: str, groups: Iterable[str]) -> None:
        """Declare desired user membership."""

        self.users[username] = set(groups)

    def enable_service(self, service: str) -> None:
        """Declare desired service state."""

        self.services_enabled.add(service)

    def install_package(self, package: str) -> None:
        """Declare desired package installation."""

        self.packages.add(package)


def compare_desired_state(
    desired: DesiredState,
    user_manager: UserManager,
    service_manager: ServiceManager,
    package_manager: PackageManagerSimulator,
) -> List[str]:
    """Compare simulated actual state against desired state."""

    changes: List[str] = []

    for username, groups in desired.users.items():
        if username not in user_manager.users:
            changes.append(f"Create user: {username}")
            continue

        actual_groups = user_manager.users[username].all_groups
        missing_groups = groups - actual_groups

        for group in sorted(missing_groups):
            changes.append(f"Add {username} to group {group}")

    for service_name in desired.services_enabled:
        service = service_manager.services.get(service_name)

        if service is None:
            changes.append(f"Service not registered: {service_name}")
        elif not service.enabled_at_boot:
            changes.append(f"Enable service: {service_name}")

    for package in desired.packages:
        package_state = package_manager.packages.get(package)

        if package_state is None:
            changes.append(f"Package unavailable: {package}")
        elif not package_state.installed:
            changes.append(f"Install package: {package}")

    return changes


def demonstrate_idempotence(
    manager: UserManager,
    services: ServiceManager,
    packages: PackageManagerSimulator,
) -> None:
    """Demonstrate desired-state thinking."""

    section("15. Idempotent administration and configuration management")

    desired = DesiredState()

    desired.add_user("alice", {"developers", "operations"})
    desired.add_user("serveradmin", {"operations"})
    desired.enable_service("ssh")
    desired.enable_service("nginx")
    desired.install_package("nginx")
    desired.install_package("git")

    changes = compare_desired_state(
        desired,
        manager,
        services,
        packages,
    )

    print("Desired state:")
    print("  users:", desired.users)
    print("  services:", sorted(desired.services_enabled))
    print("  packages:", sorted(desired.packages))

    print()
    print("Required changes:")
    if changes:
        for change in changes:
            print(f"  - {change}")
    else:
        print("  None. Actual state already matches desired state.")

    print()
    print("Idempotence means an operation can be safely applied repeatedly")
    print("without producing unintended additional changes.")
    print()
    print("For example:")
    print("  'ensure nginx is installed'")
    print("is preferable to blindly running an installation command every time.")


# ---------------------------------------------------------------------------
# Networking fundamentals
# ---------------------------------------------------------------------------


def demonstrate_networking() -> None:
    """Explain administration-relevant networking."""

    section("16. Networking fundamentals for administrators")

    print("Important concepts:")
    print("  IP address       identifies a network interface/address.")
    print("  Subnet           defines a network boundary.")
    print("  Gateway          forwards traffic beyond the local network.")
    print("  DNS              maps names to addresses.")
    print("  TCP              connection-oriented transport protocol.")
    print("  UDP              connectionless transport protocol.")
    print("  Port             identifies a service endpoint.")
    print("  Socket           combines addressing and transport information.")

    print()
    print("Useful commands:")
    print("  ip addr")
    print("  ip route")
    print("  ss -tulpn")
    print("  ping")
    print("  traceroute")
    print("  dig")
    print("  curl")

    print()
    print("A common diagnostic sequence is:")
    print("  1. Check interface state.")
    print("  2. Check IP configuration.")
    print("  3. Check routing.")
    print("  4. Check DNS.")
    print("  5. Check whether the destination port is listening.")
    print("  6. Check firewall rules.")
    print("  7. Check the service logs.")


# ---------------------------------------------------------------------------
# Troubleshooting
# ---------------------------------------------------------------------------


def troubleshooting_matrix() -> None:
    """Provide a structured troubleshooting model."""

    section("17. Troubleshooting methodology")

    problems = [
        (
            "Cannot SSH",
            [
                "Check network connectivity.",
                "Check sshd service status.",
                "Check listening port with ss.",
                "Check firewall rules.",
                "Check username and authentication method.",
                "Inspect authentication logs.",
                "Validate sshd configuration.",
            ],
        ),
        (
            "Permission denied",
            [
                "Check file ownership with ls -l.",
                "Check user identity with id.",
                "Check group membership.",
                "Check directory traversal permissions.",
                "Check ACLs if configured.",
                "Check mount and security controls.",
            ],
        ),
        (
            "Service will not start",
            [
                "Run systemctl status SERVICE.",
                "Inspect journalctl logs.",
                "Validate configuration syntax.",
                "Check port conflicts.",
                "Check file permissions.",
                "Check dependencies.",
                "Check available disk space.",
            ],
        ),
        (
            "Disk is full",
            [
                "Run df -h.",
                "Check inode usage with df -i.",
                "Find large directories with du.",
                "Inspect logs.",
                "Check deleted-but-open files.",
                "Remove data only after understanding its purpose.",
            ],
        ),
    ]

    for problem, steps in problems:
        print(problem + ":")
        for index, step in enumerate(steps, start=1):
            print(f"  {index}. {step}")
        print()


# ---------------------------------------------------------------------------
# Safe command execution demonstration
# ---------------------------------------------------------------------------


def demonstrate_read_only_system_inspection() -> None:
    """Run harmless local inspection commands when available."""

    section("18. Safe local inspection")

    commands = [
        ["uname", "-a"],
        ["id"],
        ["whoami"],
    ]

    for command in commands:
        executable = shutil.which(command[0])

        if not executable:
            print(f"{command[0]}: command not available on this platform.")
            continue

        try:
            result = run_command(command, timeout=5)

            print(f"$ {command_text(command)}")

            if result.stdout.strip():
                print(result.stdout.strip())

            if result.stderr.strip():
                print("stderr:", result.stderr.strip())

        except (subprocess.SubprocessError, OSError) as error:
            print(f"Unable to run {command[0]}: {error}")

        print()


# ---------------------------------------------------------------------------
# Administrative checklist
# ---------------------------------------------------------------------------


def production_checklist() -> None:
    """Display a practical production server checklist."""

    section("19. Production Linux administration checklist")

    checklist = [
        "Define server purpose and ownership.",
        "Use a documented hostname.",
        "Create named administrative accounts.",
        "Avoid routine direct root login.",
        "Use strong authentication and SSH keys where appropriate.",
        "Use groups to implement role-based access.",
        "Apply least-privilege permissions.",
        "Install only required packages.",
        "Remove or disable unnecessary services.",
        "Configure firewall policy.",
        "Keep operating-system packages patched.",
        "Configure logging and monitoring.",
        "Protect configuration and secret files.",
        "Implement tested backups.",
        "Document recovery procedures.",
        "Monitor CPU, memory, storage, network, and service health.",
        "Automate repeatable tasks.",
        "Make automation observable and idempotent.",
        "Test changes before production deployment.",
        "Record significant administrative changes.",
    ]

    for item in checklist:
        print(f"[ ] {item}")


# ---------------------------------------------------------------------------
# Capstone simulation
# ---------------------------------------------------------------------------


@dataclass
class LinuxServer:
    """An integrated server administration simulation."""

    hostname: str
    users: UserManager
    packages: PackageManagerSimulator
    services: ServiceManager
    ssh: SSHConfiguration
    firewall_enabled: bool = True

    def status_report(self) -> None:
        """Print an integrated server status report."""

        section(f"20. Server status report: {self.hostname}")

        print("System:")
        print(f"  hostname: {self.hostname}")
        print(f"  firewall: {'enabled' if self.firewall_enabled else 'disabled'}")

        print()
        print("Users:")
        for user in self.users.users.values():
            print(
                f"  {user.username:15} "
                f"uid={user.uid:<5} "
                f"locked={str(user.locked):<5}"
            )

        print()
        print("Packages:")
        for package in self.packages.packages.values():
            if package.installed:
                print(f"  {package.name} {package.version}")

        print()
        print("Services:")
        for service in self.services.services.values():
            print(
                f"  {service.name:10} "
                f"state={service.state.value:<8} "
                f"enabled={service.enabled_at_boot}"
            )

        print()
        print("SSH:")
        print(f"  port={self.ssh.port}")
        print(f"  public-key-auth={self.ssh.pubkey_authentication}")
        print(f"  password-auth={self.ssh.password_authentication}")
        print(f"  root-login={self.ssh.permit_root_login}")


def build_server() -> LinuxServer:
    """Build a complete example server."""

    users = demonstrate_users_and_groups()
    packages = demonstrate_packages()
    services = demonstrate_services()

    ssh = SSHConfiguration(
        port=22,
        permit_root_login="prohibit-password",
        password_authentication=False,
        pubkey_authentication=True,
        max_auth_tries=3,
        allow_users={"serveradmin"},
    )

    return LinuxServer(
        hostname="app-server-01",
        users=users,
        packages=packages,
        services=services,
        ssh=ssh,
        firewall_enabled=True,
    )


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------


def test_permission_conversion() -> None:
    """Test rwx to numeric conversion."""

    permissions = PermissionSet(True, True, False)

    assert permissions.numeric() == 6
    assert permissions.symbolic() == "rw-"


def test_username_validation() -> None:
    """Test username policy."""

    assert is_valid_linux_username("alice")
    assert is_valid_linux_username("server_admin")
    assert not is_valid_linux_username("Alice!")
    assert not is_valid_linux_username("")


def test_user_group_membership() -> None:
    """Test group management."""

    manager = UserManager()
    manager.add_group("developers")
    manager.add_user("alice", primary_group="developers")
    manager.add_group("operations")
    manager.add_user_to_group("alice", "operations")

    assert "developers" in manager.users["alice"].all_groups
    assert "operations" in manager.users["alice"].all_groups


def test_service_lifecycle() -> None:
    """Test service lifecycle."""

    service = Service("nginx")
    assert service.state == ServiceState.STOPPED

    service.start()
    assert service.state == ServiceState.RUNNING

    service.stop()
    assert service.state == ServiceState.STOPPED

    service.enable()
    assert service.enabled_at_boot is True


def test_ssh_validation() -> None:
    """Test a secure SSH configuration."""

    ssh = SSHConfiguration(
        permit_root_login="no",
        password_authentication=False,
        pubkey_authentication=True,
    )

    assert ssh.validate() == []


def run_tests() -> None:
    """Run the internal test suite."""

    section("21. Internal tests")

    tests = [
        test_permission_conversion,
        test_username_validation,
        test_user_group_membership,
        test_service_lifecycle,
        test_ssh_validation,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
            passed += 1
        except AssertionError as error:
            print(f"FAIL  {test.__name__}: {error}")

    print()
    print(f"{passed}/{len(tests)} tests passed.")


# ---------------------------------------------------------------------------
# Advanced topics
# ---------------------------------------------------------------------------


def advanced_topics() -> None:
    """Explain advanced Linux administration concepts."""

    section("22. Advanced administration concepts")

    topics = {
        "ACLs": (
            "Access Control Lists provide more granular permissions than the "
            "traditional owner/group/other model."
        ),
        "Capabilities": (
            "Linux capabilities split some traditionally root-level privileges "
            "into more granular process privileges."
        ),
        "SELinux/AppArmor": (
            "Mandatory access-control systems can restrict what processes may "
            "do even when traditional Unix permissions allow an operation."
        ),
        "Namespaces": (
            "Namespaces isolate process views of resources and are fundamental "
            "to modern container implementations."
        ),
        "cgroups": (
            "Control groups constrain and account for resource consumption."
        ),
        "systemd units": (
            "systemd manages services and many other unit types through "
            "declarative configuration."
        ),
        "journald": (
            "systemd-journald collects structured system and service events."
        ),
        "Linux capabilities": (
            "Capabilities can reduce the need for full root privileges."
        ),
        "audit framework": (
            "Linux auditing can record security-relevant events for analysis."
        ),
        "containerization": (
            "Containers package applications while sharing the host kernel."
        ),
    }

    for topic, description in topics.items():
        print(f"{topic}:")
        print(f"  {description}")

    print()
    print("Advanced operational trade-offs:")
    print("  More security controls can increase operational complexity.")
    print("  More automation can reduce manual errors but can amplify mistakes.")
    print("  More monitoring improves visibility but increases storage and processing.")
    print("  More restrictive permissions improve isolation but may break applications.")
    print("  More services increase functionality but increase the attack surface.")


# ---------------------------------------------------------------------------
# Main educational sequence
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the complete Linux administration lesson."""

    print("Linux Administration Project")
    print("Comprehensive server administration learning and simulation")
    print()
    print("This program demonstrates administrative concepts without making")
    print("privileged changes to the host operating system.")

    manager = demonstrate_users_and_groups()
    permission_examples()
    permission_check_demo(manager)
    demonstrate_ssh(manager)
    packages = demonstrate_packages()
    services = demonstrate_services()
    demonstrate_processes()
    demonstrate_filesystem_commands()
    demonstrate_environment()
    demonstrate_shell_automation()
    demonstrate_scheduling()
    audit = demonstrate_logging()
    demonstrate_backup()
    demonstrate_security_validation(manager)
    demonstrate_idempotence(manager, services, packages)
    demonstrate_networking()
    troubleshooting_matrix()
    demonstrate_read_only_system_inspection()
    production_checklist()

    server = LinuxServer(
        hostname="production-app-01",
        users=manager,
        packages=packages,
        services=services,
        ssh=SSHConfiguration(
            permit_root_login="prohibit-password",
            password_authentication=False,
            pubkey_authentication=True,
            allow_users={"serveradmin"},
        ),
        firewall_enabled=True,
    )

    server.status_report()

    advanced_topics()
    run_tests()

    section("23. Key command reference")

    commands = [
        ("Identity", "id"),
        ("Current user", "whoami"),
        ("User information", "getent passwd USER"),
        ("Groups", "groups USER"),
        ("Create user", "sudo useradd -m USER"),
        ("Create group", "sudo groupadd GROUP"),
        ("Add group membership", "sudo usermod -aG GROUP USER"),
        ("Lock account", "sudo passwd -l USER"),
        ("SSH key generation", "ssh-keygen -t ed25519"),
        ("Permissions", "chmod MODE FILE"),
        ("Ownership", "chown USER:GROUP FILE"),
        ("Disk usage", "df -h"),
        ("Directory usage", "du -sh DIRECTORY"),
        ("Processes", "ps aux"),
        ("Sockets", "ss -tulpn"),
        ("Service status", "systemctl status SERVICE"),
        ("Start service", "sudo systemctl start SERVICE"),
        ("Enable service", "sudo systemctl enable SERVICE"),
        ("Service logs", "journalctl -u SERVICE"),
        ("Package update", "sudo apt update"),
        ("Package install", "sudo apt install PACKAGE"),
        ("File search", "find PATH -name PATTERN"),
    ]

    for purpose, command in commands:
        print(f"{purpose:24} {command}")

    section("24. Administrative principles")

    principles = [
        "Least privilege",
        "Defense in depth",
        "Explicit configuration",
        "Repeatable automation",
        "Idempotence",
        "Observability",
        "Test before production",
        "Backups and restoration testing",
        "Patch management",
        "Minimal attack surface",
        "Separation of duties",
        "Documented change management",
    ]

    for number, principle in enumerate(principles, start=1):
        print(f"{number:2}. {principle}")

    print()
    print("The Linux administrator's job is not simply to execute commands.")
    print("The administrator must understand why a change is required, what")
    print("access it grants, what dependencies it creates, how it can fail,")
    print("how it will be monitored, and how the system can be recovered.")

    # Keep the variable used so linters can see that the audit object is
    # intentionally created as part of the integrated lesson.
    _ = audit


if __name__ == "__main__":
    main()
