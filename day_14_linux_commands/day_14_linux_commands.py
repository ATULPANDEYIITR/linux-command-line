#!/usr/bin/env python3
"""
Linux Commands: Beginner-to-Advanced Practice Lab

This standalone study script teaches practical Linux file-system commands:
navigation, file creation, copying, moving, deleting, searching, inspecting,
permissions, links, archives, pipelines, redirection, command composition,
safe deletion, troubleshooting, and production-oriented practices.

The script creates a temporary practice directory so demonstrations do not
modify the user's real files. Linux commands are executed when available.
Python equivalents are also demonstrated because they make the underlying
file operations easier to understand.

Recommended environment:
    Linux, macOS, WSL, or another POSIX-compatible environment.

Run:
    python3 linux_commands_practice.py
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def title(text: str) -> None:
    """Print a major lesson heading."""
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def section(text: str) -> None:
    """Print a smaller lesson heading."""
    print("\n" + "-" * 78)
    print(text)
    print("-" * 78)


def explain(command: str, description: str) -> None:
    """Print a command and its explanation."""
    print(f"\n$ {command}")
    print(f"  {description}")


def show_output(output: str) -> None:
    """Print command output in a readable form."""
    if output:
        print(output.rstrip())


# ---------------------------------------------------------------------------
# Linux command execution
# ---------------------------------------------------------------------------

def command_exists(command: str) -> bool:
    """Return True when a command is available in PATH."""
    return shutil.which(command) is not None


def run_command(
    command: str,
    cwd: Path | None = None,
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """
    Execute a shell command safely without invoking a shell.

    Splitting is intentionally simple because this teaching function receives
    already-tokenized commands. Commands containing shell syntax such as pipes
    or redirections are demonstrated separately with subprocess.run(...,
    shell=True) only when that syntax itself is the lesson.
    """
    import shlex

    arguments = shlex.split(command)

    if not arguments:
        raise ValueError("Command cannot be empty.")

    if not command_exists(arguments[0]):
        raise FileNotFoundError(
            f"Linux command '{arguments[0]}' is not available on this system."
        )

    return subprocess.run(
        arguments,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def demonstrate_command(
    command: str,
    description: str,
    cwd: Path | None = None,
) -> None:
    """Explain and, when possible, execute a command."""
    explain(command, description)

    first_word = command.split()[0]

    if not command_exists(first_word):
        print(f"  [Skipped: '{first_word}' is not installed or not available.]")
        return

    try:
        result = run_command(command, cwd=cwd)
        if result.stdout:
            show_output(result.stdout)
        if result.stderr:
            print(f"  stderr: {result.stderr.rstrip()}")
        print(f"  exit status: {result.returncode}")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"  [Command could not be demonstrated: {exc}]")


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def lesson_01_linux_and_the_file_system() -> None:
    title("1. Linux commands and the file system")

    print(
        """
Linux commands are small programs that perform operations such as navigating
directories, creating files, inspecting information, searching for files, and
transforming text.

A Linux path has two important forms:

  Absolute path:
      /home/user/documents/report.txt

  Relative path:
      documents/report.txt

An absolute path starts at the root directory, written as /.
A relative path starts from the current working directory.

Important path symbols:

  /     root directory or path separator
  .     current directory
  ..    parent directory
  ~     current user's home directory
  -     commonly introduces command options

Linux is case-sensitive. The names report.txt, Report.txt, and REPORT.TXT
represent different directory entries.

Directories form a tree:

  /
  ├── home
  │   └── user
  │       └── documents
  ├── etc
  ├── var
  └── tmp
"""
    )

    demonstrate_command(
        "pwd",
        "Print the absolute path of the current working directory.",
    )

    demonstrate_command(
        "ls",
        "List directory entries.",
    )

    demonstrate_command(
        "ls -l",
        "Show a long listing containing permissions, ownership, size, and timestamps.",
    )

    demonstrate_command(
        "ls -la",
        "Include hidden entries and show detailed metadata.",
    )


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def lesson_02_navigation(workspace: Path) -> None:
    title("2. Navigation commands")

    print(
        """
The core navigation commands are:

  pwd     show the current directory
  ls      list directory contents
  cd      change directory

The shell remembers a current working directory. Relative paths are resolved
from that location.

Examples:

  cd /tmp
  cd ..
  cd .
  cd ~
  cd -

The command 'cd -' changes to the previous working directory in interactive
shells.

Options modify command behavior. For example, 'ls -l' asks ls for a long
format. Many commands use '--help' to display their built-in usage
information.
"""
    )

    demonstrate_command(
        f"pwd",
        "Display the current location before starting file operations.",
        workspace,
    )

    demonstrate_command(
        "ls -la",
        "Inspect the practice directory, including hidden entries.",
        workspace,
    )

    demonstrate_command(
        "ls -lh",
        "Display file sizes in a human-readable format.",
        workspace,
    )

    demonstrate_command(
        "find . -maxdepth 2 -type d",
        "List directories below the current location. find uses . as the starting point.",
        workspace,
    )


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------

def lesson_03_creation(workspace: Path) -> None:
    title("3. Creating files and directories")

    print(
        """
Directories are created with mkdir.

Files can be created with touch, but touch primarily updates timestamps. It
creates an empty file when the named file does not exist.

Examples:

  mkdir projects
  mkdir -p projects/linux/commands
  touch notes.txt

The -p option allows mkdir to create missing parent directories and avoids an
error when the target directory already exists.

A shell can also create file content with redirection:

  printf 'first line\\n' > notes.txt
  printf 'second line\\n' >> notes.txt

The single > operator replaces the destination file.
The double >> operator appends to the destination.

Be careful with > because it can destroy existing content.
"""
    )

    demonstrate_command(
        "mkdir command_lab",
        "Create a directory for a command practice exercise.",
        workspace,
    )

    demonstrate_command(
        "mkdir -p command_lab/data/raw",
        "Create multiple missing parent directories in one operation.",
        workspace,
    )

    demonstrate_command(
        "touch command_lab/notes.txt",
        "Create an empty file.",
        workspace,
    )

    demonstrate_command(
        "ls -l command_lab",
        "Verify the created directory and file.",
        workspace,
    )

    # Demonstrate shell redirection safely inside the temporary workspace.
    if command_exists("printf"):
        command = "printf 'Linux command practice\\n' > command_lab/notes.txt"
        print(f"\n$ {command}")
        result = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            text=True,
            capture_output=True,
        )
        print(f"  exit status: {result.returncode}")

    demonstrate_command(
        "cat command_lab/notes.txt",
        "Read the text created through shell redirection.",
        workspace,
    )

    # Python equivalent: the same conceptual operation without a shell.
    python_file = workspace / "command_lab" / "python_notes.txt"
    python_file.write_text(
        "Python can create files without invoking a shell.\n",
        encoding="utf-8",
    )

    print(
        "\nPython equivalent:\n"
        f"  Path.write_text(...) created {python_file.name}\n"
        "  This avoids shell quoting problems when Python itself is the application."
    )


# ---------------------------------------------------------------------------
# Reading and inspecting
# ---------------------------------------------------------------------------

def lesson_04_inspection(workspace: Path) -> None:
    title("4. Inspecting files and directories")

    print(
        """
Several commands inspect files without changing them.

  cat       print an entire file
  less      interactively view a file
  head      display the beginning
  tail      display the end
  wc        count lines, words, and bytes
  file      identify the type of a file
  stat      display detailed file metadata
  du        estimate disk usage
  df        show file-system space

For large files, 'less' is generally preferable to cat because cat attempts
to print the entire file immediately.

tail -f is commonly used for monitoring a growing log file:

  tail -f application.log

head and tail support line counts:

  head -n 20 application.log
  tail -n 50 application.log

wc supports multiple useful counts:

  wc -l file.txt
  wc -w file.txt
  wc -c file.txt
"""
    )

    test_file = workspace / "inspection.txt"
    test_file.write_text(
        "\n".join(
            [
                "Linux file inspection",
                "Navigation uses pwd and cd.",
                "Creation uses mkdir and touch.",
                "Copying uses cp.",
                "Moving and renaming use mv.",
                "Deletion uses rm.",
                "Searching uses find and grep.",
                "Inspection uses cat, head, tail, stat, and file.",
                "Permissions use chmod.",
                "Ownership uses chown and chgrp.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    commands = [
        ("cat inspection.txt", "Print the complete file."),
        ("head -n 3 inspection.txt", "Print the first three lines."),
        ("tail -n 3 inspection.txt", "Print the last three lines."),
        ("wc inspection.txt", "Show line, word, and byte counts."),
        ("wc -l inspection.txt", "Count lines."),
        ("file inspection.txt", "Identify the file type."),
        ("stat inspection.txt", "Show detailed metadata."),
        ("du -h inspection.txt", "Show approximate disk usage in human-readable form."),
    ]

    for command, description in commands:
        demonstrate_command(command, description, workspace)

    demonstrate_command(
        "df -h .",
        "Show free and used space for the file system containing the current directory.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Copying
# ---------------------------------------------------------------------------

def lesson_05_copying(workspace: Path) -> None:
    title("5. Copying files and directories")

    print(
        """
cp copies files and directories.

Common forms:

  cp source.txt destination.txt
  cp source.txt directory/
  cp -r source_directory destination_directory

The -r option means recursive. It is required when copying directory trees
with the traditional cp interface.

The -i option asks before overwriting an existing destination:

  cp -i source.txt destination.txt

The -n option commonly prevents overwriting an existing destination:

  cp -n source.txt destination.txt

Exact option behavior can vary slightly across implementations, so
'cp --help' and the system manual should be treated as authoritative.

A useful safety habit is to inspect the destination before copying into it.
"""
    )

    source = workspace / "source.txt"
    source.write_text("Original source content.\n", encoding="utf-8")

    demonstrate_command(
        "cp source.txt source_backup.txt",
        "Copy one file to another file.",
        workspace,
    )

    demonstrate_command(
        "mkdir -p copies",
        "Create a destination directory.",
        workspace,
    )

    demonstrate_command(
        "cp source.txt copies/",
        "Copy a file into an existing directory.",
        workspace,
    )

    demonstrate_command(
        "cp -r command_lab copies/command_lab_copy",
        "Recursively copy a directory tree.",
        workspace,
    )

    demonstrate_command(
        "find copies -maxdepth 3 -print",
        "Verify the copied files and directories.",
        workspace,
    )

    # Python equivalent to clarify the conceptual model.
    python_copy = workspace / "python_copy.txt"
    shutil.copy2(source, python_copy)

    print(
        "\nPython equivalent:\n"
        f"  shutil.copy2('{source.name}', '{python_copy.name}')\n"
        "  copy2 preserves important metadata such as modification time."
    )


# ---------------------------------------------------------------------------
# Moving and renaming
# ---------------------------------------------------------------------------

def lesson_06_moving(workspace: Path) -> None:
    title("6. Moving and renaming")

    print(
        """
mv has two closely related uses.

Renaming:

  mv old_name.txt new_name.txt

Moving:

  mv report.txt documents/

Moving into another directory changes the file's path without necessarily
changing its contents.

Moving can also overwrite a destination depending on options and the system.
Safer interactive behavior can be requested with:

  mv -i source destination

When the source and destination are on different file systems, an apparent
move can require a copy followed by removal rather than a simple metadata
operation. This matters for very large files and special file systems.
"""
    )

    rename_source = workspace / "rename_me.txt"
    rename_source.write_text("This file will be renamed.\n", encoding="utf-8")

    demonstrate_command(
        "mv rename_me.txt renamed.txt",
        "Rename a file within the same directory.",
        workspace,
    )

    demonstrate_command(
        "mkdir -p moved",
        "Create a target directory.",
        workspace,
    )

    demonstrate_command(
        "mv renamed.txt moved/",
        "Move the renamed file into another directory.",
        workspace,
    )

    demonstrate_command(
        "find moved -maxdepth 1 -type f -print",
        "Verify the final location.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Deleting
# ---------------------------------------------------------------------------

def lesson_07_deletion(workspace: Path) -> None:
    title("7. Deleting files and directories")

    print(
        """
rm removes directory entries.

Common forms:

  rm file.txt
  rm -i file.txt
  rm -r directory/
  rm -rf directory/

The -r option recursively removes a directory tree.
The -f option forces removal without interactive confirmation in common
implementations.

The combination rm -rf is powerful and dangerous. A mistyped path can remove
a large amount of data. It should never be treated like a recycle-bin
operation.

Safer workflow:

  1. Print the target.
  2. Inspect the target with ls or find.
  3. Use rm -i when appropriate.
  4. Avoid unnecessary root privileges.
  5. Use an absolute path only when you are certain it is correct.
  6. Never execute destructive commands copied from an untrusted source
     without understanding them.

A trailing slash can also communicate that a path is intended to be a
directory, but it does not make an unsafe command safe.
"""
    )

    removable = workspace / "delete_me.txt"
    removable.write_text("Temporary content.\n", encoding="utf-8")

    demonstrate_command(
        "ls -l delete_me.txt",
        "Inspect the file before deleting it.",
        workspace,
    )

    demonstrate_command(
        "rm delete_me.txt",
        "Delete a single file after verifying its target.",
        workspace,
    )

    removable_dir = workspace / "temporary_directory"
    removable_dir.mkdir()
    (removable_dir / "one.txt").write_text("one\n", encoding="utf-8")
    (removable_dir / "two.txt").write_text("two\n", encoding="utf-8")

    demonstrate_command(
        "find temporary_directory -print",
        "Inspect the directory tree before recursive deletion.",
        workspace,
    )

    demonstrate_command(
        "rm -r temporary_directory",
        "Recursively remove the demonstration directory.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Searching
# ---------------------------------------------------------------------------

def lesson_08_searching(workspace: Path) -> None:
    title("8. Searching for files and text")

    print(
        """
find searches directory trees based on properties such as:

  -name
  -type
  -size
  -mtime
  -user
  -perm

Examples:

  find . -name '*.txt'
  find . -type f
  find . -type d
  find . -type f -size +1M
  find . -type f -mtime -7

The expression '*.txt' is quoted so the shell does not expand the wildcard
before find receives it.

grep searches text rather than file-system structure.

Examples:

  grep 'error' application.log
  grep -n 'error' application.log
  grep -i 'error' application.log
  grep -r 'error' logs/

Important grep options:

  -n    show line numbers
  -i    ignore case
  -r    recursively search directories
  -v    select lines that do not match
  -E    use extended regular expressions

The commands solve different problems:

  find -> Where is the file?
  grep -> Which file content contains this text?
"""
    )

    search_root = workspace / "search_lab"
    search_root.mkdir()
    (search_root / "app.log").write_text(
        "INFO server started\n"
        "WARNING cache is nearly full\n"
        "ERROR database connection failed\n"
        "INFO retry completed\n",
        encoding="utf-8",
    )
    (search_root / "notes.txt").write_text(
        "The database configuration is stored separately.\n"
        "Linux commands are case-sensitive.\n",
        encoding="utf-8",
    )
    (search_root / "nested").mkdir()
    (search_root / "nested" / "report.txt").write_text(
        "Database reliability report.\n",
        encoding="utf-8",
    )

    commands = [
        (
            "find search_lab -type f",
            "Find regular files recursively.",
        ),
        (
            "find search_lab -name '*.txt'",
            "Find files whose names end in .txt.",
        ),
        (
            "find search_lab -type f -name '*.txt'",
            "Combine file type and name criteria.",
        ),
        (
            "grep -n 'ERROR' search_lab/app.log",
            "Find ERROR lines and show their line numbers.",
        ),
        (
            "grep -ri 'database' search_lab",
            "Recursively search for database, ignoring case.",
        ),
        (
            "grep -rv 'INFO' search_lab/app.log",
            "Show lines that do not contain INFO.",
        ),
    ]

    for command, description in commands:
        demonstrate_command(command, description, workspace)


# ---------------------------------------------------------------------------
# Wildcards and shell expansion
# ---------------------------------------------------------------------------

def lesson_09_wildcards(workspace: Path) -> None:
    title("9. Wildcards and shell expansion")

    print(
        """
Shell wildcards are patterns interpreted by the shell.

  *       matches zero or more characters
  ?       matches one character
  [abc]   matches one character from a, b, or c
  [0-9]   matches one character in the range 0 through 9

Examples:

  ls *.txt
  ls report?.csv
  ls image[0-9].png

A critical distinction exists between shell globbing and regular expressions.
They are not the same language.

For example, '*.txt' is a shell glob. It is not a regular expression.

Quoting controls shell interpretation:

  '*.txt'       passes the literal pattern to a program
  "*.txt"       also prevents pathname expansion
  *.txt         allows the shell to expand matching filenames before execution

This distinction is especially important with find, grep, scripts, and file
names containing spaces or special characters.
"""
    )

    wildcard_dir = workspace / "wildcards"
    wildcard_dir.mkdir()
    for filename in [
        "report1.txt",
        "report2.txt",
        "report10.txt",
        "notes.txt",
        "image1.png",
    ]:
        (wildcard_dir / filename).write_text(
            f"Sample file: {filename}\n",
            encoding="utf-8",
        )

    demonstrate_command(
        "printf '%s\\n' *.txt",
        "Use a shell glob to expand all .txt names in the current practice directory.",
        wildcard_dir,
    )

    demonstrate_command(
        "find . -name '*.txt'",
        "Quote the pattern so find, not the shell, interprets it.",
        wildcard_dir,
    )


# ---------------------------------------------------------------------------
# Pipes and redirection
# ---------------------------------------------------------------------------

def lesson_10_pipes_redirection(workspace: Path) -> None:
    title("10. Redirection, pipes, stdin, stdout, and stderr")

    print(
        """
Linux programs normally work with three standard streams:

  stdin   standard input
  stdout  standard output
  stderr  standard error

Common redirection operators:

  command > file       replace stdout destination
  command >> file      append stdout
  command 2> file      redirect stderr
  command 2>> file     append stderr
  command < file       use file as stdin

A pipe connects stdout of one process to stdin of another:

  command1 | command2

For example:

  cat file.txt | grep error

This can be shortened to:

  grep error file.txt

A pipeline is valuable when each command performs one focused transformation.

Another useful example:

  find . -type f | wc -l

The first command discovers files, and the second counts the resulting lines.

Command substitution evaluates one command and uses its output as data:

  current_dir=$(pwd)

This is different from a pipe because command substitution embeds the result
inside another command.
"""
    )

    report = workspace / "pipeline.txt"
    report.write_text(
        "INFO start\n"
        "ERROR network failure\n"
        "INFO retry\n"
        "ERROR timeout\n"
        "INFO complete\n",
        encoding="utf-8",
    )

    demonstrate_command(
        "cat pipeline.txt",
        "Print the source data used for pipeline examples.",
        workspace,
    )

    # The following uses shell syntax deliberately because the lesson is about
    # pipes. The input file is inside our private temporary workspace.
    pipeline_command = "grep 'ERROR' pipeline.txt | wc -l"
    print(f"\n$ {pipeline_command}")
    result = subprocess.run(
        pipeline_command,
        cwd=workspace,
        shell=True,
        text=True,
        capture_output=True,
    )
    show_output(result.stdout)
    print(f"  exit status: {result.returncode}")

    redirection_command = "grep 'ERROR' pipeline.txt > errors.txt"
    print(f"\n$ {redirection_command}")
    result = subprocess.run(
        redirection_command,
        cwd=workspace,
        shell=True,
        text=True,
        capture_output=True,
    )
    print(f"  exit status: {result.returncode}")

    demonstrate_command(
        "cat errors.txt",
        "Inspect output redirected from grep into a file.",
        workspace,
    )

    # Demonstrate stderr independently.
    if command_exists("ls"):
        print("\n$ ls missing-file 2> error.log")
        result = subprocess.run(
            "ls missing-file 2> error.log",
            cwd=workspace,
            shell=True,
            text=True,
            capture_output=True,
        )
        print(f"  exit status: {result.returncode}")

        demonstrate_command(
            "cat error.log",
            "Read the stderr output captured in a file.",
            workspace,
        )


# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------

def lesson_11_text_processing(workspace: Path) -> None:
    title("11. Basic text-processing commands")

    print(
        """
Linux becomes particularly powerful when file operations are combined with
text-processing tools.

Important commands include:

  sort    sort lines
  uniq    remove adjacent duplicate lines
  cut     select fields or character ranges
  tr      translate or delete characters
  sed     perform stream-oriented text transformations
  awk     process structured text by fields and conditions

Examples:

  sort names.txt
  sort names.txt | uniq
  cut -d',' -f1 data.csv
  tr 'a-z' 'A-Z' < names.txt
  sed 's/old/new/g' file.txt
  awk '{print $1}' file.txt

uniq removes adjacent duplicate lines, so sorting before uniq is often
necessary when the goal is to count all repeated values.

awk treats whitespace-separated input as fields by default:

  $1    first field
  $2    second field
  $0    entire record

For CSV files containing quoted commas, basic cut and awk expressions are not
full CSV parsers. Real CSV processing may require a dedicated parser.
"""
    )

    text_file = workspace / "people.txt"
    text_file.write_text(
        "Zara 28\n"
        "Amit 31\n"
        "Ravi 26\n"
        "Amit 31\n"
        "Neha 29\n",
        encoding="utf-8",
    )

    demonstrations = [
        ("sort people.txt", "Sort records lexicographically."),
        ("sort people.txt | uniq", "Sort first, then remove adjacent duplicates."),
        ("awk '{print $1}' people.txt", "Print the first whitespace-separated field."),
        ("awk '$2 >= 29 {print $1, $2}' people.txt", "Filter records by a numeric field."),
    ]

    for command, description in demonstrations:
        print(f"\n$ {command}")
        print(f"  {description}")

        if command_exists(command.split()[0]):
            result = subprocess.run(
                command,
                cwd=workspace,
                shell=True,
                text=True,
                capture_output=True,
            )
            show_output(result.stdout)
            if result.stderr:
                print(f"  stderr: {result.stderr.rstrip()}")
            print(f"  exit status: {result.returncode}")
        else:
            print("  [Skipped because the required command is unavailable.]")


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def lesson_12_permissions(workspace: Path) -> None:
    title("12. Permissions and ownership")

    print(
        """
Linux permissions are traditionally represented for three classes:

  user       owner of the file
  group      members of the file's group
  others     everyone else

Each class can have:

  r   read
  w   write
  x   execute

A symbolic mode such as:

  -rwxr-xr--

can be interpreted as:

  user:   rwx
  group:  r-x
  others: r--

Numeric permissions use octal values:

  r = 4
  w = 2
  x = 1

Therefore:

  rwx = 7
  r-x = 5
  r-- = 4

So 754 means:

  owner  -> rwx
  group  -> r-x
  others -> r--

Common commands:

  chmod 644 file.txt
  chmod 755 script.sh
  chmod u+x script.sh

Ownership:

  chown user file
  chown user:group file

Group changes:

  chgrp group file

Changing ownership usually requires elevated privileges. Do not use sudo as
a default response to permission problems. First determine which permission
or ownership rule actually caused the failure.
"""
    )

    permission_file = workspace / "permissions.txt"
    permission_file.write_text("Permission demonstration.\n", encoding="utf-8")

    demonstrate_command(
        "ls -l permissions.txt",
        "Inspect the file's current permission bits.",
        workspace,
    )

    if command_exists("chmod"):
        demonstrate_command(
            "chmod 640 permissions.txt",
            "Set owner read/write, group read, and no permissions for others.",
            workspace,
        )

        demonstrate_command(
            "ls -l permissions.txt",
            "Verify the changed permission bits.",
            workspace,
        )

    # Demonstrate Python's view of permission bits.
    mode = permission_file.stat().st_mode
    print(
        "\nPython inspection:\n"
        f"  Numeric permission bits: {stat.S_IMODE(mode):03o}\n"
        f"  Owner-readable: {bool(mode & stat.S_IRUSR)}\n"
        f"  Owner-writable: {bool(mode & stat.S_IWUSR)}\n"
        f"  Owner-executable: {bool(mode & stat.S_IXUSR)}"
    )


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

def lesson_13_links(workspace: Path) -> None:
    title("13. Hard links and symbolic links")

    print(
        """
Linux supports multiple names and references to file data.

Hard link:

  ln original.txt hard_link.txt

A hard link refers to the same underlying inode as the original directory
entry. Removing one name does not necessarily remove the data while another
hard link still exists.

Symbolic link:

  ln -s original.txt symbolic_link.txt

A symbolic link stores a path to another file. It can point across file
systems and can point to directories. If its target disappears, the symlink
can become dangling.

Important distinction:

  hard link -> another directory entry for the same inode
  symlink   -> a separate object containing a target path

Hard links generally cannot cross file-system boundaries and normally cannot
be created for directories by ordinary users.

Symlinks are common for configuration paths, release directories, and
alternative names.
"""
    )

    original = workspace / "original.txt"
    original.write_text("Shared inode demonstration.\n", encoding="utf-8")

    if command_exists("ln"):
        demonstrate_command(
            "ln original.txt hard_link.txt",
            "Create a hard link to the same file data.",
            workspace,
        )

        demonstrate_command(
            "ln -s original.txt symbolic_link.txt",
            "Create a symbolic link referring to the original path.",
            workspace,
        )

        demonstrate_command(
            "ls -li original.txt hard_link.txt symbolic_link.txt",
            "Compare inode numbers and inspect the symbolic link.",
            workspace,
        )

        demonstrate_command(
            "cat symbolic_link.txt",
            "Read the target through the symbolic link.",
            workspace,
        )


# ---------------------------------------------------------------------------
# Archives and compression
# ---------------------------------------------------------------------------

def lesson_14_archives(workspace: Path) -> None:
    title("14. Archives and compression")

    print(
        """
tar is an archive utility. It combines multiple files into an archive.

Common options:

  tar -cf archive.tar directory/
  tar -tf archive.tar
  tar -xf archive.tar

The letters commonly mean:

  c -> create
  t -> list contents
  x -> extract
  f -> archive file name follows

Compression can be combined with tar:

  tar -czf archive.tar.gz directory/
  tar -xzf archive.tar.gz

Here z selects gzip compression.

The archive format and compression algorithm are separate concepts. tar
packages files; gzip compresses the resulting stream.

Always inspect archives from untrusted sources carefully before extracting
them, especially when archive members contain absolute paths or path
traversal sequences.
"""
    )

    archive_source = workspace / "archive_source"
    archive_source.mkdir()
    (archive_source / "a.txt").write_text("A\n", encoding="utf-8")
    (archive_source / "b.txt").write_text("B\n", encoding="utf-8")

    if command_exists("tar"):
        demonstrate_command(
            "tar -cf practice.tar archive_source",
            "Create a tar archive from the demonstration directory.",
            workspace,
        )

        demonstrate_command(
            "tar -tf practice.tar",
            "List archive members without extracting them.",
            workspace,
        )

        extraction_dir = workspace / "extracted"
        extraction_dir.mkdir()

        demonstrate_command(
            "tar -xf ../practice.tar",
            "Extract the archive into a separate demonstration directory.",
            extraction_dir,
        )

        demonstrate_command(
            "find extracted -print",
            "Inspect the extracted directory tree.",
            workspace,
        )

    if command_exists("gzip"):
        # Use a separate copy so the archive lesson remains understandable.
        gzip_source = workspace / "compression_demo.txt"
        gzip_source.write_text(
            "Compression reduces the size of suitable data by representing it "
            "more efficiently.\n" * 20,
            encoding="utf-8",
        )

        demonstrate_command(
            "gzip -k compression_demo.txt",
            "Create a gzip-compressed copy while retaining the original (-k).",
            workspace,
        )

        demonstrate_command(
            "ls -lh compression_demo.txt compression_demo.txt.gz",
            "Compare original and compressed file sizes.",
            workspace,
        )


# ---------------------------------------------------------------------------
# Command discovery and help
# ---------------------------------------------------------------------------

def lesson_15_help_and_documentation() -> None:
    title("15. Discovering command behavior")

    print(
        """
Linux commands often expose their usage through:

  command --help
  man command
  info command

Examples:

  ls --help
  man cp
  man find

The man system is especially important because command behavior and available
options can vary between implementations and distributions.

Other useful discovery commands include:

  type command
  which command
  command -v command

'command -v' is often useful in scripts because it determines whether a
command can be resolved through PATH.

Do not memorize every option. Understand the command's model, then consult
the local documentation for exact syntax.
"""
    )

    demonstrate_command(
        "command -v ls",
        "Show the executable selected for ls through PATH.",
    )

    demonstrate_command(
        "command -v find",
        "Check whether find is available.",
    )

    demonstrate_command(
        "ls --help",
        "Display built-in help when supported.",
    )


# ---------------------------------------------------------------------------
# Environment and PATH
# ---------------------------------------------------------------------------

def lesson_16_environment() -> None:
    title("16. Environment variables and PATH")

    print(
        """
The shell maintains environment variables that programs can read.

Important variables include:

  HOME     user's home directory
  PATH     directories searched for executable commands
  PWD      current working directory in many shells
  USER     current user in many environments

PATH is particularly important. When you type:

  python

the shell searches directories listed in PATH until it finds a matching
executable.

Inspect variables:

  echo "$HOME"
  echo "$PATH"
  printenv HOME
  printenv

When a command is not found, common causes include:

  - the program is not installed
  - its directory is not in PATH
  - a typo occurred
  - a shell environment has not been refreshed

Never blindly add untrusted directories to PATH. PATH ordering determines
which executable is selected when multiple commands have the same name.
"""
    )

    for variable in ["HOME", "PATH", "PWD", "USER"]:
        print(f"\n{variable} = {os.environ.get(variable, '[not defined]')}")

    demonstrate_command(
        "printenv HOME",
        "Ask the environment for the user's home directory.",
    )


# ---------------------------------------------------------------------------
# Exit status and error handling
# ---------------------------------------------------------------------------

def lesson_17_exit_status() -> None:
    title("17. Exit status and reliable command execution")

    print(
        """
Linux programs normally return an exit status.

Conventionally:

  0       success
  nonzero failure or another condition

The shell exposes the previous command's status through $?.

For example:

  ls existing-file
  echo $?

A failed command can therefore be detected by scripts.

Common shell control operators include:

  command1 && command2
      run command2 only when command1 succeeds

  command1 || command2
      run command2 when command1 fails

  command1 ; command2
      run command2 regardless of command1's exit status

These operators are different from pipes.

Python's subprocess module provides returncode for the same underlying
process result. When building automation, checking exit status is essential.
"""
    )

    print("\nPython demonstration of exit status:")

    success = subprocess.run(
        ["python", "-c", "print('success')"],
        text=True,
        capture_output=True,
    )
    print(f"  successful command return code: {success.returncode}")

    failure = subprocess.run(
        ["python", "-c", "raise SystemExit(7)"],
        text=True,
        capture_output=True,
    )
    print(f"  failed command return code: {failure.returncode}")

    if command_exists("true") and command_exists("false"):
        demonstrate_command(
            "true",
            "A conventional command that exits successfully.",
        )

        demonstrate_command(
            "false",
            "A conventional command that returns a failure status.",
        )


# ---------------------------------------------------------------------------
# Quoting and filenames
# ---------------------------------------------------------------------------

def lesson_18_quoting(workspace: Path) -> None:
    title("18. Quoting, spaces, and special characters")

    print(
        """
The shell interprets spaces and special characters before a command receives
its arguments.

A filename such as:

  quarterly report.txt

must be quoted or escaped:

  cat 'quarterly report.txt'
  cat quarterly\\ report.txt

Single quotes generally preserve characters literally.
Double quotes still allow some shell expansions, such as variables and
command substitution.

Example:

  name="Atul"
  echo "$name"

Using quotes around "$name" prevents word splitting and pathname expansion.

A robust general rule is to quote variables unless you deliberately need the
shell to split or expand them.

File names beginning with '-' deserve special attention. Many commands may
interpret such a name as an option. A conventional way to indicate the end of
options is:

  command -- filename

For example:

  rm -- -strange-name.txt

This protects the filename from being interpreted as a command option.
"""
    )

    special_file = workspace / "quarterly report.txt"
    special_file.write_text("A filename containing spaces.\n", encoding="utf-8")

    demonstrate_command(
        "cat 'quarterly report.txt'",
        "Use quoting so the filename is passed as one argument.",
        workspace,
    )

    demonstrate_command(
        "ls -l -- 'quarterly report.txt'",
        "Use -- to separate command options from the filename.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Permissions and executable scripts
# ---------------------------------------------------------------------------

def lesson_19_executable_script(workspace: Path) -> None:
    title("19. Executable files and shebangs")

    print(
        """
A shell script is commonly started with a shebang:

  #!/bin/bash

The shebang tells the kernel which interpreter should execute the script when
the file is run directly.

For example:

  chmod +x hello.sh
  ./hello.sh

The current directory is commonly not included in PATH for security reasons.
Therefore:

  hello.sh

and:

  ./hello.sh

are not equivalent.

The first asks PATH to locate hello.sh.
The second explicitly identifies the file in the current directory.

A script should use the least privileges necessary and should validate input
before performing destructive operations.
"""
    )

    script = workspace / "hello.sh"
    script.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'Hello from a Linux shell script.'\n",
        encoding="utf-8",
    )

    if command_exists("chmod"):
        demonstrate_command(
            "chmod +x hello.sh",
            "Mark the shell script as executable.",
            workspace,
        )

        demonstrate_command(
            "./hello.sh",
            "Execute the script directly using its shebang.",
            workspace,
        )


# ---------------------------------------------------------------------------
# Advanced find operations
# ---------------------------------------------------------------------------

def lesson_20_advanced_find(workspace: Path) -> None:
    title("20. Advanced find patterns")

    print(
        """
find becomes especially useful when its tests are combined.

Examples:

  find . -type f -name '*.log'
  find . -type f -size +10M
  find . -type f -mtime +30
  find . -type f -perm 600
  find . -type f -exec wc -l {} \\;

The -exec action can execute another command for each matched item.

The special token {} represents the current result.

A semicolon terminates the -exec expression. It is normally escaped or
quoted so that the shell does not consume it.

For large result sets, find implementations may support:

  -exec command {} +

This groups multiple paths into fewer command invocations and can be more
efficient than running the command once per file.
"""
    )

    advanced = workspace / "advanced_find"
    advanced.mkdir()

    for index in range(1, 4):
        file_path = advanced / f"data{index}.txt"
        file_path.write_text(
            f"file {index}\nline two\nline three\n",
            encoding="utf-8",
        )

    demonstrate_command(
        "find advanced_find -type f -name '*.txt'",
        "Find all text files in the demonstration directory.",
        workspace,
    )

    demonstrate_command(
        r"find advanced_find -type f -name '*.txt' -exec wc -l {} +",
        "Count lines in all matching files using grouped -exec execution.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Disk usage and inode considerations
# ---------------------------------------------------------------------------

def lesson_21_disk_usage(workspace: Path) -> None:
    title("21. Disk usage, file size, and inode considerations")

    print(
        """
File size and disk usage are related but not identical.

  ls -lh file
      displays the logical file size.

  du -h file
      reports disk usage attributed to the file.

Sparse files can have a large apparent size while occupying fewer physical
blocks.

Disk space and inode availability are separate resources. A system can have
free bytes but still fail to create files when it runs out of inodes.

Useful commands:

  df -h
  df -i
  du -sh directory/

For directory investigations, du is often more useful than repeatedly
checking individual files.
"""
    )

    demonstrate_command(
        "du -sh .",
        "Estimate the total disk usage of the practice workspace.",
        workspace,
    )

    demonstrate_command(
        "df -h .",
        "Inspect available file-system space.",
        workspace,
    )

    demonstrate_command(
        "df -i .",
        "Inspect inode usage when supported by the file system.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Safe shell automation
# ---------------------------------------------------------------------------

def lesson_22_safe_automation(workspace: Path) -> None:
    title("22. Safe automation patterns")

    print(
        """
Automation becomes useful when many files must be processed consistently.

A dangerous pattern is constructing shell commands by directly concatenating
untrusted strings:

  command = "rm " + user_input

The resulting string can be interpreted as shell syntax.

A safer Python approach is to pass an argument list to subprocess.run:

  subprocess.run(["rm", "--", filename], check=True)

This avoids shell parsing for the filename.

When shell syntax itself is required, use careful quoting and validation.

For shell scripts, common defensive practices include:

  - quote variables
  - validate paths
  - use explicit directories
  - avoid unnecessary sudo
  - inspect destructive targets
  - check exit statuses
  - use temporary directories for experiments
  - avoid parsing ls output as structured data

For machine-readable file processing, prefer direct APIs or find's structured
options over fragile text parsing.
"""
    )

    safe_file = workspace / "safe automation.txt"
    safe_file.write_text("Safe argument passing example.\n", encoding="utf-8")

    if command_exists("cat"):
        result = subprocess.run(
            ["cat", "--", str(safe_file)],
            text=True,
            capture_output=True,
            check=False,
        )

        print("\nPython subprocess with an argument list:")
        print("  subprocess.run(['cat', '--', filename], ...)")
        print(f"  return code: {result.returncode}")
        print(f"  output: {result.stdout.rstrip()}")


# ---------------------------------------------------------------------------
# Symbolic command combinations
# ---------------------------------------------------------------------------

def lesson_23_command_composition(workspace: Path) -> None:
    title("23. Combining commands into useful workflows")

    print(
        """
Real shell work rarely consists of one command in isolation.

Example workflow:

  mkdir -p project/logs
  touch project/logs/application.log
  grep -n 'ERROR' project/logs/application.log
  find project -type f
  du -sh project

A more advanced pipeline might be:

  find . -type f -name '*.log' -print0 | xargs -0 grep -n 'ERROR'

The -print0 and -0 combination handles spaces and other unusual characters
more reliably than newline-delimited processing.

Many modern find implementations can avoid xargs entirely:

  find . -type f -name '*.log' -exec grep -n 'ERROR' {} +

The second form is often easier to reason about because find directly controls
which paths are passed to grep.
"""
    )

    project = workspace / "project"
    (project / "logs").mkdir(parents=True)

    for name, content in {
        "application.log": "INFO start\nERROR database\nINFO end\n",
        "worker.log": "INFO worker\nWARNING slow task\nERROR timeout\n",
        "readme.txt": "Project documentation.\n",
    }.items():
        (project / "logs" / name if name.endswith(".log") else project / name).write_text(
            content,
            encoding="utf-8",
        )

    demonstrate_command(
        "find project -type f -print",
        "Discover all project files.",
        workspace,
    )

    demonstrate_command(
        r"find project -type f -name '*.log' -exec grep -n 'ERROR' {} +",
        "Find log files and search their contents efficiently.",
        workspace,
    )

    demonstrate_command(
        "du -sh project",
        "Measure the project's disk usage.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Troubleshooting
# ---------------------------------------------------------------------------

def lesson_24_troubleshooting(workspace: Path) -> None:
    title("24. Troubleshooting common command errors")

    print(
        """
When a command fails, do not immediately retry it with sudo or force flags.
Identify the failure first.

Common errors:

  command not found
      The command may not be installed or may not be in PATH.

  No such file or directory
      The path is wrong, the working directory is unexpected, or a link target
      does not exist.

  Permission denied
      The current user may lack required permission, or the file may not be
      executable.

  Is a directory
      A command expected a file but received a directory.

  Not a directory
      A path component that should be a directory is actually a file.

  File exists
      An operation expected a destination not to exist.

Useful diagnostic commands:

  pwd
  ls -la
  file path
  stat path
  namei -l path
  id
  command -v command

A disciplined diagnostic sequence is:

  1. Check where you are.
  2. Check the exact path.
  3. Check file type.
  4. Check permissions.
  5. Check ownership.
  6. Check whether the command exists.
  7. Check exit status.
  8. Only then consider privilege or environmental issues.
"""
    )

    missing = workspace / "does-not-exist.txt"

    if command_exists("cat"):
        print(f"\n$ cat {missing.name}")
        result = subprocess.run(
            ["cat", str(missing)],
            cwd=workspace,
            text=True,
            capture_output=True,
        )
        print(f"  return code: {result.returncode}")
        print(f"  stderr: {result.stderr.rstrip()}")


# ---------------------------------------------------------------------------
# Common mistakes
# ---------------------------------------------------------------------------

def lesson_25_common_mistakes() -> None:
    title("25. Common mistakes and subtle behaviors")

    print(
        """
1. Confusing relative and absolute paths

   If the current directory changes, a relative path can refer to a different
   location. Use pwd when uncertain.

2. Forgetting that Linux is case-sensitive

   config.txt and Config.txt are different names.

3. Forgetting to quote paths containing spaces

   Use:
       cat 'annual report.txt'

4. Accidentally overwriting files with >

   Use >> when appending is intended.

5. Forgetting -r when recursively copying or deleting directories

   cp directory destination
   rm directory

   may fail where:
   cp -r directory destination
   rm -r directory

   is intended.

6. Using rm -rf without inspecting the target

   Force and recursive deletion remove safeguards.

7. Assuming uniq finds every duplicate automatically

   uniq only removes adjacent duplicates, so sorting is often required first.

8. Treating find patterns like regular expressions

   -name commonly uses shell-style wildcard patterns.

9. Parsing ls output

   File names can contain spaces, tabs, newlines, and unusual characters.
   Structured tools such as find, stat, and direct system APIs are safer for
   automation.

10. Using sudo unnecessarily

   Root privileges increase the impact of mistakes.

11. Forgetting that symbolic links can dangle

   A symlink may remain after its target is deleted.

12. Assuming mv is always a constant-time metadata operation

   Cross-file-system moves can require copying data.

13. Ignoring exit statuses

   A command may produce output and still fail.

14. Assuming command options are identical everywhere

   GNU/Linux, BSD, BusyBox, and other implementations can differ.
"""
    )


# ---------------------------------------------------------------------------
# Python comparison
# ---------------------------------------------------------------------------

def lesson_26_linux_commands_vs_python(workspace: Path) -> None:
    title("26. Linux commands versus Python file APIs")

    print(
        """
Linux commands are excellent for interactive administration and concise
shell workflows.

Python is often preferable when:

  - logic becomes complicated
  - input validation is required
  - errors need structured handling
  - operations must be portable
  - file names contain unusual characters
  - the process becomes a larger application

Useful Python equivalents:

  pwd          -> Path.cwd()
  ls           -> Path.iterdir()
  mkdir        -> Path.mkdir()
  touch        -> Path.touch()
  cp           -> shutil.copy2()
  mv           -> shutil.move()
  rm           -> Path.unlink()
  rm -r        -> shutil.rmtree()
  find         -> pathlib.Path.rglob()
  cat          -> Path.read_text()
  stat         -> Path.stat()

The best choice depends on the task. A short shell command can be clearer
than a large Python program, while structured application logic is generally
easier to test in Python.
"""
    )

    python_demo = workspace / "python_api_demo"
    python_demo.mkdir()

    file_a = python_demo / "a.txt"
    file_a.write_text("Python pathlib demonstration.\n", encoding="utf-8")

    file_b = python_demo / "b.txt"
    shutil.copy2(file_a, file_b)

    renamed = python_demo / "renamed.txt"
    shutil.move(file_b, renamed)

    print("\nPython implementation sequence:")
    print(f"  created: {file_a}")
    print(f"  copied:  {renamed}")
    print(f"  entries: {[p.name for p in python_demo.iterdir()]}")

    # pathlib.rglob demonstrates recursive searching without find.
    matches = list(python_demo.rglob("*.txt"))
    print(f"  recursive *.txt matches: {[p.name for p in matches]}")


# ---------------------------------------------------------------------------
# Production considerations
# ---------------------------------------------------------------------------

def lesson_27_production_considerations() -> None:
    title("27. Production and security considerations")

    print(
        """
File-system commands have direct operational consequences, so production
usage requires more discipline than experimentation.

Least privilege:
    Run commands as the least-privileged account that can perform the task.

Input validation:
    Treat file names, paths, and command arguments received from users or
    external systems as untrusted data.

Path traversal:
    An application accepting a path such as ../../secret.txt can accidentally
    access data outside an intended directory. Validate and constrain paths.

Shell injection:
    Never construct shell commands by concatenating untrusted input.

Race conditions:
    A file can change between checking it and operating on it. Security-
    sensitive applications should use appropriate atomic operations and
    operating-system APIs.

Symlink attacks:
    A path that appears safe can point somewhere unexpected through a symlink.
    Sensitive applications need careful handling of links and directory
    traversal.

Backups:
    rm is generally irreversible from the command's perspective. Important
    data should have independent backups.

Atomic updates:
    For configuration files, writing a temporary file and atomically replacing
    the destination can prevent readers from observing partially written data.

Logging:
    Automated file operations should record enough information to diagnose
    failures without leaking secrets.

Permissions:
    Avoid world-writable files and directories unless there is a deliberate
    reason. Avoid granting execute permission unnecessarily.

Reliability:
    Check exit statuses and handle partial failures.

Portability:
    Test assumptions about command options when scripts may run across
    different distributions or Unix-like systems.
"""
    )


# ---------------------------------------------------------------------------
# Practice exercises
# ---------------------------------------------------------------------------

def lesson_28_practice_exercises(workspace: Path) -> None:
    title("28. Integrated practice exercises")

    print(
        """
Exercise 1: Navigation
    Create a directory named exercise1, create a nested directory named data,
    enter it, and verify the location with pwd.

Exercise 2: File creation
    Create three text files. Put different content into each file and inspect
    them with cat, head, and tail.

Exercise 3: Copy and move
    Copy one file into a backup directory. Rename another file and move it
    into a separate directory.

Exercise 4: Search
    Use find to locate every .txt file. Use grep to find a chosen word inside
    those files.

Exercise 5: Pipeline
    Count the number of matching lines using grep followed by wc.

Exercise 6: Permissions
    Inspect permissions with ls -l. Change a demonstration file to 640 and
    verify the result.

Exercise 7: Links
    Create a symbolic link and verify that reading the link returns the target
    file's content.

Exercise 8: Archives
    Create a directory tree, archive it with tar, list the archive contents,
    then extract it into another directory.

Exercise 9: Safe deletion
    Before deleting a directory recursively, inspect it using find. Remove
    only the intended practice directory.

Exercise 10: Integrated workflow
    Create a project directory containing logs and documents. Find log files,
    search them for ERROR, count the matching lines, inspect disk usage, and
    archive the project.

All exercises should be performed inside a disposable practice directory.
"""
    )

    exercise_root = workspace / "exercise_solution_demo"
    exercise_root.mkdir()

    (exercise_root / "data").mkdir()
    (exercise_root / "data" / "one.txt").write_text(
        "alpha\nerror: connection\nomega\n",
        encoding="utf-8",
    )
    (exercise_root / "data" / "two.txt").write_text(
        "beta\nnormal operation\ngamma\n",
        encoding="utf-8",
    )
    (exercise_root / "data" / "three.txt").write_text(
        "delta\nerror: timeout\nepsilon\n",
        encoding="utf-8",
    )

    demonstrate_command(
        "find exercise_solution_demo -type f -name '*.txt'",
        "Exercise solution: discover all text files.",
        workspace,
    )

    demonstrate_command(
        "grep -ri -n 'error' exercise_solution_demo/data",
        "Exercise solution: find error messages recursively.",
        workspace,
    )

    if command_exists("grep") and command_exists("wc"):
        command = "grep -ri -n 'error' exercise_solution_demo/data | wc -l"
        print(f"\n$ {command}")
        result = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            text=True,
            capture_output=True,
        )
        show_output(result.stdout)
        print(f"  exit status: {result.returncode}")

    demonstrate_command(
        "du -sh exercise_solution_demo",
        "Exercise solution: measure the practice directory.",
        workspace,
    )


# ---------------------------------------------------------------------------
# Command reference
# ---------------------------------------------------------------------------

def lesson_29_reference() -> None:
    title("29. Command reference")

    reference = [
        ("pwd", "Print working directory.", "pwd"),
        ("ls", "List directory contents.", "ls -la"),
        ("cd", "Change directory.", "cd /tmp"),
        ("mkdir", "Create directories.", "mkdir -p project/data"),
        ("touch", "Create an empty file or update timestamps.", "touch notes.txt"),
        ("cp", "Copy files or directories.", "cp -r src backup"),
        ("mv", "Move or rename files and directories.", "mv old.txt new.txt"),
        ("rm", "Remove files or directories.", "rm -r old_directory"),
        ("cat", "Print file contents.", "cat notes.txt"),
        ("less", "Interactively inspect large text files.", "less application.log"),
        ("head", "Show the beginning of a file.", "head -n 20 file.txt"),
        ("tail", "Show the end of a file.", "tail -n 20 file.txt"),
        ("wc", "Count lines, words, and bytes.", "wc -l file.txt"),
        ("file", "Identify a file's type.", "file image.png"),
        ("stat", "Display detailed metadata.", "stat file.txt"),
        ("find", "Search directory trees.", "find . -type f -name '*.txt'"),
        ("grep", "Search text for patterns.", "grep -n 'ERROR' app.log"),
        ("sort", "Sort lines.", "sort names.txt"),
        ("uniq", "Remove adjacent duplicate lines.", "sort names.txt | uniq"),
        ("cut", "Extract fields or character ranges.", "cut -d',' -f1 data.csv"),
        ("tr", "Translate or delete characters.", "tr 'a-z' 'A-Z'"),
        ("sed", "Perform stream text transformations.", "sed 's/old/new/g' file"),
        ("awk", "Process records and fields.", "awk '{print $1}' file"),
        ("chmod", "Change permission bits.", "chmod 640 file.txt"),
        ("chown", "Change file owner.", "chown user file.txt"),
        ("chgrp", "Change file group.", "chgrp developers file.txt"),
        ("ln", "Create hard or symbolic links.", "ln -s target link"),
        ("tar", "Create, list, and extract archives.", "tar -czf backup.tar.gz project"),
        ("gzip", "Compress data using gzip.", "gzip file.txt"),
        ("df", "Show file-system space.", "df -h"),
        ("du", "Show disk usage.", "du -sh directory"),
        ("which", "Locate an executable in PATH.", "which python"),
        ("type", "Describe how the shell resolves a command.", "type cd"),
        ("printenv", "Display environment variables.", "printenv PATH"),
    ]

    print(f"\n{'Command':<12} {'Purpose':<48} Example")
    print("-" * 105)

    for command, purpose, example in reference:
        print(f"{command:<12} {purpose:<48} {example}")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main() -> None:
    title("Linux Commands Practice Lab")

    print(
        f"""
Platform detected: {platform.system()} {platform.release()}
Python version: {platform.python_version()}
Current working directory: {Path.cwd()}

This lesson uses a temporary workspace. Files created by the demonstrations
are removed automatically when the script finishes.

The Linux commands themselves are demonstrated when they are available on the
current machine. On Windows without WSL, many Linux commands will be skipped,
but the explanations and Python file-system demonstrations still run.
"""
    )

    with tempfile.TemporaryDirectory(prefix="linux_commands_lab_") as temp_dir:
        workspace = Path(temp_dir)

        print(f"Temporary practice workspace: {workspace}")

        lesson_01_linux_and_the_file_system()
        lesson_02_navigation(workspace)
        lesson_03_creation(workspace)
        lesson_04_inspection(workspace)
        lesson_05_copying(workspace)
        lesson_06_moving(workspace)
        lesson_07_deletion(workspace)
        lesson_08_searching(workspace)
        lesson_09_wildcards(workspace)
        lesson_10_pipes_redirection(workspace)
        lesson_11_text_processing(workspace)
        lesson_12_permissions(workspace)
        lesson_13_links(workspace)
        lesson_14_archives(workspace)
        lesson_15_help_and_documentation()
        lesson_16_environment()
        lesson_17_exit_status()
        lesson_18_quoting(workspace)
        lesson_19_executable_script(workspace)
        lesson_20_advanced_find(workspace)
        lesson_21_disk_usage(workspace)
        lesson_22_safe_automation(workspace)
        lesson_23_command_composition(workspace)
        lesson_24_troubleshooting(workspace)
        lesson_25_common_mistakes()
        lesson_26_linux_commands_vs_python(workspace)
        lesson_27_production_considerations()
        lesson_28_practice_exercises(workspace)
        lesson_29_reference()

        title("Practice workspace cleanup")
        print(
            "All demonstration files were created under the temporary workspace "
            "and will be removed automatically."
        )

    title("End of Linux Commands Practice Lab")
    print(
        "The lesson covered navigation, creation, copying, moving, deletion, "
        "searching, inspection, text processing, permissions, links, archives, "
        "pipelines, troubleshooting, automation, and production considerations."
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nPractice interrupted by the user.")
        sys.exit(130)
