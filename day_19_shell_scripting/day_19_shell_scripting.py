#!/usr/bin/env python3
"""
Shell Scripting Study Companion
===============================

This Python program teaches Bash shell scripting from beginner to advanced
concepts through executable simulations and comparisons.

The Python code intentionally models shell concepts rather than executing
arbitrary shell commands. This keeps the study program portable and safe.

Covered concepts:
- Shell and Bash fundamentals
- Variables and environment variables
- Quoting and expansion
- Conditions and exit status
- Loops
- Functions
- Positional arguments
- Arrays and associative arrays
- Command substitution
- Pipelines and redirection
- File and directory automation
- Validation and error handling
- Traps and cleanup
- Configuration handling
- Logging
- Concurrency concepts
- Idempotent automation
- Security practices
- Performance considerations
- A realistic deployment-automation case study
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterable


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def show(label: str, value) -> None:
    print(f"{label}: {value}")


# ---------------------------------------------------------------------------
# 1. Shell fundamentals
# ---------------------------------------------------------------------------

def demonstrate_shell_fundamentals() -> None:
    section("1. Shell fundamentals")

    print(
        """
A shell is a command interpreter. Bash is a widely used Unix shell.

A terminal is the interface in which a shell commonly runs. The shell reads
commands, performs parsing and expansion, launches programs, connects input
and output, and reports an exit status.

Typical Bash commands include:

    pwd
    ls
    cd /tmp
    mkdir project
    printf '%s\\n' 'hello'
    date

A shell script is normally a text file containing Bash commands.

A Bash script commonly starts with:

    #!/usr/bin/env bash

The first line is called a shebang. It tells the operating system which
interpreter should execute the file.

A script can then be made executable with:

    chmod +x script.sh

and executed with:

    ./script.sh

The Python program does not execute those commands automatically. Instead,
it demonstrates their semantics safely.
"""
    )

    current_directory = Path.cwd()
    home_directory = Path.home()

    show("Current directory", current_directory)
    show("Home directory", home_directory)
    show("Operating system", os.name)


# ---------------------------------------------------------------------------
# 2. Variables and data representation
# ---------------------------------------------------------------------------

def demonstrate_variables() -> None:
    section("2. Bash variables")

    print(
        """
Bash variables are assigned without spaces around '=':

    name="Atul"
    count=10

A variable is expanded with '$':

    echo "$name"

Using double quotes around expansions is a critical habit because it protects
whitespace and prevents accidental word splitting.

Bash does not have the same static type system as languages such as C++.
Values are generally represented as strings, although arithmetic expansion
provides integer arithmetic.
"""
    )

    name = "Atul"
    count = 10
    project = "shell-automation"

    show("name", name)
    show("count", count)
    show("project", project)

    arithmetic_result = count * 3 + 2
    show("Arithmetic equivalent", arithmetic_result)

    print("\nPython equivalent of Bash arithmetic expansion:")
    print('    $((count * 3 + 2))')
    print(f"    Result: {arithmetic_result}")


def demonstrate_environment_variables() -> None:
    section("3. Environment variables")

    print(
        """
A normal Bash variable belongs to the current shell.

An environment variable is exported so that child processes inherit it:

    APP_ENV="production"
    export APP_ENV

Bash provides common environment variables such as HOME, PATH, USER,
SHELL, and PWD.

A child process receives a copy of the parent's environment. Changes made
inside the child normally do not modify the parent's environment.
"""
    )

    important = ["HOME", "PATH", "SHELL", "USER", "PWD"]
    for variable in important:
        show(variable, os.environ.get(variable, "<not set>"))


# ---------------------------------------------------------------------------
# 4. Quoting and expansion
# ---------------------------------------------------------------------------

def demonstrate_quoting() -> None:
    section("4. Quoting and expansion")

    print(
        """
Bash has three especially important quoting mechanisms.

Single quotes:
    'literal $text'

The contents are treated almost entirely literally.

Double quotes:
    "value: $text"

Parameter expansion occurs, but word splitting and pathname expansion are
suppressed for the resulting value.

Backslash:
    \\$

can escape individual characters.

Command substitution executes a command and inserts its output:

    current_user="$(whoami)"

Arithmetic expansion evaluates arithmetic:

    total="$((price * quantity))"

A common mistake is writing:

    rm $filename

instead of:

    rm -- "$filename"

Quoting becomes especially important when filenames contain spaces,
wildcards, tabs, or shell metacharacters.
"""
    )

    filename = "quarterly report.txt"
    unquoted_concept = filename.split()
    quoted_concept = [filename]

    show("Unquoted conceptual word splitting", unquoted_concept)
    show("Quoted conceptual argument", quoted_concept)


# ---------------------------------------------------------------------------
# 5. Command substitution
# ---------------------------------------------------------------------------

def demonstrate_command_substitution() -> None:
    section("5. Command substitution")

    print(
        """
Bash command substitution has the form:

    result="$(command)"

The older backtick syntax:

    result="`command`"

works in many situations but is harder to read and nest. Modern scripts
should normally use "$(...)" syntax.

The Python subprocess module provides a useful conceptual comparison.
"""
    )

    try:
        completed = subprocess.run(
            ["python", "-c", "print('command output')"],
            capture_output=True,
            text=True,
            check=True,
        )
        result = completed.stdout.strip()
        show("Captured command output", result)
    except (OSError, subprocess.CalledProcessError) as error:
        show("Subprocess demonstration error", error)


# ---------------------------------------------------------------------------
# 6. Exit status
# ---------------------------------------------------------------------------

def demonstrate_exit_status() -> None:
    section("6. Exit status")

    print(
        """
Every normal Unix process terminates with an integer exit status.

Conventionally:
    0       success
    nonzero failure

Bash exposes the previous command's status through:

    $?

Examples:

    if command; then
        echo "success"
    else
        echo "failure"
    fi

This is preferable to parsing human-readable output when a command already
provides a reliable exit status.
"""
    )

    success = 0
    failure = 1

    show("Successful status", success)
    show("Failure status", failure)
    show("Success test", success == 0)
    show("Failure test", failure != 0)


# ---------------------------------------------------------------------------
# 7. Conditions
# ---------------------------------------------------------------------------

def demonstrate_conditions() -> None:
    section("7. Conditions")

    print(
        """
Bash supports conditional execution with if, elif, and else.

Examples:

    if [[ "$age" -ge 18 ]]; then
        echo "adult"
    elif [[ "$age" -ge 13 ]]; then
        echo "teenager"
    else
        echo "child"
    fi

For Bash-specific scripts, [[ ... ]] is generally safer and more expressive
than the older [ ... ] syntax.

Common tests include:

    -f file       regular file
    -d directory  directory
    -r file       readable
    -w file       writable
    -x file       executable
    -z string     empty string
    -n string     non-empty string
    string1 == string2
    number1 -eq number2
    number1 -lt number2
"""
    )

    age = 24
    environment = "production"
    config_exists = True

    if age >= 18:
        print("Age condition: adult")

    if environment == "production":
        print("Environment condition: production")

    if config_exists:
        print("File-existence condition: configuration is available")


# ---------------------------------------------------------------------------
# 8. Case statements
# ---------------------------------------------------------------------------

def demonstrate_case() -> None:
    section("8. Case statements")

    print(
        """
case is useful when a variable has several expected alternatives.

Bash example:

    case "$environment" in
        development)
            echo "Development mode"
            ;;
        testing)
            echo "Testing mode"
            ;;
        production)
            echo "Production mode"
            ;;
        *)
            echo "Unknown environment"
            exit 1
            ;;
    esac

The Python match statement is a useful conceptual comparison, although Bash
case patterns use shell pattern matching rather than Python's exact syntax.
"""
    )

    environment = "production"

    match environment:
        case "development":
            print("Development mode")
        case "testing":
            print("Testing mode")
        case "production":
            print("Production mode")
        case _:
            print("Unknown environment")


# ---------------------------------------------------------------------------
# 9. Loops
# ---------------------------------------------------------------------------

def demonstrate_loops() -> None:
    section("9. Loops")

    print(
        """
Bash provides several looping forms.

For a list:

    for file in *.log; do
        echo "$file"
    done

For a numeric sequence:

    for ((i=1; i<=5; i++)); do
        echo "$i"
    done

While a condition remains true:

    while [[ "$attempt" -le 3 ]]; do
        ...
        ((attempt++))
    done

Until a condition becomes true:

    until command; do
        ...
    done

The shell also supports break and continue.
"""
    )

    print("List loop:")
    for filename in ["app.log", "db.log", "worker.log"]:
        print(f"  processing {filename}")

    print("Numeric loop:")
    for number in range(1, 6):
        print(f"  number={number}")

    print("While-loop equivalent:")
    attempt = 1
    while attempt <= 3:
        print(f"  attempt={attempt}")
        attempt += 1


# ---------------------------------------------------------------------------
# 10. Functions
# ---------------------------------------------------------------------------

def demonstrate_functions() -> None:
    section("10. Functions")

    print(
        """
Bash functions group reusable commands:

    greet() {
        local name="$1"
        printf 'Hello, %s\\n' "$name"
    }

Arguments are available as:

    $1, $2, $3 ...
    "$@"
    "$#"

"$@" is especially important when forwarding arguments because it preserves
individual argument boundaries.

Bash functions do not normally return arbitrary strings through return.
The return keyword communicates an exit status. Output can instead be
captured using command substitution.
"""
    )

    def greet(name: str) -> str:
        return f"Hello, {name}"

    def add_numbers(first: int, second: int) -> int:
        return first + second

    show("Function result", greet("Atul"))
    show("Arithmetic function", add_numbers(10, 25))


# ---------------------------------------------------------------------------
# 11. Positional arguments
# ---------------------------------------------------------------------------

def demonstrate_arguments() -> None:
    section("11. Positional arguments")

    print(
        """
A Bash script receives command-line arguments through special parameters.

    $0       script name
    $1       first argument
    $2       second argument
    $#       number of arguments
    "$@"     all arguments as separate words
    "$*"     all arguments joined according to IFS

Example:

    ./backup.sh /data /backup

would give:

    $1 = /data
    $2 = /backup

A robust script should validate required arguments before using them.
"""
    )

    arguments = ["/data", "/backup", "--verbose"]
    show("Simulated $0", "backup.sh")
    show("Simulated $1", arguments[0])
    show("Simulated $2", arguments[1])
    show("Simulated $#", len(arguments))
    show("Simulated $@", arguments)


# ---------------------------------------------------------------------------
# 12. Arrays
# ---------------------------------------------------------------------------

def demonstrate_arrays() -> None:
    section("12. Indexed and associative arrays")

    print(
        """
Bash indexed arrays:

    servers=("web01" "web02" "web03")
    echo "${servers[0]}"
    echo "${#servers[@]}"

Associative arrays require Bash support:

    declare -A ports
    ports[http]=80
    ports[https]=443

Quote expansions when passing array elements as arguments.
"""
    )

    servers = ["web01", "web02", "web03"]
    ports = {"http": 80, "https": 443, "ssh": 22}

    show("Indexed array", servers)
    show("First element", servers[0])
    show("Array length", len(servers))
    show("Associative array", ports)


# ---------------------------------------------------------------------------
# 13. Reading files
# ---------------------------------------------------------------------------

def demonstrate_file_processing() -> None:
    section("13. File processing")

    print(
        """
A reliable Bash pattern for reading a file line by line is:

    while IFS= read -r line; do
        printf '%s\\n' "$line"
    done < "$file"

IFS= prevents unwanted trimming and read -r prevents backslash escaping
from changing the input.

For structured data, line-oriented parsing can become fragile. JSON, CSV,
XML, and other formats may require dedicated parsers rather than ad-hoc
shell parsing.
"""
    )

    sample_lines = [
        "server=web01",
        "server=web02",
        "server=web03",
    ]

    for line in sample_lines:
        print(f"  read: {line}")


# ---------------------------------------------------------------------------
# 14. Redirection and pipelines
# ---------------------------------------------------------------------------

def demonstrate_redirection() -> None:
    section("14. Redirection and pipelines")

    print(
        """
Shell redirection connects process input and output.

    command > file        stdout, replace file
    command >> file       stdout, append
    command < file        stdin from file
    command 2> file       stderr to file
    command > file 2>&1   stdout and stderr to same destination
    command 2>&1 | other  combine stderr with stdout before piping

Pipelines connect stdout of one command to stdin of another:

    ps aux | grep python

A pipeline is a data-flow mechanism, not merely a sequence of commands.

With Bash's pipefail option:

    set -o pipefail

the pipeline status can reflect a failure from an earlier command.
"""
    )

    data = ["ERROR database", "INFO started", "ERROR timeout", "INFO stopped"]
    errors = [line for line in data if "ERROR" in line]

    show("Pipeline-style input", data)
    show("Pipeline-style filtering", errors)


# ---------------------------------------------------------------------------
# 15. Globbing versus regular expressions
# ---------------------------------------------------------------------------

def demonstrate_patterns() -> None:
    section("15. Globbing versus regular expressions")

    print(
        """
Shell globbing is used for pathname expansion:

    *.log
    backup-?.tar.gz

Regular expressions are a different pattern language.

Bash's [[ ... =~ ... ]] operator supports regular-expression matching.

Confusing glob syntax and regular-expression syntax is a common mistake.

Glob:
    *.log

Regular expression:
    ^.*\\.log$

The first is a shell filename pattern. The second describes a regular
expression.
"""
    )

    filenames = ["app.log", "database.txt", "worker.log", "README.md"]
    log_files = [name for name in filenames if name.endswith(".log")]
    regex_matches = [
        name for name in filenames
        if re.fullmatch(r".*\.log", name)
    ]

    show("Glob-like selection", log_files)
    show("Regex selection", regex_matches)


# ---------------------------------------------------------------------------
# 16. Temporary files and filesystem automation
# ---------------------------------------------------------------------------

def demonstrate_filesystem_automation() -> None:
    section("16. Filesystem automation")

    print(
        """
Shell scripts are frequently used to create directories, move files,
archive data, rotate logs, and clean temporary resources.

Important commands include:

    mkdir -p directory
    cp source destination
    mv source destination
    rm -- file
    find directory ...
    chmod mode file
    chown user:group file

Automation should distinguish between:
- expected missing resources,
- permission errors,
- invalid paths,
- unexpected failures.

Use temporary directories and cleanup mechanisms instead of writing
temporary files into unpredictable locations.
"""
    )

    with tempfile.TemporaryDirectory(prefix="shell-study-") as temporary:
        root = Path(temporary)
        source = root / "source.txt"
        destination_directory = root / "archive"
        destination = destination_directory / "source.txt"

        destination_directory.mkdir(parents=True, exist_ok=True)
        source.write_text("important data\n", encoding="utf-8")
        shutil.copy2(source, destination)

        show("Temporary workspace", root)
        show("Copied file exists", destination.exists())
        show("Copied content", destination.read_text(encoding="utf-8").strip())


# ---------------------------------------------------------------------------
# 17. Strict mode
# ---------------------------------------------------------------------------

def demonstrate_strict_mode() -> None:
    section("17. Bash strict mode")

    print(
        """
A commonly used Bash reliability baseline is:

    set -Eeuo pipefail

Meaning:

    -e    exit when a simple command fails, subject to Bash's rules
    -E    preserve ERR traps in functions/subshell contexts
    -u    treat unset variables as errors
    pipefail
          make a pipeline fail if a component fails

Strict mode is useful but is not a substitute for understanding Bash's
conditional-command rules. Commands used intentionally as tests can have
nonzero statuses without representing script failure.

Example:

    if grep -q "pattern" "$file"; then
        ...
    fi

is different from blindly executing grep when no match is acceptable.
"""
    )

    strict_flags = ["-e", "-E", "-u", "pipefail"]
    show("Recommended baseline", "set -Eeuo pipefail")
    show("Purpose", strict_flags)


# ---------------------------------------------------------------------------
# 18. Traps and cleanup
# ---------------------------------------------------------------------------

def demonstrate_traps() -> None:
    section("18. Traps and cleanup")

    print(
        """
trap allows a script to respond to signals or shell events.

Typical cleanup pattern:

    cleanup() {
        rm -rf -- "$temporary_directory"
    }

    trap cleanup EXIT

Other useful signals/events include:
    INT   interruption
    TERM  termination request
    HUP   hangup
    ERR   command error handling

Cleanup functions should themselves be written defensively. Temporary
resources should be uniquely named and created with safe permissions.
"""
    )

    cleanup_events = []

    def cleanup() -> None:
        cleanup_events.append("temporary resources released")

    try:
        print("Simulating work...")
    finally:
        cleanup()

    show("Cleanup result", cleanup_events)


# ---------------------------------------------------------------------------
# 19. Logging
# ---------------------------------------------------------------------------

def demonstrate_logging() -> None:
    section("19. Logging")

    print(
        """
Production automation benefits from consistent logs.

Bash often uses functions such as:

    log() {
        printf '%s [%s] %s\\n' \
            "$(date '+%Y-%m-%dT%H:%M:%S%z')" \
            "$1" \
            "$2"
    }

stderr is commonly used for diagnostic messages:

    printf 'ERROR: invalid configuration\\n' >&2

Structured logs can make automated processing easier.
"""
    )

    def log(level: str, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        print(f"{timestamp} [{level}] {message}")

    log("INFO", "automation started")
    log("INFO", "configuration validated")
    log("WARNING", "optional cache directory is absent")
    log("INFO", "automation completed")


# ---------------------------------------------------------------------------
# 20. Validation
# ---------------------------------------------------------------------------

def demonstrate_validation() -> None:
    section("20. Input validation")

    print(
        """
Never assume command-line input is safe or valid.

Validate:
- required argument count,
- allowed values,
- numeric ranges,
- paths,
- file types,
- configuration values.

A Bash script can use:

    [[ "$environment" == "development" ||
       "$environment" == "testing" ||
       "$environment" == "production" ]]

For numeric validation, regular expressions can first establish that input
has the expected form before arithmetic evaluation.

Avoid evaluating user input as shell code. Constructs such as eval can turn
data into executable code and create command-injection vulnerabilities.
"""
    )

    allowed_environments = {"development", "testing", "production"}

    for candidate in ["production", "unknown", "testing"]:
        valid = candidate in allowed_environments
        print(f"{candidate!r} -> valid={valid}")


# ---------------------------------------------------------------------------
# 21. Safe command construction
# ---------------------------------------------------------------------------

def demonstrate_command_safety() -> None:
    section("21. Safe command construction")

    print(
        """
Shell command injection can occur when untrusted text is concatenated into
a command and then interpreted by a shell.

Unsafe conceptual pattern:

    sh -c "backup $USER_INPUT"

Safer approaches:
- avoid shell evaluation when a direct API is available,
- use arrays for command arguments,
- quote shell expansions,
- validate inputs,
- use -- where supported to mark the end of options.

Bash arrays are especially useful:

    command=(grep -- "$pattern" "$file")
    "${command[@]}"

This preserves argument boundaries.
"""
    )

    user_pattern = "ERROR message"
    filename = "application log.txt"

    command_as_arguments = ["grep", "--", user_pattern, filename]

    show("Safe argument vector", command_as_arguments)
    show("Number of arguments", len(command_as_arguments))


# ---------------------------------------------------------------------------
# 22. Configuration
# ---------------------------------------------------------------------------

@dataclass
class ApplicationConfig:
    environment: str
    application_name: str
    backup_directory: Path
    retention_days: int = 7

    def validate(self) -> None:
        allowed = {"development", "testing", "production"}

        if self.environment not in allowed:
            raise ValueError(
                f"environment must be one of {sorted(allowed)}"
            )

        if not self.application_name:
            raise ValueError("application_name cannot be empty")

        if self.retention_days < 1:
            raise ValueError("retention_days must be positive")


def demonstrate_configuration() -> None:
    section("22. Configuration-driven automation")

    print(
        """
Hard-coding environment-specific values makes scripts difficult to reuse.

A production script may read:
- environment variables,
- command-line options,
- configuration files,
- secret stores,
- deployment metadata.

Configuration precedence should be explicit. Secrets should not be committed
to source control or printed into logs.
"""
    )

    config = ApplicationConfig(
        environment="production",
        application_name="inventory-api",
        backup_directory=Path("/var/backups/inventory-api"),
        retention_days=14,
    )

    config.validate()
    show("Validated configuration", config)


# ---------------------------------------------------------------------------
# 23. Idempotence
# ---------------------------------------------------------------------------

def demonstrate_idempotence() -> None:
    section("23. Idempotent automation")

    print(
        """
An operation is idempotent when repeating it produces the same desired
state after the first successful application.

Prefer:

    mkdir -p "$directory"

over logic that fails merely because the directory already exists.

For configuration management, scripts should move the system toward a
declared state rather than blindly performing the same mutation every time.
"""
    )

    with tempfile.TemporaryDirectory(prefix="idempotence-") as temporary:
        directory = Path(temporary) / "application"

        for _ in range(3):
            directory.mkdir(parents=True, exist_ok=True)

        show("Directory after three identical operations", directory.exists())


# ---------------------------------------------------------------------------
# 24. Checksums and integrity
# ---------------------------------------------------------------------------

def demonstrate_integrity() -> None:
    section("24. Checksums and file integrity")

    print(
        """
Checksums can detect accidental changes.

Common Unix tools include:

    sha256sum file

Cryptographic hashes such as SHA-256 are useful for integrity verification,
but a hash alone does not prove authenticity. If an attacker can replace
both the file and its published hash, the check can be defeated.

Authenticity requires a trusted source, signature, certificate, or equivalent
trust mechanism.
"""
    )

    content = b"release artifact\n"
    digest = hashlib.sha256(content).hexdigest()

    show("SHA-256", digest)
    show("Digest length", len(digest))


# ---------------------------------------------------------------------------
# 25. File permissions
# ---------------------------------------------------------------------------

def demonstrate_permissions() -> None:
    section("25. Unix permissions")

    print(
        """
Unix permissions commonly represent:
- owner permissions,
- group permissions,
- other permissions.

Typical modes:

    600   owner read/write
    644   owner read/write, others read
    755   owner read/write/execute, others read/execute

Scripts containing credentials or sensitive configuration should not be
world-readable.

The principle of least privilege means granting only the permissions needed
for the task.
"""
    )

    mode_examples = {
        "600": "owner read/write",
        "644": "owner read/write, others read",
        "755": "owner read/write/execute, others read/execute",
    }

    for mode, meaning in mode_examples.items():
        show(mode, meaning)

    with tempfile.TemporaryDirectory(prefix="permissions-") as temporary:
        sensitive_file = Path(temporary) / "secret.conf"
        sensitive_file.write_text("example-secret\n", encoding="utf-8")
        sensitive_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

        show(
            "Temporary sensitive file mode",
            oct(sensitive_file.stat().st_mode & 0o777),
        )


# ---------------------------------------------------------------------------
# 26. Parallel execution concepts
# ---------------------------------------------------------------------------

def demonstrate_concurrency() -> None:
    section("26. Concurrency and background jobs")

    print(
        """
Bash can start background processes with '&':

    task_a &
    task_b &
    wait

The process identifier is available through '$!'.

wait synchronizes with child processes and returns their statuses.

Parallelism can improve throughput for independent tasks, but it can also
cause:
- resource contention,
- race conditions,
- log interleaving,
- uncontrolled process growth,
- nondeterministic failures.

Concurrency should therefore be bounded rather than starting unlimited jobs.
"""
    )

    tasks = ["database-check", "cache-check", "filesystem-check"]
    start = time.perf_counter()

    # This simulation is sequential because the purpose is to explain the
    # shell mechanism without creating uncontrolled child processes.
    results = {task: "completed" for task in tasks}

    elapsed = time.perf_counter() - start

    show("Tasks", results)
    show("Simulation duration", f"{elapsed:.6f}s")


# ---------------------------------------------------------------------------
# 27. Retry strategy
# ---------------------------------------------------------------------------

def demonstrate_retries() -> None:
    section("27. Retry logic")

    print(
        """
Automation often interacts with temporary failures such as:
- network interruptions,
- service startup races,
- transient DNS failures,
- temporary file locks.

A robust retry mechanism should have:
- a maximum attempt count,
- a delay,
- a clear failure condition,
- logging,
- optional exponential backoff.

Blind infinite retries can hide permanent failures.
"""
    )

    attempts = 0
    maximum_attempts = 4
    simulated_success_on = 3

    while attempts < maximum_attempts:
        attempts += 1
        print(f"Attempt {attempts}")

        if attempts >= simulated_success_on:
            print("Operation succeeded.")
            break
    else:
        print("Operation failed after maximum attempts.")


# ---------------------------------------------------------------------------
# 28. Performance considerations
# ---------------------------------------------------------------------------

def demonstrate_performance() -> None:
    section("28. Performance considerations")

    print(
        """
Shell is excellent for orchestration: connecting mature Unix tools,
managing processes, automating deployments, and composing system commands.

It becomes less suitable when:
- processing millions of records with complex transformations,
- implementing CPU-heavy algorithms,
- maintaining large amounts of state,
- requiring sophisticated data structures,
- needing strict cross-platform behavior.

Launching many external processes can be expensive. A loop that invokes
another command for every record may be much slower than using a single
specialized command or a language with in-process processing.

Prefer simple pipelines for simple transformations and use a more suitable
language when algorithmic complexity becomes dominant.
"""
    )

    values = list(range(100_000))

    start = time.perf_counter()
    result = sum(value * value for value in values)
    elapsed = time.perf_counter() - start

    show("Processed values", len(values))
    show("Calculated result", result)
    show("Elapsed time", f"{elapsed:.6f}s")


# ---------------------------------------------------------------------------
# 29. Testing shell scripts
# ---------------------------------------------------------------------------

def demonstrate_testing() -> None:
    section("29. Testing automation scripts")

    print(
        """
Shell scripts deserve tests just like application code.

Test:
- successful execution,
- invalid arguments,
- missing files,
- permission failures,
- empty input,
- unusual filenames,
- repeated execution,
- interrupted execution,
- partial failure,
- cleanup behavior.

A useful design technique is separating:
- argument parsing,
- validation,
- business logic,
- side effects,
- output.

Small functions are easier to test than one enormous script.
"""
    )

    def validate_port(port: int) -> bool:
        return 1 <= port <= 65535

    test_cases = [0, 22, 443, 65535, 65536]

    for port in test_cases:
        print(f"port={port:5d} valid={validate_port(port)}")


# ---------------------------------------------------------------------------
# 30. Realistic automation case study
# ---------------------------------------------------------------------------

@dataclass
class DeploymentState:
    application: str
    version: str
    environment: str
    deployed_version: str | None = None
    health_checks: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


class DeploymentAutomation:
    """
    A safe Python model of a Bash deployment script.

    The class represents operations that a real Bash script could orchestrate:
    validate configuration, prepare directories, verify an artifact, deploy,
    run health checks, and roll back if necessary.
    """

    ALLOWED_ENVIRONMENTS = {"development", "testing", "production"}

    def __init__(self, state: DeploymentState):
        self.state = state

    def log(self, level: str, message: str) -> None:
        entry = f"[{level}] {message}"
        self.state.logs.append(entry)
        print(entry)

    def validate(self) -> None:
        if self.state.environment not in self.ALLOWED_ENVIRONMENTS:
            raise ValueError("unsupported environment")

        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.state.application):
            raise ValueError("invalid application name")

        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.state.version):
            raise ValueError("invalid version")

        self.log("INFO", "configuration validated")

    def prepare(self) -> None:
        self.log("INFO", "deployment workspace prepared")

    def verify_artifact(self) -> None:
        self.log("INFO", "artifact integrity verified")

    def deploy(self) -> None:
        self.state.deployed_version = self.state.version
        self.log(
            "INFO",
            f"{self.state.application} deployed at version "
            f"{self.state.version}",
        )

    def health_check(self) -> bool:
        checks = ["process", "port", "application"]

        for check in checks:
            self.state.health_checks.append(check)
            self.log("INFO", f"health check passed: {check}")

        return True

    def rollback(self, previous_version: str | None) -> None:
        self.state.deployed_version = previous_version
        self.log(
            "WARNING",
            f"rollback completed to {previous_version!r}",
        )

    def run(self, previous_version: str | None = None) -> bool:
        self.validate()
        self.prepare()
        self.verify_artifact()
        self.deploy()

        if not self.health_check():
            self.rollback(previous_version)
            return False

        self.log("INFO", "deployment completed successfully")
        return True


def demonstrate_deployment_case_study() -> None:
    section("31. Industry-style deployment automation case study")

    print(
        """
A common Bash use case is deployment orchestration.

A production deployment script might:
1. parse command-line options,
2. validate the environment,
3. verify required tools,
4. load configuration,
5. check the artifact,
6. create a release directory,
7. deploy the artifact,
8. restart or reload a service,
9. execute health checks,
10. record the result,
11. roll back when necessary.

Bash is useful here because it can coordinate operating-system commands,
service managers, filesystem operations, environment variables, and other
Unix utilities.

The Python implementation below models the same architecture while keeping
side effects controlled.
"""
    )

    state = DeploymentState(
        application="inventory-api",
        version="2026.09.19",
        environment="production",
    )

    automation = DeploymentAutomation(state)
    success = automation.run(previous_version="2026.09.18")

    show("Deployment success", success)
    show("Deployed version", state.deployed_version)
    show("Health checks", state.health_checks)


# ---------------------------------------------------------------------------
# 32. Shell script architecture
# ---------------------------------------------------------------------------

def demonstrate_architecture() -> None:
    section("32. Production shell-script architecture")

    print(
        """
A maintainable Bash automation script often follows this structure:

    #!/usr/bin/env bash
    set -Eeuo pipefail

    readonly SCRIPT_NAME="$(basename "$0")"

    usage() {
        ...
    }

    log() {
        ...
    }

    cleanup() {
        ...
    }

    validate_environment() {
        ...
    }

    main() {
        ...
    }

    trap cleanup EXIT
    main "$@"

The exact organization depends on complexity, but the principles are
stable:
- fail deliberately,
- validate early,
- quote expansions,
- isolate functions,
- keep side effects understandable,
- log important state transitions,
- clean up temporary resources,
- make repeated execution safe where possible.
"""
    )


# ---------------------------------------------------------------------------
# 33. Common mistakes
# ---------------------------------------------------------------------------

def demonstrate_common_mistakes() -> None:
    section("33. Common shell-scripting mistakes")

    mistakes = {
        "Unquoted variables":
            'rm $file',
        "Safer quoting":
            'rm -- "$file"',
        "Parsing ls output":
            'for file in $(ls)',
        "Safer filename iteration":
            'for file in *; do ...; done',
        "Ignoring exit status":
            'command',
        "Explicit error handling":
            'if ! command; then ...; fi',
        "Unsafe evaluation":
            'eval "$user_input"',
        "Safer argument handling":
            '"${command[@]}"',
    }

    for label, example in mistakes.items():
        print(f"{label}: {example}")


# ---------------------------------------------------------------------------
# 34. Bash-specific subtleties
# ---------------------------------------------------------------------------

def demonstrate_subtleties() -> None:
    section("34. Bash-specific subtleties")

    print(
        """
Important Bash behavior includes:

1. Word splitting
   Unquoted parameter expansions can become multiple words.

2. Filename expansion
   Wildcards such as '*' may expand into filenames.

3. Empty globs
   Depending on shell options, an unmatched wildcard may remain literal.
   'nullglob' can change this behavior.

4. set -e exceptions
   errexit does not mean "abort after every nonzero status". Bash has
   contextual rules around conditions, pipelines, lists, and functions.

5. Subshells
   Parentheses create a subshell environment:

       (cd /tmp; echo "$PWD")

   Changes inside normally do not affect the parent shell.

6. Command grouping
   Braces group commands in the current shell:

       { command1; command2; }

7. Process substitution
   Bash can provide command output as a pseudo-file:

       diff <(sort file1) <(sort file2)

8. Here documents
   Multi-line input can be supplied with:

       command <<EOF
       text
       EOF

9. Here strings
   A string can be supplied as stdin:

       grep pattern <<< "$text"

These features are powerful but increase complexity. They should be used
when they make the script clearer rather than merely shorter.
"""
    )


# ---------------------------------------------------------------------------
# 35. Practical shell checklist
# ---------------------------------------------------------------------------

def print_production_checklist() -> None:
    section("35. Production shell scripting checklist")

    checklist = [
        "Use an explicit Bash shebang when Bash features are required.",
        "Use set -Eeuo pipefail where appropriate and understand its semantics.",
        "Quote variable expansions unless word splitting is intentional.",
        "Use arrays for command arguments instead of string-built commands.",
        "Validate external input before using it.",
        "Avoid eval with untrusted data.",
        "Check command exit statuses.",
        "Use -- before user-controlled filenames where supported.",
        "Use temporary directories instead of predictable temporary filenames.",
        "Clean up resources with trap.",
        "Do not expose credentials in logs or process arguments.",
        "Use least-privilege permissions.",
        "Make automation idempotent when possible.",
        "Bound retries and concurrency.",
        "Log meaningful state transitions.",
        "Test failure paths, not only successful paths.",
        "Use a more suitable language when shell becomes an application runtime.",
    ]

    for item in checklist:
        print(f"[ ] {item}")


# ---------------------------------------------------------------------------
# 36. Main program
# ---------------------------------------------------------------------------

def main() -> None:
    print(
        """
SHELL SCRIPTING WITH BASH
=========================

This executable study companion progresses from basic shell concepts to
production-oriented automation design.
"""
    )

    demonstrate_shell_fundamentals()
    demonstrate_variables()
    demonstrate_environment_variables()
    demonstrate_quoting()
    demonstrate_command_substitution()
    demonstrate_exit_status()
    demonstrate_conditions()
    demonstrate_case()
    demonstrate_loops()
    demonstrate_functions()
    demonstrate_arguments()
    demonstrate_arrays()
    demonstrate_file_processing()
    demonstrate_redirection()
    demonstrate_patterns()
    demonstrate_filesystem_automation()
    demonstrate_strict_mode()
    demonstrate_traps()
    demonstrate_logging()
    demonstrate_validation()
    demonstrate_command_safety()
    demonstrate_configuration()
    demonstrate_idempotence()
    demonstrate_integrity()
    demonstrate_permissions()
    demonstrate_concurrency()
    demonstrate_retries()
    demonstrate_performance()
    demonstrate_testing()
    demonstrate_deployment_case_study()
    demonstrate_architecture()
    demonstrate_common_mistakes()
    demonstrate_subtleties()
    print_production_checklist()

    section("End of executable study companion")
    print("The examples completed successfully.")


if __name__ == "__main__":
    main()
