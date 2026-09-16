# Processes and services

## Topic introduction

A process is a running instance of a program. When an operating system starts a program, it creates a process with its own virtual address space, operating-system resources, identifiers, security credentials, scheduling information, and execution state.

A service is a long-running process or group of processes that performs a background function such as serving HTTP requests, processing jobs, collecting metrics, running scheduled tasks, or managing infrastructure components.

A thread is an execution path within a process. Threads in the same process normally share the process address space and many process resources, while separate processes provide stronger isolation.

Linux provides several mechanisms for inspecting and controlling processes. The `/proc` pseudo-filesystem exposes kernel-maintained process information, while `systemd` commonly acts as the service manager and process supervisor on modern Linux systems.

The three implementations in this repository examine the subject from complementary perspectives:

- Python demonstrates high-level process creation, subprocess management, threads, multiprocessing, signals, monitoring, IPC, and service concepts.
- JavaScript demonstrates Node.js process APIs, asynchronous child-process management, signals, worker threads, IPC, memory metrics, and service-oriented application behavior.
- C++ develops a Linux-oriented technical case study using operating-system process primitives such as `fork`, `exec`, `waitpid`, pipes, signals, threads, and `/proc`.

## Fundamental concepts

### Program versus process

A program is a static collection of instructions and data stored on a filesystem. A process is a live execution instance of that program.

The same executable can have multiple processes running simultaneously. Each process can have a different PID, environment, command-line configuration, memory state, open resources, and execution history.

### Process identifier

A process identifier, or PID, uniquely identifies a process within the relevant operating-system PID namespace.

The Python implementation obtains the current PID with `os.getpid()`. Node.js exposes it through `process.pid`. The C++ implementation uses the POSIX `getpid()` function.

A PID should not be treated as a permanent identity. Once a process terminates, its PID can eventually be reused.

### Parent and child processes

Processes commonly have parent-child relationships.

A parent process can create a child process. The child may execute the same program image or replace its process image with another executable.

The parent PID is exposed by Python through `os.getppid()`, by Node.js through `process.ppid`, and by Linux through fields such as `PPid` in `/proc/<pid>/status`.

Parent-child relationships are important for supervision, cleanup, process trees, and understanding how applications were started.

### Process isolation

Separate processes normally have separate virtual address spaces. A memory address used by one process does not normally provide direct access to another process's memory.

This isolation is one of the major distinctions between processes and threads.

Process isolation improves fault containment and security boundaries, but communication between processes requires mechanisms such as pipes, sockets, shared memory, message queues, or other forms of IPC.

## Process states

Operating systems maintain execution states for processes and threads.

Typical Linux process-state concepts include:

- Running or runnable
- Sleeping
- Uninterruptible sleep
- Stopped
- Zombie
- Dead or terminated

The exact state representation depends on the operating system and kernel interface.

A process that is sleeping is not necessarily broken. It may simply be waiting for I/O, a timer, a lock, a network event, or another resource.

A zombie is a terminated child whose exit status has not yet been collected by its parent. Proper parent-side waiting prevents zombie accumulation.

## The `/proc` filesystem

Linux exposes process information through the `/proc` pseudo-filesystem.

A directory such as `/proc/1234` corresponds to PID `1234` while that process exists.

Important examples include:

- `/proc/<pid>/status` for human-readable process metadata
- `/proc/<pid>/cmdline` for command-line arguments
- `/proc/<pid>/fd` for file-descriptor information
- `/proc/<pid>/stat` for detailed process statistics
- `/proc/<pid>/task` for thread-related information
- `/proc/meminfo` for system memory information
- `/proc/cpuinfo` for processor information

The implementations intentionally handle the possibility that a process disappears between enumeration and inspection. Process tables are inherently dynamic.

A monitoring program should expect races such as:

1. Enumerate a PID.
2. The process exits.
3. Attempt to read its information.
4. The operating system reports that the path no longer exists.

This is normal and should be handled rather than treated as an exceptional system failure.

## Process creation

### Python

Python provides several levels of process control.

`subprocess.run()` is convenient when a program needs to execute another command and wait for its completion.

`subprocess.Popen()` provides lower-level lifecycle control. It allows the application to start a process, inspect its state, communicate with it, terminate it, and wait for completion.

`multiprocessing` provides process-based parallel execution within Python programs.

`ProcessPoolExecutor` provides a higher-level pool abstraction for distributing independent CPU-oriented tasks across processes.

### JavaScript

Node.js provides the `child_process` module.

`execFile()` executes an executable without requiring a shell by default and is useful when the application has a command plus explicit arguments.

`spawn()` is appropriate when the application needs streaming access to child-process input or output.

`fork()` is a Node-specific mechanism for creating another Node.js process with built-in IPC support.

### C++

On POSIX systems, process creation can be implemented using primitives such as:

- `fork()`
- `exec()`
- `wait()`
- `waitpid()`

`fork()` creates a child process. The child can then call an `exec` family function to replace its process image with another program.

The C++ case study uses `fork()` followed by `execl()` and then uses `waitpid()` in the parent.

## `fork`, `exec`, and `waitpid`

These operations illustrate a fundamental POSIX process model.

`fork()` creates a child process.

After `fork()`, both parent and child continue from approximately the same program point, but they have different process identities.

The return value distinguishes them:

- `-1` indicates failure.
- `0` indicates the child.
- A positive value in the parent represents the child's PID.

`exec` replaces the current process image with another executable. It does not create an additional process by itself.

`waitpid()` allows the parent to collect a child's termination status.

A typical parent-child sequence is:

1. Parent calls `fork()`.
2. Child is created.
3. Child calls `exec`.
4. Child performs its work.
5. Child terminates.
6. Parent calls `waitpid`.
7. Parent receives the exit status.

This distinction between process creation and process-image replacement is fundamental to POSIX process management.

## Exit status

A process normally terminates with an exit status.

Conventionally, zero indicates successful completion and nonzero values indicate some type of failure.

The exact meaning of a nonzero code is application-specific.

The C++ implementation examines `waitpid()` results with `WIFEXITED()` and `WEXITSTATUS()`.

A process may also terminate because of a signal. The C++ implementation detects this with `WIFSIGNALED()` and retrieves the terminating signal with `WTERMSIG()`.

## Threads

A thread is an execution path within a process.

Threads normally share:

- Process address space
- Heap
- Global variables
- Open resources associated with the process

Each thread still has execution-specific state such as:

- Stack
- Registers
- Program counter
- Scheduling state
- Thread identifier

Shared memory makes communication efficient but introduces synchronization problems.

## Race conditions

A race condition occurs when the correctness of a program depends on the timing or ordering of concurrent operations.

For example, a shared counter updated by multiple threads can lose increments if multiple threads perform a read-modify-write sequence simultaneously.

The Python implementation uses `threading.Lock` to protect shared mutable state.

The C++ implementation uses `std::atomic` for a counter.

An atomic operation can provide synchronization for specific operations without requiring a traditional mutex.

Neither approach should be selected automatically. The synchronization mechanism must match the data and correctness requirements.

## Mutexes and locks

A mutex provides exclusive access to a critical section.

The Python example uses:

`with lock:`

to establish a protected region.

C++ commonly uses `std::mutex` together with `std::lock_guard` or `std::unique_lock`.

Locks provide correctness but can reduce concurrency. Poor locking design can also cause:

- Deadlocks
- Lock contention
- Priority inversion
- Reduced throughput

Critical sections should generally be small and clearly defined.

## Processes versus threads

| Property | Process | Thread |
|---|---|---|
| Address space | Normally separate | Shared within process |
| Isolation | Stronger | Weaker |
| Communication | IPC mechanisms | Shared memory or messaging |
| Creation overhead | Usually higher | Usually lower |
| Failure containment | Usually stronger | Usually weaker |
| Shared-state complexity | Lower by default | Higher |
| Memory duplication | Separate process memory | Shared process memory |
| Scheduling | OS-managed | OS-managed |
| Suitable for isolation | Yes | Limited |
| Suitable for lightweight concurrency | Less direct | Yes |

The distinction is not simply about speed. Processes and threads provide different architectural boundaries.

## CPU-bound and I/O-bound workloads

A CPU-bound workload spends most of its time executing computations.

Examples include:

- Numerical calculations
- Image processing
- Compression
- Cryptographic calculations
- Large simulations

An I/O-bound workload spends significant time waiting for external operations.

Examples include:

- Network requests
- File operations
- Database queries
- Waiting for external services

The best concurrency model depends on the runtime, operating system, workload, and communication requirements.

The Python program demonstrates process-based parallelism for CPU-oriented work.

Node.js demonstrates worker threads for CPU-intensive JavaScript execution while keeping the primary event-driven process responsive.

## Python multiprocessing

CPython uses the Global Interpreter Lock, commonly called the GIL, for ordinary Python bytecode execution.

The GIL affects CPU-bound Python threading because only one thread can execute Python bytecode at a time within a standard CPython interpreter state.

Separate processes provide separate interpreter instances and therefore provide a common way to achieve CPU parallelism for CPU-bound Python workloads.

This does not mean processes are universally better than threads. Processes introduce:

- Higher startup overhead
- IPC overhead
- Serialization costs
- Greater memory consumption
- More complicated lifecycle management

## Node.js worker threads

Node.js uses an event-driven architecture and is highly effective for asynchronous I/O.

Worker threads provide a mechanism for executing JavaScript work in separate threads.

They are useful for CPU-intensive JavaScript operations that would otherwise block the event loop.

The JavaScript implementation creates worker threads to count prime numbers.

Worker threads should not be introduced for ordinary asynchronous I/O that can already be handled efficiently by Node.js's asynchronous APIs.

## Node.js child processes

The JavaScript implementation demonstrates three major child-process mechanisms.

### `execFile`

`execFile()` runs an executable with an explicit argument list.

This is useful for commands where output can reasonably be collected.

### `spawn`

`spawn()` provides streaming access to process input and output.

It is useful when a child produces continuous output or when the parent needs fine-grained lifecycle control.

### `fork`

Node.js `fork()` creates another Node.js process and establishes an IPC channel.

This is different from a worker thread. A forked process provides process-level isolation.

## Subprocess security

Applications frequently need to invoke external programs. This creates an important security boundary.

Avoid constructing shell commands by concatenating untrusted strings.

For example, a dangerous design conceptually looks like:

`exec("program " + userInput)`

If the input contains shell metacharacters, the shell may interpret them as commands or control operators.

A safer pattern is to pass executable arguments separately, such as:

`execFile(executable, [argument])`

or:

`spawn(executable, [argument])`

The executable and each argument should be treated as separate values.

Shell execution is sometimes genuinely required, but it should be an explicit architectural decision with strict input validation.

## Signals

A signal is an asynchronous notification delivered to a process.

Common Unix and Linux signals include:

- `SIGTERM` for requesting termination
- `SIGKILL` for immediate termination that cannot be handled by the target
- `SIGINT` for an interrupt request
- `SIGHUP` traditionally associated with terminal hangups and commonly used by applications for reload behavior
- `SIGUSR1` and `SIGUSR2` for application-defined purposes

Signal semantics vary by signal and operating system.

## SIGTERM versus SIGKILL

`SIGTERM` is normally a graceful termination request.

A process can handle `SIGTERM`, perform cleanup, close resources, flush state, and exit.

`SIGKILL` cannot be caught or handled by the target process.

The normal operational sequence is therefore:

1. Request graceful termination.
2. Give the process a reasonable amount of time.
3. Verify whether it exited.
4. Escalate if necessary.

The Python timeout example follows this principle by attempting graceful termination before forcing termination.

The C++ signal-driven example records a termination request and allows normal application code to perform cleanup.

## Signal-handler design

Signal handlers have strict safety constraints.

A handler should not perform arbitrary application work.

Complex operations such as allocating memory, acquiring ordinary mutexes, performing blocking I/O, or invoking large parts of an application framework can create unsafe behavior depending on the operation and execution environment.

A common pattern is:

1. Receive a signal.
2. Set a simple notification state.
3. Return from the handler.
4. Let normal application code observe the state.
5. Perform cleanup in the ordinary execution context.

The C++ case study demonstrates this model.

## Graceful shutdown

A well-designed service should have a defined shutdown procedure.

Typical cleanup includes:

- Stop accepting new requests.
- Stop taking new jobs.
- Finish or cancel current work according to policy.
- Close network connections.
- Flush important data.
- Close files.
- Release locks.
- Close database connections.
- Stop worker threads.
- Exit with an appropriate status.

A shutdown path should be idempotent where practical. Multiple shutdown requests should not cause duplicate cleanup.

The JavaScript and C++ implementations explicitly guard their shutdown paths.

## Process monitoring

Monitoring involves repeatedly observing process state and resource behavior.

Useful process metrics can include:

- PID
- Parent PID
- Process state
- CPU usage
- Memory usage
- Number of threads
- Open file descriptors
- Start time
- Runtime
- Exit status
- Restart count

The Linux implementations use `/proc` to inspect process metadata.

A production monitor should account for races because processes can terminate between individual observations.

## CPU utilization

CPU utilization is generally measured over an interval rather than by taking a single instantaneous value.

Conceptually:

`CPU utilization = CPU time consumed / observation time`

For multi-core systems, interpretation depends on whether utilization is normalized against one logical CPU or the total available CPU capacity.

A process consuming 100% of one logical CPU is different from a process consuming 100% of a 32-core machine.

Monitoring systems must define their units clearly.

## Memory metrics

Memory measurements can refer to different concepts.

Examples include:

- Virtual memory size
- Resident set size
- Heap allocation
- Shared memory
- File-backed memory
- Anonymous memory

The Linux `/proc/<pid>/status` interface exposes values such as `VmSize` and `VmRSS`.

Node.js exposes process-specific memory metrics through `process.memoryUsage()`.

A memory number without a definition is difficult to interpret correctly.

## File descriptors

Unix-like operating systems represent many resources using file descriptors.

Examples include:

- Files
- Pipes
- Sockets
- Terminals
- Device interfaces

The Linux `/proc/<pid>/fd` directory can expose symbolic links representing descriptors belonging to a process.

A process that repeatedly opens resources without closing them can eventually exhaust its descriptor limit.

The Python implementation demonstrates resource lifecycle management using a context manager.

## Inter-process communication

IPC allows processes to exchange information.

Common IPC mechanisms include:

- Pipes
- Unix domain sockets
- TCP/UDP sockets
- Shared memory
- Message queues
- Signals
- Files
- Memory-mapped files

The C++ implementation demonstrates a pipe.

The Python implementation demonstrates `multiprocessing.Queue`.

The JavaScript implementation demonstrates IPC through `child_process.fork()`.

IPC introduces serialization, synchronization, failure, and lifecycle concerns.

## Pipes

A pipe provides a byte stream between processes.

A common design is:

1. Parent creates a pipe.
2. Parent creates a child.
3. Parent and child close the unused pipe ends.
4. One side writes.
5. The other side reads.
6. Descriptors are closed when communication ends.

The C++ implementation follows this model.

Closing unused descriptors is important. Leaving descriptors open can prevent readers from observing end-of-file and can cause unexpected blocking behavior.

## Service architecture

A service usually has several layers:

- Service manager
- Service process
- Application logic
- Worker threads or child processes
- External resources
- Logs
- Configuration
- Monitoring
- Shutdown handling

The service manager is responsible for lifecycle management while the application is responsible for performing its domain-specific work.

Keeping these responsibilities separate makes systems easier to operate.

## systemd

`systemd` is a service and system-management framework used by many Linux distributions.

It commonly manages:

- Services
- Sockets
- Timers
- Mounts
- Targets
- Dependencies
- Resource controls
- Service restart policies

A systemd service is commonly represented by a unit file.

Important service concepts include:

- Unit name
- Description
- Dependencies
- Execution command
- User and group
- Environment
- Restart policy
- Working directory
- Resource limits
- Security restrictions
- Logging behavior
- Startup and shutdown behavior

The Python and JavaScript implementations query `systemctl` when systemd is available.

The C++ implementation explains the integration model because systemd configuration is normally external to the application binary.

## systemctl

`systemctl` is the primary command-line interface for interacting with systemd.

Common read-only operations include:

- `systemctl status <unit>`
- `systemctl is-active <unit>`
- `systemctl list-units --type=service`
- `systemctl list-unit-files`
- `systemctl show <unit>`

Logs can commonly be inspected through:

`journalctl -u <unit>`

Administrative operations such as starting, stopping, enabling, disabling, or modifying services may require appropriate privileges.

## Service states

A service manager can track states such as:

- Loaded
- Active
- Inactive
- Failed
- Activating
- Deactivating

A process being alive does not necessarily mean the application is healthy.

A production service may need health checks that verify:

- The process responds.
- Dependencies are available.
- Required data stores are accessible.
- The application is processing work.
- Queue latency is acceptable.

## Restart policies

A supervisor can restart a process when it terminates unexpectedly.

Restart behavior should be controlled.

Important parameters include:

- Maximum restart count
- Restart delay
- Backoff strategy
- Failure classification
- Maximum crash frequency
- Startup timeout
- Shutdown timeout

The Python implementation includes a small educational supervisor with exponential-style delay.

A production environment should normally rely on a mature service manager rather than implementing a complete service supervisor inside every application.

## Exponential backoff

Repeatedly restarting a failed process immediately can create a restart loop.

Backoff increases the delay between attempts.

A simple pattern is:

`delay = min(initial_delay * 2^attempt, maximum_delay)`

Backoff reduces CPU consumption and allows temporary dependencies or infrastructure problems to recover.

Production systems often use additional jitter to avoid synchronized restart behavior across many instances.

## Process supervision

A supervisor needs to answer several questions:

- Did the process start?
- Is it still running?
- Did it exit normally?
- Did it crash?
- Was it killed by a signal?
- Should it restart?
- How many times has it restarted?
- Has the restart rate exceeded a threshold?
- What output or logs explain the failure?

These questions become more important as the number of services grows.

## Process priority

Operating systems provide scheduling controls that can influence process priority.

On Linux, the nice value is one example.

A higher nice value generally represents lower scheduling priority.

Changing scheduling priority can affect other workloads, so it should be done deliberately.

A service should not assume that it can arbitrarily obtain higher priority. Privilege and resource-control rules may prevent such changes.

## Resource limits

Processes can be constrained using operating-system resource controls.

Examples include limits on:

- Open files
- Processes
- Memory
- CPU
- Core dumps
- Locked memory

Resource limits can prevent one faulty component from consuming unlimited system resources.

Modern Linux service management can also use cgroups and systemd resource-control features.

## Process groups and sessions

A single process is not always the complete unit of lifecycle management.

Unix-like operating systems provide process groups and sessions.

These mechanisms are useful when a parent needs to manage a group of related processes.

For example, a service might launch multiple worker processes. Terminating only the parent may not terminate all descendants unless the process hierarchy and group-management strategy are designed correctly.

## Zombies and orphaned processes

A child that terminates remains as a zombie until its parent collects the termination status.

A parent should use `wait()` or `waitpid()` when appropriate.

An orphaned process is a process whose original parent has terminated. Operating systems have mechanisms for reparenting such processes.

Modern service managers can provide stronger lifecycle control than relying exclusively on application-level parent-child relationships.

## Timeouts

Timeouts are essential in process management.

Operations that may require timeouts include:

- Process startup
- Process shutdown
- IPC
- Network operations
- Health checks
- Child-process completion
- Service dependencies

The Python and JavaScript implementations terminate long-running child processes after a bounded period.

A timeout should have an explicit failure policy rather than simply abandoning the operation.

## Error handling

Process operations can fail because of:

- Missing executables
- Permission errors
- Invalid arguments
- Resource exhaustion
- Process termination
- Broken pipes
- Timeouts
- Invalid configuration
- Missing services
- Operating-system restrictions

The three implementations deliberately handle several failure paths.

Monitoring code should distinguish between expected dynamic conditions and actual system failures.

For example, a process disappearing while a process table is being scanned can be normal.

## Security considerations

Process management is a security-sensitive area because it interacts with operating-system resources.

Important practices include:

### Least privilege

Run services with only the permissions they require.

A network service that does not need administrator privileges should not run as an unrestricted administrator.

### Safe command execution

Avoid shell interpretation for untrusted input.

Use explicit executable and argument arrays where possible.

### Input validation

Validate configuration, file paths, numeric limits, environment variables, and external input.

### Credential handling

Avoid exposing secrets in command-line arguments because process inspection mechanisms can make command lines visible to other users depending on system permissions.

Prefer appropriate secret-management mechanisms and protected configuration.

### Filesystem restrictions

Restrict access to directories and files that the service actually requires.

### Resource controls

Apply appropriate limits to reduce the impact of runaway processes, excessive memory usage, descriptor leaks, and fork storms.

### Logging

Logs should support debugging and auditing without exposing passwords, tokens, private keys, or other sensitive values.

## Python implementation

The Python script is a standalone educational process-management laboratory.

### Process identity

`demonstrate_process_identity()` shows:

- PID
- Parent PID
- Python executable
- Python version
- Current directory
- Command-line arguments
- Environment information

This establishes the difference between a Python program and its running process.

### `/proc` inspection

`read_proc_file()` and `parse_proc_status()` provide a small parser for Linux process metadata.

`ProcessSnapshot` models selected fields as structured data.

This demonstrates how a monitoring program can transform operating-system information into application-level objects.

### Subprocess management

`demonstrate_subprocess()` uses `subprocess.run()`.

`demonstrate_process_timeout()` uses `subprocess.Popen()` and demonstrates the progression from waiting to graceful termination and finally forced termination.

### Threads

`demonstrate_threads()` creates several threads that update shared state under a lock.

This illustrates shared memory and synchronization.

### Multiprocessing

`demonstrate_process_pool()` distributes CPU-oriented prime-counting tasks across separate processes.

This demonstrates why process-based concurrency can be useful for CPU-bound Python work.

### Signals

`demonstrate_signals()` installs a signal handler.

`demonstrate_graceful_child_shutdown()` starts a child process that handles `SIGTERM`, changes its application state, and exits through a normal cleanup path.

### IPC

`demonstrate_multiprocessing_ipc()` uses multiprocessing queues to exchange tasks and results between processes.

### Service model

`ManagedService` models application-level service lifecycle behavior with a worker thread.

It deliberately does not attempt to replace systemd.

### Supervisor

`ProcessSupervisor` demonstrates restart-on-failure behavior with a bounded restart policy and increasing delay.

This illustrates the basic idea behind supervision while recognizing that mature service managers are better suited to production lifecycle management.

## JavaScript implementation

The JavaScript file focuses on Node.js process behavior.

### Process object

The `process` object exposes:

- PID
- Parent PID
- Environment
- Arguments
- Working directory
- Executable path
- Runtime version

### Memory metrics

`process.memoryUsage()` exposes runtime-specific memory measurements.

This differs conceptually from Linux `/proc` metrics because Node.js reports information about its JavaScript runtime and associated process memory categories.

### `execFile`

The `runExecFile()` helper demonstrates asynchronous execution with an explicit argument list and timeout.

### `spawn`

`demonstrateSpawn()` demonstrates streaming stdout and stderr from a child process.

### Signals

`demonstrateSignals()` shows signal handling in Node.js.

`demonstrateGracefulShutdown()` demonstrates a shutdown path that performs cleanup before allowing the application to finish.

### Worker threads

`runPrimeWorker()` and `demonstrateWorkerThreads()` use Node.js worker threads for CPU-oriented JavaScript work.

### Fork IPC

`demonstrateForkIPC()` creates a separate Node.js process and communicates through its IPC channel.

This provides a direct comparison between worker threads and child processes.

### Event loop

`demonstrateEventLoop()` shows the ordering of synchronous execution, microtasks, and timer callbacks.

This matters because a CPU-intensive operation executed directly on the main thread can prevent other event-loop work from progressing.

## C++ case study

The C++ implementation models a Linux-oriented worker-service environment.

### Problem being modeled

The case study represents a service architecture where a supervising application needs to:

- Start child processes
- Communicate with workers
- Monitor processes
- Handle termination
- Perform graceful shutdown
- Run concurrent application work
- Understand service-manager integration

### Major components

`ProcessInfo` represents selected process metadata.

`Pipe` encapsulates a POSIX pipe and closes descriptors safely.

`JobService` models a long-running application worker.

`ProcessSupervisor` demonstrates `fork()`, `exec()`, and `waitpid()`.

Signal handling uses `sigaction()`.

The process monitor reads `/proc`.

### IPC algorithm

The pipe demonstration follows this sequence:

1. Create a pipe.
2. Fork a child.
3. Child closes the read end.
4. Child writes a message.
5. Child closes its write end.
6. Parent closes its write end.
7. Parent reads the message.
8. Parent waits for the child.
9. Parent interprets the exit status.

This is a complete parent-child communication path.

### Threading

`demonstrateThreads()` creates multiple C++ threads and uses an atomic counter.

The example avoids a data race on the counter by using atomic operations.

### Signal-driven shutdown

The C++ program installs handlers for `SIGTERM` and `SIGINT`.

The handlers update a shutdown state.

Normal application code detects that state and performs the actual cleanup.

This separates asynchronous notification from ordinary application logic.

### Process supervision

`ProcessSupervisor` demonstrates the fundamental supervisor pattern:

- Create a child.
- Replace the child image with an executable.
- Wait for termination.
- Inspect exit status.
- Distinguish normal termination from signal termination.

A real supervisor would add logging, timeouts, restart policy, process groups, resource limits, health checks, and more sophisticated failure classification.

## Important distinctions

### Service versus process

A process is an operating-system execution unit.

A service is an application or operational concept describing a continuously available function.

A service can consist of one process, multiple processes, threads, or a combination.

### Service versus systemd unit

A service is an application-level concept.

A systemd unit is an operating-system configuration object managed by systemd.

A service can be represented by a systemd service unit, but the application itself should not be confused with its unit definition.

### Process versus program

A program is static.

A process is executing.

### Process versus container

A container is an isolation and packaging abstraction built using operating-system mechanisms.

A container normally contains one or more processes, rather than being equivalent to a process itself.

### Process monitoring versus health checking

Process monitoring answers questions such as whether a PID exists and what resources it is consuming.

Health checking asks whether the application is actually functioning correctly.

A process can remain alive while its application logic is deadlocked or unable to serve requests.

## Edge cases

### Process exits during inspection

A monitor can discover a PID and then fail to read `/proc/<pid>/status` because the process exited.

This is expected in a dynamic process table.

### Child ignores graceful termination

A child may not terminate promptly after `SIGTERM`.

A supervisor should use a timeout and then escalate according to its termination policy.

### Executable does not exist

Process creation can fail because an executable cannot be found.

Applications should report the failure clearly and avoid assuming that every process start succeeds.

### Permission denied

Some process information or service operations may be restricted.

Monitoring code should distinguish permission errors from nonexistent processes.

### Zombie processes

A parent that fails to collect child status can accumulate zombies.

### Thread exceptions

An exception in one worker does not automatically mean the entire process has been designed to shut down safely.

Thread lifecycle and error propagation need explicit design.

### Resource leaks

Unclosed files, pipes, sockets, or other descriptors can exhaust operating-system limits.

### Restart storms

Immediate unlimited restarts can produce high CPU usage and obscure the underlying failure.

Bounded restart policies and backoff reduce this risk.

## Common mistakes

### Using `shell=True` unnecessarily

Shell execution adds interpretation and security complexity.

### Treating a PID as permanent identity

PIDs can be reused.

### Killing processes without cleanup

Immediate termination can leave application-level state incomplete.

### Assuming a process is healthy because it exists

Liveness and health are different concepts.

### Sharing mutable state between threads without synchronization

This can create race conditions and undefined or incorrect behavior.

### Creating too many processes

Process creation consumes operating-system resources and can reduce performance when task sizes are small.

### Ignoring child exit status

A supervisor that does not inspect child status loses important failure information.

### Forgetting timeouts

A blocked child can make the supervising application block indefinitely.

### Closing the wrong IPC descriptors

Incorrect descriptor lifecycle can cause deadlocks or unexpected EOF behavior.

### Running services with excessive privileges

A compromise of an unnecessarily privileged service can have a larger impact.

## Performance considerations

Process creation is normally more expensive than a simple function call and often more expensive than creating a thread.

IPC can also introduce serialization, copying, synchronization, and context-switching costs.

For CPU-bound workloads, parallelism can provide substantial benefits when the work is sufficiently large to justify coordination overhead.

For I/O-bound workloads, asynchronous I/O or a modest number of worker threads may be more appropriate.

Monitoring itself consumes resources. A monitor that scans thousands of processes and reads many files too frequently can create unnecessary filesystem and kernel overhead.

The appropriate monitoring interval depends on the operational requirement.

## Scheduling considerations

Operating-system scheduling determines when runnable threads and processes receive CPU time.

Important concepts include:

- Scheduling priority
- Nice values
- CPU affinity
- Real-time scheduling
- Preemption
- Context switching
- CPU contention

Real-time scheduling requires careful engineering because inappropriate priority configuration can affect system responsiveness.

## Production service considerations

A production service normally needs more than a main loop.

Important operational features include:

- Deterministic startup
- Configuration validation
- Graceful shutdown
- Structured logging
- Health checks
- Metrics
- Timeouts
- Restart policy
- Backoff
- Resource limits
- Dependency handling
- Security isolation
- Correct exit codes
- Signal handling
- Log rotation or centralized logging
- Observability
- Failure classification

A service manager such as systemd can provide many lifecycle capabilities outside the application itself.

## Design principles demonstrated

The implementations apply several general engineering principles.

### Separate lifecycle management from business logic

The service lifecycle determines whether work should run.

The worker logic performs the actual task.

Keeping those responsibilities distinct makes both easier to test.

### Prefer explicit interfaces

Passing an executable and argument array is clearer and safer than constructing a shell string.

### Bound operations

Timeouts prevent indefinite waiting.

Restart limits prevent infinite failure loops.

### Handle dynamic system state

Processes can appear and disappear at any moment.

Monitoring code must therefore tolerate races.

### Make cleanup explicit

Resources should have clear ownership and lifecycle rules.

### Use the appropriate concurrency boundary

Threads are useful when shared-memory concurrency is desirable.

Processes are useful when stronger isolation or separate runtime execution is required.

Asynchronous I/O is useful when the primary challenge is waiting rather than computation.

## Practical applications

Process and service management is relevant to:

- Web servers
- API platforms
- Background job systems
- Database services
- Data-processing pipelines
- Monitoring agents
- Build systems
- CI/CD workers
- Message consumers
- Machine-learning inference services
- Security monitoring agents
- Network services
- Scheduled workloads
- Distributed systems
- Containerized applications
- Cloud infrastructure

The same underlying ideas appear at different scales. A local worker process and a large production service fleet both require lifecycle control, failure handling, observability, and resource management.

## Implementation correspondence

| Concept | Python | JavaScript | C++ |
|---|---|---|---|
| Process identity | `os.getpid()` | `process.pid` | `getpid()` |
| Parent PID | `os.getppid()` | `process.ppid` | `getppid()` |
| Child process | `subprocess` | `child_process` | `fork`/`exec` |
| Process timeout | `Popen` + timeout | `spawn` + timer | POSIX lifecycle primitives |
| Threads | `threading` | `worker_threads` | `std::thread` |
| Process parallelism | `multiprocessing` | child processes | POSIX processes |
| IPC | `multiprocessing.Queue` | fork IPC | pipe |
| Signals | `signal` | `process.on` | `sigaction` |
| Linux monitoring | `/proc` | `/proc` | `/proc` |
| Service concept | `ManagedService` | `ServiceController` | `JobService` |
| Supervision | `ProcessSupervisor` | child lifecycle APIs | `ProcessSupervisor` |
| Tests | assertions | custom assertions | custom `require` |
| Security | explicit subprocess arguments | `execFile` | explicit POSIX APIs |

## Limitations

The Python and JavaScript programs are intentionally educational and use only standard runtime facilities.

The C++ case study is deliberately Linux/POSIX-oriented because concepts such as `fork()`, `exec()`, `waitpid()`, POSIX signals, pipes, and `/proc` are central to the case study.

Windows uses different process and service APIs, although the general concepts of process identity, threads, supervision, resource management, services, and IPC still apply.

The simplified supervisors do not implement all features of a production service manager.

The process metrics shown by `/proc` are selected examples rather than a complete monitoring system.

## Best practices

- Use explicit process ownership.
- Collect child exit status.
- Set reasonable timeouts.
- Prefer graceful termination before forced termination.
- Avoid shell execution with untrusted input.
- Validate configuration.
- Use least privilege.
- Close descriptors and other resources deterministically.
- Synchronize shared mutable state.
- Use process isolation when fault containment is important.
- Use threads when shared-memory concurrency is appropriate.
- Use worker processes for workloads that benefit from process-level isolation or parallel CPU execution.
- Use mature service managers for production lifecycle management.
- Monitor both process-level metrics and application-level health.
- Bound restart attempts and use backoff.
- Record useful exit codes and failure information.
- Keep signal handlers minimal.
- Design shutdown behavior before implementing the main service loop.
