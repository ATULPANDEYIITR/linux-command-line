#!/usr/bin/env python3
"""
Introduction to Linux
=====================

A self-contained study program covering Linux architecture, distributions,
kernels, shells, command-line concepts, processes, filesystems, permissions,
packages, networking, containers, virtualization, security, and the reasons
Linux dominates cloud infrastructure.

The program is designed to run on Linux, macOS, or Windows. Linux-specific
commands are executed only when available and are limited to read-oriented
inspection commands.

No third-party Python packages are required.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def title(text: str) -> None:
    """Print a consistent section heading."""
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def subsection(text: str) -> None:
    """Print a smaller heading."""
    print("\n" + "-" * 78)
    print(text)
    print("-" * 78)


def explain(text: str) -> None:
    """Print wrapped explanatory text."""
    print(textwrap.fill(text, width=76))


def show(label: str, value: object) -> None:
    """Display a named value."""
    print(f"{label:<28}: {value}")


def run_command(
    command: list[str],
    timeout: float = 3.0,
) -> tuple[int, str, str]:
    """
    Execute a command safely enough for educational inspection.

    The function does not invoke a shell, which avoids shell interpretation
    of command strings. Only commands explicitly passed as argument lists
    are executed.
    """
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except (FileNotFoundError, PermissionError):
        return 127, "", "command not available"
    except subprocess.TimeoutExpired:
        return 124, "", "command timed out"


# ---------------------------------------------------------------------------
# 1. What Linux is
# ---------------------------------------------------------------------------

def section_linux_definition() -> None:
    title("1. What is Linux?")

    explain(
        "Linux is a family of operating systems built around the Linux kernel. "
        "Strictly speaking, Linux is the kernel rather than the complete operating "
        "system. A practical Linux operating system combines the kernel with system "
        "libraries, utilities, a package manager, services, applications, and often "
        "a graphical desktop or server software."
    )

    explain(
        "The kernel is the privileged core responsible for managing hardware and "
        "system resources. User applications normally do not access hardware directly. "
        "They request services through system calls exposed by the kernel."
    )

    print("\nA simplified Linux stack:")
    print(
        """
        +---------------------------------------------------+
        | Applications                                     |
        | Web servers | Databases | Python | Java | CLI   |
        +---------------------------------------------------+
        | Shells and System Utilities                     |
        | bash | sh | systemd tools | core utilities     |
        +---------------------------------------------------+
        | Libraries and Runtime                           |
        | glibc | OpenSSL | language runtimes            |
        +---------------------------------------------------+
        | Linux Kernel                                     |
        | Processes | Memory | Filesystems | Networking  |
        | Drivers | Security | Scheduling                 |
        +---------------------------------------------------+
        | Hardware                                        |
        | CPU | RAM | Disk | Network | GPU | Devices     |
        +---------------------------------------------------+
        """
    )

    explain(
        "This layered model is useful because a failure or configuration change "
        "at one layer can affect the layers above it. For example, an application "
        "may fail because a library is missing, a service may fail because a file "
        "permission is incorrect, or a process may fail because the kernel denies "
        "a requested operation."
    )


# ---------------------------------------------------------------------------
# 2. Operating-system architecture
# ---------------------------------------------------------------------------

def section_architecture() -> None:
    title("2. Operating-system architecture")

    subsection("Kernel space and user space")

    explain(
        "Modern operating systems separate privileged kernel space from ordinary "
        "user space. Kernel code can perform sensitive operations such as configuring "
        "memory mappings and device access. User programs operate with restricted "
        "privileges and request protected operations through system calls."
    )

    print(
        """
        User space
        ├── Shell
        ├── Python application
        ├── Web server
        ├── Database
        └── Other processes
                │
                │ system calls
                ▼
        Kernel space
        ├── Process scheduler
        ├── Virtual memory
        ├── Virtual filesystem
        ├── Network stack
        ├── Device drivers
        └── Security mechanisms
                │
                ▼
        Hardware
        """
    )

    subsection("Monolithic kernel with modular design")

    explain(
        "Linux is commonly described as a monolithic kernel because major operating "
        "system services such as process management, memory management, networking, "
        "and filesystem support operate within kernel space. This does not mean every "
        "driver or feature must be permanently built into one binary. Linux supports "
        "loadable kernel modules, allowing many components to be loaded and unloaded "
        "when needed."
    )

    subsection("System calls")

    explain(
        "A system call is a controlled interface through which a user-space program "
        "requests a kernel service. Common examples include operations associated "
        "with opening files, creating processes, reading data, writing data, and "
        "communicating through sockets."
    )

    print("\nConceptual example:")
    print("Python open() -> language/runtime library -> system call -> Linux kernel -> filesystem")


# ---------------------------------------------------------------------------
# 3. Linux distributions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DistributionFamily:
    name: str
    examples: tuple[str, ...]
    package_manager: str
    common_use: str


DISTRIBUTIONS = (
    DistributionFamily(
        "Debian family",
        ("Debian", "Ubuntu", "Linux Mint"),
        "APT / dpkg",
        "Servers, desktops, cloud systems, general-purpose computing",
    ),
    DistributionFamily(
        "Red Hat family",
        ("Red Hat Enterprise Linux", "Fedora", "Rocky Linux", "AlmaLinux"),
        "DNF / RPM",
        "Enterprise servers, cloud, development, infrastructure",
    ),
    DistributionFamily(
        "Arch family",
        ("Arch Linux", "Manjaro"),
        "pacman",
        "Customizable desktops and learning",
    ),
    DistributionFamily(
        "SUSE family",
        ("SUSE Linux Enterprise", "openSUSE"),
        "zypper / RPM",
        "Enterprise and development environments",
    ),
)


def section_distributions() -> None:
    title("3. Linux distributions")

    explain(
        "A Linux distribution packages the Linux kernel together with software "
        "required to create a usable operating system. Distributions differ in "
        "release model, package ecosystem, default configuration, support policy, "
        "security tooling, desktop choices, and intended audience."
    )

    print("\nMajor distribution families:")
    for distro in DISTRIBUTIONS:
        print(f"\n{distro.name}")
        print(f"  Examples        : {', '.join(distro.examples)}")
        print(f"  Package system  : {distro.package_manager}")
        print(f"  Typical use     : {distro.common_use}")

    explain(
        "A distribution should not be confused with the kernel itself. Two "
        "distributions may use Linux while providing substantially different "
        "administration tools, default services, repositories, and release policies."
    )

    subsection("Stable versus rolling release")

    print(
        """
        Stable release
        - Versioned releases
        - Strong emphasis on predictable updates
        - Common in production infrastructure

        Rolling release
        - Continuous package updates
        - Newer software arrives continuously
        - Requires careful update management
        """
    )

    explain(
        "Production systems often prioritize predictable behavior over receiving "
        "the newest software immediately. Development environments may accept more "
        "frequent changes when newer compiler, language, or framework versions are useful."
    )


# ---------------------------------------------------------------------------
# 4. Detect the current operating environment
# ---------------------------------------------------------------------------

def parse_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    """Parse the standard Linux os-release format when present."""
    result: dict[str, str] = {}

    if not path.exists():
        return result

    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in line or line.startswith("#"):
                continue

            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            result[key] = value
    except OSError:
        return {}

    return result


def section_environment() -> None:
    title("4. Inspecting the current operating environment")

    show("Operating system", platform.system())
    show("OS release", platform.release())
    show("Kernel version", platform.version())
    show("Machine architecture", platform.machine())
    show("Python version", platform.python_version())
    show("Processor", platform.processor() or "Not reported")
    show("Hostname", socket.gethostname())

    os_release = parse_os_release()

    if os_release:
        subsection("Linux distribution information")
        show("Distribution", os_release.get("PRETTY_NAME", "Unknown"))
        show("Distribution ID", os_release.get("ID", "Unknown"))
        show("Version", os_release.get("VERSION", "Unknown"))
        show("Version ID", os_release.get("VERSION_ID", "Unknown"))
    else:
        explain(
            "The standard /etc/os-release file is normally available on Linux. "
            "It was not found here, so distribution-specific information cannot "
            "be determined from that file."
        )

    subsection("Environment variables")

    important_variables = (
        "HOME",
        "PATH",
        "SHELL",
        "USER",
        "LANG",
        "PWD",
    )

    for name in important_variables:
        show(name, os.environ.get(name, "<not set>"))

    explain(
        "Environment variables are key-value settings inherited by processes. "
        "PATH is especially important because it determines which directories "
        "are searched when a command is entered without an explicit path."
    )


# ---------------------------------------------------------------------------
# 5. The shell
# ---------------------------------------------------------------------------

def section_shell() -> None:
    title("5. Shells and command-line interfaces")

    explain(
        "A shell is a program that interprets commands and starts other programs. "
        "Bash is one of the most widely used Unix-like shells. Other shells include "
        "sh, zsh, fish, and ksh. The shell is not the Linux kernel."
    )

    print(
        """
        Keyboard input
             |
             v
        Shell
        ├── parses command
        ├── expands variables
        ├── handles redirection
        ├── creates pipelines
        └── starts processes
             |
             v
        Linux kernel
             |
             v
        Process execution
        """
    )

    subsection("Important shell concepts")

    concepts = {
        "Command": "A program or shell builtin requested by the user.",
        "Argument": "A value supplied to a command.",
        "Option": "A command-line parameter controlling behavior.",
        "Pipe": "Connects standard output of one process to standard input of another.",
        "Redirection": "Changes where standard input or output goes.",
        "Environment variable": "A named value inherited by child processes.",
        "Exit status": "An integer returned by a process to indicate success or failure.",
    }

    for key, value in concepts.items():
        print(f"{key:<20}: {value}")

    subsection("Command execution from Python")

    # shutil.which() searches PATH without invoking a shell.
    for command in ("bash", "sh", "zsh", "powershell", "cmd"):
        location = shutil.which(command)
        print(f"{command:<12} -> {location or 'not found'}")

    subsection("Safe command demonstration")

    # uname is read-only and useful for understanding the current kernel.
    if shutil.which("uname"):
        code, stdout, stderr = run_command(["uname", "-a"])
        if code == 0:
            print("uname -a:")
            print(stdout)
        else:
            print(f"uname failed: {stderr}")
    else:
        explain(
            "The uname command is not available on this platform. The Python "
            "platform module provided the equivalent basic operating-system information."
        )


# ---------------------------------------------------------------------------
# 6. Filesystem hierarchy
# ---------------------------------------------------------------------------

def section_filesystem() -> None:
    title("6. Linux filesystem hierarchy")

    explain(
        "Linux uses a hierarchical filesystem. The root directory is represented "
        "by /. Unlike Windows drive-letter conventions, a Linux system presents "
        "filesystems through a directory tree. Additional filesystems can be "
        "mounted at directories called mount points."
    )

    directories = {
        "/": "Root of the filesystem hierarchy.",
        "/bin": "Essential user command binaries on systems that retain this path.",
        "/boot": "Bootloader files and Linux kernel-related boot files.",
        "/dev": "Device representations exposed to user space.",
        "/etc": "System-wide configuration files.",
        "/home": "Home directories for ordinary users.",
        "/lib": "Essential shared libraries and kernel modules on applicable layouts.",
        "/opt": "Optional third-party application software.",
        "/proc": "Virtual filesystem exposing process and kernel information.",
        "/root": "Home directory of the root account.",
        "/run": "Volatile runtime state.",
        "/sbin": "System administration binaries on applicable layouts.",
        "/srv": "Data served by system services.",
        "/sys": "Virtual filesystem exposing kernel/device information.",
        "/tmp": "Temporary files.",
        "/usr": "Large collection of user-space programs, libraries, and shared data.",
        "/var": "Variable data such as logs, caches, queues, and application state.",
    }

    for path, description in directories.items():
        print(f"{path:<8} {description}")

    subsection("Everything is represented through filesystem interfaces")

    explain(
        "Unix-like systems commonly expose many resources through file-like "
        "interfaces. Linux's virtual filesystems, including procfs and sysfs, "
        "make kernel and device information inspectable through paths even though "
        "the information is not ordinary persistent disk files."
    )

    if Path("/proc").exists():
        print("\nThis system has /proc.")
        for path in ("/proc/cpuinfo", "/proc/meminfo", "/proc/uptime"):
            file_path = Path(path)
            if file_path.exists():
                try:
                    content = file_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                    print(f"\n{path}:")
                    print("\n".join(content.splitlines()[:8]))
                except OSError as error:
                    print(f"Could not read {path}: {error}")
    else:
        explain(
            "/proc is a Linux virtual filesystem. It is not available on this "
            "non-Linux environment."
        )


# ---------------------------------------------------------------------------
# 7. Files, directories, paths, and links
# ---------------------------------------------------------------------------

def section_files_and_paths() -> None:
    title("7. Files, directories, paths, and links")

    explain(
        "Linux paths can be absolute or relative. An absolute path starts at /. "
        "A relative path is interpreted from the current working directory."
    )

    print(
        """
        /home/user/project/report.txt     absolute path
        ./report.txt                      relative to current directory
        ../report.txt                     one directory above
        ~                                 home directory in many shells
        .                                 current directory
        ..                                parent directory
        """
    )

    subsection("Symbolic links and hard links")

    explain(
        "A symbolic link is a filesystem object that points to another path. "
        "A hard link is another directory entry referring to the same underlying "
        "inode on filesystems that support the operation. Symbolic links can point "
        "across filesystems, while hard links generally cannot."
    )

    with tempfile.TemporaryDirectory() as temporary_directory:
        base = Path(temporary_directory)
        original = base / "original.txt"
        symbolic = base / "symbolic.txt"
        hard = base / "hard.txt"

        original.write_text("Linux filesystem example\n", encoding="utf-8")

        try:
            symbolic.symlink_to(original.name)
        except OSError:
            symbolic = None

        try:
            hard.link_to(original)
        except OSError:
            hard = None

        print(f"Original exists : {original.exists()}")
        print(f"Symbolic link   : {symbolic is not None and symbolic.is_symlink()}")
        print(f"Hard link       : {hard is not None and hard.exists()}")

        if hard is not None:
            print(f"Original inode  : {original.stat().st_ino}")
            print(f"Hard-link inode : {hard.stat().st_ino}")

        if symbolic is not None:
            print(f"Symlink target  : {os.readlink(symbolic)}")


# ---------------------------------------------------------------------------
# 8. Permissions and ownership
# ---------------------------------------------------------------------------

def section_permissions() -> None:
    title("8. Users, groups, ownership, and permissions")

    explain(
        "Linux uses users and groups as fundamental parts of its access-control "
        "model. Files commonly have an owner, a group, and permission bits for "
        "the owner, group, and other users."
    )

    print(
        """
        Example permission representation:

        -rwxr-x---

        -       regular file
        rwx     owner: read, write, execute
        r-x     group: read, execute
        ---     others: no permissions
        """
    )

    subsection("Permission meanings")

    permissions = {
        "read (r)": "Read file contents or list directory entries.",
        "write (w)": "Modify file contents or modify directory entries.",
        "execute (x)": "Execute a file or traverse a directory.",
    }

    for permission, meaning in permissions.items():
        print(f"{permission:<12}: {meaning}")

    subsection("Numeric permissions")

    print(
        """
        r = 4
        w = 2
        x = 1

        7 = rwx
        6 = rw-
        5 = r-x
        4 = r--
        0 = ---

        755 = rwxr-xr-x
        644 = rw-r--r--
        """
    )

    explain(
        "The execute bit has a different practical meaning for directories. "
        "A user generally needs directory execute permission to traverse that "
        "directory, even when the directory also has read permission."
    )

    if hasattr(os, "stat"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "permissions.txt"
            path.write_text("permission example\n", encoding="utf-8")

            mode = path.stat().st_mode
            print(f"\nTemporary file: {path}")
            print(f"Mode bits: {oct(mode & 0o777)}")


# ---------------------------------------------------------------------------
# 9. Processes
# ---------------------------------------------------------------------------

def section_processes() -> None:
    title("9. Processes and process management")

    explain(
        "A process is a running instance of a program. It has an address space, "
        "execution state, open resources, environment information, and an operating "
        "system process identifier called a PID."
    )

    print(
        """
        Program on disk
             |
             | start
             v
        Process
        ├── PID
        ├── virtual address space
        ├── open file descriptors
        ├── environment
        ├── credentials
        └── threads
        """
    )

    subsection("Parent and child processes")

    explain(
        "Processes can create other processes. The resulting relationship is often "
        "described as parent and child. On Linux, process creation is commonly based "
        "on fork-like mechanisms followed by program execution through exec-like "
        "mechanisms."
    )

    subsection("Demonstration with Python")

    child_code = (
        "import os, time; "
        "print(f'child pid={os.getpid()} parent={os.getppid()}', flush=True); "
        "time.sleep(0.2)"
    )

    if hasattr(os, "fork"):
        print("This operating system provides os.fork().")
        pid = os.fork()

        if pid == 0:
            # Child process.
            print(f"Child process: PID={os.getpid()}, parent={os.getppid()}")
            os._exit(0)
        else:
            # Parent waits for the child to finish.
            waited_pid, status = os.waitpid(pid, 0)
            print(f"Parent process: waited for PID={waited_pid}, status={status}")
    else:
        explain(
            "os.fork() is not available on this operating system. A subprocess "
            "example is used instead."
        )
        completed = subprocess.run(
            [sys.executable, "-c", child_code],
            capture_output=True,
            text=True,
            check=False,
        )
        print(completed.stdout.strip())

    explain(
        "A process is not identical to a program file. One program can create "
        "many simultaneous processes, and a process has runtime state that does "
        "not exist merely because the executable file exists."
    )


# ---------------------------------------------------------------------------
# 10. Threads and scheduling
# ---------------------------------------------------------------------------

def section_threads() -> None:
    title("10. Threads and CPU scheduling")

    explain(
        "A process may contain one or multiple threads. Threads within a process "
        "share many process resources, including the address space, while maintaining "
        "their own execution state such as a stack and scheduling context."
    )

    print(
        """
        Process
        ├── Thread 1
        ├── Thread 2
        └── Thread 3

        Shared resources
        ├── virtual address space
        ├── open file descriptors
        └── process-level resources
        """
    )

    subsection("Scheduling")

    explain(
        "The Linux scheduler decides which runnable threads receive CPU time. "
        "Modern Linux scheduling is preemptive, meaning the kernel can interrupt "
        "a running task and schedule another task according to scheduling policy "
        "and priority."
    )

    explain(
        "For CPU-bound workloads, available CPU cores and scheduling behavior affect "
        "throughput. For I/O-bound workloads, processes can spend substantial time "
        "waiting for network, disk, or other operations, allowing other tasks to run."
    )


# ---------------------------------------------------------------------------
# 11. Memory management
# ---------------------------------------------------------------------------

def section_memory() -> None:
    title("11. Memory management")

    explain(
        "Linux provides processes with virtual address spaces rather than exposing "
        "physical RAM directly. Virtual memory improves isolation, simplifies memory "
        "management, and allows mechanisms such as demand paging and memory mapping."
    )

    print(
        """
        Process virtual address space
        ├── code
        ├── read-only data
        ├── heap
        ├── shared libraries
        ├── memory mappings
        └── stack

                   virtual addresses
                          |
                          v
                  Memory-management unit
                          |
                          v
                    Physical memory
        """
    )

    subsection("Memory concepts")

    concepts = {
        "Virtual memory": "Address space presented to a process.",
        "Page": "A fixed-size unit used for virtual-memory management.",
        "Page table": "Maps virtual addresses to physical memory locations or states.",
        "Swap": "Disk-backed storage that can hold memory pages when configured.",
        "OOM": "Out-of-memory condition in which available memory is insufficient.",
        "Memory mapping": "Mapping files or anonymous memory into a process address space.",
    }

    for key, value in concepts.items():
        print(f"{key:<18}: {value}")

    if Path("/proc/meminfo").exists():
        subsection("Reading memory information")
        try:
            lines = Path("/proc/meminfo").read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
            for line in lines[:6]:
                print(line)
        except OSError as error:
            print(f"Unable to read /proc/meminfo: {error}")


# ---------------------------------------------------------------------------
# 12. Networking
# ---------------------------------------------------------------------------

def section_networking() -> None:
    title("12. Linux networking")

    explain(
        "Linux contains a full networking stack used by servers, desktops, routers, "
        "firewalls, containers, virtual machines, and cloud infrastructure. Applications "
        "normally communicate using sockets, while the kernel handles lower-level "
        "networking functions."
    )

    print(
        """
        Application
             |
             v
        Socket API
             |
             v
        Transport layer
        TCP / UDP
             |
             v
        Internet layer
        IP
             |
             v
        Link layer
        Ethernet / Wi-Fi / virtual interfaces
             |
             v
        Network device
        """
    )

    subsection("Inspect the local network configuration")

    for command in (["ip", "addr"], ["ifconfig"]):
        if shutil.which(command[0]):
            code, stdout, stderr = run_command(command)
            if code == 0:
                print(f"\nCommand: {' '.join(command)}")
                print("\n".join(stdout.splitlines()[:20]))
                break

    subsection("Socket example")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind(("127.0.0.1", 0))
        assigned_port = server_socket.getsockname()[1]
        server_socket.listen(1)

        print(f"Bound a local TCP socket to 127.0.0.1:{assigned_port}")
        print("The socket is listening only on the local machine.")
    finally:
        server_socket.close()

    explain(
        "Binding to 127.0.0.1 restricts this demonstration to the local host. "
        "Production services often bind to a specific interface or all interfaces "
        "depending on their intended network exposure."
    )


# ---------------------------------------------------------------------------
# 13. Services and system initialization
# ---------------------------------------------------------------------------

def section_services() -> None:
    title("13. Services, daemons, and system initialization")

    explain(
        "A daemon is a background process that performs a service without requiring "
        "continuous interactive input. Examples include web servers, schedulers, "
        "logging services, SSH servers, and database servers."
    )

    explain(
        "Modern Linux distributions commonly use systemd as the initialization and "
        "service-management system, although other init systems exist. systemd can "
        "start services, manage dependencies, track processes, collect logs through "
        "journald, and coordinate system startup."
    )

    if shutil.which("systemctl"):
        subsection("systemctl inspection")
        code, stdout, stderr = run_command(["systemctl", "is-system-running"])
        if stdout:
            print(f"systemctl is-system-running -> {stdout}")
        elif stderr:
            print(f"systemctl inspection result -> {stderr}")
    else:
        explain(
            "systemctl is not available in this environment. This is normal on "
            "non-systemd systems and non-Linux operating systems."
        )


# ---------------------------------------------------------------------------
# 14. Package management
# ---------------------------------------------------------------------------

def section_packages() -> None:
    title("14. Package management")

    explain(
        "Linux distributions normally use package managers to install, update, "
        "remove, and verify software. A package usually contains files plus metadata "
        "such as version information and dependency requirements."
    )

    print(
        """
        Debian / Ubuntu family
        apt -> high-level package management
        dpkg -> low-level .deb package management

        Fedora / RHEL family
        dnf -> high-level package management
        rpm -> low-level RPM package management

        Arch family
        pacman -> package management
        """
    )

    explain(
        "Package managers solve dependency-management problems by maintaining "
        "repositories and package metadata. Repositories allow administrators to "
        "obtain software from controlled sources and update it systematically."
    )

    available = [
        command
        for command in ("apt", "dnf", "yum", "pacman", "zypper", "rpm", "dpkg")
        if shutil.which(command)
    ]

    show("Package commands detected", ", ".join(available) if available else "None")

    explain(
        "A common mistake is to install software by downloading arbitrary binaries "
        "from untrusted locations. Package provenance, repository configuration, "
        "signatures, update policy, and dependency behavior should be considered "
        "when managing production systems."
    )


# ---------------------------------------------------------------------------
# 15. Environment variables and PATH
# ---------------------------------------------------------------------------

def section_environment_variables() -> None:
    title("15. Environment variables and PATH")

    explain(
        "An environment is a collection of key-value variables inherited by a "
        "new process from its parent. Applications frequently use environment "
        "variables for configuration such as paths, locale settings, and service "
        "configuration."
    )

    path_value = os.environ.get("PATH", "")
    path_entries = path_value.split(os.pathsep) if path_value else []

    print("\nPATH entries:")
    for index, entry in enumerate(path_entries, start=1):
        print(f"{index:>3}. {entry}")

    subsection("Demonstrate PATH lookup")

    executable = "python"
    location = shutil.which(executable)
    show(f"Location of {executable}", location or "not found")

    explain(
        "PATH ordering matters. If multiple executable files have the same command "
        "name, the shell generally uses the first matching directory in PATH. "
        "Accidentally placing an untrusted directory earlier in PATH can create "
        "a command-hijacking risk."
    )


# ---------------------------------------------------------------------------
# 16. Standard input, output, error, and exit status
# ---------------------------------------------------------------------------

def section_io() -> None:
    title("16. Standard input, output, error, and exit status")

    explain(
        "Unix-like processes conventionally use three standard file descriptors: "
        "0 for standard input, 1 for standard output, and 2 for standard error."
    )

    print(
        """
        File descriptor 0 -> stdin
        File descriptor 1 -> stdout
        File descriptor 2 -> stderr
        """
    )

    subsection("Python subprocess demonstration")

    command = [
        sys.executable,
        "-c",
        "print('standard output'); import sys; print('standard error', file=sys.stderr)",
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    show("Exit status", completed.returncode)
    print(f"Captured stdout: {completed.stdout.strip()}")
    print(f"Captured stderr: {completed.stderr.strip()}")

    explain(
        "Separating standard output and standard error is useful in automation. "
        "A program can emit normal results to stdout while sending diagnostics "
        "to stderr."
    )


# ---------------------------------------------------------------------------
# 17. Pipes and composability
# ---------------------------------------------------------------------------

def section_pipes() -> None:
    title("17. Pipes and composability")

    explain(
        "A Unix pipeline connects the output of one process to the input of another. "
        "This design encourages small programs that perform focused operations and "
        "can be combined into larger workflows."
    )

    print(
        """
        command A
            |
            | stdout
            v
        command B
            |
            | stdout
            v
        command C
        """
    )

    subsection("Pipeline implemented with Python subprocess")

    first = subprocess.Popen(
        [sys.executable, "-c", "print('linux\\nkernel\\nshell\\ncloud\\n')"],
        stdout=subprocess.PIPE,
        text=True,
    )

    assert first.stdout is not None

    second = subprocess.Popen(
        [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
        stdin=first.stdout,
        stdout=subprocess.PIPE,
        text=True,
    )

    first.stdout.close()
    output, _ = second.communicate()
    first.wait()

    print(output.strip())

    explain(
        "The example reproduces the idea of a shell pipeline without invoking "
        "a shell. Avoiding shell=True when it is unnecessary is often safer when "
        "command arguments may contain untrusted input."
    )


# ---------------------------------------------------------------------------
# 18. Linux security model
# ---------------------------------------------------------------------------

def section_security() -> None:
    title("18. Linux security fundamentals")

    explain(
        "Linux security begins with isolation and least privilege. Users and groups "
        "limit access, file permissions protect resources, and kernel security "
        "mechanisms provide additional controls."
    )

    print(
        """
        Important security layers
        ├── User and group permissions
        ├── File ownership
        ├── Linux capabilities
        ├── SELinux / AppArmor
        ├── Namespaces
        ├── cgroups
        ├── Seccomp
        ├── Firewalling
        ├── Secure authentication
        └── Software updates
        """
    )

    subsection("Root")

    explain(
        "The root account traditionally has broad administrative authority. Running "
        "every application as root violates least privilege because a compromise "
        "of that application can potentially gain much greater control."
    )

    subsection("sudo")

    explain(
        "sudo allows an authorized user to execute selected commands with elevated "
        "privileges. Production environments should configure administrative access "
        "carefully and avoid treating sudo as a substitute for access control design."
    )

    subsection("Capabilities")

    explain(
        "Linux capabilities divide some traditional root privileges into smaller "
        "units. This can allow a process to receive only the specific privileged "
        "operation it requires."
    )

    subsection("Mandatory access control")

    explain(
        "SELinux and AppArmor can impose policy-based restrictions beyond ordinary "
        "Unix permission bits. These mechanisms are particularly important for "
        "hardening services that process untrusted or externally supplied data."
    )


# ---------------------------------------------------------------------------
# 19. Namespaces and containers
# ---------------------------------------------------------------------------

def section_namespaces() -> None:
    title("19. Namespaces and Linux containers")

    explain(
        "Linux namespaces isolate selected views of system resources. Different "
        "namespace types can isolate process identifiers, networking, mount points, "
        "user identities, hostnames, and other resources."
    )

    print(
        """
        Container process
        ├── PID namespace
        ├── Network namespace
        ├── Mount namespace
        ├── User namespace
        └── Other isolation mechanisms
        """
    )

    explain(
        "Containers are not simply lightweight virtual machines. Traditional "
        "containers share the host kernel while isolating processes and resources "
        "through kernel mechanisms. A virtual machine normally provides a virtualized "
        "hardware environment with a separate guest kernel."
    )

    subsection("Containers versus virtual machines")

    print(
        """
        Containers
        - Share host kernel
        - Usually start quickly
        - High workload density
        - Strong process/resource isolation, but kernel is shared

        Virtual machines
        - Guest operating system has its own kernel
        - Stronger hardware/OS boundary
        - Usually greater resource overhead
        - Can run a different operating system family
        """
    )


# ---------------------------------------------------------------------------
# 20. cgroups and resource control
# ---------------------------------------------------------------------------

def section_cgroups() -> None:
    title("20. Control groups and resource management")

    explain(
        "Linux control groups, commonly called cgroups, organize processes and "
        "control or account for resources such as CPU, memory, and I/O. They are "
        "a major foundation for modern container platforms."
    )

    print(
        """
        Host
        |
        +-- Workload A
        |     +-- process
        |     +-- process
        |     CPU limit
        |     memory limit
        |
        +-- Workload B
              +-- process
              +-- process
              CPU limit
              memory limit
        """
    )

    explain(
        "Namespaces answer questions such as 'what can this process see?' "
        "Cgroups answer questions such as 'how much resource can this group use?' "
        "Together they form an important part of the Linux container model."
    )

    if Path("/sys/fs/cgroup").exists():
        show("cgroup filesystem", "/sys/fs/cgroup is present")
    else:
        show("cgroup filesystem", "Not detected")


# ---------------------------------------------------------------------------
# 21. Virtualization
# ---------------------------------------------------------------------------

def section_virtualization() -> None:
    title("21. Linux and virtualization")

    explain(
        "Linux can act as a guest operating system inside a virtual machine or as "
        "a host platform running virtual machines. Technologies such as KVM use "
        "hardware virtualization capabilities to allow guest operating systems "
        "to execute efficiently."
    )

    print(
        """
        Physical server
        |
        +-- Linux host
        |     |
        |     +-- VM 1 -> guest kernel
        |     +-- VM 2 -> guest kernel
        |     +-- VM 3 -> guest kernel
        |
        +-- Containers
              |
              +-- application processes
        """
    )

    explain(
        "Cloud platforms commonly combine virtualization with Linux because it "
        "provides a mature operating-system platform for compute instances, networking, "
        "storage, orchestration, monitoring, and automation."
    )


# ---------------------------------------------------------------------------
# 22. Why Linux dominates cloud infrastructure
# ---------------------------------------------------------------------------

def section_cloud() -> None:
    title("22. Why Linux dominates cloud infrastructure")

    factors = {
        "Open-source model": (
            "Organizations can inspect, modify, automate, and deploy Linux "
            "without relying on a single proprietary operating-system vendor."
        ),
        "Automation": (
            "Linux exposes extensive command-line and programmatic interfaces, "
            "which work well with infrastructure automation and CI/CD."
        ),
        "Resource efficiency": (
            "Linux can run effectively on small virtual machines as well as "
            "large multi-core servers."
        ),
        "Networking": (
            "Linux has mature networking facilities and is widely used for "
            "servers, appliances, routers, and container networking."
        ),
        "Container ecosystem": (
            "Namespaces, cgroups, capabilities, seccomp, and related kernel "
            "facilities form important foundations for containers."
        ),
        "Developer ecosystem": (
            "Linux supports major programming languages, databases, web servers, "
            "development tools, and open-source infrastructure software."
        ),
        "Operational maturity": (
            "Logging, service management, process control, permissions, networking, "
            "monitoring, and scripting are deeply integrated into the ecosystem."
        ),
        "Portability": (
            "Linux runs across many architectures and hardware environments, "
            "from embedded devices to cloud servers and supercomputers."
        ),
    }

    for factor, explanation in factors.items():
        print(f"\n{factor}")
        explain(explanation)

    subsection("Typical cloud software stack")

    print(
        """
        Cloud application
              |
        Web/API service
              |
        Container runtime / orchestration
              |
        Linux kernel
              |
        Virtual machine or bare metal
              |
        Cloud provider infrastructure
              |
        Physical hardware
        """
    )

    explain(
        "Linux's cloud importance is not explained by one feature. It results from "
        "the interaction of the kernel, networking, security controls, virtualization, "
        "containers, package ecosystems, automation tooling, and a large operational "
        "community."
    )


# ---------------------------------------------------------------------------
# 23. Cloud-native architecture
# ---------------------------------------------------------------------------

def section_cloud_native() -> None:
    title("23. Linux in cloud-native systems")

    explain(
        "Cloud-native systems frequently consist of many services running across "
        "virtual machines or containers. Linux provides the process, networking, "
        "filesystem, resource-control, and security primitives beneath these systems."
    )

    print(
        """
        Developer
           |
           v
        Source repository
           |
           v
        CI/CD pipeline
           |
           v
        Container image
           |
           v
        Container runtime
           |
           v
        Linux kernel
           |
           +-----------------------+
           |                       |
        CPU/RAM                  Network
           |                       |
           +-----------+-----------+
                       |
                    Storage
        """
    )

    explain(
        "Orchestration systems add another control layer. They can schedule workloads, "
        "restart failed processes, expose services over networks, manage configuration, "
        "and scale workloads. The underlying worker nodes commonly use Linux."
    )


# ---------------------------------------------------------------------------
# 24. Kernel modules and drivers
# ---------------------------------------------------------------------------

def section_kernel_modules() -> None:
    title("24. Kernel modules and device drivers")

    explain(
        "A device driver allows the operating system to communicate with particular "
        "hardware or virtual devices. Linux supports loadable kernel modules, which "
        "can provide drivers and other kernel functionality without requiring every "
        "component to be permanently built into the kernel image."
    )

    if shutil.which("lsmod"):
        code, stdout, stderr = run_command(["lsmod"])
        if code == 0:
            print("\nLoaded modules:")
            print("\n".join(stdout.splitlines()[:15]))
        else:
            print(f"lsmod unavailable or failed: {stderr}")
    else:
        explain(
            "lsmod is not available in this environment. It is normally used on "
            "Linux systems to inspect currently loaded kernel modules."
        )

    if shutil.which("uname"):
        code, stdout, stderr = run_command(["uname", "-r"])
        if code == 0:
            show("Running kernel release", stdout)


# ---------------------------------------------------------------------------
# 25. Logs and observability
# ---------------------------------------------------------------------------

def section_logs() -> None:
    title("25. Logging and observability")

    explain(
        "Production Linux systems require visibility into processes, resources, "
        "network traffic, application behavior, and failures. Logs provide historical "
        "event information, while metrics and traces can provide additional operational "
        "context."
    )

    print(
        """
        Observability signals
        ├── Logs
        ├── Metrics
        └── Traces

        Common Linux operational data
        ├── CPU usage
        ├── Memory usage
        ├── Disk usage
        ├── Network activity
        ├── Process state
        └── Service status
        """
    )

    if shutil.which("journalctl"):
        code, stdout, stderr = run_command(
            ["journalctl", "-n", "5", "--no-pager"]
        )
        if code == 0:
            print("\nRecent journal entries:")
            print(stdout)
        else:
            explain(
                "journalctl exists but the current user could not retrieve "
                "the journal with this command."
            )
    else:
        explain(
            "journalctl is not available. It is commonly used on systemd-based "
            "Linux systems to inspect system journal entries."
        )


# ---------------------------------------------------------------------------
# 26. Disk and filesystem concepts
# ---------------------------------------------------------------------------

def section_storage() -> None:
    title("26. Storage, filesystems, and mounts")

    explain(
        "A filesystem defines how data and metadata are organized on storage. "
        "Linux supports many filesystems, including ext4, XFS, Btrfs, and others."
    )

    print(
        """
        Storage device
             |
        Partition / logical volume
             |
        Filesystem
             |
        Mount point
             |
        Directory tree
        """
    )

    explain(
        "Mounting attaches a filesystem to a location in the directory hierarchy. "
        "The filesystem type, mount options, permissions, ownership, and storage "
        "characteristics all affect application behavior."
    )

    if shutil.which("df"):
        code, stdout, stderr = run_command(["df", "-h"])
        if code == 0:
            print("\ndf -h:")
            print("\n".join(stdout.splitlines()[:10]))

    if shutil.which("lsblk"):
        code, stdout, stderr = run_command(["lsblk"])
        if code == 0:
            print("\nlsblk:")
            print("\n".join(stdout.splitlines()[:15]))


# ---------------------------------------------------------------------------
# 27. Architecture and CPU compatibility
# ---------------------------------------------------------------------------

def section_architectures() -> None:
    title("27. CPU architectures and portability")

    explain(
        "Linux supports multiple processor architectures. Common cloud environments "
        "include x86-64 and ARM64. Software compiled for one architecture is not "
        "automatically executable on another architecture unless compatibility or "
        "translation mechanisms are provided."
    )

    print(
        """
        Common architectures
        - x86-64 / AMD64
        - ARM64 / AArch64
        - RISC-V
        - Other architectures supported by Linux
        """
    )

    show("Python-reported architecture", platform.machine())

    explain(
        "Architecture affects binary compatibility, instruction sets, available "
        "hardware acceleration, and sometimes software packaging. Portable source "
        "code can still require architecture-specific dependencies after compilation."
    )


# ---------------------------------------------------------------------------
# 28. Shell scripting concepts through Python
# ---------------------------------------------------------------------------

def section_automation() -> None:
    title("28. Linux automation concepts")

    explain(
        "Linux administration frequently relies on automation. Shell scripts, Python "
        "programs, configuration management, scheduled jobs, and CI/CD systems can "
        "repeat operational tasks consistently."
    )

    subsection("Idempotence")

    explain(
        "An operation is idempotent when applying it repeatedly produces the same "
        "intended final state after the first successful application. Idempotence "
        "reduces the risk of automation producing unintended cumulative changes."
    )

    def ensure_text(path: Path, text: str) -> bool:
        """
        Create a file with exact content only when the desired state differs.

        This is a simple demonstration of idempotent-style behavior.
        """
        current = None

        if path.exists():
            try:
                current = path.read_text(encoding="utf-8")
            except OSError:
                current = None

        if current == text:
            return False

        path.write_text(text, encoding="utf-8")
        return True

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "desired-state.txt"
        desired = "Linux automation state\n"

        first_change = ensure_text(path, desired)
        second_change = ensure_text(path, desired)

        print(f"First application changed state : {first_change}")
        print(f"Second application changed state: {second_change}")

    explain(
        "This pattern is simplified compared with production configuration management, "
        "but it demonstrates the distinction between 'perform an action' and "
        "'make the system reach a desired state'."
    )


# ---------------------------------------------------------------------------
# 29. Error handling and troubleshooting
# ---------------------------------------------------------------------------

def section_troubleshooting() -> None:
    title("29. Linux troubleshooting methodology")

    explain(
        "Effective troubleshooting starts by identifying the exact symptom and "
        "then collecting evidence before changing configuration. Guessing and "
        "making many simultaneous changes makes root-cause analysis difficult."
    )

    print(
        """
        A practical investigation sequence:

        1. Define the symptom.
        2. Determine whether the failure is reproducible.
        3. Check service status.
        4. Inspect logs.
        5. Check CPU and memory.
        6. Check disk space and filesystem state.
        7. Check network connectivity.
        8. Check permissions and ownership.
        9. Check recent configuration or software changes.
        10. Make one controlled change.
        11. Re-test.
        12. Record the root cause and corrective action.
        """
    )

    subsection("Useful Linux diagnostic commands")

    commands = {
        "uname": "Kernel and system information",
        "ps": "Process listing",
        "top": "Interactive process/resource monitoring",
        "free": "Memory information",
        "df": "Filesystem free-space information",
        "du": "Directory/file space usage",
        "ip": "Network interface and routing information",
        "ss": "Socket information",
        "journalctl": "systemd journal",
        "systemctl": "Service management",
        "dmesg": "Kernel message buffer",
        "lsblk": "Block-device information",
    }

    for command, purpose in commands.items():
        print(f"{command:<12}: {purpose}")


# ---------------------------------------------------------------------------
# 30. Common Linux mistakes
# ---------------------------------------------------------------------------

def section_mistakes() -> None:
    title("30. Common mistakes and misconceptions")

    mistakes = [
        (
            "Linux is the complete operating system.",
            "Linux technically refers to the kernel; distributions combine it with the rest of the operating-system environment.",
        ),
        (
            "Bash is Linux.",
            "Bash is a shell. Linux is the kernel used by Linux distributions.",
        ),
        (
            "Everything under / is stored on one physical disk.",
            "Different filesystems can be mounted at different points in the directory tree.",
        ),
        (
            "chmod 777 is a universal fix.",
            "It grants broad permissions and can create security problems. Permissions should follow least privilege.",
        ),
        (
            "Root should run every application.",
            "Applications should normally run with only the privileges they require.",
        ),
        (
            "Containers are virtual machines.",
            "Containers generally share the host kernel; virtual machines normally have guest kernels.",
        ),
        (
            "Deleting a file always frees disk space immediately.",
            "An open process can continue holding an unlinked file, so disk usage may remain until the file descriptor closes.",
        ),
        (
            "A process and a program are the same thing.",
            "A program is executable code; a process is a running instance with runtime state.",
        ),
        (
            "The newest package is always the best production choice.",
            "Production software requires compatibility, security, testing, supportability, and controlled upgrades.",
        ),
        (
            "If ping works, the application network is definitely healthy.",
            "Different protocols, ports, DNS behavior, firewalls, proxies, and application-layer failures can still cause problems.",
        ),
    ]

    for misconception, correction in mistakes:
        print(f"\nMisconception: {misconception}")
        print(f"Correction   : {correction}")


# ---------------------------------------------------------------------------
# 31. Production considerations
# ---------------------------------------------------------------------------

def section_production() -> None:
    title("31. Production Linux considerations")

    explain(
        "A production Linux system should be treated as an engineered service "
        "rather than simply a computer with software installed on it."
    )

    areas = {
        "Security": "Least privilege, patching, authentication, firewalling, secrets management, auditing.",
        "Reliability": "Backups, health checks, service restart policies, redundancy, capacity planning.",
        "Performance": "CPU, memory, disk I/O, network throughput, latency, process behavior.",
        "Observability": "Logs, metrics, alerts, traces, system health information.",
        "Automation": "Repeatable configuration, deployment, rollback, and validation.",
        "Change management": "Testing, staged rollout, version control, documented changes.",
        "Resource limits": "Prevent one workload from exhausting shared CPU, memory, or disk resources.",
        "Disaster recovery": "Recovery procedures must be tested rather than assumed to work.",
    }

    for area, details in areas.items():
        print(f"\n{area}")
        explain(details)

    explain(
        "A technically correct Linux configuration can still be operationally poor "
        "if it cannot be monitored, recovered, updated, audited, or reproduced."
    )


# ---------------------------------------------------------------------------
# 32. Performance concepts
# ---------------------------------------------------------------------------

def section_performance() -> None:
    title("32. Linux performance concepts")

    explain(
        "Performance analysis should distinguish CPU utilization, memory pressure, "
        "storage latency, storage throughput, network latency, network throughput, "
        "lock contention, scheduling behavior, and application-level bottlenecks."
    )

    print(
        """
        CPU-bound
        - Limited primarily by computation
        - More CPU capacity may improve throughput

        I/O-bound
        - Limited primarily by waiting for I/O
        - Faster storage or network may help

        Memory-bound
        - Limited by memory capacity or memory access behavior
        - Excessive swapping can severely affect performance

        Network-bound
        - Limited by bandwidth, latency, packet processing, or remote service behavior
        """
    )

    explain(
        "A high CPU percentage is not automatically a problem, and low CPU usage "
        "does not prove that a system is healthy. Measurements must be interpreted "
        "in the context of workload expectations."
    )


# ---------------------------------------------------------------------------
# 33. Security demonstration: command injection awareness
# ---------------------------------------------------------------------------

def section_command_security() -> None:
    title("33. Secure process execution")

    explain(
        "When software executes operating-system commands, passing arguments as a "
        "list is generally safer than constructing a shell command string from "
        "untrusted input. Shell metacharacters can otherwise be interpreted as "
        "additional commands."
    )

    safe_argument = "file name with spaces.txt"

    # No shell is involved here. The argument is passed as one argument.
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", safe_argument],
        capture_output=True,
        text=True,
        check=False,
    )

    print(f"Argument received by child process: {completed.stdout.strip()}")

    explain(
        "The principle is broader than Python. Any application that constructs "
        "commands for a shell must carefully handle untrusted input. Prefer direct "
        "APIs over shell commands when a direct API exists."
    )


# ---------------------------------------------------------------------------
# 34. Linux versus other operating-system approaches
# ---------------------------------------------------------------------------

def section_comparison() -> None:
    title("34. Linux compared with other operating-system approaches")

    print(
        """
        Aspect              Linux                 Windows              macOS
        --------------------------------------------------------------------------
        Kernel               Linux kernel          Windows NT           XNU
        Main ecosystem       Open-source-heavy     Proprietary-heavy    Unix-based
        Server usage         Very broad            Very broad           More limited
        Shell ecosystem      Many shells           PowerShell/cmd       zsh and Unix tools
        Package tooling      Distribution-based    Multiple systems    Homebrew + system tools
        Container role       Core infrastructure   Strong support       Strong support
        Hardware range      Very broad            Broad               Apple-focused
        Customization        Very high             Moderate             Controlled
        """
    )

    explain(
        "The comparison is intentionally broad. Modern operating systems can "
        "support similar workloads, and enterprise decisions depend on application "
        "requirements, existing expertise, licensing, hardware, security policies, "
        "support agreements, and operational constraints."
    )


# ---------------------------------------------------------------------------
# 35. Integrated mini simulation
# ---------------------------------------------------------------------------

@dataclass
class ProcessInfo:
    pid: int
    name: str
    memory_mb: float
    cpu_percent: float
    user: str


def simulate_process_table() -> list[ProcessInfo]:
    """Create a deterministic process table for studying process concepts."""
    return [
        ProcessInfo(101, "init", 18.2, 0.1, "root"),
        ProcessInfo(205, "sshd", 12.7, 0.2, "root"),
        ProcessInfo(311, "python", 84.5, 3.4, "developer"),
        ProcessInfo(412, "database", 512.0, 18.7, "dbuser"),
        ProcessInfo(509, "web-server", 128.4, 7.1, "web"),
    ]


def section_integrated_simulation() -> None:
    title("35. Integrated Linux server simulation")

    processes = simulate_process_table()

    print(
        f"{'PID':>6} {'PROCESS':<16} {'MEMORY MB':>12} "
        f"{'CPU %':>8} {'USER':<12}"
    )
    print("-" * 62)

    for process in processes:
        print(
            f"{process.pid:>6} {process.name:<16} "
            f"{process.memory_mb:>12.1f} {process.cpu_percent:>8.1f} "
            f"{process.user:<12}"
        )

    total_memory = sum(process.memory_mb for process in processes)
    total_cpu = sum(process.cpu_percent for process in processes)

    print("-" * 62)
    print(f"{'TOTAL':<23} {total_memory:>12.1f} {total_cpu:>8.1f}")

    highest_memory = max(processes, key=lambda process: process.memory_mb)
    highest_cpu = max(processes, key=lambda process: process.cpu_percent)

    print(f"\nHighest memory consumer: {highest_memory.name}")
    print(f"Highest CPU consumer   : {highest_cpu.name}")

    explain(
        "This simulation demonstrates how operational data can be represented "
        "programmatically. Real Linux monitoring tools obtain these values from "
        "the kernel and system interfaces rather than from a fixed Python list."
    )


# ---------------------------------------------------------------------------
# 36. Learning checks
# ---------------------------------------------------------------------------

def section_knowledge_checks() -> None:
    title("36. Knowledge checks")

    questions = [
        (
            "What is the difference between Linux and a Linux distribution?",
            "Linux is the kernel; a distribution packages the kernel with the software and configuration needed for a usable operating system.",
        ),
        (
            "What does a shell do?",
            "It interprets commands and starts programs while providing features such as variables, pipelines, and redirection.",
        ),
        (
            "Why are permissions important?",
            "They restrict which users and groups can read, modify, execute, or traverse resources.",
        ),
        (
            "What is a process?",
            "A running instance of a program with runtime state and operating-system-managed resources.",
        ),
        (
            "Why is /proc special?",
            "It is a virtual filesystem exposing process and kernel information rather than ordinary persistent disk files.",
        ),
        (
            "What is the difference between namespaces and cgroups?",
            "Namespaces isolate what processes can see; cgroups control or account for resource usage.",
        ),
        (
            "Why are containers important to Linux?",
            "Linux provides kernel mechanisms such as namespaces, cgroups, capabilities, and seccomp that support process and resource isolation.",
        ),
        (
            "Why is Linux widely used in cloud infrastructure?",
            "Its open-source model, automation capabilities, networking, portability, resource efficiency, security controls, virtualization support, and container ecosystem make it well suited to infrastructure workloads.",
        ),
    ]

    for index, (question, answer) in enumerate(questions, start=1):
        print(f"\n{index}. {question}")
        print(f"   Answer: {answer}")


# ---------------------------------------------------------------------------
# 37. Main program
# ---------------------------------------------------------------------------

SECTIONS: list[tuple[str, Callable[[], None]]] = [
    ("Linux definition", section_linux_definition),
    ("Architecture", section_architecture),
    ("Distributions", section_distributions),
    ("Environment inspection", section_environment),
    ("Shell", section_shell),
    ("Filesystem", section_filesystem),
    ("Files and paths", section_files_and_paths),
    ("Permissions", section_permissions),
    ("Processes", section_processes),
    ("Threads and scheduling", section_threads),
    ("Memory", section_memory),
    ("Networking", section_networking),
    ("Services", section_services),
    ("Package management", section_packages),
    ("Environment variables", section_environment_variables),
    ("Standard I/O", section_io),
    ("Pipes", section_pipes),
    ("Security", section_security),
    ("Namespaces", section_namespaces),
    ("Cgroups", section_cgroups),
    ("Virtualization", section_virtualization),
    ("Cloud infrastructure", section_cloud),
    ("Cloud-native systems", section_cloud_native),
    ("Kernel modules", section_kernel_modules),
    ("Observability", section_logs),
    ("Storage", section_storage),
    ("Architectures", section_architectures),
    ("Automation", section_automation),
    ("Troubleshooting", section_troubleshooting),
    ("Common mistakes", section_mistakes),
    ("Production", section_production),
    ("Performance", section_performance),
    ("Command security", section_command_security),
    ("Operating-system comparison", section_comparison),
    ("Integrated simulation", section_integrated_simulation),
    ("Knowledge checks", section_knowledge_checks),
]


def run_all_sections() -> None:
    """Run every lesson in a logical beginner-to-advanced order."""
    print(
        textwrap.dedent(
            """
            INTRODUCTION TO LINUX
            ======================
            Architecture, distributions, kernels, shells, administration,
            security, containers, virtualization, and cloud infrastructure.
            """
        ).strip()
    )

    for _, function in SECTIONS:
        try:
            function()
        except KeyboardInterrupt:
            print("\nExecution interrupted by the user.")
            raise
        except Exception as error:
            # Educational programs should expose unexpected failures without
            # hiding the rest of the lesson structure.
            print(f"\nSection error in {function.__name__}: {error}")


def main() -> None:
    run_all_sections()


if __name__ == "__main__":
    main()
