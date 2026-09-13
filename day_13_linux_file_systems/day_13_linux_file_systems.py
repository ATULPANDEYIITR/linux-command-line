#!/usr/bin/env python3
"""
Linux File System: Beginner-to-Advanced Study Script

This standalone Python program teaches and demonstrates important Linux
filesystem concepts:

- Directories, files, and paths
- Absolute and relative paths
- Linux filesystem hierarchy
- File types
- File metadata
- Permissions and permission notation
- Ownership and groups
- chmod, chown, and umask concepts
- Symbolic links and hard links
- Directory permissions
- Special permission bits
- File descriptors and standard streams
- Mount points and filesystems
- Inodes and links
- Path normalization
- Safe filesystem programming with Python
- Validation and error handling
- Recursive directory traversal
- Disk usage concepts
- Security considerations
- Performance considerations
- Common mistakes and edge cases

Most examples use Python's standard library and do not require external
packages. Commands that would normally be executed in a Linux shell are
shown as strings or explained through Python where appropriate.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


# ============================================================================
# 1. BASIC TERMINOLOGY
# ============================================================================

def section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def explain_basic_terms() -> None:
    section("1. Basic Linux Filesystem Terminology")

    terms = {
        "filesystem": (
            "A system that organizes and stores files and directories on "
            "storage devices."
        ),
        "file": (
            "A named object containing data. Linux also represents many "
            "devices and interfaces as file-like objects."
        ),
        "directory": (
            "A filesystem object that maps names to filesystem objects."
        ),
        "path": (
            "A sequence of directory names used to identify a filesystem "
            "object."
        ),
        "inode": (
            "A filesystem data structure containing metadata about an object, "
            "such as permissions, ownership, timestamps, and data-block "
            "references."
        ),
        "mount point": (
            "A directory where another filesystem becomes accessible in the "
            "directory tree."
        ),
        "symbolic link": (
            "A filesystem object containing a path to another object."
        ),
        "hard link": (
            "Another directory entry referring to the same inode."
        ),
        "owner": (
            "The user associated with the owner permission class of a file."
        ),
        "group": (
            "The group associated with the group permission class of a file."
        ),
    }

    for term, definition in terms.items():
        print(f"{term:18} : {definition}")


# ============================================================================
# 2. PATHS
# ============================================================================

def demonstrate_paths() -> None:
    section("2. Paths: Absolute and Relative")

    examples = [
        "/etc/hosts",
        "/var/log",
        "/home/user/Documents/report.txt",
        "./notes.txt",
        "../notes.txt",
        "projects/python/main.py",
        "~/Documents",
    ]

    for path in examples:
        print(f"{path:35} absolute={os.path.isabs(os.path.expanduser(path))}")

    print("\nImportant distinctions:")
    print("- /etc/hosts is an absolute path because it begins at /.")
    print("- ./notes.txt is relative to the current working directory.")
    print("- ../notes.txt refers to the parent directory.")
    print("- ~ is shell syntax for the current user's home directory.")
    print("- Python does not automatically expand ~ with pathlib.Path().")


def demonstrate_pathlib() -> None:
    section("3. Python pathlib: Safer Path Manipulation")

    current = pathlib.Path.cwd()
    home = pathlib.Path.home()

    print("Current working directory:", current)
    print("Home directory:", home)

    example = current / "documents" / "report.txt"
    print("Constructed path:", example)
    print("Parent:", example.parent)
    print("Filename:", example.name)
    print("Suffix:", example.suffix)
    print("Stem:", example.stem)

    # resolve() produces an absolute path. strict=False allows a nonexistent
    # target to be resolved without requiring the file to exist.
    print("Resolved form:", example.resolve(strict=False))


# ============================================================================
# 3. FILESYSTEM HIERARCHY
# ============================================================================

def explain_filesystem_hierarchy() -> None:
    section("4. Linux Filesystem Hierarchy")

    hierarchy = {
        "/": "Filesystem root. Every absolute path starts here.",
        "/bin": "Essential user commands on systems that retain this directory.",
        "/boot": "Bootloader files, kernel images, and related boot data.",
        "/dev": "Device nodes representing devices and kernel interfaces.",
        "/etc": "System-wide configuration files.",
        "/home": "Home directories for ordinary users.",
        "/lib": "Essential shared libraries and kernel-related modules.",
        "/media": "Common mount location for removable media.",
        "/mnt": "Traditional temporary/manual mount location.",
        "/opt": "Optional application software.",
        "/proc": "Virtual filesystem exposing process and kernel information.",
        "/root": "Home directory of the root user.",
        "/run": "Runtime data created since boot.",
        "/sbin": "System administration commands on systems retaining this path.",
        "/srv": "Data intended to be served by system services.",
        "/sys": "Virtual filesystem exposing kernel/device information.",
        "/tmp": "Temporary files.",
        "/usr": "Most user-space applications, libraries, and shared data.",
        "/var": "Variable data such as logs, caches, queues, and databases.",
    }

    for path, purpose in hierarchy.items():
        print(f"{path:10} {purpose}")

    print("\nModern Linux systems may merge directories such as /bin and /usr/bin.")
    print("The exact contents of a directory vary by distribution and system.")


# ============================================================================
# 4. FILE TYPES
# ============================================================================

def file_type_name(mode: int) -> str:
    """Return a human-readable Linux file type."""
    if stat.S_ISREG(mode):
        return "regular file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symbolic link"
    if stat.S_ISCHR(mode):
        return "character device"
    if stat.S_ISBLK(mode):
        return "block device"
    if stat.S_ISFIFO(mode):
        return "FIFO/named pipe"
    if stat.S_ISSOCK(mode):
        return "socket"
    return "unknown"


def demonstrate_file_types() -> None:
    section("5. Linux File Types")

    print("The first character of a long listing commonly identifies type:")
    print("  -  regular file")
    print("  d  directory")
    print("  l  symbolic link")
    print("  c  character device")
    print("  b  block device")
    print("  p  FIFO/named pipe")
    print("  s  socket")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        regular = root / "regular.txt"
        directory = root / "directory"

        regular.write_text("Linux filesystem example\n", encoding="utf-8")
        directory.mkdir()

        for path in (regular, directory):
            mode = path.lstat().st_mode
            print(f"{path.name:15} -> {file_type_name(mode)}")


# ============================================================================
# 5. FILE METADATA
# ============================================================================

def permission_string(mode: int) -> str:
    """Convert a mode value to ls-like symbolic permissions."""
    return stat.filemode(mode)


def demonstrate_metadata() -> None:
    section("6. File Metadata")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "metadata.txt"
        path.write_text("metadata example\n", encoding="utf-8")

        metadata = path.stat()

        print("Path:", path)
        print("Size:", metadata.st_size, "bytes")
        print("Mode:", oct(stat.S_IMODE(metadata.st_mode)))
        print("Permissions:", permission_string(metadata.st_mode))
        print("Owner UID:", metadata.st_uid)
        print("Group GID:", metadata.st_gid)
        print("Inode:", metadata.st_ino)
        print("Device ID:", metadata.st_dev)
        print(
            "Modification time:",
            datetime.fromtimestamp(metadata.st_mtime).isoformat(),
        )
        print(
            "Access time:",
            datetime.fromtimestamp(metadata.st_atime).isoformat(),
        )
        print(
            "Status-change time:",
            datetime.fromtimestamp(metadata.st_ctime).isoformat(),
        )

    print(
        "\nOn Unix-like systems, ctime is generally the inode metadata "
        "change time, not the file creation time."
    )


# ============================================================================
# 6. PERMISSION MODEL
# ============================================================================

def explain_permissions() -> None:
    section("7. Linux Permissions")

    print("A typical permission string:")
    print("  -rwxr-xr--")
    print()
    print("Position interpretation:")
    print("  -          file type")
    print("  rwx        owner permissions")
    print("  r-x        group permissions")
    print("  r--        permissions for others")
    print()
    print("Permission values:")
    print("  r = 4")
    print("  w = 2")
    print("  x = 1")
    print()
    print("Common numeric modes:")
    print("  644 = rw-r--r--")
    print("  600 = rw-------")
    print("  755 = rwxr-xr-x")
    print("  700 = rwx------")
    print("  750 = rwxr-x---")

    examples = [0o644, 0o600, 0o755, 0o700, 0o750, 0o777]

    for mode in examples:
        print(f"{mode:03o} -> {stat.filemode(stat.S_IFREG | mode)}")


def permission_bits(mode: int) -> dict[str, dict[str, bool]]:
    """Return owner/group/other read-write-execute permissions."""
    return {
        "owner": {
            "read": bool(mode & stat.S_IRUSR),
            "write": bool(mode & stat.S_IWUSR),
            "execute": bool(mode & stat.S_IXUSR),
        },
        "group": {
            "read": bool(mode & stat.S_IRGRP),
            "write": bool(mode & stat.S_IWGRP),
            "execute": bool(mode & stat.S_IXGRP),
        },
        "other": {
            "read": bool(mode & stat.S_IROTH),
            "write": bool(mode & stat.S_IWOTH),
            "execute": bool(mode & stat.S_IXOTH),
        },
    }


def demonstrate_permission_bits() -> None:
    section("8. Permission Bits in Python")

    mode = 0o754
    print("Mode:", oct(mode))
    print("Meaning:", stat.filemode(stat.S_IFREG | mode))

    for identity, permissions in permission_bits(mode).items():
        print(identity, permissions)


def demonstrate_chmod() -> None:
    section("9. Changing Permissions with Python")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "private.txt"
        path.write_text("private data\n", encoding="utf-8")

        # chmod changes permission bits. This demonstration uses a temporary
        # file so that no real user file is modified.
        path.chmod(0o600)

        print("After chmod(0o600):")
        print(stat.filemode(path.stat().st_mode))

        path.chmod(0o644)
        print("After chmod(0o644):")
        print(stat.filemode(path.stat().st_mode))


# ============================================================================
# 7. DIRECTORY PERMISSIONS
# ============================================================================

def explain_directory_permissions() -> None:
    section("10. Directory Permissions")

    print("Directory permissions have meanings that differ from regular files:")
    print()
    print("Read (r):")
    print("  Allows listing directory entries.")
    print()
    print("Write (w):")
    print("  Allows creating, deleting, or renaming entries when combined with")
    print("  appropriate execute permission.")
    print()
    print("Execute (x):")
    print("  Allows traversing/searching the directory.")
    print()
    print("A directory with write permission but no execute permission can")
    print("produce surprising access behavior. Directory permissions should")
    print("therefore be evaluated as a combination, not independently.")


# ============================================================================
# 8. OWNERSHIP
# ============================================================================

def demonstrate_ownership() -> None:
    section("11. Ownership")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "ownership.txt"
        path.write_text("ownership example\n", encoding="utf-8")

        metadata = path.stat()
        print("UID:", metadata.st_uid)
        print("GID:", metadata.st_gid)

    print("\nTypical shell concepts:")
    print("  ls -l file")
    print("  chown user file")
    print("  chown user:group file")
    print("  chgrp group file")
    print()
    print(
        "Changing ownership generally requires elevated privileges or "
        "appropriate system permissions."
    )


# ============================================================================
# 9. UMASK
# ============================================================================

def demonstrate_umask() -> None:
    section("12. umask and Default Permissions")

    print("umask removes permission bits from permissions requested during")
    print("creation of files and directories.")
    print()
    print("Typical conceptual calculation:")
    print("  requested_mode AND NOT umask")
    print()
    print("Example:")
    print("  file requested mode: 666")
    print("  umask:              022")
    print("  resulting mode:     644")
    print()
    print("Directories commonly begin from a requested mode of 777.")
    print("With umask 022, the resulting mode is commonly 755.")

    current_umask = os.umask(0)
    os.umask(current_umask)

    print("\nCurrent process umask:", oct(current_umask))


# ============================================================================
# 10. SYMBOLIC LINKS
# ============================================================================

def demonstrate_symbolic_links() -> None:
    section("13. Symbolic Links")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        target = root / "original.txt"
        link = root / "shortcut.txt"

        target.write_text("content through symbolic link\n", encoding="utf-8")
        link.symlink_to(target)

        print("Target:", target)
        print("Link:", link)
        print("Link exists:", link.exists())
        print("Link itself exists:", link.is_symlink())
        print("Link target:", os.readlink(link))
        print("Reading link:", link.read_text(encoding="utf-8"))

        print("\nUsing lstat() examines the link itself.")
        print("Using stat() follows the link.")

        print("lstat type:", file_type_name(link.lstat().st_mode))
        print("stat type:", file_type_name(link.stat().st_mode))


def demonstrate_broken_symlink() -> None:
    section("14. Broken Symbolic Links")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        target = root / "missing.txt"
        link = root / "broken-link"

        link.symlink_to(target)

        print("is_symlink():", link.is_symlink())
        print("exists():", link.exists())
        print("lexists():", os.path.lexists(link))

        print(
            "\nA symbolic link can exist as a directory entry while its target "
            "does not exist."
        )


# ============================================================================
# 11. HARD LINKS
# ============================================================================

def demonstrate_hard_links() -> None:
    section("15. Hard Links")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        original = root / "original.txt"
        hard_link = root / "second-name.txt"

        original.write_text("shared inode data\n", encoding="utf-8")
        os.link(original, hard_link)

        first = original.stat()
        second = hard_link.stat()

        print("Original inode:", first.st_ino)
        print("Hard-link inode:", second.st_ino)
        print("Same inode:", first.st_ino == second.st_ino)
        print("Original link count:", first.st_nlink)

        hard_link.write_text("modified through second name\n", encoding="utf-8")
        print("Original content:", original.read_text(encoding="utf-8"))

    print("\nImportant hard-link limitations:")
    print("- Hard links normally cannot cross filesystem boundaries.")
    print("- Directories are normally not hard-linked by ordinary users.")
    print("- A hard link references an inode rather than another pathname.")


# ============================================================================
# 12. LINKS COMPARISON
# ============================================================================

def compare_links() -> None:
    section("16. Symbolic Links vs Hard Links")

    comparisons = [
        ("References", "Path", "Same inode"),
        ("Cross filesystem", "Yes", "No"),
        ("Can point to directory", "Usually yes", "Normally no"),
        ("Broken target possible", "Yes", "No target concept"),
        ("Inode", "Different inode for link", "Same inode"),
        ("Target replacement", "Link can become broken", "Independent name"),
        ("Common use", "Aliases, compatibility paths", "Multiple names for same data"),
    ]

    print(f"{'Property':25} {'Symbolic link':25} {'Hard link':25}")
    print("-" * 78)
    for property_name, symbolic, hard in comparisons:
        print(f"{property_name:25} {symbolic:25} {hard:25}")


# ============================================================================
# 13. DIRECTORY TREE OPERATIONS
# ============================================================================

def demonstrate_directory_operations() -> None:
    section("17. Creating and Navigating Directories")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        project = root / "project"
        source = project / "src"
        tests = project / "tests"

        source.mkdir(parents=True)
        tests.mkdir()

        (source / "main.py").write_text("print('hello')\n", encoding="utf-8")
        (tests / "test_main.py").write_text(
            "assert True\n",
            encoding="utf-8",
        )

        print("Project tree:")
        for path in sorted(project.rglob("*")):
            relative = path.relative_to(project)
            print(
                f"  {relative} "
                f"({'directory' if path.is_dir() else 'file'})"
            )


def demonstrate_globbing() -> None:
    section("18. Pattern Matching with pathlib")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        files = [
            "main.py",
            "test_main.py",
            "README.md",
            "notes.txt",
            "data.csv",
        ]

        for filename in files:
            (root / filename).write_text("", encoding="utf-8")

        print("Python files:")
        for path in root.glob("*.py"):
            print(" ", path.name)

        print("Files beginning with test:")
        for path in root.glob("test*"):
            print(" ", path.name)


# ============================================================================
# 14. FILE READING AND WRITING
# ============================================================================

def demonstrate_file_io() -> None:
    section("19. Reading and Writing Files")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "example.txt"

        path.write_text(
            "Linux\nFilesystem\nPython\n",
            encoding="utf-8",
        )

        print("Full content:")
        print(path.read_text(encoding="utf-8"))

        print("Line-by-line:")
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                print(f"{line_number}: {line.rstrip()}")

        # append mode preserves existing data and writes new data at the end.
        with path.open("a", encoding="utf-8") as file:
            file.write("Appended line\n")

        print("After append:")
        print(path.read_text(encoding="utf-8"))


def demonstrate_binary_io() -> None:
    section("20. Binary Files")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "binary.dat"

        data = bytes([0, 1, 2, 127, 128, 255])

        path.write_bytes(data)
        recovered = path.read_bytes()

        print("Written bytes:", data)
        print("Recovered bytes:", recovered)
        print("Equal:", data == recovered)


# ============================================================================
# 15. SAFE FILE OPERATIONS
# ============================================================================

def demonstrate_safe_file_operations() -> None:
    section("21. Safe File Operations")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        source = root / "source.txt"
        destination = root / "destination.txt"

        source.write_text("important data\n", encoding="utf-8")

        # shutil.copy2 preserves metadata where supported.
        shutil.copy2(source, destination)

        print("Copied:", destination.read_text(encoding="utf-8"))

        renamed = root / "renamed.txt"
        destination.rename(renamed)

        print("Renamed:", renamed.name)

        # unlink removes the directory entry. For a regular file whose link
        # count reaches zero, its storage becomes reclaimable by the filesystem.
        renamed.unlink()

        print("Exists after unlink:", renamed.exists())


# ============================================================================
# 16. ATOMIC REPLACEMENT
# ============================================================================

def demonstrate_atomic_replacement() -> None:
    section("22. Atomic File Replacement")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        target = root / "configuration.txt"
        temporary = root / "configuration.tmp"

        target.write_text("old configuration\n", encoding="utf-8")
        temporary.write_text("new configuration\n", encoding="utf-8")

        # os.replace() replaces the destination atomically at the filesystem
        # namespace level when source and destination are on the same filesystem.
        os.replace(temporary, target)

        print(target.read_text(encoding="utf-8"))

    print(
        "Atomic replacement is useful for reducing the chance that readers "
        "observe a partially written file."
    )


# ============================================================================
# 17. PATH NORMALIZATION
# ============================================================================

def demonstrate_path_normalization() -> None:
    section("23. Path Normalization")

    samples = [
        "/var/log/../tmp/app.log",
        "./project/./src/../README.md",
        "/home/user/../../etc/passwd",
    ]

    for value in samples:
        normalized = os.path.normpath(value)
        print(f"{value:35} -> {normalized}")

    print("\nNormalization simplifies path syntax.")
    print("It does not verify that the resulting path exists.")
    print("It also does not make untrusted paths automatically safe.")


# ============================================================================
# 18. PATH TRAVERSAL SECURITY
# ============================================================================

def safe_path_within_directory(base: pathlib.Path, user_path: str) -> pathlib.Path:
    """
    Resolve a user-supplied relative path and verify it remains inside base.

    This is useful when an application allows users to select files below a
    controlled directory. The check must be designed carefully for symlinks
    and race conditions in security-sensitive applications.
    """
    base_resolved = base.resolve()
    candidate = (base_resolved / user_path).resolve()

    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("Path escapes the permitted directory") from exc

    return candidate


def demonstrate_path_traversal_defense() -> None:
    section("24. Path Traversal and Security")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp) / "uploads"
        root.mkdir()

        allowed = safe_path_within_directory(root, "documents/report.txt")
        print("Allowed path:", allowed)

        dangerous_inputs = [
            "../secret.txt",
            "../../etc/passwd",
            "/etc/passwd",
        ]

        for user_input in dangerous_inputs:
            try:
                result = safe_path_within_directory(root, user_input)
                print("Unexpectedly allowed:", result)
            except ValueError as error:
                print(f"Rejected {user_input!r}: {error}")

    print(
        "\nSecurity-sensitive programs must also consider symlink races, "
        "permissions, mount points, hard links, and time-of-check/time-of-use "
        "conditions."
    )


# ============================================================================
# 19. DIRECTORY TRAVERSAL
# ============================================================================

@dataclass
class FileRecord:
    path: pathlib.Path
    size: int
    is_symlink: bool


def collect_files(root: pathlib.Path) -> list[FileRecord]:
    """Collect regular files without following directory symlinks."""
    records: list[FileRecord] = []

    for current_root, directories, filenames in os.walk(
        root,
        followlinks=False,
    ):
        current_path = pathlib.Path(current_root)

        # Explicitly avoid descending through symlinked directories.
        directories[:] = [
            directory
            for directory in directories
            if not (current_path / directory).is_symlink()
        ]

        for filename in filenames:
            path = current_path / filename

            try:
                metadata = path.stat()
            except OSError:
                # Files can disappear or become inaccessible during traversal.
                continue

            if stat.S_ISREG(metadata.st_mode):
                records.append(
                    FileRecord(
                        path=path,
                        size=metadata.st_size,
                        is_symlink=path.is_symlink(),
                    )
                )

    return records


def demonstrate_recursive_traversal() -> None:
    section("25. Recursive Filesystem Traversal")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        (root / "a").mkdir()
        (root / "b").mkdir()
        (root / "a" / "first.txt").write_text("12345", encoding="utf-8")
        (root / "a" / "second.txt").write_text("123456789", encoding="utf-8")
        (root / "b" / "third.txt").write_text("12", encoding="utf-8")

        records = collect_files(root)

        for record in records:
            print(f"{record.path.relative_to(root)} -> {record.size} bytes")

        print("Total files:", len(records))
        print("Total bytes:", sum(record.size for record in records))


# ============================================================================
# 20. DISK USAGE
# ============================================================================

def demonstrate_disk_usage() -> None:
    section("26. Filesystem and Disk Usage")

    usage = shutil.disk_usage(pathlib.Path.cwd())

    print("Total bytes:", usage.total)
    print("Used bytes:", usage.used)
    print("Free bytes:", usage.free)

    print("\nCommon Linux commands:")
    print("  df -h      filesystem-level capacity")
    print("  du -sh DIR directory-level usage")
    print("  du -ah DIR detailed usage")


# ============================================================================
# 21. INODES
# ============================================================================

def demonstrate_inodes() -> None:
    section("27. Inodes")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        first = root / "first.txt"
        second = root / "second.txt"

        first.write_text("same inode\n", encoding="utf-8")
        os.link(first, second)

        first_stat = first.stat()
        second_stat = second.stat()

        print("First inode:", first_stat.st_ino)
        print("Second inode:", second_stat.st_ino)
        print("Same inode:", first_stat.st_ino == second_stat.st_ino)
        print("Link count:", first_stat.st_nlink)

    print(
        "\nA filesystem can run out of inodes even when it still has free "
        "data-block space."
    )


# ============================================================================
# 22. FILE DESCRIPTORS
# ============================================================================

def demonstrate_file_descriptors() -> None:
    section("28. File Descriptors")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "fd.txt"

        # open() returns a Python file object that owns an operating-system
        # file descriptor.
        with path.open("w", encoding="utf-8") as file:
            print("Python file object:", file)
            print("Operating-system descriptor:", file.fileno())
            file.write("descriptor demonstration\n")

    print("\nStandard POSIX descriptors:")
    print("  0 = stdin")
    print("  1 = stdout")
    print("  2 = stderr")

    print("\nPython examples:")
    print("  open(path)")
    print("  os.open(path, flags)")
    print("  os.read(fd, size)")
    print("  os.write(fd, data)")


# ============================================================================
# 23. OPEN FLAGS
# ============================================================================

def demonstrate_low_level_open() -> None:
    section("29. Low-Level File Descriptors")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "low-level.txt"

        flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC

        fd = os.open(path, flags, 0o600)

        try:
            os.write(fd, b"written using a file descriptor\n")
        finally:
            os.close(fd)

        print(path.read_text(encoding="utf-8"))


# ============================================================================
# 24. MOUNT POINTS
# ============================================================================

def demonstrate_mount_information() -> None:
    section("30. Mount Points and Filesystems")

    print("A Linux system presents filesystems as one unified directory tree.")
    print("A filesystem can be attached at a mount point such as /mnt/data.")
    print()
    print("Python can inspect whether a path is a mount point:")
    print("  os.path.ismount(path)")

    current = pathlib.Path.cwd()
    print("Current directory is mount point:", os.path.ismount(current))
    print("Root is mount point:", os.path.ismount("/"))

    print("\nCommon shell commands:")
    print("  mount")
    print("  findmnt")
    print("  lsblk")
    print("  df -h")
    print("  cat /proc/mounts")


# ============================================================================
# 25. SPECIAL PERMISSIONS
# ============================================================================

def explain_special_bits() -> None:
    section("31. Special Permission Bits")

    print("Set-user-ID (setuid):")
    print("  Can cause an executable to run with the file owner's effective UID.")
    print("  This is security-sensitive and should be used sparingly.")
    print()
    print("Set-group-ID (setgid):")
    print("  On executables it can affect effective group identity.")
    print("  On directories it commonly causes newly created files to inherit")
    print("  the directory's group.")
    print()
    print("Sticky bit:")
    print("  On a shared directory, it restricts deletion/renaming of entries.")
    print("  /tmp commonly uses this behavior.")

    print("\nTypical numeric forms:")
    print("  4755 -> setuid + 755")
    print("  2755 -> setgid + 755")
    print("  1777 -> sticky + 777")


# ============================================================================
# 26. ACCESS CHECKS
# ============================================================================

def demonstrate_access_checks() -> None:
    section("32. Access Checks")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "check.txt"
        path.write_text("access check\n", encoding="utf-8")

        print("Readable:", os.access(path, os.R_OK))
        print("Writable:", os.access(path, os.W_OK))
        print("Executable:", os.access(path, os.X_OK))

    print(
        "\nFor security decisions, os.access() should not generally be used "
        "as a pre-check before an operation. The filesystem state can change "
        "between the check and the actual operation."
    )


# ============================================================================
# 27. ERROR HANDLING
# ============================================================================

def demonstrate_filesystem_errors() -> None:
    section("33. Filesystem Error Handling")

    with tempfile.TemporaryDirectory() as temp:
        missing = pathlib.Path(temp) / "does-not-exist.txt"

        try:
            missing.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            print("FileNotFoundError:", error)

        directory = pathlib.Path(temp) / "directory"
        directory.mkdir()

        try:
            directory.read_text(encoding="utf-8")
        except IsADirectoryError as error:
            print("IsADirectoryError:", error)

    print("\nOther important exceptions:")
    print("  PermissionError")
    print("  FileExistsError")
    print("  NotADirectoryError")
    print("  OSError")
    print("  UnicodeDecodeError")
    print("  ValueError for invalid API arguments")


# ============================================================================
# 28. RACE CONDITIONS
# ============================================================================

def demonstrate_race_condition_concept() -> None:
    section("34. Time-of-Check/Time-of-Use Problems")

    print("Unsafe conceptual pattern:")
    print("  if path.exists():")
    print("      read(path)")
    print()
    print(
        "Another process could replace, delete, or modify the path between "
        "the existence check and the read."
    )
    print()
    print("Safer approach:")
    print("  Attempt the operation directly and handle the resulting exception.")
    print()
    print("For sensitive operations, use OS primitives designed for the desired")
    print("security property, such as directory file descriptors and no-follow")
    print("options where the platform/API supports them.")


# ============================================================================
# 29. SYMLINK SECURITY
# ============================================================================

def demonstrate_symlink_security() -> None:
    section("35. Symbolic Link Security")

    print("A program that writes to a path controlled by an attacker may be")
    print("tricked into writing somewhere unexpected through a symbolic link.")
    print()
    print("Risk-reduction techniques include:")
    print("- Use trusted directories with restrictive permissions.")
    print("- Avoid following untrusted symlinks for security-sensitive actions.")
    print("- Use appropriate open flags such as O_NOFOLLOW where supported.")
    print("- Prefer directory-relative operations using file descriptors.")
    print("- Minimize the time between validation and use.")
    print("- Run services with the minimum required privileges.")


# ============================================================================
# 30. TEMPORARY FILES
# ============================================================================

def demonstrate_secure_temporary_files() -> None:
    section("36. Secure Temporary Files")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        # NamedTemporaryFile and TemporaryDirectory use safer mechanisms than
        # manually generating predictable names.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=root,
            delete=False,
        ) as temporary:
            temporary.write("temporary secret\n")
            temporary_path = pathlib.Path(temporary.name)

        print("Temporary path:", temporary_path)
        print("Content:", temporary_path.read_text(encoding="utf-8"))

        temporary_path.unlink()


# ============================================================================
# 31. ENCODING
# ============================================================================

def demonstrate_encoding() -> None:
    section("37. Text Encoding")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "unicode.txt"

        text = "Linux filesystem: café, résumé, भारत\n"
        path.write_text(text, encoding="utf-8")

        recovered = path.read_text(encoding="utf-8")

        print("Original:", text.rstrip())
        print("Recovered:", recovered.rstrip())
        print("Equal:", text == recovered)

    print(
        "\nExplicitly choosing an encoding makes filesystem text processing "
        "more predictable across systems."
    )


# ============================================================================
# 32. LARGE FILES
# ============================================================================

def demonstrate_streaming_large_files() -> None:
    section("38. Processing Large Files Efficiently")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "large-log.txt"

        with path.open("w", encoding="utf-8") as file:
            for number in range(1000):
                file.write(f"event={number} status=ok\n")

        count = 0

        # Iterating over a file streams lines rather than loading the complete
        # file into memory.
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if "status=ok" in line:
                    count += 1

        print("Matching lines:", count)


# ============================================================================
# 33. PERFORMANCE
# ============================================================================

def explain_performance() -> None:
    section("39. Filesystem Performance")

    print("Important performance factors:")
    print("- Storage device latency and throughput")
    print("- Filesystem metadata operations")
    print("- Directory size and lookup behavior")
    print("- Cache effects")
    print("- Number of system calls")
    print("- Network filesystem latency")
    print("- Small random I/O versus large sequential I/O")
    print("- File descriptor management")
    print("- Sync and durability requirements")

    print("\nUseful principles:")
    print("- Stream large files instead of loading them entirely into RAM.")
    print("- Avoid unnecessary repeated metadata queries.")
    print("- Batch operations when an API allows it.")
    print("- Do not call fsync() indiscriminately because durability has a cost.")
    print("- Measure actual workloads before optimizing.")


# ============================================================================
# 34. DURABILITY
# ============================================================================

def demonstrate_flush_and_fsync() -> None:
    section("40. Flush, fsync, and Durability")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "durability.txt"

        with path.open("w", encoding="utf-8") as file:
            file.write("durability example\n")
            file.flush()

            # flush() transfers Python's buffered data to the operating-system
            # layer. fsync() requests that the OS flush file data and metadata
            # needed for the file to stable storage according to the platform.
            os.fsync(file.fileno())

        print("Data was explicitly flushed and fsynced.")

    print(
        "\nDurability semantics depend on the filesystem, storage hardware, "
        "mount configuration, and operating system."
    )


# ============================================================================
# 35. CURRENT DIRECTORY
# ============================================================================

def demonstrate_current_directory() -> None:
    section("41. Current Working Directory")

    print("Current directory:", os.getcwd())
    print("Python pathlib:", pathlib.Path.cwd())

    print("\nRelative paths are interpreted against the process's current")
    print("working directory, not necessarily the directory containing the script.")


# ============================================================================
# 36. ENVIRONMENT AND HOME
# ============================================================================

def demonstrate_home_and_environment() -> None:
    section("42. Home Directory and Environment")

    print("Home directory:", pathlib.Path.home())
    print("HOME environment variable:", os.environ.get("HOME"))

    print(
        "\nHOME is an environment variable, while Path.home() asks the "
        "operating system for the user's home directory."
    )


# ============================================================================
# 37. DIRECTORY ENTRY VS FILE CONTENT
# ============================================================================

def explain_directory_entries() -> None:
    section("43. Directory Entries vs File Data")

    print("A directory is not simply a container holding file bytes.")
    print()
    print("Conceptually, a directory maps names to filesystem objects.")
    print("An inode describes metadata and points toward the object's data.")
    print()
    print("This distinction explains why:")
    print("- Multiple hard-link names can refer to one inode.")
    print("- Deleting a filename does not necessarily immediately destroy data.")
    print("- A file can remain open after its directory entry is removed.")
    print("- Symbolic links store a path rather than sharing the target inode.")


# ============================================================================
# 38. UNLINKED BUT OPEN FILES
# ============================================================================

def demonstrate_unlinked_open_file() -> None:
    section("44. Open Files After unlink()")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "open.txt"

        with path.open("w+", encoding="utf-8") as file:
            file.write("This file has an open descriptor.\n")
            file.flush()

            path.unlink()

            print("Directory entry exists:", path.exists())
            print("Open descriptor still works.")

            file.seek(0)
            print("Content:", file.read())

    print(
        "\nOn Unix-like systems, the data can remain accessible through an "
        "open file descriptor until the final reference is closed."
    )


# ============================================================================
# 39. FILE NAMING EDGE CASES
# ============================================================================

def demonstrate_filename_edge_cases() -> None:
    section("45. Filename Edge Cases")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        filenames = [
            "normal.txt",
            "file with spaces.txt",
            ".hidden",
            "multiple.dots.txt",
            "file_without_extension",
            "dash-name.txt",
        ]

        for filename in filenames:
            (root / filename).write_text("example\n", encoding="utf-8")

        for path in sorted(root.iterdir()):
            print(
                f"name={path.name!r}, suffix={path.suffix!r}, "
                f"hidden={path.name.startswith('.')}"
            )

    print(
        "\nShell quoting rules matter when filenames contain spaces, wildcard "
        "characters, newlines, or other special characters."
    )


# ============================================================================
# 40. HIDDEN FILES
# ============================================================================

def explain_hidden_files() -> None:
    section("46. Hidden Files")

    print(
        "Linux does not require a special filesystem type for hidden files."
    )
    print("A common convention is that a filename beginning with '.' is hidden.")
    print()
    print("Examples:")
    print("  ~/.bashrc")
    print("  ~/.config/")
    print("  .git/")
    print()
    print("The hidden status is primarily a naming convention used by tools.")


# ============================================================================
# 41. CASE SENSITIVITY
# ============================================================================

def demonstrate_case_sensitivity() -> None:
    section("47. Case Sensitivity")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        lower = root / "file.txt"
        upper = root / "File.txt"

        lower.write_text("lower\n", encoding="utf-8")
        upper.write_text("upper\n", encoding="utf-8")

        print("Both names exist:", lower.exists() and upper.exists())
        print("file.txt content:", lower.read_text(encoding="utf-8").strip())
        print("File.txt content:", upper.read_text(encoding="utf-8").strip())

    print(
        "\nTypical Linux filesystems are case-sensitive, although filesystem "
        "behavior can vary with configuration and filesystem type."
    )


# ============================================================================
# 42. ROOT USER
# ============================================================================

def explain_root() -> None:
    section("48. The Root User")

    print("root is the traditional Unix/Linux superuser account.")
    print()
    print("Root-level privileges can bypass many normal permission checks.")
    print("This makes accidental root operations especially dangerous.")
    print()
    print("Best practice:")
    print("- Use ordinary accounts for normal work.")
    print("- Elevate privileges only for required administrative actions.")
    print("- Verify paths carefully before destructive operations.")
    print("- Avoid scripts that unnecessarily require root.")


# ============================================================================
# 43. COMMON SHELL COMMANDS
# ============================================================================

def list_common_commands() -> None:
    section("49. Common Linux Filesystem Commands")

    commands = {
        "pwd": "Print current working directory.",
        "ls": "List directory entries.",
        "ls -la": "List entries including hidden files with detailed metadata.",
        "cd": "Change current working directory.",
        "mkdir": "Create directories.",
        "touch": "Create an empty file or update timestamps.",
        "cp": "Copy files/directories.",
        "mv": "Move or rename files/directories.",
        "rm": "Remove directory entries.",
        "ln": "Create links.",
        "chmod": "Change permission bits.",
        "chown": "Change ownership.",
        "chgrp": "Change group ownership.",
        "stat": "Display detailed file metadata.",
        "find": "Search the filesystem tree.",
        "du": "Estimate file/directory space usage.",
        "df": "Display filesystem free/used space.",
        "file": "Identify file type from content/metadata.",
        "readlink": "Inspect symbolic-link targets.",
        "realpath": "Resolve a path to a canonical form.",
    }

    for command, purpose in commands.items():
        print(f"{command:12} {purpose}")


# ============================================================================
# 44. PERMISSION CALCULATOR
# ============================================================================

def symbolic_to_numeric(symbolic: str) -> int:
    """
    Convert nine permission characters such as rwxr-xr-- to an octal value.

    The input must contain exactly nine characters using r, w, x, or -.
    """
    if len(symbolic) != 9:
        raise ValueError("Expected exactly nine permission characters")

    values = 0

    groups = (
        symbolic[0:3],
        symbolic[3:6],
        symbolic[6:9],
    )

    for index, group in enumerate(groups):
        digit = 0

        if group[0] == "r":
            digit += 4
        elif group[0] != "-":
            raise ValueError("Invalid read permission")

        if group[1] == "w":
            digit += 2
        elif group[1] != "-":
            raise ValueError("Invalid write permission")

        if group[2] == "x":
            digit += 1
        elif group[2] != "-":
            raise ValueError("Invalid execute permission")

        values += digit * (100 ** (2 - index))

    return values


def demonstrate_permission_calculator() -> None:
    section("50. Permission Conversion")

    examples = [
        "rwxr-xr-x",
        "rw-r--r--",
        "rw-------",
        "rwxr-x---",
    ]

    for symbolic in examples:
        numeric = symbolic_to_numeric(symbolic)
        print(f"{symbolic} -> {numeric:03d}")


# ============================================================================
# 45. FILE SEARCH BY SIZE
# ============================================================================

def find_files_larger_than(
    root: pathlib.Path,
    minimum_size: int,
) -> Iterable[tuple[pathlib.Path, int]]:
    """Yield regular files at least minimum_size bytes."""
    for current_root, directories, filenames in os.walk(
        root,
        followlinks=False,
    ):
        current_path = pathlib.Path(current_root)

        directories[:] = [
            name
            for name in directories
            if not (current_path / name).is_symlink()
        ]

        for filename in filenames:
            path = current_path / filename

            try:
                metadata = path.stat()
            except OSError:
                continue

            if stat.S_ISREG(metadata.st_mode) and metadata.st_size >= minimum_size:
                yield path, metadata.st_size


def demonstrate_file_search() -> None:
    section("51. Searching Files by Size")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        (root / "small.txt").write_text("abc", encoding="utf-8")
        (root / "large.txt").write_text("x" * 100, encoding="utf-8")
        (root / "another-large.txt").write_text("y" * 150, encoding="utf-8")

        for path, size in find_files_larger_than(root, 50):
            print(path.name, "->", size, "bytes")


# ============================================================================
# 46. CHECKSUMS
# ============================================================================

def demonstrate_file_checksum() -> None:
    section("52. File Integrity and Hashes")

    import hashlib

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "data.txt"
        path.write_text("integrity example\n", encoding="utf-8")

        digest = hashlib.sha256()

        # Streaming the file avoids loading a potentially large file into memory.
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(64 * 1024), b""):
                digest.update(chunk)

        print("SHA-256:", digest.hexdigest())

    print(
        "\nCryptographic hashes can detect accidental or malicious changes, "
        "but a hash alone does not prove authenticity."
    )


# ============================================================================
# 47. FILESYSTEM TIMESTAMPS
# ============================================================================

def demonstrate_timestamps() -> None:
    section("53. Filesystem Timestamps")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "timestamps.txt"
        path.write_text("timestamp example\n", encoding="utf-8")

        metadata = path.stat()

        print("atime:", datetime.fromtimestamp(metadata.st_atime))
        print("mtime:", datetime.fromtimestamp(metadata.st_mtime))
        print("ctime:", datetime.fromtimestamp(metadata.st_ctime))

        new_mtime = metadata.st_mtime - 3600
        os.utime(path, (metadata.st_atime, new_mtime))

        changed = path.stat()
        print("Updated mtime:", datetime.fromtimestamp(changed.st_mtime))

    print(
        "\nTimestamp semantics and available creation-time fields vary by "
        "filesystem and operating system."
    )


# ============================================================================
# 48. DIRECTORY ORDER
# ============================================================================

def demonstrate_directory_order() -> None:
    section("54. Directory Listing Order")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        for name in ["z.txt", "a.txt", "m.txt"]:
            (root / name).write_text("", encoding="utf-8")

        raw = list(root.iterdir())
        sorted_entries = sorted(root.iterdir())

        print("Filesystem/API iteration order:")
        for path in raw:
            print(" ", path.name)

        print("\nExplicitly sorted order:")
        for path in sorted_entries:
            print(" ", path.name)

    print(
        "\nPrograms should not assume directory iteration order unless they "
        "explicitly sort entries."
    )


# ============================================================================
# 49. PERMISSIONS AND SYMLINKS
# ============================================================================

def demonstrate_lstat_vs_stat() -> None:
    section("55. stat() vs lstat()")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        target = root / "target.txt"
        link = root / "link.txt"

        target.write_text("target\n", encoding="utf-8")
        link.symlink_to(target)

        followed = link.stat()
        not_followed = link.lstat()

        print("stat() mode:", stat.filemode(followed.st_mode))
        print("lstat() mode:", stat.filemode(not_followed.st_mode))
        print("stat() follows link:", stat.S_ISREG(followed.st_mode))
        print("lstat() sees link:", stat.S_ISLNK(not_followed.st_mode))


# ============================================================================
# 50. DIRECTORY FD CONCEPT
# ============================================================================

def explain_directory_file_descriptors() -> None:
    section("56. Directory File Descriptors")

    print("Many POSIX APIs can operate relative to an already opened directory.")
    print()
    print("Conceptual pattern:")
    print("  open trusted directory")
    print("  perform operations relative to that directory")
    print()
    print("This can reduce ambiguity caused by changing working directories and")
    print("can support stronger security designs when combined with suitable")
    print("no-follow and ownership checks.")
    print()
    print(
        "Python exposes several dir_fd parameters through os functions on "
        "platforms that support them."
    )


# ============================================================================
# 51. FILESYSTEM BOUNDARIES
# ============================================================================

def demonstrate_filesystem_boundary() -> None:
    section("57. Filesystem Boundaries")

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "example.txt"
        path.write_text("filesystem example\n", encoding="utf-8")

        metadata = path.stat()
        print("Device identifier:", metadata.st_dev)
        print("Inode:", metadata.st_ino)

    print(
        "\nThe device identifier helps distinguish objects located on different "
        "mounted filesystems."
    )


# ============================================================================
# 52. UNIX SOCKET AND PIPE CONCEPTS
# ============================================================================

def explain_non_regular_objects() -> None:
    section("58. Non-Regular Filesystem Objects")

    print("Linux exposes more than ordinary files:")
    print("- Device nodes provide interfaces to devices.")
    print("- FIFOs provide named inter-process communication channels.")
    print("- Unix domain sockets provide local process communication.")
    print("- /proc and /sys expose kernel-managed virtual information.")
    print()
    print(
        "Applications should not assume every directory entry is a regular "
        "file that can safely be opened and read as ordinary text."
    )


# ============================================================================
# 53. PRODUCTION FILE HANDLING
# ============================================================================

def explain_production_practices() -> None:
    section("59. Production Filesystem Practices")

    practices = [
        "Use pathlib for clear path manipulation.",
        "Use explicit text encodings.",
        "Handle FileNotFoundError and PermissionError explicitly when useful.",
        "Do not trust user-provided paths.",
        "Use least privilege.",
        "Avoid predictable temporary filenames.",
        "Do not assume directory iteration order.",
        "Do not assume every filesystem supports identical semantics.",
        "Use streaming I/O for large files.",
        "Use atomic replacement for appropriate configuration/state updates.",
        "Consider durability requirements before using fsync.",
        "Avoid following untrusted symbolic links in sensitive operations.",
        "Log failures without exposing secrets.",
        "Test behavior under permission failures and missing files.",
        "Consider network filesystems and concurrent modifications.",
    ]

    for practice in practices:
        print("•", practice)


# ============================================================================
# 54. COMMON MISTAKES
# ============================================================================

def explain_common_mistakes() -> None:
    section("60. Common Linux Filesystem Mistakes")

    mistakes = {
        "Using relative paths without understanding cwd":
            "The same path can refer to different objects from different directories.",
        "Assuming chmod changes ownership":
            "chmod changes permission bits; ownership requires chown/chgrp.",
        "Treating directory x as a normal executable bit":
            "Directory x means traversal/search permission.",
        "Assuming exists() guarantees later access":
            "Filesystem state can change between operations.",
        "Following untrusted symlinks":
            "A path may resolve somewhere outside the intended directory.",
        "Using predictable temporary filenames":
            "Attackers may race or pre-create names.",
        "Loading huge files with read_text()":
            "Memory usage can become excessive.",
        "Assuming every file is regular":
            "Linux directories can contain links, sockets, devices, and FIFOs.",
        "Confusing ctime with creation time":
            "On Linux, ctime is generally metadata change time.",
        "Deleting a filename and assuming immediate data destruction":
            "Open descriptors and additional hard links can keep data accessible.",
        "Using chmod 777 as a universal fix":
            "It can create unnecessary security exposure.",
    }

    for mistake, explanation in mistakes.items():
        print(f"{mistake}\n  {explanation}\n")


# ============================================================================
# 55. EDGE CASES
# ============================================================================

def demonstrate_edge_cases() -> None:
    section("61. Important Filesystem Edge Cases")

    cases = [
        "A symbolic link can point to a nonexistent target.",
        "A file can be deleted while still open by a process.",
        "Two names can refer to one inode through hard links.",
        "A path can cross mount points.",
        "A directory can be readable but not traversable.",
        "A file can disappear between directory listing and stat().",
        "A permission check can become stale immediately.",
        "Filenames can contain spaces and many characters that are special to shells.",
        "Filesystem timestamps may have filesystem-specific precision and semantics.",
        "Network filesystems can have different consistency and locking behavior.",
        "A filesystem can exhaust inodes before exhausting data capacity.",
        "Case sensitivity is filesystem-dependent.",
    ]

    for case in cases:
        print("•", case)


# ============================================================================
# 56. INTEGRATED FILESYSTEM AUDIT
# ============================================================================

def audit_path(path: pathlib.Path) -> dict[str, object]:
    """Return useful metadata for a path without following symlinks."""
    metadata = path.lstat()
    mode = metadata.st_mode

    return {
        "path": str(path),
        "type": file_type_name(mode),
        "permissions": permission_string(mode),
        "numeric_mode": oct(stat.S_IMODE(mode)),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "inode": metadata.st_ino,
        "device": metadata.st_dev,
        "links": metadata.st_nlink,
        "size": metadata.st_size,
        "is_symlink": stat.S_ISLNK(mode),
    }


def demonstrate_integrated_audit() -> None:
    section("62. Integrated Filesystem Audit")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        file_path = root / "report.txt"
        directory = root / "documents"

        file_path.write_text("audit example\n", encoding="utf-8")
        directory.mkdir()

        link = root / "report-link"
        link.symlink_to(file_path)

        for path in [file_path, directory, link]:
            print(audit_path(path))


# ============================================================================
# 57. MINI FILE MANAGER
# ============================================================================

class MiniFileManager:
    """
    Small educational abstraction around filesystem operations.

    It demonstrates validation, directory creation, reading, writing,
    listing, and controlled deletion without pretending to be a full
    production file-management service.
    """

    def __init__(self, root: pathlib.Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def safe_path(self, relative_path: str) -> pathlib.Path:
        return safe_path_within_directory(self.root, relative_path)

    def write_text(self, relative_path: str, content: str) -> pathlib.Path:
        path = self.safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_text(self, relative_path: str) -> str:
        path = self.safe_path(relative_path)
        return path.read_text(encoding="utf-8")

    def list_files(self) -> list[pathlib.Path]:
        return sorted(
            path.relative_to(self.root)
            for path in self.root.rglob("*")
            if path.is_file() and not path.is_symlink()
        )

    def delete_file(self, relative_path: str) -> None:
        path = self.safe_path(relative_path)

        if not path.is_file() or path.is_symlink():
            raise ValueError("Target is not a regular file")

        path.unlink()


def demonstrate_mini_file_manager() -> None:
    section("63. Integrated Mini File Manager")

    with tempfile.TemporaryDirectory() as temp:
        manager = MiniFileManager(pathlib.Path(temp))

        manager.write_text("notes/linux.txt", "Filesystem study notes\n")
        manager.write_text("notes/permissions.txt", "chmod and ownership\n")

        print("Files:")
        for path in manager.list_files():
            print(" ", path)

        print("Read:", manager.read_text("notes/linux.txt").strip())

        try:
            manager.read_text("../outside.txt")
        except ValueError as error:
            print("Traversal rejected:", error)

        manager.delete_file("notes/permissions.txt")
        print("After deletion:", manager.list_files())


# ============================================================================
# 58. TESTING
# ============================================================================

def run_filesystem_tests() -> None:
    section("64. Basic Filesystem Tests")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        file_path = root / "test.txt"
        file_path.write_text("hello", encoding="utf-8")

        assert file_path.exists()
        assert file_path.is_file()
        assert file_path.read_text(encoding="utf-8") == "hello"

        directory = root / "directory"
        directory.mkdir()

        assert directory.exists()
        assert directory.is_dir()

        link = root / "link"
        link.symlink_to(file_path)

        assert link.is_symlink()
        assert link.read_text(encoding="utf-8") == "hello"

        hard = root / "hard"
        os.link(file_path, hard)

        assert file_path.stat().st_ino == hard.stat().st_ino

        print("All filesystem assertions passed.")


# ============================================================================
# 59. KNOWLEDGE CHECK
# ============================================================================

def knowledge_check() -> None:
    section("65. Knowledge Check")

    questions = [
        (
            "1. What character normally represents a regular file in ls -l?",
            "-",
        ),
        (
            "2. What does x mean on a directory?",
            "Permission to traverse/search the directory.",
        ),
        (
            "3. What does 755 mean?",
            "rwx for owner, r-x for group, r-x for others.",
        ),
        (
            "4. What does a symbolic link store?",
            "A path to another filesystem object.",
        ),
        (
            "5. What does a hard link share with another hard-link name?",
            "The same inode.",
        ),
        (
            "6. What is /etc primarily used for?",
            "System-wide configuration.",
        ),
        (
            "7. Why is chmod 777 usually discouraged?",
            "It grants broad permissions and can expose data or operations.",
        ),
        (
            "8. Why can exists() be unsafe as a security pre-check?",
            "The filesystem can change between checking and using the path.",
        ),
        (
            "9. What does inode exhaustion mean?",
            "The filesystem has no available inode structures for new objects.",
        ),
        (
            "10. Why use streaming I/O for large files?",
            "It avoids loading the entire file into memory.",
        ),
    ]

    for question, answer in questions:
        print(question)
        print("Answer:", answer)
        print()


# ============================================================================
# 60. FINAL SYSTEMATIC DEMONSTRATION
# ============================================================================

def run_integrated_demo() -> None:
    section("66. End-to-End Filesystem Demonstration")

    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        # Build a miniature Linux-like project tree.
        project = root / "project"
        source = project / "src"
        config = project / "config"
        logs = project / "logs"

        for directory in [source, config, logs]:
            directory.mkdir(parents=True)

        application = source / "application.py"
        settings = config / "settings.conf"
        log_file = logs / "application.log"

        application.write_text(
            "print('filesystem application')\n",
            encoding="utf-8",
        )
        settings.write_text(
            "environment=development\n",
            encoding="utf-8",
        )
        log_file.write_text(
            "INFO application started\n",
            encoding="utf-8",
        )

        application.chmod(0o750)
        settings.chmod(0o640)
        log_file.chmod(0o640)

        latest = project / "latest.log"
        latest.symlink_to(log_file)

        print("Project:", project)
        print()
        print("Filesystem tree:")

        for path in sorted(project.rglob("*")):
            relative = path.relative_to(project)

            if path.is_symlink():
                description = f"symlink -> {os.readlink(path)}"
            elif path.is_dir():
                description = "directory"
            else:
                description = "regular file"

            print(f"  {relative} [{description}]")

        print("\nMetadata:")
        for path in [application, settings, log_file, latest]:
            print(audit_path(path))

        print("\nApplication content:")
        print(application.read_text(encoding="utf-8"))

        print("Latest log through symbolic link:")
        print(latest.read_text(encoding="utf-8"))

    print(
        "\nThe temporary tree has now been removed automatically. This "
        "illustrates why temporary directories are useful for isolated tests."
    )


# ============================================================================
# 61. MAIN PROGRAM
# ============================================================================

def main() -> None:
    """Run the complete Linux filesystem study program."""
    explain_basic_terms()
    demonstrate_paths()
    demonstrate_pathlib()
    explain_filesystem_hierarchy()
    demonstrate_file_types()
    demonstrate_metadata()
    explain_permissions()
    demonstrate_permission_bits()
    demonstrate_chmod()
    explain_directory_permissions()
    demonstrate_ownership()
    demonstrate_umask()
    demonstrate_symbolic_links()
    demonstrate_broken_symlink()
    demonstrate_hard_links()
    compare_links()
    demonstrate_directory_operations()
    demonstrate_globbing()
    demonstrate_file_io()
    demonstrate_binary_io()
    demonstrate_safe_file_operations()
    demonstrate_atomic_replacement()
    demonstrate_path_normalization()
    demonstrate_path_traversal_defense()
    demonstrate_recursive_traversal()
    demonstrate_disk_usage()
    demonstrate_inodes()
    demonstrate_file_descriptors()
    demonstrate_low_level_open()
    demonstrate_mount_information()
    explain_special_bits()
    demonstrate_access_checks()
    demonstrate_filesystem_errors()
    demonstrate_race_condition_concept()
    demonstrate_symlink_security()
    demonstrate_secure_temporary_files()
    demonstrate_encoding()
    demonstrate_streaming_large_files()
    explain_performance()
    demonstrate_flush_and_fsync()
    demonstrate_current_directory()
    demonstrate_home_and_environment()
    explain_directory_entries()
    demonstrate_unlinked_open_file()
    demonstrate_filename_edge_cases()
    explain_hidden_files()
    demonstrate_case_sensitivity()
    explain_root()
    list_common_commands()
    demonstrate_permission_calculator()
    demonstrate_file_search()
    demonstrate_file_checksum()
    demonstrate_timestamps()
    demonstrate_directory_order()
    demonstrate_lstat_vs_stat()
    explain_directory_file_descriptors()
    demonstrate_filesystem_boundary()
    explain_non_regular_objects()
    explain_production_practices()
    explain_common_mistakes()
    demonstrate_edge_cases()
    demonstrate_integrated_audit()
    demonstrate_mini_file_manager()
    run_filesystem_tests()
    knowledge_check()
    run_integrated_demo()

    section("Study Program Complete")
    print("The Linux filesystem concepts and executable demonstrations are complete.")


if __name__ == "__main__":
    main()
