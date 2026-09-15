"""
Users and Groups on Linux
==========================

A self-contained study program covering:

    * users and user accounts
    * groups and supplementary groups
    * UID/GID concepts
    * /etc/passwd, /etc/group, /etc/shadow
    * file ownership and permission bits
    * read/write/execute permissions
    * symbolic and numeric chmod notation
    * umask
    * sudo and privilege escalation
    * authentication versus authorization
    * least privilege
    * setuid, setgid, and sticky bit
    * ACL concepts
    * service accounts
    * account lifecycle
    * permission evaluation
    * security and auditing
    * practical command execution
    * a safe in-memory permission simulator
    * testing and edge cases

The program is designed to be useful on Linux, but most educational
examples work on other operating systems without requiring root access.

Run:
    python3 users_groups_permissions.py

Some demonstrations use Linux commands when they are available.
Operations that modify the real system are intentionally NOT performed
automatically.
"""

from __future__ import annotations

import argparse
import grp
import os
import platform
import pwd
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    """Print a consistent educational section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    print("\n--- " + title + " ---")


def run_command(command: list[str]) -> tuple[int, str, str]:
    """
    Execute a read-only command.

    We return stdout and stderr rather than raising immediately so the caller
    can explain failures such as missing commands or insufficient privileges.
    """
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"Command not found: {command[0]}"
    except OSError as exc:
        return 1, "", str(exc)


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


# ---------------------------------------------------------------------------
# Basic operating-system identity
# ---------------------------------------------------------------------------

def demonstrate_current_identity() -> None:
    section("1. Current process identity")

    print(f"Operating system: {platform.system()}")
    print(f"Kernel/platform: {platform.platform()}")
    print(f"Current username: {getattr(pwd.getpwuid(os.getuid()), 'pw_name', 'unknown')}")
    print(f"Real UID: {os.getuid()}")
    print(f"Effective UID: {os.geteuid()}")
    print(f"Real GID: {os.getgid()}")
    print(f"Effective GID: {os.getegid()}")

    groups = os.getgroups()
    print(f"Supplementary group IDs: {groups}")

    print("\nImportant distinction:")
    print("Authentication answers 'Who are you?'")
    print("Authorization answers 'What are you allowed to do?'")
    print("Privilege management controls when and how additional authority")
    print("may be obtained.")


# ---------------------------------------------------------------------------
# User database
# ---------------------------------------------------------------------------

def explain_passwd_database() -> None:
    section("2. User accounts and the passwd database")

    print(
        "Linux commonly stores account metadata through the passwd database, "
        "traditionally represented by /etc/passwd."
    )

    print("\nTraditional /etc/passwd fields:")
    fields = [
        "username",
        "password placeholder (normally x)",
        "UID",
        "primary GID",
        "GECOS/comment",
        "home directory",
        "login shell",
    ]
    for index, field_name in enumerate(fields, 1):
        print(f"{index}. {field_name}")

    print(
        "\nModern systems normally store password hashes in /etc/shadow rather "
        "than placing them directly in /etc/passwd."
    )

    try:
        users = pwd.getpwall()
        print(f"\nAccounts visible through the system password database: {len(users)}")

        for account in users[:10]:
            print(
                f"  username={account.pw_name!r:20} "
                f"uid={account.pw_uid:<6} "
                f"gid={account.pw_gid:<6} "
                f"home={account.pw_dir!r}"
            )
    except Exception as exc:
        print(f"Unable to enumerate passwd database: {exc}")


def explain_user_classes() -> None:
    subsection("Human users, system users, and service accounts")

    print(
        "A human account normally has an interactive login, a home directory, "
        "and a shell appropriate for the user's workflow."
    )
    print(
        "A service account is normally created for a process or service. "
        "Giving a service its own identity makes its permissions easier to "
        "restrict and audit."
    )
    print(
        "A disabled shell such as /usr/sbin/nologin can prevent interactive "
        "login for accounts that do not need it."
    )


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

def demonstrate_groups() -> None:
    section("3. Groups and group membership")

    print("A group is a named collection of users identified internally by a GID.")
    print("Groups provide a convenient way to grant shared access without")
    print("assigning permissions separately to every user.")

    try:
        current_user = pwd.getpwuid(os.getuid())
        print(f"\nPrimary group: {current_user.pw_gid}")

        try:
            primary_group = grp.getgrgid(current_user.pw_gid)
            print(f"Primary group name: {primary_group.gr_name}")
        except KeyError:
            print("Primary GID has no corresponding visible group entry.")

        print("\nSupplementary groups:")
        for gid in os.getgroups():
            try:
                group = grp.getgrgid(gid)
                print(f"  {gid}: {group.gr_name}")
            except KeyError:
                print(f"  {gid}: <unknown group>")

        print("\nSelected groups from the group database:")
        for group in grp.getgrall()[:10]:
            print(f"  {group.gr_name}: GID={group.gr_gid}, members={group.gr_mem}")
    except Exception as exc:
        print(f"Unable to read group information: {exc}")


# ---------------------------------------------------------------------------
# Permission theory
# ---------------------------------------------------------------------------

def explain_permission_bits() -> None:
    section("4. Linux file permissions")

    print(
        "The traditional permission model evaluates three classes of subjects:"
    )
    print("  user/owner   -> permissions for the file owner")
    print("  group        -> permissions for the file's group")
    print("  other        -> permissions for everyone else")

    print("\nEach class can have:")
    print("  r = read    = 4")
    print("  w = write   = 2")
    print("  x = execute = 1")

    print("\nExamples:")
    examples = {
        "rwx": 7,
        "rw-": 6,
        "r-x": 5,
        "r--": 4,
        "-wx": 3,
        "-w-": 2,
        "--x": 1,
        "---": 0,
    }
    for symbolic, numeric in examples.items():
        print(f"  {symbolic} = {numeric}")

    print("\nCommon modes:")
    print("  644 = rw-r--r--")
    print("  640 = rw-r-----")
    print("  600 = rw-------")
    print("  755 = rwxr-xr-x")
    print("  750 = rwxr-x---")
    print("  700 = rwx------")

    print(
        "\nImportant: execute permission means different things for files and "
        "directories. For a regular file, x permits execution. For a "
        "directory, x permits traversal/search through the directory."
    )


def symbolic_permission(mode: int) -> str:
    """Return a human-readable symbolic permission string."""
    return stat.filemode(mode)


def permission_number(mode: int) -> str:
    """Return the ordinary three-digit permission representation."""
    return oct(mode & 0o777)[2:].zfill(3)


def demonstrate_mode_conversion() -> None:
    subsection("Converting permissions")

    for mode in (0o600, 0o640, 0o644, 0o700, 0o750, 0o755, 0o777):
        print(
            f"{permission_number(mode)} -> "
            f"{symbolic_permission(stat.S_IFREG | mode)}"
        )


# ---------------------------------------------------------------------------
# Real file inspection
# ---------------------------------------------------------------------------

def inspect_file(path: Path) -> None:
    section(f"5. Inspecting permissions: {path}")

    try:
        metadata = path.stat()
    except OSError as exc:
        print(f"Cannot inspect path: {exc}")
        return

    print(f"Path: {path}")
    print(f"Type: {stat.filemode(metadata.st_mode)}")
    print(f"Mode: {permission_number(metadata.st_mode)}")
    print(f"UID: {metadata.st_uid}")
    print(f"GID: {metadata.st_gid}")
    print(f"Size: {metadata.st_size} bytes")

    try:
        owner = pwd.getpwuid(metadata.st_uid).pw_name
    except KeyError:
        owner = "<unknown>"
    try:
        group = grp.getgrgid(metadata.st_gid).gr_name
    except KeyError:
        group = "<unknown>"

    print(f"Owner name: {owner}")
    print(f"Group name: {group}")

    print("\nPython access checks for the current process:")
    print(f"  readable:   {yes_no(os.access(path, os.R_OK))}")
    print(f"  writable:   {yes_no(os.access(path, os.W_OK))}")
    print(f"  executable: {yes_no(os.access(path, os.X_OK))}")


# ---------------------------------------------------------------------------
# Permission evaluator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Identity:
    """
    An abstract process identity.

    This model deliberately separates the owner UID, primary group and
    supplementary groups so permission evaluation can be studied without
    modifying the real operating system.
    """

    uid: int
    primary_gid: int
    supplementary_gids: frozenset[int] = frozenset()

    @property
    def all_gids(self) -> frozenset[int]:
        return frozenset({self.primary_gid, *self.supplementary_gids})


@dataclass(frozen=True)
class PermissionObject:
    """
    Minimal representation of a Unix-like permission-controlled object.
    """

    owner_uid: int
    group_gid: int
    mode: int


def permission_class(identity: Identity, obj: PermissionObject) -> str:
    """
    Determine whether owner, group, or other permissions apply.

    The owner test has priority. If the identity is not the owner but belongs
    to the owning group, group bits apply. Otherwise, other bits apply.

    This ordering is a crucial detail in traditional Unix permission checks.
    """
    if identity.uid == obj.owner_uid:
        return "owner"

    if obj.group_gid in identity.all_gids:
        return "group"

    return "other"


def has_permission(
    identity: Identity,
    obj: PermissionObject,
    requested: str,
) -> bool:
    """Evaluate r, w, and x against an abstract permission object."""
    if requested not in {"r", "w", "x"}:
        raise ValueError("requested permission must be r, w, or x")

    subject_class = permission_class(identity, obj)

    offsets = {
        "owner": 6,
        "group": 3,
        "other": 0,
    }
    values = {
        "r": 4,
        "w": 2,
        "x": 1,
    }

    bit_position = offsets[subject_class]
    required_value = values[requested]
    return bool((obj.mode >> bit_position) & required_value)


def demonstrate_permission_evaluator() -> None:
    section("6. Permission evaluation without changing the operating system")

    owner = Identity(uid=1000, primary_gid=100)
    teammate = Identity(uid=1001, primary_gid=100)
    outsider = Identity(uid=1002, primary_gid=200)
    object_info = PermissionObject(
        owner_uid=1000,
        group_gid=100,
        mode=0o640,
    )

    print("Simulated object: owner=UID 1000, group=GID 100, mode=640")
    print("Mode 640 means rw-r-----.")

    for label, identity in [
        ("owner", owner),
        ("group member", teammate),
        ("outsider", outsider),
    ]:
        print(f"\n{label}:")
        print(f"  selected permission class: {permission_class(identity, object_info)}")
        for requested in "rwx":
            print(
                f"  {requested}: "
                f"{yes_no(has_permission(identity, object_info, requested))}"
            )

    print(
        "\nEdge case: membership in the owning group does not mean the owner "
        "bits and group bits are combined. The applicable class is selected "
        "and that class's bits are evaluated."
    )


# ---------------------------------------------------------------------------
# Directory permissions
# ---------------------------------------------------------------------------

def explain_directory_permissions() -> None:
    section("7. Directory permissions")

    print("Directory permissions have a particularly important interpretation:")
    print("  r -> list directory entries")
    print("  w -> create, remove, or rename entries when combined appropriately")
    print("  x -> traverse/search the directory")
    print()
    print(
        "A user often needs x on every parent directory in a path. Therefore, "
        "a file can have readable bits while still being inaccessible because "
        "one of its parent directories cannot be traversed."
    )

    print("\nExample:")
    print("  /srv/project/data/report.txt")
    print("  A process needs suitable directory traversal permissions on")
    print("  /srv, /srv/project, and /srv/project/data to reach the file.")


# ---------------------------------------------------------------------------
# Special permission bits
# ---------------------------------------------------------------------------

def explain_special_bits() -> None:
    section("8. Special permission bits")

    print("setuid:")
    print(
        "  On an executable file, the process can run with the file owner's "
        "effective identity, subject to operating-system rules."
    )
    print("  Numeric prefix: 4xxx")
    print()
    print("setgid:")
    print(
        "  On an executable, it can provide the file group's identity to the "
        "process. On directories, new files can inherit the directory's group."
    )
    print("  Numeric prefix: 2xxx")
    print()
    print("sticky bit:")
    print(
        "  On a shared directory, it restricts deletion/renaming of entries "
        "to appropriate owners or privileged users."
    )
    print("  Numeric prefix: 1xxx")

    for mode in (0o4755, 0o2755, 0o1777):
        print(f"  {oct(mode)} -> {stat.filemode(stat.S_IFREG | mode)}")


# ---------------------------------------------------------------------------
# umask
# ---------------------------------------------------------------------------

def demonstrate_umask() -> None:
    section("9. umask")

    print(
        "umask removes permission bits from permissions requested during file "
        "or directory creation."
    )
    print("A simplified conceptual calculation is:")
    print("  resulting_mode = requested_mode & ~umask")

    requested_file_mode = 0o666
    requested_directory_mode = 0o777

    for mask in (0o022, 0o027, 0o077):
        file_mode = requested_file_mode & ~mask
        directory_mode = requested_directory_mode & ~mask
        print(
            f"umask {mask:03o}: "
            f"file={file_mode:03o}, directory={directory_mode:03o}"
        )

    print(
        "\nCaveat: actual creation also depends on the system call, filesystem, "
        "default ACLs, application behavior, and other operating-system rules."
    )


# ---------------------------------------------------------------------------
# sudo
# ---------------------------------------------------------------------------

def demonstrate_sudo() -> None:
    section("10. sudo and controlled privilege elevation")

    sudo_path = shutil.which("sudo")

    if sudo_path is None:
        print("sudo is not installed or is not available in PATH.")
        return

    print(f"sudo executable: {sudo_path}")

    return_code, stdout, stderr = run_command([sudo_path, "-n", "-l"])

    if return_code == 0:
        print("Non-interactive sudo policy query succeeded:")
        print(stdout)
    else:
        print(
            "The local sudo policy could not be queried without interaction "
            "or sufficient authorization."
        )
        if stderr:
            print(f"Message: {stderr}")

    print("\nSecurity principles:")
    print("  * Grant only commands that are actually required.")
    print("  * Avoid unrestricted ALL privileges when narrower rules suffice.")
    print("  * Avoid sharing administrator passwords.")
    print("  * Audit privileged commands.")
    print("  * Protect configuration files such as /etc/sudoers.")
    print("  * Prefer least privilege and explicit administrative boundaries.")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def explain_authentication() -> None:
    section("11. Authentication and authorization")

    print("Authentication mechanisms establish identity.")
    print("Examples include:")
    print("  * passwords")
    print("  * SSH public keys")
    print("  * hardware-backed credentials")
    print("  * multi-factor authentication")
    print("  * centralized identity services")

    print("\nAuthorization mechanisms determine permitted actions.")
    print("Examples include:")
    print("  * Unix file permissions")
    print("  * groups")
    print("  * sudo policy")
    print("  * ACLs")
    print("  * application roles")
    print("  * mandatory access-control systems")

    print(
        "\nA successfully authenticated user is not automatically authorized "
        "to perform every operation."
    )


# ---------------------------------------------------------------------------
# ACL concepts
# ---------------------------------------------------------------------------

def demonstrate_acl_commands() -> None:
    section("12. ACLs")

    getfacl = shutil.which("getfacl")
    setfacl = shutil.which("setfacl")

    print(
        "Traditional owner/group/other permissions are compact but sometimes "
        "insufficient when different users need different access."
    )
    print(
        "POSIX ACLs can add named user/group entries and default directory "
        "ACLs while retaining the traditional mode-bit interface."
    )

    print(f"getfacl available: {yes_no(getfacl is not None)}")
    print(f"setfacl available: {yes_no(setfacl is not None)}")

    if getfacl:
        return_code, stdout, stderr = run_command([getfacl, "-p", __file__])
        if return_code == 0:
            print("\nACL information for this script:")
            print(stdout)
        elif stderr:
            print(f"ACL query failed: {stderr}")

    print(
        "\nImportant ACL detail: an ACL mask can limit the effective "
        "permissions of named users, named groups, and the owning group entry."
    )


# ---------------------------------------------------------------------------
# Safe account lifecycle examples
# ---------------------------------------------------------------------------

def explain_account_lifecycle() -> None:
    section("13. Account lifecycle")

    stages = [
        ("Provision", "Create an account with the minimum required identity and groups."),
        ("Configure", "Set home directory, shell, authentication method, and access."),
        ("Use", "Authenticate and operate within authorized permissions."),
        ("Audit", "Review login activity, groups, privileged access, and ownership."),
        ("Modify", "Adjust groups and privileges as responsibilities change."),
        ("Disable", "Prevent authentication when the account should no longer be used."),
        ("Retire", "Remove or archive account data according to organizational policy."),
    ]

    for stage, description in stages:
        print(f"{stage:10} -> {description}")

    print("\nTypical commands, shown for study rather than automatic execution:")
    print("  useradd / adduser")
    print("  usermod")
    print("  passwd")
    print("  userdel")
    print("  groupadd")
    print("  groupmod")
    print("  groupdel")
    print("  usermod -aG <group> <user>")
    print("  id <user>")
    print("  groups <user>")


# ---------------------------------------------------------------------------
# Safe command reference
# ---------------------------------------------------------------------------

def command_reference() -> None:
    section("14. Practical command reference")

    commands = {
        "id": "Display UID, GID, and group membership for an identity.",
        "whoami": "Display the effective username associated with the current identity.",
        "groups": "Display group membership.",
        "passwd": "Manage password authentication for an account.",
        "useradd": "Create a user account on systems providing this utility.",
        "usermod": "Modify account properties and group membership.",
        "userdel": "Remove an account.",
        "groupadd": "Create a group.",
        "groupmod": "Modify a group.",
        "groupdel": "Remove a group.",
        "chmod": "Change permission bits.",
        "chown": "Change file owner and, where authorized, group.",
        "chgrp": "Change file group ownership.",
        "umask": "Inspect or configure default permission masking.",
        "sudo": "Run a command under a permitted privileged identity.",
        "getfacl": "Inspect POSIX ACLs when available.",
        "setfacl": "Modify POSIX ACLs when available.",
        "ls -l": "Display ownership and symbolic permissions.",
    }

    for command, purpose in commands.items():
        print(f"{command:16} {purpose}")


# ---------------------------------------------------------------------------
# Security mistakes
# ---------------------------------------------------------------------------

def security_mistakes() -> None:
    section("15. Common mistakes and security risks")

    mistakes = [
        (
            "777 everywhere",
            "Gives unnecessary write/execute access and can allow tampering."
        ),
        (
            "Shared administrator accounts",
            "Reduce accountability because actions cannot be reliably attributed."
        ),
        (
            "Excessive sudo access",
            "Turns a narrow operational need into broad system authority."
        ),
        (
            "Unnecessary service privileges",
            "A compromised service can inherit excessive authority."
        ),
        (
            "Wrong group membership",
            "A user may gain access to sensitive files or devices."
        ),
        (
            "Secrets in world-readable files",
            "Credentials can be exposed to unrelated local users."
        ),
        (
            "Confusing authentication with authorization",
            "Being able to log in does not imply permission for every resource."
        ),
        (
            "Ignoring directory permissions",
            "File-level permissions alone do not guarantee path accessibility."
        ),
        (
            "Relying only on numeric chmod values",
            "Makes it easier to overlook special bits, ACLs, or ownership."
        ),
    ]

    for problem, explanation in mistakes:
        print(f"{problem}: {explanation}")


# ---------------------------------------------------------------------------
# Performance and design
# ---------------------------------------------------------------------------

def performance_and_design() -> None:
    section("16. Performance and system-design considerations")

    print(
        "Permission checks are performed frequently by the operating system. "
        "Keeping identity and permission information compact allows efficient "
        "authorization decisions."
    )

    print("\nDesign principles:")
    print("  * Keep service identities separate.")
    print("  * Prefer groups over manually duplicated access rules.")
    print("  * Minimize the number of privileged operations.")
    print("  * Separate authentication infrastructure from application authorization.")
    print("  * Cache identity information carefully when centralized directories are used.")
    print("  * Account for stale group membership in long-running processes.")
    print("  * Log security-sensitive administrative changes.")

    print("\nTrade-off:")
    print(
        "Very simple permission models are easy to reason about but can become "
        "inflexible. ACLs and centralized identity systems provide finer control "
        "but increase operational complexity."
    )


# ---------------------------------------------------------------------------
# Testing permission decisions
# ---------------------------------------------------------------------------

def run_permission_tests() -> None:
    section("17. Automated permission tests")

    owner = Identity(1000, 100)
    group_member = Identity(1001, 100)
    supplementary_member = Identity(1002, 200, frozenset({100}))
    outsider = Identity(1003, 300)

    obj = PermissionObject(1000, 100, 0o640)

    test_cases = [
        ("owner can read", owner, "r", True),
        ("owner can write", owner, "w", True),
        ("owner cannot execute", owner, "x", False),
        ("group member can read", group_member, "r", True),
        ("group member cannot write", group_member, "w", False),
        ("supplementary member can read", supplementary_member, "r", True),
        ("outsider cannot read", outsider, "r", False),
    ]

    passed = 0

    for name, identity, requested, expected in test_cases:
        actual = has_permission(identity, obj, requested)
        status = "PASS" if actual == expected else "FAIL"
        passed += actual == expected
        print(f"{status:4} {name}")

    print(f"\n{passed}/{len(test_cases)} permission tests passed.")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def edge_cases() -> None:
    section("18. Important edge cases")

    print("1. UID 0 normally represents the superuser identity.")
    print("2. A process can have real and effective user/group identities.")
    print("3. Supplementary groups can affect authorization.")
    print("4. File permissions and ACLs can interact.")
    print("5. Symlinks have special metadata behavior.")
    print("6. Directory x permission controls traversal.")
    print("7. A file may be readable but inaccessible through its path.")
    print("8. Root privileges are subject to modern kernel security mechanisms.")
    print("9. Containers can change the apparent namespace and identity model.")
    print("10. Network filesystems can impose different authorization semantics.")
    print("11. Mandatory access-control systems can add restrictions beyond mode bits.")
    print("12. Capabilities can split selected privileged operations instead of using")
    print("    a single all-powerful superuser identity.")


# ---------------------------------------------------------------------------
# Capabilities and advanced Linux security
# ---------------------------------------------------------------------------

def advanced_privilege_models() -> None:
    section("19. Advanced privilege concepts")

    print("Linux capabilities divide traditional superuser powers into capabilities.")
    print("Examples include:")
    print("  CAP_CHOWN   -> changing file ownership in permitted situations")
    print("  CAP_NET_BIND_SERVICE -> binding to traditionally privileged ports")
    print("  CAP_NET_ADMIN -> selected network administration operations")
    print("  CAP_DAC_OVERRIDE -> bypass selected discretionary access checks")
    print("  CAP_SETUID -> manipulating user identities in permitted ways")

    print("\nThis enables a design such as:")
    print("  service needs one privileged operation")
    print("  -> grant the narrow capability")
    print("  -> avoid granting broad administrator authority")

    print("\nOther advanced controls include:")
    print("  * Linux namespaces")
    print("  * seccomp")
    print("  * SELinux")
    print("  * AppArmor")
    print("  * systemd sandboxing")
    print("  * container user namespaces")


# ---------------------------------------------------------------------------
# Practical read-only system demonstration
# ---------------------------------------------------------------------------

def read_only_system_demo() -> None:
    section("20. Read-only system demonstration")

    commands = [
        ["id"],
        ["whoami"],
        ["groups"],
        ["ls", "-ld", str(Path.cwd())],
    ]

    for command in commands:
        print(f"\n$ {' '.join(command)}")
        return_code, stdout, stderr = run_command(command)
        if stdout:
            print(stdout)
        if stderr:
            print(f"stderr: {stderr}")
        print(f"exit code: {return_code}")


# ---------------------------------------------------------------------------
# Mini security audit
# ---------------------------------------------------------------------------

def audit_path(path: Path) -> None:
    section(f"21. Mini permission audit: {path}")

    if not path.exists():
        print("Path does not exist.")
        return

    metadata = path.stat()

    warnings: list[str] = []

    if metadata.st_mode & stat.S_IWOTH:
        warnings.append("Other users have write permission.")

    if metadata.st_mode & stat.S_IWGRP:
        warnings.append("The owning group has write permission.")

    if metadata.st_mode & stat.S_IXOTH:
        warnings.append("Other users have execute/traversal permission.")

    if metadata.st_mode & stat.S_ISUID:
        warnings.append("setuid bit is enabled.")

    if metadata.st_mode & stat.S_ISGID:
        warnings.append("setgid bit is enabled.")

    print(f"Permissions: {stat.filemode(metadata.st_mode)}")
    print(f"Owner UID: {metadata.st_uid}")
    print(f"Group GID: {metadata.st_gid}")

    if warnings:
        print("\nPotentially important findings:")
        for warning in warnings:
            print(f"  * {warning}")
    else:
        print("\nNo selected high-level findings were detected.")

    print(
        "\nThis is an educational audit, not a complete security scanner. "
        "Real audits must also consider ACLs, capabilities, MAC policies, "
        "mount options, namespaces, application authorization, and context."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Comprehensive educational demonstration of Linux users, groups, permissions, and privilege management."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(__file__),
        help="Path to inspect and audit. Defaults to this script.",
    )
    parser.add_argument(
        "--system-demo",
        action="store_true",
        help="Run read-only operating-system command demonstrations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    demonstrate_current_identity()
    explain_passwd_database()
    explain_user_classes()
    demonstrate_groups()
    explain_permission_bits()
    demonstrate_mode_conversion()
    inspect_file(args.path)
    demonstrate_permission_evaluator()
    explain_directory_permissions()
    explain_special_bits()
    demonstrate_umask()
    demonstrate_sudo()
    explain_authentication()
    demonstrate_acl_commands()
    explain_account_lifecycle()
    command_reference()
    security_mistakes()
    performance_and_design()
    run_permission_tests()
    edge_cases()
    advanced_privilege_models()

    if args.system_demo:
        read_only_system_demo()

    audit_path(args.path)

    section("Study checkpoint")
    print("You should now be able to distinguish:")
    print("  identity -> UID/GID and groups")
    print("  authentication -> proving identity")
    print("  authorization -> deciding permitted actions")
    print("  ownership -> user/group associated with a resource")
    print("  permissions -> discretionary access bits")
    print("  sudo -> controlled command-level privilege elevation")
    print("  ACL -> finer-grained discretionary permissions")
    print("  capabilities -> selected pieces of privileged authority")
    print("  MAC -> policy-based restrictions beyond ordinary DAC permissions")
    print("\nNo account, password, group, ownership, or permission-changing")
    print("operation is performed automatically by this study program.")


if __name__ == "__main__":
    main()
