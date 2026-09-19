# Shell scripting with Bash

## Introduction

Shell scripting is the practice of writing executable command sequences for a shell interpreter. Bash, short for Bourne Again Shell, is one of the most widely used shells in Unix and Linux environments.

Bash scripts are particularly useful for operating-system automation, deployment workflows, filesystem operations, process orchestration, scheduled jobs, system administration, build automation, testing workflows, configuration tasks, and combining existing command-line utilities.

A shell script occupies a different architectural position from a conventional application. It commonly coordinates other programs rather than implementing every algorithm itself. This distinction is important because Bash is exceptionally effective at process orchestration and command composition, while complex computation, large-scale data processing, and sophisticated application state are often better handled by languages such as Python, JavaScript, C++, Java, or Go.

This repository contains three complementary implementations:

- A Python study companion that explains Bash concepts progressively and models important shell behaviors.
- A JavaScript implementation that demonstrates process execution, environment inheritance, filesystem automation, asynchronous operations, retries, concurrency control, and deployment orchestration.
- A C++ deployment case study that models an industry-style automation system using typed configuration, validation, filesystem management, logging, health checks, rollback, retries, and bounded concurrency.

The implementations are deliberately self-contained and avoid unnecessary third-party dependencies.

## Fundamental concepts

### Shell

A shell is a command interpreter. It accepts commands, parses them, performs shell-specific expansion, launches programs, connects input and output, and reports command status.

Bash is both an interactive shell and a scripting language.

A user can interact with Bash through a terminal:

`$ pwd`

A script can contain the same kinds of commands:

`printf '%s\n' "hello"`

The shell is responsible for interpreting the command syntax. The external program is responsible for performing the requested operation when the command refers to an external executable.

This distinction explains why shell scripting is particularly effective for automation. Bash can coordinate programs that already exist on the operating system.

### Terminal

A terminal provides an interface through which a user can interact with a shell. The terminal itself is not the shell.

A simplified relationship is:

`terminal -> shell -> command/program -> operating system`

Modern systems may provide terminal emulators, remote terminals, virtual consoles, or other interfaces, but the conceptual separation remains useful.

### Bash

Bash provides:

- variables
- functions
- conditions
- loops
- arrays
- arithmetic expansion
- parameter expansion
- command substitution
- pipelines
- redirection
- pattern matching
- traps
- positional parameters
- shell options
- process control

Bash also inherits many conventions from Unix shells.

### Shell script

A shell script is normally a text file containing shell commands and control structures.

A Bash script commonly begins with a shebang such as:

`#!/usr/bin/env bash`

The shebang identifies the interpreter that should execute the file when the operating system launches the script directly.

A script can commonly be executed as:

`./script.sh`

when it has appropriate execute permissions.

## Variables

Bash variables are assigned without spaces surrounding the assignment operator.

Example:

`name="Atul"`

This is different from many programming-language assignment statements because the shell parser treats whitespace as meaningful.

Variable expansion uses the dollar sign:

`echo "$name"`

The Python implementation demonstrates the conceptual relationship between Bash string variables and Python variables.

Bash does not use the same static type system as C++. A shell variable generally represents textual data, although Bash supports arithmetic evaluation for integer calculations.

For example:

`count=10`

and:

`total=$((count * 3 + 2))`

The arithmetic expression is evaluated by Bash.

## Environment variables

An ordinary shell variable belongs to the current shell process.

An exported variable becomes part of the environment inherited by child processes.

Example:

`APP_ENV="production"`

followed by:

`export APP_ENV`

A child process can then read `APP_ENV`.

Common environment variables include:

- `HOME`
- `PATH`
- `PWD`
- `USER`
- `SHELL`

The JavaScript implementation demonstrates the same process-environment concept through `process.env`.

Environment variables are widely used for deployment configuration because they allow the same program or script to operate under different environments without changing its source code.

Environment variables should not automatically be treated as secure storage. Secrets placed in environment variables can still become visible through process inspection, diagnostics, crash reports, or configuration mistakes depending on the operating environment.

## Quoting

Quoting is one of the most important Bash topics.

### Single quotes

Single quotes preserve the literal meaning of most characters:

`'hello $name'`

The `$name` expression is not expanded inside ordinary single quotes.

### Double quotes

Double quotes allow parameter expansion:

`"hello $name"`

but protect the resulting value from normal word splitting and pathname expansion.

This is why the following pattern is generally preferred:

`rm -- "$filename"`

rather than:

`rm $filename`

If `filename` contains spaces, an unquoted expansion can become multiple arguments.

### Backslash

A backslash can escape individual characters.

Quoting and escaping are not merely stylistic concerns. They directly affect how the shell parses commands and therefore affect both correctness and security.

## Word splitting

Bash can perform word splitting on unquoted expansions.

Suppose:

`filename="quarterly report.txt"`

An unquoted expansion may produce two words conceptually:

`quarterly`

and:

`report.txt`

A quoted expansion preserves the value as one argument:

`"$filename"`

This is one of the most common sources of shell-script bugs.

## Pathname expansion

Shell globbing is different from regular-expression matching.

Common shell patterns include:

`*.log`

and:

`backup-?.tar.gz`

The shell can expand these patterns to matching pathnames before the external command receives its arguments.

This means a command such as:

`rm *.log`

may result in several filenames being passed to `rm`.

Globbing should therefore be understood as a shell parsing and expansion operation rather than as a feature of `rm`.

## Regular expressions

Regular expressions are a separate pattern system.

Bash supports regular-expression matching through `[[ ... =~ ... ]]`.

For example, a conceptual regular expression for a filename ending in `.log` is:

`^.*\.log$`

A glob such as:

`*.log`

and a regular expression such as:

`^.*\.log$`

may appear similar but follow different syntax and semantics.

The Python and JavaScript implementations demonstrate this distinction.

## Command substitution

Command substitution captures command output.

The modern form is:

`result="$(command)"`

The older backtick syntax is also recognized by Bash, but the `$()` form is generally easier to read and nest.

Command substitution is commonly used when the output of one operation becomes an input to another operation.

For example:

`current_user="$(whoami)"`

The Python implementation demonstrates the same general concept with subprocess execution and captured output.

## Arithmetic expansion

Bash provides arithmetic expansion:

`$((expression))`

For example:

`total=$((price * quantity))`

This is useful for integer arithmetic.

For calculations requiring floating-point mathematics, sophisticated numerical processing, or complex mathematical algorithms, another language or specialized command may be more appropriate.

## Exit status

Unix processes communicate an exit status to their parent process.

By convention:

- `0` indicates success.
- A nonzero value indicates failure or another condition.

Bash exposes the previous command's status through:

`$?`

Conditional execution can use a command directly:

`if command; then`

The important principle is that command success should normally be determined from the exit status rather than by parsing human-readable output.

The JavaScript and C++ implementations model explicit success and failure states to show the same architectural principle.

## Conditions

Bash provides `if`, `elif`, and `else`.

A Bash-specific conditional commonly uses:

`[[ condition ]]`

Typical tests include:

`-f file`

for a regular file,

`-d directory`

for a directory,

`-r file`

for readability,

`-w file`

for writability,

and:

`-x file`

for executability.

String tests include:

`-z "$value"`

for an empty string and:

`-n "$value"`

for a non-empty string.

Numeric comparisons use operators such as:

`-eq`

`-ne`

`-lt`

`-le`

`-gt`

`-ge`

String comparisons and numeric comparisons should not be confused.

## Case statements

A `case` statement is useful when a value has multiple expected alternatives.

A deployment script may use an environment value such as:

`development`

`testing`

or:

`production`

and select different behavior for each.

The general Bash structure is:

`case "$environment" in`

followed by patterns and their associated commands, terminated with `esac`.

The C++ and JavaScript implementations model the same configuration-selection concept through typed values and validation.

## Loops

Bash provides several looping mechanisms.

### For loop

A list-oriented loop can process a collection of values.

Example:

`for file in *.log; do`

followed by the processing commands and:

`done`

Bash also supports arithmetic loops:

`for ((i=1; i<=5; i++)); do`

### While loop

A `while` loop continues while its condition succeeds.

Example:

`while [[ "$attempt" -le 3 ]]; do`

### Until loop

An `until` loop continues until its condition succeeds.

This can be useful for retry and readiness logic.

### Break and continue

`break` exits a loop.

`continue` skips the remaining body of the current iteration and proceeds to the next iteration.

Loop control should remain clear because shell syntax can become difficult to reason about when many nested conditions and pipelines are combined.

## Functions

Functions allow reusable shell operations to be grouped together.

A Bash function can be defined as:

`function_name() {`

followed by its commands and a closing brace.

Function parameters are accessed through positional parameters.

For example:

`$1`

represents the first function argument.

`$2`

represents the second.

`$#`

represents the number of positional parameters.

`"$@"`

represents all arguments as separate words.

This last form is particularly important when forwarding arguments because it preserves argument boundaries.

A Bash function's `return` mechanism communicates an exit status. It should not be confused with returning arbitrary data as in many conventional programming languages.

Text can be emitted and captured using command substitution:

`result="$(function_name)"`

The Python and JavaScript implementations use ordinary function return values to illustrate the conceptual difference.

## Positional parameters

Scripts commonly receive values through command-line arguments.

The most important Bash parameters are:

- `$0` for the script name
- `$1` for the first argument
- `$2` for the second argument
- `$#` for the number of arguments
- `"$@"` for all arguments individually
- `"$*"` for all arguments combined according to shell rules

A deployment script might conceptually accept:

`./deploy.sh production 2026.09.19`

The script should validate both values before using them.

## Arrays

Bash supports indexed arrays.

An example is:

`servers=("web01" "web02" "web03")`

An element can be accessed with:

`${servers[0]}`

The number of elements can be obtained through:

`${#servers[@]}`

Bash also supports associative arrays using:

`declare -A`

The JavaScript implementation uses arrays and objects to represent similar structures.

The C++ implementation uses vectors, sets, and maps where their stronger type and algorithmic properties are useful.

## Reading files

A robust Bash pattern for reading text files line by line is:

`while IFS= read -r line; do`

followed by processing and:

`done < "$file"`

The use of `IFS=` helps preserve leading and trailing whitespace, while `read -r` prevents backslashes from being interpreted as escape characters.

For structured formats such as JSON, XML, or complex CSV data, ad-hoc shell parsing can become unreliable. A specialized parser or application language is often more appropriate.

## Redirection

Shell redirection connects commands to files or other streams.

Common forms include:

`command > file`

which redirects standard output and replaces the file,

`command >> file`

which appends standard output,

`command < file`

which supplies file content as standard input,

and:

`command 2> file`

which redirects standard error.

A common combined form is:

`command > file 2>&1`

which sends both standard output and standard error to the same destination.

Understanding file descriptors is important for production shell automation.

The conventional descriptors are:

- `0` standard input
- `1` standard output
- `2` standard error

## Pipelines

A pipeline connects the output of one process to the input of another.

Example:

`ps aux | grep python`

Conceptually:

`process A stdout -> process B stdin`

Pipelines allow mature command-line utilities to be composed into larger workflows.

They are one of Bash's strongest features.

The pipeline operator does not automatically mean that every failure in the pipeline is visible through the final status. Bash's `pipefail` option changes pipeline status behavior so that a failure from an earlier component can be reflected.

A common reliability baseline is:

`set -o pipefail`

## Strict mode

A frequently used Bash reliability baseline is:

`set -Eeuo pipefail`

The options have different meanings:

- `-e` enables `errexit` behavior.
- `-E` preserves `ERR` trap behavior in additional execution contexts.
- `-u` treats unset variables as errors.
- `pipefail` makes pipeline status account for failures in pipeline components.

Strict mode is useful but should not be treated as a magic guarantee of correctness.

The behavior of `errexit` has contextual rules. Commands used intentionally as conditions can return nonzero statuses without necessarily indicating that the script should terminate.

For example:

`if grep -q "pattern" "$file"; then`

uses the exit status as a condition.

Understanding Bash's execution rules is more important than blindly adding options without understanding their effects.

## Traps and cleanup

Bash provides `trap` for responding to signals and shell events.

A common cleanup pattern is:

`cleanup() {`

followed by temporary-resource cleanup and:

`trap cleanup EXIT`

This allows a script to release temporary resources when it exits.

Relevant signals and events include:

- `EXIT`
- `INT`
- `TERM`
- `HUP`
- `ERR`

Temporary resources should be created safely and cleanup logic should be designed so that unexpected termination does not leave sensitive or misleading state behind.

The Python implementation uses `try` and `finally`, while JavaScript uses `finally` blocks. C++ uses resource-management techniques and explicit cleanup.

## Configuration-driven automation

Hard-coded environment-specific values make automation difficult to reuse.

Configuration may come from:

- command-line arguments
- environment variables
- configuration files
- deployment metadata
- service discovery
- secure secret-management systems

The configuration model used by all three implementations includes:

- application name
- version
- environment
- retention policy

The implementations validate these values before deployment.

A production system should define configuration precedence explicitly. It should also distinguish ordinary configuration from sensitive credentials.

## Input validation

External input should be treated as untrusted until validated.

Typical validation includes:

- required argument count
- allowed environment values
- numeric ranges
- valid filenames
- valid application identifiers
- expected file types
- acceptable configuration values

For example, an application name can be restricted to:

`[A-Za-z0-9._-]+`

when those are the only characters required.

The exact validation rule should reflect the actual application's domain rather than blindly applying a generic pattern.

## Command injection

Command injection is one of the most important security risks in shell scripting.

A dangerous conceptual pattern is constructing a shell command by concatenating untrusted input:

`command="program $user_input"`

and then evaluating that string through a shell.

The problem is that the shell may interpret metacharacters in the input as syntax rather than data.

Important defensive practices include:

- quote expansions
- validate allowed input
- avoid `eval`
- avoid unnecessary shell interpretation
- use arrays for command arguments
- use `--` where supported
- avoid constructing command strings unnecessarily

A safer Bash design is to represent a command as an array:

`command=(grep -- "$pattern" "$file")`

and execute it with:

`"${command[@]}"`

This preserves argument boundaries.

The JavaScript implementation demonstrates the same principle using `spawn` and `execFile` rather than blindly constructing shell command strings.

## `eval`

`eval` causes its arguments to be interpreted as shell code.

Because it converts data into executable shell syntax, it should be avoided when processing untrusted values.

Many designs that appear to require `eval` can instead use:

- arrays
- functions
- case statements
- associative arrays
- explicit dispatch tables
- controlled variable expansion

Removing `eval` often makes both security and reasoning easier.

## Filename safety

Filenames can contain spaces, tabs, wildcard characters, and other characters that affect shell parsing.

A common robust pattern is:

`rm -- "$filename"`

The `--` tells many Unix utilities that subsequent values should be treated as operands rather than command options.

The exact support for `--` depends on the utility, so command documentation and implementation behavior still matter.

## Filesystem automation

Shell scripts frequently automate:

- directory creation
- file copying
- file movement
- archive operations
- log rotation
- cleanup
- permissions
- backups
- release directories

A command such as:

`mkdir -p "$directory"`

is valuable because it is naturally idempotent.

The Python, JavaScript, and C++ implementations create temporary workspaces and demonstrate controlled filesystem operations.

## Idempotence

An operation is idempotent when repeating it produces the same desired state after the first successful execution.

For example:

`mkdir -p "$directory"`

can safely be repeated when the directory already exists.

Idempotence is highly valuable in automation because scripts can be retried without necessarily creating duplicate or conflicting state.

Deployment automation should ideally move the environment toward a declared state rather than merely performing a sequence of mutations that assumes a pristine system.

## Checksums and integrity

Commands such as:

`sha256sum artifact.tar.gz`

can calculate a cryptographic digest.

A digest can detect accidental modification.

A digest by itself does not necessarily establish authenticity. If an attacker can replace both the artifact and the digest, the verification can still succeed.

Authenticity normally requires a trusted source, digital signature, certificate, protected metadata, or another trust mechanism.

The Python and JavaScript implementations use SHA-256 through their standard libraries.

The C++ case study explicitly identifies its simple digest as a demonstration rather than a production cryptographic implementation. Production C++ artifact verification should use a vetted cryptographic implementation rather than `std::hash`.

## Unix permissions

Unix permissions commonly distinguish:

- owner
- group
- others

Common permission modes include:

`600`

for owner read/write,

`644`

for owner read/write and others read,

and:

`755`

for owner read/write/execute and others read/execute.

Sensitive configuration should not automatically be world-readable.

The principle of least privilege means a script or service should have only the permissions required for its work.

This is especially important for deployment automation because deployment accounts can otherwise become high-impact security targets.

## Logging

Production automation should produce useful logs.

A typical Bash logging function may include:

- timestamp
- severity
- message
- relevant operation identifier

Useful levels include:

- INFO
- WARNING
- ERROR

Logs should describe important state transitions without exposing credentials, tokens, private keys, or other secrets.

Structured logging becomes increasingly valuable when automation is consumed by monitoring and observability systems.

The three implementations all demonstrate explicit logging.

## Retry logic

Transient failures are common in automation.

Examples include:

- temporary network failures
- service startup delays
- temporary file locks
- DNS instability
- temporary dependency unavailability

A robust retry policy should define:

- maximum attempts
- delay
- failure conditions
- logging
- optional exponential backoff

Exponential backoff increases the delay between repeated attempts.

A conceptual sequence might be:

`100 ms -> 200 ms -> 400 ms -> 800 ms`

Retries should have a finite limit. Infinite retries can turn a permanent failure into an indefinitely running process.

## Background jobs

Bash can execute commands asynchronously:

`task_a &`

The process identifier of a background command can be obtained using:

`$!`

The `wait` command synchronizes with child processes.

For example:

`task_a &`

`pid_a=$!`

`wait "$pid_a"`

The main concern is that uncontrolled background execution can overwhelm the machine or the service being accessed.

## Bounded concurrency

Parallel work can improve throughput when tasks are independent.

It can also introduce:

- race conditions
- resource contention
- excessive memory consumption
- too many open files
- excessive network connections
- interleaved logs
- nondeterministic failures

A production automation system should normally impose a concurrency limit.

The JavaScript implementation provides `mapWithConcurrency`, while the C++ case study implements a simple batch-based task executor.

The batch executor is intentionally straightforward. A production system may use a persistent worker pool to avoid repeated thread creation.

## Process orchestration

Shell scripting is strongest when a system needs to coordinate existing programs.

A deployment script might invoke:

- package managers
- version-control tools
- archive utilities
- service managers
- network clients
- database utilities
- monitoring commands

The script becomes an orchestration layer.

This architecture is different from implementing the underlying services themselves.

## Python implementation

The Python script is structured as a progressive study companion.

It begins with shell terminology and continues through:

- variables
- environment variables
- quoting
- command substitution
- exit statuses
- conditions
- case-style branching
- loops
- functions
- arguments
- arrays
- file processing
- redirection
- pipelines
- globbing
- regular expressions
- filesystem automation
- strict mode
- traps
- logging
- validation
- command safety
- configuration
- idempotence
- integrity
- permissions
- concurrency
- retries
- performance
- testing
- deployment architecture

The Python program intentionally avoids arbitrary shell execution. It models the semantics safely and uses controlled subprocess demonstrations where process execution is itself the educational subject.

### Python configuration model

`ApplicationConfig` represents deployment configuration.

Its validation method checks:

- environment membership
- application name
- retention period

This illustrates a useful design principle for shell scripts: validate configuration before performing side effects.

### Python deployment model

`DeploymentState` represents deployment state.

`DeploymentAutomation` then separates operations into:

- validation
- preparation
- artifact verification
- deployment
- health checks
- rollback

This is preferable to placing every operation inside one large function because each stage has a distinct responsibility.

## JavaScript implementation

The JavaScript implementation complements the Python script by focusing on Node.js capabilities that are particularly useful for understanding shell orchestration from an application-runtime perspective.

It demonstrates:

- operating-system information
- environment inheritance
- process arguments
- safe child-process execution
- asynchronous process execution
- filesystem operations
- exit-status handling
- pipeline concepts
- functions
- arrays and objects
- regular expressions
- retry logic
- exponential backoff
- bounded concurrency
- temporary resources
- cleanup
- idempotence
- configuration validation
- deployment orchestration
- security considerations
- performance considerations

### Node.js process execution

Node.js provides several process APIs.

`spawn` is appropriate when an application needs streaming control over a child process.

`execFile` can execute an executable with explicit arguments without requiring a constructed shell command.

This distinction is important when input is potentially influenced by users or external systems.

The JavaScript implementation demonstrates argument-vector execution instead of relying on concatenated shell command strings.

### Asynchronous operations

Node.js uses asynchronous APIs extensively.

Promises allow multiple operations to be coordinated without blocking the JavaScript event loop.

This provides a useful comparison with Bash background jobs.

Bash:

`task &`

Node.js:

`spawn(...)`

Both can represent asynchronous process execution, but the programming models are different.

### Filesystem automation

Node.js provides filesystem APIs through:

`fs`

and:

`fs/promises`

The implementation uses asynchronous filesystem operations to create directories, write files, read files, copy files, and remove temporary workspaces.

This demonstrates how application code can perform tasks that might otherwise be orchestrated through Bash commands.

## C++ case study

The C++ program models an industry-style deployment automation system.

The scenario is a deployment of:

`inventory-api`

to:

`production`

with a version such as:

`2026.09.19`

The workflow is:

`validate -> prepare -> verify -> deploy -> health check`

If deployment or validation fails, the system records the failure and can roll back to the previous version.

### Deployment configuration

`DeploymentConfig` stores:

- application
- version
- environment
- release root
- retention policy

Its `validate()` method rejects invalid values.

This represents a typed equivalent of the validation normally implemented through Bash conditionals.

### Logging

`Logger` centralizes logging.

The implementation provides:

- INFO
- WARNING
- ERROR

A mutex protects concurrent writes so multiple asynchronous tasks do not modify output in an uncontrolled way.

This is an example of a design consideration that becomes more explicit in a multithreaded language.

### Argument parser

`ArgumentParser` demonstrates structured command-line argument handling.

It accepts arguments in the form:

`--name=value`

and rejects malformed options.

The class is included to demonstrate the architectural relationship between Bash positional parameters and structured command-line processing in a compiled language.

### File manager

`FileManager` encapsulates filesystem operations.

It supports:

- directory creation
- file writing
- file reading
- existence checks

`std::filesystem::create_directories()` is naturally suited to idempotent directory creation.

### Artifact verification

`ArtifactVerifier` demonstrates the concept of calculating and checking an artifact digest.

The implementation deliberately uses `std::hash` only as an educational placeholder for the concept of digest comparison. `std::hash` should not be treated as a cryptographic hash or production artifact-authentication mechanism.

A production deployment system should use a vetted cryptographic implementation and, where authenticity matters, a trusted signature or equivalent verification mechanism.

### Health checks

`HealthChecker` performs deterministic local checks for the case study.

The checks include:

- configuration
- release directory
- application version

A real deployment system could expand this model to include:

- process health
- TCP connectivity
- HTTP endpoints
- database connectivity
- queue connectivity
- dependency readiness
- application-specific business checks

### Rollback

Rollback is a critical property of deployment automation.

The case study records the previous version and restores that state when a deployment becomes unhealthy.

The basic state transition is:

`previous version -> new version -> health check`

If the health check fails:

`new version -> previous version`

Rollback itself must also be observable and should have clearly defined failure behavior in a production system.

## Shell functions versus application classes

Bash functions and C++ classes solve related organizational problems but provide different levels of structure.

A Bash function groups shell operations:

`deploy() { ... }`

A C++ class can group:

- state
- validation
- behavior
- invariants
- dependencies

The C++ deployment implementation uses separate classes for:

- configuration
- logging
- argument parsing
- filesystem operations
- artifact verification
- health checks
- deployment orchestration
- retry behavior
- concurrency

This separation makes the case study substantially more explicit than a single shell script.

## Shell arguments versus typed parameters

Bash receives textual command-line values.

For example:

`$1`

contains the first positional argument.

The script must interpret the text as the required type.

C++ can represent the resulting state with types such as:

`std::string`

and:

`int`

and validate them through explicit functions.

JavaScript lies between these approaches because it is dynamically typed while still providing structured arrays, objects, classes, and runtime validation.

## Shell arrays versus application collections

Bash indexed arrays are useful for small collections of arguments or values.

For example:

`servers=("web01" "web02" "web03")`

For more complex processing, C++ provides:

`std::vector`

for ordered collections,

`std::set`

for ordered unique values,

and:

`std::map`

for key-value associations.

JavaScript arrays and objects provide similarly convenient data structures at the application level.

## Edge cases

Reliable shell automation must account for unusual input and system state.

Important edge cases include:

### Empty variables

With `set -u`, an unset variable can cause an error.

Scripts should deliberately initialize optional values or use safe parameter-expansion techniques when appropriate.

### Spaces in filenames

A filename such as:

`quarterly report.txt`

requires careful quoting.

### Wildcard characters

A filename containing `*` or `?` can interact with pathname expansion when an expansion is not quoted.

### Missing files

A script should distinguish between an expected missing file and an unexpected filesystem failure.

### Permission failures

A directory can exist but still be inaccessible.

Existence alone does not prove that an operation will succeed.

### Empty glob results

Shell behavior for unmatched wildcards depends on shell options.

The `nullglob` option can cause unmatched globs to expand to nothing instead of remaining literal.

### Pipeline failures

Without appropriate handling, an earlier command in a pipeline can fail while a later command succeeds.

`pipefail` changes this behavior.

### Signals

A process may receive termination or interruption signals.

Cleanup should be designed accordingly.

### Partial deployment

A deployment may fail after changing part of the system.

This is why deployment automation should define rollback or recovery semantics.

### Repeated execution

A script should behave predictably when run more than once.

Idempotent operations reduce the risk of duplicate or conflicting state.

## Exceptions and error handling

Bash does not use exceptions in the same sense as C++ or Python.

Failure is primarily communicated through exit statuses and control structures.

A script can explicitly test a command:

`if ! command; then`

and implement an error path.

C++ uses exceptions in the case study to transfer failure information from lower-level components to the deployment controller.

JavaScript uses rejected promises and exceptions for asynchronous failure handling.

These are different language mechanisms representing the same broader architectural requirement: failures must be observable and handled intentionally.

## Common mistakes

### Unquoted expansions

Fragile:

`rm $file`

Preferred when one argument is intended:

`rm -- "$file"`

### Parsing `ls`

Fragile:

`for file in $(ls)`

This breaks for unusual filenames and performs unnecessary parsing.

A safer shell design should use shell pathname expansion directly when appropriate or use `find` with a carefully designed processing strategy.

### Using `eval`

Fragile:

`eval "$input"`

This can convert untrusted data into shell syntax.

### Ignoring exit status

A script that never checks important command statuses can continue after a failed operation and create misleading system state.

### Excessive command substitution

Starting external commands repeatedly can become expensive.

### Parsing complex structured data with shell text manipulation

JSON, XML, and complicated CSV structures should generally be handled by suitable parsers.

### Unbounded background jobs

Starting hundreds or thousands of background processes without resource control can destabilize the host.

### Infinite retries

Retries should have finite limits and clear failure semantics.

### Logging secrets

Passwords, access tokens, private keys, and similar credentials should not be written to ordinary logs.

## Advanced Bash features

### Subshells

Parentheses create a subshell context:

`(cd /tmp; echo "$PWD")`

Changes made inside the subshell normally do not modify the parent shell's working directory.

### Command grouping

Braces can group commands in the current shell:

`{ command1; command2; }`

The distinction between braces and parentheses matters because they have different execution contexts.

### Process substitution

Bash supports process substitution such as:

`diff <(sort file1) <(sort file2)`

This can expose command output through a file-like interface.

It is powerful but Bash-specific and therefore reduces portability to simpler POSIX shells.

### Here documents

A here document supplies multiline input:

`command <<EOF`

followed by content and:

`EOF`

This is useful for configuration generation and multiline input.

### Here strings

A here string provides a string as standard input:

`command <<< "$text"`

This is concise for Bash-specific scripts.

## POSIX shell versus Bash

Not every shell supports every Bash feature.

Bash provides features such as:

- `[[ ... ]]`
- arrays
- associative arrays
- arithmetic loops
- process substitution
- `<<<`
- Bash-specific shell options

A script that uses these features should explicitly identify Bash as its interpreter.

If maximum portability across Unix-like systems is more important, a POSIX shell such as `sh` may be preferable, but that requires restricting the syntax and features used.

The interpreter choice should be deliberate rather than accidental.

## Performance considerations

Shell scripts are often efficient enough for orchestration because they delegate work to optimized system utilities.

The main performance costs can appear when a script launches large numbers of external processes.

For example, processing one million records by starting a new command for each record can produce significant process-creation overhead.

A more appropriate design may be:

- one optimized command
- a pipeline
- an in-process Python program
- a compiled C++ program
- a specialized data-processing system

The right boundary depends on workload characteristics.

The C++ case study explicitly discusses algorithmic and operational complexity.

## Complexity

Shell scripts often operate at the orchestration level, so their performance can be dominated by:

- process startup
- filesystem latency
- network latency
- external program behavior
- command pipelines

When implementing algorithms inside Bash, conventional complexity concerns still apply, but the language becomes increasingly awkward for large computational workloads.

For example, searching an indexed array repeatedly, repeatedly invoking external commands, or constructing large strings can become inefficient.

C++ offers explicit data structures with well-understood complexity characteristics.

The C++ case study uses:

- `std::map` for key-value configuration
- `std::set` for allowed environments
- `std::vector` for ordered health-check results
- `std::filesystem` for filesystem operations
- asynchronous tasks for bounded parallel work

## Security considerations

Shell scripts frequently operate with significant system privileges, making security particularly important.

### Least privilege

Run automation with only the permissions it requires.

Avoid executing an entire deployment process as a highly privileged user when individual operations can use narrower permissions.

### Input validation

Validate command-line values and environment variables before using them.

### Quoting

Quote expansions unless splitting is intentionally required.

### Command construction

Prefer arrays and direct argument passing.

### `eval`

Avoid it with untrusted data.

### Temporary resources

Use secure temporary directories and filenames.

### Secrets

Do not commit credentials into source code.

Do not print credentials into logs.

### Artifact authenticity

Integrity hashes alone do not necessarily prove who produced an artifact.

Use a trusted verification mechanism for production release systems.

### Dependency execution

A shell script should not assume that a command on `PATH` is always the expected executable in high-security contexts. Where appropriate, validate dependencies and control execution environments.

## Production shell-script structure

A maintainable Bash script can be organized around:

`#!/usr/bin/env bash`

`set -Eeuo pipefail`

then functions such as:

- `usage`
- `log`
- `cleanup`
- `validate_environment`
- `verify_dependencies`
- `prepare`
- `deploy`
- `health_check`
- `rollback`
- `main`

Finally:

`trap cleanup EXIT`

and:

`main "$@"`

The exact structure depends on the script's complexity.

The important architectural principle is separation of responsibilities.

Argument parsing should not be mixed indiscriminately with deployment mutation.

Validation should happen before irreversible operations.

Cleanup should be centralized.

Important state transitions should be logged.

## Deployment workflow modeled by the C++ program

The C++ case study represents the following deployment workflow.

### Configuration

The system receives:

- application name
- release version
- target environment
- release directory
- retention period

### Validation

The configuration is checked before any deployment mutation.

Invalid environments are rejected.

Empty values are rejected.

Unsupported application and version characters are rejected.

Invalid retention periods are rejected.

### Preparation

The release directory is created.

The operation is idempotent because `create_directories` does not fail merely because the requested directory already exists.

### Artifact verification

The artifact content is associated with the application and version.

The case study demonstrates digest comparison while explicitly avoiding the false claim that `std::hash` is cryptographically secure.

### Deployment

A release metadata file is created.

The deployed version is updated.

### Health check

The deployment runs several deterministic checks.

The design can be extended to actual process, port, HTTP, database, or service checks.

### Rollback

If the deployment becomes unhealthy, the previous version is restored in the modeled state.

## Why three languages are used

The three implementations demonstrate different aspects of shell scripting.

### Bash concepts through Python

Python provides an accessible environment for modeling:

- shell terminology
- variables
- control flow
- filesystem behavior
- validation
- error handling
- deployment state
- automation architecture

It also makes complex data structures easier to represent while keeping the conceptual focus on Bash.

### Shell orchestration through JavaScript

Node.js is particularly useful for demonstrating:

- process spawning
- argument vectors
- environment inheritance
- asynchronous operations
- streams
- filesystem APIs
- concurrency limits
- Promise-based error handling

These capabilities make it possible to compare Bash background processes and pipelines with application-level process orchestration.

### Industry-style system modeling through C++

C++ demonstrates:

- explicit types
- class-based architecture
- deterministic validation
- filesystem APIs
- exception handling
- resource management
- concurrency
- synchronization
- complexity analysis

The C++ program models a deployment controller rather than merely reproducing Bash syntax.

## Important distinctions

| Concept | Bash | Python | JavaScript | C++ |
|---|---|---|---|---|
| Primary role in these files | Shell automation concepts | Educational modeling | Process and async orchestration | Deployment system case study |
| Variables | Shell parameters | Typed dynamically at runtime | Dynamically typed bindings | Explicit static types |
| Functions | Shell functions | Functions | Functions | Functions and methods |
| Arrays | Bash arrays | Lists | Arrays | `std::vector` |
| Key-value data | Associative arrays | Dictionaries | Objects/Maps | `std::map` |
| Failure mechanism | Exit status | Exceptions/return values | Exceptions/rejected promises | Exceptions/status values |
| Processes | Native shell behavior | Subprocess APIs | `spawn`/`execFile` | Explicit process APIs or system interfaces |
| Concurrency | Background jobs | Threads/processes/async facilities | Async event-driven model | Threads/futures |
| Filesystem | Unix commands and shell redirection | `pathlib` | `fs/promises` | `std::filesystem` |
| Configuration | Variables/environment/arguments | Dataclasses | Classes/objects | Structs/classes |
| Main strength | Orchestration | General-purpose automation | Event-driven process orchestration | Systems and performance-oriented applications |

## When shell scripting is appropriate

Bash is particularly suitable when the task involves:

- invoking existing Unix tools
- connecting commands with pipelines
- managing files and directories
- starting and stopping services
- deployment orchestration
- build automation
- environment setup
- scheduled maintenance
- simple system administration
- combining specialized command-line programs

## When another language is more appropriate

A different language becomes attractive when the problem requires:

- complex algorithms
- large data structures
- sophisticated application state
- large-scale data processing
- extensive testing infrastructure
- complex networking
- advanced concurrency
- cross-platform application logic
- database-heavy application behavior
- substantial domain modeling

A common production architecture is therefore not Bash versus another language, but Bash plus another language.

For example, Bash can orchestrate a deployment while Python implements complex data validation or C++ provides a high-performance binary.

## Implementation considerations

A production shell script should be treated as software rather than as a disposable list of commands.

Important engineering practices include:

- explicit interpreter selection
- deliberate shell options
- input validation
- careful quoting
- controlled subprocess execution
- meaningful exit statuses
- clear logging
- cleanup handlers
- bounded retries
- bounded concurrency
- idempotent operations
- secure temporary resources
- least-privilege execution
- testable functions
- clear configuration handling
- documented failure behavior

The complexity of the script should also be monitored. When a shell script begins implementing extensive business logic, complex parsing, sophisticated state management, or large algorithms, moving that portion into a general-purpose language can improve maintainability and testability.

## Execution

The Python file can be executed with a Python 3 interpreter.

The JavaScript file can be executed with a modern Node.js runtime.

The C++ program requires a compiler supporting C++17 or later.

The C++ implementation uses only standard-library facilities.

The Python and JavaScript implementations likewise avoid external package requirements.

## Relationship between the implementations

The three files are not intended to be identical translations.

The Python implementation emphasizes conceptual learning and executable demonstrations.

The JavaScript implementation emphasizes operating-system integration, asynchronous process control, filesystem APIs, and bounded concurrency.

The C++ implementation emphasizes a realistic deployment architecture with explicit state, validation, resource handling, logging, health checks, rollback, retries, and concurrency.

Together, these perspectives show why Bash remains valuable for system automation while also clarifying the boundary between shell orchestration and application development.

## Technical limitations

Bash has several characteristics that become limitations as scripts grow:

- implicit string-oriented data representation
- complex quoting rules
- context-sensitive error behavior
- limited native data structures
- process overhead for repeated external commands
- portability differences between shells
- difficult large-scale testing
- complicated concurrency behavior
- difficult structured-data processing
- subtle interactions between expansion mechanisms

These are not reasons to avoid Bash. They are architectural constraints that should influence where Bash is used.

A small, well-structured Bash script can be easier to maintain than a large application written in a more powerful language. A large Bash program can become difficult to reason about when it crosses the boundary into application-level complexity.

The appropriate design depends on the problem, operating environment, reliability requirements, security model, performance requirements, and maintenance expectations.
