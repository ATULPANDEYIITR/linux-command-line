"""
Linux Installation and Environment
==================================

A standalone study script covering Linux installation and environment
management from absolute beginner concepts through advanced administration.

Topics covered:
- Linux fundamentals and distributions
- Virtual machines and hypervisors
- Linux installation planning
- Disk partitions and filesystems
- Cloud Linux instances
- Terminal and shell environments
- Filesystem navigation
- Users, groups, permissions, and ownership
- Environment variables and PATH
- Package management
- Processes, services, systemd, logs, and resource inspection
- Networking fundamentals
- SSH authentication and secure remote administration
- SSH configuration concepts
- File transfer and remote execution
- Cloud security and firewall concepts
- Automation patterns
- Troubleshooting methodology
- Production administration practices
- Performance and security considerations

The demonstrations are intentionally conservative. Commands that could modify
the operating system are printed for study rather than executed automatically.
Safe local Python demonstrations and read-only operating-system inspection
commands may be executed.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import platform
import shlex
import shutil
import socket
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


# ============================================================================
# General teaching utilities
# ============================================================================

def title(text: str) -> None:
    """Print a major section heading."""
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def subsection(text: str) -> None:
    """Print a smaller section heading."""
    print("\n" + "-" * 78)
    print(text)
    print("-" * 78)


def explain(text: str) -> None:
    """Print explanatory text with readable wrapping."""
    print(textwrap.fill(text, width=78))


def show_command(command: str, description: str = "") -> None:
    """Display a shell command without executing it."""
    print(f"\n$ {command}")
    if description:
        print(f"  {description}")


def show_code(code: str) -> None:
    """Display a small code or configuration example."""
    print(textwrap.dedent(code).strip())


def run_read_only_command(
    command: Sequence[str],
    *,
    timeout: float = 5.0,
) -> tuple[int, str, str]:
    """
    Execute a command considered safe for local inspection.

    The function does not invoke a shell. This avoids shell parsing and reduces
    the risk of accidental command injection.
    """
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
        return 1, "", str(exc)


def command_exists(command: str) -> bool:
    """Return True when an executable is available in PATH."""
    return shutil.which(command) is not None


# ============================================================================
# Linux fundamentals
# ============================================================================

def teach_linux_fundamentals() -> None:
    title("Linux fundamentals")

    explain(
        "Linux is an open-source kernel. A complete operating system built "
        "around the Linux kernel normally includes user-space programs, "
        "libraries, utilities, package management, a shell, and system "
        "services. Ubuntu, Debian, Fedora, Rocky Linux, AlmaLinux, Arch Linux, "
        "openSUSE, and many other distributions package these components in "
        "different ways."
    )

    subsection("Kernel versus distribution")

    concepts = {
        "Kernel": "Core software responsible for hardware, memory, processes, networking, and system calls.",
        "Distribution": "A complete operating-system ecosystem built around a Linux kernel.",
        "Shell": "A command interpreter used to interact with the operating system.",
        "Terminal emulator": "A graphical application that provides a terminal interface.",
        "Package manager": "Software that installs, updates, removes, and verifies packages.",
        "Service": "A background process that performs a persistent system function.",
        "Filesystem": "The structure and rules used to store and organize files.",
        "Daemon": "A background program that normally provides a service.",
        "Repository": "A trusted source containing packages and metadata.",
    }

    for name, meaning in concepts.items():
        print(f"{name:20} {meaning}")

    subsection("Common Linux distribution families")

    families = [
        ("Debian family", "Debian, Ubuntu, Linux Mint", "apt / dpkg"),
        ("Red Hat family", "Fedora, RHEL, Rocky Linux, AlmaLinux", "dnf / rpm"),
        ("Arch family", "Arch Linux, Manjaro", "pacman"),
        ("SUSE family", "openSUSE, SUSE Linux Enterprise", "zypper / rpm"),
    ]

    print(f"{'Family':20} {'Examples':38} {'Typical tools'}")
    print("-" * 78)
    for family, examples, tools in families:
        print(f"{family:20} {examples:38} {tools}")

    subsection("Linux architecture")

    show_code(
        """
        User applications
              |
        Shell / utilities
              |
        System libraries
              |
        System calls
              |
        Linux kernel
              |
        Hardware
        """
    )

    explain(
        "Applications normally do not access hardware directly. They request "
        "services from the kernel through system calls. The kernel manages "
        "resources such as CPU time, memory, files, devices, processes, and "
        "networking."
    )


# ============================================================================
# Virtual machines
# ============================================================================

@dataclass
class VirtualMachinePlan:
    """Describe a basic Linux virtual-machine configuration."""

    name: str
    cpu_cores: int
    memory_gb: int
    disk_gb: int
    network_mode: str

    def validate(self) -> list[str]:
        """Return configuration problems without modifying a VM."""
        problems: list[str] = []

        if self.cpu_cores < 1:
            problems.append("CPU core count must be at least 1.")
        if self.memory_gb < 1:
            problems.append("Memory must be at least 1 GB.")
        if self.disk_gb < 8:
            problems.append("Disk allocation is too small for a practical general-purpose installation.")
        if self.network_mode not in {"NAT", "bridged", "host-only"}:
            problems.append("Network mode should be NAT, bridged, or host-only.")

        return problems


def teach_virtual_machines() -> None:
    title("Virtual machines")

    explain(
        "A virtual machine, or VM, is an isolated software-defined computer "
        "that runs a guest operating system on a physical host. A hypervisor "
        "allocates CPU, memory, storage, and virtual networking to the guest."
    )

    subsection("Type 1 and Type 2 hypervisors")

    print("Type 1: runs directly on hardware.")
    print("Examples: VMware ESXi, Microsoft Hyper-V Server, Xen.")
    print()
    print("Type 2: runs as an application on a host operating system.")
    print("Examples: VirtualBox, VMware Workstation, Parallels Desktop.")

    subsection("VM resource planning")

    plan = VirtualMachinePlan(
        name="linux-lab",
        cpu_cores=2,
        memory_gb=4,
        disk_gb=30,
        network_mode="NAT",
    )

    print(f"VM name:       {plan.name}")
    print(f"CPU cores:     {plan.cpu_cores}")
    print(f"Memory:        {plan.memory_gb} GB")
    print(f"Disk:          {plan.disk_gb} GB")
    print(f"Network mode:  {plan.network_mode}")

    problems = plan.validate()
    print("Validation:", "valid" if not problems else problems)

    subsection("Virtual networking")

    network_modes = {
        "NAT": "The VM can normally access external networks through the host. Incoming access usually requires port forwarding.",
        "Bridged": "The VM appears as another machine on the physical network and can receive an address from that network.",
        "Host-only": "The VM communicates with the host and other host-only guests without requiring external network access.",
    }

    for mode, description in network_modes.items():
        print(f"{mode:10} {description}")

    subsection("Typical VM installation workflow")

    workflow = [
        "Download a Linux ISO from a trusted distribution source.",
        "Verify the ISO checksum when verification information is available.",
        "Create a virtual machine with appropriate CPU, memory, disk, and networking.",
        "Attach the ISO as a virtual optical disk.",
        "Boot the VM from the ISO.",
        "Select language, keyboard, timezone, and installation options.",
        "Partition the virtual disk.",
        "Create a normal administrative user.",
        "Install the bootloader and operating system.",
        "Reboot and detach the installation ISO.",
        "Update the system.",
        "Install required packages and development tools.",
        "Configure networking and SSH only when needed.",
    ]

    for index, step in enumerate(workflow, start=1):
        print(f"{index:2}. {step}")

    subsection("Important VM trade-offs")

    explain(
        "VMs provide isolation, snapshots, repeatability, and convenient "
        "experimentation, but they consume host resources and add a "
        "virtualization layer. Snapshots are useful for short-term rollback, "
        "but they are not a substitute for independent backups."
    )


# ============================================================================
# Linux installation
# ============================================================================

def teach_linux_installation() -> None:
    title("Linux installation")

    subsection("Installation planning")

    planning_questions = [
        "Which distribution and release is appropriate?",
        "Is the installation physical, virtual, or cloud-based?",
        "How much CPU, RAM, storage, and network capacity is required?",
        "Will the machine use a desktop environment or a server-only installation?",
        "Which filesystem and partition layout are appropriate?",
        "Is disk encryption required?",
        "Will the machine need remote SSH administration?",
        "What recovery and backup mechanism will be available?",
    ]

    for question in planning_questions:
        print(f"- {question}")

    subsection("Firmware and boot process")

    explain(
        "Modern systems commonly use UEFI firmware. The firmware initializes "
        "hardware and locates an operating-system bootloader. A Linux boot "
        "loader such as GRUB can then load the kernel and initial RAM filesystem."
    )

    show_code(
        """
        Power on
          |
        UEFI / firmware
          |
        Bootloader
          |
        Linux kernel
          |
        initramfs
          |
        systemd and system services
          |
        Login / graphical environment / application services
        """
    )

    subsection("Partitioning concepts")

    partitions = {
        "EFI System Partition": "Stores UEFI boot files. Usually formatted as FAT32.",
        "/": "Root filesystem containing the main Linux directory hierarchy.",
        "/home": "Optional separate filesystem for user data.",
        "swap": "Disk-backed memory mechanism with performance characteristics different from RAM.",
        "/boot": "Optional separate location for boot-related files on some installations.",
    }

    for partition, description in partitions.items():
        print(f"{partition:24} {description}")

    explain(
        "A simple installation can use a root filesystem plus an EFI System "
        "Partition and swap. More specialized servers may use separate "
        "filesystems or logical volumes to control growth and failure domains."
    )

    subsection("Filesystem examples")

    filesystems = [
        ("ext4", "General-purpose Linux filesystem with broad compatibility."),
        ("XFS", "High-performance filesystem frequently used on enterprise systems."),
        ("Btrfs", "Copy-on-write filesystem with snapshots and advanced volume features."),
        ("FAT32", "Common filesystem for UEFI boot partitions."),
    ]

    for filesystem, description in filesystems:
        print(f"{filesystem:8} {description}")

    subsection("Safe installation commands to study")

    show_command(
        "lsblk",
        "Lists block devices and helps identify disks and partitions.",
    )
    show_command(
        "blkid",
        "Displays filesystem identifiers and UUIDs.",
    )
    show_command(
        "df -h",
        "Shows mounted filesystem capacity in human-readable units.",
    )

    explain(
        "Disk-partitioning commands such as fdisk, parted, mkfs, and wipefs can "
        "destroy data. They should never be executed against an uncertain disk."
    )


# ============================================================================
# Terminal and shell
# ============================================================================

def teach_terminal() -> None:
    title("Terminal environments and shell fundamentals")

    explain(
        "A terminal is an interface through which a user interacts with a "
        "shell. Bash is a widely used shell, while zsh, fish, and other shells "
        "provide different features and syntax."
    )

    subsection("Essential navigation")

    commands = [
        ("pwd", "Print the current working directory."),
        ("ls", "List directory contents."),
        ("ls -la", "Show hidden files and detailed metadata."),
        ("cd /path", "Change directory."),
        ("cd ..", "Move to the parent directory."),
        ("cd ~", "Move to the current user's home directory."),
        ("mkdir project", "Create a directory."),
        ("touch file.txt", "Create an empty file or update its timestamp."),
    ]

    for command, purpose in commands:
        show_command(command, purpose)

    subsection("Reading and manipulating files")

    file_commands = [
        ("cat file.txt", "Print a file."),
        ("less file.txt", "Read a file interactively."),
        ("head -n 20 file.txt", "Read the first 20 lines."),
        ("tail -n 20 file.txt", "Read the last 20 lines."),
        ("grep 'error' application.log", "Search for matching text."),
        ("wc -l application.log", "Count lines."),
        ("cp source destination", "Copy a file or directory with appropriate options."),
        ("mv old new", "Move or rename."),
        ("rm file.txt", "Remove a file. Use with care."),
    ]

    for command, purpose in file_commands:
        show_command(command, purpose)

    subsection("Pipes and redirection")

    show_code(
        """
        command > output.txt
            # Redirect standard output and replace the destination.

        command >> output.txt
            # Append standard output.

        command 2> errors.txt
            # Redirect standard error.

        command1 | command2
            # Send standard output of command1 to command2.

        command1 | grep "failed" | wc -l
            # Search output and count matching lines.
        """
    )

    explain(
        "Unix-style pipelines are powerful because small programs can be "
        "combined into processing chains. They also introduce failure and "
        "quoting considerations, so scripts should check exit codes when "
        "correctness matters."
    )

    subsection("Shell quoting")

    show_code(
        """
        name="Linux server"
        echo "$name"
        echo '$name'

        # Double quotes normally allow variable expansion.
        # Single quotes normally preserve literal characters.
        """
    )

    subsection("Command discovery")

    show_command("command -v python3", "Find the executable selected by PATH.")
    show_command("type cd", "Determine whether a command is a builtin, alias, or executable.")
    show_command("man ls", "Read a command's manual page.")

    subsection("Exit status")

    explain(
        "Unix commands normally return an integer exit status. Zero conventionally "
        "means success, while a nonzero value indicates failure or another condition."
    )

    show_code(
        """
        mkdir example
        echo $?

        if mkdir example; then
            echo "Directory creation succeeded"
        else
            echo "Directory creation failed"
        fi
        """
    )


# ============================================================================
# Filesystem and permissions
# ============================================================================

def teach_filesystem_and_permissions() -> None:
    title("Linux filesystem, users, groups, and permissions")

    subsection("Filesystem hierarchy")

    hierarchy = {
        "/": "Root of the entire filesystem hierarchy.",
        "/etc": "System-wide configuration files.",
        "/home": "Normal users' home directories.",
        "/var": "Frequently changing data such as logs and caches.",
        "/tmp": "Temporary files.",
        "/usr": "Most user-space applications, libraries, and shared resources.",
        "/opt": "Optional third-party software.",
        "/dev": "Device interfaces.",
        "/proc": "Virtual kernel/process information filesystem.",
        "/sys": "Virtual filesystem exposing hardware and kernel information.",
        "/run": "Volatile runtime state.",
    }

    for path, description in hierarchy.items():
        print(f"{path:8} {description}")

    subsection("Ownership")

    explain(
        "Linux filesystem objects have an owning user and group. Permission "
        "bits can separately describe access for the owner, group, and others."
    )

    show_code(
        """
        -rwxr-xr--

        owner:   rwx
        group:   r-x
        others:  r--

        r = read
        w = write
        x = execute
        """
    )

    subsection("Octal permissions")

    permissions = {
        "0": "---",
        "1": "--x",
        "2": "-w-",
        "3": "-wx",
        "4": "r--",
        "5": "r-x",
        "6": "rw-",
        "7": "rwx",
    }

    for number, symbolic in permissions.items():
        print(f"{number} = {symbolic}")

    show_command("chmod 750 script.sh", "Owner gets rwx, group gets r-x, others get no permissions.")
    show_command("chown user:group file.txt", "Change ownership; normally requires appropriate privileges.")
    show_command("id", "Display the current user's UID, GID, and group memberships.")

    subsection("Special permission concepts")

    explain(
        "Setuid, setgid, and the sticky bit are special permission mechanisms. "
        "They have important security implications and should be applied only "
        "when their behavior is clearly understood."
    )

    show_command("ls -ld /tmp", "Inspect the sticky-bit behavior of the temporary directory.")
    show_command("chmod 1777 shared-directory", "Example of a sticky directory pattern; use only when appropriate.")

    subsection("Least privilege")

    explain(
        "The principle of least privilege means an account or process should "
        "receive only the permissions required to perform its task. Routine "
        "work should normally be performed as a normal user rather than as root."
    )

    show_command("sudo command", "Temporarily request elevated privileges for an authorized operation.")


# ============================================================================
# Environment variables
# ============================================================================

def teach_environment_variables() -> None:
    title("Environment variables and PATH")

    subsection("What is an environment variable?")

    explain(
        "An environment variable is a named value inherited by processes from "
        "their parent process. Programs use environment variables for settings "
        "such as PATH, HOME, LANG, EDITOR, and application-specific configuration."
    )

    important = ["HOME", "USER", "SHELL", "PATH", "PWD", "LANG"]

    for name in important:
        print(f"{name:8} = {os.environ.get(name, '<not defined>')}")

    subsection("PATH")

    explain(
        "PATH is a colon-separated list of directories. When a command is "
        "entered without a path, the shell searches these directories in order."
    )

    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    for index, entry in enumerate(path_entries, start=1):
        print(f"{index:2}. {entry}")

    subsection("Safe Python demonstration")

    temporary_environment = dict(os.environ)
    temporary_environment["LINUX_STUDY_MODE"] = "enabled"

    print(
        "A child process can receive an environment variable without changing "
        "the parent Python process:"
    )
    print("LINUX_STUDY_MODE =", temporary_environment["LINUX_STUDY_MODE"])

    subsection("Persistent environment configuration")

    show_command(
        "export APP_ENV=production",
        "Sets a variable for the current shell and processes launched from it.",
    )

    show_code(
        """
        # Common shell startup files:
        ~/.bashrc
        ~/.profile
        ~/.zshrc

        # A variable intended as an application secret should generally
        # not be committed to source control.
        """
    )

    explain(
        "Startup-file behavior differs between login shells, interactive "
        "non-login shells, graphical sessions, SSH sessions, and service "
        "managers. Environment configuration should therefore be tested in "
        "the same execution context used by the application."
    )


# ============================================================================
# Package management
# ============================================================================

def teach_package_management() -> None:
    title("Package management")

    explain(
        "Linux distributions use package managers to install software and "
        "resolve dependencies. A package usually contains compiled or "
        "interpreted software plus metadata describing dependencies, files, "
        "versions, and installation information."
    )

    subsection("Debian and Ubuntu")

    show_command("sudo apt update", "Refresh package metadata.")
    show_command("sudo apt upgrade", "Install available package upgrades.")
    show_command("sudo apt install nginx", "Install a package.")
    show_command("apt search nginx", "Search configured repositories.")
    show_command("apt show nginx", "Display package metadata.")

    subsection("Fedora, RHEL, Rocky Linux, and AlmaLinux")

    show_command("sudo dnf check-update", "Check package updates.")
    show_command("sudo dnf upgrade", "Install package updates.")
    show_command("sudo dnf install nginx", "Install a package.")
    show_command("dnf search nginx", "Search repositories.")

    subsection("Package lifecycle")

    show_code(
        """
        Repository metadata
              |
        Dependency resolution
              |
        Package download
              |
        Signature / integrity verification
              |
        Installation
              |
        Configuration
              |
        Service activation when required
        """
    )

    explain(
        "Package management is safer than downloading arbitrary binaries "
        "because repositories provide metadata, dependency handling, and "
        "distribution-integrated update mechanisms. Third-party repositories "
        "must still be evaluated for trust and maintenance quality."
    )


# ============================================================================
# Processes and services
# ============================================================================

def teach_processes_and_services() -> None:
    title("Processes, services, systemd, and logs")

    subsection("Processes")

    explain(
        "A process is a running instance of a program. It has an identifier "
        "called a PID and resources such as memory mappings, open files, "
        "credentials, and scheduling information."
    )

    show_command("ps aux", "List processes.")
    show_command("top", "Interactively inspect CPU and memory usage.")
    show_command("free -h", "Inspect memory and swap.")
    show_command("uptime", "Inspect uptime and load averages.")
    show_command("df -h", "Inspect filesystem capacity.")
    show_command("du -sh /var/log", "Estimate directory disk usage.")

    subsection("Signals")

    signals = {
        "SIGTERM": "Requests graceful termination.",
        "SIGKILL": "Forces termination and cannot be handled by the target process.",
        "SIGHUP": "Historically related to terminal hangup; many daemons use it to reload configuration.",
        "SIGINT": "Interactive interrupt, commonly generated by Ctrl+C.",
    }

    for signal, meaning in signals.items():
        print(f"{signal:8} {meaning}")

    show_command("kill -TERM PID", "Request graceful process termination.")
    show_command("kill -KILL PID", "Force termination only when safer approaches fail.")

    subsection("systemd")

    explain(
        "systemd is a common Linux init and service-management system. It "
        "starts services during boot, tracks service state, manages dependencies, "
        "and integrates with the journal."
    )

    show_command("systemctl status ssh", "Inspect SSH service state; service name varies by distribution.")
    show_command("sudo systemctl restart ssh", "Restart an SSH service.")
    show_command("sudo systemctl enable ssh", "Configure a service to start at boot.")
    show_command("sudo systemctl disable ssh", "Prevent automatic boot activation.")

    subsection("Logs")

    show_command("journalctl -u ssh", "View journal records associated with a service.")
    show_command("journalctl -b", "View logs from the current boot.")
    show_command("journalctl -p warning", "Filter journal messages by priority.")

    explain(
        "When diagnosing a service, inspect its status, recent logs, listening "
        "ports, configuration, dependencies, permissions, and resource usage "
        "before repeatedly restarting it."
    )


# ============================================================================
# Networking
# ============================================================================

@dataclass
class NetworkConcept:
    """A simple representation of an important networking concept."""

    name: str
    layer_or_role: str
    description: str


def teach_networking() -> None:
    title("Linux networking fundamentals")

    concepts = [
        NetworkConcept("MAC address", "Link layer", "Identifier associated with a network interface."),
        NetworkConcept("IP address", "Network layer", "Logical address used for IP communication."),
        NetworkConcept("Subnet", "Network layer", "Defines which addresses belong to a local network prefix."),
        NetworkConcept("Gateway", "Routing", "Router used to reach networks outside the local subnet."),
        NetworkConcept("DNS", "Application support", "Maps names such as example.com to IP addresses."),
        NetworkConcept("TCP", "Transport", "Connection-oriented transport with reliable ordered delivery."),
        NetworkConcept("UDP", "Transport", "Connectionless transport with lower protocol overhead."),
        NetworkConcept("Port", "Transport", "Logical endpoint number associated with network services."),
    ]

    for concept in concepts:
        print(f"{concept.name:18} {concept.layer_or_role:18} {concept.description}")

    subsection("Useful commands")

    commands = [
        ("ip addr", "Inspect network interfaces and IP addresses."),
        ("ip route", "Inspect the routing table."),
        ("ip link", "Inspect network interfaces and link state."),
        ("ss -tulpn", "Inspect listening TCP/UDP sockets where permitted."),
        ("ping HOST", "Test basic IP reachability; ICMP may be blocked."),
        ("dig example.com", "Query DNS records when dig is installed."),
        ("curl https://example.com", "Make an HTTP request."),
    ]

    for command, purpose in commands:
        show_command(command, purpose)

    subsection("Private IPv4 ranges")

    private_ranges = [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]

    for network in private_ranges:
        print(network)

    explain(
        "Private IPv4 addresses are commonly used inside local networks and "
        "cloud virtual networks. They are not globally routable on the public "
        "Internet."
    )

    subsection("Ports commonly encountered in administration")

    ports = {
        22: "SSH",
        53: "DNS",
        80: "HTTP",
        443: "HTTPS",
        5432: "PostgreSQL",
        3306: "MySQL / MariaDB",
    }

    for port, service in ports.items():
        print(f"{port:5} {service}")

    explain(
        "A port number alone does not prove which service is running. Always "
        "inspect the actual listener and configuration when troubleshooting."
    )


# ============================================================================
# SSH
# ============================================================================

@dataclass
class SSHConnection:
    """Represent the logical components of an SSH connection."""

    username: str
    hostname: str
    port: int = 22
    identity_file: str | None = None

    def command(self) -> list[str]:
        """Build an SSH argument list without invoking a shell."""
        arguments = ["ssh", "-p", str(self.port)]

        if self.identity_file:
            arguments.extend(["-i", self.identity_file])

        arguments.append(f"{self.username}@{self.hostname}")
        return arguments


def teach_ssh() -> None:
    title("SSH access and remote administration")

    explain(
        "SSH, or Secure Shell, provides encrypted remote access to systems. "
        "It is commonly used for interactive administration, command execution, "
        "secure file transfer, automation, and tunneling."
    )

    subsection("Connection anatomy")

    show_code(
        """
        Local computer
             |
             | TCP connection
             v
        Server:22
             |
        SSH server
             |
        Authentication
             |
        Encrypted session
             |
        Remote shell / command
        """
    )

    subsection("Basic SSH command")

    connection = SSHConnection(
        username="ubuntu",
        hostname="203.0.113.10",
        port=22,
        identity_file="~/.ssh/id_ed25519",
    )

    print("Example argument structure:")
    print(" ".join(shlex.quote(part) for part in connection.command()))

    explain(
        "The example uses a documentation-only IP address. Replace it with "
        "the actual address of a server you are authorized to administer."
    )

    subsection("Password versus public-key authentication")

    print("Password authentication:")
    print("- Client proves knowledge of a password.")
    print("- Convenient but vulnerable to password guessing and credential reuse.")
    print()
    print("Public-key authentication:")
    print("- Client holds a private key.")
    print("- Server stores the corresponding public key.")
    print("- The private key does not need to be copied to the server.")

    subsection("Creating an SSH key pair")

    show_command(
        "ssh-keygen -t ed25519 -C \"admin-key\"",
        "Generate an Ed25519 key pair on a trusted local machine.",
    )

    explain(
        "The private key must remain private. The public key can be placed in "
        "the authorized_keys file of an account on the remote server."
    )

    show_command(
        "ssh-copy-id user@server",
        "Install a public key when the server and local environment support this helper.",
    )

    subsection("SSH configuration")

    show_code(
        """
        Host production-server
            HostName 203.0.113.10
            User admin
            Port 22
            IdentityFile ~/.ssh/id_ed25519
        """
    )

    explain(
        "The SSH client configuration file can provide aliases and connection "
        "defaults. File permissions and key handling remain security-sensitive."
    )

    subsection("Remote commands")

    show_command(
        "ssh user@server 'uname -a'",
        "Run a read-only command remotely.",
    )

    show_command(
        "ssh user@server 'df -h'",
        "Inspect remote filesystem capacity.",
    )

    subsection("File transfer")

    show_command(
        "scp ./file.txt user@server:/tmp/",
        "Copy a file using SSH transport.",
    )

    show_command(
        "sftp user@server",
        "Start an interactive SSH-based file-transfer session.",
    )

    show_command(
        "rsync -avz ./project/ user@server:/srv/project/",
        "Synchronize files efficiently over SSH.",
    )

    subsection("SSH troubleshooting sequence")

    troubleshooting = [
        "Confirm the server address and DNS resolution.",
        "Confirm the server is reachable on the expected network path.",
        "Confirm TCP port 22 or the configured SSH port is reachable.",
        "Check the SSH server is running.",
        "Check the username.",
        "Check private-key path and permissions.",
        "Use verbose SSH diagnostics.",
        "Inspect server-side authentication logs.",
        "Check firewall and cloud security-group rules.",
        "Check account restrictions and authorized_keys configuration.",
    ]

    for index, step in enumerate(troubleshooting, start=1):
        print(f"{index:2}. {step}")

    show_command(
        "ssh -v user@server",
        "Enable verbose client diagnostics.",
    )

    show_command(
        "ssh -vvv user@server",
        "Enable very detailed SSH client diagnostics when necessary.",
    )


# ============================================================================
# Cloud Linux
# ============================================================================

@dataclass
class CloudInstancePlan:
    """Represent high-level cloud-instance planning choices."""

    provider: str
    image: str
    region: str
    vcpu: int
    memory_gb: int
    storage_gb: int
    public_ip: bool
    ssh_port: int = 22


def teach_cloud_linux() -> None:
    title("Cloud Linux instances")

    explain(
        "A cloud Linux instance is a virtual machine supplied by a cloud "
        "provider. The provider normally manages the physical infrastructure "
        "while the customer manages the guest operating system, applications, "
        "identity configuration, and selected network controls."
    )

    subsection("Common cloud components")

    components = {
        "Region": "Geographic area containing cloud infrastructure.",
        "Availability zone": "Isolated location within a region for resilience.",
        "Image": "Template used to create a machine.",
        "Instance type": "Defines compute resources such as CPU and memory.",
        "Virtual network": "Private logical network for cloud resources.",
        "Subnet": "Address range within a virtual network.",
        "Security group": "Stateful virtual firewall rules in many cloud platforms.",
        "Public IP": "Internet-routable address associated with an instance or interface.",
        "Block storage": "Persistent virtual disk service.",
        "IAM": "Identity and access management system.",
    }

    for component, description in components.items():
        print(f"{component:20} {description}")

    subsection("Example instance plan")

    plan = CloudInstancePlan(
        provider="Example Cloud",
        image="Ubuntu LTS",
        region="example-region-1",
        vcpu=2,
        memory_gb=4,
        storage_gb=40,
        public_ip=True,
    )

    for field_name, value in vars(plan).items():
        print(f"{field_name:15} {value}")

    subsection("Cloud provisioning sequence")

    steps = [
        "Choose a region and availability design.",
        "Choose a trusted Linux image.",
        "Choose instance resources.",
        "Create or select a virtual network and subnet.",
        "Configure security-group or firewall rules.",
        "Create or select an SSH key pair.",
        "Launch the instance.",
        "Discover its private and public addresses.",
        "Connect through SSH.",
        "Update the operating system.",
        "Create a normal administrative account where appropriate.",
        "Install and configure required software.",
        "Configure monitoring, backups, and logging.",
    ]

    for step in steps:
        print(f"- {step}")

    subsection("Cloud firewall principle")

    explain(
        "Expose only the ports required by the service. For a basic web server, "
        "TCP 80 and 443 may be required. SSH should be restricted to trusted "
        "sources whenever practical rather than exposed broadly."
    )

    show_code(
        """
        Example conceptual policy:

        Inbound:
            TCP 22   -> trusted administration network only
            TCP 80   -> public, if HTTP is required
            TCP 443  -> public, if HTTPS is required

        Default:
            deny unnecessary inbound traffic
        """
    )

    explain(
        "Cloud firewall rules and the operating system firewall are separate "
        "control layers. Both must allow traffic when both are configured."
    )


# ============================================================================
# Security
# ============================================================================

def teach_security() -> None:
    title("Linux security and secure administration")

    subsection("Core security principles")

    principles = [
        "Use least privilege.",
        "Keep the operating system and packages patched.",
        "Prefer SSH keys over reusable passwords where practical.",
        "Protect private keys with appropriate filesystem permissions and passphrases.",
        "Do not expose unnecessary network services.",
        "Use firewalls as a network access-control layer.",
        "Separate administrative and application accounts.",
        "Do not store secrets in source repositories.",
        "Monitor authentication and service logs.",
        "Use backups that are independent from the primary machine.",
        "Test recovery procedures.",
        "Treat third-party packages and repositories as trust decisions.",
    ]

    for principle in principles:
        print(f"- {principle}")

    subsection("SSH hardening concepts")

    hardening = [
        "Use key-based authentication.",
        "Disable direct root SSH login when appropriate.",
        "Disable password authentication after confirming key access works.",
        "Restrict SSH exposure using network controls where possible.",
        "Use strong private-key protection.",
        "Review authorized_keys periodically.",
        "Keep the SSH server patched.",
        "Monitor failed and successful authentication attempts.",
    ]

    for item in hardening:
        print(f"- {item}")

    subsection("Example SSH server settings")

    show_code(
        """
        # /etc/ssh/sshd_config
        #
        # These are examples of security-relevant settings.
        # Test configuration and maintain a recovery path before changing them.

        PermitRootLogin no
        PasswordAuthentication no
        PubkeyAuthentication yes
        """
    )

    explain(
        "Never disable a login method before verifying that another working "
        "administrative path exists. A configuration mistake can lock an "
        "administrator out of a remote server."
    )

    subsection("Secret handling")

    show_code(
        """
        BAD:
        DATABASE_PASSWORD="real-password"
        git add application.py

        BETTER:
        DATABASE_PASSWORD is injected through a protected deployment mechanism
        and read by the application from its runtime environment.
        """
    )

    explain(
        "Environment variables are useful for configuration, but they are not "
        "automatically secret. Processes, debugging tools, service managers, "
        "logs, or crash reports can expose environment values depending on the "
        "system. Dedicated secret-management systems may be more appropriate "
        "for sensitive production credentials."
    )


# ============================================================================
# Automation
# ============================================================================

def teach_automation() -> None:
    title("Automation and remote administration")

    explain(
        "Manual administration does not scale well across many machines. "
        "Automation makes configuration repeatable and reduces accidental "
        "differences between servers."
    )

    subsection("Shell scripting basics")

    show_code(
        """
        #!/usr/bin/env bash
        set -euo pipefail

        APP_DIR="/srv/example-app"

        if [[ ! -d "$APP_DIR" ]]; then
            echo "Application directory is missing"
            exit 1
        fi

        echo "Application directory exists"
        """
    )

    explain(
        "set -euo pipefail is a common defensive shell pattern. It is useful "
        "but not a complete correctness guarantee. Commands whose nonzero "
        "status is intentionally expected need explicit handling."
    )

    subsection("Idempotence")

    explain(
        "An operation is idempotent when applying it repeatedly produces the "
        "same desired state after the first successful application. Idempotence "
        "is an important property in configuration automation."
    )

    show_code(
        """
        # Non-idempotent idea:
        echo "setting" >> /etc/example.conf

        # Idempotent goal:
        ensure /etc/example.conf contains exactly one required configuration
        entry, regardless of how many times the automation runs.
        """
    )

    subsection("Automation layers")

    layers = [
        "Shell scripts for small local tasks.",
        "SSH for remote execution and transport.",
        "Configuration-management systems for repeatable server state.",
        "Infrastructure-as-code for reproducible infrastructure.",
        "CI/CD systems for controlled software delivery.",
        "Monitoring and alerting for operational feedback.",
    ]

    for layer in layers:
        print(f"- {layer}")

    subsection("Python and SSH safety")

    explain(
        "When Python automation invokes operating-system commands, prefer "
        "subprocess argument lists instead of shell=True when shell syntax is "
        "not required. Validate externally supplied hostnames, filenames, and "
        "arguments before using them."
    )

    show_code(
        """
        # Safer argument-list pattern:
        subprocess.run(
            ["ssh", "user@example.com", "uname", "-a"],
            check=True,
        )

        # Avoid constructing an untrusted command string and passing it to
        # a shell without careful validation.
        """)


# ============================================================================
# Performance
# ============================================================================

def teach_performance() -> None:
    title("Performance and capacity considerations")

    subsection("Four basic resource categories")

    resources = {
        "CPU": "Compute capacity and scheduling.",
        "Memory": "Working data and executable mappings.",
        "Storage": "Persistent data and filesystem capacity.",
        "Network": "Data transfer capacity and latency.",
    }

    for resource, meaning in resources.items():
        print(f"{resource:10} {meaning}")

    subsection("Useful measurements")

    show_command("uptime", "Load averages and system uptime.")
    show_command("top", "Interactive process-level resource view.")
    show_command("free -h", "RAM and swap usage.")
    show_command("df -h", "Filesystem capacity.")
    show_command("df -i", "Filesystem inode usage.")
    show_command("iostat", "Storage and CPU statistics when sysstat is installed.")
    show_command("vmstat", "Virtual-memory and system activity statistics.")
    show_command("ss -s", "Network socket summary.")

    explain(
        "Capacity problems should be diagnosed using measurements rather than "
        "assumptions. High load does not necessarily mean CPU saturation. "
        "Memory pressure, blocked I/O, and excessive process activity can also "
        "contribute to load."
    )

    subsection("Disk-space versus inode exhaustion")

    explain(
        "A filesystem can have free bytes while running out of inodes. This "
        "can happen when an application creates enormous numbers of small files."
    )

    show_command("df -h", "Check byte capacity.")
    show_command("df -i", "Check inode capacity.")

    subsection("Log growth")

    explain(
        "Logs can consume significant storage. Production systems need an "
        "appropriate retention and rotation strategy. Deleting active log "
        "files blindly can also produce confusing behavior because processes "
        "may continue holding open file descriptors."
    )


# ============================================================================
# Debugging
# ============================================================================

def teach_debugging() -> None:
    title("Linux troubleshooting methodology")

    explain(
        "Effective troubleshooting starts with a precise problem statement. "
        "Instead of changing many settings at once, collect evidence, form a "
        "hypothesis, test it, and record the result."
    )

    subsection("Layered troubleshooting model")

    layers = [
        ("Physical / virtualization", "Is the machine or VM actually running?"),
        ("Boot", "Did firmware, bootloader, kernel, and init complete?"),
        ("Network", "Does the interface have an address and route?"),
        ("Transport", "Is the required TCP/UDP port reachable?"),
        ("Service", "Is the service running and listening?"),
        ("Application", "Is the application configuration correct?"),
        ("Authentication", "Does the account have valid credentials and permissions?"),
        ("Data", "Is required storage available and healthy?"),
    ]

    for layer, question in layers:
        print(f"{layer:24} {question}")

    subsection("SSH failure example")

    scenario = {
        "Symptom": "ssh user@server fails",
        "Question 1": "Does DNS resolve the server name?",
        "Question 2": "Does the server have network connectivity?",
        "Question 3": "Is the SSH port reachable?",
        "Question 4": "Is sshd running?",
        "Question 5": "Is authentication succeeding?",
        "Question 6": "Is the account authorized?",
    }

    for key, value in scenario.items():
        print(f"{key:12} {value}")

    subsection("Useful diagnostics")

    show_command("getent hosts server.example.com", "Check name resolution through system name-service configuration.")
    show_command("ip route", "Inspect local routing.")
    show_command("ss -ltnp", "Inspect local TCP listeners where permitted.")
    show_command("ssh -v user@server", "Inspect SSH client negotiation and authentication.")
    show_command("journalctl -u ssh --since '10 minutes ago'", "Inspect recent SSH service logs.")

    subsection("Configuration validation")

    explain(
        "Many production tools provide syntax-validation commands. Validate "
        "configuration before restarting a service. This reduces the risk of "
        "turning a configuration mistake into an outage."
    )


# ============================================================================
# Local environment inspection
# ============================================================================

def inspect_local_environment() -> None:
    title("Safe local Linux environment inspection")

    print("Python version:", sys.version.split()[0])
    print("Platform:", platform.platform())
    print("Kernel:", platform.release())
    print("Architecture:", platform.machine())
    print("Hostname:", socket.gethostname())
    print("Current user:", getpass.getuser())
    print("Home directory:", Path.home())
    print("Current directory:", Path.cwd())

    subsection("Important executables")

    for executable in ["bash", "sh", "ssh", "scp", "sftp", "python3", "curl", "git"]:
        location = shutil.which(executable)
        print(f"{executable:10} {location or 'not found'}")

    subsection("Filesystem capacity")

    try:
        usage = shutil.disk_usage(Path.cwd())
        gib = 1024**3
        print(f"Total:     {usage.total / gib:.2f} GiB")
        print(f"Used:      {usage.used / gib:.2f} GiB")
        print(f"Free:      {usage.free / gib:.2f} GiB")
    except OSError as exc:
        print("Could not inspect disk usage:", exc)

    subsection("Selected environment variables")

    for name in ["HOME", "USER", "SHELL", "LANG", "PATH"]:
        print(f"{name:8} = {os.environ.get(name, '<not defined>')}")


# ============================================================================
# Security-oriented Python examples
# ============================================================================

def demonstrate_secure_python_patterns() -> None:
    title("Python implementation patterns for Linux administration")

    subsection("Avoid shell interpretation when possible")

    command = ["python3", "--version"]
    print("Argument list:", command)

    if command_exists("python3"):
        return_code, stdout, stderr = run_read_only_command(command)
        print("Exit code:", return_code)
        print("Output:", stdout or stderr or "<no output>")
    else:
        print("python3 executable was not found.")

    subsection("Path handling")

    user_supplied_name = "../notes.txt"
    base_directory = Path("/srv/application").resolve()

    candidate = (base_directory / user_supplied_name).resolve()

    print("Base directory:", base_directory)
    print("Candidate path:", candidate)

    try:
        candidate.relative_to(base_directory)
        print("Candidate remains inside the permitted directory.")
    except ValueError:
        print("Candidate escapes the permitted directory and should be rejected.")

    explain(
        "The example demonstrates a basic path-containment check. Real "
        "applications also need to consider symbolic links, filesystem races, "
        "permissions, mount points, and the exact trust model."
    )

    subsection("Hashing for integrity checks")

    data = b"Linux installation study material"
    digest = hashlib.sha256(data).hexdigest()

    print("SHA-256:", digest)

    explain(
        "Cryptographic hashes can detect accidental or malicious modification "
        "when the expected digest comes from a trusted source. A hash by itself "
        "does not establish authenticity unless the expected value is trusted."
    )


# ============================================================================
# Production administration
# ============================================================================

def teach_production_practices() -> None:
    title("Production Linux administration")

    subsection("Operational baseline")

    baseline = [
        "Document the operating system and release.",
        "Record installed software and important configuration.",
        "Use centralized identity where appropriate.",
        "Apply security updates using a controlled process.",
        "Restrict administrative access.",
        "Configure host and network firewalls.",
        "Collect logs and monitor important services.",
        "Monitor CPU, memory, storage, and network resources.",
        "Maintain tested backups.",
        "Document recovery procedures.",
        "Use configuration management for repeatable state.",
        "Use change control for important production modifications.",
    ]

    for item in baseline:
        print(f"- {item}")

    subsection("Backups")

    explain(
        "A backup is useful only if it can be restored. Backup strategy should "
        "consider recovery-point objectives, recovery-time objectives, retention, "
        "encryption, access control, geographic independence, and restore testing."
    )

    subsection("Availability")

    explain(
        "High availability is not achieved merely by adding another server. "
        "Applications, databases, storage, DNS, networking, deployment "
        "processes, and operational procedures can all become failure points."
    )

    subsection("Configuration management")

    explain(
        "Important server configuration should be reproducible. Manual changes "
        "that exist only on a machine create configuration drift and make future "
        "recovery difficult."
    )

    subsection("Production change sequence")

    sequence = [
        "Understand the requested change.",
        "Identify affected services and dependencies.",
        "Back up or establish rollback capability.",
        "Validate the configuration.",
        "Apply the smallest controlled change.",
        "Check service health.",
        "Check logs and key metrics.",
        "Verify application behavior.",
        "Document the change and outcome.",
    ]

    for index, step in enumerate(sequence, start=1):
        print(f"{index:2}. {step}")


# ============================================================================
# Comparisons
# ============================================================================

def teach_comparisons() -> None:
    title("Important comparisons")

    comparisons = [
        ("VM", "Strong guest isolation and repeatability", "Consumes dedicated virtual resources"),
        ("Cloud instance", "Rapid provisioning and provider infrastructure", "Ongoing provider and network dependencies"),
        ("SSH password", "Simple initial access", "More exposed to password attacks and credential reuse"),
        ("SSH key", "Strong authentication and automation support", "Private-key protection is critical"),
        ("NAT networking", "Simple outbound connectivity", "Inbound access often needs port forwarding"),
        ("Bridged networking", "Guest behaves like another LAN device", "Greater network exposure"),
        ("ext4", "Mature and broadly supported", "Fewer advanced snapshot features than Btrfs"),
        ("Btrfs", "Snapshots and copy-on-write capabilities", "Requires understanding of its feature set and operational model"),
        ("Manual administration", "Simple for one-off changes", "Does not scale reliably"),
        ("Automation", "Repeatable and scalable", "Requires design, testing, and careful secret handling"),
    ]

    print(f"{'Approach':24} {'Strength':32} {'Trade-off'}")
    print("-" * 78)
    for approach, strength, tradeoff in comparisons:
        print(f"{approach:24} {strength:32} {tradeoff}")


# ============================================================================
# Practical lab simulation
# ============================================================================

def run_practical_lab() -> None:
    title("Practical Linux administration lab")

    explain(
        "This lab is a planning simulation. It does not create a VM, change "
        "partitions, alter firewall rules, or connect to a remote machine."
    )

    subsection("Lab objective")

    print(
        "Build a Linux VM or cloud instance, connect through SSH, install a "
        "small application, inspect its service, and troubleshoot deliberately."
    )

    subsection("Stage A: machine creation")

    show_code(
        """
        VM:
            CPU:       2 cores
            Memory:    4 GB
            Storage:   30+ GB
            Network:   NAT for a private laboratory

        Cloud:
            CPU:       2 vCPU
            Memory:    2-4 GB
            Storage:   20-40 GB
            Network:   private subnet + restricted administration access
        """
    )

    subsection("Stage B: first login")

    show_command("whoami", "Confirm the logged-in account.")
    show_command("hostname", "Confirm the machine identity.")
    show_command("pwd", "Confirm the current directory.")
    show_command("uname -a", "Inspect kernel and architecture information.")
    show_command("ip addr", "Inspect network interfaces.")

    subsection("Stage C: update")

    show_command("sudo apt update", "Debian/Ubuntu example.")
    show_command("sudo apt upgrade", "Debian/Ubuntu example.")

    subsection("Stage D: SSH")

    show_command("ssh-keygen -t ed25519", "Generate a key pair on the trusted administration machine.")
    show_command("ssh user@SERVER_IP", "Connect to the authorized server.")

    subsection("Stage E: service inspection")

    show_command("systemctl status ssh", "Inspect SSH service.")
    show_command("ss -ltnp", "Inspect TCP listeners.")
    show_command("journalctl -u ssh -n 50", "Inspect recent SSH service logs.")

    subsection("Stage F: resource inspection")

    show_command("free -h", "Inspect memory.")
    show_command("df -h", "Inspect filesystem capacity.")
    show_command("uptime", "Inspect load and uptime.")
    show_command("top", "Inspect processes interactively.")

    subsection("Stage G: deliberate troubleshooting")

    explain(
        "A useful exercise is to observe a known-good service, then introduce "
        "one controlled configuration change in a disposable laboratory "
        "environment. Record the symptom, inspect logs, identify the failed "
        "layer, restore the configuration, and verify recovery."
    )


# ============================================================================
# Knowledge checks
# ============================================================================

def knowledge_check() -> None:
    title("Knowledge check")

    questions = [
        (
            "1. What is the difference between the Linux kernel and a distribution?",
            "The kernel provides core operating-system functionality; a distribution packages the kernel with user-space software and management tools."
        ),
        (
            "2. What does SSH provide?",
            "Encrypted remote communication, commonly including shell access, command execution, and file transfer."
        ),
        (
            "3. Why is an SSH private key sensitive?",
            "Anyone who obtains an usable private key may be able to authenticate as its owner where the corresponding public key is trusted."
        ),
        (
            "4. What does chmod 750 mean?",
            "Owner has rwx, group has r-x, and others have no permissions."
        ),
        (
            "5. What is PATH?",
            "A list of directories searched by the shell for executable commands."
        ),
        (
            "6. Why should production SSH access be restricted?",
            "Reducing exposed authentication surfaces lowers the attack surface."
        ),
        (
            "7. What does systemctl manage?",
            "It communicates with systemd to inspect and control services and other units."
        ),
        (
            "8. Why are backups not enough by themselves?",
            "A backup strategy also requires secure retention and successful restoration testing."
        ),
        (
            "9. Why use subprocess argument lists in Python?",
            "They avoid unnecessary shell parsing and reduce command-injection risk when arguments are treated as data."
        ),
        (
            "10. Why should configuration changes be validated before service restart?",
            "A syntax or semantic configuration error can cause service failure or an outage."
        ),
    ]

    for question, answer in questions:
        print(f"\n{question}")
        print(f"Answer: {answer}")


# ============================================================================
# Main program
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Comprehensive Linux Installation and Environment study script."
    )
    parser.add_argument(
        "--section",
        choices=[
            "all",
            "fundamentals",
            "vm",
            "installation",
            "terminal",
            "permissions",
            "environment",
            "packages",
            "services",
            "networking",
            "ssh",
            "cloud",
            "security",
            "automation",
            "performance",
            "debugging",
            "inspection",
            "python",
            "production",
            "comparisons",
            "lab",
            "quiz",
        ],
        default="all",
        help="Run one topic instead of the complete study guide.",
    )

    args = parser.parse_args()

    sections = {
        "fundamentals": teach_linux_fundamentals,
        "vm": teach_virtual_machines,
        "installation": teach_linux_installation,
        "terminal": teach_terminal,
        "permissions": teach_filesystem_and_permissions,
        "environment": teach_environment_variables,
        "packages": teach_package_management,
        "services": teach_processes_and_services,
        "networking": teach_networking,
        "ssh": teach_ssh,
        "cloud": teach_cloud_linux,
        "security": teach_security,
        "automation": teach_automation,
        "performance": teach_performance,
        "debugging": teach_debugging,
        "inspection": inspect_local_environment,
        "python": demonstrate_secure_python_patterns,
        "production": teach_production_practices,
        "comparisons": teach_comparisons,
        "lab": run_practical_lab,
        "quiz": knowledge_check,
    }

    if args.section == "all":
        for function in sections.values():
            function()
    else:
        sections[args.section]()

    title("Study script execution complete")
    explain(
        "The script separates conceptual administration commands from commands "
        "that modify the operating system. Commands shown for installation, "
        "firewalling, partitioning, SSH hardening, and service management should "
        "be executed only on systems you own or are explicitly authorized to "
        "administer."
    )


if __name__ == "__main__":
    main()
