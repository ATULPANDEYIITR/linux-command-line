#!/usr/bin/env python3
"""
Processes and Services
======================

A standalone study program covering:

- Processes and programs
- Process identifiers and parent/child relationships
- Process states
- Environment and command-line arguments
- Threads
- CPU-bound and I/O-bound work
- Threading, multiprocessing, and subprocesses
- Process monitoring
- Signals
- Graceful and forced termination
- Service concepts
- Linux /proc process inspection
- systemd concepts and practical command execution
- Resource limits and process priority
- Logging, timeouts, failure handling
- Security and production considerations

The program uses only the Python standard library.

The process-monitoring examples are most informative on Linux because
/proc and systemd are Linux facilities. The remaining examples work on
other operating systems with appropriate platform differences.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def heading(title: str) -> None:
    """Print a consistent section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def show_result(label: str, value: object) -> None:
    print(f"{label:<28}: {value}")


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def demonstrate_process_identity() -> None:
    heading("1. Process identity")

    show_result("Operating system", platform.system())
    show_result("Process ID (PID)", os.getpid())
    show_result("Parent PID", os.getppid())
    show_result("Executable", sys.executable)
    show_result("Python version", platform.python_version())
    show_result("Current working directory", os.getcwd())

    # sys.argv contains the command-line arguments supplied to this process.
    show_result("Command-line arguments", sys.argv)

    # Environment variables belong to the process environment.
    show_result("PATH available", bool(os.environ.get("PATH")))


# ---------------------------------------------------------------------------
# Process states and /proc
# ---------------------------------------------------------------------------

def read_proc_file(pid: int, filename: str) -> Optional[str]:
    """Read a Linux /proc file, returning None if it is unavailable."""
    path = Path("/proc") / str(pid) / filename
    try:
        return path.read_text(errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        return None


def parse_proc_status(pid: int) -> dict[str, str]:
    """Parse selected fields from /proc/<pid>/status."""
    text = read_proc_file(pid, "status")
    if text is None:
        return {}

    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def demonstrate_proc_inspection() -> None:
    heading("2. Linux /proc process inspection")

    if platform.system() != "Linux":
        print("/proc is Linux-specific; this section is skipped.")
        return

    pid = os.getpid()
    status = parse_proc_status(pid)

    for field in (
        "Name",
        "State",
        "Pid",
        "PPid",
        "Threads",
        "VmSize",
        "VmRSS",
    ):
        show_result(field, status.get(field, "unavailable"))

    cmdline = read_proc_file(pid, "cmdline")
    if cmdline is not None:
        arguments = cmdline.replace("\x00", " ").strip()
        show_result("Kernel-visible command line", arguments)

    # /proc/<pid>/fd contains symbolic links for open file descriptors.
    fd_directory = Path("/proc") / str(pid) / "fd"
    try:
        descriptors = list(fd_directory.iterdir())
        show_result("Open file descriptor count", len(descriptors))
    except (PermissionError, FileNotFoundError, OSError):
        show_result("Open file descriptor count", "unavailable")


def list_linux_pids(limit: int = 20) -> list[int]:
    """Return a small sorted list of numeric Linux process IDs."""
    if platform.system() != "Linux":
        return []

    pids = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            pids.append(int(entry.name))
    return sorted(pids)[:limit]


def demonstrate_process_enumeration() -> None:
    heading("3. Process enumeration")

    if platform.system() != "Linux":
        print("Process enumeration example uses Linux /proc.")
        return

    for pid in list_linux_pids():
        status = parse_proc_status(pid)
        name = status.get("Name", "?")
        state = status.get("State", "?")
        parent = status.get("PPid", "?")
        print(f"PID={pid:<7} PPID={parent:<7} STATE={state:<24} NAME={name}")


# ---------------------------------------------------------------------------
# Subprocesses
# ---------------------------------------------------------------------------

def demonstrate_subprocess() -> None:
    heading("4. Creating and controlling a child process")

    # subprocess.run creates a child process and waits for it.
    completed = subprocess.run(
        [sys.executable, "-c", "print('child process says hello')"],
        text=True,
        capture_output=True,
        check=False,
    )

    show_result("Return code", completed.returncode)
    show_result("Captured stdout", completed.stdout.strip())
    show_result("Captured stderr", completed.stderr.strip() or "<empty>")

    # Passing an argument explicitly is safer than building a shell command
    # from untrusted strings.
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", "safe argument"],
        text=True,
        capture_output=True,
        check=True,
    )
    show_result("Explicit argument", completed.stdout.strip())


def demonstrate_process_timeout() -> None:
    heading("5. Process timeout")

    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(10); print('finished')",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        stdout, stderr = child.communicate(timeout=0.5)
        show_result("Child output", stdout.strip())
    except subprocess.TimeoutExpired:
        print("Timeout reached; terminating the child.")
        child.terminate()

        try:
            stdout, stderr = child.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            print("Child ignored graceful termination; forcing termination.")
            child.kill()
            stdout, stderr = child.communicate()

        show_result("Final return code", child.returncode)
        show_result("Remaining stdout", stdout.strip())
        show_result("Remaining stderr", stderr.strip())


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def demonstrate_threads() -> None:
    heading("6. Threads")

    # Threads share the same process address space. A lock protects shared
    # mutable state when multiple threads update it.
    counter = 0
    lock = threading.Lock()

    def worker(iterations: int) -> None:
        nonlocal counter
        for _ in range(iterations):
            with lock:
                counter += 1

    threads = [
        threading.Thread(target=worker, args=(10_000,), name=f"worker-{i}")
        for i in range(4)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    show_result("Expected shared counter", 40_000)
    show_result("Actual shared counter", counter)
    show_result("Current thread", threading.current_thread().name)


def demonstrate_thread_exception_and_daemon() -> None:
    heading("7. Thread lifecycle and exception behavior")

    errors: queue.Queue[str] = queue.Queue()

    def risky_worker() -> None:
        try:
            raise ValueError("demonstration exception")
        except ValueError as exc:
            errors.put(str(exc))

    worker = threading.Thread(target=risky_worker, name="exception-worker")
    worker.start()
    worker.join()

    show_result("Worker alive after join", worker.is_alive())
    show_result("Captured worker error", errors.get_nowait())

    # A daemon thread does not keep the Python process alive. It should not
    # be used for work that must be completed or persisted.
    stop_event = threading.Event()

    def daemon_worker() -> None:
        while not stop_event.wait(0.05):
            pass

    daemon = threading.Thread(
        target=daemon_worker,
        name="daemon-worker",
        daemon=True,
    )
    daemon.start()
    show_result("Daemon thread", daemon.daemon)
    stop_event.set()
    daemon.join(timeout=1)


# ---------------------------------------------------------------------------
# CPU work and process parallelism
# ---------------------------------------------------------------------------

def is_prime(number: int) -> bool:
    if number < 2:
        return False
    if number == 2:
        return True
    if number % 2 == 0:
        return False

    divisor = 3
    while divisor * divisor <= number:
        if number % divisor == 0:
            return False
        divisor += 2
    return True


def count_primes(start: int, end: int) -> int:
    return sum(is_prime(number) for number in range(start, end))


def demonstrate_process_pool() -> None:
    heading("8. CPU-bound work with multiple processes")

    # ProcessPoolExecutor creates worker processes. Separate processes can
    # execute Python bytecode on separate CPU cores, unlike ordinary Python
    # threads constrained by the CPython GIL for CPU-bound Python code.
    from concurrent.futures import ProcessPoolExecutor

    ranges = [
        (100_000, 100_500),
        (100_500, 101_000),
        (101_000, 101_500),
        (101_500, 102_000),
    ]

    with ProcessPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda pair: count_primes(*pair), ranges))

    show_result("Ranges processed", len(ranges))
    show_result("Prime counts", results)
    show_result("Total primes found", sum(results))


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

_signal_received = threading.Event()


def handle_sigusr1(signum: int, frame: object) -> None:
    """A signal handler should do minimal work."""
    print(f"Signal handler received signal {signum}")
    _signal_received.set()


def demonstrate_signals() -> None:
    heading("9. Signals")

    if not hasattr(signal, "SIGUSR1"):
        print("SIGUSR1 is unavailable on this platform.")
        return

    signal.signal(signal.SIGUSR1, handle_sigusr1)

    print("Sending SIGUSR1 to the current process.")
    os.kill(os.getpid(), signal.SIGUSR1)

    if _signal_received.wait(timeout=1):
        print("Signal was processed successfully.")
    else:
        print("Signal was not observed within the timeout.")


def demonstrate_graceful_child_shutdown() -> None:
    heading("10. Graceful process shutdown")

    child_code = """
import signal
import sys
import time

running = True

def shutdown(signum, frame):
    global running
    print("child: shutdown requested", flush=True)
    running = False

signal.signal(signal.SIGTERM, shutdown)

while running:
    print("child: working", flush=True)
    time.sleep(0.1)

print("child: cleanup complete", flush=True)
"""

    if platform.system() == "Windows":
        print("POSIX SIGTERM behavior differs on Windows; demonstration skipped.")
        return

    child = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(0.25)
    child.send_signal(signal.SIGTERM)

    stdout, stderr = child.communicate(timeout=2)

    show_result("Child return code", child.returncode)
    print("Child output:")
    print(stdout.strip())
    if stderr.strip():
        print("Child error output:")
        print(stderr.strip())


# ---------------------------------------------------------------------------
# Resource usage and process monitoring
# ---------------------------------------------------------------------------

@dataclass
class ProcessSnapshot:
    pid: int
    name: str
    state: str
    parent_pid: str
    threads: str
    resident_memory: str


def get_process_snapshot(pid: int) -> Optional[ProcessSnapshot]:
    status = parse_proc_status(pid)
    if not status:
        return None

    return ProcessSnapshot(
        pid=pid,
        name=status.get("Name", "?"),
        state=status.get("State", "?"),
        parent_pid=status.get("PPid", "?"),
        threads=status.get("Threads", "?"),
        resident_memory=status.get("VmRSS", "?"),
    )


def demonstrate_monitoring() -> None:
    heading("11. Lightweight process monitoring")

    if platform.system() != "Linux":
        print("This monitor uses /proc and therefore requires Linux.")
        return

    for pid in list_linux_pids(limit=10):
        snapshot = get_process_snapshot(pid)
        if snapshot:
            print(
                f"PID={snapshot.pid:<7} "
                f"NAME={snapshot.name:<20} "
                f"STATE={snapshot.state:<24} "
                f"THREADS={snapshot.threads:<5} "
                f"RSS={snapshot.resident_memory}"
            )


# ---------------------------------------------------------------------------
# Process tree
# ---------------------------------------------------------------------------

def demonstrate_process_tree() -> None:
    heading("12. Parent-child relationships")

    if platform.system() != "Linux":
        print("The process-tree example uses /proc.")
        return

    records = []
    for pid in list_linux_pids(limit=50):
        status = parse_proc_status(pid)
        if status:
            records.append(
                (
                    pid,
                    status.get("PPid", "?"),
                    status.get("Name", "?"),
                )
            )

    for pid, parent, name in records:
        print(f"PID={pid:<7} PPID={parent:<7} {name}")


# ---------------------------------------------------------------------------
# File descriptors and service-like work
# ---------------------------------------------------------------------------

def demonstrate_file_descriptor_lifecycle() -> None:
    heading("13. File descriptors and process resources")

    with tempfile.NamedTemporaryFile(
        mode="w+",
        prefix="process-study-",
        delete=False,
    ) as temporary:
        path = Path(temporary.name)
        temporary.write("resource lifecycle demonstration\n")
        temporary.flush()

        print(f"Temporary file created: {path}")
        print(f"File descriptor: {temporary.fileno()}")

        temporary.seek(0)
        print(f"Read data: {temporary.read().strip()}")

    # The descriptor is automatically closed by the context manager.
    try:
        path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Service abstraction
# ---------------------------------------------------------------------------

@dataclass
class ServiceResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


def run_service_command(arguments: Iterable[str]) -> ServiceResult:
    """
    Run systemctl safely without a shell.

    This function does not require root privileges for read-only commands.
    Administrative service changes generally require appropriate privileges.
    """
    command = ["systemctl", *arguments]

    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return ServiceResult(command, 127, "", "systemctl is not installed")
    except subprocess.TimeoutExpired:
        return ServiceResult(command, 124, "", "systemctl command timed out")

    return ServiceResult(
        command=command,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def demonstrate_systemd() -> None:
    heading("14. systemd and systemctl")

    if platform.system() != "Linux":
        print("systemd is primarily a Linux service manager; section skipped.")
        return

    # systemctl --version checks whether systemctl is available.
    result = run_service_command(["--version"])

    show_result("systemctl return code", result.return_code)

    if result.stdout:
        print(result.stdout.splitlines()[0])

    if result.stderr:
        print(result.stderr.strip())

    # list-units is read-only and demonstrates querying the service manager.
    result = run_service_command(
        ["list-units", "--type=service", "--no-pager", "--no-legend"]
    )

    if result.return_code == 0:
        services = result.stdout.splitlines()
        print(f"Visible active service units: {len(services)}")
        for line in services[:5]:
            print(line)
    else:
        print("Unable to query active services.")
        if result.stderr:
            print(result.stderr.strip())


# ---------------------------------------------------------------------------
# Service architecture model
# ---------------------------------------------------------------------------

class ManagedService:
    """
    A small in-process model of a long-running service.

    A real systemd service is an operating-system process managed by PID 1
    (systemd on systems using systemd). This class models the application
    portion only.
    """

    def __init__(self, name: str):
        self.name = name
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("service is already running")

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"service-{self.name}",
        )
        self._thread.start()

    def _run(self) -> None:
        print(f"{self.name}: started")
        while not self._stop.wait(0.05):
            pass
        print(f"{self.name}: stopping")

    def stop(self, timeout: float = 2.0) -> None:
        if not self._thread:
            return

        self._stop.set()
        self._thread.join(timeout=timeout)

        if self._thread.is_alive():
            raise TimeoutError(f"{self.name} did not stop in time")

        print(f"{self.name}: stopped")


def demonstrate_service_lifecycle() -> None:
    heading("15. Service lifecycle")

    service = ManagedService("example-worker")
    service.start()
    time.sleep(0.1)
    service.stop()


# ---------------------------------------------------------------------------
# Security considerations
# ---------------------------------------------------------------------------

def demonstrate_safe_subprocess_rules() -> None:
    heading("16. Secure process execution")

    # Prefer argument arrays over shell=True.
    safe = subprocess.run(
        [sys.executable, "-c", "print(2 + 3)"],
        capture_output=True,
        text=True,
        check=True,
    )

    show_result("Safe command output", safe.stdout.strip())

    # Never interpolate untrusted input into a shell command.
    #
    # Dangerous pattern:
    # subprocess.run(f"some-command {user_input}", shell=True)
    #
    # Safer pattern:
    # subprocess.run(["some-command", user_input], shell=False)
    #
    # The example above is intentionally not executed because the executable
    # is not guaranteed to exist on every platform.


# ---------------------------------------------------------------------------
# Error handling and defensive monitoring
# ---------------------------------------------------------------------------

def wait_for_process(
    process: subprocess.Popen[str],
    timeout: float,
) -> tuple[bool, Optional[int]]:
    """Wait for a process without blocking indefinitely."""
    try:
        return True, process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, None


def demonstrate_defensive_lifecycle() -> None:
    heading("17. Defensive lifecycle management")

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.2)"]
    )

    completed, return_code = wait_for_process(child, timeout=1)

    if completed:
        print(f"Child completed normally with return code {return_code}.")
    else:
        print("Child exceeded timeout; terminating it.")
        child.terminate()
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

    show_result("Final child state", child.poll())


# ---------------------------------------------------------------------------
# Performance considerations
# ---------------------------------------------------------------------------

def demonstrate_process_vs_thread_concepts() -> None:
    heading("18. Process versus thread characteristics")

    characteristics = {
        "Process": {
            "memory": "Separate virtual address space",
            "failure isolation": "Higher",
            "communication": "IPC required for sharing",
            "creation cost": "Usually higher",
            "CPU parallelism": "Strong",
        },
        "Thread": {
            "memory": "Shared process address space",
            "failure isolation": "Lower",
            "communication": "Shared memory is direct",
            "creation cost": "Usually lower",
            "CPU parallelism": "Depends on runtime and workload",
        },
    }

    print(json.dumps(characteristics, indent=2))


# ---------------------------------------------------------------------------
# Advanced: worker process protocol
# ---------------------------------------------------------------------------

def worker_process(input_queue, output_queue) -> None:
    """
    Worker function used by multiprocessing.Queue.

    Queue communication is a form of inter-process communication. Objects are
    serialized between processes rather than simply sharing Python objects.
    """
    while True:
        task = input_queue.get()
        if task is None:
            break

        task_id, number = task
        output_queue.put((task_id, number * number))


def demonstrate_multiprocessing_ipc() -> None:
    heading("19. Inter-process communication with multiprocessing")

    import multiprocessing

    input_queue = multiprocessing.Queue()
    output_queue = multiprocessing.Queue()

    process = multiprocessing.Process(
        target=worker_process,
        args=(input_queue, output_queue),
        name="square-worker",
    )
    process.start()

    for task_id, number in enumerate([2, 5, 9, 12]):
        input_queue.put((task_id, number))

    results = [output_queue.get(timeout=2) for _ in range(4)]

    # A sentinel tells the worker to leave its loop.
    input_queue.put(None)
    process.join(timeout=2)

    if process.is_alive():
        process.terminate()
        process.join()

    print("IPC results:", sorted(results))
    show_result("Worker exit code", process.exitcode)


# ---------------------------------------------------------------------------
# Scheduling and priorities
# ---------------------------------------------------------------------------

def demonstrate_priority() -> None:
    heading("20. Process priority")

    if hasattr(os, "getpriority"):
        try:
            current_priority = os.getpriority(os.PRIO_PROCESS, os.getpid())
            show_result("Current nice value", current_priority)
        except OSError as exc:
            show_result("Priority query error", exc)
    else:
        print("Process priority APIs are unavailable on this platform.")

    print(
        "Changing priority can affect scheduling and may require privileges. "
        "A production service should not arbitrarily change priority."
    )


# ---------------------------------------------------------------------------
# Mini process supervisor
# ---------------------------------------------------------------------------

class ProcessSupervisor:
    """
    Minimal restart-on-failure supervisor.

    This is educational only. Production systems should generally use a
    mature service manager such as systemd rather than reinventing one.
    """

    def __init__(self, command: list[str], max_restarts: int = 2):
        self.command = command
        self.max_restarts = max_restarts
        self.restart_count = 0

    def run(self) -> int:
        while True:
            print(f"Supervisor starting: {self.command}")

            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate()
            print(f"Child exited with code {process.returncode}")

            if stdout.strip():
                print(stdout.strip())

            if stderr.strip():
                print(stderr.strip())

            if process.returncode == 0:
                return 0

            if self.restart_count >= self.max_restarts:
                print("Restart limit reached.")
                return process.returncode

            self.restart_count += 1
            delay = min(2 ** self.restart_count, 10)
            print(f"Restarting after {delay} second(s).")
            time.sleep(delay)


def demonstrate_supervisor() -> None:
    heading("21. Minimal process supervisor")

    # The child intentionally exits unsuccessfully once. The supervisor then
    # restarts it and reaches a successful exit.
    command = [
        sys.executable,
        "-c",
        (
            "import os; "
            "marker=os.path.exists('supervisor-marker.tmp'); "
            "open('supervisor-marker.tmp','a').close(); "
            "print('child attempt, marker=', marker); "
            "raise SystemExit(0 if marker else 1)"
        ),
    ]

    marker = Path("supervisor-marker.tmp")
    try:
        if marker.exists():
            marker.unlink()

        supervisor = ProcessSupervisor(command, max_restarts=2)
        code = supervisor.run()
        show_result("Supervisor final code", code)
    finally:
        try:
            marker.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Educational calculations
# ---------------------------------------------------------------------------

def demonstrate_resource_metrics() -> None:
    heading("22. Resource metrics and interpretation")

    # CPU utilization is conceptually:
    #
    #     busy CPU time / elapsed observation time
    #
    # Operating systems expose different counters and APIs for obtaining the
    # exact values. A single instantaneous measurement is often misleading.
    process_count = len(list_linux_pids()) if platform.system() == "Linux" else None
    cpu_count = os.cpu_count()

    show_result("Logical CPU count", cpu_count)
    show_result("Observed process sample", process_count)

    memory_example_bytes = 512 * 1024 * 1024
    gib = memory_example_bytes / (1024 ** 3)
    show_result("Example memory in GiB", f"{gib:.3f}")


# ---------------------------------------------------------------------------
# Testing concepts
# ---------------------------------------------------------------------------

def test_prime_function() -> None:
    assert is_prime(2)
    assert is_prime(97)
    assert not is_prime(1)
    assert not is_prime(100)
    assert not is_prime(-5)


def test_snapshot_self() -> None:
    snapshot = get_process_snapshot(os.getpid())
    if platform.system() == "Linux":
        assert snapshot is not None
        assert snapshot.pid == os.getpid()


def run_tests() -> None:
    heading("23. Embedded tests")
    test_prime_function()
    test_snapshot_self()
    print("All embedded tests passed.")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Processes, threads, signals, services, and systemd study program."
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run the main demonstrations without the longer examples.",
    )
    parser.add_argument(
        "--systemd",
        action="store_true",
        help="Run only the systemd/systemctl demonstration.",
    )
    parser.add_argument(
        "--tests",
        action="store_true",
        help="Run embedded tests.",
    )
    args = parser.parse_args()

    if args.tests:
        run_tests()
        return

    if args.systemd:
        demonstrate_systemd()
        return

    heading("Processes and Services: executable study program")
    print("This program is running as a process.")
    print(f"PID: {os.getpid()}")

    demonstrate_process_identity()
    demonstrate_proc_inspection()
    demonstrate_process_enumeration()
    demonstrate_subprocess()
    demonstrate_process_timeout()
    demonstrate_threads()

    if not args.quick:
        demonstrate_thread_exception_and_daemon()
        demonstrate_process_pool()
        demonstrate_signals()
        demonstrate_graceful_child_shutdown()
        demonstrate_monitoring()
        demonstrate_process_tree()
        demonstrate_file_descriptor_lifecycle()
        demonstrate_systemd()
        demonstrate_service_lifecycle()
        demonstrate_safe_subprocess_rules()
        demonstrate_defensive_lifecycle()
        demonstrate_process_vs_thread_concepts()
        demonstrate_multiprocessing_ipc()
        demonstrate_priority()
        demonstrate_supervisor()
        demonstrate_resource_metrics()
    else:
        print("\nQuick mode enabled; advanced demonstrations were skipped.")

    run_tests()

    heading("Study complete")
    print("Review the source comments and execute individual sections to experiment.")


if __name__ == "__main__":
    # The multiprocessing examples require a protected entry point,
    # especially on platforms using the spawn start method.
    main()
